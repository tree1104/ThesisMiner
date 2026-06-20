"""AI 回复样本数据

提供各类 AI 回复样本，供集成测试、E2E 测试与压测使用：
- 含引用的 AI 回复（Markdown 链接、编号引用、裸 URL）
- 推理过程内容（reasoning_content）
- 流式分片（streaming chunks）
- 错误响应样本
"""
from typing import Optional


# ===== 含引用的 AI 回复样本 =====
SAMPLE_AI_RESPONSES: list[dict] = [
    {
        "id": "resp_001",
        "agent_id": "searcher",
        "content": (
            "根据您的研究方向，我检索到以下相关文献：\n\n"
            "1. Graph Neural Networks for Software Vulnerability Detection "
            "(https://dl.acm.org/doi/10.1145/3697.2024.001) - ACM Computing Surveys 2024\n\n"
            "2. Efficient Container Scheduling for Edge Computing "
            "(https://ieeexplore.ieee.org/document/tec2024) - IEEE TEC 2024\n\n"
            "3. [Retrieval-Augmented Generation for Domain QA]"
            "(https://aclanthology.org/2024.acl-long.003) - ACL 2024\n\n"
            "建议您重点关注第一篇综述，它系统梳理了GNN在漏洞检测中的应用。"
        ),
        "citations": [
            {
                "url": "https://dl.acm.org/doi/10.1145/3697.2024.001",
                "title": "Graph Neural Networks for Software Vulnerability Detection",
                "snippet": "A comprehensive survey of GNN-based vulnerability detection methods.",
                "source_domain": "dl.acm.org",
                "favicon": "https://www.google.com/s2/favicons?domain=dl.acm.org&sz=32",
            },
            {
                "url": "https://ieeexplore.ieee.org/document/tec2024",
                "title": "Efficient Container Scheduling for Edge Computing",
                "snippet": "Multi-agent RL framework for edge container scheduling.",
                "source_domain": "ieeexplore.ieee.org",
                "favicon": "https://www.google.com/s2/favicons?domain=ieeexplore.ieee.org&sz=32",
            },
            {
                "url": "https://aclanthology.org/2024.acl-long.003",
                "title": "Retrieval-Augmented Generation for Domain QA",
                "snippet": "RAG framework with three-stage prompt caching.",
                "source_domain": "aclanthology.org",
                "favicon": "https://www.google.com/s2/favicons?domain=aclanthology.org&sz=32",
            },
        ],
        "token_usage": {
            "prompt_tokens": 320,
            "completion_tokens": 180,
            "total_tokens": 500,
            "cached_tokens": 280,
        },
    },
    {
        "id": "resp_002",
        "agent_id": "reasoner",
        "content": (
            "基于四维创意引擎，我为您生成以下候选论题：\n\n"
            "```json\n"
            "{\n"
            '  "candidates": [\n'
            '    {"title": "基于图神经网络的代码漏洞检测方法研究", '
            '"dimension": "method_transfer", '
            '"rationale": "将GNN从社交网络迁移到代码分析领域"},\n'
            '    {"title": "面向边缘计算的轻量级容器调度算法研究", '
            '"dimension": "pain_point_breakthrough", '
            '"rationale": "解决边缘节点资源受限的调度痛点"},\n'
            '    {"title": "基于扩散模型的少样本图像生成与增强研究", '
            '"dimension": "trend_forecast", '
            '"rationale": "顺应扩散模型的前沿趋势"},\n'
            '    {"title": "基于大语言模型的领域知识问答系统研究", '
            '"dimension": "cross_discipline", '
            '"rationale": "将LLM与检索增强生成交叉融合"}\n'
            "  ]\n"
            "}\n"
            "```\n\n"
            "更多详情参考 https://arxiv.org/abs/2024.12345 与 "
            "https://github.com/thesisminer/examples"
        ),
        "citations": [
            {
                "url": "https://arxiv.org/abs/2024.12345",
                "title": "arXiv:2024.12345",
                "snippet": "Recent advances in graph neural networks for code analysis.",
                "source_domain": "arxiv.org",
                "favicon": "https://www.google.com/s2/favicons?domain=arxiv.org&sz=32",
            },
            {
                "url": "https://github.com/thesisminer/examples",
                "title": "thesisminer/examples",
                "snippet": "Open-source examples for thesis generation.",
                "source_domain": "github.com",
                "favicon": "https://www.google.com/s2/favicons?domain=github.com&sz=32",
            },
        ],
        "token_usage": {
            "prompt_tokens": 450,
            "completion_tokens": 320,
            "total_tokens": 770,
            "cached_tokens": 410,
        },
    },
    {
        "id": "resp_003",
        "agent_id": "critic",
        "content": (
            "对候选论题的评估结果如下：\n\n"
            "```json\n"
            "{\n"
            '  "evaluations": [\n'
            '    {"title": "基于图神经网络的代码漏洞检测方法研究", '
            '"score": 82, "novelty": 78, "feasibility": 85, '
            '"issues": ["数据集偏差可能导致泛化不足"], '
            '"suggestions": ["增加跨项目实验验证"]},\n'
            '    {"title": "面向边缘计算的轻量级容器调度算法研究", '
            '"score": 75, "novelty": 70, "feasibility": 80, '
            '"issues": ["实验场景较为单一"], '
            '"suggestions": ["扩展到多种边缘场景"]},\n'
            '    {"title": "基于扩散模型的少样本图像生成与增强研究", '
            '"score": 88, "novelty": 90, "feasibility": 75, '
            '"issues": ["计算资源需求较高"], '
            '"suggestions": ["设计轻量化模型变体"]},\n'
            '    {"title": "基于大语言模型的领域知识问答系统研究", '
            '"score": 91, "novelty": 85, "feasibility": 92, '
            '"issues": ["幻觉问题仍需解决"], '
            '"suggestions": ["引入自洽性投票机制"]}\n'
            "  ]\n"
            "}\n"
            "```\n\n"
            "平均评分 84，建议选择评分最高的「基于大语言模型的领域知识问答系统研究」。"
            "更多评估方法详见 https://example.com/eval-methods"
        ),
        "citations": [
            {
                "url": "https://example.com/eval-methods",
                "title": "Evaluation Methods for Thesis Topics",
                "snippet": "Comprehensive evaluation framework for research proposals.",
                "source_domain": "example.com",
                "favicon": "https://www.google.com/s2/favicons?domain=example.com&sz=32",
            },
        ],
        "token_usage": {
            "prompt_tokens": 580,
            "completion_tokens": 420,
            "total_tokens": 1000,
            "cached_tokens": 540,
        },
    },
    {
        "id": "resp_004",
        "agent_id": "writer",
        "content": (
            "# 基于大语言模型的领域知识问答系统研究\n\n"
            "## 一、选题背景与意义\n\n"
            "大语言模型（LLM）在通用问答任务上展现出卓越能力，"
            "但在专业领域仍存在幻觉、知识时效性差等问题。"
            "本研究面向垂直领域构建检索增强生成（RAG）问答系统，"
            "提出三段式提示缓存机制以降低API调用成本。\n\n"
            "## 二、研究内容\n\n"
            "1. 三段式提示缓存机制设计\n"
            "2. 基于知识图谱的多跳检索策略\n"
            "3. 基于自洽性投票的幻觉检测方法\n\n"
            "参考文档：\n"
            "[1] https://aclanthology.org/2024.acl-long.003\n"
            "[2] https://arxiv.org/abs/2024.56789\n"
            "[3] https://openreview.net/forum?id=rag2024"
        ),
        "citations": [
            {
                "url": "https://aclanthology.org/2024.acl-long.003",
                "title": "RAG for Domain QA",
                "snippet": "Retrieval-augmented generation framework.",
                "source_domain": "aclanthology.org",
                "favicon": "https://www.google.com/s2/favicons?domain=aclanthology.org&sz=32",
            },
            {
                "url": "https://arxiv.org/abs/2024.56789",
                "title": "arXiv:2024.56789",
                "snippet": "Knowledge graph enhanced retrieval.",
                "source_domain": "arxiv.org",
                "favicon": "https://www.google.com/s2/favicons?domain=arxiv.org&sz=32",
            },
            {
                "url": "https://openreview.net/forum?id=rag2024",
                "title": "OpenReview: RAG 2024",
                "snippet": "Hallucination detection in LLMs.",
                "source_domain": "openreview.net",
                "favicon": "https://www.google.com/s2/favicons?domain=openreview.net&sz=32",
            },
        ],
        "token_usage": {
            "prompt_tokens": 720,
            "completion_tokens": 580,
            "total_tokens": 1300,
            "cached_tokens": 680,
        },
    },
    {
        "id": "resp_005",
        "agent_id": "orchestrator",
        "content": (
            "五阶段流程已完成。可进入深度辅助：\n\n"
            "- 文献精读：https://thesisminer.cn/deep/literature\n"
            "- 实验预研：https://thesisminer.cn/deep/experiment\n"
            "- 答辩模拟：https://thesisminer.cn/deep/defense\n\n"
            "完整开题报告：https://thesisminer.cn/report/12345"
        ),
        "citations": [
            {
                "url": "https://thesisminer.cn/deep/literature",
                "title": "文献精读 - ThesisMiner",
                "snippet": "对选定文献进行深度解读。",
                "source_domain": "thesisminer.cn",
                "favicon": "https://www.google.com/s2/favicons?domain=thesisminer.cn&sz=32",
            },
            {
                "url": "https://thesisminer.cn/deep/experiment",
                "title": "实验预研 - ThesisMiner",
                "snippet": "梳理实验设计思路。",
                "source_domain": "thesisminer.cn",
                "favicon": "https://www.google.com/s2/favicons?domain=thesisminer.cn&sz=32",
            },
            {
                "url": "https://thesisminer.cn/deep/defense",
                "title": "答辩模拟 - ThesisMiner",
                "snippet": "模拟答辩问答场景。",
                "source_domain": "thesisminer.cn",
                "favicon": "https://www.google.com/s2/favicons?domain=thesisminer.cn&sz=32",
            },
            {
                "url": "https://thesisminer.cn/report/12345",
                "title": "开题报告 - ThesisMiner",
                "snippet": "完整开题报告文档。",
                "source_domain": "thesisminer.cn",
                "favicon": "https://www.google.com/s2/favicons?domain=thesisminer.cn&sz=32",
            },
        ],
        "token_usage": {
            "prompt_tokens": 200,
            "completion_tokens": 120,
            "total_tokens": 320,
            "cached_tokens": 180,
        },
    },
]


# ===== 推理过程内容样本 =====
SAMPLE_REASONING_CONTENT: list[dict] = [
    {
        "id": "reasoning_001",
        "agent_id": "reasoner",
        "reasoning": (
            "<think>\n"
            "用户研究方向是计算机科学，需要基于四维创意引擎生成候选论题。\n\n"
            "分析步骤：\n"
            "1. 学科交叉：将GNN从社交网络迁移到代码分析，形成新视角\n"
            "2. 方法迁移：将多智能体RL迁移到边缘容器调度\n"
            "3. 痛点突破：解决少样本场景下扩散模型训练困难\n"
            "4. 趋势前瞻：顺应LLM+RAG的前沿趋势\n\n"
            "结合近2年文献，避免与已有研究重复。\n"
            "每个维度生成1个候选，共4个候选。\n"
            "</think>"
        ),
    },
    {
        "id": "reasoning_002",
        "agent_id": "critic",
        "reasoning": (
            "<think>\n"
            "评估候选论题时需考虑：\n"
            "1. 新颖性：与已有文献的差异度\n"
            "2. 可行性：研究难度与资源匹配度\n"
            "3. 综合评分：加权平均\n\n"
            "对4个候选逐一评估：\n"
            "- 候选1：GNN漏洞检测，新颖性78，可行性85，综合82\n"
            "- 候选2：边缘调度，新颖性70，可行性80，综合75\n"
            "- 候选3：扩散模型，新颖性90，可行性75，综合88\n"
            "- 候选4：LLM问答，新颖性85，可行性92，综合91\n\n"
            "平均评分84 > 60，通过门禁。\n"
            "推荐候选4作为最佳论题。\n"
            "</think>"
        ),
    },
    {
        "id": "reasoning_003",
        "agent_id": "writer",
        "reasoning": (
            "<think>\n"
            "生成开题内容时需遵循以下结构：\n"
            "1. 选题背景与意义\n"
            "2. 国内外研究现状\n"
            "3. 研究内容与目标\n"
            "4. 研究方法与技术路线\n"
            "5. 预期成果与创新点\n"
            "6. 研究计划\n"
            "7. 参考文献\n\n"
            "针对LLM问答系统论题，重点突出：\n"
            "- 三段式提示缓存机制的创新性\n"
            "- 基于知识图谱的多跳检索策略\n"
            "- 自洽性投票的幻觉检测方法\n"
            "</think>"
        ),
    },
    {
        "id": "reasoning_004",
        "agent_id": "orchestrator",
        "reasoning": (
            "<think>\n"
            "五阶段流程编排：\n"
            "1. 信息确权：调用SearcherAgent检索近2年文献\n"
            "2. 创意：调用ReasonerAgent生成候选论题\n"
            "3. 校验：调用CriticAgent评估新颖性与可行性\n"
            "4. 生成：调用WriterAgent多粒度生成开题内容\n"
            "5. 深度辅助：提供文献精读/实验预研/答辩模拟入口\n\n"
            "门禁控制：\n"
            "- 信息确权需用户确认\n"
            "- 校验评分<60回退到创意\n"
            "- 生成内容为空则失败\n\n"
            "当前流程已顺利完成，可进入深度辅助阶段。\n"
            "</think>"
        ),
    },
]


# ===== 流式分片样本 =====
SAMPLE_STREAMING_CHUNKS: list[dict] = [
    {
        "id": "stream_001",
        "agent_id": "writer",
        "chunks": [
            {"type": "reasoning", "content": "<think>\n用户请求生成开题报告。"},
            {"type": "reasoning", "content": "首先分析论题背景..."},
            {"type": "reasoning", "content": "然后梳理研究现状..."},
            {"type": "reasoning", "content": "最后设计研究方案。\n</think>"},
            {"type": "content", "content": "# 基于大语言模型的领域知识问答系统研究\n\n"},
            {"type": "content", "content": "## 一、选题背景与意义\n\n"},
            {"type": "content", "content": "大语言模型（LLM）在通用问答任务上展现出卓越能力，"},
            {"type": "content", "content": "但在专业领域仍存在幻觉、知识时效性差等问题。"},
            {"type": "content", "content": "本研究面向垂直领域构建检索增强生成（RAG）问答系统，"},
            {"type": "content", "content": "提出三段式提示缓存机制以降低API调用成本。\n\n"},
            {"type": "content", "content": "## 二、研究内容\n\n"},
            {"type": "content", "content": "1. 三段式提示缓存机制设计\n"},
            {"type": "content", "content": "2. 基于知识图谱的多跳检索策略\n"},
            {"type": "content", "content": "3. 基于自洽性投票的幻觉检测方法\n"},
            {"type": "done", "content": ""},
        ],
    },
    {
        "id": "stream_002",
        "agent_id": "reasoner",
        "chunks": [
            {"type": "reasoning", "content": "<think>\n基于四维创意引擎生成候选论题。"},
            {"type": "reasoning", "content": "学科交叉维度：LLM+知识图谱\n</think>"},
            {"type": "content", "content": "```json\n"},
            {"type": "content", "content": "{\n  \"candidates\": [\n"},
            {"type": "content", "content": "    {\"title\": \"基于大语言模型的领域知识问答系统研究\", "},
            {"type": "content", "content": "\"dimension\": \"cross_discipline\", "},
            {"type": "content", "content": "\"rationale\": \"将LLM与检索增强生成交叉融合\"}\n"},
            {"type": "content", "content": "  ]\n}\n```\n"},
            {"type": "done", "content": ""},
        ],
    },
    {
        "id": "stream_003",
        "agent_id": "critic",
        "chunks": [
            {"type": "reasoning", "content": "<think>\n评估候选论题质量。"},
            {"type": "reasoning", "content": "新颖性、可行性、综合评分。\n</think>"},
            {"type": "content", "content": "评估结果：\n"},
            {"type": "content", "content": "- 候选1：评分82，新颖性78，可行性85\n"},
            {"type": "content", "content": "- 候选2：评分91，新颖性85，可行性92\n"},
            {"type": "content", "content": "推荐候选2作为最佳论题。"},
            {"type": "done", "content": ""},
        ],
    },
]


# ===== 错误响应样本 =====
SAMPLE_ERROR_RESPONSES: list[dict] = [
    {
        "id": "error_001",
        "error_type": "api_key_missing",
        "error_code": 401,
        "message": "API Key 未配置，请前往设置页完成配置",
        "details": {
            "configured": False,
            "hint": "在 .env 文件或设置页配置 ai_api_key",
        },
    },
    {
        "id": "error_002",
        "error_type": "rate_limit_exceeded",
        "error_code": 429,
        "message": "API 调用频率超限，请稍后重试",
        "details": {
            "retry_after": 60,
            "limit": 60,
            "window": "per_minute",
        },
    },
    {
        "id": "error_003",
        "error_type": "context_length_exceeded",
        "error_code": 400,
        "message": "上下文长度超出模型限制（32768 tokens）",
        "details": {
            "actual_tokens": 35120,
            "max_tokens": 32768,
            "hint": "请清空部分历史对话或开启DST压缩",
        },
    },
    {
        "id": "error_004",
        "error_type": "model_not_found",
        "error_code": 404,
        "message": "模型 'deepseek-v3' 不存在或未配置",
        "details": {
            "model_id": "deepseek-v3",
            "available_models": ["gpt-4o", "gpt-4o-mini", "deepseek-chat"],
        },
    },
    {
        "id": "error_005",
        "error_type": "network_timeout",
        "error_code": 504,
        "message": "AI 服务请求超时（30s）",
        "details": {
            "timeout": 30,
            "endpoint": "https://api.deepseek.com/v1/chat/completions",
            "hint": "请检查网络连接或增加超时时间",
        },
    },
    {
        "id": "error_006",
        "error_type": "json_parse_error",
        "error_code": 500,
        "message": "AI 返回内容无法解析为 JSON",
        "details": {
            "raw_content": "抱歉，我无法生成JSON格式的回复...",
            "hint": "请重试或调整提示词",
        },
    },
    {
        "id": "error_007",
        "error_type": "session_not_found",
        "error_code": 404,
        "message": "会话不存在或已被删除",
        "details": {
            "session_id": "abc123",
        },
    },
    {
        "id": "error_008",
        "error_type": "conversation_not_found",
        "error_code": 404,
        "message": "对话不存在或已被删除",
        "details": {
            "conversation_id": "xyz789",
        },
    },
]


def get_response_with_citations(agent_id: str = "searcher") -> dict:
    """获取指定 Agent 的含引用回复样本

    Args:
        agent_id: Agent 标识，如 searcher、reasoner、critic、writer、orchestrator。

    Returns:
        匹配的回复样本字典；未找到时返回第一个样本。
    """
    for resp in SAMPLE_AI_RESPONSES:
        if resp["agent_id"] == agent_id:
            return resp
    return SAMPLE_AI_RESPONSES[0]


def get_streaming_chunks(agent_id: str = "writer") -> list[dict]:
    """获取指定 Agent 的流式分片样本

    Args:
        agent_id: Agent 标识。

    Returns:
        流式分片列表；未找到时返回第一个样本的 chunks。
    """
    for stream in SAMPLE_STREAMING_CHUNKS:
        if stream["agent_id"] == agent_id:
            return stream["chunks"]
    return SAMPLE_STREAMING_CHUNKS[0]["chunks"]


def get_error_response(error_type: str) -> Optional[dict]:
    """按错误类型获取错误响应样本

    Args:
        error_type: 错误类型标识，如 api_key_missing、rate_limit_exceeded。

    Returns:
        匹配的错误响应字典；未找到时返回 None。
    """
    for err in SAMPLE_ERROR_RESPONSES:
        if err["error_type"] == error_type:
            return err
    return None


# 模块导入时断言样本数量满足要求
assert len(SAMPLE_AI_RESPONSES) >= 5, "AI 回复样本不足5个"
assert len(SAMPLE_REASONING_CONTENT) >= 4, "推理内容样本不足4个"
assert len(SAMPLE_STREAMING_CHUNKS) >= 3, "流式分片样本不足3个"
assert len(SAMPLE_ERROR_RESPONSES) >= 5, "错误响应样本不足5个"
