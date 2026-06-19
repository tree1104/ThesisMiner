"""透明账本模块

记录每次 AI 调用的 token 用量与费用，提供明细查询与汇总统计。
所有记录持久化到 budget_ledger 表。
"""
import datetime
import uuid

from backend.database import execute_insert, fetch_all, fetch_one
from backend.budgets.estimator import estimate_cost


def record_usage(
    session_id: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    purpose: str,
    cached_tokens: int = 0,
) -> dict:
    """记录一次 AI 调用的用量与费用到 budget_ledger 表。

    Args:
        session_id: 关联的会话 ID。
        model: 调用使用的模型名称。
        prompt_tokens: 输入 token 数。
        completion_tokens: 输出 token 数。
        purpose: 调用用途（如 reasoner、mentor、inspire）。
        cached_tokens: 缓存命中的 prompt token 数（v7.0 新增）。

    Returns:
        写入的账本记录字典。
    """
    total_tokens = prompt_tokens + completion_tokens
    cost = estimate_cost(model, prompt_tokens, completion_tokens)
    now = datetime.datetime.now().isoformat()
    entry_id = uuid.uuid4().hex

    entry = {
        "id": entry_id,
        "session_id": session_id,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cached_prompt_tokens": cached_tokens,
        "cost": cost,
        "purpose": purpose,
        "created_at": now,
    }

    execute_insert("budget_ledger", entry)
    return entry


def get_ledger_entries(
    session_id: str = None, limit: int = 50, offset: int = 0
) -> list[dict]:
    """查询账本明细，可选按会话过滤，按创建时间降序。

    Args:
        session_id: 可选的会话 ID 过滤条件。
        limit: 返回条数上限，默认 50。
        offset: 偏移量，默认 0。

    Returns:
        账本记录字典列表。
    """
    if session_id:
        return fetch_all(
            "SELECT * FROM budget_ledger WHERE session_id = ? "
            "ORDER BY created_at DESC LIMIT ? OFFSET ?;",
            (session_id, limit, offset),
        )
    return fetch_all(
        "SELECT * FROM budget_ledger ORDER BY created_at DESC LIMIT ? OFFSET ?;",
        (limit, offset),
    )


def get_ledger_summary() -> dict:
    """汇总账本统计信息，包含三类 token 细分。

    包含总调用次数、总 token 数、总费用，以及按模型、按用途的分组统计。
    三类 token：input_cached（缓存命中输入）、input_uncached（未命中输入）、output（输出）。

    Returns:
        汇总字典：total_calls、total_tokens、total_cost、input_cached、
        input_uncached、output、by_model、by_purpose。
    """
    rows = fetch_all("SELECT * FROM budget_ledger;")

    total_calls = len(rows)
    total_tokens = sum(row.get("total_tokens", 0) for row in rows)
    total_cost = round(sum(row.get("cost", 0.0) for row in rows), 6)

    # 三类 token 统计（v7.0 新增）
    input_cached = sum(row.get("cached_prompt_tokens", 0) for row in rows)
    input_uncached = sum(
        row.get("prompt_tokens", 0) - row.get("cached_prompt_tokens", 0)
        for row in rows
    )
    output = sum(row.get("completion_tokens", 0) for row in rows)

    by_model: dict[str, dict] = {}
    by_purpose: dict[str, dict] = {}

    for row in rows:
        model = row.get("model", "unknown")
        purpose = row.get("purpose", "unknown")
        tokens = row.get("total_tokens", 0)
        cost = row.get("cost", 0.0)
        cached = row.get("cached_prompt_tokens", 0)
        uncached = row.get("prompt_tokens", 0) - cached
        output_tokens = row.get("completion_tokens", 0)

        # 按模型分组（含三类 token）
        if model not in by_model:
            by_model[model] = {
                "calls": 0, "tokens": 0, "cost": 0.0,
                "input_cached": 0, "input_uncached": 0, "output": 0,
            }
        by_model[model]["calls"] += 1
        by_model[model]["tokens"] += tokens
        by_model[model]["cost"] = round(by_model[model]["cost"] + cost, 6)
        by_model[model]["input_cached"] += cached
        by_model[model]["input_uncached"] += uncached
        by_model[model]["output"] += output_tokens

        # 按用途分组（含三类 token）
        if purpose not in by_purpose:
            by_purpose[purpose] = {
                "calls": 0, "tokens": 0, "cost": 0.0,
                "input_cached": 0, "input_uncached": 0, "output": 0,
            }
        by_purpose[purpose]["calls"] += 1
        by_purpose[purpose]["tokens"] += tokens
        by_purpose[purpose]["cost"] = round(by_purpose[purpose]["cost"] + cost, 6)
        by_purpose[purpose]["input_cached"] += cached
        by_purpose[purpose]["input_uncached"] += uncached
        by_purpose[purpose]["output"] += output_tokens

    return {
        "total_calls": total_calls,
        "total_tokens": total_tokens,
        "total_cost": total_cost,
        "input_cached": input_cached,
        "input_uncached": input_uncached,
        "output": output,
        "by_model": by_model,
        "by_purpose": by_purpose,
    }


def get_session_cost(session_id: str) -> dict:
    """查询指定会话的总费用统计，含三类 token 细分。

    Args:
        session_id: 会话唯一标识。

    Returns:
        会话费用字典：session_id、total_calls、total_tokens、total_cost、
        input_cached、input_uncached、output。
    """
    rows = fetch_all(
        "SELECT * FROM budget_ledger WHERE session_id = ?;", (session_id,)
    )

    total_calls = len(rows)
    total_tokens = sum(row.get("total_tokens", 0) for row in rows)
    total_cost = round(sum(row.get("cost", 0.0) for row in rows), 6)
    input_cached = sum(row.get("cached_prompt_tokens", 0) for row in rows)
    input_uncached = sum(
        row.get("prompt_tokens", 0) - row.get("cached_prompt_tokens", 0)
        for row in rows
    )
    output = sum(row.get("completion_tokens", 0) for row in rows)

    return {
        "session_id": session_id,
        "total_calls": total_calls,
        "total_tokens": total_tokens,
        "total_cost": total_cost,
        "input_cached": input_cached,
        "input_uncached": input_uncached,
        "output": output,
    }
