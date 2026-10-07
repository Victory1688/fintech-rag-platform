package com.fintech.rag.platform.infra.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.fintech.rag.platform.domain.model.AuditLog;
import org.apache.ibatis.annotations.Mapper;

/**
 * AuditLog 数据访问。
 *
 * @author rag-platform
 */
@Mapper
public interface AuditLogMapper extends BaseMapper<AuditLog> {
}
