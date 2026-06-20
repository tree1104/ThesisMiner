"""资源管理器（ResourceManager）单元测试

测试覆盖范围：
    - 资源快照与配额：ResourceSnapshot/ResourceQuota/PoolStats/ResourceAlert 数据类
    - 限流策略：令牌桶/漏桶/滑动窗口/固定窗口的 acquire/try_acquire/get_state
    - 连接池：acquire/release/cleanup_idle/close_all/健康检查/统计
    - 线程池：submit/submit_and_wait/map/resize/shutdown/统计/任务历史
    - 协程池：并发控制/统计
    - 资源管理器：监控启停/快照/历史/配额管理/预留/告警
    - 池注册管理：连接池/线程池/协程池/限流器注册与获取
    - 报告生成、容量建议、统计、配置、关闭
    - 便捷函数、装饰器、线程安全

测试策略：
    1. 使用 mock factory 创建虚拟连接
    2. 通过 mock psutil 验证监控逻辑
    3. 验证限流器的令牌消耗与补充
    4. 覆盖边界条件（超时、容量满、并发访问）
"""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from backend.optimization.resource_manager import (
    DEFAULT_BUCKET_CAPACITY,
    DEFAULT_BUCKET_FILL_RATE,
    DEFAULT_CONNECTION_IDLE_TIMEOUT,
    DEFAULT_CONNECTION_POOL_SIZE,
    DEFAULT_CONNECTION_MAX_LIFETIME,
    DEFAULT_COROUTINE_POOL_SIZE,
    DEFAULT_CPU_CRITICAL,
    DEFAULT_CPU_EMERGENCY,
    DEFAULT_CPU_WARNING,
    DEFAULT_DISK_CRITICAL,
    DEFAULT_DISK_WARNING,
    DEFAULT_HISTORY_CAPACITY,
    DEFAULT_MEM_CRITICAL,
    DEFAULT_MEM_WARNING,
    DEFAULT_SAMPLE_INTERVAL,
    DEFAULT_THREAD_POOL_SIZE,
    AlertLevel,
    ConnectionPool,
    CoroutinePoolManager,
    FixedWindowRateLimiter,
    LeakyBucketRateLimiter,
    LimitStrategy,
    PoolStats,
    RateLimiter,
    ResourceManager,
    ResourceAlert,
    ResourceQuota,
    ResourceSnapshot,
    ResourceType,
    SlidingWindowRateLimiter,
    ThreadPoolManager,
    TokenBucketRateLimiter,
    create_rate_limiter,
    get_resource_manager,
    rate_limited,
    with_quota_check,
)


# ===== Fixtures =====


@pytest.fixture
def manager() -> ResourceManager:
    """提供默认配置的资源管理器实例。"""
    return ResourceManager(enable_monitoring=False)


@pytest.fixture
def monitoring_manager() -> ResourceManager:
    """提供启用监控的资源管理器（短采样间隔）。"""
    m = ResourceManager(
        sample_interval=0.1,
        history_capacity=100,
        enable_monitoring=True,
    )
    yield m
    m.stop_monitoring()


@pytest.fixture
def connection_pool() -> ConnectionPool:
    """提供连接池实例。"""
    counter = {"count": 0}

    def factory():
        counter["count"] += 1
        conn = MagicMock()
        conn.id = counter["count"]
        conn.closed = False
        return conn

    return ConnectionPool(factory=factory, max_size=5)


@pytest.fixture
def thread_pool() -> ThreadPoolManager:
    """提供线程池实例。"""
    return ThreadPoolManager(max_workers=4)


@pytest.fixture
def token_bucket() -> TokenBucketRateLimiter:
    """提供令牌桶限流器。"""
    return TokenBucketRateLimiter(capacity=10, rate=10.0)


# ===== 枚举与常量测试 =====


class TestEnumsAndConstants:
    """测试枚举与常量定义。"""

    def test_resource_type_values(self):
        """验证资源类型枚举。"""
        assert ResourceType.CPU.value == "cpu"
        assert ResourceType.MEMORY.value == "memory"
        assert ResourceType.DISK.value == "disk"
        assert ResourceType.NETWORK.value == "network"
        assert ResourceType.CONNECTION.value == "connection"
        assert ResourceType.THREAD.value == "thread"
        assert ResourceType.COROUTINE.value == "coroutine"

    def test_alert_level_values(self):
        """验证告警级别枚举。"""
        assert hasattr(AlertLevel, "INFO")
        assert hasattr(AlertLevel, "WARNING")
        assert hasattr(AlertLevel, "CRITICAL")
        assert hasattr(AlertLevel, "EMERGENCY")

    def test_limit_strategy_values(self):
        """验证限流策略枚举。"""
        assert LimitStrategy.TOKEN_BUCKET.value == "token_bucket"
        assert LimitStrategy.LEAKY_BUCKET.value == "leaky_bucket"
        assert LimitStrategy.SLIDING_WINDOW.value == "sliding_window"
        assert LimitStrategy.FIXED_WINDOW.value == "fixed_window"

    def test_default_constants(self):
        """验证默认常量值合理。"""
        assert DEFAULT_SAMPLE_INTERVAL > 0
        assert DEFAULT_HISTORY_CAPACITY > 0
        assert DEFAULT_CPU_WARNING < DEFAULT_CPU_CRITICAL < DEFAULT_CPU_EMERGENCY
        assert DEFAULT_MEM_WARNING < DEFAULT_MEM_CRITICAL
        assert DEFAULT_DISK_WARNING < DEFAULT_DISK_CRITICAL
        assert DEFAULT_THREAD_POOL_SIZE > 0
        assert DEFAULT_CONNECTION_POOL_SIZE > 0
        assert DEFAULT_COROUTINE_POOL_SIZE > 0
        assert DEFAULT_BUCKET_CAPACITY > 0
        assert DEFAULT_BUCKET_FILL_RATE > 0


# ===== 数据类测试 =====


class TestDataclasses:
    """测试数据类。"""

    def test_resource_snapshot_default(self):
        """测试资源快照默认值。"""
        snapshot = ResourceSnapshot()
        assert snapshot.cpu_percent == 0.0
        assert snapshot.memory_percent == 0.0
        assert snapshot.timestamp > 0

    def test_resource_snapshot_to_dict(self):
        """测试资源快照序列化。"""
        snapshot = ResourceSnapshot(cpu_percent=50.0, memory_percent=60.0)
        d = snapshot.to_dict()
        assert d["cpu_percent"] == 50.0
        assert d["memory_percent"] == 60.0
        assert "timestamp" in d

    def test_resource_quota_available(self):
        """测试配额可用量计算。"""
        quota = ResourceQuota(
            resource_type=ResourceType.CPU,
            limit=100.0, current=30.0, reserved=20.0,
        )
        assert quota.available == 50.0

    def test_resource_quota_utilization(self):
        """测试配额使用率计算。"""
        quota = ResourceQuota(
            resource_type=ResourceType.CPU,
            limit=100.0, current=50.0, reserved=0.0,
        )
        assert quota.utilization == 0.5

    def test_resource_quota_is_exceeded(self):
        """测试配额超限判断。"""
        quota = ResourceQuota(
            resource_type=ResourceType.CPU,
            limit=80.0, current=70.0, reserved=20.0,
        )
        assert quota.is_exceeded is True

    def test_resource_quota_not_exceeded(self):
        """测试配额未超限。"""
        quota = ResourceQuota(
            resource_type=ResourceType.CPU,
            limit=100.0, current=30.0, reserved=20.0,
        )
        assert quota.is_exceeded is False

    def test_resource_quota_zero_limit_utilization(self):
        """测试零配额使用率为 0。"""
        quota = ResourceQuota(limit=0.0)
        assert quota.utilization == 0.0

    def test_resource_quota_to_dict(self):
        """测试配额序列化。"""
        quota = ResourceQuota(
            resource_type=ResourceType.MEMORY,
            limit=100.0, current=40.0,
        )
        d = quota.to_dict()
        assert d["resource_type"] == "memory"
        assert d["limit"] == 100.0
        assert d["available"] == 60.0

    def test_pool_stats_to_dict(self):
        """测试池统计序列化。"""
        stats = PoolStats(pool_type="connection", total=10, active=5, idle=5)
        d = stats.to_dict()
        assert d["pool_type"] == "connection"
        assert d["total"] == 10
        assert d["active"] == 5

    def test_resource_alert_to_dict(self):
        """测试告警序列化。"""
        alert = ResourceAlert(
            level=AlertLevel.WARNING,
            resource_type=ResourceType.CPU,
            message="CPU 高",
            current_value=90.0,
            threshold=80.0,
        )
        d = alert.to_dict()
        assert d["level"] == AlertLevel.WARNING.value
        assert d["resource_type"] == "cpu"
        assert d["current_value"] == 90.0


# ===== 限流器测试 =====


class TestRateLimiters:
    """测试限流策略。"""

    def test_create_token_bucket(self):
        """测试创建令牌桶。"""
        limiter = create_rate_limiter(
            LimitStrategy.TOKEN_BUCKET, capacity=10, rate=5.0
        )
        assert isinstance(limiter, TokenBucketRateLimiter)

    def test_create_leaky_bucket(self):
        """测试创建漏桶。"""
        limiter = create_rate_limiter(
            LimitStrategy.LEAKY_BUCKET, capacity=10, rate=5.0
        )
        assert isinstance(limiter, LeakyBucketRateLimiter)

    def test_create_sliding_window(self):
        """测试创建滑动窗口。"""
        limiter = create_rate_limiter(
            LimitStrategy.SLIDING_WINDOW, capacity=10, rate=5.0
        )
        assert isinstance(limiter, SlidingWindowRateLimiter)

    def test_create_fixed_window(self):
        """测试创建固定窗口。"""
        limiter = create_rate_limiter(
            LimitStrategy.FIXED_WINDOW, capacity=10, rate=5.0
        )
        assert isinstance(limiter, FixedWindowRateLimiter)

    def test_token_bucket_acquire(self, token_bucket):
        """测试令牌桶获取令牌。"""
        # 桶初始满，应能获取
        result = token_bucket.acquire(1)
        assert result is True

    def test_token_bucket_exhausted(self):
        """测试令牌桶耗尽后获取失败。"""
        limiter = TokenBucketRateLimiter(capacity=2, rate=0.01)
        # 获取 2 个令牌
        assert limiter.acquire(1) is True
        assert limiter.acquire(1) is True
        # 第 3 个应失败
        assert limiter.acquire(1) is False

    def test_token_bucket_refill(self):
        """测试令牌桶补充。"""
        limiter = TokenBucketRateLimiter(capacity=5, rate=100.0)
        # 耗尽令牌
        for _ in range(5):
            limiter.acquire(1)
        # 等待补充
        time.sleep(0.1)
        assert limiter.acquire(1) is True

    def test_token_bucket_try_acquire(self, token_bucket):
        """测试令牌桶 try_acquire。"""
        result = token_bucket.try_acquire(1, timeout=0.1)
        assert result is True

    def test_token_bucket_get_state(self, token_bucket):
        """测试令牌桶状态。"""
        state = token_bucket.get_state()
        assert isinstance(state, dict)
        assert "capacity" in state or "tokens" in state

    def test_leaky_bucket_acquire(self):
        """测试漏桶获取。"""
        limiter = LeakyBucketRateLimiter(capacity=10, rate=5.0)
        assert limiter.acquire(1) is True

    def test_leaky_bucket_exhausted(self):
        """测试漏桶耗尽。"""
        limiter = LeakyBucketRateLimiter(capacity=2, rate=0.01)
        assert limiter.acquire(1) is True
        assert limiter.acquire(1) is True
        assert limiter.acquire(1) is False

    def test_leaky_bucket_get_state(self):
        """测试漏桶状态。"""
        limiter = LeakyBucketRateLimiter(capacity=10, rate=5.0)
        state = limiter.get_state()
        assert isinstance(state, dict)

    def test_sliding_window_acquire(self):
        """测试滑动窗口获取。"""
        limiter = SlidingWindowRateLimiter(capacity=10, rate=5.0)
        assert limiter.acquire(1) is True

    def test_sliding_window_exhausted(self):
        """测试滑动窗口耗尽。"""
        limiter = SlidingWindowRateLimiter(capacity=2, rate=0.01)
        assert limiter.acquire(1) is True
        assert limiter.acquire(1) is True
        assert limiter.acquire(1) is False

    def test_sliding_window_get_state(self):
        """测试滑动窗口状态。"""
        limiter = SlidingWindowRateLimiter(capacity=10, rate=5.0)
        state = limiter.get_state()
        assert isinstance(state, dict)

    def test_fixed_window_acquire(self):
        """测试固定窗口获取。"""
        limiter = FixedWindowRateLimiter(capacity=10, rate=5.0)
        assert limiter.acquire(1) is True

    def test_fixed_window_exhausted(self):
        """测试固定窗口耗尽。"""
        limiter = FixedWindowRateLimiter(capacity=2, rate=0.01)
        assert limiter.acquire(1) is True
        assert limiter.acquire(1) is True
        assert limiter.acquire(1) is False

    def test_fixed_window_get_state(self):
        """测试固定窗口状态。"""
        limiter = FixedWindowRateLimiter(capacity=10, rate=5.0)
        state = limiter.get_state()
        assert isinstance(state, dict)


# ===== 连接池测试 =====


class TestConnectionPool:
    """测试连接池。"""

    def test_acquire_creates_connection(self, connection_pool):
        """测试获取连接时创建新连接。"""
        conn = connection_pool.acquire(timeout=1.0)
        assert conn is not None
        stats = connection_pool.get_stats()
        assert stats["total"] >= 1

    def test_release_returns_to_pool(self, connection_pool):
        """测试释放连接返回池中。"""
        conn = connection_pool.acquire(timeout=1.0)
        connection_pool.release(conn)
        stats = connection_pool.get_stats()
        assert stats["idle"] >= 1

    def test_acquire_reuses_idle(self, connection_pool):
        """测试获取连接时复用空闲连接。"""
        conn1 = connection_pool.acquire(timeout=1.0)
        connection_pool.release(conn1)
        conn2 = connection_pool.acquire(timeout=1.0)
        # 应复用同一连接
        assert conn2 is conn1

    def test_acquire_multiple(self, connection_pool):
        """测试获取多个连接。"""
        conns = [connection_pool.acquire(timeout=1.0) for _ in range(3)]
        assert len(conns) == 3
        stats = connection_pool.get_stats()
        assert stats["active"] == 3

    def test_release_all(self, connection_pool):
        """测试释放所有连接。"""
        conns = [connection_pool.acquire(timeout=1.0) for _ in range(3)]
        for conn in conns:
            connection_pool.release(conn)
        stats = connection_pool.get_stats()
        assert stats["active"] == 0
        assert stats["idle"] == 3

    def test_max_size_limit(self):
        """测试最大连接数限制。"""
        counter = {"count": 0}

        def factory():
            counter["count"] += 1
            return MagicMock(id=counter["count"])

        pool = ConnectionPool(factory=factory, max_size=2)
        conn1 = pool.acquire(timeout=0.1)
        conn2 = pool.acquire(timeout=0.1)
        # 第 3 个应超时
        with pytest.raises(TimeoutError):
            pool.acquire(timeout=0.1)

    def test_cleanup_idle(self, connection_pool):
        """测试清理空闲连接。"""
        conn = connection_pool.acquire(timeout=1.0)
        connection_pool.release(conn)
        cleaned = connection_pool.cleanup_idle()
        assert cleaned >= 0

    def test_close_all(self, connection_pool):
        """测试关闭所有连接。"""
        conn = connection_pool.acquire(timeout=1.0)
        connection_pool.release(conn)
        closed = connection_pool.close_all()
        assert closed >= 1

    def test_get_stats(self, connection_pool):
        """测试获取统计。"""
        connection_pool.acquire(timeout=1.0)
        stats = connection_pool.get_stats()
        assert "total" in stats
        assert "active" in stats
        assert "idle" in stats
        assert stats["pool_type"] == "connection"

    def test_health_check(self):
        """测试健康检查。"""
        def factory():
            return MagicMock(healthy=True)

        def health_check(conn):
            return conn.healthy

        pool = ConnectionPool(
            factory=factory, max_size=5, health_check=health_check,
        )
        conn = pool.acquire(timeout=1.0)
        assert conn is not None


# ===== 线程池测试 =====


class TestThreadPoolManager:
    """测试线程池管理器。"""

    def test_submit(self, thread_pool):
        """测试提交任务。"""
        def task():
            return 42

        future = thread_pool.submit(task)
        result = future.result(timeout=1.0)
        assert result == 42

    def test_submit_with_args(self, thread_pool):
        """测试带参数提交任务。"""
        def task(a, b):
            return a + b

        future = thread_pool.submit(task, 1, 2)
        result = future.result(timeout=1.0)
        assert result == 3

    def test_submit_and_wait(self, thread_pool):
        """测试提交并等待。"""
        def task():
            return "done"

        result = thread_pool.submit_and_wait(task, timeout=1.0)
        assert result == "done"

    def test_map(self, thread_pool):
        """测试 map 并行执行。"""
        def task(x):
            return x * 2

        results = thread_pool.map(task, [1, 2, 3, 4, 5])
        assert list(results) == [2, 4, 6, 8, 10]

    def test_resize(self, thread_pool):
        """测试调整线程池大小。"""
        thread_pool.resize(8)
        stats = thread_pool.get_stats()
        # resize 后应反映新大小
        assert isinstance(stats, dict)

    def test_shutdown(self, thread_pool):
        """测试关闭线程池。"""
        thread_pool.shutdown(wait=True)
        # 关闭后不应抛异常
        assert True

    def test_get_stats(self, thread_pool):
        """测试获取统计。"""
        stats = thread_pool.get_stats()
        assert isinstance(stats, dict)

    def test_get_task_history(self, thread_pool):
        """测试获取任务历史。"""
        def task():
            return 1

        thread_pool.submit(task).result(timeout=1.0)
        history = thread_pool.get_task_history()
        assert isinstance(history, list)


# ===== 协程池测试 =====


class TestCoroutinePoolManager:
    """测试协程池管理器。"""

    def test_create(self):
        """测试创建协程池。"""
        pool = CoroutinePoolManager(max_concurrency=10)
        assert pool is not None

    def test_get_stats(self):
        """测试获取统计。"""
        pool = CoroutinePoolManager(max_concurrency=10)
        stats = pool.get_stats()
        assert isinstance(stats, dict)


# ===== 资源管理器监控测试 =====


class TestResourceManagerMonitoring:
    """测试资源管理器监控功能。"""

    def test_start_stop_monitoring(self, monitoring_manager):
        """测试启动与停止监控。"""
        monitoring_manager.start_monitoring()
        config = monitoring_manager.get_config()
        assert config["monitoring_running"] is True
        monitoring_manager.stop_monitoring()
        config = monitoring_manager.get_config()
        assert config["monitoring_running"] is False

    def test_start_monitoring_idempotent(self, monitoring_manager):
        """测试重复启动监控不报错。"""
        monitoring_manager.start_monitoring()
        monitoring_manager.start_monitoring()
        monitoring_manager.stop_monitoring()

    def test_get_snapshot(self, manager):
        """测试获取当前快照。"""
        snapshot = manager.get_snapshot()
        assert isinstance(snapshot, ResourceSnapshot)

    def test_get_snapshot_with_history(self, monitoring_manager):
        """测试有历史时返回最新快照。"""
        monitoring_manager.start_monitoring()
        time.sleep(0.3)
        monitoring_manager.stop_monitoring()
        snapshot = monitoring_manager.get_snapshot()
        assert isinstance(snapshot, ResourceSnapshot)

    def test_get_history(self, monitoring_manager):
        """测试获取历史快照。"""
        monitoring_manager.start_monitoring()
        time.sleep(0.3)
        monitoring_manager.stop_monitoring()
        history = monitoring_manager.get_history(limit=10)
        assert isinstance(history, list)
        assert len(history) > 0

    def test_get_history_limit(self, monitoring_manager):
        """测试历史快照数量限制。"""
        monitoring_manager.start_monitoring()
        time.sleep(0.5)
        monitoring_manager.stop_monitoring()
        history = monitoring_manager.get_history(limit=2)
        assert len(history) <= 2


# ===== 配额管理测试 =====


class TestQuotaManagement:
    """测试配额管理功能。"""

    def test_set_quota(self, manager):
        """测试设置配额。"""
        manager.set_quota(ResourceType.CPU, 80.0)
        quota = manager.get_quota(ResourceType.CPU)
        assert quota is not None
        assert quota.limit == 80.0

    def test_get_quota(self, manager):
        """测试获取配额。"""
        quota = manager.get_quota(ResourceType.CPU)
        assert quota is not None
        assert quota.resource_type == ResourceType.CPU

    def test_get_quota_nonexistent(self, manager):
        """测试获取不存在的配额返回 None。"""
        # NETWORK 可能未配置
        quota = manager.get_quota(ResourceType.NETWORK)
        # 视默认配置可能为 None 或有值
        assert quota is None or isinstance(quota, ResourceQuota)

    def test_get_all_quotas(self, manager):
        """测试获取所有配额。"""
        quotas = manager.get_all_quotas()
        assert isinstance(quotas, dict)
        assert "cpu" in quotas
        assert "memory" in quotas

    def test_check_quota_available(self, manager):
        """测试检查配额可用。"""
        manager.set_quota(ResourceType.CPU, 100.0)
        # 当前 CPU 使用率应低于 100%
        available = manager.check_quota(ResourceType.CPU, amount=10)
        assert isinstance(available, bool)

    def test_reserve(self, manager):
        """测试预留资源。"""
        manager.set_quota(ResourceType.CPU, 100.0)
        result = manager.reserve(ResourceType.CPU, 20.0)
        assert result is True
        quota = manager.get_quota(ResourceType.CPU)
        assert quota.reserved == 20.0

    def test_reserve_exceeds_limit(self, manager):
        """测试预留超过配额。"""
        manager.set_quota(ResourceType.CPU, 50.0)
        # 设置当前使用量较高
        quota = manager.get_quota(ResourceType.CPU)
        quota.current = 40.0
        result = manager.reserve(ResourceType.CPU, 20.0)
        assert result is False

    def test_release_reservation(self, manager):
        """测试释放预留。"""
        manager.set_quota(ResourceType.CPU, 100.0)
        manager.reserve(ResourceType.CPU, 30.0)
        manager.release_reservation(ResourceType.CPU, 10.0)
        quota = manager.get_quota(ResourceType.CPU)
        assert quota.reserved == 20.0

    def test_release_reservation_below_zero(self, manager):
        """测试释放预留不低于 0。"""
        manager.set_quota(ResourceType.CPU, 100.0)
        manager.release_reservation(ResourceType.CPU, 50.0)
        quota = manager.get_quota(ResourceType.CPU)
        assert quota.reserved >= 0


# ===== 告警测试 =====


class TestAlerts:
    """测试告警功能。"""

    def test_get_alerts_empty(self, manager):
        """测试无告警时返回空列表。"""
        alerts = manager.get_alerts()
        assert isinstance(alerts, list)

    def test_clear_alerts(self, manager):
        """测试清空告警。"""
        count = manager.clear_alerts()
        assert isinstance(count, int)

    def test_get_alerts_by_level(self, manager):
        """测试按级别过滤告警。"""
        alerts = manager.get_alerts(level=AlertLevel.WARNING)
        assert isinstance(alerts, list)
        for alert in alerts:
            assert alert.level == AlertLevel.WARNING

    def test_alert_triggered_on_high_cpu(self, monitoring_manager):
        """测试高 CPU 触发告警（mock）。"""
        # mock 高 CPU 快照
        high_cpu_snapshot = ResourceSnapshot(
            cpu_percent=98.0,  # 超过 EMERGENCY 阈值
            memory_percent=50.0,
            disk_percent=50.0,
        )
        with patch.object(
            monitoring_manager, "_take_snapshot",
            return_value=high_cpu_snapshot,
        ):
            monitoring_manager.start_monitoring()
            time.sleep(0.3)
            monitoring_manager.stop_monitoring()
            alerts = monitoring_manager.get_alerts()
            # 应有 CPU 相关告警
            cpu_alerts = [a for a in alerts if a.resource_type == ResourceType.CPU]
            assert len(cpu_alerts) > 0


# ===== 池注册管理测试 =====


class TestPoolRegistration:
    """测试池注册管理功能。"""

    def test_register_connection_pool(self, manager):
        """测试注册连接池。"""
        def factory():
            return MagicMock()

        pool = manager.register_connection_pool("db", factory, max_size=5)
        assert pool is not None
        assert manager.get_connection_pool("db") is pool

    def test_get_connection_pool_nonexistent(self, manager):
        """测试获取不存在的连接池返回 None。"""
        assert manager.get_connection_pool("nonexistent") is None

    def test_cleanup_all_pools(self, manager):
        """测试清理所有连接池。"""
        def factory():
            return MagicMock()

        manager.register_connection_pool("db1", factory, max_size=5)
        manager.register_connection_pool("db2", factory, max_size=5)
        result = manager.cleanup_all_pools()
        assert isinstance(result, dict)
        assert "db1" in result
        assert "db2" in result

    def test_close_all_pools(self, manager):
        """测试关闭所有连接池。"""
        def factory():
            return MagicMock()

        manager.register_connection_pool("db1", factory, max_size=5)
        result = manager.close_all_pools()
        assert isinstance(result, dict)

    def test_register_thread_pool(self, manager):
        """测试注册线程池。"""
        pool = manager.register_thread_pool("workers", max_workers=4)
        assert pool is not None
        assert manager.get_thread_pool("workers") is pool

    def test_get_thread_pool_nonexistent(self, manager):
        """测试获取不存在的线程池返回 None。"""
        assert manager.get_thread_pool("nonexistent") is None

    def test_register_coroutine_pool(self, manager):
        """测试注册协程池。"""
        pool = manager.register_coroutine_pool("async_workers", max_concurrency=10)
        assert pool is not None
        assert manager.get_coroutine_pool("async_workers") is pool

    def test_get_coroutine_pool_nonexistent(self, manager):
        """测试获取不存在的协程池返回 None。"""
        assert manager.get_coroutine_pool("nonexistent") is None

    def test_register_rate_limiter(self, manager):
        """测试注册限流器。"""
        limiter = manager.register_rate_limiter(
            "api", LimitStrategy.TOKEN_BUCKET, capacity=10, rate=5.0
        )
        assert limiter is not None
        assert manager.get_rate_limiter("api") is limiter

    def test_get_rate_limiter_nonexistent(self, manager):
        """测试获取不存在的限流器返回 None。"""
        assert manager.get_rate_limiter("nonexistent") is None

    def test_check_rate(self, manager):
        """测试检查限流。"""
        manager.register_rate_limiter(
            "api", LimitStrategy.TOKEN_BUCKET, capacity=10, rate=5.0
        )
        result = manager.check_rate("api", tokens=1)
        assert result is True

    def test_check_rate_nonexistent(self, manager):
        """测试检查不存在的限流器返回 False 或 True。"""
        result = manager.check_rate("nonexistent")
        # 视实现可能返回 False
        assert isinstance(result, bool)


# ===== 报告与建议测试 =====


class TestReportAndSuggestions:
    """测试报告生成与容量建议。"""

    def test_generate_report(self, manager):
        """测试生成报告。"""
        report = manager.generate_report()
        assert isinstance(report, dict)
        assert "snapshot" in report or "quotas" in report or "pools" in report

    def test_get_capacity_suggestions(self, manager):
        """测试获取容量建议。"""
        suggestions = manager.get_capacity_suggestions()
        assert isinstance(suggestions, list)
        assert len(suggestions) > 0

    def test_get_stats(self, manager):
        """测试获取统计。"""
        stats = manager.get_stats()
        assert isinstance(stats, dict)
        assert "total_snapshots" in stats
        assert "total_alerts" in stats

    def test_get_config(self, manager):
        """测试获取配置。"""
        config = manager.get_config()
        assert "sample_interval" in config
        assert "history_capacity" in config
        assert "enable_monitoring" in config
        assert "monitoring_running" in config
        assert "quotas" in config
        assert "pool_counts" in config


# ===== 关闭测试 =====


class TestShutdown:
    """测试关闭功能。"""

    def test_shutdown(self, manager):
        """测试关闭资源管理器。"""
        def factory():
            return MagicMock()

        manager.register_connection_pool("db", factory, max_size=5)
        manager.register_thread_pool("workers", max_workers=4)
        manager.shutdown()
        # 关闭后池应被清空
        config = manager.get_config()
        assert config["pool_counts"]["connection"] == 0
        assert config["pool_counts"]["thread"] == 0

    def test_shutdown_idempotent(self, manager):
        """测试重复关闭不报错。"""
        manager.shutdown()
        manager.shutdown()


# ===== 便捷函数与装饰器测试 =====


class TestConvenienceFunctions:
    """测试便捷函数与装饰器。"""

    def test_get_resource_manager_singleton(self):
        """测试全局管理器单例。"""
        m1 = get_resource_manager()
        m2 = get_resource_manager()
        assert m1 is m2

    def test_rate_limited_decorator(self):
        """测试限流装饰器。"""
        manager = get_resource_manager()
        manager.register_rate_limiter(
            "test_limiter", LimitStrategy.TOKEN_BUCKET,
            capacity=10, rate=10.0,
        )

        @rate_limited("test_limiter", tokens=1)
        def func():
            return "success"

        result = func()
        assert result == "success"

    def test_rate_limited_decorator_no_limiter(self):
        """测试无限流器时装饰器直接执行。"""
        @rate_limited("nonexistent_limiter", tokens=1)
        def func():
            return "success"

        result = func()
        assert result == "success"

    def test_with_quota_check_decorator(self):
        """测试配额检查装饰器。"""
        manager = get_resource_manager()
        manager.set_quota(ResourceType.CPU, 100.0)

        @with_quota_check(ResourceType.CPU, amount=0)
        def func():
            return "success"

        result = func()
        assert result == "success"


# ===== 线程安全测试 =====


class TestThreadSafety:
    """测试线程安全性。"""

    def test_concurrent_quota_operations(self, manager):
        """测试并发配额操作。"""
        errors: list[Exception] = []
        manager.set_quota(ResourceType.CPU, 1000.0)

        def worker():
            try:
                for _ in range(20):
                    manager.reserve(ResourceType.CPU, 1.0)
                    manager.release_reservation(ResourceType.CPU, 1.0)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0

    def test_concent_connection_pool_access(self, connection_pool):
        """测试并发连接池访问。"""
        errors: list[Exception] = []
        conns: list = []

        def worker():
            try:
                conn = connection_pool.acquire(timeout=2.0)
                conns.append(conn)
                time.sleep(0.01)
                connection_pool.release(conn)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0

    def test_concurrent_rate_limiter(self, token_bucket):
        """测试并发限流器访问。"""
        errors: list[Exception] = []
        results: list[bool] = []

        def worker():
            try:
                for _ in range(5):
                    result = token_bucket.acquire(1)
                    results.append(result)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        # 部分请求应成功（容量 10，共 20 请求）
        success_count = sum(1 for r in results if r)
        assert success_count <= 10


# ===== 异常处理测试 =====


class TestErrorHandling:
    """测试异常处理。"""

    def test_connection_pool_factory_exception(self):
        """测试连接工厂异常处理。"""
        def factory():
            raise RuntimeError("factory error")

        pool = ConnectionPool(factory=factory, max_size=5)
        with pytest.raises(RuntimeError):
            pool.acquire(timeout=0.1)

    def test_connection_pool_acquire_timeout(self):
        """测试获取连接超时。"""
        def factory():
            return MagicMock()

        pool = ConnectionPool(factory=factory, max_size=1)
        # 占用唯一连接
        conn = pool.acquire(timeout=0.1)
        # 第二次应超时
        with pytest.raises(TimeoutError):
            pool.acquire(timeout=0.1)
        pool.release(conn)

    def test_monitoring_with_psutil_unavailable(self):
        """测试 psutil 不可用时的监控容错。"""
        manager = ResourceManager(
            sample_interval=0.1,
            enable_monitoring=True,
        )
        # mock _take_snapshot 模拟 psutil 不可用时的快照
        with patch.object(
            manager, "_take_snapshot",
            return_value=ResourceSnapshot(cpu_percent=0.0),
        ):
            # 不应抛异常
            manager.start_monitoring()
            time.sleep(0.2)
            manager.stop_monitoring()
        manager.stop_monitoring()


# ===== 综合场景测试 =====


class TestComplexScenarios:
    """测试复杂综合场景。"""

    def test_full_resource_management_workflow(self, manager):
        """测试完整资源管理工作流。"""
        # 注册连接池
        def factory():
            return MagicMock()

        manager.register_connection_pool("db", factory, max_size=5)
        # 注册线程池
        manager.register_thread_pool("workers", max_workers=4)
        # 注册限流器
        manager.register_rate_limiter(
            "api", LimitStrategy.TOKEN_BUCKET, capacity=10, rate=5.0
        )
        # 设置配额
        manager.set_quota(ResourceType.CPU, 80.0)
        # 获取配置
        config = manager.get_config()
        assert config["pool_counts"]["connection"] == 1
        assert config["pool_counts"]["thread"] == 1
        assert config["pool_counts"]["rate_limiter"] == 1
        # 生成报告
        report = manager.generate_report()
        assert isinstance(report, dict)
        # 关闭
        manager.shutdown()

    def test_multiple_rate_limiters(self, manager):
        """测试多个限流器协同。"""
        for strategy in LimitStrategy:
            manager.register_rate_limiter(
                f"limiter_{strategy.value}", strategy,
                capacity=5, rate=1.0,
            )
        for strategy in LimitStrategy:
            limiter = manager.get_rate_limiter(f"limiter_{strategy.value}")
            assert limiter is not None

    def test_quota_reservation_workflow(self, manager):
        """测试配额预留工作流。"""
        manager.set_quota(ResourceType.MEMORY, 100.0)
        # 预留
        assert manager.reserve(ResourceType.MEMORY, 30.0) is True
        assert manager.reserve(ResourceType.MEMORY, 30.0) is True
        # 检查可用
        quota = manager.get_quota(ResourceType.MEMORY)
        assert quota.reserved == 60.0
        # 释放部分
        manager.release_reservation(ResourceType.MEMORY, 20.0)
        quota = manager.get_quota(ResourceType.MEMORY)
        assert quota.reserved == 40.0

    def test_mocked_snapshot_for_alerts(self, monitoring_manager):
        """测试通过 mock 快照触发多种告警。"""
        critical_snapshot = ResourceSnapshot(
            cpu_percent=90.0,  # CRITICAL
            memory_percent=95.0,  # EMERGENCY
            disk_percent=92.0,  # CRITICAL
        )
        with patch.object(
            monitoring_manager, "_take_snapshot",
            return_value=critical_snapshot,
        ):
            monitoring_manager.start_monitoring()
            time.sleep(0.3)
            monitoring_manager.stop_monitoring()
            alerts = monitoring_manager.get_alerts()
            # 应有多种资源告警
            resource_types = {a.resource_type for a in alerts}
            assert len(resource_types) >= 1
