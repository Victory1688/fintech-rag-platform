package com.fintech.rag.chat.infra.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.fintech.rag.chat.domain.model.Conversation;
import org.apache.ibatis.annotations.Mapper;

/**
 * 会话 数据访问。
 *
 * @author rag-platform
 */
@Mapper
public interface ConversationMapper extends BaseMapper<Conversation> {
}
