package com.fintech.rag.retrieval.api.controller;

import com.fintech.rag.api.dto.retrieval.RetrievalRequest;
import com.fintech.rag.api.dto.retrieval.RetrievalResponse;
import com.fintech.rag.api.server.interceptor.SourceAuthInterceptor;
import com.fintech.rag.common.core.R;
import com.fintech.rag.retrieval.app.service.RetrievalAppService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 检索接口。
 *
 * <p>注意：{@code roleCodes} 与 {@code deptId} 来自<b>网关注入的请求头</b>（从 JWT 解析），
 * 不从请求体读取 —— 否则用户改一个字段就能把「按角色授权」变成「按任意角色授权」。</p>
 *
 * @author rag-platform
 */
@RestController
@RequestMapping("/api/retrieval")
public class RetrievalController {

    private final RetrievalAppService retrievalAppService;

    public RetrievalController(RetrievalAppService retrievalAppService) {
        this.retrievalAppService = retrievalAppService;
    }

    @PostMapping("/search")
    public R<RetrievalResponse> search(@Valid @RequestBody RetrievalRequest request,
                                       HttpServletRequest servletRequest) {
        String roleCodes = (String) servletRequest.getAttribute(SourceAuthInterceptor.ATTR_USER_ROLES);
        String deptIdText = (String) servletRequest.getAttribute(SourceAuthInterceptor.ATTR_USER_DEPT);
        Long deptId = null;
        if (deptIdText != null && !deptIdText.isBlank()) {
            try {
                deptId = Long.parseLong(deptIdText);
            } catch (NumberFormatException ignored) {
                // 非法部门 ID 视为无部门，不放大权限
            }
        }
        return R.ok(retrievalAppService.search(request, roleCodes, deptId));
    }
}
