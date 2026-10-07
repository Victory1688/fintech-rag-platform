package com.fintech.rag.common.integration.ragflow;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * RAGFlow 接入配置（knowledge / ingest / retrieval 三个服务共用）。
 *
 * <p><b>API Key 的持有范围必须收敛</b>：只允许这三个服务配置，
 * rag-chat-service 与 rag-gateway 不得持有，防止生成链路被直接拿去访问知识库。</p>
 *
 * @author rag-platform
 */
@ConfigurationProperties(prefix = "rag.ragflow")
public class RagFlowProperties {

    /** RAGFlow 服务地址，如 http://10.10.2.31:9380 */
    private String baseUrl = "http://127.0.0.1:9380";

    /** API Key，由 RAGFlow 页面生成 */
    private String apiKey;

    /** 默认向量模型，同一知识库内必须一致，否则 RAGFlow 会拒绝检索 */
    private String defaultEmbeddingModel = "BAAI/bge-large-zh-v1.5";

    /** 默认重排模型 */
    private String defaultRerankModel = "BAAI/bge-reranker-v2-m3";

    private int connectTimeoutMs = 3000;

    /** 检索类调用超时 */
    private int readTimeoutMs = 5000;

    /** 文档上传/解析类调用超时，通常更宽松 */
    private int uploadTimeoutMs = 120000;

    /** 单文档解析最长等待时间，超时判定为失败 */
    private long parseTimeoutMs = 30 * 60 * 1000L;

    public String getBaseUrl() {
        return baseUrl;
    }

    public void setBaseUrl(String baseUrl) {
        this.baseUrl = baseUrl;
    }

    public String getApiKey() {
        return apiKey;
    }

    public void setApiKey(String apiKey) {
        this.apiKey = apiKey;
    }

    public String getDefaultEmbeddingModel() {
        return defaultEmbeddingModel;
    }

    public void setDefaultEmbeddingModel(String defaultEmbeddingModel) {
        this.defaultEmbeddingModel = defaultEmbeddingModel;
    }

    public String getDefaultRerankModel() {
        return defaultRerankModel;
    }

    public void setDefaultRerankModel(String defaultRerankModel) {
        this.defaultRerankModel = defaultRerankModel;
    }

    public int getConnectTimeoutMs() {
        return connectTimeoutMs;
    }

    public void setConnectTimeoutMs(int connectTimeoutMs) {
        this.connectTimeoutMs = connectTimeoutMs;
    }

    public int getReadTimeoutMs() {
        return readTimeoutMs;
    }

    public void setReadTimeoutMs(int readTimeoutMs) {
        this.readTimeoutMs = readTimeoutMs;
    }

    public int getUploadTimeoutMs() {
        return uploadTimeoutMs;
    }

    public void setUploadTimeoutMs(int uploadTimeoutMs) {
        this.uploadTimeoutMs = uploadTimeoutMs;
    }

    public long getParseTimeoutMs() {
        return parseTimeoutMs;
    }

    public void setParseTimeoutMs(long parseTimeoutMs) {
        this.parseTimeoutMs = parseTimeoutMs;
    }
}
