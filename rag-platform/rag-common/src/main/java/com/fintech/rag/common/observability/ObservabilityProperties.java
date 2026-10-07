package com.fintech.rag.common.observability;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * 可观测配置（可由 Nacos 动态下发，无需重启）。
 *
 * <p><b>默认值即生产安全值</b>：默认只上报指标、不回传任何内容。</p>
 *
 * @author rag-platform
 */
@ConfigurationProperties(prefix = "rag.observability")
public class ObservabilityProperties {

    /** 总开关。关闭后不上报 OTLP，但 Prometheus 指标不受影响 */
    private boolean enabled = true;

    /** 采集档位，生产默认 METRICS_ONLY */
    private ContentLevel contentLevel = ContentLevel.METRICS_ONLY;

    /**
     * 是否允许在 FULL_CONTENT 档位下运行。
     *
     * <p>这是防呆闸：即使有人把 content-level 配成 FULL_CONTENT，
     * 只要本开关为 false（默认），也会被降级为 REDACTED_CONTENT —— 防止运维误配导致原文出内网。</p>
     */
    private boolean allowPlainTextContent = false;

    /** 采集内容时单字段最大字符数（防止超长 Prompt 打爆上报通道） */
    private int maxContentChars = 2000;

    /** 是否记录召回片段文本（仅 REDACTED_CONTENT 及以上档位生效） */
    private boolean recordRetrievedChunks = false;

    /** 主体哈希盐值，必须走环境变量注入；为空时退化为不带盐的哈希（仅开发可用） */
    private String subjectHashSalt = "";

    /** 上游模型供应商标识，写入 gen_ai.provider.name（OpenAI 兼容协议下统一填 openai） */
    private String providerName = "openai";

    public boolean isEnabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }

    public ContentLevel getContentLevel() {
        return contentLevel;
    }

    public void setContentLevel(ContentLevel contentLevel) {
        this.contentLevel = contentLevel;
    }

    public boolean isAllowPlainTextContent() {
        return allowPlainTextContent;
    }

    public void setAllowPlainTextContent(boolean allowPlainTextContent) {
        this.allowPlainTextContent = allowPlainTextContent;
    }

    public int getMaxContentChars() {
        return maxContentChars;
    }

    public void setMaxContentChars(int maxContentChars) {
        this.maxContentChars = maxContentChars;
    }

    public boolean isRecordRetrievedChunks() {
        return recordRetrievedChunks;
    }

    public void setRecordRetrievedChunks(boolean recordRetrievedChunks) {
        this.recordRetrievedChunks = recordRetrievedChunks;
    }

    public String getSubjectHashSalt() {
        return subjectHashSalt;
    }

    public void setSubjectHashSalt(String subjectHashSalt) {
        this.subjectHashSalt = subjectHashSalt;
    }

    public String getProviderName() {
        return providerName;
    }

    public void setProviderName(String providerName) {
        this.providerName = providerName;
    }

    /**
     * 生效档位：叠加「防呆闸」后的实际档位。
     *
     * <p>业务代码一律调用本方法，<b>不要直接读 contentLevel</b>，
     * 否则防呆闸形同虚设。</p>
     */
    public ContentLevel effectiveContentLevel() {
        if (contentLevel == ContentLevel.FULL_CONTENT && !allowPlainTextContent) {
            return ContentLevel.REDACTED_CONTENT;
        }
        return contentLevel;
    }
}
