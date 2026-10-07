package com.fintech.rag.platform.app.service;

import com.fintech.rag.api.dto.platform.UserTokenPayload;
import com.fintech.rag.platform.infra.security.JwtTokenService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * 认证应用服务。
 *
 * <p><b>待对接项：</b>当前为骨架实现，用户校验走内存桩。
 * 落地时替换为「统一身份源（OIDC/CAS/LDAP）校验 + 本地用户/角色表补充授权信息」。</p>
 *
 * @author rag-platform
 */
@Service
public class AuthAppService {

    private static final Logger log = LoggerFactory.getLogger(AuthAppService.class);

    private final JwtTokenService jwtTokenService;

    public AuthAppService(JwtTokenService jwtTokenService) {
        this.jwtTokenService = jwtTokenService;
    }

    /**
     * 登录。
     *
     * @return 访问令牌
     */
    public String login(String username, String password) {
        // TODO 对接统一身份源；当前桩实现仅用于链路联调，上线前必须替换
        if (username == null || username.isBlank()) {
            throw new IllegalArgumentException("用户名不能为空");
        }
        log.info("用户登录成功 username={}", username);

        UserTokenPayload payload = new UserTokenPayload(
                username, username, 1L, 2, List.of("CREDIT_OFFICER"));
        return jwtTokenService.issueAccessToken(payload);
    }

    /** 刷新令牌，返回新的访问令牌 */
    public String refresh(String refreshToken) {
        UserTokenPayload payload = jwtTokenService.parse(refreshToken);
        return jwtTokenService.issueAccessToken(payload);
    }

    /** 校验用户令牌（供网关调用） */
    public UserTokenPayload verify(String token) {
        return jwtTokenService.parse(token);
    }

    /** 签发访问令牌（供登录成功后使用） */
    public String issueAccessToken(UserTokenPayload payload) {
        return jwtTokenService.issueAccessToken(payload);
    }
}
