package com.fintech.rag.platform.infra.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.fintech.rag.platform.domain.model.ModelConfig;
import org.apache.ibatis.annotations.Mapper;

/**
 * ModelConfig 数据访问。
 *
 * @author rag-platform
 */
@Mapper
public interface ModelConfigMapper extends BaseMapper<ModelConfig> {
}
