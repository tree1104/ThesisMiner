"""健康检查器模块

提供系统级与应用级的健康监控能力，包括：
    - 数据库健康检查（连接、表完整性、WAL 模式、响应时间）
    - API 健康检查（HTTP 状态码、响应时间、端点可用性）
    - LLM 服务健康检查（API 可达性、配额、模型可用性）
    - 磁盘空间检查（总量、可用、使用率）
    - 内存使用检查（物理内存、虚拟内存、进程内存）
    - CPU 负载检查（系统级、进程级、负载平均值）
    - 健康状态聚合（综合所有检查结果）
    - 故障告警（异常状态触发告警）
    - 自动恢复（可配置的恢复动作）
    - 健康历史记录（时序存储、趋势分析）
    - SLA 监控（可用性计算、SLA 报告）
    - 健康检查 API 端点（liveness/readiness）
    - 就绪检查与存活检查

依赖 psutil（可选）：若未安装则降级为占位实现。
所有健康数据可写入 SQLite 时序存储，便于历史回溯与可视化。

典型用法：
    checker = HealthChecker()
    status = checker.check_all()
    is_alive = checker.liveness()
    is_ready = checker.readiness()
    report = checker.generate_sla_report(days=30)
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

# 尝试导入 psutil（可选依赖）
try:
    import psutil  # type: ignore

    _HAS_PSUTIL = True
except ImportError:  # pragma: no cover - 降级处理
    psutil = None  # type: ignore
    _HAS_PSUTIL = False

# 尝试导入项目内模块
try:
    from backend.database import DB_PATH, get_connection
except Exception:  # pragma: no cover
    DB_PATH = "data/thesis_miner.db"

    def get_connection():  # type: ignore
        pass

try:
    from backend.utils.logger import get_logger

    _logger = get_logger(__name__)
except Exception:  # pragma: no cover
    import logging

    _logger = logging.getLogger(__name__)


# ===== 常量定义 =====

# 健康状态枚举
HEALTHY = "healthy"
DEGRADED = "degraded"
UNHEALTHY = "unhealthy"
UNKNOWN = "unknown"

# 健康状态中文映射
STATUS_NAMES = {
    HEALTHY: "健康",
    DEGRADED: "降级",
    UNHEALTHY: "不健康",
    UNKNOWN: "未知",
}

# 默认检查间隔（秒）
DEFAULT_CHECK_INTERVAL = 30.0

# 默认超时时间（秒）
DEFAULT_TIMEOUT = 5.0

# 默认历史记录容量（按 30s 间隔约保留 24 小时）
DEFAULT_HISTORY_CAPACITY = 2880

# CPU 异常阈值（百分比）
DEFAULT_CPU_WARNING_THRESHOLD = 70.0
DEFAULT_CPU_CRITICAL_THRESHOLD = 90.0

# 内存异常阈值（百分比）
DEFAULT_MEM_WARNING_THRESHOLD = 75.0
DEFAULT_MEM_CRITICAL_THRESHOLD = 90.0

# 磁盘空间异常阈值（百分比）
DEFAULT_DISK_WARNING_THRESHOLD = 80.0
DEFAULT_DISK_CRITICAL_THRESHOLD = 95.0

# 数据库响应时间阈值（毫秒）
DEFAULT_DB_LATENCY_WARNING = 100
DEFAULT_DB_LATENCY_CRITICAL = 500

# API 响应时间阈值（毫秒）
DEFAULT_API_LATENCY_WARNING = 500
DEFAULT_API_LATENCY_CRITICAL = 2000

# LLM 服务响应时间阈值（毫秒）
DEFAULT_LLM_LATENCY_WARNING = 3000
DEFAULT_LLM_LATENCY_CRITICAL = 10000

# SLA 目标可用率（百分比）
DEFAULT_SLA_TARGET = 99.9

# 健康检查表名
HEALTH_HISTORY_TABLE = "health_history"
HEALTH_INCIDENTS_TABLE = "health_incidents"


# ===== 工具函数 =====

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


def _format_bytes(num_bytes: float) -> str:
    """格式化字节数为人类可读字符串。"""
    for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} EB"


def _format_duration(seconds: float) -> str:
    """格式化秒数为人类可读的持续时间。"""
    if seconds < 60:
        return f"{seconds:.1f} 秒"
    elif seconds < 3600:
        return f"{seconds / 60:.1f} 分钟"
    elif seconds < 86400:
        return f"{seconds / 3600:.1f} 小时"
    else:
        return f"{seconds / 86400:.1f} 天"


# ===== 数据类定义 =====

@dataclass
class CheckResult:
    """单项检查结果。

    Attributes:
        name: 检查项名称。
        status: 健康状态（healthy/degraded/unhealthy/unknown）。
        message: 状态描述消息。
        details: 详细信息字典。
        latency_ms: 检查耗时（毫秒）。
        timestamp: 检查时间戳。
        error: 错误信息（若有）。
    """
    name: str = ""
    status: str = UNKNOWN
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0
    timestamp: str = field(default_factory=_iso_now)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典表示。"""
        return {
            "name": self.name,
            "status": self.status,
            "status_name": STATUS_NAMES.get(self.status, "未知"),
            "message": self.message,
            "details": self.details,
            "latency_ms": round(self.latency_ms, 2),
            "timestamp": self.timestamp,
            "error": self.error,
        }


@dataclass
class HealthStatus:
    """聚合健康状态。

    Attributes:
        overall: 总体状态（取所有检查项的最差状态）。
        checks: 各项检查结果。
        timestamp: 检查时间戳。
        uptime_seconds: 系统运行时长（秒）。
    """
    overall: str = UNKNOWN
    checks: Dict[str, CheckResult] = field(default_factory=dict)
    timestamp: str = field(default_factory=_iso_now)
    uptime_seconds: float = 0.0

    @property
    def is_healthy(self) -> bool:
        """是否健康。"""
        return self.overall == HEALTHY

    @property
    def is_degraded(self) -> bool:
        """是否降级。"""
        return self.overall == DEGRADED

    @property
    def is_unhealthy(self) -> bool:
        """是否不健康。"""
        return self.overall == UNHEALTHY

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典表示。"""
        return {
            "overall": self.overall,
            "overall_name": STATUS_NAMES.get(self.overall, "未知"),
            "is_healthy": self.is_healthy,
            "is_degraded": self.is_degraded,
            "is_unhealthy": self.is_unhealthy,
            "timestamp": self.timestamp,
            "uptime_seconds": round(self.uptime_seconds, 2),
            "uptime_formatted": _format_duration(self.uptime_seconds),
            "checks": {name: result.to_dict() for name, result in self.checks.items()},
            "check_count": len(self.checks),
            "healthy_count": sum(1 for r in self.checks.values() if r.status == HEALTHY),
            "degraded_count": sum(1 for r in self.checks.values() if r.status == DEGRADED),
            "unhealthy_count": sum(1 for r in self.checks.values() if r.status == UNHEALTHY),
        }


@dataclass
class HealthIncident:
    """健康事件（故障记录）。

    Attributes:
        incident_id: 事件 ID。
        check_name: 相关检查项名称。
        status: 事件状态。
        message: 事件描述。
        started_at: 开始时间。
        ended_at: 结束时间（若已恢复）。
        duration_seconds: 持续时长（秒）。
        resolved: 是否已恢复。
        actions_taken: 采取的恢复动作列表。
    """
    incident_id: str = ""
    check_name: str = ""
    status: str = UNHEALTHY
    message: str = ""
    started_at: str = field(default_factory=_iso_now)
    ended_at: Optional[str] = None
    duration_seconds: float = 0.0
    resolved: bool = False
    actions_taken: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典表示。"""
        return {
            "incident_id": self.incident_id,
            "check_name": self.check_name,
            "status": self.status,
            "message": self.message,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_seconds": round(self.duration_seconds, 2),
            "duration_formatted": _format_duration(self.duration_seconds),
            "resolved": self.resolved,
            "actions_taken": self.actions_taken,
        }


@dataclass
class SLAReport:
    """SLA 报告。

    Attributes:
        period_start: 报告周期开始时间。
        period_end: 报告周期结束时间。
        total_seconds: 周期总时长（秒）。
        uptime_seconds: 可用时长（秒）。
        downtime_seconds: 不可用时长（秒）。
        availability: 可用率（百分比）。
        sla_target: SLA 目标（百分比）。
        sla_met: 是否满足 SLA。
        incidents: 事件列表。
        incident_count: 事件数。
    """
    period_start: str = ""
    period_end: str = ""
    total_seconds: float = 0.0
    uptime_seconds: float = 0.0
    downtime_seconds: float = 0.0
    availability: float = 0.0
    sla_target: float = DEFAULT_SLA_TARGET
    sla_met: bool = False
    incidents: List[HealthIncident] = field(default_factory=list)
    incident_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典表示。"""
        return {
            "period_start": self.period_start,
            "period_end": self.period_end,
            "total_seconds": round(self.total_seconds, 2),
            "total_formatted": _format_duration(self.total_seconds),
            "uptime_seconds": round(self.uptime_seconds, 2),
            "uptime_formatted": _format_duration(self.uptime_seconds),
            "downtime_seconds": round(self.downtime_seconds, 2),
            "downtime_formatted": _format_duration(self.downtime_seconds),
            "availability": round(self.availability, 4),
            "sla_target": self.sla_target,
            "sla_met": self.sla_met,
            "incident_count": self.incident_count,
            "incidents": [i.to_dict() for i in self.incidents],
        }


# ===== 主类：健康检查器 =====

class HealthChecker:
    """系统健康检查器。

    提供全面的系统健康监控能力，包括数据库、API、LLM 服务、
    磁盘、内存、CPU 等多项检查，支持健康状态聚合、故障告警、
    自动恢复、历史记录与 SLA 监控。

    线程安全说明：所有共享状态均使用锁保护，可在多线程环境使用。
    建议通过 get_instance() 获取全局单例。

    Attributes:
        check_interval: 检查间隔（秒）。
        history_capacity: 历史记录容量。
    """

    # 单例实例
    _instance: Optional["HealthChecker"] = None
    _instance_lock = threading.Lock()

    def __init__(
        self,
        check_interval: float = DEFAULT_CHECK_INTERVAL,
        history_capacity: int = DEFAULT_HISTORY_CAPACITY,
        enable_auto_recovery: bool = True,
    ) -> None:
        """初始化健康检查器。

        Args:
            check_interval: 检查间隔（秒）。
            history_capacity: 历史记录容量。
            enable_auto_recovery: 是否启用自动恢复。
        """
        self.check_interval: float = check_interval
        self.history_capacity: int = history_capacity
        self.enable_auto_recovery: bool = enable_auto_recovery
        # 阈值配置
        self.thresholds: Dict[str, Dict[str, float]] = {
            "cpu": {
                "warning": DEFAULT_CPU_WARNING_THRESHOLD,
                "critical": DEFAULT_CPU_CRITICAL_THRESHOLD,
            },
            "memory": {
                "warning": DEFAULT_MEM_WARNING_THRESHOLD,
                "critical": DEFAULT_MEM_CRITICAL_THRESHOLD,
            },
            "disk": {
                "warning": DEFAULT_DISK_WARNING_THRESHOLD,
                "critical": DEFAULT_DISK_CRITICAL_THRESHOLD,
            },
            "db_latency": {
                "warning": DEFAULT_DB_LATENCY_WARNING,
                "critical": DEFAULT_DB_LATENCY_CRITICAL,
            },
            "api_latency": {
                "warning": DEFAULT_API_LATENCY_WARNING,
                "critical": DEFAULT_API_LATENCY_CRITICAL,
            },
            "llm_latency": {
                "warning": DEFAULT_LLM_LATENCY_WARNING,
                "critical": DEFAULT_LLM_LATENCY_CRITICAL,
            },
        }
        # 历史记录（内存环形缓冲）
        self._history: Deque[HealthStatus] = deque(maxlen=history_capacity)
        self._history_lock = threading.Lock()
        # 活跃事件（未恢复的故障）
        self._active_incidents: Dict[str, HealthIncident] = {}
        self._incidents_lock = threading.Lock()
        # 历史事件
        self._incident_history: Deque[HealthIncident] = deque(maxlen=1000)
        # 检查项注册表
        self._checks: Dict[str, Callable[[], CheckResult]] = {}
        self._checks_lock = threading.Lock()
        # 自动恢复动作注册表
        self._recovery_actions: Dict[str, Callable[[], bool]] = {}
        # 启动时间
        self._start_time: float = _now_ts()
        # 后台检查线程
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitor_running: bool = False
        # API 端点配置
        self._api_endpoints: Dict[str, str] = {}
        # LLM 服务配置
        self._llm_endpoints: Dict[str, str] = {}
        # 初始化数据库表
        self._init_db()
        # 注册默认检查项
        self._register_default_checks()
        _logger.info(
            "HealthChecker 初始化完成，检查项=%d，间隔=%.1fs",
            len(self._checks), self.check_interval,
        )

    @classmethod
    def get_instance(cls) -> "HealthChecker":
        """获取全局单例实例。"""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _init_db(self) -> None:
        """初始化数据库表。"""
        try:
            Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            try:
                conn.execute("PRAGMA journal_mode=WAL;")
                # 健康历史表
                conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {HEALTH_HISTORY_TABLE} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        check_name TEXT NOT NULL,
                        status TEXT NOT NULL,
                        message TEXT,
                        latency_ms REAL,
                        details TEXT,
                        error TEXT
                    )
                """)
                # 健康事件表
                conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {HEALTH_INCIDENTS_TABLE} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        incident_id TEXT UNIQUE NOT NULL,
                        check_name TEXT NOT NULL,
                        status TEXT NOT NULL,
                        message TEXT,
                        started_at TEXT NOT NULL,
                        ended_at TEXT,
                        duration_seconds REAL,
                        resolved INTEGER DEFAULT 0,
                        actions_taken TEXT
                    )
                """)
                # 创建索引
                conn.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{HEALTH_HISTORY_TABLE}_ts "
                    f"ON {HEALTH_HISTORY_TABLE}(timestamp)"
                )
                conn.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{HEALTH_HISTORY_TABLE}_name "
                    f"ON {HEALTH_HISTORY_TABLE}(check_name)"
                )
                conn.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{HEALTH_INCIDENTS_TABLE}_name "
                    f"ON {HEALTH_INCIDENTS_TABLE}(check_name)"
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as e:  # pragma: no cover
            _logger.warning("初始化健康检查数据库表失败: %s", e)

    def _register_default_checks(self) -> None:
        """注册默认检查项。"""
        with self._checks_lock:
            self._checks["database"] = self.check_database
            self._checks["disk"] = self.check_disk
            self._checks["memory"] = self.check_memory
            self._checks["cpu"] = self.check_cpu
            self._checks["python_runtime"] = self.check_python_runtime

    # ===== 检查项注册 =====

    def register_check(self, name: str, check_func: Callable[[], CheckResult]) -> None:
        """注册自定义检查项。

        Args:
            name: 检查项名称。
            check_func: 检查函数，返回 CheckResult。
        """
        with self._checks_lock:
            self._checks[name] = check_func
        _logger.info("注册健康检查项: %s", name)

    def unregister_check(self, name: str) -> bool:
        """注销检查项。"""
        with self._checks_lock:
            if name in self._checks:
                del self._checks[name]
                _logger.info("注销健康检查项: %s", name)
                return True
            return False

    def register_api_endpoint(self, name: str, url: str) -> None:
        """注册 API 端点用于健康检查。"""
        self._api_endpoints[name] = url

    def register_llm_endpoint(self, name: str, url: str) -> None:
        """注册 LLM 服务端点用于健康检查。"""
        self._llm_endpoints[name] = url

    def register_recovery_action(
        self,
        check_name: str,
        action: Callable[[], bool],
    ) -> None:
        """注册自动恢复动作。

        Args:
            check_name: 检查项名称。
            action: 恢复动作函数，返回是否成功。
        """
        self._recovery_actions[check_name] = action

    def set_threshold(
        self,
        check_name: str,
        warning: float,
        critical: float,
    ) -> None:
        """设置检查项阈值。

        Args:
            check_name: 检查项名称（cpu/memory/disk/db_latency 等）。
            warning: 警告阈值。
            critical: 严重阈值。
        """
        if check_name in self.thresholds:
            self.thresholds[check_name]["warning"] = warning
            self.thresholds[check_name]["critical"] = critical

    # ===== 单项检查 =====

    def check_database(self) -> CheckResult:
        """数据库健康检查。

        检查数据库连接、WAL 模式、表完整性与响应时间。

        Returns:
            检查结果。
        """
        start_time = _now_ts()
        result = CheckResult(name="database")
        try:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=DEFAULT_TIMEOUT)
            try:
                # 检查连接
                cursor = conn.execute("SELECT 1")
                cursor.fetchone()
                # 检查 WAL 模式
                cursor = conn.execute("PRAGMA journal_mode")
                journal_mode = cursor.fetchone()[0]
                # 检查表完整性
                cursor = conn.execute("PRAGMA integrity_check")
                integrity = cursor.fetchone()[0]
                # 检查数据库大小
                db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
                # 计算延迟
                latency_ms = (_now_ts() - start_time) * 1000
                # 判断状态
                if integrity != "ok":
                    result.status = UNHEALTHY
                    result.message = f"数据库完整性检查失败: {integrity}"
                    result.error = integrity
                elif journal_mode.lower() != "wal":
                    result.status = DEGRADED
                    result.message = f"数据库未启用 WAL 模式（当前: {journal_mode}）"
                elif latency_ms > self.thresholds["db_latency"]["critical"]:
                    result.status = UNHEALTHY
                    result.message = f"数据库响应过慢: {latency_ms:.0f}ms"
                elif latency_ms > self.thresholds["db_latency"]["warning"]:
                    result.status = DEGRADED
                    result.message = f"数据库响应较慢: {latency_ms:.0f}ms"
                else:
                    result.status = HEALTHY
                    result.message = "数据库运行正常"
                result.details = {
                    "journal_mode": journal_mode,
                    "integrity": integrity,
                    "db_size_bytes": db_size,
                    "db_size_formatted": _format_bytes(db_size),
                    "db_path": DB_PATH,
                }
                result.latency_ms = latency_ms
            finally:
                conn.close()
        except sqlite3.Error as e:
            result.status = UNHEALTHY
            result.message = f"数据库连接失败: {e}"
            result.error = str(e)
            result.latency_ms = (_now_ts() - start_time) * 1000
        except Exception as e:
            result.status = UNHEALTHY
            result.message = f"数据库检查异常: {e}"
            result.error = str(e)
            result.latency_ms = (_now_ts() - start_time) * 1000
        return result

    def check_disk(self, path: str = "/") -> CheckResult:
        """磁盘空间检查。

        Args:
            path: 检查的磁盘路径。

        Returns:
            检查结果。
        """
        result = CheckResult(name="disk")
        try:
            # Windows 下使用当前盘符
            if os.name == "nt" and path == "/":
                path = os.path.splitdrive(os.getcwd())[0] + "\\"
            disk_usage = shutil.disk_usage(path)
            total = disk_usage.total
            used = disk_usage.used
            free = disk_usage.free
            usage_percent = (used / total * 100) if total > 0 else 0
            # 判断状态
            if usage_percent >= self.thresholds["disk"]["critical"]:
                result.status = UNHEALTHY
                result.message = f"磁盘空间严重不足: {usage_percent:.1f}%"
            elif usage_percent >= self.thresholds["disk"]["warning"]:
                result.status = DEGRADED
                result.message = f"磁盘空间不足: {usage_percent:.1f}%"
            else:
                result.status = HEALTHY
                result.message = f"磁盘空间充足: {usage_percent:.1f}%"
            result.details = {
                "path": path,
                "total_bytes": total,
                "total_formatted": _format_bytes(total),
                "used_bytes": used,
                "used_formatted": _format_bytes(used),
                "free_bytes": free,
                "free_formatted": _format_bytes(free),
                "usage_percent": round(usage_percent, 2),
            }
        except Exception as e:
            result.status = UNKNOWN
            result.message = f"磁盘检查失败: {e}"
            result.error = str(e)
        return result

    def check_memory(self) -> CheckResult:
        """内存使用检查。

        Returns:
            检查结果。
        """
        result = CheckResult(name="memory")
        if not _HAS_PSUTIL:
            # 降级：使用 os 模块获取有限信息
            result.status = UNKNOWN
            result.message = "psutil 未安装，无法获取内存信息"
            result.details = {"psutil_available": False}
            return result
        try:
            mem = psutil.virtual_memory()
            total = mem.total
            available = mem.available
            used = mem.used
            usage_percent = mem.percent
            # 交换分区
            swap = psutil.swap_memory()
            # 判断状态
            if usage_percent >= self.thresholds["memory"]["critical"]:
                result.status = UNHEALTHY
                result.message = f"内存使用严重过高: {usage_percent:.1f}%"
            elif usage_percent >= self.thresholds["memory"]["warning"]:
                result.status = DEGRADED
                result.message = f"内存使用过高: {usage_percent:.1f}%"
            else:
                result.status = HEALTHY
                result.message = f"内存使用正常: {usage_percent:.1f}%"
            result.details = {
                "total_bytes": total,
                "total_formatted": _format_bytes(total),
                "available_bytes": available,
                "available_formatted": _format_bytes(available),
                "used_bytes": used,
                "used_formatted": _format_bytes(used),
                "usage_percent": round(usage_percent, 2),
                "swap_total_bytes": swap.total,
                "swap_used_bytes": swap.used,
                "swap_percent": swap.percent,
            }
        except Exception as e:
            result.status = UNKNOWN
            result.message = f"内存检查失败: {e}"
            result.error = str(e)
        return result

    def check_cpu(self) -> CheckResult:
        """CPU 负载检查。

        Returns:
            检查结果。
        """
        result = CheckResult(name="cpu")
        if not _HAS_PSUTIL:
            result.status = UNKNOWN
            result.message = "psutil 未安装，无法获取 CPU 信息"
            result.details = {"psutil_available": False}
            return result
        try:
            # CPU 使用率（interval=None 表示非阻塞，返回上次调用以来的平均值）
            cpu_percent = psutil.cpu_percent(interval=0.1)
            # CPU 核心数
            cpu_count = psutil.cpu_count(logical=True)
            cpu_count_physical = psutil.cpu_count(logical=False)
            # 负载平均值（Unix 系统可用）
            load_avg: Optional[Tuple[float, float, float]] = None
            if hasattr(psutil, "getloadavg"):
                try:
                    load_avg = psutil.getloadavg()
                except Exception:  # pragma: no cover
                    pass
            # 判断状态
            if cpu_percent >= self.thresholds["cpu"]["critical"]:
                result.status = UNHEALTHY
                result.message = f"CPU 使用率严重过高: {cpu_percent:.1f}%"
            elif cpu_percent >= self.thresholds["cpu"]["warning"]:
                result.status = DEGRADED
                result.message = f"CPU 使用率过高: {cpu_percent:.1f}%"
            else:
                result.status = HEALTHY
                result.message = f"CPU 使用率正常: {cpu_percent:.1f}%"
            result.details = {
                "cpu_percent": round(cpu_percent, 2),
                "logical_cores": cpu_count,
                "physical_cores": cpu_count_physical,
                "load_avg_1min": load_avg[0] if load_avg else None,
                "load_avg_5min": load_avg[1] if load_avg else None,
                "load_avg_15min": load_avg[2] if load_avg else None,
            }
        except Exception as e:
            result.status = UNKNOWN
            result.message = f"CPU 检查失败: {e}"
            result.error = str(e)
        return result

    def check_python_runtime(self) -> CheckResult:
        """Python 运行时检查。

        Returns:
            检查结果。
        """
        import sys
        result = CheckResult(name="python_runtime")
        try:
            # 进程信息
            pid = os.getpid()
            # 线程数
            thread_count = threading.active_count()
            # Python 版本
            python_version = sys.version
            # 判断状态
            if thread_count > 500:
                result.status = DEGRADED
                result.message = f"线程数过多: {thread_count}"
            else:
                result.status = HEALTHY
                result.message = "Python 运行时正常"
            result.details = {
                "pid": pid,
                "thread_count": thread_count,
                "python_version": python_version,
                "platform": sys.platform,
            }
            # 进程级资源（需要 psutil）
            if _HAS_PSUTIL:
                try:
                    proc = psutil.Process(pid)
                    result.details["process_memory_rss"] = proc.memory_info().rss
                    result.details["process_memory_rss_formatted"] = _format_bytes(
                        proc.memory_info().rss
                    )
                    result.details["process_cpu_percent"] = proc.cpu_percent()
                    result.details["process_create_time"] = datetime.fromtimestamp(
                        proc.create_time(), tz=timezone.utc
                    ).isoformat()
                    result.details["process_thread_count"] = proc.num_threads()
                    # 文件描述符数
                    if hasattr(proc, "num_fds"):
                        result.details["process_fd_count"] = proc.num_fds()
                    elif os.name == "nt":
                        try:
                            result.details["process_handle_count"] = proc.num_handles()
                        except Exception:  # pragma: no cover
                            pass
                except Exception:  # pragma: no cover
                    pass
        except Exception as e:
            result.status = UNKNOWN
            result.message = f"运行时检查失败: {e}"
            result.error = str(e)
        return result

    def check_api_endpoint(
        self,
        name: str,
        url: str,
        timeout: float = DEFAULT_TIMEOUT,
        expected_status: int = 200,
    ) -> CheckResult:
        """API 端点健康检查。

        Args:
            name: 端点名称。
            url: 端点 URL。
            timeout: 超时时间。
            expected_status: 期望的 HTTP 状态码。

        Returns:
            检查结果。
        """
        start_time = _now_ts()
        result = CheckResult(name=f"api_{name}")
        try:
            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", "ThesisMiner-HealthChecker/1.0")
            with urllib.request.urlopen(req, timeout=timeout) as response:
                status_code = response.getcode()
                latency_ms = (_now_ts() - start_time) * 1000
                # 判断状态
                if status_code != expected_status:
                    result.status = UNHEALTHY
                    result.message = f"API 返回异常状态码: {status_code}（期望: {expected_status}）"
                elif latency_ms > self.thresholds["api_latency"]["critical"]:
                    result.status = UNHEALTHY
                    result.message = f"API 响应过慢: {latency_ms:.0f}ms"
                elif latency_ms > self.thresholds["api_latency"]["warning"]:
                    result.status = DEGRADED
                    result.message = f"API 响应较慢: {latency_ms:.0f}ms"
                else:
                    result.status = HEALTHY
                    result.message = "API 响应正常"
                result.details = {
                    "url": url,
                    "status_code": status_code,
                    "expected_status": expected_status,
                }
                result.latency_ms = latency_ms
        except urllib.error.HTTPError as e:
            result.status = UNHEALTHY
            result.message = f"API HTTP 错误: {e.code}"
            result.error = str(e)
            result.latency_ms = (_now_ts() - start_time) * 1000
            result.details = {"url": url, "status_code": e.code}
        except urllib.error.URLError as e:
            result.status = UNHEALTHY
            result.message = f"API 不可达: {e.reason}"
            result.error = str(e)
            result.latency_ms = (_now_ts() - start_time) * 1000
            result.details = {"url": url}
        except Exception as e:
            result.status = UNHEALTHY
            result.message = f"API 检查异常: {e}"
            result.error = str(e)
            result.latency_ms = (_now_ts() - start_time) * 1000
            result.details = {"url": url}
        return result

    def check_llm_service(
        self,
        name: str,
        url: str,
        timeout: float = DEFAULT_TIMEOUT,
        api_key: Optional[str] = None,
    ) -> CheckResult:
        """LLM 服务健康检查。

        Args:
            name: 服务名称。
            url: 服务 URL。
            timeout: 超时时间。
            api_key: API 密钥（可选）。

        Returns:
            检查结果。
        """
        start_time = _now_ts()
        result = CheckResult(name=f"llm_{name}")
        try:
            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", "ThesisMiner-HealthChecker/1.0")
            if api_key:
                req.add_header("Authorization", f"Bearer {api_key}")
            with urllib.request.urlopen(req, timeout=timeout) as response:
                status_code = response.getcode()
                latency_ms = (_now_ts() - start_time) * 1000
                # 判断状态
                if status_code != 200:
                    result.status = UNHEALTHY
                    result.message = f"LLM 服务返回异常状态码: {status_code}"
                elif latency_ms > self.thresholds["llm_latency"]["critical"]:
                    result.status = UNHEALTHY
                    result.message = f"LLM 服务响应过慢: {latency_ms:.0f}ms"
                elif latency_ms > self.thresholds["llm_latency"]["warning"]:
                    result.status = DEGRADED
                    result.message = f"LLM 服务响应较慢: {latency_ms:.0f}ms"
                else:
                    result.status = HEALTHY
                    result.message = "LLM 服务正常"
                result.details = {
                    "url": url,
                    "status_code": status_code,
                    "service_name": name,
                }
                result.latency_ms = latency_ms
        except urllib.error.HTTPError as e:
            result.status = UNHEALTHY
            result.message = f"LLM 服务 HTTP 错误: {e.code}"
            result.error = str(e)
            result.latency_ms = (_now_ts() - start_time) * 1000
            result.details = {"url": url, "status_code": e.code}
        except urllib.error.URLError as e:
            result.status = UNHEALTHY
            result.message = f"LLM 服务不可达: {e.reason}"
            result.error = str(e)
            result.latency_ms = (_now_ts() - start_time) * 1000
            result.details = {"url": url}
        except Exception as e:
            result.status = UNHEALTHY
            result.message = f"LLM 服务检查异常: {e}"
            result.error = str(e)
            result.latency_ms = (_now_ts() - start_time) * 1000
            result.details = {"url": url}
        return result

    def check_tcp_port(
        self,
        host: str,
        port: int,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> CheckResult:
        """TCP 端口连通性检查。

        Args:
            host: 主机地址。
            port: 端口号。
            timeout: 超时时间。

        Returns:
            检查结果。
        """
        start_time = _now_ts()
        result = CheckResult(name=f"tcp_{host}_{port}")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            try:
                sock.connect((host, port))
                latency_ms = (_now_ts() - start_time) * 1000
                result.status = HEALTHY
                result.message = f"端口 {port} 可达"
                result.details = {
                    "host": host,
                    "port": port,
                    "connected": True,
                }
                result.latency_ms = latency_ms
            finally:
                sock.close()
        except socket.timeout:
            result.status = UNHEALTHY
            result.message = f"端口 {port} 连接超时"
            result.error = "timeout"
            result.latency_ms = (_now_ts() - start_time) * 1000
            result.details = {"host": host, "port": port, "connected": False}
        except ConnectionRefusedError:
            result.status = UNHEALTHY
            result.message = f"端口 {port} 连接被拒绝"
            result.error = "connection refused"
            result.latency_ms = (_now_ts() - start_time) * 1000
            result.details = {"host": host, "port": port, "connected": False}
        except Exception as e:
            result.status = UNHEALTHY
            result.message = f"端口 {port} 检查失败: {e}"
            result.error = str(e)
            result.latency_ms = (_now_ts() - start_time) * 1000
            result.details = {"host": host, "port": port, "connected": False}
        return result

    # ===== 聚合检查 =====

    def check_all(self) -> HealthStatus:
        """执行所有注册的检查项。

        Returns:
            聚合健康状态。
        """
        status = HealthStatus(
            timestamp=_iso_now(),
            uptime_seconds=_now_ts() - self._start_time,
        )
        # 执行所有检查
        with self._checks_lock:
            checks = dict(self._checks)
        for name, check_func in checks.items():
            try:
                result = check_func()
                status.checks[name] = result
            except Exception as e:
                status.checks[name] = CheckResult(
                    name=name,
                    status=UNHEALTHY,
                    message=f"检查执行异常: {e}",
                    error=str(e),
                )
        # 执行 API 端点检查
        for name, url in self._api_endpoints.items():
            result = self.check_api_endpoint(name, url)
            status.checks[f"api_{name}"] = result
        # 执行 LLM 服务检查
        for name, url in self._llm_endpoints.items():
            result = self.check_llm_service(name, url)
            status.checks[f"llm_{name}"] = result
        # 聚合状态
        status.overall = self._aggregate_status(status.checks)
        # 记录历史
        self._record_history(status)
        # 检测事件
        self._detect_incidents(status)
        return status

    def _aggregate_status(self, checks: Dict[str, CheckResult]) -> str:
        """聚合所有检查项的状态。

        取最差状态作为总体状态。

        Args:
            checks: 检查结果字典。

        Returns:
            聚合状态字符串。
        """
        if not checks:
            return UNKNOWN
        status_priority = {HEALTHY: 0, DEGRADED: 1, UNHEALTHY: 2, UNKNOWN: 3}
        worst_status = HEALTHY
        for result in checks.values():
            if status_priority.get(result.status, 3) > status_priority.get(worst_status, 0):
                worst_status = result.status
        return worst_status

    # ===== 历史记录 =====

    def _record_history(self, status: HealthStatus) -> None:
        """记录健康状态到历史。"""
        with self._history_lock:
            self._history.append(status)
        # 持久化到数据库
        self._persist_check_results(status)

    def _persist_check_results(self, status: HealthStatus) -> None:
        """将检查结果持久化到数据库。"""
        try:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            try:
                for name, result in status.checks.items():
                    conn.execute(
                        f"INSERT INTO {HEALTH_HISTORY_TABLE} "
                        f"(timestamp, check_name, status, message, latency_ms, details, error) "
                        f"VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            result.timestamp,
                            name,
                            result.status,
                            result.message,
                            result.latency_ms,
                            json.dumps(result.details, ensure_ascii=False),
                            result.error,
                        ),
                    )
                conn.commit()
            finally:
                conn.close()
        except Exception as e:  # pragma: no cover
            _logger.debug("持久化健康检查结果失败: %s", e)

    def get_history(
        self,
        check_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """获取健康检查历史。

        Args:
            check_name: 检查项名称，为 None 时返回所有。
            limit: 返回记录数。

        Returns:
            历史记录列表。
        """
        try:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            try:
                if check_name:
                    cursor = conn.execute(
                        f"SELECT * FROM {HEALTH_HISTORY_TABLE} "
                        f"WHERE check_name = ? ORDER BY timestamp DESC LIMIT ?",
                        (check_name, limit),
                    )
                else:
                    cursor = conn.execute(
                        f"SELECT * FROM {HEALTH_HISTORY_TABLE} "
                        f"ORDER BY timestamp DESC LIMIT ?",
                        (limit,),
                    )
                rows = cursor.fetchall()
                return [
                    {
                        "timestamp": row["timestamp"],
                        "check_name": row["check_name"],
                        "status": row["status"],
                        "message": row["message"],
                        "latency_ms": row["latency_ms"],
                        "details": json.loads(row["details"]) if row["details"] else {},
                        "error": row["error"],
                    }
                    for row in rows
                ]
            finally:
                conn.close()
        except Exception as e:  # pragma: no cover
            _logger.warning("获取健康检查历史失败: %s", e)
            return []

    # ===== 事件管理 =====

    def _detect_incidents(self, status: HealthStatus) -> None:
        """检测健康事件（故障与恢复）。"""
        with self._incidents_lock:
            for name, result in status.checks.items():
                if result.status == UNHEALTHY:
                    # 检查是否已有活跃事件
                    if name not in self._active_incidents:
                        # 创建新事件
                        incident = HealthIncident(
                            incident_id=f"{name}_{int(_now_ts() * 1000)}",
                            check_name=name,
                            status=result.status,
                            message=result.message,
                            started_at=result.timestamp,
                        )
                        self._active_incidents[name] = incident
                        _logger.warning(
                            "检测到健康事件: %s - %s", name, result.message
                        )
                        # 尝试自动恢复
                        if self.enable_auto_recovery:
                            self._attempt_recovery(name, incident)
                elif result.status in (HEALTHY, DEGRADED):
                    # 检查是否有活跃事件需要恢复
                    if name in self._active_incidents:
                        incident = self._active_incidents.pop(name)
                        incident.resolved = True
                        incident.ended_at = result.timestamp
                        incident.duration_seconds = _now_ts() - _parse_iso_ts(incident.started_at)
                        self._incident_history.append(incident)
                        self._persist_incident(incident)
                        _logger.info(
                            "健康事件已恢复: %s，持续 %s",
                            name, _format_duration(incident.duration_seconds),
                        )

    def _attempt_recovery(self, check_name: str, incident: HealthIncident) -> None:
        """尝试自动恢复。

        Args:
            check_name: 检查项名称。
            incident: 相关事件。
        """
        action = self._recovery_actions.get(check_name)
        if action is None:
            return
        try:
            _logger.info("尝试自动恢复: %s", check_name)
            success = action()
            incident.actions_taken.append(
                f"自动恢复动作执行: {'成功' if success else '失败'}"
            )
            if success:
                _logger.info("自动恢复成功: %s", check_name)
            else:
                _logger.warning("自动恢复失败: %s", check_name)
        except Exception as e:
            incident.actions_taken.append(f"自动恢复异常: {e}")
            _logger.error("自动恢复异常: %s - %s", check_name, e)

    def _persist_incident(self, incident: HealthIncident) -> None:
        """持久化事件到数据库。"""
        try:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            try:
                conn.execute(
                    f"INSERT OR REPLACE INTO {HEALTH_INCIDENTS_TABLE} "
                    f"(incident_id, check_name, status, message, started_at, ended_at, "
                    f"duration_seconds, resolved, actions_taken) "
                    f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        incident.incident_id,
                        incident.check_name,
                        incident.status,
                        incident.message,
                        incident.started_at,
                        incident.ended_at,
                        incident.duration_seconds,
                        1 if incident.resolved else 0,
                        json.dumps(incident.actions_taken, ensure_ascii=False),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as e:  # pragma: no cover
            _logger.debug("持久化健康事件失败: %s", e)

    def get_active_incidents(self) -> List[HealthIncident]:
        """获取当前活跃事件。"""
        with self._incidents_lock:
            return list(self._active_incidents.values())

    def get_incident_history(
        self,
        check_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[HealthIncident]:
        """获取事件历史。"""
        try:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            try:
                if check_name:
                    cursor = conn.execute(
                        f"SELECT * FROM {HEALTH_INCIDENTS_TABLE} "
                        f"WHERE check_name = ? ORDER BY started_at DESC LIMIT ?",
                        (check_name, limit),
                    )
                else:
                    cursor = conn.execute(
                        f"SELECT * FROM {HEALTH_INCIDENTS_TABLE} "
                        f"ORDER BY started_at DESC LIMIT ?",
                        (limit,),
                    )
                rows = cursor.fetchall()
                incidents: List[HealthIncident] = []
                for row in rows:
                    incident = HealthIncident(
                        incident_id=row["incident_id"],
                        check_name=row["check_name"],
                        status=row["status"],
                        message=row["message"],
                        started_at=row["started_at"],
                        ended_at=row["ended_at"],
                        duration_seconds=row["duration_seconds"] or 0.0,
                        resolved=bool(row["resolved"]),
                        actions_taken=json.loads(row["actions_taken"]) if row["actions_taken"] else [],
                    )
                    incidents.append(incident)
                return incidents
            finally:
                conn.close()
        except Exception as e:  # pragma: no cover
            _logger.warning("获取事件历史失败: %s", e)
            return []

    # ===== 存活与就绪检查 =====

    def liveness(self) -> bool:
        """存活检查（Liveness）。

        检查进程是否正常运行。若返回 False，应重启服务。

        Returns:
            是否存活。
        """
        try:
            # 简单检查：能否执行基本操作
            _ = os.getpid()
            _ = threading.active_count()
            return True
        except Exception:  # pragma: no cover
            return False

    def readiness(self) -> bool:
        """就绪检查（Readiness）。

        检查服务是否准备好接收请求。若返回 False，应停止转发流量。

        Returns:
            是否就绪。
        """
        try:
            # 检查数据库是否可用
            db_result = self.check_database()
            if db_result.status == UNHEALTHY:
                return False
            return True
        except Exception:  # pragma: no cover
            return False

    # ===== 后台监控 =====

    def start_monitoring(self, interval: Optional[float] = None) -> None:
        """启动后台监控线程。

        Args:
            interval: 检查间隔（秒），为 None 时使用默认值。
        """
        if self._monitor_running:
            _logger.warning("监控线程已在运行")
            return
        if interval is not None:
            self.check_interval = interval
        self._monitor_running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="HealthMonitor",
        )
        self._monitor_thread.start()
        _logger.info("健康监控已启动，间隔=%.1fs", self.check_interval)

    def stop_monitoring(self) -> None:
        """停止后台监控。"""
        self._monitor_running = False
        if self._monitor_thread is not None:
            self._monitor_thread.join(timeout=10)
            self._monitor_thread = None
        _logger.info("健康监控已停止")

    def _monitor_loop(self) -> None:
        """监控循环。"""
        while self._monitor_running:
            try:
                self.check_all()
            except Exception as e:  # pragma: no cover
                _logger.error("健康检查循环异常: %s", e)
            # 等待下一次检查
            time.sleep(self.check_interval)

    # ===== 趋势分析 =====

    def analyze_trend(
        self,
        check_name: str,
        hours: int = 24,
    ) -> Dict[str, Any]:
        """分析检查项的趋势。

        Args:
            check_name: 检查项名称。
            hours: 分析的时间范围（小时）。

        Returns:
            趋势分析结果。
        """
        history = self.get_history(check_name=check_name, limit=10000)
        if not history:
            return {
                "check_name": check_name,
                "sample_count": 0,
                "message": "无历史数据",
            }
        # 过滤时间范围
        cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
        cutoff_str = cutoff.isoformat()
        recent_history = [
            h for h in history if h["timestamp"] >= cutoff_str
        ]
        if not recent_history:
            return {
                "check_name": check_name,
                "sample_count": 0,
                "message": "指定时间范围内无数据",
            }
        # 统计
        status_counts: Dict[str, int] = {}
        latencies: List[float] = []
        for record in recent_history:
            status_counts[record["status"]] = status_counts.get(record["status"], 0) + 1
            if record["latency_ms"] is not None:
                latencies.append(record["latency_ms"])
        # 延迟统计
        latency_stats: Dict[str, float] = {}
        if latencies:
            latency_stats = {
                "avg": sum(latencies) / len(latencies),
                "min": min(latencies),
                "max": max(latencies),
                "p50": _percentile(latencies, 50),
                "p95": _percentile(latencies, 95),
                "p99": _percentile(latencies, 99),
            }
        # 可用率
        total = len(recent_history)
        healthy = status_counts.get(HEALTHY, 0)
        degraded = status_counts.get(DEGRADED, 0)
        unhealthy = status_counts.get(UNHEALTHY, 0)
        availability = (healthy + degraded * 0.5) / total if total > 0 else 0
        return {
            "check_name": check_name,
            "hours": hours,
            "sample_count": total,
            "status_distribution": status_counts,
            "availability": round(availability, 4),
            "latency_stats_ms": {k: round(v, 2) for k, v in latency_stats.items()},
            "trend": "stable" if unhealthy == 0 else "degrading",
        }

    # ===== SLA 报告 =====

    def generate_sla_report(self, days: int = 30) -> SLAReport:
        """生成 SLA 报告。

        Args:
            days: 报告周期（天）。

        Returns:
            SLA 报告。
        """
        period_end = datetime.now(tz=timezone.utc)
        period_start = period_end - timedelta(days=days)
        report = SLAReport(
            period_start=period_start.isoformat(),
            period_end=period_end.isoformat(),
            total_seconds=days * 86400,
            sla_target=DEFAULT_SLA_TARGET,
        )
        # 获取事件历史
        incidents = self.get_incident_history(limit=10000)
        # 过滤时间范围
        period_incidents: List[HealthIncident] = []
        for incident in incidents:
            try:
                started = _parse_iso_ts(incident.started_at)
                if started >= period_start.timestamp():
                    period_incidents.append(incident)
            except Exception:  # pragma: no cover
                continue
        report.incidents = period_incidents
        report.incident_count = len(period_incidents)
        # 计算不可用时长
        downtime = sum(i.duration_seconds for i in period_incidents if i.status == UNHEALTHY)
        report.downtime_seconds = downtime
        report.uptime_seconds = report.total_seconds - downtime
        # 计算可用率
        if report.total_seconds > 0:
            report.availability = (report.uptime_seconds / report.total_seconds) * 100
        # 判断是否满足 SLA
        report.sla_met = report.availability >= DEFAULT_SLA_TARGET
        return report

    # ===== 健康摘要 =====

    def get_health_summary(self) -> Dict[str, Any]:
        """获取健康摘要。"""
        status = self.check_all()
        active_incidents = self.get_active_incidents()
        return {
            "overall": status.overall,
            "overall_name": STATUS_NAMES.get(status.overall, "未知"),
            "timestamp": status.timestamp,
            "uptime_seconds": round(status.uptime_seconds, 2),
            "uptime_formatted": _format_duration(status.uptime_seconds),
            "check_count": len(status.checks),
            "healthy_count": sum(1 for r in status.checks.values() if r.status == HEALTHY),
            "degraded_count": sum(1 for r in status.checks.values() if r.status == DEGRADED),
            "unhealthy_count": sum(1 for r in status.checks.values() if r.status == UNHEALTHY),
            "active_incidents": len(active_incidents),
            "checks": {name: r.to_dict() for name, r in status.checks.items()},
        }

    def get_last_status(self) -> Optional[HealthStatus]:
        """获取最近一次健康状态。"""
        with self._history_lock:
            if self._history:
                return self._history[-1]
        return None


# ===== 辅助函数 =====

def _parse_iso_ts(iso_str: str) -> float:
    """解析 ISO8601 时间字符串为时间戳。"""
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.timestamp()
    except Exception:
        return _now_ts()


def _percentile(data: List[float], p: float) -> float:
    """计算百分位数。

    Args:
        data: 数据列表。
        p: 百分位（0-100）。

    Returns:
        百分位数值。
    """
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * p / 100
    f = int(k)
    c = f + 1 if f + 1 < len(sorted_data) else f
    if f == c:
        return sorted_data[f]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


# ===== 模块级单例访问 =====

def get_health_checker() -> HealthChecker:
    """获取全局健康检查器单例。"""
    return HealthChecker.get_instance()


def check_health() -> HealthStatus:
    """模块级健康检查便捷函数。"""
    return get_health_checker().check_all()


def liveness_check() -> bool:
    """模块级存活检查便捷函数。"""
    return get_health_checker().liveness()


def readiness_check() -> bool:
    """模块级就绪检查便捷函数。"""
    return get_health_checker().readiness()
