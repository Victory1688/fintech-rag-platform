package com.fintech.rag.platform.infra.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.fintech.rag.platform.domain.model.SensitiveRule;
import org.apache.ibatis.annotations.Mapper;

/**
 * SensitiveRule 数据访问。
 *
 * @author rag-platform
 */
@Mapper
public interface SensitiveRuleMapper extends BaseMapper<SensitiveRule> {
}
