package com.fintech.rag.chat.api.controller;

import com.fintech.rag.api.dto.common.EvalMetric;
import com.fintech.rag.api.dto.common.EvalSource;
import com.fintech.rag.api.dto.eval.ManualEvalRequest;
import com.fintech.rag.chat.app.eval.EvalScoreCommand;
import com.fintech.rag.chat.app.eval.LlmEvalScoreAppService;
import com.fintech.rag.chat.domain.model.LlmEvalScore;
import com.fintech.rag.common.context.RequestContext;
import com.fintech.rag.common.core.R;
import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.math.BigDecimal;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 人工评估接口 —— 运营 / 业务专家对具体回答打分。
 *
 * <p><b>准入</b>：只能由内网应用（AppKey + HMAC 签名）调用，由
 * {@code SourceAuthInterceptor} 强制 —— 不额外写角色判断，因为
 * 「内网应用」本身就是受控集合，而终端用户绝不能给自己刷分。</p>
 *
 * <p><b>为什么人工评分值得单独做一个接口</b>：LLM-as-judge 与规则指标都无法回答
 * 「这个答案业务上到底对不对」。人工评分是<b>黄金集的唯一来源</b>，
 * 也是争议样本定调的手段 —— 它同时也是校准自动评估器的基准。</p>
 *
 * @author rag-platform
 */
@RestController
@RequestMapping("/api/ai")
public class EvalController {

    private final LlmEvalScoreAppService evalScoreAppService;

    public EvalController(LlmEvalScoreAppService evalScoreAppService) {
        this.evalScoreAppService = evalScoreAppService;
    }

    /**
     * 人工评分。
     *
     * <p>不接收 traceId 之外的「被评估内容」——评分对象是库里已有的那条回答，
     * 由 messageId / traceId 定位，避免调用方通过本接口塞入任意文本。</p>
     */
    @PostMapping("/eval/manual")
    public R<Map<String, Object>> manual(@Valid @RequestBody ManualEvalRequest request) {
        if (request.traceId() == null && request.messageId() == null) {
            throw BizException.of(ErrorCode.PARAM_INVALID, "traceId 与 messageId 至少提供一个");
        }

        // 指标白名单在此先校验一次，让错误在参数层暴露（写入入口还会再校验一次，双保险）
        EvalMetric metric;
        try {
            metric = EvalMetric.of(request.metricCode());
        } catch (IllegalArgumentException ex) {
            throw BizException.of(ErrorCode.PARAM_INVALID, ex.getMessage());
        }

        LlmEvalScore saved = evalScoreAppService.record(new EvalScoreCommand(
                request.traceId(),
                parseLong(request.messageId()),
                null,
                null,
                EvalSource.MANUAL,
                null,
                null,
                metric.name(),
                request.score(),
                null,
                request.reason(),
                RequestContext.currentSubjectId()));

        Map<String, Object> data = new LinkedHashMap<>();
        data.put("scoreId", saved.getId() == null ? null : String.valueOf(saved.getId()));
        data.put("metricCode", saved.getMetricCode());
        data.put("score", saved.getScore() == null ? null : saved.getScore().toPlainString());
        data.put("threshold", saved.getThreshold() == null ? null : saved.getThreshold().toPlainString());
        data.put("passed", saved.getPassed());
        data.put("scoreScale", saved.getScoreScale());
        return R.ok(data);
    }

    private Long parseLong(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        try {
            return Long.parseLong(value);
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    /** 保留给未来「批量导入人工评分」使用的量纲常量，避免调用方各写各的 */
    public static final BigDecimal SCORE_SCALE_ONE = BigDecimal.ONE;
}
