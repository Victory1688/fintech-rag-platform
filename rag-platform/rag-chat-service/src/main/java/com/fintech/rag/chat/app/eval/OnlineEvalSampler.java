package com.fintech.rag.chat.app.eval;

import com.fintech.rag.api.dto.common.EvalMetric;
import com.fintech.rag.api.dto.common.EvalSource;
import com.fintech.rag.common.observability.RagOutcome;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.List;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;

/**
 * 在线抽样评估器 —— 把「线上真实回答」变成质量趋势数据。
 *
 * <p><b>两条硬约束</b>：</p>
 * <ol>
 *   <li><b>绝不阻塞回答</b>：抽样与评分都发生在回答已经交付之后，走独立有界队列；
 *       队列满时<b>直接丢弃样本</b>而不是等待 —— 评估样本丢十条规定无所谓，
 *       拖慢用户回答一条都不行；</li>
 *   <li><b>不采集文本</b>：本类只基于结构化链路事实算分，不读取问答原文、不调用大模型，
 *       因此可以在生产环境长期开启而不引入合规风险与额外推理成本。</li>
 * </ol>
 *
 * <p><b>骨架阶段的指标选择（重要）</b>：只启用「无需裁判模型即可计算」的指标。
 * {@code FAITHFULNESS} / {@code ANSWER_RELEVANCY} / {@code HALLUCINATION} 需要
 * LLM-as-judge，若此时强行用规则凑一个假分数，质量看板会比没有看板更危险 ——
 * 因为它会让人误以为幻觉已被监控。宁可空着，也不要假数据。</p>
 *
 * <p><b>代理指标的诚实说明</b>：{@code CONTEXT_PRECISION} 在业界标准定义里
 * 依赖「哪些片段真正支撑了答案」的判定，本类用「引用数 / 召回数」近似。
 * 近似值方向的单调性是对的（召回一堆没用上的片段必然拉低该值），
 * 因此适合看趋势，<b>不适合用于对外的精确质量结论</b>。</p>
 *
 * @author rag-platform
 */
@Component
public class OnlineEvalSampler {

    private static final Logger log = LoggerFactory.getLogger(OnlineEvalSampler.class);

    private final EvalProperties properties;
    private final LlmEvalScoreAppService evalScoreAppService;
    private final ExecutorService executor;
    private final AtomicLong offered = new AtomicLong();
    private final AtomicLong rejected = new AtomicLong();
    private final AtomicLong sampled = new AtomicLong();

    public OnlineEvalSampler(EvalProperties properties, LlmEvalScoreAppService evalScoreAppService) {
        this.properties = properties;
        this.evalScoreAppService = evalScoreAppService;
        this.executor = new ThreadPoolExecutor(
                1, Math.max(1, properties.getMaxConcurrent()),
                60L, TimeUnit.SECONDS,
                new ArrayBlockingQueue<>(256),
                runnable -> {
                    Thread thread = new Thread(runnable, "rag-online-eval");
                    thread.setDaemon(true);
                    return thread;
                },
                // 队列满 = 直接丢弃样本。评估丢样本无害，阻塞问答有害
                new ThreadPoolExecutor.DiscardPolicy());
    }

    /**
     * 尝试抽样评估（非阻塞，调用后立即返回）。
     *
     * <p>调用时机：回答已交付用户之后。放在交付前会引入不必要的耦合：
     * 一旦评估逻辑抛异常，回答可能被牵连失败。</p>
     */
    public void trySample(EvalSampleContext context) {
        if (context == null || !properties.isOnlineEnabled()) {
            return;
        }
        offered.incrementAndGet();
        if (!hit(context)) {
            return;
        }
        try {
            executor.execute(() -> evaluate(context));
        } catch (Exception ex) {
            rejected.incrementAndGet();
            log.debug("在线评估任务提交失败（已丢弃样本）", ex);
        }
    }

    /** 抽样判定：按采样率随机命中；错误与空召回必抽 —— 这两类样本最有诊断价值 */
    private boolean hit(EvalSampleContext context) {
        if (isDiagnostic(context.answerType())) {
            return true;
        }
        double rate = properties.getSampleRate() == null ? 0.0 : properties.getSampleRate().doubleValue();
        return Math.random() < rate;
    }

    private boolean isDiagnostic(String answerType) {
        return RagOutcome.NO_HIT.name().equals(answerType) || RagOutcome.ERROR.name().equals(answerType);
    }

    // ------------------------------------------------------------------ 评分
    private void evaluate(EvalSampleContext context) {
        try {
            sampled.incrementAndGet();
            for (String metricCode : properties.getManualMetrics()) {
                EvalMetric metric;
                try {
                    metric = EvalMetric.of(metricCode);
                } catch (IllegalArgumentException ex) {
                    log.warn("rag.eval.manual-metrics 含非法指标码 {}，已跳过", metricCode);
                    continue;
                }
                if (!metric.isComputableWithoutJudge()) {
                    // 防呆：配置里把需要裁判模型的指标打开了也不执行，避免产出假分数
                    log.warn("指标 {} 需要 LLM-as-judge，当前版本不计算（见 OnlineEvalSampler 类注释）",
                            metric.name());
                    continue;
                }
                BigDecimal score = compute(metric, context);
                if (score == null) {
                    continue;
                }
                evalScoreAppService.record(new EvalScoreCommand(
                        context.traceId(), context.messageId(), context.conversationId(),
                        null, EvalSource.ONLINE, proxyJudgeName(),
                        context.promptVersion(), metric.name(), score, null,
                        buildReason(metric, context), null));
            }
        } catch (Exception ex) {
            // 评估失败绝不能冒泡：它跑在异步线程里，冒泡只会变成一个无人处理的堆栈
            log.warn("在线评估执行失败 traceId={}", context.traceId(), ex);
        }
    }

    /** 代理指标计算。返回 null 表示本次样本无法计算该指标（不写假值） */
    private BigDecimal compute(EvalMetric metric, EvalSampleContext context) {
        return switch (metric) {
            case CITATION_COVERAGE -> citationCoverage(context);
            case CONTEXT_PRECISION -> contextPrecision(context);
            default -> null;
        };
    }

    /**
     * 引用覆盖率 = 引用数 / 期望引用数。
     *
     * <p>期望引用数取「召回片段数的下界」与 5 的较小值，且至少为 1：
     * 召回到 8 段只引 1 段，不应算满分；而召回到 1 段引 1 段，就是合理的满分。</p>
     */
    private BigDecimal citationCoverage(EvalSampleContext context) {
        if (!RagOutcome.ANSWERED.name().equals(context.answerType())) {
            // 空召回 / 护栏拦截 / 出错时，谈引用覆盖率没有意义，不写分
            return null;
        }
        int expected = Math.min(Math.max(context.chunkCount(), 1), 5);
        BigDecimal raw = BigDecimal.valueOf(context.citationCount())
                .divide(BigDecimal.valueOf(expected), 4, RoundingMode.HALF_UP);
        return clamp(raw);
    }

    /** 上下文精确率（代理）＝ 被引用的片段数 / 召回片段数。召回一堆没用上的片段会拉低此值 */
    private BigDecimal contextPrecision(EvalSampleContext context) {
        if (context.chunkCount() <= 0) {
            // 零召回时该指标无定义，写 0 会被误读成「召回质量极差」，宁可留空
            return null;
        }
        BigDecimal raw = BigDecimal.valueOf(context.citationCount())
                .divide(BigDecimal.valueOf(context.chunkCount()), 4, RoundingMode.HALF_UP);
        return clamp(raw);
    }

    private BigDecimal clamp(BigDecimal value) {
        if (value.compareTo(BigDecimal.ZERO) < 0) {
            return BigDecimal.ZERO;
        }
        return value.compareTo(BigDecimal.ONE) > 0 ? BigDecimal.ONE : value;
    }

    /**
     * 代理指标的「裁判」标识。
     *
     * <p>这里刻意不写死成真实模型名：分数由规则算出，若写成
     * {@code gpt-4o-mini} 会让后续按 judge_model 的归因分析失真 ——
     * 看起来是模型评的，其实是规则算的。写 {@code rule-proxy} 保持诚实。</p>
     */
    private String proxyJudgeName() {
        return "rule-proxy";
    }

    /** 评分理由：只写链路事实，绝不写问答原文 */
    private String buildReason(EvalMetric metric, EvalSampleContext context) {
        List<String> facts = List.of(
                metric.name(),
                "answerType=" + context.answerType(),
                "citations=" + context.citationCount(),
                "chunks=" + context.chunkCount(),
                "rawChunks=" + context.rawChunkCount(),
                "topScore=" + context.topScore(),
                "costMs=" + context.costMs());
        return String.join(" ", facts);
    }

    /** 观测用计数（可挂到 actuator / 指标，便于确认「抽样真的在跑」） */
    public long offeredCount() {
        return offered.get();
    }

    public long sampledCount() {
        return sampled.get();
    }

    public long rejectedCount() {
        return rejected.get();
    }
}
