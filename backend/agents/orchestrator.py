"""Orchestrator 主管理 Agent - Claude Code 式主管理架构

维护五阶段状态机，按阶段调度子 Agent：
信息确权 → 创意 → 校验 → 生成 → 深度辅助

v8.0：作为 BaseAgent 子类接入多 Agent 架构，自身也可调用 LLM 做任务分解决策。
"""
import logging
from typing import AsyncGenerator

from backend.agents.base_agent import AgentResult, BaseAgent
from backend.agents.agent_registry import get_agent
from backend.config import get_step_model

logger = logging.getLogger(__name__)


class OrchestratorAgent(BaseAgent):
    """主管理 Agent

    负责任务分解、阶段调度、门禁控制。
    自身也可调用 LLM 做任务分解决策，但主要职责是协调子 Agent。
    """

    # 五阶段顺序
    STAGES = ["info_confirm", "creativity", "validation", "generation", "deep_assist"]

    def __init__(self):
        super().__init__(
            agent_id="orchestrator",
            name="Orchestrator",
            description="主管理Agent，调度五阶段流程",
            system_prompt=self._default_system_prompt(),
            model_id=get_step_model("orchestrator"),
            temperature=0.3,
            max_tokens=4096,
            capabilities=["streaming", "thinking", "web_search"],
        )
        # 当前阶段
        self.current_stage = "info_confirm"
        # 各阶段结果缓存
        self.stage_results: dict[str, AgentResult] = {}

    @staticmethod
    def _default_system_prompt() -> str:
        return """你是 ThesisMiner 的主管理 Agent（Orchestrator）。

你的职责：
1. 接收用户的研究方向请求
2. 按五阶段闭环导航流调度子 Agent：
   - 信息确权：调用 SearcherAgent 检索近2年文献
   - 创意：调用 ReasonerAgent 生成候选论题
   - 校验：调用 CriticAgent 评估新颖性与可行性
   - 生成：调用 WriterAgent 多粒度生成开题内容
   - 深度辅助：提供文献精读/实验预研/答辩模拟入口
3. 控制阶段间门禁：
   - 信息确权需用户确认后才进入创意
   - 校验评分 < 60 回退到创意重新生成
4. 汇总各阶段结果返回给用户

输出格式为 JSON，包含 stage、status、data 字段。"""

    async def run(self, task_input: dict) -> AgentResult:
        """执行编排（非流式版本）

        Args:
            task_input: 任务输入字典，可包含：
                - user_input: 用户研究方向描述
                - discipline: 学科方向
                - degree: 学位层次
                - granularity: 生成粒度

        Returns:
            AgentResult，data 包含 stages 列表与 final_stage。
        """
        results = []
        user_input = task_input.get("user_input", "") or task_input.get("query", "")
        async for chunk in self.orchestrate(user_input, conversation_id=""):
            results.append(chunk)

        return AgentResult(
            agent_id=self.agent_id,
            success=True,
            content="\n".join(str(r.get("content", "")) for r in results),
            data={
                "stages": results,
                "final_stage": self.current_stage,
            },
        )

    async def orchestrate(
        self, user_input: str, conversation_id: str = ""
    ) -> AsyncGenerator[dict, None]:
        """流式编排 - 按五阶段顺序调用子 Agent

        Args:
            user_input: 用户研究方向描述。
            conversation_id: 会话 ID（预留）。

        Yields:
            每阶段产出的 dict:
            {"stage": str, "agent_id": str, "status": str,
             "content": str, "data": dict}
        """
        # ===== 阶段1: 信息确权 =====
        self.current_stage = "info_confirm"
        yield {
            "stage": "info_confirm",
            "agent_id": "searcher",
            "status": "started",
            "content": "正在检索近2年文献...",
        }

        searcher = get_agent("searcher")
        search_result = await searcher.run({
            "query": user_input,
            "years": 2,
        })
        self.stage_results["info_confirm"] = search_result

        yield {
            "stage": "info_confirm",
            "agent_id": "searcher",
            "status": "completed",
            "content": "文献检索完成",
            "data": search_result.data,
            "citations": search_result.citations,
        }

        # 等待用户确认（门禁）- 在实际使用中由前端触发 confirm 事件
        # 这里先继续流程（测试模式）

        # ===== 阶段2: 创意 =====
        self.current_stage = "creativity"
        yield {
            "stage": "creativity",
            "agent_id": "reasoner",
            "status": "started",
            "content": "正在生成候选论题...",
        }

        reasoner = get_agent("reasoner")
        reason_result = await reasoner.run({
            "discipline": "",  # 由调用方在 task_input 中传入
            "degree": "master",
            "search_feeds": search_result.data.get("papers", []),
        })
        self.stage_results["creativity"] = reason_result

        yield {
            "stage": "creativity",
            "agent_id": "reasoner",
            "status": "completed",
            "content": "候选论题生成完成",
            "data": reason_result.data,
        }

        # ===== 阶段3: 校验 =====
        self.current_stage = "validation"
        yield {
            "stage": "validation",
            "agent_id": "critic",
            "status": "started",
            "content": "正在评估候选论题...",
        }

        critic = get_agent("critic")
        critic_result = await critic.run({
            "candidates": reason_result.data.get("candidates", []),
            "search_feeds": search_result.data.get("papers", []),
        })
        self.stage_results["validation"] = critic_result

        # 检查评分是否达标
        evaluations = critic_result.data.get("evaluations", [])
        avg_score = (
            sum(e.get("score", 0) for e in evaluations) / len(evaluations)
            if evaluations else 0
        )

        if avg_score < 60:
            yield {
                "stage": "validation",
                "agent_id": "critic",
                "status": "retry",
                "content": f"平均评分 {avg_score:.0f} < 60，回退到创意阶段重新生成",
                "data": critic_result.data,
            }
            # 回退到创意阶段
            self.current_stage = "creativity"
            return

        yield {
            "stage": "validation",
            "agent_id": "critic",
            "status": "completed",
            "content": f"评估完成，平均评分 {avg_score:.0f}",
            "data": critic_result.data,
        }

        # ===== 阶段4: 生成 =====
        self.current_stage = "generation"
        yield {
            "stage": "generation",
            "agent_id": "writer",
            "status": "started",
            "content": "正在生成开题内容...",
        }

        writer = get_agent("writer")
        # 取评分最高的候选
        best_candidate = evaluations[0] if evaluations else {}
        writer_result = await writer.run({
            "topic": best_candidate.get("title", user_input),
            "granularity": "outline",
            "context": {
                "search_feeds": search_result.data.get("papers", []),
                "evaluation": critic_result.data,
            },
        })
        self.stage_results["generation"] = writer_result

        yield {
            "stage": "generation",
            "agent_id": "writer",
            "status": "completed",
            "content": "内容生成完成",
            "data": writer_result.data,
        }

        # ===== 阶段5: 深度辅助 =====
        self.current_stage = "deep_assist"
        yield {
            "stage": "deep_assist",
            "agent_id": "orchestrator",
            "status": "completed",
            "content": "可进入深度辅助：文献精读 / 实验预研 / 答辩模拟",
            "data": {
                "options": [
                    "literature_reading",
                    "experiment_preparation",
                    "defense_simulation",
                ]
            },
        }

    def confirm_info(self) -> bool:
        """用户确认信息确权阶段，允许进入创意阶段

        Returns:
            成功切换返回 True，当前阶段不匹配返回 False。
        """
        if self.current_stage == "info_confirm":
            self.current_stage = "creativity"
            return True
        return False

    def get_stage(self) -> str:
        """获取当前阶段"""
        return self.current_stage

    def reset(self):
        """重置编排状态，用于新会话

        清空阶段结果与当前阶段，并重置所有子 Agent 上下文。
        """
        self.current_stage = "info_confirm"
        self.stage_results = {}
        self.reset_context()
        # 同步重置所有子 Agent 上下文
        from backend.agents.agent_registry import reset_all_contexts
        reset_all_contexts()
