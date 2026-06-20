"""性能监控器模块

提供系统级与进程级的性能监控能力，包括：
    - CPU 使用率（系统级与进程级）
    - 内存使用（物理内存、虚拟内存、进程 RSS）
    - 磁盘 I/O 与空间
    - 网络流量
    - 进程级资源占用（线程数、文件描述符数）
    - 性能基线与异常检测
    - 告警阈值管理
    - 性能报告生成与趋势分析

依赖 psutil（可选）：若未安装则降级为占位实现，仅返回零值。
所有监控数据可写入时序存储，便于历史回溯与可视化。

典型用法：
    monitor = PerformanceMonitor.get_instance()
    monitor.start_sampling(interval=5.0)
    snapshot = monitor.snapshot()
    report = monitor.generate_report()
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple

# 尝试导入 psutil（可选依赖）
try:
    import psutil  # type: ignore

    _HAS_PSUTIL = True
except ImportError:  # pragma: no cover - 降级处理
    psutil = None  # type: ignore
    _HAS_PSUTIL = False

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

# 默认采样间隔（秒）
DEFAULT_SAMPLE_INTERVAL = 5.0

# 内存中保留的采样点数（按 5s 间隔约保留 24 小时）
DEFAULT_HISTORY_CAPACITY = 17280

# CPU 异常阈值（百分比）
DEFAULT_CPU_WARNING_THRESHOLD = 70.0
DEFAULT_CPU_CRITICAL_THRESHOLD = 90.0

# 内存异常阈值（百分比）
DEFAULT_MEM_WARNING_THRESHOLD = 75.0
DEFAULT_MEM_CRITICAL_THRESHOLD = 90.0

# 磁盘空间异常阈值（百分比）
DEFAULT_DISK_WARNING_THRESHOLD = 80.0
DEFAULT_DISK_CRITICAL_THRESHOLD = 95.0

# 异常持续多久才触发告警（秒）
DEFAULT_ALERT_SUSTAIN_SECONDS = 30.0

# 基线计算所需的最少样本数
DEFAULT_BASELINE_MIN_SAMPLES = 50

# 基线计算窗口（最近 N 个样本）
DEFAULT_BASELINE_WINDOW = 1000


def _now_ts() -> float:
    """获取当前 UTC 时间戳。"""
    return time.time()


def _iso_now() -> str:
    """获取当前 UTC 时间的 ISO8601 字符串。"""
    return datetime.now(tz=timezone.utc).isoformat()


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


@dataclass
class CpuSnapshot:
    """CPU 快照。"""

    system_percent: float = 0.0  # 系统整体 CPU 使用率
    process_percent: float = 0.0  # 当前进程 CPU 使用率
    load_avg_1m: float = 0.0  # 1 分钟负载（仅类 Unix）
    load_avg_5m: float = 0.0  # 5 分钟负载
    load_avg_15m: float = 0.0  # 15 分钟负载
    core_count: int = 0  # CPU 核心数
    timestamp: float = field(default_factory=_now_ts)


@dataclass
class MemorySnapshot:
    """内存快照。"""

    total_bytes: int = 0  # 物理内存总量
    available_bytes: int = 0  # 可用物理内存
    used_bytes: int = 0  # 已用物理内存
    used_percent: float = 0.0  # 使用率
    swap_total_bytes: int = 0  # 交换分区总量
    swap_used_bytes: int = 0  # 交换分区已用
    swap_used_percent: float = 0.0
    process_rss: int = 0  # 进程 RSS
    process_vms: int = 0  # 进程虚拟内存
    process_percent: float = 0.0  # 进程内存占比
    timestamp: float = field(default_factory=_now_ts)


@dataclass
class DiskSnapshot:
    """磁盘快照。"""

    # 磁盘空间
    total_bytes: int = 0
    used_bytes: int = 0
    free_bytes: int = 0
    used_percent: float = 0.0
    # 磁盘 I/O 计数
    read_count: int = 0
    write_count: int = 0
    read_bytes: int = 0
    write_bytes: int = 0
    # I/O 速率（字节/秒，需两次采样计算）
    read_bytes_per_sec: float = 0.0
    write_bytes_per_sec: float = 0.0
    timestamp: float = field(default_factory=_now_ts)


@dataclass
class NetworkSnapshot:
    """网络快照。"""

    bytes_sent: int = 0  # 累计发送字节数
    bytes_recv: int = 0  # 累计接收字节数
    packets_sent: int = 0
    packets_recv: int = 0
    # 速率（字节/秒）
    bytes_sent_per_sec: float = 0.0
    bytes_recv_per_sec: float = 0.0
    timestamp: float = field(default_factory=_now_ts)


@dataclass
class ProcessSnapshot:
    """进程级快照。"""

    pid: int = 0
    name: str = ""
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    rss: int = 0
    vms: int = 0
    thread_count: int = 0
    fd_count: int = 0  # 文件描述符数（类 Unix）
    create_time: float = 0.0
    cmdline: str = ""
    timestamp: float = field(default_factory=_now_ts)


@dataclass
class PerformanceSnapshot:
    """综合性能快照。"""

    cpu: CpuSnapshot = field(default_factory=CpuSnapshot)
    memory: MemorySnapshot = field(default_factory=MemorySnapshot)
    disk: DiskSnapshot = field(default_factory=DiskSnapshot)
    network: NetworkSnapshot = field(default_factory=NetworkSnapshot)
    process: ProcessSnapshot = field(default_factory=ProcessSnapshot)
    timestamp: float = field(default_factory=_now_ts)

    def to_dict(self) -> Dict[str, Any]:
        """转为字典。"""
        return {
            "timestamp": self.timestamp,
            "iso_timestamp": datetime.fromtimestamp(
                self.timestamp, tz=timezone.utc
            ).isoformat(),
            "cpu": self.cpu.__dict__,
            "memory": self.memory.__dict__,
            "disk": self.disk.__dict__,
            "network": self.network.__dict__,
            "process": self.process.__dict__,
        }


@dataclass
class AlertRule:
    """告警规则。"""

    name: str
    metric_path: str  # 形如 "cpu.system_percent"
    warning_threshold: float
    critical_threshold: float
    sustain_seconds: float = DEFAULT_ALERT_SUSTAIN_SECONDS
    comparison: str = ">"  # ">" 或 "<"
    enabled: bool = True
    description: str = ""


@dataclass
class AlertEvent:
    """告警事件。"""

    rule_name: str
    level: str  # "warning" / "critical" / "recovered"
    metric_path: str
    value: float
    threshold: float
    message: str
    timestamp: float = field(default_factory=_now_ts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_name": self.rule_name,
            "level": self.level,
            "metric_path": self.metric_path,
            "value": self.value,
            "threshold": self.threshold,
            "message": self.message,
            "timestamp": self.timestamp,
            "iso_timestamp": datetime.fromtimestamp(
                self.timestamp, tz=timezone.utc
            ).isoformat(),
        }


class AlertManager:
    """告警管理器

    管理告警规则、检测异常、生成告警事件、去重与抑制。
    """

    def __init__(self):
        self._rules: Dict[str, AlertRule] = {}
        self._sustained: Dict[str, float] = {}  # rule_name -> 持续开始时间
        self._active_alerts: Dict[str, AlertEvent] = {}  # rule_name -> 当前告警
        self._history: Deque[AlertEvent] = deque(maxlen=1000)
        self._callbacks: List = []
        self._lock = threading.RLock()

    def add_rule(self, rule: AlertRule) -> None:
        """添加告警规则。"""
        with self._lock:
            self._rules[rule.name] = rule

    def remove_rule(self, name: str) -> bool:
        """移除告警规则。"""
        with self._lock:
            return self._rules.pop(name, None) is not None

    def get_rules(self) -> List[AlertRule]:
        """获取所有规则。"""
        with self._lock:
            return list(self._rules.values())

    def add_callback(self, callback) -> None:
        """注册告警回调。"""
        self._callbacks.append(callback)

    def _get_metric_value(self, snapshot: PerformanceSnapshot, path: str) -> Optional[float]:
        """从快照中按路径获取指标值。

        Args:
            snapshot: 性能快照。
            path: 形如 "cpu.system_percent" 的路径。

        Returns:
            指标值；路径无效返回 None。
        """
        parts = path.split(".")
        obj: Any = snapshot
        for part in parts:
            if hasattr(obj, part):
                obj = getattr(obj, part)
            else:
                return None
        if isinstance(obj, (int, float)):
            return float(obj)
        return None

    def evaluate(self, snapshot: PerformanceSnapshot) -> List[AlertEvent]:
        """评估快照，返回新触发的告警事件列表。"""
        new_events: List[AlertEvent] = []
        now = snapshot.timestamp
        with self._lock:
            for rule in self._rules.values():
                if not rule.enabled:
                    continue
                value = self._get_metric_value(snapshot, rule.metric_path)
                if value is None:
                    continue
                # 判断是否超阈值
                exceeded_level = None
                threshold = 0.0
                if rule.comparison == ">":
                    if value >= rule.critical_threshold:
                        exceeded_level = "critical"
                        threshold = rule.critical_threshold
                    elif value >= rule.warning_threshold:
                        exceeded_level = "warning"
                        threshold = rule.warning_threshold
                elif rule.comparison == "<":
                    if value <= rule.critical_threshold:
                        exceeded_level = "critical"
                        threshold = rule.critical_threshold
                    elif value <= rule.warning_threshold:
                        exceeded_level = "warning"
                        threshold = rule.warning_threshold

                if exceeded_level:
                    # 检查持续时间
                    if rule.name not in self._sustained:
                        self._sustained[rule.name] = now
                    sustain_start = self._sustained[rule.name]
                    if now - sustain_start >= rule.sustain_seconds:
                        # 检查是否已存在同级别告警
                        existing = self._active_alerts.get(rule.name)
                        if not existing or existing.level != exceeded_level:
                            event = AlertEvent(
                                rule_name=rule.name,
                                level=exceeded_level,
                                metric_path=rule.metric_path,
                                value=value,
                                threshold=threshold,
                                message=(
                                    f"{rule.name}: {rule.metric_path}={value:.2f} "
                                    f"超过 {exceeded_level} 阈值 {threshold:.2f}"
                                ),
                                timestamp=now,
                            )
                            new_events.append(event)
                            self._active_alerts[rule.name] = event
                            self._history.append(event)
                else:
                    # 恢复正常
                    if rule.name in self._active_alerts:
                        recovered = AlertEvent(
                            rule_name=rule.name,
                            level="recovered",
                            metric_path=rule.metric_path,
                            value=value,
                            threshold=0.0,
                            message=f"{rule.name}: {rule.metric_path} 已恢复正常",
                            timestamp=now,
                        )
                        new_events.append(recovered)
                        self._history.append(recovered)
                        del self._active_alerts[rule.name]
                    self._sustained.pop(rule.name, None)
        # 触发回调
        for event in new_events:
            for callback in self._callbacks:
                try:
                    callback(event)
                except Exception as e:
                    _logger.error(f"告警回调执行失败: {e}", exc_info=True)
        return new_events

    def get_active_alerts(self) -> List[AlertEvent]:
        """获取当前活跃告警。"""
        with self._lock:
            return list(self._active_alerts.values())

    def get_history(self, limit: int = 100) -> List[AlertEvent]:
        """获取告警历史。"""
        with self._lock:
            return list(self._history)[-limit:]

    def clear(self) -> None:
        """清空所有告警状态。"""
        with self._lock:
            self._sustained.clear()
            self._active_alerts.clear()
            self._history.clear()


class PerformanceBaseline:
    """性能基线

    基于历史样本计算指标的正常范围（均值 ± N 倍标准差），
    用于异常检测。
    """

    def __init__(self, window: int = DEFAULT_BASELINE_WINDOW):
        """初始化基线。

        Args:
            window: 计算窗口（最近 N 个样本）。
        """
        self.window = window
        self._samples: Dict[str, Deque[float]] = defaultdict(
            lambda: deque(maxlen=window)
        )
        self._lock = threading.RLock()

    def update(self, metric_path: str, value: float) -> None:
        """更新基线样本。"""
        with self._lock:
            self._samples[metric_path].append(value)

    def get_stats(self, metric_path: str) -> Optional[Tuple[float, float, float, float]]:
        """获取基线统计。

        Returns:
            (mean, std, lower, upper) 元组；样本不足返回 None。
        """
        with self._lock:
            samples = list(self._samples.get(metric_path, []))
        if len(samples) < DEFAULT_BASELINE_MIN_SAMPLES:
            return None
        n = len(samples)
        mean = sum(samples) / n
        variance = sum((x - mean) ** 2 for x in samples) / n
        std = variance ** 0.5
        # 3-sigma 区间
        lower = mean - 3 * std
        upper = mean + 3 * std
        return mean, std, lower, upper

    def is_anomaly(self, metric_path: str, value: float) -> bool:
        """判断是否为异常值。"""
        stats = self.get_stats(metric_path)
        if stats is None:
            return False
        _, _, lower, upper = stats
        return value < lower or value > upper

    def get_all_baselines(self) -> Dict[str, Dict[str, float]]:
        """获取所有指标的基线。"""
        result: Dict[str, Dict[str, float]] = {}
        with self._lock:
            for path in self._samples.keys():
                stats = self.get_stats(path)
                if stats:
                    mean, std, lower, upper = stats
                    result[path] = {
                        "mean": mean,
                        "std": std,
                        "lower": lower,
                        "upper": upper,
                        "sample_count": len(self._samples[path]),
                    }
        return result

    def clear(self) -> None:
        """清空基线。"""
        with self._lock:
            self._samples.clear()


class PerformanceMonitor:
    """性能监控器（单例）

    整合 CPU/内存/磁盘/网络/进程监控，提供：
        - 定时异步采样
        - 历史数据存储
        - 性能基线与异常检测
        - 告警管理
        - 报告生成
        - 趋势分析
        - SQLite 持久化
    """

    _instance: Optional["PerformanceMonitor"] = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> "PerformanceMonitor":
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
        self._history: Deque[PerformanceSnapshot] = deque(maxlen=DEFAULT_HISTORY_CAPACITY)
        self._lock = threading.RLock()
        self._sampling = False
        self._sample_task: Optional[asyncio.Task] = None
        self._sample_interval = DEFAULT_SAMPLE_INTERVAL
        # 上一次的 I/O 与网络计数，用于计算速率
        self._last_disk_io: Optional[Tuple[float, int, int]] = None
        self._last_net_io: Optional[Tuple[float, int, int]] = None
        # 子组件
        self.alert_manager = AlertManager()
        self.baseline = PerformanceBaseline()
        # 注册默认告警规则
        self._register_default_alerts()
        # 进程对象缓存
        self._process: Any = None
        if _HAS_PSUTIL:
            try:
                self._process = psutil.Process()
            except Exception:  # pragma: no cover
                self._process = None

    @classmethod
    def get_instance(cls) -> "PerformanceMonitor":
        """获取单例实例。"""
        return cls()

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例（仅用于测试）。"""
        with cls._instance_lock:
            cls._instance = None

    def _register_default_alerts(self) -> None:
        """注册默认告警规则。"""
        defaults = [
            AlertRule(
                name="high_cpu",
                metric_path="cpu.system_percent",
                warning_threshold=DEFAULT_CPU_WARNING_THRESHOLD,
                critical_threshold=DEFAULT_CPU_CRITICAL_THRESHOLD,
                description="系统 CPU 使用率过高",
            ),
            AlertRule(
                name="high_memory",
                metric_path="memory.used_percent",
                warning_threshold=DEFAULT_MEM_WARNING_THRESHOLD,
                critical_threshold=DEFAULT_MEM_CRITICAL_THRESHOLD,
                description="物理内存使用率过高",
            ),
            AlertRule(
                name="high_disk",
                metric_path="disk.used_percent",
                warning_threshold=DEFAULT_DISK_WARNING_THRESHOLD,
                critical_threshold=DEFAULT_DISK_CRITICAL_THRESHOLD,
                description="磁盘空间不足",
            ),
            AlertRule(
                name="process_high_cpu",
                metric_path="process.cpu_percent",
                warning_threshold=80.0,
                critical_threshold=95.0,
                description="进程 CPU 使用率过高",
            ),
            AlertRule(
                name="process_high_memory",
                metric_path="process.memory_percent",
                warning_threshold=50.0,
                critical_threshold=70.0,
                description="进程内存占用过高",
            ),
        ]
        for rule in defaults:
            self.alert_manager.add_rule(rule)

    # ===== 采样方法 =====

    def _sample_cpu(self) -> CpuSnapshot:
        """采样 CPU。"""
        snap = CpuSnapshot()
        if not _HAS_PSUTIL:
            return snap
        try:
            snap.system_percent = _safe_float(psutil.cpu_percent(interval=None))
            snap.core_count = psutil.cpu_count(logical=True) or 0
            if self._process:
                snap.process_percent = _safe_float(self._process.cpu_percent(interval=None))
            # 负载均值（仅类 Unix）
            try:
                load1, load5, load15 = os.getloadavg()
                snap.load_avg_1m = float(load1)
                snap.load_avg_5m = float(load5)
                snap.load_avg_15m = float(load15)
            except (AttributeError, OSError):
                pass
        except Exception as e:
            _logger.debug(f"CPU 采样失败: {e}")
        return snap

    def _sample_memory(self) -> MemorySnapshot:
        """采样内存。"""
        snap = MemorySnapshot()
        if not _HAS_PSUTIL:
            return snap
        try:
            vm = psutil.virtual_memory()
            snap.total_bytes = int(vm.total)
            snap.available_bytes = int(vm.available)
            snap.used_bytes = int(vm.used)
            snap.used_percent = _safe_float(vm.percent)
            swap = psutil.swap_memory()
            snap.swap_total_bytes = int(swap.total)
            snap.swap_used_bytes = int(swap.used)
            snap.swap_used_percent = _safe_float(swap.percent)
            if self._process:
                mem_info = self._process.memory_info()
                snap.process_rss = int(getattr(mem_info, "rss", 0))
                snap.process_vms = int(getattr(mem_info, "vms", 0))
                snap.process_percent = _safe_float(self._process.memory_percent())
        except Exception as e:
            _logger.debug(f"内存采样失败: {e}")
        return snap

    def _sample_disk(self) -> DiskSnapshot:
        """采样磁盘。"""
        snap = DiskSnapshot()
        if not _HAS_PSUTIL:
            return snap
        try:
            # 磁盘空间（监控数据目录所在分区）
            disk_path = str(Path(DB_PATH).resolve().parent) if DB_PATH else "/"
            usage = psutil.disk_usage(disk_path)
            snap.total_bytes = int(usage.total)
            snap.used_bytes = int(usage.used)
            snap.free_bytes = int(usage.free)
            snap.used_percent = _safe_float(usage.percent)
            # 磁盘 I/O
            io = psutil.disk_io_counters()
            if io:
                snap.read_count = int(getattr(io, "read_count", 0))
                snap.write_count = int(getattr(io, "write_count", 0))
                snap.read_bytes = int(getattr(io, "read_bytes", 0))
                snap.write_bytes = int(getattr(io, "write_bytes", 0))
                now = _now_ts()
                if self._last_disk_io is not None:
                    last_ts, last_read, last_write = self._last_disk_io
                    elapsed = now - last_ts
                    if elapsed > 0:
                        snap.read_bytes_per_sec = (snap.read_bytes - last_read) / elapsed
                        snap.write_bytes_per_sec = (snap.write_bytes - last_write) / elapsed
                self._last_disk_io = (now, snap.read_bytes, snap.write_bytes)
        except Exception as e:
            _logger.debug(f"磁盘采样失败: {e}")
        return snap

    def _sample_network(self) -> NetworkSnapshot:
        """采样网络。"""
        snap = NetworkSnapshot()
        if not _HAS_PSUTIL:
            return snap
        try:
            io = psutil.net_io_counters()
            if io:
                snap.bytes_sent = int(getattr(io, "bytes_sent", 0))
                snap.bytes_recv = int(getattr(io, "bytes_recv", 0))
                snap.packets_sent = int(getattr(io, "packets_sent", 0))
                snap.packets_recv = int(getattr(io, "packets_recv", 0))
                now = _now_ts()
                if self._last_net_io is not None:
                    last_ts, last_sent, last_recv = self._last_net_io
                    elapsed = now - last_ts
                    if elapsed > 0:
                        snap.bytes_sent_per_sec = (snap.bytes_sent - last_sent) / elapsed
                        snap.bytes_recv_per_sec = (snap.bytes_recv - last_recv) / elapsed
                self._last_net_io = (now, snap.bytes_sent, snap.bytes_recv)
        except Exception as e:
            _logger.debug(f"网络采样失败: {e}")
        return snap

    def _sample_process(self) -> ProcessSnapshot:
        """采样进程。"""
        snap = ProcessSnapshot()
        if not _HAS_PSUTIL or not self._process:
            snap.pid = os.getpid()
            return snap
        try:
            snap.pid = self._process.pid
            snap.name = self._process.name() or ""
            snap.cpu_percent = _safe_float(self._process.cpu_percent(interval=None))
            snap.memory_percent = _safe_float(self._process.memory_percent())
            mem_info = self._process.memory_info()
            snap.rss = int(getattr(mem_info, "rss", 0))
            snap.vms = int(getattr(mem_info, "vms", 0))
            try:
                snap.thread_count = self._process.num_threads()
            except Exception:
                snap.thread_count = 0
            try:
                snap.fd_count = self._process.num_fds()  # 类 Unix
            except (AttributeError, Exception):
                try:
                    snap.fd_count = self._process.num_handles()  # Windows
                except Exception:
                    snap.fd_count = 0
            snap.create_time = _safe_float(self._process.create_time())
            try:
                cmdline = self._process.cmdline()
                snap.cmdline = " ".join(cmdline) if cmdline else ""
            except Exception:
                snap.cmdline = ""
        except Exception as e:
            _logger.debug(f"进程采样失败: {e}")
        return snap

    def snapshot(self) -> PerformanceSnapshot:
        """采集一次综合快照。"""
        snap = PerformanceSnapshot(
            cpu=self._sample_cpu(),
            memory=self._sample_memory(),
            disk=self._sample_disk(),
            network=self._sample_network(),
            process=self._sample_process(),
        )
        # 存入历史
        with self._lock:
            self._history.append(snap)
        # 更新基线
        self._update_baseline(snap)
        # 评估告警
        self.alert_manager.evaluate(snap)
        return snap

    def _update_baseline(self, snap: PerformanceSnapshot) -> None:
        """更新性能基线。"""
        self.baseline.update("cpu.system_percent", snap.cpu.system_percent)
        self.baseline.update("cpu.process_percent", snap.cpu.process_percent)
        self.baseline.update("memory.used_percent", snap.memory.used_percent)
        self.baseline.update("memory.process_percent", snap.memory.process_percent)
        self.baseline.update("disk.used_percent", snap.disk.used_percent)
        self.baseline.update("disk.read_bytes_per_sec", snap.disk.read_bytes_per_sec)
        self.baseline.update("disk.write_bytes_per_sec", snap.disk.write_bytes_per_sec)
        self.baseline.update("network.bytes_sent_per_sec", snap.network.bytes_sent_per_sec)
        self.baseline.update("network.bytes_recv_per_sec", snap.network.bytes_recv_per_sec)
        self.baseline.update("process.cpu_percent", snap.process.cpu_percent)
        self.baseline.update("process.memory_percent", snap.process.memory_percent)

    # ===== 历史数据访问 =====

    def get_history(
        self,
        limit: int = 100,
        start_ts: Optional[float] = None,
        end_ts: Optional[float] = None,
    ) -> List[PerformanceSnapshot]:
        """获取历史快照。"""
        with self._lock:
            snaps = list(self._history)
        if start_ts is not None:
            snaps = [s for s in snaps if s.timestamp >= start_ts]
        if end_ts is not None:
            snaps = [s for s in snaps if s.timestamp <= end_ts]
        if limit > 0:
            snaps = snaps[-limit:]
        return snaps

    def get_latest(self) -> Optional[PerformanceSnapshot]:
        """获取最近一次快照。"""
        with self._lock:
            return self._history[-1] if self._history else None

    def clear_history(self) -> None:
        """清空历史。"""
        with self._lock:
            self._history.clear()

    # ===== 异步采样 =====

    async def start_sampling(self, interval: float = DEFAULT_SAMPLE_INTERVAL) -> None:
        """启动异步定时采样。"""
        if self._sampling:
            return
        self._sampling = True
        self._sample_interval = interval

        async def _run():
            while self._sampling:
                try:
                    self.snapshot()
                except Exception as e:
                    _logger.error(f"性能采样异常: {e}", exc_info=True)
                await asyncio.sleep(interval)

        self._sample_task = asyncio.create_task(_run())
        _logger.info(f"性能采样已启动，间隔 {interval} 秒")

    async def stop_sampling(self) -> None:
        """停止异步采样。"""
        self._sampling = False
        if self._sample_task and not self._sample_task.done():
            self._sample_task.cancel()
            try:
                await self._sample_task
            except asyncio.CancelledError:
                pass
        self._sample_task = None

    def is_sampling(self) -> bool:
        """是否正在采样。"""
        return self._sampling

    # ===== 报告生成 =====

    def generate_report(
        self,
        window_seconds: Optional[float] = None,
    ) -> Dict[str, Any]:
        """生成性能报告。

        Args:
            window_seconds: 报告时间窗口（秒），None 则覆盖全部历史。

        Returns:
            报告字典。
        """
        now = _now_ts()
        start_ts = (now - window_seconds) if window_seconds else None
        snaps = self.get_history(start_ts=start_ts)
        if not snaps:
            return {
                "generated_at": _iso_now(),
                "window_seconds": window_seconds,
                "sample_count": 0,
                "message": "无历史数据",
            }

        # 计算统计
        cpu_system = [s.cpu.system_percent for s in snaps]
        cpu_process = [s.cpu.process_percent for s in snaps]
        mem_used = [s.memory.used_percent for s in snaps]
        mem_process = [s.memory.process_percent for s in snaps]
        disk_used = [s.disk.used_percent for s in snaps]
        disk_read_rate = [s.disk.read_bytes_per_sec for s in snaps]
        disk_write_rate = [s.disk.write_bytes_per_sec for s in snaps]
        net_sent_rate = [s.network.bytes_sent_per_sec for s in snaps]
        net_recv_rate = [s.network.bytes_recv_per_sec for s in snaps]

        latest = snaps[-1]
        report = {
            "generated_at": _iso_now(),
            "window_seconds": window_seconds,
            "sample_count": len(snaps),
            "period_start": datetime.fromtimestamp(
                snaps[0].timestamp, tz=timezone.utc
            ).isoformat(),
            "period_end": datetime.fromtimestamp(
                snaps[-1].timestamp, tz=timezone.utc
            ).isoformat(),
            "latest": latest.to_dict(),
            "summary": {
                "cpu": self._summarize_series(cpu_system),
                "cpu_process": self._summarize_series(cpu_process),
                "memory": self._summarize_series(mem_used),
                "memory_process": self._summarize_series(mem_process),
                "disk": self._summarize_series(disk_used),
                "disk_read_rate": self._summarize_series(disk_read_rate),
                "disk_write_rate": self._summarize_series(disk_write_rate),
                "network_sent_rate": self._summarize_series(net_sent_rate),
                "network_recv_rate": self._summarize_series(net_recv_rate),
            },
            "alerts": {
                "active": [a.to_dict() for a in self.alert_manager.get_active_alerts()],
                "recent": [a.to_dict() for a in self.alert_manager.get_history(limit=20)],
            },
            "baselines": self.baseline.get_all_baselines(),
            "bottlenecks": self._identify_bottlenecks(snaps),
        }
        return report

    def _summarize_series(self, values: List[float]) -> Dict[str, float]:
        """计算序列统计摘要。"""
        if not values:
            return {"min": 0, "max": 0, "avg": 0, "p50": 0, "p90": 0, "p99": 0}
        sorted_vals = sorted(values)
        n = len(sorted_vals)

        def _q(q_val: float) -> float:
            pos = q_val * (n - 1)
            lower = int(pos)
            upper = min(lower + 1, n - 1)
            frac = pos - lower
            return sorted_vals[lower] * (1 - frac) + sorted_vals[upper] * frac

        return {
            "min": sorted_vals[0],
            "max": sorted_vals[-1],
            "avg": sum(values) / n,
            "p50": _q(0.5),
            "p90": _q(0.9),
            "p99": _q(0.99),
        }

    def _identify_bottlenecks(self, snaps: List[PerformanceSnapshot]) -> List[Dict[str, Any]]:
        """识别性能瓶颈。"""
        bottlenecks: List[Dict[str, Any]] = []
        if not snaps:
            return bottlenecks
        latest = snaps[-1]
        # CPU 瓶颈
        if latest.cpu.system_percent > DEFAULT_CPU_WARNING_THRESHOLD:
            bottlenecks.append(
                {
                    "type": "cpu",
                    "severity": "critical"
                    if latest.cpu.system_percent > DEFAULT_CPU_CRITICAL_THRESHOLD
                    else "warning",
                    "value": latest.cpu.system_percent,
                    "threshold": DEFAULT_CPU_WARNING_THRESHOLD,
                    "message": f"CPU 使用率 {latest.cpu.system_percent:.1f}% 过高",
                }
            )
        # 内存瓶颈
        if latest.memory.used_percent > DEFAULT_MEM_WARNING_THRESHOLD:
            bottlenecks.append(
                {
                    "type": "memory",
                    "severity": "critical"
                    if latest.memory.used_percent > DEFAULT_MEM_CRITICAL_THRESHOLD
                    else "warning",
                    "value": latest.memory.used_percent,
                    "threshold": DEFAULT_MEM_WARNING_THRESHOLD,
                    "message": f"内存使用率 {latest.memory.used_percent:.1f}% 过高",
                }
            )
        # 磁盘空间瓶颈
        if latest.disk.used_percent > DEFAULT_DISK_WARNING_THRESHOLD:
            bottlenecks.append(
                {
                    "type": "disk_space",
                    "severity": "critical"
                    if latest.disk.used_percent > DEFAULT_DISK_CRITICAL_THRESHOLD
                    else "warning",
                    "value": latest.disk.used_percent,
                    "threshold": DEFAULT_DISK_WARNING_THRESHOLD,
                    "message": f"磁盘使用率 {latest.disk.used_percent:.1f}% 过高",
                }
            )
        # 进程内存瓶颈
        if latest.process.memory_percent > 50.0:
            bottlenecks.append(
                {
                    "type": "process_memory",
                    "severity": "warning",
                    "value": latest.process.memory_percent,
                    "threshold": 50.0,
                    "message": f"进程内存占用 {latest.process.memory_percent:.1f}% 过高",
                }
            )
        # 异常检测
        for path, value in [
            ("cpu.system_percent", latest.cpu.system_percent),
            ("memory.used_percent", latest.memory.used_percent),
            ("disk.used_percent", latest.disk.used_percent),
        ]:
            if self.baseline.is_anomaly(path, value):
                stats = self.baseline.get_stats(path)
                if stats:
                    mean, std, lower, upper = stats
                    bottlenecks.append(
                        {
                            "type": "anomaly",
                            "severity": "warning",
                            "metric": path,
                            "value": value,
                            "baseline_mean": mean,
                            "baseline_upper": upper,
                            "message": f"{path}={value:.2f} 偏离基线（均值 {mean:.2f}，上限 {upper:.2f}）",
                        }
                    )
        return bottlenecks

    def generate_text_report(self, window_seconds: Optional[float] = None) -> str:
        """生成文本格式报告。"""
        report = self.generate_report(window_seconds=window_seconds)
        lines: List[str] = []
        lines.append("=" * 60)
        lines.append("ThesisMiner 性能报告")
        lines.append(f"生成时间: {report.get('generated_at', '')}")
        lines.append(f"样本数: {report.get('sample_count', 0)}")
        lines.append("=" * 60)
        latest = report.get("latest", {})
        if latest:
            cpu = latest.get("cpu", {})
            mem = latest.get("memory", {})
            disk = latest.get("disk", {})
            net = latest.get("network", {})
            proc = latest.get("process", {})
            lines.append("")
            lines.append("[当前状态]")
            lines.append(
                f"  CPU: 系统 {cpu.get('system_percent', 0):.1f}% | "
                f"进程 {cpu.get('process_percent', 0):.1f}% | "
                f"核心数 {cpu.get('core_count', 0)}"
            )
            lines.append(
                f"  内存: {mem.get('used_percent', 0):.1f}% | "
                f"可用 {mem.get('available_bytes', 0) / 1024 / 1024:.1f} MB | "
                f"进程 RSS {mem.get('process_rss', 0) / 1024 / 1024:.1f} MB"
            )
            lines.append(
                f"  磁盘: {disk.get('used_percent', 0):.1f}% | "
                f"读 {disk.get('read_bytes_per_sec', 0) / 1024:.1f} KB/s | "
                f"写 {disk.get('write_bytes_per_sec', 0) / 1024:.1f} KB/s"
            )
            lines.append(
                f"  网络: 发送 {net.get('bytes_sent_per_sec', 0) / 1024:.1f} KB/s | "
                f"接收 {net.get('bytes_recv_per_sec', 0) / 1024:.1f} KB/s"
            )
            lines.append(
                f"  进程: PID {proc.get('pid', 0)} | "
                f"线程 {proc.get('thread_count', 0)} | "
                f"FD {proc.get('fd_count', 0)}"
            )
        summary = report.get("summary", {})
        if summary:
            lines.append("")
            lines.append("[统计摘要]")
            for key, stats in summary.items():
                lines.append(
                    f"  {key}: avg={stats.get('avg', 0):.2f} "
                    f"p50={stats.get('p50', 0):.2f} "
                    f"p90={stats.get('p90', 0):.2f} "
                    f"p99={stats.get('p99', 0):.2f} "
                    f"max={stats.get('max', 0):.2f}"
                )
        bottlenecks = report.get("bottlenecks", [])
        if bottlenecks:
            lines.append("")
            lines.append("[瓶颈识别]")
            for b in bottlenecks:
                lines.append(
                    f"  [{b.get('severity', '').upper()}] {b.get('message', '')}"
                )
        alerts = report.get("alerts", {})
        active = alerts.get("active", [])
        if active:
            lines.append("")
            lines.append("[活跃告警]")
            for a in active:
                lines.append(
                    f"  [{a.get('level', '').upper()}] {a.get('message', '')}"
                )
        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)

    # ===== 趋势分析 =====

    def analyze_trend(
        self,
        metric_path: str,
        window_seconds: Optional[float] = None,
    ) -> Dict[str, Any]:
        """分析指标趋势。

        Args:
            metric_path: 指标路径（如 "cpu.system_percent"）。
            window_seconds: 时间窗口。

        Returns:
            趋势分析结果。
        """
        now = _now_ts()
        start_ts = (now - window_seconds) if window_seconds else None
        snaps = self.get_history(start_ts=start_ts)
        values: List[Tuple[float, float]] = []
        for s in snaps:
            v = self._get_metric_by_path(s, metric_path)
            if v is not None:
                values.append((s.timestamp, v))
        if len(values) < 2:
            return {
                "metric": metric_path,
                "sample_count": len(values),
                "trend": "unknown",
                "message": "样本不足",
            }
        # 简单线性回归计算斜率
        n = len(values)
        x_mean = sum(t for t, _ in values) / n
        y_mean = sum(v for _, v in values) / n
        numerator = sum((t - x_mean) * (v - y_mean) for t, v in values)
        denominator = sum((t - x_mean) ** 2 for t, _ in values)
        slope = numerator / denominator if denominator != 0 else 0.0
        # 判断趋势
        if abs(slope) < 1e-6:
            trend = "stable"
        elif slope > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        # 计算变化率
        first_val = values[0][1]
        last_val = values[-1][1]
        change_rate = ((last_val - first_val) / first_val * 100) if first_val != 0 else 0.0
        return {
            "metric": metric_path,
            "sample_count": n,
            "trend": trend,
            "slope": slope,
            "change_rate_percent": change_rate,
            "first_value": first_val,
            "last_value": last_val,
            "mean": y_mean,
            "min": min(v for _, v in values),
            "max": max(v for _, v in values),
        }

    def _get_metric_by_path(
        self, snap: PerformanceSnapshot, path: str
    ) -> Optional[float]:
        """从快照中按路径获取指标值。"""
        parts = path.split(".")
        obj: Any = snap
        for part in parts:
            if hasattr(obj, part):
                obj = getattr(obj, part)
            else:
                return None
        if isinstance(obj, (int, float)):
            return float(obj)
        return None

    # ===== 可视化数据准备 =====

    def prepare_chart_data(
        self,
        metric_paths: List[str],
        window_seconds: Optional[float] = None,
        max_points: int = 200,
    ) -> Dict[str, Any]:
        """准备图表数据。

        Args:
            metric_paths: 指标路径列表。
            window_seconds: 时间窗口。
            max_points: 最大数据点数（超出则降采样）。

        Returns:
            图表数据字典。
        """
        now = _now_ts()
        start_ts = (now - window_seconds) if window_seconds else None
        snaps = self.get_history(start_ts=start_ts)
        # 降采样
        if len(snaps) > max_points:
            step = len(snaps) / max_points
            indices = [int(i * step) for i in range(max_points)]
            snaps = [snaps[i] for i in indices]
        series: Dict[str, List[List[float]]] = {}
        for path in metric_paths:
            points: List[List[float]] = []
            for s in snaps:
                v = self._get_metric_by_path(s, path)
                if v is not None:
                    points.append([s.timestamp * 1000, v])  # ms 时间戳
            series[path] = points
        return {
            "generated_at": _iso_now(),
            "series": series,
            "point_count": len(snaps),
        }

    # ===== SQLite 持久化 =====

    def _ensure_table(self, conn: sqlite3.Connection) -> None:
        """确保持久化表存在。"""
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS performance_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                cpu_system REAL,
                cpu_process REAL,
                mem_used_percent REAL,
                mem_process_percent REAL,
                mem_process_rss INTEGER,
                disk_used_percent REAL,
                disk_read_rate REAL,
                disk_write_rate REAL,
                net_sent_rate REAL,
                net_recv_rate REAL,
                process_cpu REAL,
                process_memory REAL,
                thread_count INTEGER,
                snapshot_json TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_perf_ts ON performance_snapshots(timestamp)"
        )

    def persist_to_db(self, db_path: Optional[str] = None) -> int:
        """将历史快照持久化到 SQLite。"""
        path = db_path or DB_PATH
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        snaps = self.get_history(limit=0)
        if not snaps:
            return 0
        total = 0
        try:
            conn = sqlite3.connect(path)
            try:
                self._ensure_table(conn)
                for s in snaps:
                    conn.execute(
                        """
                        INSERT INTO performance_snapshots
                        (timestamp, cpu_system, cpu_process, mem_used_percent,
                         mem_process_percent, mem_process_rss, disk_used_percent,
                         disk_read_rate, disk_write_rate, net_sent_rate, net_recv_rate,
                         process_cpu, process_memory, thread_count, snapshot_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            s.timestamp,
                            s.cpu.system_percent,
                            s.cpu.process_percent,
                            s.memory.used_percent,
                            s.memory.process_percent,
                            s.memory.process_rss,
                            s.disk.used_percent,
                            s.disk.read_bytes_per_sec,
                            s.disk.write_bytes_per_sec,
                            s.network.bytes_sent_per_sec,
                            s.network.bytes_recv_per_sec,
                            s.process.cpu_percent,
                            s.process.memory_percent,
                            s.process.thread_count,
                            json.dumps(s.to_dict(), ensure_ascii=False, default=str),
                        ),
                    )
                    total += 1
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            _logger.error(f"性能快照持久化失败: {e}", exc_info=True)
        return total

    def load_from_db(
        self,
        db_path: Optional[str] = None,
        limit: int = 1000,
    ) -> int:
        """从 SQLite 加载历史快照。"""
        path = db_path or DB_PATH
        if not Path(path).exists():
            return 0
        total = 0
        try:
            conn = sqlite3.connect(path)
            try:
                cursor = conn.execute(
                    "SELECT snapshot_json FROM performance_snapshots ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                )
                for row in cursor:
                    try:
                        data = json.loads(row[0])
                        snap = self._dict_to_snapshot(data)
                        with self._lock:
                            self._history.append(snap)
                        total += 1
                    except (json.JSONDecodeError, KeyError) as e:
                        _logger.debug(f"快照反序列化失败: {e}")
            finally:
                conn.close()
        except Exception as e:
            _logger.error(f"性能快照加载失败: {e}", exc_info=True)
        return total

    def _dict_to_snapshot(self, data: Dict[str, Any]) -> PerformanceSnapshot:
        """从字典重建快照。"""
        snap = PerformanceSnapshot()
        cpu_data = data.get("cpu", {})
        snap.cpu = CpuSnapshot(
            system_percent=_safe_float(cpu_data.get("system_percent")),
            process_percent=_safe_float(cpu_data.get("process_percent")),
            load_avg_1m=_safe_float(cpu_data.get("load_avg_1m")),
            load_avg_5m=_safe_float(cpu_data.get("load_avg_5m")),
            load_avg_15m=_safe_float(cpu_data.get("load_avg_15m")),
            core_count=_safe_int(cpu_data.get("core_count")),
            timestamp=_safe_float(data.get("timestamp")),
        )
        mem_data = data.get("memory", {})
        snap.memory = MemorySnapshot(
            total_bytes=_safe_int(mem_data.get("total_bytes")),
            available_bytes=_safe_int(mem_data.get("available_bytes")),
            used_bytes=_safe_int(mem_data.get("used_bytes")),
            used_percent=_safe_float(mem_data.get("used_percent")),
            swap_total_bytes=_safe_int(mem_data.get("swap_total_bytes")),
            swap_used_bytes=_safe_int(mem_data.get("swap_used_bytes")),
            swap_used_percent=_safe_float(mem_data.get("swap_used_percent")),
            process_rss=_safe_int(mem_data.get("process_rss")),
            process_vms=_safe_int(mem_data.get("process_vms")),
            process_percent=_safe_float(mem_data.get("process_percent")),
        )
        disk_data = data.get("disk", {})
        snap.disk = DiskSnapshot(
            total_bytes=_safe_int(disk_data.get("total_bytes")),
            used_bytes=_safe_int(disk_data.get("used_bytes")),
            free_bytes=_safe_int(disk_data.get("free_bytes")),
            used_percent=_safe_float(disk_data.get("used_percent")),
            read_count=_safe_int(disk_data.get("read_count")),
            write_count=_safe_int(disk_data.get("write_count")),
            read_bytes=_safe_int(disk_data.get("read_bytes")),
            write_bytes=_safe_int(disk_data.get("write_bytes")),
            read_bytes_per_sec=_safe_float(disk_data.get("read_bytes_per_sec")),
            write_bytes_per_sec=_safe_float(disk_data.get("write_bytes_per_sec")),
        )
        net_data = data.get("network", {})
        snap.network = NetworkSnapshot(
            bytes_sent=_safe_int(net_data.get("bytes_sent")),
            bytes_recv=_safe_int(net_data.get("bytes_recv")),
            packets_sent=_safe_int(net_data.get("packets_sent")),
            packets_recv=_safe_int(net_data.get("packets_recv")),
            bytes_sent_per_sec=_safe_float(net_data.get("bytes_sent_per_sec")),
            bytes_recv_per_sec=_safe_float(net_data.get("bytes_recv_per_sec")),
        )
        proc_data = data.get("process", {})
        snap.process = ProcessSnapshot(
            pid=_safe_int(proc_data.get("pid")),
            name=str(proc_data.get("name", "")),
            cpu_percent=_safe_float(proc_data.get("cpu_percent")),
            memory_percent=_safe_float(proc_data.get("memory_percent")),
            rss=_safe_int(proc_data.get("rss")),
            vms=_safe_int(proc_data.get("vms")),
            thread_count=_safe_int(proc_data.get("thread_count")),
            fd_count=_safe_int(proc_data.get("fd_count")),
            create_time=_safe_float(proc_data.get("create_time")),
            cmdline=str(proc_data.get("cmdline", "")),
        )
        snap.timestamp = _safe_float(data.get("timestamp"))
        return snap

    # ===== 资源清理 =====

    def shutdown(self) -> None:
        """关闭监控器，清理资源。"""
        if self._sampling:
            self._sampling = False
        if self._sample_task and not self._sample_task.done():
            self._sample_task.cancel()
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._sample_task)
            except Exception:
                pass
        self._sample_task = None
        self._process = None
        _logger.info("性能监控器已关闭")

    def export_json(self, indent: Optional[int] = None) -> str:
        """导出为 JSON 字符串。"""
        report = self.generate_report()
        return json.dumps(report, ensure_ascii=False, default=str, indent=indent)


# ===== 模块级便捷函数 =====


def get_performance_monitor() -> PerformanceMonitor:
    """获取全局性能监控器单例。"""
    return PerformanceMonitor.get_instance()


def quick_snapshot() -> Dict[str, Any]:
    """快速采集一次性能快照并返回字典。"""
    monitor = get_performance_monitor()
    snap = monitor.snapshot()
    return snap.to_dict()


def check_health() -> Dict[str, Any]:
    """健康检查：返回当前性能状态摘要。"""
    monitor = get_performance_monitor()
    latest = monitor.get_latest()
    if latest is None:
        snap = monitor.snapshot()
    else:
        snap = latest
    bottlenecks = monitor._identify_bottlenecks([snap])
    active_alerts = monitor.alert_manager.get_active_alerts()
    healthy = len(bottlenecks) == 0 and len(active_alerts) == 0
    return {
        "healthy": healthy,
        "timestamp": _iso_now(),
        "cpu_percent": snap.cpu.system_percent,
        "memory_percent": snap.memory.used_percent,
        "disk_percent": snap.disk.used_percent,
        "bottlenecks": bottlenecks,
        "active_alerts": [a.to_dict() for a in active_alerts],
    }


# ===== 单元测试可运行逻辑 =====


def _run_self_test() -> None:
    """模块自检。

    可直接 `python -m backend.analytics.performance_monitor` 运行。
    """
    PerformanceMonitor.reset_instance()
    monitor = PerformanceMonitor.get_instance()

    # 采集若干样本
    print("采集 5 个性能样本...")
    for _ in range(5):
        monitor.snapshot()
        time.sleep(0.5)

    # 验证历史
    history = monitor.get_history(limit=10)
    assert len(history) >= 5, f"历史样本数应为 5，实际 {len(history)}"

    # 验证最新快照
    latest = monitor.get_latest()
    assert latest is not None
    print(
        f"最新快照: CPU={latest.cpu.system_percent:.1f}% "
        f"MEM={latest.memory.used_percent:.1f}% "
        f"DISK={latest.disk.used_percent:.1f}%"
    )

    # 验证报告生成
    report = monitor.generate_report(window_seconds=60)
    assert report["sample_count"] >= 5
    assert "summary" in report
    assert "bottlenecks" in report
    print(f"报告生成成功，样本数 {report['sample_count']}")

    # 验证文本报告
    text_report = monitor.generate_text_report(window_seconds=60)
    assert "ThesisMiner 性能报告" in text_report
    print("文本报告生成成功")

    # 验证趋势分析
    trend = monitor.analyze_trend("cpu.system_percent", window_seconds=60)
    assert "trend" in trend
    print(f"CPU 趋势: {trend['trend']}")

    # 验证图表数据
    chart_data = monitor.prepare_chart_data(
        ["cpu.system_percent", "memory.used_percent"],
        window_seconds=60,
    )
    assert "series" in chart_data
    print(f"图表数据准备成功，包含 {len(chart_data['series'])} 个序列")

    # 验证告警管理
    rules = monitor.alert_manager.get_rules()
    assert len(rules) > 0
    print(f"已注册 {len(rules)} 条告警规则")

    # 验证健康检查
    health = check_health()
    assert "healthy" in health
    print(f"健康检查: healthy={health['healthy']}")

    # 验证基线（样本不足时应返回 None）
    baseline_stats = monitor.baseline.get_stats("cpu.system_percent")
    if baseline_stats is None:
        print("基线样本不足（预期，因样本数 < 50）")
    else:
        print(f"基线: mean={baseline_stats[0]:.2f}")

    # 验证 JSON 导出
    json_text = monitor.export_json()
    assert "summary" in json_text
    print("JSON 导出成功")

    monitor.shutdown()
    print("PerformanceMonitor 自检通过")


if __name__ == "__main__":
    _run_self_test()
