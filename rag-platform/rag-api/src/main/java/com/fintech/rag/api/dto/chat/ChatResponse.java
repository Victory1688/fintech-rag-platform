package com.fintech.rag.api.dto.chat;

import com.fintech.rag.api.dto.common.AnswerType;

import java.util.List;

/**
 * 问答响应契约。
 *
 * @param messageId      消息 ID
 * @param conversationId 会话 ID
 * @param answerType     答案类型，见 {@link AnswerType}
 * @param answer         答案正文，引用以 [1] [2] 形式内联
 * @param citations      引用列表，与正文 [n] 一一对应
 * @param guardrail      护栏命中情况
 * @param modelCode      实际使用的模型配置编码（便于问题定位与成本归因）
 * @param usage          token 用量
 * @param ttfbMs         首字节耗时
 * @param costMs         端到端耗时
 * @param disclaimer     免责声明
 * @author rag-platform
 */
public record ChatResponse(String messageId,
                           String conversationId,
                           AnswerType answerType,
                           String answer,
                           List<Citation> citations,
                           Guardrail guardrail,
                           String modelCode,
                           Usage usage,
                           int ttfbMs,
                           int costMs,
                           String disclaimer) {

    /**
     * 引用条目。
     *
     * @param seq        序号，对应正文中的 [seq]
     * @param kbId       知识库 ID
     * @param docId      文档 ID
     * @param docName    文档名
     * @param versionNo  版本号
     * @param pageNo     页码
     * @param chunkIndex 片段序号
     * @param score      相关度得分
     * @param content    引用原文片段
     */
    public record Citation(int seq,
                           Long kbId,
                           Long docId,
                           String docName,
                           Integer versionNo,
                           Integer pageNo,
                           Integer chunkIndex,
                           Double score,
                           String content) {
    }

    /**
     * 护栏结果。
     *
     * @param hit    是否命中
     * @param types  命中类型列表，取值见 GuardrailType 名称
     * @param reason 人类可读原因，便于前端提示与日志排查
     */
    public record Guardrail(boolean hit, List<String> types, String reason) {

        public static Guardrail pass() {
            return new Guardrail(false, List.of(), null);
        }
    }

    /**
     * token 用量。
     *
     * @param inputTokens  输入 token
     * @param outputTokens 输出 token
     * @param totalTokens  合计
     */
    public record Usage(int inputTokens, int outputTokens, int totalTokens) {

        public static Usage zero() {
            return new Usage(0, 0, 0);
        }
    }
}
