"""提示词模板模块

集中管理 Reasoner、Mentor、Inspire 三个角色的系统提示词与用户提示构建函数。
同时提供三段式 Prompt 构建器（不可变基础段 / 不可变画像段 / 动态尾部段）
与前缀哈希计算，用于 Prompt 缓存架构。
"""
import hashlib
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


# =============================================================================
# 三段式 Prompt 构建器（Task 5.1）
# 将 Prompt 拆分为不可变基础段、不可变画像段、动态尾部段，
# 用于 Prompt 缓存架构：前两段哈希稳定可缓存，第三段每轮变化。
# =============================================================================


def build_immutable_base() -> str:
    """构建不可变基础段：系统角色 + 硬约束（不随会话变化）。

    包含 Reasoner 角色定义、输出 JSON 格式要求、标题名词性短语约束等。
    该段内容在所有会话、所有轮次中完全相同，可作为缓存前缀的稳定部分。

    Returns:
        不可变基础段字符串。
    """
    return (
        "你是学术论题生成专家 Reasoner，负责生成直通开题报告的论题。\n"
        "硬约束：\n"
        "1. 必须输出 JSON 格式，包含字段：title、inspiration_source、"
        "problem_awareness、research_significance(含theoretical和practical)、"
        "literature_review_outline、differentiation、"
        "research_content(列表)、feasibility_analysis、confidence_score(0-1)。\n"
        "2. title 必须为限 20 字以内的名词性短语，不得以动词开头。\n"
        "3. confidence_score 取值范围 0-1。\n"
        "4. 严格按 JSON 格式输出，不要附加额外说明文字。"
    )


def build_immutable_profile(degree: str, discipline: str, mentor_info: str) -> str:
    """构建不可变画像段：学位 + 学科 + 导师信息（会话内不变）。

    同一会话内多次调用应返回完全相同的字符串，可作为缓存前缀的
    会话级稳定部分（与不可变基础段拼接后计算前缀哈希）。

    Args:
        degree: 学位类型（master / doctor）。
        discipline: 学科类型。
        mentor_info: 导师信息（研究方向、背景等）。

    Returns:
        不可变画像段字符串。
    """
    return (
        f"学位层次：{degree}\n"
        f"学科领域：{discipline}\n"
        f"导师信息：{mentor_info}"
    )


def build_dynamic_tail(query: str, dst_state: dict = None) -> str:
    """构建动态尾部段：当前查询 + DST 压缩状态。

    每轮对话不同，包含当前用户输入与压缩后的历史状态。
    该段不参与缓存前缀哈希计算。

    Args:
        query: 当前用户查询字符串。
        dst_state: 可选的 DST 状态字典，包含 selected_topic、
            confirmed_methods、confirmed_discipline、open_questions、
            iteration_count 等槽位。

    Returns:
        动态尾部段字符串。
    """
    parts = []
    if dst_state:
        # 格式化 DST 状态块
        dst_lines = _format_dst_block(dst_state)
        if dst_lines:
            parts.append("[DST 状态块]")
            parts.append(dst_lines)
    parts.append("[当前查询]")
    parts.append(query)
    return "\n".join(parts)


def _format_dst_block(state: dict) -> str:
    """将 DST 状态字典格式化为可读字符串（内部辅助函数）。

    Args:
        state: DST 状态字典。

    Returns:
        格式化后的状态字符串；状态为空时返回空字符串。
    """
    if not state:
        return ""
    lines = []
    if state.get("selected_topic"):
        lines.append(f"已选定论题：{state['selected_topic']}")
    if state.get("confirmed_methods"):
        lines.append(f"已确认方法：{', '.join(state['confirmed_methods'])}")
    if state.get("confirmed_discipline"):
        lines.append(f"已确认学科：{state['confirmed_discipline']}")
    if state.get("open_questions"):
        lines.append(f"待解决问题：{'; '.join(state['open_questions'])}")
    if state.get("iteration_count") is not None:
        lines.append(f"对话轮数：{state['iteration_count']}")
    return "\n".join(lines)


def compute_prefix_hash(base: str, profile: str) -> str:
    """计算前缀段的 SHA-256 哈希作为缓存标识。

    将 immutable_base 与 immutable_profile 拼接后取 SHA-256 前 16 位作为缓存 ID。
    同一会话内多次调用应返回相同哈希。

    Args:
        base: 不可变基础段字符串。
        profile: 不可变画像段字符串。

    Returns:
        16 字符长度的哈希字符串。
    """
    combined = base + "\n" + profile
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:16]


# =============================================================================
# 三段式 Prompt 缓存构建器（Task 2.2）
# 将系统角色 + 硬约束 + 学位/学科/导师信息拼接为不可变前缀，
# 仅尾部动态变化，确保 DeepSeek 缓存命中率 ≥95%。
# =============================================================================


def build_prompt_with_cache(
    system_role: str,
    hard_constraints: list[str],
    degree: str,
    discipline: str,
    advisor: str,
    dynamic_content: str,
) -> dict:
    """构建带缓存前缀的三段式 Prompt（Task 2.2）。

    将系统角色 + 硬约束 + 学位/学科/导师信息拼接为不可变前缀，
    仅尾部 dynamic_content 变化，确保同会话内 DeepSeek 缓存命中。

    Args:
        system_role: 系统角色描述（如"你是论文选题专家"）。
        hard_constraints: 硬约束列表（如["标题≤25字", "硕士1年内"]）。
        degree: 学位（master/doctor）。
        discipline: 学科领域。
        advisor: 导师方向。
        dynamic_content: 动态尾部文本（每轮变化）。

    Returns:
        包含 prefix / prefix_messages / dynamic / dynamic_messages 的字典：
            - prefix: 不可变前缀文本
            - prefix_messages: 不可变前缀消息列表（用于 messages 数组）
            - dynamic: 动态尾部文本
            - dynamic_messages: 动态尾部消息列表
    """
    # 构建固定前缀文本
    prefix_parts = [f"[SYSTEM_ROLE]\n{system_role}\n"]
    if hard_constraints:
        prefix_parts.append("[HARD_CONSTRAINTS]")
        for i, c in enumerate(hard_constraints, 1):
            prefix_parts.append(f"{i}. {c}")
        prefix_parts.append("")
    if degree or discipline or advisor:
        prefix_parts.append("[ACADEMIC_CONTEXT]")
        if degree:
            prefix_parts.append(f"学位: {degree}")
        if discipline:
            prefix_parts.append(f"学科: {discipline}")
        if advisor:
            prefix_parts.append(f"导师方向: {advisor}")
        prefix_parts.append("")

    prefix_text = "\n".join(prefix_parts)

    return {
        "prefix": prefix_text,
        "prefix_messages": [{"role": "system", "content": prefix_text}],
        "dynamic": dynamic_content,
        "dynamic_messages": [{"role": "user", "content": dynamic_content}],
    }
