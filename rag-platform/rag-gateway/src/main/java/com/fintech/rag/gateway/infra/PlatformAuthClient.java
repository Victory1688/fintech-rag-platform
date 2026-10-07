package com.fintech.rag.gateway.infra;

import com.fintech.rag.api.dto.platform.UserTokenPayload;
import com.fintech.rag.common.constant.RagHeaders;
import com.fintech.rag.common.core.R;
import com.fintech.rag.gateway.config.GatewayAuthProperties;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.time.Duration;

/**
 * 调用 rag-platform-service 校验用户令牌。
 *
 * <p>注意：这里刻意使用「服务名 + 负载均衡」而非硬编码 IP，
 * 复用 Nacos 服务发现，避免容器环境下 IP 漂移导致网关整体不可用。</p>
 *
 * @author rag-platform
 */
@Component
public class PlatformAuthClient {

    private static final ParameterizedTypeReference<R<UserTokenPayload>> TYPE_REF =
            new ParameterizedTypeReference<>() {
            };

    private final WebClient webClient;
    private final GatewayAuthProperties properties;

    public PlatformAuthClient(WebClient.Builder loadBalancedWebClientBuilder, GatewayAuthProperties properties) {
        this.webClient = loadBalancedWebClientBuilder
                .baseUrl("http://rag-platform-service")
                .build();
        this.properties = properties;
    }

    /**
     * 校验用户令牌。
     *
     * @param token 用户 JWT
     * @return 校验通过返回载荷，否则返回空 Mono
     */
    public Mono<UserTokenPayload> verifyUserToken(String token) {
        return webClient.post()
                .uri("/api/platform/auth/verify")
                .header(RagHeaders.USER_TOKEN, token)
                .retrieve()
                .bodyToMono(TYPE_REF)
                .timeout(Duration.ofMillis(properties.getAuthTimeoutMs()))
                .map(result -> result.isSuccess() ? result.getData() : null);
    }
}
