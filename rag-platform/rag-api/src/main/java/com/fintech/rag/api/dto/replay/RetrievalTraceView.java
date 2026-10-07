package com.fintech.rag.api.dto.replay;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 检索段视图 —— 回放时展示「这次回答当时检索到了什么」。
 *
 * <p><b>刻意不包含召回片段原文</b>：片段原文即知识库正文，是整套系统里最敏感的数据。
 * 回放接口的价值在于「看清链路与统计」，不在「搬运正文」——
 * 要正文请走带审计留痕的知识库详情接口。少传一个字段，
 * 就少一条「回放接口被当成批量导出通道」的风险路径。</p>
 *
 * <p>{@code originalQuery} / {@code rewrittenQuery} 属于<b>用户提问侧</b>数据，
 * 敏感度低于片段原文，但仍按内容采集档位控制（METRICS_ONLY 下返回 null）。</p>
 *
 * @param traceId         链路 ID
 * @param conversationId  会话 ID
 * @param subjectType     主体类型
 * @param originalQuery   原始问题（受内容档位控制，可能为 null）
 * @param rewrittenQuery  改写后的检索式（受内容档位控制，可能为 null）
 * @param kbIds           服务端推导后的实际检索范围
 * @param chunkCount      最终召回片段数
 * @param topScore        最高分
 * @param cacheHit        是否命中缓存
 * @param rerankUsed      是否启用精排
 * @param costMs          检索总耗时
 * @param ragflowCostMs   RAGFlow 调用耗时
 * @param result          1 成功 / 0 失败
 * @param errorCode       失败错误码
 * @param createTime      发生时间
 * @author rag-platform
 */
public record RetrievalTraceView(String traceId,
                                 Long conversationId,
                                 String subjectType,
                                 String originalQuery,
                                 String rewrittenQuery,
                                 String kbIds,
                                 Integer chunkCount,
                                 BigDecimal topScore,
                                 Integer cacheHit,
                                 Integer rerankUsed,
                                 Integer costMs,
                                 Integer ragflowCostMs,
                                 Integer result,
                                 String errorCode,
                                 LocalDateTime createTime) {

    /** 空召回判定：链路回放时用于「是没召回到，还是召回了没用上」的快速判别 */
    public boolean emptyHit() {
        return chunkCount == null || chunkCount == 0;
    }
}
