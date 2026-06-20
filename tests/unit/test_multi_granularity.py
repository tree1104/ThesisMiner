"""多粒度生成器单元测试

测试 backend/constraints/multi_granularity.py。
覆盖以下功能：
  - GranularitySpec 数据类
  - GRANULARITY_SPECS 字典
  - get_granularity_spec: 获取粒度规格
  - validate_granularity: 验证生成内容
  - build_granularity_prompt: 构建粒度生成 Prompt

测试策略：
  - 纯逻辑测试，不依赖数据库
  - 覆盖四种粒度（标题/摘要/大纲/全文）
  - 边界条件：未知粒度、长度边界、空内容
"""
import os
import sys

import pytest

# ===== 项目根目录加入 sys.path =====
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.constraints.multi_granularity import (
    GranularitySpec,
    GRANULARITY_SPECS,
    get_granularity_spec,
    validate_granularity,
    build_granularity_prompt,
)


# ===== 测试类：GranularitySpec 数据类 =====

class TestGranularitySpec:
    """测试 GranularitySpec 数据类。"""

    def test_construction(self):
        """应能正常构造。"""
        spec = GranularitySpec(
            level="title",
            name="标题级",
            min_length=8,
            max_length=20,
            description="精炼的论题标题",
        )
        assert spec.level == "title"
        assert spec.name == "标题级"
        assert spec.min_length == 8
        assert spec.max_length == 20
        assert spec.description == "精炼的论题标题"


# ===== 测试类：GRANULARITY_SPECS 字典 =====

class TestGranularitySpecs:
    """测试 GRANULARITY_SPECS 字典。"""

    def test_contains_four_levels(self):
        """应包含四种粒度。"""
        assert "title" in GRANULARITY_SPECS
        assert "abstract" in GRANULARITY_SPECS
        assert "outline" in GRANULARITY_SPECS
        assert "full" in GRANULARITY_SPECS

    def test_title_spec(self):
        """标题级规格应正确。"""
        spec = GRANULARITY_SPECS["title"]
        assert spec.level == "title"
        assert spec.name == "标题级"
        assert spec.min_length == 8
        assert spec.max_length == 20

    def test_abstract_spec(self):
        """摘要级规格应正确。"""
        spec = GRANULARITY_SPECS["abstract"]
        assert spec.level == "abstract"
        assert spec.min_length == 200
        assert spec.max_length == 300

    def test_outline_spec(self):
        """大纲级规格应正确。"""
        spec = GRANULARITY_SPECS["outline"]
        assert spec.level == "outline"
        assert spec.min_length == 500
        assert spec.max_length == 2000

    def test_full_spec(self):
        """全文级规格应正确。"""
        spec = GRANULARITY_SPECS["full"]
        assert spec.level == "full"
        assert spec.min_length == 5000
        assert spec.max_length == 50000

    def test_all_specs_are_granularity_spec_instances(self):
        """所有规格应为 GranularitySpec 实例。"""
        for spec in GRANULARITY_SPECS.values():
            assert isinstance(spec, GranularitySpec)


# ===== 测试类：get_granularity_spec =====

class TestGetGranularitySpec:
    """测试 get_granularity_spec 函数。"""

    def test_get_title_spec(self):
        """获取标题级规格。"""
        spec = get_granularity_spec("title")
        assert spec is not None
        assert spec.level == "title"

    def test_get_abstract_spec(self):
        """获取摘要级规格。"""
        spec = get_granularity_spec("abstract")
        assert spec is not None
        assert spec.level == "abstract"

    def test_get_outline_spec(self):
        """获取大纲级规格。"""
        spec = get_granularity_spec("outline")
        assert spec is not None
        assert spec.level == "outline"

    def test_get_full_spec(self):
        """获取全文级规格。"""
        spec = get_granularity_spec("full")
        assert spec is not None
        assert spec.level == "full"

    def test_unknown_level_returns_none(self):
        """未知粒度应返回 None。"""
        assert get_granularity_spec("unknown") is None

    def test_empty_string_returns_none(self):
        """空字符串应返回 None。"""
        assert get_granularity_spec("") is None


# ===== 测试类：validate_granularity =====

class TestValidateGranularity:
    """测试 validate_granularity 函数。"""

    def test_valid_title_length(self):
        """合规标题长度应通过验证。"""
        content = "一二三四五六七八"  # 8 字，在 8-20 范围内
        result = validate_granularity(content, "title")
        assert result["valid"] is True

    def test_title_too_short(self):
        """标题过短应不通过。"""
        content = "短"  # 1 字
        result = validate_granularity(content, "title")
        assert result["valid"] is False

    def test_title_too_long(self):
        """标题过长应不通过。"""
        content = "一二三四五六七八九十一二三四五六七八九十一二三四五六"  # 26 字
        result = validate_granularity(content, "title")
        assert result["valid"] is False

    def test_valid_abstract_length(self):
        """合规摘要长度应通过验证。"""
        content = "x" * 250  # 250 字，在 200-300 范围内
        result = validate_granularity(content, "abstract")
        assert result["valid"] is True

    def test_abstract_too_short(self):
        """摘要过短应不通过。"""
        content = "x" * 100  # 100 字
        result = validate_granularity(content, "abstract")
        assert result["valid"] is False

    def test_valid_outline_length(self):
        """合规大纲长度应通过验证。"""
        content = "x" * 1000  # 1000 字，在 500-2000 范围内
        result = validate_granularity(content, "outline")
        assert result["valid"] is True

    def test_valid_full_length(self):
        """合规全文长度应通过验证。"""
        content = "x" * 10000  # 10000 字，在 5000-50000 范围内
        result = validate_granularity(content, "full")
        assert result["valid"] is True

    def test_unknown_level(self):
        """未知粒度应返回 invalid。"""
        result = validate_granularity("内容", "unknown")
        assert result["valid"] is False
        assert "未知粒度" in result["message"]

    def test_result_contains_length(self):
        """结果应包含 length 字段。"""
        result = validate_granularity("测试内容", "title")
        assert "length" in result
        assert result["length"] == 4

    def test_result_contains_min_max(self):
        """结果应包含 min_required 与 max_required。"""
        result = validate_granularity("测试", "title")
        assert "min_required" in result
        assert "max_required" in result
        assert result["min_required"] == 8
        assert result["max_required"] == 20

    def test_boundary_min_length(self):
        """正好等于最小长度应通过。"""
        content = "x" * 8  # 正好 8 字
        result = validate_granularity(content, "title")
        assert result["valid"] is True

    def test_boundary_max_length(self):
        """正好等于最大长度应通过。"""
        content = "x" * 20  # 正好 20 字
        result = validate_granularity(content, "title")
        assert result["valid"] is True

    def test_empty_content(self):
        """空内容应不通过。"""
        result = validate_granularity("", "title")
        assert result["valid"] is False


# ===== 测试类：build_granularity_prompt =====

class TestBuildGranularityPrompt:
    """测试 build_granularity_prompt 函数。"""

    def test_title_prompt(self):
        """标题级 Prompt 应包含字数要求。"""
        prompt = build_granularity_prompt("title", "深度学习")
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "深度学习" in prompt
        assert "8" in prompt  # min_length
        assert "20" in prompt  # max_length

    def test_abstract_prompt(self):
        """摘要级 Prompt 应包含字数要求。"""
        prompt = build_granularity_prompt("abstract", "深度学习")
        assert len(prompt) > 0
        assert "深度学习" in prompt
        assert "200" in prompt
        assert "300" in prompt

    def test_outline_prompt(self):
        """大纲级 Prompt 应包含大纲格式要求。"""
        prompt = build_granularity_prompt("outline", "深度学习")
        assert len(prompt) > 0
        assert "深度学习" in prompt
        assert "大纲" in prompt or "目录" in prompt

    def test_full_prompt(self):
        """全文级 Prompt 应包含字数要求。"""
        prompt = build_granularity_prompt("full", "深度学习")
        assert len(prompt) > 0
        assert "深度学习" in prompt
        assert "5000" in prompt

    def test_unknown_level_returns_empty(self):
        """未知粒度应返回空字符串。"""
        prompt = build_granularity_prompt("unknown", "深度学习")
        assert prompt == ""

    def test_prompt_contains_topic(self):
        """Prompt 应包含论题。"""
        topic = "基于知识图谱的论文推荐"
        prompt = build_granularity_prompt("title", topic)
        assert topic in prompt

    def test_prompt_with_context(self):
        """带 context 的 Prompt 应正常生成。"""
        prompt = build_granularity_prompt(
            "title", "深度学习", context={"degree": "master"}
        )
        assert len(prompt) > 0

    def test_title_prompt_mentions_innovation(self):
        """标题级 Prompt 应提及创新点。"""
        prompt = build_granularity_prompt("title", "深度学习")
        assert "创新" in prompt

    def test_abstract_prompt_mentions_four_elements(self):
        """摘要级 Prompt 应提及四要素。"""
        prompt = build_granularity_prompt("abstract", "深度学习")
        assert "背景" in prompt
        assert "问题" in prompt
        assert "方法" in prompt
        assert "意义" in prompt

    def test_full_prompt_mentions_sections(self):
        """全文级 Prompt 应提及各章节。"""
        prompt = build_granularity_prompt("full", "深度学习")
        assert "选题依据" in prompt or "文献综述" in prompt
        assert "研究方法" in prompt


# ===== 集成测试 =====

class TestMultiGranularityIntegration:
    """多粒度生成器集成测试。"""

    def test_full_granularity_flow(self):
        """测试完整粒度流程：获取规格→验证→构建 Prompt。"""
        # 1. 获取规格
        spec = get_granularity_spec("title")
        assert spec is not None
        # 2. 构建 Prompt
        prompt = build_granularity_prompt("title", "深度学习研究")
        assert len(prompt) > 0
        # 3. 模拟生成内容
        content = "深度学习教育应用"  # 8 字
        # 4. 验证内容
        result = validate_granularity(content, "title")
        assert result["valid"] is True

    def test_all_four_granularities(self):
        """测试所有四种粒度。"""
        for level in ["title", "abstract", "outline", "full"]:
            spec = get_granularity_spec(level)
            assert spec is not None
            prompt = build_granularity_prompt(level, "测试论题")
            assert len(prompt) > 0
