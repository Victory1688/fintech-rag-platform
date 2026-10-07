package com.fintech.rag.gateway.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.ArrayList;
import java.util.List;

/**
 * 网关鉴权配置。
 *
 * @author rag-platform
 */
@ConfigurationProperties(prefix = "rag.gateway")
public class GatewayAuthProperties {

    /** 免登录路径（Ant 风格），务必最小化 */
    private List<String> publicPaths = new ArrayList<>();

    /** 调用 rag-platform-service 校验令牌的超时（毫秒），必须短，否则网关会被拖死 */
    private long authTimeoutMs = 500;

    /** 认证服务不可用时是否拒绝请求。生产必须 true（fail-close） */
    private boolean failClose = true;

    /**
     * 网关签名密钥（可选强校验）。
     * 为空则只依赖「内网侧 IP 白名单 + 内网请求禁止携带来源头」两道闸；
     * 配置后网关会额外注入 X-Gateway-Signature，AI 服务验签，不依赖 IP，适合容器环境。
     */
    private String signSecret;

    /**
     * 是否接受客户端传入的 {@code traceparent}（默认 <b>false</b>）。
     *
     * <p><b>为什么默认拒绝</b>：traceparent 与身份头同属「客户端可伪造」的输入。
     * 若直接接受，攻击者可以：</p>
     * <ul>
     *   <li>把任意请求挂到别人的链路下（污染排障结论、栽赃）；</li>
     *   <li>用超长/畸形 traceparent 制造解析异常与日志噪声；</li>
     *   <li>构造「同一个 traceId 反复出现」以干扰容量统计。</li>
     * </ul>
     * <p>因此默认由网关作为链路的<b>唯一根</b>重新生成。若确有「浏览器 → 后端」的
     * 端到端追踪需求，可置为 true（仅接受格式合法且非全零的 traceparent）。</p>
     */
    private boolean acceptClientTraceparent = false;

    public List<String> getPublicPaths() {
        return publicPaths;
    }

    public void setPublicPaths(List<String> publicPaths) {
        this.publicPaths = publicPaths;
    }

    public long getAuthTimeoutMs() {
        return authTimeoutMs;
    }

    public void setAuthTimeoutMs(long authTimeoutMs) {
        this.authTimeoutMs = authTimeoutMs;
    }

    public boolean isFailClose() {
        return failClose;
    }

    public void setFailClose(boolean failClose) {
        this.failClose = failClose;
    }

    public String getSignSecret() {
        return signSecret;
    }

    public void setSignSecret(String signSecret) {
        this.signSecret = signSecret;
    }

    public boolean isAcceptClientTraceparent() {
        return acceptClientTraceparent;
    }

    public void setAcceptClientTraceparent(boolean acceptClientTraceparent) {
        this.acceptClientTraceparent = acceptClientTraceparent;
    }
}
