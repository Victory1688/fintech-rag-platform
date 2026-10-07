package com.fintech.rag.chat.app.eval;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

/**
 * 在线评估配置。
 *
 * <pre>
 * rag:
 *   eval:
 *     online-enabled: true          # 总开关；关闭后不抽样，评估只能靠离线批次与人工
 *     sample-rate: 0.05             # 抽样率。5% 足够观察趋势，又不会把 token 成本推高
 *     max-concurrent: 2             # 抽样评估线程数上限，防止评估把生成链路的资源吃掉
 *     manual-metrics: [...]         # 骨架阶段仅启用「无需裁判模型即可计算」的指标
 * </pre>
 *
 * <p><b>采样率怎么定</b>：在线评估的目的是「发现趋势变化」，不是「精确统计」。
 * 5% 采样在日请求量过千时即可给出稳定的日维度曲线；把采样率设成 1.0
 * 只会让评估成本随流量线性上涨，而趋势判断并不会更准。</p>
 *
 * <p><b>为什么要有 max-concurrent</b>：评估任务与用户问答共用 CPU 与网络。
 * 不设上限时，一次流量高峰会让评估线程占满线程池，反而拖慢真实回答 ——
 * 观测手段拖垮被测系统是最典型的自伤。</p>
 *
 * @author rag-platform
 */
@ConfigurationProperties(prefix = "rag.eval")
public class EvalProperties {

    private boolean onlineEnabled = true;

    private BigDecimal sampleRate = new BigDecimal("0.05");

    private int maxConcurrent = 2;

    /** 骨架阶段启用的指标：必须是 EvalMetric 中 computableWithoutJudge=true 的那些 */
    private List<String> manualMetrics = new ArrayList<>(List.of("CITATION_COVERAGE", "CONTEXT_PRECISION"));

    public boolean isOnlineEnabled() {
        return onlineEnabled;
    }

    public void setOnlineEnabled(boolean onlineEnabled) {
        this.onlineEnabled = onlineEnabled;
    }

    public BigDecimal getSampleRate() {
        return sampleRate;
    }

    public void setSampleRate(BigDecimal sampleRate) {
        this.sampleRate = sampleRate;
    }

    public int getMaxConcurrent() {
        return maxConcurrent;
    }

    public void setMaxConcurrent(int maxConcurrent) {
        this.maxConcurrent = maxConcurrent;
    }

    public List<String> getManualMetrics() {
        return manualMetrics;
    }

    public void setManualMetrics(List<String> manualMetrics) {
        this.manualMetrics = manualMetrics;
    }
}
