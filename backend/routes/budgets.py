"""预算控制路由模块

提供账本明细查询、预算估算、汇总统计、会话费用与模型定价查询接口。
"""
from fastapi import APIRouter

from backend.budgets import estimator, transparent_ledger
from backend.models import BudgetEstimateRequest

router = APIRouter(prefix="/api/budgets", tags=["budgets"])


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
    """获取模型定价表。"""
    try:
        return estimator.MODEL_PRICING
    except Exception as e:
        return {"success": False, "error": str(e)}
