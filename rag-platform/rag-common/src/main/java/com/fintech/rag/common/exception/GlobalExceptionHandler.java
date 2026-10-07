package com.fintech.rag.common.exception;

import com.fintech.rag.common.core.R;
import jakarta.servlet.http.HttpServletRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.validation.BindException;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.stream.Collectors;

/**
 * 全局异常处理器（Servlet 栈）。
 *
 * <p>由 {@code RagCommonWebAutoConfiguration} 条件装配，WebFlux 网关不会加载本类。</p>
 *
 * @author rag-platform
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(BizException.class)
    public R<Void> handleBizException(BizException ex, HttpServletRequest request) {
        log.warn("业务异常 uri={} code={} msg={}", request.getRequestURI(), ex.getCode(), ex.getMessage());
        return R.fail(ex.getCode(), ex.getMessage());
    }

    @ExceptionHandler({MethodArgumentNotValidException.class, BindException.class})
    public R<Void> handleValidationException(Exception ex) {
        String detail;
        if (ex instanceof MethodArgumentNotValidException manv) {
            detail = manv.getBindingResult().getFieldErrors().stream()
                    .map(FieldError::getDefaultMessage)
                    .collect(Collectors.joining("; "));
        } else {
            BindException be = (BindException) ex;
            detail = be.getBindingResult().getFieldErrors().stream()
                    .map(FieldError::getDefaultMessage)
                    .collect(Collectors.joining("; "));
        }
        log.warn("参数校验失败 detail={}", detail);
        return R.fail(ErrorCode.PARAM_INVALID, detail);
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public R<Void> handleIllegalArgument(IllegalArgumentException ex) {
        log.warn("参数非法 msg={}", ex.getMessage());
        return R.fail(ErrorCode.PARAM_INVALID, ex.getMessage());
    }

    @ExceptionHandler(Exception.class)
    public R<Void> handleException(Exception ex, HttpServletRequest request) {
        // 未预期异常必须打完整堆栈并触发告警，不允许静默吞掉
        log.error("系统异常 uri={}", request.getRequestURI(), ex);
        return R.fail(ErrorCode.INTERNAL_ERROR);
    }
}
