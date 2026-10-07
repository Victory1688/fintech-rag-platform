# 可观测平台部署（LangFuse + OTel Collector + Prometheus/Grafana）

> 配套文档：`docs/05-AI可观测与运维监控方案.md`
> 目录用途：把 6 个业务服务的「链路 + 指标 + AI 业务观测」落成一套可私有化部署的底座。

## 1. 组件与职责

| 组件 | 职责 | 不负责 |
|---|---|---|
| **LangFuse v3** | AI 业务链路回放、Token 成本、人工标注、LLM-as-judge 评估、Prompt 版本管理 | 基础设施监控、限流熔断、告警中心 |
| **OTel Collector** | 唯一上报出口：接收 → 兜底脱敏 → 尾部采样 → 扇出 | 存储 |
| **Prometheus** | 拉取各服务 `/actuator/prometheus`（JVM、HTTP、GenAI 指标） | 接收 trace |
| **Alertmanager** | 告警分级路由（P0/P1/P2/P3）→ 企业微信 / 邮件 | 产生告警 |
| **Grafana** | 系统总览 / AI 链路 / 成本用量 / 质量看板 | — |

## 2. 快速开始

```bash
cd deploy/observability

# 1) 生成 .env 与全部密钥
cp env.example .env
./init-secrets.sh          # 首次会提示你填入 LangFuse API Key

# 2) ClickHouse 依赖的系统参数
sudo sysctl -w vm.max_map_count=262144

# 3) 拉起全部组件
docker compose -f docker-compose-observability.yml --env-file .env up -d

# 4) 首次启动后在 LangFuse UI 创建项目并取得 API Key
#    访问 http://<host>:3000（默认只绑 127.0.0.1，请用 SSH 隧道或反向代理）
#    拿到 pk/sk 后回填 .env，重新执行 ./init-secrets.sh 并重启 Collector
docker compose -f docker-compose-observability.yml restart otel-collector
```

**访问入口（默认只绑 127.0.0.1，需 SSH 隧道）**

| 组件 | 端口 |
|---|---|
| LangFuse UI | 3000 |
| Grafana | 3001 |
| Prometheus | 9090 |
| Alertmanager | 9093 |
| MinIO 控制台 | 9091 |

## 3. 业务服务侧需要配置的环境变量

```bash
# 应用只认 Collector，不认 LangFuse（LangFuse 密钥只配在 Collector 这一处）
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://otel-collector.rag.local:4318/v1/traces
export OTEL_SERVICE_NAME=rag-chat-service
export OTEL_RESOURCE_ATTRIBUTES=deployment.environment=prod,service.namespace=rag
export OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental

export RAG_OBS_CONTENT_LEVEL=METRICS_ONLY   # 生产默认：不落问答原文
export RAG_OBS_SAMPLING=0.2
export RAG_SUBJECT_HASH_SALT=$(openssl rand -hex 16)
```

> 6 个服务共用的 OTLP / 采样 / 采集档位建议放到 Nacos 的 `rag-common.yaml`，
> 避免改一次配置要动 6 份文件。

## 4. 验证清单（逐条做，不要跳）

| # | 验证项 | 动作 | 期望 |
|---|---|---|---|
| 1 | Collector 存活 | `curl localhost:13133` | 返回 200 |
| 2 | traceId 全链路一致 | 发一次问答，比对网关/chat/retrieval 日志的 traceId | 三处一致，且为 **32 位小写 hex** |
| 3 | traceparent 洗白 | 手工带伪造 `traceparent: 00-aaaa...-bbbb...-01` 调网关 | LangFuse 里的 traceId **不是**伪造值 |
| 4 | LangFuse 收到 Trace | 打开 LangFuse → Traces | 能看到 `rag.chat.answer` 根 span 及其子 span |
| 5 | 指标被采集 | Prometheus 查询 `rag_chat_answer_total` | 有数据 |
| 6 | **LangFuse 宕机** | `docker stop langfuse-web langfuse-worker` 后压测问答 | 业务 RT 无明显变化、成功率不变（关键演练） |
| 7 | **Collector 宕机** | `docker stop otel-collector` 后压测 | 同上 |
| 8 | 空召回不调用大模型 | 提问知识库里没有的内容 | `rag_chat_answer_total{outcome="ABSTAINED"}` +1，且模型指标无增长 |
| 9 | 告警能触达 | 手工停一个服务 | P0 告警在 1~2 分钟内到达企业微信 |
| 10 | actuator 不可外达 | 从外网/办公网访问任一服务 `/actuator/env` | 403 / 不可达 |

## 5. 运维要点

| 主题 | 要点 |
|---|---|
| **备份** | PostgreSQL 每日 `pg_dump`；ClickHouse/MinIO 走卷快照或对象复制；保留 30 天 |
| **数据生命周期** | ClickHouse 表级 TTL（内容类 30 天、纯指标 90~180 天）；MinIO 桶生命周期规则；Prometheus 原始 15 天 |
| **资源** | 全栈约 14 vCPU / 18 GB / 450 GB 起；ClickHouse 必须显式限制内存，否则会吃掉宿主机空闲内存 |
| **升级** | LangFuse 走 OTLP 接入（不用已日落的旧 Ingestion API），因此 v3→v4 是配置级迁移而非代码级 |
| **多环境** | dev/staging/prod 各自独立 LangFuse project 与 API Key，避免压测数据污染真实质量指标 |
| **权限** | 自托管开源版 RBAC 粒度较粗，用「知识库 → project 映射 + 网络层限制 + 堡垒机」替代细粒度权限 |
| **故障降级** | LangFuse / Collector / Prometheus 任一宕机，业务必须零影响；超限只允许丢 trace，绝不阻塞 |
| **合规** | 生产锁 `RAG_OBS_CONTENT_LEVEL=METRICS_ONLY`；告警文本禁止携带问答原文与用户身份 |

## 6. 常见问题

| 现象 | 原因与处理 |
|---|---|
| LangFuse 起不来 | 检查 MinIO 是否健康（v3 必需对象存储）；检查 `ENCRYPTION_KEY`/`SALT` 是否为 32 字节 hex |
| ClickHouse OOM | 容器内存上限调小（如 `deploy.resources.limits.memory: 2g`），并确认 `memory_limiter` 已启用 |
| LangFuse 里看不到 Trace | ① Collector 的 `LANGFUSE_AUTH_HEADER` 是否为 `base64(pk:sk)`；② 是否带了 `x-langfuse-ingestion-version: 4`；③ `docker logs otel-collector` 看导出错误 |
| Trace 变成两条互不相关的链路 | 检查网关 `accept-client-traceparent` 是否为 false，以及 SSE 线程池是否恢复了父 span（见 `ChatController`） |
| 指标里没有 GenAI 指标 | 确认 `micrometer-registry-prometheus` 与 OTel 依赖已生效；`/actuator/prometheus` 里搜 `gen_ai` |
| locale / 时区导致日期对不上 | Prometheus 与本地库统一用 Asia/Shanghai 业务日期切分（docs/05 §7.3） |
