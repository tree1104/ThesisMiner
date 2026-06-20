"""审计日志器模块

提供安全审计日志的记录、存储、检索与管理能力，包括：
    - 用户操作日志（登录/登出/创建/修改/删除）
    - API 调用日志（请求/响应/参数/耗时）
    - 数据变更日志（变更前/变更后/变更类型）
    - 认证日志（成功/失败/锁定/解锁）
    - 授权日志（权限检查/角色变更）
    - 配置变更日志（系统配置/规则变更）
    - 日志结构化（JSON 格式，便于检索与分析）
    - 日志索引（按时间/用户/操作类型/资源等多维索引）
    - 日志检索（支持多条件组合查询）
    - 日志归档（按时间归档到压缩文件）
    - 日志清理（按保留策略自动清理）
    - 日志完整性保护（链式哈希防篡改）
    - 合规报告生成（满足审计合规要求）
    - 审计追溯（操作链路还原）

所有审计日志写入 SQLite 持久化存储，并支持文件归档。
采用链式哈希保证日志完整性，防止篡改。

典型用法：
    logger = AuditLogger()
    logger.log_user_action(user_id="u001", action="login", resource="system",
                           result="success", ip="192.168.1.1")
    logger.log_api_call(user_id="u001", method="POST", path="/api/proposals",
                        status_code=201, duration_ms=150)
    logger.log_data_change(user_id="u001", table="proposals", record_id="p001",
                           action="update", before={"title": "old"}, after={"title": "new"})
    report = logger.generate_compliance_report(start_date, end_date)
    results = logger.search(user_id="u001", action="login", start_time=...)
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import shutil
import sqlite3
import threading
import time
from collections import deque, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Union

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

# 审计日志表名
AUDIT_LOGS_TABLE = "audit_logs"
AUDIT_ARCHIVE_TABLE = "audit_archive"

# 默认归档目录
DEFAULT_ARCHIVE_DIR = "data/audit_archive"

# 默认保留天数
DEFAULT_RETENTION_DAYS = 90

# 默认归档阈值（条数）
DEFAULT_ARCHIVE_THRESHOLD = 10000

# 默认批量写入大小
DEFAULT_BATCH_SIZE = 100

# 默认最大检索结果数
DEFAULT_SEARCH_LIMIT = 1000

# 日志完整性校验链长度
DEFAULT_CHAIN_LENGTH = 1000


class AuditEventType(str, Enum):
    """审计事件类型枚举。"""

    # 用户操作
    USER_LOGIN = "user_login"                # 用户登录
    USER_LOGOUT = "user_logout"              # 用户登出
    USER_REGISTER = "user_register"          # 用户注册
    USER_DELETE = "user_delete"              # 用户删除
    USER_UPDATE = "user_update"              # 用户信息修改

    # 认证授权
    AUTH_SUCCESS = "auth_success"            # 认证成功
    AUTH_FAILURE = "auth_failure"            # 认证失败
    AUTH_LOCKED = "auth_locked"              # 账户锁定
    AUTH_UNLOCKED = "auth_unlocked"          # 账户解锁
    PERMISSION_GRANTED = "permission_granted"  # 权限授予
    PERMISSION_DENIED = "permission_denied"  # 权限拒绝
    ROLE_ASSIGNED = "role_assigned"          # 角色分配
    ROLE_REVOKED = "role_revoked"            # 角色撤销

    # API 调用
    API_CALL = "api_call"                    # API 调用
    API_ERROR = "api_error"                  # API 错误

    # 数据操作
    DATA_CREATE = "data_create"              # 数据创建
    DATA_READ = "data_read"                  # 数据读取
    DATA_UPDATE = "data_update"              # 数据更新
    DATA_DELETE = "data_delete"              # 数据删除
    DATA_EXPORT = "data_export"              # 数据导出
    DATA_IMPORT = "data_import"              # 数据导入

    # 配置变更
    CONFIG_CHANGE = "config_change"          # 配置变更
    RULE_CHANGE = "rule_change"              # 规则变更
    SYSTEM_UPDATE = "system_update"          # 系统更新

    # 其他
    CUSTOM = "custom"                        # 自定义事件


# 事件类型中文映射
EVENT_TYPE_NAMES = {
    AuditEventType.USER_LOGIN: "用户登录",
    AuditEventType.USER_LOGOUT: "用户登出",
    AuditEventType.USER_REGISTER: "用户注册",
    AuditEventType.USER_DELETE: "用户删除",
    AuditEventType.USER_UPDATE: "用户信息修改",
    AuditEventType.AUTH_SUCCESS: "认证成功",
    AuditEventType.AUTH_FAILURE: "认证失败",
    AuditEventType.AUTH_LOCKED: "账户锁定",
    AuditEventType.AUTH_UNLOCKED: "账户解锁",
    AuditEventType.PERMISSION_GRANTED: "权限授予",
    AuditEventType.PERMISSION_DENIED: "权限拒绝",
    AuditEventType.ROLE_ASSIGNED: "角色分配",
    AuditEventType.ROLE_REVOKED: "角色撤销",
    AuditEventType.API_CALL: "API调用",
    AuditEventType.API_ERROR: "API错误",
    AuditEventType.DATA_CREATE: "数据创建",
    AuditEventType.DATA_READ: "数据读取",
    AuditEventType.DATA_UPDATE: "数据更新",
    AuditEventType.DATA_DELETE: "数据删除",
    AuditEventType.DATA_EXPORT: "数据导出",
    AuditEventType.DATA_IMPORT: "数据导入",
    AuditEventType.CONFIG_CHANGE: "配置变更",
    AuditEventType.RULE_CHANGE: "规则变更",
    AuditEventType.SYSTEM_UPDATE: "系统更新",
    AuditEventType.CUSTOM: "自定义事件",
}

# 操作结果
RESULT_SUCCESS = "success"
RESULT_FAILURE = "failure"
RESULT_DENIED = "denied"
RESULT_ERROR = "error"

# 操作结果中文映射
RESULT_NAMES = {
    RESULT_SUCCESS: "成功",
    RESULT_FAILURE: "失败",
    RESULT_DENIED: "拒绝",
    RESULT_ERROR: "错误",
}

# 严重级别
SEVERITY_INFO = "info"
SEVERITY_WARN = "warn"
SEVERITY_ERROR = "error"
SEVERITY_CRITICAL = "critical"

# 严重级别中文映射
SEVERITY_NAMES = {
    SEVERITY_INFO: "信息",
    SEVERITY_WARN: "警告",
    SEVERITY_ERROR: "错误",
    SEVERITY_CRITICAL: "严重",
}


# ===== 工具函数 =====

def _now_ts() -> float:
    """获取当前 UTC 时间戳。"""
    return time.time()


def _iso_now() -> str:
    """获取当前 UTC 时间的 ISO8601 字符串。"""
    return datetime.now(tz=timezone.utc).isoformat()


def _safe_str(value: Any, max_length: int = 1000) -> str:
    """安全转换为字符串，并截断超长内容。"""
    if value is None:
        return ""
    try:
        s = str(value)
        if len(s) > max_length:
            return s[:max_length] + "...[truncated]"
        return s
    except Exception:
        return ""


def _safe_json(value: Any, max_length: int = 5000) -> str:
    """安全转换为 JSON 字符串。"""
    try:
        s = json.dumps(value, ensure_ascii=False, default=str)
        if len(s) > max_length:
            return s[:max_length] + "...[truncated]"
        return s
    except Exception:
        return _safe_str(value, max_length)


def _hash_content(content: str) -> str:
    """计算内容的 SHA-256 哈希。"""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _mask_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """脱敏敏感数据。

    对密码、令牌、密钥等敏感字段进行掩码处理。

    Args:
        data: 原始数据字典。

    Returns:
        脱敏后的数据字典。
    """
    if not isinstance(data, dict):
        return data
    sensitive_keys = {
        "password", "passwd", "pwd", "secret", "token", "api_key",
        "apikey", "access_key", "secret_key", "private_key", "credential",
        "authorization", "auth", "cookie", "session_id", "ssn",
    }
    masked: Dict[str, Any] = {}
    for key, value in data.items():
        key_lower = key.lower()
        if key_lower in sensitive_keys or any(s in key_lower for s in sensitive_keys):
            # 掩码处理
            if isinstance(value, str) and len(value) > 4:
                masked[key] = value[:2] + "*" * (len(value) - 4) + value[-2:]
            else:
                masked[key] = "****"
        elif isinstance(value, dict):
            masked[key] = _mask_sensitive_data(value)
        else:
            masked[key] = value
    return masked


# ===== 数据类定义 =====

@dataclass
class AuditEvent:
    """审计事件。

    Attributes:
        event_id: 事件唯一 ID。
        event_type: 事件类型。
        timestamp: 事件时间戳。
        user_id: 操作用户 ID。
        username: 操作用户名。
        action: 操作动作。
        resource: 操作资源。
        resource_id: 资源 ID。
        result: 操作结果（success/failure/denied/error）。
        severity: 严重级别（info/warn/error/critical）。
        ip_address: 客户端 IP 地址。
        user_agent: 用户代理。
        session_id: 会话 ID。
        request_id: 请求 ID。
        details: 详细信息字典。
        before_state: 变更前状态。
        after_state: 变更后状态。
        duration_ms: 操作耗时（毫秒）。
        prev_hash: 前一条日志的哈希（用于链式完整性）。
        curr_hash: 当前日志的哈希。
    """
    event_id: str = ""
    event_type: str = AuditEventType.CUSTOM.value
    timestamp: str = field(default_factory=_iso_now)
    user_id: str = ""
    username: str = ""
    action: str = ""
    resource: str = ""
    resource_id: str = ""
    result: str = RESULT_SUCCESS
    severity: str = SEVERITY_INFO
    ip_address: str = ""
    user_agent: str = ""
    session_id: str = ""
    request_id: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    before_state: Optional[Dict[str, Any]] = None
    after_state: Optional[Dict[str, Any]] = None
    duration_ms: float = 0.0
    prev_hash: str = ""
    curr_hash: str = ""

    def __post_init__(self) -> None:
        if not self.event_id:
            # 生成唯一 ID：时间戳 + 随机数
            import uuid
            self.event_id = f"{int(_now_ts() * 1000000)}_{uuid.uuid4().hex[:12]}"

    def compute_hash(self, prev_hash: str = "") -> str:
        """计算当前事件的哈希值（用于链式完整性保护）。

        Args:
            prev_hash: 前一条事件的哈希。

        Returns:
            当前事件的哈希值。
        """
        self.prev_hash = prev_hash
        # 构建待哈希内容
        content_parts = [
            self.event_id,
            self.event_type,
            self.timestamp,
            self.user_id,
            self.action,
            self.resource,
            self.resource_id,
            self.result,
            str(self.details),
            str(self.before_state),
            str(self.after_state),
            self.prev_hash,
        ]
        content = "|".join(content_parts)
        self.curr_hash = _hash_content(content)
        return self.curr_hash

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典表示。"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "event_type_name": EVENT_TYPE_NAMES.get(AuditEventType(self.event_type), "自定义事件") if self.event_type in [e.value for e in AuditEventType] else "自定义事件",
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "username": self.username,
            "action": self.action,
            "resource": self.resource,
            "resource_id": self.resource_id,
            "result": self.result,
            "result_name": RESULT_NAMES.get(self.result, "未知"),
            "severity": self.severity,
            "severity_name": SEVERITY_NAMES.get(self.severity, "未知"),
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "session_id": self.session_id,
            "request_id": self.request_id,
            "details": self.details,
            "before_state": self.before_state,
            "after_state": self.after_state,
            "duration_ms": self.duration_ms,
            "prev_hash": self.prev_hash,
            "curr_hash": self.curr_hash,
        }

    def to_db_tuple(self) -> tuple:
        """转换为数据库插入元组。"""
        return (
            self.event_id,
            self.event_type,
            self.timestamp,
            self.user_id,
            self.username,
            self.action,
            self.resource,
            self.resource_id,
            self.result,
            self.severity,
            self.ip_address,
            self.user_agent,
            self.session_id,
            self.request_id,
            _safe_json(self.details),
            _safe_json(self.before_state),
            _safe_json(self.after_state),
            self.duration_ms,
            self.prev_hash,
            self.curr_hash,
        )


@dataclass
class ComplianceReport:
    """合规报告。

    Attributes:
        report_id: 报告 ID。
        period_start: 报告周期开始。
        period_end: 报告周期结束。
        total_events: 事件总数。
        by_type: 按类型统计。
        by_result: 按结果统计。
        by_severity: 按严重级别统计。
        by_user: 按用户统计。
        failed_auth_count: 认证失败次数。
        permission_denied_count: 权限拒绝次数。
        data_changes_count: 数据变更次数。
        config_changes_count: 配置变更次数。
        critical_events: 严重事件列表。
        integrity_verified: 完整性校验结果。
        generated_at: 报告生成时间。
    """
    report_id: str = ""
    period_start: str = ""
    period_end: str = ""
    total_events: int = 0
    by_type: Dict[str, int] = field(default_factory=dict)
    by_result: Dict[str, int] = field(default_factory=dict)
    by_severity: Dict[str, int] = field(default_factory=dict)
    by_user: Dict[str, int] = field(default_factory=dict)
    failed_auth_count: int = 0
    permission_denied_count: int = 0
    data_changes_count: int = 0
    config_changes_count: int = 0
    critical_events: List[Dict[str, Any]] = field(default_factory=list)
    integrity_verified: bool = False
    integrity_errors: List[str] = field(default_factory=list)
    generated_at: str = field(default_factory=_iso_now)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典表示。"""
        return {
            "report_id": self.report_id,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "total_events": self.total_events,
            "by_type": self.by_type,
            "by_result": self.by_result,
            "by_severity": self.by_severity,
            "by_user": dict(sorted(self.by_user.items(), key=lambda x: x[1], reverse=True)[:20]),
            "failed_auth_count": self.failed_auth_count,
            "permission_denied_count": self.permission_denied_count,
            "data_changes_count": self.data_changes_count,
            "config_changes_count": self.config_changes_count,
            "critical_events_count": len(self.critical_events),
            "critical_events": self.critical_events[:50],
            "integrity_verified": self.integrity_verified,
            "integrity_errors": self.integrity_errors,
            "generated_at": self.generated_at,
        }


@dataclass
class SearchFilter:
    """审计日志检索过滤器。

    Attributes:
        event_type: 事件类型。
        user_id: 用户 ID。
        username: 用户名。
        action: 操作动作。
        resource: 资源。
        resource_id: 资源 ID。
        result: 操作结果。
        severity: 严重级别。
        ip_address: IP 地址。
        session_id: 会话 ID。
        request_id: 请求 ID。
        start_time: 开始时间。
        end_time: 结束时间。
        keyword: 关键词（搜索 details 字段）。
        limit: 返回数量。
        offset: 偏移量。
        order_by: 排序字段。
        order_desc: 是否降序。
    """
    event_type: Optional[str] = None
    user_id: Optional[str] = None
    username: Optional[str] = None
    action: Optional[str] = None
    resource: Optional[str] = None
    resource_id: Optional[str] = None
    result: Optional[str] = None
    severity: Optional[str] = None
    ip_address: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    keyword: Optional[str] = None
    limit: int = DEFAULT_SEARCH_LIMIT
    offset: int = 0
    order_by: str = "timestamp"
    order_desc: bool = True

    def to_where_clause(self) -> Tuple[str, List[Any]]:
        """构建 SQL WHERE 子句。

        Returns:
            (WHERE 子句, 参数列表) 元组。
        """
        conditions: List[str] = []
        params: List[Any] = []
        if self.event_type:
            conditions.append("event_type = ?")
            params.append(self.event_type)
        if self.user_id:
            conditions.append("user_id = ?")
            params.append(self.user_id)
        if self.username:
            conditions.append("username = ?")
            params.append(self.username)
        if self.action:
            conditions.append("action LIKE ?")
            params.append(f"%{self.action}%")
        if self.resource:
            conditions.append("resource = ?")
            params.append(self.resource)
        if self.resource_id:
            conditions.append("resource_id = ?")
            params.append(self.resource_id)
        if self.result:
            conditions.append("result = ?")
            params.append(self.result)
        if self.severity:
            conditions.append("severity = ?")
            params.append(self.severity)
        if self.ip_address:
            conditions.append("ip_address = ?")
            params.append(self.ip_address)
        if self.session_id:
            conditions.append("session_id = ?")
            params.append(self.session_id)
        if self.request_id:
            conditions.append("request_id = ?")
            params.append(self.request_id)
        if self.start_time:
            conditions.append("timestamp >= ?")
            params.append(self.start_time)
        if self.end_time:
            conditions.append("timestamp <= ?")
            params.append(self.end_time)
        if self.keyword:
            conditions.append("details LIKE ?")
            params.append(f"%{self.keyword}%")
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        return where_clause, params


# ===== 主类：审计日志器 =====

class AuditLogger:
    """安全审计日志器。

    提供全面的审计日志记录、存储、检索与管理能力，支持合规报告生成
    与日志完整性保护。

    线程安全说明：所有共享状态均使用锁保护，可在多线程环境使用。
    建议通过 get_instance() 获取全局单例。

    Attributes:
        retention_days: 日志保留天数。
        archive_dir: 归档目录。
    """

    # 单例实例
    _instance: Optional["AuditLogger"] = None
    _instance_lock = threading.Lock()

    def __init__(
        self,
        retention_days: int = DEFAULT_RETENTION_DAYS,
        archive_dir: str = DEFAULT_ARCHIVE_DIR,
        enable_integrity: bool = True,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        """初始化审计日志器。

        Args:
            retention_days: 日志保留天数。
            archive_dir: 归档目录。
            enable_integrity: 是否启用完整性保护（链式哈希）。
            batch_size: 批量写入大小。
        """
        self.retention_days: int = retention_days
        self.archive_dir: str = archive_dir
        self.enable_integrity: bool = enable_integrity
        self.batch_size: int = batch_size
        # 批量写入缓冲
        self._batch_buffer: List[AuditEvent] = []
        self._batch_lock = threading.Lock()
        # 链式哈希：上一条日志的哈希
        self._last_hash: str = ""
        self._hash_lock = threading.Lock()
        # 统计计数器
        self._stats: Dict[str, int] = defaultdict(int)
        self._stats_lock = threading.Lock()
        # 初始化数据库
        self._init_db()
        # 初始化归档目录
        Path(archive_dir).mkdir(parents=True, exist_ok=True)
        # 加载最后一条日志的哈希
        self._load_last_hash()
        _logger.info(
            "AuditLogger 初始化完成，保留天数=%d，归档目录=%s，完整性保护=%s",
            self.retention_days, self.archive_dir, self.enable_integrity,
        )

    @classmethod
    def get_instance(cls) -> "AuditLogger":
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
                # 审计日志表
                conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {AUDIT_LOGS_TABLE} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id TEXT UNIQUE NOT NULL,
                        event_type TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        user_id TEXT,
                        username TEXT,
                        action TEXT,
                        resource TEXT,
                        resource_id TEXT,
                        result TEXT,
                        severity TEXT,
                        ip_address TEXT,
                        user_agent TEXT,
                        session_id TEXT,
                        request_id TEXT,
                        details TEXT,
                        before_state TEXT,
                        after_state TEXT,
                        duration_ms REAL,
                        prev_hash TEXT,
                        curr_hash TEXT
                    )
                """)
                # 创建索引
                conn.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{AUDIT_LOGS_TABLE}_ts "
                    f"ON {AUDIT_LOGS_TABLE}(timestamp)"
                )
                conn.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{AUDIT_LOGS_TABLE}_type "
                    f"ON {AUDIT_LOGS_TABLE}(event_type)"
                )
                conn.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{AUDIT_LOGS_TABLE}_user "
                    f"ON {AUDIT_LOGS_TABLE}(user_id)"
                )
                conn.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{AUDIT_LOGS_TABLE}_resource "
                    f"ON {AUDIT_LOGS_TABLE}(resource)"
                )
                conn.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{AUDIT_LOGS_TABLE}_result "
                    f"ON {AUDIT_LOGS_TABLE}(result)"
                )
                conn.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{AUDIT_LOGS_TABLE}_severity "
                    f"ON {AUDIT_LOGS_TABLE}(severity)"
                )
                conn.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{AUDIT_LOGS_TABLE}_session "
                    f"ON {AUDIT_LOGS_TABLE}(session_id)"
                )
                conn.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{AUDIT_LOGS_TABLE}_request "
                    f"ON {AUDIT_LOGS_TABLE}(request_id)"
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as e:  # pragma: no cover
            _logger.warning("初始化审计日志数据库表失败: %s", e)

    def _load_last_hash(self) -> None:
        """加载最后一条日志的哈希值。"""
        try:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            try:
                cursor = conn.execute(
                    f"SELECT curr_hash FROM {AUDIT_LOGS_TABLE} "
                    f"ORDER BY id DESC LIMIT 1"
                )
                row = cursor.fetchone()
                if row and row[0]:
                    with self._hash_lock:
                        self._last_hash = row[0]
                    _logger.debug("加载最后一条日志哈希: %s", self._last_hash[:16])
            finally:
                conn.close()
        except Exception as e:  # pragma: no cover
            _logger.debug("加载最后哈希失败: %s", e)

    # ===== 日志记录方法 =====

    def log(self, event: AuditEvent) -> bool:
        """记录审计事件。

        Args:
            event: 审计事件对象。

        Returns:
            是否记录成功。
        """
        # 脱敏处理
        if event.details:
            event.details = _mask_sensitive_data(event.details)
        if event.before_state:
            event.before_state = _mask_sensitive_data(event.before_state)
        if event.after_state:
            event.after_state = _mask_sensitive_data(event.after_state)
        # 计算完整性哈希
        if self.enable_integrity:
            with self._hash_lock:
                event.compute_hash(self._last_hash)
                self._last_hash = event.curr_hash
        # 写入数据库
        success = self._write_event(event)
        if success:
            with self._stats_lock:
                self._stats["total"] += 1
                self._stats[event.event_type] += 1
                self._stats[event.result] += 1
        return success

    def _write_event(self, event: AuditEvent) -> bool:
        """写入事件到数据库。"""
        try:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            try:
                conn.execute(
                    f"INSERT INTO {AUDIT_LOGS_TABLE} "
                    f"(event_id, event_type, timestamp, user_id, username, action, "
                    f"resource, resource_id, result, severity, ip_address, user_agent, "
                    f"session_id, request_id, details, before_state, after_state, "
                    f"duration_ms, prev_hash, curr_hash) "
                    f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    event.to_db_tuple(),
                )
                conn.commit()
                return True
            finally:
                conn.close()
        except sqlite3.IntegrityError:
            _logger.warning("审计事件已存在: %s", event.event_id)
            return False
        except Exception as e:  # pragma: no cover
            _logger.error("写入审计事件失败: %s", e)
            return False

    def log_user_action(
        self,
        user_id: str,
        action: str,
        resource: str = "",
        resource_id: str = "",
        result: str = RESULT_SUCCESS,
        ip_address: str = "",
        user_agent: str = "",
        session_id: str = "",
        details: Optional[Dict[str, Any]] = None,
        severity: str = SEVERITY_INFO,
    ) -> bool:
        """记录用户操作日志。

        Args:
            user_id: 用户 ID。
            action: 操作动作。
            resource: 操作资源。
            resource_id: 资源 ID。
            result: 操作结果。
            ip_address: IP 地址。
            user_agent: 用户代理。
            session_id: 会话 ID。
            details: 详细信息。
            severity: 严重级别。

        Returns:
            是否记录成功。
        """
        # 推断事件类型
        event_type = AuditEventType.CUSTOM
        action_lower = action.lower()
        if "login" in action_lower or "登录" in action:
            event_type = AuditEventType.USER_LOGIN
        elif "logout" in action_lower or "登出" in action:
            event_type = AuditEventType.USER_LOGOUT
        elif "register" in action_lower or "注册" in action:
            event_type = AuditEventType.USER_REGISTER
        elif "delete" in action_lower or "删除" in action:
            event_type = AuditEventType.DATA_DELETE if resource else AuditEventType.USER_DELETE
        elif "create" in action_lower or "创建" in action:
            event_type = AuditEventType.DATA_CREATE
        elif "update" in action_lower or "修改" in action or "更新" in action:
            event_type = AuditEventType.DATA_UPDATE
        elif "read" in action_lower or "查询" in action or "查看" in action:
            event_type = AuditEventType.DATA_READ
        event = AuditEvent(
            event_type=event_type.value,
            user_id=user_id,
            action=action,
            resource=resource,
            resource_id=resource_id,
            result=result,
            severity=severity,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            details=details or {},
        )
        return self.log(event)

    def log_auth(
        self,
        user_id: str,
        success: bool,
        ip_address: str = "",
        user_agent: str = "",
        details: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """记录认证日志。

        Args:
            user_id: 用户 ID。
            success: 是否认证成功。
            ip_address: IP 地址。
            user_agent: 用户代理。
            details: 详细信息。

        Returns:
            是否记录成功。
        """
        event_type = AuditEventType.AUTH_SUCCESS if success else AuditEventType.AUTH_FAILURE
        result = RESULT_SUCCESS if success else RESULT_FAILURE
        severity = SEVERITY_INFO if success else SEVERITY_WARN
        event = AuditEvent(
            event_type=event_type.value,
            user_id=user_id,
            action="authenticate",
            resource="auth",
            result=result,
            severity=severity,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or {},
        )
        return self.log(event)

    def log_permission(
        self,
        user_id: str,
        permission: str,
        granted: bool,
        resource: str = "",
        details: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """记录授权日志。

        Args:
            user_id: 用户 ID。
            permission: 权限名称。
            granted: 是否授权。
            resource: 资源。
            details: 详细信息。

        Returns:
            是否记录成功。
        """
        event_type = AuditEventType.PERMISSION_GRANTED if granted else AuditEventType.PERMISSION_DENIED
        result = RESULT_SUCCESS if granted else RESULT_DENIED
        severity = SEVERITY_INFO if granted else SEVERITY_WARN
        event = AuditEvent(
            event_type=event_type.value,
            user_id=user_id,
            action=f"check_permission:{permission}",
            resource=resource,
            result=result,
            severity=severity,
            details=details or {"permission": permission},
        )
        return self.log(event)

    def log_api_call(
        self,
        user_id: str,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float = 0.0,
        ip_address: str = "",
        user_agent: str = "",
        session_id: str = "",
        request_id: str = "",
        params: Optional[Dict[str, Any]] = None,
        response_size: int = 0,
    ) -> bool:
        """记录 API 调用日志。

        Args:
            user_id: 用户 ID。
            method: HTTP 方法。
            path: 请求路径。
            status_code: HTTP 状态码。
            duration_ms: 耗时（毫秒）。
            ip_address: IP 地址。
            user_agent: 用户代理。
            session_id: 会话 ID。
            request_id: 请求 ID。
            params: 请求参数。
            response_size: 响应大小。

        Returns:
            是否记录成功。
        """
        # 判断结果与严重级别
        if status_code < 400:
            result = RESULT_SUCCESS
            severity = SEVERITY_INFO
            event_type = AuditEventType.API_CALL
        elif status_code < 500:
            result = RESULT_DENIED
            severity = SEVERITY_WARN
            event_type = AuditEventType.API_CALL
        else:
            result = RESULT_ERROR
            severity = SEVERITY_ERROR
            event_type = AuditEventType.API_ERROR
        event = AuditEvent(
            event_type=event_type.value,
            user_id=user_id,
            action=f"{method} {path}",
            resource=path,
            result=result,
            severity=severity,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            request_id=request_id,
            duration_ms=duration_ms,
            details={
                "method": method,
                "path": path,
                "status_code": status_code,
                "params": _mask_sensitive_data(params) if params else {},
                "response_size": response_size,
            },
        )
        return self.log(event)

    def log_data_change(
        self,
        user_id: str,
        table: str,
        record_id: str,
        action: str,
        before: Optional[Dict[str, Any]] = None,
        after: Optional[Dict[str, Any]] = None,
        ip_address: str = "",
        session_id: str = "",
        details: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """记录数据变更日志。

        Args:
            user_id: 用户 ID。
            table: 数据表名。
            record_id: 记录 ID。
            action: 变更动作（create/update/delete）。
            before: 变更前状态。
            after: 变更后状态。
            ip_address: IP 地址。
            session_id: 会话 ID。
            details: 详细信息。

        Returns:
            是否记录成功。
        """
        # 推断事件类型
        action_lower = action.lower()
        if "create" in action_lower or "insert" in action_lower:
            event_type = AuditEventType.DATA_CREATE
        elif "update" in action_lower or "modify" in action_lower:
            event_type = AuditEventType.DATA_UPDATE
        elif "delete" in action_lower or "remove" in action_lower:
            event_type = AuditEventType.DATA_DELETE
        else:
            event_type = AuditEventType.DATA_UPDATE
        # 计算变更字段
        changed_fields: List[str] = []
        if before and after:
            for key in set(list(before.keys()) + list(after.keys())):
                if before.get(key) != after.get(key):
                    changed_fields.append(key)
        event = AuditEvent(
            event_type=event_type.value,
            user_id=user_id,
            action=action,
            resource=table,
            resource_id=record_id,
            result=RESULT_SUCCESS,
            severity=SEVERITY_INFO,
            ip_address=ip_address,
            session_id=session_id,
            before_state=before,
            after_state=after,
            details={
                **(details or {}),
                "table": table,
                "record_id": record_id,
                "changed_fields": changed_fields,
            },
        )
        return self.log(event)

    def log_config_change(
        self,
        user_id: str,
        config_key: str,
        old_value: Any,
        new_value: Any,
        ip_address: str = "",
        details: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """记录配置变更日志。

        Args:
            user_id: 用户 ID。
            config_key: 配置键。
            old_value: 旧值。
            new_value: 新值。
            ip_address: IP 地址。
            details: 详细信息。

        Returns:
            是否记录成功。
        """
        event = AuditEvent(
            event_type=AuditEventType.CONFIG_CHANGE.value,
            user_id=user_id,
            action="config_change",
            resource="config",
            resource_id=config_key,
            result=RESULT_SUCCESS,
            severity=SEVERITY_WARN,
            ip_address=ip_address,
            before_state={"value": old_value},
            after_state={"value": new_value},
            details={
                **(details or {}),
                "config_key": config_key,
                "old_value": _safe_str(old_value),
                "new_value": _safe_str(new_value),
            },
        )
        return self.log(event)

    def log_role_change(
        self,
        user_id: str,
        target_user_id: str,
        role: str,
        assigned: bool,
        ip_address: str = "",
        details: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """记录角色变更日志。

        Args:
            user_id: 操作者 ID。
            target_user_id: 目标用户 ID。
            role: 角色名。
            assigned: 是否分配（True=分配，False=撤销）。
            ip_address: IP 地址。
            details: 详细信息。

        Returns:
            是否记录成功。
        """
        event_type = AuditEventType.ROLE_ASSIGNED if assigned else AuditEventType.ROLE_REVOKED
        event = AuditEvent(
            event_type=event_type.value,
            user_id=user_id,
            action=f"{'assign' if assigned else 'revoke'}_role",
            resource="role",
            resource_id=role,
            result=RESULT_SUCCESS,
            severity=SEVERITY_WARN,
            ip_address=ip_address,
            details={
                **(details or {}),
                "target_user_id": target_user_id,
                "role": role,
                "assigned": assigned,
            },
        )
        return self.log(event)

    def log_custom(
        self,
        user_id: str,
        action: str,
        resource: str = "",
        result: str = RESULT_SUCCESS,
        severity: str = SEVERITY_INFO,
        details: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> bool:
        """记录自定义审计事件。

        Args:
            user_id: 用户 ID。
            action: 操作动作。
            resource: 资源。
            result: 结果。
            severity: 严重级别。
            details: 详细信息。
            **kwargs: 其他字段值。

        Returns:
            是否记录成功。
        """
        event = AuditEvent(
            event_type=AuditEventType.CUSTOM.value,
            user_id=user_id,
            action=action,
            resource=resource,
            result=result,
            severity=severity,
            details=details or {},
        )
        # 设置额外字段
        for key, value in kwargs.items():
            if hasattr(event, key):
                setattr(event, key, value)
        return self.log(event)

    # ===== 日志检索 =====

    def search(self, filter_obj: Optional[SearchFilter] = None, **kwargs: Any) -> List[Dict[str, Any]]:
        """检索审计日志。

        支持多条件组合查询。

        Args:
            filter_obj: 检索过滤器对象。
            **kwargs: 过滤器字段（用于快捷构建过滤器）。

        Returns:
            审计日志列表。
        """
        if filter_obj is None:
            filter_obj = SearchFilter(**kwargs)
        where_clause, params = filter_obj.to_where_clause()
        # 排序
        valid_order_fields = {
            "timestamp", "event_type", "user_id", "resource",
            "result", "severity", "id",
        }
        order_field = filter_obj.order_by if filter_obj.order_by in valid_order_fields else "timestamp"
        order_dir = "DESC" if filter_obj.order_desc else "ASC"
        query = (
            f"SELECT * FROM {AUDIT_LOGS_TABLE}"
            f"{where_clause} ORDER BY {order_field} {order_dir} LIMIT ? OFFSET ?"
        )
        params.extend([filter_obj.limit, filter_obj.offset])
        try:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            try:
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                return [self._row_to_dict(row) for row in rows]
            finally:
                conn.close()
        except Exception as e:  # pragma: no cover
            _logger.error("检索审计日志失败: %s", e)
            return []

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """将数据库行转换为字典。"""
        result = dict(row)
        # 解析 JSON 字段
        for json_field in ["details", "before_state", "after_state"]:
            if result.get(json_field):
                try:
                    result[json_field] = json.loads(result[json_field])
                except (json.JSONDecodeError, TypeError):
                    pass
        # 添加中文映射
        event_type = result.get("event_type", "")
        try:
            et = AuditEventType(event_type)
            result["event_type_name"] = EVENT_TYPE_NAMES.get(et, "自定义事件")
        except ValueError:
            result["event_type_name"] = "自定义事件"
        result["result_name"] = RESULT_NAMES.get(result.get("result", ""), "未知")
        result["severity_name"] = SEVERITY_NAMES.get(result.get("severity", ""), "未知")
        return result

    def get_by_id(self, event_id: str) -> Optional[Dict[str, Any]]:
        """按事件 ID 获取日志。"""
        try:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            try:
                cursor = conn.execute(
                    f"SELECT * FROM {AUDIT_LOGS_TABLE} WHERE event_id = ?",
                    (event_id,),
                )
                row = cursor.fetchone()
                return self._row_to_dict(row) if row else None
            finally:
                conn.close()
        except Exception as e:  # pragma: no cover
            _logger.error("获取审计日志失败: %s", e)
            return None

    def get_user_activity(
        self,
        user_id: str,
        hours: int = 24,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """获取用户活动记录。

        Args:
            user_id: 用户 ID。
            hours: 查询时间范围（小时）。
            limit: 返回数量。

        Returns:
            用户活动列表。
        """
        start_time = (datetime.now(tz=timezone.utc) - timedelta(hours=hours)).isoformat()
        return self.search(
            user_id=user_id,
            start_time=start_time,
            limit=limit,
        )

    def get_resource_history(
        self,
        resource: str,
        resource_id: str = "",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """获取资源操作历史。

        Args:
            resource: 资源名。
            resource_id: 资源 ID。
            limit: 返回数量。

        Returns:
            资源操作历史列表。
        """
        kwargs: Dict[str, Any] = {"resource": resource, "limit": limit}
        if resource_id:
            kwargs["resource_id"] = resource_id
        return self.search(**kwargs)

    def get_session_activity(self, session_id: str) -> List[Dict[str, Any]]:
        """获取会话活动记录。"""
        return self.search(session_id=session_id, limit=1000)

    def get_request_trace(self, request_id: str) -> List[Dict[str, Any]]:
        """获取请求链路追踪。"""
        return self.search(request_id=request_id, limit=1000)

    # ===== 完整性校验 =====

    def verify_integrity(self, limit: int = 0) -> Tuple[bool, List[str]]:
        """校验日志完整性。

        通过验证链式哈希，检测日志是否被篡改。

        Args:
            limit: 校验的记录数（0 表示全部）。

        Returns:
            (是否完整, 错误列表) 元组。
        """
        if not self.enable_integrity:
            return True, ["完整性保护未启用"]
        errors: List[str] = []
        try:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            try:
                query = (
                    f"SELECT event_id, event_type, timestamp, user_id, action, "
                    f"resource, resource_id, result, details, before_state, after_state, "
                    f"prev_hash, curr_hash FROM {AUDIT_LOGS_TABLE} ORDER BY id ASC"
                )
                if limit > 0:
                    query += f" LIMIT {limit}"
                cursor = conn.execute(query)
                rows = cursor.fetchall()
                prev_hash = ""
                checked = 0
                for row in rows:
                    # 重新计算哈希
                    content_parts = [
                        row["event_id"], row["event_type"], row["timestamp"],
                        row["user_id"] or "", row["action"] or "",
                        row["resource"] or "", row["resource_id"] or "",
                        row["result"] or "", row["details"] or "",
                        row["before_state"] or "", row["after_state"] or "",
                        prev_hash,
                    ]
                    content = "|".join(content_parts)
                    expected_hash = _hash_content(content)
                    # 校验 prev_hash
                    if row["prev_hash"] != prev_hash:
                        errors.append(
                            f"事件 {row['event_id']} 的 prev_hash 不匹配"
                            f"（期望: {prev_hash[:16]}..., 实际: {row['prev_hash'][:16] if row['prev_hash'] else '空'}...）"
                        )
                    # 校验 curr_hash
                    if row["curr_hash"] != expected_hash:
                        errors.append(
                            f"事件 {row['event_id']} 的 curr_hash 不匹配"
                            f"（可能被篡改）"
                        )
                    prev_hash = row["curr_hash"]
                    checked += 1
                _logger.info("完整性校验完成: 检查 %d 条，错误 %d 条", checked, len(errors))
            finally:
                conn.close()
        except Exception as e:  # pragma: no cover
            errors.append(f"完整性校验异常: {e}")
        return len(errors) == 0, errors

    # ===== 归档与清理 =====

    def archive(
        self,
        before_date: Optional[str] = None,
        batch_size: int = 1000,
    ) -> int:
        """归档旧日志。

        将指定日期之前的日志导出到压缩文件，并从数据库中删除。

        Args:
            before_date: 归档此日期之前的日志（ISO 格式），为 None 时使用保留策略。
            batch_size: 每批处理的记录数。

        Returns:
            归档的记录数。
        """
        if before_date is None:
            cutoff = datetime.now(tz=timezone.utc) - timedelta(days=self.retention_days)
            before_date = cutoff.isoformat()
        # 归档文件名
        archive_filename = f"audit_{before_date[:10]}_{int(_now_ts())}.jsonl.gz"
        archive_path = Path(self.archive_dir) / archive_filename
        archived_count = 0
        try:
            # 查询待归档记录
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            try:
                cursor = conn.execute(
                    f"SELECT COUNT(*) FROM {AUDIT_LOGS_TABLE} WHERE timestamp < ?",
                    (before_date,),
                )
                total = cursor.fetchone()[0]
                if total == 0:
                    _logger.info("无待归档日志")
                    return 0
                _logger.info("开始归档 %d 条日志到 %s", total, archive_path)
                # 分批导出
                with gzip.open(archive_path, "wt", encoding="utf-8") as f:
                    offset = 0
                    while offset < total:
                        cursor = conn.execute(
                            f"SELECT * FROM {AUDIT_LOGS_TABLE} "
                            f"WHERE timestamp < ? ORDER BY id LIMIT ? OFFSET ?",
                            (before_date, batch_size, offset),
                        )
                        rows = cursor.fetchall()
                        if not rows:
                            break
                        for row in rows:
                            f.write(json.dumps(dict(row), ensure_ascii=False, default=str) + "\n")
                            archived_count += 1
                        offset += batch_size
                # 删除已归档记录
                conn.execute(
                    f"DELETE FROM {AUDIT_LOGS_TABLE} WHERE timestamp < ?",
                    (before_date,),
                )
                conn.commit()
                _logger.info("归档完成: %d 条日志 -> %s", archived_count, archive_path)
            finally:
                conn.close()
        except Exception as e:  # pragma: no cover
            _logger.error("归档失败: %s", e)
            return 0
        return archived_count

    def cleanup(self, days: Optional[int] = None) -> int:
        """清理过期日志。

        直接删除超过保留期的日志（不归档）。

        Args:
            days: 保留天数，为 None 时使用默认值。

        Returns:
            删除的记录数。
        """
        retention = days if days is not None else self.retention_days
        cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=retention)).isoformat()
        try:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            try:
                cursor = conn.execute(
                    f"DELETE FROM {AUDIT_LOGS_TABLE} WHERE timestamp < ?",
                    (cutoff,),
                )
                deleted = cursor.rowcount
                conn.commit()
                _logger.info("清理过期审计日志: 删除 %d 条（%d 天前）", deleted, retention)
                return deleted
            finally:
                conn.close()
        except Exception as e:  # pragma: no cover
            _logger.error("清理审计日志失败: %s", e)
            return 0

    def list_archives(self) -> List[Dict[str, Any]]:
        """列出所有归档文件。"""
        archive_path = Path(self.archive_dir)
        if not archive_path.exists():
            return []
        archives: List[Dict[str, Any]] = []
        for f in sorted(archive_path.glob("*.gz"), key=lambda x: x.stat().st_mtime, reverse=True):
            stat = f.stat()
            archives.append({
                "filename": f.name,
                "path": str(f),
                "size_bytes": stat.st_size,
                "size_formatted": _format_bytes(stat.st_size),
                "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            })
        return archives

    def restore_from_archive(self, archive_filename: str) -> int:
        """从归档文件恢复日志。

        Args:
            archive_filename: 归档文件名。

        Returns:
            恢复的记录数。
        """
        archive_path = Path(self.archive_dir) / archive_filename
        if not archive_path.exists():
            _logger.error("归档文件不存在: %s", archive_path)
            return 0
        restored = 0
        try:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            try:
                with gzip.open(archive_path, "rt", encoding="utf-8") as f:
                    for line in f:
                        try:
                            record = json.loads(line.strip())
                            # 插入（忽略已存在的）
                            conn.execute(
                                f"INSERT OR IGNORE INTO {AUDIT_LOGS_TABLE} "
                                f"(event_id, event_type, timestamp, user_id, username, "
                                f"action, resource, resource_id, result, severity, "
                                f"ip_address, user_agent, session_id, request_id, "
                                f"details, before_state, after_state, duration_ms, "
                                f"prev_hash, curr_hash) "
                                f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                (
                                    record.get("event_id"),
                                    record.get("event_type"),
                                    record.get("timestamp"),
                                    record.get("user_id"),
                                    record.get("username"),
                                    record.get("action"),
                                    record.get("resource"),
                                    record.get("resource_id"),
                                    record.get("result"),
                                    record.get("severity"),
                                    record.get("ip_address"),
                                    record.get("user_agent"),
                                    record.get("session_id"),
                                    record.get("request_id"),
                                    record.get("details"),
                                    record.get("before_state"),
                                    record.get("after_state"),
                                    record.get("duration_ms"),
                                    record.get("prev_hash"),
                                    record.get("curr_hash"),
                                ),
                            )
                            restored += 1
                        except (json.JSONDecodeError, KeyError):
                            continue
                conn.commit()
                _logger.info("从归档恢复: %d 条日志 <- %s", restored, archive_path)
            finally:
                conn.close()
        except Exception as e:  # pragma: no cover
            _logger.error("从归档恢复失败: %s", e)
            return 0
        return restored

    # ===== 合规报告 =====

    def generate_compliance_report(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: int = 30,
    ) -> ComplianceReport:
        """生成合规报告。

        Args:
            start_date: 开始日期（ISO 格式），为 None 时自动计算。
            end_date: 结束日期（ISO 格式），为 None 时使用当前时间。
            days: 报告周期（天），当 start_date 为 None 时使用。

        Returns:
            合规报告对象。
        """
        if end_date is None:
            end_date = _iso_now()
        if start_date is None:
            start_dt = datetime.now(tz=timezone.utc) - timedelta(days=days)
            start_date = start_dt.isoformat()
        report = ComplianceReport(
            report_id=f"compliance_{int(_now_ts())}",
            period_start=start_date,
            period_end=end_date,
        )
        try:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            try:
                # 查询时间范围内的事件
                cursor = conn.execute(
                    f"SELECT * FROM {AUDIT_LOGS_TABLE} "
                    f"WHERE timestamp >= ? AND timestamp <= ? ORDER BY timestamp",
                    (start_date, end_date),
                )
                rows = cursor.fetchall()
                report.total_events = len(rows)
                # 统计
                for row in rows:
                    event_type = row["event_type"]
                    result = row["result"] or "unknown"
                    severity = row["severity"] or "info"
                    user_id = row["user_id"] or "anonymous"
                    report.by_type[event_type] = report.by_type.get(event_type, 0) + 1
                    report.by_result[result] = report.by_result.get(result, 0) + 1
                    report.by_severity[severity] = report.by_severity.get(severity, 0) + 1
                    report.by_user[user_id] = report.by_user.get(user_id, 0) + 1
                    # 特殊计数
                    if event_type == AuditEventType.AUTH_FAILURE.value:
                        report.failed_auth_count += 1
                    elif event_type == AuditEventType.PERMISSION_DENIED.value:
                        report.permission_denied_count += 1
                    elif event_type in (
                        AuditEventType.DATA_CREATE.value,
                        AuditEventType.DATA_UPDATE.value,
                        AuditEventType.DATA_DELETE.value,
                    ):
                        report.data_changes_count += 1
                    elif event_type == AuditEventType.CONFIG_CHANGE.value:
                        report.config_changes_count += 1
                    # 收集严重事件
                    if severity in (SEVERITY_ERROR, SEVERITY_CRITICAL):
                        report.critical_events.append({
                            "event_id": row["event_id"],
                            "event_type": event_type,
                            "timestamp": row["timestamp"],
                            "user_id": user_id,
                            "action": row["action"],
                            "result": result,
                            "severity": severity,
                            "details": row["details"],
                        })
            finally:
                conn.close()
        except Exception as e:  # pragma: no cover
            _logger.error("生成合规报告失败: %s", e)
        # 完整性校验
        if self.enable_integrity:
            verified, errors = self.verify_integrity()
            report.integrity_verified = verified
            report.integrity_errors = errors
        else:
            report.integrity_verified = True
        return report

    # ===== 审计追溯 =====

    def trace_operation(
        self,
        resource: str,
        resource_id: str,
    ) -> List[Dict[str, Any]]:
        """追溯资源的操作历史。

        还原指定资源的所有操作链路。

        Args:
            resource: 资源名。
            resource_id: 资源 ID。

        Returns:
            操作历史列表（按时间正序）。
        """
        return self.search(
            resource=resource,
            resource_id=resource_id,
            limit=1000,
            order_by="timestamp",
            order_desc=False,
        )

    def trace_user(
        self,
        user_id: str,
        hours: int = 168,
    ) -> Dict[str, Any]:
        """追溯用户操作。

        还原指定用户在时间范围内的所有操作。

        Args:
            user_id: 用户 ID。
            hours: 查询时间范围（小时），默认 7 天。

        Returns:
            用户操作追溯报告。
        """
        start_time = (datetime.now(tz=timezone.utc) - timedelta(hours=hours)).isoformat()
        activities = self.search(
            user_id=user_id,
            start_time=start_time,
            limit=10000,
        )
        # 分析
        by_type: Dict[str, int] = defaultdict(int)
        by_result: Dict[str, int] = defaultdict(int)
        by_resource: Dict[str, int] = defaultdict(int)
        ip_addresses: Set[str] = set()
        sessions: Set[str] = set()
        first_activity: Optional[str] = None
        last_activity: Optional[str] = None
        for activity in activities:
            by_type[activity.get("event_type", "unknown")] += 1
            by_result[activity.get("result", "unknown")] += 1
            by_resource[activity.get("resource", "unknown")] += 1
            if activity.get("ip_address"):
                ip_addresses.add(activity["ip_address"])
            if activity.get("session_id"):
                sessions.add(activity["session_id"])
            ts = activity.get("timestamp", "")
            if ts:
                if first_activity is None or ts < first_activity:
                    first_activity = ts
                if last_activity is None or ts > last_activity:
                    last_activity = ts
        return {
            "user_id": user_id,
            "period_hours": hours,
            "total_activities": len(activities),
            "by_type": dict(by_type),
            "by_result": dict(by_result),
            "by_resource": dict(by_resource),
            "unique_ip_count": len(ip_addresses),
            "ip_addresses": list(ip_addresses),
            "unique_session_count": len(sessions),
            "first_activity": first_activity,
            "last_activity": last_activity,
            "activities": activities[:100],  # 最近的 100 条
        }

    # ===== 统计信息 =====

    def get_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """获取审计日志统计。

        Args:
            hours: 统计时间范围（小时）。

        Returns:
            统计信息字典。
        """
        start_time = (datetime.now(tz=timezone.utc) - timedelta(hours=hours)).isoformat()
        try:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            try:
                cursor = conn.execute(
                    f"SELECT event_type, result, severity, user_id, COUNT(*) as count "
                    f"FROM {AUDIT_LOGS_TABLE} WHERE timestamp >= ? "
                    f"GROUP BY event_type, result, severity, user_id",
                    (start_time,),
                )
                rows = cursor.fetchall()
                # 汇总
                total = 0
                by_type: Dict[str, int] = defaultdict(int)
                by_result: Dict[str, int] = defaultdict(int)
                by_severity: Dict[str, int] = defaultdict(int)
                by_user: Dict[str, int] = defaultdict(int)
                for row in rows:
                    count = row["count"]
                    total += count
                    by_type[row["event_type"]] += count
                    by_result[row["result"]] += count
                    by_severity[row["severity"]] += count
                    by_user[row["user_id"] or "anonymous"] += count
                return {
                    "period_hours": hours,
                    "total_events": total,
                    "by_type": dict(by_type),
                    "by_result": dict(by_result),
                    "by_severity": dict(by_severity),
                    "by_user": dict(sorted(by_user.items(), key=lambda x: x[1], reverse=True)[:20]),
                    "unique_users": len(by_user),
                }
            finally:
                conn.close()
        except Exception as e:  # pragma: no cover
            _logger.error("获取审计统计失败: %s", e)
            return {"period_hours": hours, "total_events": 0}

    def get_count(self) -> int:
        """获取日志总数。"""
        try:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            try:
                cursor = conn.execute(f"SELECT COUNT(*) FROM {AUDIT_LOGS_TABLE}")
                return cursor.fetchone()[0]
            finally:
                conn.close()
        except Exception:  # pragma: no cover
            return 0

    # ===== 导出 =====

    def export_to_json(
        self,
        output_path: str,
        filter_obj: Optional[SearchFilter] = None,
    ) -> int:
        """导出审计日志到 JSON 文件。

        Args:
            output_path: 输出文件路径。
            filter_obj: 过滤器，为 None 时导出全部。

        Returns:
            导出的记录数。
        """
        records = self.search(filter_obj, limit=100000)
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=2, default=str)
            _logger.info("导出 %d 条审计日志到 %s", len(records), output_path)
            return len(records)
        except Exception as e:  # pragma: no cover
            _logger.error("导出审计日志失败: %s", e)
            return 0

    def export_to_csv(
        self,
        output_path: str,
        filter_obj: Optional[SearchFilter] = None,
    ) -> int:
        """导出审计日志到 CSV 文件。

        Args:
            output_path: 输出文件路径。
            filter_obj: 过滤器。

        Returns:
            导出的记录数。
        """
        import csv
        records = self.search(filter_obj, limit=100000)
        if not records:
            return 0
        try:
            fieldnames = [
                "event_id", "event_type", "event_type_name", "timestamp",
                "user_id", "username", "action", "resource", "resource_id",
                "result", "result_name", "severity", "severity_name",
                "ip_address", "session_id", "request_id", "duration_ms",
            ]
            with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                for record in records:
                    writer.writerow(record)
            _logger.info("导出 %d 条审计日志到 %s", len(records), output_path)
            return len(records)
        except Exception as e:  # pragma: no cover
            _logger.error("导出审计日志失败: %s", e)
            return 0


def _format_bytes(num_bytes: float) -> str:
    """格式化字节数为人类可读字符串。"""
    for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} EB"


# ===== 模块级单例访问 =====

def get_audit_logger() -> AuditLogger:
    """获取全局审计日志器单例。"""
    return AuditLogger.get_instance()


def log_audit(
    user_id: str,
    action: str,
    resource: str = "",
    result: str = RESULT_SUCCESS,
    details: Optional[Dict[str, Any]] = None,
) -> bool:
    """模块级审计日志记录便捷函数。"""
    return get_audit_logger().log_custom(
        user_id=user_id,
        action=action,
        resource=resource,
        result=result,
        details=details,
    )


def log_user_action(
    user_id: str,
    action: str,
    resource: str = "",
    result: str = RESULT_SUCCESS,
    ip_address: str = "",
) -> bool:
    """模块级用户操作日志便捷函数。"""
    return get_audit_logger().log_user_action(
        user_id=user_id,
        action=action,
        resource=resource,
        result=result,
        ip_address=ip_address,
    )
