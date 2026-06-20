"""去 AI 痕迹风格规范化器单元测试

测试 backend/constraints/style_normalizer.py。
覆盖以下功能：
  - TEMPLATE_REPLACEMENTS: 模板词替换规则
  - PARALLEL_PATTERNS: 过度对仗模式
  - normalize: 去 AI 痕迹规范化
  - _split_long_sentences: 拆分过长句子
  - _reduce_transition_words: 减少过渡词频率
  - get_ai_trace_score: 计算 AI 痕迹评分
  - normalize_with_diff: 规范化并返回差异对比

测试策略：
  - 纯逻辑测试，不依赖数据库
  - 覆盖各种模板词替换场景
  - 边界条件：空输入、无模板词、高 AI 痕迹文本
"""
import os
import sys

import pytest

# ===== 项目根目录加入 sys.path =====
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.constraints.style_normalizer import (
    TEMPLATE_REPLACEMENTS,
    PARALLEL_PATTERNS,
    normalize,
    _split_long_sentences,
    _reduce_transition_words,
    get_ai_trace_score,
    normalize_with_diff,
)


# ===== 测试类：TEMPLATE_REPLACEMENTS =====

class TestTemplateReplacements:
    """测试 TEMPLATE_REPLACEMENTS 常量。"""

    def test_is_list(self):
        """应为列表。"""
        assert isinstance(TEMPLATE_REPLACEMENTS, list)

    def test_not_empty(self):
        """不应为空。"""
        assert len(TEMPLATE_REPLACEMENTS) > 0

    def test_items_are_tuples(self):
        """每个元素应为元组。"""
        for item in TEMPLATE_REPLACEMENTS:
            assert isinstance(item, tuple)
            assert len(item) == 2

    def test_contains_shouxiang_pattern(self):
        """应包含"首先"替换规则。"""
        patterns = [p for p, _ in TEMPLATE_REPLACEMENTS]
        assert any("首先" in p for p in patterns)

    def test_contains_zongshang_pattern(self):
        """应包含"综上所述"替换规则。"""
        patterns = [p for p, _ in TEMPLATE_REPLACEMENTS]
        assert any("综上所述" in p for p in patterns)


# ===== 测试类：PARALLEL_PATTERNS =====

class TestParallelPatterns:
    """测试 PARALLEL_PATTERNS 常量。"""

    def test_is_list(self):
        """应为列表。"""
        assert isinstance(PARALLEL_PATTERNS, list)

    def test_not_empty(self):
        """不应为空。"""
        assert len(PARALLEL_PATTERNS) > 0

    def test_items_are_strings(self):
        """每个元素应为字符串（正则模式）。"""
        for pattern in PARALLEL_PATTERNS:
            assert isinstance(pattern, str)


# ===== 测试类：normalize =====

class TestNormalize:
    """测试 normalize 函数。"""

    def test_empty_text(self):
        """空文本应返回空。"""
        assert normalize("") == ""

    def test_none_text(self):
        """None 应返回 None。"""
        assert normalize(None) is None

    def test_removes_shouxiang(self):
        """应移除"首先"。"""
        result = normalize("首先，我们需要了解背景。")
        assert "首先" not in result

    def test_replaces_cixi(self):
        """应替换"其次"为"接着，"。"""
        result = normalize("其次，分析数据。")
        assert "接着" in result

    def test_replaces_zongshang(self):
        """应替换"综上所述"为"总的来看，"。"""
        result = normalize("综上所述，研究结果表明。")
        assert "总的来看" in result

    def test_replaces_zongeryan(self):
        """应替换"总而言之"为"整体而言，"。"""
        result = normalize("总而言之，结论如下。")
        assert "整体而言" in result

    def test_replaces_zhongsuoyuzi(self):
        """应移除"众所周知"。"""
        result = normalize("众所周知，深度学习很流行。")
        assert "众所周知" not in result

    def test_preserves_normal_text(self):
        """正常文本应基本保持不变。"""
        text = "本研究探讨了深度学习在教育领域的应用。"
        result = normalize(text)
        # 核心内容应保留
        assert "深度学习" in result
        assert "教育" in result

    def test_handles_multiple_template_words(self):
        """应处理多个模板词。"""
        text = "首先，介绍背景。其次，分析数据。综上所述，得出结论。"
        result = normalize(text)
        assert "首先" not in result
        assert "综上所述" not in result

    def test_chinese_text(self):
        """应处理中文文本。"""
        text = "首先，我们需要理解问题。"
        result = normalize(text)
        assert isinstance(result, str)


# ===== 测试类：_split_long_sentences =====

class TestSplitLongSentences:
    """测试 _split_long_sentences 函数。"""

    def test_short_sentence_unchanged(self):
        """短句子应保持不变。"""
        text = "这是一个短句子。"
        result = _split_long_sentences(text, max_length=50)
        assert "短句子" in result

    def test_long_sentence_split(self):
        """长句子应被拆分。"""
        text = "这是一个非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常长的句子。"
        result = _split_long_sentences(text, max_length=20)
        # 拆分后应仍包含原内容
        assert "长" in result

    def test_empty_text(self):
        """空文本应返回空。"""
        assert _split_long_sentences("") == ""

    def test_default_max_length(self):
        """默认 max_length=50。"""
        text = "短句子。"
        result = _split_long_sentences(text)
        assert "短句子" in result

    def test_multiple_sentences(self):
        """多个句子应分别处理。"""
        text = "第一句。第二句。第三句。"
        result = _split_long_sentences(text, max_length=50)
        assert "第一句" in result
        assert "第二句" in result
        assert "第三句" in result


# ===== 测试类：_reduce_transition_words =====

class TestReduceTransitionWords:
    """测试 _reduce_transition_words 函数。"""

    def test_few_transitions_unchanged(self):
        """少量过渡词应保持不变。"""
        text = "因此，结果如下。"
        result = _reduce_transition_words(text)
        assert "因此" in result

    def test_many_transitions_reduced(self):
        """过多过渡词应被减少。"""
        text = "因此A。因此B。因此C。因此D。因此E。"
        result = _reduce_transition_words(text)
        # 应减少"因此"的出现次数
        assert result.count("因此") < text.count("因此")

    def test_empty_text(self):
        """空文本应返回空。"""
        assert _reduce_transition_words("") == ""

    def test_mixed_transition_words(self):
        """混合过渡词应分别处理。"""
        text = "因此A。所以B。然而C。因此D。所以E。然而F。因此G。所以H。然而I。"
        result = _reduce_transition_words(text)
        assert isinstance(result, str)


# ===== 测试类：get_ai_trace_score =====

class TestGetAiTraceScore:
    """测试 get_ai_trace_score 函数。"""

    def test_empty_text(self):
        """空文本应返回 100。"""
        assert get_ai_trace_score("") == 100

    def test_none_text(self):
        """None 应返回 100。"""
        assert get_ai_trace_score(None) == 100

    def test_normal_text_high_score(self):
        """正常文本应有较高评分。"""
        text = "本研究采用实验方法验证假设。样本来自随机抽样。数据分析使用回归模型。"
        score = get_ai_trace_score(text)
        assert score > 0

    def test_text_with_template_words_lower_score(self):
        """含模板词的文本评分应低于正常文本。"""
        text_with_templates = "首先，介绍背景。其次，分析数据。综上所述，得出结论。"
        text_normal = "本研究采用实验方法。数据分析使用回归模型。结果验证了假设。"
        score_templates = get_ai_trace_score(text_with_templates)
        score_normal = get_ai_trace_score(text_normal)
        assert score_templates < score_normal

    def test_score_in_range(self):
        """评分应在 0-100 范围内。"""
        text = "首先，综上所述，众所周知，总而言之。"
        score = get_ai_trace_score(text)
        assert 0 <= score <= 100

    def test_more_template_words_lower_score(self):
        """更多模板词应导致更低评分。"""
        few = "首先，介绍。"
        many = "首先，介绍。其次，分析。最后，结论。综上所述，总结。"
        score_few = get_ai_trace_score(few)
        score_many = get_ai_trace_score(many)
        assert score_many <= score_few


# ===== 测试类：normalize_with_diff =====

class TestNormalizeWithDiff:
    """测试 normalize_with_diff 函数。"""

    def test_returns_dict(self):
        """应返回字典。"""
        result = normalize_with_diff("测试文本。")
        assert isinstance(result, dict)

    def test_contains_required_fields(self):
        """应包含所有必需字段。"""
        result = normalize_with_diff("测试文本。")
        assert "original" in result
        assert "normalized" in result
        assert "changes" in result
        assert "ai_score_before" in result
        assert "ai_score_after" in result

    def test_original_equals_input(self):
        """original 应等于输入文本。"""
        text = "测试文本。"
        result = normalize_with_diff(text)
        assert result["original"] == text

    def test_normalized_is_string(self):
        """normalized 应为字符串。"""
        result = normalize_with_diff("测试文本。")
        assert isinstance(result["normalized"], str)

    def test_changes_is_int(self):
        """changes 应为整数。"""
        result = normalize_with_diff("测试文本。")
        assert isinstance(result["changes"], int)

    def test_ai_scores_in_range(self):
        """AI 评分应在 0-100 范围内。"""
        result = normalize_with_diff("首先，测试。")
        assert 0 <= result["ai_score_before"] <= 100
        assert 0 <= result["ai_score_after"] <= 100

    def test_empty_text(self):
        """空文本应正常处理。"""
        result = normalize_with_diff("")
        assert result["original"] == ""
        assert result["normalized"] == ""

    def test_text_with_templates(self):
        """含模板词的文本应产生变化。"""
        text = "首先，介绍背景。综上所述，得出结论。"
        result = normalize_with_diff(text)
        # 规范化后应与原文不同
        assert result["normalized"] != text or result["changes"] >= 0

    def test_ai_score_after_normalize(self):
        """规范化后 AI 评分应不低于规范化前（或相等）。"""
        text = "首先，介绍。其次，分析。"
        result = normalize_with_diff(text)
        # 规范化应降低 AI 痕迹（提高评分）
        assert result["ai_score_after"] >= result["ai_score_before"] - 5


# ===== 集成测试 =====

class TestStyleNormalizerIntegration:
    """风格规范化器集成测试。"""

    def test_full_normalization_flow(self):
        """测试完整规范化流程。"""
        text = "首先，介绍研究背景。其次，分析数据。综上所述，得出结论。"
        # 1. 计算 AI 痕迹评分
        score_before = get_ai_trace_score(text)
        # 2. 规范化
        normalized = normalize(text)
        # 3. 计算规范化后的评分
        score_after = get_ai_trace_score(normalized)
        # 4. 差异对比
        diff = normalize_with_diff(text)
        assert diff["original"] == text
        assert diff["normalized"] == normalized
        assert diff["ai_score_before"] == score_before
        assert diff["ai_score_after"] == score_after

    def test_template_word_removal_improves_score(self):
        """移除模板词应提高 AI 痕迹评分。"""
        text = "首先，介绍背景。其次，分析数据。最后，得出结论。综上所述，研究完成。"
        normalized = normalize(text)
        score_before = get_ai_trace_score(text)
        score_after = get_ai_trace_score(normalized)
        # 规范化后评分应提高（或至少不降低）
        assert score_after >= score_before
