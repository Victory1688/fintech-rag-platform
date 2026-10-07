package com.fintech.rag.platform.domain.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 审计日志。
 *
 * <p>金融合规要求：谁、何时、问了什么、召回了哪些文档，必须可追溯。
 * 本表写入量最大，生产建议按月分区 + 冷热分层。</p>
 *
 * @author rag-platform
 */
@Data
@TableName("t_audit_log")
public class AuditLog {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private Long tenantId;

    private String traceId;

    /** QUERY / RETRIEVAL / INGEST / KB_CHANGE / AUTH / CONFIG_CHANGE */
    private String eventType;

    private String requestSource;

    private String subjectType;

    private String subjectId;

    private String subjectName;

    private String clientIp;

    private String resource;

    private String kbIds;

    private String docIds;

    /** JSON 字符串，写入前必须已完成脱敏 */
    private String detail;

    private Integer result;

    private String errorCode;

    private Integer costMs;

    private LocalDateTime eventTime;
}
