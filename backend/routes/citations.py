"""引用相关 API 端点

提供按消息 ID 查询引用列表的接口（Task 10.4）。
"""
from fastapi import APIRouter

from backend.database import get_db_connection

router = APIRouter(tags=["citations"])


@router.get("/api/messages/{mid}/citations")
async def get_message_citations(mid: str) -> dict:
    """获取指定消息的引用列表（Task 10.4）。

    Args:
        mid: 消息 ID（conversation_messages.id）。

    Returns:
        包含 message_id 与 citations 列表的字典。
    """
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT id, url, title, snippet, source_domain, favicon "
            "FROM search_citations WHERE message_id = ? ORDER BY id",
            (mid,),
        ).fetchall()
        return {
            "message_id": mid,
            "citations": [dict(r) for r in rows],
        }
    finally:
        conn.close()
