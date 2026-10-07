package com.fintech.rag.platform.domain.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.math.BigDecimal;

/**
 * 模型配置（供 LlmRouter 动态路由）。
 *
 * @author rag-platform
 */
@Data
@TableName("t_model_config")
public class ModelConfig {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private Long tenantId;

    private String configCode;

    private String provider;

    private String baseUrl;

    /** API Key 密文 */
    private String apiKeyEnc;

    private String modelName;

    private BigDecimal temperature;

    private Integer maxTokens;

    /** 可处理的最大密级：1公开 2内部 3机密 */
    private Integer sensitiveLevel;

    private Integer priority;

    private Integer isDefault;

    private Integer status;
}
