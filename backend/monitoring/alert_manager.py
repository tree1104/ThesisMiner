"""告警管理器模块

提供系统告警的生成、分发与管理能力，包括：
    - 告警规则配置（基于阈值、持续时间、频率等条件）
    - 告警级别（INFO/WARN/ERROR/CRITICAL）
    - 告警去重（相同告警在时间窗口内合并）
    - 告警聚合（相关告警分组）
    - 告警抑制（维护期间或依赖故障时抑制）
    - 告警恢复（故障恢复后发送恢复通知）
    - 多渠道通知（邮件/Webhook/日志/Slack 模拟）
    - 告警历史记录与统计
    - 告警趋势分析
    - 告警规则评估引擎

所有告警数据可写入 SQLite 持久化存储，便于历史回溯与统计分析。
通知渠道采用可插拔设计，支持自定义通知器。

典型用法：
    manager = AlertManager()
    manager.add_rule(AlertRule(name="high_cpu", metric="cpu_usage",
                               threshold=90.0, level=AlertLevel.CRITICAL))
    manager.evaluate({"cpu_usage": 95.0, "memory_usage": 60.0})
    manager.notify(Alert(title="CPU 过高", message="CPU 使用率达 95%",
                         level=AlertLevel.CRITICAL))
    stats = manager.get_statistics(hours=24)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import smtplib
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from collections import deque, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import IntEnum
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple, Union

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


# ===== 常量定义 =====

# 告警表名
ALERTS_TABLE = "alerts"
ALERT_RULES_TABLE = "alert_rules"

# 默认去重窗口（秒）
DEFAULT_DEDUP_WINDOW = 300  # 5 分钟

# 默认聚合窗口（秒）
DEFAULT_AGGREGATION_WINDOW = 60  # 1 分钟

# 默认抑制时长（秒）
DEFAULT_SUPPRESSION_DURATION = 3600  # 1 小时

# 默认历史记录容量
DEFAULT_HISTORY_CAPACITY = 10000

# 默认通知重试次数
DEFAULT_RETRY_COUNT = 3

# 默认通知重试间隔（秒）
DEFAULT_RETRY_INTERVAL = 5.0


class AlertLevel(IntEnum):
    """告警级别枚举。

    数值越大表示越严重。
    """
    INFO = 1       # 信息：一般性通知
    WARN = 2       # 警告：需要关注
    ERROR = 3      # 错误：需要处理
    CRITICAL = 4   # 严重：需要立即处理


# 告警级别中文映射
ALERT_LEVEL_NAMES = {
    AlertLevel.INFO: "信息",
    AlertLevel.WARN: "警告",
    AlertLevel.ERROR: "错误",
    AlertLevel.CRITICAL: "严重",
}

# 告警级别颜色（用于通知格式化）
ALERT_LEVEL_COLORS = {
    AlertLevel.INFO: "#36C5F0",      # 蓝色
    AlertLevel.WARN: "#F2C744",      # 黄色
    AlertLevel.ERROR: "#EB5757",     # 红色
    AlertLevel.CRITICAL: "#9B2C2C",  # 深红色
}

# 告警状态枚举
ALERT_STATE_FIRING = "firing"      # 触发中
ALERT_STATE_RESOLVED = "resolved"  # 已恢复
ALERT_STATE_SUPPRESSED = "suppressed"  # 已抑制

# 告警状态中文映射
ALERT_STATE_NAMES = {
    ALERT_STATE_FIRING: "触发中",
    ALERT_STATE_RESOLVED: "已恢复",
    ALERT_STATE_SUPPRESSED: "已抑制",
}

# 比较运算符
OPERATORS = {
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


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


def _generate_alert_id(
    title: str,
    source: str,
    level: AlertLevel,
) -> str:
    """生成告警 ID（基于内容的哈希）。

    Args:
        title: 告警标题。
        source: 告警来源。
        level: 告警级别。

    Returns:
        告警 ID 字符串。
    """
    content = f"{title}|{source}|{level.name}"
    return hashlib.md5(content.encode("utf-8")).hexdigest()[:16]


# ===== 数据类定义 =====

@dataclass
class Alert:
    """告警。

    Attributes:
        alert_id: 告警唯一 ID。
        title: 告警标题。
        message: 告警消息。
        level: 告警级别。
        source: 告警来源（如 cpu/memory/database）。
        state: 告警状态（firing/resolved/suppressed）。
        timestamp: 告警时间戳。
        resolved_at: 恢复时间戳。
        labels: 标签字典（用于分类与过滤）。
        details: 详细信息字典。
        duration_seconds: 持续时长（秒）。
        notification_sent: 是否已发送通知。
        fingerprint: 指纹（用于去重）。
    """
    alert_id: str = ""
    title: str = ""
    message: str = ""
    level: AlertLevel = AlertLevel.WARN
    source: str = ""
    state: str = ALERT_STATE_FIRING
    timestamp: str = field(default_factory=_iso_now)
    resolved_at: Optional[str] = None
    labels: Dict[str, str] = field(default_factory=dict)
    details: Dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 0.0
    notification_sent: bool = False
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.alert_id:
            self.alert_id = _generate_alert_id(self.title, self.source, self.level)
        if not self.fingerprint:
            self.fingerprint = self._compute_fingerprint()

    def _compute_fingerprint(self) -> str:
        """计算告警指纹（用于去重）。"""
        content = f"{self.title}|{self.source}|{self.level.name}"
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典表示。"""
        return {
            "alert_id": self.alert_id,
            "title": self.title,
            "message": self.message,
            "level": self.level.name,
            "level_value": int(self.level),
            "level_name": ALERT_LEVEL_NAMES.get(self.level, "未知"),
            "source": self.source,
            "state": self.state,
            "state_name": ALERT_STATE_NAMES.get(self.state, "未知"),
            "timestamp": self.timestamp,
            "resolved_at": self.resolved_at,
            "labels": self.labels,
            "details": self.details,
            "duration_seconds": round(self.duration_seconds, 2),
            "duration_formatted": _format_duration(self.duration_seconds),
            "notification_sent": self.notification_sent,
            "fingerprint": self.fingerprint,
        }


@dataclass
class AlertRule:
    """告警规则。

    Attributes:
        name: 规则名称。
        metric: 监控指标名。
        operator: 比较运算符（>/>=/</<=/==/!=）。
        threshold: 阈值。
        level: 触发时的告警级别。
        duration: 持续多久才触发（秒）。
        description: 规则描述。
        enabled: 是否启用。
        labels: 附加标签。
        cooldown: 冷却时间（秒），同一规则在冷却期内不重复触发。
        last_triggered: 上次触发时间戳。
    """
    name: str = ""
    metric: str = ""
    operator: str = ">"
    threshold: float = 0.0
    level: AlertLevel = AlertLevel.WARN
    duration: float = 0.0
    description: str = ""
    enabled: bool = True
    labels: Dict[str, str] = field(default_factory=dict)
    cooldown: float = DEFAULT_DEDUP_WINDOW
    last_triggered: float = 0.0

    def evaluate(self, value: float) -> bool:
        """评估规则是否满足触发条件。

        Args:
            value: 指标值。

        Returns:
            是否满足触发条件。
        """
        if not self.enabled:
            return False
        op_func = OPERATORS.get(self.operator)
        if op_func is None:
            return False
        try:
            return op_func(value, self.threshold)
        except (TypeError, ValueError):
            return False

    def is_in_cooldown(self) -> bool:
        """是否在冷却期内。"""
        if self.cooldown <= 0:
            return False
        return (_now_ts() - self.last_triggered) < self.cooldown

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典表示。"""
        return {
            "name": self.name,
            "metric": self.metric,
            "operator": self.operator,
            "threshold": self.threshold,
            "level": self.level.name,
            "level_name": ALERT_LEVEL_NAMES.get(self.level, "未知"),
            "duration": self.duration,
            "description": self.description,
            "enabled": self.enabled,
            "labels": self.labels,
            "cooldown": self.cooldown,
            "last_triggered": datetime.fromtimestamp(
                self.last_triggered, tz=timezone.utc
            ).isoformat() if self.last_triggered > 0 else None,
        }


@dataclass
class AlertStatistics:
    """告警统计。

    Attributes:
        period_start: 统计周期开始。
        period_end: 统计周期结束。
        total: 告警总数。
        by_level: 按级别统计。
        by_source: 按来源统计。
        by_state: 按状态统计。
        resolved_count: 已恢复数。
        avg_resolution_time: 平均恢复时间（秒）。
        top_sources: 最频繁的告警来源。
    """
    period_start: str = ""
    period_end: str = ""
    total: int = 0
    by_level: Dict[str, int] = field(default_factory=dict)
    by_source: Dict[str, int] = field(default_factory=dict)
    by_state: Dict[str, int] = field(default_factory=dict)
    resolved_count: int = 0
    avg_resolution_time: float = 0.0
    top_sources: List[Tuple[str, int]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典表示。"""
        return {
            "period_start": self.period_start,
            "period_end": self.period_end,
            "total": self.total,
            "by_level": self.by_level,
            "by_source": self.by_source,
            "by_state": self.by_state,
            "resolved_count": self.resolved_count,
            "avg_resolution_time": round(self.avg_resolution_time, 2),
            "avg_resolution_time_formatted": _format_duration(self.avg_resolution_time),
            "top_sources": [{"source": s, "count": c} for s, c in self.top_sources],
        }


# ===== 通知器接口 =====

class Notifier:
    """通知器基类。

    所有通知渠道需继承此类并实现 send 方法。
    """

    def __init__(self, name: str, enabled: bool = True) -> None:
        """初始化通知器。

        Args:
            name: 通知器名称。
            enabled: 是否启用。
        """
        self.name = name
        self.enabled = enabled
        self.send_count = 0
        self.fail_count = 0
        self._lock = threading.Lock()

    def send(self, alert: Alert) -> bool:
        """发送告警通知。

        Args:
            alert: 告警对象。

        Returns:
            是否发送成功。
        """
        raise NotImplementedError

    def get_stats(self) -> Dict[str, Any]:
        """获取通知器统计。"""
        with self._lock:
            return {
                "name": self.name,
                "enabled": self.enabled,
                "send_count": self.send_count,
                "fail_count": self.fail_count,
                "success_rate": (
                    (self.send_count - self.fail_count) / self.send_count
                    if self.send_count > 0 else 0.0
                ),
            }


class LogNotifier(Notifier):
    """日志通知器。

    将告警写入日志文件。
    """

    def __init__(self, enabled: bool = True) -> None:
        super().__init__(name="log", enabled=enabled)

    def send(self, alert: Alert) -> bool:
        """将告警写入日志。"""
        if not self.enabled:
            return False
        try:
            with self._lock:
                self.send_count += 1
            log_message = (
                f"[告警] [{alert.level.name}] {alert.title} - {alert.message} "
                f"(来源: {alert.source}, ID: {alert.alert_id})"
            )
            if alert.level >= AlertLevel.ERROR:
                _logger.error(log_message)
            elif alert.level >= AlertLevel.WARN:
                _logger.warning(log_message)
            else:
                _logger.info(log_message)
            return True
        except Exception as e:  # pragma: no cover
            with self._lock:
                self.fail_count += 1
            _logger.error("日志通知发送失败: %s", e)
            return False


class WebhookNotifier(Notifier):
    """Webhook 通知器。

    将告警通过 HTTP POST 发送到指定 URL。
    """

    def __init__(
        self,
        webhook_url: str,
        enabled: bool = True,
        timeout: float = 10.0,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        """初始化 Webhook 通知器。

        Args:
            webhook_url: Webhook URL。
            enabled: 是否启用。
            timeout: 超时时间。
            headers: 自定义请求头。
        """
        super().__init__(name="webhook", enabled=enabled)
        self.webhook_url = webhook_url
        self.timeout = timeout
        self.headers = headers or {"Content-Type": "application/json"}

    def send(self, alert: Alert) -> bool:
        """发送 Webhook 通知。"""
        if not self.enabled or not self.webhook_url:
            return False
        try:
            with self._lock:
                self.send_count += 1
            payload = json.dumps(alert.to_dict(), ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                self.webhook_url,
                data=payload,
                method="POST",
            )
            for key, value in self.headers.items():
                req.add_header(key, value)
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return response.getcode() < 400
        except Exception as e:
            with self._lock:
                self.fail_count += 1
            _logger.warning("Webhook 通知发送失败: %s", e)
            return False


class EmailNotifier(Notifier):
    """邮件通知器。

    通过 SMTP 发送告警邮件。
    """

    def __init__(
        self,
        smtp_host: str = "",
        smtp_port: int = 25,
        smtp_user: str = "",
        smtp_password: str = "",
        from_addr: str = "",
        to_addrs: Optional[List[str]] = None,
        use_tls: bool = False,
        enabled: bool = True,
    ) -> None:
        """初始化邮件通知器。

        Args:
            smtp_host: SMTP 服务器地址。
            smtp_port: SMTP 端口。
            smtp_user: SMTP 用户名。
            smtp_password: SMTP 密码。
            from_addr: 发件人地址。
            to_addrs: 收件人地址列表。
            use_tls: 是否使用 TLS。
            enabled: 是否启用。
        """
        super().__init__(name="email", enabled=enabled)
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_addr = from_addr
        self.to_addrs = to_addrs or []
        self.use_tls = use_tls

    def send(self, alert: Alert) -> bool:
        """发送邮件通知。"""
        if not self.enabled or not self.smtp_host or not self.to_addrs:
            return False
        try:
            with self._lock:
                self.send_count += 1
            # 构建邮件
            msg = MIMEMultipart("alternative")
            msg["From"] = self.from_addr
            msg["To"] = ", ".join(self.to_addrs)
            msg["Subject"] = f"[{alert.level.name}] {alert.title}"
            # 纯文本内容
            text_content = (
                f"告警标题: {alert.title}\n"
                f"告警级别: {ALERT_LEVEL_NAMES.get(alert.level, '未知')}\n"
                f"告警来源: {alert.source}\n"
                f"告警消息: {alert.message}\n"
                f"告警时间: {alert.timestamp}\n"
                f"告警状态: {ALERT_STATE_NAMES.get(alert.state, '未知')}\n"
                f"告警 ID: {alert.alert_id}\n"
            )
            msg.attach(MIMEText(text_content, "plain", "utf-8"))
            # HTML 内容
            color = ALERT_LEVEL_COLORS.get(alert.level, "#666666")
            html_content = f"""
            <html><body>
            <div style="border-left: 4px solid {color}; padding: 10px;">
                <h2 style="color: {color};">{alert.title}</h2>
                <table style="border-collapse: collapse;">
                    <tr><td style="padding: 5px;">级别</td><td style="padding: 5px;">
                        <b>{ALERT_LEVEL_NAMES.get(alert.level, '未知')}</b></td></tr>
                    <tr><td style="padding: 5px;">来源</td><td style="padding: 5px;">{alert.source}</td></tr>
                    <tr><td style="padding: 5px;">消息</td><td style="padding: 5px;">{alert.message}</td></tr>
                    <tr><td style="padding: 5px;">时间</td><td style="padding: 5px;">{alert.timestamp}</td></tr>
                    <tr><td style="padding: 5px;">状态</td><td style="padding: 5px;">
                        {ALERT_STATE_NAMES.get(alert.state, '未知')}</td></tr>
                    <tr><td style="padding: 5px;">ID</td><td style="padding: 5px;">{alert.alert_id}</td></tr>
                </table>
            </div>
            </body></html>
            """
            msg.attach(MIMEText(html_content, "html", "utf-8"))
            # 发送邮件
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
                if self.use_tls:
                    server.starttls()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.from_addr, self.to_addrs, msg.as_string())
            return True
        except Exception as e:
            with self._lock:
                self.fail_count += 1
            _logger.warning("邮件通知发送失败: %s", e)
            return False


class SlackNotifier(Notifier):
    """Slack 通知器（模拟）。

    通过 Slack Webhook 发送告警消息（格式兼容 Slack Incoming Webhook）。
    若未配置 Webhook URL，则降级为日志输出。
    """

    def __init__(
        self,
        webhook_url: str = "",
        channel: str = "#alerts",
        enabled: bool = True,
    ) -> None:
        """初始化 Slack 通知器。

        Args:
            webhook_url: Slack Webhook URL。
            channel: 目标频道。
            enabled: 是否启用。
        """
        super().__init__(name="slack", enabled=enabled)
        self.webhook_url = webhook_url
        self.channel = channel

    def send(self, alert: Alert) -> bool:
        """发送 Slack 通知。"""
        if not self.enabled:
            return False
        try:
            with self._lock:
                self.send_count += 1
            color = ALERT_LEVEL_COLORS.get(alert.level, "#666666")
            # 构建 Slack 消息格式
            payload = {
                "channel": self.channel,
                "attachments": [
                    {
                        "color": color,
                        "title": f"[{ALERT_LEVEL_NAMES.get(alert.level, '未知')}] {alert.title}",
                        "text": alert.message,
                        "fields": [
                            {"title": "来源", "value": alert.source, "short": True},
                            {"title": "状态", "value": ALERT_STATE_NAMES.get(alert.state, "未知"), "short": True},
                            {"title": "时间", "value": alert.timestamp, "short": True},
                            {"title": "ID", "value": alert.alert_id, "short": True},
                        ],
                        "footer": "ThesisMiner AlertManager",
                        "ts": int(_now_ts()),
                    }
                ],
            }
            if self.webhook_url:
                # 发送到 Slack Webhook
                data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                req = urllib.request.Request(
                    self.webhook_url,
                    data=data,
                    method="POST",
                )
                req.add_header("Content-Type", "application/json")
                with urllib.request.urlopen(req, timeout=10) as response:
                    return response.getcode() < 400
            else:
                # 降级：仅记录日志
                _logger.info(
                    "[Slack 模拟] #%s | %s | %s",
                    self.channel, alert.title, alert.message
                )
                return True
        except Exception as e:
            with self._lock:
                self.fail_count += 1
            _logger.warning("Slack 通知发送失败: %s", e)
            return False


# ===== 主类：告警管理器 =====

class AlertManager:
    """告警管理器。

    提供告警规则配置、告警生成、去重、聚合、抑制、分发与历史管理能力。

    线程安全说明：所有共享状态均使用锁保护，可在多线程环境使用。
    建议通过 get_instance() 获取全局单例。

    Attributes:
        dedup_window: 去重时间窗口（秒）。
        notifiers: 已注册的通知器列表。
    """

    # 单例实例
    _instance: Optional["AlertManager"] = None
    _instance_lock = threading.Lock()

    def __init__(
        self,
        dedup_window: float = DEFAULT_DEDUP_WINDOW,
        history_capacity: int = DEFAULT_HISTORY_CAPACITY,
    ) -> None:
        """初始化告警管理器。

        Args:
            dedup_window: 去重时间窗口（秒）。
            history_capacity: 历史记录容量。
        """
        self.dedup_window: float = dedup_window
        self.history_capacity: int = history_capacity
        # 告警规则
        self._rules: Dict[str, AlertRule] = {}
        self._rules_lock = threading.Lock()
        # 活跃告警（未恢复）
        self._active_alerts: Dict[str, Alert] = {}
        self._active_lock = threading.Lock()
        # 告警历史
        self._history: Deque[Alert] = deque(maxlen=history_capacity)
        self._history_lock = threading.Lock()
        # 去重缓存：fingerprint -> 最近告警时间
        self._dedup_cache: Dict[str, float] = {}
        self._dedup_lock = threading.Lock()
        # 抑制规则：source -> 抑制到期时间
        self._suppressions: Dict[str, float] = {}
        self._suppression_lock = threading.Lock()
        # 通知器列表
        self._notifiers: List[Notifier] = []
        self._notifiers_lock = threading.Lock()
        # 级别过滤：仅发送此级别及以上的告警
        self._min_notify_level: AlertLevel = AlertLevel.INFO
        # 初始化数据库
        self._init_db()
        # 注册默认通知器（日志通知器始终启用）
        self.add_notifier(LogNotifier(enabled=True))
        _logger.info(
            "AlertManager 初始化完成，去重窗口=%.0fs，历史容量=%d",
            self.dedup_window, self.history_capacity,
        )

    @classmethod
    def get_instance(cls) -> "AlertManager":
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
                # 告警表
                conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {ALERTS_TABLE} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        alert_id TEXT UNIQUE NOT NULL,
                        title TEXT NOT NULL,
                        message TEXT,
                        level TEXT NOT NULL,
                        source TEXT,
                        state TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        resolved_at TEXT,
                        labels TEXT,
                        details TEXT,
                        duration_seconds REAL,
                        notification_sent INTEGER DEFAULT 0,
                        fingerprint TEXT
                    )
                """)
                # 告警规则表
                conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {ALERT_RULES_TABLE} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        metric TEXT NOT NULL,
                        operator TEXT NOT NULL,
                        threshold REAL NOT NULL,
                        level TEXT NOT NULL,
                        duration REAL,
                        description TEXT,
                        enabled INTEGER DEFAULT 1,
                        labels TEXT,
                        cooldown REAL,
                        last_triggered REAL
                    )
                """)
                # 创建索引
                conn.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{ALERTS_TABLE}_ts "
                    f"ON {ALERTS_TABLE}(timestamp)"
                )
                conn.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{ALERTS_TABLE}_source "
                    f"ON {ALERTS_TABLE}(source)"
                )
                conn.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{ALERTS_TABLE}_level "
                    f"ON {ALERTS_TABLE}(level)"
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as e:  # pragma: no cover
            _logger.warning("初始化告警数据库表失败: %s", e)

    # ===== 规则管理 =====

    def add_rule(self, rule: AlertRule) -> None:
        """添加告警规则。

        Args:
            rule: 告警规则对象。
        """
        with self._rules_lock:
            self._rules[rule.name] = rule
        # 持久化
        self._persist_rule(rule)
        _logger.info("添加告警规则: %s (指标=%s, 阈值=%s%s)", rule.name, rule.metric, rule.operator, rule.threshold)

    def remove_rule(self, name: str) -> bool:
        """移除告警规则。"""
        with self._rules_lock:
            if name in self._rules:
                del self._rules[name]
                _logger.info("移除告警规则: %s", name)
                return True
            return False

    def get_rule(self, name: str) -> Optional[AlertRule]:
        """获取告警规则。"""
        with self._rules_lock:
            return self._rules.get(name)

    def get_all_rules(self) -> List[AlertRule]:
        """获取所有告警规则。"""
        with self._rules_lock:
            return list(self._rules.values())

    def enable_rule(self, name: str) -> bool:
        """启用规则。"""
        with self._rules_lock:
            if name in self._rules:
                self._rules[name].enabled = True
                return True
            return False

    def disable_rule(self, name: str) -> bool:
        """禁用规则。"""
        with self._rules_lock:
            if name in self._rules:
                self._rules[name].enabled = False
                return True
            return False

    def _persist_rule(self, rule: AlertRule) -> None:
        """持久化规则到数据库。"""
        try:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            try:
                conn.execute(
                    f"INSERT OR REPLACE INTO {ALERT_RULES_TABLE} "
                    f"(name, metric, operator, threshold, level, duration, description, "
                    f"enabled, labels, cooldown, last_triggered) "
                    f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        rule.name,
                        rule.metric,
                        rule.operator,
                        rule.threshold,
                        rule.level.name,
                        rule.duration,
                        rule.description,
                        1 if rule.enabled else 0,
                        json.dumps(rule.labels, ensure_ascii=False),
                        rule.cooldown,
                        rule.last_triggered,
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as e:  # pragma: no cover
            _logger.debug("持久化告警规则失败: %s", e)

    # ===== 规则评估 =====

    def evaluate(self, metrics: Dict[str, float]) -> List[Alert]:
        """评估所有规则。

        根据传入的指标数据，评估所有告警规则，生成告警。

        Args:
            metrics: 指标名到值的映射。

        Returns:
            触发的告警列表。
        """
        triggered: List[Alert] = []
        with self._rules_lock:
            rules = list(self._rules.values())
        for rule in rules:
            if not rule.enabled:
                continue
            value = metrics.get(rule.metric)
            if value is None:
                continue
            # 评估规则
            if rule.evaluate(value):
                # 检查冷却期
                if rule.is_in_cooldown():
                    continue
                # 创建告警
                alert = Alert(
                    title=f"{rule.name}: {rule.metric} {rule.operator} {rule.threshold}",
                    message=f"指标 {rule.metric} 当前值为 {value}，"
                            f"触发条件 {rule.operator} {rule.threshold}",
                    level=rule.level,
                    source=rule.metric,
                    labels=rule.labels.copy(),
                    details={
                        "rule_name": rule.name,
                        "metric": rule.metric,
                        "current_value": value,
                        "threshold": rule.threshold,
                        "operator": rule.operator,
                    },
                )
                # 更新规则触发时间
                rule.last_triggered = _now_ts()
                # 发送告警
                self.notify(alert)
                triggered.append(alert)
        return triggered

    # ===== 告警生成与通知 =====

    def notify(self, alert: Alert) -> bool:
        """发送告警通知。

        处理去重、抑制、分发到各通知渠道。

        Args:
            alert: 告警对象。

        Returns:
            是否成功发送（至少一个通知器成功）。
        """
        # 检查抑制
        if self._is_suppressed(alert.source):
            alert.state = ALERT_STATE_SUPPRESSED
            _logger.debug("告警被抑制: %s", alert.title)
            self._record_history(alert)
            return False
        # 去重检查
        if self._is_duplicate(alert):
            _logger.debug("告警被去重: %s", alert.title)
            return False
        # 级别过滤
        if alert.level < self._min_notify_level:
            _logger.debug("告警级别低于阈值: %s", alert.title)
            self._record_history(alert)
            return False
        # 记录活跃告警
        with self._active_lock:
            self._active_alerts[alert.alert_id] = alert
        # 分发到通知器
        success = False
        with self._notifiers_lock:
            notifiers = list(self._notifiers)
        for notifier in notifiers:
            try:
                if notifier.send(alert):
                    success = True
            except Exception as e:  # pragma: no cover
                _logger.error("通知器 %s 发送异常: %s", notifier.name, e)
        alert.notification_sent = success
        # 记录历史
        self._record_history(alert)
        # 持久化
        self._persist_alert(alert)
        return success

    def resolve(self, alert_id: str, message: str = "") -> bool:
        """恢复告警。

        Args:
            alert_id: 告警 ID。
            message: 恢复消息。

        Returns:
            是否成功恢复。
        """
        with self._active_lock:
            alert = self._active_alerts.pop(alert_id, None)
        if alert is None:
            return False
        alert.state = ALERT_STATE_RESOLVED
        alert.resolved_at = _iso_now()
        # 计算持续时长
        try:
            started = datetime.fromisoformat(alert.timestamp)
            alert.duration_seconds = (datetime.now(tz=timezone.utc) - started).total_seconds()
        except Exception:  # pragma: no cover
            pass
        # 发送恢复通知
        if message:
            alert.message = f"[已恢复] {message}"
        else:
            alert.message = f"[已恢复] {alert.message}"
        # 分发恢复通知
        with self._notifiers_lock:
            notifiers = list(self._notifiers)
        for notifier in notifiers:
            try:
                notifier.send(alert)
            except Exception as e:  # pragma: no cover
                _logger.error("恢复通知发送异常: %s", e)
        # 记录历史
        self._record_history(alert)
        # 持久化
        self._persist_alert(alert)
        _logger.info("告警已恢复: %s (持续 %s)", alert.title, _format_duration(alert.duration_seconds))
        return True

    def resolve_by_source(self, source: str, message: str = "") -> int:
        """按来源恢复所有活跃告警。

        Args:
            source: 告警来源。
            message: 恢复消息。

        Returns:
            恢复的告警数。
        """
        count = 0
        with self._active_lock:
            alert_ids = [
                aid for aid, alert in self._active_alerts.items()
                if alert.source == source
            ]
        for alert_id in alert_ids:
            if self.resolve(alert_id, message):
                count += 1
        return count

    # ===== 去重 =====

    def _is_duplicate(self, alert: Alert) -> bool:
        """检查告警是否为重复。

        在去重时间窗口内，相同指纹的告警视为重复。

        Args:
            alert: 待检查的告警。

        Returns:
            是否为重复。
        """
        now = _now_ts()
        with self._dedup_lock:
            # 清理过期记录
            expired = [
                fp for fp, ts in self._dedup_cache.items()
                if now - ts > self.dedup_window
            ]
            for fp in expired:
                del self._dedup_cache[fp]
            # 检查重复
            if alert.fingerprint in self._dedup_cache:
                last_time = self._dedup_cache[alert.fingerprint]
                if now - last_time < self.dedup_window:
                    return True
            # 记录
            self._dedup_cache[alert.fingerprint] = now
            return False

    # ===== 抑制 =====

    def suppress(
        self,
        source: str,
        duration: float = DEFAULT_SUPPRESSION_DURATION,
    ) -> None:
        """抑制指定来源的告警。

        Args:
            source: 告警来源。
            duration: 抑制时长（秒）。
        """
        with self._suppression_lock:
            self._suppressions[source] = _now_ts() + duration
        _logger.info("抑制告警来源: %s，时长 %s", source, _format_duration(duration))

    def unsuppress(self, source: str) -> bool:
        """取消抑制。"""
        with self._suppression_lock:
            if source in self._suppressions:
                del self._suppressions[source]
                _logger.info("取消抑制: %s", source)
                return True
            return False

    def _is_suppressed(self, source: str) -> bool:
        """检查来源是否被抑制。"""
        with self._suppression_lock:
            if source not in self._suppressions:
                return False
            if _now_ts() > self._suppressions[source]:
                del self._suppressions[source]
                return False
            return True

    # ===== 通知器管理 =====

    def add_notifier(self, notifier: Notifier) -> None:
        """添加通知器。"""
        with self._notifiers_lock:
            self._notifiers.append(notifier)
        _logger.info("添加通知器: %s", notifier.name)

    def remove_notifier(self, name: str) -> bool:
        """移除通知器。"""
        with self._notifiers_lock:
            for i, notifier in enumerate(self._notifiers):
                if notifier.name == name:
                    self._notifiers.pop(i)
                    _logger.info("移除通知器: %s", name)
                    return True
            return False

    def get_notifiers(self) -> List[Notifier]:
        """获取所有通知器。"""
        with self._notifiers_lock:
            return list(self._notifiers)

    def set_min_notify_level(self, level: AlertLevel) -> None:
        """设置最小通知级别。"""
        self._min_notify_level = level
        _logger.info("设置最小通知级别: %s", level.name)

    # ===== 历史与统计 =====

    def _record_history(self, alert: Alert) -> None:
        """记录告警到历史。"""
        with self._history_lock:
            self._history.append(alert)

    def _persist_alert(self, alert: Alert) -> None:
        """持久化告警到数据库。"""
        try:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            try:
                conn.execute(
                    f"INSERT OR REPLACE INTO {ALERTS_TABLE} "
                    f"(alert_id, title, message, level, source, state, timestamp, "
                    f"resolved_at, labels, details, duration_seconds, notification_sent, fingerprint) "
                    f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        alert.alert_id,
                        alert.title,
                        alert.message,
                        alert.level.name,
                        alert.source,
                        alert.state,
                        alert.timestamp,
                        alert.resolved_at,
                        json.dumps(alert.labels, ensure_ascii=False),
                        json.dumps(alert.details, ensure_ascii=False),
                        alert.duration_seconds,
                        1 if alert.notification_sent else 0,
                        alert.fingerprint,
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as e:  # pragma: no cover
            _logger.debug("持久化告警失败: %s", e)

    def get_active_alerts(self) -> List[Alert]:
        """获取所有活跃告警。"""
        with self._active_lock:
            return list(self._active_alerts.values())

    def get_history(
        self,
        level: Optional[AlertLevel] = None,
        source: Optional[str] = None,
        limit: int = 100,
    ) -> List[Alert]:
        """获取告警历史。

        Args:
            level: 按级别过滤。
            source: 按来源过滤。
            limit: 返回数量。

        Returns:
            告警列表。
        """
        try:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            try:
                query = f"SELECT * FROM {ALERTS_TABLE}"
                conditions: List[str] = []
                params: List[Any] = []
                if level is not None:
                    conditions.append("level = ?")
                    params.append(level.name)
                if source is not None:
                    conditions.append("source = ?")
                    params.append(source)
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                alerts: List[Alert] = []
                for row in rows:
                    alert = Alert(
                        alert_id=row["alert_id"],
                        title=row["title"],
                        message=row["message"] or "",
                        level=AlertLevel[row["level"]],
                        source=row["source"] or "",
                        state=row["state"],
                        timestamp=row["timestamp"],
                        resolved_at=row["resolved_at"],
                        labels=json.loads(row["labels"]) if row["labels"] else {},
                        details=json.loads(row["details"]) if row["details"] else {},
                        duration_seconds=row["duration_seconds"] or 0.0,
                        notification_sent=bool(row["notification_sent"]),
                        fingerprint=row["fingerprint"] or "",
                    )
                    alerts.append(alert)
                return alerts
            finally:
                conn.close()
        except Exception as e:  # pragma: no cover
            _logger.warning("获取告警历史失败: %s", e)
            return []

    def get_statistics(self, hours: int = 24) -> AlertStatistics:
        """获取告警统计。

        Args:
            hours: 统计时间范围（小时）。

        Returns:
            告警统计对象。
        """
        period_end = datetime.now(tz=timezone.utc)
        period_start = period_end - timedelta(hours=hours)
        stats = AlertStatistics(
            period_start=period_start.isoformat(),
            period_end=period_end.isoformat(),
        )
        # 从数据库查询
        try:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            try:
                query = (
                    f"SELECT * FROM {ALERTS_TABLE} "
                    f"WHERE timestamp >= ? ORDER BY timestamp DESC"
                )
                cursor = conn.execute(query, (period_start.isoformat(),))
                rows = cursor.fetchall()
                # 统计
                resolution_times: List[float] = []
                for row in rows:
                    stats.total += 1
                    level = row["level"]
                    stats.by_level[level] = stats.by_level.get(level, 0) + 1
                    source = row["source"] or "unknown"
                    stats.by_source[source] = stats.by_source.get(source, 0) + 1
                    state = row["state"]
                    stats.by_state[state] = stats.by_state.get(state, 0) + 1
                    if state == ALERT_STATE_RESOLVED:
                        stats.resolved_count += 1
                        if row["duration_seconds"]:
                            resolution_times.append(row["duration_seconds"])
                # 平均恢复时间
                if resolution_times:
                    stats.avg_resolution_time = sum(resolution_times) / len(resolution_times)
                # 最频繁来源
                stats.top_sources = sorted(
                    stats.by_source.items(), key=lambda x: x[1], reverse=True
                )[:10]
            finally:
                conn.close()
        except Exception as e:  # pragma: no cover
            _logger.warning("获取告警统计失败: %s", e)
        return stats

    def analyze_trend(self, hours: int = 24) -> Dict[str, Any]:
        """分析告警趋势。

        Args:
            hours: 分析时间范围（小时）。

        Returns:
            趋势分析结果。
        """
        stats = self.get_statistics(hours=hours)
        # 计算趋势
        trend: Dict[str, Any] = {
            "period_hours": hours,
            "total_alerts": stats.total,
            "by_level": stats.by_level,
            "by_source": stats.by_source,
            "by_state": stats.by_state,
            "resolved_rate": (
                stats.resolved_count / stats.total if stats.total > 0 else 0.0
            ),
            "avg_resolution_time": round(stats.avg_resolution_time, 2),
            "top_sources": [
                {"source": s, "count": c} for s, c in stats.top_sources
            ],
        }
        # 判断趋势方向
        if stats.total == 0:
            trend["direction"] = "stable"
            trend["assessment"] = "无告警"
        elif stats.resolved_count / max(stats.total, 1) > 0.9:
            trend["direction"] = "improving"
            trend["assessment"] = "告警恢复率高，系统趋于稳定"
        elif stats.by_level.get(AlertLevel.CRITICAL.name, 0) > 0:
            trend["direction"] = "degrading"
            trend["assessment"] = "存在严重告警，需要关注"
        else:
            trend["direction"] = "stable"
            trend["assessment"] = "告警水平正常"
        return trend

    # ===== 批量操作 =====

    def batch_notify(self, alerts: List[Alert]) -> int:
        """批量发送告警通知。

        Args:
            alerts: 告警列表。

        Returns:
            成功发送的数量。
        """
        success_count = 0
        for alert in alerts:
            if self.notify(alert):
                success_count += 1
        return success_count

    def clear_active_alerts(self) -> int:
        """清除所有活跃告警（标记为恢复）。"""
        with self._active_lock:
            count = len(self._active_alerts)
            self._active_alerts.clear()
        _logger.info("清除所有活跃告警: %d 条", count)
        return count

    # ===== 通知模板 =====

    def format_alert_text(self, alert: Alert) -> str:
        """格式化告警为纯文本。

        Args:
            alert: 告警对象。

        Returns:
            格式化的文本。
        """
        lines = [
            f"{'=' * 50}",
            f"告警标题: {alert.title}",
            f"告警级别: {ALERT_LEVEL_NAMES.get(alert.level, '未知')}",
            f"告警来源: {alert.source}",
            f"告警状态: {ALERT_STATE_NAMES.get(alert.state, '未知')}",
            f"告警时间: {alert.timestamp}",
            f"告警消息: {alert.message}",
            f"告警 ID: {alert.alert_id}",
        ]
        if alert.resolved_at:
            lines.append(f"恢复时间: {alert.resolved_at}")
            lines.append(f"持续时长: {_format_duration(alert.duration_seconds)}")
        if alert.labels:
            lines.append(f"标签: {', '.join(f'{k}={v}' for k, v in alert.labels.items())}")
        if alert.details:
            lines.append("详细信息:")
            for key, value in alert.details.items():
                lines.append(f"  {key}: {value}")
        lines.append(f"{'=' * 50}")
        return "\n".join(lines)

    def format_alert_html(self, alert: Alert) -> str:
        """格式化告警为 HTML。

        Args:
            alert: 告警对象。

        Returns:
            格式化的 HTML。
        """
        color = ALERT_LEVEL_COLORS.get(alert.level, "#666666")
        html_parts = [
            f'<div style="border: 1px solid {color}; border-left: 4px solid {color}; padding: 15px; margin: 10px 0;">',
            f'<h3 style="color: {color}; margin: 0 0 10px 0;">{alert.title}</h3>',
            f'<table style="border-collapse: collapse; width: 100%;">',
            f'<tr><td style="padding: 5px; width: 100px;"><b>级别</b></td><td style="padding: 5px;">{ALERT_LEVEL_NAMES.get(alert.level, "未知")}</td></tr>',
            f'<tr><td style="padding: 5px;"><b>来源</b></td><td style="padding: 5px;">{alert.source}</td></tr>',
            f'<tr><td style="padding: 5px;"><b>状态</b></td><td style="padding: 5px;">{ALERT_STATE_NAMES.get(alert.state, "未知")}</td></tr>',
            f'<tr><td style="padding: 5px;"><b>时间</b></td><td style="padding: 5px;">{alert.timestamp}</td></tr>',
            f'<tr><td style="padding: 5px;"><b>消息</b></td><td style="padding: 5px;">{alert.message}</td></tr>',
        ]
        if alert.resolved_at:
            html_parts.append(
                f'<tr><td style="padding: 5px;"><b>恢复时间</b></td><td style="padding: 5px;">{alert.resolved_at}</td></tr>'
            )
            html_parts.append(
                f'<tr><td style="padding: 5px;"><b>持续时长</b></td><td style="padding: 5px;">{_format_duration(alert.duration_seconds)}</td></tr>'
            )
        html_parts.append("</table>")
        if alert.details:
            html_parts.append('<h4 style="margin: 10px 0 5px 0;">详细信息</h4><ul>')
            for key, value in alert.details.items():
                html_parts.append(f"<li><b>{key}</b>: {value}</li>")
            html_parts.append("</ul>")
        html_parts.append("</div>")
        return "".join(html_parts)

    # ===== 清理 =====

    def cleanup_history(self, days: int = 30) -> int:
        """清理历史告警。

        Args:
            days: 保留天数。

        Returns:
            删除的记录数。
        """
        cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=days)).isoformat()
        try:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            try:
                cursor = conn.execute(
                    f"DELETE FROM {ALERTS_TABLE} WHERE timestamp < ?",
                    (cutoff,),
                )
                deleted = cursor.rowcount
                conn.commit()
                _logger.info("清理告警历史: 删除 %d 条（%d 天前）", deleted, days)
                return deleted
            finally:
                conn.close()
        except Exception as e:  # pragma: no cover
            _logger.warning("清理告警历史失败: %s", e)
            return 0


# ===== 模块级单例访问 =====

def get_alert_manager() -> AlertManager:
    """获取全局告警管理器单例。"""
    return AlertManager.get_instance()


def send_alert(
    title: str,
    message: str,
    level: AlertLevel = AlertLevel.WARN,
    source: str = "",
) -> bool:
    """模块级发送告警便捷函数。"""
    alert = Alert(title=title, message=message, level=level, source=source)
    return get_alert_manager().notify(alert)


def add_alert_rule(
    name: str,
    metric: str,
    operator: str,
    threshold: float,
    level: AlertLevel = AlertLevel.WARN,
) -> None:
    """模块级添加告警规则便捷函数。"""
    rule = AlertRule(
        name=name, metric=metric, operator=operator,
        threshold=threshold, level=level,
    )
    get_alert_manager().add_rule(rule)
