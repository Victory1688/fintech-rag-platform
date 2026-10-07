package com.fintech.rag.common.config;

import com.fintech.rag.common.observability.ContentSanitizer;
import com.fintech.rag.common.observability.MicrometerTraceIdProvider;
import com.fintech.rag.common.observability.ObservabilityProperties;
import com.fintech.rag.common.observability.TraceIdProvider;
import io.micrometer.tracing.Tracer;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;

/**
 * 可观测公共能力自动装配。
 *
 * <p><b>条件注解写在自动配置类上的原因</b>：Spring Boot 通过 ASM 读取元数据判断
 * {@code @ConditionalOnClass}，不会触发类加载。因此当 classpath 缺少
 * {@code io.micrometer.tracing.Tracer} 时，{@link #micrometerTraceIdProvider} 不会被调用，
 * {@link MicrometerTraceIdProvider} 这个引用了 Tracer 的类型也就不会被加载 —— 避免了
 * 引用 rag-api 的外部业务方（未引入追踪依赖）启动时 NoClassDefFoundError。</p>
 *
 * @author rag-platform
 */
@AutoConfiguration
@EnableConfigurationProperties(ObservabilityProperties.class)
@ConditionalOnProperty(prefix = "rag.observability", name = "enabled", havingValue = "true", matchIfMissing = true)
public class RagCommonObservabilityAutoConfiguration {

    @Bean
    @ConditionalOnMissingBean
    public ContentSanitizer contentSanitizer(ObservabilityProperties properties) {
        return new ContentSanitizer(properties);
    }

    @Bean
    @ConditionalOnMissingBean
    @ConditionalOnClass(Tracer.class)
    public TraceIdProvider micrometerTraceIdProvider(Tracer tracer) {
        return new MicrometerTraceIdProvider(tracer);
    }
}
