package com.fintech.rag.platform.api.controller;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.fintech.rag.api.dto.platform.ModelConfigDTO;
import com.fintech.rag.api.dto.platform.SensitiveRuleDTO;
import com.fintech.rag.common.core.R;
import com.fintech.rag.common.util.AesCiphers;
import com.fintech.rag.platform.config.PlatformSecurityProperties;
import com.fintech.rag.platform.domain.model.ModelConfig;
import com.fintech.rag.platform.domain.model.SensitiveRule;
import com.fintech.rag.platform.infra.persistence.mapper.ModelConfigMapper;
import com.fintech.rag.platform.infra.persistence.mapper.SensitiveRuleMapper;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 配置类接口：模型配置与脱敏规则。
 *
 * <p>这两个配置是 rag-chat-service 的「运行时依赖」，必须本地缓存 + 定时刷新，
 * 不能每次问答都远程调用。</p>
 *
 * @author rag-platform
 */
@RestController
@RequestMapping("/api/platform")
public class ConfigController {

    private final ModelConfigMapper modelConfigMapper;
    private final SensitiveRuleMapper sensitiveRuleMapper;
    private final PlatformSecurityProperties securityProperties;

    public ConfigController(ModelConfigMapper modelConfigMapper,
                            SensitiveRuleMapper sensitiveRuleMapper,
                            PlatformSecurityProperties securityProperties) {
        this.modelConfigMapper = modelConfigMapper;
        this.sensitiveRuleMapper = sensitiveRuleMapper;
        this.securityProperties = securityProperties;
    }

    /**
     * 模型配置列表（按优先级升序，供 LlmRouter 做敏感度分流）。
     */
    @GetMapping("/model-configs")
    public R<List<ModelConfigDTO>> listModelConfigs() {
        List<ModelConfig> configs = modelConfigMapper.selectList(
                Wrappers.<ModelConfig>lambdaQuery()
                        .eq(ModelConfig::getStatus, 1)
                        .orderByAsc(ModelConfig::getPriority));

        List<ModelConfigDTO> result = configs.stream().map(c -> new ModelConfigDTO(
                c.getConfigCode(),
                c.getProvider(),
                c.getBaseUrl(),
                decryptQuietly(c.getApiKeyEnc()),
                c.getModelName(),
                c.getTemperature() == null ? null : c.getTemperature().doubleValue(),
                c.getMaxTokens(),
                c.getSensitiveLevel(),
                c.getPriority(),
                c.getIsDefault() != null && c.getIsDefault() == 1
        )).toList();
        return R.ok(result);
    }

    /** 脱敏规则列表 */
    @GetMapping("/sensitive-rules")
    public R<List<SensitiveRuleDTO>> listSensitiveRules() {
        List<SensitiveRule> rules = sensitiveRuleMapper.selectList(
                Wrappers.<SensitiveRule>lambdaQuery().eq(SensitiveRule::getStatus, 1));

        List<SensitiveRuleDTO> result = rules.stream().map(r -> new SensitiveRuleDTO(
                r.getRuleCode(), r.getRuleName(), r.getRuleType(), r.getPattern(),
                r.getMaskChar(), r.getKeepPrefix(), r.getKeepSuffix(), r.getAction()
        )).toList();
        return R.ok(result);
    }

    private String decryptQuietly(String cipher) {
        if (cipher == null || cipher.isBlank()) {
            return null;
        }
        try {
            return AesCiphers.decrypt(cipher, securityProperties.getAesKey());
        } catch (Exception ex) {
            // 单条配置解密失败不应导致整个列表接口 500
            return null;
        }
    }
}
