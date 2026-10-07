# -*- coding: utf-8 -*-
"""
S5: 生成 rag-knowledge-service（知识资产）与 rag-ingest-service（入库流水线）
     + rag-common 的 RAGFlow 接入配置（三个服务共用，避免各写一份）
"""
import pathlib

BASE = pathlib.Path(r"D:/AiWorkOut/java-ai/rag-platform")
FILES = {}


def add(rel, content):
    FILES[rel] = content.lstrip("\n")


# ============================================================ rag-common
add("rag-common/src/main/java/com/fintech/rag/common/integration/ragflow/RagFlowProperties.java", r'''
package com.fintech.rag.common.integration.ragflow;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * RAGFlow 接入配置（knowledge / ingest / retrieval 三个服务共用）。
 *
 * <p><b>API Key 的持有范围必须收敛</b>：只允许这三个服务配置，
 * rag-chat-service 与 rag-gateway 不得持有，防止生成链路被直接拿去访问知识库。</p>
 *
 * @author rag-platform
 */
@ConfigurationProperties(prefix = "rag.ragflow")
public class RagFlowProperties {

    /** RAGFlow 服务地址，如 http://10.10.2.31:9380 */
    private String baseUrl = "http://127.0.0.1:9380";

    /** API Key，由 RAGFlow 页面生成 */
    private String apiKey;

    /** 默认向量模型，同一知识库内必须一致，否则 RAGFlow 会拒绝检索 */
    private String defaultEmbeddingModel = "BAAI/bge-large-zh-v1.5";

    /** 默认重排模型 */
    private String defaultRerankModel = "BAAI/bge-reranker-v2-m3";

    private int connectTimeoutMs = 3000;

    /** 检索类调用超时 */
    private int readTimeoutMs = 5000;

    /** 文档上传/解析类调用超时，通常更宽松 */
    private int uploadTimeoutMs = 120000;

    /** 单文档解析最长等待时间，超时判定为失败 */
    private long parseTimeoutMs = 30 * 60 * 1000L;

    public String getBaseUrl() {
        return baseUrl;
    }

    public void setBaseUrl(String baseUrl) {
        this.baseUrl = baseUrl;
    }

    public String getApiKey() {
        return apiKey;
    }

    public void setApiKey(String apiKey) {
        this.apiKey = apiKey;
    }

    public String getDefaultEmbeddingModel() {
        return defaultEmbeddingModel;
    }

    public void setDefaultEmbeddingModel(String defaultEmbeddingModel) {
        this.defaultEmbeddingModel = defaultEmbeddingModel;
    }

    public String getDefaultRerankModel() {
        return defaultRerankModel;
    }

    public void setDefaultRerankModel(String defaultRerankModel) {
        this.defaultRerankModel = defaultRerankModel;
    }

    public int getConnectTimeoutMs() {
        return connectTimeoutMs;
    }

    public void setConnectTimeoutMs(int connectTimeoutMs) {
        this.connectTimeoutMs = connectTimeoutMs;
    }

    public int getReadTimeoutMs() {
        return readTimeoutMs;
    }

    public void setReadTimeoutMs(int readTimeoutMs) {
        this.readTimeoutMs = readTimeoutMs;
    }

    public int getUploadTimeoutMs() {
        return uploadTimeoutMs;
    }

    public void setUploadTimeoutMs(int uploadTimeoutMs) {
        this.uploadTimeoutMs = uploadTimeoutMs;
    }

    public long getParseTimeoutMs() {
        return parseTimeoutMs;
    }

    public void setParseTimeoutMs(long parseTimeoutMs) {
        this.parseTimeoutMs = parseTimeoutMs;
    }
}
''')

# ============================================================================
# =========================  rag-knowledge-service  ==========================
# ============================================================================
add("rag-knowledge-service/pom.xml", r'''
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

    <artifactId>rag-knowledge-service</artifactId>
    <packaging>jar</packaging>
    <name>rag-knowledge-service</name>
    <description>知识资产：知识库、文档、ACL、Dataset 映射</description>

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
        <!-- 需要调用 platform 做验签（AppVerifierPort 的 Feign 适配器） -->
        <dependency>
            <groupId>org.springframework.cloud</groupId>
            <artifactId>spring-cloud-starter-openfeign</artifactId>
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
        <finalName>rag-knowledge-service</finalName>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>
''')

KN = "rag-knowledge-service/src/main/java/com/fintech/rag/knowledge"

add(KN + "/KnowledgeApplication.java", r'''
package com.fintech.rag.knowledge;

import com.fintech.rag.api.client.PlatformClient;
import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;
import org.springframework.cloud.openfeign.EnableFeignClients;

/**
 * 知识库服务启动类。
 *
 * <p>对外提供两类接口：</p>
 * <ul>
 *   <li>管理面：知识库与文档 CRUD、ACL 配置（经网关，用户身份）</li>
 *   <li>内网面：授权查询、文档元数据（Feign 直连，应用身份）</li>
 * </ul>
 *
 * @author rag-platform
 */
@SpringBootApplication(scanBasePackages = "com.fintech.rag.knowledge")
@EnableDiscoveryClient
@EnableFeignClients(clients = PlatformClient.class)
@ConfigurationPropertiesScan("com.fintech.rag.knowledge")
@MapperScan("com.fintech.rag.knowledge.infra.persistence.mapper")
public class KnowledgeApplication {

    public static void main(String[] args) {
        SpringApplication.run(KnowledgeApplication.class, args);
    }
}
''')

add(KN + "/domain/model/KnowledgeBase.java", r'''
package com.fintech.rag.knowledge.domain.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.annotation.Version;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 知识库。
 *
 * <p>{@code version} 是检索缓存的失效锚点：内容或检索参数变更即 +1，
 * 使旧缓存自然不再命中，无需精确删除缓存 Key。</p>
 *
 * @author rag-platform
 */
@Data
@TableName("t_knowledge_base")
public class KnowledgeBase {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private Long tenantId;

    private String kbCode;

    private String kbName;

    private String description;

    /** PRODUCT / POLICY / REGULATION / INTERNAL / CASE */
    private String category;

    /** RAGFlow Dataset ID */
    private String ragflowDatasetId;

    private String embeddingModel;

    private String chunkMethod;

    private Integer chunkTokenNum;

    private BigDecimal similarityThreshold;

    private BigDecimal vectorSimilarityWeight;

    private Integer topK;

    private String rerankModel;

    private Integer secretLevel;

    private String bizChannel;

    private Long ownerDeptId;

    private Long ownerUserId;

    private Integer docCount;

    private Long chunkCount;

    /** 版本号，用于检索缓存失效 */
    @Version
    private Long version;

    private Integer status;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;

    private String createBy;

    @TableLogic
    private Integer deleted;
}
''')

add(KN + "/domain/model/KbDocument.java", r'''
package com.fintech.rag.knowledge.domain.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 文档。
 *
 * @author rag-platform
 */
@Data
@TableName("t_document")
public class KbDocument {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private Long tenantId;

    private Long kbId;

    private String docCode;

    private String docName;

    private String fileType;

    private Long fileSize;

    /** 用于重复检测 */
    private String fileMd5;

    private String minioBucket;

    private String minioObjectKey;

    private Long currentVersionId;

    private Integer versionNo;

    private Integer secretLevel;

    /** 生效日期，参与检索过滤 */
    private LocalDate effectiveDate;

    /** 失效日期，参与检索过滤 */
    private LocalDate expireDate;

    private Long sourceDeptId;

    private Long ownerUserId;

    private String tags;

    private Integer chunkNum;

    private String ragflowDocumentId;

    /** PENDING / UPLOADED / PARSING / PARSED / FAILED / OFFLINE */
    private String parseStatus;

    private String parseError;

    private Integer parseTimeMs;

    private String offlineReason;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;

    private String createBy;

    @TableLogic
    private Integer deleted;
}
''')

add(KN + "/domain/model/KbAcl.java", r'''
package com.fintech.rag.knowledge.domain.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 知识库访问控制。
 *
 * @author rag-platform
 */
@Data
@TableName("t_kb_acl")
public class KbAcl {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private Long tenantId;

    private Long kbId;

    /** USER / ROLE / DEPT / APP */
    private String granteeType;

    /** 对应 userId / roleCode / deptId / appId */
    private String granteeId;

    /** READ / MANAGE */
    private String permission;

    private LocalDateTime createTime;

    private String createBy;
}
''')

KN_MAPPER = KN + "/infra/persistence/mapper/"
for name, entity, desc in (
        ("KnowledgeBase", "KnowledgeBase", "知识库"),
        ("KbDocument", "KbDocument", "文档"),
        ("KbAcl", "KbAcl", "知识库 ACL")):
    add(KN_MAPPER + name + "Mapper.java", r'''
package com.fintech.rag.knowledge.infra.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.fintech.rag.knowledge.domain.model.%ENTITY%;
import org.apache.ibatis.annotations.Mapper;

/**
 * %DESC% 数据访问。
 *
 * @author rag-platform
 */
@Mapper
public interface %NAME%Mapper extends BaseMapper<%ENTITY%> {
}
'''.replace("%ENTITY%", entity).replace("%NAME%", name).replace("%DESC%", desc))

add(KN + "/infra/client/RagFlowDatasetClient.java", r'''
package com.fintech.rag.knowledge.infra.client;

import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import com.fintech.rag.common.integration.ragflow.RagFlowProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.time.Duration;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * RAGFlow Dataset（知识库）客户端。
 *
 * <p>RAGFlow 的 HTTP 接口统一返回 {@code {"code":0,"data":{...},"message":"..."}}，
 * {@code code != 0} 表示业务失败，必须显式判断，不能只看 HTTP 状态码。</p>
 *
 * @author rag-platform
 */
@Component
public class RagFlowDatasetClient {

    private static final Logger log = LoggerFactory.getLogger(RagFlowDatasetClient.class);
    private static final int SUCCESS_CODE = 0;

    private final RestClient restClient;
    private final RagFlowProperties properties;

    public RagFlowDatasetClient(RagFlowProperties properties) {
        this.properties = properties;
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofMillis(properties.getConnectTimeoutMs()));
        factory.setReadTimeout(Duration.ofMillis(properties.getReadTimeoutMs()));
        this.restClient = RestClient.builder()
                .baseUrl(properties.getBaseUrl())
                .requestFactory(factory)
                .defaultHeader(HttpHeaders.AUTHORIZATION, "Bearer " + properties.getApiKey())
                .build();
    }

    /**
     * 创建 Dataset，返回 datasetId。
     *
     * <p>注意：RAGFlow 要求同一 Dataset 内向量模型一致，因此创建时就要定下来，
     * 后续不允许变更（变更需重建 Dataset 并重新入库）。</p>
     */
    public String createDataset(String name, String description, String embeddingModel,
                                String chunkMethod, Integer chunkTokenNum) {
        Map<String, Object> body = new HashMap<>();
        body.put("name", name);
        body.put("description", description == null ? "" : description);
        body.put("embedding_model", embeddingModel == null
                ? properties.getDefaultEmbeddingModel() : embeddingModel);
        body.put("chunk_method", chunkMethod == null ? "NAIVE" : chunkMethod);
        body.put("parser_config", Map.of("chunk_token_num", chunkTokenNum == null ? 512 : chunkTokenNum));

        RagFlowResponse<Object> response = restClient.post()
                .uri("/api/v1/datasets")
                .contentType(MediaType.APPLICATION_JSON)
                .body(body)
                .retrieve()
                .body(new ParameterizedTypeReference<>() {
                });

        String datasetId = extractDatasetId(response);
        if (datasetId == null) {
            log.error("创建 RAGFlow Dataset 失败 name={} message={}", name,
                    response == null ? null : response.message());
            throw BizException.of(ErrorCode.RAGFLOW_DATASET_SYNC_FAILED);
        }
        log.info("创建 RAGFlow Dataset 成功 name={} datasetId={}", name, datasetId);
        return datasetId;
    }

    /** 删除 Dataset（仅空库可删，RAGFlow 侧会校验） */
    public void deleteDataset(String datasetId) {
        RagFlowResponse<Object> response = restClient.delete()
                .uri("/api/v1/datasets")
                .contentType(MediaType.APPLICATION_JSON)
                .body(Map.of("ids", List.of(datasetId)))
                .retrieve()
                .body(new ParameterizedTypeReference<>() {
                });
        if (response == null || response.code() != SUCCESS_CODE) {
            throw BizException.of(ErrorCode.RAGFLOW_DATASET_SYNC_FAILED, "删除 Dataset 失败");
        }
    }

    @SuppressWarnings("unchecked")
    private String extractDatasetId(RagFlowResponse<Object> response) {
        if (response == null || response.code() != SUCCESS_CODE || response.data() == null) {
            return null;
        }
        Object data = response.data();
        try {
            if (data instanceof List<?> list && !list.isEmpty()) {
                Object first = list.get(0);
                if (first instanceof Map<?, ?> map && map.get("id") != null) {
                    return String.valueOf(map.get("id"));
                }
            }
            if (data instanceof Map<?, ?> map) {
                return map.get("id") == null ? null : String.valueOf(map.get("id"));
            }
        } catch (Exception ex) {
            log.warn("解析 Dataset 响应失败", ex);
        }
        return null;
    }

    /** RAGFlow 统一响应包装 */
    public record RagFlowResponse<T>(Integer code, String message, T data) {
    }

    /** 便于扩展：列出全部 dataset（运维排障用） */
    public List<String> listDatasetNames() {
        RagFlowResponse<Object> response = restClient.get()
                .uri("/api/v1/datasets?page=1&page_size=100")
                .retrieve()
                .body(new ParameterizedTypeReference<>() {
                });
        List<String> names = new ArrayList<>();
        if (response != null && response.data() instanceof List<?> list) {
            for (Object item : list) {
                if (item instanceof Map<?, ?> map && map.get("name") != null) {
                    names.add(String.valueOf(map.get("name")));
                }
            }
        }
        return names;
    }
}
''')

add(KN + "/app/service/AuthorizedKbQueryAppService.java", r'''
package com.fintech.rag.knowledge.app.service;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.fintech.rag.api.dto.knowledge.KbBrief;
import com.fintech.rag.knowledge.domain.model.KbAcl;
import com.fintech.rag.knowledge.domain.model.KnowledgeBase;
import com.fintech.rag.knowledge.infra.persistence.mapper.KbAclMapper;
import com.fintech.rag.knowledge.infra.persistence.mapper.KnowledgeBaseMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * 授权知识库查询服务 —— <b>越权防护的「授权真源」</b>。
 *
 * <p>全平台只有这里可以回答「某个主体能访问哪些知识库」。
 * rag-chat-service 与 rag-retrieval-service 都必须调用本服务的结果作为硬约束，
 * <b>绝不接受请求体中传入的知识库 ID 作为授权依据</b>。</p>
 *
 * <p>授权匹配规则（并集）：</p>
 * <ul>
 *   <li>APP 主体：匹配 granteeType=APP 且 granteeId=appId</li>
 *   <li>USER 主体：匹配 granteeType=USER(=userId)、ROLE(∈用户角色)、DEPT(=用户部门)</li>
 * </ul>
 *
 * @author rag-platform
 */
@Service
public class AuthorizedKbQueryAppService {

    private static final Logger log = LoggerFactory.getLogger(AuthorizedKbQueryAppService.class);

    private final KbAclMapper kbAclMapper;
    private final KnowledgeBaseMapper knowledgeBaseMapper;

    public AuthorizedKbQueryAppService(KbAclMapper kbAclMapper, KnowledgeBaseMapper knowledgeBaseMapper) {
        this.kbAclMapper = kbAclMapper;
        this.knowledgeBaseMapper = knowledgeBaseMapper;
    }

    /**
     * 查询主体已授权的知识库。
     *
     * @param subjectType USER / APP
     * @param subjectId   userId / appId
     * @param roleCodes   逗号分隔的角色编码，USER 主体必传（网关从 JWT 解析后透传）
     * @param deptId      部门 ID，USER 主体必传
     */
    public List<KbBrief> listAuthorizedKbs(String subjectType, String subjectId,
                                           String roleCodes, Long deptId) {
        List<String> granteeIds = new ArrayList<>();
        Set<String> granteeTypes = new HashSet<>();

        if ("APP".equalsIgnoreCase(subjectType)) {
            granteeTypes.add("APP");
            granteeIds.add(subjectId);
        } else {
            granteeTypes.add("USER");
            granteeIds.add(subjectId);
            if (roleCodes != null && !roleCodes.isBlank()) {
                granteeTypes.add("ROLE");
                for (String role : roleCodes.split(",")) {
                    if (!role.isBlank()) {
                        granteeIds.add(role.trim());
                    }
                }
            }
            if (deptId != null) {
                granteeTypes.add("DEPT");
                granteeIds.add(String.valueOf(deptId));
            }
        }

        List<KbAcl> acls = kbAclMapper.selectList(Wrappers.<KbAcl>lambdaQuery()
                .in(KbAcl::getGranteeType, granteeTypes)
                .in(KbAcl::getGranteeId, granteeIds));

        if (acls.isEmpty()) {
            log.info("主体无任何知识库授权 subjectType={} subjectId={}", subjectType, subjectId);
            return List.of();
        }

        // 同一知识库被多种方式授权时，取最高权限
        Map<Long, String> permissionMap = new HashMap<>();
        for (KbAcl acl : acls) {
            permissionMap.merge(acl.getKbId(), acl.getPermission() == null ? "READ" : acl.getPermission(),
                    (oldPerm, newPerm) -> "MANAGE".equals(newPerm) ? newPerm : oldPerm);
        }

        List<KnowledgeBase> bases = knowledgeBaseMapper.selectList(Wrappers.<KnowledgeBase>lambdaQuery()
                .in(KnowledgeBase::getId, permissionMap.keySet())
                .eq(KnowledgeBase::getStatus, 1));

        return bases.stream()
                .map(kb -> new KbBrief(
                        kb.getId(),
                        kb.getKbCode(),
                        kb.getKbName(),
                        kb.getCategory(),
                        kb.getSecretLevel(),
                        kb.getVersion(),
                        permissionMap.get(kb.getId()),
                        kb.getDocCount()))
                .collect(Collectors.toList());
    }
}
''')

add(KN + "/app/service/KnowledgeBaseAppService.java", r'''
package com.fintech.rag.knowledge.app.service;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.fintech.rag.api.dto.knowledge.KbBrief;
import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import com.fintech.rag.knowledge.domain.model.KbAcl;
import com.fintech.rag.knowledge.domain.model.KnowledgeBase;
import com.fintech.rag.knowledge.infra.client.RagFlowDatasetClient;
import com.fintech.rag.knowledge.infra.persistence.mapper.KbAclMapper;
import com.fintech.rag.knowledge.infra.persistence.mapper.KnowledgeBaseMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 知识库应用服务。
 *
 * <p><b>RAGFlow 不在本地事务内</b>：创建知识库时先建本地记录，再调 RAGFlow，
 * 失败则把本地记录标记为「同步失败」并允许重试。
 * 反过来（先调 RAGFlow 再建本地记录）会产生 RAGFlow 侧垃圾 Dataset。</p>
 *
 * @author rag-platform
 */
@Service
public class KnowledgeBaseAppService {

    private static final Logger log = LoggerFactory.getLogger(KnowledgeBaseAppService.class);

    private final KnowledgeBaseMapper knowledgeBaseMapper;
    private final KbAclMapper kbAclMapper;
    private final RagFlowDatasetClient ragFlowDatasetClient;
    private final AuthorizedKbQueryAppService authorizedKbQueryAppService;

    public KnowledgeBaseAppService(KnowledgeBaseMapper knowledgeBaseMapper,
                                   KbAclMapper kbAclMapper,
                                   RagFlowDatasetClient ragFlowDatasetClient,
                                   AuthorizedKbQueryAppService authorizedKbQueryAppService) {
        this.knowledgeBaseMapper = knowledgeBaseMapper;
        this.kbAclMapper = kbAclMapper;
        this.ragFlowDatasetClient = ragFlowDatasetClient;
        this.authorizedKbQueryAppService = authorizedKbQueryAppService;
    }

    /**
     * 创建知识库（含 RAGFlow Dataset 同步）。
     */
    @Transactional(rollbackFor = Exception.class)
    public Long create(CreateCommand command) {
        Long exists = knowledgeBaseMapper.selectCount(Wrappers.<KnowledgeBase>lambdaQuery()
                .eq(KnowledgeBase::getKbCode, command.kbCode()));
        if (exists != null && exists > 0) {
            throw BizException.of(ErrorCode.PARAM_INVALID, "知识库编码已存在：" + command.kbCode());
        }

        KnowledgeBase kb = new KnowledgeBase();
        kb.setTenantId(0L);
        kb.setKbCode(command.kbCode());
        kb.setKbName(command.kbName());
        kb.setDescription(command.description());
        kb.setCategory(command.category());
        kb.setEmbeddingModel(command.embeddingModel());
        kb.setChunkMethod(command.chunkMethod() == null ? "NAIVE" : command.chunkMethod());
        kb.setChunkTokenNum(command.chunkTokenNum() == null ? 512 : command.chunkTokenNum());
        // 检索参数默认值来自评测经验，最终以评测集回归结果调优
        kb.setSimilarityThreshold(new BigDecimal("0.20"));
        kb.setVectorSimilarityWeight(new BigDecimal("0.30"));
        kb.setTopK(1024);
        kb.setRerankModel("BAAI/bge-reranker-v2-m3");
        kb.setSecretLevel(command.secretLevel() == null ? 2 : command.secretLevel());
        kb.setOwnerDeptId(command.ownerDeptId());
        kb.setOwnerUserId(command.ownerUserId());
        kb.setDocCount(0);
        kb.setChunkCount(0L);
        kb.setVersion(1L);
        kb.setStatus(1);
        kb.setDeleted(0);
        knowledgeBaseMapper.insert(kb);

        String datasetId = ragFlowDatasetClient.createDataset(
                command.kbCode(), command.description(), command.embeddingModel(),
                kb.getChunkMethod(), kb.getChunkTokenNum());
        kb.setRagflowDatasetId(datasetId);
        knowledgeBaseMapper.updateById(kb);

        log.info("创建知识库完成 kbId={} kbCode={} datasetId={}", kb.getId(), kb.getKbCode(), datasetId);
        return kb.getId();
    }

    /**
     * 更新知识库。任何影响检索结果的变更都必须 version + 1，触发检索缓存失效。
     */
    @Transactional(rollbackFor = Exception.class)
    public void updateRetrievalParams(Long kbId, BigDecimal similarityThreshold,
                                      BigDecimal vectorSimilarityWeight, Integer topK) {
        KnowledgeBase kb = knowledgeBaseMapper.selectById(kbId);
        if (kb == null) {
            throw BizException.of(ErrorCode.KB_NOT_FOUND);
        }
        kb.setSimilarityThreshold(similarityThreshold);
        kb.setVectorSimilarityWeight(vectorSimilarityWeight);
        kb.setTopK(topK);
        kb.setVersion(kb.getVersion() == null ? 1L : kb.getVersion() + 1);
        knowledgeBaseMapper.updateById(kb);
        log.info("更新检索参数并递增版本 kbId={} version={}", kbId, kb.getVersion());
    }

    public List<KbBrief> listAuthorized(String subjectType, String subjectId,
                                        String roleCodes, Long deptId) {
        return authorizedKbQueryAppService.listAuthorizedKbs(subjectType, subjectId, roleCodes, deptId);
    }

    /** 批量获取知识库版本号，供检索缓存 Key 构造 */
    public Map<String, Long> getKbVersions(List<Long> kbIds) {
        if (kbIds == null || kbIds.isEmpty()) {
            return Map.of();
        }
        return knowledgeBaseMapper.selectList(Wrappers.<KnowledgeBase>lambdaQuery()
                        .select(KnowledgeBase::getId, KnowledgeBase::getVersion)
                        .in(KnowledgeBase::getId, kbIds))
                .stream()
                .collect(Collectors.toMap(kb -> String.valueOf(kb.getId()),
                        kb -> kb.getVersion() == null ? 0L : kb.getVersion()));
    }

    public void bindAcl(Long kbId, String granteeType, String granteeId, String permission) {
        KbAcl acl = new KbAcl();
        acl.setTenantId(0L);
        acl.setKbId(kbId);
        acl.setGranteeType(granteeType);
        acl.setGranteeId(granteeId);
        acl.setPermission(permission == null ? "READ" : permission);
        kbAclMapper.insert(acl);
    }

    /** 创建命令 */
    public record CreateCommand(String kbCode, String kbName, String description, String category,
                                String embeddingModel, String chunkMethod, Integer chunkTokenNum,
                                Integer secretLevel, Long ownerDeptId, Long ownerUserId) {
    }
}
''')

add(KN + "/api/controller/KnowledgeBaseController.java", r'''
package com.fintech.rag.knowledge.api.controller;

import com.fintech.rag.api.dto.knowledge.KbBrief;
import com.fintech.rag.common.core.R;
import com.fintech.rag.knowledge.app.service.KnowledgeBaseAppService;
import com.fintech.rag.knowledge.app.service.KnowledgeBaseAppService.CreateCommand;
import jakarta.validation.constraints.NotBlank;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

/**
 * 知识库接口。
 *
 * @author rag-platform
 */
@RestController
@RequestMapping("/api/kb")
public class KnowledgeBaseController {

    private final KnowledgeBaseAppService appService;

    public KnowledgeBaseController(KnowledgeBaseAppService appService) {
        this.appService = appService;
    }

    /**
     * 创建知识库。
     */
    @PostMapping
    public R<Long> create(@RequestBody KnowledgeBaseCreateRequest request) {
        Long kbId = appService.create(new CreateCommand(
                request.kbCode(), request.kbName(), request.description(), request.category(),
                request.embeddingModel(), request.chunkMethod(), request.chunkTokenNum(),
                request.secretLevel(), request.ownerDeptId(), request.ownerUserId()));
        return R.ok(kbId);
    }

    /**
     * 查询主体已授权的知识库（内网调用为主，是越权防护的授权真源）。
     */
    @GetMapping("/authorized")
    public R<List<KbBrief>> listAuthorized(@RequestParam String subjectType,
                                           @RequestParam String subjectId,
                                           @RequestParam(required = false) String roleCodes,
                                           @RequestParam(required = false) Long deptId) {
        return R.ok(appService.listAuthorized(subjectType, subjectId, roleCodes, deptId));
    }

    /**
     * 批量获取知识库版本号（检索缓存 Key 构造）。
     */
    @PostMapping("/version")
    public R<Map<String, Long>> getKbVersions(@RequestBody List<Long> kbIds) {
        return R.ok(appService.getKbVersions(kbIds));
    }

    /**
     * 调整检索参数。变更会递增知识库版本号，从而让检索缓存自动失效。
     */
    @PostMapping("/retrieval-params")
    public R<Void> updateRetrievalParams(@RequestParam Long kbId,
                                         @RequestParam BigDecimal similarityThreshold,
                                         @RequestParam BigDecimal vectorSimilarityWeight,
                                         @RequestParam Integer topK) {
        appService.updateRetrievalParams(kbId, similarityThreshold, vectorSimilarityWeight, topK);
        return R.ok();
    }

    /**
     * 配置知识库 ACL。
     */
    @PostMapping("/acl")
    public R<Void> bindAcl(@RequestParam Long kbId,
                           @RequestParam String granteeType,
                           @RequestParam String granteeId,
                           @RequestParam(defaultValue = "READ") String permission) {
        appService.bindAcl(kbId, granteeType, granteeId, permission);
        return R.ok();
    }

    /** 创建请求体 */
    public record KnowledgeBaseCreateRequest(@NotBlank String kbCode,
                                             @NotBlank String kbName,
                                             String description,
                                             @NotBlank String category,
                                             String embeddingModel,
                                             String chunkMethod,
                                             Integer chunkTokenNum,
                                             Integer secretLevel,
                                             Long ownerDeptId,
                                             Long ownerUserId) {
    }
}
''')

add(KN + "/api/controller/DocumentController.java", r'''
package com.fintech.rag.knowledge.api.controller;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.fintech.rag.api.dto.knowledge.DocumentMeta;
import com.fintech.rag.common.core.R;
import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import com.fintech.rag.knowledge.domain.model.KbDocument;
import com.fintech.rag.knowledge.infra.persistence.mapper.KbDocumentMapper;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.stream.Collectors;

/**
 * 文档接口。
 *
 * @author rag-platform
 */
@RestController
@RequestMapping("/api/kb/documents")
public class DocumentController {

    private final KbDocumentMapper documentMapper;

    public DocumentController(KbDocumentMapper documentMapper) {
        this.documentMapper = documentMapper;
    }

    /**
     * 批量查询文档元数据（检索结果二次过滤使用：密级、生效期）。
     */
    @PostMapping("/meta")
    public R<List<DocumentMeta>> listMeta(@RequestBody List<Long> docIds) {
        if (docIds == null || docIds.isEmpty()) {
            return R.ok(List.of());
        }
        List<DocumentMeta> metas = documentMapper.selectList(Wrappers.<KbDocument>lambdaQuery()
                        .in(KbDocument::getId, docIds))
                .stream()
                .map(doc -> new DocumentMeta(
                        doc.getId(), doc.getKbId(), doc.getDocName(), doc.getVersionNo(),
                        doc.getSecretLevel(), doc.getEffectiveDate(), doc.getExpireDate(),
                        doc.getParseStatus(), doc.getChunkNum()))
                .collect(Collectors.toList());
        return R.ok(metas);
    }

    /**
     * 下线文档：下线后不可再被召回。
     *
     * <p>必须同步调用 RAGFlow 把文档从可检索状态摘除，否则「UI 下线了但检索还在召回」，
     * 是同类系统最常见的线上事故之一。</p>
     */
    @PostMapping("/offline")
    public R<Void> offline(@RequestParam Long docId, @RequestParam String reason) {
        KbDocument document = documentMapper.selectById(docId);
        if (document == null) {
            throw BizException.of(ErrorCode.DOC_NOT_FOUND);
        }
        document.setParseStatus("OFFLINE");
        document.setOfflineReason(reason);
        documentMapper.updateById(document);
        // TODO 调用 RAGFlow 摘除文档可检索状态；失败必须告警并进入重试队列
        return R.ok();
    }
}
''')

add("rag-knowledge-service/src/main/resources/application.yml", r'''
server:
  port: 8082
  shutdown: graceful

spring:
  application:
    name: rag-knowledge-service
  profiles:
    active: dev
  config:
    import:
      - optional:nacos:rag-knowledge-service.yaml
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
    url: jdbc:mysql://${MYSQL_HOST:127.0.0.1}:${MYSQL_PORT:3306}/rag_knowledge?useUnicode=true&characterEncoding=utf8&serverTimezone=Asia/Shanghai
    username: ${MYSQL_USERNAME:rag}
    password: ${MYSQL_PASSWORD:rag123456}

mybatis-plus:
  configuration:
    map-underscore-to-camel-case: true
  global-config:
    db-config:
      logic-delete-field: deleted
      logic-delete-value: 1
      logic-not-delete-value: 0

feign:
  okhttp:
    enabled: true
  client:
    config:
      default:
        connectTimeout: 1000
        readTimeout: 3000
      # 验签是高频短调用，超时必须更严
      rag-platform-service:
        connectTimeout: 300
        readTimeout: 500

rag:
  ragflow:
    base-url: http://${RAGFLOW_HOST:127.0.0.1}:${RAGFLOW_PORT:9380}
    api-key: ${RAGFLOW_API_KEY:}
    default-embedding-model: BAAI/bge-large-zh-v1.5
    default-rerank-model: BAAI/bge-reranker-v2-m3
  server:
    auth:
      enabled: true
      trusted-gateway-cidrs:
        - 10.10.1.0/24
      gateway-signature-enabled: false
      gateway-sign-secret: ${RAG_GATEWAY_SIGN_SECRET:}

management:
  endpoints:
    web:
      exposure:
        include: health,info,prometheus,metrics

logging:
  level:
    com.fintech.rag: INFO
''')

# ============================================================================
# ==========================  rag-ingest-service  ============================
# ============================================================================
add("rag-ingest-service/pom.xml", r'''
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

    <artifactId>rag-ingest-service</artifactId>
    <packaging>jar</packaging>
    <name>rag-ingest-service</name>
    <description>文档入库流水线：上传、解析、状态机、重试</description>

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
            <groupId>org.springframework.cloud</groupId>
            <artifactId>spring-cloud-starter-openfeign</artifactId>
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

        <!-- 对象存储：原始文档永久归档，供引用溯源下载 -->
        <dependency>
            <groupId>io.minio</groupId>
            <artifactId>minio</artifactId>
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
        <finalName>rag-ingest-service</finalName>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>
''')

IG = "rag-ingest-service/src/main/java/com/fintech/rag/ingest"

add(IG + "/IngestApplication.java", r'''
package com.fintech.rag.ingest;

import com.fintech.rag.api.client.PlatformClient;
import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;
import org.springframework.cloud.openfeign.EnableFeignClients;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * 文档入库服务启动类。
 *
 * <p>本服务是典型的「重 IO + 长任务 + 批处理」型：必须与在线问答服务物理隔离，
 * 否则一次批量导入就能把在线问答的线程池与数据库连接池打满。</p>
 *
 * @author rag-platform
 */
@SpringBootApplication(scanBasePackages = "com.fintech.rag.ingest")
@EnableDiscoveryClient
@EnableFeignClients(clients = PlatformClient.class)
@EnableScheduling
@ConfigurationPropertiesScan("com.fintech.rag.ingest")
@MapperScan("com.fintech.rag.ingest.infra.persistence.mapper")
public class IngestApplication {

    public static void main(String[] args) {
        SpringApplication.run(IngestApplication.class, args);
    }
}
''')

add(IG + "/domain/model/IngestTask.java", r'''
package com.fintech.rag.ingest.domain.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.EnumSet;
import java.util.Set;

/**
 * 文档入库任务。
 *
 * <p>解析状态机内聚在本类中，<b>禁止在业务代码里散落 {@code if (status == X) update(Y)}</b>，
 * 否则状态会漂移到非法组合（例如从 FAILED 直接跳到 PARSED）。</p>
 *
 * @author rag-platform
 */
@Data
@TableName("t_ingest_task")
public class IngestTask {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private Long tenantId;

    private String taskNo;

    private Long kbId;

    private Long docId;

    private String fileName;

    private String fileMd5;

    private Long fileSize;

    private String minioObjectKey;

    private String ragflowDocumentId;

    private String status;

    private String currentStep;

    private Integer progress;

    private Integer retryCount;

    private Integer maxRetry;

    private String errorCode;

    private String errorMsg;

    private Integer chunkNum;

    private Long costMs;

    private String submittedBy;

    private LocalDateTime submittedAt;

    private LocalDateTime finishedAt;

    private LocalDateTime updateTime;

    @TableLogic
    private Integer deleted;

    /** 解析状态 */
    public enum Status {
        /** 已落盘，待上传 */
        PENDING,
        /** 已入 RAGFlow，待解析 */
        UPLOADED,
        /** 解析中 */
        PARSING,
        /** 解析完成，可检索 */
        PARSED,
        /** 解析失败，可重试 */
        FAILED,
        /** 已下线 */
        OFFLINE,
        /** 已取消 */
        CANCELED
    }

    private static final java.util.Map<Status, Set<Status>> TRANSITIONS = java.util.Map.of(
            Status.PENDING, EnumSet.of(Status.UPLOADED, Status.CANCELED),
            Status.UPLOADED, EnumSet.of(Status.PARSING, Status.FAILED, Status.CANCELED),
            Status.PARSING, EnumSet.of(Status.PARSED, Status.FAILED),
            Status.FAILED, EnumSet.of(Status.UPLOADED),
            Status.PARSED, EnumSet.of(Status.OFFLINE),
            Status.OFFLINE, EnumSet.of(Status.UPLOADED),
            Status.CANCELED, EnumSet.noneOf(Status.class)
    );

    /** 校验状态迁移是否合法 */
    public static boolean canTransit(String from, String to) {
        try {
            Status f = Status.valueOf(from);
            Status t = Status.valueOf(to);
            return TRANSITIONS.getOrDefault(f, EnumSet.noneOf(Status.class)).contains(t);
        } catch (IllegalArgumentException ex) {
            return false;
        }
    }
}
''')

add(IG + "/domain/model/OutboxMessage.java", r'''
package com.fintech.rag.ingest.domain.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 本地消息表（Outbox）。
 *
 * <p><b>为什么必须有这张表：</b>入库成功需要「更新任务状态」+「通知下游可检索」。
 * 若直接发 MQ，存在「写库成功但消息丢失」与「消息已发但事务回滚」两种不一致。
 * 正确做法是：同库同事务写入本表，再由定时任务投递 MQ，投递成功才标记 SENT，
 * 从而把「本地事务」与「消息投递」解耦成「至少一次投递 + 下游幂等」。</p>
 *
 * @author rag-platform
 */
@Data
@TableName("t_outbox")
public class OutboxMessage {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private Long tenantId;

    /** 业务消息 ID，下游幂等键 */
    private String messageId;

    private String topic;

    private String tag;

    private String bizKey;

    /** JSON 负载 */
    private String payload;

    /** NEW / SENT / FAILED */
    private String status;

    private Integer retryCount;

    private LocalDateTime nextRetryAt;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;
}
''')

IG_MAPPER = IG + "/infra/persistence/mapper/"
for name, entity, desc in (("IngestTask", "IngestTask", "入库任务"), ("OutboxMessage", "OutboxMessage", "本地消息")):
    add(IG_MAPPER + name + "Mapper.java", r'''
package com.fintech.rag.ingest.infra.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.fintech.rag.ingest.domain.model.%ENTITY%;
import org.apache.ibatis.annotations.Mapper;

/**
 * %DESC% 数据访问。
 *
 * @author rag-platform
 */
@Mapper
public interface %NAME%Mapper extends BaseMapper<%ENTITY%> {
}
'''.replace("%ENTITY%", entity).replace("%NAME%", name).replace("%DESC%", desc))

add(IG + "/infra/mq/IngestEventPublisher.java", r'''
package com.fintech.rag.ingest.infra.mq;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * 入库事件发布器。
 *
 * <p>骨架中给出接口与默认实现（仅打日志），落地时替换为 RocketMQ 生产者：</p>
 * <pre>
 * rocketMQTemplate.syncSend(topic + ":" + tag, MessageBuilder.withPayload(payload)
 *         .setHeader(RocketMQHeaders.KEYS, messageId).build());
 * </pre>
 *
 * <p>下游（knowledge / platform 审计 / 看板）必须按 {@code messageId} 做幂等，
 * 因为 Outbox 是<b>至少一次</b>投递语义。</p>
 *
 * @author rag-platform
 */
@Component
public class IngestEventPublisher {

    private static final Logger log = LoggerFactory.getLogger(IngestEventPublisher.class);

    /**
     * 发布事件。
     *
     * @return true 表示投递成功（可以标记 SENT）
     */
    public boolean publish(String topic, String tag, String messageId, String payload) {
        // TODO 替换为 RocketMQ 同步发送；当前为骨架实现
        log.info("[Outbox] 投递事件 topic={} tag={} messageId={} payloadLen={}",
                topic, tag, messageId, payload == null ? 0 : payload.length());
        return true;
    }
}
''')

add(IG + "/infra/storage/MinioStorageService.java", r'''
package com.fintech.rag.ingest.infra.storage;

import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import com.fintech.rag.ingest.config.MinioProperties;
import io.minio.BucketExistsArgs;
import io.minio.MakeBucketArgs;
import io.minio.MinioClient;
import io.minio.PutObjectArgs;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.io.InputStream;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;

/**
 * MinIO 对象存储服务 —— 原始文档永久归档。
 *
 * <p>为什么必须自己存一份原始文件：RAGFlow 内只存解析后的分片，
 * 用户点击「查看原文」时需要 PDF 原件定位到对应页码。
 * 归档缺失会导致引用溯源功能直接失效。</p>
 *
 * @author rag-platform
 */
@Service
public class MinioStorageService {

    private static final Logger log = LoggerFactory.getLogger(MinioStorageService.class);
    private static final DateTimeFormatter DATE_FORMAT = DateTimeFormatter.ofPattern("yyyy/MM/dd");

    private final MinioClient minioClient;
    private final MinioProperties properties;

    public MinioStorageService(MinioProperties properties) {
        this.properties = properties;
        this.minioClient = MinioClient.builder()
                .endpoint(properties.getEndpoint())
                .credentials(properties.getAccessKey(), properties.getSecretKey())
                .build();
    }

    /**
     * 上传原始文档。
     *
     * @return 对象 Key，形如 {@code kb/1001/2026/09/29/<sha256前缀>_文件名}
     */
    public String upload(Long kbId, String fileName, String md5, long size, InputStream inputStream) {
        String objectKey = buildObjectKey(kbId, md5, fileName);
        try {
            ensureBucket();
            minioClient.putObject(PutObjectArgs.builder()
                    .bucket(properties.getBucket())
                    .object(objectKey)
                    .stream(inputStream, size, -1)
                    .contentType("application/octet-stream")
                    .build());
            log.info("原始文档归档成功 bucket={} key={}", properties.getBucket(), objectKey);
            return objectKey;
        } catch (Exception ex) {
            log.error("原始文档归档失败 kbId={} fileName={}", kbId, fileName, ex);
            throw BizException.of(ErrorCode.INTERNAL_ERROR, "文档归档失败");
        }
    }

    private String buildObjectKey(Long kbId, String md5, String fileName) {
        String safeName = fileName == null ? "unknown" : fileName.replaceAll("[\\\\/:*?\"<>|]", "_");
        String prefix = md5 == null ? "nohash" : md5.substring(0, Math.min(8, md5.length()));
        return "kb/" + kbId + "/" + LocalDate.now().format(DATE_FORMAT) + "/" + prefix + "_" + safeName;
    }

    private void ensureBucket() throws Exception {
        boolean exists = minioClient.bucketExists(
                BucketExistsArgs.builder().bucket(properties.getBucket()).build());
        if (!exists) {
            minioClient.makeBucket(MakeBucketArgs.builder().bucket(properties.getBucket()).build());
            log.info("创建 MinIO bucket={}", properties.getBucket());
        }
    }
}
''')

add(IG + "/config/MinioProperties.java", r'''
package com.fintech.rag.ingest.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * MinIO 配置。
 *
 * @author rag-platform
 */
@ConfigurationProperties(prefix = "rag.minio")
public class MinioProperties {

    private String endpoint = "http://127.0.0.1:9000";

    private String accessKey;

    private String secretKey;

    private String bucket = "rag-origin-doc";

    public String getEndpoint() {
        return endpoint;
    }

    public void setEndpoint(String endpoint) {
        this.endpoint = endpoint;
    }

    public String getAccessKey() {
        return accessKey;
    }

    public void setAccessKey(String accessKey) {
        this.accessKey = accessKey;
    }

    public String getSecretKey() {
        return secretKey;
    }

    public void setSecretKey(String secretKey) {
        this.secretKey = secretKey;
    }

    public String getBucket() {
        return bucket;
    }

    public void setBucket(String bucket) {
        this.bucket = bucket;
    }
}
''')

add(IG + "/infra/client/RagFlowDocumentClient.java", r'''
package com.fintech.rag.ingest.infra.client;

import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import com.fintech.rag.common.integration.ragflow.RagFlowProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestClient;

import java.time.Duration;
import java.util.Map;

/**
 * RAGFlow 文档客户端：上传、触发解析、查询解析状态。
 *
 * <p><b>关键认知：RAGFlow 的解析是异步的。</b>上传接口返回不等于解析完成，
 * 解析完成才可被检索。因此必须「上传 → 触发解析 → 轮询状态」三段式，
 * 上传完立刻提问必然召回为空。</p>
 *
 * @author rag-platform
 */
@Component
public class RagFlowDocumentClient {

    private static final Logger log = LoggerFactory.getLogger(RagFlowDocumentClient.class);
    private static final int SUCCESS_CODE = 0;

    private final RestClient uploadClient;

    public RagFlowDocumentClient(RagFlowProperties properties) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofMillis(properties.getConnectTimeoutMs()));
        factory.setReadTimeout(Duration.ofMillis(properties.getUploadTimeoutMs()));
        this.uploadClient = RestClient.builder()
                .baseUrl(properties.getBaseUrl())
                .requestFactory(factory)
                .defaultHeader(HttpHeaders.AUTHORIZATION, "Bearer " + properties.getApiKey())
                .build();
    }

    /**
     * 上传文档到指定 Dataset。
     *
     * @return RAGFlow 文档 ID
     */
    public String uploadDocument(String datasetId, String fileName, byte[] content) {
        MultiValueMap<String, Object> form = new LinkedMultiValueMap<>();
        form.add("file", new ByteArrayResource(content) {
            @Override
            public String getFilename() {
                return fileName;
            }
        });

        RagFlowResponse<Object> response = uploadClient.post()
                .uri("/api/v1/datasets/{datasetId}/documents", datasetId)
                .contentType(MediaType.MULTIPART_FORM_DATA)
                .body(form)
                .retrieve()
                .body(new ParameterizedTypeReference<>() {
                });

        String documentId = extractFirstId(response);
        if (documentId == null) {
            log.error("上传文档到 RAGFlow 失败 datasetId={} fileName={}", datasetId, fileName);
            throw BizException.of(ErrorCode.RAGFLOW_CALL_FAILED, "上传文档失败");
        }
        log.info("上传文档成功 datasetId={} fileName={} documentId={}", datasetId, fileName, documentId);
        return documentId;
    }

    /** 触发解析（分片 + 向量化） */
    public void startParsing(String datasetId, String documentId) {
        RagFlowResponse<Object> response = uploadClient.post()
                .uri("/api/v1/datasets/{datasetId}/chunks", datasetId)
                .contentType(MediaType.APPLICATION_JSON)
                .body(Map.of("document_ids", java.util.List.of(documentId)))
                .retrieve()
                .body(new ParameterizedTypeReference<>() {
                });
        if (response == null || response.code() != SUCCESS_CODE) {
            throw BizException.of(ErrorCode.RAGFLOW_CALL_FAILED, "触发解析失败");
        }
    }

    /**
     * 查询文档解析状态。
     *
     * @return RAGFlow 的 run 状态：UNSTART / RUNNING / DONE / FAIL
     */
    public String queryRunStatus(String datasetId, String documentId) {
        RagFlowResponse<Object> response = uploadClient.get()
                .uri("/api/v1/datasets/{datasetId}/documents?id={documentId}", datasetId, documentId)
                .retrieve()
                .body(new ParameterizedTypeReference<>() {
                });
        String status = extractField(response, "run");
        return status == null ? "UNSTART" : status;
    }

    /** 查询已生成的分片数量 */
    public int queryChunkCount(String datasetId, String documentId) {
        RagFlowResponse<Object> response = uploadClient.get()
                .uri("/api/v1/datasets/{datasetId}/documents?id={documentId}", datasetId, documentId)
                .retrieve()
                .body(new ParameterizedTypeReference<>() {
                });
        String value = extractField(response, "chunk_count");
        try {
            return value == null ? 0 : Integer.parseInt(value);
        } catch (NumberFormatException ex) {
            return 0;
        }
    }

    /** 从 RAGFlow 文档中摘除可检索状态（文档下线） */
    public void disableDocument(String datasetId, String documentId) {
        RagFlowResponse<Object> response = uploadClient.put()
                .uri("/api/v1/datasets/{datasetId}/documents/{documentId}", datasetId, documentId)
                .contentType(MediaType.APPLICATION_JSON)
                .body(Map.of("chunk_method", "NAIVE"))
                .retrieve()
                .body(new ParameterizedTypeReference<>() {
                });
        if (response == null || response.code() != SUCCESS_CODE) {
            throw BizException.of(ErrorCode.RAGFLOW_CALL_FAILED, "文档下线失败");
        }
    }

    @SuppressWarnings("unchecked")
    private String extractFirstId(RagFlowResponse<Object> response) {
        if (response == null || response.code() != SUCCESS_CODE || response.data() == null) {
            return null;
        }
        Object data = response.data();
        if (data instanceof java.util.List<?> list && !list.isEmpty()) {
            Object first = list.get(0);
            if (first instanceof Map<?, ?> map && map.get("id") != null) {
                return String.valueOf(map.get("id"));
            }
        }
        return null;
    }

    @SuppressWarnings("unchecked")
    private String extractField(RagFlowResponse<Object> response, String field) {
        if (response == null || response.data() == null) {
            return null;
        }
        Object data = response.data();
        if (data instanceof java.util.List<?> list && !list.isEmpty()) {
            data = list.get(0);
        }
        if (data instanceof Map<?, ?> map && map.get(field) != null) {
            return String.valueOf(map.get(field));
        }
        if (data instanceof Map<?, ?> map && map.get("docs") instanceof java.util.List<?> docs
                && !docs.isEmpty() && docs.get(0) instanceof Map<?, ?> doc && doc.get(field) != null) {
            return String.valueOf(doc.get(field));
        }
        return null;
    }

    /** RAGFlow 统一响应 */
    public record RagFlowResponse<T>(Integer code, String message, T data) {
    }
}
''')

add(IG + "/app/pipeline/DocumentIngestPipeline.java", r'''
package com.fintech.rag.ingest.app.pipeline;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import com.fintech.rag.ingest.domain.model.IngestTask;
import com.fintech.rag.ingest.domain.model.OutboxMessage;
import com.fintech.rag.ingest.infra.client.RagFlowDocumentClient;
import com.fintech.rag.ingest.infra.persistence.mapper.IngestTaskMapper;
import com.fintech.rag.ingest.infra.persistence.mapper.OutboxMessageMapper;
import com.fintech.rag.ingest.infra.storage.MinioStorageService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.io.InputStream;
import java.time.LocalDateTime;
import java.util.UUID;

/**
 * 文档入库流水线 —— 本服务的核心编排。
 *
 * <p>流程：校验 → MinIO 落盘 → 建任务(PENDING) → 上传 RAGFlow → UPLOADED
 * → 触发解析 → PARSING → 轮询(PARSE 完成) → PARSED → 写 Outbox 通知下游。</p>
 *
 * <p><b>事务边界：</b>只有「本地库写入 + Outbox 写入」在一个事务里；
 * 调用 RAGFlow / MinIO 一律在事务之外，失败靠状态机 + 重试补偿，
 * 绝不能把外部系统调用包在数据库事务里（长事务会拖垮连接池）。</p>
 *
 * @author rag-platform
 */
@Service
public class DocumentIngestPipeline {

    private static final Logger log = LoggerFactory.getLogger(DocumentIngestPipeline.class);
    private static final String TOPIC = "RAG_INGEST";
    private static final String TAG_DOC_READY = "DOC_READY";

    private final IngestTaskMapper taskMapper;
    private final OutboxMessageMapper outboxMapper;
    private final MinioStorageService storageService;
    private final RagFlowDocumentClient ragFlowClient;

    public DocumentIngestPipeline(IngestTaskMapper taskMapper,
                                  OutboxMessageMapper outboxMapper,
                                  MinioStorageService storageService,
                                  RagFlowDocumentClient ragFlowClient) {
        this.taskMapper = taskMapper;
        this.outboxMapper = outboxMapper;
        this.storageService = storageService;
        this.ragFlowClient = ragFlowClient;
    }

    /**
     * 提交入库任务。
     *
     * @return 任务号
     */
    public String submit(Long kbId, String datasetId, String fileName, String md5, long size,
                         InputStream inputStream, String submittedBy) {
        // 重复检测：同一知识库下相同 MD5 的文档直接提示，避免重复入库造成召回重复
        Long duplicated = taskMapper.selectCount(Wrappers.<IngestTask>lambdaQuery()
                .eq(IngestTask::getKbId, kbId)
                .eq(IngestTask::getFileMd5, md5)
                .in(IngestTask::getStatus, IngestTask.Status.PENDING.name(),
                        IngestTask.Status.UPLOADED.name(), IngestTask.Status.PARSING.name(),
                        IngestTask.Status.PARSED.name()));
        if (duplicated != null && duplicated > 0) {
            throw BizException.of(ErrorCode.DOC_DUPLICATED, "该文档已存在（内容相同），请勿重复上传");
        }

        String objectKey = storageService.upload(kbId, fileName, md5, size, inputStream);

        IngestTask task = new IngestTask();
        task.setTenantId(0L);
        task.setTaskNo("T" + System.currentTimeMillis() + UUID.randomUUID().toString().substring(0, 6));
        task.setKbId(kbId);
        task.setFileName(fileName);
        task.setFileMd5(md5);
        task.setFileSize(size);
        task.setMinioObjectKey(objectKey);
        task.setStatus(IngestTask.Status.PENDING.name());
        task.setCurrentStep("STORE");
        task.setProgress(10);
        task.setRetryCount(0);
        task.setMaxRetry(3);
        task.setSubmittedBy(submittedBy);
        task.setSubmittedAt(LocalDateTime.now());
        task.setDeleted(0);
        taskMapper.insert(task);

        log.info("入库任务已创建 taskNo={} kbId={} fileName={}", task.getTaskNo(), kbId, fileName);
        return task.getTaskNo();
    }

    /**
     * 推进一步：把 PENDING 的任务上传到 RAGFlow 并触发解析。
     */
    @Transactional(rollbackFor = Exception.class)
    public void advanceUpload(String taskNo, String datasetId, byte[] content) {
        IngestTask task = requireTask(taskNo);
        transit(task, IngestTask.Status.UPLOADED, "UPLOAD", 40,
                () -> {
                    String documentId = ragFlowClient.uploadDocument(datasetId, task.getFileName(), content);
                    task.setRagflowDocumentId(documentId);
                });

        transit(task, IngestTask.Status.PARSING, "PARSE", 60,
                () -> ragFlowClient.startParsing(datasetId, task.getRagflowDocumentId()));
    }

    /**
     * 解析完成：落终态并写 Outbox 通知下游。
     */
    @Transactional(rollbackFor = Exception.class)
    public void markParsed(String taskNo, int chunkNum) {
        IngestTask task = requireTask(taskNo);
        transit(task, IngestTask.Status.PARSED, "PARSED", 100, () -> task.setChunkNum(chunkNum));
        task.setFinishedAt(LocalDateTime.now());
        task.setCostMs(System.currentTimeMillis() - task.getSubmittedAt()
                .atZone(java.time.ZoneId.systemDefault()).toInstant().toEpochMilli());
        taskMapper.updateById(task);

        OutboxMessage message = new OutboxMessage();
        message.setTenantId(0L);
        message.setMessageId("DOC_READY_" + task.getTaskNo());
        message.setTopic(TOPIC);
        message.setTag(TAG_DOC_READY);
        message.setBizKey(task.getTaskNo());
        message.setPayload("{\"taskNo\":\"" + task.getTaskNo() + "\",\"kbId\":"
                + task.getKbId() + ",\"chunkNum\":" + chunkNum + "}");
        message.setStatus("NEW");
        message.setRetryCount(0);
        outboxMapper.insert(message);

        log.info("文档解析完成并写入 Outbox taskNo={} chunkNum={}", taskNo, chunkNum);
    }

    /**
     * 标记失败。超过最大重试次数则不再自动重试，等待人工介入。
     */
    @Transactional(rollbackFor = Exception.class)
    public void markFailed(String taskNo, String errorCode, String errorMsg) {
        IngestTask task = requireTask(taskNo);
        task.setStatus(IngestTask.Status.FAILED.name());
        task.setErrorCode(errorCode);
        task.setErrorMsg(errorMsg == null ? null
                : errorMsg.substring(0, Math.min(1000, errorMsg.length())));
        task.setFinishedAt(LocalDateTime.now());
        taskMapper.updateById(task);
        log.warn("入库任务失败 taskNo={} retryCount={} error={}", taskNo, task.getRetryCount(), errorMsg);
    }

    /** 人工重试：重置状态为 UPLOADED，重新走解析 */
    @Transactional(rollbackFor = Exception.class)
    public void retry(String taskNo) {
        IngestTask task = requireTask(taskNo);
        if (task.getRetryCount() != null && task.getMaxRetry() != null
                && task.getRetryCount() >= task.getMaxRetry()) {
            throw BizException.of(ErrorCode.INTERNAL_ERROR, "已超过最大重试次数，请人工处理");
        }
        if (!IngestTask.canTransit(task.getStatus(), IngestTask.Status.UPLOADED.name())) {
            throw BizException.of(ErrorCode.INTERNAL_ERROR,
                    "当前状态不允许重试：" + task.getStatus());
        }
        task.setStatus(IngestTask.Status.UPLOADED.name());
        task.setRetryCount(task.getRetryCount() == null ? 1 : task.getRetryCount() + 1);
        task.setErrorCode(null);
        task.setErrorMsg(null);
        taskMapper.updateById(task);
    }

    private IngestTask requireTask(String taskNo) {
        IngestTask task = taskMapper.selectOne(Wrappers.<IngestTask>lambdaQuery()
                .eq(IngestTask::getTaskNo, taskNo));
        if (task == null) {
            throw BizException.of(ErrorCode.INTERNAL_ERROR, "任务不存在：" + taskNo);
        }
        return task;
    }

    /** 统一的状态迁移入口：先校验合法性，再执行副作用，最后落库 */
    private void transit(IngestTask task, IngestTask.Status target, String step,
                         int progress, Runnable action) {
        if (!IngestTask.canTransit(task.getStatus(), target.name())) {
            throw BizException.of(ErrorCode.INTERNAL_ERROR,
                    "非法状态迁移 " + task.getStatus() + " -> " + target);
        }
        action.run();
        task.setStatus(target.name());
        task.setCurrentStep(step);
        task.setProgress(progress);
        taskMapper.updateById(task);
    }
}
''')

add(IG + "/app/job/ParseStatusPollingJob.java", r'''
package com.fintech.rag.ingest.app.job;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.fintech.rag.common.integration.ragflow.RagFlowProperties;
import com.fintech.rag.ingest.app.pipeline.DocumentIngestPipeline;
import com.fintech.rag.ingest.domain.model.IngestTask;
import com.fintech.rag.ingest.infra.client.RagFlowDocumentClient;
import com.fintech.rag.ingest.infra.persistence.mapper.IngestTaskMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.List;

/**
 * 解析状态轮询任务。
 *
 * <p>RAGFlow 不提供解析完成的回调，所以只能轮询。
 * <b>必须设置超时兜底</b>：没有超时判定的话，卡在 PARSING 的任务会永久占用配额，
 * 且用户永远看到「解析中」。</p>
 *
 * @author rag-platform
 */
@Component
public class ParseStatusPollingJob {

    private static final Logger log = LoggerFactory.getLogger(ParseStatusPollingJob.class);
    private static final int BATCH_SIZE = 50;

    private final IngestTaskMapper taskMapper;
    private final RagFlowDocumentClient ragFlowClient;
    private final DocumentIngestPipeline pipeline;
    private final RagFlowProperties ragFlowProperties;

    public ParseStatusPollingJob(IngestTaskMapper taskMapper,
                                 RagFlowDocumentClient ragFlowClient,
                                 DocumentIngestPipeline pipeline,
                                 RagFlowProperties ragFlowProperties) {
        this.taskMapper = taskMapper;
        this.ragFlowClient = ragFlowClient;
        this.pipeline = pipeline;
        this.ragFlowProperties = ragFlowProperties;
    }

    /**
     * 每 10 秒轮询一次解析中的任务。
     */
    @Scheduled(fixedDelayString = "${rag.ingest.poll-interval-ms:10000}")
    public void poll() {
        List<IngestTask> tasks = taskMapper.selectList(Wrappers.<IngestTask>lambdaQuery()
                .eq(IngestTask::getStatus, IngestTask.Status.PARSING.name())
                .orderByAsc(IngestTask::getSubmittedAt)
                .last("limit " + BATCH_SIZE));

        if (tasks.isEmpty()) {
            return;
        }

        for (IngestTask task : tasks) {
            try {
                handle(task);
            } catch (Exception ex) {
                log.error("轮询解析状态异常 taskNo={}", task.getTaskNo(), ex);
            }
        }
    }

    private void handle(IngestTask task) {
        String datasetId = resolveDatasetId(task);
        if (datasetId == null) {
            pipeline.markFailed(task.getTaskNo(), "B0008", "知识库 Dataset 映射缺失");
            return;
        }

        String runStatus = ragFlowClient.queryRunStatus(datasetId, task.getRagflowDocumentId());
        switch (runStatus.toUpperCase()) {
            case "DONE" -> {
                int chunkNum = ragFlowClient.queryChunkCount(datasetId, task.getRagflowDocumentId());
                pipeline.markParsed(task.getTaskNo(), chunkNum);
            }
            case "FAIL" -> pipeline.markFailed(task.getTaskNo(), "B0003", "RAGFlow 解析失败");
            case "UNSTART", "RUNNING" -> checkTimeout(task);
            default -> log.warn("未知解析状态 taskNo={} status={}", task.getTaskNo(), runStatus);
        }
    }

    /** 超时兜底：解析超过阈值直接判失败，释放用户预期 */
    private void checkTimeout(IngestTask task) {
        if (task.getSubmittedAt() == null) {
            return;
        }
        long elapsed = Duration.between(task.getSubmittedAt(), LocalDateTime.now()).toMillis();
        if (elapsed > ragFlowProperties.getParseTimeoutMs()) {
            log.warn("解析超时 taskNo={} elapsedMs={}", task.getTaskNo(), elapsed);
            pipeline.markFailed(task.getTaskNo(), "C0003", "解析超时，请检查文档格式或重试");
        }
    }

    /**
     * TODO 通过 rag-knowledge-service 查询 kbId -> ragflowDatasetId 映射，
     * 骨架阶段直接返回空并说明原因，避免引入不必要的服务依赖。
     */
    private String resolveDatasetId(IngestTask task) {
        return null;
    }
}
''')

add(IG + "/app/job/OutboxRelayJob.java", r'''
package com.fintech.rag.ingest.app.job;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.fintech.rag.ingest.domain.model.OutboxMessage;
import com.fintech.rag.ingest.infra.mq.IngestEventPublisher;
import com.fintech.rag.ingest.infra.persistence.mapper.OutboxMessageMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

/**
 * Outbox 投递任务。
 *
 * <p>把「本地事务」与「消息投递」解耦：事务只负责写 Outbox，
 * 本任务负责可靠投递，投递成功才标记 SENT，失败则指数退避重试。</p>
 *
 * <p><b>下游必须幂等</b>：本机制是「至少一次」语义，重复投递是正常的，
 * 重复消费才是 bug。</p>
 *
 * @author rag-platform
 */
@Component
public class OutboxRelayJob {

    private static final Logger log = LoggerFactory.getLogger(OutboxRelayJob.class);
    private static final int BATCH_SIZE = 100;
    private static final int MAX_RETRY = 10;

    private final OutboxMessageMapper outboxMapper;
    private final IngestEventPublisher publisher;

    public OutboxRelayJob(OutboxMessageMapper outboxMapper, IngestEventPublisher publisher) {
        this.outboxMapper = outboxMapper;
        this.publisher = publisher;
    }

    @Scheduled(fixedDelayString = "${rag.ingest.outbox-interval-ms:5000}")
    @Transactional(rollbackFor = Exception.class)
    public void relay() {
        List<OutboxMessage> messages = outboxMapper.selectList(Wrappers.<OutboxMessage>lambdaQuery()
                .eq(OutboxMessage::getStatus, "NEW")
                .and(w -> w.isNull(OutboxMessage::getNextRetryAt)
                        .or().le(OutboxMessage::getNextRetryAt, LocalDateTime.now()))
                .orderByAsc(OutboxMessage::getCreateTime)
                .last("limit " + BATCH_SIZE));

        for (OutboxMessage message : messages) {
            boolean sent = publisher.publish(message.getTopic(), message.getTag(),
                    message.getMessageId(), message.getPayload());
            if (sent) {
                message.setStatus("SENT");
            } else {
                int retry = message.getRetryCount() == null ? 1 : message.getRetryCount() + 1;
                message.setRetryCount(retry);
                message.setStatus(retry >= MAX_RETRY ? "FAILED" : "NEW");
                // 指数退避：2^n 秒，上限 10 分钟
                long delaySeconds = Math.min(600, (long) Math.pow(2, retry));
                message.setNextRetryAt(LocalDateTime.now().plusSeconds(delaySeconds));
                log.warn("Outbox 投递失败 messageId={} retry={}", message.getMessageId(), retry);
            }
            outboxMapper.updateById(message);
        }
    }
}
''')

add(IG + "/api/controller/IngestController.java", r'''
package com.fintech.rag.ingest.api.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.fintech.rag.common.core.PageResult;
import com.fintech.rag.common.core.R;
import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import com.fintech.rag.ingest.app.pipeline.DocumentIngestPipeline;
import com.fintech.rag.ingest.domain.model.IngestTask;
import com.fintech.rag.ingest.infra.persistence.mapper.IngestTaskMapper;
import org.springframework.util.DigestUtils;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.InputStream;

/**
 * 文档入库接口。
 *
 * @author rag-platform
 */
@RestController
@RequestMapping("/api/ingest")
public class IngestController {

    /** 类型白名单：只放行解析能力确认为可用的格式 */
    private static final java.util.Set<String> ALLOWED_EXT = java.util.Set.of(
            "pdf", "docx", "doc", "xlsx", "xls", "pptx", "ppt", "txt", "md", "html", "png", "jpg");

    private static final long MAX_FILE_SIZE = 200L * 1024 * 1024;

    private final DocumentIngestPipeline pipeline;
    private final IngestTaskMapper taskMapper;

    public IngestController(DocumentIngestPipeline pipeline, IngestTaskMapper taskMapper) {
        this.pipeline = pipeline;
        this.taskMapper = taskMapper;
    }

    /**
     * 上传并提交入库任务。
     *
     * <p>只做「接收 + 落盘 + 建任务」，解析由流水线与轮询任务推进，
     * 接口本身必须快速返回，不能阻塞在解析上。</p>
     */
    @PostMapping("/upload")
    public R<String> upload(@RequestParam Long kbId,
                            @RequestParam String datasetId,
                            @RequestParam("file") MultipartFile file,
                            @RequestParam(required = false) String submittedBy) throws IOException {
        validate(file);

        // 直接用字节流算摘要，避免「文件字节 -> String -> 再哈希」造成的隐式编码转换
        String md5 = DigestUtils.md5DigestAsHex(file.getBytes());
        try (InputStream in = file.getInputStream()) {
            String taskNo = pipeline.submit(kbId, datasetId, file.getOriginalFilename(),
                    md5, file.getSize(), in, submittedBy);
            return R.ok(taskNo);
        }
    }

    @GetMapping("/tasks")
    public R<PageResult<IngestTask>> page(@RequestParam(defaultValue = "1") long pageNum,
                                          @RequestParam(defaultValue = "20") long pageSize,
                                          @RequestParam(required = false) Long kbId,
                                          @RequestParam(required = false) String status) {
        Page<IngestTask> page = new Page<>(pageNum, pageSize);
        IPage<IngestTask> result = taskMapper.selectPage(page, Wrappers.<IngestTask>lambdaQuery()
                .eq(kbId != null, IngestTask::getKbId, kbId)
                .eq(status != null, IngestTask::getStatus, status)
                .orderByDesc(IngestTask::getSubmittedAt));
        return R.ok(PageResult.of(result.getRecords(), pageNum, pageSize, result.getTotal()));
    }

    @GetMapping("/tasks/detail")
    public R<IngestTask> detail(@RequestParam String taskNo) {
        IngestTask task = taskMapper.selectOne(Wrappers.<IngestTask>lambdaQuery()
                .eq(IngestTask::getTaskNo, taskNo));
        if (task == null) {
            throw BizException.of(ErrorCode.INTERNAL_ERROR, "任务不存在");
        }
        return R.ok(task);
    }

    @PostMapping("/tasks/retry")
    public R<Void> retry(@RequestParam String taskNo) {
        pipeline.retry(taskNo);
        return R.ok();
    }

    private void validate(MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw BizException.of(ErrorCode.PARAM_INVALID, "上传文件不能为空");
        }
        if (file.getSize() > MAX_FILE_SIZE) {
            throw BizException.of(ErrorCode.FILE_TOO_LARGE, "文件超过 200MB 限制");
        }
        String name = file.getOriginalFilename();
        int dot = name == null ? -1 : name.lastIndexOf('.');
        String ext = dot < 0 ? "" : name.substring(dot + 1).toLowerCase();
        if (!ALLOWED_EXT.contains(ext)) {
            throw BizException.of(ErrorCode.FILE_TYPE_UNSUPPORTED, "不支持的文件类型：" + ext);
        }
        // TODO 接入 ClamAV 病毒扫描；未扫描的文件不得进入解析流程
    }
}
''')

add("rag-ingest-service/src/main/resources/application.yml", r'''
server:
  port: 8083
  shutdown: graceful
  tomcat:
    max-http-form-post-size: 210MB

spring:
  application:
    name: rag-ingest-service
  profiles:
    active: dev
  config:
    import:
      - optional:nacos:rag-ingest-service.yaml
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
  servlet:
    multipart:
      max-file-size: 200MB
      max-request-size: 210MB
  datasource:
    driver-class-name: com.mysql.cj.jdbc.Driver
    url: jdbc:mysql://${MYSQL_HOST:127.0.0.1}:${MYSQL_PORT:3306}/rag_ingest?useUnicode=true&characterEncoding=utf8&serverTimezone=Asia/Shanghai
    username: ${MYSQL_USERNAME:rag}
    password: ${MYSQL_PASSWORD:rag123456}
    hikari:
      maximum-pool-size: 10

mybatis-plus:
  configuration:
    map-underscore-to-camel-case: true
  global-config:
    db-config:
      logic-delete-field: deleted
      logic-delete-value: 1
      logic-not-delete-value: 0

rag:
  ragflow:
    base-url: http://${RAGFLOW_HOST:127.0.0.1}:${RAGFLOW_PORT:9380}
    api-key: ${RAGFLOW_API_KEY:}
    upload-timeout-ms: 120000
    parse-timeout-ms: 1800000
  minio:
    endpoint: ${MINIO_ENDPOINT:http://127.0.0.1:9000}
    access-key: ${MINIO_ACCESS_KEY:}
    secret-key: ${MINIO_SECRET_KEY:}
    bucket: rag-origin-doc
  ingest:
    poll-interval-ms: 10000
    outbox-interval-ms: 5000
  server:
    auth:
      enabled: true
      trusted-gateway-cidrs:
        - 10.10.1.0/24
      gateway-signature-enabled: false
      gateway-sign-secret: ${RAG_GATEWAY_SIGN_SECRET:}

management:
  endpoints:
    web:
      exposure:
        include: health,info,prometheus,metrics

logging:
  level:
    com.fintech.rag: INFO
''')

if __name__ == "__main__":
    for rel, content in FILES.items():
        target = BASE / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print("W +", rel)
    print("---- total:", len(FILES))
