package com.fintech.rag.chat.app.eval;

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
