package com.fintech.rag.api.dto.common;

import java.math.BigDecimal;

/**
 * 评估指标白名单 —— {@code t_llm_eval_score.metric_code} 的合法取值。
 *
 * <p><b>为什么必须是白名单而不是自由字符串</b>：指标码是看板的分组维度，
 * 一旦允许业务方随手写（{@code FAITHFULNESS} / {@code faithfulness} / {@code 忠实度} 三种写法并存），
 * 同一个指标会被拆成三条曲线，且历史数据无法重算。校验放在写入入口，
 * 让错误在写入时就失败，而不是在出质量报告时才发现对不上。</p>
 *
 * <p><b>量纲（scoreScale）</b>：统一为 1，即所有分数都归一到 0~1，阈值也用 0~1 表达。
 * 曾经考虑过 1~5 分制，但五级分值在跨指标聚合时无法直接比较，且容易被误当成百分制。</p>
 *
 * <p><b>canComputeWithoutJudge</b>：标记该指标是否「无需大模型即可计算」。
 * 骨架阶段只启用可算指标，需要裁判模型的指标必须等 LLM-as-judge 接入后再开启 ——
 * 这样评估链路当天就能跑起来，不必等模型接入，也不会用假分数骗自己。</p>
 *
 * @author rag-platform
 */
public enum EvalMetric {

    /** 忠实度：回答是否完全由召回片段支撑（需裁判模型，防幻觉的核心指标） */
    FAITHFULNESS(false, "0.85"),

    /** 答案相关性：回答是否切题（需裁判模型） */
    ANSWER_RELEVANCY(false, "0.80"),

    /** 上下文精确率：召回片段中真正被用上的比例（可由引用数/召回数近似） */
    CONTEXT_PRECISION(true, "0.50"),

    /** 上下文召回率：应召回的内容是否都召回（需标注集） */
    CONTEXT_RECALL(false, "0.80"),

    /** 幻觉率：回答中无出处的事实性陈述比例（越低越好，需裁判模型） */
    HALLUCINATION(false, "0.10"),

    /** 引用覆盖率：有引用支撑的句子占比（可由正文 [n] 标记与引用列表算得） */
    CITATION_COVERAGE(true, "0.90"),

    /** 有用性：人工主观评分 */
    HELPFULNESS(false, "0.80");

    private final boolean computableWithoutJudge;
    private final BigDecimal defaultThreshold;

    EvalMetric(boolean computableWithoutJudge, String defaultThreshold) {
        this.computableWithoutJudge = computableWithoutJudge;
        this.defaultThreshold = new BigDecimal(defaultThreshold);
    }

    /** 是否无需裁判模型即可计算（骨架阶段仅启用这类指标） */
    public boolean isComputableWithoutJudge() {
        return computableWithoutJudge;
    }

    /** 默认门禁阈值（0~1）。低于阈值即 passed=0，用于发版门禁与告警 */
    public BigDecimal getDefaultThreshold() {
        return defaultThreshold;
    }

    /** 本指标是否为「越低越好」（幻觉类）。门禁判定方向相反，写错会把好模型判失败 */
    public boolean isLowerBetter() {
        return this == HALLUCINATION;
    }

    /** 按指标码解析；非法值抛异常，由写入入口转为业务错误码 */
    public static EvalMetric of(String code) {
        if (code != null) {
            for (EvalMetric metric : values()) {
                if (metric.name().equalsIgnoreCase(code.trim())) {
                    return metric;
                }
            }
        }
        throw new IllegalArgumentException("非法的评估指标码: " + code + "（合法取值见 EvalMetric）");
    }
}
