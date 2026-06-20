"""SQLite 数据库管理模块

使用 sqlite3 标准库实现轻量级持久化，启用 WAL 模式以支持并发读取。
模块导入时自动初始化所有表结构。
"""
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

# 数据库文件路径
DB_PATH = "data/thesis_miner.db"


def _ensure_data_dir() -> None:
    """确保 data 目录存在。"""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """获取数据库连接的上下文管理器。

    启用 WAL 模式以支持并发读，check_same_thread=False 允许跨线程使用。
    """
    _ensure_data_dir()
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        # 启用外键约束，确保级联删除生效（每次连接都需要设置）
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_db_connection() -> sqlite3.Connection:
    """获取数据库连接（非上下文管理器版本，Task 2.4 新增）。

    与 get_connection 不同，此函数返回原始连接，调用方需手动 commit/close。
    启用 WAL 模式与外键约束，设置 row_factory 为 sqlite3.Row。
    适用于需要手动控制事务生命周期的场景（如 cache_monitor）。

    Returns:
        配置好的 sqlite3.Connection 对象，调用方负责关闭。
    """
    _ensure_data_dir()
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """创建所有表结构（若不存在）。"""
    _ensure_data_dir()
    with get_connection() as conn:
        cursor = conn.cursor()
        # 启用外键约束，确保级联删除生效（每次连接都需要设置）
        cursor.execute("PRAGMA foreign_keys = ON;")

        # 会话表
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT,
                degree TEXT,
                discipline TEXT,
                mentor_info TEXT,
                status TEXT,
                created_at TEXT,
                updated_at TEXT,
                context TEXT,
                cache_prefix_hash TEXT,
                cache_id TEXT,
                cache_hit_rate REAL,
                active_conversation_id TEXT
            );
            """
        )

        # 论题提案表
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS proposals (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                title TEXT,
                inspiration_source TEXT,
                problem_awareness TEXT,
                research_significance TEXT,
                literature_review_outline TEXT,
                differentiation TEXT,
                research_content TEXT,
                feasibility_analysis TEXT,
                confidence_score REAL,
                auto_rewritten INTEGER,
                created_at TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );
            """
        )

        # 学脉节点表
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS lineage_nodes (
                id TEXT PRIMARY KEY,
                node_type TEXT,
                title TEXT,
                abstract TEXT,
                metadata TEXT,
                created_at TEXT
            );
            """
        )

        # 学脉边表
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS lineage_edges (
                id TEXT PRIMARY KEY,
                source_id TEXT,
                target_id TEXT,
                relation_type TEXT,
                weight REAL,
                created_at TEXT,
                FOREIGN KEY (source_id) REFERENCES lineage_nodes(id),
                FOREIGN KEY (target_id) REFERENCES lineage_nodes(id)
            );
            """
        )

        # 预算账本表（v8.0 新增 cache_hit_rate 列用于缓存命中率监控）
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS budget_ledger (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                model TEXT,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                total_tokens INTEGER,
                cached_prompt_tokens INTEGER DEFAULT 0,
                cost REAL,
                purpose TEXT,
                created_at TEXT,
                cache_hit_rate REAL DEFAULT 0,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );
            """
        )

        # 知识卡片表
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_cards (
                id TEXT PRIMARY KEY,
                title TEXT,
                content TEXT,
                tags TEXT,
                source TEXT,
                created_at TEXT
            );
            """
        )

        # 对话表（Task 6.1：v8.0 新增，用于多轮对话管理）
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                title TEXT DEFAULT '新对话',
                agent_id TEXT DEFAULT 'orchestrator',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                status TEXT DEFAULT 'active',
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );
            """
        )

        # 对话消息表（Task 6.2：v8.0 新增，存储对话中的每条消息）
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                agent_id TEXT,
                role TEXT NOT NULL,
                content TEXT,
                reasoning TEXT,
                search_results_json TEXT,
                token_usage_json TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            );
            """
        )

        # 搜索引用表（Task 6.3 / Task 10：v8.0 新增，存储消息中的引用链接）
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS search_citations (
                id TEXT PRIMARY KEY,
                message_id TEXT NOT NULL,
                url TEXT NOT NULL,
                title TEXT,
                snippet TEXT,
                source_domain TEXT,
                favicon TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (message_id) REFERENCES conversation_messages(id) ON DELETE CASCADE
            );
            """
        )

        conn.commit()

    # 处理已存在数据库的表结构升级（新增字段等）
    migrate_db()


def migrate_db() -> None:
    """数据库迁移：为已存在的数据库补充新增字段。

    SQLite 不支持在 CREATE TABLE IF NOT EXISTS 时为已存在的表添加列，
    因此需要通过 ALTER TABLE 显式补齐 sessions 表的缓存相关字段，
    以及 budget_ledger 表的 cache_hit_rate 字段（Task 2.5），
    sessions 表的 active_conversation_id 字段（Task 6.4）。
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        # 查询 sessions 表现有的列名
        cursor.execute("PRAGMA table_info(sessions);")
        existing_columns = {row["name"] for row in cursor.fetchall()}

        # 缺失则补齐 cache_prefix_hash 列
        if "cache_prefix_hash" not in existing_columns:
            cursor.execute(
                "ALTER TABLE sessions ADD COLUMN cache_prefix_hash TEXT;"
            )
        # 缺失则补齐 cache_id 列
        if "cache_id" not in existing_columns:
            cursor.execute("ALTER TABLE sessions ADD COLUMN cache_id TEXT;")
        # 缺失则补齐 cache_hit_rate 列
        if "cache_hit_rate" not in existing_columns:
            cursor.execute("ALTER TABLE sessions ADD COLUMN cache_hit_rate REAL;")
        # Task 6.4：缺失则补齐 active_conversation_id 列
        if "active_conversation_id" not in existing_columns:
            cursor.execute(
                "ALTER TABLE sessions ADD COLUMN active_conversation_id TEXT;"
            )

        # 检查 budget_ledger 表是否有 cached_prompt_tokens 列（v7.0 三类 token 统计）
        cursor.execute("PRAGMA table_info(budget_ledger);")
        ledger_columns = {row["name"] for row in cursor.fetchall()}
        if "cached_prompt_tokens" not in ledger_columns:
            cursor.execute(
                "ALTER TABLE budget_ledger ADD COLUMN cached_prompt_tokens INTEGER DEFAULT 0;"
            )
        # Task 2.5：缺失则补齐 cache_hit_rate 列（用于缓存命中率监控）
        if "cache_hit_rate" not in ledger_columns:
            cursor.execute(
                "ALTER TABLE budget_ledger ADD COLUMN cache_hit_rate REAL DEFAULT 0;"
            )

        conn.commit()


# ---------------- CRUD 辅助函数 ----------------


def execute_query(sql: str, params: tuple = ()) -> int:
    """执行写操作（INSERT/UPDATE/DELETE），返回受影响的行数。"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return cursor.rowcount


def execute_insert(table: str, data: dict) -> int:
    """向指定表插入一行数据，返回受影响的行数。

    Args:
        table: 目标表名。
        data: 列名到值的映射，JSON 字段会自动序列化。
    """
    # 对 dict/list 类型字段进行 JSON 序列化
    processed_data: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, (dict, list)):
            processed_data[key] = json.dumps(value, ensure_ascii=False)
        else:
            processed_data[key] = value

    columns = list(processed_data.keys())
    placeholders = ", ".join(["?"] * len(columns))
    column_str = ", ".join(columns)
    sql = f"INSERT INTO {table} ({column_str}) VALUES ({placeholders});"
    values = tuple(processed_data[col] for col in columns)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, values)
        return cursor.rowcount


def fetch_one(sql: str, params: tuple = ()) -> dict | None:
    """查询单条记录，返回字典或 None。"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)


def fetch_all(sql: str, params: tuple = ()) -> list[dict]:
    """查询多条记录，返回字典列表。"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


# 模块导入时自动初始化数据库
init_db()
