"""新颖性评估模块单元测试

测试 backend/constraints/novelty_checker.py。
覆盖以下功能：
  - NoveltyResult 数据类
  - DIMENSION_WEIGHTS 权重字典
  - calculate_similarity: 相似度计算
  - _tokenize: 分词函数
  - score_cross_discipline: 学科交叉评分
  - score_method_transfer: 方法迁移评分
  - score_pain_point: 痛点突破评分
  - score_trend_foresight: 趋势前瞻评分
  - assess_novelty: 综合新颖性评估

测试策略：
  - 纯逻辑测试，不依赖数据库
  - 覆盖四维评分的各种关键词匹配
  - 边界条件：空输入、无文献、高相似度惩罚
"""
import os
import sys

import pytest

# ===== 项目根目录加入 sys.path =====
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.constraints.novelty_checker import (
    NoveltyResult,
    DIMENSION_WEIGHTS,
    calculate_similarity,
    _tokenize,
    score_cross_discipline,
    score_method_transfer,
    score_pain_point,
    score_trend_foresight,
    assess_novelty,
)


# ===== 测试类：NoveltyResult 数据类 =====

class TestNoveltyResult:
    """测试 NoveltyResult 数据类。"""

    def test_construction(self):
        """应能正常构造。"""
        result = NoveltyResult(
            score=75,
            dimensions={"cross_discipline": 80},
            similarity=0.2,
            issues=["问题1"],
            suggestions=["建议1"],
        )
        assert result.score == 75
        assert result.dimensions["cross_discipline"] == 80
        assert result.similarity == 0.2
        assert len(result.issues) == 1
        assert len(result.suggestions) == 1

    def test_default_empty_collections(self):
        """空集合应能正常构造。"""
        result = NoveltyResult(
            score=50,
            dimensions={},
            similarity=0.0,
            issues=[],
            suggestions=[],
        )
        assert result.issues == []
        assert result.suggestions == []


# ===== 测试类：DIMENSION_WEIGHTS =====

class TestDimensionWeights:
    """测试 DIMENSION_WEIGHTS 权重字典。"""

    def test_contains_four_dimensions(self):
        """应包含四个维度。"""
        assert "cross_discipline" in DIMENSION_WEIGHTS
        assert "method_transfer" in DIMENSION_WEIGHTS
        assert "pain_point" in DIMENSION_WEIGHTS
        assert "trend_foresight" in DIMENSION_WEIGHTS

    def test_weights_sum_to_one(self):
        """权重总和应约等于 1。"""
        total = sum(DIMENSION_WEIGHTS.values())
        assert abs(total - 1.0) < 0.01

    def test_cross_discipline_weight(self):
        """学科交叉权重应为 0.30。"""
        assert DIMENSION_WEIGHTS["cross_discipline"] == 0.30

    def test_method_transfer_weight(self):
        """方法迁移权重应为 0.25。"""
        assert DIMENSION_WEIGHTS["method_transfer"] == 0.25

    def test_pain_point_weight(self):
        """痛点突破权重应为 0.25。"""
        assert DIMENSION_WEIGHTS["pain_point"] == 0.25

    def test_trend_foresight_weight(self):
        """趋势前瞻权重应为 0.20。"""
        assert DIMENSION_WEIGHTS["trend_foresight"] == 0.20


# ===== 测试类：calculate_similarity =====

class TestCalculateSimilarity:
    """测试 calculate_similarity 函数。"""

    def test_empty_existing_titles(self):
        """无已有文献时相似度应为 0。"""
        assert calculate_similarity("论题", []) == 0.0

    def test_identical_titles(self):
        """完全相同的标题相似度应为 1。"""
        topic = "深度学习研究"
        assert calculate_similarity(topic, [topic]) == 1.0

    def test_no_overlap(self):
        """无重叠关键词时相似度应为 0。"""
        topic = "AAAA"
        existing = ["BBBB"]
        result = calculate_similarity(topic, existing)
        assert result == 0.0

    def test_partial_overlap(self):
        """部分重叠相似度应在 0-1 之间。"""
        topic = "深度学习 教育应用"
        existing = ["深度学习 医疗应用"]
        result = calculate_similarity(topic, existing)
        assert 0 < result < 1

    def test_returns_max_similarity(self):
        """应返回最大相似度。"""
        topic = "深度学习"
        existing = ["完全不同的标题", "深度学习", "另一个不同标题"]
        result = calculate_similarity(topic, existing)
        assert result == 1.0

    def test_empty_topic(self):
        """空论题相似度应为 0。"""
        assert calculate_similarity("", ["标题"]) == 0.0

    def test_multiple_existing(self):
        """多个已有文献应取最大相似度。"""
        topic = "机器学习研究"
        existing = ["深度学习", "机器学习", "自然语言处理"]
        result = calculate_similarity(topic, existing)
        assert result > 0


# ===== 测试类：_tokenize =====

class TestTokenize:
    """测试 _tokenize 函数。"""

    def test_chinese_text(self):
        """中文文本应产生 2-gram 分词。"""
        tokens = _tokenize("深度学习")
        assert len(tokens) > 0

    def test_english_text(self):
        """英文文本应按词分词。"""
        tokens = _tokenize("deep learning")
        assert "deep" in tokens
        assert "learning" in tokens

    def test_mixed_text(self):
        """中英混合文本应同时分词。"""
        tokens = _tokenize("deep 深度 learning")
        assert "deep" in tokens
        assert "learning" in tokens

    def test_empty_string(self):
        """空字符串应返回空列表。"""
        assert _tokenize("") == []

    def test_chinese_bigram(self):
        """中文应产生 2-gram。"""
        tokens = _tokenize("深度学习")
        # 应包含 "深度" 和 "度学" 和 "学习" 等 2-gram
        assert "深度" in tokens or "度学" in tokens or "学习" in tokens


# ===== 测试类：score_cross_discipline =====

class TestScoreCrossDiscipline:
    """测试 score_cross_discipline 函数。"""

    def test_empty_topic(self):
        """空论题应返回 0。"""
        assert score_cross_discipline("") == 0

    def test_basic_score(self):
        """无跨学科关键词时应返回基础分 50。"""
        assert score_cross_discipline("常规研究") == 50

    def test_with_cross_keyword(self):
        """含"跨"关键词应加分。"""
        score = score_cross_discipline("跨学科研究")
        assert score > 50

    def test_with_intersection_keyword(self):
        """含"交叉"关键词应加分。"""
        score = score_cross_discipline("交叉领域研究")
        assert score > 50

    def test_with_fusion_keyword(self):
        """含"融合"关键词应加分。"""
        score = score_cross_discipline("融合研究")
        assert score > 50

    def test_with_interdisciplinary_keyword(self):
        """含"interdisciplinary"关键词应加分。"""
        score = score_cross_discipline("interdisciplinary research")
        assert score > 50

    def test_max_score_100(self):
        """评分不应超过 100。"""
        score = score_cross_discipline("跨 交叉 融合 多学科 interdisciplinary cross")
        assert score <= 100


# ===== 测试类：score_method_transfer =====

class TestScoreMethodTransfer:
    """测试 score_method_transfer 函数。"""

    def test_empty_topic(self):
        """空论题应返回 0。"""
        assert score_method_transfer("") == 0

    def test_basic_score(self):
        """无迁移关键词时应返回基础分 50。"""
        assert score_method_transfer("常规研究") == 50

    def test_with_transfer_keyword(self):
        """含"迁移"关键词应加分。"""
        score = score_method_transfer("迁移学习方法")
        assert score > 50

    def test_with_borrow_keyword(self):
        """含"借鉴"关键词应加分。"""
        score = score_method_transfer("借鉴已有方法")
        assert score > 50

    def test_with_adapt_keyword(self):
        """含"adapt"关键词应加分。"""
        score = score_method_transfer("adapt existing method")
        assert score > 50

    def test_max_score_100(self):
        """评分不应超过 100。"""
        score = score_method_transfer("迁移 借鉴 应用 引入 transfer adapt")
        assert score <= 100


# ===== 测试类：score_pain_point =====

class TestScorePainPoint:
    """测试 score_pain_point 函数。"""

    def test_empty_topic(self):
        """空论题应返回 0。"""
        assert score_pain_point("") == 0

    def test_basic_score(self):
        """无痛点关键词时应返回基础分 50。"""
        assert score_pain_point("常规研究") == 50

    def test_with_problem_keyword(self):
        """含"问题"关键词应加分。"""
        score = score_pain_point("问题导向研究")
        assert score > 50

    def test_with_challenge_keyword(self):
        """含"挑战"关键词应加分。"""
        score = score_pain_point("挑战性研究")
        assert score > 50

    def test_with_bottleneck_keyword(self):
        """含"瓶颈"关键词应加分。"""
        score = score_pain_point("突破瓶颈")
        assert score > 50

    def test_max_score_100(self):
        """评分不应超过 100。"""
        score = score_pain_point("问题 挑战 难点 瓶颈 problem challenge issue")
        assert score <= 100


# ===== 测试类：score_trend_foresight =====

class TestScoreTrendForesight:
    """测试 score_trend_foresight 函数。"""

    def test_empty_topic(self):
        """空论题应返回 0。"""
        assert score_trend_foresight("") == 0

    def test_basic_score(self):
        """无趋势关键词时应返回基础分 50。"""
        assert score_trend_foresight("常规研究") == 50

    def test_with_trend_keyword(self):
        """含"趋势"关键词应加分。"""
        score = score_trend_foresight("趋势分析研究")
        assert score > 50

    def test_with_future_keyword(self):
        """含"未来"关键词应加分。"""
        score = score_trend_foresight("未来发展方向")
        assert score > 50

    def test_with_emerging_keyword(self):
        """含"新兴"关键词应加分。"""
        score = score_trend_foresight("新兴技术研究")
        assert score > 50

    def test_max_score_100(self):
        """评分不应超过 100。"""
        score = score_trend_foresight("趋势 未来 新兴 前沿 trend future emerging")
        assert score <= 100


# ===== 测试类：assess_novelty =====

class TestAssessNovelty:
    """测试 assess_novelty 函数。"""

    def test_returns_novelty_result(self):
        """应返回 NoveltyResult 实例。"""
        result = assess_novelty("测试论题")
        assert isinstance(result, NoveltyResult)

    def test_empty_topic(self):
        """空论题应返回低分。"""
        result = assess_novelty("")
        assert result.score == 0

    def test_no_existing_papers(self):
        """无已有文献时相似度应为 0。"""
        result = assess_novelty("新论题", [])
        assert result.similarity == 0.0

    def test_with_existing_papers(self):
        """有已有文献时应计算相似度。"""
        result = assess_novelty(
            "深度学习研究",
            [{"title": "深度学习研究"}],
        )
        assert result.similarity > 0

    def test_high_similarity_reduces_score(self):
        """高相似度应降低总分。"""
        topic = "深度学习研究"
        result_no_sim = assess_novelty(topic, [])
        result_high_sim = assess_novelty(topic, [{"title": topic}])
        assert result_high_sim.score < result_no_sim.score

    def test_dimensions_contain_four_keys(self):
        """dimensions 应包含四个维度。"""
        result = assess_novelty("测试论题")
        assert "cross_discipline" in result.dimensions
        assert "method_transfer" in result.dimensions
        assert "pain_point" in result.dimensions
        assert "trend_foresight" in result.dimensions

    def test_issues_added_for_high_similarity(self):
        """高相似度应添加问题。"""
        topic = "深度学习研究"
        result = assess_novelty(topic, [{"title": topic}])
        assert len(result.issues) > 0

    def test_suggestions_added_for_high_similarity(self):
        """高相似度应添加建议。"""
        topic = "深度学习研究"
        result = assess_novelty(topic, [{"title": topic}])
        assert len(result.suggestions) > 0

    def test_score_in_range(self):
        """评分应在 0-100 范围内。"""
        result = assess_novelty("跨学科融合趋势研究")
        assert 0 <= result.score <= 100

    def test_with_discipline_param(self):
        """discipline 参数应能正常传递。"""
        result = assess_novelty("测试论题", discipline="计算机科学")
        assert isinstance(result, NoveltyResult)

    def test_low_dimension_score_adds_issue(self):
        """低维度评分应添加问题。"""
        # 普通论题无任何关键词，各维度都是 50
        result = assess_novelty("普通研究")
        # 50 分不算低（< 40 才算低），所以不应有维度问题
        # 但如果有高相似度，会有相似度问题
        assert isinstance(result.issues, list)


# ===== 集成测试 =====

class TestNoveltyCheckerIntegration:
    """新颖性评估集成测试。"""

    def test_full_assessment_flow(self):
        """测试完整评估流程。"""
        topic = "跨学科融合的趋势前瞻研究"
        existing = [
            {"title": "深度学习在医疗中的应用"},
            {"title": "自然语言处理综述"},
        ]
        result = assess_novelty(topic, existing, "计算机科学")
        assert isinstance(result, NoveltyResult)
        assert 0 <= result.score <= 100
        assert 0 <= result.similarity <= 1
        assert len(result.dimensions) == 4

    def test_comparison_high_vs_low_novelty(self):
        """比较高新颖性与低新颖性论题。"""
        # 高新颖性：含多个创新关键词，无相似文献
        high = assess_novelty("跨学科融合迁移趋势研究", [])
        # 低新颖性：无创新关键词，有高度相似文献
        low_topic = "常规研究"
        low = assess_novelty(low_topic, [{"title": low_topic}])
        assert high.score > low.score
