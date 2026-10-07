package com.fintech.rag.api.client;

import com.fintech.rag.api.dto.retrieval.RetrievalRequest;
import com.fintech.rag.api.dto.retrieval.RetrievalResponse;
import com.fintech.rag.common.core.R;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;

/**
 * 检索服务契约。
 *
 * <p>调用方：rag-chat-service、检索工作台、内网业务微服务。</p>
 *
 * <p><strong>降级策略：fail-close。</strong>检索不可用时返回「服务繁忙」，
 * 绝不可降级为「不检索直接让大模型自由作答」——这等同于放弃引用与合规底线。</p>
 *
 * @author rag-platform
 */
@FeignClient(name = "rag-retrieval-service", contextId = "retrievalClient", path = "/api/retrieval")
public interface RetrievalClient {

    /** 执行检索 */
    @PostMapping("/search")
    R<RetrievalResponse> search(@RequestBody RetrievalRequest request);
}
