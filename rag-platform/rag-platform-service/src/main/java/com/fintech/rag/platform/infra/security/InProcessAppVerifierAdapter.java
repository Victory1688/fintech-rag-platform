package com.fintech.rag.platform.infra.security;

import com.fintech.rag.api.dto.platform.AppSignVerifyRequest;
import com.fintech.rag.api.dto.platform.AppSignVerifyResult;
import com.fintech.rag.api.server.port.AppVerifierPort;
import com.fintech.rag.api.server.port.UserTokenVerifierPort;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * rag-platform-service 的进程内验签适配器。
 *
 * <p>platform 是验签能力的宿主，不能通过 Feign 调用自己（自环调用会带来
 * 线程池耗尽与超时放大的双重风险），因此直接注入本地内核。</p>
 *
 * @author rag-platform
 */
@Configuration
public class InProcessAppVerifierAdapter {

    private static final Logger log = LoggerFactory.getLogger(InProcessAppVerifierAdapter.class);

    @Bean
    public AppVerifierPort inProcessAppVerifierPort(AppSignatureVerifier verifier) {
        return request -> {
            try {
                return verifier.verify(request);
            } catch (Exception ex) {
                log.error("本地验签异常，按 fail-close 处理 appId={}", request.appId(), ex);
                return AppSignVerifyResult.rejected("验签服务内部错误");
            }
        };
    }

    @Bean
    public UserTokenVerifierPort inProcessUserTokenVerifierPort(JwtTokenService jwtTokenService) {
        return token -> jwtTokenService.parse(token);
    }
}
