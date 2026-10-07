package com.fintech.rag.knowledge.domain.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.annotation.Version;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 知识库。
 *
 * <p>{@code version} 是检索缓存的失效锚点：内容或检索参数变更即 +1，
 * 使旧缓存自然不再命中，无需精确删除缓存 Key。</p>
 *
 * @author rag-platform
 */
@Data
@TableName("t_knowledge_base")
public class KnowledgeBase {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private Long tenantId;

    private String kbCode;

    private String kbName;

    private String description;

    /** PRODUCT / POLICY / REGULATION / INTERNAL / CASE */
    private String category;

    /** RAGFlow Dataset ID */
    private String ragflowDatasetId;

    private String embeddingModel;

    private String chunkMethod;

    private Integer chunkTokenNum;

    private BigDecimal similarityThreshold;

    private BigDecimal vectorSimilarityWeight;

    private Integer topK;

    private String rerankModel;

    private Integer secretLevel;

    private String bizChannel;

    private Long ownerDeptId;

    private Long ownerUserId;

    private Integer docCount;

    private Long chunkCount;

    /** 版本号，用于检索缓存失效 */
    @Version
    private Long version;

    private Integer status;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;

    private String createBy;

    @TableLogic
    private Integer deleted;
}
