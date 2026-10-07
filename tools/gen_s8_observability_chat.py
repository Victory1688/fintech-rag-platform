# -*- coding: utf-8 -*-
"""
S8: rag-chat-service 可观测埋点

【重要】本脚本必须在 s6 之后执行：会覆写 s6 生成的下列文件
         - app/service/ChatOrchestrationAppService.java（业务根 span + 结果归因）
         - api/controller/ChatController.java（修复异步 SSE 上下文/traceId 丢失）
         - infra/llm/LlmRouter.java（模型实例挂载埋点监听器）
         - domain/model/ChatMessage.java（补 traceId）
         - src/main/resources/application.yml（OTLP + 采集档位）

执行顺序：s1 → s2 → s3 → s4 → s5 → s6 → s7 → s8 → s9 → s10 → check_skeleton.py
"""
import pathlib

BASE = pathlib.Path(r"D:/AiWorkOut/java-ai/rag-platform")
FILES = {}


def add(rel, content):
    FILES[rel] = content.lstrip("\n")


# ============================================================================
# 1. ChatMessage：补 traceId（把本地消息与链路里的 Trace 对上）
# ============================================================================
add("rag-chat-service/src/main/java/com/fintech/rag/chat/domain/model/ChatMessage.java", r'''
package com.fintech.rag.chat.domain.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 消息。
 *
 * @author rag-platform
 */
@Data
@TableName("t_message")
public class ChatMessage {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private Long tenantId;

    private Long conversationId;

    private String messageNo;

    private Long parentId;

    /** USER / ASSISTANT / SYSTEM / TOOL */
    private String role;

    private String content;

    private Integer contentTokens;

    /** ANSWERED / NO_HIT / GUARDRAIL_BLOCKED / ERROR */
    private String answerType;

    private String modelCode;

    /** Prompt 模板版本，用于问题复现 */
    private String promptVersion;

    private Long retrievalLogId;

    private String guardrailHit;

    /**
     * 全链路 traceId（W3C 32 位 hex）。
     *
     * <p>用途：把「本地消息」与「可观测平台里的那条 Trace」对上。
     * 用户点踩时先查消息拿 traceId，再去 LangFuse 按 traceId 回放完整链路 ——
     * 这是定位问题最快的路径。必须落库，因为 Trace 有 TTL 而本字段不会过期。</p>
     */
    private String traceId;

    /** 首字节时间（毫秒），流式场景的核心体验指标 */
    private Integer ttfbMs;

    private Integer costMs;

    private LocalDateTime createTime;

    @TableLogic
    private Integer deleted;
}
''')

# ============================================================================
# 2. LLM 埋点监听器
# ============================================================================
add("rag-chat-service/src/main/java/com/fintech/rag/chat/infra/llm/LlmTraceListener.java", r'''
package com.fintech.rag.chat.infra.llm;

import com.fintech.rag.common.observability.ContentLevel;
import com.fintech.rag.common.observability.ContentSanitizer;
import com.fintech.rag.common.observability.GenAiSemconv;
import com.fintech.rag.common.observability.ObservabilityProperties;
import dev.langchain4j.model.chat.listener.ChatModelErrorContext;
import dev.langchain4j.model.chat.listener.ChatModelListener;
import dev.langchain4j.model.chat.listener.ChatModelRequestContext;
import dev.langchain4j.model.chat.listener.ChatModelResponseContext;
import dev.langchain4j.model.chat.request.ChatRequest;
import dev.langchain4j.model.chat.request.ChatRequestParameters;
import dev.langchain4j.model.chat.response.ChatResponse;
import dev.langchain4j.model.output.TokenUsage;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.tracing.Span;
import io.micrometer.tracing.Tracer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.Map;

/**
 * LLM 调用埋点监听器 —— 把「模型调用」变成规范的 GenAI span 与指标。
 *
 * <p><b>为什么不用 LangChain4j 自带的观测模块</b>：自带模块目前只完整覆盖 token 用量，
 * 且模块坐标在 1.x 小版本间调整过（{@code langchain4j-observation} /
 * {@code langchain4j-micrometer-observation} 两种叫法都出现过），直接依赖有版本风险；
 * 而我们需要在 span 上挂自有业务属性（来源、会话、Prompt 版本），
 * 自己实现 100 行即可，可控可测、不用追版本。</p>
 *
 * <p><b>本监听器拿不到「首字延迟」</b>：LangChain4j 只有请求/响应/错误三个回调，
 * <b>没有逐 chunk 事件</b>，所以 TTFT/TTFC 必须由 SSE 回调层手工计时
 * （见 {@code ChatPipelineMetrics} / {@code StreamTimingRecorder}）。
 * 这一点不提前说明，落地时会误以为「接了埋点就有 TTFT」。</p>
 *
 * <p><b>版本提示</b>：LangChain4j 1.x 的 listener 包路径与 {@code attributes()}
 * 传递机制在不同小版本间调整过。IDE 若报找不到类/方法，请按实际版本调整。</p>
 *
 * @author rag-platform
 */
@Component
public class LlmTraceListener implements ChatModelListener {

    private static final Logger log = LoggerFactory.getLogger(LlmTraceListener.class);

    /** 通过 attributes 在回调间传递状态：onRequest 在调用线程，onResponse 可能在 IO 线程 */
    private static final String KEY_START_NANOS = "rag.llm.start.nanos";
    private static final String KEY_SPAN = "rag.llm.span";
    private static final String KEY_MODEL = "rag.llm.model";
    private static final String UNKNOWN_MODEL = "unknown";

    private final ObjectProvider<Tracer> tracerProvider;
    private final MeterRegistry meterRegistry;
    private final ObservabilityProperties properties;
    private final ContentSanitizer sanitizer;

    public LlmTraceListener(ObjectProvider<Tracer> tracerProvider,
                           MeterRegistry meterRegistry,
                           ObservabilityProperties properties,
                           ContentSanitizer sanitizer) {
        this.tracerProvider = tracerProvider;
        this.meterRegistry = meterRegistry;
        this.properties = properties;
        this.sanitizer = sanitizer;
    }

    @Override
    public void onRequest(ChatModelRequestContext requestContext) {
        try {
            Map<Object, Object> attributes = requestContext.attributes();
            attributes.put(KEY_START_NANOS, System.nanoTime());

            ChatRequest chatRequest = requestContext.chatRequest();
            ChatRequestParameters parameters = chatRequest == null ? null : chatRequest.parameters();
            String model = parameters == null || parameters.modelName() == null
                    ? UNKNOWN_MODEL : parameters.modelName();
            attributes.put(KEY_MODEL, model);

            Tracer tracer = tracerProvider.getIfAvailable();
            if (tracer == null) {
                return;
            }
            Span span = tracer.nextSpan()
                    .name(GenAiSemconv.inferenceSpanName(GenAiSemconv.OP_CHAT, model));
            // 采样相关属性必须在 span 创建时设置，否则尾部采样无法按模型决策
            span.tag(GenAiSemconv.ATTR_OPERATION_NAME, GenAiSemconv.OP_CHAT);
            span.tag(GenAiSemconv.ATTR_PROVIDER_NAME, properties.getProviderName());
            span.tag(GenAiSemconv.ATTR_REQUEST_MODEL, model);
            if (parameters != null) {
                tagDouble(span, GenAiSemconv.ATTR_REQUEST_TEMPERATURE, parameters.temperature());
                tagDouble(span, GenAiSemconv.ATTR_REQUEST_TOP_P, parameters.topP());
                tagInt(span, GenAiSemconv.ATTR_REQUEST_MAX_TOKENS, parameters.maxOutputTokens());
            }
            tagInputContent(span, attributes, chatRequest);
            attributes.put(KEY_SPAN, span.start());
        } catch (Exception ex) {
            // 埋点永不影响业务：监听器内任何异常都必须吞掉并记日志
            log.warn("LLM 埋点 onRequest 异常（已忽略）", ex);
        }
    }

    @Override
    public void onResponse(ChatModelResponseContext responseContext) {
        try {
            Map<Object, Object> attributes = responseContext.attributes();
            Object spanHolder = attributes.get(KEY_SPAN);
            String model = String.valueOf(attributes.getOrDefault(KEY_MODEL, UNKNOWN_MODEL));
            ChatResponse response = responseContext.chatResponse();

            TokenUsage usage = response == null ? null : response.tokenUsage();
            long inputTokens = usage == null || usage.inputTokenCount() == null ? 0 : usage.inputTokenCount();
            long outputTokens = usage == null || usage.outputTokenCount() == null ? 0 : usage.outputTokenCount();

            if (spanHolder instanceof Span span) {
                span.tag(GenAiSemconv.ATTR_INPUT_TOKENS, inputTokens);
                span.tag(GenAiSemconv.ATTR_OUTPUT_TOKENS, outputTokens);
                if (response != null && response.metadata() != null
                        && response.metadata().modelName() != null) {
                    span.tag(GenAiSemconv.ATTR_RESPONSE_MODEL, response.metadata().modelName());
                }
                tagOutputContent(span, response);
                span.end();
            }
            recordMetrics(attributes, model, inputTokens, outputTokens, null);
        } catch (Exception ex) {
            log.warn("LLM 埋点 onResponse 异常（已忽略）", ex);
        }
    }

    @Override
    public void onError(ChatModelErrorContext errorContext) {
        try {
            Map<Object, Object> attributes = errorContext.attributes();
            Object spanHolder = attributes.get(KEY_SPAN);
            String model = String.valueOf(attributes.getOrDefault(KEY_MODEL, UNKNOWN_MODEL));
            Throwable error = errorContext.error();

            if (spanHolder instanceof Span span) {
                span.tag(GenAiSemconv.ATTR_ERROR_TYPE, errorType(error));
                if (error != null) {
                    span.error(error);
                }
                span.end();
            }
            recordMetrics(attributes, model, 0, 0, errorType(error));
        } catch (Exception ex) {
            log.warn("LLM 埋点 onError 异常（已忽略）", ex);
        }
    }

    // ------------------------------------------------------------------ 内容采集
    private void tagInputContent(Span span, Map<Object, Object> attributes, ChatRequest chatRequest) {
        ContentLevel level = properties.effectiveContentLevel();
        if (!level.allowsAnyContent() || chatRequest == null || chatRequest.messages() == null) {
            return;
        }
        String joined = joinMessages(chatRequest);
        String content = sanitizer.forReporting(joined);
        if (content == null) {
            // 只允许指纹的档位：上报指纹与长度，绝不落原文
            span.tag(GenAiSemconv.ATTR_INPUT_MESSAGES + ".fingerprint", sanitizer.fingerprint(joined));
            span.tag(GenAiSemconv.ATTR_INPUT_MESSAGES + ".length", String.valueOf(joined.length()));
            return;
        }
        span.tag(GenAiSemconv.ATTR_INPUT_MESSAGES, content);
        attributes.put(GenAiSemconv.ATTR_INPUT_MESSAGES, content);
    }

    private void tagOutputContent(Span span, ChatResponse response) {
        ContentLevel level = properties.effectiveContentLevel();
        if (!level.allowsAnyContent() || response == null || response.aiMessage() == null) {
            return;
        }
        String text = response.aiMessage().text();
        if (text == null) {
            return;
        }
        String content = sanitizer.forReporting(text);
        if (content == null) {
            span.tag(GenAiSemconv.ATTR_OUTPUT_MESSAGES + ".fingerprint", sanitizer.fingerprint(text));
            return;
        }
        span.tag(GenAiSemconv.ATTR_OUTPUT_MESSAGES, content);
    }

    private String joinMessages(ChatRequest chatRequest) {
        StringBuilder sb = new StringBuilder();
        chatRequest.messages().forEach(message -> {
            if (message != null) {
                sb.append(message.type()).append(": ").append(String.valueOf(message)).append('\n');
            }
        });
        return sb.toString();
    }

    // ------------------------------------------------------------------ 指标
    private void recordMetrics(Map<Object, Object> attributes, String model,
                               long inputTokens, long outputTokens, String errorType) {
        String provider = properties.getProviderName();
        if (inputTokens > 0) {
            meterRegistry.summary(GenAiSemconv.METRIC_TOKEN_USAGE,
                            GenAiSemconv.TAG_TOKEN_TYPE, GenAiSemconv.TOKEN_TYPE_INPUT,
                            GenAiSemconv.TAG_REQUEST_MODEL, model,
                            GenAiSemconv.TAG_PROVIDER_NAME, provider)
                    .record(inputTokens);
        }
        if (outputTokens > 0) {
            meterRegistry.summary(GenAiSemconv.METRIC_TOKEN_USAGE,
                            GenAiSemconv.TAG_TOKEN_TYPE, GenAiSemconv.TOKEN_TYPE_OUTPUT,
                            GenAiSemconv.TAG_REQUEST_MODEL, model,
                            GenAiSemconv.TAG_PROVIDER_NAME, provider)
                    .record(outputTokens);
        }
        Object startHolder = attributes.get(KEY_START_NANOS);
        if (startHolder instanceof Long startNanos) {
            Duration duration = Duration.ofNanos(System.nanoTime() - startNanos);
            if (errorType == null) {
                meterRegistry.timer(GenAiSemconv.METRIC_OPERATION_DURATION,
                                GenAiSemconv.TAG_REQUEST_MODEL, model,
                                GenAiSemconv.TAG_PROVIDER_NAME, provider)
                        .record(duration);
            } else {
                meterRegistry.timer(GenAiSemconv.METRIC_OPERATION_DURATION,
                                GenAiSemconv.TAG_REQUEST_MODEL, model,
                                GenAiSemconv.TAG_PROVIDER_NAME, provider,
                                GenAiSemconv.TAG_ERROR_TYPE, errorType)
                        .record(duration);
            }
        }
    }

    private void tagDouble(Span span, String key, Double value) {
        if (value != null) {
            span.tag(key, value);
        }
    }

    private void tagInt(Span span, String key, Integer value) {
        if (value != null) {
            span.tag(key, (long) value);
        }
    }

    /** 用异常类名而非 message 作为 error.type —— message 无界，会打爆指标基数 */
    private String errorType(Throwable error) {
        return error == null ? "unknown" : error.getClass().getName();
    }
}
''')

# ============================================================================
# 3. 流式计时器 + 管线指标
# ============================================================================
add("rag-chat-service/src/main/java/com/fintech/rag/chat/app/metric/StreamTimingRecorder.java", r'''
package com.fintech.rag.chat.app.metric;

import com.fintech.rag.common.observability.GenAiSemconv;
import io.micrometer.core.instrument.MeterRegistry;

import java.time.Duration;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;

/**
 * 流式计时器 —— 手工埋点的 TTFT / TTFC（无法自动获得）。
 *
 * <p>OpenTelemetry 自 v1.41.0 定义了对应指标名，本节按规范名上报：</p>
 * <ul>
 *   <li>{@code gen_ai.client.operation.time_to_first_chunk} —— 首字延迟</li>
 *   <li>{@code gen_ai.client.operation.time_per_output_chunk} —— 吐字间隔</li>
 * </ul>
 *
 * <p><b>口径提醒</b>：本类的首字延迟从「请求进入编排层」开始计时，<b>包含检索耗时</b>，
 * 这是用户真实感知的延迟；而模型 span 的 duration 只含模型调用。两者不可混用，
 * 看板必须分开画，否则会得出「模型变快了但用户觉得更慢」这类矛盾结论。</p>
 *
 * @author rag-platform
 */
public class StreamTimingRecorder {

    private static final long MAX_SANE_GAP_NANOS = Duration.ofSeconds(10).toNanos();

    private final MeterRegistry meterRegistry;
    private final long startNanos;
    private final String model;
    private final String appSource;

    private final AtomicInteger chunks = new AtomicInteger();
    private final AtomicLong lastChunkNanos = new AtomicLong();
    private final AtomicLong firstChunkNanos = new AtomicLong();

    public StreamTimingRecorder(MeterRegistry meterRegistry, long startNanos,
                                String model, String appSource) {
        this.meterRegistry = meterRegistry;
        this.startNanos = startNanos;
        this.model = model;
        this.appSource = appSource;
        this.lastChunkNanos.set(startNanos);
    }

    /** 每收到一个增量片段调用一次 */
    public void onChunk() {
        long now = System.nanoTime();
        int index = chunks.incrementAndGet();
        if (index == 1) {
            firstChunkNanos.set(now);
            record(GenAiSemconv.METRIC_TIME_TO_FIRST_CHUNK, now - startNanos);
            return;
        }
        long gap = now - lastChunkNanos.get();
        lastChunkNanos.set(now);
        // 滤掉离群值：GC 停顿与网络抖动会把均值拉偏
        if (gap > 0 && gap < MAX_SANE_GAP_NANOS) {
            record(GenAiSemconv.METRIC_TIME_PER_OUTPUT_CHUNK, gap);
        }
    }

    /** 首字延迟（毫秒）；未收到任何片段时返回 null */
    public Integer firstChunkMs() {
        long first = firstChunkNanos.get();
        return first == 0 ? null : (int) ((first - startNanos) / 1_000_000L);
    }

    public int chunkCount() {
        return chunks.get();
    }

    private void record(String metric, long nanos) {
        meterRegistry.timer(metric,
                        GenAiSemconv.TAG_REQUEST_MODEL, model,
                        GenAiSemconv.TAG_APP_SOURCE, appSource)
                .record(Duration.ofNanos(Math.max(nanos, 0)));
    }
}
''')

add("rag-chat-service/src/main/java/com/fintech/rag/chat/app/metric/ChatPipelineMetrics.java", r'''
package com.fintech.rag.chat.app.metric;

import com.fintech.rag.common.observability.GenAiSemconv;
import com.fintech.rag.common.observability.RagOutcome;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.stereotype.Component;

/**
 * 问答管线指标 —— 质量看板与告警的数据来源。
 *
 * <p><b>标签纪律（写错会导致 Prometheus 内存爆炸）</b>：只允许枚举型、有界的标签
 * （outcome / app_source / model_code / guardrail_type / vote / reason_code）；
 * <b>禁止</b>把 userId、conversationId、traceId、提问原文做成标签。</p>
 *
 * @author rag-platform
 */
@Component
public class ChatPipelineMetrics {

    private final MeterRegistry meterRegistry;

    public ChatPipelineMetrics(MeterRegistry meterRegistry) {
        this.meterRegistry = meterRegistry;
    }

    /** 记录一次回答的业务结果。空召回率 = NO_HIT / 总数，是知识库覆盖度的核心指标 */
    public void recordAnswer(RagOutcome outcome, String appSource, String modelCode) {
        meterRegistry.counter(GenAiSemconv.METRIC_CHAT_ANSWER_TOTAL,
                        GenAiSemconv.TAG_OUTCOME, outcome.name(),
                        GenAiSemconv.TAG_APP_SOURCE, safe(appSource),
                        GenAiSemconv.TAG_MODEL_CODE, safe(modelCode))
                .increment();
    }

    /** 记录护栏命中（按类型分布，用于发现「哪类护栏老在拦」） */
    public void recordGuardrailHit(String guardrailType) {
        meterRegistry.counter(GenAiSemconv.METRIC_GUARDRAIL_HIT_TOTAL,
                        GenAiSemconv.TAG_GUARDRAIL_TYPE, safe(guardrailType))
                .increment();
    }

    /** 记录用户反馈（点赞率 = like / (like + dislike)，即「采纳率」） */
    public void recordFeedback(String vote, String reasonCode) {
        meterRegistry.counter(GenAiSemconv.METRIC_FEEDBACK_TOTAL,
                        GenAiSemconv.TAG_VOTE, safe(vote),
                        GenAiSemconv.TAG_REASON_CODE, safe(reasonCode))
                .increment();
    }

    /** 开启一次流式计时（TTFC / 吐字间隔） */
    public StreamTimingRecorder startStream(long startNanos, String model, String appSource) {
        return new StreamTimingRecorder(meterRegistry, startNanos, safe(model), safe(appSource));
    }

    private String safe(String value) {
        return value == null || value.isBlank() ? "unknown" : value;
    }
}
''')

# ============================================================================
# 4. 编排层：业务根 span + 结果归因 + 流式计时
# ============================================================================
add("rag-chat-service/src/main/java/com/fintech/rag/chat/app/service/ChatOrchestrationAppService.java", r'''
package com.fintech.rag.chat.app.service;

import com.fintech.rag.api.client.RetrievalClient;
import com.fintech.rag.api.dto.chat.ChatRequest;
import com.fintech.rag.api.dto.chat.ChatResponse;
import com.fintech.rag.api.dto.common.AnswerType;
import com.fintech.rag.api.dto.retrieval.RetrievalRequest;
import com.fintech.rag.api.dto.retrieval.RetrievalResponse;
import com.fintech.rag.chat.app.guard.AnswerGuardrail;
import com.fintech.rag.chat.app.metric.ChatPipelineMetrics;
import com.fintech.rag.chat.app.metric.StreamTimingRecorder;
import com.fintech.rag.chat.app.prompt.PromptTemplateRegistry;
import com.fintech.rag.chat.domain.model.ChatMessage;
import com.fintech.rag.chat.infra.llm.LlmRouter;
import com.fintech.rag.chat.infra.persistence.mapper.ChatMessageMapper;
import com.fintech.rag.common.context.RequestContext;
import com.fintech.rag.common.core.R;
import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import com.fintech.rag.common.observability.ContentSanitizer;
import com.fintech.rag.common.observability.GenAiSemconv;
import com.fintech.rag.common.observability.ObservabilityProperties;
import com.fintech.rag.common.observability.RagOutcome;
import dev.langchain4j.data.message.AiMessage;
import dev.langchain4j.data.message.SystemMessage;
import dev.langchain4j.data.message.UserMessage;
import dev.langchain4j.model.chat.ChatModel;
import dev.langchain4j.model.chat.StreamingChatModel;
import dev.langchain4j.model.chat.response.StreamingChatResponseHandler;
import io.micrometer.tracing.Span;
import io.micrometer.tracing.Tracer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.function.Consumer;

/**
 * 问答编排应用服务 —— <b>生成链路的唯一编排点</b>。
 *
 * <p>链路：鉴权（拦截器已完成）→ 检索 → 空召回判定 → 组装 Prompt → 调用模型
 * → 护栏校验 → 落库 → 计量上报。</p>
 *
 * <p><b>「无据不答」是本服务的最高优先级规则</b>：检索结果为空时直接返回兜底话术，
 * <b>绝不调用大模型</b>。原因很简单——调用模型就一定会有编造风险，
 * 且无法通过护栏事后 100% 拦住。</p>
 *
 * <p><b>可观测设计</b>：本服务创建业务根 span {@code rag.chat.answer}，标注
 * 「来源 / 主体哈希 / 结果归因 / 引用数 / 护栏命中」。模型 span 由
 * {@code LlmTraceListener} 产出，检索 span 由 retrieval 服务产出，
 * 三者经同一条 traceId 串成一棵树 —— 这样「回答错了」才能一眼看出是检索问题还是生成问题。</p>
 *
 * @author rag-platform
 */
@Service
public class ChatOrchestrationAppService {

    private static final Logger log = LoggerFactory.getLogger(ChatOrchestrationAppService.class);

    private final RetrievalClient retrievalClient;
    private final LlmRouter llmRouter;
    private final PromptTemplateRegistry promptRegistry;
    private final AnswerGuardrail guardrail;
    private final ConversationMemoryStore memoryStore;
    private final ChatMessageMapper messageMapper;
    private final ChatPipelineMetrics metrics;
    private final ObjectProvider<Tracer> tracerProvider;
    private final ObservabilityProperties observabilityProperties;
    private final ContentSanitizer sanitizer;

    public ChatOrchestrationAppService(RetrievalClient retrievalClient,
                                       LlmRouter llmRouter,
                                       PromptTemplateRegistry promptRegistry,
                                       AnswerGuardrail guardrail,
                                       ConversationMemoryStore memoryStore,
                                       ChatMessageMapper messageMapper,
                                       ChatPipelineMetrics metrics,
                                       ObjectProvider<Tracer> tracerProvider,
                                       ObservabilityProperties observabilityProperties,
                                       ContentSanitizer sanitizer) {
        this.retrievalClient = retrievalClient;
        this.llmRouter = llmRouter;
        this.promptRegistry = promptRegistry;
        this.guardrail = guardrail;
        this.memoryStore = memoryStore;
        this.messageMapper = messageMapper;
        this.metrics = metrics;
        this.tracerProvider = tracerProvider;
        this.observabilityProperties = observabilityProperties;
        this.sanitizer = sanitizer;
    }

    // ------------------------------------------------------------------ 非流式
    public ChatResponse chat(ChatRequest request, String subjectType, String subjectId,
                             String roleCodes, Long deptId) {
        long start = System.currentTimeMillis();
        String appSource = resolveAppSource();
        Span span = startBusinessSpan(request, appSource);
        try {
            RetrievalResponse retrieval = retrieve(request, subjectType, subjectId, roleCodes, deptId);

            // 空召回：不调用大模型，直接兜底
            if (retrieval == null || retrieval.emptyHit() || retrieval.chunks().isEmpty()) {
                return buildNoHitResponse(request, start, appSource, span);
            }

            int secretLevel = resolveSecretLevel(request);
            String modelCode = llmRouter.routeCode(secretLevel);
            String systemPrompt = promptRegistry.systemPrompt();
            String userPrompt = promptRegistry.userPrompt(request.question(), retrieval.chunks());
            tagContent(span, GenAiSemconv.ATTR_SYSTEM_INSTRUCTIONS, systemPrompt);
            tagContent(span, GenAiSemconv.ATTR_INPUT_MESSAGES, userPrompt);
            ChatModel model = llmRouter.route(secretLevel);

            AiMessage aiMessage = model.chat(toLcMessages(request, systemPrompt, userPrompt)).aiMessage();
            String rawAnswer = aiMessage == null ? "" : aiMessage.text();

            AnswerGuardrail.GuardrailResult guardResult = guardrail.check(rawAnswer, retrieval.chunks().size());
            int cost = (int) (System.currentTimeMillis() - start);

            Long messageId = saveAssistantMessage(request, guardResult.answer(),
                    AnswerType.ANSWERED.name(), modelCode, cost, null);

            tagSuccess(span, retrieval.chunks().size(), guardResult, modelCode);
            metrics.recordAnswer(RagOutcome.ANSWERED, appSource, modelCode);

            return new ChatResponse(
                    messageId == null ? null : String.valueOf(messageId),
                    request.conversationId(),
                    AnswerType.ANSWERED,
                    guardResult.answer(),
                    buildCitations(retrieval),
                    guardResult.toGuardrail(),
                    modelCode,
                    ChatResponse.Usage.zero(),
                    0,
                    cost,
                    promptRegistry.disclaimer());
        } catch (RuntimeException ex) {
            tagFailure(span, ex);
            metrics.recordAnswer(RagOutcome.ERROR, appSource, null);
            throw ex;
        } finally {
            end(span);
        }
    }

    // ------------------------------------------------------------------ 流式
    /**
     * 流式问答。
     *
     * <p>检索一次性完成（不流式），随后模型增量返回 token，通过 {@code onDelta} 逐段推送。</p>
     *
     * <p><b>TTFC 手工埋点</b>：每收到一个片段调用一次计时器；首个片段记
     * {@code time_to_first_chunk}，后续记 {@code time_per_output_chunk}。</p>
     *
     * @param onDelta  增量回调
     * @param onFinish 完成回调（携带护栏处理后的完整答案与引用）
     * @param onError  异常回调
     */
    public void stream(ChatRequest request, String subjectType, String subjectId,
                       String roleCodes, Long deptId,
                       Consumer<String> onDelta,
                       java.util.function.BiConsumer<String, List<ChatResponse.Citation>> onFinish,
                       Consumer<Throwable> onError) {
        long startNanos = System.nanoTime();
        long start = System.currentTimeMillis();
        String appSource = resolveAppSource();
        Span span = startBusinessSpan(request, appSource);

        RetrievalResponse retrieval;
        try {
            retrieval = retrieve(request, subjectType, subjectId, roleCodes, deptId);
        } catch (Exception ex) {
            tagFailure(span, ex);
            end(span);
            metrics.recordAnswer(RagOutcome.ERROR, appSource, null);
            onError.accept(ex);
            return;
        }

        if (retrieval == null || retrieval.emptyHit() || retrieval.chunks().isEmpty()) {
            String noHit = promptRegistry.noHitAnswer();
            onDelta.accept(noHit);
            onFinish.accept(noHit, List.of());
            saveAssistantMessage(request, noHit, AnswerType.NO_HIT.name(), null,
                    (int) (System.currentTimeMillis() - start), null);
            tagOutcome(span, RagOutcome.NO_HIT, 0);
            end(span);
            metrics.recordAnswer(RagOutcome.NO_HIT, appSource, null);
            return;
        }

        int secretLevel = resolveSecretLevel(request);
        String modelCode = llmRouter.routeCode(secretLevel);
        StreamingChatModel model = llmRouter.routeStreaming(secretLevel);
        List<ChatResponse.Citation> citations = buildCitations(retrieval);
        StringBuilder buffer = new StringBuilder();

        StreamTimingRecorder timing = metrics.startStream(startNanos, modelCode, appSource);

        model.chat(toLcMessages(request, promptRegistry.systemPrompt(),
                        promptRegistry.userPrompt(request.question(), retrieval.chunks())),
                new StreamingChatResponseHandler() {

                    @Override
                    public void onPartialResponse(String partialResponse) {
                        timing.onChunk();
                        buffer.append(partialResponse);
                        onDelta.accept(partialResponse);
                    }

                    @Override
                    public void onCompleteResponse(dev.langchain4j.model.chat.response.ChatResponse response) {
                        AnswerGuardrail.GuardrailResult guardResult =
                                guardrail.check(buffer.toString(), citations.size());
                        int cost = (int) (System.currentTimeMillis() - start);
                        Integer ttfbMs = timing.firstChunkMs();
                        saveAssistantMessage(request, guardResult.answer(),
                                AnswerType.ANSWERED.name(), modelCode, cost, ttfbMs);

                        tagSuccess(span, citations.size(), guardResult, modelCode);
                        tagSpan(span, "rag.stream.chunk.count", timing.chunkCount());
                        end(span);
                        metrics.recordAnswer(RagOutcome.ANSWERED, appSource, modelCode);

                        onFinish.accept(guardResult.answer(), citations);
                    }

                    @Override
                    public void onError(Throwable error) {
                        log.error("流式生成失败 conversationId={}", request.conversationId(), error);
                        tagFailure(span, error);
                        end(span);
                        metrics.recordAnswer(RagOutcome.ERROR, appSource, modelCode);
                        onError.accept(error);
                    }
                });
    }

    // ------------------------------------------------------------------ 内部
    private RetrievalResponse retrieve(ChatRequest request, String subjectType, String subjectId,
                                       String roleCodes, Long deptId) {
        RetrievalRequest.Options options = request.options() == null
                ? RetrievalRequest.Options.defaults() : request.options();

        RetrievalRequest retrievalRequest = new RetrievalRequest(
                request.question(),
                com.fintech.rag.api.dto.common.SubjectType.valueOf(subjectType),
                subjectId,
                request.kbIds(),
                RetrievalRequest.Filters.defaults(),
                new RetrievalRequest.Options(
                        options.topN(), new java.math.BigDecimal("0.20"),
                        new java.math.BigDecimal("0.30"), Boolean.TRUE),
                RequestContext.currentTraceId(),
                parseLongQuietly(request.conversationId()));

        R<RetrievalResponse> result = retrievalClient.search(retrievalRequest);
        if (result == null || !result.isSuccess() || result.getData() == null) {
            // fail-close：检索不可用时拒绝作答，绝不「不检索直接生成」
            throw BizException.of(ErrorCode.DEPENDENCY_UNAVAILABLE, "检索服务暂不可用，请稍后重试");
        }
        return result.getData();
    }

    private List<dev.langchain4j.data.message.ChatMessage> toLcMessages(
            ChatRequest request, String systemPrompt, String userPrompt) {
        List<dev.langchain4j.data.message.ChatMessage> messages = new ArrayList<>();
        messages.add(SystemMessage.from(systemPrompt));

        // 历史轮次：仅取 USER / ASSISTANT，且截断长度，防止上下文超长
        List<ChatMessage> history = memoryStore.recent(parseLongQuietly(request.conversationId()));
        for (ChatMessage message : history) {
            String role = message.getRole();
            if ("USER".equals(role)) {
                messages.add(UserMessage.from(truncate(message.getContent(), 500)));
            } else if ("ASSISTANT".equals(role)) {
                messages.add(AiMessage.from(truncate(message.getContent(), 500)));
            }
        }

        messages.add(UserMessage.from(userPrompt));
        return messages;
    }

    private int resolveSecretLevel(ChatRequest request) {
        // 骨架：默认按「内部」密级处理；落地时按知识库密级与用户密级取较高者
        return 2;
    }

    private List<ChatResponse.Citation> buildCitations(RetrievalResponse retrieval) {
        List<ChatResponse.Citation> citations = new ArrayList<>();
        int seq = 1;
        for (RetrievalResponse.Chunk chunk : retrieval.chunks()) {
            citations.add(new ChatResponse.Citation(
                    seq++, chunk.kbId(), chunk.docId(), chunk.docName(), chunk.versionNo(),
                    chunk.pageNo(), chunk.chunkIndex(), chunk.score(), chunk.content()));
        }
        return citations;
    }

    private ChatResponse buildNoHitResponse(ChatRequest request, long start, String appSource, Span span) {
        int cost = (int) (System.currentTimeMillis() - start);
        String answer = promptRegistry.noHitAnswer();
        Long messageId = saveAssistantMessage(request, answer, AnswerType.NO_HIT.name(), null, cost, null);
        tagOutcome(span, RagOutcome.NO_HIT, 0);
        metrics.recordAnswer(RagOutcome.NO_HIT, appSource, null);
        return new ChatResponse(
                messageId == null ? null : String.valueOf(messageId),
                request.conversationId(),
                AnswerType.NO_HIT,
                answer,
                List.of(),
                ChatResponse.Guardrail.pass(),
                null,
                ChatResponse.Usage.zero(),
                0,
                cost,
                promptRegistry.disclaimer());
    }

    private Long saveAssistantMessage(ChatRequest request, String answer, String answerType,
                                      String modelCode, int cost, Integer ttfbMs) {
        try {
            ChatMessage message = new ChatMessage();
            message.setTenantId(0L);
            message.setConversationId(parseLongQuietly(request.conversationId()));
            message.setMessageNo("M" + UUID.randomUUID().toString().replace("-", ""));
            message.setRole("ASSISTANT");
            message.setContent(answer);
            message.setAnswerType(answerType);
            message.setModelCode(modelCode);
            message.setPromptVersion(PromptTemplateRegistry.VERSION);
            message.setTraceId(RequestContext.currentTraceId());
            message.setTtfbMs(ttfbMs);
            message.setCostMs(cost);
            message.setDeleted(0);
            messageMapper.insert(message);
            return message.getId();
        } catch (Exception ex) {
            // 落库失败不能影响用户已经看到的答案，但必须告警
            log.error("保存消息失败 conversationId={}", request.conversationId(), ex);
            return null;
        }
    }

    // -------------------------------------------------------------- 可观测辅助
    private Span startBusinessSpan(ChatRequest request, String appSource) {
        Tracer tracer = tracerProvider.getIfAvailable();
        if (tracer == null) {
            return null;
        }
        Span span = tracer.nextSpan().name(GenAiSemconv.SPAN_BUSINESS_CHAT).start();
        tagSpan(span, GenAiSemconv.ATTR_SOURCE, appSource);
        tagSpan(span, GenAiSemconv.ATTR_CONVERSATION_ID, request.conversationId());
        tagSpan(span, GenAiSemconv.ATTR_PROMPT_VERSION, PromptTemplateRegistry.VERSION);
        // 主体只上报哈希：既不丢失维度归因，也不落可识别身份信息
        tagSpan(span, GenAiSemconv.ATTR_SUBJECT_HASH,
                sanitizer.subjectHash(RequestContext.currentSubjectId()));
        if (request.kbIds() != null) {
            tagSpan(span, GenAiSemconv.ATTR_KB_COUNT, request.kbIds().size());
        }
        return span;
    }

    private void tagSuccess(Span span, int citationCount,
                           AnswerGuardrail.GuardrailResult guardResult, String modelCode) {
        tagOutcome(span, RagOutcome.ANSWERED, citationCount);
        tagSpan(span, GenAiSemconv.TAG_MODEL_CODE, modelCode);
        if (guardResult != null && guardResult.toGuardrail() != null
                && guardResult.toGuardrail().hit()) {
            tagSpan(span, GenAiSemconv.ATTR_GUARDRAIL_HIT, "true");
            if (guardResult.toGuardrail().types() != null) {
                guardResult.toGuardrail().types()
                        .forEach(type -> metrics.recordGuardrailHit(String.valueOf(type)));
            }
        }
    }

    private void tagOutcome(Span span, RagOutcome outcome, int citationCount) {
        tagSpan(span, GenAiSemconv.ATTR_OUTCOME, outcome.name());
        tagSpan(span, GenAiSemconv.ATTR_CITATION_COUNT, citationCount);
    }

    private void tagFailure(Span span, Throwable error) {
        if (span == null) {
            return;
        }
        tagSpan(span, GenAiSemconv.ATTR_OUTCOME, RagOutcome.ERROR.name());
        tagSpan(span, GenAiSemconv.ATTR_ERROR_TYPE,
                error == null ? "unknown" : error.getClass().getName());
    }

    private void tagContent(Span span, String key, String content) {
        if (span == null) {
            return;
        }
        String sanitized = sanitizer.forReporting(content);
        if (sanitized != null) {
            tagSpan(span, key, sanitized);
        } else if (observabilityProperties.effectiveContentLevel().allowsAnyContent()) {
            tagSpan(span, key + ".fingerprint", sanitizer.fingerprint(content));
        }
    }

    private void tagSpan(Span span, String key, String value) {
        if (span != null && value != null) {
            span.tag(key, value);
        }
    }

    private void tagSpan(Span span, String key, int value) {
        if (span != null) {
            span.tag(key, (long) value);
        }
    }

    private void end(Span span) {
        if (span != null) {
            span.end();
        }
    }

    /** 请求来源（DMZ_WEB / SF_INNER_APP）：用于「外网用户流量 vs 内网应用流量」分开统计 */
    private String resolveAppSource() {
        com.fintech.rag.common.context.RequestSource source = RequestContext.currentSource();
        return source == null ? "UNKNOWN" : source.name();
    }

    private Long parseLongQuietly(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        try {
            return Long.parseLong(value);
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    private String truncate(String value, int max) {
        if (value == null) {
            return "";
        }
        return value.length() <= max ? value : value.substring(0, max);
    }
}
''')

# ============================================================================
# 5. 控制器：修复异步 SSE 的上下文 / traceId 丢失
# ============================================================================
add("rag-chat-service/src/main/java/com/fintech/rag/chat/api/controller/ChatController.java", r'''
package com.fintech.rag.chat.api.controller;

import com.fintech.rag.api.dto.chat.ChatRequest;
import com.fintech.rag.api.dto.chat.ChatResponse;
import com.fintech.rag.api.server.interceptor.SourceAuthInterceptor;
import com.fintech.rag.chat.app.service.ChatOrchestrationAppService;
import com.fintech.rag.common.context.RequestContext;
import com.fintech.rag.common.core.R;
import com.fintech.rag.common.exception.ErrorCode;
import io.micrometer.tracing.Span;
import io.micrometer.tracing.Tracer;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 问答接口。
 *
 * <p>主体身份一律从请求头获取（网关透传或 AppKey 验签结果），
 * <b>绝不从请求体读取</b>，否则用户改一个字段就能以他人身份提问。</p>
 *
 * <p><b>重要修复：异步 SSE 的上下文传递</b></p>
 * <p>流式生成跑在独立线程池里，而 {@code RequestContext}（ThreadLocal）与 MDC
 * <b>不会自动跨线程传递</b>。不显式传递会同时踩三个坑：</p>
 * <ol>
 *   <li>检索请求里的 traceId 变成 null → 检索日志与链路关联不上；</li>
 *   <li>日志里没有 traceId → 一次问答的日志串不起来；</li>
 *   <li>OTel 在当前线程找不到父 span → <b>另起一条新链路</b>，
 *       一个用户请求在 LangFuse 里变成两条互不相关的 Trace。</li>
 * </ol>
 * <p>因此这里在提交任务前捕获上下文快照与父 span，在任务线程内恢复。</p>
 *
 * @author rag-platform
 */
@RestController
@RequestMapping("/api/ai")
public class ChatController {

    private static final Logger log = LoggerFactory.getLogger(ChatController.class);

    /** SSE 超时：覆盖最长生成耗时并留余量 */
    private static final long SSE_TIMEOUT_MS = 180_000L;

    private final ChatOrchestrationAppService chatAppService;
    private final ObjectProvider<Tracer> tracerProvider;

    /**
     * 生成链路是长耗时阻塞调用，必须使用独立线程池，
     * 不能占用 Tomcat 的请求线程，否则少量并发就会把容器线程打满。
     */
    private final ExecutorService streamExecutor = Executors.newFixedThreadPool(32, r -> {
        Thread thread = new Thread(r, "chat-stream-" + System.nanoTime());
        thread.setDaemon(true);
        return thread;
    });

    public ChatController(ChatOrchestrationAppService chatAppService,
                          ObjectProvider<Tracer> tracerProvider) {
        this.chatAppService = chatAppService;
        this.tracerProvider = tracerProvider;
    }

    /** 非流式问答 */
    @PostMapping("/chat")
    public R<ChatResponse> chat(@Valid @RequestBody ChatRequest request, HttpServletRequest servletRequest) {
        SubjectContext context = resolveSubject(servletRequest);
        return R.ok(chatAppService.chat(request, context.subjectType(), context.subjectId(),
                context.roleCodes(), context.deptId()));
    }

    /**
     * 流式问答（SSE）。
     *
     * <p>事件协议：</p>
     * <pre>
     *   event: delta      数据为增量文本片段
     *   event: citations  数据为引用列表 JSON
     *   event: done       数据为完成标记
     *   event: error      数据为错误码与提示
     * </pre>
     */
    @PostMapping(value = "/chat/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter chatStream(@Valid @RequestBody ChatRequest request, HttpServletRequest servletRequest) {
        SseEmitter emitter = new SseEmitter(SSE_TIMEOUT_MS);
        SubjectContext context = resolveSubject(servletRequest);

        // ---- 捕获上下文（必须在请求线程上做） ----
        RequestContext.Snapshot snapshot = RequestContext.get();
        String traceId = RequestContext.currentTraceId();
        Tracer tracer = tracerProvider.getIfAvailable();
        Span parentSpan = tracer == null ? null : tracer.currentSpan();

        emitter.onTimeout(() -> log.warn("SSE 超时 conversationId={}", request.conversationId()));
        emitter.onError(ex -> log.warn("SSE 异常 conversationId={}", request.conversationId(), ex));

        streamExecutor.execute(() -> {
            // ---- 在线程池线程内恢复上下文 ----
            RequestContext.set(snapshot);
            if (traceId != null) {
                MDC.put("traceId", traceId);
            }
            Tracer.SpanInScope scope = null;
            if (tracer != null && parentSpan != null) {
                scope = tracer.withSpan(parentSpan);
            }
            try {
                chatAppService.stream(request, context.subjectType(), context.subjectId(),
                        context.roleCodes(), context.deptId(),
                        delta -> sendQuietly(emitter, "delta", delta),
                        (answer, citations) -> {
                            sendQuietly(emitter, "citations", citations);
                            sendQuietly(emitter, "done", "ok");
                            emitter.complete();
                        },
                        error -> {
                            sendQuietly(emitter, "error",
                                    ErrorCode.LLM_CALL_FAILED.getCode() + ":"
                                            + ErrorCode.LLM_CALL_FAILED.getMessage());
                            emitter.complete();
                        });
            } catch (Exception ex) {
                log.error("流式问答失败 conversationId={}", request.conversationId(), ex);
                sendQuietly(emitter, "error", ErrorCode.INTERNAL_ERROR.getCode());
                emitter.complete();
            } finally {
                if (scope != null) {
                    scope.close();
                }
                MDC.clear();
                RequestContext.clear();
            }
        });
        return emitter;
    }

    private void sendQuietly(SseEmitter emitter, String event, Object data) {
        try {
            emitter.send(SseEmitter.event().name(event).data(data));
        } catch (IOException | IllegalStateException ex) {
            // 客户端主动断开是常态（用户点了「停止生成」），不应记为错误
            log.debug("SSE 推送失败（客户端可能已断开）event={}", event);
        }
    }

    private SubjectContext resolveSubject(HttpServletRequest request) {
        String roles = (String) request.getAttribute(SourceAuthInterceptor.ATTR_USER_ROLES);
        String deptIdText = (String) request.getAttribute(SourceAuthInterceptor.ATTR_USER_DEPT);
        Long deptId = null;
        if (deptIdText != null && !deptIdText.isBlank()) {
            try {
                deptId = Long.parseLong(deptIdText);
            } catch (NumberFormatException ignored) {
                // 非法部门 ID 视为无部门，不放大权限
            }
        }
        String subjectType = RequestContext.currentSource()
                == com.fintech.rag.common.context.RequestSource.DMZ_WEB ? "USER" : "APP";
        String subjectId = RequestContext.currentSubjectId();
        return new SubjectContext(subjectType, subjectId, roles, deptId);
    }

    /** 调用主体上下文 */
    private record SubjectContext(String subjectType, String subjectId, String roleCodes, Long deptId) {
    }
}
''')

# ============================================================================
# 6. LlmRouter：模型实例挂载埋点监听器
# ============================================================================
add("rag-chat-service/src/main/java/com/fintech/rag/chat/infra/llm/LlmRouter.java", r'''
package com.fintech.rag.chat.infra.llm;

import com.fintech.rag.api.client.PlatformClient;
import com.fintech.rag.api.dto.platform.ModelConfigDTO;
import com.fintech.rag.common.core.R;
import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import dev.langchain4j.model.chat.ChatModel;
import dev.langchain4j.model.chat.StreamingChatModel;
import dev.langchain4j.model.openai.OpenAiChatModel;
import dev.langchain4j.model.openai.OpenAiStreamingChatModel;
import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 模型路由器 —— <b>信贷场景的合规关键组件</b>。
 *
 * <p>路由规则：</p>
 * <ol>
 *   <li>先按「本次请求涉及的最高密级」筛出可处理该密级的模型配置；</li>
 *   <li>在该集合内按 priority 升序取第一个可用模型；</li>
 *   <li>调用失败时自动切换到下一个（failover），全部失败才抛错。</li>
 * </ol>
 *
 * <p>典型配置：</p>
 * <pre>
 *   PRIMARY_CLOUD      sensitiveLevel=2  priority=100  云侧 DeepSeek/通义
 *   SENSITIVE_PRIVATE  sensitiveLevel=3  priority=10   内网私有化模型
 * </pre>
 * 高密级请求只会命中私有化通道，数据不出内网。
 *
 * <p><b>埋点挂载点</b>：模型实例构建时挂上 {@link LlmTraceListener}，
 * 使「路由」与「埋点」解耦 —— 无论路由到哪个模型埋点都自动生效，
 * 不必在业务代码里到处手写打点。</p>
 *
 * @author rag-platform
 */
@Component
public class LlmRouter {

    private static final Logger log = LoggerFactory.getLogger(LlmRouter.class);

    private final PlatformClient platformClient;
    private final LlmTraceListener traceListener;

    /** configCode -> 同步模型实例 */
    private final Map<String, ChatModel> chatModels = new ConcurrentHashMap<>();

    /** configCode -> 流式模型实例 */
    private final Map<String, StreamingChatModel> streamingModels = new ConcurrentHashMap<>();

    /** 当前生效的配置，按 priority 升序 */
    private volatile List<ModelConfigDTO> configs = new ArrayList<>();

    public LlmRouter(PlatformClient platformClient, LlmTraceListener traceListener) {
        this.platformClient = platformClient;
        this.traceListener = traceListener;
    }

    @PostConstruct
    public void init() {
        refresh();
    }

    /**
     * 定时刷新模型配置。用定时拉取而非每次问答远程调用，
     * 避免把「模型配置查询」变成高频调用的性能瓶颈。
     */
    @Scheduled(fixedDelayString = "${rag.chat.model-refresh-ms:300000}", initialDelay = 300000)
    public void scheduleRefresh() {
        try {
            refresh();
        } catch (Exception ex) {
            log.error("刷新模型配置失败，沿用旧配置", ex);
        }
    }

    public synchronized void refresh() {
        R<List<ModelConfigDTO>> result = platformClient.listModelConfigs();
        if (result == null || !result.isSuccess() || result.getData() == null) {
            log.warn("拉取模型配置为空，沿用上一次配置");
            return;
        }
        List<ModelConfigDTO> latest = new ArrayList<>(result.getData());
        latest.sort(Comparator.comparing(c -> c.priority() == null ? Integer.MAX_VALUE : c.priority()));

        chatModels.clear();
        streamingModels.clear();
        for (ModelConfigDTO config : latest) {
            try {
                chatModels.put(config.configCode(), buildChatModel(config));
                streamingModels.put(config.configCode(), buildStreamingModel(config));
            } catch (Exception ex) {
                log.error("构建模型实例失败，跳过该配置 configCode={}", config.configCode(), ex);
            }
        }
        this.configs = latest;
        log.info("模型配置已刷新，共 {} 个", latest.size());
    }

    /**
     * 按密级路由（同步）。
     *
     * @param secretLevel 本次请求涉及的最高密级
     */
    public ChatModel route(int secretLevel) {
        ModelConfigDTO config = pick(secretLevel);
        ChatModel model = chatModels.get(config.configCode());
        if (model == null) {
            throw BizException.of(ErrorCode.NO_MODEL_AVAILABLE,
                    "模型实例构建失败：" + config.configCode());
        }
        return model;
    }

    /** 按密级路由（流式） */
    public StreamingChatModel routeStreaming(int secretLevel) {
        ModelConfigDTO config = pick(secretLevel);
        StreamingChatModel model = streamingModels.get(config.configCode());
        if (model == null) {
            throw BizException.of(ErrorCode.NO_MODEL_AVAILABLE,
                    "流式模型实例构建失败：" + config.configCode());
        }
        return model;
    }

    /** 返回本次实际使用的配置编码，用于日志、Token 归因与问题定位 */
    public String routeCode(int secretLevel) {
        return pick(secretLevel).configCode();
    }

    private ModelConfigDTO pick(int secretLevel) {
        List<ModelConfigDTO> snapshot = this.configs;
        if (snapshot.isEmpty()) {
            throw BizException.of(ErrorCode.NO_MODEL_AVAILABLE, "模型配置为空，请检查配置中心");
        }
        // 候选：能处理该密级 且 实例已就绪
        List<ModelConfigDTO> candidates = snapshot.stream()
                .filter(c -> c.sensitiveLevel() != null && c.sensitiveLevel() >= secretLevel)
                .filter(c -> chatModels.containsKey(c.configCode()))
                .toList();

        if (candidates.isEmpty()) {
            throw BizException.of(ErrorCode.NO_MODEL_AVAILABLE,
                    "当前密级(" + secretLevel + ")下无可用模型配置，请检查敏感度路由规则");
        }
        return candidates.get(0);
    }

    private ChatModel buildChatModel(ModelConfigDTO config) {
        return OpenAiChatModel.builder()
                .baseUrl(config.baseUrl())
                .apiKey(config.apiKey())
                .modelName(config.modelName())
                .temperature(config.temperature() == null ? 0.2 : config.temperature())
                .maxTokens(config.maxTokens() == null ? 1024 : config.maxTokens())
                .timeout(Duration.ofSeconds(60))
                .logRequests(false)
                .logResponses(false)
                // 埋点：挂载后所有调用自动产出 GenAI span 与 token 指标
                .listeners(traceListener)
                .build();
    }

    private StreamingChatModel buildStreamingModel(ModelConfigDTO config) {
        return OpenAiStreamingChatModel.builder()
                .baseUrl(config.baseUrl())
                .apiKey(config.apiKey())
                .modelName(config.modelName())
                .temperature(config.temperature() == null ? 0.2 : config.temperature())
                .maxTokens(config.maxTokens() == null ? 1024 : config.maxTokens())
                .timeout(Duration.ofSeconds(120))
                .listeners(traceListener)
                .build();
    }
}
''')

# ============================================================================
# 7. rag-chat-service application.yml
# ============================================================================
add("rag-chat-service/src/main/resources/application.yml", r'''
server:
  port: 8085
  shutdown: graceful
  tomcat:
    threads:
      # 生成链路是长耗时调用，线程数不能按常规设太小，但也不能无脑放大
      max: 200

spring:
  application:
    name: rag-chat-service
  profiles:
    active: dev
  config:
    import:
      - optional:nacos:rag-chat-service.yaml
      - optional:nacos:rag-common.yaml
  cloud:
    nacos:
      server-addr: ${NACOS_ADDR:127.0.0.1:8848}
      username: ${NACOS_USERNAME:nacos}
      password: ${NACOS_PASSWORD:nacos}
      discovery:
        namespace: ${NACOS_NAMESPACE:rag}
        group: RAG_GROUP
      config:
        namespace: ${NACOS_NAMESPACE:rag}
        group: RAG_GROUP
        file-extension: yaml
  datasource:
    driver-class-name: com.mysql.cj.jdbc.Driver
    url: jdbc:mysql://${MYSQL_HOST:127.0.0.1}:${MYSQL_PORT:3306}/rag_chat?useUnicode=true&characterEncoding=utf8&serverTimezone=Asia/Shanghai
    username: ${MYSQL_USERNAME:rag}
    password: ${MYSQL_PASSWORD:rag123456}
  data:
    redis:
      host: ${REDIS_HOST:127.0.0.1}
      port: ${REDIS_PORT:6379}
      password: ${REDIS_PASSWORD:}
      database: 2

mybatis-plus:
  configuration:
    map-underscore-to-camel-case: true
  global-config:
    db-config:
      logic-delete-field: deleted
      logic-delete-value: 1
      logic-not-delete-value: 0

feign:
  client:
    config:
      default:
        connectTimeout: 500
        readTimeout: 10000
      # 检索超时必须严于生成，检索慢就直接降级，不要让用户干等
      rag-retrieval-service:
        connectTimeout: 500
        readTimeout: 3000
      rag-platform-service:
        connectTimeout: 300
        readTimeout: 500

rag:
  chat:
    model-refresh-ms: 300000
    guardrail-refresh-ms: 600000
  server:
    auth:
      enabled: true
      trusted-gateway-cidrs:
        - 10.10.1.0/24
      gateway-signature-enabled: false
      gateway-sign-secret: ${RAG_GATEWAY_SIGN_SECRET:}
  # ---------------------------------------------------------------------------
  # 可观测（详见 docs/05-AI可观测与运维监控方案.md）
  # 生产把 content-level 保持 METRICS_ONLY：既不落问答原文，也不影响链路回放能力
  # ---------------------------------------------------------------------------
  observability:
    enabled: true
    content-level: ${RAG_OBS_CONTENT_LEVEL:METRICS_ONLY}
    # 防呆闸：即使 content-level 被误配成 FULL_CONTENT，也不会真的上报原文
    allow-plain-text-content: false
    max-content-chars: 2000
    record-retrieved-chunks: false
    subject-hash-salt: ${RAG_SUBJECT_HASH_SALT:}
    provider-name: openai

management:
  endpoints:
    web:
      exposure:
        include: health,info,prometheus,metrics
  endpoint:
    health:
      show-details: never
  metrics:
    tags:
      application: ${spring.application.name}
  tracing:
    sampling:
      probability: ${RAG_OBS_SAMPLING:0.1}
  otlp:
    tracing:
      # 应用只认 OTel Collector（LangFuse 密钥只配在 Collector，业务服务不持有）
      endpoint: ${OTEL_EXPORTER_OTLP_TRACES_ENDPOINT:http://127.0.0.1:4318/v1/traces}
      timeout: 3s

logging:
  level:
    com.fintech.rag: INFO
    dev.langchain4j: WARN
''')

if __name__ == "__main__":
    for rel, content in FILES.items():
        target = BASE / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print("W +", rel)
    print("---- total:", len(FILES))
