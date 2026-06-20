"""模型路由器模块

提供完整的智能模型路由实现，包括：
    - 基于任务类型/复杂度/成本/延迟的路由决策
    - 模型负载均衡、故障转移、降级策略
    - 路由规则配置、动态调整、A/B 测试
    - 路由日志、性能统计、成本分析
    - 完整的路由策略、决策树算法

设计原则：
    1. 零外部依赖：仅使用 Python 标准库
    2. 线程安全：所有公共方法通过 RLock 保护
    3. 可配置：路由规则、策略、权重均可动态调整
    4. 可观测：完整的路由日志与统计
"""
from __future__ import annotations

import math
import random
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Any, Callable, Optional


# ===== 枚举与常量 =====


class TaskType:
    """任务类型常量。"""

    GENERATION = "generation"        # 文本生成
    ANALYSIS = "analysis"            # 分析
    SUMMARIZATION = "summarization"  # 摘要
    TRANSLATION = "translation"      # 翻译
    CODING = "coding"                # 代码生成
    REASONING = "reasoning"          # 推理
    SEARCH = "search"                # 搜索
    EMBEDDING = "embedding"          # 向量嵌入
    CLASSIFICATION = "classification"  # 分类
    EXTRACTION = "extraction"        # 信息抽取


# 任务类型中文名
TASK_TYPE_NAMES = {
    TaskType.GENERATION: "文本生成",
    TaskType.ANALYSIS: "分析",
    TaskType.SUMMARIZATION: "摘要",
    TaskType.TRANSLATION: "翻译",
    TaskType.CODING: "代码生成",
    TaskType.REASONING: "推理",
    TaskType.SEARCH: "搜索",
    TaskType.EMBEDDING: "向量嵌入",
    TaskType.CLASSIFICATION: "分类",
    TaskType.EXTRACTION: "信息抽取",
}


class ComplexityLevel:
    """任务复杂度级别。"""

    SIMPLE = "simple"      # 简单
    MEDIUM = "medium"      # 中等
    COMPLEX = "complex"    # 复杂
    EXPERT = "expert"      # 专家级


# 复杂度中文名
COMPLEXITY_NAMES = {
    ComplexityLevel.SIMPLE: "简单",
    ComplexityLevel.MEDIUM: "中等",
    ComplexityLevel.COMPLEX: "复杂",
    ComplexityLevel.EXPERT: "专家级",
}

# 复杂度数值映射（用于评分）
COMPLEXITY_SCORES = {
    ComplexityLevel.SIMPLE: 1,
    ComplexityLevel.MEDIUM: 2,
    ComplexityLevel.COMPLEX: 3,
    ComplexityLevel.EXPERT: 4,
}


class RoutingStrategy:
    """路由策略常量。"""

    COST_OPTIMIZED = "cost_optimized"        # 成本优先
    QUALITY_OPTIMIZED = "quality_optimized"  # 质量优先
    LATENCY_OPTIMIZED = "latency_optimized"  # 延迟优先
    BALANCED = "balanced"                    # 平衡
    LOAD_BALANCED = "load_balanced"          # 负载均衡


# 策略中文名
STRATEGY_NAMES = {
    RoutingStrategy.COST_OPTIMIZED: "成本优先",
    RoutingStrategy.QUALITY_OPTIMIZED: "质量优先",
    RoutingStrategy.LATENCY_OPTIMIZED: "延迟优先",
    RoutingStrategy.BALANCED: "平衡",
    RoutingStrategy.LOAD_BALANCED: "负载均衡",
}

# 策略权重配置
STRATEGY_WEIGHTS = {
    RoutingStrategy.COST_OPTIMIZED: {
        "cost": 0.6, "quality": 0.2, "latency": 0.2,
    },
    RoutingStrategy.QUALITY_OPTIMIZED: {
        "cost": 0.15, "quality": 0.7, "latency": 0.15,
    },
    RoutingStrategy.LATENCY_OPTIMIZED: {
        "cost": 0.2, "quality": 0.2, "latency": 0.6,
    },
    RoutingStrategy.BALANCED: {
        "cost": 0.33, "quality": 0.34, "latency": 0.33,
    },
    RoutingStrategy.LOAD_BALANCED: {
        "cost": 0.25, "quality": 0.25, "latency": 0.25, "load": 0.25,
    },
}

# 模型状态
MODEL_STATES = {
    "active": "活跃",
    "degraded": "降级",
    "overloaded": "过载",
    "failed": "故障",
    "maintenance": "维护中",
}

# 默认故障转移重试次数
DEFAULT_FAILOVER_RETRIES = 3

# 默认请求超时（秒）
DEFAULT_TIMEOUT = 30

# 负载统计窗口（秒）
LOAD_WINDOW_SECONDS = 60

# A/B 测试默认流量分配
DEFAULT_AB_TRAFFIC_SPLIT = 0.5


# ===== 数据结构 =====


@dataclass
class ModelInfo:
    """模型信息。

    Attributes:
        id: 模型 ID。
        name: 模型名称。
        provider: 提供商。
        base_url: API 地址。
        pricing: 定价（input_cny_per_million, output_cny_per_million）。
        max_context: 最大上下文长度。
        max_output: 最大输出长度。
        capabilities: 支持的能力列表。
        quality_score: 质量评分（0-100）。
        avg_latency_ms: 平均延迟（毫秒）。
        throughput_qps: 吞吐量（QPS）。
        state: 当前状态。
        weight: 路由权重。
        release_year: 发布年份。
        metadata: 扩展元数据。
    """

    id: str = ""
    name: str = ""
    provider: str = ""
    base_url: str = ""
    pricing: dict[str, float] = field(default_factory=dict)
    max_context: int = 4096
    max_output: int = 2048
    capabilities: list[str] = field(default_factory=list)
    quality_score: float = 70.0
    avg_latency_ms: float = 1000.0
    throughput_qps: float = 10.0
    state: str = "active"
    weight: float = 1.0
    release_year: int = 2024
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelInfo":
        defaults = cls().__dict__
        merged = {**defaults, **{k: v for k, v in data.items() if k in defaults}}
        return cls(**merged)

    def supports(self, capability: str) -> bool:
        """检查是否支持指定能力。"""
        return capability in self.capabilities

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """估算请求成本（元）。

        Args:
            input_tokens: 输入 token 数。
            output_tokens: 输出 token 数。

        Returns:
            预估成本（元）。
        """
        input_price = self.pricing.get("input_cny_per_million", 0.0)
        output_price = self.pricing.get("output_cny_per_million", 0.0)
        return (input_tokens * input_price + output_tokens * output_price) / 1_000_000

    def is_available(self) -> bool:
        """是否可用。"""
        return self.state in ("active", "degraded")


@dataclass
class RoutingRule:
    """路由规则。

    Attributes:
        id: 规则 ID。
        name: 规则名称。
        priority: 优先级（数值越小越优先）。
        task_type: 任务类型（None 表示任意）。
        complexity: 复杂度（None 表示任意）。
        preferred_models: 偏好模型 ID 列表。
        excluded_models: 排除模型 ID 列表。
        strategy: 路由策略。
        condition: 自定义条件函数。
        enabled: 是否启用。
        description: 规则描述。
    """

    id: str = ""
    name: str = ""
    priority: int = 100
    task_type: Optional[str] = None
    complexity: Optional[str] = None
    preferred_models: list[str] = field(default_factory=list)
    excluded_models: list[str] = field(default_factory=list)
    strategy: str = RoutingStrategy.BALANCED
    condition: Optional[Callable[[dict[str, Any]], bool]] = None
    enabled: bool = True
    description: str = ""

    def matches(self, context: dict[str, Any]) -> bool:
        """检查规则是否匹配上下文。"""
        if not self.enabled:
            return False
        if self.task_type and context.get("task_type") != self.task_type:
            return False
        if self.complexity and context.get("complexity") != self.complexity:
            return False
        if self.condition is not None:
            try:
                if not self.condition(context):
                    return False
            except Exception:
                return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "priority": self.priority,
            "task_type": self.task_type,
            "complexity": self.complexity,
            "preferred_models": self.preferred_models,
            "excluded_models": self.excluded_models,
            "strategy": self.strategy,
            "enabled": self.enabled,
            "description": self.description,
        }


@dataclass
class RoutingDecision:
    """路由决策。

    Attributes:
        id: 决策 ID。
        timestamp: 决策时间。
        task_type: 任务类型。
        complexity: 复杂度。
        strategy: 路由策略。
        selected_model_id: 选中的模型 ID。
        candidate_models: 候选模型列表。
        scores: 各模型评分。
        reason: 决策原因。
        estimated_cost: 预估成本。
        estimated_latency: 预估延迟。
        rule_id: 匹配的规则 ID。
        metadata: 元数据。
    """

    id: str = ""
    timestamp: str = ""
    task_type: str = ""
    complexity: str = ""
    strategy: str = ""
    selected_model_id: str = ""
    candidate_models: list[str] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)
    reason: str = ""
    estimated_cost: float = 0.0
    estimated_latency: float = 0.0
    rule_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "task_type": self.task_type,
            "complexity": self.complexity,
            "strategy": self.strategy,
            "selected_model_id": self.selected_model_id,
            "candidate_models": self.candidate_models,
            "scores": {k: round(v, 4) for k, v in self.scores.items()},
            "reason": self.reason,
            "estimated_cost": round(self.estimated_cost, 6),
            "estimated_latency": round(self.estimated_latency, 2),
            "rule_id": self.rule_id,
            "metadata": self.metadata,
        }


@dataclass
class RoutingLog:
    """路由日志。

    Attributes:
        id: 日志 ID。
        decision_id: 关联的决策 ID。
        timestamp: 时间戳。
        model_id: 模型 ID。
        task_type: 任务类型。
        success: 是否成功。
        latency_ms: 实际延迟（毫秒）。
        input_tokens: 输入 token 数。
        output_tokens: 输出 token 数。
        cost: 实际成本。
        error: 错误信息。
        fallback_used: 是否使用了故障转移。
        fallback_model_id: 故障转移目标模型 ID。
    """

    id: str = ""
    decision_id: str = ""
    timestamp: str = ""
    model_id: str = ""
    task_type: str = ""
    success: bool = True
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    error: str = ""
    fallback_used: bool = False
    fallback_model_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ModelLoadStats:
    """模型负载统计。

    Attributes:
        model_id: 模型 ID。
        window_start: 统计窗口起始时间。
        request_count: 请求总数。
        success_count: 成功数。
        failure_count: 失败数。
        avg_latency_ms: 平均延迟。
        total_cost: 总成本。
        total_tokens: 总 token 数。
        current_load: 当前负载（0-1）。
    """

    model_id: str = ""
    window_start: str = ""
    request_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    avg_latency_ms: float = 0.0
    total_cost: float = 0.0
    total_tokens: int = 0
    current_load: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "window_start": self.window_start,
            "request_count": self.request_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": round(self.success_count / max(self.request_count, 1), 4),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "total_cost": round(self.total_cost, 6),
            "total_tokens": self.total_tokens,
            "current_load": round(self.current_load, 4),
        }


# ===== 工具函数 =====


def _now_iso() -> str:
    """返回当前时间的 ISO 格式字符串。"""
    return datetime.now().isoformat()


def _now_timestamp() -> float:
    """返回当前时间戳。"""
    return time.time()


def _new_id(prefix: str = "route") -> str:
    """生成带前缀的唯一 ID。"""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _normalize(value: float, min_val: float, max_val: float) -> float:
    """将值归一化到 0-1 范围。"""
    if max_val == min_val:
        return 0.5
    return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))


# ===== 负载跟踪器 =====


class LoadTracker:
    """模型负载跟踪器。

    维护每个模型的滑动窗口负载统计，用于负载均衡决策。
    """

    def __init__(self, window_seconds: int = LOAD_WINDOW_SECONDS) -> None:
        """初始化负载跟踪器。

        Args:
            window_seconds: 统计窗口（秒）。
        """
        self._lock = threading.RLock()
        self._window = window_seconds
        # model_id -> deque of (timestamp, latency, success, cost, tokens)
        self._records: dict[str, deque[tuple[float, float, bool, float, int]]] = defaultdict(deque)
        # model_id -> 当前并发数
        self._concurrent: dict[str, int] = defaultdict(int)

    def record(self, model_id: str, latency_ms: float, success: bool,
               cost: float = 0.0, tokens: int = 0) -> None:
        """记录一次请求。

        Args:
            model_id: 模型 ID。
            latency_ms: 延迟（毫秒）。
            success: 是否成功。
            cost: 成本。
            tokens: token 数。
        """
        with self._lock:
            now = _now_timestamp()
            self._records[model_id].append((now, latency_ms, success, cost, tokens))
            self._cleanup(model_id, now)

    def increment_concurrent(self, model_id: str) -> int:
        """增加并发计数。"""
        with self._lock:
            self._concurrent[model_id] += 1
            return self._concurrent[model_id]

    def decrement_concurrent(self, model_id: str) -> int:
        """减少并发计数。"""
        with self._lock:
            self._concurrent[model_id] = max(0, self._concurrent[model_id] - 1)
            return self._concurrent[model_id]

    def get_stats(self, model_id: str) -> ModelLoadStats:
        """获取模型负载统计。"""
        with self._lock:
            now = _now_timestamp()
            self._cleanup(model_id, now)
            records = list(self._records.get(model_id, deque()))
            if not records:
                return ModelLoadStats(
                    model_id=model_id,
                    window_start=datetime.fromtimestamp(now - self._window).isoformat(),
                    current_load=0.0,
                )
            request_count = len(records)
            success_count = sum(1 for r in records if r[2])
            failure_count = request_count - success_count
            avg_latency = sum(r[1] for r in records) / request_count
            total_cost = sum(r[3] for r in records)
            total_tokens = sum(r[4] for r in records)
            # 当前负载 = 并发数 / 窗口内请求数 * 调整因子
            concurrent = self._concurrent.get(model_id, 0)
            load = min(1.0, concurrent / max(1, request_count / 10))
            return ModelLoadStats(
                model_id=model_id,
                window_start=datetime.fromtimestamp(now - self._window).isoformat(),
                request_count=request_count,
                success_count=success_count,
                failure_count=failure_count,
                avg_latency_ms=avg_latency,
                total_cost=total_cost,
                total_tokens=total_tokens,
                current_load=load,
            )

    def _cleanup(self, model_id: str, now: float) -> None:
        """清理过期记录。"""
        cutoff = now - self._window
        records = self._records.get(model_id, deque())
        while records and records[0][0] < cutoff:
            records.popleft()

    def get_all_stats(self) -> dict[str, ModelLoadStats]:
        """获取所有模型的负载统计。"""
        with self._lock:
            return {mid: self.get_stats(mid) for mid in list(self._records.keys())}

    def reset(self) -> None:
        """重置所有统计。"""
        with self._lock:
            self._records.clear()
            self._concurrent.clear()


# ===== 决策树路由器 =====


class DecisionTreeRouter:
    """基于决策树的路由器。

    根据任务类型、复杂度、上下文长度等特征，通过决策树选择模型。
    """

    def __init__(self) -> None:
        """初始化决策树路由器。"""
        self._lock = threading.RLock()
        # 决策树节点：feature -> {value: child_node or model_id}
        self._tree: dict[str, Any] = {}

    def build_default_tree(self, models: dict[str, ModelInfo]) -> None:
        """构建默认决策树。

        Args:
            models: 可用模型字典。
        """
        with self._lock:
            # 简化的决策树结构
            self._tree = {
                "feature": "task_type",
                "children": {
                    TaskType.EMBEDDING: {
                        "feature": "context_length",
                        "children": {
                            "short": self._find_embedding_model(models),
                            "long": self._find_embedding_model(models),
                        },
                    },
                    TaskType.REASONING: {
                        "feature": "complexity",
                        "children": {
                            ComplexityLevel.EXPERT: self._find_best_quality_model(models),
                            ComplexityLevel.COMPLEX: self._find_best_quality_model(models),
                            ComplexityLevel.MEDIUM: self._find_balanced_model(models),
                            ComplexityLevel.SIMPLE: self._find_balanced_model(models),
                        },
                    },
                    TaskType.CODING: {
                        "feature": "complexity",
                        "children": {
                            ComplexityLevel.EXPERT: self._find_best_quality_model(models),
                            ComplexityLevel.COMPLEX: self._find_best_quality_model(models),
                            ComplexityLevel.MEDIUM: self._find_balanced_model(models),
                            ComplexityLevel.SIMPLE: self._find_cheapest_model(models),
                        },
                    },
                    TaskType.GENERATION: {
                        "feature": "complexity",
                        "children": {
                            ComplexityLevel.EXPERT: self._find_best_quality_model(models),
                            ComplexityLevel.COMPLEX: self._find_balanced_model(models),
                            ComplexityLevel.MEDIUM: self._find_balanced_model(models),
                            ComplexityLevel.SIMPLE: self._find_cheapest_model(models),
                        },
                    },
                },
                "default": self._find_balanced_model(models),
            }

    def _find_best_quality_model(self, models: dict[str, ModelInfo]) -> str:
        """找质量最高的模型。"""
        if not models:
            return ""
        available = [m for m in models.values() if m.is_available()]
        if not available:
            return ""
        return max(available, key=lambda m: m.quality_score).id

    def _find_cheapest_model(self, models: dict[str, ModelInfo]) -> str:
        """找最便宜的模型。"""
        if not models:
            return ""
        available = [m for m in models.values() if m.is_available()]
        if not available:
            return ""
        return min(available, key=lambda m: m.pricing.get("input_cny_per_million", 0)).id

    def _find_balanced_model(self, models: dict[str, ModelInfo]) -> str:
        """找平衡的模型。"""
        if not models:
            return ""
        available = [m for m in models.values() if m.is_available()]
        if not available:
            return ""
        # 综合评分：质量 / (成本 * 延迟)
        def balance_score(m: ModelInfo) -> float:
            cost = m.pricing.get("input_cny_per_million", 1) + 1
            latency = m.avg_latency_ms / 1000 + 1
            return m.quality_score / (cost * latency)
        return max(available, key=balance_score).id

    def _find_embedding_model(self, models: dict[str, ModelInfo]) -> str:
        """找支持 embedding 的模型。"""
        for m in models.values():
            if m.is_available() and m.supports("embedding"):
                return m.id
        return self._find_cheapest_model(models)

    def route(self, context: dict[str, Any]) -> Optional[str]:
        """执行决策树路由。

        Args:
            context: 路由上下文。

        Returns:
            选中的模型 ID，或 None。
        """
        with self._lock:
            if not self._tree:
                return None
            return self._traverse(self._tree, context)

    def _traverse(self, node: dict[str, Any], context: dict[str, Any]) -> Optional[str]:
        """递归遍历决策树。"""
        if isinstance(node, str):
            return node
        if not isinstance(node, dict):
            return None
        feature = node.get("feature")
        if not feature:
            return node.get("default")
        # 获取特征值
        if feature == "task_type":
            value = context.get("task_type", "")
        elif feature == "complexity":
            value = context.get("complexity", "")
        elif feature == "context_length":
            context_len = context.get("context_length", 0)
            if context_len < 1000:
                value = "short"
            elif context_len < 10000:
                value = "medium"
            else:
                value = "long"
        else:
            value = context.get(feature, "")
        children = node.get("children", {})
        child = children.get(value)
        if child is not None:
            return self._traverse(child, context)
        return node.get("default")


# ===== 模型路由器主类 =====


class ModelRouter:
    """模型路由器主类。

    提供智能模型路由，包括：
        - 基于任务类型/复杂度/成本/延迟的路由决策
        - 模型负载均衡
        - 故障转移与降级
        - 路由规则配置
        - A/B 测试
        - 路由日志与性能统计
        - 成本分析

    线程安全：所有公共方法通过 RLock 保护。
    """

    def __init__(self, default_strategy: str = RoutingStrategy.BALANCED) -> None:
        """初始化模型路由器。

        Args:
            default_strategy: 默认路由策略。
        """
        self._lock = threading.RLock()
        self._default_strategy = default_strategy
        # 模型注册表：model_id -> ModelInfo
        self._models: dict[str, ModelInfo] = {}
        # 路由规则列表（按优先级排序）
        self._rules: list[RoutingRule] = []
        # 负载跟踪器
        self._load_tracker = LoadTracker()
        # 决策树路由器
        self._decision_tree = DecisionTreeRouter()
        # 路由日志
        self._logs: deque[RoutingLog] = deque(maxlen=10000)
        # 路由决策历史
        self._decisions: deque[RoutingDecision] = deque(maxlen=10000)
        # A/B 测试配置
        self._ab_tests: dict[str, dict[str, Any]] = {}
        # 故障模型记录：model_id -> 失败时间戳
        self._failed_models: dict[str, float] = {}
        # 故障恢复时间（秒）
        self._recovery_seconds = 60
        # 模型降级映射
        self._degradation_map: dict[str, list[str]] = {}

    # ===== 模型管理 =====

    def register_model(self, model: ModelInfo) -> str:
        """注册模型。

        Args:
            model: 模型信息。

        Returns:
            模型 ID。
        """
        with self._lock:
            self._models[model.id] = model
            # 重建决策树
            self._decision_tree.build_default_tree(self._models)
            return model.id

    def unregister_model(self, model_id: str) -> bool:
        """注销模型。"""
        with self._lock:
            if model_id not in self._models:
                return False
            del self._models[model_id]
            self._decision_tree.build_default_tree(self._models)
            return True

    def get_model(self, model_id: str) -> Optional[ModelInfo]:
        """获取模型信息。"""
        with self._lock:
            return self._models.get(model_id)

    def list_models(self, available_only: bool = False) -> list[ModelInfo]:
        """列出所有模型。"""
        with self._lock:
            models = list(self._models.values())
            if available_only:
                models = [m for m in models if m.is_available()]
            return models

    def update_model_state(self, model_id: str, state: str) -> bool:
        """更新模型状态。"""
        with self._lock:
            model = self._models.get(model_id)
            if model is None:
                return False
            model.state = state
            if state == "failed":
                self._failed_models[model_id] = _now_timestamp()
            elif state in ("active", "degraded"):
                self._failed_models.pop(model_id, None)
            return True

    def set_degradation_chain(self, model_id: str, fallback_ids: list[str]) -> None:
        """设置模型降级链。

        Args:
            model_id: 主模型 ID。
            fallback_ids: 降级目标模型 ID 列表（按优先级）。
        """
        with self._lock:
            self._degradation_map[model_id] = fallback_ids

    # ===== 规则管理 =====

    def add_rule(self, rule: RoutingRule) -> str:
        """添加路由规则。"""
        with self._lock:
            if not rule.id:
                rule.id = _new_id("rule")
            self._rules.append(rule)
            # 按优先级排序
            self._rules.sort(key=lambda r: r.priority)
            return rule.id

    def remove_rule(self, rule_id: str) -> bool:
        """移除路由规则。"""
        with self._lock:
            for i, rule in enumerate(self._rules):
                if rule.id == rule_id:
                    self._rules.pop(i)
                    return True
            return False

    def list_rules(self) -> list[RoutingRule]:
        """列出所有规则。"""
        with self._lock:
            return list(self._rules)

    def set_default_strategy(self, strategy: str) -> None:
        """设置默认路由策略。"""
        with self._lock:
            self._default_strategy = strategy

    # ===== 路由决策 =====

    def route(self, task_type: str, complexity: str = ComplexityLevel.MEDIUM,
              context_length: int = 0, input_tokens: int = 0,
              output_tokens: int = 0, strategy: Optional[str] = None,
              extra_context: Optional[dict[str, Any]] = None) -> RoutingDecision:
        """执行路由决策。

        Args:
            task_type: 任务类型。
            complexity: 复杂度。
            context_length: 上下文长度。
            input_tokens: 预估输入 token 数。
            output_tokens: 预估输出 token 数。
            strategy: 路由策略（None 使用默认）。
            extra_context: 额外上下文。

        Returns:
            路由决策。
        """
        with self._lock:
            context = {
                "task_type": task_type,
                "complexity": complexity,
                "context_length": context_length,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                **(extra_context or {}),
            }
            decision = RoutingDecision(
                id=_new_id("decision"),
                timestamp=_now_iso(),
                task_type=task_type,
                complexity=complexity,
                strategy=strategy or self._default_strategy,
            )
            # 1. 匹配路由规则
            matched_rule = self._match_rule(context)
            if matched_rule:
                decision.rule_id = matched_rule.id
                decision.strategy = matched_rule.strategy
                # 应用规则偏好
                preferred = matched_rule.preferred_models
                excluded = set(matched_rule.excluded_models)
            else:
                preferred = []
                excluded = set()
            # 2. 获取候选模型
            candidates = self._get_candidates(task_type, context_length, preferred, excluded)
            if not candidates:
                decision.reason = "无可用候选模型"
                return decision
            decision.candidate_models = [m.id for m in candidates]
            # 3. 评分与选择
            scores = self._score_models(candidates, decision.strategy, context)
            decision.scores = scores
            # 选择最高分模型
            selected_id = max(scores, key=scores.get) if scores else candidates[0].id
            decision.selected_model_id = selected_id
            selected_model = self._models.get(selected_id)
            if selected_model:
                decision.estimated_cost = selected_model.estimate_cost(input_tokens, output_tokens)
                decision.estimated_latency = selected_model.avg_latency_ms
            decision.reason = self._generate_decision_reason(
                selected_id, scores, decision.strategy, matched_rule
            )
            # 保存决策
            self._decisions.append(decision)
            return decision

    def _match_rule(self, context: dict[str, Any]) -> Optional[RoutingRule]:
        """匹配路由规则。"""
        for rule in self._rules:
            if rule.matches(context):
                return rule
        return None

    def _get_candidates(self, task_type: str, context_length: int,
                        preferred: list[str], excluded: set[str]) -> list[ModelInfo]:
        """获取候选模型列表。"""
        candidates: list[ModelInfo] = []
        # 优先考虑偏好模型
        for model_id in preferred:
            model = self._models.get(model_id)
            if model and model.is_available() and model_id not in excluded:
                if self._is_model_suitable(model, task_type, context_length):
                    candidates.append(model)
        # 添加其他可用模型
        for model in self._models.values():
            if model.id in excluded or model.id in [m.id for m in candidates]:
                continue
            if not model.is_available():
                continue
            if self._is_model_suitable(model, task_type, context_length):
                candidates.append(model)
        # 过滤故障模型
        candidates = [m for m in candidates if not self._is_failed(m.id)]
        return candidates

    def _is_model_suitable(self, model: ModelInfo, task_type: str,
                           context_length: int) -> bool:
        """检查模型是否适合任务。"""
        # 检查上下文长度
        if context_length > 0 and context_length > model.max_context:
            return False
        # 检查能力（embedding 任务需要 embedding 能力）
        if task_type == TaskType.EMBEDDING and not model.supports("embedding"):
            return False
        return True

    def _is_failed(self, model_id: str) -> bool:
        """检查模型是否处于故障状态。"""
        failed_time = self._failed_models.get(model_id)
        if failed_time is None:
            return False
        # 检查是否已过恢复期
        if _now_timestamp() - failed_time >= self._recovery_seconds:
            # 自动恢复
            self._failed_models.pop(model_id, None)
            model = self._models.get(model_id)
            if model and model.state == "failed":
                model.state = "active"
            return False
        return True

    def _score_models(self, candidates: list[ModelInfo], strategy: str,
                      context: dict[str, Any]) -> dict[str, float]:
        """对候选模型评分。

        Args:
            candidates: 候选模型列表。
            strategy: 路由策略。
            context: 路由上下文。

        Returns:
            model_id -> score 字典。
        """
        if not candidates:
            return {}
        weights = STRATEGY_WEIGHTS.get(strategy, STRATEGY_WEIGHTS[RoutingStrategy.BALANCED])
        # 收集各维度数据用于归一化
        costs = [m.pricing.get("input_cny_per_million", 0) + m.pricing.get("output_cny_per_million", 0) for m in candidates]
        qualities = [m.quality_score for m in candidates]
        latencies = [m.avg_latency_ms for m in candidates]
        loads = [self._load_tracker.get_stats(m.id).current_load for m in candidates]
        min_cost, max_cost = min(costs), max(costs)
        min_quality, max_quality = min(qualities), max(qualities)
        min_latency, max_latency = min(latencies), max(latencies)
        min_load, max_load = min(loads), max(loads)
        scores: dict[str, float] = {}
        for i, model in enumerate(candidates):
            # 归一化（成本和延迟越低越好，反转）
            cost_score = 1.0 - _normalize(costs[i], min_cost, max_cost) if max_cost > min_cost else 0.5
            quality_score = _normalize(qualities[i], min_quality, max_quality) if max_quality > min_quality else 0.5
            latency_score = 1.0 - _normalize(latencies[i], min_latency, max_latency) if max_latency > min_latency else 0.5
            load_score = 1.0 - _normalize(loads[i], min_load, max_load) if max_load > min_load else 0.5
            # 加权求和
            total_score = (
                cost_score * weights.get("cost", 0.33)
                + quality_score * weights.get("quality", 0.34)
                + latency_score * weights.get("latency", 0.33)
            )
            if "load" in weights:
                total_score += load_score * weights["load"]
            # 应用模型自身权重
            total_score *= model.weight
            scores[model.id] = total_score
        return scores

    def _generate_decision_reason(self, selected_id: str, scores: dict[str, float],
                                  strategy: str, rule: Optional[RoutingRule]) -> str:
        """生成决策原因。"""
        parts: list[str] = []
        parts.append(f"策略：{STRATEGY_NAMES.get(strategy, strategy)}")
        if rule:
            parts.append(f"匹配规则：{rule.name}")
        if selected_id in scores:
            parts.append(f"得分：{scores[selected_id]:.4f}")
        model = self._models.get(selected_id)
        if model:
            parts.append(f"模型：{model.name}")
        return "；".join(parts)

    # ===== 故障转移 =====

    def get_failover_model(self, failed_model_id: str,
                           context: Optional[dict[str, Any]] = None) -> Optional[str]:
        """获取故障转移模型。

        Args:
            failed_model_id: 故障模型 ID。
            context: 原始路由上下文。

        Returns:
            故障转移目标模型 ID，或 None。
        """
        with self._lock:
            # 标记模型故障
            self.update_model_state(failed_model_id, "failed")
            # 检查降级链
            fallback_ids = self._degradation_map.get(failed_model_id, [])
            for fb_id in fallback_ids:
                model = self._models.get(fb_id)
                if model and model.is_available() and not self._is_failed(fb_id):
                    return fb_id
            # 退而求其次：重新路由
            if context:
                task_type = context.get("task_type", TaskType.GENERATION)
                complexity = context.get("complexity", ComplexityLevel.MEDIUM)
                context_length = context.get("context_length", 0)
                decision = self.route(
                    task_type=task_type,
                    complexity=complexity,
                    context_length=context_length,
                    strategy=RoutingStrategy.LATENCY_OPTIMIZED,
                )
                if decision.selected_model_id and decision.selected_model_id != failed_model_id:
                    return decision.selected_model_id
            # 最后兜底：找任意可用模型
            for model in self._models.values():
                if model.id != failed_model_id and model.is_available():
                    return model.id
            return None

    def report_failure(self, model_id: str, error: str = "",
                       decision_id: str = "") -> Optional[str]:
        """报告模型故障并触发故障转移。

        Args:
            model_id: 故障模型 ID。
            error: 错误信息。
            decision_id: 关联的决策 ID。

        Returns:
            故障转移目标模型 ID，或 None。
        """
        with self._lock:
            # 记录日志
            log = RoutingLog(
                id=_new_id("log"),
                decision_id=decision_id,
                timestamp=_now_iso(),
                model_id=model_id,
                success=False,
                error=error,
                fallback_used=True,
            )
            self._logs.append(log)
            # 获取故障转移模型
            context = None
            if decision_id:
                decision = next((d for d in self._decisions if d.id == decision_id), None)
                if decision:
                    context = {
                        "task_type": decision.task_type,
                        "complexity": decision.complexity,
                        "context_length": decision.metadata.get("context_length", 0),
                    }
            fallback_id = self.get_failover_model(model_id, context)
            if fallback_id:
                log.fallback_model_id = fallback_id
            return fallback_id

    def report_success(self, model_id: str, latency_ms: float,
                       input_tokens: int = 0, output_tokens: int = 0,
                       cost: float = 0.0, decision_id: str = "") -> None:
        """报告请求成功。

        Args:
            model_id: 模型 ID。
            latency_ms: 实际延迟。
            input_tokens: 输入 token 数。
            output_tokens: 输出 token 数。
            cost: 实际成本。
            decision_id: 关联的决策 ID。
        """
        with self._lock:
            # 记录负载
            self._load_tracker.record(model_id, latency_ms, True, cost, input_tokens + output_tokens)
            # 记录日志
            log = RoutingLog(
                id=_new_id("log"),
                decision_id=decision_id,
                timestamp=_now_iso(),
                model_id=model_id,
                success=True,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
            )
            self._logs.append(log)

    # ===== A/B 测试 =====

    def setup_ab_test(self, test_id: str, model_a: str, model_b: str,
                      traffic_split: float = DEFAULT_AB_TRAFFIC_SPLIT,
                      duration_hours: int = 24) -> dict[str, Any]:
        """配置 A/B 测试。

        Args:
            test_id: 测试 ID。
            model_a: 模型 A ID。
            model_b: 模型 B ID。
            traffic_split: 流量分配（A 的比例，0-1）。
            duration_hours: 持续时间（小时）。

        Returns:
            测试配置。
        """
        with self._lock:
            config = {
                "test_id": test_id,
                "model_a": model_a,
                "model_b": model_b,
                "traffic_split": traffic_split,
                "start_time": _now_iso(),
                "end_time": (datetime.now() + timedelta(hours=duration_hours)).isoformat(),
                "duration_hours": duration_hours,
                "active": True,
                "results": {
                    "a": {"requests": 0, "successes": 0, "total_cost": 0.0, "total_latency": 0.0},
                    "b": {"requests": 0, "successes": 0, "total_cost": 0.0, "total_latency": 0.0},
                },
            }
            self._ab_tests[test_id] = config
            return config

    def get_ab_test_model(self, test_id: str) -> Optional[str]:
        """获取 A/B 测试分配的模型。

        Args:
            test_id: 测试 ID。

        Returns:
            分配的模型 ID，或 None（测试不存在或已结束）。
        """
        with self._lock:
            test = self._ab_tests.get(test_id)
            if not test or not test["active"]:
                return None
            # 检查是否过期
            end_time = datetime.fromisoformat(test["end_time"])
            if datetime.now() > end_time:
                test["active"] = False
                return None
            # 随机分配
            if random.random() < test["traffic_split"]:
                test["results"]["a"]["requests"] += 1
                return test["model_a"]
            else:
                test["results"]["b"]["requests"] += 1
                return test["model_b"]

    def record_ab_test_result(self, test_id: str, model_id: str,
                              success: bool, latency_ms: float, cost: float) -> None:
        """记录 A/B 测试结果。"""
        with self._lock:
            test = self._ab_tests.get(test_id)
            if not test:
                return
            group = "a" if model_id == test["model_a"] else "b"
            result = test["results"][group]
            if success:
                result["successes"] += 1
            result["total_cost"] += cost
            result["total_latency"] += latency_ms

    def get_ab_test_results(self, test_id: str) -> Optional[dict[str, Any]]:
        """获取 A/B 测试结果。"""
        with self._lock:
            test = self._ab_tests.get(test_id)
            if not test:
                return None
            a = test["results"]["a"]
            b = test["results"]["b"]
            return {
                "test_id": test_id,
                "active": test["active"],
                "model_a": test["model_a"],
                "model_b": test["model_b"],
                "results": {
                    "a": {
                        "requests": a["requests"],
                        "successes": a["successes"],
                        "success_rate": a["successes"] / max(a["requests"], 1),
                        "avg_cost": a["total_cost"] / max(a["requests"], 1),
                        "avg_latency": a["total_latency"] / max(a["requests"], 1),
                    },
                    "b": {
                        "requests": b["requests"],
                        "successes": b["successes"],
                        "success_rate": b["successes"] / max(b["requests"], 1),
                        "avg_cost": b["total_cost"] / max(b["requests"], 1),
                        "avg_latency": b["total_latency"] / max(b["requests"], 1),
                    },
                },
            }

    def stop_ab_test(self, test_id: str) -> bool:
        """停止 A/B 测试。"""
        with self._lock:
            test = self._ab_tests.get(test_id)
            if not test:
                return False
            test["active"] = False
            return True

    # ===== 日志与统计 =====

    def get_logs(self, model_id: Optional[str] = None,
                 limit: int = 100) -> list[RoutingLog]:
        """获取路由日志。"""
        with self._lock:
            logs = list(self._logs)
            if model_id:
                logs = [l for l in logs if l.model_id == model_id]
            return logs[-limit:]

    def get_decisions(self, limit: int = 100) -> list[RoutingDecision]:
        """获取路由决策历史。"""
        with self._lock:
            return list(self._decisions)[-limit:]

    def get_model_stats(self, model_id: str) -> Optional[ModelLoadStats]:
        """获取模型负载统计。"""
        with self._lock:
            return self._load_tracker.get_stats(model_id)

    def get_all_stats(self) -> dict[str, ModelLoadStats]:
        """获取所有模型负载统计。"""
        with self._lock:
            return self._load_tracker.get_all_stats()

    def get_cost_analysis(self, hours: int = 24) -> dict[str, Any]:
        """获取成本分析。

        Args:
            hours: 分析时间范围（小时）。

        Returns:
            成本分析结果。
        """
        with self._lock:
            cutoff = datetime.now() - timedelta(hours=hours)
            cutoff_str = cutoff.isoformat()
            # 按模型统计成本
            model_costs: dict[str, dict[str, float]] = defaultdict(
                lambda: {"cost": 0.0, "requests": 0, "tokens": 0}
            )
            total_cost = 0.0
            total_requests = 0
            for log in self._logs:
                if log.timestamp < cutoff_str:
                    continue
                model_costs[log.model_id]["cost"] += log.cost
                model_costs[log.model_id]["requests"] += 1
                model_costs[log.model_id]["tokens"] += log.input_tokens + log.output_tokens
                total_cost += log.cost
                total_requests += 1
            # 按任务类型统计
            task_costs: dict[str, float] = defaultdict(float)
            for decision in self._decisions:
                if decision.timestamp < cutoff_str:
                    continue
                task_costs[decision.task_type] += decision.estimated_cost
            return {
                "time_range_hours": hours,
                "total_cost": round(total_cost, 6),
                "total_requests": total_requests,
                "avg_cost_per_request": round(total_cost / max(total_requests, 1), 6),
                "model_breakdown": {
                    mid: {
                        "cost": round(stats["cost"], 6),
                        "requests": stats["requests"],
                        "tokens": stats["tokens"],
                        "avg_cost": round(stats["cost"] / max(stats["requests"], 1), 6),
                    }
                    for mid, stats in model_costs.items()
                },
                "task_breakdown": {
                    task: round(cost, 6) for task, cost in task_costs.items()
                },
            }

    def get_performance_report(self) -> dict[str, Any]:
        """获取性能报告。"""
        with self._lock:
            all_stats = self._load_tracker.get_all_stats()
            if not all_stats:
                return {
                    "total_models": len(self._models),
                    "active_models": sum(1 for m in self._models.values() if m.is_available()),
                    "total_requests": 0,
                }
            total_requests = sum(s.request_count for s in all_stats.values())
            total_success = sum(s.success_count for s in all_stats.values())
            total_failures = sum(s.failure_count for s in all_stats.values())
            avg_latency = (
                sum(s.avg_latency_ms * s.request_count for s in all_stats.values())
                / max(total_requests, 1)
            )
            return {
                "total_models": len(self._models),
                "active_models": sum(1 for m in self._models.values() if m.is_available()),
                "failed_models": len(self._failed_models),
                "total_requests": total_requests,
                "total_successes": total_success,
                "total_failures": total_failures,
                "overall_success_rate": round(total_success / max(total_requests, 1), 4),
                "avg_latency_ms": round(avg_latency, 2),
                "model_stats": {mid: s.to_dict() for mid, s in all_stats.items()},
                "rules_count": len(self._rules),
                "ab_tests_count": len(self._ab_tests),
                "decisions_logged": len(self._decisions),
                "logs_count": len(self._logs),
            }

    def stats(self) -> dict[str, Any]:
        """返回路由器统计信息。"""
        with self._lock:
            return {
                "total_models": len(self._models),
                "available_models": sum(1 for m in self._models.values() if m.is_available()),
                "failed_models": sum(1 for m in self._models.values() if m.state == "failed"),
                "rules_count": len(self._rules),
                "ab_tests_count": len(self._ab_tests),
                "active_ab_tests": sum(1 for t in self._ab_tests.values() if t["active"]),
                "decisions_count": len(self._decisions),
                "logs_count": len(self._logs),
                "default_strategy": self._default_strategy,
            }

    def reset_stats(self) -> None:
        """重置统计信息。"""
        with self._lock:
            self._load_tracker.reset()
            self._logs.clear()
            self._decisions.clear()
            self._failed_models.clear()


# ===== 模块级单例 =====


_global_instance: Optional[ModelRouter] = None
_global_lock = threading.Lock()


def get_model_router() -> ModelRouter:
    """获取全局模型路由器单例。"""
    global _global_instance
    if _global_instance is None:
        with _global_lock:
            if _global_instance is None:
                _global_instance = ModelRouter()
    return _global_instance


def reset_model_router() -> None:
    """重置全局单例（主要用于测试）。"""
    global _global_instance
    with _global_lock:
        _global_instance = None
