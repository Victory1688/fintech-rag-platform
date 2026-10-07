package com.fintech.rag.platform.infra.security;

import com.fintech.rag.api.dto.platform.UserTokenPayload;
import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import com.fintech.rag.platform.config.PlatformSecurityProperties;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Date;
import java.util.List;

/**
 * 用户令牌服务（JWT，HS256）。
 *
 * <p><b>JJWT 0.12.x API 注意事项：</b>{@code parserBuilder()} 已废弃，
 * 必须用 {@code Jwts.parser().verifyWith(key).build()}；HS256 的密钥长度
 * 必须 ≥ 32 字节，否则启动期即会抛 WeakKeyException。</p>
 *
 * @author rag-platform
 */
@Component
public class JwtTokenService {

    private static final String CLAIM_NAME = "name";
    private static final String CLAIM_DEPT = "deptId";
    private static final String CLAIM_SECRET_LEVEL = "secretLevel";
    private static final String CLAIM_ROLES = "roles";

    private final SecretKey key;
    private final PlatformSecurityProperties properties;

    public JwtTokenService(PlatformSecurityProperties properties) {
        this.properties = properties;
        byte[] secretBytes = properties.getJwt().getSecret().getBytes(StandardCharsets.UTF_8);
        if (secretBytes.length < 32) {
            throw new IllegalStateException("JWT 密钥长度不足 32 字节，HS256 不允许弱密钥，请检查 rag.security.jwt.secret 配置");
        }
        this.key = Keys.hmacShaKeyFor(secretBytes);
    }

    /** 签发访问令牌 */
    public String issueAccessToken(UserTokenPayload payload) {
        return issue(payload, properties.getJwt().getAccessTokenTtl().toMillis());
    }

    /** 签发刷新令牌 */
    public String issueRefreshToken(UserTokenPayload payload) {
        return issue(payload, properties.getJwt().getRefreshTokenTtl().toMillis());
    }

    private String issue(UserTokenPayload payload, long ttlMillis) {
        Instant now = Instant.now();
        return Jwts.builder()
                .subject(payload.userId())
                .issuer(properties.getJwt().getIssuer())
                .claim(CLAIM_NAME, payload.realName())
                .claim(CLAIM_DEPT, payload.deptId())
                .claim(CLAIM_SECRET_LEVEL, payload.secretLevel())
                .claim(CLAIM_ROLES, payload.roles())
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plusMillis(ttlMillis)))
                .signWith(key)
                .compact();
    }

    /**
     * 解析并校验令牌。
     *
     * @throws BizException 令牌非法或已过期
     */
    @SuppressWarnings("unchecked")
    public UserTokenPayload parse(String token) {
        if (token == null || token.isBlank()) {
            throw BizException.of(ErrorCode.TOKEN_INVALID);
        }
        try {
            Claims claims = Jwts.parser()
                    .verifyWith(key)
                    .requireIssuer(properties.getJwt().getIssuer())
                    .build()
                    .parseSignedClaims(token)
                    .getPayload();

            return new UserTokenPayload(
                    claims.getSubject(),
                    claims.get(CLAIM_NAME, String.class),
                    claims.get(CLAIM_DEPT, Long.class),
                    claims.get(CLAIM_SECRET_LEVEL, Integer.class),
                    claims.get(CLAIM_ROLES, List.class));
        } catch (JwtException | IllegalArgumentException ex) {
            throw BizException.of(ErrorCode.TOKEN_INVALID);
        }
    }
}
