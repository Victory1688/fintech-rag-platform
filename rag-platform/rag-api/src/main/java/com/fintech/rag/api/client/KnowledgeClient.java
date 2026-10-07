package com.fintech.rag.api.client;

import com.fintech.rag.api.dto.knowledge.DocumentMeta;
import com.fintech.rag.api.dto.knowledge.KbBrief;
import com.fintech.rag.common.core.R;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;

import java.util.List;
import java.util.Map;

/**
 * 知识库服务契约。
 *
 * <p>调用方：rag-chat-service、rag-retrieval-service。</p>
 *
 * <p><strong>降级策略：fail-close。</strong>授权查询失败时必须拒绝本次请求（返回无权限），
 * 绝不可降级为「返回全量知识库」，否则一次依赖抖动就会变成数据泄漏事故。</p>
 *
 * @author rag-platform
 */
@FeignClient(name = "rag-knowledge-service", contextId = "knowledgeClient", path = "/api/kb")
public interface KnowledgeClient {

    /**
     * 查询指定主体已授权的知识库（<b>越权防护的授权真源</b>）。
     *
     * @param subjectType USER / APP
     * @param subjectId   userId / appId
     * @param roleCodes   用户角色编码，逗号分隔（用于按角色授权）；APP 主体传空
     * @param deptId      用户部门 ID（用于按部门授权）；APP 主体传空
     */
    @GetMapping("/authorized")
    R<List<KbBrief>> listAuthorizedKbs(@RequestParam("subjectType") String subjectType,
                                       @RequestParam("subjectId") String subjectId,
                                       @RequestParam(value = "roleCodes", required = false) String roleCodes,
                                       @RequestParam(value = "deptId", required = false) Long deptId);

    /** 批量查询文档元数据（检索结果二次过滤用） */
    @PostMapping("/documents/meta")
    R<List<DocumentMeta>> listDocumentMeta(@RequestBody List<Long> docIds);

    /** 批量获取知识库版本号（检索缓存 Key 构造用） */
    @PostMapping("/version")
    R<Map<String, Long>> getKbVersions(@RequestBody List<Long> kbIds);
}
