"""资源管理器模块

提供系统资源管理与调度能力，包括：
    - CPU/内存/磁盘/网络资源监控与限制
    - 连接池管理（数据库连接池）
    - 线程池管理、协程池管理
    - 资源配额、资源隔离、资源回收
    - 资源使用报告、容量规划、扩容建议
    - 限流策略（令牌桶、漏桶、滑动窗口）

设计原则：
    1. 零外部依赖：仅使用 Python 标准库
    2. 线程安全：所有公共方法通过 RLock 保护
    3. 可配置：阈值、配额、策略均可调整
    4. 可观测：内置资源使用统计与告警
    5. 优雅降级：资源不足时自动降级而非崩溃
"""
from __future__ import annotations

import asyncio
import os
import queue
import threading
import time
import uuid
from collections import deque, defaultdict
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional


# ===== 枚举 =====


class ResourceType(str, Enum):
    """资源类型。"""

    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    CONNECTION = "connection"
    THREAD = "thread"
    COROUTINE = "coroutine"


class AlertLevel(str, Enum):
    """告警级别。"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class LimitStrategy(str, Enum):
    """限流策略。"""

    TOKEN_BUCKET = "token_bucket"      # 令牌桶
    LEAKY_BUCKET = "leaky_bucket"      # 漏桶
    SLIDING_WINDOW = "sliding_window"  # 滑动窗口
    FIXED_WINDOW = "fixed_window"      # 固定窗口


# ===== 常量 =====


# 默认采样间隔（秒）
DEFAULT_SAMPLE_INTERVAL = 5.0

# 默认历史保留采样点数
DEFAULT_HISTORY_CAPACITY = 2880  # 4 小时（5s 间隔）

# CPU 告警阈值（百分比）
DEFAULT_CPU_WARNING = 70.0
DEFAULT_CPU_CRITICAL = 85.0
DEFAULT_CPU_EMERGENCY = 95.0

# 内存告警阈值（百分比）
DEFAULT_MEM_WARNING = 75.0
DEFAULT_MEM_CRITICAL = 88.0
DEFAULT_MEM_EMERGENCY = 95.0

# 磁盘告警阈值（百分比）
DEFAULT_DISK_WARNING = 80.0
DEFAULT_DISK_CRITICAL = 90.0
DEFAULT_DISK_EMERGENCY = 95.0

# 默认线程池大小
DEFAULT_THREAD_POOL_SIZE = 10

# 默认连接池大小
DEFAULT_CONNECTION_POOL_SIZE = 20

# 默认协程池大小
DEFAULT_COROUTINE_POOL_SIZE = 100

# 连接空闲超时（秒）
DEFAULT_CONNECTION_IDLE_TIMEOUT = 300

# 连接最大寿命（秒）
DEFAULT_CONNECTION_MAX_LIFETIME = 3600

# 令牌桶默认容量
DEFAULT_BUCKET_CAPACITY = 100

# 令牌桶默认填充速率（令牌/秒）
DEFAULT_BUCKET_FILL_RATE = 10.0

# 资源配额默认值
DEFAULT_QUOTA_LIMITS: dict[ResourceType, float] = {
    ResourceType.CPU: 80.0,          # CPU 使用率上限 %
    ResourceType.MEMORY: 80.0,       # 内存使用率上限 %
    ResourceType.DISK: 85.0,         # 磁盘使用率上限 %
    ResourceType.CONNECTION: 100,    # 最大连接数
    ResourceType.THREAD: 50,         # 最大线程数
    ResourceType.COROUTINE: 200,     # 最大协程数
}


# ===== 数据结构 =====


@dataclass
class ResourceSnapshot:
    """资源快照。

    Attributes:
        timestamp: 时间戳。
        cpu_percent: CPU 使用率（%）。
        memory_percent: 内存使用率（%）。
        memory_used_mb: 已用内存（MB）。
        memory_total_mb: 总内存（MB）。
        disk_percent: 磁盘使用率（%）。
        disk_used_gb: 已用磁盘（GB）。
        disk_total_gb: 总磁盘（GB）。
        network_bytes_sent: 网络发送字节。
        network_bytes_recv: 网络接收字节。
        thread_count: 线程数。
        connection_count: 连接数。
        coroutine_count: 协程数。
    """

    timestamp: float = field(default_factory=time.time)
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_used_mb: float = 0.0
    memory_total_mb: float = 0.0
    disk_percent: float = 0.0
    disk_used_gb: float = 0.0
    disk_total_gb: float = 0.0
    network_bytes_sent: int = 0
    network_bytes_recv: int = 0
    thread_count: int = 0
    connection_count: int = 0
    coroutine_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "cpu_percent": round(self.cpu_percent, 2),
            "memory_percent": round(self.memory_percent, 2),
            "memory_used_mb": round(self.memory_used_mb, 2),
            "memory_total_mb": round(self.memory_total_mb, 2),
            "disk_percent": round(self.disk_percent, 2),
            "disk_used_gb": round(self.disk_used_gb, 2),
            "disk_total_gb": round(self.disk_total_gb, 2),
            "network_bytes_sent": self.network_bytes_sent,
            "network_bytes_recv": self.network_bytes_recv,
            "thread_count": self.thread_count,
            "connection_count": self.connection_count,
            "coroutine_count": self.coroutine_count,
        }


@dataclass
class ResourceQuota:
    """资源配额。

    Attributes:
        resource_type: 资源类型。
        limit: 配额上限。
        current: 当前使用量。
        reserved: 预留量。
        unit: 单位。
    """

    resource_type: ResourceType = ResourceType.CPU
    limit: float = 0.0
    current: float = 0.0
    reserved: float = 0.0
    unit: str = ""

    @property
    def available(self) -> float:
        """可用量。"""
        return max(0.0, self.limit - self.current - self.reserved)

    @property
    def utilization(self) -> float:
        """使用率。"""
        if self.limit <= 0:
            return 0.0
        return (self.current + self.reserved) / self.limit

    @property
    def is_exceeded(self) -> bool:
        """是否超限。"""
        return self.current + self.reserved > self.limit

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_type": self.resource_type.value,
            "limit": self.limit,
            "current": round(self.current, 4),
            "reserved": round(self.reserved, 4),
            "available": round(self.available, 4),
            "utilization": round(self.utilization, 4),
            "is_exceeded": self.is_exceeded,
            "unit": self.unit,
        }


@dataclass
class PoolStats:
    """池统计。

    Attributes:
        pool_type: 池类型。
        total: 总数。
        active: 活跃数。
        idle: 空闲数。
        waiting: 等待数。
        created: 累计创建数。
        destroyed: 累计销毁数.
        acquisitions: 累计获取数.
        rejections: 累计拒绝数.
        avg_wait_time: 平均等待时间.
    """

    pool_type: str = ""
    total: int = 0
    active: int = 0
    idle: int = 0
    waiting: int = 0
    created: int = 0
    destroyed: int = 0
    acquisitions: int = 0
    rejections: int = 0
    avg_wait_time: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "pool_type": self.pool_type,
            "total": self.total,
            "active": self.active,
            "idle": self.idle,
            "waiting": self.waiting,
            "created": self.created,
            "destroyed": self.destroyed,
            "acquisitions": self.acquisitions,
            "rejections": self.rejections,
            "avg_wait_time": round(self.avg_wait_time, 4),
        }


@dataclass
class ResourceAlert:
    """资源告警。

    Attributes:
        id: 告警 ID。
        level: 告警级别。
        resource_type: 资源类型。
        message: 告警消息。
        value: 当前值。
        threshold: 阈值。
        timestamp: 时间戳。
    """

    id: str = ""
    level: AlertLevel = AlertLevel.WARNING
    resource_type: ResourceType = ResourceType.CPU
    message: str = ""
    value: float = 0.0
    threshold: float = 0.0
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ===== 限流器实现 =====


class RateLimiter:
    """限流器基类。"""

    def __init__(self, capacity: float, fill_rate: float) -> None:
        self._capacity = capacity
        self._fill_rate = fill_rate
        self._lock = threading.RLock()

    def acquire(self, tokens: float = 1.0) -> bool:
        """尝试获取令牌。

        Args:
            tokens: 需要的令牌数。

        Returns:
            是否成功。
        """
        raise NotImplementedError

    def try_acquire(self, tokens: float = 1.0, timeout: float = 0.0) -> bool:
        """尝试在超时内获取令牌。

        Args:
            tokens: 需要的令牌数。
            timeout: 超时时间。

        Returns:
            是否成功。
        """
        raise NotImplementedError

    def get_state(self) -> dict[str, Any]:
        """获取状态。"""
        raise NotImplementedError


class TokenBucketRateLimiter(RateLimiter):
    """令牌桶限流器。"""

    def __init__(
        self,
        capacity: float = DEFAULT_BUCKET_CAPACITY,
        fill_rate: float = DEFAULT_BUCKET_FILL_RATE,
    ) -> None:
        super().__init__(capacity, fill_rate)
        self._tokens = capacity
        self._last_fill = time.time()

    def _refill(self) -> None:
        """补充令牌。"""
        now = time.time()
        elapsed = now - self._last_fill
        new_tokens = elapsed * self._fill_rate
        self._tokens = min(self._capacity, self._tokens + new_tokens)
        self._last_fill = now

    def acquire(self, tokens: float = 1.0) -> bool:
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    def try_acquire(self, tokens: float = 1.0, timeout: float = 0.0) -> bool:
        deadline = time.time() + timeout
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return True
            if time.time() >= deadline:
                return False
            # 等待补充
            wait_time = (tokens - self._tokens) / self._fill_rate if self._fill_rate > 0 else 0.1
            time.sleep(min(wait_time, 0.1))

    def get_state(self) -> dict[str, Any]:
        with self._lock:
            self._refill()
            return {
                "strategy": LimitStrategy.TOKEN_BUCKET.value,
                "capacity": self._capacity,
                "fill_rate": self._fill_rate,
                "current_tokens": round(self._tokens, 2),
                "utilization": round(1 - self._tokens / self._capacity, 4),
            }


class LeakyBucketRateLimiter(RateLimiter):
    """漏桶限流器。"""

    def __init__(
        self,
        capacity: float = DEFAULT_BUCKET_CAPACITY,
        leak_rate: float = DEFAULT_BUCKET_FILL_RATE,
    ) -> None:
        super().__init__(capacity, leak_rate)
        self._water = 0.0
        self._last_leak = time.time()

    def _leak(self) -> None:
        """漏水。"""
        now = time.time()
        elapsed = now - self._last_leak
        leaked = elapsed * self._fill_rate
        self._water = max(0.0, self._water - leaked)
        self._last_leak = now

    def acquire(self, tokens: float = 1.0) -> bool:
        with self._lock:
            self._leak()
            if self._water + tokens <= self._capacity:
                self._water += tokens
                return True
            return False

    def try_acquire(self, tokens: float = 1.0, timeout: float = 0.0) -> bool:
        deadline = time.time() + timeout
        while True:
            with self._lock:
                self._leak()
                if self._water + tokens <= self._capacity:
                    self._water += tokens
                    return True
            if time.time() >= deadline:
                return False
            time.sleep(0.05)

    def get_state(self) -> dict[str, Any]:
        with self._lock:
            self._leak()
            return {
                "strategy": LimitStrategy.LEAKY_BUCKET.value,
                "capacity": self._capacity,
                "leak_rate": self._fill_rate,
                "current_water": round(self._water, 2),
                "utilization": round(self._water / self._capacity, 4),
            }


class SlidingWindowRateLimiter(RateLimiter):
    """滑动窗口限流器。"""

    def __init__(
        self,
        capacity: float = DEFAULT_BUCKET_CAPACITY,
        window_size: float = 1.0,
    ) -> None:
        super().__init__(capacity, capacity / window_size)
        self._window_size = window_size
        self._requests: deque[float] = deque()

    def _cleanup(self) -> None:
        """清理过期请求。"""
        cutoff = time.time() - self._window_size
        while self._requests and self._requests[0] < cutoff:
            self._requests.popleft()

    def acquire(self, tokens: float = 1.0) -> bool:
        with self._lock:
            self._cleanup()
            if len(self._requests) + tokens <= self._capacity:
                now = time.time()
                for _ in range(int(tokens)):
                    self._requests.append(now)
                return True
            return False

    def try_acquire(self, tokens: float = 1.0, timeout: float = 0.0) -> bool:
        deadline = time.time() + timeout
        while True:
            with self._lock:
                self._cleanup()
                if len(self._requests) + tokens <= self._capacity:
                    now = time.time()
                    for _ in range(int(tokens)):
                        self._requests.append(now)
                    return True
            if time.time() >= deadline:
                return False
            time.sleep(0.05)

    def get_state(self) -> dict[str, Any]:
        with self._lock:
            self._cleanup()
            return {
                "strategy": LimitStrategy.SLIDING_WINDOW.value,
                "capacity": self._capacity,
                "window_size": self._window_size,
                "current_requests": len(self._requests),
                "utilization": round(len(self._requests) / self._capacity, 4),
            }


class FixedWindowRateLimiter(RateLimiter):
    """固定窗口限流器。"""

    def __init__(
        self,
        capacity: float = DEFAULT_BUCKET_CAPACITY,
        window_size: float = 1.0,
    ) -> None:
        super().__init__(capacity, capacity / window_size)
        self._window_size = window_size
        self._window_start = time.time()
        self._count = 0

    def _reset_if_needed(self) -> None:
        """窗口重置。"""
        now = time.time()
        if now - self._window_start >= self._window_size:
            self._window_start = now
            self._count = 0

    def acquire(self, tokens: float = 1.0) -> bool:
        with self._lock:
            self._reset_if_needed()
            if self._count + tokens <= self._capacity:
                self._count += tokens
                return True
            return False

    def try_acquire(self, tokens: float = 1.0, timeout: float = 0.0) -> bool:
        deadline = time.time() + timeout
        while True:
            with self._lock:
                self._reset_if_needed()
                if self._count + tokens <= self._capacity:
                    self._count += tokens
                    return True
            if time.time() >= deadline:
                return False
            time.sleep(0.05)

    def get_state(self) -> dict[str, Any]:
        with self._lock:
            self._reset_if_needed()
            return {
                "strategy": LimitStrategy.FIXED_WINDOW.value,
                "capacity": self._capacity,
                "window_size": self._window_size,
                "current_count": self._count,
                "utilization": round(self._count / self._capacity, 4),
            }


def create_rate_limiter(
    strategy: LimitStrategy,
    capacity: float = DEFAULT_BUCKET_CAPACITY,
    rate: float = DEFAULT_BUCKET_FILL_RATE,
) -> RateLimiter:
    """创建限流器。

    Args:
        strategy: 限流策略。
        capacity: 容量。
        rate: 速率。

    Returns:
        限流器实例。
    """
    if strategy == LimitStrategy.TOKEN_BUCKET:
        return TokenBucketRateLimiter(capacity, rate)
    elif strategy == LimitStrategy.LEAKY_BUCKET:
        return LeakyBucketRateLimiter(capacity, rate)
    elif strategy == LimitStrategy.SLIDING_WINDOW:
        return SlidingWindowRateLimiter(capacity, 1.0 / rate if rate > 0 else 1.0)
    elif strategy == LimitStrategy.FIXED_WINDOW:
        return FixedWindowRateLimiter(capacity, 1.0 / rate if rate > 0 else 1.0)
    else:
        return TokenBucketRateLimiter(capacity, rate)


# ===== 连接池 =====


class ConnectionPool:
    """通用连接池。

    支持任意连接对象的池化管理，包括创建、复用、回收、健康检查。
    """

    def __init__(
        self,
        factory: Callable[[], Any],
        max_size: int = DEFAULT_CONNECTION_POOL_SIZE,
        idle_timeout: float = DEFAULT_CONNECTION_IDLE_TIMEOUT,
        max_lifetime: float = DEFAULT_CONNECTION_MAX_LIFETIME,
        health_check: Optional[Callable[[Any], bool]] = None,
        on_create: Optional[Callable[[Any], None]] = None,
        on_destroy: Optional[Callable[[Any], None]] = None,
    ) -> None:
        """初始化连接池。

        Args:
            factory: 连接创建工厂函数。
            max_size: 最大连接数。
            idle_timeout: 空闲超时（秒）。
            max_lifetime: 最大寿命（秒）。
            health_check: 健康检查函数。
            on_create: 连接创建回调。
            on_destroy: 连接销毁回调。
        """
        self._lock = threading.RLock()
        self._factory = factory
        self._max_size = max_size
        self._idle_timeout = idle_timeout
        self._max_lifetime = max_lifetime
        self._health_check = health_check
        self._on_create = on_create
        self._on_destroy = on_destroy

        # 空闲连接队列
        self._idle: deque[tuple[Any, float, float]] = deque()  # (conn, created, last_used)
        # 活跃连接集合
        self._active: set[int] = set()  # conn id
        self._active_conns: dict[int, Any] = {}
        # 等待队列
        self._waiters: deque[threading.Event] = deque()

        # 统计
        self._stats = PoolStats(pool_type="connection")

    def acquire(self, timeout: float = 30.0) -> Any:
        """获取连接。

        Args:
            timeout: 超时时间。

        Returns:
            连接对象。

        Raises:
            TimeoutError: 获取超时。
        """
        start_time = time.time()
        with self._lock:
            self._stats.acquisitions += 1
            # 尝试从空闲队列获取
            conn = self._try_get_idle()
            if conn is not None:
                self._stats.avg_wait_time = (
                    self._stats.avg_wait_time * (self._stats.acquisitions - 1) +
                    (time.time() - start_time)
                ) / self._stats.acquisitions
                return conn
            # 创建新连接
            if self._stats.total < self._max_size:
                conn = self._create_connection()
                self._stats.avg_wait_time = (
                    self._stats.avg_wait_time * (self._stats.acquisitions - 1) +
                    (time.time() - start_time)
                ) / self._stats.acquisitions
                return conn
            # 等待
            waiter = threading.Event()
            self._waiters.append(waiter)
            self._stats.waiting = len(self._waiters)

        # 等待连接释放
        if not waiter.wait(timeout=timeout):
            with self._lock:
                if waiter in self._waiters:
                    self._waiters.remove(waiter)
                    self._stats.waiting = len(self._waiters)
            self._stats.rejections += 1
            raise TimeoutError(f"获取连接超时（{timeout}s）")

        # 被唤醒后重试
        return self.acquire(timeout=max(0.1, timeout - (time.time() - start_time)))

    def release(self, conn: Any) -> None:
        """释放连接。

        Args:
            conn: 连接对象。
        """
        with self._lock:
            conn_id = id(conn)
            if conn_id not in self._active:
                return
            self._active.discard(conn_id)
            self._active_conns.pop(conn_id, None)
            self._stats.active = len(self._active)
            # 检查连接是否过期
            created_at = getattr(conn, "_pool_created_at", time.time())
            if time.time() - created_at > self._max_lifetime:
                self._destroy_connection(conn)
                self._stats.total = len(self._idle) + len(self._active)
                # 唤醒等待者
                self._notify_waiter()
                return
            # 放回空闲队列
            self._idle.append((conn, created_at, time.time()))
            self._stats.idle = len(self._idle)
            self._stats.total = self._stats.idle + self._stats.active
            # 唤醒等待者
            self._notify_waiter()

    def _try_get_idle(self) -> Optional[Any]:
        """尝试从空闲队列获取连接。"""
        while self._idle:
            conn, created_at, last_used = self._idle.popleft()
            # 检查空闲超时
            if time.time() - last_used > self._idle_timeout:
                self._destroy_connection(conn)
                continue
            # 检查寿命
            if time.time() - created_at > self._max_lifetime:
                self._destroy_connection(conn)
                continue
            # 健康检查
            if self._health_check and not self._health_check(conn):
                self._destroy_connection(conn)
                continue
            # 标记为活跃
            conn_id = id(conn)
            self._active.add(conn_id)
            self._active_conns[conn_id] = conn
            self._stats.active = len(self._active)
            self._stats.idle = len(self._idle)
            return conn
        return None

    def _create_connection(self) -> Any:
        """创建新连接。"""
        conn = self._factory()
        conn._pool_created_at = time.time()
        conn_id = id(conn)
        self._active.add(conn_id)
        self._active_conns[conn_id] = conn
        self._stats.created += 1
        self._stats.active = len(self._active)
        self._stats.total = self._stats.idle + self._stats.active
        if self._on_create:
            try:
                self._on_create(conn)
            except Exception:
                pass
        return conn

    def _destroy_connection(self, conn: Any) -> None:
        """销毁连接。"""
        if self._on_destroy:
            try:
                self._on_destroy(conn)
            except Exception:
                pass
        else:
            # 尝试调用 close 方法
            close_method = getattr(conn, "close", None)
            if close_method:
                try:
                    close_method()
                except Exception:
                    pass
        self._stats.destroyed += 1

    def _notify_waiter(self) -> None:
        """通知等待者。"""
        if self._waiters:
            waiter = self._waiters.popleft()
            self._stats.waiting = len(self._waiters)
            waiter.set()

    def cleanup_idle(self) -> int:
        """清理过期空闲连接。

        Returns:
            清理数量。
        """
        with self._lock:
            count = 0
            remaining: deque[tuple[Any, float, float]] = deque()
            while self._idle:
                conn, created_at, last_used = self._idle.popleft()
                if (
                    time.time() - last_used > self._idle_timeout
                    or time.time() - created_at > self._max_lifetime
                ):
                    self._destroy_connection(conn)
                    count += 1
                else:
                    remaining.append((conn, created_at, last_used))
            self._idle = remaining
            self._stats.idle = len(self._idle)
            self._stats.total = self._stats.idle + self._stats.active
            return count

    def close_all(self) -> int:
        """关闭所有连接。

        Returns:
            关闭数量。
        """
        with self._lock:
            count = 0
            while self._idle:
                conn, _, _ = self._idle.popleft()
                self._destroy_connection(conn)
                count += 1
            for conn in list(self._active_conns.values()):
                self._destroy_connection(conn)
                count += 1
            self._active.clear()
            self._active_conns.clear()
            self._stats.idle = 0
            self._stats.active = 0
            self._stats.total = 0
            return count

    def get_stats(self) -> dict[str, Any]:
        """获取统计。"""
        with self._lock:
            return self._stats.to_dict()


# ===== 线程池管理器 =====


class ThreadPoolManager:
    """线程池管理器。

    封装 ThreadPoolExecutor，提供任务队列监控与动态调整。
    """

    def __init__(
        self,
        max_workers: int = DEFAULT_THREAD_POOL_SIZE,
        thread_name_prefix: str = "worker",
    ) -> None:
        """初始化线程池管理器。

        Args:
            max_workers: 最大工作线程数。
            thread_name_prefix: 线程名前缀。
        """
        self._lock = threading.RLock()
        self._max_workers = max_workers
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix=thread_name_prefix,
        )
        self._stats = PoolStats(pool_type="thread")
        self._active_futures: dict[str, Future] = {}
        self._task_history: deque[dict[str, Any]] = deque(maxlen=1000)

    def submit(
        self,
        fn: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> Future:
        """提交任务。

        Args:
            fn: 任务函数。
            *args: 位置参数。
            **kwargs: 关键字参数。

        Returns:
            Future 对象。
        """
        with self._lock:
            task_id = str(uuid.uuid4())
            self._stats.acquisitions += 1
            start_time = time.time()

            def wrapped() -> Any:
                self._stats.active += 1
                try:
                    result = fn(*args, **kwargs)
                    return result
                finally:
                    self._stats.active -= 1
                    exec_time = time.time() - start_time
                    self._task_history.append({
                        "task_id": task_id,
                        "execution_time": round(exec_time, 4),
                        "status": "completed",
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                    })

            future = self._executor.submit(wrapped)
            self._active_futures[task_id] = future
            self._stats.total = self._stats.active + self._stats.idle
            return future

    def submit_and_wait(
        self,
        fn: Callable,
        *args: Any,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> Any:
        """提交任务并等待结果。

        Args:
            fn: 任务函数。
            *args: 位置参数。
            timeout: 超时。
            **kwargs: 关键字参数。

        Returns:
            任务结果。
        """
        future = self.submit(fn, *args, **kwargs)
        return future.result(timeout=timeout)

    def map(
        self,
        fn: Callable,
        *iterables: Any,
        timeout: Optional[float] = None,
    ) -> list[Any]:
        """批量提交任务。

        Args:
            fn: 任务函数。
            *iterables: 可迭代参数。
            timeout: 超时。

        Returns:
            结果列表。
        """
        return list(self._executor.map(fn, *iterables, timeout=timeout))

    def resize(self, max_workers: int) -> None:
        """调整线程池大小。

        注意：ThreadPoolExecutor 不支持动态调整，此方法会重建线程池。

        Args:
            max_workers: 新的最大线程数。
        """
        with self._lock:
            # 等待当前任务完成
            self._executor.shutdown(wait=True)
            self._max_workers = max_workers
            self._executor = ThreadPoolExecutor(
                max_workers=max_workers,
                thread_name_prefix="worker",
            )

    def shutdown(self, wait: bool = True) -> None:
        """关闭线程池。

        Args:
            wait: 是否等待任务完成。
        """
        with self._lock:
            self._executor.shutdown(wait=wait)

    def get_stats(self) -> dict[str, Any]:
        """获取统计。"""
        with self._lock:
            stats = self._stats.to_dict()
            stats["max_workers"] = self._max_workers
            stats["pending_tasks"] = len(self._active_futures)
            stats["task_history_size"] = len(self._task_history)
            return stats

    def get_task_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """获取任务历史。

        Args:
            limit: 返回数量上限。

        Returns:
            任务历史列表。
        """
        with self._lock:
            return list(self._task_history)[-limit:]


# ===== 协程池管理器 =====


class CoroutinePoolManager:
    """协程池管理器。

    管理异步任务，限制并发协程数。
    """

    def __init__(
        self,
        max_concurrency: int = DEFAULT_COROUTINE_POOL_SIZE,
    ) -> None:
        """初始化协程池管理器。

        Args:
            max_concurrency: 最大并发数。
        """
        self._lock = threading.RLock()
        self._max_concurrency = max_concurrency
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._stats = PoolStats(pool_type="coroutine")
        self._active_tasks: set[asyncio.Task] = set()

    async def submit(self, coro: Any) -> Any:
        """提交协程任务。

        Args:
            coro: 协程对象。

        Returns:
            协程结果。
        """
        async with self._semaphore:
            with self._lock:
                self._stats.acquisitions += 1
                self._stats.active += 1
            try:
                task = asyncio.ensure_future(coro)
                self._active_tasks.add(task)
                result = await task
                return result
            finally:
                with self._lock:
                    self._stats.active -= 1
                    self._stats.total = self._stats.active + self._stats.idle

    async def submit_batch(
        self,
        coros: list[Any],
        return_exceptions: bool = False,
    ) -> list[Any]:
        """批量提交协程任务。

        Args:
            coros: 协程列表。
            return_exceptions: 是否返回异常而非抛出。

        Returns:
            结果列表。
        """
        tasks = [self.submit(c) for c in coros]
        return await asyncio.gather(*tasks, return_exceptions=return_exceptions)

    def get_stats(self) -> dict[str, Any]:
        """获取统计。"""
        with self._lock:
            stats = self._stats.to_dict()
            stats["max_concurrency"] = self._max_concurrency
            stats["active_tasks"] = len(self._active_tasks)
            return stats


# ===== 主资源管理器类 =====


class ResourceManager:
    """资源管理器。

    统一管理系统资源，提供监控、配额、池化、限流能力。

    功能包括：
        - CPU/内存/磁盘/网络资源监控
        - 资源配额管理与隔离
        - 连接池管理
        - 线程池管理
        - 协程池管理
        - 限流策略（令牌桶/漏桶/滑动窗口/固定窗口）
        - 资源告警
        - 资源使用报告
        - 容量规划与扩容建议

    线程安全：所有公共方法通过 RLock 保护。

    典型用法：
        manager = ResourceManager()
        manager.start_monitoring()
        pool = manager.get_connection_pool("db", factory)
        conn = pool.acquire()
        try:
            ...
        finally:
            pool.release(conn)
        snapshot = manager.get_snapshot()
        report = manager.generate_report()
    """

    def __init__(
        self,
        sample_interval: float = DEFAULT_SAMPLE_INTERVAL,
        history_capacity: int = DEFAULT_HISTORY_CAPACITY,
        quotas: Optional[dict[ResourceType, float]] = None,
        enable_monitoring: bool = True,
    ) -> None:
        """初始化资源管理器。

        Args:
            sample_interval: 采样间隔（秒）。
            history_capacity: 历史保留采样点数。
            quotas: 资源配额。
            enable_monitoring: 是否启用监控。
        """
        self._lock = threading.RLock()
        self._sample_interval = sample_interval
        self._history_capacity = history_capacity
        self._enable_monitoring = enable_monitoring

        # 资源配额
        self._quotas: dict[ResourceType, ResourceQuota] = {}
        quota_limits = dict(DEFAULT_QUOTA_LIMITS)
        if quotas:
            quota_limits.update(quotas)
        for rtype, limit in quota_limits.items():
            self._quotas[rtype] = ResourceQuota(
                resource_type=rtype,
                limit=limit,
                unit=self._get_resource_unit(rtype),
            )

        # 历史采样
        self._history: deque[ResourceSnapshot] = deque(maxlen=history_capacity)

        # 连接池注册表
        self._connection_pools: dict[str, ConnectionPool] = {}
        # 线程池注册表
        self._thread_pools: dict[str, ThreadPoolManager] = {}
        # 协程池注册表
        self._coroutine_pools: dict[str, CoroutinePoolManager] = {}
        # 限流器注册表
        self._rate_limiters: dict[str, RateLimiter] = {}

        # 告警历史
        self._alerts: deque[ResourceAlert] = deque(maxlen=500)

        # 监控线程
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False

        # 统计
        self._stats = {
            "total_snapshots": 0,
            "total_alerts": 0,
            "monitoring_uptime": 0.0,
        }
        self._monitor_start_time = 0.0

    # ===== 监控 =====

    def start_monitoring(self) -> None:
        """启动资源监控。"""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._monitor_start_time = time.time()
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                daemon=True,
            )
            self._monitor_thread.start()

    def stop_monitoring(self) -> None:
        """停止资源监控。"""
        with self._lock:
            self._running = False
            if self._monitor_thread:
                self._monitor_thread.join(timeout=5.0)
                self._monitor_thread = None
            if self._monitor_start_time > 0:
                self._stats["monitoring_uptime"] = time.time() - self._monitor_start_time

    def _monitor_loop(self) -> None:
        """监控循环。"""
        while self._running:
            try:
                snapshot = self._take_snapshot()
                with self._lock:
                    self._history.append(snapshot)
                    self._stats["total_snapshots"] += 1
                    # 更新配额当前值
                    self._update_quotas(snapshot)
                    # 检查告警
                    self._check_alerts(snapshot)
            except Exception:  # pragma: no cover
                pass
            time.sleep(self._sample_interval)

    def _take_snapshot(self) -> ResourceSnapshot:
        """采集资源快照。"""
        snapshot = ResourceSnapshot(timestamp=time.time())
        # 尝试使用 psutil（可选）
        try:
            import psutil  # type: ignore
            snapshot.cpu_percent = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            snapshot.memory_percent = mem.percent
            snapshot.memory_used_mb = mem.used / (1024 * 1024)
            snapshot.memory_total_mb = mem.total / (1024 * 1024)
            disk = psutil.disk_usage("/")
            snapshot.disk_percent = disk.percent
            snapshot.disk_used_gb = disk.used / (1024 ** 3)
            snapshot.disk_total_gb = disk.total / (1024 ** 3)
            net = psutil.net_io_counters()
            snapshot.network_bytes_sent = net.bytes_sent
            snapshot.network_bytes_recv = net.bytes_recv
        except ImportError:
            # psutil 不可用，使用 os 模块获取部分信息
            snapshot.cpu_percent = 0.0
            # 内存信息（仅 Unix 可用）
            try:
                import resource
                mem = resource.getrusage(resource.RUSAGE_SELF)
                snapshot.memory_used_mb = mem.ru_maxrss / 1024  # KB -> MB
            except (ImportError, AttributeError):
                pass
            # 磁盘信息
            try:
                disk_stat = os.statvfs(".")
                snapshot.disk_total_gb = (disk_stat.f_blocks * disk_stat.f_frsize) / (1024 ** 3)
                snapshot.disk_used_gb = snapshot.disk_total_gb - (
                    disk_stat.f_bavail * disk_stat.f_frsize / (1024 ** 3)
                )
                if snapshot.disk_total_gb > 0:
                    snapshot.disk_percent = (
                        snapshot.disk_used_gb / snapshot.disk_total_gb * 100
                    )
            except (OSError, AttributeError):
                pass

        # 线程数
        snapshot.thread_count = threading.active_count()
        # 连接数
        snapshot.connection_count = sum(
            pool._stats.total for pool in self._connection_pools.values()
        )
        # 协程数
        snapshot.coroutine_count = sum(
            pool._stats.active for pool in self._coroutine_pools.values()
        )

        return snapshot

    def get_snapshot(self) -> ResourceSnapshot:
        """获取当前资源快照。

        Returns:
            资源快照。
        """
        with self._lock:
            if self._history:
                return self._history[-1]
            return self._take_snapshot()

    def get_history(self, limit: int = 100) -> list[ResourceSnapshot]:
        """获取历史快照。

        Args:
            limit: 返回数量上限。

        Returns:
            历史快照列表。
        """
        with self._lock:
            return list(self._history)[-limit:]

    # ===== 配额管理 =====

    def _update_quotas(self, snapshot: ResourceSnapshot) -> None:
        """更新配额当前值。"""
        self._quotas[ResourceType.CPU].current = snapshot.cpu_percent
        self._quotas[ResourceType.MEMORY].current = snapshot.memory_percent
        self._quotas[ResourceType.DISK].current = snapshot.disk_percent
        self._quotas[ResourceType.CONNECTION].current = snapshot.connection_count
        self._quotas[ResourceType.THREAD].current = snapshot.thread_count
        self._quotas[ResourceType.COROUTINE].current = snapshot.coroutine_count

    def set_quota(self, resource_type: ResourceType, limit: float) -> None:
        """设置资源配额。

        Args:
            resource_type: 资源类型。
            limit: 配额上限。
        """
        with self._lock:
            if resource_type in self._quotas:
                self._quotas[resource_type].limit = limit
            else:
                self._quotas[resource_type] = ResourceQuota(
                    resource_type=resource_type,
                    limit=limit,
                    unit=self._get_resource_unit(resource_type),
                )

    def get_quota(self, resource_type: ResourceType) -> Optional[ResourceQuota]:
        """获取资源配额。

        Args:
            resource_type: 资源类型。

        Returns:
            资源配额。
        """
        with self._lock:
            return self._quotas.get(resource_type)

    def get_all_quotas(self) -> dict[str, dict[str, Any]]:
        """获取所有配额。

        Returns:
            配额字典。
        """
        with self._lock:
            return {
                rtype.value: quota.to_dict()
                for rtype, quota in self._quotas.items()
            }

    def check_quota(self, resource_type: ResourceType, amount: float = 0) -> bool:
        """检查资源是否可用。

        Args:
            resource_type: 资源类型。
            amount: 需要的资源量。

        Returns:
            是否可用。
        """
        with self._lock:
            quota = self._quotas.get(resource_type)
            if quota is None:
                return True
            return quota.current + amount <= quota.limit

    def reserve(self, resource_type: ResourceType, amount: float) -> bool:
        """预留资源。

        Args:
            resource_type: 资源类型。
            amount: 预留量。

        Returns:
            是否成功。
        """
        with self._lock:
            quota = self._quotas.get(resource_type)
            if quota is None:
                return False
            if quota.current + quota.reserved + amount > quota.limit:
                return False
            quota.reserved += amount
            return True

    def release_reservation(
        self, resource_type: ResourceType, amount: float
    ) -> None:
        """释放预留资源。

        Args:
            resource_type: 资源类型。
            amount: 释放量。
        """
        with self._lock:
            quota = self._quotas.get(resource_type)
            if quota:
                quota.reserved = max(0, quota.reserved - amount)

    def _get_resource_unit(self, rtype: ResourceType) -> str:
        """获取资源单位。"""
        units = {
            ResourceType.CPU: "%",
            ResourceType.MEMORY: "%",
            ResourceType.DISK: "%",
            ResourceType.NETWORK: "bytes/s",
            ResourceType.CONNECTION: "count",
            ResourceType.THREAD: "count",
            ResourceType.COROUTINE: "count",
        }
        return units.get(rtype, "")

    # ===== 告警 =====

    def _check_alerts(self, snapshot: ResourceSnapshot) -> None:
        """检查告警条件。"""
        # CPU 告警
        if snapshot.cpu_percent >= DEFAULT_CPU_EMERGENCY:
            self._raise_alert(
                AlertLevel.EMERGENCY, ResourceType.CPU,
                f"CPU 使用率紧急: {snapshot.cpu_percent:.1f}%",
                snapshot.cpu_percent, DEFAULT_CPU_EMERGENCY,
            )
        elif snapshot.cpu_percent >= DEFAULT_CPU_CRITICAL:
            self._raise_alert(
                AlertLevel.CRITICAL, ResourceType.CPU,
                f"CPU 使用率严重: {snapshot.cpu_percent:.1f}%",
                snapshot.cpu_percent, DEFAULT_CPU_CRITICAL,
            )
        elif snapshot.cpu_percent >= DEFAULT_CPU_WARNING:
            self._raise_alert(
                AlertLevel.WARNING, ResourceType.CPU,
                f"CPU 使用率警告: {snapshot.cpu_percent:.1f}%",
                snapshot.cpu_percent, DEFAULT_CPU_WARNING,
            )

        # 内存告警
        if snapshot.memory_percent >= DEFAULT_MEM_EMERGENCY:
            self._raise_alert(
                AlertLevel.EMERGENCY, ResourceType.MEMORY,
                f"内存使用率紧急: {snapshot.memory_percent:.1f}%",
                snapshot.memory_percent, DEFAULT_MEM_EMERGENCY,
            )
        elif snapshot.memory_percent >= DEFAULT_MEM_CRITICAL:
            self._raise_alert(
                AlertLevel.CRITICAL, ResourceType.MEMORY,
                f"内存使用率严重: {snapshot.memory_percent:.1f}%",
                snapshot.memory_percent, DEFAULT_MEM_CRITICAL,
            )
        elif snapshot.memory_percent >= DEFAULT_MEM_WARNING:
            self._raise_alert(
                AlertLevel.WARNING, ResourceType.MEMORY,
                f"内存使用率警告: {snapshot.memory_percent:.1f}%",
                snapshot.memory_percent, DEFAULT_MEM_WARNING,
            )

        # 磁盘告警
        if snapshot.disk_percent >= DEFAULT_DISK_EMERGENCY:
            self._raise_alert(
                AlertLevel.EMERGENCY, ResourceType.DISK,
                f"磁盘使用率紧急: {snapshot.disk_percent:.1f}%",
                snapshot.disk_percent, DEFAULT_DISK_EMERGENCY,
            )
        elif snapshot.disk_percent >= DEFAULT_DISK_CRITICAL:
            self._raise_alert(
                AlertLevel.CRITICAL, ResourceType.DISK,
                f"磁盘使用率严重: {snapshot.disk_percent:.1f}%",
                snapshot.disk_percent, DEFAULT_DISK_CRITICAL,
            )

        # 配额超限告警
        for rtype, quota in self._quotas.items():
            if quota.is_exceeded:
                self._raise_alert(
                    AlertLevel.WARNING, rtype,
                    f"{rtype.value} 资源配额超限: "
                    f"{quota.current:.1f}/{quota.limit:.1f} {quota.unit}",
                    quota.current, quota.limit,
                )

    def _raise_alert(
        self,
        level: AlertLevel,
        resource_type: ResourceType,
        message: str,
        value: float,
        threshold: float,
    ) -> None:
        """产生告警。"""
        alert = ResourceAlert(
            id=str(uuid.uuid4()),
            level=level,
            resource_type=resource_type,
            message=message,
            value=value,
            threshold=threshold,
            timestamp=datetime.utcnow().isoformat() + "Z",
        )
        self._alerts.append(alert)
        self._stats["total_alerts"] += 1

    def get_alerts(
        self,
        level: Optional[AlertLevel] = None,
        limit: int = 100,
    ) -> list[ResourceAlert]:
        """获取告警。

        Args:
            level: 告警级别过滤。
            limit: 返回数量上限。

        Returns:
            告警列表。
        """
        with self._lock:
            alerts = list(self._alerts)
            if level:
                alerts = [a for a in alerts if a.level == level]
            return list(reversed(alerts))[:limit]

    def clear_alerts(self) -> int:
        """清空告警。

        Returns:
            清除数量。
        """
        with self._lock:
            count = len(self._alerts)
            self._alerts.clear()
            return count

    # ===== 连接池管理 =====

    def register_connection_pool(
        self,
        name: str,
        factory: Callable[[], Any],
        max_size: int = DEFAULT_CONNECTION_POOL_SIZE,
        **kwargs: Any,
    ) -> ConnectionPool:
        """注册连接池。

        Args:
            name: 池名称。
            factory: 连接创建工厂。
            max_size: 最大连接数。
            **kwargs: 其他参数。

        Returns:
            连接池实例。
        """
        with self._lock:
            pool = ConnectionPool(
                factory=factory,
                max_size=max_size,
                **kwargs,
            )
            self._connection_pools[name] = pool
            return pool

    def get_connection_pool(self, name: str) -> Optional[ConnectionPool]:
        """获取连接池。

        Args:
            name: 池名称。

        Returns:
            连接池实例。
        """
        with self._lock:
            return self._connection_pools.get(name)

    def cleanup_all_pools(self) -> dict[str, int]:
        """清理所有连接池的空闲连接。

        Returns:
            各池清理数量。
        """
        with self._lock:
            result: dict[str, int] = {}
            for name, pool in self._connection_pools.items():
                result[name] = pool.cleanup_idle()
            return result

    def close_all_pools(self) -> dict[str, int]:
        """关闭所有连接池。

        Returns:
            各池关闭数量。
        """
        with self._lock:
            result: dict[str, int] = {}
            for name, pool in self._connection_pools.items():
                result[name] = pool.close_all()
            return result

    # ===== 线程池管理 =====

    def register_thread_pool(
        self,
        name: str,
        max_workers: int = DEFAULT_THREAD_POOL_SIZE,
    ) -> ThreadPoolManager:
        """注册线程池。

        Args:
            name: 池名称。
            max_workers: 最大线程数。

        Returns:
            线程池管理器实例。
        """
        with self._lock:
            pool = ThreadPoolManager(max_workers=max_workers)
            self._thread_pools[name] = pool
            return pool

    def get_thread_pool(self, name: str) -> Optional[ThreadPoolManager]:
        """获取线程池。

        Args:
            name: 池名称。

        Returns:
            线程池管理器实例。
        """
        with self._lock:
            return self._thread_pools.get(name)

    # ===== 协程池管理 =====

    def register_coroutine_pool(
        self,
        name: str,
        max_concurrency: int = DEFAULT_COROUTINE_POOL_SIZE,
    ) -> CoroutinePoolManager:
        """注册协程池。

        Args:
            name: 池名称。
            max_concurrency: 最大并发数。

        Returns:
            协程池管理器实例。
        """
        with self._lock:
            pool = CoroutinePoolManager(max_concurrency=max_concurrency)
            self._coroutine_pools[name] = pool
            return pool

    def get_coroutine_pool(self, name: str) -> Optional[CoroutinePoolManager]:
        """获取协程池。

        Args:
            name: 池名称。

        Returns:
            协程池管理器实例。
        """
        with self._lock:
            return self._coroutine_pools.get(name)

    # ===== 限流器管理 =====

    def register_rate_limiter(
        self,
        name: str,
        strategy: LimitStrategy = LimitStrategy.TOKEN_BUCKET,
        capacity: float = DEFAULT_BUCKET_CAPACITY,
        rate: float = DEFAULT_BUCKET_FILL_RATE,
    ) -> RateLimiter:
        """注册限流器。

        Args:
            name: 限流器名称。
            strategy: 限流策略。
            capacity: 容量。
            rate: 速率。

        Returns:
            限流器实例。
        """
        with self._lock:
            limiter = create_rate_limiter(strategy, capacity, rate)
            self._rate_limiters[name] = limiter
            return limiter

    def get_rate_limiter(self, name: str) -> Optional[RateLimiter]:
        """获取限流器。

        Args:
            name: 限流器名称。

        Returns:
            限流器实例。
        """
        with self._lock:
            return self._rate_limiters.get(name)

    def check_rate(self, name: str, tokens: float = 1.0) -> bool:
        """检查限流。

        Args:
            name: 限流器名称。
            tokens: 请求令牌数。

        Returns:
            是否允许。
        """
        with self._lock:
            limiter = self._rate_limiters.get(name)
            if limiter is None:
                return True
            return limiter.acquire(tokens)

    # ===== 报告 =====

    def generate_report(self) -> dict[str, Any]:
        """生成资源使用报告。

        Returns:
            报告字典。
        """
        with self._lock:
            snapshot = self.get_snapshot()
            history = list(self._history)

            # 计算历史统计
            cpu_values = [s.cpu_percent for s in history] if history else []
            mem_values = [s.memory_percent for s in history] if history else []
            disk_values = [s.disk_percent for s in history] if history else []

            report: dict[str, Any] = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "current": snapshot.to_dict(),
                "history_stats": {
                    "sample_count": len(history),
                    "cpu": {
                        "avg": round(sum(cpu_values) / len(cpu_values), 2) if cpu_values else 0,
                        "max": round(max(cpu_values), 2) if cpu_values else 0,
                        "min": round(min(cpu_values), 2) if cpu_values else 0,
                    },
                    "memory": {
                        "avg": round(sum(mem_values) / len(mem_values), 2) if mem_values else 0,
                        "max": round(max(mem_values), 2) if mem_values else 0,
                        "min": round(min(mem_values), 2) if mem_values else 0,
                    },
                    "disk": {
                        "avg": round(sum(disk_values) / len(disk_values), 2) if disk_values else 0,
                        "max": round(max(disk_values), 2) if disk_values else 0,
                        "min": round(min(disk_values), 2) if disk_values else 0,
                    },
                },
                "quotas": self.get_all_quotas(),
                "pools": {
                    "connection": {
                        name: pool.get_stats()
                        for name, pool in self._connection_pools.items()
                    },
                    "thread": {
                        name: pool.get_stats()
                        for name, pool in self._thread_pools.items()
                    },
                    "coroutine": {
                        name: pool.get_stats()
                        for name, pool in self._coroutine_pools.items()
                    },
                },
                "rate_limiters": {
                    name: limiter.get_state()
                    for name, limiter in self._rate_limiters.items()
                },
                "alerts": {
                    "total": len(self._alerts),
                    "recent": [a.to_dict() for a in list(self._alerts)[-10:]],
                },
                "stats": dict(self._stats),
            }
            return report

    def get_capacity_suggestions(self) -> list[str]:
        """获取容量规划建议。

        基于当前资源使用情况生成扩容/缩容建议。

        Returns:
            建议列表。
        """
        with self._lock:
            suggestions: list[str] = []
            snapshot = self.get_snapshot()
            history = list(self._history)

            # CPU 建议
            if history:
                avg_cpu = sum(s.cpu_percent for s in history) / len(history)
                if avg_cpu > 80:
                    suggestions.append(
                        f"⚠️ CPU 平均使用率 {avg_cpu:.1f}%，建议扩容 CPU 资源。"
                    )
                elif avg_cpu < 20:
                    suggestions.append(
                        f"📋 CPU 平均使用率 {avg_cpu:.1f}%，可考虑缩容以节省成本。"
                    )

            # 内存建议
            if snapshot.memory_percent > 85:
                suggestions.append(
                    f"⚠️ 内存使用率 {snapshot.memory_percent:.1f}%，"
                    "建议增加内存或优化内存使用。"
                )
            if history:
                avg_mem = sum(s.memory_percent for s in history) / len(history)
                if avg_mem > 75:
                    suggestions.append(
                        f"📋 内存平均使用率 {avg_mem:.1f}%，接近告警阈值，"
                        "建议提前扩容。"
                    )

            # 磁盘建议
            if snapshot.disk_percent > 85:
                suggestions.append(
                    f"⚠️ 磁盘使用率 {snapshot.disk_percent:.1f}%，"
                    "建议清理磁盘或扩容存储。"
                )

            # 连接池建议
            for name, pool in self._connection_pools.items():
                stats = pool.get_stats()
                if stats["waiting"] > 0:
                    suggestions.append(
                        f"⚠️ 连接池 '{name}' 有 {stats['waiting']} 个等待者，"
                        f"建议增大连接池大小（当前 {stats['total']}）。"
                    )
                if stats["rejections"] > 0:
                    suggestions.append(
                        f"⚠️ 连接池 '{name}' 累计拒绝 {stats['rejections']} 次请求，"
                        "建议增大池大小或优化连接使用。"
                    )

            # 线程池建议
            for name, pool in self._thread_pools.items():
                stats = pool.get_stats()
                if stats["active"] >= stats.get("max_workers", 10) * 0.9:
                    suggestions.append(
                        f"⚠️ 线程池 '{name}' 活跃线程 {stats['active']}，"
                        "接近上限，建议增大线程池。"
                    )

            # 限流器建议
            for name, limiter in self._rate_limiters.items():
                state = limiter.get_state()
                if state.get("utilization", 0) > 0.9:
                    suggestions.append(
                        f"⚠️ 限流器 '{name}' 利用率 {state['utilization']:.1%}，"
                        "接近上限，建议增大容量。"
                    )

            if not suggestions:
                suggestions.append("✅ 当前资源配置合理，无需调整。")

            return suggestions

    def get_stats(self) -> dict[str, Any]:
        """获取统计。"""
        with self._lock:
            return dict(self._stats)

    def get_config(self) -> dict[str, Any]:
        """获取配置。"""
        with self._lock:
            return {
                "sample_interval": self._sample_interval,
                "history_capacity": self._history_capacity,
                "enable_monitoring": self._enable_monitoring,
                "monitoring_running": self._running,
                "quotas": self.get_all_quotas(),
                "pool_counts": {
                    "connection": len(self._connection_pools),
                    "thread": len(self._thread_pools),
                    "coroutine": len(self._coroutine_pools),
                    "rate_limiter": len(self._rate_limiters),
                },
            }

    def shutdown(self) -> None:
        """关闭资源管理器，释放所有资源。"""
        with self._lock:
            self.stop_monitoring()
            # 关闭所有连接池
            for pool in self._connection_pools.values():
                pool.close_all()
            # 关闭所有线程池
            for pool in self._thread_pools.values():
                pool.shutdown(wait=False)
            # 清空注册表
            self._connection_pools.clear()
            self._thread_pools.clear()
            self._coroutine_pools.clear()
            self._rate_limiters.clear()


# ===== 模块级便捷函数 =====


_global_manager: Optional[ResourceManager] = None
_global_lock = threading.Lock()


def get_resource_manager() -> ResourceManager:
    """获取全局资源管理器实例。

    Returns:
        全局 ResourceManager 实例。
    """
    global _global_manager
    with _global_lock:
        if _global_manager is None:
            _global_manager = ResourceManager()
        return _global_manager


def rate_limited(
    limiter_name: str,
    tokens: float = 1.0,
) -> Callable:
    """限流装饰器。

    Args:
        limiter_name: 限流器名称。
        tokens: 请求令牌数。

    Returns:
        装饰器函数。
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            manager = get_resource_manager()
            limiter = manager.get_rate_limiter(limiter_name)
            if limiter is None:
                return func(*args, **kwargs)
            if not limiter.acquire(tokens):
                raise RuntimeError(
                    f"请求被限流（限流器: {limiter_name}, 令牌: {tokens}）"
                )
            return func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator


def with_quota_check(
    resource_type: ResourceType,
    amount: float = 0,
) -> Callable:
    """配额检查装饰器。

    Args:
        resource_type: 资源类型。
        amount: 需要的资源量。

    Returns:
        装饰器函数。
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            manager = get_resource_manager()
            if not manager.check_quota(resource_type, amount):
                raise RuntimeError(
                    f"资源配额不足（类型: {resource_type.value}, 需要: {amount}）"
                )
            return func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator
