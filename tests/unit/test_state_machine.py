"""编排状态机单元测试

测试 backend/orchestration/state_machine.py。
覆盖以下功能：
  - Stage 枚举（v8.0 五阶段）
  - Event 枚举（v8.0 事件）
  - TRANSITIONS 状态转移表
  - TransitionResult 数据类
  - transition 状态转移函数
  - get_next_events 获取可触发事件
  - is_valid_transition 检查转移合法性
  - State 枚举（旧版兼容）
  - StateMachine 类（旧版兼容）
  - OrchestrationContext 数据类
  - OrchestrationStateMachine 类
  - create_orchestration 便捷函数

测试策略：
  - 纯逻辑测试，不依赖数据库
  - 覆盖五阶段正向流转与回退逻辑
  - 边界条件：非法转移、RESET 事件、START 事件
"""
import asyncio
import os
import sys

import pytest

# ===== 项目根目录加入 sys.path =====
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.orchestration.state_machine import (
    Stage,
    Event,
    TRANSITIONS,
    TransitionResult,
    transition,
    get_next_events,
    is_valid_transition,
    State,
    StateMachine,
    OrchestrationContext,
    OrchestrationStateMachine,
    create_orchestration,
    STATE_INIT,
    STATE_INSPIRING,
    STATE_REASONING,
    STATE_VALIDATING,
    STATE_COMPLETED,
    STATE_FAILED,
)


# ===== 辅助函数 =====

def _run_async(coro):
    """辅助函数：运行异步协程。"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ===== 测试类：Stage 枚举 =====

class TestStageEnum:
    """测试 Stage 枚举（v8.0）。"""

    def test_stage_values(self):
        """五阶段枚举值应正确。"""
        assert Stage.INFO_CONFIRM.value == "info_confirm"
        assert Stage.CREATIVITY.value == "creativity"
        assert Stage.VALIDATION.value == "validation"
        assert Stage.GENERATION.value == "generation"
        assert Stage.DEEP_ASSIST.value == "deep_assist"

    def test_stage_count(self):
        """应有 5 个阶段。"""
        assert len(list(Stage)) == 5

    def test_stage_is_string_enum(self):
        """Stage 应继承 str。"""
        assert isinstance(Stage.INFO_CONFIRM, str)


# ===== 测试类：Event 枚举 =====

class TestEventEnum:
    """测试 Event 枚举。"""

    def test_event_values(self):
        """事件枚举值应正确。"""
        assert Event.START.value == "start"
        assert Event.USER_CONFIRM.value == "user_confirm"
        assert Event.CANDIDATES_GENERATED.value == "candidates_generated"
        assert Event.EVALUATION_DONE.value == "evaluation_done"
        assert Event.SCORE_PASS.value == "score_pass"
        assert Event.SCORE_FAIL.value == "score_fail"
        assert Event.GENERATION_DONE.value == "generation_done"
        assert Event.ENTER_DEEP_ASSIST.value == "enter_deep_assist"
        assert Event.RESET.value == "reset"

    def test_event_count(self):
        """应有 9 个事件。"""
        assert len(list(Event)) == 9


# ===== 测试类：TRANSITIONS =====

class TestTransitions:
    """测试 TRANSITIONS 状态转移表。"""

    def test_contains_user_confirm_transition(self):
        """应包含用户确认转移。"""
        assert (Stage.INFO_CONFIRM, Event.USER_CONFIRM) in TRANSITIONS

    def test_contains_candidates_generated_transition(self):
        """应包含候选生成转移。"""
        assert (Stage.CREATIVITY, Event.CANDIDATES_GENERATED) in TRANSITIONS

    def test_contains_score_pass_transition(self):
        """应包含评分通过转移。"""
        assert (Stage.VALIDATION, Event.SCORE_PASS) in TRANSITIONS

    def test_contains_score_fail_transition(self):
        """应包含评分失败转移。"""
        assert (Stage.VALIDATION, Event.SCORE_FAIL) in TRANSITIONS

    def test_score_fail_returns_to_creativity(self):
        """评分失败应回退到创意阶段。"""
        assert TRANSITIONS[(Stage.VALIDATION, Event.SCORE_FAIL)] == Stage.CREATIVITY

    def test_contains_generation_done_transition(self):
        """应包含生成完成转移。"""
        assert (Stage.GENERATION, Event.GENERATION_DONE) in TRANSITIONS

    def test_contains_reset_transition(self):
        """应包含重置转移。"""
        assert (Stage.DEEP_ASSIST, Event.RESET) in TRANSITIONS

    def test_reset_returns_to_info_confirm(self):
        """重置应回到信息确权阶段。"""
        assert TRANSITIONS[(Stage.DEEP_ASSIST, Event.RESET)] == Stage.INFO_CONFIRM


# ===== 测试类：TransitionResult 数据类 =====

class TestTransitionResult:
    """测试 TransitionResult 数据类。"""

    def test_construction(self):
        """应能正常构造。"""
        result = TransitionResult(
            success=True,
            from_stage=Stage.INFO_CONFIRM,
            to_stage=Stage.CREATIVITY,
            event=Event.USER_CONFIRM,
            message="转移成功",
        )
        assert result.success is True
        assert result.from_stage == Stage.INFO_CONFIRM
        assert result.to_stage == Stage.CREATIVITY
        assert result.event == Event.USER_CONFIRM
        assert result.message == "转移成功"
        assert result.is_retry is False

    def test_with_retry(self):
        """is_retry 字段应能设置。"""
        result = TransitionResult(
            success=False,
            from_stage=Stage.VALIDATION,
            to_stage=Stage.CREATIVITY,
            event=Event.SCORE_FAIL,
            message="回退",
            is_retry=True,
        )
        assert result.is_retry is True


# ===== 测试类：transition 函数 =====

class TestTransition:
    """测试 transition 函数。"""

    def test_user_confirm_transition(self):
        """用户确认应从信息确权转移到创意。"""
        result = transition(Stage.INFO_CONFIRM, Event.USER_CONFIRM)
        assert result.success is True
        assert result.to_stage == Stage.CREATIVITY
        assert result.is_retry is False

    def test_candidates_generated_transition(self):
        """候选生成应从创意转移到校验。"""
        result = transition(Stage.CREATIVITY, Event.CANDIDATES_GENERATED)
        assert result.success is True
        assert result.to_stage == Stage.VALIDATION

    def test_score_pass_transition(self):
        """评分通过应从校验转移到生成。"""
        result = transition(Stage.VALIDATION, Event.SCORE_PASS)
        assert result.success is True
        assert result.to_stage == Stage.GENERATION

    def test_score_fail_transition(self):
        """评分失败应从校验回退到创意。"""
        result = transition(Stage.VALIDATION, Event.SCORE_FAIL)
        assert result.success is True
        assert result.to_stage == Stage.CREATIVITY
        assert result.is_retry is True

    def test_generation_done_transition(self):
        """生成完成应从生成转移到深度辅助。"""
        result = transition(Stage.GENERATION, Event.GENERATION_DONE)
        assert result.success is True
        assert result.to_stage == Stage.DEEP_ASSIST

    def test_reset_transition(self):
        """重置应回到信息确权。"""
        result = transition(Stage.DEEP_ASSIST, Event.RESET)
        assert result.success is True
        assert result.to_stage == Stage.INFO_CONFIRM

    def test_reset_from_any_stage(self):
        """从任何阶段重置都应回到信息确权。"""
        for stage in Stage:
            result = transition(stage, Event.RESET)
            assert result.success is True
            assert result.to_stage == Stage.INFO_CONFIRM

    def test_start_from_none(self):
        """从 None 启动应进入信息确权。"""
        result = transition(None, Event.START)
        assert result.success is True
        assert result.to_stage == Stage.INFO_CONFIRM

    def test_invalid_transition(self):
        """非法转移应返回失败。"""
        result = transition(Stage.INFO_CONFIRM, Event.SCORE_PASS)
        assert result.success is False
        assert result.to_stage == Stage.INFO_CONFIRM
        assert "非法转移" in result.message

    def test_invalid_transition_from_generation(self):
        """从生成阶段触发用户确认应失败。"""
        result = transition(Stage.GENERATION, Event.USER_CONFIRM)
        assert result.success is False

    def test_message_contains_stages(self):
        """转移消息应包含阶段信息。"""
        result = transition(Stage.INFO_CONFIRM, Event.USER_CONFIRM)
        assert "用户确认" in result.message or "创意" in result.message

    def test_score_fail_message_mentions_retry(self):
        """评分失败消息应提及回退。"""
        result = transition(Stage.VALIDATION, Event.SCORE_FAIL)
        assert "回退" in result.message or "创意" in result.message


# ===== 测试类：get_next_events =====

class TestGetNextEvents:
    """测试 get_next_events 函数。"""

    def test_info_confirm_next_events(self):
        """信息确权阶段可触发的事件。"""
        events = get_next_events(Stage.INFO_CONFIRM)
        assert Event.USER_CONFIRM in events

    def test_creativity_next_events(self):
        """创意阶段可触发的事件。"""
        events = get_next_events(Stage.CREATIVITY)
        assert Event.CANDIDATES_GENERATED in events

    def test_validation_next_events(self):
        """校验阶段可触发的事件。"""
        events = get_next_events(Stage.VALIDATION)
        assert Event.SCORE_PASS in events
        assert Event.SCORE_FAIL in events

    def test_generation_next_events(self):
        """生成阶段可触发的事件。"""
        events = get_next_events(Stage.GENERATION)
        assert Event.GENERATION_DONE in events

    def test_deep_assist_next_events(self):
        """深度辅助阶段可触发的事件。"""
        events = get_next_events(Stage.DEEP_ASSIST)
        assert Event.RESET in events

    def test_returns_list(self):
        """应返回列表。"""
        events = get_next_events(Stage.INFO_CONFIRM)
        assert isinstance(events, list)


# ===== 测试类：is_valid_transition =====

class TestIsValidTransition:
    """测试 is_valid_transition 函数。"""

    def test_valid_transition(self):
        """合法转移应返回 True。"""
        assert is_valid_transition(Stage.INFO_CONFIRM, Event.USER_CONFIRM) is True

    def test_invalid_transition(self):
        """非法转移应返回 False。"""
        assert is_valid_transition(Stage.INFO_CONFIRM, Event.SCORE_PASS) is False

    def test_reset_always_valid(self):
        """RESET 事件应始终合法。"""
        for stage in Stage:
            assert is_valid_transition(stage, Event.RESET) is True

    def test_score_pass_from_validation_valid(self):
        """从校验阶段评分通过应合法。"""
        assert is_valid_transition(Stage.VALIDATION, Event.SCORE_PASS) is True

    def test_score_pass_from_creativity_invalid(self):
        """从创意阶段评分通过应不合法。"""
        assert is_valid_transition(Stage.CREATIVITY, Event.SCORE_PASS) is False


# ===== 测试类：State 枚举（旧版兼容） =====

class TestStateEnum:
    """测试 State 枚举（旧版兼容）。"""

    def test_state_values(self):
        """旧版状态值应正确。"""
        assert State.INIT.value == "init"
        assert State.SEARCHING.value == "searching"
        assert State.REASONING.value == "reasoning"
        assert State.PROPOSAL.value == "proposal"
        assert State.DONE.value == "done"

    def test_state_count(self):
        """应有 5 个旧版状态。"""
        assert len(list(State)) == 5


# ===== 测试类：StateMachine（旧版兼容） =====

class TestStateMachineLegacy:
    """测试 StateMachine 类（旧版兼容）。"""

    def test_initial_state(self):
        """初始状态应为 INIT。"""
        sm = StateMachine()
        assert sm.state == State.INIT

    def test_advance_once(self):
        """推进一次应到 SEARCHING。"""
        sm = StateMachine()
        sm.advance()
        assert sm.state == State.SEARCHING

    def test_advance_to_done(self):
        """推进到完成。"""
        sm = StateMachine()
        for _ in range(4):
            sm.advance()
        assert sm.state == State.DONE

    def test_advance_past_done(self):
        """超过 DONE 应保持 DONE。"""
        sm = StateMachine()
        for _ in range(4):
            sm.advance()
        sm.advance()  # 再推进
        assert sm.state == State.DONE

    def test_reset(self):
        """重置应回到 INIT。"""
        sm = StateMachine()
        sm.advance()
        sm.reset()
        assert sm.state == State.INIT


# ===== 测试类：OrchestrationContext =====

class TestOrchestrationContext:
    """测试 OrchestrationContext 数据类。"""

    def test_construction(self):
        """应能正常构造。"""
        ctx = OrchestrationContext(
            session_id="test-session",
            degree="master",
            discipline="science_engineering",
            mentor_info="导师信息",
        )
        assert ctx.session_id == "test-session"
        assert ctx.degree == "master"
        assert ctx.discipline == "science_engineering"
        assert ctx.mentor_info == "导师信息"
        assert ctx.mode == "quick"
        assert ctx.count == 3
        assert ctx.current_state == STATE_INIT

    def test_default_collections(self):
        """默认集合应为空列表。"""
        ctx = OrchestrationContext(
            session_id="s", degree="master", discipline="sci", mentor_info="m"
        )
        assert ctx.candidates == []
        assert ctx.proposals == []
        assert ctx.errors == []

    def test_post_init_creates_independent_lists(self):
        """__post_init__ 应创建独立列表。"""
        ctx1 = OrchestrationContext(
            session_id="s", degree="master", discipline="sci", mentor_info="m"
        )
        ctx2 = OrchestrationContext(
            session_id="s", degree="master", discipline="sci", mentor_info="m"
        )
        ctx1.candidates.append({"x": 1})
        assert len(ctx2.candidates) == 0


# ===== 测试类：create_orchestration =====

class TestCreateOrchestration:
    """测试 create_orchestration 便捷函数。"""

    def test_returns_state_machine(self):
        """应返回 OrchestrationStateMachine 实例。"""
        sm = create_orchestration(
            session_id="test",
            degree="master",
            discipline="science_engineering",
            mentor_info="导师",
        )
        assert isinstance(sm, OrchestrationStateMachine)

    def test_context_initialized(self):
        """上下文应正确初始化。"""
        sm = create_orchestration(
            session_id="test",
            degree="doctor",
            discipline="humanities_social",
            mentor_info="导师信息",
            mode="deep",
            count=5,
        )
        assert sm.ctx.session_id == "test"
        assert sm.ctx.degree == "doctor"
        assert sm.ctx.discipline == "humanities_social"
        assert sm.ctx.mode == "deep"
        assert sm.ctx.count == 5

    def test_default_mode_and_count(self):
        """默认 mode 与 count 应正确。"""
        sm = create_orchestration(
            session_id="test",
            degree="master",
            discipline="sci",
            mentor_info="m",
        )
        assert sm.ctx.mode == "quick"
        assert sm.ctx.count == 3


# ===== 测试类：OrchestrationStateMachine =====

class TestOrchestrationStateMachine:
    """测试 OrchestrationStateMachine 类。"""

    def test_initial_state(self):
        """初始状态应为 INIT。"""
        sm = create_orchestration(
            session_id="test", degree="master", discipline="sci", mentor_info="m"
        )
        assert sm.ctx.current_state == STATE_INIT

    def test_handle_error_appends_to_errors(self):
        """handle_error 应将错误追加到 errors 列表。"""
        sm = create_orchestration(
            session_id="test", degree="master", discipline="sci", mentor_info="m"
        )
        sm.handle_error(Exception("测试错误"))
        assert len(sm.ctx.errors) == 1
        assert sm.ctx.current_state == STATE_FAILED

    def test_handle_error_records_state(self):
        """handle_error 应记录当前状态。"""
        sm = create_orchestration(
            session_id="test", degree="master", discipline="sci", mentor_info="m"
        )
        sm.ctx.current_state = STATE_REASONING
        sm.handle_error(Exception("错误"))
        assert sm.ctx.errors[0]["state"] == STATE_REASONING

    def test_fallback_proposal(self):
        """_fallback_proposal 应返回基本提案字典。"""
        sm = create_orchestration(
            session_id="test", degree="master", discipline="sci", mentor_info="m"
        )
        candidate = {"direction": "研究方向", "suggestion": "建议"}
        proposal = sm._fallback_proposal(candidate)
        assert "title" in proposal
        assert "inspiration_source" in proposal
        assert "problem_awareness" in proposal
        assert "research_content" in proposal

    def test_fallback_proposal_truncates_title(self):
        """_fallback_proposal 应截断过长的方向描述。"""
        sm = create_orchestration(
            session_id="test", degree="master", discipline="sci", mentor_info="m"
        )
        long_direction = "这是一个非常非常非常非常非常非常长的研究方向描述"
        candidate = {"direction": long_direction, "suggestion": "建议"}
        proposal = sm._fallback_proposal(candidate)
        assert len(proposal["title"]) <= 20

    def test_fallback_proposal_empty_candidate(self):
        """_fallback_proposal 应处理空候选。"""
        sm = create_orchestration(
            session_id="test", degree="master", discipline="sci", mentor_info="m"
        )
        proposal = sm._fallback_proposal({})
        assert proposal["title"] == "未命名论题"


# ===== 测试类：状态常量 =====

class TestStateConstants:
    """测试状态常量。"""

    def test_state_init(self):
        """STATE_INIT 应为 'init'。"""
        assert STATE_INIT == "init"

    def test_state_inspiring(self):
        """STATE_INSPIRING 应为 'inspiring'。"""
        assert STATE_INSPIRING == "inspiring"

    def test_state_reasoning(self):
        """STATE_REASONING 应为 'reasoning'。"""
        assert STATE_REASONING == "reasoning"

    def test_state_validating(self):
        """STATE_VALIDATING 应为 'validating'。"""
        assert STATE_VALIDATING == "validating"

    def test_state_completed(self):
        """STATE_COMPLETED 应为 'completed'。"""
        assert STATE_COMPLETED == "completed"

    def test_state_failed(self):
        """STATE_FAILED 应为 'failed'。"""
        assert STATE_FAILED == "failed"


# ===== 集成测试 =====

class TestStateMachineIntegration:
    """状态机集成测试。"""

    def test_full_five_stage_flow(self):
        """测试五阶段完整正向流程。"""
        # 1. 信息确权 → 创意
        r1 = transition(Stage.INFO_CONFIRM, Event.USER_CONFIRM)
        assert r1.success and r1.to_stage == Stage.CREATIVITY
        # 2. 创意 → 校验
        r2 = transition(Stage.CREATIVITY, Event.CANDIDATES_GENERATED)
        assert r2.success and r2.to_stage == Stage.VALIDATION
        # 3. 校验 → 生成（评分通过）
        r3 = transition(Stage.VALIDATION, Event.SCORE_PASS)
        assert r3.success and r3.to_stage == Stage.GENERATION
        # 4. 生成 → 深度辅助
        r4 = transition(Stage.GENERATION, Event.GENERATION_DONE)
        assert r4.success and r4.to_stage == Stage.DEEP_ASSIST
        # 5. 深度辅助 → 信息确权（重置）
        r5 = transition(Stage.DEEP_ASSIST, Event.RESET)
        assert r5.success and r5.to_stage == Stage.INFO_CONFIRM

    def test_retry_flow(self):
        """测试评分失败回退流程。"""
        # 1. 信息确权 → 创意
        transition(Stage.INFO_CONFIRM, Event.USER_CONFIRM)
        # 2. 创意 → 校验
        transition(Stage.CREATIVITY, Event.CANDIDATES_GENERATED)
        # 3. 校验 → 创意（评分失败回退）
        r = transition(Stage.VALIDATION, Event.SCORE_FAIL)
        assert r.success
        assert r.to_stage == Stage.CREATIVITY
        assert r.is_retry is True
        # 4. 重新创意 → 校验
        r = transition(Stage.CREATIVITY, Event.CANDIDATES_GENERATED)
        assert r.to_stage == Stage.VALIDATION
