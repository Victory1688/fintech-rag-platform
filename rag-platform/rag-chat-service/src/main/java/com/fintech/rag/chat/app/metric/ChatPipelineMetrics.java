package com.fintech.rag.chat.app.metric;

import com.fintech.rag.common.observability.GenAiSemconv;
import com.fintech.rag.common.observability.RagOutcome;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.stereotype.Component;

/**
 * 问答管线指标 —— 质量看板与告警的数据来源。
 *
 * <p><b>标签纪律（写错会导致 Prometheus 内存爆炸）</b>：只允许枚举型、有界的标签
 * （outcome / app_source / model_code / guardrail_type / vote / reason_code）；
 * <b>禁止</b>把 userId、conversationId、traceId、提问原文做成标签。</p>
 *
 * @author rag-platform
 */
@Component
public class ChatPipelineMetrics {

    private final MeterRegistry meterRegistry;

    public ChatPipelineMetrics(MeterRegistry meterRegistry) {
        this.meterRegistry = meterRegistry;
    }

    /** 记录一次回答的业务结果。空召回率 = NO_HIT / 总数，是知识库覆盖度的核心指标 */
    public void recordAnswer(RagOutcome outcome, String appSource, String modelCode) {
        meterRegistry.counter(GenAiSemconv.METRIC_CHAT_ANSWER_TOTAL,
                        GenAiSemconv.TAG_OUTCOME, outcome.name(),
                        GenAiSemconv.TAG_APP_SOURCE, safe(appSource),
                        GenAiSemconv.TAG_MODEL_CODE, safe(modelCode))
                .increment();
    }

    /** 记录护栏命中（按类型分布，用于发现「哪类护栏老在拦」） */
    public void recordGuardrailHit(String guardrailType) {
        meterRegistry.counter(GenAiSemconv.METRIC_GUARDRAIL_HIT_TOTAL,
                        GenAiSemconv.TAG_GUARDRAIL_TYPE, safe(guardrailType))
                .increment();
    }

    /** 记录用户反馈（点赞率 = like / (like + dislike)，即「采纳率」） */
    public void recordFeedback(String vote, String reasonCode) {
        meterRegistry.counter(GenAiSemconv.METRIC_FEEDBACK_TOTAL,
                        GenAiSemconv.TAG_VOTE, safe(vote),
                        GenAiSemconv.TAG_REASON_CODE, safe(reasonCode))
                .increment();
    }

    /** 开启一次流式计时（TTFC / 吐字间隔） */
    public StreamTimingRecorder startStream(long startNanos, String model, String appSource) {
        return new StreamTimingRecorder(meterRegistry, startNanos, safe(model), safe(appSource));
    }

    private String safe(String value) {
        return value == null || value.isBlank() ? "unknown" : value;
    }
}
