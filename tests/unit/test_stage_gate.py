"""五阶段门禁单元测试

测试 backend/constraints/stage_gate.py。
覆盖以下功能：
  - Stage 枚举：五阶段定义
  - GateResult 数据类：门禁检查结果
  - StageGate 数据类：阶段门禁定义
  - STAGE_GATES 字典：五阶段门禁配置
  - check_gate 函数：门禁检查逻辑

测试策略：
  - 纯逻辑测试，不依赖数据库
  - 覆盖五阶段各自的进入/退出条件
  - 边界条件：空数据、未知阶段、评分边界
"""
import os
import sys

import pytest

# ===== 项目根目录加入 sys.path =====
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.constraints.stage_gate import (
    Stage,
    GateResult,
    StageGate,
    STAGE_GATES,
    check_gate,
)


# ===== 测试类：Stage 枚举 =====

class TestStageEnum:
    """测试 Stage 枚举。"""

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

    def test_stage_from_value(self):
        """应能通过值创建枚举。"""
        assert Stage("info_confirm") == Stage.INFO_CONFIRM
        assert Stage("creativity") == Stage.CREATIVITY


# ===== 测试类：GateResult 数据类 =====

class TestGateResult:
    """测试 GateResult 数据类。"""

    def test_default_values(self):
        """默认值应正确。"""
        result = GateResult(passed=True, stage=Stage.INFO_CONFIRM)
        assert result.passed is True
        assert result.stage == Stage.INFO_CONFIRM
        assert result.message == ""
        assert result.data is None
        assert result.retry_stage is None

    def test_with_all_fields(self):
        """设置所有字段应正确。"""
        result = GateResult(
            passed=False,
            stage=Stage.VALIDATION,
            message="评分不足",
            data={"score": 50},
            retry_stage=Stage.CREATIVITY,
        )
        assert result.passed is False
        assert result.message == "评分不足"
        assert result.data["score"] == 50
        assert result.retry_stage == Stage.CREATIVITY


# ===== 测试类：StageGate 数据类 =====

class TestStageGateDataclass:
    """测试 StageGate 数据类。"""

    def test_default_values(self):
        """默认值应正确。"""
        gate = StageGate(
            stage=Stage.CREATIVITY,
            name="创意",
            description="生成候选",
            enter_condition="进入",
            exit_condition="退出",
        )
        assert gate.require_user_confirmation is False
        assert gate.min_score == 0
        assert gate.retry_on_fail is None

    def test_with_all_fields(self):
        """设置所有字段应正确。"""
        gate = StageGate(
            stage=Stage.VALIDATION,
            name="校验",
            description="评估候选",
            enter_condition="候选已生成",
            exit_condition="评分≥60",
            require_user_confirmation=False,
            min_score=60,
            retry_on_fail=Stage.CREATIVITY,
        )
        assert gate.min_score == 60
        assert gate.retry_on_fail == Stage.CREATIVITY


# ===== 测试类：STAGE_GATES 字典 =====

class TestStageGatesDict:
    """测试 STAGE_GATES 字典。"""

    def test_contains_all_stages(self):
        """应包含所有 5 个阶段的门禁定义。"""
        assert Stage.INFO_CONFIRM in STAGE_GATES
        assert Stage.CREATIVITY in STAGE_GATES
        assert Stage.VALIDATION in STAGE_GATES
        assert Stage.GENERATION in STAGE_GATES
        assert Stage.DEEP_ASSIST in STAGE_GATES

    def test_info_confirm_gate_config(self):
        """信息确权门禁应需要用户确认。"""
        gate = STAGE_GATES[Stage.INFO_CONFIRM]
        assert gate.require_user_confirmation is True
        assert gate.name == "信息确权"

    def test_creativity_gate_config(self):
        """创意门禁应不需要用户确认。"""
        gate = STAGE_GATES[Stage.CREATIVITY]
        assert gate.require_user_confirmation is False
        assert gate.name == "谱系解析与四维创意"

    def test_validation_gate_config(self):
        """校验门禁应有最低分 60 与回退阶段。"""
        gate = STAGE_GATES[Stage.VALIDATION]
        assert gate.min_score == 60
        assert gate.retry_on_fail == Stage.CREATIVITY

    def test_generation_gate_config(self):
        """生成门禁配置应正确。"""
        gate = STAGE_GATES[Stage.GENERATION]
        assert gate.name == "多粒度生成与降重脱敏"

    def test_deep_assist_gate_config(self):
        """深度辅助门禁配置应正确。"""
        gate = STAGE_GATES[Stage.DEEP_ASSIST]
        assert gate.name == "深度辅助闭环"


# ===== 测试类：check_gate - INFO_CONFIRM =====

class TestCheckGateInfoConfirm:
    """测试 check_gate - 信息确权阶段。"""

    def test_user_confirmed_passes(self):
        """用户已确认时应通过。"""
        result = check_gate(Stage.INFO_CONFIRM, {"user_confirmed": True})
        assert result.passed is True
        assert "用户已确认" in result.message

    def test_user_not_confirmed_fails(self):
        """用户未确认时应不通过。"""
        result = check_gate(Stage.INFO_CONFIRM, {"user_confirmed": False})
        assert result.passed is False
        assert "等待用户确认" in result.message

    def test_no_data_fails(self):
        """无数据时应不通过。"""
        result = check_gate(Stage.INFO_CONFIRM)
        assert result.passed is False

    def test_empty_data_fails(self):
        """空数据时应不通过。"""
        result = check_gate(Stage.INFO_CONFIRM, {})
        assert result.passed is False


# ===== 测试类：check_gate - CREATIVITY =====

class TestCheckGateCreativity:
    """测试 check_gate - 创意阶段。"""

    def test_three_candidates_passes(self):
        """3 个候选应通过。"""
        candidates = [{"title": f"候选{i}"} for i in range(3)]
        result = check_gate(Stage.CREATIVITY, {"candidates": candidates})
        assert result.passed is True

    def test_more_than_three_passes(self):
        """超过 3 个候选应通过。"""
        candidates = [{"title": f"候选{i}"} for i in range(5)]
        result = check_gate(Stage.CREATIVITY, {"candidates": candidates})
        assert result.passed is True

    def test_two_candidates_fails(self):
        """2 个候选应不通过。"""
        candidates = [{"title": "候选1"}, {"title": "候选2"}]
        result = check_gate(Stage.CREATIVITY, {"candidates": candidates})
        assert result.passed is False
        assert "候选不足" in result.message

    def test_empty_candidates_fails(self):
        """空候选列表应不通过。"""
        result = check_gate(Stage.CREATIVITY, {"candidates": []})
        assert result.passed is False

    def test_no_data_fails(self):
        """无数据时应不通过。"""
        result = check_gate(Stage.CREATIVITY)
        assert result.passed is False


# ===== 测试类：check_gate - VALIDATION =====

class TestCheckGateValidation:
    """测试 check_gate - 校验阶段。"""

    def test_score_above_threshold_passes(self):
        """评分≥60 应通过。"""
        evaluations = [{"score": 70}, {"score": 80}]
        result = check_gate(Stage.VALIDATION, {"evaluations": evaluations})
        assert result.passed is True

    def test_score_exactly_60_passes(self):
        """评分正好 60 应通过。"""
        evaluations = [{"score": 60}, {"score": 60}]
        result = check_gate(Stage.VALIDATION, {"evaluations": evaluations})
        assert result.passed is True

    def test_score_below_threshold_fails(self):
        """评分<60 应不通过并设置回退阶段。"""
        evaluations = [{"score": 50}, {"score": 55}]
        result = check_gate(Stage.VALIDATION, {"evaluations": evaluations})
        assert result.passed is False
        assert result.retry_stage == Stage.CREATIVITY

    def test_empty_evaluations_fails(self):
        """空评估列表应不通过。"""
        result = check_gate(Stage.VALIDATION, {"evaluations": []})
        assert result.passed is False
        assert "无评估结果" in result.message

    def test_no_data_fails(self):
        """无数据时应不通过。"""
        result = check_gate(Stage.VALIDATION)
        assert result.passed is False


# ===== 测试类：check_gate - GENERATION =====

class TestCheckGateGeneration:
    """测试 check_gate - 生成阶段。"""

    def test_non_empty_content_passes(self):
        """非空内容应通过。"""
        result = check_gate(Stage.GENERATION, {"content": "生成的内容"})
        assert result.passed is True

    def test_empty_content_fails(self):
        """空内容应不通过。"""
        result = check_gate(Stage.GENERATION, {"content": ""})
        assert result.passed is False

    def test_no_content_fails(self):
        """无 content 字段应不通过。"""
        result = check_gate(Stage.GENERATION, {})
        assert result.passed is False

    def test_no_data_fails(self):
        """无数据时应不通过。"""
        result = check_gate(Stage.GENERATION)
        assert result.passed is False


# ===== 测试类：check_gate - DEEP_ASSIST =====

class TestCheckGateDeepAssist:
    """测试 check_gate - 深度辅助阶段。"""

    def test_always_passes(self):
        """深度辅助阶段应始终通过。"""
        result = check_gate(Stage.DEEP_ASSIST)
        assert result.passed is True

    def test_passes_with_data(self):
        """带数据也应通过。"""
        result = check_gate(Stage.DEEP_ASSIST, {"any": "data"})
        assert result.passed is True


# ===== 测试类：check_gate - 异常情况 =====

class TestCheckGateEdgeCases:
    """测试 check_gate 异常情况。"""

    def test_unknown_stage_fails(self):
        """未知阶段应返回失败结果。"""
        # 使用一个不在 STAGE_GATES 中的值
        result = check_gate("unknown_stage")
        assert result.passed is False
        assert "未知阶段" in result.message
