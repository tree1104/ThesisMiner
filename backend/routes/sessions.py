"""会话管理路由模块

提供会话的创建、查询、详情获取、删除与状态更新接口。
所有持久化操作委托给 session_manager 完成。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.models import ApiResponse, SessionCreate
from backend.sessions import session_manager

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class SessionStatusUpdate(BaseModel):
    """会话状态更新请求。"""

    status: str


@router.post("")
async def create_session(req: SessionCreate) -> dict:
    """创建新会话。"""
    try:
        session = session_manager.create_session(req)
        return session
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("")
async def list_sessions(limit: int = 20, offset: int = 0) -> dict:
    """分页查询会话列表。"""
    try:
        sessions = session_manager.list_sessions(limit, offset)
        return {
            "sessions": sessions,
            "count": len(sessions),
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/{session_id}")
async def get_session(session_id: str) -> dict:
    """获取会话详情。"""
    try:
        session = session_manager.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="会话不存在")
        return session
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.delete("/{session_id}")
async def delete_session(session_id: str) -> ApiResponse:
    """删除指定会话。"""
    try:
        session_manager.delete_session(session_id)
        return ApiResponse(success=True, message="会话已删除")
    except Exception as e:
        return ApiResponse(success=False, error=str(e))


@router.patch("/{session_id}/status")
async def update_session_status(
    session_id: str, req: SessionStatusUpdate
) -> ApiResponse:
    """更新会话状态。"""
    try:
        session_manager.update_session_status(session_id, req.status)
        return ApiResponse(success=True, message="状态已更新")
    except Exception as e:
        return ApiResponse(success=False, error=str(e))
