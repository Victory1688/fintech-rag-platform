package com.fintech.rag.chat;

import com.fintech.rag.api.client.KnowledgeClient;
import com.fintech.rag.api.client.PlatformClient;
import com.fintech.rag.api.client.RetrievalClient;
import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;
import org.springframework.cloud.openfeign.EnableFeignClients;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * 问答编排服务启动类。
 *
 * <p>职责：把「检索到的片段」变成「合规、可溯源、贴合本行口径的回答」。
 * 生成链路成本最高，因此本服务的限流、缓存、降级策略要比检索服务更保守。</p>
 *
 * @author rag-platform
 */
@SpringBootApplication(scanBasePackages = "com.fintech.rag.chat")
@EnableDiscoveryClient
@EnableFeignClients(clients = {PlatformClient.class, KnowledgeClient.class, RetrievalClient.class})
@EnableScheduling
@ConfigurationPropertiesScan("com.fintech.rag.chat")
@MapperScan("com.fintech.rag.chat.infra.persistence.mapper")
public class ChatApplication {

    public static void main(String[] args) {
        SpringApplication.run(ChatApplication.class, args);
    }
}
