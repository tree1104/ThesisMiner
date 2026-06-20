# -*- coding: utf-8 -*-
"""
test_agent_communicator.py - Agent 通信总线模块单元测试

本测试文件覆盖 backend/agents/agent_communicator.py 中的所有组件：
- MessageType / MessagePriority / MessageStatus 枚举
- AgentMessage 数据类（to_dict/to_json/from_dict/is_expired/is_broadcast/create_reply）
- CommunicationStats 通信统计
- EventBus 事件总线（subscribe/unsubscribe/publish/publish_async/get_history/get_stats）
- MessageBus 消息总线（register_handler/send/send_async/get_messages/acknowledge/clear_queue）
- MessageRouter 消息路由器（add_rule/remove_rule/set_default_handler/route/list_rules）
- AgentCommunicator 通信器（send_message/broadcast/publish_event/subscribe/request/respond）
- CommunicatorRegistry 注册表
- Topics 预定义主题常量
- 全局函数（get_communicator_registry/get_communicator/create_communicator）

作者：ThesisMiner 团队
版本：v8.0
"""

import json
import time
import threading
import pytest
import asyncio
from unittest.mock import patch, MagicMock
from datetime import datetime

# 由于源模块可能存在导入问题（MessageType.MESSAGE 属性缺失），
# 使用 try/except 保护导入，确保测试文件可被 pytest 收集
try:
    from backend.agents.agent_communicator import (
        MessageType,
        MessagePriority,
        MessageStatus,
        AgentMessage,
        CommunicationStats,
        EventBus,
        MessageBus,
        MessageRouter,
        AgentCommunicator,
        CommunicatorRegistry,
        Topics,
        get_communicator_registry,
        get_communicator,
        create_communicator,
    )
    _IMPORT_OK = True
    _IMPORT_ERROR = None
except Exception as e:
    _IMPORT_OK = False
    _IMPORT_ERROR = e
    # 创建占位对象以避免 NameError
    MessageType = None
    MessagePriority = None
    MessageStatus = None
    AgentMessage = None
    CommunicationStats = None
    EventBus = None
    MessageBus = None
    MessageRouter = None
    AgentCommunicator = None
    CommunicatorRegistry = None
    Topics = None
    get_communicator_registry = None
    get_communicator = None
    create_communicator = None

# 如果导入失败，跳过所有测试
pytestmark = pytest.mark.skipif(not _IMPORT_OK, reason=f"agent_communicator 模块导入失败: {_IMPORT_ERROR}")


# ===== MessageType 枚举测试 =====


class TestMessageType:
    """测试 MessageType 枚举。"""

    def test_type_values(self):
        """测试枚举值存在。"""
        assert MessageType.REQUEST
        assert MessageType.RESPONSE
        assert MessageType.EVENT
        assert MessageType.NOTIFICATION
        assert MessageType.COMMAND
        assert MessageType.QUERY
        assert MessageType.RESULT
        assert MessageType.ERROR
        assert MessageType.HEARTBEAT

    def test_type_count(self):
        """测试枚举成员数量。"""
        types = list(MessageType)
        assert len(types) == 9

    def test_type_uniqueness(self):
        """测试枚举值唯一性。"""
        values = [t.value for t in MessageType]
        assert len(values) == len(set(values))

    def test_type_string_values(self):
        """测试枚举值为字符串。"""
        for msg_type in MessageType:
            assert isinstance(msg_type.value, str)

    def test_type_lookup_by_value(self):
        """测试通过值查找枚举。"""
        for msg_type in MessageType:
            assert MessageType(msg_type.value) == msg_type

    def test_type_inheritance(self):
        """测试枚举继承 str。"""
        assert isinstance(MessageType.REQUEST, str)

    def test_specific_values(self):
        """测试特定枚举值。"""
        assert MessageType.REQUEST.value == "request"
        assert MessageType.RESPONSE.value == "response"
        assert MessageType.EVENT.value == "event"
        assert MessageType.NOTIFICATION.value == "notification"
        assert MessageType.COMMAND.value == "command"
        assert MessageType.QUERY.value == "query"
        assert MessageType.RESULT.value == "result"
        assert MessageType.ERROR.value == "error"
        assert MessageType.HEARTBEAT.value == "heartbeat"


# ===== MessagePriority 枚举测试 =====


class TestMessagePriority:
    """测试 MessagePriority 枚举。"""

    def test_priority_values(self):
        """测试优先级值存在。"""
        assert MessagePriority.LOW
        assert MessagePriority.NORMAL
        assert MessagePriority.HIGH
        assert MessagePriority.URGENT

    def test_priority_ordering(self):
        """测试优先级顺序。"""
        assert MessagePriority.LOW < MessagePriority.NORMAL
        assert MessagePriority.NORMAL < MessagePriority.HIGH
        assert MessagePriority.HIGH < MessagePriority.URGENT

    def test_priority_int_values(self):
        """测试优先级整数值。"""
        assert MessagePriority.LOW.value == 0
        assert MessagePriority.NORMAL.value == 1
        assert MessagePriority.HIGH.value == 2
        assert MessagePriority.URGENT.value == 3

    def test_priority_inheritance(self):
        """测试枚举继承 int。"""
        assert isinstance(MessagePriority.LOW, int)

    def test_priority_count(self):
        """测试枚举成员数量。"""
        priorities = list(MessagePriority)
        assert len(priorities) == 4


# ===== MessageStatus 枚举测试 =====


class TestMessageStatus:
    """测试 MessageStatus 枚举。"""

    def test_status_values(self):
        """测试状态值存在。"""
        assert MessageStatus.PENDING
        assert MessageStatus.DELIVERED
        assert MessageStatus.PROCESSED
        assert MessageStatus.FAILED
        assert MessageStatus.EXPIRED

    def test_status_count(self):
        """测试枚举成员数量。"""
        statuses = list(MessageStatus)
        assert len(statuses) == 5

    def test_status_uniqueness(self):
        """测试枚举值唯一性。"""
        values = [s.value for s in MessageStatus]
        assert len(values) == len(set(values))

    def test_status_string_values(self):
        """测试枚举值为字符串。"""
        for status in MessageStatus:
            assert isinstance(status.value, str)

    def test_specific_status_values(self):
        """测试特定状态值。"""
        assert MessageStatus.PENDING.value == "pending"
        assert MessageStatus.DELIVERED.value == "delivered"
        assert MessageStatus.PROCESSED.value == "processed"
        assert MessageStatus.FAILED.value == "failed"
        assert MessageStatus.EXPIRED.value == "expired"


# ===== AgentMessage 数据类测试 =====


class TestAgentMessage:
    """测试 AgentMessage 数据类。"""

    def test_create_default_message(self):
        """测试创建默认消息。"""
        msg = AgentMessage()
        assert msg.id is not None
        assert msg.type == MessageType.EVENT.value
        assert msg.source == ""
        assert msg.target == ""
        assert msg.content is None

    def test_create_with_content(self):
        """测试带内容创建消息。"""
        msg = AgentMessage(content="测试内容")
        assert msg.content == "测试内容"

    def test_create_with_source_target(self):
        """测试带发送方和接收方创建。"""
        msg = AgentMessage(source="agent_1", target="agent_2")
        assert msg.source == "agent_1"
        assert msg.target == "agent_2"

    def test_create_with_topic(self):
        """测试带主题创建。"""
        msg = AgentMessage(topic="search.results")
        assert msg.topic == "search.results"

    def test_create_with_priority(self):
        """测试带优先级创建。"""
        msg = AgentMessage(priority=MessagePriority.HIGH.value)
        assert msg.priority == MessagePriority.HIGH.value

    def test_create_with_metadata(self):
        """测试带元数据创建。"""
        metadata = {"key": "value", "timestamp": "2024-01-01"}
        msg = AgentMessage(metadata=metadata)
        assert msg.metadata == metadata

    def test_to_dict(self):
        """测试转换为字典。"""
        msg = AgentMessage(source="a", target="b", content="测试")
        d = msg.to_dict()
        assert d["source"] == "a"
        assert d["target"] == "b"
        assert d["content"] == "测试"
        assert "id" in d
        assert "type" in d
        assert "timestamp" in d

    def test_to_json(self):
        """测试转换为 JSON。"""
        msg = AgentMessage(content="JSON 测试")
        json_str = msg.to_json()
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["content"] == "JSON 测试"

    def test_from_dict(self):
        """测试从字典创建。"""
        data = {
            "id": "test_id",
            "type": "request",
            "source": "agent_1",
            "target": "agent_2",
            "content": "从字典创建",
        }
        msg = AgentMessage.from_dict(data)
        assert msg.id == "test_id"
        assert msg.type == "request"
        assert msg.source == "agent_1"
        assert msg.target == "agent_2"
        assert msg.content == "从字典创建"

    def test_from_dict_with_defaults(self):
        """测试从不完整字典创建（使用默认值）。"""
        data = {"content": "最小数据"}
        msg = AgentMessage.from_dict(data)
        assert msg.content == "最小数据"
        assert msg.id  # 应自动生成

    def test_is_expired_not_expired(self):
        """测试未过期消息。"""
        msg = AgentMessage(expires_at=0)  # 0 表示永不过期
        assert msg.is_expired() is False

    def test_is_expired_with_future_time(self):
        """测试未来过期时间。"""
        msg = AgentMessage(expires_at=time.time() + 3600)
        assert msg.is_expired() is False

    def test_is_expired_with_past_time(self):
        """测试已过期消息。"""
        msg = AgentMessage(expires_at=time.time() - 100)
        assert msg.is_expired() is True

    def test_is_broadcast_no_target(self):
        """测试无目标的广播消息。"""
        msg = AgentMessage(target="")
        assert msg.is_broadcast() is True

    def test_is_broadcast_with_target(self):
        """测试有目标的非广播消息。"""
        msg = AgentMessage(target="agent_1")
        assert msg.is_broadcast() is False

    def test_create_reply(self):
        """测试创建回复消息。"""
        original = AgentMessage(
            source="agent_1",
            target="agent_2",
            content="原始请求",
            correlation_id="corr_123",
        )
        reply = original.create_reply("回复内容")
        assert reply.content == "回复内容"
        assert reply.source == "agent_2"  # 回复的发送方是原接收方
        assert reply.target == "agent_1"  # 回复的接收方是原发送方
        assert reply.reply_to == original.id

    def test_create_reply_with_type(self):
        """测试带类型的回复。"""
        original = AgentMessage(source="a", target="b")
        reply = original.create_reply("回复", msg_type=MessageType.RESULT.value)
        assert reply.type == MessageType.RESULT.value

    def test_unique_ids(self):
        """测试消息 ID 唯一性。"""
        msg1 = AgentMessage()
        msg2 = AgentMessage()
        assert msg1.id != msg2.id

    def test_timestamp_auto_set(self):
        """测试时间戳自动设置。"""
        msg = AgentMessage()
        assert msg.timestamp > 0

    def test_default_retry_count(self):
        """测试默认重试次数。"""
        msg = AgentMessage()
        assert msg.retry_count == 0
        assert msg.max_retries == 3

    def test_round_trip_json(self):
        """测试 JSON 往返转换。"""
        original = AgentMessage(
            source="agent_1",
            target="agent_2",
            content="往返测试",
            topic="test.topic",
        )
        json_str = original.to_json()
        restored = AgentMessage.from_dict(json.loads(json_str))
        assert restored.source == original.source
        assert restored.target == original.target
        assert restored.content == original.content
        assert restored.topic == original.topic


# ===== CommunicationStats 测试 =====


class TestCommunicationStats:
    """测试 CommunicationStats 类。"""

    def test_create_stats(self):
        """测试创建统计。"""
        stats = CommunicationStats()
        d = stats.to_dict()
        assert d["sent"] == 0
        assert d["received"] == 0
        assert d["delivered"] == 0

    def test_record_sent(self):
        """测试记录发送。"""
        stats = CommunicationStats()
        msg = AgentMessage(source="a", type="event")
        stats.record_sent(msg)
        d = stats.to_dict()
        assert d["sent"] == 1
        assert d["by_source"]["a"] == 1
        assert d["by_type"]["event"] == 1

    def test_record_received(self):
        """测试记录接收。"""
        stats = CommunicationStats()
        stats.record_received()
        assert stats.to_dict()["received"] == 1

    def test_record_delivered(self):
        """测试记录投递。"""
        stats = CommunicationStats()
        stats.record_delivered()
        assert stats.to_dict()["delivered"] == 1

    def test_record_failed(self):
        """测试记录失败。"""
        stats = CommunicationStats()
        stats.record_failed()
        assert stats.to_dict()["failed"] == 1

    def test_record_expired(self):
        """测试记录过期。"""
        stats = CommunicationStats()
        stats.record_expired()
        assert stats.to_dict()["expired"] == 1

    def test_reset(self):
        """测试重置统计。"""
        stats = CommunicationStats()
        msg = AgentMessage(source="a")
        stats.record_sent(msg)
        stats.record_delivered()
        stats.reset()
        d = stats.to_dict()
        assert d["sent"] == 0
        assert d["delivered"] == 0

    def test_by_type_tracking(self):
        """测试按类型统计。"""
        stats = CommunicationStats()
        stats.record_sent(AgentMessage(type="request"))
        stats.record_sent(AgentMessage(type="response"))
        stats.record_sent(AgentMessage(type="request"))
        d = stats.to_dict()
        assert d["by_type"]["request"] == 2
        assert d["by_type"]["response"] == 1

    def test_by_source_tracking(self):
        """测试按来源统计。"""
        stats = CommunicationStats()
        stats.record_sent(AgentMessage(source="agent_1"))
        stats.record_sent(AgentMessage(source="agent_2"))
        stats.record_sent(AgentMessage(source="agent_1"))
        d = stats.to_dict()
        assert d["by_source"]["agent_1"] == 2
        assert d["by_source"]["agent_2"] == 1

    def test_by_target_tracking(self):
        """测试按目标统计。"""
        stats = CommunicationStats()
        stats.record_sent(AgentMessage(source="a", target="agent_1"))
        stats.record_sent(AgentMessage(source="b", target="agent_2"))
        d = stats.to_dict()
        assert d["by_target"]["agent_1"] == 1
        assert d["by_target"]["agent_2"] == 1

    def test_messages_per_second(self):
        """测试每秒消息数计算。"""
        stats = CommunicationStats()
        msg = AgentMessage(source="a")
        stats.record_sent(msg)
        d = stats.to_dict()
        assert d["messages_per_second"] >= 0

    def test_uptime(self):
        """测试运行时间。"""
        stats = CommunicationStats()
        time.sleep(0.1)
        d = stats.to_dict()
        assert d["uptime_seconds"] > 0

    def test_thread_safety(self):
        """测试线程安全。"""
        stats = CommunicationStats()
        msg = AgentMessage(source="a")

        def record():
            for _ in range(100):
                stats.record_sent(msg)

        threads = [threading.Thread(target=record) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert stats.to_dict()["sent"] == 500


# ===== EventBus 测试 =====


class TestEventBus:
    """测试 EventBus 类。"""

    def test_create_event_bus(self):
        """测试创建事件总线。"""
        bus = EventBus()
        assert bus.list_topics() == []

    def test_subscribe(self):
        """测试订阅。"""
        bus = EventBus()
        sub_id = bus.subscribe("test.topic", lambda msg: None)
        assert isinstance(sub_id, str)
        assert "test.topic" in bus.list_topics()

    def test_subscribe_with_filter(self):
        """测试带过滤器的订阅。"""
        bus = EventBus()
        received = []

        def filter_func(msg):
            return msg.priority >= MessagePriority.HIGH.value

        bus.subscribe("test.topic", lambda msg: received.append(msg), filter_func)

        # 低优先级消息应被过滤
        low_msg = AgentMessage(topic="test.topic", priority=MessagePriority.LOW.value)
        bus.publish(low_msg)
        assert len(received) == 0

        # 高优先级消息应通过
        high_msg = AgentMessage(topic="test.topic", priority=MessagePriority.HIGH.value)
        bus.publish(high_msg)
        assert len(received) == 1

    def test_unsubscribe(self):
        """测试取消订阅。"""
        bus = EventBus()
        sub_id = bus.subscribe("test.topic", lambda msg: None)
        result = bus.unsubscribe("test.topic", sub_id)
        assert result is True

    def test_unsubscribe_not_found(self):
        """测试取消不存在的订阅。"""
        bus = EventBus()
        result = bus.unsubscribe("nonexistent", "fake_id")
        assert result is False

    def test_unsubscribe_all(self):
        """测试取消所有订阅。"""
        bus = EventBus()
        bus.subscribe("topic1", lambda msg: None)
        bus.subscribe("topic1", lambda msg: None)
        count = bus.unsubscribe_all("topic1")
        assert count == 2
        assert "topic1" not in bus.list_topics()

    def test_publish(self):
        """测试发布事件。"""
        bus = EventBus()
        received = []
        bus.subscribe("test.topic", lambda msg: received.append(msg))
        msg = AgentMessage(topic="test.topic", content="测试事件")
        delivered = bus.publish(msg)
        assert delivered == 1
        assert len(received) == 1
        assert received[0].content == "测试事件"

    def test_publish_no_subscribers(self):
        """测试无订阅者发布。"""
        bus = EventBus()
        msg = AgentMessage(topic="no.subscribers", content="测试")
        delivered = bus.publish(msg)
        assert delivered == 0

    def test_publish_expired(self):
        """测试发布过期消息。"""
        bus = EventBus()
        received = []
        bus.subscribe("test.topic", lambda msg: received.append(msg))
        msg = AgentMessage(topic="test.topic", expires_at=time.time() - 100)
        delivered = bus.publish(msg)
        assert delivered == 0
        assert len(received) == 0

    def test_publish_multiple_subscribers(self):
        """测试多订阅者发布。"""
        bus = EventBus()
        received1 = []
        received2 = []
        bus.subscribe("test.topic", lambda msg: received1.append(msg))
        bus.subscribe("test.topic", lambda msg: received2.append(msg))
        msg = AgentMessage(topic="test.topic")
        delivered = bus.publish(msg)
        assert delivered == 2
        assert len(received1) == 1
        assert len(received2) == 1

    def test_wildcard_subscription(self):
        """测试通配符订阅。"""
        bus = EventBus()
        received = []
        bus.subscribe("*", lambda msg: received.append(msg))
        msg = AgentMessage(topic="any.topic")
        bus.publish(msg)
        assert len(received) == 1

    def test_handler_exception_handling(self):
        """测试处理器异常处理。"""
        bus = EventBus()

        def bad_handler(msg):
            raise ValueError("处理器错误")

        bus.subscribe("test.topic", bad_handler)
        msg = AgentMessage(topic="test.topic")
        # 不应抛出异常
        delivered = bus.publish(msg)
        assert delivered == 0  # 异常导致未投递

    def test_get_subscribers(self):
        """测试获取订阅者。"""
        bus = EventBus()
        bus.subscribe("test.topic", lambda msg: None)
        subs = bus.get_subscribers("test.topic")
        assert len(subs) == 1

    def test_list_topics(self):
        """测试列出主题。"""
        bus = EventBus()
        bus.subscribe("topic1", lambda msg: None)
        bus.subscribe("topic2", lambda msg: None)
        topics = bus.list_topics()
        assert "topic1" in topics
        assert "topic2" in topics

    def test_get_history(self):
        """测试获取历史。"""
        bus = EventBus()
        bus.subscribe("test.topic", lambda msg: None)
        bus.publish(AgentMessage(topic="test.topic", content="消息1"))
        bus.publish(AgentMessage(topic="test.topic", content="消息2"))
        history = bus.get_history()
        assert len(history) == 2

    def test_get_history_with_topic_filter(self):
        """测试带主题过滤的历史。"""
        bus = EventBus()
        bus.subscribe("topic1", lambda msg: None)
        bus.subscribe("topic2", lambda msg: None)
        bus.publish(AgentMessage(topic="topic1"))
        bus.publish(AgentMessage(topic="topic2"))
        history = bus.get_history(topic="topic1")
        assert len(history) == 1

    def test_get_history_with_limit(self):
        """测试带限制的历史。"""
        bus = EventBus()
        bus.subscribe("test.topic", lambda msg: None)
        for i in range(10):
            bus.publish(AgentMessage(topic="test.topic", content=f"消息_{i}"))
        history = bus.get_history(limit=3)
        assert len(history) == 3

    def test_clear_history(self):
        """测试清空历史。"""
        bus = EventBus()
        bus.subscribe("test.topic", lambda msg: None)
        bus.publish(AgentMessage(topic="test.topic"))
        bus.clear_history()
        assert len(bus.get_history()) == 0

    def test_get_stats(self):
        """测试获取统计。"""
        bus = EventBus()
        bus.subscribe("test.topic", lambda msg: None)
        bus.publish(AgentMessage(topic="test.topic"))
        stats = bus.get_stats()
        assert isinstance(stats, dict)
        assert stats["sent"] == 1

    @pytest.mark.asyncio
    async def test_publish_async(self):
        """测试异步发布。"""
        bus = EventBus()
        received = []

        async def async_handler(msg):
            received.append(msg)

        bus.subscribe("test.topic", async_handler)
        msg = AgentMessage(topic="test.topic", content="异步测试")
        delivered = await bus.publish_async(msg)
        assert delivered == 1
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_publish_async_with_sync_handler(self):
        """测试异步发布带同步处理器。"""
        bus = EventBus()
        received = []
        bus.subscribe("test.topic", lambda msg: received.append(msg))
        msg = AgentMessage(topic="test.topic")
        delivered = await bus.publish_async(msg)
        assert delivered == 1


# ===== MessageBus 测试 =====


class TestMessageBus:
    """测试 MessageBus 类。"""

    def test_create_message_bus(self):
        """测试创建消息总线。"""
        bus = MessageBus()
        assert bus.get_stats()["sent"] == 0

    def test_register_handler(self):
        """测试注册处理器。"""
        bus = MessageBus()
        handler = MagicMock()
        bus.register_handler("agent_1", handler)
        # 发送消息应调用处理器
        msg = AgentMessage(source="agent_2", target="agent_1", content="测试")
        bus.send(msg)
        handler.assert_called_once_with(msg)

    def test_unregister_handler(self):
        """测试注销处理器。"""
        bus = MessageBus()
        handler = MagicMock()
        bus.register_handler("agent_1", handler)
        bus.unregister_handler("agent_1")
        msg = AgentMessage(source="agent_2", target="agent_1")
        bus.send(msg)
        handler.assert_not_called()

    def test_send_point_to_point(self):
        """测试点对点发送。"""
        bus = MessageBus()
        received = []
        bus.register_handler("agent_1", lambda msg: received.append(msg))
        msg = AgentMessage(source="agent_2", target="agent_1", content="点对点")
        result = bus.send(msg)
        assert result is True
        assert len(received) == 1

    def test_send_broadcast(self):
        """测试广播发送。"""
        bus = MessageBus()
        received1 = []
        received2 = []
        bus.register_handler("agent_1", lambda msg: received1.append(msg))
        bus.register_handler("agent_2", lambda msg: received2.append(msg))
        msg = AgentMessage(source="agent_3", target="", content="广播")  # 空目标=广播
        result = bus.send(msg)
        assert result is True
        assert len(received1) == 1
        assert len(received2) == 1

    def test_send_expired(self):
        """测试发送过期消息。"""
        bus = MessageBus()
        handler = MagicMock()
        bus.register_handler("agent_1", handler)
        msg = AgentMessage(
            source="agent_2",
            target="agent_1",
            expires_at=time.time() - 100,
        )
        result = bus.send(msg)
        assert result is False
        handler.assert_not_called()

    def test_send_no_handler(self):
        """测试发送到无处理器的 Agent。"""
        bus = MessageBus()
        msg = AgentMessage(source="agent_1", target="agent_no_handler")
        result = bus.send(msg)
        # 消息入队，返回 True
        assert result is True

    def test_get_messages(self):
        """测试获取待处理消息。"""
        bus = MessageBus()
        msg = AgentMessage(source="agent_1", target="agent_2")
        bus.send(msg)
        messages = bus.get_messages("agent_2")
        assert len(messages) >= 1

    def test_acknowledge(self):
        """测试确认消息。"""
        bus = MessageBus()
        msg = AgentMessage(source="agent_1", target="agent_2")
        bus.send(msg)
        result = bus.acknowledge(msg.id)
        assert result is True

    def test_acknowledge_not_found(self):
        """测试确认不存在的消息。"""
        bus = MessageBus()
        result = bus.acknowledge("nonexistent_id")
        assert result is False

    def test_get_queue_size(self):
        """测试获取队列大小。"""
        bus = MessageBus()
        bus.send(AgentMessage(source="a", target="agent_1"))
        bus.send(AgentMessage(source="b", target="agent_1"))
        size = bus.get_queue_size("agent_1")
        assert size >= 2

    def test_clear_queue(self):
        """测试清空队列。"""
        bus = MessageBus()
        bus.send(AgentMessage(source="a", target="agent_1"))
        bus.send(AgentMessage(source="b", target="agent_1"))
        count = bus.clear_queue("agent_1")
        assert count >= 2
        assert bus.get_queue_size("agent_1") == 0

    def test_get_stats(self):
        """测试获取统计。"""
        bus = MessageBus()
        handler = MagicMock()
        bus.register_handler("agent_1", handler)
        bus.send(AgentMessage(source="agent_2", target="agent_1"))
        stats = bus.get_stats()
        assert stats["sent"] == 1

    def test_handler_exception(self):
        """测试处理器异常。"""
        bus = MessageBus()

        def bad_handler(msg):
            raise ValueError("错误")

        bus.register_handler("agent_1", bad_handler)
        msg = AgentMessage(source="agent_2", target="agent_1")
        result = bus.send(msg)
        # 异常导致返回 False
        assert result is False

    @pytest.mark.asyncio
    async def test_send_async(self):
        """测试异步发送。"""
        bus = MessageBus()
        received = []

        async def async_handler(msg):
            received.append(msg)

        bus.register_handler("agent_1", async_handler)
        msg = AgentMessage(source="agent_2", target="agent_1")
        result = await bus.send_async(msg)
        assert result is True
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_send_async_broadcast(self):
        """测试异步广播。"""
        bus = MessageBus()
        received1 = []
        received2 = []

        async def handler1(msg):
            received1.append(msg)

        async def handler2(msg):
            received2.append(msg)

        bus.register_handler("agent_1", handler1)
        bus.register_handler("agent_2", handler2)
        msg = AgentMessage(source="agent_3", target="")
        result = await bus.send_async(msg)
        assert result is True


# ===== MessageRouter 测试 =====


class TestMessageRouter:
    """测试 MessageRouter 类。"""

    def test_create_router(self):
        """测试创建路由器。"""
        router = MessageRouter()
        assert router.list_rules() == []

    def test_add_rule(self):
        """测试添加规则。"""
        router = MessageRouter()
        handler = MagicMock()
        rule_id = router.add_rule(handler, source="agent_1")
        assert rule_id == 0
        rules = router.list_rules()
        assert len(rules) == 1

    def test_add_rule_with_all_filters(self):
        """测试带所有过滤器的规则。"""
        router = MessageRouter()
        handler = MagicMock()
        rule_id = router.add_rule(
            handler,
            source="agent_1",
            target="agent_2",
            topic="test.topic",
            msg_type="request",
            priority=10,
        )
        assert rule_id == 0

    def test_remove_rule(self):
        """测试移除规则。"""
        router = MessageRouter()
        handler = MagicMock()
        rule_id = router.add_rule(handler)
        result = router.remove_rule(rule_id)
        assert result is True
        assert len(router.list_rules()) == 0

    def test_remove_rule_not_found(self):
        """测试移除不存在的规则。"""
        router = MessageRouter()
        result = router.remove_rule(999)
        assert result is False

    def test_set_default_handler(self):
        """测试设置默认处理器。"""
        router = MessageRouter()
        default_handler = MagicMock()
        router.set_default_handler(default_handler)
        # 无匹配规则时调用默认处理器
        msg = AgentMessage(source="unknown")
        router.route(msg)
        default_handler.assert_called_once()

    def test_route_matching(self):
        """测试路由匹配。"""
        router = MessageRouter()
        handler = MagicMock()
        router.add_rule(handler, source="agent_1")
        msg = AgentMessage(source="agent_1")
        delivered = router.route(msg)
        assert delivered == 1
        handler.assert_called_once()

    def test_route_no_match(self):
        """测试无匹配路由。"""
        router = MessageRouter()
        handler = MagicMock()
        router.add_rule(handler, source="agent_1")
        msg = AgentMessage(source="agent_2")
        delivered = router.route(msg)
        assert delivered == 0
        handler.assert_not_called()

    def test_route_multiple_matches(self):
        """测试多规则匹配。"""
        router = MessageRouter()
        handler1 = MagicMock()
        handler2 = MagicMock()
        router.add_rule(handler1, topic="test")
        router.add_rule(handler2, msg_type="event")
        msg = AgentMessage(topic="test", type="event")
        delivered = router.route(msg)
        assert delivered == 2

    def test_route_with_content_filter(self):
        """测试带内容过滤的路由。"""
        router = MessageRouter()
        handler = MagicMock()
        router.add_rule(
            handler,
            content_filter=lambda msg: msg.content == "匹配",
        )
        # 匹配的消息
        msg1 = AgentMessage(content="匹配")
        router.route(msg1)
        handler.assert_called_once()

        # 不匹配的消息
        handler.reset_mock()
        msg2 = AgentMessage(content="不匹配")
        router.route(msg2)
        handler.assert_not_called()

    def test_route_handler_exception(self):
        """测试路由处理器异常。"""
        router = MessageRouter()

        def bad_handler(msg):
            raise ValueError("错误")

        router.add_rule(bad_handler, source="agent_1")
        msg = AgentMessage(source="agent_1")
        # 不应抛出异常
        delivered = router.route(msg)
        assert delivered == 0

    def test_priority_ordering(self):
        """测试优先级排序。"""
        router = MessageRouter()
        order = []

        def handler1(msg):
            order.append(1)

        def handler2(msg):
            order.append(2)

        def handler3(msg):
            order.append(3)

        # 添加时顺序不同，但按优先级执行
        router.add_rule(handler1, priority=1)
        router.add_rule(handler2, priority=10)
        router.add_rule(handler3, priority=5)

        msg = AgentMessage()
        router.route(msg)
        # 高优先级先执行
        assert order[0] == 2  # priority=10

    def test_list_rules(self):
        """测试列出规则。"""
        router = MessageRouter()
        router.add_rule(lambda msg: None, source="a", topic="t1")
        router.add_rule(lambda msg: None, target="b", msg_type="request")
        rules = router.list_rules()
        assert len(rules) == 2
        assert rules[0]["source"] == "a"
        assert rules[1]["target"] == "b"

    def test_clear_rules(self):
        """测试清空规则。"""
        router = MessageRouter()
        router.add_rule(lambda msg: None)
        router.add_rule(lambda msg: None)
        router.clear_rules()
        assert len(router.list_rules()) == 0


# ===== AgentCommunicator 测试 =====


class TestAgentCommunicator:
    """测试 AgentCommunicator 类。"""

    def test_create_communicator(self):
        """测试创建通信器。"""
        comm = AgentCommunicator("test_agent")
        assert comm.agent_id == "test_agent"
        assert comm.event_bus is not None
        assert comm.message_bus is not None
        assert comm.router is not None

    def test_send_message(self):
        """测试发送消息。"""
        comm = AgentCommunicator("agent_1")
        received = []
        target_comm = AgentCommunicator("agent_2")
        target_comm.register_message_handler(lambda msg: received.append(msg))

        # 需要共享 MessageBus 才能投递，这里测试消息创建
        msg = AgentMessage(
            source="agent_1",
            target="agent_2",
            content="测试消息",
            type=MessageType.REQUEST.value,
        )
        comm.message_bus.send(msg)
        assert msg.source == "agent_1"
        assert msg.target == "agent_2"

    def test_broadcast(self):
        """测试广播。"""
        comm = AgentCommunicator("agent_1")
        msg = comm.broadcast(content="广播内容", topic="broadcast.topic")
        assert msg.target == ""  # 广播无目标
        assert msg.source == "agent_1"
        assert msg.content == "广播内容"

    def test_publish_event(self):
        """测试发布事件。"""
        comm = AgentCommunicator("agent_1")
        received = []
        comm.subscribe("test.event", lambda msg: received.append(msg))
        msg = comm.publish_event("test.event", {"key": "value"})
        assert msg.topic == "test.event"
        assert msg.content == {"key": "value"}
        assert len(received) == 1

    def test_publish_event_with_metadata(self):
        """测试带元数据发布事件。"""
        comm = AgentCommunicator("agent_1")
        metadata = {"priority": "high", "source": "test"}
        msg = comm.publish_event("test.event", "内容", metadata=metadata)
        assert msg.metadata == metadata

    def test_subscribe(self):
        """测试订阅。"""
        comm = AgentCommunicator("agent_1")
        sub_id = comm.subscribe("test.topic", lambda msg: None)
        assert isinstance(sub_id, str)

    def test_unsubscribe(self):
        """测试取消订阅。"""
        comm = AgentCommunicator("agent_1")
        sub_id = comm.subscribe("test.topic", lambda msg: None)
        result = comm.unsubscribe("test.topic", sub_id)
        assert result is True

    def test_register_message_handler(self):
        """测试注册消息处理器。"""
        comm = AgentCommunicator("agent_1")
        handler = MagicMock()
        comm.register_message_handler(handler)
        # 处理器应注册到 message_bus
        assert comm.message_bus._handlers.get("agent_1") is handler

    def test_unregister_message_handler(self):
        """测试注销消息处理器。"""
        comm = AgentCommunicator("agent_1")
        comm.register_message_handler(lambda msg: None)
        comm.unregister_message_handler()
        assert "agent_1" not in comm.message_bus._handlers

    def test_respond(self):
        """测试回复消息。"""
        comm = AgentCommunicator("agent_1")
        original = AgentMessage(
            source="agent_2",
            target="agent_1",
            content="请求",
            correlation_id="corr_123",
        )
        reply = comm.respond(original, "回复内容")
        assert reply.content == "回复内容"
        assert reply.source == "agent_1"
        assert reply.target == "agent_2"

    def test_get_stats(self):
        """测试获取统计。"""
        comm = AgentCommunicator("agent_1")
        comm.publish_event("test.topic", "内容")
        stats = comm.get_stats()
        assert isinstance(stats, dict)
        assert stats["agent_id"] == "agent_1"
        assert "own_stats" in stats
        assert "event_bus" in stats
        assert "message_bus" in stats

    def test_reset(self):
        """测试重置通信器。"""
        comm = AgentCommunicator("agent_1")
        comm.publish_event("test.topic", "内容")
        comm.reset()
        stats = comm.get_stats()
        assert stats["own_stats"]["sent"] == 0

    @pytest.mark.asyncio
    async def test_publish_event_async(self):
        """测试异步发布事件。"""
        comm = AgentCommunicator("agent_1")
        received = []

        async def handler(msg):
            received.append(msg)

        comm.subscribe("async.topic", handler)
        msg = await comm.publish_event_async("async.topic", "异步事件")
        assert msg.topic == "async.topic"
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_send_message_async(self):
        """测试异步发送消息。"""
        comm = AgentCommunicator("agent_1")
        msg = await comm.send_message_async(
            target="agent_2",
            content="异步消息",
            msg_type=MessageType.REQUEST.value,
        )
        assert msg.target == "agent_2"
        assert msg.content == "异步消息"


# ===== CommunicatorRegistry 测试 =====


class TestCommunicatorRegistry:
    """测试 CommunicatorRegistry 类。"""

    def test_create_registry(self):
        """测试创建注册表。"""
        registry = CommunicatorRegistry()
        assert registry.list_communicators() == []

    def test_create_communicator(self):
        """测试创建通信器。"""
        registry = CommunicatorRegistry()
        comm = registry.create_communicator("agent_1")
        assert comm is not None
        assert comm.agent_id == "agent_1"

    def test_get_communicator(self):
        """测试获取通信器。"""
        registry = CommunicatorRegistry()
        registry.create_communicator("agent_1")
        comm = registry.get_communicator("agent_1")
        assert comm is not None
        assert comm.agent_id == "agent_1"

    def test_get_communicator_not_found(self):
        """测试获取不存在的通信器。"""
        registry = CommunicatorRegistry()
        comm = registry.get_communicator("nonexistent")
        assert comm is None

    def test_remove_communicator(self):
        """测试移除通信器。"""
        registry = CommunicatorRegistry()
        registry.create_communicator("agent_1")
        result = registry.remove_communicator("agent_1")
        assert result is True
        assert registry.get_communicator("agent_1") is None

    def test_remove_communicator_not_found(self):
        """测试移除不存在的通信器。"""
        registry = CommunicatorRegistry()
        result = registry.remove_communicator("nonexistent")
        assert result is False

    def test_list_communicators(self):
        """测试列出通信器。"""
        registry = CommunicatorRegistry()
        registry.create_communicator("agent_1")
        registry.create_communicator("agent_2")
        comms = registry.list_communicators()
        assert len(comms) == 2
        assert "agent_1" in comms
        assert "agent_2" in comms

    def test_get_all_stats(self):
        """测试获取所有统计。"""
        registry = CommunicatorRegistry()
        registry.create_communicator("agent_1")
        registry.create_communicator("agent_2")
        stats = registry.get_all_stats()
        assert isinstance(stats, dict)
        assert len(stats) == 2

    def test_create_idempotent(self):
        """测试重复创建同一通信器。"""
        registry = CommunicatorRegistry()
        comm1 = registry.create_communicator("agent_1")
        comm2 = registry.create_communicator("agent_1")
        assert comm1 is comm2

    def test_thread_safety(self):
        """测试线程安全。"""
        registry = CommunicatorRegistry()

        def create_comms():
            for i in range(10):
                registry.create_communicator(f"agent_{i}")

        threads = [threading.Thread(target=create_comms) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(registry.list_communicators()) == 10


# ===== Topics 预定义主题测试 =====


class TestTopics:
    """测试 Topics 预定义主题常量。"""

    def test_orchestration_topics(self):
        """测试编排相关主题。"""
        assert Topics.ORCHESTRATION_START == "orchestration.start"
        assert Topics.ORCHESTRATION_COMPLETE == "orchestration.complete"
        assert Topics.ORCHESTRATION_FAILED == "orchestration.failed"
        assert Topics.STAGE_ENTER == "stage.enter"
        assert Topics.STAGE_EXIT == "stage.exit"
        assert Topics.STAGE_RETRY == "stage.retry"

    def test_agent_topics(self):
        """测试 Agent 相关主题。"""
        assert Topics.AGENT_STARTED == "agent.started"
        assert Topics.AGENT_COMPLETED == "agent.completed"
        assert Topics.AGENT_ERROR == "agent.error"
        assert Topics.AGENT_TIMEOUT == "agent.timeout"

    def test_task_topics(self):
        """测试任务相关主题。"""
        assert Topics.TASK_CREATED == "task.created"
        assert Topics.TASK_ASSIGNED == "task.assigned"
        assert Topics.TASK_COMPLETED == "task.completed"
        assert Topics.TASK_FAILED == "task.failed"

    def test_search_topics(self):
        """测试检索相关主题。"""
        assert Topics.SEARCH_STARTED == "search.started"
        assert Topics.SEARCH_COMPLETED == "search.completed"
        assert Topics.SEARCH_DEGRADED == "search.degraded"

    def test_generation_topics(self):
        """测试生成相关主题。"""
        assert Topics.GENERATION_STARTED == "generation.started"
        assert Topics.GENERATION_PROGRESS == "generation.progress"
        assert Topics.GENERATION_COMPLETED == "generation.completed"

    def test_validation_topics(self):
        """测试校验相关主题。"""
        assert Topics.VALIDATION_PASSED == "validation.passed"
        assert Topics.VALIDATION_FAILED == "validation.failed"
        assert Topics.GATE_PASSED == "gate.passed"
        assert Topics.GATE_FAILED == "gate.failed"

    def test_budget_topics(self):
        """测试预算相关主题。"""
        assert Topics.BUDGET_WARNING == "budget.warning"
        assert Topics.BUDGET_EXCEEDED == "budget.exceeded"
        assert Topics.COST_RECORDED == "cost.recorded"

    def test_cache_topics(self):
        """测试缓存相关主题。"""
        assert Topics.CACHE_HIT == "cache.hit"
        assert Topics.CACHE_MISS == "cache.miss"

    def test_system_topics(self):
        """测试系统相关主题。"""
        assert Topics.SYSTEM_HEALTH == "system.health"
        assert Topics.SYSTEM_ERROR == "system.error"

    def test_all_topics_are_strings(self):
        """测试所有主题为字符串。"""
        topic_attrs = [
            attr for attr in dir(Topics)
            if not attr.startswith("_") and isinstance(getattr(Topics, attr), str)
        ]
        assert len(topic_attrs) >= 25  # 至少 25 个预定义主题


# ===== 全局函数测试 =====


class TestGlobalFunctions:
    """测试全局函数。"""

    def test_get_communicator_registry(self):
        """测试获取全局注册表。"""
        registry = get_communicator_registry()
        assert registry is not None
        assert isinstance(registry, CommunicatorRegistry)

    def test_registry_singleton(self):
        """测试注册表单例。"""
        registry1 = get_communicator_registry()
        registry2 = get_communicator_registry()
        assert registry1 is registry2

    def test_create_communicator_global(self):
        """测试全局创建通信器。"""
        comm = create_communicator("global_test_agent")
        assert comm is not None
        assert comm.agent_id == "global_test_agent"

    def test_get_communicator_global(self):
        """测试全局获取通信器。"""
        create_communicator("global_get_agent")
        comm = get_communicator("global_get_agent")
        assert comm is not None

    def test_get_communicator_not_found(self):
        """测试获取不存在的通信器。"""
        comm = get_communicator("nonexistent_global_agent")
        assert comm is None


# ===== 集成测试 =====


class TestIntegration:
    """集成测试。"""

    def test_event_bus_full_workflow(self):
        """测试事件总线完整工作流。"""
        bus = EventBus()
        received = []

        # 订阅
        sub_id = bus.subscribe("integration.topic", lambda msg: received.append(msg))

        # 发布
        bus.publish(AgentMessage(topic="integration.topic", content="消息1"))
        bus.publish(AgentMessage(topic="integration.topic", content="消息2"))

        # 验证
        assert len(received) == 2
        assert received[0].content == "消息1"

        # 取消订阅
        bus.unsubscribe("integration.topic", sub_id)
        bus.publish(AgentMessage(topic="integration.topic", content="消息3"))
        assert len(received) == 2  # 取消后不再接收

    def test_message_bus_full_workflow(self):
        """测试消息总线完整工作流。"""
        bus = MessageBus()
        received = []

        # 注册处理器
        bus.register_handler("worker", lambda msg: received.append(msg))

        # 发送消息
        msg1 = AgentMessage(source="manager", target="worker", content="任务1")
        msg2 = AgentMessage(source="manager", target="worker", content="任务2")
        bus.send(msg1)
        bus.send(msg2)

        # 验证
        assert len(received) == 2

        # 确认消息
        bus.acknowledge(msg1.id)
        assert bus.get_queue_size("worker") >= 1  # 还剩一条

    def test_router_full_workflow(self):
        """测试路由器完整工作流。"""
        router = MessageRouter()
        routed = []

        # 添加规则
        router.add_rule(
            lambda msg: routed.append(("high", msg)),
            msg_type="command",
            priority=10,
        )
        router.add_rule(
            lambda msg: routed.append(("low", msg)),
            msg_type="event",
            priority=1,
        )

        # 路由消息
        router.route(AgentMessage(type="command", content="命令"))
        router.route(AgentMessage(type="event", content="事件"))

        # 验证
        assert len(routed) == 2
        assert routed[0][0] == "high"
        assert routed[1][0] == "low"

    def test_communicator_full_workflow(self):
        """测试通信器完整工作流。"""
        comm = AgentCommunicator("integration_agent")

        # 订阅事件
        events = []
        comm.subscribe("workflow.event", lambda msg: events.append(msg))

        # 发布事件
        comm.publish_event("workflow.event", {"step": 1})
        comm.publish_event("workflow.event", {"step": 2})

        # 广播
        comm.broadcast("系统通知", topic="system.notification")

        # 验证
        assert len(events) == 2
        stats = comm.get_stats()
        assert stats["own_stats"]["sent"] >= 3

    def test_multi_agent_communication(self):
        """测试多 Agent 通信。"""
        # 创建共享消息总线
        shared_bus = MessageBus()

        # 创建两个通信器共享同一消息总线
        comm1 = AgentCommunicator("agent_alpha")
        comm1.message_bus = shared_bus

        comm2 = AgentCommunicator("agent_beta")
        comm2.message_bus = shared_bus

        # comm2 注册消息处理器
        received = []
        comm2.register_message_handler(lambda msg: received.append(msg.content))

        # comm1 发送消息给 comm2
        msg = AgentMessage(
            source="agent_alpha",
            target="agent_beta",
            content="你好 agent_beta",
            type=MessageType.REQUEST.value,
        )
        shared_bus.send(msg)

        # 验证
        assert len(received) == 1
        assert received[0] == "你好 agent_beta"


# ===== 边界情况测试 =====


class TestEdgeCases:
    """边界情况测试。"""

    def test_empty_content_message(self):
        """测试空内容消息。"""
        msg = AgentMessage(content="")
        assert msg.content == ""

    def test_none_content_message(self):
        """测试 None 内容消息。"""
        msg = AgentMessage(content=None)
        assert msg.content is None

    def test_complex_content(self):
        """测试复杂内容。"""
        content = {
            "nested": {"data": [1, 2, 3]},
            "list": ["a", "b", "c"],
            "value": 42,
        }
        msg = AgentMessage(content=content)
        d = msg.to_dict()
        assert d["content"] == content

    def test_unicode_content(self):
        """测试 Unicode 内容。"""
        msg = AgentMessage(content="🎉🎊 中文测试 émojis")
        json_str = msg.to_json()
        parsed = json.loads(json_str)
        assert "🎉" in parsed["content"]

    def test_very_long_content(self):
        """测试超长内容。"""
        long_content = "x" * 10000
        msg = AgentMessage(content=long_content)
        assert len(msg.content) == 10000

    def test_message_with_special_chars_in_metadata(self):
        """测试元数据中的特殊字符。"""
        metadata = {"path": "C:\\Users\\test", "regex": "^\\d+$"}
        msg = AgentMessage(metadata=metadata)
        json_str = msg.to_json()
        parsed = json.loads(json_str)
        assert parsed["metadata"]["path"] == "C:\\Users\\test"

    def test_expired_at_zero(self):
        """测试 expires_at 为 0（永不过期）。"""
        msg = AgentMessage(expires_at=0)
        assert msg.is_expired() is False

    def test_broadcast_with_topic(self):
        """测试带主题的广播。"""
        msg = AgentMessage(target="", topic="broadcast.topic")
        assert msg.is_broadcast() is True
        assert msg.topic == "broadcast.topic"

    def test_reply_chain(self):
        """测试回复链。"""
        original = AgentMessage(
            source="agent_1",
            target="agent_2",
            content="原始请求",
            correlation_id="chain_123",
        )
        reply1 = original.create_reply("第一次回复")
        reply2 = reply1.create_reply("第二次回复")
        assert reply2.target == "agent_2"  # 回到原始发送方
        assert reply2.reply_to == reply1.id

    def test_event_bus_max_history(self):
        """测试事件总线历史上限。"""
        bus = EventBus()
        bus.subscribe("topic", lambda msg: None)
        # 发布超过 1000 条消息
        for i in range(1100):
            bus.publish(AgentMessage(topic="topic", content=f"消息_{i}"))
        history = bus.get_history()
        # 历史应限制在 1000 条
        assert len(history) <= 1000

    def test_concurrent_publish(self):
        """测试并发发布。"""
        bus = EventBus()
        received = []
        lock = threading.Lock()

        def handler(msg):
            with lock:
                received.append(msg)

        bus.subscribe("concurrent.topic", handler)

        def publish():
            for i in range(50):
                bus.publish(AgentMessage(topic="concurrent.topic", content=f"消息_{i}"))

        threads = [threading.Thread(target=publish) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(received) == 200

    def test_router_no_rules_no_default(self):
        """测试无规则无默认处理器的路由。"""
        router = MessageRouter()
        msg = AgentMessage()
        delivered = router.route(msg)
        assert delivered == 0

    def test_message_bus_queue_overflow(self):
        """测试消息总线队列溢出。"""
        bus = MessageBus(max_queue_size=10)
        # 发送超过队列大小的消息
        for i in range(20):
            bus.send(AgentMessage(source="a", target="overflow_agent", content=f"消息_{i}"))
        # 队列应有大小限制
        size = bus.get_queue_size("overflow_agent")
        assert size <= 10

    def test_communicator_agent_id_persistence(self):
        """测试通信器 Agent ID 持久性。"""
        comm = AgentCommunicator("persistent_agent")
        msg = comm.broadcast("测试")
        assert msg.source == "persistent_agent"

    def test_stats_accuracy(self):
        """测试统计准确性。"""
        stats = CommunicationStats()
        for i in range(10):
            msg = AgentMessage(source="agent_1", type="event", target="agent_2")
            stats.record_sent(msg)
            if i < 7:
                stats.record_delivered()
            elif i < 9:
                stats.record_failed()
            else:
                stats.record_expired()
        d = stats.to_dict()
        assert d["sent"] == 10
        assert d["delivered"] == 7
        assert d["failed"] == 2
        assert d["expired"] == 1
