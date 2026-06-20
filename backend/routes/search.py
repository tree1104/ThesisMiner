"""会话历史检索 API 端点（Task 12 / v9.0）

提供对 agent_messages 表的多条件检索接口，支持关键词、时间范围、
会话、Agent 类型与阶段过滤，返回分页结果。
"""
import logging

from fastapi import APIRouter, Query

from backend import database

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/search/messages")
async def search_messages(
    q: str = Query("", description="关键词，对消息内容做全文匹配"),
    session_id: str = Query(None, description="会话 ID 过滤"),
    agent_id: str = Query(None, description="Agent ID 过滤"),
    stage: str = Query(None, description="阶段过滤"),
    date_from: str = Query(None, description="起始日期（YYYY-MM-DD）"),
    date_to: str = Query(None, description="截止日期（YYYY-MM-DD）"),
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
) -> dict:
    """多条件检索会话消息历史。

    所有过滤条件为 AND 逻辑，关键词为空时仅按其余条件过滤。
    返回分页结果，每条结果包含会话名称、Agent、时间戳与阶段信息。
    """
    try:
        return database.search_messages(
            keyword=q or "",
            session_id=session_id,
            agent_id=agent_id,
            stage=stage,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        logger.warning("消息检索失败", exc_info=True)
        return {
            "total": 0,
            "page": page,
            "page_size": page_size,
            "results": [],
            "error": str(e),
        }


@router.get("/api/search/sessions")
async def list_search_sessions() -> dict:
    """返回所有存在消息记录的会话列表，用于检索页面的会话筛选下拉框。"""
    try:
        sessions = database.get_search_sessions()
        return {"sessions": sessions, "count": len(sessions)}
    except Exception as e:
        logger.warning("会话列表查询失败", exc_info=True)
        return {"sessions": [], "count": 0, "error": str(e)}
