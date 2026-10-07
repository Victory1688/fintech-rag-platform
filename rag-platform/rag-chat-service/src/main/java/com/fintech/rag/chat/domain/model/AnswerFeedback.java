package com.fintech.rag.chat.domain.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 答案反馈（{@code t_feedback}）。
 *
 * <p><b>本表是「知识库建设」最直接的输入源</b>：点踩原因按 {@code reason_code} 聚合后，
 * 「NO_HIT 占比高」说明知识缺口，「WRONG_ANSWER 占比高」说明检索或 Prompt 有问题，
 * 「OUTDATED 占比高」说明制度更新没同步到知识库 —— 三种结论对应三种完全不同的整改动作。</p>
 *
 * <p><b>不设 @TableLogic</b>：反馈记录不做逻辑删除。用户撤回反馈用 {@code handle_status}
 * 表达处理状态，物理记录必须留存（合规要求可追溯「谁在什么时候反馈过什么」）。</p>
 *
 * @author rag-platform
 */
@Data
@TableName("t_feedback")
public class AnswerFeedback {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private Long tenantId;

    private Long messageId;

    private Long conversationId;

    private String subjectType;

    private String subjectId;

    /** LIKE / DISLIKE */
    private String vote;

    /** NO_HIT / WRONG_ANSWER / OUTDATED / IRRELEVANT / OTHER */
    private String reasonCode;

    /** 补充说明（已脱敏） */
    private String comment;

    /** PENDING / PROCESSING / DONE / IGNORED */
    private String handleStatus;

    private String handler;

    private String handleNote;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;
}
