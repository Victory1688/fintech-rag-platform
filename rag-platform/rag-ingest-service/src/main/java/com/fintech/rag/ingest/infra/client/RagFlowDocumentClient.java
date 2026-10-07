package com.fintech.rag.ingest.infra.client;

import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import com.fintech.rag.common.integration.ragflow.RagFlowProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestClient;

import java.time.Duration;
import java.util.Map;

/**
 * RAGFlow 文档客户端：上传、触发解析、查询解析状态。
 *
 * <p><b>关键认知：RAGFlow 的解析是异步的。</b>上传接口返回不等于解析完成，
 * 解析完成才可被检索。因此必须「上传 → 触发解析 → 轮询状态」三段式，
 * 上传完立刻提问必然召回为空。</p>
 *
 * @author rag-platform
 */
@Component
public class RagFlowDocumentClient {

    private static final Logger log = LoggerFactory.getLogger(RagFlowDocumentClient.class);
    private static final int SUCCESS_CODE = 0;

    private final RestClient uploadClient;

    public RagFlowDocumentClient(RagFlowProperties properties) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofMillis(properties.getConnectTimeoutMs()));
        factory.setReadTimeout(Duration.ofMillis(properties.getUploadTimeoutMs()));
        this.uploadClient = RestClient.builder()
                .baseUrl(properties.getBaseUrl())
                .requestFactory(factory)
                .defaultHeader(HttpHeaders.AUTHORIZATION, "Bearer " + properties.getApiKey())
                .build();
    }

    /**
     * 上传文档到指定 Dataset。
     *
     * @return RAGFlow 文档 ID
     */
    public String uploadDocument(String datasetId, String fileName, byte[] content) {
        MultiValueMap<String, Object> form = new LinkedMultiValueMap<>();
        form.add("file", new ByteArrayResource(content) {
            @Override
            public String getFilename() {
                return fileName;
            }
        });

        RagFlowResponse<Object> response = uploadClient.post()
                .uri("/api/v1/datasets/{datasetId}/documents", datasetId)
                .contentType(MediaType.MULTIPART_FORM_DATA)
                .body(form)
                .retrieve()
                .body(new ParameterizedTypeReference<>() {
                });

        String documentId = extractFirstId(response);
        if (documentId == null) {
            log.error("上传文档到 RAGFlow 失败 datasetId={} fileName={}", datasetId, fileName);
            throw BizException.of(ErrorCode.RAGFLOW_CALL_FAILED, "上传文档失败");
        }
        log.info("上传文档成功 datasetId={} fileName={} documentId={}", datasetId, fileName, documentId);
        return documentId;
    }

    /** 触发解析（分片 + 向量化） */
    public void startParsing(String datasetId, String documentId) {
        RagFlowResponse<Object> response = uploadClient.post()
                .uri("/api/v1/datasets/{datasetId}/chunks", datasetId)
                .contentType(MediaType.APPLICATION_JSON)
                .body(Map.of("document_ids", java.util.List.of(documentId)))
                .retrieve()
                .body(new ParameterizedTypeReference<>() {
                });
        if (response == null || response.code() != SUCCESS_CODE) {
            throw BizException.of(ErrorCode.RAGFLOW_CALL_FAILED, "触发解析失败");
        }
    }

    /**
     * 查询文档解析状态。
     *
     * @return RAGFlow 的 run 状态：UNSTART / RUNNING / DONE / FAIL
     */
    public String queryRunStatus(String datasetId, String documentId) {
        RagFlowResponse<Object> response = uploadClient.get()
                .uri("/api/v1/datasets/{datasetId}/documents?id={documentId}", datasetId, documentId)
                .retrieve()
                .body(new ParameterizedTypeReference<>() {
                });
        String status = extractField(response, "run");
        return status == null ? "UNSTART" : status;
    }

    /** 查询已生成的分片数量 */
    public int queryChunkCount(String datasetId, String documentId) {
        RagFlowResponse<Object> response = uploadClient.get()
                .uri("/api/v1/datasets/{datasetId}/documents?id={documentId}", datasetId, documentId)
                .retrieve()
                .body(new ParameterizedTypeReference<>() {
                });
        String value = extractField(response, "chunk_count");
        try {
            return value == null ? 0 : Integer.parseInt(value);
        } catch (NumberFormatException ex) {
            return 0;
        }
    }

    /** 从 RAGFlow 文档中摘除可检索状态（文档下线） */
    public void disableDocument(String datasetId, String documentId) {
        RagFlowResponse<Object> response = uploadClient.put()
                .uri("/api/v1/datasets/{datasetId}/documents/{documentId}", datasetId, documentId)
                .contentType(MediaType.APPLICATION_JSON)
                .body(Map.of("chunk_method", "NAIVE"))
                .retrieve()
                .body(new ParameterizedTypeReference<>() {
                });
        if (response == null || response.code() != SUCCESS_CODE) {
            throw BizException.of(ErrorCode.RAGFLOW_CALL_FAILED, "文档下线失败");
        }
    }

    @SuppressWarnings("unchecked")
    private String extractFirstId(RagFlowResponse<Object> response) {
        if (response == null || response.code() != SUCCESS_CODE || response.data() == null) {
            return null;
        }
        Object data = response.data();
        if (data instanceof java.util.List<?> list && !list.isEmpty()) {
            Object first = list.get(0);
            if (first instanceof Map<?, ?> map && map.get("id") != null) {
                return String.valueOf(map.get("id"));
            }
        }
        return null;
    }

    @SuppressWarnings("unchecked")
    private String extractField(RagFlowResponse<Object> response, String field) {
        if (response == null || response.data() == null) {
            return null;
        }
        Object data = response.data();
        if (data instanceof java.util.List<?> list && !list.isEmpty()) {
            data = list.get(0);
        }
        if (data instanceof Map<?, ?> map && map.get(field) != null) {
            return String.valueOf(map.get(field));
        }
        if (data instanceof Map<?, ?> map && map.get("docs") instanceof java.util.List<?> docs
                && !docs.isEmpty() && docs.get(0) instanceof Map<?, ?> doc && doc.get(field) != null) {
            return String.valueOf(doc.get(field));
        }
        return null;
    }

    /** RAGFlow 统一响应 */
    public record RagFlowResponse<T>(Integer code, String message, T data) {
    }
}
