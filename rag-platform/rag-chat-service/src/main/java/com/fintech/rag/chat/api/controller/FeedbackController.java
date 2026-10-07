package com.fintech.rag.chat.api.controller;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.fintech.rag.api.dto.chat.FeedbackRequest;
import com.fintech.rag.chat.app.metric.ChatPipelineMetrics;
import com.fintech.rag.chat.domain.model.AnswerFeedback;
import com.fintech.rag.chat.domain.model.ChatMessage;
import com.fintech.rag.chat.infra.persistence.mapper.AnswerFeedbackMapper;
import com.fintech.rag.chat.infra.persistence.mapper.ChatMessageMapper;
import com.fintech.rag.common.context.RequestContext;
import com.fintech.rag.common.core.R;
import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import com.fintech.rag.common.observability.ContentSanitizer;
import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 答案反馈接口。
 *
 * <p><b>本接口是「按 traceId 回放」的常规入口</b>：用户点踩时前端只传 messageId，
 * 后端据此反查该条消息的 traceId 并返回给运营侧 —— 用户不需要理解什么是 traceId，
 * 但运营点一下就能跳到完整链路。这是把可观测能力「产品化」的关键一步：
 * 链路数据只有能被非工程角色用上，才真正解决定位效率问题。</p>
 *
 * <p><b>防刷分</b>：同一主体对同一消息只保留一条反馈（唯一键 uk_message_subject），
 * 重复提交走更新。否则「点赞率」这个指标可以被一个人刷到任意数值。</p>
 *
 * @author rag-platform
 */
@RestController
@RequestMapping("/api/ai")
public class FeedbackController {

    private static final Logger log = LoggerFactory.getLogger(FeedbackController.class);

    private static final long DEFAULT_TENANT_ID = 0L;
    private static final String STATUS_PENDING = "PENDING";

    private final AnswerFeedbackMapper feedbackMapper;
    private final ChatMessageMapper messageMapper;
    private final ChatPipelineMetrics metrics;
    private final ContentSanitizer sanitizer;

    public FeedbackController(AnswerFeedbackMapper feedbackMapper,
                              ChatMessageMapper messageMapper,
                              ChatPipelineMetrics metrics,
                              ContentSanitizer sanitizer) {
        this.feedbackMapper = feedbackMapper;
        this.messageMapper = messageMapper;
        this.metrics = metrics;
        this.sanitizer = sanitizer;
    }

    /**
     * 提交反馈。
     *
     * @return 含 traceId 的结果：前端可据此展示「已记录，可随时复盘」
     */
    @PostMapping("/feedback")
    public R<Map<String, Object>> feedback(@Valid @RequestBody FeedbackRequest request) {
        if (!request.isValidVote()) {
            throw BizException.of(ErrorCode.PARAM_INVALID, "反馈类型只能是 LIKE 或 DISLIKE");
        }

        Long messageId = parseLong(request.messageId());
        if (messageId == null) {
            throw BizException.of(ErrorCode.PARAM_INVALID, "消息ID非法");
        }

        // 反查消息：既拿到 traceId（回放钥匙），又校验消息确实存在
        ChatMessage message = messageMapper.selectById(messageId);
        if (message == null) {
            throw BizException.of(ErrorCode.PARAM_INVALID, "消息不存在或已删除");
        }

        String subjectType = subjectTypeOf();
        String subjectId = RequestContext.currentSubjectId();
        String vote = request.vote().toUpperCase(java.util.Locale.ROOT);

        AnswerFeedback existing = feedbackMapper.selectOne(Wrappers.<AnswerFeedback>lambdaQuery()
                .eq(AnswerFeedback::getMessageId, messageId)
                .eq(AnswerFeedback::getSubjectId, subjectId)
                .last("limit 1"));

        if (existing == null) {
            AnswerFeedback entity = new AnswerFeedback();
            entity.setTenantId(DEFAULT_TENANT_ID);
            entity.setMessageId(messageId);
            entity.setConversationId(message.getConversationId());
            entity.setSubjectType(subjectType);
            entity.setSubjectId(subjectId);
            entity.setVote(vote);
            entity.setReasonCode(blankToNull(request.reasonCode()));
            entity.setComment(sanitizer.mask(blankToNull(request.comment())));
            entity.setHandleStatus(STATUS_PENDING);
            feedbackMapper.insert(entity);
        } else {
            existing.setVote(vote);
            existing.setReasonCode(blankToNull(request.reasonCode()));
            existing.setComment(sanitizer.mask(blankToNull(request.comment())));
            // 用户改了反馈内容，处理状态退回待处理：此前若有运营已处理，结论已不适用
            existing.setHandleStatus(STATUS_PENDING);
            feedbackMapper.updateById(existing);
        }

        metrics.recordFeedback(vote, blankToNull(request.reasonCode()));

        log.info("收到答案反馈 messageId={} vote={} reasonCode={} traceId={}",
                messageId, vote, request.reasonCode(), message.getTraceId());

        return R.ok(Map.of(
                "messageId", request.messageId(),
                "vote", vote,
                // 把 traceId 回带给调用方：运营端凭此一键回放本次回答
                "traceId", message.getTraceId() == null ? "" : message.getTraceId(),
                "replayPath", "/api/ai/replay/" + (message.getTraceId() == null ? "" : message.getTraceId())));
    }

    private String subjectTypeOf() {
        return RequestContext.currentSource() == com.fintech.rag.common.context.RequestSource.DMZ_WEB
                ? "USER" : "APP";
    }

    private Long parseLong(String value) {
        try {
            return Long.parseLong(value);
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    private String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value;
    }
}
