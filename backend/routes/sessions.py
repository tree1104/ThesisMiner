"""会话管理路由模块

提供会话的创建、查询、详情获取、删除与状态更新接口。
所有持久化操作委托给 session_manager 完成。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.database import fetch_one
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
    """分页查询会话列表，附带对话轮数统计。"""
    try:
        sessions = session_manager.list_sessions(limit, offset)
        # 为每个会话统计对话轮数（budget_ledger 中的调用次数）
        for s in sessions:
            session_id = s.get("id")
            if session_id:
                row = fetch_one(
                    "SELECT COUNT(*) as cnt FROM budget_ledger WHERE session_id = ?;",
                    (session_id,),
                )
                s["dialog_rounds"] = row["cnt"] if row else 0
            else:
                s["dialog_rounds"] = 0
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
    """获取会话详情，附带对话轮数统计。"""
    try:
        session = session_manager.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="会话不存在")
        # 统计对话轮数（budget_ledger 中的调用次数）
        row = fetch_one(
            "SELECT COUNT(*) as cnt FROM budget_ledger WHERE session_id = ?;",
            (session_id,),
        )
        session["dialog_rounds"] = row["cnt"] if row else 0
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
