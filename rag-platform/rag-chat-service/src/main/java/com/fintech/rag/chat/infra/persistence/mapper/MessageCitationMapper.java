package com.fintech.rag.chat.infra.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.fintech.rag.chat.domain.model.MessageCitation;
import org.apache.ibatis.annotations.Mapper;

/**
 * 消息引用 数据访问。
 *
 * <p>刻意只继承 {@code BaseMapper} 不写自定义 SQL：复杂聚合（按天成本汇总、
 * 按指标算趋势）应走报表侧或数仓，不在业务服务的 Mapper 里堆 SQL ——
 * 那会让「一次看板查询拖垮问答服务」从不可能变成可能。</p>
 *
 * @author rag-platform
 */
@Mapper
public interface MessageCitationMapper extends BaseMapper<MessageCitation> {
}
