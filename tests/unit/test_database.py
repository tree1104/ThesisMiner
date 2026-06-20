"""单元测试：数据库管理模块

测试 backend/database.py 的所有功能，包括：
- init_db 表结构创建
- migrate_db 数据库迁移
- get_connection / get_db_connection 连接管理
- sessions / proposals / lineage_nodes / lineage_edges 表
- budget_ledger / knowledge_cards 表
- conversations / conversation_messages / search_citations 表
- execute_query / execute_insert / fetch_one / fetch_all CRUD 辅助函数
- WAL 模式与外键约束
- cache_hit_rate 列迁移
"""
import json
import os
import sqlite3
import sys
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# 在导入 backend.database 前设置临时数据库
_TMP_DIR = tempfile.mkdtemp(prefix="thesisminer_db_test_")
_TMP_DB = os.path.join(_TMP_DIR, "test_db.db")

import backend.database as _db_module
_db_module.DB_PATH = _TMP_DB
_db_module.init_db()

from backend.database import (
    DB_PATH,
    init_db,
    migrate_db,
    get_connection,
    get_db_connection,
    execute_query,
    execute_insert,
    fetch_one,
    fetch_all,
    _ensure_data_dir,
)


# ===== init_db 测试 =====


class TestInitDb:
    """init_db 表结构创建测试"""

    def test_init_db_creates_sessions_table(self):
        """init_db 应创建 sessions 表"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='sessions';"
            )
            assert cursor.fetchone() is not None

    def test_init_db_creates_proposals_table(self):
        """init_db 应创建 proposals 表"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='proposals';"
            )
            assert cursor.fetchone() is not None

    def test_init_db_creates_lineage_nodes_table(self):
        """init_db 应创建 lineage_nodes 表"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='lineage_nodes';"
            )
            assert cursor.fetchone() is not None

    def test_init_db_creates_lineage_edges_table(self):
        """init_db 应创建 lineage_edges 表"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='lineage_edges';"
            )
            assert cursor.fetchone() is not None

    def test_init_db_creates_budget_ledger_table(self):
        """init_db 应创建 budget_ledger 表"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='budget_ledger';"
            )
            assert cursor.fetchone() is not None

    def test_init_db_creates_knowledge_cards_table(self):
        """init_db 应创建 knowledge_cards 表"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='knowledge_cards';"
            )
            assert cursor.fetchone() is not None

    def test_init_db_creates_conversations_table(self):
        """init_db 应创建 conversations 表"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='conversations';"
            )
            assert cursor.fetchone() is not None

    def test_init_db_creates_conversation_messages_table(self):
        """init_db 应创建 conversation_messages 表"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='conversation_messages';"
            )
            assert cursor.fetchone() is not None

    def test_init_db_creates_search_citations_table(self):
        """init_db 应创建 search_citations 表"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='search_citations';"
            )
            assert cursor.fetchone() is not None

    def test_init_db_idempotent(self):
        """init_db 多次调用不应报错"""
        init_db()
        init_db()
        # 验证表仍然存在
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='table';"
            )
            assert cursor.fetchone()[0] >= 9


# ===== sessions 表结构测试 =====


class TestSessionsTable:
    """sessions 表结构测试"""

    def test_sessions_has_id_column(self):
        """sessions 表应有 id 列"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(sessions);")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "id" in columns

    def test_sessions_has_cache_prefix_hash_column(self):
        """sessions 表应有 cache_prefix_hash 列"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(sessions);")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "cache_prefix_hash" in columns

    def test_sessions_has_cache_id_column(self):
        """sessions 表应有 cache_id 列"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(sessions);")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "cache_id" in columns

    def test_sessions_has_cache_hit_rate_column(self):
        """sessions 表应有 cache_hit_rate 列"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(sessions);")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "cache_hit_rate" in columns

    def test_sessions_has_active_conversation_id_column(self):
        """sessions 表应有 active_conversation_id 列"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(sessions);")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "active_conversation_id" in columns

    def test_sessions_has_degree_column(self):
        """sessions 表应有 degree 列"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(sessions);")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "degree" in columns

    def test_sessions_has_context_column(self):
        """sessions 表应有 context 列"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(sessions);")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "context" in columns


# ===== budget_ledger 表结构测试 =====


class TestBudgetLedgerTable:
    """budget_ledger 表结构测试"""

    def test_budget_ledger_has_cached_prompt_tokens(self):
        """budget_ledger 表应有 cached_prompt_tokens 列"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(budget_ledger);")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "cached_prompt_tokens" in columns

    def test_budget_ledger_has_cache_hit_rate(self):
        """budget_ledger 表应有 cache_hit_rate 列"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(budget_ledger);")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "cache_hit_rate" in columns

    def test_budget_ledger_has_required_columns(self):
        """budget_ledger 表应有所有必需列"""
        required = {
            "id", "session_id", "model", "prompt_tokens",
            "completion_tokens", "total_tokens", "cost", "purpose", "created_at",
        }
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(budget_ledger);")
            columns = {row["name"] for row in cursor.fetchall()}
            assert required.issubset(columns)


# ===== conversations 表结构测试 =====


class TestConversationsTable:
    """conversations 表结构测试"""

    def test_conversations_has_required_columns(self):
        """conversations 表应有所有必需列"""
        required = {"id", "session_id", "title", "agent_id", "created_at", "updated_at", "status"}
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(conversations);")
            columns = {row["name"] for row in cursor.fetchall()}
            assert required.issubset(columns)

    def test_conversation_messages_has_required_columns(self):
        """conversation_messages 表应有所有必需列"""
        required = {
            "id", "conversation_id", "agent_id", "role", "content",
            "reasoning", "search_results_json", "token_usage_json", "created_at",
        }
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(conversation_messages);")
            columns = {row["name"] for row in cursor.fetchall()}
            assert required.issubset(columns)

    def test_search_citations_has_required_columns(self):
        """search_citations 表应有所有必需列"""
        required = {
            "id", "message_id", "url", "title", "snippet",
            "source_domain", "favicon", "created_at",
        }
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(search_citations);")
            columns = {row["name"] for row in cursor.fetchall()}
            assert required.issubset(columns)


# ===== get_connection 测试 =====


class TestGetConnection:
    """get_connection 上下文管理器测试"""

    def test_get_connection_returns_connection(self):
        """get_connection 应返回 sqlite3.Connection"""
        with get_connection() as conn:
            assert isinstance(conn, sqlite3.Connection)

    def test_get_connection_sets_row_factory(self):
        """get_connection 应设置 row_factory 为 sqlite3.Row"""
        with get_connection() as conn:
            assert conn.row_factory is sqlite3.Row

    def test_get_connection_commits_on_success(self):
        """get_connection 成功时应自动 commit"""
        test_id = "test-commit-" + uuid.uuid4().hex
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO sessions (id, title) VALUES (?, ?);",
                (test_id, "测试"),
            )
        # 新连接验证数据已提交
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM sessions WHERE id = ?;", (test_id,))
            assert cursor.fetchone() is not None

    def test_get_connection_rolls_back_on_error(self):
        """get_connection 出错时应回滚"""
        test_id = "test-rollback-" + uuid.uuid4().hex
        with pytest.raises(Exception):
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO sessions (id, title) VALUES (?, ?);",
                    (test_id, "测试"),
                )
                # 故意触发错误
                raise Exception("测试回滚")
        # 验证数据已回滚
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM sessions WHERE id = ?;", (test_id,))
            assert cursor.fetchone() is None

    def test_get_connection_closes_after_use(self):
        """get_connection 使用后应关闭连接"""
        with get_connection() as conn:
            pass
        # 连接已关闭，再次操作应报错
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1;")


# ===== get_db_connection 测试 =====


class TestGetDbConnection:
    """get_db_connection 非上下文管理器版本测试"""

    def test_get_db_connection_returns_connection(self):
        """get_db_connection 应返回 Connection"""
        conn = get_db_connection()
        try:
            assert isinstance(conn, sqlite3.Connection)
        finally:
            conn.close()

    def test_get_db_connection_sets_row_factory(self):
        """get_db_connection 应设置 row_factory"""
        conn = get_db_connection()
        try:
            assert conn.row_factory is sqlite3.Row
        finally:
            conn.close()

    def test_get_db_connection_requires_manual_close(self):
        """get_db_connection 需手动关闭"""
        conn = get_db_connection()
        conn.execute("SELECT 1;")
        conn.close()
        # 关闭后操作应报错
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1;")

    def test_get_db_connection_can_commit(self):
        """get_db_connection 可手动 commit"""
        test_id = "test-manual-" + uuid.uuid4().hex
        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO sessions (id, title) VALUES (?, ?);",
                (test_id, "手动提交"),
            )
            conn.commit()
        finally:
            conn.close()
        # 验证数据已提交
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM sessions WHERE id = ?;", (test_id,))
            assert cursor.fetchone() is not None


# ===== migrate_db 测试 =====


class TestMigrateDb:
    """migrate_db 数据库迁移测试"""

    def test_migrate_db_idempotent(self):
        """migrate_db 多次调用不应报错"""
        migrate_db()
        migrate_db()

    def test_migrate_db_adds_cache_prefix_hash(self):
        """migrate_db 应确保 cache_prefix_hash 列存在"""
        migrate_db()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(sessions);")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "cache_prefix_hash" in columns

    def test_migrate_db_adds_cache_id(self):
        """migrate_db 应确保 cache_id 列存在"""
        migrate_db()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(sessions);")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "cache_id" in columns

    def test_migrate_db_adds_cache_hit_rate_to_sessions(self):
        """migrate_db 应确保 sessions.cache_hit_rate 列存在"""
        migrate_db()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(sessions);")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "cache_hit_rate" in columns

    def test_migrate_db_adds_active_conversation_id(self):
        """migrate_db 应确保 active_conversation_id 列存在"""
        migrate_db()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(sessions);")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "active_conversation_id" in columns

    def test_migrate_db_adds_cached_prompt_tokens(self):
        """migrate_db 应确保 budget_ledger.cached_prompt_tokens 列存在"""
        migrate_db()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(budget_ledger);")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "cached_prompt_tokens" in columns

    def test_migrate_db_adds_cache_hit_rate_to_ledger(self):
        """migrate_db 应确保 budget_ledger.cache_hit_rate 列存在"""
        migrate_db()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(budget_ledger);")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "cache_hit_rate" in columns


# ===== _ensure_data_dir 测试 =====


class TestEnsureDataDir:
    """_ensure_data_dir 目录创建测试"""

    def test_ensure_data_dir_creates_parent(self, tmp_path):
        """_ensure_data_dir 应创建父目录"""
        test_db = str(tmp_path / "subdir" / "test.db")
        original_path = _db_module.DB_PATH
        try:
            _db_module.DB_PATH = test_db
            _ensure_data_dir()
            assert os.path.isdir(str(tmp_path / "subdir"))
        finally:
            _db_module.DB_PATH = original_path

    def test_ensure_data_dir_idempotent(self):
        """_ensure_data_dir 多次调用不应报错"""
        _ensure_data_dir()
        _ensure_data_dir()


# ===== execute_insert 测试 =====


class TestExecuteInsert:
    """execute_insert 插入测试"""

    def test_execute_insert_returns_rowcount(self):
        """execute_insert 应返回受影响行数"""
        test_id = uuid.uuid4().hex
        rowcount = execute_insert("sessions", {
            "id": test_id,
            "title": "插入测试",
        })
        assert rowcount == 1

    def test_execute_insert_serializes_dict(self):
        """execute_insert 应自动序列化 dict 字段"""
        test_id = uuid.uuid4().hex
        execute_insert("sessions", {
            "id": test_id,
            "title": "序列化测试",
            "context": {"key": "value", "list": [1, 2, 3]},
        })
        row = fetch_one("SELECT * FROM sessions WHERE id = ?;", (test_id,))
        assert row is not None
        # context 应为 JSON 字符串
        context = json.loads(row["context"])
        assert context["key"] == "value"
        assert context["list"] == [1, 2, 3]

    def test_execute_insert_serializes_list(self):
        """execute_insert 应自动序列化 list 字段"""
        test_id = uuid.uuid4().hex
        execute_insert("sessions", {
            "id": test_id,
            "title": "列表序列化",
            "context": ["a", "b", "c"],
        })
        row = fetch_one("SELECT * FROM sessions WHERE id = ?;", (test_id,))
        context = json.loads(row["context"])
        assert context == ["a", "b", "c"]

    def test_execute_insert_with_string_value(self):
        """execute_insert 应正确处理字符串值"""
        test_id = uuid.uuid4().hex
        execute_insert("sessions", {
            "id": test_id,
            "title": "纯字符串",
        })
        row = fetch_one("SELECT * FROM sessions WHERE id = ?;", (test_id,))
        assert row["title"] == "纯字符串"

    def test_execute_insert_knowledge_card(self):
        """execute_insert 应能插入 knowledge_cards 表"""
        card_id = uuid.uuid4().hex
        execute_insert("knowledge_cards", {
            "id": card_id,
            "title": "测试卡片",
            "content": "卡片内容",
            "tags": ["标签1", "标签2"],
            "source": "测试",
            "created_at": "2026-01-01",
        })
        row = fetch_one("SELECT * FROM knowledge_cards WHERE id = ?;", (card_id,))
        assert row is not None
        assert row["title"] == "测试卡片"


# ===== execute_query 测试 =====


class TestExecuteQuery:
    """execute_query 写操作测试"""

    def test_execute_query_update(self):
        """execute_query 应执行 UPDATE"""
        test_id = uuid.uuid4().hex
        execute_insert("sessions", {"id": test_id, "title": "原标题"})
        rowcount = execute_query(
            "UPDATE sessions SET title = ? WHERE id = ?;",
            ("新标题", test_id),
        )
        assert rowcount == 1
        row = fetch_one("SELECT title FROM sessions WHERE id = ?;", (test_id,))
        assert row["title"] == "新标题"

    def test_execute_query_delete(self):
        """execute_query 应执行 DELETE"""
        test_id = uuid.uuid4().hex
        execute_insert("sessions", {"id": test_id, "title": "待删除"})
        rowcount = execute_query("DELETE FROM sessions WHERE id = ?;", (test_id,))
        assert rowcount == 1
        row = fetch_one("SELECT id FROM sessions WHERE id = ?;", (test_id,))
        assert row is None

    def test_execute_query_no_match(self):
        """execute_query 无匹配时应返回 0"""
        rowcount = execute_query(
            "DELETE FROM sessions WHERE id = ?;",
            ("nonexistent-id",),
        )
        assert rowcount == 0


# ===== fetch_one 测试 =====


class TestFetchOne:
    """fetch_one 单条查询测试"""

    def test_fetch_one_returns_dict(self):
        """fetch_one 应返回字典"""
        test_id = uuid.uuid4().hex
        execute_insert("sessions", {"id": test_id, "title": "查询测试"})
        row = fetch_one("SELECT * FROM sessions WHERE id = ?;", (test_id,))
        assert isinstance(row, dict)
        assert row["id"] == test_id

    def test_fetch_one_returns_none_when_not_found(self):
        """fetch_one 不存在时应返回 None"""
        row = fetch_one("SELECT * FROM sessions WHERE id = ?;", ("nonexistent",))
        assert row is None

    def test_fetch_one_with_params(self):
        """fetch_one 应正确使用参数"""
        test_id = uuid.uuid4().hex
        execute_insert("sessions", {"id": test_id, "title": "参数查询"})
        row = fetch_one(
            "SELECT * FROM sessions WHERE id = ? AND title = ?;",
            (test_id, "参数查询"),
        )
        assert row is not None
        assert row["title"] == "参数查询"


# ===== fetch_all 测试 =====


class TestFetchAll:
    """fetch_all 多条查询测试"""

    def test_fetch_all_returns_list(self):
        """fetch_all 应返回列表"""
        rows = fetch_all("SELECT * FROM sessions LIMIT 5;")
        assert isinstance(rows, list)

    def test_fetch_all_returns_dicts(self):
        """fetch_all 列表中每项应为字典"""
        test_id = uuid.uuid4().hex
        execute_insert("sessions", {"id": test_id, "title": "列表查询"})
        rows = fetch_all("SELECT * FROM sessions WHERE id = ?;", (test_id,))
        assert len(rows) == 1
        assert isinstance(rows[0], dict)

    def test_fetch_all_empty_result(self):
        """fetch_all 无结果时应返回空列表"""
        rows = fetch_all("SELECT * FROM sessions WHERE id = ?;", ("nonexistent",))
        assert rows == []

    def test_fetch_all_multiple_rows(self):
        """fetch_all 应返回多行"""
        for i in range(3):
            execute_insert("sessions", {
                "id": f"multi-{i}-{uuid.uuid4().hex}",
                "title": f"多行{i}",
            })
        rows = fetch_all("SELECT * FROM sessions WHERE title LIKE ?;", ("多行%",))
        assert len(rows) >= 3


# ===== 外键约束测试 =====


class TestForeignKeys:
    """外键约束测试"""

    def test_foreign_keys_enabled_in_get_connection(self):
        """get_connection 应启用外键约束"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys;")
            assert cursor.fetchone()[0] == 1

    def test_foreign_keys_enabled_in_get_db_connection(self):
        """get_db_connection 应启用外键约束"""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys;")
            assert cursor.fetchone()[0] == 1
        finally:
            conn.close()

    def test_cascade_delete_proposals(self):
        """删除 session 应级联删除关联 proposals"""
        session_id = uuid.uuid4().hex
        proposal_id = uuid.uuid4().hex
        execute_insert("sessions", {"id": session_id, "title": "级联测试"})
        execute_insert("proposals", {
            "id": proposal_id,
            "session_id": session_id,
            "title": "级联论题",
        })
        # 验证 proposal 存在
        assert fetch_one("SELECT * FROM proposals WHERE id = ?;", (proposal_id,)) is not None
        # 删除 session
        execute_query("DELETE FROM sessions WHERE id = ?;", (session_id,))
        # proposal 应被级联删除
        assert fetch_one("SELECT * FROM proposals WHERE id = ?;", (proposal_id,)) is None

    def test_cascade_delete_conversations(self):
        """删除 session 应级联删除关联 conversations"""
        session_id = uuid.uuid4().hex
        conv_id = str(uuid.uuid4())
        execute_insert("sessions", {"id": session_id, "title": "对话级联"})
        execute_insert("conversations", {
            "id": conv_id,
            "session_id": session_id,
            "title": "测试对话",
        })
        assert fetch_one("SELECT * FROM conversations WHERE id = ?;", (conv_id,)) is not None
        execute_query("DELETE FROM sessions WHERE id = ?;", (session_id,))
        assert fetch_one("SELECT * FROM conversations WHERE id = ?;", (conv_id,)) is None

    def test_cascade_delete_messages(self):
        """删除 conversation 应级联删除关联 messages"""
        session_id = uuid.uuid4().hex
        conv_id = str(uuid.uuid4())
        msg_id = str(uuid.uuid4())
        execute_insert("sessions", {"id": session_id, "title": "消息级联"})
        execute_insert("conversations", {
            "id": conv_id,
            "session_id": session_id,
            "title": "消息级联对话",
        })
        execute_insert("conversation_messages", {
            "id": msg_id,
            "conversation_id": conv_id,
            "role": "user",
            "content": "测试消息",
        })
        assert fetch_one("SELECT * FROM conversation_messages WHERE id = ?;", (msg_id,)) is not None
        execute_query("DELETE FROM conversations WHERE id = ?;", (conv_id,))
        assert fetch_one("SELECT * FROM conversation_messages WHERE id = ?;", (msg_id,)) is None

    def test_cascade_delete_citations(self):
        """删除 message 应级联删除关联 citations"""
        session_id = uuid.uuid4().hex
        conv_id = str(uuid.uuid4())
        msg_id = str(uuid.uuid4())
        cite_id = str(uuid.uuid4())
        execute_insert("sessions", {"id": session_id, "title": "引用级联"})
        execute_insert("conversations", {
            "id": conv_id,
            "session_id": session_id,
            "title": "引用级联对话",
        })
        execute_insert("conversation_messages", {
            "id": msg_id,
            "conversation_id": conv_id,
            "role": "assistant",
            "content": "带引用的回复",
        })
        execute_insert("search_citations", {
            "id": cite_id,
            "message_id": msg_id,
            "url": "https://example.com",
        })
        assert fetch_one("SELECT * FROM search_citations WHERE id = ?;", (cite_id,)) is not None
        execute_query("DELETE FROM conversation_messages WHERE id = ?;", (msg_id,))
        assert fetch_one("SELECT * FROM search_citations WHERE id = ?;", (cite_id,)) is None


# ===== WAL 模式测试 =====


class TestWalMode:
    """WAL 模式测试"""

    def test_wal_mode_in_get_connection(self):
        """get_connection 应启用 WAL 模式"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode;")
            mode = cursor.fetchone()[0]
            assert mode.lower() == "wal"

    def test_wal_mode_in_get_db_connection(self):
        """get_db_connection 应启用 WAL 模式"""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode;")
            mode = cursor.fetchone()[0]
            assert mode.lower() == "wal"
        finally:
            conn.close()


# ===== proposals 表测试 =====


class TestProposalsTable:
    """proposals 表测试"""

    def test_proposals_has_required_columns(self):
        """proposals 表应有所有必需列"""
        required = {
            "id", "session_id", "title", "inspiration_source",
            "problem_awareness", "research_significance", "literature_review_outline",
            "differentiation", "research_content", "feasibility_analysis",
            "confidence_score", "auto_rewritten", "created_at",
        }
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(proposals);")
            columns = {row["name"] for row in cursor.fetchall()}
            assert required.issubset(columns)

    def test_insert_proposal(self):
        """应能插入 proposal 记录"""
        session_id = uuid.uuid4().hex
        proposal_id = uuid.uuid4().hex
        execute_insert("sessions", {"id": session_id, "title": "论题测试"})
        execute_insert("proposals", {
            "id": proposal_id,
            "session_id": session_id,
            "title": "测试论题",
            "confidence_score": 0.85,
        })
        row = fetch_one("SELECT * FROM proposals WHERE id = ?;", (proposal_id,))
        assert row is not None
        assert row["title"] == "测试论题"


# ===== lineage 表测试 =====


class TestLineageTables:
    """lineage_nodes 与 lineage_edges 表测试"""

    def test_lineage_nodes_has_required_columns(self):
        """lineage_nodes 表应有所有必需列"""
        required = {"id", "node_type", "title", "abstract", "metadata", "created_at"}
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(lineage_nodes);")
            columns = {row["name"] for row in cursor.fetchall()}
            assert required.issubset(columns)

    def test_lineage_edges_has_required_columns(self):
        """lineage_edges 表应有所有必需列"""
        required = {"id", "source_id", "target_id", "relation_type", "weight", "created_at"}
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(lineage_edges);")
            columns = {row["name"] for row in cursor.fetchall()}
            assert required.issubset(columns)

    def test_insert_lineage_node(self):
        """应能插入 lineage_node"""
        node_id = uuid.uuid4().hex
        execute_insert("lineage_nodes", {
            "id": node_id,
            "node_type": "paper",
            "title": "测试节点",
            "abstract": "测试摘要",
        })
        row = fetch_one("SELECT * FROM lineage_nodes WHERE id = ?;", (node_id,))
        assert row is not None
        assert row["title"] == "测试节点"

    def test_insert_lineage_edge(self):
        """应能插入 lineage_edge"""
        source_id = uuid.uuid4().hex
        target_id = uuid.uuid4().hex
        edge_id = uuid.uuid4().hex
        execute_insert("lineage_nodes", {"id": source_id, "node_type": "paper", "title": "源"})
        execute_insert("lineage_nodes", {"id": target_id, "node_type": "paper", "title": "目标"})
        execute_insert("lineage_edges", {
            "id": edge_id,
            "source_id": source_id,
            "target_id": target_id,
            "relation_type": "cites",
            "weight": 1.0,
        })
        row = fetch_one("SELECT * FROM lineage_edges WHERE id = ?;", (edge_id,))
        assert row is not None
        assert row["relation_type"] == "cites"


# ===== knowledge_cards 表测试 =====


class TestKnowledgeCardsTable:
    """knowledge_cards 表测试"""

    def test_knowledge_cards_has_required_columns(self):
        """knowledge_cards 表应有所有必需列"""
        required = {"id", "title", "content", "tags", "source", "created_at"}
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(knowledge_cards);")
            columns = {row["name"] for row in cursor.fetchall()}
            assert required.issubset(columns)

    def test_insert_knowledge_card(self):
        """应能插入 knowledge_card"""
        card_id = uuid.uuid4().hex
        execute_insert("knowledge_cards", {
            "id": card_id,
            "title": "知识卡片",
            "content": "内容",
            "tags": ["AI", "测试"],
            "source": "测试",
        })
        row = fetch_one("SELECT * FROM knowledge_cards WHERE id = ?;", (card_id,))
        assert row is not None
        assert row["title"] == "知识卡片"
