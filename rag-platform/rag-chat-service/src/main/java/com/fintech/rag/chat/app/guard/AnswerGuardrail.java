package com.fintech.rag.chat.app.guard;

import com.fintech.rag.api.client.PlatformClient;
import com.fintech.rag.api.dto.chat.ChatResponse;
import com.fintech.rag.api.dto.common.GuardrailType;
import com.fintech.rag.api.dto.platform.SensitiveRuleDTO;
import com.fintech.rag.common.core.R;
import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 答案护栏 —— <b>金融场景的合规底线</b>。
 *
 * <p>大模型本质上是在「续写最可能的文本」，它无法自我保证不编造。
 * 因此必须在外层用确定性规则做校验，而不是寄希望于提示词。</p>
 *
 * <p>本类实现的护栏（与 PRD 一一对应）：</p>
 * <ul>
 *   <li>空召回拦截（由编排层在调用模型前判定）</li>
 *   <li>引用完整性：正文 [n] 必须有对应 citation</li>
 *   <li>无引用数值告警：出现利率/额度等数值但无引用</li>
 *   <li>敏感信息脱敏：身份证 / 手机号 / 银行卡</li>
 * </ul>
 *
 * @author rag-platform
 */
@Component
public class AnswerGuardrail {

    private static final Logger log = LoggerFactory.getLogger(AnswerGuardrail.class);

    /** 引用标记 [1] [2] */
    private static final Pattern CITATION_PATTERN = Pattern.compile("\\[(\\d{1,2})]");

    /** 数值敏感表述：命中但无引用 → 追加提示并告警 */
    private static final Pattern SENSITIVE_NUMERIC_PATTERN = Pattern.compile(
            "(\\d+(?:\\.\\d+)?)\\s*(%|万元|亿元|元|天|个月|年|次)");

    private static final Pattern ID_CARD_PATTERN = Pattern.compile("\\b\\d{17}[\\dXx]\\b");
    private static final Pattern MOBILE_PATTERN = Pattern.compile("\\b1[3-9]\\d{9}\\b");
    private static final Pattern BANK_CARD_PATTERN = Pattern.compile("\\b\\d{16,19}\\b");

    private final PlatformClient platformClient;

    /** 平台下发的脱敏规则，本地缓存，定时刷新 */
    private volatile List<SensitiveRuleDTO> sensitiveRules = new ArrayList<>();

    public AnswerGuardrail(PlatformClient platformClient) {
        this.platformClient = platformClient;
    }

    @PostConstruct
    public void init() {
        refreshRules();
    }

    @Scheduled(fixedDelayString = "${rag.chat.guardrail-refresh-ms:600000}", initialDelay = 60000)
    public void refreshRules() {
        try {
            R<List<SensitiveRuleDTO>> result = platformClient.listSensitiveRules();
            if (result != null && result.isSuccess() && result.getData() != null) {
                this.sensitiveRules = result.getData();
                log.info("脱敏规则已刷新，共 {} 条", this.sensitiveRules.size());
            }
        } catch (Exception ex) {
            log.error("刷新脱敏规则失败，沿用旧规则", ex);
        }
    }

    /**
     * 校验并修正答案。
     *
     * @param rawAnswer      模型原始输出
     * @param citationCount  实际引用条数
     * @return 校验结果
     */
    public GuardrailResult check(String rawAnswer, int citationCount) {
        List<String> hitTypes = new ArrayList<>();
        List<String> reasons = new ArrayList<>();
        String answer = rawAnswer == null ? "" : rawAnswer;

        // ---------- 1. 引用完整性 ----------
        if (citationCount <= 0) {
            hitTypes.add(GuardrailType.MISSING_CITATION.name());
            reasons.add("答案未包含任何引用来源");
        } else {
            Matcher matcher = CITATION_PATTERN.matcher(answer);
            int maxRef = 0;
            while (matcher.find()) {
                maxRef = Math.max(maxRef, Integer.parseInt(matcher.group(1)));
            }
            if (maxRef > citationCount) {
                // 模型引用了不存在的编号：裁剪为最大合法编号，避免前端出现「引用了不存在的来源」
                answer = answer.replaceAll("\\[(\\d{1,2})]", m -> {
                    int n = Integer.parseInt(m.group(1));
                    return n <= citationCount ? m.group(0) : "";
                });
                hitTypes.add(GuardrailType.MISSING_CITATION.name());
                reasons.add("答案引用了不存在的来源编号，已自动裁剪");
            }
        }

        // ---------- 2. 数值无引用 ----------
        if (citationCount <= 0 && SENSITIVE_NUMERIC_PATTERN.matcher(answer).find()) {
            hitTypes.add(GuardrailType.UNSUPPORTED_NUMERIC.name());
            reasons.add("答案包含具体数值但无引用来源");
        }

        // ---------- 3. 敏感信息脱敏 ----------
        String masked = maskSensitive(answer);
        if (!masked.equals(answer)) {
            hitTypes.add(GuardrailType.SENSITIVE.name());
            reasons.add("答案包含敏感信息，已脱敏");
            answer = masked;
        }

        return new GuardrailResult(answer, hitTypes, String.join("；", reasons));
    }

    /** 脱敏：先跑平台下发的规则，再跑内置兜底规则（平台规则缺失时也不至于裸奔） */
    public String maskSensitive(String text) {
        if (text == null || text.isBlank()) {
            return text;
        }
        String result = text;

        for (SensitiveRuleDTO rule : sensitiveRules) {
            if (!"REGEX".equalsIgnoreCase(rule.getRuleType())) {
                continue;
            }
            try {
                Pattern pattern = Pattern.compile(rule.getPattern());
                result = replace(pattern, result, rule.getKeepPrefix(), rule.getKeepSuffix(),
                        rule.getMaskChar() == null ? "*" : rule.getMaskChar());
            } catch (Exception ex) {
                log.warn("脱敏规则执行失败 ruleCode={}", rule.getRuleCode(), ex);
            }
        }

        result = replace(ID_CARD_PATTERN, result, 4, 2, "*");
        result = replace(MOBILE_PATTERN, result, 3, 4, "*");
        result = replace(BANK_CARD_PATTERN, result, 4, 4, "*");
        return result;
    }

    private String replace(Pattern pattern, String text, Integer keepPrefix, Integer keepSuffix, String mask) {
        int prefix = keepPrefix == null ? 0 : keepPrefix;
        int suffix = keepSuffix == null ? 0 : keepSuffix;
        Matcher matcher = pattern.matcher(text);

        StringBuilder builder = new StringBuilder();
        while (matcher.find()) {
            String matched = matcher.group();
            int len = matched.length();
            if (prefix + suffix >= len) {
                matcher.appendReplacement(builder, Matcher.quoteReplacement(mask.repeat(len)));
                continue;
            }
            String masked = matched.substring(0, prefix)
                    + mask.repeat(len - prefix - suffix)
                    + matched.substring(len - suffix);
            matcher.appendReplacement(builder, Matcher.quoteReplacement(masked));
        }
        matcher.appendTail(builder);
        return builder.toString();
    }

    /**
     * 护栏校验结果。
     *
     * @param answer   修正后的答案
     * @param hitTypes 命中类型
     * @param reason   人类可读原因
     */
    public record GuardrailResult(String answer, List<String> hitTypes, String reason) {

        public boolean hit() {
            return !hitTypes.isEmpty();
        }

        public ChatResponse.Guardrail toGuardrail() {
            return new ChatResponse.Guardrail(hit(), hitTypes, reason == null || reason.isBlank() ? null : reason);
        }
    }
}
