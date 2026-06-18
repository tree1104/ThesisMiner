"""提示词模板模块

集中管理 Reasoner、Mentor、Inspire 三个角色的系统提示词与用户提示构建函数。
"""
import json

# Reasoner 系统提示词：学术论题生成专家
REASONER_SYSTEM_PROMPT = (
    "你是学术论题生成专家 Reasoner，负责生成直通开题报告的论题。"
    "必须输出 JSON 格式，包含字段："
    "title(限20字内名词性短语)、inspiration_source、problem_awareness、"
    "research_significance(含theoretical和practical)、"
    "literature_review_outline、differentiation、"
    "research_content(列表)、feasibility_analysis、confidence_score(0-1)。"
)

# Mentor 系统提示词：导师视角的评审专家
MENTOR_SYSTEM_PROMPT = (
    "你是导师视角的评审专家，负责从可行性、创新性、学术规范角度评审论题。"
)

# Inspire 系统提示词：创意涌现引擎
INSPIRE_SYSTEM_PROMPT = "你是创意涌现引擎，负责生成有差异化的研究方向候选。"


def build_reasoner_prompt(
    degree: str, discipline: str, mentor_info: str, context: str = ""
) -> str:
    """构建 Reasoner 角色的用户提示。

    Args:
        degree: 学位类型（master / doctor）。
        discipline: 学科类型。
        mentor_info: 导师信息（研究方向、背景等）。
        context: 可选的上下文补充信息。

    Returns:
        拼接好的用户提示字符串。
    """
    parts = [
        f"学位层次：{degree}",
        f"学科领域：{discipline}",
        f"导师信息：{mentor_info}",
    ]
    if context:
        parts.append(f"上下文：{context}")
    parts.append("请基于以上信息生成一个直通开题报告的论题，严格按 JSON 格式输出。")
    return "\n".join(parts)


def build_mentor_prompt(proposal: dict) -> str:
    """构建 Mentor 角色的评审提示。

    Args:
        proposal: 论题提案字典。

    Returns:
        拼接好的评审提示字符串。
    """
    proposal_text = json.dumps(proposal, ensure_ascii=False, indent=2)
    return (
        "请评审以下论题提案，从可行性、创新性、学术规范三个角度给出意见与评分：\n"
        f"{proposal_text}"
    )


def build_inspire_prompt(discipline: str, topic: str, context: str = "") -> str:
    """构建 Inspire 角色的创意激发提示。

    Args:
        discipline: 学科类型。
        topic: 当前主题或种子方向。
        context: 可选的上下文补充信息。

    Returns:
        拼接好的创意激发提示字符串。
    """
    parts = [
        f"学科领域：{discipline}",
        f"当前主题：{topic}",
    ]
    if context:
        parts.append(f"上下文：{context}")
    parts.append("请生成若干有差异化的研究方向候选。")
    return "\n".join(parts)
