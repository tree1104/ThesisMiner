"""智能上下文压缩（smart_compact）单元测试

测试 backend/sessions/context_manager.py 中的 smart_compact 及辅助函数，
以及 backend/ai/cache_monitor.py 中的 verify_cache_hit_rate。

覆盖以下功能：
  - smart_compact: 智能上下文压缩主入口
  - _count_rounds: 统计对话轮数
  - _is_fixed_message: 判断固定消息
  - _partition_messages: 三段划分
  - _compress_message: 抽取式压缩
  - verify_cache_hit_rate: 缓存命中率估算

测试策略：
  - 纯逻辑测试，不依赖外部 API
  - 验证阈值触发、固定上下文保留、压缩字符数、缓存命中率
  - 验证确定性（相同输入 -> 相同输出）
  - 验证不同配置参数的覆盖
"""
import os
import sys
import tempfile

import pytest

# ===== 项目根目录加入 sys.path =====
_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ===== 临时数据库初始化（必须在导入 backend.database 之前覆盖 DB_PATH）=====
# cache_monitor.py 在模块加载时导入 backend.database，
# 因此需先设置临时数据库避免污染正式数据。
_TMP_DIR = tempfile.mkdtemp(prefix="thesisminer_smart_compact_test_")
import backend.database as _db  # noqa: E402

_db.DB_PATH = os.path.join(_TMP_DIR, "test.db")
_db.init_db()

from backend.sessions.context_manager import (  # noqa: E402
    smart_compact,
    _count_rounds,
    _is_fixed_message,
    _partition_messages,
    _compress_message,
    MultiContextManager,
)
from backend.ai.cache_monitor import verify_cache_hit_rate  # noqa: E402
from backend.config import get_compact_config  # noqa: E402


# ===== 辅助函数 =====


def _make_message(role: str, content: str, **extra) -> dict:
    """构造消息字典。"""
    msg = {"role": role, "content": content}
    msg.update(extra)
    return msg


def _make_rounds(
    n_rounds: int,
    user_chars: int = 300,
    assistant_chars: int = 300,
    start_index: int = 1,
) -> list[dict]:
    """构造 n_rounds 轮 user-assistant 对话。

    Args:
        n_rounds: 对话轮数。
        user_chars: 每条 user 消息的字符数。
        assistant_chars: 每条 assistant 消息的字符数。
        start_index: 起始轮次编号（用于区分不同轮次的内容）。

    Returns:
        消息列表（user/assistant 交替）。
    """
    messages = []
    for i in range(start_index, start_index + n_rounds):
        user_content = f"用户第{i}轮提问：" + "x" * max(0, user_chars - 10)
        assistant_content = f"助手第{i}轮回复：" + "y" * max(0, assistant_chars - 10)
        messages.append(_make_message("user", user_content))
        messages.append(_make_message("assistant", assistant_content))
    return messages


def _make_long_system_prompt(chars: int = 50000) -> str:
    """构造指定长度的系统提示词。"""
    base = "你是论文选题专家助手。"
    return base + "系统约束" * max(0, (chars - len(base)) // 4)


# ===== 测试类：_count_rounds =====


class TestCountRounds:
    """测试 _count_rounds 函数。"""

    def test_count_empty(self):
        """空列表轮数为 0。"""
        assert _count_rounds([]) == 0

    def test_count_single_round(self):
        """单轮对话（user+assistant）轮数为 1。"""
        messages = [
            _make_message("user", "你好"),
            _make_message("assistant", "你好！"),
        ]
        assert _count_rounds(messages) == 1

    def test_count_multiple_rounds(self):
        """多轮对话轮数等于 user 消息数。"""
        messages = [
            _make_message("system", "系统提示"),
            _make_message("user", "问题1"),
            _make_message("assistant", "回答1"),
            _make_message("user", "问题2"),
            _make_message("assistant", "回答2"),
            _make_message("user", "问题3"),
            _make_message("assistant", "回答3"),
        ]
        assert _count_rounds(messages) == 3

    def test_count_with_only_system(self):
        """仅系统消息时轮数为 0。"""
        messages = [_make_message("system", "系统提示")]
        assert _count_rounds(messages) == 0

    def test_count_ignores_non_dict(self):
        """非字典项应被安全忽略。"""
        messages = [
            "not a dict",
            _make_message("user", "问题"),
            None,
            _make_message("assistant", "回答"),
        ]
        assert _count_rounds(messages) == 1


# ===== 测试类：_is_fixed_message =====


class TestIsFixedMessage:
    """测试 _is_fixed_message 函数。"""

    def test_system_message_is_fixed(self):
        """系统消息是固定消息。"""
        assert _is_fixed_message(_make_message("system", "系统提示")) is True

    def test_user_message_not_fixed(self):
        """user 消息不是固定消息。"""
        assert _is_fixed_message(_make_message("user", "问题")) is False

    def test_assistant_message_not_fixed(self):
        """assistant 消息不是固定消息。"""
        assert _is_fixed_message(_make_message("assistant", "回答")) is False

    def test_dst_state_message_is_fixed(self):
        """带 metadata.is_dst_state=True 的消息是固定消息。"""
        msg = _make_message("user", "内容", metadata={"is_dst_state": True})
        assert _is_fixed_message(msg) is True

    def test_non_dict_returns_false(self):
        """非字典输入返回 False。"""
        assert _is_fixed_message("not a dict") is False
        assert _is_fixed_message(None) is False


# ===== 测试类：_partition_messages =====


class TestPartitionMessages:
    """测试 _partition_messages 函数。"""

    def test_partition_basic(self):
        """基本划分：系统前缀 + 可压缩中段 + 最近 N 轮。"""
        messages = [
            _make_message("system", "系统提示"),
        ] + _make_rounds(5, user_chars=100, assistant_chars=100)
        # 5 轮 = 10 条对话消息，keep_recent=2 -> 最近 4 条
        fixed, compressible, recent = _partition_messages(messages, keep_recent=2)
        assert len(fixed) == 1  # 系统提示
        assert len(recent) == 4  # 2 轮 = 4 条
        assert len(compressible) == 6  # 10 - 4 = 6 条

    def test_partition_no_system(self):
        """无系统消息时固定前缀为空。"""
        messages = _make_rounds(5, user_chars=100, assistant_chars=100)
        fixed, compressible, recent = _partition_messages(messages, keep_recent=2)
        assert len(fixed) == 0
        assert len(recent) == 4
        assert len(compressible) == 6

    def test_partition_keep_recent_exceeds_conversational(self):
        """keep_recent 超过对话消息数时全部保留为最近。"""
        messages = [
            _make_message("system", "系统提示"),
            _make_message("user", "问题"),
            _make_message("assistant", "回答"),
        ]
        fixed, compressible, recent = _partition_messages(messages, keep_recent=3)
        assert len(fixed) == 1
        assert len(compressible) == 0
        assert len(recent) == 2

    def test_partition_dst_state_in_prefix(self):
        """DST 状态消息（system 角色）应归入固定前缀。"""
        messages = [
            _make_message("system", "系统提示"),
            _make_message("system", "[对话状态摘要]\n已选定论题：xxx"),
        ] + _make_rounds(4, user_chars=100, assistant_chars=100)
        fixed, compressible, recent = _partition_messages(messages, keep_recent=2)
        assert len(fixed) == 2  # 系统提示 + DST 状态


# ===== 测试类：_compress_message =====


class TestCompressMessage:
    """测试 _compress_message 函数。"""

    def test_compress_long_message(self):
        """长消息应被截断到约 N 字符并加 [compressed] 前缀。"""
        original = "这是一段很长的内容" + "x" * 200
        compressed = _compress_message(_make_message("user", original), chars=50)
        assert compressed["content"].startswith("[compressed] ")
        # 截断部分应为前 50 字符 + "..."
        truncated_part = compressed["content"][len("[compressed] "):]
        assert truncated_part == original[:50] + "..."

    def test_compress_short_message_no_truncation(self):
        """短消息（<= N 字符）不应被截断。"""
        original = "短内容"
        compressed = _compress_message(_make_message("user", original), chars=50)
        assert compressed["content"] == "[compressed] " + original

    def test_compress_preserves_role(self):
        """压缩后应保留 role 字段。"""
        compressed = _compress_message(
            _make_message("assistant", "x" * 200), chars=50
        )
        assert compressed["role"] == "assistant"

    def test_compress_preserves_metadata(self):
        """压缩后应保留 metadata 等额外字段。"""
        msg = _make_message("user", "x" * 200, metadata={"turn": 5})
        compressed = _compress_message(msg, chars=50)
        assert compressed["metadata"] == {"turn": 5}

    def test_compress_is_deterministic(self):
        """相同输入应产生相同输出（确定性）。"""
        msg = _make_message("user", "相同的内容" + "x" * 200)
        c1 = _compress_message(msg, chars=80)
        c2 = _compress_message(msg, chars=80)
        assert c1 == c2


# ===== 测试类：smart_compact 主函数 =====


class TestSmartCompact:
    """测试 smart_compact 主函数。"""

    def test_below_threshold_no_compression(self):
        """测试：轮数低于阈值时不触发压缩（5 轮，阈值=10）。"""
        messages = [
            _make_message("system", "系统提示"),
        ] + _make_rounds(5, user_chars=200, assistant_chars=200)
        config = {
            "compact_threshold": 10,
            "compact_chars": 100,
            "compact_keep_recent": 3,
        }
        result = smart_compact(messages, config)
        # 应原样返回（同一对象或相等内容）
        assert result == messages
        # 不应有 [compressed] 标记
        assert all(
            "[compressed]" not in m.get("content", "")
            for m in result
            if isinstance(m, dict)
        )

    def test_at_threshold_triggers_compression(self):
        """测试：轮数达到阈值时触发压缩（15 轮，阈值=10）。"""
        messages = [
            _make_message("system", "系统提示"),
        ] + _make_rounds(15, user_chars=200, assistant_chars=200)
        config = {
            "compact_threshold": 10,
            "compact_chars": 100,
            "compact_keep_recent": 3,
        }
        result = smart_compact(messages, config)
        # 结果不应等于原始（已压缩）
        assert result != messages
        # 应存在 [compressed] 标记的消息
        compressed_count = sum(
            1
            for m in result
            if isinstance(m, dict) and m.get("content", "").startswith("[compressed]")
        )
        # 15 轮 - 3 轮保留 = 12 轮 = 24 条消息被压缩
        assert compressed_count == 24

    def test_compressed_messages_approx_target_chars(self):
        """测试：压缩后消息约为目标字符数（~100 字符）。"""
        messages = [
            _make_message("system", "系统提示"),
        ] + _make_rounds(15, user_chars=500, assistant_chars=500)
        config = {
            "compact_threshold": 10,
            "compact_chars": 100,
            "compact_keep_recent": 3,
        }
        result = smart_compact(messages, config)
        for m in result:
            if isinstance(m, dict) and m.get("content", "").startswith("[compressed]"):
                # 截断部分（去掉 "[compressed] " 前缀）应为 100 字符 + "..."
                truncated = m["content"][len("[compressed] "):]
                # 100 字符 + "..." = 103 字符
                assert len(truncated) == 103

    def test_system_messages_preserved(self):
        """测试：系统消息不被压缩。"""
        system_content = "重要的系统提示，不应被压缩"
        messages = [
            _make_message("system", system_content),
        ] + _make_rounds(15, user_chars=200, assistant_chars=200)
        config = {
            "compact_threshold": 10,
            "compact_chars": 100,
            "compact_keep_recent": 3,
        }
        result = smart_compact(messages, config)
        # 第一条应仍为系统消息且内容未变
        assert result[0]["role"] == "system"
        assert result[0]["content"] == system_content
        assert "[compressed]" not in result[0]["content"]

    def test_recent_rounds_preserved(self):
        """测试：最近 N 轮不被压缩。"""
        messages = [
            _make_message("system", "系统提示"),
        ] + _make_rounds(15, user_chars=200, assistant_chars=200)
        keep_recent = 3
        config = {
            "compact_threshold": 10,
            "compact_chars": 100,
            "compact_keep_recent": keep_recent,
        }
        result = smart_compact(messages, config)
        # 最后 2*keep_recent 条应为原始消息（无 [compressed] 标记）
        recent = result[-(2 * keep_recent):]
        for m in recent:
            assert not m["content"].startswith("[compressed]")
        # 且内容应与原始最后 N 轮一致
        original_recent = messages[-(2 * keep_recent):]
        assert [m["content"] for m in recent] == [
            m["content"] for m in original_recent
        ]

    def test_dst_state_preserved(self):
        """测试：DST 状态消息被保留（不被压缩）。"""
        dst_content = "[对话状态摘要]\n已选定论题：基于深度学习的论文选题\n已确认方法：实验法"
        messages = [
            _make_message("system", "系统提示"),
            _make_message("system", dst_content),
        ] + _make_rounds(15, user_chars=200, assistant_chars=200)
        config = {
            "compact_threshold": 10,
            "compact_chars": 100,
            "compact_keep_recent": 3,
        }
        result = smart_compact(messages, config)
        # DST 状态消息（第二条）应保持原样
        dst_msg = result[1]
        assert dst_msg["role"] == "system"
        assert dst_msg["content"] == dst_content
        assert "[compressed]" not in dst_msg["content"]

    def test_dst_state_via_metadata_preserved(self):
        """测试：通过 metadata.is_dst_state 标记的消息被保留。"""
        dst_content = "DST 状态内容"
        messages = [
            _make_message("system", "系统提示"),
            _make_message("system", dst_content, metadata={"is_dst_state": True}),
        ] + _make_rounds(15, user_chars=200, assistant_chars=200)
        config = {
            "compact_threshold": 10,
            "compact_chars": 100,
            "compact_keep_recent": 3,
        }
        result = smart_compact(messages, config)
        # DST 状态消息应保持原样
        dst_msg = result[1]
        assert dst_msg["content"] == dst_content

    def test_custom_config_threshold5_chars50_keep2(self):
        """测试：自定义配置（threshold=5, chars=50, keep_recent=2）。"""
        messages = [
            _make_message("system", "系统提示"),
        ] + _make_rounds(10, user_chars=300, assistant_chars=300)
        config = {
            "compact_threshold": 5,
            "compact_chars": 50,
            "compact_keep_recent": 2,
        }
        result = smart_compact(messages, config)
        # 10 轮 - 2 轮保留 = 8 轮 = 16 条被压缩
        compressed_count = sum(
            1
            for m in result
            if isinstance(m, dict) and m.get("content", "").startswith("[compressed]")
        )
        assert compressed_count == 16
        # 最近 2*2=4 条应为原始
        recent = result[-4:]
        for m in recent:
            assert not m["content"].startswith("[compressed]")
        # 压缩消息的截断部分应为 50 字符 + "..."
        for m in result:
            if isinstance(m, dict) and m.get("content", "").startswith("[compressed]"):
                truncated = m["content"][len("[compressed] "):]
                assert len(truncated) == 53  # 50 + "..."

    def test_deterministic_output(self):
        """测试：相同输入产生相同输出（确定性，利于缓存稳定）。"""
        messages = [
            _make_message("system", "系统提示"),
        ] + _make_rounds(15, user_chars=200, assistant_chars=200)
        config = {
            "compact_threshold": 10,
            "compact_chars": 100,
            "compact_keep_recent": 3,
        }
        result1 = smart_compact(messages, config)
        result2 = smart_compact(messages, config)
        assert result1 == result2

    def test_empty_messages(self):
        """测试：空消息列表原样返回。"""
        assert smart_compact([], {"compact_threshold": 10}) == []

    def test_non_list_input(self):
        """测试：非列表输入安全处理。"""
        assert smart_compact(None, {"compact_threshold": 10}) == []
        assert smart_compact("not a list", {"compact_threshold": 10}) == []

    def test_preserves_message_structure(self):
        """测试：压缩后消息保持 role/content 结构。"""
        messages = [
            _make_message("system", "系统提示"),
        ] + _make_rounds(15, user_chars=200, assistant_chars=200)
        config = {
            "compact_threshold": 10,
            "compact_chars": 100,
            "compact_keep_recent": 3,
        }
        result = smart_compact(messages, config)
        for m in result:
            assert isinstance(m, dict)
            assert "role" in m
            assert "content" in m
            assert m["role"] in ("system", "user", "assistant")

    def test_method_on_multi_context_manager(self):
        """测试：MultiContextManager.smart_compact 方法可用。"""
        manager = MultiContextManager()
        messages = [
            _make_message("system", "系统提示"),
        ] + _make_rounds(15, user_chars=200, assistant_chars=200)
        config = {
            "compact_threshold": 10,
            "compact_chars": 100,
            "compact_keep_recent": 3,
        }
        result = manager.smart_compact(messages, config)
        # 应与模块级函数结果一致
        assert result == smart_compact(messages, config)
        assert any(
            m.get("content", "").startswith("[compressed]")
            for m in result
            if isinstance(m, dict)
        )


# ===== 测试类：verify_cache_hit_rate =====


class TestVerifyCacheHitRate:
    """测试 verify_cache_hit_rate 函数。"""

    def test_empty_messages_returns_zero(self):
        """空消息列表返回 0.0。"""
        assert verify_cache_hit_rate([]) == 0.0

    def test_all_system_messages_full_hit(self):
        """全部系统消息时命中率为 1.0。"""
        messages = [
            _make_message("system", "系统提示"),
            _make_message("system", "约束"),
        ]
        assert verify_cache_hit_rate(messages) == 1.0

    def test_cache_hit_rate_above_95_percent(self):
        """测试：压缩后布局缓存命中率 >=95%。

        构造场景：大系统提示 + 多轮压缩历史 + 少量最近轮次，
        使稳定前缀占总上下文 >=95%。
        """
        # 大系统提示（稳定前缀主体）
        system_prompt = _make_long_system_prompt(chars=50000)
        messages = [_make_message("system", system_prompt)]
        # 15 轮对话，每条 300 字符
        messages += _make_rounds(15, user_chars=300, assistant_chars=300)
        config = {
            "compact_threshold": 10,
            "compact_chars": 100,
            "compact_keep_recent": 3,
        }
        compressed = smart_compact(messages, config)
        hit_rate = verify_cache_hit_rate(compressed)
        # 应 >=95%
        assert hit_rate >= 0.95, f"缓存命中率 {hit_rate:.4f} 低于 95% 阈值"

    def test_compressed_messages_counted_as_stable(self):
        """测试：[compressed] 标记的消息计入稳定前缀。"""
        messages = [
            _make_message("system", "系统提示"),
            _make_message("user", "[compressed] 压缩内容"),
            _make_message("assistant", "[compressed] 压缩回复"),
            _make_message("user", "最近的原始问题"),
            _make_message("assistant", "最近的原始回复"),
        ]
        hit_rate = verify_cache_hit_rate(messages)
        # 系统提示 + 2 条压缩消息 = 稳定；2 条原始 = 动态
        # 命中率 = (系统 + 压缩) / 总计
        assert 0.0 < hit_rate < 1.0

    def test_dst_state_counted_as_stable(self):
        """测试：DST 状态消息计入稳定前缀。"""
        messages = [
            _make_message("system", "系统提示"),
            _make_message("user", "DST 内容", metadata={"is_dst_state": True}),
            _make_message("user", "动态问题"),
        ]
        hit_rate = verify_cache_hit_rate(messages)
        # 系统提示 + DST = 稳定；1 条动态
        assert 0.0 < hit_rate < 1.0

    def test_non_dict_messages_ignored(self):
        """测试：非字典消息被安全忽略。"""
        messages = [
            "not a dict",
            None,
            _make_message("system", "系统"),
        ]
        # 不应抛出异常
        hit_rate = verify_cache_hit_rate(messages)
        assert hit_rate == 1.0  # 仅系统消息


# ===== 测试类：get_compact_config =====


class TestGetCompactConfig:
    """测试 get_compact_config 配置函数。"""

    def test_returns_dict_with_required_keys(self):
        """测试：返回包含必需键的字典。"""
        cfg = get_compact_config()
        assert isinstance(cfg, dict)
        assert "enabled" in cfg
        assert "compact_threshold" in cfg
        assert "compact_chars" in cfg
        assert "compact_keep_recent" in cfg

    def test_default_values(self):
        """测试：默认值符合预期。"""
        cfg = get_compact_config()
        assert isinstance(cfg["compact_threshold"], int)
        assert isinstance(cfg["compact_chars"], int)
        assert isinstance(cfg["compact_keep_recent"], int)
        assert isinstance(cfg["enabled"], bool)

    def test_env_override(self, monkeypatch):
        """测试：环境变量可覆盖默认值。"""
        monkeypatch.setenv("COMPACT_THRESHOLD", "7")
        monkeypatch.setenv("COMPACT_CHARS", "80")
        monkeypatch.setenv("COMPACT_KEEP_RECENT", "2")
        monkeypatch.setenv("COMPACT_ENABLED", "false")
        cfg = get_compact_config()
        assert cfg["compact_threshold"] == 7
        assert cfg["compact_chars"] == 80
        assert cfg["compact_keep_recent"] == 2
        assert cfg["enabled"] is False


# ===== 集成测试：smart_compact + verify_cache_hit_rate =====


class TestSmartCompactCacheIntegration:
    """智能压缩与缓存命中率集成测试。"""

    def test_compression_improves_cache_hit_rate(self):
        """测试：压缩后缓存命中率应高于未压缩时。"""
        system_prompt = _make_long_system_prompt(chars=50000)
        messages = [_make_message("system", system_prompt)]
        messages += _make_rounds(15, user_chars=300, assistant_chars=300)
        config = {
            "compact_threshold": 10,
            "compact_chars": 100,
            "compact_keep_recent": 3,
        }
        # 未压缩时的命中率（仅系统消息为稳定前缀）
        rate_before = verify_cache_hit_rate(messages)
        # 压缩后的命中率
        compressed = smart_compact(messages, config)
        rate_after = verify_cache_hit_rate(compressed)
        # 压缩后命中率应高于压缩前
        assert rate_after > rate_before
        # 压缩后应 >=95%
        assert rate_after >= 0.95

    def test_cache_hit_rate_with_different_keep_recent(self):
        """测试：不同 keep_recent 值下的缓存命中率。"""
        system_prompt = _make_long_system_prompt(chars=80000)
        messages = [_make_message("system", system_prompt)]
        messages += _make_rounds(20, user_chars=300, assistant_chars=300)

        for keep_recent in (1, 2, 3, 5):
            config = {
                "compact_threshold": 10,
                "compact_chars": 100,
                "compact_keep_recent": keep_recent,
            }
            compressed = smart_compact(messages, config)
            rate = verify_cache_hit_rate(compressed)
            # 大系统提示下，各 keep_recent 值均应 >=95%
            assert rate >= 0.95, (
                f"keep_recent={keep_recent} 时命中率 {rate:.4f} 低于 95%"
            )
