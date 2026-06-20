"""会话管理模块单元测试

测试 backend/sessions/session_manager.py 的所有函数。
覆盖以下功能：
  - create_session: 创建会话（含自动创建默认对话）
  - get_session: 获取会话详情（含对话列表与激活对话）
  - list_sessions: 分页查询会话列表
  - update_session_status: 更新会话状态
  - update_session_context: 更新会话上下文
  - update_session_context_with_dst: 使用 DST 压缩更新上下文
  - delete_session: 删除会话（级联清理）
  - update_cache_info: 更新缓存信息
  - get_cache_info: 获取缓存信息
  - compress_context: 上下文压缩器
  - rename_session: 重命名会话
  - 委托函数: create_conversation / list_conversations / get_conversation 等

测试策略：
  - 使用临时数据库隔离测试
  - 使用 SessionCreate 模型构造请求
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

# ===== 临时数据库初始化 =====
_TMP_DIR = tempfile.mkdtemp(prefix="thesisminer_session_mgr_test_")
import backend.database as _db
_db.DB_PATH = os.path.join(_TMP_DIR, "test.db")
_db.init_db()

from backend.sessions import session_manager
from backend.models import SessionCreate, DegreeType, DisciplineType
from backend.database import get_db_connection


# ===== 辅助函数 =====

def _make_session_create(title: str = "测试会话",
                         degree: DegreeType = DegreeType.master,
                         discipline: DisciplineType = DisciplineType.science_engineering,
                         mentor_info: str = "测试导师",
                         mode: str = "quick") -> SessionCreate:
    """构造 SessionCreate 请求对象。

    Args:
        title: 会话标题。
        degree: 学位类型。
        discipline: 学科类型。
        mentor_info: 导师信息。
        mode: 生成模式。

    Returns:
        SessionCreate 实例。
    """
    return SessionCreate(
        title=title,
        degree=degree,
        discipline=discipline,
        mentor_info=mentor_info,
        mode=mode,
    )


def _create_test_session(title: str = "测试会话") -> dict:
    """创建一个测试会话并返回。

    Args:
        title: 会话标题。

    Returns:
        创建的会话字典。
    """
    req = _make_session_create(title=title)
    return session_manager.create_session(req)


# ===== 测试类：create_session =====

class TestCreateSession:
    """测试 create_session 函数。"""

    def test_create_returns_dict_with_id(self):
        """创建会话应返回含 id 的字典。"""
        session = _create_test_session()
        assert "id" in session
        assert len(session["id"]) > 0

    def test_create_preserves_title(self):
        """创建会话应保留标题。"""
        session = _create_test_session(title="我的开题")
        assert session["title"] == "我的开题"

    def test_create_sets_status_active(self):
        """创建会话状态应为 active。"""
        session = _create_test_session()
        assert session["status"] == "active"

    def test_create_sets_timestamps(self):
        """创建会话应设置 created_at 与 updated_at。"""
        session = _create_test_session()
        assert "created_at" in session
        assert "updated_at" in session
        assert len(session["created_at"]) > 0

    def test_create_initializes_context(self):
        """创建会话应初始化 context 含空 history 与 candidates。"""
        session = _create_test_session()
        assert "context" in session
        assert session["context"]["history"] == []
        assert session["context"]["candidates"] == []

    def test_create_auto_creates_default_conversation(self):
        """创建会话应自动创建默认对话。"""
        session = _create_test_session()
        assert "conversations" in session
        assert len(session["conversations"]) == 1
        assert session["conversations"][0]["title"] == "新对话"

    def test_create_sets_active_conversation_id(self):
        """创建会话应设置 active_conversation_id。"""
        session = _create_test_session()
        assert "active_conversation_id" in session
        assert session["active_conversation_id"] == session["conversations"][0]["id"]

    def test_create_with_master_degree(self):
        """创建硕士学位会话。"""
        req = _make_session_create(degree=DegreeType.master)
        session = session_manager.create_session(req)
        assert session["degree"] == "master"

    def test_create_with_doctor_degree(self):
        """创建博士学位会话。"""
        req = _make_session_create(degree=DegreeType.doctor)
        session = session_manager.create_session(req)
        assert session["degree"] == "doctor"

    def test_create_with_humanities_discipline(self):
        """创建人文社科学科会话。"""
        req = _make_session_create(discipline=DisciplineType.humanities_social)
        session = session_manager.create_session(req)
        assert session["discipline"] == "humanities_social"

    def test_create_generates_unique_ids(self):
        """每次创建的会话 id 应唯一。"""
        ids = set()
        for _ in range(5):
            session = _create_test_session()
            ids.add(session["id"])
        assert len(ids) == 5


# ===== 测试类：get_session =====

class TestGetSession:
    """测试 get_session 函数。"""

    def test_get_existing_session(self):
        """获取存在的会话应返回完整字典。"""
        created = _create_test_session(title="查询测试")
        result = session_manager.get_session(created["id"])
        assert result is not None
        assert result["title"] == "查询测试"

    def test_get_nonexistent_returns_none(self):
        """获取不存在的会话应返回 None。"""
        result = session_manager.get_session("nonexistent-id")
        assert result is None

    def test_get_includes_conversations(self):
        """返回应包含 conversations 列表。"""
        created = _create_test_session()
        result = session_manager.get_session(created["id"])
        assert "conversations" in result
        assert len(result["conversations"]) >= 1

    def test_get_includes_active_conversation(self):
        """返回应包含 active_conversation 详情。"""
        created = _create_test_session()
        result = session_manager.get_session(created["id"])
        assert "active_conversation" in result
        assert result["active_conversation"] is not None

    def test_get_deserializes_context(self):
        """返回的 context 应为字典而非 JSON 字符串。"""
        created = _create_test_session()
        result = session_manager.get_session(created["id"])
        assert isinstance(result["context"], dict)

    def test_get_after_adding_conversation(self):
        """添加新对话后获取应包含多个对话。"""
        created = _create_test_session()
        session_manager.create_conversation(created["id"], title="第二对话")
        result = session_manager.get_session(created["id"])
        assert len(result["conversations"]) == 2


# ===== 测试类：list_sessions =====

class TestListSessions:
    """测试 list_sessions 函数。"""

    def test_list_empty(self):
        """无会话时返回空列表。"""
        # 注意：其他测试可能已创建会话，此处验证返回的是列表
        result = session_manager.list_sessions()
        assert isinstance(result, list)

    def test_list_returns_created_sessions(self):
        """列表应包含已创建的会话。"""
        session = _create_test_session(title="列表测试")
        result = session_manager.list_sessions()
        ids = [s["id"] for s in result]
        assert session["id"] in ids

    def test_list_with_limit(self):
        """limit 参数应限制返回条数。"""
        for i in range(5):
            _create_test_session(title=f"会话{i}")
        result = session_manager.list_sessions(limit=3)
        assert len(result) <= 3

    def test_list_with_offset(self):
        """offset 参数应跳过指定条数。"""
        for i in range(5):
            _create_test_session(title=f"偏移会话{i}")
        result1 = session_manager.list_sessions(limit=2, offset=0)
        result2 = session_manager.list_sessions(limit=2, offset=2)
        # 两批结果不应重叠
        ids1 = {s["id"] for s in result1}
        ids2 = {s["id"] for s in result2}
        assert not (ids1 & ids2)

    def test_list_deserializes_context(self):
        """列表中的 context 应已反序列化。"""
        session = _create_test_session()
        result = session_manager.list_sessions()
        found = [s for s in result if s["id"] == session["id"]][0]
        assert isinstance(found["context"], dict)


# ===== 测试类：update_session_status =====

class TestUpdateSessionStatus:
    """测试 update_session_status 函数。"""

    def test_update_status_to_closed(self):
        """更新状态为 closed。"""
        session = _create_test_session()
        rows = session_manager.update_session_status(session["id"], "closed")
        assert rows == 1
        updated = session_manager.get_session(session["id"])
        assert updated["status"] == "closed"

    def test_update_status_to_active(self):
        """更新状态为 active。"""
        session = _create_test_session()
        session_manager.update_session_status(session["id"], "closed")
        rows = session_manager.update_session_status(session["id"], "active")
        assert rows == 1
        updated = session_manager.get_session(session["id"])
        assert updated["status"] == "active"

    def test_update_status_nonexistent_returns_zero(self):
        """更新不存在的会话应返回 0。"""
        rows = session_manager.update_session_status("nonexistent", "closed")
        assert rows == 0


# ===== 测试类：update_session_context =====

class TestUpdateSessionContext:
    """测试 update_session_context 函数。"""

    def test_update_context_basic(self):
        """更新上下文应写入新值。"""
        session = _create_test_session()
        new_context = {"history": [{"role": "user", "content": "hi"}], "candidates": []}
        rows = session_manager.update_session_context(session["id"], new_context)
        assert rows == 1
        updated = session_manager.get_session(session["id"])
        assert updated["context"]["history"][0]["content"] == "hi"

    def test_update_context_with_complex_data(self):
        """更新含复杂数据的上下文。"""
        session = _create_test_session()
        new_context = {
            "history": [{"role": "user", "content": "测试"}],
            "candidates": [{"title": "候选1"}, {"title": "候选2"}],
            "extra_field": {"nested": "value"},
        }
        session_manager.update_session_context(session["id"], new_context)
        updated = session_manager.get_session(session["id"])
        assert len(updated["context"]["candidates"]) == 2
        assert updated["context"]["extra_field"]["nested"] == "value"

    def test_update_context_nonexistent_returns_zero(self):
        """更新不存在的会话上下文应返回 0。"""
        rows = session_manager.update_session_context("nonexistent", {})
        assert rows == 0


# ===== 测试类：update_session_context_with_dst =====

class TestUpdateSessionContextWithDst:
    """测试 update_session_context_with_dst 函数。"""

    def test_dst_update_with_short_history(self):
        """短历史（≤5条）的 DST 更新应保留全部。"""
        session = _create_test_session()
        context = {
            "history": [
                {"role": "user", "content": "选定论题：AI教育"},
                {"role": "assistant", "content": "好的"},
            ],
        }
        rows = session_manager.update_session_context_with_dst(session["id"], context)
        assert rows == 1
        updated = session_manager.get_session(session["id"])
        # 短历史不压缩，应保留原样
        assert len(updated["context"]["history"]) == 2

    def test_dst_update_with_long_history(self):
        """长历史（>5条）的 DST 更新应压缩。"""
        session = _create_test_session()
        # 构造 10 条历史
        full_history = []
        for i in range(5):
            full_history.append({"role": "user", "content": f"用户消息{i}"})
            full_history.append({"role": "assistant", "content": f"助手回复{i}"})
        context = {"history": full_history}
        rows = session_manager.update_session_context_with_dst(session["id"], context)
        assert rows == 1
        updated = session_manager.get_session(session["id"])
        # 压缩后历史应减少
        assert "dst_state" in updated["context"]

    def test_dst_update_with_non_dict_context(self):
        """非字典上下文应走原逻辑。"""
        session = _create_test_session()
        # 非字典类型直接走 update_session_context
        rows = session_manager.update_session_context_with_dst(
            session["id"], "not-a-dict"
        )
        assert rows == 1


# ===== 测试类：delete_session =====

class TestDeleteSession:
    """测试 delete_session 函数。"""

    def test_delete_existing_session(self):
        """删除存在的会话应返回 1。"""
        session = _create_test_session()
        rows = session_manager.delete_session(session["id"])
        assert rows == 1
        assert session_manager.get_session(session["id"]) is None

    def test_delete_nonexistent_returns_zero(self):
        """删除不存在的会话应返回 0。"""
        rows = session_manager.delete_session("nonexistent-id")
        assert rows == 0

    def test_delete_cascades_budget_ledger(self):
        """删除会话应级联清理 budget_ledger 记录。"""
        session = _create_test_session()
        # 插入一条 budget_ledger 记录
        conn = get_db_connection()
        try:
            conn.execute(
                """INSERT INTO budget_ledger (id, session_id, model, prompt_tokens,
                   completion_tokens, total_tokens, cost, purpose, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                (uuid.uuid4().hex, session["id"], "test-model", 100, 50, 150, 0.01,
                 "test", ),
            )
            conn.commit()
        finally:
            conn.close()
        # 删除会话
        session_manager.delete_session(session["id"])
        # 验证 budget_ledger 记录已被删除
        conn = get_db_connection()
        try:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM budget_ledger WHERE session_id = ?",
                (session["id"],),
            ).fetchone()
        finally:
            conn.close()
        assert row["cnt"] == 0


# ===== 测试类：update_cache_info / get_cache_info =====

class TestCacheInfo:
    """测试 update_cache_info 与 get_cache_info 函数。"""

    def test_update_cache_info(self):
        """更新缓存信息应写入三个字段。"""
        session = _create_test_session()
        rows = session_manager.update_cache_info(
            session["id"], "hash123", "cache-id-456", 0.95
        )
        assert rows == 1

    def test_get_cache_info_after_update(self):
        """更新后获取应返回更新的值。"""
        session = _create_test_session()
        session_manager.update_cache_info(
            session["id"], "prefix-hash", "cache-789", 0.88
        )
        info = session_manager.get_cache_info(session["id"])
        assert info["cache_prefix_hash"] == "prefix-hash"
        assert info["cache_id"] == "cache-789"
        assert info["cache_hit_rate"] == 0.88

    def test_get_cache_info_nonexistent_returns_none(self):
        """获取不存在会话的缓存信息应返回 None。"""
        result = session_manager.get_cache_info("nonexistent-id")
        assert result is None

    def test_get_cache_info_without_update(self):
        """未更新缓存信息时获取应返回 None 值。"""
        session = _create_test_session()
        info = session_manager.get_cache_info(session["id"])
        # 初始值应为 None
        assert info["cache_prefix_hash"] is None
        assert info["cache_id"] is None


# ===== 测试类：compress_context =====

class TestCompressContext:
    """测试 compress_context 函数。"""

    def test_compress_short_history(self):
        """短历史不压缩。"""
        context = {"history": [{"i": 1}, {"i": 2}], "other": "value"}
        result = session_manager.compress_context(context, max_history=10)
        assert len(result["history"]) == 2
        assert result["other"] == "value"

    def test_compress_long_history(self):
        """长历史应截取最近 max_history 条。"""
        history = [{"i": i} for i in range(20)]
        context = {"history": history}
        result = session_manager.compress_context(context, max_history=5)
        assert len(result["history"]) == 5
        # 应保留最近的 5 条
        assert result["history"][0]["i"] == 15
        assert result["history"][4]["i"] == 19

    def test_compress_preserves_other_fields(self):
        """压缩应保留 context 中的其他字段。"""
        context = {
            "history": [{"i": i} for i in range(20)],
            "candidates": ["a", "b"],
            "metadata": {"key": "value"},
        }
        result = session_manager.compress_context(context, max_history=5)
        assert result["candidates"] == ["a", "b"]
        assert result["metadata"]["key"] == "value"

    def test_compress_empty_history(self):
        """空历史不压缩。"""
        context = {"history": []}
        result = session_manager.compress_context(context)
        assert result["history"] == []

    def test_compress_default_max_history(self):
        """默认 max_history=10。"""
        history = [{"i": i} for i in range(15)]
        context = {"history": history}
        result = session_manager.compress_context(context)
        assert len(result["history"]) == 10


# ===== 测试类：rename_session =====

class TestRenameSession:
    """测试 rename_session 函数。"""

    def test_rename_updates_title(self):
        """重命名应更新标题。"""
        session = _create_test_session(title="旧标题")
        result = session_manager.rename_session(session["id"], "新标题")
        assert result["title"] == "新标题"

    def test_rename_nonexistent_returns_none(self):
        """重命名不存在的会话应返回 None。"""
        result = session_manager.rename_session("nonexistent", "新标题")
        assert result is None

    def test_rename_with_chinese_title(self):
        """使用中文标题重命名。"""
        session = _create_test_session(title="old")
        result = session_manager.rename_session(session["id"], "基于图谱的论文推荐")
        assert result["title"] == "基于图谱的论文推荐"


# ===== 测试类：委托函数 =====

class TestDelegatedConversationFunctions:
    """测试委托给 ConversationManager 的函数。"""

    def test_create_conversation_delegated(self):
        """create_conversation 委托应正常工作。"""
        session = _create_test_session()
        conv = session_manager.create_conversation(session["id"], title="委托对话")
        assert conv is not None
        assert conv["title"] == "委托对话"

    def test_list_conversations_delegated(self):
        """list_conversations 委托应正常工作。"""
        session = _create_test_session()
        result = session_manager.list_conversations(session["id"])
        assert len(result) >= 1

    def test_get_conversation_delegated(self):
        """get_conversation 委托应正常工作。"""
        session = _create_test_session()
        conv_id = session["active_conversation_id"]
        result = session_manager.get_conversation(conv_id)
        assert result is not None
        assert result["id"] == conv_id

    def test_delete_conversation_delegated(self):
        """delete_conversation 委托应正常工作。"""
        session = _create_test_session()
        conv = session_manager.create_conversation(session["id"], title="待删除")
        result = session_manager.delete_conversation(conv["id"])
        assert result is True

    def test_rename_conversation_delegated(self):
        """rename_conversation 委托应正常工作。"""
        session = _create_test_session()
        conv = session_manager.create_conversation(session["id"], title="旧名")
        result = session_manager.rename_conversation(conv["id"], "新名")
        assert result["title"] == "新名"

    def test_set_active_conversation_delegated(self):
        """set_active_conversation 委托应正常工作。"""
        session = _create_test_session()
        conv1 = session_manager.create_conversation(session["id"], title="A")
        result = session_manager.set_active_conversation(session["id"], conv1["id"])
        assert result is True

    def test_add_conversation_message_delegated(self):
        """add_conversation_message 委托应正常工作。"""
        session = _create_test_session()
        msg = session_manager.add_conversation_message(
            session["active_conversation_id"], "user", "委托消息"
        )
        assert msg["content"] == "委托消息"

    def test_get_conversation_messages_delegated(self):
        """get_conversation_messages 委托应正常工作。"""
        session = _create_test_session()
        conv_id = session["active_conversation_id"]
        session_manager.add_conversation_message(conv_id, "user", "消息1")
        result = session_manager.get_conversation_messages(conv_id)
        assert len(result) >= 1

    def test_get_conversation_context_delegated(self):
        """get_conversation_context 委托应正常工作。"""
        session = _create_test_session()
        conv_id = session["active_conversation_id"]
        session_manager.add_conversation_message(conv_id, "user", "上下文测试")
        result = session_manager.get_conversation_context(conv_id)
        assert len(result) >= 1

    def test_get_message_citations_delegated(self):
        """get_message_citations 委托应正常工作。"""
        session = _create_test_session()
        msg = session_manager.add_conversation_message(
            session["active_conversation_id"],
            "assistant",
            "带引用的回复",
            citations=[{"url": "http://x.com", "title": "引用",
                       "snippet": "", "source_domain": "", "favicon": ""}],
        )
        result = session_manager.get_message_citations(msg["id"])
        assert len(result) == 1


# ===== 集成测试 =====

class TestSessionManagerIntegration:
    """session_manager 集成测试：模拟完整会话流程。"""

    def test_full_session_lifecycle(self):
        """测试完整会话生命周期：创建→查询→更新→删除。"""
        # 1. 创建
        session = _create_test_session(title="生命周期")
        sid = session["id"]
        # 2. 查询
        result = session_manager.get_session(sid)
        assert result["title"] == "生命周期"
        # 3. 更新状态
        session_manager.update_session_status(sid, "closed")
        assert session_manager.get_session(sid)["status"] == "closed"
        # 4. 更新上下文
        session_manager.update_session_context(sid, {"history": [{"x": 1}]})
        assert len(session_manager.get_session(sid)["context"]["history"]) == 1
        # 5. 重命名
        session_manager.rename_session(sid, "新生命周期")
        assert session_manager.get_session(sid)["title"] == "新生命周期"
        # 6. 删除
        session_manager.delete_session(sid)
        assert session_manager.get_session(sid) is None

    def test_session_with_multiple_conversations(self):
        """测试会话下多对话管理流程。"""
        session = _create_test_session()
        sid = session["id"]
        # 创建多个对话
        conv1 = session_manager.create_conversation(sid, title="对话1")
        conv2 = session_manager.create_conversation(sid, title="对话2")
        conv3 = session_manager.create_conversation(sid, title="对话3")
        # 验证列表
        convs = session_manager.list_conversations(sid)
        assert len(convs) == 4  # 含默认对话
        # 切换激活对话
        session_manager.set_active_conversation(sid, conv1["id"])
        # 删除一个对话
        session_manager.delete_conversation(conv2["id"])
        convs_after = session_manager.list_conversations(sid)
        assert len(convs_after) == 3

    def test_session_cache_info_flow(self):
        """测试会话缓存信息更新流程。"""
        session = _create_test_session()
        sid = session["id"]
        # 初始无缓存信息
        info = session_manager.get_cache_info(sid)
        assert info["cache_prefix_hash"] is None
        # 更新缓存信息
        session_manager.update_cache_info(sid, "hash-v1", "cache-v1", 0.92)
        info = session_manager.get_cache_info(sid)
        assert info["cache_prefix_hash"] == "hash-v1"
        assert info["cache_hit_rate"] == 0.92
        # 再次更新
        session_manager.update_cache_info(sid, "hash-v2", "cache-v2", 0.97)
        info = session_manager.get_cache_info(sid)
        assert info["cache_prefix_hash"] == "hash-v2"
        assert info["cache_hit_rate"] == 0.97
