package com.fintech.rag.api.server.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.ArrayList;
import java.util.List;

/**
 * 服务端来源鉴权配置。
 *
 * <pre>
 * rag:
 *   server:
 *     auth:
 *       enabled: true                  # 是否启用（默认关闭，避免影响引入 SDK 的业务方）
 *       public-paths: [...]            # 完全放开
 *       gateway-only-paths: [...]      # 仅允许网关访问（无需应用签名，但仍校验网关网段）
 *       trusted-gateway-cidrs: [...]   # 网关网段白名单
 *       gateway-signature-enabled: true # 启用网关签名强校验（容器环境推荐）
 *       gateway-sign-secret: xxx
 * </pre>
 *
 * <p><b>安全默认值：</b>若既未配置 {@code trusted-gateway-cidrs} 又未启用网关签名，
 * 则任何携带 {@code X-Request-Source} 的请求都会被拒绝。宁可启动后调不通，
 * 也不能默认信任一个可被伪造的请求头。</p>
 *
 * @author rag-platform
 */
@ConfigurationProperties(prefix = "rag.server.auth")
public class SourceAuthProperties {

    private boolean enabled = false;

    private List<String> publicPaths = new ArrayList<>(List.of(
            "/actuator/**", "/doc.html", "/v3/api-docs/**", "/error", "/favicon.ico"));

    private List<String> gatewayOnlyPaths = new ArrayList<>();

    private List<String> trustedGatewayCidrs = new ArrayList<>();

    private boolean gatewaySignatureEnabled = false;

    private String gatewaySignSecret;

    /** 应用签名时间戳窗口（毫秒） */
    private long timestampWindowMs = 5 * 60 * 1000L;

    public boolean isEnabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }

    public List<String> getPublicPaths() {
        return publicPaths;
    }

    public void setPublicPaths(List<String> publicPaths) {
        this.publicPaths = publicPaths;
    }

    public List<String> getGatewayOnlyPaths() {
        return gatewayOnlyPaths;
    }

    public void setGatewayOnlyPaths(List<String> gatewayOnlyPaths) {
        this.gatewayOnlyPaths = gatewayOnlyPaths;
    }

    public List<String> getTrustedGatewayCidrs() {
        return trustedGatewayCidrs;
    }

    public void setTrustedGatewayCidrs(List<String> trustedGatewayCidrs) {
        this.trustedGatewayCidrs = trustedGatewayCidrs;
    }

    public boolean isGatewaySignatureEnabled() {
        return gatewaySignatureEnabled;
    }

    public void setGatewaySignatureEnabled(boolean gatewaySignatureEnabled) {
        this.gatewaySignatureEnabled = gatewaySignatureEnabled;
    }

    public String getGatewaySignSecret() {
        return gatewaySignSecret;
    }

    public void setGatewaySignSecret(String gatewaySignSecret) {
        this.gatewaySignSecret = gatewaySignSecret;
    }

    public long getTimestampWindowMs() {
        return timestampWindowMs;
    }

    public void setTimestampWindowMs(long timestampWindowMs) {
        this.timestampWindowMs = timestampWindowMs;
    }
}
