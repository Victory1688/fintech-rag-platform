package com.fintech.rag.common.exception;

/**
 * 全局错误码。
 *
 * <p>码段划分（详见 docs/03-数据模型与接口契约.md §8.3）：</p>
 * <ul>
 *   <li>{@code A0xxx} 认证与鉴权</li>
 *   <li>{@code B0xxx} 知识库与文档</li>
 *   <li>{@code C0xxx} 检索</li>
 *   <li>{@code D0xxx} 生成</li>
 *   <li>{@code E0xxx} 配额与限流</li>
 *   <li>{@code F0xxx} 系统</li>
 * </ul>
 *
 * @author rag-platform
 */
public enum ErrorCode {

    // ---------------- 成功 ----------------
    SUCCESS("0", "success"),

    // ---------------- A0xxx 认证与鉴权 ----------------
    TOKEN_INVALID("A0001", "令牌无效或已过期"),
    APP_SIGN_INVALID("A0002", "应用签名校验失败"),
    TIMESTAMP_OUT_OF_WINDOW("A0003", "请求时间戳超出允许窗口"),
    REQUEST_SOURCE_FORGED("A0004", "请求来源标识被伪造，已拒绝"),
    KB_NO_PERMISSION("A0005", "无该知识库访问权限"),
    APP_DISABLED("A0006", "应用已禁用或已过期"),
    APP_IP_NOT_ALLOWED("A0007", "调用方 IP 不在白名单内"),
    NONCE_REPLAYED("A0008", "请求已被重复提交（nonce 重放）"),
    AUTH_SERVICE_UNAVAILABLE("A0009", "认证服务不可用，本次请求已拒绝"),

    // ---------------- B0xxx 知识库与文档 ----------------
    KB_NOT_FOUND("B0001", "知识库不存在"),
    DOC_DUPLICATED("B0002", "文档已存在（MD5 重复）"),
    DOC_PARSE_FAILED("B0003", "文档解析失败"),
    DOC_OFFLINE("B0004", "文档已下线"),
    FILE_TYPE_UNSUPPORTED("B0005", "文件类型不支持"),
    FILE_TOO_LARGE("B0006", "文件超过大小限制"),
    KB_NOT_EMPTY("B0007", "知识库非空，禁止删除"),
    RAGFLOW_DATASET_SYNC_FAILED("B0008", "RAGFlow Dataset 同步失败"),
    DOC_NOT_FOUND("B0009", "文档不存在"),

    // ---------------- C0xxx 检索 ----------------
    RETRIEVAL_NO_HIT("C0001", "知识库中未找到相关内容"),
    RAGFLOW_CALL_FAILED("C0002", "RAGFlow 调用失败"),
    RETRIEVAL_TIMEOUT("C0003", "检索超时"),
    KB_NOT_READY("C0004", "知识库尚未就绪（无已解析文档）"),
    RETRIEVAL_PARAM_INVALID("C0005", "检索参数非法"),

    // ---------------- D0xxx 生成 ----------------
    LLM_CALL_FAILED("D0001", "模型调用失败"),
    LLM_RATE_LIMITED("D0002", "上游模型限流"),
    GUARDRAIL_BLOCKED("D0003", "答案触发安全护栏，已拦截"),
    CONTEXT_TOO_LONG("D0004", "上下文超长"),
    NO_MODEL_AVAILABLE("D0005", "当前密级下无可用模型配置"),

    // ---------------- E0xxx 配额与限流 ----------------
    QPS_LIMIT_EXCEEDED("E0001", "超过 QPS 限流阈值"),
    DAILY_QUOTA_EXCEEDED("E0002", "超过日调用配额"),
    TOKEN_QUOTA_EXCEEDED("E0003", "Token 配额已耗尽"),

    // ---------------- F0xxx 系统 ----------------
    PARAM_INVALID("F0001", "参数校验失败"),
    INTERNAL_ERROR("F0002", "系统内部错误"),
    DEPENDENCY_UNAVAILABLE("F0003", "依赖服务不可用");

    private final String code;
    private final String message;

    ErrorCode(String code, String message) {
        this.code = code;
        this.message = message;
    }

    public String getCode() {
        return code;
    }

    public String getMessage() {
        return message;
    }
}
