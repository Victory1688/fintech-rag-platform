package com.fintech.rag.platform.api.controller;

import com.fintech.rag.api.dto.platform.UserTokenPayload;
import com.fintech.rag.common.constant.RagHeaders;
import com.fintech.rag.common.core.R;
import com.fintech.rag.platform.app.service.AuthAppService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 认证接口。
 *
 * <p>{@code /login} 与 {@code /refresh} 是网关白名单里唯一放开的外网入口，
 * 必须在网关或本层叠加图形验证码 / 频率限制 / 异常登录锁定。</p>
 *
 * @author rag-platform
 */
@RestController
@RequestMapping("/api/platform/auth")
public class AuthController {

    private final AuthAppService authAppService;

    public AuthController(AuthAppService authAppService) {
        this.authAppService = authAppService;
    }

    @PostMapping("/login")
    public R<Map<String, String>> login(@RequestParam String username,
                                        @RequestParam String password) {
        String token = authAppService.login(username, password);
        return R.ok(Map.of("accessToken", token));
    }

    @PostMapping("/refresh")
    public R<Map<String, String>> refresh(HttpServletRequest request) {
        String refreshToken = request.getHeader(RagHeaders.USER_TOKEN);
        return R.ok(Map.of("accessToken", authAppService.refresh(refreshToken)));
    }

    /**
     * 令牌校验（仅允许网关调用，走 GATEWAY_ONLY_PATHS 白名单 + 网关网段限制）。
     */
    @PostMapping("/verify")
    public R<UserTokenPayload> verify(HttpServletRequest request) {
        Object payload = request.getAttribute("USER_PAYLOAD");
        if (payload instanceof UserTokenPayload userTokenPayload) {
            return R.ok(userTokenPayload);
        }
        return R.ok(authAppService.verify(request.getHeader(RagHeaders.USER_TOKEN)));
    }
}
