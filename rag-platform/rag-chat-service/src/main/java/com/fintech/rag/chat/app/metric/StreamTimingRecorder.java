package com.fintech.rag.chat.app.metric;

import com.fintech.rag.common.observability.GenAiSemconv;
import io.micrometer.core.instrument.MeterRegistry;

import java.time.Duration;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;

/**
 * 流式计时器 —— 手工埋点的 TTFT / TTFC（无法自动获得）。
 *
 * <p>OpenTelemetry 自 v1.41.0 定义了对应指标名，本节按规范名上报：</p>
 * <ul>
 *   <li>{@code gen_ai.client.operation.time_to_first_chunk} —— 首字延迟</li>
 *   <li>{@code gen_ai.client.operation.time_per_output_chunk} —— 吐字间隔</li>
 * </ul>
 *
 * <p><b>口径提醒</b>：本类的首字延迟从「请求进入编排层」开始计时，<b>包含检索耗时</b>，
 * 这是用户真实感知的延迟；而模型 span 的 duration 只含模型调用。两者不可混用，
 * 看板必须分开画，否则会得出「模型变快了但用户觉得更慢」这类矛盾结论。</p>
 *
 * @author rag-platform
 */
public class StreamTimingRecorder {

    private static final long MAX_SANE_GAP_NANOS = Duration.ofSeconds(10).toNanos();

    private final MeterRegistry meterRegistry;
    private final long startNanos;
    private final String model;
    private final String appSource;

    private final AtomicInteger chunks = new AtomicInteger();
    private final AtomicLong lastChunkNanos = new AtomicLong();
    private final AtomicLong firstChunkNanos = new AtomicLong();

    public StreamTimingRecorder(MeterRegistry meterRegistry, long startNanos,
                                String model, String appSource) {
        this.meterRegistry = meterRegistry;
        this.startNanos = startNanos;
        this.model = model;
        this.appSource = appSource;
        this.lastChunkNanos.set(startNanos);
    }

    /** 每收到一个增量片段调用一次 */
    public void onChunk() {
        long now = System.nanoTime();
        int index = chunks.incrementAndGet();
        if (index == 1) {
            firstChunkNanos.set(now);
            record(GenAiSemconv.METRIC_TIME_TO_FIRST_CHUNK, now - startNanos);
            return;
        }
        long gap = now - lastChunkNanos.get();
        lastChunkNanos.set(now);
        // 滤掉离群值：GC 停顿与网络抖动会把均值拉偏
        if (gap > 0 && gap < MAX_SANE_GAP_NANOS) {
            record(GenAiSemconv.METRIC_TIME_PER_OUTPUT_CHUNK, gap);
        }
    }

    /** 首字延迟（毫秒）；未收到任何片段时返回 null */
    public Integer firstChunkMs() {
        long first = firstChunkNanos.get();
        return first == 0 ? null : (int) ((first - startNanos) / 1_000_000L);
    }

    public int chunkCount() {
        return chunks.get();
    }

    private void record(String metric, long nanos) {
        meterRegistry.timer(metric,
                        GenAiSemconv.TAG_REQUEST_MODEL, model,
                        GenAiSemconv.TAG_APP_SOURCE, appSource)
                .record(Duration.ofNanos(Math.max(nanos, 0)));
    }
}
