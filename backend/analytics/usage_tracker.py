"""用量追踪器模块

追踪 API 调用次数、Token 用量、成本，支持：
    - 按用户/Agent/模型/阶段多维统计
    - 预算管理与超限告警
    - 配额控制（硬限制与软限制）
    - 日报/周报/月报生成
    - CSV/JSON 导出
    - 异步批量写入
    - 数据聚合
    - SQLite 持久化

成本计算基于可配置的模型价格表（每千 Token 价格），
默认覆盖 DeepSeek、OpenAI 主流模型。

典型用法：
    tracker = UsageTracker.get_instance()
    tracker.record_llm_usage(
        user_id="user-1",
        agent_id="reasoner",
        model="deepseek-chat",
        stage="creativity",
        prompt_tokens=1200,
        completion_tokens=800,
    )
    report = tracker.generate_daily_report(date="2026-06-19")
    csv_text = tracker.export_csv(start_date="2026-06-01", end_date="2026-06-19")
"""
from __future__ import annotations

import asyncio
import csv
import io
import json
import sqlite3
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, List, Optional, Tuple

# 尝试导入项目内模块
try:
    from backend.database import DB_PATH
except Exception:  # pragma: no cover
    DB_PATH = "data/thesis_miner.db"

try:
    from backend.utils.logger import get_logger

    _logger = get_logger(__name__)
except Exception:  # pragma: no cover
    import logging

    _logger = logging.getLogger(__name__)


# ===== 默认配置常量 =====

# 批量写入缓冲区大小
DEFAULT_BATCH_SIZE = 200

# 批量写入刷新间隔（秒）
DEFAULT_FLUSH_INTERVAL = 5.0

# 内存中保留的最近记录数
DEFAULT_RECENT_CAPACITY = 10000

# 默认预算告警阈值（百分比）
DEFAULT_BUDGET_WARNING_PCT = 80.0
DEFAULT_BUDGET_CRITICAL_PCT = 95.0

# 默认配额刷新周期：daily / weekly / monthly
DEFAULT_QUOTA_PERIOD = "daily"


def _now_ts() -> float:
    """获取当前 UTC 时间戳。"""
    return time.time()


def _iso_now() -> str:
    """获取当前 UTC 时间的 ISO8601 字符串。"""
    return datetime.now(tz=timezone.utc).isoformat()


def _today_str() -> str:
    """获取当前 UTC 日期字符串（YYYY-MM-DD）。"""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")


def _date_to_str(d: date) -> str:
    """date 转字符串。"""
    return d.strftime("%Y-%m-%d")


def _parse_date(s: str) -> date:
    """解析日期字符串。"""
    return datetime.strptime(s, "%Y-%m-%d").date()


def _safe_float(value: Any, default: float = 0.0) -> float:
    """安全转换为 float。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    """安全转换为 int。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ===== 默认模型价格表（每千 Token，单位：美元）=====
# 价格仅供参考，实际使用时应在配置文件中覆盖
DEFAULT_MODEL_PRICING: Dict[str, Dict[str, float]] = {
    # DeepSeek
    "deepseek-chat": {"prompt": 0.0014, "completion": 0.0028},
    "deepseek-coder": {"prompt": 0.0014, "completion": 0.0028},
    "deepseek-reasoner": {"prompt": 0.004, "completion": 0.016},
    # OpenAI
    "gpt-4o": {"prompt": 0.005, "completion": 0.015},
    "gpt-4o-mini": {"prompt": 0.00015, "completion": 0.0006},
    "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
    "gpt-4": {"prompt": 0.03, "completion": 0.06},
    "gpt-3.5-turbo": {"prompt": 0.0005, "completion": 0.0015},
    # Anthropic
    "claude-3-opus": {"prompt": 0.015, "completion": 0.075},
    "claude-3-sonnet": {"prompt": 0.003, "completion": 0.015},
    "claude-3-haiku": {"prompt": 0.00025, "completion": 0.00125},
    # 本地模型（零成本）
    "local": {"prompt": 0.0, "completion": 0.0},
    "random": {"prompt": 0.0, "completion": 0.0},
}

# 默认 embedding 模型价格（每千 Token）
DEFAULT_EMBEDDING_PRICING: Dict[str, float] = {
    "text-embedding-3-small": 0.00002,
    "text-embedding-3-large": 0.00013,
    "text-embedding-ada-002": 0.0001,
    "local": 0.0,
}


@dataclass
class UsageRecord:
    """单次用量记录。"""

    record_id: str = ""
    user_id: str = ""
    session_id: str = ""
    agent_id: str = ""
    model: str = ""
    stage: str = ""  # info_confirm / creativity / validation / generation / deep_assist
    operation: str = ""  # llm_call / embedding / cache_lookup / api_request
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    cache_hit: bool = False
    cache_saved_tokens: int = 0
    duration_ms: float = 0.0
    success: bool = True
    error_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=_now_ts)

    def to_dict(self) -> Dict[str, Any]:
        """转为字典。"""
        return {
            "record_id": self.record_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "model": self.model,
            "stage": self.stage,
            "operation": self.operation,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": self.cost_usd,
            "cache_hit": self.cache_hit,
            "cache_saved_tokens": self.cache_saved_tokens,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "iso_timestamp": datetime.fromtimestamp(
                self.timestamp, tz=timezone.utc
            ).isoformat(),
            "date": datetime.fromtimestamp(self.timestamp, tz=timezone.utc).strftime(
                "%Y-%m-%d"
            ),
        }


@dataclass
class Budget:
    """预算配置。"""

    name: str
    user_id: str = ""  # 空表示全局预算
    period: str = DEFAULT_QUOTA_PERIOD  # daily / weekly / monthly
    token_limit: int = 0  # 0 表示不限制
    cost_limit_usd: float = 0.0  # 0 表示不限制
    request_limit: int = 0  # 0 表示不限制
    warning_pct: float = DEFAULT_BUDGET_WARNING_PCT
    critical_pct: float = DEFAULT_BUDGET_CRITICAL_PCT
    enabled: bool = True
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "user_id": self.user_id,
            "period": self.period,
            "token_limit": self.token_limit,
            "cost_limit_usd": self.cost_limit_usd,
            "request_limit": self.request_limit,
            "warning_pct": self.warning_pct,
            "critical_pct": self.critical_pct,
            "enabled": self.enabled,
            "description": self.description,
        }


@dataclass
class BudgetStatus:
    """预算使用状态。"""

    budget: Budget
    used_tokens: int = 0
    used_cost_usd: float = 0.0
    used_requests: int = 0
    period_start: float = 0.0
    period_end: float = 0.0
    is_exceeded: bool = False
    is_warning: bool = False
    is_critical: bool = False
    usage_pct: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "budget": self.budget.to_dict(),
            "used_tokens": self.used_tokens,
            "used_cost_usd": self.used_cost_usd,
            "used_requests": self.used_requests,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "is_exceeded": self.is_exceeded,
            "is_warning": self.is_warning,
            "is_critical": self.is_critical,
            "usage_pct": self.usage_pct,
        }


@dataclass
class QuotaCheckResult:
    """配额检查结果。"""

    allowed: bool
    reason: str = ""
    exceeded_budgets: List[str] = field(default_factory=list)
    warning_budgets: List[str] = field(default_factory=list)


class PricingCalculator:
    """成本计算器

    根据模型价格表计算单次调用的成本。
    """

    def __init__(
        self,
        llm_pricing: Optional[Dict[str, Dict[str, float]]] = None,
        embedding_pricing: Optional[Dict[str, float]] = None,
    ):
        """初始化成本计算器。

        Args:
            llm_pricing: LLM 模型价格表。
            embedding_pricing: Embedding 模型价格表。
        """
        self.llm_pricing: Dict[str, Dict[str, float]] = dict(llm_pricing or DEFAULT_MODEL_PRICING)
        self.embedding_pricing: Dict[str, float] = dict(
            embedding_pricing or DEFAULT_EMBEDDING_PRICING
        )
        self._lock = threading.RLock()

    def update_llm_price(
        self,
        model: str,
        prompt_per_1k: float,
        completion_per_1k: float,
    ) -> None:
        """更新 LLM 模型价格。"""
        with self._lock:
            self.llm_pricing[model] = {
                "prompt": prompt_per_1k,
                "completion": completion_per_1k,
            }

    def update_embedding_price(self, model: str, price_per_1k: float) -> None:
        """更新 Embedding 模型价格。"""
        with self._lock:
            self.embedding_pricing[model] = price_per_1k

    def get_llm_price(self, model: str) -> Tuple[float, float]:
        """获取 LLM 模型价格。

        Returns:
            (prompt_per_1k, completion_per_1k) 元组。
        """
        with self._lock:
            price = self.llm_pricing.get(model)
            if price:
                return price["prompt"], price["completion"]
            # 未知模型使用默认价格
            default = self.llm_pricing.get("deepseek-chat", {"prompt": 0.001, "completion": 0.002})
            return default["prompt"], default["completion"]

    def calculate_llm_cost(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:
        """计算 LLM 调用成本（美元）。"""
        prompt_price, completion_price = self.get_llm_price(model)
        cost = (prompt_tokens / 1000.0) * prompt_price + (
            completion_tokens / 1000.0
        ) * completion_price
        return round(cost, 6)

    def calculate_embedding_cost(self, model: str, token_count: int) -> float:
        """计算 Embedding 调用成本。"""
        with self._lock:
            price = self.embedding_pricing.get(model, 0.0)
        return round((token_count / 1000.0) * price, 6)

    def list_models(self) -> Dict[str, Any]:
        """列出所有已知模型的价格。"""
        with self._lock:
            return {
                "llm": dict(self.llm_pricing),
                "embedding": dict(self.embedding_pricing),
            }


class BudgetManager:
    """预算管理器

    管理多个预算配置，跟踪使用量，触发告警。
    """

    def __init__(self):
        self._budgets: Dict[str, Budget] = {}
        self._usage_cache: Dict[str, BudgetStatus] = {}
        self._callbacks: List = []
        self._lock = threading.RLock()

    def add_budget(self, budget: Budget) -> None:
        """添加预算配置。"""
        with self._lock:
            self._budgets[budget.name] = budget

    def remove_budget(self, name: str) -> bool:
        """移除预算。"""
        with self._lock:
            existed = self._budgets.pop(name, None) is not None
            self._usage_cache.pop(name, None)
            return existed

    def get_budget(self, name: str) -> Optional[Budget]:
        """获取预算配置。"""
        with self._lock:
            return self._budgets.get(name)

    def list_budgets(self) -> List[Budget]:
        """列出所有预算。"""
        with self._lock:
            return list(self._budgets.values())

    def add_callback(self, callback) -> None:
        """注册预算告警回调。"""
        self._callbacks.append(callback)

    def get_period_range(self, period: str, now: Optional[float] = None) -> Tuple[float, float]:
        """计算当前周期的时间范围。

        Args:
            period: daily / weekly / monthly。
            now: 当前时间戳，None 则使用真实当前时间。

        Returns:
            (period_start, period_end) 时间戳元组。
        """
        ts = now or _now_ts()
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        if period == "daily":
            start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif period == "weekly":
            # 周一为一周开始
            start = dt - timedelta(days=dt.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=7)
        elif period == "monthly":
            start = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if dt.month == 12:
                end = start.replace(year=dt.year + 1, month=1)
            else:
                end = start.replace(month=dt.month + 1)
        else:
            start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        return start.timestamp(), end.timestamp()

    def update_usage(
        self,
        budget_name: str,
        tokens: int,
        cost: float,
        requests: int = 1,
        records: Optional[List[UsageRecord]] = None,
    ) -> BudgetStatus:
        """更新预算使用量。

        Args:
            budget_name: 预算名。
            tokens: 本次新增 Token 数。
            cost: 本次新增成本。
            requests: 本次新增请求数。
            records: 可选，用于精确计算周期内用量的全部记录。

        Returns:
            更新后的预算状态。
        """
        with self._lock:
            budget = self._budgets.get(budget_name)
            if not budget or not budget.enabled:
                raise ValueError(f"预算 {budget_name} 不存在或未启用")
            period_start, period_end = self.get_period_range(budget.period)
            # 若使用 records 重新精确计算
            if records is not None:
                period_records = [
                    r
                    for r in records
                    if period_start <= r.timestamp < period_end
                    and (not budget.user_id or r.user_id == budget.user_id)
                ]
                used_tokens = sum(r.total_tokens for r in period_records)
                used_cost = sum(r.cost_usd for r in period_records)
                used_requests = len(period_records)
            else:
                # 增量更新缓存
                cached = self._usage_cache.get(budget_name)
                if (
                    cached
                    and cached.period_start == period_start
                ):
                    used_tokens = cached.used_tokens + tokens
                    used_cost = cached.used_cost_usd + cost
                    used_requests = cached.used_requests + requests
                else:
                    used_tokens = tokens
                    used_cost = cost
                    used_requests = requests
            # 计算使用率与状态
            usage_pct = 0.0
            if budget.token_limit > 0:
                usage_pct = max(usage_pct, used_tokens / budget.token_limit * 100)
            if budget.cost_limit_usd > 0:
                usage_pct = max(usage_pct, used_cost / budget.cost_limit_usd * 100)
            if budget.request_limit > 0:
                usage_pct = max(usage_pct, used_requests / budget.request_limit * 100)
            is_exceeded = (
                (budget.token_limit > 0 and used_tokens >= budget.token_limit)
                or (budget.cost_limit_usd > 0 and used_cost >= budget.cost_limit_usd)
                or (budget.request_limit > 0 and used_requests >= budget.request_limit)
            )
            is_critical = usage_pct >= budget.critical_pct
            is_warning = usage_pct >= budget.warning_pct
            status = BudgetStatus(
                budget=budget,
                used_tokens=used_tokens,
                used_cost_usd=used_cost,
                used_requests=used_requests,
                period_start=period_start,
                period_end=period_end,
                is_exceeded=is_exceeded,
                is_warning=is_warning,
                is_critical=is_critical,
                usage_pct=usage_pct,
            )
            self._usage_cache[budget_name] = status
            # 触发告警回调
            if is_exceeded or is_critical or is_warning:
                for callback in self._callbacks:
                    try:
                        callback(status)
                    except Exception as e:
                        _logger.error(f"预算告警回调失败: {e}", exc_info=True)
            return status

    def get_status(self, budget_name: str) -> Optional[BudgetStatus]:
        """获取预算当前状态。"""
        with self._lock:
            return self._usage_cache.get(budget_name)

    def get_all_statuses(self) -> List[BudgetStatus]:
        """获取所有预算状态。"""
        with self._lock:
            return list(self._usage_cache.values())

    def check_quota(
        self,
        user_id: str,
        estimated_tokens: int = 0,
        estimated_cost: float = 0.0,
    ) -> QuotaCheckResult:
        """检查配额是否允许新调用。

        Args:
            user_id: 用户 ID。
            estimated_tokens: 预估 Token 数。
            estimated_cost: 预估成本。

        Returns:
            检查结果。
        """
        result = QuotaCheckResult(allowed=True)
        with self._lock:
            for budget in self._budgets.values():
                if not budget.enabled:
                    continue
                if budget.user_id and budget.user_id != user_id:
                    continue
                status = self._usage_cache.get(budget.name)
                if not status:
                    continue
                # 检查是否超限
                if budget.token_limit > 0:
                    if status.used_tokens + estimated_tokens >= budget.token_limit:
                        result.allowed = False
                        result.exceeded_budgets.append(budget.name)
                        result.reason = f"预算 {budget.name} Token 即将超限"
                if budget.cost_limit_usd > 0:
                    if status.used_cost_usd + estimated_cost >= budget.cost_limit_usd:
                        result.allowed = False
                        result.exceeded_budgets.append(budget.name)
                        result.reason = f"预算 {budget.name} 成本即将超限"
                if status.is_warning:
                    result.warning_budgets.append(budget.name)
        return result

    def clear(self) -> None:
        """清空所有预算状态。"""
        with self._lock:
            self._usage_cache.clear()


class UsageAggregator:
    """用量数据聚合器

    按多个维度（用户/Agent/模型/阶段/日期）聚合用量数据。
    """

    @staticmethod
    def aggregate_by_dimension(
        records: List[UsageRecord],
        dimension: str,
    ) -> Dict[str, Dict[str, Any]]:
        """按指定维度聚合。

        Args:
            records: 用量记录列表。
            dimension: 聚合维度，可选 user_id / agent_id / model / stage / operation / date。

        Returns:
            {dimension_value: {stats}} 字典。
        """
        groups: Dict[str, List[UsageRecord]] = defaultdict(list)
        for r in records:
            key = UsageAggregator._get_dimension_value(r, dimension)
            groups[key].append(r)
        result: Dict[str, Dict[str, Any]] = {}
        for key, group_records in groups.items():
            result[key] = UsageAggregator._compute_stats(group_records)
        return result

    @staticmethod
    def _get_dimension_value(record: UsageRecord, dimension: str) -> str:
        """获取记录的维度值。"""
        if dimension == "date":
            return datetime.fromtimestamp(record.timestamp, tz=timezone.utc).strftime(
                "%Y-%m-%d"
            )
        return str(getattr(record, dimension, "") or "")

    @staticmethod
    def _compute_stats(records: List[UsageRecord]) -> Dict[str, Any]:
        """计算一组记录的统计。"""
        if not records:
            return {
                "count": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost_usd": 0.0,
                "cache_hit_count": 0,
                "cache_hit_rate": 0.0,
                "success_count": 0,
                "success_rate": 0.0,
                "avg_duration_ms": 0.0,
            }
        n = len(records)
        prompt_tokens = sum(r.prompt_tokens for r in records)
        completion_tokens = sum(r.completion_tokens for r in records)
        total_tokens = sum(r.total_tokens for r in records)
        cost = sum(r.cost_usd for r in records)
        cache_hits = sum(1 for r in records if r.cache_hit)
        successes = sum(1 for r in records if r.success)
        total_duration = sum(r.duration_ms for r in records)
        return {
            "count": n,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost_usd": round(cost, 6),
            "cache_hit_count": cache_hits,
            "cache_hit_rate": round(cache_hits / n, 4),
            "success_count": successes,
            "success_rate": round(successes / n, 4),
            "avg_duration_ms": round(total_duration / n, 2),
        }

    @staticmethod
    def aggregate_multi_dimension(
        records: List[UsageRecord],
        dimensions: List[str],
    ) -> Dict[str, Dict[str, Any]]:
        """多维度交叉聚合。

        Args:
            records: 用量记录列表。
            dimensions: 维度列表（如 ["user_id", "model"]）。

        Returns:
            嵌套字典，外层为第一个维度的值，内层为后续维度的聚合结果。
        """
        if not dimensions:
            return {}
        if len(dimensions) == 1:
            return UsageAggregator.aggregate_by_dimension(records, dimensions[0])
        first_dim = dimensions[0]
        rest_dims = dimensions[1:]
        groups: Dict[str, List[UsageRecord]] = defaultdict(list)
        for r in records:
            key = UsageAggregator._get_dimension_value(r, first_dim)
            groups[key].append(r)
        result: Dict[str, Dict[str, Any]] = {}
        for key, group_records in groups.items():
            result[key] = UsageAggregator.aggregate_multi_dimension(
                group_records, rest_dims
            )
        return result

    @staticmethod
    def top_n_by_cost(
        records: List[UsageRecord],
        dimension: str,
        n: int = 10,
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """按成本排名前 N。"""
        aggregated = UsageAggregator.aggregate_by_dimension(records, dimension)
        sorted_items = sorted(
            aggregated.items(), key=lambda x: x[1]["cost_usd"], reverse=True
        )
        return sorted_items[:n]

    @staticmethod
    def top_n_by_tokens(
        records: List[UsageRecord],
        dimension: str,
        n: int = 10,
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """按 Token 数排名前 N。"""
        aggregated = UsageAggregator.aggregate_by_dimension(records, dimension)
        sorted_items = sorted(
            aggregated.items(), key=lambda x: x[1]["total_tokens"], reverse=True
        )
        return sorted_items[:n]


class UsageTracker:
    """用量追踪器（单例）

    整合成本计算、预算管理、数据聚合，提供：
        - 用量记录（同步与异步）
        - 批量写入缓冲
        - 多维统计
        - 报告生成（日报/周报/月报）
        - CSV/JSON 导出
        - SQLite 持久化
        - 配额检查
    """

    _instance: Optional["UsageTracker"] = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> "UsageTracker":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._records: Deque[UsageRecord] = deque(maxlen=DEFAULT_RECENT_CAPACITY)
        self._lock = threading.RLock()
        self.pricing = PricingCalculator()
        self.budget_manager = BudgetManager()
        self._batch_buffer: List[UsageRecord] = []
        self._batch_lock = threading.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._flush_enabled = False
        # 注册默认全局预算
        self._register_default_budgets()

    @classmethod
    def get_instance(cls) -> "UsageTracker":
        """获取单例实例。"""
        return cls()

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例（仅用于测试）。"""
        with cls._instance_lock:
            cls._instance = None

    def _register_default_budgets(self) -> None:
        """注册默认预算。"""
        # 全局每日预算（默认 100 万 Token / 10 美元 / 10000 次请求）
        self.budget_manager.add_budget(
            Budget(
                name="global_daily",
                user_id="",
                period="daily",
                token_limit=1_000_000,
                cost_limit_usd=10.0,
                request_limit=10_000,
                description="全局每日预算",
            )
        )
        # 单用户每日预算（默认 10 万 Token / 1 美元 / 1000 次请求）
        self.budget_manager.add_budget(
            Budget(
                name="user_daily",
                user_id="",
                period="daily",
                token_limit=100_000,
                cost_limit_usd=1.0,
                request_limit=1_000,
                description="单用户每日预算（user_id 留空表示模板）",
            )
        )

    # ===== 记录方法 =====

    def record_llm_usage(
        self,
        user_id: str,
        agent_id: str,
        model: str,
        stage: str,
        prompt_tokens: int,
        completion_tokens: int,
        session_id: str = "",
        cache_hit: bool = False,
        cache_saved_tokens: int = 0,
        duration_ms: float = 0.0,
        success: bool = True,
        error_message: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UsageRecord:
        """记录一次 LLM 调用用量。

        Args:
            user_id: 用户 ID。
            agent_id: Agent ID（searcher/reasoner/critic/mentor/writer/orchestrator）。
            model: 模型名。
            stage: 调用阶段。
            prompt_tokens: 输入 Token 数。
            completion_tokens: 输出 Token 数。
            session_id: 会话 ID。
            cache_hit: 是否命中缓存。
            cache_saved_tokens: 缓存节省的 Token 数。
            duration_ms: 耗时（毫秒）。
            success: 是否成功。
            error_message: 错误信息。
            metadata: 附加元数据。

        Returns:
            创建的用量记录。
        """
        total_tokens = prompt_tokens + completion_tokens
        cost = self.pricing.calculate_llm_cost(model, prompt_tokens, completion_tokens)
        # 缓存命中时，prompt 部分成本按 10% 计算（DeepSeek 缓存价格约为 1/10）
        if cache_hit and cache_saved_tokens > 0:
            saved_cost = self.pricing.calculate_llm_cost(
                model, cache_saved_tokens, 0
            )
            cost = max(0.0, cost - saved_cost * 0.9)
        record = UsageRecord(
            record_id=f"rec-{int(_now_ts() * 1000)}-{threading.get_ident() % 10000}",
            user_id=user_id,
            session_id=session_id,
            agent_id=agent_id,
            model=model,
            stage=stage,
            operation="llm_call",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost,
            cache_hit=cache_hit,
            cache_saved_tokens=cache_saved_tokens,
            duration_ms=duration_ms,
            success=success,
            error_message=error_message,
            metadata=metadata or {},
        )
        self._add_record(record)
        return record

    def record_embedding_usage(
        self,
        user_id: str,
        model: str,
        token_count: int,
        session_id: str = "",
        agent_id: str = "",
        stage: str = "",
        duration_ms: float = 0.0,
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UsageRecord:
        """记录一次 Embedding 调用用量。"""
        cost = self.pricing.calculate_embedding_cost(model, token_count)
        record = UsageRecord(
            record_id=f"emb-{int(_now_ts() * 1000)}-{threading.get_ident() % 10000}",
            user_id=user_id,
            session_id=session_id,
            agent_id=agent_id,
            model=model,
            stage=stage,
            operation="embedding",
            prompt_tokens=token_count,
            completion_tokens=0,
            total_tokens=token_count,
            cost_usd=cost,
            duration_ms=duration_ms,
            success=success,
            metadata=metadata or {},
        )
        self._add_record(record)
        return record

    def record_api_request(
        self,
        user_id: str,
        endpoint: str,
        method: str = "GET",
        status_code: int = 200,
        duration_ms: float = 0.0,
        session_id: str = "",
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UsageRecord:
        """记录一次 API 请求（不涉及 Token 成本）。"""
        record = UsageRecord(
            record_id=f"api-{int(_now_ts() * 1000)}-{threading.get_ident() % 10000}",
            user_id=user_id,
            session_id=session_id,
            operation="api_request",
            duration_ms=duration_ms,
            success=success,
            metadata={
                "endpoint": endpoint,
                "method": method,
                "status_code": status_code,
                **(metadata or {}),
            },
        )
        self._add_record(record)
        return record

    def _add_record(self, record: UsageRecord) -> None:
        """添加记录到内存与批量缓冲。"""
        with self._lock:
            self._records.append(record)
        # 更新预算
        self._update_budgets(record)
        # 加入批量缓冲
        with self._batch_lock:
            self._batch_buffer.append(record)
            if len(self._batch_buffer) >= DEFAULT_BATCH_SIZE:
                self._flush_batch_locked()

    def _update_budgets(self, record: UsageRecord) -> None:
        """更新相关预算的使用量。"""
        for budget in self.budget_manager.list_budgets():
            if not budget.enabled:
                continue
            # 全局预算或匹配用户的预算
            if budget.user_id and budget.user_id != record.user_id:
                continue
            try:
                self.budget_manager.update_usage(
                    budget.name,
                    tokens=record.total_tokens,
                    cost=record.cost_usd,
                    requests=1,
                )
            except Exception as e:
                _logger.debug(f"预算更新失败 {budget.name}: {e}")

    # ===== 配额检查 =====

    def check_quota(
        self,
        user_id: str,
        estimated_tokens: int = 0,
        estimated_cost: float = 0.0,
    ) -> QuotaCheckResult:
        """检查配额。"""
        return self.budget_manager.check_quota(user_id, estimated_tokens, estimated_cost)

    def is_allowed(self, user_id: str, estimated_tokens: int = 0) -> bool:
        """快速判断是否允许调用。"""
        return self.check_quota(user_id, estimated_tokens).allowed

    # ===== 查询方法 =====

    def get_records(
        self,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        model: Optional[str] = None,
        stage: Optional[str] = None,
        operation: Optional[str] = None,
        start_ts: Optional[float] = None,
        end_ts: Optional[float] = None,
        limit: int = 0,
    ) -> List[UsageRecord]:
        """查询用量记录。"""
        with self._lock:
            records = list(self._records)
        # 过滤
        if user_id is not None:
            records = [r for r in records if r.user_id == user_id]
        if agent_id is not None:
            records = [r for r in records if r.agent_id == agent_id]
        if model is not None:
            records = [r for r in records if r.model == model]
        if stage is not None:
            records = [r for r in records if r.stage == stage]
        if operation is not None:
            records = [r for r in records if r.operation == operation]
        if start_ts is not None:
            records = [r for r in records if r.timestamp >= start_ts]
        if end_ts is not None:
            records = [r for r in records if r.timestamp <= end_ts]
        if limit > 0:
            records = records[-limit:]
        return records

    def get_records_by_date(
        self,
        date_str: str,
        user_id: Optional[str] = None,
    ) -> List[UsageRecord]:
        """按日期查询记录。"""
        target_date = _parse_date(date_str)
        start_ts = datetime.combine(
            target_date, datetime.min.time(), tzinfo=timezone.utc
        ).timestamp()
        end_ts = start_ts + 86400
        return self.get_records(user_id=user_id, start_ts=start_ts, end_ts=end_ts)

    def get_summary(
        self,
        user_id: Optional[str] = None,
        start_ts: Optional[float] = None,
        end_ts: Optional[float] = None,
    ) -> Dict[str, Any]:
        """获取用量摘要。"""
        records = self.get_records(user_id=user_id, start_ts=start_ts, end_ts=end_ts)
        return UsageAggregator._compute_stats(records)

    # ===== 报告生成 =====

    def generate_daily_report(
        self,
        date_str: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """生成日报。"""
        target_date = date_str or _today_str()
        records = self.get_records_by_date(target_date, user_id=user_id)
        return self._build_report(
            title=f"日报 - {target_date}",
            records=records,
            period_type="daily",
            period_value=target_date,
        )

    def generate_weekly_report(
        self,
        week_start: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """生成周报。"""
        if week_start:
            start_date = _parse_date(week_start)
        else:
            today = datetime.now(tz=timezone.utc).date()
            start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
        start_ts = datetime.combine(
            start_date, datetime.min.time(), tzinfo=timezone.utc
        ).timestamp()
        end_ts = datetime.combine(
            end_date, datetime.max.time(), tzinfo=timezone.utc
        ).timestamp()
        records = self.get_records(user_id=user_id, start_ts=start_ts, end_ts=end_ts)
        return self._build_report(
            title=f"周报 - {start_date} 至 {end_date}",
            records=records,
            period_type="weekly",
            period_value=f"{start_date}~{end_date}",
        )

    def generate_monthly_report(
        self,
        year_month: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """生成月报。

        Args:
            year_month: 形如 "2026-06" 的字符串，None 则使用当前月。
        """
        if year_month:
            year, month = map(int, year_month.split("-"))
        else:
            now = datetime.now(tz=timezone.utc)
            year, month = now.year, now.month
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
        start_ts = datetime.combine(
            start_date, datetime.min.time(), tzinfo=timezone.utc
        ).timestamp()
        end_ts = datetime.combine(
            end_date, datetime.max.time(), tzinfo=timezone.utc
        ).timestamp()
        records = self.get_records(user_id=user_id, start_ts=start_ts, end_ts=end_ts)
        return self._build_report(
            title=f"月报 - {year}-{month:02d}",
            records=records,
            period_type="monthly",
            period_value=f"{year}-{month:02d}",
        )

    def _build_report(
        self,
        title: str,
        records: List[UsageRecord],
        period_type: str,
        period_value: str,
    ) -> Dict[str, Any]:
        """构建报告字典。"""
        overall = UsageAggregator._compute_stats(records)
        by_user = UsageAggregator.aggregate_by_dimension(records, "user_id")
        by_agent = UsageAggregator.aggregate_by_dimension(records, "agent_id")
        by_model = UsageAggregator.aggregate_by_dimension(records, "model")
        by_stage = UsageAggregator.aggregate_by_dimension(records, "stage")
        by_operation = UsageAggregator.aggregate_by_dimension(records, "operation")
        by_date = UsageAggregator.aggregate_by_dimension(records, "date")
        top_users_cost = UsageAggregator.top_n_by_cost(records, "user_id", n=10)
        top_models_cost = UsageAggregator.top_n_by_cost(records, "model", n=10)
        top_agents_cost = UsageAggregator.top_n_by_cost(records, "agent_id", n=10)
        return {
            "title": title,
            "period_type": period_type,
            "period_value": period_value,
            "generated_at": _iso_now(),
            "overall": overall,
            "by_user": by_user,
            "by_agent": by_agent,
            "by_model": by_model,
            "by_stage": by_stage,
            "by_operation": by_operation,
            "by_date": by_date,
            "top_users_by_cost": top_users_cost,
            "top_models_by_cost": top_models_cost,
            "top_agents_by_cost": top_agents_cost,
            "budget_statuses": [
                s.to_dict() for s in self.budget_manager.get_all_statuses()
            ],
        }

    # ===== 导出 =====

    def export_csv(
        self,
        output_path: Optional[str] = None,
        user_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> str:
        """导出为 CSV。

        Args:
            output_path: 输出文件路径，None 则返回字符串。
            user_id: 用户过滤。
            start_date: 起始日期（YYYY-MM-DD）。
            end_date: 结束日期（YYYY-MM-DD）。

        Returns:
            CSV 文本（output_path 为 None 时）。
        """
        start_ts = (
            datetime.combine(_parse_date(start_date), datetime.min.time(), tzinfo=timezone.utc).timestamp()
            if start_date
            else None
        )
        end_ts = (
            datetime.combine(_parse_date(end_date), datetime.max.time(), tzinfo=timezone.utc).timestamp()
            if end_date
            else None
        )
        records = self.get_records(
            user_id=user_id, start_ts=start_ts, end_ts=end_ts
        )
        output = io.StringIO()
        fieldnames = [
            "record_id", "timestamp", "iso_timestamp", "date",
            "user_id", "session_id", "agent_id", "model", "stage", "operation",
            "prompt_tokens", "completion_tokens", "total_tokens", "cost_usd",
            "cache_hit", "cache_saved_tokens", "duration_ms",
            "success", "error_message",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            d = r.to_dict()
            row = {k: d.get(k, "") for k in fieldnames}
            writer.writerow(row)
        csv_text = output.getvalue()
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8", newline="") as f:
                f.write(csv_text)
        return csv_text

    def export_json(
        self,
        output_path: Optional[str] = None,
        user_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        indent: Optional[int] = 2,
    ) -> str:
        """导出为 JSON。"""
        start_ts = (
            datetime.combine(_parse_date(start_date), datetime.min.time(), tzinfo=timezone.utc).timestamp()
            if start_date
            else None
        )
        end_ts = (
            datetime.combine(_parse_date(end_date), datetime.max.time(), tzinfo=timezone.utc).timestamp()
            if end_date
            else None
        )
        records = self.get_records(
            user_id=user_id, start_ts=start_ts, end_ts=end_ts
        )
        data = {
            "exported_at": _iso_now(),
            "filter": {
                "user_id": user_id,
                "start_date": start_date,
                "end_date": end_date,
            },
            "record_count": len(records),
            "records": [r.to_dict() for r in records],
        }
        json_text = json.dumps(data, ensure_ascii=False, default=str, indent=indent)
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(json_text)
        return json_text

    def export_report(
        self,
        report: Dict[str, Any],
        output_path: str,
        fmt: str = "json",
    ) -> None:
        """导出报告到文件。"""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        if fmt == "json":
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, default=str, indent=2)
        elif fmt == "csv":
            # 报告 CSV：按用户维度导出
            with open(output_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["维度值", "请求数", "Token 数", "成本(USD)", "缓存命中率", "成功率"])
                for dim_name in ["by_user", "by_agent", "by_model", "by_stage"]:
                    writer.writerow([f"=== {dim_name} ===", "", "", "", "", ""])
                    for key, stats in report.get(dim_name, {}).items():
                        writer.writerow(
                            [
                                key,
                                stats.get("count", 0),
                                stats.get("total_tokens", 0),
                                stats.get("cost_usd", 0),
                                stats.get("cache_hit_rate", 0),
                                stats.get("success_rate", 0),
                            ]
                        )
        else:
            raise ValueError(f"不支持的导出格式: {fmt}")

    # ===== 批量写入 =====

    def flush_batch(self) -> int:
        """刷新批量缓冲区，将记录写入 SQLite。"""
        with self._batch_lock:
            return self._flush_batch_locked()

    def _flush_batch_locked(self) -> int:
        """实际执行批量刷新。"""
        if not self._batch_buffer:
            return 0
        records = list(self._batch_buffer)
        self._batch_buffer.clear()
        try:
            self._write_to_db(records)
        except Exception as e:
            _logger.error(f"批量写入数据库失败: {e}", exc_info=True)
            # 失败时放回缓冲区
            with self._batch_lock:
                self._batch_buffer = records + self._batch_buffer
            return 0
        return len(records)

    async def start_flush_task(self, interval: float = DEFAULT_FLUSH_INTERVAL) -> None:
        """启动异步定时刷新任务。"""
        if self._flush_enabled:
            return
        self._flush_enabled = True

        async def _run():
            while self._flush_enabled:
                try:
                    self.flush_batch()
                except Exception as e:
                    _logger.error(f"定时刷新异常: {e}", exc_info=True)
                await asyncio.sleep(interval)

        self._flush_task = asyncio.create_task(_run())
        _logger.info(f"用量定时刷新任务已启动，间隔 {interval} 秒")

    async def stop_flush_task(self) -> None:
        """停止异步定时刷新任务。"""
        self._flush_enabled = False
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        self._flush_task = None
        # 最后刷新一次
        self.flush_batch()

    # ===== SQLite 持久化 =====

    def _ensure_table(self, conn: sqlite3.Connection) -> None:
        """确保持久化表存在。"""
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usage_records (
                record_id TEXT PRIMARY KEY,
                user_id TEXT,
                session_id TEXT,
                agent_id TEXT,
                model TEXT,
                stage TEXT,
                operation TEXT,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                total_tokens INTEGER,
                cost_usd REAL,
                cache_hit INTEGER,
                cache_saved_tokens INTEGER,
                duration_ms REAL,
                success INTEGER,
                error_message TEXT,
                metadata TEXT,
                timestamp REAL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_usage_user_ts ON usage_records(user_id, timestamp)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_usage_model_ts ON usage_records(model, timestamp)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_usage_agent_ts ON usage_records(agent_id, timestamp)"
        )

    def _write_to_db(self, records: List[UsageRecord]) -> None:
        """将记录写入 SQLite。"""
        path = DB_PATH
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        try:
            self._ensure_table(conn)
            for r in records:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO usage_records
                    (record_id, user_id, session_id, agent_id, model, stage, operation,
                     prompt_tokens, completion_tokens, total_tokens, cost_usd,
                     cache_hit, cache_saved_tokens, duration_ms, success, error_message,
                     metadata, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        r.record_id,
                        r.user_id,
                        r.session_id,
                        r.agent_id,
                        r.model,
                        r.stage,
                        r.operation,
                        r.prompt_tokens,
                        r.completion_tokens,
                        r.total_tokens,
                        r.cost_usd,
                        1 if r.cache_hit else 0,
                        r.cache_saved_tokens,
                        r.duration_ms,
                        1 if r.success else 0,
                        r.error_message,
                        json.dumps(r.metadata, ensure_ascii=False),
                        r.timestamp,
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def load_from_db(
        self,
        db_path: Optional[str] = None,
        limit: int = 10000,
    ) -> int:
        """从 SQLite 加载历史记录。"""
        path = db_path or DB_PATH
        if not Path(path).exists():
            return 0
        total = 0
        try:
            conn = sqlite3.connect(path)
            try:
                cursor = conn.execute(
                    "SELECT record_id, user_id, session_id, agent_id, model, stage, operation, "
                    "prompt_tokens, completion_tokens, total_tokens, cost_usd, cache_hit, "
                    "cache_saved_tokens, duration_ms, success, error_message, metadata, timestamp "
                    "FROM usage_records ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                )
                for row in cursor:
                    try:
                        metadata = json.loads(row[16]) if row[16] else {}
                    except json.JSONDecodeError:
                        metadata = {}
                    record = UsageRecord(
                        record_id=row[0],
                        user_id=row[1] or "",
                        session_id=row[2] or "",
                        agent_id=row[3] or "",
                        model=row[4] or "",
                        stage=row[5] or "",
                        operation=row[6] or "",
                        prompt_tokens=_safe_int(row[7]),
                        completion_tokens=_safe_int(row[8]),
                        total_tokens=_safe_int(row[9]),
                        cost_usd=_safe_float(row[10]),
                        cache_hit=bool(row[11]),
                        cache_saved_tokens=_safe_int(row[12]),
                        duration_ms=_safe_float(row[13]),
                        success=bool(row[14]),
                        error_message=row[15] or "",
                        metadata=metadata,
                        timestamp=_safe_float(row[17]),
                    )
                    with self._lock:
                        self._records.append(record)
                    total += 1
            finally:
                conn.close()
        except Exception as e:
            _logger.error(f"用量记录加载失败: {e}", exc_info=True)
        return total

    # ===== 预算管理便捷方法 =====

    def add_budget(self, budget: Budget) -> None:
        """添加预算。"""
        self.budget_manager.add_budget(budget)

    def get_budget_status(self, name: str) -> Optional[BudgetStatus]:
        """获取预算状态。"""
        return self.budget_manager.get_status(name)

    def list_budgets(self) -> List[Budget]:
        """列出所有预算。"""
        return self.budget_manager.list_budgets()

    def get_budget_alerts(self) -> List[Dict[str, Any]]:
        """获取当前预算告警。"""
        statuses = self.budget_manager.get_all_statuses()
        alerts = []
        for s in statuses:
            if s.is_exceeded:
                alerts.append(
                    {
                        "level": "critical",
                        "budget": s.budget.name,
                        "message": f"预算 {s.budget.name} 已超限（{s.usage_pct:.1f}%）",
                        "status": s.to_dict(),
                    }
                )
            elif s.is_critical:
                alerts.append(
                    {
                        "level": "critical",
                        "budget": s.budget.name,
                        "message": f"预算 {s.budget.name} 使用率达 {s.usage_pct:.1f}%",
                        "status": s.to_dict(),
                    }
                )
            elif s.is_warning:
                alerts.append(
                    {
                        "level": "warning",
                        "budget": s.budget.name,
                        "message": f"预算 {s.budget.name} 使用率达 {s.usage_pct:.1f}%",
                        "status": s.to_dict(),
                    }
                )
        return alerts

    # ===== 清理 =====

    def clear_records(self) -> None:
        """清空内存记录。"""
        with self._lock:
            self._records.clear()

    def shutdown(self) -> None:
        """关闭追踪器。"""
        if self._flush_enabled:
            self._flush_enabled = False
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
        self._flush_task = None
        # 最后刷新一次
        try:
            self.flush_batch()
        except Exception as e:
            _logger.error(f"关闭时刷新失败: {e}", exc_info=True)
        _logger.info("用量追踪器已关闭")


# ===== 模块级便捷函数 =====


def get_usage_tracker() -> UsageTracker:
    """获取全局用量追踪器单例。"""
    return UsageTracker.get_instance()


def track_llm_call(
    user_id: str,
    agent_id: str,
    model: str,
    stage: str,
    prompt_tokens: int,
    completion_tokens: int,
    **kwargs,
) -> UsageRecord:
    """记录 LLM 调用的便捷函数。"""
    tracker = get_usage_tracker()
    return tracker.record_llm_usage(
        user_id=user_id,
        agent_id=agent_id,
        model=model,
        stage=stage,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        **kwargs,
    )


def track_api_request(
    user_id: str,
    endpoint: str,
    method: str = "GET",
    status_code: int = 200,
    duration_ms: float = 0.0,
    **kwargs,
) -> UsageRecord:
    """记录 API 请求的便捷函数。"""
    tracker = get_usage_tracker()
    return tracker.record_api_request(
        user_id=user_id,
        endpoint=endpoint,
        method=method,
        status_code=status_code,
        duration_ms=duration_ms,
        **kwargs,
    )


def check_user_quota(user_id: str, estimated_tokens: int = 0) -> bool:
    """检查用户配额的便捷函数。"""
    tracker = get_usage_tracker()
    return tracker.is_allowed(user_id, estimated_tokens)


# ===== 单元测试可运行逻辑 =====


def _run_self_test() -> None:
    """模块自检。

    可直接 `python -m backend.analytics.usage_tracker` 运行。
    """
    UsageTracker.reset_instance()
    tracker = UsageTracker.get_instance()

    # 测试 LLM 用量记录
    for i in range(20):
        tracker.record_llm_usage(
            user_id="user-1" if i % 2 == 0 else "user-2",
            agent_id=["searcher", "reasoner", "critic", "writer"][i % 4],
            model="deepseek-chat",
            stage=["creativity", "generation", "validation"][i % 3],
            prompt_tokens=500 + i * 10,
            completion_tokens=200 + i * 5,
            cache_hit=(i % 5 == 0),
            cache_saved_tokens=100 if i % 5 == 0 else 0,
            duration_ms=500.0 + i * 10,
        )
    # 测试 Embedding 用量记录
    for i in range(5):
        tracker.record_embedding_usage(
            user_id="user-1",
            model="text-embedding-3-small",
            token_count=300 + i * 50,
            agent_id="searcher",
            stage="creativity",
        )
    # 测试 API 请求记录
    for i in range(10):
        tracker.record_api_request(
            user_id="user-1",
            endpoint="/api/sessions",
            method="GET",
            status_code=200,
            duration_ms=20.0 + i,
        )

    # 验证记录数
    all_records = tracker.get_records()
    assert len(all_records) >= 35, f"记录数应 >= 35，实际 {len(all_records)}"

    # 验证成本计算
    llm_records = tracker.get_records(operation="llm_call")
    assert len(llm_records) == 20
    total_cost = sum(r.cost_usd for r in llm_records)
    assert total_cost > 0, "LLM 总成本应 > 0"

    # 验证聚合
    by_user = UsageAggregator.aggregate_by_dimension(llm_records, "user_id")
    assert "user-1" in by_user
    assert "user-2" in by_user
    by_model = UsageAggregator.aggregate_by_dimension(llm_records, "model")
    assert "deepseek-chat" in by_model

    # 验证 Top N
    top_users = UsageAggregator.top_n_by_cost(llm_records, "user_id", n=5)
    assert len(top_users) <= 5

    # 验证日报
    daily_report = tracker.generate_daily_report()
    assert "overall" in daily_report
    assert daily_report["overall"]["count"] >= 35
    print(f"日报生成成功：{daily_report['overall']['count']} 条记录，成本 ${daily_report['overall']['cost_usd']:.4f}")

    # 验证 CSV 导出
    csv_text = tracker.export_csv()
    assert "record_id" in csv_text
    lines = csv_text.strip().split("\n")
    assert len(lines) >= 36  # header + 35 records

    # 验证 JSON 导出
    json_text = tracker.export_json()
    parsed = json.loads(json_text)
    assert parsed["record_count"] >= 35

    # 验证预算管理
    budgets = tracker.list_budgets()
    assert len(budgets) >= 2
    alerts = tracker.get_budget_alerts()
    print(f"预算告警数：{len(alerts)}")

    # 验证配额检查
    quota = tracker.check_quota("user-1", estimated_tokens=100)
    assert isinstance(quota.allowed, bool)

    # 验证多维度聚合
    multi = UsageAggregator.aggregate_multi_dimension(
        llm_records, ["user_id", "model"]
    )
    assert "user-1" in multi

    tracker.shutdown()
    print("UsageTracker 自检通过")


if __name__ == "__main__":
    _run_self_test()
