"""全流程门禁定义

v8.0 五阶段闭环导航流：
1. info_confirmation - 信息确权（强制联网检索+用户确认）
2. creativity - 谱系解析与四维创意
3. validation - 重复度评估与硬约束修复
4. generation - 多粒度生成与降重脱敏
5. deep_assist - 深度辅助闭环

v9.0 全流程闭环扩展（选题→开题→完成论文）：
6. thesis_writing - 论文撰写（需完成开题生成）
7. defense_prep - 答辩准备（需完成论文撰写）
8. completed - 流程完成
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Stage(str, Enum):
    """全流程阶段枚举"""
    INFO_CONFIRM = "info_confirm"
    CREATIVITY = "creativity"
    VALIDATION = "validation"
    GENERATION = "generation"
    DEEP_ASSIST = "deep_assist"
    # v9.0 新增阶段
    THESIS_WRITING = "thesis_writing"
    DEFENSE_PREP = "defense_prep"
    COMPLETED = "completed"


@dataclass
class GateResult:
    """门禁检查结果"""
    passed: bool
    stage: Stage
    message: str = ""
    data: dict = None
    retry_stage: Optional[Stage] = None  # 回退到的阶段


@dataclass
class StageGate:
    """阶段门禁定义"""
    stage: Stage
    name: str
    description: str
    enter_condition: str  # 进入条件描述
    exit_condition: str   # 退出条件描述
    require_user_confirmation: bool = False
    min_score: int = 0    # 最低通过分数
    retry_on_fail: Optional[Stage] = None  # 失败时回退到的阶段


# 五阶段门禁定义
STAGE_GATES: dict[Stage, StageGate] = {
    Stage.INFO_CONFIRM: StageGate(
        stage=Stage.INFO_CONFIRM,
        name="信息确权",
        description="联网检索近2年文献，展示摘要后等待用户确认",
        enter_condition="用户发起论题生成请求",
        exit_condition="用户确认信息无误",
        require_user_confirmation=True,
    ),
    Stage.CREATIVITY: StageGate(
        stage=Stage.CREATIVITY,
        name="谱系解析与四维创意",
        description="基于检索结果生成候选论题",
        enter_condition="信息确权阶段通过",
        exit_condition="生成至少3个候选论题",
    ),
    Stage.VALIDATION: StageGate(
        stage=Stage.VALIDATION,
        name="重复度评估与硬约束修复",
        description="评估候选论题的新颖性与可行性",
        enter_condition="创意阶段产出候选论题",
        exit_condition="平均评分≥60",
        min_score=60,
        retry_on_fail=Stage.CREATIVITY,
    ),
    Stage.GENERATION: StageGate(
        stage=Stage.GENERATION,
        name="多粒度生成与降重脱敏",
        description="按选定粒度生成开题内容",
        enter_condition="校验阶段通过",
        exit_condition="内容生成完成且通过style_normalizer",
    ),
    Stage.DEEP_ASSIST: StageGate(
        stage=Stage.DEEP_ASSIST,
        name="深度辅助闭环",
        description="文献精读/实验预研/答辩模拟",
        enter_condition="生成阶段完成",
        exit_condition="用户结束或发起新请求",
    ),
    # v9.0 新增阶段门禁
    Stage.THESIS_WRITING: StageGate(
        stage=Stage.THESIS_WRITING,
        name="论文撰写",
        description="基于开题报告进行论文撰写，覆盖各章节",
        enter_condition="生成阶段完成且有开题提案，大纲已批准",
        exit_condition="论文各章节撰写完成",
    ),
    Stage.DEFENSE_PREP: StageGate(
        stage=Stage.DEFENSE_PREP,
        name="答辩准备",
        description="答辩PPT、问题预测、模拟演练",
        enter_condition="论文撰写阶段完成且有论文草稿",
        exit_condition="答辩准备完成",
    ),
    Stage.COMPLETED: StageGate(
        stage=Stage.COMPLETED,
        name="流程完成",
        description="全流程闭环完成",
        enter_condition="答辩准备阶段完成",
        exit_condition="流程结束",
    ),
}


def check_gate(stage: Stage, data: dict = None) -> GateResult:
    """检查阶段门禁是否通过

    Args:
        stage: 当前阶段
        data: 检查数据（如评分、候选数量等）

    Returns:
        GateResult: 门禁检查结果
    """
    gate = STAGE_GATES.get(stage)
    if not gate:
        return GateResult(passed=False, stage=stage, message=f"未知阶段: {stage}")

    data = data or {}

    if stage == Stage.INFO_CONFIRM:
        # 信息确权需要用户确认
        if data.get("user_confirmed"):
            return GateResult(passed=True, stage=stage, message="用户已确认")
        return GateResult(passed=False, stage=stage, message="等待用户确认")

    if stage == Stage.CREATIVITY:
        # 创意阶段需要至少3个候选
        candidates = data.get("candidates", [])
        if len(candidates) >= 3:
            return GateResult(passed=True, stage=stage, message=f"生成{len(candidates)}个候选")
        return GateResult(passed=False, stage=stage, message=f"候选不足，需≥3个，当前{len(candidates)}个")

    if stage == Stage.VALIDATION:
        # 校验阶段需要平均分≥60
        evaluations = data.get("evaluations", [])
        if not evaluations:
            return GateResult(passed=False, stage=stage, message="无评估结果")
        avg_score = sum(e.get("score", 0) for e in evaluations) / len(evaluations)
        if avg_score >= gate.min_score:
            return GateResult(passed=True, stage=stage, message=f"平均评分{avg_score:.0f}≥{gate.min_score}")
        return GateResult(
            passed=False, stage=stage,
            message=f"平均评分{avg_score:.0f}<{gate.min_score}，需回退重新生成",
            retry_stage=gate.retry_on_fail,
        )

    if stage == Stage.GENERATION:
        # 生成阶段需要内容不为空
        content = data.get("content", "")
        if content and len(content) > 0:
            return GateResult(passed=True, stage=stage, message="内容生成完成")
        return GateResult(passed=False, stage=stage, message="生成内容为空")

    if stage == Stage.DEEP_ASSIST:
        return GateResult(passed=True, stage=stage, message="进入深度辅助")

    if stage == Stage.THESIS_WRITING:
        # 论文撰写需要：已完成生成阶段（有提案）+ 大纲已批准
        proposal = data.get("proposal")
        generation_completed = data.get("generation_completed", False)
        outline_approved = data.get("outline_approved", False)
        if not generation_completed:
            return GateResult(passed=False, stage=stage, message="未完成生成阶段，无法进入论文撰写")
        if not proposal:
            return GateResult(passed=False, stage=stage, message="缺少开题提案，无法进入论文撰写")
        if not outline_approved:
            return GateResult(passed=False, stage=stage, message="大纲未批准，无法进入论文撰写")
        return GateResult(passed=True, stage=stage, message="开题提案与大纲就绪，进入论文撰写")

    if stage == Stage.DEFENSE_PREP:
        # 答辩准备需要：已完成论文撰写 + 有论文草稿（至少部分章节）
        thesis_writing_completed = data.get("thesis_writing_completed", False)
        chapters = data.get("chapters", [])
        if not thesis_writing_completed:
            return GateResult(passed=False, stage=stage, message="未完成论文撰写阶段，无法进入答辩准备")
        if not chapters or len(chapters) == 0:
            return GateResult(passed=False, stage=stage, message="缺少论文草稿章节，无法进入答辩准备")
        return GateResult(passed=True, stage=stage, message=f"论文草稿就绪（{len(chapters)}章），进入答辩准备")

    if stage == Stage.COMPLETED:
        return GateResult(passed=True, stage=stage, message="全流程完成")

    return GateResult(passed=False, stage=stage, message="未知检查条件")


# ===== v9.0 会话级门禁检查函数 =====


def check_thesis_writing_gate(session_id: str, data: dict = None) -> tuple[bool, str]:
    """检查会话是否可进入 THESIS_WRITING 阶段。

    进入条件：
        1. 会话中存在开题提案（proposal 非空）
        2. 已完成 GENERATION 阶段（generation_completed 为 True）

    Args:
        session_id: 会话 ID。
        data: 检查数据字典，包含 proposal / generation_completed / outline_approved 等字段。
              若为 None，则尝试从会话存储获取（当前实现以 data 为主）。

    Returns:
        (passed, reason): passed 为是否通过，reason 为说明文本。
    """
    data = data or {}
    proposal = data.get("proposal")
    generation_completed = data.get("generation_completed", False)
    outline_approved = data.get("outline_approved", False)

    if not generation_completed:
        return (False, f"会话 {session_id} 未完成生成阶段，无法进入论文撰写")
    if not proposal:
        return (False, f"会话 {session_id} 缺少开题提案，无法进入论文撰写")
    if not outline_approved:
        return (False, f"会话 {session_id} 大纲未批准，无法进入论文撰写")
    return (True, f"会话 {session_id} 开题提案与大纲就绪，可进入论文撰写")


def check_defense_prep_gate(session_id: str, data: dict = None) -> tuple[bool, str]:
    """检查会话是否可进入 DEFENSE_PREP 阶段。

    进入条件：
        1. 已完成 THESIS_WRITING 阶段（thesis_writing_completed 为 True）
        2. 存在论文草稿章节（chapters 列表非空）

    Args:
        session_id: 会话 ID。
        data: 检查数据字典，包含 thesis_writing_completed / chapters 等字段。
              若为 None，则尝试从会话存储获取（当前实现以 data 为主）。

    Returns:
        (passed, reason): passed 为是否通过，reason 为说明文本。
    """
    data = data or {}
    thesis_writing_completed = data.get("thesis_writing_completed", False)
    chapters = data.get("chapters", [])

    if not thesis_writing_completed:
        return (False, f"会话 {session_id} 未完成论文撰写阶段，无法进入答辩准备")
    if not chapters or len(chapters) == 0:
        return (False, f"会话 {session_id} 缺少论文草稿章节，无法进入答辩准备")
    return (True, f"会话 {session_id} 论文草稿就绪（{len(chapters)}章），可进入答辩准备")


# 阶段门禁注册表：阶段 → 会话级检查函数
GATE_REGISTRY: dict[Stage, callable] = {
    Stage.THESIS_WRITING: check_thesis_writing_gate,
    Stage.DEFENSE_PREP: check_defense_prep_gate,
}
