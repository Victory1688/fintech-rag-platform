package com.fintech.rag.knowledge.app.service;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.fintech.rag.api.dto.knowledge.KbBrief;
import com.fintech.rag.knowledge.domain.model.KbAcl;
import com.fintech.rag.knowledge.domain.model.KnowledgeBase;
import com.fintech.rag.knowledge.infra.persistence.mapper.KbAclMapper;
import com.fintech.rag.knowledge.infra.persistence.mapper.KnowledgeBaseMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * 授权知识库查询服务 —— <b>越权防护的「授权真源」</b>。
 *
 * <p>全平台只有这里可以回答「某个主体能访问哪些知识库」。
 * rag-chat-service 与 rag-retrieval-service 都必须调用本服务的结果作为硬约束，
 * <b>绝不接受请求体中传入的知识库 ID 作为授权依据</b>。</p>
 *
 * <p>授权匹配规则（并集）：</p>
 * <ul>
 *   <li>APP 主体：匹配 granteeType=APP 且 granteeId=appId</li>
 *   <li>USER 主体：匹配 granteeType=USER(=userId)、ROLE(∈用户角色)、DEPT(=用户部门)</li>
 * </ul>
 *
 * @author rag-platform
 */
@Service
public class AuthorizedKbQueryAppService {

    private static final Logger log = LoggerFactory.getLogger(AuthorizedKbQueryAppService.class);

    private final KbAclMapper kbAclMapper;
    private final KnowledgeBaseMapper knowledgeBaseMapper;

    public AuthorizedKbQueryAppService(KbAclMapper kbAclMapper, KnowledgeBaseMapper knowledgeBaseMapper) {
        this.kbAclMapper = kbAclMapper;
        this.knowledgeBaseMapper = knowledgeBaseMapper;
    }

    /**
     * 查询主体已授权的知识库。
     *
     * @param subjectType USER / APP
     * @param subjectId   userId / appId
     * @param roleCodes   逗号分隔的角色编码，USER 主体必传（网关从 JWT 解析后透传）
     * @param deptId      部门 ID，USER 主体必传
     */
    public List<KbBrief> listAuthorizedKbs(String subjectType, String subjectId,
                                           String roleCodes, Long deptId) {
        List<String> granteeIds = new ArrayList<>();
        Set<String> granteeTypes = new HashSet<>();

        if ("APP".equalsIgnoreCase(subjectType)) {
            granteeTypes.add("APP");
            granteeIds.add(subjectId);
        } else {
            granteeTypes.add("USER");
            granteeIds.add(subjectId);
            if (roleCodes != null && !roleCodes.isBlank()) {
                granteeTypes.add("ROLE");
                for (String role : roleCodes.split(",")) {
                    if (!role.isBlank()) {
                        granteeIds.add(role.trim());
                    }
                }
            }
            if (deptId != null) {
                granteeTypes.add("DEPT");
                granteeIds.add(String.valueOf(deptId));
            }
        }

        List<KbAcl> acls = kbAclMapper.selectList(Wrappers.<KbAcl>lambdaQuery()
                .in(KbAcl::getGranteeType, granteeTypes)
                .in(KbAcl::getGranteeId, granteeIds));

        if (acls.isEmpty()) {
            log.info("主体无任何知识库授权 subjectType={} subjectId={}", subjectType, subjectId);
            return List.of();
        }

        // 同一知识库被多种方式授权时，取最高权限
        Map<Long, String> permissionMap = new HashMap<>();
        for (KbAcl acl : acls) {
            permissionMap.merge(acl.getKbId(), acl.getPermission() == null ? "READ" : acl.getPermission(),
                    (oldPerm, newPerm) -> "MANAGE".equals(newPerm) ? newPerm : oldPerm);
        }

        List<KnowledgeBase> bases = knowledgeBaseMapper.selectList(Wrappers.<KnowledgeBase>lambdaQuery()
                .in(KnowledgeBase::getId, permissionMap.keySet())
                .eq(KnowledgeBase::getStatus, 1));

        return bases.stream()
                .map(kb -> new KbBrief(
                        kb.getId(),
                        kb.getKbCode(),
                        kb.getKbName(),
                        kb.getCategory(),
                        kb.getSecretLevel(),
                        kb.getVersion(),
                        permissionMap.get(kb.getId()),
                        kb.getDocCount()))
                .collect(Collectors.toList());
    }
}
