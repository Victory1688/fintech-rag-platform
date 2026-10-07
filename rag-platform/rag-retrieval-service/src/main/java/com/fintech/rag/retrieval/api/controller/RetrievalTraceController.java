package com.fintech.rag.retrieval.api.controller;

import com.fintech.rag.api.dto.replay.RetrievalTraceView;
import com.fintech.rag.common.core.R;
import com.fintech.rag.retrieval.app.service.RetrievalTraceQueryService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 检索日志查询接口（内网契约）。
 *
 * <p>路径刻意与 {@code RetrievalClient.findLogsByTrace} 的声明完全一致：
 * {@code /api/retrieval/logs/trace/{traceId}} —— 服务端直接暴露 {@code /api/**}，
 * 网关不做 RewritePath，内外网共用同一路径契约（见 docs/01 路径契约）。</p>
 *
 * <p>本接口不返回召回片段原文，只返回统计与范围：探针只有「查了什么、查到几段」，
 * 没有「查到了什么内容」。</p>
 *
 * @author rag-platform
 */
@RestController
@RequestMapping("/api/retrieval")
public class RetrievalTraceController {

    private final RetrievalTraceQueryService traceQueryService;

    public RetrievalTraceController(RetrievalTraceQueryService traceQueryService) {
        this.traceQueryService = traceQueryService;
    }

    /** 按 traceId 查询检索段（可能多条：多路召回或工具调用引发的二次检索） */
    @GetMapping("/logs/trace/{traceId}")
    public R<List<RetrievalTraceView>> byTrace(@PathVariable("traceId") String traceId) {
        return R.ok(traceQueryService.findByTrace(traceId));
    }
}
