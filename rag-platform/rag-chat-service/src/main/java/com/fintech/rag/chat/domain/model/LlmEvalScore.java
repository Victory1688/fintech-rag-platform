package com.fintech.rag.chat.domain.model;

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
