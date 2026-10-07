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
