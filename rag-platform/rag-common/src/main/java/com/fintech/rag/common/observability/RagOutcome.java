package com.fintech.rag.common.observability;

/**
 * 业务结果归因 —— 质量看板与告警的核心维度。
 *
 * <p>为什么单列一个枚举：只看「成功率」会把「无据不答」也算成成功，
 * 从而掩盖「知识库覆盖不足」这个真问题。必须按结果分类统计。</p>
 *
 * @author rag-platform
 */
public enum RagOutcome {

    /** 正常作答（检索命中且通过护栏） */
    ANSWERED,

    /** 检索无命中 —— 未调用大模型（「无据不答」） */
    ABSTAINED,

    /** 被护栏拦截 */
    GUARDRAIL_BLOCKED,

    /** 链路异常（检索失败 / 模型失败 / 超时） */
    ERROR
}
