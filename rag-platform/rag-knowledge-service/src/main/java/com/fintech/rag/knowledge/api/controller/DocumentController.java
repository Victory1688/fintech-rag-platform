package com.fintech.rag.knowledge.api.controller;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.fintech.rag.api.dto.knowledge.DocumentMeta;
import com.fintech.rag.common.core.R;
import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import com.fintech.rag.knowledge.domain.model.KbDocument;
import com.fintech.rag.knowledge.infra.persistence.mapper.KbDocumentMapper;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.stream.Collectors;

/**
 * 文档接口。
 *
 * @author rag-platform
 */
@RestController
@RequestMapping("/api/kb/documents")
public class DocumentController {

    private final KbDocumentMapper documentMapper;

    public DocumentController(KbDocumentMapper documentMapper) {
        this.documentMapper = documentMapper;
    }

    /**
     * 批量查询文档元数据（检索结果二次过滤使用：密级、生效期）。
     */
    @PostMapping("/meta")
    public R<List<DocumentMeta>> listMeta(@RequestBody List<Long> docIds) {
        if (docIds == null || docIds.isEmpty()) {
            return R.ok(List.of());
        }
        List<DocumentMeta> metas = documentMapper.selectList(Wrappers.<KbDocument>lambdaQuery()
                        .in(KbDocument::getId, docIds))
                .stream()
                .map(doc -> new DocumentMeta(
                        doc.getId(), doc.getKbId(), doc.getDocName(), doc.getVersionNo(),
                        doc.getSecretLevel(), doc.getEffectiveDate(), doc.getExpireDate(),
                        doc.getParseStatus(), doc.getChunkNum()))
                .collect(Collectors.toList());
        return R.ok(metas);
    }

    /**
     * 下线文档：下线后不可再被召回。
     *
     * <p>必须同步调用 RAGFlow 把文档从可检索状态摘除，否则「UI 下线了但检索还在召回」，
     * 是同类系统最常见的线上事故之一。</p>
     */
    @PostMapping("/offline")
    public R<Void> offline(@RequestParam Long docId, @RequestParam String reason) {
        KbDocument document = documentMapper.selectById(docId);
        if (document == null) {
            throw BizException.of(ErrorCode.DOC_NOT_FOUND);
        }
        document.setParseStatus("OFFLINE");
        document.setOfflineReason(reason);
        documentMapper.updateById(document);
        // TODO 调用 RAGFlow 摘除文档可检索状态；失败必须告警并进入重试队列
        return R.ok();
    }
}
