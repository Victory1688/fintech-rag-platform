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
