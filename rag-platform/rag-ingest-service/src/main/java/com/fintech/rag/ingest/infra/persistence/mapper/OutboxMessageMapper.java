package com.fintech.rag.ingest.infra.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.fintech.rag.ingest.domain.model.OutboxMessage;
import org.apache.ibatis.annotations.Mapper;

/**
 * 本地消息 数据访问。
 *
 * @author rag-platform
 */
@Mapper
public interface OutboxMessageMapper extends BaseMapper<OutboxMessage> {
}
