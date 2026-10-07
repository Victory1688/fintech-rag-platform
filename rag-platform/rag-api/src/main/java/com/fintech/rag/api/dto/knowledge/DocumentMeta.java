package com.fintech.rag.api.dto.knowledge;

import java.time.LocalDate;

/**
 * 文档元数据（检索结果二次过滤与引用展示使用）。
 *
 * @param docId         文档 ID
 * @param kbId          知识库 ID
 * @param docName       文件名
 * @param versionNo     当前版本号
 * @param secretLevel   密级
 * @param effectiveDate 生效日期
 * @param expireDate    失效日期，null 表示长期有效
 * @param parseStatus   解析状态
 * @param chunkNum      分片数
 * @author rag-platform
 */
public record DocumentMeta(Long docId,
                           Long kbId,
                           String docName,
                           Integer versionNo,
                           Integer secretLevel,
                           LocalDate effectiveDate,
                           LocalDate expireDate,
                           String parseStatus,
                           Integer chunkNum) {
}
