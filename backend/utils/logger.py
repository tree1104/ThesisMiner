"""完整日志系统

提供结构化日志、多处理器、日志轮转、JSON 格式化、审计日志等能力。
支持控制台、文件、内存三种输出目标，可按模块独立配置日志级别。

核心组件：
    - StructuredFormatter: 结构化日志格式化器（文本/JSON 双模式）
    - RotatingFileHandler: 按大小轮转的文件处理器
    - TimedRotatingFileHandler: 按时间轮转的文件处理器
    - AuditLogger: 审计日志记录器（独立文件、独立格式）
    - LogManager: 全局日志管理器（单例，统一配置入口）
    - ContextFilter: 上下文注入过滤器（request_id / user_id / session_id）

设计原则：
    1. 线程安全：所有处理器与格式化器均可在多线程环境使用
    2. 零依赖：仅使用 Python 标准库（logging / json / threading / time）
    3. 可扩展：通过 add_handler / remove_handler 动态增删处理器
    4. 可观测：内置统计计数器，便于监控日志吞吐量
"""
import json
import logging
import logging.handlers
import os
import sys
import threading
import time
import traceback
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional


# ===== 日志级别常量（扩展标准 logging 级别）=====
# 在标准 DEBUG/INFO/WARNING/ERROR/CRITICAL 之外增加 TRACE 与 AUDIT
TRACE = 5  # 低于 DEBUG，用于极细粒度追踪
AUDIT = 35  # 介于 WARNING 与 ERROR 之间，用于审计事件

# 注册到 logging 模块，使 logging.TRACE / logging.AUDIT 可用
logging.addLevelName(TRACE, "TRACE")
logging.addLevelName(AUDIT, "AUDIT")


def _trace(self, message, *args, **kwargs):
    """TRACE 级别日志方法"""
    if self.isEnabledFor(TRACE):
        self._log(TRACE, message, args, **kwargs)


def _audit(self, message, *args, **kwargs):
    """AUDIT 级别日志方法"""
    if self.isEnabledFor(AUDIT):
        self._log(AUDIT, message, args, **kwargs)


# 为 Logger 类注入 trace 与 audit 方法
logging.Logger.trace = _trace
logging.Logger.audit = _audit


# ===== 上下文存储（线程局部变量）=====
# 用于在日志中注入 request_id / user_id / session_id 等上下文字段
_context = threading.local()


def set_log_context(**kwargs):
    """设置当前线程的日志上下文字段。

    常用字段：request_id、user_id、session_id、agent_id、stage。
    设置后，所有经过 ContextFilter 的日志记录都会携带这些字段。

    Args:
        **kwargs: 上下文字段键值对。
    """
    if not hasattr(_context, "fields"):
        _context.fields = {}
    _context.fields.update(kwargs)


def clear_log_context():
    """清空当前线程的日志上下文。"""
    if hasattr(_context, "fields"):
        _context.fields.clear()


def get_log_context() -> dict:
    """获取当前线程的日志上下文副本。"""
    if hasattr(_context, "fields"):
        return _context.fields.copy()
    return {}


class ContextFilter(logging.Filter):
    """上下文注入过滤器

    将线程局部上下文字段（request_id / user_id / session_id 等）
    注入到每条日志记录的 extra 属性中，供格式化器使用。
    """

    def __init__(self, default_fields: Optional[dict] = None):
        super().__init__()
        # default_fields 为所有日志记录的默认字段（如 hostname、service）
        self.default_fields = default_fields or {}

    def filter(self, record: logging.LogRecord) -> bool:
        """注入上下文字段到日志记录。"""
        # 注入默认字段
        for key, value in self.default_fields.items():
            if not hasattr(record, key):
                setattr(record, key, value)
        # 注入线程上下文字段
        ctx = get_log_context()
        for key, value in ctx.items():
            setattr(record, key, value)
        # 确保 timestamp 字段存在（ISO8601 格式）
        if not hasattr(record, "timestamp"):
            record.timestamp = datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat()
        return True


class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器

    支持两种输出模式：
        - text: 人类可读的多行文本格式（默认）
        - json: 机器可解析的单行 JSON 格式

    JSON 模式下，所有 extra 字段与上下文字段都会被序列化到 JSON 对象中，
    便于 ELK / Loki / Datadog 等日志聚合系统采集与检索。
    """

    # 文本模式默认格式
    TEXT_FORMAT = (
        "%(timestamp)s | %(levelname)-8s | %(name)s | "
        "%(funcName)s:%(lineno)d | %(message)s"
    )

    # 文本模式带上下文的扩展格式
    TEXT_FORMAT_WITH_CONTEXT = (
        "%(timestamp)s | %(levelname)-8s | %(name)s | "
        "%(funcName)s:%(lineno)d | req=%(request_id)s | "
        "sess=%(session_id)s | %(message)s"
    )

    # JSON 模式输出的核心字段
    JSON_FIELDS = [
        "timestamp",
        "level",
        "logger",
        "message",
        "module",
        "funcName",
        "lineno",
        "thread",
        "threadName",
        "process",
        "pathname",
    ]

    # 上下文字段（若存在则输出）
    CONTEXT_FIELDS = [
        "request_id",
        "user_id",
        "session_id",
        "agent_id",
        "stage",
        "task_id",
        "correlation_id",
    ]

    def __init__(self, mode: str = "text", include_context: bool = True):
        """初始化格式化器。

        Args:
            mode: 输出模式，"text" 或 "json"。
            include_context: 文本模式下是否包含上下文字段。
        """
        super().__init__()
        self.mode = mode
        self.include_context = include_context

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录。"""
        if self.mode == "json":
            return self._format_json(record)
        return self._format_text(record)

    def _format_text(self, record: logging.LogRecord) -> str:
        """文本模式格式化。"""
        # 确保必要字段存在
        if not hasattr(record, "timestamp"):
            record.timestamp = datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat()
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        if not hasattr(record, "session_id"):
            record.session_id = "-"

        fmt = self.TEXT_FORMAT_WITH_CONTEXT if self.include_context else self.TEXT_FORMAT
        result = fmt % record.__dict__

        # 追加异常信息
        if record.exc_info:
            result += "\n" + self.formatException(record.exc_info)
        # 追加堆栈信息
        if record.stack_info:
            result += "\n" + self.formatStack(record.stack_info)

        # 追加额外字段（非标准属性）
        standard_attrs = set(
            [
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "asctime", "timestamp", "request_id", "session_id",
            ]
        )
        extras = []
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                extras.append(f"{key}={value}")
        if extras:
            result += " | " + " ".join(extras)

        return result

    def _format_json(self, record: logging.LogRecord) -> str:
        """JSON 模式格式化。"""
        # 确保必要字段存在
        if not hasattr(record, "timestamp"):
            record.timestamp = datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat()

        log_entry = {
            "timestamp": record.timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName,
            "lineno": record.lineno,
            "thread": record.thread,
            "threadName": record.threadName,
            "process": record.process,
            "pathname": record.pathname,
        }

        # 注入上下文字段
        for field in self.CONTEXT_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                log_entry[field] = value

        # 注入额外字段（非标准属性）
        standard_attrs = set(
            [
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "asctime", "timestamp",
            ]
        )
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_") and key not in self.CONTEXT_FIELDS:
                try:
                    json.dumps(value)
                    log_entry[key] = value
                except (TypeError, ValueError):
                    log_entry[key] = str(value)

        # 追加异常信息
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
            log_entry["exception_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
        if record.stack_info:
            log_entry["stack_info"] = self.formatStack(record.stack_info)

        return json.dumps(log_entry, ensure_ascii=False, default=str)


class MemoryHandler(logging.Handler):
    """内存日志处理器

    将日志记录暂存在内存环形缓冲区中，用于：
        - 调试时快速查看最近日志
        - 错误发生时导出上下文日志
        - 测试断言日志输出

    缓冲区大小固定，超出后自动丢弃最旧记录。
    """

    def __init__(self, capacity: int = 1000, level: int = logging.NOTSET):
        """初始化内存处理器。

        Args:
            capacity: 缓冲区容量（最大记录数）。
            level: 最低日志级别。
        """
        super().__init__(level=level)
        self.capacity = capacity
        self._buffer = deque(maxlen=capacity)
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        """将日志记录写入内存缓冲区。"""
        try:
            msg = self.format(record)
            with self._lock:
                self._buffer.append(
                    {
                        "timestamp": record.created,
                        "level": record.levelname,
                        "logger": record.name,
                        "message": record.getMessage(),
                        "formatted": msg,
                        "record": record,
                    }
                )
        except Exception:
            self.handleError(record)

    def get_records(self, level: Optional[int] = None, logger_name: Optional[str] = None) -> list:
        """获取缓冲区中的日志记录。

        Args:
            level: 可选，按级别过滤。
            logger_name: 可选，按 logger 名称过滤（前缀匹配）。

        Returns:
            日志记录列表。
        """
        with self._lock:
            records = list(self._buffer)
        if level is not None:
            records = [r for r in records if logging.getLevelName(r["level"]) >= level]
        if logger_name is not None:
            records = [r for r in records if r["logger"].startswith(logger_name)]
        return records

    def clear(self) -> None:
        """清空缓冲区。"""
        with self._lock:
            self._buffer.clear()

    def get_stats(self) -> dict:
        """获取缓冲区统计信息。"""
        with self._lock:
            total = len(self._buffer)
            level_counts = defaultdict(int)
            for r in self._buffer:
                level_counts[r["level"]] += 1
            return {
                "total": total,
                "capacity": self.capacity,
                "by_level": dict(level_counts),
            }


class AuditLogger:
    """审计日志记录器

    专门用于记录安全审计事件，如：
        - 用户登录 / 登出
        - 配置变更
        - 敏感数据访问
        - API 密钥使用
        - 权限变更

    审计日志写入独立文件，使用 JSON 格式，便于合规审计与追溯。
    每条审计记录包含：时间戳、事件类型、操作者、目标、结果、详情。
    """

    def __init__(self, log_file: str = "logs/audit.log", max_bytes: int = 10 * 1024 * 1024, backup_count: int = 10):
        """初始化审计日志记录器。

        Args:
            log_file: 审计日志文件路径。
            max_bytes: 单文件最大字节数，超出后轮转。
            backup_count: 保留的备份文件数。
        """
        self.log_file = log_file
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self._lock = threading.Lock()
        self._ensure_dir()

        # 创建独立的 logger（不传播到根 logger，避免重复记录）
        self._logger = logging.getLogger("thesisminer.audit")
        self._logger.setLevel(AUDIT)
        self._logger.propagate = False

        # 配置轮转文件处理器
        handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        handler.setLevel(AUDIT)
        handler.setFormatter(StructuredFormatter(mode="json", include_context=False))
        # 避免重复添加处理器
        if not self._logger.handlers:
            self._logger.addHandler(handler)

    def _ensure_dir(self) -> None:
        """确保日志目录存在。"""
        log_dir = os.path.dirname(self.log_file)
        if log_dir:
            Path(log_dir).mkdir(parents=True, exist_ok=True)

    def log_event(
        self,
        event_type: str,
        actor: str = "",
        target: str = "",
        result: str = "success",
        details: Optional[dict] = None,
        severity: str = "info",
    ) -> None:
        """记录审计事件。

        Args:
            event_type: 事件类型（如 login / logout / config_change / data_access）。
            actor: 操作者标识（用户 ID 或系统名称）。
            target: 操作目标（如配置项名称、数据表名）。
            result: 操作结果（success / failure / denied）。
            details: 事件详情字典。
            severity: 严重级别（info / warning / error / critical）。
        """
        event = {
            "event_type": event_type,
            "actor": actor,
            "target": target,
            "result": result,
            "details": details or {},
            "severity": severity,
        }
        # 注入上下文
        ctx = get_log_context()
        if ctx:
            event["context"] = ctx

        with self._lock:
            self._logger.audit(json.dumps(event, ensure_ascii=False, default=str))

    def log_login(self, user_id: str, success: bool, ip: str = "", details: Optional[dict] = None) -> None:
        """记录登录事件。"""
        self.log_event(
            event_type="login",
            actor=user_id,
            result="success" if success else "failure",
            details={"ip": ip, **(details or {})},
            severity="info" if success else "warning",
        )

    def log_logout(self, user_id: str, details: Optional[dict] = None) -> None:
        """记录登出事件。"""
        self.log_event(
            event_type="logout",
            actor=user_id,
            result="success",
            details=details or {},
        )

    def log_config_change(self, actor: str, key: str, old_value: Any, new_value: Any) -> None:
        """记录配置变更事件。"""
        self.log_event(
            event_type="config_change",
            actor=actor,
            target=key,
            result="success",
            details={"old_value": str(old_value), "new_value": str(new_value)},
            severity="warning",
        )

    def log_data_access(self, actor: str, resource: str, action: str = "read") -> None:
        """记录敏感数据访问事件。"""
        self.log_event(
            event_type="data_access",
            actor=actor,
            target=resource,
            result="success",
            details={"action": action},
            severity="info",
        )

    def log_api_key_usage(self, actor: str, provider: str, purpose: str) -> None:
        """记录 API 密钥使用事件。"""
        self.log_event(
            event_type="api_key_usage",
            actor=actor,
            target=provider,
            result="success",
            details={"purpose": purpose},
            severity="info",
        )

    def log_permission_change(self, actor: str, target_user: str, permission: str, granted: bool) -> None:
        """记录权限变更事件。"""
        self.log_event(
            event_type="permission_change",
            actor=actor,
            target=target_user,
            result="success",
            details={"permission": permission, "granted": granted},
            severity="warning" if granted else "error",
        )


class LogStats:
    """日志统计计数器

    按级别与 logger 名称统计日志产出量，用于监控与容量规划。
    线程安全，使用原子计数器。
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._level_counts = defaultdict(int)
        self._logger_counts = defaultdict(lambda: defaultdict(int))
        self._error_messages = deque(maxlen=100)
        self._start_time = time.time()

    def record(self, record: logging.LogRecord) -> None:
        """记录一条日志。"""
        with self._lock:
            self._level_counts[record.levelname] += 1
            self._logger_counts[record.name][record.levelname] += 1
            if record.levelno >= logging.ERROR:
                self._error_messages.append(
                    {
                        "timestamp": record.created,
                        "logger": record.name,
                        "message": record.getMessage(),
                    }
                )

    def get_summary(self) -> dict:
        """获取统计摘要。"""
        with self._lock:
            uptime = time.time() - self._start_time
            total = sum(self._level_counts.values())
            return {
                "uptime_seconds": uptime,
                "total_records": total,
                "records_per_second": total / uptime if uptime > 0 else 0,
                "by_level": dict(self._level_counts),
                "by_logger": {
                    name: dict(levels) for name, levels in self._logger_counts.items()
                },
                "recent_errors": list(self._error_messages),
            }

    def reset(self) -> None:
        """重置统计计数器。"""
        with self._lock:
            self._level_counts.clear()
            self._logger_counts.clear()
            self._error_messages.clear()
            self._start_time = time.time()


# 全局统计实例
_global_stats = LogStats()


class StatsHandler(logging.Handler):
    """统计处理器

    不输出日志，仅更新全局统计计数器。
    应添加到根 logger 以统计所有日志。
    """

    def emit(self, record: logging.LogRecord) -> None:
        _global_stats.record(record)


class LogManager:
    """全局日志管理器（单例）

    统一管理所有 logger 的配置，提供：
        - 初始化根 logger（控制台 + 文件 + 内存）
        - 按模块获取 logger
        - 动态调整日志级别
        - 获取内存日志与统计信息
        - 关闭与清理

    使用示例：
        manager = LogManager.get_instance()
        manager.setup(log_dir="logs", level="INFO", json_console=False)
        logger = manager.get_logger("backend.agents")
        logger.info("Agent 启动")
    """

    _instance: Optional["LogManager"] = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> "LogManager":
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
        self._setup_done = False
        self._memory_handler: Optional[MemoryHandler] = None
        self._stats_handler: Optional[StatsHandler] = None
        self._context_filter: Optional[ContextFilter] = None
        self._audit_logger: Optional[AuditLogger] = None
        self._file_handlers: list = []
        self._console_handler: Optional[logging.Handler] = None
        self._log_dir: str = "logs"
        self._configured_loggers: set = set()

    @classmethod
    def get_instance(cls) -> "LogManager":
        """获取单例实例。"""
        return cls()

    def setup(
        self,
        log_dir: str = "logs",
        level: str = "INFO",
        json_console: bool = False,
        json_file: bool = True,
        console_enabled: bool = True,
        file_enabled: bool = True,
        memory_enabled: bool = True,
        memory_capacity: int = 1000,
        max_file_size: int = 10 * 1024 * 1024,
        backup_count: int = 10,
        audit_enabled: bool = True,
        default_fields: Optional[dict] = None,
    ) -> None:
        """初始化全局日志配置。

        Args:
            log_dir: 日志文件目录。
            level: 全局日志级别（DEBUG/INFO/WARNING/ERROR/CRITICAL/TRACE）。
            json_console: 控制台是否输出 JSON 格式。
            json_file: 文件是否输出 JSON 格式。
            console_enabled: 是否启用控制台输出。
            file_enabled: 是否启用文件输出。
            memory_enabled: 是否启用内存缓冲。
            memory_capacity: 内存缓冲区容量。
            max_file_size: 单文件最大字节数。
            backup_count: 文件轮转备份数。
            audit_enabled: 是否启用审计日志。
            default_fields: 所有日志记录的默认字段。
        """
        if self._setup_done:
            return

        self._log_dir = log_dir
        Path(log_dir).mkdir(parents=True, exist_ok=True)

        # 解析日志级别
        numeric_level = getattr(logging, level.upper(), logging.INFO)

        # 配置根 logger
        root_logger = logging.getLogger()
        root_logger.setLevel(numeric_level)

        # 清除已有处理器（避免重复）
        root_logger.handlers.clear()

        # 上下文过滤器
        hostname = os.environ.get("HOSTNAME", os.environ.get("COMPUTERNAME", "localhost"))
        service = os.environ.get("SERVICE_NAME", "thesisminer")
        self._context_filter = ContextFilter(
            default_fields={
                "hostname": hostname,
                "service": service,
                **(default_fields or {}),
            }
        )

        # 控制台处理器
        if console_enabled:
            self._console_handler = logging.StreamHandler(sys.stdout)
            self._console_handler.setLevel(numeric_level)
            self._console_handler.setFormatter(
                StructuredFormatter(mode="json" if json_console else "text")
            )
            self._console_handler.addFilter(self._context_filter)
            root_logger.addHandler(self._console_handler)

        # 文件处理器（主日志文件，按大小轮转）
        if file_enabled:
            main_log_file = os.path.join(log_dir, "thesisminer.log")
            file_handler = logging.handlers.RotatingFileHandler(
                main_log_file,
                maxBytes=max_file_size,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setLevel(numeric_level)
            file_handler.setFormatter(
                StructuredFormatter(mode="json" if json_file else "text")
            )
            file_handler.addFilter(self._context_filter)
            root_logger.addHandler(file_handler)
            self._file_handlers.append(file_handler)

            # 错误日志文件（仅记录 ERROR 及以上）
            error_log_file = os.path.join(log_dir, "error.log")
            error_handler = logging.handlers.RotatingFileHandler(
                error_log_file,
                maxBytes=max_file_size,
                backupCount=backup_count,
                encoding="utf-8",
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(StructuredFormatter(mode="json"))
            error_handler.addFilter(self._context_filter)
            root_logger.addHandler(error_handler)
            self._file_handlers.append(error_handler)

        # 内存处理器
        if memory_enabled:
            self._memory_handler = MemoryHandler(capacity=memory_capacity)
            self._memory_handler.setLevel(numeric_level)
            self._memory_handler.setFormatter(
                StructuredFormatter(mode="text", include_context=True)
            )
            self._memory_handler.addFilter(self._context_filter)
            root_logger.addHandler(self._memory_handler)

        # 统计处理器
        self._stats_handler = StatsHandler()
        self._stats_handler.setLevel(numeric_level)
        root_logger.addHandler(self._stats_handler)

        # 审计日志
        if audit_enabled:
            audit_file = os.path.join(log_dir, "audit.log")
            self._audit_logger = AuditLogger(log_file=audit_file)

        # 捕获未处理异常
        sys.excepthook = self._excepthook

        # 配置第三方库日志级别（降低噪音）
        for noisy_logger in ["urllib3", "httpx", "httpcore", "openai", "asyncio"]:
            logging.getLogger(noisy_logger).setLevel(logging.WARNING)

        self._setup_done = True
        root_logger.info(
            "日志系统初始化完成",
            extra={"log_dir": log_dir, "level": level},
        )

    def _excepthook(self, exc_type, exc_value, exc_tb) -> None:
        """全局未处理异常钩子。"""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logger = logging.getLogger("thesisminer.excepthook")
        logger.critical(
            "未处理的异常",
            exc_info=(exc_type, exc_value, exc_tb),
            extra={
                "exception_type": exc_type.__name__,
                "exception_message": str(exc_value),
            },
        )

    def get_logger(self, name: str, level: Optional[str] = None) -> logging.Logger:
        """获取指定名称的 logger。

        Args:
            name: logger 名称（通常为模块名，如 backend.agents.orchestrator）。
            level: 可选，为该 logger 设置独立级别。

        Returns:
            logging.Logger 实例。
        """
        logger = logging.getLogger(name)
        if level:
            numeric_level = getattr(logging, level.upper(), logging.INFO)
            logger.setLevel(numeric_level)
        self._configured_loggers.add(name)
        return logger

    def set_level(self, level: str, logger_name: Optional[str] = None) -> None:
        """动态调整日志级别。

        Args:
            level: 目标级别（DEBUG/INFO/WARNING/ERROR/CRITICAL/TRACE）。
            logger_name: 可选，指定 logger 名称；为 None 则调整根 logger。
        """
        numeric_level = getattr(logging, level.upper(), logging.INFO)
        target = logging.getLogger(logger_name) if logger_name else logging.getLogger()
        target.setLevel(numeric_level)
        # 同步调整处理器级别
        for handler in target.handlers:
            handler.setLevel(numeric_level)

    def get_memory_handler(self) -> Optional[MemoryHandler]:
        """获取内存日志处理器。"""
        return self._memory_handler

    def get_audit_logger(self) -> Optional[AuditLogger]:
        """获取审计日志记录器。"""
        return self._audit_logger

    def get_stats(self) -> dict:
        """获取日志统计信息。"""
        return _global_stats.get_summary()

    def get_recent_logs(self, count: int = 100, level: Optional[int] = None) -> list:
        """获取最近的内存日志记录。"""
        if self._memory_handler is None:
            return []
        records = self._memory_handler.get_records(level=level)
        return records[-count:]

    def export_logs(self, output_file: str, level: Optional[int] = None) -> int:
        """导出内存日志到文件。

        Args:
            output_file: 输出文件路径。
            level: 可选，按级别过滤。

        Returns:
            导出的记录数。
        """
        if self._memory_handler is None:
            return 0
        records = self._memory_handler.get_records(level=level)
        with open(output_file, "w", encoding="utf-8") as f:
            for r in records:
                f.write(r["formatted"] + "\n")
        return len(records)

    def add_handler(self, handler: logging.Handler, logger_name: Optional[str] = None) -> None:
        """为指定 logger 添加自定义处理器。

        Args:
            handler: 日志处理器实例。
            logger_name: 可选，目标 logger 名称；为 None 则添加到根 logger。
        """
        if self._context_filter:
            handler.addFilter(self._context_filter)
        target = logging.getLogger(logger_name) if logger_name else logging.getLogger()
        target.addHandler(handler)

    def remove_handler(self, handler: logging.Handler, logger_name: Optional[str] = None) -> None:
        """移除指定 logger 的处理器。"""
        target = logging.getLogger(logger_name) if logger_name else logging.getLogger()
        target.removeHandler(handler)

    def shutdown(self) -> None:
        """关闭日志系统，刷新所有处理器。"""
        logging.shutdown()
        self._setup_done = False
        self._file_handlers.clear()
        self._console_handler = None
        self._memory_handler = None
        self._stats_handler = None

    def reset(self) -> None:
        """重置日志管理器（主要用于测试）。

        清除所有处理器与统计，恢复到未初始化状态。
        """
        root_logger = logging.getLogger()
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass
        self._setup_done = False
        self._file_handlers.clear()
        self._console_handler = None
        self._memory_handler = None
        self._stats_handler = None
        self._audit_logger = None
        self._configured_loggers.clear()
        _global_stats.reset()


# ===== 模块级便捷函数 =====


def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """获取 logger 的便捷函数。

    自动初始化日志系统（若尚未初始化），使用默认配置。

    Args:
        name: logger 名称。
        level: 可选，独立日志级别。

    Returns:
        logging.Logger 实例。
    """
    manager = LogManager.get_instance()
    if not manager._setup_done:
        manager.setup()
    return manager.get_logger(name, level=level)


def init_logging(
    log_dir: str = "logs",
    level: str = "INFO",
    json_console: bool = False,
    json_file: bool = True,
    **kwargs,
) -> LogManager:
    """初始化日志系统的便捷函数。

    Args:
        log_dir: 日志文件目录。
        level: 全局日志级别。
        json_console: 控制台是否 JSON 格式。
        json_file: 文件是否 JSON 格式。
        **kwargs: 其他 LogManager.setup 参数。

    Returns:
        LogManager 单例实例。
    """
    manager = LogManager.get_instance()
    manager.setup(
        log_dir=log_dir,
        level=level,
        json_console=json_console,
        json_file=json_file,
        **kwargs,
    )
    return manager


def log_function_call(logger: Optional[logging.Logger] = None, level: int = logging.DEBUG):
    """函数调用日志装饰器

    记录函数的调用参数、返回值与执行耗时。

    使用示例：
        @log_function_call()
        def generate_proposal(degree, discipline):
            ...

    Args:
        logger: 可选，指定 logger；为 None 则使用调用模块的 logger。
        level: 日志级别。

    Returns:
        装饰器函数。
    """

    def decorator(func: Callable):
        import functools

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            use_logger = logger or logging.getLogger(func.__module__)
            func_name = f"{func.__module__}.{func.__qualname__}"
            start_time = time.time()
            use_logger.log(
                level,
                f"调用函数 {func_name} | args={args!r} kwargs={kwargs!r}",
            )
            try:
                result = func(*args, **kwargs)
                elapsed = (time.time() - start_time) * 1000
                use_logger.log(
                    level,
                    f"函数 {func_name} 返回 | 耗时={elapsed:.2f}ms | result={result!r}",
                )
                return result
            except Exception as e:
                elapsed = (time.time() - start_time) * 1000
                use_logger.error(
                    f"函数 {func_name} 异常 | 耗时={elapsed:.2f}ms | error={e!r}",
                    exc_info=True,
                )
                raise

        return wrapper

    return decorator


def log_async_function_call(logger: Optional[logging.Logger] = None, level: int = logging.DEBUG):
    """异步函数调用日志装饰器

    记录异步函数的调用参数、返回值与执行耗时。

    Args:
        logger: 可选，指定 logger。
        level: 日志级别。

    Returns:
        装饰器函数。
    """

    def decorator(func: Callable):
        import functools

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            use_logger = logger or logging.getLogger(func.__module__)
            func_name = f"{func.__module__}.{func.__qualname__}"
            start_time = time.time()
            use_logger.log(
                level,
                f"调用异步函数 {func_name} | args={args!r} kwargs={kwargs!r}",
            )
            try:
                result = await func(*args, **kwargs)
                elapsed = (time.time() - start_time) * 1000
                use_logger.log(
                    level,
                    f"异步函数 {func_name} 返回 | 耗时={elapsed:.2f}ms | result={result!r}",
                )
                return result
            except Exception as e:
                elapsed = (time.time() - start_time) * 1000
                use_logger.error(
                    f"异步函数 {func_name} 异常 | 耗时={elapsed:.2f}ms | error={e!r}",
                    exc_info=True,
                )
                raise

        return wrapper

    return decorator


def log_execution_time(logger: Optional[logging.Logger] = None, level: int = logging.INFO):
    """执行耗时日志装饰器

    仅记录函数执行耗时，不记录参数与返回值（适用于高频函数）。

    Args:
        logger: 可选，指定 logger。
        level: 日志级别。

    Returns:
        装饰器函数。
    """

    def decorator(func: Callable):
        import functools

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            use_logger = logger or logging.getLogger(func.__module__)
            func_name = f"{func.__module__}.{func.__qualname__}"
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                elapsed = (time.time() - start_time) * 1000
                use_logger.log(level, f"{func_name} 执行耗时: {elapsed:.2f}ms")
                return result
            except Exception:
                elapsed = (time.time() - start_time) * 1000
                use_logger.log(level, f"{func_name} 失败耗时: {elapsed:.2f}ms")
                raise

        return wrapper

    return decorator


class LogContext:
    """日志上下文管理器

    在 with 语句块内设置日志上下文字段，退出后自动清除。
    支持嵌套（内层 with 的字段会合并到外层）。

    使用示例：
        with LogContext(request_id="req-123", user_id="user-456"):
            logger.info("处理请求")  # 日志中会携带 request_id 与 user_id
            with LogContext(stage="generation"):
                logger.info("生成内容")  # 携带 request_id、user_id、stage
    """

    def __init__(self, **kwargs):
        self.new_fields = kwargs
        self.old_fields: dict = {}

    def __enter__(self):
        self.old_fields = get_log_context()
        set_log_context(**self.new_fields)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        clear_log_context()
        if self.old_fields:
            set_log_context(**self.old_fields)
        return False


def configure_third_party_logging(level: str = "WARNING") -> None:
    """配置第三方库的日志级别。

    降低第三方库的日志噪音，使应用日志更清晰。

    Args:
        level: 第三方库的日志级别。
    """
    numeric_level = getattr(logging, level.upper(), logging.WARNING)
    third_party_loggers = [
        "urllib3",
        "urllib3.connectionpool",
        "httpx",
        "httpcore",
        "openai",
        "asyncio",
        "sqlalchemy",
        "pydantic",
        "uvicorn",
        "uvicorn.access",
        "fastapi",
        "httpcore.http11",
        "httpcore.connection",
    ]
    for name in third_party_loggers:
        logging.getLogger(name).setLevel(numeric_level)


def get_log_file_path(log_dir: str = "logs", log_type: str = "main") -> str:
    """获取日志文件路径。

    Args:
        log_dir: 日志目录。
        log_type: 日志类型（main / error / audit）。

    Returns:
        日志文件完整路径。
    """
    filename_map = {
        "main": "thesisminer.log",
        "error": "error.log",
        "audit": "audit.log",
        "access": "access.log",
    }
    filename = filename_map.get(log_type, f"{log_type}.log")
    return os.path.join(log_dir, filename)


def rotate_log_file(filepath: str, backup_count: int = 5) -> None:
    """手动轮转日志文件。

    Args:
        filepath: 日志文件路径。
        backup_count: 保留备份数。
    """
    if not os.path.exists(filepath):
        return
    # 轮转现有备份
    for i in range(backup_count - 1, 0, -1):
        src = f"{filepath}.{i}"
        dst = f"{filepath}.{i + 1}"
        if os.path.exists(src):
            if os.path.exists(dst):
                os.remove(dst)
            os.rename(src, dst)
    # 当前文件轮转为 .1
    dst = f"{filepath}.1"
    if os.path.exists(dst):
        os.remove(dst)
    os.rename(filepath, dst)


def read_log_file(filepath: str, max_lines: int = 1000, level_filter: Optional[str] = None) -> list:
    """读取日志文件内容。

    Args:
        filepath: 日志文件路径。
        max_lines: 最大读取行数。
        level_filter: 可选，按级别过滤（仅对 JSON 日志有效）。

    Returns:
        日志行列表。
    """
    if not os.path.exists(filepath):
        return []
    lines = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if level_filter:
                try:
                    entry = json.loads(line.strip())
                    if entry.get("level", "").upper() == level_filter.upper():
                        lines.append(line.strip())
                except (json.JSONDecodeError, KeyError):
                    lines.append(line.strip())
            else:
                lines.append(line.strip())
            if len(lines) >= max_lines:
                break
    return lines


def format_exception(exc: Exception, include_traceback: bool = True) -> str:
    """格式化异常信息为字符串。

    Args:
        exc: 异常实例。
        include_traceback: 是否包含完整堆栈。

    Returns:
        格式化后的异常字符串。
    """
    if include_traceback:
        return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return f"{type(exc).__name__}: {exc}"


def sanitize_log_message(message: str, sensitive_keys: Optional[list] = None) -> str:
    """脱敏日志消息中的敏感信息。

    将敏感字段值替换为 ***。

    Args:
        message: 原始日志消息。
        sensitive_keys: 敏感字段名列表（默认包含 password / api_key / token / secret）。

    Returns:
        脱敏后的日志消息。
    """
    if sensitive_keys is None:
        sensitive_keys = ["password", "api_key", "apikey", "token", "secret", "authorization", "cookie"]

    import re

    result = message
    for key in sensitive_keys:
        # 匹配 "key": "value" 或 key=value 格式
        patterns = [
            rf'(["\']?{key}["\']?\s*[:=]\s*["\']?)[^"\']+(["\']?)',
            rf'({key}=)[^\s,}}]+',
        ]
        for pattern in patterns:
            result = re.sub(pattern, r"\1***\2", result, flags=re.IGNORECASE)
    return result


class SensitiveDataFilter(logging.Filter):
    """敏感数据脱敏过滤器

    在日志输出前对消息中的敏感信息进行脱敏处理。
    """

    def __init__(self, sensitive_keys: Optional[list] = None):
        super().__init__()
        self.sensitive_keys = sensitive_keys

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = sanitize_log_message(record.msg, self.sensitive_keys)
        return True


# ===== 模块级 logger（供本模块内部使用）=====
_module_logger = logging.getLogger(__name__)
