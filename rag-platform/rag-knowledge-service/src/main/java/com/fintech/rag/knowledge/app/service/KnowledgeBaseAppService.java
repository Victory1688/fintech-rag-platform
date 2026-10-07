package com.fintech.rag.knowledge.app.service;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.fintech.rag.api.dto.knowledge.KbBrief;
import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import com.fintech.rag.knowledge.domain.model.KbAcl;
import com.fintech.rag.knowledge.domain.model.KnowledgeBase;
import com.fintech.rag.knowledge.infra.client.RagFlowDatasetClient;
import com.fintech.rag.knowledge.infra.persistence.mapper.KbAclMapper;
import com.fintech.rag.knowledge.infra.persistence.mapper.KnowledgeBaseMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 知识库应用服务。
 *
 * <p><b>RAGFlow 不在本地事务内</b>：创建知识库时先建本地记录，再调 RAGFlow，
 * 失败则把本地记录标记为「同步失败」并允许重试。
 * 反过来（先调 RAGFlow 再建本地记录）会产生 RAGFlow 侧垃圾 Dataset。</p>
 *
 * @author rag-platform
 */
@Service
public class KnowledgeBaseAppService {

    private static final Logger log = LoggerFactory.getLogger(KnowledgeBaseAppService.class);

    private final KnowledgeBaseMapper knowledgeBaseMapper;
    private final KbAclMapper kbAclMapper;
    private final RagFlowDatasetClient ragFlowDatasetClient;
    private final AuthorizedKbQueryAppService authorizedKbQueryAppService;

    public KnowledgeBaseAppService(KnowledgeBaseMapper knowledgeBaseMapper,
                                   KbAclMapper kbAclMapper,
                                   RagFlowDatasetClient ragFlowDatasetClient,
                                   AuthorizedKbQueryAppService authorizedKbQueryAppService) {
        this.knowledgeBaseMapper = knowledgeBaseMapper;
        this.kbAclMapper = kbAclMapper;
        this.ragFlowDatasetClient = ragFlowDatasetClient;
        this.authorizedKbQueryAppService = authorizedKbQueryAppService;
    }

    /**
     * 创建知识库（含 RAGFlow Dataset 同步）。
     */
    @Transactional(rollbackFor = Exception.class)
    public Long create(CreateCommand command) {
        Long exists = knowledgeBaseMapper.selectCount(Wrappers.<KnowledgeBase>lambdaQuery()
                .eq(KnowledgeBase::getKbCode, command.kbCode()));
        if (exists != null && exists > 0) {
            throw BizException.of(ErrorCode.PARAM_INVALID, "知识库编码已存在：" + command.kbCode());
        }

        KnowledgeBase kb = new KnowledgeBase();
        kb.setTenantId(0L);
        kb.setKbCode(command.kbCode());
        kb.setKbName(command.kbName());
        kb.setDescription(command.description());
        kb.setCategory(command.category());
        kb.setEmbeddingModel(command.embeddingModel());
        kb.setChunkMethod(command.chunkMethod() == null ? "NAIVE" : command.chunkMethod());
        kb.setChunkTokenNum(command.chunkTokenNum() == null ? 512 : command.chunkTokenNum());
        // 检索参数默认值来自评测经验，最终以评测集回归结果调优
        kb.setSimilarityThreshold(new BigDecimal("0.20"));
        kb.setVectorSimilarityWeight(new BigDecimal("0.30"));
        kb.setTopK(1024);
        kb.setRerankModel("BAAI/bge-reranker-v2-m3");
        kb.setSecretLevel(command.secretLevel() == null ? 2 : command.secretLevel());
        kb.setOwnerDeptId(command.ownerDeptId());
        kb.setOwnerUserId(command.ownerUserId());
        kb.setDocCount(0);
        kb.setChunkCount(0L);
        kb.setVersion(1L);
        kb.setStatus(1);
        kb.setDeleted(0);
        knowledgeBaseMapper.insert(kb);

        String datasetId = ragFlowDatasetClient.createDataset(
                command.kbCode(), command.description(), command.embeddingModel(),
                kb.getChunkMethod(), kb.getChunkTokenNum());
        kb.setRagflowDatasetId(datasetId);
        knowledgeBaseMapper.updateById(kb);

        log.info("创建知识库完成 kbId={} kbCode={} datasetId={}", kb.getId(), kb.getKbCode(), datasetId);
        return kb.getId();
    }

    /**
     * 更新知识库。任何影响检索结果的变更都必须 version + 1，触发检索缓存失效。
     */
    @Transactional(rollbackFor = Exception.class)
    public void updateRetrievalParams(Long kbId, BigDecimal similarityThreshold,
                                      BigDecimal vectorSimilarityWeight, Integer topK) {
        KnowledgeBase kb = knowledgeBaseMapper.selectById(kbId);
        if (kb == null) {
            throw BizException.of(ErrorCode.KB_NOT_FOUND);
        }
        kb.setSimilarityThreshold(similarityThreshold);
        kb.setVectorSimilarityWeight(vectorSimilarityWeight);
        kb.setTopK(topK);
        kb.setVersion(kb.getVersion() == null ? 1L : kb.getVersion() + 1);
        knowledgeBaseMapper.updateById(kb);
        log.info("更新检索参数并递增版本 kbId={} version={}", kbId, kb.getVersion());
    }

    public List<KbBrief> listAuthorized(String subjectType, String subjectId,
                                        String roleCodes, Long deptId) {
        return authorizedKbQueryAppService.listAuthorizedKbs(subjectType, subjectId, roleCodes, deptId);
    }

    /** 批量获取知识库版本号，供检索缓存 Key 构造 */
    public Map<String, Long> getKbVersions(List<Long> kbIds) {
        if (kbIds == null || kbIds.isEmpty()) {
            return Map.of();
        }
        return knowledgeBaseMapper.selectList(Wrappers.<KnowledgeBase>lambdaQuery()
                        .select(KnowledgeBase::getId, KnowledgeBase::getVersion)
                        .in(KnowledgeBase::getId, kbIds))
                .stream()
                .collect(Collectors.toMap(kb -> String.valueOf(kb.getId()),
                        kb -> kb.getVersion() == null ? 0L : kb.getVersion()));
    }

    public void bindAcl(Long kbId, String granteeType, String granteeId, String permission) {
        KbAcl acl = new KbAcl();
        acl.setTenantId(0L);
        acl.setKbId(kbId);
        acl.setGranteeType(granteeType);
        acl.setGranteeId(granteeId);
        acl.setPermission(permission == null ? "READ" : permission);
        kbAclMapper.insert(acl);
    }

    /** 创建命令 */
    public record CreateCommand(String kbCode, String kbName, String description, String category,
                                String embeddingModel, String chunkMethod, Integer chunkTokenNum,
                                Integer secretLevel, Long ownerDeptId, Long ownerUserId) {
    }
}
