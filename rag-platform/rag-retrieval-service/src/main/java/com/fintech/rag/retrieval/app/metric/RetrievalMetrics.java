package com.fintech.rag.retrieval.app.metric;

import com.fintech.rag.common.observability.GenAiSemconv;
import com.fintech.rag.common.observability.RagOutcome;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.stereotype.Component;

import java.time.Duration;

/**
 * 检索指标 —— 空召回率是 RAG 系统最重要的质量信号。
 *
 * <p><b>为什么空召回率必须单独告警</b>：空召回意味着「知识库里没有」，
 * 用户看到的是兜底话术。它上升通常意味着两件事之一：① 知识库缺文档；
 * ② 检索参数或解析质量劣化。无论哪一种，只看「接口成功率」都发现不了 ——
 * 因为空召回在接口层是一次 200 成功。</p>
 *
 * @author rag-platform
 */
@Component
public class RetrievalMetrics {

    private final MeterRegistry meterRegistry;

    public RetrievalMetrics(MeterRegistry meterRegistry) {
        this.meterRegistry = meterRegistry;
    }

    /**
     * 记录一次检索。
     *
     * @param appSource   请求来源（DMZ_WEB / SF_INNER_APP）
     * @param cacheHit    是否命中缓存
     * @param outcome     结果归因
     * @param rawChunks   RAGFlow 原始召回数
     * @param finalChunks 业务过滤后的最终召回数
     * @param topScore    最高相似度（可为 null）
     * @param ragflowMs   RAGFlow 调用耗时
     */
    public void record(String appSource, boolean cacheHit, RagOutcome outcome,
                       int rawChunks, int finalChunks, Double topScore, long ragflowMs) {
        String source = appSource == null ? "unknown" : appSource;
        String hit = cacheHit ? "true" : "false";

        meterRegistry.counter(GenAiSemconv.METRIC_RETRIEVAL_TOTAL,
                        GenAiSemconv.TAG_OUTCOME, outcome.name(),
                        GenAiSemconv.TAG_APP_SOURCE, source,
                        GenAiSemconv.ATTR_CACHE_HIT, hit)
                .increment();

        if (outcome == RagOutcome.NO_HIT) {
            meterRegistry.counter(GenAiSemconv.METRIC_RETRIEVAL_EMPTY_TOTAL,
                            GenAiSemconv.TAG_APP_SOURCE, source)
                    .increment();
        }

        meterRegistry.summary(GenAiSemconv.METRIC_RETRIEVAL_CHUNKS,
                        GenAiSemconv.TAG_APP_SOURCE, source,
                        GenAiSemconv.ATTR_CACHE_HIT, hit)
                .record(finalChunks);

        if (ragflowMs > 0) {
            meterRegistry.timer("rag_retrieval_ragflow_duration",
                            GenAiSemconv.TAG_APP_SOURCE, source)
                    .record(Duration.ofMillis(ragflowMs));
        }
    }
}
