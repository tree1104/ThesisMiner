"""Task 9 测试：验证 v8.0 五阶段闭环导航流状态机

覆盖：
- All valid transitions work
- Invalid transitions are rejected
- SCORE_FAIL triggers retry (回退 to CREATIVITY)
- RESET from any stage goes to INFO_CONFIRM
- get_next_events returns correct events
- Backward compatibility: StateMachine class still works
"""
import os
import sys

import pytest

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestStageEnum:
    """五阶段状态枚举测试"""

    def test_stage_has_5_values(self):
        """Stage 枚举应有5个值"""
        from backend.orchestration.state_machine import Stage

        assert len(Stage) == 5

    def test_stage_values(self):
        """Stage 枚举值应正确"""
        from backend.orchestration.state_machine import Stage

        assert Stage.INFO_CONFIRM == "info_confirm"
        assert Stage.CREATIVITY == "creativity"
        assert Stage.VALIDATION == "validation"
        assert Stage.GENERATION == "generation"
        assert Stage.DEEP_ASSIST == "deep_assist"


class TestEventEnum:
    """事件枚举测试"""

    def test_event_has_expected_values(self):
        """Event 枚举应包含所有预期事件"""
        from backend.orchestration.state_machine import Event

        assert Event.START == "start"
        assert Event.USER_CONFIRM == "user_confirm"
        assert Event.CANDIDATES_GENERATED == "candidates_generated"
        assert Event.EVALUATION_DONE == "evaluation_done"
        assert Event.SCORE_PASS == "score_pass"
        assert Event.SCORE_FAIL == "score_fail"
        assert Event.GENERATION_DONE == "generation_done"
        assert Event.ENTER_DEEP_ASSIST == "enter_deep_assist"
        assert Event.RESET == "reset"


class TestValidTransitions:
    """合法状态转移测试"""

    def test_info_confirm_to_creativity(self):
        """信息确权 → 创意（用户确认）"""
        from backend.orchestration.state_machine import Stage, Event, transition

        result = transition(Stage.INFO_CONFIRM, Event.USER_CONFIRM)
        assert result.success is True
        assert result.from_stage == Stage.INFO_CONFIRM
        assert result.to_stage == Stage.CREATIVITY

    def test_creativity_to_validation(self):
        """创意 → 校验（候选生成完成）"""
        from backend.orchestration.state_machine import Stage, Event, transition

        result = transition(Stage.CREATIVITY, Event.CANDIDATES_GENERATED)
        assert result.success is True
        assert result.from_stage == Stage.CREATIVITY
        assert result.to_stage == Stage.VALIDATION

    def test_validation_to_generation_on_pass(self):
        """校验 → 生成（评分通过）"""
        from backend.orchestration.state_machine import Stage, Event, transition

        result = transition(Stage.VALIDATION, Event.SCORE_PASS)
        assert result.success is True
        assert result.from_stage == Stage.VALIDATION
        assert result.to_stage == Stage.GENERATION

    def test_generation_to_deep_assist(self):
        """生成 → 深度辅助（生成完成）"""
        from backend.orchestration.state_machine import Stage, Event, transition

        result = transition(Stage.GENERATION, Event.GENERATION_DONE)
        assert result.success is True
        assert result.from_stage == Stage.GENERATION
        assert result.to_stage == Stage.DEEP_ASSIST

    def test_start_from_none(self):
        """START 事件从 None 启动"""
        from backend.orchestration.state_machine import Stage, Event, transition

        result = transition(None, Event.START)
        assert result.success is True
        assert result.to_stage == Stage.INFO_CONFIRM


class TestInvalidTransitions:
    """非法状态转移测试"""

    def test_invalid_transition_rejected(self):
        """非法转移应被拒绝"""
        from backend.orchestration.state_machine import Stage, Event, transition

        # INFO_CONFIRM + SCORE_PASS 是非法的
        result = transition(Stage.INFO_CONFIRM, Event.SCORE_PASS)
        assert result.success is False
        assert result.to_stage == Stage.INFO_CONFIRM  # 保持原阶段
        assert "非法转移" in result.message

    def test_invalid_transition_creativity_to_generation(self):
        """创意 → 生成（跳过校验）是非法的"""
        from backend.orchestration.state_machine import Stage, Event, transition

        result = transition(Stage.CREATIVITY, Event.GENERATION_DONE)
        assert result.success is False

    def test_invalid_transition_deep_assist_to_generation(self):
        """深度辅助 → 生成（回退）是非法的"""
        from backend.orchestration.state_machine import Stage, Event, transition

        result = transition(Stage.DEEP_ASSIST, Event.GENERATION_DONE)
        assert result.success is False


class TestScoreFailRetry:
    """评分失败回退测试"""

    def test_score_fail_triggers_retry_to_creativity(self):
        """评分失败应回退到创意阶段"""
        from backend.orchestration.state_machine import Stage, Event, transition

        result = transition(Stage.VALIDATION, Event.SCORE_FAIL)
        assert result.success is True
        assert result.from_stage == Stage.VALIDATION
        assert result.to_stage == Stage.CREATIVITY
        assert result.is_retry is True

    def test_score_pass_not_retry(self):
        """评分通过不应标记为retry"""
        from backend.orchestration.state_machine import Stage, Event, transition

        result = transition(Stage.VALIDATION, Event.SCORE_PASS)
        assert result.is_retry is False


class TestResetTransition:
    """RESET 转移测试"""

    def test_reset_from_info_confirm(self):
        """从信息确权重置"""
        from backend.orchestration.state_machine import Stage, Event, transition

        result = transition(Stage.INFO_CONFIRM, Event.RESET)
        assert result.success is True
        assert result.to_stage == Stage.INFO_CONFIRM

    def test_reset_from_creativity(self):
        """从创意阶段重置"""
        from backend.orchestration.state_machine import Stage, Event, transition

        result = transition(Stage.CREATIVITY, Event.RESET)
        assert result.success is True
        assert result.to_stage == Stage.INFO_CONFIRM

    def test_reset_from_validation(self):
        """从校验阶段重置"""
        from backend.orchestration.state_machine import Stage, Event, transition

        result = transition(Stage.VALIDATION, Event.RESET)
        assert result.success is True
        assert result.to_stage == Stage.INFO_CONFIRM

    def test_reset_from_generation(self):
        """从生成阶段重置"""
        from backend.orchestration.state_machine import Stage, Event, transition

        result = transition(Stage.GENERATION, Event.RESET)
        assert result.success is True
        assert result.to_stage == Stage.INFO_CONFIRM

    def test_reset_from_deep_assist(self):
        """从深度辅助重置"""
        from backend.orchestration.state_machine import Stage, Event, transition

        result = transition(Stage.DEEP_ASSIST, Event.RESET)
        assert result.success is True
        assert result.to_stage == Stage.INFO_CONFIRM


class TestGetNextEvents:
    """获取可触发事件测试"""

    def test_next_events_for_info_confirm(self):
        """信息确权阶段可触发事件"""
        from backend.orchestration.state_machine import Stage, Event, get_next_events

        events = get_next_events(Stage.INFO_CONFIRM)
        assert Event.USER_CONFIRM in events

    def test_next_events_for_creativity(self):
        """创意阶段可触发事件"""
        from backend.orchestration.state_machine import Stage, Event, get_next_events

        events = get_next_events(Stage.CREATIVITY)
        assert Event.CANDIDATES_GENERATED in events

    def test_next_events_for_validation(self):
        """校验阶段可触发事件（含PASS和FAIL）"""
        from backend.orchestration.state_machine import Stage, Event, get_next_events

        events = get_next_events(Stage.VALIDATION)
        assert Event.SCORE_PASS in events
        assert Event.SCORE_FAIL in events

    def test_next_events_for_generation(self):
        """生成阶段可触发事件"""
        from backend.orchestration.state_machine import Stage, Event, get_next_events

        events = get_next_events(Stage.GENERATION)
        assert Event.GENERATION_DONE in events

    def test_next_events_for_deep_assist(self):
        """深度辅助阶段可触发事件"""
        from backend.orchestration.state_machine import Stage, Event, get_next_events

        events = get_next_events(Stage.DEEP_ASSIST)
        assert Event.RESET in events


class TestIsValidTransition:
    """转移合法性检查测试"""

    def test_valid_transition_returns_true(self):
        """合法转移应返回True"""
        from backend.orchestration.state_machine import Stage, Event, is_valid_transition

        assert is_valid_transition(Stage.INFO_CONFIRM, Event.USER_CONFIRM) is True

    def test_invalid_transition_returns_false(self):
        """非法转移应返回False"""
        from backend.orchestration.state_machine import Stage, Event, is_valid_transition

        assert is_valid_transition(Stage.INFO_CONFIRM, Event.SCORE_PASS) is False

    def test_reset_always_valid(self):
        """RESET 事件始终合法"""
        from backend.orchestration.state_machine import Stage, Event, is_valid_transition

        for stage in Stage:
            assert is_valid_transition(stage, Event.RESET) is True


class TestTransitionResult:
    """转移结果测试"""

    def test_transition_result_has_message(self):
        """转移结果应包含消息"""
        from backend.orchestration.state_machine import Stage, Event, transition

        result = transition(Stage.INFO_CONFIRM, Event.USER_CONFIRM)
        assert isinstance(result.message, str)
        assert len(result.message) > 0

    def test_transition_result_message_for_retry(self):
        """回退转移消息应包含回退信息"""
        from backend.orchestration.state_machine import Stage, Event, transition

        result = transition(Stage.VALIDATION, Event.SCORE_FAIL)
        assert "回退" in result.message


class TestBackwardCompatibility:
    """向后兼容性测试"""

    def test_state_machine_class_initial_state(self):
        """StateMachine 初始状态应为 INIT"""
        from backend.orchestration.state_machine import StateMachine, State

        sm = StateMachine()
        assert sm.state == State.INIT

    def test_state_machine_advance(self):
        """StateMachine 推进应按顺序"""
        from backend.orchestration.state_machine import StateMachine, State

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

    def test_state_machine_advance_past_done(self):
        """StateMachine 推进超过 DONE 应保持 DONE"""
        from backend.orchestration.state_machine import StateMachine, State

        sm = StateMachine()
        for _ in range(10):
            sm.advance()
        assert sm.state == State.DONE

    def test_state_machine_reset(self):
        """StateMachine 重置应回到 INIT"""
        from backend.orchestration.state_machine import StateMachine, State

        sm = StateMachine()
        sm.advance()
        sm.advance()
        sm.reset()
        assert sm.state == State.INIT

    def test_state_enum_values(self):
        """State 枚举值应正确"""
        from backend.orchestration.state_machine import State

        assert State.INIT == "init"
        assert State.SEARCHING == "searching"
        assert State.REASONING == "reasoning"
        assert State.PROPOSAL == "proposal"
        assert State.DONE == "done"


class TestV7BackwardCompatibility:
    """v7 既有接口向后兼容测试"""

    def test_state_constants_exist(self):
        """v7 状态常量应存在"""
        from backend.orchestration.state_machine import (
            STATE_INIT,
            STATE_INSPIRING,
            STATE_REASONING,
            STATE_VALIDATING,
            STATE_COMPLETED,
            STATE_FAILED,
        )

        assert STATE_INIT == "init"
        assert STATE_INSPIRING == "inspiring"
        assert STATE_REASONING == "reasoning"
        assert STATE_VALIDATING == "validating"
        assert STATE_COMPLETED == "completed"
        assert STATE_FAILED == "failed"

    def test_orchestration_context_exists(self):
        """OrchestrationContext 应存在且可实例化"""
        from backend.orchestration.state_machine import OrchestrationContext

        ctx = OrchestrationContext(
            session_id="test",
            degree="master",
            discipline="计算机",
            mentor_info="导师信息",
        )
        assert ctx.session_id == "test"
        assert ctx.degree == "master"
        assert ctx.candidates == []
        assert ctx.proposals == []
        assert ctx.errors == []

    def test_orchestration_state_machine_exists(self):
        """OrchestrationStateMachine 应存在且可实例化"""
        from backend.orchestration.state_machine import (
            OrchestrationContext,
            OrchestrationStateMachine,
        )

        ctx = OrchestrationContext(
            session_id="test",
            degree="master",
            discipline="计算机",
            mentor_info="导师信息",
        )
        sm = OrchestrationStateMachine(ctx)
        assert sm.ctx is ctx

    def test_create_orchestration_exists(self):
        """create_orchestration 便捷函数应可用"""
        from backend.orchestration.state_machine import (
            create_orchestration,
            OrchestrationStateMachine,
        )

        sm = create_orchestration(
            session_id="test",
            degree="master",
            discipline="计算机",
            mentor_info="导师信息",
        )
        assert isinstance(sm, OrchestrationStateMachine)
        assert sm.ctx.session_id == "test"


class TestTransitionsTable:
    """状态转移表测试"""

    def test_transitions_table_has_6_entries(self):
        """转移表应有6个条目"""
        from backend.orchestration.state_machine import TRANSITIONS

        assert len(TRANSITIONS) == 6

    def test_transitions_cover_all_stages(self):
        """转移表应覆盖所有阶段（作为源状态）"""
        from backend.orchestration.state_machine import TRANSITIONS, Stage

        source_stages = {stage for (stage, _) in TRANSITIONS.keys()}
        for stage in Stage:
            assert stage in source_stages
