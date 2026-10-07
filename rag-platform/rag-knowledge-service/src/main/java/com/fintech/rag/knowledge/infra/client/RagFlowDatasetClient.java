package com.fintech.rag.knowledge.infra.client;

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
 * RAGFlow Dataset（知识库）客户端。
 *
 * <p>RAGFlow 的 HTTP 接口统一返回 {@code {"code":0,"data":{...},"message":"..."}}，
 * {@code code != 0} 表示业务失败，必须显式判断，不能只看 HTTP 状态码。</p>
 *
 * @author rag-platform
 */
@Component
public class RagFlowDatasetClient {

    private static final Logger log = LoggerFactory.getLogger(RagFlowDatasetClient.class);
    private static final int SUCCESS_CODE = 0;

    private final RestClient restClient;
    private final RagFlowProperties properties;

    public RagFlowDatasetClient(RagFlowProperties properties) {
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
     * 创建 Dataset，返回 datasetId。
     *
     * <p>注意：RAGFlow 要求同一 Dataset 内向量模型一致，因此创建时就要定下来，
     * 后续不允许变更（变更需重建 Dataset 并重新入库）。</p>
     */
    public String createDataset(String name, String description, String embeddingModel,
                                String chunkMethod, Integer chunkTokenNum) {
        Map<String, Object> body = new HashMap<>();
        body.put("name", name);
        body.put("description", description == null ? "" : description);
        body.put("embedding_model", embeddingModel == null
                ? properties.getDefaultEmbeddingModel() : embeddingModel);
        body.put("chunk_method", chunkMethod == null ? "NAIVE" : chunkMethod);
        body.put("parser_config", Map.of("chunk_token_num", chunkTokenNum == null ? 512 : chunkTokenNum));

        RagFlowResponse<Object> response = restClient.post()
                .uri("/api/v1/datasets")
                .contentType(MediaType.APPLICATION_JSON)
                .body(body)
                .retrieve()
                .body(new ParameterizedTypeReference<>() {
                });

        String datasetId = extractDatasetId(response);
        if (datasetId == null) {
            log.error("创建 RAGFlow Dataset 失败 name={} message={}", name,
                    response == null ? null : response.message());
            throw BizException.of(ErrorCode.RAGFLOW_DATASET_SYNC_FAILED);
        }
        log.info("创建 RAGFlow Dataset 成功 name={} datasetId={}", name, datasetId);
        return datasetId;
    }

    /** 删除 Dataset（仅空库可删，RAGFlow 侧会校验） */
    public void deleteDataset(String datasetId) {
        RagFlowResponse<Object> response = restClient.delete()
                .uri("/api/v1/datasets")
                .contentType(MediaType.APPLICATION_JSON)
                .body(Map.of("ids", List.of(datasetId)))
                .retrieve()
                .body(new ParameterizedTypeReference<>() {
                });
        if (response == null || response.code() != SUCCESS_CODE) {
            throw BizException.of(ErrorCode.RAGFLOW_DATASET_SYNC_FAILED, "删除 Dataset 失败");
        }
    }

    @SuppressWarnings("unchecked")
    private String extractDatasetId(RagFlowResponse<Object> response) {
        if (response == null || response.code() != SUCCESS_CODE || response.data() == null) {
            return null;
        }
        Object data = response.data();
        try {
            if (data instanceof List<?> list && !list.isEmpty()) {
                Object first = list.get(0);
                if (first instanceof Map<?, ?> map && map.get("id") != null) {
                    return String.valueOf(map.get("id"));
                }
            }
            if (data instanceof Map<?, ?> map) {
                return map.get("id") == null ? null : String.valueOf(map.get("id"));
            }
        } catch (Exception ex) {
            log.warn("解析 Dataset 响应失败", ex);
        }
        return null;
    }

    /** RAGFlow 统一响应包装 */
    public record RagFlowResponse<T>(Integer code, String message, T data) {
    }

    /** 便于扩展：列出全部 dataset（运维排障用） */
    public List<String> listDatasetNames() {
        RagFlowResponse<Object> response = restClient.get()
                .uri("/api/v1/datasets?page=1&page_size=100")
                .retrieve()
                .body(new ParameterizedTypeReference<>() {
                });
        List<String> names = new ArrayList<>();
        if (response != null && response.data() instanceof List<?> list) {
            for (Object item : list) {
                if (item instanceof Map<?, ?> map && map.get("name") != null) {
                    names.add(String.valueOf(map.get("name")));
                }
            }
        }
        return names;
    }
}
