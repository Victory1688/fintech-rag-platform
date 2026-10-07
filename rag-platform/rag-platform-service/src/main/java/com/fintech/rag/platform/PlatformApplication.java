package com.fintech.rag.platform;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.cache.annotation.EnableCaching;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;

/**
 * 平台治理服务启动类。
 *
 * <p>本服务被所有其它服务依赖（验签、授权、模型配置、脱敏规则），
 * 因此可用性优先级最高：必须多实例 + 本地缓存兜底。</p>
 *
 * @author rag-platform
 */
@SpringBootApplication(scanBasePackages = "com.fintech.rag.platform")
@EnableDiscoveryClient
@EnableCaching
@ConfigurationPropertiesScan("com.fintech.rag.platform")
@MapperScan("com.fintech.rag.platform.infra.persistence.mapper")
public class PlatformApplication {

    public static void main(String[] args) {
        SpringApplication.run(PlatformApplication.class, args);
    }
}
