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
