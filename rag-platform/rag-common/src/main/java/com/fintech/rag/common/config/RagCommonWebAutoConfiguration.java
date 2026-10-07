package com.fintech.rag.common.config;

import com.fintech.rag.common.context.RequestContextFilter;
import com.fintech.rag.common.exception.GlobalExceptionHandler;
import com.fintech.rag.common.observability.TraceIdProvider;
import jakarta.servlet.Filter;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnWebApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;

/**
 * Servlet 栈公共能力自动装配。
 *
 * <p>条件注解写在自动配置类上（而非被装配的类上），Spring Boot 可通过 ASM 读取元数据
 * 判断条件，不会触发 class loading，因此 rag-gateway（WebFlux）不会因为缺少
 * jakarta.servlet 而启动失败。</p>
 *
 * @author rag-platform
 */
@AutoConfiguration
@ConditionalOnWebApplication(type = ConditionalOnWebApplication.Type.SERVLET)
@ConditionalOnClass(name = "jakarta.servlet.Filter")
@Import(GlobalExceptionHandler.class)
public class RagCommonWebAutoConfiguration {

    @Bean
    @ConditionalOnMissingBean
    public Filter requestContextFilter(ObjectProvider<TraceIdProvider> traceIdProvider) {
        // 用 ObjectProvider 注入：未引入追踪依赖时 getIfAvailable() 返回 null，
        // 过滤器退化为「自行解析 traceparent」，不会启动失败
        return new RequestContextFilter(traceIdProvider);
    }
}
