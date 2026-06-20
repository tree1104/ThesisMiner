"""Agent 上下文管理

管理 Agent 的上下文窗口、消息历史、token 计数与上下文压缩。

核心组件：
    - Message: 消息数据结构
    - TokenCounter: Token 计数器（多种估算策略）
    - ContextWindow: 上下文窗口管理器
    - MessageHistory: 消息历史管理
    - ContextCompressor: 上下文压缩器
    - ContextManager: 上下文管理器（整合以上组件）

设计原则：
    1. 模型无关：支持多种模型的 token 计数策略
    2. 可压缩：超长上下文自动压缩（摘要 + 保留近期）
    3. 可观测：提供 token 用量、上下文利用率等统计
    4. 线程安全：所有操作使用锁保护
"""
import hashlib
import json
import re
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


# ===== 消息角色枚举 =====


class MessageRole(str, Enum):
    """消息角色"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    FUNCTION = "function"


@dataclass
class Message:
    """消息

    封装一条对话消息。
    """
    role: str = "user"
    content: str = ""
    name: str = ""
    tool_call_id: str = ""
    tool_calls: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    token_count: int = 0

    def to_dict(self) -> dict:
        """转换为字典（用于 API 调用）。"""
        result = {"role": self.role, "content": self.content}
        if self.name:
            result["name"] = self.name
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            result["tool_calls"] = self.tool_calls
        return result

    def to_openai_dict(self) -> dict:
        """转换为 OpenAI API 格式字典。"""
        return self.to_dict()

    def to_anthropic_dict(self) -> dict:
        """转换为 Anthropic API 格式字典。"""
        # Anthropic 使用 user/assistant 角色
        role = self.role if self.role in ("user", "assistant") else "user"
        return {"role": role, "content": self.content}

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        """从字典创建消息。"""
        return cls(
            role=data.get("role", "user"),
            content=data.get("content", ""),
            name=data.get("name", ""),
            tool_call_id=data.get("tool_call_id", ""),
            tool_calls=data.get("tool_calls", []),
            metadata=data.get("metadata", {}),
        )

    def estimate_tokens(self, chars_per_token: float = 2.5) -> int:
        """估算 token 数（简单字符数除法）。"""
        if self.token_count > 0:
            return self.token_count
        # 中文约 1 字 = 1 token，英文约 4 字符 = 1 token
        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", self.content))
        english_chars = len(self.content) - chinese_chars
        return int(chinese_chars + english_chars / chars_per_token)


# ===== Token 计数器 =====


class TokenCounter:
    """Token 计数器

    提供多种 token 计数策略，从简单估算到精确计数。
    """

    # 各模型的 chars_per_token 估算值
    MODEL_CHARS_PER_TOKEN = {
        "gpt-4": 4.0,
        "gpt-4.1": 4.0,
        "gpt-4.1-mini": 4.0,
        "gpt-3.5-turbo": 4.0,
        "deepseek-v3.2": 3.0,
        "deepseek-r2": 3.0,
        "claude-sonnet-4.5": 3.5,
        "claude-opus-4.5": 3.5,
        "qwen3-max": 2.5,
        "gemini-2.5-pro": 3.5,
        "glm-4.6": 2.5,
        "doubao-1.5-pro": 2.5,
    }

    # 默认 chars_per_token
    DEFAULT_CHARS_PER_TOKEN = 3.0

    # 中文每字 token 数
    CHINESE_TOKENS_PER_CHAR = 1.0

    def __init__(self, model: str = ""):
        self.model = model.lower()
        self.chars_per_token = self.MODEL_CHARS_PER_TOKEN.get(
            self.model, self.DEFAULT_CHARS_PER_TOKEN
        )

    def count(self, text: str) -> int:
        """计算文本的 token 数。

        采用混合估算策略：
            - 中文字符按 1 字 = 1 token
            - 英文字符按 chars_per_token 估算
            - 标点与空白按 0.5 token 估算

        Args:
            text: 文本字符串。

        Returns:
            估算的 token 数。
        """
        if not text:
            return 0

        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
        # 英文字母数字
        english_alnum = len(re.findall(r"[a-zA-Z0-9]", text))
        # 标点与特殊字符
        punctuation = len(re.findall(r"[^\w\s\u4e00-\u9fff]", text))
        # 空白字符
        whitespace = len(re.findall(r"\s", text))

        tokens = (
            chinese_chars * self.CHINESE_TOKENS_PER_CHAR
            + english_alnum / self.chars_per_token
            + punctuation * 0.5
            + whitespace * 0.25
        )
        return int(tokens) + 1  # 向上取整

    def count_message(self, message: Message) -> int:
        """计算单条消息的 token 数（含角色开销）。"""
        content_tokens = self.count(message.content)
        # 角色与格式开销约 4 token
        role_overhead = 4
        # tool_calls 开销
        tool_overhead = 0
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_overhead += self.count(json.dumps(tc, ensure_ascii=False))
        return content_tokens + role_overhead + tool_overhead

    def count_messages(self, messages: list) -> int:
        """计算消息列表的总 token 数。"""
        total = 0
        for msg in messages:
            if isinstance(msg, Message):
                total += self.count_message(msg)
            elif isinstance(msg, dict):
                total += self.count_message(Message.from_dict(msg))
        # 对话开销约 3 token
        return total + 3

    def count_with_response(self, messages: list, response: str = "") -> dict:
        """计算请求与响应的 token 数。

        Returns:
            {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}
        """
        prompt_tokens = self.count_messages(messages)
        completion_tokens = self.count(response)
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }

    def max_context_for_model(self) -> int:
        """获取模型的最大上下文长度。"""
        context_limits = {
            "gpt-4": 8192,
            "gpt-4.1": 1000000,
            "gpt-4.1-mini": 1000000,
            "gpt-3.5-turbo": 16385,
            "deepseek-v3.2": 128000,
            "deepseek-r2": 128000,
            "claude-sonnet-4.5": 200000,
            "claude-opus-4.5": 200000,
            "qwen3-max": 131072,
            "gemini-2.5-pro": 2000000,
            "glm-4.6": 131072,
            "doubao-1.5-pro": 131072,
        }
        return context_limits.get(self.model, 128000)


# ===== 上下文窗口管理器 =====


class ContextWindow:
    """上下文窗口管理器

    管理单个 Agent 的上下文窗口，确保不超过模型的最大上下文长度。
    提供窗口利用率监控与自动裁剪。
    """

    def __init__(
        self,
        max_tokens: int = 128000,
        reserved_for_response: int = 4096,
        model: str = "",
    ):
        """初始化上下文窗口。

        Args:
            max_tokens: 最大上下文 token 数。
            reserved_for_response: 为响应预留的 token 数。
            model: 模型名称（用于 token 计数）。
        """
        self.max_tokens = max_tokens
        self.reserved_for_response = reserved_for_response
        self.token_counter = TokenCounter(model=model)
        self._messages: list[Message] = []
        self._lock = threading.RLock()
        self._total_tokens = 0

    @property
    def available_tokens(self) -> int:
        """可用 token 数（扣除预留）。"""
        return self.max_tokens - self.reserved_for_response - self._total_tokens

    @property
    def utilization(self) -> float:
        """上下文利用率（0.0 - 1.0）。"""
        usable = self.max_tokens - self.reserved_for_response
        if usable <= 0:
            return 1.0
        return min(1.0, self._total_tokens / usable)

    def add_message(self, message: Message) -> bool:
        """添加消息到上下文。

        Args:
            message: 消息对象。

        Returns:
            添加成功返回 True，超出窗口返回 False。
        """
        with self._lock:
            tokens = self.token_counter.count_message(message)
            if tokens > self.available_tokens:
                return False
            message.token_count = tokens
            self._messages.append(message)
            self._total_tokens += tokens
            return True

    def add_messages(self, messages: list) -> int:
        """批量添加消息。

        Returns:
            成功添加的消息数。
        """
        count = 0
        for msg in messages:
            if self.add_message(msg):
                count += 1
            else:
                break
        return count

    def get_messages(self, include_system: bool = True) -> list:
        """获取消息列表。"""
        with self._lock:
            if include_system:
                return list(self._messages)
            return [m for m in self._messages if m.role != "system"]

    def get_messages_dict(self, include_system: bool = True) -> list:
        """获取消息字典列表（用于 API 调用）。"""
        return [m.to_dict() for m in self.get_messages(include_system)]

    def get_system_message(self) -> Optional[Message]:
        """获取系统消息。"""
        with self._lock:
            for msg in self._messages:
                if msg.role == "system":
                    return msg
        return None

    def set_system_message(self, content: str) -> None:
        """设置系统消息。"""
        with self._lock:
            # 移除现有系统消息
            self._messages = [m for m in self._messages if m.role != "system"]
            # 插入新系统消息到开头
            system_msg = Message(role="system", content=content)
            system_msg.token_count = self.token_counter.count_message(system_msg)
            self._messages.insert(0, system_msg)
            self._recalculate_tokens()

    def remove_oldest(self, count: int = 1, keep_system: bool = True) -> list:
        """移除最旧的消息。

        Args:
            count: 移除数量。
            keep_system: 是否保留系统消息。

        Returns:
            被移除的消息列表。
        """
        with self._lock:
            removed = []
            for _ in range(count):
                if not self._messages:
                    break
                # 找到第一条非系统消息（若需保留系统消息）
                idx = 0
                if keep_system:
                    while idx < len(self._messages) and self._messages[idx].role == "system":
                        idx += 1
                if idx >= len(self._messages):
                    break
                msg = self._messages.pop(idx)
                self._total_tokens -= msg.token_count
                removed.append(msg)
            return removed

    def trim_to_fit(self, target_tokens: int, keep_system: bool = True, keep_recent: int = 2) -> list:
        """裁剪上下文以适应目标 token 数。

        Args:
            target_tokens: 目标 token 数。
            keep_system: 是否保留系统消息。
            keep_recent: 保留最近的消息数。

        Returns:
            被移除的消息列表。
        """
        with self._lock:
            removed = []
            while self._total_tokens > target_tokens and len(self._messages) > keep_recent + (1 if keep_system else 0):
                msgs = self.remove_oldest(1, keep_system=keep_system)
                if not msgs:
                    break
                removed.extend(msgs)
            return removed

    def clear(self, keep_system: bool = True) -> None:
        """清空上下文。"""
        with self._lock:
            if keep_system:
                system = self.get_system_message()
                self._messages = [system] if system else []
            else:
                self._messages = []
            self._recalculate_tokens()

    def _recalculate_tokens(self) -> None:
        """重新计算总 token 数。"""
        self._total_tokens = sum(m.token_count for m in self._messages)

    def get_stats(self) -> dict:
        """获取上下文统计。"""
        with self._lock:
            role_counts = {}
            for msg in self._messages:
                role_counts[msg.role] = role_counts.get(msg.role, 0) + 1
            return {
                "total_messages": len(self._messages),
                "total_tokens": self._total_tokens,
                "max_tokens": self.max_tokens,
                "available_tokens": self.available_tokens,
                "utilization": self.utilization,
                "reserved_for_response": self.reserved_for_response,
                "by_role": role_counts,
            }

    def __len__(self) -> int:
        return len(self._messages)


# ===== 消息历史管理 =====


class MessageHistory:
    """消息历史管理

    管理对话的完整消息历史，支持分页查询、搜索与导出。
    """

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._messages: deque = deque(maxlen=max_size)
        self._lock = threading.RLock()

    def add(self, message: Message) -> None:
        """添加消息。"""
        with self._lock:
            self._messages.append(message)

    def add_many(self, messages: list) -> None:
        """批量添加消息。"""
        with self._lock:
            for msg in messages:
                self._messages.append(msg)

    def get_all(self) -> list:
        """获取所有消息。"""
        with self._lock:
            return list(self._messages)

    def get_recent(self, count: int) -> list:
        """获取最近的消息。"""
        with self._lock:
            messages = list(self._messages)
            return messages[-count:] if count < len(messages) else messages

    def get_by_role(self, role: str) -> list:
        """按角色获取消息。"""
        with self._lock:
            return [m for m in self._messages if m.role == role]

    def search(self, keyword: str, case_sensitive: bool = False) -> list:
        """搜索消息内容。"""
        with self._lock:
            if not case_sensitive:
                keyword = keyword.lower()
            results = []
            for msg in self._messages:
                content = msg.content if case_sensitive else msg.content.lower()
                if keyword in content:
                    results.append(msg)
            return results

    def get_range(self, start: int, end: int) -> list:
        """获取指定范围的消息。"""
        with self._lock:
            messages = list(self._messages)
            return messages[start:end]

    def count(self) -> int:
        """消息总数。"""
        with self._lock:
            return len(self._messages)

    def clear(self) -> None:
        """清空历史。"""
        with self._lock:
            self._messages.clear()

    def export(self, format: str = "json") -> str:
        """导出历史。"""
        with self._lock:
            messages = list(self._messages)
            if format == "json":
                return json.dumps(
                    [m.to_dict() for m in messages],
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            elif format == "text":
                lines = []
                for m in messages:
                    lines.append(f"[{m.role}] {m.content}")
                return "\n\n".join(lines)
            return ""

    def to_dict_list(self) -> list:
        """转为字典列表。"""
        with self._lock:
            return [m.to_dict() for m in self._messages]


# ===== 上下文压缩器 =====


class ContextCompressor:
    """上下文压缩器

    当上下文超过阈值时，将早期消息压缩为摘要，保留近期消息原文。
    支持多种压缩策略。
    """

    def __init__(
        self,
        compression_threshold: int = 10,
        keep_recent: int = 4,
        strategy: str = "summary",
    ):
        """初始化压缩器。

        Args:
            compression_threshold: 触发压缩的消息数阈值。
            keep_recent: 压缩时保留的近期消息数。
            strategy: 压缩策略（summary / truncate / keyword）。
        """
        self.compression_threshold = compression_threshold
        self.keep_recent = keep_recent
        self.strategy = strategy

    def should_compress(self, message_count: int) -> bool:
        """判断是否需要压缩。"""
        return message_count > self.compression_threshold

    def compress(self, messages: list) -> tuple:
        """压缩消息列表。

        Args:
            messages: 消息列表。

        Returns:
            (压缩后的消息列表, 被压缩的消息列表)
        """
        if len(messages) <= self.compression_threshold:
            return messages, []

        # 保留系统消息与近期消息
        system_messages = [m for m in messages if m.role == "system"]
        non_system = [m for m in messages if m.role != "system"]

        if len(non_system) <= self.keep_recent:
            return messages, []

        to_compress = non_system[: -self.keep_recent]
        to_keep = non_system[-self.keep_recent :]

        # 根据策略压缩
        if self.strategy == "summary":
            summary = self._summarize(to_compress)
            summary_msg = Message(
                role="system",
                content=f"[对话历史摘要]\n{summary}",
                metadata={"compressed": True, "original_count": len(to_compress)},
            )
            compressed = system_messages + [summary_msg] + to_keep
        elif self.strategy == "truncate":
            truncated = self._truncate(to_compress)
            compressed = system_messages + truncated + to_keep
        elif self.strategy == "keyword":
            keywords = self._extract_keywords(to_compress)
            keyword_msg = Message(
                role="system",
                content=f"[历史关键词] {', '.join(keywords)}",
                metadata={"compressed": True, "strategy": "keyword"},
            )
            compressed = system_messages + [keyword_msg] + to_keep
        else:
            compressed = messages

        return compressed, to_compress

    def _summarize(self, messages: list) -> str:
        """生成摘要（简单实现，提取关键信息）。"""
        summaries = []
        for msg in messages:
            # 提取每条消息的前 100 字符作为摘要
            content = msg.content[:100]
            if len(msg.content) > 100:
                content += "..."
            summaries.append(f"[{msg.role}] {content}")
        return "\n".join(summaries)

    def _truncate(self, messages: list) -> list:
        """截断消息内容。"""
        truncated = []
        for msg in messages:
            if len(msg.content) > 200:
                new_msg = Message(
                    role=msg.role,
                    content=msg.content[:200] + "...[已截断]",
                    metadata={**msg.metadata, "truncated": True},
                )
                truncated.append(new_msg)
            else:
                truncated.append(msg)
        return truncated

    def _extract_keywords(self, messages: list) -> list:
        """提取关键词。"""
        # 简单实现：提取所有消息中的高频词
        word_count: dict[str, int] = {}
        for msg in messages:
            # 简单分词（按空格与标点）
            words = re.findall(r"[\w\u4e00-\u9fff]+", msg.content)
            for word in words:
                if len(word) >= 2:
                    word_count[word] = word_count.get(word, 0) + 1
        # 取前 20 个高频词
        sorted_words = sorted(word_count.items(), key=lambda x: x[1], reverse=True)
        return [word for word, _ in sorted_words[:20]]


# ===== 上下文管理器 =====


class ContextManager:
    """上下文管理器

    整合上下文窗口、消息历史、token 计数与压缩能力。
    每个 Agent 实例持有一个 ContextManager。
    """

    def __init__(
        self,
        agent_id: str,
        model: str = "",
        max_tokens: int = 128000,
        reserved_for_response: int = 4096,
        auto_compress: bool = True,
        compression_threshold: int = 10,
        keep_recent: int = 4,
    ):
        """初始化上下文管理器。

        Args:
            agent_id: Agent 标识。
            model: 模型名称。
            max_tokens: 最大上下文 token 数。
            reserved_for_response: 为响应预留的 token 数。
            auto_compress: 是否自动压缩。
            compression_threshold: 压缩阈值。
            keep_recent: 压缩时保留的近期消息数。
        """
        self.agent_id = agent_id
        self.model = model
        self.window = ContextWindow(
            max_tokens=max_tokens,
            reserved_for_response=reserved_for_response,
            model=model,
        )
        self.history = MessageHistory()
        self.compressor = ContextCompressor(
            compression_threshold=compression_threshold,
            keep_recent=keep_recent,
        )
        self.auto_compress = auto_compress
        self._lock = threading.RLock()
        self._compress_count = 0

    def add_message(self, message: Message) -> bool:
        """添加消息到上下文。"""
        with self._lock:
            # 添加到历史
            self.history.add(message)

            # 添加到窗口
            if not self.window.add_message(message):
                # 窗口已满，尝试压缩
                if self.auto_compress:
                    self._compress_context()
                    return self.window.add_message(message)
                return False
            return True

    def add_user_message(self, content: str) -> bool:
        """添加用户消息。"""
        return self.add_message(Message(role="user", content=content))

    def add_assistant_message(self, content: str, reasoning: str = "") -> bool:
        """添加助手消息。"""
        full_content = content
        if reasoning:
            full_content = f"[推理] {reasoning}\n\n[回复] {content}"
        return self.add_message(Message(role="assistant", content=full_content))

    def add_system_message(self, content: str) -> None:
        """设置系统消息。"""
        with self._lock:
            self.window.set_system_message(content)

    def get_messages(self) -> list:
        """获取当前上下文消息。"""
        return self.window.get_messages()

    def get_messages_dict(self) -> list:
        """获取消息字典列表。"""
        return self.window.get_messages_dict()

    def _compress_context(self) -> None:
        """压缩上下文。"""
        with self._lock:
            messages = self.window.get_messages()
            compressed, removed = self.compressor.compress(messages)
            if removed:
                # 重建窗口
                self.window.clear(keep_system=False)
                for msg in compressed:
                    self.window.add_message(msg)
                self._compress_count += 1

    def reset(self, keep_system: bool = True) -> None:
        """重置上下文。"""
        with self._lock:
            self.window.clear(keep_system=keep_system)
            self.history.clear()

    def get_stats(self) -> dict:
        """获取统计信息。"""
        with self._lock:
            window_stats = self.window.get_stats()
            return {
                "agent_id": self.agent_id,
                "model": self.model,
                "window": window_stats,
                "history_count": self.history.count(),
                "compress_count": self._compress_count,
                "auto_compress": self.auto_compress,
            }

    def export_history(self, format: str = "json") -> str:
        """导出历史记录。"""
        return self.history.export(format=format)

    def search_history(self, keyword: str) -> list:
        """搜索历史记录。"""
        return self.history.search(keyword)

    def get_context_hash(self) -> str:
        """获取当前上下文的哈希（用于缓存键）。"""
        messages = self.get_messages_dict()
        serialized = json.dumps(messages, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:32]

    def restore_from_db(
        self, conversation_id: str = None, session_id: str = None
    ) -> list:
        """从 SQLite 数据库恢复 Agent 历史到上下文。

        加载 agent_messages 表中属于本上下文 agent_id 的消息，重建窗口
        与历史。系统提示保持不变。

        Args:
            conversation_id: 对话 ID 过滤（可选）。
            session_id: 会话 ID 过滤（可选）。

        Returns:
            恢复后的消息字典列表（不含系统提示）。
        """
        # 延迟导入以避免循环依赖
        from backend import database

        with self._lock:
            rows = database.load_agent_history(
                agent_id=self.agent_id,
                conversation_id=conversation_id,
                session_id=session_id,
            )

            # 保留系统提示，清空其余消息
            self.window.clear(keep_system=False)
            self.history.clear()

            restored: list[dict] = []
            for row in rows:
                role = row.get("role", "user")
                if role == "system":
                    continue
                content = row.get("content", "")
                msg = Message(role=role, content=content)
                # 写入窗口与历史
                self.window.add_message(msg)
                self.history.add(msg)
                restored.append(msg.to_dict())
            return restored

    def clear_cache(self) -> None:
        """清空内存上下文（强制下次从数据库重新加载）。

        仅清空窗口与历史缓存，不影响数据库中的持久化记录。
        """
        with self._lock:
            self.window.clear(keep_system=False)
            self.history.clear()
            self._compress_count = 0


# ===== 全局上下文注册表 =====


class ContextRegistry:
    """上下文注册表

    管理多个 Agent 的上下文管理器，支持按 agent_id 检索。
    """

    def __init__(self):
        self._contexts: dict[str, ContextManager] = {}
        self._lock = threading.RLock()

    def create_context(self, agent_id: str, **kwargs) -> ContextManager:
        """创建上下文。"""
        with self._lock:
            if agent_id in self._contexts:
                return self._contexts[agent_id]
            ctx = ContextManager(agent_id=agent_id, **kwargs)
            self._contexts[agent_id] = ctx
            return ctx

    def get_context(self, agent_id: str) -> Optional[ContextManager]:
        """获取上下文。"""
        with self._lock:
            return self._contexts.get(agent_id)

    def remove_context(self, agent_id: str) -> bool:
        """移除上下文。"""
        with self._lock:
            if agent_id in self._contexts:
                del self._contexts[agent_id]
                return True
            return False

    def reset_context(self, agent_id: str) -> bool:
        """重置指定上下文。"""
        ctx = self.get_context(agent_id)
        if ctx:
            ctx.reset()
            return True
        return False

    def reset_all(self) -> None:
        """重置所有上下文。"""
        with self._lock:
            for ctx in self._contexts.values():
                ctx.reset()

    def list_contexts(self) -> list:
        """列出所有上下文。"""
        with self._lock:
            return list(self._contexts.keys())

    def get_all_stats(self) -> dict:
        """获取所有上下文统计。"""
        with self._lock:
            return {agent_id: ctx.get_stats() for agent_id, ctx in self._contexts.items()}


# 全局注册表实例
_global_registry = ContextRegistry()


def get_context_registry() -> ContextRegistry:
    """获取全局上下文注册表。"""
    return _global_registry


def get_context(agent_id: str) -> Optional[ContextManager]:
    """获取指定 Agent 的上下文。"""
    return _global_registry.get_context(agent_id)


def create_context(agent_id: str, **kwargs) -> ContextManager:
    """创建上下文。"""
    return _global_registry.create_context(agent_id, **kwargs)


def reset_all_contexts() -> None:
    """重置所有上下文。"""
    _global_registry.reset_all()
