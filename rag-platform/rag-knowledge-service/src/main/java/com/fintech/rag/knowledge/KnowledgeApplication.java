package com.fintech.rag.knowledge;

import com.fintech.rag.api.client.PlatformClient;
import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;
import org.springframework.cloud.openfeign.EnableFeignClients;

/**
 * 知识库服务启动类。
 *
 * <p>对外提供两类接口：</p>
 * <ul>
 *   <li>管理面：知识库与文档 CRUD、ACL 配置（经网关，用户身份）</li>
 *   <li>内网面：授权查询、文档元数据（Feign 直连，应用身份）</li>
 * </ul>
 *
 * @author rag-platform
 */
@SpringBootApplication(scanBasePackages = "com.fintech.rag.knowledge")
@EnableDiscoveryClient
@EnableFeignClients(clients = PlatformClient.class)
@ConfigurationPropertiesScan("com.fintech.rag.knowledge")
@MapperScan("com.fintech.rag.knowledge.infra.persistence.mapper")
public class KnowledgeApplication {

    public static void main(String[] args) {
        SpringApplication.run(KnowledgeApplication.class, args);
    }
}
