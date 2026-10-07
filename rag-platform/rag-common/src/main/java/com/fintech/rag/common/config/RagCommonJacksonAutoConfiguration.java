package com.fintech.rag.common.config;

import com.fasterxml.jackson.databind.ser.std.ToStringSerializer;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.jackson.Jackson2ObjectMapperBuilderCustomizer;
import org.springframework.context.annotation.Bean;

/**
 * Jackson 全局配置。
 *
 * <p><strong>为什么必须把 Long 序列化成字符串：</strong>
 * 本工程主键使用雪花 ID（19 位），超过 JavaScript
 * {@code Number.MAX_SAFE_INTEGER}（2^53-1，16 位），
 * 直接以数字下发会被前端静默截断，导致「前端拿到的主键去查库查不到」，
 * 且极难排查。统一转字符串是业界标准做法。</p>
 *
 * @author rag-platform
 */
@AutoConfiguration
@ConditionalOnClass(Jackson2ObjectMapperBuilderCustomizer.class)
public class RagCommonJacksonAutoConfiguration {

    @Bean
    public Jackson2ObjectMapperBuilderCustomizer longToStringCustomizer() {
        return builder -> builder
                .serializerByType(Long.class, ToStringSerializer.instance)
                .serializerByType(Long.TYPE, ToStringSerializer.instance);
    }
}
