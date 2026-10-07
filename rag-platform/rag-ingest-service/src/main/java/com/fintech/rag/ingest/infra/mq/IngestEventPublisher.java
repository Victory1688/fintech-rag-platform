package com.fintech.rag.ingest.infra.mq;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * 入库事件发布器。
 *
 * <p>骨架中给出接口与默认实现（仅打日志），落地时替换为 RocketMQ 生产者：</p>
 * <pre>
 * rocketMQTemplate.syncSend(topic + ":" + tag, MessageBuilder.withPayload(payload)
 *         .setHeader(RocketMQHeaders.KEYS, messageId).build());
 * </pre>
 *
 * <p>下游（knowledge / platform 审计 / 看板）必须按 {@code messageId} 做幂等，
 * 因为 Outbox 是<b>至少一次</b>投递语义。</p>
 *
 * @author rag-platform
 */
@Component
public class IngestEventPublisher {

    private static final Logger log = LoggerFactory.getLogger(IngestEventPublisher.class);

    /**
     * 发布事件。
     *
     * @return true 表示投递成功（可以标记 SENT）
     */
    public boolean publish(String topic, String tag, String messageId, String payload) {
        // TODO 替换为 RocketMQ 同步发送；当前为骨架实现
        log.info("[Outbox] 投递事件 topic={} tag={} messageId={} payloadLen={}",
                topic, tag, messageId, payload == null ? 0 : payload.length());
        return true;
    }
}
