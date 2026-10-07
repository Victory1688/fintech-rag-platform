package com.fintech.rag.api.server.interceptor;

import com.fintech.rag.api.dto.common.SubjectType;
import com.fintech.rag.api.dto.platform.AppSignVerifyRequest;
import com.fintech.rag.api.dto.platform.AppSignVerifyResult;
import com.fintech.rag.api.dto.platform.UserTokenPayload;
import com.fintech.rag.api.server.config.SourceAuthProperties;
import com.fintech.rag.api.server.port.AppVerifierPort;
import com.fintech.rag.api.server.port.UserTokenVerifierPort;
import com.fintech.rag.common.constant.RagHeaders;
import com.fintech.rag.common.context.RequestContext;
import com.fintech.rag.common.context.RequestSource;
import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import com.fintech.rag.common.util.HmacSignatures;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.http.HttpMethod;
import org.springframework.util.AntPathMatcher;
import org.springframework.web.servlet.HandlerInterceptor;

import java.util.List;

/**
 * 请求来源识别与两套鉴权分流拦截器 —— <b>全平台统一的鉴权入口</b>。
 *
 * <p>分流依据只有一个：{@code X-Request-Source}（由 DMZ 网关注入）。</p>
 *
 * <table border="1">
 *   <caption>两套体系对比</caption>
 *   <tr><th>维度</th><th>DMZ_WEB（外网前端）</th><th>SF_INNER_APP（内网应用）</th></tr>
 *   <tr><td>身份主体</td><td>终端用户</td><td>应用</td></tr>
 *   <tr><td>凭证</td><td>JWT（网关已校验）</td><td>AppKey + HMAC 签名</td></tr>
 *   <tr><td>校验动作</td><td>来源 IP / 网关签名 + 身份头非空</td><td>反向拦截 + 签名/时间戳/nonce 校验</td></tr>
 *   <tr><td>限流维度</td><td>按用户</td><td>按 AppId（独立桶）</td></tr>
 *   <tr><td>权限模型</td><td>人维度</td><td>应用维度</td></tr>
 * </table>
 *
 * <p><b>三道防伪造闸（缺一不可）：</b></p>
 * <ol>
 *   <li>网关洗白：客户端传入的来源头一律被网关删除后重写（见 rag-gateway）；</li>
 *   <li>来源校验：带来源标识的请求必须来自可信网关网段，或通过网关签名验签；</li>
 *   <li>反向拦截：内网请求若携带网关身份特征，直接 403 ——
 *       这一条比白名单更重要，白名单可能配漏，反向拦截是兜底。</li>
 * </ol>
 *
 * @author rag-platform
 */
public class SourceAuthInterceptor implements HandlerInterceptor {

    private static final Logger log = LoggerFactory.getLogger(SourceAuthInterceptor.class);
    private static final AntPathMatcher MATCHER = new AntPathMatcher();

    public static final String ATTR_USER_PAYLOAD = "USER_PAYLOAD";
    public static final String ATTR_APP_RESULT = "APP_VERIFY_RESULT";
    public static final String ATTR_USER_ROLES = "USER_ROLES";
    public static final String ATTR_USER_DEPT = "USER_DEPT";

    private final SourceAuthProperties properties;
    private final AppVerifierPort appVerifierPort;
    private final ObjectProvider<UserTokenVerifierPort> userTokenVerifierProvider;

    public SourceAuthInterceptor(SourceAuthProperties properties,
                                 AppVerifierPort appVerifierPort,
                                 ObjectProvider<UserTokenVerifierPort> userTokenVerifierProvider) {
        this.properties = properties;
        this.appVerifierPort = appVerifierPort;
        this.userTokenVerifierProvider = userTokenVerifierProvider;
    }

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
        if (HttpMethod.OPTIONS.matches(request.getMethod())) {
            return true;
        }

        String path = request.getRequestURI();
        if (matchesAny(properties.getPublicPaths(), path)) {
            return true;
        }

        RequestContext.Snapshot snapshot = RequestContext.get();
        String clientIp = snapshot == null ? request.getRemoteAddr() : snapshot.clientIp();
        String sourceHeader = request.getHeader(RagHeaders.REQUEST_SOURCE);

        // ---------- 闸 3：反向拦截（内网请求不得伪装成网关流量） ----------
        if (sourceHeader == null && request.getHeader(RagHeaders.GATEWAY_SIGNATURE) != null) {
            log.warn("[防伪造] 内网请求携带网关签名 ip={} path={}", clientIp, path);
            throw BizException.of(ErrorCode.REQUEST_SOURCE_FORGED);
        }

        if (RequestSource.DMZ_HEADER_VALUE.equals(sourceHeader)) {
            handleDmzWeb(request, snapshot, clientIp, path);
        } else {
            handleInnerApp(request, snapshot, clientIp, path);
        }
        return true;
    }

    // ------------------------------------------------------------------ 外网用户流量
    private void handleDmzWeb(HttpServletRequest request, RequestContext.Snapshot snapshot,
                              String clientIp, String path) {
        if (!isTrustedGateway(clientIp, request)) {
            log.warn("[防伪造] 来源标识不可信的请求 ip={} path={}", clientIp, path);
            throw BizException.of(ErrorCode.REQUEST_SOURCE_FORGED);
        }

        String userToken = request.getHeader(RagHeaders.USER_TOKEN);

        // 网关专用路径：需要真正解析令牌（例如 /auth/verify 本身就是被拿来校验的）
        if (matchesAny(properties.getGatewayOnlyPaths(), path)) {
            UserTokenVerifierPort port = userTokenVerifierProvider.getIfAvailable();
            if (port == null) {
                throw BizException.of(ErrorCode.AUTH_SERVICE_UNAVAILABLE, "本服务未配置用户令牌校验能力");
            }
            UserTokenPayload payload = port.verify(userToken);
            fillSubject(snapshot, SubjectType.USER.name(), payload.userId(), payload.realName());
            request.setAttribute(ATTR_USER_PAYLOAD, payload);
            return;
        }

        // 常规业务路径：信任网关透传的用户身份头，但必须做非空校验
        String userId = request.getHeader(RagHeaders.USER_ID);
        if (userId == null || userId.isBlank()) {
            throw BizException.of(ErrorCode.TOKEN_INVALID, "缺少用户身份信息，请重新登录");
        }
        fillSubject(snapshot, SubjectType.USER.name(), userId, request.getHeader(RagHeaders.USER_NAME));
        // 角色与部门由网关从 JWT 中解析后透传，用于「按角色/部门授权」的知识库 ACL 判定，
        // 避免每次请求都去 platform 拉一次用户画像
        request.setAttribute(ATTR_USER_ROLES, request.getHeader(RagHeaders.USER_ROLES));
        request.setAttribute(ATTR_USER_DEPT, request.getHeader(RagHeaders.USER_DEPT));
    }

    // ------------------------------------------------------------------ 内网应用流量
    private void handleInnerApp(HttpServletRequest request, RequestContext.Snapshot snapshot,
                                String clientIp, String path) {
        String appId = request.getHeader(RagHeaders.APP_ID);
        String timestamp = request.getHeader(RagHeaders.APP_TIMESTAMP);
        String nonce = request.getHeader(RagHeaders.APP_NONCE);
        String signature = request.getHeader(RagHeaders.APP_SIGNATURE);

        if (isBlank(appId) || isBlank(signature)) {
            throw BizException.of(ErrorCode.APP_SIGN_INVALID, "缺少应用身份信息");
        }

        String bodySha256 = HmacSignatures.sha256Hex(cachedBody(request));
        AppSignVerifyResult result = appVerifierPort.verify(new AppSignVerifyRequest(
                appId, request.getMethod(), path, timestamp, nonce, signature, bodySha256, clientIp));

        if (result == null || !result.valid()) {
            throw BizException.of(ErrorCode.APP_SIGN_INVALID,
                    result == null ? "应用签名校验失败" : result.reason());
        }

        fillSubject(snapshot, SubjectType.APP.name(), appId,
                result.appName() == null ? appId : result.appName());
        request.setAttribute(ATTR_APP_RESULT, result);
    }

    // ------------------------------------------------------------------ 工具
    private boolean isTrustedGateway(String clientIp, HttpServletRequest request) {
        if (properties.getTrustedGatewayCidrs().size() > 0 && cidrMatched(clientIp)) {
            return true;
        }
        if (properties.isGatewaySignatureEnabled()) {
            return verifyGatewaySignature(request);
        }
        return false;
    }

    /**
     * 网关签名验签：{@code X-Gateway-Signature: <timestamp>.<hmac>}。
     * 相比 IP 白名单，容器/K8s 环境下更可靠（Pod IP 会漂移）。
     */
    private boolean verifyGatewaySignature(HttpServletRequest request) {
        String header = request.getHeader(RagHeaders.GATEWAY_SIGNATURE);
        if (header == null) {
            return false;
        }
        int dot = header.lastIndexOf('.');
        if (dot <= 0) {
            return false;
        }
        String timestamp = header.substring(0, dot);
        String signature = header.substring(dot + 1);

        try {
            long ts = Long.parseLong(timestamp);
            if (Math.abs(System.currentTimeMillis() - ts) > properties.getTimestampWindowMs()) {
                return false;
            }
        } catch (NumberFormatException ex) {
            return false;
        }

        String secret = properties.getGatewaySignSecret();
        if (secret == null || secret.isBlank()) {
            log.error("已启用网关签名校验但未配置 rag.server.auth.gateway-sign-secret");
            return false;
        }
        String expected = HmacSignatures.hmacSha256Hex(secret, request.getRequestURI() + "\n" + timestamp);
        return HmacSignatures.constantTimeEquals(expected, signature);
    }

    private boolean cidrMatched(String ip) {
        if (ip == null || ip.isBlank()) {
            return false;
        }
        return properties.getTrustedGatewayCidrs().stream()
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .anyMatch(cidr -> matchCidr(cidr, ip));
    }

    /** 简化 CIDR 匹配（IPv4）。生产建议改用 Spring 的 IpAddressMatcher 以支持 IPv6 */
    private boolean matchCidr(String cidr, String ip) {
        int slash = cidr.indexOf('/');
        if (slash < 0) {
            return cidr.equals(ip);
        }
        try {
            int prefix = Integer.parseInt(cidr.substring(slash + 1));
            long mask = prefix <= 0 ? 0L : (0xFFFFFFFFL << (32 - prefix)) & 0xFFFFFFFFL;
            return (toLong(cidr.substring(0, slash)) & mask) == (toLong(ip) & mask);
        } catch (Exception ex) {
            return false;
        }
    }

    private long toLong(String ip) {
        String[] parts = ip.split("\\.");
        if (parts.length != 4) {
            throw new IllegalArgumentException("非法 IPv4: " + ip);
        }
        long value = 0L;
        for (String part : parts) {
            value = (value << 8) | Integer.parseInt(part);
        }
        return value;
    }

    private boolean matchesAny(List<String> patterns, String path) {
        return patterns != null && patterns.stream().anyMatch(p -> MATCHER.match(p, path));
    }

    private boolean isBlank(String s) {
        return s == null || s.isBlank();
    }

    private String cachedBody(HttpServletRequest request) {
        Object cached = request.getAttribute("CACHED_BODY");
        return cached == null ? "" : cached.toString();
    }

    private void fillSubject(RequestContext.Snapshot snapshot, String subjectType,
                             String subjectId, String subjectName) {
        if (snapshot == null) {
            RequestContext.set(new RequestContext.Snapshot(
                    RequestSource.SF_INNER_APP, subjectType, subjectId, subjectName,
                    null, null, null));
            return;
        }
        RequestContext.set(snapshot.withSubject(subjectType, subjectId, subjectName));
    }
}
