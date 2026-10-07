package com.fintech.rag.platform.domain.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

/**
 * 敏感信息脱敏规则。
 *
 * @author rag-platform
 */
@Data
@TableName("t_sensitive_rule")
public class SensitiveRule {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private String ruleCode;

    private String ruleName;

    /** REGEX / DICT */
    private String ruleType;

    private String pattern;

    private String maskChar;

    private Integer keepPrefix;

    private Integer keepSuffix;

    /** MASK / BLOCK / WARN */
    private String action;

    private Integer status;
}
