package com.fintech.rag.ingest.app.pipeline;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import com.fintech.rag.ingest.domain.model.IngestTask;
import com.fintech.rag.ingest.domain.model.OutboxMessage;
import com.fintech.rag.ingest.infra.client.RagFlowDocumentClient;
import com.fintech.rag.ingest.infra.persistence.mapper.IngestTaskMapper;
import com.fintech.rag.ingest.infra.persistence.mapper.OutboxMessageMapper;
import com.fintech.rag.ingest.infra.storage.MinioStorageService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.io.InputStream;
import java.time.LocalDateTime;
import java.util.UUID;

/**
 * 文档入库流水线 —— 本服务的核心编排。
 *
 * <p>流程：校验 → MinIO 落盘 → 建任务(PENDING) → 上传 RAGFlow → UPLOADED
 * → 触发解析 → PARSING → 轮询(PARSE 完成) → PARSED → 写 Outbox 通知下游。</p>
 *
 * <p><b>事务边界：</b>只有「本地库写入 + Outbox 写入」在一个事务里；
 * 调用 RAGFlow / MinIO 一律在事务之外，失败靠状态机 + 重试补偿，
 * 绝不能把外部系统调用包在数据库事务里（长事务会拖垮连接池）。</p>
 *
 * @author rag-platform
 */
@Service
public class DocumentIngestPipeline {

    private static final Logger log = LoggerFactory.getLogger(DocumentIngestPipeline.class);
    private static final String TOPIC = "RAG_INGEST";
    private static final String TAG_DOC_READY = "DOC_READY";

    private final IngestTaskMapper taskMapper;
    private final OutboxMessageMapper outboxMapper;
    private final MinioStorageService storageService;
    private final RagFlowDocumentClient ragFlowClient;

    public DocumentIngestPipeline(IngestTaskMapper taskMapper,
                                  OutboxMessageMapper outboxMapper,
                                  MinioStorageService storageService,
                                  RagFlowDocumentClient ragFlowClient) {
        this.taskMapper = taskMapper;
        this.outboxMapper = outboxMapper;
        this.storageService = storageService;
        this.ragFlowClient = ragFlowClient;
    }

    /**
     * 提交入库任务。
     *
     * @return 任务号
     */
    public String submit(Long kbId, String datasetId, String fileName, String md5, long size,
                         InputStream inputStream, String submittedBy) {
        // 重复检测：同一知识库下相同 MD5 的文档直接提示，避免重复入库造成召回重复
        Long duplicated = taskMapper.selectCount(Wrappers.<IngestTask>lambdaQuery()
                .eq(IngestTask::getKbId, kbId)
                .eq(IngestTask::getFileMd5, md5)
                .in(IngestTask::getStatus, IngestTask.Status.PENDING.name(),
                        IngestTask.Status.UPLOADED.name(), IngestTask.Status.PARSING.name(),
                        IngestTask.Status.PARSED.name()));
        if (duplicated != null && duplicated > 0) {
            throw BizException.of(ErrorCode.DOC_DUPLICATED, "该文档已存在（内容相同），请勿重复上传");
        }

        String objectKey = storageService.upload(kbId, fileName, md5, size, inputStream);

        IngestTask task = new IngestTask();
        task.setTenantId(0L);
        task.setTaskNo("T" + System.currentTimeMillis() + UUID.randomUUID().toString().substring(0, 6));
        task.setKbId(kbId);
        task.setFileName(fileName);
        task.setFileMd5(md5);
        task.setFileSize(size);
        task.setMinioObjectKey(objectKey);
        task.setStatus(IngestTask.Status.PENDING.name());
        task.setCurrentStep("STORE");
        task.setProgress(10);
        task.setRetryCount(0);
        task.setMaxRetry(3);
        task.setSubmittedBy(submittedBy);
        task.setSubmittedAt(LocalDateTime.now());
        task.setDeleted(0);
        taskMapper.insert(task);

        log.info("入库任务已创建 taskNo={} kbId={} fileName={}", task.getTaskNo(), kbId, fileName);
        return task.getTaskNo();
    }

    /**
     * 推进一步：把 PENDING 的任务上传到 RAGFlow 并触发解析。
     */
    @Transactional(rollbackFor = Exception.class)
    public void advanceUpload(String taskNo, String datasetId, byte[] content) {
        IngestTask task = requireTask(taskNo);
        transit(task, IngestTask.Status.UPLOADED, "UPLOAD", 40,
                () -> {
                    String documentId = ragFlowClient.uploadDocument(datasetId, task.getFileName(), content);
                    task.setRagflowDocumentId(documentId);
                });

        transit(task, IngestTask.Status.PARSING, "PARSE", 60,
                () -> ragFlowClient.startParsing(datasetId, task.getRagflowDocumentId()));
    }

    /**
     * 解析完成：落终态并写 Outbox 通知下游。
     */
    @Transactional(rollbackFor = Exception.class)
    public void markParsed(String taskNo, int chunkNum) {
        IngestTask task = requireTask(taskNo);
        transit(task, IngestTask.Status.PARSED, "PARSED", 100, () -> task.setChunkNum(chunkNum));
        task.setFinishedAt(LocalDateTime.now());
        task.setCostMs(System.currentTimeMillis() - task.getSubmittedAt()
                .atZone(java.time.ZoneId.systemDefault()).toInstant().toEpochMilli());
        taskMapper.updateById(task);

        OutboxMessage message = new OutboxMessage();
        message.setTenantId(0L);
        message.setMessageId("DOC_READY_" + task.getTaskNo());
        message.setTopic(TOPIC);
        message.setTag(TAG_DOC_READY);
        message.setBizKey(task.getTaskNo());
        message.setPayload("{\"taskNo\":\"" + task.getTaskNo() + "\",\"kbId\":"
                + task.getKbId() + ",\"chunkNum\":" + chunkNum + "}");
        message.setStatus("NEW");
        message.setRetryCount(0);
        outboxMapper.insert(message);

        log.info("文档解析完成并写入 Outbox taskNo={} chunkNum={}", taskNo, chunkNum);
    }

    /**
     * 标记失败。超过最大重试次数则不再自动重试，等待人工介入。
     */
    @Transactional(rollbackFor = Exception.class)
    public void markFailed(String taskNo, String errorCode, String errorMsg) {
        IngestTask task = requireTask(taskNo);
        task.setStatus(IngestTask.Status.FAILED.name());
        task.setErrorCode(errorCode);
        task.setErrorMsg(errorMsg == null ? null
                : errorMsg.substring(0, Math.min(1000, errorMsg.length())));
        task.setFinishedAt(LocalDateTime.now());
        taskMapper.updateById(task);
        log.warn("入库任务失败 taskNo={} retryCount={} error={}", taskNo, task.getRetryCount(), errorMsg);
    }

    /** 人工重试：重置状态为 UPLOADED，重新走解析 */
    @Transactional(rollbackFor = Exception.class)
    public void retry(String taskNo) {
        IngestTask task = requireTask(taskNo);
        if (task.getRetryCount() != null && task.getMaxRetry() != null
                && task.getRetryCount() >= task.getMaxRetry()) {
            throw BizException.of(ErrorCode.INTERNAL_ERROR, "已超过最大重试次数，请人工处理");
        }
        if (!IngestTask.canTransit(task.getStatus(), IngestTask.Status.UPLOADED.name())) {
            throw BizException.of(ErrorCode.INTERNAL_ERROR,
                    "当前状态不允许重试：" + task.getStatus());
        }
        task.setStatus(IngestTask.Status.UPLOADED.name());
        task.setRetryCount(task.getRetryCount() == null ? 1 : task.getRetryCount() + 1);
        task.setErrorCode(null);
        task.setErrorMsg(null);
        taskMapper.updateById(task);
    }

    private IngestTask requireTask(String taskNo) {
        IngestTask task = taskMapper.selectOne(Wrappers.<IngestTask>lambdaQuery()
                .eq(IngestTask::getTaskNo, taskNo));
        if (task == null) {
            throw BizException.of(ErrorCode.INTERNAL_ERROR, "任务不存在：" + taskNo);
        }
        return task;
    }

    /** 统一的状态迁移入口：先校验合法性，再执行副作用，最后落库 */
    private void transit(IngestTask task, IngestTask.Status target, String step,
                         int progress, Runnable action) {
        if (!IngestTask.canTransit(task.getStatus(), target.name())) {
            throw BizException.of(ErrorCode.INTERNAL_ERROR,
                    "非法状态迁移 " + task.getStatus() + " -> " + target);
        }
        action.run();
        task.setStatus(target.name());
        task.setCurrentStep(step);
        task.setProgress(progress);
        taskMapper.updateById(task);
    }
}
