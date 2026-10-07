package com.fintech.rag.common.observability;

/**
 * 可观测数据采集档位 —— <b>金融场景的合规开关</b>。
 *
 * <p>顺序即敏感度，禁止跨档跳级开启。生产默认 {@link #METRICS_ONLY}。</p>
 *
 * @author rag-platform
 */
public enum ContentLevel {

    /** 只上报 span 结构与数值属性，绝不回传 prompt / 答案 / 召回片段（生产默认） */
    METRICS_ONLY(0),

    /** 额外上报内容指纹（sha256 前 16 位）与长度，不落原文 */
    FINGERPRINT(1),

    /** 上报脱敏后的 prompt / 答案 / 召回片段（正则 + 掩码） */
    REDACTED_CONTENT(2),

    /** 上报原文 —— <b>仅限开发环境，生产必须禁用</b> */
    FULL_CONTENT(3);

    private final int rank;

    ContentLevel(int rank) {
        this.rank = rank;
    }

    public int rank() {
        return rank;
    }

    /** 是否允许携带任何形式的内容（含指纹） */
    public boolean allowsAnyContent() {
        return rank >= FINGERPRINT.rank;
    }

    /** 是否允许携带真实文本（已脱敏或原文） */
    public boolean allowsText() {
        return rank >= REDACTED_CONTENT.rank;
    }

    /** 是否为原文档位（生产禁用） */
    public boolean isPlainText() {
        return rank >= FULL_CONTENT.rank;
    }
}
