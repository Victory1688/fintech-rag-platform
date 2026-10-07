package com.fintech.rag.api.server.interceptor;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.core.Ordered;
import org.springframework.web.filter.OncePerRequestFilter;
import org.springframework.web.util.ContentCachingRequestWrapper;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Set;

/**
 * 请求体缓存过滤器。
 *
 * <p>应用签名需要原始请求体参与校验，而 Servlet 的 InputStream 只能读一次。
 * 用 {@link ContentCachingRequestWrapper} 缓存后可重复读取。</p>
 *
 * <p><b>必须跳过文件上传路径</b>：把 200MB 的文档读进堆内存会直接 OOM。</p>
 *
 * @author rag-platform
 */
public class BodyCachingFilter extends OncePerRequestFilter implements Ordered {

    private static final String CACHE_ATTRIBUTE = "CACHED_BODY";

    private static final Set<String> SKIP_PREFIXES = Set.of(
            "/api/ingest/upload", "/actuator", "/v3/api-docs", "/doc.html");

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        ContentCachingRequestWrapper wrapper = new ContentCachingRequestWrapper(request);
        filterChain.doFilter(wrapper, response);
        // 必须在链执行完之后读取：此时 body 才被真正消费并缓存
        byte[] body = wrapper.getContentAsByteArray();
        if (body.length > 0) {
            wrapper.setAttribute(CACHE_ATTRIBUTE, new String(body, StandardCharsets.UTF_8));
        }
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String uri = request.getRequestURI();
        return SKIP_PREFIXES.stream().anyMatch(uri::startsWith);
    }

    @Override
    public int getOrder() {
        return Ordered.HIGHEST_PRECEDENCE + 20;
    }
}
