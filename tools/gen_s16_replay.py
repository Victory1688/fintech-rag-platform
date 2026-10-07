# -*- coding: utf-8 -*-
"""
S16 · 按 traceId 一键回放（chat 侧 + 契约）。

为什么需要它：可观测平台（APM / LangFuse）能看链路，但有三件事它做不了 ——
  1) Trace 有 TTL，三个月后合规检查要看「那天那条回答依据了什么」，平台里早没了；
  2) 平台里是技术视图（span/属性），运营看不懂，也不该让他们去学 span；
  3) 平台不持有业务语义（消息、引用、评分），跨不到业务侧。

回放视图做的就是把「一条 traceId」翻译成「人话的时间线」：
  用户问了什么 → 检索到几段、最高分多少 → 用了哪个模型、首字多久 →
  回答里引用了哪些文档的哪个版本 → 系统给它打了多少分。

产出：
  1) rag-api/dto/replay/ReplayView.java      聚合视图契约
  2) chat/app/eval/ReplayProperties.java     深链模板与准入开关
  3) chat/app/eval/ReplayAppService.java     聚合逻辑（含准入与内容档位控制）
  4) chat/api/controller/ReplayController.java

幂等：覆盖写。
"""
import pathlib
import re

ROOT = pathlib.Path(r"D:/AiWorkOut/java-ai")
API = ROOT / "rag-platform/rag-api/src/main/java/com/fintech/rag/api"
CHAT = ROOT / "rag-platform/rag-chat-service/src/main/java/com/fintech/rag/chat"

written = []


def w(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    written.append(path)
    print("W +", path.relative_to(ROOT).as_posix())


# ============================================================ ReplayView
w(API / "dto/replay/ReplayView.java", r'''package com.fintech.rag.api.dto.replay;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;

/**
 * 一次回答的完整回放视图 —— <b>把 traceId 翻译成「人话」</b>。
 *
 * <p><b>设计原则：默认不返回任何问答原文与片段原文。</b>
 * 回放的核心价值在于「看清链路与统计」（是否召回到、用了哪个模型、慢在哪一步、
 * 引用了哪份文件的哪个版本、系统给自己打了多少分），这些都不需要正文。
 * 正文是否可见由统一的内容采集档位决定（见 {@code ReplayAppService}），
 * 不为回放单独开后门 —— 后门一旦存在，它就会成为批量导出通道。</p>
 *
 * <p><b>为什么要有 {@code degraded}</b>：回放的价值在依赖挂掉时才最大
 * （出了问题才来回放）。因此检索服务不可达时不能整体失败，
 * 而要返回能拿到的那部分，并把缺失原因<b>显式列出来</b>。
 * 「少了一块且知道为什么少」远胜于「整个页面报 500」。</p>
 *
 * @param traceId        链路 ID
 * @param found          是否找到任何关联数据；false 表示该 traceId 不存在或已超出留存期
 * @param degraded       降级说明列表（依赖不可达、数据缺失等），空列表表示数据完整
 * @param conversation   会话摘要
 * @param messages       消息列表（按时间正序，用户与助手成对）
 * @param citations      引用列表（默认不含正文，只给位置与分数）
 * @param tokenUsage     token 计量流水
 * @param evalScores     质量评估分数
 * @param retrievalLogs  检索段（来自 rag-retrieval-service，默认不含片段原文）
 * @param timeline       关键事件时间线 —— <b>非工程角色主要看这一段</b>
 * @param deepLinks      跳到 APM / LangFuse 的深链（无密钥，仅 URL）
 * @author rag-platform
 */
public record ReplayView(String traceId,
                         boolean found,
                         List<String> degraded,
                         ConversationBrief conversation,
                         List<MessageItem> messages,
                         List<CitationItem> citations,
                         List<TokenItem> tokenUsage,
                         List<EvalItem> evalScores,
                         List<RetrievalTraceView> retrievalLogs,
                         List<TimelineItem> timeline,
                         DeepLinks deepLinks) {

    /**
     * 会话摘要。
     *
     * <p>{@code subjectId} 已掩码（如 {@code 100***86}）：运维需要「知道是谁的会话」
     * 才能找对人对齐，但不需要看到完整账号 —— 掩码后仍可人工核对，又不构成
     * 一份可直接落盘的身份证号清单。</p>
     */
    public record ConversationBrief(Long conversationId,
                                    String conversationNo,
                                    String title,
                                    String subjectType,
                                    String subjectId,
                                    Integer status,
                                    LocalDateTime createTime) {
    }

    /**
     * 消息条目。
     *
     * @param contentOmitted true 表示正文按内容档位被省略（不是数据丢失）
     * @param answerType     ANSWERED / NO_HIT / GUARDRAIL_BLOCKED / ERROR
     */
    public record MessageItem(String messageId,
                              String role,
                              String answerType,
                              String content,
                              boolean contentOmitted,
                              String modelCode,
                              String promptVersion,
                              String guardrailHit,
                              Integer ttfbMs,
                              Integer costMs,
                              LocalDateTime createTime) {
    }

    /**
     * 引用条目（默认无正文）。
     *
     * @param contentOmitted     正文是否被省略
     * @param contentFingerprint 片段指纹：用于判断「两次回答引用的是同一段」而不泄漏正文
     */
    public record CitationItem(int seq,
                               Long kbId,
                               Long docId,
                               String docName,
                               Integer versionNo,
                               Integer pageNo,
                               Integer chunkIndex,
                               BigDecimal score,
                               boolean contentOmitted,
                               String contentFingerprint) {
    }

    /** Token 计量条目 */
    public record TokenItem(String modelCode,
                            String modelName,
                            Integer inputTokens,
                            Integer outputTokens,
                            Integer totalTokens,
                            Integer costMs,
                            LocalDate bizDate) {
    }

    /** 质量评估条目 */
    public record EvalItem(String metricCode,
                           BigDecimal score,
                           Integer scoreScale,
                           Integer passed,
                           BigDecimal threshold,
                           String evalSource,
                           String judgeModel,
                           String reason,
                           LocalDateTime createTime) {
    }

    /**
     * 时间线条目。
     *
     * @param at     发生时间（ISO 字符串，便于前端直接渲染）
     * @param stage  阶段名：SESSION / QUESTION / RETRIEVAL / GENERATE / EVALUATE
     * @param detail 人类可读摘要
     */
    public record TimelineItem(String at, String stage, String detail) {
    }

    /**
     * 深链。
     *
     * <p>模板由配置提供（{@code rag.replay.*-url-template}），<b>不含任何密钥</b>。
     * 若未配置则返回 null，前端不展示对应入口 —— 而不是给一个点了 404 的链接。</p>
     */
    public record DeepLinks(String apm,
                            String langfuse,
                            String retrievalLog) {
    }
}
''')

# ============================================================ ReplayProperties
w(CHAT / "app/eval/ReplayProperties.java", r'''package com.fintech.rag.chat.app.eval;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * 回放能力配置。
 *
 * <pre>
 * rag:
 *   replay:
 *     enabled: true
 *     apm-url-template: "http://apm.internal/trace/{traceId}"
 *     langfuse-url-template: "http://langfuse.internal/project/rag/traces/{traceId}"
 *     retrieval-log-url-template: "http://ops.internal/rag/retrieval?traceId={traceId}"
 * </pre>
 *
 * <p><b>为什么深链用「模板」而不是拼死在代码里</b>：APM 与 LangFuse 的地址
 * 在不同环境（开发 / 测试 / 生产）都不同，写进代码意味着改一次环境要发一次版。
 * 模板放在配置中心，运维自己就能改。</p>
 *
 * <p><b>模板里绝不允许出现密钥</b>：LangFuse 的 pk/sk 只配在 OTel Collector，
 * 业务服务零持有（见 docs/05 安全约定）。深链是给人点的普通 URL，
 * 有权限的人点进去自然能看到数据，没有权限的人拿了 URL 也看不到。</p>
 *
 * @author rag-platform
 */
@ConfigurationProperties(prefix = "rag.replay")
public class ReplayProperties {

    private boolean enabled = true;

    /** APM 链路详情页模板，{traceId} 为占位符 */
    private String apmUrlTemplate;

    /** LangFuse Trace 详情页模板 */
    private String langfuseUrlTemplate;

    /** 检索日志工作台模板 */
    private String retrievalLogUrlTemplate;

    public boolean isEnabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }

    public String getApmUrlTemplate() {
        return apmUrlTemplate;
    }

    public void setApmUrlTemplate(String apmUrlTemplate) {
        this.apmUrlTemplate = apmUrlTemplate;
    }

    public String getLangfuseUrlTemplate() {
        return langfuseUrlTemplate;
    }

    public void setLangfuseUrlTemplate(String langfuseUrlTemplate) {
        this.langfuseUrlTemplate = langfuseUrlTemplate;
    }

    public String getRetrievalLogUrlTemplate() {
        return retrievalLogUrlTemplate;
    }

    public void setRetrievalLogUrlTemplate(String retrievalLogUrlTemplate) {
        this.retrievalLogUrlTemplate = retrievalLogUrlTemplate;
    }
}
''')

# ============================================================ ReplayAppService
w(CHAT / "app/eval/ReplayAppService.java", r'''package com.fintech.rag.chat.app.eval;

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
''')

# ============================================================ ReplayController
w(CHAT / "api/controller/ReplayController.java", r'''package com.fintech.rag.chat.api.controller;

import com.fintech.rag.api.dto.replay.ReplayView;
import com.fintech.rag.chat.app.eval.ReplayAppService;
import com.fintech.rag.common.core.R;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 回放接口 —— <b>「按 traceId 一键回放一次回答」的对外入口</b>。
 *
 * <p><b>为什么路径是 /replay/{traceId} 而不是 /message/{messageId}/replay</b>：
 * traceId 是跨系统（APM、LangFuse、检索日志、审计日志）唯一通用的键。
 * 用户报障时往往只能提供「日志里的一串 ID」，从 traceId 出发才能一次性
 * 把散落在五个地方的证据聚齐。messageId 只是业务侧的锚点，
 * 回放接口同时提供 {@code /replay/by-message/{messageId}} 便于前端从点踩直接跳转。</p>
 *
 * <p><b>网关侧不得暴露本路径</b>：回放会返回他人的问答记录与引用信息，
 * 属于内网运维能力。网关的路由白名单里不应包含 {@code /api/ai/replay/**}；
 * 服务侧另有 {@code X-Request-Source} 准入校验作为纵深防御。</p>
 *
 * @author rag-platform
 */
@RestController
@RequestMapping("/api/ai")
public class ReplayController {

    private final ReplayAppService replayAppService;

    public ReplayController(ReplayAppService replayAppService) {
        this.replayAppService = replayAppService;
    }

    /**
     * 按 traceId 回放。
     *
     * @param traceId     32 位小写 hex 的 W3C trace-id
     * @param withContent 是否请求正文；即便为 true，仍受内容采集档位最终裁决
     */
    @GetMapping("/replay/{traceId}")
    public R<ReplayView> replay(@PathVariable("traceId") String traceId,
                                @RequestParam(value = "withContent", required = false)
                                Boolean withContent) {
        // 用包装类型而非 primitive：@RequestParam(required=false) + boolean 在参数缺省时
        // 会因「不可为 null 的基本类型拿到 null」而抛异常，属于典型的边界坑
        return R.ok(replayAppService.replay(traceId, Boolean.TRUE.equals(withContent)));
    }
}
''')

print("---- total:", len(written))


# ============================================================ application.yml（改）
# 采用「整节重写」而不是「插一行」：
# 最初的实现是把 eval 块插到 `observability:` 键之前，结果把 observability 的
# 注释块与它的键分开了（注释留在原地、键被挤到下面），YAML 结构虽然合法，
# 但人读起来完全错乱 —— 这种问题在 review 时极易漏过。
# 整节重写让「顺序与归属」由脚本唯一决定，无论跑多少次结果都一样。
def rag_section(with_replay: bool) -> str:
    replay_block = """  # ---------------------------------------------------------------------------
  # 回放（按 traceId 一键还原一次回答）
  # 深链模板按环境填写；**未配置时回放视图返回 null，前端不展示入口** ——
  # 不给一个点了必然 404 的链接，是运维工具的基本体面。
  # 模板里严禁出现任何密钥：LangFuse 凭据只配在 OTel Collector，业务服务零持有。
  # ---------------------------------------------------------------------------
  replay:
    enabled: ${RAG_REPLAY_ENABLED:true}
    apm-url-template: ${RAG_REPLAY_APM_URL:}
    langfuse-url-template: ${RAG_REPLAY_LANGFUSE_URL:}
    retrieval-log-url-template: ${RAG_REPLAY_RETRIEVAL_URL:}
""" if with_replay else ""
    return """rag:
  # ---------------------------------------------------------------------------
  # 问答链路参数
  # ---------------------------------------------------------------------------
  chat:
    model-refresh-ms: 300000
    guardrail-refresh-ms: 600000
  # ---------------------------------------------------------------------------
  # 服务端来源鉴权（两套鉴权唯一分流点是 X-Request-Source，仅网关注入）
  # ---------------------------------------------------------------------------
  server:
    auth:
      enabled: true
      trusted-gateway-cidrs:
        - 10.10.1.0/24
      gateway-signature-enabled: false
      gateway-sign-secret: ${RAG_GATEWAY_SIGN_SECRET:}
  # ---------------------------------------------------------------------------
  # 在线评估（t_llm_eval_score 的 ONLINE 来源）
  # 只启用「无需裁判模型即可计算」的指标：CITATION_COVERAGE / CONTEXT_PRECISION。
  # FAITHFULNESS、ANSWER_RELEVANCY、HALLUCINATION 需要 LLM-as-judge，
  # 接入前刻意不计算 —— 用规则凑出来的假分数比没有分数更危险。
  # ---------------------------------------------------------------------------
  eval:
    online-enabled: ${RAG_EVAL_ONLINE_ENABLED:true}
    sample-rate: ${RAG_EVAL_SAMPLE_RATE:0.05}
    max-concurrent: ${RAG_EVAL_MAX_CONCURRENT:2}
    manual-metrics:
      - CITATION_COVERAGE
      - CONTEXT_PRECISION
""" + replay_block + """  # ---------------------------------------------------------------------------
  # 可观测（详见 docs/05-AI可观测与运维监控方案.md）
  # 生产把 content-level 保持 METRICS_ONLY：既不落问答原文，也不影响链路回放能力
  # ---------------------------------------------------------------------------
  observability:
    enabled: true
    content-level: ${RAG_OBS_CONTENT_LEVEL:METRICS_ONLY}
    # 防呆闸：即使 content-level 被误配成 FULL_CONTENT，也不会真的上报原文
    # 如需在开发环境开启原文上报，把本项置为 true（生产严禁）
    allow-plain-text-content: ${RAG_OBS_ALLOW_PLAIN_TEXT:false}
    max-content-chars: 2000
    record-retrieved-chunks: false
    subject-hash-salt: ${RAG_SUBJECT_HASH_SALT:}
    provider-name: openai

"""


yml_path = ROOT / "rag-platform/rag-chat-service/src/main/resources/application.yml"
yml_text = yml_path.read_text(encoding="utf-8")
match = re.search(r'(?ms)^rag:.*?(?=^management:)', yml_text)
if match:
    yml_path.write_text(yml_text[:match.start()] + rag_section(True) + yml_text[match.end():],
                        encoding="utf-8", newline="\n")
    w(yml_path, yml_path.read_text(encoding='utf-8'))
    print("   （rag 节已整节规范化，顺序：chat / server / eval / replay / observability）")
else:
    print("!  未在 application.yml 中找到 rag: 节，跳过")

print("---- 含 yml 合计:", len(written))
