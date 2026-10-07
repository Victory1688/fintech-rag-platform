package com.fintech.rag.knowledge.api.controller;

import com.fintech.rag.api.dto.knowledge.KbBrief;
import com.fintech.rag.common.core.R;
import com.fintech.rag.knowledge.app.service.KnowledgeBaseAppService;
import com.fintech.rag.knowledge.app.service.KnowledgeBaseAppService.CreateCommand;
import jakarta.validation.constraints.NotBlank;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

/**
 * 知识库接口。
 *
 * @author rag-platform
 */
@RestController
@RequestMapping("/api/kb")
public class KnowledgeBaseController {

    private final KnowledgeBaseAppService appService;

    public KnowledgeBaseController(KnowledgeBaseAppService appService) {
        this.appService = appService;
    }

    /**
     * 创建知识库。
     */
    @PostMapping
    public R<Long> create(@RequestBody KnowledgeBaseCreateRequest request) {
        Long kbId = appService.create(new CreateCommand(
                request.kbCode(), request.kbName(), request.description(), request.category(),
                request.embeddingModel(), request.chunkMethod(), request.chunkTokenNum(),
                request.secretLevel(), request.ownerDeptId(), request.ownerUserId()));
        return R.ok(kbId);
    }

    /**
     * 查询主体已授权的知识库（内网调用为主，是越权防护的授权真源）。
     */
    @GetMapping("/authorized")
    public R<List<KbBrief>> listAuthorized(@RequestParam String subjectType,
                                           @RequestParam String subjectId,
                                           @RequestParam(required = false) String roleCodes,
                                           @RequestParam(required = false) Long deptId) {
        return R.ok(appService.listAuthorized(subjectType, subjectId, roleCodes, deptId));
    }

    /**
     * 批量获取知识库版本号（检索缓存 Key 构造）。
     */
    @PostMapping("/version")
    public R<Map<String, Long>> getKbVersions(@RequestBody List<Long> kbIds) {
        return R.ok(appService.getKbVersions(kbIds));
    }

    /**
     * 调整检索参数。变更会递增知识库版本号，从而让检索缓存自动失效。
     */
    @PostMapping("/retrieval-params")
    public R<Void> updateRetrievalParams(@RequestParam Long kbId,
                                         @RequestParam BigDecimal similarityThreshold,
                                         @RequestParam BigDecimal vectorSimilarityWeight,
                                         @RequestParam Integer topK) {
        appService.updateRetrievalParams(kbId, similarityThreshold, vectorSimilarityWeight, topK);
        return R.ok();
    }

    /**
     * 配置知识库 ACL。
     */
    @PostMapping("/acl")
    public R<Void> bindAcl(@RequestParam Long kbId,
                           @RequestParam String granteeType,
                           @RequestParam String granteeId,
                           @RequestParam(defaultValue = "READ") String permission) {
        appService.bindAcl(kbId, granteeType, granteeId, permission);
        return R.ok();
    }

    /** 创建请求体 */
    public record KnowledgeBaseCreateRequest(@NotBlank String kbCode,
                                             @NotBlank String kbName,
                                             String description,
                                             @NotBlank String category,
                                             String embeddingModel,
                                             String chunkMethod,
                                             Integer chunkTokenNum,
                                             Integer secretLevel,
                                             Long ownerDeptId,
                                             Long ownerUserId) {
    }
}
