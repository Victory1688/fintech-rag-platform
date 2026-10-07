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
