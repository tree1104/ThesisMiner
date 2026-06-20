"""答辩准备路由模块（Task 10 / v9.0）

提供答辩准备阶段的 API 端点，覆盖 DEFENSE_PREP 阶段：
    - 答辩 PPT 大纲生成
    - 模拟答辩问题生成
    - 模拟答辩（针对问题生成回答）
    - 答辩开场白生成
    - 回答评估与反馈

所有端点挂载在 /api/defense/{session_id}/... 路径下。
"""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.agents.defense_agent import DefenseAgent
from backend.ai.ai_proxy import check_api_configured

logger = logging.getLogger(__name__)
router = APIRouter(tags=["defense"])


# ===== 请求模型 =====


class DefensePptRequest(BaseModel):
    """答辩 PPT 大纲生成请求。"""

    thesis_title: str = ""
    chapters: list = []
    degree: str = "master"


class DefenseQuestionsRequest(BaseModel):
    """答辩问题生成请求。"""

    thesis_title: str = ""
    chapters: list = []
    degree: str = "master"
    num_questions: int = 20


class DefenseSimulateRequest(BaseModel):
    """模拟答辩请求。"""

    question: str = ""
    thesis_content: str = ""


class DefenseSpeechRequest(BaseModel):
    """答辩话术生成请求。"""

    thesis_title: str = ""
    chapters: list = []
    degree: str = "master"
    duration_minutes: int = 10


class DefenseEvaluateRequest(BaseModel):
    """回答评估请求。"""

    answer: str = ""
    question: str = ""
    thesis_content: str = ""


# ===== Agent 单例 =====

_agent_instance: DefenseAgent | None = None


def _get_agent() -> DefenseAgent:
    """获取 DefenseAgent 单例实例。"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = DefenseAgent()
    return _agent_instance


def _ensure_api_configured():
    """检查 AI API 是否已配置，未配置时抛出 400。"""
    if not check_api_configured():
        raise HTTPException(
            status_code=400,
            detail="AI API Key 未配置，请在设置页配置",
        )


# ===== 答辩准备端点 =====


@router.post("/api/defense/{session_id}/ppt")
async def generate_defense_ppt(session_id: str, body: DefensePptRequest):
    """生成答辩 PPT 大纲。

    Args:
        session_id: 会话 ID。
        body: PPT 生成请求（thesis_title / chapters / degree）。

    Returns:
        包含 ppt 字段的字典。
    """
    _ensure_api_configured()
    agent = _get_agent()
    try:
        ppt = await agent.generate_defense_ppt(
            thesis_title=body.thesis_title,
            chapters=body.chapters,
            degree=body.degree,
            session_id=session_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.warning("答辩 PPT 生成失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"答辩 PPT 生成失败: {e}")
    return {"session_id": session_id, "ppt": ppt}


@router.post("/api/defense/{session_id}/questions")
async def generate_defense_questions(
    session_id: str, body: DefenseQuestionsRequest
):
    """生成答辩问题列表。

    Args:
        session_id: 会话 ID。
        body: 问题生成请求（thesis_title / chapters / degree / num_questions）。

    Returns:
        包含 questions 列表的字典。
    """
    _ensure_api_configured()
    agent = _get_agent()
    try:
        questions = await agent.generate_questions(
            thesis_title=body.thesis_title,
            chapters=body.chapters,
            degree=body.degree,
            num_questions=body.num_questions,
            session_id=session_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.warning("答辩问题生成失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"答辩问题生成失败: {e}")
    return {"session_id": session_id, "questions": questions}


@router.post("/api/defense/{session_id}/simulate")
async def simulate_defense(session_id: str, body: DefenseSimulateRequest):
    """模拟答辩，针对问题生成回答。

    Args:
        session_id: 会话 ID。
        body: 模拟答辩请求（question / thesis_content）。

    Returns:
        包含 answer 字段的字典。
    """
    _ensure_api_configured()
    agent = _get_agent()
    try:
        answer = await agent.simulate_defense(
            question=body.question,
            thesis_content=body.thesis_content,
            session_id=session_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.warning("模拟答辩失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"模拟答辩失败: {e}")
    return {"session_id": session_id, "answer": answer}


@router.post("/api/defense/{session_id}/speech")
async def generate_defense_speech(
    session_id: str, body: DefenseSpeechRequest
):
    """生成答辩开场白。

    Args:
        session_id: 会话 ID。
        body: 话术生成请求（thesis_title / chapters / degree / duration_minutes）。

    Returns:
        包含 speech 字段的字典。
    """
    _ensure_api_configured()
    agent = _get_agent()
    try:
        speech = await agent.generate_defense_speech(
            thesis_title=body.thesis_title,
            chapters=body.chapters,
            degree=body.degree,
            duration_minutes=body.duration_minutes,
            session_id=session_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.warning("答辩话术生成失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"答辩话术生成失败: {e}")
    return {"session_id": session_id, "speech": speech}


@router.post("/api/defense/{session_id}/evaluate")
async def evaluate_answer(session_id: str, body: DefenseEvaluateRequest):
    """评估用户回答并给出反馈。

    Args:
        session_id: 会话 ID。
        body: 评估请求（answer / question / thesis_content）。

    Returns:
        包含 result 字段的字典（score / strengths / weaknesses / suggestions /
        model_answer）。
    """
    _ensure_api_configured()
    agent = _get_agent()
    try:
        result = await agent.evaluate_answer(
            answer=body.answer,
            question=body.question,
            thesis_content=body.thesis_content,
            session_id=session_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.warning("回答评估失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"回答评估失败: {e}")
    return {"session_id": session_id, "result": result}
