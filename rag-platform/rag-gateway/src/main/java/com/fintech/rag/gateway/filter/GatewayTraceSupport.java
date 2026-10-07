package com.fintech.rag.gateway.filter;

import com.fintech.rag.common.util.TraceIds;
import io.micrometer.tracing.Span;
import io.micrometer.tracing.Tracer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Component;

/**
 * 网关侧 traceId 解析支持。
 *
 * <p>优先取 Micrometer Tracing 当前 span 的 traceId（OTel 已按 W3C 规范生成，
 * 这是权威值）；未引入追踪依赖时自行生成一个 32 位 hex，保证下游永远收到合规 traceparent。</p>
 *
 * @author rag-platform
 */
@Component
public class GatewayTraceSupport {

    private static final Logger log = LoggerFactory.getLogger(GatewayTraceSupport.class);

    private final ObjectProvider<Tracer> tracerProvider;

    public GatewayTraceSupport(ObjectProvider<Tracer> tracerProvider) {
        this.tracerProvider = tracerProvider;
    }

    /** 当前链路的 traceId（32 位小写 hex，绝不为 null） */
    public String resolveCurrentTraceId() {
        Tracer tracer = tracerProvider.getIfAvailable();
        if (tracer != null) {
            Span span = tracer.currentSpan();
            if (span != null && span.context() != null && span.context().traceId() != null) {
                String traceId = TraceIds.normalize(span.context().traceId());
                if (traceId != null) {
                    return traceId;
                }
                // OTel 给出的 traceId 竟然不合规，说明追踪实现异常，降级并告警
                log.warn("追踪上下文中的 traceId 非法，降级为新生成 traceId");
            }
        }
        return TraceIds.newTraceId();
    }

    /** 本次链路是否采样（用于设置 traceparent 的 sampled 标志位） */
    public boolean isSampled() {
        Tracer tracer = tracerProvider.getIfAvailable();
        if (tracer == null) {
            return true;
        }
        Span span = tracer.currentSpan();
        if (span == null || span.context() == null) {
            return true;
        }
        Boolean sampled = span.context().sampled();
        return sampled == null || sampled;
    }
}
