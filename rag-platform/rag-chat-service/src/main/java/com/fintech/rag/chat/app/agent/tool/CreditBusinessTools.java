package com.fintech.rag.chat.app.agent.tool;

import dev.langchain4j.agent.tool.P;
import dev.langchain4j.agent.tool.Tool;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * 信贷业务工具集（Function Calling）。
 *
 * <p><b>三条安全约束，缺一不可：</b></p>
 * <ol>
 *   <li><b>只读</b>：只允许查询类工具。任何写操作（修改额度、提交申请）绝不允许
 *       由模型触发，这是不可退让的红线。</li>
 *   <li><b>参数校验</b>：工具入参必须做白名单与格式校验，防止模型构造出越权参数。</li>
 *   <li><b>超时与降级</b>：业务系统不可用时返回「暂时无法查询」，
 *       不得让模型据此编造数据。</li>
 * </ol>
 *
 * <p>骨架中为占位实现，落地时接入真实业务接口（走 rag-api 的 Feign 契约）。</p>
 *
 * @author rag-platform
 */
@Component
public class CreditBusinessTools {

    private static final Logger log = LoggerFactory.getLogger(CreditBusinessTools.class);

    /**
     * 查询产品当前执行利率。
     *
     * @param productCode 产品编码，必须是行内正式编码
     */
    @Tool("查询指定信贷产品的当前执行利率区间。仅在用户明确询问利率时调用，productCode 必须是行内正式产品编码。")
    public String queryProductRate(@P("产品编码，例如 P10086") String productCode) {
        if (productCode == null || !productCode.matches("P\\d{5}")) {
            log.warn("[工具] 非法产品编码请求：{}", productCode);
            return "产品编码格式不正确，无法查询";
        }
        log.info("[工具] 查询产品利率 productCode={}", productCode);
        // TODO 接入信贷产品中台接口；当前返回占位，调用方需按「数据来源：业务系统」标注
        return "{\"productCode\":\"" + productCode + "\",\"status\":\"NOT_INTEGRATED\"}";
    }

    /**
     * 查询某业务条线的在售产品清单。
     *
     * @param channel 业务条线，取值：小微 / 零售 / 对公
     */
    @Tool("查询指定业务条线当前在售的信贷产品清单。仅用于帮助用户确定产品范围，不返回审批结论。")
    public String listProductsByChannel(@P("业务条线，取值：小微 / 零售 / 对公") String channel) {
        if (channel == null || !java.util.Set.of("小微", "零售", "对公").contains(channel)) {
            return "业务条线取值非法，仅支持：小微 / 零售 / 对公";
        }
        log.info("[工具] 查询在售产品 channel={}", channel);
        return "{\"channel\":\"" + channel + "\",\"status\":\"NOT_INTEGRATED\"}";
    }
}
