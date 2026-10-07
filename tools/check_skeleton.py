# -*- coding: utf-8 -*-
"""
骨架结构自检（含可观测埋点一致性校验）。

A. 通用结构
   1) package 声明与目录是否一致
   2) 公开类型名与文件名是否一致
   3) 大括号/圆括号是否配平
   4) POM / application.yml 基本可解析

B. 可观测专项（把「落地时会静默失败」的坑固化成校验项）
   5) 可观测关键文件与部署编排是否存在
   6) AutoConfiguration.imports 是否登记了可观测自动配置
   7) 是否误用了已废弃的 OTel GenAI 语义约定属性
   8) 网关追踪头洗白过滤器 order 是否正确（必须早于 Boot 观测过滤器）
   9) Feign 模块是否引入 feign-micrometer（否则跨服务 traceparent 静默断裂）
  10) 是否显式锁定 W3C 传播（否则 Collector / LangFuse 解析不了 traceparent）
  11) 指标标签纪律（禁止无界标签：traceId / userId / conversationId …）
  12) LangFuse 密钥是否泄漏到业务代码（只允许出现在 deploy/）
  13) 内容采集档位防呆（FULL_CONTENT 必须伴随 allow-plain-text-content=false）
"""
import json
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

BASE = pathlib.Path(r"D:/AiWorkOut/java-ai/rag-platform")
DEPLOY = pathlib.Path(r"D:/AiWorkOut/java-ai/deploy/observability")

errors = []
java_count = 0
pom_count = 0
yml_count = 0


# ------------------------------------------------------------------ 文本工具
def strip_literals(src: str) -> str:
    """去掉字符串字面量与注释，避免大括号/引号被误判"""
    out = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c == '"' and src.startswith('"""', i):
            j = src.find('"""', i + 3)
            i = n if j < 0 else j + 3
            continue
        if c == '"':
            i += 1
            while i < n and src[i] != '"':
                if src[i] == '\\':
                    i += 1
                i += 1
            i += 1
            continue
        if c == "'":
            i += 1
            while i < n and src[i] != "'":
                if src[i] == '\\':
                    i += 1
                i += 1
            i += 1
            continue
        if c == '/' and i + 1 < n and src[i + 1] == '/':
            j = src.find('\n', i)
            i = n if j < 0 else j
            continue
        if c == '/' and i + 1 < n and src[i + 1] == '*':
            j = src.find('*/', i + 2)
            i = n if j < 0 else j + 2
            continue
        out.append(c)
        i += 1
    return ''.join(out)


def strip_comments(src: str) -> str:
    """只去注释、保留字符串字面量。

    用途：校验「废弃属性是否被真正使用」——Javadoc 里为说明「不要用 gen_ai.system」
    必然会出现该字符串，若不去注释就会误报。
    """
    out = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c == '"':
            out.append(c)
            i += 1
            while i < n and src[i] != '"':
                if src[i] == '\\':
                    out.append(src[i])
                    i += 1
                if i < n:
                    out.append(src[i])
                    i += 1
            if i < n:
                out.append('"')
                i += 1
            continue
        if c == "'":
            out.append(c)
            i += 1
            while i < n and src[i] != "'":
                if src[i] == '\\':
                    out.append(src[i])
                    i += 1
                if i < n:
                    out.append(src[i])
                    i += 1
            if i < n:
                out.append("'")
                i += 1
            continue
        if c == '/' and i + 1 < n and src[i + 1] == '/':
            j = src.find('\n', i)
            i = n if j < 0 else j
            continue
        if c == '/' and i + 1 < n and src[i + 1] == '*':
            j = src.find('*/', i + 2)
            i = n if j < 0 else j + 2
            continue
        out.append(c)
        i += 1
    return ''.join(out)


def call_args(src: str, start: int) -> str:
    """从 start（'(' 位置）起返回配对括号内的参数文本"""
    depth = 0
    for i in range(start, len(src)):
        if src[i] == '(':
            depth += 1
        elif src[i] == ')':
            depth -= 1
            if depth == 0:
                return src[start + 1:i]
    return src[start:]


JAVA_FILES = sorted(BASE.rglob("*.java"))
POM_FILES = sorted(BASE.rglob("pom.xml"))
YML_FILES = sorted(BASE.rglob("application.yml"))


# ================================================================ A. 通用结构
for path in JAVA_FILES:
    java_count += 1
    rel = path.relative_to(BASE).as_posix()
    src = path.read_text(encoding="utf-8")

    m = re.search(r'^\s*package\s+([\w.]+)\s*;', src, re.M)
    if not m:
        errors.append(f"[无 package] {rel}")
    else:
        pkg = m.group(1)
        marker = "/src/main/java/"
        expected = rel.split(marker, 1)[1].rsplit("/", 1)[0].replace("/", ".")
        if pkg != expected:
            errors.append(f"[package 不匹配] {rel}\n    声明={pkg}\n    期望={expected}")

    m = re.search(r'^\s*public\s+(?:final\s+|abstract\s+)?(?:class|interface|enum|record)\s+(\w+)', src, re.M)
    if m and m.group(1) != path.stem:
        errors.append(f"[类型名不匹配] {rel}  类型={m.group(1)}")

    clean = strip_literals(src)
    for op, cl, label in (("{", "}", "大括号"), ("(", ")", "圆括号")):
        if clean.count(op) != clean.count(cl):
            errors.append(f"[{label}不配平] {rel}  {op}={clean.count(op)} {cl}={clean.count(cl)}")

for path in POM_FILES:
    pom_count += 1
    try:
        ET.parse(path)
    except Exception as ex:
        errors.append(f"[POM 解析失败] {path.relative_to(BASE).as_posix()} -> {ex}")

for path in YML_FILES:
    yml_count += 1
    text = path.read_text(encoding="utf-8")
    rel = path.relative_to(BASE).as_posix()
    if "\t" in text:
        errors.append(f"[YAML 含 TAB] {rel}")
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.rstrip()
        if stripped != line:
            errors.append(f"[YAML 行尾空格] {rel}:{i}")
        if ':' in line and not line.strip().startswith("#") and not line.strip().startswith("-"):
            key = line.split(":", 1)[0]
            if '"' in key or "'" in key:
                errors.append(f"[YAML key 带引号] {rel}:{i}")


# ================================================================ B. 可观测专项
OBS_FILES_REQUIRED = [
    "rag-common/src/main/java/com/fintech/rag/common/observability/GenAiSemconv.java",
    "rag-common/src/main/java/com/fintech/rag/common/observability/ContentLevel.java",
    "rag-common/src/main/java/com/fintech/rag/common/observability/ContentSanitizer.java",
    "rag-common/src/main/java/com/fintech/rag/common/observability/ObservabilityProperties.java",
    "rag-common/src/main/java/com/fintech/rag/common/observability/RagOutcome.java",
    "rag-common/src/main/java/com/fintech/rag/common/observability/TraceIdProvider.java",
    "rag-common/src/main/java/com/fintech/rag/common/observability/MicrometerTraceIdProvider.java",
    "rag-common/src/main/java/com/fintech/rag/common/util/TraceIds.java",
    "rag-common/src/main/java/com/fintech/rag/common/config/RagCommonObservabilityAutoConfiguration.java",
    "rag-gateway/src/main/java/com/fintech/rag/gateway/filter/InboundTraceSanitizeWebFilter.java",
    "rag-gateway/src/main/java/com/fintech/rag/gateway/filter/GatewayTraceSupport.java",
    "rag-chat-service/src/main/java/com/fintech/rag/chat/infra/llm/LlmTraceListener.java",
    "rag-chat-service/src/main/java/com/fintech/rag/chat/app/metric/ChatPipelineMetrics.java",
    "rag-chat-service/src/main/java/com/fintech/rag/chat/app/metric/StreamTimingRecorder.java",
    "rag-retrieval-service/src/main/java/com/fintech/rag/retrieval/app/metric/RetrievalMetrics.java",
]
for rel in OBS_FILES_REQUIRED:
    if not (BASE / rel).is_file():
        errors.append(f"[可观测文件缺失] {rel}")

DEPLOY_FILES_REQUIRED = [
    "docker-compose-observability.yml",
    "otel-collector-config.yaml",
    "prometheus.yml",
    "alert-rules.yml",
    "alertmanager.yml.tpl",
    "grafana-dashboard-observability.json",
    "grafana-provisioning/datasources/prometheus.yml",
    "grafana-provisioning/dashboards/provider.yml",
    "env.example",
    "init-secrets.sh",
    "README.md",
]
for name in DEPLOY_FILES_REQUIRED:
    if not (DEPLOY / name).is_file():
        errors.append(f"[部署编排缺失] deploy/observability/{name}")

# ---- 6) AutoConfiguration.imports 登记
IMPORTS_EXPECT = {
    "rag-common": "com.fintech.rag.common.config.RagCommonObservabilityAutoConfiguration",
    "rag-api": "com.fintech.rag.api.config.RagApiAutoConfiguration",
}
for module, expect in IMPORTS_EXPECT.items():
    f = BASE / module / "src/main/resources/META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports"
    if not f.is_file():
        errors.append(f"[imports 缺失] {module} 缺少 AutoConfiguration.imports")
        continue
    if expect not in f.read_text(encoding="utf-8"):
        errors.append(f"[imports 未登记] {module} 缺少 {expect}")

# ---- 7) 废弃的 GenAI 语义约定属性（去注释后仍出现 = 真的在用）
DEPRECATED_ATTRS = ["gen_ai.system", "gen_ai.content.prompt", "gen_ai.content.completion"]
for path in JAVA_FILES:
    code = strip_comments(path.read_text(encoding="utf-8"))
    for attr in DEPRECATED_ATTRS:
        # 必须精确到属性边界：gen_ai.system_instructions 是有效属性，不能被 gen_ai.system 误伤
        if re.search(re.escape(attr) + r'(?![\w.])', code):
            errors.append(
                f"[废弃语义约定] {path.relative_to(BASE).as_posix()} 使用了已废弃属性 {attr}"
                f"（应为 gen_ai.provider.name / gen_ai.input.messages / gen_ai.output.messages）")

# ---- 8) 网关洗白过滤器 order
sanitize = BASE / "rag-gateway/src/main/java/com/fintech/rag/gateway/filter/InboundTraceSanitizeWebFilter.java"
if sanitize.is_file():
    code = strip_comments(sanitize.read_text(encoding="utf-8"))
    m = re.search(r'int\s+getOrder\(\)\s*\{(.*?)\}', code, re.S)
    if not m:
        errors.append("[网关洗白] InboundTraceSanitizeWebFilter 未见 getOrder()")
    elif "HIGHEST_PRECEDENCE +" in m.group(1).replace(" ", " "):
        errors.append("[网关洗白] getOrder() 返回 HIGHEST_PRECEDENCE 的偏移值；"
                      "必须恰好为 HIGHEST_PRECEDENCE，否则晚于 Boot 观测过滤器，伪造 traceparent 已被采纳")

# ---- 9) Feign 模块必须引入 feign-micrometer
for path in POM_FILES:
    text = path.read_text(encoding="utf-8")
    if "openfeign" in text and "feign-micrometer" not in text:
        errors.append(f"[Feign 透传缺失] {path.relative_to(BASE).as_posix()} 使用 OpenFeign 但未引入 "
                      f"io.github.openfeign:feign-micrometer —— Feign 调用不会带 traceparent，跨服务链路静默断裂")

# ---- 10) 显式锁定 W3C 传播
for path in YML_FILES:
    text = path.read_text(encoding="utf-8")
    if "tracing:" in text:
        if "propagation:" not in text or "type: w3c" not in text:
            errors.append(f"[传播格式未锁定] {path.relative_to(BASE).as_posix()} 含 tracing 但未显式声明 "
                          f"management.tracing.propagation.type: w3c")

# ---- 11) 指标标签纪律
FORBIDDEN_TAGS = ["traceId", "userId", "conversationId", "subjectId", "clientIp", "question", "query"]
for path in JAVA_FILES:
    src = path.read_text(encoding="utf-8")
    rel = path.relative_to(BASE).as_posix()
    for m in re.finditer(r'meterRegistry\s*\.\s*\w+\s*\(', src):
        args = call_args(src, src.index('(', m.start()))
        for bad in FORBIDDEN_TAGS:
            if re.search(r'"%s"' % re.escape(bad), args):
                errors.append(f"[指标标签越界] {rel} 把 {bad} 当成了指标标签"
                              f"（无界维度会导致 Prometheus 内存爆炸）")

# ---- 12) LangFuse 密钥不得出现在业务代码
SECRET_TOKENS = ["LANGFUSE_SECRET_KEY", "LANGFUSE_PUBLIC_KEY", "x-langfuse-ingestion-version",
                 "langfuse-secret", "X-Langfuse-Ingestion-Version"]
for path in JAVA_FILES + YML_FILES:
    text = path.read_text(encoding="utf-8")
    for token in SECRET_TOKENS:
        if token in text:
            errors.append(f"[密钥越界] {path.relative_to(BASE).as_posix()} 出现 {token}；"
                          f"LangFuse 凭据只允许配置在 deploy/observability/otel-collector-config.yaml")

# ---- 13) 内容采集档位防呆
for path in YML_FILES:
    text = path.read_text(encoding="utf-8")
    rel = path.relative_to(BASE).as_posix()
    if re.search(r'content-level\s*:\s*\S*FULL_CONTENT', text) \
            and not re.search(r'allow-plain-text-content\s*:\s*false', text):
        errors.append(f"[采集档位防呆] {rel} 开启了 FULL_CONTENT 但未显式关闭 allow-plain-text-content")

# ---- 附加：部署编排里的 JSON 必须可解析
dash = DEPLOY / "grafana-dashboard-observability.json"
if dash.is_file():
    try:
        json.loads(dash.read_text(encoding="utf-8"))
    except Exception as ex:
        errors.append(f"[Grafana 看板 JSON 非法] {ex}")


# ================================================================ 输出
print(f"Java 文件: {java_count}  POM: {pom_count}  application.yml: {yml_count}")
print(f"可观测专项：必需源码 {len(OBS_FILES_REQUIRED)} 项 / 部署编排 {len(DEPLOY_FILES_REQUIRED)} 项")
if errors:
    print("\n===== 发现问题 =====")
    for e in errors:
        print(" -", e)
    sys.exit(1)
print("结构自检通过：package / 类型名 / 括号配平 / POM / YAML / 可观测埋点一致性 均无异常")
