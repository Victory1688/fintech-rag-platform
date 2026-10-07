package com.fintech.rag.gateway.filter;

import com.fintech.rag.api.dto.platform.UserTokenPayload;
import com.fintech.rag.common.constant.RagHeaders;
import com.fintech.rag.gateway.config.GatewayAuthProperties;
import com.fintech.rag.gateway.infra.PlatformAuthClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.http.server.reactive.ServerHttpResponse;
import org.springframework.stereotype.Component;
import org.springframework.util.AntPathMatcher;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.nio.charset.StandardCharsets;

/**
 * 统一鉴权过滤器（只处理「外网用户流量」）。
 *
 * <p>职责：校验用户令牌 → 解析出用户身份 → 以可信 Header 透传给内网服务。
 * 内网业务微服务的流量不走网关，其应用签名校验在各服务自身的拦截器中完成。</p>
 *
 * <p><b>fail-close 原则</b>：认证服务不可用时必须拒绝请求。
 * 若选择 fail-open，一次 platform 抖动就等于全网鉴权失效，属于不可接受的风险。</p>
 *
 * @author rag-platform
 */
@Component
public class UnifiedAuthGlobalFilter implements GlobalFilter, Ordered {

    private static final Logger log = LoggerFactory.getLogger(UnifiedAuthGlobalFilter.class);
    private static final AntPathMatcher MATCHER = new AntPathMatcher();

    private final PlatformAuthClient platformAuthClient;
    private final GatewayAuthProperties properties;

    public UnifiedAuthGlobalFilter(PlatformAuthClient platformAuthClient, GatewayAuthProperties properties) {
        this.platformAuthClient = platformAuthClient;
        this.properties = properties;
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        ServerHttpRequest request = exchange.getRequest();
        String path = request.getPath().value();

        if (isPublic(path) || isPreflight(request)) {
            return chain.filter(exchange);
        }

        String token = request.getHeaders().getFirst(RagHeaders.USER_TOKEN);
        if (token == null || token.isBlank()) {
            return reject(exchange, HttpStatus.UNAUTHORIZED, "A0001", "缺少用户令牌");
        }

        return platformAuthClient.verifyUserToken(token)
                .flatMap(payload -> {
                    if (payload == null) {
                        return reject(exchange, HttpStatus.UNAUTHORIZED, "A0001", "令牌无效或已过期");
                    }
                    ServerHttpRequest mutated = request.mutate()
                            .header(RagHeaders.USER_ID, payload.userId())
                            .header(RagHeaders.USER_NAME, payload.realName() == null ? "" : payload.realName())
                            .header(RagHeaders.USER_ROLES, payload.roles() == null
                                    ? "" : String.join(",", payload.roles()))
                            .header(RagHeaders.USER_DEPT, payload.deptId() == null
                                    ? "" : String.valueOf(payload.deptId()))
                            .build();
                    return chain.filter(exchange.mutate().request(mutated).build());
                })
                .onErrorResume(ex -> {
                    log.error("鉴权服务调用异常 path={}", path, ex);
                    if (properties.isFailClose()) {
                        return reject(exchange, HttpStatus.SERVICE_UNAVAILABLE, "A0009", "认证服务不可用，请稍后重试");
                    }
                    return reject(exchange, HttpStatus.UNAUTHORIZED, "A0001", "令牌校验失败");
                });
    }

    private boolean isPublic(String path) {
        return properties.getPublicPaths().stream().anyMatch(pattern -> MATCHER.match(pattern, path));
    }

    private boolean isPreflight(ServerHttpRequest request) {
        return org.springframework.http.HttpMethod.OPTIONS.equals(request.getMethod());
    }

    private Mono<Void> reject(ServerWebExchange exchange, HttpStatus status, String code, String message) {
        ServerHttpResponse response = exchange.getResponse();
        response.setStatusCode(status);
        response.getHeaders().setContentType(MediaType.APPLICATION_JSON);
        String body = "{\"code\":\"" + code + "\",\"message\":\"" + message + "\",\"data\":null}";
        DataBuffer buffer = response.bufferFactory().wrap(body.getBytes(StandardCharsets.UTF_8));
        return response.writeWith(Mono.just(buffer));
    }

    @Override
    public int getOrder() {
        // 晚于来源洗白，早于一切业务转发
        return Ordered.HIGHEST_PRECEDENCE + 200;
    }
}
