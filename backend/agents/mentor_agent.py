"""Mentor 智能体模块

负责从导师视角评审论题提案，包含单次评审、批量评审与兜底方案。
所有 AI 相关导入采用延迟导入以避免循环依赖。

v8.0 升级：在保留既有函数的基础上，新增 MentorAgent 作为 BaseAgent 子类，
统一接入多 Agent 架构。既有函数保持兼容。
"""
import json
import logging

from backend.agents.base_agent import AgentResult, BaseAgent
from backend.config import get_step_model

logger = logging.getLogger(__name__)


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


# ==================== MentorAgent（v8.0 新增） ====================


class MentorAgent(BaseAgent):
    """MentorAgent - 导师视角评审 Agent

    模拟导师视角对论题进行评审，给出指导建议与方向判断。
    在保留既有 review_proposal / batch_review 函数的基础上，
    包装为 BaseAgent 子类接入多 Agent 架构。
    """

    def __init__(self):
        super().__init__(
            agent_id="mentor",
            name="Mentor",
            description="导师视角评审 Agent，给出指导建议",
            system_prompt=self._default_system_prompt(),
            model_id=get_step_model("mentor"),
            temperature=0.4,
            max_tokens=2048,
            capabilities=[],
        )

    @staticmethod
    def _default_system_prompt() -> str:
        return (
            "你是 ThesisMiner 的导师视角 Agent（Mentor），模拟真实导师的评审视角。\n"
            "你的职责：\n"
            "1. 从导师视角评估论题的学术价值与可行性\n"
            "2. 结合导师的研究方向与资源，判断论题是否契合\n"
            "3. 给出具体的指导建议（advice）与方向判断（direction）\n"
            "4. direction 取值：approve / revise / reject\n\n"
            "输出 JSON 格式：\n"
            '{"advice": str, "direction": str, "score": int, "reason": str}'
        )

    async def run(self, task_input: dict) -> AgentResult:
        """执行导师评审

        Args:
            task_input: 包含以下字段：
                - topic: 论题标题
                - context: 上下文字典，可包含 degree / discipline / mentor_info /
                  evaluation 等

        Returns:
            AgentResult，data 包含 advice 与 direction。
        """
        topic = task_input.get("topic", "")
        context = task_input.get("context", {}) or {}

        if not topic:
            return AgentResult(
                agent_id=self.agent_id,
                success=False,
                error="缺少论题 topic",
                data={"advice": "", "direction": "reject"},
            )

        try:
            # 构建用户提示
            user_prompt = self._build_user_prompt(topic, context)
            self.add_message("user", user_prompt)

            # 延迟导入以避免循环依赖
            from backend.ai.ai_proxy import call_llm

            llm_result = await call_llm(
                system_prompt=self.system_prompt,
                user_prompt=user_prompt,
                model=self.model_id,
                temperature=self.temperature,
                purpose="mentor",
            )

            content = llm_result.get("content", "")
            self.add_message("assistant", content)

            # 解析评审结果
            advice, direction = self._parse_response(content)

            return AgentResult(
                agent_id=self.agent_id,
                success=True,
                content=content,
                data={
                    "advice": advice,
                    "direction": direction,
                    "topic": topic,
                },
                token_usage={
                    "prompt_tokens": llm_result.get("prompt_tokens", 0),
                    "completion_tokens": llm_result.get("completion_tokens", 0),
                    "total_tokens": llm_result.get("total_tokens", 0),
                },
            )
        except Exception as e:
            # 失败时返回兜底评审
            return AgentResult(
                agent_id=self.agent_id,
                success=False,
                error=f"导师评审失败: {e}",
                data={
                    "advice": "评审服务暂时不可用，建议人工复核论题",
                    "direction": "revise",
                    "topic": topic,
                },
            )

    @staticmethod
    def _build_user_prompt(topic: str, context: dict) -> str:
        """构建 LLM 用户提示

        Args:
            topic: 论题标题。
            context: 上下文字典。

        Returns:
            用户提示字符串。
        """
        degree = context.get("degree", "master")
        discipline = context.get("discipline", "")
        mentor_info = context.get("mentor_info", "")
        evaluation = context.get("evaluation", {})

        degree_label = "硕士" if degree == "master" else "博士"

        # 评估信息摘要
        eval_text = ""
        if evaluation:
            eval_data = evaluation.get("evaluations", [])
            if eval_data:
                first = eval_data[0]
                eval_text = (
                    f"评估评分：{first.get('score', 'N/A')}\n"
                    f"新颖性：{first.get('novelty', 'N/A')}\n"
                    f"可行性：{first.get('feasibility', 'N/A')}\n"
                    f"问题：{first.get('issues', [])}\n"
                    f"建议：{first.get('suggestions', [])}"
                )

        return (
            f"论题标题：{topic}\n"
            f"学位层次：{degree_label}\n"
            f"学科方向：{discipline or '未指定'}\n"
            f"导师信息：{mentor_info or '未提供'}\n"
            f"{('评估信息：\n' + eval_text) if eval_text else ''}\n"
            f"请从导师视角给出评审意见与方向判断。"
            f"严格按 JSON 格式输出："
            f'{{"advice": str, "direction": str, "score": int, "reason": str}}'
        )

    @staticmethod
    def _parse_response(content: str) -> tuple[str, str]:
        """解析 LLM 返回的评审结果

        Args:
            content: LLM 返回的文本内容。

        Returns:
            (advice, direction) 元组。direction 取值 approve / revise / reject。
        """
        if not content:
            return "暂无评审意见", "revise"

        # 尝试解析 JSON
        parsed = None
        try:
            parsed = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            # 尝试提取代码块
            import re
            code_block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
            if code_block:
                try:
                    parsed = json.loads(code_block.group(1))
                except (json.JSONDecodeError, TypeError):
                    pass
            # 尝试提取 {...} 子串
            if parsed is None:
                first = content.find("{")
                last = content.rfind("}")
                if first != -1 and last > first:
                    try:
                        parsed = json.loads(content[first:last + 1])
                    except (json.JSONDecodeError, TypeError):
                        pass

        if isinstance(parsed, dict):
            advice = parsed.get("advice", "") or "暂无评审意见"
            direction = parsed.get("direction", "revise")
            if direction not in ("approve", "revise", "reject"):
                direction = "revise"
            return advice, direction

        # 解析失败，返回兜底
        return content[:200] if content else "暂无评审意见", "revise"
