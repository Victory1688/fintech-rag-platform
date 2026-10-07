package com.fintech.rag.platform.domain.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 内网应用凭证。
 *
 * @author rag-platform
 */
@Data
@TableName("t_app_credential")
public class AppCredential {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private Long tenantId;

    /** 应用 ID */
    private String appId;

    private String appName;

    /** AppSecret 密文（AES-256-GCM），禁止明文入库、禁止日志打印 */
    private String appSecretEnc;

    private String owner;

    private Integer qpsLimit;

    private Long dailyLimit;

    /** 调用方 IP 白名单，逗号分隔，空表示不限 */
    private String ipWhitelist;

    /** 1 启用 0 禁用 */
    private Integer status;

    private LocalDateTime expireAt;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;

    private String createBy;

    @TableLogic
    private Integer deleted;
}
