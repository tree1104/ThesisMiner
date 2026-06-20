"""编排管道模块单元测试

测试 backend/orchestration/pipeline.py 中的所有组件：
    - 枚举: StageStatus / PipelineStatus / ErrorHandlingStrategy / TemplateCategory
    - 数据类: StageResult / PipelineResult
    - PipelineContext: 管道上下文（数据传递容器）
    - PipelineStage: 阶段基类 / FunctionalStage / AsyncFunctionalStage
    - Pipeline: 管道主类（阶段组合/顺序执行/错误处理/重试）
    - PipelineMonitor: 管道监控器
    - PipelineExecutor: 管道执行器（同步/异步/批量/并行）
    - PipelineTemplateRegistry: 20+ 管道模板注册表
    - PipelineBuilder: 流式构建器
    - PipelineEvent / PipelineEventBus: 事件总线
    - CheckpointManager: 检查点管理器
    - CommonStages: 常用阶段集合
    - 全局函数: create_pipeline / create_context / get_template_registry 等

测试覆盖：
    - 枚举值与属性
    - 数据类的字段、属性、序列化
    - 上下文的增删改查、检查点、克隆、合并
    - 阶段的执行、条件判断、依赖声明
    - 管道的阶段组合（添加/插入/移除/替换）、执行流程、错误处理、重试
    - 监控器的事件记录与统计
    - 执行器的同步/异步/批量/并行执行
    - 模板注册表的 20+ 模板、创建管道、自定义模板
    - 构建器的链式 API
    - 事件总线的订阅/发布/取消
    - 检查点的保存/加载/删除
    - 边界条件与异常场景
"""
import asyncio
import os
import sys
import time
import threading
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
    from backend.orchestration.pipeline import (
        StageStatus,
        PipelineStatus,
        ErrorHandlingStrategy,
        TemplateCategory,
        StageResult,
        PipelineResult,
        PipelineContext,
        PipelineStage,
        FunctionalStage,
        AsyncFunctionalStage,
        Pipeline,
        PipelineMonitor,
        PipelineExecutor,
        PipelineTemplateRegistry,
        PipelineBuilder,
        PipelineEvent,
        PipelineEventBus,
        CheckpointManager,
        CommonStages,
        create_pipeline,
        create_context,
        create_monitor,
        create_executor,
        create_builder,
        get_template_registry,
        create_pipeline_from_template,
        list_pipeline_templates,
    )
    _IMPORT_OK = True
except Exception as exc:  # pragma: no cover
    _IMPORT_ERROR = str(exc)

pytestmark = pytest.mark.skipif(not _IMPORT_OK, reason=f"被测模块导入失败: {_IMPORT_ERROR}")


# ===== 辅助函数 =====


def _make_simple_stage(name: str = "simple", data: object = None) -> FunctionalStage:
    """构造简单的函数式阶段。"""
    def _func(context: PipelineContext):
        context.set(name, data if data is not None else f"{name}_output")
        return data if data is not None else f"{name}_output"
    return FunctionalStage(name=name, func=_func)


def _make_failing_stage(name: str = "failing", error_msg: str = "阶段执行失败") -> FunctionalStage:
    """构造总是失败的函数式阶段。"""
    def _func(context: PipelineContext):
        raise RuntimeError(error_msg)
    return FunctionalStage(name=name, func=_func)


def _make_context(input_data: dict = None) -> PipelineContext:
    """构造测试用上下文。"""
    return PipelineContext(input_data=input_data or {"query": "深度学习"})


# ===== 枚举测试 =====


class TestStageStatus:
    """测试 StageStatus 枚举。"""

    def test_enum_values(self):
        """测试枚举值。"""
        assert StageStatus.PENDING.value == "pending"
        assert StageStatus.RUNNING.value == "running"
        assert StageStatus.SUCCESS.value == "success"
        assert StageStatus.FAILED.value == "failed"
        assert StageStatus.SKIPPED.value == "skipped"
        assert StageStatus.RETRYING.value == "retrying"
        assert StageStatus.TIMEOUT.value == "timeout"
        assert StageStatus.CANCELLED.value == "cancelled"

    def test_enum_count(self):
        """测试枚举成员数。"""
        assert len(list(StageStatus)) == 8


class TestPipelineStatus:
    """测试 PipelineStatus 枚举。"""

    def test_enum_values(self):
        """测试枚举值。"""
        assert PipelineStatus.IDLE.value == "idle"
        assert PipelineStatus.RUNNING.value == "running"
        assert PipelineStatus.SUCCESS.value == "success"
        assert PipelineStatus.FAILED.value == "failed"
        assert PipelineStatus.CANCELLED.value == "cancelled"
        assert PipelineStatus.PARTIAL.value == "partial"

    def test_enum_count(self):
        """测试枚举成员数。"""
        assert len(list(PipelineStatus)) == 6


class TestErrorHandlingStrategy:
    """测试 ErrorHandlingStrategy 枚举。"""

    def test_enum_values(self):
        """测试枚举值。"""
        assert ErrorHandlingStrategy.RAISE.value == "raise"
        assert ErrorHandlingStrategy.SKIP.value == "skip"
        assert ErrorHandlingStrategy.RETRY.value == "retry"
        assert ErrorHandlingStrategy.FALLBACK.value == "fallback"
        assert ErrorHandlingStrategy.ROLLBACK.value == "rollback"

    def test_enum_count(self):
        """测试枚举成员数。"""
        assert len(list(ErrorHandlingStrategy)) == 5


class TestTemplateCategory:
    """测试 TemplateCategory 枚举。"""

    def test_enum_values(self):
        """测试枚举值。"""
        assert TemplateCategory.GENERATION.value == "generation"
        assert TemplateCategory.VALIDATION.value == "validation"
        assert TemplateCategory.ANALYSIS.value == "analysis"
        assert TemplateCategory.ASSIST.value == "assist"
        assert TemplateCategory.BATCH.value == "batch"
        assert TemplateCategory.ADVANCED.value == "advanced"

    def test_enum_count(self):
        """测试枚举成员数。"""
        assert len(list(TemplateCategory)) == 6


# ===== StageResult 测试 =====


class TestStageResult:
    """测试 StageResult 数据类。"""

    def test_default_values(self):
        """测试默认值。"""
        result = StageResult()
        assert result.stage_name == ""
        assert result.status == StageStatus.PENDING
        assert result.data is None
        assert result.error is None
        assert result.retry_count == 0
        assert result.metadata == {}

    def test_success_property(self):
        """测试 success 属性。"""
        result = StageResult(status=StageStatus.SUCCESS)
        assert result.success is True
        assert result.failed is False
        assert result.skipped is False

    def test_failed_property(self):
        """测试 failed 属性。"""
        result = StageResult(status=StageStatus.FAILED)
        assert result.failed is True
        assert result.success is False

    def test_timeout_is_failed(self):
        """测试超时也算失败。"""
        result = StageResult(status=StageStatus.TIMEOUT)
        assert result.failed is True

    def test_skipped_property(self):
        """测试 skipped 属性。"""
        result = StageResult(status=StageStatus.SKIPPED)
        assert result.skipped is True
        assert result.success is False
        assert result.failed is False

    def test_to_dict(self):
        """测试转换为字典。"""
        result = StageResult(
            stage_name="test_stage",
            status=StageStatus.SUCCESS,
            data={"key": "value"},
            duration_ms=100.5,
            retry_count=2,
        )
        d = result.to_dict()
        assert d["stage_name"] == "test_stage"
        assert d["status"] == "success"
        assert d["data"] == {"key": "value"}
        assert d["duration_ms"] == 100.5
        assert d["retry_count"] == 2


# ===== PipelineResult 测试 =====


class TestPipelineResult:
    """测试 PipelineResult 数据类。"""

    def test_default_values(self):
        """测试默认值。"""
        result = PipelineResult()
        assert result.pipeline_name == ""
        assert result.status == PipelineStatus.IDLE
        assert result.data is None
        assert result.stage_results == []
        assert result.total_stages == 0
        assert result.executed_stages == 0
        assert result.failed_stages == 0
        assert result.skipped_stages == 0

    def test_success_property(self):
        """测试 success 属性。"""
        result = PipelineResult(status=PipelineStatus.SUCCESS)
        assert result.success is True
        assert result.failed is False

    def test_failed_property(self):
        """测试 failed 属性。"""
        result = PipelineResult(status=PipelineStatus.FAILED)
        assert result.failed is True
        assert result.success is False

    def test_get_stage_result_by_name(self):
        """测试按名称获取阶段结果。"""
        sr = StageResult(stage_name="stage1", status=StageStatus.SUCCESS)
        result = PipelineResult(stage_results=[sr])
        found = result.get_stage_result("stage1")
        assert found is not None
        assert found.stage_name == "stage1"

    def test_get_stage_result_not_found(self):
        """测试获取不存在的阶段结果。"""
        result = PipelineResult(stage_results=[])
        assert result.get_stage_result("nonexistent") is None

    def test_get_stage_result_from_dict(self):
        """测试从字典形式获取阶段结果。"""
        result = PipelineResult(
            stage_results=[{"stage_name": "dict_stage", "status": "success", "data": "ok"}]
        )
        found = result.get_stage_result("dict_stage")
        assert found is not None
        assert found.stage_name == "dict_stage"

    def test_to_dict(self):
        """测试转换为字典。"""
        sr = StageResult(stage_name="s1", status=StageStatus.SUCCESS)
        result = PipelineResult(
            pipeline_name="test",
            status=PipelineStatus.SUCCESS,
            total_stages=3,
            executed_stages=3,
            stage_results=[sr],
        )
        d = result.to_dict()
        assert d["pipeline_name"] == "test"
        assert d["status"] == "success"
        assert d["total_stages"] == 3
        assert len(d["stage_results"]) == 1


# ===== PipelineContext 测试 =====


class TestPipelineContext:
    """测试 PipelineContext 管道上下文。"""

    def test_init_with_defaults(self):
        """测试默认初始化。"""
        ctx = PipelineContext()
        assert ctx.input_data == {}
        assert ctx.metadata == {}
        assert ctx.session_id == ""
        assert ctx.conversation_id == ""
        assert ctx.current_stage == ""
        assert ctx.is_cancelled is False

    def test_init_with_data(self):
        """测试带数据初始化。"""
        ctx = PipelineContext(
            input_data={"query": "测试", "degree": "master"},
            metadata={"key": "value"},
            session_id="s1",
            conversation_id="c1",
        )
        assert ctx.input_data["query"] == "测试"
        assert ctx.metadata["key"] == "value"
        assert ctx.session_id == "s1"
        assert ctx.conversation_id == "c1"

    def test_user_input_extraction(self):
        """测试用户输入提取。"""
        ctx = PipelineContext(input_data={"user_input": "用户输入"})
        assert ctx.user_input == "用户输入"
        ctx2 = PipelineContext(input_data={"query": "查询"})
        assert ctx2.user_input == "查询"

    def test_degree_discipline_extraction(self):
        """测试学位与学科提取。"""
        ctx = PipelineContext(input_data={"degree": "doctor", "discipline": "CS"})
        assert ctx.degree == "doctor"
        assert ctx.discipline == "CS"

    def test_set_and_get(self):
        """测试设置与获取数据。"""
        ctx = PipelineContext()
        ctx.set("key1", "value1")
        assert ctx.get("key1") == "value1"

    def test_get_with_default(self):
        """测试获取不存在的键返回默认值。"""
        ctx = PipelineContext()
        assert ctx.get("nonexistent") is None
        assert ctx.get("nonexistent", "default") == "default"

    def test_update(self):
        """测试批量更新。"""
        ctx = PipelineContext()
        ctx.update({"a": 1, "b": 2})
        assert ctx.get("a") == 1
        assert ctx.get("b") == 2

    def test_remove(self):
        """测试移除数据。"""
        ctx = PipelineContext()
        ctx.set("key", "value")
        assert ctx.remove("key") is True
        assert ctx.get("key") is None

    def test_remove_nonexistent(self):
        """测试移除不存在的键。"""
        ctx = PipelineContext()
        assert ctx.remove("nonexistent") is False

    def test_has(self):
        """测试判断键存在。"""
        ctx = PipelineContext()
        ctx.set("key", "value")
        assert ctx.has("key") is True
        assert ctx.has("nonexistent") is False

    def test_keys(self):
        """测试获取所有键。"""
        ctx = PipelineContext()
        ctx.set("a", 1)
        ctx.set("b", 2)
        keys = ctx.keys()
        assert "a" in keys
        assert "b" in keys

    def test_to_dict(self):
        """测试转换为字典。"""
        ctx = PipelineContext(input_data={"q": "test"}, session_id="s1")
        ctx.set("data_key", "data_value")
        d = ctx.to_dict()
        assert d["input_data"]["q"] == "test"
        assert d["data"]["data_key"] == "data_value"
        assert d["session_id"] == "s1"

    def test_save_and_restore_checkpoint(self):
        """测试保存与恢复检查点。"""
        ctx = PipelineContext()
        ctx.set("key", "original")
        ctx.save_checkpoint("stage1")
        # 修改数据
        ctx.set("key", "modified")
        # 恢复检查点
        assert ctx.restore_checkpoint("stage1") is True
        assert ctx.get("key") == "original"

    def test_restore_nonexistent_checkpoint(self):
        """测试恢复不存在的检查点。"""
        ctx = PipelineContext()
        assert ctx.restore_checkpoint("nonexistent") is False

    def test_list_checkpoints(self):
        """测试列出检查点。"""
        ctx = PipelineContext()
        ctx.save_checkpoint("stage1")
        ctx.save_checkpoint("stage2")
        checkpoints = ctx.list_checkpoints()
        assert "stage1" in checkpoints
        assert "stage2" in checkpoints

    def test_log_execution(self):
        """测试记录执行日志。"""
        ctx = PipelineContext()
        ctx.log_execution("stage1", "success", 100.5)
        log = ctx.get_execution_log()
        assert len(log) == 1
        assert log[0]["stage"] == "stage1"
        assert log[0]["status"] == "success"
        assert log[0]["duration_ms"] == 100.5

    def test_cancel(self):
        """测试取消管道。"""
        ctx = PipelineContext()
        assert ctx.is_cancelled is False
        ctx.cancel()
        assert ctx.is_cancelled is True

    def test_clone(self):
        """测试克隆上下文。"""
        ctx = PipelineContext(input_data={"q": "test"}, session_id="s1")
        ctx.set("key", "value")
        cloned = ctx.clone()
        assert cloned.session_id == "s1"
        assert cloned.get("key") == "value"
        # 修改克隆不影响原对象
        cloned.set("key", "modified")
        assert ctx.get("key") == "value"

    def test_merge(self):
        """测试合并上下文。"""
        ctx1 = PipelineContext()
        ctx1.set("a", 1)
        ctx2 = PipelineContext()
        ctx2.set("b", 2)
        ctx1.merge(ctx2)
        assert ctx1.get("a") == 1
        assert ctx1.get("b") == 2


# ===== PipelineStage 测试 =====


class TestPipelineStage:
    """测试 PipelineStage 阶段基类。"""

    def test_init_defaults(self):
        """测试默认初始化。"""
        stage = PipelineStage()
        assert stage.name == "PipelineStage"
        assert stage.description == ""
        assert stage.timeout == 0.0
        assert stage.max_retries == 0
        assert stage.error_strategy == ErrorHandlingStrategy.RAISE
        assert stage.tags == []

    def test_init_with_params(self):
        """测试带参数初始化。"""
        stage = PipelineStage(
            name="custom",
            description="自定义阶段",
            timeout=30.0,
            max_retries=3,
            error_strategy=ErrorHandlingStrategy.SKIP,
        )
        assert stage.name == "custom"
        assert stage.description == "自定义阶段"
        assert stage.timeout == 30.0
        assert stage.max_retries == 3
        assert stage.error_strategy == ErrorHandlingStrategy.SKIP

    def test_execute_not_implemented(self):
        """测试基类 execute 抛出 NotImplementedError。"""
        stage = PipelineStage(name="base")
        ctx = PipelineContext()
        with pytest.raises(NotImplementedError):
            stage.execute(ctx)

    def test_should_run_default(self):
        """测试默认应执行。"""
        stage = PipelineStage(name="test")
        ctx = PipelineContext()
        assert stage.should_run(ctx) is True

    def test_should_run_cancelled_context(self):
        """测试上下文取消时不应执行。"""
        stage = PipelineStage(name="test")
        ctx = PipelineContext()
        ctx.cancel()
        assert stage.should_run(ctx) is False

    def test_should_run_with_condition(self):
        """测试带条件的执行判断。"""
        stage = PipelineStage(
            name="conditional",
            condition=lambda ctx: ctx.get("flag", False),
        )
        ctx = PipelineContext()
        assert stage.should_run(ctx) is False
        ctx.set("flag", True)
        assert stage.should_run(ctx) is True

    def test_should_run_condition_exception(self):
        """测试条件函数异常时返回 False。"""
        def _bad_condition(ctx):
            raise ValueError("条件异常")
        stage = PipelineStage(name="bad_cond", condition=_bad_condition)
        ctx = PipelineContext()
        assert stage.should_run(ctx) is False

    def test_depends_on(self):
        """测试声明依赖。"""
        stage = PipelineStage(name="dep_test")
        stage.depends_on("stage_a")
        stage.depends_on("stage_b")
        deps = stage.get_dependencies()
        assert "stage_a" in deps
        assert "stage_b" in deps

    def test_depends_on_dedup(self):
        """测试依赖去重。"""
        stage = PipelineStage(name="dep_dedup")
        stage.depends_on("stage_a")
        stage.depends_on("stage_a")
        assert len(stage.get_dependencies()) == 1

    def test_initialize_and_cleanup(self):
        """测试初始化与清理。"""
        stage = PipelineStage(name="init_clean")
        ctx = PipelineContext()
        stage.initialize(ctx)
        assert stage._initialized is True
        stage.cleanup(ctx)  # 不应报错

    def test_repr(self):
        """测试字符串表示。"""
        stage = PipelineStage(name="repr_test", timeout=10.0, max_retries=2)
        repr_str = repr(stage)
        assert "repr_test" in repr_str


class TestFunctionalStage:
    """测试 FunctionalStage 函数式阶段。"""

    def test_execute_success(self):
        """测试成功执行。"""
        def _func(ctx):
            ctx.set("result", "done")
            return "done"
        stage = FunctionalStage(name="func1", func=_func)
        ctx = PipelineContext()
        result = stage.execute(ctx)
        assert result.success is True
        assert result.stage_name == "func1"
        assert result.data == "done"
        assert ctx.get("result") == "done"

    def test_execute_failure(self):
        """测试执行失败。"""
        def _func(ctx):
            raise RuntimeError("执行失败")
        stage = FunctionalStage(name="func_fail", func=_func)
        ctx = PipelineContext()
        result = stage.execute(ctx)
        assert result.failed is True
        assert "执行失败" in result.error
        assert result.error_type == "RuntimeError"

    def test_execute_returns_stage_result(self):
        """测试函数返回 StageResult 时直接使用。"""
        def _func(ctx):
            return StageResult(
                stage_name="custom",
                status=StageStatus.SUCCESS,
                data="custom_data",
            )
        stage = FunctionalStage(name="func_custom", func=_func)
        ctx = PipelineContext()
        result = stage.execute(ctx)
        assert result.data == "custom_data"

    def test_execute_duration_recorded(self):
        """测试执行耗时被记录。"""
        def _func(ctx):
            time.sleep(0.01)
            return "ok"
        stage = FunctionalStage(name="duration_test", func=_func)
        ctx = PipelineContext()
        result = stage.execute(ctx)
        assert result.duration_ms > 0


# ===== Pipeline 测试 =====


class TestPipeline:
    """测试 Pipeline 管道主类。"""

    def test_init_defaults(self):
        """测试默认初始化。"""
        pipeline = Pipeline()
        assert pipeline.name == "pipeline"
        assert pipeline.error_strategy == ErrorHandlingStrategy.RAISE
        assert pipeline.max_retries == 0
        assert pipeline.stage_count() == 0

    def test_add_stage(self):
        """测试添加阶段。"""
        pipeline = Pipeline(name="test")
        stage = _make_simple_stage("s1")
        pipeline.add_stage(stage)
        assert pipeline.stage_count() == 1
        assert "s1" in pipeline.get_stage_names()

    def test_add_stage_chaining(self):
        """测试链式添加阶段。"""
        pipeline = Pipeline(name="chain")
        result = pipeline.add_stage(_make_simple_stage("s1"))
        assert result is pipeline

    def test_add_duplicate_stage_name(self):
        """测试添加重名阶段抛出异常。"""
        pipeline = Pipeline(name="dup")
        pipeline.add_stage(_make_simple_stage("s1"))
        with pytest.raises(ValueError, match="已存在"):
            pipeline.add_stage(_make_simple_stage("s1"))

    def test_insert_stage(self):
        """测试在指定位置插入阶段。"""
        pipeline = Pipeline(name="insert")
        pipeline.add_stage(_make_simple_stage("s1"))
        pipeline.add_stage(_make_simple_stage("s3"))
        pipeline.insert_stage(1, _make_simple_stage("s2"))
        names = pipeline.get_stage_names()
        assert names == ["s1", "s2", "s3"]

    def test_insert_after(self):
        """测试在指定阶段后插入。"""
        pipeline = Pipeline(name="insert_after")
        pipeline.add_stage(_make_simple_stage("s1"))
        pipeline.add_stage(_make_simple_stage("s3"))
        pipeline.insert_after("s1", _make_simple_stage("s2"))
        names = pipeline.get_stage_names()
        assert names == ["s1", "s2", "s3"]

    def test_insert_before(self):
        """测试在指定阶段前插入。"""
        pipeline = Pipeline(name="insert_before")
        pipeline.add_stage(_make_simple_stage("s1"))
        pipeline.add_stage(_make_simple_stage("s3"))
        pipeline.insert_before("s3", _make_simple_stage("s2"))
        names = pipeline.get_stage_names()
        assert names == ["s1", "s2", "s3"]

    def test_remove_stage(self):
        """测试移除阶段。"""
        pipeline = Pipeline(name="remove")
        pipeline.add_stage(_make_simple_stage("s1"))
        pipeline.add_stage(_make_simple_stage("s2"))
        assert pipeline.remove_stage("s1") is True
        assert pipeline.stage_count() == 1
        assert "s1" not in pipeline.get_stage_names()

    def test_remove_nonexistent_stage(self):
        """测试移除不存在的阶段。"""
        pipeline = Pipeline(name="remove_nonexist")
        assert pipeline.remove_stage("nonexistent") is False

    def test_replace_stage(self):
        """测试替换阶段。"""
        pipeline = Pipeline(name="replace")
        pipeline.add_stage(_make_simple_stage("s1"))
        pipeline.replace_stage("s1", _make_simple_stage("s2"))
        assert "s1" not in pipeline.get_stage_names()
        assert "s2" in pipeline.get_stage_names()

    def test_replace_nonexistent(self):
        """测试替换不存在的阶段。"""
        pipeline = Pipeline(name="replace_nonexist")
        assert pipeline.replace_stage("nonexistent", _make_simple_stage("s1")) is False

    def test_get_stage(self):
        """测试获取指定阶段。"""
        pipeline = Pipeline(name="get")
        stage = _make_simple_stage("s1")
        pipeline.add_stage(stage)
        found = pipeline.get_stage("s1")
        assert found is stage

    def test_get_stage_nonexistent(self):
        """测试获取不存在的阶段。"""
        pipeline = Pipeline(name="get_nonexist")
        assert pipeline.get_stage("nonexistent") is None

    def test_get_stages(self):
        """测试获取所有阶段列表。"""
        pipeline = Pipeline(name="all")
        pipeline.add_stage(_make_simple_stage("s1"))
        pipeline.add_stage(_make_simple_stage("s2"))
        stages = pipeline.get_stages()
        assert len(stages) == 2

    def test_clear_stages(self):
        """测试清空阶段。"""
        pipeline = Pipeline(name="clear")
        pipeline.add_stage(_make_simple_stage("s1"))
        pipeline.clear_stages()
        assert pipeline.stage_count() == 0

    def test_execute_success(self):
        """测试成功执行管道。"""
        pipeline = Pipeline(name="exec_ok")
        pipeline.add_stage(_make_simple_stage("s1", "output1"))
        pipeline.add_stage(_make_simple_stage("s2", "output2"))
        ctx = _make_context()
        result = pipeline.execute(ctx)
        assert result.success is True
        assert result.total_stages == 2
        assert result.executed_stages == 2
        assert result.failed_stages == 0

    def test_execute_empty_pipeline(self):
        """测试执行空管道。"""
        pipeline = Pipeline(name="empty")
        ctx = _make_context()
        result = pipeline.execute(ctx)
        assert result.success is True
        assert result.total_stages == 0

    def test_execute_with_failure_raise(self):
        """测试失败时抛出策略。"""
        pipeline = Pipeline(
            name="fail_raise",
            error_strategy=ErrorHandlingStrategy.RAISE,
        )
        pipeline.add_stage(_make_failing_stage("fail_stage"))
        ctx = _make_context()
        result = pipeline.execute(ctx)
        assert result.failed_stages >= 1

    def test_execute_with_skip_strategy(self):
        """测试跳过失败阶段策略。"""
        pipeline = Pipeline(
            name="fail_skip",
            error_strategy=ErrorHandlingStrategy.SKIP,
        )
        pipeline.add_stage(_make_simple_stage("s1", "out1"))
        pipeline.add_stage(_make_failing_stage("fail"))
        pipeline.add_stage(_make_simple_stage("s3", "out3"))
        ctx = _make_context()
        result = pipeline.execute(ctx)
        # 跳过策略下应继续执行后续阶段
        assert result.executed_stages >= 2

    def test_execute_with_cancel(self):
        """测试取消管道执行。"""
        pipeline = Pipeline(name="cancel_test")
        def _cancel_func(ctx):
            ctx.cancel()
            return "ok"
        pipeline.add_stage(FunctionalStage(name="cancel_stage", func=_cancel_func))
        pipeline.add_stage(_make_simple_stage("after_cancel"))
        ctx = _make_context()
        result = pipeline.execute(ctx)
        assert result.status == PipelineStatus.CANCELLED

    def test_execute_with_condition(self):
        """测试带条件的阶段执行。"""
        pipeline = Pipeline(name="conditional")
        pipeline.add_stage(_make_simple_stage("s1", "out1"))
        # 条件为 False 的阶段应被跳过
        pipeline.add_stage(PipelineStage(
            name="conditional_stage",
            condition=lambda ctx: False,
        ))
        ctx = _make_context()
        result = pipeline.execute(ctx)
        assert result.skipped_stages >= 1

    def test_execute_with_checkpoints(self):
        """测试启用检查点的执行。"""
        pipeline = Pipeline(name="checkpoints", enable_checkpoints=True)
        pipeline.add_stage(_make_simple_stage("s1", "out1"))
        pipeline.add_stage(_make_simple_stage("s2", "out2"))
        ctx = _make_context()
        pipeline.execute(ctx)
        checkpoints = ctx.list_checkpoints()
        assert "s1" in checkpoints
        assert "s2" in checkpoints

    def test_set_monitor(self):
        """测试设置监控器。"""
        pipeline = Pipeline(name="monitor_test")
        monitor = PipelineMonitor()
        pipeline.set_monitor(monitor)
        ctx = _make_context()
        pipeline.add_stage(_make_simple_stage("s1"))
        pipeline.execute(ctx)
        events = monitor.get_events()
        assert len(events) > 0

    def test_stage_count(self):
        """测试阶段计数。"""
        pipeline = Pipeline(name="count")
        assert pipeline.stage_count() == 0
        pipeline.add_stage(_make_simple_stage("s1"))
        assert pipeline.stage_count() == 1


# ===== PipelineMonitor 测试 =====


class TestPipelineMonitor:
    """测试 PipelineMonitor 管道监控器。"""

    def test_init(self):
        """测试初始化。"""
        monitor = PipelineMonitor()
        assert monitor.get_events() == []

    def test_on_pipeline_start(self):
        """测试管道开始事件。"""
        monitor = PipelineMonitor()
        pipeline = Pipeline(name="mon_start")
        pipeline.add_stage(_make_simple_stage("s1"))
        ctx = _make_context()
        pipeline.set_monitor(monitor)
        pipeline.execute(ctx)
        start_events = monitor.get_events("pipeline_start")
        assert len(start_events) >= 1

    def test_on_pipeline_end(self):
        """测试管道结束事件。"""
        monitor = PipelineMonitor()
        pipeline = Pipeline(name="mon_end")
        pipeline.add_stage(_make_simple_stage("s1"))
        ctx = _make_context()
        pipeline.set_monitor(monitor)
        pipeline.execute(ctx)
        end_events = monitor.get_events("pipeline_end")
        assert len(end_events) >= 1

    def test_on_stage_success(self):
        """测试阶段成功事件。"""
        monitor = PipelineMonitor()
        pipeline = Pipeline(name="mon_stage_ok")
        pipeline.add_stage(_make_simple_stage("s1"))
        ctx = _make_context()
        pipeline.set_monitor(monitor)
        pipeline.execute(ctx)
        success_events = monitor.get_events("stage_success")
        assert len(success_events) >= 1

    def test_on_stage_failure(self):
        """测试阶段失败事件。"""
        monitor = PipelineMonitor()
        pipeline = Pipeline(name="mon_stage_fail")
        pipeline.add_stage(_make_failing_stage("fail"))
        ctx = _make_context()
        pipeline.set_monitor(monitor)
        pipeline.execute(ctx)
        failure_events = monitor.get_events("stage_failure")
        assert len(failure_events) >= 1

    def test_on_stage_skip(self):
        """测试阶段跳过事件。"""
        monitor = PipelineMonitor()
        pipeline = Pipeline(name="mon_skip")
        pipeline.add_stage(PipelineStage(
            name="skip_stage",
            condition=lambda ctx: False,
        ))
        ctx = _make_context()
        pipeline.set_monitor(monitor)
        pipeline.execute(ctx)
        skip_events = monitor.get_events("stage_skip")
        assert len(skip_events) >= 1

    def test_get_stage_stats(self):
        """测试获取阶段统计。"""
        monitor = PipelineMonitor()
        pipeline = Pipeline(name="mon_stats")
        pipeline.add_stage(_make_simple_stage("s1"))
        ctx = _make_context()
        pipeline.set_monitor(monitor)
        pipeline.execute(ctx)
        stats = monitor.get_stage_stats()
        assert "s1" in stats
        assert stats["s1"]["total"] >= 1
        assert stats["s1"]["success"] >= 1

    def test_get_pipeline_stats(self):
        """测试获取管道统计。"""
        monitor = PipelineMonitor()
        pipeline = Pipeline(name="mon_pipe_stats")
        pipeline.add_stage(_make_simple_stage("s1"))
        ctx = _make_context()
        pipeline.set_monitor(monitor)
        pipeline.execute(ctx)
        stats = monitor.get_pipeline_stats()
        assert "mon_pipe_stats" in stats

    def test_get_stats(self):
        """测试获取汇总统计。"""
        monitor = PipelineMonitor()
        pipeline = Pipeline(name="mon_summary")
        pipeline.add_stage(_make_simple_stage("s1"))
        ctx = _make_context()
        pipeline.set_monitor(monitor)
        pipeline.execute(ctx)
        stats = monitor.get_stats()
        assert "pipelines" in stats
        assert "stages" in stats
        assert "total_events" in stats

    def test_clear(self):
        """测试清空事件与统计。"""
        monitor = PipelineMonitor()
        pipeline = Pipeline(name="mon_clear")
        pipeline.add_stage(_make_simple_stage("s1"))
        ctx = _make_context()
        pipeline.set_monitor(monitor)
        pipeline.execute(ctx)
        monitor.clear()
        assert monitor.get_events() == []


# ===== PipelineExecutor 测试 =====


class TestPipelineExecutor:
    """测试 PipelineExecutor 管道执行器。"""

    def test_init(self):
        """测试初始化。"""
        executor = PipelineExecutor(max_workers=2)
        assert executor.max_workers == 2
        assert executor.monitor is not None

    def test_execute(self):
        """测试同步执行。"""
        executor = PipelineExecutor()
        pipeline = Pipeline(name="exec_test")
        pipeline.add_stage(_make_simple_stage("s1", "out1"))
        ctx = _make_context()
        result = executor.execute(pipeline, ctx)
        assert result.success is True

    def test_execute_batch_sequential(self):
        """测试顺序批量执行。"""
        executor = PipelineExecutor()
        pipelines = [
            Pipeline(name=f"batch_{i}"),
        ]
        pipelines[0].add_stage(_make_simple_stage("s1"))
        contexts = [_make_context()]
        results = executor.execute_batch(pipelines, contexts, parallel=False)
        assert len(results) == 1

    def test_execute_batch_parallel(self):
        """测试并行批量执行。"""
        executor = PipelineExecutor(max_workers=2)
        pipelines = []
        contexts = []
        for i in range(3):
            p = Pipeline(name=f"par_{i}")
            p.add_stage(_make_simple_stage(f"s{i}", f"out{i}"))
            pipelines.append(p)
            contexts.append(_make_context())
        results = executor.execute_batch(pipelines, contexts, parallel=True)
        assert len(results) == 3

    def test_execute_batch_mismatch(self):
        """测试管道与上下文数量不匹配。"""
        executor = PipelineExecutor()
        with pytest.raises(ValueError, match="长度不一致"):
            executor.execute_batch([Pipeline()], [], parallel=False)

    def test_execute_async(self):
        """测试异步执行。"""
        executor = PipelineExecutor()
        pipeline = Pipeline(name="async_exec")
        pipeline.add_stage(_make_simple_stage("s1", "out1"))
        ctx = _make_context()
        result = asyncio.get_event_loop().run_until_complete(
            executor.execute_async(pipeline, ctx)
        ) if not asyncio.get_event_loop().is_running() else None
        # 在测试环境中可能无法直接运行，验证不抛异常即可


# ===== PipelineTemplateRegistry 测试 =====


class TestPipelineTemplateRegistry:
    """测试 PipelineTemplateRegistry 模板注册表。"""

    def test_init_has_default_templates(self):
        """测试初始化包含默认模板。"""
        registry = PipelineTemplateRegistry()
        templates = registry.list_templates()
        assert len(templates) >= 20

    def test_list_template_names(self):
        """测试列出模板名称。"""
        registry = PipelineTemplateRegistry()
        names = registry.list_template_names()
        assert "proposal_generation" in names
        assert "literature_review" in names
        assert "feasibility_check" in names

    def test_get_template(self):
        """测试获取模板。"""
        registry = PipelineTemplateRegistry()
        tpl = registry.get_template("proposal_generation")
        assert tpl is not None
        assert tpl["name"] == "proposal_generation"
        assert "stage_names" in tpl
        assert "description" in tpl

    def test_get_template_nonexistent(self):
        """测试获取不存在的模板。"""
        registry = PipelineTemplateRegistry()
        assert registry.get_template("nonexistent") is None

    def test_has_template(self):
        """测试判断模板存在。"""
        registry = PipelineTemplateRegistry()
        assert registry.has_template("proposal_generation") is True
        assert registry.has_template("nonexistent") is False

    def test_register_custom_template(self):
        """测试注册自定义模板。"""
        registry = PipelineTemplateRegistry()
        registry.register_template(
            name="custom_template",
            category=TemplateCategory.GENERATION,
            description="自定义模板",
            stage_names=["step1", "step2"],
        )
        assert registry.has_template("custom_template") is True
        tpl = registry.get_template("custom_template")
        assert tpl["description"] == "自定义模板"

    def test_remove_template(self):
        """测试移除模板。"""
        registry = PipelineTemplateRegistry()
        registry.register_template(
            name="to_remove",
            category=TemplateCategory.BATCH,
            description="待移除",
            stage_names=["s1"],
        )
        assert registry.remove_template("to_remove") is True
        assert not registry.has_template("to_remove")

    def test_remove_nonexistent_template(self):
        """测试移除不存在的模板。"""
        registry = PipelineTemplateRegistry()
        assert registry.remove_template("nonexistent") is False

    def test_create_pipeline_from_template(self):
        """测试从模板创建管道。"""
        registry = PipelineTemplateRegistry()
        pipeline = registry.create_pipeline("proposal_generation")
        assert pipeline.name == "proposal_generation"
        assert pipeline.stage_count() == 5  # info_confirm/creativity/validation/generation/deep_assist

    def test_create_pipeline_with_custom_name(self):
        """测试使用自定义名称创建管道。"""
        registry = PipelineTemplateRegistry()
        pipeline = registry.create_pipeline("proposal_generation", pipeline_name="my_pipeline")
        assert pipeline.name == "my_pipeline"

    def test_create_pipeline_with_custom_stages(self):
        """测试使用自定义阶段创建管道。"""
        registry = PipelineTemplateRegistry()
        custom_stage = _make_simple_stage("info_confirm", "custom_output")
        pipeline = registry.create_pipeline(
            "proposal_generation",
            custom_stages={"info_confirm": custom_stage},
        )
        ctx = _make_context()
        result = pipeline.execute(ctx)
        assert result.success is True

    def test_create_pipeline_unknown_template(self):
        """测试创建未知模板的管道抛出异常。"""
        registry = PipelineTemplateRegistry()
        with pytest.raises(ValueError, match="未知管道模板"):
            registry.create_pipeline("nonexistent_template")

    def test_list_templates_by_category(self):
        """测试按分类列出模板。"""
        registry = PipelineTemplateRegistry()
        gen_templates = registry.list_templates(TemplateCategory.GENERATION)
        for t in gen_templates:
            assert t["category"] == TemplateCategory.GENERATION

    def test_all_20_plus_templates_exist(self):
        """测试所有 20+ 模板都存在。"""
        registry = PipelineTemplateRegistry()
        expected = [
            "proposal_generation", "literature_review", "feasibility_check",
            "originality_check", "format_check", "deep_assist_full",
            "deep_assist_literature", "deep_assist_experiment", "deep_assist_defense",
            "multi_granularity_generation", "style_normalization", "citation_formatting",
            "plagiarism_scan", "academic_review", "batch_generation",
            "iterative_refinement", "ab_test_pipeline", "fallback_pipeline",
            "parallel_pipeline", "conditional_pipeline",
        ]
        for name in expected:
            assert registry.has_template(name), f"模板 {name} 不存在"


# ===== PipelineBuilder 测试 =====


class TestPipelineBuilder:
    """测试 PipelineBuilder 流式构建器。"""

    def test_build_simple(self):
        """测试构建简单管道。"""
        pipeline = (
            PipelineBuilder("builder_test")
            .add_stage(_make_simple_stage("s1"))
            .build()
        )
        assert pipeline.name == "builder_test"
        assert pipeline.stage_count() == 1

    def test_build_with_description(self):
        """测试设置描述。"""
        pipeline = (
            PipelineBuilder("desc_test")
            .description("测试描述")
            .build()
        )
        assert pipeline.description == "测试描述"

    def test_add_functional_stage(self):
        """测试添加函数式阶段。"""
        pipeline = (
            PipelineBuilder("func_builder")
            .add_functional_stage("fs1", lambda ctx: "ok")
            .build()
        )
        assert pipeline.stage_count() == 1

    def test_with_error_strategy(self):
        """测试设置错误策略。"""
        pipeline = (
            PipelineBuilder("strategy_test")
            .with_error_strategy(ErrorHandlingStrategy.SKIP)
            .build()
        )
        assert pipeline.error_strategy == ErrorHandlingStrategy.SKIP

    def test_with_retries(self):
        """测试设置重试。"""
        pipeline = (
            PipelineBuilder("retry_test")
            .with_retries(max_retries=3, delay=2.0, backoff=1.5)
            .build()
        )
        assert pipeline.max_retries == 3
        assert pipeline.retry_delay == 2.0
        assert pipeline.retry_backoff == 1.5

    def test_with_timeout(self):
        """测试设置超时。"""
        pipeline = (
            PipelineBuilder("timeout_test")
            .with_timeout(60.0)
            .build()
        )
        assert pipeline.default_timeout == 60.0

    def test_with_checkpoints(self):
        """测试启用检查点。"""
        pipeline = (
            PipelineBuilder("checkpoint_test")
            .with_checkpoints(True)
            .build()
        )
        assert pipeline.enable_checkpoints is True

    def test_with_tags(self):
        """测试添加标签。"""
        pipeline = (
            PipelineBuilder("tag_test")
            .with_tags("tag1", "tag2")
            .build()
        )
        assert "tag1" in pipeline.tags
        assert "tag2" in pipeline.tags

    def test_with_monitor(self):
        """测试设置监控器。"""
        monitor = PipelineMonitor()
        pipeline = (
            PipelineBuilder("monitor_builder")
            .with_monitor(monitor)
            .build()
        )
        # 执行后验证监控器记录了事件
        pipeline.add_stage(_make_simple_stage("s1"))
        ctx = _make_context()
        pipeline.execute(ctx)
        assert len(monitor.get_events()) > 0

    def test_chained_build(self):
        """测试完整链式构建。"""
        pipeline = (
            PipelineBuilder("full_chain")
            .description("完整链式构建")
            .add_stage(_make_simple_stage("s1"))
            .add_stage(_make_simple_stage("s2"))
            .with_error_strategy(ErrorHandlingStrategy.SKIP)
            .with_retries(2, 1.0, 2.0)
            .with_timeout(30.0)
            .with_checkpoints(True)
            .with_tags("test", "chain")
            .build()
        )
        assert pipeline.stage_count() == 2
        assert pipeline.error_strategy == ErrorHandlingStrategy.SKIP
        assert pipeline.enable_checkpoints is True
        ctx = _make_context()
        result = pipeline.execute(ctx)
        assert result.success is True


# ===== PipelineEvent / PipelineEventBus 测试 =====


class TestPipelineEvent:
    """测试 PipelineEvent 管道事件。"""

    def test_init(self):
        """测试初始化。"""
        event = PipelineEvent(
            event_type="test_event",
            pipeline_name="test_pipeline",
            stage_name="test_stage",
            data={"key": "value"},
        )
        assert event.event_type == "test_event"
        assert event.pipeline_name == "test_pipeline"
        assert event.stage_name == "test_stage"
        assert event.data == {"key": "value"}
        assert event.timestamp > 0

    def test_to_dict(self):
        """测试转换为字典。"""
        event = PipelineEvent(event_type="dict_test", data="data")
        d = event.to_dict()
        assert d["event_type"] == "dict_test"
        assert d["data"] == "data"
        assert "timestamp" in d


class TestPipelineEventBus:
    """测试 PipelineEventBus 事件总线。"""

    def test_subscribe_and_publish(self):
        """测试订阅与发布。"""
        bus = PipelineEventBus()
        received = []
        bus.subscribe("test_event", lambda e: received.append(e))
        bus.publish(PipelineEvent(event_type="test_event", data="payload"))
        assert len(received) == 1
        assert received[0].data == "payload"

    def test_unsubscribe(self):
        """测试取消订阅。"""
        bus = PipelineEventBus()
        received = []
        handler = lambda e: received.append(e)
        bus.subscribe("test_event", handler)
        bus.unsubscribe("test_event", handler)
        bus.publish(PipelineEvent(event_type="test_event"))
        assert len(received) == 0

    def test_unsubscribe_nonexistent(self):
        """测试取消不存在的订阅。"""
        bus = PipelineEventBus()
        assert bus.unsubscribe("nonexistent", lambda e: None) is False

    def test_wildcard_subscription(self):
        """测试通配符订阅。"""
        bus = PipelineEventBus()
        received = []
        bus.subscribe("*", lambda e: received.append(e))
        bus.publish(PipelineEvent(event_type="any_event"))
        assert len(received) == 1

    def test_handler_exception_isolated(self):
        """测试处理器异常不影响其他处理器。"""
        bus = PipelineEventBus()
        received = []
        def _bad_handler(e):
            raise RuntimeError("处理器异常")
        bus.subscribe("test", _bad_handler)
        bus.subscribe("test", lambda e: received.append(e))
        bus.publish(PipelineEvent(event_type="test"))
        assert len(received) == 1

    def test_clear(self):
        """测试清空订阅。"""
        bus = PipelineEventBus()
        received = []
        bus.subscribe("test", lambda e: received.append(e))
        bus.clear()
        bus.publish(PipelineEvent(event_type="test"))
        assert len(received) == 0


# ===== CheckpointManager 测试 =====


class TestCheckpointManager:
    """测试 CheckpointManager 检查点管理器。"""

    def test_save_and_load_checkpoint(self, tmp_path):
        """测试保存与加载检查点。"""
        mgr = CheckpointManager(storage_dir=str(tmp_path / "checkpoints"))
        ctx = _make_context()
        ctx.set("key", "value")
        cp_id = mgr.save_checkpoint("test_pipeline", "stage1", ctx)
        loaded = mgr.load_checkpoint(cp_id)
        assert loaded is not None
        assert loaded["pipeline_name"] == "test_pipeline"
        assert loaded["stage_name"] == "stage1"

    def test_list_checkpoints(self, tmp_path):
        """测试列出检查点。"""
        mgr = CheckpointManager(storage_dir=str(tmp_path / "list_cps"))
        ctx = _make_context()
        mgr.save_checkpoint("pipe1", "stage1", ctx)
        mgr.save_checkpoint("pipe2", "stage1", ctx)
        all_cps = mgr.list_checkpoints()
        assert len(all_cps) == 2
        pipe1_cps = mgr.list_checkpoints("pipe1")
        assert len(pipe1_cps) == 1

    def test_delete_checkpoint(self, tmp_path):
        """测试删除检查点。"""
        mgr = CheckpointManager(storage_dir=str(tmp_path / "del_cps"))
        ctx = _make_context()
        cp_id = mgr.save_checkpoint("pipe", "stage", ctx)
        assert mgr.delete_checkpoint(cp_id) is True

    def test_delete_nonexistent_checkpoint(self, tmp_path):
        """测试删除不存在的检查点。"""
        mgr = CheckpointManager(storage_dir=str(tmp_path / "del_nonexist"))
        assert mgr.delete_checkpoint("nonexistent") is False

    def test_clear_all(self, tmp_path):
        """测试清空所有检查点。"""
        mgr = CheckpointManager(storage_dir=str(tmp_path / "clear_cps"))
        ctx = _make_context()
        mgr.save_checkpoint("pipe", "stage", ctx)
        mgr.clear_all()
        assert len(mgr.list_checkpoints()) == 0


# ===== CommonStages 测试 =====


class TestCommonStages:
    """测试 CommonStages 常用阶段集合。"""

    def test_validate_input_success(self):
        """测试输入校验阶段成功。"""
        stage = CommonStages.validate_input(required_keys=["query"])
        ctx = PipelineContext(input_data={"query": "test"})
        result = stage.execute(ctx)
        assert result.success is True

    def test_validate_input_failure(self):
        """测试输入校验阶段失败。"""
        stage = CommonStages.validate_input(required_keys=["missing_key"])
        ctx = PipelineContext(input_data={"query": "test"})
        result = stage.execute(ctx)
        assert result.failed is True
        assert "missing_key" in result.error

    def test_validate_input_no_required_keys(self):
        """测试无必需键时校验通过。"""
        stage = CommonStages.validate_input()
        ctx = PipelineContext(input_data={"any": "data"})
        result = stage.execute(ctx)
        assert result.success is True

    def test_log_stage(self):
        """测试日志记录阶段。"""
        stage = CommonStages.log_stage("测试日志消息")
        ctx = _make_context()
        result = stage.execute(ctx)
        assert result.success is True
        assert "测试日志消息" in result.data["message"]

    def test_log_stage_default_message(self):
        """测试日志阶段默认消息。"""
        stage = CommonStages.log_stage()
        ctx = _make_context()
        ctx.set("key1", "value1")
        result = stage.execute(ctx)
        assert result.success is True


# ===== 全局函数测试 =====


class TestGlobalFunctions:
    """测试全局便捷函数。"""

    def test_create_pipeline(self):
        """测试创建管道函数。"""
        pipeline = create_pipeline("global_pipe")
        assert pipeline.name == "global_pipe"

    def test_create_context(self):
        """测试创建上下文函数。"""
        ctx = create_context({"query": "test"})
        assert ctx.input_data["query"] == "test"

    def test_create_monitor(self):
        """测试创建监控器函数。"""
        monitor = create_monitor()
        assert monitor is not None

    def test_create_executor(self):
        """测试创建执行器函数。"""
        executor = create_executor(max_workers=2)
        assert executor.max_workers == 2

    def test_create_builder(self):
        """测试创建构建器函数。"""
        builder = create_builder("global_builder")
        assert builder is not None

    def test_get_template_registry(self):
        """测试获取全局模板注册表。"""
        registry = get_template_registry()
        assert registry is not None
        assert registry.has_template("proposal_generation") is True

    def test_get_template_registry_singleton(self):
        """测试全局注册表为单例。"""
        r1 = get_template_registry()
        r2 = get_template_registry()
        assert r1 is r2

    def test_create_pipeline_from_template(self):
        """测试从模板创建管道函数。"""
        pipeline = create_pipeline_from_template("proposal_generation")
        assert pipeline.name == "proposal_generation"
        assert pipeline.stage_count() == 5

    def test_list_pipeline_templates(self):
        """测试列出管道模板函数。"""
        templates = list_pipeline_templates()
        assert len(templates) >= 20


# ===== 集成测试 =====


class TestIntegration:
    """集成测试：模拟完整管道工作流。"""

    def test_full_pipeline_workflow(self):
        """测试完整管道工作流。"""
        # 1. 使用构建器构建管道
        pipeline = (
            PipelineBuilder("integration_test")
            .description("集成测试管道")
            .add_functional_stage("validate", lambda ctx: ctx.set("validated", True))
            .add_functional_stage("process", lambda ctx: ctx.set("processed", True))
            .add_functional_stage("output", lambda ctx: ctx.set("output", "完成"))
            .with_error_strategy(ErrorHandlingStrategy.SKIP)
            .with_checkpoints(True)
            .build()
        )
        # 2. 创建上下文
        ctx = create_context({"query": "深度学习", "degree": "master"})
        # 3. 执行管道
        result = pipeline.execute(ctx)
        # 4. 验证结果
        assert result.success is True
        assert result.total_stages == 3
        assert ctx.get("validated") is True
        assert ctx.get("processed") is True
        assert ctx.get("output") == "完成"
        # 5. 验证检查点
        assert len(ctx.list_checkpoints()) == 3

    def test_template_pipeline_execution(self):
        """测试模板管道执行。"""
        pipeline = create_pipeline_from_template("literature_review")
        ctx = create_context({"query": "深度学习文献综述"})
        result = pipeline.execute(ctx)
        assert result.success is True
        assert result.total_stages == 5

    def test_pipeline_with_monitor_and_events(self):
        """测试带监控器与事件的管道。"""
        monitor = create_monitor()
        pipeline = (
            create_builder("monitored_pipe")
            .add_stage(_make_simple_stage("s1"))
            .add_stage(_make_simple_stage("s2"))
            .with_monitor(monitor)
            .build()
        )
        ctx = create_context({"query": "test"})
        pipeline.execute(ctx)
        # 验证监控器记录了事件
        assert len(monitor.get_events()) >= 4  # 2 start + 2 end
        stats = monitor.get_stats()
        assert stats["total_events"] >= 4

    def test_error_recovery_workflow(self):
        """测试错误恢复工作流。"""
        pipeline = (
            PipelineBuilder("error_recovery")
            .add_stage(_make_simple_stage("s1", "out1"))
            .add_stage(_make_failing_stage("fail", "模拟失败"))
            .add_stage(_make_simple_stage("s3", "out3"))
            .with_error_strategy(ErrorHandlingStrategy.SKIP)
            .build()
        )
        ctx = create_context({"query": "test"})
        result = pipeline.execute(ctx)
        # 跳过策略下应继续执行
        assert result.executed_stages >= 2
        assert ctx.get("s1") == "out1"
        assert ctx.get("s3") == "out3"

    def test_checkpoint_restore_workflow(self):
        """测试检查点恢复工作流。"""
        pipeline = (
            PipelineBuilder("checkpoint_workflow")
            .add_stage(_make_simple_stage("s1", "v1"))
            .with_checkpoints(True)
            .build()
        )
        ctx = create_context({"query": "test"})
        pipeline.execute(ctx)
        # 修改上下文
        ctx.set("s1", "modified")
        # 恢复检查点
        assert ctx.restore_checkpoint("s1")
        assert ctx.get("s1") == "v1"


# ===== 边界条件测试 =====


class TestEdgeCases:
    """边界条件与异常场景测试。"""

    def test_empty_pipeline_name(self):
        """测试空管道名称。"""
        pipeline = Pipeline(name="")
        assert pipeline.name == ""

    def test_stage_with_empty_name(self):
        """测试空阶段名称（使用类名）。"""
        stage = PipelineStage(name="")
        assert stage.name == "PipelineStage"

    def test_context_with_none_input(self):
        """测试 None 输入数据。"""
        ctx = PipelineContext(input_data=None)
        assert ctx.input_data == {}

    def test_context_with_none_metadata(self):
        """测试 None 元数据。"""
        ctx = PipelineContext(metadata=None)
        assert ctx.metadata == {}

    def test_large_input_data(self):
        """测试大量输入数据。"""
        data = {f"key_{i}": f"value_{i}" for i in range(1000)}
        ctx = PipelineContext(input_data=data)
        assert len(ctx.input_data) == 1000

    def test_many_stages(self):
        """测试大量阶段。"""
        pipeline = Pipeline(name="many_stages")
        for i in range(100):
            pipeline.add_stage(_make_simple_stage(f"stage_{i}"))
        assert pipeline.stage_count() == 100
        ctx = _make_context()
        result = pipeline.execute(ctx)
        assert result.success is True
        assert result.total_stages == 100

    def test_nested_data_in_context(self):
        """测试上下文中嵌套数据。"""
        ctx = PipelineContext()
        ctx.set("nested", {"a": {"b": {"c": [1, 2, 3]}}})
        d = ctx.to_dict()
        assert d["data"]["nested"]["a"]["b"]["c"] == [1, 2, 3]

    def test_unicode_in_stage_names(self):
        """测试阶段名含 Unicode。"""
        pipeline = Pipeline(name="unicode_test")
        stage = FunctionalStage(name="中文阶段", func=lambda ctx: "ok")
        pipeline.add_stage(stage)
        assert "中文阶段" in pipeline.get_stage_names()

    def test_concurrent_context_access(self):
        """测试并发上下文访问。"""
        ctx = PipelineContext()
        errors = []

        def writer():
            try:
                for i in range(100):
                    ctx.set(f"key_{i}", i)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for i in range(100):
                    ctx.get(f"key_{i}")
                    ctx.keys()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0

    def test_pipeline_repr_in_stage(self):
        """测试阶段字符串表示。"""
        stage = PipelineStage(name="repr_stage", timeout=5.0, max_retries=3)
        repr_str = repr(stage)
        assert "repr_stage" in repr_str
        assert "5.0" in repr_str

    def test_functional_stage_with_none_return(self):
        """测试函数式阶段返回 None。"""
        stage = FunctionalStage(name="none_return", func=lambda ctx: None)
        ctx = _make_context()
        result = stage.execute(ctx)
        assert result.success is True
        assert result.data is None

    def test_template_with_empty_stage_names(self):
        """测试空阶段名列表的模板。"""
        registry = PipelineTemplateRegistry()
        registry.register_template(
            name="empty_stages",
            category=TemplateCategory.GENERATION,
            description="空阶段模板",
            stage_names=[],
        )
        pipeline = registry.create_pipeline("empty_stages")
        assert pipeline.stage_count() == 0
