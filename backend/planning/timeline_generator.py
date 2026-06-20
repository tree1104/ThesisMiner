"""时间线生成器模块

提供完整的研究时间线生成能力，包括：
    - 甘特图数据生成、关键路径分析、里程碑标记
    - 时间冲突检测、资源平衡、优化建议
    - 多时间线对比、历史时间线分析、基准对比
    - 时间线导出（JSON/CSV/Markdown 表格/HTML）
    - 完整的时间线算法、可视化数据

设计原则：
    1. 零外部依赖：仅使用 Python 标准库
    2. 线程安全：所有公共方法通过 RLock 保护
    3. 可持久化：基于 dataclass，支持序列化
    4. 可视化友好：生成可直接用于前端渲染的数据

核心数据结构：
    - TimelineTask: 时间线任务（含起止、依赖、资源）
    - Timeline: 时间线（含任务、里程碑、关键路径）
    - CriticalPath: 关键路径（含任务链、总工期、缓冲）
    - TimelineConflict: 时间冲突（含冲突类型、涉及任务）
"""
from __future__ import annotations

import csv
import io
import json
import math
import re
import threading
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Any, Iterable, Optional


# ===== 常量定义 =====

# 任务状态
TASK_STATUS = {
    "pending": "待开始",
    "in_progress": "进行中",
    "completed": "已完成",
    "blocked": "已阻塞",
    "deferred": "已推迟",
}

# 任务优先级
TASK_PRIORITY = {
    "critical": "关键",
    "high": "高",
    "medium": "中",
    "low": "低",
}

# 优先级数值映射（用于排序与关键路径计算）
PRIORITY_WEIGHTS = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}

# 冲突类型
CONFLICT_TYPES = {
    "time_overlap": "时间重叠（同一资源并行任务）",
    "dependency_violation": "依赖违反（前置未完成即开始）",
    "resource_overload": "资源过载（超出可用量）",
    "deadline_conflict": "截止冲突（与硬性截止日冲突）",
    "milestone_conflict": "里程碑冲突（里程碑落在非工作日）",
}

# 工作日模式（周一至周五）
DEFAULT_WORKDAYS = {0, 1, 2, 3, 4}  # Monday=0 .. Sunday=6

# 默认节假日（示例，可扩展）
DEFAULT_HOLIDAYS = {
    "2026-01-01": "元旦",
    "2026-02-10": "春节",
    "2026-02-11": "春节",
    "2026-02-12": "春节",
    "2026-04-04": "清明节",
    "2026-05-01": "劳动节",
    "2026-06-10": "端午节",
    "2026-09-16": "中秋节",
    "2026-10-01": "国庆节",
    "2026-10-02": "国庆节",
    "2026-10-03": "国庆节",
}

# 时间线视图粒度
TIMELINE_GRANULARITY = {
    "day": "按天",
    "week": "按周",
    "month": "按月",
    "quarter": "按季度",
}

# 甘特图默认颜色（按优先级）
GANTT_COLORS = {
    "critical": "#dc3545",
    "high": "#fd7e14",
    "medium": "#0d6efd",
    "low": "#198754",
}

# 里程碑标记符号
MILESTONE_SYMBOLS = {
    "major": "★",
    "minor": "●",
    "review": "◆",
    "deadline": "⛔",
}

# 优化建议类型
OPTIMIZATION_TYPES = {
    "parallelize": "可并行化（无依赖任务串行排列）",
    "split": "可拆分（大任务拆为小任务）",
    "merge": "可合并（小任务合并）",
    "buffer": "需增加缓冲（关键路径无缓冲）",
    "resource_balance": "资源平衡（负载不均）",
    "dependency_simplify": "简化依赖（冗余依赖）",
}


# ===== 数据结构 =====


@dataclass
class TimelineTask:
    """时间线任务数据结构。

    Attributes:
        id: 任务 ID。
        name: 任务名称。
        start_date: 开始日期（ISO 格式）。
        end_date: 结束日期（ISO 格式）。
        duration_days: 持续天数。
        progress: 完成进度（0-100）。
        status: 状态。
        priority: 优先级。
        dependencies: 依赖任务 ID 列表。
        assignee: 负责人。
        resources: 所需资源列表。
        milestone: 关联里程碑（如有）。
        is_milestone: 是否为里程碑节点。
        milestone_type: 里程碑类型（major/minor/review/deadline）。
        color: 显示颜色。
        metadata: 扩展元数据。
    """

    id: str = ""
    name: str = ""
    start_date: str = ""
    end_date: str = ""
    duration_days: int = 0
    progress: float = 0.0
    status: str = "pending"
    priority: str = "medium"
    dependencies: list[str] = field(default_factory=list)
    assignee: str = ""
    resources: list[str] = field(default_factory=list)
    milestone: str = ""
    is_milestone: bool = False
    milestone_type: str = ""
    color: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TimelineTask":
        """从字典构造任务实例。"""
        defaults = cls().__dict__
        merged = {**defaults, **{k: v for k, v in data.items() if k in defaults}}
        return cls(**merged)

    def is_overdue(self, reference_date: Optional[str] = None) -> bool:
        """判断任务是否逾期。"""
        if not self.end_date:
            return False
        ref = reference_date or datetime.now().strftime("%Y-%m-%d")
        return ref > self.end_date and self.status != "completed"

    def overlaps(self, other: "TimelineTask") -> bool:
        """判断与另一任务是否时间重叠。

        Args:
            other: 另一任务。

        Returns:
            是否重叠。
        """
        if not self.start_date or not self.end_date:
            return False
        if not other.start_date or not other.end_date:
            return False
        return not (self.end_date < other.start_date or other.end_date < self.start_date)

    def workdays(self, holidays: Optional[set[str]] = None, workdays: Optional[set[int]] = None) -> int:
        """计算工作日天数。

        Args:
            holidays: 节假日集合（ISO 日期字符串）。
            workdays: 工作日集合（0=周一..6=周日）。

        Returns:
            工作日天数。
        """
        if not self.start_date or not self.end_date:
            return 0
        holidays = holidays or set()
        workdays = workdays or DEFAULT_WORKDAYS
        try:
            start = datetime.strptime(self.start_date, "%Y-%m-%d")
            end = datetime.strptime(self.end_date, "%Y-%m-%d")
        except ValueError:
            return 0
        count = 0
        current = start
        while current <= end:
            iso = current.strftime("%Y-%m-%d")
            if current.weekday() in workdays and iso not in holidays:
                count += 1
            current += timedelta(days=1)
        return count


@dataclass
class TimelineConflict:
    """时间冲突数据结构。

    Attributes:
        id: 冲突 ID。
        conflict_type: 冲突类型。
        description: 冲突描述。
        task_ids: 涉及任务 ID 列表。
        severity: 严重程度（critical/high/medium/low）。
        suggestion: 解决建议。
    """

    id: str = ""
    conflict_type: str = "time_overlap"
    description: str = ""
    task_ids: list[str] = field(default_factory=list)
    severity: str = "medium"
    suggestion: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return asdict(self)


@dataclass
class CriticalPath:
    """关键路径数据结构。

    Attributes:
        task_ids: 关键路径上的任务 ID 序列。
        total_duration: 总工期（天）。
        total_workdays: 总工作日。
        buffer: 总缓冲（天）。
        tasks: 关键路径上的任务列表。
        is_feasible: 是否可行（无循环依赖）。
    """

    task_ids: list[str] = field(default_factory=list)
    total_duration: int = 0
    total_workdays: int = 0
    buffer: int = 0
    tasks: list[TimelineTask] = field(default_factory=list)
    is_feasible: bool = True

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "task_ids": self.task_ids,
            "total_duration": self.total_duration,
            "total_workdays": self.total_workdays,
            "buffer": self.buffer,
            "tasks": [t.to_dict() for t in self.tasks],
            "is_feasible": self.is_feasible,
        }


@dataclass
class Timeline:
    """时间线数据结构。

    Attributes:
        id: 时间线 ID。
        name: 时间线名称。
        tasks: 任务列表。
        milestones: 里程碑任务列表。
        start_date: 时间线开始日期。
        end_date: 时间线结束日期。
        critical_path: 关键路径。
        conflicts: 冲突列表。
        created_at: 创建时间。
        updated_at: 更新时间。
        metadata: 扩展元数据。
    """

    id: str = ""
    name: str = ""
    tasks: list[TimelineTask] = field(default_factory=list)
    milestones: list[TimelineTask] = field(default_factory=list)
    start_date: str = ""
    end_date: str = ""
    critical_path: Optional[CriticalPath] = None
    conflicts: list[TimelineConflict] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "id": self.id,
            "name": self.name,
            "tasks": [t.to_dict() for t in self.tasks],
            "milestones": [m.to_dict() for m in self.milestones],
            "start_date": self.start_date,
            "end_date": self.end_date,
            "critical_path": self.critical_path.to_dict() if self.critical_path else None,
            "conflicts": [c.to_dict() for c in self.conflicts],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }


@dataclass
class OptimizationSuggestion:
    """优化建议数据结构。

    Attributes:
        id: 建议 ID。
        suggestion_type: 建议类型。
        description: 建议描述。
        task_ids: 涉及任务 ID 列表。
        expected_benefit: 预期收益。
        difficulty: 实施难度（easy/medium/hard）。
    """

    id: str = ""
    suggestion_type: str = "parallelize"
    description: str = ""
    task_ids: list[str] = field(default_factory=list)
    expected_benefit: str = ""
    difficulty: str = "medium"

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return asdict(self)


# ===== 主类实现 =====


class TimelineGenerator:
    """时间线生成器主类。

    提供甘特图数据生成、关键路径分析、里程碑标记、时间冲突检测、
    资源平衡、优化建议、多时间线对比、历史时间线分析、基准对比、
    时间线导出（JSON/CSV/Markdown/HTML）等能力。

    线程安全：所有公共方法通过 RLock 保护。
    """

    def __init__(
        self,
        workdays: Optional[set[int]] = None,
        holidays: Optional[set[str]] = None,
    ):
        """初始化时间线生成器。

        Args:
            workdays: 工作日集合（0=周一..6=周日），默认周一至周五。
            holidays: 节假日集合（ISO 日期字符串）。
        """
        self._lock = threading.RLock()
        self._timelines: dict[str, Timeline] = {}
        self._history: list[dict[str, Any]] = []
        self._workdays = workdays if workdays is not None else set(DEFAULT_WORKDAYS)
        self._holidays = holidays if holidays is not None else set(DEFAULT_HOLIDAYS.keys())

    # ===== 时间线创建 =====

    def create_timeline(
        self,
        name: str,
        start_date: str,
        end_date: str,
        tasks: Optional[list[dict[str, Any]]] = None,
    ) -> Timeline:
        """创建时间线。

        Args:
            name: 时间线名称。
            start_date: 开始日期（ISO 格式）。
            end_date: 结束日期（ISO 格式）。
            tasks: 任务字典列表（可选，后续可添加）。

        Returns:
            创建的 Timeline 实例。
        """
        with self._lock:
            # 验证日期
            try:
                start = datetime.strptime(start_date, "%Y-%m-%d")
                end = datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError as e:
                raise ValueError(f"日期格式错误: {e}")
            if end <= start:
                raise ValueError("结束日期必须晚于开始日期")

            timeline_id = f"tl_{uuid.uuid4().hex[:12]}"
            timeline = Timeline(
                id=timeline_id,
                name=name,
                start_date=start_date,
                end_date=end_date,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
            )

            # 添加初始任务
            if tasks:
                for t in tasks:
                    self._add_task_internal(timeline, t)

            # 自动计算关键路径与冲突
            timeline.critical_path = self._compute_critical_path(timeline)
            timeline.conflicts = self._detect_conflicts(timeline)

            self._timelines[timeline_id] = timeline
            return timeline

    def add_task(
        self,
        timeline_id: str,
        name: str,
        start_date: str,
        end_date: str,
        priority: str = "medium",
        dependencies: Optional[list[str]] = None,
        assignee: str = "",
        resources: Optional[list[str]] = None,
        is_milestone: bool = False,
        milestone_type: str = "",
        progress: float = 0.0,
        status: str = "pending",
    ) -> Optional[TimelineTask]:
        """向时间线添加任务。

        Args:
            timeline_id: 时间线 ID。
            name: 任务名称。
            start_date: 开始日期。
            end_date: 结束日期。
            priority: 优先级。
            dependencies: 依赖任务 ID 列表。
            assignee: 负责人。
            resources: 所需资源列表。
            is_milestone: 是否为里程碑。
            milestone_type: 里程碑类型。
            progress: 完成进度。
            status: 状态。

        Returns:
            创建的任务，时间线不存在返回 None。
        """
        with self._lock:
            timeline = self._timelines.get(timeline_id)
            if not timeline:
                return None
            task_data = {
                "name": name,
                "start_date": start_date,
                "end_date": end_date,
                "priority": priority,
                "dependencies": dependencies or [],
                "assignee": assignee,
                "resources": resources or [],
                "is_milestone": is_milestone,
                "milestone_type": milestone_type,
                "progress": progress,
                "status": status,
            }
            task = self._add_task_internal(timeline, task_data)
            # 重新计算关键路径与冲突
            timeline.critical_path = self._compute_critical_path(timeline)
            timeline.conflicts = self._detect_conflicts(timeline)
            timeline.updated_at = datetime.now().isoformat()
            return task

    def _add_task_internal(
        self, timeline: Timeline, data: dict[str, Any]
    ) -> TimelineTask:
        """内部方法：向时间线添加任务（不加锁）。

        Args:
            timeline: 时间线实例。
            data: 任务数据字典。

        Returns:
            创建的任务。
        """
        # 计算持续天数
        start_date = data.get("start_date", "")
        end_date = data.get("end_date", "")
        duration = 0
        if start_date and end_date:
            try:
                start = datetime.strptime(start_date, "%Y-%m-%d")
                end = datetime.strptime(end_date, "%Y-%m-%d")
                duration = max(1, (end - start).days + 1)
            except ValueError:
                duration = 0

        priority = data.get("priority", "medium")
        is_milestone = data.get("is_milestone", False)
        task = TimelineTask(
            id=data.get("id", f"task_{uuid.uuid4().hex[:8]}"),
            name=data.get("name", ""),
            start_date=start_date,
            end_date=end_date,
            duration_days=duration,
            progress=data.get("progress", 0.0),
            status=data.get("status", "pending"),
            priority=priority,
            dependencies=data.get("dependencies", []),
            assignee=data.get("assignee", ""),
            resources=data.get("resources", []),
            milestone=data.get("milestone", ""),
            is_milestone=is_milestone,
            milestone_type=data.get("milestone_type", ""),
            color=data.get("color", GANTT_COLORS.get(priority, "#0d6efd")),
            metadata=data.get("metadata", {}),
        )
        if is_milestone:
            timeline.milestones.append(task)
        else:
            timeline.tasks.append(task)
        return task

    # ===== 时间线查询 =====

    def get_timeline(self, timeline_id: str) -> Optional[Timeline]:
        """获取时间线。"""
        with self._lock:
            return self._timelines.get(timeline_id)

    def list_timelines(self) -> list[Timeline]:
        """列出所有时间线。"""
        with self._lock:
            return list(self._timelines.values())

    def delete_timeline(self, timeline_id: str) -> bool:
        """删除时间线。"""
        with self._lock:
            if timeline_id in self._timelines:
                tl = self._timelines[timeline_id]
                self._history.append({
                    "timeline_id": timeline_id,
                    "name": tl.name,
                    "task_count": len(tl.tasks),
                    "duration_days": self._compute_total_duration(tl),
                    "deleted_at": datetime.now().isoformat(),
                })
                del self._timelines[timeline_id]
                return True
            return False

    def get_task(self, timeline_id: str, task_id: str) -> Optional[TimelineTask]:
        """获取时间线中的任务。"""
        with self._lock:
            timeline = self._timelines.get(timeline_id)
            if not timeline:
                return None
            for t in timeline.tasks + timeline.milestones:
                if t.id == task_id:
                    return t
            return None

    def update_task(
        self,
        timeline_id: str,
        task_id: str,
        updates: dict[str, Any],
    ) -> bool:
        """更新任务属性。

        Args:
            timeline_id: 时间线 ID。
            task_id: 任务 ID。
            updates: 更新字段字典。

        Returns:
            是否更新成功。
        """
        with self._lock:
            timeline = self._timelines.get(timeline_id)
            if not timeline:
                return False
            for t in timeline.tasks + timeline.milestones:
                if t.id == task_id:
                    for k, v in updates.items():
                        if hasattr(t, k):
                            setattr(t, k, v)
                    # 重新计算持续天数
                    if "start_date" in updates or "end_date" in updates:
                        if t.start_date and t.end_date:
                            try:
                                start = datetime.strptime(t.start_date, "%Y-%m-%d")
                                end = datetime.strptime(t.end_date, "%Y-%m-%d")
                                t.duration_days = max(1, (end - start).days + 1)
                            except ValueError:
                                pass
                    timeline.critical_path = self._compute_critical_path(timeline)
                    timeline.conflicts = self._detect_conflicts(timeline)
                    timeline.updated_at = datetime.now().isoformat()
                    return True
            return False

    def remove_task(self, timeline_id: str, task_id: str) -> bool:
        """删除任务。"""
        with self._lock:
            timeline = self._timelines.get(timeline_id)
            if not timeline:
                return False
            for collection in (timeline.tasks, timeline.milestones):
                for i, t in enumerate(collection):
                    if t.id == task_id:
                        collection.pop(i)
                        # 移除其他任务对该任务的依赖
                        for other in timeline.tasks + timeline.milestones:
                            if task_id in other.dependencies:
                                other.dependencies.remove(task_id)
                        timeline.critical_path = self._compute_critical_path(timeline)
                        timeline.conflicts = self._detect_conflicts(timeline)
                        timeline.updated_at = datetime.now().isoformat()
                        return True
            return False

    # ===== 关键路径分析 =====

    def _compute_critical_path(self, timeline: Timeline) -> CriticalPath:
        """计算关键路径（基于最长路径算法）。

        使用拓扑排序 + 动态规划求最长路径。

        Args:
            timeline: 时间线实例。

        Returns:
            关键路径实例。
        """
        tasks = timeline.tasks + timeline.milestones
        if not tasks:
            return CriticalPath()

        # 构建任务映射
        task_map: dict[str, TimelineTask] = {t.id: t for t in tasks}
        # 构建邻接表（依赖 -> 后继）
        successors: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = {t.id: 0 for t in tasks}
        for t in tasks:
            for dep in t.dependencies:
                if dep in task_map:
                    successors[dep].append(t.id)
                    in_degree[t.id] += 1

        # 拓扑排序（Kahn 算法）
        queue: deque[str] = deque()
        for tid, deg in in_degree.items():
            if deg == 0:
                queue.append(tid)
        topo_order: list[str] = []
        while queue:
            tid = queue.popleft()
            topo_order.append(tid)
            for succ in successors[tid]:
                in_degree[succ] -= 1
                if in_degree[succ] == 0:
                    queue.append(succ)

        # 检测循环依赖
        if len(topo_order) != len(tasks):
            return CriticalPath(is_feasible=False)

        # 动态规划求最长路径
        # earliest_finish[tid] = max(earliest_finish[dep]) + duration[tid]
        earliest_start: dict[str, int] = {}
        earliest_finish: dict[str, int] = {}
        predecessor: dict[str, Optional[str]] = {t.id: None for t in tasks}

        for tid in topo_order:
            task = task_map[tid]
            es = 0
            for dep in task.dependencies:
                if dep in earliest_finish:
                    if earliest_finish[dep] > es:
                        es = earliest_finish[dep]
                        predecessor[tid] = dep
            earliest_start[tid] = es
            earliest_finish[tid] = es + max(task.duration_days, 1)

        # 找到结束最晚的任务
        if not earliest_finish:
            return CriticalPath()
        end_tid = max(earliest_finish, key=earliest_finish.get)
        total_duration = earliest_finish[end_tid]

        # 回溯关键路径
        path: list[str] = []
        current: Optional[str] = end_tid
        while current is not None:
            path.append(current)
            current = predecessor[current]
        path.reverse()

        # 计算工作日
        total_workdays = 0
        path_tasks: list[TimelineTask] = []
        for tid in path:
            task = task_map[tid]
            path_tasks.append(task)
            total_workdays += task.workdays(self._holidays, self._workdays)

        # 计算缓冲（时间线总长 - 关键路径长）
        tl_total = self._compute_total_duration(timeline)
        buffer = max(0, tl_total - total_duration)

        return CriticalPath(
            task_ids=path,
            total_duration=total_duration,
            total_workdays=total_workdays,
            buffer=buffer,
            tasks=path_tasks,
            is_feasible=True,
        )

    def _compute_total_duration(self, timeline: Timeline) -> int:
        """计算时间线总工期（天）。"""
        tasks = timeline.tasks + timeline.milestones
        if not tasks:
            return 0
        try:
            starts = [datetime.strptime(t.start_date, "%Y-%m-%d") for t in tasks if t.start_date]
            ends = [datetime.strptime(t.end_date, "%Y-%m-%d") for t in tasks if t.end_date]
            if not starts or not ends:
                return 0
            return (max(ends) - min(starts)).days + 1
        except ValueError:
            return 0

    def analyze_critical_path(self, timeline_id: str) -> dict[str, Any]:
        """分析关键路径详情。

        Args:
            timeline_id: 时间线 ID。

        Returns:
            分析结果字典。
        """
        with self._lock:
            timeline = self._timelines.get(timeline_id)
            if not timeline or not timeline.critical_path:
                return {}
            cp = timeline.critical_path
            # 各任务缓冲分析
            task_slacks: list[dict[str, Any]] = []
            for task in timeline.tasks + timeline.milestones:
                if task.id in cp.task_ids:
                    slack = 0
                    on_cp = True
                else:
                    # 计算非关键任务的总浮动时间
                    slack = self._compute_task_slack(timeline, task)
                    on_cp = False
                task_slacks.append({
                    "task_id": task.id,
                    "name": task.name,
                    "on_critical_path": on_cp,
                    "slack_days": slack,
                    "duration_days": task.duration_days,
                })
            return {
                "timeline_id": timeline_id,
                "critical_path": cp.to_dict(),
                "total_duration": cp.total_duration,
                "total_workdays": cp.total_workdays,
                "buffer": cp.buffer,
                "is_feasible": cp.is_feasible,
                "task_slacks": task_slacks,
                "critical_task_count": len(cp.task_ids),
                "total_task_count": len(timeline.tasks) + len(timeline.milestones),
            }

    def _compute_task_slack(self, timeline: Timeline, task: TimelineTask) -> int:
        """计算任务总浮动时间（Total Slack）。

        Args:
            timeline: 时间线实例。
            task: 任务实例。

        Returns:
            浮动天数。
        """
        # 简化算法：latest_finish - earliest_finish
        # 这里用近似：时间线总长 - 任务结束到时间线结束的距离 - 任务开始到时间线开始的距离 - 任务工期
        if not timeline.critical_path:
            return 0
        tl_total = timeline.critical_path.total_duration
        try:
            task_duration = max(task.duration_days, 1)
            # 简化：假设非关键任务的浮动 = 总工期 - 该任务工期（粗略估计）
            return max(0, tl_total - task_duration * 2)
        except Exception:
            return 0

    # ===== 冲突检测 =====

    def _detect_conflicts(self, timeline: Timeline) -> list[TimelineConflict]:
        """检测时间线冲突。

        Args:
            timeline: 时间线实例。

        Returns:
            冲突列表。
        """
        conflicts: list[TimelineConflict] = []
        tasks = timeline.tasks + timeline.milestones

        # 1. 时间重叠冲突（同一负责人并行任务）
        assignee_tasks: dict[str, list[TimelineTask]] = defaultdict(list)
        for t in tasks:
            if t.assignee and t.start_date and t.end_date:
                assignee_tasks[t.assignee].append(t)
        for assignee, atasks in assignee_tasks.items():
            for i in range(len(atasks)):
                for j in range(i + 1, len(atasks)):
                    if atasks[i].overlaps(atasks[j]):
                        conflicts.append(TimelineConflict(
                            id=f"conflict_{uuid.uuid4().hex[:8]}",
                            conflict_type="time_overlap",
                            description=f"负责人「{assignee}」的任务「{atasks[i].name}」与「{atasks[j].name}」时间重叠",
                            task_ids=[atasks[i].id, atasks[j].id],
                            severity="high",
                            suggestion="调整其中一项任务的时间或重新分配负责人",
                        ))

        # 2. 依赖违反冲突
        task_map = {t.id: t for t in tasks}
        for t in tasks:
            for dep_id in t.dependencies:
                if dep_id in task_map:
                    dep = task_map[dep_id]
                    if dep.end_date and t.start_date and dep.end_date > t.start_date:
                        conflicts.append(TimelineConflict(
                            id=f"conflict_{uuid.uuid4().hex[:8]}",
                            conflict_type="dependency_violation",
                            description=f"任务「{t.name}」在依赖「{dep.name}」完成前开始",
                            task_ids=[t.id, dep_id],
                            severity="critical",
                            suggestion=f"将「{t.name}」的开始日期调整至「{dep.name}」结束之后",
                        ))

        # 3. 资源过载冲突（同一资源并行任务过多）
        resource_tasks: dict[str, list[TimelineTask]] = defaultdict(list)
        for t in tasks:
            for r in t.resources:
                if t.start_date and t.end_date:
                    resource_tasks[r].append(t)
        for resource, rtasks in resource_tasks.items():
            # 检测同一资源在同一时间段被多个任务使用
            for i in range(len(rtasks)):
                for j in range(i + 1, len(rtasks)):
                    if rtasks[i].overlaps(rtasks[j]):
                        conflicts.append(TimelineConflict(
                            id=f"conflict_{uuid.uuid4().hex[:8]}",
                            conflict_type="resource_overload",
                            description=f"资源「{resource}」同时被「{rtasks[i].name}」与「{rtasks[j].name}」占用",
                            task_ids=[rtasks[i].id, rtasks[j].id],
                            severity="medium",
                            suggestion="错开任务时间或增加资源",
                        ))

        # 4. 截止冲突（任务超出时间线结束日期）
        for t in tasks:
            if t.end_date and timeline.end_date and t.end_date > timeline.end_date:
                conflicts.append(TimelineConflict(
                    id=f"conflict_{uuid.uuid4().hex[:8]}",
                    conflict_type="deadline_conflict",
                    description=f"任务「{t.name}」结束日期超出时间线截止",
                    task_ids=[t.id],
                    severity="high",
                    suggestion="压缩任务工期或延长整体时间线",
                ))

        return conflicts

    def get_conflicts(self, timeline_id: str) -> list[TimelineConflict]:
        """获取时间线冲突列表。"""
        with self._lock:
            timeline = self._timelines.get(timeline_id)
            if not timeline:
                return []
            return timeline.conflicts

    def resolve_conflict(
        self, timeline_id: str, conflict_id: str, resolution: str = "auto"
    ) -> bool:
        """解决冲突（标记为已处理）。

        Args:
            timeline_id: 时间线 ID。
            conflict_id: 冲突 ID。
            resolution: 解决方式（auto/manual/ignore）。

        Returns:
            是否处理成功。
        """
        with self._lock:
            timeline = self._timelines.get(timeline_id)
            if not timeline:
                return False
            for c in timeline.conflicts:
                if c.id == conflict_id:
                    c.metadata = c.metadata or {}
                    c.metadata["resolution"] = resolution
                    c.metadata["resolved_at"] = datetime.now().isoformat()
                    return True
            return False

    # ===== 甘特图数据生成 =====

    def generate_gantt_data(
        self,
        timeline_id: str,
        granularity: str = "day",
    ) -> dict[str, Any]:
        """生成甘特图数据。

        Args:
            timeline_id: 时间线 ID。
            granularity: 粒度（day/week/month/quarter）。

        Returns:
            甘特图数据字典（可直接用于前端渲染）。
        """
        with self._lock:
            timeline = self._timelines.get(timeline_id)
            if not timeline:
                return {}
            tasks_data = []
            for t in timeline.tasks:
                tasks_data.append({
                    "id": t.id,
                    "name": t.name,
                    "start": t.start_date,
                    "end": t.end_date,
                    "duration": t.duration_days,
                    "progress": t.progress,
                    "status": t.status,
                    "status_name": TASK_STATUS.get(t.status, t.status),
                    "priority": t.priority,
                    "priority_name": TASK_PRIORITY.get(t.priority, t.priority),
                    "color": t.color or GANTT_COLORS.get(t.priority, "#0d6efd"),
                    "assignee": t.assignee,
                    "dependencies": t.dependencies,
                    "resources": t.resources,
                    "is_milestone": False,
                    "on_critical_path": bool(
                        timeline.critical_path and t.id in timeline.critical_path.task_ids
                    ),
                })
            # 里程碑
            milestones_data = []
            for m in timeline.milestones:
                milestones_data.append({
                    "id": m.id,
                    "name": m.name,
                    "date": m.start_date,
                    "type": m.milestone_type,
                    "symbol": MILESTONE_SYMBOLS.get(m.milestone_type, "●"),
                    "status": m.status,
                    "progress": m.progress,
                })
            # 时间轴刻度
            time_axis = self._generate_time_axis(
                timeline.start_date, timeline.end_date, granularity
            )
            return {
                "timeline_id": timeline_id,
                "name": timeline.name,
                "start_date": timeline.start_date,
                "end_date": timeline.end_date,
                "granularity": granularity,
                "tasks": tasks_data,
                "milestones": milestones_data,
                "time_axis": time_axis,
                "critical_path": timeline.critical_path.to_dict() if timeline.critical_path else None,
                "conflicts": [c.to_dict() for c in timeline.conflicts],
                "total_duration": self._compute_total_duration(timeline),
            }

    def _generate_time_axis(
        self, start_date: str, end_date: str, granularity: str
    ) -> list[dict[str, str]]:
        """生成时间轴刻度。

        Args:
            start_date: 开始日期。
            end_date: 结束日期。
            granularity: 粒度。

        Returns:
            刻度列表。
        """
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            return []
        axis: list[dict[str, str]] = []
        current = start
        if granularity == "day":
            while current <= end:
                axis.append({
                    "date": current.strftime("%Y-%m-%d"),
                    "label": current.strftime("%m-%d"),
                    "is_weekend": current.weekday() >= 5,
                    "is_holiday": current.strftime("%Y-%m-%d") in self._holidays,
                })
                current += timedelta(days=1)
        elif granularity == "week":
            while current <= end:
                week_start = current - timedelta(days=current.weekday())
                axis.append({
                    "date": week_start.strftime("%Y-%m-%d"),
                    "label": f"{week_start.strftime('%m-%d')}周",
                })
                current += timedelta(days=7)
        elif granularity == "month":
            while current <= end:
                axis.append({
                    "date": current.strftime("%Y-%m-01"),
                    "label": current.strftime("%Y-%m"),
                })
                # 跳到下个月
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1, day=1)
                else:
                    current = current.replace(month=current.month + 1, day=1)
        elif granularity == "quarter":
            while current <= end:
                q = (current.month - 1) // 3 + 1
                axis.append({
                    "date": current.strftime("%Y-%m-01"),
                    "label": f"{current.year}Q{q}",
                })
                # 跳到下个季度
                next_month = q * 3 + 1
                if next_month > 12:
                    current = current.replace(year=current.year + 1, month=1, day=1)
                else:
                    current = current.replace(month=next_month, day=1)
        return axis

    # ===== 资源平衡 =====

    def balance_resources(self, timeline_id: str) -> dict[str, Any]:
        """资源平衡分析。

        Args:
            timeline_id: 时间线 ID。

        Returns:
            资源平衡分析结果。
        """
        with self._lock:
            timeline = self._timelines.get(timeline_id)
            if not timeline:
                return {}
            tasks = timeline.tasks + timeline.milestones
            # 按资源统计负载
            resource_load: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for t in tasks:
                for r in t.resources:
                    resource_load[r].append({
                        "task_id": t.id,
                        "task_name": t.name,
                        "start_date": t.start_date,
                        "end_date": t.end_date,
                        "duration_days": t.duration_days,
                    })
            # 检测过载
            overload: list[dict[str, Any]] = []
            for resource, loads in resource_load.items():
                # 检测时间重叠
                for i in range(len(loads)):
                    for j in range(i + 1, len(loads)):
                        li = loads[i]
                        lj = loads[j]
                        if li["start_date"] and li["end_date"] and lj["start_date"] and lj["end_date"]:
                            if not (li["end_date"] < lj["start_date"] or lj["end_date"] < li["start_date"]):
                                overload.append({
                                    "resource": resource,
                                    "task1": li["task_name"],
                                    "task2": lj["task_name"],
                                    "suggestion": "错开任务时间或增加资源",
                                })
            # 负载统计
            load_summary = []
            for resource, loads in resource_load.items():
                total_days = sum(l["duration_days"] for l in loads)
                load_summary.append({
                    "resource": resource,
                    "task_count": len(loads),
                    "total_days": total_days,
                    "tasks": loads,
                })
            return {
                "timeline_id": timeline_id,
                "resource_count": len(resource_load),
                "load_summary": load_summary,
                "overload_count": len(overload),
                "overload_details": overload,
                "is_balanced": len(overload) == 0,
            }

    # ===== 优化建议 =====

    def generate_optimization_suggestions(
        self, timeline_id: str
    ) -> list[OptimizationSuggestion]:
        """生成优化建议。

        Args:
            timeline_id: 时间线 ID。

        Returns:
            优化建议列表。
        """
        with self._lock:
            timeline = self._timelines.get(timeline_id)
            if not timeline:
                return []
            suggestions: list[OptimizationSuggestion] = []
            tasks = timeline.tasks

            # 1. 可并行化建议（无依赖关系的串行任务）
            for i in range(len(tasks)):
                for j in range(i + 1, len(tasks)):
                    ti = tasks[i]
                    tj = tasks[j]
                    # 无依赖且时间不重叠但可重叠
                    if (tj.id not in ti.dependencies and ti.id not in tj.dependencies
                            and ti.assignee != tj.assignee
                            and ti.start_date and tj.start_date):
                        # 如果 tj 在 ti 之后开始且无依赖，可提前
                        if tj.start_date > ti.end_date:
                            suggestions.append(OptimizationSuggestion(
                                id=f"opt_{uuid.uuid4().hex[:8]}",
                                suggestion_type="parallelize",
                                description=f"任务「{tj.name}」与「{ti.name}」无依赖，可并行执行以缩短总工期",
                                task_ids=[ti.id, tj.id],
                                expected_benefit=f"可缩短约 {min(ti.duration_days, tj.duration_days)} 天",
                                difficulty="easy",
                            ))

            # 2. 大任务拆分建议
            avg_duration = sum(t.duration_days for t in tasks) / max(len(tasks), 1)
            for t in tasks:
                if t.duration_days > avg_duration * 2 and t.duration_days > 14:
                    suggestions.append(OptimizationSuggestion(
                        id=f"opt_{uuid.uuid4().hex[:8]}",
                        suggestion_type="split",
                        description=f"任务「{t.name}」工期较长（{t.duration_days}天），建议拆分为多个子任务",
                        task_ids=[t.id],
                        expected_benefit="便于进度控制与风险管理",
                        difficulty="medium",
                    ))

            # 3. 关键路径缓冲建议
            if timeline.critical_path and timeline.critical_path.buffer < 7:
                suggestions.append(OptimizationSuggestion(
                    id=f"opt_{uuid.uuid4().hex[:8]}",
                    suggestion_type="buffer",
                    description=f"关键路径缓冲仅 {timeline.critical_path.buffer} 天，建议增加缓冲以应对风险",
                    task_ids=timeline.critical_path.task_ids,
                    expected_benefit="提高按期完成概率",
                    difficulty="hard",
                ))

            # 4. 资源平衡建议
            balance = self.balance_resources(timeline_id)
            if not balance.get("is_balanced", True):
                suggestions.append(OptimizationSuggestion(
                    id=f"opt_{uuid.uuid4().hex[:8]}",
                    suggestion_type="resource_balance",
                    description=f"检测到 {balance.get('overload_count', 0)} 处资源过载，建议错开任务时间",
                    task_ids=[],
                    expected_benefit="避免资源争用，提高执行效率",
                    difficulty="medium",
                ))

            # 5. 小任务合并建议
            small_tasks = [t for t in tasks if t.duration_days <= 2]
            if len(small_tasks) >= 3:
                suggestions.append(OptimizationSuggestion(
                    id=f"opt_{uuid.uuid4().hex[:8]}",
                    suggestion_type="merge",
                    description=f"检测到 {len(small_tasks)} 个小任务（≤2天），建议合并以减少管理开销",
                    task_ids=[t.id for t in small_tasks],
                    expected_benefit="减少任务切换开销",
                    difficulty="easy",
                ))

            return suggestions

    # ===== 多时间线对比 =====

    def compare_timelines(
        self, timeline_ids: list[str]
    ) -> dict[str, Any]:
        """对比多个时间线。

        Args:
            timeline_ids: 时间线 ID 列表。

        Returns:
            对比结果字典。
        """
        with self._lock:
            timelines = [self._timelines.get(tid) for tid in timeline_ids]
            if not all(timelines):
                return {}
            comparison: list[dict[str, Any]] = []
            for tl in timelines:
                comparison.append({
                    "timeline_id": tl.id,
                    "name": tl.name,
                    "task_count": len(tl.tasks),
                    "milestone_count": len(tl.milestones),
                    "total_duration": self._compute_total_duration(tl),
                    "critical_path_duration": tl.critical_path.total_duration if tl.critical_path else 0,
                    "buffer": tl.critical_path.buffer if tl.critical_path else 0,
                    "conflict_count": len(tl.conflicts),
                    "start_date": tl.start_date,
                    "end_date": tl.end_date,
                })
            # 找出最优时间线（综合评分）
            scored = []
            for c in comparison:
                # 评分：工期越短越好，冲突越少越好，缓冲适中越好
                duration_score = max(0, 100 - c["total_duration"] / 7)  # 每周扣1分
                conflict_score = max(0, 100 - c["conflict_count"] * 20)
                buffer_score = 100 if 7 <= c["buffer"] <= 30 else 50
                total_score = duration_score * 0.4 + conflict_score * 0.4 + buffer_score * 0.2
                scored.append((total_score, c["timeline_id"]))
            scored.sort(reverse=True)
            return {
                "comparison": comparison,
                "best_timeline_id": scored[0][1] if scored else None,
                "best_score": round(scored[0][0], 2) if scored else 0,
                "ranking": [s[1] for s in scored],
            }

    # ===== 历史分析 =====

    def save_to_history(self, timeline_id: str, note: str = "") -> bool:
        """将时间线快照存入历史。"""
        with self._lock:
            timeline = self._timelines.get(timeline_id)
            if not timeline:
                return False
            self._history.append({
                "timeline_id": timeline_id,
                "name": timeline.name,
                "task_count": len(timeline.tasks),
                "milestone_count": len(timeline.milestones),
                "duration_days": self._compute_total_duration(timeline),
                "conflict_count": len(timeline.conflicts),
                "note": note,
                "saved_at": datetime.now().isoformat(),
            })
            return True

    def analyze_history(self) -> dict[str, Any]:
        """分析历史时间线。"""
        with self._lock:
            if not self._history:
                return {}
            durations = [h["duration_days"] for h in self._history if h.get("duration_days")]
            task_counts = [h["task_count"] for h in self._history]
            conflict_counts = [h["conflict_count"] for h in self._history]
            return {
                "history_count": len(self._history),
                "avg_duration": round(sum(durations) / len(durations), 1) if durations else 0,
                "avg_task_count": round(sum(task_counts) / len(task_counts), 1) if task_counts else 0,
                "avg_conflict_count": round(sum(conflict_counts) / len(conflict_counts), 1) if conflict_counts else 0,
                "history": self._history,
            }

    def benchmark_against_history(self, timeline_id: str) -> dict[str, Any]:
        """与历史基准对比。"""
        with self._lock:
            timeline = self._timelines.get(timeline_id)
            if not timeline or not self._history:
                return {}
            current_duration = self._compute_total_duration(timeline)
            current_tasks = len(timeline.tasks)
            current_conflicts = len(timeline.conflicts)
            durations = [h["duration_days"] for h in self._history if h.get("duration_days")]
            task_counts = [h["task_count"] for h in self._history]
            if not durations:
                return {}
            avg_dur = sum(durations) / len(durations)
            avg_tasks = sum(task_counts) / len(task_counts) if task_counts else 0
            return {
                "current_duration": current_duration,
                "history_avg_duration": round(avg_dur, 1),
                "duration_vs_avg": round(current_duration - avg_dur, 1),
                "current_task_count": current_tasks,
                "history_avg_task_count": round(avg_tasks, 1),
                "current_conflict_count": current_conflicts,
                "duration_percentile": round(
                    sum(1 for d in durations if d < current_duration) / len(durations) * 100, 2
                ),
            }

    # ===== 导出 =====

    def export_json(self, timeline_id: str) -> str:
        """导出为 JSON 字符串。"""
        with self._lock:
            timeline = self._timelines.get(timeline_id)
            if not timeline:
                return "{}"
            return json.dumps(timeline.to_dict(), ensure_ascii=False, indent=2)

    def export_csv(self, timeline_id: str) -> str:
        """导出为 CSV 字符串。"""
        with self._lock:
            timeline = self._timelines.get(timeline_id)
            if not timeline:
                return ""
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                "任务ID", "任务名称", "开始日期", "结束日期", "持续天数",
                "进度", "状态", "优先级", "负责人", "是否里程碑", "在关键路径",
            ])
            cp_ids = timeline.critical_path.task_ids if timeline.critical_path else []
            for t in timeline.tasks + timeline.milestones:
                writer.writerow([
                    t.id, t.name, t.start_date, t.end_date, t.duration_days,
                    f"{t.progress}%", TASK_STATUS.get(t.status, t.status),
                    TASK_PRIORITY.get(t.priority, t.priority), t.assignee,
                    "是" if t.is_milestone else "否",
                    "是" if t.id in cp_ids else "否",
                ])
            return output.getvalue()

    def export_markdown(self, timeline_id: str) -> str:
        """导出为 Markdown 表格。"""
        with self._lock:
            timeline = self._timelines.get(timeline_id)
            if not timeline:
                return ""
            lines: list[str] = []
            lines.append(f"# 时间线：{timeline.name}")
            lines.append("")
            lines.append(f"- **时间范围**：{timeline.start_date} ~ {timeline.end_date}")
            lines.append(f"- **任务数**：{len(timeline.tasks)}")
            lines.append(f"- **里程碑数**：{len(timeline.milestones)}")
            if timeline.critical_path:
                lines.append(f"- **关键路径工期**：{timeline.critical_path.total_duration} 天")
                lines.append(f"- **缓冲**：{timeline.critical_path.buffer} 天")
            lines.append(f"- **冲突数**：{len(timeline.conflicts)}")
            lines.append("")
            lines.append("## 任务列表")
            lines.append("")
            lines.append("| 任务 | 开始 | 结束 | 工期 | 进度 | 状态 | 优先级 | 负责人 |")
            lines.append("|------|------|------|------|------|------|--------|--------|")
            cp_ids = timeline.critical_path.task_ids if timeline.critical_path else []
            for t in timeline.tasks:
                cp_mark = " ⚡" if t.id in cp_ids else ""
                lines.append(
                    f"| {t.name}{cp_mark} | {t.start_date} | {t.end_date} | "
                    f"{t.duration_days}天 | {t.progress:.0f}% | "
                    f"{TASK_STATUS.get(t.status, t.status)} | "
                    f"{TASK_PRIORITY.get(t.priority, t.priority)} | {t.assignee} |"
                )
            lines.append("")
            if timeline.milestones:
                lines.append("## 里程碑")
                lines.append("")
                lines.append("| 里程碑 | 日期 | 类型 | 状态 |")
                lines.append("|--------|------|------|------|")
                for m in timeline.milestones:
                    lines.append(
                        f"| {MILESTONE_SYMBOLS.get(m.milestone_type, '●')} {m.name} | "
                        f"{m.start_date} | {m.milestone_type} | "
                        f"{TASK_STATUS.get(m.status, m.status)} |"
                    )
                lines.append("")
            if timeline.conflicts:
                lines.append("## 冲突列表")
                lines.append("")
                lines.append("| 冲突 | 类型 | 严重程度 | 建议 |")
                lines.append("|------|------|----------|------|")
                for c in timeline.conflicts:
                    lines.append(
                        f"| {c.description} | {CONFLICT_TYPES.get(c.conflict_type, c.conflict_type)} | "
                        f"{TASK_PRIORITY.get(c.severity, c.severity)} | {c.suggestion} |"
                    )
                lines.append("")
            return "\n".join(lines)

    def export_html(self, timeline_id: str) -> str:
        """导出为 HTML 页面（含简易甘特图）。"""
        with self._lock:
            timeline = self._timelines.get(timeline_id)
            if not timeline:
                return ""
            gantt = self.generate_gantt_data(timeline_id, "day")
            html_parts: list[str] = []
            html_parts.append("<!DOCTYPE html>")
            html_parts.append('<html lang="zh-CN"><head><meta charset="UTF-8">')
            html_parts.append(f"<title>时间线：{timeline.name}</title>")
            html_parts.append("<style>")
            html_parts.append("body{font-family:sans-serif;margin:20px;}")
            html_parts.append(".gantt{border:1px solid #ddd;border-collapse:collapse;}")
            html_parts.append(".gantt th,.gantt td{border:1px solid #ddd;padding:6px 10px;}")
            html_parts.append(".gantt th{background:#f5f5f5;}")
            html_parts.append(".bar{height:20px;border-radius:3px;color:#fff;padding:2px 6px;}")
            html_parts.append(".milestone{color:#dc3545;font-weight:bold;}")
            html_parts.append(".conflict{color:#fd7e14;}")
            html_parts.append("</style></head><body>")
            html_parts.append(f"<h1>时间线：{timeline.name}</h1>")
            html_parts.append(f"<p>时间范围：{timeline.start_date} ~ {timeline.end_date}</p>")
            html_parts.append('<table class="gantt">')
            html_parts.append("<tr><th>任务</th><th>开始</th><th>结束</th><th>工期</th>"
                              "<th>进度</th><th>状态</th><th>优先级</th><th>负责人</th></tr>")
            cp_ids = timeline.critical_path.task_ids if timeline.critical_path else []
            for t in gantt["tasks"]:
                cp_mark = " ⚡" if t["id"] in cp_ids else ""
                color = t.get("color", "#0d6efd")
                html_parts.append(
                    f'<tr><td>{t["name"]}{cp_mark}</td>'
                    f'<td>{t["start"]}</td><td>{t["end"]}</td>'
                    f'<td>{t["duration"]}天</td>'
                    f'<td><div class="bar" style="background:{color};width:{t["progress"]}%">'
                    f'{t["progress"]}%</div></td>'
                    f'<td>{t["status_name"]}</td>'
                    f'<td>{t["priority_name"]}</td>'
                    f'<td>{t["assignee"]}</td></tr>'
                )
            html_parts.append("</table>")
            if gantt["milestones"]:
                html_parts.append("<h2>里程碑</h2><ul>")
                for m in gantt["milestones"]:
                    html_parts.append(
                        f'<li class="milestone">{m["symbol"]} {m["name"]} ({m["date"]})</li>'
                    )
                html_parts.append("</ul>")
            if gantt["conflicts"]:
                html_parts.append("<h2>冲突</h2><ul>")
                for c in gantt["conflicts"]:
                    html_parts.append(
                        f'<li class="conflict">{c["description"]} — {c["suggestion"]}</li>'
                    )
                html_parts.append("</ul>")
            html_parts.append("</body></html>")
            return "\n".join(html_parts)

    # ===== 工具方法 =====

    def set_workdays(self, workdays: set[int]) -> None:
        """设置工作日。"""
        with self._lock:
            self._workdays = workdays

    def set_holidays(self, holidays: set[str]) -> None:
        """设置节假日。"""
        with self._lock:
            self._holidays = holidays

    def add_holiday(self, date: str, name: str = "") -> None:
        """添加节假日。"""
        with self._lock:
            self._holidays.add(date)

    def compute_workdays_between(self, start_date: str, end_date: str) -> int:
        """计算两个日期之间的工作日天数。"""
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            return 0
        count = 0
        current = start
        while current <= end:
            iso = current.strftime("%Y-%m-%d")
            if current.weekday() in self._workdays and iso not in self._holidays:
                count += 1
            current += timedelta(days=1)
        return count

    def add_business_days(self, start_date: str, days: int) -> str:
        """从起始日期增加 N 个工作日。"""
        try:
            current = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            return start_date
        added = 0
        while added < days:
            current += timedelta(days=1)
            iso = current.strftime("%Y-%m-%d")
            if current.weekday() in self._workdays and iso not in self._holidays:
                added += 1
        return current.strftime("%Y-%m-%d")

    def summary(self) -> dict[str, Any]:
        """返回生成器汇总信息。"""
        with self._lock:
            return {
                "timeline_count": len(self._timelines),
                "history_count": len(self._history),
                "workdays": sorted(self._workdays),
                "holiday_count": len(self._holidays),
            }

    def get_timeline_statistics(self, timeline_id: str) -> dict[str, Any]:
        """计算时间线统计指标。"""
        with self._lock:
            timeline = self._timelines.get(timeline_id)
            if not timeline:
                return {}
            tasks = timeline.tasks + timeline.milestones
            total_workdays = sum(
                t.workdays(self._holidays, self._workdays) for t in tasks
            )
            completed = sum(1 for t in tasks if t.status == "completed")
            in_progress = sum(1 for t in tasks if t.status == "in_progress")
            blocked = sum(1 for t in tasks if t.status == "blocked")
            return {
                "timeline_id": timeline_id,
                "total_tasks": len(tasks),
                "completed_tasks": completed,
                "in_progress_tasks": in_progress,
                "blocked_tasks": blocked,
                "pending_tasks": len(tasks) - completed - in_progress - blocked,
                "milestone_count": len(timeline.milestones),
                "total_duration_days": self._compute_total_duration(timeline),
                "total_workdays": total_workdays,
                "critical_path_duration": timeline.critical_path.total_duration if timeline.critical_path else 0,
                "buffer_days": timeline.critical_path.buffer if timeline.critical_path else 0,
                "conflict_count": len(timeline.conflicts),
                "critical_conflict_count": sum(
                    1 for c in timeline.conflicts if c.severity == "critical"
                ),
                "avg_task_duration": round(
                    sum(t.duration_days for t in tasks) / max(len(tasks), 1), 1
                ),
                "completion_rate": round(completed / max(len(tasks), 1) * 100, 2),
            }
