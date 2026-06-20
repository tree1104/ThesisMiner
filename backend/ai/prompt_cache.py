"""三段式 Prompt 缓存前缀构建模块

DeepSeek 缓存要求前缀字节级一致。本模块将系统角色 + 硬约束 + 学位/学科/导师信息
拼接为不可变前缀，仅尾部动态变化，确保同会话内缓存命中率 ≥95%。
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CachedPrefix:
    """缓存前缀数据结构"""
    prefix: str           # 不可变前缀文本
    prefix_messages: list  # 不可变前缀消息列表（用于 messages 数组）
    dynamic: str          # 动态尾部文本
    prefix_char_count: int


def build_cached_prefix(
    system_role: str,
    hard_constraints: list[str],
    degree: str = "",
    discipline: str = "",
    advisor: str = "",
) -> CachedPrefix:
    """构建三段式缓存前缀

    Args:
        system_role: 系统角色描述（如"你是论文选题专家"）
        hard_constraints: 硬约束列表（如["标题≤25字", "硕士1年内"]）
        degree: 学位（master/doctor）
        discipline: 学科领域
        advisor: 导师方向

    Returns:
        CachedPrefix 对象，prefix 部分在会话内字节级一致
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

    return CachedPrefix(
        prefix=prefix_text,
        prefix_messages=[{"role": "system", "content": prefix_text}],
        dynamic="",  # 由调用方填充
        prefix_char_count=len(prefix_text.encode("utf-8")),
    )


def is_deepseek_model(model_id: str) -> bool:
    """判断是否为 DeepSeek 模型（需应用缓存优化）"""
    return "deepseek" in model_id.lower()
