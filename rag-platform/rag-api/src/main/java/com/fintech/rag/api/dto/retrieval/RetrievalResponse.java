package com.fintech.rag.api.dto.retrieval;

import java.util.List;

/**
 * 检索响应契约。
 *
 * @param query          原始问题
 * @param rewrittenQuery Query 改写后的检索式
 * @param chunks         召回片段，已按分数降序
 * @param emptyHit       true 表示空召回，上层必须走「无据不答」分支，禁止调用大模型
 * @param cacheHit       是否命中缓存
 * @param costMs         检索总耗时（含改写、Rerank）
 * @author rag-platform
 */
public record RetrievalResponse(String query,
                                String rewrittenQuery,
                                List<Chunk> chunks,
                                boolean emptyHit,
                                boolean cacheHit,
                                long costMs) {

    /**
     * 召回片段。
     *
     * @param chunkId     片段 ID（RAGFlow chunk id）
     * @param kbId        知识库 ID
     * @param docId       文档 ID
     * @param docName     文档名（用于引用展示）
     * @param versionNo   文档版本号（引用需标注版本，避免引用过期内容）
     * @param chunkIndex  片段在文档内的序号
     * @param pageNo      页码（解析可得时）
     * @param content     片段原文
     * @param score       最终得分
     * @param vectorScore 向量相似度
     * @param termScore   关键词相似度
     */
    public record Chunk(String chunkId,
                        Long kbId,
                        Long docId,
                        String docName,
                        Integer versionNo,
                        Integer chunkIndex,
                        Integer pageNo,
                        String content,
                        Double score,
                        Double vectorScore,
                        Double termScore) {
    }

    /** 空召回的标准返回，上层据此走兜底话术 */
    public static RetrievalResponse empty(String query, String rewrittenQuery, long costMs) {
        return new RetrievalResponse(query, rewrittenQuery, List.of(), true, false, costMs);
    }
}
