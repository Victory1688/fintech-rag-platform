package com.fintech.rag.platform.api.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.fintech.rag.api.dto.platform.AuditLogDTO;
import com.fintech.rag.common.core.PageResult;
import com.fintech.rag.common.core.R;
import com.fintech.rag.platform.domain.model.AuditLog;
import com.fintech.rag.platform.infra.persistence.mapper.AuditLogMapper;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.List;

/**
 * 审计日志接口。
 *
 * <p>写入侧：各服务异步批量上报，<b>失败不得阻塞主链路</b>。
 * 生产建议改为「先落 RocketMQ，本服务消费入库」，避免上报流量直接压到数据库。</p>
 *
 * @author rag-platform
 */
@RestController
@RequestMapping("/api/platform/audit")
public class AuditLogController {

    private final AuditLogMapper auditLogMapper;

    public AuditLogController(AuditLogMapper auditLogMapper) {
        this.auditLogMapper = auditLogMapper;
    }

    @PostMapping("/batch")
    public R<Void> batchSave(@RequestBody List<AuditLogDTO> logs) {
        if (logs == null || logs.isEmpty()) {
            return R.ok();
        }
        List<AuditLog> entities = new ArrayList<>(logs.size());
        for (AuditLogDTO dto : logs) {
            AuditLog entity = new AuditLog();
            entity.setTenantId(0L);
            entity.setTraceId(dto.traceId());
            entity.setEventType(dto.eventType());
            entity.setRequestSource(dto.requestSource());
            entity.setSubjectType(dto.subjectType());
            entity.setSubjectId(dto.subjectId());
            entity.setSubjectName(dto.subjectName());
            entity.setClientIp(dto.clientIp());
            entity.setResource(dto.resource());
            entity.setKbIds(dto.kbIds() == null ? null : dto.kbIds().toString());
            entity.setDocIds(dto.docIds() == null ? null : dto.docIds().toString());
            entity.setDetail(dto.detailJson());
            entity.setResult(dto.result() == null ? 1 : dto.result());
            entity.setErrorCode(dto.errorCode());
            entity.setCostMs(dto.costMs());
            entity.setEventTime(dto.eventTime() == null
                    ? LocalDateTime.now()
                    : LocalDateTime.ofInstant(Instant.ofEpochMilli(dto.eventTime()), ZoneId.systemDefault()));
            entities.add(entity);
        }
        entities.forEach(auditLogMapper::insert);
        return R.ok();
    }

    @GetMapping
    public R<PageResult<AuditLog>> page(@RequestParam(defaultValue = "1") long pageNum,
                                        @RequestParam(defaultValue = "20") long pageSize,
                                        @RequestParam(required = false) String subjectId,
                                        @RequestParam(required = false) String eventType) {
        Page<AuditLog> page = new Page<>(pageNum, pageSize);
        IPage<AuditLog> result = auditLogMapper.selectPage(page,
                Wrappers.<AuditLog>lambdaQuery()
                        .eq(subjectId != null, AuditLog::getSubjectId, subjectId)
                        .eq(eventType != null, AuditLog::getEventType, eventType)
                        .orderByDesc(AuditLog::getEventTime));
        return R.ok(PageResult.of(result.getRecords(), pageNum, pageSize, result.getTotal()));
    }
}
