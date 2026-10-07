package com.fintech.rag.platform.infra.security;

import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import java.time.Duration;

/**
 * nonce 防重放守卫。
 *
 * <p>原理：同一 appId + nonce 在 TTL 窗口内只允许出现一次。
 * 即使攻击者截获了完整请求（含签名），也无法重复提交。</p>
 *
 * @author rag-platform
 */
@Component
public class NonceReplayGuard {

    private static final String KEY_PREFIX = "platform:nonce:";

    private final StringRedisTemplate redisTemplate;

    public NonceReplayGuard(StringRedisTemplate redisTemplate) {
        this.redisTemplate = redisTemplate;
    }

    /**
     * 占用 nonce。
     *
     * @return true 表示首次出现（放行），false 表示已重复（拒绝）
     */
    public boolean tryAcquire(String appId, String nonce, Duration ttl) {
        if (nonce == null || nonce.isBlank()) {
            return false;
        }
        Boolean ok = redisTemplate.opsForValue()
                .setIfAbsent(KEY_PREFIX + appId + ":" + nonce, "1", ttl);
        return Boolean.TRUE.equals(ok);
    }
}
