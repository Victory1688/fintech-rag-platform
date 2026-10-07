package com.fintech.rag.ingest;

import com.fintech.rag.api.client.PlatformClient;
import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;
import org.springframework.cloud.openfeign.EnableFeignClients;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * 文档入库服务启动类。
 *
 * <p>本服务是典型的「重 IO + 长任务 + 批处理」型：必须与在线问答服务物理隔离，
 * 否则一次批量导入就能把在线问答的线程池与数据库连接池打满。</p>
 *
 * @author rag-platform
 */
@SpringBootApplication(scanBasePackages = "com.fintech.rag.ingest")
@EnableDiscoveryClient
@EnableFeignClients(clients = PlatformClient.class)
@EnableScheduling
@ConfigurationPropertiesScan("com.fintech.rag.ingest")
@MapperScan("com.fintech.rag.ingest.infra.persistence.mapper")
public class IngestApplication {

    public static void main(String[] args) {
        SpringApplication.run(IngestApplication.class, args);
    }
}
