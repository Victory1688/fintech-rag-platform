package com.fintech.rag.api.dto.platform;

/**
 * 模型配置（供 rag-chat-service 做动态路由）。
 *
 * <p><strong>安全提醒：</strong>{@code apiKey} 通过 HTTP 在可信内网传输是过渡方案。
 * 生产环境建议改为「Nacos 加密配置下发 + 本地解密」，本接口只回传 configCode 与模型名，
 * 避免模型密钥在经过多个服务的内存与日志时被意外落盘。</p>
 *
 * @param configCode     配置编码，如 PRIMARY_CLOUD / SENSITIVE_PRIVATE
 * @param provider       deepseek / qwen / openai-compatible / vllm
 * @param baseUrl        API 地址
 * @param apiKey         密钥
 * @param modelName      模型名
 * @param temperature    默认温度
 * @param maxTokens      默认最大输出 token
 * @param sensitiveLevel 可处理的最大密级
 * @param priority       路由优先级，越小越优先
 * @param isDefault      是否默认配置
 * @author rag-platform
 */
public record ModelConfigDTO(String configCode,
                             String provider,
                             String baseUrl,
                             String apiKey,
                             String modelName,
                             Double temperature,
                             Integer maxTokens,
                             Integer sensitiveLevel,
                             Integer priority,
                             Boolean isDefault) {
}
