package com.fintech.rag.common.context;

import com.fintech.rag.common.constant.RagHeaders;
import com.fintech.rag.common.observability.TraceIdProvider;
import com.fintech.rag.common.util.TraceIds;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.MDC;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.core.Ordered;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/**
 * 请求上下文初始化过滤器（Servlet 栈）。
 *
 * <p>只做三件事：解析 traceId、解析请求来源、解析客户端 IP。
 * <strong>不做鉴权</strong>——鉴权由各服务的 SourceAuthInterceptor 完成，
 * 因为不同服务的权限模型不同（用户维度 vs 应用维度）。</p>
 *
 * <p><b>traceId 的解析优先级（顺序很重要）</b>：</p>
 * <ol>
 *   <li>{@link TraceIdProvider}：即 Micrometer Tracing 当前 span 的 traceId。
 *       这是<b>权威值</b> —— OTel 已按 W3C 规范从 traceparent 提取并生成了 span，
 *       我们直接复用它，保证「日志里的 traceId」与「链路里的 traceId」完全一致。</li>
 *   <li>本地解析 traceparent / X-Trace-Id（用于未引入追踪依赖的服务或降级场景）。</li>
 *   <li>都没有则新建。</li>
 * </ol>
 * <p>本过滤器位于观测过滤器之后执行（order 更大），因此第 1 步在正常情况下必然命中。</p>
 *
 * @author rag-platform
 */
public class RequestContextFilter extends OncePerRequestFilter implements Ordered {

    private final ObjectProvider<TraceIdProvider> traceIdProvider;

    public RequestContextFilter(ObjectProvider<TraceIdProvider> traceIdProvider) {
        this.traceIdProvider = traceIdProvider;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        String traceId = resolveTraceId(request);
        String clientIp = resolveClientIp(request);
        RequestSource source = RequestSource.resolve(request.getHeader(RagHeaders.REQUEST_SOURCE));

        RequestContext.set(new RequestContext.Snapshot(
                source, null, null, null,
                request.getHeader(RagHeaders.APP_ID),
                clientIp, traceId));

        MDC.put("traceId", traceId);
        response.setHeader(RagHeaders.TRACE_ID, traceId);
        try {
            filterChain.doFilter(request, response);
        } finally {
            // 必须清理：线程池复用会串号，这是排查线上诡异问题的常见根源
            MDC.clear();
            RequestContext.clear();
        }
    }

    private String resolveTraceId(HttpServletRequest request) {
        TraceIdProvider provider = traceIdProvider.getIfAvailable();
        if (provider != null) {
            String current = provider.currentTraceId();
            if (current != null && !current.isBlank()) {
                return current;
            }
        }
        String fromTraceparent = TraceIds.parseTraceId(request.getHeader(RagHeaders.TRACEPARENT));
        if (fromTraceparent != null) {
            return fromTraceparent;
        }
        return TraceIds.resolve(request.getHeader(RagHeaders.TRACE_ID));
    }

    private String resolveClientIp(HttpServletRequest request) {
        String[] headers = {"X-Forwarded-For", "X-Real-IP", "Proxy-Client-IP", "WL-Proxy-Client-IP"};
        for (String header : headers) {
            String value = request.getHeader(header);
            if (value != null && !value.isBlank() && !"unknown".equalsIgnoreCase(value)) {
                int comma = value.indexOf(',');
                return comma > 0 ? value.substring(0, comma).trim() : value.trim();
            }
        }
        return request.getRemoteAddr();
    }

    @Override
    public int getOrder() {
        // 必须晚于 Spring Boot 的观测过滤器（ServerHttpObservationFilter = HIGHEST_PRECEDENCE + 1），
        // 否则拿不到当前 span 的 traceId
        return Ordered.HIGHEST_PRECEDENCE + 10;
    }
}
