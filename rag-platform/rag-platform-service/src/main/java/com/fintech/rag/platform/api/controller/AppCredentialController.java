package com.fintech.rag.platform.api.controller;

import com.fintech.rag.api.dto.platform.AppSignVerifyRequest;
import com.fintech.rag.api.dto.platform.AppSignVerifyResult;
import com.fintech.rag.common.core.R;
import com.fintech.rag.platform.app.service.AppCredentialAppService;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 应用凭证接口。
 *
 * @author rag-platform
 */
@RestController
@RequestMapping("/api/platform/app")
public class AppCredentialController {

    private final AppCredentialAppService appService;

    public AppCredentialController(AppCredentialAppService appService) {
        this.appService = appService;
    }

    /**
     * 验签（被所有内网服务调用，是 QPS 最高的接口，必须保证轻量与低延迟）。
     */
    @PostMapping("/verify")
    public R<AppSignVerifyResult> verify(@Valid @RequestBody AppSignVerifyRequest request) {
        return R.ok(appService.verify(request));
    }

    /** 创建应用凭证，返回的 secret 仅此一次可见 */
    @PostMapping
    public R<Map<String, String>> create(@RequestParam String appId,
                                         @RequestParam String appName,
                                         @RequestParam(required = false) String owner,
                                         @RequestParam(required = false) Integer qpsLimit,
                                         @RequestParam(required = false) Long dailyLimit) {
        String secret = appService.create(appId, appName, owner, qpsLimit, dailyLimit);
        return R.ok(Map.of("appId", appId, "appSecret", secret,
                "notice", "AppSecret 仅此一次返回，请立即交付给调用方并妥善保管"));
    }

    /** 密钥轮换，graceHours 为旧密钥的并行有效期 */
    @PostMapping("/{appId}/rotate")
    public R<Map<String, String>> rotate(@PathVariable String appId,
                                         @RequestParam(defaultValue = "24") int graceHours) {
        String secret = appService.rotate(appId, graceHours);
        return R.ok(Map.of("appId", appId, "appSecret", secret));
    }

    @GetMapping("/{appId}")
    public R<Map<String, String>> detail(@PathVariable String appId) {
        // 骨架：返回占位；落地时返回脱敏后的应用信息（绝不回显 secret）
        return R.ok(Map.of("appId", appId));
    }
}
