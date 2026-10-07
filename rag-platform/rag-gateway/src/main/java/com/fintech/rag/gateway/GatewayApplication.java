package com.fintech.rag.gateway;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;

/**
 * DMZ 边界网关启动类。
 *
 * <p>职责边界（严格遵守）：只管流量与安全，不承载任何 RAG / LLM 业务逻辑。
 * 一旦在网关里写 Prompt 拼装或检索逻辑，就会变成「分布式单体」。</p>
 *
 * @author rag-platform
 */
@SpringBootApplication(scanBasePackages = "com.fintech.rag.gateway")
@EnableDiscoveryClient
@ConfigurationPropertiesScan("com.fintech.rag.gateway")
public class GatewayApplication {

    public static void main(String[] args) {
        SpringApplication.run(GatewayApplication.class, args);
    }
}
