"""DST 压缩器模块

将完整对话历史替换为压缩后的 DST 状态块，减少 token 用量。

当历史超过阈值（默认 5 轮）时，将早期历史替换为单个 DST 状态摘要消息，
仅保留最近 2 轮原始对话，从而保持 Prompt 前缀稳定并降低 token 消耗。
"""


def compact_history(history: list[dict], dst_state: dict) -> list[dict]:
    """将历史压缩为 DST 状态块。

    当历史超过 5 轮时，将早期历史替换为单个 DST 状态消息，
    仅保留最近 2 轮原始对话。

    Args:
        history: 原始对话历史。
        dst_state: DST 提取的状态字典。

    Returns:
        压缩后的历史列表（前缀稳定，token 减少）。
    """
    if not isinstance(history, list):
        return []

    # 历史不超过 5 条时无需压缩
    if len(history) <= 5:
        return history

    # 构建 DST 状态摘要消息
    dst_summary = _format_dst_state(dst_state)
    compressed_msg = {
        "role": "system",
        "content": f"[对话状态摘要]\n{dst_summary}",
    }

    # 保留最近 2 轮原始对话（user+assistant 各 1 条 = 4 条消息）
    recent = history[-4:]
    return [compressed_msg] + recent


def _format_dst_state(state: dict) -> str:
    """格式化 DST 状态为可读字符串。

    Args:
        state: DST 状态字典。

    Returns:
        格式化后的状态字符串。
    """
    if not state:
        return "对话轮数：0"

    lines = []
    if state.get("selected_topic"):
        lines.append(f"已选定论题：{state['selected_topic']}")
    if state.get("confirmed_methods"):
        lines.append(f"已确认方法：{', '.join(state['confirmed_methods'])}")
    if state.get("confirmed_discipline"):
        lines.append(f"已确认学科：{state['confirmed_discipline']}")
    if state.get("open_questions"):
        lines.append(f"待解决问题：{'; '.join(state['open_questions'])}")
    lines.append(f"对话轮数：{state.get('iteration_count', 0)}")
    return "\n".join(lines)
