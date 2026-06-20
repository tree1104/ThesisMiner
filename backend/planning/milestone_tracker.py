"""里程碑追踪器模块

提供完整的研究里程碑追踪能力，包括：
    - 里程碑定义、状态管理、完成度计算
    - 里程碑依赖关系、关键路径、延迟预警
    - 进度报告、里程碑评审、验收标准
    - 历史里程碑分析、趋势预测、改进建议
    - 完整的追踪算法、报告模板

设计原则：
    1. 零外部依赖：仅使用 Python 标准库
    2. 线程安全：所有公共方法通过 RLock 保护
    3. 可持久化：基于 dataclass，支持序列化
    4. 可扩展：里程碑类型、状态均可动态扩展

核心数据结构：
    - Milestone: 里程碑（含验收标准、依赖、状态）
    - MilestoneStatus: 里程碑状态常量
    - MilestoneReview: 里程碑评审记录
    - AcceptanceCriteria: 验收标准
"""
from __future__ import annotations

import math
import re
import threading
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Any, Iterable, Optional


# ===== 常量定义 =====


class MilestoneStatus:
    """里程碑状态常量。"""

    PROPOSED = "proposed"          # 已提出
    APPROVED = "approved"          # 已批准
    IN_PROGRESS = "in_progress"    # 进行中
    UNDER_REVIEW = "under_review"  # 评审中
    COMPLETED = "completed"        # 已完成
    DELAYED = "delayed"            # 已延期
    CANCELLED = "cancelled"        # 已取消
    BLOCKED = "blocked"            # 已阻塞


# 状态中文名
STATUS_NAMES = {
    MilestoneStatus.PROPOSED: "已提出",
    MilestoneStatus.APPROVED: "已批准",
    MilestoneStatus.IN_PROGRESS: "进行中",
    MilestoneStatus.UNDER_REVIEW: "评审中",
    MilestoneStatus.COMPLETED: "已完成",
    MilestoneStatus.DELAYED: "已延期",
    MilestoneStatus.CANCELLED: "已取消",
    MilestoneStatus.BLOCKED: "已阻塞",
}

# 里程碑类型
MILESTONE_TYPES = {
    "proposal": "开题答辩",
    "literature_review": "文献综述完成",
    "research_design": "研究设计完成",
    "data_collection": "数据收集完成",
    "data_analysis": "数据分析完成",
    "draft_completion": "初稿完成",
    "midterm_review": "中期检查",
    "revision_completion": "修改稿完成",
    "predefense": "预答辩",
    "defense": "正式答辩",
    "submission": "论文提交",
    "custom": "自定义里程碑",
}

# 里程碑优先级
MILESTONE_PRIORITY = {
    "critical": "关键",
    "high": "高",
    "medium": "中",
    "low": "低",
}

# 延迟预警阈值（天）
DELAY_WARNING_THRESHOLDS = {
    "early": 3,     # 提前 3 天预警
    "warning": 7,   # 7 天预警
    "critical": 14, # 14 天严重预警
}

# 评审结果
REVIEW_RESULTS = {
    "passed": "通过",
    "passed_with_revision": "通过但需修改",
    "major_revision": "重大修改",
    "failed": "未通过",
    "deferred": "延期评审",
}

# 默认里程碑模板（按学位论文流程）
DEFAULT_MILESTONE_TEMPLATES = [
    {
        "id": "ms_proposal",
        "name": "开题答辩",
        "type": "proposal",
        "description": "完成开题报告并通过开题答辩",
        "default_offset_days": 30,
        "priority": "critical",
        "acceptance_criteria": [
            "开题报告撰写完成",
            "研究问题与假设明确",
            "研究方法确定",
            "导师签字同意",
            "开题答辩通过",
        ],
    },
    {
        "id": "ms_literature",
        "name": "文献综述完成",
        "type": "literature_review",
        "description": "完成系统文献综述",
        "default_offset_days": 60,
        "priority": "high",
        "acceptance_criteria": [
            "检索 50 篇以上相关文献",
            "综述结构完整",
            "研究空白明确",
            "导师审阅通过",
        ],
    },
    {
        "id": "ms_design",
        "name": "研究设计完成",
        "type": "research_design",
        "description": "完成研究设计方案",
        "default_offset_days": 90,
        "priority": "critical",
        "acceptance_criteria": [
            "概念框架构建完成",
            "变量操作化定义明确",
            "抽样方案确定",
            "分析计划制定",
            "导师签字同意",
        ],
    },
    {
        "id": "ms_data",
        "name": "数据收集完成",
        "type": "data_collection",
        "description": "完成全部数据收集与清洗",
        "default_offset_days": 150,
        "priority": "critical",
        "acceptance_criteria": [
            "样本量达到设计要求",
            "数据清洗完成",
            "数据质量检查通过",
            "数据归档",
        ],
    },
    {
        "id": "ms_analysis",
        "name": "数据分析完成",
        "type": "data_analysis",
        "description": "完成数据分析与假设检验",
        "default_offset_days": 200,
        "priority": "critical",
        "acceptance_criteria": [
            "描述统计完成",
            "推断统计完成",
            "假设检验结论明确",
            "稳健性检验通过",
            "结果可视化完成",
        ],
    },
    {
        "id": "ms_draft",
        "name": "初稿完成",
        "type": "draft_completion",
        "description": "完成论文初稿",
        "default_offset_days": 250,
        "priority": "critical",
        "acceptance_criteria": [
            "各章节撰写完成",
            "引用规范",
            "格式符合要求",
            "导师审阅",
        ],
    },
    {
        "id": "ms_midterm",
        "name": "中期检查",
        "type": "midterm_review",
        "description": "通过中期检查",
        "default_offset_days": 180,
        "priority": "high",
        "acceptance_criteria": [
            "中期报告撰写完成",
            "进度符合计划",
            "中期检查通过",
        ],
    },
    {
        "id": "ms_revision",
        "name": "修改稿完成",
        "type": "revision_completion",
        "description": "完成论文修改稿",
        "default_offset_days": 300,
        "priority": "high",
        "acceptance_criteria": [
            "根据评审意见修改",
            "查重通过",
            "格式最终确认",
            "导师签字",
        ],
    },
    {
        "id": "ms_predefense",
        "name": "预答辩",
        "type": "predefense",
        "description": "通过预答辩",
        "default_offset_days": 320,
        "priority": "critical",
        "acceptance_criteria": [
            "论文定稿",
            "预答辩通过",
            "送审资格确认",
        ],
    },
    {
        "id": "ms_defense",
        "name": "正式答辩",
        "type": "defense",
        "description": "通过正式答辩",
        "default_offset_days": 350,
        "priority": "critical",
        "acceptance_criteria": [
            "盲审通过",
            "答辩 PPT 完成",
            "答辩通过",
            "答辩委员会签字",
        ],
    },
]


# ===== 数据结构 =====


@dataclass
class AcceptanceCriteria:
    """验收标准数据结构。

    Attributes:
        id: 标准 ID。
        description: 标准描述。
        is_met: 是否满足。
        evidence: 满足证据。
        verified_by: 验证人。
        verified_at: 验证时间。
    """

    id: str = ""
    description: str = ""
    is_met: bool = False
    evidence: str = ""
    verified_by: str = ""
    verified_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return asdict(self)


@dataclass
class Milestone:
    """里程碑数据结构。

    Attributes:
        id: 里程碑 ID。
        name: 里程碑名称。
        type: 里程碑类型。
        description: 里程碑描述。
        planned_date: 计划日期。
        actual_date: 实际日期。
        status: 状态。
        priority: 优先级。
        acceptance_criteria: 验收标准列表。
        dependencies: 依赖里程碑 ID 列表。
        assignee: 负责人。
        progress: 完成进度（0-100）。
        reviews: 评审记录列表。
        notes: 备注。
        created_at: 创建时间。
        updated_at: 更新时间。
        metadata: 扩展元数据。
    """

    id: str = ""
    name: str = ""
    type: str = "custom"
    description: str = ""
    planned_date: str = ""
    actual_date: str = ""
    status: str = MilestoneStatus.PROPOSED
    priority: str = "medium"
    acceptance_criteria: list[AcceptanceCriteria] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    assignee: str = ""
    progress: float = 0.0
    reviews: list["MilestoneReview"] = field(default_factory=list)
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "planned_date": self.planned_date,
            "actual_date": self.actual_date,
            "status": self.status,
            "status_name": STATUS_NAMES.get(self.status, self.status),
            "priority": self.priority,
            "priority_name": MILESTONE_PRIORITY.get(self.priority, self.priority),
            "acceptance_criteria": [c.to_dict() for c in self.acceptance_criteria],
            "dependencies": self.dependencies,
            "assignee": self.assignee,
            "progress": self.progress,
            "reviews": [r.to_dict() for r in self.reviews],
            "notes": self.notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Milestone":
        """从字典构造里程碑实例。"""
        m = cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            type=data.get("type", "custom"),
            description=data.get("description", ""),
            planned_date=data.get("planned_date", ""),
            actual_date=data.get("actual_date", ""),
            status=data.get("status", MilestoneStatus.PROPOSED),
            priority=data.get("priority", "medium"),
            dependencies=data.get("dependencies", []),
            assignee=data.get("assignee", ""),
            progress=data.get("progress", 0.0),
            notes=data.get("notes", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            metadata=data.get("metadata", {}),
        )
        m.acceptance_criteria = [
            AcceptanceCriteria(**c) for c in data.get("acceptance_criteria", [])
        ]
        m.reviews = [
            MilestoneReview.from_dict(r) for r in data.get("reviews", [])
        ]
        return m

    def is_overdue(self, reference_date: Optional[str] = None) -> bool:
        """判断里程碑是否逾期。"""
        if not self.planned_date:
            return False
        if self.status in (MilestoneStatus.COMPLETED, MilestoneStatus.CANCELLED):
            return False
        ref = reference_date or datetime.now().strftime("%Y-%m-%d")
        return ref > self.planned_date

    def delay_days(self, reference_date: Optional[str] = None) -> int:
        """计算延迟天数（正数表示逾期，负数表示提前）。"""
        if not self.planned_date:
            return 0
        ref = reference_date or datetime.now().strftime("%Y-%m-%d")
        # 若已完成，用实际日期比较
        compare_date = self.actual_date if self.actual_date and self.status == MilestoneStatus.COMPLETED else ref
        try:
            planned = datetime.strptime(self.planned_date, "%Y-%m-%d")
            actual = datetime.strptime(compare_date, "%Y-%m-%d")
            return (actual - planned).days
        except ValueError:
            return 0

    def completion_rate(self) -> float:
        """计算验收标准完成率。"""
        if not self.acceptance_criteria:
            return self.progress
        met = sum(1 for c in self.acceptance_criteria if c.is_met)
        return round(met / len(self.acceptance_criteria) * 100, 2)

    def is_complete(self) -> bool:
        """判断里程碑是否真正完成（所有验收标准满足）。"""
        if not self.acceptance_criteria:
            return self.status == MilestoneStatus.COMPLETED
        return all(c.is_met for c in self.acceptance_criteria)


@dataclass
class MilestoneReview:
    """里程碑评审记录数据结构。

    Attributes:
        id: 评审 ID。
        reviewer: 评审人。
        review_date: 评审日期。
        result: 评审结果。
        comments: 评审意见。
        action_items: 待办事项列表。
        next_review_date: 下次评审日期。
    """

    id: str = ""
    reviewer: str = ""
    review_date: str = ""
    result: str = "passed"
    comments: str = ""
    action_items: list[str] = field(default_factory=list)
    next_review_date: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MilestoneReview":
        """从字典构造评审记录。"""
        defaults = cls().__dict__
        merged = {**defaults, **{k: v for k, v in data.items() if k in defaults}}
        return cls(**merged)


# ===== 主类实现 =====


class MilestoneTracker:
    """里程碑追踪器主类。

    提供里程碑定义、状态管理、完成度计算、依赖关系、关键路径、延迟预警、
    进度报告、里程碑评审、验收标准、历史分析、趋势预测、改进建议等能力。

    线程安全：所有公共方法通过 RLock 保护。
    """

    def __init__(self):
        """初始化里程碑追踪器。"""
        self._lock = threading.RLock()
        self._milestones: dict[str, Milestone] = {}
        self._history: list[dict[str, Any]] = []
        self._project_start: str = ""
        self._project_end: str = ""

    # ===== 里程碑创建 =====

    def create_milestone(
        self,
        name: str,
        type: str = "custom",
        description: str = "",
        planned_date: str = "",
        priority: str = "medium",
        acceptance_criteria: Optional[list[str]] = None,
        dependencies: Optional[list[str]] = None,
        assignee: str = "",
    ) -> Milestone:
        """创建里程碑。

        Args:
            name: 里程碑名称。
            type: 里程碑类型。
            description: 里程碑描述。
            planned_date: 计划日期。
            priority: 优先级。
            acceptance_criteria: 验收标准描述列表。
            dependencies: 依赖里程碑 ID 列表。
            assignee: 负责人。

        Returns:
            创建的 Milestone 实例。
        """
        with self._lock:
            if type not in MILESTONE_TYPES:
                type = "custom"
            ms_id = f"ms_{uuid.uuid4().hex[:10]}"
            criteria: list[AcceptanceCriteria] = []
            for desc in (acceptance_criteria or []):
                criteria.append(AcceptanceCriteria(
                    id=f"ac_{uuid.uuid4().hex[:8]}",
                    description=desc,
                    is_met=False,
                ))
            milestone = Milestone(
                id=ms_id,
                name=name,
                type=type,
                description=description,
                planned_date=planned_date,
                status=MilestoneStatus.PROPOSED,
                priority=priority,
                acceptance_criteria=criteria,
                dependencies=dependencies or [],
                assignee=assignee,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
            )
            self._milestones[ms_id] = milestone
            return milestone

    def create_default_milestones(
        self,
        start_date: str,
        end_date: str,
        degree: str = "master",
    ) -> list[Milestone]:
        """根据模板创建默认里程碑。

        Args:
            start_date: 项目开始日期。
            end_date: 项目结束日期。
            degree: 学位类型。

        Returns:
            创建的里程碑列表。
        """
        with self._lock:
            self._project_start = start_date
            self._project_end = end_date
            try:
                start = datetime.strptime(start_date, "%Y-%m-%d")
                end = datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError as e:
                raise ValueError(f"日期格式错误: {e}")
            total_days = (end - start).days
            if total_days <= 0:
                raise ValueError("结束日期必须晚于开始日期")

            created: list[Milestone] = []
            for tpl in DEFAULT_MILESTONE_TEMPLATES:
                # 按偏移天数比例计算实际日期
                offset_ratio = tpl["default_offset_days"] / 365  # 假设模板基于 1 年
                actual_offset = int(total_days * offset_ratio)
                planned = start + timedelta(days=actual_offset)
                if planned > end:
                    planned = end
                ms = self.create_milestone(
                    name=tpl["name"],
                    type=tpl["type"],
                    description=tpl["description"],
                    planned_date=planned.strftime("%Y-%m-%d"),
                    priority=tpl["priority"],
                    acceptance_criteria=tpl["acceptance_criteria"],
                )
                created.append(ms)
            # 设置依赖关系
            self._setup_default_dependencies()
            return created

    def _setup_default_dependencies(self) -> None:
        """设置默认里程碑依赖关系。"""
        # 按类型查找里程碑
        by_type: dict[str, str] = {}
        for ms in self._milestones.values():
            by_type[ms.type] = ms.id
        # 依赖链：开题 -> 文献 -> 设计 -> 数据 -> 分析 -> 初稿 -> 修改 -> 预答辩 -> 答辩
        dep_chain = [
            "proposal", "literature_review", "research_design",
            "data_collection", "data_analysis", "draft_completion",
            "revision_completion", "predefense", "defense",
        ]
        for i in range(1, len(dep_chain)):
            curr_type = dep_chain[i]
            prev_type = dep_chain[i - 1]
            if curr_type in by_type and prev_type in by_type:
                ms = self._milestones[by_type[curr_type]]
                if by_type[prev_type] not in ms.dependencies:
                    ms.dependencies.append(by_type[prev_type])

    # ===== 里程碑查询 =====

    def get_milestone(self, milestone_id: str) -> Optional[Milestone]:
        """获取里程碑。"""
        with self._lock:
            return self._milestones.get(milestone_id)

    def list_milestones(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        type: Optional[str] = None,
    ) -> list[Milestone]:
        """列出里程碑（可过滤）。"""
        with self._lock:
            result = list(self._milestones.values())
            if status:
                result = [m for m in result if m.status == status]
            if priority:
                result = [m for m in result if m.priority == priority]
            if type:
                result = [m for m in result if m.type == type]
            # 按计划日期排序
            result.sort(key=lambda m: m.planned_date or "9999-12-31")
            return result

    def delete_milestone(self, milestone_id: str) -> bool:
        """删除里程碑。"""
        with self._lock:
            if milestone_id not in self._milestones:
                return False
            # 移除其他里程碑对该里程碑的依赖
            for ms in self._milestones.values():
                if milestone_id in ms.dependencies:
                    ms.dependencies.remove(milestone_id)
            del self._milestones[milestone_id]
            return True

    # ===== 状态管理 =====

    def update_status(
        self,
        milestone_id: str,
        status: str,
        note: str = "",
        actual_date: Optional[str] = None,
    ) -> bool:
        """更新里程碑状态。

        Args:
            milestone_id: 里程碑 ID。
            status: 新状态。
            note: 备注。
            actual_date: 实际完成日期（完成时使用）。

        Returns:
            是否更新成功。
        """
        with self._lock:
            ms = self._milestones.get(milestone_id)
            if not ms:
                return False
            if status not in STATUS_NAMES:
                raise ValueError(f"未知状态: {status}")
            ms.status = status
            if note:
                ms.notes = note if not ms.notes else f"{ms.notes}\n{note}"
            if status == MilestoneStatus.COMPLETED:
                ms.actual_date = actual_date or datetime.now().strftime("%Y-%m-%d")
                ms.progress = 100.0
                # 自动标记所有验收标准为满足
                for c in ms.acceptance_criteria:
                    c.is_met = True
                    if not c.verified_at:
                        c.verified_at = ms.actual_date
            ms.updated_at = datetime.now().isoformat()
            return True

    def update_progress(
        self, milestone_id: str, progress: float
    ) -> bool:
        """更新里程碑进度。"""
        with self._lock:
            ms = self._milestones.get(milestone_id)
            if not ms:
                return False
            ms.progress = max(0.0, min(100.0, float(progress)))
            # 自动状态转换
            if ms.progress >= 100.0 and ms.status not in (
                MilestoneStatus.COMPLETED, MilestoneStatus.UNDER_REVIEW
            ):
                ms.status = MilestoneStatus.UNDER_REVIEW
            elif ms.progress > 0.0 and ms.status == MilestoneStatus.PROPOSED:
                ms.status = MilestoneStatus.IN_PROGRESS
            ms.updated_at = datetime.now().isoformat()
            return True

    def update_planned_date(
        self, milestone_id: str, new_date: str, reason: str = ""
    ) -> bool:
        """更新计划日期。"""
        with self._lock:
            ms = self._milestones.get(milestone_id)
            if not ms:
                return False
            old_date = ms.planned_date
            ms.planned_date = new_date
            if reason:
                ms.metadata = ms.metadata or {}
                ms.metadata["date_change_reason"] = reason
                ms.metadata["previous_date"] = old_date
            ms.updated_at = datetime.now().isoformat()
            return True

    # ===== 验收标准管理 =====

    def add_acceptance_criteria(
        self, milestone_id: str, description: str
    ) -> Optional[AcceptanceCriteria]:
        """添加验收标准。"""
        with self._lock:
            ms = self._milestones.get(milestone_id)
            if not ms:
                return None
            criteria = AcceptanceCriteria(
                id=f"ac_{uuid.uuid4().hex[:8]}",
                description=description,
                is_met=False,
            )
            ms.acceptance_criteria.append(criteria)
            ms.updated_at = datetime.now().isoformat()
            return criteria

    def verify_criteria(
        self,
        milestone_id: str,
        criteria_id: str,
        is_met: bool,
        evidence: str = "",
        verified_by: str = "",
    ) -> bool:
        """验证验收标准。"""
        with self._lock:
            ms = self._milestones.get(milestone_id)
            if not ms:
                return False
            for c in ms.acceptance_criteria:
                if c.id == criteria_id:
                    c.is_met = is_met
                    c.evidence = evidence
                    c.verified_by = verified_by
                    c.verified_at = datetime.now().strftime("%Y-%m-%d")
                    # 更新进度
                    ms.progress = ms.completion_rate()
                    ms.updated_at = datetime.now().isoformat()
                    return True
            return False

    def check_completion(self, milestone_id: str) -> dict[str, Any]:
        """检查里程碑完成情况。"""
        with self._lock:
            ms = self._milestones.get(milestone_id)
            if not ms:
                return {}
            total = len(ms.acceptance_criteria)
            met = sum(1 for c in ms.acceptance_criteria if c.is_met)
            unmet = [c.to_dict() for c in ms.acceptance_criteria if not c.is_met]
            return {
                "milestone_id": milestone_id,
                "name": ms.name,
                "total_criteria": total,
                "met_criteria": met,
                "unmet_criteria": total - met,
                "completion_rate": ms.completion_rate(),
                "is_complete": ms.is_complete(),
                "unmet_details": unmet,
                "status": ms.status,
            }

    # ===== 依赖关系与关键路径 =====

    def add_dependency(
        self, milestone_id: str, depends_on_id: str
    ) -> bool:
        """添加依赖关系。"""
        with self._lock:
            ms = self._milestones.get(milestone_id)
            if not ms or depends_on_id not in self._milestones:
                return False
            if milestone_id == depends_on_id:
                return False  # 不能依赖自己
            # 检测循环依赖
            if self._would_create_cycle(milestone_id, depends_on_id):
                return False
            if depends_on_id not in ms.dependencies:
                ms.dependencies.append(depends_on_id)
                ms.updated_at = datetime.now().isoformat()
            return True

    def _would_create_cycle(
        self, milestone_id: str, depends_on_id: str
    ) -> bool:
        """检测添加依赖是否会形成循环。

        Args:
            milestone_id: 当前里程碑 ID。
            depends_on_id: 要依赖的里程碑 ID。

        Returns:
            是否会形成循环。
        """
        # 从 depends_on_id 出发，看能否回到 milestone_id
        visited: set[str] = set()
        queue: deque[str] = deque([depends_on_id])
        while queue:
            curr = queue.popleft()
            if curr == milestone_id:
                return True
            if curr in visited:
                continue
            visited.add(curr)
            ms = self._milestones.get(curr)
            if ms:
                for dep in ms.dependencies:
                    queue.append(dep)
        return False

    def remove_dependency(
        self, milestone_id: str, depends_on_id: str
    ) -> bool:
        """移除依赖关系。"""
        with self._lock:
            ms = self._milestones.get(milestone_id)
            if not ms:
                return False
            if depends_on_id in ms.dependencies:
                ms.dependencies.remove(depends_on_id)
                ms.updated_at = datetime.now().isoformat()
                return True
            return False

    def compute_critical_path(self) -> list[str]:
        """计算里程碑关键路径。

        Returns:
            关键路径上的里程碑 ID 列表。
        """
        with self._lock:
            if not self._milestones:
                return []
            # 拓扑排序
            in_degree: dict[str, int] = {mid: 0 for mid in self._milestones}
            for ms in self._milestones.values():
                for dep in ms.dependencies:
                    if dep in in_degree:
                        in_degree[ms.id] += 1
            queue: deque[str] = deque()
            for mid, deg in in_degree.items():
                if deg == 0:
                    queue.append(mid)
            topo: list[str] = []
            while queue:
                curr = queue.popleft()
                topo.append(curr)
                for ms in self._milestones.values():
                    if curr in ms.dependencies:
                        in_degree[ms.id] -= 1
                        if in_degree[ms.id] == 0:
                            queue.append(ms.id)
            if len(topo) != len(self._milestones):
                return []  # 存在循环
            # 求最长路径（按计划日期间隔）
            # 简化：选择计划日期最晚的链
            paths: dict[str, list[str]] = {mid: [mid] for mid in self._milestones}
            for mid in topo:
                ms = self._milestones[mid]
                for dep in ms.dependencies:
                    if dep in paths:
                        candidate = paths[dep] + [mid]
                        if len(candidate) > len(paths[mid]):
                            paths[mid] = candidate
            # 找最长路径
            longest = max(paths.values(), key=len)
            return longest

    def get_dependency_chain(self, milestone_id: str) -> list[str]:
        """获取里程碑的完整依赖链。

        Args:
            milestone_id: 里程碑 ID。

        Returns:
            依赖链（从最早到当前）。
        """
        with self._lock:
            chain: list[str] = []
            visited: set[str] = set()
            self._build_chain(milestone_id, chain, visited)
            chain.reverse()
            return chain

    def _build_chain(
        self, milestone_id: str, chain: list[str], visited: set[str]
    ) -> None:
        """递归构建依赖链。"""
        if milestone_id in visited:
            return
        visited.add(milestone_id)
        ms = self._milestones.get(milestone_id)
        if not ms:
            return
        for dep in ms.dependencies:
            self._build_chain(dep, chain, visited)
        chain.append(milestone_id)

    # ===== 延迟预警 =====

    def check_delays(
        self, reference_date: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """检查所有里程碑的延迟情况。

        Args:
            reference_date: 参考日期，默认为今天。

        Returns:
            延迟预警列表。
        """
        with self._lock:
            ref = reference_date or datetime.now().strftime("%Y-%m-%d")
            warnings: list[dict[str, Any]] = []
            for ms in self._milestones.values():
                if ms.status in (MilestoneStatus.COMPLETED, MilestoneStatus.CANCELLED):
                    continue
                if not ms.planned_date:
                    continue
                try:
                    planned = datetime.strptime(ms.planned_date, "%Y-%m-%d")
                    now = datetime.strptime(ref, "%Y-%m-%d")
                except ValueError:
                    continue
                days_to_deadline = (planned - now).days
                delay = ms.delay_days(ref)
                if delay > 0:
                    # 已逾期
                    severity = "critical"
                    if delay < DELAY_WARNING_THRESHOLDS["warning"]:
                        severity = "warning"
                    elif delay < DELAY_WARNING_THRESHOLDS["critical"]:
                        severity = "high"
                    warnings.append({
                        "milestone_id": ms.id,
                        "name": ms.name,
                        "planned_date": ms.planned_date,
                        "delay_days": delay,
                        "severity": severity,
                        "status": ms.status,
                        "suggestion": self._generate_delay_suggestion(ms, delay),
                    })
                elif days_to_deadline <= DELAY_WARNING_THRESHOLDS["early"] and days_to_deadline >= 0:
                    # 即将到期
                    warnings.append({
                        "milestone_id": ms.id,
                        "name": ms.name,
                        "planned_date": ms.planned_date,
                        "days_to_deadline": days_to_deadline,
                        "severity": "early",
                        "status": ms.status,
                        "suggestion": f"里程碑「{ms.name}」将在 {days_to_deadline} 天内到期，请加快进度",
                    })
            # 按严重程度排序
            severity_order = {"critical": 0, "high": 1, "warning": 2, "early": 3}
            warnings.sort(key=lambda w: severity_order.get(w["severity"], 99))
            return warnings

    def _generate_delay_suggestion(self, ms: Milestone, delay: int) -> str:
        """生成延迟建议。"""
        suggestions = []
        if delay > 14:
            suggestions.append(f"里程碑「{ms.name}」已严重逾期 {delay} 天，建议立即调整计划或申请延期")
        elif delay > 7:
            suggestions.append(f"里程碑「{ms.name}」已逾期 {delay} 天，建议增加投入或简化范围")
        else:
            suggestions.append(f"里程碑「{ms.name}」轻微逾期 {delay} 天，建议加快进度")
        # 检查依赖是否阻塞
        for dep_id in ms.dependencies:
            dep = self._milestones.get(dep_id)
            if dep and dep.status != MilestoneStatus.COMPLETED:
                suggestions.append(f"依赖里程碑「{dep.name}」未完成，可能阻塞当前进度")
        return "；".join(suggestions)

    def get_blocked_milestones(self) -> list[Milestone]:
        """获取被阻塞的里程碑（依赖未完成）。"""
        with self._lock:
            blocked: list[Milestone] = []
            for ms in self._milestones.values():
                if ms.status in (MilestoneStatus.COMPLETED, MilestoneStatus.CANCELLED):
                    continue
                for dep_id in ms.dependencies:
                    dep = self._milestones.get(dep_id)
                    if dep and dep.status != MilestoneStatus.COMPLETED:
                        blocked.append(ms)
                        break
            return blocked

    # ===== 评审管理 =====

    def add_review(
        self,
        milestone_id: str,
        reviewer: str,
        result: str,
        comments: str = "",
        action_items: Optional[list[str]] = None,
        next_review_date: str = "",
    ) -> Optional[MilestoneReview]:
        """添加评审记录。

        Args:
            milestone_id: 里程碑 ID。
            reviewer: 评审人。
            result: 评审结果（passed/passed_with_revision/major_revision/failed/deferred）。
            comments: 评审意见。
            action_items: 待办事项列表。
            next_review_date: 下次评审日期。

        Returns:
            创建的评审记录，里程碑不存在返回 None。
        """
        with self._lock:
            ms = self._milestones.get(milestone_id)
            if not ms:
                return None
            if result not in REVIEW_RESULTS:
                raise ValueError(f"未知评审结果: {result}")
            review = MilestoneReview(
                id=f"rev_{uuid.uuid4().hex[:8]}",
                reviewer=reviewer,
                review_date=datetime.now().strftime("%Y-%m-%d"),
                result=result,
                comments=comments,
                action_items=action_items or [],
                next_review_date=next_review_date,
            )
            ms.reviews.append(review)
            # 根据评审结果更新状态
            if result == "passed":
                ms.status = MilestoneStatus.COMPLETED
                ms.actual_date = datetime.now().strftime("%Y-%m-%d")
                ms.progress = 100.0
                for c in ms.acceptance_criteria:
                    c.is_met = True
                    if not c.verified_at:
                        c.verified_at = ms.actual_date
            elif result == "passed_with_revision":
                ms.status = MilestoneStatus.IN_PROGRESS
            elif result == "major_revision":
                ms.status = MilestoneStatus.IN_PROGRESS
            elif result == "failed":
                ms.status = MilestoneStatus.BLOCKED
            elif result == "deferred":
                ms.status = MilestoneStatus.DELAYED
            ms.updated_at = datetime.now().isoformat()
            return review

    def get_reviews(self, milestone_id: str) -> list[MilestoneReview]:
        """获取里程碑的评审记录。"""
        with self._lock:
            ms = self._milestones.get(milestone_id)
            if not ms:
                return []
            return list(ms.reviews)

    def get_latest_review(self, milestone_id: str) -> Optional[MilestoneReview]:
        """获取最新的评审记录。"""
        with self._lock:
            ms = self._milestones.get(milestone_id)
            if not ms or not ms.reviews:
                return None
            return ms.reviews[-1]

    # ===== 进度报告 =====

    def generate_progress_report(
        self, reference_date: Optional[str] = None
    ) -> dict[str, Any]:
        """生成进度报告。

        Args:
            reference_date: 参考日期。

        Returns:
            进度报告字典。
        """
        with self._lock:
            ref = reference_date or datetime.now().strftime("%Y-%m-%d")
            total = len(self._milestones)
            if total == 0:
                return {"reference_date": ref, "total_milestones": 0}
            # 状态统计
            status_counts: dict[str, int] = defaultdict(int)
            for ms in self._milestones.values():
                status_counts[ms.status] += 1
            # 完成率
            completed = status_counts.get(MilestoneStatus.COMPLETED, 0)
            completion_rate = round(completed / total * 100, 2)
            # 延迟情况
            delays = self.check_delays(ref)
            # 关键路径
            critical_path = self.compute_critical_path()
            # 即将到期
            upcoming = self._get_upcoming_milestones(ref, days=14)
            # 阻塞
            blocked = self.get_blocked_milestones()
            # 各里程碑详情
            milestone_details = []
            for ms in self._milestones.values():
                milestone_details.append({
                    "id": ms.id,
                    "name": ms.name,
                    "type": ms.type,
                    "type_name": MILESTONE_TYPES.get(ms.type, ms.type),
                    "planned_date": ms.planned_date,
                    "actual_date": ms.actual_date,
                    "status": ms.status,
                    "status_name": STATUS_NAMES.get(ms.status, ms.status),
                    "priority": ms.priority,
                    "progress": ms.progress,
                    "completion_rate": ms.completion_rate(),
                    "delay_days": ms.delay_days(ref),
                    "is_overdue": ms.is_overdue(ref),
                    "assignee": ms.assignee,
                })
            milestone_details.sort(key=lambda m: m["planned_date"] or "9999-12-31")
            return {
                "reference_date": ref,
                "project_start": self._project_start,
                "project_end": self._project_end,
                "total_milestones": total,
                "completed_milestones": completed,
                "completion_rate": completion_rate,
                "status_counts": dict(status_counts),
                "status_names": {
                    k: STATUS_NAMES.get(k, k) for k in status_counts
                },
                "delay_count": len(delays),
                "delays": delays,
                "critical_path": critical_path,
                "upcoming_milestones": upcoming,
                "blocked_count": len(blocked),
                "blocked_milestones": [
                    {"id": m.id, "name": m.name, "planned_date": m.planned_date}
                    for m in blocked
                ],
                "milestone_details": milestone_details,
                "summary": self._generate_report_summary(
                    total, completed, len(delays), len(blocked)
                ),
            }

    def _get_upcoming_milestones(
        self, reference_date: str, days: int = 14
    ) -> list[dict[str, Any]]:
        """获取即将到期的里程碑。"""
        with self._lock:
            try:
                ref = datetime.strptime(reference_date, "%Y-%m-%d")
            except ValueError:
                return []
            upcoming: list[dict[str, Any]] = []
            for ms in self._milestones.values():
                if ms.status in (MilestoneStatus.COMPLETED, MilestoneStatus.CANCELLED):
                    continue
                if not ms.planned_date:
                    continue
                try:
                    planned = datetime.strptime(ms.planned_date, "%Y-%m-%d")
                except ValueError:
                    continue
                diff = (planned - ref).days
                if 0 <= diff <= days:
                    upcoming.append({
                        "milestone_id": ms.id,
                        "name": ms.name,
                        "planned_date": ms.planned_date,
                        "days_to_deadline": diff,
                        "progress": ms.progress,
                        "priority": ms.priority,
                    })
            upcoming.sort(key=lambda x: x["days_to_deadline"])
            return upcoming

    def _generate_report_summary(
        self, total: int, completed: int, delay_count: int, blocked_count: int
    ) -> str:
        """生成报告摘要。"""
        parts: list[str] = []
        parts.append(f"共 {total} 个里程碑，已完成 {completed} 个")
        rate = round(completed / max(total, 1) * 100, 1)
        parts.append(f"完成率 {rate}%")
        if delay_count > 0:
            parts.append(f"有 {delay_count} 个里程碑存在延迟预警")
        if blocked_count > 0:
            parts.append(f"有 {blocked_count} 个里程碑被阻塞")
        if delay_count == 0 and blocked_count == 0:
            parts.append("整体进度正常")
        return "；".join(parts)

    # ===== 历史分析 =====

    def save_snapshot(self, note: str = "") -> bool:
        """保存当前状态快照到历史。"""
        with self._lock:
            snapshot = {
                "snapshot_time": datetime.now().isoformat(),
                "total_milestones": len(self._milestones),
                "completed": sum(
                    1 for m in self._milestones.values()
                    if m.status == MilestoneStatus.COMPLETED
                ),
                "in_progress": sum(
                    1 for m in self._milestones.values()
                    if m.status == MilestoneStatus.IN_PROGRESS
                ),
                "delayed": sum(
                    1 for m in self._milestones.values()
                    if m.status == MilestoneStatus.DELAYED
                ),
                "blocked": sum(
                    1 for m in self._milestones.values()
                    if m.status == MilestoneStatus.BLOCKED
                ),
                "avg_progress": round(
                    sum(m.progress for m in self._milestones.values())
                    / max(len(self._milestones), 1), 2
                ),
                "note": note,
            }
            self._history.append(snapshot)
            return True

    def analyze_history(self) -> dict[str, Any]:
        """分析历史趋势。"""
        with self._lock:
            if not self._history:
                return {}
            snapshots = self._history
            # 进度趋势
            progress_trend = [s["avg_progress"] for s in snapshots]
            completion_trend = [s["completed"] for s in snapshots]
            # 计算趋势方向
            if len(progress_trend) >= 2:
                recent_avg = sum(progress_trend[-3:]) / min(3, len(progress_trend))
                earlier_avg = sum(progress_trend[:-3]) / max(len(progress_trend) - 3, 1)
                trend_direction = "上升" if recent_avg > earlier_avg else (
                    "下降" if recent_avg < earlier_avg else "平稳"
                )
            else:
                trend_direction = "数据不足"
            return {
                "snapshot_count": len(snapshots),
                "first_snapshot": snapshots[0]["snapshot_time"] if snapshots else "",
                "last_snapshot": snapshots[-1]["snapshot_time"] if snapshots else "",
                "progress_trend": progress_trend,
                "completion_trend": completion_trend,
                "trend_direction": trend_direction,
                "current_completion": snapshots[-1]["completed"] if snapshots else 0,
                "current_avg_progress": snapshots[-1]["avg_progress"] if snapshots else 0,
                "snapshots": snapshots,
            }

    def predict_completion(self) -> dict[str, Any]:
        """基于历史趋势预测完成时间。

        Returns:
            预测结果字典。
        """
        with self._lock:
            if len(self._history) < 2:
                return {"predictable": False, "reason": "历史数据不足"}
            # 计算平均进度增长率
            progresses = [s["avg_progress"] for s in self._history]
            # 简单线性回归
            n = len(progresses)
            x = list(range(n))
            x_mean = sum(x) / n
            y_mean = sum(progresses) / n
            numerator = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, progresses))
            denominator = sum((xi - x_mean) ** 2 for xi in x)
            if denominator == 0:
                return {"predictable": False, "reason": "进度无变化"}
            slope = numerator / denominator
            if slope <= 0:
                return {"predictable": False, "reason": "进度未增长"}
            # 预测达到 100% 所需的快照数
            remaining = 100 - progresses[-1]
            snapshots_needed = remaining / slope
            # 假设每次快照间隔约 7 天
            days_needed = int(snapshots_needed * 7)
            try:
                predicted_date = datetime.now() + timedelta(days=days_needed)
            except Exception:
                return {"predictable": False, "reason": "预测计算异常"}
            return {
                "predictable": True,
                "current_progress": progresses[-1],
                "growth_rate_per_snapshot": round(slope, 2),
                "remaining_progress": round(remaining, 2),
                "estimated_days": days_needed,
                "predicted_completion_date": predicted_date.strftime("%Y-%m-%d"),
                "confidence": "low" if n < 5 else ("medium" if n < 10 else "high"),
            }

    def generate_improvement_suggestions(self) -> list[dict[str, str]]:
        """生成改进建议。"""
        with self._lock:
            suggestions: list[dict[str, str]] = []
            # 检查延迟
            delays = self.check_delays()
            if delays:
                critical_delays = [d for d in delays if d["severity"] == "critical"]
                if critical_delays:
                    suggestions.append({
                        "type": "delay",
                        "priority": "critical",
                        "suggestion": f"有 {len(critical_delays)} 个里程碑严重逾期，建议立即调整计划",
                    })
            # 检查阻塞
            blocked = self.get_blocked_milestones()
            if blocked:
                suggestions.append({
                    "type": "blockage",
                    "priority": "high",
                    "suggestion": f"有 {len(blocked)} 个里程碑被阻塞，建议优先解决依赖问题",
                })
            # 检查验收标准
            for ms in self._milestones.values():
                if ms.status == MilestoneStatus.IN_PROGRESS:
                    rate = ms.completion_rate()
                    if rate < 50 and ms.progress > 50:
                        suggestions.append({
                            "type": "criteria",
                            "priority": "medium",
                            "suggestion": f"里程碑「{ms.name}」进度 {ms.progress}% 但验收标准仅完成 {rate}%，建议同步推进",
                        })
            # 检查无负责人的里程碑
            no_assignee = [m for m in self._milestones.values() if not m.assignee]
            if no_assignee:
                suggestions.append({
                    "type": "assignment",
                    "priority": "medium",
                    "suggestion": f"有 {len(no_assignee)} 个里程碑未指定负责人，建议明确分工",
                })
            # 检查计划日期缺失
            no_date = [m for m in self._milestones.values() if not m.planned_date]
            if no_date:
                suggestions.append({
                    "type": "planning",
                    "priority": "high",
                    "suggestion": f"有 {len(no_date)} 个里程碑未设置计划日期，建议完善计划",
                })
            if not suggestions:
                suggestions.append({
                    "type": "positive",
                    "priority": "low",
                    "suggestion": "里程碑管理状况良好，继续保持",
                })
            return suggestions

    # ===== 统计 =====

    def compute_statistics(self) -> dict[str, Any]:
        """计算里程碑统计指标。"""
        with self._lock:
            total = len(self._milestones)
            if total == 0:
                return {"total_milestones": 0}
            status_counts: dict[str, int] = defaultdict(int)
            type_counts: dict[str, int] = defaultdict(int)
            priority_counts: dict[str, int] = defaultdict(int)
            total_progress = 0.0
            total_delay = 0
            delay_count = 0
            for ms in self._milestones.values():
                status_counts[ms.status] += 1
                type_counts[ms.type] += 1
                priority_counts[ms.priority] += 1
                total_progress += ms.progress
                delay = ms.delay_days()
                if delay > 0:
                    total_delay += delay
                    delay_count += 1
            return {
                "total_milestones": total,
                "status_counts": dict(status_counts),
                "type_counts": dict(type_counts),
                "priority_counts": dict(priority_counts),
                "completed": status_counts.get(MilestoneStatus.COMPLETED, 0),
                "in_progress": status_counts.get(MilestoneStatus.IN_PROGRESS, 0),
                "delayed": status_counts.get(MilestoneStatus.DELAYED, 0),
                "blocked": status_counts.get(MilestoneStatus.BLOCKED, 0),
                "completion_rate": round(
                    status_counts.get(MilestoneStatus.COMPLETED, 0) / total * 100, 2
                ),
                "avg_progress": round(total_progress / total, 2),
                "avg_delay_days": round(total_delay / max(delay_count, 1), 1),
                "delayed_count": delay_count,
                "total_criteria": sum(
                    len(ms.acceptance_criteria) for ms in self._milestones.values()
                ),
                "met_criteria": sum(
                    1 for ms in self._milestones.values()
                    for c in ms.acceptance_criteria if c.is_met
                ),
            }

    def summary(self) -> dict[str, Any]:
        """返回追踪器汇总信息。"""
        with self._lock:
            return {
                "milestone_count": len(self._milestones),
                "history_count": len(self._history),
                "project_start": self._project_start,
                "project_end": self._project_end,
                "available_types": list(MILESTONE_TYPES.keys()),
                "available_statuses": list(STATUS_NAMES.keys()),
            }

    # ===== 导出 =====

    def export_markdown(self) -> str:
        """导出为 Markdown 报告。"""
        with self._lock:
            lines: list[str] = []
            lines.append("# 里程碑追踪报告")
            lines.append("")
            lines.append(f"- **项目周期**：{self._project_start} ~ {self._project_end}")
            stats = self.compute_statistics()
            lines.append(f"- **里程碑总数**：{stats.get('total_milestones', 0)}")
            lines.append(f"- **已完成**：{stats.get('completed', 0)}")
            lines.append(f"- **完成率**：{stats.get('completion_rate', 0)}%")
            lines.append(f"- **平均进度**：{stats.get('avg_progress', 0)}%")
            lines.append("")
            lines.append("## 里程碑列表")
            lines.append("")
            lines.append("| 里程碑 | 类型 | 计划日期 | 实际日期 | 状态 | 优先级 | 进度 | 延迟 |")
            lines.append("|--------|------|----------|----------|------|--------|------|------|")
            for ms in sorted(
                self._milestones.values(),
                key=lambda m: m.planned_date or "9999-12-31",
            ):
                delay = ms.delay_days()
                delay_str = f"{delay}天" if delay > 0 else "-"
                lines.append(
                    f"| {ms.name} | {MILESTONE_TYPES.get(ms.type, ms.type)} | "
                    f"{ms.planned_date} | {ms.actual_date or '-'} | "
                    f"{STATUS_NAMES.get(ms.status, ms.status)} | "
                    f"{MILESTONE_PRIORITY.get(ms.priority, ms.priority)} | "
                    f"{ms.progress:.0f}% | {delay_str} |"
                )
            lines.append("")
            # 延迟预警
            delays = self.check_delays()
            if delays:
                lines.append("## 延迟预警")
                lines.append("")
                lines.append("| 里程碑 | 计划日期 | 延迟天数 | 严重程度 | 建议 |")
                lines.append("|--------|----------|----------|----------|------|")
                for d in delays:
                    lines.append(
                        f"| {d['name']} | {d['planned_date']} | "
                        f"{d.get('delay_days', 0)}天 | {d['severity']} | "
                        f"{d['suggestion']} |"
                    )
                lines.append("")
            # 改进建议
            suggestions = self.generate_improvement_suggestions()
            if suggestions:
                lines.append("## 改进建议")
                lines.append("")
                for s in suggestions:
                    lines.append(f"- **[{s['priority']}]** {s['suggestion']}")
                lines.append("")
            return "\n".join(lines)

    def export_dict(self) -> dict[str, Any]:
        """导出为字典。"""
        with self._lock:
            return {
                "project_start": self._project_start,
                "project_end": self._project_end,
                "milestones": [m.to_dict() for m in self._milestones.values()],
                "statistics": self.compute_statistics(),
                "exported_at": datetime.now().isoformat(),
            }
