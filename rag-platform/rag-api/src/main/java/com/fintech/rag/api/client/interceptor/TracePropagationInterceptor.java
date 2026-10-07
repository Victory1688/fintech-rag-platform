package com.fintech.rag.api.client.interceptor;

import com.fintech.rag.common.constant.RagHeaders;
import com.fintech.rag.common.context.RequestContext;
import com.fintech.rag.common.util.TraceIds;
import feign.RequestInterceptor;
import feign.RequestTemplate;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.util.ClassUtils;

/**
 * Feign 追踪透传拦截器。
 *
 * <p><strong>职责边界（务必看清，否则会漏掉真正的透传依赖）：</strong></p>
 * <ul>
 *   <li>本类只负责透传<b>业务自定义头</b> {@code X-Trace-Id}（给日志、审计、人工排障用）；</li>
 *   <li>标准 W3C {@code traceparent} 由 <b>Feign 观测能力</b>注入，不是本类做的 ——
 *       即 classpath 上的 {@code io.github.openfeign:feign-micrometer}。
 *       该依赖会装配 {@code MicrometerObservationCapability}，由
 *       {@code PropagatingSenderTracingObservationHandler} 把当前 span 写成
 *       {@code traceparent} 头。</li>
 * </ul>
 *
 * <p><b>为什么启动时要体检一次</b>：缺 {@code feign-micrometer} 时 Feign 调用不会带
 * {@code traceparent}，下游会另起一条新链路。它的表现非常隐蔽 —— 网关到第一个服务的
 * 链路是好的，只有后续 Feign 跳转断掉，看日志「每条都有 traceId」却「串不成一条链」。
 * 与其等人肉排查，不如启动即报错。</p>
 *
 * <p><strong>绝不在此处添加 {@code X-Request-Source}。</strong>
 * 来源标识只能由 DMZ 网关注入；内网 Feign 客户端一旦全局带上它，
 * AI 服务侧的反向拦截会直接把内网调用判为伪造并返回 403。</p>
 *
 * @author rag-platform
 */
public class TracePropagationInterceptor implements RequestInterceptor {

    private static final Logger log = LoggerFactory.getLogger(TracePropagationInterceptor.class);

    /**
     * Feign 观测能力类名 —— 只做「存在性判断」，不引用其类型，
     * 因此本类在缺少该依赖时仍可正常加载。
     */
    private static final String FEIGN_OBSERVATION_CAPABILITY = "feign.micrometer.MicrometerObservationCapability";

    public TracePropagationInterceptor() {
        checkPropagationReady();
    }

    @Override
    public void apply(RequestTemplate template) {
        String traceId = RequestContext.currentTraceId();
        template.header(RagHeaders.TRACE_ID, TraceIds.resolve(traceId));
        // 注意：此处刻意不手动写 traceparent —— 手写会与 Feign 观测能力注入的头并存，
        // 变成两个 traceparent（取值还不一致），下游取哪个取决于实现细节，属于不可控行为。
    }

    /**
     * 启动期体检：Feign 在 classpath 上，但观测能力缺失时直接报错。
     *
     * <p>这里用 ERROR 而不是 WARN：这不是「可选优化项」，而是会让整条链路静默断裂的
     * 配置缺陷，必须让人第一眼看到。</p>
     */
    private void checkPropagationReady() {
        try {
            boolean hasFeign = ClassUtils.isPresent("feign.Request", getClass().getClassLoader());
            boolean hasObservation = ClassUtils.isPresent(FEIGN_OBSERVATION_CAPABILITY, getClass().getClassLoader());
            if (hasFeign && !hasObservation) {
                log.error("""
                        检测到 Feign 但缺少链路透传能力：跨服务调用不会携带 traceparent，                        下游将另起一条新链路（链路会在第一个 Feign 跳转处断裂）。
                        修复方式：在模块 pom.xml 中引入
                            <dependency>
                                <groupId>io.github.openfeign</groupId>
                                <artifactId>feign-micrometer</artifactId>
                            </dependency>
                        并确保 io.micrometer:micrometer-tracing-bridge-otel 在 classpath 上。                        详见 docs/05 §5.5。""");
            }
        } catch (Throwable ignored) {
            // 体检本身永不影响启动
        }
    }
}
