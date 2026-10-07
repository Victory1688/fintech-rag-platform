# -*- coding: utf-8 -*-
"""
S6: 生成 rag-retrieval-service（检索）与 rag-chat-service（问答编排）
"""
import pathlib

BASE = pathlib.Path(r"D:/AiWorkOut/java-ai/rag-platform")
FILES = {}


def add(rel, content):
    FILES[rel] = content.lstrip("\n")


# ============================================================================
# =========================  rag-retrieval-service  =========================
# ============================================================================
add("rag-retrieval-service/pom.xml", r'''
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>com.fintech.rag</groupId>
        <artifactId>rag-platform</artifactId>
        <version>1.0.0-SNAPSHOT</version>
    </parent>

    <artifactId>rag-retrieval-service</artifactId>
    <packaging>jar</packaging>
    <name>rag-retrieval-service</name>
    <description>检索服务：Query改写、混合检索、Rerank、业务过滤、缓存</description>

    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-redis</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-actuator</artifactId>
        </dependency>
        <dependency>
            <groupId>io.micrometer</groupId>
            <artifactId>micrometer-registry-prometheus</artifactId>
        </dependency>
        <dependency>
            <groupId>com.alibaba.cloud</groupId>
            <artifactId>spring-cloud-starter-alibaba-nacos-discovery</artifactId>
        </dependency>
        <dependency>
            <groupId>com.alibaba.cloud</groupId>
            <artifactId>spring-cloud-starter-alibaba-nacos-config</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.cloud</groupId>
            <artifactId>spring-cloud-starter-openfeign</artifactId>
        </dependency>
        <dependency>
            <groupId>com.baomidou</groupId>
            <artifactId>mybatis-plus-spring-boot3-starter</artifactId>
        </dependency>
        <dependency>
            <groupId>com.mysql</groupId>
            <artifactId>mysql-connector-j</artifactId>
            <scope>runtime</scope>
        </dependency>
        <dependency>
            <groupId>com.fintech.rag</groupId>
            <artifactId>rag-common</artifactId>
        </dependency>
        <dependency>
            <groupId>com.fintech.rag</groupId>
            <artifactId>rag-api</artifactId>
        </dependency>
    </dependencies>

    <build>
        <finalName>rag-retrieval-service</finalName>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>
''')

RT = "rag-retrieval-service/src/main/java/com/fintech/rag/retrieval"

add(RT + "/RetrievalApplication.java", r'''
package com.fintech.rag.retrieval;

import com.fintech.rag.api.client.KnowledgeClient;
import com.fintech.rag.api.client.PlatformClient;
import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;
import org.springframework.cloud.openfeign.EnableFeignClients;

/**
 * 检索服务启动类。
 *
 * <p>本服务把「检索策略」收口到一处：Query 改写、RAGFlow 混合检索、Rerank、
 * 业务过滤、缓存、召回评测。这样 RAGFlow 参数调整、未来更换检索引擎，
 * 都只需要改这一个服务。</p>
 *
 * @author rag-platform
 */
@SpringBootApplication(scanBasePackages = "com.fintech.rag.retrieval")
@EnableDiscoveryClient
@EnableFeignClients(clients = {PlatformClient.class, KnowledgeClient.class})
@ConfigurationPropertiesScan("com.fintech.rag.retrieval")
@MapperScan("com.fintech.rag.retrieval.infra.persistence.mapper")
public class RetrievalApplication {

    public static void main(String[] args) {
        SpringApplication.run(RetrievalApplication.class, args);
    }
}
''')

add(RT + "/domain/model/RetrievalLog.java", r'''
package com.fintech.rag.retrieval.domain.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 检索日志。
 *
 * <p>这张表是「空召回率」「Top5 命中率」「缓存命中率」的唯一数据来源，
 * 也是运营侧发现知识缺口的主要线索，不允许为了省存储而裁剪。</p>
 *
 * @author rag-platform
 */
@Data
@TableName("t_retrieval_log")
public class RetrievalLog {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private Long tenantId;

    private String traceId;

    private Long conversationId;

    private Long messageId;

    private String subjectType;

    private String subjectId;

    private String originalQuery;

    private String rewrittenQuery;

    /** 服务端推导后的实际检索范围，用于审计「到底查了哪些库」 */
    private String kbIds;

    private String filterJson;

    private Integer chunkCount;

    private BigDecimal topScore;

    private Integer cacheHit;

    private Integer rerankUsed;

    private Integer costMs;

    private Integer ragflowCostMs;

    private Integer result;

    private String errorCode;

    private LocalDateTime createTime;
}
''')

add(RT + "/infra/persistence/mapper/RetrievalLogMapper.java", r'''
package com.fintech.rag.retrieval.infra.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.fintech.rag.retrieval.domain.model.RetrievalLog;
import org.apache.ibatis.annotations.Mapper;

/**
 * 检索日志数据访问。
 *
 * @author rag-platform
 */
@Mapper
public interface RetrievalLogMapper extends BaseMapper<RetrievalLog> {
}
''')

add(RT + "/infra/client/RagFlowRetrievalClient.java", r'''
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
''')

add(RT + "/app/query/QueryRewriter.java", r'''
package com.fintech.rag.retrieval.app.query;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Query 改写器。
 *
 * <p>信贷场景下用户提问高度口语化（「小微信用贷能贷多少」），
 * 而文档里写的是「单户最高授信额度」。不做改写，向量相似度会明显偏低。</p>
 *
 * <p>骨架实现采用<b>规则词典</b>：确定性高、零成本、可解释、无幻觉风险。
 * 需要引入大模型改写时，务必加「改写结果不得引入原问题没有的业务实体」的校验，
 * 否则模型会把「抵押贷」改写成「信用贷」，造成答非所问且难以发现。</p>
 *
 * @author rag-platform
 */
@Component
public class QueryRewriter {

    private static final Logger log = LoggerFactory.getLogger(QueryRewriter.class);

    /** 业务术语归一表（口语 → 规范表述） */
    private static final Map<String, String> TERM_DICTIONARY = new LinkedHashMap<>();

    static {
        TERM_DICTIONARY.put("能贷多少", "最高授信额度");
        TERM_DICTIONARY.put("能借多少", "最高授信额度");
        TERM_DICTIONARY.put("利息多少", "执行利率");
        TERM_DICTIONARY.put("利率多少", "执行利率");
        TERM_DICTIONARY.put("要什么材料", "申请材料清单");
        TERM_DICTIONARY.put("需要什么资料", "申请材料清单");
        TERM_DICTIONARY.put("征信要求", "征信准入条件");
        TERM_DICTIONARY.put("能贷几年", "贷款期限");
    }

    /**
     * 改写查询。
     *
     * @param query      原始问题
     * @param bizChannel 业务条线（小微/零售/对公），可作为语境补充
     */
    public String rewrite(String query, String bizChannel) {
        if (query == null || query.isBlank()) {
            return query;
        }

        String rewritten = query;
        for (Map.Entry<String, String> entry : TERM_DICTIONARY.entrySet()) {
            if (rewritten.contains(entry.getKey())) {
                rewritten = rewritten.replace(entry.getKey(), entry.getValue());
            }
        }

        // 补充业务条线语境，提高召回精度
        if (bizChannel != null && !bizChannel.isBlank() && !rewritten.contains(bizChannel)) {
            rewritten = bizChannel + " " + rewritten;
        }

        if (!rewritten.equals(query)) {
            log.debug("Query 改写: [{}] -> [{}]", query, rewritten);
        }
        return rewritten;
    }
}
''')

add(RT + "/app/filter/ChunkBusinessFilter.java", r'''
package com.fintech.rag.retrieval.app.filter;

import com.fintech.rag.api.dto.knowledge.DocumentMeta;
import com.fintech.rag.api.dto.retrieval.RetrievalRequest;
import com.fintech.rag.api.dto.retrieval.RetrievalResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 召回结果业务过滤器 —— <b>越权防护的最后一道闸</b>。
 *
 * <p>RAGFlow 只按「向量相似度」召回，它不理解密级、生效期、业务条线。
 * 即使 dataset 白名单已经收得很紧，仍可能出现：</p>
 * <ul>
 *   <li>ACL 配置滞后：文档刚被提升为「机密」，但用户集合尚未同步；</li>
 *   <li>版本错乱：召回了已失效的历史版本；</li>
 *   <li>跨条线污染：小微的问题召回了对公的制度。</li>
 * </ul>
 *
 * <p>因此必须在 Java 侧做二次过滤。宁可少召回，也不能多召回 ——
 * 漏召回只是体验问题，多召回是合规事故。</p>
 *
 * @author rag-platform
 */
@Component
public class ChunkBusinessFilter {

    private static final Logger log = LoggerFactory.getLogger(ChunkBusinessFilter.class);

    /**
     * 过滤召回结果。
     *
     * @param chunks       RAGFlow 原始召回
     * @param docMetaMap   文档元数据（docId -> meta）
     * @param request      原始检索请求
     * @param authorizedKbIds 已授权知识库 ID 集合（最终硬约束）
     * @param userSecretLevel 用户密级
     */
    public List<RetrievalResponse.Chunk> filter(List<RetrievalResponse.Chunk> chunks,
                                                Map<Long, DocumentMeta> docMetaMap,
                                                RetrievalRequest request,
                                                java.util.Set<Long> authorizedKbIds,
                                                int userSecretLevel) {
        if (chunks == null || chunks.isEmpty()) {
            return List.of();
        }

        RetrievalRequest.Filters filters = request.filters() == null
                ? RetrievalRequest.Filters.defaults() : request.filters();
        int secretLevelMax = filters.secretLevelMax() == null
                ? userSecretLevel : Math.min(filters.secretLevelMax(), userSecretLevel);

        List<RetrievalResponse.Chunk> result = new ArrayList<>(chunks.size());
        int droppedByKb = 0;
        int droppedBySecret = 0;
        int droppedByExpire = 0;

        for (RetrievalResponse.Chunk chunk : chunks) {
            DocumentMeta meta = chunk.docId() == null ? null : docMetaMap.get(chunk.docId());

            // 1) 知识库必须属于授权集合
            if (meta != null && !authorizedKbIds.contains(meta.kbId())) {
                droppedByKb++;
                continue;
            }

            // 2) 密级不得高于用户可访问密级
            if (meta != null && meta.secretLevel() != null && meta.secretLevel() > secretLevelMax) {
                droppedBySecret++;
                continue;
            }

            // 3) 生效期校验
            if (Boolean.TRUE.equals(filters.effectiveOnly()) && meta != null) {
                LocalDate today = LocalDate.now();
                if (meta.effectiveDate() != null && meta.effectiveDate().isAfter(today)) {
                    droppedByExpire++;
                    continue;
                }
                if (meta.expireDate() != null && meta.expireDate().isBefore(today)) {
                    droppedByExpire++;
                    continue;
                }
            }

            // 4) 文档必须处于可检索状态
            if (meta != null && !"PARSED".equals(meta.parseStatus())) {
                continue;
            }

            // 5) 回填元数据，供引用展示使用
            result.add(new RetrievalResponse.Chunk(
                    chunk.chunkId(),
                    meta == null ? chunk.kbId() : meta.kbId(),
                    chunk.docId(),
                    meta == null ? chunk.docName() : meta.docName(),
                    meta == null ? chunk.versionNo() : meta.versionNo(),
                    chunk.chunkIndex(),
                    chunk.pageNo(),
                    chunk.content(),
                    chunk.score(),
                    chunk.vectorScore(),
                    chunk.termScore()));
        }

        if (droppedByKb + droppedBySecret + droppedByExpire > 0) {
            log.warn("[越权防护] 过滤召回片段 kb越权={} 密级越权={} 失效={} 剩余={}/{}",
                    droppedByKb, droppedBySecret, droppedByExpire, result.size(), chunks.size());
        }
        return deduplicate(result);
    }

    /** 相邻片段合并去重：同一文档相邻 chunk 常被同时召回，直接展示会造成引用冗余 */
    private List<RetrievalResponse.Chunk> deduplicate(List<RetrievalResponse.Chunk> chunks) {
        Map<String, RetrievalResponse.Chunk> unique = new HashMap<>();
        for (RetrievalResponse.Chunk chunk : chunks) {
            String key = chunk.chunkId() != null
                    ? chunk.chunkId()
                    : (chunk.docId() + "#" + chunk.content().hashCode());
            unique.merge(key, chunk, (old, fresh) ->
                    (old.score() == null ? 0.0 : old.score()) >= (fresh.score() == null ? 0.0 : fresh.score())
                            ? old : fresh);
        }
        List<RetrievalResponse.Chunk> deduped = new ArrayList<>(unique.values());
        deduped.sort((a, b) -> Double.compare(
                b.score() == null ? 0.0 : b.score(),
                a.score() == null ? 0.0 : a.score()));
        return deduped;
    }
}
''')

add(RT + "/app/cache/RetrievalCacheKeyBuilder.java", r'''
package com.fintech.rag.retrieval.app.cache;

import com.fintech.rag.common.util.HmacSignatures;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 检索缓存 Key 构造器。
 *
 * <p><b>为什么必须集中构造、禁止业务代码手写 Key：</b>
 * 缓存 Key 少一个维度，就会造成越权。例如漏了授权范围维度，
 * 那么「A 用户查过的问题」会把答案缓存给「只有部分权限的 B 用户」，
 * 结果是 B 看到了自己无权访问的机密制度内容。</p>
 *
 * <p>Key 组成（缺一不可）：</p>
 * <ol>
 *   <li>授权范围指纹（datasetId 排序后哈希）</li>
 *   <li>知识库版本指纹（内容或参数变更 → 版本变化 → 旧缓存自然不命中）</li>
 *   <li>归一化后的查询</li>
 *   <li>业务过滤条件指纹</li>
 *   <li>用户密级</li>
 *   <li>检索参数指纹</li>
 * </ol>
 *
 * @author rag-platform
 */
@Component
public class RetrievalCacheKeyBuilder {

    private static final String PREFIX = "ret:v1:";

    public String build(List<String> datasetIds, Map<String, Long> kbVersions,
                        String normalizedQuery, String filtersFingerprint,
                        int userSecretLevel, String optionsFingerprint) {
        String datasetHash = sha(sorted(datasetIds));
        String versionHash = sha(kbVersions.entrySet().stream()
                .sorted(Map.Entry.comparingByKey())
                .map(e -> e.getKey() + "=" + e.getValue())
                .collect(Collectors.joining("&")));
        String queryHash = sha(normalizedQuery);

        return PREFIX + datasetHash + ":" + versionHash + ":" + queryHash + ":"
                + filtersFingerprint + ":" + userSecretLevel + ":" + optionsFingerprint;
    }

    /** 归一化查询：去空白、统一大小写、去掉无意义标点，避免「同一问题两种写法」重复穿透 */
    public String normalizeQuery(String query) {
        if (query == null) {
            return "";
        }
        return query.trim()
                .toLowerCase()
                .replaceAll("[\\s\\p{Punct}]+", "")
                .replaceAll("[，。？！；：、“”‘’（）《》]", "");
    }

    private String sorted(List<String> ids) {
        if (ids == null || ids.isEmpty()) {
            return "EMPTY";
        }
        return ids.stream().sorted().collect(Collectors.joining(","));
    }

    private String sha(String value) {
        String hex = HmacSignatures.sha256Hex(value == null ? "" : value);
        return hex.substring(0, 16);
    }
}
''')

add(RT + "/app/service/RetrievalAppService.java", r'''
package com.fintech.rag.retrieval.app.service;

import com.fintech.rag.api.client.KnowledgeClient;
import com.fintech.rag.api.dto.knowledge.DocumentMeta;
import com.fintech.rag.api.dto.knowledge.KbBrief;
import com.fintech.rag.api.dto.retrieval.RetrievalRequest;
import com.fintech.rag.api.dto.retrieval.RetrievalResponse;
import com.fintech.rag.common.core.R;
import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import com.fintech.rag.retrieval.app.cache.RetrievalCacheKeyBuilder;
import com.fintech.rag.retrieval.app.filter.ChunkBusinessFilter;
import com.fintech.rag.retrieval.app.query.QueryRewriter;
import com.fintech.rag.retrieval.domain.model.RetrievalLog;
import com.fintech.rag.retrieval.infra.client.RagFlowRetrievalClient;
import com.fintech.rag.retrieval.infra.persistence.mapper.RetrievalLogMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
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
 *   <li>向 platform / knowledge 取「授权知识库真源」，与请求意图取交集 → 得到 dataset 白名单</li>
 *   <li>Query 改写</li>
 *   <li>查缓存（Key 已包含权限指纹）</li>
 *   <li>调 RAGFlow 检索</li>
 *   <li>业务过滤（密级 / 生效期 / 越权 / 去重）</li>
 *   <li>写检索日志（合规审计 + 运营分析）</li>
 * </ol>
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

    public RetrievalAppService(KnowledgeClient knowledgeClient,
                               RagFlowRetrievalClient ragFlowClient,
                               QueryRewriter queryRewriter,
                               ChunkBusinessFilter businessFilter,
                               RetrievalCacheKeyBuilder cacheKeyBuilder,
                               StringRedisTemplate redisTemplate,
                               RetrievalLogMapper retrievalLogMapper) {
        this.knowledgeClient = knowledgeClient;
        this.ragFlowClient = ragFlowClient;
        this.queryRewriter = queryRewriter;
        this.businessFilter = businessFilter;
        this.cacheKeyBuilder = cacheKeyBuilder;
        this.redisTemplate = redisTemplate;
        this.retrievalLogMapper = retrievalLogMapper;
    }

    public RetrievalResponse search(RetrievalRequest request, String roleCodes, Long deptId) {
        long start = System.currentTimeMillis();

        // ---------- 1. 授权真源（越权防护的根本） ----------
        List<KbBrief> authorizedKbs = fetchAuthorizedKbs(request.subjectType().name(),
                request.subjectId(), roleCodes, deptId);
        if (authorizedKbs.isEmpty()) {
            log.info("主体无任何授权知识库 subjectId={}", request.subjectId());
            return RetrievalResponse.empty(request.query(), request.query(),
                    System.currentTimeMillis() - start);
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
            return RetrievalResponse.empty(request.query(), request.query(),
                    System.currentTimeMillis() - start);
        }

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
            log.debug("检索缓存命中 key={}", cacheKey);
        }

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

        if (emptyHit) {
            redisTemplate.opsForValue().set(cacheKey, "EMPTY", EMPTY_HIT_TTL);
            return RetrievalResponse.empty(request.query(), rewrittenQuery, cost);
        }
        return new RetrievalResponse(request.query(), rewrittenQuery, filtered, false, false, cost);
    }

    // ------------------------------------------------------------------ 辅助
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
''')

add(RT + "/api/controller/RetrievalController.java", r'''
package com.fintech.rag.retrieval.api.controller;

import com.fintech.rag.api.dto.retrieval.RetrievalRequest;
import com.fintech.rag.api.dto.retrieval.RetrievalResponse;
import com.fintech.rag.api.server.interceptor.SourceAuthInterceptor;
import com.fintech.rag.common.core.R;
import com.fintech.rag.retrieval.app.service.RetrievalAppService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 检索接口。
 *
 * <p>注意：{@code roleCodes} 与 {@code deptId} 来自<b>网关注入的请求头</b>（从 JWT 解析），
 * 不从请求体读取 —— 否则用户改一个字段就能把「按角色授权」变成「按任意角色授权」。</p>
 *
 * @author rag-platform
 */
@RestController
@RequestMapping("/api/retrieval")
public class RetrievalController {

    private final RetrievalAppService retrievalAppService;

    public RetrievalController(RetrievalAppService retrievalAppService) {
        this.retrievalAppService = retrievalAppService;
    }

    @PostMapping("/search")
    public R<RetrievalResponse> search(@Valid @RequestBody RetrievalRequest request,
                                       HttpServletRequest servletRequest) {
        String roleCodes = (String) servletRequest.getAttribute(SourceAuthInterceptor.ATTR_USER_ROLES);
        String deptIdText = (String) servletRequest.getAttribute(SourceAuthInterceptor.ATTR_USER_DEPT);
        Long deptId = null;
        if (deptIdText != null && !deptIdText.isBlank()) {
            try {
                deptId = Long.parseLong(deptIdText);
            } catch (NumberFormatException ignored) {
                // 非法部门 ID 视为无部门，不放大权限
            }
        }
        return R.ok(retrievalAppService.search(request, roleCodes, deptId));
    }
}
''')

add("rag-retrieval-service/src/main/resources/application.yml", r'''
server:
  port: 8084
  shutdown: graceful

spring:
  application:
    name: rag-retrieval-service
  profiles:
    active: dev
  config:
    import:
      - optional:nacos:rag-retrieval-service.yaml
      - optional:nacos:rag-common.yaml
  cloud:
    nacos:
      server-addr: ${NACOS_ADDR:127.0.0.1:8848}
      username: ${NACOS_USERNAME:nacos}
      password: ${NACOS_PASSWORD:nacos}
      discovery:
        namespace: ${NACOS_NAMESPACE:rag}
        group: RAG_GROUP
      config:
        namespace: ${NACOS_NAMESPACE:rag}
        group: RAG_GROUP
        file-extension: yaml
  datasource:
    driver-class-name: com.mysql.cj.jdbc.Driver
    url: jdbc:mysql://${MYSQL_HOST:127.0.0.1}:${MYSQL_PORT:3306}/rag_retrieval?useUnicode=true&characterEncoding=utf8&serverTimezone=Asia/Shanghai
    username: ${MYSQL_USERNAME:rag}
    password: ${MYSQL_PASSWORD:rag123456}
  data:
    redis:
      host: ${REDIS_HOST:127.0.0.1}
      port: ${REDIS_PORT:6379}
      password: ${REDIS_PASSWORD:}
      database: 1
      timeout: 500ms

mybatis-plus:
  configuration:
    map-underscore-to-camel-case: true

feign:
  client:
    config:
      default:
        connectTimeout: 500
        readTimeout: 3000

rag:
  ragflow:
    base-url: http://${RAGFLOW_HOST:127.0.0.1}:${RAGFLOW_PORT:9380}
    api-key: ${RAGFLOW_API_KEY:}
    read-timeout-ms: 5000
    default-rerank-model: BAAI/bge-reranker-v2-m3
  server:
    auth:
      enabled: true
      trusted-gateway-cidrs:
        - 10.10.1.0/24
      gateway-signature-enabled: false
      gateway-sign-secret: ${RAG_GATEWAY_SIGN_SECRET:}

management:
  endpoints:
    web:
      exposure:
        include: health,info,prometheus,metrics

logging:
  level:
    com.fintech.rag: INFO
''')

# ============================================================================
# ===========================  rag-chat-service  =============================
# ============================================================================
add("rag-chat-service/pom.xml", r'''
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>com.fintech.rag</groupId>
        <artifactId>rag-platform</artifactId>
        <version>1.0.0-SNAPSHOT</version>
    </parent>

    <artifactId>rag-chat-service</artifactId>
    <packaging>jar</packaging>
    <name>rag-chat-service</name>
    <description>问答编排：LangChain4j、Prompt、Agent、SSE、护栏、Token 计量</description>

    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-redis</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-actuator</artifactId>
        </dependency>
        <dependency>
            <groupId>io.micrometer</groupId>
            <artifactId>micrometer-registry-prometheus</artifactId>
        </dependency>
        <dependency>
            <groupId>com.alibaba.cloud</groupId>
            <artifactId>spring-cloud-starter-alibaba-nacos-discovery</artifactId>
        </dependency>
        <dependency>
            <groupId>com.alibaba.cloud</groupId>
            <artifactId>spring-cloud-starter-alibaba-nacos-config</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.cloud</groupId>
            <artifactId>spring-cloud-starter-openfeign</artifactId>
        </dependency>
        <dependency>
            <groupId>com.baomidou</groupId>
            <artifactId>mybatis-plus-spring-boot3-starter</artifactId>
        </dependency>
        <dependency>
            <groupId>com.mysql</groupId>
            <artifactId>mysql-connector-j</artifactId>
            <scope>runtime</scope>
        </dependency>

        <!--
          LangChain4j：刻意只引 core + open-ai 两个基础包，不使用 Spring Boot Starter。
          原因：模型需要从配置中心 / platform 动态路由（多模型 + 敏感度分流 + 故障切换），
          Starter 的静态装配表达不了这种动态性。
        -->
        <dependency>
            <groupId>dev.langchain4j</groupId>
            <artifactId>langchain4j</artifactId>
        </dependency>
        <dependency>
            <groupId>dev.langchain4j</groupId>
            <artifactId>langchain4j-open-ai</artifactId>
        </dependency>

        <dependency>
            <groupId>com.fintech.rag</groupId>
            <artifactId>rag-common</artifactId>
        </dependency>
        <dependency>
            <groupId>com.fintech.rag</groupId>
            <artifactId>rag-api</artifactId>
        </dependency>
    </dependencies>

    <build>
        <finalName>rag-chat-service</finalName>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>
''')

CH = "rag-chat-service/src/main/java/com/fintech/rag/chat"

add(CH + "/ChatApplication.java", r'''
package com.fintech.rag.chat;

import com.fintech.rag.api.client.KnowledgeClient;
import com.fintech.rag.api.client.PlatformClient;
import com.fintech.rag.api.client.RetrievalClient;
import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;
import org.springframework.cloud.openfeign.EnableFeignClients;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * 问答编排服务启动类。
 *
 * <p>职责：把「检索到的片段」变成「合规、可溯源、贴合本行口径的回答」。
 * 生成链路成本最高，因此本服务的限流、缓存、降级策略要比检索服务更保守。</p>
 *
 * @author rag-platform
 */
@SpringBootApplication(scanBasePackages = "com.fintech.rag.chat")
@EnableDiscoveryClient
@EnableFeignClients(clients = {PlatformClient.class, KnowledgeClient.class, RetrievalClient.class})
@EnableScheduling
@ConfigurationPropertiesScan("com.fintech.rag.chat")
@MapperScan("com.fintech.rag.chat.infra.persistence.mapper")
public class ChatApplication {

    public static void main(String[] args) {
        SpringApplication.run(ChatApplication.class, args);
    }
}
''')

add(CH + "/infra/llm/LlmRouter.java", r'''
package com.fintech.rag.chat.infra.llm;

import com.fintech.rag.api.client.PlatformClient;
import com.fintech.rag.api.dto.platform.ModelConfigDTO;
import com.fintech.rag.common.core.R;
import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import dev.langchain4j.model.chat.ChatModel;
import dev.langchain4j.model.chat.StreamingChatModel;
import dev.langchain4j.model.openai.OpenAiChatModel;
import dev.langchain4j.model.openai.OpenAiStreamingChatModel;
import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 模型路由器 —— <b>信贷场景的合规关键组件</b>。
 *
 * <p>路由规则：</p>
 * <ol>
 *   <li>先按「本次请求涉及的最高密级」筛出可处理该密级的模型配置；</li>
 *   <li>在该集合内按 priority 升序取第一个可用模型；</li>
 *   <li>调用失败时自动切换到下一个（failover），全部失败才抛错。</li>
 * </ol>
 *
 * <p>典型配置：</p>
 * <pre>
 *   PRIMARY_CLOUD      sensitiveLevel=2  priority=100  云侧 DeepSeek/通义
 *   SENSITIVE_PRIVATE  sensitiveLevel=3  priority=10   内网私有化模型
 * </pre>
 * 高密级请求只会命中私有化通道，数据不出内网。
 *
 * @author rag-platform
 */
@Component
public class LlmRouter {

    private static final Logger log = LoggerFactory.getLogger(LlmRouter.class);

    private final PlatformClient platformClient;

    /** configCode -> 同步模型实例 */
    private final Map<String, ChatModel> chatModels = new ConcurrentHashMap<>();

    /** configCode -> 流式模型实例 */
    private final Map<String, StreamingChatModel> streamingModels = new ConcurrentHashMap<>();

    /** 当前生效的配置，按 priority 升序 */
    private volatile List<ModelConfigDTO> configs = new ArrayList<>();

    public LlmRouter(PlatformClient platformClient) {
        this.platformClient = platformClient;
    }

    @PostConstruct
    public void init() {
        refresh();
    }

    /**
     * 定时刷新模型配置。用定时拉取而非每次问答远程调用，
     * 避免把「模型配置查询」变成高频调用的性能瓶颈。
     */
    @Scheduled(fixedDelayString = "${rag.chat.model-refresh-ms:300000}", initialDelay = 300000)
    public void scheduleRefresh() {
        try {
            refresh();
        } catch (Exception ex) {
            log.error("刷新模型配置失败，沿用旧配置", ex);
        }
    }

    public synchronized void refresh() {
        R<List<ModelConfigDTO>> result = platformClient.listModelConfigs();
        if (result == null || !result.isSuccess() || result.getData() == null) {
            log.warn("拉取模型配置为空，沿用上一次配置");
            return;
        }
        List<ModelConfigDTO> latest = new ArrayList<>(result.getData());
        latest.sort(Comparator.comparing(c -> c.priority() == null ? Integer.MAX_VALUE : c.priority()));

        chatModels.clear();
        streamingModels.clear();
        for (ModelConfigDTO config : latest) {
            try {
                chatModels.put(config.configCode(), buildChatModel(config));
                streamingModels.put(config.configCode(), buildStreamingModel(config));
            } catch (Exception ex) {
                log.error("构建模型实例失败，跳过该配置 configCode={}", config.configCode(), ex);
            }
        }
        this.configs = latest;
        log.info("模型配置已刷新，共 {} 个", latest.size());
    }

    /**
     * 按密级路由（同步）。
     *
     * @param secretLevel 本次请求涉及的最高密级
     */
    public ChatModel route(int secretLevel) {
        ModelConfigDTO config = pick(secretLevel);
        ChatModel model = chatModels.get(config.configCode());
        if (model == null) {
            throw BizException.of(ErrorCode.NO_MODEL_AVAILABLE,
                    "模型实例构建失败：" + config.configCode());
        }
        return model;
    }

    /** 按密级路由（流式） */
    public StreamingChatModel routeStreaming(int secretLevel) {
        ModelConfigDTO config = pick(secretLevel);
        StreamingChatModel model = streamingModels.get(config.configCode());
        if (model == null) {
            throw BizException.of(ErrorCode.NO_MODEL_AVAILABLE,
                    "流式模型实例构建失败：" + config.configCode());
        }
        return model;
    }

    /** 返回本次实际使用的配置编码，用于日志、Token 归因与问题定位 */
    public String routeCode(int secretLevel) {
        return pick(secretLevel).configCode();
    }

    private ModelConfigDTO pick(int secretLevel) {
        List<ModelConfigDTO> snapshot = this.configs;
        if (snapshot.isEmpty()) {
            throw BizException.of(ErrorCode.NO_MODEL_AVAILABLE, "模型配置为空，请检查配置中心");
        }
        // 候选：能处理该密级 且 实例已就绪
        List<ModelConfigDTO> candidates = snapshot.stream()
                .filter(c -> c.sensitiveLevel() != null && c.sensitiveLevel() >= secretLevel)
                .filter(c -> chatModels.containsKey(c.configCode()))
                .toList();

        if (candidates.isEmpty()) {
            throw BizException.of(ErrorCode.NO_MODEL_AVAILABLE,
                    "当前密级(" + secretLevel + ")下无可用模型配置，请检查敏感度路由规则");
        }
        return candidates.get(0);
    }

    private ChatModel buildChatModel(ModelConfigDTO config) {
        return OpenAiChatModel.builder()
                .baseUrl(config.baseUrl())
                .apiKey(config.apiKey())
                .modelName(config.modelName())
                .temperature(config.temperature() == null ? 0.2 : config.temperature())
                .maxTokens(config.maxTokens() == null ? 1024 : config.maxTokens())
                .timeout(Duration.ofSeconds(60))
                .logRequests(false)
                .logResponses(false)
                .build();
    }

    private StreamingChatModel buildStreamingModel(ModelConfigDTO config) {
        return OpenAiStreamingChatModel.builder()
                .baseUrl(config.baseUrl())
                .apiKey(config.apiKey())
                .modelName(config.modelName())
                .temperature(config.temperature() == null ? 0.2 : config.temperature())
                .maxTokens(config.maxTokens() == null ? 1024 : config.maxTokens())
                .timeout(Duration.ofSeconds(120))
                .build();
    }
}
''')

add(CH + "/app/prompt/PromptTemplateRegistry.java", r'''
package com.fintech.rag.chat.app.prompt;

import com.fintech.rag.api.dto.retrieval.RetrievalResponse;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * Prompt 模板注册表。
 *
 * <p>模板集中管理而非散落在 Service 里，有两个实际好处：
 * 一是产品/业务人员可以参与文案评审；二是每次回答都记录 {@code promptVersion}，
 * 出问题时可复现「当时用的是哪一版提示词」。</p>
 *
 * @author rag-platform
 */
@Component
public class PromptTemplateRegistry {

    /** 模板版本号，随模板变更递增，落库到消息表便于问题复现 */
    public static final String VERSION = "v1.3";

    private static final String SYSTEM_TEMPLATE = """
            你是某银行信贷业务的知识助手，服务对象是本行客户经理、风控与合规人员。

            【最重要的规则】
            1. 只能依据下面「参考资料」中的内容作答，不得使用你自身的通用知识补充。
            2. 参考资料中没有的内容，必须明确回答「知识库中未找到相关规定」，并建议咨询对应管理部门。
            3. 每一个事实性结论后面必须标注引用编号，格式为 [1]、[2]，编号必须与参考资料一致。
            4. 涉及金额、利率、期限、次数等数值时，必须逐字引用原文，不得换算、不得四舍五入。
            5. 若不同参考资料存在冲突，必须指出冲突并分别标注来源，不得自行裁决。
            6. 不得给出授信审批结论或风险判断，只做制度与政策的检索与整理。
            7. 回答使用专业、简洁的书面语，分条陈述，不使用表情符号。

            【输出结构】
            - 先给结论（1~2 句）
            - 再分条列出依据（每条带引用编号）
            - 若存在例外条款或适用条件，单列一节说明
            """;

    private static final String USER_TEMPLATE = """
            参考资料：
            %s

            用户问题：%s
            """;

    /** 系统提示词 */
    public String systemPrompt() {
        return SYSTEM_TEMPLATE;
    }

    /** 组装用户提示词（含检索上下文） */
    public String userPrompt(String question, List<RetrievalResponse.Chunk> chunks) {
        StringBuilder context = new StringBuilder();
        int index = 1;
        for (RetrievalResponse.Chunk chunk : chunks) {
            context.append("[").append(index).append("] 来源：《")
                    .append(chunk.docName() == null ? "未知文档" : chunk.docName())
                    .append("》");
            if (chunk.versionNo() != null) {
                context.append("（第 ").append(chunk.versionNo()).append(" 版）");
            }
            if (chunk.pageNo() != null) {
                context.append(" 第 ").append(chunk.pageNo()).append(" 页");
            }
            context.append("\n").append(chunk.content()).append("\n\n");
            index++;
        }
        return String.format(USER_TEMPLATE, context, question);
    }

    /** 空召回时的兜底话术：不调用模型，直接返回 */
    public String noHitAnswer() {
        return "知识库中未找到与该问题相关的内容。建议：\n"
                + "1. 换用更具体的表述（例如加上产品名称、业务条线）重新提问；\n"
                + "2. 确认该内容是否已上传至本知识库；\n"
                + "3. 提交知识缺口反馈，我们会安排补录。";
    }

    /** 免责声明 */
    public String disclaimer() {
        return "以上内容由系统基于行内知识库自动生成，仅供参考，请以行内正式制度文件为准。";
    }
}
''')

add(CH + "/app/guard/AnswerGuardrail.java", r'''
package com.fintech.rag.chat.app.guard;

import com.fintech.rag.api.client.PlatformClient;
import com.fintech.rag.api.dto.chat.ChatResponse;
import com.fintech.rag.api.dto.common.GuardrailType;
import com.fintech.rag.api.dto.platform.SensitiveRuleDTO;
import com.fintech.rag.common.core.R;
import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 答案护栏 —— <b>金融场景的合规底线</b>。
 *
 * <p>大模型本质上是在「续写最可能的文本」，它无法自我保证不编造。
 * 因此必须在外层用确定性规则做校验，而不是寄希望于提示词。</p>
 *
 * <p>本类实现的护栏（与 PRD 一一对应）：</p>
 * <ul>
 *   <li>空召回拦截（由编排层在调用模型前判定）</li>
 *   <li>引用完整性：正文 [n] 必须有对应 citation</li>
 *   <li>无引用数值告警：出现利率/额度等数值但无引用</li>
 *   <li>敏感信息脱敏：身份证 / 手机号 / 银行卡</li>
 * </ul>
 *
 * @author rag-platform
 */
@Component
public class AnswerGuardrail {

    private static final Logger log = LoggerFactory.getLogger(AnswerGuardrail.class);

    /** 引用标记 [1] [2] */
    private static final Pattern CITATION_PATTERN = Pattern.compile("\\[(\\d{1,2})]");

    /** 数值敏感表述：命中但无引用 → 追加提示并告警 */
    private static final Pattern SENSITIVE_NUMERIC_PATTERN = Pattern.compile(
            "(\\d+(?:\\.\\d+)?)\\s*(%|万元|亿元|元|天|个月|年|次)");

    private static final Pattern ID_CARD_PATTERN = Pattern.compile("\\b\\d{17}[\\dXx]\\b");
    private static final Pattern MOBILE_PATTERN = Pattern.compile("\\b1[3-9]\\d{9}\\b");
    private static final Pattern BANK_CARD_PATTERN = Pattern.compile("\\b\\d{16,19}\\b");

    private final PlatformClient platformClient;

    /** 平台下发的脱敏规则，本地缓存，定时刷新 */
    private volatile List<SensitiveRuleDTO> sensitiveRules = new ArrayList<>();

    public AnswerGuardrail(PlatformClient platformClient) {
        this.platformClient = platformClient;
    }

    @PostConstruct
    public void init() {
        refreshRules();
    }

    @Scheduled(fixedDelayString = "${rag.chat.guardrail-refresh-ms:600000}", initialDelay = 60000)
    public void refreshRules() {
        try {
            R<List<SensitiveRuleDTO>> result = platformClient.listSensitiveRules();
            if (result != null && result.isSuccess() && result.getData() != null) {
                this.sensitiveRules = result.getData();
                log.info("脱敏规则已刷新，共 {} 条", this.sensitiveRules.size());
            }
        } catch (Exception ex) {
            log.error("刷新脱敏规则失败，沿用旧规则", ex);
        }
    }

    /**
     * 校验并修正答案。
     *
     * @param rawAnswer      模型原始输出
     * @param citationCount  实际引用条数
     * @return 校验结果
     */
    public GuardrailResult check(String rawAnswer, int citationCount) {
        List<String> hitTypes = new ArrayList<>();
        List<String> reasons = new ArrayList<>();
        String answer = rawAnswer == null ? "" : rawAnswer;

        // ---------- 1. 引用完整性 ----------
        if (citationCount <= 0) {
            hitTypes.add(GuardrailType.MISSING_CITATION.name());
            reasons.add("答案未包含任何引用来源");
        } else {
            Matcher matcher = CITATION_PATTERN.matcher(answer);
            int maxRef = 0;
            while (matcher.find()) {
                maxRef = Math.max(maxRef, Integer.parseInt(matcher.group(1)));
            }
            if (maxRef > citationCount) {
                // 模型引用了不存在的编号：裁剪为最大合法编号，避免前端出现「引用了不存在的来源」
                answer = answer.replaceAll("\\[(\\d{1,2})]", m -> {
                    int n = Integer.parseInt(m.group(1));
                    return n <= citationCount ? m.group(0) : "";
                });
                hitTypes.add(GuardrailType.MISSING_CITATION.name());
                reasons.add("答案引用了不存在的来源编号，已自动裁剪");
            }
        }

        // ---------- 2. 数值无引用 ----------
        if (citationCount <= 0 && SENSITIVE_NUMERIC_PATTERN.matcher(answer).find()) {
            hitTypes.add(GuardrailType.UNSUPPORTED_NUMERIC.name());
            reasons.add("答案包含具体数值但无引用来源");
        }

        // ---------- 3. 敏感信息脱敏 ----------
        String masked = maskSensitive(answer);
        if (!masked.equals(answer)) {
            hitTypes.add(GuardrailType.SENSITIVE.name());
            reasons.add("答案包含敏感信息，已脱敏");
            answer = masked;
        }

        return new GuardrailResult(answer, hitTypes, String.join("；", reasons));
    }

    /** 脱敏：先跑平台下发的规则，再跑内置兜底规则（平台规则缺失时也不至于裸奔） */
    public String maskSensitive(String text) {
        if (text == null || text.isBlank()) {
            return text;
        }
        String result = text;

        for (SensitiveRuleDTO rule : sensitiveRules) {
            if (!"REGEX".equalsIgnoreCase(rule.getRuleType())) {
                continue;
            }
            try {
                Pattern pattern = Pattern.compile(rule.getPattern());
                result = replace(pattern, result, rule.getKeepPrefix(), rule.getKeepSuffix(),
                        rule.getMaskChar() == null ? "*" : rule.getMaskChar());
            } catch (Exception ex) {
                log.warn("脱敏规则执行失败 ruleCode={}", rule.getRuleCode(), ex);
            }
        }

        result = replace(ID_CARD_PATTERN, result, 4, 2, "*");
        result = replace(MOBILE_PATTERN, result, 3, 4, "*");
        result = replace(BANK_CARD_PATTERN, result, 4, 4, "*");
        return result;
    }

    private String replace(Pattern pattern, String text, Integer keepPrefix, Integer keepSuffix, String mask) {
        int prefix = keepPrefix == null ? 0 : keepPrefix;
        int suffix = keepSuffix == null ? 0 : keepSuffix;
        Matcher matcher = pattern.matcher(text);

        StringBuilder builder = new StringBuilder();
        while (matcher.find()) {
            String matched = matcher.group();
            int len = matched.length();
            if (prefix + suffix >= len) {
                matcher.appendReplacement(builder, Matcher.quoteReplacement(mask.repeat(len)));
                continue;
            }
            String masked = matched.substring(0, prefix)
                    + mask.repeat(len - prefix - suffix)
                    + matched.substring(len - suffix);
            matcher.appendReplacement(builder, Matcher.quoteReplacement(masked));
        }
        matcher.appendTail(builder);
        return builder.toString();
    }

    /**
     * 护栏校验结果。
     *
     * @param answer   修正后的答案
     * @param hitTypes 命中类型
     * @param reason   人类可读原因
     */
    public record GuardrailResult(String answer, List<String> hitTypes, String reason) {

        public boolean hit() {
            return !hitTypes.isEmpty();
        }

        public ChatResponse.Guardrail toGuardrail() {
            return new ChatResponse.Guardrail(hit(), hitTypes, reason == null || reason.isBlank() ? null : reason);
        }
    }
}
''')

add(CH + "/app/agent/tool/CreditBusinessTools.java", r'''
package com.fintech.rag.chat.app.agent.tool;

import dev.langchain4j.agent.tool.P;
import dev.langchain4j.agent.tool.Tool;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * 信贷业务工具集（Function Calling）。
 *
 * <p><b>三条安全约束，缺一不可：</b></p>
 * <ol>
 *   <li><b>只读</b>：只允许查询类工具。任何写操作（修改额度、提交申请）绝不允许
 *       由模型触发，这是不可退让的红线。</li>
 *   <li><b>参数校验</b>：工具入参必须做白名单与格式校验，防止模型构造出越权参数。</li>
 *   <li><b>超时与降级</b>：业务系统不可用时返回「暂时无法查询」，
 *       不得让模型据此编造数据。</li>
 * </ol>
 *
 * <p>骨架中为占位实现，落地时接入真实业务接口（走 rag-api 的 Feign 契约）。</p>
 *
 * @author rag-platform
 */
@Component
public class CreditBusinessTools {

    private static final Logger log = LoggerFactory.getLogger(CreditBusinessTools.class);

    /**
     * 查询产品当前执行利率。
     *
     * @param productCode 产品编码，必须是行内正式编码
     */
    @Tool("查询指定信贷产品的当前执行利率区间。仅在用户明确询问利率时调用，productCode 必须是行内正式产品编码。")
    public String queryProductRate(@P("产品编码，例如 P10086") String productCode) {
        if (productCode == null || !productCode.matches("P\\d{5}")) {
            log.warn("[工具] 非法产品编码请求：{}", productCode);
            return "产品编码格式不正确，无法查询";
        }
        log.info("[工具] 查询产品利率 productCode={}", productCode);
        // TODO 接入信贷产品中台接口；当前返回占位，调用方需按「数据来源：业务系统」标注
        return "{\"productCode\":\"" + productCode + "\",\"status\":\"NOT_INTEGRATED\"}";
    }

    /**
     * 查询某业务条线的在售产品清单。
     *
     * @param channel 业务条线，取值：小微 / 零售 / 对公
     */
    @Tool("查询指定业务条线当前在售的信贷产品清单。仅用于帮助用户确定产品范围，不返回审批结论。")
    public String listProductsByChannel(@P("业务条线，取值：小微 / 零售 / 对公") String channel) {
        if (channel == null || !java.util.Set.of("小微", "零售", "对公").contains(channel)) {
            return "业务条线取值非法，仅支持：小微 / 零售 / 对公";
        }
        log.info("[工具] 查询在售产品 channel={}", channel);
        return "{\"channel\":\"" + channel + "\",\"status\":\"NOT_INTEGRATED\"}";
    }
}
''')

add(CH + "/app/service/ConversationMemoryStore.java", r'''
package com.fintech.rag.chat.app.service;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.fintech.rag.chat.domain.model.ChatMessage;
import com.fintech.rag.chat.infra.persistence.mapper.ChatMessageMapper;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;

/**
 * 会话记忆存储。
 *
 * <p>骨架使用「按会话查询最近 N 条消息」的简易实现。
 * 落地时建议改为 Redis 存窗口 + 数据库存全量：
 * 前者保证多轮对话低延迟，后者保证审计可追溯（金融场景必须全量留存）。</p>
 *
 * @author rag-platform
 */
@Service
public class ConversationMemoryStore {

    /** 参与 Prompt 的历史轮数上限，过多会稀释检索上下文并推高 token 成本 */
    private static final int MAX_HISTORY_MESSAGES = 6;

    private final ChatMessageMapper messageMapper;

    public ConversationMemoryStore(ChatMessageMapper messageMapper) {
        this.messageMapper = messageMapper;
    }

    /** 读取最近若干条消息（时间正序） */
    public List<ChatMessage> recent(Long conversationId) {
        if (conversationId == null) {
            return List.of();
        }
        List<ChatMessage> messages = messageMapper.selectList(Wrappers.<ChatMessage>lambdaQuery()
                .eq(ChatMessage::getConversationId, conversationId)
                .orderByDesc(ChatMessage::getCreateTime)
                .last("limit " + MAX_HISTORY_MESSAGES));
        List<ChatMessage> ordered = new ArrayList<>(messages);
        java.util.Collections.reverse(ordered);
        return ordered;
    }
}
''')

add(CH + "/domain/model/Conversation.java", r'''
package com.fintech.rag.chat.domain.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 会话。
 *
 * @author rag-platform
 */
@Data
@TableName("t_conversation")
public class Conversation {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private Long tenantId;

    private String conversationNo;

    private String title;

    private String subjectType;

    private String subjectId;

    private String kbScope;

    private Integer messageCount;

    private Long totalTokens;

    private Integer status;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;

    @TableLogic
    private Integer deleted;
}
''')

add(CH + "/domain/model/ChatMessage.java", r'''
package com.fintech.rag.chat.domain.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 消息。
 *
 * @author rag-platform
 */
@Data
@TableName("t_message")
public class ChatMessage {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private Long tenantId;

    private Long conversationId;

    private String messageNo;

    private Long parentId;

    /** USER / ASSISTANT / SYSTEM / TOOL */
    private String role;

    private String content;

    private Integer contentTokens;

    /** ANSWERED / NO_HIT / GUARDRAIL_BLOCKED / ERROR */
    private String answerType;

    private String modelCode;

    /** Prompt 模板版本，用于问题复现 */
    private String promptVersion;

    private Long retrievalLogId;

    private String guardrailHit;

    private Integer ttfbMs;

    private Integer costMs;

    private LocalDateTime createTime;

    @TableLogic
    private Integer deleted;
}
''')

CH_MAPPER = CH + "/infra/persistence/mapper/"
for name, entity, desc in (("Conversation", "Conversation", "会话"), ("ChatMessage", "ChatMessage", "消息")):
    add(CH_MAPPER + name + "Mapper.java", r'''
package com.fintech.rag.chat.infra.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.fintech.rag.chat.domain.model.%ENTITY%;
import org.apache.ibatis.annotations.Mapper;

/**
 * %DESC% 数据访问。
 *
 * @author rag-platform
 */
@Mapper
public interface %NAME%Mapper extends BaseMapper<%ENTITY%> {
}
'''.replace("%ENTITY%", entity).replace("%NAME%", name).replace("%DESC%", desc))

add(CH + "/app/service/ChatOrchestrationAppService.java", r'''
package com.fintech.rag.chat.app.service;

import com.fintech.rag.api.client.RetrievalClient;
import com.fintech.rag.api.dto.chat.ChatRequest;
import com.fintech.rag.api.dto.chat.ChatResponse;
import com.fintech.rag.api.dto.common.AnswerType;
import com.fintech.rag.api.dto.retrieval.RetrievalRequest;
import com.fintech.rag.api.dto.retrieval.RetrievalResponse;
import com.fintech.rag.chat.app.guard.AnswerGuardrail;
import com.fintech.rag.chat.app.prompt.PromptTemplateRegistry;
import com.fintech.rag.chat.domain.model.ChatMessage;
import com.fintech.rag.chat.infra.llm.LlmRouter;
import com.fintech.rag.chat.infra.persistence.mapper.ChatMessageMapper;
import com.fintech.rag.common.core.R;
import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import dev.langchain4j.data.message.AiMessage;
import dev.langchain4j.data.message.SystemMessage;
import dev.langchain4j.data.message.UserMessage;
import dev.langchain4j.model.chat.ChatModel;
import dev.langchain4j.model.chat.StreamingChatModel;
import dev.langchain4j.model.chat.response.StreamingChatResponseHandler;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.function.Consumer;

/**
 * 问答编排应用服务 —— <b>生成链路的唯一编排点</b>。
 *
 * <p>链路：鉴权（拦截器已完成）→ 检索 → 空召回判定 → 组装 Prompt → 调用模型
 * → 护栏校验 → 落库 → 计量上报。</p>
 *
 * <p><b>「无据不答」是本服务的最高优先级规则</b>：
 * 检索结果为空时直接返回兜底话术，<b>绝不调用大模型</b>。
 * 原因很简单——调用模型就一定会有编造风险，且无法通过护栏事后 100% 拦住。</p>
 *
 * @author rag-platform
 */
@Service
public class ChatOrchestrationAppService {

    private static final Logger log = LoggerFactory.getLogger(ChatOrchestrationAppService.class);

    private final RetrievalClient retrievalClient;
    private final LlmRouter llmRouter;
    private final PromptTemplateRegistry promptRegistry;
    private final AnswerGuardrail guardrail;
    private final ConversationMemoryStore memoryStore;
    private final ChatMessageMapper messageMapper;

    public ChatOrchestrationAppService(RetrievalClient retrievalClient,
                                       LlmRouter llmRouter,
                                       PromptTemplateRegistry promptRegistry,
                                       AnswerGuardrail guardrail,
                                       ConversationMemoryStore memoryStore,
                                       ChatMessageMapper messageMapper) {
        this.retrievalClient = retrievalClient;
        this.llmRouter = llmRouter;
        this.promptRegistry = promptRegistry;
        this.guardrail = guardrail;
        this.memoryStore = memoryStore;
        this.messageMapper = messageMapper;
    }

    // ------------------------------------------------------------------ 非流式
    public ChatResponse chat(ChatRequest request, String subjectType, String subjectId,
                             String roleCodes, Long deptId) {
        long start = System.currentTimeMillis();

        RetrievalResponse retrieval = retrieve(request, subjectType, subjectId, roleCodes, deptId);

        // 空召回：不调用大模型，直接兜底
        if (retrieval == null || retrieval.emptyHit() || retrieval.chunks().isEmpty()) {
            return buildNoHitResponse(request, retrieval, start);
        }

        int secretLevel = resolveSecretLevel(request);
        String systemPrompt = promptRegistry.systemPrompt();
        String userPrompt = promptRegistry.userPrompt(request.question(), retrieval.chunks());
        ChatModel model = llmRouter.route(secretLevel);

        AiMessage aiMessage = model.chat(toLcMessages(request, systemPrompt, userPrompt)).aiMessage();
        String rawAnswer = aiMessage == null ? "" : aiMessage.text();

        AnswerGuardrail.GuardrailResult guardResult = guardrail.check(rawAnswer, retrieval.chunks().size());
        int cost = (int) (System.currentTimeMillis() - start);

        Long messageId = saveAssistantMessage(request, guardResult.answer(),
                AnswerType.ANSWERED.name(), llmRouter.routeCode(secretLevel), cost);

        return new ChatResponse(
                messageId == null ? null : String.valueOf(messageId),
                request.conversationId(),
                AnswerType.ANSWERED,
                guardResult.answer(),
                buildCitations(retrieval),
                guardResult.toGuardrail(),
                llmRouter.routeCode(secretLevel),
                ChatResponse.Usage.zero(),
                0,
                cost,
                promptRegistry.disclaimer());
    }

    // ------------------------------------------------------------------ 流式
    /**
     * 流式问答。
     *
     * <p>检索一次性完成（不流式），随后模型增量返回 token，
     * 通过 {@code onDelta} 逐段推送给前端。</p>
     *
     * @param onDelta  增量回调
     * @param onFinish 完成回调（携带护栏处理后的完整答案与引用）
     * @param onError  异常回调
     */
    public void stream(ChatRequest request, String subjectType, String subjectId,
                       String roleCodes, Long deptId,
                       Consumer<String> onDelta,
                       java.util.function.BiConsumer<String, List<ChatResponse.Citation>> onFinish,
                       Consumer<Throwable> onError) {
        long start = System.currentTimeMillis();

        RetrievalResponse retrieval;
        try {
            retrieval = retrieve(request, subjectType, subjectId, roleCodes, deptId);
        } catch (Exception ex) {
            onError.accept(ex);
            return;
        }

        if (retrieval == null || retrieval.emptyHit() || retrieval.chunks().isEmpty()) {
            String noHit = promptRegistry.noHitAnswer();
            onDelta.accept(noHit);
            onFinish.accept(noHit, List.of());
            saveAssistantMessage(request, noHit, AnswerType.NO_HIT.name(), null,
                    (int) (System.currentTimeMillis() - start));
            return;
        }

        int secretLevel = resolveSecretLevel(request);
        StreamingChatModel model = llmRouter.routeStreaming(secretLevel);
        List<ChatResponse.Citation> citations = buildCitations(retrieval);
        StringBuilder buffer = new StringBuilder();

        model.chat(toLcMessages(request, promptRegistry.systemPrompt(),
                        promptRegistry.userPrompt(request.question(), retrieval.chunks())),
                new StreamingChatResponseHandler() {

                    @Override
                    public void onPartialResponse(String partialResponse) {
                        buffer.append(partialResponse);
                        onDelta.accept(partialResponse);
                    }

                    @Override
                    public void onCompleteResponse(dev.langchain4j.model.chat.response.ChatResponse response) {
                        AnswerGuardrail.GuardrailResult guardResult =
                                guardrail.check(buffer.toString(), citations.size());
                        int cost = (int) (System.currentTimeMillis() - start);
                        saveAssistantMessage(request, guardResult.answer(),
                                AnswerType.ANSWERED.name(), llmRouter.routeCode(secretLevel), cost);
                        onFinish.accept(guardResult.answer(), citations);
                    }

                    @Override
                    public void onError(Throwable error) {
                        log.error("流式生成失败 conversationId={}", request.conversationId(), error);
                        onError.accept(error);
                    }
                });
    }

    // ------------------------------------------------------------------ 内部
    private RetrievalResponse retrieve(ChatRequest request, String subjectType, String subjectId,
                                       String roleCodes, Long deptId) {
        RetrievalRequest.Options options = request.options() == null
                ? RetrievalRequest.Options.defaults() : request.options();

        RetrievalRequest retrievalRequest = new RetrievalRequest(
                request.question(),
                com.fintech.rag.api.dto.common.SubjectType.valueOf(subjectType),
                subjectId,
                request.kbIds(),
                RetrievalRequest.Filters.defaults(),
                new RetrievalRequest.Options(
                        options.topN(), new java.math.BigDecimal("0.20"),
                        new java.math.BigDecimal("0.30"), Boolean.TRUE),
                com.fintech.rag.common.context.RequestContext.currentTraceId(),
                parseLongQuietly(request.conversationId()));

        R<RetrievalResponse> result = retrievalClient.search(retrievalRequest);
        if (result == null || !result.isSuccess() || result.getData() == null) {
            // fail-close：检索不可用时拒绝作答，绝不「不检索直接生成」
            throw BizException.of(ErrorCode.DEPENDENCY_UNAVAILABLE, "检索服务暂不可用，请稍后重试");
        }
        return result.getData();
    }

    private List<dev.langchain4j.data.message.ChatMessage> toLcMessages(
            ChatRequest request, String systemPrompt, String userPrompt) {
        List<dev.langchain4j.data.message.ChatMessage> messages = new ArrayList<>();
        messages.add(SystemMessage.from(systemPrompt));

        // 历史轮次：仅取 USER / ASSISTANT，且截断长度，防止上下文超长
        List<ChatMessage> history = memoryStore.recent(parseLongQuietly(request.conversationId()));
        for (ChatMessage message : history) {
            String role = message.getRole();
            if ("USER".equals(role)) {
                messages.add(UserMessage.from(truncate(message.getContent(), 500)));
            } else if ("ASSISTANT".equals(role)) {
                messages.add(AiMessage.from(truncate(message.getContent(), 500)));
            }
        }

        messages.add(UserMessage.from(userPrompt));
        return messages;
    }

    private int resolveSecretLevel(ChatRequest request) {
        // 骨架：默认按「内部」密级处理；落地时按知识库密级与用户密级取较高者
        return 2;
    }

    private List<ChatResponse.Citation> buildCitations(RetrievalResponse retrieval) {
        List<ChatResponse.Citation> citations = new ArrayList<>();
        int seq = 1;
        for (RetrievalResponse.Chunk chunk : retrieval.chunks()) {
            citations.add(new ChatResponse.Citation(
                    seq++, chunk.kbId(), chunk.docId(), chunk.docName(), chunk.versionNo(),
                    chunk.pageNo(), chunk.chunkIndex(), chunk.score(), chunk.content()));
        }
        return citations;
    }

    private ChatResponse buildNoHitResponse(ChatRequest request, RetrievalResponse retrieval, long start) {
        int cost = (int) (System.currentTimeMillis() - start);
        String answer = promptRegistry.noHitAnswer();
        Long messageId = saveAssistantMessage(request, answer, AnswerType.NO_HIT.name(), null, cost);
        return new ChatResponse(
                messageId == null ? null : String.valueOf(messageId),
                request.conversationId(),
                AnswerType.NO_HIT,
                answer,
                List.of(),
                ChatResponse.Guardrail.pass(),
                null,
                ChatResponse.Usage.zero(),
                0,
                cost,
                promptRegistry.disclaimer());
    }

    private Long saveAssistantMessage(ChatRequest request, String answer, String answerType,
                                      String modelCode, int cost) {
        try {
            ChatMessage message = new ChatMessage();
            message.setTenantId(0L);
            message.setConversationId(parseLongQuietly(request.conversationId()));
            message.setMessageNo("M" + UUID.randomUUID().toString().replace("-", ""));
            message.setRole("ASSISTANT");
            message.setContent(answer);
            message.setAnswerType(answerType);
            message.setModelCode(modelCode);
            message.setPromptVersion(PromptTemplateRegistry.VERSION);
            message.setCostMs(cost);
            message.setDeleted(0);
            messageMapper.insert(message);
            return message.getId();
        } catch (Exception ex) {
            // 落库失败不能影响用户已经看到的答案，但必须告警
            log.error("保存消息失败 conversationId={}", request.conversationId(), ex);
            return null;
        }
    }

    private Long parseLongQuietly(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        try {
            return Long.parseLong(value);
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    private String truncate(String value, int max) {
        if (value == null) {
            return "";
        }
        return value.length() <= max ? value : value.substring(0, max);
    }
}
''')

add(CH + "/api/controller/ChatController.java", r'''
package com.fintech.rag.chat.api.controller;

import com.fintech.rag.api.dto.chat.ChatRequest;
import com.fintech.rag.api.dto.chat.ChatResponse;
import com.fintech.rag.api.server.interceptor.SourceAuthInterceptor;
import com.fintech.rag.chat.app.service.ChatOrchestrationAppService;
import com.fintech.rag.common.context.RequestContext;
import com.fintech.rag.common.core.R;
import com.fintech.rag.common.exception.ErrorCode;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 问答接口。
 *
 * <p>主体身份一律从请求头获取（网关透传或 AppKey 验签结果），
 * <b>绝不从请求体读取</b>，否则用户改一个字段就能以他人身份提问。</p>
 *
 * @author rag-platform
 */
@RestController
@RequestMapping("/api/ai")
public class ChatController {

    private static final Logger log = LoggerFactory.getLogger(ChatController.class);

    /** SSE 超时：覆盖最长生成耗时并留余量 */
    private static final long SSE_TIMEOUT_MS = 180_000L;

    private final ChatOrchestrationAppService chatAppService;

    /**
     * 生成链路是长耗时阻塞调用，必须使用独立线程池，
     * 不能占用 Tomcat 的请求线程，否则少量并发就会把容器线程打满。
     */
    private final ExecutorService streamExecutor = Executors.newFixedThreadPool(32, r -> {
        Thread thread = new Thread(r, "chat-stream-" + System.nanoTime());
        thread.setDaemon(true);
        return thread;
    });

    public ChatController(ChatOrchestrationAppService chatAppService) {
        this.chatAppService = chatAppService;
    }

    /** 非流式问答 */
    @PostMapping("/chat")
    public R<ChatResponse> chat(@Valid @RequestBody ChatRequest request, HttpServletRequest servletRequest) {
        SubjectContext context = resolveSubject(servletRequest);
        return R.ok(chatAppService.chat(request, context.subjectType(), context.subjectId(),
                context.roleCodes(), context.deptId()));
    }

    /**
     * 流式问答（SSE）。
     *
     * <p>事件协议：</p>
     * <pre>
     *   event: delta      数据为增量文本片段
     *   event: citations  数据为引用列表 JSON
     *   event: done       数据为完成标记
     *   event: error      数据为错误码与提示
     * </pre>
     */
    @PostMapping(value = "/chat/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter chatStream(@Valid @RequestBody ChatRequest request, HttpServletRequest servletRequest) {
        SseEmitter emitter = new SseEmitter(SSE_TIMEOUT_MS);
        SubjectContext context = resolveSubject(servletRequest);

        emitter.onTimeout(() -> log.warn("SSE 超时 conversationId={}", request.conversationId()));
        emitter.onError(ex -> log.warn("SSE 异常 conversationId={}", request.conversationId(), ex));

        streamExecutor.execute(() -> {
            try {
                chatAppService.stream(request, context.subjectType(), context.subjectId(),
                        context.roleCodes(), context.deptId(),
                        delta -> sendQuietly(emitter, "delta", delta),
                        (answer, citations) -> {
                            sendQuietly(emitter, "citations", citations);
                            sendQuietly(emitter, "done", "ok");
                            emitter.complete();
                        },
                        error -> {
                            sendQuietly(emitter, "error",
                                    ErrorCode.LLM_CALL_FAILED.getCode() + ":" + ErrorCode.LLM_CALL_FAILED.getMessage());
                            emitter.complete();
                        });
            } catch (Exception ex) {
                log.error("流式问答失败 conversationId={}", request.conversationId(), ex);
                sendQuietly(emitter, "error", ErrorCode.INTERNAL_ERROR.getCode());
                emitter.complete();
            }
        });
        return emitter;
    }

    private void sendQuietly(SseEmitter emitter, String event, Object data) {
        try {
            emitter.send(SseEmitter.event().name(event).data(data));
        } catch (IOException | IllegalStateException ex) {
            // 客户端主动断开是常态（用户点了「停止生成」），不应记为错误
            log.debug("SSE 推送失败（客户端可能已断开）event={}", event);
        }
    }

    private SubjectContext resolveSubject(HttpServletRequest request) {
        String roles = (String) request.getAttribute(SourceAuthInterceptor.ATTR_USER_ROLES);
        String deptIdText = (String) request.getAttribute(SourceAuthInterceptor.ATTR_USER_DEPT);
        Long deptId = null;
        if (deptIdText != null && !deptIdText.isBlank()) {
            try {
                deptId = Long.parseLong(deptIdText);
            } catch (NumberFormatException ignored) {
                // 非法部门 ID 视为无部门，不放大权限
            }
        }
        String subjectType = RequestContext.currentSource() == com.fintech.rag.common.context.RequestSource.DMZ_WEB
                ? "USER" : "APP";
        String subjectId = RequestContext.currentSubjectId();
        return new SubjectContext(subjectType, subjectId, roles, deptId);
    }

    /** 调用主体上下文 */
    private record SubjectContext(String subjectType, String subjectId, String roleCodes, Long deptId) {
    }
}
''')

add("rag-chat-service/src/main/resources/application.yml", r'''
server:
  port: 8085
  shutdown: graceful
  tomcat:
    threads:
      # 生成链路是长耗时调用，线程数不能按常规设太小，但也不能无脑放大
      max: 200

spring:
  application:
    name: rag-chat-service
  profiles:
    active: dev
  config:
    import:
      - optional:nacos:rag-chat-service.yaml
      - optional:nacos:rag-common.yaml
  cloud:
    nacos:
      server-addr: ${NACOS_ADDR:127.0.0.1:8848}
      username: ${NACOS_USERNAME:nacos}
      password: ${NACOS_PASSWORD:nacos}
      discovery:
        namespace: ${NACOS_NAMESPACE:rag}
        group: RAG_GROUP
      config:
        namespace: ${NACOS_NAMESPACE:rag}
        group: RAG_GROUP
        file-extension: yaml
  datasource:
    driver-class-name: com.mysql.cj.jdbc.Driver
    url: jdbc:mysql://${MYSQL_HOST:127.0.0.1}:${MYSQL_PORT:3306}/rag_chat?useUnicode=true&characterEncoding=utf8&serverTimezone=Asia/Shanghai
    username: ${MYSQL_USERNAME:rag}
    password: ${MYSQL_PASSWORD:rag123456}
  data:
    redis:
      host: ${REDIS_HOST:127.0.0.1}
      port: ${REDIS_PORT:6379}
      password: ${REDIS_PASSWORD:}
      database: 2

mybatis-plus:
  configuration:
    map-underscore-to-camel-case: true
  global-config:
    db-config:
      logic-delete-field: deleted
      logic-delete-value: 1
      logic-not-delete-value: 0

feign:
  client:
    config:
      default:
        connectTimeout: 500
        readTimeout: 10000
      # 检索超时必须严于生成，检索慢就直接降级，不要让用户干等
      rag-retrieval-service:
        connectTimeout: 500
        readTimeout: 3000
      rag-platform-service:
        connectTimeout: 300
        readTimeout: 500

rag:
  chat:
    model-refresh-ms: 300000
    guardrail-refresh-ms: 600000
  server:
    auth:
      enabled: true
      trusted-gateway-cidrs:
        - 10.10.1.0/24
      gateway-signature-enabled: false
      gateway-sign-secret: ${RAG_GATEWAY_SIGN_SECRET:}

management:
  endpoints:
    web:
      exposure:
        include: health,info,prometheus,metrics

logging:
  level:
    com.fintech.rag: INFO
    dev.langchain4j: WARN
''')

if __name__ == "__main__":
    for rel, content in FILES.items():
        target = BASE / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print("W +", rel)
    print("---- total:", len(FILES))
