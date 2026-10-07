package com.fintech.rag.chat.domain.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 消息。
 *
 * @author rag-platform
 */
@Data
@TableName("t_message")
public class ChatMessage {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private Long tenantId;

    private Long conversationId;

    private String messageNo;

    private Long parentId;

    /** USER / ASSISTANT / SYSTEM / TOOL */
    private String role;

    private String content;

    private Integer contentTokens;

    /** ANSWERED / NO_HIT / GUARDRAIL_BLOCKED / ERROR */
    private String answerType;

    private String modelCode;

    /** Prompt 模板版本，用于问题复现 */
    private String promptVersion;

    private Long retrievalLogId;

    private String guardrailHit;

    /**
     * 全链路 traceId（W3C 32 位 hex）。
     *
     * <p>用途：把「本地消息」与「可观测平台里的那条 Trace」对上。
     * 用户点踩时先查消息拿 traceId，再去 LangFuse 按 traceId 回放完整链路 ——
     * 这是定位问题最快的路径。必须落库，因为 Trace 有 TTL 而本字段不会过期。</p>
     */
    private String traceId;

    /** 首字节时间（毫秒），流式场景的核心体验指标 */
    private Integer ttfbMs;

    private Integer costMs;

    private LocalDateTime createTime;

    @TableLogic
    private Integer deleted;
}
