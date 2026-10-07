package com.fintech.rag.api.server.adapter;

import com.fintech.rag.api.client.PlatformClient;
import com.fintech.rag.api.dto.platform.AppSignVerifyRequest;
import com.fintech.rag.api.dto.platform.AppSignVerifyResult;
import com.fintech.rag.api.server.port.AppVerifierPort;
import com.fintech.rag.common.core.R;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * 通过 Feign 调用 rag-platform-service 完成验签。
 *
 * <p><b>fail-close</b>：远程调用异常（超时、503、网络抖动）一律返回「校验不通过」。
 * 绝不能因为 platform 挂了就放行全部请求。</p>
 *
 * @author rag-platform
 */
public class FeignAppVerifierAdapter implements AppVerifierPort {

    private static final Logger log = LoggerFactory.getLogger(FeignAppVerifierAdapter.class);

    private final PlatformClient platformClient;

    public FeignAppVerifierAdapter(PlatformClient platformClient) {
        this.platformClient = platformClient;
    }

    @Override
    public AppSignVerifyResult verify(AppSignVerifyRequest request) {
        try {
            R<AppSignVerifyResult> result = platformClient.verifyAppSignature(request);
            if (result != null && result.isSuccess() && result.getData() != null) {
                return result.getData();
            }
            return AppSignVerifyResult.rejected("验签服务返回异常");
        } catch (Exception ex) {
            log.error("调用验签服务失败，按 fail-close 处理 appId={}", request.appId(), ex);
            return AppSignVerifyResult.rejected("验签服务不可用");
        }
    }
}
