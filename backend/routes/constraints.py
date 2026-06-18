"""约束校验路由模块

提供标题格式校验、可行性校验、文献基线校验，
以及学术日历与文献基线的查询接口。
"""
from fastapi import APIRouter
from pydantic import BaseModel

from backend.constraints import academic_calendar, format_validator, lit_baselines
from backend.models import CheckFeasibilityRequest, DegreeType, ValidateTitleRequest

router = APIRouter(prefix="/api/constraints", tags=["constraints"])


class CheckLiteratureRequest(BaseModel):
    """文献基线校验请求。"""

    degree: DegreeType
    count: int


def _enum_to_str(value) -> str:
    """将枚举值转换为字符串，非枚举则直接转为字符串。"""
    return value.value if hasattr(value, "value") else str(value)


@router.post("/validate-title")
async def validate_title(req: ValidateTitleRequest) -> dict:
    """校验标题格式并自动重写。"""
    try:
        result = format_validator.validate_and_rewrite(req.title)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/check-feasibility")
async def check_feasibility(req: CheckFeasibilityRequest) -> dict:
    """校验研究周期可行性。"""
    try:
        degree = _enum_to_str(req.degree)
        result = academic_calendar.validate_timeframe(degree, req.timeframe_months)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/check-literature")
async def check_literature(req: CheckLiteratureRequest) -> dict:
    """校验文献数量是否达到基线要求。"""
    try:
        degree = _enum_to_str(req.degree)
        result = lit_baselines.check_literature_count(degree, req.count)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/calendar/{degree}")
async def get_calendar(degree: str) -> dict:
    """获取指定学位的学术日历信息。"""
    try:
        return academic_calendar.get_calendar(degree)
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/baseline/{degree}")
async def get_baseline(degree: str) -> dict:
    """获取指定学位的文献基线。"""
    try:
        baseline = lit_baselines.get_baseline(degree)
        return {"degree": degree, "baseline": baseline}
    except Exception as e:
        return {"success": False, "error": str(e)}
