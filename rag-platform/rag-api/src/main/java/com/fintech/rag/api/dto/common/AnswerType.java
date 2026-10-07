package com.fintech.rag.api.dto.common;

/**
 * 答案类型。
 *
 * <p>{@link #NO_HIT} 与 {@link #GUARDRAIL_BLOCKED} 是金融场景的关键语义：
 * 它们表示「系统明确拒绝回答」，而不是「回答失败」，前端需要区别展示。</p>
 *
 * @author rag-platform
 */
public enum AnswerType {

    /** 正常基于知识库作答（含引用） */
    ANSWERED,

    /** 未召回到任何有效内容，未调用大模型 */
    NO_HIT,

    /** 触发出参护栏被拦截 */
    GUARDRAIL_BLOCKED,

    /** 系统错误 */
    ERROR
}
