"""编排流程状态机

定义论题生成流程的状态枚举、上下文与状态机，
串联前置检索、精炼、校验等钩子，编排完整流程。
"""
from dataclasses import dataclass


# 状态枚举常量
STATE_INIT = "init"
STATE_INSPIRING = "inspiring"  # 创意发散
STATE_REASONING = "reasoning"  # 精炼
STATE_VALIDATING = "validating"  # 校验
STATE_COMPLETED = "completed"
STATE_FAILED = "failed"


@dataclass
class OrchestrationContext:
    """编排流程上下文，承载会话级状态。

    在整个编排流程中传递会话信息、候选集合、提案集合与错误记录。
    """

    session_id: str
    degree: str
    discipline: str
    mentor_info: str
    mode: str = "quick"
    count: int = 3
    current_state: str = STATE_INIT
    candidates: list = None
    proposals: list = None
    errors: list = None
    context: str = ""

    def __post_init__(self) -> None:
        """初始化可变默认值，避免 dataclass 共享可变对象。"""
        if self.candidates is None:
            self.candidates = []
        if self.proposals is None:
            self.proposals = []
        if self.errors is None:
            self.errors = []


class OrchestrationStateMachine:
    """编排流程状态机，驱动从创意发散到校验完成的完整流程。"""

    def __init__(self, ctx: OrchestrationContext) -> None:
        """初始化状态机。

        Args:
            ctx: 编排流程上下文实例。
        """
        self.ctx = ctx

    async def run(self) -> dict:
        """编排完整流程。

        依次执行：
            1. 创意发散：调用前置检索钩子生成候选。
            2. 精炼：对每个候选调用精炼器生成提案。
            3. 校验：对每个提案执行后置精炼与可行性拦截。
            4. 完成：返回最终结果。

        流程中任意阶段抛出异常时，交由 handle_error 处理并终止流程。

        Returns:
            包含 session_id、state、candidates、proposals、errors 字段的结果字典。
        """
        try:
            # 阶段一：创意发散
            self.ctx.current_state = STATE_INSPIRING
            from backend.orchestration.hooks import pre_search

            pre_result = pre_search.run(
                degree=self.ctx.degree,
                discipline=self.ctx.discipline,
                mentor_info=self.ctx.mentor_info,
                context=self.ctx.context,
            )
            self.ctx.candidates = pre_result.get("candidates", [])
            # 富化上下文，供后续阶段使用
            self.ctx.context = pre_result.get(
                "context_enriched", self.ctx.context
            )

            # 阶段二：精炼
            self.ctx.current_state = STATE_REASONING
            for candidate in self.ctx.candidates:
                proposal = await self._call_reasoner(candidate)
                self.ctx.proposals.append(proposal)

            # 阶段三：校验
            self.ctx.current_state = STATE_VALIDATING
            from backend.orchestration.hooks import (
                post_reasoner,
                academic_feasibility_check,
            )

            validated_proposals: list = []
            for proposal in self.ctx.proposals:
                # 后置精炼：校验并重写标题
                proposal = post_reasoner.run(proposal)
                # 可行性拦截：校验时间与文献
                proposal = academic_feasibility_check.run(
                    proposal,
                    degree=self.ctx.degree,
                )
                validated_proposals.append(proposal)
            self.ctx.proposals = validated_proposals

            # 阶段四：完成
            self.ctx.current_state = STATE_COMPLETED
        except Exception as e:  # noqa: BLE001 - 编排层需捕获所有异常以记录上下文
            self.handle_error(e)

        return {
            "session_id": self.ctx.session_id,
            "state": self.ctx.current_state,
            "candidates": self.ctx.candidates,
            "proposals": self.ctx.proposals,
            "errors": self.ctx.errors,
        }

    async def _call_reasoner(self, candidate: dict) -> dict:
        """调用精炼器生成提案。

        预留接口，实际调用 agents.reasoner_proposal 模块的 generate_proposal；
        若 agents 模块不可用，返回基于候选的简化提案。

        Args:
            candidate: 候选字典。

        Returns:
            提案字典。
        """
        try:
            # 延迟导入避免循环依赖
            from backend.agents import reasoner_proposal
        except (ImportError, ModuleNotFoundError):
            # agents 模块不可用，返回简化提案
            return self._fallback_proposal(candidate)

        try:
            # 异步调用 generate_proposal 生成提案
            return await reasoner_proposal.generate_proposal(
                degree=self.ctx.degree,
                discipline=self.ctx.discipline,
                mentor_info=self.ctx.mentor_info,
                candidate=candidate,
                context=self.ctx.context,
                session_id=self.ctx.session_id,
            )
        except Exception:
            # AI 调用失败（如 API 未配置），优先使用模块内置兜底方案
            try:
                return reasoner_proposal.fallback_proposal(
                    degree=self.ctx.degree,
                    discipline=self.ctx.discipline,
                    mentor_info=self.ctx.mentor_info,
                    candidate=candidate,
                )
            except Exception:
                # 模块兜底也失败，使用本地兜底
                return self._fallback_proposal(candidate)

    def _fallback_proposal(self, candidate: dict) -> dict:
        """基于候选生成简化提案（agents 模块不可用时的兜底）。

        Args:
            candidate: 候选字典。

        Returns:
            简化提案字典，包含后续校验所需的最小字段集。
        """
        direction = candidate.get("direction", "")
        suggestion = candidate.get("suggestion", "")
        # 标题取方向描述的前 20 字，避免超长
        title = direction[:20] if direction else "未命名论题"
        return {
            "title": title,
            "inspiration_source": candidate.get("inspiration_source", ""),
            "inspiration_detail": direction,
            "problem_awareness": suggestion,
            "research_content": [suggestion] if suggestion else [],
            "feasibility_analysis": "待补充",
            "confidence_score": 0.5,
            "auto_rewritten": False,
        }

    def handle_error(self, error: Exception) -> None:
        """处理流程中的异常。

        记录错误到上下文，并将状态切换为失败。

        Args:
            error: 捕获到的异常。
        """
        self.ctx.errors.append(
            {
                "state": self.ctx.current_state,
                "error": str(error),
                "type": type(error).__name__,
            }
        )
        self.ctx.current_state = STATE_FAILED


def create_orchestration(
    session_id: str,
    degree: str,
    discipline: str,
    mentor_info: str,
    mode: str = "quick",
    count: int = 3,
) -> OrchestrationStateMachine:
    """创建编排状态机的便捷函数。

    Args:
        session_id: 会话 ID。
        degree: 学位类型，取值为 "master" 或 "doctor"。
        discipline: 学科类型，取值为 "humanities_social" 或 "science_engineering"。
        mentor_info: 导师信息，可能包含导师项目与同门论文。
        mode: 模式，默认 "quick"。
        count: 候选数量，默认 3。

    Returns:
        初始化完成的 OrchestrationStateMachine 实例。
    """
    ctx = OrchestrationContext(
        session_id=session_id,
        degree=degree,
        discipline=discipline,
        mentor_info=mentor_info,
        mode=mode,
        count=count,
    )
    return OrchestrationStateMachine(ctx)
