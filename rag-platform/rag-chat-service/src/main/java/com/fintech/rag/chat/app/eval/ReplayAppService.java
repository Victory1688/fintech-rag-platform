package com.fintech.rag.chat.app.eval;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.fintech.rag.api.client.PlatformClient;
import com.fintech.rag.api.client.RetrievalClient;
import com.fintech.rag.api.dto.platform.AuditLogDTO;
import com.fintech.rag.api.dto.replay.ReplayView;
import com.fintech.rag.api.dto.replay.RetrievalTraceView;
import com.fintech.rag.chat.domain.model.ChatMessage;
import com.fintech.rag.chat.domain.model.Conversation;
import com.fintech.rag.chat.domain.model.LlmEvalScore;
import com.fintech.rag.chat.domain.model.MessageCitation;
import com.fintech.rag.chat.domain.model.TokenUsageRecord;
import com.fintech.rag.chat.infra.persistence.mapper.ChatMessageMapper;
import com.fintech.rag.chat.infra.persistence.mapper.ConversationMapper;
import com.fintech.rag.chat.infra.persistence.mapper.LlmEvalScoreMapper;
import com.fintech.rag.chat.infra.persistence.mapper.MessageCitationMapper;
import com.fintech.rag.chat.infra.persistence.mapper.TokenUsageRecordMapper;
import com.fintech.rag.common.context.RequestContext;
import com.fintech.rag.common.context.RequestSource;
import com.fintech.rag.common.core.R;
import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import com.fintech.rag.common.observability.ContentSanitizer;
import com.fintech.rag.common.util.TraceIds;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;

/**
 * 回放应用服务 —— <b>把一条 traceId 还原成一次可读的回答过程</b>。
 *
 * <p><b>四道闸（缺一不可）</b>：</p>
 * <ol>
 *   <li><b>准入闸</b>：只允许内网调用。回放是运维诊断能力，终端用户既能看就必然看到别人的问答。
 *       网关侧不暴露 {@code /api/ai/replay/**}，服务侧再判一次
 *       {@code X-Request-Source != DMZ_WEB} —— 纵深防御，不赌网关配置永远不会改错；</li>
 *   <li><b>格式闸</b>：traceId 必须是合法 W3C 32 位小写 hex。不做校验时，
 *       用户可以传 {@code %} 或超长串去打库，既是注入面也是性能面；</li>
 *   <li><b>内容闸</b>：正文是否返回完全由内容采集档位决定，回放不额外开后门；</li>
 *   <li><b>审计闸</b>：每次回放都写审计（谁、在什么时候、查了哪条 trace）。
 *       <b>查看别人的问答记录本身就是一次敏感操作</b>，必须留痕 ——
 *       否则「运维可以静默浏览任何用户的问答」会成为安全评审的一票否决项。</li>
 * </ol>
 *
 * <p><b>降级哲学</b>：检索段拿不到时不失败、不隐藏，而是在 {@code degraded} 里写明原因。
 * 回放工具最需要可用的时机，恰恰是依赖出问题的时候。</p>
 *
 * @author rag-platform
 */
@Service
public class ReplayAppService {

    private static final Logger log = LoggerFactory.getLogger(ReplayAppService.class);

    private static final String EVENT_QUERY = "QUERY";
    private static final String RESOURCE_REPLAY = "replay";

    private final ChatMessageMapper messageMapper;
    private final ConversationMapper conversationMapper;
    private final MessageCitationMapper citationMapper;
    private final TokenUsageRecordMapper tokenUsageMapper;
    private final LlmEvalScoreMapper evalScoreMapper;
    private final RetrievalClient retrievalClient;
    private final PlatformClient platformClient;
    private final ReplayProperties properties;
    private final ContentSanitizer sanitizer;

    public ReplayAppService(ChatMessageMapper messageMapper,
                            ConversationMapper conversationMapper,
                            MessageCitationMapper citationMapper,
                            TokenUsageRecordMapper tokenUsageMapper,
                            LlmEvalScoreMapper evalScoreMapper,
                            RetrievalClient retrievalClient,
                            PlatformClient platformClient,
                            ReplayProperties properties,
                            ContentSanitizer sanitizer) {
        this.messageMapper = messageMapper;
        this.conversationMapper = conversationMapper;
        this.citationMapper = citationMapper;
        this.tokenUsageMapper = tokenUsageMapper;
        this.evalScoreMapper = evalScoreMapper;
        this.retrievalClient = retrievalClient;
        this.platformClient = platformClient;
        this.properties = properties;
        this.sanitizer = sanitizer;
    }

    /**
     * 回放一次回答。
     *
     * @param traceId      链路 ID
     * @param withContent  是否请求正文（仍受内容档位最终裁决）
     */
    public ReplayView replay(String traceId, boolean withContent) {
        if (!properties.isEnabled()) {
            throw BizException.of(ErrorCode.DEPENDENCY_UNAVAILABLE, "回放能力未启用");
        }
        // ---- 闸 1：准入 ----
        if (RequestContext.currentSource() == RequestSource.DMZ_WEB) {
            log.warn("[回放拒绝] 来自外网入口的回放请求 ip 已记录 traceId={}", traceId);
            throw BizException.of(ErrorCode.KB_NO_PERMISSION, "回放接口仅限内网调用");
        }
        // ---- 闸 2：格式 ----
        if (!TraceIds.isValidTraceId(traceId)) {
            throw BizException.of(ErrorCode.PARAM_INVALID,
                    "traceId 必须是 32 位小写十六进制（W3C trace-id）");
        }
        // ---- 闸 4：审计（在真正查数据之前写，即使查询失败也留下「有人查过」的事实） ----
        audit(traceId);

        List<String> degraded = new ArrayList<>();
        boolean withRealContent = withContent && contentAllowed(degraded);

        // ---- 本地库 ----
        List<ChatMessage> messages = messageMapper.selectList(Wrappers.<ChatMessage>lambdaQuery()
                .eq(ChatMessage::getTraceId, traceId)
                .orderByAsc(ChatMessage::getCreateTime));

        Long conversationId = messages.isEmpty() ? null : messages.get(0).getConversationId();
        Conversation conversation = conversationId == null ? null : conversationMapper.selectById(conversationId);

        List<MessageCitation> citations = messageIdsOf(messages).isEmpty() ? List.of()
                : citationMapper.selectList(Wrappers.<MessageCitation>lambdaQuery()
                        .in(MessageCitation::getMessageId, messageIdsOf(messages))
                        .orderByAsc(MessageCitation::getSeq));

        List<TokenUsageRecord> tokens = tokenUsageMapper.selectList(Wrappers.<TokenUsageRecord>lambdaQuery()
                .eq(TokenUsageRecord::getTraceId, traceId)
                .orderByAsc(TokenUsageRecord::getCreateTime));

        List<LlmEvalScore> scores = evalScoreMapper.selectList(Wrappers.<LlmEvalScore>lambdaQuery()
                .eq(LlmEvalScore::getTraceId, traceId)
                .orderByAsc(LlmEvalScore::getCreateTime));

        // ---- 检索段（跨服务，fail-open） ----
        List<RetrievalTraceView> retrievalLogs = fetchRetrievalLogs(traceId, degraded);

        boolean found = !messages.isEmpty() || !retrievalLogs.isEmpty() || !scores.isEmpty() || !tokens.isEmpty();
        if (!found) {
            degraded.add("未找到该 traceId 的本地数据：可能 traceId 有误，或该链路早于本功能上线");
        }

        return new ReplayView(
                traceId,
                found,
                degraded,
                toConversationBrief(conversation),
                toMessages(messages, withRealContent),
                toCitations(citations, withRealContent),
                toTokens(tokens),
                toEvals(scores),
                retrievalLogs,
                buildTimeline(conversation, messages, retrievalLogs, scores),
                buildDeepLinks(traceId));
    }

    // ------------------------------------------------------------------ 闸 3：内容
    /**
     * 内容是否可见 —— <b>最终裁决权在内容采集档位，不在本方法</b>。
     *
     * <p>这里只做一次「档位是否允许文本」的探测：用空字符串走一遍
     * {@link ContentSanitizer#forReporting} 的档位分支，不允许则返回 false。
     * 真正的脱敏与截断仍由 {@code forReporting} 在拼接每个字段时执行，
     * 避免「判断用一套规则、脱敏用另一套」的经典漏洞。</p>
     */
    private boolean contentAllowed(List<String> degraded) {
        String probe = sanitizer.forReporting("probe");
        if (probe != null) {
            return true;
        }
        degraded.add("正文未返回：当前内容采集档位为 METRICS_ONLY（如需查看正文，"
                + "请在内网环境把 rag.observability.content-level 调整为 REDACTED_CONTENT）");
        return false;
    }

    private String contentOrOmit(String text, boolean allowed) {
        if (!allowed || text == null) {
            return null;
        }
        return sanitizer.forReporting(text);
    }

    // ------------------------------------------------------------------ 装配
    private ReplayView.ConversationBrief toConversationBrief(Conversation conversation) {
        if (conversation == null) {
            return null;
        }
        return new ReplayView.ConversationBrief(
                conversation.getId(),
                conversation.getConversationNo(),
                conversation.getTitle(),
                conversation.getSubjectType(),
                // 掩码而非明文：可人工核对，又不会形成一份可直接落盘的账号清单。
                // 刻意不用 sanitizer.mask —— 它匹配的是手机号/身份证等长数字模式，
                // 对 5~6 位的 userId 不会生效，会造成「以为脱敏了其实没脱」的假安全。
                maskIdentifier(conversation.getSubjectId()),
                conversation.getStatus(),
                conversation.getCreateTime());
    }

    private List<ReplayView.MessageItem> toMessages(List<ChatMessage> messages, boolean withContent) {
        List<ReplayView.MessageItem> items = new ArrayList<>();
        for (ChatMessage message : messages) {
            String content = contentOrOmit(message.getContent(), withContent);
            items.add(new ReplayView.MessageItem(
                    message.getId() == null ? null : String.valueOf(message.getId()),
                    message.getRole(),
                    message.getAnswerType(),
                    content,
                    content == null,
                    message.getModelCode(),
                    message.getPromptVersion(),
                    message.getGuardrailHit(),
                    message.getTtfbMs(),
                    message.getCostMs(),
                    message.getCreateTime()));
        }
        return items;
    }

    private List<ReplayView.CitationItem> toCitations(List<MessageCitation> citations, boolean withContent) {
        List<ReplayView.CitationItem> items = new ArrayList<>();
        for (MessageCitation citation : citations) {
            boolean omitted = !withContent || citation.getContent() == null;
            items.add(new ReplayView.CitationItem(
                    citation.getSeq() == null ? 0 : citation.getSeq(),
                    citation.getKbId(),
                    citation.getDocId(),
                    citation.getDocName(),
                    citation.getVersionNo(),
                    citation.getPageNo(),
                    citation.getChunkIndex(),
                    citation.getScore(),
                    omitted,
                    // 指纹用于「两次回答是否引用了同一段」的比对，不泄漏正文
                    omitted ? sanitizer.fingerprint(citation.getContent()) : null));
        }
        return items;
    }

    private List<ReplayView.TokenItem> toTokens(List<TokenUsageRecord> tokens) {
        List<ReplayView.TokenItem> items = new ArrayList<>();
        for (TokenUsageRecord token : tokens) {
            items.add(new ReplayView.TokenItem(token.getModelCode(), token.getModelName(),
                    token.getInputTokens(), token.getOutputTokens(), token.getTotalTokens(),
                    token.getCostMs(), token.getBizDate()));
        }
        return items;
    }

    private List<ReplayView.EvalItem> toEvals(List<LlmEvalScore> scores) {
        List<ReplayView.EvalItem> items = new ArrayList<>();
        for (LlmEvalScore score : scores) {
            items.add(new ReplayView.EvalItem(score.getMetricCode(), score.getScore(),
                    score.getScoreScale(), score.getPassed(), score.getThreshold(),
                    score.getEvalSource(), score.getJudgeModel(), score.getReason(),
                    score.getCreateTime()));
        }
        return items;
    }

    // ------------------------------------------------------------------ 时间线
    /**
     * 构造时间线 —— 回放视图里<b>最被需要的一段</b>。
     *
     * <p>它不是简单的日志罗列，而是按「一次回答的因果顺序」重排：
     * 会话 → 提问 → 检索（含召回数/最高分/缓存命中）→ 生成（含模型/首字/总耗时）→ 评估。
     * 非工程角色看这一段就能回答「这次为什么答得不好」。</p>
     */
    private List<ReplayView.TimelineItem> buildTimeline(Conversation conversation,
                                                        List<ChatMessage> messages,
                                                        List<RetrievalTraceView> retrievalLogs,
                                                        List<LlmEvalScore> scores) {
        List<ReplayView.TimelineItem> timeline = new ArrayList<>();

        if (conversation != null && conversation.getCreateTime() != null) {
            timeline.add(new ReplayView.TimelineItem(conversation.getCreateTime().toString(),
                    "SESSION", "会话创建：" + safe(conversation.getTitle())));
        }
        for (ChatMessage message : messages) {
            String at = message.getCreateTime() == null ? null : message.getCreateTime().toString();
            if ("USER".equals(message.getRole())) {
                timeline.add(new ReplayView.TimelineItem(at, "QUESTION", "用户提问（正文见消息列表）"));
            } else if ("ASSISTANT".equals(message.getRole())) {
                timeline.add(new ReplayView.TimelineItem(at, "GENERATE",
                        "生成完成：answerType=" + safe(message.getAnswerType())
                                + " model=" + safe(message.getModelCode())
                                + " 首字=" + (message.getTtfbMs() == null ? "-" : message.getTtfbMs() + "ms")
                                + " 总耗时=" + (message.getCostMs() == null ? "-" : message.getCostMs() + "ms")
                                + " 护栏=" + safe(message.getGuardrailHit())));
            }
        }
        for (RetrievalTraceView retrieval : retrievalLogs) {
            String at = retrieval.createTime() == null ? null : retrieval.createTime().toString();
            String verdict = retrieval.emptyHit() ? "空召回（未调用大模型）" : "召回成功";
            timeline.add(new ReplayView.TimelineItem(at, "RETRIEVAL",
                    verdict + "：chunks=" + retrieval.chunkCount()
                            + " topScore=" + retrieval.topScore()
                            + " cacheHit=" + retrieval.cacheHit()
                            + " ragflow=" + retrieval.ragflowCostMs() + "ms"
                            + " 范围=" + safe(retrieval.kbIds())));
        }
        for (LlmEvalScore score : scores) {
            String at = score.getCreateTime() == null ? null : score.getCreateTime().toString();
            timeline.add(new ReplayView.TimelineItem(at, "EVALUATE",
                    "评估：" + safe(score.getMetricCode())
                            + "=" + (score.getScore() == null ? "-" : score.getScore().toPlainString())
                            + " 阈值=" + (score.getThreshold() == null ? "-" : score.getThreshold().toPlainString())
                            + " 结论=" + (Integer.valueOf(1).equals(score.getPassed()) ? "通过" : "未通过")
                            + " 来源=" + safe(score.getEvalSource())));
        }
        return timeline;
    }

    // ------------------------------------------------------------------ 深链
    private ReplayView.DeepLinks buildDeepLinks(String traceId) {
        String apm = render(properties.getApmUrlTemplate(), traceId);
        String langfuse = render(properties.getLangfuseUrlTemplate(), traceId);
        String retrievalLog = render(properties.getRetrievalLogUrlTemplate(), traceId);
        if (apm == null && langfuse == null && retrievalLog == null) {
            return null;
        }
        return new ReplayView.DeepLinks(apm, langfuse, retrievalLog);
    }

    /** 模板渲染：未配置则返回 null（前端不展示入口，而不是给一个必然 404 的链接） */
    private String render(String template, String traceId) {
        if (template == null || template.isBlank()) {
            return null;
        }
        return template.replace("{traceId}", traceId);
    }

    // ------------------------------------------------------------------ 跨服务
    private List<RetrievalTraceView> fetchRetrievalLogs(String traceId, List<String> degraded) {
        try {
            R<List<RetrievalTraceView>> result = retrievalClient.findLogsByTrace(traceId);
            if (result == null || !result.isSuccess() || result.getData() == null) {
                degraded.add("检索段获取失败（retrieval-service 返回异常），本地数据仍可查看");
                return List.of();
            }
            return result.getData();
        } catch (Exception ex) {
            log.warn("回放拉取检索段失败 traceId={}（已降级）", traceId, ex);
            degraded.add("检索段获取失败（" + ex.getClass().getSimpleName()
                    + "），本地数据仍可查看 —— 诊断工具在依赖故障时更需要可用");
            return List.of();
        }
    }

    // ------------------------------------------------------------------ 审计
    private void audit(String traceId) {
        try {
            RequestContext.Snapshot snapshot = RequestContext.get();
            AuditLogDTO dto = new AuditLogDTO(
                    traceId,
                    EVENT_QUERY,
                    snapshot == null || snapshot.source() == null ? null : snapshot.source().name(),
                    snapshot == null ? null : snapshot.subjectType(),
                    snapshot == null ? null : snapshot.subjectId(),
                    null,
                    snapshot == null ? null : snapshot.clientIp(),
                    RESOURCE_REPLAY,
                    null,
                    null,
                    "{\"action\":\"REPLAY\",\"target\":\"" + traceId + "\"}",
                    1,
                    null,
                    null,
                    System.currentTimeMillis());
            platformClient.saveAuditLogs(List.of(dto));
        } catch (Exception ex) {
            // 审计失败不阻断回放，但必须留下本地痕迹（否则敏感操作会不可追溯）
            log.error("[回放审计失败] traceId={} 操作主体={} —— 请检查 platform 服务",
                    traceId, RequestContext.currentSubjectId(), ex);
        }
    }

    // ------------------------------------------------------------------ 工具
    private List<Long> messageIdsOf(List<ChatMessage> messages) {
        List<Long> ids = new ArrayList<>();
        for (ChatMessage message : messages) {
            if (message.getId() != null) {
                ids.add(message.getId());
            }
        }
        return ids;
    }

    private String safe(String value) {
        return value == null || value.isBlank() ? "-" : value;
    }

    /**
     * 主体标识部分掩码：保留前 2 后 2，中间统一用 * 替换。
     *
     * <p>与 {@code ContentSanitizer.mask} 的分工：后者面向「长数字 PII 模式」
     * （手机号 / 身份证 / 银行卡），对短账号不生效；本方法面向「任意长度的账号标识」，
     * 保证任何情况下都不出现完整账号。</p>
     */
    private String maskIdentifier(String identifier) {
        if (identifier == null || identifier.isBlank()) {
            return identifier;
        }
        if (identifier.length() <= 4) {
            return "****";
        }
        return identifier.substring(0, 2)
                + "*".repeat(identifier.length() - 4)
                + identifier.substring(identifier.length() - 2);
    }

}
