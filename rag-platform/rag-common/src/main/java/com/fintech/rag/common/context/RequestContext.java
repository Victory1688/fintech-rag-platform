package com.fintech.rag.common.context;

/**
 * 请求级上下文（ThreadLocal）。
 *
 * <p>承载：来源、主体身份、客户端 IP、traceId。由
 * {@code RequestContextFilter} 初始化，由各服务的鉴权拦截器补齐身份信息，
 * 请求结束后必须清理，防止线程池复用导致的串号。</p>
 *
 * @author rag-platform
 */
public final class RequestContext {

    private static final ThreadLocal<Snapshot> HOLDER = new ThreadLocal<>();

    private RequestContext() {
    }

    public static void set(Snapshot snapshot) {
        HOLDER.set(snapshot);
    }

    public static Snapshot get() {
        return HOLDER.get();
    }

    public static void clear() {
        HOLDER.remove();
    }

    public static String currentTraceId() {
        Snapshot s = HOLDER.get();
        return s == null ? null : s.traceId();
    }

    public static String currentSubjectId() {
        Snapshot s = HOLDER.get();
        return s == null ? null : s.subjectId();
    }

    public static RequestSource currentSource() {
        Snapshot s = HOLDER.get();
        return s == null ? null : s.source();
    }

    public static boolean isDmzWeb() {
        return currentSource() == RequestSource.DMZ_WEB;
    }

    public static boolean isInnerApp() {
        return currentSource() == RequestSource.SF_INNER_APP;
    }

    /**
     * 上下文的不可变快照。
     *
     * @param source      请求来源
     * @param subjectType 主体类型 USER / APP
     * @param subjectId   主体标识 userId / appId
     * @param subjectName 主体名称（便于日志与审计）
     * @param appId       内网应用 ID（来源为 SF_INNER_APP 时非空）
     * @param clientIp    调用方 IP
     * @param traceId     全链路追踪 ID
     */
    public record Snapshot(RequestSource source,
                           String subjectType,
                           String subjectId,
                           String subjectName,
                           String appId,
                           String clientIp,
                           String traceId) {

        public Snapshot withSubject(String subjectType, String subjectId, String subjectName) {
            return new Snapshot(source, subjectType, subjectId, subjectName, appId, clientIp, traceId);
        }
    }
}
