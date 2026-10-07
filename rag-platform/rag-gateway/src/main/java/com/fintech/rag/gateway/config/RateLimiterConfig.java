package com.fintech.rag.gateway.config;

import com.fintech.rag.common.constant.RagHeaders;
import org.springframework.cloud.gateway.filter.ratelimit.KeyResolver;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;
import reactor.core.publisher.Mono;

/**
 * 网关限流 Key 解析器。
 *
 * <p>限流维度决定「谁能把谁打挂」：</p>
 * <ul>
 *   <li>{@code userKeyResolver}：按用户维度（外网前端流量）。生成链路成本高，
 *       必须按人限流，否则单个用户刷问题就能把模型配额耗尽。</li>
 *   <li>{@code appKeyResolver}：按应用维度（内网业务微服务）。与用户独立成桶，
 *       防止内网批量调用把前端 AI 能力挤垮。</li>
 * </ul>
 *
 * <p>两者必须使用<b>独立的 Redis 桶</b>，因此 Key 前缀不同。</p>
 *
 * @author rag-platform
 */
@Configuration
public class RateLimiterConfig {

    @Bean
    @Primary
    public KeyResolver userKeyResolver() {
        return exchange -> {
            String userId = exchange.getRequest().getHeaders().getFirst(RagHeaders.USER_ID);
            if (userId != null && !userId.isBlank()) {
                return Mono.just("user:" + userId);
            }
            // 未登录/预检请求退化为按 IP，避免所有匿名请求共用一个桶
            String ip = exchange.getRequest().getRemoteAddress() == null
                    ? "unknown"
                    : exchange.getRequest().getRemoteAddress().getAddress().getHostAddress();
            return Mono.just("ip:" + ip);
        };
    }

    @Bean
    public KeyResolver appKeyResolver() {
        return exchange -> {
            String appId = exchange.getRequest().getHeaders().getFirst(RagHeaders.APP_ID);
            return Mono.just("app:" + (appId == null || appId.isBlank() ? "anonymous" : appId));
        };
    }
}
