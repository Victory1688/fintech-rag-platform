package com.fintech.rag.knowledge.infra.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.fintech.rag.knowledge.domain.model.KnowledgeBase;
import org.apache.ibatis.annotations.Mapper;

/**
 * 知识库 数据访问。
 *
 * @author rag-platform
 */
@Mapper
public interface KnowledgeBaseMapper extends BaseMapper<KnowledgeBase> {
}
