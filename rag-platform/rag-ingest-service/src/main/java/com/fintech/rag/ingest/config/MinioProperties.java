package com.fintech.rag.ingest.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * MinIO 配置。
 *
 * @author rag-platform
 */
@ConfigurationProperties(prefix = "rag.minio")
public class MinioProperties {

    private String endpoint = "http://127.0.0.1:9000";

    private String accessKey;

    private String secretKey;

    private String bucket = "rag-origin-doc";

    public String getEndpoint() {
        return endpoint;
    }

    public void setEndpoint(String endpoint) {
        this.endpoint = endpoint;
    }

    public String getAccessKey() {
        return accessKey;
    }

    public void setAccessKey(String accessKey) {
        this.accessKey = accessKey;
    }

    public String getSecretKey() {
        return secretKey;
    }

    public void setSecretKey(String secretKey) {
        this.secretKey = secretKey;
    }

    public String getBucket() {
        return bucket;
    }

    public void setBucket(String bucket) {
        this.bucket = bucket;
    }
}
