package com.fintech.rag.knowledge.domain.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 文档。
 *
 * @author rag-platform
 */
@Data
@TableName("t_document")
public class KbDocument {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private Long tenantId;

    private Long kbId;

    private String docCode;

    private String docName;

    private String fileType;

    private Long fileSize;

    /** 用于重复检测 */
    private String fileMd5;

    private String minioBucket;

    private String minioObjectKey;

    private Long currentVersionId;

    private Integer versionNo;

    private Integer secretLevel;

    /** 生效日期，参与检索过滤 */
    private LocalDate effectiveDate;

    /** 失效日期，参与检索过滤 */
    private LocalDate expireDate;

    private Long sourceDeptId;

    private Long ownerUserId;

    private String tags;

    private Integer chunkNum;

    private String ragflowDocumentId;

    /** PENDING / UPLOADED / PARSING / PARSED / FAILED / OFFLINE */
    private String parseStatus;

    private String parseError;

    private Integer parseTimeMs;

    private String offlineReason;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;

    private String createBy;

    @TableLogic
    private Integer deleted;
}
