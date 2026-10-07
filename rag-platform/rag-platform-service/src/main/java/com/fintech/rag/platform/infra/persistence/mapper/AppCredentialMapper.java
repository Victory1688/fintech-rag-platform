package com.fintech.rag.platform.infra.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.fintech.rag.platform.domain.model.AppCredential;
import org.apache.ibatis.annotations.Mapper;

/**
 * AppCredential 数据访问。
 *
 * @author rag-platform
 */
@Mapper
public interface AppCredentialMapper extends BaseMapper<AppCredential> {
}
