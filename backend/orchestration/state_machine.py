"""编排流程状态机

v7: 定义论题生成流程的状态枚举、上下文与状态机，
    串联前置检索、精炼、校验等钩子，编排完整流程。
v8.0: 新增五阶段闭环导航流状态机（Stage/Event/transition），
      保持 v7 既有接口（OrchestrationContext/OrchestrationStateMachine）向后兼容。
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional


# ===== v8.0 五阶段状态枚举 =====
class Stage(str, Enum):
    """v8.0 五阶段状态枚举"""
    INFO_CONFIRM = "info_confirm"
    CREATIVITY = "creativity"
    VALIDATION = "validation"
    GENERATION = "generation"
    DEEP_ASSIST = "deep_assist"


# 事件枚举
class Event(str, Enum):
    """v8.0 状态机事件枚举"""
    START = "start"
    USER_CONFIRM = "user_confirm"
    CANDIDATES_GENERATED = "candidates_generated"
    EVALUATION_DONE = "evaluation_done"
    SCORE_PASS = "score_pass"
    SCORE_FAIL = "score_fail"
    GENERATION_DONE = "generation_done"
    ENTER_DEEP_ASSIST = "enter_deep_assist"
    RESET = "reset"


# 状态转移表
TRANSITIONS = {
    (Stage.INFO_CONFIRM, Event.USER_CONFIRM): Stage.CREATIVITY,
    (Stage.CREATIVITY, Event.CANDIDATES_GENERATED): Stage.VALIDATION,
    (Stage.VALIDATION, Event.SCORE_PASS): Stage.GENERATION,
    (Stage.VALIDATION, Event.SCORE_FAIL): Stage.CREATIVITY,  # 回退
    (Stage.GENERATION, Event.GENERATION_DONE): Stage.DEEP_ASSIST,
    (Stage.DEEP_ASSIST, Event.RESET): Stage.INFO_CONFIRM,
}


@dataclass
class TransitionResult:
    """状态转移结果"""
    success: bool
    from_stage: Stage
    to_stage: Stage
    event: Event
    message: str
    is_retry: bool = False


def transition(current_stage: Stage, event: Event) -> TransitionResult:
    """执行状态转移

    Args:
        current_stage: 当前阶段
        event: 触发事件

    Returns:
        TransitionResult: 转移结果
    """
    # 处理 RESET 事件
    if event == Event.RESET:
        return TransitionResult(
            success=True,
            from_stage=current_stage,
            to_stage=Stage.INFO_CONFIRM,
            event=event,
            message="重置到信息确权阶段",
        )

    # 处理 START 事件
    if event == Event.START and current_stage is None:
        return TransitionResult(
            success=True,
            from_stage=None,
            to_stage=Stage.INFO_CONFIRM,
            event=event,
            message="启动五阶段流程",
        )

    key = (current_stage, event)
    if key not in TRANSITIONS:
        return TransitionResult(
            success=False,
            from_stage=current_stage,
            to_stage=current_stage,
            event=event,
            message=f"非法转移: {current_stage} + {event}",
        )

    to_stage = TRANSITIONS[key]
    is_retry = (event == Event.SCORE_FAIL)

    messages = {
        (Stage.INFO_CONFIRM, Event.USER_CONFIRM): "用户确认，进入创意阶段",
        (Stage.CREATIVITY, Event.CANDIDATES_GENERATED): "候选生成完成，进入校验阶段",
        (Stage.VALIDATION, Event.SCORE_PASS): "评分通过，进入生成阶段",
        (Stage.VALIDATION, Event.SCORE_FAIL): "评分不通过，回退到创意阶段",
        (Stage.GENERATION, Event.GENERATION_DONE): "生成完成，进入深度辅助",
        (Stage.DEEP_ASSIST, Event.RESET): "重置流程",
    }

    return TransitionResult(
        success=True,
        from_stage=current_stage,
        to_stage=to_stage,
        event=event,
        message=messages.get(key, f"{current_stage} → {to_stage}"),
        is_retry=is_retry,
    )


def get_next_events(current_stage: Stage) -> list[Event]:
    """获取当前阶段可触发的事件列表"""
    next_events = []
    for (stage, event) in TRANSITIONS:
        if stage == current_stage:
            next_events.append(event)
    return next_events


def is_valid_transition(current_stage: Stage, event: Event) -> bool:
    """检查转移是否合法"""
    if event == Event.RESET:
        return True
    return (current_stage, event) in TRANSITIONS


# ===== 向后兼容的旧版状态枚举与状态机 =====
class State(str, Enum):
    """旧版状态枚举（向后兼容）"""
    INIT = "init"
    SEARCHING = "searching"
    REASONING = "reasoning"
    PROPOSAL = "proposal"
    DONE = "done"


class StateMachine:
    """旧版状态机（向后兼容 v7）

    提供简化的线性状态推进接口，与 v7 既有 OrchestrationStateMachine 并存。
    """

    def __init__(self):
        self.state = State.INIT

    def advance(self) -> State:
        """推进到下一状态"""
        order = [State.INIT, State.SEARCHING, State.REASONING, State.PROPOSAL, State.DONE]
        try:
            idx = order.index(self.state)
            if idx < len(order) - 1:
                self.state = order[idx + 1]
        except ValueError:
            self.state = State.INIT
        return self.state

    def reset(self):
        """重置到初始状态"""
        self.state = State.INIT


# ===== v7 既有状态常量（向后兼容） =====
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
