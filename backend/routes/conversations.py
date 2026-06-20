"""对话管理 API 端点

提供对话的创建、查询、重命名、删除、消息管理与上下文窗口接口，
以及 Agent 列表查询接口（SubTask 7.5-7.6）。
v9.0 Task 7：新增 SSE 流式输出端点 /api/conversations/{cid}/stream。
"""
import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.sessions.conversation_manager import get_conversation_manager

logger = logging.getLogger(__name__)
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


class StreamRequest(BaseModel):
    """v9.0 Task 7：流式对话请求。"""

    message: str
    agent_id: str = ""
    deep_thinking: bool = False
    web_search: bool = False


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


@router.post("/api/conversations/{cid}/stream")
async def stream_conversation(cid: str, body: StreamRequest):
    """v9.0 Task 7：流式对话端点。

    接收用户消息，调用 Agent 以流式方式生成回复，通过 SSE 实时推送
    推理过程与正文内容。流结束后将完整回复持久化到数据库。

    SSE 事件格式：
        data: {"type": "reasoning", "content": "..."}\n\n
        data: {"type": "content", "content": "..."}\n\n
        data: {"type": "done", "content": "...", "reasoning": "...",
               "citations": [...]}\n\n

    Args:
        cid: 对话 ID。
        body: 流式请求体（message / agent_id / deep_thinking / web_search）。

    Returns:
        StreamingResponse，media_type 为 text/event-stream。
    """
    cm = get_conversation_manager()
    conv = cm.get_conversation(cid)
    if not conv:
        raise HTTPException(404, "对话不存在")

    # 确定 Agent：优先使用请求体指定的 agent_id，回退到对话绑定的 agent_id
    agent_id = body.agent_id or conv.get("agent_id") or "orchestrator"

    # 延迟导入以避免循环依赖
    from backend.agents.agent_registry import get_agent
    from backend.ai.ai_proxy import call_llm_stream
    from backend.ai.streaming import format_stream_as_sse

    try:
        agent = get_agent(agent_id)
    except ValueError:
        raise HTTPException(404, f"Agent '{agent_id}' 未注册")

    message = body.message or ""
    if not message.strip():
        raise HTTPException(400, "消息内容不能为空")

    # 加载该对话的历史消息到 Agent 内存上下文
    try:
        agent.load_history(conversation_id=cid)
    except Exception:
        logger.debug("加载 Agent 历史失败", exc_info=True)

    # 持久化用户消息：
    # - agent_messages 表（Agent 历史恢复，由 agent.save_message 处理）
    # - conversation_messages 表（对话消息列表，供前端查询，由 cm.add_message 处理）
    try:
        agent.save_message("user", message, conversation_id=cid)
    except Exception:
        logger.debug("持久化用户消息到 agent_messages 失败", exc_info=True)
    try:
        cm.add_message(cid, "user", message, agent_id=agent_id)
    except Exception:
        logger.debug("持久化用户消息到 conversation_messages 失败", exc_info=True)

    # 构建包含近期上下文的用户提示（最近 6 条历史 + 当前消息）
    user_prompt = _build_contextual_prompt(agent, message)

    # 调用流式 LLM
    stream = call_llm_stream(
        system_prompt=agent.system_prompt,
        user_prompt=user_prompt,
        model=agent.model_id or None,
        temperature=agent.temperature,
        purpose=agent_id,
        deep_thinking=body.deep_thinking,
        web_search=body.web_search,
    )

    async def event_generator():
        """SSE 事件生成器：流式输出 + 完成后持久化助手回复。"""
        content_parts: list = []
        reasoning_parts: list = []
        try:
            async for sse_chunk in format_stream_as_sse(stream):
                # 解析已发射的事件用于最终持久化
                try:
                    payload = json.loads(sse_chunk[len("data: "):].strip())
                    if payload.get("type") == "content":
                        content_parts.append(payload.get("content", ""))
                    elif payload.get("type") == "reasoning":
                        reasoning_parts.append(payload.get("content", ""))
                    elif payload.get("type") == "done":
                        # done 事件中已包含完整内容，覆盖累积值
                        content_parts = [payload.get("content", "")]
                        reasoning_parts = [payload.get("reasoning", "")]
                except Exception:
                    pass
                yield sse_chunk
        except Exception as exc:
            yield (
                "data: " +
                json.dumps(
                    {"type": "error", "content": str(exc)},
                    ensure_ascii=False,
                ) +
                "\n\n"
            )
            return

        # 流结束后持久化助手回复：
        # - agent_messages 表（Agent 历史恢复）
        # - conversation_messages 表（对话消息列表，供前端查询）
        full_content = "".join(content_parts)
        full_reasoning = "".join(reasoning_parts)
        if full_content:
            try:
                agent.save_message(
                    "assistant",
                    full_content,
                    reasoning=full_reasoning or None,
                    conversation_id=cid,
                )
            except Exception:
                logger.debug("持久化助手消息到 agent_messages 失败", exc_info=True)
            try:
                cm.add_message(
                    cid,
                    "assistant",
                    full_content,
                    agent_id=agent_id,
                    reasoning=full_reasoning or "",
                )
            except Exception:
                logger.debug("持久化助手消息到 conversation_messages 失败", exc_info=True)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _build_contextual_prompt(agent, current_message: str) -> str:
    """构建包含近期对话上下文的用户提示。

    将 Agent 内存中除系统提示外的最近若干条消息拼接到当前消息前，
    使 LLM 能感知对话历史（call_llm_stream 不接受 messages 列表）。

    Args:
        agent: Agent 实例。
        current_message: 当前用户消息。

    Returns:
        拼接了上下文的用户提示字符串。
    """
    context = agent.get_context()
    # 跳过系统提示，取最近 6 条交互
    history = [m for m in context if m.get("role") != "system"][-6:]
    if not history:
        return current_message

    lines = ["[近期对话上下文]"]
    for m in history:
        role = m.get("role", "user")
        content = m.get("content", "")
        label = "用户" if role == "user" else "助手"
        lines.append(f"{label}: {content}")
    lines.append("")
    lines.append("[当前消息]")
    lines.append(current_message)
    return "\n".join(lines)
