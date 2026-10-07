package com.fintech.rag.ingest.infra.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.fintech.rag.ingest.domain.model.IngestTask;
import org.apache.ibatis.annotations.Mapper;

/**
 * 入库任务 数据访问。
 *
 * @author rag-platform
 */
@Mapper
public interface IngestTaskMapper extends BaseMapper<IngestTask> {
}
