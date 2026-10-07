package com.fintech.rag.api.dto.replay;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;

/**
 * 一次回答的完整回放视图 —— <b>把 traceId 翻译成「人话」</b>。
 *
 * <p><b>设计原则：默认不返回任何问答原文与片段原文。</b>
 * 回放的核心价值在于「看清链路与统计」（是否召回到、用了哪个模型、慢在哪一步、
 * 引用了哪份文件的哪个版本、系统给自己打了多少分），这些都不需要正文。
 * 正文是否可见由统一的内容采集档位决定（见 {@code ReplayAppService}），
 * 不为回放单独开后门 —— 后门一旦存在，它就会成为批量导出通道。</p>
 *
 * <p><b>为什么要有 {@code degraded}</b>：回放的价值在依赖挂掉时才最大
 * （出了问题才来回放）。因此检索服务不可达时不能整体失败，
 * 而要返回能拿到的那部分，并把缺失原因<b>显式列出来</b>。
 * 「少了一块且知道为什么少」远胜于「整个页面报 500」。</p>
 *
 * @param traceId        链路 ID
 * @param found          是否找到任何关联数据；false 表示该 traceId 不存在或已超出留存期
 * @param degraded       降级说明列表（依赖不可达、数据缺失等），空列表表示数据完整
 * @param conversation   会话摘要
 * @param messages       消息列表（按时间正序，用户与助手成对）
 * @param citations      引用列表（默认不含正文，只给位置与分数）
 * @param tokenUsage     token 计量流水
 * @param evalScores     质量评估分数
 * @param retrievalLogs  检索段（来自 rag-retrieval-service，默认不含片段原文）
 * @param timeline       关键事件时间线 —— <b>非工程角色主要看这一段</b>
 * @param deepLinks      跳到 APM / LangFuse 的深链（无密钥，仅 URL）
 * @author rag-platform
 */
public record ReplayView(String traceId,
                         boolean found,
                         List<String> degraded,
                         ConversationBrief conversation,
                         List<MessageItem> messages,
                         List<CitationItem> citations,
                         List<TokenItem> tokenUsage,
                         List<EvalItem> evalScores,
                         List<RetrievalTraceView> retrievalLogs,
                         List<TimelineItem> timeline,
                         DeepLinks deepLinks) {

    /**
     * 会话摘要。
     *
     * <p>{@code subjectId} 已掩码（如 {@code 100***86}）：运维需要「知道是谁的会话」
     * 才能找对人对齐，但不需要看到完整账号 —— 掩码后仍可人工核对，又不构成
     * 一份可直接落盘的身份证号清单。</p>
     */
    public record ConversationBrief(Long conversationId,
                                    String conversationNo,
                                    String title,
                                    String subjectType,
                                    String subjectId,
                                    Integer status,
                                    LocalDateTime createTime) {
    }

    /**
     * 消息条目。
     *
     * @param contentOmitted true 表示正文按内容档位被省略（不是数据丢失）
     * @param answerType     ANSWERED / NO_HIT / GUARDRAIL_BLOCKED / ERROR
     */
    public record MessageItem(String messageId,
                              String role,
                              String answerType,
                              String content,
                              boolean contentOmitted,
                              String modelCode,
                              String promptVersion,
                              String guardrailHit,
                              Integer ttfbMs,
                              Integer costMs,
                              LocalDateTime createTime) {
    }

    /**
     * 引用条目（默认无正文）。
     *
     * @param contentOmitted     正文是否被省略
     * @param contentFingerprint 片段指纹：用于判断「两次回答引用的是同一段」而不泄漏正文
     */
    public record CitationItem(int seq,
                               Long kbId,
                               Long docId,
                               String docName,
                               Integer versionNo,
                               Integer pageNo,
                               Integer chunkIndex,
                               BigDecimal score,
                               boolean contentOmitted,
                               String contentFingerprint) {
    }

    /** Token 计量条目 */
    public record TokenItem(String modelCode,
                            String modelName,
                            Integer inputTokens,
                            Integer outputTokens,
                            Integer totalTokens,
                            Integer costMs,
                            LocalDate bizDate) {
    }

    /** 质量评估条目 */
    public record EvalItem(String metricCode,
                           BigDecimal score,
                           Integer scoreScale,
                           Integer passed,
                           BigDecimal threshold,
                           String evalSource,
                           String judgeModel,
                           String reason,
                           LocalDateTime createTime) {
    }

    /**
     * 时间线条目。
     *
     * @param at     发生时间（ISO 字符串，便于前端直接渲染）
     * @param stage  阶段名：SESSION / QUESTION / RETRIEVAL / GENERATE / EVALUATE
     * @param detail 人类可读摘要
     */
    public record TimelineItem(String at, String stage, String detail) {
    }

    /**
     * 深链。
     *
     * <p>模板由配置提供（{@code rag.replay.*-url-template}），<b>不含任何密钥</b>。
     * 若未配置则返回 null，前端不展示对应入口 —— 而不是给一个点了 404 的链接。</p>
     */
    public record DeepLinks(String apm,
                            String langfuse,
                            String retrievalLog) {
    }
}
