package com.fintech.rag.gateway.filter;

import com.fintech.rag.common.constant.RagHeaders;
import com.fintech.rag.common.util.TraceIds;
import com.fintech.rag.gateway.config.GatewayAuthProperties;
import org.springframework.core.Ordered;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import org.springframework.web.server.WebFilter;
import org.springframework.web.server.WebFilterChain;
import reactor.core.publisher.Mono;

/**
 * 入站追踪头洗白 —— <b>必须在观测过滤器之前执行</b>。
 *
 * <p><b>为什么需要它（这是最容易漏的一处安全问题）</b>：</p>
 * <p>Spring Boot 的 WebFlux 观测过滤器（{@code org.springframework.web.filter.reactive
 * .ServerHttpObservationFilter}）order 为 {@code Ordered.HIGHEST_PRECEDENCE + 1}，
 * 它在 <b>WebFilter 链的最前面</b>就把入站 {@code traceparent} 提取成了父上下文。
 * 而 Gateway 的 {@code GlobalFilter} 属于「路由内的过滤器链」，执行时机远晚于 WebFilter —— 
 * 也就是说，等我们自己的 GlobalFilter 去删 traceparent 时，客户端伪造的 traceId
 * <b>已经被采纳为本次链路的 traceId 了</b>。</p>
 *
 * <p>所以：洗白动作必须放在一个 order 更小（更早）的 {@link WebFilter} 里。</p>
 *
 * @author rag-platform
 */
@Component
public class InboundTraceSanitizeWebFilter implements WebFilter, Ordered {

    private final GatewayAuthProperties properties;

    public InboundTraceSanitizeWebFilter(GatewayAuthProperties properties) {
        this.properties = properties;
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain chain) {
        ServerHttpRequest request = exchange.getRequest();
        ServerHttpRequest.Builder builder = request.mutate();

        builder.headers(headers -> {
            if (properties.isAcceptClientTraceparent()) {
                // 白名单模式：仅接受格式合法的 traceparent，非法一律删除
                String incoming = headers.getFirst(RagHeaders.TRACEPARENT);
                if (!TraceIds.isValidTraceparent(incoming)) {
                    headers.remove(RagHeaders.TRACEPARENT);
                }
            } else {
                // 默认模式：网关是链路的唯一根，客户端传入的追踪头一律丢弃
                headers.remove(RagHeaders.TRACEPARENT);
            }
            // 业务自定义 traceId 头同样不可信
            String legacy = headers.getFirst(RagHeaders.TRACE_ID);
            if (legacy != null && !TraceIds.isValidTraceId(legacy)) {
                headers.remove(RagHeaders.TRACE_ID);
            }
        });

        return chain.filter(exchange.mutate().request(builder.build()).build());
    }

    @Override
    public int getOrder() {
        // 必须小于 Spring Boot 观测过滤器的 HIGHEST_PRECEDENCE + 1
        return Ordered.HIGHEST_PRECEDENCE;
    }
}
