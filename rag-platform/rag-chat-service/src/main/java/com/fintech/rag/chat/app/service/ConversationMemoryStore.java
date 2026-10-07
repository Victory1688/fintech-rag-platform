package com.fintech.rag.chat.app.service;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.fintech.rag.chat.domain.model.ChatMessage;
import com.fintech.rag.chat.infra.persistence.mapper.ChatMessageMapper;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;

/**
 * 会话记忆存储。
 *
 * <p>骨架使用「按会话查询最近 N 条消息」的简易实现。
 * 落地时建议改为 Redis 存窗口 + 数据库存全量：
 * 前者保证多轮对话低延迟，后者保证审计可追溯（金融场景必须全量留存）。</p>
 *
 * @author rag-platform
 */
@Service
public class ConversationMemoryStore {

    /** 参与 Prompt 的历史轮数上限，过多会稀释检索上下文并推高 token 成本 */
    private static final int MAX_HISTORY_MESSAGES = 6;

    private final ChatMessageMapper messageMapper;

    public ConversationMemoryStore(ChatMessageMapper messageMapper) {
        this.messageMapper = messageMapper;
    }

    /** 读取最近若干条消息（时间正序） */
    public List<ChatMessage> recent(Long conversationId) {
        if (conversationId == null) {
            return List.of();
        }
        List<ChatMessage> messages = messageMapper.selectList(Wrappers.<ChatMessage>lambdaQuery()
                .eq(ChatMessage::getConversationId, conversationId)
                .orderByDesc(ChatMessage::getCreateTime)
                .last("limit " + MAX_HISTORY_MESSAGES));
        List<ChatMessage> ordered = new ArrayList<>(messages);
        java.util.Collections.reverse(ordered);
        return ordered;
    }
}
