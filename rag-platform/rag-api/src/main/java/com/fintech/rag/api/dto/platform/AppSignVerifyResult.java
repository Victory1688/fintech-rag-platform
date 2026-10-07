package com.fintech.rag.api.dto.platform;

/**
 * 应用签名验签结果。
 *
 * @param valid       是否通过
 * @param reason      失败原因
 * @param appId       应用 ID
 * @param appName     应用名称
 * @param qpsLimit    QPS 上限
 * @param dailyLimit  日调用量上限
 * @param ipWhitelist IP 白名单（逗号分隔）
 * @author rag-platform
 */
public record AppSignVerifyResult(boolean valid,
                                  String reason,
                                  String appId,
                                  String appName,
                                  Integer qpsLimit,
                                  Long dailyLimit,
                                  String ipWhitelist) {

    public static AppSignVerifyResult rejected(String reason) {
        return new AppSignVerifyResult(false, reason, null, null, null, null, null);
    }
}
