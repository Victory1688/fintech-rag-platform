package com.fintech.rag.platform.infra.persistence.repository;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.fintech.rag.platform.domain.model.AppCredential;
import com.fintech.rag.platform.infra.persistence.mapper.AppCredentialMapper;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 应用凭证仓储。
 *
 * <p><b>为什么必须加缓存：</b>验签是每个内网请求的必经之路，
 * 若每次都查库，platform 的数据库会在高并发下率先成为瓶颈。
 * 缓存 TTL 5 分钟，密钥轮换时主动失效。</p>
 *
 * @author rag-platform
 */
@Repository
public class AppCredentialRepository {

    private final AppCredentialMapper mapper;

    public AppCredentialRepository(AppCredentialMapper mapper) {
        this.mapper = mapper;
    }

    /** 按 appId 查询生效中的凭证（支持轮换期多条并存，返回最新的） */
    @Cacheable(cacheNames = "platform:app-cred", key = "#appId", unless = "#result == null")
    public AppCredential findActive(String appId) {
        List<AppCredential> list = mapper.selectList(Wrappers.<AppCredential>lambdaQuery()
                .eq(AppCredential::getAppId, appId)
                .eq(AppCredential::getStatus, 1)
                .and(w -> w.isNull(AppCredential::getExpireAt)
                        .or().gt(AppCredential::getExpireAt, LocalDateTime.now()))
                .orderByDesc(AppCredential::getId));
        return list.isEmpty() ? null : list.get(0);
    }

    /** 凭证变更后必须主动失效缓存，否则最长 5 分钟内旧密钥仍然可用 */
    @CacheEvict(cacheNames = "platform:app-cred", key = "#appId")
    public void evict(String appId) {
        // 由 @CacheEvict 完成清理，方法体空实现
    }

    public int save(AppCredential credential) {
        return mapper.insert(credential);
    }
}
