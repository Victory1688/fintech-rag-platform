package com.fintech.rag.chat.api.controller;

import com.fintech.rag.api.dto.replay.ReplayView;
import com.fintech.rag.chat.app.eval.ReplayAppService;
import com.fintech.rag.common.core.R;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 回放接口 —— <b>「按 traceId 一键回放一次回答」的对外入口</b>。
 *
 * <p><b>为什么路径是 /replay/{traceId} 而不是 /message/{messageId}/replay</b>：
 * traceId 是跨系统（APM、LangFuse、检索日志、审计日志）唯一通用的键。
 * 用户报障时往往只能提供「日志里的一串 ID」，从 traceId 出发才能一次性
 * 把散落在五个地方的证据聚齐。messageId 只是业务侧的锚点，
 * 回放接口同时提供 {@code /replay/by-message/{messageId}} 便于前端从点踩直接跳转。</p>
 *
 * <p><b>网关侧不得暴露本路径</b>：回放会返回他人的问答记录与引用信息，
 * 属于内网运维能力。网关的路由白名单里不应包含 {@code /api/ai/replay/**}；
 * 服务侧另有 {@code X-Request-Source} 准入校验作为纵深防御。</p>
 *
 * @author rag-platform
 */
@RestController
@RequestMapping("/api/ai")
public class ReplayController {

    private final ReplayAppService replayAppService;

    public ReplayController(ReplayAppService replayAppService) {
        this.replayAppService = replayAppService;
    }

    /**
     * 按 traceId 回放。
     *
     * @param traceId     32 位小写 hex 的 W3C trace-id
     * @param withContent 是否请求正文；即便为 true，仍受内容采集档位最终裁决
     */
    @GetMapping("/replay/{traceId}")
    public R<ReplayView> replay(@PathVariable("traceId") String traceId,
                                @RequestParam(value = "withContent", required = false)
                                Boolean withContent) {
        // 用包装类型而非 primitive：@RequestParam(required=false) + boolean 在参数缺省时
        // 会因「不可为 null 的基本类型拿到 null」而抛异常，属于典型的边界坑
        return R.ok(replayAppService.replay(traceId, Boolean.TRUE.equals(withContent)));
    }
}
