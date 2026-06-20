"""Task 8 测试：验证 v9.0 全流程闭环导航流状态机

覆盖 v9.0 扩展（选题→开题→完成论文）：
- 新增阶段 THESIS_WRITING / DEFENSE_PREP / COMPLETED 存在性
- 新增事件 ENTER_THESIS_WRITING / ENTER_DEFENSE_PREP / DEFENSE_COMPLETED
- DEEP_ASSIST → THESIS_WRITING 转移
- THESIS_WRITING → DEFENSE_PREP 转移
- DEFENSE_PREP → COMPLETED 转移
- 跳过 DEEP_ASSIST（GENERATION → THESIS_WRITING 直接转移）
- 门禁检查阻止非法转移（无 GENERATION 完成不能进入 THESIS_WRITING）
- 全流程：INFO_CONFIRM → CREATIVITY → VALIDATION → GENERATION → DEEP_ASSIST
           → THESIS_WRITING → DEFENSE_PREP → COMPLETED
- 向后兼容：v8.0 五阶段转移仍然有效
- 门禁函数 check_thesis_writing_gate / check_defense_prep_gate
- GATE_REGISTRY 注册表
"""
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
)
from backend.constraints.stage_gate import (
    Stage as GateStage,
    GateResult,
    StageGate,
    STAGE_GATES,
    check_gate,
    check_thesis_writing_gate,
    check_defense_prep_gate,
    GATE_REGISTRY,
)


# ===== 测试类：新增阶段枚举 =====

class TestNewStagesExist:
    """测试 v9.0 新增阶段存在性。"""

    def test_thesis_writing_stage_exists(self):
        """THESIS_WRITING 阶段应存在。"""
        assert hasattr(Stage, "THESIS_WRITING")
        assert Stage.THESIS_WRITING == "thesis_writing"

    def test_defense_prep_stage_exists(self):
        """DEFENSE_PREP 阶段应存在。"""
        assert hasattr(Stage, "DEFENSE_PREP")
        assert Stage.DEFENSE_PREP == "defense_prep"

    def test_completed_stage_exists(self):
        """COMPLETED 阶段应存在。"""
        assert hasattr(Stage, "COMPLETED")
        assert Stage.COMPLETED == "completed"

    def test_stage_count_is_8(self):
        """阶段总数应为 8（v8.0 五阶段 + v9.0 三阶段）。"""
        assert len(list(Stage)) == 8

    def test_all_stages_listed(self):
        """应包含全部 8 个阶段。"""
        expected = {
            Stage.INFO_CONFIRM,
            Stage.CREATIVITY,
            Stage.VALIDATION,
            Stage.GENERATION,
            Stage.DEEP_ASSIST,
            Stage.THESIS_WRITING,
            Stage.DEFENSE_PREP,
            Stage.COMPLETED,
        }
        assert set(Stage) == expected


# ===== 测试类：新增事件枚举 =====

class TestNewEventsExist:
    """测试 v9.0 新增事件存在性。"""

    def test_enter_thesis_writing_event_exists(self):
        """ENTER_THESIS_WRITING 事件应存在。"""
        assert hasattr(Event, "ENTER_THESIS_WRITING")
        assert Event.ENTER_THESIS_WRITING == "enter_thesis_writing"

    def test_enter_defense_prep_event_exists(self):
        """ENTER_DEFENSE_PREP 事件应存在。"""
        assert hasattr(Event, "ENTER_DEFENSE_PREP")
        assert Event.ENTER_DEFENSE_PREP == "enter_defense_prep"

    def test_defense_completed_event_exists(self):
        """DEFENSE_COMPLETED 事件应存在。"""
        assert hasattr(Event, "DEFENSE_COMPLETED")
        assert Event.DEFENSE_COMPLETED == "defense_completed"

    def test_event_count_is_12(self):
        """事件总数应为 12（v8.0 九事件 + v9.0 三事件）。"""
        assert len(list(Event)) == 12


# ===== 测试类：新增转移表条目 =====

class TestNewTransitions:
    """测试 v9.0 新增转移表条目。"""

    def test_deep_assist_to_thesis_writing_in_transitions(self):
        """转移表应包含 DEEP_ASSIST → THESIS_WRITING。"""
        assert (Stage.DEEP_ASSIST, Event.ENTER_THESIS_WRITING) in TRANSITIONS
        assert TRANSITIONS[(Stage.DEEP_ASSIST, Event.ENTER_THESIS_WRITING)] == Stage.THESIS_WRITING

    def test_generation_to_thesis_writing_skip_in_transitions(self):
        """转移表应包含 GENERATION → THESIS_WRITING（跳过深度辅助）。"""
        assert (Stage.GENERATION, Event.ENTER_THESIS_WRITING) in TRANSITIONS
        assert TRANSITIONS[(Stage.GENERATION, Event.ENTER_THESIS_WRITING)] == Stage.THESIS_WRITING

    def test_thesis_writing_to_defense_prep_in_transitions(self):
        """转移表应包含 THESIS_WRITING → DEFENSE_PREP。"""
        assert (Stage.THESIS_WRITING, Event.ENTER_DEFENSE_PREP) in TRANSITIONS
        assert TRANSITIONS[(Stage.THESIS_WRITING, Event.ENTER_DEFENSE_PREP)] == Stage.DEFENSE_PREP

    def test_defense_prep_to_completed_in_transitions(self):
        """转移表应包含 DEFENSE_PREP → COMPLETED。"""
        assert (Stage.DEFENSE_PREP, Event.DEFENSE_COMPLETED) in TRANSITIONS
        assert TRANSITIONS[(Stage.DEFENSE_PREP, Event.DEFENSE_COMPLETED)] == Stage.COMPLETED

    def test_completed_reset_in_transitions(self):
        """转移表应包含 COMPLETED → RESET → INFO_CONFIRM。"""
        assert (Stage.COMPLETED, Event.RESET) in TRANSITIONS
        assert TRANSITIONS[(Stage.COMPLETED, Event.RESET)] == Stage.INFO_CONFIRM


# ===== 测试类：DEEP_ASSIST → THESIS_WRITING 转移 =====

class TestDeepAssistToThesisWriting:
    """测试 DEEP_ASSIST → THESIS_WRITING 转移。"""

    def test_transition_success(self):
        """DEEP_ASSIST + ENTER_THESIS_WRITING 应成功转移到 THESIS_WRITING。"""
        result = transition(Stage.DEEP_ASSIST, Event.ENTER_THESIS_WRITING)
        assert result.success is True
        assert result.from_stage == Stage.DEEP_ASSIST
        assert result.to_stage == Stage.THESIS_WRITING
        assert result.is_retry is False

    def test_transition_message(self):
        """转移消息应包含论文撰写信息。"""
        result = transition(Stage.DEEP_ASSIST, Event.ENTER_THESIS_WRITING)
        assert "论文撰写" in result.message

    def test_is_valid_transition(self):
        """该转移应被 is_valid_transition 判定为合法。"""
        assert is_valid_transition(Stage.DEEP_ASSIST, Event.ENTER_THESIS_WRITING) is True

    def test_next_events_includes_enter_thesis_writing(self):
        """DEEP_ASSIST 的可触发事件应包含 ENTER_THESIS_WRITING。"""
        events = get_next_events(Stage.DEEP_ASSIST)
        assert Event.ENTER_THESIS_WRITING in events


# ===== 测试类：THESIS_WRITING → DEFENSE_PREP 转移 =====

class TestThesisWritingToDefensePrep:
    """测试 THESIS_WRITING → DEFENSE_PREP 转移。"""

    def test_transition_success(self):
        """THESIS_WRITING + ENTER_DEFENSE_PREP 应成功转移到 DEFENSE_PREP。"""
        result = transition(Stage.THESIS_WRITING, Event.ENTER_DEFENSE_PREP)
        assert result.success is True
        assert result.from_stage == Stage.THESIS_WRITING
        assert result.to_stage == Stage.DEFENSE_PREP
        assert result.is_retry is False

    def test_transition_message(self):
        """转移消息应包含答辩准备信息。"""
        result = transition(Stage.THESIS_WRITING, Event.ENTER_DEFENSE_PREP)
        assert "答辩准备" in result.message

    def test_is_valid_transition(self):
        """该转移应被 is_valid_transition 判定为合法。"""
        assert is_valid_transition(Stage.THESIS_WRITING, Event.ENTER_DEFENSE_PREP) is True

    def test_next_events_includes_enter_defense_prep(self):
        """THESIS_WRITING 的可触发事件应包含 ENTER_DEFENSE_PREP。"""
        events = get_next_events(Stage.THESIS_WRITING)
        assert Event.ENTER_DEFENSE_PREP in events


# ===== 测试类：DEFENSE_PREP → COMPLETED 转移 =====

class TestDefensePrepToCompleted:
    """测试 DEFENSE_PREP → COMPLETED 转移。"""

    def test_transition_success(self):
        """DEFENSE_PREP + DEFENSE_COMPLETED 应成功转移到 COMPLETED。"""
        result = transition(Stage.DEFENSE_PREP, Event.DEFENSE_COMPLETED)
        assert result.success is True
        assert result.from_stage == Stage.DEFENSE_PREP
        assert result.to_stage == Stage.COMPLETED
        assert result.is_retry is False

    def test_transition_message(self):
        """转移消息应包含流程结束信息。"""
        result = transition(Stage.DEFENSE_PREP, Event.DEFENSE_COMPLETED)
        assert "流程结束" in result.message or "完成" in result.message

    def test_is_valid_transition(self):
        """该转移应被 is_valid_transition 判定为合法。"""
        assert is_valid_transition(Stage.DEFENSE_PREP, Event.DEFENSE_COMPLETED) is True

    def test_next_events_includes_defense_completed(self):
        """DEFENSE_PREP 的可触发事件应包含 DEFENSE_COMPLETED。"""
        events = get_next_events(Stage.DEFENSE_PREP)
        assert Event.DEFENSE_COMPLETED in events


# ===== 测试类：跳过 DEEP_ASSIST =====

class TestSkipDeepAssist:
    """测试跳过 DEEP_ASSIST（GENERATION → THESIS_WRITING 直接转移）。"""

    def test_generation_to_thesis_writing_success(self):
        """GENERATION + ENTER_THESIS_WRITING 应成功转移到 THESIS_WRITING。"""
        result = transition(Stage.GENERATION, Event.ENTER_THESIS_WRITING)
        assert result.success is True
        assert result.from_stage == Stage.GENERATION
        assert result.to_stage == Stage.THESIS_WRITING

    def test_skip_message_mentions_skip(self):
        """跳过转移的消息应提及跳过深度辅助。"""
        result = transition(Stage.GENERATION, Event.ENTER_THESIS_WRITING)
        assert "跳过" in result.message or "直接" in result.message

    def test_is_valid_skip_transition(self):
        """跳过转移应被判定为合法。"""
        assert is_valid_transition(Stage.GENERATION, Event.ENTER_THESIS_WRITING) is True

    def test_generation_has_two_forward_options(self):
        """GENERATION 应有两个前进选项：GENERATION_DONE 和 ENTER_THESIS_WRITING。"""
        events = get_next_events(Stage.GENERATION)
        assert Event.GENERATION_DONE in events
        assert Event.ENTER_THESIS_WRITING in events


# ===== 测试类：向后转移被阻止 =====

class TestBackwardTransitionsRejected:
    """测试向后转移被阻止（除显式 retry 外）。"""

    def test_thesis_writing_to_generation_rejected(self):
        """THESIS_WRITING → GENERATION（向后）应被拒绝。"""
        result = transition(Stage.THESIS_WRITING, Event.GENERATION_DONE)
        assert result.success is False
        assert result.to_stage == Stage.THESIS_WRITING  # 保持原阶段

    def test_defense_prep_to_thesis_writing_rejected(self):
        """DEFENSE_PREP → THESIS_WRITING（向后）应被拒绝。"""
        result = transition(Stage.DEFENSE_PREP, Event.ENTER_THESIS_WRITING)
        assert result.success is False

    def test_completed_to_defense_prep_rejected(self):
        """COMPLETED → DEFENSE_PREP（向后）应被拒绝。"""
        result = transition(Stage.COMPLETED, Event.ENTER_DEFENSE_PREP)
        assert result.success is False

    def test_thesis_writing_to_creativity_rejected(self):
        """THESIS_WRITING → CREATIVITY（跨阶段向后）应被拒绝。"""
        result = transition(Stage.THESIS_WRITING, Event.CANDIDATES_GENERATED)
        assert result.success is False

    def test_score_fail_still_allowed_as_retry(self):
        """SCORE_FAIL 回退（显式 retry）应仍然允许。"""
        result = transition(Stage.VALIDATION, Event.SCORE_FAIL)
        assert result.success is True
        assert result.is_retry is True
        assert result.to_stage == Stage.CREATIVITY


# ===== 测试类：RESET 从新阶段 =====

class TestResetFromNewStages:
    """测试从 v9.0 新阶段执行 RESET。"""

    def test_reset_from_thesis_writing(self):
        """从 THESIS_WRITING 重置应回到 INFO_CONFIRM。"""
        result = transition(Stage.THESIS_WRITING, Event.RESET)
        assert result.success is True
        assert result.to_stage == Stage.INFO_CONFIRM

    def test_reset_from_defense_prep(self):
        """从 DEFENSE_PREP 重置应回到 INFO_CONFIRM。"""
        result = transition(Stage.DEFENSE_PREP, Event.RESET)
        assert result.success is True
        assert result.to_stage == Stage.INFO_CONFIRM

    def test_reset_from_completed(self):
        """从 COMPLETED 重置应回到 INFO_CONFIRM。"""
        result = transition(Stage.COMPLETED, Event.RESET)
        assert result.success is True
        assert result.to_stage == Stage.INFO_CONFIRM

    def test_reset_valid_from_all_new_stages(self):
        """RESET 应从所有新阶段合法。"""
        for stage in [Stage.THESIS_WRITING, Stage.DEFENSE_PREP, Stage.COMPLETED]:
            assert is_valid_transition(stage, Event.RESET) is True


# ===== 测试类：全流程集成测试 =====

class TestFullFlowIntegration:
    """全流程集成测试：INFO_CONFIRM → ... → COMPLETED。"""

    def test_full_flow_through_deep_assist(self):
        """测试全流程（经 DEEP_ASSIST）：
        INFO_CONFIRM → CREATIVITY → VALIDATION → GENERATION
        → DEEP_ASSIST → THESIS_WRITING → DEFENSE_PREP → COMPLETED
        """
        # 1. INFO_CONFIRM → CREATIVITY
        r = transition(Stage.INFO_CONFIRM, Event.USER_CONFIRM)
        assert r.success and r.to_stage == Stage.CREATIVITY
        # 2. CREATIVITY → VALIDATION
        r = transition(Stage.CREATIVITY, Event.CANDIDATES_GENERATED)
        assert r.success and r.to_stage == Stage.VALIDATION
        # 3. VALIDATION → GENERATION
        r = transition(Stage.VALIDATION, Event.SCORE_PASS)
        assert r.success and r.to_stage == Stage.GENERATION
        # 4. GENERATION → DEEP_ASSIST
        r = transition(Stage.GENERATION, Event.GENERATION_DONE)
        assert r.success and r.to_stage == Stage.DEEP_ASSIST
        # 5. DEEP_ASSIST → THESIS_WRITING
        r = transition(Stage.DEEP_ASSIST, Event.ENTER_THESIS_WRITING)
        assert r.success and r.to_stage == Stage.THESIS_WRITING
        # 6. THESIS_WRITING → DEFENSE_PREP
        r = transition(Stage.THESIS_WRITING, Event.ENTER_DEFENSE_PREP)
        assert r.success and r.to_stage == Stage.DEFENSE_PREP
        # 7. DEFENSE_PREP → COMPLETED
        r = transition(Stage.DEFENSE_PREP, Event.DEFENSE_COMPLETED)
        assert r.success and r.to_stage == Stage.COMPLETED

    def test_full_flow_skipping_deep_assist(self):
        """测试全流程（跳过 DEEP_ASSIST）：
        INFO_CONFIRM → CREATIVITY → VALIDATION → GENERATION
        → THESIS_WRITING → DEFENSE_PREP → COMPLETED
        """
        # 1-3. 前三阶段
        stage = transition(Stage.INFO_CONFIRM, Event.USER_CONFIRM).to_stage
        assert stage == Stage.CREATIVITY
        stage = transition(stage, Event.CANDIDATES_GENERATED).to_stage
        assert stage == Stage.VALIDATION
        stage = transition(stage, Event.SCORE_PASS).to_stage
        assert stage == Stage.GENERATION
        # 4. GENERATION → THESIS_WRITING（跳过 DEEP_ASSIST）
        stage = transition(stage, Event.ENTER_THESIS_WRITING).to_stage
        assert stage == Stage.THESIS_WRITING
        # 5. THESIS_WRITING → DEFENSE_PREP
        stage = transition(stage, Event.ENTER_DEFENSE_PREP).to_stage
        assert stage == Stage.DEFENSE_PREP
        # 6. DEFENSE_PREP → COMPLETED
        stage = transition(stage, Event.DEFENSE_COMPLETED).to_stage
        assert stage == Stage.COMPLETED

    def test_full_flow_with_retry(self):
        """测试全流程含评分失败回退。"""
        # INFO_CONFIRM → CREATIVITY → VALIDATION
        stage = transition(Stage.INFO_CONFIRM, Event.USER_CONFIRM).to_stage
        stage = transition(stage, Event.CANDIDATES_GENERATED).to_stage
        # VALIDATION → CREATIVITY（评分失败回退）
        r = transition(stage, Event.SCORE_FAIL)
        assert r.success and r.to_stage == Stage.CREATIVITY and r.is_retry
        # 重新 CREATIVITY → VALIDATION → GENERATION → ... → COMPLETED
        stage = transition(Stage.CREATIVITY, Event.CANDIDATES_GENERATED).to_stage
        stage = transition(stage, Event.SCORE_PASS).to_stage
        stage = transition(stage, Event.GENERATION_DONE).to_stage
        stage = transition(stage, Event.ENTER_THESIS_WRITING).to_stage
        stage = transition(stage, Event.ENTER_DEFENSE_PREP).to_stage
        stage = transition(stage, Event.DEFENSE_COMPLETED).to_stage
        assert stage == Stage.COMPLETED


# ===== 测试类：向后兼容性 =====

class TestV8BackwardCompatibility:
    """测试 v8.0 五阶段向后兼容性。"""

    def test_v8_five_stage_flow_still_works(self):
        """v8.0 五阶段流程应仍然有效。"""
        r = transition(Stage.INFO_CONFIRM, Event.USER_CONFIRM)
        assert r.success and r.to_stage == Stage.CREATIVITY
        r = transition(Stage.CREATIVITY, Event.CANDIDATES_GENERATED)
        assert r.success and r.to_stage == Stage.VALIDATION
        r = transition(Stage.VALIDATION, Event.SCORE_PASS)
        assert r.success and r.to_stage == Stage.GENERATION
        r = transition(Stage.GENERATION, Event.GENERATION_DONE)
        assert r.success and r.to_stage == Stage.DEEP_ASSIST
        r = transition(Stage.DEEP_ASSIST, Event.RESET)
        assert r.success and r.to_stage == Stage.INFO_CONFIRM

    def test_v8_stages_preserved(self):
        """v8.0 五阶段应保留。"""
        assert Stage.INFO_CONFIRM == "info_confirm"
        assert Stage.CREATIVITY == "creativity"
        assert Stage.VALIDATION == "validation"
        assert Stage.GENERATION == "generation"
        assert Stage.DEEP_ASSIST == "deep_assist"

    def test_v8_events_preserved(self):
        """v8.0 事件应保留。"""
        assert Event.START == "start"
        assert Event.USER_CONFIRM == "user_confirm"
        assert Event.RESET == "reset"


# ===== 测试类：门禁 - THESIS_WRITING =====

class TestThesisWritingGate:
    """测试 THESIS_WRITING 阶段门禁。"""

    def test_gate_passes_with_proposal_and_generation_completed(self):
        """有提案、生成完成、大纲批准时应通过。"""
        data = {
            "proposal": {"title": "测试论题"},
            "generation_completed": True,
            "outline_approved": True,
        }
        result = check_gate(GateStage.THESIS_WRITING, data)
        assert result.passed is True

    def test_gate_fails_without_generation_completed(self):
        """未完成生成阶段时应不通过。"""
        data = {
            "proposal": {"title": "测试论题"},
            "generation_completed": False,
            "outline_approved": True,
        }
        result = check_gate(GateStage.THESIS_WRITING, data)
        assert result.passed is False
        assert "生成阶段" in result.message

    def test_gate_fails_without_proposal(self):
        """缺少提案时应不通过。"""
        data = {
            "proposal": None,
            "generation_completed": True,
            "outline_approved": True,
        }
        result = check_gate(GateStage.THESIS_WRITING, data)
        assert result.passed is False
        assert "提案" in result.message

    def test_gate_fails_without_outline_approved(self):
        """大纲未批准时应不通过。"""
        data = {
            "proposal": {"title": "测试论题"},
            "generation_completed": True,
            "outline_approved": False,
        }
        result = check_gate(GateStage.THESIS_WRITING, data)
        assert result.passed is False
        assert "大纲" in result.message

    def test_gate_fails_with_empty_data(self):
        """空数据时应不通过。"""
        result = check_gate(GateStage.THESIS_WRITING, {})
        assert result.passed is False


# ===== 测试类：门禁 - DEFENSE_PREP =====

class TestDefensePrepGate:
    """测试 DEFENSE_PREP 阶段门禁。"""

    def test_gate_passes_with_chapters_and_writing_completed(self):
        """有章节、论文撰写完成时应通过。"""
        data = {
            "thesis_writing_completed": True,
            "chapters": [{"title": "第一章"}, {"title": "第二章"}],
        }
        result = check_gate(GateStage.DEFENSE_PREP, data)
        assert result.passed is True

    def test_gate_fails_without_writing_completed(self):
        """未完成论文撰写时应不通过。"""
        data = {
            "thesis_writing_completed": False,
            "chapters": [{"title": "第一章"}],
        }
        result = check_gate(GateStage.DEFENSE_PREP, data)
        assert result.passed is False
        assert "论文撰写" in result.message

    def test_gate_fails_without_chapters(self):
        """缺少章节时应不通过。"""
        data = {
            "thesis_writing_completed": True,
            "chapters": [],
        }
        result = check_gate(GateStage.DEFENSE_PREP, data)
        assert result.passed is False
        assert "草稿" in result.message or "章节" in result.message

    def test_gate_fails_with_empty_data(self):
        """空数据时应不通过。"""
        result = check_gate(GateStage.DEFENSE_PREP, {})
        assert result.passed is False


# ===== 测试类：门禁 - COMPLETED =====

class TestCompletedGate:
    """测试 COMPLETED 阶段门禁。"""

    def test_gate_always_passes(self):
        """COMPLETED 阶段应始终通过。"""
        result = check_gate(GateStage.COMPLETED)
        assert result.passed is True


# ===== 测试类：会话级门禁函数 =====

class TestSessionGateFunctions:
    """测试 check_thesis_writing_gate / check_defense_prep_gate 函数。"""

    def test_thesis_writing_gate_passes(self):
        """check_thesis_writing_gate 满足条件时应返回 (True, reason)。"""
        data = {
            "proposal": {"title": "论题"},
            "generation_completed": True,
            "outline_approved": True,
        }
        passed, reason = check_thesis_writing_gate("session-1", data)
        assert passed is True
        assert "session-1" in reason

    def test_thesis_writing_gate_fails_no_generation(self):
        """未完成生成阶段时应返回 (False, reason)。"""
        data = {
            "proposal": {"title": "论题"},
            "generation_completed": False,
            "outline_approved": True,
        }
        passed, reason = check_thesis_writing_gate("session-1", data)
        assert passed is False
        assert "生成阶段" in reason

    def test_thesis_writing_gate_fails_no_proposal(self):
        """缺少提案时应返回 (False, reason)。"""
        data = {
            "proposal": None,
            "generation_completed": True,
            "outline_approved": True,
        }
        passed, reason = check_thesis_writing_gate("session-1", data)
        assert passed is False
        assert "提案" in reason

    def test_thesis_writing_gate_fails_no_outline(self):
        """大纲未批准时应返回 (False, reason)。"""
        data = {
            "proposal": {"title": "论题"},
            "generation_completed": True,
            "outline_approved": False,
        }
        passed, reason = check_thesis_writing_gate("session-1", data)
        assert passed is False
        assert "大纲" in reason

    def test_thesis_writing_gate_returns_tuple(self):
        """应返回 tuple[bool, str]。"""
        result = check_thesis_writing_gate("s", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)

    def test_defense_prep_gate_passes(self):
        """check_defense_prep_gate 满足条件时应返回 (True, reason)。"""
        data = {
            "thesis_writing_completed": True,
            "chapters": [{"title": "第一章"}],
        }
        passed, reason = check_defense_prep_gate("session-2", data)
        assert passed is True
        assert "session-2" in reason

    def test_defense_prep_gate_fails_no_writing(self):
        """未完成论文撰写时应返回 (False, reason)。"""
        data = {
            "thesis_writing_completed": False,
            "chapters": [{"title": "第一章"}],
        }
        passed, reason = check_defense_prep_gate("session-2", data)
        assert passed is False
        assert "论文撰写" in reason

    def test_defense_prep_gate_fails_no_chapters(self):
        """缺少章节时应返回 (False, reason)。"""
        data = {
            "thesis_writing_completed": True,
            "chapters": [],
        }
        passed, reason = check_defense_prep_gate("session-2", data)
        assert passed is False
        assert "草稿" in reason or "章节" in reason

    def test_defense_prep_gate_returns_tuple(self):
        """应返回 tuple[bool, str]。"""
        result = check_defense_prep_gate("s", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)


# ===== 测试类：GATE_REGISTRY 注册表 =====

class TestGateRegistry:
    """测试 GATE_REGISTRY 注册表。"""

    def test_registry_contains_thesis_writing(self):
        """注册表应包含 THESIS_WRITING。"""
        assert GateStage.THESIS_WRITING in GATE_REGISTRY

    def test_registry_contains_defense_prep(self):
        """注册表应包含 DEFENSE_PREP。"""
        assert GateStage.DEFENSE_PREP in GATE_REGISTRY

    def test_registry_functions_callable(self):
        """注册表中的函数应可调用。"""
        for stage, func in GATE_REGISTRY.items():
            assert callable(func)

    def test_registry_thesis_writing_function(self):
        """注册表中 THESIS_WRITING 对应 check_thesis_writing_gate。"""
        assert GATE_REGISTRY[GateStage.THESIS_WRITING] is check_thesis_writing_gate

    def test_registry_defense_prep_function(self):
        """注册表中 DEFENSE_PREP 对应 check_defense_prep_gate。"""
        assert GATE_REGISTRY[GateStage.DEFENSE_PREP] is check_defense_prep_gate


# ===== 测试类：STAGE_GATES 字典包含新阶段 =====

class TestStageGatesDictNewStages:
    """测试 STAGE_GATES 字典包含 v9.0 新阶段。"""

    def test_contains_thesis_writing_gate(self):
        """STAGE_GATES 应包含 THESIS_WRITING。"""
        assert GateStage.THESIS_WRITING in STAGE_GATES

    def test_contains_defense_prep_gate(self):
        """STAGE_GATES 应包含 DEFENSE_PREP。"""
        assert GateStage.DEFENSE_PREP in STAGE_GATES

    def test_contains_completed_gate(self):
        """STAGE_GATES 应包含 COMPLETED。"""
        assert GateStage.COMPLETED in STAGE_GATES

    def test_thesis_writing_gate_config(self):
        """THESIS_WRITING 门禁配置应正确。"""
        gate = STAGE_GATES[GateStage.THESIS_WRITING]
        assert gate.name == "论文撰写"

    def test_defense_prep_gate_config(self):
        """DEFENSE_PREP 门禁配置应正确。"""
        gate = STAGE_GATES[GateStage.DEFENSE_PREP]
        assert gate.name == "答辩准备"

    def test_completed_gate_config(self):
        """COMPLETED 门禁配置应正确。"""
        gate = STAGE_GATES[GateStage.COMPLETED]
        assert gate.name == "流程完成"


# ===== 测试类：门禁阻止非法转移 =====

class TestGatePreventsInvalidTransition:
    """测试门禁检查阻止非法转移（无 GENERATION 完成不能进入 THESIS_WRITING）。"""

    def test_cannot_enter_thesis_writing_without_generation(self):
        """未完成 GENERATION 时门禁应阻止进入 THESIS_WRITING。"""
        data = {
            "proposal": None,
            "generation_completed": False,
            "outline_approved": False,
        }
        result = check_gate(GateStage.THESIS_WRITING, data)
        assert result.passed is False

    def test_cannot_enter_defense_prep_without_thesis_writing(self):
        """未完成 THESIS_WRITING 时门禁应阻止进入 DEFENSE_PREP。"""
        data = {
            "thesis_writing_completed": False,
            "chapters": [],
        }
        result = check_gate(GateStage.DEFENSE_PREP, data)
        assert result.passed is False

    def test_gate_check_function_returns_false_without_generation(self):
        """check_thesis_writing_gate 未完成生成时应返回 False。"""
        passed, _ = check_thesis_writing_gate("s", {"generation_completed": False})
        assert passed is False

    def test_gate_check_function_returns_false_without_writing(self):
        """check_defense_prep_gate 未完成论文撰写时应返回 False。"""
        passed, _ = check_defense_prep_gate("s", {"thesis_writing_completed": False})
        assert passed is False
