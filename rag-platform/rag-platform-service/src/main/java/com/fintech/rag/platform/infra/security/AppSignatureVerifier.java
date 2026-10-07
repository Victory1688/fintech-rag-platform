package com.fintech.rag.platform.infra.security;

import com.fintech.rag.api.dto.platform.AppSignVerifyRequest;
import com.fintech.rag.api.dto.platform.AppSignVerifyResult;
import com.fintech.rag.common.util.AesCiphers;
import com.fintech.rag.common.util.HmacSignatures;
import com.fintech.rag.platform.config.PlatformSecurityProperties;
import com.fintech.rag.platform.domain.model.AppCredential;
import com.fintech.rag.platform.infra.persistence.repository.AppCredentialRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.time.Duration;

/**
 * 内网应用签名校验器 —— <b>第二套鉴权体系的判定内核</b>。
 *
 * <p>校验顺序（任一失败即拒绝，顺序不可调整）：</p>
 * <ol>
 *   <li>凭证存在且启用未过期</li>
 *   <li>时间戳在允许窗口内（默认 ±5 分钟）</li>
 *   <li>调用方 IP 在白名单内（若配置）</li>
 *   <li>nonce 未被使用过（防重放）</li>
 *   <li>HMAC-SHA256 签名匹配（常量时间比较）</li>
 * </ol>
 *
 * <p>为什么先查 nonce 再验签？可以在签名爆破前先挡掉重放请求；
 * 但要注意 nonce 已被占用而签名不匹配时，该 nonce 就废了——
 * 这是可接受的，因为合法调用方每次都会生成新 nonce。</p>
 *
 * @author rag-platform
 */
@Component
public class AppSignatureVerifier {

    private static final Logger log = LoggerFactory.getLogger(AppSignatureVerifier.class);

    private final AppCredentialRepository repository;
    private final NonceReplayGuard nonceReplayGuard;
    private final PlatformSecurityProperties properties;

    public AppSignatureVerifier(AppCredentialRepository repository,
                                NonceReplayGuard nonceReplayGuard,
                                PlatformSecurityProperties properties) {
        this.repository = repository;
        this.nonceReplayGuard = nonceReplayGuard;
        this.properties = properties;
    }

    public AppSignVerifyResult verify(AppSignVerifyRequest request) {
        AppCredential credential = repository.findActive(request.appId());
        if (credential == null) {
            log.warn("应用凭证不存在或已停用 appId={}", request.appId());
            return AppSignVerifyResult.rejected("应用不存在或已停用");
        }

        if (!withinTimeWindow(request.timestamp())) {
            return AppSignVerifyResult.rejected("请求时间戳超出允许窗口");
        }

        if (!ipAllowed(credential.getIpWhitelist(), request.clientIp())) {
            log.warn("调用方 IP 不在白名单 appId={} ip={}", request.appId(), request.clientIp());
            return AppSignVerifyResult.rejected("调用方 IP 不在白名单");
        }

        Duration nonceTtl = properties.getAppSign().getNonceTtl();
        if (!nonceReplayGuard.tryAcquire(request.appId(), request.nonce(), nonceTtl)) {
            return AppSignVerifyResult.rejected("请求已被重复提交");
        }

        String secret;
        try {
            secret = AesCiphers.decrypt(credential.getAppSecretEnc(), properties.getAesKey());
        } catch (Exception ex) {
            // 解密失败通常意味着 AES 密钥配置错误，属于启动期问题，必须告警
            log.error("AppSecret 解密失败 appId={}", request.appId(), ex);
            return AppSignVerifyResult.rejected("服务端密钥配置异常");
        }

        boolean matched = HmacSignatures.verify(
                secret,
                request.method(),
                request.path(),
                request.timestamp(),
                request.nonce(),
                request.bodySha256(),
                request.signature());

        if (!matched) {
            log.warn("应用签名不匹配 appId={} path={}", request.appId(), request.path());
            return AppSignVerifyResult.rejected("应用签名校验失败");
        }

        return new AppSignVerifyResult(true, null,
                credential.getAppId(), credential.getAppName(),
                credential.getQpsLimit(), credential.getDailyLimit(),
                credential.getIpWhitelist());
    }

    private boolean withinTimeWindow(String timestamp) {
        try {
            long ts = Long.parseLong(timestamp);
            long diff = Math.abs(System.currentTimeMillis() - ts);
            return diff <= properties.getAppSign().getTimestampWindow().toMillis();
        } catch (NumberFormatException ex) {
            return false;
        }
    }

    private boolean ipAllowed(String whitelist, String clientIp) {
        if (whitelist == null || whitelist.isBlank()) {
            return true;
        }
        if (clientIp == null || clientIp.isBlank()) {
            return false;
        }
        for (String pattern : whitelist.split(",")) {
            String trimmed = pattern.trim();
            if (trimmed.isEmpty()) {
                continue;
            }
            if (trimmed.endsWith("*")) {
                if (clientIp.startsWith(trimmed.substring(0, trimmed.length() - 1))) {
                    return true;
                }
            } else if (trimmed.equals(clientIp)) {
                return true;
            }
        }
        return false;
    }
}
