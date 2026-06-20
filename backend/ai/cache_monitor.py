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
