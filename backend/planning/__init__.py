"""研究规划模块

提供完整的研究规划能力，包括：
    - 研究计划生成、阶段划分、时间线、里程碑
    - 资源分配、风险评估、应急预案
    - 研究方法选择、数据收集与分析计划
    - 进度跟踪、计划调整、完成度评估
    - 多学科研究规划、跨领域协作规划
    - 甘特图数据生成、关键路径分析
    - 里程碑追踪、依赖关系、延迟预警

子模块：
    - research_planner: 研究规划器主类
    - timeline_generator: 时间线生成器
    - milestone_tracker: 里程碑追踪器

公共导出：
    - ResearchPlanner: 研究规划器主类
    - TimelineGenerator: 时间线生成器主类
    - MilestoneTracker: 里程碑追踪器主类
    - ResearchPlan: 研究计划数据结构
    - Timeline: 时间线数据结构
    - Milestone: 里程碑数据结构
"""
from backend.planning.research_planner import (
    ResearchPlanner,
    ResearchPlan,
    ResearchPhase,
    RiskAssessment,
)
from backend.planning.timeline_generator import (
    TimelineGenerator,
    Timeline,
    TimelineTask,
    CriticalPath,
)
from backend.planning.milestone_tracker import (
    MilestoneTracker,
    Milestone,
    MilestoneStatus,
    MilestoneReview,
)

__all__ = [
    "ResearchPlanner",
    "ResearchPlan",
    "ResearchPhase",
    "RiskAssessment",
    "TimelineGenerator",
    "Timeline",
    "TimelineTask",
    "CriticalPath",
    "MilestoneTracker",
    "Milestone",
    "MilestoneStatus",
    "MilestoneReview",
]

__version__ = "8.0.0"
