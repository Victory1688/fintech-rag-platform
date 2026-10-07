package com.fintech.rag.common.constant;

/**
 * 全链路请求头常量。
 *
 * <p>集中定义的目的：任何一处硬编码字符串写错，都会造成静默的鉴权绕过或
 * 来源误判，因此禁止在业务代码里手写 Header 名。</p>
 *
 * @author rag-platform
 */
public final class RagHeaders {

    private RagHeaders() {
    }

    // ---------- 来源标识（只能由 DMZ 网关写入） ----------
    /** 请求来源标识，DMZ 网关注入 {@code DMZ_GATEWAY}；内网请求禁止携带 */
    public static final String REQUEST_SOURCE = "X-Request-Source";

    /** 网关签名（可选强校验），不依赖 IP 白名单 */
    public static final String GATEWAY_SIGNATURE = "X-Gateway-Signature";

    // ---------- 外网用户身份（网关校验后透传） ----------
    /** 用户 JWT */
    public static final String USER_TOKEN = "X-User-Token";

    /** 网关解析后的用户 ID */
    public static final String USER_ID = "X-User-Id";

    /** 网关解析后的用户名称 */
    public static final String USER_NAME = "X-User-Name";

    /** 网关解析后的用户角色编码（逗号分隔）。用于「按角色授权」的知识库 ACL 判定 */
    public static final String USER_ROLES = "X-User-Roles";

    /** 网关解析后的用户部门 ID。用于「按部门授权」的知识库 ACL 判定 */
    public static final String USER_DEPT = "X-User-Dept";

    // ---------- 内网应用身份 ----------
    /** 应用 ID */
    public static final String APP_ID = "X-App-Id";

    /** 毫秒时间戳，与服务端偏差超过 5 分钟拒绝 */
    public static final String APP_TIMESTAMP = "X-App-Timestamp";

    /** 随机串，配合 Redis 防重放 */
    public static final String APP_NONCE = "X-App-Nonce";

    /** HMAC-SHA256 签名 */
    public static final String APP_SIGNATURE = "X-App-Signature";

    // ---------- 追踪 ----------
    /**
     * W3C Trace Context 标准透传头，格式 {@code 00-{32hex}-{16hex}-{2hex}}。
     *
     * <p><b>安全约束</b>：该头可由客户端任意伪造，伪造后可污染/覆盖整条链路，
     * 因此必须由网关「先删后写」，且应用侧不得直接信任外部传入值。</p>
     *
     * @see com.fintech.rag.common.util.TraceIds
     */
    public static final String TRACEPARENT = "traceparent";

    /**
     * 业务自定义追踪头（历史兼容）。
     *
     * <p>新代码请使用 {@link #TRACEPARENT}；保留本常量只为兼容早期对接方与
     * 人工排障时手填 traceId 的场景。取值必须是合法的 32 位 hex。</p>
     */
    public static final String TRACE_ID = "X-Trace-Id";
}
