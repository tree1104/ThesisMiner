"""硬约束规则库单元测试

测试 backend/constraints/hard_rules.py。
覆盖以下功能：
  - HardRuleViolation 数据类
  - validate_title: 标题约束验证
  - validate_timeline: 时间可行性验证
  - validate_discipline_match: 学科匹配验证
  - validate_advisor_alignment: 导师方向对齐验证
  - validate_duplication: 重复度验证
  - validate_all: 综合验证
  - has_errors: 错误级别检查

测试策略：
  - 纯逻辑测试，不依赖数据库
  - 覆盖硕士/博士不同学位的约束差异
  - 边界条件：空输入、边界值、禁止模式
"""
import os
import sys

import pytest

# ===== 项目根目录加入 sys.path =====
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.constraints.hard_rules import (
    HardRuleViolation,
    validate_title,
    validate_timeline,
    validate_discipline_match,
    validate_advisor_alignment,
    validate_duplication,
    validate_all,
    has_errors,
)


# ===== 测试类：HardRuleViolation 数据类 =====

class TestHardRuleViolation:
    """测试 HardRuleViolation 数据类。"""

    def test_default_field(self):
        """field 字段默认应为空字符串。"""
        v = HardRuleViolation(rule="test", severity="error", message="msg")
        assert v.field == ""

    def test_with_all_fields(self):
        """设置所有字段应正确。"""
        v = HardRuleViolation(
            rule="title_length",
            severity="error",
            message="标题过长",
            field="title",
        )
        assert v.rule == "title_length"
        assert v.severity == "error"
        assert v.message == "标题过长"
        assert v.field == "title"

    def test_severity_values(self):
        """severity 应支持 error 与 warning。"""
        v1 = HardRuleViolation(rule="r", severity="error", message="m")
        v2 = HardRuleViolation(rule="r", severity="warning", message="m")
        assert v1.severity == "error"
        assert v2.severity == "warning"


# ===== 测试类：validate_title =====

class TestValidateTitle:
    """测试 validate_title 函数。"""

    def test_empty_title_returns_error(self):
        """空标题应返回 error。"""
        violations = validate_title("")
        assert len(violations) == 1
        assert violations[0].severity == "error"
        assert violations[0].rule == "title_required"

    def test_valid_master_title(self):
        """合规硕士标题应无违规。"""
        violations = validate_title("基于深度学习的论文推荐", degree="master")
        # 标题长度 8-25 之间，无禁止模式
        error_violations = [v for v in violations if v.severity == "error"]
        assert len(error_violations) == 0

    def test_valid_doctor_title(self):
        """合规博士标题应无违规。"""
        violations = validate_title("基于知识图谱的学术论文推荐系统研究", degree="doctor")
        error_violations = [v for v in violations if v.severity == "error"]
        assert len(error_violations) == 0

    def test_master_title_too_long(self):
        """硕士标题超过 25 字应返回 error。"""
        long_title = "这是一个超过二十五个字的标题用于测试标题长度约束功能是否正常工作"
        violations = validate_title(long_title, degree="master")
        length_violations = [v for v in violations if v.rule == "title_length"]
        assert len(length_violations) == 1
        assert length_violations[0].severity == "error"

    def test_doctor_title_too_long(self):
        """博士标题超过 30 字应返回 error。"""
        long_title = "这是一个超过三十个字的标题用于测试博士论文标题长度约束功能是否正常工作呀"
        violations = validate_title(long_title, degree="doctor")
        length_violations = [v for v in violations if v.rule == "title_length"]
        assert len(length_violations) == 1

    def test_title_too_short_warning(self):
        """标题过短应返回 warning。"""
        violations = validate_title("短标题", degree="master")
        min_len_violations = [v for v in violations if v.rule == "title_min_length"]
        assert len(min_len_violations) == 1
        assert min_len_violations[0].severity == "warning"

    def test_title_with_forbidden_pattern_jiyu(self):
        """匹配"基于.*的研究"模式应返回 warning。"""
        violations = validate_title("基于深度学习的研究", degree="master")
        pattern_violations = [v for v in violations if v.rule == "title_pattern"]
        assert len(pattern_violations) >= 1

    def test_title_with_forbidden_pattern_yingyong(self):
        """匹配".*的应用研究"模式应返回 warning。"""
        violations = validate_title("深度学习的应用研究", degree="master")
        pattern_violations = [v for v in violations if v.rule == "title_pattern"]
        assert len(pattern_violations) >= 1

    def test_title_with_forbidden_pattern_taotao(self):
        """匹配"关于.*的探讨"模式应返回 warning。"""
        violations = validate_title("关于深度学习的探讨", degree="master")
        pattern_violations = [v for v in violations if v.rule == "title_pattern"]
        assert len(pattern_violations) >= 1

    def test_title_boundary_25_chars_master(self):
        """硕士标题正好 25 字应无长度 error。"""
        title = "一二三四五六七八九十一二三四五六七八九十一二三四"  # 25 字
        violations = validate_title(title, degree="master")
        length_violations = [v for v in violations if v.rule == "title_length"]
        assert len(length_violations) == 0

    def test_title_boundary_26_chars_master(self):
        """硕士标题 26 字应返回长度 error。"""
        title = "一二三四五六七八九十一二三四五六七八九十一二三四五六"  # 26 字
        violations = validate_title(title, degree="master")
        length_violations = [v for v in violations if v.rule == "title_length"]
        assert len(length_violations) == 1

    def test_title_boundary_30_chars_doctor(self):
        """博士标题正好 30 字应无长度 error。"""
        title = "一二三四五六七八九十一二三四五六七八九十一二三四五六七八九十"  # 30 字
        violations = validate_title(title, degree="doctor")
        length_violations = [v for v in violations if v.rule == "title_length"]
        assert len(length_violations) == 0

    def test_title_boundary_8_chars_no_warning(self):
        """标题正好 8 字应无过短 warning。"""
        title = "一二三四五六七八"  # 8 字
        violations = validate_title(title, degree="master")
        min_len_violations = [v for v in violations if v.rule == "title_min_length"]
        assert len(min_len_violations) == 0


# ===== 测试类：validate_timeline =====

class TestValidateTimeline:
    """测试 validate_timeline 函数。"""

    def test_empty_timeline_returns_error(self):
        """空时间规划应返回 error。"""
        violations = validate_timeline({})
        assert len(violations) == 1
        assert violations[0].rule == "timeline_required"
        assert violations[0].severity == "error"

    def test_none_timeline_returns_error(self):
        """None 时间规划应返回 error。"""
        violations = validate_timeline(None)
        assert len(violations) == 1
        assert violations[0].rule == "timeline_required"

    def test_valid_master_timeline(self):
        """合规硕士时间规划（≤12个月）应无违规。"""
        violations = validate_timeline({"total_months": 10}, degree="master")
        assert len(violations) == 0

    def test_valid_doctor_timeline(self):
        """合规博士时间规划（≤24个月）应无违规。"""
        violations = validate_timeline({"total_months": 20}, degree="doctor")
        assert len(violations) == 0

    def test_master_timeline_too_long(self):
        """硕士时间规划超过 12 个月应返回 error。"""
        violations = validate_timeline({"total_months": 15}, degree="master")
        assert len(violations) == 1
        assert violations[0].rule == "timeline_feasibility"
        assert violations[0].severity == "error"

    def test_doctor_timeline_too_long(self):
        """博士时间规划超过 24 个月应返回 error。"""
        violations = validate_timeline({"total_months": 30}, degree="doctor")
        assert len(violations) == 1
        assert violations[0].rule == "timeline_feasibility"

    def test_boundary_12_months_master(self):
        """硕士正好 12 个月应无违规。"""
        violations = validate_timeline({"total_months": 12}, degree="master")
        assert len(violations) == 0

    def test_boundary_24_months_doctor(self):
        """博士正好 24 个月应无违规。"""
        violations = validate_timeline({"total_months": 24}, degree="doctor")
        assert len(violations) == 0

    def test_zero_months_valid(self):
        """0 个月应无违规。"""
        violations = validate_timeline({"total_months": 0}, degree="master")
        assert len(violations) == 0


# ===== 测试类：validate_discipline_match =====

class TestValidateDisciplineMatch:
    """测试 validate_discipline_match 函数。"""

    def test_empty_discipline_returns_warning(self):
        """空学科应返回 warning。"""
        violations = validate_discipline_match("论题", "")
        assert len(violations) == 1
        assert violations[0].rule == "discipline_required"
        assert violations[0].severity == "warning"

    def test_with_discipline_no_violations(self):
        """有学科时应无违规。"""
        violations = validate_discipline_match("论题", "计算机科学")
        assert len(violations) == 0

    def test_with_any_topic_and_discipline(self):
        """任意论题与学科组合应无违规。"""
        violations = validate_discipline_match("深度学习研究", "人工智能")
        assert len(violations) == 0


# ===== 测试类：validate_advisor_alignment =====

class TestValidateAdvisorAlignment:
    """测试 validate_advisor_alignment 函数。"""

    def test_with_overlap_no_violations(self):
        """论题与导师方向有重叠关键词应无违规。"""
        violations = validate_advisor_alignment(
            "深度学习 教育应用", "深度学习 自然语言处理"
        )
        assert len(violations) == 0

    def test_no_overlap_returns_warning(self):
        """论题与导师方向无重叠应返回 warning。"""
        violations = validate_advisor_alignment(
            "深度学习研究", "教育学研究方法"
        )
        assert len(violations) == 1
        assert violations[0].rule == "advisor_alignment"
        assert violations[0].severity == "warning"

    def test_empty_advisor_no_violations(self):
        """空导师方向应无违规。"""
        violations = validate_advisor_alignment("论题", "")
        assert len(violations) == 0

    def test_empty_topic_no_violations(self):
        """空论题应无违规。"""
        violations = validate_advisor_alignment("", "导师方向")
        assert len(violations) == 0

    def test_both_empty_no_violations(self):
        """论题与导师方向都空应无违规。"""
        violations = validate_advisor_alignment("", "")
        assert len(violations) == 0

    def test_single_word_overlap(self):
        """单个关键词重叠应无违规。"""
        violations = validate_advisor_alignment("AI", "AI")
        assert len(violations) == 0


# ===== 测试类：validate_duplication =====

class TestValidateDuplication:
    """测试 validate_duplication 函数。"""

    def test_below_threshold_no_violations(self):
        """相似度低于阈值应无违规。"""
        violations = validate_duplication(0.2, threshold=0.3)
        assert len(violations) == 0

    def test_above_threshold_returns_error(self):
        """相似度高于阈值应返回 error。"""
        violations = validate_duplication(0.5, threshold=0.3)
        assert len(violations) == 1
        assert violations[0].rule == "duplication"
        assert violations[0].severity == "error"

    def test_at_threshold_no_violations(self):
        """相似度等于阈值应无违规。"""
        violations = validate_duplication(0.3, threshold=0.3)
        assert len(violations) == 0

    def test_zero_similarity_no_violations(self):
        """相似度为 0 应无违规。"""
        violations = validate_duplication(0.0)
        assert len(violations) == 0

    def test_custom_threshold(self):
        """自定义阈值应生效。"""
        violations = validate_duplication(0.4, threshold=0.5)
        assert len(violations) == 0

    def test_high_similarity_message_contains_percentage(self):
        """违规消息应包含百分比。"""
        violations = validate_duplication(0.65, threshold=0.3)
        assert "65.0%" in violations[0].message


# ===== 测试类：validate_all =====

class TestValidateAll:
    """测试 validate_all 函数。"""

    def test_all_valid_no_violations(self):
        """全部合规应无违规。"""
        violations = validate_all(
            topic="深度学习 论文推荐",
            degree="master",
            discipline="计算机科学",
            advisor_direction="深度学习 人工智能",
            timeline={"total_months": 10},
            similarity=0.1,
        )
        assert len(violations) == 0

    def test_multiple_violations(self):
        """多个违规应全部返回。"""
        violations = validate_all(
            topic="短",  # 标题过短
            degree="master",
            discipline="",  # 学科为空
            advisor_direction="无关方向",  # 导师方向不匹配
            timeline={},  # 时间规划为空
            similarity=0.5,  # 重复度高
        )
        assert len(violations) >= 4

    def test_validate_all_with_defaults(self):
        """使用默认参数应正常执行。"""
        violations = validate_all("合规标题测试")
        assert isinstance(violations, list)

    def test_validate_all_combines_all_checks(self):
        """应组合所有验证函数的结果。"""
        violations = validate_all(
            topic="",  # 标题为空
            degree="master",
            timeline=None,  # 时间为空
        )
        rules = {v.rule for v in violations}
        assert "title_required" in rules
        assert "timeline_required" in rules


# ===== 测试类：has_errors =====

class TestHasErrors:
    """测试 has_errors 函数。"""

    def test_with_error_violation(self):
        """含 error 级别违规应返回 True。"""
        violations = [
            HardRuleViolation("r1", "error", "m1"),
            HardRuleViolation("r2", "warning", "m2"),
        ]
        assert has_errors(violations) is True

    def test_with_only_warnings(self):
        """仅含 warning 级别违规应返回 False。"""
        violations = [
            HardRuleViolation("r1", "warning", "m1"),
            HardRuleViolation("r2", "warning", "m2"),
        ]
        assert has_errors(violations) is False

    def test_empty_list(self):
        """空列表应返回 False。"""
        assert has_errors([]) is False

    def test_mixed_severities(self):
        """混合级别违规应返回 True。"""
        violations = [
            HardRuleViolation("r1", "warning", "m1"),
            HardRuleViolation("r2", "error", "m2"),
            HardRuleViolation("r3", "warning", "m3"),
        ]
        assert has_errors(violations) is True

    def test_all_errors(self):
        """全部 error 应返回 True。"""
        violations = [
            HardRuleViolation("r1", "error", "m1"),
            HardRuleViolation("r2", "error", "m2"),
        ]
        assert has_errors(violations) is True
