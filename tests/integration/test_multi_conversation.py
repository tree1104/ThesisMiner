"""集成测试：多对话管理验证

覆盖：
- 同一会话下多个对话并存
- 对话之间的上下文隔离
- 对话切换
- 消息路由到特定 Agent
- 使用真实 DB

运行方式：python -m pytest tests/integration/test_multi_conversation.py -v
"""
import os
import sys
import tempfile

import pytest

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 切换到临时数据库
import backend.database as _db

_tmp_dir = tempfile.mkdtemp(prefix="thesisminer_multi_conv_")
_tmp_db = os.path.join(_tmp_dir, "test_multi_conv.db")
_db.DB_PATH = _tmp_db
_db.init_db()

from backend.sessions.conversation_manager import (
    ConversationManager,
    get_conversation_manager,
)
from backend.sessions import session_manager
from backend.models import SessionCreate, DegreeType, DisciplineType


# ===== 辅助函数 =====

def _make_session(title: str = "多对话测试会话") -> str:
    """创建测试会话，返回 session_id"""
    req = SessionCreate(
        title=title,
        degree=DegreeType.master,
        discipline=DisciplineType.science_engineering,
        mentor_info="测试导师",
    )
    session = session_manager.create_session(req)
    return session["id"]


def _make_conversation(session_id: str, title: str = "测试对话", agent_id: str = "orchestrator") -> str:
    """创建测试对话，返回 conversation_id"""
    cm = get_conversation_manager()
    conv = cm.create_conversation(session_id, title=title, agent_id=agent_id)
    return conv["id"]


def _add_message(conv_id: str, role: str = "user", content: str = "测试消息",
                 agent_id: str = "", citations: list = None) -> str:
    """添加消息到对话，返回 message_id"""
    cm = get_conversation_manager()
    msg = cm.add_message(
        conv_id, role, content, agent_id=agent_id,
        citations=citations or [],
    )
    return msg["id"]


# ===== 多对话创建测试 =====

class TestMultipleConversationCreation:
    """多对话创建测试"""

    def test_create_multiple_conversations_in_session(self):
        """在同一会话下创建多个对话"""
        sid = _make_session("多对话创建测试")
        cm = get_conversation_manager()

        conv1 = cm.create_conversation(sid, title="对话1", agent_id="orchestrator")
        conv2 = cm.create_conversation(sid, title="对话2", agent_id="reasoner")
        conv3 = cm.create_conversation(sid, title="对话3", agent_id="critic")

        convs = cm.list_conversations(sid)
        # 默认对话 + 3个新对话 = 4
        assert len(convs) >= 4

        titles = [c["title"] for c in convs]
        assert "对话1" in titles
        assert "对话2" in titles
        assert "对话3" in titles

    def test_each_conversation_has_unique_id(self):
        """每个对话应有唯一 ID"""
        sid = _make_session("唯一ID测试")
        cm = get_conversation_manager()

        conv1 = cm.create_conversation(sid, title="对话A")
        conv2 = cm.create_conversation(sid, title="对话B")
        conv3 = cm.create_conversation(sid, title="对话C")

        assert conv1["id"] != conv2["id"]
        assert conv2["id"] != conv3["id"]
        assert conv1["id"] != conv3["id"]

    def test_conversation_has_correct_agent_id(self):
        """对话应记录正确的 agent_id"""
        sid = _make_session("Agent ID测试")
        cm = get_conversation_manager()

        for agent_id in ["orchestrator", "reasoner", "critic", "writer", "searcher", "mentor"]:
            conv = cm.create_conversation(sid, title=f"对话_{agent_id}", agent_id=agent_id)
            assert conv["agent_id"] == agent_id

    def test_conversation_default_status_active(self):
        """对话默认状态应为 active"""
        sid = _make_session("状态测试")
        cm = get_conversation_manager()
        conv = cm.create_conversation(sid, title="状态测试对话")
        assert conv["status"] == "active"

    def test_conversation_message_count_starts_zero(self):
        """新对话的消息数应为0"""
        sid = _make_session("消息计数测试")
        cm = get_conversation_manager()
        conv = cm.create_conversation(sid, title="计数测试")
        assert conv["message_count"] == 0


# ===== 上下文隔离测试 =====

class TestContextIsolation:
    """对话间上下文隔离测试"""

    def test_messages_isolated_between_conversations(self):
        """不同对话的消息应相互隔离"""
        sid = _make_session("隔离测试")
        cm = get_conversation_manager()

        conv1 = cm.create_conversation(sid, title="对话1")
        conv2 = cm.create_conversation(sid, title="对话2")

        # 在 conv1 添加消息
        cm.add_message(conv1["id"], "user", "对话1的消息")
        cm.add_message(conv1["id"], "assistant", "对话1的回复")

        # 在 conv2 添加消息
        cm.add_message(conv2["id"], "user", "对话2的消息")

        # 验证隔离
        msgs1 = cm.get_messages(conv1["id"])
        msgs2 = cm.get_messages(conv2["id"])

        assert len(msgs1) == 2
        assert len(msgs2) == 1
        assert msgs1[0]["content"] == "对话1的消息"
        assert msgs2[0]["content"] == "对话2的消息"

    def test_message_count_independent(self):
        """对话的消息计数应独立"""
        sid = _make_session("计数独立测试")
        cm = get_conversation_manager()

        conv1 = cm.create_conversation(sid, title="对话1")
        conv2 = cm.create_conversation(sid, title="对话2")

        # 只在 conv1 添加消息
        for i in range(5):
            cm.add_message(conv1["id"], "user", f"消息{i}")

        conv1_updated = cm.get_conversation(conv1["id"])
        conv2_updated = cm.get_conversation(conv2["id"])

        assert conv1_updated["message_count"] == 5
        assert conv2_updated["message_count"] == 0

    def test_citations_isolated_between_conversations(self):
        """不同对话的引用应相互隔离"""
        sid = _make_session("引用隔离测试")
        cm = get_conversation_manager()

        conv1 = cm.create_conversation(sid, title="对话1")
        conv2 = cm.create_conversation(sid, title="对话2")

        # 在 conv1 添加带引用的消息
        msg1 = cm.add_message(
            conv1["id"], "assistant", "带引用的回复",
            agent_id="searcher",
            citations=[{"url": "https://example.com/1", "title": "引用1"}],
        )

        # 在 conv2 添加不带引用的消息
        msg2 = cm.add_message(
            conv2["id"], "assistant", "不带引用的回复",
            agent_id="reasoner",
        )

        cites1 = cm.get_message_citations(msg1["id"])
        cites2 = cm.get_message_citations(msg2["id"])

        assert len(cites1) == 1
        assert len(cites2) == 0

    def test_context_window_isolated(self):
        """上下文窗口应按对话隔离"""
        sid = _make_session("上下文窗口测试")
        cm = get_conversation_manager()

        conv1 = cm.create_conversation(sid, title="对话1")
        conv2 = cm.create_conversation(sid, title="对话2")

        # conv1 添加多条消息
        for i in range(10):
            cm.add_message(conv1["id"], "user" if i % 2 == 0 else "assistant", f"消息{i}")

        # conv2 添加少量消息
        cm.add_message(conv2["id"], "user", "对话2唯一消息")

        ctx1 = cm.get_context_window(conv1["id"], max_tokens=8000)
        ctx2 = cm.get_context_window(conv2["id"], max_tokens=8000)

        assert len(ctx1) == 10
        assert len(ctx2) == 1
        assert ctx2[0]["content"] == "对话2唯一消息"


# ===== 对话切换测试 =====

class TestConversationSwitching:
    """对话切换测试"""

    def test_set_active_conversation(self):
        """设置激活对话"""
        sid = _make_session("激活对话测试")
        cm = get_conversation_manager()

        conv1 = cm.create_conversation(sid, title="对话1")
        conv2 = cm.create_conversation(sid, title="对话2")

        # 设置 conv2 为激活
        result = cm.set_active(sid, conv2["id"])
        assert result is True

        # 验证 session 的 active_conversation_id
        session = session_manager.get_session(sid)
        assert session["active_conversation_id"] == conv2["id"]

    def test_switch_active_conversation_multiple_times(self):
        """多次切换激活对话"""
        sid = _make_session("多次切换测试")
        cm = get_conversation_manager()

        conv1 = cm.create_conversation(sid, title="对话1")
        conv2 = cm.create_conversation(sid, title="对话2")
        conv3 = cm.create_conversation(sid, title="对话3")

        # 依次切换
        cm.set_active(sid, conv1["id"])
        session = session_manager.get_session(sid)
        assert session["active_conversation_id"] == conv1["id"]

        cm.set_active(sid, conv2["id"])
        session = session_manager.get_session(sid)
        assert session["active_conversation_id"] == conv2["id"]

        cm.set_active(sid, conv3["id"])
        session = session_manager.get_session(sid)
        assert session["active_conversation_id"] == conv3["id"]

    def test_switch_preserves_message_history(self):
        """切换对话不应影响各对话的消息历史"""
        sid = _make_session("切换保留历史测试")
        cm = get_conversation_manager()

        conv1 = cm.create_conversation(sid, title="对话1")
        conv2 = cm.create_conversation(sid, title="对话2")

        # 各自添加消息
        cm.add_message(conv1["id"], "user", "对话1消息1")
        cm.add_message(conv1["id"], "assistant", "对话1回复1")
        cm.add_message(conv2["id"], "user", "对话2消息1")

        # 切换到 conv1
        cm.set_active(sid, conv1["id"])
        msgs1 = cm.get_messages(conv1["id"])
        assert len(msgs1) == 2

        # 切换到 conv2
        cm.set_active(sid, conv2["id"])
        msgs2 = cm.get_messages(conv2["id"])
        assert len(msgs2) == 1

        # 切回 conv1，消息应仍在
        cm.set_active(sid, conv1["id"])
        msgs1_again = cm.get_messages(conv1["id"])
        assert len(msgs1_again) == 2


# ===== 消息路由测试 =====

class TestMessageRouting:
    """消息路由到特定 Agent 测试"""

    def test_message_records_agent_id(self):
        """消息应记录产生它的 agent_id"""
        sid = _make_session("消息路由测试")
        cm = get_conversation_manager()
        conv = cm.create_conversation(sid, title="路由测试")

        # 不同 Agent 的消息
        msg1 = cm.add_message(conv["id"], "assistant", "Orchestrator回复", agent_id="orchestrator")
        msg2 = cm.add_message(conv["id"], "assistant", "Reasoner回复", agent_id="reasoner")
        msg3 = cm.add_message(conv["id"], "assistant", "Critic回复", agent_id="critic")

        assert msg1["agent_id"] == "orchestrator"
        assert msg2["agent_id"] == "reasoner"
        assert msg3["agent_id"] == "critic"

    def test_user_message_has_empty_agent_id(self):
        """用户消息的 agent_id 应为空"""
        sid = _make_session("用户消息测试")
        cm = get_conversation_manager()
        conv = cm.create_conversation(sid, title="用户消息测试")

        msg = cm.add_message(conv["id"], "user", "用户输入", agent_id="")
        assert msg["agent_id"] == ""

    def test_messages_from_different_agents_coexist(self):
        """不同 Agent 的消息可在同一对话中共存"""
        sid = _make_session("多Agent共存测试")
        cm = get_conversation_manager()
        conv = cm.create_conversation(sid, title="多Agent共存")

        agents = ["orchestrator", "searcher", "reasoner", "critic", "writer", "mentor"]
        for agent_id in agents:
            cm.add_message(conv["id"], "assistant", f"{agent_id}的回复", agent_id=agent_id)

        msgs = cm.get_messages(conv["id"])
        assert len(msgs) == 6

        agent_ids_in_msgs = [m["agent_id"] for m in msgs]
        for agent_id in agents:
            assert agent_id in agent_ids_in_msgs

    def test_conversation_default_agent_id(self):
        """对话应记录默认 agent_id"""
        sid = _make_session("默认Agent测试")
        cm = get_conversation_manager()

        for agent_id in ["orchestrator", "reasoner", "critic"]:
            conv = cm.create_conversation(sid, title=f"默认{agent_id}", agent_id=agent_id)
            assert conv["agent_id"] == agent_id


# ===== 对话 CRUD 综合测试 =====

class TestConversationCRUD:
    """对话 CRUD 综合测试"""

    def test_get_conversation_returns_none_for_nonexistent(self):
        """获取不存在的对话应返回 None"""
        cm = get_conversation_manager()
        result = cm.get_conversation("nonexistent-id")
        assert result is None

    def test_rename_conversation(self):
        """重命名对话"""
        sid = _make_session("重命名测试")
        cm = get_conversation_manager()
        conv = cm.create_conversation(sid, title="原标题")

        renamed = cm.rename_conversation(conv["id"], "新标题")
        assert renamed is not None
        assert renamed["title"] == "新标题"

    def test_rename_nonexistent_returns_none(self):
        """重命名不存在的对话应返回 None"""
        cm = get_conversation_manager()
        result = cm.rename_conversation("nonexistent", "新标题")
        assert result is None

    def test_delete_conversation(self):
        """删除对话"""
        sid = _make_session("删除测试")
        cm = get_conversation_manager()
        conv = cm.create_conversation(sid, title="待删除")

        result = cm.delete_conversation(conv["id"])
        assert result is True

        # 验证已删除
        deleted = cm.get_conversation(conv["id"])
        assert deleted is None

    def test_delete_nonexistent_returns_false(self):
        """删除不存在的对话应返回 False"""
        cm = get_conversation_manager()
        result = cm.delete_conversation("nonexistent")
        assert result is False

    def test_delete_conversation_cascades_messages(self):
        """删除对话应级联删除消息"""
        sid = _make_session("级联删除测试")
        cm = get_conversation_manager()
        conv = cm.create_conversation(sid, title="级联删除")

        # 添加消息
        msg1 = cm.add_message(conv["id"], "user", "消息1")
        msg2 = cm.add_message(conv["id"], "assistant", "回复1")
        assert len(cm.get_messages(conv["id"])) == 2

        # 删除对话
        cm.delete_conversation(conv["id"])

        # 消息应也被删除（通过 get_message 验证）
        assert cm.get_message(msg1["id"]) is None
        assert cm.get_message(msg2["id"]) is None

    def test_list_conversations_ordered_by_updated_at(self):
        """对话列表应按 updated_at 降序排列"""
        sid = _make_session("排序测试")
        cm = get_conversation_manager()

        conv1 = cm.create_conversation(sid, title="对话1")
        conv2 = cm.create_conversation(sid, title="对话2")

        # 更新 conv1（通过添加消息）
        cm.add_message(conv1["id"], "user", "更新对话1")

        convs = cm.list_conversations(sid)
        # conv1 应排在 conv2 前面（因为最近更新）
        conv1_idx = next(i for i, c in enumerate(convs) if c["id"] == conv1["id"])
        conv2_idx = next(i for i, c in enumerate(convs) if c["id"] == conv2["id"])
        assert conv1_idx < conv2_idx


# ===== 消息管理测试 =====

class TestMessageManagement:
    """消息管理测试"""

    def test_add_message_returns_message_dict(self):
        """add_message 应返回消息字典"""
        sid = _make_session("添加消息测试")
        cm = get_conversation_manager()
        conv = cm.create_conversation(sid, title="消息测试")

        msg = cm.add_message(conv["id"], "user", "测试内容")
        assert msg is not None
        assert msg["role"] == "user"
        assert msg["content"] == "测试内容"
        assert msg["conversation_id"] == conv["id"]

    def test_get_message_returns_none_for_nonexistent(self):
        """获取不存在的消息应返回 None"""
        cm = get_conversation_manager()
        assert cm.get_message("nonexistent") is None

    def test_get_messages_returns_empty_for_empty_conversation(self):
        """空对话的消息列表应为空"""
        sid = _make_session("空对话测试")
        cm = get_conversation_manager()
        conv = cm.create_conversation(sid, title="空对话")

        msgs = cm.get_messages(conv["id"])
        assert msgs == []

    def test_get_messages_respects_limit(self):
        """get_messages 应遵守 limit 参数"""
        sid = _make_session("Limit测试")
        cm = get_conversation_manager()
        conv = cm.create_conversation(sid, title="Limit测试")

        for i in range(10):
            cm.add_message(conv["id"], "user", f"消息{i}")

        msgs = cm.get_messages(conv["id"], limit=5)
        assert len(msgs) == 5

    def test_message_preserves_reasoning(self):
        """消息应保留 reasoning 字段"""
        sid = _make_session("Reasoning测试")
        cm = get_conversation_manager()
        conv = cm.create_conversation(sid, title="Reasoning测试")

        msg = cm.add_message(
            conv["id"], "assistant", "回复内容",
            reasoning="<think>推理过程</think>",
        )
        assert msg["reasoning"] == "<think>推理过程</think>"

    def test_message_preserves_search_results(self):
        """消息应保留 search_results"""
        sid = _make_session("搜索结果测试")
        cm = get_conversation_manager()
        conv = cm.create_conversation(sid, title="搜索结果测试")

        search_results = [{"title": "文献1", "url": "https://example.com/1"}]
        msg = cm.add_message(
            conv["id"], "assistant", "带搜索结果的回复",
            search_results=search_results,
        )
        assert msg["search_results"] == search_results

    def test_message_preserves_token_usage(self):
        """消息应保留 token_usage"""
        sid = _make_session("Token测试")
        cm = get_conversation_manager()
        conv = cm.create_conversation(sid, title="Token测试")

        token_usage = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
        msg = cm.add_message(
            conv["id"], "assistant", "带token用量的回复",
            token_usage=token_usage,
        )
        assert msg["token_usage"] == token_usage


# ===== 引用管理测试 =====

class TestCitationManagement:
    """引用管理测试"""

    def test_add_message_with_citations(self):
        """添加带引用的消息"""
        sid = _make_session("引用测试")
        cm = get_conversation_manager()
        conv = cm.create_conversation(sid, title="引用测试")

        citations = [
            {"url": "https://example.com/1", "title": "引用1", "snippet": "摘要1"},
            {"url": "https://example.com/2", "title": "引用2", "snippet": "摘要2"},
        ]
        msg = cm.add_message(
            conv["id"], "assistant", "带引用的回复",
            citations=citations,
        )

        cites = cm.get_message_citations(msg["id"])
        assert len(cites) == 2
        assert cites[0]["url"] == "https://example.com/1"
        assert cites[1]["url"] == "https://example.com/2"

    def test_get_citations_for_nonexistent_message(self):
        """获取不存在消息的引用应返回空列表"""
        cm = get_conversation_manager()
        cites = cm.get_message_citations("nonexistent")
        assert cites == []

    def test_citations_preserve_all_fields(self):
        """引用应保留所有字段"""
        sid = _make_session("引用字段测试")
        cm = get_conversation_manager()
        conv = cm.create_conversation(sid, title="引用字段")

        citations = [{
            "url": "https://example.com/test",
            "title": "测试标题",
            "snippet": "测试摘要",
            "source_domain": "example.com",
            "favicon": "https://favicon.com/icon.ico",
        }]
        msg = cm.add_message(conv["id"], "assistant", "回复", citations=citations)

        cites = cm.get_message_citations(msg["id"])
        assert len(cites) == 1
        cite = cites[0]
        assert cite["url"] == "https://example.com/test"
        assert cite["title"] == "测试标题"
        assert cite["snippet"] == "测试摘要"
        assert cite["source_domain"] == "example.com"
        assert cite["favicon"] == "https://favicon.com/icon.ico"


# ===== 多会话多对话综合测试 =====

class TestMultiSessionMultiConversation:
    """多会话多对话综合测试"""

    def test_multiple_sessions_each_with_conversations(self):
        """多个会话各自有对话"""
        cm = get_conversation_manager()

        # 创建3个会话，每个会话2个对话
        session_convs = {}
        for i in range(3):
            sid = _make_session(f"会话{i}")
            convs = []
            for j in range(2):
                conv = cm.create_conversation(sid, title=f"会话{i}_对话{j}")
                convs.append(conv["id"])
            session_convs[sid] = convs

        # 验证每个会话的对话列表
        for sid, expected_conv_ids in session_convs.items():
            convs = cm.list_conversations(sid)
            conv_ids = [c["id"] for c in convs]
            for cid in expected_conv_ids:
                assert cid in conv_ids

    def test_cross_session_isolation(self):
        """跨会话的对话应完全隔离"""
        cm = get_conversation_manager()

        sid1 = _make_session("会话1")
        sid2 = _make_session("会话2")

        conv1 = cm.create_conversation(sid1, title="会话1对话")
        conv2 = cm.create_conversation(sid2, title="会话2对话")

        # 各自添加消息
        cm.add_message(conv1["id"], "user", "会话1的消息")
        cm.add_message(conv2["id"], "user", "会话2的消息")

        # 验证隔离
        msgs1 = cm.get_messages(conv1["id"])
        msgs2 = cm.get_messages(conv2["id"])

        assert len(msgs1) == 1
        assert len(msgs2) == 1
        assert msgs1[0]["content"] == "会话1的消息"
        assert msgs2[0]["content"] == "会话2的消息"

    def test_conversation_belongs_to_correct_session(self):
        """对话应属于正确的会话"""
        cm = get_conversation_manager()

        sid1 = _make_session("会话A")
        sid2 = _make_session("会话B")

        conv1 = cm.create_conversation(sid1, title="属于会话A")
        conv2 = cm.create_conversation(sid2, title="属于会话B")

        assert conv1["session_id"] == sid1
        assert conv2["session_id"] == sid2

        # 会话A的对话列表不应包含会话B的对话
        convs1 = cm.list_conversations(sid1)
        convs2 = cm.list_conversations(sid2)
        conv1_ids = [c["id"] for c in convs1]
        conv2_ids = [c["id"] for c in convs2]

        assert conv1["id"] in conv1_ids
        assert conv2["id"] not in conv1_ids
        assert conv2["id"] in conv2_ids
        assert conv1["id"] not in conv2_ids
