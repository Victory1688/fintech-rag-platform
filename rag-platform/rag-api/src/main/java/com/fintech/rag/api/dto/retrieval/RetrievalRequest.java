package com.fintech.rag.api.dto.retrieval;

import com.fintech.rag.api.dto.common.SubjectType;

import java.math.BigDecimal;
import java.util.List;

/**
 * 检索请求契约。
 *
 * <p><strong>安全约定（务必遵守）：</strong>{@code kbIds} 只能表达「用户勾选的检索范围意图」，
 * 绝不可作为授权依据。rag-retrieval-service 必须按 {@code subjectType + subjectId}
 * 重新向 rag-platform / rag-knowledge 拉取授权知识库集合，再与 kbIds 取交集，
 * 否则前端改一个数字即可越权读取机密制度。</p>
 *
 * @param query       原始问题
 * @param subjectType 主体类型
 * @param subjectId   主体标识（userId / appId）
 * @param kbIds       用户意图范围，可为空表示「全部授权范围」
 * @param filters     业务过滤条件
 * @param options     检索调优参数
 * @param traceId     全链路追踪 ID
 * @param conversationId 会话 ID（可空，仅用于日志关联）
 * @author rag-platform
 */
public record RetrievalRequest(String query,
                               SubjectType subjectType,
                               String subjectId,
                               List<Long> kbIds,
                               Filters filters,
                               Options options,
                               String traceId,
                               Long conversationId) {

    /**
     * 业务过滤条件。
     *
     * @param secretLevelMax 最大密级，用户密级；超过该密级的内容不可召回
     * @param effectiveOnly  是否只召回在生效期内的文档
     * @param bizChannel     业务条线（小微/零售/对公）
     * @param productCode    产品编码
     * @param docIds         限定文档范围（可空）
     */
    public record Filters(Integer secretLevelMax,
                          Boolean effectiveOnly,
                          String bizChannel,
                          String productCode,
                          List<Long> docIds) {

        public static Filters defaults() {
            return new Filters(2, Boolean.TRUE, null, null, null);
        }
    }

    /**
     * 检索调优参数。默认值即生产推荐起点，最终应以评测集回归结果为准。
     *
     * @param topN                  最终返回条数
     * @param similarityThreshold   相似度阈值，低于该值视为不相关（RAGFlow 默认 0.2）
     * @param vectorSimilarityWeight 向量权重，0 纯关键词、1 纯向量（RAGFlow 默认 0.3）
     * @param useRerank             是否二次精排
     */
    public record Options(Integer topN,
                          BigDecimal similarityThreshold,
                          BigDecimal vectorSimilarityWeight,
                          Boolean useRerank) {

        public static Options defaults() {
            return new Options(8, new BigDecimal("0.20"), new BigDecimal("0.30"), Boolean.TRUE);
        }
    }
}
