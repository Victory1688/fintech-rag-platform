package com.fintech.rag.api.dto.common;

/**
 * 答案护栏命中类型。
 *
 * @author rag-platform
 */
public enum GuardrailType {

    /** 空召回：相似度全部低于阈值 */
    NO_HIT,

    /** 引用缺失：正文有 [n] 标记但无对应引用 */
    MISSING_CITATION,

    /** 敏感信息：身份证 / 卡号 / 手机号等 */
    SENSITIVE,

    /** 跨知识库越权：引用了未授权知识库内容 */
    CROSS_KB,

    /** 无引用数值：出现利率/额度等数值但无出处 */
    UNSUPPORTED_NUMERIC
}
