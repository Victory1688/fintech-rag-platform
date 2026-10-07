package com.fintech.rag.ingest.infra.storage;

import com.fintech.rag.common.exception.BizException;
import com.fintech.rag.common.exception.ErrorCode;
import com.fintech.rag.ingest.config.MinioProperties;
import io.minio.BucketExistsArgs;
import io.minio.MakeBucketArgs;
import io.minio.MinioClient;
import io.minio.PutObjectArgs;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.io.InputStream;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;

/**
 * MinIO 对象存储服务 —— 原始文档永久归档。
 *
 * <p>为什么必须自己存一份原始文件：RAGFlow 内只存解析后的分片，
 * 用户点击「查看原文」时需要 PDF 原件定位到对应页码。
 * 归档缺失会导致引用溯源功能直接失效。</p>
 *
 * @author rag-platform
 */
@Service
public class MinioStorageService {

    private static final Logger log = LoggerFactory.getLogger(MinioStorageService.class);
    private static final DateTimeFormatter DATE_FORMAT = DateTimeFormatter.ofPattern("yyyy/MM/dd");

    private final MinioClient minioClient;
    private final MinioProperties properties;

    public MinioStorageService(MinioProperties properties) {
        this.properties = properties;
        this.minioClient = MinioClient.builder()
                .endpoint(properties.getEndpoint())
                .credentials(properties.getAccessKey(), properties.getSecretKey())
                .build();
    }

    /**
     * 上传原始文档。
     *
     * @return 对象 Key，形如 {@code kb/1001/2026/09/29/<sha256前缀>_文件名}
     */
    public String upload(Long kbId, String fileName, String md5, long size, InputStream inputStream) {
        String objectKey = buildObjectKey(kbId, md5, fileName);
        try {
            ensureBucket();
            minioClient.putObject(PutObjectArgs.builder()
                    .bucket(properties.getBucket())
                    .object(objectKey)
                    .stream(inputStream, size, -1)
                    .contentType("application/octet-stream")
                    .build());
            log.info("原始文档归档成功 bucket={} key={}", properties.getBucket(), objectKey);
            return objectKey;
        } catch (Exception ex) {
            log.error("原始文档归档失败 kbId={} fileName={}", kbId, fileName, ex);
            throw BizException.of(ErrorCode.INTERNAL_ERROR, "文档归档失败");
        }
    }

    private String buildObjectKey(Long kbId, String md5, String fileName) {
        String safeName = fileName == null ? "unknown" : fileName.replaceAll("[\\\\/:*?\"<>|]", "_");
        String prefix = md5 == null ? "nohash" : md5.substring(0, Math.min(8, md5.length()));
        return "kb/" + kbId + "/" + LocalDate.now().format(DATE_FORMAT) + "/" + prefix + "_" + safeName;
    }

    private void ensureBucket() throws Exception {
        boolean exists = minioClient.bucketExists(
                BucketExistsArgs.builder().bucket(properties.getBucket()).build());
        if (!exists) {
            minioClient.makeBucket(MakeBucketArgs.builder().bucket(properties.getBucket()).build());
            log.info("创建 MinIO bucket={}", properties.getBucket());
        }
    }
}
