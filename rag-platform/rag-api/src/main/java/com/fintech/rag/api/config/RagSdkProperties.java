package com.fintech.rag.api.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * 内网业务方接入 SDK 配置。
 *
 * <pre>
 * rag:
 *   sdk:
 *     enabled: true
 *     app-id: biz_credit_apply
 *     app-secret: ${RAG_APP_SECRET}
 * </pre>
 *
 * <p>密钥禁止硬编码到配置文件提交到仓库，必须走环境变量或配置中心加密配置。</p>
 *
 * @author rag-platform
 */
@ConfigurationProperties(prefix = "rag.sdk")
public class RagSdkProperties {

    /** 是否启用 SDK 签名拦截器 */
    private boolean enabled = false;

    /** 应用 ID */
    private String appId;

    /** 应用密钥 */
    private String appSecret;

    public boolean isEnabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }

    public String getAppId() {
        return appId;
    }

    public void setAppId(String appId) {
        this.appId = appId;
    }

    public String getAppSecret() {
        return appSecret;
    }

    public void setAppSecret(String appSecret) {
        this.appSecret = appSecret;
    }
}
