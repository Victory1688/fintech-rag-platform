package com.fintech.rag.api.config;

import com.fintech.rag.api.client.interceptor.AppSignatureRequestInterceptor;
import com.fintech.rag.api.client.interceptor.TracePropagationInterceptor;
import feign.RequestInterceptor;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;

/**
 * rag-api 自动装配：统一为所有 Feign 客户端挂上追踪透传与（可选的）应用签名。
 *
 * <p>注意本配置<b>不会</b>自动开启 Feign 扫描。各服务需显式声明
 * {@code @EnableFeignClients(clients = {KnowledgeClient.class, ...})}，
 * 显式优于隐式：可以清楚看到每个服务依赖了哪些下游。</p>
 *
 * @author rag-platform
 */
@AutoConfiguration
@ConditionalOnClass(RequestInterceptor.class)
@EnableConfigurationProperties(RagSdkProperties.class)
public class RagApiAutoConfiguration {

    @Bean
    @ConditionalOnMissingBean(name = "tracePropagationInterceptor")
    public RequestInterceptor tracePropagationInterceptor() {
        return new TracePropagationInterceptor();
    }

    @Bean
    @ConditionalOnMissingBean(name = "appSignatureRequestInterceptor")
    public RequestInterceptor appSignatureRequestInterceptor(RagSdkProperties properties) {
        return new AppSignatureRequestInterceptor(properties);
    }
}
