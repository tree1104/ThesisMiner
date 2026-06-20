"""ThesisMiner 分析与监控模块

提供指标收集、性能监控、用量追踪三大能力，用于支撑系统的可观测性。

子模块：
    - metrics_collector: 指标收集器（Counter/Gauge/Histogram，Prometheus 导出）
    - performance_monitor: 性能监控器（CPU/内存/磁盘/网络，告警与基线）
    - usage_tracker: 用量追踪器（Token/API 调用/成本/预算控制）

设计原则：
    1. 线程安全：所有共享状态均使用锁保护，可在多线程环境使用
    2. 零侵入：模块可独立运行，不强制依赖外部存储
    3. 可降级：psutil 等可选依赖缺失时自动降级为占位实现
"""
from backend.analytics.metrics_collector import (
    Counter,
    Gauge,
    Histogram,
    MetricsCollector,
    get_metrics_collector,
)
from backend.analytics.performance_monitor import (
    PerformanceMonitor,
    get_performance_monitor,
)
from backend.analytics.usage_tracker import (
    UsageTracker,
    get_usage_tracker,
)

__all__ = [
    # 指标收集
    "Counter",
    "Gauge",
    "Histogram",
    "MetricsCollector",
    "get_metrics_collector",
    # 性能监控
    "PerformanceMonitor",
    "get_performance_monitor",
    # 用量追踪
    "UsageTracker",
    "get_usage_tracker",
]
