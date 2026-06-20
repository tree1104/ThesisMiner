"""研究规划器模块

提供完整的研究规划能力，包括：
    - 研究计划生成、阶段划分、时间线、里程碑
    - 资源分配、风险评估、应急预案
    - 研究方法选择、数据收集与分析计划
    - 进度跟踪、计划调整、完成度评估
    - 多学科研究规划、跨领域协作规划
    - 完整的规划模板、评估算法

设计原则：
    1. 零外部依赖：仅使用 Python 标准库
    2. 线程安全：所有公共方法通过 RLock 保护
    3. 可持久化：基于 dataclass，支持序列化
    4. 可扩展：阶段、方法、模板均可动态扩展

核心数据结构：
    - ResearchPlan: 研究计划（含阶段、资源、风险、方法等）
    - ResearchPhase: 研究阶段（含任务、时间、产出）
    - RiskAssessment: 风险评估（含风险项、概率、影响、应对）
    - ResourceAllocation: 资源分配（含人力、设备、经费、时间）
"""
from __future__ import annotations

import math
import re
import threading
import uuid
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Any, Iterable, Optional


# ===== 常量定义 =====

# 默认研究阶段模板（覆盖学位论文全生命周期）
DEFAULT_PHASE_TEMPLATES = [
    {
        "id": "phase_literature",
        "name": "文献综述与选题",
        "description": "系统检索与梳理相关文献，明确研究空白，确定研究问题与假设。",
        "default_weight": 0.15,
        "default_duration_days": 30,
        "key_activities": [
            "确定检索关键词与数据库",
            "系统检索并筛选文献",
            "撰写文献综述初稿",
            "识别研究空白",
            "凝练研究问题",
            "形成研究假设",
        ],
        "deliverables": [
            "文献综述报告",
            "研究问题清单",
            "研究假设陈述",
        ],
    },
    {
        "id": "phase_design",
        "name": "研究设计与方法",
        "description": "确定研究框架、变量、方法、样本与数据来源。",
        "default_weight": 0.15,
        "default_duration_days": 25,
        "key_activities": [
            "构建概念框架",
            "确定变量与操作化定义",
            "选择研究方法",
            "设计抽样方案",
            "确定数据来源",
            "制定分析计划",
        ],
        "deliverables": [
            "研究设计方案",
            "变量操作化表",
            "抽样方案",
            "数据分析计划",
        ],
    },
    {
        "id": "phase_data",
        "name": "数据收集",
        "description": "按设计方案收集一手/二手数据，确保数据质量。",
        "default_weight": 0.25,
        "default_duration_days": 45,
        "key_activities": [
            "准备数据收集工具",
            "预测试与工具修订",
            "正式数据收集",
            "数据清洗与编码",
            "数据质量检查",
            "数据归档",
        ],
        "deliverables": [
            "原始数据集",
            "清洗后数据集",
            "数据字典",
            "数据质量报告",
        ],
    },
    {
        "id": "phase_analysis",
        "name": "数据分析",
        "description": "按分析计划进行统计分析或质性分析，验证假设。",
        "default_weight": 0.20,
        "default_duration_days": 35,
        "key_activities": [
            "描述性统计分析",
            "推断性统计分析",
            "假设检验",
            "稳健性检验",
            "质性资料编码（如适用）",
            "结果可视化",
        ],
        "deliverables": [
            "分析结果报告",
            "统计图表",
            "假设检验结论",
        ],
    },
    {
        "id": "phase_writing",
        "name": "论文撰写",
        "description": "撰写论文各章节，形成完整初稿。",
        "default_weight": 0.15,
        "default_duration_days": 30,
        "key_activities": [
            "撰写引言",
            "撰写文献综述章节",
            "撰写研究方法章节",
            "撰写结果章节",
            "撰写讨论章节",
            "撰写结论与展望",
        ],
        "deliverables": [
            "论文初稿",
            "章节写作清单",
        ],
    },
    {
        "id": "phase_revision",
        "name": "修改与完善",
        "description": "根据导师与评审意见修改论文，完善格式与引用。",
        "default_weight": 0.10,
        "default_duration_days": 20,
        "key_activities": [
            "导师审阅反馈",
            "修改内容与结构",
            "完善引用与格式",
            "查重与降重",
            "语言润色",
        ],
        "deliverables": [
            "论文修改稿",
            "查重报告",
            "修改说明",
        ],
    },
]

# 学位类型对应总周期（天）
DEGREE_DURATION_DAYS = {
    "bachelor": 180,   # 本科毕设约 6 个月
    "master": 365,     # 硕士约 1 年
    "phd": 1095,       # 博士约 3 年
    "postdoc": 730,    # 博后约 2 年
}

# 学位中文名
DEGREE_NAMES = {
    "bachelor": "本科毕业论文",
    "master": "硕士学位论文",
    "phd": "博士学位论文",
    "postdoc": "博士后出站报告",
}

# 研究方法分类（与 method_library 对齐）
METHOD_CATEGORIES = {
    "quantitative": "定量方法",
    "qualitative": "定性方法",
    "mixed": "混合方法",
    "theoretical": "理论方法",
    "empirical": "经验方法",
}

# 风险等级阈值（按概率×影响得分）
RISK_THRESHOLDS = {
    "critical": 0.7,   # 关键风险
    "high": 0.5,       # 高风险
    "medium": 0.3,     # 中风险
    "low": 0.0,        # 低风险
}

# 风险等级中文名
RISK_LEVEL_NAMES = {
    "critical": "关键",
    "high": "高",
    "medium": "中",
    "low": "低",
}

# 资源类型
RESOURCE_TYPES = {
    "human": "人力资源",
    "equipment": "设备资源",
    "funding": "经费资源",
    "data": "数据资源",
    "software": "软件资源",
    "time": "时间资源",
}

# 完成度评估权重（各阶段默认权重）
COMPLETION_WEIGHTS = {
    "phase_literature": 0.15,
    "phase_design": 0.15,
    "phase_data": 0.25,
    "phase_analysis": 0.20,
    "phase_writing": 0.15,
    "phase_revision": 0.10,
}

# 多学科协作模式
COLLABORATION_MODES = {
    "interdisciplinary": "跨学科合作（不同学科研究者共同参与）",
    "multidisciplinary": "多学科并列（各学科独立研究后整合）",
    "transdisciplinary": "超学科融合（整合形成新框架）",
    "cross_domain": "跨领域借鉴（方法/理论迁移）",
}


# ===== 数据结构 =====


@dataclass
class ResearchPhase:
    """研究阶段数据结构。

    Attributes:
        id: 阶段唯一标识。
        name: 阶段名称。
        description: 阶段描述。
        weight: 阶段权重（用于完成度计算，0-1）。
        start_date: 开始日期（ISO 格式）。
        end_date: 结束日期（ISO 格式）。
        duration_days: 持续天数。
        key_activities: 关键活动列表。
        deliverables: 产出物列表。
        progress: 完成进度（0-100）。
        status: 状态（pending/in_progress/completed/blocked）。
        dependencies: 依赖阶段 ID 列表。
        assigned_to: 负责人。
        metadata: 扩展元数据。
    """

    id: str = ""
    name: str = ""
    description: str = ""
    weight: float = 0.0
    start_date: str = ""
    end_date: str = ""
    duration_days: int = 0
    key_activities: list[str] = field(default_factory=list)
    deliverables: list[str] = field(default_factory=list)
    progress: float = 0.0
    status: str = "pending"
    dependencies: list[str] = field(default_factory=list)
    assigned_to: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResearchPhase":
        """从字典构造阶段实例。"""
        defaults = cls().__dict__
        merged = {**defaults, **{k: v for k, v in data.items() if k in defaults}}
        return cls(**merged)

    def is_overdue(self, reference_date: Optional[str] = None) -> bool:
        """判断阶段是否逾期。

        Args:
            reference_date: 参考日期（ISO 格式），默认为当前日期。

        Returns:
            是否逾期。
        """
        if not self.end_date:
            return False
        ref = reference_date or datetime.now().strftime("%Y-%m-%d")
        return ref > self.end_date and self.status != "completed"

    def expected_progress(self, reference_date: Optional[str] = None) -> float:
        """根据时间推算预期进度（0-100）。

        Args:
            reference_date: 参考日期，默认为当前日期。

        Returns:
            预期进度百分比。
        """
        if not self.start_date or not self.end_date:
            return 0.0
        ref = reference_date or datetime.now().strftime("%Y-%m-%d")
        try:
            start = datetime.strptime(self.start_date, "%Y-%m-%d")
            end = datetime.strptime(self.end_date, "%Y-%m-%d")
            now = datetime.strptime(ref, "%Y-%m-%d")
        except ValueError:
            return 0.0
        if now <= start:
            return 0.0
        if now >= end:
            return 100.0
        total = (end - start).days
        elapsed = (now - start).days
        if total <= 0:
            return 100.0
        return round(elapsed / total * 100, 2)


@dataclass
class RiskItem:
    """风险项数据结构。

    Attributes:
        id: 风险 ID。
        description: 风险描述。
        category: 风险类别（technical/schedule/resource/external/ethical）。
        probability: 发生概率（0-1）。
        impact: 影响程度（0-1）。
        mitigation: 缓解措施。
        contingency: 应急预案。
        owner: 责任人。
        status: 状态（identified/mitigating/resolved/occurred）。
        trigger: 触发条件。
    """

    id: str = ""
    description: str = ""
    category: str = "technical"
    probability: float = 0.0
    impact: float = 0.0
    mitigation: str = ""
    contingency: str = ""
    owner: str = ""
    status: str = "identified"
    trigger: str = ""

    @property
    def score(self) -> float:
        """风险得分 = 概率 × 影响。"""
        return round(self.probability * self.impact, 4)

    @property
    def level(self) -> str:
        """风险等级。"""
        s = self.score
        if s >= RISK_THRESHOLDS["critical"]:
            return "critical"
        if s >= RISK_THRESHOLDS["high"]:
            return "high"
        if s >= RISK_THRESHOLDS["medium"]:
            return "medium"
        return "low"

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        d = asdict(self)
        d["score"] = self.score
        d["level"] = self.level
        return d


@dataclass
class RiskAssessment:
    """风险评估数据结构。

    Attributes:
        risks: 风险项列表。
        overall_level: 总体风险等级。
        summary: 评估摘要。
        assessment_date: 评估日期。
    """

    risks: list[RiskItem] = field(default_factory=list)
    overall_level: str = "low"
    summary: str = ""
    assessment_date: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "risks": [r.to_dict() for r in self.risks],
            "overall_level": self.overall_level,
            "summary": self.summary,
            "assessment_date": self.assessment_date,
        }


@dataclass
class ResourceAllocation:
    """资源分配数据结构。

    Attributes:
        resource_type: 资源类型。
        description: 资源描述。
        amount: 数量。
        unit: 单位。
        cost: 成本。
        source: 来源。
        phase_id: 关联阶段 ID。
        metadata: 扩展元数据。
    """

    resource_type: str = "human"
    description: str = ""
    amount: float = 0.0
    unit: str = ""
    cost: float = 0.0
    source: str = ""
    phase_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return asdict(self)


@dataclass
class DataCollectionPlan:
    """数据收集计划数据结构。

    Attributes:
        data_type: 数据类型（primary/secondary/tertiary）。
        source: 数据来源。
        method: 收集方法。
        sample_size: 样本量。
        sampling: 抽样方案。
        frequency: 收集频率。
        quality_control: 质量控制措施。
        ethical_considerations: 伦理考量。
        storage: 存储方案。
        timeline: 时间安排。
    """

    data_type: str = "primary"
    source: str = ""
    method: str = ""
    sample_size: int = 0
    sampling: str = ""
    frequency: str = ""
    quality_control: list[str] = field(default_factory=list)
    ethical_considerations: list[str] = field(default_factory=list)
    storage: str = ""
    timeline: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return asdict(self)


@dataclass
class AnalysisPlan:
    """分析计划数据结构。

    Attributes:
        analysis_type: 分析类型（descriptive/inferential/exploratory/confirmatory）。
        methods: 分析方法列表。
        software: 软件工具。
        variables: 变量列表。
        hypotheses: 待检验假设列表。
        significance_level: 显著性水平。
        power: 检验功效。
        robustness_checks: 稳健性检验列表。
        visualization: 可视化方案。
    """

    analysis_type: str = "inferential"
    methods: list[str] = field(default_factory=list)
    software: list[str] = field(default_factory=list)
    variables: list[str] = field(default_factory=list)
    hypotheses: list[str] = field(default_factory=list)
    significance_level: float = 0.05
    power: float = 0.8
    robustness_checks: list[str] = field(default_factory=list)
    visualization: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return asdict(self)


@dataclass
class ResearchPlan:
    """研究计划数据结构。

    Attributes:
        id: 计划 ID。
        title: 研究标题。
        degree: 学位类型。
        discipline: 学科代码。
        research_question: 研究问题。
        hypotheses: 研究假设列表。
        phases: 研究阶段列表。
        resources: 资源分配列表。
        risks: 风险评估。
        data_plan: 数据收集计划。
        analysis_plan: 分析计划。
        start_date: 计划开始日期。
        end_date: 计划结束日期。
        collaborators: 协作者列表。
        created_at: 创建时间。
        updated_at: 更新时间。
        metadata: 扩展元数据。
    """

    id: str = ""
    title: str = ""
    degree: str = "master"
    discipline: str = ""
    research_question: str = ""
    hypotheses: list[str] = field(default_factory=list)
    phases: list[ResearchPhase] = field(default_factory=list)
    resources: list[ResourceAllocation] = field(default_factory=list)
    risks: RiskAssessment = field(default_factory=RiskAssessment)
    data_plan: Optional[DataCollectionPlan] = None
    analysis_plan: Optional[AnalysisPlan] = None
    start_date: str = ""
    end_date: str = ""
    collaborators: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "id": self.id,
            "title": self.title,
            "degree": self.degree,
            "discipline": self.discipline,
            "research_question": self.research_question,
            "hypotheses": self.hypotheses,
            "phases": [p.to_dict() for p in self.phases],
            "resources": [r.to_dict() for r in self.resources],
            "risks": self.risks.to_dict(),
            "data_plan": self.data_plan.to_dict() if self.data_plan else None,
            "analysis_plan": self.analysis_plan.to_dict() if self.analysis_plan else None,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "collaborators": self.collaborators,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResearchPlan":
        """从字典构造计划实例。"""
        plan = cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            degree=data.get("degree", "master"),
            discipline=data.get("discipline", ""),
            research_question=data.get("research_question", ""),
            hypotheses=data.get("hypotheses", []),
            start_date=data.get("start_date", ""),
            end_date=data.get("end_date", ""),
            collaborators=data.get("collaborators", []),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            metadata=data.get("metadata", {}),
        )
        plan.phases = [ResearchPhase.from_dict(p) for p in data.get("phases", [])]
        plan.resources = [ResourceAllocation(**r) for r in data.get("resources", [])]
        risk_data = data.get("risks", {})
        plan.risks = RiskAssessment(
            risks=[RiskItem(**rk) for rk in risk_data.get("risks", [])],
            overall_level=risk_data.get("overall_level", "low"),
            summary=risk_data.get("summary", ""),
            assessment_date=risk_data.get("assessment_date", ""),
        )
        dp = data.get("data_plan")
        if dp:
            plan.data_plan = DataCollectionPlan(**dp)
        ap = data.get("analysis_plan")
        if ap:
            plan.analysis_plan = AnalysisPlan(**ap)
        return plan


# ===== 主类实现 =====


class ResearchPlanner:
    """研究规划器主类。

    提供研究计划生成、阶段划分、时间线、里程碑、资源分配、风险评估、
    方法选择、数据收集与分析计划、进度跟踪、计划调整、完成度评估、
    多学科研究规划、跨领域协作规划等能力。

    线程安全：所有公共方法通过 RLock 保护。
    """

    def __init__(self, default_degree: str = "master"):
        """初始化研究规划器。

        Args:
            default_degree: 默认学位类型。
        """
        self._lock = threading.RLock()
        self._plans: dict[str, ResearchPlan] = {}
        self._default_degree = default_degree
        # 历史计划用于基准对比
        self._history: list[dict[str, Any]] = []

    # ===== 计划创建 =====

    def create_plan(
        self,
        title: str,
        degree: str = "",
        discipline: str = "",
        research_question: str = "",
        hypotheses: Optional[list[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        total_duration_days: Optional[int] = None,
    ) -> ResearchPlan:
        """创建研究计划。

        根据学位类型与时间范围自动生成默认阶段、资源、风险评估框架。

        Args:
            title: 研究标题。
            degree: 学位类型（bachelor/master/phd/postdoc）。
            discipline: 学科代码。
            research_question: 研究问题。
            hypotheses: 研究假设列表。
            start_date: 开始日期（ISO 格式），默认今天。
            end_date: 结束日期（ISO 格式），默认按学位周期推算。
            total_duration_days: 总周期天数（覆盖 end_date）。

        Returns:
            创建的 ResearchPlan 实例。
        """
        with self._lock:
            degree = degree or self._default_degree
            if degree not in DEGREE_DURATION_DAYS:
                raise ValueError(f"不支持的学位类型: {degree}")

            # 确定起止时间
            start = datetime.strptime(start_date, "%Y-%m-%d") if start_date else datetime.now()
            if end_date:
                end = datetime.strptime(end_date, "%Y-%m-%d")
            elif total_duration_days:
                end = start + timedelta(days=total_duration_days)
            else:
                end = start + timedelta(days=DEGREE_DURATION_DAYS[degree])

            plan_id = f"plan_{uuid.uuid4().hex[:12]}"
            plan = ResearchPlan(
                id=plan_id,
                title=title,
                degree=degree,
                discipline=discipline,
                research_question=research_question,
                hypotheses=hypotheses or [],
                start_date=start.strftime("%Y-%m-%d"),
                end_date=end.strftime("%Y-%m-%d"),
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
            )

            # 生成默认阶段
            plan.phases = self._generate_default_phases(start, end, degree)
            # 生成默认资源分配
            plan.resources = self._generate_default_resources(plan.phases, degree)
            # 生成默认风险评估
            plan.risks = self._generate_default_risks(plan.phases, degree)
            # 生成默认数据收集计划
            plan.data_plan = self._generate_default_data_plan(plan.phases)
            # 生成默认分析计划
            plan.analysis_plan = self._generate_default_analysis_plan(hypotheses or [])

            self._plans[plan_id] = plan
            return plan

    def _generate_default_phases(
        self, start: datetime, end: datetime, degree: str
    ) -> list[ResearchPhase]:
        """根据时间范围与学位类型生成默认阶段。

        Args:
            start: 计划开始时间。
            end: 计划结束时间。
            degree: 学位类型。

        Returns:
            研究阶段列表。
        """
        total_days = (end - start).days
        if total_days <= 0:
            raise ValueError("计划结束日期必须晚于开始日期")

        phases: list[ResearchPhase] = []
        current = start
        for tpl in DEFAULT_PHASE_TEMPLATES:
            # 按权重分配天数
            duration = max(5, int(total_days * tpl["default_weight"]))
            phase_end = min(current + timedelta(days=duration), end)
            phase = ResearchPhase(
                id=tpl["id"],
                name=tpl["name"],
                description=tpl["description"],
                weight=tpl["default_weight"],
                start_date=current.strftime("%Y-%m-%d"),
                end_date=phase_end.strftime("%Y-%m-%d"),
                duration_days=(phase_end - current).days,
                key_activities=list(tpl["key_activities"]),
                deliverables=list(tpl["deliverables"]),
                progress=0.0,
                status="pending",
            )
            phases.append(phase)
            current = phase_end + timedelta(days=1)
            if current >= end:
                break

        # 设置阶段依赖
        for i, phase in enumerate(phases):
            if i > 0:
                phase.dependencies = [phases[i - 1].id]

        return phases

    def _generate_default_resources(
        self, phases: list[ResearchPhase], degree: str
    ) -> list[ResourceAllocation]:
        """生成默认资源分配。

        Args:
            phases: 研究阶段列表。
            degree: 学位类型。

        Returns:
            资源分配列表。
        """
        resources: list[ResourceAllocation] = []
        # 人力资源
        resources.append(ResourceAllocation(
            resource_type="human",
            description="主研究者（学生）",
            amount=1.0,
            unit="人",
            cost=0.0,
            source="学生本人",
            phase_id="",
        ))
        resources.append(ResourceAllocation(
            resource_type="human",
            description="指导教师",
            amount=1.0,
            unit="人",
            cost=0.0,
            source="学院指派",
            phase_id="",
        ))
        # 经费资源（按学位差异）
        funding_amount = {"bachelor": 500, "master": 3000, "phd": 15000, "postdoc": 50000}
        resources.append(ResourceAllocation(
            resource_type="funding",
            description="研究经费",
            amount=float(funding_amount.get(degree, 2000)),
            unit="元",
            cost=float(funding_amount.get(degree, 2000)),
            source="学院/导师课题",
            phase_id="phase_data",
        ))
        # 软件资源
        resources.append(ResourceAllocation(
            resource_type="software",
            description="统计分析软件",
            amount=1.0,
            unit="套",
            cost=0.0,
            source="学校授权",
            phase_id="phase_analysis",
        ))
        # 数据资源
        resources.append(ResourceAllocation(
            resource_type="data",
            description="数据库访问权限",
            amount=1.0,
            unit="项",
            cost=0.0,
            source="图书馆/数据平台",
            phase_id="phase_data",
        ))
        # 设备资源
        resources.append(ResourceAllocation(
            resource_type="equipment",
            description="实验设备/计算资源",
            amount=1.0,
            unit="套",
            cost=0.0,
            source="实验室",
            phase_id="phase_data",
        ))
        return resources

    def _generate_default_risks(
        self, phases: list[ResearchPhase], degree: str
    ) -> RiskAssessment:
        """生成默认风险评估。

        Args:
            phases: 研究阶段列表。
            degree: 学位类型。

        Returns:
            风险评估实例。
        """
        risks: list[RiskItem] = []
        # 数据收集风险
        risks.append(RiskItem(
            id="risk_data_collection",
            description="数据收集困难，样本量不足或回收率低",
            category="resource",
            probability=0.4,
            impact=0.7,
            mitigation="提前联系样本来源，准备备用抽样方案，提高激励",
            contingency="启用备用数据源或缩减研究范围，改用二手数据",
            owner="主研究者",
            status="identified",
            trigger="回收率低于 50% 或样本量低于设计要求 80%",
        ))
        # 时间风险
        risks.append(RiskItem(
            id="risk_schedule",
            description="研究进度滞后，关键阶段延期",
            category="schedule",
            probability=0.5,
            impact=0.6,
            mitigation="设置阶段里程碑，每周复盘进度，预留缓冲时间",
            contingency="压缩后续阶段或调整研究范围",
            owner="主研究者",
            status="identified",
            trigger="阶段进度落后预期 2 周以上",
        ))
        # 技术风险
        risks.append(RiskItem(
            id="risk_technical",
            description="分析方法不熟练，结果不可靠",
            category="technical",
            probability=0.3,
            impact=0.6,
            mitigation="提前学习相关方法，请教导师与同行，做预分析",
            contingency="简化分析方案或寻求统计咨询",
            owner="主研究者",
            status="identified",
            trigger="分析结果异常或无法解释",
        ))
        # 外部风险
        risks.append(RiskItem(
            id="risk_external",
            description="外部环境变化（政策、疫情、合作方退出）",
            category="external",
            probability=0.2,
            impact=0.8,
            mitigation="建立多方合作，准备替代方案，关注政策动态",
            contingency="调整研究对象或数据来源",
            owner="导师",
            status="identified",
            trigger="合作方退出或政策重大调整",
        ))
        # 伦理风险
        risks.append(RiskItem(
            id="risk_ethical",
            description="伦理审查未通过或数据隐私问题",
            category="ethical",
            probability=0.15,
            impact=0.9,
            mitigation="提前提交伦理审查，做好知情同意与数据脱敏",
            contingency="修改研究设计以符合伦理要求",
            owner="导师",
            status="identified",
            trigger="伦理委员会要求修改或拒绝批准",
        ))

        # 计算总体风险等级
        scores = [r.score for r in risks]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        if avg_score >= RISK_THRESHOLDS["critical"]:
            overall = "critical"
        elif avg_score >= RISK_THRESHOLDS["high"]:
            overall = "high"
        elif avg_score >= RISK_THRESHOLDS["medium"]:
            overall = "medium"
        else:
            overall = "low"

        return RiskAssessment(
            risks=risks,
            overall_level=overall,
            summary=f"共识别 {len(risks)} 项风险，总体风险等级：{RISK_LEVEL_NAMES[overall]}",
            assessment_date=datetime.now().strftime("%Y-%m-%d"),
        )

    def _generate_default_data_plan(
        self, phases: list[ResearchPhase]
    ) -> DataCollectionPlan:
        """生成默认数据收集计划。

        Args:
            phases: 研究阶段列表。

        Returns:
            数据收集计划实例。
        """
        return DataCollectionPlan(
            data_type="primary",
            source="待确定（问卷/访谈/实验/档案）",
            method="待确定",
            sample_size=0,
            sampling="待确定（随机/分层/便利）",
            frequency="一次性收集",
            quality_control=[
                "预测试工具",
                "双录入校验",
                "逻辑检查与异常值处理",
                "缺失值处理方案",
            ],
            ethical_considerations=[
                "知情同意",
                "数据匿名化",
                "保密存储",
                "伦理审查申请",
            ],
            storage="加密存储于本地+云端备份",
            timeline=phases[2].start_date if len(phases) > 2 else "",
        )

    def _generate_default_analysis_plan(
        self, hypotheses: list[str]
    ) -> AnalysisPlan:
        """生成默认分析计划。

        Args:
            hypotheses: 研究假设列表。

        Returns:
            分析计划实例。
        """
        return AnalysisPlan(
            analysis_type="inferential",
            methods=["描述统计", "相关分析", "回归分析", "假设检验"],
            software=["SPSS", "R", "Python"],
            variables=["自变量", "因变量", "控制变量"],
            hypotheses=list(hypotheses),
            significance_level=0.05,
            power=0.8,
            robustness_checks=[
                "替换样本子集",
                "替换估计方法",
                "加入遗漏变量",
                "工具变量法（如适用）",
            ],
            visualization="表格 + 图形（散点/箱线/系数图）",
        )

    # ===== 计划查询 =====

    def get_plan(self, plan_id: str) -> Optional[ResearchPlan]:
        """获取研究计划。

        Args:
            plan_id: 计划 ID。

        Returns:
            计划实例，不存在返回 None。
        """
        with self._lock:
            return self._plans.get(plan_id)

    def list_plans(self) -> list[ResearchPlan]:
        """列出所有研究计划。"""
        with self._lock:
            return list(self._plans.values())

    def delete_plan(self, plan_id: str) -> bool:
        """删除研究计划。

        Args:
            plan_id: 计划 ID。

        Returns:
            是否删除成功。
        """
        with self._lock:
            if plan_id in self._plans:
                # 存入历史用于基准对比
                plan = self._plans[plan_id]
                self._history.append({
                    "plan_id": plan_id,
                    "title": plan.title,
                    "degree": plan.degree,
                    "completion": self.compute_completion(plan),
                    "deleted_at": datetime.now().isoformat(),
                })
                del self._plans[plan_id]
                return True
            return False

    # ===== 阶段管理 =====

    def add_phase(
        self,
        plan_id: str,
        name: str,
        description: str = "",
        weight: float = 0.1,
        duration_days: int = 14,
        key_activities: Optional[list[str]] = None,
        deliverables: Optional[list[str]] = None,
        dependencies: Optional[list[str]] = None,
    ) -> Optional[ResearchPhase]:
        """向计划添加自定义阶段。

        Args:
            plan_id: 计划 ID。
            name: 阶段名称。
            description: 阶段描述。
            weight: 阶段权重。
            duration_days: 持续天数。
            key_activities: 关键活动列表。
            deliverables: 产出物列表。
            dependencies: 依赖阶段 ID 列表。

        Returns:
            创建的阶段实例，计划不存在返回 None。
        """
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan:
                return None
            # 计算起始日期：上一阶段结束 + 1
            if plan.phases:
                last_end = datetime.strptime(plan.phases[-1].end_date, "%Y-%m-%d")
                start = last_end + timedelta(days=1)
            else:
                start = datetime.strptime(plan.start_date, "%Y-%m-%d")
            end = start + timedelta(days=duration_days)
            phase = ResearchPhase(
                id=f"phase_custom_{uuid.uuid4().hex[:8]}",
                name=name,
                description=description,
                weight=weight,
                start_date=start.strftime("%Y-%m-%d"),
                end_date=end.strftime("%Y-%m-%d"),
                duration_days=duration_days,
                key_activities=key_activities or [],
                deliverables=deliverables or [],
                dependencies=dependencies or [],
            )
            plan.phases.append(phase)
            plan.updated_at = datetime.now().isoformat()
            return phase

    def update_phase_progress(
        self, plan_id: str, phase_id: str, progress: float, status: Optional[str] = None
    ) -> bool:
        """更新阶段进度。

        Args:
            plan_id: 计划 ID。
            phase_id: 阶段 ID。
            progress: 进度（0-100）。
            status: 新状态（可选）。

        Returns:
            是否更新成功。
        """
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan:
                return False
            for phase in plan.phases:
                if phase.id == phase_id:
                    phase.progress = max(0.0, min(100.0, float(progress)))
                    if status:
                        phase.status = status
                    # 进度达 100 自动标记完成
                    if phase.progress >= 100.0 and not status:
                        phase.status = "completed"
                    plan.updated_at = datetime.now().isoformat()
                    return True
            return False

    def reorder_phases(self, plan_id: str, phase_ids: list[str]) -> bool:
        """重排阶段顺序。

        Args:
            plan_id: 计划 ID。
            phase_ids: 按新顺序排列的阶段 ID 列表。

        Returns:
            是否重排成功。
        """
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan:
                return False
            if len(phase_ids) != len(plan.phases):
                return False
            id_to_phase = {p.id: p for p in plan.phases}
            if set(id_to_phase.keys()) != set(phase_ids):
                return False
            plan.phases = [id_to_phase[pid] for pid in phase_ids]
            plan.updated_at = datetime.now().isoformat()
            return True

    # ===== 完成度评估 =====

    def compute_completion(
        self, plan: ResearchPlan, reference_date: Optional[str] = None
    ) -> float:
        """计算计划整体完成度。

        Args:
            plan: 研究计划。
            reference_date: 参考日期。

        Returns:
            完成度（0-100）。
        """
        if not plan.phases:
            return 0.0
        total_weight = sum(p.weight for p in plan.phases)
        if total_weight <= 0:
            # 等权重
            return round(sum(p.progress for p in plan.phases) / len(plan.phases), 2)
        weighted = sum(p.progress * p.weight for p in plan.phases)
        return round(weighted / total_weight, 2)

    def compute_completion_detail(
        self, plan: ResearchPlan, reference_date: Optional[str] = None
    ) -> dict[str, Any]:
        """计算完成度详情（含各阶段、预期、偏差）。

        Args:
            plan: 研究计划。
            reference_date: 参考日期。

        Returns:
            完成度详情字典。
        """
        ref = reference_date or datetime.now().strftime("%Y-%m-%d")
        overall = self.compute_completion(plan, ref)
        phase_details = []
        for phase in plan.phases:
            expected = phase.expected_progress(ref)
            actual = phase.progress
            deviation = round(actual - expected, 2)
            phase_details.append({
                "phase_id": phase.id,
                "name": phase.name,
                "expected_progress": expected,
                "actual_progress": actual,
                "deviation": deviation,
                "status": phase.status,
                "is_overdue": phase.is_overdue(ref),
            })
        # 总体偏差
        total_expected = sum(
            p.expected_progress(ref) * p.weight for p in plan.phases
        ) / max(sum(p.weight for p in plan.phases), 1e-9)
        return {
            "overall_completion": overall,
            "overall_expected": round(total_expected, 2),
            "overall_deviation": round(overall - total_expected, 2),
            "reference_date": ref,
            "phases": phase_details,
        }

    # ===== 风险管理 =====

    def add_risk(
        self,
        plan_id: str,
        description: str,
        category: str = "technical",
        probability: float = 0.3,
        impact: float = 0.5,
        mitigation: str = "",
        contingency: str = "",
        owner: str = "",
        trigger: str = "",
    ) -> Optional[RiskItem]:
        """向计划添加风险项。

        Args:
            plan_id: 计划 ID。
            description: 风险描述。
            category: 风险类别。
            probability: 发生概率（0-1）。
            impact: 影响程度（0-1）。
            mitigation: 缓解措施。
            contingency: 应急预案。
            owner: 责任人。
            trigger: 触发条件。

        Returns:
            创建的风险项，计划不存在返回 None。
        """
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan:
                return None
            risk = RiskItem(
                id=f"risk_{uuid.uuid4().hex[:8]}",
                description=description,
                category=category,
                probability=max(0.0, min(1.0, probability)),
                impact=max(0.0, min(1.0, impact)),
                mitigation=mitigation,
                contingency=contingency,
                owner=owner,
                status="identified",
                trigger=trigger,
            )
            plan.risks.risks.append(risk)
            # 重新评估总体等级
            plan.risks.overall_level = self._compute_overall_risk(plan.risks.risks)
            plan.risks.assessment_date = datetime.now().strftime("%Y-%m-%d")
            plan.updated_at = datetime.now().isoformat()
            return risk

    def _compute_overall_risk(self, risks: list[RiskItem]) -> str:
        """计算总体风险等级。

        Args:
            risks: 风险项列表。

        Returns:
            总体风险等级。
        """
        if not risks:
            return "low"
        scores = [r.score for r in risks]
        avg = sum(scores) / len(scores)
        # 同时考虑最高风险
        max_score = max(scores)
        combined = (avg + max_score) / 2
        if combined >= RISK_THRESHOLDS["critical"]:
            return "critical"
        if combined >= RISK_THRESHOLDS["high"]:
            return "high"
        if combined >= RISK_THRESHOLDS["medium"]:
            return "medium"
        return "low"

    def update_risk_status(
        self, plan_id: str, risk_id: str, status: str, note: str = ""
    ) -> bool:
        """更新风险状态。

        Args:
            plan_id: 计划 ID。
            risk_id: 风险 ID。
            status: 新状态（identified/mitigating/resolved/occurred）。
            note: 备注。

        Returns:
            是否更新成功。
        """
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan:
                return False
            for risk in plan.risks.risks:
                if risk.id == risk_id:
                    risk.status = status
                    if note:
                        risk.metadata = risk.metadata or {}
                        risk.metadata["note"] = note
                    plan.updated_at = datetime.now().isoformat()
                    return True
            return False

    def get_critical_risks(self, plan_id: str) -> list[RiskItem]:
        """获取关键与高风险项。

        Args:
            plan_id: 计划 ID。

        Returns:
            风险项列表（按得分降序）。
        """
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan:
                return []
            high = [r for r in plan.risks.risks if r.level in ("critical", "high")]
            return sorted(high, key=lambda r: r.score, reverse=True)

    # ===== 资源管理 =====

    def add_resource(
        self,
        plan_id: str,
        resource_type: str,
        description: str,
        amount: float = 1.0,
        unit: str = "",
        cost: float = 0.0,
        source: str = "",
        phase_id: str = "",
    ) -> Optional[ResourceAllocation]:
        """向计划添加资源分配。

        Args:
            plan_id: 计划 ID。
            resource_type: 资源类型。
            description: 资源描述。
            amount: 数量。
            unit: 单位。
            cost: 成本。
            source: 来源。
            phase_id: 关联阶段 ID。

        Returns:
            创建的资源分配，计划不存在返回 None。
        """
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan:
                return None
            if resource_type not in RESOURCE_TYPES:
                raise ValueError(f"未知资源类型: {resource_type}")
            res = ResourceAllocation(
                resource_type=resource_type,
                description=description,
                amount=amount,
                unit=unit,
                cost=cost,
                source=source,
                phase_id=phase_id,
            )
            plan.resources.append(res)
            plan.updated_at = datetime.now().isoformat()
            return res

    def compute_resource_summary(self, plan_id: str) -> dict[str, Any]:
        """计算资源汇总。

        Args:
            plan_id: 计划 ID。

        Returns:
            资源汇总字典（按类型分组）。
        """
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan:
                return {}
            by_type: dict[str, list[ResourceAllocation]] = defaultdict(list)
            for r in plan.resources:
                by_type[r.resource_type].append(r)
            summary: dict[str, Any] = {}
            total_cost = 0.0
            for rtype, items in by_type.items():
                summary[rtype] = {
                    "name": RESOURCE_TYPES.get(rtype, rtype),
                    "count": len(items),
                    "total_cost": sum(i.cost for i in items),
                    "items": [i.to_dict() for i in items],
                }
                total_cost += sum(i.cost for i in items)
            summary["total_cost"] = total_cost
            return summary

    # ===== 方法选择 =====

    def recommend_methods(
        self,
        plan_id: str,
        research_type: str = "empirical",
        data_type: str = "quantitative",
        discipline: str = "",
    ) -> list[dict[str, Any]]:
        """推荐研究方法。

        Args:
            plan_id: 计划 ID。
            research_type: 研究类型（empirical/theoretical/mixed）。
            data_type: 数据类型（quantitative/qualitative/mixed）。
            discipline: 学科代码。

        Returns:
            推荐方法列表（含名称、类别、适用性、理由）。
        """
        # 方法库（精简版，与 method_library 对齐）
        method_lib = self._get_method_library()
        scored: list[tuple[float, dict[str, Any]]] = []
        for m in method_lib:
            score = 0.0
            reasons: list[str] = []
            # 数据类型匹配
            if data_type == "quantitative" and m["category"] == "quantitative":
                score += 0.4
                reasons.append("与定量数据匹配")
            elif data_type == "qualitative" and m["category"] == "qualitative":
                score += 0.4
                reasons.append("与定性数据匹配")
            elif data_type == "mixed" and m["category"] == "mixed":
                score += 0.5
                reasons.append("支持混合方法")
            # 研究类型匹配
            if research_type == "empirical" and m["category"] in ("empirical", "quantitative", "qualitative"):
                score += 0.3
                reasons.append("适用于经验研究")
            elif research_type == "theoretical" and m["category"] == "theoretical":
                score += 0.4
                reasons.append("适用于理论研究")
            # 学科匹配
            if discipline and discipline in m.get("applicable_disciplines", []):
                score += 0.3
                reasons.append(f"适用于学科 {discipline}")
            if score > 0:
                scored.append((score, {
                    "method_id": m["id"],
                    "name": m["name"],
                    "category": m["category"],
                    "category_name": METHOD_CATEGORIES.get(m["category"], m["category"]),
                    "score": round(score, 3),
                    "reasons": reasons,
                    "description": m.get("description", ""),
                }))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s[1] for s in scored[:8]]

    def _get_method_library(self) -> list[dict[str, Any]]:
        """获取方法库（精简版内置）。

        Returns:
            方法列表。
        """
        return [
            {
                "id": "method_survey",
                "name": "问卷调查法",
                "category": "quantitative",
                "description": "通过问卷收集大样本数据，进行统计分析。",
                "applicable_disciplines": ["0401", "0402", "1202", "0303", "0202"],
            },
            {
                "id": "method_experiment",
                "name": "实验研究法",
                "category": "quantitative",
                "description": "控制条件下操纵自变量，观察因变量，建立因果。",
                "applicable_disciplines": ["0701", "0702", "0811", "0402"],
            },
            {
                "id": "method_interview",
                "name": "深度访谈法",
                "category": "qualitative",
                "description": "通过半结构化访谈深入理解受访者观点。",
                "applicable_disciplines": ["0303", "0401", "0501", "1202"],
            },
            {
                "id": "method_case_study",
                "name": "案例研究法",
                "category": "qualitative",
                "description": "深入剖析单个或多个案例，揭示机制。",
                "applicable_disciplines": ["1202", "0303", "0401"],
            },
            {
                "id": "method_content_analysis",
                "name": "内容分析法",
                "category": "qualitative",
                "description": "系统分析文本/媒体内容，量化或质化。",
                "applicable_disciplines": ["0501", "0503", "0303"],
            },
            {
                "id": "method_meta_analysis",
                "name": "元分析法",
                "category": "quantitative",
                "description": "整合多项研究效应量，得出综合结论。",
                "applicable_disciplines": ["0402", "1001", "0701"],
            },
            {
                "id": "method_modeling",
                "name": "数学建模法",
                "category": "theoretical",
                "description": "构建数学模型描述与预测现象。",
                "applicable_disciplines": ["0701", "0702", "0811", "1201"],
            },
            {
                "id": "method_simulation",
                "name": "仿真模拟法",
                "category": "quantitative",
                "description": "通过计算机仿真研究系统行为。",
                "applicable_disciplines": ["0811", "0812", "0701"],
            },
            {
                "id": "method_ethnography",
                "name": "民族志法",
                "category": "qualitative",
                "description": "长期田野观察，理解文化与社会现象。",
                "applicable_disciplines": ["0303", "0401", "0501"],
            },
            {
                "id": "method_mixed_sequential",
                "name": "序列混合法",
                "category": "mixed",
                "description": "先定量后定性（或反之）序列展开。",
                "applicable_disciplines": ["0401", "0402", "1202", "0303"],
            },
        ]

    # ===== 计划调整 =====

    def adjust_plan_schedule(
        self,
        plan_id: str,
        new_end_date: Optional[str] = None,
        phase_adjustments: Optional[dict[str, int]] = None,
    ) -> bool:
        """调整计划时间安排。

        Args:
            plan_id: 计划 ID。
            new_end_date: 新结束日期（ISO 格式）。
            phase_adjustments: 阶段天数调整字典 {phase_id: delta_days}。

        Returns:
            是否调整成功。
        """
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan:
                return False
            # 调整单个阶段
            if phase_adjustments:
                for phase in plan.phases:
                    if phase.id in phase_adjustments:
                        delta = phase_adjustments[phase.id]
                        try:
                            old_end = datetime.strptime(phase.end_date, "%Y-%m-%d")
                            new_end = old_end + timedelta(days=delta)
                            phase.end_date = new_end.strftime("%Y-%m-%d")
                            phase.duration_days += delta
                        except (ValueError, TypeError):
                            continue
            # 整体调整结束日期
            if new_end_date:
                plan.end_date = new_end_date
            plan.updated_at = datetime.now().isoformat()
            return True

    def rebalance_weights(self, plan_id: str) -> bool:
        """重新平衡阶段权重（按天数比例）。

        Args:
            plan_id: 计划 ID。

        Returns:
            是否平衡成功。
        """
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan or not plan.phases:
                return False
            total_days = sum(p.duration_days for p in plan.phases)
            if total_days <= 0:
                return False
            for phase in plan.phases:
                phase.weight = round(phase.duration_days / total_days, 4)
            plan.updated_at = datetime.now().isoformat()
            return True

    # ===== 多学科规划 =====

    def plan_multidisciplinary(
        self,
        plan_id: str,
        disciplines: list[str],
        collaboration_mode: str = "interdisciplinary",
        lead_discipline: str = "",
    ) -> dict[str, Any]:
        """生成多学科研究规划。

        Args:
            plan_id: 计划 ID。
            disciplines: 涉及学科代码列表。
            collaboration_mode: 协作模式（见 COLLABORATION_MODES）。
            lead_discipline: 主导学科代码。

        Returns:
            多学科规划字典。
        """
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan:
                return {}
            if collaboration_mode not in COLLABORATION_MODES:
                raise ValueError(f"未知协作模式: {collaboration_mode}")
            if not disciplines:
                return {}

            # 各学科分工建议
            discipline_roles = self._assign_discipline_roles(
                disciplines, collaboration_mode, lead_discipline
            )
            # 跨学科整合点
            integration_points = self._identify_integration_points(
                disciplines, collaboration_mode
            )
            # 协作风险
            collab_risks = self._identify_collaboration_risks(disciplines, collaboration_mode)
            # 沟通机制
            communication = self._design_communication_plan(disciplines, collaboration_mode)

            return {
                "plan_id": plan_id,
                "disciplines": disciplines,
                "collaboration_mode": collaboration_mode,
                "mode_name": COLLABORATION_MODES[collaboration_mode],
                "lead_discipline": lead_discipline or disciplines[0],
                "discipline_roles": discipline_roles,
                "integration_points": integration_points,
                "collaboration_risks": collab_risks,
                "communication_plan": communication,
            }

    def _assign_discipline_roles(
        self,
        disciplines: list[str],
        mode: str,
        lead: str,
    ) -> list[dict[str, str]]:
        """为各学科分配角色。

        Args:
            disciplines: 学科列表。
            mode: 协作模式。
            lead: 主导学科。

        Returns:
            角色分配列表。
        """
        roles: list[dict[str, str]] = []
        if not lead:
            lead = disciplines[0]
        for disc in disciplines:
            if disc == lead:
                role = "主导：负责研究框架、核心问题与整合"
            elif mode == "interdisciplinary":
                role = "协作：提供本学科理论/方法支持"
            elif mode == "multidisciplinary":
                role = "并列：独立承担子课题"
            elif mode == "transdisciplinary":
                role = "融合：参与新框架构建"
            else:
                role = "借鉴：提供方法/理论参考"
            roles.append({"discipline": disc, "role": role})
        return roles

    def _identify_integration_points(
        self, disciplines: list[str], mode: str
    ) -> list[dict[str, str]]:
        """识别跨学科整合点。

        Args:
            disciplines: 学科列表。
            mode: 协作模式。

        Returns:
            整合点列表。
        """
        points: list[dict[str, str]] = []
        if len(disciplines) < 2:
            return points
        # 通用整合点
        points.append({
            "stage": "文献综述",
            "description": "整合多学科视角的文献，识别交叉空白",
            "importance": "高",
        })
        points.append({
            "stage": "研究设计",
            "description": "融合多学科理论框架，确定共同研究问题",
            "importance": "高",
        })
        if mode in ("interdisciplinary", "transdisciplinary"):
            points.append({
                "stage": "数据分析",
                "description": "采用多学科方法交叉验证结果",
                "importance": "中",
            })
        points.append({
            "stage": "讨论与结论",
            "description": "从多学科角度解释结果，提出综合贡献",
            "importance": "高",
        })
        return points

    def _identify_collaboration_risks(
        self, disciplines: list[str], mode: str
    ) -> list[dict[str, str]]:
        """识别协作风险。

        Args:
            disciplines: 学科列表。
            mode: 协作模式。

        Returns:
            风险列表。
        """
        risks: list[dict[str, str]] = []
        if len(disciplines) >= 3:
            risks.append({
                "risk": "学科术语差异导致沟通障碍",
                "mitigation": "建立术语对照表，定期召开跨学科研讨会",
            })
        if mode == "transdisciplinary":
            risks.append({
                "risk": "整合难度大，难以形成统一框架",
                "mitigation": "明确整合目标，分阶段整合，预留充足时间",
            })
        if mode == "multidisciplinary":
            risks.append({
                "risk": "各子课题割裂，缺乏有机联系",
                "mitigation": "设置整合阶段，明确各子课题接口",
            })
        risks.append({
            "risk": "学科贡献归属不清",
            "mitigation": "事先明确各学科贡献与作者顺序",
        })
        return risks

    def _design_communication_plan(
        self, disciplines: list[str], mode: str
    ) -> dict[str, Any]:
        """设计沟通机制。

        Args:
            disciplines: 学科列表。
            mode: 协作模式。

        Returns:
            沟通计划字典。
        """
        frequency = "每周" if mode == "interdisciplinary" else "每两周"
        return {
            "regular_meeting": f"{frequency}召开跨学科协调会",
            "shared_platform": "使用协作文档与项目管理工具共享进度",
            "milestone_review": "每个里程碑节点召开联合评审",
            "conflict_resolution": "由主导学科负责人协调，必要时引入第三方",
            "knowledge_sharing": "每月举办一次学科互讲，增进相互理解",
        }

    # ===== 进度跟踪 =====

    def track_progress(
        self, plan_id: str, reference_date: Optional[str] = None
    ) -> dict[str, Any]:
        """跟踪计划进度。

        Args:
            plan_id: 计划 ID。
            reference_date: 参考日期。

        Returns:
            进度跟踪报告字典。
        """
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan:
                return {}
            ref = reference_date or datetime.now().strftime("%Y-%m-%d")
            completion_detail = self.compute_completion_detail(plan, ref)
            # 识别问题阶段
            problem_phases = [
                p for p in completion_detail["phases"]
                if p["deviation"] < -10 or p["is_overdue"]
            ]
            # 识别关键风险
            critical_risks = self.get_critical_risks(plan_id)
            # 生成建议
            recommendations = self._generate_progress_recommendations(
                completion_detail, problem_phases, critical_risks
            )
            return {
                "plan_id": plan_id,
                "reference_date": ref,
                "completion": completion_detail["overall_completion"],
                "expected_completion": completion_detail["overall_expected"],
                "deviation": completion_detail["overall_deviation"],
                "phases": completion_detail["phases"],
                "problem_phases": problem_phases,
                "critical_risks": [r.to_dict() for r in critical_risks],
                "recommendations": recommendations,
            }

    def _generate_progress_recommendations(
        self,
        completion: dict[str, Any],
        problem_phases: list[dict[str, Any]],
        critical_risks: list[RiskItem],
    ) -> list[str]:
        """生成进度建议。

        Args:
            completion: 完成度详情。
            problem_phases: 问题阶段列表。
            critical_risks: 关键风险列表。

        Returns:
            建议列表。
        """
        recs: list[str] = []
        if completion["overall_deviation"] < -10:
            recs.append(
                f"整体进度落后预期 {abs(completion['overall_deviation'])}%，"
                "建议立即复盘并调整后续阶段时间"
            )
        for p in problem_phases:
            if p["is_overdue"]:
                recs.append(f"阶段「{p['name']}」已逾期，建议优先推进或调整范围")
            elif p["deviation"] < -10:
                recs.append(
                    f"阶段「{p['name']}」落后预期 {abs(p['deviation'])}%，"
                    "建议增加投入或简化任务"
                )
        for r in critical_risks[:3]:
            recs.append(
                f"关注风险「{r.description}」（{RISK_LEVEL_NAMES[r.level]}），"
                f"落实缓解措施：{r.mitigation}"
            )
        if not recs:
            recs.append("进度正常，继续保持当前节奏")
        return recs

    # ===== 历史与基准对比 =====

    def save_to_history(self, plan_id: str, note: str = "") -> bool:
        """将计划快照存入历史。

        Args:
            plan_id: 计划 ID。
            note: 备注。

        Returns:
            是否保存成功。
        """
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan:
                return False
            self._history.append({
                "plan_id": plan_id,
                "title": plan.title,
                "degree": plan.degree,
                "completion": self.compute_completion(plan),
                "phase_count": len(plan.phases),
                "risk_level": plan.risks.overall_level,
                "note": note,
                "saved_at": datetime.now().isoformat(),
            })
            return True

    def compare_with_history(self, plan_id: str) -> dict[str, Any]:
        """与历史计划对比。

        Args:
            plan_id: 当前计划 ID。

        Returns:
            对比结果字典。
        """
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan or not self._history:
                return {}
            current_completion = self.compute_completion(plan)
            history_completions = [h["completion"] for h in self._history if h.get("completion") is not None]
            if not history_completions:
                return {}
            avg_hist = sum(history_completions) / len(history_completions)
            max_hist = max(history_completions)
            min_hist = min(history_completions)
            return {
                "current_completion": current_completion,
                "history_avg": round(avg_hist, 2),
                "history_max": max_hist,
                "history_min": min_hist,
                "vs_avg": round(current_completion - avg_hist, 2),
                "history_count": len(history_completions),
                "percentile": round(
                    sum(1 for c in history_completions if c < current_completion)
                    / len(history_completions) * 100, 2
                ),
            }

    # ===== 导出 =====

    def export_plan_markdown(self, plan_id: str) -> str:
        """导出计划为 Markdown 文档。

        Args:
            plan_id: 计划 ID。

        Returns:
            Markdown 字符串。
        """
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan:
                return ""
            lines: list[str] = []
            lines.append(f"# 研究计划：{plan.title}")
            lines.append("")
            lines.append(f"- **学位类型**：{DEGREE_NAMES.get(plan.degree, plan.degree)}")
            lines.append(f"- **学科代码**：{plan.discipline or '未指定'}")
            lines.append(f"- **起止时间**：{plan.start_date} ~ {plan.end_date}")
            lines.append(f"- **研究问题**：{plan.research_question or '未指定'}")
            if plan.hypotheses:
                lines.append("- **研究假设**：")
                for i, h in enumerate(plan.hypotheses, 1):
                    lines.append(f"  {i}. {h}")
            lines.append("")

            # 阶段
            lines.append("## 研究阶段")
            lines.append("")
            lines.append("| 阶段 | 起止时间 | 权重 | 进度 | 状态 |")
            lines.append("|------|----------|------|------|------|")
            for p in plan.phases:
                lines.append(
                    f"| {p.name} | {p.start_date}~{p.end_date} | "
                    f"{p.weight:.0%} | {p.progress:.0f}% | {p.status} |"
                )
            lines.append("")

            # 资源
            if plan.resources:
                lines.append("## 资源分配")
                lines.append("")
                lines.append("| 类型 | 描述 | 数量 | 单位 | 成本 | 来源 |")
                lines.append("|------|------|------|------|------|------|")
                for r in plan.resources:
                    lines.append(
                        f"| {RESOURCE_TYPES.get(r.resource_type, r.resource_type)} | "
                        f"{r.description} | {r.amount} | {r.unit} | "
                        f"{r.cost} | {r.source} |"
                    )
                lines.append("")

            # 风险
            if plan.risks.risks:
                lines.append("## 风险评估")
                lines.append("")
                lines.append(f"**总体风险等级**：{RISK_LEVEL_NAMES.get(plan.risks.overall_level, plan.risks.overall_level)}")
                lines.append("")
                lines.append("| 风险 | 类别 | 概率 | 影响 | 等级 | 缓解措施 |")
                lines.append("|------|------|------|------|------|----------|")
                for r in plan.risks.risks:
                    lines.append(
                        f"| {r.description} | {r.category} | {r.probability:.0%} | "
                        f"{r.impact:.0%} | {RISK_LEVEL_NAMES[r.level]} | {r.mitigation} |"
                    )
                lines.append("")

            # 数据计划
            if plan.data_plan:
                dp = plan.data_plan
                lines.append("## 数据收集计划")
                lines.append("")
                lines.append(f"- **数据类型**：{dp.data_type}")
                lines.append(f"- **来源**：{dp.source}")
                lines.append(f"- **方法**：{dp.method}")
                lines.append(f"- **样本量**：{dp.sample_size}")
                lines.append(f"- **抽样方案**：{dp.sampling}")
                if dp.quality_control:
                    lines.append("- **质量控制**：")
                    for q in dp.quality_control:
                        lines.append(f"  - {q}")
                lines.append("")

            # 分析计划
            if plan.analysis_plan:
                ap = plan.analysis_plan
                lines.append("## 分析计划")
                lines.append("")
                lines.append(f"- **分析类型**：{ap.analysis_type}")
                lines.append(f"- **方法**：{', '.join(ap.methods)}")
                lines.append(f"- **软件**：{', '.join(ap.software)}")
                lines.append(f"- **显著性水平**：{ap.significance_level}")
                lines.append(f"- **检验功效**：{ap.power}")
                lines.append("")

            # 完成度
            completion = self.compute_completion(plan)
            lines.append("## 完成度")
            lines.append("")
            lines.append(f"**整体完成度**：{completion:.2f}%")
            lines.append("")

            return "\n".join(lines)

    def export_plan_dict(self, plan_id: str) -> dict[str, Any]:
        """导出计划为字典。

        Args:
            plan_id: 计划 ID。

        Returns:
            计划字典，不存在返回空字典。
        """
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan:
                return {}
            return plan.to_dict()

    # ===== 模板 =====

    def get_plan_template(self, degree: str = "master") -> dict[str, Any]:
        """获取计划模板。

        Args:
            degree: 学位类型。

        Returns:
            模板字典。
        """
        if degree not in DEGREE_DURATION_DAYS:
            raise ValueError(f"不支持的学位类型: {degree}")
        return {
            "degree": degree,
            "degree_name": DEGREE_NAMES[degree],
            "default_duration_days": DEGREE_DURATION_DAYS[degree],
            "phases": [
                {
                    "id": t["id"],
                    "name": t["name"],
                    "description": t["description"],
                    "default_weight": t["default_weight"],
                    "default_duration_days": t["default_duration_days"],
                    "key_activities": t["key_activities"],
                    "deliverables": t["deliverables"],
                }
                for t in DEFAULT_PHASE_TEMPLATES
            ],
            "method_categories": METHOD_CATEGORIES,
            "resource_types": RESOURCE_TYPES,
            "risk_thresholds": RISK_THRESHOLDS,
            "collaboration_modes": COLLABORATION_MODES,
        }

    def list_templates(self) -> list[dict[str, str]]:
        """列出所有可用模板。

        Returns:
            模板列表。
        """
        return [
            {"degree": k, "name": v, "duration_days": DEGREE_DURATION_DAYS[k]}
            for k, v in DEGREE_NAMES.items()
        ]

    # ===== 统计 =====

    def compute_plan_statistics(self, plan_id: str) -> dict[str, Any]:
        """计算计划统计指标。

        Args:
            plan_id: 计划 ID。

        Returns:
            统计字典。
        """
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan:
                return {}
            total_days = 0
            completed_days = 0
            for p in plan.phases:
                total_days += p.duration_days
                completed_days += p.duration_days * (p.progress / 100.0)
            return {
                "plan_id": plan_id,
                "phase_count": len(plan.phases),
                "total_duration_days": total_days,
                "completed_days": round(completed_days, 1),
                "remaining_days": round(total_days - completed_days, 1),
                "overall_completion": self.compute_completion(plan),
                "resource_count": len(plan.resources),
                "total_cost": sum(r.cost for r in plan.resources),
                "risk_count": len(plan.risks.risks),
                "critical_risk_count": sum(
                    1 for r in plan.risks.risks if r.level in ("critical", "high")
                ),
                "overall_risk_level": plan.risks.overall_level,
                "collaborator_count": len(plan.collaborators),
            }

    def summary(self) -> dict[str, Any]:
        """返回规划器汇总信息。

        Returns:
            汇总字典。
        """
        with self._lock:
            return {
                "plan_count": len(self._plans),
                "history_count": len(self._history),
                "default_degree": self._default_degree,
                "supported_degrees": list(DEGREE_DURATION_DAYS.keys()),
                "phase_templates": len(DEFAULT_PHASE_TEMPLATES),
            }
