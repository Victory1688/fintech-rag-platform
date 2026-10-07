package com.fintech.rag.retrieval.app.query;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Query 改写器。
 *
 * <p>信贷场景下用户提问高度口语化（「小微信用贷能贷多少」），
 * 而文档里写的是「单户最高授信额度」。不做改写，向量相似度会明显偏低。</p>
 *
 * <p>骨架实现采用<b>规则词典</b>：确定性高、零成本、可解释、无幻觉风险。
 * 需要引入大模型改写时，务必加「改写结果不得引入原问题没有的业务实体」的校验，
 * 否则模型会把「抵押贷」改写成「信用贷」，造成答非所问且难以发现。</p>
 *
 * @author rag-platform
 */
@Component
public class QueryRewriter {

    private static final Logger log = LoggerFactory.getLogger(QueryRewriter.class);

    /** 业务术语归一表（口语 → 规范表述） */
    private static final Map<String, String> TERM_DICTIONARY = new LinkedHashMap<>();

    static {
        TERM_DICTIONARY.put("能贷多少", "最高授信额度");
        TERM_DICTIONARY.put("能借多少", "最高授信额度");
        TERM_DICTIONARY.put("利息多少", "执行利率");
        TERM_DICTIONARY.put("利率多少", "执行利率");
        TERM_DICTIONARY.put("要什么材料", "申请材料清单");
        TERM_DICTIONARY.put("需要什么资料", "申请材料清单");
        TERM_DICTIONARY.put("征信要求", "征信准入条件");
        TERM_DICTIONARY.put("能贷几年", "贷款期限");
    }

    /**
     * 改写查询。
     *
     * @param query      原始问题
     * @param bizChannel 业务条线（小微/零售/对公），可作为语境补充
     */
    public String rewrite(String query, String bizChannel) {
        if (query == null || query.isBlank()) {
            return query;
        }

        String rewritten = query;
        for (Map.Entry<String, String> entry : TERM_DICTIONARY.entrySet()) {
            if (rewritten.contains(entry.getKey())) {
                rewritten = rewritten.replace(entry.getKey(), entry.getValue());
            }
        }

        // 补充业务条线语境，提高召回精度
        if (bizChannel != null && !bizChannel.isBlank() && !rewritten.contains(bizChannel)) {
            rewritten = bizChannel + " " + rewritten;
        }

        if (!rewritten.equals(query)) {
            log.debug("Query 改写: [{}] -> [{}]", query, rewritten);
        }
        return rewritten;
    }
}
