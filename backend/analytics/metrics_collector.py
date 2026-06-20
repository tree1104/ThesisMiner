"""指标收集器模块

提供 Counter / Gauge / Histogram 三种指标类型，支持：
    - 多维度标签（labels）
    - 滑动窗口统计与百分位计算（p50/p90/p99）
    - Prometheus 文本格式导出
    - JSON 序列化导出
    - 时序数据持久化（SQLite）
    - 异步批量上报
    - 线程安全

设计参考 Prometheus 客户端规范，但完全使用 Python 标准库实现，
避免引入 prometheus_client 等外部依赖。

典型用法：
    collector = MetricsCollector.get_instance()
    counter = collector.counter("api_requests_total", "API 请求总数")
    counter.inc(labels={"method": "GET", "path": "/sessions"})
    histogram = collector.histogram("api_latency_seconds", "API 延迟")
    histogram.observe(0.123, labels={"path": "/sessions"})
    prom_text = collector.export_prometheus()
"""
from __future__ import annotations

import asyncio
import bisect
import json
import math
import sqlite3
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, List, Optional, Tuple

# 尝试导入项目内数据库模块（用于时序数据持久化）
try:
    from backend.database import DB_PATH
except Exception:  # pragma: no cover - 降级处理
    DB_PATH = "data/thesis_miner.db"

# 尝试导入日志（避免循环依赖）
try:
    from backend.utils.logger import get_logger

    _logger = get_logger(__name__)
except Exception:  # pragma: no cover - 降级到标准 logging
    import logging

    _logger = logging.getLogger(__name__)


# ===== 默认配置常量 =====

# 滑动窗口默认大小（秒）
DEFAULT_WINDOW_SECONDS = 300

# Histogram 默认桶边界（秒），覆盖 1ms ~ 10s
DEFAULT_HISTOGRAM_BUCKETS: Tuple[float, ...] = (
    0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5,
    1.0, 2.5, 5.0, 10.0,
)

# 默认百分位列表
DEFAULT_PERCENTILES: Tuple[float, ...] = (0.5, 0.9, 0.95, 0.99)

# 时序数据持久化采样间隔（秒）
DEFAULT_PERSIST_INTERVAL = 60

# 内存中保留的时序点数量上限
DEFAULT_TIMESERIES_CAPACITY = 1440  # 一分钟一个点，保留 24 小时

# 批量上报缓冲区大小
DEFAULT_BATCH_BUFFER_SIZE = 1024


def _now_ts() -> float:
    """获取当前 UTC 时间戳（秒）。"""
    return time.time()


def _iso_now() -> str:
    """获取当前 UTC 时间的 ISO8601 字符串。"""
    return datetime.now(tz=timezone.utc).isoformat()


def _labels_to_key(labels: Optional[Dict[str, str]]) -> str:
    """将标签字典转为稳定排序的字符串键，便于作为内部字典的 key。

    Args:
        labels: 标签字典。

    Returns:
        形如 "k1=v1,k2=v2" 的字符串；空标签返回空串。
    """
    if not labels:
        return ""
    items = sorted(labels.items())
    return ",".join(f"{k}={v}" for k, v in items)


def _escape_label_value(value: str) -> str:
    """转义 Prometheus 标签值中的特殊字符。"""
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _format_labels(labels: Optional[Dict[str, str]]) -> str:
    """格式化标签为 Prometheus 文本格式。

    Args:
        labels: 标签字典。

    Returns:
        形如 '{method="GET",path="/sessions"}' 的字符串；空标签返回空串。
    """
    if not labels:
        return ""
    items = sorted(labels.items())
    pairs = [f'{k}="{_escape_label_value(str(v))}"' for k, v in items]
    return "{" + ",".join(pairs) + "}"


def _quantile(sorted_values: List[float], q: float) -> float:
    """计算有序列表的分位数。

    使用线性插值法（与 numpy.percentile 默认一致）。

    Args:
        sorted_values: 已排序的数值列表。
        q: 分位数，取值 [0, 1]。

    Returns:
        分位数值；空列表返回 0.0。
    """
    if not sorted_values:
        return 0.0
    if q <= 0:
        return sorted_values[0]
    if q >= 1:
        return sorted_values[-1]
    n = len(sorted_values)
    pos = q * (n - 1)
    lower = int(math.floor(pos))
    upper = int(math.ceil(pos))
    if lower == upper:
        return sorted_values[lower]
    frac = pos - lower
    return sorted_values[lower] * (1 - frac) + sorted_values[upper] * frac


@dataclass
class MetricSample:
    """单个指标采样点。"""

    name: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=_now_ts)

    def to_dict(self) -> Dict[str, Any]:
        """转为字典。"""
        return {
            "name": self.name,
            "value": self.value,
            "labels": dict(self.labels),
            "timestamp": self.timestamp,
        }


@dataclass
class TimeSeriesPoint:
    """时序数据点。"""

    timestamp: float
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


class Counter:
    """单调递增计数器

    适用于记录累计请求数、错误数、处理字节数等只增不减的指标。
    支持 reset（仅用于测试或重启场景）。

    线程安全。
    """

    def __init__(
        self,
        name: str,
        description: str = "",
        label_names: Optional[Iterable[str]] = None,
    ):
        """初始化计数器。

        Args:
            name: 指标名称（建议以 _total 结尾）。
            description: 指标描述。
            label_names: 标签键名列表。
        """
        self.name = name
        self.description = description
        self.label_names: Tuple[str, ...] = tuple(label_names or ())
        self._values: Dict[str, float] = defaultdict(float)
        self._lock = threading.RLock()
        # 记录每个标签组合的创建时间，用于速率计算
        self._created_at: Dict[str, float] = {}

    def _validate_labels(self, labels: Optional[Dict[str, str]]) -> Dict[str, str]:
        """校验标签并返回规范化后的字典。"""
        labels = labels or {}
        if set(labels.keys()) != set(self.label_names):
            raise ValueError(
                f"标签键不匹配：期望 {self.label_names}，实际 {tuple(labels.keys())}"
            )
        return {k: str(v) for k, v in labels.items()}

    def inc(self, amount: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        """增加计数值。

        Args:
            amount: 增量，必须 >= 0。
            labels: 标签字典。
        """
        if amount < 0:
            raise ValueError("Counter 增量必须非负")
        norm_labels = self._validate_labels(labels)
        key = _labels_to_key(norm_labels)
        with self._lock:
            self._values[key] += amount
            if key not in self._created_at:
                self._created_at[key] = _now_ts()

    def get(self, labels: Optional[Dict[str, str]] = None) -> float:
        """获取指定标签组合的当前值。"""
        norm_labels = self._validate_labels(labels)
        key = _labels_to_key(norm_labels)
        with self._lock:
            return self._values.get(key, 0.0)

    def get_all(self) -> List[Tuple[Dict[str, str], float]]:
        """获取所有标签组合的值。"""
        with self._lock:
            results = []
            for key, value in self._values.items():
                labels = {}
                if key:
                    for pair in key.split(","):
                        k, _, v = pair.partition("=")
                        labels[k] = v
                results.append((labels, value))
            return results

    def reset(self) -> None:
        """重置计数器（仅用于测试）。"""
        with self._lock:
            self._values.clear()
            self._created_at.clear()

    def export_prometheus(self) -> List[str]:
        """导出为 Prometheus 文本格式行列表。"""
        lines: List[str] = []
        if self.description:
            lines.append(f"# HELP {self.name} {self.description}")
        lines.append(f"# TYPE {self.name} counter")
        with self._lock:
            for key, value in self._values.items():
                labels = {}
                if key:
                    for pair in key.split(","):
                        k, _, v = pair.partition("=")
                        labels[k] = v
                label_str = _format_labels(labels)
                lines.append(f"{self.name}{label_str} {value}")
        return lines

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典。"""
        with self._lock:
            return {
                "name": self.name,
                "type": "counter",
                "description": self.description,
                "label_names": list(self.label_names),
                "values": [
                    {"labels": labels, "value": value}
                    for labels, value in self.get_all()
                ],
            }


class Gauge:
    """可增可减的瞬时值

    适用于记录当前并发数、队列长度、温度等可上下波动的指标。

    线程安全。
    """

    def __init__(
        self,
        name: str,
        description: str = "",
        label_names: Optional[Iterable[str]] = None,
    ):
        """初始化 Gauge。"""
        self.name = name
        self.description = description
        self.label_names: Tuple[str, ...] = tuple(label_names or ())
        self._values: Dict[str, float] = defaultdict(float)
        self._lock = threading.RLock()

    def _validate_labels(self, labels: Optional[Dict[str, str]]) -> Dict[str, str]:
        """校验标签。"""
        labels = labels or {}
        if set(labels.keys()) != set(self.label_names):
            raise ValueError(
                f"标签键不匹配：期望 {self.label_names}，实际 {tuple(labels.keys())}"
            )
        return {k: str(v) for k, v in labels.items()}

    def set(self, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """设置当前值。"""
        norm_labels = self._validate_labels(labels)
        key = _labels_to_key(norm_labels)
        with self._lock:
            self._values[key] = float(value)

    def inc(self, amount: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        """增加值。"""
        norm_labels = self._validate_labels(labels)
        key = _labels_to_key(norm_labels)
        with self._lock:
            self._values[key] += amount

    def dec(self, amount: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        """减少值。"""
        self.inc(-amount, labels)

    def get(self, labels: Optional[Dict[str, str]] = None) -> float:
        """获取当前值。"""
        norm_labels = self._validate_labels(labels)
        key = _labels_to_key(norm_labels)
        with self._lock:
            return self._values.get(key, 0.0)

    def get_all(self) -> List[Tuple[Dict[str, str], float]]:
        """获取所有标签组合的值。"""
        with self._lock:
            results = []
            for key, value in self._values.items():
                labels = {}
                if key:
                    for pair in key.split(","):
                        k, _, v = pair.partition("=")
                        labels[k] = v
                results.append((labels, value))
            return results

    def reset(self) -> None:
        """重置（仅用于测试）。"""
        with self._lock:
            self._values.clear()

    def export_prometheus(self) -> List[str]:
        """导出为 Prometheus 文本格式。"""
        lines: List[str] = []
        if self.description:
            lines.append(f"# HELP {self.name} {self.description}")
        lines.append(f"# TYPE {self.name} gauge")
        with self._lock:
            for key, value in self._values.items():
                labels = {}
                if key:
                    for pair in key.split(","):
                        k, _, v = pair.partition("=")
                        labels[k] = v
                label_str = _format_labels(labels)
                lines.append(f"{self.name}{label_str} {value}")
        return lines

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典。"""
        with self._lock:
            return {
                "name": self.name,
                "type": "gauge",
                "description": self.description,
                "label_names": list(self.label_names),
                "values": [
                    {"labels": labels, "value": value}
                    for labels, value in self.get_all()
                ],
            }


class Histogram:
    """直方图指标

    记录观测值的分布，支持：
        - 桶计数（bucket counts）
        - 总和（sum）
        - 总数（count）
        - 滑动窗口内的百分位计算（p50/p90/p99）

    适用于记录请求延迟、响应大小等分布型指标。

    线程安全。
    """

    def __init__(
        self,
        name: str,
        description: str = "",
        buckets: Optional[Iterable[float]] = None,
        label_names: Optional[Iterable[str]] = None,
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
        max_samples: int = 1024,
    ):
        """初始化直方图。

        Args:
            name: 指标名称。
            description: 描述。
            buckets: 桶边界列表（升序）。
            label_names: 标签键名列表。
            window_seconds: 滑动窗口大小（秒）。
            max_samples: 每个标签组合在窗口内保留的最大样本数。
        """
        self.name = name
        self.description = description
        self.buckets: Tuple[float, ...] = tuple(sorted(buckets or DEFAULT_HISTOGRAM_BUCKETS))
        if not self.buckets:
            self.buckets = DEFAULT_HISTOGRAM_BUCKETS
        self.label_names: Tuple[str, ...] = tuple(label_names or ())
        self.window_seconds = window_seconds
        self.max_samples = max_samples

        # 每个标签组合的统计状态
        # _states[key] = {
        #     "buckets": [count_per_bucket],
        #     "sum": float,
        #     "count": int,
        #     "samples": deque[(timestamp, value)],
        # }
        self._states: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

    def _validate_labels(self, labels: Optional[Dict[str, str]]) -> Dict[str, str]:
        """校验标签。"""
        labels = labels or {}
        if set(labels.keys()) != set(self.label_names):
            raise ValueError(
                f"标签键不匹配：期望 {self.label_names}，实际 {tuple(labels.keys())}"
            )
        return {k: str(v) for k, v in labels.items()}

    def _get_or_create_state(self, key: str) -> Dict[str, Any]:
        """获取或创建指定标签组合的状态。"""
        if key not in self._states:
            self._states[key] = {
                "buckets": [0] * (len(self.buckets) + 1),  # 最后一桶为 +Inf
                "sum": 0.0,
                "count": 0,
                "samples": deque(maxlen=self.max_samples),
            }
        return self._states[key]

    def observe(self, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """记录一次观测值。

        Args:
            value: 观测值（必须 >= 0）。
            labels: 标签字典。
        """
        if value < 0:
            raise ValueError("Histogram 观测值必须非负")
        norm_labels = self._validate_labels(labels)
        key = _labels_to_key(norm_labels)
        now = _now_ts()
        with self._lock:
            state = self._get_or_create_state(key)
            # 更新桶计数
            idx = bisect.bisect_left(self.buckets, value)
            state["buckets"][idx] += 1
            # 更新总和与总数
            state["sum"] += value
            state["count"] += 1
            # 添加到滑动窗口样本
            state["samples"].append((now, value))

    def _prune_samples(self, samples: Deque[Tuple[float, float]], now: float) -> List[float]:
        """清理过期样本并返回当前窗口内的有效值列表。"""
        cutoff = now - self.window_seconds
        valid: List[float] = []
        while samples and samples[0][0] < cutoff:
            samples.popleft()
        for _, v in samples:
            valid.append(v)
        return valid

    def get_count(self, labels: Optional[Dict[str, str]] = None) -> int:
        """获取累计观测次数。"""
        norm_labels = self._validate_labels(labels)
        key = _labels_to_key(norm_labels)
        with self._lock:
            state = self._states.get(key)
            return state["count"] if state else 0

    def get_sum(self, labels: Optional[Dict[str, str]] = None) -> float:
        """获取累计观测总和。"""
        norm_labels = self._validate_labels(labels)
        key = _labels_to_key(norm_labels)
        with self._lock:
            state = self._states.get(key)
            return state["sum"] if state else 0.0

    def get_avg(self, labels: Optional[Dict[str, str]] = None) -> float:
        """获取平均值。"""
        count = self.get_count(labels)
        if count == 0:
            return 0.0
        return self.get_sum(labels) / count

    def get_percentile(
        self,
        q: float,
        labels: Optional[Dict[str, str]] = None,
        use_window: bool = True,
    ) -> float:
        """获取分位数。

        Args:
            q: 分位数 [0, 1]。
            labels: 标签。
            use_window: True 则基于滑动窗口样本计算，False 则基于桶估算。

        Returns:
            分位数值。
        """
        norm_labels = self._validate_labels(labels)
        key = _labels_to_key(norm_labels)
        with self._lock:
            state = self._states.get(key)
            if not state or state["count"] == 0:
                return 0.0
            if use_window:
                valid = self._prune_samples(state["samples"], _now_ts())
                if not valid:
                    return 0.0
                valid.sort()
                return _quantile(valid, q)
            # 基于桶估算
            target = q * state["count"]
            cumulative = 0
            for i, bucket_count in enumerate(state["buckets"]):
                cumulative += bucket_count
                if cumulative >= target:
                    if i < len(self.buckets):
                        return self.buckets[i]
                    # +Inf 桶，返回最后一个有限桶边界
                    return self.buckets[-1] if self.buckets else 0.0
            return self.buckets[-1] if self.buckets else 0.0

    def get_percentiles(
        self,
        qs: Iterable[float] = DEFAULT_PERCENTILES,
        labels: Optional[Dict[str, str]] = None,
        use_window: bool = True,
    ) -> Dict[str, float]:
        """批量获取分位数。"""
        return {f"p{int(q * 100)}": self.get_percentile(q, labels, use_window) for q in qs}

    def get_all_label_sets(self) -> List[Dict[str, str]]:
        """获取所有出现过的标签组合。"""
        with self._lock:
            results = []
            for key in self._states.keys():
                labels = {}
                if key:
                    for pair in key.split(","):
                        k, _, v = pair.partition("=")
                        labels[k] = v
                results.append(labels)
            return results

    def reset(self) -> None:
        """重置（仅用于测试）。"""
        with self._lock:
            self._states.clear()

    def export_prometheus(self) -> List[str]:
        """导出为 Prometheus 文本格式。"""
        lines: List[str] = []
        if self.description:
            lines.append(f"# HELP {self.name} {self.description}")
        lines.append(f"# TYPE {self.name} histogram")
        with self._lock:
            for key, state in self._states.items():
                labels = {}
                if key:
                    for pair in key.split(","):
                        k, _, v = pair.partition("=")
                        labels[k] = v
                # 输出每个桶
                cumulative = 0
                for i, bucket_count in enumerate(state["buckets"]):
                    cumulative += bucket_count
                    bucket_le = self.buckets[i] if i < len(self.buckets) else float("inf")
                    bucket_labels = dict(labels)
                    bucket_labels["le"] = (
                        str(bucket_le) if bucket_le != float("inf") else "+Inf"
                    )
                    lines.append(
                        f"{self.name}_bucket{_format_labels(bucket_labels)} {cumulative}"
                    )
                # 输出 sum 与 count
                lines.append(f"{self.name}_sum{_format_labels(labels)} {state['sum']}")
                lines.append(f"{self.name}_count{_format_labels(labels)} {state['count']}")
        return lines

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典。"""
        with self._lock:
            series = []
            for key, state in self._states.items():
                labels = {}
                if key:
                    for pair in key.split(","):
                        k, _, v = pair.partition("=")
                        labels[k] = v
                valid = self._prune_samples(state["samples"], _now_ts())
                valid_sorted = sorted(valid)
                percentiles = {
                    f"p{int(q * 100)}": _quantile(valid_sorted, q)
                    for q in DEFAULT_PERCENTILES
                }
                series.append(
                    {
                        "labels": labels,
                        "count": state["count"],
                        "sum": state["sum"],
                        "avg": state["sum"] / state["count"] if state["count"] else 0.0,
                        "buckets": [
                            {"le": le, "count": cnt}
                            for le, cnt in zip(
                                list(self.buckets) + ["+Inf"], state["buckets"]
                            )
                        ],
                        "percentiles": percentiles,
                    }
                )
            return {
                "name": self.name,
                "type": "histogram",
                "description": self.description,
                "label_names": list(self.label_names),
                "buckets": list(self.buckets),
                "series": series,
            }


class TimeSeriesStore:
    """时序数据存储

    在内存中维护每个指标的最近 N 个采样点，并提供 SQLite 持久化能力。
    用于绘制趋势图与历史回溯。
    """

    def __init__(self, capacity: int = DEFAULT_TIMESERIES_CAPACITY):
        """初始化时序存储。

        Args:
            capacity: 每个指标保留的最大采样点数。
        """
        self.capacity = capacity
        # _series[name][label_key] = deque[TimeSeriesPoint]
        self._series: Dict[str, Dict[str, Deque[TimeSeriesPoint]]] = defaultdict(
            lambda: defaultdict(lambda: deque(maxlen=capacity))
        )
        self._lock = threading.RLock()

    def record(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
        timestamp: Optional[float] = None,
    ) -> None:
        """记录一个采样点。"""
        ts = timestamp or _now_ts()
        key = _labels_to_key(labels or {})
        point = TimeSeriesPoint(timestamp=ts, value=value, labels=dict(labels or {}))
        with self._lock:
            self._series[name][key].append(point)

    def get_series(
        self,
        name: str,
        labels: Optional[Dict[str, str]] = None,
        start_ts: Optional[float] = None,
        end_ts: Optional[float] = None,
    ) -> List[TimeSeriesPoint]:
        """获取时序数据。"""
        key = _labels_to_key(labels or {})
        with self._lock:
            points = list(self._series.get(name, {}).get(key, []))
        if start_ts is not None:
            points = [p for p in points if p.timestamp >= start_ts]
        if end_ts is not None:
            points = [p for p in points if p.timestamp <= end_ts]
        return points

    def get_all_series_names(self) -> List[str]:
        """获取所有指标名。"""
        with self._lock:
            return list(self._series.keys())

    def clear(self, name: Optional[str] = None) -> None:
        """清空时序数据。"""
        with self._lock:
            if name is None:
                self._series.clear()
            else:
                self._series.pop(name, None)

    def to_dict(self, name: Optional[str] = None) -> Dict[str, Any]:
        """序列化为字典。"""
        result: Dict[str, Any] = {}
        with self._lock:
            names = [name] if name else list(self._series.keys())
            for n in names:
                label_map = self._series.get(n, {})
                result[n] = {
                    label_key: [
                        {"timestamp": p.timestamp, "value": p.value, "labels": p.labels}
                        for p in points
                    ]
                    for label_key, points in label_map.items()
                }
        return result


class MetricsCollector:
    """指标收集器（单例）

    统一管理所有 Counter / Gauge / Histogram 指标，提供：
        - 指标注册与获取
        - Prometheus 文本格式导出
        - JSON 序列化导出
        - 时序数据存储
        - 异步批量上报
        - SQLite 持久化

    使用示例：
        collector = MetricsCollector.get_instance()
        c = collector.counter("requests_total", "请求总数", ["method"])
        c.inc(labels={"method": "GET"})
        print(collector.export_prometheus())
    """

    _instance: Optional["MetricsCollector"] = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> "MetricsCollector":
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
        self._counters: Dict[str, Counter] = {}
        self._gauges: Dict[str, Gauge] = {}
        self._histograms: Dict[str, Histogram] = {}
        self._lock = threading.RLock()
        self._time_series = TimeSeriesStore()
        self._persist_enabled = False
        self._persist_task: Optional[asyncio.Task] = None
        self._batch_buffer: List[MetricSample] = []
        self._batch_lock = threading.Lock()
        self._batch_callbacks: List = []
        # 内置指标
        self._register_builtin_metrics()

    @classmethod
    def get_instance(cls) -> "MetricsCollector":
        """获取单例实例。"""
        return cls()

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例（仅用于测试）。"""
        with cls._instance_lock:
            cls._instance = None

    def _register_builtin_metrics(self) -> None:
        """注册内置指标。"""
        # 指标收集器自身运行指标
        self.counter(
            "metrics_collector_operations_total",
            "指标收集器操作总数",
            ["operation", "metric_type"],
        )
        self.gauge(
            "metrics_collector_registered_metrics",
            "已注册指标数量",
            ["metric_type"],
        )
        self.histogram(
            "metrics_collector_export_duration_seconds",
            "指标导出耗时",
        )

    def counter(
        self,
        name: str,
        description: str = "",
        label_names: Optional[Iterable[str]] = None,
    ) -> Counter:
        """注册或获取 Counter。"""
        with self._lock:
            if name in self._counters:
                return self._counters[name]
            if name in self._gauges or name in self._histograms:
                raise ValueError(f"指标名 {name} 已被其他类型占用")
            c = Counter(name, description, label_names)
            self._counters[name] = c
            self._update_registered_gauge()
            return c

    def gauge(
        self,
        name: str,
        description: str = "",
        label_names: Optional[Iterable[str]] = None,
    ) -> Gauge:
        """注册或获取 Gauge。"""
        with self._lock:
            if name in self._gauges:
                return self._gauges[name]
            if name in self._counters or name in self._histograms:
                raise ValueError(f"指标名 {name} 已被其他类型占用")
            g = Gauge(name, description, label_names)
            self._gauges[name] = g
            self._update_registered_gauge()
            return g

    def histogram(
        self,
        name: str,
        description: str = "",
        buckets: Optional[Iterable[float]] = None,
        label_names: Optional[Iterable[str]] = None,
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
        max_samples: int = 1024,
    ) -> Histogram:
        """注册或获取 Histogram。"""
        with self._lock:
            if name in self._histograms:
                return self._histograms[name]
            if name in self._counters or name in self._gauges:
                raise ValueError(f"指标名 {name} 已被其他类型占用")
            h = Histogram(
                name,
                description,
                buckets=buckets,
                label_names=label_names,
                window_seconds=window_seconds,
                max_samples=max_samples,
            )
            self._histograms[name] = h
            self._update_registered_gauge()
            return h

    def _update_registered_gauge(self) -> None:
        """更新已注册指标数量 Gauge。"""
        g = self._gauges.get("metrics_collector_registered_metrics")
        if g:
            g.set(len(self._counters), {"metric_type": "counter"})
            g.set(len(self._gauges), {"metric_type": "gauge"})
            g.set(len(self._histograms), {"metric_type": "histogram"})

    def get_counter(self, name: str) -> Optional[Counter]:
        """获取已注册的 Counter。"""
        return self._counters.get(name)

    def get_gauge(self, name: str) -> Optional[Gauge]:
        """获取已注册的 Gauge。"""
        return self._gauges.get(name)

    def get_histogram(self, name: str) -> Optional[Histogram]:
        """获取已注册的 Histogram。"""
        return self._histograms.get(name)

    def list_metric_names(self) -> Dict[str, List[str]]:
        """列出所有指标名。"""
        with self._lock:
            return {
                "counter": list(self._counters.keys()),
                "gauge": list(self._gauges.keys()),
                "histogram": list(self._histograms.keys()),
            }

    def remove_metric(self, name: str) -> bool:
        """移除指标。"""
        with self._lock:
            removed = False
            if name in self._counters:
                del self._counters[name]
                removed = True
            if name in self._gauges:
                del self._gauges[name]
                removed = True
            if name in self._histograms:
                del self._histograms[name]
                removed = True
            if removed:
                self._update_registered_gauge()
            return removed

    def clear_all(self) -> None:
        """清空所有指标（仅用于测试）。"""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._time_series.clear()
            self._batch_buffer.clear()
            self._register_builtin_metrics()

    def export_prometheus(self) -> str:
        """导出为 Prometheus 文本格式字符串。"""
        start = _now_ts()
        lines: List[str] = []
        with self._lock:
            for c in self._counters.values():
                lines.extend(c.export_prometheus())
            for g in self._gauges.values():
                lines.extend(g.export_prometheus())
            for h in self._histograms.values():
                lines.extend(h.export_prometheus())
        # 记录导出耗时
        duration = _now_ts() - start
        export_h = self._histograms.get("metrics_collector_export_duration_seconds")
        if export_h:
            export_h.observe(duration)
        return "\n".join(lines) + ("\n" if lines else "")

    def export_json(self, indent: Optional[int] = None) -> str:
        """导出为 JSON 字符串。"""
        with self._lock:
            data = {
                "timestamp": _iso_now(),
                "counters": [c.to_dict() for c in self._counters.values()],
                "gauges": [g.to_dict() for g in self._gauges.values()],
                "histograms": [h.to_dict() for h in self._histograms.values()],
            }
        return json.dumps(data, ensure_ascii=False, default=str, indent=indent)

    def export_dict(self) -> Dict[str, Any]:
        """导出为字典。"""
        with self._lock:
            return {
                "timestamp": _iso_now(),
                "counters": [c.to_dict() for c in self._counters.values()],
                "gauges": [g.to_dict() for g in self._gauges.values()],
                "histograms": [h.to_dict() for h in self._histograms.values()],
            }

    def snapshot(self) -> Dict[str, Any]:
        """生成快照（与 export_dict 等价，语义上强调瞬时状态）。"""
        return self.export_dict()

    # ===== 时序数据相关 =====

    def record_timeseries(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """记录时序数据点。"""
        self._time_series.record(name, value, labels)

    def get_timeseries(
        self,
        name: str,
        labels: Optional[Dict[str, str]] = None,
        start_ts: Optional[float] = None,
        end_ts: Optional[float] = None,
    ) -> List[TimeSeriesPoint]:
        """获取时序数据。"""
        return self._time_series.get_series(name, labels, start_ts, end_ts)

    def snapshot_all_to_timeseries(self) -> None:
        """将所有 Gauge 与 Histogram 的当前值写入时序存储。

        适用于定时采样任务。
        """
        with self._lock:
            for g in self._gauges.values():
                for labels, value in g.get_all():
                    self._time_series.record(g.name, value, labels)
            for h in self._histograms.values():
                for labels in h.get_all_label_sets():
                    avg = h.get_avg(labels)
                    self._time_series.record(f"{h.name}_avg", avg, labels)
                    p99 = h.get_percentile(0.99, labels)
                    self._time_series.record(f"{h.name}_p99", p99, labels)

    # ===== 批量上报 =====

    def add_batch_callback(self, callback) -> None:
        """注册批量上报回调函数。

        回调函数签名：callback(samples: List[MetricSample]) -> None
        """
        self._batch_callbacks.append(callback)

    def record_sample(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """记录一个采样点到批量缓冲区。"""
        sample = MetricSample(name=name, value=value, labels=dict(labels or {}))
        with self._batch_lock:
            self._batch_buffer.append(sample)
            if len(self._batch_buffer) >= DEFAULT_BATCH_BUFFER_SIZE:
                self._flush_batch_locked()

    def flush_batch(self) -> int:
        """刷新批量缓冲区，触发回调。"""
        with self._batch_lock:
            return self._flush_batch_locked()

    def _flush_batch_locked(self) -> int:
        """实际执行批量刷新（调用方需持有锁）。"""
        if not self._batch_buffer:
            return 0
        samples = list(self._batch_buffer)
        self._batch_buffer.clear()
        for callback in self._batch_callbacks:
            try:
                callback(samples)
            except Exception as e:
                _logger.error(f"批量上报回调执行失败: {e}", exc_info=True)
        return len(samples)

    # ===== SQLite 持久化 =====

    def _ensure_persist_table(self, conn: sqlite3.Connection) -> None:
        """确保持久化表存在。"""
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS metrics_timeseries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                value REAL NOT NULL,
                labels TEXT,
                timestamp REAL NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_metrics_ts_name ON metrics_timeseries(name, timestamp)"
        )

    def persist_to_db(self, db_path: Optional[str] = None) -> int:
        """将当前时序数据持久化到 SQLite。

        Args:
            db_path: 数据库路径，默认使用项目 DB_PATH。

        Returns:
            写入的记录数。
        """
        path = db_path or DB_PATH
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        data = self._time_series.to_dict()
        total = 0
        try:
            conn = sqlite3.connect(path)
            try:
                self._ensure_persist_table(conn)
                for name, label_map in data.items():
                    for label_key, points in label_map.items():
                        for p in points:
                            conn.execute(
                                "INSERT INTO metrics_timeseries (name, value, labels, timestamp) VALUES (?, ?, ?, ?)",
                                (
                                    name,
                                    p["value"],
                                    json.dumps(p["labels"], ensure_ascii=False),
                                    p["timestamp"],
                                ),
                            )
                            total += 1
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            _logger.error(f"指标持久化失败: {e}", exc_info=True)
        return total

    def load_from_db(
        self,
        db_path: Optional[str] = None,
        name: Optional[str] = None,
        limit: int = 10000,
    ) -> int:
        """从 SQLite 加载历史时序数据。

        Args:
            db_path: 数据库路径。
            name: 指标名过滤，None 则加载全部。
            limit: 最大加载条数。

        Returns:
            加载的记录数。
        """
        path = db_path or DB_PATH
        if not Path(path).exists():
            return 0
        total = 0
        try:
            conn = sqlite3.connect(path)
            try:
                if name:
                    cursor = conn.execute(
                        "SELECT name, value, labels, timestamp FROM metrics_timeseries WHERE name = ? ORDER BY timestamp DESC LIMIT ?",
                        (name, limit),
                    )
                else:
                    cursor = conn.execute(
                        "SELECT name, value, labels, timestamp FROM metrics_timeseries ORDER BY timestamp DESC LIMIT ?",
                        (limit,),
                    )
                for row in cursor:
                    n, v, labels_json, ts = row
                    try:
                        labels = json.loads(labels_json) if labels_json else {}
                    except json.JSONDecodeError:
                        labels = {}
                    self._time_series.record(n, v, labels, ts)
                    total += 1
            finally:
                conn.close()
        except Exception as e:
            _logger.error(f"指标加载失败: {e}", exc_info=True)
        return total

    # ===== 异步任务 =====

    async def start_persist_task(self, interval: float = DEFAULT_PERSIST_INTERVAL) -> None:
        """启动异步定时持久化任务。"""
        if self._persist_enabled:
            return
        self._persist_enabled = True

        async def _run():
            while self._persist_enabled:
                try:
                    self.snapshot_all_to_timeseries()
                    self.persist_to_db()
                except Exception as e:
                    _logger.error(f"定时持久化任务异常: {e}", exc_info=True)
                await asyncio.sleep(interval)

        self._persist_task = asyncio.create_task(_run())
        _logger.info(f"指标定时持久化任务已启动，间隔 {interval} 秒")

    async def stop_persist_task(self) -> None:
        """停止异步定时持久化任务。"""
        self._persist_enabled = False
        if self._persist_task and not self._persist_task.done():
            self._persist_task.cancel()
            try:
                await self._persist_task
            except asyncio.CancelledError:
                pass
        self._persist_task = None

    # ===== 便捷统计方法 =====

    def get_metric_summary(self, name: str) -> Optional[Dict[str, Any]]:
        """获取单个指标的摘要信息。"""
        if name in self._counters:
            return self._counters[name].to_dict()
        if name in self._gauges:
            return self._gauges[name].to_dict()
        if name in self._histograms:
            return self._histograms[name].to_dict()
        return None

    def get_all_summaries(self) -> Dict[str, Any]:
        """获取所有指标的摘要。"""
        return self.export_dict()

    def measure_latency(self, name: str, labels: Optional[Dict[str, str]] = None):
        """延迟测量上下文管理器。

        使用示例：
            with collector.measure_latency("api_latency", {"path": "/sessions"}):
                do_something()
        """
        label_names = tuple(labels.keys()) if labels else None
        histogram = self.histogram(name, f"{name} 延迟分布", label_names=label_names)

        class _LatencyContext:
            def __init__(self, hist: Histogram, lbls: Optional[Dict[str, str]]):
                self._hist = hist
                self._labels = lbls
                self._start = 0.0

            def __enter__(self):
                self._start = _now_ts()
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                duration = _now_ts() - self._start
                self._hist.observe(duration, self._labels)
                return False

        return _LatencyContext(histogram, labels)


# ===== 模块级便捷函数 =====


def get_metrics_collector() -> MetricsCollector:
    """获取全局指标收集器单例。"""
    return MetricsCollector.get_instance()


def record_api_request(
    method: str,
    path: str,
    status: int,
    duration: float,
    collector: Optional[MetricsCollector] = None,
) -> None:
    """记录一次 API 请求的便捷函数。

    Args:
        method: HTTP 方法。
        path: 请求路径。
        status: 响应状态码。
        duration: 耗时（秒）。
        collector: 可选，指定收集器。
    """
    c = collector or get_metrics_collector()
    # 请求总数
    counter = c.counter(
        "http_requests_total",
        "HTTP 请求总数",
        ["method", "path", "status"],
    )
    counter.inc(labels={"method": method, "path": path, "status": str(status)})
    # 延迟
    hist = c.histogram(
        "http_request_duration_seconds",
        "HTTP 请求延迟",
        label_names=["method", "path"],
    )
    hist.observe(duration, labels={"method": method, "path": path})


def record_llm_call(
    provider: str,
    model: str,
    stage: str,
    duration: float,
    success: bool,
    collector: Optional[MetricsCollector] = None,
) -> None:
    """记录一次 LLM 调用的便捷函数。

    Args:
        provider: 提供商（如 deepseek）。
        model: 模型名。
        stage: 调用阶段。
        duration: 耗时（秒）。
        success: 是否成功。
        collector: 可选，指定收集器。
    """
    c = collector or get_metrics_collector()
    counter = c.counter(
        "llm_calls_total",
        "LLM 调用总数",
        ["provider", "model", "stage", "result"],
    )
    counter.inc(
        labels={
            "provider": provider,
            "model": model,
            "stage": stage,
            "result": "success" if success else "failure",
        }
    )
    hist = c.histogram(
        "llm_call_duration_seconds",
        "LLM 调用延迟",
        label_names=["provider", "model", "stage"],
    )
    hist.observe(duration, labels={"provider": provider, "model": model, "stage": stage})


def record_cache_event(
    cache_type: str,
    hit: bool,
    collector: Optional[MetricsCollector] = None,
) -> None:
    """记录一次缓存事件的便捷函数。"""
    c = collector or get_metrics_collector()
    counter = c.counter(
        "cache_events_total",
        "缓存事件总数",
        ["cache_type", "result"],
    )
    counter.inc(
        labels={"cache_type": cache_type, "result": "hit" if hit else "miss"}
    )


def update_concurrent_gauge(
    metric_name: str,
    value: float,
    labels: Optional[Dict[str, str]] = None,
    collector: Optional[MetricsCollector] = None,
) -> None:
    """更新并发数 Gauge 的便捷函数。"""
    c = collector or get_metrics_collector()
    g = c.gauge(metric_name, f"{metric_name} 当前并发数")
    g.set(value, labels)


# ===== 单元测试可运行逻辑 =====


def _run_self_test() -> None:
    """模块自检：构造指标、记录样本、导出并校验。

    可直接 `python -m backend.analytics.metrics_collector` 运行。
    """
    MetricsCollector.reset_instance()
    c = MetricsCollector.get_instance()

    # 测试 Counter
    req_counter = c.counter(
        "test_requests_total",
        "测试请求总数",
        ["method", "status"],
    )
    for _ in range(100):
        req_counter.inc(labels={"method": "GET", "status": "200"})
    for _ in range(5):
        req_counter.inc(labels={"method": "GET", "status": "500"})
    assert req_counter.get(labels={"method": "GET", "status": "200"}) == 100
    assert req_counter.get(labels={"method": "GET", "status": "500"}) == 5

    # 测试 Gauge
    queue_gauge = c.gauge("test_queue_size", "测试队列大小", ["queue"])
    queue_gauge.set(10, labels={"queue": "default"})
    queue_gauge.inc(5, labels={"queue": "default"})
    queue_gauge.dec(3, labels={"queue": "default"})
    assert queue_gauge.get(labels={"queue": "default"}) == 12

    # 测试 Histogram
    latency_hist = c.histogram(
        "test_latency_seconds",
        "测试延迟",
        buckets=[0.01, 0.1, 1.0, 10.0],
        label_names=["endpoint"],
    )
    import random

    for _ in range(1000):
        v = random.expovariate(5)  # 指数分布模拟延迟
        latency_hist.observe(v, labels={"endpoint": "/api"})

    p50 = latency_hist.get_percentile(0.5, labels={"endpoint": "/api"})
    p99 = latency_hist.get_percentile(0.99, labels={"endpoint": "/api"})
    assert 0 < p50 < p99, f"p50={p50} 应小于 p99={p99}"
    assert latency_hist.get_count(labels={"endpoint": "/api"}) == 1000

    # 测试导出
    prom_text = c.export_prometheus()
    assert "test_requests_total" in prom_text
    assert "test_queue_size" in prom_text
    assert "test_latency_seconds_bucket" in prom_text

    json_text = c.export_json()
    parsed = json.loads(json_text)
    assert "counters" in parsed
    assert "gauges" in parsed
    assert "histograms" in parsed

    # 测试时序存储
    c.snapshot_all_to_timeseries()
    ts_points = c.get_timeseries("test_queue_size", labels={"queue": "default"})
    assert len(ts_points) >= 1

    # 测试批量上报
    received: List[MetricSample] = []
    c.add_batch_callback(received.extend)
    for i in range(10):
        c.record_sample("test_batch_metric", float(i))
    flushed = c.flush_batch()
    assert flushed == 10
    assert len(received) == 10

    # 测试延迟测量上下文
    with c.measure_latency("test_context_latency"):
        time.sleep(0.01)
    h = c.get_histogram("test_context_latency")
    assert h is not None
    assert h.get_count() == 1

    print("MetricsCollector 自检通过")
    print(f"已注册指标: {c.list_metric_names()}")
    print(f"Prometheus 导出前 5 行:")
    for line in prom_text.split("\n")[:5]:
        print(f"  {line}")


if __name__ == "__main__":
    _run_self_test()
