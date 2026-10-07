package com.fintech.rag.api.client;

import com.fintech.rag.api.dto.platform.AppSignVerifyRequest;
import com.fintech.rag.api.dto.platform.AppSignVerifyResult;
import com.fintech.rag.api.dto.platform.AuditLogDTO;
import com.fintech.rag.api.dto.platform.ModelConfigDTO;
import com.fintech.rag.api.dto.platform.SensitiveRuleDTO;
import com.fintech.rag.api.dto.platform.UserTokenPayload;
import com.fintech.rag.common.constant.RagHeaders;
import com.fintech.rag.common.core.R;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;

import java.util.List;

/**
 * 平台治理服务契约。
 *
 * <p>调用方：几乎所有服务。</p>
 *
 * <p><strong>降级策略：</strong></p>
 * <ul>
 *   <li>验签 / 授权类 → fail-close（拒绝请求）</li>
 *   <li>模型配置 / 脱敏规则 → 走本地缓存，缓存未命中时 fail-close（宁可拒绝也不能无护栏生成）</li>
 *   <li>审计上报 → fail-open（写本地日志 + 重试队列，不阻塞主链路）</li>
 * </ul>
 *
 * @author rag-platform
 */
@FeignClient(name = "rag-platform-service", contextId = "platformClient", path = "/api/platform")
public interface PlatformClient {

    /** 校验内网应用签名 */
    @PostMapping("/app/verify")
    R<AppSignVerifyResult> verifyAppSignature(@RequestBody AppSignVerifyRequest request);

    /** 校验用户令牌（仅网关专用路径使用，避免常规请求重复解析） */
    @PostMapping("/auth/verify")
    R<UserTokenPayload> verifyUserToken(@RequestHeader(RagHeaders.USER_TOKEN) String token);

    /** 拉取模型配置（供 LlmRouter） */
    @GetMapping("/model-configs")
    R<List<ModelConfigDTO>> listModelConfigs();

    /** 拉取脱敏规则 */
    @GetMapping("/sensitive-rules")
    R<List<SensitiveRuleDTO>> listSensitiveRules();

    /** 批量上报审计日志（异步，不阻塞主链路） */
    @PostMapping("/audit/batch")
    R<Void> saveAuditLogs(@RequestBody List<AuditLogDTO> logs);
}
