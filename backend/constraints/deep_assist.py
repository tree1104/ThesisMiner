"""深度辅助三件套

1. 文献精读 - 深度解读指定文献
2. 实验预研 - 设计实验方案
3. 答辩模拟 - 模拟答辩问答
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DeepAssistResult:
    """深度辅助结果"""
    assist_type: str
    content: str
    suggestions: list[str]
    follow_up: list[str]


async def literature_reading(paper: dict, focus: str = "") -> DeepAssistResult:
    """文献精读

    Args:
        paper: 文献信息（title, abstract, authors, year等）
        focus: 重点关注方面（方法/结论/创新点）
    """
    try:
        from backend.ai.ai_proxy import call_llm
        from backend.config import get_step_model

        user_prompt = f"""请深度解读以下文献：
标题：{paper.get('title', '')}
作者：{paper.get('authors', '')}
年份：{paper.get('year', '')}
摘要：{paper.get('abstract', '')}

重点关注：{focus or '整体解读'}

请输出：
1. 研究问题与动机
2. 核心方法
3. 主要结论
4. 创新点与局限
5. 对本研究的启示
"""
        result = await call_llm(
            system_prompt="你是学术研究助手，请根据用户请求提供专业的文献精读辅助。",
            user_prompt=user_prompt,
            model=get_step_model("reasoner"),
            purpose="reasoner",
        )

        return DeepAssistResult(
            assist_type="literature_reading",
            content=result.get("content", ""),
            suggestions=["关注方法可复用部分", "注意样本量限制"],
            follow_up=["该方法是否适用于你的研究？", "如何改进其局限？"],
        )
    except Exception as e:
        return DeepAssistResult(
            assist_type="literature_reading",
            content=f"精读失败: {e}",
            suggestions=[],
            follow_up=[],
        )


async def experiment_preparation(topic: str, method: str = "") -> DeepAssistResult:
    """实验预研

    Args:
        topic: 研究论题
        method: 拟采用的方法
    """
    try:
        from backend.ai.ai_proxy import call_llm
        from backend.config import get_step_model

        user_prompt = f"""请为以下研究设计实验方案：
论题：{topic}
拟采用方法：{method or '待定'}

请输出：
1. 实验目标
2. 实验变量（自变量/因变量/控制变量）
3. 实验步骤
4. 数据采集方案
5. 评估指标
6. 预期结果与风险
"""
        result = await call_llm(
            system_prompt="你是学术研究助手，请根据用户请求设计专业的实验预研方案。",
            user_prompt=user_prompt,
            model=get_step_model("reasoner"),
            purpose="reasoner",
        )

        return DeepAssistResult(
            assist_type="experiment_preparation",
            content=result.get("content", ""),
            suggestions=["先做小规模预实验", "准备备选方案"],
            follow_up=["样本量是否足够？", "如何控制混杂变量？"],
        )
    except Exception as e:
        return DeepAssistResult(
            assist_type="experiment_preparation",
            content=f"预研失败: {e}",
            suggestions=[],
            follow_up=[],
        )


async def defense_simulation(topic: str, report_content: str = "") -> DeepAssistResult:
    """答辩模拟

    Args:
        topic: 研究论题
        report_content: 开题报告内容
    """
    try:
        from backend.ai.ai_proxy import call_llm
        from backend.config import get_step_model

        user_prompt = f"""请模拟开题答辩问答：
论题：{topic}
报告摘要：{report_content[:500] if report_content else '无'}

请生成：
1. 评委可能提出的5个关键问题（聚焦创新性/可行性/方法）
2. 每个问题的建议回答要点
3. 答辩注意事项
"""
        result = await call_llm(
            system_prompt="你是学术研究助手，请根据用户请求模拟专业的开题答辩问答。",
            user_prompt=user_prompt,
            model=get_step_model("mentor"),
            purpose="mentor",
        )

        return DeepAssistResult(
            assist_type="defense_simulation",
            content=result.get("content", ""),
            suggestions=["准备PPT要点", "练习时间控制"],
            follow_up=["如何应对方法质疑？", "如何突出创新点？"],
        )
    except Exception as e:
        return DeepAssistResult(
            assist_type="defense_simulation",
            content=f"模拟失败: {e}",
            suggestions=[],
            follow_up=[],
        )
