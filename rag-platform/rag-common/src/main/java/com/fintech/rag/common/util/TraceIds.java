package com.fintech.rag.common.util;

import java.util.Locale;
import java.util.concurrent.ThreadLocalRandom;
import java.util.regex.Pattern;

/**
 * W3C Trace Context 工具 —— <b>全链路追踪 ID 的唯一真源</b>。
 *
 * <p><b>为什么必须是 32 位小写十六进制？</b></p>
 * <p>OpenTelemetry / OTel Collector / LangFuse / Tempo 全部按 W3C Trace Context 规范解析
 * trace-id（32 位十六进制）与 span-id（16 位十六进制），透传头是标准 {@code traceparent}：
 * {@code 00-{trace-id}-{span-id}-{trace-flags}}。</p>
 * <p>若自造格式（例如加前缀、混入非十六进制字符），则：</p>
 * <ol>
 *   <li>OTel SDK 无法把它当作父上下文，会另起一条新链路；</li>
 *   <li>LangFuse 与 APM 里的 traceId 对不上，跨系统关联 100% 失败；</li>
 *   <li>问题表现是「日志里有 traceId，但链路里查不到」，非常难排查。</li>
 * </ol>
 *
 * @author rag-platform
 */
public final class TraceIds {

    /** W3C 标准透传头 */
    public static final String TRACEPARENT = "traceparent";

    private static final char[] HEX = "0123456789abcdef".toCharArray();
    private static final int TRACE_ID_LENGTH = 32;
    private static final int SPAN_ID_LENGTH = 16;
    private static final String ZERO_TRACE_ID = "00000000000000000000000000000000";
    private static final String ZERO_SPAN_ID = "0000000000000000";
    private static final String TRACE_FLAG_SAMPLED = "01";
    private static final String TRACE_FLAG_NOT_SAMPLED = "00";

    /** 00-<32hex>-<16hex>-<2hex>，版本位允许 00~fe（ff 非法） */
    private static final Pattern TRACEPARENT_PATTERN = Pattern.compile(
            "^(?!ff)[0-9a-f]{2}-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$");
    private static final Pattern TRACE_ID_PATTERN = Pattern.compile("^[0-9a-f]{32}$");

    private TraceIds() {
    }

    /** 生成一个新的合规 traceId（32 位小写十六进制，且不为全零） */
    public static String newTraceId() {
        byte[] bytes = new byte[16];
        while (true) {
            ThreadLocalRandom.current().nextBytes(bytes);
            String candidate = toHex(bytes);
            if (!ZERO_TRACE_ID.equals(candidate)) {
                return candidate;
            }
        }
    }

    /** 生成一个新的合规 spanId（16 位小写十六进制，且不为全零） */
    public static String newSpanId() {
        byte[] bytes = new byte[8];
        while (true) {
            ThreadLocalRandom.current().nextBytes(bytes);
            String candidate = toHex(bytes);
            if (!ZERO_SPAN_ID.equals(candidate)) {
                return candidate;
            }
        }
    }

    /** 是否为合规 traceId */
    public static boolean isValidTraceId(String traceId) {
        return traceId != null
                && traceId.length() == TRACE_ID_LENGTH
                && !ZERO_TRACE_ID.equals(traceId)
                && TRACE_ID_PATTERN.matcher(traceId).matches();
    }

    /**
     * 沿用上游 traceId，非法或缺失则新建。
     *
     * <p>注意：这里做的是「格式校验」而非「信任」——是否接受上游传入值，
     * 由调用方决定（网关侧会把客户端传入的 traceparent 整体洗掉）。</p>
     */
    public static String resolve(String traceId) {
        String normalized = normalize(traceId);
        return normalized == null ? newTraceId() : normalized;
    }

    /** 规范化：允许大小写混写，统一为小写；非法返回 null */
    public static String normalize(String traceId) {
        if (traceId == null) {
            return null;
        }
        String candidate = traceId.trim().toLowerCase(Locale.ROOT);
        return isValidTraceId(candidate) ? candidate : null;
    }

    /** 从 traceparent 解析 traceId，非法返回 null */
    public static String parseTraceId(String traceparent) {
        String[] parts = splitTraceparent(traceparent);
        return parts == null ? null : parts[1];
    }

    /** 从 traceparent 解析 spanId，非法返回 null */
    public static String parseSpanId(String traceparent) {
        String[] parts = splitTraceparent(traceparent);
        return parts == null ? null : parts[2];
    }

    /** 上游是否已采样（trace-flags 最低位为 1） */
    public static boolean isSampled(String traceparent) {
        String[] parts = splitTraceparent(traceparent);
        if (parts == null) {
            return false;
        }
        return (Integer.parseInt(parts[3], 16) & 0x01) == 1;
    }

    /**
     * 组装 traceparent。
     *
     * @param traceId 32 位 hex
     * @param spanId  16 位 hex
     * @param sampled 是否采样
     */
    public static String formatTraceparent(String traceId, String spanId, boolean sampled) {
        String safeTraceId = isValidTraceId(traceId) ? traceId : newTraceId();
        String safeSpanId = isHex(spanId, SPAN_ID_LENGTH) ? spanId : newSpanId();
        return "00-" + safeTraceId + "-" + safeSpanId + "-"
                + (sampled ? TRACE_FLAG_SAMPLED : TRACE_FLAG_NOT_SAMPLED);
    }

    /**
     * 只带 traceId 的 traceparent（spanId 由本方法生成一个合规随机值）。
     *
     * <p>用途：网关生成 traceparent 透传给下游时，网关自己的 spanId 对下游无意义，
     * 下游的 OTel SDK 会以「父上下文」方式提取 traceId 并生成自己的 spanId。</p>
     *
     * <p><b>不要传全零 spanId</b>：W3C 规范明确「span-id 全零」的 traceparent 属于非法值，
     * OTel / Collector / LangFuse 会直接丢弃并另起新链路 —— 这正是「网关发了头下游却不认」的根因。
     * 本方法内部会把它替换为一个合规随机 spanId。</p>
     */
    public static String formatTraceparent(String traceId, boolean sampled) {
        return formatTraceparent(traceId, ZERO_SPAN_ID, sampled);
    }

    /** 是否形如合法 traceparent */
    public static boolean isValidTraceparent(String traceparent) {
        return splitTraceparent(traceparent) != null;
    }

    private static String[] splitTraceparent(String traceparent) {
        if (traceparent == null) {
            return null;
        }
        String candidate = traceparent.trim().toLowerCase(Locale.ROOT);
        if (!TRACEPARENT_PATTERN.matcher(candidate).matches()) {
            return null;
        }
        String[] parts = candidate.split("-");
        if (ZERO_TRACE_ID.equals(parts[1]) || ZERO_SPAN_ID.equals(parts[2])) {
            return null;
        }
        return parts;
    }

    private static boolean isHex(String value, int length) {
        if (value == null || value.length() != length || ZERO_SPAN_ID.equals(value)) {
            return false;
        }
        for (int i = 0; i < value.length(); i++) {
            if (Character.digit(value.charAt(i), 16) < 0) {
                return false;
            }
        }
        return true;
    }

    private static String toHex(byte[] bytes) {
        char[] chars = new char[bytes.length * 2];
        for (int i = 0; i < bytes.length; i++) {
            int v = bytes[i] & 0xFF;
            chars[i * 2] = HEX[v >>> 4];
            chars[i * 2 + 1] = HEX[v & 0x0F];
        }
        return new String(chars);
    }

    /** 供日志/看板使用的短格式（前 8 位） */
    public static String shortId(String traceId) {
        return traceId == null || traceId.length() <= 8 ? String.valueOf(traceId) : traceId.substring(0, 8);
    }
}
