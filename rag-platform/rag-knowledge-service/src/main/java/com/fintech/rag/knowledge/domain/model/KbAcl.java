package com.fintech.rag.knowledge.domain.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 知识库访问控制。
 *
 * @author rag-platform
 */
@Data
@TableName("t_kb_acl")
public class KbAcl {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private Long tenantId;

    private Long kbId;

    /** USER / ROLE / DEPT / APP */
    private String granteeType;

    /** 对应 userId / roleCode / deptId / appId */
    private String granteeId;

    /** READ / MANAGE */
    private String permission;

    private LocalDateTime createTime;

    private String createBy;
}
