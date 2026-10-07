package com.fintech.rag.api.dto.common;

/**
 * 评估来源 —— 回答质量分数的「出处」。
 *
 * <p><b>为什么必须区分来源</b>：三种来源的可信度与用途完全不同，混在一起统计会得出错误结论。</p>
 *
 * <table border="1">
 *   <caption>来源对比</caption>
 *   <tr><th>来源</th><th>触发方</th><th>典型指标</th><th>用途</th><th>可信度</th></tr>
 *   <tr><td>ONLINE</td><td>系统按采样率自动</td><td>CITATION_COVERAGE、CONTEXT_PRECISION</td>
 *       <td>线上质量趋势监控</td><td>中（可算指标确定，代理指标近似）</td></tr>
 *   <tr><td>BATCH</td><td>离线评测任务</td><td>全量指标</td>
 *       <td><b>发版门禁</b></td><td>高（固定评测集 + 固定裁判）</td></tr>
 *   <tr><td>MANUAL</td><td>运营 / 业务专家</td><td>HELPFULNESS</td>
 *       <td>争议样本定调、标注黄金集</td><td>最高</td></tr>
 * </table>
 *
 * <p><b>门禁只能用 BATCH</b>：样本量可控、评测集固定、结果可复现。
 * 用 ONLINE 分数做发版门禁会被采样偏差与流量结构变化带偏。</p>
 *
 * @author rag-platform
 */
public enum EvalSource {

    /** 在线抽样：回答完成后异步评分，不阻塞用户 */
    ONLINE,

    /** 离线批量：评测任务跑固定评测集，是发版门禁的唯一合法来源 */
    BATCH,

    /** 人工评估：运营在后台对具体回答打分 */
    MANUAL
}
