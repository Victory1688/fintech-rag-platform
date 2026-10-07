package com.fintech.rag.platform.app.service;

import com.fintech.rag.api.dto.platform.AppSignVerifyRequest;
import com.fintech.rag.api.dto.platform.AppSignVerifyResult;
import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import com.fintech.rag.common.util.AesCiphers;
import com.fintech.rag.platform.config.PlatformSecurityProperties;
import com.fintech.rag.platform.domain.model.AppCredential;
import com.fintech.rag.platform.infra.persistence.repository.AppCredentialRepository;
import com.fintech.rag.platform.infra.security.AppSignatureVerifier;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.security.SecureRandom;
import java.time.LocalDateTime;
import java.util.Base64;

/**
 * 应用凭证应用服务。
 *
 * @author rag-platform
 */
@Service
public class AppCredentialAppService {

    private static final Logger log = LoggerFactory.getLogger(AppCredentialAppService.class);
    private static final SecureRandom RANDOM = new SecureRandom();

    private final AppSignatureVerifier verifier;
    private final AppCredentialRepository repository;
    private final PlatformSecurityProperties properties;

    public AppCredentialAppService(AppSignatureVerifier verifier,
                                   AppCredentialRepository repository,
                                   PlatformSecurityProperties properties) {
        this.verifier = verifier;
        this.repository = repository;
        this.properties = properties;
    }

    /** 验签（供各服务调用） */
    public AppSignVerifyResult verify(AppSignVerifyRequest request) {
        return verifier.verify(request);
    }

    /**
     * 创建应用凭证。
     *
     * <p><b>安全约定</b>：AppSecret 只在创建响应中返回一次明文，之后只存密文，
     * 任何接口都不允许再回显。</p>
     *
     * @return AppSecret 明文（仅此一次）
     */
    @Transactional(rollbackFor = Exception.class)
    public String create(String appId, String appName, String owner, Integer qpsLimit, Long dailyLimit) {
        String plainSecret = generateSecret();
        AppCredential credential = new AppCredential();
        credential.setTenantId(0L);
        credential.setAppId(appId);
        credential.setAppName(appName);
        credential.setAppSecretEnc(AesCiphers.encrypt(plainSecret, properties.getAesKey()));
        credential.setOwner(owner);
        credential.setQpsLimit(qpsLimit == null ? 20 : qpsLimit);
        credential.setDailyLimit(dailyLimit == null ? 100000L : dailyLimit);
        credential.setStatus(1);
        credential.setDeleted(0);
        repository.save(credential);
        log.info("创建应用凭证 appId={}", appId);
        return plainSecret;
    }

    /**
     * 密钥轮换：新密钥立即生效，旧凭证设置过期时间，形成并行窗口。
     *
     * @return 新的 AppSecret 明文（仅此一次）
     */
    @Transactional(rollbackFor = Exception.class)
    public String rotate(String appId, int graceHours) {
        AppCredential old = repository.findActive(appId);
        if (old == null) {
            throw BizException.of(ErrorCode.APP_DISABLED);
        }

        String plainSecret = generateSecret();
        old.setExpireAt(LocalDateTime.now().plusHours(graceHours));
        old.setStatus(1);
        repository.save(old);

        AppCredential fresh = new AppCredential();
        fresh.setTenantId(old.getTenantId());
        fresh.setAppId(appId);
        fresh.setAppName(old.getAppName());
        fresh.setAppSecretEnc(AesCiphers.encrypt(plainSecret, properties.getAesKey()));
        fresh.setOwner(old.getOwner());
        fresh.setQpsLimit(old.getQpsLimit());
        fresh.setDailyLimit(old.getDailyLimit());
        fresh.setIpWhitelist(old.getIpWhitelist());
        fresh.setStatus(1);
        fresh.setDeleted(0);
        repository.save(fresh);

        // 必须主动失效缓存，否则旧密钥在新实例上仍然可用
        repository.evict(appId);
        log.info("应用密钥轮换完成 appId={} graceHours={}", appId, graceHours);
        return plainSecret;
    }

    private String generateSecret() {
        byte[] bytes = new byte[32];
        RANDOM.nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }
}
