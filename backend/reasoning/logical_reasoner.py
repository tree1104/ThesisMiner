"""逻辑推理器模块

提供完整的逻辑推理能力，包括：
    - 演绎推理、归纳推理、类比推理、因果推理
    - 论证结构分析、论证强度评估、逻辑谬误检测
    - 假设识别、前提验证、结论推导
    - 推理链构建、推理可视化、推理验证
    - 完整的推理规则、谬误数据库

设计原则：
    1. 零外部依赖：仅使用 Python 标准库
    2. 线程安全：所有公共方法通过 RLock 保护
    3. 可持久化：基于 dataclass，支持序列化
    4. 规则可扩展：推理规则、谬误定义均可动态扩展

核心数据结构：
    - ReasoningStep: 推理步骤（前提、结论、规则）
    - ReasoningChain: 推理链（多步骤序列）
    - LogicalFallacy: 逻辑谬误（类型、描述、示例）
"""
from __future__ import annotations

import re
import threading
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Iterable, Optional


# ===== 常量定义 =====

# 推理类型
REASONING_TYPES = {
    "deductive": "演绎推理",
    "inductive": "归纳推理",
    "abductive": "溯因推理",
    "analogical": "类比推理",
    "causal": "因果推理",
    "statistical": "统计推理",
}

# 推理有效性等级
VALIDITY_LEVELS = {
    "valid": "有效",
    "strong": "强",
    "moderate": "中等",
    "weak": "弱",
    "invalid": "无效",
}

# 前提类型
PREMISE_TYPES = {
    "fact": "事实",
    "definition": "定义",
    "assumption": "假设",
    "evidence": "证据",
    "testimony": "证言",
    "statistic": "统计数据",
    "principle": "原理",
}

# 谬误类型分类
FALLACY_CATEGORIES = {
    "formal": "形式谬误",
    "informal": "非形式谬误",
    "relevance": "相关性谬误",
    "ambiguity": "歧义谬误",
    "presumption": "预设谬误",
}

# 逻辑连接词（中文）
LOGICAL_CONNECTIVES = {
    "therefore": ["因此", "所以", "故", "由此", "可见", "得出"],
    "because": ["因为", "由于", "基于", "鉴于"],
    "if": ["如果", "若", "假如", "假设", "倘若"],
    "then": ["那么", "则", "就", "便"],
    "all": ["所有", "凡是", "任何", "每个"],
    "some": ["有些", "某些", "部分", "存在"],
    "none": ["没有", "无", "不存在", "都不"],
    "and": ["并且", "且", "同时", "以及"],
    "or": ["或者", "或", "要么"],
    "not": ["不", "非", "未", "没有"],
    "implies": ["蕴含", "推导", "意味着", "必然"],
    "equivalent": ["等价", "当且仅当", "充要"],
}

# 谬误数据库（精选常见逻辑谬误）
FALLACY_DATABASE = [
    {
        "id": "fallacy_affirming_consequent",
        "name": "肯定后件",
        "category": "formal",
        "description": "从「如果 P 则 Q」和「Q」推出「P」",
        "example": "如果下雨则地湿；地湿；所以下雨了。（可能洒水车经过）",
        "detection_pattern": r"如果.*则.*[；。].*所以",
    },
    {
        "id": "fallacy_denying_antecedent",
        "name": "否定前件",
        "category": "formal",
        "description": "从「如果 P 则 Q」和「非 P」推出「非 Q」",
        "example": "如果下雨则地湿；没下雨；所以地不湿。（可能其他原因导致地湿）",
        "detection_pattern": r"如果.*则.*[；。].*没.*所以.*不",
    },
    {
        "id": "fallacy_ad_hominem",
        "name": "人身攻击",
        "category": "relevance",
        "description": "攻击提出论点的人而非论点本身",
        "example": "他的观点不可信，因为他品行不端。",
        "detection_pattern": r"(品行|人格|道德|长相|出身).*(不可信|错误|不对)",
    },
    {
        "id": "fallacy_straw_man",
        "name": "稻草人谬误",
        "category": "relevance",
        "description": "歪曲对方观点后攻击歪曲后的版本",
        "example": "你说要环保，就是要我们回到原始社会吗？",
        "detection_pattern": r"(就是|等价于|意味着).*(回到|放弃|消灭|取消)",
    },
    {
        "id": "fallacy_appeal_authority",
        "name": "诉诸权威",
        "category": "relevance",
        "description": "仅因权威人士支持就认为论点正确",
        "example": "某专家这么说，所以一定是对的。",
        "detection_pattern": r"(专家|教授|权威|名人).*(所以|因此|必然).*(对|正确)",
    },
    {
        "id": "fallacy_appeal_popularity",
        "name": "诉诸大众",
        "category": "relevance",
        "description": "因多数人相信就认为正确",
        "example": "大家都这么认为，所以是对的。",
        "detection_pattern": r"(大家|多数人|所有人都).*(所以|因此).*(对|正确)",
    },
    {
        "id": "fallacy_slippery_slope",
        "name": "滑坡谬误",
        "category": "presumption",
        "description": "夸大连锁后果，无充分证据",
        "example": "如果允许 A，就会导致 B，进而导致 C，最终毁灭。",
        "detection_pattern": r"(导致|引发|引起).*(进而|然后|最终).*(毁灭|灾难|崩溃)",
    },
    {
        "id": "fallacy_false_dilemma",
        "name": "虚假两难",
        "category": "presumption",
        "description": "只给出两个选择，忽略其他可能",
        "example": "要么支持，要么反对，没有中间立场。",
        "detection_pattern": r"(要么.*要么|不是.*就是|只有.*或者).*(没有|不存在)",
    },
    {
        "id": "fallacy_circular",
        "name": "循环论证",
        "category": "presumption",
        "description": "结论作为前提使用",
        "example": "A 是对的，因为 B 说 A 对；B 可信，因为 A 说 B 可信。",
        "detection_pattern": r"因为.*所以.*因为",
    },
    {
        "id": "fallacy_hasty_generalization",
        "name": "以偏概全",
        "category": "presumption",
        "description": "从少数案例推出普遍结论",
        "example": "我见到的三个 X 都如此，所以所有 X 都如此。",
        "detection_pattern": r"(我见到|我看到|我遇到).*(所以|因此).*(所有|全部|都)",
    },
    {
        "id": "fallacy_post_hoc",
        "name": "事后归因",
        "category": "presumption",
        "description": "因 B 在 A 之后发生，就认为 A 导致 B",
        "example": "公鸡打鸣后太阳升起，所以公鸡打鸣导致日出。",
        "detection_pattern": r"之后.*所以.*导致",
    },
    {
        "id": "fallacy_equivocation",
        "name": "歧义谬误",
        "category": "ambiguity",
        "description": "同一词在不同语境下含义不同",
        "example": "银行（河岸）有树，银行（金融机构）也有树（盆栽）。",
        "detection_pattern": r"",
    },
    {
        "id": "fallacy_composition",
        "name": "合成谬误",
        "category": "ambiguity",
        "description": "从部分属性推出整体属性",
        "example": "每个零件都轻，所以整台机器也轻。",
        "detection_pattern": r"每个.*都.*所以.*整体.*也",
    },
    {
        "id": "fallacy_division",
        "name": "分解谬误",
        "category": "ambiguity",
        "description": "从整体属性推出部分属性",
        "example": "这台机器很重，所以每个零件都很重。",
        "detection_pattern": r"整体.*所以.*每个.*也",
    },
    {
        "id": "fallacy_appeal_ignorance",
        "name": "诉诸无知",
        "category": "presumption",
        "description": "因未被证伪就认为正确，或未被证实就认为错误",
        "example": "没人证明它错，所以它对。",
        "detection_pattern": r"(没人|无法|不能).*(证明|证伪).*(所以|因此).*(对|错|正确|错误)",
    },
    {
        "id": "fallacy_bandwagon",
        "name": "从众谬误",
        "category": "relevance",
        "description": "因多数人做就认为正确",
        "example": "大家都买这只股票，所以它一定好。",
        "detection_pattern": r"(大家|多数人|所有人).*(买|做|选).*(所以|因此).*(好|对|正确)",
    },
    {
        "id": "fallacy_red_herring",
        "name": "转移话题",
        "category": "relevance",
        "description": "引入无关话题转移注意力",
        "example": "你说我迟到，但小王昨天也迟到了。",
        "detection_pattern": r"但.*也",
    },
    {
        "id": "fallacy_tu_quoque",
        "name": "你也一样",
        "category": "relevance",
        "description": "以对方也犯错来为自己辩护",
        "example": "你说我抽烟不好，你自己不也抽吗？",
        "detection_pattern": r"你自己.*也.*不也.*吗",
    },
]

# 演绎推理规则模板（经典三段论等）
DEDUCTIVE_RULES = [
    {
        "id": "rule_modus_ponens",
        "name": "肯定前件（Modus Ponens）",
        "pattern": {"premise1": "如果 P 则 Q", "premise2": "P", "conclusion": "Q"},
        "validity": "valid",
    },
    {
        "id": "rule_modus_tollens",
        "name": "否定后件（Modus Tollens）",
        "pattern": {"premise1": "如果 P 则 Q", "premise2": "非 Q", "conclusion": "非 P"},
        "validity": "valid",
    },
    {
        "id": "rule_hypothetical_syllogism",
        "name": "假言三段论",
        "pattern": {"premise1": "如果 P 则 Q", "premise2": "如果 Q 则 R", "conclusion": "如果 P 则 R"},
        "validity": "valid",
    },
    {
        "id": "rule_disjunctive_syllogism",
        "name": "选言三段论",
        "pattern": {"premise1": "P 或 Q", "premise2": "非 P", "conclusion": "Q"},
        "validity": "valid",
    },
    {
        "id": "rule_categorical_syllogism",
        "name": "直言三段论",
        "pattern": {"premise1": "所有 M 是 P", "premise2": "所有 S 是 M", "conclusion": "所有 S 是 P"},
        "validity": "valid",
    },
]

# 归纳推理强度评估指标
INDUCTIVE_STRENGTH_FACTORS = {
    "sample_size": "样本量",
    "sample_representativeness": "样本代表性",
    "evidence_diversity": "证据多样性",
    "consistency": "一致性",
    "counterexample_count": "反例数量",
}


# ===== 数据结构 =====


@dataclass
class ReasoningStep:
    """推理步骤数据结构。

    Attributes:
        id: 步骤 ID。
        step_type: 步骤类型（premise/inference/conclusion）。
        content: 步骤内容。
        rule: 使用的推理规则。
        premises: 前提步骤 ID 列表。
        confidence: 置信度（0-1）。
        metadata: 扩展元数据。
    """

    id: str = ""
    step_type: str = "premise"
    content: str = ""
    rule: str = ""
    premises: list[str] = field(default_factory=list)
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return asdict(self)


@dataclass
class LogicalFallacy:
    """逻辑谬误数据结构。

    Attributes:
        id: 谬误 ID。
        name: 谬误名称。
        category: 谬误类别。
        description: 谬误描述。
        example: 示例。
        detected_in: 检测到的文本片段。
        severity: 严重程度（critical/major/minor）。
    """

    id: str = ""
    name: str = ""
    category: str = "informal"
    description: str = ""
    example: str = ""
    detected_in: str = ""
    severity: str = "major"

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return asdict(self)


@dataclass
class ReasoningChain:
    """推理链数据结构。

    Attributes:
        id: 推理链 ID。
        reasoning_type: 推理类型。
        steps: 推理步骤列表。
        conclusion: 最终结论。
        validity: 有效性等级。
        confidence: 整体置信度。
        fallacies: 检测到的谬误列表。
        created_at: 创建时间。
        metadata: 扩展元数据。
    """

    id: str = ""
    reasoning_type: str = "deductive"
    steps: list[ReasoningStep] = field(default_factory=list)
    conclusion: str = ""
    validity: str = "valid"
    confidence: float = 1.0
    fallacies: list[LogicalFallacy] = field(default_factory=list)
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "id": self.id,
            "reasoning_type": self.reasoning_type,
            "reasoning_type_name": REASONING_TYPES.get(self.reasoning_type, self.reasoning_type),
            "steps": [s.to_dict() for s in self.steps],
            "conclusion": self.conclusion,
            "validity": self.validity,
            "validity_name": VALIDITY_LEVELS.get(self.validity, self.validity),
            "confidence": self.confidence,
            "fallacies": [f.to_dict() for f in self.fallacies],
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    def premise_steps(self) -> list[ReasoningStep]:
        """获取所有前提步骤。"""
        return [s for s in self.steps if s.step_type == "premise"]

    def conclusion_steps(self) -> list[ReasoningStep]:
        """获取所有结论步骤。"""
        return [s for s in self.steps if s.step_type == "conclusion"]

    def inference_steps(self) -> list[ReasoningStep]:
        """获取所有推理步骤。"""
        return [s for s in self.steps if s.step_type == "inference"]


@dataclass
class Premise:
    """前提数据结构。

    Attributes:
        id: 前提 ID。
        content: 前提内容。
        premise_type: 前提类型。
        is_explicit: 是否明确陈述。
        confidence: 置信度。
        source: 来源。
        verified: 是否已验证。
    """

    id: str = ""
    content: str = ""
    premise_type: str = "fact"
    is_explicit: bool = True
    confidence: float = 1.0
    source: str = ""
    verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return asdict(self)


# ===== 主类实现 =====


class LogicalReasoner:
    """逻辑推理器主类。

    提供演绎推理、归纳推理、类比推理、因果推理、论证结构分析、
    论证强度评估、逻辑谬误检测、假设识别、前提验证、结论推导、
    推理链构建、推理可视化、推理验证等能力。

    线程安全：所有公共方法通过 RLock 保护。
    """

    def __init__(self):
        """初始化逻辑推理器。"""
        self._lock = threading.RLock()
        self._chains: dict[str, ReasoningChain] = {}
        self._fallacies_db: list[dict[str, Any]] = list(FALLACY_DATABASE)
        self._rules_db: list[dict[str, Any]] = list(DEDUCTIVE_RULES)

    # ===== 推理链构建 =====

    def create_chain(
        self,
        reasoning_type: str = "deductive",
        premises: Optional[list[str]] = None,
        conclusion: str = "",
    ) -> ReasoningChain:
        """创建推理链。

        Args:
            reasoning_type: 推理类型。
            premises: 前提内容列表。
            conclusion: 结论内容。

        Returns:
            创建的推理链实例。
        """
        with self._lock:
            if reasoning_type not in REASONING_TYPES:
                raise ValueError(f"未知推理类型: {reasoning_type}")
            chain_id = f"chain_{uuid.uuid4().hex[:10]}"
            steps: list[ReasoningStep] = []
            # 添加前提步骤
            premise_ids: list[str] = []
            for p in (premises or []):
                step = ReasoningStep(
                    id=f"step_{uuid.uuid4().hex[:8]}",
                    step_type="premise",
                    content=p,
                    confidence=1.0,
                )
                steps.append(step)
                premise_ids.append(step.id)
            # 添加结论步骤
            if conclusion:
                concl_step = ReasoningStep(
                    id=f"step_{uuid.uuid4().hex[:8]}",
                    step_type="conclusion",
                    content=conclusion,
                    premises=premise_ids,
                    confidence=1.0,
                )
                steps.append(concl_step)
            chain = ReasoningChain(
                id=chain_id,
                reasoning_type=reasoning_type,
                steps=steps,
                conclusion=conclusion,
                created_at=datetime.now().isoformat(),
            )
            # 自动评估
            chain.validity = self._evaluate_validity(chain)
            chain.confidence = self._evaluate_confidence(chain)
            chain.fallacies = self._detect_fallacies_in_chain(chain)
            self._chains[chain_id] = chain
            return chain

    def add_premise(
        self,
        chain_id: str,
        content: str,
        premise_type: str = "fact",
        confidence: float = 1.0,
    ) -> Optional[ReasoningStep]:
        """向推理链添加前提。"""
        with self._lock:
            chain = self._chains.get(chain_id)
            if not chain:
                return None
            step = ReasoningStep(
                id=f"step_{uuid.uuid4().hex[:8]}",
                step_type="premise",
                content=content,
                rule=premise_type,
                confidence=confidence,
            )
            chain.steps.append(step)
            # 重新评估
            chain.validity = self._evaluate_validity(chain)
            chain.confidence = self._evaluate_confidence(chain)
            return step

    def add_inference(
        self,
        chain_id: str,
        content: str,
        rule: str = "",
        premise_ids: Optional[list[str]] = None,
        confidence: float = 1.0,
    ) -> Optional[ReasoningStep]:
        """向推理链添加中间推理步骤。"""
        with self._lock:
            chain = self._chains.get(chain_id)
            if not chain:
                return None
            step = ReasoningStep(
                id=f"step_{uuid.uuid4().hex[:8]}",
                step_type="inference",
                content=content,
                rule=rule,
                premises=premise_ids or [],
                confidence=confidence,
            )
            chain.steps.append(step)
            chain.validity = self._evaluate_validity(chain)
            chain.confidence = self._evaluate_confidence(chain)
            return step

    def set_conclusion(
        self, chain_id: str, conclusion: str, premise_ids: Optional[list[str]] = None
    ) -> bool:
        """设置推理链结论。"""
        with self._lock:
            chain = self._chains.get(chain_id)
            if not chain:
                return False
            chain.conclusion = conclusion
            # 添加结论步骤
            concl_step = ReasoningStep(
                id=f"step_{uuid.uuid4().hex[:8]}",
                step_type="conclusion",
                content=conclusion,
                premises=premise_ids or [],
            )
            chain.steps.append(concl_step)
            chain.validity = self._evaluate_validity(chain)
            chain.confidence = self._evaluate_confidence(chain)
            chain.fallacies = self._detect_fallacies_in_chain(chain)
            return True

    # ===== 推理类型实现 =====

    def deductive_reasoning(
        self,
        major_premise: str,
        minor_premise: str,
        conclusion: str,
    ) -> ReasoningChain:
        """演绎推理（三段论）。

        Args:
            major_premise: 大前提。
            minor_premise: 小前提。
            conclusion: 结论。

        Returns:
            推理链实例。
        """
        return self.create_chain(
            reasoning_type="deductive",
            premises=[major_premise, minor_premise],
            conclusion=conclusion,
        )

    def inductive_reasoning(
        self,
        observations: list[str],
        conclusion: str,
        confidence: float = 0.7,
    ) -> ReasoningChain:
        """归纳推理（从特殊到一般）。

        Args:
            observations: 观察案例列表。
            conclusion: 归纳结论。
            confidence: 置信度。

        Returns:
            推理链实例。
        """
        with self._lock:
            chain = self.create_chain(
                reasoning_type="inductive",
                premises=observations,
                conclusion=conclusion,
            )
            # 归纳推理的置信度取决于样本量
            sample_confidence = min(1.0, len(observations) / 30.0)
            chain.confidence = min(confidence, sample_confidence)
            # 归纳推理不保证有效，只评估强度
            chain.validity = self._evaluate_inductive_strength(observations, conclusion)
            return chain

    def abductive_reasoning(
        self,
        observation: str,
        hypotheses: list[str],
    ) -> ReasoningChain:
        """溯因推理（从结果推导最佳解释）。

        Args:
            observation: 观察现象。
            hypotheses: 可能解释列表。

        Returns:
            推理链实例。
        """
        with self._lock:
            # 选择最佳解释（简化：选第一个）
            best = hypotheses[0] if hypotheses else ""
            chain = self.create_chain(
                reasoning_type="abductive",
                premises=[observation] + hypotheses,
                conclusion=f"最佳解释：{best}",
            )
            chain.confidence = 0.6  # 溯因推理置信度通常较低
            chain.validity = "moderate"
            return chain

    def analogical_reasoning(
        self,
        source_domain: str,
        target_domain: str,
        mappings: list[tuple[str, str]],
        conclusion: str,
    ) -> ReasoningChain:
        """类比推理。

        Args:
            source_domain: 源领域。
            target_domain: 目标领域。
            mappings: 映射对列表 [(源属性, 目标属性)]。
            conclusion: 类比结论。

        Returns:
            推理链实例。
        """
        with self._lock:
            premises = [f"源领域：{source_domain}", f"目标领域：{target_domain}"]
            for src, tgt in mappings:
                premises.append(f"映射：{src} → {tgt}")
            chain = self.create_chain(
                reasoning_type="analogical",
                premises=premises,
                conclusion=conclusion,
            )
            # 类比强度取决于映射数量与相关性
            strength = min(1.0, len(mappings) / 5.0)
            chain.confidence = strength
            chain.validity = "strong" if strength >= 0.8 else (
                "moderate" if strength >= 0.5 else "weak"
            )
            return chain

    def causal_reasoning(
        self,
        cause: str,
        effect: str,
        mechanism: str = "",
        evidence: Optional[list[str]] = None,
    ) -> ReasoningChain:
        """因果推理。

        Args:
            cause: 原因。
            effect: 结果。
            mechanism: 因果机制。
            evidence: 支持证据列表。

        Returns:
            推理链实例。
        """
        with self._lock:
            premises = [f"原因：{cause}", f"结果：{effect}"]
            if mechanism:
                premises.append(f"机制：{mechanism}")
            if evidence:
                premises.extend(evidence)
            chain = self.create_chain(
                reasoning_type="causal",
                premises=premises,
                conclusion=f"{cause} 导致 {effect}",
            )
            # 因果推理强度取决于机制明确性与证据
            base = 0.5
            if mechanism:
                base += 0.2
            if evidence:
                base += min(0.3, len(evidence) * 0.1)
            chain.confidence = min(1.0, base)
            chain.validity = "strong" if base >= 0.8 else (
                "moderate" if base >= 0.6 else "weak"
            )
            return chain

    # ===== 评估方法 =====

    def _evaluate_validity(self, chain: ReasoningChain) -> str:
        """评估推理有效性。

        Args:
            chain: 推理链。

        Returns:
            有效性等级。
        """
        if chain.reasoning_type == "deductive":
            return self._evaluate_deductive_validity(chain)
        elif chain.reasoning_type == "inductive":
            return self._evaluate_inductive_strength(
                [s.content for s in chain.premise_steps()],
                chain.conclusion,
            )
        elif chain.reasoning_type == "analogical":
            return chain.validity
        elif chain.reasoning_type == "causal":
            return chain.validity
        elif chain.reasoning_type == "abductive":
            return "moderate"
        return "moderate"

    def _evaluate_deductive_validity(self, chain: ReasoningChain) -> str:
        """评估演绎推理有效性。

        Args:
            chain: 推理链。

        Returns:
            有效性等级。
        """
        premises = chain.premise_steps()
        if len(premises) < 2:
            return "weak"
        # 检测是否匹配已知规则模式
        premise_texts = [p.content for p in premises]
        for rule in self._rules_db:
            if self._match_rule(rule, premise_texts, chain.conclusion):
                return "valid"
        # 简化：若有两个以上前提且有结论，认为中等
        if len(premises) >= 2 and chain.conclusion:
            return "moderate"
        return "weak"

    def _match_rule(
        self, rule: dict[str, Any], premises: list[str], conclusion: str
    ) -> bool:
        """检测前提与结论是否匹配规则模式。

        Args:
            rule: 规则字典。
            premises: 前提文本列表。
            conclusion: 结论文本。

        Returns:
            是否匹配。
        """
        pattern = rule.get("pattern", {})
        # 简化匹配：检测关键词
        p1 = pattern.get("premise1", "")
        p2 = pattern.get("premise2", "")
        concl = pattern.get("conclusion", "")
        # 检测「如果...则...」模式
        if "如果" in p1 and "如果" in p2:
            has_conditional = any("如果" in p or "若" in p for p in premises)
            return has_conditional
        if "所有" in p1 and "所有" in p2:
            has_universal = any("所有" in p or "凡是" in p for p in premises)
            return has_universal
        return False

    def _evaluate_inductive_strength(
        self, observations: list[str], conclusion: str
    ) -> str:
        """评估归纳推理强度。

        Args:
            observations: 观察列表。
            conclusion: 结论。

        Returns:
            强度等级。
        """
        n = len(observations)
        if n >= 30:
            return "strong"
        elif n >= 10:
            return "moderate"
        elif n >= 3:
            return "weak"
        return "invalid"

    def _evaluate_confidence(self, chain: ReasoningChain) -> float:
        """评估推理整体置信度。

        Args:
            chain: 推理链。

        Returns:
            置信度（0-1）。
        """
        if not chain.steps:
            return 0.0
        # 取所有步骤置信度的加权平均
        total_weight = 0.0
        weighted_sum = 0.0
        for step in chain.steps:
            weight = 2.0 if step.step_type == "premise" else 1.0
            weighted_sum += step.confidence * weight
            total_weight += weight
        if total_weight == 0:
            return 0.0
        return round(weighted_sum / total_weight, 4)

    # ===== 谬误检测 =====

    def detect_fallacies(self, text: str) -> list[LogicalFallacy]:
        """检测文本中的逻辑谬误。

        Args:
            text: 待检测文本。

        Returns:
            检测到的谬误列表。
        """
        with self._lock:
            detected: list[LogicalFallacy] = []
            for fallacy_def in self._fallacies_db:
                pattern = fallacy_def.get("detection_pattern", "")
                if not pattern:
                    continue
                try:
                    match = re.search(pattern, text)
                    if match:
                        detected.append(LogicalFallacy(
                            id=fallacy_def["id"],
                            name=fallacy_def["name"],
                            category=fallacy_def["category"],
                            description=fallacy_def["description"],
                            example=fallacy_def.get("example", ""),
                            detected_in=match.group(0),
                            severity=self._assess_fallacy_severity(fallacy_def),
                        ))
                except re.error:
                    continue
            return detected

    def _detect_fallacies_in_chain(self, chain: ReasoningChain) -> list[LogicalFallacy]:
        """检测推理链中的谬误。"""
        # 拼接所有步骤内容
        full_text = " ".join(s.content for s in chain.steps)
        if chain.conclusion:
            full_text += " " + chain.conclusion
        return self.detect_fallacies(full_text)

    def _assess_fallacy_severity(self, fallacy_def: dict[str, Any]) -> str:
        """评估谬误严重程度。"""
        cat = fallacy_def.get("category", "")
        if cat == "formal":
            return "critical"
        if cat in ("presumption", "relevance"):
            return "major"
        return "minor"

    def get_fallacy_database(self) -> list[dict[str, Any]]:
        """获取谬误数据库。"""
        with self._lock:
            return list(self._fallacies_db)

    def add_fallacy(
        self,
        name: str,
        category: str,
        description: str,
        example: str = "",
        detection_pattern: str = "",
    ) -> dict[str, Any]:
        """添加自定义谬误。"""
        with self._lock:
            fallacy = {
                "id": f"fallacy_custom_{uuid.uuid4().hex[:8]}",
                "name": name,
                "category": category,
                "description": description,
                "example": example,
                "detection_pattern": detection_pattern,
            }
            self._fallacies_db.append(fallacy)
            return fallacy

    # ===== 假设识别 =====

    def identify_assumptions(
        self, chain_id: str
    ) -> list[Premise]:
        """识别推理链中的隐含假设。

        Args:
            chain_id: 推理链 ID。

        Returns:
            隐含假设列表。
        """
        with self._lock:
            chain = self._chains.get(chain_id)
            if not chain:
                return []
            assumptions: list[Premise] = []
            premises = chain.premise_steps()
            conclusion = chain.conclusion
            if not premises or not conclusion:
                return assumptions
            # 检测常见隐含假设模式
            # 1. 因果假设：从相关推出因果
            if any("相关" in p.content for p in premises) and "导致" in conclusion:
                assumptions.append(Premise(
                    id=f"asm_{uuid.uuid4().hex[:8]}",
                    content="相关性意味着因果关系",
                    premise_type="assumption",
                    is_explicit=False,
                    confidence=0.3,
                ))
            # 2. 代表性假设：从样本推出总体
            if chain.reasoning_type == "inductive":
                assumptions.append(Premise(
                    id=f"asm_{uuid.uuid4().hex[:8]}",
                    content="样本具有代表性，可推广到总体",
                    premise_type="assumption",
                    is_explicit=False,
                    confidence=0.5,
                ))
            # 3. 类比假设：源域与目标域相似
            if chain.reasoning_type == "analogical":
                assumptions.append(Premise(
                    id=f"asm_{uuid.uuid4().hex[:8]}",
                    content="源领域与目标领域在关键方面相似",
                    premise_type="assumption",
                    is_explicit=False,
                    confidence=0.6,
                ))
            # 4. 因果机制假设
            if chain.reasoning_type == "causal":
                assumptions.append(Premise(
                    id=f"asm_{uuid.uuid4().hex[:8]}",
                    content="存在明确的因果机制连接原因与结果",
                    premise_type="assumption",
                    is_explicit=False,
                    confidence=0.7,
                ))
            # 5. 排除他因假设
            assumptions.append(Premise(
                id=f"asm_{uuid.uuid4().hex[:8]}",
                content="已排除其他可能的解释",
                premise_type="assumption",
                is_explicit=False,
                confidence=0.5,
            ))
            return assumptions

    def verify_premise(
        self, chain_id: str, premise_id: str, verified: bool, evidence: str = ""
    ) -> bool:
        """验证前提。

        Args:
            chain_id: 推理链 ID。
            premise_id: 前提步骤 ID。
            verified: 是否验证通过。
            evidence: 验证证据。

        Returns:
            是否更新成功。
        """
        with self._lock:
            chain = self._chains.get(chain_id)
            if not chain:
                return False
            for step in chain.steps:
                if step.id == premise_id:
                    step.metadata = step.metadata or {}
                    step.metadata["verified"] = verified
                    step.metadata["evidence"] = evidence
                    if not verified:
                        step.confidence *= 0.5  # 未验证则降低置信度
                    chain.confidence = self._evaluate_confidence(chain)
                    return True
            return False

    # ===== 推理验证 =====

    def validate_chain(self, chain_id: str) -> dict[str, Any]:
        """验证推理链。

        Args:
            chain_id: 推理链 ID。

        Returns:
            验证结果字典。
        """
        with self._lock:
            chain = self._chains.get(chain_id)
            if not chain:
                return {}
            issues: list[str] = []
            # 检查前提数量
            premises = chain.premise_steps()
            if len(premises) < 2:
                issues.append("前提数量不足（建议至少 2 个）")
            # 检查结论
            if not chain.conclusion:
                issues.append("缺少明确结论")
            # 检查置信度
            if chain.confidence < 0.5:
                issues.append(f"整体置信度偏低（{chain.confidence:.0%}）")
            # 检查谬误
            if chain.fallacies:
                critical = [f for f in chain.fallacies if f.severity == "critical"]
                if critical:
                    issues.append(f"存在 {len(critical)} 个严重谬误")
                major = [f for f in chain.fallacies if f.severity == "major"]
                if major:
                    issues.append(f"存在 {len(major)} 个主要谬误")
            # 检查隐含假设
            assumptions = self.identify_assumptions(chain_id)
            if assumptions:
                issues.append(f"存在 {len(assumptions)} 个隐含假设需验证")
            # 检查前提是否已验证
            unverified = [
                s for s in premises
                if not s.metadata.get("verified", False)
            ]
            if unverified:
                issues.append(f"有 {len(unverified)} 个前提未验证")
            return {
                "chain_id": chain_id,
                "is_valid": len(issues) == 0,
                "validity": chain.validity,
                "validity_name": VALIDITY_LEVELS.get(chain.validity, chain.validity),
                "confidence": chain.confidence,
                "issue_count": len(issues),
                "issues": issues,
                "premise_count": len(premises),
                "fallacy_count": len(chain.fallacies),
                "assumption_count": len(assumptions),
                "unverified_premise_count": len(unverified),
            }

    # ===== 推理可视化 =====

    def visualize_chain(self, chain_id: str) -> dict[str, Any]:
        """生成推理链可视化数据。

        Args:
            chain_id: 推理链 ID。

        Returns:
            可视化数据字典（节点 + 边）。
        """
        with self._lock:
            chain = self._chains.get(chain_id)
            if not chain:
                return {}
            nodes: list[dict[str, Any]] = []
            edges: list[dict[str, Any]] = []
            for step in chain.steps:
                color = {
                    "premise": "#0d6efd",
                    "inference": "#fd7e14",
                    "conclusion": "#198754",
                }.get(step.step_type, "#6c757d")
                nodes.append({
                    "id": step.id,
                    "label": step.content[:50] + ("..." if len(step.content) > 50 else ""),
                    "type": step.step_type,
                    "color": color,
                    "confidence": step.confidence,
                    "rule": step.rule,
                })
                # 添加依赖边
                for dep_id in step.premises:
                    edges.append({
                        "source": dep_id,
                        "target": step.id,
                        "label": step.rule or "推导",
                    })
            return {
                "chain_id": chain_id,
                "reasoning_type": chain.reasoning_type,
                "reasoning_type_name": REASONING_TYPES.get(chain.reasoning_type, chain.reasoning_type),
                "nodes": nodes,
                "edges": edges,
                "validity": chain.validity,
                "confidence": chain.confidence,
                "fallacies": [f.to_dict() for f in chain.fallacies],
            }

    def visualize_chain_text(self, chain_id: str) -> str:
        """生成推理链文本可视化。

        Args:
            chain_id: 推理链 ID。

        Returns:
            文本可视化字符串。
        """
        with self._lock:
            chain = self._chains.get(chain_id)
            if not chain:
                return ""
            lines: list[str] = []
            lines.append(f"=== 推理链 [{chain.id}] ===")
            lines.append(f"类型：{REASONING_TYPES.get(chain.reasoning_type, chain.reasoning_type)}")
            lines.append(f"有效性：{VALIDITY_LEVELS.get(chain.validity, chain.validity)}")
            lines.append(f"置信度：{chain.confidence:.0%}")
            lines.append("")
            for i, step in enumerate(chain.steps, 1):
                prefix = {"premise": "前提", "inference": "推理", "conclusion": "结论"}.get(
                    step.step_type, step.step_type
                )
                lines.append(f"{i}. [{prefix}] {step.content}")
                if step.premises:
                    lines.append(f"   ← 依赖：{', '.join(step.premises)}")
                if step.rule:
                    lines.append(f"   规则：{step.rule}")
                lines.append(f"   置信度：{step.confidence:.0%}")
            if chain.conclusion:
                lines.append("")
                lines.append(f"==> 结论：{chain.conclusion}")
            if chain.fallacies:
                lines.append("")
                lines.append("检测到的谬误：")
                for f in chain.fallacies:
                    lines.append(f"  ! [{f.severity}] {f.name}：{f.description}")
            return "\n".join(lines)

    # ===== 查询方法 =====

    def get_chain(self, chain_id: str) -> Optional[ReasoningChain]:
        """获取推理链。"""
        with self._lock:
            return self._chains.get(chain_id)

    def list_chains(
        self, reasoning_type: Optional[str] = None
    ) -> list[ReasoningChain]:
        """列出推理链。"""
        with self._lock:
            chains = list(self._chains.values())
            if reasoning_type:
                chains = [c for c in chains if c.reasoning_type == reasoning_type]
            return chains

    def delete_chain(self, chain_id: str) -> bool:
        """删除推理链。"""
        with self._lock:
            if chain_id in self._chains:
                del self._chains[chain_id]
                return True
            return False

    # ===== 规则管理 =====

    def get_rules_database(self) -> list[dict[str, Any]]:
        """获取推理规则数据库。"""
        with self._lock:
            return list(self._rules_db)

    def add_rule(
        self,
        name: str,
        pattern: dict[str, str],
        validity: str = "valid",
    ) -> dict[str, Any]:
        """添加推理规则。"""
        with self._lock:
            rule = {
                "id": f"rule_custom_{uuid.uuid4().hex[:8]}",
                "name": name,
                "pattern": pattern,
                "validity": validity,
            }
            self._rules_db.append(rule)
            return rule

    # ===== 统计 =====

    def compute_statistics(self) -> dict[str, Any]:
        """计算推理器统计指标。"""
        with self._lock:
            total = len(self._chains)
            if total == 0:
                return {"total_chains": 0}
            type_counts: dict[str, int] = defaultdict(int)
            validity_counts: dict[str, int] = defaultdict(int)
            fallacy_total = 0
            confidence_sum = 0.0
            for chain in self._chains.values():
                type_counts[chain.reasoning_type] += 1
                validity_counts[chain.validity] += 1
                fallacy_total += len(chain.fallacies)
                confidence_sum += chain.confidence
            return {
                "total_chains": total,
                "type_counts": dict(type_counts),
                "validity_counts": dict(validity_counts),
                "avg_confidence": round(confidence_sum / total, 4),
                "total_fallacies": fallacy_total,
                "avg_fallacies_per_chain": round(fallacy_total / total, 2),
                "fallacy_db_size": len(self._fallacies_db),
                "rule_db_size": len(self._rules_db),
            }

    def summary(self) -> dict[str, Any]:
        """返回推理器汇总信息。"""
        with self._lock:
            return {
                "chain_count": len(self._chains),
                "fallacy_count": len(self._fallacies_db),
                "rule_count": len(self._rules_db),
                "supported_types": list(REASONING_TYPES.keys()),
            }

    # ===== 导出 =====

    def export_chain_markdown(self, chain_id: str) -> str:
        """导出推理链为 Markdown。"""
        with self._lock:
            chain = self._chains.get(chain_id)
            if not chain:
                return ""
            lines: list[str] = []
            lines.append(f"# 推理链：{chain.id}")
            lines.append("")
            lines.append(f"- **类型**：{REASONING_TYPES.get(chain.reasoning_type, chain.reasoning_type)}")
            lines.append(f"- **有效性**：{VALIDITY_LEVELS.get(chain.validity, chain.validity)}")
            lines.append(f"- **置信度**：{chain.confidence:.0%}")
            lines.append(f"- **创建时间**：{chain.created_at}")
            lines.append("")
            lines.append("## 推理步骤")
            lines.append("")
            for i, step in enumerate(chain.steps, 1):
                prefix = {"premise": "前提", "inference": "推理", "conclusion": "结论"}.get(
                    step.step_type, step.step_type
                )
                lines.append(f"{i}. **[{prefix}]** {step.content}")
                if step.rule:
                    lines.append(f"   - 规则：{step.rule}")
                lines.append(f"   - 置信度：{step.confidence:.0%}")
            lines.append("")
            if chain.conclusion:
                lines.append(f"## 结论")
                lines.append("")
                lines.append(f"> {chain.conclusion}")
                lines.append("")
            if chain.fallacies:
                lines.append("## 检测到的谬误")
                lines.append("")
                for f in chain.fallacies:
                    lines.append(f"- **{f.name}**（{f.severity}）：{f.description}")
                lines.append("")
            return "\n".join(lines)

    def export_chain_dict(self, chain_id: str) -> dict[str, Any]:
        """导出推理链为字典。"""
        with self._lock:
            chain = self._chains.get(chain_id)
            if not chain:
                return {}
            return chain.to_dict()
