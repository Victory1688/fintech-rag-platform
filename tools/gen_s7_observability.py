# -*- coding: utf-8 -*-
"""
S7: 生成 AI 可观测能力 —— 公共层（rag-common）与 DMZ 网关（rag-gateway）

【重要】本脚本必须在 s1 与 s3 之后执行：它会【覆写】下列由 s1/s3 生成的文件，
       以加入可观测能力（W3C traceparent、采集策略、脱敏、OTLP 配置）。
       覆写清单：
         - pom.xml（根 POM：补 OTel 依赖）
         - rag-common: TraceIds / RagHeaders / RequestContextFilter / RagCommonWebAutoConfiguration
                       / AutoConfiguration.imports
         - rag-gateway: GatewayAuthProperties / RequestSourceSanitizeGlobalFilter / application.yml

【为什么这么做】最终版本只在一个地方定义（本脚本），避免「改了 s1 忘了改 s7」的双写漂移。
       执行顺序：s1 → s2 → s3 → s4 → s5 → s6 → s7 → s8 → check_skeleton.py
"""
import pathlib

BASE = pathlib.Path(r"D:/AiWorkOut/java-ai/rag-platform")
FILES = {}


def add(rel, content):
    FILES[rel] = content.lstrip("\n")


# ============================================================================
# 0. 根 POM：补 Micrometer Tracing（OTel Bridge）与 OTLP 导出器
# ============================================================================
add("pom.xml", r'''
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>com.fintech.rag</groupId>
    <artifactId>rag-platform</artifactId>
    <version>1.0.0-SNAPSHOT</version>
    <packaging>pom</packaging>

    <name>rag-platform</name>
    <description>金融信贷 RAG 知识库平台 - 微服务聚合工程</description>

    <!--
      ============================================================================
      版本基线说明（务必先读）
      1. 下列版本按 2026-09 主流稳定组合给出；落地时请以 start.spring.io 与
         mvnrepository.com 的实时可用版本为准。
      2. Spring Boot / Spring Cloud / Spring Cloud Alibaba 三者必须按官方对照表
         【成套升级】，禁止只升其中一个，否则 Nacos 装配会失败。
      3. 所有三方版本统一在此锁定，子模块禁止自行指定 version。
      ============================================================================
    -->
    <properties>
        <java.version>17</java.version>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
        <project.reporting.outputEncoding>UTF-8</project.reporting.outputEncoding>

        <spring-boot.version>3.5.6</spring-boot.version>
        <spring-cloud.version>2025.0.0</spring-cloud.version>
        <spring-cloud-alibaba.version>2025.0.0.0</spring-cloud-alibaba.version>

        <!-- LangChain4j：只用 core + open-ai 两个基础包，刻意不引 spring-boot-starter，
             因为模型需要从配置中心动态路由（多模型/敏感度分流），starter 的静态装配不适用 -->
        <langchain4j.version>1.20.0</langchain4j.version>

        <mybatis-plus.version>3.5.9</mybatis-plus.version>
        <jjwt.version>0.12.6</jjwt.version>
        <mapstruct.version>1.6.3</mapstruct.version>
        <knife4j.version>4.5.0</knife4j.version>
        <lombok.version>1.18.36</lombok.version>
        <minio.version>8.5.17</minio.version>
    </properties>

    <modules>
        <!-- 库模块（不可独立部署） -->
        <module>rag-common</module>
        <module>rag-api</module>
        <!-- 可独立部署服务 -->
        <module>rag-gateway</module>
        <module>rag-platform-service</module>
        <module>rag-knowledge-service</module>
        <module>rag-ingest-service</module>
        <module>rag-retrieval-service</module>
        <module>rag-chat-service</module>
    </modules>

    <dependencyManagement>
        <dependencies>
            <!-- ===== Spring 官方 BOM ===== -->
            <dependency>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-dependencies</artifactId>
                <version>${spring-boot.version}</version>
                <type>pom</type>
                <scope>import</scope>
            </dependency>
            <dependency>
                <groupId>org.springframework.cloud</groupId>
                <artifactId>spring-cloud-dependencies</artifactId>
                <version>${spring-cloud.version}</version>
                <type>pom</type>
                <scope>import</scope>
            </dependency>
            <dependency>
                <groupId>com.alibaba.cloud</groupId>
                <artifactId>spring-cloud-alibaba-dependencies</artifactId>
                <version>${spring-cloud-alibaba.version}</version>
                <type>pom</type>
                <scope>import</scope>
            </dependency>

            <!-- ===== LangChain4j BOM ===== -->
            <dependency>
                <groupId>dev.langchain4j</groupId>
                <artifactId>langchain4j-bom</artifactId>
                <version>${langchain4j.version}</version>
                <type>pom</type>
                <scope>import</scope>
            </dependency>

            <!-- ===== 本工程模块 ===== -->
            <dependency>
                <groupId>com.fintech.rag</groupId>
                <artifactId>rag-common</artifactId>
                <version>${project.version}</version>
            </dependency>
            <dependency>
                <groupId>com.fintech.rag</groupId>
                <artifactId>rag-api</artifactId>
                <version>${project.version}</version>
            </dependency>

            <!-- ===== 持久层 =====
                 注意：Boot 3 必须用 mybatis-plus-spring-boot3-starter。
                 若引入 mybatis-plus-extension 时出现包结构兼容报错，回退到 3.5.5。 -->
            <dependency>
                <groupId>com.baomidou</groupId>
                <artifactId>mybatis-plus-spring-boot3-starter</artifactId>
                <version>${mybatis-plus.version}</version>
            </dependency>

            <!-- ===== 安全：JWT =====
                 0.12.x 与 0.11.x API 不兼容，ParserBuilder 已废弃，请用 Jwts.parser() -->
            <dependency>
                <groupId>io.jsonwebtoken</groupId>
                <artifactId>jjwt-api</artifactId>
                <version>${jjwt.version}</version>
            </dependency>
            <dependency>
                <groupId>io.jsonwebtoken</groupId>
                <artifactId>jjwt-impl</artifactId>
                <version>${jjwt.version}</version>
                <scope>runtime</scope>
            </dependency>
            <dependency>
                <groupId>io.jsonwebtoken</groupId>
                <artifactId>jjwt-jackson</artifactId>
                <version>${jjwt.version}</version>
                <scope>runtime</scope>
            </dependency>

            <!-- ===== 对象存储 ===== -->
            <dependency>
                <groupId>io.minio</groupId>
                <artifactId>minio</artifactId>
                <version>${minio.version}</version>
            </dependency>

            <!-- ===== 文档与工具 ===== -->
            <dependency>
                <groupId>com.github.xiaoymin</groupId>
                <artifactId>knife4j-openapi3-jakarta-spring-boot-starter</artifactId>
                <version>${knife4j.version}</version>
            </dependency>
            <dependency>
                <groupId>org.mapstruct</groupId>
                <artifactId>mapstruct</artifactId>
                <version>${mapstruct.version}</version>
            </dependency>
            <dependency>
                <groupId>org.mapstruct</groupId>
                <artifactId>mapstruct-processor</artifactId>
                <version>${mapstruct.version}</version>
                <scope>provided</scope>
            </dependency>
            <dependency>
                <groupId>org.projectlombok</groupId>
                <artifactId>lombok</artifactId>
                <version>${lombok.version}</version>
                <scope>provided</scope>
            </dependency>

            <!-- ===== 可观测：链路追踪（OTel Bridge）=====
                 两者均由 spring-boot-dependencies 统一管理版本，故此处不写 version。
                 若某次构建报「缺少 version」，说明当前 Boot BOM 未纳管该坐标，
                 请在 properties 中补 <opentelemetry.version>x.y.z</opentelemetry.version>
                 并在此显式声明（详见 docs/04 §4 的 V9）。
                 为什么不用 OpenTelemetry Java Agent：见 docs/05 §1.2 第 8 条。 -->
            <dependency>
                <groupId>io.micrometer</groupId>
                <artifactId>micrometer-tracing-bridge-otel</artifactId>
            </dependency>
            <dependency>
                <groupId>io.opentelemetry</groupId>
                <artifactId>opentelemetry-exporter-otlp</artifactId>
            </dependency>
            <dependency>
                <groupId>io.micrometer</groupId>
                <artifactId>micrometer-registry-prometheus</artifactId>
            </dependency>
        </dependencies>
    </dependencyManagement>

    <dependencies>
        <!-- 所有模块共用 -->
        <dependency>
            <groupId>org.projectlombok</groupId>
            <artifactId>lombok</artifactId>
            <scope>provided</scope>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>

        <!--
          可观测依赖统一在此声明（optional=true），原因：
          1) 6 个服务都需要，写在根 POM 避免 6 份重复；
          2) 必须 optional —— rag-api 是对外 SDK，业务方引它时不应被动引入 OTel 导出器与
             JVM 采集开销（optional 依赖不参与传递，但本工程内部子模块仍可编译使用）。
          只在根 POM 加一次，子模块无需重复声明。
        -->
        <dependency>
            <groupId>io.micrometer</groupId>
            <artifactId>micrometer-tracing-bridge-otel</artifactId>
            <optional>true</optional>
        </dependency>
        <dependency>
            <groupId>io.opentelemetry</groupId>
            <artifactId>opentelemetry-exporter-otlp</artifactId>
            <optional>true</optional>
        </dependency>
    </dependencies>

    <build>
        <pluginManagement>
            <plugins>
                <plugin>
                    <groupId>org.springframework.boot</groupId>
                    <artifactId>spring-boot-maven-plugin</artifactId>
                    <version>${spring-boot.version}</version>
                    <configuration>
                        <excludes>
                            <exclude>
                                <groupId>org.projectlombok</groupId>
                                <artifactId>lombok</artifactId>
                            </exclude>
                        </excludes>
                    </configuration>
                </plugin>
            </plugins>
        </pluginManagement>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <configuration>
                    <release>${java.version}</release>
                    <parameters>true</parameters>
                    <annotationProcessorPaths>
                        <path>
                            <groupId>org.projectlombok</groupId>
                            <artifactId>lombok</artifactId>
                            <version>${lombok.version}</version>
                        </path>
                        <path>
                            <groupId>org.mapstruct</groupId>
                            <artifactId>mapstruct-processor</artifactId>
                            <version>${mapstruct.version}</version>
                        </path>
                    </annotationProcessorPaths>
                </configuration>
            </plugin>
        </plugins>
    </build>
</project>
''')

# ============================================================================
# 1. rag-common：W3C Trace Context 工具（修掉「traceId 不是 32 位 hex」的硬伤）
# ============================================================================
add("rag-common/src/main/java/com/fintech/rag/common/util/TraceIds.java", r'''
package com.fintech.rag.common.util;

import java.util.Locale;
import java.util.concurrent.ThreadLocalRandom;
import java.util.regex.Pattern;

/**
 * W3C Trace Context 工具 —— <b>全链路追踪 ID 的唯一真源</b>。
 *
 * <p><b>为什么必须是 32 位小写十六进制？</b></p>
 * <p>OpenTelemetry / OTel Collector / LangFuse / Tempo 全部按 W3C Trace Context 规范解析
 * trace-id（32 位十六进制）与 span-id（16 位十六进制），透传头是标准 {@code traceparent}：
 * {@code 00-{trace-id}-{span-id}-{trace-flags}}。</p>
 * <p>若自造格式（例如加前缀、混入非十六进制字符），则：</p>
 * <ol>
 *   <li>OTel SDK 无法把它当作父上下文，会另起一条新链路；</li>
 *   <li>LangFuse 与 APM 里的 traceId 对不上，跨系统关联 100% 失败；</li>
 *   <li>问题表现是「日志里有 traceId，但链路里查不到」，非常难排查。</li>
 * </ol>
 *
 * @author rag-platform
 */
public final class TraceIds {

    /** W3C 标准透传头 */
    public static final String TRACEPARENT = "traceparent";

    private static final char[] HEX = "0123456789abcdef".toCharArray();
    private static final int TRACE_ID_LENGTH = 32;
    private static final int SPAN_ID_LENGTH = 16;
    private static final String ZERO_TRACE_ID = "00000000000000000000000000000000";
    private static final String ZERO_SPAN_ID = "0000000000000000";
    private static final String TRACE_FLAG_SAMPLED = "01";
    private static final String TRACE_FLAG_NOT_SAMPLED = "00";

    /** 00-<32hex>-<16hex>-<2hex>，版本位允许 00~fe（ff 非法） */
    private static final Pattern TRACEPARENT_PATTERN = Pattern.compile(
            "^(?!ff)[0-9a-f]{2}-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$");
    private static final Pattern TRACE_ID_PATTERN = Pattern.compile("^[0-9a-f]{32}$");

    private TraceIds() {
    }

    /** 生成一个新的合规 traceId（32 位小写十六进制，且不为全零） */
    public static String newTraceId() {
        byte[] bytes = new byte[16];
        while (true) {
            ThreadLocalRandom.current().nextBytes(bytes);
            String candidate = toHex(bytes);
            if (!ZERO_TRACE_ID.equals(candidate)) {
                return candidate;
            }
        }
    }

    /** 生成一个新的合规 spanId（16 位小写十六进制，且不为全零） */
    public static String newSpanId() {
        byte[] bytes = new byte[8];
        while (true) {
            ThreadLocalRandom.current().nextBytes(bytes);
            String candidate = toHex(bytes);
            if (!ZERO_SPAN_ID.equals(candidate)) {
                return candidate;
            }
        }
    }

    /** 是否为合规 traceId */
    public static boolean isValidTraceId(String traceId) {
        return traceId != null
                && traceId.length() == TRACE_ID_LENGTH
                && !ZERO_TRACE_ID.equals(traceId)
                && TRACE_ID_PATTERN.matcher(traceId).matches();
    }

    /**
     * 沿用上游 traceId，非法或缺失则新建。
     *
     * <p>注意：这里做的是「格式校验」而非「信任」——是否接受上游传入值，
     * 由调用方决定（网关侧会把客户端传入的 traceparent 整体洗掉）。</p>
     */
    public static String resolve(String traceId) {
        String normalized = normalize(traceId);
        return normalized == null ? newTraceId() : normalized;
    }

    /** 规范化：允许大小写混写，统一为小写；非法返回 null */
    public static String normalize(String traceId) {
        if (traceId == null) {
            return null;
        }
        String candidate = traceId.trim().toLowerCase(Locale.ROOT);
        return isValidTraceId(candidate) ? candidate : null;
    }

    /** 从 traceparent 解析 traceId，非法返回 null */
    public static String parseTraceId(String traceparent) {
        String[] parts = splitTraceparent(traceparent);
        return parts == null ? null : parts[1];
    }

    /** 从 traceparent 解析 spanId，非法返回 null */
    public static String parseSpanId(String traceparent) {
        String[] parts = splitTraceparent(traceparent);
        return parts == null ? null : parts[2];
    }

    /** 上游是否已采样（trace-flags 最低位为 1） */
    public static boolean isSampled(String traceparent) {
        String[] parts = splitTraceparent(traceparent);
        if (parts == null) {
            return false;
        }
        return (Integer.parseInt(parts[3], 16) & 0x01) == 1;
    }

    /**
     * 组装 traceparent。
     *
     * @param traceId 32 位 hex
     * @param spanId  16 位 hex
     * @param sampled 是否采样
     */
    public static String formatTraceparent(String traceId, String spanId, boolean sampled) {
        String safeTraceId = isValidTraceId(traceId) ? traceId : newTraceId();
        String safeSpanId = isHex(spanId, SPAN_ID_LENGTH) ? spanId : newSpanId();
        return "00-" + safeTraceId + "-" + safeSpanId + "-"
                + (sampled ? TRACE_FLAG_SAMPLED : TRACE_FLAG_NOT_SAMPLED);
    }

    /**
     * 只带 traceId 的 traceparent（spanId 用占位）。
     *
     * <p>用途：网关生成 traceparent 透传给下游时，网关自己的 spanId 对下游无意义，
     * 下游的 OTel SDK 会以「父上下文」方式提取 traceId 并生成自己的 spanId。</p>
     */
    public static String formatTraceparent(String traceId, boolean sampled) {
        return formatTraceparent(traceId, ZERO_SPAN_ID, sampled);
    }

    /** 是否形如合法 traceparent */
    public static boolean isValidTraceparent(String traceparent) {
        return splitTraceparent(traceparent) != null;
    }

    private static String[] splitTraceparent(String traceparent) {
        if (traceparent == null) {
            return null;
        }
        String candidate = traceparent.trim().toLowerCase(Locale.ROOT);
        if (!TRACEPARENT_PATTERN.matcher(candidate).matches()) {
            return null;
        }
        String[] parts = candidate.split("-");
        if (ZERO_TRACE_ID.equals(parts[1]) || ZERO_SPAN_ID.equals(parts[2])) {
            return null;
        }
        return parts;
    }

    private static boolean isHex(String value, int length) {
        if (value == null || value.length() != length || ZERO_SPAN_ID.equals(value)) {
            return false;
        }
        for (int i = 0; i < value.length(); i++) {
            if (Character.digit(value.charAt(i), 16) < 0) {
                return false;
            }
        }
        return true;
    }

    private static String toHex(byte[] bytes) {
        char[] chars = new char[bytes.length * 2];
        for (int i = 0; i < bytes.length; i++) {
            int v = bytes[i] & 0xFF;
            chars[i * 2] = HEX[v >>> 4];
            chars[i * 2 + 1] = HEX[v & 0x0F];
        }
        return new String(chars);
    }

    /** 供日志/看板使用的短格式（前 8 位） */
    public static String shortId(String traceId) {
        return traceId == null || traceId.length() <= 8 ? String.valueOf(traceId) : traceId.substring(0, 8);
    }
}
''')

# ============================================================================
# 2. rag-common：请求头常量（新增 traceparent）
# ============================================================================
add("rag-common/src/main/java/com/fintech/rag/common/constant/RagHeaders.java", r'''
package com.fintech.rag.common.constant;

/**
 * 全链路请求头常量。
 *
 * <p>集中定义的目的：任何一处硬编码字符串写错，都会造成静默的鉴权绕过或
 * 来源误判，因此禁止在业务代码里手写 Header 名。</p>
 *
 * @author rag-platform
 */
public final class RagHeaders {

    private RagHeaders() {
    }

    // ---------- 来源标识（只能由 DMZ 网关写入） ----------
    /** 请求来源标识，DMZ 网关注入 {@code DMZ_GATEWAY}；内网请求禁止携带 */
    public static final String REQUEST_SOURCE = "X-Request-Source";

    /** 网关签名（可选强校验），不依赖 IP 白名单 */
    public static final String GATEWAY_SIGNATURE = "X-Gateway-Signature";

    // ---------- 外网用户身份（网关校验后透传） ----------
    /** 用户 JWT */
    public static final String USER_TOKEN = "X-User-Token";

    /** 网关解析后的用户 ID */
    public static final String USER_ID = "X-User-Id";

    /** 网关解析后的用户名称 */
    public static final String USER_NAME = "X-User-Name";

    /** 网关解析后的用户角色编码（逗号分隔）。用于「按角色授权」的知识库 ACL 判定 */
    public static final String USER_ROLES = "X-User-Roles";

    /** 网关解析后的用户部门 ID。用于「按部门授权」的知识库 ACL 判定 */
    public static final String USER_DEPT = "X-User-Dept";

    // ---------- 内网应用身份 ----------
    /** 应用 ID */
    public static final String APP_ID = "X-App-Id";

    /** 毫秒时间戳，与服务端偏差超过 5 分钟拒绝 */
    public static final String APP_TIMESTAMP = "X-App-Timestamp";

    /** 随机串，配合 Redis 防重放 */
    public static final String APP_NONCE = "X-App-Nonce";

    /** HMAC-SHA256 签名 */
    public static final String APP_SIGNATURE = "X-App-Signature";

    // ---------- 追踪 ----------
    /**
     * W3C Trace Context 标准透传头，格式 {@code 00-{32hex}-{16hex}-{2hex}}。
     *
     * <p><b>安全约束</b>：该头可由客户端任意伪造，伪造后可污染/覆盖整条链路，
     * 因此必须由网关「先删后写」，且应用侧不得直接信任外部传入值。</p>
     *
     * @see com.fintech.rag.common.util.TraceIds
     */
    public static final String TRACEPARENT = "traceparent";

    /**
     * 业务自定义追踪头（历史兼容）。
     *
     * <p>新代码请使用 {@link #TRACEPARENT}；保留本常量只为兼容早期对接方与
     * 人工排障时手填 traceId 的场景。取值必须是合法的 32 位 hex。</p>
     */
    public static final String TRACE_ID = "X-Trace-Id";
}
''')

# ============================================================================
# 3. rag-common：请求上下文过滤器（traceparent 优先 + 对齐 OTel traceId）
# ============================================================================
add("rag-common/src/main/java/com/fintech/rag/common/context/RequestContextFilter.java", r'''
package com.fintech.rag.common.context;

import com.fintech.rag.common.constant.RagHeaders;
import com.fintech.rag.common.observability.TraceIdProvider;
import com.fintech.rag.common.util.TraceIds;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.MDC;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.core.Ordered;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/**
 * 请求上下文初始化过滤器（Servlet 栈）。
 *
 * <p>只做三件事：解析 traceId、解析请求来源、解析客户端 IP。
 * <strong>不做鉴权</strong>——鉴权由各服务的 SourceAuthInterceptor 完成，
 * 因为不同服务的权限模型不同（用户维度 vs 应用维度）。</p>
 *
 * <p><b>traceId 的解析优先级（顺序很重要）</b>：</p>
 * <ol>
 *   <li>{@link TraceIdProvider}：即 Micrometer Tracing 当前 span 的 traceId。
 *       这是<b>权威值</b> —— OTel 已按 W3C 规范从 traceparent 提取并生成了 span，
 *       我们直接复用它，保证「日志里的 traceId」与「链路里的 traceId」完全一致。</li>
 *   <li>本地解析 traceparent / X-Trace-Id（用于未引入追踪依赖的服务或降级场景）。</li>
 *   <li>都没有则新建。</li>
 * </ol>
 * <p>本过滤器位于观测过滤器之后执行（order 更大），因此第 1 步在正常情况下必然命中。</p>
 *
 * @author rag-platform
 */
public class RequestContextFilter extends OncePerRequestFilter implements Ordered {

    private final ObjectProvider<TraceIdProvider> traceIdProvider;

    public RequestContextFilter(ObjectProvider<TraceIdProvider> traceIdProvider) {
        this.traceIdProvider = traceIdProvider;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        String traceId = resolveTraceId(request);
        String clientIp = resolveClientIp(request);
        RequestSource source = RequestSource.resolve(request.getHeader(RagHeaders.REQUEST_SOURCE));

        RequestContext.set(new RequestContext.Snapshot(
                source, null, null, null,
                request.getHeader(RagHeaders.APP_ID),
                clientIp, traceId));

        MDC.put("traceId", traceId);
        response.setHeader(RagHeaders.TRACE_ID, traceId);
        try {
            filterChain.doFilter(request, response);
        } finally {
            // 必须清理：线程池复用会串号，这是排查线上诡异问题的常见根源
            MDC.clear();
            RequestContext.clear();
        }
    }

    private String resolveTraceId(HttpServletRequest request) {
        TraceIdProvider provider = traceIdProvider.getIfAvailable();
        if (provider != null) {
            String current = provider.currentTraceId();
            if (current != null && !current.isBlank()) {
                return current;
            }
        }
        String fromTraceparent = TraceIds.parseTraceId(request.getHeader(RagHeaders.TRACEPARENT));
        if (fromTraceparent != null) {
            return fromTraceparent;
        }
        return TraceIds.resolve(request.getHeader(RagHeaders.TRACE_ID));
    }

    private String resolveClientIp(HttpServletRequest request) {
        String[] headers = {"X-Forwarded-For", "X-Real-IP", "Proxy-Client-IP", "WL-Proxy-Client-IP"};
        for (String header : headers) {
            String value = request.getHeader(header);
            if (value != null && !value.isBlank() && !"unknown".equalsIgnoreCase(value)) {
                int comma = value.indexOf(',');
                return comma > 0 ? value.substring(0, comma).trim() : value.trim();
            }
        }
        return request.getRemoteAddr();
    }

    @Override
    public int getOrder() {
        // 必须晚于 Spring Boot 的观测过滤器（ServerHttpObservationFilter = HIGHEST_PRECEDENCE + 1），
        // 否则拿不到当前 span 的 traceId
        return Ordered.HIGHEST_PRECEDENCE + 10;
    }
}
''')

# ============================================================================
# 4. rag-common：可观测公共组件
# ============================================================================
add("rag-common/src/main/java/com/fintech/rag/common/observability/TraceIdProvider.java", r'''
package com.fintech.rag.common.observability;

/**
 * 当前 traceId 提供者。
 *
 * <p>刻意定义成接口而非直接依赖 Micrometer Tracing：这样 rag-common 对追踪实现
 * <b>零硬依赖</b>——未引入追踪依赖的服务（或引用 rag-api 的外部业务方）不会因为
 * 缺少 {@code io.micrometer.tracing.Tracer} 而启动失败。</p>
 *
 * @author rag-platform
 */
public interface TraceIdProvider {

    /** 当前请求的 traceId；无上下文时返回 null */
    String currentTraceId();
}
''')

add("rag-common/src/main/java/com/fintech/rag/common/observability/MicrometerTraceIdProvider.java", r'''
package com.fintech.rag.common.observability;

import io.micrometer.tracing.Span;
import io.micrometer.tracing.Tracer;

/**
 * Micrometer Tracing 实现：直接复用当前 span 的 traceId。
 *
 * <p><b>为什么必须复用而不是自己生成</b>：OTel 按 W3C 规范从 traceparent 提取了
 * 父上下文并创建了 span，此时 traceId 已经确定。若业务代码再自己生成一个，
 * 结果就是「日志一个 ID、链路另一个 ID」，排障时永远对不上。</p>
 *
 * <p>本类只在 classpath 存在 {@code io.micrometer.tracing.Tracer} 时被装配
 * （见 {@code RagCommonObservabilityAutoConfiguration}）。</p>
 *
 * @author rag-platform
 */
public class MicrometerTraceIdProvider implements TraceIdProvider {

    private final Tracer tracer;

    public MicrometerTraceIdProvider(Tracer tracer) {
        this.tracer = tracer;
    }

    @Override
    public String currentTraceId() {
        Span span = tracer.currentSpan();
        if (span == null || span.context() == null) {
            return null;
        }
        return span.context().traceId();
    }
}
''')

add("rag-common/src/main/java/com/fintech/rag/common/observability/ContentLevel.java", r'''
package com.fintech.rag.common.observability;

/**
 * 可观测数据采集档位 —— <b>金融场景的合规开关</b>。
 *
 * <p>顺序即敏感度，禁止跨档跳级开启。生产默认 {@link #METRICS_ONLY}。</p>
 *
 * @author rag-platform
 */
public enum ContentLevel {

    /** 只上报 span 结构与数值属性，绝不回传 prompt / 答案 / 召回片段（生产默认） */
    METRICS_ONLY(0),

    /** 额外上报内容指纹（sha256 前 16 位）与长度，不落原文 */
    FINGERPRINT(1),

    /** 上报脱敏后的 prompt / 答案 / 召回片段（正则 + 掩码） */
    REDACTED_CONTENT(2),

    /** 上报原文 —— <b>仅限开发环境，生产必须禁用</b> */
    FULL_CONTENT(3);

    private final int rank;

    ContentLevel(int rank) {
        this.rank = rank;
    }

    public int rank() {
        return rank;
    }

    /** 是否允许携带任何形式的内容（含指纹） */
    public boolean allowsAnyContent() {
        return rank >= FINGERPRINT.rank;
    }

    /** 是否允许携带真实文本（已脱敏或原文） */
    public boolean allowsText() {
        return rank >= REDACTED_CONTENT.rank;
    }

    /** 是否为原文档位（生产禁用） */
    public boolean isPlainText() {
        return rank >= FULL_CONTENT.rank;
    }
}
''')

add("rag-common/src/main/java/com/fintech/rag/common/observability/RagOutcome.java", r'''
package com.fintech.rag.common.observability;

/**
 * 业务结果归因 —— 质量看板与告警的核心维度。
 *
 * <p>为什么单列一个枚举：只看「成功率」会把「无据不答」也算成成功，
 * 从而掩盖「知识库覆盖不足」这个真问题。必须按结果分类统计。</p>
 *
 * @author rag-platform
 */
public enum RagOutcome {

    /** 正常作答（检索命中且通过护栏） */
    ANSWERED,

    /** 检索无命中 —— 未调用大模型（「无据不答」） */
    ABSTAINED,

    /** 被护栏拦截 */
    GUARDRAIL_BLOCKED,

    /** 链路异常（检索失败 / 模型失败 / 超时） */
    ERROR
}
''')

add("rag-common/src/main/java/com/fintech/rag/common/observability/GenAiSemconv.java", r'''
package com.fintech.rag.common.observability;

import java.util.Locale;

/**
 * OpenTelemetry GenAI 语义约定常量映射层 —— <b>埋点名称的唯一真源</b>。
 *
 * <p><b>为什么要单独一个常量类？</b></p>
 * <p>截至 2026-09，OTel GenAI 语义约定<b>全部处于 Development 状态</b>
 * （GenAI 文档已于 2026-06 迁至独立仓库 {@code open-telemetry/semantic-conventions-genai}，
 * 尚无 tagged release，属性名仍可能变更）。一旦属性改名，如果没有映射层，
 * 就要在几十处业务代码里改字符串并重建全部看板；有映射层则只改本文件。</p>
 *
 * <p><b>禁止使用的废弃属性</b>（照抄 2025 年博客的常见坑）：</p>
 * <ul>
 *   <li>{@code gen_ai.system} → 已由 {@code gen_ai.provider.name} 取代（v1.37 起）</li>
 *   <li>{@code gen_ai.content.prompt} / {@code gen_ai.content.completion} → 已废弃</li>
 * </ul>
 *
 * @author rag-platform
 */
public final class GenAiSemconv {

    private GenAiSemconv() {
    }

    // ---------------------------------------------------------------- 操作名
    public static final String OP_CHAT = "chat";
    public static final String OP_TEXT_COMPLETION = "text_completion";
    public static final String OP_EMBEDDINGS = "embeddings";
    public static final String OP_RETRIEVAL = "retrieval";
    public static final String OP_EXECUTE_TOOL = "execute_tool";
    public static final String OP_INVOKE_AGENT = "invoke_agent";
    public static final String OP_CREATE_AGENT = "create_agent";

    // ------------------------------------------------------------ span 属性
    public static final String ATTR_OPERATION_NAME = "gen_ai.operation.name";
    public static final String ATTR_PROVIDER_NAME = "gen_ai.provider.name";
    public static final String ATTR_REQUEST_MODEL = "gen_ai.request.model";
    public static final String ATTR_RESPONSE_MODEL = "gen_ai.response.model";
    public static final String ATTR_REQUEST_TEMPERATURE = "gen_ai.request.temperature";
    public static final String ATTR_REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens";
    public static final String ATTR_REQUEST_TOP_P = "gen_ai.request.top_p";
    public static final String ATTR_INPUT_TOKENS = "gen_ai.usage.input_tokens";
    public static final String ATTR_OUTPUT_TOKENS = "gen_ai.usage.output_tokens";
    public static final String ATTR_FINISH_REASONS = "gen_ai.response.finish_reasons";
    public static final String ATTR_CONVERSATION_ID = "gen_ai.conversation.id";
    public static final String ATTR_TOOL_NAME = "gen_ai.tool.name";
    public static final String ATTR_TOOL_CALL_ID = "gen_ai.tool.call.id";
    public static final String ATTR_AGENT_NAME = "gen_ai.agent.name";
    public static final String ATTR_AGENT_ID = "gen_ai.agent.id";
    public static final String ATTR_ERROR_TYPE = "error.type";

    /** 内容采集（opt-in，默认关闭，见 docs/05 §6） */
    public static final String ATTR_SYSTEM_INSTRUCTIONS = "gen_ai.system_instructions";
    public static final String ATTR_INPUT_MESSAGES = "gen_ai.input.messages";
    public static final String ATTR_OUTPUT_MESSAGES = "gen_ai.output.messages";
    /** 内容与 trace 分离存储时使用的独立事件名 */
    public static final String EVENT_INFERENCE_OPERATION_DETAILS = "gen_ai.client.inference.operation.details";

    // ---------------------------------------------------------------- 指标
    public static final String METRIC_TOKEN_USAGE = "gen_ai.client.token.usage";
    public static final String METRIC_OPERATION_DURATION = "gen_ai.client.operation.duration";
    /** 流式首字延迟（TTFT）：v1.41.0 起定义，<b>必须手工埋点</b> */
    public static final String METRIC_TIME_TO_FIRST_CHUNK = "gen_ai.client.operation.time_to_first_chunk";
    /** 流式吐字间隔：v1.41.0 起定义，<b>必须手工埋点</b> */
    public static final String METRIC_TIME_PER_OUTPUT_CHUNK = "gen_ai.client.operation.time_per_output_chunk";
    public static final String TAG_TOKEN_TYPE = "gen_ai.token.type";
    public static final String TAG_OPERATION_NAME = "gen_ai.operation.name";
    public static final String TAG_PROVIDER_NAME = "gen_ai.provider.name";
    public static final String TAG_REQUEST_MODEL = "gen_ai.request.model";
    public static final String TAG_RESPONSE_MODEL = "gen_ai.response.model";
    public static final String TAG_ERROR_TYPE = "error.type";
    public static final String TOKEN_TYPE_INPUT = "input";
    public static final String TOKEN_TYPE_OUTPUT = "output";

    // -------------------------------------------------- 自有业务属性与指标
    /** 自研属性统一加自有前缀，避免与规范属性冲突（规范明确要求这么做） */
    public static final String ATTR_SOURCE = "rag.source";
    public static final String ATTR_SUBJECT_HASH = "rag.subject.hash";
    public static final String ATTR_CONVERSATION_ID = "rag.conversation.id";
    public static final String ATTR_KB_COUNT = "rag.kb.count";
    public static final String ATTR_PROMPT_VERSION = "rag.prompt.version";
    public static final String ATTR_OUTCOME = "rag.outcome";
    public static final String ATTR_CITATION_COUNT = "rag.citation.count";
    public static final String ATTR_GUARDRAIL_HIT = "rag.guardrail.hit";
    public static final String ATTR_CACHE_HIT = "rag.retrieval.cache.hit";
    public static final String ATTR_CHUNK_COUNT = "rag.retrieval.chunk.count";
    public static final String ATTR_RAW_CHUNK_COUNT = "rag.retrieval.raw.chunk.count";
    public static final String ATTR_TOP_SCORE = "rag.retrieval.top.score";
    public static final String ATTR_RERANK_USED = "rag.retrieval.rerank.used";

    public static final String METRIC_CHAT_ANSWER_TOTAL = "rag_chat_answer_total";
    public static final String METRIC_RETRIEVAL_TOTAL = "rag_retrieval_total";
    public static final String METRIC_RETRIEVAL_EMPTY_TOTAL = "rag_retrieval_empty_total";
    public static final String METRIC_RETRIEVAL_CHUNKS = "rag_retrieval_chunks";
    public static final String METRIC_GUARDRAIL_HIT_TOTAL = "rag_guardrail_hit_total";
    public static final String METRIC_FEEDBACK_TOTAL = "rag_feedback_total";
    public static final String TAG_OUTCOME = "outcome";
    public static final String TAG_APP_SOURCE = "app_source";
    public static final String TAG_MODEL_CODE = "model_code";
    public static final String TAG_GUARDRAIL_TYPE = "guardrail_type";
    public static final String TAG_VOTE = "vote";
    public static final String TAG_REASON_CODE = "reason_code";

    /** 业务根 span 名：自有前缀 + 自有语义，<b>不要伪装成规范名</b> */
    public static final String SPAN_BUSINESS_CHAT = "rag.chat.answer";
    public static final String SPAN_BUSINESS_RETRIEVAL = "retrieval ragflow-hybrid";

    /**
     * 推理 span 命名：{@code {gen_ai.operation.name} {gen_ai.request.model}}。
     *
     * <p>规范要求模型名做小写与空白规范化，避免出现非法 span 名。</p>
     */
    public static String inferenceSpanName(String operation, String model) {
        String safeOp = (operation == null || operation.isBlank()) ? OP_CHAT : operation;
        String safeModel = sanitizeName(model);
        return safeOp + " " + safeModel;
    }

    /** 工具 span 命名：{@code execute_tool {tool.name}}（v1.41 起必须带工具名） */
    public static String toolSpanName(String toolName) {
        return OP_EXECUTE_TOOL + " " + sanitizeName(toolName);
    }

    /** Agent span 命名：{@code invoke_agent {gen_ai.agent.name}} */
    public static String agentSpanName(String agentName) {
        return OP_INVOKE_AGENT + " " + sanitizeName(agentName);
    }

    private static String sanitizeName(String value) {
        if (value == null || value.isBlank()) {
            return "unknown";
        }
        return value.trim().toLowerCase(Locale.ROOT).replace(' ', '-');
    }
}
''')

add("rag-common/src/main/java/com/fintech/rag/common/observability/ObservabilityProperties.java", r'''
package com.fintech.rag.common.observability;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * 可观测配置（可由 Nacos 动态下发，无需重启）。
 *
 * <p><b>默认值即生产安全值</b>：默认只上报指标、不回传任何内容。</p>
 *
 * @author rag-platform
 */
@ConfigurationProperties(prefix = "rag.observability")
public class ObservabilityProperties {

    /** 总开关。关闭后不上报 OTLP，但 Prometheus 指标不受影响 */
    private boolean enabled = true;

    /** 采集档位，生产默认 METRICS_ONLY */
    private ContentLevel contentLevel = ContentLevel.METRICS_ONLY;

    /**
     * 是否允许在 FULL_CONTENT 档位下运行。
     *
     * <p>这是防呆闸：即使有人把 content-level 配成 FULL_CONTENT，
     * 只要本开关为 false（默认），也会被降级为 REDACTED_CONTENT —— 防止运维误配导致原文出内网。</p>
     */
    private boolean allowPlainTextContent = false;

    /** 采集内容时单字段最大字符数（防止超长 Prompt 打爆上报通道） */
    private int maxContentChars = 2000;

    /** 是否记录召回片段文本（仅 REDACTED_CONTENT 及以上档位生效） */
    private boolean recordRetrievedChunks = false;

    /** 主体哈希盐值，必须走环境变量注入；为空时退化为不带盐的哈希（仅开发可用） */
    private String subjectHashSalt = "";

    /** 上游模型供应商标识，写入 gen_ai.provider.name（OpenAI 兼容协议下统一填 openai） */
    private String providerName = "openai";

    public boolean isEnabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }

    public ContentLevel getContentLevel() {
        return contentLevel;
    }

    public void setContentLevel(ContentLevel contentLevel) {
        this.contentLevel = contentLevel;
    }

    public boolean isAllowPlainTextContent() {
        return allowPlainTextContent;
    }

    public void setAllowPlainTextContent(boolean allowPlainTextContent) {
        this.allowPlainTextContent = allowPlainTextContent;
    }

    public int getMaxContentChars() {
        return maxContentChars;
    }

    public void setMaxContentChars(int maxContentChars) {
        this.maxContentChars = maxContentChars;
    }

    public boolean isRecordRetrievedChunks() {
        return recordRetrievedChunks;
    }

    public void setRecordRetrievedChunks(boolean recordRetrievedChunks) {
        this.recordRetrievedChunks = recordRetrievedChunks;
    }

    public String getSubjectHashSalt() {
        return subjectHashSalt;
    }

    public void setSubjectHashSalt(String subjectHashSalt) {
        this.subjectHashSalt = subjectHashSalt;
    }

    public String getProviderName() {
        return providerName;
    }

    public void setProviderName(String providerName) {
        this.providerName = providerName;
    }

    /**
     * 生效档位：叠加「防呆闸」后的实际档位。
     *
     * <p>业务代码一律调用本方法，<b>不要直接读 contentLevel</b>，
     * 否则防呆闸形同虚设。</p>
     */
    public ContentLevel effectiveContentLevel() {
        if (contentLevel == ContentLevel.FULL_CONTENT && !allowPlainTextContent) {
            return ContentLevel.REDACTED_CONTENT;
        }
        return contentLevel;
    }
}
''')

add("rag-common/src/main/java/com/fintech/rag/common/observability/ContentSanitizer.java", r'''
package com.fintech.rag.common.observability;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 应用侧内容脱敏与指纹工具 —— <b>可观测上报前的最后一道人工闸门</b>。
 *
 * <p><b>为什么脱敏必须在应用侧做，而不是交给 OTel Collector？</b></p>
 * <p>Collector 的 redaction/transform processor 是<b>兜底安全网</b>，不是控制手段：
 * 一旦某个字段在应用侧被采集，它就已经离开了受控边界（进入网络、进入 exporter 队列、
 * 可能落进 exporter 的错误日志）。正确做法是在「构造上报内容」这一步就脱敏。</p>
 *
 * <p><b>与输出侧脱敏的规则一致性</b>：本类内置规则与 {@code AnswerGuardrail} 的
 * 输出脱敏规则应保持同源（理想做法是都从 {@code t_sensitive_rule} 加载）。
 * 两处规则不一致会形成「对用户脱敏了、但对 LangFuse 没脱敏」的合规漏洞。</p>
 *
 * @author rag-platform
 */
public class ContentSanitizer {

    /** 手机号（中国大陆） */
    private static final Pattern PHONE = Pattern.compile("(?<!\\d)(1[3-9]\\d{9})(?!\\d)");
    /** 18 位身份证（末位可为 X） */
    private static final Pattern ID_CARD = Pattern.compile("(?<!\\d)(\\d{17}[\\dXx])(?!\\d)");
    /** 15 位旧身份证 */
    private static final Pattern ID_CARD_15 = Pattern.compile("(?<!\\d)(\\d{15})(?!\\d)");
    /** 银行卡（16~19 位连续数字） */
    private static final Pattern BANK_CARD = Pattern.compile("(?<!\\d)(\\d{16,19})(?!\\d)");
    /** 邮箱 */
    private static final Pattern EMAIL = Pattern.compile("([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\\.[A-Za-z]{2,})");

    private final ObservabilityProperties properties;

    public ContentSanitizer(ObservabilityProperties properties) {
        this.properties = properties;
    }

    /**
     * 脱敏：保留可读性（前 3 后 2 / 域名保留），便于人工比对，但不泄露完整值。
     */
    public String mask(String text) {
        if (text == null || text.isEmpty()) {
            return text;
        }
        String masked = ID_CARD.matcher(text).replaceAll(m -> maskKeep(m.group(1), 3, 2));
        masked = ID_CARD_15.matcher(masked).replaceAll(m -> maskKeep(m.group(1), 3, 2));
        masked = PHONE.matcher(masked).replaceAll(m -> maskKeep(m.group(1), 3, 2));
        masked = BANK_CARD.matcher(masked).replaceAll(m -> maskKeep(m.group(1), 4, 2));
        masked = EMAIL.matcher(masked).replaceAll(m -> m.group(1).charAt(0) + "***@" + m.group(2));
        return masked;
    }

    /** 内容指纹（sha256 前 16 位 hex），用于「同一问题是否重复出现」而无需落原文 */
    public String fingerprint(String text) {
        if (text == null) {
            return null;
        }
        return sha256Hex(text).substring(0, 16);
    }

    /** 主体标识哈希（带盐），用于在不落 userId 的前提下做维度归因 */
    public String subjectHash(String subjectId) {
        if (subjectId == null || subjectId.isBlank()) {
            return null;
        }
        String salt = properties.getSubjectHashSalt() == null ? "" : properties.getSubjectHashSalt();
        String raw = sha256Hex(salt + "|" + subjectId);
        return raw.substring(0, 16);
    }

    /**
     * 按当前档位产出「可上报的文本」。
     *
     * @param text 原始文本（可能是 prompt / 答案 / 召回片段）
     * @return null 表示本档位不允许上报文本；否则返回已脱敏并截断的文本
     */
    public String forReporting(String text) {
        ContentLevel level = properties.effectiveContentLevel();
        if (text == null || text.isEmpty() || !level.allowsText()) {
            return null;
        }
        String prepared = level.isPlainText() ? text : mask(text);
        return truncate(prepared, properties.getMaxContentChars());
    }

    private String maskKeep(String value, int head, int tail) {
        if (value == null || value.length() <= head + tail) {
            return "***";
        }
        StringBuilder sb = new StringBuilder();
        sb.append(value, 0, head);
        sb.append("*".repeat(value.length() - head - tail));
        sb.append(value, value.length() - tail, value.length());
        return sb.toString();
    }

    private String truncate(String value, int max) {
        if (value == null || max <= 0 || value.length() <= max) {
            return value;
        }
        return value.substring(0, max) + "...[truncated]";
    }

    private String sha256Hex(String value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] bytes = digest.digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder(bytes.length * 2);
            for (byte b : bytes) {
                sb.append(Character.forDigit((b >> 4) & 0xF, 16));
                sb.append(Character.forDigit(b & 0xF, 16));
            }
            return sb.toString();
        } catch (NoSuchAlgorithmException ex) {
            // SHA-256 是 JDK 必备算法，正常不可能走到这里
            throw new IllegalStateException("SHA-256 not available", ex);
        }
    }
}
''')

# ============================================================================
# 5. rag-common：可观测自动装配 + 覆写 web 自动装配
# ============================================================================
add("rag-common/src/main/java/com/fintech/rag/common/config/RagCommonObservabilityAutoConfiguration.java", r'''
package com.fintech.rag.common.config;

import com.fintech.rag.common.observability.ContentSanitizer;
import com.fintech.rag.common.observability.MicrometerTraceIdProvider;
import com.fintech.rag.common.observability.ObservabilityProperties;
import com.fintech.rag.common.observability.TraceIdProvider;
import io.micrometer.tracing.Tracer;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;

/**
 * 可观测公共能力自动装配。
 *
 * <p><b>条件注解写在自动配置类上的原因</b>：Spring Boot 通过 ASM 读取元数据判断
 * {@code @ConditionalOnClass}，不会触发类加载。因此当 classpath 缺少
 * {@code io.micrometer.tracing.Tracer} 时，{@link #micrometerTraceIdProvider} 不会被调用，
 * {@link MicrometerTraceIdProvider} 这个引用了 Tracer 的类型也就不会被加载 —— 避免了
 * 引用 rag-api 的外部业务方（未引入追踪依赖）启动时 NoClassDefFoundError。</p>
 *
 * @author rag-platform
 */
@AutoConfiguration
@EnableConfigurationProperties(ObservabilityProperties.class)
@ConditionalOnProperty(prefix = "rag.observability", name = "enabled", havingValue = "true", matchIfMissing = true)
public class RagCommonObservabilityAutoConfiguration {

    @Bean
    @ConditionalOnMissingBean
    public ContentSanitizer contentSanitizer(ObservabilityProperties properties) {
        return new ContentSanitizer(properties);
    }

    @Bean
    @ConditionalOnMissingBean
    @ConditionalOnClass(Tracer.class)
    public TraceIdProvider micrometerTraceIdProvider(Tracer tracer) {
        return new MicrometerTraceIdProvider(tracer);
    }
}
''')

add("rag-common/src/main/java/com/fintech/rag/common/config/RagCommonWebAutoConfiguration.java", r'''
package com.fintech.rag.common.config;

import com.fintech.rag.common.context.RequestContextFilter;
import com.fintech.rag.common.exception.GlobalExceptionHandler;
import com.fintech.rag.common.observability.TraceIdProvider;
import jakarta.servlet.Filter;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnWebApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;

/**
 * Servlet 栈公共能力自动装配。
 *
 * <p>条件注解写在自动配置类上（而非被装配的类上），Spring Boot 可通过 ASM 读取元数据
 * 判断条件，不会触发 class loading，因此 rag-gateway（WebFlux）不会因为缺少
 * jakarta.servlet 而启动失败。</p>
 *
 * @author rag-platform
 */
@AutoConfiguration
@ConditionalOnWebApplication(type = ConditionalOnWebApplication.Type.SERVLET)
@ConditionalOnClass(name = "jakarta.servlet.Filter")
@Import(GlobalExceptionHandler.class)
public class RagCommonWebAutoConfiguration {

    @Bean
    @ConditionalOnMissingBean
    public Filter requestContextFilter(ObjectProvider<TraceIdProvider> traceIdProvider) {
        // 用 ObjectProvider 注入：未引入追踪依赖时 getIfAvailable() 返回 null，
        // 过滤器退化为「自行解析 traceparent」，不会启动失败
        return new RequestContextFilter(traceIdProvider);
    }
}
''')

add("rag-common/src/main/resources/META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports", r'''
com.fintech.rag.common.config.RagCommonJacksonAutoConfiguration
com.fintech.rag.common.config.RagCommonWebAutoConfiguration
com.fintech.rag.common.config.RagCommonObservabilityAutoConfiguration
''')

# ============================================================================
# 6. rag-gateway：traceparent 洗白（WebFilter，必须早于观测过滤器）+ 网关配置
# ============================================================================
add("rag-gateway/src/main/java/com/fintech/rag/gateway/config/GatewayAuthProperties.java", r'''
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
''')

add("rag-gateway/src/main/java/com/fintech/rag/gateway/filter/InboundTraceSanitizeWebFilter.java", r'''
package com.fintech.rag.gateway.filter;

import com.fintech.rag.common.constant.RagHeaders;
import com.fintech.rag.common.util.TraceIds;
import com.fintech.rag.gateway.config.GatewayAuthProperties;
import org.springframework.core.Ordered;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import org.springframework.web.server.WebFilter;
import org.springframework.web.server.WebFilterChain;
import reactor.core.publisher.Mono;

/**
 * 入站追踪头洗白 —— <b>必须在观测过滤器之前执行</b>。
 *
 * <p><b>为什么需要它（这是最容易漏的一处安全问题）</b>：</p>
 * <p>Spring Boot 的 WebFlux 观测过滤器（{@code org.springframework.web.filter.reactive
 * .ServerHttpObservationFilter}）order 为 {@code Ordered.HIGHEST_PRECEDENCE + 1}，
 * 它在 <b>WebFilter 链的最前面</b>就把入站 {@code traceparent} 提取成了父上下文。
 * 而 Gateway 的 {@code GlobalFilter} 属于「路由内的过滤器链」，执行时机远晚于 WebFilter —— 
 * 也就是说，等我们自己的 GlobalFilter 去删 traceparent 时，客户端伪造的 traceId
 * <b>已经被采纳为本次链路的 traceId 了</b>。</p>
 *
 * <p>所以：洗白动作必须放在一个 order 更小（更早）的 {@link WebFilter} 里。</p>
 *
 * @author rag-platform
 */
@Component
public class InboundTraceSanitizeWebFilter implements WebFilter, Ordered {

    private final GatewayAuthProperties properties;

    public InboundTraceSanitizeWebFilter(GatewayAuthProperties properties) {
        this.properties = properties;
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain chain) {
        ServerHttpRequest request = exchange.getRequest();
        ServerHttpRequest.Builder builder = request.mutate();

        builder.headers(headers -> {
            if (properties.isAcceptClientTraceparent()) {
                // 白名单模式：仅接受格式合法的 traceparent，非法一律删除
                String incoming = headers.getFirst(RagHeaders.TRACEPARENT);
                if (!TraceIds.isValidTraceparent(incoming)) {
                    headers.remove(RagHeaders.TRACEPARENT);
                }
            } else {
                // 默认模式：网关是链路的唯一根，客户端传入的追踪头一律丢弃
                headers.remove(RagHeaders.TRACEPARENT);
            }
            // 业务自定义 traceId 头同样不可信
            String legacy = headers.getFirst(RagHeaders.TRACE_ID);
            if (legacy != null && !TraceIds.isValidTraceId(legacy)) {
                headers.remove(RagHeaders.TRACE_ID);
            }
        });

        return chain.filter(exchange.mutate().request(builder.build()).build());
    }

    @Override
    public int getOrder() {
        // 必须小于 Spring Boot 观测过滤器的 HIGHEST_PRECEDENCE + 1
        return Ordered.HIGHEST_PRECEDENCE;
    }
}
''')

add("rag-gateway/src/main/java/com/fintech/rag/gateway/filter/RequestSourceSanitizeGlobalFilter.java", r'''
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
import org.springframework.util.StringUtils;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.util.Set;

/**
 * 请求来源标识注入、「洗白」与链路透传过滤器 —— <b>整套防伪造机制的第一道闸</b>。
 *
 * <p>核心逻辑（顺序不可颠倒）：</p>
 * <ol>
 *   <li><b>先删</b>：强制移除客户端可能传入的一切身份/来源头，防止前端伪造；</li>
 *   <li><b>再写</b>：注入可信的 {@code X-Request-Source: DMZ_GATEWAY}；</li>
 *   <li><b>链路透传</b>：解析当前 span 的 traceId，写成标准 {@code traceparent} 下发给内网服务
 *       （traceId 由 OTel 生成，此处只做「向下游声明」，不再自行造 ID）；</li>
 *   <li>可选注入 {@code X-Gateway-Signature}，供内网侧做不依赖 IP 的强校验。</li>
 * </ol>
 *
 * <p>为什么不在 route 里用 {@code RemoveRequestHeader}/{@code AddRequestHeader}？
 * 声明式过滤器对新增路由容易漏配，一旦漏配就是静默的鉴权绕过。
 * 用 GlobalFilter 可以保证「所有路由无例外」。</p>
 *
 * <p><b>注意</b>：入站 traceparent 的洗白在 {@link InboundTraceSanitizeWebFilter} 中完成，
 * 因为 GlobalFilter 执行得太晚（观测过滤器已经把伪造值采纳为父上下文了）。</p>
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
            RagHeaders.APP_SIGNATURE,
            RagHeaders.TRACEPARENT,
            RagHeaders.TRACE_ID
    );

    private final GatewayAuthProperties properties;
    private final GatewayTraceSupport traceSupport;

    public RequestSourceSanitizeGlobalFilter(GatewayAuthProperties properties,
                                            GatewayTraceSupport traceSupport) {
        this.properties = properties;
        this.traceSupport = traceSupport;
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        ServerHttpRequest request = exchange.getRequest();
        String traceId = traceSupport.resolveCurrentTraceId();

        ServerHttpRequest.Builder builder = request.mutate();
        builder.headers(headers -> {
            SPOOFABLE_HEADERS.forEach(headers::remove);
            headers.set(RagHeaders.REQUEST_SOURCE, RequestSource.DMZ_HEADER_VALUE);
            headers.set(RagHeaders.TRACE_ID, traceId);
            headers.set(RagHeaders.TRACEPARENT, TraceIds.formatTraceparent(traceId, traceSupport.isSampled()));
            if (StringUtils.hasText(properties.getSignSecret())) {
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

add("rag-gateway/src/main/java/com/fintech/rag/gateway/filter/GatewayTraceSupport.java", r'''
package com.fintech.rag.gateway.filter;

import com.fintech.rag.common.util.TraceIds;
import io.micrometer.tracing.Span;
import io.micrometer.tracing.Tracer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Component;

/**
 * 网关侧 traceId 解析支持。
 *
 * <p>优先取 Micrometer Tracing 当前 span 的 traceId（OTel 已按 W3C 规范生成，
 * 这是权威值）；未引入追踪依赖时自行生成一个 32 位 hex，保证下游永远收到合规 traceparent。</p>
 *
 * @author rag-platform
 */
@Component
public class GatewayTraceSupport {

    private static final Logger log = LoggerFactory.getLogger(GatewayTraceSupport.class);

    private final ObjectProvider<Tracer> tracerProvider;

    public GatewayTraceSupport(ObjectProvider<Tracer> tracerProvider) {
        this.tracerProvider = tracerProvider;
    }

    /** 当前链路的 traceId（32 位小写 hex，绝不为 null） */
    public String resolveCurrentTraceId() {
        Tracer tracer = tracerProvider.getIfAvailable();
        if (tracer != null) {
            Span span = tracer.currentSpan();
            if (span != null && span.context() != null && span.context().traceId() != null) {
                String traceId = TraceIds.normalize(span.context().traceId());
                if (traceId != null) {
                    return traceId;
                }
                // OTel 给出的 traceId 竟然不合规，说明追踪实现异常，降级并告警
                log.warn("追踪上下文中的 traceId 非法，降级为新生成 traceId");
            }
        }
        return TraceIds.newTraceId();
    }

    /** 本次链路是否采样（用于设置 traceparent 的 sampled 标志位） */
    public boolean isSampled() {
        Tracer tracer = tracerProvider.getIfAvailable();
        if (tracer == null) {
            return true;
        }
        Span span = tracer.currentSpan();
        if (span == null || span.context() == null) {
            return true;
        }
        Boolean sampled = span.context().sampled();
        return sampled == null || sampled;
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
    # 是否接受客户端传入的 traceparent。默认 false：网关是链路的唯一根（详见 docs/05 §1.2）
    accept-client-traceparent: false
    public-paths:
      - /api/platform/auth/login
      - /api/platform/auth/refresh
      - /api/ai/health
      - /actuator/health
      - /doc.html
      - /v3/api-docs/**
    # 说明：原先把 /actuator/** 整体放入 public-paths 是危险配置 ——
    # actuator 暴露 prometheus/metrics/env/heapdump 等敏感端点，
    # 生产必须由「内网采集器直连端口」而不是「经网关对外暴露」。
    # 故此处只放行健康检查，其余 actuator 端点一律走内网。

management:
  endpoints:
    web:
      exposure:
        # 生产环境请把 include 收敛到健康与指标；env/heapdump/loggers 等严禁暴露
        include: health,info,prometheus,metrics,gateway
  endpoint:
    health:
      show-details: never
  metrics:
    tags:
      application: ${spring.application.name}
  tracing:
    sampling:
      # 见 docs/05 §7.2：指标不受采样影响，trace 采样可显著降低存储与网络成本
      probability: ${RAG_OBS_SAMPLING:0.1}
  otlp:
    tracing:
      # 应用只认 OTel Collector，不认 LangFuse（LangFuse 密钥只配在 Collector）
      endpoint: ${OTEL_EXPORTER_OTLP_TRACES_ENDPOINT:http://127.0.0.1:4318/v1/traces}
      timeout: 3s

logging:
  level:
    org.springframework.cloud.gateway: INFO
    com.fintech.rag: INFO
''')

if __name__ == "__main__":
    for rel, content in FILES.items():
        target = BASE / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print("W +", rel)
    print("---- total:", len(FILES))
