package com.fintech.rag.common.util;

import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Base64;

/**
 * AES-256-GCM 加解密工具，用于 AppSecret、模型 API Key 等敏感字段落库加密。
 *
 * <p>选 GCM 而非 CBC 的原因：GCM 自带完整性校验，密文被篡改会解密失败，
 * 而 CBC 需要额外做 HMAC，容易漏做。</p>
 *
 * <p>输出格式：{@code Base64(IV(12B) || CIPHERTEXT || TAG)}</p>
 *
 * @author rag-platform
 */
public final class AesCiphers {

    private static final String ALGORITHM = "AES";
    private static final String TRANSFORMATION = "AES/GCM/NoPadding";
    private static final int IV_LENGTH = 12;
    private static final int TAG_BITS = 128;

    private static final SecureRandom RANDOM = new SecureRandom();

    private AesCiphers() {
    }

    /** 加密；salt 为 32 字节密钥（建议由 KMS/环境变量提供，禁止入库） */
    public static String encrypt(String plainText, String keyBase64) {
        try {
            byte[] iv = new byte[IV_LENGTH];
            RANDOM.nextBytes(iv);
            Cipher cipher = Cipher.getInstance(TRANSFORMATION);
            cipher.init(Cipher.ENCRYPT_MODE, toKey(keyBase64), new GCMParameterSpec(TAG_BITS, iv));
            byte[] cipherText = cipher.doFinal(plainText.getBytes(StandardCharsets.UTF_8));

            byte[] result = new byte[iv.length + cipherText.length];
            System.arraycopy(iv, 0, result, 0, iv.length);
            System.arraycopy(cipherText, 0, result, iv.length, cipherText.length);
            return Base64.getEncoder().encodeToString(result);
        } catch (Exception ex) {
            throw new IllegalStateException("AES 加密失败", ex);
        }
    }

    /** 解密 */
    public static String decrypt(String cipherBase64, String keyBase64) {
        try {
            byte[] all = Base64.getDecoder().decode(cipherBase64);
            byte[] iv = new byte[IV_LENGTH];
            System.arraycopy(all, 0, iv, 0, IV_LENGTH);
            byte[] cipherText = new byte[all.length - IV_LENGTH];
            System.arraycopy(all, IV_LENGTH, cipherText, 0, cipherText.length);

            Cipher cipher = Cipher.getInstance(TRANSFORMATION);
            cipher.init(Cipher.DECRYPT_MODE, toKey(keyBase64), new GCMParameterSpec(TAG_BITS, iv));
            return new String(cipher.doFinal(cipherText), StandardCharsets.UTF_8);
        } catch (Exception ex) {
            throw new IllegalStateException("AES 解密失败（密钥错误或密文被篡改）", ex);
        }
    }

    private static SecretKeySpec toKey(String keyBase64) {
        byte[] key = Base64.getDecoder().decode(keyBase64);
        if (key.length != 32) {
            throw new IllegalArgumentException("AES-256 密钥必须为 32 字节（Base64 编码后 44 字符）");
        }
        return new SecretKeySpec(key, ALGORITHM);
    }
}
