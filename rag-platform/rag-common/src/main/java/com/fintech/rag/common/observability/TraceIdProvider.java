package com.fintech.rag.common.observability;

/**
 * 当前 traceId 提供者。
 *
 * <p>刻意定义成接口而非直接依赖 Micrometer Tracing：这样 rag-common 对追踪实现
 * <b>零硬依赖</b>——未引入追踪依赖的服务（或引用 rag-api 的外部业务方）不会因为
 * 缺少 {@code io.micrometer.tracing.Tracer} 而启动失败。</p>
 *
 * @author rag-platform
 */
public interface TraceIdProvider {

    /** 当前请求的 traceId；无上下文时返回 null */
    String currentTraceId();
}
