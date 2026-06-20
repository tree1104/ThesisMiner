"""约束校验路由模块

提供标题格式校验、可行性校验、文献基线校验，
以及学术日历与文献基线的查询接口。

v6.0 增强：集成真实文献检索，支持热插拔与降级机制。
新增 search-literature 与 search-status 端点。
"""
from fastapi import APIRouter
from pydantic import BaseModel

from backend.agents.searcher_wrapper import get_searcher
from backend.config import get_settings
from backend.constraints import academic_calendar, format_validator, lit_baselines
from backend.models import CheckFeasibilityRequest, DegreeType, ValidateTitleRequest

router = APIRouter(prefix="/api/constraints", tags=["constraints"])


class CheckLiteratureRequest(BaseModel):
    """文献基线校验请求。"""

    degree: DegreeType
    count: int
    # v6.0: 可选关键词，提供时使用真实检索估算文献数量
    keyword: str | None = None


class SearchLiteratureRequest(BaseModel):
    """文献检索请求（v6.0 新增）。"""

    keyword: str
    count: int = 10
    degree: DegreeType | None = None


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
    """校验文献数量是否达到基线要求。

    v6.0: 集成检索器工厂。若提供 keyword，则使用检索器估算真实文献数量
    并据此校验；否则沿用请求中的 count（保持向后兼容）。
    """
    try:
        degree = _enum_to_str(req.degree)
        searcher = get_searcher()

        # 提供关键词时使用检索器估算真实文献数量
        if req.keyword:
            est_result = await searcher.estimate_literature_count(req.keyword)
            actual_count = est_result["count"]
            search_degraded = est_result.get("search_degraded", False)
        else:
            actual_count = req.count
            search_degraded = False

        result = lit_baselines.check_literature_count(degree, actual_count)
        result["search_degraded"] = search_degraded
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/search-literature")
async def search_literature(req: SearchLiteratureRequest) -> dict:
    """真实文献检索（v6.0 新增）。

    根据关键词检索相关文献，返回真实结果；当真实检索不可用或失败时，
    自动降级为模拟结果并附加 search_degraded 标记。
    """
    try:
        searcher = get_searcher()
        result = await searcher.search_and_summarize(req.keyword, req.count)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/search-status")
async def search_status() -> dict:
    """查询真实文献检索状态（v6.0 新增）。"""
    try:
        settings = get_settings()
        configured = bool(
            settings.search_api_keys.get("arxiv")
            or settings.search_api_keys.get("semantic_scholar")
        )
        return {
            "real_search_enabled": settings.real_search_enabled,
            "configured": configured,
        }
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
