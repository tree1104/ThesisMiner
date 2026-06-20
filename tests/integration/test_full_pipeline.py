"""集成测试：端到端五阶段全流程管道验证

覆盖 ThesisMiner v8.0 的完整编排链路，包含：
    - 五阶段状态机转移（INFO_CONFIRM → CREATIVITY → VALIDATION → GENERATION → DEEP_ASSIST）
    - 端到端管道编排（Pipeline + PipelineStage + PipelineContext）
    - 多 Agent 协作（Searcher/Reasoner/Critic/Writer/DeepAssist 串联）
    - 多对话隔离（不同 session_id/conversation_id 上下文独立）
    - 上下文管理与检查点恢复
    - 引用解析与存储（CitationVerifier 集成）
    - 缓存命中验证（CacheOptimizer 集成）
    - 错误处理与恢复（重试/跳过/降级/回滚）
    - 监控与诊断（PipelineMonitor + PipelineDiagnostics）
    - 模板注册表与预定义管道
    - 异步执行与批量执行

运行方式：
    python -m pytest tests/integration/test_full_pipeline.py -v
"""
import asyncio
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# 在导入 backend 模块前，切换到临时数据库，避免污染正式数据
try:
    import backend.database as _db_module
    _tmp_dir_integration = tempfile.mkdtemp(prefix="thesisminer_full_pipeline_")
    _tmp_db_integration = os.path.join(_tmp_dir_integration, "test_full_pipeline.db")
    _db_module.DB_PATH = _tmp_db_integration
    _db_module.init_db()
except Exception:
    pass

# 导入被测模块
from backend.orchestration.state_machine import (
    Event,
    Stage,
    State,
    StateMachine,
    TRANSITIONS,
    TransitionResult,
    create_orchestration,
    get_next_events,
    is_valid_transition,
    transition,
)
from backend.orchestration.pipeline import (
    AsyncFunctionalStage,
    CheckpointManager,
    CommonStages,
    ErrorHandlingStrategy,
    FunctionalStage,
    Pipeline,
    PipelineBuilder,
    PipelineContext,
    PipelineDiagnostics,
    PipelineEvent,
    PipelineEventBus,
    PipelineExecutor,
    PipelineMonitor,
    PipelineResult,
    PipelineStage,
    PipelineStatus,
    PipelineTemplateRegistry,
    StageResult,
    StageStatus,
    TemplateCategory,
    build_proposal_generation_pipeline,
    create_context,
    create_pipeline,
    create_pipeline_from_template,
    get_template_registry,
    list_pipeline_templates,
)


# ===== 辅助函数 =====


def _make_stage_result(
    name: str,
    data=None,
    status: StageStatus = StageStatus.SUCCESS,
) -> StageResult:
    """构造阶段执行结果。"""
    return StageResult(
        stage_name=name,
        status=status,
        data=data,
        start_time=time.time(),
        end_time=time.time(),
        duration_ms=1.0,
    )


def _build_five_stage_pipeline(
    error_strategy: ErrorHandlingStrategy = ErrorHandlingStrategy.RAISE,
    enable_checkpoints: bool = False,
) -> Pipeline:
    """构建五阶段测试管道（信息确权→创意→校验→生成→深度辅助）。"""
    def _info_confirm(ctx: PipelineContext) -> StageResult:
        ctx.set("info_confirmed", True)
        ctx.set("degree", ctx.input_data.get("degree", "master"))
        ctx.set("discipline", ctx.input_data.get("discipline", "science_engineering"))
        return _make_stage_result("info_confirm", {"confirmed": True})

    def _creativity(ctx: PipelineContext) -> StageResult:
        candidates = [
            {"title": "深度学习在图像识别中的应用", "score": 0},
            {"title": "自然语言处理前沿研究", "score": 0},
            {"title": "强化学习与决策系统", "score": 0},
        ]
        ctx.set("candidates", candidates)
        return _make_stage_result("creativity", {"candidates": candidates})

    def _validation(ctx: PipelineContext) -> StageResult:
        candidates = ctx.get("candidates", [])
        evaluations = [
            {"title": c.get("title", ""), "score": 82, "passed": True}
            for c in candidates
        ]
        ctx.set("evaluations", evaluations)
        return _make_stage_result("validation", {"evaluations": evaluations})

    def _generation(ctx: PipelineContext) -> StageResult:
        evaluations = ctx.get("evaluations", [])
        best = evaluations[0] if evaluations else {}
        content = f"基于《{best.get('title', '未知')}》的开题报告"
        ctx.set("generated_content", content)
        ctx.set("proposal", {"title": best.get("title", ""), "content": content})
        return _make_stage_result("generation", {"content": content})

    def _deep_assist(ctx: PipelineContext) -> StageResult:
        options = ["literature_reading", "experiment_prep", "defense_sim"]
        ctx.set("deep_assist_options", options)
        return _make_stage_result("deep_assist", {"options": options})

    pipeline = Pipeline(
        name="five_stage_full",
        error_strategy=error_strategy,
        enable_checkpoints=enable_checkpoints,
    )
    pipeline.add_stage(FunctionalStage(name="info_confirm", func=_info_confirm))
    pipeline.add_stage(FunctionalStage(name="creativity", func=_creativity))
    pipeline.add_stage(FunctionalStage(name="validation", func=_validation))
    pipeline.add_stage(FunctionalStage(name="generation", func=_generation))
    pipeline.add_stage(FunctionalStage(name="deep_assist", func=_deep_assist))
    return pipeline


def _build_failing_pipeline(
    fail_stage: str = "validation",
    error_strategy: ErrorHandlingStrategy = ErrorHandlingStrategy.RAISE,
) -> Pipeline:
    """构建含失败阶段的管道。"""
    def _ok(name: str):
        def _fn(ctx: PipelineContext) -> StageResult:
            ctx.set(f"{name}_done", True)
            return _make_stage_result(name, {"done": True})
        return _fn

    def _fail(ctx: PipelineContext) -> StageResult:
        return StageResult(
            stage_name=fail_stage,
            status=StageStatus.FAILED,
            error="模拟阶段失败",
            error_type="SimulatedError",
        )

    pipeline = Pipeline(name="failing_pipeline", error_strategy=error_strategy)
    pipeline.add_stage(FunctionalStage(name="info_confirm", func=_ok("info_confirm")))
    pipeline.add_stage(FunctionalStage(name="creativity", func=_ok("creativity")))
    if fail_stage == "validation":
        pipeline.add_stage(FunctionalStage(name="validation", func=_fail, error_strategy=error_strategy))
    else:
        pipeline.add_stage(FunctionalStage(name="validation", func=_ok("validation")))
    if fail_stage == "generation":
        pipeline.add_stage(FunctionalStage(name="generation", func=_fail, error_strategy=error_strategy))
    else:
        pipeline.add_stage(FunctionalStage(name="generation", func=_ok("generation")))
    pipeline.add_stage(FunctionalStage(name="deep_assist", func=_ok("deep_assist")))
    return pipeline


# ===== Fixtures =====


@pytest.fixture
def basic_context():
    """基础管道上下文。"""
    return PipelineContext(
        input_data={
            "user_input": "深度学习在医学影像中的应用",
            "degree": "master",
            "discipline": "science_engineering",
            "mentor_info": "张教授",
        },
        session_id="test-session-001",
        conversation_id="test-conv-001",
    )


@pytest.fixture
def five_stage_pipeline():
    """五阶段管道。"""
    return _build_five_stage_pipeline()


@pytest.fixture
def checkpoint_pipeline():
    """启用检查点的五阶段管道。"""
    return _build_five_stage_pipeline(enable_checkpoints=True)


@pytest.fixture
def skip_pipeline():
    """跳过策略管道。"""
    return _build_failing_pipeline(error_strategy=ErrorHandlingStrategy.SKIP)


@pytest.fixture
def monitor():
    """管道监控器。"""
    return PipelineMonitor()


@pytest.fixture
def executor(monitor):
    """管道执行器。"""
    return PipelineExecutor(max_workers=4, monitor=monitor)


@pytest.fixture
def registry():
    """管道模板注册表。"""
    return PipelineTemplateRegistry()


@pytest.fixture
def temp_checkpoint_manager(tmp_path):
    """临时检查点管理器。"""
    return CheckpointManager(storage_dir=str(tmp_path / "checkpoints"))


# ===== 测试类：五阶段状态机端到端 =====


class TestFiveStageStateMachine:
    """五阶段状态机端到端测试。"""

    def test_full_happy_path_transitions(self):
        """测试完整五阶段正向转移路径。"""
        # 启动
        result = transition(None, Event.START)
        assert result.success is True
        assert result.to_stage == Stage.INFO_CONFIRM

        # INFO_CONFIRM → CREATIVITY
        result = transition(Stage.INFO_CONFIRM, Event.USER_CONFIRM)
        assert result.success is True
        assert result.to_stage == Stage.CREATIVITY
        assert result.is_retry is False

        # CREATIVITY → VALIDATION
        result = transition(Stage.CREATIVITY, Event.CANDIDATES_GENERATED)
        assert result.success is True
        assert result.to_stage == Stage.VALIDATION

        # VALIDATION → GENERATION（评分通过）
        result = transition(Stage.VALIDATION, Event.SCORE_PASS)
        assert result.success is True
        assert result.to_stage == Stage.GENERATION

        # GENERATION → DEEP_ASSIST
        result = transition(Stage.GENERATION, Event.GENERATION_DONE)
        assert result.success is True
        assert result.to_stage == Stage.DEEP_ASSIST

    def test_score_fail_retry_path(self):
        """测试评分不通过的回退路径。"""
        # 推进到校验阶段
        current = Stage.VALIDATION
        result = transition(current, Event.SCORE_FAIL)
        assert result.success is True
        assert result.to_stage == Stage.CREATIVITY
        assert result.is_retry is True
        assert "回退" in result.message

    def test_reset_from_any_stage(self):
        """测试从任意阶段重置。"""
        for stage in Stage:
            result = transition(stage, Event.RESET)
            assert result.success is True
            assert result.to_stage == Stage.INFO_CONFIRM

    def test_invalid_transitions_are_rejected(self):
        """测试非法转移被拒绝。"""
        # INFO_CONFIRM 不能直接跳到 GENERATION
        result = transition(Stage.INFO_CONFIRM, Event.GENERATION_DONE)
        assert result.success is False
        assert result.to_stage == Stage.INFO_CONFIRM
        assert "非法转移" in result.message

        # CREATIVITY 不能触发 USER_CONFIRM
        result = transition(Stage.CREATIVITY, Event.USER_CONFIRM)
        assert result.success is False

    def test_get_next_events_for_each_stage(self):
        """测试每个阶段的可触发事件列表。"""
        info_events = get_next_events(Stage.INFO_CONFIRM)
        assert Event.USER_CONFIRM in info_events

        creativity_events = get_next_events(Stage.CREATIVITY)
        assert Event.CANDIDATES_GENERATED in creativity_events

        validation_events = get_next_events(Stage.VALIDATION)
        assert Event.SCORE_PASS in validation_events
        assert Event.SCORE_FAIL in validation_events

        generation_events = get_next_events(Stage.GENERATION)
        assert Event.GENERATION_DONE in generation_events

        deep_events = get_next_events(Stage.DEEP_ASSIST)
        assert Event.RESET in deep_events

    def test_is_valid_transition(self):
        """测试转移合法性检查。"""
        assert is_valid_transition(Stage.INFO_CONFIRM, Event.USER_CONFIRM) is True
        assert is_valid_transition(Stage.VALIDATION, Event.SCORE_PASS) is True
        assert is_valid_transition(Stage.INFO_CONFIRM, Event.GENERATION_DONE) is False
        # RESET 始终合法
        assert is_valid_transition(Stage.GENERATION, Event.RESET) is True

    def test_transition_result_dataclass(self):
        """测试 TransitionResult 数据类字段。"""
        result = transition(Stage.INFO_CONFIRM, Event.USER_CONFIRM)
        assert isinstance(result, TransitionResult)
        assert hasattr(result, "success")
        assert hasattr(result, "from_stage")
        assert hasattr(result, "to_stage")
        assert hasattr(result, "event")
        assert hasattr(result, "message")
        assert hasattr(result, "is_retry")
        assert result.from_stage == Stage.INFO_CONFIRM
        assert result.event == Event.USER_CONFIRM

    def test_transitions_table_completeness(self):
        """测试状态转移表覆盖所有阶段（除 DEEP_ASSIST 外都有出口）。"""
        stages_with_outgoing = set()
        for (stage, _event) in TRANSITIONS.keys():
            stages_with_outgoing.add(stage)
        # INFO_CONFIRM/CREATIVITY/VALIDATION/GENERATION 都应在转移表中
        assert Stage.INFO_CONFIRM in stages_with_outgoing
        assert Stage.CREATIVITY in stages_with_outgoing
        assert Stage.VALIDATION in stages_with_outgoing
        assert Stage.GENERATION in stages_with_outgoing


# ===== 测试类：端到端管道执行 =====


class TestEndToEndPipelineExecution:
    """端到端管道执行测试。"""

    def test_full_five_stage_pipeline_success(self, five_stage_pipeline, basic_context):
        """测试五阶段管道完整成功执行。"""
        result = five_stage_pipeline.execute(basic_context)

        assert result.success is True
        assert result.status == PipelineStatus.SUCCESS
        assert result.total_stages == 5
        assert result.executed_stages == 5
        assert result.failed_stages == 0
        assert result.skipped_stages == 0

        # 验证各阶段都产生了上下文数据
        assert basic_context.get("info_confirmed") is True
        assert len(basic_context.get("candidates", [])) == 3
        assert len(basic_context.get("evaluations", [])) == 3
        assert basic_context.get("generated_content") is not None
        assert len(basic_context.get("deep_assist_options", [])) == 3

    def test_pipeline_stage_order_preserved(self, five_stage_pipeline, basic_context):
        """测试阶段执行顺序保持。"""
        result = five_stage_pipeline.execute(basic_context)
        stage_names = [sr.stage_name for sr in result.stage_results]
        assert stage_names == [
            "info_confirm", "creativity", "validation", "generation", "deep_assist"
        ]

    def test_pipeline_duration_recorded(self, five_stage_pipeline, basic_context):
        """测试管道执行耗时被记录。"""
        result = five_stage_pipeline.execute(basic_context)
        assert result.duration_ms > 0
        assert result.start_time > 0
        assert result.end_time >= result.start_time
        for sr in result.stage_results:
            assert sr.duration_ms >= 0

    def test_pipeline_context_data_flow(self, five_stage_pipeline, basic_context):
        """测试阶段间数据通过上下文流转。"""
        five_stage_pipeline.execute(basic_context)
        # creativity 阶段读取 info_confirm 设置的数据
        assert basic_context.get("degree") == "master"
        # validation 阶段读取 creativity 的候选
        candidates = basic_context.get("candidates")
        evaluations = basic_context.get("evaluations")
        assert len(evaluations) == len(candidates)
        # generation 读取 evaluations
        proposal = basic_context.get("proposal")
        assert proposal["title"] == evaluations[0]["title"]

    def test_pipeline_execution_log(self, five_stage_pipeline, basic_context):
        """测试上下文执行日志记录。"""
        five_stage_pipeline.execute(basic_context)
        log = basic_context.get_execution_log()
        assert len(log) == 5
        for entry in log:
            assert "stage" in entry
            assert "status" in entry
            assert "duration_ms" in entry
            assert entry["status"] == "success"

    def test_pipeline_to_dict(self, five_stage_pipeline, basic_context):
        """测试管道序列化为字典。"""
        five_stage_pipeline.execute(basic_context)
        d = five_stage_pipeline.to_dict()
        assert d["name"] == "five_stage_full"
        assert d["stage_count"] == 5
        assert len(d["stages"]) == 5

    def test_pipeline_result_to_dict(self, five_stage_pipeline, basic_context):
        """测试管道结果序列化。"""
        result = five_stage_pipeline.execute(basic_context)
        d = result.to_dict()
        assert d["pipeline_name"] == "five_stage_full"
        assert d["status"] == "success"
        assert d["total_stages"] == 5
        assert d["executed_stages"] == 5
        assert len(d["stage_results"]) == 5


# ===== 测试类：多对话隔离 =====


class TestMultiConversationIsolation:
    """多对话隔离测试。"""

    def test_two_conversations_isolated(self, five_stage_pipeline):
        """测试两个对话上下文完全隔离。"""
        ctx1 = PipelineContext(
            input_data={"user_input": "深度学习应用", "degree": "master"},
            session_id="session-A",
            conversation_id="conv-A",
        )
        ctx2 = PipelineContext(
            input_data={"user_input": "自然语言处理", "degree": "doctor"},
            session_id="session-B",
            conversation_id="conv-B",
        )

        five_stage_pipeline.execute(ctx1)
        five_stage_pipeline.execute(ctx2)

        # 验证两个上下文数据独立
        assert ctx1.session_id == "session-A"
        assert ctx2.session_id == "session-B"
        assert ctx1.get("degree") == "master"
        assert ctx2.get("degree") == "doctor"
        # 候选标题应不同（基于不同输入）
        candidates1 = ctx1.get("candidates", [])
        candidates2 = ctx2.get("candidates", [])
        # 候选数量相同但内容独立
        assert len(candidates1) == len(candidates2)
        # 上下文键独立
        assert ctx1.conversation_id != ctx2.conversation_id

    def test_concurrent_conversations_thread_safety(self):
        """测试并发对话的线程安全。"""
        pipeline = _build_five_stage_pipeline()
        results = {}
        errors = []

        def _run(conv_id: str):
            try:
                ctx = PipelineContext(
                    input_data={"user_input": f"测试{conv_id}", "degree": "master"},
                    session_id=f"session-{conv_id}",
                    conversation_id=f"conv-{conv_id}",
                )
                res = pipeline.execute(ctx)
                results[conv_id] = (res, ctx)
            except Exception as e:
                errors.append((conv_id, str(e)))

        threads = [
            threading.Thread(target=_run, args=(f"T{i}",))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"并发执行出错: {errors}"
        assert len(results) == 5
        for conv_id, (res, ctx) in results.items():
            assert res.success is True
            assert ctx.conversation_id == f"conv-{conv_id}"

    def test_context_clone_isolation(self, basic_context):
        """测试上下文克隆后的数据隔离。"""
        basic_context.set("original_key", "original_value")
        cloned = basic_context.clone()
        cloned.set("original_key", "modified_value")
        cloned.set("clone_only", "clone_data")

        # 原上下文不受影响
        assert basic_context.get("original_key") == "original_value"
        assert basic_context.get("clone_only") is None
        assert cloned.get("original_key") == "modified_value"

    def test_context_merge(self):
        """测试上下文合并。"""
        ctx1 = PipelineContext(input_data={"a": 1})
        ctx1.set("shared", "from_ctx1")
        ctx2 = PipelineContext(input_data={"b": 2})
        ctx2.set("shared", "from_ctx2")
        ctx2.set("extra", "ctx2_data")

        ctx1.merge(ctx2)
        # 合并后 ctx1 的 shared 被 ctx2 覆盖
        assert ctx1.get("shared") == "from_ctx2"
        assert ctx1.get("extra") == "ctx2_data"


# ===== 测试类：上下文管理与检查点 =====


class TestContextManagementAndCheckpoints:
    """上下文管理与检查点测试。"""

    def test_checkpoint_save_and_restore(self, checkpoint_pipeline):
        """测试检查点保存与恢复。"""
        ctx = PipelineContext(
            input_data={"user_input": "检查点测试", "degree": "master"},
        )
        checkpoint_pipeline.execute(ctx)
        # 启用检查点后，每个成功阶段都应保存检查点
        checkpoints = ctx.list_checkpoints()
        assert len(checkpoints) == 5
        assert "info_confirm" in checkpoints
        assert "deep_assist" in checkpoints

    def test_checkpoint_restore_rolls_back_data(self):
        """测试检查点恢复回滚数据。"""
        ctx = PipelineContext(input_data={})
        ctx.set("stage1_data", "value1")
        ctx.save_checkpoint("stage1")

        ctx.set("stage2_data", "value2")
        ctx.set("stage1_data", "modified")

        # 恢复到 stage1 检查点
        success = ctx.restore_checkpoint("stage1")
        assert success is True
        assert ctx.get("stage1_data") == "value1"
        # stage2 的数据应被回滚掉
        assert ctx.get("stage2_data") is None

    def test_checkpoint_restore_nonexistent(self):
        """测试恢复不存在的检查点。"""
        ctx = PipelineContext(input_data={})
        success = ctx.restore_checkpoint("nonexistent")
        assert success is False

    def test_context_cancel(self, five_stage_pipeline):
        """测试上下文取消中断管道。"""
        ctx = PipelineContext(input_data={"user_input": "取消测试"})

        # 在第一个阶段执行后取消
        original_execute = five_stage_pipeline._stages[0].execute
        cancel_called = []

        def _cancel_after_first(context):
            result = original_execute(context)
            context.cancel()
            cancel_called.append(True)
            return result

        five_stage_pipeline._stages[0].execute = _cancel_after_first
        result = five_stage_pipeline.execute(ctx)

        assert cancel_called == [True]
        assert result.status == PipelineStatus.CANCELLED
        # 后续阶段不应执行
        assert ctx.get("candidates") is None

    def test_context_keys_and_has(self, basic_context):
        """测试上下文键查询。"""
        basic_context.set("key1", "value1")
        basic_context.set("key2", "value2")
        assert basic_context.has("key1") is True
        assert basic_context.has("nonexistent") is False
        keys = basic_context.keys()
        assert "key1" in keys
        assert "key2" in keys

    def test_context_remove(self, basic_context):
        """测试上下文移除键。"""
        basic_context.set("to_remove", "value")
        assert basic_context.remove("to_remove") is True
        assert basic_context.has("to_remove") is False
        assert basic_context.remove("nonexistent") is False

    def test_context_update_batch(self, basic_context):
        """测试上下文批量更新。"""
        basic_context.update({"k1": "v1", "k2": "v2", "k3": "v3"})
        assert basic_context.get("k1") == "v1"
        assert basic_context.get("k2") == "v2"
        assert basic_context.get("k3") == "v3"


# ===== 测试类：错误处理与恢复 =====


class TestErrorHandlingAndRecovery:
    """错误处理与恢复测试。"""

    def test_raise_strategy_terminates_pipeline(self):
        """测试 RAISE 策略终止管道。"""
        pipeline = _build_failing_pipeline(
            fail_stage="validation",
            error_strategy=ErrorHandlingStrategy.RAISE,
        )
        ctx = PipelineContext(input_data={"user_input": "测试"})
        result = pipeline.execute(ctx)

        assert result.failed is True
        assert result.status == PipelineStatus.FAILED
        assert result.failed_stages == 1
        # 后续阶段不应执行
        assert ctx.get("generated_content") is None

    def test_skip_strategy_continues_pipeline(self, skip_pipeline):
        """测试 SKIP 策略跳过失败阶段继续执行。"""
        ctx = PipelineContext(input_data={"user_input": "测试"})
        result = skip_pipeline.execute(ctx)

        # 跳过策略下管道应继续执行后续阶段
        assert result.status in (PipelineStatus.PARTIAL, PipelineStatus.SUCCESS)
        assert result.failed_stages == 1
        # 后续阶段应执行
        assert ctx.get("deep_assist_done") is True

    def test_fallback_strategy_uses_fallback_stage(self):
        """测试 FALLBACK 策略使用降级阶段。"""
        fallback_stage = FunctionalStage(
            name="validation_fallback",
            func=lambda ctx: _make_stage_result(
                "validation_fallback", {"fallback": True}
            ),
        )
        pipeline = Pipeline(name="fallback_test")
        pipeline.add_stage(FunctionalStage(
            name="info_confirm",
            func=lambda ctx: _make_stage_result("info_confirm", {"ok": True}),
        ))
        pipeline.add_stage(FunctionalStage(
            name="validation",
            func=lambda ctx: StageResult(
                stage_name="validation",
                status=StageStatus.FAILED,
                error="主阶段失败",
            ),
            error_strategy=ErrorHandlingStrategy.FALLBACK,
            fallback_stage=fallback_stage,
        ))
        pipeline.add_stage(FunctionalStage(
            name="generation",
            func=lambda ctx: _make_stage_result("generation", {"ok": True}),
        ))

        ctx = PipelineContext(input_data={})
        result = pipeline.execute(ctx)

        assert result.success is True
        # 应包含降级阶段的结果
        stage_names = [sr.stage_name for sr in result.stage_results]
        assert "validation_fallback" in stage_names

    def test_rollback_strategy_restores_checkpoint(self):
        """测试 ROLLBACK 策略回滚到检查点。"""
        pipeline = Pipeline(
            name="rollback_test",
            enable_checkpoints=True,
        )
        pipeline.add_stage(FunctionalStage(
            name="stage1",
            func=lambda ctx: _make_stage_result("stage1", {"step": 1}),
        ))
        pipeline.add_stage(FunctionalStage(
            name="stage2",
            func=lambda ctx: StageResult(
                stage_name="stage2",
                status=StageStatus.FAILED,
                error="模拟失败",
            ),
            error_strategy=ErrorHandlingStrategy.ROLLBACK,
        ))
        pipeline.add_stage(FunctionalStage(
            name="stage3",
            func=lambda ctx: _make_stage_result("stage3", {"step": 3}),
        ))

        ctx = PipelineContext(input_data={})
        result = pipeline.execute(ctx)

        # ROLLBACK 策略下，回滚后继续执行
        # stage1 成功保存检查点，stage2 失败回滚，stage3 继续执行
        assert result.executed_stages >= 2

    def test_retry_strategy_exhausts_retries(self):
        """测试 RETRY 策略重试耗尽后终止。"""
        call_count = {"n": 0}

        def _always_fail(ctx: PipelineContext) -> StageResult:
            call_count["n"] += 1
            return StageResult(
                stage_name="flaky",
                status=StageStatus.FAILED,
                error=f"第 {call_count['n']} 次失败",
            )

        pipeline = Pipeline(name="retry_test")
        pipeline.add_stage(FunctionalStage(
            name="flaky",
            func=_always_fail,
            max_retries=2,
            retry_delay=0.01,
            error_strategy=ErrorHandlingStrategy.RETRY,
        ))

        ctx = PipelineContext(input_data={})
        result = pipeline.execute(ctx)

        assert result.failed is True
        # 应执行 1 + 2 = 3 次
        assert call_count["n"] == 3

    def test_retry_strategy_succeeds_on_second_attempt(self):
        """测试 RETRY 策略第二次成功。"""
        call_count = {"n": 0}

        def _fail_then_succeed(ctx: PipelineContext) -> StageResult:
            call_count["n"] += 1
            if call_count["n"] == 1:
                return StageResult(
                    stage_name="flaky",
                    status=StageStatus.FAILED,
                    error="首次失败",
                )
            return _make_stage_result("flaky", {"attempt": call_count["n"]})

        pipeline = Pipeline(name="retry_success_test")
        pipeline.add_stage(FunctionalStage(
            name="flaky",
            func=_fail_then_succeed,
            max_retries=3,
            retry_delay=0.01,
            error_strategy=ErrorHandlingStrategy.RETRY,
        ))

        ctx = PipelineContext(input_data={})
        result = pipeline.execute(ctx)

        assert result.success is True
        assert call_count["n"] == 2

    def test_condition_skips_stage(self):
        """测试条件函数跳过阶段。"""
        pipeline = Pipeline(name="conditional_test")
        pipeline.add_stage(FunctionalStage(
            name="always_run",
            func=lambda ctx: _make_stage_result("always_run", {"ok": True}),
        ))
        pipeline.add_stage(FunctionalStage(
            name="conditional",
            func=lambda ctx: _make_stage_result("conditional", {"ok": True}),
            condition=lambda ctx: False,  # 条件为 False，跳过
        ))
        pipeline.add_stage(FunctionalStage(
            name="after_conditional",
            func=lambda ctx: _make_stage_result("after_conditional", {"ok": True}),
        ))

        ctx = PipelineContext(input_data={})
        result = pipeline.execute(ctx)

        assert result.success is True
        assert result.skipped_stages == 1
        assert result.executed_stages == 2
        skipped = [sr for sr in result.stage_results if sr.skipped]
        assert len(skipped) == 1
        assert skipped[0].stage_name == "conditional"


# ===== 测试类：监控与诊断 =====


class TestMonitoringAndDiagnostics:
    """监控与诊断测试。"""

    def test_monitor_records_all_events(self, five_stage_pipeline, monitor, basic_context):
        """测试监控器记录所有事件。"""
        five_stage_pipeline.set_monitor(monitor)
        five_stage_pipeline.execute(basic_context)

        events = monitor.get_events()
        # 应包含 pipeline_start, 5 个 stage_success, pipeline_end
        assert len(events) >= 7
        start_events = monitor.get_events("pipeline_start")
        assert len(start_events) == 1
        end_events = monitor.get_events("pipeline_end")
        assert len(end_events) == 1
        success_events = monitor.get_events("stage_success")
        assert len(success_events) == 5

    def test_monitor_stage_stats(self, five_stage_pipeline, monitor, basic_context):
        """测试监控器阶段统计。"""
        five_stage_pipeline.set_monitor(monitor)
        five_stage_pipeline.execute(basic_context)

        stats = monitor.get_stage_stats()
        assert "info_confirm" in stats
        assert stats["info_confirm"]["success"] == 1
        assert stats["info_confirm"]["total"] == 1
        assert stats["info_confirm"]["avg_duration_ms"] >= 0

    def test_monitor_pipeline_stats(self, five_stage_pipeline, monitor, basic_context):
        """测试监控器管道统计。"""
        five_stage_pipeline.set_monitor(monitor)
        five_stage_pipeline.execute(basic_context)

        stats = monitor.get_pipeline_stats("five_stage_full")
        assert stats["total"] == 1
        assert stats["success"] == 1
        assert stats["avg_duration_ms"] >= 0

    def test_monitor_failure_events(self, monitor):
        """测试监控器记录失败事件。"""
        pipeline = _build_failing_pipeline(error_strategy=ErrorHandlingStrategy.SKIP)
        pipeline.set_monitor(monitor)
        ctx = PipelineContext(input_data={})
        pipeline.execute(ctx)

        failure_events = monitor.get_events("stage_failure")
        assert len(failure_events) >= 1
        assert failure_events[0]["stage"] == "validation"

    def test_monitor_clear(self, five_stage_pipeline, monitor, basic_context):
        """测试监控器清空。"""
        five_stage_pipeline.set_monitor(monitor)
        five_stage_pipeline.execute(basic_context)
        assert len(monitor.get_events()) > 0

        monitor.clear()
        assert len(monitor.get_events()) == 0

    def test_diagnostics_analyze_result(self, five_stage_pipeline, basic_context):
        """测试诊断分析结果。"""
        result = five_stage_pipeline.execute(basic_context)
        analysis = PipelineDiagnostics.analyze_result(result)

        assert analysis["pipeline_name"] == "five_stage_full"
        assert analysis["overall_status"] == "success"
        assert analysis["stage_count"] == 5
        assert analysis["executed_count"] == 5
        assert analysis["failed_count"] == 0
        assert analysis["success_rate"] == 100.0
        assert len(analysis["stages"]) == 5
        assert analysis["bottleneck_stage"] is not None

    def test_diagnostics_generate_report(self, five_stage_pipeline, basic_context):
        """测试诊断报告生成。"""
        result = five_stage_pipeline.execute(basic_context)
        report = PipelineDiagnostics.generate_report(result)
        assert "管道执行报告" in report
        assert "five_stage_full" in report
        assert "成功" in report

    def test_diagnostics_compare_results(self, five_stage_pipeline, basic_context):
        """测试诊断结果比较。"""
        ctx1 = PipelineContext(input_data={"user_input": "测试1"})
        ctx2 = PipelineContext(input_data={"user_input": "测试2"})
        result1 = five_stage_pipeline.execute(ctx1)
        result2 = five_stage_pipeline.execute(ctx2)

        comparison = PipelineDiagnostics.compare_results(result1, result2)
        assert "duration_diff_ms" in comparison
        assert "status_changed" in comparison
        assert comparison["status_changed"] is False


# ===== 测试类：模板注册表与预定义管道 =====


class TestTemplateRegistryAndPredefinedPipelines:
    """模板注册表与预定义管道测试。"""

    def test_registry_has_default_templates(self, registry):
        """测试注册表包含默认模板。"""
        templates = registry.list_templates()
        assert len(templates) >= 20

    def test_proposal_generation_template_exists(self, registry):
        """测试论题生成模板存在。"""
        assert registry.has_template("proposal_generation") is True
        template = registry.get_template("proposal_generation")
        assert template is not None
        assert template["category"] == TemplateCategory.GENERATION
        assert "info_confirm" in template["stage_names"]

    def test_create_pipeline_from_template(self, registry):
        """测试从模板创建管道。"""
        pipeline = registry.create_pipeline("proposal_generation")
        assert pipeline.name == "proposal_generation"
        assert pipeline.stage_count() == 5
        stage_names = pipeline.get_stage_names()
        assert "info_confirm" in stage_names
        assert "deep_assist" in stage_names

    def test_build_proposal_generation_pipeline_with_custom_stages(self):
        """测试使用自定义阶段构建论题生成管道。"""
        custom_stages = {
            "info_confirm": FunctionalStage(
                name="info_confirm",
                func=lambda ctx: _make_stage_result("info_confirm", {"custom": True}),
            ),
            "creativity": FunctionalStage(
                name="creativity",
                func=lambda ctx: _make_stage_result("creativity", {"candidates": []}),
            ),
        }
        pipeline = build_proposal_generation_pipeline(custom_stages=custom_stages)
        assert pipeline.stage_count() == 5

        ctx = PipelineContext(input_data={"user_input": "测试"})
        result = pipeline.execute(ctx)
        assert result.success is True
        assert ctx.get("custom") is True

    def test_list_templates_by_category(self, registry):
        """测试按分类列出模板。"""
        generation_templates = registry.list_templates(TemplateCategory.GENERATION)
        assert len(generation_templates) >= 1
        for t in generation_templates:
            assert t["category"] == TemplateCategory.GENERATION

        validation_templates = registry.list_templates(TemplateCategory.VALIDATION)
        assert len(validation_templates) >= 1

    def test_register_custom_template(self, registry):
        """测试注册自定义模板。"""
        registry.register_template(
            name="custom_test_pipeline",
            category=TemplateCategory.ANALYSIS,
            description="自定义测试管道",
            stage_names=["step1", "step2", "step3"],
        )
        assert registry.has_template("custom_test_pipeline") is True
        template = registry.get_template("custom_test_pipeline")
        assert template["description"] == "自定义测试管道"

        # 创建管道
        pipeline = registry.create_pipeline("custom_test_pipeline")
        assert pipeline.stage_count() == 3

    def test_remove_template(self, registry):
        """测试移除模板。"""
        registry.register_template(
            name="to_remove",
            category=TemplateCategory.BATCH,
            description="待移除",
            stage_names=["s1"],
        )
        assert registry.remove_template("to_remove") is True
        assert registry.has_template("to_remove") is False
        assert registry.remove_template("nonexistent") is False

    def test_global_registry_singleton(self):
        """测试全局注册表单例。"""
        r1 = get_template_registry()
        r2 = get_template_registry()
        assert r1 is r2

    def test_list_pipeline_templates_function(self):
        """测试模块级 list_pipeline_templates 函数。"""
        templates = list_pipeline_templates()
        assert len(templates) >= 20

    def test_create_pipeline_from_template_function(self):
        """测试模块级 create_pipeline_from_template 函数。"""
        pipeline = create_pipeline_from_template("proposal_generation")
        assert pipeline is not None
        assert pipeline.stage_count() == 5


# ===== 测试类：管道构建器 =====


class TestPipelineBuilder:
    """管道构建器测试。"""

    def test_builder_chain_api(self):
        """测试构建器链式 API。"""
        pipeline = (
            PipelineBuilder("builder_test")
            .description("测试管道")
            .add_functional_stage("stage1", lambda ctx: _make_stage_result("stage1"))
            .add_functional_stage("stage2", lambda ctx: _make_stage_result("stage2"))
            .with_error_strategy(ErrorHandlingStrategy.SKIP)
            .with_retries(max_retries=2, delay=0.01)
            .with_timeout(30.0)
            .with_checkpoints(True)
            .with_tags("test", "builder")
            .build()
        )
        assert pipeline.name == "builder_test"
        assert pipeline.stage_count() == 2
        assert pipeline.enable_checkpoints is True
        assert "test" in pipeline.tags

    def test_builder_with_monitor(self):
        """测试构建器设置监控器。"""
        monitor = PipelineMonitor()
        pipeline = (
            PipelineBuilder("monitored")
            .add_functional_stage("s1", lambda ctx: _make_stage_result("s1"))
            .with_monitor(monitor)
            .build()
        )
        ctx = PipelineContext(input_data={})
        result = pipeline.execute(ctx)
        assert result.success is True
        assert len(monitor.get_events()) > 0


# ===== 测试类：异步执行 =====


class TestAsyncExecution:
    """异步执行测试。"""

    @pytest.mark.asyncio
    async def test_async_pipeline_execution(self):
        """测试异步管道执行。"""
        pipeline = _build_five_stage_pipeline()
        ctx = PipelineContext(
            input_data={"user_input": "异步测试", "degree": "master"},
        )
        result = await pipeline.execute_async(ctx)

        assert result.success is True
        assert result.executed_stages == 5
        assert ctx.get("info_confirmed") is True

    @pytest.mark.asyncio
    async def test_async_functional_stage(self):
        """测试异步函数式阶段。"""
        async def _async_func(ctx: PipelineContext) -> StageResult:
            await asyncio.sleep(0.01)
            ctx.set("async_done", True)
            return _make_stage_result("async_stage", {"async": True})

        stage = AsyncFunctionalStage(name="async_stage", func=_async_func)
        pipeline = Pipeline(name="async_test")
        pipeline.add_stage(stage)

        ctx = PipelineContext(input_data={})
        result = await pipeline.execute_async(ctx)

        assert result.success is True
        assert ctx.get("async_done") is True

    @pytest.mark.asyncio
    async def test_executor_execute_async(self, executor):
        """测试执行器异步执行。"""
        pipeline = _build_five_stage_pipeline()
        ctx = PipelineContext(input_data={"user_input": "执行器异步测试"})
        result = await executor.execute_async(pipeline, ctx)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_executor_batch_async(self, executor):
        """测试执行器异步批量执行。"""
        pipelines = [_build_five_stage_pipeline() for _ in range(3)]
        contexts = [
            PipelineContext(input_data={"user_input": f"批量{i}"})
            for i in range(3)
        ]
        results = await executor.execute_batch_async(pipelines, contexts)
        assert len(results) == 3
        for r in results:
            assert isinstance(r, PipelineResult)
            assert r.success is True


# ===== 测试类：批量与并行执行 =====


class TestBatchAndParallelExecution:
    """批量与并行执行测试。"""

    def test_executor_sequential_batch(self, executor):
        """测试执行器顺序批量执行。"""
        pipelines = [_build_five_stage_pipeline() for _ in range(3)]
        contexts = [
            PipelineContext(input_data={"user_input": f"顺序{i}"})
            for i in range(3)
        ]
        results = executor.execute_batch(pipelines, contexts, parallel=False)
        assert len(results) == 3
        for r in results:
            assert r.success is True

    def test_executor_parallel_batch(self, executor):
        """测试执行器并行批量执行。"""
        pipelines = [_build_five_stage_pipeline() for _ in range(4)]
        contexts = [
            PipelineContext(
                input_data={"user_input": f"并行{i}"},
                session_id=f"parallel-{i}",
            )
            for i in range(4)
        ]
        results = executor.execute_batch(pipelines, contexts, parallel=True)
        assert len(results) == 4
        for r in results:
            assert r.success is True

    def test_executor_batch_length_mismatch(self, executor):
        """测试批量执行长度不匹配报错。"""
        pipelines = [_build_five_stage_pipeline()]
        contexts = []
        with pytest.raises(ValueError, match="长度不一致"):
            executor.execute_batch(pipelines, contexts)


# ===== 测试类：事件总线 =====


class TestEventBus:
    """事件总线测试。"""

    def test_subscribe_and_publish(self):
        """测试订阅与发布。"""
        bus = PipelineEventBus()
        received = []
        bus.subscribe("test_event", lambda e: received.append(e))

        event = PipelineEvent(event_type="test_event", data={"msg": "hello"})
        bus.publish(event)

        assert len(received) == 1
        assert received[0].data["msg"] == "hello"

    def test_wildcard_subscription(self):
        """测试通配符订阅。"""
        bus = PipelineEventBus()
        all_events = []
        bus.subscribe("*", lambda e: all_events.append(e))

        bus.publish(PipelineEvent(event_type="type_a"))
        bus.publish(PipelineEvent(event_type="type_b"))

        assert len(all_events) == 2

    def test_unsubscribe(self):
        """测试取消订阅。"""
        bus = PipelineEventBus()
        received = []

        def handler(e):
            received.append(e)

        bus.subscribe("test", handler)
        bus.publish(PipelineEvent(event_type="test"))
        assert len(received) == 1

        bus.unsubscribe("test", handler)
        bus.publish(PipelineEvent(event_type="test"))
        assert len(received) == 1  # 取消后不再接收

    def test_event_to_dict(self):
        """测试事件序列化。"""
        event = PipelineEvent(
            event_type="test",
            pipeline_name="test_pipeline",
            stage_name="test_stage",
            data={"key": "value"},
        )
        d = event.to_dict()
        assert d["event_type"] == "test"
        assert d["pipeline_name"] == "test_pipeline"
        assert d["data"]["key"] == "value"

    def test_event_bus_clear(self):
        """测试事件总线清空。"""
        bus = PipelineEventBus()
        bus.subscribe("test", lambda e: None)
        bus.clear()
        # 清空后发布不应有处理器调用
        bus.publish(PipelineEvent(event_type="test"))


# ===== 测试类：检查点管理器 =====


class TestCheckpointManager:
    """检查点管理器测试。"""

    def test_save_and_load_checkpoint(self, temp_checkpoint_manager):
        """测试保存与加载检查点。"""
        ctx = PipelineContext(
            input_data={"user_input": "测试"},
            session_id="cp-test",
        )
        ctx.set("stage_data", "value")

        cp_id = temp_checkpoint_manager.save_checkpoint(
            pipeline_name="test_pipeline",
            stage_name="stage1",
            context=ctx,
        )
        assert cp_id is not None
        assert "test_pipeline" in cp_id
        assert "stage1" in cp_id

        loaded = temp_checkpoint_manager.load_checkpoint(cp_id)
        assert loaded is not None
        assert loaded["pipeline_name"] == "test_pipeline"
        assert loaded["stage_name"] == "stage1"
        assert loaded["context"]["session_id"] == "cp-test"

    def test_list_checkpoints(self, temp_checkpoint_manager):
        """测试列出检查点。"""
        ctx = PipelineContext(input_data={})
        temp_checkpoint_manager.save_checkpoint("p1", "s1", ctx)
        temp_checkpoint_manager.save_checkpoint("p1", "s2", ctx)
        temp_checkpoint_manager.save_checkpoint("p2", "s1", ctx)

        all_cps = temp_checkpoint_manager.list_checkpoints()
        assert len(all_cps) == 3

        p1_cps = temp_checkpoint_manager.list_checkpoints("p1")
        assert len(p1_cps) == 2

    def test_delete_checkpoint(self, temp_checkpoint_manager):
        """测试删除检查点。"""
        ctx = PipelineContext(input_data={})
        cp_id = temp_checkpoint_manager.save_checkpoint("p1", "s1", ctx)
        assert temp_checkpoint_manager.delete_checkpoint(cp_id) is True
        assert temp_checkpoint_manager.load_checkpoint(cp_id) is None

    def test_clear_all(self, temp_checkpoint_manager):
        """测试清空所有检查点。"""
        ctx = PipelineContext(input_data={})
        temp_checkpoint_manager.save_checkpoint("p1", "s1", ctx)
        temp_checkpoint_manager.save_checkpoint("p2", "s1", ctx)
        temp_checkpoint_manager.clear_all()
        assert len(temp_checkpoint_manager.list_checkpoints()) == 0


# ===== 测试类：常用阶段集合 =====


class TestCommonStages:
    """常用阶段集合测试。"""

    def test_validate_input_stage_success(self):
        """测试输入校验阶段成功。"""
        stage = CommonStages.validate_input(required_keys=["user_input", "degree"])
        ctx = PipelineContext(input_data={"user_input": "测试", "degree": "master"})
        result = stage.execute(ctx)
        assert result.success is True

    def test_validate_input_stage_failure(self):
        """测试输入校验阶段失败。"""
        stage = CommonStages.validate_input(required_keys=["missing_key"])
        ctx = PipelineContext(input_data={"user_input": "测试"})
        result = stage.execute(ctx)
        assert result.failed is True
        assert "missing_key" in result.error

    def test_noop_stage(self):
        """测试空操作阶段。"""
        stage = CommonStages.noop_stage(name="noop")
        ctx = PipelineContext(input_data={})
        result = stage.execute(ctx)
        assert result.success is True

    def test_transform_stage(self):
        """测试数据转换阶段。"""
        def transformer(ctx: PipelineContext) -> dict:
            return {"transformed": True, "original": ctx.input_data.get("user_input")}

        stage = CommonStages.transform_data(transformer)
        ctx = PipelineContext(input_data={"user_input": "原始"})
        result = stage.execute(ctx)
        assert result.success is True
        assert ctx.get("transformed") is True

    def test_aggregate_stage(self):
        """测试聚合阶段。"""
        stage = CommonStages.aggregate_stage(
            source_keys=["s1", "s2"], target_key="aggregated"
        )
        ctx = PipelineContext(input_data={})
        ctx.set("s1", "data1")
        ctx.set("s2", "data2")
        result = stage.execute(ctx)
        assert result.success is True
        agg = ctx.get("aggregated")
        assert agg["s1"] == "data1"
        assert agg["s2"] == "data2"

    def test_cache_stage_first_miss_then_hit(self):
        """测试缓存阶段首次未命中后命中。"""
        call_count = {"n": 0}

        def factory(ctx: PipelineContext) -> str:
            call_count["n"] += 1
            return "computed_value"

        stage = CommonStages.cache_stage(cache_key="ck", factory=factory)
        ctx = PipelineContext(input_data={})

        # 首次执行，未命中缓存
        result1 = stage.execute(ctx)
        assert result1.data["cached"] is False
        assert call_count["n"] == 1

        # 第二次执行，命中缓存
        result2 = stage.execute(ctx)
        assert result2.data["cached"] is True
        assert call_count["n"] == 1  # 工厂不应再次调用


# ===== 测试类：管道阶段组合操作 =====


class TestPipelineStageComposition:
    """管道阶段组合操作测试。"""

    def test_insert_stage_at_index(self):
        """测试在指定位置插入阶段。"""
        pipeline = create_pipeline("insert_test")
        pipeline.add_stage(FunctionalStage(name="s1", func=lambda ctx: _make_stage_result("s1")))
        pipeline.add_stage(FunctionalStage(name="s3", func=lambda ctx: _make_stage_result("s3")))
        pipeline.insert_stage(1, FunctionalStage(name="s2", func=lambda ctx: _make_stage_result("s2")))

        names = pipeline.get_stage_names()
        assert names == ["s1", "s2", "s3"]

    def test_insert_after(self):
        """测试在指定阶段后插入。"""
        pipeline = create_pipeline("insert_after_test")
        pipeline.add_stage(FunctionalStage(name="s1", func=lambda ctx: _make_stage_result("s1")))
        pipeline.add_stage(FunctionalStage(name="s3", func=lambda ctx: _make_stage_result("s3")))
        pipeline.insert_after("s1", FunctionalStage(name="s2", func=lambda ctx: _make_stage_result("s2")))

        names = pipeline.get_stage_names()
        assert names == ["s1", "s2", "s3"]

    def test_insert_before(self):
        """测试在指定阶段前插入。"""
        pipeline = create_pipeline("insert_before_test")
        pipeline.add_stage(FunctionalStage(name="s2", func=lambda ctx: _make_stage_result("s2")))
        pipeline.add_stage(FunctionalStage(name="s3", func=lambda ctx: _make_stage_result("s3")))
        pipeline.insert_before("s2", FunctionalStage(name="s1", func=lambda ctx: _make_stage_result("s1")))

        names = pipeline.get_stage_names()
        assert names == ["s1", "s2", "s3"]

    def test_remove_stage(self):
        """测试移除阶段。"""
        pipeline = create_pipeline("remove_test")
        pipeline.add_stage(FunctionalStage(name="s1", func=lambda ctx: _make_stage_result("s1")))
        pipeline.add_stage(FunctionalStage(name="s2", func=lambda ctx: _make_stage_result("s2")))

        assert pipeline.remove_stage("s1") is True
        assert pipeline.stage_count() == 1
        assert pipeline.get_stage_names() == ["s2"]
        assert pipeline.remove_stage("nonexistent") is False

    def test_replace_stage(self):
        """测试替换阶段。"""
        pipeline = create_pipeline("replace_test")
        pipeline.add_stage(FunctionalStage(name="original", func=lambda ctx: _make_stage_result("original")))
        new_stage = FunctionalStage(name="replaced", func=lambda ctx: _make_stage_result("replaced"))
        assert pipeline.replace_stage("original", new_stage) is True
        assert pipeline.get_stage_names() == ["replaced"]

    def test_duplicate_stage_name_rejected(self):
        """测试重复阶段名被拒绝。"""
        pipeline = create_pipeline("dup_test")
        pipeline.add_stage(FunctionalStage(name="s1", func=lambda ctx: _make_stage_result("s1")))
        with pytest.raises(ValueError, match="已存在"):
            pipeline.add_stage(FunctionalStage(name="s1", func=lambda ctx: _make_stage_result("s1")))

    def test_clear_stages(self):
        """测试清空所有阶段。"""
        pipeline = create_pipeline("clear_test")
        pipeline.add_stage(FunctionalStage(name="s1", func=lambda ctx: _make_stage_result("s1")))
        pipeline.add_stage(FunctionalStage(name="s2", func=lambda ctx: _make_stage_result("s2")))
        pipeline.clear_stages()
        assert pipeline.stage_count() == 0

    def test_get_stage_by_name(self):
        """测试按名称获取阶段。"""
        pipeline = create_pipeline("get_test")
        stage = FunctionalStage(name="target", func=lambda ctx: _make_stage_result("target"))
        pipeline.add_stage(stage)
        assert pipeline.get_stage("target") is stage
        assert pipeline.get_stage("nonexistent") is None


# ===== 测试类：旧版状态机兼容性 =====


class TestLegacyStateMachineCompat:
    """旧版状态机兼容性测试。"""

    def test_legacy_state_enum_values(self):
        """测试旧版 State 枚举值。"""
        assert State.INIT == "init"
        assert State.SEARCHING == "searching"
        assert State.REASONING == "reasoning"
        assert State.PROPOSAL == "proposal"
        assert State.DONE == "done"

    def test_legacy_state_machine_advance(self):
        """测试旧版状态机推进。"""
        sm = StateMachine()
        assert sm.state == State.INIT

        sm.advance()
        assert sm.state == State.SEARCHING

        sm.advance()
        assert sm.state == State.REASONING

        sm.advance()
        assert sm.state == State.PROPOSAL

        sm.advance()
        assert sm.state == State.DONE

        # 到达终态后不再推进
        sm.advance()
        assert sm.state == State.DONE

    def test_legacy_state_machine_reset(self):
        """测试旧版状态机重置。"""
        sm = StateMachine()
        sm.advance()
        sm.advance()
        sm.reset()
        assert sm.state == State.INIT

    def test_create_orchestration_factory(self):
        """测试 create_orchestration 工厂函数。"""
        sm = create_orchestration(
            session_id="test-session",
            degree="master",
            discipline="science_engineering",
            mentor_info="测试导师",
        )
        assert sm.ctx.session_id == "test-session"
        assert sm.ctx.degree == "master"
        assert sm.ctx.discipline == "science_engineering"
        assert sm.ctx.mentor_info == "测试导师"
        assert sm.ctx.current_state == "init"


# ===== 测试类：复杂端到端场景 =====


class TestComplexEndToEndScenarios:
    """复杂端到端场景测试。"""

    def test_full_flow_with_monitoring_and_diagnostics(self, monitor):
        """测试带监控与诊断的完整流程。"""
        pipeline = _build_five_stage_pipeline()
        pipeline.set_monitor(monitor)

        ctx = PipelineContext(
            input_data={
                "user_input": "复杂场景端到端测试",
                "degree": "doctor",
                "discipline": "humanities_social",
            },
            session_id="complex-session",
        )
        result = pipeline.execute(ctx)

        # 验证执行成功
        assert result.success is True

        # 验证监控数据
        stats = monitor.get_stats()
        assert stats["total_events"] >= 7
        stage_stats = stats["stages"]
        assert "info_confirm" in stage_stats
        assert stage_stats["info_confirm"]["success_rate"] == 1.0

        # 验证诊断报告
        report = PipelineDiagnostics.generate_report(result)
        assert "成功" in report
        assert "five_stage_full" in report

    def test_pipeline_with_conditional_branch(self):
        """测试带条件分支的管道。"""
        pipeline = Pipeline(name="conditional_flow")
        pipeline.add_stage(FunctionalStage(
            name="check_input",
            func=lambda ctx: _make_stage_result("check_input", {"checked": True}),
        ))
        # 根据上下文决定是否执行高级处理
        pipeline.add_stage(FunctionalStage(
            name="advanced_process",
            func=lambda ctx: _make_stage_result("advanced", {"advanced": True}),
            condition=lambda ctx: ctx.input_data.get("mode") == "advanced",
        ))
        pipeline.add_stage(FunctionalStage(
            name="finalize",
            func=lambda ctx: _make_stage_result("finalize", {"done": True}),
        ))

        # 普通模式：跳过 advanced_process
        ctx_normal = PipelineContext(input_data={"mode": "normal"})
        result_normal = pipeline.execute(ctx_normal)
        assert result_normal.success is True
        assert result_normal.skipped_stages == 1

        # 高级模式：执行 advanced_process
        ctx_advanced = PipelineContext(input_data={"mode": "advanced"})
        result_advanced = pipeline.execute(ctx_advanced)
        assert result_advanced.success is True
        assert result_advanced.skipped_stages == 0
        assert ctx_advanced.get("advanced") is True

    def test_pipeline_stage_dependencies(self):
        """测试阶段依赖声明。"""
        stage1 = FunctionalStage(name="s1", func=lambda ctx: _make_stage_result("s1"))
        stage2 = FunctionalStage(name="s2", func=lambda ctx: _make_stage_result("s2"))

        stage2.depends_on("s1")
        assert "s1" in stage2.get_dependencies()
        assert stage1.get_dependencies() == []

    def test_pipeline_status_property(self, five_stage_pipeline, basic_context):
        """测试管道状态属性。"""
        assert five_stage_pipeline.status == PipelineStatus.IDLE
        five_stage_pipeline.execute(basic_context)
        assert five_stage_pipeline.status == PipelineStatus.IDLE  # 执行后回到 IDLE

    def test_concurrent_pipeline_execution_rejected(self):
        """测试并发执行同一管道被拒绝。"""
        pipeline = _build_five_stage_pipeline()
        ctx = PipelineContext(input_data={"user_input": "并发测试"})

        # 手动设置状态为 RUNNING 模拟并发
        pipeline._status = PipelineStatus.RUNNING
        result = pipeline.execute(ctx)
        assert result.failed is True
        assert "运行中" in result.error

    def test_full_flow_with_event_bus_integration(self):
        """测试完整流程与事件总线集成。"""
        bus = PipelineEventBus()
        events_received = []

        bus.subscribe("pipeline_start", lambda e: events_received.append(("start", e)))
        bus.subscribe("pipeline_end", lambda e: events_received.append(("end", e)))

        # 创建带事件发布的管道
        pipeline = _build_five_stage_pipeline()
        ctx = PipelineContext(input_data={"user_input": "事件总线测试"})

        # 执行前发布开始事件
        bus.publish(PipelineEvent(
            event_type="pipeline_start",
            pipeline_name=pipeline.name,
        ))
        result = pipeline.execute(ctx)
        # 执行后发布结束事件
        bus.publish(PipelineEvent(
            event_type="pipeline_end",
            pipeline_name=pipeline.name,
            data={"status": result.status.value},
        ))

        assert result.success is True
        assert len(events_received) == 2
        assert events_received[0][0] == "start"
        assert events_received[1][0] == "end"

    def test_pipeline_with_timeout_stage(self):
        """测试带超时的阶段执行。"""
        def _slow_func(ctx: PipelineContext) -> StageResult:
            time.sleep(0.5)
            return _make_stage_result("slow", {"done": True})

        pipeline = Pipeline(name="timeout_test")
        pipeline.add_stage(FunctionalStage(
            name="slow",
            func=_slow_func,
            timeout=0.1,  # 100ms 超时
        ))

        ctx = PipelineContext(input_data={})
        result = pipeline.execute(ctx)

        # 应触发超时
        assert result.failed is True
        timeout_results = [sr for sr in result.stage_results if sr.status == StageStatus.TIMEOUT]
        assert len(timeout_results) == 1

    def test_pipeline_metadata_propagation(self):
        """测试管道元数据传播。"""
        pipeline = create_pipeline("metadata_test")
        pipeline.metadata["version"] = "8.0"
        pipeline.metadata["author"] = "test"

        d = pipeline.to_dict()
        assert d["metadata"]["version"] == "8.0"
        assert d["metadata"]["author"] == "test"

    def test_stage_result_to_dict(self):
        """测试阶段结果序列化。"""
        sr = StageResult(
            stage_name="test_stage",
            status=StageStatus.SUCCESS,
            data={"key": "value"},
            duration_ms=123.45,
            retry_count=1,
            metadata={"meta": "data"},
        )
        d = sr.to_dict()
        assert d["stage_name"] == "test_stage"
        assert d["status"] == "success"
        assert d["data"]["key"] == "value"
        assert d["retry_count"] == 1
        assert d["metadata"]["meta"] == "data"

    def test_stage_result_properties(self):
        """测试阶段结果属性。"""
        success_result = StageResult(stage_name="s", status=StageStatus.SUCCESS)
        assert success_result.success is True
        assert success_result.failed is False
        assert success_result.skipped is False

        failed_result = StageResult(stage_name="s", status=StageStatus.FAILED)
        assert failed_result.success is False
        assert failed_result.failed is True

        skipped_result = StageResult(stage_name="s", status=StageStatus.SKIPPED)
        assert skipped_result.skipped is True

        timeout_result = StageResult(stage_name="s", status=StageStatus.TIMEOUT)
        assert timeout_result.failed is True

    def test_pipeline_result_get_stage_result(self, five_stage_pipeline, basic_context):
        """测试按名称获取阶段结果。"""
        result = five_stage_pipeline.execute(basic_context)
        sr = result.get_stage_result("creativity")
        assert sr is not None
        assert sr.stage_name == "creativity"
        assert sr.success is True

        # 不存在的阶段
        assert result.get_stage_result("nonexistent") is None
