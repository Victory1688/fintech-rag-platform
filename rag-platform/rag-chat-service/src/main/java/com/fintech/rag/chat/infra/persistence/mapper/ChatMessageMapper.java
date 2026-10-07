package com.fintech.rag.chat.infra.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.fintech.rag.chat.domain.model.ChatMessage;
import org.apache.ibatis.annotations.Mapper;

/**
 * 消息 数据访问。
 *
 * @author rag-platform
 */
@Mapper
public interface ChatMessageMapper extends BaseMapper<ChatMessage> {
}
