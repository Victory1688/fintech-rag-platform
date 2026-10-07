package com.fintech.rag.chat.app.prompt;

import com.fintech.rag.api.dto.retrieval.RetrievalResponse;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * Prompt 模板注册表。
 *
 * <p>模板集中管理而非散落在 Service 里，有两个实际好处：
 * 一是产品/业务人员可以参与文案评审；二是每次回答都记录 {@code promptVersion}，
 * 出问题时可复现「当时用的是哪一版提示词」。</p>
 *
 * @author rag-platform
 */
@Component
public class PromptTemplateRegistry {

    /** 模板版本号，随模板变更递增，落库到消息表便于问题复现 */
    public static final String VERSION = "v1.3";

    private static final String SYSTEM_TEMPLATE = """
            你是某银行信贷业务的知识助手，服务对象是本行客户经理、风控与合规人员。

            【最重要的规则】
            1. 只能依据下面「参考资料」中的内容作答，不得使用你自身的通用知识补充。
            2. 参考资料中没有的内容，必须明确回答「知识库中未找到相关规定」，并建议咨询对应管理部门。
            3. 每一个事实性结论后面必须标注引用编号，格式为 [1]、[2]，编号必须与参考资料一致。
            4. 涉及金额、利率、期限、次数等数值时，必须逐字引用原文，不得换算、不得四舍五入。
            5. 若不同参考资料存在冲突，必须指出冲突并分别标注来源，不得自行裁决。
            6. 不得给出授信审批结论或风险判断，只做制度与政策的检索与整理。
            7. 回答使用专业、简洁的书面语，分条陈述，不使用表情符号。

            【输出结构】
            - 先给结论（1~2 句）
            - 再分条列出依据（每条带引用编号）
            - 若存在例外条款或适用条件，单列一节说明
            """;

    private static final String USER_TEMPLATE = """
            参考资料：
            %s

            用户问题：%s
            """;

    /** 系统提示词 */
    public String systemPrompt() {
        return SYSTEM_TEMPLATE;
    }

    /** 组装用户提示词（含检索上下文） */
    public String userPrompt(String question, List<RetrievalResponse.Chunk> chunks) {
        StringBuilder context = new StringBuilder();
        int index = 1;
        for (RetrievalResponse.Chunk chunk : chunks) {
            context.append("[").append(index).append("] 来源：《")
                    .append(chunk.docName() == null ? "未知文档" : chunk.docName())
                    .append("》");
            if (chunk.versionNo() != null) {
                context.append("（第 ").append(chunk.versionNo()).append(" 版）");
            }
            if (chunk.pageNo() != null) {
                context.append(" 第 ").append(chunk.pageNo()).append(" 页");
            }
            context.append("\n").append(chunk.content()).append("\n\n");
            index++;
        }
        return String.format(USER_TEMPLATE, context, question);
    }

    /** 空召回时的兜底话术：不调用模型，直接返回 */
    public String noHitAnswer() {
        return "知识库中未找到与该问题相关的内容。建议：\n"
                + "1. 换用更具体的表述（例如加上产品名称、业务条线）重新提问；\n"
                + "2. 确认该内容是否已上传至本知识库；\n"
                + "3. 提交知识缺口反馈，我们会安排补录。";
    }

    /** 免责声明 */
    public String disclaimer() {
        return "以上内容由系统基于行内知识库自动生成，仅供参考，请以行内正式制度文件为准。";
    }
}
