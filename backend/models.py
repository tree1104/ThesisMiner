"""Pydantic 数据模型定义

包含学位/学科枚举、论题提案模型、会话模型、各类请求/响应模型。
对应架构文档第3节的 AcademicThesisProposal 结构。
"""
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DegreeType(str, Enum):
    """学位类型枚举。"""

    master = "master"
    doctor = "doctor"


class DisciplineType(str, Enum):
    """学科类型枚举。"""

    humanities_social = "humanities_social"
    science_engineering = "science_engineering"


class ResearchSignificance(BaseModel):
    """研究意义：理论意义与实践意义。"""

    theoretical: str
    practical: str


class AcademicThesisProposal(BaseModel):
    """学术论题提案模型（对应架构文档第3节）。

    包含论题生成所需的核心字段，由 AI 生成并经自动改写流程处理。
    """

    title: str = Field(..., description="论题标题，限20字内")
    inspiration_source: str = Field(..., description="灵感来源")
    problem_awareness: str = Field(..., description="问题意识")
    research_significance: ResearchSignificance = Field(..., description="研究意义")
    literature_review_outline: str = Field(..., description="文献综述大纲")
    differentiation: str = Field(..., description="差异化/创新点")
    research_content: list[str] = Field(..., description="研究内容条目列表")
    feasibility_analysis: str = Field(..., description="可行性分析")
    confidence_score: float = Field(..., description="置信度评分")
    auto_rewritten: bool = Field(default=False, description="是否经过自动改写")


class SessionCreate(BaseModel):
    """创建会话请求。"""

    title: str
    degree: DegreeType
    discipline: DisciplineType
    mentor_info: str
    mode: str = "quick"


class SessionResponse(BaseModel):
    """会话响应模型。"""

    id: str
    title: str
    degree: str
    discipline: str
    mentor_info: str
    status: str
    created_at: str
    updated_at: str


class LineageNodeCreate(BaseModel):
    """学脉节点创建模型。"""

    node_type: str
    title: str
    abstract: str
    metadata: dict = Field(default_factory=dict)


class LineageImportRequest(BaseModel):
    """学脉批量导入请求：节点与边。"""

    nodes: list[dict]
    edges: list[dict]


class CreativityInspireRequest(BaseModel):
    """创意激发请求。"""

    degree: DegreeType
    discipline: DisciplineType
    mentor_info: str
    context: str = ""


class ProposalGenerateRequest(BaseModel):
    """论题生成请求。"""

    session_id: str | None = None
    degree: DegreeType
    discipline: DisciplineType
    mentor_info: str
    mode: str = "quick"
    count: int = 3


class ValidateTitleRequest(BaseModel):
    """论题标题校验请求。"""

    title: str
    degree: DegreeType


class CheckFeasibilityRequest(BaseModel):
    """可行性检查请求。"""

    research_content: list[str]
    degree: DegreeType
    timeframe_months: int


class BudgetEstimateRequest(BaseModel):
    """预算估算请求。"""

    degree: DegreeType
    mode: str = "quick"
    count: int = 3


class BudgetLedgerEntry(BaseModel):
    """预算账本条目。"""

    id: str
    session_id: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float
    purpose: str
    created_at: str


class ApiResponse(BaseModel):
    """通用 API 响应模型。"""

    success: bool
    data: Any | None = None
    error: str | None = None
    message: str | None = None


class ConfigUpdate(BaseModel):
    """配置更新请求。"""

    ai_api_key: str | None = None
    ai_base_url: str | None = None
    ai_model: str | None = None
