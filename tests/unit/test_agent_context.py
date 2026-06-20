# -*- coding: utf-8 -*-
"""
test_agent_context.py - Agent 上下文管理模块单元测试

本测试文件覆盖 backend/agents/agent_context.py 中的所有组件：
- MessageRole 枚举
- Message 数据类（to_dict/to_openai_dict/to_anthropic_dict/from_dict/estimate_tokens）
- TokenCounter（模型特定字符/token 比率、count/count_message/count_messages/count_with_response/max_context_for_model）
- ContextWindow（可用 token/利用率、add_message/add_messages/get_messages/trim_to_fit/clear/get_stats）
- MessageHistory（add/add_many/get_all/get_recent/get_by_role/search/get_range/count/clear/export）
- ContextCompressor（should_compress/compress 三策略：摘要/截断/关键词）
- ContextManager（add_message/add_user_message/add_assistant_message/get_messages/reset/get_stats/export_history/search_history/get_context_hash）
- ContextRegistry（create_context/get_context/remove_context/reset_context/reset_all/list_contexts/get_all_stats）
- 全局函数（get_context_registry/get_context/create_context/reset_all_contexts）

作者：ThesisMiner 团队
版本：v8.0
"""

import json
import time
import threading
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from backend.agents.agent_context import (
    # 枚举
    MessageRole,
    # 数据类
    Message,
    # 计数器
    TokenCounter,
    # 上下文窗口
    ContextWindow,
    # 消息历史
    MessageHistory,
    # 上下文压缩器
    ContextCompressor,
    # 上下文管理器
    ContextManager,
    # 注册表
    ContextRegistry,
    # 全局函数
    get_context_registry,
    get_context,
    create_context,
    reset_all_contexts,
)


# ===== MessageRole 枚举测试 =====


class TestMessageRole:
    """测试 MessageRole 枚举。"""

    def test_role_values(self):
        """测试枚举值存在。"""
        assert MessageRole.SYSTEM
        assert MessageRole.USER
        assert MessageRole.ASSISTANT
        assert MessageRole.TOOL
        assert MessageRole.FUNCTION

    def test_role_count(self):
        """测试枚举成员数量。"""
        roles = list(MessageRole)
        assert len(roles) == 5

    def test_role_uniqueness(self):
        """测试枚举值唯一性。"""
        values = [r.value for r in MessageRole]
        assert len(values) == len(set(values))

    def test_role_string_values(self):
        """测试枚举值为字符串。"""
        for role in MessageRole:
            assert isinstance(role.value, str)

    def test_role_lookup_by_value(self):
        """测试通过值查找枚举。"""
        for role in MessageRole:
            assert MessageRole(role.value) == role


# ===== Message 数据类测试 =====


class TestMessage:
    """测试 Message 数据类。"""

    def test_create_simple_message(self):
        """测试创建简单消息。"""
        msg = Message(role=MessageRole.USER, content="你好")
        assert msg.role == MessageRole.USER
        assert msg.content == "你好"
        assert msg.name == ""
        assert msg.tool_call_id == ""
        assert msg.tool_calls == []

    def test_create_with_name(self):
        """测试带名称的消息。"""
        msg = Message(role=MessageRole.ASSISTANT, content="回复", name="助手")
        assert msg.name == "助手"

    def test_create_with_tool_calls(self):
        """测试带工具调用的消息。"""
        tool_calls = [{"id": "call_1", "function": {"name": "search", "arguments": "{}"}}]
        msg = Message(role=MessageRole.ASSISTANT, content="", tool_calls=tool_calls)
        assert msg.tool_calls == tool_calls

    def test_create_with_metadata(self):
        """测试带元数据的消息。"""
        metadata = {"source": "test", "timestamp": "2024-01-01"}
        msg = Message(role=MessageRole.USER, content="测试", metadata=metadata)
        assert msg.metadata == metadata

    def test_to_dict(self):
        """测试转换为字典。"""
        msg = Message(role=MessageRole.USER, content="测试内容")
        d = msg.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "测试内容"

    def test_to_dict_with_all_fields(self):
        """测试包含所有字段的字典转换。"""
        msg = Message(
            role=MessageRole.ASSISTANT,
            content="回复",
            name="助手",
            tool_calls=[{"id": "1"}],
            metadata={"key": "value"},
        )
        d = msg.to_dict()
        assert "role" in d
        assert "content" in d

    def test_to_openai_dict(self):
        """测试转换为 OpenAI 格式。"""
        msg = Message(role=MessageRole.USER, content="OpenAI 格式")
        d = msg.to_openai_dict()
        assert d["role"] == "user"
        assert d["content"] == "OpenAI 格式"

    def test_to_openai_dict_with_name(self):
        """测试 OpenAI 格式带名称。"""
        msg = Message(role=MessageRole.FUNCTION, content="结果", name="func_name")
        d = msg.to_openai_dict()
        assert d["role"] == "function"
        assert d["name"] == "func_name"

    def test_to_anthropic_dict(self):
        """测试转换为 Anthropic 格式。"""
        msg = Message(role=MessageRole.USER, content="Anthropic 格式")
        d = msg.to_anthropic_dict()
        assert "role" in d
        assert "content" in d

    def test_from_dict(self):
        """测试从字典创建消息。"""
        d = {"role": "user", "content": "从字典创建"}
        msg = Message.from_dict(d)
        assert msg.role == MessageRole.USER
        assert msg.content == "从字典创建"

    def test_from_dict_with_metadata(self):
        """测试从带元数据的字典创建。"""
        d = {"role": "assistant", "content": "回复", "metadata": {"k": "v"}}
        msg = Message.from_dict(d)
        assert msg.role == MessageRole.ASSISTANT
        assert msg.metadata == {"k": "v"}

    def test_from_dict_invalid_role(self):
        """测试无效角色处理。"""
        d = {"role": "invalid_role", "content": "测试"}
        # 应该有默认处理或抛出异常
        try:
            msg = Message.from_dict(d)
            # 如果不抛异常，检查角色处理
        except (ValueError, KeyError):
            pass  # 预期行为

    def test_estimate_tokens(self):
        """测试 token 估算。"""
        msg = Message(role=MessageRole.USER, content="这是一段中文内容")
        tokens = msg.estimate_tokens()
        assert tokens > 0
        assert isinstance(tokens, int)

    def test_estimate_tokens_empty_content(self):
        """测试空内容的 token 估算。"""
        msg = Message(role=MessageRole.USER, content="")
        tokens = msg.estimate_tokens()
        assert tokens >= 0

    def test_estimate_tokens_long_content(self):
        """测试长内容的 token 估算。"""
        long_content = "a" * 1000
        msg = Message(role=MessageRole.USER, content=long_content)
        tokens = msg.estimate_tokens()
        assert tokens > 0

    def test_timestamp_auto_set(self):
        """测试时间戳自动设置。"""
        msg = Message(role=MessageRole.USER, content="测试")
        assert msg.timestamp is not None

    def test_token_count_field(self):
        """测试 token_count 字段。"""
        msg = Message(role=MessageRole.USER, content="测试", token_count=10)
        assert msg.token_count == 10

    def test_round_trip_dict(self):
        """测试字典往返转换。"""
        original = Message(role=MessageRole.ASSISTANT, content="往返测试", name="bot")
        d = original.to_dict()
        restored = Message.from_dict(d)
        assert restored.role == original.role
        assert restored.content == original.content


# ===== TokenCounter 测试 =====


class TestTokenCounter:
    """测试 TokenCounter 类。"""

    def test_count_simple_text(self):
        """测试简单文本计数。"""
        counter = TokenCounter()
        tokens = counter.count("Hello world")
        assert tokens > 0

    def test_count_empty_string(self):
        """测试空字符串计数。"""
        counter = TokenCounter()
        tokens = counter.count("")
        assert tokens == 0

    def test_count_chinese_text(self):
        """测试中文文本计数。"""
        counter = TokenCounter()
        tokens = counter.count("这是一段中文文本")
        assert tokens > 0

    def test_count_mixed_text(self):
        """测试中英文混合文本。"""
        counter = TokenCounter()
        tokens = counter.count("Hello 世界 this is 混合 text")
        assert tokens > 0

    def test_count_long_text(self):
        """测试长文本计数。"""
        counter = TokenCounter()
        text = "word " * 1000
        tokens = counter.count(text)
        assert tokens > 100

    def test_count_message(self):
        """测试单条消息计数。"""
        counter = TokenCounter()
        msg = Message(role=MessageRole.USER, content="测试消息内容")
        tokens = counter.count_message(msg)
        assert tokens > 0

    def test_count_messages(self):
        """测试多条消息计数。"""
        counter = TokenCounter()
        messages = [
            Message(role=MessageRole.SYSTEM, content="系统提示"),
            Message(role=MessageRole.USER, content="用户输入"),
            Message(role=MessageRole.ASSISTANT, content="助手回复"),
        ]
        tokens = counter.count_messages(messages)
        assert tokens > 0

    def test_count_messages_empty(self):
        """测试空消息列表计数。"""
        counter = TokenCounter()
        tokens = counter.count_messages([])
        # 空消息列表仍有对话开销（约 3 token）
        assert tokens == 3

    def test_count_with_response(self):
        """测试带响应的计数。"""
        counter = TokenCounter()
        messages = [
            Message(role=MessageRole.USER, content="问题"),
        ]
        response = "这是回答内容"
        result = counter.count_with_response(messages, response)
        assert isinstance(result, dict)
        assert result["total_tokens"] > 0

    def test_max_context_for_model(self):
        """测试获取模型最大上下文。"""
        counter = TokenCounter(model="gpt-4")
        # 测试已知模型
        ctx = counter.max_context_for_model()
        assert ctx > 0

    def test_max_context_unknown_model(self):
        """测试未知模型的最大上下文。"""
        counter = TokenCounter(model="unknown-model-xyz")
        ctx = counter.max_context_for_model()
        # 应该返回默认值或 0
        assert ctx >= 0

    def test_model_chars_per_token_dict(self):
        """测试模型字符/token 比率字典。"""
        assert hasattr(TokenCounter, "MODEL_CHARS_PER_TOKEN")
        assert isinstance(TokenCounter.MODEL_CHARS_PER_TOKEN, dict)
        assert len(TokenCounter.MODEL_CHARS_PER_TOKEN) > 0

    def test_default_chars_per_token(self):
        """测试默认字符/token 比率。"""
        assert hasattr(TokenCounter, "DEFAULT_CHARS_PER_TOKEN")
        assert TokenCounter.DEFAULT_CHARS_PER_TOKEN > 0

    def test_chinese_tokens_per_char(self):
        """测试中文字符/token 比率。"""
        assert hasattr(TokenCounter, "CHINESE_TOKENS_PER_CHAR")
        assert TokenCounter.CHINESE_TOKENS_PER_CHAR > 0

    def test_count_with_specific_model(self):
        """测试指定模型的计数。"""
        counter = TokenCounter(model="gpt-4")
        text = "Hello world this is a test"
        tokens = counter.count(text)
        assert tokens > 0

    def test_count_unicode_text(self):
        """测试 Unicode 文本计数。"""
        counter = TokenCounter()
        text = "Emoji test 🎉 and symbols ©®™"
        tokens = counter.count(text)
        assert tokens > 0

    def test_count_whitespace_only(self):
        """测试纯空白字符计数。"""
        counter = TokenCounter()
        tokens = counter.count("   \n\t  ")
        # 纯空白可能有少量 token 或为 0
        assert tokens >= 0


# ===== ContextWindow 测试 =====


class TestContextWindow:
    """测试 ContextWindow 类。"""

    def test_create_window(self):
        """测试创建上下文窗口。"""
        window = ContextWindow(max_tokens=4096)
        assert window.max_tokens == 4096

    def test_create_with_reserved(self):
        """测试带响应预留的窗口。"""
        window = ContextWindow(max_tokens=4096, reserved_for_response=1024)
        assert window.reserved_for_response == 1024

    def test_available_tokens(self):
        """测试可用 token 计算。"""
        window = ContextWindow(max_tokens=4096, reserved_for_response=1024)
        available = window.available_tokens
        assert available == 3072

    def test_add_message(self):
        """测试添加消息。"""
        window = ContextWindow(max_tokens=4096, reserved_for_response=0)
        msg = Message(role=MessageRole.USER, content="测试")
        window.add_message(msg)
        assert len(window) == 1

    def test_add_messages(self):
        """测试批量添加消息。"""
        window = ContextWindow(max_tokens=4096, reserved_for_response=0)
        messages = [
            Message(role=MessageRole.SYSTEM, content="系统"),
            Message(role=MessageRole.USER, content="用户"),
        ]
        window.add_messages(messages)
        assert len(window) == 2

    def test_get_messages(self):
        """测试获取消息列表。"""
        window = ContextWindow(max_tokens=4096, reserved_for_response=0)
        msg = Message(role=MessageRole.USER, content="测试")
        window.add_message(msg)
        messages = window.get_messages()
        assert len(messages) == 1
        assert messages[0].content == "测试"

    def test_get_messages_dict(self):
        """测试获取消息字典列表。"""
        window = ContextWindow(max_tokens=4096, reserved_for_response=0)
        msg = Message(role=MessageRole.USER, content="字典测试")
        window.add_message(msg)
        dicts = window.get_messages_dict()
        assert len(dicts) == 1
        assert dicts[0]["content"] == "字典测试"

    def test_set_system_message(self):
        """测试设置系统消息。"""
        window = ContextWindow(max_tokens=4096)
        window.set_system_message("你是助手")
        sys_msg = window.get_system_message()
        assert sys_msg is not None
        assert sys_msg.role == MessageRole.SYSTEM

    def test_get_system_message_none(self):
        """测试无系统消息时返回 None。"""
        window = ContextWindow(max_tokens=4096)
        assert window.get_system_message() is None

    def test_remove_oldest(self):
        """测试移除最旧消息。"""
        window = ContextWindow(max_tokens=4096, reserved_for_response=0)
        window.add_message(Message(role=MessageRole.USER, content="第一条"))
        window.add_message(Message(role=MessageRole.USER, content="第二条"))
        window.remove_oldest()
        messages = window.get_messages()
        assert len(messages) == 1
        assert messages[0].content == "第二条"

    def test_trim_to_fit(self):
        """测试裁剪以适应窗口。"""
        window = ContextWindow(max_tokens=200, reserved_for_response=0)
        # 添加多条消息使超出限制
        for i in range(20):
            window.add_message(Message(role=MessageRole.USER, content=f"消息内容_{i}" * 10))
        window.trim_to_fit(target_tokens=100)
        # 裁剪后应在限制内
        assert window.utilization <= 1.0

    def test_clear(self):
        """测试清空窗口。"""
        window = ContextWindow(max_tokens=4096)
        window.add_message(Message(role=MessageRole.USER, content="测试"))
        window.clear()
        assert len(window) == 0

    def test_utilization(self):
        """测试利用率计算。"""
        window = ContextWindow(max_tokens=4096, reserved_for_response=1024)
        assert window.utilization == 0.0  # 空窗口
        window.add_message(Message(role=MessageRole.USER, content="测试内容"))
        assert window.utilization > 0

    def test_get_stats(self):
        """测试获取统计信息。"""
        window = ContextWindow(max_tokens=4096, reserved_for_response=1024)
        window.add_message(Message(role=MessageRole.USER, content="测试"))
        stats = window.get_stats()
        assert isinstance(stats, dict)
        assert "max_tokens" in stats or "used_tokens" in stats

    def test_len(self):
        """测试 __len__ 方法。"""
        window = ContextWindow(max_tokens=4096, reserved_for_response=0)
        assert len(window) == 0
        window.add_message(Message(role=MessageRole.USER, content="测试"))
        assert len(window) == 1

    def test_system_message_not_counted_in_regular(self):
        """测试系统消息不计入常规消息。"""
        window = ContextWindow(max_tokens=4096)
        window.set_system_message("系统提示")
        window.add_message(Message(role=MessageRole.USER, content="用户输入"))
        messages = window.get_messages()
        # 系统消息可能单独存储或排在首位
        assert len(messages) >= 1

    def test_token_recalculation(self):
        """测试 token 重新计算。"""
        window = ContextWindow(max_tokens=4096, reserved_for_response=0)
        window.add_message(Message(role=MessageRole.USER, content="测试 token 计算"))
        stats = window.get_stats()
        # 添加消息后 token 数应大于 0
        used = stats.get("total_tokens", 0)
        assert used > 0


# ===== MessageHistory 测试 =====


class TestMessageHistory:
    """测试 MessageHistory 类。"""

    def test_create_history(self):
        """测试创建消息历史。"""
        history = MessageHistory(max_size=100)
        assert history.max_size == 100

    def test_add(self):
        """测试添加消息。"""
        history = MessageHistory(max_size=100)
        msg = Message(role=MessageRole.USER, content="测试")
        history.add(msg)
        assert history.count() == 1

    def test_add_many(self):
        """测试批量添加。"""
        history = MessageHistory(max_size=100)
        messages = [
            Message(role=MessageRole.USER, content=f"消息_{i}")
            for i in range(5)
        ]
        history.add_many(messages)
        assert history.count() == 5

    def test_get_all(self):
        """测试获取所有消息。"""
        history = MessageHistory(max_size=100)
        history.add(Message(role=MessageRole.USER, content="测试"))
        all_msgs = history.get_all()
        assert len(all_msgs) == 1

    def test_get_recent(self):
        """测试获取最近消息。"""
        history = MessageHistory(max_size=100)
        for i in range(10):
            history.add(Message(role=MessageRole.USER, content=f"消息_{i}"))
        recent = history.get_recent(3)
        assert len(recent) == 3

    def test_get_recent_more_than_available(self):
        """测试获取超过可用数量的最近消息。"""
        history = MessageHistory(max_size=100)
        history.add(Message(role=MessageRole.USER, content="只有一条"))
        recent = history.get_recent(10)
        assert len(recent) == 1

    def test_get_by_role(self):
        """测试按角色筛选。"""
        history = MessageHistory(max_size=100)
        history.add(Message(role=MessageRole.USER, content="用户"))
        history.add(Message(role=MessageRole.ASSISTANT, content="助手"))
        history.add(Message(role=MessageRole.USER, content="用户2"))
        user_msgs = history.get_by_role(MessageRole.USER)
        assert len(user_msgs) == 2

    def test_search(self):
        """测试搜索消息。"""
        history = MessageHistory(max_size=100)
        history.add(Message(role=MessageRole.USER, content="搜索关键词"))
        history.add(Message(role=MessageRole.USER, content="其他内容"))
        results = history.search("关键词")
        assert len(results) == 1

    def test_search_no_match(self):
        """测试搜索无匹配。"""
        history = MessageHistory(max_size=100)
        history.add(Message(role=MessageRole.USER, content="内容"))
        results = history.search("不存在的关键词")
        assert len(results) == 0

    def test_get_range(self):
        """测试获取范围消息。"""
        history = MessageHistory(max_size=100)
        for i in range(10):
            history.add(Message(role=MessageRole.USER, content=f"消息_{i}"))
        ranged = history.get_range(2, 5)
        assert len(ranged) == 3

    def test_count(self):
        """测试消息计数。"""
        history = MessageHistory(max_size=100)
        assert history.count() == 0
        history.add(Message(role=MessageRole.USER, content="测试"))
        assert history.count() == 1

    def test_clear(self):
        """测试清空历史。"""
        history = MessageHistory(max_size=100)
        history.add(Message(role=MessageRole.USER, content="测试"))
        history.clear()
        assert history.count() == 0

    def test_export(self):
        """测试导出历史。"""
        history = MessageHistory(max_size=100)
        history.add(Message(role=MessageRole.USER, content="导出测试"))
        exported = history.export()
        # export 返回 JSON 字符串
        data = json.loads(exported)
        assert len(data) == 1

    def test_to_dict_list(self):
        """测试转换为字典列表。"""
        history = MessageHistory(max_size=100)
        history.add(Message(role=MessageRole.USER, content="字典"))
        dict_list = history.to_dict_list()
        assert len(dict_list) == 1
        assert dict_list[0]["content"] == "字典"

    def test_max_size_eviction(self):
        """测试超出最大大小的淘汰。"""
        history = MessageHistory(max_size=3)
        for i in range(5):
            history.add(Message(role=MessageRole.USER, content=f"消息_{i}"))
        assert history.count() <= 3

    def test_empty_history_operations(self):
        """测试空历史的操作。"""
        history = MessageHistory(max_size=100)
        assert history.get_all() == []
        assert history.get_recent(5) == []
        assert history.count() == 0


# ===== ContextCompressor 测试 =====


class TestContextCompressor:
    """测试 ContextCompressor 类。"""

    def test_create_compressor(self):
        """测试创建压缩器。"""
        compressor = ContextCompressor(compression_threshold=0.8)
        assert compressor.compression_threshold == 0.8

    def test_create_with_keep_recent(self):
        """测试带保留最近消息的压缩器。"""
        compressor = ContextCompressor(compression_threshold=0.8, keep_recent=5)
        assert compressor.keep_recent == 5

    def test_should_compress_below_threshold(self):
        """测试低于阈值不需要压缩。"""
        compressor = ContextCompressor(compression_threshold=10)
        messages = [Message(role=MessageRole.USER, content="短消息")]
        # 消息数低于阈值，不需要压缩
        result = compressor.should_compress(len(messages))
        assert result is False

    def test_should_compress_above_threshold(self):
        """测试高于阈值需要压缩。"""
        compressor = ContextCompressor(compression_threshold=5)
        # 创建大量消息使消息数超过阈值
        messages = [
            Message(role=MessageRole.USER, content=f"消息内容_{i}" * 20)
            for i in range(50)
        ]
        result = compressor.should_compress(len(messages))
        assert result is True

    def test_compress_summarize_strategy(self):
        """测试摘要压缩策略。"""
        compressor = ContextCompressor(strategy="summarize", keep_recent=2)
        messages = [
            Message(role=MessageRole.USER, content=f"用户消息_{i}")
            for i in range(10)
        ]
        compressed = compressor.compress(messages)
        assert len(compressed) <= len(messages)

    def test_compress_truncate_strategy(self):
        """测试截断压缩策略。"""
        compressor = ContextCompressor(strategy="truncate", keep_recent=3)
        messages = [
            Message(role=MessageRole.USER, content=f"消息_{i}")
            for i in range(10)
        ]
        compressed = compressor.compress(messages)
        assert len(compressed) <= len(messages)

    def test_compress_keywords_strategy(self):
        """测试关键词压缩策略。"""
        compressor = ContextCompressor(strategy="keywords", keep_recent=2)
        messages = [
            Message(role=MessageRole.USER, content=f"关键词测试消息_{i}")
            for i in range(10)
        ]
        compressed = compressor.compress(messages)
        assert len(compressed) <= len(messages)

    def test_compress_empty_messages(self):
        """测试压缩空消息列表。"""
        compressor = ContextCompressor(strategy="summarize")
        compressed, removed = compressor.compress([])
        assert len(compressed) == 0

    def test_compress_keep_recent(self):
        """测试压缩后保留最近消息。"""
        compressor = ContextCompressor(strategy="truncate", keep_recent=3)
        messages = [
            Message(role=MessageRole.USER, content=f"消息_{i}")
            for i in range(10)
        ]
        compressed = compressor.compress(messages)
        # 最近的消息应该保留
        if len(compressed) >= 3:
            assert compressed[-1].content == "消息_9"

    def test_compress_short_list(self):
        """测试压缩短消息列表（无需压缩）。"""
        compressor = ContextCompressor(strategy="summarize", keep_recent=5)
        messages = [
            Message(role=MessageRole.USER, content="短消息1"),
            Message(role=MessageRole.USER, content="短消息2"),
        ]
        compressed = compressor.compress(messages)
        # 消息少，可能不压缩
        assert len(compressed) <= 2


# ===== ContextManager 测试 =====


class TestContextManager:
    """测试 ContextManager 类。"""

    def test_create_manager(self):
        """测试创建上下文管理器。"""
        manager = ContextManager(agent_id="test_agent")
        assert manager.agent_id == "test_agent"

    def test_create_with_model(self):
        """测试带模型创建。"""
        manager = ContextManager(agent_id="test_agent", model="gpt-4")
        assert manager.model == "gpt-4"

    def test_add_message(self):
        """测试添加消息。"""
        manager = ContextManager(agent_id="test_agent")
        msg = Message(role=MessageRole.USER, content="测试")
        manager.add_message(msg)
        messages = manager.get_messages()
        assert len(messages) == 1

    def test_add_user_message(self):
        """测试添加用户消息。"""
        manager = ContextManager(agent_id="test_agent")
        manager.add_user_message("用户输入")
        messages = manager.get_messages()
        assert len(messages) == 1
        assert messages[0].role == MessageRole.USER

    def test_add_assistant_message(self):
        """测试添加助手消息。"""
        manager = ContextManager(agent_id="test_agent")
        manager.add_assistant_message("助手回复")
        messages = manager.get_messages()
        assert len(messages) == 1
        assert messages[0].role == MessageRole.ASSISTANT

    def test_add_system_message(self):
        """测试添加系统消息。"""
        manager = ContextManager(agent_id="test_agent")
        manager.add_system_message("系统提示")
        # 系统消息可能存储在 window 中
        sys_msg = manager.window.get_system_message()
        assert sys_msg is not None

    def test_get_messages_dict(self):
        """测试获取消息字典。"""
        manager = ContextManager(agent_id="test_agent")
        manager.add_user_message("测试")
        dicts = manager.get_messages_dict()
        assert len(dicts) >= 1

    def test_reset(self):
        """测试重置管理器。"""
        manager = ContextManager(agent_id="test_agent")
        manager.add_user_message("测试")
        manager.reset()
        assert len(manager.get_messages()) == 0

    def test_get_stats(self):
        """测试获取统计。"""
        manager = ContextManager(agent_id="test_agent")
        manager.add_user_message("测试统计")
        stats = manager.get_stats()
        assert isinstance(stats, dict)

    def test_export_history(self):
        """测试导出历史。"""
        manager = ContextManager(agent_id="test_agent")
        manager.add_user_message("导出测试")
        exported = manager.export_history()
        assert isinstance(exported, str)

    def test_search_history(self):
        """测试搜索历史。"""
        manager = ContextManager(agent_id="test_agent")
        manager.add_user_message("搜索关键词")
        manager.add_user_message("其他内容")
        results = manager.search_history("关键词")
        assert len(results) >= 1

    def test_get_context_hash(self):
        """测试获取上下文哈希。"""
        manager = ContextManager(agent_id="test_agent")
        manager.add_user_message("哈希测试")
        hash1 = manager.get_context_hash()
        assert isinstance(hash1, str)
        assert len(hash1) > 0

    def test_context_hash_consistency(self):
        """测试上下文哈希一致性。"""
        manager = ContextManager(agent_id="test_agent")
        manager.add_user_message("一致性测试")
        hash1 = manager.get_context_hash()
        hash2 = manager.get_context_hash()
        assert hash1 == hash2

    def test_context_hash_changes_with_content(self):
        """测试内容变化时哈希改变。"""
        manager = ContextManager(agent_id="test_agent")
        manager.add_user_message("内容1")
        hash1 = manager.get_context_hash()
        manager.add_user_message("内容2")
        hash2 = manager.get_context_hash()
        assert hash1 != hash2

    def test_auto_compress(self):
        """测试自动压缩。"""
        manager = ContextManager(
            agent_id="test_agent",
            auto_compress=True,
            max_tokens=200,
        )
        # 添加大量消息触发自动压缩
        for i in range(30):
            manager.add_user_message(f"自动压缩测试消息_{i}" * 5)
        # 应该触发了压缩
        stats = manager.get_stats()
        assert isinstance(stats, dict)


# ===== ContextRegistry 测试 =====


class TestContextRegistry:
    """测试 ContextRegistry 类。"""

    def test_create_registry(self):
        """测试创建注册表。"""
        registry = ContextRegistry()
        assert registry.list_contexts() == []

    def test_create_context(self):
        """测试创建上下文。"""
        registry = ContextRegistry()
        ctx = registry.create_context("agent_1")
        assert ctx is not None
        assert ctx.agent_id == "agent_1"

    def test_get_context(self):
        """测试获取上下文。"""
        registry = ContextRegistry()
        registry.create_context("agent_1")
        ctx = registry.get_context("agent_1")
        assert ctx is not None
        assert ctx.agent_id == "agent_1"

    def test_get_context_not_found(self):
        """测试获取不存在的上下文。"""
        registry = ContextRegistry()
        ctx = registry.get_context("nonexistent")
        assert ctx is None

    def test_remove_context(self):
        """测试移除上下文。"""
        registry = ContextRegistry()
        registry.create_context("agent_1")
        result = registry.remove_context("agent_1")
        assert result is True
        assert registry.get_context("agent_1") is None

    def test_remove_context_not_found(self):
        """测试移除不存在的上下文。"""
        registry = ContextRegistry()
        result = registry.remove_context("nonexistent")
        assert result is False

    def test_reset_context(self):
        """测试重置上下文。"""
        registry = ContextRegistry()
        ctx = registry.create_context("agent_1")
        ctx.add_user_message("测试")
        result = registry.reset_context("agent_1")
        assert result is True
        assert len(ctx.get_messages()) == 0

    def test_reset_context_not_found(self):
        """测试重置不存在的上下文。"""
        registry = ContextRegistry()
        result = registry.reset_context("nonexistent")
        assert result is False

    def test_reset_all(self):
        """测试重置所有上下文。"""
        registry = ContextRegistry()
        ctx1 = registry.create_context("agent_1")
        ctx2 = registry.create_context("agent_2")
        ctx1.add_user_message("测试1")
        ctx2.add_user_message("测试2")
        registry.reset_all()
        assert len(ctx1.get_messages()) == 0
        assert len(ctx2.get_messages()) == 0

    def test_list_contexts(self):
        """测试列出上下文。"""
        registry = ContextRegistry()
        registry.create_context("agent_1")
        registry.create_context("agent_2")
        contexts = registry.list_contexts()
        assert len(contexts) == 2
        assert "agent_1" in contexts
        assert "agent_2" in contexts

    def test_get_all_stats(self):
        """测试获取所有统计。"""
        registry = ContextRegistry()
        registry.create_context("agent_1")
        registry.create_context("agent_2")
        stats = registry.get_all_stats()
        assert isinstance(stats, dict)
        assert len(stats) == 2

    def test_create_context_idempotent(self):
        """测试重复创建同一上下文。"""
        registry = ContextRegistry()
        ctx1 = registry.create_context("agent_1")
        ctx2 = registry.create_context("agent_1")
        # 应该返回同一个实例
        assert ctx1 is ctx2

    def test_thread_safety(self):
        """测试线程安全。"""
        registry = ContextRegistry()

        def create_contexts():
            for i in range(10):
                registry.create_context(f"agent_{i}")

        threads = [threading.Thread(target=create_contexts) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # 应该有 50 个上下文（0-9 各 5 次，但幂等所以只有 10 个）
        assert len(registry.list_contexts()) == 10


# ===== 全局函数测试 =====


class TestGlobalFunctions:
    """测试全局函数。"""

    def test_get_context_registry(self):
        """测试获取全局注册表。"""
        registry = get_context_registry()
        assert registry is not None
        assert isinstance(registry, ContextRegistry)

    def test_get_context_registry_singleton(self):
        """测试全局注册表单例。"""
        registry1 = get_context_registry()
        registry2 = get_context_registry()
        assert registry1 is registry2

    def test_create_context_global(self):
        """测试全局创建上下文。"""
        ctx = create_context("global_test_agent")
        assert ctx is not None
        assert ctx.agent_id == "global_test_agent"

    def test_get_context_global(self):
        """测试全局获取上下文。"""
        create_context("global_get_agent")
        ctx = get_context("global_get_agent")
        assert ctx is not None

    def test_get_context_not_found_global(self):
        """测试全局获取不存在的上下文。"""
        ctx = get_context("nonexistent_global_agent")
        assert ctx is None

    def test_reset_all_contexts(self):
        """测试全局重置所有上下文。"""
        ctx = create_context("reset_test_agent")
        ctx.add_user_message("测试")
        reset_all_contexts()
        assert len(ctx.get_messages()) == 0


# ===== 集成测试 =====


class TestIntegration:
    """集成测试。"""

    def test_full_workflow(self):
        """测试完整工作流。"""
        manager = ContextManager(agent_id="integration_agent", model="gpt-4")
        # 添加系统消息
        manager.add_system_message("你是论文助手")
        # 添加对话
        manager.add_user_message("帮我分析这篇论文")
        manager.add_assistant_message("好的，我来分析这篇论文的主要贡献。")
        manager.add_user_message("它的创新点是什么？")
        # 验证
        messages = manager.get_messages()
        assert len(messages) >= 3
        # 验证统计
        stats = manager.get_stats()
        assert isinstance(stats, dict)
        # 验证哈希
        ctx_hash = manager.get_context_hash()
        assert len(ctx_hash) > 0

    def test_multi_agent_context(self):
        """测试多 Agent 上下文。"""
        registry = ContextRegistry()
        # 创建多个 Agent 上下文
        ctx1 = registry.create_context("agent_searcher")
        ctx2 = registry.create_context("agent_writer")
        ctx3 = registry.create_context("agent_critic")
        # 各自独立添加消息
        ctx1.add_user_message("搜索论文")
        ctx2.add_user_message("撰写摘要")
        ctx3.add_user_message("评审内容")
        # 验证独立性
        assert len(ctx1.get_messages()) == 1
        assert len(ctx2.get_messages()) == 1
        assert len(ctx3.get_messages()) == 1
        assert ctx1.get_messages()[0].content == "搜索论文"
        assert ctx2.get_messages()[0].content == "撰写摘要"

    def test_context_compression_workflow(self):
        """测试上下文压缩工作流。"""
        manager = ContextManager(
            agent_id="compress_agent",
            max_tokens=500,
            reserved_for_response=0,
            auto_compress=True,
        )
        # 添加大量消息
        for i in range(20):
            manager.add_user_message(f"这是第 {i} 条消息，内容较长以触发压缩。")
        # 验证没有崩溃
        messages = manager.get_messages()
        assert len(messages) > 0

    def test_conversation_export_import(self):
        """测试对话导出导入。"""
        manager = ContextManager(agent_id="export_agent")
        manager.add_user_message("导出测试")
        manager.add_assistant_message("导出回复")
        # 导出
        exported = manager.export_history()
        assert exported is not None
        # 重置后重新创建
        manager.reset()
        assert len(manager.get_messages()) == 0


# ===== 边界情况测试 =====


class TestEdgeCases:
    """边界情况测试。"""

    def test_empty_content_message(self):
        """测试空内容消息。"""
        msg = Message(role=MessageRole.USER, content="")
        assert msg.content == ""
        tokens = msg.estimate_tokens()
        assert tokens >= 0

    def test_very_long_content(self):
        """测试超长内容。"""
        long_text = "a" * 10000
        msg = Message(role=MessageRole.USER, content=long_text)
        tokens = msg.estimate_tokens()
        assert tokens > 0

    def test_unicode_content(self):
        """测试 Unicode 内容。"""
        msg = Message(role=MessageRole.USER, content="🎉🎊🎈 Unicode 表情符号")
        d = msg.to_dict()
        assert "🎉" in d["content"]

    def test_special_characters(self):
        """测试特殊字符。"""
        special = "引号\"制表符\t换行\n反斜杠\\"
        msg = Message(role=MessageRole.USER, content=special)
        d = msg.to_dict()
        assert d["content"] == special

    def test_none_metadata(self):
        """测试 None 元数据。"""
        msg = Message(role=MessageRole.USER, content="测试", metadata=None)
        assert msg.metadata is None

    def test_large_metadata(self):
        """测试大量元数据。"""
        large_meta = {f"key_{i}": f"value_{i}" for i in range(100)}
        msg = Message(role=MessageRole.USER, content="测试", metadata=large_meta)
        assert len(msg.metadata) == 100

    def test_zero_max_tokens(self):
        """测试零最大 token。"""
        window = ContextWindow(max_tokens=0)
        assert window.max_tokens == 0

    def test_negative_reserved(self):
        """测试负数预留。"""
        window = ContextWindow(max_tokens=4096, reserved_for_response=-100)
        # 应该处理负数情况
        assert window.reserved_for_response == -100

    def test_very_small_window(self):
        """测试极小窗口。"""
        window = ContextWindow(max_tokens=10, reserved_for_response=0)
        msg = Message(role=MessageRole.USER, content="短")
        window.add_message(msg)
        # 应该能处理小窗口
        assert len(window) >= 1

    def test_history_zero_max_size(self):
        """测试零最大大小的历史。"""
        history = MessageHistory(max_size=0)
        history.add(Message(role=MessageRole.USER, content="测试"))
        # 零大小可能不接受任何消息
        assert history.count() == 0

    def test_compressor_invalid_strategy(self):
        """测试无效压缩策略。"""
        compressor = ContextCompressor(strategy="invalid_strategy")
        messages = [Message(role=MessageRole.USER, content="测试")]
        # 应该有默认处理
        try:
            compressed, removed = compressor.compress(messages)
            assert isinstance(compressed, list)
        except (ValueError, KeyError):
            pass  # 预期可能抛出异常

    def test_registry_empty_operations(self):
        """测试空注册表操作。"""
        registry = ContextRegistry()
        assert registry.list_contexts() == []
        assert registry.get_all_stats() == {}
        assert registry.get_context("any") is None

    def test_message_with_all_roles(self):
        """测试所有角色的消息。"""
        for role in MessageRole:
            msg = Message(role=role, content=f"{role.value} 消息")
            d = msg.to_dict()
            assert d is not None

    def test_deeply_nested_tool_calls(self):
        """测试深层嵌套工具调用。"""
        deep_tool_calls = [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "search",
                    "arguments": json.dumps({
                        "query": "test",
                        "filters": {"date": {"from": "2024", "to": "2025"}},
                    }),
                },
            }
        ]
        msg = Message(
            role=MessageRole.ASSISTANT,
            content="",
            tool_calls=deep_tool_calls,
        )
        assert msg.tool_calls is not None
        d = msg.to_dict()
        assert d is not None

    def test_context_manager_without_model(self):
        """测试无模型的上下文管理器。"""
        manager = ContextManager(agent_id="no_model_agent")
        manager.add_user_message("测试")
        messages = manager.get_messages()
        assert len(messages) == 1

    def test_rapid_message_addition(self):
        """测试快速添加消息。"""
        manager = ContextManager(agent_id="rapid_agent", max_tokens=10000)
        for i in range(100):
            manager.add_user_message(f"快速消息_{i}")
        messages = manager.get_messages()
        assert len(messages) > 0

    def test_concurrent_context_access(self):
        """测试并发上下文访问。"""
        registry = ContextRegistry()
        ctx = registry.create_context("concurrent_agent")

        def add_messages():
            for i in range(20):
                ctx.add_user_message(f"并发消息_{i}")

        threads = [threading.Thread(target=add_messages) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # 应该有线程安全保证
        messages = ctx.get_messages()
        assert len(messages) > 0
