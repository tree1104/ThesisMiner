"""CriticAgent - 候选论题评估 Agent

负责对 ReasonerAgent 生成的候选论题进行评估，包括：
1. 新颖性评估（novelty）：与已有文献的重复度
2. 可行性评估（feasibility）：研究难度与资源匹配度
3. 综合评分（score）：0-100 分
4. 问题清单（issues）与改进建议（suggestions）

v8.0：作为 BaseAgent 子类接入多 Agent 架构。
"""
import json
import logging

from backend.agents.base_agent import AgentResult, BaseAgent
from backend.agents.searcher_wrapper import check_novelty
from backend.config import get_step_model

logger = logging.getLogger(__name__)


# 评分阈值：低于此分数触发回退到创意阶段
SCORE_THRESHOLD = 60


class CriticAgent(BaseAgent):
    """CriticAgent - 候选论题评估 Agent

    结合本地新颖性检查（基于字符串相似度）与 LLM 评估，
    输出每个候选的综合评分、问题清单与改进建议。
    """

    def __init__(self):
        super().__init__(
            agent_id="critic",
            name="Critic",
            description="候选论题评估 Agent，评估新颖性与可行性",
            system_prompt=self._default_system_prompt(),
            model_id=get_step_model("reasoner"),  # 复用 reasoner 模型做评估
            temperature=0.2,
            max_tokens=4096,
            capabilities=["thinking"],
        )

    @staticmethod
    def _default_system_prompt() -> str:
        return (
            "你是 ThesisMiner 的评估 Agent（Critic），负责评估候选论题的质量。\n"
            "评估维度：\n"
            "1. 新颖性（novelty，0-100）：与已有研究的差异度\n"
            "2. 可行性（feasibility，0-100）：研究难度与资源匹配度\n"
            "3. 综合评分（score，0-100）：加权综合\n\n"
            "你的职责：\n"
            "1. 对每个候选论题给出三个维度的评分\n"
            "2. 列出存在的问题（issues）\n"
            "3. 提出具体的改进建议（suggestions）\n"
            "4. 评分低于 60 的候选需明确指出不可行的原因\n\n"
            "输出 JSON 格式：\n"
            '{"evaluations": [{"title": str, "score": int, "novelty": int, '
            '"feasibility": int, "issues": list, "suggestions": list}]}'
        )

    async def run(self, task_input: dict) -> AgentResult:
        """执行候选论题评估

        Args:
            task_input: 包含以下字段：
                - candidates: 候选论题列表，每项含 title / dimension / rationale
                - search_feeds: 检索到的文献列表，用于新颖性检查

        Returns:
            AgentResult，data 包含 evaluations 列表。
        """
        candidates = task_input.get("candidates", []) or []
        search_feeds = task_input.get("search_feeds", []) or []

        if not candidates:
            return AgentResult(
                agent_id=self.agent_id,
                success=False,
                error="缺少候选论题 candidates",
                data={"evaluations": []},
            )

        try:
            # 1. 本地新颖性检查：基于字符串相似度
            existing_titles = [
                p.get("title", "") for p in search_feeds if p.get("title")
            ]
            local_novelty = {}
            for c in candidates:
                title = c.get("title", "") if isinstance(c, dict) else str(c)
                if title:
                    novelty_result = check_novelty(title, existing_titles)
                    local_novelty[title] = novelty_result

            # 2. 调用 LLM 进行深度评估
            user_prompt = self._build_user_prompt(candidates, local_novelty)
            self.add_message("user", user_prompt)

            # 延迟导入以避免循环依赖
            from backend.ai.ai_proxy import call_llm

            llm_result = await call_llm(
                system_prompt=self.system_prompt,
                user_prompt=user_prompt,
                model=self.model_id,
                temperature=self.temperature,
                purpose="reasoner",
            )

            content = llm_result.get("content", "")
            self.add_message("assistant", content)

            # 3. 解析评估结果
            evaluations = self._parse_evaluations(content, candidates, local_novelty)

            return AgentResult(
                agent_id=self.agent_id,
                success=True,
                content=content,
                data={
                    "evaluations": evaluations,
                    "avg_score": (
                        sum(e.get("score", 0) for e in evaluations) / len(evaluations)
                        if evaluations else 0
                    ),
                    "threshold": SCORE_THRESHOLD,
                },
                token_usage={
                    "prompt_tokens": llm_result.get("prompt_tokens", 0),
                    "completion_tokens": llm_result.get("completion_tokens", 0),
                    "total_tokens": llm_result.get("total_tokens", 0),
                },
            )
        except Exception as e:
            # 失败时返回基于本地新颖性的兜底评估
            fallback = self._fallback_evaluations(candidates, search_feeds)
            return AgentResult(
                agent_id=self.agent_id,
                success=False,
                error=f"评估失败: {e}",
                data={
                    "evaluations": fallback,
                    "avg_score": (
                        sum(e.get("score", 0) for e in fallback) / len(fallback)
                        if fallback else 0
                    ),
                    "threshold": SCORE_THRESHOLD,
                },
            )

    @staticmethod
    def _build_user_prompt(candidates: list, local_novelty: dict) -> str:
        """构建 LLM 用户提示

        Args:
            candidates: 候选论题列表。
            local_novelty: 本地新颖性检查结果，title -> novelty dict。

        Returns:
            用户提示字符串。
        """
        lines = []
        for i, c in enumerate(candidates, 1):
            if isinstance(c, dict):
                title = c.get("title", "")
                dimension = c.get("dimension", "")
                rationale = c.get("rationale", "")
            else:
                title = str(c)
                dimension = ""
                rationale = ""
            novelty_info = local_novelty.get(title, {})
            novelty_score = novelty_info.get("novelty_score", 0)
            assessment = novelty_info.get("assessment", "未知")
            lines.append(
                f"{i}. 标题：{title}\n"
                f"   维度：{dimension}\n"
                f"   理由：{rationale}\n"
                f"   本地新颖性：{novelty_score}（{assessment}）"
            )

        candidates_text = "\n".join(lines) if lines else "（暂无候选）"

        return (
            f"待评估的候选论题：\n{candidates_text}\n\n"
            f"请对每个候选给出 score / novelty / feasibility（0-100 整数），"
            f"列出 issues 与 suggestions。严格按 JSON 格式输出：\n"
            f'{{"evaluations": [{{"title": str, "score": int, "novelty": int, '
            f'"feasibility": int, "issues": list, "suggestions": list}}]}}'
        )

    @staticmethod
    def _parse_evaluations(
        content: str, candidates: list, local_novelty: dict
    ) -> list[dict]:
        """解析 LLM 返回的评估列表

        Args:
            content: LLM 返回的文本内容。
            candidates: 原始候选列表（用于兜底）。
            local_novelty: 本地新颖性检查结果。

        Returns:
            评估字典列表，每项含 title / score / novelty / feasibility / issues / suggestions。
        """
        if not content:
            return CriticAgent._fallback_evaluations(candidates, [], local_novelty)

        evaluations = CriticAgent._extract_json_evaluations(content)
        if evaluations:
            # 规范化每个评估项
            normalized = []
            for e in evaluations:
                if not isinstance(e, dict):
                    continue
                title = (e.get("title") or "").strip()
                if not title:
                    continue
                # 融合本地新颖性：取较低值
                local = local_novelty.get(title, {})
                local_novelty_score = local.get("novelty_score", 0)
                # 本地 novelty_score 越低越新颖，转换为 0-100 分
                local_novelty_100 = int((1 - local_novelty_score) * 100)
                llm_novelty = CriticAgent._safe_int(e.get("novelty"), 50)
                # 取较低值作为最终新颖性
                final_novelty = min(llm_novelty, local_novelty_100)

                score = CriticAgent._safe_int(e.get("score"), 50)
                feasibility = CriticAgent._safe_int(e.get("feasibility"), 50)
                # 综合分不能高于新颖性
                score = min(score, max(final_novelty, feasibility))

                normalized.append({
                    "title": title,
                    "score": score,
                    "novelty": final_novelty,
                    "feasibility": feasibility,
                    "issues": e.get("issues", []) or [],
                    "suggestions": e.get("suggestions", []) or [],
                })
            if normalized:
                return normalized

        # 解析失败，使用兜底
        return CriticAgent._fallback_evaluations(candidates, [], local_novelty)

    @staticmethod
    def _extract_json_evaluations(content: str) -> list[dict]:
        """从文本中提取评估 JSON 列表

        Args:
            content: 待解析的文本。

        Returns:
            评估字典列表；解析失败返回空列表。
        """
        if not isinstance(content, str):
            return []

        # 1. 直接解析
        try:
            data = json.loads(content)
            if isinstance(data, dict) and "evaluations" in data:
                return data["evaluations"]
        except (json.JSONDecodeError, TypeError):
            pass

        # 2. 提取代码块
        import re
        code_block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        if code_block:
            try:
                data = json.loads(code_block.group(1))
                if isinstance(data, dict) and "evaluations" in data:
                    return data["evaluations"]
            except (json.JSONDecodeError, TypeError):
                pass

        # 3. 提取 {...} 子串
        first = content.find("{")
        last = content.rfind("}")
        if first != -1 and last > first:
            try:
                data = json.loads(content[first:last + 1])
                if isinstance(data, dict) and "evaluations" in data:
                    return data["evaluations"]
            except (json.JSONDecodeError, TypeError):
                pass

        return []

    @staticmethod
    def _safe_int(value, default: int = 0) -> int:
        """安全转换为 int，失败返回默认值"""
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _fallback_evaluations(
        candidates: list, search_feeds: list, local_novelty: dict = None
    ) -> list[dict]:
        """生成兜底评估（LLM 不可用时）

        基于本地新颖性检查给出简化评分。

        Args:
            candidates: 候选论题列表。
            search_feeds: 检索到的文献列表。
            local_novelty: 本地新颖性检查结果（可选）。

        Returns:
            兜底评估列表。
        """
        if local_novelty is None:
            local_novelty = {}
            existing_titles = [
                p.get("title", "") for p in search_feeds if p.get("title")
            ]
            for c in candidates:
                title = c.get("title", "") if isinstance(c, dict) else str(c)
                if title:
                    local_novelty[title] = check_novelty(title, existing_titles)

        evaluations = []
        for c in candidates:
            title = c.get("title", "") if isinstance(c, dict) else str(c)
            novelty_result = local_novelty.get(title, {})
            novelty_score = novelty_result.get("novelty_score", 0)
            assessment = novelty_result.get("assessment", "未知")

            # 本地 novelty_score 越低越新颖，转换为 0-100 分
            novelty_100 = int((1 - novelty_score) * 100)
            # 兜底可行性给 60 分
            feasibility = 60
            score = min(novelty_100, feasibility + 10)

            issues = []
            suggestions = []
            if assessment == "预警":
                issues.append("与已有文献高度相似，新颖性不足")
                suggestions.append("建议调整研究角度，增加差异化")
            elif assessment == "微创新":
                issues.append("与已有文献存在相似性")
                suggestions.append("建议明确创新点，突出差异")

            evaluations.append({
                "title": title,
                "score": score,
                "novelty": novelty_100,
                "feasibility": feasibility,
                "issues": issues,
                "suggestions": suggestions,
            })

        return evaluations
