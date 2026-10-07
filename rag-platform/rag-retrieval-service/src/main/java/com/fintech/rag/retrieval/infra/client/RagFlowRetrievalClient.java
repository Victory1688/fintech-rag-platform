package com.fintech.rag.retrieval.infra.client;

import com.fintech.rag.api.dto.retrieval.RetrievalRequest;
import com.fintech.rag.api.dto.retrieval.RetrievalResponse;
import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import com.fintech.rag.common.integration.ragflow.RagFlowProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.time.Duration;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * RAGFlow 检索客户端。
 *
 * <p>对应 RAGFlow 的 {@code POST /api/v1/retrieval}。关键参数（务必理解语义）：</p>
 * <ul>
 *   <li>{@code similarity_threshold}：低于该分数视为不相关。调高 → 更准但可能空召回；
 *       调低 → 召回率高但引入噪声。信贷场景建议区间 0.2~0.35。</li>
 *   <li>{@code vector_similarity_weight}：0 纯关键词、1 纯向量。默认 0.3 为混合检索。</li>
 *   <li>{@code top_k}：精排前的候选数量（默认 1024），不是最终返回条数。</li>
 *   <li>{@code rerank_id}：精排模型，不传则不做精排。</li>
 * </ul>
 *
 * @author rag-platform
 */
@Component
public class RagFlowRetrievalClient {

    private static final Logger log = LoggerFactory.getLogger(RagFlowRetrievalClient.class);
    private static final int SUCCESS_CODE = 0;

    private final RestClient restClient;
    private final RagFlowProperties properties;

    public RagFlowRetrievalClient(RagFlowProperties properties) {
        this.properties = properties;
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofMillis(properties.getConnectTimeoutMs()));
        factory.setReadTimeout(Duration.ofMillis(properties.getReadTimeoutMs()));
        this.restClient = RestClient.builder()
                .baseUrl(properties.getBaseUrl())
                .requestFactory(factory)
                .defaultHeader(HttpHeaders.AUTHORIZATION, "Bearer " + properties.getApiKey())
                .build();
    }

    /**
     * 执行检索。
     *
     * @param datasetIds 知识库 dataset id 列表（<b>必须已由服务端根据权限推导</b>）
     * @param request    检索请求
     */
    public List<RetrievalResponse.Chunk> retrieve(List<String> datasetIds,
                                                  RetrievalRequest request) {
        if (datasetIds == null || datasetIds.isEmpty()) {
            return List.of();
        }

        RetrievalRequest.Options options = request.options() == null
                ? RetrievalRequest.Options.defaults() : request.options();
        RetrievalRequest.Filters filters = request.filters() == null
                ? RetrievalRequest.Filters.defaults() : request.filters();

        Map<String, Object> body = new HashMap<>();
        body.put("question", request.query());
        body.put("dataset_ids", datasetIds);
        body.put("page", 1);
        body.put("page_size", options.topN() == null ? 8 : options.topN());
        body.put("similarity_threshold",
                options.similarityThreshold() == null ? 0.2 : options.similarityThreshold());
        body.put("vector_similarity_weight",
                options.vectorSimilarityWeight() == null ? 0.3 : options.vectorSimilarityWeight());
        body.put("top_k", 1024);
        body.put("highlight", true);
        // keyword=true 启用关键词参与，与向量分数做混合
        body.put("keyword", true);
        if (Boolean.TRUE.equals(options.useRerank())) {
            body.put("rerank_id", properties.getDefaultRerankModel());
        }

        RagFlowResponse<RagFlowRetrievalData> response = restClient.post()
                .uri("/api/v1/retrieval")
                .contentType(MediaType.APPLICATION_JSON)
                .body(body)
                .retrieve()
                .body(new ParameterizedTypeReference<>() {
                });

        if (response == null || response.code() != SUCCESS_CODE) {
            log.error("RAGFlow 检索失败 query={} message={}", request.query(),
                    response == null ? null : response.message());
            throw BizException.of(ErrorCode.RAGFLOW_CALL_FAILED);
        }

        List<RetrievalResponse.Chunk> chunks = new ArrayList<>();
        if (response.data() != null && response.data().chunks() != null) {
            for (RagFlowChunk chunk : response.data().chunks()) {
                chunks.add(new RetrievalResponse.Chunk(
                        chunk.id(),
                        null,
                        null,
                        chunk.document_keyword(),
                        null,
                        chunk.positions() == null || chunk.positions().isEmpty() ? null : chunk.positions().get(0),
                        null,
                        chunk.content(),
                        chunk.similarity() == null ? 0.0 : chunk.similarity(),
                        chunk.vector_similarity(),
                        chunk.term_similarity()));
            }
        }
        log.info("RAGFlow 检索完成 datasetCount={} chunkCount={}", datasetIds.size(), chunks.size());
        return chunks;
    }

    /** RAGFlow 统一响应包装 */
    public record RagFlowResponse<T>(Integer code, String message, T data) {
    }

    /** RAGFlow 检索返回体 */
    public record RagFlowRetrievalData(List<RagFlowChunk> chunks, Object pagination) {
    }

    /** RAGFlow 召回片段 */
    public record RagFlowChunk(String id,
                               String content,
                               String document_id,
                               String document_keyword,
                               String dataset_id,
                               List<Integer> positions,
                               Double similarity,
                               Double vector_similarity,
                               Double term_similarity) {
    }
}
