# -*- coding: utf-8 -*-
"""
S2: 生成 rag-api（服务间契约 + 内网接入 SDK）以及 rag-common 的签名工具类
"""
import pathlib

BASE = pathlib.Path(r"D:/AiWorkOut/java-ai/rag-platform")
FILES = {}


def add(rel, content):
    FILES[rel] = content.lstrip("\n")


# ============================================================================
# rag-common 补充：HMAC 签名工具（网关/平台验签、SDK 签名共用同一实现）
# ============================================================================
add("rag-common/src/main/java/com/fintech/rag/common/util/HmacSignatures.java", r'''
package com.fintech.rag.common.util;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/**
 * 应用请求签名工具（HMAC-SHA256）。
 *
 * <p>签名原文（\n 分隔，顺序不可变，否则验签必然失败）：</p>
 * <pre>
 *   METHOD\nPATH\nTIMESTAMP\nNONCE\nBODY_SHA256_HEX
 * </pre>
 *
 * <p>设计要点：</p>
 * <ol>
 *   <li>把 body 的 SHA-256 摘要纳入签名，避免大 body 直接参与 HMAC 计算；</li>
 *   <li>纳入 timestamp + nonce，配合服务端 Redis 实现防重放；</li>
 *   <li>比较采用 {@link MessageDigest#isEqual} 常量时间比较，防时序攻击。</li>
 * </ol>
 *
 * @author rag-platform
 */
public final class HmacSignatures {

    private static final String ALGORITHM_HMAC = "HmacSHA256";
    private static final String ALGORITHM_SHA256 = "SHA-256";

    private HmacSignatures() {
    }

    /**
     * 计算签名。
     *
     * @param appSecret  应用密钥（服务端持密文，验签前解密）
     * @param method     HTTP 方法，如 POST
     * @param path       请求路径，不含 query，如 /internal/chat/completions
     * @param timestamp  毫秒时间戳字符串
     * @param nonce      随机串
     * @param bodySha256 请求体的 SHA-256 十六进制摘要；GET 无 body 传空字符串
     * @return 小写十六进制签名
     */
    public static String sign(String appSecret, String method, String path,
                              String timestamp, String nonce, String bodySha256) {
        String payload = String.join("\n",
                upper(method),
                emptyIfNull(path),
                emptyIfNull(timestamp),
                emptyIfNull(nonce),
                emptyIfNull(bodySha256));
        return hmacSha256Hex(appSecret, payload);
    }

    /** 验签 */
    public static boolean verify(String appSecret, String method, String path,
                                 String timestamp, String nonce, String bodySha256, String signature) {
        if (signature == null || signature.isBlank()) {
            return false;
        }
        String expected = sign(appSecret, method, path, timestamp, nonce, bodySha256);
        return constantTimeEquals(expected, signature);
    }

    /** SHA-256 十六进制摘要 */
    public static String sha256Hex(String content) {
        if (content == null) {
            return "";
        }
        try {
            MessageDigest digest = MessageDigest.getInstance(ALGORITHM_SHA256);
            return toHex(digest.digest(content.getBytes(StandardCharsets.UTF_8)));
        } catch (Exception ex) {
            throw new IllegalStateException("SHA-256 计算失败", ex);
        }
    }

    /** HMAC-SHA256 十六进制 */
    public static String hmacSha256Hex(String secret, String payload) {
        try {
            Mac mac = Mac.getInstance(ALGORITHM_HMAC);
            mac.init(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), ALGORITHM_HMAC));
            return toHex(mac.doFinal(payload.getBytes(StandardCharsets.UTF_8)));
        } catch (Exception ex) {
            throw new IllegalStateException("HMAC-SHA256 计算失败", ex);
        }
    }

    /** 常量时间比较，避免通过响应时间差逐字节爆破签名 */
    public static boolean constantTimeEquals(String a, String b) {
        if (a == null || b == null) {
            return false;
        }
        return MessageDigest.isEqual(
                a.getBytes(StandardCharsets.UTF_8),
                b.getBytes(StandardCharsets.UTF_8));
    }

    private static String toHex(byte[] bytes) {
        StringBuilder sb = new StringBuilder(bytes.length * 2);
        for (byte b : bytes) {
            sb.append(Character.forDigit((b >> 4) & 0xF, 16));
            sb.append(Character.forDigit(b & 0xF, 16));
        }
        return sb.toString();
    }

    private static String upper(String s) {
        return s == null ? "" : s.toUpperCase();
    }

    private static String emptyIfNull(String s) {
        return s == null ? "" : s;
    }
}
''')

# ============================================================================
# rag-api
# ============================================================================
add("rag-api/pom.xml", r'''
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

    <artifactId>rag-api</artifactId>
    <packaging>jar</packaging>
    <name>rag-api</name>
    <description>服务间契约（DTO + Feign Client），同时作为内网业务方接入 SDK</description>

    <dependencies>
        <dependency>
            <groupId>com.fintech.rag</groupId>
            <artifactId>rag-common</artifactId>
        </dependency>
        <dependency>
            <groupId>com.fasterxml.jackson.core</groupId>
            <artifactId>jackson-databind</artifactId>
        </dependency>

        <!--
          OpenFeign 与 Validation 均为 optional：
          只用 DTO（如 rag-gateway 只做转发）的模块不需要被动引入 Feign 全套依赖。
        -->
        <dependency>
            <groupId>org.springframework.cloud</groupId>
            <artifactId>spring-cloud-starter-openfeign</artifactId>
            <optional>true</optional>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
            <optional>true</optional>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-autoconfigure</artifactId>
            <optional>true</optional>
        </dependency>
    </dependencies>
</project>
''')

API = "rag-api/src/main/java/com/fintech/rag/api"

# ---------------------------------------------------------------- 枚举
add(API + "/dto/common/SubjectType.java", r'''
package com.fintech.rag.api.dto.common;

/**
 * 调用主体类型。决定走哪套鉴权与哪套权限模型。
 *
 * @author rag-platform
 */
public enum SubjectType {

    /** 终端用户，权限模型为「人维度」 */
    USER,

    /** 内网应用，权限模型为「应用维度」 */
    APP
}
''')

add(API + "/dto/common/AnswerType.java", r'''
package com.fintech.rag.api.dto.common;

/**
 * 答案类型。
 *
 * <p>{@link #NO_HIT} 与 {@link #GUARDRAIL_BLOCKED} 是金融场景的关键语义：
 * 它们表示「系统明确拒绝回答」，而不是「回答失败」，前端需要区别展示。</p>
 *
 * @author rag-platform
 */
public enum AnswerType {

    /** 正常基于知识库作答（含引用） */
    ANSWERED,

    /** 未召回到任何有效内容，未调用大模型 */
    NO_HIT,

    /** 触发出参护栏被拦截 */
    GUARDRAIL_BLOCKED,

    /** 系统错误 */
    ERROR
}
''')

add(API + "/dto/common/GuardrailType.java", r'''
package com.fintech.rag.api.dto.common;

/**
 * 答案护栏命中类型。
 *
 * @author rag-platform
 */
public enum GuardrailType {

    /** 空召回：相似度全部低于阈值 */
    NO_HIT,

    /** 引用缺失：正文有 [n] 标记但无对应引用 */
    MISSING_CITATION,

    /** 敏感信息：身份证 / 卡号 / 手机号等 */
    SENSITIVE,

    /** 跨知识库越权：引用了未授权知识库内容 */
    CROSS_KB,

    /** 无引用数值：出现利率/额度等数值但无出处 */
    UNSUPPORTED_NUMERIC
}
''')

# ---------------------------------------------------------------- 检索契约
add(API + "/dto/retrieval/RetrievalRequest.java", r'''
package com.fintech.rag.api.dto.retrieval;

import com.fintech.rag.api.dto.common.SubjectType;

import java.math.BigDecimal;
import java.util.List;

/**
 * 检索请求契约。
 *
 * <p><strong>安全约定（务必遵守）：</strong>{@code kbIds} 只能表达「用户勾选的检索范围意图」，
 * 绝不可作为授权依据。rag-retrieval-service 必须按 {@code subjectType + subjectId}
 * 重新向 rag-platform / rag-knowledge 拉取授权知识库集合，再与 kbIds 取交集，
 * 否则前端改一个数字即可越权读取机密制度。</p>
 *
 * @param query       原始问题
 * @param subjectType 主体类型
 * @param subjectId   主体标识（userId / appId）
 * @param kbIds       用户意图范围，可为空表示「全部授权范围」
 * @param filters     业务过滤条件
 * @param options     检索调优参数
 * @param traceId     全链路追踪 ID
 * @param conversationId 会话 ID（可空，仅用于日志关联）
 * @author rag-platform
 */
public record RetrievalRequest(String query,
                               SubjectType subjectType,
                               String subjectId,
                               List<Long> kbIds,
                               Filters filters,
                               Options options,
                               String traceId,
                               Long conversationId) {

    /**
     * 业务过滤条件。
     *
     * @param secretLevelMax 最大密级，用户密级；超过该密级的内容不可召回
     * @param effectiveOnly  是否只召回在生效期内的文档
     * @param bizChannel     业务条线（小微/零售/对公）
     * @param productCode    产品编码
     * @param docIds         限定文档范围（可空）
     */
    public record Filters(Integer secretLevelMax,
                          Boolean effectiveOnly,
                          String bizChannel,
                          String productCode,
                          List<Long> docIds) {

        public static Filters defaults() {
            return new Filters(2, Boolean.TRUE, null, null, null);
        }
    }

    /**
     * 检索调优参数。默认值即生产推荐起点，最终应以评测集回归结果为准。
     *
     * @param topN                  最终返回条数
     * @param similarityThreshold   相似度阈值，低于该值视为不相关（RAGFlow 默认 0.2）
     * @param vectorSimilarityWeight 向量权重，0 纯关键词、1 纯向量（RAGFlow 默认 0.3）
     * @param useRerank             是否二次精排
     */
    public record Options(Integer topN,
                          BigDecimal similarityThreshold,
                          BigDecimal vectorSimilarityWeight,
                          Boolean useRerank) {

        public static Options defaults() {
            return new Options(8, new BigDecimal("0.20"), new BigDecimal("0.30"), Boolean.TRUE);
        }
    }
}
''')

add(API + "/dto/retrieval/RetrievalResponse.java", r'''
package com.fintech.rag.api.dto.retrieval;

import java.util.List;

/**
 * 检索响应契约。
 *
 * @param query          原始问题
 * @param rewrittenQuery Query 改写后的检索式
 * @param chunks         召回片段，已按分数降序
 * @param emptyHit       true 表示空召回，上层必须走「无据不答」分支，禁止调用大模型
 * @param cacheHit       是否命中缓存
 * @param costMs         检索总耗时（含改写、Rerank）
 * @author rag-platform
 */
public record RetrievalResponse(String query,
                                String rewrittenQuery,
                                List<Chunk> chunks,
                                boolean emptyHit,
                                boolean cacheHit,
                                long costMs) {

    /**
     * 召回片段。
     *
     * @param chunkId     片段 ID（RAGFlow chunk id）
     * @param kbId        知识库 ID
     * @param docId       文档 ID
     * @param docName     文档名（用于引用展示）
     * @param versionNo   文档版本号（引用需标注版本，避免引用过期内容）
     * @param chunkIndex  片段在文档内的序号
     * @param pageNo      页码（解析可得时）
     * @param content     片段原文
     * @param score       最终得分
     * @param vectorScore 向量相似度
     * @param termScore   关键词相似度
     */
    public record Chunk(String chunkId,
                        Long kbId,
                        Long docId,
                        String docName,
                        Integer versionNo,
                        Integer chunkIndex,
                        Integer pageNo,
                        String content,
                        Double score,
                        Double vectorScore,
                        Double termScore) {
    }

    /** 空召回的标准返回，上层据此走兜底话术 */
    public static RetrievalResponse empty(String query, String rewrittenQuery, long costMs) {
        return new RetrievalResponse(query, rewrittenQuery, List.of(), true, false, costMs);
    }
}
''')

# ---------------------------------------------------------------- 会话契约
add(API + "/dto/chat/ChatRequest.java", r'''
package com.fintech.rag.api.dto.chat;

import jakarta.validation.constraints.NotBlank;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

/**
 * 问答请求契约。
 *
 * @param conversationId 会话 ID，空则新建会话
 * @param question       用户问题
 * @param kbIds          本次检索的知识库范围（仅意图，非授权依据）
 * @param kbScopeMode    ALL 全部授权 / SELECTED 指定范围
 * @param stream         是否流式。注意：协议层决定（SSE 走 /chat/stream），本字段仅作冗余标记
 * @param bizContext     业务上下文，如 {"channel":"小微","productCode":"P10086"}
 * @param options        生成参数
 * @param withToolCall   是否允许调用业务工具（Function Calling）
 * @author rag-platform
 */
public record ChatRequest(String conversationId,
                          @NotBlank(message = "问题不能为空") String question,
                          List<Long> kbIds,
                          String kbScopeMode,
                          Boolean stream,
                          Map<String, Object> bizContext,
                          Options options,
                          Boolean withToolCall) {

    public static final String SCOPE_ALL = "ALL";
    public static final String SCOPE_SELECTED = "SELECTED";

    /**
     * 生成参数。
     *
     * @param temperature 温度，信贷问答建议 0.1~0.3，越低越稳定
     * @param maxTokens   最大输出 token
     * @param topN        引用条数上限
     * @param needCitation 是否必须带引用（金融场景恒为 true）
     */
    public record Options(BigDecimal temperature,
                          Integer maxTokens,
                          Integer topN,
                          Boolean needCitation) {

        public static Options defaults() {
            return new Options(new BigDecimal("0.20"), 1024, 8, Boolean.TRUE);
        }
    }
}
''')

add(API + "/dto/chat/ChatResponse.java", r'''
package com.fintech.rag.api.dto.chat;

import com.fintech.rag.api.dto.common.AnswerType;

import java.util.List;

/**
 * 问答响应契约。
 *
 * @param messageId      消息 ID
 * @param conversationId 会话 ID
 * @param answerType     答案类型，见 {@link AnswerType}
 * @param answer         答案正文，引用以 [1] [2] 形式内联
 * @param citations      引用列表，与正文 [n] 一一对应
 * @param guardrail      护栏命中情况
 * @param modelCode      实际使用的模型配置编码（便于问题定位与成本归因）
 * @param usage          token 用量
 * @param ttfbMs         首字节耗时
 * @param costMs         端到端耗时
 * @param disclaimer     免责声明
 * @author rag-platform
 */
public record ChatResponse(String messageId,
                           String conversationId,
                           AnswerType answerType,
                           String answer,
                           List<Citation> citations,
                           Guardrail guardrail,
                           String modelCode,
                           Usage usage,
                           int ttfbMs,
                           int costMs,
                           String disclaimer) {

    /**
     * 引用条目。
     *
     * @param seq        序号，对应正文中的 [seq]
     * @param kbId       知识库 ID
     * @param docId      文档 ID
     * @param docName    文档名
     * @param versionNo  版本号
     * @param pageNo     页码
     * @param chunkIndex 片段序号
     * @param score      相关度得分
     * @param content    引用原文片段
     */
    public record Citation(int seq,
                           Long kbId,
                           Long docId,
                           String docName,
                           Integer versionNo,
                           Integer pageNo,
                           Integer chunkIndex,
                           Double score,
                           String content) {
    }

    /**
     * 护栏结果。
     *
     * @param hit    是否命中
     * @param types  命中类型列表，取值见 GuardrailType 名称
     * @param reason 人类可读原因，便于前端提示与日志排查
     */
    public record Guardrail(boolean hit, List<String> types, String reason) {

        public static Guardrail pass() {
            return new Guardrail(false, List.of(), null);
        }
    }

    /**
     * token 用量。
     *
     * @param inputTokens  输入 token
     * @param outputTokens 输出 token
     * @param totalTokens  合计
     */
    public record Usage(int inputTokens, int outputTokens, int totalTokens) {

        public static Usage zero() {
            return new Usage(0, 0, 0);
        }
    }
}
''')

# ---------------------------------------------------------------- 知识库契约
add(API + "/dto/knowledge/KbBrief.java", r'''
package com.fintech.rag.api.dto.knowledge;

/**
 * 知识库摘要（授权查询结果）。
 *
 * @param kbId           知识库 ID
 * @param kbCode         知识库编码
 * @param kbName         知识库名称
 * @param category       PRODUCT / POLICY / REGULATION / INTERNAL / CASE
 * @param secretLevel    密级 1公开 2内部 3机密
 * @param version        版本号，用于检索缓存 Key 构造与失效
 * @param permission     READ / MANAGE
 * @param docCount       已就绪文档数，0 表示尚未就绪
 * @author rag-platform
 */
public record KbBrief(Long kbId,
                      String kbCode,
                      String kbName,
                      String category,
                      Integer secretLevel,
                      Long version,
                      String permission,
                      Integer docCount) {
}
''')

add(API + "/dto/knowledge/DocumentMeta.java", r'''
package com.fintech.rag.api.dto.knowledge;

import java.time.LocalDate;

/**
 * 文档元数据（检索结果二次过滤与引用展示使用）。
 *
 * @param docId         文档 ID
 * @param kbId          知识库 ID
 * @param docName       文件名
 * @param versionNo     当前版本号
 * @param secretLevel   密级
 * @param effectiveDate 生效日期
 * @param expireDate    失效日期，null 表示长期有效
 * @param parseStatus   解析状态
 * @param chunkNum      分片数
 * @author rag-platform
 */
public record DocumentMeta(Long docId,
                           Long kbId,
                           String docName,
                           Integer versionNo,
                           Integer secretLevel,
                           LocalDate effectiveDate,
                           LocalDate expireDate,
                           String parseStatus,
                           Integer chunkNum) {
}
''')

# ---------------------------------------------------------------- 平台契约
add(API + "/dto/platform/AppSignVerifyRequest.java", r'''
package com.fintech.rag.api.dto.platform;

/**
 * 应用签名验签请求。
 *
 * <p>由各服务的鉴权拦截器在收到内网流量时构造并调用 rag-platform-service。</p>
 *
 * @param appId      应用 ID
 * @param method     HTTP 方法
 * @param path       请求路径（不含 query）
 * @param timestamp  毫秒时间戳
 * @param nonce      随机串
 * @param signature  调用方签名
 * @param bodySha256 请求体 SHA-256，GET 传空串
 * @param clientIp   调用方 IP，用于 IP 白名单校验
 * @author rag-platform
 */
public record AppSignVerifyRequest(String appId,
                                   String method,
                                   String path,
                                   String timestamp,
                                   String nonce,
                                   String signature,
                                   String bodySha256,
                                   String clientIp) {
}
''')

add(API + "/dto/platform/AppSignVerifyResult.java", r'''
package com.fintech.rag.api.dto.platform;

/**
 * 应用签名验签结果。
 *
 * @param valid       是否通过
 * @param reason      失败原因
 * @param appId       应用 ID
 * @param appName     应用名称
 * @param qpsLimit    QPS 上限
 * @param dailyLimit  日调用量上限
 * @param ipWhitelist IP 白名单（逗号分隔）
 * @author rag-platform
 */
public record AppSignVerifyResult(boolean valid,
                                  String reason,
                                  String appId,
                                  String appName,
                                  Integer qpsLimit,
                                  Long dailyLimit,
                                  String ipWhitelist) {

    public static AppSignVerifyResult rejected(String reason) {
        return new AppSignVerifyResult(false, reason, null, null, null, null, null);
    }
}
''')

add(API + "/dto/platform/ModelConfigDTO.java", r'''
package com.fintech.rag.api.dto.platform;

/**
 * 模型配置（供 rag-chat-service 做动态路由）。
 *
 * <p><strong>安全提醒：</strong>{@code apiKey} 通过 HTTP 在可信内网传输是过渡方案。
 * 生产环境建议改为「Nacos 加密配置下发 + 本地解密」，本接口只回传 configCode 与模型名，
 * 避免模型密钥在经过多个服务的内存与日志时被意外落盘。</p>
 *
 * @param configCode     配置编码，如 PRIMARY_CLOUD / SENSITIVE_PRIVATE
 * @param provider       deepseek / qwen / openai-compatible / vllm
 * @param baseUrl        API 地址
 * @param apiKey         密钥
 * @param modelName      模型名
 * @param temperature    默认温度
 * @param maxTokens      默认最大输出 token
 * @param sensitiveLevel 可处理的最大密级
 * @param priority       路由优先级，越小越优先
 * @param isDefault      是否默认配置
 * @author rag-platform
 */
public record ModelConfigDTO(String configCode,
                             String provider,
                             String baseUrl,
                             String apiKey,
                             String modelName,
                             Double temperature,
                             Integer maxTokens,
                             Integer sensitiveLevel,
                             Integer priority,
                             Boolean isDefault) {
}
''')

add(API + "/dto/platform/SensitiveRuleDTO.java", r'''
package com.fintech.rag.api.dto.platform;

/**
 * 敏感信息规则（供 rag-chat-service 输出侧脱敏）。
 *
 * @param ruleCode   规则编码
 * @param ruleName   规则名称
 * @param ruleType   REGEX / DICT
 * @param pattern    正则表达式或 JSON 数组词典
 * @param maskChar   掩码字符
 * @param keepPrefix 保留前缀长度
 * @param keepSuffix 保留后缀长度
 * @param action     MASK 脱敏 / BLOCK 拦截 / WARN 仅告警
 * @author rag-platform
 */
public record SensitiveRuleDTO(String ruleCode,
                               String ruleName,
                               String ruleType,
                               String pattern,
                               String maskChar,
                               Integer keepPrefix,
                               Integer keepSuffix,
                               String action) {
}
''')

add(API + "/dto/platform/AuditLogDTO.java", r'''
package com.fintech.rag.api.dto.platform;

import java.util.List;

/**
 * 审计日志（各服务异步上报）。
 *
 * <p>金融合规要求：谁、何时、问了什么、召回了哪些文档，必须可追溯。
 * 因此本 DTO 的字段不允许随意裁剪。</p>
 *
 * @param traceId       追踪 ID
 * @param eventType     QUERY / RETRIEVAL / INGEST / KB_CHANGE / AUTH / CONFIG_CHANGE
 * @param requestSource DMZ_WEB / SF_INNER_APP
 * @param subjectType   USER / APP
 * @param subjectId     主体标识
 * @param subjectName   主体名称
 * @param clientIp      客户端 IP
 * @param resource      资源
 * @param kbIds         涉及知识库
 * @param docIds        涉及文档
 * @param detailJson    明细 JSON（已脱敏）
 * @param result        1成功 0失败
 * @param errorCode     错误码
 * @param costMs        耗时
 * @param eventTime     事件时间（毫秒时间戳）
 * @author rag-platform
 */
public record AuditLogDTO(String traceId,
                          String eventType,
                          String requestSource,
                          String subjectType,
                          String subjectId,
                          String subjectName,
                          String clientIp,
                          String resource,
                          List<Long> kbIds,
                          List<Long> docIds,
                          String detailJson,
                          Integer result,
                          String errorCode,
                          Integer costMs,
                          Long eventTime) {
}
''')

# ---------------------------------------------------------------- Feign 客户端
add(API + "/client/KnowledgeClient.java", r'''
package com.fintech.rag.api.client;

import com.fintech.rag.api.dto.knowledge.DocumentMeta;
import com.fintech.rag.api.dto.knowledge.KbBrief;
import com.fintech.rag.common.core.R;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;

import java.util.List;
import java.util.Map;

/**
 * 知识库服务契约。
 *
 * <p>调用方：rag-chat-service、rag-retrieval-service。</p>
 *
 * <p><strong>降级策略：fail-close。</strong>授权查询失败时必须拒绝本次请求（返回无权限），
 * 绝不可降级为「返回全量知识库」，否则一次依赖抖动就会变成数据泄漏事故。</p>
 *
 * @author rag-platform
 */
@FeignClient(name = "rag-knowledge-service", contextId = "knowledgeClient", path = "/api/kb")
public interface KnowledgeClient {

    /**
     * 查询指定主体已授权的知识库（<b>越权防护的授权真源</b>）。
     *
     * @param subjectType USER / APP
     * @param subjectId   userId / appId
     * @param roleCodes   用户角色编码，逗号分隔（用于按角色授权）；APP 主体传空
     * @param deptId      用户部门 ID（用于按部门授权）；APP 主体传空
     */
    @GetMapping("/authorized")
    R<List<KbBrief>> listAuthorizedKbs(@RequestParam("subjectType") String subjectType,
                                       @RequestParam("subjectId") String subjectId,
                                       @RequestParam(value = "roleCodes", required = false) String roleCodes,
                                       @RequestParam(value = "deptId", required = false) Long deptId);

    /** 批量查询文档元数据（检索结果二次过滤用） */
    @PostMapping("/documents/meta")
    R<List<DocumentMeta>> listDocumentMeta(@RequestBody List<Long> docIds);

    /** 批量获取知识库版本号（检索缓存 Key 构造用） */
    @PostMapping("/version")
    R<Map<String, Long>> getKbVersions(@RequestBody List<Long> kbIds);
}
''')

add(API + "/client/RetrievalClient.java", r'''
package com.fintech.rag.api.client;

import com.fintech.rag.api.dto.retrieval.RetrievalRequest;
import com.fintech.rag.api.dto.retrieval.RetrievalResponse;
import com.fintech.rag.common.core.R;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;

/**
 * 检索服务契约。
 *
 * <p>调用方：rag-chat-service、检索工作台、内网业务微服务。</p>
 *
 * <p><strong>降级策略：fail-close。</strong>检索不可用时返回「服务繁忙」，
 * 绝不可降级为「不检索直接让大模型自由作答」——这等同于放弃引用与合规底线。</p>
 *
 * @author rag-platform
 */
@FeignClient(name = "rag-retrieval-service", contextId = "retrievalClient", path = "/api/retrieval")
public interface RetrievalClient {

    /** 执行检索 */
    @PostMapping("/search")
    R<RetrievalResponse> search(@RequestBody RetrievalRequest request);
}
''')

add(API + "/client/PlatformClient.java", r'''
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
''')

# ---------------------------------------------------------------- 拦截器
add(API + "/client/interceptor/TracePropagationInterceptor.java", r'''
package com.fintech.rag.api.client.interceptor;

import com.fintech.rag.common.constant.RagHeaders;
import com.fintech.rag.common.context.RequestContext;
import com.fintech.rag.common.util.TraceIds;
import feign.RequestInterceptor;
import feign.RequestTemplate;

/**
 * Feign 追踪透传拦截器。
 *
 * <p><strong>绝不在此处添加 {@code X-Request-Source}。</strong>
 * 来源标识只能由 DMZ 网关注入；内网 Feign 客户端一旦全局带上它，
 * AI 服务侧的反向拦截会直接把内网调用判为伪造并返回 403。</p>
 *
 * @author rag-platform
 */
public class TracePropagationInterceptor implements RequestInterceptor {

    @Override
    public void apply(RequestTemplate template) {
        String traceId = RequestContext.currentTraceId();
        template.header(RagHeaders.TRACE_ID, TraceIds.resolve(traceId));
    }
}
''')

add(API + "/client/interceptor/AppSignatureRequestInterceptor.java", r'''
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
''')

# ---------------------------------------------------------------- 配置
add(API + "/config/RagSdkProperties.java", r'''
package com.fintech.rag.api.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * 内网业务方接入 SDK 配置。
 *
 * <pre>
 * rag:
 *   sdk:
 *     enabled: true
 *     app-id: biz_credit_apply
 *     app-secret: ${RAG_APP_SECRET}
 * </pre>
 *
 * <p>密钥禁止硬编码到配置文件提交到仓库，必须走环境变量或配置中心加密配置。</p>
 *
 * @author rag-platform
 */
@ConfigurationProperties(prefix = "rag.sdk")
public class RagSdkProperties {

    /** 是否启用 SDK 签名拦截器 */
    private boolean enabled = false;

    /** 应用 ID */
    private String appId;

    /** 应用密钥 */
    private String appSecret;

    public boolean isEnabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }

    public String getAppId() {
        return appId;
    }

    public void setAppId(String appId) {
        this.appId = appId;
    }

    public String getAppSecret() {
        return appSecret;
    }

    public void setAppSecret(String appSecret) {
        this.appSecret = appSecret;
    }
}
''')

add(API + "/config/RagApiAutoConfiguration.java", r'''
package com.fintech.rag.api.config;

import com.fintech.rag.api.client.interceptor.AppSignatureRequestInterceptor;
import com.fintech.rag.api.client.interceptor.TracePropagationInterceptor;
import feign.RequestInterceptor;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;

/**
 * rag-api 自动装配：统一为所有 Feign 客户端挂上追踪透传与（可选的）应用签名。
 *
 * <p>注意本配置<b>不会</b>自动开启 Feign 扫描。各服务需显式声明
 * {@code @EnableFeignClients(clients = {KnowledgeClient.class, ...})}，
 * 显式优于隐式：可以清楚看到每个服务依赖了哪些下游。</p>
 *
 * @author rag-platform
 */
@AutoConfiguration
@ConditionalOnClass(RequestInterceptor.class)
@EnableConfigurationProperties(RagSdkProperties.class)
public class RagApiAutoConfiguration {

    @Bean
    @ConditionalOnMissingBean(name = "tracePropagationInterceptor")
    public RequestInterceptor tracePropagationInterceptor() {
        return new TracePropagationInterceptor();
    }

    @Bean
    @ConditionalOnMissingBean(name = "appSignatureRequestInterceptor")
    public RequestInterceptor appSignatureRequestInterceptor(RagSdkProperties properties) {
        return new AppSignatureRequestInterceptor(properties);
    }
}
''')

add("rag-api/src/main/resources/META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports", r'''
com.fintech.rag.api.config.RagApiAutoConfiguration
''')

if __name__ == "__main__":
    for rel, content in FILES.items():
        target = BASE / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print("W +", rel)
    print("---- total:", len(FILES))
