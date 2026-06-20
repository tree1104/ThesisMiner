"""五阶段门禁定义

五阶段闭环导航流：
1. info_confirmation - 信息确权（强制联网检索+用户确认）
2. creativity - 谱系解析与四维创意
3. validation - 重复度评估与硬约束修复
4. generation - 多粒度生成与降重脱敏
5. deep_assist - 深度辅助闭环
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Stage(str, Enum):
    """五阶段枚举"""
    INFO_CONFIRM = "info_confirm"
    CREATIVITY = "creativity"
    VALIDATION = "validation"
    GENERATION = "generation"
    DEEP_ASSIST = "deep_assist"


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

    return GateResult(passed=False, stage=stage, message="未知检查条件")
