package com.fintech.rag.api.dto.platform;

import java.util.List;

/**
 * 审计日志（各服务异步上报）。
 *
 * <p>金融合规要求：谁、何时、问了什么、召回了哪些文档，必须可追溯。
 * 因此本 DTO 的字段不允许随意裁剪。</p>
 *
 * @param traceId       追踪 ID
 * @param eventType     QUERY / RETRIEVAL / INGEST / KB_CHANGE / AUTH / CONFIG_CHANGE
 * @param requestSource DMZ_WEB / SF_INNER_APP
 * @param subjectType   USER / APP
 * @param subjectId     主体标识
 * @param subjectName   主体名称
 * @param clientIp      客户端 IP
 * @param resource      资源
 * @param kbIds         涉及知识库
 * @param docIds        涉及文档
 * @param detailJson    明细 JSON（已脱敏）
 * @param result        1成功 0失败
 * @param errorCode     错误码
 * @param costMs        耗时
 * @param eventTime     事件时间（毫秒时间戳）
 * @author rag-platform
 */
public record AuditLogDTO(String traceId,
                          String eventType,
                          String requestSource,
                          String subjectType,
                          String subjectId,
                          String subjectName,
                          String clientIp,
                          String resource,
                          List<Long> kbIds,
                          List<Long> docIds,
                          String detailJson,
                          Integer result,
                          String errorCode,
                          Integer costMs,
                          Long eventTime) {
}
