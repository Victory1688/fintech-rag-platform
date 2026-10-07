package com.fintech.rag.api.server.port;

import com.fintech.rag.api.dto.platform.AppSignVerifyRequest;
import com.fintech.rag.api.dto.platform.AppSignVerifyResult;

/**
 * 应用签名校验端口（服务端）。
 *
 * <p>两种实现：</p>
 * <ul>
 *   <li>rag-platform-service：{@code InProcessAppVerifierAdapter} 直接调本地验签内核，零网络开销；</li>
 *   <li>其它服务：{@code FeignAppVerifierAdapter} 通过 Feign 调用 platform 的 /app/verify。</li>
 * </ul>
 *
 * <p>用端口而非直接依赖 Feign 客户端，是为了让 platform 自身不必调用自己（避免自环调用）。</p>
 *
 * @author rag-platform
 */
public interface AppVerifierPort {

    /**
     * 校验应用签名。
     *
     * <p><b>实现约定：任何异常都必须转成「校验不通过」，不得抛出到上层。</b>
     * 验签属于安全判定，异常即视为失败（fail-close）。</p>
     */
    AppSignVerifyResult verify(AppSignVerifyRequest request);
}
