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
                cache_hit_rate REAL
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

        # 预算账本表
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS budget_ledger (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                model TEXT,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                total_tokens INTEGER,
                cost REAL,
                purpose TEXT,
                created_at TEXT,
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

        conn.commit()

    # 处理已存在数据库的表结构升级（新增字段等）
    migrate_db()


def migrate_db() -> None:
    """数据库迁移：为已存在的数据库补充新增字段。

    SQLite 不支持在 CREATE TABLE IF NOT EXISTS 时为已存在的表添加列，
    因此需要通过 ALTER TABLE 显式补齐 sessions 表的缓存相关字段。
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
