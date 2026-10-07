package com.fintech.rag.retrieval.app.cache;

import com.fintech.rag.common.util.HmacSignatures;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 检索缓存 Key 构造器。
 *
 * <p><b>为什么必须集中构造、禁止业务代码手写 Key：</b>
 * 缓存 Key 少一个维度，就会造成越权。例如漏了授权范围维度，
 * 那么「A 用户查过的问题」会把答案缓存给「只有部分权限的 B 用户」，
 * 结果是 B 看到了自己无权访问的机密制度内容。</p>
 *
 * <p>Key 组成（缺一不可）：</p>
 * <ol>
 *   <li>授权范围指纹（datasetId 排序后哈希）</li>
 *   <li>知识库版本指纹（内容或参数变更 → 版本变化 → 旧缓存自然不命中）</li>
 *   <li>归一化后的查询</li>
 *   <li>业务过滤条件指纹</li>
 *   <li>用户密级</li>
 *   <li>检索参数指纹</li>
 * </ol>
 *
 * @author rag-platform
 */
@Component
public class RetrievalCacheKeyBuilder {

    private static final String PREFIX = "ret:v1:";

    public String build(List<String> datasetIds, Map<String, Long> kbVersions,
                        String normalizedQuery, String filtersFingerprint,
                        int userSecretLevel, String optionsFingerprint) {
        String datasetHash = sha(sorted(datasetIds));
        String versionHash = sha(kbVersions.entrySet().stream()
                .sorted(Map.Entry.comparingByKey())
                .map(e -> e.getKey() + "=" + e.getValue())
                .collect(Collectors.joining("&")));
        String queryHash = sha(normalizedQuery);

        return PREFIX + datasetHash + ":" + versionHash + ":" + queryHash + ":"
                + filtersFingerprint + ":" + userSecretLevel + ":" + optionsFingerprint;
    }

    /** 归一化查询：去空白、统一大小写、去掉无意义标点，避免「同一问题两种写法」重复穿透 */
    public String normalizeQuery(String query) {
        if (query == null) {
            return "";
        }
        return query.trim()
                .toLowerCase()
                .replaceAll("[\\s\\p{Punct}]+", "")
                .replaceAll("[，。？！；：、“”‘’（）《》]", "");
    }

    private String sorted(List<String> ids) {
        if (ids == null || ids.isEmpty()) {
            return "EMPTY";
        }
        return ids.stream().sorted().collect(Collectors.joining(","));
    }

    private String sha(String value) {
        String hex = HmacSignatures.sha256Hex(value == null ? "" : value);
        return hex.substring(0, 16);
    }
}
