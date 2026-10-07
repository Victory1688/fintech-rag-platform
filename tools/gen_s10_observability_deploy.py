# -*- coding: utf-8 -*-
"""
S10: 生成可观测部署编排（deploy/observability/）

产出：LangFuse v3 六件套 + OTel Collector + Prometheus + Alertmanager + Grafana 的
      一键部署编排、告警规则、看板与运维说明。

执行顺序：s1 → s2 → s3 → s4 → s5 → s6 → s7 → s8 → s9 → s10 → check_skeleton.py
"""
import pathlib

BASE = pathlib.Path(r"D:/AiWorkOut/java-ai/deploy/observability")
FILES = {}


def add(rel, content):
    FILES[rel] = content.lstrip("\n")


# ============================================================================
# 1. Docker Compose 编排
# ============================================================================
add("docker-compose-observability.yml", r'''
# =============================================================================
# RAG 可观测平台编排（Docker Compose）
#
# 组成：
#   LangFuse v3（AI 业务可观测与评估）：web + worker + Postgres + ClickHouse + Redis + MinIO
#   OTel Collector（唯一上报出口：接收 → 脱敏 → 尾部采样 → 扇出）
#   Prometheus + Alertmanager + Grafana（基础设施与服务指标、告警、看板）
#
# 【安全默认】除 Collector 的两个 OTLP 端口外，其余一律只绑 127.0.0.1。
#   生产请按 docs/05 §3.3 的网络矩阵收敛到内网独立网段，LangFuse UI 走堡垒机 + SSO。
#
# 启动前必做：
#   1. cp env.example .env 并填入全部密钥
#   2. sysctl -w vm.max_map_count=262144      # ClickHouse 需要
#   3. ./init-secrets.sh                      # 生成 LangFuse Basic Auth 头
#   4. docker compose -f docker-compose-observability.yml --env-file .env up -d
# =============================================================================
name: rag-observability

services:
  # ------------------------------------------------------------------ LangFuse
  langfuse-web:
    image: langfuse/langfuse:3
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      clickhouse:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
    ports:
      # 仅本机/内网可达。办公网访问请走反向代理 + 堡垒机 + SSO
      - "127.0.0.1:3000:3000"
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      NEXTAUTH_URL: ${NEXTAUTH_URL}
      NEXTAUTH_SECRET: ${NEXTAUTH_SECRET}
      SALT: ${SALT}
      ENCRYPTION_KEY: ${ENCRYPTION_KEY}
      CLICKHOUSE_URL: http://clickhouse:8123
      CLICKHOUSE_MIGRATION_URL: clickhouse://clickhouse:9000
      CLICKHOUSE_USER: ${CLICKHOUSE_USER}
      CLICKHOUSE_PASSWORD: ${CLICKHOUSE_PASSWORD}
      CLICKHOUSE_CLUSTER_ENABLED: "false"
      REDIS_HOST: redis
      REDIS_PORT: "6379"
      REDIS_AUTH: ${REDIS_AUTH}
      # 事件/多媒体对象存储：LangFuse v3 起【必需】，缺失会直接启动失败
      LANGFUSE_S3_EVENT_UPLOAD_BUCKET: langfuse
      LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT: http://minio:9000
      LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID: ${MINIO_ROOT_USER}
      LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY: ${MINIO_ROOT_PASSWORD}
      LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE: "true"
      LANGFUSE_S3_EVENT_UPLOAD_REGION: auto
      LANGFUSE_S3_MEDIA_UPLOAD_BUCKET: langfuse
      LANGFUSE_S3_MEDIA_UPLOAD_ENDPOINT: http://minio:9000
      LANGFUSE_S3_MEDIA_UPLOAD_ACCESS_KEY_ID: ${MINIO_ROOT_USER}
      LANGFUSE_S3_MEDIA_UPLOAD_SECRET_ACCESS_KEY: ${MINIO_ROOT_PASSWORD}
      LANGFUSE_S3_MEDIA_UPLOAD_FORCE_PATH_STYLE: "true"
      LANGFUSE_S3_MEDIA_UPLOAD_REGION: auto
      # 全离线部署：关闭遥测
      TELEMETRY_ENABLED: "false"
      LANGFUSE_LOG_LEVEL: info
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:3000/api/public/health"]
      interval: 30s
      timeout: 5s
      retries: 5

  langfuse-worker:
    image: langfuse/langfuse-worker:3
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      clickhouse:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      SALT: ${SALT}
      ENCRYPTION_KEY: ${ENCRYPTION_KEY}
      CLICKHOUSE_URL: http://clickhouse:8123
      CLICKHOUSE_MIGRATION_URL: clickhouse://clickhouse:9000
      CLICKHOUSE_USER: ${CLICKHOUSE_USER}
      CLICKHOUSE_PASSWORD: ${CLICKHOUSE_PASSWORD}
      REDIS_HOST: redis
      REDIS_PORT: "6379"
      REDIS_AUTH: ${REDIS_AUTH}
      LANGFUSE_S3_EVENT_UPLOAD_BUCKET: langfuse
      LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT: http://minio:9000
      LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID: ${MINIO_ROOT_USER}
      LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY: ${MINIO_ROOT_PASSWORD}
      LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE: "true"
      LANGFUSE_S3_EVENT_UPLOAD_REGION: auto
      TELEMETRY_ENABLED: "false"

  postgres:
    image: postgres:17-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - lf_postgres:/var/lib/postgresql/data
    ports:
      - "127.0.0.1:5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 10

  clickhouse:
    image: clickhouse/clickhouse-server:24
    restart: unless-stopped
    # ClickHouse 默认会吃掉空闲内存，必须显式限制，否则会连累宿主机上其他组件
    ulimits:
      nofile:
        soft: 262144
        hard: 262144
    environment:
      CLICKHOUSE_USER: ${CLICKHOUSE_USER}
      CLICKHOUSE_PASSWORD: ${CLICKHOUSE_PASSWORD}
      CLICKHOUSE_DB: ${CLICKHOUSE_DB}
      CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT: "1"
    volumes:
      - lf_clickhouse:/var/lib/clickhouse
    ports:
      - "127.0.0.1:8123:8123"
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:8123/ping"]
      interval: 10s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: ["redis-server", "--requirepass", "${REDIS_AUTH}", "--appendonly", "yes"]
    volumes:
      - lf_redis:/data
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_AUTH}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 10

  minio:
    image: minio/minio
    restart: unless-stopped
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    volumes:
      - lf_minio:/data
    # 注意：MinIO API 默认 9000，与 ClickHouse 原生端口冲突，故对外映射为 9090
    ports:
      - "127.0.0.1:9090:9000"
      - "127.0.0.1:9091:9001"
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 10s
      timeout: 5s
      retries: 10

  # ----------------------------------------------------------- OTel Collector
  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    restart: unless-stopped
    command: ["--config=/etc/otelcol/config.yaml"]
    volumes:
      - ./otel-collector-config.yaml:/etc/otelcol/config.yaml:ro
    environment:
      # Base64(pk-lf-xxx:sk-lf-xxx)，由 init-secrets.sh 生成
      LANGFUSE_AUTH_HEADER: ${LANGFUSE_AUTH_HEADER}
      LANGFUSE_OTLP_ENDPOINT: http://langfuse-web:3000/api/public/otel
      DEPLOY_ENV: ${DEPLOY_ENV}
    ports:
      # 6 个业务服务统一上报到这里（内网放通；生产禁止暴露到办公网）
      - "4318:4318"
      - "4317:4317"
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:13133/"]
      interval: 20s
      timeout: 5s
      retries: 5

  # -------------------------------------------------------------- Prometheus
  prometheus:
    image: prom/prometheus:latest
    restart: unless-stopped
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./alert-rules.yml:/etc/prometheus/alert-rules.yml:ro
      - prom_data:/prometheus
    environment:
      DEPLOY_ENV: ${DEPLOY_ENV}
    command:
      - "--config.file=/etc/prometheus/prometheus.yml"
      - "--storage.tsdb.path=/prometheus"
      # 见 docs/05 §7.4：原始指标保留 15 天，长期趋势靠 recording rules 聚合
      - "--storage.tsdb.retention.time=15d"
      - "--web.enable-lifecycle"
    ports:
      - "127.0.0.1:9090:9090"

  alertmanager:
    image: prom/alertmanager:latest
    restart: unless-stopped
    volumes:
      # 注意：Alertmanager 配置【不支持】环境变量插值，
      # 请先用 init-secrets.sh 里的 envsubst 生成 alertmanager.yml（模板见 alertmanager.yml.tpl）
      - ./alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro
    ports:
      - "127.0.0.1:9093:9093"

  # ----------------------------------------------------------------- Grafana
  grafana:
    image: grafana/grafana-oss:latest
    restart: unless-stopped
    environment:
      GF_SECURITY_ADMIN_USER: ${GRAFANA_USER}
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD}
      GF_USERS_ALLOW_SIGN_UP: "false"
    volumes:
      - ./grafana-provisioning:/etc/grafana/provisioning:ro
      - ./grafana-dashboard-observability.json:/etc/grafana/provisioning/dashboards/rag-observability.json:ro
      - grafana_data:/var/lib/grafana
    ports:
      - "127.0.0.1:3001:3000"

volumes:
  lf_postgres:
  lf_clickhouse:
  lf_redis:
  lf_minio:
  prom_data:
  grafana_data:
''')

# ============================================================================
# 2. OTel Collector 配置
# ============================================================================
add("otel-collector-config.yaml", r'''
# =============================================================================
# OTel Collector —— 应用与可观测后端之间的唯一中介
#
# 设计要点（对应 docs/05 §1.2 第 4 条、§6、§7）：
#   1. 应用只认本 Collector，不认 LangFuse：换后端/改采样/改脱敏都不用重新发版。
#   2. LangFuse 的 OTLP 端点需要 Basic Auth 与自定义版本头，故用 otlphttp 而非 otlp。
#   3. 指标【不】走 Collector —— Prometheus 直接拉各服务的 /actuator/prometheus。
#      原因：Prometheus 是 pull 模型，不存在「Collector push 给 Prometheus」的标准数据流。
#   4. 尾部采样保证「坏样本一条不丢」：错误 / 无据不答 / 护栏命中 / 慢请求 100% 保留。
#   5. 兜底脱敏：真正的脱敏在应用侧完成，这里是安全网而非控制手段。
# =============================================================================
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  # 必须放第一位：OOM 是 Collector 最常见的自杀原因
  memory_limiter:
    check_interval: 1s
    limit_percentage: 75
    spike_limit_percentage: 20

  # 统一资源属性，便于按环境/命名空间过滤
  resource:
    attributes:
      - key: deployment.environment
        value: ${env:DEPLOY_ENV}
        action: upsert
      - key: service.namespace
        value: rag
        action: upsert

  # 兜底脱敏：删除不应上报的属性、对内容属性做掩码
  # 注意：这是安全网。真正的脱敏在应用侧 ContentSanitizer 完成（docs/05 §1.2 第 11 条）
  transform/redact:
    error_mode: ignore
    trace_statements:
      - context: span
        statements:
          # 移除任何可能被误采集的身份/凭据字段
          - delete_key(attributes, "rag.user.id")
          - delete_key(attributes, "rag.user.name")
          - delete_key(attributes, "rag.app.secret")
          - delete_key(attributes, "http.request.header.authorization")
          - delete_key(attributes, "http.request.header.x-app-signature")
          - delete_key(attributes, "http.request.header.x-user-token")
          - delete_key(attributes, "http.request.header.cookie")
          # 内容属性兜底掩码：即便应用侧误采集，也不让证件号/手机号原样出内网
          - replace_pattern(attributes["gen_ai.input.messages"], "1[3-9][0-9]{9}", "1**********")
          - replace_pattern(attributes["gen_ai.output.messages"], "1[3-9][0-9]{9}", "1**********")
          - replace_pattern(attributes["gen_ai.input.messages"], "[0-9]{17}[0-9Xx]", "******************")
          - replace_pattern(attributes["gen_ai.output.messages"], "[0-9]{17}[0-9Xx]", "******************")

  # 尾部采样：先缓冲整条 trace 再决策，因此可以按「结果好坏」而非只按比例采样
  tail_sampling:
    decision_wait: 10s
    num_traces: 50000
    expected_new_traces_per_sec: 200
    policies:
      # 1) 错误链路 100% 保留
      - name: errors-always
        type: status_code
        status_code:
          status_codes: [ERROR]
      # 2) 业务异常结果 100% 保留（最有价值的质量样本）
      - name: no-hit-always
        type: string_attribute
        string_attribute:
          key: rag.outcome
          values: [NO_HIT, ERROR, GUARDRAIL_BLOCKED]
      # 3) 护栏命中 100% 保留
      - name: guardrail-always
        type: string_attribute
        string_attribute:
          key: rag.guardrail.hit
          values: ["true"]
      # 4) 慢请求 100% 保留（阈值对齐 SLO：生成链路 P95 ≤ 8s）
      - name: slow-requests
        type: latency
        latency:
          threshold_ms: 8000
      # 5) 其余兜底放行：真正的降采样交给应用侧 head sampling（两者是乘积关系）
      - name: baseline
        type: probabilistic
        probabilistic:
          sampling_percentage: 100

  batch:
    timeout: 5s
    send_batch_size: 512
    send_batch_max_size: 1024

exporters:
  # LangFuse：OTLP over HTTP + Basic Auth + ingestion 版本头
  otlphttp/langfuse:
    endpoint: ${env:LANGFUSE_OTLP_ENDPOINT}
    headers:
      Authorization: "Basic ${env:LANGFUSE_AUTH_HEADER}"
      # LangFuse 要求显式声明 ingestion 版本，缺失会静默丢数据
      x-langfuse-ingestion-version: "4"
    compression: gzip
    timeout: 10s
    retry_on_failure:
      enabled: true
      initial_interval: 2s
      max_interval: 30s
      max_elapsed_time: 120s
    sending_queue:
      enabled: true
      num_consumers: 4
      queue_size: 5000

  # 全量 trace 的第二个出口（二期启用，见 docs/05 §3.1）
  # otlphttp/tempo:
  #   endpoint: http://tempo:4318
  #   tls:
  #     insecure: true

  # 本地排查用：只打印摘要，不打印内容
  debug:
    verbosity: basic
    sampling_initial: 5
    sampling_thereafter: 200

extensions:
  health_check:
    endpoint: 0.0.0.0:13133

service:
  extensions: [health_check]
  telemetry:
    logs:
      level: info
    metrics:
      level: basic
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, resource, transform/redact, tail_sampling, batch]
      # 二期需要「全量 trace 检索」时，把 otlphttp/tempo 解注释并加到这里
      exporters: [otlphttp/langfuse, debug]
''')

# ============================================================================
# 3. Prometheus 抓取配置
# ============================================================================
add("prometheus.yml", r'''
# =============================================================================
# Prometheus 抓取配置
#
# 关键点：Prometheus 是【pull】模型 —— 各服务暴露 /actuator/prometheus，
# Prometheus 定时来抓。不存在「OTel Collector 把指标推给 Prometheus」这种标准数据流；
# 若确需 push，应使用 prometheusremotewrite exporter 推到 remote-write 端点。
# =============================================================================
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: rag
    env: ${DEPLOY_ENV}

rule_files:
  - /etc/prometheus/alert-rules.yml

alerting:
  alertmanagers:
    - static_configs:
        - targets: ["alertmanager:9093"]

scrape_configs:
  # ---------------------------------------------------------------- 业务服务
  # 说明：/actuator/prometheus 只应经内网直连，禁止通过 DMZ 网关对外暴露
  - job_name: rag-gateway
    metrics_path: /actuator/prometheus
    static_configs:
      - targets: ["rag-gateway:8080"]
  - job_name: rag-platform-service
    metrics_path: /actuator/prometheus
    static_configs:
      - targets: ["rag-platform-service:8081"]
  - job_name: rag-knowledge-service
    metrics_path: /actuator/prometheus
    static_configs:
      - targets: ["rag-knowledge-service:8082"]
  - job_name: rag-ingest-service
    metrics_path: /actuator/prometheus
    static_configs:
      - targets: ["rag-ingest-service:8083"]
  - job_name: rag-retrieval-service
    metrics_path: /actuator/prometheus
    static_configs:
      - targets: ["rag-retrieval-service:8084"]
  - job_name: rag-chat-service
    metrics_path: /actuator/prometheus
    static_configs:
      - targets: ["rag-chat-service:8085"]

  # 生产建议改为基于 Nacos 服务发现的动态抓取，避免服务扩缩容后漏抓：
  # - job_name: rag-services
  #   metrics_path: /actuator/prometheus
  #   nacos_sd_configs:
  #     - server: nacos:8848
  #       namespace: rag
  #       group: RAG_GROUP

  # ------------------------------------------------------------ 可观测自身
  - job_name: otel-collector
    static_configs:
      - targets: ["otel-collector:8888"]
  - job_name: prometheus
    static_configs:
      - targets: ["localhost:9090"]
''')

# ============================================================================
# 4. 告警规则
# ============================================================================
add("alert-rules.yml", r'''
# =============================================================================
# 告警规则（对应 docs/05 §9.1 的分级）
#
# 纪律一：告警文本不含业务内容（只含指标、阈值、服务名、traceId）
# 纪律二：质量类告警需要基线 —— 上线前 2 周只观测不告警，第 3 周起按实测值设阈值
# =============================================================================
groups:
  # ------------------------------------------------------------- P0 服务不可用
  - name: rag-p0-availability
    rules:
      - alert: RagServiceDown
        expr: up{job=~"rag-.*"} == 0
        for: 1m
        labels:
          severity: P0
        annotations:
          summary: "服务不可用：{{ $labels.job }}"
          description: "Prometheus 已连续 1 分钟抓不到 {{ $labels.job }} 的指标端点。"

      - alert: RagModelCallFailureCritical
        expr: |
          sum(rate(gen_ai_client_operation_duration_seconds_count{error_type!=""}[5m]))
          / clamp_min(sum(rate(gen_ai_client_operation_duration_seconds_count[5m])), 1) > 0.2
        for: 5m
        labels:
          severity: P0
        annotations:
          summary: "模型调用失败率超过 20%"
          description: "模型侧可能整体不可用，请检查上游供应商与网络链路。"

  # ---------------------------------------------------------- P1 质量与成本
  - name: rag-p1-quality-cost
    rules:
      - alert: RagModelCallFailureHigh
        expr: |
          sum(rate(gen_ai_client_operation_duration_seconds_count{error_type!=""}[5m]))
          / clamp_min(sum(rate(gen_ai_client_operation_duration_seconds_count[5m])), 1) > 0.05
        for: 5m
        labels:
          severity: P1
        annotations:
          summary: "模型调用失败率超过 5%"

      - alert: RagEmptyRetrievalSpike
        expr: |
          sum(rate(rag_retrieval_empty_total[15m]))
          / clamp_min(sum(rate(rag_retrieval_total[15m])), 1) > 0.3
        for: 15m
        labels:
          severity: P1
        annotations:
          summary: "空召回率超过 30%（15 分钟窗口）"
          description: "知识库可能出现缺口，或检索参数劣化。请核对最近的知识库变更与解析失败堆积。"

      - alert: RagTokenCostSurge
        expr: |
          sum(rate(gen_ai_client_token_usage_sum[1h]))
          > 3 * sum(rate(gen_ai_client_token_usage_sum[1h] offset 1d))
        for: 15m
        labels:
          severity: P1
        annotations:
          summary: "Token 消耗超过昨日同期 3 倍"
          description: "可能是刷量、Prompt 膨胀或上下文裁剪失效。"

      - alert: RagGuardrailBlockedRising
        expr: sum(rate(rag_guardrail_hit_total[30m])) > 1
        for: 30m
        labels:
          severity: P1
        annotations:
          summary: "护栏拦截持续发生"
          description: "可能是提示词注入攻击，或知识库出现了应被过滤的内容。"

  # -------------------------------------------------------- P2 性能与体验
  - name: rag-p2-performance
    rules:
      - alert: RagRetrievalSlow
        expr: |
          histogram_quantile(0.95,
            sum(rate(http_server_requests_seconds_bucket{job="rag-retrieval-service"}[5m])) by (le)
          ) > 1
        for: 5m
        labels:
          severity: P2
        annotations:
          summary: "检索 P95 超过 1s"

      - alert: RagTimeToFirstChunkSlow
        expr: |
          histogram_quantile(0.95,
            sum(rate(gen_ai_client_operation_time_to_first_chunk_seconds_bucket[5m])) by (le)
          ) > 1.5
        for: 5m
        labels:
          severity: P2
        annotations:
          summary: "流式首字延迟 P95 超过 1.5s"
          description: "注意：本指标包含检索耗时，是用户真实感知的延迟。"

      - alert: RagGatewayRateLimitHigh
        expr: |
          sum(rate(spring_cloud_gateway_requests_seconds_count{status="429"}[5m]))
          / clamp_min(sum(rate(spring_cloud_gateway_requests_seconds_count[5m])), 1) > 0.1
        for: 10m
        labels:
          severity: P2
        annotations:
          summary: "网关限流拒绝率超过 10%"
          description: "可能是正常业务增长，也可能是被刷。"

  # ---------------------------------------------------------------- P3 运维
  - name: rag-p3-ops
    rules:
      - alert: RagIngestParseFailurePileUp
        expr: sum(increase(rag_ingest_task_failed_total[1h])) > 20
        for: 10m
        labels:
          severity: P3
        annotations:
          summary: "文档解析失败堆积超过 20 个/小时"

      - alert: RagCollectorQueueSaturated
        expr: |
          otelcol_exporter_queue_size / clamp_min(otelcol_exporter_queue_capacity, 1) > 0.8
        for: 10m
        labels:
          severity: P3
        annotations:
          summary: "Collector 上报队列占用超过 80%"
          description: "LangFuse 侧可能写入受阻。超限会丢弃 trace，业务不受影响。"

      - alert: RagClickHouseDiskHigh
        expr: |
          (node_filesystem_avail_bytes{mountpoint="/var/lib/clickhouse"}
           / node_filesystem_size_bytes{mountpoint="/var/lib/clickhouse"}) < 0.2
        for: 15m
        labels:
          severity: P3
        annotations:
          summary: "ClickHouse 磁盘剩余不足 20%"
''')

# ============================================================================
# 5. Alertmanager（模板：需 envsubst 生成）
# ============================================================================
add("alertmanager.yml.tpl", r'''
# =============================================================================
# Alertmanager 配置模板
#
# 【重要】Alertmanager 原生【不支持】在配置文件里做环境变量插值，
# 因此本文件是模板，必须先用 envsubst 生成实际配置：
#     envsubst < alertmanager.yml.tpl > alertmanager.yml
# （init-secrets.sh 已包含该步骤）
#
# 【合规红线】出内网的告警文本只允许包含：指标名、阈值、当前值、服务名、traceId。
#            严禁包含问答原文、召回片段、用户身份（姓名 / 手机号 / 身份证）。
# =============================================================================
global:
  resolve_timeout: 5m

route:
  receiver: wecom-default
  group_by: ["alertname", "job"]
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    - matchers: ['severity="P0"']
      receiver: wecom-p0
      group_wait: 10s
      repeat_interval: 30m
    - matchers: ['severity="P1"']
      receiver: wecom-p1
      repeat_interval: 2h
    - matchers: ['severity="P3"']
      receiver: email-daily
      repeat_interval: 24h

inhibit_rules:
  # 服务整体不可用时，抑制它的下级指标告警，避免告警风暴
  - source_matchers: ['alertname="RagServiceDown"']
    target_matchers: ['severity=~"P1|P2|P3"']
    equal: ["job"]

receivers:
  - name: wecom-default
    webhook_configs:
      - url: "${WECOM_WEBHOOK_URL}"
        send_resolved: true
  - name: wecom-p0
    webhook_configs:
      - url: "${WECOM_WEBHOOK_P0_URL}"
        send_resolved: true
  - name: wecom-p1
    webhook_configs:
      - url: "${WECOM_WEBHOOK_URL}"
        send_resolved: true
  - name: email-daily
    email_configs:
      - to: "${OPS_MAIL_TO}"
        from: "${OPS_MAIL_FROM}"
        smarthost: "${OPS_SMTP_HOST}"
        require_tls: true
''')

# ============================================================================
# 6. Grafana provisioning + 看板
# ============================================================================
add("grafana-provisioning/datasources/prometheus.yml", r'''
apiVersion: 1

datasources:
  - name: Prometheus
    uid: rag-prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    jsonData:
      timeInterval: 15s
      httpMethod: POST
''')

add("grafana-provisioning/dashboards/provider.yml", r'''
apiVersion: 1

providers:
  - name: rag-observability
    orgId: 1
    folder: RAG
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    allowUiUpdates: true
    options:
      path: /etc/grafana/provisioning/dashboards
''')

add("grafana-dashboard-observability.json", r'''
{
  "title": "RAG 知识库 · AI 可观测总览",
  "uid": "rag-observability-overview",
  "tags": ["rag", "llm", "observability"],
  "timezone": "browser",
  "schemaVersion": 39,
  "refresh": "30s",
  "time": { "from": "now-6h", "to": "now" },
  "templating": {
    "list": [
      {
        "name": "app_source",
        "label": "流量来源",
        "type": "query",
        "datasource": { "type": "prometheus", "uid": "rag-prometheus" },
        "query": "label_values(rag_chat_answer_total, app_source)",
        "includeAll": true,
        "multi": true,
        "current": { "text": "All", "value": "$__all" }
      },
      {
        "name": "model_code",
        "label": "模型配置",
        "type": "query",
        "datasource": { "type": "prometheus", "uid": "rag-prometheus" },
        "query": "label_values(rag_chat_answer_total, model_code)",
        "includeAll": true,
        "multi": true,
        "current": { "text": "All", "value": "$__all" }
      }
    ]
  },
  "panels": [
    {
      "id": 1,
      "type": "stat",
      "title": "回答总数（近 1 小时）",
      "gridPos": { "h": 5, "w": 6, "x": 0, "y": 0 },
      "datasource": { "type": "prometheus", "uid": "rag-prometheus" },
      "targets": [
        {
          "refId": "A",
          "expr": "sum(increase(rag_chat_answer_total{app_source=~\"$app_source\"}[1h]))"
        }
      ]
    },
    {
      "id": 2,
      "type": "stat",
      "title": "空召回率（无据不答）",
      "description": "知识库覆盖度核心指标。上升说明知识库存在缺口或检索劣化。",
      "gridPos": { "h": 5, "w": 6, "x": 6, "y": 0 },
      "datasource": { "type": "prometheus", "uid": "rag-prometheus" },
      "fieldConfig": {
        "defaults": {
          "unit": "percentunit",
          "thresholds": {
            "mode": "absolute",
            "steps": [
              { "color": "green", "value": null },
              { "color": "yellow", "value": 0.2 },
              { "color": "red", "value": 0.3 }
            ]
          }
        }
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum(rate(rag_chat_answer_total{outcome=\"NO_HIT\"}[15m])) / clamp_min(sum(rate(rag_chat_answer_total[15m])), 1)"
        }
      ]
    },
    {
      "id": 3,
      "type": "stat",
      "title": "首字延迟 P95（秒）",
      "description": "含检索耗时，是用户真实感知的延迟；与模型 span duration 不是同一口径。",
      "gridPos": { "h": 5, "w": 6, "x": 12, "y": 0 },
      "datasource": { "type": "prometheus", "uid": "rag-prometheus" },
      "fieldConfig": {
        "defaults": {
          "unit": "s",
          "thresholds": {
            "mode": "absolute",
            "steps": [
              { "color": "green", "value": null },
              { "color": "yellow", "value": 1.0 },
              { "color": "red", "value": 1.5 }
            ]
          }
        }
      },
      "targets": [
        {
          "refId": "A",
          "expr": "histogram_quantile(0.95, sum(rate(gen_ai_client_operation_time_to_first_chunk_seconds_bucket[5m])) by (le))"
        }
      ]
    },
    {
      "id": 4,
      "type": "stat",
      "title": "模型调用失败率",
      "gridPos": { "h": 5, "w": 6, "x": 18, "y": 0 },
      "datasource": { "type": "prometheus", "uid": "rag-prometheus" },
      "fieldConfig": {
        "defaults": {
          "unit": "percentunit",
          "thresholds": {
            "mode": "absolute",
            "steps": [
              { "color": "green", "value": null },
              { "color": "yellow", "value": 0.05 },
              { "color": "red", "value": 0.2 }
            ]
          }
        }
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum(rate(gen_ai_client_operation_duration_seconds_count{error_type!=\"\"}[5m])) / clamp_min(sum(rate(gen_ai_client_operation_duration_seconds_count[5m])), 1)"
        }
      ]
    },
    {
      "id": 5,
      "type": "timeseries",
      "title": "回答结果分布（按来源拆分）",
      "description": "ANSWERED / NO_HIT / GUARDRAIL_BLOCKED / ERROR 趋势对比；来源即 DMZ_WEB 与 SF_INNER_APP。",
      "gridPos": { "h": 8, "w": 12, "x": 0, "y": 5 },
      "datasource": { "type": "prometheus", "uid": "rag-prometheus" },
      "targets": [
        {
          "refId": "A",
          "expr": "sum by (outcome, app_source) (rate(rag_chat_answer_total{app_source=~\"$app_source\"}[5m]))",
          "legendFormat": "{{app_source}} · {{outcome}}"
        }
      ]
    },
    {
      "id": 6,
      "type": "timeseries",
      "title": "Token 消耗（输入 / 输出）",
      "description": "成本监控。异常突增对应 P1 告警 RagTokenCostSurge。",
      "gridPos": { "h": 8, "w": 12, "x": 12, "y": 5 },
      "datasource": { "type": "prometheus", "uid": "rag-prometheus" },
      "targets": [
        {
          "refId": "A",
          "expr": "sum by (gen_ai_token_type) (rate(gen_ai_client_token_usage_sum[5m]))",
          "legendFormat": "{{gen_ai_token_type}}"
        }
      ]
    }
  ]
}
''')

# ============================================================================
# 7. 环境变量样例与密钥生成脚本
# ============================================================================
add("env.example", r'''
# =============================================================================
# 可观测平台环境变量样例
# 用法：cp env.example .env，填入真实值（.env 必须 chmod 600 且加入 .gitignore）
# 生成随机值请用 hex 而非 base64：base64 含 / + = 会破坏数据库连接串
# =============================================================================

DEPLOY_ENV=prod
NEXTAUTH_URL=http://langfuse.internal.rag:3000

# --- PostgreSQL ---
POSTGRES_USER=langfuse
POSTGRES_PASSWORD=CHANGE_ME
POSTGRES_DB=langfuse

# --- ClickHouse ---
CLICKHOUSE_USER=langfuse
CLICKHOUSE_PASSWORD=CHANGE_ME
CLICKHOUSE_DB=langfuse

# --- Redis ---
REDIS_AUTH=CHANGE_ME

# --- MinIO（LangFuse v3 必需的对象存储）---
MINIO_ROOT_USER=langfuse
MINIO_ROOT_PASSWORD=CHANGE_ME

# --- LangFuse 自身密钥 ---
NEXTAUTH_SECRET=CHANGE_ME
SALT=CHANGE_ME
ENCRYPTION_KEY=CHANGE_ME

# --- LangFuse API Key（在 LangFuse UI 中创建后填入）---
# 该密钥【只配在 Collector】，6 个业务服务都不持有
LANGFUSE_PUBLIC_KEY=pk-lf-CHANGE_ME
LANGFUSE_SECRET_KEY=sk-lf-CHANGE_ME
# 由 init-secrets.sh 生成：base64(publicKey:secretKey)
LANGFUSE_AUTH_HEADER=CHANGE_ME

# --- Grafana ---
GRAFANA_USER=admin
GRAFANA_PASSWORD=CHANGE_ME

# --- 告警通道（Alertmanager 模板插值用）---
WECOM_WEBHOOK_URL=CHANGE_ME
WECOM_WEBHOOK_P0_URL=CHANGE_ME
OPS_MAIL_TO=ops@example.com
OPS_MAIL_FROM=alert@example.com
OPS_SMTP_HOST=smtp.example.com:587
''')

add("init-secrets.sh", r'''
#!/usr/bin/env bash
# =============================================================================
# 初始化密钥与生成实际配置
#   - 为缺省项生成随机密钥（hex，避免连接串被 / + = 破坏）
#   - 生成 LangFuse Basic Auth 头（OTel Collector 使用）
#   - 用 envsubst 由 alertmanager.yml.tpl 生成 alertmanager.yml
# =============================================================================
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -f .env ]; then
  cp env.example .env
  echo "已由 env.example 生成 .env，请填入 LangFuse API Key 后重新执行本脚本。"
fi

# shellcheck disable=SC1091
set -a; . ./.env; set +a

rand_hex() { openssl rand -hex 32; }

replace_if_placeholder() {
  local key="$1"
  local current
  current="$(grep -E "^${key}=" .env | head -1 | cut -d= -f2- || true)"
  if [ -z "${current}" ] || [ "${current}" = "CHANGE_ME" ]; then
    local newval
    newval="$(rand_hex)"
    # 用 awk 原地替换，避免 sed 对特殊字符的转义问题
    awk -v k="${key}" -v v="${newval}" 'BEGIN{FS=OFS="="} $1==k{$2=v} {print}' .env > .env.tmp
    mv .env.tmp .env
    echo "已生成 ${key}"
  fi
}

for key in POSTGRES_PASSWORD CLICKHOUSE_PASSWORD REDIS_AUTH MINIO_ROOT_PASSWORD \
           NEXTAUTH_SECRET SALT ENCRYPTION_KEY GRAFANA_PASSWORD; do
  replace_if_placeholder "${key}"
done

# shellcheck disable=SC1091
set -a; . ./.env; set +a

if [ -z "${LANGFUSE_PUBLIC_KEY:-}" ] || [ "${LANGFUSE_PUBLIC_KEY}" = "pk-lf-CHANGE_ME" ]; then
  echo "!! 请先在 LangFuse UI（首次启动后访问 http://<host>:3000）创建项目并获取 API Key，"
  echo "   填入 .env 的 LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY 后重新执行本脚本。"
  exit 1
fi

# 生成 OTel Collector 使用的 Basic Auth 头
AUTH_HEADER="$(printf '%s:%s' "${LANGFUSE_PUBLIC_KEY}" "${LANGFUSE_SECRET_KEY}" | base64 -w0)"
awk -v v="${AUTH_HEADER}" 'BEGIN{FS=OFS="="} $1=="LANGFUSE_AUTH_HEADER"{$2=v} {print}' .env > .env.tmp
mv .env.tmp .env
echo "已生成 LANGFUSE_AUTH_HEADER"

# 生成 Alertmanager 实际配置（Alertmanager 不支持环境变量插值）
if command -v envsubst >/dev/null 2>&1; then
  set -a; . ./.env; set +a
  envsubst < alertmanager.yml.tpl > alertmanager.yml
  echo "已由 alertmanager.yml.tpl 生成 alertmanager.yml"
else
  echo "!! 未找到 envsubst（gettext 包），请安装后手动执行："
  echo "   envsubst < alertmanager.yml.tpl > alertmanager.yml"
fi

chmod 600 .env
echo "完成。请执行："
echo "  sysctl -w vm.max_map_count=262144"
echo "  docker compose -f docker-compose-observability.yml --env-file .env up -d"
''')

# ============================================================================
# 8. 运维说明
# ============================================================================
add("README.md", r'''
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
| 8 | 空召回不调用大模型 | 提问知识库里没有的内容 | `rag_chat_answer_total{outcome="NO_HIT"}` +1，且模型指标无增长 |
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
''')

if __name__ == "__main__":
    for rel, content in FILES.items():
        target = BASE / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print("W +", rel)
    print("---- total:", len(FILES))
