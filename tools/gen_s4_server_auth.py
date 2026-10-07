# -*- coding: utf-8 -*-
"""
S4: rag-api 的「服务端接入组件」（共享鉴权拦截器 + 端口适配）
     + rag-platform-service 的进程内验签适配器
     + 覆盖 rag-api 的 AutoConfiguration.imports（追加服务端装配）
"""
import pathlib

BASE = pathlib.Path(r"D:/AiWorkOut/java-ai/rag-platform")
FILES = {}


def add(rel, content):
    FILES[rel] = content.lstrip("\n")


API = "rag-api/src/main/java/com/fintech/rag/api"
PF = "rag-platform-service/src/main/java/com/fintech/rag/platform"

# ============================================================ 端口定义
add(API + "/server/port/AppVerifierPort.java", r'''
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
''')

add(API + "/server/port/UserTokenVerifierPort.java", r'''
package com.fintech.rag.api.server.port;

import com.fintech.rag.api.dto.platform.UserTokenPayload;

/**
 * 用户令牌校验端口（服务端）。
 *
 * <p>仅「网关专用路径」（如 /api/platform/auth/verify）需要真正解析令牌；
 * 常规业务路径信任网关注入的 X-User-Id，不重复解析，避免每请求一次远程调用。</p>
 *
 * @author rag-platform
 */
public interface UserTokenVerifierPort {

    /**
     * 解析并校验令牌。
     *
     * @param token JWT
     * @return 载荷；无效时抛出 BizException(TOKEN_INVALID)
     */
    UserTokenPayload verify(String token);
}
''')

# ============================================================ 配置属性
add(API + "/server/config/SourceAuthProperties.java", r'''
package com.fintech.rag.api.server.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.ArrayList;
import java.util.List;

/**
 * 服务端来源鉴权配置。
 *
 * <pre>
 * rag:
 *   server:
 *     auth:
 *       enabled: true                  # 是否启用（默认关闭，避免影响引入 SDK 的业务方）
 *       public-paths: [...]            # 完全放开
 *       gateway-only-paths: [...]      # 仅允许网关访问（无需应用签名，但仍校验网关网段）
 *       trusted-gateway-cidrs: [...]   # 网关网段白名单
 *       gateway-signature-enabled: true # 启用网关签名强校验（容器环境推荐）
 *       gateway-sign-secret: xxx
 * </pre>
 *
 * <p><b>安全默认值：</b>若既未配置 {@code trusted-gateway-cidrs} 又未启用网关签名，
 * 则任何携带 {@code X-Request-Source} 的请求都会被拒绝。宁可启动后调不通，
 * 也不能默认信任一个可被伪造的请求头。</p>
 *
 * @author rag-platform
 */
@ConfigurationProperties(prefix = "rag.server.auth")
public class SourceAuthProperties {

    private boolean enabled = false;

    private List<String> publicPaths = new ArrayList<>(List.of(
            "/actuator/**", "/doc.html", "/v3/api-docs/**", "/error", "/favicon.ico"));

    private List<String> gatewayOnlyPaths = new ArrayList<>();

    private List<String> trustedGatewayCidrs = new ArrayList<>();

    private boolean gatewaySignatureEnabled = false;

    private String gatewaySignSecret;

    /** 应用签名时间戳窗口（毫秒） */
    private long timestampWindowMs = 5 * 60 * 1000L;

    public boolean isEnabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }

    public List<String> getPublicPaths() {
        return publicPaths;
    }

    public void setPublicPaths(List<String> publicPaths) {
        this.publicPaths = publicPaths;
    }

    public List<String> getGatewayOnlyPaths() {
        return gatewayOnlyPaths;
    }

    public void setGatewayOnlyPaths(List<String> gatewayOnlyPaths) {
        this.gatewayOnlyPaths = gatewayOnlyPaths;
    }

    public List<String> getTrustedGatewayCidrs() {
        return trustedGatewayCidrs;
    }

    public void setTrustedGatewayCidrs(List<String> trustedGatewayCidrs) {
        this.trustedGatewayCidrs = trustedGatewayCidrs;
    }

    public boolean isGatewaySignatureEnabled() {
        return gatewaySignatureEnabled;
    }

    public void setGatewaySignatureEnabled(boolean gatewaySignatureEnabled) {
        this.gatewaySignatureEnabled = gatewaySignatureEnabled;
    }

    public String getGatewaySignSecret() {
        return gatewaySignSecret;
    }

    public void setGatewaySignSecret(String gatewaySignSecret) {
        this.gatewaySignSecret = gatewaySignSecret;
    }

    public long getTimestampWindowMs() {
        return timestampWindowMs;
    }

    public void setTimestampWindowMs(long timestampWindowMs) {
        this.timestampWindowMs = timestampWindowMs;
    }
}
''')

# ============================================================ 请求体缓存
add(API + "/server/interceptor/BodyCachingFilter.java", r'''
package com.fintech.rag.api.server.interceptor;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.core.Ordered;
import org.springframework.web.filter.OncePerRequestFilter;
import org.springframework.web.util.ContentCachingRequestWrapper;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Set;

/**
 * 请求体缓存过滤器。
 *
 * <p>应用签名需要原始请求体参与校验，而 Servlet 的 InputStream 只能读一次。
 * 用 {@link ContentCachingRequestWrapper} 缓存后可重复读取。</p>
 *
 * <p><b>必须跳过文件上传路径</b>：把 200MB 的文档读进堆内存会直接 OOM。</p>
 *
 * @author rag-platform
 */
public class BodyCachingFilter extends OncePerRequestFilter implements Ordered {

    private static final String CACHE_ATTRIBUTE = "CACHED_BODY";

    private static final Set<String> SKIP_PREFIXES = Set.of(
            "/api/ingest/upload", "/actuator", "/v3/api-docs", "/doc.html");

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        ContentCachingRequestWrapper wrapper = new ContentCachingRequestWrapper(request);
        filterChain.doFilter(wrapper, response);
        // 必须在链执行完之后读取：此时 body 才被真正消费并缓存
        byte[] body = wrapper.getContentAsByteArray();
        if (body.length > 0) {
            wrapper.setAttribute(CACHE_ATTRIBUTE, new String(body, StandardCharsets.UTF_8));
        }
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String uri = request.getRequestURI();
        return SKIP_PREFIXES.stream().anyMatch(uri::startsWith);
    }

    @Override
    public int getOrder() {
        return Ordered.HIGHEST_PRECEDENCE + 20;
    }
}
''')

# ============================================================ 核心拦截器
add(API + "/server/interceptor/SourceAuthInterceptor.java", r'''
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
''')

# ============================================================ Feign 适配器
add(API + "/server/adapter/FeignAppVerifierAdapter.java", r'''
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
''')

add(API + "/server/adapter/FeignUserTokenVerifierAdapter.java", r'''
package com.fintech.rag.api.server.adapter;

import com.fintech.rag.api.client.PlatformClient;
import com.fintech.rag.api.dto.platform.UserTokenPayload;
import com.fintech.rag.api.server.port.UserTokenVerifierPort;
import com.fintech.rag.common.core.R;
import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * 通过 Feign 调用 rag-platform-service 校验用户令牌。
 *
 * @author rag-platform
 */
public class FeignUserTokenVerifierAdapter implements UserTokenVerifierPort {

    private static final Logger log = LoggerFactory.getLogger(FeignUserTokenVerifierAdapter.class);

    private final PlatformClient platformClient;

    public FeignUserTokenVerifierAdapter(PlatformClient platformClient) {
        this.platformClient = platformClient;
    }

    @Override
    public UserTokenPayload verify(String token) {
        try {
            R<UserTokenPayload> result = platformClient.verifyUserToken(token);
            if (result == null || !result.isSuccess() || result.getData() == null) {
                throw BizException.of(ErrorCode.TOKEN_INVALID);
            }
            return result.getData();
        } catch (BizException ex) {
            throw ex;
        } catch (Exception ex) {
            log.error("调用令牌校验服务失败", ex);
            throw BizException.of(ErrorCode.AUTH_SERVICE_UNAVAILABLE);
        }
    }
}
''')

# ============================================================ 服务端自动装配
add(API + "/server/config/RagServerAuthAutoConfiguration.java", r'''
package com.fintech.rag.api.server.config;

import com.fintech.rag.api.client.PlatformClient;
import com.fintech.rag.api.server.adapter.FeignAppVerifierAdapter;
import com.fintech.rag.api.server.adapter.FeignUserTokenVerifierAdapter;
import com.fintech.rag.api.server.interceptor.BodyCachingFilter;
import com.fintech.rag.api.server.interceptor.SourceAuthInterceptor;
import com.fintech.rag.api.server.port.AppVerifierPort;
import com.fintech.rag.api.server.port.UserTokenVerifierPort;
import jakarta.servlet.Filter;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.autoconfigure.condition.ConditionalOnWebApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * 服务端来源鉴权自动装配。
 *
 * <p><b>默认关闭</b>（{@code matchIfMissing = false}）。
 * 原因：rag-api 同时作为「内网业务方接入 SDK」，业务方引入本模块只是为了调用我们，
 * 不应被强行装上服务端拦截器。本平台自己的服务需显式配置
 * {@code rag.server.auth.enabled: true}。</p>
 *
 * <p>若开启但容器内不存在 {@link AppVerifierPort} 实现，会直接抛
 * NoSuchBeanDefinitionException 启动失败 —— 这是<b>有意的 fail-fast</b>：
 * 宁可启动不了，也不能带着「看起来有鉴权、实际没鉴权」的配置上线。</p>
 *
 * @author rag-platform
 */
@AutoConfiguration
@ConditionalOnWebApplication(type = ConditionalOnWebApplication.Type.SERVLET)
@ConditionalOnClass(name = "jakarta.servlet.Filter")
@ConditionalOnProperty(prefix = "rag.server.auth", name = "enabled", havingValue = "true")
@EnableConfigurationProperties(SourceAuthProperties.class)
public class RagServerAuthAutoConfiguration {

    /** 平台自身用的是进程内适配器；其它服务在存在 PlatformClient 时自动走 Feign */
    @Bean
    @ConditionalOnMissingBean(AppVerifierPort.class)
    @ConditionalOnBean(PlatformClient.class)
    public AppVerifierPort feignAppVerifierPort(PlatformClient platformClient) {
        return new FeignAppVerifierAdapter(platformClient);
    }

    @Bean
    @ConditionalOnMissingBean(UserTokenVerifierPort.class)
    @ConditionalOnBean(PlatformClient.class)
    public UserTokenVerifierPort feignUserTokenVerifierPort(PlatformClient platformClient) {
        return new FeignUserTokenVerifierAdapter(platformClient);
    }

    @Bean
    @ConditionalOnMissingBean
    public Filter bodyCachingFilter() {
        return new BodyCachingFilter();
    }

    @Bean
    public SourceAuthInterceptor sourceAuthInterceptor(SourceAuthProperties properties,
                                                      AppVerifierPort appVerifierPort,
                                                      org.springframework.beans.factory.ObjectProvider<UserTokenVerifierPort> provider) {
        return new SourceAuthInterceptor(properties, appVerifierPort, provider);
    }

    @Bean
    public WebMvcConfigurer ragServerAuthWebMvcConfigurer(SourceAuthInterceptor interceptor) {
        return new WebMvcConfigurer() {
            @Override
            public void addInterceptors(InterceptorRegistry registry) {
                registry.addInterceptor(interceptor)
                        .addPathPatterns("/api/**", "/internal/**")
                        .excludePathPatterns("/actuator/**", "/doc.html", "/v3/api-docs/**");
            }
        };
    }
}
''')

# 覆盖 imports，追加服务端装配
add("rag-api/src/main/resources/META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports", r'''
com.fintech.rag.api.config.RagApiAutoConfiguration
com.fintech.rag.api.server.config.RagServerAuthAutoConfiguration
''')

# ============================================================ 平台进程内适配器
add(PF + "/infra/security/InProcessAppVerifierAdapter.java", r'''
package com.fintech.rag.platform.infra.security;

import com.fintech.rag.api.dto.platform.AppSignVerifyRequest;
import com.fintech.rag.api.dto.platform.AppSignVerifyResult;
import com.fintech.rag.api.server.port.AppVerifierPort;
import com.fintech.rag.api.server.port.UserTokenVerifierPort;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * rag-platform-service 的进程内验签适配器。
 *
 * <p>platform 是验签能力的宿主，不能通过 Feign 调用自己（自环调用会带来
 * 线程池耗尽与超时放大的双重风险），因此直接注入本地内核。</p>
 *
 * @author rag-platform
 */
@Configuration
public class InProcessAppVerifierAdapter {

    private static final Logger log = LoggerFactory.getLogger(InProcessAppVerifierAdapter.class);

    @Bean
    public AppVerifierPort inProcessAppVerifierPort(AppSignatureVerifier verifier) {
        return request -> {
            try {
                return verifier.verify(request);
            } catch (Exception ex) {
                log.error("本地验签异常，按 fail-close 处理 appId={}", request.appId(), ex);
                return AppSignVerifyResult.rejected("验签服务内部错误");
            }
        };
    }

    @Bean
    public UserTokenVerifierPort inProcessUserTokenVerifierPort(JwtTokenService jwtTokenService) {
        return token -> jwtTokenService.parse(token);
    }
}
''')

if __name__ == "__main__":
    for rel, content in FILES.items():
        target = BASE / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print("W +", rel)
    print("---- total:", len(FILES))
