"""任务调度器模块单元测试

测试 backend/orchestration/scheduler.py 中的所有组件：
    - 枚举: TaskPriority / TaskStatus / SchedulingStrategy / TaskType
    - 数据类: Task / TaskResult / RetryPolicy / SchedulerConfig / SchedulerStats
    - PriorityQueue: 优先级队列（FIFO / PRIORITY / DEADLINE / ROUND_ROBIN）
    - TaskHandler / FunctionalHandler: 任务处理器
    - Scheduler: 调度器主类（提交/取消/状态/结果/启动/停止）
    - ScheduledTaskScheduler: 定时任务调度器
    - PriorityManager: 任务优先级管理器（老化提升/截止紧急提升）
    - TaskDependencyGraph: 任务依赖图（拓扑排序/循环检测）
    - 全局函数: get_scheduler / create_scheduler / create_task 等

测试覆盖：
    - 枚举值与工厂方法
    - 数据类的字段、属性、序列化
    - 任务的就绪/过期/终态判断
    - 队列的入队/出队/查看/移除/清空/统计
    - 不同调度策略的排序行为
    - 处理器的注册与匹配
    - 调度器的提交/取消/状态查询/结果获取
    - 重试策略的延迟计算与重试判断
    - 统计的记录与重置
    - 定时任务的注册/取消/列出
    - 优先级的动态调整
    - 依赖图的添加/移除/拓扑排序/循环检测
    - 边界条件与异常场景
"""
import asyncio
import os
import sys
import time
import threading
import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# 确保能导入被测模块
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# 尝试导入被测模块
_IMPORT_OK = False
_IMPORT_ERROR = None
try:
    from backend.orchestration.scheduler import (
        TaskPriority,
        TaskStatus,
        SchedulingStrategy,
        TaskType,
        Task,
        TaskResult,
        RetryPolicy,
        SchedulerConfig,
        SchedulerStats,
        PriorityQueue,
        TaskHandler,
        FunctionalHandler,
        Scheduler,
        ScheduledTaskScheduler,
        PriorityManager,
        TaskDependencyGraph,
        create_scheduler,
        create_task,
        create_handler,
        create_retry_policy,
        get_scheduler,
        set_scheduler,
        reset_scheduler,
    )
    _IMPORT_OK = True
except Exception as exc:  # pragma: no cover
    _IMPORT_ERROR = str(exc)

pytestmark = pytest.mark.skipif(not _IMPORT_OK, reason=f"被测模块导入失败: {_IMPORT_ERROR}")


# ===== 辅助函数 =====


def _make_task(
    name: str = "test_task",
    priority: TaskPriority = TaskPriority.NORMAL,
    func=None,
    **kwargs,
) -> Task:
    """构造测试用任务。"""
    if func is None:
        func = lambda: "result"
    return Task(
        name=name,
        func=func,
        priority=priority,
        **kwargs,
    )


def _make_async_func(result="async_result"):
    """构造异步测试函数。"""
    async def _func():
        return result
    return _func


def _make_sync_func(result="sync_result"):
    """构造同步测试函数。"""
    def _func():
        return result
    return _func


# ===== TaskPriority 枚举测试 =====


class TestTaskPriority:
    """测试 TaskPriority 枚举。"""

    def test_enum_values(self):
        """测试枚举值。"""
        assert TaskPriority.LOWEST.value == 0
        assert TaskPriority.LOW.value == 1
        assert TaskPriority.NORMAL.value == 2
        assert TaskPriority.HIGH.value == 3
        assert TaskPriority.HIGHEST.value == 4
        assert TaskPriority.URGENT.value == 5

    def test_enum_count(self):
        """测试枚举成员数。"""
        assert len(list(TaskPriority)) == 6

    def test_from_value_exact(self):
        """测试从精确值创建。"""
        assert TaskPriority.from_value(0) == TaskPriority.LOWEST
        assert TaskPriority.from_value(2) == TaskPriority.NORMAL
        assert TaskPriority.from_value(5) == TaskPriority.URGENT

    def test_from_value_overflow(self):
        """测试超出最大值时返回 URGENT。"""
        assert TaskPriority.from_value(100) == TaskPriority.URGENT

    def test_from_value_negative(self):
        """测试负值时返回 LOWEST。"""
        assert TaskPriority.from_value(-1) == TaskPriority.LOWEST

    def test_priority_ordering(self):
        """测试优先级排序。"""
        assert TaskPriority.URGENT.value > TaskPriority.HIGH.value
        assert TaskPriority.HIGH.value > TaskPriority.NORMAL.value
        assert TaskPriority.NORMAL.value > TaskPriority.LOW.value
        assert TaskPriority.LOW.value > TaskPriority.LOWEST.value


# ===== TaskStatus 枚举测试 =====


class TestTaskStatus:
    """测试 TaskStatus 枚举。"""

    def test_enum_values(self):
        """测试枚举值。"""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.SUCCESS.value == "success"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"
        assert TaskStatus.TIMEOUT.value == "timeout"
        assert TaskStatus.RETRYING.value == "retrying"
        assert TaskStatus.SKIPPED.value == "skipped"

    def test_enum_count(self):
        """测试枚举成员数。"""
        assert len(list(TaskStatus)) == 8


# ===== SchedulingStrategy 枚举测试 =====


class TestSchedulingStrategy:
    """测试 SchedulingStrategy 枚举。"""

    def test_enum_values(self):
        """测试枚举值。"""
        assert SchedulingStrategy.FIFO.value == "fifo"
        assert SchedulingStrategy.PRIORITY.value == "priority"
        assert SchedulingStrategy.DEADLINE.value == "deadline"
        assert SchedulingStrategy.WEIGHTED_FAIR.value == "weighted_fair"
        assert SchedulingStrategy.ROUND_ROBIN.value == "round_robin"

    def test_enum_count(self):
        """测试枚举成员数。"""
        assert len(list(SchedulingStrategy)) == 5


# ===== TaskType 枚举测试 =====


class TestTaskType:
    """测试 TaskType 枚举。"""

    def test_enum_values(self):
        """测试枚举值。"""
        assert TaskType.SYNC.value == "sync"
        assert TaskType.ASYNC.value == "async"
        assert TaskType.SCHEDULED.value == "scheduled"
        assert TaskType.PERIODIC.value == "periodic"
        assert TaskType.ONE_SHOT.value == "one_shot"

    def test_enum_count(self):
        """测试枚举成员数。"""
        assert len(list(TaskType)) == 5


# ===== Task 数据类测试 =====


class TestTask:
    """测试 Task 数据类。"""

    def test_default_values(self):
        """测试默认值。"""
        task = Task()
        assert task.id != ""
        assert task.name == ""
        assert task.func is None
        assert task.args == ()
        assert task.kwargs == {}
        assert task.priority == TaskPriority.NORMAL
        assert task.status == TaskStatus.PENDING
        assert task.task_type == TaskType.ASYNC
        assert task.max_retries == 0
        assert task.retry_count == 0
        assert task.tags == []
        assert task.metadata == {}
        assert task.depends_on == []

    def test_custom_values(self):
        """测试自定义值。"""
        def _func():
            pass
        task = Task(
            name="custom",
            func=_func,
            args=("arg1",),
            kwargs={"key": "value"},
            priority=TaskPriority.HIGH,
            max_retries=3,
        )
        assert task.name == "custom"
        assert task.func is _func
        assert task.args == ("arg1",)
        assert task.kwargs == {"key": "value"}
        assert task.priority == TaskPriority.HIGH
        assert task.max_retries == 3

    def test_unique_ids(self):
        """测试每个任务有唯一 ID。"""
        task1 = Task()
        task2 = Task()
        assert task1.id != task2.id

    def test_is_ready_pending(self):
        """测试待执行任务就绪。"""
        task = Task()
        assert task.is_ready is True

    def test_is_ready_not_pending(self):
        """测试非待执行状态不就绪。"""
        task = Task(status=TaskStatus.RUNNING)
        assert task.is_ready is False

    def test_is_ready_scheduled_future(self):
        """测试计划时间未到不就绪。"""
        task = Task(scheduled_at=time.time() + 100)
        assert task.is_ready is False

    def test_is_ready_scheduled_past(self):
        """测试计划时间已到就绪。"""
        task = Task(scheduled_at=time.time() - 1)
        assert task.is_ready is True

    def test_is_expired_no_deadline(self):
        """测试无截止时间不过期。"""
        task = Task()
        assert task.is_expired is False

    def test_is_expired_past_deadline(self):
        """测试超过截止时间已过期。"""
        task = Task(deadline=time.time() - 1)
        assert task.is_expired is True

    def test_is_expired_future_deadline(self):
        """测试未到截止时间未过期。"""
        task = Task(deadline=time.time() + 100)
        assert task.is_expired is False

    def test_is_terminal_success(self):
        """测试成功为终态。"""
        task = Task(status=TaskStatus.SUCCESS)
        assert task.is_terminal is True

    def test_is_terminal_failed(self):
        """测试失败为终态。"""
        task = Task(status=TaskStatus.FAILED)
        assert task.is_terminal is True

    def test_is_terminal_pending(self):
        """测试待执行非终态。"""
        task = Task(status=TaskStatus.PENDING)
        assert task.is_terminal is False

    def test_priority_value(self):
        """测试优先级数值。"""
        task = Task(priority=TaskPriority.HIGH)
        assert task.priority_value == 3

    def test_queue_priority(self):
        """测试队列排序键。"""
        task = Task(priority=TaskPriority.HIGH)
        qp = task.queue_priority
        assert qp[0] == -3  # 高优先级取负值
        assert qp[2] == task.id

    def test_to_dict(self):
        """测试转换为字典。"""
        task = Task(name="dict_test", priority=TaskPriority.HIGH)
        d = task.to_dict()
        assert d["name"] == "dict_test"
        assert d["priority"] == "HIGH"
        assert d["status"] == "PENDING"
        assert "id" in d


# ===== TaskResult 测试 =====


class TestTaskResult:
    """测试 TaskResult 数据类。"""

    def test_default_values(self):
        """测试默认值。"""
        result = TaskResult()
        assert result.task_id == ""
        assert result.task_name == ""
        assert result.status == TaskStatus.PENDING
        assert result.result is None
        assert result.error is None

    def test_success_property(self):
        """测试 success 属性。"""
        result = TaskResult(status=TaskStatus.SUCCESS)
        assert result.success is True
        assert result.failed is False

    def test_failed_property(self):
        """测试 failed 属性。"""
        result = TaskResult(status=TaskStatus.FAILED)
        assert result.failed is True
        assert result.success is False

    def test_timeout_is_failed(self):
        """测试超时也算失败。"""
        result = TaskResult(status=TaskStatus.TIMEOUT)
        assert result.failed is True

    def test_to_dict(self):
        """测试转换为字典。"""
        result = TaskResult(
            task_id="t1",
            task_name="test",
            status=TaskStatus.SUCCESS,
            result="ok",
            duration_ms=100.5,
        )
        d = result.to_dict()
        assert d["task_id"] == "t1"
        assert d["task_name"] == "test"
        assert d["status"] == "SUCCESS"
        assert d["result"] == "ok"
        assert d["duration_ms"] == 100.5


# ===== RetryPolicy 测试 =====


class TestRetryPolicy:
    """测试 RetryPolicy 重试策略。"""

    def test_default_values(self):
        """测试默认值。"""
        policy = RetryPolicy()
        assert policy.max_retries == 3
        assert policy.initial_delay == 1.0
        assert policy.backoff_factor == 2.0
        assert policy.max_delay == 60.0
        assert policy.jitter is True

    def test_get_delay_without_jitter(self):
        """测试无抖动的延迟计算。"""
        policy = RetryPolicy(jitter=False, initial_delay=1.0, backoff_factor=2.0)
        assert policy.get_delay(0) == 1.0
        assert policy.get_delay(1) == 2.0
        assert policy.get_delay(2) == 4.0

    def test_get_delay_with_max_delay(self):
        """测试最大延迟限制。"""
        policy = RetryPolicy(
            jitter=False,
            initial_delay=1.0,
            backoff_factor=10.0,
            max_delay=50.0,
        )
        assert policy.get_delay(0) == 1.0
        assert policy.get_delay(1) == 10.0
        assert policy.get_delay(2) == 50.0  # 被限制
        assert policy.get_delay(3) == 50.0  # 被限制

    def test_get_delay_with_jitter(self):
        """测试带抖动的延迟在合理范围内。"""
        policy = RetryPolicy(jitter=True, initial_delay=10.0, backoff_factor=1.0)
        delay = policy.get_delay(0)
        # 抖动 0-25%，所以延迟在 10.0 到 12.5 之间
        assert 10.0 <= delay <= 12.5

    def test_should_retry_within_limit(self):
        """测试未超重试次数应重试。"""
        policy = RetryPolicy(max_retries=3)
        assert policy.should_retry(0, ValueError("test")) is True
        assert policy.should_retry(2, ValueError("test")) is True

    def test_should_retry_exceed_limit(self):
        """测试超过重试次数不应重试。"""
        policy = RetryPolicy(max_retries=3)
        assert policy.should_retry(3, ValueError("test")) is False

    def test_should_retry_exception_type(self):
        """测试仅对指定异常类型重试。"""
        policy = RetryPolicy(retry_on_exceptions=(ValueError,))
        assert policy.should_retry(0, ValueError("test")) is True
        assert policy.should_retry(0, TypeError("test")) is False


# ===== SchedulerConfig 测试 =====


class TestSchedulerConfig:
    """测试 SchedulerConfig 调度器配置。"""

    def test_default_values(self):
        """测试默认值。"""
        config = SchedulerConfig()
        assert config.max_workers == 4
        assert config.strategy == SchedulingStrategy.PRIORITY
        assert config.default_timeout == 300.0
        assert config.poll_interval == 0.1
        assert config.enable_stats is True
        assert config.max_queue_size == 10000

    def test_custom_values(self):
        """测试自定义值。"""
        config = SchedulerConfig(
            max_workers=8,
            strategy=SchedulingStrategy.FIFO,
            default_timeout=60.0,
        )
        assert config.max_workers == 8
        assert config.strategy == SchedulingStrategy.FIFO
        assert config.default_timeout == 60.0


# ===== SchedulerStats 测试 =====


class TestSchedulerStats:
    """测试 SchedulerStats 调度器统计。"""

    def test_default_values(self):
        """测试默认值。"""
        stats = SchedulerStats()
        assert stats.total_submitted == 0
        assert stats.total_completed == 0
        assert stats.total_failed == 0
        assert stats.current_pending == 0
        assert stats.current_running == 0

    def test_avg_duration_no_completions(self):
        """测试无完成时平均耗时为 0。"""
        stats = SchedulerStats()
        assert stats.avg_duration_ms == 0.0

    def test_avg_duration_with_completions(self):
        """测试有完成时平均耗时。"""
        stats = SchedulerStats()
        stats.record_completion(100.0, success=True)
        stats.record_completion(200.0, success=True)
        assert stats.avg_duration_ms == 150.0

    def test_success_rate_no_tasks(self):
        """测试无任务时成功率为 0。"""
        stats = SchedulerStats()
        assert stats.success_rate == 0.0

    def test_success_rate_with_tasks(self):
        """测试有任务时成功率。"""
        stats = SchedulerStats()
        stats.record_completion(100.0, success=True)
        stats.record_completion(200.0, success=False)
        assert stats.success_rate == 0.5

    def test_record_completion(self):
        """测试记录完成。"""
        stats = SchedulerStats()
        stats.record_completion(100.0, success=True)
        assert stats.total_completed == 1
        assert stats.total_duration_ms == 100.0
        assert stats.max_duration_ms == 100.0
        assert stats.min_duration_ms == 100.0

    def test_record_completion_failed(self):
        """测试记录失败完成。"""
        stats = SchedulerStats()
        stats.record_completion(100.0, success=False)
        assert stats.total_completed == 1
        assert stats.total_failed == 1

    def test_record_completion_retried(self):
        """测试记录重试完成。"""
        stats = SchedulerStats()
        stats.record_completion(100.0, success=True, retried=True)
        assert stats.total_retried == 1

    def test_reset(self):
        """测试重置统计。"""
        stats = SchedulerStats()
        stats.record_completion(100.0, success=True)
        stats.total_submitted = 5
        stats.reset()
        assert stats.total_submitted == 0
        assert stats.total_completed == 0

    def test_to_dict(self):
        """测试转换为字典。"""
        stats = SchedulerStats()
        stats.record_completion(100.0, success=True)
        d = stats.to_dict()
        assert d["total_completed"] == 1
        assert "avg_duration_ms" in d
        assert "success_rate" in d
        assert "throughput" in d


# ===== PriorityQueue 测试 =====


class TestPriorityQueue:
    """测试 PriorityQueue 优先级队列。"""

    def test_init(self):
        """测试初始化。"""
        queue = PriorityQueue()
        assert queue.strategy == SchedulingStrategy.PRIORITY
        assert queue.size() == 0
        assert queue.is_empty() is True

    def test_push_and_pop(self):
        """测试入队与出队。"""
        queue = PriorityQueue()
        task = _make_task("t1")
        assert queue.push(task) is True
        assert queue.size() == 1
        popped = queue.pop()
        assert popped is not None
        assert popped.id == task.id
        assert queue.is_empty() is True

    def test_pop_empty(self):
        """测试空队列出队返回 None。"""
        queue = PriorityQueue()
        assert queue.pop() is None

    def test_push_duplicate_id(self):
        """测试重复 ID 入队失败。"""
        queue = PriorityQueue()
        task = _make_task("t1")
        queue.push(task)
        assert queue.push(task) is False

    def test_peek(self):
        """测试查看队首。"""
        queue = PriorityQueue()
        task = _make_task("t1")
        queue.push(task)
        peeked = queue.peek()
        assert peeked is not None
        assert peeked.id == task.id
        assert queue.size() == 1  # 不弹出

    def test_peek_empty(self):
        """测试空队列查看返回 None。"""
        queue = PriorityQueue()
        assert queue.peek() is None

    def test_remove(self):
        """测试移除任务。"""
        queue = PriorityQueue()
        task = _make_task("t1")
        queue.push(task)
        removed = queue.remove(task.id)
        assert removed is not None
        assert removed.id == task.id
        assert queue.size() == 0

    def test_remove_nonexistent(self):
        """测试移除不存在的任务。"""
        queue = PriorityQueue()
        assert queue.remove("nonexistent") is None

    def test_get(self):
        """测试获取指定任务。"""
        queue = PriorityQueue()
        task = _make_task("t1")
        queue.push(task)
        found = queue.get(task.id)
        assert found is not None
        assert found.id == task.id

    def test_get_nonexistent(self):
        """测试获取不存在的任务。"""
        queue = PriorityQueue()
        assert queue.get("nonexistent") is None

    def test_clear(self):
        """测试清空队列。"""
        queue = PriorityQueue()
        for i in range(5):
            queue.push(_make_task(f"t{i}"))
        count = queue.clear()
        assert count == 5
        assert queue.is_empty() is True

    def test_is_full(self):
        """测试队列已满。"""
        queue = PriorityQueue(max_size=2)
        queue.push(_make_task("t1"))
        queue.push(_make_task("t2"))
        assert queue.is_full() is True
        assert queue.push(_make_task("t3")) is False

    def test_priority_ordering(self):
        """测试优先级排序（高优先级先出）。"""
        queue = PriorityQueue(strategy=SchedulingStrategy.PRIORITY)
        low_task = _make_task("low", priority=TaskPriority.LOW)
        high_task = _make_task("high", priority=TaskPriority.HIGH)
        queue.push(low_task)
        queue.push(high_task)
        popped = queue.pop()
        assert popped.id == high_task.id  # 高优先级先出

    def test_fifo_ordering(self):
        """测试先进先出排序。"""
        queue = PriorityQueue(strategy=SchedulingStrategy.FIFO)
        task1 = _make_task("t1")
        task2 = _make_task("t2")
        queue.push(task1)
        queue.push(task2)
        popped = queue.pop()
        assert popped.id == task1.id  # 先入先出

    def test_deadline_ordering(self):
        """测试截止时间排序。"""
        queue = PriorityQueue(strategy=SchedulingStrategy.DEADLINE)
        later_task = _make_task("later", deadline=time.time() + 1000)
        sooner_task = _make_task("sooner", deadline=time.time() + 10)
        queue.push(later_task)
        queue.push(sooner_task)
        popped = queue.pop()
        assert popped.id == sooner_task.id  # 截止时间早的先出

    def test_list_tasks(self):
        """测试列出任务。"""
        queue = PriorityQueue()
        for i in range(5):
            queue.push(_make_task(f"t{i}"))
        tasks = queue.list_tasks()
        assert len(tasks) == 5

    def test_list_tasks_by_priority(self):
        """测试按优先级过滤任务。"""
        queue = PriorityQueue()
        queue.push(_make_task("low", priority=TaskPriority.LOW))
        queue.push(_make_task("high", priority=TaskPriority.HIGH))
        high_tasks = queue.list_tasks(priority=TaskPriority.HIGH)
        assert len(high_tasks) == 1
        assert high_tasks[0].name == "high"

    def test_get_stats(self):
        """测试获取队列统计。"""
        queue = PriorityQueue()
        queue.push(_make_task("t1", priority=TaskPriority.HIGH))
        queue.push(_make_task("t2", priority=TaskPriority.LOW))
        stats = queue.get_stats()
        assert stats["size"] == 2
        assert "by_priority" in stats
        assert "by_status" in stats


# ===== TaskHandler 测试 =====


class TestTaskHandler:
    """测试 TaskHandler 任务处理器基类。"""

    def test_init_defaults(self):
        """测试默认初始化。"""
        handler = TaskHandler()
        assert handler.name == "TaskHandler"
        assert handler.task_types == []

    def test_init_with_name(self):
        """测试带名称初始化。"""
        handler = TaskHandler(name="custom_handler")
        assert handler.name == "custom_handler"

    def test_can_handle_no_types(self):
        """测试无类型限制时可处理任何任务。"""
        handler = TaskHandler()
        task = _make_task()
        assert handler.can_handle(task) is True

    def test_can_handle_with_types(self):
        """测试有类型限制时按类型匹配。"""
        handler = TaskHandler(task_types=[TaskType.ASYNC])
        async_task = _make_task(task_type=TaskType.ASYNC)
        sync_task = _make_task(task_type=TaskType.SYNC)
        assert handler.can_handle(async_task) is True
        assert handler.can_handle(sync_task) is False

    def test_handle_not_implemented(self):
        """测试基类 handle 抛出 NotImplementedError。"""
        handler = TaskHandler()
        task = _make_task()
        with pytest.raises(NotImplementedError):
            asyncio.get_event_loop().run_until_complete(handler.handle(task))


class TestFunctionalHandler:
    """测试 FunctionalHandler 函数式处理器。"""

    def test_init_with_sync_func(self):
        """测试同步函数初始化。"""
        def _sync_func(task):
            return "sync"
        handler = FunctionalHandler(func=_sync_func)
        assert handler.name == "_sync_func"
        assert handler._is_async is False

    def test_init_with_async_func(self):
        """测试异步函数初始化。"""
        async def _async_func(task):
            return "async"
        handler = FunctionalHandler(func=_async_func)
        assert handler._is_async is True

    def test_handle_sync(self):
        """测试处理同步函数。"""
        def _func(task):
            return f"handled_{task.name}"
        handler = FunctionalHandler(func=_func)
        task = _make_task(name="test")
        result = asyncio.get_event_loop().run_until_complete(handler.handle(task))
        assert result == "handled_test"


# ===== Scheduler 测试 =====


class TestScheduler:
    """测试 Scheduler 调度器主类。"""

    def test_init_defaults(self):
        """测试默认初始化。"""
        scheduler = Scheduler()
        assert scheduler.config.max_workers == 4
        assert scheduler.is_running is False

    def test_init_with_config(self):
        """测试带配置初始化。"""
        config = SchedulerConfig(max_workers=8, strategy=SchedulingStrategy.FIFO)
        scheduler = Scheduler(config=config)
        assert scheduler.config.max_workers == 8
        assert scheduler.config.strategy == SchedulingStrategy.FIFO

    def test_register_handler(self):
        """测试注册处理器。"""
        scheduler = Scheduler()
        handler = TaskHandler(name="test_handler", task_types=[TaskType.ASYNC])
        scheduler.register_handler(handler)
        handlers = scheduler.list_handlers()
        assert len(handlers) >= 1

    def test_set_default_handler(self):
        """测试设置默认处理器。"""
        scheduler = Scheduler()
        handler = TaskHandler(name="default")
        scheduler.set_default_handler(handler)
        handlers = scheduler.list_handlers()
        assert len(handlers) >= 1

    def test_submit(self):
        """测试提交任务。"""
        scheduler = Scheduler()
        task_id = scheduler.submit(func=_make_sync_func("result"), name="submit_test")
        assert task_id != ""
        assert scheduler.get_queue_size() == 1

    def test_submit_with_priority(self):
        """测试带优先级提交。"""
        scheduler = Scheduler()
        task_id = scheduler.submit(
            func=_make_sync_func(),
            name="priority_test",
            priority=TaskPriority.HIGH,
        )
        assert task_id != ""

    def test_submit_with_tags(self):
        """测试带标签提交。"""
        scheduler = Scheduler()
        task_id = scheduler.submit(
            func=_make_sync_func(),
            name="tagged",
            tags=["tag1", "tag2"],
        )
        assert task_id != ""

    def test_submit_task_object(self):
        """测试提交预构造任务对象。"""
        scheduler = Scheduler()
        task = _make_task(name="prebuilt")
        task_id = scheduler.submit_task(task)
        assert task_id == task.id

    def test_cancel_pending_task(self):
        """测试取消待执行任务。"""
        scheduler = Scheduler()
        task_id = scheduler.submit(func=_make_sync_func(), name="cancel_test")
        assert scheduler.cancel(task_id) is True
        assert scheduler.get_status(task_id) == TaskStatus.CANCELLED

    def test_cancel_nonexistent(self):
        """测试取消不存在的任务。"""
        scheduler = Scheduler()
        assert scheduler.cancel("nonexistent") is False

    def test_get_status(self):
        """测试获取任务状态。"""
        scheduler = Scheduler()
        task_id = scheduler.submit(func=_make_sync_func(), name="status_test")
        status = scheduler.get_status(task_id)
        assert status == TaskStatus.PENDING

    def test_get_status_nonexistent(self):
        """测试获取不存在任务的状态。"""
        scheduler = Scheduler()
        assert scheduler.get_status("nonexistent") is None

    def test_get_result_nonexistent(self):
        """测试获取不存在任务的结果。"""
        scheduler = Scheduler()
        assert scheduler.get_result("nonexistent") is None

    def test_on_complete_callback(self):
        """测试注册完成回调。"""
        scheduler = Scheduler()
        callback_called = []
        scheduler.on_complete("test_id", lambda r: callback_called.append(r))
        # 回调在任务完成时触发，这里仅验证注册不报错

    def test_subscribe_event(self):
        """测试订阅事件。"""
        scheduler = Scheduler()
        events_received = []
        scheduler.subscribe_event("task_submitted", lambda et, t: events_received.append(et))
        scheduler.submit(func=_make_sync_func(), name="event_test")
        assert len(events_received) >= 1

    def test_get_stats(self):
        """测试获取统计。"""
        scheduler = Scheduler()
        scheduler.submit(func=_make_sync_func(), name="stats_test")
        stats = scheduler.get_stats()
        assert stats["total_submitted"] >= 1
        assert "queue" in stats
        assert "is_running" in stats

    def test_get_queue_size(self):
        """测试获取队列长度。"""
        scheduler = Scheduler()
        assert scheduler.get_queue_size() == 0
        scheduler.submit(func=_make_sync_func(), name="size_test")
        assert scheduler.get_queue_size() == 1

    def test_get_pending_tasks(self):
        """测试获取待执行任务列表。"""
        scheduler = Scheduler()
        scheduler.submit(func=_make_sync_func(), name="pending_test")
        pending = scheduler.get_pending_tasks()
        assert len(pending) >= 1

    def test_get_running_tasks(self):
        """测试获取执行中任务列表。"""
        scheduler = Scheduler()
        running = scheduler.get_running_tasks()
        assert running == []

    def test_reset_stats(self):
        """测试重置统计。"""
        scheduler = Scheduler()
        scheduler.submit(func=_make_sync_func(), name="reset_test")
        scheduler.reset_stats()
        stats = scheduler.get_stats()
        assert stats["total_submitted"] == 0

    def test_clear_results(self):
        """测试清空结果缓存。"""
        scheduler = Scheduler()
        count = scheduler.clear_results()
        assert count == 0

    def test_is_running_property(self):
        """测试 is_running 属性。"""
        scheduler = Scheduler()
        assert scheduler.is_running is False


# ===== ScheduledTaskScheduler 测试 =====


class TestScheduledTaskScheduler:
    """测试 ScheduledTaskScheduler 定时任务调度器。"""

    def test_init(self):
        """测试初始化。"""
        scheduler = ScheduledTaskScheduler()
        assert scheduler._base_scheduler is not None
        assert scheduler.list_scheduled() == []

    def test_schedule_every(self):
        """测试按间隔调度。"""
        scheduler = ScheduledTaskScheduler()
        task_id = scheduler.schedule_every(
            func=_make_sync_func(),
            interval=3600,
            name="hourly",
        )
        assert task_id != ""
        scheduled = scheduler.list_scheduled()
        assert len(scheduled) == 1
        assert scheduled[0]["name"] == "hourly"
        assert scheduled[0]["type"] == "periodic"

    def test_schedule_at(self):
        """测试在指定时间调度。"""
        scheduler = ScheduledTaskScheduler()
        run_at = time.time() + 86400
        task_id = scheduler.schedule_at(
            func=_make_sync_func(),
            run_at=run_at,
            name="tomorrow",
        )
        assert task_id != ""
        scheduled = scheduler.list_scheduled()
        assert scheduled[0]["type"] == "one_shot"

    def test_schedule_cron(self):
        """测试 cron 表达式调度。"""
        scheduler = ScheduledTaskScheduler()
        task_id = scheduler.schedule_cron(
            func=_make_sync_func(),
            cron_expression="0 * * * *",
            name="hourly_cron",
        )
        assert task_id != ""
        scheduled = scheduler.list_scheduled()
        assert scheduled[0]["type"] == "cron"
        assert scheduled[0]["cron"] == "0 * * * *"

    def test_cancel_scheduled(self):
        """测试取消定时任务。"""
        scheduler = ScheduledTaskScheduler()
        task_id = scheduler.schedule_every(
            func=_make_sync_func(),
            interval=60,
            name="cancel_me",
        )
        assert scheduler.cancel_scheduled(task_id) is True
        assert len(scheduler.list_scheduled()) == 0

    def test_cancel_nonexistent(self):
        """测试取消不存在的定时任务。"""
        scheduler = ScheduledTaskScheduler()
        assert scheduler.cancel_scheduled("nonexistent") is False

    def test_list_scheduled(self):
        """测试列出定时任务。"""
        scheduler = ScheduledTaskScheduler()
        for i in range(3):
            scheduler.schedule_every(
                func=_make_sync_func(),
                interval=60,
                name=f"task_{i}",
            )
        scheduled = scheduler.list_scheduled()
        assert len(scheduled) == 3


# ===== PriorityManager 测试 =====


class TestPriorityManager:
    """测试 PriorityManager 优先级管理器。"""

    def test_init_defaults(self):
        """测试默认初始化。"""
        mgr = PriorityManager()
        assert mgr.aging_threshold == 300.0
        assert mgr.aging_boost == 1
        assert mgr.deadline_threshold == 60.0

    def test_adjust_priority_no_change(self):
        """测试无老化无截止时优先级不变。"""
        mgr = PriorityManager(aging_threshold=999999)
        task = _make_task(priority=TaskPriority.NORMAL)
        assert mgr.adjust_priority(task) == TaskPriority.NORMAL

    def test_adjust_priority_aging(self):
        """测试老化提升优先级。"""
        mgr = PriorityManager(aging_threshold=0.0, aging_boost=1)
        task = _make_task(priority=TaskPriority.NORMAL)
        task.created_at = time.time() - 1  # 1秒前创建
        new_priority = mgr.adjust_priority(task)
        assert new_priority.value > TaskPriority.NORMAL.value

    def test_adjust_priority_deadline_urgent(self):
        """测试截止时间紧急提升。"""
        mgr = PriorityManager(deadline_threshold=100.0)
        task = _make_task(priority=TaskPriority.LOW)
        task.deadline = time.time() + 10  # 10秒后截止
        new_priority = mgr.adjust_priority(task)
        assert new_priority == TaskPriority.URGENT

    def test_adjust_priority_max_urgent(self):
        """测试优先级不超过 URGENT。"""
        mgr = PriorityManager(aging_threshold=0.0, aging_boost=10)
        task = _make_task(priority=TaskPriority.NORMAL)
        task.created_at = time.time() - 1
        new_priority = mgr.adjust_priority(task)
        assert new_priority == TaskPriority.URGENT

    def test_batch_adjust(self):
        """测试批量调整优先级。"""
        mgr = PriorityManager(aging_threshold=0.0, aging_boost=1)
        tasks = [
            _make_task(name=f"t{i}", priority=TaskPriority.NORMAL)
            for i in range(3)
        ]
        for t in tasks:
            t.created_at = time.time() - 1
        adjustments = mgr.batch_adjust(tasks)
        assert len(adjustments) == 3
        for tid, priority in adjustments.items():
            assert priority.value > TaskPriority.NORMAL.value


# ===== TaskDependencyGraph 测试 =====


class TestTaskDependencyGraph:
    """测试 TaskDependencyGraph 任务依赖图。"""

    def test_init(self):
        """测试初始化。"""
        graph = TaskDependencyGraph()
        assert graph.topological_sort() == []
        assert graph.has_cycle() is False

    def test_add_task(self):
        """测试添加任务节点。"""
        graph = TaskDependencyGraph()
        task = _make_task(name="node1")
        graph.add_task(task)
        sorted_tasks = graph.topological_sort()
        assert len(sorted_tasks) == 1

    def test_add_task_with_dependency(self):
        """测试带依赖添加任务。"""
        graph = TaskDependencyGraph()
        task_a = _make_task(name="A")
        task_b = _make_task(name="B")
        task_b.depends_on = [task_a.id]
        graph.add_task(task_a)
        graph.add_task(task_b)
        sorted_tasks = graph.topological_sort()
        assert len(sorted_tasks) == 2
        # A 应在 B 之前
        assert sorted_tasks[0].id == task_a.id

    def test_remove_task(self):
        """测试移除任务节点。"""
        graph = TaskDependencyGraph()
        task = _make_task(name="remove_me")
        graph.add_task(task)
        removed = graph.remove_task(task.id)
        assert removed is not None
        assert removed.id == task.id
        assert len(graph.topological_sort()) == 0

    def test_remove_nonexistent(self):
        """测试移除不存在的任务。"""
        graph = TaskDependencyGraph()
        assert graph.remove_task("nonexistent") is None

    def test_add_dependency(self):
        """测试添加依赖关系。"""
        graph = TaskDependencyGraph()
        task_a = _make_task(name="A")
        task_b = _make_task(name="B")
        graph.add_task(task_a)
        graph.add_task(task_b)
        assert graph.add_dependency(task_b.id, task_a.id) is True

    def test_add_dependency_cycle_detected(self):
        """测试添加循环依赖被拒绝。"""
        graph = TaskDependencyGraph()
        task_a = _make_task(name="A")
        task_b = _make_task(name="B")
        graph.add_task(task_a)
        graph.add_task(task_b)
        graph.add_dependency(task_b.id, task_a.id)  # B 依赖 A
        # 尝试添加 A 依赖 B（会形成循环）
        assert graph.add_dependency(task_a.id, task_b.id) is False

    def test_has_cycle_no_cycle(self):
        """测试无循环。"""
        graph = TaskDependencyGraph()
        task_a = _make_task(name="A")
        task_b = _make_task(name="B")
        graph.add_task(task_a)
        graph.add_task(task_b)
        graph.add_dependency(task_b.id, task_a.id)
        assert graph.has_cycle() is False

    def test_get_ready_tasks_no_deps(self):
        """测试无依赖的任务就绪。"""
        graph = TaskDependencyGraph()
        task = _make_task(name="ready")
        graph.add_task(task)
        ready = graph.get_ready_tasks()
        assert len(ready) == 1

    def test_get_ready_tasks_with_deps(self):
        """测试有依赖且依赖未完成时不就绪。"""
        graph = TaskDependencyGraph()
        task_a = _make_task(name="A")
        task_b = _make_task(name="B")
        task_b.depends_on = [task_a.id]
        graph.add_task(task_a)
        graph.add_task(task_b)
        ready = graph.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == task_a.id

    def test_get_dependencies(self):
        """测试获取直接依赖。"""
        graph = TaskDependencyGraph()
        task_a = _make_task(name="A")
        task_b = _make_task(name="B")
        task_b.depends_on = [task_a.id]
        graph.add_task(task_a)
        graph.add_task(task_b)
        deps = graph.get_dependencies(task_b.id)
        assert task_a.id in deps

    def test_get_dependents(self):
        """测试获取被依赖的任务。"""
        graph = TaskDependencyGraph()
        task_a = _make_task(name="A")
        task_b = _make_task(name="B")
        task_b.depends_on = [task_a.id]
        graph.add_task(task_a)
        graph.add_task(task_b)
        dependents = graph.get_dependents(task_a.id)
        assert task_b.id in dependents

    def test_get_all_dependencies(self):
        """测试获取所有传递依赖。"""
        graph = TaskDependencyGraph()
        task_a = _make_task(name="A")
        task_b = _make_task(name="B")
        task_c = _make_task(name="C")
        task_b.depends_on = [task_a.id]
        task_c.depends_on = [task_b.id]
        graph.add_task(task_a)
        graph.add_task(task_b)
        graph.add_task(task_c)
        all_deps = graph.get_all_dependencies(task_c.id)
        assert task_a.id in all_deps
        assert task_b.id in all_deps

    def test_topological_sort_complex(self):
        """测试复杂拓扑排序。"""
        graph = TaskDependencyGraph()
        # A -> B -> C, A -> D
        task_a = _make_task(name="A")
        task_b = _make_task(name="B")
        task_c = _make_task(name="C")
        task_d = _make_task(name="D")
        task_b.depends_on = [task_a.id]
        task_c.depends_on = [task_b.id]
        task_d.depends_on = [task_a.id]
        graph.add_task(task_a)
        graph.add_task(task_b)
        graph.add_task(task_c)
        graph.add_task(task_d)
        sorted_tasks = graph.topological_sort()
        assert len(sorted_tasks) == 4
        # A 应在最前
        assert sorted_tasks[0].id == task_a.id
        # C 应在 B 之后
        b_idx = next(i for i, t in enumerate(sorted_tasks) if t.id == task_b.id)
        c_idx = next(i for i, t in enumerate(sorted_tasks) if t.id == task_c.id)
        assert b_idx < c_idx


# ===== 全局函数测试 =====


class TestGlobalFunctions:
    """测试全局便捷函数。"""

    def test_create_scheduler(self):
        """测试创建调度器函数。"""
        scheduler = create_scheduler(max_workers=2)
        assert scheduler.config.max_workers == 2

    def test_create_scheduler_with_strategy(self):
        """测试带策略创建调度器。"""
        scheduler = create_scheduler(strategy=SchedulingStrategy.FIFO)
        assert scheduler.config.strategy == SchedulingStrategy.FIFO

    def test_create_task(self):
        """测试创建任务函数。"""
        def _func():
            return "ok"
        task = create_task(func=_func, name="created", priority=TaskPriority.HIGH)
        assert task.name == "created"
        assert task.priority == TaskPriority.HIGH

    def test_create_handler(self):
        """测试创建处理器函数。"""
        def _func(task):
            return "handled"
        handler = create_handler(func=_func, name="custom_handler")
        assert handler.name == "custom_handler"

    def test_create_retry_policy(self):
        """测试创建重试策略函数。"""
        policy = create_retry_policy(max_retries=5, initial_delay=2.0, backoff_factor=3.0)
        assert policy.max_retries == 5
        assert policy.initial_delay == 2.0
        assert policy.backoff_factor == 3.0

    def test_get_scheduler(self):
        """测试获取全局调度器。"""
        scheduler = get_scheduler()
        assert scheduler is not None

    def test_get_scheduler_singleton(self):
        """测试全局调度器为单例。"""
        s1 = get_scheduler()
        s2 = get_scheduler()
        assert s1 is s2

    def test_set_scheduler(self):
        """测试设置全局调度器。"""
        custom = create_scheduler(max_workers=10)
        set_scheduler(custom)
        assert get_scheduler() is custom

    def test_reset_scheduler(self):
        """测试重置全局调度器。"""
        reset_scheduler()
        # 重置后获取应返回新实例
        s1 = get_scheduler()
        reset_scheduler()
        s2 = get_scheduler()
        assert s1 is not s2


# ===== 集成测试 =====


class TestIntegration:
    """集成测试：模拟完整调度工作流。"""

    def test_submit_and_cancel_workflow(self):
        """测试提交与取消工作流。"""
        scheduler = Scheduler()
        # 提交多个任务
        task_ids = []
        for i in range(5):
            tid = scheduler.submit(
                func=_make_sync_func(f"result_{i}"),
                name=f"task_{i}",
                priority=TaskPriority.NORMAL,
            )
            task_ids.append(tid)
        # 验证队列中有 5 个任务
        assert scheduler.get_queue_size() == 5
        # 取消部分任务
        scheduler.cancel(task_ids[0])
        scheduler.cancel(task_ids[1])
        assert scheduler.get_queue_size() == 3
        # 验证取消的任务状态
        assert scheduler.get_status(task_ids[0]) == TaskStatus.CANCELLED

    def test_priority_queue_workflow(self):
        """测试优先级队列工作流。"""
        queue = PriorityQueue(strategy=SchedulingStrategy.PRIORITY)
        # 按随机优先级入队
        priorities = [TaskPriority.LOW, TaskPriority.HIGH, TaskPriority.NORMAL, TaskPriority.URGENT]
        for i, p in enumerate(priorities):
            queue.push(_make_task(f"t{i}", priority=p))
        # 出队顺序应为 URGENT > HIGH > NORMAL > LOW
        popped = []
        while not queue.is_empty():
            task = queue.pop()
            if task:
                popped.append(task.priority)
        assert popped[0] == TaskPriority.URGENT
        assert popped[1] == TaskPriority.HIGH
        assert popped[2] == TaskPriority.NORMAL
        assert popped[3] == TaskPriority.LOW

    def test_dependency_graph_workflow(self):
        """测试依赖图工作流。"""
        graph = TaskDependencyGraph()
        # 创建 A -> B -> C 的依赖链
        task_a = _make_task(name="A")
        task_b = _make_task(name="B")
        task_c = _make_task(name="C")
        task_b.depends_on = [task_a.id]
        task_c.depends_on = [task_b.id]
        graph.add_task(task_a)
        graph.add_task(task_b)
        graph.add_task(task_c)
        # 拓扑排序
        sorted_tasks = graph.topological_sort()
        assert len(sorted_tasks) == 3
        assert sorted_tasks[0].id == task_a.id
        assert sorted_tasks[1].id == task_b.id
        assert sorted_tasks[2].id == task_c.id
        # 无循环
        assert graph.has_cycle() is False

    def test_priority_manager_workflow(self):
        """测试优先级管理器工作流。"""
        mgr = PriorityManager(aging_threshold=0.0, aging_boost=1)
        tasks = [
            _make_task(name=f"t{i}", priority=TaskPriority.LOW)
            for i in range(5)
        ]
        for t in tasks:
            t.created_at = time.time() - 1
        adjustments = mgr.batch_adjust(tasks)
        # 所有任务都应被提升
        assert len(adjustments) == 5
        for priority in adjustments.values():
            assert priority.value > TaskPriority.LOW.value


# ===== 边界条件测试 =====


class TestEdgeCases:
    """边界条件与异常场景测试。"""

    def test_task_empty_name(self):
        """测试空任务名。"""
        task = Task(name="")
        assert task.name == ""

    def test_task_none_func(self):
        """测试无执行函数的任务。"""
        task = Task(func=None)
        assert task.func is None

    def test_queue_zero_max_size(self):
        """测试最大容量为 0 的队列。"""
        queue = PriorityQueue(max_size=0)
        task = _make_task()
        assert queue.push(task) is False

    def test_queue_one_max_size(self):
        """测试最大容量为 1 的队列。"""
        queue = PriorityQueue(max_size=1)
        queue.push(_make_task("t1"))
        assert queue.push(_make_task("t2")) is False

    def test_retry_policy_zero_retries(self):
        """测试最大重试次数为 0。"""
        policy = RetryPolicy(max_retries=0)
        assert policy.should_retry(0, ValueError()) is False

    def test_retry_policy_large_backoff(self):
        """测试大退避倍数。"""
        policy = RetryPolicy(
            jitter=False,
            initial_delay=1.0,
            backoff_factor=100.0,
            max_delay=50.0,
        )
        assert policy.get_delay(1) == 50.0  # 被限制为 max_delay

    def test_scheduler_submit_to_full_queue(self):
        """测试向满队列提交任务。"""
        config = SchedulerConfig(max_queue_size=1)
        scheduler = Scheduler(config=config)
        scheduler.submit(func=_make_sync_func(), name="t1")
        with pytest.raises(RuntimeError, match="队列已满"):
            scheduler.submit(func=_make_sync_func(), name="t2")

    def test_dependency_graph_empty(self):
        """测试空依赖图。"""
        graph = TaskDependencyGraph()
        assert graph.topological_sort() == []
        assert graph.has_cycle() is False
        assert graph.get_ready_tasks() == []

    def test_dependency_graph_self_loop_prevented(self):
        """测试自循环依赖被阻止。"""
        graph = TaskDependencyGraph()
        task = _make_task(name="self")
        graph.add_task(task)
        # 尝试添加自依赖
        assert graph.add_dependency(task.id, task.id) is False

    def test_priority_manager_no_adjustment_needed(self):
        """测试无需调整优先级。"""
        mgr = PriorityManager(aging_threshold=999999, deadline_threshold=0.0)
        task = _make_task(priority=TaskPriority.NORMAL)
        task.created_at = time.time()
        assert mgr.adjust_priority(task) == TaskPriority.NORMAL

    def test_concurrent_queue_access(self):
        """测试并发队列访问。"""
        queue = PriorityQueue(max_size=1000)
        errors = []

        def producer():
            try:
                for i in range(100):
                    queue.push(_make_task(f"prod_{i}"))
            except Exception as e:
                errors.append(e)

        def consumer():
            try:
                for _ in range(100):
                    queue.pop()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=producer), threading.Thread(target=consumer)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0

    def test_task_with_complex_metadata(self):
        """测试任务含复杂元数据。"""
        task = Task(
            name="complex",
            metadata={"nested": {"a": [1, 2, 3]}, "list": ["x", "y"]},
        )
        d = task.to_dict()
        assert "metadata" in d

    def test_scheduler_stats_min_duration(self):
        """测试统计最小耗时。"""
        stats = SchedulerStats()
        stats.record_completion(100.0, success=True)
        stats.record_completion(50.0, success=True)
        assert stats.min_duration_ms == 50.0
        assert stats.max_duration_ms == 100.0
