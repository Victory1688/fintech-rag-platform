package com.fintech.rag.ingest.domain.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.EnumSet;
import java.util.Set;

/**
 * 文档入库任务。
 *
 * <p>解析状态机内聚在本类中，<b>禁止在业务代码里散落 {@code if (status == X) update(Y)}</b>，
 * 否则状态会漂移到非法组合（例如从 FAILED 直接跳到 PARSED）。</p>
 *
 * @author rag-platform
 */
@Data
@TableName("t_ingest_task")
public class IngestTask {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private Long tenantId;

    private String taskNo;

    private Long kbId;

    private Long docId;

    private String fileName;

    private String fileMd5;

    private Long fileSize;

    private String minioObjectKey;

    private String ragflowDocumentId;

    private String status;

    private String currentStep;

    private Integer progress;

    private Integer retryCount;

    private Integer maxRetry;

    private String errorCode;

    private String errorMsg;

    private Integer chunkNum;

    private Long costMs;

    private String submittedBy;

    private LocalDateTime submittedAt;

    private LocalDateTime finishedAt;

    private LocalDateTime updateTime;

    @TableLogic
    private Integer deleted;

    /** 解析状态 */
    public enum Status {
        /** 已落盘，待上传 */
        PENDING,
        /** 已入 RAGFlow，待解析 */
        UPLOADED,
        /** 解析中 */
        PARSING,
        /** 解析完成，可检索 */
        PARSED,
        /** 解析失败，可重试 */
        FAILED,
        /** 已下线 */
        OFFLINE,
        /** 已取消 */
        CANCELED
    }

    private static final java.util.Map<Status, Set<Status>> TRANSITIONS = java.util.Map.of(
            Status.PENDING, EnumSet.of(Status.UPLOADED, Status.CANCELED),
            Status.UPLOADED, EnumSet.of(Status.PARSING, Status.FAILED, Status.CANCELED),
            Status.PARSING, EnumSet.of(Status.PARSED, Status.FAILED),
            Status.FAILED, EnumSet.of(Status.UPLOADED),
            Status.PARSED, EnumSet.of(Status.OFFLINE),
            Status.OFFLINE, EnumSet.of(Status.UPLOADED),
            Status.CANCELED, EnumSet.noneOf(Status.class)
    );

    /** 校验状态迁移是否合法 */
    public static boolean canTransit(String from, String to) {
        try {
            Status f = Status.valueOf(from);
            Status t = Status.valueOf(to);
            return TRANSITIONS.getOrDefault(f, EnumSet.noneOf(Status.class)).contains(t);
        } catch (IllegalArgumentException ex) {
            return false;
        }
    }
}
