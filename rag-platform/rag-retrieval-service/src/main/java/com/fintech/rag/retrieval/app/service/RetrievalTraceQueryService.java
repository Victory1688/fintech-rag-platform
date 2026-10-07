package com.fintech.rag.retrieval.app.service;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.fintech.rag.api.dto.replay.RetrievalTraceView;
import com.fintech.rag.common.observability.ContentSanitizer;
import com.fintech.rag.retrieval.domain.model.RetrievalLog;
import com.fintech.rag.retrieval.infra.persistence.mapper.RetrievalLogMapper;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;

/**
 * 检索日志的按 traceId 查询 —— 供「按 traceId 一键回放」使用。
 *
 * <p><b>为什么查询侧也要过一遍脱敏</b>：库里存的是检索当时的原始问题与改写式，
 * 它们是用户输入的一部分。回放接口把它们直接返回，等于给「查看用户提问原文」
 * 开了一个绕过内容档位的后门。因此这里统一走
 * {@link ContentSanitizer#forReporting}，档位为 METRICS_ONLY 时
 * 返回 null —— <b>返回 null（字段不出现）比返回掩码后的文本更安全</b>，
 * 因为掩码规则总有疏漏的可能，而「不传」没有疏漏。</p>
 *
 * <p><b>为什么不做分页</b>：单条 traceId 下的检索次数天然有限（多路召回也就几条到几十条）。
 * 加一个「上限保护」即可，引入分页参数只会让调用方多写一层无意义的分页处理。</p>
 *
 * @author rag-platform
 */
@Service
public class RetrievalTraceQueryService {

    /** 单次回放最多返回的检索记录条数：防御「异常编排导致同一 traceId 下产生海量记录」 */
    private static final int MAX_ROWS = 50;

    private final RetrievalLogMapper retrievalLogMapper;
    private final ContentSanitizer sanitizer;

    public RetrievalTraceQueryService(RetrievalLogMapper retrievalLogMapper,
                                      ContentSanitizer sanitizer) {
        this.retrievalLogMapper = retrievalLogMapper;
        this.sanitizer = sanitizer;
    }

    /** 按 traceId 查询检索日志（时间正序：先发生的检索在前，符合阅读习惯） */
    public List<RetrievalTraceView> findByTrace(String traceId) {
        if (traceId == null || traceId.isBlank()) {
            return List.of();
        }
        List<RetrievalLog> logs = retrievalLogMapper.selectList(Wrappers.<RetrievalLog>lambdaQuery()
                .eq(RetrievalLog::getTraceId, traceId)
                .orderByAsc(RetrievalLog::getCreateTime)
                .last("limit " + MAX_ROWS));

        List<RetrievalTraceView> views = new ArrayList<>(logs.size());
        for (RetrievalLog log : logs) {
            views.add(new RetrievalTraceView(
                    log.getTraceId(),
                    log.getConversationId(),
                    log.getSubjectType(),
                    // 受内容档位控制：METRICS_ONLY 下为 null（字段不出现，而非掩码）
                    sanitizer.forReporting(log.getOriginalQuery()),
                    sanitizer.forReporting(log.getRewrittenQuery()),
                    log.getKbIds(),
                    log.getChunkCount(),
                    log.getTopScore(),
                    log.getCacheHit(),
                    log.getRerankUsed(),
                    log.getCostMs(),
                    log.getRagflowCostMs(),
                    log.getResult(),
                    log.getErrorCode(),
                    log.getCreateTime()));
        }
        return views;
    }
}
