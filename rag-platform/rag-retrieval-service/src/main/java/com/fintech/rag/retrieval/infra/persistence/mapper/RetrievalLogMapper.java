package com.fintech.rag.retrieval.infra.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.fintech.rag.retrieval.domain.model.RetrievalLog;
import org.apache.ibatis.annotations.Mapper;

/**
 * 检索日志数据访问。
 *
 * @author rag-platform
 */
@Mapper
public interface RetrievalLogMapper extends BaseMapper<RetrievalLog> {
}
