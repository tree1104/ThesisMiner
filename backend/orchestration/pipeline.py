"""编排管道模块

提供阶段化的任务编排能力，支持阶段组合、顺序执行、错误处理、重试逻辑、
超时控制、条件分支、并行执行等高级编排特性。

核心组件：
    - PipelineContext: 管道上下文（在阶段间传递数据的容器）
    - StageResult: 阶段执行结果
    - PipelineStage: 阶段基类（所有自定义阶段继承此类）
    - Pipeline: 管道主类（管理阶段列表与执行流程）
    - PipelineExecutor: 管道执行器（支持同步与异步执行）
    - PipelineMonitor: 管道监控器（记录执行指标与事件）
    - PipelineTemplateRegistry: 管道模板注册表（20+ 预定义模板）

设计原则：
    1. 可组合：阶段可自由组合为不同管道，支持插入、移除、替换
    2. 可观测：每个阶段执行记录耗时、状态、输出，便于调试与监控
    3. 可恢复：支持检查点机制，管道中断后可从指定阶段恢复
    4. 可扩展：通过继承 PipelineStage 实现自定义阶段，无需修改框架代码
    5. 容错性：支持重试、超时、降级、回滚等错误处理策略

使用示例：
    # 创建管道
    pipeline = Pipeline(name="proposal_generation")

    # 添加阶段
    pipeline.add_stage(SearchStage())
    pipeline.add_stage(ReasonStage())
    pipeline.add_stage(CriticStage())

    # 执行管道
    context = PipelineContext(input_data={"query": "深度学习"})
    result = pipeline.execute(context)
    if result.success:
        print("管道执行成功", result.data)
"""
import asyncio
import logging
import os
import threading
import time
import traceback
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, Union

logger = logging.getLogger(__name__)


# ===== 枚举定义 =====


class StageStatus(Enum):
    """阶段执行状态枚举"""

    PENDING = "pending"  # 待执行
    RUNNING = "running"  # 执行中
    SUCCESS = "success"  # 成功
    FAILED = "failed"  # 失败
    SKIPPED = "skipped"  # 跳过
    RETRYING = "retrying"  # 重试中
    TIMEOUT = "timeout"  # 超时
    CANCELLED = "cancelled"  # 已取消


class PipelineStatus(Enum):
    """管道执行状态枚举"""

    IDLE = "idle"  # 空闲
    RUNNING = "running"  # 运行中
    SUCCESS = "success"  # 成功
    FAILED = "failed"  # 失败
    CANCELLED = "cancelled"  # 已取消
    PARTIAL = "partial"  # 部分成功（某些阶段跳过或失败但管道继续）


class ErrorHandlingStrategy(Enum):
    """错误处理策略枚举"""

    RAISE = "raise"  # 抛出异常，终止管道
    SKIP = "skip"  # 跳过失败阶段，继续执行
    RETRY = "retry"  # 重试失败阶段
    FALLBACK = "fallback"  # 使用降级逻辑
    ROLLBACK = "rollback"  # 回滚到检查点


class TemplateCategory(Enum):
    """管道模板分类枚举"""

    GENERATION = "generation"  # 生成类
    VALIDATION = "validation"  # 校验类
    ANALYSIS = "analysis"  # 分析类
    ASSIST = "assist"  # 辅助类
    BATCH = "batch"  # 批处理类
    ADVANCED = "advanced"  # 高级类


# ===== 数据类定义 =====


@dataclass
class StageResult:
    """阶段执行结果

    封装单个阶段执行后的输出数据与元信息。
    """

    stage_name: str = ""
    status: StageStatus = StageStatus.PENDING
    data: Any = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    traceback: Optional[str] = None
    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: float = 0.0
    retry_count: int = 0
    metadata: dict = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """是否成功"""
        return self.status == StageStatus.SUCCESS

    @property
    def failed(self) -> bool:
        """是否失败"""
        return self.status in (StageStatus.FAILED, StageStatus.TIMEOUT)

    @property
    def skipped(self) -> bool:
        """是否跳过"""
        return self.status == StageStatus.SKIPPED

    def to_dict(self) -> dict:
        """转换为字典表示"""
        return {
            "stage_name": self.stage_name,
            "status": self.status.value,
            "data": self.data,
            "error": self.error,
            "error_type": self.error_type,
            "duration_ms": round(self.duration_ms, 2),
            "retry_count": self.retry_count,
            "metadata": self.metadata,
        }


@dataclass
class PipelineResult:
    """管道执行结果

    封装整个管道执行后的汇总结果。
    """

    pipeline_name: str = ""
    status: PipelineStatus = PipelineStatus.IDLE
    data: Any = None
    stage_results: list = field(default_factory=list)
    error: Optional[str] = None
    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: float = 0.0
    total_stages: int = 0
    executed_stages: int = 0
    failed_stages: int = 0
    skipped_stages: int = 0
    metadata: dict = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """是否成功"""
        return self.status == PipelineStatus.SUCCESS

    @property
    def failed(self) -> bool:
        """是否失败"""
        return self.status == PipelineStatus.FAILED

    def get_stage_result(self, stage_name: str) -> Optional[StageResult]:
        """按名称获取阶段结果"""
        for result in self.stage_results:
            if isinstance(result, StageResult) and result.stage_name == stage_name:
                return result
            if isinstance(result, dict) and result.get("stage_name") == stage_name:
                return StageResult(
                    stage_name=result.get("stage_name", ""),
                    status=StageStatus(result.get("status", "pending")),
                    data=result.get("data"),
                )
        return None

    def to_dict(self) -> dict:
        """转换为字典表示"""
        return {
            "pipeline_name": self.pipeline_name,
            "status": self.status.value,
            "data": self.data,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 2),
            "total_stages": self.total_stages,
            "executed_stages": self.executed_stages,
            "failed_stages": self.failed_stages,
            "skipped_stages": self.skipped_stages,
            "stage_results": [
                r.to_dict() if isinstance(r, StageResult) else r
                for r in self.stage_results
            ],
            "metadata": self.metadata,
        }


# ===== 管道上下文 =====


class PipelineContext:
    """管道上下文

    在阶段间传递数据的容器，包含输入数据、中间结果、共享状态与元信息。
    线程安全，支持并发访问。

    使用示例：
        context = PipelineContext(input_data={"query": "深度学习"})
        context.set("search_results", [...])  # 阶段1输出
        results = context.get("search_results")  # 阶段2读取
    """

    def __init__(
        self,
        input_data: Optional[dict] = None,
        metadata: Optional[dict] = None,
        session_id: str = "",
        conversation_id: str = "",
    ):
        """初始化管道上下文。

        Args:
            input_data: 输入数据字典。
            metadata: 元信息字典。
            session_id: 会话 ID。
            conversation_id: 对话 ID。
        """
        self.input_data: dict = input_data or {}
        self.metadata: dict = metadata or {}
        self.session_id: str = session_id
        self.conversation_id: str = conversation_id
        self._data: dict = {}
        self._lock = threading.RLock()
        # 检查点记录（阶段名 -> 上下文快照）
        self._checkpoints: OrderedDict = OrderedDict()
        # 执行历史
        self._execution_log: list = []
        # 用户输入（便捷访问）
        self.user_input: str = self.input_data.get("user_input", "") or self.input_data.get("query", "")
        # 学位与学科（便捷访问）
        self.degree: str = self.input_data.get("degree", "master")
        self.discipline: str = self.input_data.get("discipline", "")
        # 当前阶段名
        self.current_stage: str = ""
        # 是否已取消
        self._cancelled: bool = False

    def set(self, key: str, value: Any) -> None:
        """设置上下文数据。"""
        with self._lock:
            self._data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """获取上下文数据。"""
        with self._lock:
            return self._data.get(key, default)

    def update(self, data: dict) -> None:
        """批量更新上下文数据。"""
        with self._lock:
            self._data.update(data)

    def remove(self, key: str) -> bool:
        """移除上下文数据。"""
        with self._lock:
            if key in self._data:
                del self._data[key]
                return True
            return False

    def has(self, key: str) -> bool:
        """判断键是否存在。"""
        with self._lock:
            return key in self._data

    def keys(self) -> list:
        """返回所有键。"""
        with self._lock:
            return list(self._data.keys())

    def to_dict(self) -> dict:
        """转换为字典（包含输入数据与中间结果）。"""
        with self._lock:
            return {
                "input_data": self.input_data,
                "data": dict(self._data),
                "metadata": self.metadata,
                "session_id": self.session_id,
                "conversation_id": self.conversation_id,
                "current_stage": self.current_stage,
            }

    def save_checkpoint(self, stage_name: str) -> None:
        """保存检查点（当前上下文快照）。"""
        with self._lock:
            self._checkpoints[stage_name] = {
                "data": dict(self._data),
                "metadata": dict(self.metadata),
                "timestamp": time.time(),
            }

    def restore_checkpoint(self, stage_name: str) -> bool:
        """恢复检查点。"""
        with self._lock:
            if stage_name not in self._checkpoints:
                return False
            checkpoint = self._checkpoints[stage_name]
            self._data = dict(checkpoint["data"])
            self.metadata = dict(checkpoint["metadata"])
            return True

    def list_checkpoints(self) -> list:
        """列出所有检查点。"""
        with self._lock:
            return list(self._checkpoints.keys())

    def log_execution(self, stage_name: str, status: str, duration_ms: float, details: Optional[dict] = None) -> None:
        """记录执行日志。"""
        with self._lock:
            self._execution_log.append({
                "stage": stage_name,
                "status": status,
                "duration_ms": duration_ms,
                "timestamp": time.time(),
                "details": details or {},
            })

    def get_execution_log(self) -> list:
        """获取执行日志。"""
        with self._lock:
            return list(self._execution_log)

    def cancel(self) -> None:
        """取消管道执行。"""
        with self._lock:
            self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        """是否已取消。"""
        with self._lock:
            return self._cancelled

    def clone(self) -> "PipelineContext":
        """克隆上下文（深拷贝数据）。"""
        import copy
        with self._lock:
            cloned = PipelineContext(
                input_data=copy.deepcopy(self.input_data),
                metadata=copy.deepcopy(self.metadata),
                session_id=self.session_id,
                conversation_id=self.conversation_id,
            )
            cloned._data = copy.deepcopy(self._data)
            cloned.user_input = self.user_input
            cloned.degree = self.degree
            cloned.discipline = self.discipline
            return cloned

    def merge(self, other: "PipelineContext") -> None:
        """合并另一个上下文的数据。"""
        with self._lock:
            self._data.update(other._data)
            self.metadata.update(other.metadata)


# ===== 阶段基类 =====


class PipelineStage:
    """管道阶段基类

    所有自定义阶段应继承此类并实现 execute 方法。
    阶段是管道的最小执行单元，接收上下文并产出结果。

    使用示例：
        class SearchStage(PipelineStage):
            def execute(self, context):
                results = perform_search(context.user_input)
                context.set("search_results", results)
                return StageResult(
                    stage_name=self.name,
                    status=StageStatus.SUCCESS,
                    data=results,
                )
    """

    def __init__(
        self,
        name: str = "",
        description: str = "",
        timeout: float = 0.0,
        max_retries: int = 0,
        retry_delay: float = 1.0,
        retry_backoff: float = 2.0,
        error_strategy: ErrorHandlingStrategy = ErrorHandlingStrategy.RAISE,
        fallback_stage: Optional["PipelineStage"] = None,
        condition: Optional[Callable[["PipelineContext"], bool]] = None,
        tags: Optional[list] = None,
    ):
        """初始化管道阶段。

        Args:
            name: 阶段名称（唯一标识）。
            description: 阶段描述。
            timeout: 超时时间（秒），0 表示不限制。
            max_retries: 最大重试次数。
            retry_delay: 重试初始延迟（秒）。
            retry_backoff: 重试退避倍数。
            error_strategy: 错误处理策略。
            fallback_stage: 降级阶段（当本阶段失败且策略为 FALLBACK 时执行）。
            condition: 执行条件函数（返回 False 则跳过本阶段）。
            tags: 标签列表（用于分组与过滤）。
        """
        self.name = name or self.__class__.__name__
        self.description = description
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.retry_backoff = retry_backoff
        self.error_strategy = error_strategy
        self.fallback_stage = fallback_stage
        self.condition = condition
        self.tags = tags or []
        # 阶段是否已初始化
        self._initialized = False
        # 前置阶段（依赖）
        self._depends_on: list = []
        # 后置阶段（被依赖）
        self._dependents: list = []

    def execute(self, context: PipelineContext) -> StageResult:
        """执行阶段逻辑（子类必须实现）。

        Args:
            context: 管道上下文。

        Returns:
            StageResult 实例。
        """
        raise NotImplementedError(f"阶段 {self.name} 未实现 execute 方法")

    async def execute_async(self, context: PipelineContext) -> StageResult:
        """异步执行阶段逻辑。

        默认实现为在执行器中运行同步 execute 方法。
        子类可重写此方法实现真正的异步逻辑。

        Args:
            context: 管道上下文。

        Returns:
            StageResult 实例。
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.execute, context)

    def should_run(self, context: PipelineContext) -> bool:
        """判断是否应执行本阶段。

        Args:
            context: 管道上下文。

        Returns:
            True 表示应执行，False 表示跳过。
        """
        if context.is_cancelled:
            return False
        if self.condition is not None:
            try:
                return bool(self.condition(context))
            except Exception as e:
                logger.warning(f"阶段 {self.name} 条件检查异常: {e}")
                return False
        return True

    def initialize(self, context: PipelineContext) -> None:
        """初始化阶段（在 execute 前调用）。

        子类可重写此方法进行资源准备。
        """
        self._initialized = True

    def cleanup(self, context: PipelineContext) -> None:
        """清理阶段资源（在 execute 后调用，无论成功失败）。

        子类可重写此方法进行资源释放。
        """
        pass

    def depends_on(self, stage_name: str) -> "PipelineStage":
        """声明依赖的前置阶段。

        Args:
            stage_name: 前置阶段名称。

        Returns:
            self（支持链式调用）。
        """
        if stage_name not in self._depends_on:
            self._depends_on.append(stage_name)
        return self

    def get_dependencies(self) -> list:
        """获取依赖列表。"""
        return list(self._depends_on)

    def __repr__(self) -> str:
        return f"<PipelineStage name={self.name!r} timeout={self.timeout} retries={self.max_retries}>"


class FunctionalStage(PipelineStage):
    """函数式阶段

    将普通函数包装为管道阶段，适用于简单逻辑无需定义类。
    """

    def __init__(
        self,
        name: str,
        func: Callable[[PipelineContext], Any],
        **kwargs,
    ):
        """初始化函数式阶段。

        Args:
            name: 阶段名称。
            func: 阶段执行函数，接收 PipelineContext，返回任意值（将包装为 StageResult）。
            **kwargs: 传递给 PipelineStage 的其他参数。
        """
        super().__init__(name=name, **kwargs)
        self._func = func

    def execute(self, context: PipelineContext) -> StageResult:
        """执行函数式阶段。"""
        start_time = time.time()
        try:
            result_data = self._func(context)
            duration_ms = (time.time() - start_time) * 1000
            # 如果函数已返回 StageResult，直接使用
            if isinstance(result_data, StageResult):
                result_data.duration_ms = duration_ms
                return result_data
            # 否则包装为 StageResult
            return StageResult(
                stage_name=self.name,
                status=StageStatus.SUCCESS,
                data=result_data,
                start_time=start_time,
                end_time=time.time(),
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return StageResult(
                stage_name=self.name,
                status=StageStatus.FAILED,
                error=str(e),
                error_type=type(e).__name__,
                traceback=traceback.format_exc(),
                start_time=start_time,
                end_time=time.time(),
                duration_ms=duration_ms,
            )


class AsyncFunctionalStage(PipelineStage):
    """异步函数式阶段

    将异步函数包装为管道阶段。
    """

    def __init__(
        self,
        name: str,
        func: Callable,
        **kwargs,
    ):
        """初始化异步函数式阶段。

        Args:
            name: 阶段名称。
            func: 异步执行函数，接收 PipelineContext，返回协程。
            **kwargs: 传递给 PipelineStage 的其他参数。
        """
        super().__init__(name=name, **kwargs)
        self._func = func

    async def execute_async(self, context: PipelineContext) -> StageResult:
        """异步执行函数式阶段。"""
        start_time = time.time()
        try:
            result_data = await self._func(context)
            duration_ms = (time.time() - start_time) * 1000
            if isinstance(result_data, StageResult):
                result_data.duration_ms = duration_ms
                return result_data
            return StageResult(
                stage_name=self.name,
                status=StageStatus.SUCCESS,
                data=result_data,
                start_time=start_time,
                end_time=time.time(),
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return StageResult(
                stage_name=self.name,
                status=StageStatus.FAILED,
                error=str(e),
                error_type=type(e).__name__,
                traceback=traceback.format_exc(),
                start_time=start_time,
                end_time=time.time(),
                duration_ms=duration_ms,
            )

    def execute(self, context: PipelineContext) -> StageResult:
        """同步执行（在事件循环中运行异步函数）。"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 已在事件循环中，创建新线程运行
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.execute_async(context))
                    return future.result()
            return asyncio.run(self.execute_async(context))
        except RuntimeError:
            return asyncio.run(self.execute_async(context))


# ===== 管道主类 =====


class Pipeline:
    """管道主类

    管理阶段列表与执行流程，支持阶段组合、顺序执行、错误处理、重试逻辑。

    使用示例：
        pipeline = Pipeline(name="proposal_generation")
        pipeline.add_stage(SearchStage())
        pipeline.add_stage(ReasonStage())
        context = PipelineContext(input_data={"query": "深度学习"})
        result = pipeline.execute(context)
    """

    def __init__(
        self,
        name: str = "pipeline",
        description: str = "",
        error_strategy: ErrorHandlingStrategy = ErrorHandlingStrategy.RAISE,
        max_retries: int = 0,
        retry_delay: float = 1.0,
        retry_backoff: float = 2.0,
        default_timeout: float = 0.0,
        enable_checkpoints: bool = False,
        tags: Optional[list] = None,
    ):
        """初始化管道。

        Args:
            name: 管道名称。
            description: 管道描述。
            error_strategy: 默认错误处理策略。
            max_retries: 默认最大重试次数。
            retry_delay: 默认重试延迟。
            retry_backoff: 默认重试退避倍数。
            default_timeout: 默认阶段超时时间。
            enable_checkpoints: 是否启用检查点。
            tags: 管道标签列表。
        """
        self.name = name
        self.description = description
        self.error_strategy = error_strategy
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.retry_backoff = retry_backoff
        self.default_timeout = default_timeout
        self.enable_checkpoints = enable_checkpoints
        self.tags = tags or []
        # 阶段列表（有序）
        self._stages: list[PipelineStage] = []
        # 阶段名称到索引的映射
        self._stage_index: dict[str, int] = {}
        # 管道状态
        self._status: PipelineStatus = PipelineStatus.IDLE
        # 执行锁（防止并发执行同一管道）
        self._execution_lock = threading.RLock()
        # 监控器
        self._monitor: Optional[PipelineMonitor] = None
        # 管道级元数据
        self.metadata: dict = {}

    def add_stage(self, stage: PipelineStage) -> "Pipeline":
        """添加阶段到管道末尾。

        Args:
            stage: 要添加的阶段。

        Returns:
            self（支持链式调用）。
        """
        with self._execution_lock:
            if stage.name in self._stage_index:
                raise ValueError(f"阶段名称 '{stage.name}' 已存在")
            self._stages.append(stage)
            self._stage_index[stage.name] = len(self._stages) - 1
            # 应用默认配置（若阶段未显式设置）
            if stage.max_retries == 0 and self.max_retries > 0:
                stage.max_retries = self.max_retries
            if stage.retry_delay == 1.0 and self.retry_delay != 1.0:
                stage.retry_delay = self.retry_delay
            if stage.timeout == 0.0 and self.default_timeout > 0:
                stage.timeout = self.default_timeout
            if stage.error_strategy == ErrorHandlingStrategy.RAISE and self.error_strategy != ErrorHandlingStrategy.RAISE:
                stage.error_strategy = self.error_strategy
        return self

    def insert_stage(self, index: int, stage: PipelineStage) -> "Pipeline":
        """在指定位置插入阶段。

        Args:
            index: 插入位置索引。
            stage: 要插入的阶段。

        Returns:
            self（支持链式调用）。
        """
        with self._execution_lock:
            if stage.name in self._stage_index:
                raise ValueError(f"阶段名称 '{stage.name}' 已存在")
            self._stages.insert(index, stage)
            # 重建索引映射
            self._rebuild_index()
        return self

    def insert_after(self, stage_name: str, new_stage: PipelineStage) -> "Pipeline":
        """在指定阶段之后插入新阶段。

        Args:
            stage_name: 目标阶段名称。
            new_stage: 要插入的新阶段。

        Returns:
            self（支持链式调用）。
        """
        with self._execution_lock:
            if stage_name not in self._stage_index:
                raise ValueError(f"阶段 '{stage_name}' 不存在")
            if new_stage.name in self._stage_index:
                raise ValueError(f"阶段名称 '{new_stage.name}' 已存在")
            idx = self._stage_index[stage_name]
            self._stages.insert(idx + 1, new_stage)
            self._rebuild_index()
        return self

    def insert_before(self, stage_name: str, new_stage: PipelineStage) -> "Pipeline":
        """在指定阶段之前插入新阶段。

        Args:
            stage_name: 目标阶段名称。
            new_stage: 要插入的新阶段。

        Returns:
            self（支持链式调用）。
        """
        with self._execution_lock:
            if stage_name not in self._stage_index:
                raise ValueError(f"阶段 '{stage_name}' 不存在")
            if new_stage.name in self._stage_index:
                raise ValueError(f"阶段名称 '{new_stage.name}' 已存在")
            idx = self._stage_index[stage_name]
            self._stages.insert(idx, new_stage)
            self._rebuild_index()
        return self

    def remove_stage(self, stage_name: str) -> bool:
        """移除指定阶段。

        Args:
            stage_name: 要移除的阶段名称。

        Returns:
            移除成功返回 True，阶段不存在返回 False。
        """
        with self._execution_lock:
            if stage_name not in self._stage_index:
                return False
            idx = self._stage_index[stage_name]
            self._stages.pop(idx)
            self._rebuild_index()
            return True

    def replace_stage(self, stage_name: str, new_stage: PipelineStage) -> bool:
        """替换指定阶段。

        Args:
            stage_name: 要替换的阶段名称。
            new_stage: 新阶段。

        Returns:
            替换成功返回 True，阶段不存在返回 False。
        """
        with self._execution_lock:
            if stage_name not in self._stage_index:
                return False
            idx = self._stage_index[stage_name]
            self._stages[idx] = new_stage
            self._rebuild_index()
            return True

    def get_stage(self, stage_name: str) -> Optional[PipelineStage]:
        """获取指定阶段。"""
        with self._execution_lock:
            idx = self._stage_index.get(stage_name)
            if idx is None:
                return None
            return self._stages[idx]

    def get_stages(self) -> list:
        """获取所有阶段列表。"""
        with self._execution_lock:
            return list(self._stages)

    def get_stage_names(self) -> list:
        """获取所有阶段名称列表。"""
        with self._execution_lock:
            return [s.name for s in self._stages]

    def stage_count(self) -> int:
        """获取阶段数量。"""
        with self._execution_lock:
            return len(self._stages)

    def clear_stages(self) -> None:
        """清空所有阶段。"""
        with self._execution_lock:
            self._stages.clear()
            self._stage_index.clear()

    def set_monitor(self, monitor: "PipelineMonitor") -> None:
        """设置监控器。"""
        self._monitor = monitor

    def _rebuild_index(self) -> None:
        """重建阶段索引映射。"""
        self._stage_index = {s.name: i for i, s in enumerate(self._stages)}

    def execute(self, context: PipelineContext) -> PipelineResult:
        """同步执行管道。

        按顺序执行所有阶段，根据错误处理策略处理异常。

        Args:
            context: 管道上下文。

        Returns:
            PipelineResult 实例。
        """
        with self._execution_lock:
            if self._status == PipelineStatus.RUNNING:
                return PipelineResult(
                    pipeline_name=self.name,
                    status=PipelineStatus.FAILED,
                    error="管道正在运行中，不可重复执行",
                )
            self._status = PipelineStatus.RUNNING

        start_time = time.time()
        result = PipelineResult(
            pipeline_name=self.name,
            status=PipelineStatus.RUNNING,
            start_time=start_time,
            total_stages=len(self._stages),
        )

        # 记录管道开始事件
        if self._monitor:
            self._monitor.on_pipeline_start(self, context)

        try:
            for stage in self._stages:
                # 检查取消
                if context.is_cancelled:
                    result.status = PipelineStatus.CANCELLED
                    result.error = "管道被取消"
                    break

                # 检查执行条件
                if not stage.should_run(context):
                    stage_result = StageResult(
                        stage_name=stage.name,
                        status=StageStatus.SKIPPED,
                    )
                    result.stage_results.append(stage_result)
                    result.skipped_stages += 1
                    if self._monitor:
                        self._monitor.on_stage_skip(stage, context)
                    continue

                # 执行阶段（带重试与超时）
                stage_result = self._execute_stage_with_retry(stage, context)
                result.stage_results.append(stage_result)
                result.executed_stages += 1

                if stage_result.success:
                    # 保存检查点
                    if self.enable_checkpoints:
                        context.save_checkpoint(stage.name)
                    if self._monitor:
                        self._monitor.on_stage_success(stage, stage_result, context)
                elif stage_result.failed:
                    result.failed_stages += 1
                    if self._monitor:
                        self._monitor.on_stage_failure(stage, stage_result, context)

                    # 根据错误处理策略决定后续行为
                    should_continue = self._handle_stage_failure(stage, stage_result, context, result)
                    if not should_continue:
                        break

            # 确定最终状态
            if result.status == PipelineStatus.RUNNING:
                if result.failed_stages > 0 and result.executed_stages > result.failed_stages:
                    result.status = PipelineStatus.PARTIAL
                elif result.failed_stages > 0:
                    result.status = PipelineStatus.FAILED
                else:
                    result.status = PipelineStatus.SUCCESS

        except Exception as e:
            result.status = PipelineStatus.FAILED
            result.error = str(e)
            logger.error(f"管道 {self.name} 执行异常: {e}", exc_info=True)
        finally:
            result.end_time = time.time()
            result.duration_ms = (result.end_time - start_time) * 1000
            # 汇总数据
            result.data = context.to_dict()
            self._status = PipelineStatus.IDLE
            if self._monitor:
                self._monitor.on_pipeline_end(self, result, context)

        return result

    async def execute_async(self, context: PipelineContext) -> PipelineResult:
        """异步执行管道。

        Args:
            context: 管道上下文。

        Returns:
            PipelineResult 实例。
        """
        with self._execution_lock:
            if self._status == PipelineStatus.RUNNING:
                return PipelineResult(
                    pipeline_name=self.name,
                    status=PipelineStatus.FAILED,
                    error="管道正在运行中，不可重复执行",
                )
            self._status = PipelineStatus.RUNNING

        start_time = time.time()
        result = PipelineResult(
            pipeline_name=self.name,
            status=PipelineStatus.RUNNING,
            start_time=start_time,
            total_stages=len(self._stages),
        )

        if self._monitor:
            self._monitor.on_pipeline_start(self, context)

        try:
            for stage in self._stages:
                if context.is_cancelled:
                    result.status = PipelineStatus.CANCELLED
                    result.error = "管道被取消"
                    break

                if not stage.should_run(context):
                    stage_result = StageResult(
                        stage_name=stage.name,
                        status=StageStatus.SKIPPED,
                    )
                    result.stage_results.append(stage_result)
                    result.skipped_stages += 1
                    continue

                # 异步执行阶段
                stage_result = await self._execute_stage_async_with_retry(stage, context)
                result.stage_results.append(stage_result)
                result.executed_stages += 1

                if stage_result.success:
                    if self.enable_checkpoints:
                        context.save_checkpoint(stage.name)
                elif stage_result.failed:
                    result.failed_stages += 1
                    should_continue = self._handle_stage_failure(stage, stage_result, context, result)
                    if not should_continue:
                        break

            if result.status == PipelineStatus.RUNNING:
                if result.failed_stages > 0 and result.executed_stages > result.failed_stages:
                    result.status = PipelineStatus.PARTIAL
                elif result.failed_stages > 0:
                    result.status = PipelineStatus.FAILED
                else:
                    result.status = PipelineStatus.SUCCESS

        except Exception as e:
            result.status = PipelineStatus.FAILED
            result.error = str(e)
            logger.error(f"管道 {self.name} 异步执行异常: {e}", exc_info=True)
        finally:
            result.end_time = time.time()
            result.duration_ms = (result.end_time - start_time) * 1000
            result.data = context.to_dict()
            self._status = PipelineStatus.IDLE
            if self._monitor:
                self._monitor.on_pipeline_end(self, result, context)

        return result

    def _execute_stage_with_retry(
        self, stage: PipelineStage, context: PipelineContext
    ) -> StageResult:
        """执行阶段（带重试与超时）。"""
        max_attempts = stage.max_retries + 1
        current_delay = stage.retry_delay
        last_result = None

        for attempt in range(max_attempts):
            if context.is_cancelled:
                return StageResult(
                    stage_name=stage.name,
                    status=StageStatus.CANCELLED,
                )

            # 初始化阶段
            if attempt == 0:
                try:
                    stage.initialize(context)
                except Exception as e:
                    return StageResult(
                        stage_name=stage.name,
                        status=StageStatus.FAILED,
                        error=f"初始化失败: {e}",
                        error_type=type(e).__name__,
                    )

            start_time = time.time()
            context.current_stage = stage.name

            try:
                # 带超时执行
                if stage.timeout > 0:
                    result = self._execute_with_timeout(stage, context, stage.timeout)
                else:
                    result = stage.execute(context)

                if result is None:
                    result = StageResult(
                        stage_name=stage.name,
                        status=StageStatus.SUCCESS,
                    )

                # 确保阶段名正确
                if not result.stage_name:
                    result.stage_name = stage.name

                result.start_time = start_time
                result.end_time = time.time()
                result.duration_ms = (result.end_time - start_time) * 1000
                result.retry_count = attempt

                if result.success:
                    # 记录执行日志
                    context.log_execution(
                        stage.name, "success", result.duration_ms,
                        {"attempt": attempt + 1}
                    )
                    return result

                # 失败，判断是否重试
                if attempt < max_attempts - 1 and stage.error_strategy == ErrorHandlingStrategy.RETRY:
                    logger.info(
                        f"阶段 {stage.name} 第 {attempt + 1} 次执行失败，"
                        f"{current_delay:.1f}s 后重试: {result.error}"
                    )
                    time.sleep(current_delay)
                    current_delay *= stage.retry_backoff
                    last_result = result
                    continue

                # 不再重试或策略非 RETRY
                return result

            except asyncio.TimeoutError:
                duration_ms = (time.time() - start_time) * 1000
                result = StageResult(
                    stage_name=stage.name,
                    status=StageStatus.TIMEOUT,
                    error=f"阶段超时（{stage.timeout}s）",
                    error_type="TimeoutError",
                    duration_ms=duration_ms,
                    retry_count=attempt,
                )
                if attempt < max_attempts - 1 and stage.error_strategy == ErrorHandlingStrategy.RETRY:
                    time.sleep(current_delay)
                    current_delay *= stage.retry_backoff
                    last_result = result
                    continue
                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                result = StageResult(
                    stage_name=stage.name,
                    status=StageStatus.FAILED,
                    error=str(e),
                    error_type=type(e).__name__,
                    traceback=traceback.format_exc(),
                    duration_ms=duration_ms,
                    retry_count=attempt,
                )
                if attempt < max_attempts - 1 and stage.error_strategy == ErrorHandlingStrategy.RETRY:
                    logger.info(
                        f"阶段 {stage.name} 第 {attempt + 1} 次执行异常，"
                        f"{current_delay:.1f}s 后重试: {e}"
                    )
                    time.sleep(current_delay)
                    current_delay *= stage.retry_backoff
                    last_result = result
                    continue
                return result

            finally:
                try:
                    stage.cleanup(context)
                except Exception as e:
                    logger.warning(f"阶段 {stage.name} 清理异常: {e}")

        return last_result or StageResult(
            stage_name=stage.name,
            status=StageStatus.FAILED,
            error="未知错误",
        )

    async def _execute_stage_async_with_retry(
        self, stage: PipelineStage, context: PipelineContext
    ) -> StageResult:
        """异步执行阶段（带重试与超时）。"""
        max_attempts = stage.max_retries + 1
        current_delay = stage.retry_delay
        last_result = None

        for attempt in range(max_attempts):
            if context.is_cancelled:
                return StageResult(stage_name=stage.name, status=StageStatus.CANCELLED)

            if attempt == 0:
                try:
                    stage.initialize(context)
                except Exception as e:
                    return StageResult(
                        stage_name=stage.name,
                        status=StageStatus.FAILED,
                        error=f"初始化失败: {e}",
                    )

            start_time = time.time()
            context.current_stage = stage.name

            try:
                if stage.timeout > 0:
                    result = await asyncio.wait_for(
                        stage.execute_async(context), timeout=stage.timeout
                    )
                else:
                    result = await stage.execute_async(context)

                if result is None:
                    result = StageResult(stage_name=stage.name, status=StageStatus.SUCCESS)

                if not result.stage_name:
                    result.stage_name = stage.name

                result.start_time = start_time
                result.end_time = time.time()
                result.duration_ms = (result.end_time - start_time) * 1000
                result.retry_count = attempt

                if result.success:
                    return result

                if attempt < max_attempts - 1 and stage.error_strategy == ErrorHandlingStrategy.RETRY:
                    await asyncio.sleep(current_delay)
                    current_delay *= stage.retry_backoff
                    last_result = result
                    continue

                return result

            except asyncio.TimeoutError:
                result = StageResult(
                    stage_name=stage.name,
                    status=StageStatus.TIMEOUT,
                    error=f"阶段超时（{stage.timeout}s）",
                    retry_count=attempt,
                )
                if attempt < max_attempts - 1 and stage.error_strategy == ErrorHandlingStrategy.RETRY:
                    await asyncio.sleep(current_delay)
                    current_delay *= stage.retry_backoff
                    last_result = result
                    continue
                return result

            except Exception as e:
                result = StageResult(
                    stage_name=stage.name,
                    status=StageStatus.FAILED,
                    error=str(e),
                    error_type=type(e).__name__,
                    traceback=traceback.format_exc(),
                    retry_count=attempt,
                )
                if attempt < max_attempts - 1 and stage.error_strategy == ErrorHandlingStrategy.RETRY:
                    await asyncio.sleep(current_delay)
                    current_delay *= stage.retry_backoff
                    last_result = result
                    continue
                return result

        return last_result or StageResult(
            stage_name=stage.name, status=StageStatus.FAILED, error="未知错误"
        )

    def _execute_with_timeout(
        self, stage: PipelineStage, context: PipelineContext, timeout: float
    ) -> StageResult:
        """带超时执行同步阶段。"""
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(stage.execute, context)
            try:
                return future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                raise asyncio.TimeoutError()

    def _handle_stage_failure(
        self,
        stage: PipelineStage,
        stage_result: StageResult,
        context: PipelineContext,
        pipeline_result: PipelineResult,
    ) -> bool:
        """处理阶段失败，决定是否继续执行。

        Args:
            stage: 失败的阶段。
            stage_result: 阶段执行结果。
            context: 管道上下文。
            pipeline_result: 管道执行结果。

        Returns:
            True 表示继续执行后续阶段，False 表示终止管道。
        """
        strategy = stage.error_strategy

        if strategy == ErrorHandlingStrategy.RAISE:
            # 抛出异常，终止管道
            pipeline_result.status = PipelineStatus.FAILED
            pipeline_result.error = f"阶段 {stage.name} 失败: {stage_result.error}"
            return False

        elif strategy == ErrorHandlingStrategy.SKIP:
            # 跳过失败阶段，继续执行
            logger.warning(f"阶段 {stage.name} 失败，跳过继续执行: {stage_result.error}")
            return True

        elif strategy == ErrorHandlingStrategy.FALLBACK:
            # 使用降级阶段
            if stage.fallback_stage is not None:
                logger.info(f"阶段 {stage.name} 失败，执行降级阶段 {stage.fallback_stage.name}")
                fallback_result = self._execute_stage_with_retry(stage.fallback_stage, context)
                pipeline_result.stage_results.append(fallback_result)
                if fallback_result.success:
                    return True
                else:
                    pipeline_result.status = PipelineStatus.FAILED
                    pipeline_result.error = f"降级阶段 {stage.fallback_stage.name} 也失败: {fallback_result.error}"
                    return False
            logger.warning(f"阶段 {stage.name} 失败且无降级阶段，跳过继续执行")
            return True

        elif strategy == ErrorHandlingStrategy.ROLLBACK:
            # 回滚到检查点
            checkpoints = context.list_checkpoints()
            if checkpoints:
                last_checkpoint = checkpoints[-1]
                logger.info(f"阶段 {stage.name} 失败，回滚到检查点 {last_checkpoint}")
                context.restore_checkpoint(last_checkpoint)
                return True
            logger.warning(f"阶段 {stage.name} 失败且无检查点，终止管道")
            pipeline_result.status = PipelineStatus.FAILED
            pipeline_result.error = f"阶段 {stage.name} 失败且无检查点可回滚"
            return False

        elif strategy == ErrorHandlingStrategy.RETRY:
            # 重试已在 _execute_stage_with_retry 中处理，到这里说明重试已耗尽
            logger.warning(f"阶段 {stage.name} 重试耗尽仍失败，终止管道")
            pipeline_result.status = PipelineStatus.FAILED
            pipeline_result.error = f"阶段 {stage.name} 重试 {stage.max_retries} 次仍失败: {stage_result.error}"
            return False

        # 默认终止
        return False

    @property
    def status(self) -> PipelineStatus:
        """获取管道状态。"""
        return self._status

    def to_dict(self) -> dict:
        """转换为字典表示。"""
        return {
            "name": self.name,
            "description": self.description,
            "status": self._status.value,
            "stage_count": len(self._stages),
            "stages": [s.name for s in self._stages],
            "tags": self.tags,
            "metadata": self.metadata,
        }


# ===== 管道监控器 =====


class PipelineMonitor:
    """管道监控器

    记录管道执行过程中的事件与指标，用于调试、性能分析与监控。

    使用示例：
        monitor = PipelineMonitor()
        pipeline = Pipeline(name="test")
        pipeline.set_monitor(monitor)
        pipeline.execute(context)
        stats = monitor.get_stats()
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._events: list = []
        self._stage_stats: dict = defaultdict(lambda: {
            "total": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "total_duration_ms": 0.0,
            "max_duration_ms": 0.0,
            "min_duration_ms": float("inf"),
        })
        self._pipeline_stats: dict = defaultdict(lambda: {
            "total": 0,
            "success": 0,
            "failed": 0,
            "total_duration_ms": 0.0,
        })

    def on_pipeline_start(self, pipeline: Pipeline, context: PipelineContext) -> None:
        """管道开始事件。"""
        with self._lock:
            self._events.append({
                "type": "pipeline_start",
                "pipeline": pipeline.name,
                "timestamp": time.time(),
                "stage_count": pipeline.stage_count(),
            })

    def on_pipeline_end(self, pipeline: Pipeline, result: PipelineResult, context: PipelineContext) -> None:
        """管道结束事件。"""
        with self._lock:
            self._events.append({
                "type": "pipeline_end",
                "pipeline": pipeline.name,
                "timestamp": time.time(),
                "status": result.status.value,
                "duration_ms": result.duration_ms,
            })
            stats = self._pipeline_stats[pipeline.name]
            stats["total"] += 1
            stats["total_duration_ms"] += result.duration_ms
            if result.success:
                stats["success"] += 1
            elif result.failed:
                stats["failed"] += 1

    def on_stage_success(self, stage: PipelineStage, result: StageResult, context: PipelineContext) -> None:
        """阶段成功事件。"""
        with self._lock:
            self._events.append({
                "type": "stage_success",
                "stage": stage.name,
                "timestamp": time.time(),
                "duration_ms": result.duration_ms,
            })
            stats = self._stage_stats[stage.name]
            stats["total"] += 1
            stats["success"] += 1
            stats["total_duration_ms"] += result.duration_ms
            stats["max_duration_ms"] = max(stats["max_duration_ms"], result.duration_ms)
            stats["min_duration_ms"] = min(stats["min_duration_ms"], result.duration_ms)

    def on_stage_failure(self, stage: PipelineStage, result: StageResult, context: PipelineContext) -> None:
        """阶段失败事件。"""
        with self._lock:
            self._events.append({
                "type": "stage_failure",
                "stage": stage.name,
                "timestamp": time.time(),
                "error": result.error,
                "duration_ms": result.duration_ms,
            })
            stats = self._stage_stats[stage.name]
            stats["total"] += 1
            stats["failed"] += 1
            stats["total_duration_ms"] += result.duration_ms

    def on_stage_skip(self, stage: PipelineStage, context: PipelineContext) -> None:
        """阶段跳过事件。"""
        with self._lock:
            self._events.append({
                "type": "stage_skip",
                "stage": stage.name,
                "timestamp": time.time(),
            })
            stats = self._stage_stats[stage.name]
            stats["total"] += 1
            stats["skipped"] += 1

    def get_events(self, event_type: Optional[str] = None) -> list:
        """获取事件列表。"""
        with self._lock:
            if event_type:
                return [e for e in self._events if e["type"] == event_type]
            return list(self._events)

    def get_stage_stats(self, stage_name: Optional[str] = None) -> dict:
        """获取阶段统计。"""
        with self._lock:
            if stage_name:
                stats = self._stage_stats.get(stage_name, {})
                if stats:
                    result = dict(stats)
                    if result["total"] > 0:
                        result["avg_duration_ms"] = result["total_duration_ms"] / result["total"]
                        result["success_rate"] = result["success"] / result["total"]
                    else:
                        result["avg_duration_ms"] = 0
                        result["success_rate"] = 0
                    if result["min_duration_ms"] == float("inf"):
                        result["min_duration_ms"] = 0
                    return result
                return {}
            result = {}
            for name, stats in self._stage_stats.items():
                item = dict(stats)
                if item["total"] > 0:
                    item["avg_duration_ms"] = item["total_duration_ms"] / item["total"]
                    item["success_rate"] = item["success"] / item["total"]
                else:
                    item["avg_duration_ms"] = 0
                    item["success_rate"] = 0
                if item["min_duration_ms"] == float("inf"):
                    item["min_duration_ms"] = 0
                result[name] = item
            return result

    def get_pipeline_stats(self, pipeline_name: Optional[str] = None) -> dict:
        """获取管道统计。"""
        with self._lock:
            if pipeline_name:
                stats = self._pipeline_stats.get(pipeline_name, {})
                if stats:
                    result = dict(stats)
                    if result["total"] > 0:
                        result["avg_duration_ms"] = result["total_duration_ms"] / result["total"]
                        result["success_rate"] = result["success"] / result["total"]
                    else:
                        result["avg_duration_ms"] = 0
                        result["success_rate"] = 0
                    return result
                return {}
            result = {}
            for name, stats in self._pipeline_stats.items():
                item = dict(stats)
                if item["total"] > 0:
                    item["avg_duration_ms"] = item["total_duration_ms"] / item["total"]
                    item["success_rate"] = item["success"] / item["total"]
                else:
                    item["avg_duration_ms"] = 0
                    item["success_rate"] = 0
                result[name] = item
            return result

    def get_stats(self) -> dict:
        """获取汇总统计。"""
        return {
            "pipelines": self.get_pipeline_stats(),
            "stages": self.get_stage_stats(),
            "total_events": len(self._events),
        }

    def clear(self) -> None:
        """清空所有事件与统计。"""
        with self._lock:
            self._events.clear()
            self._stage_stats.clear()
            self._pipeline_stats.clear()


# ===== 管道执行器 =====


class PipelineExecutor:
    """管道执行器

    封装管道的执行逻辑，支持同步与异步执行、批量执行、并发执行。
    """

    def __init__(
        self,
        max_workers: int = 4,
        default_timeout: float = 300.0,
        monitor: Optional[PipelineMonitor] = None,
    ):
        """初始化管道执行器。

        Args:
            max_workers: 最大并发工作线程数。
            default_timeout: 默认执行超时时间。
            monitor: 监控器实例。
        """
        self.max_workers = max_workers
        self.default_timeout = default_timeout
        self.monitor = monitor or PipelineMonitor()
        self._lock = threading.Lock()

    def execute(self, pipeline: Pipeline, context: PipelineContext) -> PipelineResult:
        """同步执行单个管道。"""
        pipeline.set_monitor(self.monitor)
        return pipeline.execute(context)

    async def execute_async(self, pipeline: Pipeline, context: PipelineContext) -> PipelineResult:
        """异步执行单个管道。"""
        pipeline.set_monitor(self.monitor)
        return await pipeline.execute_async(context)

    def execute_batch(
        self,
        pipelines: list,
        contexts: list,
        parallel: bool = False,
    ) -> list:
        """批量执行多个管道。

        Args:
            pipelines: 管道列表。
            contexts: 上下文列表（与管道列表一一对应）。
            parallel: 是否并行执行。

        Returns:
            PipelineResult 列表。
        """
        if len(pipelines) != len(contexts):
            raise ValueError("管道列表与上下文列表长度不一致")

        if parallel:
            return self._execute_parallel(pipelines, contexts)
        return self._execute_sequential(pipelines, contexts)

    def _execute_sequential(self, pipelines: list, contexts: list) -> list:
        """顺序执行。"""
        results = []
        for pipeline, context in zip(pipelines, contexts):
            result = self.execute(pipeline, context)
            results.append(result)
        return results

    def _execute_parallel(self, pipelines: list, contexts: list) -> list:
        """并行执行。"""
        import concurrent.futures
        results = [None] * len(pipelines)
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_idx = {
                executor.submit(self.execute, pipeline, context): idx
                for idx, (pipeline, context) in enumerate(zip(pipelines, contexts))
            }
            for future in concurrent.futures.as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result(timeout=self.default_timeout)
                except Exception as e:
                    results[idx] = PipelineResult(
                        pipeline_name=pipelines[idx].name,
                        status=PipelineStatus.FAILED,
                        error=str(e),
                    )
        return results

    async def execute_batch_async(
        self,
        pipelines: list,
        contexts: list,
    ) -> list:
        """异步批量执行。"""
        if len(pipelines) != len(contexts):
            raise ValueError("管道列表与上下文列表长度不一致")
        tasks = [
            self.execute_async(pipeline, context)
            for pipeline, context in zip(pipelines, contexts)
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)


# ===== 管道模板注册表 =====


class PipelineTemplateRegistry:
    """管道模板注册表

    管理 20+ 预定义管道模板，每个模板封装了特定业务场景的阶段组合。
    支持按名称获取模板、按分类过滤、动态注册自定义模板。

    使用示例：
        registry = PipelineTemplateRegistry()
        pipeline = registry.create_pipeline("proposal_generation")
        context = PipelineContext(input_data={"query": "深度学习"})
        result = pipeline.execute(context)
    """

    def __init__(self):
        self._templates: dict[str, dict] = {}
        self._register_default_templates()

    def _register_default_templates(self) -> None:
        """注册默认管道模板（20+ 模板）。"""
        # ===== 生成类模板 =====
        self.register_template(
            name="proposal_generation",
            category=TemplateCategory.GENERATION,
            description="论题生成管道：信息确权→创意→校验→生成→深度辅助",
            stage_names=["info_confirm", "creativity", "validation", "generation", "deep_assist"],
        )
        self.register_template(
            name="literature_review",
            category=TemplateCategory.GENERATION,
            description="文献综述生成管道：检索→筛选→分类→综述撰写",
            stage_names=["search", "filter", "classify", "summarize", "review_write"],
        )
        self.register_template(
            name="feasibility_check",
            category=TemplateCategory.VALIDATION,
            description="可行性检查管道：时间可行性→资源可行性→技术可行性→综合评估",
            stage_names=["time_check", "resource_check", "tech_check", "overall_assessment"],
        )
        self.register_template(
            name="originality_check",
            category=TemplateCategory.VALIDATION,
            description="原创性检查管道：查重→新颖性评估→相似度分析→报告生成",
            stage_names=["plagiarism_scan", "novelty_score", "similarity_analysis", "report"],
        )
        self.register_template(
            name="format_check",
            category=TemplateCategory.VALIDATION,
            description="格式检查管道：标题格式→摘要格式→引用格式→整体规范",
            stage_names=["title_check", "abstract_check", "citation_check", "overall_format"],
        )

        # ===== 深度辅助类模板 =====
        self.register_template(
            name="deep_assist_full",
            category=TemplateCategory.ASSIST,
            description="深度辅助全套：文献精读→实验预研→答辩模拟",
            stage_names=["literature_reading", "experiment_prep", "defense_sim"],
        )
        self.register_template(
            name="deep_assist_literature",
            category=TemplateCategory.ASSIST,
            description="文献精读辅助：全文解析→关键观点提取→对比分析→笔记生成",
            stage_names=["parse_paper", "extract_keypoints", "compare_analysis", "note_generation"],
        )
        self.register_template(
            name="deep_assist_experiment",
            category=TemplateCategory.ASSIST,
            description="实验预研辅助：实验设计→参数估算→风险评估→方案优化",
            stage_names=["design_experiment", "estimate_params", "risk_assessment", "optimize_plan"],
        )
        self.register_template(
            name="deep_assist_defense",
            category=TemplateCategory.ASSIST,
            description="答辩模拟辅助：问题预测→回答演练→薄弱点分析→改进建议",
            stage_names=["predict_questions", "practice_answers", "weakness_analysis", "improve_suggestions"],
        )

        # ===== 多粒度生成类模板 =====
        self.register_template(
            name="multi_granularity_generation",
            category=TemplateCategory.GENERATION,
            description="多粒度生成管道：标题级→摘要级→大纲级→全文级",
            stage_names=["topic_level", "abstract_level", "outline_level", "full_text_level"],
        )
        self.register_template(
            name="style_normalization",
            category=TemplateCategory.GENERATION,
            description="风格规范化管道：模板词替换→句式调整→对仗去除→最终润色",
            stage_names=["replace_template_words", "adjust_sentence", "remove_parallelism", "final_polish"],
        )
        self.register_template(
            name="citation_formatting",
            category=TemplateCategory.GENERATION,
            description="引用格式化管道：引用解析→格式转换→一致性校验→输出",
            stage_names=["parse_citations", "convert_format", "consistency_check", "output"],
        )

        # ===== 分析类模板 =====
        self.register_template(
            name="plagiarism_scan",
            category=TemplateCategory.ANALYSIS,
            description="查重扫描管道：文本预处理→相似度计算→匹配定位→报告生成",
            stage_names=["preprocess", "similarity_calc", "match_locate", "report"],
        )
        self.register_template(
            name="academic_review",
            category=TemplateCategory.ANALYSIS,
            description="学术评审管道：结构检查→逻辑分析→创新性评估→改进建议",
            stage_names=["structure_check", "logic_analysis", "innovation_eval", "suggestions"],
        )

        # ===== 批处理类模板 =====
        self.register_template(
            name="batch_generation",
            category=TemplateCategory.BATCH,
            description="批量生成管道：参数校验→并行生成→结果聚合→质量筛选",
            stage_names=["validate_params", "parallel_generate", "aggregate", "quality_filter"],
        )
        self.register_template(
            name="iterative_refinement",
            category=TemplateCategory.BATCH,
            description="迭代优化管道：初版生成→自评→修改→再评→定稿",
            stage_names=["initial_draft", "self_eval", "revise", "re_eval", "finalize"],
        )

        # ===== 高级类模板 =====
        self.register_template(
            name="ab_test_pipeline",
            category=TemplateCategory.ADVANCED,
            description="A/B 测试管道：方案A生成→方案B生成→对比评估→择优",
            stage_names=["generate_a", "generate_b", "compare", "select_best"],
        )
        self.register_template(
            name="fallback_pipeline",
            category=TemplateCategory.ADVANCED,
            description="降级管道：主方案→失败检测→降级方案→结果合并",
            stage_names=["primary", "failure_detect", "fallback", "merge"],
        )
        self.register_template(
            name="parallel_pipeline",
            category=TemplateCategory.ADVANCED,
            description="并行管道：任务分解→并行执行→结果合并→输出",
            stage_names=["decompose", "parallel_exec", "merge_results", "output"],
        )
        self.register_template(
            name="conditional_pipeline",
            category=TemplateCategory.ADVANCED,
            description="条件管道：条件评估→分支选择→分支执行→结果输出",
            stage_names=["eval_condition", "select_branch", "exec_branch", "output"],
        )

    def register_template(
        self,
        name: str,
        category: TemplateCategory,
        description: str,
        stage_names: list,
        stage_builders: Optional[dict] = None,
        config: Optional[dict] = None,
    ) -> None:
        """注册管道模板。

        Args:
            name: 模板名称。
            category: 模板分类。
            description: 模板描述。
            stage_names: 阶段名称列表。
            stage_builders: 阶段构建器字典（阶段名 -> 构建函数）。
            config: 模板配置。
        """
        self._templates[name] = {
            "name": name,
            "category": category,
            "description": description,
            "stage_names": stage_names,
            "stage_builders": stage_builders or {},
            "config": config or {},
        }

    def get_template(self, name: str) -> Optional[dict]:
        """获取模板信息。"""
        return self._templates.get(name)

    def list_templates(self, category: Optional[TemplateCategory] = None) -> list:
        """列出所有模板。"""
        if category:
            return [
                t for t in self._templates.values()
                if t["category"] == category
            ]
        return list(self._templates.values())

    def list_template_names(self, category: Optional[TemplateCategory] = None) -> list:
        """列出所有模板名称。"""
        templates = self.list_templates(category)
        return [t["name"] for t in templates]

    def create_pipeline(
        self,
        template_name: str,
        pipeline_name: str = "",
        custom_stages: Optional[dict] = None,
    ) -> Pipeline:
        """根据模板创建管道。

        Args:
            template_name: 模板名称。
            pipeline_name: 管道名称（默认使用模板名）。
            custom_stages: 自定义阶段字典（阶段名 -> PipelineStage 实例）。

        Returns:
            Pipeline 实例。
        """
        template = self._templates.get(template_name)
        if template is None:
            raise ValueError(f"未知管道模板: {template_name}")

        pipeline = Pipeline(
            name=pipeline_name or template_name,
            description=template["description"],
            tags=[template["category"].value],
        )

        custom_stages = custom_stages or {}
        stage_builders = template["stage_builders"]

        for stage_name in template["stage_names"]:
            # 优先使用自定义阶段
            if stage_name in custom_stages:
                pipeline.add_stage(custom_stages[stage_name])
            # 其次使用模板提供的构建器
            elif stage_name in stage_builders:
                builder = stage_builders[stage_name]
                stage = builder()
                pipeline.add_stage(stage)
            else:
                # 创建占位阶段（函数式阶段，直接返回输入数据）
                placeholder = FunctionalStage(
                    name=stage_name,
                    func=lambda ctx: ctx.get(stage_name, None),
                    description=f"占位阶段: {stage_name}",
                )
                pipeline.add_stage(placeholder)

        return pipeline

    def has_template(self, name: str) -> bool:
        """判断模板是否存在。"""
        return name in self._templates

    def remove_template(self, name: str) -> bool:
        """移除模板。"""
        if name in self._templates:
            del self._templates[name]
            return True
        return False


# ===== 全局实例 =====


# 全局模板注册表
_global_registry = PipelineTemplateRegistry()


def get_template_registry() -> PipelineTemplateRegistry:
    """获取全局管道模板注册表。"""
    return _global_registry


def create_pipeline_from_template(
    template_name: str,
    pipeline_name: str = "",
    custom_stages: Optional[dict] = None,
) -> Pipeline:
    """从模板创建管道的便捷函数。"""
    return _global_registry.create_pipeline(
        template_name=template_name,
        pipeline_name=pipeline_name,
        custom_stages=custom_stages,
    )


def list_pipeline_templates(category: Optional[TemplateCategory] = None) -> list:
    """列出所有管道模板。"""
    return _global_registry.list_templates(category)


# ===== 预定义阶段工厂函数 =====


def create_search_stage(
    name: str = "search",
    timeout: float = 30.0,
    max_retries: int = 2,
) -> PipelineStage:
    """创建检索阶段。"""
    def _search(context: PipelineContext) -> StageResult:
        query = context.user_input or context.input_data.get("query", "")
        # 模拟检索结果
        results = {
            "query": query,
            "papers": [],
            "total": 0,
        }
        context.set("search_results", results)
        return StageResult(
            stage_name=name,
            status=StageStatus.SUCCESS,
            data=results,
        )

    return FunctionalStage(
        name=name,
        func=_search,
        timeout=timeout,
        max_retries=max_retries,
        error_strategy=ErrorHandlingStrategy.RETRY,
    )


def create_reason_stage(
    name: str = "creativity",
    timeout: float = 60.0,
    max_retries: int = 1,
) -> PipelineStage:
    """创建创意阶段。"""
    def _reason(context: PipelineContext) -> StageResult:
        search_results = context.get("search_results", {})
        candidates = [
            {"title": "候选论题1", "score": 0},
            {"title": "候选论题2", "score": 0},
        ]
        context.set("candidates", candidates)
        return StageResult(
            stage_name=name,
            status=StageStatus.SUCCESS,
            data={"candidates": candidates},
        )

    return FunctionalStage(
        name=name,
        func=_reason,
        timeout=timeout,
        max_retries=max_retries,
    )


def create_critic_stage(
    name: str = "validation",
    timeout: float = 45.0,
    max_retries: int = 1,
) -> PipelineStage:
    """创建校验阶段。"""
    def _critic(context: PipelineContext) -> StageResult:
        candidates = context.get("candidates", [])
        evaluations = [
            {"title": c.get("title", ""), "score": 75, "issues": [], "suggestions": []}
            for c in candidates
        ]
        context.set("evaluations", evaluations)
        return StageResult(
            stage_name=name,
            status=StageStatus.SUCCESS,
            data={"evaluations": evaluations},
        )

    return FunctionalStage(
        name=name,
        func=_critic,
        timeout=timeout,
        max_retries=max_retries,
    )


def create_writer_stage(
    name: str = "generation",
    timeout: float = 120.0,
    max_retries: int = 1,
) -> PipelineStage:
    """创建生成阶段。"""
    def _write(context: PipelineContext) -> StageResult:
        evaluations = context.get("evaluations", [])
        best = evaluations[0] if evaluations else {}
        content = f"基于 {best.get('title', '未知论题')} 的开题报告内容"
        context.set("generated_content", content)
        return StageResult(
            stage_name=name,
            status=StageStatus.SUCCESS,
            data={"content": content},
        )

    return FunctionalStage(
        name=name,
        func=_write,
        timeout=timeout,
        max_retries=max_retries,
    )


def create_deep_assist_stage(
    name: str = "deep_assist",
    timeout: float = 60.0,
) -> PipelineStage:
    """创建深度辅助阶段。"""
    def _assist(context: PipelineContext) -> StageResult:
        options = ["literature_reading", "experiment_prep", "defense_sim"]
        context.set("deep_assist_options", options)
        return StageResult(
            stage_name=name,
            status=StageStatus.SUCCESS,
            data={"options": options},
        )

    return FunctionalStage(
        name=name,
        func=_assist,
        timeout=timeout,
    )


# ===== 便捷构建函数 =====


def build_proposal_generation_pipeline(
    custom_stages: Optional[dict] = None,
) -> Pipeline:
    """构建论题生成管道。

    五阶段：信息确权→创意→校验→生成→深度辅助

    Args:
        custom_stages: 自定义阶段字典。

    Returns:
        Pipeline 实例。
    """
    default_stages = {
        "info_confirm": create_search_stage(name="info_confirm"),
        "creativity": create_reason_stage(name="creativity"),
        "validation": create_critic_stage(name="validation"),
        "generation": create_writer_stage(name="generation"),
        "deep_assist": create_deep_assist_stage(name="deep_assist"),
    }
    if custom_stages:
        default_stages.update(custom_stages)
    return create_pipeline_from_template(
        template_name="proposal_generation",
        custom_stages=default_stages,
    )


def build_literature_review_pipeline(
    custom_stages: Optional[dict] = None,
) -> Pipeline:
    """构建文献综述管道。"""
    return create_pipeline_from_template(
        template_name="literature_review",
        custom_stages=custom_stages,
    )


def build_feasibility_check_pipeline(
    custom_stages: Optional[dict] = None,
) -> Pipeline:
    """构建可行性检查管道。"""
    return create_pipeline_from_template(
        template_name="feasibility_check",
        custom_stages=custom_stages,
    )


def build_originality_check_pipeline(
    custom_stages: Optional[dict] = None,
) -> Pipeline:
    """构建原创性检查管道。"""
    return create_pipeline_from_template(
        template_name="originality_check",
        custom_stages=custom_stages,
    )


def build_format_check_pipeline(
    custom_stages: Optional[dict] = None,
) -> Pipeline:
    """构建格式检查管道。"""
    return create_pipeline_from_template(
        template_name="format_check",
        custom_stages=custom_stages,
    )


def build_deep_assist_full_pipeline(
    custom_stages: Optional[dict] = None,
) -> Pipeline:
    """构建深度辅助全套管道。"""
    return create_pipeline_from_template(
        template_name="deep_assist_full",
        custom_stages=custom_stages,
    )


def build_multi_granularity_pipeline(
    custom_stages: Optional[dict] = None,
) -> Pipeline:
    """构建多粒度生成管道。"""
    return create_pipeline_from_template(
        template_name="multi_granularity_generation",
        custom_stages=custom_stages,
    )


def build_plagiarism_scan_pipeline(
    custom_stages: Optional[dict] = None,
) -> Pipeline:
    """构建查重扫描管道。"""
    return create_pipeline_from_template(
        template_name="plagiarism_scan",
        custom_stages=custom_stages,
    )


def build_batch_generation_pipeline(
    custom_stages: Optional[dict] = None,
) -> Pipeline:
    """构建批量生成管道。"""
    return create_pipeline_from_template(
        template_name="batch_generation",
        custom_stages=custom_stages,
    )


def build_iterative_refinement_pipeline(
    custom_stages: Optional[dict] = None,
) -> Pipeline:
    """构建迭代优化管道。"""
    return create_pipeline_from_template(
        template_name="iterative_refinement",
        custom_stages=custom_stages,
    )


def build_ab_test_pipeline(
    custom_stages: Optional[dict] = None,
) -> Pipeline:
    """构建 A/B 测试管道。"""
    return create_pipeline_from_template(
        template_name="ab_test_pipeline",
        custom_stages=custom_stages,
    )


def build_fallback_pipeline(
    custom_stages: Optional[dict] = None,
) -> Pipeline:
    """构建降级管道。"""
    return create_pipeline_from_template(
        template_name="fallback_pipeline",
        custom_stages=custom_stages,
    )


def build_parallel_pipeline(
    custom_stages: Optional[dict] = None,
) -> Pipeline:
    """构建并行管道。"""
    return create_pipeline_from_template(
        template_name="parallel_pipeline",
        custom_stages=custom_stages,
    )


def build_conditional_pipeline(
    custom_stages: Optional[dict] = None,
) -> Pipeline:
    """构建条件管道。"""
    return create_pipeline_from_template(
        template_name="conditional_pipeline",
        custom_stages=custom_stages,
    )


# ===== 管道构建器 =====


class PipelineBuilder:
    """管道构建器

    提供流式 API 构建管道，支持链式调用。

    使用示例：
        pipeline = (
            PipelineBuilder("my_pipeline")
            .add_stage(SearchStage())
            .add_stage(ReasonStage())
            .with_error_strategy(ErrorHandlingStrategy.SKIP)
            .with_checkpoints(True)
            .build()
        )
    """

    def __init__(self, name: str = "pipeline"):
        self._name = name
        self._description = ""
        self._stages: list[PipelineStage] = []
        self._error_strategy = ErrorHandlingStrategy.RAISE
        self._max_retries = 0
        self._retry_delay = 1.0
        self._retry_backoff = 2.0
        self._default_timeout = 0.0
        self._enable_checkpoints = False
        self._tags: list = []
        self._monitor: Optional[PipelineMonitor] = None

    def description(self, desc: str) -> "PipelineBuilder":
        """设置管道描述。"""
        self._description = desc
        return self

    def add_stage(self, stage: PipelineStage) -> "PipelineBuilder":
        """添加阶段。"""
        self._stages.append(stage)
        return self

    def add_functional_stage(
        self, name: str, func: Callable, **kwargs
    ) -> "PipelineBuilder":
        """添加函数式阶段。"""
        self._stages.append(FunctionalStage(name=name, func=func, **kwargs))
        return self

    def with_error_strategy(self, strategy: ErrorHandlingStrategy) -> "PipelineBuilder":
        """设置错误处理策略。"""
        self._error_strategy = strategy
        return self

    def with_retries(
        self, max_retries: int, delay: float = 1.0, backoff: float = 2.0
    ) -> "PipelineBuilder":
        """设置重试配置。"""
        self._max_retries = max_retries
        self._retry_delay = delay
        self._retry_backoff = backoff
        return self

    def with_timeout(self, timeout: float) -> "PipelineBuilder":
        """设置默认超时时间。"""
        self._default_timeout = timeout
        return self

    def with_checkpoints(self, enabled: bool = True) -> "PipelineBuilder":
        """启用检查点。"""
        self._enable_checkpoints = enabled
        return self

    def with_tags(self, *tags: str) -> "PipelineBuilder":
        """添加标签。"""
        self._tags.extend(tags)
        return self

    def with_monitor(self, monitor: PipelineMonitor) -> "PipelineBuilder":
        """设置监控器。"""
        self._monitor = monitor
        return self

    def build(self) -> Pipeline:
        """构建管道。"""
        pipeline = Pipeline(
            name=self._name,
            description=self._description,
            error_strategy=self._error_strategy,
            max_retries=self._max_retries,
            retry_delay=self._retry_delay,
            retry_backoff=self._retry_backoff,
            default_timeout=self._default_timeout,
            enable_checkpoints=self._enable_checkpoints,
            tags=self._tags,
        )
        for stage in self._stages:
            pipeline.add_stage(stage)
        if self._monitor:
            pipeline.set_monitor(self._monitor)
        return pipeline


# ===== 管道事件 =====


class PipelineEvent:
    """管道事件

    用于在管道执行过程中发布事件，支持事件订阅与处理。
    """

    def __init__(
        self,
        event_type: str,
        pipeline_name: str = "",
        stage_name: str = "",
        data: Any = None,
        timestamp: float = 0.0,
    ):
        self.event_type = event_type
        self.pipeline_name = pipeline_name
        self.stage_name = stage_name
        self.data = data
        self.timestamp = timestamp or time.time()

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "pipeline_name": self.pipeline_name,
            "stage_name": self.stage_name,
            "data": self.data,
            "timestamp": self.timestamp,
        }


class PipelineEventBus:
    """管道事件总线

    发布订阅模式的事件总线，用于解耦管道执行与事件处理。
    """

    def __init__(self):
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """订阅事件。"""
        with self._lock:
            self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable) -> bool:
        """取消订阅。"""
        with self._lock:
            if event_type in self._handlers:
                try:
                    self._handlers[event_type].remove(handler)
                    return True
                except ValueError:
                    return False
            return False

    def publish(self, event: PipelineEvent) -> None:
        """发布事件。"""
        with self._lock:
            handlers = list(self._handlers.get(event.event_type, []))
            handlers.extend(self._handlers.get("*", []))  # 通配符订阅
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"事件处理器异常: {e}", exc_info=True)

    def clear(self) -> None:
        """清空所有订阅。"""
        with self._lock:
            self._handlers.clear()


# ===== 管道检查点管理器 =====


class CheckpointManager:
    """检查点管理器

    管理管道执行的检查点，支持持久化与恢复。
    """

    def __init__(self, storage_dir: str = "data/checkpoints"):
        self.storage_dir = storage_dir
        self._checkpoints: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        import os
        os.makedirs(self.storage_dir, exist_ok=True)

    def save_checkpoint(
        self,
        pipeline_name: str,
        stage_name: str,
        context: PipelineContext,
    ) -> str:
        """保存检查点。"""
        import json
        import uuid
        checkpoint_id = f"{pipeline_name}_{stage_name}_{uuid.uuid4().hex[:8]}"
        checkpoint_data = {
            "id": checkpoint_id,
            "pipeline_name": pipeline_name,
            "stage_name": stage_name,
            "context": context.to_dict(),
            "timestamp": time.time(),
        }
        with self._lock:
            self._checkpoints[checkpoint_id] = checkpoint_data
        # 持久化到文件
        filepath = os.path.join(self.storage_dir, f"{checkpoint_id}.json")
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(checkpoint_data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.warning(f"检查点持久化失败: {e}")
        return checkpoint_id

    def load_checkpoint(self, checkpoint_id: str) -> Optional[dict]:
        """加载检查点。"""
        with self._lock:
            if checkpoint_id in self._checkpoints:
                return self._checkpoints[checkpoint_id]
        # 从文件加载
        import json
        import os
        filepath = os.path.join(self.storage_dir, f"{checkpoint_id}.json")
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            with self._lock:
                self._checkpoints[checkpoint_id] = data
            return data
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def list_checkpoints(self, pipeline_name: Optional[str] = None) -> list:
        """列出检查点。"""
        with self._lock:
            if pipeline_name:
                return [
                    cp for cp in self._checkpoints.values()
                    if cp["pipeline_name"] == pipeline_name
                ]
            return list(self._checkpoints.values())

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """删除检查点。"""
        import os
        with self._lock:
            if checkpoint_id in self._checkpoints:
                del self._checkpoints[checkpoint_id]
        filepath = os.path.join(self.storage_dir, f"{checkpoint_id}.json")
        try:
            os.remove(filepath)
            return True
        except FileNotFoundError:
            return False

    def clear_all(self) -> None:
        """清空所有检查点。"""
        import os
        with self._lock:
            self._checkpoints.clear()
        # 清空目录
        try:
            for filename in os.listdir(self.storage_dir):
                if filename.endswith(".json"):
                    os.remove(os.path.join(self.storage_dir, filename))
        except Exception as e:
            logger.warning(f"清空检查点目录失败: {e}")


# ===== 模块级便捷函数 =====


def create_pipeline(name: str = "pipeline") -> Pipeline:
    """创建管道的便捷函数。"""
    return Pipeline(name=name)


def create_context(input_data: Optional[dict] = None) -> PipelineContext:
    """创建管道上下文的便捷函数。"""
    return PipelineContext(input_data=input_data)


def create_monitor() -> PipelineMonitor:
    """创建监控器的便捷函数。"""
    return PipelineMonitor()


def create_executor(
    max_workers: int = 4,
    monitor: Optional[PipelineMonitor] = None,
) -> PipelineExecutor:
    """创建执行器的便捷函数。"""
    return PipelineExecutor(max_workers=max_workers, monitor=monitor)


def create_builder(name: str = "pipeline") -> PipelineBuilder:
    """创建构建器的便捷函数。"""
    return PipelineBuilder(name=name)


# ===== 预定义阶段集合 =====


class CommonStages:
    """常用阶段集合

    提供一组通用的管道阶段，可直接用于构建管道。
    """

    @staticmethod
    def validate_input(required_keys: list = None) -> PipelineStage:
        """输入校验阶段。"""
        required_keys = required_keys or []

        def _validate(context: PipelineContext) -> StageResult:
            for key in required_keys:
                if key not in context.input_data:
                    return StageResult(
                        stage_name="validate_input",
                        status=StageStatus.FAILED,
                        error=f"缺少必需输入字段: {key}",
                    )
            return StageResult(
                stage_name="validate_input",
                status=StageStatus.SUCCESS,
                data={"validated": True},
            )

        return FunctionalStage(name="validate_input", func=_validate)

    @staticmethod
    def log_stage(message: str = "") -> PipelineStage:
        """日志记录阶段。"""
        def _log(context: PipelineContext) -> StageResult:
            log_msg = message or f"管道执行到阶段，当前数据键: {context.keys()}"
            logger.info(log_msg)
            return StageResult(
                stage_name="log",
                status=StageStatus.SUCCESS,
                data={"message": log_msg},
            )

        return FunctionalStage(name="log", func=_log)

    @staticmethod
    def transform_data(transformer: Callable) -> PipelineStage:
        """数据转换阶段。"""
        def _transform(context: PipelineContext) -> StageResult:
            try:
                transformed = transformer(context)
                if isinstance(transformed, dict):
                    context.update(transformed)
                return StageResult(
                    stage_name="transform",
                    status=StageStatus.SUCCESS,
                    data=transformed,
                )
            except Exception as e:
                return StageResult(
                    stage_name="transform",
                    status=StageStatus.FAILED,
                    error=str(e),
                )

        return FunctionalStage(name="transform", func=_transform)

    @staticmethod
    def conditional_stage(
        condition: Callable,
        true_stage: PipelineStage,
        false_stage: Optional[PipelineStage] = None,
    ) -> PipelineStage:
        """条件分支阶段。"""
        def _conditional(context: PipelineContext) -> StageResult:
            if condition(context):
                return true_stage.execute(context)
            elif false_stage:
                return false_stage.execute(context)
            return StageResult(
                stage_name="conditional",
                status=StageStatus.SKIPPED,
            )

        return FunctionalStage(name="conditional", func=_conditional)

    @staticmethod
    def noop_stage(name: str = "noop") -> PipelineStage:
        """空操作阶段。"""
        def _noop(context: PipelineContext) -> StageResult:
            return StageResult(
                stage_name=name,
                status=StageStatus.SUCCESS,
                data=None,
            )

        return FunctionalStage(name=name, func=_noop)

    @staticmethod
    def delay_stage(seconds: float = 1.0, name: str = "delay") -> PipelineStage:
        """延迟阶段。"""
        def _delay(context: PipelineContext) -> StageResult:
            time.sleep(seconds)
            return StageResult(
                stage_name=name,
                status=StageStatus.SUCCESS,
                data={"delayed_seconds": seconds},
            )

        return FunctionalStage(name=name, func=_delay)

    @staticmethod
    def cache_stage(
        cache_key: str,
        factory: Callable,
        name: str = "cache",
    ) -> PipelineStage:
        """缓存阶段。"""
        def _cache(context: PipelineContext) -> StageResult:
            cached = context.get(cache_key)
            if cached is not None:
                return StageResult(
                    stage_name=name,
                    status=StageStatus.SUCCESS,
                    data={"cached": True, "value": cached},
                )
            value = factory(context)
            context.set(cache_key, value)
            return StageResult(
                stage_name=name,
                status=StageStatus.SUCCESS,
                data={"cached": False, "value": value},
            )

        return FunctionalStage(name=name, func=_cache)

    @staticmethod
    def aggregate_stage(
        source_keys: list,
        target_key: str,
        name: str = "aggregate",
    ) -> PipelineStage:
        """聚合阶段。"""
        def _aggregate(context: PipelineContext) -> StageResult:
            aggregated = {}
            for key in source_keys:
                aggregated[key] = context.get(key)
            context.set(target_key, aggregated)
            return StageResult(
                stage_name=name,
                status=StageStatus.SUCCESS,
                data=aggregated,
            )

        return FunctionalStage(name=name, func=_aggregate)


# ===== 管道诊断工具 =====


class PipelineDiagnostics:
    """管道诊断工具

    提供管道执行后的诊断分析能力，包括瓶颈定位、错误分析、性能报告。
    """

    @staticmethod
    def analyze_result(result: PipelineResult) -> dict:
        """分析管道执行结果。"""
        analysis = {
            "pipeline_name": result.pipeline_name,
            "overall_status": result.status.value,
            "total_duration_ms": round(result.duration_ms, 2),
            "stage_count": result.total_stages,
            "executed_count": result.executed_stages,
            "failed_count": result.failed_stages,
            "skipped_count": result.skipped_stages,
            "success_rate": 0.0,
            "stages": [],
            "bottleneck_stage": None,
            "slowest_stages": [],
            "failed_stage_names": [],
            "recommendations": [],
        }

        if result.executed_stages > 0:
            analysis["success_rate"] = round(
                (result.executed_stages - result.failed_stages) / result.executed_stages * 100, 2
            )

        # 分析各阶段
        stage_durations = []
        for sr in result.stage_results:
            if isinstance(sr, StageResult):
                stage_info = {
                    "name": sr.stage_name,
                    "status": sr.status.value,
                    "duration_ms": round(sr.duration_ms, 2),
                    "retry_count": sr.retry_count,
                    "error": sr.error,
                }
                analysis["stages"].append(stage_info)
                if sr.success:
                    stage_durations.append((sr.stage_name, sr.duration_ms))
                if sr.failed:
                    analysis["failed_stage_names"].append(sr.stage_name)

        # 找出瓶颈阶段（耗时最长的成功阶段）
        if stage_durations:
            stage_durations.sort(key=lambda x: x[1], reverse=True)
            analysis["bottleneck_stage"] = stage_durations[0][0]
            analysis["slowest_stages"] = [
                {"name": name, "duration_ms": round(dur, 2)}
                for name, dur in stage_durations[:3]
            ]

        # 生成建议
        if result.failed_stages > 0:
            analysis["recommendations"].append(
                f"有 {result.failed_stages} 个阶段失败，建议检查失败阶段的错误信息"
            )
        if analysis["bottleneck_stage"]:
            analysis["recommendations"].append(
                f"瓶颈阶段为 {analysis['bottleneck_stage']}，建议优化其性能"
            )
        if result.duration_ms > 10000:
            analysis["recommendations"].append(
                "管道总耗时超过 10 秒，建议考虑并行化或缓存优化"
            )

        return analysis

    @staticmethod
    def generate_report(result: PipelineResult) -> str:
        """生成可读的执行报告。"""
        analysis = PipelineDiagnostics.analyze_result(result)
        lines = [
            f"===== 管道执行报告 =====",
            f"管道名称: {analysis['pipeline_name']}",
            f"总体状态: {analysis['overall_status']}",
            f"总耗时: {analysis['total_duration_ms']}ms",
            f"阶段总数: {analysis['stage_count']}",
            f"成功: {analysis['executed_count'] - analysis['failed_count']}",
            f"失败: {analysis['failed_count']}",
            f"跳过: {analysis['skipped_count']}",
            f"成功率: {analysis['success_rate']}%",
            "",
            "----- 阶段详情 -----",
        ]
        for stage in analysis["stages"]:
            lines.append(
                f"  {stage['name']}: {stage['status']} "
                f"({stage['duration_ms']}ms, 重试{stage['retry_count']}次)"
            )
            if stage["error"]:
                lines.append(f"    错误: {stage['error']}")

        if analysis["bottleneck_stage"]:
            lines.append("")
            lines.append(f"瓶颈阶段: {analysis['bottleneck_stage']}")

        if analysis["recommendations"]:
            lines.append("")
            lines.append("----- 建议 -----")
            for rec in analysis["recommendations"]:
                lines.append(f"  - {rec}")

        lines.append("=" * 30)
        return "\n".join(lines)

    @staticmethod
    def compare_results(result1: PipelineResult, result2: PipelineResult) -> dict:
        """比较两次管道执行结果。"""
        return {
            "pipeline_name": result1.pipeline_name,
            "duration_diff_ms": round(result2.duration_ms - result1.duration_ms, 2),
            "status_changed": result1.status != result2.status,
            "result1_status": result1.status.value,
            "result2_status": result2.status.value,
            "result1_duration_ms": round(result1.duration_ms, 2),
            "result2_duration_ms": round(result2.duration_ms, 2),
            "improvement": result2.duration_ms < result1.duration_ms,
        }


# ===== 模块导出 =====


__all__ = [
    # 枚举
    "StageStatus",
    "PipelineStatus",
    "ErrorHandlingStrategy",
    "TemplateCategory",
    # 数据类
    "StageResult",
    "PipelineResult",
    # 上下文
    "PipelineContext",
    # 阶段
    "PipelineStage",
    "FunctionalStage",
    "AsyncFunctionalStage",
    # 管道
    "Pipeline",
    "PipelineBuilder",
    # 执行器与监控
    "PipelineExecutor",
    "PipelineMonitor",
    # 模板
    "PipelineTemplateRegistry",
    # 事件
    "PipelineEvent",
    "PipelineEventBus",
    # 检查点
    "CheckpointManager",
    # 诊断
    "PipelineDiagnostics",
    # 常用阶段
    "CommonStages",
    # 便捷函数
    "create_pipeline",
    "create_context",
    "create_monitor",
    "create_executor",
    "create_builder",
    "get_template_registry",
    "create_pipeline_from_template",
    "list_pipeline_templates",
    # 阶段工厂
    "create_search_stage",
    "create_reason_stage",
    "create_critic_stage",
    "create_writer_stage",
    "create_deep_assist_stage",
    # 管道构建函数
    "build_proposal_generation_pipeline",
    "build_literature_review_pipeline",
    "build_feasibility_check_pipeline",
    "build_originality_check_pipeline",
    "build_format_check_pipeline",
    "build_deep_assist_full_pipeline",
    "build_multi_granularity_pipeline",
    "build_plagiarism_scan_pipeline",
    "build_batch_generation_pipeline",
    "build_iterative_refinement_pipeline",
    "build_ab_test_pipeline",
    "build_fallback_pipeline",
    "build_parallel_pipeline",
    "build_conditional_pipeline",
]
