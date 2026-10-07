package com.fintech.rag.api.server.config;

import com.fintech.rag.api.client.PlatformClient;
import com.fintech.rag.api.server.adapter.FeignAppVerifierAdapter;
import com.fintech.rag.api.server.adapter.FeignUserTokenVerifierAdapter;
import com.fintech.rag.api.server.interceptor.BodyCachingFilter;
import com.fintech.rag.api.server.interceptor.SourceAuthInterceptor;
import com.fintech.rag.api.server.port.AppVerifierPort;
import com.fintech.rag.api.server.port.UserTokenVerifierPort;
import jakarta.servlet.Filter;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.autoconfigure.condition.ConditionalOnWebApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * 服务端来源鉴权自动装配。
 *
 * <p><b>默认关闭</b>（{@code matchIfMissing = false}）。
 * 原因：rag-api 同时作为「内网业务方接入 SDK」，业务方引入本模块只是为了调用我们，
 * 不应被强行装上服务端拦截器。本平台自己的服务需显式配置
 * {@code rag.server.auth.enabled: true}。</p>
 *
 * <p>若开启但容器内不存在 {@link AppVerifierPort} 实现，会直接抛
 * NoSuchBeanDefinitionException 启动失败 —— 这是<b>有意的 fail-fast</b>：
 * 宁可启动不了，也不能带着「看起来有鉴权、实际没鉴权」的配置上线。</p>
 *
 * @author rag-platform
 */
@AutoConfiguration
@ConditionalOnWebApplication(type = ConditionalOnWebApplication.Type.SERVLET)
@ConditionalOnClass(name = "jakarta.servlet.Filter")
@ConditionalOnProperty(prefix = "rag.server.auth", name = "enabled", havingValue = "true")
@EnableConfigurationProperties(SourceAuthProperties.class)
public class RagServerAuthAutoConfiguration {

    /** 平台自身用的是进程内适配器；其它服务在存在 PlatformClient 时自动走 Feign */
    @Bean
    @ConditionalOnMissingBean(AppVerifierPort.class)
    @ConditionalOnBean(PlatformClient.class)
    public AppVerifierPort feignAppVerifierPort(PlatformClient platformClient) {
        return new FeignAppVerifierAdapter(platformClient);
    }

    @Bean
    @ConditionalOnMissingBean(UserTokenVerifierPort.class)
    @ConditionalOnBean(PlatformClient.class)
    public UserTokenVerifierPort feignUserTokenVerifierPort(PlatformClient platformClient) {
        return new FeignUserTokenVerifierAdapter(platformClient);
    }

    @Bean
    @ConditionalOnMissingBean
    public Filter bodyCachingFilter() {
        return new BodyCachingFilter();
    }

    @Bean
    public SourceAuthInterceptor sourceAuthInterceptor(SourceAuthProperties properties,
                                                      AppVerifierPort appVerifierPort,
                                                      org.springframework.beans.factory.ObjectProvider<UserTokenVerifierPort> provider) {
        return new SourceAuthInterceptor(properties, appVerifierPort, provider);
    }

    @Bean
    public WebMvcConfigurer ragServerAuthWebMvcConfigurer(SourceAuthInterceptor interceptor) {
        return new WebMvcConfigurer() {
            @Override
            public void addInterceptors(InterceptorRegistry registry) {
                registry.addInterceptor(interceptor)
                        .addPathPatterns("/api/**", "/internal/**")
                        .excludePathPatterns("/actuator/**", "/doc.html", "/v3/api-docs/**");
            }
        };
    }
}
