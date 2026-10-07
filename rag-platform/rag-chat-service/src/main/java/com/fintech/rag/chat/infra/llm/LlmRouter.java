package com.fintech.rag.chat.infra.llm;

import com.fintech.rag.api.client.PlatformClient;
import com.fintech.rag.api.dto.platform.ModelConfigDTO;
import com.fintech.rag.common.core.R;
import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import dev.langchain4j.model.chat.ChatModel;
import dev.langchain4j.model.chat.StreamingChatModel;
import dev.langchain4j.model.openai.OpenAiChatModel;
import dev.langchain4j.model.openai.OpenAiStreamingChatModel;
import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 模型路由器 —— <b>信贷场景的合规关键组件</b>。
 *
 * <p>路由规则：</p>
 * <ol>
 *   <li>先按「本次请求涉及的最高密级」筛出可处理该密级的模型配置；</li>
 *   <li>在该集合内按 priority 升序取第一个可用模型；</li>
 *   <li>调用失败时自动切换到下一个（failover），全部失败才抛错。</li>
 * </ol>
 *
 * <p>典型配置：</p>
 * <pre>
 *   PRIMARY_CLOUD      sensitiveLevel=2  priority=100  云侧 DeepSeek/通义
 *   SENSITIVE_PRIVATE  sensitiveLevel=3  priority=10   内网私有化模型
 * </pre>
 * 高密级请求只会命中私有化通道，数据不出内网。
 *
 * <p><b>埋点挂载点</b>：模型实例构建时挂上 {@link LlmTraceListener}，
 * 使「路由」与「埋点」解耦 —— 无论路由到哪个模型埋点都自动生效，
 * 不必在业务代码里到处手写打点。</p>
 *
 * @author rag-platform
 */
@Component
public class LlmRouter {

    private static final Logger log = LoggerFactory.getLogger(LlmRouter.class);

    private final PlatformClient platformClient;
    private final LlmTraceListener traceListener;

    /** configCode -> 同步模型实例 */
    private final Map<String, ChatModel> chatModels = new ConcurrentHashMap<>();

    /** configCode -> 流式模型实例 */
    private final Map<String, StreamingChatModel> streamingModels = new ConcurrentHashMap<>();

    /** 当前生效的配置，按 priority 升序 */
    private volatile List<ModelConfigDTO> configs = new ArrayList<>();

    public LlmRouter(PlatformClient platformClient, LlmTraceListener traceListener) {
        this.platformClient = platformClient;
        this.traceListener = traceListener;
    }

    @PostConstruct
    public void init() {
        refresh();
    }

    /**
     * 定时刷新模型配置。用定时拉取而非每次问答远程调用，
     * 避免把「模型配置查询」变成高频调用的性能瓶颈。
     */
    @Scheduled(fixedDelayString = "${rag.chat.model-refresh-ms:300000}", initialDelay = 300000)
    public void scheduleRefresh() {
        try {
            refresh();
        } catch (Exception ex) {
            log.error("刷新模型配置失败，沿用旧配置", ex);
        }
    }

    public synchronized void refresh() {
        R<List<ModelConfigDTO>> result = platformClient.listModelConfigs();
        if (result == null || !result.isSuccess() || result.getData() == null) {
            log.warn("拉取模型配置为空，沿用上一次配置");
            return;
        }
        List<ModelConfigDTO> latest = new ArrayList<>(result.getData());
        latest.sort(Comparator.comparing(c -> c.priority() == null ? Integer.MAX_VALUE : c.priority()));

        chatModels.clear();
        streamingModels.clear();
        for (ModelConfigDTO config : latest) {
            try {
                chatModels.put(config.configCode(), buildChatModel(config));
                streamingModels.put(config.configCode(), buildStreamingModel(config));
            } catch (Exception ex) {
                log.error("构建模型实例失败，跳过该配置 configCode={}", config.configCode(), ex);
            }
        }
        this.configs = latest;
        log.info("模型配置已刷新，共 {} 个", latest.size());
    }

    /**
     * 按密级路由（同步）。
     *
     * @param secretLevel 本次请求涉及的最高密级
     */
    public ChatModel route(int secretLevel) {
        ModelConfigDTO config = pick(secretLevel);
        ChatModel model = chatModels.get(config.configCode());
        if (model == null) {
            throw BizException.of(ErrorCode.NO_MODEL_AVAILABLE,
                    "模型实例构建失败：" + config.configCode());
        }
        return model;
    }

    /** 按密级路由（流式） */
    public StreamingChatModel routeStreaming(int secretLevel) {
        ModelConfigDTO config = pick(secretLevel);
        StreamingChatModel model = streamingModels.get(config.configCode());
        if (model == null) {
            throw BizException.of(ErrorCode.NO_MODEL_AVAILABLE,
                    "流式模型实例构建失败：" + config.configCode());
        }
        return model;
    }

    /** 返回本次实际使用的配置编码，用于日志、Token 归因与问题定位 */
    public String routeCode(int secretLevel) {
        return pick(secretLevel).configCode();
    }

    private ModelConfigDTO pick(int secretLevel) {
        List<ModelConfigDTO> snapshot = this.configs;
        if (snapshot.isEmpty()) {
            throw BizException.of(ErrorCode.NO_MODEL_AVAILABLE, "模型配置为空，请检查配置中心");
        }
        // 候选：能处理该密级 且 实例已就绪
        List<ModelConfigDTO> candidates = snapshot.stream()
                .filter(c -> c.sensitiveLevel() != null && c.sensitiveLevel() >= secretLevel)
                .filter(c -> chatModels.containsKey(c.configCode()))
                .toList();

        if (candidates.isEmpty()) {
            throw BizException.of(ErrorCode.NO_MODEL_AVAILABLE,
                    "当前密级(" + secretLevel + ")下无可用模型配置，请检查敏感度路由规则");
        }
        return candidates.get(0);
    }

    private ChatModel buildChatModel(ModelConfigDTO config) {
        return OpenAiChatModel.builder()
                .baseUrl(config.baseUrl())
                .apiKey(config.apiKey())
                .modelName(config.modelName())
                .temperature(config.temperature() == null ? 0.2 : config.temperature())
                .maxTokens(config.maxTokens() == null ? 1024 : config.maxTokens())
                .timeout(Duration.ofSeconds(60))
                .logRequests(false)
                .logResponses(false)
                // 埋点：挂载后所有调用自动产出 GenAI span 与 token 指标
                .listeners(traceListener)
                .build();
    }

    private StreamingChatModel buildStreamingModel(ModelConfigDTO config) {
        return OpenAiStreamingChatModel.builder()
                .baseUrl(config.baseUrl())
                .apiKey(config.apiKey())
                .modelName(config.modelName())
                .temperature(config.temperature() == null ? 0.2 : config.temperature())
                .maxTokens(config.maxTokens() == null ? 1024 : config.maxTokens())
                .timeout(Duration.ofSeconds(120))
                .listeners(traceListener)
                .build();
    }
}
