package com.fintech.rag.api.client;

import com.fintech.rag.api.dto.replay.RetrievalTraceView;
import com.fintech.rag.api.dto.retrieval.RetrievalRequest;
import com.fintech.rag.api.dto.retrieval.RetrievalResponse;
import com.fintech.rag.common.core.R;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;

import java.util.List;

/**
 * 检索服务契约。
 *
 * <p>调用方：rag-chat-service、检索工作台、内网业务微服务。</p>
 *
 * <p><strong>降级策略：fail-close。</strong>检索不可用时返回「服务繁忙」，
 * 绝不可降级为「不检索直接让大模型自由作答」——这等同于放弃引用与合规底线。</p>
 *
 * <p><strong>回放查询的降级策略：fail-open（与检索相反）。</strong>
 * 检索段拿不到时，回放视图仍应返回消息、token 用量与评估分数，
 * 并把缺失原因显式写在 {@code degraded} 里。诊断工具的价值就在于
 * 「依赖挂了也要能看」，此处若 fail-close 反而使问题更难定位。</p>
 *
 * @author rag-platform
 */
@FeignClient(name = "rag-retrieval-service", contextId = "retrievalClient", path = "/api/retrieval")
public interface RetrievalClient {

    /** 执行检索 */
    @PostMapping("/search")
    R<RetrievalResponse> search(@RequestBody RetrievalRequest request);

    /**
     * 按 traceId 查询检索日志（回放用）。
     *
     * <p>为什么是一次可能返回多条的查询：一次用户请求在某些编排下可能触发多次检索
     * （多路召回、工具调用引发的二次检索），运营看到「多条」本身就是有效信息。</p>
     */
    @GetMapping("/logs/trace/{traceId}")
    R<List<RetrievalTraceView>> findLogsByTrace(@PathVariable("traceId") String traceId);
}
