package com.fintech.rag.api.dto.common;

/**
 * 调用主体类型。决定走哪套鉴权与哪套权限模型。
 *
 * @author rag-platform
 */
public enum SubjectType {

    /** 终端用户，权限模型为「人维度」 */
    USER,

    /** 内网应用，权限模型为「应用维度」 */
    APP
}
