package com.fintech.rag.ingest.app.job;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.fintech.rag.ingest.domain.model.OutboxMessage;
import com.fintech.rag.ingest.infra.mq.IngestEventPublisher;
import com.fintech.rag.ingest.infra.persistence.mapper.OutboxMessageMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

/**
 * Outbox 投递任务。
 *
 * <p>把「本地事务」与「消息投递」解耦：事务只负责写 Outbox，
 * 本任务负责可靠投递，投递成功才标记 SENT，失败则指数退避重试。</p>
 *
 * <p><b>下游必须幂等</b>：本机制是「至少一次」语义，重复投递是正常的，
 * 重复消费才是 bug。</p>
 *
 * @author rag-platform
 */
@Component
public class OutboxRelayJob {

    private static final Logger log = LoggerFactory.getLogger(OutboxRelayJob.class);
    private static final int BATCH_SIZE = 100;
    private static final int MAX_RETRY = 10;

    private final OutboxMessageMapper outboxMapper;
    private final IngestEventPublisher publisher;

    public OutboxRelayJob(OutboxMessageMapper outboxMapper, IngestEventPublisher publisher) {
        this.outboxMapper = outboxMapper;
        this.publisher = publisher;
    }

    @Scheduled(fixedDelayString = "${rag.ingest.outbox-interval-ms:5000}")
    @Transactional(rollbackFor = Exception.class)
    public void relay() {
        List<OutboxMessage> messages = outboxMapper.selectList(Wrappers.<OutboxMessage>lambdaQuery()
                .eq(OutboxMessage::getStatus, "NEW")
                .and(w -> w.isNull(OutboxMessage::getNextRetryAt)
                        .or().le(OutboxMessage::getNextRetryAt, LocalDateTime.now()))
                .orderByAsc(OutboxMessage::getCreateTime)
                .last("limit " + BATCH_SIZE));

        for (OutboxMessage message : messages) {
            boolean sent = publisher.publish(message.getTopic(), message.getTag(),
                    message.getMessageId(), message.getPayload());
            if (sent) {
                message.setStatus("SENT");
            } else {
                int retry = message.getRetryCount() == null ? 1 : message.getRetryCount() + 1;
                message.setRetryCount(retry);
                message.setStatus(retry >= MAX_RETRY ? "FAILED" : "NEW");
                // 指数退避：2^n 秒，上限 10 分钟
                long delaySeconds = Math.min(600, (long) Math.pow(2, retry));
                message.setNextRetryAt(LocalDateTime.now().plusSeconds(delaySeconds));
                log.warn("Outbox 投递失败 messageId={} retry={}", message.getMessageId(), retry);
            }
            outboxMapper.updateById(message);
        }
    }
}
