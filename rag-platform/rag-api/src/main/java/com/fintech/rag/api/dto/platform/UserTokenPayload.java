package com.fintech.rag.api.dto.platform;

import java.util.List;

/**
 * 用户令牌载荷（JWT 解析结果）。
 *
 * @param userId      用户 ID
 * @param realName    姓名
 * @param deptId      部门 ID
 * @param secretLevel 密级，决定可召回内容的上限
 * @param roles       角色编码列表
 * @author rag-platform
 */
public record UserTokenPayload(String userId,
                               String realName,
                               Long deptId,
                               Integer secretLevel,
                               List<String> roles) {
}
