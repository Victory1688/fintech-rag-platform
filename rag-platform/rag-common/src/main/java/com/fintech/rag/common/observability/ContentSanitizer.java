package com.fintech.rag.common.observability;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 应用侧内容脱敏与指纹工具 —— <b>可观测上报前的最后一道人工闸门</b>。
 *
 * <p><b>为什么脱敏必须在应用侧做，而不是交给 OTel Collector？</b></p>
 * <p>Collector 的 redaction/transform processor 是<b>兜底安全网</b>，不是控制手段：
 * 一旦某个字段在应用侧被采集，它就已经离开了受控边界（进入网络、进入 exporter 队列、
 * 可能落进 exporter 的错误日志）。正确做法是在「构造上报内容」这一步就脱敏。</p>
 *
 * <p><b>与输出侧脱敏的规则一致性</b>：本类内置规则与 {@code AnswerGuardrail} 的
 * 输出脱敏规则应保持同源（理想做法是都从 {@code t_sensitive_rule} 加载）。
 * 两处规则不一致会形成「对用户脱敏了、但对 LangFuse 没脱敏」的合规漏洞。</p>
 *
 * @author rag-platform
 */
public class ContentSanitizer {

    /** 手机号（中国大陆） */
    private static final Pattern PHONE = Pattern.compile("(?<!\\d)(1[3-9]\\d{9})(?!\\d)");
    /** 18 位身份证（末位可为 X） */
    private static final Pattern ID_CARD = Pattern.compile("(?<!\\d)(\\d{17}[\\dXx])(?!\\d)");
    /** 15 位旧身份证 */
    private static final Pattern ID_CARD_15 = Pattern.compile("(?<!\\d)(\\d{15})(?!\\d)");
    /** 银行卡（16~19 位连续数字） */
    private static final Pattern BANK_CARD = Pattern.compile("(?<!\\d)(\\d{16,19})(?!\\d)");
    /** 邮箱 */
    private static final Pattern EMAIL = Pattern.compile("([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\\.[A-Za-z]{2,})");

    private final ObservabilityProperties properties;

    public ContentSanitizer(ObservabilityProperties properties) {
        this.properties = properties;
    }

    /**
     * 脱敏：保留可读性（前 3 后 2 / 域名保留），便于人工比对，但不泄露完整值。
     */
    public String mask(String text) {
        if (text == null || text.isEmpty()) {
            return text;
        }
        String masked = ID_CARD.matcher(text).replaceAll(m -> maskKeep(m.group(1), 3, 2));
        masked = ID_CARD_15.matcher(masked).replaceAll(m -> maskKeep(m.group(1), 3, 2));
        masked = PHONE.matcher(masked).replaceAll(m -> maskKeep(m.group(1), 3, 2));
        masked = BANK_CARD.matcher(masked).replaceAll(m -> maskKeep(m.group(1), 4, 2));
        masked = EMAIL.matcher(masked).replaceAll(m -> m.group(1).charAt(0) + "***@" + m.group(2));
        return masked;
    }

    /** 内容指纹（sha256 前 16 位 hex），用于「同一问题是否重复出现」而无需落原文 */
    public String fingerprint(String text) {
        if (text == null) {
            return null;
        }
        return sha256Hex(text).substring(0, 16);
    }

    /** 主体标识哈希（带盐），用于在不落 userId 的前提下做维度归因 */
    public String subjectHash(String subjectId) {
        if (subjectId == null || subjectId.isBlank()) {
            return null;
        }
        String salt = properties.getSubjectHashSalt() == null ? "" : properties.getSubjectHashSalt();
        String raw = sha256Hex(salt + "|" + subjectId);
        return raw.substring(0, 16);
    }

    /**
     * 按当前档位产出「可上报的文本」。
     *
     * @param text 原始文本（可能是 prompt / 答案 / 召回片段）
     * @return null 表示本档位不允许上报文本；否则返回已脱敏并截断的文本
     */
    public String forReporting(String text) {
        ContentLevel level = properties.effectiveContentLevel();
        if (text == null || text.isEmpty() || !level.allowsText()) {
            return null;
        }
        String prepared = level.isPlainText() ? text : mask(text);
        return truncate(prepared, properties.getMaxContentChars());
    }

    private String maskKeep(String value, int head, int tail) {
        if (value == null || value.length() <= head + tail) {
            return "***";
        }
        StringBuilder sb = new StringBuilder();
        sb.append(value, 0, head);
        sb.append("*".repeat(value.length() - head - tail));
        sb.append(value, value.length() - tail, value.length());
        return sb.toString();
    }

    private String truncate(String value, int max) {
        if (value == null || max <= 0 || value.length() <= max) {
            return value;
        }
        return value.substring(0, max) + "...[truncated]";
    }

    private String sha256Hex(String value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] bytes = digest.digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder(bytes.length * 2);
            for (byte b : bytes) {
                sb.append(Character.forDigit((b >> 4) & 0xF, 16));
                sb.append(Character.forDigit(b & 0xF, 16));
            }
            return sb.toString();
        } catch (NoSuchAlgorithmException ex) {
            // SHA-256 是 JDK 必备算法，正常不可能走到这里
            throw new IllegalStateException("SHA-256 not available", ex);
        }
    }
}
