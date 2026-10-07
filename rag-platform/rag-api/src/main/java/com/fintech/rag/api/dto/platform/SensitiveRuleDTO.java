package com.fintech.rag.api.dto.platform;

/**
 * 敏感信息规则（供 rag-chat-service 输出侧脱敏）。
 *
 * @param ruleCode   规则编码
 * @param ruleName   规则名称
 * @param ruleType   REGEX / DICT
 * @param pattern    正则表达式或 JSON 数组词典
 * @param maskChar   掩码字符
 * @param keepPrefix 保留前缀长度
 * @param keepSuffix 保留后缀长度
 * @param action     MASK 脱敏 / BLOCK 拦截 / WARN 仅告警
 * @author rag-platform
 */
public record SensitiveRuleDTO(String ruleCode,
                               String ruleName,
                               String ruleType,
                               String pattern,
                               String maskChar,
                               Integer keepPrefix,
                               Integer keepSuffix,
                               String action) {
}
