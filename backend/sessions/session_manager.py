"""会话管理模块

提供会话的增删改查与上下文压缩能力，
所有持久化操作通过 backend.database 的 CRUD 函数完成。
"""
import datetime
import json
import uuid

from backend.database import (
    execute_insert,
    fetch_all,
    fetch_one,
    execute_query,
    get_connection,
)
from backend.models import SessionCreate, SessionResponse
from backend.sessions.conversation_manager import get_conversation_manager
from backend.sessions.dialogue_state_tracker import extract_state
from backend.sessions.dst_compactor import compact_history


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

    # v8.0：自动创建默认对话，并设为激活对话
    cm = get_conversation_manager()
    default_conv = cm.create_conversation(
        session_id, title="新对话", agent_id="orchestrator"
    )
    session["active_conversation_id"] = default_conv["id"]
    session["conversations"] = [default_conv]
    return session


def get_session(session_id: str) -> dict | None:
    """根据会话 ID 查询单个会话。

    v8.0：附带对话列表与激活对话详情。

    Args:
        session_id: 会话唯一标识。

    Returns:
        会话字典（context 字段已反序列化为 dict），不存在时返回 None。
        额外包含 conversations（对话列表）与 active_conversation（激活对话）。
    """
    row = fetch_one("SELECT * FROM sessions WHERE id = ?;", (session_id,))
    if row is None:
        return None
    # context 字段反序列化
    _deserialize_context(row)
    # v8.0：附加对话列表与激活对话
    cm = get_conversation_manager()
    row["conversations"] = cm.list_conversations(session_id)
    active_cid = row.get("active_conversation_id")
    row["active_conversation"] = cm.get_conversation(active_cid) if active_cid else None
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


def update_session_context_with_dst(session_id: str, context: dict) -> int:
    """使用 DST 压缩更新会话上下文。

    流程：
        1. 从 context 的 history 中提取 DST 状态槽（extract_state）。
        2. 调用 compact_history 将早期历史压缩为 DST 状态摘要消息。
        3. 将压缩后的 history 与 dst_state 写回 context。
        4. 调用 update_session_context 持久化。

    保留原始 update_session_context 与 compress_context 用于向后兼容。

    Args:
        session_id: 会话唯一标识。
        context: 原始上下文字典，应包含 history 列表。

    Returns:
        受影响的行数。
    """
    if not isinstance(context, dict):
        # 非字典类型直接走原逻辑
        return update_session_context(session_id, context)

    # 复制一份避免原地修改影响调用方
    new_context = dict(context)
    history = new_context.get("history", [])
    if not isinstance(history, list):
        history = []

    # 1. 提取 DST 状态槽
    dst_state = extract_state(history)

    # 2. 压缩历史为 DST 状态摘要 + 最近 2 轮原始对话
    compressed_history = compact_history(history, dst_state)

    # 3. 写回 context
    new_context["history"] = compressed_history
    new_context["dst_state"] = dst_state

    # 4. 持久化
    return update_session_context(session_id, new_context)


def delete_session(session_id: str) -> int:
    """删除会话及其关联的论题和预算记录（级联清理）。

    使用事务显式删除关联数据，即使外键级联未生效也能正确清理。

    Args:
        session_id: 会话唯一标识。

    Returns:
        受影响的行数（sessions 表删除的行数）。
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        # 显式删除关联数据（确保即使外键约束未生效也能清理）
        cursor.execute("DELETE FROM proposals WHERE session_id = ?;", (session_id,))
        cursor.execute("DELETE FROM budget_ledger WHERE session_id = ?;", (session_id,))
        cursor.execute("DELETE FROM sessions WHERE id = ?;", (session_id,))
        return cursor.rowcount


def update_cache_info(
    session_id: str, prefix_hash: str, cache_id: str, hit_rate: float
) -> int:
    """更新会话的缓存信息。

    将缓存前缀哈希、缓存 ID 与缓存命中率写入 sessions 表对应记录，
    同时刷新 updated_at 时间戳。

    Args:
        session_id: 会话唯一标识。
        prefix_hash: 缓存前缀哈希值。
        cache_id: 缓存唯一标识。
        hit_rate: 缓存命中率（取值范围 0-1）。

    Returns:
        受影响的行数。
    """
    now = datetime.datetime.now().isoformat()
    return execute_query(
        "UPDATE sessions SET cache_prefix_hash = ?, cache_id = ?, "
        "cache_hit_rate = ?, updated_at = ? WHERE id = ?;",
        (prefix_hash, cache_id, hit_rate, now, session_id),
    )


def get_cache_info(session_id: str) -> dict | None:
    """获取会话的缓存信息。

    Args:
        session_id: 会话唯一标识。

    Returns:
        包含 cache_prefix_hash、cache_id、cache_hit_rate 三个字段的字典；
        若会话不存在则返回 None。
    """
    row = fetch_one(
        "SELECT cache_prefix_hash, cache_id, cache_hit_rate "
        "FROM sessions WHERE id = ?;",
        (session_id,),
    )
    if row is None:
        return None
    return {
        "cache_prefix_hash": row.get("cache_prefix_hash"),
        "cache_id": row.get("cache_id"),
        "cache_hit_rate": row.get("cache_hit_rate"),
    }


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


# ---------------- v8.0 会话级重命名 ----------------


def rename_session(session_id: str, title: str) -> dict | None:
    """重命名会话标题。

    Args:
        session_id: 会话唯一标识。
        title: 新标题。

    Returns:
        更新后的会话字典，不存在时返回 None。
    """
    now = datetime.datetime.now().isoformat()
    execute_query(
        "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?;",
        (title, now, session_id),
    )
    return get_session(session_id)


# ---------------- v8.0 对话操作委托 ----------------
# 以下函数将对话操作委托给 ConversationManager，保持 session_manager 作为统一入口。


def create_conversation(
    session_id: str, title: str = "新对话", agent_id: str = "orchestrator"
) -> dict:
    """创建新对话（委托给 ConversationManager）。"""
    return get_conversation_manager().create_conversation(session_id, title, agent_id)


def list_conversations(session_id: str) -> list[dict]:
    """列出会话下的所有对话（委托给 ConversationManager）。"""
    return get_conversation_manager().list_conversations(session_id)


def get_conversation(conversation_id: str) -> dict | None:
    """获取对话详情（委托给 ConversationManager）。"""
    return get_conversation_manager().get_conversation(conversation_id)


def delete_conversation(conversation_id: str) -> bool:
    """删除对话（委托给 ConversationManager）。"""
    return get_conversation_manager().delete_conversation(conversation_id)


def rename_conversation(conversation_id: str, title: str) -> dict | None:
    """重命名对话（委托给 ConversationManager）。"""
    return get_conversation_manager().rename_conversation(conversation_id, title)


def set_active_conversation(session_id: str, conversation_id: str) -> bool:
    """设置会话的激活对话（委托给 ConversationManager）。"""
    return get_conversation_manager().set_active(session_id, conversation_id)


def add_conversation_message(
    conversation_id: str,
    role: str,
    content: str,
    agent_id: str = "",
    reasoning: str = "",
    search_results: list = None,
    token_usage: dict = None,
    citations: list = None,
) -> dict:
    """添加消息到对话（委托给 ConversationManager）。"""
    return get_conversation_manager().add_message(
        conversation_id,
        role,
        content,
        agent_id,
        reasoning,
        search_results,
        token_usage,
        citations,
    )


def get_conversation_messages(conversation_id: str, limit: int = 100) -> list[dict]:
    """获取对话的所有消息（委托给 ConversationManager）。"""
    return get_conversation_manager().get_messages(conversation_id, limit)


def get_conversation_context(
    conversation_id: str, max_tokens: int = 8000
) -> list[dict]:
    """获取上下文窗口（委托给 ConversationManager）。"""
    return get_conversation_manager().get_context_window(conversation_id, max_tokens)


def get_message_citations(message_id: str) -> list[dict]:
    """获取消息的引用（委托给 ConversationManager）。"""
    return get_conversation_manager().get_message_citations(message_id)
