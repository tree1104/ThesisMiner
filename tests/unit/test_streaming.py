"""streaming 模块单元测试

覆盖 backend/ai/streaming.py 中的所有组件：
- StreamEventType: 流式事件类型枚举
- SSEEvent: SSE 事件数据结构（序列化/反序列化）
- StreamChunk: 流式分块数据结构
- StreamStats: 流式统计（持续时间/速率/转字典）
- SSEStreamParser: SSE 流解析器（喂入/缓冲/重组）
- StreamChunkProcessor: 流分块处理器（OpenAI/Anthropic 格式）
- ReasoningContentSeparator: 推理与内容分离器
- BackpressureController: 背压控制器（有界缓冲/高低水位）
- StreamAggregator: 流聚合器（合并分块）
- StreamingResponseBuilder: 流式响应构建器
- 异步流工具（stream_to_list/merge_streams/transform_stream/filter_stream/batch_stream/stream_with_timeout）
- 便捷函数（create_sse_response/create_sse_stream/parse_sse_stream/process_stream_response）
"""
import asyncio
import json
import time
from typing import AsyncIterator

import pytest

from backend.ai.streaming import (
    StreamEventType,
    SSEEvent,
    StreamChunk,
    StreamStats,
    SSEStreamParser,
    StreamChunkProcessor,
    ReasoningContentSeparator,
    BackpressureController,
    StreamAggregator,
    StreamingResponseBuilder,
    stream_to_list,
    merge_streams,
    transform_stream,
    filter_stream,
    batch_stream,
    stream_with_timeout,
    create_sse_response,
    create_sse_stream,
    parse_sse_stream,
    process_stream_response,
)


# ===== StreamEventType 测试 =====


class TestStreamEventType:
    """StreamEventType 枚举测试"""

    def test_event_types(self):
        """事件类型值"""
        assert StreamEventType.START.value == "start"
        assert StreamEventType.DELTA.value == "delta"
        assert StreamEventType.REASONING_DELTA.value == "reasoning_delta"
        assert StreamEventType.CONTENT_DELTA.value == "content_delta"
        assert StreamEventType.TOOL_CALL.value == "tool_call"
        assert StreamEventType.CITATION.value == "citation"
        assert StreamEventType.USAGE.value == "usage"
        assert StreamEventType.DONE.value == "done"
        assert StreamEventType.ERROR.value == "error"
        assert StreamEventType.HEARTBEAT.value == "heartbeat"
        assert StreamEventType.METADATA.value == "metadata"

    def test_is_string_enum(self):
        """字符串枚举"""
        assert isinstance(StreamEventType.START, str)
        assert StreamEventType.START == "start"


# ===== SSEEvent 测试 =====


class TestSSEEvent:
    """SSEEvent 数据结构测试"""

    def test_default_values(self):
        """默认值"""
        event = SSEEvent()
        assert event.event == "message"
        assert event.data == ""
        assert event.id == ""
        assert event.retry == 0
        assert event.comment == ""

    def test_to_sse_string_basic(self):
        """基本 SSE 字符串"""
        event = SSEEvent(data="hello")
        sse = event.to_sse_string()
        assert "data: hello" in sse
        assert sse.endswith("\n\n")

    def test_to_sse_string_with_event(self):
        """带事件类型"""
        event = SSEEvent(event="custom", data="test")
        sse = event.to_sse_string()
        assert "event: custom" in sse
        assert "data: test" in sse

    def test_to_sse_string_with_id(self):
        """带 ID"""
        event = SSEEvent(id="123", data="test")
        sse = event.to_sse_string()
        assert "id: 123" in sse

    def test_to_sse_string_with_retry(self):
        """带重试"""
        event = SSEEvent(retry=5000, data="test")
        sse = event.to_sse_string()
        assert "retry: 5000" in sse

    def test_to_sse_string_with_comment(self):
        """带注释"""
        event = SSEEvent(comment="heartbeat", data="")
        sse = event.to_sse_string()
        assert ": heartbeat" in sse

    def test_to_sse_string_multiline_data(self):
        """多行数据"""
        event = SSEEvent(data="line1\nline2")
        sse = event.to_sse_string()
        assert "data: line1" in sse
        assert "data: line2" in sse

    def test_to_sse_string_empty_data(self):
        """空数据"""
        event = SSEEvent(data="")
        sse = event.to_sse_string()
        assert "data: " in sse

    def test_to_sse_string_message_no_event_field(self):
        """message 事件不输出 event 字段"""
        event = SSEEvent(event="message", data="test")
        sse = event.to_sse_string()
        assert "event:" not in sse

    def test_from_data_string(self):
        """从字符串创建"""
        event = SSEEvent.from_data("hello")
        assert event.data == "hello"
        assert event.event == "message"

    def test_from_data_dict(self):
        """从字典创建（JSON 序列化）"""
        event = SSEEvent.from_data({"key": "value"})
        assert json.loads(event.data) == {"key": "value"}

    def test_from_data_with_event(self):
        """带事件类型创建"""
        event = SSEEvent.from_data("test", event="custom")
        assert event.event == "custom"

    def test_from_data_list(self):
        """从列表创建"""
        event = SSEEvent.from_data([1, 2, 3])
        assert json.loads(event.data) == [1, 2, 3]


# ===== StreamChunk 测试 =====


class TestStreamChunk:
    """StreamChunk 数据结构测试"""

    def test_default_values(self):
        """默认值"""
        chunk = StreamChunk()
        assert chunk.content == ""
        assert chunk.reasoning == ""
        assert chunk.event_type == StreamEventType.CONTENT_DELTA.value
        assert chunk.metadata == {}
        assert chunk.is_final is False
        assert chunk.index == 0

    def test_custom_values(self):
        """自定义值"""
        chunk = StreamChunk(
            content="hello",
            reasoning="thinking",
            event_type=StreamEventType.DELTA.value,
            is_final=True,
            index=5,
        )
        assert chunk.content == "hello"
        assert chunk.reasoning == "thinking"
        assert chunk.is_final is True
        assert chunk.index == 5

    def test_timestamp_auto(self):
        """自动时间戳"""
        chunk = StreamChunk()
        assert chunk.timestamp > 0


# ===== StreamStats 测试 =====


class TestStreamStats:
    """StreamStats 统计测试"""

    def test_default_values(self):
        """默认值"""
        stats = StreamStats()
        assert stats.total_chunks == 0
        assert stats.content_chunks == 0
        assert stats.reasoning_chunks == 0
        assert stats.total_content_chars == 0
        assert stats.total_reasoning_chars == 0
        assert stats.errors == 0

    def test_duration(self):
        """持续时间"""
        stats = StreamStats()
        stats.start_time = time.time() - 1
        assert stats.duration >= 1.0

    def test_duration_with_end_time(self):
        """带结束时间"""
        stats = StreamStats()
        stats.start_time = 100.0
        stats.end_time = 105.0
        assert stats.duration == 5.0

    def test_chars_per_second(self):
        """每秒字符数"""
        stats = StreamStats()
        stats.start_time = time.time() - 1
        stats.total_content_chars = 100
        assert stats.chars_per_second >= 100.0

    def test_chars_per_second_zero_duration(self):
        """零持续时间"""
        stats = StreamStats()
        stats.start_time = time.time()
        assert stats.chars_per_second == 0.0

    def test_to_dict(self):
        """转字典"""
        stats = StreamStats()
        stats.total_chunks = 10
        d = stats.to_dict()
        assert d["total_chunks"] == 10
        assert "duration" in d
        assert "chars_per_second" in d
        assert "errors" in d


# ===== SSEStreamParser 测试 =====


class TestSSEStreamParser:
    """SSEStreamParser 流解析器测试"""

    def test_feed_single_event(self):
        """喂入单个事件"""
        parser = SSEStreamParser()
        events = parser.feed("data: hello\n\n")
        assert len(events) == 1
        assert events[0].data == "hello"

    def test_feed_multiple_events(self):
        """喂入多个事件"""
        parser = SSEStreamParser()
        data = "data: first\n\ndata: second\n\n"
        events = parser.feed(data)
        assert len(events) == 2
        assert events[0].data == "first"
        assert events[1].data == "second"

    def test_feed_partial_event(self):
        """喂入不完整事件"""
        parser = SSEStreamParser()
        events = parser.feed("data: hel")
        assert len(events) == 0
        events = parser.feed("lo\n\n")
        assert len(events) == 1
        assert events[0].data == "hello"

    def test_feed_with_event_type(self):
        """带事件类型"""
        parser = SSEStreamParser()
        events = parser.feed("event: custom\ndata: test\n\n")
        assert len(events) == 1
        assert events[0].event == "custom"
        assert events[0].data == "test"

    def test_feed_with_id(self):
        """带 ID"""
        parser = SSEStreamParser()
        events = parser.feed("id: 123\ndata: test\n\n")
        assert events[0].id == "123"

    def test_feed_with_retry(self):
        """带重试"""
        parser = SSEStreamParser()
        events = parser.feed("retry: 5000\ndata: test\n\n")
        assert events[0].retry == 5000

    def test_feed_with_comment(self):
        """带注释"""
        parser = SSEStreamParser()
        events = parser.feed(": heartbeat\ndata: test\n\n")
        assert events[0].comment == "heartbeat"

    def test_feed_multiline_data(self):
        """多行数据"""
        parser = SSEStreamParser()
        events = parser.feed("data: line1\ndata: line2\n\n")
        assert events[0].data == "line1\nline2"

    def test_feed_bytes(self):
        """喂入字节数据"""
        parser = SSEStreamParser()
        events = parser.feed_bytes(b"data: hello\n\n")
        assert len(events) == 1
        assert events[0].data == "hello"

    def test_feed_empty(self):
        """空数据"""
        parser = SSEStreamParser()
        assert parser.feed("") == []

    def test_feed_crlf_line_endings(self):
        """CRLF 行尾"""
        parser = SSEStreamParser()
        events = parser.feed("data: hello\r\n\r\n")
        assert len(events) == 1
        assert events[0].data == "hello"

    def test_reset(self):
        """重置"""
        parser = SSEStreamParser()
        parser.feed("partial data")
        parser.reset()
        assert parser.get_remaining_buffer() == ""

    def test_get_remaining_buffer(self):
        """获取剩余缓冲"""
        parser = SSEStreamParser()
        parser.feed("partial")
        assert parser.get_remaining_buffer() == "partial"


# ===== StreamChunkProcessor 测试 =====


class TestStreamChunkProcessor:
    """StreamChunkProcessor 分块处理器测试"""

    def test_process_openai_content(self):
        """处理 OpenAI 内容分块"""
        processor = StreamChunkProcessor(provider="openai")
        data = json.dumps({
            "choices": [{"delta": {"content": "hello"}, "index": 0}]
        })
        chunk = processor.process_chunk(data)
        assert chunk is not None
        assert chunk.content == "hello"
        assert chunk.event_type == StreamEventType.CONTENT_DELTA.value

    def test_process_openai_reasoning(self):
        """处理 OpenAI 推理分块"""
        processor = StreamChunkProcessor(provider="openai")
        data = json.dumps({
            "choices": [{"delta": {"reasoning_content": "thinking"}, "index": 0}]
        })
        chunk = processor.process_chunk(data)
        assert chunk is not None
        assert chunk.reasoning == "thinking"
        assert chunk.event_type == StreamEventType.REASONING_DELTA.value

    def test_process_openai_done(self):
        """处理 OpenAI 完成标记"""
        processor = StreamChunkProcessor(provider="openai")
        chunk = processor.process_chunk("[DONE]")
        assert chunk is not None
        assert chunk.is_final is True
        assert chunk.event_type == StreamEventType.DONE.value

    def test_process_openai_finish_reason(self):
        """处理 finish_reason"""
        processor = StreamChunkProcessor(provider="openai")
        data = json.dumps({
            "choices": [{"delta": {}, "finish_reason": "stop", "index": 0}]
        })
        chunk = processor.process_chunk(data)
        assert chunk is not None
        assert chunk.event_type == StreamEventType.DONE.value

    def test_process_openai_usage(self):
        """处理 usage 事件"""
        processor = StreamChunkProcessor(provider="openai")
        data = json.dumps({"usage": {"total_tokens": 100}})
        chunk = processor.process_chunk(data)
        assert chunk is not None
        assert chunk.event_type == StreamEventType.USAGE.value

    def test_process_openai_tool_call(self):
        """处理工具调用"""
        processor = StreamChunkProcessor(provider="openai")
        data = json.dumps({
            "choices": [{"delta": {"tool_calls": [{"id": "call_1"}]}, "index": 0}]
        })
        chunk = processor.process_chunk(data)
        assert chunk is not None
        assert chunk.event_type == StreamEventType.TOOL_CALL.value

    def test_process_invalid_json(self):
        """处理无效 JSON"""
        processor = StreamChunkProcessor(provider="openai")
        chunk = processor.process_chunk("invalid json")
        assert chunk is None
        assert processor.stats.errors == 1

    def test_process_empty(self):
        """处理空数据"""
        processor = StreamChunkProcessor(provider="openai")
        chunk = processor.process_chunk("")
        assert chunk is not None
        assert chunk.is_final is True

    def test_process_anthropic_start(self):
        """处理 Anthropic 开始事件"""
        processor = StreamChunkProcessor(provider="anthropic")
        data = json.dumps({"type": "message_start", "message": {}})
        chunk = processor.process_chunk(data)
        assert chunk is not None
        assert chunk.event_type == StreamEventType.START.value

    def test_process_anthropic_content_delta(self):
        """处理 Anthropic 内容增量"""
        processor = StreamChunkProcessor(provider="anthropic")
        data = json.dumps({
            "type": "content_block_delta",
            "delta": {"type": "text_delta", "text": "hello"}
        })
        chunk = processor.process_chunk(data)
        assert chunk is not None
        assert chunk.content == "hello"
        assert chunk.event_type == StreamEventType.CONTENT_DELTA.value

    def test_process_anthropic_thinking_delta(self):
        """处理 Anthropic 思考增量"""
        processor = StreamChunkProcessor(provider="anthropic")
        data = json.dumps({
            "type": "content_block_delta",
            "delta": {"type": "thinking_delta", "thinking": "reasoning"}
        })
        chunk = processor.process_chunk(data)
        assert chunk is not None
        assert chunk.reasoning == "reasoning"
        assert chunk.event_type == StreamEventType.REASONING_DELTA.value

    def test_process_anthropic_stop(self):
        """处理 Anthropic 停止"""
        processor = StreamChunkProcessor(provider="anthropic")
        data = json.dumps({"type": "message_stop"})
        chunk = processor.process_chunk(data)
        assert chunk is not None
        assert chunk.is_final is True

    def test_stats_tracking(self):
        """统计跟踪"""
        processor = StreamChunkProcessor(provider="openai")
        # 内容分块
        processor.process_chunk(json.dumps({
            "choices": [{"delta": {"content": "hello"}}]
        }))
        # 推理分块
        processor.process_chunk(json.dumps({
            "choices": [{"delta": {"reasoning_content": "thinking"}}]
        }))
        assert processor.stats.total_chunks == 2
        assert processor.stats.content_chunks == 1
        assert processor.stats.reasoning_chunks == 1
        assert processor.stats.total_content_chars == 5
        assert processor.stats.total_reasoning_chars == 8

    def test_reset(self):
        """重置"""
        processor = StreamChunkProcessor(provider="openai")
        processor.process_chunk(json.dumps({
            "choices": [{"delta": {"content": "hello"}}]
        }))
        processor.reset()
        assert processor.stats.total_chunks == 0
        assert processor._chunk_index == 0

    def test_deepseek_provider(self):
        """DeepSeek 提供商（兼容 OpenAI）"""
        processor = StreamChunkProcessor(provider="deepseek")
        data = json.dumps({
            "choices": [{"delta": {"content": "hello", "reasoning_content": "thinking"}}]
        })
        chunk = processor.process_chunk(data)
        assert chunk is not None
        # 有 content 时优先 content
        assert chunk.content == "hello"


# ===== ReasoningContentSeparator 测试 =====


class TestReasoningContentSeparator:
    """ReasoningContentSeparator 推理内容分离器测试"""

    def test_process_reasoning(self):
        """处理推理分块"""
        separator = ReasoningContentSeparator()
        chunk = StreamChunk(
            reasoning="thinking",
            event_type=StreamEventType.REASONING_DELTA.value,
        )
        result = separator.process(chunk)
        assert result["reasoning"] == "thinking"
        assert result["content"] == ""

    def test_process_content(self):
        """处理内容分块"""
        separator = ReasoningContentSeparator()
        chunk = StreamChunk(
            content="hello",
            event_type=StreamEventType.CONTENT_DELTA.value,
        )
        result = separator.process(chunk)
        assert result["content"] == "hello"
        assert result["reasoning"] == ""

    def test_process_done(self):
        """处理完成分块"""
        separator = ReasoningContentSeparator()
        chunk = StreamChunk(
            event_type=StreamEventType.DONE.value,
            is_final=True,
        )
        result = separator.process(chunk)
        assert result["type"] == "done"

    def test_transition_reasoning_to_content(self):
        """推理转内容"""
        separator = ReasoningContentSeparator()
        # 推理
        separator.process(StreamChunk(
            reasoning="thinking",
            event_type=StreamEventType.REASONING_DELTA.value,
        ))
        assert separator.in_reasoning is True
        # 内容
        separator.process(StreamChunk(
            content="hello",
            event_type=StreamEventType.CONTENT_DELTA.value,
        ))
        assert separator.in_reasoning is False
        assert separator.reasoning_complete is True

    def test_get_full_reasoning(self):
        """获取完整推理"""
        separator = ReasoningContentSeparator()
        separator.process(StreamChunk(
            reasoning="part1",
            event_type=StreamEventType.REASONING_DELTA.value,
        ))
        separator.process(StreamChunk(
            reasoning="part2",
            event_type=StreamEventType.REASONING_DELTA.value,
        ))
        assert separator.get_full_reasoning() == "part1part2"

    def test_get_full_content(self):
        """获取完整内容"""
        separator = ReasoningContentSeparator()
        separator.process(StreamChunk(
            content="hello ",
            event_type=StreamEventType.CONTENT_DELTA.value,
        ))
        separator.process(StreamChunk(
            content="world",
            event_type=StreamEventType.CONTENT_DELTA.value,
        ))
        assert separator.get_full_content() == "hello world"

    def test_reset(self):
        """重置"""
        separator = ReasoningContentSeparator()
        separator.process(StreamChunk(
            reasoning="thinking",
            event_type=StreamEventType.REASONING_DELTA.value,
        ))
        separator.reset()
        assert separator.reasoning_buffer == ""
        assert separator.content_buffer == ""
        assert separator.in_reasoning is False


# ===== BackpressureController 测试 =====


class TestBackpressureController:
    """BackpressureController 背压控制器测试"""

    @pytest.mark.asyncio
    async def test_put_and_get(self):
        """放入与获取"""
        controller = BackpressureController(max_buffer_size=10)
        await controller.put("item1")
        item = await controller.get()
        assert item == "item1"

    @pytest.mark.asyncio
    async def test_put_nowait(self):
        """非阻塞放入"""
        controller = BackpressureController(max_buffer_size=10)
        assert controller.put_nowait("item") is True
        assert controller.buffer_size() == 1

    @pytest.mark.asyncio
    async def test_put_nowait_full(self):
        """缓冲区满"""
        controller = BackpressureController(max_buffer_size=2)
        controller.put_nowait("item1")
        controller.put_nowait("item2")
        assert controller.put_nowait("item3") is False

    @pytest.mark.asyncio
    async def test_get_nowait(self):
        """非阻塞获取"""
        controller = BackpressureController(max_buffer_size=10)
        controller.put_nowait("item")
        item = controller.get_nowait()
        assert item == "item"

    @pytest.mark.asyncio
    async def test_get_nowait_empty(self):
        """空缓冲区获取"""
        controller = BackpressureController(max_buffer_size=10)
        assert controller.get_nowait() is None

    @pytest.mark.asyncio
    async def test_should_pause(self):
        """应暂停"""
        controller = BackpressureController(
            max_buffer_size=100,
            high_watermark=80,
            low_watermark=20,
        )
        for i in range(85):
            controller.put_nowait(f"item{i}")
        assert controller.should_pause() is True

    @pytest.mark.asyncio
    async def test_should_resume(self):
        """应恢复"""
        controller = BackpressureController(
            max_buffer_size=100,
            high_watermark=80,
            low_watermark=20,
        )
        for i in range(10):
            controller.put_nowait(f"item{i}")
        assert controller.should_resume() is True

    @pytest.mark.asyncio
    async def test_close(self):
        """关闭"""
        controller = BackpressureController(max_buffer_size=10)
        controller.close()
        assert await controller.put("item") is False

    @pytest.mark.asyncio
    async def test_get_from_closed_empty(self):
        """从已关闭空缓冲获取"""
        controller = BackpressureController(max_buffer_size=10)
        controller.close()
        assert await controller.get() is None

    @pytest.mark.asyncio
    async def test_buffer_size(self):
        """缓冲区大小"""
        controller = BackpressureController(max_buffer_size=10)
        assert controller.buffer_size() == 0
        controller.put_nowait("item")
        assert controller.buffer_size() == 1

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """获取统计"""
        controller = BackpressureController(max_buffer_size=10)
        controller.put_nowait("item1")
        controller.put_nowait("item2")
        controller.get_nowait()
        stats = controller.get_stats()
        assert stats["produced"] == 2
        assert stats["consumed"] == 1
        assert stats["buffer_size"] == 1

    @pytest.mark.asyncio
    async def test_fifo_order(self):
        """FIFO 顺序"""
        controller = BackpressureController(max_buffer_size=10)
        await controller.put("first")
        await controller.put("second")
        assert await controller.get() == "first"
        assert await controller.get() == "second"


# ===== StreamAggregator 测试 =====


class TestStreamAggregator:
    """StreamAggregator 流聚合器测试"""

    def test_add_content_chunk(self):
        """添加内容分块"""
        aggregator = StreamAggregator()
        aggregator.add_chunk(StreamChunk(content="hello"))
        assert aggregator.get_full_content() == "hello"

    def test_add_multiple_content_chunks(self):
        """添加多个内容分块"""
        aggregator = StreamAggregator()
        aggregator.add_chunk(StreamChunk(content="hello "))
        aggregator.add_chunk(StreamChunk(content="world"))
        assert aggregator.get_full_content() == "hello world"

    def test_add_reasoning_chunk(self):
        """添加推理分块"""
        aggregator = StreamAggregator()
        aggregator.add_chunk(StreamChunk(reasoning="thinking"))
        assert aggregator.get_full_reasoning() == "thinking"

    def test_add_usage_chunk(self):
        """添加用量分块"""
        aggregator = StreamAggregator()
        aggregator.add_chunk(StreamChunk(
            event_type=StreamEventType.USAGE.value,
            metadata={"usage": {"total_tokens": 100}},
        ))
        assert aggregator.usage == {"total_tokens": 100}

    def test_add_final_chunk(self):
        """添加完成分块"""
        aggregator = StreamAggregator()
        aggregator.add_chunk(StreamChunk(is_final=True))
        assert aggregator.is_complete is True

    def test_add_error_chunk(self):
        """添加错误分块"""
        aggregator = StreamAggregator()
        aggregator.add_chunk(StreamChunk(
            event_type=StreamEventType.ERROR.value,
            content="error message",
        ))
        assert aggregator.error == "error message"

    def test_get_result(self):
        """获取结果"""
        aggregator = StreamAggregator()
        aggregator.add_chunk(StreamChunk(content="hello"))
        aggregator.add_chunk(StreamChunk(is_final=True))
        result = aggregator.get_result()
        assert result["content"] == "hello"
        assert result["is_complete"] is True
        assert "metadata" in result
        assert "usage" in result

    def test_reset(self):
        """重置"""
        aggregator = StreamAggregator()
        aggregator.add_chunk(StreamChunk(content="hello"))
        aggregator.reset()
        assert aggregator.get_full_content() == ""
        assert aggregator.is_complete is False


# ===== StreamingResponseBuilder 测试 =====


class TestStreamingResponseBuilder:
    """StreamingResponseBuilder 响应构建器测试"""

    def test_add_event(self):
        """添加事件"""
        builder = StreamingResponseBuilder()
        builder.add_event("custom", {"key": "value"})
        assert len(builder.events) == 1

    def test_add_data(self):
        """添加数据"""
        builder = StreamingResponseBuilder()
        builder.add_data("hello")
        assert len(builder.events) == 1

    def test_add_start(self):
        """添加开始事件"""
        builder = StreamingResponseBuilder()
        builder.add_start({"model": "gpt-4"})
        assert len(builder.events) == 1

    def test_add_delta(self):
        """添加增量"""
        builder = StreamingResponseBuilder()
        builder.add_delta(content="hello", reasoning="thinking")
        assert len(builder.events) == 1

    def test_add_content_delta(self):
        """添加内容增量"""
        builder = StreamingResponseBuilder()
        builder.add_content_delta("hello")
        assert len(builder.events) == 1

    def test_add_reasoning_delta(self):
        """添加推理增量"""
        builder = StreamingResponseBuilder()
        builder.add_reasoning_delta("thinking")
        assert len(builder.events) == 1

    def test_add_usage(self):
        """添加用量"""
        builder = StreamingResponseBuilder()
        builder.add_usage({"total_tokens": 100})
        assert len(builder.events) == 1

    def test_add_error(self):
        """添加错误"""
        builder = StreamingResponseBuilder()
        builder.add_error("error message", code="ERR001")
        assert len(builder.events) == 1

    def test_add_done(self):
        """添加完成"""
        builder = StreamingResponseBuilder()
        builder.add_done({"finish_reason": "stop"})
        assert len(builder.events) == 1

    def test_add_heartbeat(self):
        """添加心跳"""
        builder = StreamingResponseBuilder()
        builder.add_heartbeat()
        assert len(builder.events) == 1

    def test_build(self):
        """构建响应"""
        builder = StreamingResponseBuilder()
        builder.add_data("hello")
        result = builder.build()
        assert "data: hello" in result
        assert result.endswith("\n\n")

    def test_build_multiple_events(self):
        """构建多事件"""
        builder = StreamingResponseBuilder()
        builder.add_start()
        builder.add_content_delta("hello")
        builder.add_done()
        result = builder.build()
        assert "event: start" in result
        assert "event: content_delta" in result
        assert "event: done" in result

    def test_build_chunks(self):
        """构建分块列表"""
        builder = StreamingResponseBuilder()
        builder.add_data("hello")
        builder.add_data("world")
        chunks = builder.build_chunks()
        assert len(chunks) == 2

    def test_clear(self):
        """清空"""
        builder = StreamingResponseBuilder()
        builder.add_data("hello")
        builder.clear()
        assert len(builder.events) == 0


# ===== 异步流工具测试 =====


class TestAsyncStreamTools:
    """异步流工具测试"""

    @pytest.mark.asyncio
    async def test_stream_to_list(self):
        """流转列表"""
        async def sample_stream():
            yield 1
            yield 2
            yield 3

        result = await stream_to_list(sample_stream())
        assert result == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_transform_stream(self):
        """转换流"""
        async def sample_stream():
            yield 1
            yield 2
            yield 3

        result = await stream_to_list(
            transform_stream(sample_stream(), lambda x: x * 2)
        )
        assert result == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_filter_stream(self):
        """过滤流"""
        async def sample_stream():
            yield 1
            yield 2
            yield 3
            yield 4

        result = await stream_to_list(
            filter_stream(sample_stream(), lambda x: x % 2 == 0)
        )
        assert result == [2, 4]

    @pytest.mark.asyncio
    async def test_batch_stream(self):
        """批量流"""
        async def sample_stream():
            for i in range(5):
                yield i

        result = await stream_to_list(batch_stream(sample_stream(), batch_size=2))
        assert result == [[0, 1], [2, 3], [4]]

    @pytest.mark.asyncio
    async def test_stream_with_timeout(self):
        """带超时流"""
        async def sample_stream():
            yield 1
            yield 2

        result = await stream_to_list(stream_with_timeout(sample_stream(), timeout=1.0))
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_stream_with_timeout_exceeded(self):
        """超时流"""
        async def slow_stream():
            yield 1
            await asyncio.sleep(10)
            yield 2

        result = await stream_to_list(stream_with_timeout(slow_stream(), timeout=0.05))
        assert len(result) == 2  # 1 + timeout error chunk
        assert result[1].event_type == StreamEventType.ERROR.value

    @pytest.mark.asyncio
    async def test_merge_streams(self):
        """合并流"""
        async def stream1():
            yield 1
            yield 3

        async def stream2():
            yield 2
            yield 4

        result = await stream_to_list(merge_streams(stream1(), stream2()))
        assert sorted(result) == [1, 2, 3, 4]


# ===== 便捷函数测试 =====


class TestConvenienceFunctions:
    """便捷函数测试"""

    def test_create_sse_response(self):
        """创建 SSE 响应"""
        result = create_sse_response({"key": "value"})
        assert "data:" in result
        assert result.endswith("\n\n")

    def test_create_sse_response_with_event(self):
        """带事件类型"""
        result = create_sse_response("hello", event="custom")
        assert "event: custom" in result

    def test_create_sse_stream(self):
        """创建 SSE 流"""
        events = [
            {"event": "start", "data": {"model": "gpt-4"}},
            {"event": "delta", "data": {"content": "hello"}},
        ]
        result = create_sse_stream(events)
        assert "event: start" in result
        assert "event: delta" in result

    def test_create_sse_stream_plain_data(self):
        """纯数据流"""
        events = ["hello", "world"]
        result = create_sse_stream(events)
        assert "data: hello" in result
        assert "data: world" in result

    def test_parse_sse_stream(self):
        """解析 SSE 流"""
        text = "data: hello\n\ndata: world\n\n"
        events = parse_sse_stream(text)
        assert len(events) == 2
        assert events[0].data == "hello"
        assert events[1].data == "world"

    @pytest.mark.asyncio
    async def test_process_stream_response(self):
        """处理流式响应"""
        async def mock_stream():
            yield json.dumps({"choices": [{"delta": {"content": "hello"}}]})
            yield json.dumps({"choices": [{"delta": {"content": " world"}}]})
            yield "[DONE]"

        result = await process_stream_response(mock_stream(), provider="openai")
        assert result["content"] == "hello world"
        assert result["is_complete"] is True

    @pytest.mark.asyncio
    async def test_process_stream_response_with_callbacks(self):
        """带回调处理流"""
        content_parts = []
        done_called = False

        async def mock_stream():
            yield json.dumps({"choices": [{"delta": {"content": "hello"}}]})
            yield "[DONE]"

        def on_content(content):
            content_parts.append(content)

        def on_done(result):
            nonlocal done_called
            done_called = True

        result = await process_stream_response(
            mock_stream(),
            provider="openai",
            on_content=on_content,
            on_done=on_done,
        )
        assert len(content_parts) == 1
        assert done_called is True

    @pytest.mark.asyncio
    async def test_process_stream_response_async_callbacks(self):
        """异步回调"""
        content_parts = []

        async def mock_stream():
            yield json.dumps({"choices": [{"delta": {"content": "hello"}}]})
            yield "[DONE]"

        async def on_content(content):
            content_parts.append(content)

        await process_stream_response(
            mock_stream(),
            provider="openai",
            on_content=on_content,
        )
        assert len(content_parts) == 1

    @pytest.mark.asyncio
    async def test_process_stream_response_with_reasoning(self):
        """带推理的流"""
        async def mock_stream():
            yield json.dumps({"choices": [{"delta": {"reasoning_content": "thinking"}}]})
            yield json.dumps({"choices": [{"delta": {"content": "answer"}}]})
            yield "[DONE]"

        result = await process_stream_response(mock_stream(), provider="openai")
        assert result["reasoning"] == "thinking"
        assert result["content"] == "answer"


# ===== 集成测试 =====


class TestIntegration:
    """集成测试"""

    def test_full_sse_workflow(self):
        """完整 SSE 工作流"""
        # 构建 SSE 流
        builder = StreamingResponseBuilder()
        builder.add_start({"model": "gpt-4"})
        builder.add_content_delta("Hello ")
        builder.add_content_delta("world!")
        builder.add_done()
        sse_text = builder.build()

        # 解析 SSE 流
        events = parse_sse_stream(sse_text)
        assert len(events) == 4

        # 处理分块
        processor = StreamChunkProcessor(provider="openai")
        aggregator = StreamAggregator()
        for event in events:
            chunk = processor.process_chunk(event.data)
            if chunk:
                aggregator.add_chunk(chunk)

        assert "Hello" in aggregator.get_full_content()
        assert "world" in aggregator.get_full_content()

    @pytest.mark.asyncio
    async def test_streaming_with_backpressure(self):
        """带背压的流处理"""
        controller = BackpressureController(max_buffer_size=10)

        # 生产者
        async def producer():
            for i in range(5):
                await controller.put(f"item_{i}")

        # 消费者
        consumed = []
        async def consumer():
            for _ in range(5):
                item = await controller.get()
                consumed.append(item)

        await asyncio.gather(producer(), consumer())
        assert len(consumed) == 5

    def test_reasoning_separation_workflow(self):
        """推理分离工作流"""
        processor = StreamChunkProcessor(provider="openai")
        separator = ReasoningContentSeparator()

        # 模拟流
        chunks_data = [
            {"choices": [{"delta": {"reasoning_content": "Let me think..."}}]},
            {"choices": [{"delta": {"reasoning_content": "about this"}}]},
            {"choices": [{"delta": {"content": "The answer is"}}]},
            {"choices": [{"delta": {"content": " 42"}}]},
            "[DONE]",
        ]

        for data in chunks_data:
            chunk = processor.process_chunk(
                data if data == "[DONE]" else json.dumps(data)
            )
            if chunk:
                separator.process(chunk)

        assert separator.get_full_reasoning() == "Let me think...about this"
        assert separator.get_full_content() == "The answer is 42"

    def test_build_and_parse_roundtrip(self):
        """构建与解析往返"""
        builder = StreamingResponseBuilder()
        builder.add_event("test", {"message": "hello"})
        builder.add_event("done", {})

        sse_text = builder.build()
        events = parse_sse_stream(sse_text)

        assert len(events) == 2
        assert json.loads(events[0].data) == {"message": "hello"}


# ===== 边界情况测试 =====


class TestEdgeCases:
    """边界情况测试"""

    def test_sse_parser_empty_feed(self):
        """空喂入"""
        parser = SSEStreamParser()
        assert parser.feed("") == []

    def test_sse_parser_only_whitespace(self):
        """仅空白"""
        parser = SSEStreamParser()
        assert parser.feed("   \n\n") == []

    def test_chunk_processor_none_data(self):
        """None 数据"""
        processor = StreamChunkProcessor()
        assert processor.process_chunk(None) is None

    def test_aggregator_empty(self):
        """空聚合器"""
        aggregator = StreamAggregator()
        assert aggregator.get_full_content() == ""
        assert aggregator.get_full_reasoning() == ""
        assert aggregator.is_complete is False

    def test_backpressure_zero_buffer(self):
        """零缓冲区"""
        controller = BackpressureController(max_buffer_size=0)
        assert controller.put_nowait("item") is False

    @pytest.mark.asyncio
    async def test_stream_to_list_empty(self):
        """空流转列表"""
        async def empty_stream():
            return
            yield  # 使其成为异步生成器

        result = await stream_to_list(empty_stream())
        assert result == []

    def test_builder_empty_build(self):
        """空构建器"""
        builder = StreamingResponseBuilder()
        assert builder.build() == ""

    def test_separator_no_chunks(self):
        """无分块分离器"""
        separator = ReasoningContentSeparator()
        assert separator.get_full_reasoning() == ""
        assert separator.get_full_content() == ""
