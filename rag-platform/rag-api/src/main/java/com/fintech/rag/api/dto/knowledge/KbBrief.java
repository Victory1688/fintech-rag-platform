package com.fintech.rag.api.dto.knowledge;

/**
 * 知识库摘要（授权查询结果）。
 *
 * @param kbId           知识库 ID
 * @param kbCode         知识库编码
 * @param kbName         知识库名称
 * @param category       PRODUCT / POLICY / REGULATION / INTERNAL / CASE
 * @param secretLevel    密级 1公开 2内部 3机密
 * @param version        版本号，用于检索缓存 Key 构造与失效
 * @param permission     READ / MANAGE
 * @param docCount       已就绪文档数，0 表示尚未就绪
 * @author rag-platform
 */
public record KbBrief(Long kbId,
                      String kbCode,
                      String kbName,
                      String category,
                      Integer secretLevel,
                      Long version,
                      String permission,
                      Integer docCount) {
}
