"""会话管理模块

提供会话的增删改查与上下文压缩能力，
所有持久化操作通过 backend.database 的 CRUD 函数完成。
"""
import datetime
import json
import uuid

from backend.database import execute_insert, fetch_all, fetch_one, execute_query
from backend.models import SessionCreate, SessionResponse


def create_session(req: SessionCreate) -> dict:
    """创建新会话并写入 sessions 表。

    生成 uuid 与时间戳，初始状态为 active，初始上下文包含空的
    history 与 candidates 列表。

    Args:
        req: 会话创建请求，包含标题、学位、学科、导师信息等。

    Returns:
        完整的会话字典（含 id、时间戳、初始 context）。
    """
    session_id = uuid.uuid4().hex
    now = datetime.datetime.now().isoformat()
    # 枚举类型取字符串值存储
    degree = req.degree.value if hasattr(req.degree, "value") else str(req.degree)
    discipline = (
        req.discipline.value
        if hasattr(req.discipline, "value")
        else str(req.discipline)
    )
    context = {"history": [], "candidates": []}

    session = {
        "id": session_id,
        "title": req.title,
        "degree": degree,
        "discipline": discipline,
        "mentor_info": req.mentor_info,
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "context": context,  # execute_insert 会自动序列化为 JSON
    }

    execute_insert("sessions", session)
    return session


def get_session(session_id: str) -> dict | None:
    """根据会话 ID 查询单个会话。

    Args:
        session_id: 会话唯一标识。

    Returns:
        会话字典（context 字段已反序列化为 dict），不存在时返回 None。
    """
    row = fetch_one("SELECT * FROM sessions WHERE id = ?;", (session_id,))
    if row is None:
        return None
    # context 字段反序列化
    _deserialize_context(row)
    return row


def list_sessions(limit: int = 20, offset: int = 0) -> list[dict]:
    """查询会话列表，按创建时间降序排列。

    Args:
        limit: 返回条数上限，默认 20。
        offset: 偏移量，默认 0。

    Returns:
        会话字典列表（每条的 context 字段已反序列化）。
    """
    rows = fetch_all(
        "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ? OFFSET ?;",
        (limit, offset),
    )
    for row in rows:
        _deserialize_context(row)
    return rows


def update_session_status(session_id: str, status: str) -> int:
    """更新会话状态。

    Args:
        session_id: 会话唯一标识。
        status: 新状态值（如 active、closed）。

    Returns:
        受影响的行数。
    """
    now = datetime.datetime.now().isoformat()
    return execute_query(
        "UPDATE sessions SET status = ?, updated_at = ? WHERE id = ?;",
        (status, now, session_id),
    )


def update_session_context(session_id: str, context: dict) -> int:
    """更新会话上下文，同时刷新 updated_at。

    Args:
        session_id: 会话唯一标识。
        context: 新的上下文字典，将被 JSON 序列化后存储。

    Returns:
        受影响的行数。
    """
    now = datetime.datetime.now().isoformat()
    context_json = json.dumps(context, ensure_ascii=False)
    return execute_query(
        "UPDATE sessions SET context = ?, updated_at = ? WHERE id = ?;",
        (context_json, now, session_id),
    )


def delete_session(session_id: str) -> int:
    """删除会话。

    注意：此处仅删除 sessions 表中的记录，关联的 proposals 表数据
    不会在此函数中清理（简单实现）。

    Args:
        session_id: 会话唯一标识。

    Returns:
        受影响的行数。
    """
    return execute_query("DELETE FROM sessions WHERE id = ?;", (session_id,))


def compress_context(context: dict, max_history: int = 10) -> dict:
    """上下文压缩器：保留最近 max_history 条历史记录。

    当 history 列表长度超过 max_history 时，截取最近的 max_history 条；
    其他字段保持不变。

    Args:
        context: 原始上下文字典，应包含 history 列表。
        max_history: 保留的最大历史条数，默认 10。

    Returns:
        压缩后的上下文字典（原地修改并返回）。
    """
    history = context.get("history", [])
    if isinstance(history, list) and len(history) > max_history:
        # 保留最近 max_history 条
        context["history"] = history[-max_history:]
    return context


def _deserialize_context(row: dict) -> None:
    """将行中的 context 字段从 JSON 字符串反序列化为字典（原地修改）。

    Args:
        row: 数据库行字典。
    """
    raw = row.get("context")
    if isinstance(raw, str):
        try:
            row["context"] = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            # 解析失败时保留原始字符串
            row["context"] = raw
