package com.fintech.rag.common.observability;

import io.micrometer.tracing.Span;
import io.micrometer.tracing.Tracer;

/**
 * Micrometer Tracing 实现：直接复用当前 span 的 traceId。
 *
 * <p><b>为什么必须复用而不是自己生成</b>：OTel 按 W3C 规范从 traceparent 提取了
 * 父上下文并创建了 span，此时 traceId 已经确定。若业务代码再自己生成一个，
 * 结果就是「日志一个 ID、链路另一个 ID」，排障时永远对不上。</p>
 *
 * <p>本类只在 classpath 存在 {@code io.micrometer.tracing.Tracer} 时被装配
 * （见 {@code RagCommonObservabilityAutoConfiguration}）。</p>
 *
 * @author rag-platform
 */
public class MicrometerTraceIdProvider implements TraceIdProvider {

    private final Tracer tracer;

    public MicrometerTraceIdProvider(Tracer tracer) {
        this.tracer = tracer;
    }

    @Override
    public String currentTraceId() {
        Span span = tracer.currentSpan();
        if (span == null || span.context() == null) {
            return null;
        }
        return span.context().traceId();
    }
}
