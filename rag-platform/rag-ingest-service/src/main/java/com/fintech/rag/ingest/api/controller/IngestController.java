package com.fintech.rag.ingest.api.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.fintech.rag.common.core.PageResult;
import com.fintech.rag.common.core.R;
import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import com.fintech.rag.ingest.app.pipeline.DocumentIngestPipeline;
import com.fintech.rag.ingest.domain.model.IngestTask;
import com.fintech.rag.ingest.infra.persistence.mapper.IngestTaskMapper;
import org.springframework.util.DigestUtils;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.InputStream;

/**
 * 文档入库接口。
 *
 * @author rag-platform
 */
@RestController
@RequestMapping("/api/ingest")
public class IngestController {

    /** 类型白名单：只放行解析能力确认为可用的格式 */
    private static final java.util.Set<String> ALLOWED_EXT = java.util.Set.of(
            "pdf", "docx", "doc", "xlsx", "xls", "pptx", "ppt", "txt", "md", "html", "png", "jpg");

    private static final long MAX_FILE_SIZE = 200L * 1024 * 1024;

    private final DocumentIngestPipeline pipeline;
    private final IngestTaskMapper taskMapper;

    public IngestController(DocumentIngestPipeline pipeline, IngestTaskMapper taskMapper) {
        this.pipeline = pipeline;
        this.taskMapper = taskMapper;
    }

    /**
     * 上传并提交入库任务。
     *
     * <p>只做「接收 + 落盘 + 建任务」，解析由流水线与轮询任务推进，
     * 接口本身必须快速返回，不能阻塞在解析上。</p>
     */
    @PostMapping("/upload")
    public R<String> upload(@RequestParam Long kbId,
                            @RequestParam String datasetId,
                            @RequestParam("file") MultipartFile file,
                            @RequestParam(required = false) String submittedBy) throws IOException {
        validate(file);

        // 直接用字节流算摘要，避免「文件字节 -> String -> 再哈希」造成的隐式编码转换
        String md5 = DigestUtils.md5DigestAsHex(file.getBytes());
        try (InputStream in = file.getInputStream()) {
            String taskNo = pipeline.submit(kbId, datasetId, file.getOriginalFilename(),
                    md5, file.getSize(), in, submittedBy);
            return R.ok(taskNo);
        }
    }

    @GetMapping("/tasks")
    public R<PageResult<IngestTask>> page(@RequestParam(defaultValue = "1") long pageNum,
                                          @RequestParam(defaultValue = "20") long pageSize,
                                          @RequestParam(required = false) Long kbId,
                                          @RequestParam(required = false) String status) {
        Page<IngestTask> page = new Page<>(pageNum, pageSize);
        IPage<IngestTask> result = taskMapper.selectPage(page, Wrappers.<IngestTask>lambdaQuery()
                .eq(kbId != null, IngestTask::getKbId, kbId)
                .eq(status != null, IngestTask::getStatus, status)
                .orderByDesc(IngestTask::getSubmittedAt));
        return R.ok(PageResult.of(result.getRecords(), pageNum, pageSize, result.getTotal()));
    }

    @GetMapping("/tasks/detail")
    public R<IngestTask> detail(@RequestParam String taskNo) {
        IngestTask task = taskMapper.selectOne(Wrappers.<IngestTask>lambdaQuery()
                .eq(IngestTask::getTaskNo, taskNo));
        if (task == null) {
            throw BizException.of(ErrorCode.INTERNAL_ERROR, "任务不存在");
        }
        return R.ok(task);
    }

    @PostMapping("/tasks/retry")
    public R<Void> retry(@RequestParam String taskNo) {
        pipeline.retry(taskNo);
        return R.ok();
    }

    private void validate(MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw BizException.of(ErrorCode.PARAM_INVALID, "上传文件不能为空");
        }
        if (file.getSize() > MAX_FILE_SIZE) {
            throw BizException.of(ErrorCode.FILE_TOO_LARGE, "文件超过 200MB 限制");
        }
        String name = file.getOriginalFilename();
        int dot = name == null ? -1 : name.lastIndexOf('.');
        String ext = dot < 0 ? "" : name.substring(dot + 1).toLowerCase();
        if (!ALLOWED_EXT.contains(ext)) {
            throw BizException.of(ErrorCode.FILE_TYPE_UNSUPPORTED, "不支持的文件类型：" + ext);
        }
        // TODO 接入 ClamAV 病毒扫描；未扫描的文件不得进入解析流程
    }
}
