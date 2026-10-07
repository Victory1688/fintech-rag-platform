package com.fintech.rag.gateway.filter;

import com.fintech.rag.common.constant.RagHeaders;
import com.fintech.rag.common.context.RequestSource;
import com.fintech.rag.common.util.HmacSignatures;
import com.fintech.rag.common.util.TraceIds;
import com.fintech.rag.gateway.config.GatewayAuthProperties;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.util.Set;

/**
 * 请求来源标识注入、「洗白」与链路透传过滤器 —— <b>整套防伪造机制的第一道闸</b>。
 *
 * <p>核心逻辑（顺序不可颠倒）：</p>
 * <ol>
 *   <li><b>先删</b>：强制移除客户端可能传入的一切身份/来源头，防止前端伪造；</li>
 *   <li><b>再写</b>：注入可信的 {@code X-Request-Source: DMZ_GATEWAY}；</li>
 *   <li><b>链路透传</b>：解析当前 span 的 traceId，写成标准 {@code traceparent} 下发给内网服务
 *       （traceId 由 OTel 生成，此处只做「向下游声明」，不再自行造 ID）；</li>
 *   <li>可选注入 {@code X-Gateway-Signature}，供内网侧做不依赖 IP 的强校验。</li>
 * </ol>
 *
 * <p>为什么不在 route 里用 {@code RemoveRequestHeader}/{@code AddRequestHeader}？
 * 声明式过滤器对新增路由容易漏配，一旦漏配就是静默的鉴权绕过。
 * 用 GlobalFilter 可以保证「所有路由无例外」。</p>
 *
 * <p><b>注意</b>：入站 traceparent 的洗白在 {@link InboundTraceSanitizeWebFilter} 中完成，
 * 因为 GlobalFilter 执行得太晚（观测过滤器已经把伪造值采纳为父上下文了）。</p>
 *
 * @author rag-platform
 */
@Component
public class RequestSourceSanitizeGlobalFilter implements GlobalFilter, Ordered {

    /** 客户端可伪造、必须由网关统一洗掉的头 */
    private static final Set<String> SPOOFABLE_HEADERS = Set.of(
            RagHeaders.REQUEST_SOURCE,
            RagHeaders.GATEWAY_SIGNATURE,
            RagHeaders.USER_ID,
            RagHeaders.USER_NAME,
            RagHeaders.USER_ROLES,
            RagHeaders.USER_DEPT,
            RagHeaders.APP_ID,
            RagHeaders.APP_TIMESTAMP,
            RagHeaders.APP_NONCE,
            RagHeaders.APP_SIGNATURE,
            RagHeaders.TRACEPARENT,
            RagHeaders.TRACE_ID
    );

    private final GatewayAuthProperties properties;
    private final GatewayTraceSupport traceSupport;

    public RequestSourceSanitizeGlobalFilter(GatewayAuthProperties properties,
                                            GatewayTraceSupport traceSupport) {
        this.properties = properties;
        this.traceSupport = traceSupport;
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        ServerHttpRequest request = exchange.getRequest();
        String traceId = traceSupport.resolveCurrentTraceId();

        ServerHttpRequest.Builder builder = request.mutate();
        builder.headers(headers -> {
            SPOOFABLE_HEADERS.forEach(headers::remove);
            headers.set(RagHeaders.REQUEST_SOURCE, RequestSource.DMZ_HEADER_VALUE);
            headers.set(RagHeaders.TRACE_ID, traceId);
            headers.set(RagHeaders.TRACEPARENT, TraceIds.formatTraceparent(traceId, traceSupport.isSampled()));
            if (StringUtils.hasText(properties.getSignSecret())) {
                String timestamp = String.valueOf(System.currentTimeMillis());
                String signature = HmacSignatures.hmacSha256Hex(
                        properties.getSignSecret(), request.getPath().value() + "\n" + timestamp);
                headers.set(RagHeaders.GATEWAY_SIGNATURE, timestamp + "." + signature);
            }
        });

        ServerWebExchange mutated = exchange.mutate()
                .request(builder.build())
                .build();
        mutated.getResponse().getHeaders().set(RagHeaders.TRACE_ID, traceId);
        return chain.filter(mutated);
    }

    @Override
    public int getOrder() {
        // 必须最早执行：任何鉴权过滤器都必须拿到「已洗白」的请求头
        return Ordered.HIGHEST_PRECEDENCE + 100;
    }
}
