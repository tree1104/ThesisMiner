"""模型路由模块

提供智能模型路由的核心能力。

子模块：
    - model_router: 模型路由器（基于任务类型/复杂度/成本/延迟的路由决策）

公共导出：
    - ModelRouter: 模型路由器主类
    - ModelInfo: 模型信息数据结构
    - RoutingRule: 路由规则数据结构
    - RoutingDecision: 路由决策数据结构
    - RoutingLog: 路由日志数据结构
"""
from backend.routing.model_router import (
    ModelRouter,
    ModelInfo,
    RoutingRule,
    RoutingDecision,
    RoutingLog,
    TaskType,
    ComplexityLevel,
    RoutingStrategy,
)

__all__ = [
    "ModelRouter",
    "ModelInfo",
    "RoutingRule",
    "RoutingDecision",
    "RoutingLog",
    "TaskType",
    "ComplexityLevel",
    "RoutingStrategy",
]

__version__ = "8.0.0"
