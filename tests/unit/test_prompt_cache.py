"""单元测试：三段式 Prompt 缓存前缀构建模块

测试 backend/ai/prompt_cache.py 的所有功能，包括：
- CachedPrefix 数据结构
- build_cached_prefix 缓存前缀构建
- is_deepseek_model DeepSeek 模型判断
- 前缀一致性（同会话内字节级一致）
"""
import os
import sys
import tempfile

import pytest

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# 设置临时数据库
import backend.database as _db
_TMP_DIR = tempfile.mkdtemp(prefix="thesisminer_pc_test_")
_db.DB_PATH = os.path.join(_TMP_DIR, "test.db")
_db.init_db()

from backend.ai.prompt_cache import (
    CachedPrefix,
    build_cached_prefix,
    is_deepseek_model,
)


# ===== CachedPrefix 数据结构测试 =====


class TestCachedPrefixDataclass:
    """CachedPrefix 数据结构测试"""

    def test_cached_prefix_has_prefix_field(self):
        """CachedPrefix 应有 prefix 字段"""
        cp = CachedPrefix(
            prefix="前缀",
            prefix_messages=[],
            dynamic="",
            prefix_char_count=0,
        )
        assert cp.prefix == "前缀"

    def test_cached_prefix_has_prefix_messages_field(self):
        """CachedPrefix 应有 prefix_messages 字段"""
        cp = CachedPrefix(
            prefix="",
            prefix_messages=[{"role": "system", "content": "test"}],
            dynamic="",
            prefix_char_count=0,
        )
        assert len(cp.prefix_messages) == 1

    def test_cached_prefix_has_dynamic_field(self):
        """CachedPrefix 应有 dynamic 字段"""
        cp = CachedPrefix(prefix="", prefix_messages=[], dynamic="动态", prefix_char_count=0)
        assert cp.dynamic == "动态"

    def test_cached_prefix_has_prefix_char_count_field(self):
        """CachedPrefix 应有 prefix_char_count 字段"""
        cp = CachedPrefix(prefix="", prefix_messages=[], dynamic="", prefix_char_count=42)
        assert cp.prefix_char_count == 42

    def test_cached_prefix_default_dynamic_empty(self):
        """build_cached_prefix 返回的 dynamic 默认应为空"""
        cp = build_cached_prefix("角色", [])
        assert cp.dynamic == ""


# ===== build_cached_prefix 测试 =====


class TestBuildCachedPrefix:
    """build_cached_prefix 缓存前缀构建测试"""

    def test_returns_cached_prefix(self):
        """应返回 CachedPrefix 对象"""
        result = build_cached_prefix("角色", ["约束"])
        assert isinstance(result, CachedPrefix)

    def test_prefix_includes_system_role(self):
        """prefix 应包含系统角色"""
        result = build_cached_prefix("你是论文专家", [])
        assert "你是论文专家" in result.prefix

    def test_prefix_includes_hard_constraints(self):
        """prefix 应包含硬约束"""
        result = build_cached_prefix("角色", ["标题≤25字", "硕士1年内"])
        assert "标题≤25字" in result.prefix
        assert "硕士1年内" in result.prefix

    def test_prefix_includes_degree(self):
        """prefix 应包含学位"""
        result = build_cached_prefix("角色", [], degree="master")
        assert "master" in result.prefix

    def test_prefix_includes_discipline(self):
        """prefix 应包含学科"""
        result = build_cached_prefix("角色", [], discipline="science_engineering")
        assert "science_engineering" in result.prefix

    def test_prefix_includes_advisor(self):
        """prefix 应包含导师方向"""
        result = build_cached_prefix("角色", [], advisor="机器学习")
        assert "机器学习" in result.prefix

    def test_prefix_messages_is_list(self):
        """prefix_messages 应为列表"""
        result = build_cached_prefix("角色", [])
        assert isinstance(result.prefix_messages, list)

    def test_prefix_messages_has_one_item(self):
        """prefix_messages 应包含一条系统消息"""
        result = build_cached_prefix("角色", [])
        assert len(result.prefix_messages) == 1

    def test_prefix_messages_role_is_system(self):
        """prefix_messages 消息角色应为 system"""
        result = build_cached_prefix("角色", [])
        assert result.prefix_messages[0]["role"] == "system"

    def test_prefix_messages_content_equals_prefix(self):
        """prefix_messages 内容应等于 prefix"""
        result = build_cached_prefix("角色", ["约束"])
        assert result.prefix_messages[0]["content"] == result.prefix

    def test_prefix_char_count_positive(self):
        """prefix_char_count 应为正数"""
        result = build_cached_prefix("角色", ["约束"])
        assert result.prefix_char_count > 0

    def test_prefix_char_count_matches_utf8_length(self):
        """prefix_char_count 应匹配 prefix 的 UTF-8 字节长度"""
        result = build_cached_prefix("角色", ["约束"])
        expected = len(result.prefix.encode("utf-8"))
        assert result.prefix_char_count == expected

    def test_same_inputs_same_output(self):
        """相同输入应返回相同 prefix"""
        r1 = build_cached_prefix("角色", ["约束"], "master", "science", "导师")
        r2 = build_cached_prefix("角色", ["约束"], "master", "science", "导师")
        assert r1.prefix == r2.prefix

    def test_different_inputs_different_output(self):
        """不同输入应返回不同 prefix"""
        r1 = build_cached_prefix("角色A", ["约束"])
        r2 = build_cached_prefix("角色B", ["约束"])
        assert r1.prefix != r2.prefix

    def test_empty_constraints(self):
        """空约束列表应正常处理"""
        result = build_cached_prefix("角色", [])
        assert isinstance(result.prefix, str)
        assert "[HARD_CONSTRAINTS]" not in result.prefix

    def test_no_academic_context(self):
        """无学术上下文时应正常处理"""
        result = build_cached_prefix("角色", [])
        assert "[ACADEMIC_CONTEXT]" not in result.prefix

    def test_partial_academic_context(self):
        """部分学术上下文应触发 ACADEMIC_CONTEXT 块"""
        result = build_cached_prefix("角色", [], degree="master")
        assert "[ACADEMIC_CONTEXT]" in result.prefix
        assert "master" in result.prefix

    def test_prefix_has_system_role_marker(self):
        """prefix 应包含 [SYSTEM_ROLE] 标记"""
        result = build_cached_prefix("角色", [])
        assert "[SYSTEM_ROLE]" in result.prefix

    def test_prefix_has_hard_constraints_marker(self):
        """有约束时应包含 [HARD_CONSTRAINTS] 标记"""
        result = build_cached_prefix("角色", ["约束1"])
        assert "[HARD_CONSTRAINTS]" in result.prefix

    def test_prefix_has_academic_context_marker(self):
        """有学术上下文时应包含 [ACADEMIC_CONTEXT] 标记"""
        result = build_cached_prefix("角色", [], degree="master")
        assert "[ACADEMIC_CONTEXT]" in result.prefix

    def test_constraints_numbered(self):
        """约束应编号"""
        result = build_cached_prefix("角色", ["约束A", "约束B", "约束C"])
        assert "1. 约束A" in result.prefix
        assert "2. 约束B" in result.prefix
        assert "3. 约束C" in result.prefix

    def test_chinese_prefix_char_count(self):
        """中文 prefix 的 char_count 应正确计算 UTF-8 字节"""
        result = build_cached_prefix("你是学术专家", ["标题限制"])
        # 中文字符 UTF-8 占 3 字节
        assert result.prefix_char_count > len(result.prefix)

    def test_dynamic_default_empty(self):
        """dynamic 默认应为空字符串"""
        result = build_cached_prefix("角色", [])
        assert result.dynamic == ""


# ===== is_deepseek_model 测试 =====


class TestIsDeepseekModel:
    """is_deepseek_model DeepSeek 模型判断测试"""

    def test_deepseek_v3_returns_true(self):
        """deepseek-v3.2 应返回 True"""
        assert is_deepseek_model("deepseek-v3.2") is True

    def test_deepseek_r2_returns_true(self):
        """deepseek-r2 应返回 True"""
        assert is_deepseek_model("deepseek-r2") is True

    def test_uppercase_deepseek_returns_true(self):
        """DEEPSEEK 大写应返回 True"""
        assert is_deepseek_model("DEEPSEEK-V3") is True

    def test_mixed_case_deepseek_returns_true(self):
        """DeepSeek 混合大小写应返回 True"""
        assert is_deepseek_model("DeepSeek-Chat") is True

    def test_gpt_returns_false(self):
        """gpt-4.1 应返回 False"""
        assert is_deepseek_model("gpt-4.1") is False

    def test_claude_returns_false(self):
        """claude-sonnet-4.5 应返回 False"""
        assert is_deepseek_model("claude-sonnet-4.5") is False

    def test_qwen_returns_false(self):
        """qwen3-max 应返回 False"""
        assert is_deepseek_model("qwen3-max") is False

    def test_empty_string_returns_false(self):
        """空字符串应返回 False"""
        assert is_deepseek_model("") is False

    def test_random_string_returns_false(self):
        """随机字符串应返回 False"""
        assert is_deepseek_model("random-model") is False

    def test_deepseek_substring_returns_true(self):
        """包含 deepseek 子串应返回 True"""
        assert is_deepseek_model("my-deepseek-custom") is True

    def test_glm_returns_false(self):
        """glm-4.6 应返回 False"""
        assert is_deepseek_model("glm-4.6") is False

    def test_doubao_returns_false(self):
        """doubao-1.5-pro 应返回 False"""
        assert is_deepseek_model("doubao-1.5-pro") is False

    def test_gemini_returns_false(self):
        """gemini-2.5-pro 应返回 False"""
        assert is_deepseek_model("gemini-2.5-pro") is False


# ===== 前缀一致性测试 =====


class TestPrefixConsistency:
    """前缀一致性测试"""

    def test_same_session_same_prefix(self):
        """同一会话多次调用应返回相同 prefix"""
        cp1 = build_cached_prefix("角色", ["约束"], "master", "science", "导师A")
        cp2 = build_cached_prefix("角色", ["约束"], "master", "science", "导师A")
        assert cp1.prefix == cp2.prefix

    def test_different_session_different_prefix(self):
        """不同会话应返回不同 prefix"""
        cp1 = build_cached_prefix("角色", ["约束"], "master", "science", "导师A")
        cp2 = build_cached_prefix("角色", ["约束"], "master", "science", "导师B")
        assert cp1.prefix != cp2.prefix

    def test_prefix_char_count_consistent(self):
        """同会话 prefix_char_count 应一致"""
        cp1 = build_cached_prefix("角色", ["约束"], "master", "science", "导师")
        cp2 = build_cached_prefix("角色", ["约束"], "master", "science", "导师")
        assert cp1.prefix_char_count == cp2.prefix_char_count

    def test_prefix_messages_consistent(self):
        """同会话 prefix_messages 应一致"""
        cp1 = build_cached_prefix("角色", ["约束"], "master", "science", "导师")
        cp2 = build_cached_prefix("角色", ["约束"], "master", "science", "导师")
        assert cp1.prefix_messages == cp2.prefix_messages

    def test_byte_level_consistency(self):
        """前缀应字节级一致"""
        cp1 = build_cached_prefix("你是专家", ["约束1", "约束2"], "master", "science", "导师")
        cp2 = build_cached_prefix("你是专家", ["约束1", "约束2"], "master", "science", "导师")
        assert cp1.prefix.encode("utf-8") == cp2.prefix.encode("utf-8")
