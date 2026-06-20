"""DeepSeek 缓存命中率监控

记录每次 DeepSeek 调用的缓存命中情况，并提供最近 N 次调用的统计信息。
缓存命中率 = cached_tokens / prompt_tokens，目标 ≥95%。
"""
from backend.database import get_db_connection


def record_cache_hit(
    model_id: str,
    prompt_tokens: int,
    cached_tokens: int,
    ledger_id: int = None,
) -> None:
    """记录单次调用的缓存命中情况。

    Args:
        model_id: 模型 ID（用于判断是否 DeepSeek）。
        prompt_tokens: 本次调用的 prompt token 数。
        cached_tokens: 缓存命中的 prompt token 数。
        ledger_id: 可选的 budget_ledger 记录 ID，提供时更新该行的 cache_hit_rate。
    """
    if prompt_tokens <= 0:
        return
    hit_rate = cached_tokens / prompt_tokens
    if ledger_id:
        conn = get_db_connection()
        try:
            conn.execute(
                "UPDATE budget_ledger SET cache_hit_rate = ? WHERE id = ?",
                (hit_rate, ledger_id),
            )
            conn.commit()
        finally:
            conn.close()


def get_cache_stats(limit: int = 100) -> dict:
    """获取最近 N 次 DeepSeek 调用的缓存命中率统计。

    Args:
        limit: 统计的最近调用条数，默认 100。

    Returns:
        统计字典：avg_hit_rate / total_calls / total_cached / total_prompt /
        overall_hit_rate。无数据时返回零值字典。
    """
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """SELECT cache_hit_rate, prompt_tokens, cached_prompt_tokens
               FROM budget_ledger
               WHERE cache_hit_rate > 0
               ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        if not rows:
            return {
                "avg_hit_rate": 0.0,
                "total_calls": 0,
                "total_cached": 0,
                "total_prompt": 0,
            }
        rates = [r[0] for r in rows]
        total_cached = sum(r[2] for r in rows)
        total_prompt = sum(r[1] for r in rows)
        return {
            "avg_hit_rate": sum(rates) / len(rates),
            "total_calls": len(rows),
            "total_cached": total_cached,
            "total_prompt": total_prompt,
            "overall_hit_rate": total_cached / total_prompt if total_prompt > 0 else 0.0,
        }
    finally:
        conn.close()


def verify_cache_hit_rate(messages: list[dict]) -> float:
    """验证压缩后的消息布局是否达到 ≥95% 缓存命中率。

    与 smart_compact 协同：压缩后的历史进入三段式 Prompt 缓存的
    稳定前缀（cached），仅最近 N 轮进入动态尾部（not cached）。
    本函数按字符数估算稳定前缀占总上下文的比例，作为缓存命中率的
    近似估计。

    稳定前缀 = 系统消息 + DST 状态消息 + 带 "[compressed]" 标记的压缩消息
    动态尾部 = 其余消息（最近 N 轮原始对话）

    Args:
        messages: 压缩后的消息列表（smart_compact 的输出）。

    Returns:
        估算的缓存命中率（0.0 ~ 1.0）。空消息列表返回 0.0。
    """
    if not isinstance(messages, list) or not messages:
        return 0.0

    total_chars = 0
    stable_chars = 0
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content", "")
        if not isinstance(content, str):
            content = str(content)
        msg_len = len(content)
        total_chars += msg_len
        # 系统消息、DST 状态消息、压缩消息均属于稳定前缀
        metadata = msg.get("metadata") or {}
        is_dst = isinstance(metadata, dict) and metadata.get("is_dst_state")
        if (
            msg.get("role") == "system"
            or is_dst
            or content.startswith("[compressed]")
        ):
            stable_chars += msg_len

    if total_chars <= 0:
        return 0.0
    return stable_chars / total_chars
