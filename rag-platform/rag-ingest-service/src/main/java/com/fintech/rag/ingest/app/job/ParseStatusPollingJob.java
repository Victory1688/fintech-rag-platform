package com.fintech.rag.ingest.app.job;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.fintech.rag.common.integration.ragflow.RagFlowProperties;
import com.fintech.rag.ingest.app.pipeline.DocumentIngestPipeline;
import com.fintech.rag.ingest.domain.model.IngestTask;
import com.fintech.rag.ingest.infra.client.RagFlowDocumentClient;
import com.fintech.rag.ingest.infra.persistence.mapper.IngestTaskMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.List;

/**
 * 解析状态轮询任务。
 *
 * <p>RAGFlow 不提供解析完成的回调，所以只能轮询。
 * <b>必须设置超时兜底</b>：没有超时判定的话，卡在 PARSING 的任务会永久占用配额，
 * 且用户永远看到「解析中」。</p>
 *
 * @author rag-platform
 */
@Component
public class ParseStatusPollingJob {

    private static final Logger log = LoggerFactory.getLogger(ParseStatusPollingJob.class);
    private static final int BATCH_SIZE = 50;

    private final IngestTaskMapper taskMapper;
    private final RagFlowDocumentClient ragFlowClient;
    private final DocumentIngestPipeline pipeline;
    private final RagFlowProperties ragFlowProperties;

    public ParseStatusPollingJob(IngestTaskMapper taskMapper,
                                 RagFlowDocumentClient ragFlowClient,
                                 DocumentIngestPipeline pipeline,
                                 RagFlowProperties ragFlowProperties) {
        this.taskMapper = taskMapper;
        this.ragFlowClient = ragFlowClient;
        this.pipeline = pipeline;
        this.ragFlowProperties = ragFlowProperties;
    }

    /**
     * 每 10 秒轮询一次解析中的任务。
     */
    @Scheduled(fixedDelayString = "${rag.ingest.poll-interval-ms:10000}")
    public void poll() {
        List<IngestTask> tasks = taskMapper.selectList(Wrappers.<IngestTask>lambdaQuery()
                .eq(IngestTask::getStatus, IngestTask.Status.PARSING.name())
                .orderByAsc(IngestTask::getSubmittedAt)
                .last("limit " + BATCH_SIZE));

        if (tasks.isEmpty()) {
            return;
        }

        for (IngestTask task : tasks) {
            try {
                handle(task);
            } catch (Exception ex) {
                log.error("轮询解析状态异常 taskNo={}", task.getTaskNo(), ex);
            }
        }
    }

    private void handle(IngestTask task) {
        String datasetId = resolveDatasetId(task);
        if (datasetId == null) {
            pipeline.markFailed(task.getTaskNo(), "B0008", "知识库 Dataset 映射缺失");
            return;
        }

        String runStatus = ragFlowClient.queryRunStatus(datasetId, task.getRagflowDocumentId());
        switch (runStatus.toUpperCase()) {
            case "DONE" -> {
                int chunkNum = ragFlowClient.queryChunkCount(datasetId, task.getRagflowDocumentId());
                pipeline.markParsed(task.getTaskNo(), chunkNum);
            }
            case "FAIL" -> pipeline.markFailed(task.getTaskNo(), "B0003", "RAGFlow 解析失败");
            case "UNSTART", "RUNNING" -> checkTimeout(task);
            default -> log.warn("未知解析状态 taskNo={} status={}", task.getTaskNo(), runStatus);
        }
    }

    /** 超时兜底：解析超过阈值直接判失败，释放用户预期 */
    private void checkTimeout(IngestTask task) {
        if (task.getSubmittedAt() == null) {
            return;
        }
        long elapsed = Duration.between(task.getSubmittedAt(), LocalDateTime.now()).toMillis();
        if (elapsed > ragFlowProperties.getParseTimeoutMs()) {
            log.warn("解析超时 taskNo={} elapsedMs={}", task.getTaskNo(), elapsed);
            pipeline.markFailed(task.getTaskNo(), "C0003", "解析超时，请检查文档格式或重试");
        }
    }

    /**
     * TODO 通过 rag-knowledge-service 查询 kbId -> ragflowDatasetId 映射，
     * 骨架阶段直接返回空并说明原因，避免引入不必要的服务依赖。
     */
    private String resolveDatasetId(IngestTask task) {
        return null;
    }
}
