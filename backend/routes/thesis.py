"""论文撰写路由模块（Task 9 / v9.0）

提供论文撰写阶段的 API 端点，覆盖 THESIS_WRITING 阶段：
    - 大纲生成、章节撰写、章节修订
    - 查重检测、降重改写
    - 章节持久化 CRUD

所有端点挂载在 /api/thesis/{session_id}/... 路径下。
"""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.agents.thesis_writer import ThesisWriterAgent
from backend.ai.ai_proxy import check_api_configured
from backend import database

logger = logging.getLogger(__name__)
router = APIRouter(tags=["thesis"])


# ===== 请求模型 =====


class OutlineRequest(BaseModel):
    """大纲生成请求。"""

    proposal: str = ""
    degree: str = "master"


class ChapterWriteRequest(BaseModel):
    """章节撰写请求。"""

    chapter_title: str
    outline: str = ""
    references: list = []
    degree: str = "master"


class ReviseRequest(BaseModel):
    """章节修订请求。"""

    chapter_content: str
    feedback: str = ""


class PlagiarismRequest(BaseModel):
    """查重检测请求。"""

    chapter_content: str


class ReduceSimilarityRequest(BaseModel):
    """降重改写请求。"""

    chapter_content: str
    suggestions: list = []


class ChapterSaveRequest(BaseModel):
    """章节保存请求。"""

    title: str
    content: str = ""
    word_count: int = 0
    chapter_order: int = 0
    status: str = "draft"
    plagiarism_score: float = None


class ChapterUpdateRequest(BaseModel):
    """章节更新请求。"""

    title: str = None
    content: str = None
    word_count: int = None
    chapter_order: int = None
    status: str = None
    plagiarism_score: float = None


# ===== Agent 单例 =====

_agent_instance: ThesisWriterAgent | None = None


def _get_agent() -> ThesisWriterAgent:
    """获取 ThesisWriterAgent 单例实例。"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = ThesisWriterAgent()
    return _agent_instance


def _ensure_api_configured():
    """检查 AI API 是否已配置，未配置时抛出 400。"""
    if not check_api_configured():
        raise HTTPException(
            status_code=400,
            detail="AI API Key 未配置，请在设置页配置",
        )


# ===== 论文撰写端点 =====


@router.post("/api/thesis/{session_id}/outline")
async def generate_outline(session_id: str, body: OutlineRequest):
    """生成论文章节大纲。

    Args:
        session_id: 会话 ID。
        body: 大纲生成请求（proposal / degree）。

    Returns:
        包含 outline 字段的字典。
    """
    _ensure_api_configured()
    agent = _get_agent()
    try:
        outline = await agent.generate_outline(
            proposal=body.proposal,
            degree=body.degree,
            session_id=session_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.warning("大纲生成失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"大纲生成失败: {e}")
    return {"session_id": session_id, "outline": outline}


@router.post("/api/thesis/{session_id}/chapter")
async def write_chapter(session_id: str, body: ChapterWriteRequest):
    """撰写指定章节。

    Args:
        session_id: 会话 ID。
        body: 章节撰写请求（chapter_title / outline / references / degree）。

    Returns:
        包含 chapter 字段的字典。
    """
    _ensure_api_configured()
    agent = _get_agent()
    try:
        chapter = await agent.write_chapter(
            chapter_title=body.chapter_title,
            outline=body.outline,
            references=body.references,
            degree=body.degree,
            session_id=session_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.warning("章节撰写失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"章节撰写失败: {e}")
    return {"session_id": session_id, "chapter": chapter}


@router.post("/api/thesis/{session_id}/revise")
async def revise_chapter(session_id: str, body: ReviseRequest):
    """修订章节内容。

    Args:
        session_id: 会话 ID。
        body: 章节修订请求（chapter_content / feedback）。

    Returns:
        包含 chapter 字段的字典。
    """
    _ensure_api_configured()
    agent = _get_agent()
    try:
        chapter = await agent.revise_chapter(
            chapter_content=body.chapter_content,
            feedback=body.feedback,
            session_id=session_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.warning("章节修订失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"章节修订失败: {e}")
    return {"session_id": session_id, "chapter": chapter}


@router.post("/api/thesis/{session_id}/plagiarism")
async def check_plagiarism(session_id: str, body: PlagiarismRequest):
    """查重检测。

    Args:
        session_id: 会话 ID。
        body: 查重请求（chapter_content）。

    Returns:
        包含查重结果字段的字典（similarity_score / high_risk_sections / suggestions）。
    """
    _ensure_api_configured()
    agent = _get_agent()
    try:
        result = await agent.check_plagiarism(
            chapter_content=body.chapter_content,
            session_id=session_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.warning("查重检测失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"查重检测失败: {e}")
    return {"session_id": session_id, "result": result}


@router.post("/api/thesis/{session_id}/reduce-similarity")
async def reduce_similarity(session_id: str, body: ReduceSimilarityRequest):
    """降重改写。

    Args:
        session_id: 会话 ID。
        body: 降重请求（chapter_content / suggestions）。

    Returns:
        包含 chapter 字段的字典。
    """
    _ensure_api_configured()
    agent = _get_agent()
    try:
        chapter = await agent.reduce_similarity(
            chapter_content=body.chapter_content,
            suggestions=body.suggestions,
            session_id=session_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.warning("降重改写失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"降重改写失败: {e}")
    return {"session_id": session_id, "chapter": chapter}


# ===== 章节持久化端点 =====


@router.get("/api/thesis/{session_id}/chapters")
async def list_chapters(session_id: str):
    """列出指定会话下的所有论文章节。

    Args:
        session_id: 会话 ID。

    Returns:
        包含 chapters 列表的字典。
    """
    chapters = database.list_chapters(session_id)
    return {"session_id": session_id, "chapters": chapters}


@router.post("/api/thesis/{session_id}/chapters")
async def save_chapter(session_id: str, body: ChapterSaveRequest):
    """保存一个论文章节。

    Args:
        session_id: 会话 ID。
        body: 章节保存请求（title / content / word_count / chapter_order /
            status / plagiarism_score）。

    Returns:
        包含章节 ID 与章节详情的字典。
    """
    chapter_id = database.save_chapter(
        session_id=session_id,
        title=body.title,
        content=body.content,
        word_count=body.word_count,
        chapter_order=body.chapter_order,
        status=body.status,
        plagiarism_score=body.plagiarism_score,
    )
    chapter = database.get_chapter(chapter_id)
    return {"session_id": session_id, "chapter_id": chapter_id, "chapter": chapter}


@router.put("/api/thesis/{session_id}/chapters/{chapter_id}")
async def update_chapter(session_id: str, chapter_id: str, body: ChapterUpdateRequest):
    """更新指定论文章节。

    Args:
        session_id: 会话 ID。
        chapter_id: 章节 ID。
        body: 章节更新请求（仅更新非 None 字段）。

    Returns:
        包含更新结果与章节详情的字典。
    """
    existing = database.get_chapter(chapter_id)
    if not existing:
        raise HTTPException(status_code=404, detail="章节不存在")
    if existing.get("session_id") != session_id:
        raise HTTPException(status_code=404, detail="章节不存在")

    affected = database.update_chapter(
        chapter_id=chapter_id,
        title=body.title,
        content=body.content,
        word_count=body.word_count,
        chapter_order=body.chapter_order,
        status=body.status,
        plagiarism_score=body.plagiarism_score,
    )
    chapter = database.get_chapter(chapter_id)
    return {
        "session_id": session_id,
        "chapter_id": chapter_id,
        "updated": affected > 0,
        "chapter": chapter,
    }


@router.delete("/api/thesis/{session_id}/chapters/{chapter_id}")
async def delete_chapter(session_id: str, chapter_id: str):
    """删除指定论文章节。

    Args:
        session_id: 会话 ID。
        chapter_id: 章节 ID。

    Returns:
        包含删除结果的字典。
    """
    existing = database.get_chapter(chapter_id)
    if not existing:
        raise HTTPException(status_code=404, detail="章节不存在")
    if existing.get("session_id") != session_id:
        raise HTTPException(status_code=404, detail="章节不存在")

    affected = database.delete_chapter(chapter_id)
    return {
        "session_id": session_id,
        "chapter_id": chapter_id,
        "deleted": affected > 0,
    }
