# -*- coding: utf-8 -*-
"""
S1: 生成 rag-platform 聚合工程根 pom + rag-common 模块
"""
import os
import pathlib

BASE = pathlib.Path(r"D:/AiWorkOut/java-ai/rag-platform")
FILES = {}


def add(rel, content):
    FILES[rel] = content.lstrip("\n")


# ============================================================================
# 根 POM
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

add("README.md", r'''
# rag-platform

金融信贷 RAG 知识库平台 —— Spring Boot 3.x 微服务聚合工程。

## 模块一览

| 模块 | 类型 | 端口 | 职责 |
|---|---|---|---|
| `rag-common` | 库 | - | 统一返回、异常、请求上下文、常量、工具 |
| `rag-api` | 库 | - | 服务间契约（DTO + Feign Client），同时是内网业务方接入 SDK |
| `rag-gateway` | 服务 | 8080 | DMZ 边界网关：鉴权、限流、SSE 转发、请求来源标识注入与洗白 |
| `rag-platform-service` | 服务 | 8081 | 平台治理：身份、应用凭证、ACL、配额、模型配置、审计 |
| `rag-knowledge-service` | 服务 | 8082 | 知识库与文档资产管理、ACL、Dataset 映射 |
| `rag-ingest-service` | 服务 | 8083 | 文档入库流水线与解析状态机 |
| `rag-retrieval-service` | 服务 | 8084 | 检索：Query 改写、RAGFlow 混合检索、Rerank、业务过滤、缓存 |
| `rag-chat-service` | 服务 | 8085 | 问答编排：LangChain4j、Prompt、Agent、SSE、护栏、Token 计量 |

## 构建

```bash
# 全量构建（跳过测试）
mvn -T 1C clean install -DskipTests

# 只构建某个服务及其依赖
mvn -pl rag-chat-service -am clean package -DskipTests
```

## 启动顺序

```
1. 基础设施：MySQL -> Redis -> Nacos -> RocketMQ -> MinIO -> RAGFlow
2. rag-platform-service   （被所有服务依赖，必须最先起）
3. rag-knowledge-service
4. rag-ingest-service
5. rag-retrieval-service
6. rag-chat-service
7. rag-gateway
```

## 目录规范

每个可部署服务统一采用如下分层，禁止跨层直连：

```
com.fintech.rag.<module>
├── <Module>Application.java   启动类
├── api/                       对外接口层：Controller + Request/Response
├── app/                       应用层：用例编排（AppService）、DTO 转换
├── domain/                    领域层：model / repository(接口) / service / event
├── infra/                     基础设施层：persistence / client / mq / cache / config
└── config/                    本服务的 Spring 配置
```

> 完整架构说明见 `../docs/01-架构与技术落地方案.md`
''')

# ============================================================================
# rag-common
# ============================================================================
add("rag-common/pom.xml", r'''
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

    <artifactId>rag-common</artifactId>
    <packaging>jar</packaging>
    <name>rag-common</name>
    <description>公共能力：统一返回、异常、请求上下文、常量、工具</description>

    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-json</artifactId>
        </dependency>

        <!--
          关键：spring-boot-starter-web 必须是 optional。
          rag-gateway 基于 WebFlux（SCG），若被动继承 Servlet 栈会启动失败（MVC 与 WebFlux 互斥）。
          optional 依赖不参与传递，各服务需显式声明 spring-boot-starter-web。
        -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
            <optional>true</optional>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
            <optional>true</optional>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-configuration-processor</artifactId>
            <optional>true</optional>
        </dependency>
    </dependencies>
</project>
''')

PKG = "rag-common/src/main/java/com/fintech/rag/common"

# ---------------------------------------------------------------- 统一返回
add(PKG + "/core/R.java", r'''
package com.fintech.rag.common.core;

import com.fintech.rag.common.context.RequestContext;
import com.fintech.rag.common.exception.ErrorCode;

import java.io.Serial;
import java.io.Serializable;

/**
 * 统一返回结构。
 *
 * <p>所有对外 REST 接口必须返回 {@code R<T>}，禁止直接返回裸对象，
 * 否则前端无法统一处理错误码，也无法做全链路 traceId 关联。</p>
 *
 * @param <T> 业务数据类型
 * @author rag-platform
 */
public class R<T> implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    /** 业务码，"0" 表示成功，其它见 {@link ErrorCode} */
    private String code;

    /** 提示信息 */
    private String message;

    /** 全链路追踪 ID，与日志中的 traceId 一致 */
    private String traceId;

    /** 业务数据 */
    private T data;

    /** 服务端时间戳（毫秒） */
    private long timestamp = System.currentTimeMillis();

    public R() {
    }

    public R(String code, String message, T data) {
        this.code = code;
        this.message = message;
        this.data = data;
        this.traceId = RequestContext.currentTraceId();
    }

    public static <T> R<T> ok() {
        return ok(null);
    }

    public static <T> R<T> ok(T data) {
        return new R<>(ErrorCode.SUCCESS.getCode(), ErrorCode.SUCCESS.getMessage(), data);
    }

    public static <T> R<T> fail(ErrorCode errorCode) {
        return new R<>(errorCode.getCode(), errorCode.getMessage(), null);
    }

    public static <T> R<T> fail(ErrorCode errorCode, String message) {
        return new R<>(errorCode.getCode(), message, null);
    }

    public static <T> R<T> fail(String code, String message) {
        return new R<>(code, message, null);
    }

    public boolean isSuccess() {
        return ErrorCode.SUCCESS.getCode().equals(this.code);
    }

    public String getCode() {
        return code;
    }

    public void setCode(String code) {
        this.code = code;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }

    public String getTraceId() {
        return traceId;
    }

    public void setTraceId(String traceId) {
        this.traceId = traceId;
    }

    public T getData() {
        return data;
    }

    public void setData(T data) {
        this.data = data;
    }

    public long getTimestamp() {
        return timestamp;
    }

    public void setTimestamp(long timestamp) {
        this.timestamp = timestamp;
    }
}
''')

add(PKG + "/core/PageResult.java", r'''
package com.fintech.rag.common.core;

import java.io.Serial;
import java.io.Serializable;
import java.util.Collections;
import java.util.List;

/**
 * 统一分页结构。
 *
 * @param <T> 记录类型
 * @author rag-platform
 */
public class PageResult<T> implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    /** 当前页数据 */
    private List<T> records = Collections.emptyList();

    /** 页码，从 1 开始 */
    private long pageNum = 1L;

    /** 每页条数 */
    private long pageSize = 20L;

    /** 总记录数 */
    private long total = 0L;

    /** 总页数 */
    private long pages = 0L;

    public static <T> PageResult<T> of(List<T> records, long pageNum, long pageSize, long total) {
        PageResult<T> result = new PageResult<>();
        result.setRecords(records == null ? Collections.emptyList() : records);
        result.setPageNum(pageNum);
        result.setPageSize(pageSize);
        result.setTotal(total);
        result.setPages(pageSize <= 0 ? 0 : (total + pageSize - 1) / pageSize);
        return result;
    }

    public static <T> PageResult<T> empty(long pageNum, long pageSize) {
        return of(Collections.emptyList(), pageNum, pageSize, 0L);
    }

    public List<T> getRecords() {
        return records;
    }

    public void setRecords(List<T> records) {
        this.records = records;
    }

    public long getPageNum() {
        return pageNum;
    }

    public void setPageNum(long pageNum) {
        this.pageNum = pageNum;
    }

    public long getPageSize() {
        return pageSize;
    }

    public void setPageSize(long pageSize) {
        this.pageSize = pageSize;
    }

    public long getTotal() {
        return total;
    }

    public void setTotal(long total) {
        this.total = total;
    }

    public long getPages() {
        return pages;
    }

    public void setPages(long pages) {
        this.pages = pages;
    }
}
''')

# ---------------------------------------------------------------- 异常
add(PKG + "/exception/ErrorCode.java", r'''
package com.fintech.rag.common.exception;

/**
 * 全局错误码。
 *
 * <p>码段划分（详见 docs/03-数据模型与接口契约.md §8.3）：</p>
 * <ul>
 *   <li>{@code A0xxx} 认证与鉴权</li>
 *   <li>{@code B0xxx} 知识库与文档</li>
 *   <li>{@code C0xxx} 检索</li>
 *   <li>{@code D0xxx} 生成</li>
 *   <li>{@code E0xxx} 配额与限流</li>
 *   <li>{@code F0xxx} 系统</li>
 * </ul>
 *
 * @author rag-platform
 */
public enum ErrorCode {

    // ---------------- 成功 ----------------
    SUCCESS("0", "success"),

    // ---------------- A0xxx 认证与鉴权 ----------------
    TOKEN_INVALID("A0001", "令牌无效或已过期"),
    APP_SIGN_INVALID("A0002", "应用签名校验失败"),
    TIMESTAMP_OUT_OF_WINDOW("A0003", "请求时间戳超出允许窗口"),
    REQUEST_SOURCE_FORGED("A0004", "请求来源标识被伪造，已拒绝"),
    KB_NO_PERMISSION("A0005", "无该知识库访问权限"),
    APP_DISABLED("A0006", "应用已禁用或已过期"),
    APP_IP_NOT_ALLOWED("A0007", "调用方 IP 不在白名单内"),
    NONCE_REPLAYED("A0008", "请求已被重复提交（nonce 重放）"),
    AUTH_SERVICE_UNAVAILABLE("A0009", "认证服务不可用，本次请求已拒绝"),

    // ---------------- B0xxx 知识库与文档 ----------------
    KB_NOT_FOUND("B0001", "知识库不存在"),
    DOC_DUPLICATED("B0002", "文档已存在（MD5 重复）"),
    DOC_PARSE_FAILED("B0003", "文档解析失败"),
    DOC_OFFLINE("B0004", "文档已下线"),
    FILE_TYPE_UNSUPPORTED("B0005", "文件类型不支持"),
    FILE_TOO_LARGE("B0006", "文件超过大小限制"),
    KB_NOT_EMPTY("B0007", "知识库非空，禁止删除"),
    RAGFLOW_DATASET_SYNC_FAILED("B0008", "RAGFlow Dataset 同步失败"),
    DOC_NOT_FOUND("B0009", "文档不存在"),

    // ---------------- C0xxx 检索 ----------------
    RETRIEVAL_NO_HIT("C0001", "知识库中未找到相关内容"),
    RAGFLOW_CALL_FAILED("C0002", "RAGFlow 调用失败"),
    RETRIEVAL_TIMEOUT("C0003", "检索超时"),
    KB_NOT_READY("C0004", "知识库尚未就绪（无已解析文档）"),
    RETRIEVAL_PARAM_INVALID("C0005", "检索参数非法"),

    // ---------------- D0xxx 生成 ----------------
    LLM_CALL_FAILED("D0001", "模型调用失败"),
    LLM_RATE_LIMITED("D0002", "上游模型限流"),
    GUARDRAIL_BLOCKED("D0003", "答案触发安全护栏，已拦截"),
    CONTEXT_TOO_LONG("D0004", "上下文超长"),
    NO_MODEL_AVAILABLE("D0005", "当前密级下无可用模型配置"),

    // ---------------- E0xxx 配额与限流 ----------------
    QPS_LIMIT_EXCEEDED("E0001", "超过 QPS 限流阈值"),
    DAILY_QUOTA_EXCEEDED("E0002", "超过日调用配额"),
    TOKEN_QUOTA_EXCEEDED("E0003", "Token 配额已耗尽"),

    // ---------------- F0xxx 系统 ----------------
    PARAM_INVALID("F0001", "参数校验失败"),
    INTERNAL_ERROR("F0002", "系统内部错误"),
    DEPENDENCY_UNAVAILABLE("F0003", "依赖服务不可用");

    private final String code;
    private final String message;

    ErrorCode(String code, String message) {
        this.code = code;
        this.message = message;
    }

    public String getCode() {
        return code;
    }

    public String getMessage() {
        return message;
    }
}
''')

add(PKG + "/exception/BizException.java", r'''
package com.fintech.rag.common.exception;

import java.io.Serial;

/**
 * 业务异常。
 *
 * <p>约定：可预期的业务错误抛 {@code BizException}，由全局异常处理器转成标准返回体；
 * 不可预期的错误直接抛运行时异常并告警。</p>
 *
 * @author rag-platform
 */
public class BizException extends RuntimeException {

    @Serial
    private static final long serialVersionUID = 1L;

    private final String code;

    public BizException(ErrorCode errorCode) {
        super(errorCode.getMessage());
        this.code = errorCode.getCode();
    }

    public BizException(ErrorCode errorCode, String message) {
        super(message);
        this.code = errorCode.getCode();
    }

    public BizException(ErrorCode errorCode, String message, Throwable cause) {
        super(message, cause);
        this.code = errorCode.getCode();
    }

    public String getCode() {
        return code;
    }

    public static BizException of(ErrorCode errorCode) {
        return new BizException(errorCode);
    }

    public static BizException of(ErrorCode errorCode, String message) {
        return new BizException(errorCode, message);
    }
}
''')

add(PKG + "/exception/GlobalExceptionHandler.java", r'''
package com.fintech.rag.common.exception;

import com.fintech.rag.common.core.R;
import jakarta.servlet.http.HttpServletRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.validation.BindException;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.stream.Collectors;

/**
 * 全局异常处理器（Servlet 栈）。
 *
 * <p>由 {@code RagCommonWebAutoConfiguration} 条件装配，WebFlux 网关不会加载本类。</p>
 *
 * @author rag-platform
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(BizException.class)
    public R<Void> handleBizException(BizException ex, HttpServletRequest request) {
        log.warn("业务异常 uri={} code={} msg={}", request.getRequestURI(), ex.getCode(), ex.getMessage());
        return R.fail(ex.getCode(), ex.getMessage());
    }

    @ExceptionHandler({MethodArgumentNotValidException.class, BindException.class})
    public R<Void> handleValidationException(Exception ex) {
        String detail;
        if (ex instanceof MethodArgumentNotValidException manv) {
            detail = manv.getBindingResult().getFieldErrors().stream()
                    .map(FieldError::getDefaultMessage)
                    .collect(Collectors.joining("; "));
        } else {
            BindException be = (BindException) ex;
            detail = be.getBindingResult().getFieldErrors().stream()
                    .map(FieldError::getDefaultMessage)
                    .collect(Collectors.joining("; "));
        }
        log.warn("参数校验失败 detail={}", detail);
        return R.fail(ErrorCode.PARAM_INVALID, detail);
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public R<Void> handleIllegalArgument(IllegalArgumentException ex) {
        log.warn("参数非法 msg={}", ex.getMessage());
        return R.fail(ErrorCode.PARAM_INVALID, ex.getMessage());
    }

    @ExceptionHandler(Exception.class)
    public R<Void> handleException(Exception ex, HttpServletRequest request) {
        // 未预期异常必须打完整堆栈并触发告警，不允许静默吞掉
        log.error("系统异常 uri={}", request.getRequestURI(), ex);
        return R.fail(ErrorCode.INTERNAL_ERROR);
    }
}
''')

# ---------------------------------------------------------------- 上下文
add(PKG + "/context/RequestSource.java", r'''
package com.fintech.rag.common.context;

/**
 * 请求来源。用于区分两套完全不同的鉴权与限流体系。
 *
 * <p>识别依据是 DMZ 网关注入的请求头 {@code X-Request-Source}：</p>
 * <ul>
 *   <li>携带且值为 {@code DMZ_GATEWAY} → 外网前端用户流量，走用户令牌体系</li>
 *   <li>不携带 → SF 内网业务微服务流量，走应用 AppKey 签名体系</li>
 * </ul>
 *
 * @author rag-platform
 */
public enum RequestSource {

    /** DMZ 网关转发的前端用户请求 */
    DMZ_WEB("DMZ_GATEWAY", "外网前端用户"),

    /** SF 内网业务微服务直连请求 */
    SF_INNER_APP(null, "SF内网业务微服务");

    /** 网关注入该 Header 时使用的固定值 */
    public static final String DMZ_HEADER_VALUE = "DMZ_GATEWAY";

    private final String headerValue;
    private final String description;

    RequestSource(String headerValue, String description) {
        this.headerValue = headerValue;
        this.description = description;
    }

    public String getHeaderValue() {
        return headerValue;
    }

    public String getDescription() {
        return description;
    }

    /**
     * 根据请求头值解析来源。
     *
     * <p>注意：本方法只做「标记解析」，不做「真伪校验」。
     * 真伪校验（IP 白名单 / 网关签名）在各服务的鉴权拦截器中完成，
     * 否则内网调用方伪造该头即可冒充前端。</p>
     */
    public static RequestSource resolve(String headerValue) {
        return DMZ_HEADER_VALUE.equals(headerValue) ? DMZ_WEB : SF_INNER_APP;
    }
}
''')

add(PKG + "/context/RequestContext.java", r'''
package com.fintech.rag.common.context;

/**
 * 请求级上下文（ThreadLocal）。
 *
 * <p>承载：来源、主体身份、客户端 IP、traceId。由
 * {@code RequestContextFilter} 初始化，由各服务的鉴权拦截器补齐身份信息，
 * 请求结束后必须清理，防止线程池复用导致的串号。</p>
 *
 * @author rag-platform
 */
public final class RequestContext {

    private static final ThreadLocal<Snapshot> HOLDER = new ThreadLocal<>();

    private RequestContext() {
    }

    public static void set(Snapshot snapshot) {
        HOLDER.set(snapshot);
    }

    public static Snapshot get() {
        return HOLDER.get();
    }

    public static void clear() {
        HOLDER.remove();
    }

    public static String currentTraceId() {
        Snapshot s = HOLDER.get();
        return s == null ? null : s.traceId();
    }

    public static String currentSubjectId() {
        Snapshot s = HOLDER.get();
        return s == null ? null : s.subjectId();
    }

    public static RequestSource currentSource() {
        Snapshot s = HOLDER.get();
        return s == null ? null : s.source();
    }

    public static boolean isDmzWeb() {
        return currentSource() == RequestSource.DMZ_WEB;
    }

    public static boolean isInnerApp() {
        return currentSource() == RequestSource.SF_INNER_APP;
    }

    /**
     * 上下文的不可变快照。
     *
     * @param source      请求来源
     * @param subjectType 主体类型 USER / APP
     * @param subjectId   主体标识 userId / appId
     * @param subjectName 主体名称（便于日志与审计）
     * @param appId       内网应用 ID（来源为 SF_INNER_APP 时非空）
     * @param clientIp    调用方 IP
     * @param traceId     全链路追踪 ID
     */
    public record Snapshot(RequestSource source,
                           String subjectType,
                           String subjectId,
                           String subjectName,
                           String appId,
                           String clientIp,
                           String traceId) {

        public Snapshot withSubject(String subjectType, String subjectId, String subjectName) {
            return new Snapshot(source, subjectType, subjectId, subjectName, appId, clientIp, traceId);
        }
    }
}
''')

add(PKG + "/context/RequestContextFilter.java", r'''
package com.fintech.rag.common.context;

import com.fintech.rag.common.constant.RagHeaders;
import com.fintech.rag.common.util.TraceIds;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.MDC;
import org.springframework.core.Ordered;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/**
 * 请求上下文初始化过滤器（Servlet 栈）。
 *
 * <p>只做三件事：解析 traceId、解析请求来源、解析客户端 IP。
 * <strong>不做鉴权</strong>——鉴权由各服务的 AuthSourceInterceptor 完成，
 * 因为不同服务的权限模型不同（用户维度 vs 应用维度）。</p>
 *
 * @author rag-platform
 */
public class RequestContextFilter extends OncePerRequestFilter implements Ordered {

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        String traceId = TraceIds.resolve(request.getHeader(RagHeaders.TRACE_ID));
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
        return Ordered.HIGHEST_PRECEDENCE + 10;
    }
}
''')

# ---------------------------------------------------------------- 常量与工具
add(PKG + "/constant/RagHeaders.java", r'''
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
    /** 全链路追踪 ID */
    public static final String TRACE_ID = "X-Trace-Id";
}
''')

add(PKG + "/util/TraceIds.java", r'''
package com.fintech.rag.common.util;

import java.util.UUID;

/**
 * traceId 工具。
 *
 * @author rag-platform
 */
public final class TraceIds {

    private static final String PREFIX = "r";

    private TraceIds() {
    }

    /** 生成一个新的 traceId */
    public static String newTraceId() {
        return PREFIX + UUID.randomUUID().toString().replace("-", "");
    }

    /** 沿用上游传入的 traceId，缺失则新建 */
    public static String resolve(String traceId) {
        return (traceId == null || traceId.isBlank()) ? newTraceId() : traceId;
    }
}
''')

# ---------------------------------------------------------------- 自动装配
add(PKG + "/config/RagCommonJacksonAutoConfiguration.java", r'''
package com.fintech.rag.common.config;

import com.fasterxml.jackson.databind.ser.std.ToStringSerializer;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.jackson.Jackson2ObjectMapperBuilderCustomizer;
import org.springframework.context.annotation.Bean;

/**
 * Jackson 全局配置。
 *
 * <p><strong>为什么必须把 Long 序列化成字符串：</strong>
 * 本工程主键使用雪花 ID（19 位），超过 JavaScript
 * {@code Number.MAX_SAFE_INTEGER}（2^53-1，16 位），
 * 直接以数字下发会被前端静默截断，导致「前端拿到的主键去查库查不到」，
 * 且极难排查。统一转字符串是业界标准做法。</p>
 *
 * @author rag-platform
 */
@AutoConfiguration
@ConditionalOnClass(Jackson2ObjectMapperBuilderCustomizer.class)
public class RagCommonJacksonAutoConfiguration {

    @Bean
    public Jackson2ObjectMapperBuilderCustomizer longToStringCustomizer() {
        return builder -> builder
                .serializerByType(Long.class, ToStringSerializer.instance)
                .serializerByType(Long.TYPE, ToStringSerializer.instance);
    }
}
''')

add(PKG + "/config/RagCommonWebAutoConfiguration.java", r'''
package com.fintech.rag.common.config;

import com.fintech.rag.common.context.RequestContextFilter;
import com.fintech.rag.common.exception.GlobalExceptionHandler;
import jakarta.servlet.Filter;
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
    public Filter requestContextFilter() {
        return new RequestContextFilter();
    }
}
''')

add("rag-common/src/main/resources/META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports", r'''
com.fintech.rag.common.config.RagCommonJacksonAutoConfiguration
com.fintech.rag.common.config.RagCommonWebAutoConfiguration
''')

# ============================================================================
# 落盘
# ============================================================================
if __name__ == "__main__":
    for rel, content in FILES.items():
        target = BASE / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print("W +", rel)
    print("---- total:", len(FILES))
