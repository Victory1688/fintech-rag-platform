# fintech-rag-platform

> 金融信贷领域 **企业级 RAG 知识库平台** —— 私有化单租户部署的 Spring Boot 3 微服务工程。
> 目标是在「**有据可依、可追溯、可审计**」的前提下，为信贷业务提供知识检索与智能问答能力。

[![Java](https://img.shields.io/badge/Java-17-blue)]()
[![Spring Boot](https://img.shields.io/badge/Spring%20Boot-3.5.x-green)]()
[![Spring Cloud](https://img.shields.io/badge/Spring%20Cloud-2025.0.x-green)]()
[![License](https://img.shields.io/badge/License-Proprietary-red)]()

---

## 1. 这是什么

面向信贷业务的知识密集型问答系统。与通用「文档问答 Demo」的核心区别：

| 维度 | 本项目的做法 | 为什么 |
|---|---|---|
| **不编造** | 空召回时**不调用大模型**，直接返回兜底话术 | 金融场景下「编一个答案」的代价远高于「答不上来」 |
| **可追溯** | 每次回答都带引用片段与 `traceId`，可回放到具体文档 | 合规审计与客诉复盘的前置条件 |
| **越权防护** | 知识库范围由服务端按主体推导，**请求体传入值仅作意图** | 前端可传任何 `datasetIds`，绝不能当授权依据 |
| **全链路观测** | W3C `traceparent` 贯穿 6 个服务 + LLM 调用 | 「日志里有 ID、链路里查不到」是排障地狱 |
| **内容不出内网** | 采集档位默认 `METRICS_ONLY`，不落问答原文 | 信贷问答可能含客户敏感信息 |

---

## 2. 仓库结构

```
.
├── rag-platform/                 # Maven 聚合工程（业务代码）
│   ├── rag-common/               # 公共能力：上下文、常量、工具、可观测基础
│   ├── rag-api/                  # 服务间契约（DTO + Feign Client），同时是对外接入 SDK
│   ├── rag-gateway/              # 唯一外网入口：鉴权、来源标识注入、追踪头洗白
│   ├── rag-platform-service/     # 平台域：租户/用户/知识库元数据/模型配置
│   ├── rag-knowledge-service/    # 知识域：知识库与文档管理
│   ├── rag-ingest-service/       # 入库域：文档解析、切分、向量化、状态机
│   ├── rag-retrieval-service/    # 检索域：混合检索、重排、权限过滤（RAGFlow 唯一出口）
│   └── rag-chat-service/         # 问答域：LangChain4j 编排、SSE 流式、护栏、Token 计量
├── docs/                         # 设计文档（见 §5 索引）
├── deploy/observability/         # 可观测底座编排：OTel Collector / Prometheus / Grafana / LangFuse
├── tools/                        # 骨架生成与自检脚本
└── *.txt                         # 原始需求与方案输入稿（归档保留）
```

---

## 3. 模块与端口

| 模块 | 服务名（Nacos serviceId） | 端口 | 职责 |
|---|---|---|---|
| `rag-gateway` | `rag-gateway` | 8080 | 外网唯一入口；鉴权、限流、`X-Request-Source` 注入、`traceparent` 洗白后重写 |
| `rag-platform-service` | `rag-platform-service` | 8081 | 主体身份、知识库元数据、模型路由配置 |
| `rag-knowledge-service` | `rag-knowledge-service` | 8082 | 知识库 / 文档 CRUD，RAGFlow 数据集映射 |
| `rag-ingest-service` | `rag-ingest-service` | 8083 | 上传 → 解析 → 切分 → 向量化，状态机 + Outbox |
| `rag-retrieval-service` | `rag-retrieval-service` | 8084 | 混合检索 + 重排 + ACL 过滤；**RAGFlow API Key 持有者** |
| `rag-chat-service` | `rag-chat-service` | 8085 | 问答编排、SSE 流式、护栏、Token 计量 |

- Nacos：group `RAG_GROUP`，namespace `rag`
- 路径契约：各服务 Controller **直接暴露 `/api/**`**，网关**不做** `RewritePath`（内外网共用同一套路径）

---

## 4. 快速开始

### 4.1 前置环境

| 组件 | 版本 | 说明 |
|---|---|---|
| JDK | 17（Temurin） | 必须 17，未验证 21 |
| Maven | 3.9+ | 用于构建 |
| MySQL | 8.0 | 业务库 |
| Redis | 7.x | 缓存、Nonce 防重放、检索缓存 |
| Nacos | 2.3+ | 注册中心 + 配置中心 |
| RAGFlow | 见部署文档 | 解析与检索引擎 |
| MinIO | 最新 | 原始文档对象存储 |

### 4.2 启动顺序（不可颠倒）

```
1) 可观测底座（可选，建议先起）  →  deploy/observability/README.md
2) MySQL / Redis / Nacos / MinIO
3) rag-platform-service  (8081)   ← 其余服务依赖其身份与元数据能力
4) rag-knowledge-service (8082) / rag-ingest-service (8083)
5) rag-retrieval-service (8084)
6) rag-chat-service      (8085)
7) rag-gateway           (8080)   ← 最后启动，等下游就绪
```

### 4.3 密钥（**全部走环境变量或 Nacos 加密配置，禁止入库**）

```bash
export RAG_AES_KEY=...            # AES-256 主密钥（Base64 32B）
export RAG_JWT_SECRET=...
export RAGFLOW_API_KEY=...
export MINIO_ACCESS_KEY=... MINIO_SECRET_KEY=...
export RAG_SUBJECT_HASH_SALT=...  # 主体哈希盐，观测埋点用
```

### 4.4 骨架生成与自检

```bash
python tools/gen_s1_root_common.py           # 根 POM + rag-common
python tools/gen_s2_api.py                   # rag-api
python tools/gen_s3_gateway_platform.py
python tools/gen_s4_server_auth.py           # 必须晚于 s2
python tools/gen_s5_knowledge_ingest.py
python tools/gen_s6_retrieval_chat.py
python tools/gen_s7_observability.py         # 可观测：公共能力 + 网关
python tools/gen_s8_observability_chat.py
python tools/gen_s9_observability_retrieval.py
python tools/gen_s10_observability_deploy.py # 可观测部署编排
python tools/gen_s11_observability_feign.py  # 跨服务 traceparent 透传补丁
python tools/check_skeleton.py               # 结构与埋点一致性自检
```

---

## 5. 文档索引

| 文档 | 内容 | 主要读者 |
|---|---|---|
| [`docs/01-架构与技术落地方案.md`](docs/01-架构与技术落地方案.md) | 总体架构、服务拆分、技术选型与决策记录 | 架构 / 后端 |
| [`docs/02-PRD-金融信贷RAG知识库.md`](docs/02-PRD-金融信贷RAG知识库.md) | 产品需求、角色、核心流程与验收标准 | 产品 / 测试 |
| [`docs/03-数据模型与接口契约.md`](docs/03-数据模型与接口契约.md) | DDL、表设计、HTTP 接口与请求头契约 | 后端 |
| [`docs/04-工程骨架与实施路线.md`](docs/04-工程骨架与实施路线.md) | 目录树、启动顺序、待补齐项与冒烟清单 | 后端 / 运维 |
| [`docs/05-AI可观测与运维监控方案.md`](docs/05-AI可观测与运维监控方案.md) | 观测分层、埋点规范、LangFuse 选型、告警与看板 | 后端 / SRE |
| [`deploy/observability/README.md`](deploy/observability/README.md) | 观测底座部署、验证清单、常见问题 | SRE |

---

## 6. 安全红线（Pull Request 会被直接打回）

1. `datasetIds` / 知识库范围**只能由服务端按主体推导**，请求体传入值仅作意图，不得作为授权依据。
2. 两套鉴权的唯一分流点是 `X-Request-Source`（**仅网关注入**）：内网请求携带该头 → 直接 403。
3. 内网 Feign 客户端**禁止**添加 `X-Request-Source`。
4. RAGFlow API Key 只允许出现在 `knowledge` / `ingest` / `retrieval` 三个服务。
5. 空召回时**不调用大模型**（无据不答）。
6. 检索缓存 Key 必须用 `RetrievalCacheKeyBuilder` 构造，**禁止手写**（缺权限指纹 = 越权）。
7. 密钥只走环境变量 / Nacos 加密配置，**禁止入库、禁止提交仓库**。
8. 可观测内容采集默认 `METRICS_ONLY`；`FULL_CONTENT` 仅限开发环境，且受 `allow-plain-text-content` 防呆闸约束。

---

## 7. 工程约定

- **命名**：根包 `com.fintech.rag`；分层 `api` / `app` / `domain` / `infra` / `config`。
- **依赖**：所有三方版本在根 POM 统一锁定，子模块禁止自行指定 `version`；Spring Boot / Cloud / Cloud Alibaba 必须**成套升级**。
- **事务**：事务只包本地库；RAGFlow / LLM / MinIO 调用一律在事务外，靠状态机 + 重试补偿。
- **异步**：「写本地库 + 通知下游」必须走本地消息表（Outbox），禁止裸发 MQ。
- **超时**：跨服务调用必须显式配置超时（鉴权类 ≤ 500ms）。
- **提交**：`<type>(<scope>): <subject>`，例如 `feat(retrieval): 支持按部门 ACL 过滤`。

---

## 8. 版本基线

```
Java               17
Spring Boot        3.5.6
Spring Cloud       2025.0.0
Spring Cloud Alibaba 2025.0.0.0
LangChain4j        1.20.0
MyBatis-Plus       3.5.9
```

> 三者（Boot / Cloud / Alibaba）必须按官方对照表成套升级，只升其中一个会导致 Nacos 装配失败。
> 落地时请以 start.spring.io 与 mvnrepository 的实时可用版本为准。
