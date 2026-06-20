"""流式响应处理

提供 SSE（Server-Sent Events）流式响应处理能力，包括分块处理、
推理与内容分离、背压控制等。

核心组件：
    - SSEEvent: SSE 事件数据结构
    - SSEStreamParser: SSE 流解析器
    - StreamChunkProcessor: 流分块处理器
    - ReasoningContentSeparator: 推理与内容分离器
    - BackpressureController: 背压控制器
    - StreamAggregator: 流聚合器
    - StreamingResponseBuilder: 流式响应构建器

支持的流式格式：
    - OpenAI 标准 SSE 格式（data: {...}\n\n）
    - DeepSeek 思维链格式（reasoning_content 字段）
    - Anthropic Claude 格式（content_block_delta）
    - 通用文本流（逐行或逐块）
"""
import asyncio
import json
import re
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator, AsyncIterator, Callable, Optional


# ===== 事件类型枚举 =====


class StreamEventType(str, Enum):
    """流式事件类型"""
    START = "start"
    DELTA = "delta"
    REASONING_DELTA = "reasoning_delta"
    CONTENT_DELTA = "content_delta"
    TOOL_CALL = "tool_call"
    CITATION = "citation"
    USAGE = "usage"
    DONE = "done"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    METADATA = "metadata"


@dataclass
class SSEEvent:
    """SSE 事件

    封装一个 Server-Sent Events 事件。
    """
    event: str = "message"
    data: str = ""
    id: str = ""
    retry: int = 0
    comment: str = ""

    def to_sse_string(self) -> str:
        """转换为 SSE 格式字符串。"""
        lines = []
        if self.comment:
            lines.append(f": {self.comment}")
        if self.id:
            lines.append(f"id: {self.id}")
        if self.event and self.event != "message":
            lines.append(f"event: {self.event}")
        if self.retry:
            lines.append(f"retry: {self.retry}")
        if self.data:
            # 多行数据每行加 data: 前缀
            for line in self.data.split("\n"):
                lines.append(f"data: {line}")
        else:
            lines.append("data: ")
        return "\n".join(lines) + "\n\n"

    @classmethod
    def from_data(cls, data: Any, event: str = "message") -> "SSEEvent":
        """从数据创建 SSE 事件（自动 JSON 序列化）。"""
        if isinstance(data, str):
            return cls(event=event, data=data)
        return cls(event=event, data=json.dumps(data, ensure_ascii=False, default=str))


@dataclass
class StreamChunk:
    """流式分块

    封装一个流式响应分块。
    """
    content: str = ""
    reasoning: str = ""
    event_type: str = StreamEventType.CONTENT_DELTA.value
    metadata: dict = field(default_factory=dict)
    is_final: bool = False
    timestamp: float = field(default_factory=time.time)
    index: int = 0


@dataclass
class StreamStats:
    """流式统计"""
    total_chunks: int = 0
    content_chunks: int = 0
    reasoning_chunks: int = 0
    total_content_chars: int = 0
    total_reasoning_chars: int = 0
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    errors: int = 0

    @property
    def duration(self) -> float:
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def chars_per_second(self) -> float:
        duration = self.duration
        if duration <= 0:
            return 0.0
        return (self.total_content_chars + self.total_reasoning_chars) / duration

    def to_dict(self) -> dict:
        return {
            "total_chunks": self.total_chunks,
            "content_chunks": self.content_chunks,
            "reasoning_chunks": self.reasoning_chunks,
            "total_content_chars": self.total_content_chars,
            "total_reasoning_chars": self.total_reasoning_chars,
            "duration": self.duration,
            "chars_per_second": self.chars_per_second,
            "errors": self.errors,
        }


# ===== SSE 流解析器 =====


class SSEStreamParser:
    """SSE 流解析器

    解析 SSE 格式的字节流或文本流，产出 SSEEvent 对象。
    支持不完整分块的缓冲与重组。
    """

    def __init__(self):
        self._buffer = ""
        self._current_event = SSEEvent()

    def feed(self, data: str) -> list:
        """喂入数据，返回完整的事件列表。

        Args:
            data: SSE 文本数据（可能不完整）。

        Returns:
            完整的 SSEEvent 列表。
        """
        self._buffer += data
        events = []

        while True:
            # 查找事件结束标记（双换行）
            end_idx = self._buffer.find("\n\n")
            if end_idx == -1:
                # 也尝试 \r\n\r\n
                end_idx = self._buffer.find("\r\n\r\n")
                if end_idx == -1:
                    break
                event_text = self._buffer[:end_idx]
                self._buffer = self._buffer[end_idx + 4 :]
            else:
                event_text = self._buffer[:end_idx]
                self._buffer = self._buffer[end_idx + 2 :]

            event = self._parse_event(event_text)
            if event:
                events.append(event)

        return events

    def feed_bytes(self, data: bytes, encoding: str = "utf-8") -> list:
        """喂入字节数据。"""
        return self.feed(data.decode(encoding, errors="replace"))

    def _parse_event(self, text: str) -> Optional[SSEEvent]:
        """解析单个 SSE 事件文本。"""
        if not text.strip():
            return None

        event = SSEEvent()
        data_lines = []

        for line in text.split("\n"):
            line = line.rstrip("\r")
            if not line:
                continue
            if line.startswith(":"):
                event.comment = line[1:].strip()
            elif line.startswith("event:"):
                event.event = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].lstrip(" "))
            elif line.startswith("id:"):
                event.id = line[3:].strip()
            elif line.startswith("retry:"):
                try:
                    event.retry = int(line[6:].strip())
                except ValueError:
                    pass

        event.data = "\n".join(data_lines)
        return event

    def reset(self) -> None:
        """重置解析器状态。"""
        self._buffer = ""
        self._current_event = SSEEvent()

    def get_remaining_buffer(self) -> str:
        """获取缓冲区剩余内容。"""
        return self._buffer


# ===== 流分块处理器 =====


class StreamChunkProcessor:
    """流分块处理器

    处理流式响应的分块，统一不同模型提供商的分块格式。
    """

    # OpenAI 格式字段
    OPENAI_CONTENT_FIELD = "content"
    OPENAI_REASONING_FIELD = "reasoning_content"

    # Anthropic 格式字段
    ANTHROPIC_CONTENT_FIELD = "text"
    ANTHROPIC_REASONING_FIELD = "thinking"

    def __init__(self, provider: str = "openai"):
        """初始化分块处理器。

        Args:
            provider: 模型提供商（openai / anthropic / deepseek / qwen / gemini）。
        """
        self.provider = provider.lower()
        self.stats = StreamStats()
        self._chunk_index = 0

    def process_chunk(self, raw_data: str) -> Optional[StreamChunk]:
        """处理原始分块数据。

        Args:
            raw_data: 原始分块数据（JSON 字符串）。

        Returns:
            StreamChunk 实例，解析失败返回 None。
        """
        if not raw_data or raw_data.strip() == "[DONE]":
            chunk = StreamChunk(
                event_type=StreamEventType.DONE.value,
                is_final=True,
                index=self._chunk_index,
            )
            self.stats.total_chunks += 1
            self.stats.end_time = time.time()
            return chunk

        try:
            data = json.loads(raw_data)
        except json.JSONDecodeError:
            self.stats.errors += 1
            return None

        return self._parse_provider_chunk(data)

    def _parse_provider_chunk(self, data: dict) -> Optional[StreamChunk]:
        """按提供商解析分块。"""
        if self.provider == "anthropic":
            return self._parse_anthropic_chunk(data)
        # OpenAI 兼容格式（deepseek / qwen / gemini 等均兼容）
        return self._parse_openai_chunk(data)

    def _parse_openai_chunk(self, data: dict) -> Optional[StreamChunk]:
        """解析 OpenAI 格式分块。"""
        choices = data.get("choices", [])
        if not choices:
            # 可能是 usage 事件
            if "usage" in data:
                chunk = StreamChunk(
                    event_type=StreamEventType.USAGE.value,
                    metadata={"usage": data["usage"]},
                    index=self._chunk_index,
                )
                self.stats.total_chunks += 1
                self._chunk_index += 1
                return chunk
            return None

        choice = choices[0]
        delta = choice.get("delta", {})

        content = delta.get(self.OPENAI_CONTENT_FIELD, "") or ""
        reasoning = delta.get(self.OPENAI_REASONING_FIELD, "") or ""

        # 判断事件类型
        if reasoning and not content:
            event_type = StreamEventType.REASONING_DELTA.value
            self.stats.reasoning_chunks += 1
            self.stats.total_reasoning_chars += len(reasoning)
        elif content:
            event_type = StreamEventType.CONTENT_DELTA.value
            self.stats.content_chunks += 1
            self.stats.total_content_chars += len(content)
        else:
            # 可能有 tool_calls 或 finish_reason
            if delta.get("tool_calls"):
                event_type = StreamEventType.TOOL_CALL.value
            elif choice.get("finish_reason"):
                event_type = StreamEventType.DONE.value
            else:
                event_type = StreamEventType.METADATA.value

        chunk = StreamChunk(
            content=content,
            reasoning=reasoning,
            event_type=event_type,
            metadata={
                "finish_reason": choice.get("finish_reason"),
                "index": choice.get("index", 0),
                "model": data.get("model", ""),
            },
            index=self._chunk_index,
        )
        self.stats.total_chunks += 1
        self._chunk_index += 1
        return chunk

    def _parse_anthropic_chunk(self, data: dict) -> Optional[StreamChunk]:
        """解析 Anthropic 格式分块。"""
        event_type = data.get("type", "")

        if event_type == "message_start":
            chunk = StreamChunk(
                event_type=StreamEventType.START.value,
                metadata={"message": data.get("message", {})},
                index=self._chunk_index,
            )
            self.stats.total_chunks += 1
            self._chunk_index += 1
            return chunk

        if event_type == "content_block_delta":
            delta = data.get("delta", {})
            delta_type = delta.get("type", "")

            if delta_type == "text_delta":
                text = delta.get("text", "")
                chunk = StreamChunk(
                    content=text,
                    event_type=StreamEventType.CONTENT_DELTA.value,
                    index=self._chunk_index,
                )
                self.stats.content_chunks += 1
                self.stats.total_content_chars += len(text)
            elif delta_type == "thinking_delta":
                thinking = delta.get("thinking", "")
                chunk = StreamChunk(
                    reasoning=thinking,
                    event_type=StreamEventType.REASONING_DELTA.value,
                    index=self._chunk_index,
                )
                self.stats.reasoning_chunks += 1
                self.stats.total_reasoning_chars += len(thinking)
            else:
                chunk = StreamChunk(
                    event_type=StreamEventType.METADATA.value,
                    metadata={"delta_type": delta_type},
                    index=self._chunk_index,
                )
            self.stats.total_chunks += 1
            self._chunk_index += 1
            return chunk

        if event_type == "message_delta":
            chunk = StreamChunk(
                event_type=StreamEventType.METADATA.value,
                metadata=data.get("delta", {}),
                index=self._chunk_index,
            )
            self.stats.total_chunks += 1
            self._chunk_index += 1
            return chunk

        if event_type == "message_stop":
            chunk = StreamChunk(
                event_type=StreamEventType.DONE.value,
                is_final=True,
                index=self._chunk_index,
            )
            self.stats.total_chunks += 1
            self.stats.end_time = time.time()
            self._chunk_index += 1
            return chunk

        return None

    def reset(self) -> None:
        """重置处理器状态。"""
        self.stats = StreamStats()
        self._chunk_index = 0


# ===== 推理与内容分离器 =====


class ReasoningContentSeparator:
    """推理与内容分离器

    将流式响应中的推理内容（思维链）与正式内容分离。
    支持 DeepSeek R 系列与 Claude thinking 模式。
    """

    def __init__(self):
        self.reasoning_buffer = ""
        self.content_buffer = ""
        self.in_reasoning = False
        self.reasoning_complete = False

    def process(self, chunk: StreamChunk) -> dict:
        """处理分块，返回分离后的内容。

        Args:
            chunk: 流式分块。

        Returns:
            {"reasoning": str, "content": str, "type": str}
        """
        result = {"reasoning": "", "content": "", "type": chunk.event_type}

        if chunk.event_type == StreamEventType.REASONING_DELTA.value:
            self.in_reasoning = True
            self.reasoning_buffer += chunk.reasoning
            result["reasoning"] = chunk.reasoning

        elif chunk.event_type == StreamEventType.CONTENT_DELTA.value:
            if self.in_reasoning:
                self.in_reasoning = False
                self.reasoning_complete = True
            self.content_buffer += chunk.content
            result["content"] = chunk.content

        elif chunk.event_type == StreamEventType.DONE.value:
            result["type"] = "done"

        return result

    def get_full_reasoning(self) -> str:
        """获取完整推理内容。"""
        return self.reasoning_buffer

    def get_full_content(self) -> str:
        """获取完整正式内容。"""
        return self.content_buffer

    def reset(self) -> None:
        """重置分离器。"""
        self.reasoning_buffer = ""
        self.content_buffer = ""
        self.in_reasoning = False
        self.reasoning_complete = False


# ===== 背压控制器 =====


class BackpressureController:
    """背压控制器

    控制流式响应的生产-消费速率，防止消费者处理不过来导致内存溢出。
    使用有界缓冲区，满了则阻塞生产者。
    """

    def __init__(self, max_buffer_size: int = 100, high_watermark: int = 80, low_watermark: int = 20):
        """初始化背压控制器。

        Args:
            max_buffer_size: 最大缓冲区大小。
            high_watermark: 高水位（超过则暂停生产）。
            low_watermark: 低水位（低于则恢复生产）。
        """
        self.max_buffer_size = max_buffer_size
        self.high_watermark = min(high_watermark, max_buffer_size)
        self.low_watermark = min(low_watermark, high_watermark)
        self._buffer: deque = deque()
        self._lock = asyncio.Lock()
        self._not_full = asyncio.Event()
        self._not_empty = asyncio.Event()
        self._not_full.set()
        self._closed = False
        self._stats = {
            "produced": 0,
            "consumed": 0,
            "paused": 0,
            "dropped": 0,
        }

    async def put(self, item: Any) -> bool:
        """放入元素（异步，缓冲区满则等待）。

        Returns:
            成功放入返回 True，控制器已关闭返回 False。
        """
        if self._closed:
            return False

        while len(self._buffer) >= self.max_buffer_size:
            self._stats["paused"] += 1
            self._not_full.clear()
            await self._not_full.wait()
            if self._closed:
                return False

        self._buffer.append(item)
        self._stats["produced"] += 1
        self._not_empty.set()
        return True

    async def get(self) -> Any:
        """获取元素（异步，缓冲区空则等待）。

        Returns:
            元素，控制器已关闭且缓冲区空返回 None。
        """
        while not self._buffer:
            if self._closed:
                return None
            self._not_empty.clear()
            await self._not_empty.wait()

        item = self._buffer.popleft()
        self._stats["consumed"] += 1
        if len(self._buffer) < self.low_watermark:
            self._not_full.set()
        return item

    def put_nowait(self, item: Any) -> bool:
        """非阻塞放入。"""
        if self._closed or len(self._buffer) >= self.max_buffer_size:
            self._stats["dropped"] += 1
            return False
        self._buffer.append(item)
        self._stats["produced"] += 1
        self._not_empty.set()
        return True

    def get_nowait(self) -> Any:
        """非阻塞获取。"""
        if not self._buffer:
            return None
        item = self._buffer.popleft()
        self._stats["consumed"] += 1
        if len(self._buffer) < self.low_watermark:
            self._not_full.set()
        return item

    def should_pause(self) -> bool:
        """是否应暂停生产。"""
        return len(self._buffer) >= self.high_watermark

    def should_resume(self) -> bool:
        """是否应恢复生产。"""
        return len(self._buffer) <= self.low_watermark

    def buffer_size(self) -> int:
        """当前缓冲区大小。"""
        return len(self._buffer)

    def close(self) -> None:
        """关闭控制器。"""
        self._closed = True
        self._not_full.set()
        self._not_empty.set()

    def get_stats(self) -> dict:
        """获取统计。"""
        return {
            **self._stats,
            "buffer_size": len(self._buffer),
            "max_buffer_size": self.max_buffer_size,
        }


# ===== 流聚合器 =====


class StreamAggregator:
    """流聚合器

    将流式分块聚合为完整响应。
    """

    def __init__(self):
        self.content_parts: list = []
        self.reasoning_parts: list = []
        self.metadata: dict = {}
        self.citations: list = []
        self.tool_calls: list = []
        self.usage: dict = {}
        self.is_complete = False
        self.error: Optional[str] = None

    def add_chunk(self, chunk: StreamChunk) -> None:
        """添加分块。"""
        if chunk.content:
            self.content_parts.append(chunk.content)
        if chunk.reasoning:
            self.reasoning_parts.append(chunk.reasoning)
        if chunk.event_type == StreamEventType.USAGE.value:
            self.usage.update(chunk.metadata.get("usage", {}))
        if chunk.event_type == StreamEventType.TOOL_CALL.value:
            self.tool_calls.append(chunk.metadata)
        if chunk.event_type == StreamEventType.CITATION.value:
            self.citations.append(chunk.metadata)
        if chunk.event_type == StreamEventType.ERROR.value:
            self.error = chunk.content or chunk.metadata.get("error", "")
        if chunk.is_final:
            self.is_complete = True
        # 合并元数据
        self.metadata.update(chunk.metadata)

    def get_full_content(self) -> str:
        """获取完整内容。"""
        return "".join(self.content_parts)

    def get_full_reasoning(self) -> str:
        """获取完整推理内容。"""
        return "".join(self.reasoning_parts)

    def get_result(self) -> dict:
        """获取聚合结果。"""
        return {
            "content": self.get_full_content(),
            "reasoning": self.get_full_reasoning(),
            "metadata": self.metadata,
            "citations": self.citations,
            "tool_calls": self.tool_calls,
            "usage": self.usage,
            "is_complete": self.is_complete,
            "error": self.error,
        }

    def reset(self) -> None:
        """重置聚合器。"""
        self.content_parts.clear()
        self.reasoning_parts.clear()
        self.metadata.clear()
        self.citations.clear()
        self.tool_calls.clear()
        self.usage.clear()
        self.is_complete = False
        self.error = None


# ===== 流式响应构建器 =====


class StreamingResponseBuilder:
    """流式响应构建器

    构建符合 SSE 格式的流式响应字符串。
    """

    def __init__(self):
        self.events: list = []

    def add_event(self, event: str, data: Any) -> None:
        """添加事件。"""
        sse_event = SSEEvent.from_data(data, event=event)
        self.events.append(sse_event)

    def add_data(self, data: Any) -> None:
        """添加数据事件。"""
        self.add_event("message", data)

    def add_start(self, metadata: Optional[dict] = None) -> None:
        """添加开始事件。"""
        self.add_event("start", metadata or {})

    def add_delta(self, content: str = "", reasoning: str = "") -> None:
        """添加增量事件。"""
        data = {"content": content, "reasoning": reasoning}
        self.add_event("delta", data)

    def add_content_delta(self, content: str) -> None:
        """添加内容增量事件。"""
        self.add_event("content_delta", {"content": content})

    def add_reasoning_delta(self, reasoning: str) -> None:
        """添加推理增量事件。"""
        self.add_event("reasoning_delta", {"reasoning": reasoning})

    def add_usage(self, usage: dict) -> None:
        """添加用量事件。"""
        self.add_event("usage", usage)

    def add_error(self, error: str, code: str = "") -> None:
        """添加错误事件。"""
        self.add_event("error", {"error": error, "code": code})

    def add_done(self, metadata: Optional[dict] = None) -> None:
        """添加完成事件。"""
        self.add_event("done", metadata or {})

    def add_heartbeat(self) -> None:
        """添加心跳事件。"""
        self.events.append(SSEEvent(comment="heartbeat"))

    def build(self) -> str:
        """构建完整的 SSE 响应字符串。"""
        return "".join(event.to_sse_string() for event in self.events)

    def build_chunks(self) -> list:
        """构建分块列表（每个事件一个字符串）。"""
        return [event.to_sse_string() for event in self.events]

    def clear(self) -> None:
        """清空事件。"""
        self.events.clear()


# ===== 异步流工具 =====


async def stream_to_list(stream: AsyncIterator) -> list:
    """将异步流收集为列表。"""
    results = []
    async for item in stream:
        results.append(item)
    return results


async def merge_streams(*streams: AsyncIterator) -> AsyncGenerator:
    """合并多个异步流（按到达顺序产出）。"""
    pending = set()
    for i, stream in enumerate(streams):
        task = asyncio.ensure_future(stream.__anext__())
        task.stream_index = i
        task.stream = stream
        pending.add(task)

    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            try:
                item = task.result()
                yield item
                # 继续从该流获取
                new_task = asyncio.ensure_future(task.stream.__anext__())
                new_task.stream_index = task.stream_index
                new_task.stream = task.stream
                pending.add(new_task)
            except StopAsyncIteration:
                # 该流已结束
                pass


async def transform_stream(
    stream: AsyncIterator,
    transformer: Callable,
) -> AsyncGenerator:
    """转换流（对每个元素应用转换函数）。"""
    async for item in stream:
        yield transformer(item)


async def filter_stream(
    stream: AsyncIterator,
    predicate: Callable,
) -> AsyncGenerator:
    """过滤流（仅保留满足条件的元素）。"""
    async for item in stream:
        if predicate(item):
            yield item


async def batch_stream(stream: AsyncIterator, batch_size: int) -> AsyncGenerator:
    """批量流（将元素分批产出）。"""
    batch = []
    async for item in stream:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


async def stream_with_timeout(
    stream: AsyncIterator,
    timeout: float,
) -> AsyncGenerator:
    """带超时的流（单个元素超时则停止）。"""
    while True:
        try:
            item = await asyncio.wait_for(stream.__anext__(), timeout=timeout)
            yield item
        except StopAsyncIteration:
            break
        except asyncio.TimeoutError:
            yield StreamChunk(
                event_type=StreamEventType.ERROR.value,
                content="流式响应超时",
                metadata={"error": "timeout", "timeout": timeout},
            )
            break


# ===== 便捷函数 =====


def create_sse_response(data: Any, event: str = "message") -> str:
    """创建单个 SSE 响应。"""
    return SSEEvent.from_data(data, event=event).to_sse_string()


def create_sse_stream(events: list) -> str:
    """创建 SSE 流（多个事件）。"""
    builder = StreamingResponseBuilder()
    for event_data in events:
        if isinstance(event_data, dict):
            event_type = event_data.get("event", "message")
            data = event_data.get("data", event_data)
            builder.add_event(event_type, data)
        else:
            builder.add_data(event_data)
    return builder.build()


def parse_sse_stream(text: str) -> list:
    """解析 SSE 流文本为事件列表。"""
    parser = SSEStreamParser()
    return parser.feed(text)


async def process_stream_response(
    stream: AsyncIterator,
    provider: str = "openai",
    on_content: Optional[Callable] = None,
    on_reasoning: Optional[Callable] = None,
    on_done: Optional[Callable] = None,
    on_error: Optional[Callable] = None,
) -> dict:
    """处理流式响应的便捷函数。

    Args:
        stream: 异步流（产出原始字符串）。
        provider: 模型提供商。
        on_content: 内容回调。
        on_reasoning: 推理回调。
        on_done: 完成回调。
        on_error: 错误回调。

    Returns:
        聚合结果字典。
    """
    processor = StreamChunkProcessor(provider=provider)
    separator = ReasoningContentSeparator()
    aggregator = StreamAggregator()

    async for raw_chunk in stream:
        chunk = processor.process_chunk(raw_chunk)
        if chunk is None:
            continue

        aggregator.add_chunk(chunk)
        separated = separator.process(chunk)

        if separated["content"] and on_content:
            if asyncio.iscoroutinefunction(on_content):
                await on_content(separated["content"])
            else:
                on_content(separated["content"])

        if separated["reasoning"] and on_reasoning:
            if asyncio.iscoroutinefunction(on_reasoning):
                await on_reasoning(separated["reasoning"])
            else:
                on_reasoning(separated["reasoning"])

        if chunk.event_type == StreamEventType.ERROR.value and on_error:
            if asyncio.iscoroutinefunction(on_error):
                await on_error(chunk.metadata.get("error", ""))
            else:
                on_error(chunk.metadata.get("error", ""))

        if chunk.is_final and on_done:
            result = aggregator.get_result()
            if asyncio.iscoroutinefunction(on_done):
                await on_done(result)
            else:
                on_done(result)

    result = aggregator.get_result()
    result["stats"] = processor.stats.to_dict()
    return result
