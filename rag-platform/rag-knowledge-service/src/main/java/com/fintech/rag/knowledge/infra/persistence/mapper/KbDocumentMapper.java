package com.fintech.rag.knowledge.infra.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.fintech.rag.knowledge.domain.model.KbDocument;
import org.apache.ibatis.annotations.Mapper;

/**
 * 文档 数据访问。
 *
 * @author rag-platform
 */
@Mapper
public interface KbDocumentMapper extends BaseMapper<KbDocument> {
}
