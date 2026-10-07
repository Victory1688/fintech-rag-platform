package com.fintech.rag.chat.app.persist;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.fintech.rag.api.dto.retrieval.RetrievalResponse;
import com.fintech.rag.chat.domain.model.ChatMessage;
import com.fintech.rag.chat.domain.model.Conversation;
import com.fintech.rag.chat.domain.model.MessageCitation;
import com.fintech.rag.chat.domain.model.TokenUsageRecord;
import com.fintech.rag.chat.infra.persistence.mapper.ChatMessageMapper;
import com.fintech.rag.chat.infra.persistence.mapper.ConversationMapper;
import com.fintech.rag.chat.infra.persistence.mapper.MessageCitationMapper;
import com.fintech.rag.chat.infra.persistence.mapper.TokenUsageRecordMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

/**
 * 问答落库编排 —— <b>「一次回答」全部持久化动作的唯一出口</b>。
 *
 * <p><b>为什么要独立成类，而不是散在编排服务里</b>：落库涉及 4 张表 + 1 次会话计数更新，
 * 散在编排里会让「生成逻辑」与「存储逻辑」互相缠绕；更要紧的是
 * <b>落库失败的处理策略必须统一</b> —— 每个方法都吞异常并记 ERROR，
 * 因为「用户已经看到回答了，此时因为写库失败而报错」是纯粹的体验灾难。</p>
 *
 * <p><b>事务边界</b>：本类<b>刻意不加 {@code @Transactional}</b>。原因：
 * 这些写入都发生在模型调用<b>之后</b>（模型调用不可回滚），把它们包进事务只会
 * 延长连接持有时间、放大锁竞争，却换不来任何原子性收益。
 * 真正的原子性诉求（如「消息 + 引用」必须同时成功）应通过
 * 「先写消息，再写引用，引用失败只记 ERROR 不抛」来降级处理 ——
 * 引用缺失只会让回放少一段，而回滚消息会让用户看到「答案凭空消失」。</p>
 *
 * @author rag-platform
 */
@Service
public class ChatPersistenceService {

    private static final Logger log = LoggerFactory.getLogger(ChatPersistenceService.class);

    private static final long DEFAULT_TENANT_ID = 0L;

    private final ConversationMapper conversationMapper;
    private final ChatMessageMapper messageMapper;
    private final MessageCitationMapper citationMapper;
    private final TokenUsageRecordMapper tokenUsageMapper;

    public ChatPersistenceService(ConversationMapper conversationMapper,
                                  ChatMessageMapper messageMapper,
                                  MessageCitationMapper citationMapper,
                                  TokenUsageRecordMapper tokenUsageMapper) {
        this.conversationMapper = conversationMapper;
        this.messageMapper = messageMapper;
        this.citationMapper = citationMapper;
        this.tokenUsageMapper = tokenUsageMapper;
    }

    // ------------------------------------------------------------------ 会话
    /**
     * 确保会话存在（首问自动建会话），返回会话 ID。
     *
     * <p>返回 null 表示会话既未提供也无法创建；此时上层仍应继续作答，
     * 只是这条回答不会被归入任何会话（回放时只能按 traceId 查，查不到会话）——
     * 这比直接报错好，但必须告警。</p>
     */
    public Long ensureConversation(String rawConversationId, String subjectType, String subjectId,
                                   String question, List<Long> kbIds) {
        Long conversationId = parseLongQuietly(rawConversationId);
        if (conversationId != null) {
            return conversationId;
        }
        try {
            Conversation conversation = new Conversation();
            conversation.setTenantId(DEFAULT_TENANT_ID);
            conversation.setConversationNo("C" + UUID.randomUUID().toString().replace("-", ""));
            conversation.setTitle(titleOf(question));
            conversation.setSubjectType(subjectType);
            conversation.setSubjectId(subjectId);
            conversation.setKbScope(kbIds == null ? null : kbIds.toString());
            conversation.setMessageCount(0);
            conversation.setTotalTokens(0L);
            conversation.setStatus(1);
            conversation.setDeleted(0);
            conversationMapper.insert(conversation);
            return conversation.getId();
        } catch (Exception ex) {
            log.error("创建会话失败 subjectType={} subjectId={}（本次回答将不归属任何会话）",
                    subjectType, subjectId, ex);
            return null;
        }
    }

    /** 会话计数累加：消息数 + token。用于会话列表展示与「本会话花了多少 token」归因 */
    public void accumulateConversation(Long conversationId, int messageDelta, long tokenDelta) {
        if (conversationId == null || (messageDelta == 0 && tokenDelta == 0)) {
            return;
        }
        try {
            conversationMapper.update(null, Wrappers.<Conversation>lambdaUpdate()
                    .eq(Conversation::getId, conversationId)
                    .setSql("message_count = message_count + " + messageDelta)
                    .setSql("total_tokens = total_tokens + " + tokenDelta)
                    .set(Conversation::getUpdateTime, LocalDateTime.now()));
        } catch (Exception ex) {
            log.error("更新会话计数失败 conversationId={}", conversationId, ex);
        }
    }

    // ------------------------------------------------------------------ 消息
    /** 写入用户消息，返回消息 ID（作为助手消息的 parent_id） */
    public Long saveUserMessage(Long conversationId, String question) {
        try {
            ChatMessage message = new ChatMessage();
            message.setTenantId(DEFAULT_TENANT_ID);
            message.setConversationId(conversationId);
            message.setMessageNo(nextMessageNo());
            message.setRole("USER");
            message.setContent(question);
            message.setTraceId(com.fintech.rag.common.context.RequestContext.currentTraceId());
            message.setDeleted(0);
            messageMapper.insert(message);
            return message.getId();
        } catch (Exception ex) {
            log.error("保存用户消息失败 conversationId={}", conversationId, ex);
            return null;
        }
    }

    /**
     * 写入助手消息，返回消息 ID。
     *
     * @param parentId       上一条消息（用户消息）ID，构成对话树，回放时才能成对展示
     * @param traceId        本次回答的 W3C traceId。<b>必须来自服务端链路</b>，
     *                       这是「按 traceId 一键回放」的唯一钥匙
     * @param contentTokens  输出 token 数（可空，来自模型返回的真实用量）
     */
    public Long saveAssistantMessage(Long conversationId, Long parentId, String answer,
                                     String answerType, String modelCode, String traceId,
                                     String promptVersion, String guardrailHit,
                                     Integer ttfbMs, int costMs, Integer contentTokens) {
        try {
            ChatMessage message = new ChatMessage();
            message.setTenantId(DEFAULT_TENANT_ID);
            message.setConversationId(conversationId);
            message.setParentId(parentId);
            message.setMessageNo(nextMessageNo());
            message.setRole("ASSISTANT");
            message.setContent(answer == null ? "" : answer);
            message.setAnswerType(answerType);
            message.setModelCode(modelCode);
            message.setPromptVersion(promptVersion);
            message.setTraceId(traceId);
            message.setGuardrailHit(guardrailHit);
            message.setTtfbMs(ttfbMs);
            message.setCostMs(costMs);
            message.setContentTokens(contentTokens);
            message.setDeleted(0);
            messageMapper.insert(message);
            return message.getId();
        } catch (Exception ex) {
            log.error("保存助手消息失败 conversationId={} answerType={}", conversationId, answerType, ex);
            return null;
        }
    }

    // ------------------------------------------------------------------ 引用
    /**
     * 写入引用列表。
     *
     * <p><b>只在用户消息为 ASSISTANT 且确实召回到片段时才写</b>；
     * 空召回（NO_HIT）不会有引用，这是正确行为而非缺数据 ——
     * 回放时看到「NO_HIT 且零引用」应立刻明白链路是干净的。</p>
     *
     * @return 实际写入条数（-1 表示失败），用于反馈给 span 做自检
     */
    public int saveCitations(Long messageId, List<RetrievalResponse.Chunk> chunks) {
        if (messageId == null || chunks == null || chunks.isEmpty()) {
            return 0;
        }
        int seq = 0;
        int ok = 0;
        for (RetrievalResponse.Chunk chunk : chunks) {
            seq++;
            try {
                MessageCitation citation = new MessageCitation();
                citation.setMessageId(messageId);
                citation.setSeq(seq);
                citation.setKbId(chunk.kbId());
                citation.setDocId(chunk.docId());
                citation.setDocName(chunk.docName());
                citation.setVersionNo(chunk.versionNo() == null ? 1 : chunk.versionNo());
                citation.setRagflowChunkId(chunk.chunkId());
                citation.setChunkIndex(chunk.chunkIndex());
                citation.setContent(chunk.content());
                citation.setScore(chunk.score() == null ? null : BigDecimal.valueOf(chunk.score()));
                citation.setPageNo(chunk.pageNo());
                citationMapper.insert(citation);
                ok++;
            } catch (Exception ex) {
                log.error("写入引用失败 messageId={} seq={}（不影响回答展示）", messageId, seq, ex);
            }
        }
        return ok;
    }

    // ------------------------------------------------------------------ Token 计量
    /**
     * 写入 token 计量流水。
     *
     * <p><b>为什么这张表不能省</b>：Prometheus 里的 token 指标是观测聚合量，
     * 重启与采样会丢细节；本表是<b>计费账本</b>，要求逐笔可重算 ——
     * 「这个部门上个月花了多少 token」必须能精确回答，不能靠估算。</p>
     */
    public void saveTokenUsage(String traceId, String subjectType, String subjectId,
                               Long conversationId, Long messageId,
                               String modelCode, String modelName,
                               Integer inputTokens, Integer outputTokens, Integer costMs) {
        try {
            int in = inputTokens == null ? 0 : inputTokens;
            int out = outputTokens == null ? 0 : outputTokens;
            TokenUsageRecord record = new TokenUsageRecord();
            record.setTenantId(DEFAULT_TENANT_ID);
            record.setTraceId(traceId);
            record.setSubjectType(subjectType);
            record.setSubjectId(subjectId);
            record.setConversationId(conversationId);
            record.setMessageId(messageId);
            record.setModelCode(modelCode == null ? "UNKNOWN" : modelCode);
            record.setModelName(modelName == null ? "unknown" : modelName);
            record.setInputTokens(in);
            record.setOutputTokens(out);
            record.setTotalTokens(in + out);
            record.setCostMs(costMs);
            record.setBizDate(LocalDate.now());
            tokenUsageMapper.insert(record);
        } catch (Exception ex) {
            log.error("写入 token 计量失败 traceId={} modelCode={}", traceId, modelCode, ex);
        }
    }

    // ------------------------------------------------------------------ 工具
    private String nextMessageNo() {
        return "M" + UUID.randomUUID().toString().replace("-", "");
    }

    /** 会话标题取首问前 50 字：过长会撑爆列表布局，且首问通常已足够概括主题 */
    private String titleOf(String question) {
        if (question == null) {
            return null;
        }
        String trimmed = question.strip();
        return trimmed.length() <= 50 ? trimmed : trimmed.substring(0, 50);
    }

    private Long parseLongQuietly(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        try {
            return Long.parseLong(value);
        } catch (NumberFormatException ex) {
            return null;
        }
    }
}
