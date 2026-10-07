package com.fintech.rag.chat.app.eval;

/**
 * 在线抽样上下文 —— 从一次完成的回答里抽出的「可评估事实」。
 *
 * <p>全部字段都来自本次请求的既有产物，<b>不含问答原文</b>：
 * 评估指标应尽量建立在「结构化的链路事实」上（引用数、召回数、耗时、结果类型），
 * 这样在线评估才能在不采集任何文本内容的前提下运行 —— 这是合规友好的设计，
 * 也让评估可以在生产环境长期开启。</p>
 *
 * @param traceId        链路 ID
 * @param messageId      助手消息 ID
 * @param conversationId 会话 ID
 * @param answerType     回答类型（ANSWERED / NO_HIT / GUARDRAIL_BLOCKED / ERROR）
 * @param modelCode      模型编码
 * @param promptVersion  Prompt 版本快照
 * @param citationCount  实际引用条数
 * @param chunkCount     最终召回片段数
 * @param rawChunkCount  RAGFlow 原始召回数（用于区分「没召回到」与「召回后被过滤掉」）
 * @param topScore       最高分
 * @param ttfbMs         首字节耗时
 * @param costMs         端到端耗时
 * @author rag-platform
 */
public record EvalSampleContext(String traceId,
                                Long messageId,
                                Long conversationId,
                                String answerType,
                                String modelCode,
                                String promptVersion,
                                int citationCount,
                                int chunkCount,
                                int rawChunkCount,
                                Double topScore,
                                Integer ttfbMs,
                                int costMs) {
}
