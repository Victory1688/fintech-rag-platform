package com.fintech.rag.chat.api.controller;

import com.fintech.rag.api.dto.chat.ChatRequest;
import com.fintech.rag.api.dto.chat.ChatResponse;
import com.fintech.rag.api.server.interceptor.SourceAuthInterceptor;
import com.fintech.rag.chat.app.service.ChatOrchestrationAppService;
import com.fintech.rag.common.context.RequestContext;
import com.fintech.rag.common.core.R;
import com.fintech.rag.common.exception.ErrorCode;
import io.micrometer.tracing.Span;
import io.micrometer.tracing.Tracer;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 问答接口。
 *
 * <p>主体身份一律从请求头获取（网关透传或 AppKey 验签结果），
 * <b>绝不从请求体读取</b>，否则用户改一个字段就能以他人身份提问。</p>
 *
 * <p><b>重要修复：异步 SSE 的上下文传递</b></p>
 * <p>流式生成跑在独立线程池里，而 {@code RequestContext}（ThreadLocal）与 MDC
 * <b>不会自动跨线程传递</b>。不显式传递会同时踩三个坑：</p>
 * <ol>
 *   <li>检索请求里的 traceId 变成 null → 检索日志与链路关联不上；</li>
 *   <li>日志里没有 traceId → 一次问答的日志串不起来；</li>
 *   <li>OTel 在当前线程找不到父 span → <b>另起一条新链路</b>，
 *       一个用户请求在 LangFuse 里变成两条互不相关的 Trace。</li>
 * </ol>
 * <p>因此这里在提交任务前捕获上下文快照与父 span，在任务线程内恢复。</p>
 *
 * @author rag-platform
 */
@RestController
@RequestMapping("/api/ai")
public class ChatController {

    private static final Logger log = LoggerFactory.getLogger(ChatController.class);

    /** SSE 超时：覆盖最长生成耗时并留余量 */
    private static final long SSE_TIMEOUT_MS = 180_000L;

    private final ChatOrchestrationAppService chatAppService;
    private final ObjectProvider<Tracer> tracerProvider;

    /**
     * 生成链路是长耗时阻塞调用，必须使用独立线程池，
     * 不能占用 Tomcat 的请求线程，否则少量并发就会把容器线程打满。
     */
    private final ExecutorService streamExecutor = Executors.newFixedThreadPool(32, r -> {
        Thread thread = new Thread(r, "chat-stream-" + System.nanoTime());
        thread.setDaemon(true);
        return thread;
    });

    public ChatController(ChatOrchestrationAppService chatAppService,
                          ObjectProvider<Tracer> tracerProvider) {
        this.chatAppService = chatAppService;
        this.tracerProvider = tracerProvider;
    }

    /** 非流式问答 */
    @PostMapping("/chat")
    public R<ChatResponse> chat(@Valid @RequestBody ChatRequest request, HttpServletRequest servletRequest) {
        SubjectContext context = resolveSubject(servletRequest);
        return R.ok(chatAppService.chat(request, context.subjectType(), context.subjectId(),
                context.roleCodes(), context.deptId()));
    }

    /**
     * 流式问答（SSE）。
     *
     * <p>事件协议：</p>
     * <pre>
     *   event: delta      数据为增量文本片段
     *   event: citations  数据为引用列表 JSON
     *   event: done       数据为完成标记
     *   event: error      数据为错误码与提示
     * </pre>
     */
    @PostMapping(value = "/chat/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter chatStream(@Valid @RequestBody ChatRequest request, HttpServletRequest servletRequest) {
        SseEmitter emitter = new SseEmitter(SSE_TIMEOUT_MS);
        SubjectContext context = resolveSubject(servletRequest);

        // ---- 捕获上下文（必须在请求线程上做） ----
        RequestContext.Snapshot snapshot = RequestContext.get();
        String traceId = RequestContext.currentTraceId();
        Tracer tracer = tracerProvider.getIfAvailable();
        Span parentSpan = tracer == null ? null : tracer.currentSpan();

        emitter.onTimeout(() -> log.warn("SSE 超时 conversationId={}", request.conversationId()));
        emitter.onError(ex -> log.warn("SSE 异常 conversationId={}", request.conversationId(), ex));

        streamExecutor.execute(() -> {
            // ---- 在线程池线程内恢复上下文 ----
            RequestContext.set(snapshot);
            if (traceId != null) {
                MDC.put("traceId", traceId);
            }
            Tracer.SpanInScope scope = null;
            if (tracer != null && parentSpan != null) {
                scope = tracer.withSpan(parentSpan);
            }
            try {
                chatAppService.stream(request, context.subjectType(), context.subjectId(),
                        context.roleCodes(), context.deptId(),
                        delta -> sendQuietly(emitter, "delta", delta),
                        (answer, citations) -> {
                            sendQuietly(emitter, "citations", citations);
                            sendQuietly(emitter, "done", "ok");
                            emitter.complete();
                        },
                        error -> {
                            sendQuietly(emitter, "error",
                                    ErrorCode.LLM_CALL_FAILED.getCode() + ":"
                                            + ErrorCode.LLM_CALL_FAILED.getMessage());
                            emitter.complete();
                        });
            } catch (Exception ex) {
                log.error("流式问答失败 conversationId={}", request.conversationId(), ex);
                sendQuietly(emitter, "error", ErrorCode.INTERNAL_ERROR.getCode());
                emitter.complete();
            } finally {
                if (scope != null) {
                    scope.close();
                }
                MDC.clear();
                RequestContext.clear();
            }
        });
        return emitter;
    }

    private void sendQuietly(SseEmitter emitter, String event, Object data) {
        try {
            emitter.send(SseEmitter.event().name(event).data(data));
        } catch (IOException | IllegalStateException ex) {
            // 客户端主动断开是常态（用户点了「停止生成」），不应记为错误
            log.debug("SSE 推送失败（客户端可能已断开）event={}", event);
        }
    }

    private SubjectContext resolveSubject(HttpServletRequest request) {
        String roles = (String) request.getAttribute(SourceAuthInterceptor.ATTR_USER_ROLES);
        String deptIdText = (String) request.getAttribute(SourceAuthInterceptor.ATTR_USER_DEPT);
        Long deptId = null;
        if (deptIdText != null && !deptIdText.isBlank()) {
            try {
                deptId = Long.parseLong(deptIdText);
            } catch (NumberFormatException ignored) {
                // 非法部门 ID 视为无部门，不放大权限
            }
        }
        String subjectType = RequestContext.currentSource()
                == com.fintech.rag.common.context.RequestSource.DMZ_WEB ? "USER" : "APP";
        String subjectId = RequestContext.currentSubjectId();
        return new SubjectContext(subjectType, subjectId, roles, deptId);
    }

    /** 调用主体上下文 */
    private record SubjectContext(String subjectType, String subjectId, String roleCodes, Long deptId) {
    }
}
