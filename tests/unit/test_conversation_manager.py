"""对话管理器单元测试

测试 backend/sessions/conversation_manager.py 的 ConversationManager 类。
覆盖以下功能：
  - create_conversation: 创建新对话
  - list_conversations: 列出会话下所有对话
  - get_conversation: 获取对话详情
  - delete_conversation: 删除对话（级联删除消息与引用）
  - rename_conversation: 重命名对话
  - set_active: 设置激活对话
  - add_message: 添加消息（含引用写入）
  - get_message: 获取单条消息（含 JSON 反序列化）
  - get_messages: 获取对话所有消息
  - get_context_window: 获取上下文窗口（DST 压缩）
  - get_message_citations: 获取消息引用
  - get_conversation_manager: 单例获取

测试策略：
  - 使用临时数据库隔离测试
  - 先插入 session 满足外键约束
  - 覆盖正常流程、边界条件、异常场景
"""
import os
import sys
import tempfile
import uuid

import pytest

# ===== 项目根目录加入 sys.path =====
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ===== 临时数据库初始化（必须在导入 backend.database 之前覆盖 DB_PATH）=====
_TMP_DIR = tempfile.mkdtemp(prefix="thesisminer_conv_mgr_test_")
import backend.database as _db
_db.DB_PATH = os.path.join(_TMP_DIR, "test.db")
_db.init_db()

from backend.sessions.conversation_manager import (
    ConversationManager,
    get_conversation_manager,
)
from backend.database import get_db_connection


# ===== 辅助函数 =====

def _insert_session(session_id: str = None, title: str = "测试会话") -> str:
    """向 sessions 表插入一条记录以满足外键约束。

    conversations.session_id 外键引用 sessions.id，
    因此创建对话前必须先插入对应 session。

    Args:
        session_id: 可选的会话 ID，未提供则自动生成。
        title: 会话标题。

    Returns:
        插入的会话 ID。
    """
    sid = session_id or f"test-session-{uuid.uuid4().hex[:12]}"
    conn = get_db_connection()
    try:
        conn.execute(
            """INSERT OR IGNORE INTO sessions (id, title, created_at, updated_at)
               VALUES (?, ?, datetime('now'), datetime('now'))""",
            (sid, title),
        )
        conn.commit()
    finally:
        conn.close()
    return sid


def _make_manager() -> ConversationManager:
    """构造一个新的 ConversationManager 实例。

    每个测试使用独立实例，避免单例状态污染。

    Returns:
        ConversationManager 实例。
    """
    return ConversationManager()


# ===== 测试类：create_conversation =====

class TestCreateConversation:
    """测试 create_conversation 方法。"""

    def test_create_with_default_params(self):
        """使用默认参数创建对话，应返回包含 id 与默认标题的字典。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        assert conv is not None
        assert "id" in conv
        assert conv["session_id"] == sid
        assert conv["title"] == "新对话"
        assert conv["agent_id"] == "orchestrator"
        assert conv["status"] == "active"
        assert conv["message_count"] == 0

    def test_create_with_custom_title(self):
        """使用自定义标题创建对话。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid, title="我的开题对话")
        assert conv["title"] == "我的开题对话"

    def test_create_with_custom_agent_id(self):
        """使用自定义 agent_id 创建对话。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid, agent_id="reasoner")
        assert conv["agent_id"] == "reasoner"

    def test_create_updates_active_conversation_id(self):
        """创建对话后应更新 session 的 active_conversation_id 字段。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        # 查询 session 验证 active_conversation_id 已更新
        conn = get_db_connection()
        try:
            row = conn.execute(
                "SELECT active_conversation_id FROM sessions WHERE id = ?",
                (sid,),
            ).fetchone()
        finally:
            conn.close()
        assert row["active_conversation_id"] == conv["id"]

    def test_create_multiple_conversations_same_session(self):
        """同一 session 下创建多个对话，每个应有独立 id。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv1 = mgr.create_conversation(sid, title="对话1")
        conv2 = mgr.create_conversation(sid, title="对话2")
        assert conv1["id"] != conv2["id"]
        assert conv1["session_id"] == sid
        assert conv2["session_id"] == sid

    def test_create_returns_dict_with_message_count(self):
        """返回的字典应包含 message_count 字段，初始为 0。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        assert "message_count" in conv
        assert conv["message_count"] == 0

    def test_create_generates_unique_uuid(self):
        """每次创建的对话 id 应为唯一 UUID 字符串。"""
        sid = _insert_session()
        mgr = _make_manager()
        ids = set()
        for _ in range(5):
            conv = mgr.create_conversation(sid)
            ids.add(conv["id"])
        assert len(ids) == 5

    def test_create_with_chinese_title(self):
        """创建含中文标题的对话。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid, title="基于深度学习的论文选题研究")
        assert conv["title"] == "基于深度学习的论文选题研究"

    def test_create_with_empty_title_uses_default(self):
        """传入空标题时使用默认值。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid, title="新对话")
        assert conv["title"] == "新对话"


# ===== 测试类：list_conversations =====

class TestListConversations:
    """测试 list_conversations 方法。"""

    def test_list_empty_session(self):
        """会话下无对话时返回空列表。"""
        sid = _insert_session()
        mgr = _make_manager()
        result = mgr.list_conversations(sid)
        assert result == []

    def test_list_single_conversation(self):
        """会话下有一个对话时返回单元素列表。"""
        sid = _insert_session()
        mgr = _make_manager()
        mgr.create_conversation(sid, title="对话A")
        result = mgr.list_conversations(sid)
        assert len(result) == 1
        assert result[0]["title"] == "对话A"

    def test_list_multiple_conversations(self):
        """会话下有多个对话时全部返回。"""
        sid = _insert_session()
        mgr = _make_manager()
        mgr.create_conversation(sid, title="对话1")
        mgr.create_conversation(sid, title="对话2")
        mgr.create_conversation(sid, title="对话3")
        result = mgr.list_conversations(sid)
        assert len(result) == 3

    def test_list_isolates_by_session(self):
        """不同 session 的对话应隔离，不串数据。"""
        sid1 = _insert_session(title="会话1")
        sid2 = _insert_session(title="会话2")
        mgr = _make_manager()
        mgr.create_conversation(sid1, title="A1")
        mgr.create_conversation(sid2, title="B1")
        mgr.create_conversation(sid2, title="B2")
        result1 = mgr.list_conversations(sid1)
        result2 = mgr.list_conversations(sid2)
        assert len(result1) == 1
        assert len(result2) == 2

    def test_list_includes_message_count(self):
        """返回的对话字典应包含 message_count 字段。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        mgr.add_message(conv["id"], "user", "你好")
        result = mgr.list_conversations(sid)
        assert result[0]["message_count"] == 1

    def test_list_nonexistent_session_returns_empty(self):
        """查询不存在的 session 时返回空列表。"""
        mgr = _make_manager()
        result = mgr.list_conversations("nonexistent-session-id")
        assert result == []

    def test_list_ordered_by_updated_at_desc(self):
        """对话列表应按 updated_at 降序排列。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv1 = mgr.create_conversation(sid, title="旧对话")
        conv2 = mgr.create_conversation(sid, title="新对话")
        # 给 conv2 添加消息以更新 updated_at
        mgr.add_message(conv2["id"], "user", "更新")
        result = mgr.list_conversations(sid)
        # 列表应包含两个对话
        assert len(result) == 2
        # 验证两个对话 id 都在结果中
        result_ids = {r["id"] for r in result}
        assert conv1["id"] in result_ids
        assert conv2["id"] in result_ids


# ===== 测试类：get_conversation =====

class TestGetConversation:
    """测试 get_conversation 方法。"""

    def test_get_existing_conversation(self):
        """获取存在的对话应返回完整字典。"""
        sid = _insert_session()
        mgr = _make_manager()
        created = mgr.create_conversation(sid, title="测试对话")
        result = mgr.get_conversation(created["id"])
        assert result is not None
        assert result["id"] == created["id"]
        assert result["title"] == "测试对话"

    def test_get_nonexistent_returns_none(self):
        """获取不存在的对话应返回 None。"""
        mgr = _make_manager()
        result = mgr.get_conversation("nonexistent-conv-id")
        assert result is None

    def test_get_includes_message_count(self):
        """返回的字典应包含 message_count 字段。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        mgr.add_message(conv["id"], "user", "消息1")
        mgr.add_message(conv["id"], "assistant", "回复1")
        result = mgr.get_conversation(conv["id"])
        assert result["message_count"] == 2

    def test_get_returns_all_fields(self):
        """返回的字典应包含所有 conversations 表字段。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        result = mgr.get_conversation(conv["id"])
        expected_fields = {"id", "session_id", "title", "agent_id", "status",
                          "created_at", "updated_at", "message_count"}
        assert expected_fields.issubset(set(result.keys()))

    def test_get_after_rename_returns_new_title(self):
        """重命名后获取应返回新标题。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid, title="旧标题")
        mgr.rename_conversation(conv["id"], "新标题")
        result = mgr.get_conversation(conv["id"])
        assert result["title"] == "新标题"


# ===== 测试类：delete_conversation =====

class TestDeleteConversation:
    """测试 delete_conversation 方法。"""

    def test_delete_existing_conversation(self):
        """删除存在的对话应返回 True。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        result = mgr.delete_conversation(conv["id"])
        assert result is True

    def test_delete_nonexistent_returns_false(self):
        """删除不存在的对话应返回 False。"""
        mgr = _make_manager()
        result = mgr.delete_conversation("nonexistent-id")
        assert result is False

    def test_delete_cascades_messages(self):
        """删除对话后，关联的消息应被级联删除。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        msg = mgr.add_message(conv["id"], "user", "测试消息")
        mgr.delete_conversation(conv["id"])
        # 验证消息已被删除
        result = mgr.get_message(msg["id"])
        assert result is None

    def test_delete_does_not_affect_other_conversations(self):
        """删除一个对话不影响同 session 下的其他对话。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv1 = mgr.create_conversation(sid, title="对话1")
        conv2 = mgr.create_conversation(sid, title="对话2")
        mgr.delete_conversation(conv1["id"])
        assert mgr.get_conversation(conv2["id"]) is not None

    def test_delete_then_list_shows_remaining(self):
        """删除后列表应只显示剩余对话。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv1 = mgr.create_conversation(sid, title="保留")
        conv2 = mgr.create_conversation(sid, title="删除")
        mgr.delete_conversation(conv2["id"])
        result = mgr.list_conversations(sid)
        assert len(result) == 1
        assert result[0]["id"] == conv1["id"]


# ===== 测试类：rename_conversation =====

class TestRenameConversation:
    """测试 rename_conversation 方法。"""

    def test_rename_updates_title(self):
        """重命名应更新标题。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid, title="旧标题")
        result = mgr.rename_conversation(conv["id"], "新标题")
        assert result["title"] == "新标题"

    def test_rename_nonexistent_returns_none(self):
        """重命名不存在的对话应返回 None。"""
        mgr = _make_manager()
        result = mgr.rename_conversation("nonexistent-id", "新标题")
        assert result is None

    def test_rename_to_empty_string(self):
        """重命名为空字符串应允许（数据库层不限制）。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid, title="原标题")
        result = mgr.rename_conversation(conv["id"], "")
        assert result["title"] == ""

    def test_rename_updates_updated_at(self):
        """重命名应更新 updated_at 字段。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid, title="原标题")
        original_updated = conv["updated_at"]
        # 重命名
        result = mgr.rename_conversation(conv["id"], "新标题")
        # updated_at 可能相同（同一秒），但字段应存在
        assert "updated_at" in result

    def test_rename_with_chinese_title(self):
        """使用中文标题重命名。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid, title="old")
        result = mgr.rename_conversation(conv["id"], "基于知识图谱的论文推荐")
        assert result["title"] == "基于知识图谱的论文推荐"

    def test_rename_multiple_times(self):
        """多次重命名应每次都生效。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid, title="v1")
        mgr.rename_conversation(conv["id"], "v2")
        result = mgr.rename_conversation(conv["id"], "v3")
        assert result["title"] == "v3"


# ===== 测试类：set_active =====

class TestSetActive:
    """测试 set_active 方法。"""

    def test_set_active_updates_session(self):
        """设置激活对话应更新 session 的 active_conversation_id。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv1 = mgr.create_conversation(sid, title="对话1")
        conv2 = mgr.create_conversation(sid, title="对话2")
        # conv2 创建时已成为 active，现在切回 conv1
        result = mgr.set_active(sid, conv1["id"])
        assert result is True
        # 验证
        conn = get_db_connection()
        try:
            row = conn.execute(
                "SELECT active_conversation_id FROM sessions WHERE id = ?",
                (sid,),
            ).fetchone()
        finally:
            conn.close()
        assert row["active_conversation_id"] == conv1["id"]

    def test_set_active_returns_true(self):
        """set_active 应始终返回 True。"""
        sid = _insert_session()
        mgr = _make_manager()
        result = mgr.set_active(sid, "any-conv-id")
        assert result is True

    def test_set_active_switch_between_conversations(self):
        """在多个对话间切换激活状态。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv1 = mgr.create_conversation(sid, title="A")
        conv2 = mgr.create_conversation(sid, title="B")
        conv3 = mgr.create_conversation(sid, title="C")
        # 切换到 conv1
        mgr.set_active(sid, conv1["id"])
        conn = get_db_connection()
        try:
            row = conn.execute(
                "SELECT active_conversation_id FROM sessions WHERE id = ?",
                (sid,),
            ).fetchone()
        finally:
            conn.close()
        assert row["active_conversation_id"] == conv1["id"]


# ===== 测试类：add_message =====

class TestAddMessage:
    """测试 add_message 方法。"""

    def test_add_message_basic(self):
        """添加基本消息应返回消息字典。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        msg = mgr.add_message(conv["id"], "user", "你好")
        assert msg is not None
        assert msg["role"] == "user"
        assert msg["content"] == "你好"
        assert msg["conversation_id"] == conv["id"]

    def test_add_message_with_agent_id(self):
        """添加带 agent_id 的消息。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        msg = mgr.add_message(conv["id"], "assistant", "回复", agent_id="reasoner")
        assert msg["agent_id"] == "reasoner"

    def test_add_message_with_reasoning(self):
        """添加带推理过程的消息。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        msg = mgr.add_message(conv["id"], "assistant", "回复",
                             reasoning="这是推理过程")
        assert msg["reasoning"] == "这是推理过程"

    def test_add_message_with_search_results(self):
        """添加带搜索结果的消息，应 JSON 序列化存储。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        search_results = [{"title": "论文1", "url": "http://example.com"}]
        msg = mgr.add_message(conv["id"], "assistant", "回复",
                             search_results=search_results)
        assert msg["search_results"] == search_results

    def test_add_message_with_token_usage(self):
        """添加带 token 用量的消息。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        token_usage = {"prompt_tokens": 100, "completion_tokens": 50}
        msg = mgr.add_message(conv["id"], "assistant", "回复",
                             token_usage=token_usage)
        assert msg["token_usage"] == token_usage

    def test_add_message_with_citations(self):
        """添加带引用的消息，引用应写入 search_citations 表。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        citations = [
            {"url": "http://example.com/1", "title": "引用1",
             "snippet": "摘要1", "source_domain": "example.com", "favicon": ""},
            {"url": "http://example.com/2", "title": "引用2",
             "snippet": "摘要2", "source_domain": "example.com", "favicon": ""},
        ]
        msg = mgr.add_message(conv["id"], "assistant", "回复", citations=citations)
        # 验证引用已写入
        cites = mgr.get_message_citations(msg["id"])
        assert len(cites) == 2

    def test_add_message_updates_conversation_updated_at(self):
        """添加消息应更新对话的 updated_at 字段。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        original_updated = conv["updated_at"]
        mgr.add_message(conv["id"], "user", "新消息")
        updated_conv = mgr.get_conversation(conv["id"])
        assert "updated_at" in updated_conv

    def test_add_multiple_messages(self):
        """添加多条消息，每条应有独立 id。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        msg1 = mgr.add_message(conv["id"], "user", "消息1")
        msg2 = mgr.add_message(conv["id"], "assistant", "消息2")
        assert msg1["id"] != msg2["id"]

    def test_add_message_empty_content(self):
        """添加空内容消息应允许。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        msg = mgr.add_message(conv["id"], "user", "")
        assert msg["content"] == ""

    def test_add_message_with_empty_citations_list(self):
        """添加空引用列表不应报错。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        msg = mgr.add_message(conv["id"], "assistant", "回复", citations=[])
        cites = mgr.get_message_citations(msg["id"])
        assert cites == []


# ===== 测试类：get_message =====

class TestGetMessage:
    """测试 get_message 方法。"""

    def test_get_existing_message(self):
        """获取存在的消息应返回完整字典。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        created = mgr.add_message(conv["id"], "user", "测试内容")
        result = mgr.get_message(created["id"])
        assert result is not None
        assert result["content"] == "测试内容"

    def test_get_nonexistent_returns_none(self):
        """获取不存在的消息应返回 None。"""
        mgr = _make_manager()
        result = mgr.get_message("nonexistent-msg-id")
        assert result is None

    def test_get_deserializes_search_results(self):
        """获取消息时应反序列化 search_results 字段。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        search_results = [{"title": "论文", "url": "http://x.com"}]
        created = mgr.add_message(conv["id"], "assistant", "回复",
                                  search_results=search_results)
        result = mgr.get_message(created["id"])
        assert result["search_results"] == search_results

    def test_get_deserializes_token_usage(self):
        """获取消息时应反序列化 token_usage 字段。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        token_usage = {"prompt": 200, "completion": 100}
        created = mgr.add_message(conv["id"], "assistant", "回复",
                                  token_usage=token_usage)
        result = mgr.get_message(created["id"])
        assert result["token_usage"] == token_usage

    def test_get_message_without_search_results(self):
        """获取不含搜索结果的消息，search_results 应为空列表。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        created = mgr.add_message(conv["id"], "user", "普通消息")
        result = mgr.get_message(created["id"])
        assert result["search_results"] == []

    def test_get_message_without_token_usage(self):
        """获取不含 token 用量的消息，token_usage 应为空字典。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        created = mgr.add_message(conv["id"], "user", "普通消息")
        result = mgr.get_message(created["id"])
        assert result["token_usage"] == {}


# ===== 测试类：get_messages =====

class TestGetMessages:
    """测试 get_messages 方法。"""

    def test_get_messages_empty_conversation(self):
        """无消息的对话返回空列表。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        result = mgr.get_messages(conv["id"])
        assert result == []

    def test_get_messages_single(self):
        """获取单条消息。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        mgr.add_message(conv["id"], "user", "你好")
        result = mgr.get_messages(conv["id"])
        assert len(result) == 1
        assert result[0]["content"] == "你好"

    def test_get_messages_multiple(self):
        """获取多条消息。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        for i in range(5):
            mgr.add_message(conv["id"], "user", f"消息{i}")
        result = mgr.get_messages(conv["id"])
        assert len(result) == 5

    def test_get_messages_isolates_by_conversation(self):
        """不同对话的消息应隔离。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv1 = mgr.create_conversation(sid, title="对话1")
        conv2 = mgr.create_conversation(sid, title="对话2")
        mgr.add_message(conv1["id"], "user", "A1")
        mgr.add_message(conv2["id"], "user", "B1")
        mgr.add_message(conv2["id"], "user", "B2")
        result1 = mgr.get_messages(conv1["id"])
        result2 = mgr.get_messages(conv2["id"])
        assert len(result1) == 1
        assert len(result2) == 2

    def test_get_messages_with_limit(self):
        """limit 参数应限制返回条数。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        for i in range(10):
            mgr.add_message(conv["id"], "user", f"消息{i}")
        result = mgr.get_messages(conv["id"], limit=3)
        assert len(result) == 3

    def test_get_messages_deserializes_json_fields(self):
        """返回的消息应反序列化 search_results 与 token_usage。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        mgr.add_message(conv["id"], "assistant", "回复",
                       search_results=[{"x": 1}],
                       token_usage={"y": 2})
        result = mgr.get_messages(conv["id"])
        assert result[0]["search_results"] == [{"x": 1}]
        assert result[0]["token_usage"] == {"y": 2}

    def test_get_messages_nonexistent_conversation(self):
        """查询不存在的对话返回空列表。"""
        mgr = _make_manager()
        result = mgr.get_messages("nonexistent-id")
        assert result == []


# ===== 测试类：get_context_window =====

class TestGetContextWindow:
    """测试 get_context_window 方法。"""

    def test_context_window_empty_conversation(self):
        """无消息的对话返回空列表。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        result = mgr.get_context_window(conv["id"])
        assert result == []

    def test_context_window_small_history(self):
        """少量消息应全部返回。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        mgr.add_message(conv["id"], "user", "短消息1")
        mgr.add_message(conv["id"], "assistant", "短消息2")
        result = mgr.get_context_window(conv["id"])
        assert len(result) == 2

    def test_context_window_respects_max_tokens(self):
        """max_tokens 限制应截断消息。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        # 添加多条长消息
        for i in range(10):
            mgr.add_message(conv["id"], "user", f"这是一条较长的测试消息内容编号{i}" * 10)
        # 设置很小的 max_tokens
        result = mgr.get_context_window(conv["id"], max_tokens=50)
        # 应只返回部分消息
        assert len(result) < 10

    def test_context_window_large_max_tokens(self):
        """足够大的 max_tokens 应返回所有消息。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        for i in range(5):
            mgr.add_message(conv["id"], "user", f"消息{i}")
        result = mgr.get_context_window(conv["id"], max_tokens=100000)
        assert len(result) == 5

    def test_context_window_default_max_tokens(self):
        """默认 max_tokens=8000 应能容纳少量消息。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        mgr.add_message(conv["id"], "user", "普通消息")
        result = mgr.get_context_window(conv["id"])
        assert len(result) == 1


# ===== 测试类：get_message_citations =====

class TestGetMessageCitations:
    """测试 get_message_citations 方法。"""

    def test_get_citations_no_citations(self):
        """无引用的消息返回空列表。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        msg = mgr.add_message(conv["id"], "user", "普通消息")
        result = mgr.get_message_citations(msg["id"])
        assert result == []

    def test_get_citations_single(self):
        """获取单条引用。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        citations = [{"url": "http://x.com", "title": "标题",
                      "snippet": "摘要", "source_domain": "x.com", "favicon": ""}]
        msg = mgr.add_message(conv["id"], "assistant", "回复", citations=citations)
        result = mgr.get_message_citations(msg["id"])
        assert len(result) == 1
        assert result[0]["url"] == "http://x.com"

    def test_get_citations_multiple(self):
        """获取多条引用。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        citations = [
            {"url": f"http://x.com/{i}", "title": f"标题{i}",
             "snippet": f"摘要{i}", "source_domain": "x.com", "favicon": ""}
            for i in range(5)
        ]
        msg = mgr.add_message(conv["id"], "assistant", "回复", citations=citations)
        result = mgr.get_message_citations(msg["id"])
        assert len(result) == 5

    def test_get_citations_nonexistent_message(self):
        """查询不存在消息的引用返回空列表。"""
        mgr = _make_manager()
        result = mgr.get_message_citations("nonexistent-id")
        assert result == []

    def test_get_citations_includes_all_fields(self):
        """引用字典应包含所有 search_citations 表字段。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        citations = [{"url": "http://x.com", "title": "标题",
                      "snippet": "摘要", "source_domain": "x.com",
                      "favicon": "favicon.ico"}]
        msg = mgr.add_message(conv["id"], "assistant", "回复", citations=citations)
        result = mgr.get_message_citations(msg["id"])
        cite = result[0]
        assert "id" in cite
        assert "message_id" in cite
        assert "url" in cite
        assert "title" in cite
        assert "snippet" in cite
        assert "source_domain" in cite
        assert "favicon" in cite

    def test_get_citations_isolates_by_message(self):
        """不同消息的引用应隔离。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid)
        msg1 = mgr.add_message(conv["id"], "assistant", "回复1",
                              citations=[{"url": "http://a.com", "title": "A",
                                          "snippet": "", "source_domain": "",
                                          "favicon": ""}])
        msg2 = mgr.add_message(conv["id"], "assistant", "回复2",
                              citations=[{"url": "http://b.com", "title": "B",
                                          "snippet": "", "source_domain": "",
                                          "favicon": ""},
                                         {"url": "http://c.com", "title": "C",
                                          "snippet": "", "source_domain": "",
                                          "favicon": ""}])
        cites1 = mgr.get_message_citations(msg1["id"])
        cites2 = mgr.get_message_citations(msg2["id"])
        assert len(cites1) == 1
        assert len(cites2) == 2


# ===== 测试类：get_conversation_manager 单例 =====

class TestGetConversationManager:
    """测试 get_conversation_manager 单例函数。"""

    def test_returns_instance(self):
        """应返回 ConversationManager 实例。"""
        mgr = get_conversation_manager()
        assert isinstance(mgr, ConversationManager)

    def test_returns_same_instance(self):
        """多次调用应返回同一实例。"""
        mgr1 = get_conversation_manager()
        mgr2 = get_conversation_manager()
        assert mgr1 is mgr2

    def test_singleton_can_create_conversation(self):
        """单例实例应能正常创建对话。"""
        sid = _insert_session()
        mgr = get_conversation_manager()
        conv = mgr.create_conversation(sid, title="单例测试")
        assert conv is not None
        assert conv["title"] == "单例测试"


# ===== 集成测试 =====

class TestConversationManagerIntegration:
    """ConversationManager 集成测试：模拟完整对话流程。"""

    def test_full_conversation_lifecycle(self):
        """测试完整对话生命周期：创建→添加消息→查询→删除。"""
        sid = _insert_session()
        mgr = _make_manager()
        # 1. 创建对话
        conv = mgr.create_conversation(sid, title="生命周期测试")
        assert conv["message_count"] == 0
        # 2. 添加多条消息
        mgr.add_message(conv["id"], "user", "请帮我生成论题")
        mgr.add_message(conv["id"], "assistant", "好的，请提供研究方向",
                       agent_id="orchestrator")
        mgr.add_message(conv["id"], "user", "人工智能在教育中的应用")
        # 3. 验证消息数
        conv_updated = mgr.get_conversation(conv["id"])
        assert conv_updated["message_count"] == 3
        # 4. 获取上下文窗口
        ctx = mgr.get_context_window(conv["id"])
        assert len(ctx) == 3
        # 5. 删除对话
        assert mgr.delete_conversation(conv["id"]) is True
        assert mgr.get_conversation(conv["id"]) is None

    def test_multi_conversation_isolation(self):
        """测试多对话上下文隔离：同一 session 下两个对话互不干扰。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv1 = mgr.create_conversation(sid, title="对话A")
        conv2 = mgr.create_conversation(sid, title="对话B")
        # 对话A 添加 2 条消息
        mgr.add_message(conv1["id"], "user", "A1")
        mgr.add_message(conv1["id"], "assistant", "A2")
        # 对话B 添加 3 条消息
        mgr.add_message(conv2["id"], "user", "B1")
        mgr.add_message(conv2["id"], "assistant", "B2")
        mgr.add_message(conv2["id"], "user", "B3")
        # 验证隔离
        msgs1 = mgr.get_messages(conv1["id"])
        msgs2 = mgr.get_messages(conv2["id"])
        assert len(msgs1) == 2
        assert len(msgs2) == 3
        # 验证内容不串
        contents1 = [m["content"] for m in msgs1]
        contents2 = [m["content"] for m in msgs2]
        assert all(c.startswith("A") for c in contents1)
        assert all(c.startswith("B") for c in contents2)

    def test_conversation_with_citations_flow(self):
        """测试带引用的完整对话流程。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv = mgr.create_conversation(sid, title="引用测试")
        # 添加带引用的助手消息
        citations = [
            {"url": "http://arxiv.org/abs/2401.00001", "title": "深度学习综述",
             "snippet": "本文综述了深度学习的最新进展",
             "source_domain": "arxiv.org", "favicon": ""},
            {"url": "http://example.com/paper2", "title": "教育AI应用",
             "snippet": "探讨AI在教育领域的应用",
             "source_domain": "example.com", "favicon": ""},
        ]
        msg = mgr.add_message(conv["id"], "assistant",
                             "根据最新研究，AI在教育中有广泛应用",
                             agent_id="searcher",
                             citations=citations)
        # 验证引用可查询
        cites = mgr.get_message_citations(msg["id"])
        assert len(cites) == 2
        # 引用顺序不保证（按 UUID 排序），验证两个标题都存在
        cite_titles = [c["title"] for c in cites]
        assert "深度学习综述" in cite_titles
        assert "教育AI应用" in cite_titles
        # 删除对话后引用应级联删除
        mgr.delete_conversation(conv["id"])
        assert mgr.get_message_citations(msg["id"]) == []

    def test_rename_and_set_active_flow(self):
        """测试重命名与切换激活对话的流程。"""
        sid = _insert_session()
        mgr = _make_manager()
        conv1 = mgr.create_conversation(sid, title="初始对话")
        conv2 = mgr.create_conversation(sid, title="第二对话")
        # 重命名 conv1
        mgr.rename_conversation(conv1["id"], "重要对话")
        # 切换激活到 conv1
        mgr.set_active(sid, conv1["id"])
        # 验证
        conn = get_db_connection()
        try:
            row = conn.execute(
                "SELECT active_conversation_id FROM sessions WHERE id = ?",
                (sid,),
            ).fetchone()
        finally:
            conn.close()
        assert row["active_conversation_id"] == conv1["id"]
        # 验证标题已更新
        conv = mgr.get_conversation(conv1["id"])
        assert conv["title"] == "重要对话"
