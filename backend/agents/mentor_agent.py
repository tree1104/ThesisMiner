"""Mentor 智能体模块

负责从导师视角评审论题提案，包含单次评审、批量评审与兜底方案。
所有 AI 相关导入采用延迟导入以避免循环依赖。
"""


async def review_proposal(proposal: dict, degree: str = "master", session_id: str = None) -> dict:
    """从导师视角评审单个论题提案。

    流程：检查 API 配置 → 构建评审提示 → 调用 LLM → 整理评审结果。

    Args:
        proposal: 待评审的论题提案字典。
        degree: 学位类型，默认 master。
        session_id: 关联的会话 ID，用于账本记录。

    Returns:
        评审结果字典，包含：
        - score: 评分。
        - comments: 评审意见。
        - suggestions: 改进建议。
        - approve: 是否通过。

    Raises:
        ValueError: 当 AI API Key 未配置时抛出。
    """
    # 延迟导入以避免循环依赖
    from backend.ai.ai_proxy import call_llm_json, check_api_configured
    from backend.ai.prompts import MENTOR_SYSTEM_PROMPT, build_mentor_prompt
    from backend.budgets.estimator import get_model_for_degree

    # 检查 API 是否配置
    if not check_api_configured():
        raise ValueError("AI API Key 未配置，请在设置页配置")

    # 构建评审提示
    user_prompt = build_mentor_prompt(proposal)

    # 根据学位选择模型
    model = get_model_for_degree(degree)

    # 异步调用 LLM 获取评审结果
    result = await call_llm_json(
        system_prompt=MENTOR_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=model,
        session_id=session_id,
        purpose="mentor_review",
    )

    # 提取解析后的 JSON 内容
    review = result.get("content", {}) or {}
    if not isinstance(review, dict):
        review = {}

    # 整理并补全评审结果字段
    return _normalize_review(review)


def _normalize_review(review: dict) -> dict:
    """整理评审结果字典，确保包含所有必需字段。

    Args:
        review: 原始评审字典。

    Returns:
        规范化后的评审结果字典。
    """
    # 评分：确保为数值
    score = review.get("score", 0)
    if isinstance(score, (int, float)):
        score = float(score)
    else:
        score = 0.0

    return {
        "score": score,
        "comments": review.get("comments") or "暂无评审意见",
        "suggestions": review.get("suggestions") or "暂无改进建议",
        "approve": bool(review.get("approve", False)),
    }


async def batch_review(proposals: list[dict], degree: str = "master", session_id: str = None) -> list[dict]:
    """批量评审多个论题提案。

    对每个提案调用 review_proposal，单个失败时回退到 fallback_review。

    Args:
        proposals: 待评审的论题提案字典列表。
        degree: 学位类型，默认 master。
        session_id: 关联的会话 ID。

    Returns:
        评审结果字典列表，与输入列表一一对应。
    """
    results = []
    for proposal in proposals:
        try:
            # 异步调用单个评审
            review = await review_proposal(proposal, degree=degree, session_id=session_id)
            results.append(review)
        except Exception:
            # 单个评审失败时使用兜底方案，确保系统可用
            results.append(fallback_review(proposal))
    return results


def fallback_review(proposal: dict) -> dict:
    """AI 不可用时的兜底评审方案。

    基于提案的 confidence_score 给出简单评价。

    Args:
        proposal: 论题提案字典。

    Returns:
        兜底评审结果字典。
    """
    score = proposal.get("confidence_score", 0.5)
    if not isinstance(score, (int, float)):
        score = 0.5
    score = float(score)

    # 基于 confidence_score 给出简单评价
    if score >= 0.8:
        comments = "论题整体质量较高，方向明确。"
        suggestions = "建议进一步细化研究内容，明确创新点。"
        approve = True
    elif score >= 0.6:
        comments = "论题具备一定基础，但需进一步完善。"
        suggestions = "建议加强文献综述，明确研究问题的针对性。"
        approve = False
    else:
        comments = "论题成熟度不足，需重新审视研究方向。"
        suggestions = "建议重新选题或大幅调整研究思路。"
        approve = False

    return {
        "score": round(score, 2),
        "comments": comments,
        "suggestions": suggestions,
        "approve": approve,
    }
