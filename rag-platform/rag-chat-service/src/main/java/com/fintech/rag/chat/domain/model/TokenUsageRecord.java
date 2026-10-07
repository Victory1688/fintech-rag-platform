package com.fintech.rag.chat.domain.model;

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
