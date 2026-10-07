package com.fintech.rag.chat.domain.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 消息引用（{@code t_message_citation}）。
 *
 * <p><b>为什么引用必须落库，而不是只返回给前端</b>：</p>
 * <ol>
 *   <li>合规：金融场景要求「答案可溯源」。前端页面刷新后引用就没了，
 *       但监管检查要的是「三个月前那条回答依据的是哪份文件的哪个版本」；</li>
 *   <li>回放：用户点踩时，要能立刻看到「当时引用了哪几段、分数多少」，
 *       才能判断是检索错还是生成错；</li>
 *   <li>文档版本关联：{@code version_no} 落库后才能识别「引用的是已过期版本」。</li>
 * </ol>
 *
 * <p><b>与回放的边界</b>：本表存片段原文（引用必须能原文比对），
 * 但回放接口默认<b>不返回</b> {@code content} —— 见 {@code ReplayAppService}。</p>
 *
 * @author rag-platform
 */
@Data
@TableName("t_message_citation")
public class MessageCitation {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    private Long messageId;

    /** 引用序号，对应回答正文中的 [seq] */
    private Integer seq;

    private Long kbId;

    private Long docId;

    private String docName;

    private Integer versionNo;

    /** RAGFlow 片段 ID，便于直接跳回原文定位 */
    private String ragflowChunkId;

    private Integer chunkIndex;

    /** 引用原文片段 */
    private String content;

    private BigDecimal score;

    private Integer pageNo;

    private LocalDateTime createTime;
}
