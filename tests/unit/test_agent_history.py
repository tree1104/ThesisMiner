"""单元测试：Agent 历史持久化（Task 5 / v9.0）

测试 backend/database.py 中新增的 agent_messages 表 CRUD 函数，
以及 backend/agents/base_agent.py 与 backend/agents/agent_context.py
中新增的历史持久化与恢复能力。

覆盖范围：
  - save_agent_message：保存消息并验证入库
  - load_agent_history：保存多条消息并加载
  - load_all_agent_histories：多 Agent 消息分组加载
  - delete_agent_history：保存后删除
  - BaseAgent.save_message / load_history / get_history
  - ContextManager.restore_from_db / clear_cache 上下文恢复
  - 跨"重启"（新建 Agent 实例）历史持久化验证
"""
import asyncio
import os
import sys
import tempfile
import uuid

import pytest

# ===== 项目根目录加入 sys.path =====
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ===== 临时数据库初始化（在导入 backend.database 前覆盖 DB_PATH） =====
_TMP_DIR = tempfile.mkdtemp(prefix="thesisminer_agent_history_test_")
import backend.database as _db
_db.DB_PATH = os.path.join(_TMP_DIR, "test_agent_history.db")
_db.init_db()

from backend.agents.base_agent import AgentResult, BaseAgent
from backend.agents.agent_context import ContextManager, Message
from backend.database import (
    delete_agent_history,
    fetch_all,
    fetch_one,
    load_agent_history,
    load_all_agent_histories,
    save_agent_message,
)


# ===== 测试用具体 Agent 实现 =====


class HistoryTestAgent(BaseAgent):
    """用于历史持久化测试的具体 Agent 实现"""

    def __init__(self, agent_id="history-test-agent", system_prompt="你是测试 Agent"):
        super().__init__(
            agent_id=agent_id,
            name="HistoryTestAgent",
            description="历史持久化测试 Agent",
            system_prompt=system_prompt,
            model_id="test-model",
            temperature=0.5,
            max_tokens=2048,
            capabilities=["thinking"],
        )

    async def run(self, task_input: dict) -> AgentResult:
        return AgentResult(agent_id=self.agent_id, success=True)


# ===== save_agent_message 测试 =====


class TestSaveAgentMessage:
    """save_agent_message 函数测试"""

    def test_save_returns_message_id(self):
        """保存消息应返回非空的消息 ID"""
        msg_id = save_agent_message(
            agent_id="test-agent",
            role="user",
            content="测试消息内容",
        )
        assert msg_id is not None
        assert isinstance(msg_id, str)
        assert len(msg_id) > 0

    def test_save_persists_to_database(self):
        """保存的消息应能在数据库中查到"""
        msg_id = save_agent_message(
            agent_id="persist-test",
            role="user",
            content="持久化验证内容",
        )
        row = fetch_one(
            "SELECT * FROM agent_messages WHERE id = ?;", (msg_id,)
        )
        assert row is not None
        assert row["agent_id"] == "persist-test"
        assert row["role"] == "user"
        assert row["content"] == "持久化验证内容"

    def test_save_with_all_fields(self):
        """保存包含所有字段的消息应正确入库"""
        citations = [{"url": "https://example.com", "title": "示例"}]
        metadata = {"stage": "creativity", "score": 85}
        msg_id = save_agent_message(
            agent_id="full-field-agent",
            role="assistant",
            content="完整字段回复",
            conversation_id="conv-123",
            session_id="sess-456",
            reasoning="这是推理过程",
            citations=citations,
            metadata=metadata,
        )
        row = fetch_one(
            "SELECT * FROM agent_messages WHERE id = ?;", (msg_id,)
        )
        assert row is not None
        assert row["conversation_id"] == "conv-123"
        assert row["session_id"] == "sess-456"
        assert row["reasoning"] == "这是推理过程"
        # citations / metadata 以 JSON 字符串存储
        import json
        assert json.loads(row["citations"]) == citations
        assert json.loads(row["metadata"]) == metadata

    def test_save_generates_unique_ids(self):
        """多次保存应生成不同的消息 ID"""
        id1 = save_agent_message("uniq-agent", "user", "消息1")
        id2 = save_agent_message("uniq-agent", "user", "消息2")
        assert id1 != id2

    def test_save_timestamps_present(self):
        """保存的消息应包含 created_at 与 updated_at"""
        msg_id = save_agent_message("ts-agent", "user", "时间戳测试")
        row = fetch_one(
            "SELECT created_at, updated_at FROM agent_messages WHERE id = ?;",
            (msg_id,),
        )
        assert row is not None
        assert row["created_at"] is not None
        assert row["updated_at"] is not None
        assert len(row["created_at"]) > 0


# ===== load_agent_history 测试 =====


class TestLoadAgentHistory:
    """load_agent_history 函数测试"""

    def test_load_returns_list(self):
        """加载历史应返回列表"""
        save_agent_message("load-list-agent", "user", "消息")
        history = load_agent_history("load-list-agent")
        assert isinstance(history, list)

    def test_load_multiple_messages(self):
        """保存多条消息后应能全部加载"""
        agent_id = "multi-load-agent"
        for i in range(5):
            save_agent_message(agent_id, "user", f"消息{i}")
        history = load_agent_history(agent_id)
        assert len(history) == 5
        # 验证内容
        contents = [m["content"] for m in history]
        for i in range(5):
            assert f"消息{i}" in contents

    def test_load_ordered_by_created_at(self):
        """加载的历史应按 created_at 升序排列"""
        agent_id = "order-agent"
        ids = []
        for i in range(3):
            mid = save_agent_message(agent_id, "user", f"序号{i}")
            ids.append(mid)
        history = load_agent_history(agent_id)
        # 验证顺序与保存顺序一致
        for i, msg in enumerate(history):
            assert msg["content"] == f"序号{i}"

    def test_load_filter_by_conversation_id(self):
        """应能按 conversation_id 过滤历史"""
        agent_id = "conv-filter-agent"
        save_agent_message(agent_id, "user", "对话A消息1", conversation_id="conv-a")
        save_agent_message(agent_id, "user", "对话A消息2", conversation_id="conv-a")
        save_agent_message(agent_id, "user", "对话B消息1", conversation_id="conv-b")

        history_a = load_agent_history(agent_id, conversation_id="conv-a")
        history_b = load_agent_history(agent_id, conversation_id="conv-b")
        assert len(history_a) == 2
        assert len(history_b) == 1
        assert all(m["conversation_id"] == "conv-a" for m in history_a)
        assert all(m["conversation_id"] == "conv-b" for m in history_b)

    def test_load_filter_by_session_id(self):
        """应能按 session_id 过滤历史"""
        agent_id = "session-filter-agent"
        save_agent_message(agent_id, "user", "会话1消息", session_id="sess-1")
        save_agent_message(agent_id, "user", "会话2消息", session_id="sess-2")

        history = load_agent_history(agent_id, session_id="sess-1")
        assert len(history) == 1
        assert history[0]["session_id"] == "sess-1"
        assert history[0]["content"] == "会话1消息"

    def test_load_with_limit(self):
        """limit 参数应限制返回数量"""
        agent_id = "limit-agent"
        for i in range(10):
            save_agent_message(agent_id, "user", f"消息{i}")
        history = load_agent_history(agent_id, limit=3)
        assert len(history) == 3

    def test_load_empty_for_unknown_agent(self):
        """未知 Agent 加载历史应返回空列表"""
        history = load_agent_history("nonexistent-agent-xyz")
        assert history == []

    def test_load_deserializes_citations_and_metadata(self):
        """加载时应反序列化 citations 与 metadata 字段"""
        agent_id = "deserialize-agent"
        citations = [{"url": "https://a.com"}]
        metadata = {"key": "value"}
        save_agent_message(
            agent_id, "assistant", "带引用的回复",
            citations=citations, metadata=metadata,
        )
        history = load_agent_history(agent_id)
        assert len(history) == 1
        assert history[0]["citations"] == citations
        assert history[0]["metadata"] == metadata


# ===== load_all_agent_histories 测试 =====


class TestLoadAllAgentHistories:
    """load_all_agent_histories 函数测试"""

    def test_load_all_returns_dict(self):
        """加载全部历史应返回字典"""
        result = load_all_agent_histories()
        assert isinstance(result, dict)

    def test_load_all_groups_by_agent_id(self):
        """应按 agent_id 分组返回历史"""
        save_agent_message("group-a", "user", "A的消息1")
        save_agent_message("group-a", "user", "A的消息2")
        save_agent_message("group-b", "user", "B的消息1")

        result = load_all_agent_histories()
        assert "group-a" in result
        assert "group-b" in result
        assert len(result["group-a"]) == 2
        assert len(result["group-b"]) == 1

    def test_load_all_empty_database(self):
        """清空后加载应不包含测试 Agent（可能有其他测试残留，仅验证结构）"""
        # 删除本测试专用 agent 的数据
        delete_agent_history("empty-test-agent")
        result = load_all_agent_histories()
        assert "empty-test-agent" not in result


# ===== delete_agent_history 测试 =====


class TestDeleteAgentHistory:
    """delete_agent_history 函数测试"""

    def test_delete_returns_count(self):
        """删除应返回被删除的行数"""
        agent_id = "delete-count-agent"
        save_agent_message(agent_id, "user", "消息1")
        save_agent_message(agent_id, "user", "消息2")
        count = delete_agent_history(agent_id)
        assert count == 2

    def test_delete_removes_all_messages(self):
        """删除后该 Agent 的历史应为空"""
        agent_id = "delete-all-agent"
        save_agent_message(agent_id, "user", "待删除")
        delete_agent_history(agent_id)
        history = load_agent_history(agent_id)
        assert history == []

    def test_delete_by_conversation_id(self):
        """应能仅删除指定对话的消息"""
        agent_id = "delete-conv-agent"
        save_agent_message(agent_id, "user", "对话A", conversation_id="conv-a")
        save_agent_message(agent_id, "user", "对话B", conversation_id="conv-b")

        count = delete_agent_history(agent_id, conversation_id="conv-a")
        assert count == 1
        # 对话B 的消息应保留
        history = load_agent_history(agent_id)
        assert len(history) == 1
        assert history[0]["conversation_id"] == "conv-b"

    def test_delete_nonexistent_returns_zero(self):
        """删除不存在的 Agent 历史应返回 0"""
        count = delete_agent_history("nonexistent-delete-agent")
        assert count == 0


# ===== BaseAgent 持久化方法测试 =====


class TestBaseAgentPersistence:
    """BaseAgent.save_message / load_history / get_history 测试"""

    def test_save_message_returns_id(self):
        """BaseAgent.save_message 应返回消息 ID"""
        agent = HistoryTestAgent(agent_id="base-save-agent")
        msg_id = agent.save_message("user", "测试保存")
        assert msg_id is not None
        assert isinstance(msg_id, str)

    def test_save_message_persists_to_db(self):
        """BaseAgent.save_message 应将消息写入数据库"""
        agent = HistoryTestAgent(agent_id="base-persist-agent")
        msg_id = agent.save_message("user", "持久化测试内容")
        row = fetch_one(
            "SELECT * FROM agent_messages WHERE id = ?;", (msg_id,)
        )
        assert row is not None
        assert row["agent_id"] == "base-persist-agent"
        assert row["content"] == "持久化测试内容"

    def test_save_message_adds_to_memory(self):
        """BaseAgent.save_message 应同步追加到内存上下文"""
        agent = HistoryTestAgent(agent_id="base-memory-agent")
        initial_len = len(agent.messages)
        agent.save_message("user", "内存同步测试")
        assert len(agent.messages) == initial_len + 1
        assert agent.messages[-1]["content"] == "内存同步测试"

    def test_save_message_with_citations(self):
        """BaseAgent.save_message 应正确保存 citations"""
        agent = HistoryTestAgent(agent_id="base-cite-agent")
        citations = [{"url": "https://example.com", "title": "示例引用"}]
        msg_id = agent.save_message(
            "assistant", "带引用的回复", citations=citations
        )
        history = load_agent_history("base-cite-agent")
        assert len(history) == 1
        assert history[0]["citations"] == citations

    def test_load_history_rebuilds_memory(self):
        """BaseAgent.load_history 应从数据库重建内存上下文"""
        agent_id = "base-rebuild-agent"
        # 先保存几条消息
        agent1 = HistoryTestAgent(agent_id=agent_id)
        agent1.save_message("user", "用户消息1")
        agent1.save_message("assistant", "助手回复1")

        # 新建 Agent 实例（模拟重启），内存上下文仅有系统提示
        agent2 = HistoryTestAgent(agent_id=agent_id)
        assert len(agent2.messages) == 1  # 仅系统提示

        # 加载历史后应重建内存上下文
        rows = agent2.load_history()
        assert len(rows) == 2
        # 内存上下文：系统提示 + 2 条历史消息
        assert len(agent2.messages) == 3
        assert agent2.messages[0]["role"] == "system"
        assert agent2.messages[1]["content"] == "用户消息1"
        assert agent2.messages[2]["content"] == "助手回复1"

    def test_get_history_loads_if_empty(self):
        """get_history 在内存为空时应自动从数据库加载"""
        agent_id = "base-auto-load-agent"
        # 先保存消息
        save_agent_message(agent_id, "user", "自动加载测试")

        # 新建 Agent，内存仅有系统提示
        agent = HistoryTestAgent(agent_id=agent_id)
        history = agent.get_history()
        # 应触发自动加载，返回系统提示 + 历史消息
        assert len(history) >= 2
        assert history[0]["role"] == "system"

    def test_get_history_returns_copy(self):
        """get_history 应返回副本，修改不影响原始"""
        agent = HistoryTestAgent(agent_id="base-copy-agent")
        agent.save_message("user", "副本测试")
        history = agent.get_history()
        history.append({"role": "user", "content": "注入"})
        # 原始不受影响
        assert len(agent.messages) == len(history) - 1

    def test_save_message_with_conversation_id(self):
        """BaseAgent.save_message 应正确关联 conversation_id"""
        agent = HistoryTestAgent(agent_id="base-conv-agent")
        agent.save_message(
            "user", "带对话ID的消息", conversation_id="test-conv-123"
        )
        history = load_agent_history("base-conv-agent", conversation_id="test-conv-123")
        assert len(history) == 1
        assert history[0]["conversation_id"] == "test-conv-123"


# ===== ContextManager 恢复测试 =====


class TestContextManagerRestore:
    """ContextManager.restore_from_db / clear_cache 测试"""

    def test_restore_from_db_returns_messages(self):
        """restore_from_db 应返回恢复的消息列表"""
        agent_id = "ctx-restore-agent"
        # 先向数据库写入消息
        save_agent_message(agent_id, "user", "上下文恢复消息1")
        save_agent_message(agent_id, "assistant", "上下文恢复消息2")

        ctx = ContextManager(agent_id=agent_id)
        restored = ctx.restore_from_db()
        assert isinstance(restored, list)
        assert len(restored) == 2
        contents = [m["content"] for m in restored]
        assert "上下文恢复消息1" in contents
        assert "上下文恢复消息2" in contents

    def test_restore_rebuilds_window_and_history(self):
        """restore_from_db 应重建窗口与历史"""
        agent_id = "ctx-rebuild-agent"
        save_agent_message(agent_id, "user", "重建消息1")
        save_agent_message(agent_id, "assistant", "重建消息2")

        ctx = ContextManager(agent_id=agent_id)
        ctx.restore_from_db()
        # 窗口应包含恢复的消息
        messages = ctx.get_messages()
        assert len(messages) >= 2
        # 历史也应包含
        assert ctx.history.count() >= 2

    def test_clear_cache_empties_context(self):
        """clear_cache 应清空内存上下文"""
        agent_id = "ctx-clear-agent"
        save_agent_message(agent_id, "user", "待清除消息")

        ctx = ContextManager(agent_id=agent_id)
        ctx.restore_from_db()
        assert len(ctx.get_messages()) >= 1

        ctx.clear_cache()
        # 清空后窗口应为空
        messages = ctx.get_messages()
        assert len(messages) == 0
        assert ctx.history.count() == 0

    def test_clear_cache_does_not_delete_db(self):
        """clear_cache 不应删除数据库中的记录"""
        agent_id = "ctx-clear-db-agent"
        save_agent_message(agent_id, "user", "数据库保留测试")

        ctx = ContextManager(agent_id=agent_id)
        ctx.restore_from_db()
        ctx.clear_cache()

        # 数据库中仍应有记录
        db_history = load_agent_history(agent_id)
        assert len(db_history) == 1

    def test_restore_after_clear(self):
        """清除缓存后应能再次从数据库恢复"""
        agent_id = "ctx-restore-after-clear-agent"
        save_agent_message(agent_id, "user", "恢复验证消息")

        ctx = ContextManager(agent_id=agent_id)
        ctx.restore_from_db()
        assert len(ctx.get_messages()) >= 1

        ctx.clear_cache()
        assert len(ctx.get_messages()) == 0

        # 再次恢复
        ctx.restore_from_db()
        assert len(ctx.get_messages()) >= 1

    def test_restore_empty_history(self):
        """恢复无历史的 Agent 应返回空列表"""
        ctx = ContextManager(agent_id="ctx-empty-restore-agent")
        restored = ctx.restore_from_db()
        assert restored == []


# ===== 跨"重启"持久化测试 =====


class TestHistoryPersistsAcrossRestart:
    """验证历史在 Agent 实例重建后仍可恢复（模拟重启）"""

    def test_history_survives_new_instance(self):
        """新建 Agent 实例后应能加载之前保存的历史"""
        agent_id = "restart-persist-agent"
        # 第一个实例保存消息
        agent1 = HistoryTestAgent(agent_id=agent_id)
        agent1.save_message("user", "重启前的消息1")
        agent1.save_message("assistant", "重启前的回复1")

        # 模拟重启：新建第二个实例
        agent2 = HistoryTestAgent(agent_id=agent_id)
        # 内存上下文仅有系统提示
        assert len(agent2.messages) == 1

        # 加载历史
        history = agent2.load_history()
        assert len(history) == 2
        # 验证内容正确恢复
        contents = [m["content"] for m in history]
        assert "重启前的消息1" in contents
        assert "重启前的回复1" in contents

    def test_history_survives_with_conversation_id(self):
        """带 conversation_id 的历史在重启后应能按对话恢复"""
        agent_id = "restart-conv-agent"
        conv_id = "restart-conv-001"

        agent1 = HistoryTestAgent(agent_id=agent_id)
        agent1.save_message("user", "对话内消息", conversation_id=conv_id)
        agent1.save_message("user", "对话外消息", conversation_id="other-conv")

        # 模拟重启
        agent2 = HistoryTestAgent(agent_id=agent_id)
        history = agent2.load_history(conversation_id=conv_id)
        assert len(history) == 1
        assert history[0]["content"] == "对话内消息"
        assert history[0]["conversation_id"] == conv_id

    def test_multiple_agents_isolated_history(self):
        """多个 Agent 的历史应相互隔离"""
        agent_id_a = "restart-iso-agent-a"
        agent_id_b = "restart-iso-agent-b"

        agent_a = HistoryTestAgent(agent_id=agent_id_a)
        agent_b = HistoryTestAgent(agent_id=agent_id_b)
        agent_a.save_message("user", "Agent A 的消息")
        agent_b.save_message("user", "Agent B 的消息")

        # 模拟重启后各自加载
        new_a = HistoryTestAgent(agent_id=agent_id_a)
        new_b = HistoryTestAgent(agent_id=agent_id_b)
        history_a = new_a.load_history()
        history_b = new_b.load_history()

        assert len(history_a) == 1
        assert len(history_b) == 1
        assert history_a[0]["content"] == "Agent A 的消息"
        assert history_b[0]["content"] == "Agent B 的消息"

    def test_restore_all_histories_function(self):
        """restore_all_histories 应返回各 Agent 的恢复计数"""
        from backend.agents.agent_registry import restore_all_histories

        # 准备数据
        save_agent_message("restore-all-agent-1", "user", "消息1")
        save_agent_message("restore-all-agent-1", "user", "消息2")
        save_agent_message("restore-all-agent-2", "user", "消息3")

        result = restore_all_histories()
        assert isinstance(result, dict)
        assert result.get("restore-all-agent-1") == 2
        assert result.get("restore-all-agent-2") == 1
