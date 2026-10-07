# -*- coding: utf-8 -*-
"""
S13 · 评估与回放的契约层 + chat 库落库实体。

背景：docs/03 §6.3~§6.6 定义了 t_message_citation / t_token_usage / t_feedback /
t_llm_eval_score 四张表，但骨架里**没有任何 Java 对应物** —— 即「表建了、没人写」。
同时 retrieval 的检索日志 trace_id 取的是请求体值（客户端可控），
导致「按 traceId 回放」在最关键的一跳上不可信。

本脚本产出：
  A. rag-api 契约层
     1) domain/common/EvalSource.java      评估来源枚举（ONLINE/BATCH/MANUAL）
     2) domain/common/EvalMetric.java      评估指标白名单（含默认门禁阈值）
     3) dto/chat/FeedbackRequest.java      答案反馈请求
     4) dto/eval/ManualEvalRequest.java    人工评分请求
     5) dto/replay/RetrievalTraceView.java 检索段视图（**不含片段原文**）
     6) client/RetrievalClient.java（改）  新增「按 traceId 查检索日志」
  B. chat-service 落库实体
     7)  domain/model/MessageCitation.java
     8)  domain/model/TokenUsageRecord.java   （注意：不能叫 TokenUsage，与 LangChain4j 撞名）
     9)  domain/model/AnswerFeedback.java
     10) domain/model/LlmEvalScore.java
     11) infra/persistence/mapper/{MessageCitation,TokenUsage,Feedback,LlmEvalScore}Mapper.java

幂等：全部为覆盖写，可重复执行。
"""
import pathlib

ROOT = pathlib.Path(r"D:/AiWorkOut/java-ai")
API = ROOT / "rag-platform/rag-api/src/main/java/com/fintech/rag/api"
CHAT = ROOT / "rag-platform/rag-chat-service/src/main/java/com/fintech/rag/chat"

written = []


def w(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n" 必须显式指定：Windows 下默认会写成 CRLF，污染与 Linux/Docker 的 diff
    path.write_text(content, encoding="utf-8", newline="\n")
    written.append(path)
    print("W +", path.relative_to(ROOT).as_posix())


# ============================================================ A1 EvalSource
w(API / "dto/common/EvalSource.java", r'''package com.fintech.rag.api.dto.common;

/**
 * 评估来源 —— 回答质量分数的「出处」。
 *
 * <p><b>为什么必须区分来源</b>：三种来源的可信度与用途完全不同，混在一起统计会得出错误结论。</p>
 *
 * <table border="1">
 *   <caption>来源对比</caption>
 *   <tr><th>来源</th><th>触发方</th><th>典型指标</th><th>用途</th><th>可信度</th></tr>
 *   <tr><td>ONLINE</td><td>系统按采样率自动</td><td>CITATION_COVERAGE、CONTEXT_PRECISION</td>
 *       <td>线上质量趋势监控</td><td>中（可算指标确定，代理指标近似）</td></tr>
 *   <tr><td>BATCH</td><td>离线评测任务</td><td>全量指标</td>
 *       <td><b>发版门禁</b></td><td>高（固定评测集 + 固定裁判）</td></tr>
 *   <tr><td>MANUAL</td><td>运营 / 业务专家</td><td>HELPFULNESS</td>
 *       <td>争议样本定调、标注黄金集</td><td>最高</td></tr>
 * </table>
 *
 * <p><b>门禁只能用 BATCH</b>：样本量可控、评测集固定、结果可复现。
 * 用 ONLINE 分数做发版门禁会被采样偏差与流量结构变化带偏。</p>
 *
 * @author rag-platform
 */
public enum EvalSource {

    /** 在线抽样：回答完成后异步评分，不阻塞用户 */
    ONLINE,

    /** 离线批量：评测任务跑固定评测集，是发版门禁的唯一合法来源 */
    BATCH,

    /** 人工评估：运营在后台对具体回答打分 */
    MANUAL
}
''')

# ============================================================ A2 EvalMetric
w(API / "dto/common/EvalMetric.java", r'''package com.fintech.rag.api.dto.common;

import java.math.BigDecimal;

/**
 * 评估指标白名单 —— {@code t_llm_eval_score.metric_code} 的合法取值。
 *
 * <p><b>为什么必须是白名单而不是自由字符串</b>：指标码是看板的分组维度，
 * 一旦允许业务方随手写（{@code FAITHFULNESS} / {@code faithfulness} / {@code 忠实度} 三种写法并存），
 * 同一个指标会被拆成三条曲线，且历史数据无法重算。校验放在写入入口，
 * 让错误在写入时就失败，而不是在出质量报告时才发现对不上。</p>
 *
 * <p><b>量纲（scoreScale）</b>：统一为 1，即所有分数都归一到 0~1，阈值也用 0~1 表达。
 * 曾经考虑过 1~5 分制，但五级分值在跨指标聚合时无法直接比较，且容易被误当成百分制。</p>
 *
 * <p><b>canComputeWithoutJudge</b>：标记该指标是否「无需大模型即可计算」。
 * 骨架阶段只启用可算指标，需要裁判模型的指标必须等 LLM-as-judge 接入后再开启 ——
 * 这样评估链路当天就能跑起来，不必等模型接入，也不会用假分数骗自己。</p>
 *
 * @author rag-platform
 */
public enum EvalMetric {

    /** 忠实度：回答是否完全由召回片段支撑（需裁判模型，防幻觉的核心指标） */
    FAITHFULNESS(false, "0.85"),

    /** 答案相关性：回答是否切题（需裁判模型） */
    ANSWER_RELEVANCY(false, "0.80"),

    /** 上下文精确率：召回片段中真正被用上的比例（可由引用数/召回数近似） */
    CONTEXT_PRECISION(true, "0.50"),

    /** 上下文召回率：应召回的内容是否都召回（需标注集） */
    CONTEXT_RECALL(false, "0.80"),

    /** 幻觉率：回答中无出处的事实性陈述比例（越低越好，需裁判模型） */
    HALLUCINATION(false, "0.10"),

    /** 引用覆盖率：有引用支撑的句子占比（可由正文 [n] 标记与引用列表算得） */
    CITATION_COVERAGE(true, "0.90"),

    /** 有用性：人工主观评分 */
    HELPFULNESS(false, "0.80");

    private final boolean computableWithoutJudge;
    private final BigDecimal defaultThreshold;

    EvalMetric(boolean computableWithoutJudge, String defaultThreshold) {
        this.computableWithoutJudge = computableWithoutJudge;
        this.defaultThreshold = new BigDecimal(defaultThreshold);
    }

    /** 是否无需裁判模型即可计算（骨架阶段仅启用这类指标） */
    public boolean isComputableWithoutJudge() {
        return computableWithoutJudge;
    }

    /** 默认门禁阈值（0~1）。低于阈值即 passed=0，用于发版门禁与告警 */
    public BigDecimal getDefaultThreshold() {
        return defaultThreshold;
    }

    /** 本指标是否为「越低越好」（幻觉类）。门禁判定方向相反，写错会把好模型判失败 */
    public boolean isLowerBetter() {
        return this == HALLUCINATION;
    }

    /** 按指标码解析；非法值抛异常，由写入入口转为业务错误码 */
    public static EvalMetric of(String code) {
        if (code != null) {
            for (EvalMetric metric : values()) {
                if (metric.name().equalsIgnoreCase(code.trim())) {
                    return metric;
                }
            }
        }
        throw new IllegalArgumentException("非法的评估指标码: " + code + "（合法取值见 EvalMetric）");
    }
}
''')

# ============================================================ A3 FeedbackRequest
w(API / "dto/chat/FeedbackRequest.java", r'''package com.fintech.rag.api.dto.chat;

import jakarta.validation.constraints.NotBlank;

/**
 * 答案反馈请求（点赞 / 点踩）。
 *
 * <p><b>本接口是「按 traceId 回放」的最短路入口</b>：用户点踩时，
 * 运营只需要 messageId，系统据此反查 {@code t_message.trace_id}，
 * 再拿 traceId 去拉完整链路 —— 用户不需要知道什么是 traceId。</p>
 *
 * @param messageId      被反馈的助手消息 ID（必填）
 * @param vote           LIKE / DISLIKE
 * @param reasonCode     点踩原因：NO_HIT / WRONG_ANSWER / OUTDATED / IRRELEVANT / OTHER
 * @param comment        补充说明，**会做 PII 脱敏后落库**
 * @author rag-platform
 */
public record FeedbackRequest(@NotBlank(message = "消息ID不能为空") String messageId,
                              @NotBlank(message = "反馈类型不能为空") String vote,
                              String reasonCode,
                              String comment) {

    public static final String VOTE_LIKE = "LIKE";
    public static final String VOTE_DISLIKE = "DISLIKE";

    public boolean isLike() {
        return VOTE_LIKE.equalsIgnoreCase(vote);
    }

    public boolean isValidVote() {
        return VOTE_LIKE.equalsIgnoreCase(vote) || VOTE_DISLIKE.equalsIgnoreCase(vote);
    }
}
''')

# ============================================================ A4 ManualEvalRequest
w(API / "dto/eval/ManualEvalRequest.java", r'''package com.fintech.rag.api.dto.eval;

import jakarta.validation.constraints.NotBlank;

import java.math.BigDecimal;

/**
 * 人工评分请求（运营 / 业务专家在后台打分）。
 *
 * <p><b>准入约束</b>：本接口只允许内网应用（AppKey + HMAC 签名）调用，
 * 不允许终端用户直接调用 —— 否则用户可以给自己的问题刷分，
 * 把质量看板变成噪音源。鉴权由 {@code SourceAuthInterceptor} 承担。</p>
 *
 * <p><b>不接收的字段（刻意）</b>：</p>
 * <ul>
 *   <li>{@code passed} —— 由服务端按 metric 的阈值算出，绝不接受调用方传入；</li>
 *   <li>{@code judgeModel} —— 人工评分的裁判是人，写模型名会污染归因统计；</li>
 *   <li>{@code evalSource} —— 本接口恒为 MANUAL，不可篡改。</li>
 * </ul>
 *
 * @param traceId        被评估回答的 traceId（与 messageId 二选一，优先 traceId）
 * @param messageId      被评估的助手消息 ID
 * @param metricCode     指标码，见 {@code EvalMetric}
 * @param score          得分，量纲 0~1
 * @param reason         评分理由（**禁止写问答原文**，只写结论与依据类型）
 * @author rag-platform
 */
public record ManualEvalRequest(String traceId,
                                String messageId,
                                @NotBlank(message = "指标码不能为空") String metricCode,
                                @NotBlank(message = "得分不能为空") BigDecimal score,
                                String reason) {
}
''')

# ============================================================ A5 RetrievalTraceView
w(API / "dto/replay/RetrievalTraceView.java", r'''package com.fintech.rag.api.dto.replay;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 检索段视图 —— 回放时展示「这次回答当时检索到了什么」。
 *
 * <p><b>刻意不包含召回片段原文</b>：片段原文即知识库正文，是整套系统里最敏感的数据。
 * 回放接口的价值在于「看清链路与统计」，不在「搬运正文」——
 * 要正文请走带审计留痕的知识库详情接口。少传一个字段，
 * 就少一条「回放接口被当成批量导出通道」的风险路径。</p>
 *
 * <p>{@code originalQuery} / {@code rewrittenQuery} 属于<b>用户提问侧</b>数据，
 * 敏感度低于片段原文，但仍按内容采集档位控制（METRICS_ONLY 下返回 null）。</p>
 *
 * @param traceId         链路 ID
 * @param conversationId  会话 ID
 * @param subjectType     主体类型
 * @param originalQuery   原始问题（受内容档位控制，可能为 null）
 * @param rewrittenQuery  改写后的检索式（受内容档位控制，可能为 null）
 * @param kbIds           服务端推导后的实际检索范围
 * @param chunkCount      最终召回片段数
 * @param topScore        最高分
 * @param cacheHit        是否命中缓存
 * @param rerankUsed      是否启用精排
 * @param costMs          检索总耗时
 * @param ragflowCostMs   RAGFlow 调用耗时
 * @param result          1 成功 / 0 失败
 * @param errorCode       失败错误码
 * @param createTime      发生时间
 * @author rag-platform
 */
public record RetrievalTraceView(String traceId,
                                 Long conversationId,
                                 String subjectType,
                                 String originalQuery,
                                 String rewrittenQuery,
                                 String kbIds,
                                 Integer chunkCount,
                                 BigDecimal topScore,
                                 Integer cacheHit,
                                 Integer rerankUsed,
                                 Integer costMs,
                                 Integer ragflowCostMs,
                                 Integer result,
                                 String errorCode,
                                 LocalDateTime createTime) {

    /** 空召回判定：链路回放时用于「是没召回到，还是召回了没用上」的快速判别 */
    public boolean emptyHit() {
        return chunkCount == null || chunkCount == 0;
    }
}
''')

# ============================================================ A6 RetrievalClient（改）
w(API / "client/RetrievalClient.java", r'''package com.fintech.rag.api.client;

import com.fintech.rag.api.dto.replay.RetrievalTraceView;
import com.fintech.rag.api.dto.retrieval.RetrievalRequest;
import com.fintech.rag.api.dto.retrieval.RetrievalResponse;
import com.fintech.rag.common.core.R;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;

import java.util.List;

/**
 * 检索服务契约。
 *
 * <p>调用方：rag-chat-service、检索工作台、内网业务微服务。</p>
 *
 * <p><strong>降级策略：fail-close。</strong>检索不可用时返回「服务繁忙」，
 * 绝不可降级为「不检索直接让大模型自由作答」——这等同于放弃引用与合规底线。</p>
 *
 * <p><strong>回放查询的降级策略：fail-open（与检索相反）。</strong>
 * 检索段拿不到时，回放视图仍应返回消息、token 用量与评估分数，
 * 并把缺失原因显式写在 {@code degraded} 里。诊断工具的价值就在于
 * 「依赖挂了也要能看」，此处若 fail-close 反而使问题更难定位。</p>
 *
 * @author rag-platform
 */
@FeignClient(name = "rag-retrieval-service", contextId = "retrievalClient", path = "/api/retrieval")
public interface RetrievalClient {

    /** 执行检索 */
    @PostMapping("/search")
    R<RetrievalResponse> search(@RequestBody RetrievalRequest request);

    /**
     * 按 traceId 查询检索日志（回放用）。
     *
     * <p>为什么是一次可能返回多条的查询：一次用户请求在某些编排下可能触发多次检索
     * （多路召回、工具调用引发的二次检索），运营看到「多条」本身就是有效信息。</p>
     */
    @GetMapping("/logs/trace/{traceId}")
    R<List<RetrievalTraceView>> findLogsByTrace(@PathVariable("traceId") String traceId);
}
''')

# ============================================================ B1 MessageCitation
w(CHAT / "domain/model/MessageCitation.java", r'''package com.fintech.rag.chat.domain.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 消息引用（{@code t_message_citation}）。
 *
 * <p><b>为什么引用必须落库，而不是只返回给前端</b>：</p>
 * <ol>
 *   <li>合规：金融场景要求「答案可溯源」。前端页面刷新后引用就没了，
 *       但监管检查要的是「三个月前那条回答依据的是哪份文件的哪个版本」；</li>
 *   <li>回放：用户点踩时，要能立刻看到「当时引用了哪几段、分数多少」，
 *       才能判断是检索错还是生成错；</li>
 *   <li>文档版本关联：{@code version_no} 落库后才能识别「引用的是已过期版本」。</li>
 * </ol>
 *
 * <p><b>与回放的边界</b>：本表存片段原文（引用必须能原文比对），
 * 但回放接口默认<b>不返回</b> {@code content} —— 见 {@code ReplayAppService}。</p>
 *
 * @author rag-platform
 */
@Data
@TableName("t_message_citation")
public class MessageCitation {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private Long messageId;

    /** 引用序号，对应回答正文中的 [seq] */
    private Integer seq;

    private Long kbId;

    private Long docId;

    private String docName;

    private Integer versionNo;

    /** RAGFlow 片段 ID，便于直接跳回原文定位 */
    private String ragflowChunkId;

    private Integer chunkIndex;

    /** 引用原文片段 */
    private String content;

    private BigDecimal score;

    private Integer pageNo;

    private LocalDateTime createTime;
}
''')

# ============================================================ B2 TokenUsageRecord
w(CHAT / "domain/model/TokenUsageRecord.java", r'''package com.fintech.rag.chat.domain.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * Token 计量流水（{@code t_token_usage}）。
 *
 * <p><b>与「指标」的分工</b>：Prometheus 里的 {@code gen_ai.client.token.usage} 是
 * 观测用的聚合量，会随采样与重启丢细节；本表是<b>计费与成本归因的账本</b>，
 * 要求逐笔、不丢、可按主体/按天/按模型重算。两者不可互相替代。</p>
 *
 * <p><b>为什么用 {@code biz_date} 而不是直接按 create_time 聚合</b>：
 * 账务口径按业务日切分（跨零点的大查询应计入业务日而非自然日），
 * 且按天分区的聚合查询不会因 create_time 上有毫秒精度而无法走索引。</p>
 *
 * <p><b>类名说明</b>：刻意不叫 {@code TokenUsage} —— LangChain4j 有同名类型
 * （{@code dev.langchain4j.model.output.TokenUsage}），同名会导致
 * 「同一个文件里两个 TokenUsage」的编译歧义，属于无谓的维护成本。</p>
 *
 * @author rag-platform
 */
@Data
@TableName("t_token_usage")
public class TokenUsageRecord {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private Long tenantId;

    /** W3C trace-id（32 位小写 hex）：这是把「计费流水」与「链路」对上的唯一钥匙 */
    private String traceId;

    private String subjectType;

    private String subjectId;

    private Long conversationId;

    private Long messageId;

    private String modelCode;

    private String modelName;

    private Integer inputTokens;

    private Integer outputTokens;

    private Integer totalTokens;

    private Integer costMs;

    /** 业务日期，便于按天聚合（账务口径） */
    private LocalDate bizDate;

    private LocalDateTime createTime;
}
''')

# ============================================================ B3 AnswerFeedback
w(CHAT / "domain/model/AnswerFeedback.java", r'''package com.fintech.rag.chat.domain.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 答案反馈（{@code t_feedback}）。
 *
 * <p><b>本表是「知识库建设」最直接的输入源</b>：点踩原因按 {@code reason_code} 聚合后，
 * 「NO_HIT 占比高」说明知识缺口，「WRONG_ANSWER 占比高」说明检索或 Prompt 有问题，
 * 「OUTDATED 占比高」说明制度更新没同步到知识库 —— 三种结论对应三种完全不同的整改动作。</p>
 *
 * <p><b>不设 @TableLogic</b>：反馈记录不做逻辑删除。用户撤回反馈用 {@code handle_status}
 * 表达处理状态，物理记录必须留存（合规要求可追溯「谁在什么时候反馈过什么」）。</p>
 *
 * @author rag-platform
 */
@Data
@TableName("t_feedback")
public class AnswerFeedback {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private Long tenantId;

    private Long messageId;

    private Long conversationId;

    private String subjectType;

    private String subjectId;

    /** LIKE / DISLIKE */
    private String vote;

    /** NO_HIT / WRONG_ANSWER / OUTDATED / IRRELEVANT / OTHER */
    private String reasonCode;

    /** 补充说明（已脱敏） */
    private String comment;

    /** PENDING / PROCESSING / DONE / IGNORED */
    private String handleStatus;

    private String handler;

    private String handleNote;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;
}
''')

# ============================================================ B4 LlmEvalScore
w(CHAT / "domain/model/LlmEvalScore.java", r'''package com.fintech.rag.chat.domain.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * LLM 回答质量评估留档（{@code t_llm_eval_score}）。
 *
 * <p><b>为什么必须落本地库，而不是只留在 LangFuse</b>：LangFuse 的评分随 Trace TTL 被清理，
 * 而合规要求「答案质量评估结论」长期留档（≥ 6 个月）；且本表只留分数与结论、
 * 不留问答原文，即使安全评审不接受 ClickHouse 出现文本，质量报告照样能出。</p>
 *
 * <p><b>写入纪律（由 {@code LlmEvalScoreAppService} 强制，不要绕过它直接 insert）</b>：</p>
 * <ol>
 *   <li>{@code reason} 严禁写问答原文或召回片段全文，只写结论与依据类型；</li>
 *   <li>{@code judge_model} 与 {@code prompt_version} 必须写<b>快照值</b>，
 *       否则历史分数无法归因到具体的 Prompt 改版 —— 「上个月分数掉了」将无从解释；</li>
 *   <li>{@code passed} 必须由服务端按 {@code threshold} 计算，不接受调用方传入；</li>
 *   <li>{@code trace_id} 必须与 {@code t_message.trace_id} 对齐，
 *       否则「按 traceId 回放」时看不到评分。</li>
 * </ol>
 *
 * @author rag-platform
 */
@Data
@TableName("t_llm_eval_score")
public class LlmEvalScore {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private Long tenantId;

    /** 被评估回答的 W3C trace-id（与 t_message.trace_id 对齐） */
    private String traceId;

    /** 被评估的助手消息 ID */
    private Long messageId;

    private Long conversationId;

    /** 离线批量评估批次号；在线抽样与人工评估为空 */
    private String evalBatchNo;

    /** ONLINE / BATCH / MANUAL */
    private String evalSource;

    /** 裁判模型编码（LLM-as-judge）；人工评估为空 */
    private String judgeModel;

    /** 被评估回答所用的 Prompt 版本快照 */
    private String promptVersion;

    /** 指标码，白名单见 EvalMetric */
    private String metricCode;

    /** 得分，量纲由 score_scale 定义 */
    private BigDecimal score;

    /** 量纲：1 表示 0~1（本项目统一为 1） */
    private Integer scoreScale;

    /** 是否通过门禁阈值；未设阈值时为 null */
    private Integer passed;

    /** 本次使用的门禁阈值快照 */
    private BigDecimal threshold;

    /** 评分理由（禁止写问答原文） */
    private String reason;

    private LocalDateTime createTime;

    private String createBy;
}
''')

# ============================================================ B5~B8 Mapper
def mapper(name: str, entity: str, note: str) -> None:
    w(CHAT / f"infra/persistence/mapper/{name}Mapper.java", f'''package com.fintech.rag.chat.infra.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.fintech.rag.chat.domain.model.{entity};
import org.apache.ibatis.annotations.Mapper;

/**
 * {note} 数据访问。
 *
 * <p>刻意只继承 {{@code BaseMapper}} 不写自定义 SQL：复杂聚合（按天成本汇总、
 * 按指标算趋势）应走报表侧或数仓，不在业务服务的 Mapper 里堆 SQL ——
 * 那会让「一次看板查询拖垮问答服务」从不可能变成可能。</p>
 *
 * @author rag-platform
 */
@Mapper
public interface {name}Mapper extends BaseMapper<{entity}> {{
}}
''')


mapper("MessageCitation", "MessageCitation", "消息引用")
mapper("TokenUsageRecord", "TokenUsageRecord", "Token 计量流水")
mapper("AnswerFeedback", "AnswerFeedback", "答案反馈")
mapper("LlmEvalScore", "LlmEvalScore", "回答质量评估留档")

print("---- total:", len(written))
