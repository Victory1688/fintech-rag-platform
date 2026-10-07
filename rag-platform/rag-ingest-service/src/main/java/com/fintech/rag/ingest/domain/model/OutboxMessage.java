package com.fintech.rag.ingest.domain.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 本地消息表（Outbox）。
 *
 * <p><b>为什么必须有这张表：</b>入库成功需要「更新任务状态」+「通知下游可检索」。
 * 若直接发 MQ，存在「写库成功但消息丢失」与「消息已发但事务回滚」两种不一致。
 * 正确做法是：同库同事务写入本表，再由定时任务投递 MQ，投递成功才标记 SENT，
 * 从而把「本地事务」与「消息投递」解耦成「至少一次投递 + 下游幂等」。</p>
 *
 * @author rag-platform
 */
@Data
@TableName("t_outbox")
public class OutboxMessage {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private Long tenantId;

    /** 业务消息 ID，下游幂等键 */
    private String messageId;

    private String topic;

    private String tag;

    private String bizKey;

    /** JSON 负载 */
    private String payload;

    /** NEW / SENT / FAILED */
    private String status;

    private Integer retryCount;

    private LocalDateTime nextRetryAt;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;
}
