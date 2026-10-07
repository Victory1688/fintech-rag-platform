package com.fintech.rag.chat.app.eval;

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
