# -*- coding: utf-8 -*-
"""
S14 · 落库编排 + t_llm_eval_score 写入链路。

本脚本解决的核心问题：**表建好了，但没有人往里写。**

产出：
  1) app/persist/ChatPersistenceService.java
     落库编排的唯一入口：会话维护、用户消息、助手消息、引用、token 用量。
     纪律：每个方法内部吞异常 + 记录 ERROR，落库失败绝不影响用户已经看到的回答。
  2) app/eval/EvalProperties.java      在线抽样配置
  3) app/eval/EvalScoreCommand.java     写入命令（显式承载所有纪律字段）
  4) app/eval/LlmEvalScoreAppService.java  唯一写入口，含四条纪律校验
  5) app/eval/EvalSampleContext.java    抽样上下文
  6) app/eval/OnlineEvalSampler.java    在线抽样（异步 + 可算指标先算）
  7) api/controller/FeedbackController.java
  8) api/controller/EvalController.java
  9) rag-chat-service/src/main/resources/application.yml（改，追加 rag.eval）

幂等：全部覆盖写。
"""
import pathlib
import re

ROOT = pathlib.Path(r"D:/AiWorkOut/java-ai")
CHAT = ROOT / "rag-platform/rag-chat-service/src/main/java/com/fintech/rag/chat"
CHAT_RES = ROOT / "rag-platform/rag-chat-service/src/main/resources"

written = []


def w(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    written.append(path)
    print("W +", path.relative_to(ROOT).as_posix())


# ======================================================== 1 ChatPersistenceService
w(CHAT / "app/persist/ChatPersistenceService.java", r'''package com.fintech.rag.chat.app.persist;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.fintech.rag.api.dto.retrieval.RetrievalResponse;
import com.fintech.rag.chat.domain.model.ChatMessage;
import com.fintech.rag.chat.domain.model.Conversation;
import com.fintech.rag.chat.domain.model.MessageCitation;
import com.fintech.rag.chat.domain.model.TokenUsageRecord;
import com.fintech.rag.chat.infra.persistence.mapper.ChatMessageMapper;
import com.fintech.rag.chat.infra.persistence.mapper.ConversationMapper;
import com.fintech.rag.chat.infra.persistence.mapper.MessageCitationMapper;
import com.fintech.rag.chat.infra.persistence.mapper.TokenUsageRecordMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

/**
 * 问答落库编排 —— <b>「一次回答」全部持久化动作的唯一出口</b>。
 *
 * <p><b>为什么要独立成类，而不是散在编排服务里</b>：落库涉及 4 张表 + 1 次会话计数更新，
 * 散在编排里会让「生成逻辑」与「存储逻辑」互相缠绕；更要紧的是
 * <b>落库失败的处理策略必须统一</b> —— 每个方法都吞异常并记 ERROR，
 * 因为「用户已经看到回答了，此时因为写库失败而报错」是纯粹的体验灾难。</p>
 *
 * <p><b>事务边界</b>：本类<b>刻意不加 {@code @Transactional}</b>。原因：
 * 这些写入都发生在模型调用<b>之后</b>（模型调用不可回滚），把它们包进事务只会
 * 延长连接持有时间、放大锁竞争，却换不来任何原子性收益。
 * 真正的原子性诉求（如「消息 + 引用」必须同时成功）应通过
 * 「先写消息，再写引用，引用失败只记 ERROR 不抛」来降级处理 ——
 * 引用缺失只会让回放少一段，而回滚消息会让用户看到「答案凭空消失」。</p>
 *
 * @author rag-platform
 */
@Service
public class ChatPersistenceService {

    private static final Logger log = LoggerFactory.getLogger(ChatPersistenceService.class);

    private static final long DEFAULT_TENANT_ID = 0L;

    private final ConversationMapper conversationMapper;
    private final ChatMessageMapper messageMapper;
    private final MessageCitationMapper citationMapper;
    private final TokenUsageRecordMapper tokenUsageMapper;

    public ChatPersistenceService(ConversationMapper conversationMapper,
                                  ChatMessageMapper messageMapper,
                                  MessageCitationMapper citationMapper,
                                  TokenUsageRecordMapper tokenUsageMapper) {
        this.conversationMapper = conversationMapper;
        this.messageMapper = messageMapper;
        this.citationMapper = citationMapper;
        this.tokenUsageMapper = tokenUsageMapper;
    }

    // ------------------------------------------------------------------ 会话
    /**
     * 确保会话存在（首问自动建会话），返回会话 ID。
     *
     * <p>返回 null 表示会话既未提供也无法创建；此时上层仍应继续作答，
     * 只是这条回答不会被归入任何会话（回放时只能按 traceId 查，查不到会话）——
     * 这比直接报错好，但必须告警。</p>
     */
    public Long ensureConversation(String rawConversationId, String subjectType, String subjectId,
                                   String question, List<Long> kbIds) {
        Long conversationId = parseLongQuietly(rawConversationId);
        if (conversationId != null) {
            return conversationId;
        }
        try {
            Conversation conversation = new Conversation();
            conversation.setTenantId(DEFAULT_TENANT_ID);
            conversation.setConversationNo("C" + UUID.randomUUID().toString().replace("-", ""));
            conversation.setTitle(titleOf(question));
            conversation.setSubjectType(subjectType);
            conversation.setSubjectId(subjectId);
            conversation.setKbScope(kbIds == null ? null : kbIds.toString());
            conversation.setMessageCount(0);
            conversation.setTotalTokens(0L);
            conversation.setStatus(1);
            conversation.setDeleted(0);
            conversationMapper.insert(conversation);
            return conversation.getId();
        } catch (Exception ex) {
            log.error("创建会话失败 subjectType={} subjectId={}（本次回答将不归属任何会话）",
                    subjectType, subjectId, ex);
            return null;
        }
    }

    /** 会话计数累加：消息数 + token。用于会话列表展示与「本会话花了多少 token」归因 */
    public void accumulateConversation(Long conversationId, int messageDelta, long tokenDelta) {
        if (conversationId == null || (messageDelta == 0 && tokenDelta == 0)) {
            return;
        }
        try {
            conversationMapper.update(null, Wrappers.<Conversation>lambdaUpdate()
                    .eq(Conversation::getId, conversationId)
                    .setSql("message_count = message_count + " + messageDelta)
                    .setSql("total_tokens = total_tokens + " + tokenDelta)
                    .set(Conversation::getUpdateTime, LocalDateTime.now()));
        } catch (Exception ex) {
            log.error("更新会话计数失败 conversationId={}", conversationId, ex);
        }
    }

    // ------------------------------------------------------------------ 消息
    /** 写入用户消息，返回消息 ID（作为助手消息的 parent_id） */
    public Long saveUserMessage(Long conversationId, String question) {
        try {
            ChatMessage message = new ChatMessage();
            message.setTenantId(DEFAULT_TENANT_ID);
            message.setConversationId(conversationId);
            message.setMessageNo(nextMessageNo());
            message.setRole("USER");
            message.setContent(question);
            message.setTraceId(com.fintech.rag.common.context.RequestContext.currentTraceId());
            message.setDeleted(0);
            messageMapper.insert(message);
            return message.getId();
        } catch (Exception ex) {
            log.error("保存用户消息失败 conversationId={}", conversationId, ex);
            return null;
        }
    }

    /**
     * 写入助手消息，返回消息 ID。
     *
     * @param parentId       上一条消息（用户消息）ID，构成对话树，回放时才能成对展示
     * @param traceId        本次回答的 W3C traceId。<b>必须来自服务端链路</b>，
     *                       这是「按 traceId 一键回放」的唯一钥匙
     * @param contentTokens  输出 token 数（可空，来自模型返回的真实用量）
     */
    public Long saveAssistantMessage(Long conversationId, Long parentId, String answer,
                                     String answerType, String modelCode, String traceId,
                                     String promptVersion, String guardrailHit,
                                     Integer ttfbMs, int costMs, Integer contentTokens) {
        try {
            ChatMessage message = new ChatMessage();
            message.setTenantId(DEFAULT_TENANT_ID);
            message.setConversationId(conversationId);
            message.setParentId(parentId);
            message.setMessageNo(nextMessageNo());
            message.setRole("ASSISTANT");
            message.setContent(answer == null ? "" : answer);
            message.setAnswerType(answerType);
            message.setModelCode(modelCode);
            message.setPromptVersion(promptVersion);
            message.setTraceId(traceId);
            message.setGuardrailHit(guardrailHit);
            message.setTtfbMs(ttfbMs);
            message.setCostMs(costMs);
            message.setContentTokens(contentTokens);
            message.setDeleted(0);
            messageMapper.insert(message);
            return message.getId();
        } catch (Exception ex) {
            log.error("保存助手消息失败 conversationId={} answerType={}", conversationId, answerType, ex);
            return null;
        }
    }

    // ------------------------------------------------------------------ 引用
    /**
     * 写入引用列表。
     *
     * <p><b>只在用户消息为 ASSISTANT 且确实召回到片段时才写</b>；
     * 空召回（NO_HIT）不会有引用，这是正确行为而非缺数据 ——
     * 回放时看到「NO_HIT 且零引用」应立刻明白链路是干净的。</p>
     *
     * @return 实际写入条数（-1 表示失败），用于反馈给 span 做自检
     */
    public int saveCitations(Long messageId, List<RetrievalResponse.Chunk> chunks) {
        if (messageId == null || chunks == null || chunks.isEmpty()) {
            return 0;
        }
        int seq = 0;
        int ok = 0;
        for (RetrievalResponse.Chunk chunk : chunks) {
            seq++;
            try {
                MessageCitation citation = new MessageCitation();
                citation.setMessageId(messageId);
                citation.setSeq(seq);
                citation.setKbId(chunk.kbId());
                citation.setDocId(chunk.docId());
                citation.setDocName(chunk.docName());
                citation.setVersionNo(chunk.versionNo() == null ? 1 : chunk.versionNo());
                citation.setRagflowChunkId(chunk.chunkId());
                citation.setChunkIndex(chunk.chunkIndex());
                citation.setContent(chunk.content());
                citation.setScore(chunk.score() == null ? null : BigDecimal.valueOf(chunk.score()));
                citation.setPageNo(chunk.pageNo());
                citationMapper.insert(citation);
                ok++;
            } catch (Exception ex) {
                log.error("写入引用失败 messageId={} seq={}（不影响回答展示）", messageId, seq, ex);
            }
        }
        return ok;
    }

    // ------------------------------------------------------------------ Token 计量
    /**
     * 写入 token 计量流水。
     *
     * <p><b>为什么这张表不能省</b>：Prometheus 里的 token 指标是观测聚合量，
     * 重启与采样会丢细节；本表是<b>计费账本</b>，要求逐笔可重算 ——
     * 「这个部门上个月花了多少 token」必须能精确回答，不能靠估算。</p>
     */
    public void saveTokenUsage(String traceId, String subjectType, String subjectId,
                               Long conversationId, Long messageId,
                               String modelCode, String modelName,
                               Integer inputTokens, Integer outputTokens, Integer costMs) {
        try {
            int in = inputTokens == null ? 0 : inputTokens;
            int out = outputTokens == null ? 0 : outputTokens;
            TokenUsageRecord record = new TokenUsageRecord();
            record.setTenantId(DEFAULT_TENANT_ID);
            record.setTraceId(traceId);
            record.setSubjectType(subjectType);
            record.setSubjectId(subjectId);
            record.setConversationId(conversationId);
            record.setMessageId(messageId);
            record.setModelCode(modelCode == null ? "UNKNOWN" : modelCode);
            record.setModelName(modelName == null ? "unknown" : modelName);
            record.setInputTokens(in);
            record.setOutputTokens(out);
            record.setTotalTokens(in + out);
            record.setCostMs(costMs);
            record.setBizDate(LocalDate.now());
            tokenUsageMapper.insert(record);
        } catch (Exception ex) {
            log.error("写入 token 计量失败 traceId={} modelCode={}", traceId, modelCode, ex);
        }
    }

    // ------------------------------------------------------------------ 工具
    private String nextMessageNo() {
        return "M" + UUID.randomUUID().toString().replace("-", "");
    }

    /** 会话标题取首问前 50 字：过长会撑爆列表布局，且首问通常已足够概括主题 */
    private String titleOf(String question) {
        if (question == null) {
            return null;
        }
        String trimmed = question.strip();
        return trimmed.length() <= 50 ? trimmed : trimmed.substring(0, 50);
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
}
''')

# ======================================================== 2 EvalProperties
w(CHAT / "app/eval/EvalProperties.java", r'''package com.fintech.rag.chat.app.eval;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

/**
 * 在线评估配置。
 *
 * <pre>
 * rag:
 *   eval:
 *     online-enabled: true          # 总开关；关闭后不抽样，评估只能靠离线批次与人工
 *     sample-rate: 0.05             # 抽样率。5% 足够观察趋势，又不会把 token 成本推高
 *     max-concurrent: 2             # 抽样评估线程数上限，防止评估把生成链路的资源吃掉
 *     manual-metrics: [...]         # 骨架阶段仅启用「无需裁判模型即可计算」的指标
 * </pre>
 *
 * <p><b>采样率怎么定</b>：在线评估的目的是「发现趋势变化」，不是「精确统计」。
 * 5% 采样在日请求量过千时即可给出稳定的日维度曲线；把采样率设成 1.0
 * 只会让评估成本随流量线性上涨，而趋势判断并不会更准。</p>
 *
 * <p><b>为什么要有 max-concurrent</b>：评估任务与用户问答共用 CPU 与网络。
 * 不设上限时，一次流量高峰会让评估线程占满线程池，反而拖慢真实回答 ——
 * 观测手段拖垮被测系统是最典型的自伤。</p>
 *
 * @author rag-platform
 */
@ConfigurationProperties(prefix = "rag.eval")
public class EvalProperties {

    private boolean onlineEnabled = true;

    private BigDecimal sampleRate = new BigDecimal("0.05");

    private int maxConcurrent = 2;

    /** 骨架阶段启用的指标：必须是 EvalMetric 中 computableWithoutJudge=true 的那些 */
    private List<String> manualMetrics = new ArrayList<>(List.of("CITATION_COVERAGE", "CONTEXT_PRECISION"));

    public boolean isOnlineEnabled() {
        return onlineEnabled;
    }

    public void setOnlineEnabled(boolean onlineEnabled) {
        this.onlineEnabled = onlineEnabled;
    }

    public BigDecimal getSampleRate() {
        return sampleRate;
    }

    public void setSampleRate(BigDecimal sampleRate) {
        this.sampleRate = sampleRate;
    }

    public int getMaxConcurrent() {
        return maxConcurrent;
    }

    public void setMaxConcurrent(int maxConcurrent) {
        this.maxConcurrent = maxConcurrent;
    }

    public List<String> getManualMetrics() {
        return manualMetrics;
    }

    public void setManualMetrics(List<String> manualMetrics) {
        this.manualMetrics = manualMetrics;
    }
}
''')

# ======================================================== 3 EvalScoreCommand
w(CHAT / "app/eval/EvalScoreCommand.java", r'''package com.fintech.rag.chat.app.eval;

import com.fintech.rag.api.dto.common.EvalSource;

import java.math.BigDecimal;

/**
 * 评估分数写入命令 —— 承载全部需要落库的「快照」字段。
 *
 * <p><b>刻意不包含 {@code passed}</b>：是否通过门禁必须由写入入口按阈值算出。
 * 让调用方传 passed 只有两种结局 —— 要么各调用方算法不一致，
 * 要么有人为了让门禁通过而直接传 true。两者都会让质量报告失去意义。</p>
 *
 * @param traceId       被评估回答的 W3C traceId（与 t_message.trace_id 对齐）
 * @param messageId     被评估的助手消息 ID
 * @param conversationId 会话 ID
 * @param evalBatchNo   离线批次号，ONLINE / MANUAL 时为 null
 * @param evalSource    来源
 * @param judgeModel    裁判模型编码快照；ONLINE / BATCH 必填，MANUAL 必须为 null
 * @param promptVersion 被评估回答的 Prompt 版本快照（可空，但强烈建议填写）
 * @param metricCode    指标码，白名单见 EvalMetric
 * @param score         得分，量纲 0~1
 * @param threshold     门禁阈值快照；为 null 时取指标默认阈值
 * @param reason        评分理由（禁止写问答原文）
 * @param createBy      写入者（人工评估为操作人；自动评估为空）
 * @author rag-platform
 */
public record EvalScoreCommand(String traceId,
                               Long messageId,
                               Long conversationId,
                               String evalBatchNo,
                               EvalSource evalSource,
                               String judgeModel,
                               String promptVersion,
                               String metricCode,
                               BigDecimal score,
                               BigDecimal threshold,
                               String reason,
                               String createBy) {
}
''')

# ======================================================== 4 LlmEvalScoreAppService
w(CHAT / "app/eval/LlmEvalScoreAppService.java", r'''package com.fintech.rag.chat.app.eval;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.fintech.rag.api.dto.common.EvalMetric;
import com.fintech.rag.api.dto.common.EvalSource;
import com.fintech.rag.chat.domain.model.LlmEvalScore;
import com.fintech.rag.chat.infra.persistence.mapper.LlmEvalScoreMapper;
import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import com.fintech.rag.common.observability.ContentSanitizer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.List;

/**
 * 回答质量评估的<b>唯一写入入口</b>（{@code t_llm_eval_score}）。
 *
 * <p>所有评估来源（在线抽样 / 离线批次 / 人工评分）都必须经过本类，
 * 禁止任何地方直接 {@code llmEvalScoreMapper.insert}。</p>
 *
 * <p><b>四条写入纪律（每条都对应一个真实会踩的坑）</b>：</p>
 * <ol>
 *   <li><b>指标码白名单</b>：自由字符串会让同一指标在库里出现
 *       {@code FAITHFULNESS} / {@code faithfulness} / {@code 忠实度} 三种写法，
 *       看板被拆成三条曲线且历史无法重算；</li>
 *   <li><b>量纲校验</b>：分数必须落在 [0, 1]。不校验时的典型事故是
 *       有人按 1~5 分制写了个 4.5，于是「平均忠实度 4.5」被当成 450% 展示；</li>
 *   <li><b>reason 纪律</b>：评分理由禁止出现问答原文。检测到 PII 类模式时
 *       <b>直接丢弃 reason 并告警</b>（而不是脱敏后照写）—— reason 本该是
 *       「结论 + 依据类型」，出现 PII 说明上游把原文塞进来了，脱敏只是掩盖问题；</li>
 *   <li><b>passed 服务端计算</b>：按指标阈值算，且区分「越低越好」的指标
 *       （幻觉率）。方向写反会把最好的模型判为不合格。</li>
 * </ol>
 *
 * @author rag-platform
 */
@Service
public class LlmEvalScoreAppService {

    private static final Logger log = LoggerFactory.getLogger(LlmEvalScoreAppService.class);

    private static final long DEFAULT_TENANT_ID = 0L;
    private static final BigDecimal ZERO = BigDecimal.ZERO;
    private static final BigDecimal ONE = BigDecimal.ONE;

    private final LlmEvalScoreMapper evalScoreMapper;
    private final ContentSanitizer sanitizer;

    public LlmEvalScoreAppService(LlmEvalScoreMapper evalScoreMapper, ContentSanitizer sanitizer) {
        this.evalScoreMapper = evalScoreMapper;
        this.sanitizer = sanitizer;
    }

    /**
     * 写入一条评估分数。
     *
     * @return 落库后的实体（含生成的 ID 与计算出的 passed）
     * @throws BizException 校验不通过时抛出，<b>宁可写不进去也不要写过脏数据</b>
     */
    public LlmEvalScore record(EvalScoreCommand command) {
        if (command == null) {
            throw BizException.of(ErrorCode.PARAM_INVALID, "评估命令为空");
        }
        if (command.evalSource() == null) {
            throw BizException.of(ErrorCode.PARAM_INVALID, "评估来源不能为空");
        }
        if (command.score() == null) {
            throw BizException.of(ErrorCode.PARAM_INVALID, "评估分数不能为空");
        }

        // ---- 纪律 1：指标码白名单 ----
        EvalMetric metric;
        try {
            metric = EvalMetric.of(command.metricCode());
        } catch (IllegalArgumentException ex) {
            throw BizException.of(ErrorCode.PARAM_INVALID, ex.getMessage());
        }

        // ---- 纪律 2：量纲校验 ----
        BigDecimal score = command.score();
        if (score.compareTo(ZERO) < 0 || score.compareTo(ONE) > 0) {
            throw BizException.of(ErrorCode.PARAM_INVALID,
                    "评估分数必须在 0~1 之间，实际=" + score.toPlainString() + "（本项目统一 0~1 量纲）");
        }

        // ---- judgeModel 必填性（把「谁给的分数」写清楚，否则无法归因） ----
        String judgeModel = blankToNull(command.judgeModel());
        if (command.evalSource() == EvalSource.MANUAL) {
            if (judgeModel != null) {
                throw BizException.of(ErrorCode.PARAM_INVALID, "人工评估不应写 judgeModel（裁判是人）");
            }
        } else if (judgeModel == null) {
            throw BizException.of(ErrorCode.PARAM_INVALID,
                    command.evalSource().name() + " 来源必须写明 judgeModel，否则历史分数无法归因");
        }

        // ---- 纪律 3：reason 纪律 ----
        String reason = guardReason(command.reason());

        // ---- 纪律 4：passed 服务端计算 ----
        BigDecimal threshold = command.threshold() == null ? metric.getDefaultThreshold() : command.threshold();
        int passed = judge(metric, score, threshold) ? 1 : 0;

        LlmEvalScore entity = new LlmEvalScore();
        entity.setTenantId(DEFAULT_TENANT_ID);
        entity.setTraceId(blankToNull(command.traceId()));
        entity.setMessageId(command.messageId());
        entity.setConversationId(command.conversationId());
        entity.setEvalBatchNo(blankToNull(command.evalBatchNo()));
        entity.setEvalSource(command.evalSource().name());
        entity.setJudgeModel(judgeModel);
        entity.setPromptVersion(blankToNull(command.promptVersion()));
        entity.setMetricCode(metric.name());
        entity.setScore(score);
        entity.setScoreScale(1);
        entity.setPassed(passed);
        entity.setThreshold(threshold);
        entity.setReason(reason);
        entity.setCreateBy(blankToNull(command.createBy));
        evalScoreMapper.insert(entity);

        log.debug("评估分数落库 traceId={} metric={} score={} passed={} source={}",
                entity.getTraceId(), entity.getMetricCode(),
                entity.getScore().toPlainString(), passed, entity.getEvalSource());
        return entity;
    }

    /** 按 traceId 查询评估分数（回放视图使用） */
    public List<LlmEvalScore> listByTrace(String traceId) {
        if (traceId == null || traceId.isBlank()) {
            return List.of();
        }
        return evalScoreMapper.selectList(Wrappers.<LlmEvalScore>lambdaQuery()
                .eq(LlmEvalScore::getTraceId, traceId)
                .orderByAsc(LlmEvalScore::getCreateTime));
    }

    // ------------------------------------------------------------------ 内部
    /**
     * 门禁判定。注意「越低越好」的指标方向相反：
     * 幻觉率 0.05 优于阈值 0.10 应判通过，若沿用「越大越好」会把最好的结果判成不合格。
     */
    private boolean judge(EvalMetric metric, BigDecimal score, BigDecimal threshold) {
        return metric.isLowerBetter()
                ? score.compareTo(threshold) <= 0
                : score.compareTo(threshold) >= 0;
    }

    /**
     * reason 防污染闸。
     *
     * <p>判定方式：对 reason 做一次 PII 掩码，若掩码后与原值不同，说明里面存在
     * 手机号 / 身份证 / 银行卡 / 邮箱等模式 —— 而 reason 的定位是「结论 + 依据类型」，
     * 出现这些模式意味着上游把问答原文或用户输入塞了进来。此时丢弃整条 reason
     * 而不是脱敏后照写：<b>脱敏会让违规变得不可见，丢弃才能让上游修复。</b></p>
     */
    private String guardReason(String reason) {
        String trimmed = blankToNull(reason);
        if (trimmed == null) {
            return null;
        }
        String masked = sanitizer.mask(trimmed);
        if (!masked.equals(trimmed)) {
            log.warn("评估 reason 中出现疑似 PII/原文内容，已整条丢弃（请检查上游写入逻辑）；长度={}",
                    trimmed.length());
            return "[DROPPED: reason 含疑似 PII 或问答原文，按合规要求不予留档]";
        }
        return trimmed.length() <= 1024 ? trimmed : trimmed.substring(0, 1024);
    }

    private String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value;
    }
}
''')

# ======================================================== 5 EvalSampleContext
w(CHAT / "app/eval/EvalSampleContext.java", r'''package com.fintech.rag.chat.app.eval;

/**
 * 在线抽样上下文 —— 从一次完成的回答里抽出的「可评估事实」。
 *
 * <p>全部字段都来自本次请求的既有产物，<b>不含问答原文</b>：
 * 评估指标应尽量建立在「结构化的链路事实」上（引用数、召回数、耗时、结果类型），
 * 这样在线评估才能在不采集任何文本内容的前提下运行 —— 这是合规友好的设计，
 * 也让评估可以在生产环境长期开启。</p>
 *
 * @param traceId        链路 ID
 * @param messageId      助手消息 ID
 * @param conversationId 会话 ID
 * @param answerType     回答类型（ANSWERED / NO_HIT / GUARDRAIL_BLOCKED / ERROR）
 * @param modelCode      模型编码
 * @param promptVersion  Prompt 版本快照
 * @param citationCount  实际引用条数
 * @param chunkCount     最终召回片段数
 * @param rawChunkCount  RAGFlow 原始召回数（用于区分「没召回到」与「召回后被过滤掉」）
 * @param topScore       最高分
 * @param ttfbMs         首字节耗时
 * @param costMs         端到端耗时
 * @author rag-platform
 */
public record EvalSampleContext(String traceId,
                                Long messageId,
                                Long conversationId,
                                String answerType,
                                String modelCode,
                                String promptVersion,
                                int citationCount,
                                int chunkCount,
                                int rawChunkCount,
                                Double topScore,
                                Integer ttfbMs,
                                int costMs) {
}
''')

# ======================================================== 6 OnlineEvalSampler
w(CHAT / "app/eval/OnlineEvalSampler.java", r'''package com.fintech.rag.chat.app.eval;

import com.fintech.rag.api.dto.common.EvalMetric;
import com.fintech.rag.api.dto.common.EvalSource;
import com.fintech.rag.common.observability.RagOutcome;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.List;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;

/**
 * 在线抽样评估器 —— 把「线上真实回答」变成质量趋势数据。
 *
 * <p><b>两条硬约束</b>：</p>
 * <ol>
 *   <li><b>绝不阻塞回答</b>：抽样与评分都发生在回答已经交付之后，走独立有界队列；
 *       队列满时<b>直接丢弃样本</b>而不是等待 —— 评估样本丢十条规定无所谓，
 *       拖慢用户回答一条都不行；</li>
 *   <li><b>不采集文本</b>：本类只基于结构化链路事实算分，不读取问答原文、不调用大模型，
 *       因此可以在生产环境长期开启而不引入合规风险与额外推理成本。</li>
 * </ol>
 *
 * <p><b>骨架阶段的指标选择（重要）</b>：只启用「无需裁判模型即可计算」的指标。
 * {@code FAITHFULNESS} / {@code ANSWER_RELEVANCY} / {@code HALLUCINATION} 需要
 * LLM-as-judge，若此时强行用规则凑一个假分数，质量看板会比没有看板更危险 ——
 * 因为它会让人误以为幻觉已被监控。宁可空着，也不要假数据。</p>
 *
 * <p><b>代理指标的诚实说明</b>：{@code CONTEXT_PRECISION} 在业界标准定义里
 * 依赖「哪些片段真正支撑了答案」的判定，本类用「引用数 / 召回数」近似。
 * 近似值方向的单调性是对的（召回一堆没用上的片段必然拉低该值），
 * 因此适合看趋势，<b>不适合用于对外的精确质量结论</b>。</p>
 *
 * @author rag-platform
 */
@Component
public class OnlineEvalSampler {

    private static final Logger log = LoggerFactory.getLogger(OnlineEvalSampler.class);

    private final EvalProperties properties;
    private final LlmEvalScoreAppService evalScoreAppService;
    private final ExecutorService executor;
    private final AtomicLong offered = new AtomicLong();
    private final AtomicLong rejected = new AtomicLong();
    private final AtomicLong sampled = new AtomicLong();

    public OnlineEvalSampler(EvalProperties properties, LlmEvalScoreAppService evalScoreAppService) {
        this.properties = properties;
        this.evalScoreAppService = evalScoreAppService;
        this.executor = new ThreadPoolExecutor(
                1, Math.max(1, properties.getMaxConcurrent()),
                60L, TimeUnit.SECONDS,
                new ArrayBlockingQueue<>(256),
                runnable -> {
                    Thread thread = new Thread(runnable, "rag-online-eval");
                    thread.setDaemon(true);
                    return thread;
                },
                // 队列满 = 直接丢弃样本。评估丢样本无害，阻塞问答有害
                new ThreadPoolExecutor.DiscardPolicy());
    }

    /**
     * 尝试抽样评估（非阻塞，调用后立即返回）。
     *
     * <p>调用时机：回答已交付用户之后。放在交付前会引入不必要的耦合：
     * 一旦评估逻辑抛异常，回答可能被牵连失败。</p>
     */
    public void trySample(EvalSampleContext context) {
        if (context == null || !properties.isOnlineEnabled()) {
            return;
        }
        offered.incrementAndGet();
        if (!hit(context)) {
            return;
        }
        try {
            executor.execute(() -> evaluate(context));
        } catch (Exception ex) {
            rejected.incrementAndGet();
            log.debug("在线评估任务提交失败（已丢弃样本）", ex);
        }
    }

    /** 抽样判定：按采样率随机命中；错误与空召回必抽 —— 这两类样本最有诊断价值 */
    private boolean hit(EvalSampleContext context) {
        if (isDiagnostic(context.answerType())) {
            return true;
        }
        double rate = properties.getSampleRate() == null ? 0.0 : properties.getSampleRate().doubleValue();
        return Math.random() < rate;
    }

    private boolean isDiagnostic(String answerType) {
        return RagOutcome.NO_HIT.name().equals(answerType) || RagOutcome.ERROR.name().equals(answerType);
    }

    // ------------------------------------------------------------------ 评分
    private void evaluate(EvalSampleContext context) {
        try {
            sampled.incrementAndGet();
            for (String metricCode : properties.getManualMetrics()) {
                EvalMetric metric;
                try {
                    metric = EvalMetric.of(metricCode);
                } catch (IllegalArgumentException ex) {
                    log.warn("rag.eval.manual-metrics 含非法指标码 {}，已跳过", metricCode);
                    continue;
                }
                if (!metric.isComputableWithoutJudge()) {
                    // 防呆：配置里把需要裁判模型的指标打开了也不执行，避免产出假分数
                    log.warn("指标 {} 需要 LLM-as-judge，当前版本不计算（见 OnlineEvalSampler 类注释）",
                            metric.name());
                    continue;
                }
                BigDecimal score = compute(metric, context);
                if (score == null) {
                    continue;
                }
                evalScoreAppService.record(new EvalScoreCommand(
                        context.traceId(), context.messageId(), context.conversationId(),
                        null, EvalSource.ONLINE, proxyJudgeName(),
                        context.promptVersion(), metric.name(), score, null,
                        buildReason(metric, context), null));
            }
        } catch (Exception ex) {
            // 评估失败绝不能冒泡：它跑在异步线程里，冒泡只会变成一个无人处理的堆栈
            log.warn("在线评估执行失败 traceId={}", context.traceId(), ex);
        }
    }

    /** 代理指标计算。返回 null 表示本次样本无法计算该指标（不写假值） */
    private BigDecimal compute(EvalMetric metric, EvalSampleContext context) {
        return switch (metric) {
            case CITATION_COVERAGE -> citationCoverage(context);
            case CONTEXT_PRECISION -> contextPrecision(context);
            default -> null;
        };
    }

    /**
     * 引用覆盖率 = 引用数 / 期望引用数。
     *
     * <p>期望引用数取「召回片段数的下界」与 5 的较小值，且至少为 1：
     * 召回到 8 段只引 1 段，不应算满分；而召回到 1 段引 1 段，就是合理的满分。</p>
     */
    private BigDecimal citationCoverage(EvalSampleContext context) {
        if (!RagOutcome.ANSWERED.name().equals(context.answerType())) {
            // 空召回 / 护栏拦截 / 出错时，谈引用覆盖率没有意义，不写分
            return null;
        }
        int expected = Math.min(Math.max(context.chunkCount(), 1), 5);
        BigDecimal raw = BigDecimal.valueOf(context.citationCount())
                .divide(BigDecimal.valueOf(expected), 4, RoundingMode.HALF_UP);
        return clamp(raw);
    }

    /** 上下文精确率（代理）＝ 被引用的片段数 / 召回片段数。召回一堆没用上的片段会拉低此值 */
    private BigDecimal contextPrecision(EvalSampleContext context) {
        if (context.chunkCount() <= 0) {
            // 零召回时该指标无定义，写 0 会被误读成「召回质量极差」，宁可留空
            return null;
        }
        BigDecimal raw = BigDecimal.valueOf(context.citationCount())
                .divide(BigDecimal.valueOf(context.chunkCount()), 4, RoundingMode.HALF_UP);
        return clamp(raw);
    }

    private BigDecimal clamp(BigDecimal value) {
        if (value.compareTo(BigDecimal.ZERO) < 0) {
            return BigDecimal.ZERO;
        }
        return value.compareTo(BigDecimal.ONE) > 0 ? BigDecimal.ONE : value;
    }

    /**
     * 代理指标的「裁判」标识。
     *
     * <p>这里刻意不写死成真实模型名：分数由规则算出，若写成
     * {@code gpt-4o-mini} 会让后续按 judge_model 的归因分析失真 ——
     * 看起来是模型评的，其实是规则算的。写 {@code rule-proxy} 保持诚实。</p>
     */
    private String proxyJudgeName() {
        return "rule-proxy";
    }

    /** 评分理由：只写链路事实，绝不写问答原文 */
    private String buildReason(EvalMetric metric, EvalSampleContext context) {
        List<String> facts = List.of(
                metric.name(),
                "answerType=" + context.answerType(),
                "citations=" + context.citationCount(),
                "chunks=" + context.chunkCount(),
                "rawChunks=" + context.rawChunkCount(),
                "topScore=" + context.topScore(),
                "costMs=" + context.costMs());
        return String.join(" ", facts);
    }

    /** 观测用计数（可挂到 actuator / 指标，便于确认「抽样真的在跑」） */
    public long offeredCount() {
        return offered.get();
    }

    public long sampledCount() {
        return sampled.get();
    }

    public long rejectedCount() {
        return rejected.get();
    }
}
''')

# ======================================================== 7 FeedbackController
w(CHAT / "api/controller/FeedbackController.java", r'''package com.fintech.rag.chat.api.controller;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.fintech.rag.api.dto.chat.FeedbackRequest;
import com.fintech.rag.chat.app.metric.ChatPipelineMetrics;
import com.fintech.rag.chat.domain.model.AnswerFeedback;
import com.fintech.rag.chat.domain.model.ChatMessage;
import com.fintech.rag.chat.infra.persistence.mapper.AnswerFeedbackMapper;
import com.fintech.rag.chat.infra.persistence.mapper.ChatMessageMapper;
import com.fintech.rag.common.context.RequestContext;
import com.fintech.rag.common.core.R;
import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import com.fintech.rag.common.observability.ContentSanitizer;
import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 答案反馈接口。
 *
 * <p><b>本接口是「按 traceId 回放」的常规入口</b>：用户点踩时前端只传 messageId，
 * 后端据此反查该条消息的 traceId 并返回给运营侧 —— 用户不需要理解什么是 traceId，
 * 但运营点一下就能跳到完整链路。这是把可观测能力「产品化」的关键一步：
 * 链路数据只有能被非工程角色用上，才真正解决定位效率问题。</p>
 *
 * <p><b>防刷分</b>：同一主体对同一消息只保留一条反馈（唯一键 uk_message_subject），
 * 重复提交走更新。否则「点赞率」这个指标可以被一个人刷到任意数值。</p>
 *
 * @author rag-platform
 */
@RestController
@RequestMapping("/api/ai")
public class FeedbackController {

    private static final Logger log = LoggerFactory.getLogger(FeedbackController.class);

    private static final long DEFAULT_TENANT_ID = 0L;
    private static final String STATUS_PENDING = "PENDING";

    private final AnswerFeedbackMapper feedbackMapper;
    private final ChatMessageMapper messageMapper;
    private final ChatPipelineMetrics metrics;
    private final ContentSanitizer sanitizer;

    public FeedbackController(AnswerFeedbackMapper feedbackMapper,
                              ChatMessageMapper messageMapper,
                              ChatPipelineMetrics metrics,
                              ContentSanitizer sanitizer) {
        this.feedbackMapper = feedbackMapper;
        this.messageMapper = messageMapper;
        this.metrics = metrics;
        this.sanitizer = sanitizer;
    }

    /**
     * 提交反馈。
     *
     * @return 含 traceId 的结果：前端可据此展示「已记录，可随时复盘」
     */
    @PostMapping("/feedback")
    public R<Map<String, Object>> feedback(@Valid @RequestBody FeedbackRequest request) {
        if (!request.isValidVote()) {
            throw BizException.of(ErrorCode.PARAM_INVALID, "反馈类型只能是 LIKE 或 DISLIKE");
        }

        Long messageId = parseLong(request.messageId());
        if (messageId == null) {
            throw BizException.of(ErrorCode.PARAM_INVALID, "消息ID非法");
        }

        // 反查消息：既拿到 traceId（回放钥匙），又校验消息确实存在
        ChatMessage message = messageMapper.selectById(messageId);
        if (message == null) {
            throw BizException.of(ErrorCode.PARAM_INVALID, "消息不存在或已删除");
        }

        String subjectType = subjectTypeOf();
        String subjectId = RequestContext.currentSubjectId();
        String vote = request.vote().toUpperCase(java.util.Locale.ROOT);

        AnswerFeedback existing = feedbackMapper.selectOne(Wrappers.<AnswerFeedback>lambdaQuery()
                .eq(AnswerFeedback::getMessageId, messageId)
                .eq(AnswerFeedback::getSubjectId, subjectId)
                .last("limit 1"));

        if (existing == null) {
            AnswerFeedback entity = new AnswerFeedback();
            entity.setTenantId(DEFAULT_TENANT_ID);
            entity.setMessageId(messageId);
            entity.setConversationId(message.getConversationId());
            entity.setSubjectType(subjectType);
            entity.setSubjectId(subjectId);
            entity.setVote(vote);
            entity.setReasonCode(blankToNull(request.reasonCode()));
            entity.setComment(sanitizer.mask(blankToNull(request.comment())));
            entity.setHandleStatus(STATUS_PENDING);
            feedbackMapper.insert(entity);
        } else {
            existing.setVote(vote);
            existing.setReasonCode(blankToNull(request.reasonCode()));
            existing.setComment(sanitizer.mask(blankToNull(request.comment())));
            // 用户改了反馈内容，处理状态退回待处理：此前若有运营已处理，结论已不适用
            existing.setHandleStatus(STATUS_PENDING);
            feedbackMapper.updateById(existing);
        }

        metrics.recordFeedback(vote, blankToNull(request.reasonCode()));

        log.info("收到答案反馈 messageId={} vote={} reasonCode={} traceId={}",
                messageId, vote, request.reasonCode(), message.getTraceId());

        return R.ok(Map.of(
                "messageId", request.messageId(),
                "vote", vote,
                // 把 traceId 回带给调用方：运营端凭此一键回放本次回答
                "traceId", message.getTraceId() == null ? "" : message.getTraceId(),
                "replayPath", "/api/ai/replay/" + (message.getTraceId() == null ? "" : message.getTraceId())));
    }

    private String subjectTypeOf() {
        return RequestContext.currentSource() == com.fintech.rag.common.context.RequestSource.DMZ_WEB
                ? "USER" : "APP";
    }

    private Long parseLong(String value) {
        try {
            return Long.parseLong(value);
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    private String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value;
    }
}
''')

# ======================================================== 8 EvalController
w(CHAT / "api/controller/EvalController.java", r'''package com.fintech.rag.chat.api.controller;

import com.fintech.rag.api.dto.common.EvalMetric;
import com.fintech.rag.api.dto.common.EvalSource;
import com.fintech.rag.api.dto.eval.ManualEvalRequest;
import com.fintech.rag.chat.app.eval.EvalScoreCommand;
import com.fintech.rag.chat.app.eval.LlmEvalScoreAppService;
import com.fintech.rag.chat.domain.model.LlmEvalScore;
import com.fintech.rag.common.context.RequestContext;
import com.fintech.rag.common.core.R;
import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.math.BigDecimal;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 人工评估接口 —— 运营 / 业务专家对具体回答打分。
 *
 * <p><b>准入</b>：只能由内网应用（AppKey + HMAC 签名）调用，由
 * {@code SourceAuthInterceptor} 强制 —— 不额外写角色判断，因为
 * 「内网应用」本身就是受控集合，而终端用户绝不能给自己刷分。</p>
 *
 * <p><b>为什么人工评分值得单独做一个接口</b>：LLM-as-judge 与规则指标都无法回答
 * 「这个答案业务上到底对不对」。人工评分是<b>黄金集的唯一来源</b>，
 * 也是争议样本定调的手段 —— 它同时也是校准自动评估器的基准。</p>
 *
 * @author rag-platform
 */
@RestController
@RequestMapping("/api/ai")
public class EvalController {

    private final LlmEvalScoreAppService evalScoreAppService;

    public EvalController(LlmEvalScoreAppService evalScoreAppService) {
        this.evalScoreAppService = evalScoreAppService;
    }

    /**
     * 人工评分。
     *
     * <p>不接收 traceId 之外的「被评估内容」——评分对象是库里已有的那条回答，
     * 由 messageId / traceId 定位，避免调用方通过本接口塞入任意文本。</p>
     */
    @PostMapping("/eval/manual")
    public R<Map<String, Object>> manual(@Valid @RequestBody ManualEvalRequest request) {
        if (request.traceId() == null && request.messageId() == null) {
            throw BizException.of(ErrorCode.PARAM_INVALID, "traceId 与 messageId 至少提供一个");
        }

        // 指标白名单在此先校验一次，让错误在参数层暴露（写入入口还会再校验一次，双保险）
        EvalMetric metric;
        try {
            metric = EvalMetric.of(request.metricCode());
        } catch (IllegalArgumentException ex) {
            throw BizException.of(ErrorCode.PARAM_INVALID, ex.getMessage());
        }

        LlmEvalScore saved = evalScoreAppService.record(new EvalScoreCommand(
                request.traceId(),
                parseLong(request.messageId()),
                null,
                null,
                EvalSource.MANUAL,
                null,
                null,
                metric.name(),
                request.score(),
                null,
                request.reason(),
                RequestContext.currentSubjectId()));

        Map<String, Object> data = new LinkedHashMap<>();
        data.put("scoreId", saved.getId() == null ? null : String.valueOf(saved.getId()));
        data.put("metricCode", saved.getMetricCode());
        data.put("score", saved.getScore() == null ? null : saved.getScore().toPlainString());
        data.put("threshold", saved.getThreshold() == null ? null : saved.getThreshold().toPlainString());
        data.put("passed", saved.getPassed());
        data.put("scoreScale", saved.getScoreScale());
        return R.ok(data);
    }

    private Long parseLong(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        try {
            return Long.parseLong(value);
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    /** 保留给未来「批量导入人工评分」使用的量纲常量，避免调用方各写各的 */
    public static final BigDecimal SCORE_SCALE_ONE = BigDecimal.ONE;
}
''')

# ======================================================== 9 application.yml（改）
# 与 S16 采用同一套「整节重写」策略，理由见 gen_s16_replay.py 内的说明：
# 增量插入会把 observability 的注释块与它的键拆散，人读起来完全错乱。
# 本脚本先写入「不含 replay」的版本；S16 后跑时会把 replay 块补上（顺序仍是
# chat / server / eval / replay / observability）。
RAG_SECTION_NO_REPLAY = """rag:
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
  # ---------------------------------------------------------------------------
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

yml_path = CHAT_RES / "application.yml"
yml_text = yml_path.read_text(encoding="utf-8")
match = re.search(r'(?ms)^rag:.*?(?=^management:)', yml_text)
if match:
    yml_path.write_text(yml_text[:match.start()] + RAG_SECTION_NO_REPLAY + yml_text[match.end():],
                        encoding="utf-8", newline="\n")
    w(yml_path, yml_path.read_text(encoding="utf-8"))
    print("   （rag 节已整节规范化；replay 块由 gen_s16_replay.py 写入）")
else:
    print("!  未在 application.yml 中找到 rag: 节，跳过")

print("---- total:", len(written))
