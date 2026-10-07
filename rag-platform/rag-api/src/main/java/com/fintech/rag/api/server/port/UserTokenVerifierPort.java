package com.fintech.rag.api.server.port;

import com.fintech.rag.api.dto.platform.UserTokenPayload;

/**
 * 用户令牌校验端口（服务端）。
 *
 * <p>仅「网关专用路径」（如 /api/platform/auth/verify）需要真正解析令牌；
 * 常规业务路径信任网关注入的 X-User-Id，不重复解析，避免每请求一次远程调用。</p>
 *
 * @author rag-platform
 */
public interface UserTokenVerifierPort {

    /**
     * 解析并校验令牌。
     *
     * @param token JWT
     * @return 载荷；无效时抛出 BizException(TOKEN_INVALID)
     */
    UserTokenPayload verify(String token);
}
