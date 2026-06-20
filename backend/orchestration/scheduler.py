"""任务调度器模块

提供基于优先级队列的任务调度能力，支持并发执行、超时处理、任务取消、
重试策略、定时任务等高级调度特性。

核心组件：
    - Task: 任务数据类（封装任务输入、优先级、状态等）
    - TaskPriority: 任务优先级枚举
    - TaskStatus: 任务状态枚举
    - PriorityQueue: 优先级队列（支持 FIFO / 优先级 / 截止时间策略）
    - Scheduler: 调度器主类（管理任务队列与工作协程）
    - TaskResult: 任务执行结果
    - RetryPolicy: 重试策略
    - SchedulerConfig: 调度器配置
    - SchedulerStats: 调度器统计
    - TaskHandler: 任务处理器基类

设计原则：
    1. 高效调度：基于优先级队列，高优先级任务优先执行
    2. 并发控制：通过信号量限制最大并发数，防止资源耗尽
    3. 容错性：支持重试、超时、降级等错误处理策略
    4. 可观测：内置统计计数器，记录任务吞吐量、成功率、延迟等
    5. 可扩展：通过注册任务处理器扩展调度能力

使用示例：
    # 创建调度器
    scheduler = Scheduler(max_workers=4)

    # 提交任务
    task_id = scheduler.submit(
        func=my_async_function,
        args=("arg1",),
        priority=TaskPriority.HIGH,
    )

    # 获取结果
    result = scheduler.get_result(task_id)

    # 启动调度器
    await scheduler.start()
"""
import asyncio
import heapq
import inspect
import logging
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, Union

logger = logging.getLogger(__name__)


# ===== 枚举定义 =====


class TaskPriority(Enum):
    """任务优先级枚举

    数值越大优先级越高。
    """

    LOWEST = 0  # 最低优先级
    LOW = 1  # 低优先级
    NORMAL = 2  # 普通优先级（默认）
    HIGH = 3  # 高优先级
    HIGHEST = 4  # 最高优先级
    URGENT = 5  # 紧急（插队执行）

    @classmethod
    def from_value(cls, value: int) -> "TaskPriority":
        """从整数值创建优先级。"""
        for member in cls:
            if member.value == value:
                return member
        if value >= cls.URGENT.value:
            return cls.URGENT
        return cls.LOWEST


class TaskStatus(Enum):
    """任务状态枚举"""

    PENDING = "pending"  # 待执行（在队列中等待）
    RUNNING = "running"  # 执行中
    SUCCESS = "success"  # 成功
    FAILED = "failed"  # 失败
    CANCELLED = "cancelled"  # 已取消
    TIMEOUT = "timeout"  # 超时
    RETRYING = "retrying"  # 重试中
    SKIPPED = "skipped"  # 跳过


class SchedulingStrategy(Enum):
    """调度策略枚举"""

    FIFO = "fifo"  # 先进先出
    PRIORITY = "priority"  # 优先级调度
    DEADLINE = "deadline"  # 截止时间调度（最紧急的先执行）
    WEIGHTED_FAIR = "weighted_fair"  # 加权公平调度
    ROUND_ROBIN = "round_robin"  # 轮询调度


class TaskType(Enum):
    """任务类型枚举"""

    SYNC = "sync"  # 同步任务
    ASYNC = "async"  # 异步任务
    SCHEDULED = "scheduled"  # 定时任务
    PERIODIC = "periodic"  # 周期任务
    ONE_SHOT = "one_shot"  # 一次性任务


# ===== 数据类定义 =====


@dataclass
class Task:
    """任务数据类

    封装任务的输入、优先级、状态等所有信息。
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    func: Optional[Callable] = None
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    task_type: TaskType = TaskType.ASYNC
    created_at: float = field(default_factory=time.time)
    scheduled_at: float = 0.0  # 计划执行时间（用于定时任务）
    deadline: float = 0.0  # 截止时间（0 表示无截止）
    timeout: float = 0.0  # 超时时间（秒，0 表示不限制）
    max_retries: int = 0  # 最大重试次数
    retry_count: int = 0  # 当前重试次数
    retry_delay: float = 1.0  # 重试延迟
    retry_backoff: float = 2.0  # 重试退避倍数
    tags: list = field(default_factory=list)  # 任务标签
    metadata: dict = field(default_factory=dict)  # 任务元数据
    depends_on: list = field(default_factory=list)  # 依赖任务 ID 列表
    result: Any = None  # 执行结果
    error: Optional[str] = None  # 错误信息
    error_type: Optional[str] = None  # 错误类型
    start_time: float = 0.0  # 实际开始时间
    end_time: float = 0.0  # 实际结束时间
    duration_ms: float = 0.0  # 执行耗时（毫秒）
    worker_id: str = ""  # 执行该任务的工作线程/协程 ID
    progress: float = 0.0  # 执行进度（0.0 - 1.0）
    cancel_token: Any = None  # 取消令牌

    @property
    def is_ready(self) -> bool:
        """任务是否就绪（可执行）。"""
        if self.status != TaskStatus.PENDING:
            return False
        if self.scheduled_at > 0 and time.time() < self.scheduled_at:
            return False
        return True

    @property
    def is_expired(self) -> bool:
        """任务是否已过期（超过截止时间）。"""
        if self.deadline > 0 and time.time() > self.deadline:
            return True
        return False

    @property
    def is_terminal(self) -> bool:
        """是否为终态（不可再变更）。"""
        return self.status in (
            TaskStatus.SUCCESS,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
            TaskStatus.TIMEOUT,
            TaskStatus.SKIPPED,
        )

    @property
    def priority_value(self) -> int:
        """获取优先级数值（用于队列排序）。"""
        return self.priority.value

    @property
    def queue_priority(self) -> tuple:
        """获取队列排序键（优先级高的先出，同优先级按创建时间先入先出）。"""
        # heapq 是最小堆，所以优先级取负值
        return (-self.priority_value, self.created_at, self.id)

    def to_dict(self) -> dict:
        """转换为字典表示。"""
        return {
            "id": self.id,
            "name": self.name,
            "priority": self.priority.name,
            "status": self.status.name,
            "task_type": self.task_type.name,
            "created_at": self.created_at,
            "scheduled_at": self.scheduled_at,
            "deadline": self.deadline,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "retry_count": self.retry_count,
            "tags": self.tags,
            "depends_on": self.depends_on,
            "error": self.error,
            "error_type": self.error_type,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": round(self.duration_ms, 2),
            "progress": self.progress,
            "metadata": self.metadata,
        }


@dataclass
class TaskResult:
    """任务执行结果"""

    task_id: str = ""
    task_name: str = ""
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: float = 0.0
    retry_count: int = 0
    metadata: dict = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.status == TaskStatus.SUCCESS

    @property
    def failed(self) -> bool:
        return self.status in (TaskStatus.FAILED, TaskStatus.TIMEOUT)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "status": self.status.name,
            "result": self.result,
            "error": self.error,
            "error_type": self.error_type,
            "duration_ms": round(self.duration_ms, 2),
            "retry_count": self.retry_count,
            "metadata": self.metadata,
        }


@dataclass
class RetryPolicy:
    """重试策略

    封装任务失败后的重试配置。
    """

    max_retries: int = 3  # 最大重试次数
    initial_delay: float = 1.0  # 初始延迟（秒）
    backoff_factor: float = 2.0  # 退避倍数
    max_delay: float = 60.0  # 最大延迟（秒）
    retry_on_exceptions: tuple = (Exception,)  # 触发重试的异常类型
    jitter: bool = True  # 是否添加随机抖动（防止重试风暴）

    def get_delay(self, attempt: int) -> float:
        """计算第 attempt 次重试的延迟时间。

        Args:
            attempt: 重试次数（从 0 开始）。

        Returns:
            延迟秒数。
        """
        import random
        delay = self.initial_delay * (self.backoff_factor ** attempt)
        delay = min(delay, self.max_delay)
        if self.jitter:
            # 添加 0-25% 的随机抖动
            delay *= (1 + random.uniform(0, 0.25))
        return delay

    def should_retry(self, attempt: int, exception: Exception) -> bool:
        """判断是否应重试。

        Args:
            attempt: 当前重试次数。
            exception: 触发的异常。

        Returns:
            True 表示应重试。
        """
        if attempt >= self.max_retries:
            return False
        return isinstance(exception, self.retry_on_exceptions)


@dataclass
class SchedulerConfig:
    """调度器配置"""

    max_workers: int = 4  # 最大工作协程数
    strategy: SchedulingStrategy = SchedulingStrategy.PRIORITY  # 调度策略
    default_timeout: float = 300.0  # 默认超时时间（秒）
    default_retry_policy: RetryPolicy = field(default_factory=RetryPolicy)  # 默认重试策略
    poll_interval: float = 0.1  # 队列轮询间隔（秒）
    enable_stats: bool = True  # 是否启用统计
    max_queue_size: int = 10000  # 最大队列长度
    enable_persistence: bool = False  # 是否启用持久化
    persistence_path: str = "data/scheduler"  # 持久化路径
    worker_idle_timeout: float = 60.0  # 工作协程空闲超时
    enable_dead_task_cleanup: bool = True  # 是否启用死亡任务清理
    dead_task_ttl: float = 3600.0  # 死亡任务保留时间（秒）
    priority_preemption: bool = False  # 是否启用优先级抢占


@dataclass
class SchedulerStats:
    """调度器统计"""

    total_submitted: int = 0  # 总提交数
    total_completed: int = 0  # 总完成数
    total_failed: int = 0  # 总失败数
    total_cancelled: int = 0  # 总取消数
    total_timeout: int = 0  # 总超时数
    total_retried: int = 0  # 总重试数
    total_evicted: int = 0  # 总淘汰数（队列满时丢弃）
    current_pending: int = 0  # 当前待执行数
    current_running: int = 0  # 当前执行中数
    total_duration_ms: float = 0.0  # 总执行耗时
    max_duration_ms: float = 0.0  # 最大执行耗时
    min_duration_ms: float = float("inf")  # 最小执行耗时
    start_time: float = field(default_factory=time.time)  # 调度器启动时间

    @property
    def avg_duration_ms(self) -> float:
        """平均执行耗时。"""
        if self.total_completed == 0:
            return 0.0
        return self.total_duration_ms / self.total_completed

    @property
    def success_rate(self) -> float:
        """成功率。"""
        # total_completed 包含成功与失败的完成数，total_failed 是其子集
        total = self.total_completed + self.total_timeout
        if total == 0:
            return 0.0
        successful = self.total_completed - self.total_failed
        return successful / total

    @property
    def throughput(self) -> float:
        """吞吐量（任务/秒）。"""
        uptime = time.time() - self.start_time
        if uptime == 0:
            return 0.0
        return self.total_completed / uptime

    def record_completion(self, duration_ms: float, success: bool, retried: bool = False) -> None:
        """记录任务完成。"""
        self.total_completed += 1
        self.total_duration_ms += duration_ms
        self.max_duration_ms = max(self.max_duration_ms, duration_ms)
        self.min_duration_ms = min(self.min_duration_ms, duration_ms)
        if not success:
            self.total_failed += 1
        if retried:
            self.total_retried += 1

    def to_dict(self) -> dict:
        """转换为字典。"""
        result = {
            "total_submitted": self.total_submitted,
            "total_completed": self.total_completed,
            "total_failed": self.total_failed,
            "total_cancelled": self.total_cancelled,
            "total_timeout": self.total_timeout,
            "total_retried": self.total_retried,
            "total_evicted": self.total_evicted,
            "current_pending": self.current_pending,
            "current_running": self.current_running,
            "avg_duration_ms": round(self.avg_duration_ms, 2),
            "max_duration_ms": round(self.max_duration_ms, 2),
            "min_duration_ms": round(self.min_duration_ms if self.min_duration_ms != float("inf") else 0, 2),
            "success_rate": round(self.success_rate * 100, 2),
            "throughput": round(self.throughput, 4),
            "uptime_seconds": round(time.time() - self.start_time, 2),
        }
        return result

    def reset(self) -> None:
        """重置统计。"""
        self.total_submitted = 0
        self.total_completed = 0
        self.total_failed = 0
        self.total_cancelled = 0
        self.total_timeout = 0
        self.total_retried = 0
        self.total_evicted = 0
        self.current_pending = 0
        self.current_running = 0
        self.total_duration_ms = 0.0
        self.max_duration_ms = 0.0
        self.min_duration_ms = float("inf")
        self.start_time = time.time()


# ===== 优先级队列 =====


class PriorityQueue:
    """优先级队列

    基于堆实现的优先级队列，支持多种调度策略。
    线程安全，适用于多线程环境。

    支持的调度策略：
        - FIFO: 先进先出（按创建时间排序）
        - PRIORITY: 优先级调度（高优先级先执行）
        - DEADLINE: 截止时间调度（最紧急的先执行）
        - ROUND_ROBIN: 轮询调度（按标签轮询）
    """

    def __init__(
        self,
        strategy: SchedulingStrategy = SchedulingStrategy.PRIORITY,
        max_size: int = 10000,
    ):
        """初始化优先级队列。

        Args:
            strategy: 调度策略。
            max_size: 最大队列长度。
        """
        self.strategy = strategy
        self.max_size = max_size
        self._heap: list = []
        self._lock = threading.RLock()
        self._task_map: dict[str, Task] = {}  # 任务 ID 到任务的映射
        self._tag_queues: dict[str, deque] = defaultdict(deque)  # 标签到队列的映射（轮询用）
        self._rr_tags: list = []  # 轮询标签顺序
        self._rr_index: int = 0  # 轮询当前索引
        self._counter = 0  # 入队计数器（用于同优先级 FIFO）

    def push(self, task: Task) -> bool:
        """推入任务到队列。

        Args:
            task: 要入队的任务。

        Returns:
            入队成功返回 True，队列已满返回 False。
        """
        with self._lock:
            if len(self._heap) >= self.max_size:
                return False
            if task.id in self._task_map:
                return False

            self._task_map[task.id] = task
            self._counter += 1

            if self.strategy == SchedulingStrategy.FIFO:
                # 先进先出：按入队顺序
                priority_key = (0, self._counter, task.id)
            elif self.strategy == SchedulingStrategy.PRIORITY:
                # 优先级调度：高优先级先出
                priority_key = (-task.priority_value, self._counter, task.id)
            elif self.strategy == SchedulingStrategy.DEADLINE:
                # 截止时间调度：截止时间早的先出
                deadline = task.deadline if task.deadline > 0 else float("inf")
                priority_key = (deadline, -task.priority_value, task.id)
            else:
                # 默认优先级
                priority_key = (-task.priority_value, self._counter, task.id)

            heapq.heappush(self._heap, (priority_key, task))

            # 轮询调度：按标签入队
            if self.strategy == SchedulingStrategy.ROUND_ROBIN and task.tags:
                tag = task.tags[0]
                self._tag_queues[tag].append(task)
                if tag not in self._rr_tags:
                    self._rr_tags.append(tag)

            return True

    def pop(self) -> Optional[Task]:
        """弹出最高优先级任务。

        Returns:
            Task 实例，队列为空返回 None。
        """
        with self._lock:
            if self.strategy == SchedulingStrategy.ROUND_ROBIN and self._rr_tags:
                return self._pop_round_robin()

            while self._heap:
                _, task = heapq.heappop(self._heap)
                if task.id in self._task_map:
                    del self._task_map[task.id]
                    # 跳过未就绪的任务（定时任务）
                    if not task.is_ready:
                        # 重新入队，稍后再试
                        self._task_map[task.id] = task
                        heapq.heappush(self._heap, ((-task.priority_value, task.created_at, task.id), task))
                        continue
                    # 跳过已过期或已取消的任务
                    if task.is_expired or task.status == TaskStatus.CANCELLED:
                        continue
                    return task
            return None

    def _pop_round_robin(self) -> Optional[Task]:
        """轮询弹出。"""
        if not self._rr_tags:
            return None
        # 尝试从每个标签队列轮询弹出
        for _ in range(len(self._rr_tags)):
            if self._rr_index >= len(self._rr_tags):
                self._rr_index = 0
            tag = self._rr_tags[self._rr_index]
            self._rr_index += 1
            queue = self._tag_queues.get(tag)
            if queue:
                task = queue.popleft()
                if task.id in self._task_map:
                    del self._task_map[task.id]
                    # 同步从堆中移除（标记为已取消，下次 pop 时跳过）
                    task.status = TaskStatus.RUNNING
                    return task
        return None

    def peek(self) -> Optional[Task]:
        """查看队首任务（不弹出）。"""
        with self._lock:
            if not self._heap:
                return None
            return self._heap[0][1]

    def remove(self, task_id: str) -> Optional[Task]:
        """移除指定任务。

        Args:
            task_id: 任务 ID。

        Returns:
            被移除的 Task，不存在返回 None。
        """
        with self._lock:
            task = self._task_map.pop(task_id, None)
            if task is None:
                return None
            # 标记为已取消，下次 pop 时跳过
            task.status = TaskStatus.CANCELLED
            return task

    def get(self, task_id: str) -> Optional[Task]:
        """获取指定任务。"""
        with self._lock:
            return self._task_map.get(task_id)

    def size(self) -> int:
        """获取队列长度。"""
        with self._lock:
            return len(self._task_map)

    def is_empty(self) -> bool:
        """队列是否为空。"""
        with self._lock:
            return len(self._task_map) == 0

    def is_full(self) -> bool:
        """队列是否已满。"""
        with self._lock:
            return len(self._task_map) >= self.max_size

    def clear(self) -> int:
        """清空队列。

        Returns:
            清空的任务数。
        """
        with self._lock:
            count = len(self._task_map)
            self._heap.clear()
            self._task_map.clear()
            self._tag_queues.clear()
            self._rr_tags.clear()
            self._rr_index = 0
            return count

    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        priority: Optional[TaskPriority] = None,
        tag: Optional[str] = None,
    ) -> list:
        """列出队列中的任务（可过滤）。"""
        with self._lock:
            tasks = list(self._task_map.values())
            if status:
                tasks = [t for t in tasks if t.status == status]
            if priority:
                tasks = [t for t in tasks if t.priority == priority]
            if tag:
                tasks = [t for t in tasks if tag in t.tags]
            return tasks

    def get_stats(self) -> dict:
        """获取队列统计。"""
        with self._lock:
            priority_counts = defaultdict(int)
            status_counts = defaultdict(int)
            for task in self._task_map.values():
                priority_counts[task.priority.name] += 1
                status_counts[task.status.name] += 1
            return {
                "size": len(self._task_map),
                "max_size": self.max_size,
                "strategy": self.strategy.value,
                "by_priority": dict(priority_counts),
                "by_status": dict(status_counts),
            }


# ===== 任务处理器 =====


class TaskHandler:
    """任务处理器基类

    所有自定义任务处理器应继承此类并实现 handle 方法。
    处理器负责实际执行任务逻辑。

    使用示例：
        class SearchHandler(TaskHandler):
            async def handle(self, task: Task) -> Any:
                query = task.args[0]
                results = await perform_search(query)
                return results
    """

    def __init__(self, name: str = "", task_types: Optional[list] = None):
        self.name = name or self.__class__.__name__
        self.task_types = task_types or []

    async def handle(self, task: Task) -> Any:
        """处理任务（子类必须实现）。"""
        raise NotImplementedError(f"处理器 {self.name} 未实现 handle 方法")

    def can_handle(self, task: Task) -> bool:
        """判断是否能处理该任务。"""
        if not self.task_types:
            return True
        return task.task_type in self.task_types or task.name in self.task_types


class FunctionalHandler(TaskHandler):
    """函数式任务处理器

    将普通函数包装为任务处理器。
    """

    def __init__(self, func: Callable, name: str = "", task_types: Optional[list] = None):
        super().__init__(name=name or func.__name__, task_types=task_types)
        self._func = func
        self._is_async = asyncio.iscoroutinefunction(func)

    async def handle(self, task: Task) -> Any:
        if self._is_async:
            return await self._func(task)
        # 同步函数在执行器中运行
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._func, task)


# ===== 调度器主类 =====


class Scheduler:
    """任务调度器

    管理任务队列与工作协程，按调度策略执行任务。
    支持并发执行、超时处理、任务取消、重试策略。

    使用示例：
        scheduler = Scheduler(max_workers=4)
        await scheduler.start()

        task_id = scheduler.submit(
            func=my_async_function,
            args=("arg1",),
            priority=TaskPriority.HIGH,
        )

        result = await scheduler.wait_for_result(task_id)
        await scheduler.stop()
    """

    def __init__(
        self,
        max_workers: int = 4,
        strategy: SchedulingStrategy = SchedulingStrategy.PRIORITY,
        config: Optional[SchedulerConfig] = None,
    ):
        """初始化调度器。

        Args:
            max_workers: 最大工作协程数。
            strategy: 调度策略。
            config: 调度器配置（若提供则覆盖前两个参数）。
        """
        if config:
            self.config = config
        else:
            self.config = SchedulerConfig(
                max_workers=max_workers,
                strategy=strategy,
            )

        self._queue = PriorityQueue(
            strategy=self.config.strategy,
            max_size=self.config.max_queue_size,
        )
        self._stats = SchedulerStats()
        self._results: dict[str, TaskResult] = {}
        self._results_lock = threading.Lock()
        self._handlers: dict[str, TaskHandler] = {}
        self._default_handler: Optional[TaskHandler] = None
        self._running: bool = False
        self._workers: list = []
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock = threading.RLock()
        self._task_futures: dict[str, asyncio.Future] = {}
        self._completion_callbacks: dict[str, list[Callable]] = defaultdict(list)
        self._event_subscribers: dict[str, list[Callable]] = defaultdict(list)
        self._worker_tasks: dict[str, str] = {}  # 工作协程 ID -> 任务 ID

    def register_handler(self, handler: TaskHandler) -> None:
        """注册任务处理器。"""
        with self._lock:
            for task_type in handler.task_types:
                self._handlers[task_type] = handler
            if self._default_handler is None:
                self._default_handler = handler

    def set_default_handler(self, handler: TaskHandler) -> None:
        """设置默认任务处理器。"""
        with self._lock:
            self._default_handler = handler
            # 同时注册到 handlers 字典，便于 list_handlers 统一查询
            if handler.name and handler.name not in self._handlers:
                self._handlers[handler.name] = handler

    def submit(
        self,
        func: Optional[Callable] = None,
        args: tuple = (),
        kwargs: Optional[dict] = None,
        name: str = "",
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout: float = 0.0,
        max_retries: int = 0,
        retry_delay: float = 1.0,
        retry_backoff: float = 2.0,
        deadline: float = 0.0,
        scheduled_at: float = 0.0,
        tags: Optional[list] = None,
        depends_on: Optional[list] = None,
        metadata: Optional[dict] = None,
        task_type: TaskType = TaskType.ASYNC,
    ) -> str:
        """提交任务到调度器。

        Args:
            func: 任务执行函数（异步或同步）。
            args: 位置参数。
            kwargs: 关键字参数。
            name: 任务名称。
            priority: 任务优先级。
            timeout: 超时时间（秒）。
            max_retries: 最大重试次数。
            retry_delay: 重试初始延迟。
            retry_backoff: 重试退避倍数。
            deadline: 截止时间（Unix 时间戳，0 表示无截止）。
            scheduled_at: 计划执行时间（Unix 时间戳，0 表示立即执行）。
            tags: 任务标签列表。
            depends_on: 依赖任务 ID 列表。
            metadata: 任务元数据。
            task_type: 任务类型。

        Returns:
            任务 ID。
        """
        kwargs = kwargs or {}
        tags = tags or []
        depends_on = depends_on or []
        metadata = metadata or {}

        # 判断任务类型
        if func and asyncio.iscoroutinefunction(func):
            task_type = TaskType.ASYNC
        elif func:
            task_type = TaskType.SYNC

        task = Task(
            name=name or (func.__name__ if func else "anonymous"),
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            task_type=task_type,
            timeout=timeout or self.config.default_timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
            retry_backoff=retry_backoff,
            deadline=deadline,
            scheduled_at=scheduled_at,
            tags=tags,
            depends_on=depends_on,
            metadata=metadata,
        )

        with self._lock:
            self._stats.total_submitted += 1
            self._stats.current_pending += 1

        success = self._queue.push(task)
        if not success:
            with self._lock:
                self._stats.total_evicted += 1
                self._stats.current_pending -= 1
            logger.warning(f"任务队列已满，任务 {task.id} 被拒绝")
            raise RuntimeError("任务队列已满")

        # 发布事件
        self._publish_event("task_submitted", task)

        return task.id

    def submit_task(self, task: Task) -> str:
        """提交预构造的任务对象。

        Args:
            task: Task 实例。

        Returns:
            任务 ID。
        """
        with self._lock:
            self._stats.total_submitted += 1
            self._stats.current_pending += 1

        success = self._queue.push(task)
        if not success:
            with self._lock:
                self._stats.total_evicted += 1
                self._stats.current_pending -= 1
            raise RuntimeError("任务队列已满")

        self._publish_event("task_submitted", task)
        return task.id

    def cancel(self, task_id: str) -> bool:
        """取消任务。

        Args:
            task_id: 任务 ID。

        Returns:
            取消成功返回 True，任务不存在或已终态返回 False。
        """
        # 从队列移除
        task = self._queue.remove(task_id)
        if task:
            with self._lock:
                self._stats.total_cancelled += 1
                self._stats.current_pending -= 1
            task.status = TaskStatus.CANCELLED
            self._store_result(TaskResult(
                task_id=task_id,
                task_name=task.name,
                status=TaskStatus.CANCELLED,
                error="任务被取消",
            ))
            self._publish_event("task_cancelled", task)
            return True

        # 检查正在运行的任务
        with self._lock:
            future = self._task_futures.get(task_id)
            if future and not future.done():
                future.cancel()
                return True

        return False

    def get_status(self, task_id: str) -> Optional[TaskStatus]:
        """获取任务状态。"""
        # 检查结果
        with self._results_lock:
            result = self._results.get(task_id)
            if result:
                return result.status

        # 检查队列
        task = self._queue.get(task_id)
        if task:
            return task.status

        return None

    def get_result(self, task_id: str) -> Optional[TaskResult]:
        """获取任务结果。"""
        with self._results_lock:
            return self._results.get(task_id)

    async def wait_for_result(
        self, task_id: str, timeout: Optional[float] = None
    ) -> Optional[TaskResult]:
        """等待任务完成并获取结果。

        Args:
            task_id: 任务 ID。
            timeout: 等待超时时间（秒），None 表示无限等待。

        Returns:
            TaskResult 实例，超时返回 None。
        """
        # 检查是否已有结果
        with self._results_lock:
            result = self._results.get(task_id)
            if result:
                return result

        # 等待 Future
        with self._lock:
            future = self._task_futures.get(task_id)

        if future is None:
            # 创建 Future 并等待
            future = asyncio.get_event_loop().create_future()
            with self._lock:
                self._task_futures[task_id] = future

        try:
            if timeout:
                await asyncio.wait_for(future, timeout=timeout)
            else:
                await future
        except asyncio.TimeoutError:
            return None
        except asyncio.CancelledError:
            return None

        with self._results_lock:
            return self._results.get(task_id)

    def on_complete(self, task_id: str, callback: Callable) -> None:
        """注册任务完成回调。"""
        self._completion_callbacks[task_id].append(callback)

    def subscribe_event(self, event_type: str, handler: Callable) -> None:
        """订阅调度器事件。"""
        self._event_subscribers[event_type].append(handler)

    async def start(self) -> None:
        """启动调度器。"""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._loop = asyncio.get_event_loop()
            self._semaphore = asyncio.Semaphore(self.config.max_workers)

        # 启动工作协程
        for i in range(self.config.max_workers):
            worker = asyncio.create_task(self._worker_loop(f"worker-{i}"))
            self._workers.append(worker)

        # 启动清理协程
        if self.config.enable_dead_task_cleanup:
            asyncio.create_task(self._cleanup_loop())

        logger.info(f"调度器已启动，工作协程数: {self.config.max_workers}")
        self._publish_event("scheduler_started", None)

    async def stop(self, graceful: bool = True) -> None:
        """停止调度器。

        Args:
            graceful: 是否优雅停止（等待所有任务完成）。
        """
        with self._lock:
            if not self._running:
                return
            self._running = False

        if graceful:
            # 等待队列清空
            while not self._queue.is_empty():
                await asyncio.sleep(self.config.poll_interval)

        # 取消所有工作协程
        for worker in self._workers:
            worker.cancel()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

        logger.info("调度器已停止")
        self._publish_event("scheduler_stopped", None)

    async def _worker_loop(self, worker_id: str) -> None:
        """工作协程主循环。"""
        logger.debug(f"工作协程 {worker_id} 启动")
        while self._running:
            try:
                task = self._queue.pop()
                if task is None:
                    await asyncio.sleep(self.config.poll_interval)
                    continue

                # 检查依赖是否完成
                if not self._check_dependencies(task):
                    # 依赖未完成，重新入队
                    self._queue.push(task)
                    await asyncio.sleep(self.config.poll_interval)
                    continue

                # 获取信号量（限制并发）
                async with self._semaphore:
                    await self._execute_task(task, worker_id)

            except asyncio.CancelledError:
                logger.debug(f"工作协程 {worker_id} 被取消")
                break
            except Exception as e:
                logger.error(f"工作协程 {worker_id} 异常: {e}", exc_info=True)
                await asyncio.sleep(self.config.poll_interval)

        logger.debug(f"工作协程 {worker_id} 退出")

    async def _execute_task(self, task: Task, worker_id: str) -> None:
        """执行单个任务。"""
        task.status = TaskStatus.RUNNING
        task.start_time = time.time()
        task.worker_id = worker_id

        with self._lock:
            self._stats.current_pending -= 1
            self._stats.current_running += 1
            self._worker_tasks[worker_id] = task.id

        # 创建 Future 用于 wait_for_result
        future = self._loop.create_future()
        with self._lock:
            self._task_futures[task.id] = future

        self._publish_event("task_started", task)

        result = TaskResult(
            task_id=task.id,
            task_name=task.name,
            status=TaskStatus.RUNNING,
            start_time=task.start_time,
        )

        try:
            # 执行任务（带超时与重试）
            task_result = await self._execute_with_retry(task)
            result.status = task_result.status
            result.result = task_result.result
            result.error = task_result.error
            result.error_type = task_result.error_type
            result.retry_count = task_result.retry_count

        except Exception as e:
            result.status = TaskStatus.FAILED
            result.error = str(e)
            result.error_type = type(e).__name__
            logger.error(f"任务 {task.name} 执行异常: {e}", exc_info=True)

        finally:
            task.end_time = time.time()
            task.duration_ms = (task.end_time - task.start_time) * 1000
            task.status = result.status
            task.result = result.result
            task.error = result.error

            result.end_time = task.end_time
            result.duration_ms = task.duration_ms

            # 存储结果
            self._store_result(result)

            # 更新统计
            with self._lock:
                self._stats.current_running -= 1
                self._stats.record_completion(
                    task.duration_ms,
                    success=result.success,
                    retried=result.retry_count > 0,
                )
                if result.status == TaskStatus.TIMEOUT:
                    self._stats.total_timeout += 1
                if result.status == TaskStatus.CANCELLED:
                    self._stats.total_cancelled += 1
                self._worker_tasks.pop(worker_id, None)

            # 完成 Future
            if not future.done():
                future.set_result(result)

            # 触发回调
            self._trigger_completion_callbacks(task.id, result)

            # 发布事件
            self._publish_event("task_completed", task)

    async def _execute_with_retry(self, task: Task) -> TaskResult:
        """带重试执行任务。"""
        max_attempts = task.max_retries + 1
        current_delay = task.retry_delay
        last_error = None
        last_error_type = None

        for attempt in range(max_attempts):
            if task.status == TaskStatus.CANCELLED:
                return TaskResult(
                    task_id=task.id,
                    task_name=task.name,
                    status=TaskStatus.CANCELLED,
                )

            try:
                # 带超时执行
                if task.timeout > 0:
                    result_value = await asyncio.wait_for(
                        self._invoke_task(task), timeout=task.timeout
                    )
                else:
                    result_value = await self._invoke_task(task)

                return TaskResult(
                    task_id=task.id,
                    task_name=task.name,
                    status=TaskStatus.SUCCESS,
                    result=result_value,
                    retry_count=attempt,
                )

            except asyncio.TimeoutError:
                last_error = f"任务超时（{task.timeout}s）"
                last_error_type = "TimeoutError"
                logger.warning(f"任务 {task.name} 第 {attempt + 1} 次执行超时")
                if attempt < max_attempts - 1:
                    task.status = TaskStatus.RETRYING
                    task.retry_count = attempt + 1
                    await asyncio.sleep(current_delay)
                    current_delay *= task.retry_backoff
                    continue
                return TaskResult(
                    task_id=task.id,
                    task_name=task.name,
                    status=TaskStatus.TIMEOUT,
                    error=last_error,
                    error_type=last_error_type,
                    retry_count=attempt,
                )

            except asyncio.CancelledError:
                return TaskResult(
                    task_id=task.id,
                    task_name=task.name,
                    status=TaskStatus.CANCELLED,
                )

            except Exception as e:
                last_error = str(e)
                last_error_type = type(e).__name__
                logger.warning(
                    f"任务 {task.name} 第 {attempt + 1} 次执行失败: {e}"
                )
                if attempt < max_attempts - 1:
                    task.status = TaskStatus.RETRYING
                    task.retry_count = attempt + 1
                    await asyncio.sleep(current_delay)
                    current_delay *= task.retry_backoff
                    continue
                return TaskResult(
                    task_id=task.id,
                    task_name=task.name,
                    status=TaskStatus.FAILED,
                    error=last_error,
                    error_type=last_error_type,
                    retry_count=attempt,
                )

        return TaskResult(
            task_id=task.id,
            task_name=task.name,
            status=TaskStatus.FAILED,
            error=last_error or "未知错误",
            error_type=last_error_type,
        )

    async def _invoke_task(self, task: Task) -> Any:
        """调用任务函数。"""
        # 查找处理器
        handler = self._find_handler(task)
        if handler:
            return await handler.handle(task)

        # 直接调用函数
        if task.func is None:
            raise ValueError(f"任务 {task.name} 无执行函数且无匹配处理器")

        if asyncio.iscoroutinefunction(task.func):
            return await task.func(*task.args, **task.kwargs)
        else:
            # 同步函数在执行器中运行
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, lambda: task.func(*task.args, **task.kwargs)
            )

    def _find_handler(self, task: Task) -> Optional[TaskHandler]:
        """查找任务处理器。"""
        with self._lock:
            # 按任务类型查找
            handler = self._handlers.get(task.task_type)
            if handler and handler.can_handle(task):
                return handler
            # 按任务名查找
            handler = self._handlers.get(task.name)
            if handler and handler.can_handle(task):
                return handler
            # 按标签查找
            for tag in task.tags:
                handler = self._handlers.get(tag)
                if handler and handler.can_handle(task):
                    return handler
            # 默认处理器
            if self._default_handler and self._default_handler.can_handle(task):
                return self._default_handler
        return None

    def _check_dependencies(self, task: Task) -> bool:
        """检查任务依赖是否已完成。"""
        if not task.depends_on:
            return True
        for dep_id in task.depends_on:
            with self._results_lock:
                result = self._results.get(dep_id)
            if result is None or not result.success:
                return False
        return True

    def _store_result(self, result: TaskResult) -> None:
        """存储任务结果。"""
        with self._results_lock:
            self._results[result.task_id] = result
            # 限制结果缓存大小
            if len(self._results) > 10000:
                # 移除最早的结果
                oldest_id = next(iter(self._results))
                del self._results[oldest_id]

    def _trigger_completion_callbacks(self, task_id: str, result: TaskResult) -> None:
        """触发完成回调。"""
        callbacks = self._completion_callbacks.pop(task_id, [])
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(result))
                else:
                    callback(result)
            except Exception as e:
                logger.error(f"完成回调异常: {e}", exc_info=True)

    def _publish_event(self, event_type: str, task: Optional[Task]) -> None:
        """发布调度器事件。"""
        subscribers = self._event_subscribers.get(event_type, [])
        for subscriber in subscribers:
            try:
                subscriber(event_type, task)
            except Exception as e:
                logger.error(f"事件订阅者异常: {e}", exc_info=True)

    async def _cleanup_loop(self) -> None:
        """清理循环（定期清理过期结果）。"""
        while self._running:
            try:
                await asyncio.sleep(60)  # 每分钟清理一次
                self._cleanup_expired_results()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"清理循环异常: {e}", exc_info=True)

    def _cleanup_expired_results(self) -> int:
        """清理过期结果。

        Returns:
            清理的结果数。
        """
        if self.config.dead_task_ttl <= 0:
            return 0
        cutoff = time.time() - self.config.dead_task_ttl
        removed = 0
        with self._results_lock:
            expired_ids = [
                tid for tid, result in self._results.items()
                if result.end_time > 0 and result.end_time < cutoff
            ]
            for tid in expired_ids:
                del self._results[tid]
                removed += 1
        if removed > 0:
            logger.debug(f"清理了 {removed} 个过期结果")
        return removed

    def get_stats(self) -> dict:
        """获取调度器统计。"""
        with self._lock:
            stats = self._stats.to_dict()
        stats["queue"] = self._queue.get_stats()
        stats["is_running"] = self._running
        stats["worker_count"] = len(self._workers)
        stats["handler_count"] = len(self._handlers)
        return stats

    def get_queue_size(self) -> int:
        """获取队列长度。"""
        return self._queue.size()

    def get_pending_tasks(self) -> list:
        """获取待执行任务列表。"""
        return self._queue.list_tasks(status=TaskStatus.PENDING)

    def get_running_tasks(self) -> list:
        """获取执行中任务列表。"""
        with self._lock:
            return [
                {"worker_id": wid, "task_id": tid}
                for wid, tid in self._worker_tasks.items()
            ]

    def list_handlers(self) -> list:
        """列出所有已注册处理器。"""
        with self._lock:
            return [
                {"name": h.name, "task_types": h.task_types}
                for h in self._handlers.values()
            ]

    @property
    def is_running(self) -> bool:
        """调度器是否正在运行。"""
        return self._running

    def reset_stats(self) -> None:
        """重置统计。"""
        with self._lock:
            self._stats.reset()

    def clear_results(self) -> int:
        """清空结果缓存。

        Returns:
            清空的结果数。
        """
        with self._results_lock:
            count = len(self._results)
            self._results.clear()
            return count


# ===== 定时任务调度器 =====


class ScheduledTaskScheduler:
    """定时任务调度器

    支持定时执行任务，基于 cron 表达式或固定间隔。

    使用示例：
        scheduler = ScheduledTaskScheduler()
        scheduler.schedule_every(
            func=my_task,
            interval=3600,  # 每小时执行一次
            name="hourly_report",
        )
        scheduler.schedule_at(
            func=my_task,
            run_at=time.time() + 86400,  # 明天此时
            name="daily_report",
        )
        await scheduler.start()
    """

    def __init__(self, base_scheduler: Optional[Scheduler] = None):
        self._base_scheduler = base_scheduler or Scheduler()
        self._scheduled_tasks: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._running = False

    def schedule_every(
        self,
        func: Callable,
        interval: float,
        name: str = "",
        priority: TaskPriority = TaskPriority.NORMAL,
        args: tuple = (),
        kwargs: Optional[dict] = None,
    ) -> str:
        """按固定间隔重复执行任务。

        Args:
            func: 任务函数。
            interval: 执行间隔（秒）。
            name: 任务名称。
            priority: 任务优先级。
            args: 位置参数。
            kwargs: 关键字参数。

        Returns:
            调度任务 ID。
        """
        kwargs = kwargs or {}
        task_id = str(uuid.uuid4())
        with self._lock:
            self._scheduled_tasks[task_id] = {
                "id": task_id,
                "name": name or func.__name__,
                "func": func,
                "interval": interval,
                "priority": priority,
                "args": args,
                "kwargs": kwargs,
                "type": "periodic",
                "next_run": time.time() + interval,
                "enabled": True,
            }
        return task_id

    def schedule_at(
        self,
        func: Callable,
        run_at: float,
        name: str = "",
        priority: TaskPriority = TaskPriority.NORMAL,
        args: tuple = (),
        kwargs: Optional[dict] = None,
    ) -> str:
        """在指定时间执行一次性任务。

        Args:
            func: 任务函数。
            run_at: 执行时间（Unix 时间戳）。
            name: 任务名称。
            priority: 任务优先级。
            args: 位置参数。
            kwargs: 关键字参数。

        Returns:
            调度任务 ID。
        """
        kwargs = kwargs or {}
        task_id = str(uuid.uuid4())
        with self._lock:
            self._scheduled_tasks[task_id] = {
                "id": task_id,
                "name": name or func.__name__,
                "func": func,
                "run_at": run_at,
                "priority": priority,
                "args": args,
                "kwargs": kwargs,
                "type": "one_shot",
                "next_run": run_at,
                "enabled": True,
            }
        return task_id

    def schedule_cron(
        self,
        func: Callable,
        cron_expression: str,
        name: str = "",
        priority: TaskPriority = TaskPriority.NORMAL,
        args: tuple = (),
        kwargs: Optional[dict] = None,
    ) -> str:
        """按 cron 表达式执行任务。

        Args:
            func: 任务函数。
            cron_expression: cron 表达式（如 "0 * * * *" 每小时）。
            name: 任务名称。
            priority: 任务优先级。
            args: 位置参数。
            kwargs: 关键字参数。

        Returns:
            调度任务 ID。
        """
        kwargs = kwargs or {}
        task_id = str(uuid.uuid4())
        # 简化实现：仅存储 cron 表达式，实际解析需要 croniter 库
        with self._lock:
            self._scheduled_tasks[task_id] = {
                "id": task_id,
                "name": name or func.__name__,
                "func": func,
                "cron": cron_expression,
                "priority": priority,
                "args": args,
                "kwargs": kwargs,
                "type": "cron",
                "next_run": time.time() + 3600,  # 简化：默认1小时后
                "enabled": True,
            }
        return task_id

    def cancel_scheduled(self, task_id: str) -> bool:
        """取消定时任务。"""
        with self._lock:
            if task_id in self._scheduled_tasks:
                self._scheduled_tasks[task_id]["enabled"] = False
                del self._scheduled_tasks[task_id]
                return True
            return False

    def list_scheduled(self) -> list:
        """列出所有定时任务。"""
        with self._lock:
            return list(self._scheduled_tasks.values())

    async def start(self) -> None:
        """启动定时调度器。"""
        self._running = True
        await self._base_scheduler.start()
        asyncio.create_task(self._schedule_loop())
        logger.info("定时任务调度器已启动")

    async def stop(self) -> None:
        """停止定时调度器。"""
        self._running = False
        await self._base_scheduler.stop()
        logger.info("定时任务调度器已停止")

    async def _schedule_loop(self) -> None:
        """调度循环。"""
        while self._running:
            try:
                now = time.time()
                with self._lock:
                    due_tasks = [
                        t for t in self._scheduled_tasks.values()
                        if t["enabled"] and t["next_run"] <= now
                    ]

                for task_info in due_tasks:
                    # 提交到基础调度器
                    self._base_scheduler.submit(
                        func=task_info["func"],
                        args=task_info["args"],
                        kwargs=task_info["kwargs"],
                        name=task_info["name"],
                        priority=task_info["priority"],
                        scheduled_at=0,  # 立即执行
                    )

                    # 更新下次执行时间
                    with self._lock:
                        if task_info["id"] in self._scheduled_tasks:
                            if task_info["type"] == "periodic":
                                task_info["next_run"] = now + task_info["interval"]
                            elif task_info["type"] == "one_shot":
                                # 一次性任务，执行后移除
                                del self._scheduled_tasks[task_info["id"]]
                            elif task_info["type"] == "cron":
                                # 简化：默认1小时后
                                task_info["next_run"] = now + 3600

                await asyncio.sleep(1)  # 每秒检查一次

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"定时调度循环异常: {e}", exc_info=True)
                await asyncio.sleep(5)


# ===== 任务优先级管理器 =====


class PriorityManager:
    """任务优先级管理器

    动态调整任务优先级，支持基于等待时间的优先级提升、基于截止时间的紧急提升。
    """

    def __init__(
        self,
        aging_threshold: float = 300.0,  # 老化阈值（秒）：等待超过此时间后提升优先级
        aging_boost: int = 1,  # 老化提升级别
        deadline_threshold: float = 60.0,  # 截止紧急阈值（秒）：距截止时间小于此值时提升为紧急
    ):
        self.aging_threshold = aging_threshold
        self.aging_boost = aging_boost
        self.deadline_threshold = deadline_threshold

    def adjust_priority(self, task: Task) -> TaskPriority:
        """调整任务优先级。

        Args:
            task: 待调整的任务。

        Returns:
            调整后的优先级。
        """
        current_priority = task.priority
        wait_time = time.time() - task.created_at

        # 老化提升：等待时间超过阈值
        if wait_time > self.aging_threshold:
            new_value = min(
                current_priority.value + self.aging_boost,
                TaskPriority.URGENT.value
            )
            current_priority = TaskPriority.from_value(new_value)

        # 截止紧急提升：接近截止时间
        if task.deadline > 0:
            time_to_deadline = task.deadline - time.time()
            if time_to_deadline < self.deadline_threshold:
                current_priority = TaskPriority.URGENT

        return current_priority

    def batch_adjust(self, tasks: list) -> dict:
        """批量调整优先级。

        Args:
            tasks: 任务列表。

        Returns:
            {task_id: new_priority} 字典。
        """
        adjustments = {}
        for task in tasks:
            new_priority = self.adjust_priority(task)
            if new_priority != task.priority:
                adjustments[task.id] = new_priority
                task.priority = new_priority
        return adjustments


# ===== 任务依赖图 =====


class TaskDependencyGraph:
    """任务依赖图

    管理任务间的依赖关系，支持拓扑排序与循环检测。
    """

    def __init__(self):
        self._nodes: dict[str, Task] = {}
        self._edges: dict[str, set] = defaultdict(set)  # 依赖边：task -> 依赖的 tasks
        self._reverse_edges: dict[str, set] = defaultdict(set)  # 反向边：task -> 被依赖的 tasks
        self._lock = threading.Lock()

    def add_task(self, task: Task) -> None:
        """添加任务节点。"""
        with self._lock:
            self._nodes[task.id] = task
            for dep_id in task.depends_on:
                self._edges[task.id].add(dep_id)
                self._reverse_edges[dep_id].add(task.id)

    def remove_task(self, task_id: str) -> Optional[Task]:
        """移除任务节点。"""
        with self._lock:
            task = self._nodes.pop(task_id, None)
            if task is None:
                return None
            # 移除边
            for dep_id in self._edges.pop(task_id, set()):
                self._reverse_edges[dep_id].discard(task_id)
            for dependent_id in self._reverse_edges.pop(task_id, set()):
                self._edges[dependent_id].discard(task_id)
            return task

    def add_dependency(self, task_id: str, depends_on_id: str) -> bool:
        """添加依赖关系。

        Args:
            task_id: 任务 ID。
            depends_on_id: 依赖的任务 ID。

        Returns:
            添加成功返回 True，存在循环依赖返回 False。
        """
        with self._lock:
            # 检查循环依赖
            if self._would_create_cycle(task_id, depends_on_id):
                return False
            self._edges[task_id].add(depends_on_id)
            self._reverse_edges[depends_on_id].add(task_id)
            if task_id in self._nodes:
                self._nodes[task_id].depends_on.append(depends_on_id)
            return True

    def _would_create_cycle(self, task_id: str, depends_on_id: str) -> bool:
        """检查添加依赖是否会创建循环。"""
        # BFS 检查 depends_on_id 是否间接依赖 task_id
        visited = set()
        queue = deque([depends_on_id])
        while queue:
            current = queue.popleft()
            if current == task_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            queue.extend(self._edges.get(current, set()))
        return False

    def get_ready_tasks(self) -> list:
        """获取就绪任务（所有依赖已完成）。"""
        with self._lock:
            ready = []
            for task_id, task in self._nodes.items():
                if task.status != TaskStatus.PENDING:
                    continue
                deps = self._edges.get(task_id, set())
                if not deps:
                    ready.append(task)
                else:
                    all_deps_done = True
                    for dep_id in deps:
                        dep_task = self._nodes.get(dep_id)
                        if dep_task is None or dep_task.status != TaskStatus.SUCCESS:
                            all_deps_done = False
                            break
                    if all_deps_done:
                        ready.append(task)
            return ready

    def topological_sort(self) -> list:
        """拓扑排序。"""
        with self._lock:
            in_degree = {tid: 0 for tid in self._nodes}
            for task_id, deps in self._edges.items():
                if task_id in in_degree:
                    in_degree[task_id] = len(deps)

            queue = deque([tid for tid, deg in in_degree.items() if deg == 0])
            result = []

            while queue:
                task_id = queue.popleft()
                if task_id in self._nodes:
                    result.append(self._nodes[task_id])
                for dependent_id in self._reverse_edges.get(task_id, set()):
                    in_degree[dependent_id] -= 1
                    if in_degree[dependent_id] == 0:
                        queue.append(dependent_id)

            if len(result) != len(self._nodes):
                # 存在循环
                logger.warning("依赖图存在循环，拓扑排序不完整")

            return result

    def has_cycle(self) -> bool:
        """检测是否存在循环依赖。"""
        with self._lock:
            WHITE, GRAY, BLACK = 0, 1, 2
            color = {tid: WHITE for tid in self._nodes}

            def dfs(node_id: str) -> bool:
                color[node_id] = GRAY
                for dep_id in self._edges.get(node_id, set()):
                    if dep_id not in color:
                        continue
                    if color[dep_id] == GRAY:
                        return True
                    if color[dep_id] == WHITE and dfs(dep_id):
                        return True
                color[node_id] = BLACK
                return False

            for task_id in self._nodes:
                if color[task_id] == WHITE:
                    if dfs(task_id):
                        return True
            return False

    def get_dependencies(self, task_id: str) -> list:
        """获取任务的直接依赖。"""
        with self._lock:
            return list(self._edges.get(task_id, set()))

    def get_dependents(self, task_id: str) -> list:
        """获取直接依赖该任务的任务列表。"""
        with self._lock:
            return list(self._reverse_edges.get(task_id, set()))

    def get_all_dependencies(self, task_id: str) -> list:
        """获取所有传递依赖。"""
        with self._lock:
            visited = set()
            queue = deque([task_id])
            while queue:
                current = queue.popleft()
                for dep_id in self._edges.get(current, set()):
                    if dep_id not in visited:
                        visited.add(dep_id)
                        queue.append(dep_id)
            return list(visited)


# ===== 全局实例 =====


# 全局调度器实例
_global_scheduler: Optional[Scheduler] = None
_global_scheduler_lock = threading.Lock()


def get_scheduler() -> Scheduler:
    """获取全局调度器实例。"""
    global _global_scheduler
    with _global_scheduler_lock:
        if _global_scheduler is None:
            _global_scheduler = Scheduler()
        return _global_scheduler


def set_scheduler(scheduler: Scheduler) -> None:
    """设置全局调度器实例。"""
    global _global_scheduler
    with _global_scheduler_lock:
        _global_scheduler = scheduler


def reset_scheduler() -> None:
    """重置全局调度器。"""
    global _global_scheduler
    with _global_scheduler_lock:
        if _global_scheduler and _global_scheduler.is_running:
            # 不能同步停止异步调度器，仅清除引用
            pass
        _global_scheduler = None


# ===== 便捷函数 =====


def create_scheduler(
    max_workers: int = 4,
    strategy: SchedulingStrategy = SchedulingStrategy.PRIORITY,
) -> Scheduler:
    """创建调度器的便捷函数。"""
    return Scheduler(max_workers=max_workers, strategy=strategy)


def create_task(
    func: Callable,
    args: tuple = (),
    kwargs: Optional[dict] = None,
    name: str = "",
    priority: TaskPriority = TaskPriority.NORMAL,
    **kwargs_extra,
) -> Task:
    """创建任务对象的便捷函数。"""
    kwargs = kwargs or {}
    return Task(
        name=name or func.__name__,
        func=func,
        args=args,
        kwargs=kwargs,
        priority=priority,
        **kwargs_extra,
    )


def create_handler(func: Callable, name: str = "") -> FunctionalHandler:
    """创建函数式处理器的便捷函数。"""
    return FunctionalHandler(func=func, name=name)


def create_retry_policy(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
) -> RetryPolicy:
    """创建重试策略的便捷函数。"""
    return RetryPolicy(
        max_retries=max_retries,
        initial_delay=initial_delay,
        backoff_factor=backoff_factor,
    )


# ===== 模块导出 =====


__all__ = [
    # 枚举
    "TaskPriority",
    "TaskStatus",
    "SchedulingStrategy",
    "TaskType",
    # 数据类
    "Task",
    "TaskResult",
    "RetryPolicy",
    "SchedulerConfig",
    "SchedulerStats",
    # 队列
    "PriorityQueue",
    # 处理器
    "TaskHandler",
    "FunctionalHandler",
    # 调度器
    "Scheduler",
    "ScheduledTaskScheduler",
    # 管理器
    "PriorityManager",
    "TaskDependencyGraph",
    # 便捷函数
    "create_scheduler",
    "create_task",
    "create_handler",
    "create_retry_policy",
    "get_scheduler",
    "set_scheduler",
    "reset_scheduler",
]
