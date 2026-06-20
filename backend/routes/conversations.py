"""对话管理 API 端点

提供对话的创建、查询、重命名、删除、消息管理与上下文窗口接口，
以及 Agent 列表查询接口（SubTask 7.5-7.6）。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.sessions.conversation_manager import get_conversation_manager

router = APIRouter()


class ConversationCreate(BaseModel):
    """创建对话请求。"""

    title: str = "新对话"
    agent_id: str = "orchestrator"


class ConversationRename(BaseModel):
    """重命名对话请求。"""

    title: str


class MessageCreate(BaseModel):
    """添加消息请求。"""

    role: str
    content: str
    agent_id: str = ""
    reasoning: str = ""
    search_results: list = []
    token_usage: dict = {}
    citations: list = []


@router.post("/api/sessions/{sid}/conversations")
async def create_conversation(sid: str, body: ConversationCreate):
    """在指定会话下创建新对话。"""
    cm = get_conversation_manager()
    return cm.create_conversation(sid, body.title, body.agent_id)


@router.get("/api/sessions/{sid}/conversations")
async def list_conversations(sid: str):
    """列出指定会话下的所有对话。"""
    cm = get_conversation_manager()
    return {"conversations": cm.list_conversations(sid)}


@router.get("/api/conversations/{cid}")
async def get_conversation(cid: str):
    """获取对话详情。"""
    cm = get_conversation_manager()
    conv = cm.get_conversation(cid)
    if not conv:
        raise HTTPException(404, "对话不存在")
    return conv


@router.put("/api/conversations/{cid}")
async def rename_conversation(cid: str, body: ConversationRename):
    """重命名对话。"""
    cm = get_conversation_manager()
    conv = cm.rename_conversation(cid, body.title)
    if not conv:
        raise HTTPException(404, "对话不存在")
    return conv


@router.delete("/api/conversations/{cid}")
async def delete_conversation(cid: str):
    """删除对话（级联删除消息与引用）。"""
    cm = get_conversation_manager()
    if not cm.delete_conversation(cid):
        raise HTTPException(404, "对话不存在")
    return {"deleted": True}


@router.get("/api/conversations/{cid}/messages")
async def get_messages(cid: str, limit: int = 100):
    """获取对话的所有消息。"""
    cm = get_conversation_manager()
    return {"messages": cm.get_messages(cid, limit)}


@router.post("/api/conversations/{cid}/messages")
async def add_message(cid: str, body: MessageCreate):
    """添加消息到对话。"""
    cm = get_conversation_manager()
    return cm.add_message(
        cid, body.role, body.content, body.agent_id,
        body.reasoning, body.search_results, body.token_usage, body.citations
    )


@router.get("/api/conversations/{cid}/context")
async def get_context(cid: str, max_tokens: int = 8000):
    """获取对话的上下文窗口（含 DST 压缩）。"""
    cm = get_conversation_manager()
    return {"context": cm.get_context_window(cid, max_tokens)}


@router.put("/api/sessions/{sid}/active-conversation")
async def set_active_conversation(sid: str, cid: str):
    """设置会话的激活对话。

    Args:
        sid: 会话 ID。
        cid: 要激活的对话 ID（查询参数）。
    """
    cm = get_conversation_manager()
    cm.set_active(sid, cid)
    return {"session_id": sid, "active_conversation_id": cid}


@router.get("/api/conversations/{cid}/citations")
async def get_conversation_citations(cid: str):
    """获取对话下所有消息的引用（聚合查询）。"""
    cm = get_conversation_manager()
    messages = cm.get_messages(cid, limit=500)
    result = []
    for msg in messages:
        cites = cm.get_message_citations(msg["id"])
        if cites:
            result.append({"message_id": msg["id"], "citations": cites})
    return {"conversation_id": cid, "citations": result}


@router.get("/api/agents")
async def list_agents():
    """列出所有已注册 Agent 的元数据（SubTask 7.6）。"""
    from backend.agents.agent_registry import list_agents as _list_agents
    return {"agents": _list_agents()}
