"""Agent 通信总线

提供 Agent 间消息传递、事件总线、发布订阅、消息路由能力。

核心组件：
    - Message: 通信消息数据结构
    - EventBus: 事件总线（发布订阅模式）
    - MessageBus: 消息总线（点对点通信）
    - MessageRouter: 消息路由器
    - AgentCommunicator: Agent 通信器（整合以上组件）
    - CommunicationStats: 通信统计

设计原则：
    1. 解耦：Agent 间通过消息通信，不直接调用
    2. 异步：所有通信支持异步模式
    3. 可靠：消息确认与重试机制
    4. 可观测：消息追踪与统计
"""
import asyncio
import json
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, Union


# ===== 消息类型枚举 =====


class MessageType(str, Enum):
    """消息类型"""
    REQUEST = "request"        # 请求消息
    RESPONSE = "response"      # 响应消息
    EVENT = "event"            # 事件消息
    NOTIFICATION = "notification"  # 通知消息
    COMMAND = "command"        # 命令消息
    QUERY = "query"            # 查询消息
    RESULT = "result"          # 结果消息
    ERROR = "error"            # 错误消息
    HEARTBEAT = "heartbeat"    # 心跳消息


class MessagePriority(int, Enum):
    """消息优先级"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


class MessageStatus(str, Enum):
    """消息状态"""
    PENDING = "pending"
    DELIVERED = "delivered"
    PROCESSED = "processed"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class AgentMessage:
    """Agent 通信消息

    封装 Agent 间通信的消息。
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = MessageType.EVENT.value
    source: str = ""           # 发送方 Agent ID
    target: str = ""           # 接收方 Agent ID（空表示广播）
    topic: str = ""            # 主题（用于发布订阅）
    content: Any = None        # 消息内容
    metadata: dict = field(default_factory=dict)
    priority: int = MessagePriority.NORMAL.value
    status: str = MessageStatus.PENDING.value
    timestamp: float = field(default_factory=time.time)
    expires_at: float = 0.0    # 0 表示永不过期
    correlation_id: str = ""   # 关联 ID（用于请求-响应配对）
    reply_to: str = ""         # 回复目标消息 ID
    retry_count: int = 0
    max_retries: int = 3

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "id": self.id,
            "type": self.type,
            "source": self.source,
            "target": self.target,
            "topic": self.topic,
            "content": self.content,
            "metadata": self.metadata,
            "priority": self.priority,
            "status": self.status,
            "timestamp": self.timestamp,
            "expires_at": self.expires_at,
            "correlation_id": self.correlation_id,
            "reply_to": self.reply_to,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
        }

    def to_json(self) -> str:
        """转换为 JSON 字符串。"""
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)

    @classmethod
    def from_dict(cls, data: dict) -> "AgentMessage":
        """从字典创建消息。"""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            type=data.get("type", MessageType.EVENT.value),
            source=data.get("source", ""),
            target=data.get("target", ""),
            topic=data.get("topic", ""),
            content=data.get("content"),
            metadata=data.get("metadata", {}),
            priority=data.get("priority", MessagePriority.NORMAL.value),
            status=data.get("status", MessageStatus.PENDING.value),
            timestamp=data.get("timestamp", time.time()),
            expires_at=data.get("expires_at", 0.0),
            correlation_id=data.get("correlation_id", ""),
            reply_to=data.get("reply_to", ""),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
        )

    def is_expired(self) -> bool:
        """是否过期。"""
        if self.expires_at == 0:
            return False
        return time.time() > self.expires_at

    def is_broadcast(self) -> bool:
        """是否广播消息。"""
        return not self.target

    def create_reply(self, content: Any, msg_type: str = None) -> "AgentMessage":
        """创建回复消息。"""
        return AgentMessage(
            type=msg_type or MessageType.RESPONSE.value,
            source=self.target,
            target=self.source,
            content=content,
            correlation_id=self.correlation_id or self.id,
            reply_to=self.id,
        )


# ===== 通信统计 =====


class CommunicationStats:
    """通信统计"""

    def __init__(self):
        self._lock = threading.Lock()
        self._sent = 0
        self._received = 0
        self._delivered = 0
        self._failed = 0
        self._expired = 0
        self._by_type: dict[str, int] = defaultdict(int)
        self._by_source: dict[str, int] = defaultdict(int)
        self._by_target: dict[str, int] = defaultdict(int)
        self._start_time = time.time()

    def record_sent(self, message: AgentMessage) -> None:
        with self._lock:
            self._sent += 1
            self._by_type[message.type] += 1
            self._by_source[message.source] += 1
            if message.target:
                self._by_target[message.target] += 1

    def record_received(self) -> None:
        with self._lock:
            self._received += 1

    def record_delivered(self) -> None:
        with self._lock:
            self._delivered += 1

    def record_failed(self) -> None:
        with self._lock:
            self._failed += 1

    def record_expired(self) -> None:
        with self._lock:
            self._expired += 1

    def to_dict(self) -> dict:
        with self._lock:
            uptime = time.time() - self._start_time
            return {
                "sent": self._sent,
                "received": self._received,
                "delivered": self._delivered,
                "failed": self._failed,
                "expired": self._expired,
                "by_type": dict(self._by_type),
                "by_source": dict(self._by_source),
                "by_target": dict(self._by_target),
                "uptime_seconds": uptime,
                "messages_per_second": self._sent / uptime if uptime > 0 else 0,
            }

    def reset(self) -> None:
        with self._lock:
            self._sent = 0
            self._received = 0
            self._delivered = 0
            self._failed = 0
            self._expired = 0
            self._by_type.clear()
            self._by_source.clear()
            self._by_target.clear()
            self._start_time = time.time()


# ===== 事件总线 =====


class EventBus:
    """事件总线

    实现发布订阅模式，Agent 可订阅主题并接收相关事件。
    支持同步与异步订阅者。
    """

    def __init__(self):
        self._subscribers: dict[str, list] = defaultdict(list)
        self._lock = threading.RLock()
        self._stats = CommunicationStats()
        self._history: deque = deque(maxlen=1000)

    def subscribe(self, topic: str, handler: Callable, filter_func: Optional[Callable] = None) -> str:
        """订阅主题。

        Args:
            topic: 主题名称。
            handler: 事件处理函数（同步或异步）。
            filter_func: 可选，事件过滤函数。

        Returns:
            订阅 ID（用于取消订阅）。
        """
        sub_id = str(uuid.uuid4())
        with self._lock:
            self._subscribers[topic].append({
                "id": sub_id,
                "handler": handler,
                "filter": filter_func,
            })
        return sub_id

    def unsubscribe(self, topic: str, sub_id: str) -> bool:
        """取消订阅。"""
        with self._lock:
            if topic not in self._subscribers:
                return False
            before = len(self._subscribers[topic])
            self._subscribers[topic] = [
                s for s in self._subscribers[topic] if s["id"] != sub_id
            ]
            return len(self._subscribers[topic]) < before

    def unsubscribe_all(self, topic: str) -> int:
        """取消主题的所有订阅。

        Returns:
            取消的订阅数。
        """
        with self._lock:
            count = len(self._subscribers.get(topic, []))
            self._subscribers.pop(topic, None)
            return count

    def publish(self, message: AgentMessage) -> int:
        """发布事件（同步）。

        Args:
            message: 事件消息。

        Returns:
            投递到的订阅者数。
        """
        if message.is_expired():
            self._stats.record_expired()
            return 0

        with self._lock:
            subscribers = list(self._subscribers.get(message.topic, []))
            # 也投递给通配订阅者
            subscribers.extend(self._subscribers.get("*", []))

        delivered = 0
        self._stats.record_sent(message)
        self._history.append(message)

        for sub in subscribers:
            # 应用过滤器
            if sub["filter"] and not sub["filter"](message):
                continue
            try:
                sub["handler"](message)
                delivered += 1
                self._stats.record_delivered()
            except Exception:
                self._stats.record_failed()

        return delivered

    async def publish_async(self, message: AgentMessage) -> int:
        """发布事件（异步）。

        异步调用订阅者。
        """
        if message.is_expired():
            self._stats.record_expired()
            return 0

        with self._lock:
            subscribers = list(self._subscribers.get(message.topic, []))
            subscribers.extend(self._subscribers.get("*", []))

        delivered = 0
        self._stats.record_sent(message)
        self._history.append(message)

        tasks = []
        for sub in subscribers:
            if sub["filter"] and not sub["filter"](message):
                continue
            tasks.append(self._call_handler_async(sub["handler"], message))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                self._stats.record_failed()
            else:
                if result:
                    delivered += 1
                    self._stats.record_delivered()

        return delivered

    async def _call_handler_async(self, handler: Callable, message: AgentMessage) -> bool:
        """异步调用处理器。"""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(message)
            else:
                handler(message)
            return True
        except Exception:
            return False

    def get_subscribers(self, topic: str) -> list:
        """获取主题的订阅者。"""
        with self._lock:
            return list(self._subscribers.get(topic, []))

    def list_topics(self) -> list:
        """列出所有主题。"""
        with self._lock:
            return list(self._subscribers.keys())

    def get_history(self, topic: Optional[str] = None, limit: int = 100) -> list:
        """获取事件历史。"""
        with self._lock:
            history = list(self._history)
        if topic:
            history = [m for m in history if m.topic == topic]
        return history[-limit:]

    def get_stats(self) -> dict:
        """获取统计。"""
        return self._stats.to_dict()

    def clear_history(self) -> None:
        """清空历史。"""
        with self._lock:
            self._history.clear()


# ===== 消息总线 =====


class MessageBus:
    """消息总线

    实现点对点消息通信，支持消息队列与确认机制。
    """

    def __init__(self, max_queue_size: int = 1000):
        self._queues: dict[str, deque] = defaultdict(lambda: deque(maxlen=max_queue_size))
        self._lock = threading.RLock()
        self._stats = CommunicationStats()
        self._handlers: dict[str, Callable] = {}
        self._pending_acks: dict[str, AgentMessage] = {}

    def register_handler(self, agent_id: str, handler: Callable) -> None:
        """注册消息处理器。"""
        with self._lock:
            self._handlers[agent_id] = handler

    def unregister_handler(self, agent_id: str) -> None:
        """注销消息处理器。"""
        with self._lock:
            self._handlers.pop(agent_id, None)

    def send(self, message: AgentMessage) -> bool:
        """发送消息（同步）。

        Args:
            message: 消息对象。

        Returns:
            发送成功返回 True。
        """
        if message.is_expired():
            self._stats.record_expired()
            return False

        if message.is_broadcast():
            # 广播消息：投递给所有已注册处理器
            with self._lock:
                handlers = list(self._handlers.items())
            self._stats.record_sent(message)
            delivered = False
            for agent_id, handler in handlers:
                if agent_id != message.source:
                    try:
                        handler(message)
                        delivered = True
                        self._stats.record_delivered()
                    except Exception:
                        self._stats.record_failed()
            return delivered
        else:
            # 点对点消息
            with self._lock:
                handler = self._handlers.get(message.target)
                self._queues[message.target].append(message)
            self._stats.record_sent(message)
            if handler:
                try:
                    handler(message)
                    self._stats.record_delivered()
                    return True
                except Exception:
                    self._stats.record_failed()
                    return False
            return True  # 入队成功，等待处理

    async def send_async(self, message: AgentMessage) -> bool:
        """发送消息（异步）。"""
        if message.is_expired():
            self._stats.record_expired()
            return False

        if message.is_broadcast():
            with self._lock:
                handlers = list(self._handlers.items())
            self._stats.record_sent(message)
            tasks = []
            for agent_id, handler in handlers:
                if agent_id != message.source:
                    tasks.append(self._call_handler_async(handler, message))
            results = await asyncio.gather(*tasks, return_exceptions=True)
            delivered = any(r is True for r in results)
            return delivered
        else:
            with self._lock:
                handler = self._handlers.get(message.target)
                self._queues[message.target].append(message)
            self._stats.record_sent(message)
            if handler:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(message)
                    else:
                        handler(message)
                    self._stats.record_delivered()
                    return True
                except Exception:
                    self._stats.record_failed()
                    return False
            return True

    async def _call_handler_async(self, handler: Callable, message: AgentMessage) -> bool:
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(message)
            else:
                handler(message)
            return True
        except Exception:
            return False

    def get_messages(self, agent_id: str) -> list:
        """获取 Agent 的待处理消息。"""
        with self._lock:
            return list(self._queues.get(agent_id, []))

    def acknowledge(self, message_id: str) -> bool:
        """确认消息处理完成。"""
        with self._lock:
            for agent_id, queue in self._queues.items():
                for i, msg in enumerate(queue):
                    if msg.id == message_id:
                        queue.remove(msg)
                        return True
        return False

    def get_queue_size(self, agent_id: str) -> int:
        """获取队列大小。"""
        with self._lock:
            return len(self._queues.get(agent_id, []))

    def clear_queue(self, agent_id: str) -> int:
        """清空队列。

        Returns:
            清空的消息数。
        """
        with self._lock:
            count = len(self._queues.get(agent_id, []))
            self._queues[agent_id].clear()
            return count

    def get_stats(self) -> dict:
        """获取统计。"""
        return self._stats.to_dict()


# ===== 消息路由器 =====


class MessageRouter:
    """消息路由器

    根据消息内容、目标、主题等规则路由消息到不同处理器。
    """

    def __init__(self):
        self._rules: list = []
        self._default_handler: Optional[Callable] = None
        self._lock = threading.RLock()

    def add_rule(
        self,
        handler: Callable,
        source: Optional[str] = None,
        target: Optional[str] = None,
        topic: Optional[str] = None,
        msg_type: Optional[str] = None,
        content_filter: Optional[Callable] = None,
        priority: int = 0,
    ) -> int:
        """添加路由规则。

        Args:
            handler: 处理函数。
            source: 匹配的发送方。
            target: 匹配的接收方。
            topic: 匹配的主题。
            msg_type: 匹配的消息类型。
            content_filter: 内容过滤函数。
            priority: 规则优先级（高优先）。

        Returns:
            规则 ID。
        """
        rule_id = len(self._rules)
        with self._lock:
            self._rules.append({
                "id": rule_id,
                "handler": handler,
                "source": source,
                "target": target,
                "topic": topic,
                "msg_type": msg_type,
                "content_filter": content_filter,
                "priority": priority,
            })
            # 按优先级排序
            self._rules.sort(key=lambda r: r["priority"], reverse=True)
        return rule_id

    def remove_rule(self, rule_id: int) -> bool:
        """移除路由规则。"""
        with self._lock:
            before = len(self._rules)
            self._rules = [r for r in self._rules if r["id"] != rule_id]
            return len(self._rules) < before

    def set_default_handler(self, handler: Callable) -> None:
        """设置默认处理器。"""
        with self._lock:
            self._default_handler = handler

    def route(self, message: AgentMessage) -> int:
        """路由消息。

        Args:
            message: 消息对象。

        Returns:
            投递到的处理器数。
        """
        with self._lock:
            rules = list(self._rules)

        delivered = 0
        for rule in rules:
            if self._matches(rule, message):
                try:
                    rule["handler"](message)
                    delivered += 1
                except Exception:
                    pass

        if delivered == 0 and self._default_handler:
            try:
                self._default_handler(message)
                delivered += 1
            except Exception:
                pass

        return delivered

    def _matches(self, rule: dict, message: AgentMessage) -> bool:
        """检查规则是否匹配消息。"""
        if rule["source"] and message.source != rule["source"]:
            return False
        if rule["target"] and message.target != rule["target"]:
            return False
        if rule["topic"] and message.topic != rule["topic"]:
            return False
        if rule["msg_type"] and message.type != rule["msg_type"]:
            return False
        if rule["content_filter"] and not rule["content_filter"](message):
            return False
        return True

    def list_rules(self) -> list:
        """列出所有规则。"""
        with self._lock:
            return [
                {
                    "id": r["id"],
                    "source": r["source"],
                    "target": r["target"],
                    "topic": r["topic"],
                    "msg_type": r["msg_type"],
                    "priority": r["priority"],
                }
                for r in self._rules
            ]

    def clear_rules(self) -> None:
        """清空所有规则。"""
        with self._lock:
            self._rules.clear()


# ===== Agent 通信器 =====


class AgentCommunicator:
    """Agent 通信器

    整合事件总线、消息总线与路由器，提供统一的 Agent 间通信接口。
    每个 Agent 实例持有一个通信器。
    """

    def __init__(self, agent_id: str):
        """初始化通信器。

        Args:
            agent_id: Agent 标识。
        """
        self.agent_id = agent_id
        self.event_bus = EventBus()
        self.message_bus = MessageBus()
        self.router = MessageRouter()
        self._stats = CommunicationStats()
        self._lock = threading.RLock()
        self._message_handlers: dict[str, Callable] = {}

    def send_message(
        self,
        target: str,
        content: Any,
        msg_type: str = MessageType.MESSAGE.value,
        topic: str = "",
        priority: int = MessagePriority.NORMAL.value,
        correlation_id: str = "",
    ) -> AgentMessage:
        """发送消息到指定 Agent。

        Args:
            target: 接收方 Agent ID。
            content: 消息内容。
            msg_type: 消息类型。
            topic: 主题。
            priority: 优先级。
            correlation_id: 关联 ID。

        Returns:
            发送的消息对象。
        """
        message = AgentMessage(
            type=msg_type,
            source=self.agent_id,
            target=target,
            topic=topic,
            content=content,
            priority=priority,
            correlation_id=correlation_id,
        )
        self.message_bus.send(message)
        self._stats.record_sent(message)
        return message

    async def send_message_async(
        self,
        target: str,
        content: Any,
        msg_type: str = MessageType.MESSAGE.value,
        **kwargs,
    ) -> AgentMessage:
        """异步发送消息。"""
        message = AgentMessage(
            type=msg_type,
            source=self.agent_id,
            target=target,
            content=content,
            **kwargs,
        )
        await self.message_bus.send_async(message)
        self._stats.record_sent(message)
        return message

    def broadcast(
        self,
        content: Any,
        topic: str = "",
        msg_type: str = MessageType.NOTIFICATION.value,
    ) -> AgentMessage:
        """广播消息到所有 Agent。"""
        message = AgentMessage(
            type=msg_type,
            source=self.agent_id,
            target="",  # 空目标表示广播
            topic=topic,
            content=content,
        )
        self.message_bus.send(message)
        self._stats.record_sent(message)
        return message

    def publish_event(
        self,
        topic: str,
        content: Any,
        metadata: Optional[dict] = None,
    ) -> AgentMessage:
        """发布事件。"""
        message = AgentMessage(
            type=MessageType.EVENT.value,
            source=self.agent_id,
            topic=topic,
            content=content,
            metadata=metadata or {},
        )
        self.event_bus.publish(message)
        self._stats.record_sent(message)
        return message

    async def publish_event_async(
        self,
        topic: str,
        content: Any,
        metadata: Optional[dict] = None,
    ) -> AgentMessage:
        """异步发布事件。"""
        message = AgentMessage(
            type=MessageType.EVENT.value,
            source=self.agent_id,
            topic=topic,
            content=content,
            metadata=metadata or {},
        )
        await self.event_bus.publish_async(message)
        self._stats.record_sent(message)
        return message

    def subscribe(
        self,
        topic: str,
        handler: Callable,
        filter_func: Optional[Callable] = None,
    ) -> str:
        """订阅事件。"""
        return self.event_bus.subscribe(topic, handler, filter_func)

    def unsubscribe(self, topic: str, sub_id: str) -> bool:
        """取消订阅。"""
        return self.event_bus.unsubscribe(topic, sub_id)

    def register_message_handler(self, handler: Callable) -> None:
        """注册消息处理器（接收发给本 Agent 的消息）。"""
        self.message_bus.register_handler(self.agent_id, handler)

    def unregister_message_handler(self) -> None:
        """注销消息处理器。"""
        self.message_bus.unregister_handler(self.agent_id)

    def request(
        self,
        target: str,
        content: Any,
        timeout: float = 30.0,
    ) -> Optional[AgentMessage]:
        """发送请求并等待响应（同步）。

        Args:
            target: 目标 Agent ID。
            content: 请求内容。
            timeout: 超时秒数。

        Returns:
            响应消息，超时返回 None。
        """
        correlation_id = str(uuid.uuid4())
        response_event = threading.Event()
        response_holder: list = []

        def response_handler(msg: AgentMessage):
            if msg.correlation_id == correlation_id:
                response_holder.append(msg)
                response_event.set()

        # 临时订阅响应
        sub_id = self.subscribe(f"response.{correlation_id}", response_handler)

        # 发送请求
        self.send_message(
            target=target,
            content=content,
            msg_type=MessageType.REQUEST.value,
            correlation_id=correlation_id,
        )

        # 等待响应
        response_event.wait(timeout=timeout)
        self.unsubscribe(f"response.{correlation_id}", sub_id)

        return response_holder[0] if response_holder else None

    async def request_async(
        self,
        target: str,
        content: Any,
        timeout: float = 30.0,
    ) -> Optional[AgentMessage]:
        """发送请求并等待响应（异步）。"""
        correlation_id = str(uuid.uuid4())
        future: asyncio.Future = asyncio.get_event_loop().create_future()

        async def response_handler(msg: AgentMessage):
            if msg.correlation_id == correlation_id and not future.done():
                future.set_result(msg)

        sub_id = self.subscribe(f"response.{correlation_id}", response_handler)

        await self.send_message_async(
            target=target,
            content=content,
            msg_type=MessageType.REQUEST.value,
            correlation_id=correlation_id,
        )

        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            return None
        finally:
            self.unsubscribe(f"response.{correlation_id}", sub_id)

    def respond(self, original_message: AgentMessage, content: Any) -> AgentMessage:
        """回复消息。"""
        response = original_message.create_reply(content)
        response.topic = f"response.{original_message.correlation_id or original_message.id}"
        self.event_bus.publish(response)
        self._stats.record_sent(response)
        return response

    def get_stats(self) -> dict:
        """获取通信统计。"""
        return {
            "agent_id": self.agent_id,
            "own_stats": self._stats.to_dict(),
            "event_bus": self.event_bus.get_stats(),
            "message_bus": self.message_bus.get_stats(),
        }

    def reset(self) -> None:
        """重置通信器。"""
        self._stats.reset()
        self.event_bus.clear_history()


# ===== 全局通信注册表 =====


class CommunicatorRegistry:
    """通信器注册表

    管理多个 Agent 的通信器，支持按 agent_id 检索。
    """

    def __init__(self):
        self._communicators: dict[str, AgentCommunicator] = {}
        self._lock = threading.RLock()

    def create_communicator(self, agent_id: str) -> AgentCommunicator:
        """创建通信器。"""
        with self._lock:
            if agent_id in self._communicators:
                return self._communicators[agent_id]
            comm = AgentCommunicator(agent_id=agent_id)
            self._communicators[agent_id] = comm
            return comm

    def get_communicator(self, agent_id: str) -> Optional[AgentCommunicator]:
        """获取通信器。"""
        with self._lock:
            return self._communicators.get(agent_id)

    def remove_communicator(self, agent_id: str) -> bool:
        """移除通信器。"""
        with self._lock:
            if agent_id in self._communicators:
                del self._communicators[agent_id]
                return True
            return False

    def list_communicators(self) -> list:
        """列出所有通信器。"""
        with self._lock:
            return list(self._communicators.keys())

    def get_all_stats(self) -> dict:
        """获取所有通信器统计。"""
        with self._lock:
            return {aid: c.get_stats() for aid, c in self._communicators.items()}


# 全局注册表实例
_global_registry = CommunicatorRegistry()


def get_communicator_registry() -> CommunicatorRegistry:
    """获取全局通信器注册表。"""
    return _global_registry


def get_communicator(agent_id: str) -> Optional[AgentCommunicator]:
    """获取指定 Agent 的通信器。"""
    return _global_registry.get_communicator(agent_id)


def create_communicator(agent_id: str) -> AgentCommunicator:
    """创建通信器。"""
    return _global_registry.create_communicator(agent_id)


# ===== 预定义主题 =====


class Topics:
    """预定义事件主题"""
    # 编排相关
    ORCHESTRATION_START = "orchestration.start"
    ORCHESTRATION_COMPLETE = "orchestration.complete"
    ORCHESTRATION_FAILED = "orchestration.failed"
    STAGE_ENTER = "stage.enter"
    STAGE_EXIT = "stage.exit"
    STAGE_RETRY = "stage.retry"

    # Agent 相关
    AGENT_STARTED = "agent.started"
    AGENT_COMPLETED = "agent.completed"
    AGENT_ERROR = "agent.error"
    AGENT_TIMEOUT = "agent.timeout"

    # 任务相关
    TASK_CREATED = "task.created"
    TASK_ASSIGNED = "task.assigned"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"

    # 检索相关
    SEARCH_STARTED = "search.started"
    SEARCH_COMPLETED = "search.completed"
    SEARCH_DEGRADED = "search.degraded"

    # 生成相关
    GENERATION_STARTED = "generation.started"
    GENERATION_PROGRESS = "generation.progress"
    GENERATION_COMPLETED = "generation.completed"

    # 校验相关
    VALIDATION_PASSED = "validation.passed"
    VALIDATION_FAILED = "validation.failed"
    GATE_PASSED = "gate.passed"
    GATE_FAILED = "gate.failed"

    # 预算相关
    BUDGET_WARNING = "budget.warning"
    BUDGET_EXCEEDED = "budget.exceeded"
    COST_RECORDED = "cost.recorded"

    # 缓存相关
    CACHE_HIT = "cache.hit"
    CACHE_MISS = "cache.miss"

    # 系统相关
    SYSTEM_HEALTH = "system.health"
    SYSTEM_ERROR = "system.error"
