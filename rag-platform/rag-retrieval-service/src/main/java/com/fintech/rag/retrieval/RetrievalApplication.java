package com.fintech.rag.retrieval;

import com.fintech.rag.api.client.KnowledgeClient;
import com.fintech.rag.api.client.PlatformClient;
import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;
import org.springframework.cloud.openfeign.EnableFeignClients;

/**
 * 检索服务启动类。
 *
 * <p>本服务把「检索策略」收口到一处：Query 改写、RAGFlow 混合检索、Rerank、
 * 业务过滤、缓存、召回评测。这样 RAGFlow 参数调整、未来更换检索引擎，
 * 都只需要改这一个服务。</p>
 *
 * @author rag-platform
 */
@SpringBootApplication(scanBasePackages = "com.fintech.rag.retrieval")
@EnableDiscoveryClient
@EnableFeignClients(clients = {PlatformClient.class, KnowledgeClient.class})
@ConfigurationPropertiesScan("com.fintech.rag.retrieval")
@MapperScan("com.fintech.rag.retrieval.infra.persistence.mapper")
public class RetrievalApplication {

    public static void main(String[] args) {
        SpringApplication.run(RetrievalApplication.class, args);
    }
}
