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
