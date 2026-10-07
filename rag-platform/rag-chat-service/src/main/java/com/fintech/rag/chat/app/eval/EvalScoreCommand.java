package com.fintech.rag.chat.app.eval;

import com.fintech.rag.api.dto.common.EvalSource;

import java.math.BigDecimal;

/**
 * 评估分数写入命令 —— 承载全部需要落库的「快照」字段。
 *
 * <p><b>刻意不包含 {@code passed}</b>：是否通过门禁必须由写入入口按阈值算出。
 * 让调用方传 passed 只有两种结局 —— 要么各调用方算法不一致，
 * 要么有人为了让门禁通过而直接传 true。两者都会让质量报告失去意义。</p>
 *
 * @param traceId       被评估回答的 W3C traceId（与 t_message.trace_id 对齐）
 * @param messageId     被评估的助手消息 ID
 * @param conversationId 会话 ID
 * @param evalBatchNo   离线批次号，ONLINE / MANUAL 时为 null
 * @param evalSource    来源
 * @param judgeModel    裁判模型编码快照；ONLINE / BATCH 必填，MANUAL 必须为 null
 * @param promptVersion 被评估回答的 Prompt 版本快照（可空，但强烈建议填写）
 * @param metricCode    指标码，白名单见 EvalMetric
 * @param score         得分，量纲 0~1
 * @param threshold     门禁阈值快照；为 null 时取指标默认阈值
 * @param reason        评分理由（禁止写问答原文）
 * @param createBy      写入者（人工评估为操作人；自动评估为空）
 * @author rag-platform
 */
public record EvalScoreCommand(String traceId,
                               Long messageId,
                               Long conversationId,
                               String evalBatchNo,
                               EvalSource evalSource,
                               String judgeModel,
                               String promptVersion,
                               String metricCode,
                               BigDecimal score,
                               BigDecimal threshold,
                               String reason,
                               String createBy) {
}
