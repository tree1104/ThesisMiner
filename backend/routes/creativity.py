"""创意引擎路由模块

提供创意激发、跨域联想、趋势嫁接与候选排序接口。
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.creativity import academic_lineage, candidate_ranker, cross_domain
from backend.models import ApiResponse, CreativityInspireRequest
from backend.orchestration.hooks import pre_search

router = APIRouter(prefix="/api/creativity", tags=["creativity"])


class CrossDomainRequest(BaseModel):
    """跨域联想请求。"""

    domain_a: str
    domain_b: str


class TrendGraftRequest(BaseModel):
    """趋势嫁接请求。"""

    keywords: list[str] = Field(default_factory=list)


class RankRequest(BaseModel):
    """候选排序请求。"""

    candidates: list[dict] = Field(default_factory=list)
    degree: str = "master"


@router.post("/inspire")
def inspire(payload: CreativityInspireRequest):
    """激发创意候选，整合学术谱系、问题意识与跨域联想。"""
    try:
        result = pre_search.run(
            degree=payload.degree.value,
            discipline=payload.discipline.value,
            mentor_info=payload.mentor_info,
            context=payload.context,
        )
        return {
            "candidates": result.get("candidates", []),
            "problem_awareness": result.get("problem_awareness"),
            "context_enriched": result.get("context_enriched"),
        }
    except Exception as e:
        return ApiResponse(success=False, error=str(e))


@router.post("/cross-domain")
def cross_domain_association(payload: CrossDomainRequest):
    """跨域联想：将领域 A 的成熟方法嫁接至领域 B 的未解问题。"""
    try:
        result = cross_domain.cross_domain_association(
            domain_a=payload.domain_a, domain_b=payload.domain_b
        )
        return result
    except Exception as e:
        return ApiResponse(success=False, error=str(e))


@router.post("/trend-graft")
def trend_grafting(payload: TrendGraftRequest):
    """趋势嫁接：基于近期高频术语进行语义组合。"""
    try:
        result = cross_domain.trend_grafting(keywords=payload.keywords)
        return result
    except Exception as e:
        return ApiResponse(success=False, error=str(e))


@router.post("/rank")
def rank_candidates(payload: RankRequest):
    """候选排序：基于灵感来源权重打分并按分数降序排序。"""
    try:
        ranked = candidate_ranker.rank_candidates(
            candidates=payload.candidates, degree=payload.degree
        )
        return {"ranked_candidates": ranked, "count": len(ranked)}
    except Exception as e:
        return ApiResponse(success=False, error=str(e))


@router.get("/candidates")
def get_candidates(
    degree: str = "master",
    discipline: str = "humanities_social",
    mentor_info: str = "",
):
    """获取示例候选：解析导师信息并生成谱系候选。"""
    try:
        # 复用 pre_search 中既有的导师信息解析逻辑，分离导师项目与同门论文
        mentor_projects, senior_theses = pre_search._parse_mentor_info(mentor_info)
        candidates = academic_lineage.generate_lineage_candidates(
            mentor_projects, senior_theses
        )
        return {"candidates": candidates}
    except Exception as e:
        return ApiResponse(success=False, error=str(e))
