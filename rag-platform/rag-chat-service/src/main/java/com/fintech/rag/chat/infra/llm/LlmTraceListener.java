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
