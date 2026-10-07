package com.fintech.rag.retrieval.app.service;

import com.fintech.rag.api.client.KnowledgeClient;
import com.fintech.rag.api.dto.knowledge.DocumentMeta;
import com.fintech.rag.api.dto.knowledge.KbBrief;
import com.fintech.rag.api.dto.retrieval.RetrievalRequest;
import com.fintech.rag.api.dto.retrieval.RetrievalResponse;
import com.fintech.rag.common.core.R;
import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import com.fintech.rag.common.observability.GenAiSemconv;
import com.fintech.rag.common.observability.RagOutcome;
import com.fintech.rag.retrieval.app.cache.RetrievalCacheKeyBuilder;
import com.fintech.rag.retrieval.app.filter.ChunkBusinessFilter;
import com.fintech.rag.retrieval.app.metric.RetrievalMetrics;
import com.fintech.rag.retrieval.app.query.QueryRewriter;
import com.fintech.rag.retrieval.domain.model.RetrievalLog;
import com.fintech.rag.retrieval.infra.client.RagFlowRetrievalClient;
import com.fintech.rag.retrieval.infra.persistence.mapper.RetrievalLogMapper;
import io.micrometer.tracing.Span;
import io.micrometer.tracing.Tracer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * 检索应用服务 —— 检索链路的唯一编排点。
 *
 * <p><b>执行顺序（顺序即安全，不可调整）：</b></p>
 * <ol>
 *   <li>向 platform / knowledge 取「授权知识库真源」，与请求意图取交集 → dataset 白名单</li>
 *   <li>Query 改写</li>
 *   <li>查缓存（Key 已包含权限指纹）</li>
 *   <li>调 RAGFlow 检索</li>
 *   <li>业务过滤（密级 / 生效期 / 越权 / 去重）</li>
 *   <li>写检索日志（合规审计 + 运营分析）</li>
 * </ol>
 *
 * <p><b>可观测设计</b>：本服务产出 GenAI 规范中的 {@code retrieval} span（v1.40 起定义），
 * 并把「缓存命中 / 原始召回数 / 最终召回数 / 最高分」写入 span 与指标。
 * 这样在 LangFuse 里看到某次回答质量差时，可以直接判断是「没召回到」还是「召回了但没用上」。</p>
 *
 * @author rag-platform
 */
@Service
public class RetrievalAppService {

    private static final Logger log = LoggerFactory.getLogger(RetrievalAppService.class);
    /** 空召回不得缓存过久：知识库补文档后用户应尽快能查到 */
    private static final Duration EMPTY_HIT_TTL = Duration.ofMinutes(2);
    private static final Duration CACHE_TTL = Duration.ofMinutes(10);

    private final KnowledgeClient knowledgeClient;
    private final RagFlowRetrievalClient ragFlowClient;
    private final QueryRewriter queryRewriter;
    private final ChunkBusinessFilter businessFilter;
    private final RetrievalCacheKeyBuilder cacheKeyBuilder;
    private final StringRedisTemplate redisTemplate;
    private final RetrievalLogMapper retrievalLogMapper;
    private final RetrievalMetrics metrics;
    private final ObjectProvider<Tracer> tracerProvider;

    public RetrievalAppService(KnowledgeClient knowledgeClient,
                               RagFlowRetrievalClient ragFlowClient,
                               QueryRewriter queryRewriter,
                               ChunkBusinessFilter businessFilter,
                               RetrievalCacheKeyBuilder cacheKeyBuilder,
                               StringRedisTemplate redisTemplate,
                               RetrievalLogMapper retrievalLogMapper,
                               RetrievalMetrics metrics,
                               ObjectProvider<Tracer> tracerProvider) {
        this.knowledgeClient = knowledgeClient;
        this.ragFlowClient = ragFlowClient;
        this.queryRewriter = queryRewriter;
        this.businessFilter = businessFilter;
        this.cacheKeyBuilder = cacheKeyBuilder;
        this.redisTemplate = redisTemplate;
        this.retrievalLogMapper = retrievalLogMapper;
        this.metrics = metrics;
        this.tracerProvider = tracerProvider;
    }

    public RetrievalResponse search(RetrievalRequest request, String roleCodes, Long deptId) {
        long start = System.currentTimeMillis();
        String appSource = resolveAppSource();
        Span span = startSpan();
        boolean cacheHit = false;
        int rawChunkCount = 0;
        try {
            // ---------- 1. 授权真源（越权防护的根本） ----------
            List<KbBrief> authorizedKbs = fetchAuthorizedKbs(request.subjectType().name(),
                    request.subjectId(), roleCodes, deptId);
            if (authorizedKbs.isEmpty()) {
                log.info("主体无任何授权知识库 subjectId={}", request.subjectId());
                return abort(span, request, appSource, cacheHit, rawChunkCount, start);
            }

            Set<Long> authorizedKbIds = authorizedKbs.stream()
                    .filter(kb -> kb.docCount() != null && kb.docCount() > 0)
                    .map(KbBrief::kbId)
                    .collect(Collectors.toSet());

            // 请求中的 kbIds 只作为「缩小范围的意图」，必须与授权集合取交集
            if (request.kbIds() != null && !request.kbIds().isEmpty()) {
                Set<Long> intent = new HashSet<>(request.kbIds());
                authorizedKbIds.retainAll(intent);
            }
            if (authorizedKbIds.isEmpty()) {
                return abort(span, request, appSource, cacheHit, rawChunkCount, start);
            }
            tag(span, GenAiSemconv.ATTR_KB_COUNT, authorizedKbIds.size());

            String bizChannel = request.filters() == null ? null : request.filters().bizChannel();
            String rewrittenQuery = queryRewriter.rewrite(request.query(), bizChannel);

            // ---------- 2. 缓存 ----------
            Map<String, Long> kbVersions = fetchKbVersions(authorizedKbIds);
            int userSecretLevel = request.filters() != null && request.filters().secretLevelMax() != null
                    ? request.filters().secretLevelMax() : 2;
            String cacheKey = cacheKeyBuilder.build(
                    authorizedKbIds.stream().map(String::valueOf).collect(Collectors.toList()),
                    kbVersions,
                    cacheKeyBuilder.normalizeQuery(rewrittenQuery),
                    filtersFingerprint(request),
                    userSecretLevel,
                    optionsFingerprint(request));

            // 骨架：缓存读写用 JSON 序列化，此处仅示范 Key 与命中判断
            String cached = redisTemplate.opsForValue().get(cacheKey);
            if (cached != null) {
                cacheHit = true;
                log.debug("检索缓存命中 key={}", cacheKey);
            }
            tag(span, GenAiSemconv.ATTR_CACHE_HIT, String.valueOf(cacheHit));

            // ---------- 3. 调用 RAGFlow ----------
            // datasetIds 来自授权知识库的映射，绝不使用请求体中的值
            List<String> datasetIds = fetchDatasetIds(authorizedKbIds);
            long ragFlowStart = System.currentTimeMillis();
            List<RetrievalResponse.Chunk> rawChunks =
                    ragFlowClient.retrieve(datasetIds, new RetrievalRequest(
                            rewrittenQuery, request.subjectType(), request.subjectId(),
                            request.kbIds(), request.filters(), request.options(),
                            request.traceId(), request.conversationId()));
            int ragFlowCost = (int) (System.currentTimeMillis() - ragFlowStart);
            rawChunkCount = rawChunks == null ? 0 : rawChunks.size();
            tag(span, GenAiSemconv.ATTR_RAW_CHUNK_COUNT, rawChunkCount);

            // ---------- 4. 业务过滤 ----------
            Map<Long, DocumentMeta> docMetaMap = fetchDocumentMeta(rawChunks);
            List<RetrievalResponse.Chunk> filtered = businessFilter.filter(
                    rawChunks, docMetaMap, request, authorizedKbIds, userSecretLevel);
            filtered = filtered.stream()
                    .limit(request.options() == null || request.options().topN() == null
                            ? 8 : request.options().topN())
                    .collect(Collectors.toList());

            boolean emptyHit = filtered.isEmpty();
            int cost = (int) (System.currentTimeMillis() - start);

            // ---------- 5. 审计日志 ----------
            writeLog(request, rewrittenQuery, authorizedKbIds, filtered, ragFlowCost, cost, rawChunks.size());

            Double topScore = filtered.isEmpty() || filtered.get(0).score() == null
                    ? null : filtered.get(0).score();
            tag(span, GenAiSemconv.ATTR_CHUNK_COUNT, filtered.size());
            tag(span, GenAiSemconv.ATTR_TOP_SCORE, topScore);
            RagOutcome outcome = emptyHit ? RagOutcome.NO_HIT : RagOutcome.ANSWERED;
            tag(span, GenAiSemconv.ATTR_OUTCOME, outcome.name());

            metrics.record(appSource, cacheHit, outcome,
                    rawChunkCount, filtered.size(), topScore, ragFlowCost);

            if (emptyHit) {
                redisTemplate.opsForValue().set(cacheKey, "EMPTY", EMPTY_HIT_TTL);
                return RetrievalResponse.empty(request.query(), rewrittenQuery, cost);
            }
            return new RetrievalResponse(request.query(), rewrittenQuery, filtered, false, false, cost);
        } catch (RuntimeException ex) {
            tag(span, GenAiSemconv.ATTR_OUTCOME, RagOutcome.ERROR.name());
            tag(span, GenAiSemconv.ATTR_ERROR_TYPE, ex.getClass().getName());
            error(span, ex);
            metrics.record(appSource, cacheHit, RagOutcome.ERROR, rawChunkCount, 0, null, 0);
            throw ex;
        } finally {
            endSpan(span);
        }
    }

    // ------------------------------------------------------------------ 辅助
    private RetrievalResponse abort(Span span, RetrievalRequest request, String appSource,
                                    boolean cacheHit, int rawChunkCount, long start) {
        tag(span, GenAiSemconv.ATTR_OUTCOME, RagOutcome.NO_HIT.name());
        metrics.record(appSource, cacheHit, RagOutcome.NO_HIT, rawChunkCount, 0, null, 0);
        return RetrievalResponse.empty(request.query(), request.query(),
                System.currentTimeMillis() - start);
    }

    /**
     * 开启检索 span。
     *
     * <p>未引入追踪依赖时返回 {@code null}，由下方的 null 安全辅助方法兜住 ——
     * 刻意<b>不</b>自己实现一个空 Span：Micrometer {@code Span} 接口在不同版本间
     * 抽象方法不一致，自实现会带来编译期脆弱性（升级即报错），
     * 而 null + 辅助方法更简单也更稳。</p>
     */
    private Span startSpan() {
        Tracer tracer = tracerProvider.getIfAvailable();
        if (tracer == null) {
            return null;
        }
        Span span = tracer.nextSpan().name(GenAiSemconv.SPAN_BUSINESS_RETRIEVAL).start();
        span.tag(GenAiSemconv.ATTR_OPERATION_NAME, GenAiSemconv.OP_RETRIEVAL);
        return span;
    }

    private void tag(Span span, String key, String value) {
        if (span != null && value != null) {
            span.tag(key, value);
        }
    }

    private void tag(Span span, String key, int value) {
        if (span != null) {
            span.tag(key, (long) value);
        }
    }

    private void tag(Span span, String key, Double value) {
        if (span != null && value != null) {
            span.tag(key, value);
        }
    }

    private void error(Span span, Throwable throwable) {
        if (span != null) {
            span.error(throwable);
        }
    }

    private void endSpan(Span span) {
        if (span != null) {
            span.end();
        }
    }

    /** 请求来源（DMZ_WEB / SF_INNER_APP）：用于「外网用户流量 vs 内网应用流量」分开统计 */
    private String resolveAppSource() {
        com.fintech.rag.common.context.RequestSource source =
                com.fintech.rag.common.context.RequestContext.currentSource();
        return source == null ? "UNKNOWN" : source.name();
    }

    private List<KbBrief> fetchAuthorizedKbs(String subjectType, String subjectId,
                                             String roleCodes, Long deptId) {
        R<List<KbBrief>> result = knowledgeClient.listAuthorizedKbs(subjectType, subjectId, roleCodes, deptId);
        if (result == null || !result.isSuccess() || result.getData() == null) {
            // fail-close：授权不可得时拒绝检索，绝不退化为「全量知识库」
            throw BizException.of(ErrorCode.KB_NO_PERMISSION, "知识库授权信息获取失败");
        }
        return result.getData();
    }

    private Map<String, Long> fetchKbVersions(Set<Long> kbIds) {
        R<Map<String, Long>> result = knowledgeClient.getKbVersions(List.copyOf(kbIds));
        return result != null && result.isSuccess() && result.getData() != null
                ? result.getData() : Map.of();
    }

    private Map<Long, DocumentMeta> fetchDocumentMeta(List<RetrievalResponse.Chunk> chunks) {
        List<Long> docIds = chunks.stream()
                .map(RetrievalResponse.Chunk::docId)
                .filter(java.util.Objects::nonNull)
                .distinct()
                .collect(Collectors.toList());
        if (docIds.isEmpty()) {
            return Map.of();
        }
        R<List<DocumentMeta>> result = knowledgeClient.listDocumentMeta(docIds);
        if (result == null || !result.isSuccess() || result.getData() == null) {
            return Map.of();
        }
        Map<Long, DocumentMeta> map = new HashMap<>();
        result.getData().forEach(meta -> map.put(meta.docId(), meta));
        return map;
    }

    /**
     * TODO 由 knowledge 服务提供「kbId -> ragflowDatasetId」批量查询接口。
     * 骨架阶段先返回空列表并记录告警，避免实现出「用 kbId 当 datasetId」的隐性 bug。
     */
    private List<String> fetchDatasetIds(Set<Long> kbIds) {
        log.debug("待接入 kbId -> datasetId 映射查询 kbIds={}", kbIds);
        return List.of();
    }

    private String filtersFingerprint(RetrievalRequest request) {
        RetrievalRequest.Filters f = request.filters();
        if (f == null) {
            return "D";
        }
        return String.valueOf(java.util.Objects.hash(
                f.secretLevelMax(), f.effectiveOnly(), f.bizChannel(), f.productCode()));
    }

    private String optionsFingerprint(RetrievalRequest request) {
        RetrievalRequest.Options o = request.options();
        if (o == null) {
            return "D";
        }
        return String.valueOf(java.util.Objects.hash(
                o.topN(), o.similarityThreshold(), o.vectorSimilarityWeight(), o.useRerank()));
    }

    private void writeLog(RetrievalRequest request, String rewrittenQuery, Set<Long> kbIds,
                          List<RetrievalResponse.Chunk> chunks, int ragFlowCost, int cost, int rawCount) {
        try {
            RetrievalLog entity = new RetrievalLog();
            entity.setTenantId(0L);
            entity.setTraceId(request.traceId());
            entity.setConversationId(request.conversationId());
            entity.setSubjectType(request.subjectType().name());
            entity.setSubjectId(request.subjectId());
            entity.setOriginalQuery(truncate(request.query(), 1000));
            entity.setRewrittenQuery(truncate(rewrittenQuery, 1000));
            entity.setKbIds(kbIds.toString());
            entity.setChunkCount(chunks.size());
            entity.setTopScore(chunks.isEmpty() || chunks.get(0).score() == null
                    ? null : java.math.BigDecimal.valueOf(chunks.get(0).score()));
            entity.setCacheHit(0);
            entity.setRerankUsed(1);
            entity.setCostMs(cost);
            entity.setRagflowCostMs(ragFlowCost);
            entity.setResult(rawCount >= 0 ? 1 : 0);
            retrievalLogMapper.insert(entity);
        } catch (Exception ex) {
            // 审计日志写失败不得影响检索主链路
            log.error("写入检索日志失败", ex);
        }
    }

    private String truncate(String value, int max) {
        if (value == null) {
            return null;
        }
        return value.length() <= max ? value : value.substring(0, max);
    }
}
