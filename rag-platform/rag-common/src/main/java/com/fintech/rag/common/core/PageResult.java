package com.fintech.rag.common.core;

import java.io.Serial;
import java.io.Serializable;
import java.util.Collections;
import java.util.List;

/**
 * 统一分页结构。
 *
 * @param <T> 记录类型
 * @author rag-platform
 */
public class PageResult<T> implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    /** 当前页数据 */
    private List<T> records = Collections.emptyList();

    /** 页码，从 1 开始 */
    private long pageNum = 1L;

    /** 每页条数 */
    private long pageSize = 20L;

    /** 总记录数 */
    private long total = 0L;

    /** 总页数 */
    private long pages = 0L;

    public static <T> PageResult<T> of(List<T> records, long pageNum, long pageSize, long total) {
        PageResult<T> result = new PageResult<>();
        result.setRecords(records == null ? Collections.emptyList() : records);
        result.setPageNum(pageNum);
        result.setPageSize(pageSize);
        result.setTotal(total);
        result.setPages(pageSize <= 0 ? 0 : (total + pageSize - 1) / pageSize);
        return result;
    }

    public static <T> PageResult<T> empty(long pageNum, long pageSize) {
        return of(Collections.emptyList(), pageNum, pageSize, 0L);
    }

    public List<T> getRecords() {
        return records;
    }

    public void setRecords(List<T> records) {
        this.records = records;
    }

    public long getPageNum() {
        return pageNum;
    }

    public void setPageNum(long pageNum) {
        this.pageNum = pageNum;
    }

    public long getPageSize() {
        return pageSize;
    }

    public void setPageSize(long pageSize) {
        this.pageSize = pageSize;
    }

    public long getTotal() {
        return total;
    }

    public void setTotal(long total) {
        this.total = total;
    }

    public long getPages() {
        return pages;
    }

    public void setPages(long pages) {
        this.pages = pages;
    }
}
