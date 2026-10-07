package com.fintech.rag.api.dto.eval;

import jakarta.validation.constraints.NotBlank;

import java.math.BigDecimal;

/**
 * 人工评分请求（运营 / 业务专家在后台打分）。
 *
 * <p><b>准入约束</b>：本接口只允许内网应用（AppKey + HMAC 签名）调用，
 * 不允许终端用户直接调用 —— 否则用户可以给自己的问题刷分，
 * 把质量看板变成噪音源。鉴权由 {@code SourceAuthInterceptor} 承担。</p>
 *
 * <p><b>不接收的字段（刻意）</b>：</p>
 * <ul>
 *   <li>{@code passed} —— 由服务端按 metric 的阈值算出，绝不接受调用方传入；</li>
 *   <li>{@code judgeModel} —— 人工评分的裁判是人，写模型名会污染归因统计；</li>
 *   <li>{@code evalSource} —— 本接口恒为 MANUAL，不可篡改。</li>
 * </ul>
 *
 * @param traceId        被评估回答的 traceId（与 messageId 二选一，优先 traceId）
 * @param messageId      被评估的助手消息 ID
 * @param metricCode     指标码，见 {@code EvalMetric}
 * @param score          得分，量纲 0~1
 * @param reason         评分理由（**禁止写问答原文**，只写结论与依据类型）
 * @author rag-platform
 */
public record ManualEvalRequest(String traceId,
                                String messageId,
                                @NotBlank(message = "指标码不能为空") String metricCode,
                                @NotBlank(message = "得分不能为空") BigDecimal score,
                                String reason) {
}
