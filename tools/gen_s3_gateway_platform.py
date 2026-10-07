# -*- coding: utf-8 -*-
"""
S3: 生成 rag-gateway（DMZ 边界网关）与 rag-platform-service（平台治理）
"""
import pathlib

BASE = pathlib.Path(r"D:/AiWorkOut/java-ai/rag-platform")
FILES = {}


def add(rel, content):
    FILES[rel] = content.lstrip("\n")


# ============================================================================
# rag-common 补充：AES 对称加密（凭证、密钥落库加密）
# ============================================================================
add("rag-common/src/main/java/com/fintech/rag/common/util/AesCiphers.java", r'''
package com.fintech.rag.common.util;

import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Base64;

/**
 * AES-256-GCM 加解密工具，用于 AppSecret、模型 API Key 等敏感字段落库加密。
 *
 * <p>选 GCM 而非 CBC 的原因：GCM 自带完整性校验，密文被篡改会解密失败，
 * 而 CBC 需要额外做 HMAC，容易漏做。</p>
 *
 * <p>输出格式：{@code Base64(IV(12B) || CIPHERTEXT || TAG)}</p>
 *
 * @author rag-platform
 */
public final class AesCiphers {

    private static final String ALGORITHM = "AES";
    private static final String TRANSFORMATION = "AES/GCM/NoPadding";
    private static final int IV_LENGTH = 12;
    private static final int TAG_BITS = 128;

    private static final SecureRandom RANDOM = new SecureRandom();

    private AesCiphers() {
    }

    /** 加密；salt 为 32 字节密钥（建议由 KMS/环境变量提供，禁止入库） */
    public static String encrypt(String plainText, String keyBase64) {
        try {
            byte[] iv = new byte[IV_LENGTH];
            RANDOM.nextBytes(iv);
            Cipher cipher = Cipher.getInstance(TRANSFORMATION);
            cipher.init(Cipher.ENCRYPT_MODE, toKey(keyBase64), new GCMParameterSpec(TAG_BITS, iv));
            byte[] cipherText = cipher.doFinal(plainText.getBytes(StandardCharsets.UTF_8));

            byte[] result = new byte[iv.length + cipherText.length];
            System.arraycopy(iv, 0, result, 0, iv.length);
            System.arraycopy(cipherText, 0, result, iv.length, cipherText.length);
            return Base64.getEncoder().encodeToString(result);
        } catch (Exception ex) {
            throw new IllegalStateException("AES 加密失败", ex);
        }
    }

    /** 解密 */
    public static String decrypt(String cipherBase64, String keyBase64) {
        try {
            byte[] all = Base64.getDecoder().decode(cipherBase64);
            byte[] iv = new byte[IV_LENGTH];
            System.arraycopy(all, 0, iv, 0, IV_LENGTH);
            byte[] cipherText = new byte[all.length - IV_LENGTH];
            System.arraycopy(all, IV_LENGTH, cipherText, 0, cipherText.length);

            Cipher cipher = Cipher.getInstance(TRANSFORMATION);
            cipher.init(Cipher.DECRYPT_MODE, toKey(keyBase64), new GCMParameterSpec(TAG_BITS, iv));
            return new String(cipher.doFinal(cipherText), StandardCharsets.UTF_8);
        } catch (Exception ex) {
            throw new IllegalStateException("AES 解密失败（密钥错误或密文被篡改）", ex);
        }
    }

    private static SecretKeySpec toKey(String keyBase64) {
        byte[] key = Base64.getDecoder().decode(keyBase64);
        if (key.length != 32) {
            throw new IllegalArgumentException("AES-256 密钥必须为 32 字节（Base64 编码后 44 字符）");
        }
        return new SecretKeySpec(key, ALGORITHM);
    }
}
''')

# ============================================================================
# rag-api 补充：用户令牌载荷
# ============================================================================
add("rag-api/src/main/java/com/fintech/rag/api/dto/platform/UserTokenPayload.java", r'''
package com.fintech.rag.api.dto.platform;

import java.util.List;

/**
 * 用户令牌载荷（JWT 解析结果）。
 *
 * @param userId      用户 ID
 * @param realName    姓名
 * @param deptId      部门 ID
 * @param secretLevel 密级，决定可召回内容的上限
 * @param roles       角色编码列表
 * @author rag-platform
 */
public record UserTokenPayload(String userId,
                               String realName,
                               Long deptId,
                               Integer secretLevel,
                               List<String> roles) {
}
''')

# ============================================================================
# ===========================  rag-gateway  ==================================
# ============================================================================
add("rag-gateway/pom.xml", r'''
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>com.fintech.rag</groupId>
        <artifactId>rag-platform</artifactId>
        <version>1.0.0-SNAPSHOT</version>
    </parent>

    <artifactId>rag-gateway</artifactId>
    <packaging>jar</packaging>
    <name>rag-gateway</name>
    <description>DMZ 边界网关：鉴权、限流、SSE 转发、请求来源标识注入与洗白</description>

    <dependencies>
        <!--
          必须是 Spring Cloud Gateway（WebFlux），不能同时引入 spring-boot-starter-web，
          否则 Spring MVC 与 WebFlux 冲突导致启动失败。
          rag-common 中的 Servlet 相关自动配置已用 @ConditionalOnWebApplication 隔离。
        -->
        <dependency>
            <groupId>org.springframework.cloud</groupId>
            <artifactId>spring-cloud-starter-gateway</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.cloud</groupId>
            <artifactId>spring-cloud-starter-loadbalancer</artifactId>
        </dependency>
        <dependency>
            <groupId>com.alibaba.cloud</groupId>
            <artifactId>spring-cloud-starter-alibaba-nacos-discovery</artifactId>
        </dependency>
        <dependency>
            <groupId>com.alibaba.cloud</groupId>
            <artifactId>spring-cloud-starter-alibaba-nacos-config</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-redis-reactive</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-actuator</artifactId>
        </dependency>
        <dependency>
            <groupId>io.micrometer</groupId>
            <artifactId>micrometer-registry-prometheus</artifactId>
        </dependency>

        <dependency>
            <groupId>com.fintech.rag</groupId>
            <artifactId>rag-common</artifactId>
        </dependency>
        <dependency>
            <groupId>com.fintech.rag</groupId>
            <artifactId>rag-api</artifactId>
        </dependency>
    </dependencies>

    <build>
        <finalName>rag-gateway</finalName>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>
''')

GW = "rag-gateway/src/main/java/com/fintech/rag/gateway"

add(GW + "/GatewayApplication.java", r'''
package com.fintech.rag.gateway;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;

/**
 * DMZ 边界网关启动类。
 *
 * <p>职责边界（严格遵守）：只管流量与安全，不承载任何 RAG / LLM 业务逻辑。
 * 一旦在网关里写 Prompt 拼装或检索逻辑，就会变成「分布式单体」。</p>
 *
 * @author rag-platform
 */
@SpringBootApplication(scanBasePackages = "com.fintech.rag.gateway")
@EnableDiscoveryClient
@ConfigurationPropertiesScan("com.fintech.rag.gateway")
public class GatewayApplication {

    public static void main(String[] args) {
        SpringApplication.run(GatewayApplication.class, args);
    }
}
''')

add(GW + "/config/GatewayAuthProperties.java", r'''
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
}
''')

add(GW + "/filter/RequestSourceSanitizeGlobalFilter.java", r'''
package com.fintech.rag.gateway.filter;

import com.fintech.rag.common.constant.RagHeaders;
import com.fintech.rag.common.context.RequestSource;
import com.fintech.rag.common.util.HmacSignatures;
import com.fintech.rag.common.util.TraceIds;
import com.fintech.rag.gateway.config.GatewayAuthProperties;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.util.Set;

/**
 * 请求来源标识注入与「洗白」过滤器 —— <b>整套防伪造机制的第一道闸</b>。
 *
 * <p>核心逻辑（顺序不可颠倒）：</p>
 * <ol>
 *   <li><b>先删</b>：强制移除客户端可能传入的一切身份/来源头，防止前端伪造；</li>
 *   <li><b>再写</b>：注入可信的 {@code X-Request-Source: DMZ_GATEWAY}；</li>
 *   <li>透传 traceId，缺失则新生成；</li>
 *   <li>可选注入 {@code X-Gateway-Signature}，供内网侧做不依赖 IP 的强校验。</li>
 * </ol>
 *
 * <p>为什么不在 route 里用 {@code RemoveRequestHeader}/{@code AddRequestHeader}？
 * 声明式过滤器对新增路由容易漏配，一旦漏配就是静默的鉴权绕过。
 * 用 GlobalFilter 可以保证「所有路由无例外」。</p>
 *
 * @author rag-platform
 */
@Component
public class RequestSourceSanitizeGlobalFilter implements GlobalFilter, Ordered {

    /** 客户端可伪造、必须由网关统一洗掉的头 */
    private static final Set<String> SPOOFABLE_HEADERS = Set.of(
            RagHeaders.REQUEST_SOURCE,
            RagHeaders.GATEWAY_SIGNATURE,
            RagHeaders.USER_ID,
            RagHeaders.USER_NAME,
            RagHeaders.USER_ROLES,
            RagHeaders.USER_DEPT,
            RagHeaders.APP_ID,
            RagHeaders.APP_TIMESTAMP,
            RagHeaders.APP_NONCE,
            RagHeaders.APP_SIGNATURE
    );

    private final GatewayAuthProperties properties;

    public RequestSourceSanitizeGlobalFilter(GatewayAuthProperties properties) {
        this.properties = properties;
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        ServerHttpRequest request = exchange.getRequest();
        String traceId = TraceIds.resolve(request.getHeaders().getFirst(RagHeaders.TRACE_ID));

        ServerHttpRequest.Builder builder = request.mutate();
        builder.headers(headers -> {
            SPOOFABLE_HEADERS.forEach(headers::remove);
            headers.set(RagHeaders.REQUEST_SOURCE, RequestSource.DMZ_HEADER_VALUE);
            headers.set(RagHeaders.TRACE_ID, traceId);
            if (properties.getSignSecret() != null && !properties.getSignSecret().isBlank()) {
                String timestamp = String.valueOf(System.currentTimeMillis());
                String signature = HmacSignatures.hmacSha256Hex(
                        properties.getSignSecret(), request.getPath().value() + "\n" + timestamp);
                headers.set(RagHeaders.GATEWAY_SIGNATURE, timestamp + "." + signature);
            }
        });

        ServerWebExchange mutated = exchange.mutate()
                .request(builder.build())
                .build();
        mutated.getResponse().getHeaders().set(RagHeaders.TRACE_ID, traceId);
        return chain.filter(mutated);
    }

    @Override
    public int getOrder() {
        // 必须最早执行：任何鉴权过滤器都必须拿到「已洗白」的请求头
        return Ordered.HIGHEST_PRECEDENCE + 100;
    }
}
''')

add(GW + "/filter/UnifiedAuthGlobalFilter.java", r'''
package com.fintech.rag.gateway.filter;

import com.fintech.rag.api.dto.platform.UserTokenPayload;
import com.fintech.rag.common.constant.RagHeaders;
import com.fintech.rag.gateway.config.GatewayAuthProperties;
import com.fintech.rag.gateway.infra.PlatformAuthClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.http.server.reactive.ServerHttpResponse;
import org.springframework.stereotype.Component;
import org.springframework.util.AntPathMatcher;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.nio.charset.StandardCharsets;

/**
 * 统一鉴权过滤器（只处理「外网用户流量」）。
 *
 * <p>职责：校验用户令牌 → 解析出用户身份 → 以可信 Header 透传给内网服务。
 * 内网业务微服务的流量不走网关，其应用签名校验在各服务自身的拦截器中完成。</p>
 *
 * <p><b>fail-close 原则</b>：认证服务不可用时必须拒绝请求。
 * 若选择 fail-open，一次 platform 抖动就等于全网鉴权失效，属于不可接受的风险。</p>
 *
 * @author rag-platform
 */
@Component
public class UnifiedAuthGlobalFilter implements GlobalFilter, Ordered {

    private static final Logger log = LoggerFactory.getLogger(UnifiedAuthGlobalFilter.class);
    private static final AntPathMatcher MATCHER = new AntPathMatcher();

    private final PlatformAuthClient platformAuthClient;
    private final GatewayAuthProperties properties;

    public UnifiedAuthGlobalFilter(PlatformAuthClient platformAuthClient, GatewayAuthProperties properties) {
        this.platformAuthClient = platformAuthClient;
        this.properties = properties;
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        ServerHttpRequest request = exchange.getRequest();
        String path = request.getPath().value();

        if (isPublic(path) || isPreflight(request)) {
            return chain.filter(exchange);
        }

        String token = request.getHeaders().getFirst(RagHeaders.USER_TOKEN);
        if (token == null || token.isBlank()) {
            return reject(exchange, HttpStatus.UNAUTHORIZED, "A0001", "缺少用户令牌");
        }

        return platformAuthClient.verifyUserToken(token)
                .flatMap(payload -> {
                    if (payload == null) {
                        return reject(exchange, HttpStatus.UNAUTHORIZED, "A0001", "令牌无效或已过期");
                    }
                    ServerHttpRequest mutated = request.mutate()
                            .header(RagHeaders.USER_ID, payload.userId())
                            .header(RagHeaders.USER_NAME, payload.realName() == null ? "" : payload.realName())
                            .header(RagHeaders.USER_ROLES, payload.roles() == null
                                    ? "" : String.join(",", payload.roles()))
                            .header(RagHeaders.USER_DEPT, payload.deptId() == null
                                    ? "" : String.valueOf(payload.deptId()))
                            .build();
                    return chain.filter(exchange.mutate().request(mutated).build());
                })
                .onErrorResume(ex -> {
                    log.error("鉴权服务调用异常 path={}", path, ex);
                    if (properties.isFailClose()) {
                        return reject(exchange, HttpStatus.SERVICE_UNAVAILABLE, "A0009", "认证服务不可用，请稍后重试");
                    }
                    return reject(exchange, HttpStatus.UNAUTHORIZED, "A0001", "令牌校验失败");
                });
    }

    private boolean isPublic(String path) {
        return properties.getPublicPaths().stream().anyMatch(pattern -> MATCHER.match(pattern, path));
    }

    private boolean isPreflight(ServerHttpRequest request) {
        return org.springframework.http.HttpMethod.OPTIONS.equals(request.getMethod());
    }

    private Mono<Void> reject(ServerWebExchange exchange, HttpStatus status, String code, String message) {
        ServerHttpResponse response = exchange.getResponse();
        response.setStatusCode(status);
        response.getHeaders().setContentType(MediaType.APPLICATION_JSON);
        String body = "{\"code\":\"" + code + "\",\"message\":\"" + message + "\",\"data\":null}";
        DataBuffer buffer = response.bufferFactory().wrap(body.getBytes(StandardCharsets.UTF_8));
        return response.writeWith(Mono.just(buffer));
    }

    @Override
    public int getOrder() {
        // 晚于来源洗白，早于一切业务转发
        return Ordered.HIGHEST_PRECEDENCE + 200;
    }
}
''')

add(GW + "/infra/PlatformAuthClient.java", r'''
package com.fintech.rag.gateway.infra;

import com.fintech.rag.api.dto.platform.UserTokenPayload;
import com.fintech.rag.common.constant.RagHeaders;
import com.fintech.rag.common.core.R;
import com.fintech.rag.gateway.config.GatewayAuthProperties;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.time.Duration;

/**
 * 调用 rag-platform-service 校验用户令牌。
 *
 * <p>注意：这里刻意使用「服务名 + 负载均衡」而非硬编码 IP，
 * 复用 Nacos 服务发现，避免容器环境下 IP 漂移导致网关整体不可用。</p>
 *
 * @author rag-platform
 */
@Component
public class PlatformAuthClient {

    private static final ParameterizedTypeReference<R<UserTokenPayload>> TYPE_REF =
            new ParameterizedTypeReference<>() {
            };

    private final WebClient webClient;
    private final GatewayAuthProperties properties;

    public PlatformAuthClient(WebClient.Builder loadBalancedWebClientBuilder, GatewayAuthProperties properties) {
        this.webClient = loadBalancedWebClientBuilder
                .baseUrl("http://rag-platform-service")
                .build();
        this.properties = properties;
    }

    /**
     * 校验用户令牌。
     *
     * @param token 用户 JWT
     * @return 校验通过返回载荷，否则返回空 Mono
     */
    public Mono<UserTokenPayload> verifyUserToken(String token) {
        return webClient.post()
                .uri("/api/platform/auth/verify")
                .header(RagHeaders.USER_TOKEN, token)
                .retrieve()
                .bodyToMono(TYPE_REF)
                .timeout(Duration.ofMillis(properties.getAuthTimeoutMs()))
                .map(result -> result.isSuccess() ? result.getData() : null);
    }
}
''')

add(GW + "/config/RateLimiterConfig.java", r'''
package com.fintech.rag.gateway.config;

import com.fintech.rag.common.constant.RagHeaders;
import org.springframework.cloud.gateway.filter.ratelimit.KeyResolver;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;
import reactor.core.publisher.Mono;

/**
 * 网关限流 Key 解析器。
 *
 * <p>限流维度决定「谁能把谁打挂」：</p>
 * <ul>
 *   <li>{@code userKeyResolver}：按用户维度（外网前端流量）。生成链路成本高，
 *       必须按人限流，否则单个用户刷问题就能把模型配额耗尽。</li>
 *   <li>{@code appKeyResolver}：按应用维度（内网业务微服务）。与用户独立成桶，
 *       防止内网批量调用把前端 AI 能力挤垮。</li>
 * </ul>
 *
 * <p>两者必须使用<b>独立的 Redis 桶</b>，因此 Key 前缀不同。</p>
 *
 * @author rag-platform
 */
@Configuration
public class RateLimiterConfig {

    @Bean
    @Primary
    public KeyResolver userKeyResolver() {
        return exchange -> {
            String userId = exchange.getRequest().getHeaders().getFirst(RagHeaders.USER_ID);
            if (userId != null && !userId.isBlank()) {
                return Mono.just("user:" + userId);
            }
            // 未登录/预检请求退化为按 IP，避免所有匿名请求共用一个桶
            String ip = exchange.getRequest().getRemoteAddress() == null
                    ? "unknown"
                    : exchange.getRequest().getRemoteAddress().getAddress().getHostAddress();
            return Mono.just("ip:" + ip);
        };
    }

    @Bean
    public KeyResolver appKeyResolver() {
        return exchange -> {
            String appId = exchange.getRequest().getHeaders().getFirst(RagHeaders.APP_ID);
            return Mono.just("app:" + (appId == null || appId.isBlank() ? "anonymous" : appId));
        };
    }
}
''')

add(GW + "/config/WebClientConfig.java", r'''
package com.fintech.rag.gateway.config;

import org.springframework.cloud.client.loadbalancer.LoadBalanced;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.reactive.function.client.WebClient;

/**
 * WebClient 配置（启用服务发现负载均衡）。
 *
 * @author rag-platform
 */
@Configuration
public class WebClientConfig {

    @Bean
    @LoadBalanced
    public WebClient.Builder loadBalancedWebClientBuilder() {
        return WebClient.builder();
    }
}
''')

add("rag-gateway/src/main/resources/application.yml", r'''
server:
  port: 8080
  # 网关前置一般还有 Nginx，此处只监听内网；Nginx 需配置 proxy_buffering off 才能透传 SSE
  shutdown: graceful

spring:
  application:
    name: rag-gateway
  profiles:
    active: dev
  config:
    import:
      - optional:nacos:rag-gateway.yaml
      - optional:nacos:rag-common.yaml
  cloud:
    nacos:
      server-addr: ${NACOS_ADDR:127.0.0.1:8848}
      username: ${NACOS_USERNAME:nacos}
      password: ${NACOS_PASSWORD:nacos}
      discovery:
        namespace: ${NACOS_NAMESPACE:rag}
        group: RAG_GROUP
      config:
        namespace: ${NACOS_NAMESPACE:rag}
        group: RAG_GROUP
        file-extension: yaml
    # ---------------------------------------------------------------------
    # 重要版本提示：Spring Cloud Gateway 4.2 起，配置前缀搬迁为
    #   spring.cloud.gateway.server.webflux.*
    # 本文件沿用兼容前缀 spring.cloud.gateway.*。
    # 若你使用 Spring Cloud Gateway 5.x 出现「路由不生效」，请整体替换前缀。
    # ---------------------------------------------------------------------
    gateway:
      discovery:
        locator:
          # 关闭自动路由：自动路由会把所有注册服务暴露出去，是常见的安全事故来源
          enabled: false
      httpclient:
        connect-timeout: 3000
        # SSE 必须调大，否则长回答会在中途被网关掐断
        response-timeout: 300s
      routes:
        # 说明：路由不做重写，各服务自身的 Controller 就挂在 /api/** 下。
        # 好处是「内网直连」与「网关转发」走同一套路径契约，排障时不会混淆。
        - id: rag-chat-service
          uri: lb://rag-chat-service
          predicates:
            - Path=/api/ai/**
          filters:
            # 生成链路成本高，限流必须做在网关；桶按「用户」维度，避免单用户打爆模型
            - name: RequestRateLimiter
              args:
                key-resolver: "#{@userKeyResolver}"
                redis-rate-limiter.replenishRate: 2
                redis-rate-limiter.burstCapacity: 5
        - id: rag-knowledge-service
          uri: lb://rag-knowledge-service
          predicates:
            - Path=/api/kb/**
          filters:
            - name: RequestRateLimiter
              args:
                key-resolver: "#{@userKeyResolver}"
                redis-rate-limiter.replenishRate: 20
                redis-rate-limiter.burstCapacity: 40
        - id: rag-ingest-service
          uri: lb://rag-ingest-service
          predicates:
            - Path=/api/ingest/**
          filters:
            - name: RequestRateLimiter
              args:
                key-resolver: "#{@userKeyResolver}"
                redis-rate-limiter.replenishRate: 10
                redis-rate-limiter.burstCapacity: 20
        - id: rag-platform-service
          uri: lb://rag-platform-service
          predicates:
            - Path=/api/platform/**
  data:
    redis:
      host: ${REDIS_HOST:127.0.0.1}
      port: ${REDIS_PORT:6379}
      password: ${REDIS_PASSWORD:}
      database: 3
      timeout: 2s

rag:
  gateway:
    fail-close: true
    auth-timeout-ms: 500
    # 可选：配置后额外注入 X-Gateway-Signature，内网服务可做不依赖 IP 的强校验
    sign-secret: ${RAG_GATEWAY_SIGN_SECRET:}
    public-paths:
      - /api/platform/auth/login
      - /api/platform/auth/refresh
      - /api/ai/health
      - /actuator/**
      - /doc.html
      - /v3/api-docs/**

management:
  endpoints:
    web:
      exposure:
        include: health,info,prometheus,metrics,gateway
  metrics:
    tags:
      application: ${spring.application.name}

logging:
  level:
    org.springframework.cloud.gateway: INFO
    com.fintech.rag: INFO
''')

# ============================================================================
# =======================  rag-platform-service  =============================
# ============================================================================
add("rag-platform-service/pom.xml", r'''
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>com.fintech.rag</groupId>
        <artifactId>rag-platform</artifactId>
        <version>1.0.0-SNAPSHOT</version>
    </parent>

    <artifactId>rag-platform-service</artifactId>
    <packaging>jar</packaging>
    <name>rag-platform-service</name>
    <description>平台治理：身份、应用凭证、ACL、配额、模型配置、审计</description>

    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-redis</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-cache</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-actuator</artifactId>
        </dependency>
        <dependency>
            <groupId>io.micrometer</groupId>
            <artifactId>micrometer-registry-prometheus</artifactId>
        </dependency>

        <dependency>
            <groupId>com.alibaba.cloud</groupId>
            <artifactId>spring-cloud-starter-alibaba-nacos-discovery</artifactId>
        </dependency>
        <dependency>
            <groupId>com.alibaba.cloud</groupId>
            <artifactId>spring-cloud-starter-alibaba-nacos-config</artifactId>
        </dependency>

        <dependency>
            <groupId>com.baomidou</groupId>
            <artifactId>mybatis-plus-spring-boot3-starter</artifactId>
        </dependency>
        <dependency>
            <groupId>com.mysql</groupId>
            <artifactId>mysql-connector-j</artifactId>
            <scope>runtime</scope>
        </dependency>

        <!-- JWT：0.12.x API -->
        <dependency>
            <groupId>io.jsonwebtoken</groupId>
            <artifactId>jjwt-api</artifactId>
        </dependency>
        <dependency>
            <groupId>io.jsonwebtoken</groupId>
            <artifactId>jjwt-impl</artifactId>
        </dependency>
        <dependency>
            <groupId>io.jsonwebtoken</groupId>
            <artifactId>jjwt-jackson</artifactId>
        </dependency>

        <dependency>
            <groupId>com.github.xiaoymin</groupId>
            <artifactId>knife4j-openapi3-jakarta-spring-boot-starter</artifactId>
        </dependency>

        <dependency>
            <groupId>com.fintech.rag</groupId>
            <artifactId>rag-common</artifactId>
        </dependency>
        <dependency>
            <groupId>com.fintech.rag</groupId>
            <artifactId>rag-api</artifactId>
        </dependency>
    </dependencies>

    <build>
        <finalName>rag-platform-service</finalName>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>
''')

PF = "rag-platform-service/src/main/java/com/fintech/rag/platform"

add(PF + "/PlatformApplication.java", r'''
package com.fintech.rag.platform;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.cache.annotation.EnableCaching;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;

/**
 * 平台治理服务启动类。
 *
 * <p>本服务被所有其它服务依赖（验签、授权、模型配置、脱敏规则），
 * 因此可用性优先级最高：必须多实例 + 本地缓存兜底。</p>
 *
 * @author rag-platform
 */
@SpringBootApplication(scanBasePackages = "com.fintech.rag.platform")
@EnableDiscoveryClient
@EnableCaching
@ConfigurationPropertiesScan("com.fintech.rag.platform")
@MapperScan("com.fintech.rag.platform.infra.persistence.mapper")
public class PlatformApplication {

    public static void main(String[] args) {
        SpringApplication.run(PlatformApplication.class, args);
    }
}
''')

# ---------------------------------------------------------------- 领域模型
add(PF + "/domain/model/AppCredential.java", r'''
package com.fintech.rag.platform.domain.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 内网应用凭证。
 *
 * @author rag-platform
 */
@Data
@TableName("t_app_credential")
public class AppCredential {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private Long tenantId;

    /** 应用 ID */
    private String appId;

    private String appName;

    /** AppSecret 密文（AES-256-GCM），禁止明文入库、禁止日志打印 */
    private String appSecretEnc;

    private String owner;

    private Integer qpsLimit;

    private Long dailyLimit;

    /** 调用方 IP 白名单，逗号分隔，空表示不限 */
    private String ipWhitelist;

    /** 1 启用 0 禁用 */
    private Integer status;

    private LocalDateTime expireAt;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;

    private String createBy;

    @TableLogic
    private Integer deleted;
}
''')

add(PF + "/domain/model/ModelConfig.java", r'''
package com.fintech.rag.platform.domain.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.math.BigDecimal;

/**
 * 模型配置（供 LlmRouter 动态路由）。
 *
 * @author rag-platform
 */
@Data
@TableName("t_model_config")
public class ModelConfig {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private Long tenantId;

    private String configCode;

    private String provider;

    private String baseUrl;

    /** API Key 密文 */
    private String apiKeyEnc;

    private String modelName;

    private BigDecimal temperature;

    private Integer maxTokens;

    /** 可处理的最大密级：1公开 2内部 3机密 */
    private Integer sensitiveLevel;

    private Integer priority;

    private Integer isDefault;

    private Integer status;
}
''')

add(PF + "/domain/model/SensitiveRule.java", r'''
package com.fintech.rag.platform.domain.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

/**
 * 敏感信息脱敏规则。
 *
 * @author rag-platform
 */
@Data
@TableName("t_sensitive_rule")
public class SensitiveRule {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private String ruleCode;

    private String ruleName;

    /** REGEX / DICT */
    private String ruleType;

    private String pattern;

    private String maskChar;

    private Integer keepPrefix;

    private Integer keepSuffix;

    /** MASK / BLOCK / WARN */
    private String action;

    private Integer status;
}
''')

add(PF + "/domain/model/AuditLog.java", r'''
package com.fintech.rag.platform.domain.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 审计日志。
 *
 * <p>金融合规要求：谁、何时、问了什么、召回了哪些文档，必须可追溯。
 * 本表写入量最大，生产建议按月分区 + 冷热分层。</p>
 *
 * @author rag-platform
 */
@Data
@TableName("t_audit_log")
public class AuditLog {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private Long tenantId;

    private String traceId;

    /** QUERY / RETRIEVAL / INGEST / KB_CHANGE / AUTH / CONFIG_CHANGE */
    private String eventType;

    private String requestSource;

    private String subjectType;

    private String subjectId;

    private String subjectName;

    private String clientIp;

    private String resource;

    private String kbIds;

    private String docIds;

    /** JSON 字符串，写入前必须已完成脱敏 */
    private String detail;

    private Integer result;

    private String errorCode;

    private Integer costMs;

    private LocalDateTime eventTime;
}
''')

# ---------------------------------------------------------------- Mapper
for name, entity in (("AppCredential", "AppCredential"), ("ModelConfig", "ModelConfig"),
                     ("SensitiveRule", "SensitiveRule"), ("AuditLog", "AuditLog")):
    add(PF + "/infra/persistence/mapper/" + name + "Mapper.java", r'''
package com.fintech.rag.platform.infra.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.fintech.rag.platform.domain.model.%ENTITY%;
import org.apache.ibatis.annotations.Mapper;

/**
 * %ENTITY% 数据访问。
 *
 * @author rag-platform
 */
@Mapper
public interface %NAME%Mapper extends BaseMapper<%ENTITY%> {
}
'''.replace("%ENTITY%", entity).replace("%NAME%", name))

# ---------------------------------------------------------------- 仓储
add(PF + "/infra/persistence/repository/AppCredentialRepository.java", r'''
package com.fintech.rag.platform.infra.persistence.repository;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.fintech.rag.platform.domain.model.AppCredential;
import com.fintech.rag.platform.infra.persistence.mapper.AppCredentialMapper;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 应用凭证仓储。
 *
 * <p><b>为什么必须加缓存：</b>验签是每个内网请求的必经之路，
 * 若每次都查库，platform 的数据库会在高并发下率先成为瓶颈。
 * 缓存 TTL 5 分钟，密钥轮换时主动失效。</p>
 *
 * @author rag-platform
 */
@Repository
public class AppCredentialRepository {

    private final AppCredentialMapper mapper;

    public AppCredentialRepository(AppCredentialMapper mapper) {
        this.mapper = mapper;
    }

    /** 按 appId 查询生效中的凭证（支持轮换期多条并存，返回最新的） */
    @Cacheable(cacheNames = "platform:app-cred", key = "#appId", unless = "#result == null")
    public AppCredential findActive(String appId) {
        List<AppCredential> list = mapper.selectList(Wrappers.<AppCredential>lambdaQuery()
                .eq(AppCredential::getAppId, appId)
                .eq(AppCredential::getStatus, 1)
                .and(w -> w.isNull(AppCredential::getExpireAt)
                        .or().gt(AppCredential::getExpireAt, LocalDateTime.now()))
                .orderByDesc(AppCredential::getId));
        return list.isEmpty() ? null : list.get(0);
    }

    /** 凭证变更后必须主动失效缓存，否则最长 5 分钟内旧密钥仍然可用 */
    @CacheEvict(cacheNames = "platform:app-cred", key = "#appId")
    public void evict(String appId) {
        // 由 @CacheEvict 完成清理，方法体空实现
    }

    public int save(AppCredential credential) {
        return mapper.insert(credential);
    }
}
''')

# ---------------------------------------------------------------- 安全
add(PF + "/infra/security/NonceReplayGuard.java", r'''
package com.fintech.rag.platform.infra.security;

import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import java.time.Duration;

/**
 * nonce 防重放守卫。
 *
 * <p>原理：同一 appId + nonce 在 TTL 窗口内只允许出现一次。
 * 即使攻击者截获了完整请求（含签名），也无法重复提交。</p>
 *
 * @author rag-platform
 */
@Component
public class NonceReplayGuard {

    private static final String KEY_PREFIX = "platform:nonce:";

    private final StringRedisTemplate redisTemplate;

    public NonceReplayGuard(StringRedisTemplate redisTemplate) {
        this.redisTemplate = redisTemplate;
    }

    /**
     * 占用 nonce。
     *
     * @return true 表示首次出现（放行），false 表示已重复（拒绝）
     */
    public boolean tryAcquire(String appId, String nonce, Duration ttl) {
        if (nonce == null || nonce.isBlank()) {
            return false;
        }
        Boolean ok = redisTemplate.opsForValue()
                .setIfAbsent(KEY_PREFIX + appId + ":" + nonce, "1", ttl);
        return Boolean.TRUE.equals(ok);
    }
}
''')

add(PF + "/infra/security/AppSignatureVerifier.java", r'''
package com.fintech.rag.platform.infra.security;

import com.fintech.rag.api.dto.platform.AppSignVerifyRequest;
import com.fintech.rag.api.dto.platform.AppSignVerifyResult;
import com.fintech.rag.common.util.AesCiphers;
import com.fintech.rag.common.util.HmacSignatures;
import com.fintech.rag.platform.config.PlatformSecurityProperties;
import com.fintech.rag.platform.domain.model.AppCredential;
import com.fintech.rag.platform.infra.persistence.repository.AppCredentialRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.time.Duration;

/**
 * 内网应用签名校验器 —— <b>第二套鉴权体系的判定内核</b>。
 *
 * <p>校验顺序（任一失败即拒绝，顺序不可调整）：</p>
 * <ol>
 *   <li>凭证存在且启用未过期</li>
 *   <li>时间戳在允许窗口内（默认 ±5 分钟）</li>
 *   <li>调用方 IP 在白名单内（若配置）</li>
 *   <li>nonce 未被使用过（防重放）</li>
 *   <li>HMAC-SHA256 签名匹配（常量时间比较）</li>
 * </ol>
 *
 * <p>为什么先查 nonce 再验签？可以在签名爆破前先挡掉重放请求；
 * 但要注意 nonce 已被占用而签名不匹配时，该 nonce 就废了——
 * 这是可接受的，因为合法调用方每次都会生成新 nonce。</p>
 *
 * @author rag-platform
 */
@Component
public class AppSignatureVerifier {

    private static final Logger log = LoggerFactory.getLogger(AppSignatureVerifier.class);

    private final AppCredentialRepository repository;
    private final NonceReplayGuard nonceReplayGuard;
    private final PlatformSecurityProperties properties;

    public AppSignatureVerifier(AppCredentialRepository repository,
                                NonceReplayGuard nonceReplayGuard,
                                PlatformSecurityProperties properties) {
        this.repository = repository;
        this.nonceReplayGuard = nonceReplayGuard;
        this.properties = properties;
    }

    public AppSignVerifyResult verify(AppSignVerifyRequest request) {
        AppCredential credential = repository.findActive(request.appId());
        if (credential == null) {
            log.warn("应用凭证不存在或已停用 appId={}", request.appId());
            return AppSignVerifyResult.rejected("应用不存在或已停用");
        }

        if (!withinTimeWindow(request.timestamp())) {
            return AppSignVerifyResult.rejected("请求时间戳超出允许窗口");
        }

        if (!ipAllowed(credential.getIpWhitelist(), request.clientIp())) {
            log.warn("调用方 IP 不在白名单 appId={} ip={}", request.appId(), request.clientIp());
            return AppSignVerifyResult.rejected("调用方 IP 不在白名单");
        }

        Duration nonceTtl = properties.getAppSign().getNonceTtl();
        if (!nonceReplayGuard.tryAcquire(request.appId(), request.nonce(), nonceTtl)) {
            return AppSignVerifyResult.rejected("请求已被重复提交");
        }

        String secret;
        try {
            secret = AesCiphers.decrypt(credential.getAppSecretEnc(), properties.getAesKey());
        } catch (Exception ex) {
            // 解密失败通常意味着 AES 密钥配置错误，属于启动期问题，必须告警
            log.error("AppSecret 解密失败 appId={}", request.appId(), ex);
            return AppSignVerifyResult.rejected("服务端密钥配置异常");
        }

        boolean matched = HmacSignatures.verify(
                secret,
                request.method(),
                request.path(),
                request.timestamp(),
                request.nonce(),
                request.bodySha256(),
                request.signature());

        if (!matched) {
            log.warn("应用签名不匹配 appId={} path={}", request.appId(), request.path());
            return AppSignVerifyResult.rejected("应用签名校验失败");
        }

        return new AppSignVerifyResult(true, null,
                credential.getAppId(), credential.getAppName(),
                credential.getQpsLimit(), credential.getDailyLimit(),
                credential.getIpWhitelist());
    }

    private boolean withinTimeWindow(String timestamp) {
        try {
            long ts = Long.parseLong(timestamp);
            long diff = Math.abs(System.currentTimeMillis() - ts);
            return diff <= properties.getAppSign().getTimestampWindow().toMillis();
        } catch (NumberFormatException ex) {
            return false;
        }
    }

    private boolean ipAllowed(String whitelist, String clientIp) {
        if (whitelist == null || whitelist.isBlank()) {
            return true;
        }
        if (clientIp == null || clientIp.isBlank()) {
            return false;
        }
        for (String pattern : whitelist.split(",")) {
            String trimmed = pattern.trim();
            if (trimmed.isEmpty()) {
                continue;
            }
            if (trimmed.endsWith("*")) {
                if (clientIp.startsWith(trimmed.substring(0, trimmed.length() - 1))) {
                    return true;
                }
            } else if (trimmed.equals(clientIp)) {
                return true;
            }
        }
        return false;
    }
}
''')

add(PF + "/infra/security/JwtTokenService.java", r'''
package com.fintech.rag.platform.infra.security;

import com.fintech.rag.api.dto.platform.UserTokenPayload;
import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import com.fintech.rag.platform.config.PlatformSecurityProperties;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Date;
import java.util.List;

/**
 * 用户令牌服务（JWT，HS256）。
 *
 * <p><b>JJWT 0.12.x API 注意事项：</b>{@code parserBuilder()} 已废弃，
 * 必须用 {@code Jwts.parser().verifyWith(key).build()}；HS256 的密钥长度
 * 必须 ≥ 32 字节，否则启动期即会抛 WeakKeyException。</p>
 *
 * @author rag-platform
 */
@Component
public class JwtTokenService {

    private static final String CLAIM_NAME = "name";
    private static final String CLAIM_DEPT = "deptId";
    private static final String CLAIM_SECRET_LEVEL = "secretLevel";
    private static final String CLAIM_ROLES = "roles";

    private final SecretKey key;
    private final PlatformSecurityProperties properties;

    public JwtTokenService(PlatformSecurityProperties properties) {
        this.properties = properties;
        byte[] secretBytes = properties.getJwt().getSecret().getBytes(StandardCharsets.UTF_8);
        if (secretBytes.length < 32) {
            throw new IllegalStateException("JWT 密钥长度不足 32 字节，HS256 不允许弱密钥，请检查 rag.security.jwt.secret 配置");
        }
        this.key = Keys.hmacShaKeyFor(secretBytes);
    }

    /** 签发访问令牌 */
    public String issueAccessToken(UserTokenPayload payload) {
        return issue(payload, properties.getJwt().getAccessTokenTtl().toMillis());
    }

    /** 签发刷新令牌 */
    public String issueRefreshToken(UserTokenPayload payload) {
        return issue(payload, properties.getJwt().getRefreshTokenTtl().toMillis());
    }

    private String issue(UserTokenPayload payload, long ttlMillis) {
        Instant now = Instant.now();
        return Jwts.builder()
                .subject(payload.userId())
                .issuer(properties.getJwt().getIssuer())
                .claim(CLAIM_NAME, payload.realName())
                .claim(CLAIM_DEPT, payload.deptId())
                .claim(CLAIM_SECRET_LEVEL, payload.secretLevel())
                .claim(CLAIM_ROLES, payload.roles())
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plusMillis(ttlMillis)))
                .signWith(key)
                .compact();
    }

    /**
     * 解析并校验令牌。
     *
     * @throws BizException 令牌非法或已过期
     */
    @SuppressWarnings("unchecked")
    public UserTokenPayload parse(String token) {
        if (token == null || token.isBlank()) {
            throw BizException.of(ErrorCode.TOKEN_INVALID);
        }
        try {
            Claims claims = Jwts.parser()
                    .verifyWith(key)
                    .requireIssuer(properties.getJwt().getIssuer())
                    .build()
                    .parseSignedClaims(token)
                    .getPayload();

            return new UserTokenPayload(
                    claims.getSubject(),
                    claims.get(CLAIM_NAME, String.class),
                    claims.get(CLAIM_DEPT, Long.class),
                    claims.get(CLAIM_SECRET_LEVEL, Integer.class),
                    claims.get(CLAIM_ROLES, List.class));
        } catch (JwtException | IllegalArgumentException ex) {
            throw BizException.of(ErrorCode.TOKEN_INVALID);
        }
    }
}
''')

add(PF + "/config/PlatformSecurityProperties.java", r'''
package com.fintech.rag.platform.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Duration;

/**
 * 平台安全配置。
 *
 * @author rag-platform
 */
@ConfigurationProperties(prefix = "rag.security")
public class PlatformSecurityProperties {

    /** AES-256 主密钥（Base64，32 字节），用于加解密 AppSecret / API Key */
    private String aesKey;

    /** DMZ 网关网段白名单，用于校验「携带来源标识的请求是否真的来自网关」 */
    private java.util.List<String> trustedGatewayCidrs = new java.util.ArrayList<>();

    private Jwt jwt = new Jwt();

    private AppSign appSign = new AppSign();

    public static class Jwt {

        private String issuer = "rag-platform";

        private String secret;

        private Duration accessTokenTtl = Duration.ofHours(2);

        private Duration refreshTokenTtl = Duration.ofHours(8);

        public String getIssuer() {
            return issuer;
        }

        public void setIssuer(String issuer) {
            this.issuer = issuer;
        }

        public String getSecret() {
            return secret;
        }

        public void setSecret(String secret) {
            this.secret = secret;
        }

        public Duration getAccessTokenTtl() {
            return accessTokenTtl;
        }

        public void setAccessTokenTtl(Duration accessTokenTtl) {
            this.accessTokenTtl = accessTokenTtl;
        }

        public Duration getRefreshTokenTtl() {
            return refreshTokenTtl;
        }

        public void setRefreshTokenTtl(Duration refreshTokenTtl) {
            this.refreshTokenTtl = refreshTokenTtl;
        }
    }

    public static class AppSign {

        /** 允许的时间戳偏差窗口 */
        private Duration timestampWindow = Duration.ofMinutes(5);

        /** nonce 记忆时长，应 ≥ 时间戳窗口，否则窗口内仍可重放 */
        private Duration nonceTtl = Duration.ofMinutes(10);

        public Duration getTimestampWindow() {
            return timestampWindow;
        }

        public void setTimestampWindow(Duration timestampWindow) {
            this.timestampWindow = timestampWindow;
        }

        public Duration getNonceTtl() {
            return nonceTtl;
        }

        public void setNonceTtl(Duration nonceTtl) {
            this.nonceTtl = nonceTtl;
        }
    }

    public String getAesKey() {
        return aesKey;
    }

    public void setAesKey(String aesKey) {
        this.aesKey = aesKey;
    }

    public java.util.List<String> getTrustedGatewayCidrs() {
        return trustedGatewayCidrs;
    }

    public void setTrustedGatewayCidrs(java.util.List<String> trustedGatewayCidrs) {
        this.trustedGatewayCidrs = trustedGatewayCidrs;
    }

    public Jwt getJwt() {
        return jwt;
    }

    public void setJwt(Jwt jwt) {
        this.jwt = jwt;
    }

    public AppSign getAppSign() {
        return appSign;
    }

    public void setAppSign(AppSign appSign) {
        this.appSign = appSign;
    }
}
''')

# ---------------------------------------------------------------- 两套鉴权拦截器
add(PF + "/infra/interceptor/RequestSourceAuthInterceptor.java", r'''
package com.fintech.rag.platform.infra.interceptor;

import com.fintech.rag.api.dto.common.SubjectType;
import com.fintech.rag.api.dto.platform.AppSignVerifyRequest;
import com.fintech.rag.api.dto.platform.AppSignVerifyResult;
import com.fintech.rag.api.dto.platform.UserTokenPayload;
import com.fintech.rag.common.constant.RagHeaders;
import com.fintech.rag.common.context.RequestContext;
import com.fintech.rag.common.context.RequestSource;
import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import com.fintech.rag.common.util.HmacSignatures;
import com.fintech.rag.platform.config.PlatformSecurityProperties;
import com.fintech.rag.platform.infra.security.AppSignatureVerifier;
import com.fintech.rag.platform.infra.security.JwtTokenService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpMethod;
import org.springframework.stereotype.Component;
import org.springframework.util.AntPathMatcher;
import org.springframework.web.servlet.HandlerInterceptor;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Set;

/**
 * 请求来源识别与两套鉴权分流拦截器 —— <b>本方案的鉴权核心</b>。
 *
 * <p>分流规则（唯一依据是 {@code X-Request-Source}）：</p>
 * <ul>
 *   <li>携带 {@code DMZ_GATEWAY} → 外网用户流量 → 校验用户 JWT；
 *       <b>且必须先校验来源 IP 属于网关网段</b>，否则内网调用方伪造该头即可绕过应用签名。</li>
 *   <li>不携带 → 内网应用流量 → 校验 AppKey + HMAC 签名 + 时间戳 + nonce。</li>
 * </ul>
 *
 * <p><b>反向拦截（防伪造的关键）</b>：内网网段发来的请求若携带了来源标识，一律 403。
 * 这一条比 IP 白名单更重要——白名单可能配置疏漏，反向拦截是兜底。</p>
 *
 * @author rag-platform
 */
@Component
public class RequestSourceAuthInterceptor implements HandlerInterceptor {

    private static final Logger log = LoggerFactory.getLogger(RequestSourceAuthInterceptor.class);
    private static final AntPathMatcher MATCHER = new AntPathMatcher();

    /** 完全放开的路径：不需要任何身份。务必最小化，login 需自行叠加验证码/风控 */
    private static final Set<String> PUBLIC_PATHS = Set.of(
            "/api/platform/auth/login",
            "/api/platform/auth/refresh",
            "/actuator/**",
            "/doc.html",
            "/v3/api-docs/**",
            "/error"
    );

    /** 仅允许网关访问的路径：无需应用签名，但必须来自可信网关网段 */
    private static final Set<String> GATEWAY_ONLY_PATHS = Set.of(
            "/api/platform/auth/verify"
    );

    private final JwtTokenService jwtTokenService;
    private final AppSignatureVerifier appSignatureVerifier;
    private final PlatformSecurityProperties properties;

    public RequestSourceAuthInterceptor(JwtTokenService jwtTokenService,
                                        AppSignatureVerifier appSignatureVerifier,
                                        PlatformSecurityProperties properties) {
        this.jwtTokenService = jwtTokenService;
        this.appSignatureVerifier = appSignatureVerifier;
        this.properties = properties;
    }

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
        if (HttpMethod.OPTIONS.matches(request.getMethod())) {
            return true;
        }

        String path = request.getRequestURI();
        if (isPublic(path)) {
            return true;
        }

        RequestContext.Snapshot snapshot = RequestContext.get();
        String clientIp = snapshot == null ? request.getRemoteAddr() : snapshot.clientIp();
        String sourceHeader = request.getHeader(RagHeaders.REQUEST_SOURCE);

        // ---------- 反向拦截：内网请求不得携带来源标识 ----------
        if (sourceHeader == null && request.getHeader(RagHeaders.GATEWAY_SIGNATURE) != null) {
            log.warn("内网请求携带网关签名，判定为伪造 ip={} path={}", clientIp, path);
            throw BizException.of(ErrorCode.REQUEST_SOURCE_FORGED);
        }

        if (RequestSource.DMZ_HEADER_VALUE.equals(sourceHeader)) {
            return handleDmzWeb(request, response, snapshot, clientIp, path);
        }
        return handleInnerApp(request, response, snapshot, clientIp, path);
    }

    // ---------------------------------------------------------------- 外网用户流量
    private boolean handleDmzWeb(HttpServletRequest request, HttpServletResponse response,
                                 RequestContext.Snapshot snapshot, String clientIp, String path) {
        // 第一道：来源 IP 必须属于可信网关网段
        if (!isTrustedGateway(clientIp)) {
            log.warn("来源标识被伪造：ip 不在网关网段 ip={} path={}", clientIp, path);
            throw BizException.of(ErrorCode.REQUEST_SOURCE_FORGED);
        }

        // 第二道（可选）：网关签名验签，适合容器环境（IP 会漂移）
        String gatewaySignature = request.getHeader(RagHeaders.GATEWAY_SIGNATURE);
        if (properties.getTrustedGatewayCidrs().isEmpty() && gatewaySignature == null) {
            throw BizException.of(ErrorCode.REQUEST_SOURCE_FORGED);
        }

        // 网关已完成用户鉴权，此处按需二次解析（例如 GATEWAY_ONLY_PATHS）
        String userToken = request.getHeader(RagHeaders.USER_TOKEN);
        if (GATEWAY_ONLY_PATHS.stream().anyMatch(p -> MATCHER.match(p, path))) {
            // /auth/verify 就是拿来校验令牌的，直接解析
            UserTokenPayload payload = jwtTokenService.parse(userToken);
            fillSubject(snapshot, payload.userId(), payload.realName());
            request.setAttribute("USER_PAYLOAD", payload);
            return true;
        }

        // 常规业务路径：信任网关透传的用户身份头，但做非空校验
        String userId = request.getHeader(RagHeaders.USER_ID);
        if (userId == null || userId.isBlank()) {
            throw BizException.of(ErrorCode.TOKEN_INVALID, "缺少用户身份信息");
        }
        fillSubject(snapshot, userId, request.getHeader(RagHeaders.USER_NAME));
        return true;
    }

    // ---------------------------------------------------------------- 内网应用流量
    private boolean handleInnerApp(HttpServletRequest request, HttpServletResponse response,
                                   RequestContext.Snapshot snapshot, String clientIp, String path) {
        String appId = request.getHeader(RagHeaders.APP_ID);
        String timestamp = request.getHeader(RagHeaders.APP_TIMESTAMP);
        String nonce = request.getHeader(RagHeaders.APP_NONCE);
        String signature = request.getHeader(RagHeaders.APP_SIGNATURE);

        if (appId == null || appId.isBlank() || signature == null || signature.isBlank()) {
            throw BizException.of(ErrorCode.APP_SIGN_INVALID, "缺少应用身份信息");
        }

        String bodySha256 = HmacSignatures.sha256Hex(readBody(request));
        AppSignVerifyResult result = appSignatureVerifier.verify(new AppSignVerifyRequest(
                appId, request.getMethod(), path, timestamp, nonce, signature, bodySha256, clientIp));

        if (!result.valid()) {
            throw BizException.of(ErrorCode.APP_SIGN_INVALID, result.reason());
        }

        fillSubject(snapshot, appId, result.appName());
        request.setAttribute("APP_CREDENTIAL", result);
        return true;
    }

    private String readBody(HttpServletRequest request) {
        Object cached = request.getAttribute("CACHED_BODY");
        return cached == null ? "" : cached.toString();
    }

    private void fillSubject(RequestContext.Snapshot snapshot, String subjectId, String subjectName) {
        if (snapshot == null) {
            // 兜底：正常流程一定会被 RequestContextFilter 初始化
            RequestContext.set(new RequestContext.Snapshot(
                    RequestSource.SF_INNER_APP, SubjectType.APP.name(), subjectId, subjectName,
                    null, null, null));
            return;
        }
        String subjectType = snapshot.source() == RequestSource.DMZ_WEB
                ? SubjectType.USER.name() : SubjectType.APP.name();
        RequestContext.set(snapshot.withSubject(subjectType, subjectId, subjectName));
    }

    private boolean isPublic(String path) {
        return PUBLIC_PATHS.stream().anyMatch(p -> MATCHER.match(p, path));
    }

    private boolean isTrustedGateway(String ip) {
        List<String> cidrs = properties.getTrustedGatewayCidrs();
        if (cidrs == null || cidrs.isEmpty()) {
            return false;
        }
        return cidrs.stream().anyMatch(cidr -> matchCidr(cidr, ip));
    }

    /** 简化版 CIDR 匹配，仅支持 IPv4 的 /x 前缀；生产建议用 IPAddressMatcher */
    private boolean matchCidr(String cidr, String ip) {
        if (cidr == null || cidr.isBlank() || ip == null) {
            return false;
        }
        int slash = cidr.indexOf('/');
        if (slash < 0) {
            return cidr.equals(ip);
        }
        try {
            int prefix = Integer.parseInt(cidr.substring(slash + 1));
            long mask = prefix == 0 ? 0L : (0xFFFFFFFFL << (32 - prefix)) & 0xFFFFFFFFL;
            return (toLong(cidr.substring(0, slash)) & mask) == (toLong(ip) & mask);
        } catch (Exception ex) {
            return false;
        }
    }

    private long toLong(String ip) {
        String[] parts = ip.split("\\.");
        long value = 0;
        for (String part : parts) {
            value = (value << 8) | Integer.parseInt(part);
        }
        return value;
    }

    /** 供需要原始 body 的签名校验使用（配合 BodyCachingFilter） */
    public static byte[] bodyBytes(String body) {
        return body == null ? new byte[0] : body.getBytes(StandardCharsets.UTF_8);
    }
}
''')

add(PF + "/infra/interceptor/BodyCachingFilter.java", r'''
package com.fintech.rag.platform.infra.interceptor;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.core.Ordered;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;
import org.springframework.web.util.ContentCachingRequestWrapper;

import java.io.IOException;
import java.nio.charset.StandardCharsets;

/**
 * 请求体缓存过滤器。
 *
 * <p>应用签名需要原始请求体参与校验，而 Servlet 的 InputStream 只能读一次。
 * 用 {@link ContentCachingRequestWrapper} 缓存后，拦截器与业务代码都能重复读取。</p>
 *
 * <p>注意：必须在拦截器之前执行，且缓存体在请求结束后应尽快释放，
 * 大文件上传（文档入库）路径建议跳过本过滤器以节省内存。</p>
 *
 * @author rag-platform
 */
@Component
public class BodyCachingFilter extends OncePerRequestFilter implements Ordered {

    private static final String CACHE_ATTRIBUTE = "CACHED_BODY";

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        ContentCachingRequestWrapper wrapper = new ContentCachingRequestWrapper(request);
        filterChain.doFilter(wrapper, response);
        byte[] body = wrapper.getContentAsByteArray();
        if (body.length > 0) {
            wrapper.setAttribute(CACHE_ATTRIBUTE, new String(body, StandardCharsets.UTF_8));
        }
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        // 大文件上传不缓存，避免把 200MB 文档读进堆内存
        return request.getRequestURI().startsWith("/api/ingest/upload");
    }

    @Override
    public int getOrder() {
        return Ordered.HIGHEST_PRECEDENCE + 20;
    }
}
''')

add(PF + "/config/WebMvcConfig.java", r'''
package com.fintech.rag.platform.config;

import com.fintech.rag.platform.infra.interceptor.RequestSourceAuthInterceptor;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * MVC 配置：注册鉴权拦截器。
 *
 * @author rag-platform
 */
@Configuration
public class WebMvcConfig implements WebMvcConfigurer {

    private final RequestSourceAuthInterceptor authSourceInterceptor;

    public WebMvcConfig(RequestSourceAuthInterceptor authSourceInterceptor) {
        this.authSourceInterceptor = authSourceInterceptor;
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(authSourceInterceptor)
                .addPathPatterns("/api/**")
                .excludePathPatterns("/actuator/**", "/doc.html", "/v3/api-docs/**");
    }
}
''')

# ---------------------------------------------------------------- 应用层
add(PF + "/app/service/AuthAppService.java", r'''
package com.fintech.rag.platform.app.service;

import com.fintech.rag.api.dto.platform.UserTokenPayload;
import com.fintech.rag.platform.infra.security.JwtTokenService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * 认证应用服务。
 *
 * <p><b>待对接项：</b>当前为骨架实现，用户校验走内存桩。
 * 落地时替换为「统一身份源（OIDC/CAS/LDAP）校验 + 本地用户/角色表补充授权信息」。</p>
 *
 * @author rag-platform
 */
@Service
public class AuthAppService {

    private static final Logger log = LoggerFactory.getLogger(AuthAppService.class);

    private final JwtTokenService jwtTokenService;

    public AuthAppService(JwtTokenService jwtTokenService) {
        this.jwtTokenService = jwtTokenService;
    }

    /**
     * 登录。
     *
     * @return 访问令牌
     */
    public String login(String username, String password) {
        // TODO 对接统一身份源；当前桩实现仅用于链路联调，上线前必须替换
        if (username == null || username.isBlank()) {
            throw new IllegalArgumentException("用户名不能为空");
        }
        log.info("用户登录成功 username={}", username);

        UserTokenPayload payload = new UserTokenPayload(
                username, username, 1L, 2, List.of("CREDIT_OFFICER"));
        return jwtTokenService.issueAccessToken(payload);
    }

    /** 刷新令牌，返回新的访问令牌 */
    public String refresh(String refreshToken) {
        UserTokenPayload payload = jwtTokenService.parse(refreshToken);
        return jwtTokenService.issueAccessToken(payload);
    }

    /** 校验用户令牌（供网关调用） */
    public UserTokenPayload verify(String token) {
        return jwtTokenService.parse(token);
    }

    /** 签发访问令牌（供登录成功后使用） */
    public String issueAccessToken(UserTokenPayload payload) {
        return jwtTokenService.issueAccessToken(payload);
    }
}
''')

add(PF + "/app/service/AppCredentialAppService.java", r'''
package com.fintech.rag.platform.app.service;

import com.fintech.rag.api.dto.platform.AppSignVerifyRequest;
import com.fintech.rag.api.dto.platform.AppSignVerifyResult;
import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import com.fintech.rag.common.util.AesCiphers;
import com.fintech.rag.platform.config.PlatformSecurityProperties;
import com.fintech.rag.platform.domain.model.AppCredential;
import com.fintech.rag.platform.infra.persistence.repository.AppCredentialRepository;
import com.fintech.rag.platform.infra.security.AppSignatureVerifier;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.security.SecureRandom;
import java.time.LocalDateTime;
import java.util.Base64;

/**
 * 应用凭证应用服务。
 *
 * @author rag-platform
 */
@Service
public class AppCredentialAppService {

    private static final Logger log = LoggerFactory.getLogger(AppCredentialAppService.class);
    private static final SecureRandom RANDOM = new SecureRandom();

    private final AppSignatureVerifier verifier;
    private final AppCredentialRepository repository;
    private final PlatformSecurityProperties properties;

    public AppCredentialAppService(AppSignatureVerifier verifier,
                                   AppCredentialRepository repository,
                                   PlatformSecurityProperties properties) {
        this.verifier = verifier;
        this.repository = repository;
        this.properties = properties;
    }

    /** 验签（供各服务调用） */
    public AppSignVerifyResult verify(AppSignVerifyRequest request) {
        return verifier.verify(request);
    }

    /**
     * 创建应用凭证。
     *
     * <p><b>安全约定</b>：AppSecret 只在创建响应中返回一次明文，之后只存密文，
     * 任何接口都不允许再回显。</p>
     *
     * @return AppSecret 明文（仅此一次）
     */
    @Transactional(rollbackFor = Exception.class)
    public String create(String appId, String appName, String owner, Integer qpsLimit, Long dailyLimit) {
        String plainSecret = generateSecret();
        AppCredential credential = new AppCredential();
        credential.setTenantId(0L);
        credential.setAppId(appId);
        credential.setAppName(appName);
        credential.setAppSecretEnc(AesCiphers.encrypt(plainSecret, properties.getAesKey()));
        credential.setOwner(owner);
        credential.setQpsLimit(qpsLimit == null ? 20 : qpsLimit);
        credential.setDailyLimit(dailyLimit == null ? 100000L : dailyLimit);
        credential.setStatus(1);
        credential.setDeleted(0);
        repository.save(credential);
        log.info("创建应用凭证 appId={}", appId);
        return plainSecret;
    }

    /**
     * 密钥轮换：新密钥立即生效，旧凭证设置过期时间，形成并行窗口。
     *
     * @return 新的 AppSecret 明文（仅此一次）
     */
    @Transactional(rollbackFor = Exception.class)
    public String rotate(String appId, int graceHours) {
        AppCredential old = repository.findActive(appId);
        if (old == null) {
            throw BizException.of(ErrorCode.APP_DISABLED);
        }

        String plainSecret = generateSecret();
        old.setExpireAt(LocalDateTime.now().plusHours(graceHours));
        old.setStatus(1);
        repository.save(old);

        AppCredential fresh = new AppCredential();
        fresh.setTenantId(old.getTenantId());
        fresh.setAppId(appId);
        fresh.setAppName(old.getAppName());
        fresh.setAppSecretEnc(AesCiphers.encrypt(plainSecret, properties.getAesKey()));
        fresh.setOwner(old.getOwner());
        fresh.setQpsLimit(old.getQpsLimit());
        fresh.setDailyLimit(old.getDailyLimit());
        fresh.setIpWhitelist(old.getIpWhitelist());
        fresh.setStatus(1);
        fresh.setDeleted(0);
        repository.save(fresh);

        // 必须主动失效缓存，否则旧密钥在新实例上仍然可用
        repository.evict(appId);
        log.info("应用密钥轮换完成 appId={} graceHours={}", appId, graceHours);
        return plainSecret;
    }

    private String generateSecret() {
        byte[] bytes = new byte[32];
        RANDOM.nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }
}
''')

# ---------------------------------------------------------------- 接口层
add(PF + "/api/controller/AuthController.java", r'''
package com.fintech.rag.platform.api.controller;

import com.fintech.rag.api.dto.platform.UserTokenPayload;
import com.fintech.rag.common.constant.RagHeaders;
import com.fintech.rag.common.core.R;
import com.fintech.rag.platform.app.service.AuthAppService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 认证接口。
 *
 * <p>{@code /login} 与 {@code /refresh} 是网关白名单里唯一放开的外网入口，
 * 必须在网关或本层叠加图形验证码 / 频率限制 / 异常登录锁定。</p>
 *
 * @author rag-platform
 */
@RestController
@RequestMapping("/api/platform/auth")
public class AuthController {

    private final AuthAppService authAppService;

    public AuthController(AuthAppService authAppService) {
        this.authAppService = authAppService;
    }

    @PostMapping("/login")
    public R<Map<String, String>> login(@RequestParam String username,
                                        @RequestParam String password) {
        String token = authAppService.login(username, password);
        return R.ok(Map.of("accessToken", token));
    }

    @PostMapping("/refresh")
    public R<Map<String, String>> refresh(HttpServletRequest request) {
        String refreshToken = request.getHeader(RagHeaders.USER_TOKEN);
        return R.ok(Map.of("accessToken", authAppService.refresh(refreshToken)));
    }

    /**
     * 令牌校验（仅允许网关调用，走 GATEWAY_ONLY_PATHS 白名单 + 网关网段限制）。
     */
    @PostMapping("/verify")
    public R<UserTokenPayload> verify(HttpServletRequest request) {
        Object payload = request.getAttribute("USER_PAYLOAD");
        if (payload instanceof UserTokenPayload userTokenPayload) {
            return R.ok(userTokenPayload);
        }
        return R.ok(authAppService.verify(request.getHeader(RagHeaders.USER_TOKEN)));
    }
}
''')

add(PF + "/api/controller/AppCredentialController.java", r'''
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
''')

add(PF + "/api/controller/AuditLogController.java", r'''
package com.fintech.rag.platform.api.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.fintech.rag.api.dto.platform.AuditLogDTO;
import com.fintech.rag.common.core.PageResult;
import com.fintech.rag.common.core.R;
import com.fintech.rag.platform.domain.model.AuditLog;
import com.fintech.rag.platform.infra.persistence.mapper.AuditLogMapper;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.List;

/**
 * 审计日志接口。
 *
 * <p>写入侧：各服务异步批量上报，<b>失败不得阻塞主链路</b>。
 * 生产建议改为「先落 RocketMQ，本服务消费入库」，避免上报流量直接压到数据库。</p>
 *
 * @author rag-platform
 */
@RestController
@RequestMapping("/api/platform/audit")
public class AuditLogController {

    private final AuditLogMapper auditLogMapper;

    public AuditLogController(AuditLogMapper auditLogMapper) {
        this.auditLogMapper = auditLogMapper;
    }

    @PostMapping("/batch")
    public R<Void> batchSave(@RequestBody List<AuditLogDTO> logs) {
        if (logs == null || logs.isEmpty()) {
            return R.ok();
        }
        List<AuditLog> entities = new ArrayList<>(logs.size());
        for (AuditLogDTO dto : logs) {
            AuditLog entity = new AuditLog();
            entity.setTenantId(0L);
            entity.setTraceId(dto.traceId());
            entity.setEventType(dto.eventType());
            entity.setRequestSource(dto.requestSource());
            entity.setSubjectType(dto.subjectType());
            entity.setSubjectId(dto.subjectId());
            entity.setSubjectName(dto.subjectName());
            entity.setClientIp(dto.clientIp());
            entity.setResource(dto.resource());
            entity.setKbIds(dto.kbIds() == null ? null : dto.kbIds().toString());
            entity.setDocIds(dto.docIds() == null ? null : dto.docIds().toString());
            entity.setDetail(dto.detailJson());
            entity.setResult(dto.result() == null ? 1 : dto.result());
            entity.setErrorCode(dto.errorCode());
            entity.setCostMs(dto.costMs());
            entity.setEventTime(dto.eventTime() == null
                    ? LocalDateTime.now()
                    : LocalDateTime.ofInstant(Instant.ofEpochMilli(dto.eventTime()), ZoneId.systemDefault()));
            entities.add(entity);
        }
        entities.forEach(auditLogMapper::insert);
        return R.ok();
    }

    @GetMapping
    public R<PageResult<AuditLog>> page(@RequestParam(defaultValue = "1") long pageNum,
                                        @RequestParam(defaultValue = "20") long pageSize,
                                        @RequestParam(required = false) String subjectId,
                                        @RequestParam(required = false) String eventType) {
        Page<AuditLog> page = new Page<>(pageNum, pageSize);
        IPage<AuditLog> result = auditLogMapper.selectPage(page,
                Wrappers.<AuditLog>lambdaQuery()
                        .eq(subjectId != null, AuditLog::getSubjectId, subjectId)
                        .eq(eventType != null, AuditLog::getEventType, eventType)
                        .orderByDesc(AuditLog::getEventTime));
        return R.ok(PageResult.of(result.getRecords(), pageNum, pageSize, result.getTotal()));
    }
}
''')

add(PF + "/api/controller/ConfigController.java", r'''
package com.fintech.rag.platform.api.controller;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.fintech.rag.api.dto.platform.ModelConfigDTO;
import com.fintech.rag.api.dto.platform.SensitiveRuleDTO;
import com.fintech.rag.common.core.R;
import com.fintech.rag.common.util.AesCiphers;
import com.fintech.rag.platform.config.PlatformSecurityProperties;
import com.fintech.rag.platform.domain.model.ModelConfig;
import com.fintech.rag.platform.domain.model.SensitiveRule;
import com.fintech.rag.platform.infra.persistence.mapper.ModelConfigMapper;
import com.fintech.rag.platform.infra.persistence.mapper.SensitiveRuleMapper;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 配置类接口：模型配置与脱敏规则。
 *
 * <p>这两个配置是 rag-chat-service 的「运行时依赖」，必须本地缓存 + 定时刷新，
 * 不能每次问答都远程调用。</p>
 *
 * @author rag-platform
 */
@RestController
@RequestMapping("/api/platform")
public class ConfigController {

    private final ModelConfigMapper modelConfigMapper;
    private final SensitiveRuleMapper sensitiveRuleMapper;
    private final PlatformSecurityProperties securityProperties;

    public ConfigController(ModelConfigMapper modelConfigMapper,
                            SensitiveRuleMapper sensitiveRuleMapper,
                            PlatformSecurityProperties securityProperties) {
        this.modelConfigMapper = modelConfigMapper;
        this.sensitiveRuleMapper = sensitiveRuleMapper;
        this.securityProperties = securityProperties;
    }

    /**
     * 模型配置列表（按优先级升序，供 LlmRouter 做敏感度分流）。
     */
    @GetMapping("/model-configs")
    public R<List<ModelConfigDTO>> listModelConfigs() {
        List<ModelConfig> configs = modelConfigMapper.selectList(
                Wrappers.<ModelConfig>lambdaQuery()
                        .eq(ModelConfig::getStatus, 1)
                        .orderByAsc(ModelConfig::getPriority));

        List<ModelConfigDTO> result = configs.stream().map(c -> new ModelConfigDTO(
                c.getConfigCode(),
                c.getProvider(),
                c.getBaseUrl(),
                decryptQuietly(c.getApiKeyEnc()),
                c.getModelName(),
                c.getTemperature() == null ? null : c.getTemperature().doubleValue(),
                c.getMaxTokens(),
                c.getSensitiveLevel(),
                c.getPriority(),
                c.getIsDefault() != null && c.getIsDefault() == 1
        )).toList();
        return R.ok(result);
    }

    /** 脱敏规则列表 */
    @GetMapping("/sensitive-rules")
    public R<List<SensitiveRuleDTO>> listSensitiveRules() {
        List<SensitiveRule> rules = sensitiveRuleMapper.selectList(
                Wrappers.<SensitiveRule>lambdaQuery().eq(SensitiveRule::getStatus, 1));

        List<SensitiveRuleDTO> result = rules.stream().map(r -> new SensitiveRuleDTO(
                r.getRuleCode(), r.getRuleName(), r.getRuleType(), r.getPattern(),
                r.getMaskChar(), r.getKeepPrefix(), r.getKeepSuffix(), r.getAction()
        )).toList();
        return R.ok(result);
    }

    private String decryptQuietly(String cipher) {
        if (cipher == null || cipher.isBlank()) {
            return null;
        }
        try {
            return AesCiphers.decrypt(cipher, securityProperties.getAesKey());
        } catch (Exception ex) {
            // 单条配置解密失败不应导致整个列表接口 500
            return null;
        }
    }
}
''')

add("rag-platform-service/src/main/resources/application.yml", r'''
server:
  port: 8081
  shutdown: graceful
  tomcat:
    threads:
      max: 400

spring:
  application:
    name: rag-platform-service
  profiles:
    active: dev
  config:
    import:
      - optional:nacos:rag-platform-service.yaml
      - optional:nacos:rag-common.yaml
  cloud:
    nacos:
      server-addr: ${NACOS_ADDR:127.0.0.1:8848}
      username: ${NACOS_USERNAME:nacos}
      password: ${NACOS_PASSWORD:nacos}
      discovery:
        namespace: ${NACOS_NAMESPACE:rag}
        group: RAG_GROUP
      config:
        namespace: ${NACOS_NAMESPACE:rag}
        group: RAG_GROUP
        file-extension: yaml
  datasource:
    driver-class-name: com.mysql.cj.jdbc.Driver
    url: jdbc:mysql://${MYSQL_HOST:127.0.0.1}:${MYSQL_PORT:3306}/rag_platform?useUnicode=true&characterEncoding=utf8&serverTimezone=Asia/Shanghai&rewriteBatchedStatements=true
    username: ${MYSQL_USERNAME:rag}
    password: ${MYSQL_PASSWORD:rag123456}
    hikari:
      maximum-pool-size: 20
      minimum-idle: 5
      connection-timeout: 3000
  data:
    redis:
      host: ${REDIS_HOST:127.0.0.1}
      port: ${REDIS_PORT:6379}
      password: ${REDIS_PASSWORD:}
      database: 0
  cache:
    type: redis
    redis:
      time-to-live: 5m
      # 不缓存 null，避免「应用不存在」被缓存后新建凭证不可用
      cache-null-values: false

mybatis-plus:
  configuration:
    map-underscore-to-camel-case: true
  global-config:
    db-config:
      logic-delete-field: deleted
      logic-delete-value: 1
      logic-not-delete-value: 0

rag:
  security:
    # AES-256 主密钥（Base64 32 字节）。生产必须由 KMS 或环境变量注入，禁止入库、禁止提交仓库
    aes-key: ${RAG_AES_KEY:}
    jwt:
      issuer: rag-platform
      secret: ${RAG_JWT_SECRET:}
      access-token-ttl: 2h
      refresh-token-ttl: 8h
    app-sign:
      timestamp-window: 5m
      nonce-ttl: 10m
  server:
    auth:
      # 本平台自己的服务必须显式开启；rag-api 作为对外 SDK 时默认不开启
      enabled: true
      # 仅允许网关访问：/auth/verify 是网关专用的令牌校验入口
      gateway-only-paths:
        - /api/platform/auth/verify
      # 完全放开：登录/刷新是唯一的外网匿名入口，需叠加验证码与频率限制
      public-paths:
        - /api/platform/auth/login
        - /api/platform/auth/refresh
        - /actuator/**
        - /doc.html
        - /v3/api-docs/**
      # 网关网段白名单：判定「带来源标识的请求是否真的来自网关」
      trusted-gateway-cidrs:
        - 10.10.1.0/24
      # 容器/K8s 环境 Pod IP 会漂移，推荐启用签名强校验替代 IP 白名单
      gateway-signature-enabled: false
      gateway-sign-secret: ${RAG_GATEWAY_SIGN_SECRET:}

management:
  endpoints:
    web:
      exposure:
        include: health,info,prometheus,metrics
  metrics:
    tags:
      application: ${spring.application.name}

logging:
  level:
    com.fintech.rag: INFO
''')

if __name__ == "__main__":
    # ------------------------------------------------------------------
    # 去重：这三个组件已统一由 rag-api 的 server 包提供（共享鉴权组件），
    # 不允许在 platform 本地再生成一份，避免 5 个服务各维护一套鉴权逻辑。
    # 见 gen_s4_server_auth.py
    # ------------------------------------------------------------------
    for duplicated in (
        PF + "/infra/interceptor/RequestSourceAuthInterceptor.java",
        PF + "/infra/interceptor/BodyCachingFilter.java",
        PF + "/config/WebMvcConfig.java",
    ):
        FILES.pop(duplicated, None)

    for rel, content in FILES.items():
        target = BASE / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print("W +", rel)
    print("---- total:", len(FILES))
