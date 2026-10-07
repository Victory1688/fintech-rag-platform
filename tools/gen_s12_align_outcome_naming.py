# -*- coding: utf-8 -*-
"""
S12 —— 统一「无据不答」的取值词汇（文档 / 代码 / 看板 / Collector 四方对齐）。

问题：
    同一个业务事件存在两套命名，落地后必然对不上：
      · 契约与数据库：AnswerType.NO_HIT  → t_message.answer_type='NO_HIT'
      · 可观测侧    ：RagOutcome.ABSTAINED → rag_chat_answer_total{outcome="ABSTAINED"}
    后果：运维在看板上看到 30% 的 ABSTAINED，去库里按 answer_type='NO_HIT' 查却
    要额外做一次「人名对照」，跨系统核对成本高、易错。

决策：**统一为 NO_HIT**（与对外契约、DDL、GuardrailType.NO_HIT 一致）。
    同时把取值大小写统一为**枚举名原样（大写）**——因为指标取值来自
    `RagOutcome.name()`，Grafana 查询与 Collector tail_sampling 也按大写匹配，
    文档里若写小写就会「照着文档查不到数据」。

本脚本为幂等补丁：重复执行不会产生变化。
"""
import pathlib
import re

ROOT = pathlib.Path(r"D:/AiWorkOut/java-ai")

TARGETS = [
    # 生成脚本中的源码模板（必须一起改，否则重新生成会把旧名字带回来）
    "tools/gen_s7_observability.py",
    "tools/gen_s8_observability_chat.py",
    "tools/gen_s9_observability_retrieval.py",
    "tools/gen_s10_observability_deploy.py",
    # 已生成的源码
    "rag-platform/rag-common/src/main/java/com/fintech/rag/common/observability/RagOutcome.java",
    "rag-platform/rag-chat-service/src/main/java/com/fintech/rag/chat/app/metric/ChatPipelineMetrics.java",
    "rag-platform/rag-chat-service/src/main/java/com/fintech/rag/chat/app/service/ChatOrchestrationAppService.java",
    "rag-platform/rag-retrieval-service/src/main/java/com/fintech/rag/retrieval/app/metric/RetrievalMetrics.java",
    "rag-platform/rag-retrieval-service/src/main/java/com/fintech/rag/retrieval/app/service/RetrievalAppService.java",
    # 部署编排
    "deploy/observability/grafana-dashboard-observability.json",
    "deploy/observability/otel-collector-config.yaml",
    "deploy/observability/README.md",
    # 文档
    "docs/05-AI可观测与运维监控方案.md",
]

changed = []
for rel in TARGETS:
    p = ROOT / rel
    if not p.is_file():
        print(f"[warn] 文件不存在，跳过：{rel}")
        continue
    text = p.read_text(encoding="utf-8")
    original = text

    # 1) tail_sampling 策略名先更名（避免被后面的全局替换拆成 NO_HIT-always）
    text = text.replace("abstained-always", "no-hit-always")
    # 2) 枚举名 / 标签值：ABSTAINED -> NO_HIT
    text = text.replace("ABSTAINED", "NO_HIT")
    # 3) 文档里的小写写法
    text = text.replace("abstained", "NO_HIT")

    if text != original:
        p.write_text(text, encoding="utf-8", newline="\n")
        changed.append(rel)
        print(f"[ok] {rel}")

print("\n---- 变更文件数: %d ----" % len(changed))

# 残留检查：整个仓库不应再出现旧词汇（本脚本自身因含说明文字需排除）
SELF = pathlib.Path(__file__).resolve()
leftover = []
for p in ROOT.rglob("*"):
    if not p.is_file() or ".git" in p.parts:
        continue
    if p.resolve() == SELF:
        continue
    if p.suffix.lower() in {".jar", ".png", ".jpg", ".pdf", ".class"}:
        continue
    try:
        text = p.read_text(encoding="utf-8")
    except Exception:
        continue
    if re.search(r"ABSTAINED|abstained", text):
        leftover.append(p.relative_to(ROOT).as_posix())

print("\n---- 残留旧词汇（应为空）----")
for x in leftover:
    print("  !", x)
if not leftover:
    print("  (无)")
