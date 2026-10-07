package com.fintech.rag.common.core;

import com.fintech.rag.common.context.RequestContext;
import com.fintech.rag.common.exception.ErrorCode;

import java.io.Serial;
import java.io.Serializable;

/**
 * 统一返回结构。
 *
 * <p>所有对外 REST 接口必须返回 {@code R<T>}，禁止直接返回裸对象，
 * 否则前端无法统一处理错误码，也无法做全链路 traceId 关联。</p>
 *
 * @param <T> 业务数据类型
 * @author rag-platform
 */
public class R<T> implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    /** 业务码，"0" 表示成功，其它见 {@link ErrorCode} */
    private String code;

    /** 提示信息 */
    private String message;

    /** 全链路追踪 ID，与日志中的 traceId 一致 */
    private String traceId;

    /** 业务数据 */
    private T data;

    /** 服务端时间戳（毫秒） */
    private long timestamp = System.currentTimeMillis();

    public R() {
    }

    public R(String code, String message, T data) {
        this.code = code;
        this.message = message;
        this.data = data;
        this.traceId = RequestContext.currentTraceId();
    }

    public static <T> R<T> ok() {
        return ok(null);
    }

    public static <T> R<T> ok(T data) {
        return new R<>(ErrorCode.SUCCESS.getCode(), ErrorCode.SUCCESS.getMessage(), data);
    }

    public static <T> R<T> fail(ErrorCode errorCode) {
        return new R<>(errorCode.getCode(), errorCode.getMessage(), null);
    }

    public static <T> R<T> fail(ErrorCode errorCode, String message) {
        return new R<>(errorCode.getCode(), message, null);
    }

    public static <T> R<T> fail(String code, String message) {
        return new R<>(code, message, null);
    }

    public boolean isSuccess() {
        return ErrorCode.SUCCESS.getCode().equals(this.code);
    }

    public String getCode() {
        return code;
    }

    public void setCode(String code) {
        this.code = code;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }

    public String getTraceId() {
        return traceId;
    }

    public void setTraceId(String traceId) {
        this.traceId = traceId;
    }

    public T getData() {
        return data;
    }

    public void setData(T data) {
        this.data = data;
    }

    public long getTimestamp() {
        return timestamp;
    }

    public void setTimestamp(long timestamp) {
        this.timestamp = timestamp;
    }
}
