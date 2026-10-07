package com.fintech.rag.platform.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Duration;

/**
 * 平台安全配置。
 *
 * @author rag-platform
 */
@ConfigurationProperties(prefix = "rag.security")
public class PlatformSecurityProperties {

    /** AES-256 主密钥（Base64，32 字节），用于加解密 AppSecret / API Key */
    private String aesKey;

    /** DMZ 网关网段白名单，用于校验「携带来源标识的请求是否真的来自网关」 */
    private java.util.List<String> trustedGatewayCidrs = new java.util.ArrayList<>();

    private Jwt jwt = new Jwt();

    private AppSign appSign = new AppSign();

    public static class Jwt {

        private String issuer = "rag-platform";

        private String secret;

        private Duration accessTokenTtl = Duration.ofHours(2);

        private Duration refreshTokenTtl = Duration.ofHours(8);

        public String getIssuer() {
            return issuer;
        }

        public void setIssuer(String issuer) {
            this.issuer = issuer;
        }

        public String getSecret() {
            return secret;
        }

        public void setSecret(String secret) {
            this.secret = secret;
        }

        public Duration getAccessTokenTtl() {
            return accessTokenTtl;
        }

        public void setAccessTokenTtl(Duration accessTokenTtl) {
            this.accessTokenTtl = accessTokenTtl;
        }

        public Duration getRefreshTokenTtl() {
            return refreshTokenTtl;
        }

        public void setRefreshTokenTtl(Duration refreshTokenTtl) {
            this.refreshTokenTtl = refreshTokenTtl;
        }
    }

    public static class AppSign {

        /** 允许的时间戳偏差窗口 */
        private Duration timestampWindow = Duration.ofMinutes(5);

        /** nonce 记忆时长，应 ≥ 时间戳窗口，否则窗口内仍可重放 */
        private Duration nonceTtl = Duration.ofMinutes(10);

        public Duration getTimestampWindow() {
            return timestampWindow;
        }

        public void setTimestampWindow(Duration timestampWindow) {
            this.timestampWindow = timestampWindow;
        }

        public Duration getNonceTtl() {
            return nonceTtl;
        }

        public void setNonceTtl(Duration nonceTtl) {
            this.nonceTtl = nonceTtl;
        }
    }

    public String getAesKey() {
        return aesKey;
    }

    public void setAesKey(String aesKey) {
        this.aesKey = aesKey;
    }

    public java.util.List<String> getTrustedGatewayCidrs() {
        return trustedGatewayCidrs;
    }

    public void setTrustedGatewayCidrs(java.util.List<String> trustedGatewayCidrs) {
        this.trustedGatewayCidrs = trustedGatewayCidrs;
    }

    public Jwt getJwt() {
        return jwt;
    }

    public void setJwt(Jwt jwt) {
        this.jwt = jwt;
    }

    public AppSign getAppSign() {
        return appSign;
    }

    public void setAppSign(AppSign appSign) {
        this.appSign = appSign;
    }
}
