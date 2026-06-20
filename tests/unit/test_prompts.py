"""单元测试：提示词模板模块

测试 backend/ai/prompts.py 的所有功能，包括：
- REASONER_SYSTEM_PROMPT / MENTOR_SYSTEM_PROMPT / INSPIRE_SYSTEM_PROMPT 常量
- build_reasoner_prompt 用户提示构建
- build_mentor_prompt 评审提示构建
- build_inspire_prompt 创意激发提示构建
- build_immutable_base 不可变基础段
- build_immutable_profile 不可变画像段
- build_dynamic_tail 动态尾部段
- compute_prefix_hash 前缀哈希计算
- build_prompt_with_cache 缓存前缀构建
- _format_dst_block DST 状态格式化
"""
import hashlib
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
_TMP_DIR = tempfile.mkdtemp(prefix="thesisminer_prompts_test_")
_db.DB_PATH = os.path.join(_TMP_DIR, "test.db")
_db.init_db()

from backend.ai.prompts import (
    REASONER_SYSTEM_PROMPT,
    MENTOR_SYSTEM_PROMPT,
    INSPIRE_SYSTEM_PROMPT,
    build_reasoner_prompt,
    build_mentor_prompt,
    build_inspire_prompt,
    build_immutable_base,
    build_immutable_profile,
    build_dynamic_tail,
    compute_prefix_hash,
    build_prompt_with_cache,
    _format_dst_block,
)


# ===== 系统提示词常量测试 =====


class TestSystemPrompts:
    """系统提示词常量测试"""

    def test_reasoner_system_prompt_is_string(self):
        """REASONER_SYSTEM_PROMPT 应为字符串"""
        assert isinstance(REASONER_SYSTEM_PROMPT, str)

    def test_reasoner_system_prompt_not_empty(self):
        """REASONER_SYSTEM_PROMPT 不应为空"""
        assert len(REASONER_SYSTEM_PROMPT) > 0

    def test_reasoner_system_prompt_mentions_json(self):
        """REASONER_SYSTEM_PROMPT 应提及 JSON 格式"""
        assert "JSON" in REASONER_SYSTEM_PROMPT or "json" in REASONER_SYSTEM_PROMPT

    def test_mentor_system_prompt_is_string(self):
        """MENTOR_SYSTEM_PROMPT 应为字符串"""
        assert isinstance(MENTOR_SYSTEM_PROMPT, str)

    def test_mentor_system_prompt_not_empty(self):
        """MENTOR_SYSTEM_PROMPT 不应为空"""
        assert len(MENTOR_SYSTEM_PROMPT) > 0

    def test_inspire_system_prompt_is_string(self):
        """INSPIRE_SYSTEM_PROMPT 应为字符串"""
        assert isinstance(INSPIRE_SYSTEM_PROMPT, str)

    def test_inspire_system_prompt_not_empty(self):
        """INSPIRE_SYSTEM_PROMPT 不应为空"""
        assert len(INSPIRE_SYSTEM_PROMPT) > 0


# ===== build_reasoner_prompt 测试 =====


class TestBuildReasonerPrompt:
    """build_reasoner_prompt 用户提示构建测试"""

    def test_returns_string(self):
        """应返回字符串"""
        result = build_reasoner_prompt("master", "science_engineering", "导师信息")
        assert isinstance(result, str)

    def test_includes_degree(self):
        """应包含学位层次"""
        result = build_reasoner_prompt("master", "science", "导师")
        assert "master" in result

    def test_includes_discipline(self):
        """应包含学科领域"""
        result = build_reasoner_prompt("master", "science_engineering", "导师")
        assert "science_engineering" in result

    def test_includes_mentor_info(self):
        """应包含导师信息"""
        result = build_reasoner_prompt("master", "science", "张教授-机器学习")
        assert "张教授-机器学习" in result

    def test_includes_context_when_provided(self):
        """提供 context 时应包含"""
        result = build_reasoner_prompt("master", "science", "导师", context="额外上下文")
        assert "额外上下文" in result

    def test_excludes_context_when_empty(self):
        """context 为空时不应包含上下文行"""
        result = build_reasoner_prompt("master", "science", "导师", context="")
        assert "上下文" not in result

    def test_includes_json_instruction(self):
        """应包含 JSON 格式输出指令"""
        result = build_reasoner_prompt("master", "science", "导师")
        assert "JSON" in result or "json" in result

    def test_doctor_degree(self):
        """博士学位应正确处理"""
        result = build_reasoner_prompt("doctor", "science", "导师")
        assert "doctor" in result


# ===== build_mentor_prompt 测试 =====


class TestBuildMentorPrompt:
    """build_mentor_prompt 评审提示构建测试"""

    def test_returns_string(self):
        """应返回字符串"""
        result = build_mentor_prompt({"title": "测试论题"})
        assert isinstance(result, str)

    def test_includes_proposal_json(self):
        """应包含提案的 JSON 序列化"""
        proposal = {"title": "论题A", "score": 85}
        result = build_mentor_prompt(proposal)
        assert "论题A" in result
        assert "85" in result

    def test_includes_review_instruction(self):
        """应包含评审指令"""
        result = build_mentor_prompt({"title": "测试"})
        assert "评审" in result

    def test_empty_proposal(self):
        """空提案字典应正常处理"""
        result = build_mentor_prompt({})
        assert isinstance(result, str)

    def test_nested_proposal(self):
        """嵌套提案应正确序列化"""
        proposal = {
            "title": "测试",
            "research_significance": {"theoretical": "理论", "practical": "实践"},
        }
        result = build_mentor_prompt(proposal)
        assert "理论" in result
        assert "实践" in result


# ===== build_inspire_prompt 测试 =====


class TestBuildInspirePrompt:
    """build_inspire_prompt 创意激发提示构建测试"""

    def test_returns_string(self):
        """应返回字符串"""
        result = build_inspire_prompt("science", "主题")
        assert isinstance(result, str)

    def test_includes_discipline(self):
        """应包含学科"""
        result = build_inspire_prompt("humanities_social", "主题")
        assert "humanities_social" in result

    def test_includes_topic(self):
        """应包含主题"""
        result = build_inspire_prompt("science", "机器学习")
        assert "机器学习" in result

    def test_includes_context_when_provided(self):
        """提供 context 时应包含"""
        result = build_inspire_prompt("science", "主题", context="上下文信息")
        assert "上下文信息" in result

    def test_includes_instruction(self):
        """应包含生成指令"""
        result = build_inspire_prompt("science", "主题")
        assert "研究方向" in result or "候选" in result


# ===== build_immutable_base 测试 =====


class TestBuildImmutableBase:
    """build_immutable_base 不可变基础段测试"""

    def test_returns_string(self):
        """应返回字符串"""
        result = build_immutable_base()
        assert isinstance(result, str)

    def test_not_empty(self):
        """不应为空"""
        result = build_immutable_base()
        assert len(result) > 0

    def test_mentions_reasoner_role(self):
        """应提及 Reasoner 角色"""
        result = build_immutable_base()
        assert "Reasoner" in result

    def test_mentions_json_format(self):
        """应提及 JSON 格式"""
        result = build_immutable_base()
        assert "JSON" in result

    def test_mentions_title_constraint(self):
        """应提及标题约束"""
        result = build_immutable_base()
        assert "title" in result.lower() or "标题" in result

    def test_idempotent(self):
        """多次调用应返回相同结果"""
        r1 = build_immutable_base()
        r2 = build_immutable_base()
        assert r1 == r2


# ===== build_immutable_profile 测试 =====


class TestBuildImmutableProfile:
    """build_immutable_profile 不可变画像段测试"""

    def test_returns_string(self):
        """应返回字符串"""
        result = build_immutable_profile("master", "science", "导师")
        assert isinstance(result, str)

    def test_includes_degree(self):
        """应包含学位"""
        result = build_immutable_profile("master", "science", "导师")
        assert "master" in result

    def test_includes_discipline(self):
        """应包含学科"""
        result = build_immutable_profile("master", "humanities_social", "导师")
        assert "humanities_social" in result

    def test_includes_mentor_info(self):
        """应包含导师信息"""
        result = build_immutable_profile("master", "science", "李教授-NLP")
        assert "李教授-NLP" in result

    def test_same_inputs_same_output(self):
        """相同输入应返回相同结果"""
        r1 = build_immutable_profile("master", "science", "导师A")
        r2 = build_immutable_profile("master", "science", "导师A")
        assert r1 == r2

    def test_different_inputs_different_output(self):
        """不同输入应返回不同结果"""
        r1 = build_immutable_profile("master", "science", "导师A")
        r2 = build_immutable_profile("doctor", "science", "导师A")
        assert r1 != r2


# ===== build_dynamic_tail 测试 =====


class TestBuildDynamicTail:
    """build_dynamic_tail 动态尾部段测试"""

    def test_returns_string(self):
        """应返回字符串"""
        result = build_dynamic_tail("查询内容")
        assert isinstance(result, str)

    def test_includes_query(self):
        """应包含查询内容"""
        result = build_dynamic_tail("如何做研究")
        assert "如何做研究" in result

    def test_includes_current_query_marker(self):
        """应包含 [当前查询] 标记"""
        result = build_dynamic_tail("查询")
        assert "[当前查询]" in result

    def test_with_dst_state(self):
        """提供 DST 状态时应包含状态块"""
        dst_state = {"selected_topic": "测试论题", "iteration_count": 3}
        result = build_dynamic_tail("查询", dst_state)
        assert "[DST 状态块]" in result
        assert "测试论题" in result

    def test_without_dst_state(self):
        """无 DST 状态时不应包含状态块"""
        result = build_dynamic_tail("查询", None)
        assert "[DST 状态块]" not in result

    def test_empty_dst_state(self):
        """空 DST 状态字典不应包含状态块"""
        result = build_dynamic_tail("查询", {})
        assert "[DST 状态块]" not in result

    def test_dst_with_methods(self):
        """DST 含 confirmed_methods 时应包含"""
        dst_state = {"confirmed_methods": ["方法A", "方法B"]}
        result = build_dynamic_tail("查询", dst_state)
        assert "方法A" in result
        assert "方法B" in result

    def test_dst_with_open_questions(self):
        """DST 含 open_questions 时应包含"""
        dst_state = {"open_questions": ["问题1", "问题2"]}
        result = build_dynamic_tail("查询", dst_state)
        assert "问题1" in result


# ===== _format_dst_block 测试 =====


class TestFormatDstBlock:
    """_format_dst_block DST 状态格式化测试"""

    def test_empty_state_returns_empty(self):
        """空状态应返回空字符串"""
        assert _format_dst_block({}) == ""

    def test_none_state_returns_empty(self):
        """None 状态应返回空字符串"""
        assert _format_dst_block(None) == ""

    def test_with_selected_topic(self):
        """含 selected_topic 时应格式化"""
        result = _format_dst_block({"selected_topic": "论题X"})
        assert "论题X" in result

    def test_with_confirmed_methods(self):
        """含 confirmed_methods 时应格式化"""
        result = _format_dst_block({"confirmed_methods": ["方法A"]})
        assert "方法A" in result

    def test_with_iteration_count(self):
        """含 iteration_count 时应格式化"""
        result = _format_dst_block({"iteration_count": 5})
        assert "5" in result


# ===== compute_prefix_hash 测试 =====


class TestComputePrefixHash:
    """compute_prefix_hash 前缀哈希计算测试"""

    def test_returns_string(self):
        """应返回字符串"""
        result = compute_prefix_hash("base", "profile")
        assert isinstance(result, str)

    def test_length_16(self):
        """哈希长度应为 16"""
        result = compute_prefix_hash("base", "profile")
        assert len(result) == 16

    def test_same_inputs_same_hash(self):
        """相同输入应返回相同哈希"""
        h1 = compute_prefix_hash("base", "profile")
        h2 = compute_prefix_hash("base", "profile")
        assert h1 == h2

    def test_different_inputs_different_hash(self):
        """不同输入应返回不同哈希"""
        h1 = compute_prefix_hash("base1", "profile")
        h2 = compute_prefix_hash("base2", "profile")
        assert h1 != h2

    def test_hash_is_hex(self):
        """哈希应为十六进制字符串"""
        result = compute_prefix_hash("base", "profile")
        assert all(c in "0123456789abcdef" for c in result)

    def test_matches_sha256(self):
        """应匹配 SHA-256 前 16 位"""
        base = "base"
        profile = "profile"
        combined = base + "\n" + profile
        expected = hashlib.sha256(combined.encode("utf-8")).hexdigest()[:16]
        result = compute_prefix_hash(base, profile)
        assert result == expected


# ===== build_prompt_with_cache 测试 =====


class TestBuildPromptWithCache:
    """build_prompt_with_cache 缓存前缀构建测试"""

    def test_returns_dict(self):
        """应返回字典"""
        result = build_prompt_with_cache(
            "角色", ["约束1"], "master", "science", "导师", "动态"
        )
        assert isinstance(result, dict)

    def test_has_prefix_key(self):
        """应包含 prefix 键"""
        result = build_prompt_with_cache("角色", [], "", "", "", "动态")
        assert "prefix" in result

    def test_has_prefix_messages_key(self):
        """应包含 prefix_messages 键"""
        result = build_prompt_with_cache("角色", [], "", "", "", "动态")
        assert "prefix_messages" in result

    def test_has_dynamic_key(self):
        """应包含 dynamic 键"""
        result = build_prompt_with_cache("角色", [], "", "", "", "动态内容")
        assert "dynamic" in result

    def test_has_dynamic_messages_key(self):
        """应包含 dynamic_messages 键"""
        result = build_prompt_with_cache("角色", [], "", "", "", "动态")
        assert "dynamic_messages" in result

    def test_prefix_includes_system_role(self):
        """prefix 应包含系统角色"""
        result = build_prompt_with_cache("你是专家", [], "", "", "", "动态")
        assert "你是专家" in result["prefix"]

    def test_prefix_includes_constraints(self):
        """prefix 应包含硬约束"""
        result = build_prompt_with_cache("角色", ["约束A", "约束B"], "", "", "", "动态")
        assert "约束A" in result["prefix"]
        assert "约束B" in result["prefix"]

    def test_prefix_includes_academic_context(self):
        """prefix 应包含学术上下文"""
        result = build_prompt_with_cache(
            "角色", [], "master", "science", "导师A", "动态"
        )
        assert "master" in result["prefix"]
        assert "science" in result["prefix"]
        assert "导师A" in result["prefix"]

    def test_prefix_messages_is_list(self):
        """prefix_messages 应为列表"""
        result = build_prompt_with_cache("角色", [], "", "", "", "动态")
        assert isinstance(result["prefix_messages"], list)

    def test_prefix_messages_has_system_role(self):
        """prefix_messages 第一项 role 应为 system"""
        result = build_prompt_with_cache("角色", [], "", "", "", "动态")
        assert result["prefix_messages"][0]["role"] == "system"

    def test_dynamic_messages_has_user_role(self):
        """dynamic_messages 应为 user 角色"""
        result = build_prompt_with_cache("角色", [], "", "", "", "动态内容")
        assert result["dynamic_messages"][0]["role"] == "user"

    def test_dynamic_equals_input(self):
        """dynamic 应等于输入的 dynamic_content"""
        result = build_prompt_with_cache("角色", [], "", "", "", "我的动态内容")
        assert result["dynamic"] == "我的动态内容"

    def test_empty_constraints(self):
        """空约束列表应正常处理"""
        result = build_prompt_with_cache("角色", [], "", "", "", "动态")
        assert isinstance(result["prefix"], str)

    def test_no_academic_context(self):
        """无学术上下文时应正常处理"""
        result = build_prompt_with_cache("角色", [], "", "", "", "动态")
        assert "[ACADEMIC_CONTEXT]" not in result["prefix"]
