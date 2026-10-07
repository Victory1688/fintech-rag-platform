package com.fintech.rag.api.client.interceptor;

import com.fintech.rag.api.config.RagSdkProperties;
import com.fintech.rag.common.constant.RagHeaders;
import com.fintech.rag.common.util.HmacSignatures;
import com.fintech.rag.common.util.TraceIds;
import com.fintech.rag.common.context.RequestContext;
import feign.RequestInterceptor;
import feign.RequestTemplate;

import java.nio.charset.StandardCharsets;
import java.util.Collection;
import java.util.UUID;

/**
 * 内网应用身份签名拦截器（内网业务方接入 SDK 的核心组件）。
 *
 * <p>业务方只需在配置里填 {@code rag.sdk.app-id} 与 {@code rag.sdk.app-secret}，
 * 引入 rag-api + 本拦截器即可调用 AI 能力，无需自己实现签名算法。</p>
 *
 * @author rag-platform
 */
public class AppSignatureRequestInterceptor implements RequestInterceptor {

    private final RagSdkProperties properties;

    public AppSignatureRequestInterceptor(RagSdkProperties properties) {
        this.properties = properties;
    }

    @Override
    public void apply(RequestTemplate template) {
        if (!properties.isEnabled()) {
            return;
        }

        String method = template.method();
        String path = template.path();
        String timestamp = String.valueOf(System.currentTimeMillis());
        String nonce = UUID.randomUUID().toString().replace("-", "");
        String body = template.body() == null
                ? ""
                : new String(template.body(), StandardCharsets.UTF_8);
        String bodySha256 = HmacSignatures.sha256Hex(body);

        String signature = HmacSignatures.sign(
                properties.getAppSecret(), method, path, timestamp, nonce, bodySha256);

        template.header(RagHeaders.APP_ID, properties.getAppId());
        template.header(RagHeaders.APP_TIMESTAMP, timestamp);
        template.header(RagHeaders.APP_NONCE, nonce);
        template.header(RagHeaders.APP_SIGNATURE, signature);

        // 顺手透传 traceId，便于跨系统排障
        String traceId = RequestContext.currentTraceId();
        if (traceId == null || traceId.isBlank()) {
            traceId = TraceIds.newTraceId();
        }
        template.header(RagHeaders.TRACE_ID, traceId);
    }

    /** Feign 模板的 query 参数会拼进 path，这里保持 path 与签名侧一致 */
    @SuppressWarnings("unused")
    private String normalizePath(String path, Collection<String> queries) {
        return path;
    }
}
