package com.fintech.rag.chat.domain.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 会话。
 *
 * @author rag-platform
 */
@Data
@TableName("t_conversation")
public class Conversation {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private Long tenantId;

    private String conversationNo;

    private String title;

    private String subjectType;

    private String subjectId;

    private String kbScope;

    private Integer messageCount;

    private Long totalTokens;

    private Integer status;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;

    @TableLogic
    private Integer deleted;
}
