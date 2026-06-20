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

        # Agent 消息历史表（Task 5：v9.0 新增，用于 Agent 历史持久化）
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_messages (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                conversation_id TEXT,
                session_id TEXT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                reasoning TEXT,
                citations TEXT,
                metadata TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_messages_agent ON agent_messages(agent_id);"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_messages_conversation ON agent_messages(conversation_id);"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_messages_session ON agent_messages(session_id);"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_messages_created ON agent_messages(created_at);"
        )

        # 论文章节表（Task 9 / v9.0 新增，用于论文撰写阶段的章节持久化）
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS thesis_chapters (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                title TEXT,
                content TEXT,
                word_count INTEGER DEFAULT 0,
                chapter_order INTEGER DEFAULT 0,
                status TEXT DEFAULT 'draft',
                plagiarism_score REAL,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_thesis_chapters_session ON thesis_chapters(session_id);"
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


# ---------------- Agent 消息历史 CRUD（Task 5 / v9.0） ----------------


def save_agent_message(
    agent_id: str,
    role: str,
    content: str,
    conversation_id: str = None,
    session_id: str = None,
    reasoning: str = None,
    citations: list = None,
    metadata: dict = None,
) -> str:
    """保存一条 Agent 消息到数据库，返回消息 ID。

    Args:
        agent_id: Agent 标识（如 'orchestrator' / 'reasoner' 等）。
        role: 消息角色（'user' / 'assistant' / 'system'）。
        content: 消息内容。
        conversation_id: 关联的对话 ID（可选）。
        session_id: 关联的会话 ID（可选）。
        reasoning: 推理/思维链内容（可选）。
        citations: 引用列表（可选，将 JSON 序列化存储）。
        metadata: 额外元数据（可选，将 JSON 序列化存储）。

    Returns:
        生成的消息 ID（uuid4 字符串）。
    """
    from datetime import datetime
    from uuid import uuid4

    msg_id = str(uuid4())
    now = datetime.now().isoformat()

    citations_json = json.dumps(citations, ensure_ascii=False) if citations else None
    metadata_json = json.dumps(metadata, ensure_ascii=False) if metadata else None

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO agent_messages
                (id, agent_id, conversation_id, session_id, role, content,
                 reasoning, citations, metadata, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                msg_id,
                agent_id,
                conversation_id,
                session_id,
                role,
                content,
                reasoning,
                citations_json,
                metadata_json,
                now,
                now,
            ),
        )
        return msg_id


def load_agent_history(
    agent_id: str,
    conversation_id: str = None,
    session_id: str = None,
    limit: int = 100,
) -> list[dict]:
    """加载指定 Agent 的消息历史。

    可通过 conversation_id 或 session_id 进一步过滤；若两者均为空，
    则返回该 agent 的全部历史（受 limit 限制）。

    Args:
        agent_id: Agent 标识。
        conversation_id: 对话 ID 过滤（可选）。
        session_id: 会话 ID 过滤（可选）。
        limit: 返回的最大消息数，默认 100。

    Returns:
        消息字典列表，按 created_at 升序排列。每项包含 id / agent_id /
        conversation_id / session_id / role / content / reasoning /
        citations（已反序列化为 list）/ metadata（已反序列化为 dict）/
        created_at / updated_at。
    """
    sql = "SELECT * FROM agent_messages WHERE agent_id = ?"
    params: list = [agent_id]

    if conversation_id is not None:
        sql += " AND conversation_id = ?"
        params.append(conversation_id)
    if session_id is not None:
        sql += " AND session_id = ?"
        params.append(session_id)

    sql += " ORDER BY created_at ASC"
    if limit and limit > 0:
        sql += " LIMIT ?"
        params.append(limit)

    rows = fetch_all(sql, tuple(params))
    # 反序列化 citations / metadata 字段
    for row in rows:
        row["citations"] = _safe_json_loads(row.get("citations"))
        row["metadata"] = _safe_json_loads(row.get("metadata"))
    return rows


def load_all_agent_histories() -> dict:
    """加载所有 Agent 的消息历史，按 agent_id 分组。

    Returns:
        字典 {agent_id: [message_dict, ...]}，每个消息字典的字段与
        load_agent_history 返回值一致。
    """
    sql = "SELECT * FROM agent_messages ORDER BY agent_id, created_at ASC;"
    rows = fetch_all(sql)
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        row["citations"] = _safe_json_loads(row.get("citations"))
        row["metadata"] = _safe_json_loads(row.get("metadata"))
        grouped.setdefault(row["agent_id"], []).append(row)
    return grouped


def delete_agent_history(agent_id: str, conversation_id: str = None) -> int:
    """删除指定 Agent 的消息历史。

    Args:
        agent_id: Agent 标识。
        conversation_id: 若提供，仅删除该对话下的消息；否则删除该 agent 全部消息。

    Returns:
        被删除的行数。
    """
    if conversation_id is not None:
        sql = "DELETE FROM agent_messages WHERE agent_id = ? AND conversation_id = ?;"
        params = (agent_id, conversation_id)
    else:
        sql = "DELETE FROM agent_messages WHERE agent_id = ?;"
        params = (agent_id,)

    return execute_query(sql, params)


def _safe_json_loads(value):
    """安全反序列化 JSON 字符串，失败或为空时返回 None。"""
    if not value:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


# ---------------- 论文章节 CRUD（Task 9 / v9.0） ----------------


def save_chapter(
    session_id: str,
    title: str,
    content: str,
    word_count: int = 0,
    chapter_order: int = 0,
    status: str = "draft",
    plagiarism_score: float = None,
    chapter_id: str = None,
) -> str:
    """保存一个论文章节到数据库，返回章节 ID。

    Args:
        session_id: 关联的会话 ID。
        title: 章节标题。
        content: 章节内容（Markdown）。
        word_count: 字数。
        chapter_order: 章节序号。
        status: 章节状态（draft/revised/final）。
        plagiarism_score: 查重相似度评分（可选）。
        chapter_id: 指定的章节 ID，为 None 时自动生成。

    Returns:
        生成的章节 ID（uuid4 字符串）。
    """
    from datetime import datetime
    from uuid import uuid4

    chapter_id = chapter_id or str(uuid4())
    now = datetime.now().isoformat()

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO thesis_chapters
                (id, session_id, title, content, word_count, chapter_order,
                 status, plagiarism_score, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                chapter_id,
                session_id,
                title,
                content,
                word_count,
                chapter_order,
                status,
                plagiarism_score,
                now,
                now,
            ),
        )
        return chapter_id


def get_chapter(chapter_id: str) -> dict | None:
    """根据章节 ID 获取单个论文章节。

    Args:
        chapter_id: 章节 ID。

    Returns:
        章节字典或 None（不存在时）。
    """
    return fetch_one(
        "SELECT * FROM thesis_chapters WHERE id = ?;",
        (chapter_id,),
    )


def list_chapters(session_id: str) -> list[dict]:
    """列出指定会话下的所有论文章节，按 chapter_order 升序排列。

    Args:
        session_id: 会话 ID。

    Returns:
        章节字典列表。
    """
    return fetch_all(
        "SELECT * FROM thesis_chapters WHERE session_id = ? "
        "ORDER BY chapter_order ASC, created_at ASC;",
        (session_id,),
    )


def update_chapter(
    chapter_id: str,
    title: str = None,
    content: str = None,
    word_count: int = None,
    chapter_order: int = None,
    status: str = None,
    plagiarism_score: float = None,
) -> int:
    """更新指定论文章节的字段，返回受影响的行数。

    仅更新非 None 的字段。

    Args:
        chapter_id: 章节 ID。
        title: 新标题（可选）。
        content: 新内容（可选）。
        word_count: 新字数（可选）。
        chapter_order: 新序号（可选）。
        status: 新状态（可选）。
        plagiarism_score: 新查重评分（可选）。

    Returns:
        受影响的行数（0 表示章节不存在或无字段更新）。
    """
    from datetime import datetime

    updates: list[str] = []
    params: list = []
    field_map = {
        "title": title,
        "content": content,
        "word_count": word_count,
        "chapter_order": chapter_order,
        "status": status,
        "plagiarism_score": plagiarism_score,
    }
    for field, value in field_map.items():
        if value is not None:
            updates.append(f"{field} = ?")
            params.append(value)

    if not updates:
        return 0

    updates.append("updated_at = ?")
    params.append(datetime.now().isoformat())
    params.append(chapter_id)

    sql = (
        "UPDATE thesis_chapters SET "
        + ", ".join(updates)
        + " WHERE id = ?;"
    )
    return execute_query(sql, tuple(params))


def delete_chapter(chapter_id: str) -> int:
    """删除指定论文章节，返回受影响的行数。

    Args:
        chapter_id: 章节 ID。

    Returns:
        受影响的行数（0 表示章节不存在）。
    """
    return execute_query(
        "DELETE FROM thesis_chapters WHERE id = ?;",
        (chapter_id,),
    )


# ---------------- 消息检索（Task 12 / v9.0） ----------------


def search_messages(
    keyword: str = "",
    session_id: str = None,
    agent_id: str = None,
    stage: str = None,
    date_from: str = None,
    date_to: str = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """多条件检索 Agent 消息历史，返回分页结果。

    在 agent_messages 表上执行多过滤条件查询，LEFT JOIN sessions 表以获取
    会话标题（session_name），LEFT JOIN conversations 表以获取对话标题。
    关键词匹配使用 SQL LIKE（大小写不敏感，通过 LOWER 实现）。

    Args:
        keyword: 关键词，对 content 字段做 LIKE 匹配（空字符串表示不过滤）。
        session_id: 会话 ID 过滤（可选）。
        agent_id: Agent ID 过滤（可选）。
        stage: 阶段过滤（可选），匹配 metadata JSON 列中的 stage 字段。
        date_from: 起始日期（ISO 字符串，可选），按 created_at 过滤。
        date_to: 截止日期（ISO 字符串，可选），按 created_at 过滤。
        page: 页码，从 1 开始。
        page_size: 每页条数，默认 20。

    Returns:
        字典，包含 total / page / page_size / results。
        results 中每项含 id / conversation_id / session_id / session_name /
        conversation_title / agent_id / role / content / reasoning / created_at /
        stage。
    """
    # 构建动态 WHERE 子句
    conditions: list[str] = []
    params: list = []

    if keyword and keyword.strip():
        conditions.append("LOWER(am.content) LIKE LOWER(?)")
        params.append(f"%{keyword.strip()}%")
    if session_id:
        conditions.append("am.session_id = ?")
        params.append(session_id)
    if agent_id:
        conditions.append("am.agent_id = ?")
        params.append(agent_id)
    if stage:
        # stage 存储在 metadata JSON 列中，使用 LIKE 匹配
        conditions.append("am.metadata LIKE ?")
        params.append(f'%"stage"%:%"{stage}"%')
    if date_from:
        conditions.append("am.created_at >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("am.created_at <= ?")
        params.append(date_to + " 23:59:59" if len(date_to) == 10 else date_to)

    where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    # 分页参数
    page = max(1, int(page))
    page_size = max(1, min(100, int(page_size)))
    offset = (page - 1) * page_size

    sql = (
        "SELECT am.id, am.conversation_id, am.session_id, am.agent_id, am.role, "
        "am.content, am.reasoning, am.created_at, am.metadata, "
        "s.title AS session_name, c.title AS conversation_title "
        "FROM agent_messages am "
        "LEFT JOIN sessions s ON am.session_id = s.id "
        "LEFT JOIN conversations c ON am.conversation_id = c.id "
        f"{where_clause} "
        "ORDER BY am.created_at DESC, am.id DESC "
        "LIMIT ? OFFSET ?"
    )
    count_sql = f"SELECT COUNT(*) AS cnt FROM agent_messages am{where_clause}"

    with get_connection() as conn:
        cursor = conn.cursor()
        # 查询总数
        cursor.execute(count_sql, tuple(params))
        count_row = cursor.fetchone()
        total = count_row["cnt"] if count_row else 0

        # 查询当前页数据
        cursor.execute(sql, tuple(params + [page_size, offset]))
        rows = cursor.fetchall()

    results = []
    for row in rows:
        item = dict(row)
        # 从 metadata JSON 中提取 stage 字段
        metadata = _safe_json_loads(item.pop("metadata", None))
        item["stage"] = (metadata or {}).get("stage") if isinstance(metadata, dict) else None
        results.append(item)

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": results,
    }


def get_search_sessions() -> list[dict]:
    """获取所有会话的 ID 与标题，用于检索页面的会话筛选下拉框。

    仅返回存在 agent_messages 记录的会话，按创建时间降序排列。

    Returns:
        字典列表，每项含 id / title / created_at。
    """
    sql = (
        "SELECT DISTINCT s.id, s.title, s.created_at "
        "FROM sessions s "
        "INNER JOIN agent_messages am ON am.session_id = s.id "
        "ORDER BY s.created_at DESC"
    )
    return fetch_all(sql)


# 模块导入时自动初始化数据库
init_db()
