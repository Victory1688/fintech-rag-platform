package com.fintech.rag.api.server.adapter;

import com.fintech.rag.api.client.PlatformClient;
import com.fintech.rag.api.dto.platform.UserTokenPayload;
import com.fintech.rag.api.server.port.UserTokenVerifierPort;
import com.fintech.rag.common.core.R;
import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * 通过 Feign 调用 rag-platform-service 校验用户令牌。
 *
 * @author rag-platform
 */
public class FeignUserTokenVerifierAdapter implements UserTokenVerifierPort {

    private static final Logger log = LoggerFactory.getLogger(FeignUserTokenVerifierAdapter.class);

    private final PlatformClient platformClient;

    public FeignUserTokenVerifierAdapter(PlatformClient platformClient) {
        this.platformClient = platformClient;
    }

    @Override
    public UserTokenPayload verify(String token) {
        try {
            R<UserTokenPayload> result = platformClient.verifyUserToken(token);
            if (result == null || !result.isSuccess() || result.getData() == null) {
                throw BizException.of(ErrorCode.TOKEN_INVALID);
            }
            return result.getData();
        } catch (BizException ex) {
            throw ex;
        } catch (Exception ex) {
            log.error("调用令牌校验服务失败", ex);
            throw BizException.of(ErrorCode.AUTH_SERVICE_UNAVAILABLE);
        }
    }
}
