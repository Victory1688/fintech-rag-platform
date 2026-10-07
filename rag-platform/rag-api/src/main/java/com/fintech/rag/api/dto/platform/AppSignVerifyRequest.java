package com.fintech.rag.api.dto.platform;

/**
 * 应用签名验签请求。
 *
 * <p>由各服务的鉴权拦截器在收到内网流量时构造并调用 rag-platform-service。</p>
 *
 * @param appId      应用 ID
 * @param method     HTTP 方法
 * @param path       请求路径（不含 query）
 * @param timestamp  毫秒时间戳
 * @param nonce      随机串
 * @param signature  调用方签名
 * @param bodySha256 请求体 SHA-256，GET 传空串
 * @param clientIp   调用方 IP，用于 IP 白名单校验
 * @author rag-platform
 */
public record AppSignVerifyRequest(String appId,
                                   String method,
                                   String path,
                                   String timestamp,
                                   String nonce,
                                   String signature,
                                   String bodySha256,
                                   String clientIp) {
}
