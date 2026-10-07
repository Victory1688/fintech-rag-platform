package com.fintech.rag.common.util;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/**
 * 应用请求签名工具（HMAC-SHA256）。
 *
 * <p>签名原文（\n 分隔，顺序不可变，否则验签必然失败）：</p>
 * <pre>
 *   METHOD\nPATH\nTIMESTAMP\nNONCE\nBODY_SHA256_HEX
 * </pre>
 *
 * <p>设计要点：</p>
 * <ol>
 *   <li>把 body 的 SHA-256 摘要纳入签名，避免大 body 直接参与 HMAC 计算；</li>
 *   <li>纳入 timestamp + nonce，配合服务端 Redis 实现防重放；</li>
 *   <li>比较采用 {@link MessageDigest#isEqual} 常量时间比较，防时序攻击。</li>
 * </ol>
 *
 * @author rag-platform
 */
public final class HmacSignatures {

    private static final String ALGORITHM_HMAC = "HmacSHA256";
    private static final String ALGORITHM_SHA256 = "SHA-256";

    private HmacSignatures() {
    }

    /**
     * 计算签名。
     *
     * @param appSecret  应用密钥（服务端持密文，验签前解密）
     * @param method     HTTP 方法，如 POST
     * @param path       请求路径，不含 query，如 /internal/chat/completions
     * @param timestamp  毫秒时间戳字符串
     * @param nonce      随机串
     * @param bodySha256 请求体的 SHA-256 十六进制摘要；GET 无 body 传空字符串
     * @return 小写十六进制签名
     */
    public static String sign(String appSecret, String method, String path,
                              String timestamp, String nonce, String bodySha256) {
        String payload = String.join("\n",
                upper(method),
                emptyIfNull(path),
                emptyIfNull(timestamp),
                emptyIfNull(nonce),
                emptyIfNull(bodySha256));
        return hmacSha256Hex(appSecret, payload);
    }

    /** 验签 */
    public static boolean verify(String appSecret, String method, String path,
                                 String timestamp, String nonce, String bodySha256, String signature) {
        if (signature == null || signature.isBlank()) {
            return false;
        }
        String expected = sign(appSecret, method, path, timestamp, nonce, bodySha256);
        return constantTimeEquals(expected, signature);
    }

    /** SHA-256 十六进制摘要 */
    public static String sha256Hex(String content) {
        if (content == null) {
            return "";
        }
        try {
            MessageDigest digest = MessageDigest.getInstance(ALGORITHM_SHA256);
            return toHex(digest.digest(content.getBytes(StandardCharsets.UTF_8)));
        } catch (Exception ex) {
            throw new IllegalStateException("SHA-256 计算失败", ex);
        }
    }

    /** HMAC-SHA256 十六进制 */
    public static String hmacSha256Hex(String secret, String payload) {
        try {
            Mac mac = Mac.getInstance(ALGORITHM_HMAC);
            mac.init(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), ALGORITHM_HMAC));
            return toHex(mac.doFinal(payload.getBytes(StandardCharsets.UTF_8)));
        } catch (Exception ex) {
            throw new IllegalStateException("HMAC-SHA256 计算失败", ex);
        }
    }

    /** 常量时间比较，避免通过响应时间差逐字节爆破签名 */
    public static boolean constantTimeEquals(String a, String b) {
        if (a == null || b == null) {
            return false;
        }
        return MessageDigest.isEqual(
                a.getBytes(StandardCharsets.UTF_8),
                b.getBytes(StandardCharsets.UTF_8));
    }

    private static String toHex(byte[] bytes) {
        StringBuilder sb = new StringBuilder(bytes.length * 2);
        for (byte b : bytes) {
            sb.append(Character.forDigit((b >> 4) & 0xF, 16));
            sb.append(Character.forDigit(b & 0xF, 16));
        }
        return sb.toString();
    }

    private static String upper(String s) {
        return s == null ? "" : s.toUpperCase();
    }

    private static String emptyIfNull(String s) {
        return s == null ? "" : s;
    }
}
