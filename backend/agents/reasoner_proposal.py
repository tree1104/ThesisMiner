"""Reasoner 智能体模块

负责生成直通开题报告的论题提案，包含单次生成、批量生成与兜底方案。
所有 AI 相关导入采用延迟导入以避免循环依赖。
"""


def generate_proposal(
    degree: str,
    discipline: str,
    mentor_info: str,
    candidate: dict = None,
    context: str = "",
    session_id: str = None,
) -> dict:
    """生成单个直通开题的论题提案。

    流程：检查 API 配置 → 构建候选上下文 → 调用 LLM → 校验重写标题 → 补全字段。

    Args:
        degree: 学位类型（master / doctor）。
        discipline: 学科类型。
        mentor_info: 导师信息（研究方向、背景等）。
        candidate: 可选的候选信息字典，可包含 direction 与 suggestion 字段。
        context: 可选的上下文补充信息。
        session_id: 关联的会话 ID，用于账本记录。

    Returns:
        完整的论题提案字典，符合 AcademicThesisProposal 结构。

    Raises:
        ValueError: 当 AI API Key 未配置时抛出。
    """
    # 延迟导入以避免循环依赖
    from backend.ai.ai_proxy import call_llm_json, check_api_configured
    from backend.ai.prompts import REASONER_SYSTEM_PROMPT, build_reasoner_prompt
    from backend.budgets.estimator import get_model_for_degree
    from backend.constraints.format_validator import validate_and_rewrite
    from backend.models import AcademicThesisProposal

    # 检查 API 是否配置
    if not check_api_configured():
        raise ValueError("AI API Key 未配置，请在设置页配置")

    # 构建候选信息上下文：将候选的 direction/suggestion 加入 context
    enriched_context = context
    if candidate:
        candidate_parts = []
        if candidate.get("direction"):
            candidate_parts.append(f"候选方向：{candidate['direction']}")
        if candidate.get("suggestion"):
            candidate_parts.append(f"建议：{candidate['suggestion']}")
        if candidate_parts:
            joined = "\n".join(candidate_parts)
            enriched_context = f"{enriched_context}\n{joined}".strip() if enriched_context else joined

    # 构建用户提示
    user_prompt = build_reasoner_prompt(degree, discipline, mentor_info, enriched_context)

    # 根据学位选择模型
    model = get_model_for_degree(degree)

    # 调用 LLM 获取结构化响应
    result = call_llm_json(
        system_prompt=REASONER_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=model,
        session_id=session_id,
        purpose="reasoner_proposal",
    )

    # 提取解析后的 JSON 内容
    proposal = result.get("content", {}) or {}
    if not isinstance(proposal, dict):
        proposal = {}

    # 校验并重写标题
    title = proposal.get("title", "")
    if title:
        rewrite_result = validate_and_rewrite(title)
        proposal["title"] = rewrite_result["title"]
        proposal["auto_rewritten"] = rewrite_result["auto_rewritten"]
    else:
        proposal["title"] = ""
        proposal["auto_rewritten"] = False

    # 补全缺失字段，确保输出符合 AcademicThesisProposal 结构
    proposal = _ensure_proposal_fields(proposal, degree, mentor_info, candidate)

    # 引用 AcademicThesisProposal 以满足导入要求并作为结构参照
    _ = AcademicThesisProposal

    return proposal


def _ensure_proposal_fields(
    proposal: dict,
    degree: str,
    mentor_info: str,
    candidate: dict = None,
) -> dict:
    """补全 proposal 字典中缺失的字段，使其符合 AcademicThesisProposal 结构。

    Args:
        proposal: 待补全的提案字典。
        degree: 学位类型。
        mentor_info: 导师信息。
        candidate: 可选的候选信息字典。

    Returns:
        补全后的提案字典。
    """
    base = mentor_info.strip() if mentor_info else "学术研究"
    direction = candidate.get("direction", base) if candidate else base

    # 标题
    if not proposal.get("title"):
        proposal["title"] = direction[:20] if len(direction) > 20 else direction

    # 灵感来源
    if not proposal.get("inspiration_source"):
        proposal["inspiration_source"] = f"基于导师研究方向：{base[:50]}"

    # 问题意识
    if not proposal.get("problem_awareness"):
        proposal["problem_awareness"] = "待补充"

    # 研究意义：确保为含 theoretical 与 practical 的字典
    significance = proposal.get("research_significance")
    if not isinstance(significance, dict):
        significance = {}
    if not significance.get("theoretical"):
        significance["theoretical"] = "待补充"
    if not significance.get("practical"):
        significance["practical"] = "待补充"
    proposal["research_significance"] = significance

    # 文献综述大纲
    if not proposal.get("literature_review_outline"):
        proposal["literature_review_outline"] = "待补充"

    # 差异化/创新点
    if not proposal.get("differentiation"):
        proposal["differentiation"] = "待补充"

    # 研究内容：确保为非空列表
    content = proposal.get("research_content")
    if not isinstance(content, list) or not content:
        proposal["research_content"] = ["待补充研究内容"]

    # 可行性分析
    if not proposal.get("feasibility_analysis"):
        proposal["feasibility_analysis"] = f"结合{degree}学位要求与导师资源，具备研究可行性"

    # 置信度评分：确保为 0-1 的浮点数
    score = proposal.get("confidence_score")
    if not isinstance(score, (int, float)):
        proposal["confidence_score"] = 0.5
    else:
        proposal["confidence_score"] = max(0.0, min(1.0, float(score)))

    # 是否经过自动改写
    proposal["auto_rewritten"] = bool(proposal.get("auto_rewritten", False))

    return proposal


def generate_multiple(
    degree: str,
    discipline: str,
    mentor_info: str,
    candidates: list[dict] = None,
    count: int = 3,
    context: str = "",
    session_id: str = None,
) -> list[dict]:
    """批量生成多个论题提案。

    若 candidates 为空，则基于 mentor_info 生成默认候选方向；
    对每个候选调用 generate_proposal，单个失败时回退到 fallback_proposal。

    Args:
        degree: 学位类型（master / doctor）。
        discipline: 学科类型。
        mentor_info: 导师信息。
        candidates: 候选信息字典列表，为空时自动生成。
        count: 生成数量，默认 3。
        context: 可选的上下文补充信息。
        session_id: 关联的会话 ID。

    Returns:
        论题提案字典列表。
    """
    # 若 candidates 为空，使用默认候选（基于 mentor_info 生成）
    if not candidates:
        candidates = _build_default_candidates(mentor_info, count)

    proposals = []
    for candidate in candidates:
        try:
            proposal = generate_proposal(
                degree=degree,
                discipline=discipline,
                mentor_info=mentor_info,
                candidate=candidate,
                context=context,
                session_id=session_id,
            )
            proposals.append(proposal)
        except Exception:
            # 单个生成失败时使用兜底方案，确保系统可用
            proposal = fallback_proposal(degree, discipline, mentor_info, candidate)
            proposals.append(proposal)

    return proposals


def _build_default_candidates(mentor_info: str, count: int) -> list[dict]:
    """基于导师信息生成默认候选方向列表。

    Args:
        mentor_info: 导师信息。
        count: 所需候选数量。

    Returns:
        候选信息字典列表，每项包含 direction 与 suggestion 字段。
    """
    base = mentor_info.strip() if mentor_info else "学术研究"
    directions = [
        f"{base}的理论拓展",
        f"{base}的实证分析",
        f"{base}的跨学科应用",
        f"{base}的方法论创新",
        f"{base}的案例研究",
    ]

    candidates = []
    for i in range(count):
        direction = directions[i] if i < len(directions) else f"{base}的延伸方向{i + 1}"
        candidates.append({
            "direction": direction,
            "suggestion": f"围绕{base}展开的第{i + 1}个候选方向",
        })
    return candidates


def fallback_proposal(
    degree: str,
    discipline: str,
    mentor_info: str,
    candidate: dict = None,
) -> dict:
    """AI 不可用时的兜底论题生成方案。

    基于候选信息拼装一个结构完整的简化 proposal。

    Args:
        degree: 学位类型。
        discipline: 学科类型。
        mentor_info: 导师信息。
        candidate: 可选的候选信息字典。

    Returns:
        结构完整的简化论题提案字典。
    """
    base = mentor_info.strip() if mentor_info else "学术研究"
    direction = candidate.get("direction", base) if candidate else base
    suggestion = candidate.get("suggestion", "") if candidate else ""

    # 拼装简化标题（限20字内）
    title = direction[:20] if len(direction) > 20 else direction

    return {
        "title": title,
        "inspiration_source": f"基于导师研究方向：{base[:50]}",
        "problem_awareness": f"围绕{direction}的核心问题尚未充分解决",
        "research_significance": {
            "theoretical": f"为{direction}提供理论补充",
            "practical": f"为{direction}的实践应用提供参考",
        },
        "literature_review_outline": f"围绕{direction}梳理国内外研究现状",
        "differentiation": suggestion or f"区别于已有{direction}研究的切入点",
        "research_content": [
            f"{direction}的概念界定与理论基础",
            f"{direction}的研究现状梳理",
            f"{direction}的实证或案例分析",
        ],
        "feasibility_analysis": f"结合{degree}学位要求与导师资源，具备研究可行性",
        "confidence_score": 0.4,
        "auto_rewritten": False,
    }
