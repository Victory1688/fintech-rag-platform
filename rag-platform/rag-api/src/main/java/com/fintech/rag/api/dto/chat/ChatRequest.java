package com.fintech.rag.api.dto.chat;

import jakarta.validation.constraints.NotBlank;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

/**
 * 问答请求契约。
 *
 * @param conversationId 会话 ID，空则新建会话
 * @param question       用户问题
 * @param kbIds          本次检索的知识库范围（仅意图，非授权依据）
 * @param kbScopeMode    ALL 全部授权 / SELECTED 指定范围
 * @param stream         是否流式。注意：协议层决定（SSE 走 /chat/stream），本字段仅作冗余标记
 * @param bizContext     业务上下文，如 {"channel":"小微","productCode":"P10086"}
 * @param options        生成参数
 * @param withToolCall   是否允许调用业务工具（Function Calling）
 * @author rag-platform
 */
public record ChatRequest(String conversationId,
                          @NotBlank(message = "问题不能为空") String question,
                          List<Long> kbIds,
                          String kbScopeMode,
                          Boolean stream,
                          Map<String, Object> bizContext,
                          Options options,
                          Boolean withToolCall) {

    public static final String SCOPE_ALL = "ALL";
    public static final String SCOPE_SELECTED = "SELECTED";

    /**
     * 生成参数。
     *
     * @param temperature 温度，信贷问答建议 0.1~0.3，越低越稳定
     * @param maxTokens   最大输出 token
     * @param topN        引用条数上限
     * @param needCitation 是否必须带引用（金融场景恒为 true）
     */
    public record Options(BigDecimal temperature,
                          Integer maxTokens,
                          Integer topN,
                          Boolean needCitation) {

        public static Options defaults() {
            return new Options(new BigDecimal("0.20"), 1024, 8, Boolean.TRUE);
        }
    }
}
