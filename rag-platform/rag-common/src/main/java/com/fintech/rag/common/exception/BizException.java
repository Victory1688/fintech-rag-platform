package com.fintech.rag.common.exception;

import java.io.Serial;

/**
 * 业务异常。
 *
 * <p>约定：可预期的业务错误抛 {@code BizException}，由全局异常处理器转成标准返回体；
 * 不可预期的错误直接抛运行时异常并告警。</p>
 *
 * @author rag-platform
 */
public class BizException extends RuntimeException {

    @Serial
    private static final long serialVersionUID = 1L;

    private final String code;

    public BizException(ErrorCode errorCode) {
        super(errorCode.getMessage());
        this.code = errorCode.getCode();
    }

    public BizException(ErrorCode errorCode, String message) {
        super(message);
        this.code = errorCode.getCode();
    }

    public BizException(ErrorCode errorCode, String message, Throwable cause) {
        super(message, cause);
        this.code = errorCode.getCode();
    }

    public String getCode() {
        return code;
    }

    public static BizException of(ErrorCode errorCode) {
        return new BizException(errorCode);
    }

    public static BizException of(ErrorCode errorCode, String message) {
        return new BizException(errorCode, message);
    }
}
