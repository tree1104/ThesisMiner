"""ReasonerAgent - 四维创意引擎

基于四维创意引擎（学科交叉 / 方法迁移 / 痛点突破 / 趋势前瞻）生成
候选论题。每个候选包含标题、所属维度与生成理由。

v8.0：作为 BaseAgent 子类接入多 Agent 架构，独立维护上下文与模型路由。
"""
import json
import logging

from backend.agents.base_agent import AgentResult, BaseAgent
from backend.config import get_step_model

logger = logging.getLogger(__name__)


# 四维创意引擎维度定义
FOUR_DIMENSIONS = [
    {
        "id": "cross_discipline",
        "name": "学科交叉",
        "description": "将其他学科的理论/方法引入本学科，形成新的研究视角",
    },
    {
        "id": "method_transfer",
        "name": "方法迁移",
        "description": "将成熟方法迁移到新场景或新数据集，验证普适性",
    },
    {
        "id": "pain_point_breakthrough",
        "name": "痛点突破",
        "description": "针对领域内公认难题或未解决问题，提出新思路",
    },
    {
        "id": "trend_forecast",
        "name": "趋势前瞻",
        "description": "结合新兴技术/政策/社会趋势，前瞻性布局研究方向",
    },
]


class ReasonerAgent(BaseAgent):
    """ReasonerAgent - 四维创意引擎 Agent

    基于学科交叉 / 方法迁移 / 痛点突破 / 趋势前瞻四个维度，
    结合检索到的文献 feed 生成候选论题。
    """

    def __init__(self):
        super().__init__(
            agent_id="reasoner",
            name="Reasoner",
            description="四维创意引擎 Agent，生成候选论题",
            system_prompt=self._default_system_prompt(),
            model_id=get_step_model("reasoner"),
            temperature=0.8,
            max_tokens=4096,
            capabilities=["thinking"],
        )

    @staticmethod
    def _default_system_prompt() -> str:
        dimensions_desc = "\n".join(
            f"- {d['name']}（{d['id']}）：{d['description']}"
            for d in FOUR_DIMENSIONS
        )
        return (
            "你是 ThesisMiner 的创意引擎 Agent（Reasoner），基于四维创意引擎生成候选论题。\n"
            f"四个维度：\n{dimensions_desc}\n\n"
            "你的职责：\n"
            "1. 基于用户学科与学位层次，结合检索到的近2年文献 feed\n"
            "2. 在四个维度上各生成 1-2 个候选论题，共 4-8 个候选\n"
            "3. 每个候选需标注所属维度与生成理由（rationale）\n"
            "4. 标题限 20 字内名词性短语，避免与已有文献重复\n\n"
            "输出 JSON 格式：\n"
            '{"candidates": [{"title": str, "dimension": str, "rationale": str}]}\n'
            "dimension 取值：cross_discipline / method_transfer / "
            "pain_point_breakthrough / trend_forecast"
        )

    async def run(self, task_input: dict) -> AgentResult:
        """执行候选论题生成

        Args:
            task_input: 包含以下字段：
                - discipline: 学科方向
                - degree: 学位层次（master / doctor）
                - search_feeds: 检索到的文献列表，用于避免重复

        Returns:
            AgentResult，data 包含 candidates 列表。
        """
        discipline = task_input.get("discipline", "")
        degree = task_input.get("degree", "master")
        search_feeds = task_input.get("search_feeds", []) or []
        conversation_id = task_input.get("conversation_id")
        session_id = task_input.get("session_id")

        try:
            # 构建用户提示
            user_prompt = self._build_user_prompt(discipline, degree, search_feeds)
            # 持久化用户消息（Task 5 / v9.0）
            try:
                self.save_message(
                    "user", user_prompt,
                    conversation_id=conversation_id, session_id=session_id,
                )
            except Exception:
                logger.debug("持久化用户消息失败", exc_info=True)
            else:
                # save_message 已同步到内存，无需再 add_message
                pass

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
            # 持久化 assistant 回复（Task 5 / v9.0）
            try:
                self.save_message(
                    "assistant", content,
                    conversation_id=conversation_id, session_id=session_id,
                )
            except Exception:
                logger.debug("持久化 assistant 消息失败", exc_info=True)
                self.add_message("assistant", content)

            # 解析候选列表
            candidates = self._parse_candidates(content, discipline)

            return AgentResult(
                agent_id=self.agent_id,
                success=True,
                content=content,
                data={
                    "candidates": candidates,
                    "discipline": discipline,
                    "degree": degree,
                    "dimensions": [d["id"] for d in FOUR_DIMENSIONS],
                },
                token_usage={
                    "prompt_tokens": llm_result.get("prompt_tokens", 0),
                    "completion_tokens": llm_result.get("completion_tokens", 0),
                    "total_tokens": llm_result.get("total_tokens", 0),
                },
            )
        except Exception as e:
            # 失败时返回基于四维度的兜底候选
            fallback = self._fallback_candidates(discipline)
            return AgentResult(
                agent_id=self.agent_id,
                success=False,
                error=f"创意生成失败: {e}",
                data={"candidates": fallback, "discipline": discipline, "degree": degree},
            )

    @staticmethod
    def _build_user_prompt(discipline: str, degree: str, search_feeds: list) -> str:
        """构建 LLM 用户提示

        Args:
            discipline: 学科方向。
            degree: 学位层次。
            search_feeds: 检索到的文献列表。

        Returns:
            用户提示字符串。
        """
        # 提取已有文献标题，避免重复
        existing_titles = [
            p.get("title", "") for p in search_feeds if p.get("title")
        ][:20]
        existing_text = "\n".join(f"- {t}" for t in existing_titles) or "（暂无）"

        degree_label = "硕士" if degree == "master" else "博士"

        return (
            f"学科方向：{discipline or '未指定'}\n"
            f"学位层次：{degree_label}\n\n"
            f"近2年相关文献标题（避免与之重复）：\n{existing_text}\n\n"
            f"请基于四维创意引擎生成 4-8 个候选论题，"
            f"每个维度至少 1 个候选。严格按 JSON 格式输出：\n"
            f'{{"candidates": [{{"title": str, "dimension": str, "rationale": str}}]}}'
        )

    @staticmethod
    def _parse_candidates(content: str, discipline: str) -> list[dict]:
        """解析 LLM 返回的候选列表

        Args:
            content: LLM 返回的文本内容。
            discipline: 学科方向（用于兜底）。

        Returns:
            候选字典列表，每项包含 title / dimension / rationale。
        """
        if not content:
            return ReasonerAgent._fallback_candidates(discipline)

        # 尝试从内容中提取 JSON
        candidates = ReasonerAgent._extract_json_candidates(content)
        if candidates:
            # 规范化每个候选
            valid_dims = {d["id"] for d in FOUR_DIMENSIONS}
            normalized = []
            for c in candidates:
                if not isinstance(c, dict):
                    continue
                title = (c.get("title") or "").strip()
                if not title:
                    continue
                dimension = c.get("dimension", "cross_discipline")
                if dimension not in valid_dims:
                    dimension = "cross_discipline"
                normalized.append({
                    "title": title,
                    "dimension": dimension,
                    "rationale": c.get("rationale", "") or "",
                })
            if normalized:
                return normalized

        # 解析失败，使用兜底
        return ReasonerAgent._fallback_candidates(discipline)

    @staticmethod
    def _extract_json_candidates(content: str) -> list[dict]:
        """从文本中提取候选 JSON 列表

        支持：直接 JSON、```json 代码块、{...} 子串三种模式。

        Args:
            content: 待解析的文本。

        Returns:
            候选字典列表；解析失败返回空列表。
        """
        if not isinstance(content, str):
            return []

        # 1. 尝试直接解析
        try:
            data = json.loads(content)
            if isinstance(data, dict) and "candidates" in data:
                return data["candidates"]
        except (json.JSONDecodeError, TypeError):
            pass

        # 2. 提取 ```json ... ``` 代码块
        import re
        code_block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        if code_block:
            try:
                data = json.loads(code_block.group(1))
                if isinstance(data, dict) and "candidates" in data:
                    return data["candidates"]
            except (json.JSONDecodeError, TypeError):
                pass

        # 3. 提取第一个 '{' 到最后一个 '}' 的子串
        first = content.find("{")
        last = content.rfind("}")
        if first != -1 and last > first:
            try:
                data = json.loads(content[first:last + 1])
                if isinstance(data, dict) and "candidates" in data:
                    return data["candidates"]
            except (json.JSONDecodeError, TypeError):
                pass

        return []

    @staticmethod
    def _fallback_candidates(discipline: str) -> list[dict]:
        """生成兜底候选（LLM 不可用时）

        Args:
            discipline: 学科方向。

        Returns:
            兜底候选列表，每个维度一个候选。
        """
        base = discipline.strip() if discipline else "学术研究"
        return [
            {
                "title": f"{base}的跨学科融合研究",
                "dimension": "cross_discipline",
                "rationale": f"将其他学科方法引入{base}，形成新视角",
            },
            {
                "title": f"{base}方法在新场景的迁移验证",
                "dimension": "method_transfer",
                "rationale": f"迁移{base}的成熟方法到新场景，验证普适性",
            },
            {
                "title": f"{base}领域核心痛点的突破路径",
                "dimension": "pain_point_breakthrough",
                "rationale": f"针对{base}内公认难题提出新思路",
            },
            {
                "title": f"{base}与新兴技术的前瞻布局",
                "dimension": "trend_forecast",
                "rationale": f"结合新兴趋势前瞻性研究{base}",
            },
        ]
