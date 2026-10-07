package com.fintech.rag.api.dto.chat;

import jakarta.validation.constraints.NotBlank;

/**
 * 答案反馈请求（点赞 / 点踩）。
 *
 * <p><b>本接口是「按 traceId 回放」的最短路入口</b>：用户点踩时，
 * 运营只需要 messageId，系统据此反查 {@code t_message.trace_id}，
 * 再拿 traceId 去拉完整链路 —— 用户不需要知道什么是 traceId。</p>
 *
 * @param messageId      被反馈的助手消息 ID（必填）
 * @param vote           LIKE / DISLIKE
 * @param reasonCode     点踩原因：NO_HIT / WRONG_ANSWER / OUTDATED / IRRELEVANT / OTHER
 * @param comment        补充说明，**会做 PII 脱敏后落库**
 * @author rag-platform
 */
public record FeedbackRequest(@NotBlank(message = "消息ID不能为空") String messageId,
                              @NotBlank(message = "反馈类型不能为空") String vote,
                              String reasonCode,
                              String comment) {

    public static final String VOTE_LIKE = "LIKE";
    public static final String VOTE_DISLIKE = "DISLIKE";

    public boolean isLike() {
        return VOTE_LIKE.equalsIgnoreCase(vote);
    }

    public boolean isValidVote() {
        return VOTE_LIKE.equalsIgnoreCase(vote) || VOTE_DISLIKE.equalsIgnoreCase(vote);
    }
}
