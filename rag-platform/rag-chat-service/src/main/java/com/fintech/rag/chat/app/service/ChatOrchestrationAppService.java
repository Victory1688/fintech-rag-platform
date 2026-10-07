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
            tagOutcome(span, RagOutcome.ABSTAINED, 0);
            end(span);
            metrics.recordAnswer(RagOutcome.ABSTAINED, appSource, null);
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
        tagOutcome(span, RagOutcome.ABSTAINED, 0);
        metrics.recordAnswer(RagOutcome.ABSTAINED, appSource, null);
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
