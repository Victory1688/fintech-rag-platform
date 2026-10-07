package com.fintech.rag.common.observability;

import java.util.Locale;

/**
 * OpenTelemetry GenAI 语义约定常量映射层 —— <b>埋点名称的唯一真源</b>。
 *
 * <p><b>为什么要单独一个常量类？</b></p>
 * <p>截至 2026-09，OTel GenAI 语义约定<b>全部处于 Development 状态</b>
 * （GenAI 文档已于 2026-06 迁至独立仓库 {@code open-telemetry/semantic-conventions-genai}，
 * 尚无 tagged release，属性名仍可能变更）。一旦属性改名，如果没有映射层，
 * 就要在几十处业务代码里改字符串并重建全部看板；有映射层则只改本文件。</p>
 *
 * <p><b>禁止使用的废弃属性</b>（照抄 2025 年博客的常见坑）：</p>
 * <ul>
 *   <li>{@code gen_ai.system} → 已由 {@code gen_ai.provider.name} 取代（v1.37 起）</li>
 *   <li>{@code gen_ai.content.prompt} / {@code gen_ai.content.completion} → 已废弃</li>
 * </ul>
 *
 * @author rag-platform
 */
public final class GenAiSemconv {

    private GenAiSemconv() {
    }

    // ---------------------------------------------------------------- 操作名
    public static final String OP_CHAT = "chat";
    public static final String OP_TEXT_COMPLETION = "text_completion";
    public static final String OP_EMBEDDINGS = "embeddings";
    public static final String OP_RETRIEVAL = "retrieval";
    public static final String OP_EXECUTE_TOOL = "execute_tool";
    public static final String OP_INVOKE_AGENT = "invoke_agent";
    public static final String OP_CREATE_AGENT = "create_agent";

    // ------------------------------------------------------------ span 属性
    public static final String ATTR_OPERATION_NAME = "gen_ai.operation.name";
    public static final String ATTR_PROVIDER_NAME = "gen_ai.provider.name";
    public static final String ATTR_REQUEST_MODEL = "gen_ai.request.model";
    public static final String ATTR_RESPONSE_MODEL = "gen_ai.response.model";
    public static final String ATTR_REQUEST_TEMPERATURE = "gen_ai.request.temperature";
    public static final String ATTR_REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens";
    public static final String ATTR_REQUEST_TOP_P = "gen_ai.request.top_p";
    public static final String ATTR_INPUT_TOKENS = "gen_ai.usage.input_tokens";
    public static final String ATTR_OUTPUT_TOKENS = "gen_ai.usage.output_tokens";
    public static final String ATTR_FINISH_REASONS = "gen_ai.response.finish_reasons";
    public static final String ATTR_CONVERSATION_ID = "gen_ai.conversation.id";
    public static final String ATTR_TOOL_NAME = "gen_ai.tool.name";
    public static final String ATTR_TOOL_CALL_ID = "gen_ai.tool.call.id";
    public static final String ATTR_AGENT_NAME = "gen_ai.agent.name";
    public static final String ATTR_AGENT_ID = "gen_ai.agent.id";
    public static final String ATTR_ERROR_TYPE = "error.type";

    /** 内容采集（opt-in，默认关闭，见 docs/05 §6） */
    public static final String ATTR_SYSTEM_INSTRUCTIONS = "gen_ai.system_instructions";
    public static final String ATTR_INPUT_MESSAGES = "gen_ai.input.messages";
    public static final String ATTR_OUTPUT_MESSAGES = "gen_ai.output.messages";
    /** 内容与 trace 分离存储时使用的独立事件名 */
    public static final String EVENT_INFERENCE_OPERATION_DETAILS = "gen_ai.client.inference.operation.details";

    // ---------------------------------------------------------------- 指标
    public static final String METRIC_TOKEN_USAGE = "gen_ai.client.token.usage";
    public static final String METRIC_OPERATION_DURATION = "gen_ai.client.operation.duration";
    /** 流式首字延迟（TTFT）：v1.41.0 起定义，<b>必须手工埋点</b> */
    public static final String METRIC_TIME_TO_FIRST_CHUNK = "gen_ai.client.operation.time_to_first_chunk";
    /** 流式吐字间隔：v1.41.0 起定义，<b>必须手工埋点</b> */
    public static final String METRIC_TIME_PER_OUTPUT_CHUNK = "gen_ai.client.operation.time_per_output_chunk";
    public static final String TAG_TOKEN_TYPE = "gen_ai.token.type";
    public static final String TAG_OPERATION_NAME = "gen_ai.operation.name";
    public static final String TAG_PROVIDER_NAME = "gen_ai.provider.name";
    public static final String TAG_REQUEST_MODEL = "gen_ai.request.model";
    public static final String TAG_RESPONSE_MODEL = "gen_ai.response.model";
    public static final String TAG_ERROR_TYPE = "error.type";
    public static final String TOKEN_TYPE_INPUT = "input";
    public static final String TOKEN_TYPE_OUTPUT = "output";

    // -------------------------------------------------- 自有业务属性与指标
    /** 自研属性统一加自有前缀，避免与规范属性冲突（规范明确要求这么做） */
    public static final String ATTR_SOURCE = "rag.source";
    public static final String ATTR_SUBJECT_HASH = "rag.subject.hash";
    public static final String ATTR_CONVERSATION_ID = "rag.conversation.id";
    public static final String ATTR_KB_COUNT = "rag.kb.count";
    public static final String ATTR_PROMPT_VERSION = "rag.prompt.version";
    public static final String ATTR_OUTCOME = "rag.outcome";
    public static final String ATTR_CITATION_COUNT = "rag.citation.count";
    public static final String ATTR_GUARDRAIL_HIT = "rag.guardrail.hit";
    public static final String ATTR_CACHE_HIT = "rag.retrieval.cache.hit";
    public static final String ATTR_CHUNK_COUNT = "rag.retrieval.chunk.count";
    public static final String ATTR_RAW_CHUNK_COUNT = "rag.retrieval.raw.chunk.count";
    public static final String ATTR_TOP_SCORE = "rag.retrieval.top.score";
    public static final String ATTR_RERANK_USED = "rag.retrieval.rerank.used";

    public static final String METRIC_CHAT_ANSWER_TOTAL = "rag_chat_answer_total";
    public static final String METRIC_RETRIEVAL_TOTAL = "rag_retrieval_total";
    public static final String METRIC_RETRIEVAL_EMPTY_TOTAL = "rag_retrieval_empty_total";
    public static final String METRIC_RETRIEVAL_CHUNKS = "rag_retrieval_chunks";
    public static final String METRIC_GUARDRAIL_HIT_TOTAL = "rag_guardrail_hit_total";
    public static final String METRIC_FEEDBACK_TOTAL = "rag_feedback_total";
    public static final String TAG_OUTCOME = "outcome";
    public static final String TAG_APP_SOURCE = "app_source";
    public static final String TAG_MODEL_CODE = "model_code";
    public static final String TAG_GUARDRAIL_TYPE = "guardrail_type";
    public static final String TAG_VOTE = "vote";
    public static final String TAG_REASON_CODE = "reason_code";

    /** 业务根 span 名：自有前缀 + 自有语义，<b>不要伪装成规范名</b> */
    public static final String SPAN_BUSINESS_CHAT = "rag.chat.answer";
    public static final String SPAN_BUSINESS_RETRIEVAL = "retrieval ragflow-hybrid";

    /**
     * 推理 span 命名：{@code {gen_ai.operation.name} {gen_ai.request.model}}。
     *
     * <p>规范要求模型名做小写与空白规范化，避免出现非法 span 名。</p>
     */
    public static String inferenceSpanName(String operation, String model) {
        String safeOp = (operation == null || operation.isBlank()) ? OP_CHAT : operation;
        String safeModel = sanitizeName(model);
        return safeOp + " " + safeModel;
    }

    /** 工具 span 命名：{@code execute_tool {tool.name}}（v1.41 起必须带工具名） */
    public static String toolSpanName(String toolName) {
        return OP_EXECUTE_TOOL + " " + sanitizeName(toolName);
    }

    /** Agent span 命名：{@code invoke_agent {gen_ai.agent.name}} */
    public static String agentSpanName(String agentName) {
        return OP_INVOKE_AGENT + " " + sanitizeName(agentName);
    }

    private static String sanitizeName(String value) {
        if (value == null || value.isBlank()) {
            return "unknown";
        }
        return value.trim().toLowerCase(Locale.ROOT).replace(' ', '-');
    }
}
