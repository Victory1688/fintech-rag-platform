# -*- coding: utf-8 -*-
"""
S11 —— 修复「跨服务链路断点」（可观测落地补丁）。

背景（本次评审新发现的硬伤，必须修）：
    Spring Cloud OpenFeign 在 Boot 3（Micrometer Tracing）下**不会自动透传 traceparent**，
    除非 classpath 上存在 io.github.openfeign:feign-micrometer
    （其 FeignClientsConfiguration.MicrometerConfiguration 才会注册
     MicrometerObservationCapability + PropagatingSenderTracingObservationHandler）。
    缺这个依赖时，网关 → 服务 A 的链路是通的，但服务 A → 服务 B 的 Feign 调用会
    **另起一条新链路**：现象是「traceId 在第一个 Feign 跳变了一下就断了」，极难排查。

本脚本做四件事：
  1) 根 pom 的 dependencyManagement 纳管 feign-micrometer；
  2) 所有声明了 openfeign 的模块显式引入 feign-micrometer；
  3) 重写 TracePropagationInterceptor：保留 X-Trace-Id 透传，并新增启动期「防呆体检」
     （缺 feign-micrometer 时直接 ERROR + 可执行修复提示，避免静默断链）；
  4) 6 个服务统一显式声明 management.tracing.propagation.type = w3c。

另修正 TraceIds 第二个 formatTraceparent 重载的误导性注释（原写「spanId 用占位」，
实际实现是「生成一个合规随机 spanId」，语义完全不同 —— 注释写错会让人误以为可以传全零）。

幂等：重复执行不会重复插入。
"""
import pathlib
import re

BASE = pathlib.Path(r"D:/AiWorkOut/java-ai/rag-platform")
written = []

# ---------------------------------------------------------------- 工具
FEIGN_MICROMETER_MANAGED = """
            <!--
              Feign 观测能力（跨服务 traceparent 透传的关键依赖）。

              为什么必须显式声明：Spring Cloud OpenFeign 只有在 classpath 上存在
              io.github.openfeign:feign-micrometer 时，才会装配
              MicrometerObservationCapability 与 PropagatingSenderTracingObservationHandler；
              缺失时 Feign 调用**不带 traceparent**，下游会另起一条新链路
              （详见 docs/05 §1.2 第 10 条 / §5.5）。

              版本由 spring-cloud-dependencies 引入的 feign-bom 统一纳管，故此处不写 version。
              若构建报「缺少 version」，请在 properties 中补
              <feign.version>x.y.z</feign.version> 并在此显式声明。
            -->
            <dependency>
                <groupId>io.github.openfeign</groupId>
                <artifactId>feign-micrometer</artifactId>
            </dependency>"""

FEIGN_MICROMETER_MODULE = """
        <!--
          Feign 观测：没有它，本服务发起的 Feign 调用不会携带 traceparent，
          跨服务链路会在此断开（详见 docs/05 §5.5「跨服务透传」）。
        -->
        <dependency>
            <groupId>io.github.openfeign</groupId>
            <artifactId>feign-micrometer</artifactId>
        </dependency>"""

TRACING_BLOCK = """
  tracing:
    propagation:
      # 显式锁定 W3C（traceparent + tracestate）。
      # 一旦被改成 b3，OTel Collector 与 LangFuse 都无法解析 traceparent，
      # 「APM 链路」与「AI 观测」的 traceId 会整条对不上（详见 docs/05 §1.2 第 1 条）。
      type: w3c
    sampling:
      probability: ${RAG_OBS_SAMPLING:0.1}
  otlp:
    tracing:
      # 应用只认 OTel Collector，不认 LangFuse（LangFuse 密钥只配在 Collector）
      endpoint: ${OTEL_EXPORTER_OTLP_TRACES_ENDPOINT:http://127.0.0.1:4318/v1/traces}
      timeout: 3s"""

PROPAGATION_SNIPPET = """    propagation:
      # 显式锁定 W3C（traceparent + tracestate），禁止退回 b3 / 自定义头
      type: w3c
"""


def write(path: pathlib.Path, text: str):
    path.write_text(text, encoding="utf-8", newline="\n")
    written.append(path.relative_to(BASE).as_posix() if path.is_relative_to(BASE) else str(path))


# ================================================================ 1) 根 pom
def patch_root_pom():
    pom = BASE / "pom.xml"
    text = pom.read_text(encoding="utf-8")
    if "feign-micrometer" in text:
        print("[skip] 根 pom 已纳管 feign-micrometer")
        return
    anchor = "\n        </dependencies>\n    </dependencyManagement>"
    if anchor not in text:
        raise SystemExit("根 pom 未找到 dependencyManagement 结束锚点，请人工检查")
    text = text.replace(anchor, FEIGN_MICROMETER_MANAGED + anchor, 1)
    write(pom, text)
    print("[ok] 根 pom dependencyManagement += feign-micrometer")


# ================================================================ 2) 模块 pom
def patch_module_poms():
    targets = ["rag-api", "rag-chat-service", "rag-ingest-service",
               "rag-knowledge-service", "rag-retrieval-service"]
    for name in targets:
        pom = BASE / name / "pom.xml"
        text = pom.read_text(encoding="utf-8")
        if "feign-micrometer" in text:
            print(f"[skip] {name}/pom.xml 已引入 feign-micrometer")
            continue
        if "openfeign" not in text:
            print(f"[skip] {name}/pom.xml 未使用 openfeign（无需引入）")
            continue
        idx = text.rfind("\n    </dependencies>")
        if idx < 0:
            raise SystemExit(f"{name}/pom.xml 未找到 </dependencies> 锚点")
        text = text[:idx] + FEIGN_MICROMETER_MODULE + text[idx:]
        write(pom, text)
        print(f"[ok] {name}/pom.xml += feign-micrometer")


# ================================================================ 3) Feign 拦截器
INTERCEPTOR = '''package com.fintech.rag.api.client.interceptor;

import com.fintech.rag.common.constant.RagHeaders;
import com.fintech.rag.common.context.RequestContext;
import com.fintech.rag.common.util.TraceIds;
import feign.RequestInterceptor;
import feign.RequestTemplate;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.util.ClassUtils;

/**
 * Feign 追踪透传拦截器。
 *
 * <p><strong>职责边界（务必看清，否则会漏掉真正的透传依赖）：</strong></p>
 * <ul>
 *   <li>本类只负责透传<b>业务自定义头</b> {@code X-Trace-Id}（给日志、审计、人工排障用）；</li>
 *   <li>标准 W3C {@code traceparent} 由 <b>Feign 观测能力</b>注入，不是本类做的 ——
 *       即 classpath 上的 {@code io.github.openfeign:feign-micrometer}。
 *       该依赖会装配 {@code MicrometerObservationCapability}，由
 *       {@code PropagatingSenderTracingObservationHandler} 把当前 span 写成
 *       {@code traceparent} 头。</li>
 * </ul>
 *
 * <p><b>为什么启动时要体检一次</b>：缺 {@code feign-micrometer} 时 Feign 调用不会带
 * {@code traceparent}，下游会另起一条新链路。它的表现非常隐蔽 —— 网关到第一个服务的
 * 链路是好的，只有后续 Feign 跳转断掉，看日志「每条都有 traceId」却「串不成一条链」。
 * 与其等人肉排查，不如启动即报错。</p>
 *
 * <p><strong>绝不在此处添加 {@code X-Request-Source}。</strong>
 * 来源标识只能由 DMZ 网关注入；内网 Feign 客户端一旦全局带上它，
 * AI 服务侧的反向拦截会直接把内网调用判为伪造并返回 403。</p>
 *
 * @author rag-platform
 */
public class TracePropagationInterceptor implements RequestInterceptor {

    private static final Logger log = LoggerFactory.getLogger(TracePropagationInterceptor.class);

    /**
     * Feign 观测能力类名 —— 只做「存在性判断」，不引用其类型，
     * 因此本类在缺少该依赖时仍可正常加载。
     */
    private static final String FEIGN_OBSERVATION_CAPABILITY = "feign.micrometer.MicrometerObservationCapability";

    public TracePropagationInterceptor() {
        checkPropagationReady();
    }

    @Override
    public void apply(RequestTemplate template) {
        String traceId = RequestContext.currentTraceId();
        template.header(RagHeaders.TRACE_ID, TraceIds.resolve(traceId));
        // 注意：此处刻意不手动写 traceparent —— 手写会与 Feign 观测能力注入的头并存，
        // 变成两个 traceparent（取值还不一致），下游取哪个取决于实现细节，属于不可控行为。
    }

    /**
     * 启动期体检：Feign 在 classpath 上，但观测能力缺失时直接报错。
     *
     * <p>这里用 ERROR 而不是 WARN：这不是「可选优化项」，而是会让整条链路静默断裂的
     * 配置缺陷，必须让人第一眼看到。</p>
     */
    private void checkPropagationReady() {
        try {
            boolean hasFeign = ClassUtils.isPresent("feign.Request", getClass().getClassLoader());
            boolean hasObservation = ClassUtils.isPresent(FEIGN_OBSERVATION_CAPABILITY, getClass().getClassLoader());
            if (hasFeign && !hasObservation) {
                log.error("""
                        检测到 Feign 但缺少链路透传能力：跨服务调用不会携带 traceparent，\
                        下游将另起一条新链路（链路会在第一个 Feign 跳转处断裂）。
                        修复方式：在模块 pom.xml 中引入
                            <dependency>
                                <groupId>io.github.openfeign</groupId>
                                <artifactId>feign-micrometer</artifactId>
                            </dependency>
                        并确保 io.micrometer:micrometer-tracing-bridge-otel 在 classpath 上。\
                        详见 docs/05 §5.5。""");
            }
        } catch (Throwable ignored) {
            // 体检本身永不影响启动
        }
    }
}
'''


def rewrite_interceptor():
    path = BASE / "rag-api/src/main/java/com/fintech/rag/api/client/interceptor/TracePropagationInterceptor.java"
    if "FEIGN_OBSERVATION_CAPABILITY" in path.read_text(encoding="utf-8"):
        print("[skip] TracePropagationInterceptor 已含体检逻辑")
        return
    write(path, INTERCEPTOR)
    print("[ok] 重写 TracePropagationInterceptor（+ feign-micrometer 启动体检）")


# ================================================================ 4) TraceIds 注释勘误
def fix_traceids_javadoc():
    path = BASE / "rag-common/src/main/java/com/fintech/rag/common/util/TraceIds.java"
    text = path.read_text(encoding="utf-8")
    old = """     * 只带 traceId 的 traceparent（spanId 用占位）。"""
    new = """     * 只带 traceId 的 traceparent（spanId 由本方法生成一个合规随机值）。"""
    if old not in text:
        print("[skip] TraceIds 注释已是修正版")
        return
    text = text.replace(old, new, 1)
    old2 = """     * <p>用途：网关生成 traceparent 透传给下游时，网关自己的 spanId 对下游无意义，
     * 下游的 OTel SDK 会以「父上下文」方式提取 traceId 并生成自己的 spanId。</p>"""
    new2 = """     * <p>用途：网关生成 traceparent 透传给下游时，网关自己的 spanId 对下游无意义，
     * 下游的 OTel SDK 会以「父上下文」方式提取 traceId 并生成自己的 spanId。</p>
     *
     * <p><b>不要传全零 spanId</b>：W3C 规范明确「span-id 全零」的 traceparent 属于非法值，
     * OTel / Collector / LangFuse 会直接丢弃并另起新链路 —— 这正是「网关发了头下游却不认」的根因。
     * 本方法内部会把它替换为一个合规随机 spanId。</p>"""
    if old2 in text:
        text = text.replace(old2, new2, 1)
    write(path, text)
    print("[ok] TraceIds javadoc 勘误（全零 spanId 的坑）")


# ================================================================ 5) YAML：锁定 W3C
def patch_yaml():
    targets = ["rag-gateway", "rag-platform-service", "rag-knowledge-service",
               "rag-ingest-service", "rag-retrieval-service", "rag-chat-service"]
    for name in targets:
        path = BASE / name / "src/main/resources/application.yml"
        text = path.read_text(encoding="utf-8")
        rel = f"{name}/src/main/resources/application.yml"

        if "propagation:" in text:
            print(f"[skip] {rel} 已声明 propagation")
            continue

        if "\n  otlp:" in text:
            # 已有 tracing/otlp 段：只补 propagation（插在 sampling 之前）
            if "\n    sampling:" not in text:
                print(f"[warn] {rel} 有 otlp 但无 sampling，需人工确认")
                continue
            text = text.replace("\n    sampling:", "\n" + PROPAGATION_SNIPPET.rstrip("\n") + "\n    sampling:", 1)
        else:
            # 没有 tracing/otlp 段：整块补到 management 段落末尾
            lines = text.split("\n")
            start = None
            for i, line in enumerate(lines):
                if line.rstrip() == "management:":
                    start = i
                    break
            if start is None:
                print(f"[warn] {rel} 未找到 management: 段落，跳过")
                continue
            end = len(lines)
            for j in range(start + 1, len(lines)):
                l = lines[j]
                if l.strip() == "" or l.startswith(" ") or l.startswith("#"):
                    continue
                end = j
                break
            block = TRACING_BLOCK.rstrip("\n").split("\n")
            lines = lines[:end] + [""] + block + lines[end:]
            text = "\n".join(lines)

        write(path, text)
        print(f"[ok] {rel} += W3C 传播声明")


if __name__ == "__main__":
    patch_root_pom()
    patch_module_poms()
    rewrite_interceptor()
    fix_traceids_javadoc()
    patch_yaml()
    print("\n---- total: %d ----" % len(written))
    for w in written:
        print("  W", w)
