# -*- coding: utf-8 -*-
"""
S17 · retrieval 侧：修掉检索日志的 4 个真 bug，并提供按 traceId 查询。

改造前 t_retrieval_log 的实际写入情况（全部是「看着有、实际不对」）：

  bug 1  空召回（含「无授权知识库」这一分支）**完全不落日志**。
         而空召回率是知识库覆盖度的核心指标，运营全靠它找知识缺口 ——
         最该被记录的一类结果，恰恰一条都没记。
  bug 2  cache_hit 硬编码 0。上面刚算出来的 cacheHit 变量根本没被用上，
         于是「缓存命中率」这个看板永远是 0。
  bug 3  rerank_used 硬编码 1，result 写成 `rawCount >= 0 ? 1 : 0`
         （rawCount 恒 >= 0，所以 result 恒为 1，永远看不到失败）。
  bug 4  trace_id 取的是**请求体里客户端传来的值**。审计字段的权威来源必须是
         服务端实际链路，取客户端值意味着「填什么就记什么」——
         出现问题时这条检索记录可能根本关联不到真实链路。

另外补上：filter_json 落库、异常路径也写日志（否则「检索报错」在库里毫无痕迹）。

产出：
  1) retrieval/app/service/RetrievalTraceQueryService.java   按 traceId 查询（内容档位受控）
  2) retrieval/api/controller/RetrievalTraceController.java  GET /api/retrieval/logs/trace/{traceId}
  3) retrieval/app/service/RetrievalAppService.java（覆盖写）

口径定义（同步写入 docs/03）：
  result = 1 表示「检索流程正常完成」——**包含空召回**；
  result = 0 表示「检索失败」。这样空召回（result=1, chunk_count=0）
  与检索报错（result=0）在库里就能分开，运营不会把「报错」误判成「知识缺口」。

幂等：覆盖写。
"""
import pathlib

ROOT = pathlib.Path(r"D:/AiWorkOut/java-ai")
RET = ROOT / "rag-platform/rag-retrieval-service/src/main/java/com/fintech/rag/retrieval"

written = []


def w(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    written.append(path)
    print("W +", path.relative_to(ROOT).as_posix())


# ============================================== 1 RetrievalTraceQueryService
w(RET / "app/service/RetrievalTraceQueryService.java", r'''package com.fintech.rag.retrieval.app.service;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.fintech.rag.api.dto.replay.RetrievalTraceView;
import com.fintech.rag.common.observability.ContentSanitizer;
import com.fintech.rag.retrieval.domain.model.RetrievalLog;
import com.fintech.rag.retrieval.infra.persistence.mapper.RetrievalLogMapper;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;

/**
 * 检索日志的按 traceId 查询 —— 供「按 traceId 一键回放」使用。
 *
 * <p><b>为什么查询侧也要过一遍脱敏</b>：库里存的是检索当时的原始问题与改写式，
 * 它们是用户输入的一部分。回放接口把它们直接返回，等于给「查看用户提问原文」
 * 开了一个绕过内容档位的后门。因此这里统一走
 * {@link ContentSanitizer#forReporting}，档位为 METRICS_ONLY 时
 * 返回 null —— <b>返回 null（字段不出现）比返回掩码后的文本更安全</b>，
 * 因为掩码规则总有疏漏的可能，而「不传」没有疏漏。</p>
 *
 * <p><b>为什么不做分页</b>：单条 traceId 下的检索次数天然有限（多路召回也就几条到几十条）。
 * 加一个「上限保护」即可，引入分页参数只会让调用方多写一层无意义的分页处理。</p>
 *
 * @author rag-platform
 */
@Service
public class RetrievalTraceQueryService {

    /** 单次回放最多返回的检索记录条数：防御「异常编排导致同一 traceId 下产生海量记录」 */
    private static final int MAX_ROWS = 50;

    private final RetrievalLogMapper retrievalLogMapper;
    private final ContentSanitizer sanitizer;

    public RetrievalTraceQueryService(RetrievalLogMapper retrievalLogMapper,
                                      ContentSanitizer sanitizer) {
        this.retrievalLogMapper = retrievalLogMapper;
        this.sanitizer = sanitizer;
    }

    /** 按 traceId 查询检索日志（时间正序：先发生的检索在前，符合阅读习惯） */
    public List<RetrievalTraceView> findByTrace(String traceId) {
        if (traceId == null || traceId.isBlank()) {
            return List.of();
        }
        List<RetrievalLog> logs = retrievalLogMapper.selectList(Wrappers.<RetrievalLog>lambdaQuery()
                .eq(RetrievalLog::getTraceId, traceId)
                .orderByAsc(RetrievalLog::getCreateTime)
                .last("limit " + MAX_ROWS));

        List<RetrievalTraceView> views = new ArrayList<>(logs.size());
        for (RetrievalLog log : logs) {
            views.add(new RetrievalTraceView(
                    log.getTraceId(),
                    log.getConversationId(),
                    log.getSubjectType(),
                    // 受内容档位控制：METRICS_ONLY 下为 null（字段不出现，而非掩码）
                    sanitizer.forReporting(log.getOriginalQuery()),
                    sanitizer.forReporting(log.getRewrittenQuery()),
                    log.getKbIds(),
                    log.getChunkCount(),
                    log.getTopScore(),
                    log.getCacheHit(),
                    log.getRerankUsed(),
                    log.getCostMs(),
                    log.getRagflowCostMs(),
                    log.getResult(),
                    log.getErrorCode(),
                    log.getCreateTime()));
        }
        return views;
    }
}
''')

# ============================================== 2 RetrievalTraceController
w(RET / "api/controller/RetrievalTraceController.java", r'''package com.fintech.rag.retrieval.api.controller;

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
''')

# ============================================== 3 RetrievalAppService（改）
w(RET / "app/service/RetrievalAppService.java", r'''package com.fintech.rag.retrieval.app.service;

import com.fintech.rag.api.client.KnowledgeClient;
import com.fintech.rag.api.dto.knowledge.DocumentMeta;
import com.fintech.rag.api.dto.knowledge.KbBrief;
import com.fintech.rag.api.dto.retrieval.RetrievalRequest;
import com.fintech.rag.api.dto.retrieval.RetrievalResponse;
import com.fintech.rag.common.context.RequestContext;
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
 * <p><b>检索日志的职责（本次重点修正）</b>：{@code t_retrieval_log} 是
 * 「空召回率 / 缓存命中率 / Top5 命中率」的唯一数据来源，也是运营发现知识缺口的主要线索。
 * 因此<b>所有出口路径都必须落日志</b>，包括「无授权知识库」与「检索异常」这两条
 * 以前被漏掉的路径 —— 前者是越权尝试或授权配置缺失的证据，后者是故障留痕。</p>
 *
 * <p><b>trace_id 的权威来源</b>：一律取本服务链路中的实际 traceId
 * （{@code RequestContext.currentTraceId()}，由 OTel 生成）。
 * 请求体里的 {@code traceId} 只作为兜底 —— 审计字段若采用调用方传入的值，
 * 就等于「填什么就记什么」，出现问题时这条记录可能关联不到真实链路。</p>
 *
 * @author rag-platform
 */
@Service
public class RetrievalAppService {

    private static final Logger log = LoggerFactory.getLogger(RetrievalAppService.class);
    /** 空召回不得缓存过久：知识库补文档后用户应尽快能查到 */
    private static final Duration EMPTY_HIT_TTL = Duration.ofMinutes(2);
    private static final Duration CACHE_TTL = Duration.ofMinutes(10);

    /** 检索日志 result 口径：1 = 流程正常完成（含空召回）；0 = 检索失败 */
    private static final int RESULT_OK = 1;
    private static final int RESULT_FAIL = 0;

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
        // traceId 以本服务链路为准，请求体值仅兜底（详见类注释）
        String traceId = resolveTraceId(request);
        Span span = startSpan();
        boolean cacheHit = false;
        boolean rerankUsed = request.options() != null && Boolean.TRUE.equals(request.options().useRerank());
        int rawChunkCount = 0;
        try {
            // ---------- 1. 授权真源（越权防护的根本） ----------
            List<KbBrief> authorizedKbs = fetchAuthorizedKbs(request.subjectType().name(),
                    request.subjectId(), roleCodes, deptId);
            if (authorizedKbs.isEmpty()) {
                log.info("主体无任何授权知识库 subjectId={}", request.subjectId());
                return abort(span, request, appSource, traceId, cacheHit, rerankUsed,
                        rawChunkCount, start, ErrorCode.KB_NO_PERMISSION.getCode());
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
                // 有授权但交集为空：属于「用户勾选范围超出了自己的授权」，
                // 必须留痕 —— 这是权限模型是否被正确理解的重要信号
                return abort(span, request, appSource, traceId, cacheHit, rerankUsed,
                        rawChunkCount, start, ErrorCode.KB_NO_PERMISSION.getCode());
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
                            traceId, request.conversationId()));
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

            // ---------- 5. 检索日志（成功路径，含空召回） ----------
            writeLog(request, traceId, rewrittenQuery, authorizedKbIds, filtered,
                    cacheHit, rerankUsed, ragFlowCost, cost, RESULT_OK, null);

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
            return new RetrievalResponse(request.query(), rewrittenQuery, filtered, false, cacheHit, cost);
        } catch (RuntimeException ex) {
            int cost = (int) (System.currentTimeMillis() - start);
            tag(span, GenAiSemconv.ATTR_OUTCOME, RagOutcome.ERROR.name());
            tag(span, GenAiSemconv.ATTR_ERROR_TYPE, ex.getClass().getName());
            error(span, ex);
            metrics.record(appSource, cacheHit, RagOutcome.ERROR, rawChunkCount, 0, null, 0);
            // 失败路径同样必须落日志：否则「检索报错」在库里没有任何痕迹，
            // 运营会把故障期的流量缺口误读成「知识库覆盖度突然变好」
            writeLog(request, traceId, null, Set.of(), List.of(),
                    cacheHit, rerankUsed, 0, cost, RESULT_FAIL, errorCodeOf(ex));
            throw ex;
        } finally {
            endSpan(span);
        }
    }

    // ------------------------------------------------------------------ 辅助
    /**
     * 中止路径（无授权 / 授权与意图无交集）。
     *
     * <p><b>以前这里不落日志，是本次修正的重点</b>：这条路径正是「越权尝试」
     * 与「知识库 ACL 配置缺失」的唯一线索，不落日志等于把最需要审计的行为漏掉了。</p>
     */
    private RetrievalResponse abort(Span span, RetrievalRequest request, String appSource,
                                    String traceId, boolean cacheHit, boolean rerankUsed,
                                    int rawChunkCount, long start, String errorCode) {
        long cost = System.currentTimeMillis() - start;
        tag(span, GenAiSemconv.ATTR_OUTCOME, RagOutcome.NO_HIT.name());
        metrics.record(appSource, cacheHit, RagOutcome.NO_HIT, rawChunkCount, 0, null, 0);
        writeLog(request, traceId, null, Set.of(), List.of(),
                cacheHit, rerankUsed, 0, (int) cost, RESULT_OK, errorCode);
        return RetrievalResponse.empty(request.query(), request.query(), cost);
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
        com.fintech.rag.common.context.RequestSource source = RequestContext.currentSource();
        return source == null ? "UNKNOWN" : source.name();
    }

    /**
     * traceId 权威取值：服务端链路优先。
     *
     * <p>为什么不能直接用请求体里的值：那是调用方填的，审计记录若采用它，
     * 就变成「填什么记什么」，一旦填错（或内网伪造）就会出现
     * 「检索日志关联不到任何真实链路」的黑洞记录。</p>
     */
    private String resolveTraceId(RetrievalRequest request) {
        String current = RequestContext.currentTraceId();
        if (current != null && !current.isBlank()) {
            return current;
        }
        return request.traceId();
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

    /**
     * 写检索日志。
     *
     * <p>所有出口路径（成功 / 空召回 / 无授权 / 异常）都必须调用本方法，
     * 且各字段必须写<b>真实值</b>——曾经这里把 cache_hit 写死 0、rerank_used 写死 1，
     * 结果是「缓存命中率永远是 0」，看板画得很平，却没人发现是数据源错了。</p>
     *
     * @param traceId     服务端链路的 traceId（非请求体传入值）
     * @param rerankUsed  是否真的启用了精排（取自请求参数，而非写死）
     * @param result      1 = 流程正常完成（含空召回）；0 = 检索失败
     * @param errorCode   失败或阻断原因码；正常成功时为 null
     */
    private void writeLog(RetrievalRequest request, String traceId, String rewrittenQuery,
                          Set<Long> kbIds, List<RetrievalResponse.Chunk> chunks,
                          boolean cacheHit, boolean rerankUsed,
                          int ragFlowCost, int cost, int result, String errorCode) {
        try {
            RetrievalLog entity = new RetrievalLog();
            entity.setTenantId(0L);
            entity.setTraceId(traceId);
            entity.setConversationId(request.conversationId());
            entity.setSubjectType(request.subjectType().name());
            entity.setSubjectId(request.subjectId());
            entity.setOriginalQuery(truncate(request.query(), 1000));
            entity.setRewrittenQuery(truncate(rewrittenQuery, 1000));
            entity.setKbIds(kbIds.toString());
            entity.setFilterJson(filterJsonOf(request));
            entity.setChunkCount(chunks.size());
            entity.setTopScore(chunks.isEmpty() || chunks.get(0).score() == null
                    ? null : java.math.BigDecimal.valueOf(chunks.get(0).score()));
            entity.setCacheHit(cacheHit ? 1 : 0);
            entity.setRerankUsed(rerankUsed ? 1 : 0);
            entity.setCostMs(cost);
            entity.setRagflowCostMs(ragFlowCost);
            entity.setResult(result);
            entity.setErrorCode(errorCode);
            retrievalLogMapper.insert(entity);
        } catch (Exception ex) {
            // 审计日志写失败不得影响检索主链路
            log.error("写入检索日志失败 traceId={} result={}", traceId, result, ex);
        }
    }

    /**
     * 业务过滤条件落库为 JSON。
     *
     * <p>手写 JSON 而非引入 ObjectMapper：这里只有 4 个标量字段，
     * 而手写能让「字段名与 DDL 注释严格一致」一眼可见；字符串值做转义，
     * 避免 bizChannel 里的引号把 JSON 撑破（MySQL 的 json 类型会直接拒绝非法 JSON）。</p>
     */
    private String filterJsonOf(RetrievalRequest request) {
        RetrievalRequest.Filters f = request.filters();
        if (f == null) {
            return null;
        }
        return "{\"secretLevelMax\":" + (f.secretLevelMax() == null ? "null" : f.secretLevelMax())
                + ",\"effectiveOnly\":" + (f.effectiveOnly() == null ? "null" : f.effectiveOnly())
                + ",\"bizChannel\":" + jsonString(f.bizChannel())
                + ",\"productCode\":" + jsonString(f.productCode()) + "}";
    }

    private String jsonString(String value) {
        if (value == null) {
            return "null";
        }
        return "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"") + "\"";
    }

    private String errorCodeOf(Throwable ex) {
        if (ex instanceof BizException biz) {
            return biz.getCode();
        }
        return ErrorCode.INTERNAL_ERROR.getCode();
    }

    private String truncate(String value, int max) {
        if (value == null) {
            return null;
        }
        return value.length() <= max ? value : value.substring(0, max);
    }
}
''')

print("---- total:", len(written))
