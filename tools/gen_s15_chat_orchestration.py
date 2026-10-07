# -*- coding: utf-8 -*-
"""
S15 · 编排层改造：把「真实 token 用量 / 引用 / 用户消息 / 审计」接上。

改造前的问题（都是「看起来有、实际没有」）：
  1. ChatResponse.usage 恒为 zeros —— 模型真实用量只进了 Prometheus 指标，
     没进 t_token_usage 账本，「按部门算成本」无法回答；
  2. 引用只返回前端，没落 t_message_citation —— 页面刷新后无法溯源，
     「引用的是哪个文档版本」在三个月后的合规检查里说不清；
  3. 只落 assistant 消息，不落 user 消息 —— 回放时看不到用户当时问的是什么；
  4. 落库未写审计（t_audit_log）—— 金融场景「谁在何时问了什么」必须可追溯。

产出：
  1) app/service/ChatOrchestrationAppService.java（覆盖写）
  2) api/controller/ChatController.java（覆盖写，SSE done 事件回带 messageId + traceId）

幂等：覆盖写。
"""
import pathlib

ROOT = pathlib.Path(r"D:/AiWorkOut/java-ai")
CHAT = ROOT / "rag-platform/rag-chat-service/src/main/java/com/fintech/rag/chat"

written = []


def w(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    written.append(path)
    print("W +", path.relative_to(ROOT).as_posix())


# ==================================================== 1 ChatOrchestrationAppService
w(CHAT / "app/service/ChatOrchestrationAppService.java", r'''package com.fintech.rag.chat.app.service;

import com.fintech.rag.api.client.PlatformClient;
import com.fintech.rag.api.client.RetrievalClient;
import com.fintech.rag.api.dto.chat.ChatRequest;
import com.fintech.rag.api.dto.chat.ChatResponse;
import com.fintech.rag.api.dto.common.AnswerType;
import com.fintech.rag.api.dto.platform.AuditLogDTO;
import com.fintech.rag.api.dto.retrieval.RetrievalRequest;
import com.fintech.rag.api.dto.retrieval.RetrievalResponse;
import com.fintech.rag.chat.app.eval.EvalSampleContext;
import com.fintech.rag.chat.app.eval.OnlineEvalSampler;
import com.fintech.rag.chat.app.guard.AnswerGuardrail;
import com.fintech.rag.chat.app.metric.ChatPipelineMetrics;
import com.fintech.rag.chat.app.metric.StreamTimingRecorder;
import com.fintech.rag.chat.app.persist.ChatPersistenceService;
import com.fintech.rag.chat.app.prompt.PromptTemplateRegistry;
import com.fintech.rag.chat.domain.model.ChatMessage;
import com.fintech.rag.chat.infra.llm.LlmRouter;
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
import dev.langchain4j.model.output.TokenUsage;
import io.micrometer.tracing.Span;
import io.micrometer.tracing.Tracer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.function.Consumer;

/**
 * 问答编排应用服务 —— <b>生成链路的唯一编排点</b>。
 *
 * <p>链路：鉴权（拦截器已完成）→ 建会话 → 存用户消息 → 检索 → 空召回判定
 * → 组装 Prompt → 调用模型 → 护栏校验 → 落库（消息/引用/token）→ 审计 → 抽样评估。</p>
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
 * <p><b>落库顺序的刻意安排</b>：所有写库动作都在模型调用<b>之后</b>，
 * 且每个动作独立失败、互不牵连（见 {@code ChatPersistenceService}）。
 * 这是为了不出现「回答已经生成好了，却因为写库报错而返回失败」这种情况。</p>
 *
 * @author rag-platform
 */
@Service
public class ChatOrchestrationAppService {

    private static final Logger log = LoggerFactory.getLogger(ChatOrchestrationAppService.class);

    private static final String EVENT_QUERY = "QUERY";
    private static final String PATH_CHAT = "/api/ai/chat";
    private static final String PATH_CHAT_STREAM = "/api/ai/chat/stream";

    private final RetrievalClient retrievalClient;
    private final LlmRouter llmRouter;
    private final PromptTemplateRegistry promptRegistry;
    private final AnswerGuardrail guardrail;
    private final ConversationMemoryStore memoryStore;
    private final ChatPersistenceService persistence;
    private final OnlineEvalSampler evalSampler;
    private final PlatformClient platformClient;
    private final ChatPipelineMetrics metrics;
    private final ObjectProvider<Tracer> tracerProvider;
    private final ObservabilityProperties observabilityProperties;
    private final ContentSanitizer sanitizer;

    public ChatOrchestrationAppService(RetrievalClient retrievalClient,
                                       LlmRouter llmRouter,
                                       PromptTemplateRegistry promptRegistry,
                                       AnswerGuardrail guardrail,
                                       ConversationMemoryStore memoryStore,
                                       ChatPersistenceService persistence,
                                       OnlineEvalSampler evalSampler,
                                       PlatformClient platformClient,
                                       ChatPipelineMetrics metrics,
                                       ObjectProvider<Tracer> tracerProvider,
                                       ObservabilityProperties observabilityProperties,
                                       ContentSanitizer sanitizer) {
        this.retrievalClient = retrievalClient;
        this.llmRouter = llmRouter;
        this.promptRegistry = promptRegistry;
        this.guardrail = guardrail;
        this.memoryStore = memoryStore;
        this.persistence = persistence;
        this.evalSampler = evalSampler;
        this.platformClient = platformClient;
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
        String traceId = RequestContext.currentTraceId();
        Span span = startBusinessSpan(request, appSource);

        Long conversationId = persistence.ensureConversation(
                request.conversationId(), subjectType, subjectId, request.question(), request.kbIds());
        Long userMessageId = persistence.saveUserMessage(conversationId, request.question());

        try {
            RetrievalResponse retrieval = retrieve(request, subjectType, subjectId, roleCodes, deptId);

            // 空召回：不调用大模型，直接兜底
            if (retrieval == null || retrieval.emptyHit() || retrieval.chunks().isEmpty()) {
                int cost = (int) (System.currentTimeMillis() - start);
                String answer = promptRegistry.noHitAnswer();
                Long messageId = persistAssistant(conversationId, userMessageId, answer,
                        AnswerType.NO_HIT.name(), null, traceId, null, null, cost, null,
                        List.of(), retrieval);
                tagOutcome(span, RagOutcome.NO_HIT, 0);
                metrics.recordAnswer(RagOutcome.NO_HIT, appSource, null);
                audit(traceId, subjectType, subjectId, PATH_CHAT, 1, null, cost,
                        AnswerType.NO_HIT, null, 0, request.kbIds());
                sampleEval(traceId, messageId, conversationId, AnswerType.NO_HIT.name(), null, 0,
                        0, rawChunkCountOf(retrieval), topScoreOf(retrieval), null, cost);
                return new ChatResponse(
                        messageId == null ? null : String.valueOf(messageId),
                        conversationId == null ? request.conversationId() : String.valueOf(conversationId),
                        AnswerType.NO_HIT, answer, List.of(), ChatResponse.Guardrail.pass(),
                        null, ChatResponse.Usage.zero(), 0, cost, promptRegistry.disclaimer());
            }

            int secretLevel = resolveSecretLevel(request);
            String modelCode = llmRouter.routeCode(secretLevel);
            String systemPrompt = promptRegistry.systemPrompt();
            String userPrompt = promptRegistry.userPrompt(request.question(), retrieval.chunks());
            tagContent(span, GenAiSemconv.ATTR_SYSTEM_INSTRUCTIONS, systemPrompt);
            tagContent(span, GenAiSemconv.ATTR_INPUT_MESSAGES, userPrompt);
            ChatModel model = llmRouter.route(secretLevel);

            // ---- 关键：从 LangChain4j 的响应里取「真实」token 用量 ----
            // 埋点监听器只把用量送进了 Prometheus 指标（观测量），
            // 而 t_token_usage 是计费账本，必须在此处显式取出并落库。
            dev.langchain4j.model.chat.response.ChatResponse lcResponse =
                    model.chat(toLcMessages(request, systemPrompt, userPrompt));
            AiMessage aiMessage = lcResponse == null ? null : lcResponse.aiMessage();
            String rawAnswer = aiMessage == null ? "" : aiMessage.text();
            TokenUsage usage = lcResponse == null ? null : lcResponse.tokenUsage();
            Integer inputTokens = usage == null ? null : usage.inputTokenCount();
            Integer outputTokens = usage == null ? null : usage.outputTokenCount();
            String modelName = lcResponse == null || lcResponse.metadata() == null
                    ? null : lcResponse.metadata().modelName();

            AnswerGuardrail.GuardrailResult guardResult = guardrail.check(rawAnswer, retrieval.chunks().size());
            int cost = (int) (System.currentTimeMillis() - start);
            String answerType = guardResult.toGuardrail() != null && guardResult.toGuardrail().hit()
                    ? AnswerType.GUARDRAIL_BLOCKED.name() : AnswerType.ANSWERED.name();

            Long messageId = persistAssistant(conversationId, userMessageId, guardResult.answer(),
                    answerType, modelCode, traceId, guardrailHitOf(guardResult), null, cost,
                    outputTokens, retrieval.chunks(), retrieval);
            persistence.saveTokenUsage(traceId, subjectType, subjectId, conversationId, messageId,
                    modelCode, modelName, inputTokens, outputTokens, cost);

            tagSuccess(span, retrieval.chunks().size(), guardResult, modelCode);
            RagOutcome outcome = AnswerType.GUARDRAIL_BLOCKED.name().equals(answerType)
                    ? RagOutcome.GUARDRAIL_BLOCKED : RagOutcome.ANSWERED;
            metrics.recordAnswer(outcome, appSource, modelCode);

            audit(traceId, subjectType, subjectId, PATH_CHAT, 1, null, cost,
                    AnswerType.valueOf(answerType), modelCode, retrieval.chunks().size(), request.kbIds());
            sampleEval(traceId, messageId, conversationId, answerType, modelCode,
                    retrieval.chunks().size(), retrieval.chunks().size(),
                    rawChunkCountOf(retrieval), topScoreOf(retrieval), null, cost);

            return new ChatResponse(
                    messageId == null ? null : String.valueOf(messageId),
                    conversationId == null ? request.conversationId() : String.valueOf(conversationId),
                    AnswerType.valueOf(answerType),
                    guardResult.answer(),
                    buildCitations(retrieval),
                    guardResult.toGuardrail(),
                    modelCode,
                    toUsage(usage),
                    0,
                    cost,
                    promptRegistry.disclaimer());
        } catch (RuntimeException ex) {
            tagFailure(span, ex);
            metrics.recordAnswer(RagOutcome.ERROR, appSource, null);
            audit(traceId, subjectType, subjectId, PATH_CHAT, 0, ex, -1,
                    AnswerType.ERROR, null, 0, request.kbIds());
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
     * @param onFinish 完成回调（携带完整答案、引用、消息 ID 与 traceId）
     * @param onError  异常回调
     */
    public void stream(ChatRequest request, String subjectType, String subjectId,
                       String roleCodes, Long deptId,
                       Consumer<String> onDelta,
                       Consumer<StreamResult> onFinish,
                       Consumer<Throwable> onError) {
        long startNanos = System.nanoTime();
        long start = System.currentTimeMillis();
        String appSource = resolveAppSource();
        String traceId = RequestContext.currentTraceId();
        Span span = startBusinessSpan(request, appSource);

        Long conversationId = persistence.ensureConversation(
                request.conversationId(), subjectType, subjectId, request.question(), request.kbIds());
        Long userMessageId = persistence.saveUserMessage(conversationId, request.question());

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
            int cost = (int) (System.currentTimeMillis() - start);
            String noHit = promptRegistry.noHitAnswer();
            onDelta.accept(noHit);
            Long messageId = persistAssistant(conversationId, userMessageId, noHit,
                    AnswerType.NO_HIT.name(), null, traceId, null, null, cost, null,
                    List.of(), retrieval);
            tagOutcome(span, RagOutcome.NO_HIT, 0);
            end(span);
            metrics.recordAnswer(RagOutcome.NO_HIT, appSource, null);
            audit(traceId, subjectType, subjectId, PATH_CHAT_STREAM, 1, null, cost,
                    AnswerType.NO_HIT, null, 0, request.kbIds());
            sampleEval(traceId, messageId, conversationId, AnswerType.NO_HIT.name(), null,
                    0, 0, rawChunkCountOf(retrieval), topScoreOf(retrieval), null, cost);
            onFinish.accept(new StreamResult(noHit, List.of(),
                    messageId == null ? null : String.valueOf(messageId), traceId));
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
                        String answerType = guardResult.toGuardrail() != null
                                && guardResult.toGuardrail().hit()
                                ? AnswerType.GUARDRAIL_BLOCKED.name() : AnswerType.ANSWERED.name();

                        // 流式的 token 用量同样从响应里取，与埋点指标各走各的通道
                        TokenUsage usage = response == null ? null : response.tokenUsage();
                        Integer inputTokens = usage == null ? null : usage.inputTokenCount();
                        Integer outputTokens = usage == null ? null : usage.outputTokenCount();
                        String modelName = response == null || response.metadata() == null
                                ? null : response.metadata().modelName();

                        Long messageId = persistAssistant(conversationId, userMessageId,
                                guardResult.answer(), answerType, modelCode, traceId,
                                guardrailHitOf(guardResult), ttfbMs, cost, outputTokens,
                                retrieval.chunks(), retrieval);
                        persistence.saveTokenUsage(traceId, subjectType, subjectId, conversationId,
                                messageId, modelCode, modelName, inputTokens, outputTokens, cost);

                        tagSuccess(span, citations.size(), guardResult, modelCode);
                        tagSpan(span, "rag.stream.chunk.count", timing.chunkCount());
                        end(span);

                        RagOutcome outcome = AnswerType.GUARDRAIL_BLOCKED.name().equals(answerType)
                                ? RagOutcome.GUARDRAIL_BLOCKED : RagOutcome.ANSWERED;
                        metrics.recordAnswer(outcome, appSource, modelCode);
                        audit(traceId, subjectType, subjectId, PATH_CHAT_STREAM, 1, null, cost,
                                AnswerType.valueOf(answerType), modelCode, citations.size(), request.kbIds());
                        sampleEval(traceId, messageId, conversationId, answerType, modelCode,
                                citations.size(), retrieval.chunks().size(),
                                rawChunkCountOf(retrieval), topScoreOf(retrieval), ttfbMs, cost);

                        onFinish.accept(new StreamResult(guardResult.answer(), citations,
                                messageId == null ? null : String.valueOf(messageId), traceId));
                    }

                    @Override
                    public void onError(Throwable error) {
                        log.error("流式生成失败 conversationId={}", request.conversationId(), error);
                        tagFailure(span, error);
                        end(span);
                        metrics.recordAnswer(RagOutcome.ERROR, appSource, modelCode);
                        audit(traceId, subjectType, subjectId, PATH_CHAT_STREAM, 0, error, -1,
                                AnswerType.ERROR, modelCode, 0, request.kbIds());
                        onError.accept(error);
                    }
                });
    }

    /** 流式完成结果：把 messageId 与 traceId 一并回给前端，用户侧才能拿到「回放钥匙」 */
    public record StreamResult(String answer,
                               List<ChatResponse.Citation> citations,
                               String messageId,
                               String traceId) {
    }

    // ------------------------------------------------------------------ 落库
    /**
     * 落库一次回答的全部产物。
     *
     * @return 助手消息 ID
     */
    private Long persistAssistant(Long conversationId, Long parentId, String answer, String answerType,
                                  String modelCode, String traceId, String guardrailHit,
                                  Integer ttfbMs, int costMs, Integer contentTokens,
                                  List<RetrievalResponse.Chunk> chunks, RetrievalResponse retrieval) {
        Long messageId = persistence.saveAssistantMessage(conversationId, parentId, answer, answerType,
                modelCode, traceId, PromptTemplateRegistry.VERSION, guardrailHit,
                ttfbMs, costMs, contentTokens);
        persistence.saveCitations(messageId, chunks);
        // 一次问答成对产生 user + assistant 两条消息，故消息数 +2
        int tokens = contentTokens == null ? 0 : contentTokens;
        persistence.accumulateConversation(conversationId, 2, tokens);
        return messageId;
    }

    // ------------------------------------------------------------------ 抽样评估
    private void sampleEval(String traceId, Long messageId, Long conversationId, String answerType,
                            String modelCode, int citationCount, int chunkCount, int rawChunkCount,
                            Double topScore, Integer ttfbMs, int costMs) {
        evalSampler.trySample(new EvalSampleContext(traceId, messageId, conversationId,
                answerType, modelCode, PromptTemplateRegistry.VERSION,
                citationCount, chunkCount, rawChunkCount, topScore, ttfbMs, costMs));
    }

    // ------------------------------------------------------------------ 审计
    /**
     * 上报审计日志（fail-open，绝不阻塞回答）。
     *
     * <p><b>detailJson 只写结构化摘要，不写问答原文</b>：审计的目的是「谁在何时问了什么」，
     * 「问了什么」通过 messageId 关联到 t_message 即可取到（受权限与脱敏控制），
     * 没必要在审计表里再复制一份正文 —— 那等于把最敏感的数据多存一份、多一处泄漏面。</p>
     */
    private void audit(String traceId, String subjectType, String subjectId, String resource,
                       int result, Throwable error, int costMs, AnswerType answerType,
                       String modelCode, int citationCount, List<Long> kbIds) {
        try {
            RequestContext.Snapshot snapshot = RequestContext.get();
            String detail = "{\"answerType\":\"" + answerType.name()
                    + "\",\"citations\":" + citationCount
                    + ",\"modelCode\":" + (modelCode == null ? "null" : "\"" + modelCode + "\"")
                    + ",\"promptVersion\":\"" + PromptTemplateRegistry.VERSION + "\"}";
            AuditLogDTO dto = new AuditLogDTO(
                    traceId,
                    EVENT_QUERY,
                    snapshot == null || snapshot.source() == null ? null : snapshot.source().name(),
                    subjectType,
                    subjectId,
                    null,
                    snapshot == null ? null : snapshot.clientIp(),
                    resource,
                    kbIds,
                    null,
                    detail,
                    result,
                    error == null ? null : ErrorCode.LLM_CALL_FAILED.getCode(),
                    costMs < 0 ? null : costMs,
                    System.currentTimeMillis());
            R<Void> ignored = platformClient.saveAuditLogs(List.of(dto));
            if (ignored == null || !ignored.isSuccess()) {
                log.warn("审计上报未成功 traceId={}（不影响主链路）", traceId);
            }
        } catch (Exception ex) {
            // 审计上报失败必须 fail-open：主链路已经完成，不能因为审计服务抖动就报错
            log.warn("审计上报异常 traceId={}（已降级）", traceId, ex);
        }
    }

    // ------------------------------------------------------------------ 检索
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
        if (retrieval == null || retrieval.chunks() == null) {
            return citations;
        }
        int seq = 1;
        for (RetrievalResponse.Chunk chunk : retrieval.chunks()) {
            citations.add(new ChatResponse.Citation(
                    seq++, chunk.kbId(), chunk.docId(), chunk.docName(), chunk.versionNo(),
                    chunk.pageNo(), chunk.chunkIndex(), chunk.score(), chunk.content()));
        }
        return citations;
    }

    private ChatResponse.Usage toUsage(TokenUsage usage) {
        if (usage == null) {
            return ChatResponse.Usage.zero();
        }
        int in = usage.inputTokenCount() == null ? 0 : usage.inputTokenCount();
        int out = usage.outputTokenCount() == null ? 0 : usage.outputTokenCount();
        int total = usage.totalTokenCount() == null ? in + out : usage.totalTokenCount();
        return new ChatResponse.Usage(in, out, total);
    }

    private int rawChunkCountOf(RetrievalResponse retrieval) {
        return retrieval == null || retrieval.chunks() == null ? 0 : retrieval.chunks().size();
    }

    private Double topScoreOf(RetrievalResponse retrieval) {
        if (retrieval == null || retrieval.chunks() == null || retrieval.chunks().isEmpty()) {
            return null;
        }
        return retrieval.chunks().get(0).score();
    }

    private String guardrailHitOf(AnswerGuardrail.GuardrailResult guardResult) {
        if (guardResult == null || guardResult.toGuardrail() == null
                || !guardResult.toGuardrail().hit()
                || guardResult.toGuardrail().types() == null) {
            return null;
        }
        String joined = String.join(",", guardResult.toGuardrail().types());
        return joined.length() <= 128 ? joined : joined.substring(0, 128);
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

# ==================================================== 2 ChatController
w(CHAT / "api/controller/ChatController.java", r'''package com.fintech.rag.chat.api.controller;

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
import java.util.LinkedHashMap;
import java.util.Map;
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
 * <p><b>SSE done 事件携带 messageId 与 traceId</b>：流式场景下前端拿不到
 * {@code R.traceId}（响应是事件流而非统一返回体），若不在 done 里回带，
 * 用户点踩时就无法定位到具体那条回答 —— 回放链路会在最后一米断掉。</p>
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
     *   event: done       数据为 {messageId, conversationId, traceId}，前端凭 traceId 可回放本次回答
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
                        result -> {
                            sendQuietly(emitter, "citations", result.citations());
                            Map<String, Object> done = new LinkedHashMap<>();
                            done.put("messageId", result.messageId() == null ? "" : result.messageId());
                            done.put("conversationId", request.conversationId() == null ? "" : request.conversationId());
                            done.put("traceId", result.traceId() == null ? "" : result.traceId());
                            sendQuietly(emitter, "done", done);
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

print("---- total:", len(written))
