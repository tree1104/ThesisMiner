"""预算控制路由模块

提供账本明细查询、预算估算、汇总统计、会话费用与模型定价查询接口。
v8.0 新增 DeepSeek 缓存命中率统计接口（Task 2.6）。
"""
from fastapi import APIRouter

from backend.ai import cache_monitor
from backend.budgets import estimator, transparent_ledger
from backend.models import BudgetEstimateRequest

router = APIRouter(prefix="/api/budgets", tags=["budgets"])

# Task 2.6：缓存统计路由（无前缀，路径为 /api/cache-stats）
cache_stats_router = APIRouter(tags=["cache"])


def _enum_to_str(value) -> str:
    """将枚举值转换为字符串，非枚举则直接转为字符串。"""
    return value.value if hasattr(value, "value") else str(value)


@router.get("/ledger")
async def get_ledger(
    session_id: str = None, limit: int = 50, offset: int = 0
) -> dict:
    """获取账本明细，可选按会话过滤。"""
    try:
        entries = transparent_ledger.get_ledger_entries(session_id, limit, offset)
        return {
            "entries": entries,
            "count": len(entries),
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/estimate")
async def estimate_budget(req: BudgetEstimateRequest) -> dict:
    """估算会话级预算。"""
    try:
        degree = _enum_to_str(req.degree)
        result = estimator.estimate_session_budget(degree, req.mode, req.count)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/summary")
async def get_summary() -> dict:
    """获取账本汇总统计。"""
    try:
        return transparent_ledger.get_ledger_summary()
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/session/{session_id}")
async def get_session_cost(session_id: str) -> dict:
    """获取指定会话的费用统计。"""
    try:
        return transparent_ledger.get_session_cost(session_id)
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/pricing")
async def get_pricing() -> dict:
    """获取模型定价表（从模型注册表读取）。"""
    try:
        from backend.config import get_settings

        settings = get_settings()
        # 返回模型注册表中的定价信息
        pricing = {}
        for model in settings.models:
            pricing[model["id"]] = {
                "label": model.get("label", model["id"]),
                "input_cny_per_million": model.get("pricing", {}).get("input_cny_per_million", 0),
                "output_cny_per_million": model.get("pricing", {}).get("output_cny_per_million", 0),
                "currency": "CNY",
            }
        return {
            "pricing": pricing,
            "currency": settings.currency,
            "unit": "元/百万 token" if settings.currency == "CNY" else "USD/百万 token",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@cache_stats_router.get("/api/cache-stats")
async def get_cache_stats() -> dict:
    """获取 DeepSeek 缓存命中率统计（Task 2.6）。

    返回最近 100 次调用的平均命中率、总调用数、总缓存 token 数、
    总 prompt token 数与整体命中率。
    """
    try:
        return cache_monitor.get_cache_stats()
    except Exception as e:
        return {"success": False, "error": str(e)}
