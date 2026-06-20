"""对话历史样本数据

提供多轮对话历史样本，供集成测试、E2E 测试与压测使用：
- 单对话多轮历史
- 多对话并存样本
- 不同 Agent 的消息样本
"""
from typing import Optional


# ===== 对话历史样本 =====
SAMPLE_CONVERSATIONS: list[dict] = [
    {
        "id": "conv_sample_001",
        "session_id": "sess_sample_001",
        "title": "GNN漏洞检测论题讨论",
        "agent_id": "orchestrator",
        "messages": [
            {
                "role": "user",
                "content": "我想研究图神经网络在代码漏洞检测中的应用，请帮我生成论题。",
                "agent_id": "",
                "reasoning": "",
            },
            {
                "role": "assistant",
                "content": "好的，我将为您启动五阶段流程。首先进行信息确权，检索近2年相关文献...",
                "agent_id": "orchestrator",
                "reasoning": "<think>用户研究方向为GNN+漏洞检测，启动五阶段流程。</think>",
            },
            {
                "role": "assistant",
                "content": "检索完成，找到以下相关文献：\n1. GNN for Vulnerability Detection (ACM CSUR 2024)\n2. Devign: Effective Vulnerability Identification (NeurIPS 2019)\n\n请确认信息无误后进入创意阶段。",
                "agent_id": "searcher",
                "reasoning": "<think>检索关键词：GNN, vulnerability detection。返回2篇核心文献。</think>",
                "citations": [
                    {"url": "https://dl.acm.org/doi/10.1145/3697.2024.001", "title": "GNN for Vulnerability Detection"},
                    {"url": "https://arxiv.org/abs/1909.03496", "title": "Devign"},
                ],
            },
            {
                "role": "user",
                "content": "信息确认无误，请继续。",
                "agent_id": "",
                "reasoning": "",
            },
            {
                "role": "assistant",
                "content": "基于四维创意引擎，生成以下候选论题：\n1. 基于图神经网络的代码漏洞检测方法研究\n2. 面向跨项目泛化的GNN漏洞检测框架\n3. 基于注意力机制的可解释漏洞检测",
                "agent_id": "reasoner",
                "reasoning": "<think>四维创意引擎：方法迁移、痛点突破、趋势前瞻、学科交叉。</think>",
            },
        ],
    },
    {
        "id": "conv_sample_002",
        "session_id": "sess_sample_001",
        "title": "LLM问答系统讨论",
        "agent_id": "orchestrator",
        "messages": [
            {
                "role": "user",
                "content": "我对大语言模型的领域问答系统感兴趣，能否帮我分析研究价值？",
                "agent_id": "",
                "reasoning": "",
            },
            {
                "role": "assistant",
                "content": "大语言模型在领域问答中面临三大挑战：幻觉、知识时效性、专业术语理解。"
                "RAG是当前主流解决方案，但仍存在检索精度不足、缓存命中率低等问题。"
                "您的研究方向具有显著的理论与实践价值。",
                "agent_id": "mentor",
                "reasoning": "<think>分析LLM领域问答的研究价值与挑战。</think>",
            },
            {
                "role": "user",
                "content": "请评估这个论题的可行性。",
                "agent_id": "",
                "reasoning": "",
            },
            {
                "role": "assistant",
                "content": "评估结果：\n- 新颖性：85分（RAG+知识图谱多跳检索组合较新）\n- 可行性：92分（技术栈成熟，数据集可用）\n- 综合评分：91分\n\n建议作为硕士论文选题。",
                "agent_id": "critic",
                "reasoning": "<think>从新颖性、可行性、综合评分三维度评估。</think>",
            },
        ],
    },
    {
        "id": "conv_sample_003",
        "session_id": "sess_sample_002",
        "title": "鲁迅小说研究",
        "agent_id": "orchestrator",
        "messages": [
            {
                "role": "user",
                "content": "我想研究鲁迅小说中的现代性焦虑叙事，请帮我梳理研究思路。",
                "agent_id": "",
                "reasoning": "",
            },
            {
                "role": "assistant",
                "content": "鲁迅小说的现代性焦虑叙事可从三个维度切入：\n1. 凝视结构（看/被看）中的权力焦虑\n2. 重复与延迟的叙事节奏中的心理焦虑\n3. 反讽与悖论的修辞策略中的认知焦虑\n\n建议采用叙事学+现代性理论的交叉视角。",
                "agent_id": "reasoner",
                "reasoning": "<think>从叙事学与现代性理论双重视角分析鲁迅小说。</think>",
            },
        ],
    },
]


# ===== 多轮对话样本 =====
SAMPLE_MULTI_TURN_DIALOGUES: list[dict] = [
    {
        "id": "dialogue_001",
        "title": "五阶段完整流程对话",
        "turns": [
            {"turn": 1, "role": "user", "content": "请帮我生成一个关于GNN漏洞检测的论题。"},
            {"turn": 2, "role": "assistant", "agent_id": "orchestrator",
             "content": "好的，启动五阶段流程。阶段1：信息确权，正在检索文献..."},
            {"turn": 3, "role": "assistant", "agent_id": "searcher",
             "content": "检索完成，找到3篇核心文献。请确认信息。"},
            {"turn": 4, "role": "user", "content": "确认无误，继续。"},
            {"turn": 5, "role": "assistant", "agent_id": "orchestrator",
             "content": "阶段2：创意，正在生成候选论题..."},
            {"turn": 6, "role": "assistant", "agent_id": "reasoner",
             "content": "生成4个候选论题，覆盖四维创意引擎。"},
            {"turn": 7, "role": "assistant", "agent_id": "orchestrator",
             "content": "阶段3：校验，正在评估候选论题..."},
            {"turn": 8, "role": "assistant", "agent_id": "critic",
             "content": "评估完成，平均评分84，通过门禁。推荐候选4。"},
            {"turn": 9, "role": "assistant", "agent_id": "orchestrator",
             "content": "阶段4：生成，正在生成开题内容..."},
            {"turn": 10, "role": "assistant", "agent_id": "writer",
             "content": "开题报告已生成，包含背景、现状、方法、计划等章节。"},
            {"turn": 11, "role": "assistant", "agent_id": "orchestrator",
             "content": "阶段5：深度辅助，可进入文献精读/实验预研/答辩模拟。"},
        ],
    },
    {
        "id": "dialogue_002",
        "title": "低评分回退对话",
        "turns": [
            {"turn": 1, "role": "user", "content": "请生成论题。"},
            {"turn": 2, "role": "assistant", "agent_id": "orchestrator",
             "content": "启动五阶段流程..."},
            {"turn": 3, "role": "assistant", "agent_id": "reasoner",
             "content": "生成4个候选论题。"},
            {"turn": 4, "role": "assistant", "agent_id": "critic",
             "content": "评估完成，平均评分45 < 60，回退到创意阶段。"},
            {"turn": 5, "role": "assistant", "agent_id": "orchestrator",
             "content": "评分不通过，重新生成候选论题..."},
            {"turn": 6, "role": "assistant", "agent_id": "reasoner",
             "content": "重新生成4个候选论题（已优化）。"},
            {"turn": 7, "role": "assistant", "agent_id": "critic",
             "content": "重新评估，平均评分78，通过门禁。"},
        ],
    },
    {
        "id": "dialogue_003",
        "title": "多Agent协作对话",
        "turns": [
            {"turn": 1, "role": "user", "content": "请从导师视角评估我的论题。"},
            {"turn": 2, "role": "assistant", "agent_id": "mentor",
             "content": "从导师视角看，论题具有创新性，但需注意实验设计的严谨性。"},
            {"turn": 3, "role": "user", "content": "请从批评者视角再评估一次。"},
            {"turn": 4, "role": "assistant", "agent_id": "critic",
             "content": "从批评者视角看，论题新颖性85分，可行性75分，建议加强可行性论证。"},
            {"turn": 5, "role": "user", "content": "请生成开题报告。"},
            {"turn": 6, "role": "assistant", "agent_id": "writer",
             "content": "开题报告已生成，已根据评估建议加强可行性分析章节。"},
        ],
    },
]


# ===== 不同 Agent 的消息样本 =====
SAMPLE_AGENT_MESSAGES: dict[str, list[dict]] = {
    "orchestrator": [
        {
            "role": "assistant",
            "content": "启动五阶段流程：信息确权 → 创意 → 校验 → 生成 → 深度辅助。",
            "reasoning": "<think>编排五阶段流程，按顺序调度子Agent。</think>",
        },
        {
            "role": "assistant",
            "content": "阶段1完成，进入阶段2：创意。",
            "reasoning": "<think>用户已确认信息，推进到创意阶段。</think>",
        },
        {
            "role": "assistant",
            "content": "所有阶段已完成，可进入深度辅助。",
            "reasoning": "<think>五阶段流程顺利完成。</think>",
        },
    ],
    "searcher": [
        {
            "role": "assistant",
            "content": "检索到5篇相关文献，按相关度排序：\n1. GNN for Vulnerability Detection\n2. Devign\n3. ReVeal",
            "reasoning": "<think>使用关键词检索，返回Top-5结果。</think>",
            "citations": [
                {"url": "https://dl.acm.org/doi/10.1145/3697.2024.001", "title": "GNN for Vulnerability Detection"},
                {"url": "https://arxiv.org/abs/1909.03496", "title": "Devign"},
            ],
        },
        {
            "role": "assistant",
            "content": "未找到完全匹配的文献，返回相关领域文献3篇。",
            "reasoning": "<think>关键词无精确匹配，扩展到相关领域。</think>",
        },
    ],
    "reasoner": [
        {
            "role": "assistant",
            "content": "基于四维创意引擎生成4个候选论题：\n1. 学科交叉维度\n2. 方法迁移维度\n3. 痛点突破维度\n4. 趋势前瞻维度",
            "reasoning": "<think>四维创意引擎：cross_discipline, method_transfer, pain_point_breakthrough, trend_forecast。</think>",
        },
        {
            "role": "assistant",
            "content": "重新生成候选论题（已根据评估反馈优化）。",
            "reasoning": "<think>评分不通过，根据Critic反馈优化候选。</think>",
        },
    ],
    "critic": [
        {
            "role": "assistant",
            "content": "评估结果：平均评分84，通过门禁。推荐候选4。",
            "reasoning": "<think>4个候选评分：82, 75, 88, 91。平均84 > 60，通过。</think>",
        },
        {
            "role": "assistant",
            "content": "评估结果：平均评分45 < 60，回退到创意阶段。",
            "reasoning": "<think>4个候选评分：42, 48, 50, 40。平均45 < 60，不通过。</think>",
        },
    ],
    "writer": [
        {
            "role": "assistant",
            "content": "# 开题报告\n\n## 一、选题背景\n...\n## 二、研究现状\n...\n## 三、研究内容\n...",
            "reasoning": "<think>按标准开题报告模板生成，包含7个章节。</think>",
        },
        {
            "role": "assistant",
            "content": "## 论题大纲\n1. 绪论\n2. 相关工作\n3. 方法设计\n4. 实验\n5. 总结",
            "reasoning": "<think>生成大纲粒度内容，5个章节。</think>",
        },
    ],
    "mentor": [
        {
            "role": "assistant",
            "content": "从导师视角看，论题具有创新性，但需注意：\n1. 实验设计需严谨\n2. 数据集选择需有代表性\n3. 与现有工作的对比需充分",
            "reasoning": "<think>导师视角关注研究的严谨性与可行性。</think>",
        },
        {
            "role": "assistant",
            "content": "建议在开题报告中加强可行性分析章节，明确实验资源与时间安排。",
            "reasoning": "<think>针对可行性不足的问题提出改进建议。</think>",
        },
    ],
}


def build_conversation_history(
    num_turns: int = 10,
    agent_id: str = "orchestrator",
) -> list[dict]:
    """构建指定轮数的对话历史

    Args:
        num_turns: 对话轮数（user+assistant 各算一轮）。
        agent_id: 助手消息的 Agent ID。

    Returns:
        对话消息列表，user 与 assistant 交替。
    """
    history = []
    user_messages = [
        "请帮我生成论题。",
        "请评估这个论题的可行性。",
        "请生成开题报告。",
        "请优化论题标题。",
        "请检查重复度。",
        "请生成大纲。",
        "请生成摘要。",
        "请提供参考文献。",
        "请评估创新性。",
        "请总结研究内容。",
    ]
    assistant_messages = SAMPLE_AGENT_MESSAGES.get(agent_id, SAMPLE_AGENT_MESSAGES["orchestrator"])

    for i in range(num_turns):
        history.append({
            "role": "user",
            "content": user_messages[i % len(user_messages)],
            "agent_id": "",
            "reasoning": "",
        })
        asst_msg = assistant_messages[i % len(assistant_messages)]
        history.append({
            "role": "assistant",
            "content": asst_msg["content"],
            "agent_id": agent_id,
            "reasoning": asst_msg.get("reasoning", ""),
        })
    return history


def get_conversation_by_id(conv_id: str) -> Optional[dict]:
    """按 ID 获取对话样本

    Args:
        conv_id: 对话 ID。

    Returns:
        匹配的对话字典；未找到时返回 None。
    """
    for conv in SAMPLE_CONVERSATIONS:
        if conv["id"] == conv_id:
            return conv
    return None


# 模块导入时断言样本数量满足要求
assert len(SAMPLE_CONVERSATIONS) >= 3, "对话样本不足3个"
assert len(SAMPLE_MULTI_TURN_DIALOGUES) >= 3, "多轮对话样本不足3个"
assert len(SAMPLE_AGENT_MESSAGES) >= 5, "Agent消息样本不足5种"
