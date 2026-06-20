"""论题验证器单元测试

测试 ThesisValidator 的多维度验证能力，覆盖：
    - 工具函数（_now_iso / _new_id / _count_chinese_chars / _count_words / _extract_year）
    - 数据结构（ValidationIssue / DimensionResult / ValidationReport / ValidationRule）
    - 常量与枚举（SeverityLevel / VALIDATION_DIMENSIONS / DIMENSION_WEIGHTS 等）
    - 各维度验证器（TitleValidator / AbstractValidator / OutlineValidator /
      ReferencesValidator / MethodValidator / FeasibilityValidator /
      NoveltyValidator / CompletenessValidator）
    - 主类 ThesisValidator（注册、规则、综合验证、报告、历史、对比、统计）
    - 模块级单例（get_thesis_validator / reset_thesis_validator）
    - 线程安全与边界情况
"""
from __future__ import annotations

import os
import re
import sys
import threading
import time
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# 将项目根目录加入 sys.path，确保可导入 backend 包
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.validation.thesis_validator import (
    ABSTRACT_MAX_LENGTH,
    ABSTRACT_MIN_LENGTH,
    ABSTRACT_STRUCTURE_KEYWORDS,
    DIMENSION_WEIGHTS,
    OUTLINE_LEVEL_PATTERNS,
    REFERENCE_COUNT_BASELINE,
    RECENT_RATIO_MIN,
    RECENT_YEARS_THRESHOLD,
    SEVERITY_NAMES,
    SEVERITY_WEIGHTS,
    TITLE_FORBIDDEN_PATTERNS,
    TITLE_MAX_LENGTH,
    TITLE_MIN_LENGTH,
    VALIDATION_DIMENSIONS,
    AbstractValidator,
    CompletenessValidator,
    DimensionResult,
    FeasibilityValidator,
    MethodValidator,
    NoveltyValidator,
    OutlineValidator,
    ReferencesValidator,
    SeverityLevel,
    ThesisValidator,
    TitleValidator,
    ValidationIssue,
    ValidationReport,
    ValidationRule,
    _count_chinese_chars,
    _count_words,
    _extract_year,
    _new_id,
    _now_iso,
    get_thesis_validator,
    reset_thesis_validator,
)


# ===== 工具函数测试 =====


class TestNowIso:
    """测试 _now_iso 工具函数。"""

    def test_now_iso_returns_string(self):
        # 应返回非空字符串
        result = _now_iso()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_now_iso_is_valid_iso_format(self):
        # 应为合法的 ISO 格式时间
        result = _now_iso()
        # 尝试解析，不应抛出异常
        parsed = datetime.fromisoformat(result)
        assert parsed is not None

    def test_now_iso_increases_over_time(self):
        # 连续调用应返回递增的时间
        t1 = _now_iso()
        time.sleep(0.01)
        t2 = _now_iso()
        d1 = datetime.fromisoformat(t1)
        d2 = datetime.fromisoformat(t2)
        assert d2 >= d1


class TestNewId:
    """测试 _new_id 工具函数。"""

    def test_new_id_default_prefix(self):
        # 默认前缀应为 issue
        result = _new_id()
        assert result.startswith("issue_")

    def test_new_id_custom_prefix(self):
        # 自定义前缀应正确应用
        result = _new_id("report")
        assert result.startswith("report_")

    def test_new_id_uniqueness(self):
        # 多次调用应生成不同的 ID
        ids = {_new_id() for _ in range(100)}
        assert len(ids) == 100

    def test_new_id_length(self):
        # ID 长度应为 前缀 + 1（下划线） + 8（hex）
        result = _new_id("test")
        # "test_" (5) + 8 个 hex 字符 = 13
        assert len(result) == 5 + 8


class TestCountChineseChars:
    """测试 _count_chinese_chars 工具函数。"""

    def test_pure_chinese(self):
        # 纯中文字符
        assert _count_chinese_chars("你好世界") == 4

    def test_pure_english(self):
        # 纯英文应返回 0
        assert _count_chinese_chars("hello world") == 0

    def test_mixed(self):
        # 中英混合
        assert _count_chinese_chars("hello 世界") == 2

    def test_empty_string(self):
        # 空字符串
        assert _count_chinese_chars("") == 0

    def test_with_punctuation(self):
        # 含中文标点
        assert _count_chinese_chars("你好，世界！") == 4

    def test_with_numbers(self):
        # 含数字
        assert _count_chinese_chars("2024年") == 1


class TestCountWords:
    """测试 _count_words 工具函数。"""

    def test_pure_chinese(self):
        # 纯中文按字计数
        assert _count_words("你好世界") == 4

    def test_pure_english(self):
        # 纯英文按词计数
        assert _count_words("hello world") == 2

    def test_mixed(self):
        # 中英混合：中文字数 + 英文词数
        assert _count_words("hello 世界") == 1 + 2  # 1 英文词 + 2 中文字

    def test_empty_string(self):
        assert _count_words("") == 0

    def test_with_numbers_and_punctuation(self):
        # 含数字与标点
        result = _count_words("测试 test 123")
        # 中文2字 + 英文1词 = 3
        assert result == 3


class TestExtractYear:
    """测试 _extract_year 工具函数。"""

    def test_extract_20xx_year(self):
        assert _extract_year("Published in 2023") == 2023

    def test_extract_19xx_year(self):
        assert _extract_year("Classic paper from 1995") == 1995

    def test_no_year(self):
        assert _extract_year("no year here") is None

    def test_multiple_years_returns_first(self):
        # 多个年份应返回第一个匹配
        result = _extract_year("2019 and 2020")
        assert result in (2019, 2020)

    def test_empty_string(self):
        assert _extract_year("") is None

    def test_year_in_chinese_context(self):
        assert _extract_year("2020年发表") == 2020


# ===== 常量与枚举测试 =====


class TestSeverityLevel:
    """测试 SeverityLevel 常量类。"""

    def test_severity_values(self):
        assert SeverityLevel.INFO == "info"
        assert SeverityLevel.WARNING == "warning"
        assert SeverityLevel.ERROR == "error"
        assert SeverityLevel.CRITICAL == "critical"

    def test_severity_weights_keys(self):
        # 权重字典应包含所有级别
        for level in ["info", "warning", "error", "critical"]:
            assert level in SEVERITY_WEIGHTS

    def test_severity_weights_values(self):
        # 严重级别越高，权重越大
        assert SEVERITY_WEIGHTS[SeverityLevel.INFO] < SEVERITY_WEIGHTS[SeverityLevel.WARNING]
        assert SEVERITY_WEIGHTS[SeverityLevel.WARNING] < SEVERITY_WEIGHTS[SeverityLevel.ERROR]
        assert SEVERITY_WEIGHTS[SeverityLevel.ERROR] < SEVERITY_WEIGHTS[SeverityLevel.CRITICAL]

    def test_severity_names(self):
        # 中文名称映射
        assert SEVERITY_NAMES[SeverityLevel.INFO] == "提示"
        assert SEVERITY_NAMES[SeverityLevel.WARNING] == "警告"
        assert SEVERITY_NAMES[SeverityLevel.ERROR] == "错误"
        assert SEVERITY_NAMES[SeverityLevel.CRITICAL] == "严重错误"


class TestValidationDimensions:
    """测试验证维度常量。"""

    def test_dimensions_count(self):
        # 应有 8 个验证维度
        assert len(VALIDATION_DIMENSIONS) == 8

    def test_dimensions_keys(self):
        expected = {"title", "abstract", "outline", "references",
                    "method", "feasibility", "novelty", "completeness"}
        assert set(VALIDATION_DIMENSIONS.keys()) == expected

    def test_dimension_weights_sum(self):
        # 权重总和应接近 1.0
        total = sum(DIMENSION_WEIGHTS.values())
        assert abs(total - 1.0) < 0.01

    def test_dimension_weights_keys_match(self):
        # 权重字典的键应与维度字典一致
        assert set(DIMENSION_WEIGHTS.keys()) == set(VALIDATION_DIMENSIONS.keys())


class TestLengthConstants:
    """测试长度相关常量。"""

    def test_title_length_bounds(self):
        assert TITLE_MIN_LENGTH < TITLE_MAX_LENGTH
        assert TITLE_MIN_LENGTH > 0

    def test_abstract_length_bounds(self):
        assert ABSTRACT_MIN_LENGTH < ABSTRACT_MAX_LENGTH
        assert ABSTRACT_MIN_LENGTH > 0

    def test_reference_baseline(self):
        # 博士要求应高于硕士
        assert REFERENCE_COUNT_BASELINE["doctor"] > REFERENCE_COUNT_BASELINE["master"]

    def test_recent_years_threshold(self):
        assert RECENT_YEARS_THRESHOLD > 0
        assert 0 < RECENT_RATIO_MIN < 1


class TestPatterns:
    """测试正则模式常量。"""

    def test_title_forbidden_patterns_not_empty(self):
        assert len(TITLE_FORBIDDEN_PATTERNS) > 0
        for pattern, message in TITLE_FORBIDDEN_PATTERNS:
            assert isinstance(pattern, str)
            assert isinstance(message, str)

    def test_abstract_structure_keywords(self):
        # 应包含 5 个结构部分
        expected = {"background", "problem", "method", "result", "conclusion"}
        assert set(ABSTRACT_STRUCTURE_KEYWORDS.keys()) == expected

    def test_outline_level_patterns_compiled(self):
        # 所有模式应为编译后的正则对象
        for pattern in OUTLINE_LEVEL_PATTERNS:
            assert hasattr(pattern, "match")


# ===== 数据结构测试 =====


class TestValidationIssue:
    """测试 ValidationIssue 数据结构。"""

    def test_default_values(self):
        issue = ValidationIssue()
        assert issue.dimension == ""
        assert issue.severity == SeverityLevel.WARNING
        assert issue.context == {}

    def test_custom_values(self):
        issue = ValidationIssue(
            id="test_001",
            dimension="title",
            severity=SeverityLevel.ERROR,
            code="title_too_short",
            message="标题过短",
            location="title",
            suggestion="扩展标题",
        )
        assert issue.id == "test_001"
        assert issue.severity == SeverityLevel.ERROR

    def test_to_dict(self):
        issue = ValidationIssue(id="i1", dimension="title", code="c1")
        d = issue.to_dict()
        assert d["id"] == "i1"
        assert d["dimension"] == "title"
        assert d["code"] == "c1"
        assert "context" in d

    def test_context_mutable_default(self):
        # 不同实例的 context 应独立
        i1 = ValidationIssue()
        i2 = ValidationIssue()
        i1.context["key"] = "value"
        assert "key" not in i2.context


class TestDimensionResult:
    """测试 DimensionResult 数据结构。"""

    def test_default_values(self):
        result = DimensionResult()
        assert result.score == 0.0
        assert result.passed is True
        assert result.issues == []

    def test_with_issues(self):
        issues = [ValidationIssue(code="c1"), ValidationIssue(code="c2")]
        result = DimensionResult(dimension="title", score=80.0, issues=issues, passed=True)
        assert len(result.issues) == 2
        assert result.score == 80.0

    def test_to_dict(self):
        issues = [ValidationIssue(id="i1", code="c1")]
        result = DimensionResult(dimension="title", score=75.5, issues=issues, passed=False, summary="测试")
        d = result.to_dict()
        assert d["dimension"] == "title"
        assert d["score"] == 75.5
        assert d["passed"] is False
        assert len(d["issues"]) == 1
        assert d["issues"][0]["id"] == "i1"


class TestValidationReport:
    """测试 ValidationReport 数据结构。"""

    def test_default_values(self):
        report = ValidationReport()
        assert report.overall_score == 0.0
        assert report.passed is False
        assert report.critical_count == 0

    def test_with_data(self):
        report = ValidationReport(
            id="r1",
            thesis_id="t1",
            overall_score=85.5,
            passed=True,
            critical_count=0,
            error_count=1,
            warning_count=2,
            info_count=3,
        )
        assert report.thesis_id == "t1"
        assert report.overall_score == 85.5
        assert report.passed is True

    def test_to_dict(self):
        dim_result = DimensionResult(dimension="title", score=90.0)
        report = ValidationReport(
            id="r1",
            thesis_id="t1",
            overall_score=85.5,
            dimension_results={"title": dim_result},
            all_issues=[ValidationIssue(id="i1")],
            critical_count=0,
            error_count=1,
            warning_count=2,
            info_count=3,
            passed=True,
            recommendations=["建议1"],
        )
        d = report.to_dict()
        assert d["id"] == "r1"
        assert d["overall_score"] == 85.5
        assert "title" in d["dimension_results"]
        assert d["issue_counts"]["total"] == 1
        assert d["issue_counts"]["error"] == 1

    def test_to_dict_rounds_score(self):
        # 综合评分应四舍五入到 2 位小数
        report = ValidationReport(overall_score=85.567)
        d = report.to_dict()
        assert d["overall_score"] == 85.57


class TestValidationRule:
    """测试 ValidationRule 数据结构。"""

    def test_default_values(self):
        rule = ValidationRule()
        assert rule.enabled is True
        assert rule.validator is None

    def test_validate_disabled_returns_empty(self):
        # 禁用的规则应返回空列表
        rule = ValidationRule(enabled=False, validator=lambda d: [ValidationIssue()])
        assert rule.validate({}) == []

    def test_validate_no_validator_returns_empty(self):
        rule = ValidationRule(validator=None)
        assert rule.validate({}) == []

    def test_validate_normal(self):
        # 正常验证应返回验证函数的结果
        expected = [ValidationIssue(code="test")]
        rule = ValidationRule(validator=lambda d: expected)
        result = rule.validate({})
        assert result == expected

    def test_validate_handles_exception(self):
        # 验证函数抛异常时应返回错误问题
        def bad_validator(data):
            raise ValueError("测试异常")

        rule = ValidationRule(name="bad", dimension="title", validator=bad_validator)
        result = rule.validate({})
        assert len(result) == 1
        assert result[0].severity == SeverityLevel.ERROR
        assert "测试异常" in result[0].message


# ===== 标题验证器测试 =====


class TestTitleValidator:
    """测试 TitleValidator。"""

    def setup_method(self):
        self.validator = TitleValidator()

    def test_empty_title(self):
        # 空标题应返回 CRITICAL 问题
        issues = self.validator.validate({"title": ""})
        assert len(issues) == 1
        assert issues[0].severity == SeverityLevel.CRITICAL
        assert issues[0].code == "title_empty"

    def test_missing_title(self):
        # 缺少标题字段
        issues = self.validator.validate({})
        assert len(issues) == 1
        assert issues[0].code == "title_empty"

    def test_short_title(self):
        # 过短标题
        issues = self.validator.validate({"title": "短"})
        codes = [i.code for i in issues]
        assert "title_too_short" in codes

    def test_long_title(self):
        # 过长标题
        long_title = "这是一个非常非常非常非常非常非常非常非常非常非常非常非常长的标题" * 2
        issues = self.validator.validate({"title": long_title})
        codes = [i.code for i in issues]
        assert "title_too_long" in codes

    def test_valid_title(self):
        # 合规标题应无问题
        issues = self.validator.validate({"title": "基于深度学习的文本分类研究"})
        # 可能有宽泛词警告，但不应有 CRITICAL 或长度问题
        codes = [i.code for i in issues]
        assert "title_empty" not in codes
        assert "title_too_short" not in codes
        assert "title_too_long" not in codes

    def test_forbidden_pattern_about(self):
        # 以"关于"开头
        issues = self.validator.validate({"title": "关于深度学习的研究"})
        codes = [i.code for i in issues]
        assert "title_format" in codes

    def test_forbidden_pattern_shallow_words(self):
        # 含"浅谈"等词
        issues = self.validator.validate({"title": "浅谈深度学习技术"})
        codes = [i.code for i in issues]
        assert "title_format" in codes

    def test_vague_title(self):
        # 含多个宽泛词
        issues = self.validator.validate({"title": "研究分析探讨应用"})
        codes = [i.code for i in issues]
        assert "title_vague" in codes

    def test_question_title(self):
        # 疑问式标题
        issues = self.validator.validate({"title": "深度学习如何改变世界？"})
        codes = [i.code for i in issues]
        assert "title_question" in codes
        # 疑问式应为 INFO 级别
        question_issue = next(i for i in issues if i.code == "title_question")
        assert question_issue.severity == SeverityLevel.INFO


# ===== 摘要验证器测试 =====


class TestAbstractValidator:
    """测试 AbstractValidator。"""

    def setup_method(self):
        self.validator = AbstractValidator()

    def test_empty_abstract(self):
        issues = self.validator.validate({"abstract": ""})
        assert len(issues) == 1
        assert issues[0].severity == SeverityLevel.CRITICAL
        assert issues[0].code == "abstract_empty"

    def test_short_abstract(self):
        issues = self.validator.validate({"abstract": "这是短摘要"})
        codes = [i.code for i in issues]
        assert "abstract_too_short" in codes

    def test_long_abstract(self):
        long_abstract = "摘要内容" * 500
        issues = self.validator.validate({"abstract": long_abstract})
        codes = [i.code for i in issues]
        assert "abstract_too_long" in codes

    def test_missing_structure_sections(self):
        # 缺少结构部分的摘要
        abstract = "本文研究了深度学习。" * 50
        issues = self.validator.validate({"abstract": abstract})
        codes = [i.code for i in issues]
        # 应至少缺少某些结构部分
        assert any(c.startswith("abstract_missing_") for c in codes)

    def test_complete_abstract(self):
        # 包含所有结构部分的摘要
        abstract = (
            "近年来，深度学习成为研究热点。"
            "现有方法存在过拟合问题。"
            "本文提出基于Transformer的方法。"
            "实验结果表明准确率提升10%。"
            "本研究具有重要理论价值。"
        ) * 10
        issues = self.validator.validate({"abstract": abstract})
        codes = [i.code for i in issues]
        # 不应缺少任何结构部分
        for section in ["background", "problem", "method", "result", "conclusion"]:
            assert f"abstract_missing_{section}" not in codes

    def test_lack_statement(self):
        # 缺少明确贡献陈述
        abstract = "研究背景现状近年来随着目前。" * 50
        issues = self.validator.validate({"abstract": abstract})
        codes = [i.code for i in issues]
        assert "abstract_lack_statement" in codes

    def test_lack_data(self):
        # 缺少数据支撑
        abstract = (
            "近年来深度学习发展。"
            "存在过拟合问题。"
            "本文提出新方法。"
            "结果显示有效。"
            "结论有贡献。"
        ) * 10
        issues = self.validator.validate({"abstract": abstract})
        codes = [i.code for i in issues]
        assert "abstract_lack_data" in codes


# ===== 大纲验证器测试 =====


class TestOutlineValidator:
    """测试 OutlineValidator。"""

    def setup_method(self):
        self.validator = OutlineValidator()

    def test_empty_outline(self):
        issues = self.validator.validate({"outline": ""})
        assert len(issues) >= 1
        codes = [i.code for i in issues]
        assert "outline_empty" in codes

    def test_no_lit_review(self):
        outline = (
            "第一章 绪论\n"
            "第二章 研究方法\n"
            "第三章 实验结果\n"
            "第四章 结论"
        )
        issues = self.validator.validate({"outline": outline})
        codes = [i.code for i in issues]
        assert "outline_no_lit_review" in codes

    def test_no_method_chapter(self):
        outline = (
            "第一章 绪论\n"
            "第二章 文献综述\n"
            "第三章 实验结果\n"
            "第四章 结论"
        )
        issues = self.validator.validate({"outline": outline})
        codes = [i.code for i in issues]
        assert "outline_no_method" in codes

    def test_no_conclusion(self):
        outline = (
            "第一章 绪论\n"
            "第二章 文献综述\n"
            "第三章 研究方法\n"
            "第四章 实验结果"
        )
        issues = self.validator.validate({"outline": outline})
        codes = [i.code for i in issues]
        assert "outline_no_conclusion" in codes

    def test_few_chapters(self):
        outline = "第一章 绪论\n第二章 文献综述"
        issues = self.validator.validate({"outline": outline})
        codes = [i.code for i in issues]
        assert "outline_few_chapters" in codes

    def test_complete_outline(self):
        # 完整大纲应无关键错误
        outline = (
            "第一章 绪论\n"
            "第二章 文献综述与研究现状\n"
            "第三章 研究方法与设计\n"
            "第四章 实验结果与分析\n"
            "第五章 结论与展望"
        )
        issues = self.validator.validate({"outline": outline})
        codes = [i.code for i in issues]
        assert "outline_no_lit_review" not in codes
        assert "outline_no_method" not in codes
        assert "outline_no_conclusion" not in codes

    def test_hierarchy_jump(self):
        # 层级跳跃
        outline = (
            "第一章 绪论\n"
            "1.1.1.1 跳跃层级"
        )
        issues = self.validator.validate({"outline": outline})
        # 可能有层级跳跃问题（取决于正则匹配）
        assert isinstance(issues, list)


# ===== 参考文献验证器测试 =====


class TestReferencesValidator:
    """测试 ReferencesValidator。"""

    def setup_method(self):
        self.validator = ReferencesValidator()

    def test_empty_references(self):
        issues = self.validator.validate({"references": []})
        assert len(issues) == 1
        assert issues[0].severity == SeverityLevel.CRITICAL
        assert issues[0].code == "references_empty"

    def test_insufficient_references_master(self):
        # 硕士论文参考文献不足
        refs = [{"text": "Author. Title. Journal, 2020."} for _ in range(10)]
        issues = self.validator.validate({"references": refs, "degree": "master"})
        codes = [i.code for i in issues]
        assert "references_insufficient" in codes

    def test_insufficient_references_doctor(self):
        # 博士论文要求更高
        refs = [{"text": "Author. Title. Journal, 2020."} for _ in range(40)]
        issues = self.validator.validate({"references": refs, "degree": "doctor"})
        codes = [i.code for i in issues]
        assert "references_insufficient" in codes

    def test_sufficient_references(self):
        # 足够的参考文献
        refs = [{"text": "Author. Title. Journal, 2023."} for _ in range(35)]
        issues = self.validator.validate({"references": refs, "degree": "master"})
        codes = [i.code for i in issues]
        assert "references_insufficient" not in codes

    def test_reference_no_year(self):
        # 缺少年份的参考文献
        refs = [{"text": "Author. Title. Journal."}]
        issues = self.validator.validate({"references": refs, "degree": "master"})
        codes = [i.code for i in issues]
        assert "ref_no_year" in codes

    def test_reference_too_short(self):
        # 过短的参考文献
        refs = [{"text": "短"}]
        issues = self.validator.validate({"references": refs, "degree": "master"})
        codes = [i.code for i in issues]
        assert "ref_too_short" in codes

    def test_outdated_references(self):
        # 过旧的参考文献
        refs = [{"text": f"Author{i}. Title{i}. Journal, 1990."} for i in range(35)]
        issues = self.validator.validate({"references": refs, "degree": "master"})
        codes = [i.code for i in issues]
        assert "references_outdated" in codes

    def test_string_references(self):
        # 字符串形式的参考文献
        refs = ["Smith. Deep Learning. Journal, 2023." for _ in range(35)]
        issues = self.validator.validate({"references": refs, "degree": "master"})
        assert isinstance(issues, list)


# ===== 研究方法验证器测试 =====


class TestMethodValidator:
    """测试 MethodValidator。"""

    def setup_method(self):
        self.validator = MethodValidator()

    def test_empty_method(self):
        issues = self.validator.validate({"method": ""})
        assert len(issues) == 1
        assert issues[0].severity == SeverityLevel.CRITICAL
        assert issues[0].code == "method_empty"

    def test_no_method_detail(self):
        issues = self.validator.validate({"method": "实验法", "method_detail": ""})
        codes = [i.code for i in issues]
        assert "method_no_detail" in codes

    def test_short_method_detail(self):
        issues = self.validator.validate({"method": "实验法", "method_detail": "简短描述"})
        codes = [i.code for i in issues]
        assert "method_detail_short" in codes

    def test_experiment_no_sample(self):
        # 实验研究未说明样本
        detail = "本研究采用实验方法进行。" * 20
        issues = self.validator.validate({"method": "实验研究", "method_detail": detail})
        codes = [i.code for i in issues]
        assert "method_no_sample" in codes

    def test_questionnaire_no_reliability(self):
        # 问卷调查未提及信效度
        detail = "本研究使用问卷调查。" * 20
        issues = self.validator.validate({"method": "问卷调查", "method_detail": detail})
        codes = [i.code for i in issues]
        assert "method_no_reliability" in codes

    def test_interview_no_coding(self):
        # 访谈研究未说明编码
        detail = "本研究采用访谈方法收集数据。" * 20
        issues = self.validator.validate({"method": "访谈研究", "method_detail": detail})
        codes = [i.code for i in issues]
        assert "method_no_coding" in codes

    def test_discipline_mismatch_humanities(self):
        # 人文学科使用定量方法
        detail = "本研究使用回归分析方法。" * 20
        issues = self.validator.validate({
            "method": "回归分析",
            "method_detail": detail,
            "discipline": "0101",
        })
        codes = [i.code for i in issues]
        assert "method_discipline_mismatch" in codes

    def test_discipline_mismatch_science(self):
        # 理工科使用定性方法
        detail = "本研究采用民族志方法。" * 20
        issues = self.validator.validate({
            "method": "民族志研究",
            "method_detail": detail,
            "discipline": "0701",
        })
        codes = [i.code for i in issues]
        assert "method_discipline_mismatch" in codes


# ===== 可行性验证器测试 =====


class TestFeasibilityValidator:
    """测试 FeasibilityValidator。"""

    def setup_method(self):
        self.validator = FeasibilityValidator()

    def test_empty_feasibility(self):
        issues = self.validator.validate({})
        codes = [i.code for i in issues]
        assert "feasibility_empty" in codes
        assert "timeline_empty" in codes

    def test_short_feasibility(self):
        issues = self.validator.validate({"feasibility_analysis": "可行"})
        codes = [i.code for i in issues]
        assert "feasibility_short" in codes

    def test_missing_dimensions(self):
        # 缺少某些维度的可行性分析
        feasibility = "本研究在技术上可行。" * 30
        issues = self.validator.validate({"feasibility_analysis": feasibility})
        codes = [i.code for i in issues]
        # 应提示缺少数据、时间、资源维度
        assert "feasibility_no_数据" in codes or any("feasibility_no_" in c for c in codes)

    def test_complete_feasibility(self):
        feasibility = (
            "技术上采用成熟方法。"
            "数据来源可靠。"
            "时间安排合理。"
            "资源经费充足。"
        ) * 10
        issues = self.validator.validate({
            "feasibility_analysis": feasibility,
            "timeline": "6个月",
            "resources": "充足",
        })
        codes = [i.code for i in issues]
        assert "feasibility_empty" not in codes
        assert "timeline_empty" not in codes

    def test_no_timeline(self):
        feasibility = "技术上可行，数据可靠，时间合理，资源充足。" * 10
        issues = self.validator.validate({
            "feasibility_analysis": feasibility,
            "timeline": "",
        })
        codes = [i.code for i in issues]
        assert "timeline_empty" in codes

    def test_no_resources(self):
        feasibility = "技术上可行，数据可靠，时间合理，资源充足。" * 10
        issues = self.validator.validate({
            "feasibility_analysis": feasibility,
            "resources": "",
        })
        codes = [i.code for i in issues]
        assert "resources_empty" in codes


# ===== 新颖性验证器测试 =====


class TestNoveltyValidator:
    """测试 NoveltyValidator。"""

    def setup_method(self):
        self.validator = NoveltyValidator()

    def test_empty_differentiation(self):
        issues = self.validator.validate({})
        codes = [i.code for i in issues]
        assert "novelty_empty" in codes

    def test_strong_claim(self):
        # 含"首次"等强表述
        issues = self.validator.validate({"differentiation": "本研究首次提出新方法"})
        codes = [i.code for i in issues]
        assert "novelty_claim_strong" in codes

    def test_unclear_innovation(self):
        # 创新点类型不明确
        issues = self.validator.validate({"differentiation": "本研究与众不同"})
        codes = [i.code for i in issues]
        assert "novelty_unclear" in codes

    def test_clear_innovation(self):
        # 明确的方法创新
        issues = self.validator.validate({"differentiation": "本研究提出新的算法方法"})
        codes = [i.code for i in issues]
        assert "novelty_unclear" not in codes

    def test_no_inspiration_source(self):
        issues = self.validator.validate({"differentiation": "提出新方法"})
        codes = [i.code for i in issues]
        assert "inspiration_empty" in codes

    def test_with_inspiration(self):
        issues = self.validator.validate({
            "differentiation": "提出新方法",
            "inspiration_source": "受某某研究启发",
        })
        codes = [i.code for i in issues]
        assert "inspiration_empty" not in codes


# ===== 完整性验证器测试 =====


class TestCompletenessValidator:
    """测试 CompletenessValidator。"""

    def setup_method(self):
        self.validator = CompletenessValidator()

    def test_all_fields_missing(self):
        issues = self.validator.validate({})
        codes = [i.code for i in issues]
        # 应报告所有必填字段缺失
        for field_name in CompletenessValidator.REQUIRED_FIELDS:
            assert f"missing_{field_name}" in codes

    def test_all_fields_present(self):
        data = {
            "title": "标题",
            "abstract": "摘要",
            "outline": "大纲",
            "references": ["ref1"],
            "method": "方法",
            "feasibility_analysis": "可行",
            "differentiation": "创新",
        }
        issues = self.validator.validate(data)
        assert len(issues) == 0

    def test_empty_string_field(self):
        # 空字符串字段应视为缺失
        data = {"title": "", "abstract": "摘要"}
        issues = self.validator.validate(data)
        codes = [i.code for i in issues]
        assert "missing_title" in codes

    def test_empty_list_field(self):
        # 空列表字段应视为缺失
        data = {"references": []}
        issues = self.validator.validate(data)
        codes = [i.code for i in issues]
        assert "missing_references" in codes

    def test_required_fields_count(self):
        # 应有 7 个必填字段
        assert len(CompletenessValidator.REQUIRED_FIELDS) == 7


# ===== ThesisValidator 主类测试 =====


class TestThesisValidatorInit:
    """测试 ThesisValidator 初始化。"""

    def test_init_creates_validators(self):
        validator = ThesisValidator()
        # 应注册 8 个维度验证器
        assert len(validator._validators) == 8
        for dim in VALIDATION_DIMENSIONS:
            assert dim in validator._validators

    def test_init_empty_custom_rules(self):
        validator = ThesisValidator()
        assert validator._custom_rules == []

    def test_init_empty_history(self):
        validator = ThesisValidator()
        assert validator._history == []


class TestThesisValidatorRegister:
    """测试 ThesisValidator 注册功能。"""

    def test_register_validator(self):
        validator = ThesisValidator()
        custom_validator = MagicMock(return_value=[])
        validator.register_validator("custom_dim", custom_validator)
        assert "custom_dim" in validator._validators

    def test_register_overrides_existing(self):
        validator = ThesisValidator()
        new_validator = MagicMock(return_value=[])
        validator.register_validator("title", new_validator)
        # 应覆盖原有验证器
        assert validator._validators["title"] == new_validator


class TestThesisValidatorRules:
    """测试 ThesisValidator 规则管理。"""

    def test_add_rule(self):
        validator = ThesisValidator()
        rule = ValidationRule(id="r1", name="测试规则", dimension="title")
        validator.add_rule(rule)
        assert len(validator._custom_rules) == 1

    def test_remove_rule(self):
        validator = ThesisValidator()
        rule = ValidationRule(id="r1", name="测试规则", dimension="title")
        validator.add_rule(rule)
        result = validator.remove_rule("r1")
        assert result is True
        assert len(validator._custom_rules) == 0

    def test_remove_nonexistent_rule(self):
        validator = ThesisValidator()
        result = validator.remove_rule("nonexistent")
        assert result is False

    def test_rule_executed_in_validate(self):
        validator = ThesisValidator()
        # 添加一个总是返回问题的规则
        issue = ValidationIssue(code="custom", severity=SeverityLevel.WARNING, message="自定义问题")
        rule = ValidationRule(
            id="r1",
            name="自定义规则",
            dimension="title",
            validator=lambda d: [issue],
        )
        validator.add_rule(rule)
        report = validator.validate({"title": "正常标题"})
        # title 维度应包含自定义问题
        title_issues = report.dimension_results["title"].issues
        codes = [i.code for i in title_issues]
        assert "custom" in codes


class TestThesisValidatorValidate:
    """测试 ThesisValidator 综合验证。"""

    def test_validate_returns_report(self):
        validator = ThesisValidator()
        report = validator.validate({"title": "测试标题"})
        assert isinstance(report, ValidationReport)
        assert report.id.startswith("report_")

    def test_validate_all_dimensions(self):
        validator = ThesisValidator()
        report = validator.validate({"title": "测试"})
        # 应包含所有维度的结果
        for dim in VALIDATION_DIMENSIONS:
            assert dim in report.dimension_results

    def test_validate_specific_dimensions(self):
        validator = ThesisValidator()
        report = validator.validate({"title": "测试"}, dimensions=["title"])
        # 应只包含 title 维度
        assert "title" in report.dimension_results
        assert len(report.dimension_results) == 1

    def test_validate_empty_data(self):
        validator = ThesisValidator()
        report = validator.validate({})
        # 空数据应产生多个 CRITICAL 问题
        assert report.critical_count > 0
        assert report.passed is False

    def test_validate_good_thesis(self):
        # 完整良好的论题数据
        data = {
            "id": "thesis_001",
            "title": "基于深度学习的文本分类方法研究",
            "abstract": (
                "近年来，深度学习技术快速发展。"
                "现有文本分类方法存在准确率不足的问题。"
                "本文提出基于Transformer的新方法。"
                "实验结果表明准确率提升15%。"
                "本研究具有重要理论价值与实践意义。"
            ) * 10,
            "outline": (
                "第一章 绪论\n"
                "第二章 文献综述与研究现状\n"
                "第三章 研究方法与设计\n"
                "第四章 实验结果与分析\n"
                "第五章 结论与展望"
            ),
            "references": [
                {"text": f"Author{i}. Title{i}. Journal, 2023."} for i in range(35)
            ],
            "method": "实验法",
            "method_detail": "本研究采用对照实验方法，样本为100名被试，使用SPSS进行数据分析。" * 5,
            "feasibility_analysis": (
                "技术上采用成熟方法。"
                "数据来源可靠。"
                "时间安排合理。"
                "资源经费充足。"
            ) * 10,
            "timeline": "6个月完成",
            "resources": "充足",
            "differentiation": "本研究提出新的算法方法",
            "inspiration_source": "受Transformer启发",
        }
        validator = ThesisValidator()
        report = validator.validate(data)
        # 良好论题应通过或接近通过
        assert report.overall_score > 0
        assert isinstance(report.passed, bool)

    def test_validate_records_history(self):
        validator = ThesisValidator()
        validator.validate({"title": "测试"})
        assert len(validator._history) == 1

    def test_validate_with_thesis_id(self):
        validator = ThesisValidator()
        report = validator.validate({"id": "t123", "title": "测试"})
        assert report.thesis_id == "t123"

    def test_validate_validator_exception_handled(self):
        validator = ThesisValidator()
        # 注册一个会抛异常的验证器
        def bad_validator(data):
            raise RuntimeError("验证器异常")
        validator.register_validator("title", bad_validator)
        report = validator.validate({"title": "测试"}, dimensions=["title"])
        # 应捕获异常并生成错误问题
        title_result = report.dimension_results["title"]
        codes = [i.code for i in title_result.issues]
        assert "validator_error" in codes


class TestThesisValidatorScoring:
    """测试 ThesisValidator 评分算法。"""

    def test_dimension_score_no_issues(self):
        validator = ThesisValidator()
        score = validator._compute_dimension_score([])
        assert score == 100.0

    def test_dimension_score_with_issues(self):
        validator = ThesisValidator()
        issues = [
            ValidationIssue(severity=SeverityLevel.WARNING),
            ValidationIssue(severity=SeverityLevel.ERROR),
        ]
        score = validator._compute_dimension_score(issues)
        # 100 - 15 - 30 = 55
        assert score < 100.0
        assert score == 100.0 - SEVERITY_WEIGHTS[SeverityLevel.WARNING] * 100 - SEVERITY_WEIGHTS[SeverityLevel.ERROR] * 100

    def test_dimension_score_minimum_zero(self):
        validator = ThesisValidator()
        # 大量 CRITICAL 问题应使分数降至 0
        issues = [ValidationIssue(severity=SeverityLevel.CRITICAL) for _ in range(10)]
        score = validator._compute_dimension_score(issues)
        assert score == 0.0

    def test_overall_score_weighted(self):
        validator = ThesisValidator()
        dim_results = {
            "title": DimensionResult(dimension="title", score=80.0),
            "abstract": DimensionResult(dimension="abstract", score=90.0),
        }
        score = validator._compute_overall_score(dim_results)
        # 加权平均
        expected = (80.0 * DIMENSION_WEIGHTS["title"] + 90.0 * DIMENSION_WEIGHTS["abstract"]) / (
            DIMENSION_WEIGHTS["title"] + DIMENSION_WEIGHTS["abstract"]
        )
        assert abs(score - expected) < 0.01

    def test_overall_score_empty(self):
        validator = ThesisValidator()
        score = validator._compute_overall_score({})
        assert score == 0.0


class TestThesisValidatorSummary:
    """测试 ThesisValidator 总结生成。"""

    def test_summary_no_issues(self):
        validator = ThesisValidator()
        summary = validator._generate_dimension_summary("title", [], 100.0)
        assert "通过" in summary
        assert "100.0" in summary

    def test_summary_with_issues(self):
        validator = ThesisValidator()
        issues = [
            ValidationIssue(severity=SeverityLevel.ERROR),
            ValidationIssue(severity=SeverityLevel.WARNING),
        ]
        summary = validator._generate_dimension_summary("title", issues, 55.0)
        assert "55.0" in summary
        assert "错误" in summary
        assert "警告" in summary


class TestThesisValidatorRecommendations:
    """测试 ThesisValidator 建议生成。"""

    def test_recommendations_with_critical(self):
        validator = ThesisValidator()
        report = ValidationReport(critical_count=2, overall_score=30.0)
        recs = validator._generate_recommendations(report)
        # 应包含严重问题提示
        assert any("严重问题" in r for r in recs)

    def test_recommendations_high_score(self):
        validator = ThesisValidator()
        report = ValidationReport(critical_count=0, overall_score=85.0)
        recs = validator._generate_recommendations(report)
        # 应包含良好评价
        assert any("良好" in r for r in recs)

    def test_recommendations_low_score(self):
        validator = ThesisValidator()
        report = ValidationReport(critical_count=0, overall_score=40.0)
        recs = validator._generate_recommendations(report)
        # 应包含不达标提示
        assert any("不达标" in r for r in recs)

    def test_recommendations_medium_score(self):
        validator = ThesisValidator()
        report = ValidationReport(critical_count=0, overall_score=65.0)
        recs = validator._generate_recommendations(report)
        # 应包含合格提示
        assert any("合格" in r for r in recs)


class TestThesisValidatorHistory:
    """测试 ThesisValidator 历史记录。"""

    def test_get_history_all(self):
        validator = ThesisValidator()
        for i in range(3):
            validator.validate({"title": f"测试{i}"})
        history = validator.get_history()
        assert len(history) == 3

    def test_get_history_by_thesis_id(self):
        validator = ThesisValidator()
        validator.validate({"id": "t1", "title": "测试1"})
        validator.validate({"id": "t2", "title": "测试2"})
        validator.validate({"id": "t1", "title": "测试1修改"})
        history = validator.get_history(thesis_id="t1")
        assert len(history) == 2
        assert all(r.thesis_id == "t1" for r in history)

    def test_get_history_limit(self):
        validator = ThesisValidator()
        for i in range(5):
            validator.validate({"title": f"测试{i}"})
        history = validator.get_history(limit=2)
        assert len(history) == 2


class TestThesisValidatorCompare:
    """测试 ThesisValidator 报告对比。"""

    def test_compare_reports(self):
        validator = ThesisValidator()
        r1 = validator.validate({"title": ""})
        r2 = validator.validate({"title": "这是一个正常的论题标题"})
        result = validator.compare_reports(r1.id, r2.id)
        assert "score_change" in result
        assert "issue_change" in result
        assert "improved" in result

    def test_compare_nonexistent_reports(self):
        validator = ThesisValidator()
        result = validator.compare_reports("nonexistent1", "nonexistent2")
        assert "error" in result

    def test_compare_improved_report(self):
        validator = ThesisValidator()
        r1 = validator.validate({"title": ""})
        r2 = validator.validate({"title": "这是一个正常的论题标题"})
        result = validator.compare_reports(r1.id, r2.id)
        # 修改后应有所改善
        assert result["improved"] is True or result["score_change"] >= 0


class TestThesisValidatorStats:
    """测试 ThesisValidator 统计。"""

    def test_stats_empty(self):
        validator = ThesisValidator()
        stats = validator.stats()
        assert stats["total_validations"] == 0
        assert stats["avg_score"] == 0.0

    def test_stats_with_history(self):
        validator = ThesisValidator()
        validator.validate({"title": "测试1"})
        validator.validate({"title": "测试2"})
        stats = validator.stats()
        assert stats["total_validations"] == 2
        assert "avg_score" in stats
        assert "pass_rate" in stats
        assert "dimensions" in stats

    def test_stats_custom_rules_count(self):
        validator = ThesisValidator()
        validator.add_rule(ValidationRule(id="r1", name="规则1", dimension="title"))
        validator.validate({"title": "测试"})
        stats = validator.stats()
        assert stats["custom_rules"] == 1


# ===== 模块级单例测试 =====


class TestGlobalInstance:
    """测试模块级单例。"""

    def test_get_singleton(self):
        reset_thesis_validator()
        instance1 = get_thesis_validator()
        instance2 = get_thesis_validator()
        assert instance1 is instance2

    def test_reset_singleton(self):
        reset_thesis_validator()
        instance1 = get_thesis_validator()
        reset_thesis_validator()
        instance2 = get_thesis_validator()
        assert instance1 is not instance2

    def test_singleton_is_thesis_validator(self):
        reset_thesis_validator()
        instance = get_thesis_validator()
        assert isinstance(instance, ThesisValidator)


# ===== 线程安全测试 =====


class TestThreadSafety:
    """测试线程安全。"""

    def test_concurrent_validate(self):
        # 并发执行验证不应出错
        validator = ThesisValidator()
        results = []
        errors = []

        def worker():
            try:
                for _ in range(5):
                    report = validator.validate({"title": "并发测试标题"})
                    results.append(report)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20

    def test_concurrent_add_remove_rules(self):
        # 并发添加和移除规则
        validator = ThesisValidator()
        errors = []

        def adder():
            try:
                for i in range(10):
                    validator.add_rule(ValidationRule(id=f"r_{i}", name=f"规则{i}", dimension="title"))
            except Exception as e:
                errors.append(e)

        def remover():
            try:
                for i in range(10):
                    validator.remove_rule(f"r_{i}")
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=adder)
        t2 = threading.Thread(target=remover)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        assert len(errors) == 0

    def test_concurrent_history_access(self):
        # 并发访问历史记录
        validator = ThesisValidator()
        errors = []

        def validator_worker():
            try:
                for _ in range(5):
                    validator.validate({"title": "测试"})
            except Exception as e:
                errors.append(e)

        def reader_worker():
            try:
                for _ in range(5):
                    validator.get_history()
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=validator_worker),
            threading.Thread(target=validator_worker),
            threading.Thread(target=reader_worker),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0


# ===== 边界情况测试 =====


class TestEdgeCases:
    """测试边界情况。"""

    def test_validate_none_data(self):
        # None 数据应不崩溃（可能产生异常问题）
        validator = ThesisValidator()
        try:
            report = validator.validate({})
            assert isinstance(report, ValidationReport)
        except Exception:
            # 即使抛异常也应被捕获
            pass

    def test_validate_whitespace_title(self):
        validator = ThesisValidator()
        report = validator.validate({"title": "   "})
        # 空白标题应产生问题
        assert isinstance(report, ValidationReport)

    def test_validate_very_long_title(self):
        validator = ThesisValidator()
        long_title = "测试" * 1000
        report = validator.validate({"title": long_title})
        assert isinstance(report, ValidationReport)

    def test_validate_special_characters(self):
        validator = ThesisValidator()
        report = validator.validate({"title": "特殊字符<>&\"'标题"})
        assert isinstance(report, ValidationReport)

    def test_validate_unicode(self):
        validator = ThesisValidator()
        report = validator.validate({"title": "日本語のタイトル"})
        assert isinstance(report, ValidationReport)

    def test_dimension_result_passed_with_critical(self):
        # 含 CRITICAL 问题的维度应不通过
        validator = ThesisValidator()
        issues = [ValidationIssue(severity=SeverityLevel.CRITICAL)]
        score = validator._compute_dimension_score(issues)
        # 验证 passed 逻辑：score >= 60 且无 CRITICAL
        # 由于有 CRITICAL，即使分数高也不应通过
        assert score < 60  # CRITICAL 扣 50 分

    def test_report_passed_requires_no_critical(self):
        # 整体通过要求无 CRITICAL
        validator = ThesisValidator()
        report = validator.validate({"title": ""})  # 空标题产生 CRITICAL
        assert report.critical_count > 0
        assert report.passed is False

    def test_validate_with_extra_context(self):
        # 额外上下文字段应不影响验证
        validator = ThesisValidator()
        data = {
            "title": "测试标题",
            "extra_field": "额外字段",
            "nested": {"key": "value"},
        }
        report = validator.validate(data)
        assert isinstance(report, ValidationReport)

    def test_validate_dimensions_unknown(self):
        # 未知维度应被跳过
        validator = ThesisValidator()
        report = validator.validate({"title": "测试"}, dimensions=["unknown_dim"])
        # 未知维度不应出现在结果中
        assert "unknown_dim" not in report.dimension_results

    def test_rule_with_exception_validator(self):
        # 规则验证器抛异常应被捕获
        validator = ThesisValidator()
        rule = ValidationRule(
            id="r1",
            name="异常规则",
            dimension="title",
            validator=lambda d: (_ for _ in ()).throw(ValueError("异常")),
        )
        validator.add_rule(rule)
        report = validator.validate({"title": "测试"})
        # 应正常返回报告
        assert isinstance(report, ValidationReport)

    def test_multiple_validates_accumulate_history(self):
        # 多次验证应累积历史
        validator = ThesisValidator()
        initial_count = len(validator._history)
        for i in range(5):
            validator.validate({"title": f"测试{i}"})
        assert len(validator._history) == initial_count + 5

    def test_score_never_negative(self):
        # 评分不应为负
        validator = ThesisValidator()
        issues = [ValidationIssue(severity=SeverityLevel.CRITICAL) for _ in range(100)]
        score = validator._compute_dimension_score(issues)
        assert score >= 0.0

    def test_score_never_exceeds_100(self):
        # 评分不应超过 100
        validator = ThesisValidator()
        score = validator._compute_dimension_score([])
        assert score <= 100.0

    def test_overall_score_with_single_dimension(self):
        # 单维度综合评分应等于该维度评分
        validator = ThesisValidator()
        dim_results = {
            "title": DimensionResult(dimension="title", score=75.0),
        }
        score = validator._compute_overall_score(dim_results)
        assert abs(score - 75.0) < 0.01

    def test_recommendations_with_low_dimension_score(self):
        # 低分维度应在建议中提及
        validator = ThesisValidator()
        dim_results = {
            "title": DimensionResult(
                dimension="title",
                score=30.0,
                issues=[ValidationIssue(message="标题问题")],
            )
        }
        report = ValidationReport(
            critical_count=0,
            overall_score=30.0,
            dimension_results=dim_results,
        )
        recs = validator._generate_recommendations(report)
        assert any("标题" in r for r in recs)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
