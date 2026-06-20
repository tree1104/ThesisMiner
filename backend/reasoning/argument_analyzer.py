"""论证分析器模块

提供完整的学术论证分析能力，包括：
    - 论点识别、论据提取、论证结构分析
    - 论证强度评估、论证有效性检查、反驳识别
    - 论证图构建、论证链追踪、薄弱环节识别
    - 论证改进建议、论证模板推荐
    - 完整的分析规则、评估算法

设计原则：
    1. 零外部依赖：仅使用 Python 标准库
    2. 线程安全：所有公共方法通过 RLock 保护
    3. 可持久化：基于 dataclass，支持序列化
    4. 规则可扩展：分析规则、模板均可动态扩展

核心数据结构：
    - Argument: 论证（含论点、论据、结构）
    - ArgumentStructure: 论证结构（树形）
    - ArgumentStrength: 论证强度评估
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

# 论证类型
ARGUMENT_TYPES = {
    "deductive": "演绎论证",
    "inductive": "归纳论证",
    "abductive": "溯因论证",
    "analogical": "类比论证",
    "causal": "因果论证",
    "empirical": "经验论证",
    "theoretical": "理论论证",
    "statistical": "统计论证",
}

# 论点类型
CLAIM_TYPES = {
    "fact": "事实论点",
    "value": "价值论点",
    "policy": "政策论点",
    "definition": "定义论点",
    "cause": "因果论点",
    "comparison": "比较论点",
    "evaluation": "评价论点",
}

# 论据类型
EVIDENCE_TYPES = {
    "empirical": "经验证据",
    "statistical": "统计证据",
    "testimonial": "证言证据",
    "anecdotal": "轶事证据",
    "documentary": "文献证据",
    "experimental": "实验证据",
    "observational": "观察证据",
    "logical": "逻辑证据",
    "authority": "权威证据",
}

# 论证结构类型
STRUCTURE_TYPES = {
    "simple": "简单结构（单一论据支持论点）",
    "linked": "链接结构（多论据共同支持）",
    "convergent": "汇聚结构（多论据独立支持）",
    "serial": "串行结构（子论证链）",
    "divergent": "发散结构（一论据支持多论点）",
    "complex": "复合结构",
}

# 论证强度等级
STRENGTH_LEVELS = {
    "very_strong": "很强",
    "strong": "强",
    "moderate": "中等",
    "weak": "弱",
    "very_weak": "很弱",
}

# 强度评分阈值
STRENGTH_THRESHOLDS = {
    "very_strong": 0.85,
    "strong": 0.7,
    "moderate": 0.5,
    "weak": 0.3,
    "very_weak": 0.0,
}

# 论证有效性
VALIDITY_STATUS = {
    "valid": "有效",
    "invalid": "无效",
    "sound": "可靠（有效且前提为真）",
    "unsound": "不可靠",
    "cogent": "可信（归纳强且前提为真）",
    "uncogent": "不可信",
}

# 反驳类型
REFUTATION_TYPES = {
    "direct": "直接反驳（直接否定论点）",
    "counter_evidence": "反例反驳（提供反例）",
    "undercut": "削弱反驳（攻击论据与论点的联系）",
    "rebuttal": "反驳论据（攻击论据本身）",
    "counter_argument": "反论证（提出对立论证）",
    "reductio": "归谬法（推出荒谬结论）",
}

# 论点指示词（中文）
CLAIM_INDICATORS = [
    "因此", "所以", "由此可见", "可以得出", "证明", "表明",
    "说明", "意味着", "支持", "认为", "主张", "观点是",
    "结论是", "由此可见", "综上",
]

# 论据指示词（中文）
EVIDENCE_INDICATORS = [
    "因为", "由于", "基于", "鉴于", "根据", "依据",
    "数据显示", "研究表明", "调查发现", "实验表明",
    "例如", "比如", "如", "实例", "案例",
    "据统计", "数据显示", "文献指出", "学者认为",
]

# 反驳指示词
REFUTATION_INDICATORS = [
    "然而", "但是", "不过", "尽管如此", "相反",
    "反对意见", "反驳", "质疑", "问题在于",
    "并非如此", "未必", "不一定", "存疑",
]

# 论证模板库
ARGUMENT_TEMPLATES = [
    {
        "id": "template_toulmin",
        "name": "图尔敏模型",
        "description": "包含主张、根据、担保、支持、反驳、限定",
        "components": ["claim", "grounds", "warrant", "backing", "rebuttal", "qualifier"],
        "applicable_types": ["empirical", "policy"],
    },
    {
        "id": "template_aristotelian",
        "name": "亚里士多德三段论",
        "description": "大前提、小前提、结论",
        "components": ["major_premise", "minor_premise", "conclusion"],
        "applicable_types": ["deductive"],
    },
    {
        "id": "template_causal",
        "name": "因果论证模板",
        "description": "原因、机制、证据、结论",
        "components": ["cause", "mechanism", "evidence", "effect"],
        "applicable_types": ["causal"],
    },
    {
        "id": "template_comparative",
        "name": "比较论证模板",
        "description": "比较对象、比较维度、相似性、结论",
        "components": ["subjects", "criteria", "similarities", "conclusion"],
        "applicable_types": ["analogical", "comparison"],
    },
    {
        "id": "template_statistical",
        "name": "统计论证模板",
        "description": "数据来源、样本、统计量、显著性、结论",
        "components": ["data_source", "sample", "statistic", "significance", "conclusion"],
        "applicable_types": ["statistical", "empirical"],
    },
    {
        "id": "template_literature",
        "name": "文献综述论证",
        "description": "文献检索、筛选、分析、综合、结论",
        "components": ["search", "screening", "analysis", "synthesis", "conclusion"],
        "applicable_types": ["theoretical", "empirical"],
    },
]

# 评估维度
EVALUATION_DIMENSIONS = {
    "relevance": "相关性（论据与论点相关）",
    "sufficiency": "充分性（论据足够支持论点）",
    "credibility": "可信性（论据来源可靠）",
    "consistency": "一致性（论据之间不矛盾）",
    "clarity": "清晰性（论点表述明确）",
    "completeness": "完整性（考虑了反面观点）",
}


# ===== 数据结构 =====


@dataclass
class Claim:
    """论点数据结构。

    Attributes:
        id: 论点 ID。
        content: 论点内容。
        claim_type: 论点类型。
        is_main: 是否为主论点。
        qualifier: 限定词（如「可能」「必然」）。
        confidence: 置信度。
    """

    id: str = ""
    content: str = ""
    claim_type: str = "fact"
    is_main: bool = False
    qualifier: str = ""
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return asdict(self)


@dataclass
class Evidence:
    """论据数据结构。

    Attributes:
        id: 论据 ID。
        content: 论据内容。
        evidence_type: 论据类型。
        source: 来源。
        credibility: 可信度（0-1）。
        supports: 支持的论点 ID。
        weight: 权重。
    """

    id: str = ""
    content: str = ""
    evidence_type: str = "empirical"
    source: str = ""
    credibility: float = 0.5
    supports: str = ""
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return asdict(self)


@dataclass
class Refutation:
    """反驳数据结构。

    Attributes:
        id: 反驳 ID。
        content: 反驳内容。
        refutation_type: 反驳类型。
        target: 被反驳的论点/论据 ID。
        strength: 反驳强度（0-1）。
    """

    id: str = ""
    content: str = ""
    refutation_type: str = "direct"
    target: str = ""
    strength: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return asdict(self)


@dataclass
class ArgumentStructure:
    """论证结构数据结构。

    Attributes:
        structure_type: 结构类型。
        nodes: 节点列表（论点与论据）。
        edges: 边列表（支持关系）。
        depth: 结构深度。
        width: 结构宽度。
    """

    structure_type: str = "simple"
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    depth: int = 1
    width: int = 1

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return asdict(self)


@dataclass
class ArgumentStrength:
    """论证强度评估数据结构。

    Attributes:
        overall_score: 总体评分（0-1）。
        level: 强度等级。
        dimensions: 各维度评分。
        weaknesses: 薄弱环节列表。
        recommendations: 改进建议列表。
    """

    overall_score: float = 0.0
    level: str = "moderate"
    dimensions: dict[str, float] = field(default_factory=dict)
    weaknesses: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return asdict(self)


@dataclass
class Argument:
    """论证数据结构。

    Attributes:
        id: 论证 ID。
        title: 论证标题。
        argument_type: 论证类型。
        main_claim: 主论点。
        sub_claims: 子论点列表。
        evidence: 论据列表。
        refutations: 反驳列表。
        structure: 论证结构。
        strength: 强度评估。
        created_at: 创建时间。
        updated_at: 更新时间。
        metadata: 扩展元数据。
    """

    id: str = ""
    title: str = ""
    argument_type: str = "empirical"
    main_claim: Optional[Claim] = None
    sub_claims: list[Claim] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    refutations: list[Refutation] = field(default_factory=list)
    structure: Optional[ArgumentStructure] = None
    strength: Optional[ArgumentStrength] = None
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "id": self.id,
            "title": self.title,
            "argument_type": self.argument_type,
            "argument_type_name": ARGUMENT_TYPES.get(self.argument_type, self.argument_type),
            "main_claim": self.main_claim.to_dict() if self.main_claim else None,
            "sub_claims": [c.to_dict() for c in self.sub_claims],
            "evidence": [e.to_dict() for e in self.evidence],
            "refutations": [r.to_dict() for r in self.refutations],
            "structure": self.structure.to_dict() if self.structure else None,
            "strength": self.strength.to_dict() if self.strength else None,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }


# ===== 主类实现 =====


class ArgumentAnalyzer:
    """论证分析器主类。

    提供论点识别、论据提取、论证结构分析、论证强度评估、论证有效性检查、
    反驳识别、论证图构建、论证链追踪、薄弱环节识别、论证改进建议、
    论证模板推荐等能力。

    线程安全：所有公共方法通过 RLock 保护。
    """

    def __init__(self):
        """初始化论证分析器。"""
        self._lock = threading.RLock()
        self._arguments: dict[str, Argument] = {}
        self._templates: list[dict[str, Any]] = list(ARGUMENT_TEMPLATES)

    # ===== 论证创建 =====

    def create_argument(
        self,
        title: str,
        argument_type: str = "empirical",
        main_claim: str = "",
        claim_type: str = "fact",
    ) -> Argument:
        """创建论证。

        Args:
            title: 论证标题。
            argument_type: 论证类型。
            main_claim: 主论点内容。
            claim_type: 论点类型。

        Returns:
            创建的 Argument 实例。
        """
        with self._lock:
            if argument_type not in ARGUMENT_TYPES:
                argument_type = "empirical"
            arg_id = f"arg_{uuid.uuid4().hex[:10]}"
            claim = Claim(
                id=f"claim_{uuid.uuid4().hex[:8]}",
                content=main_claim,
                claim_type=claim_type,
                is_main=True,
            ) if main_claim else None
            argument = Argument(
                id=arg_id,
                title=title,
                argument_type=argument_type,
                main_claim=claim,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
            )
            self._arguments[arg_id] = argument
            return argument

    def add_sub_claim(
        self,
        argument_id: str,
        content: str,
        claim_type: str = "fact",
        qualifier: str = "",
    ) -> Optional[Claim]:
        """添加子论点。"""
        with self._lock:
            arg = self._arguments.get(argument_id)
            if not arg:
                return None
            claim = Claim(
                id=f"claim_{uuid.uuid4().hex[:8]}",
                content=content,
                claim_type=claim_type,
                is_main=False,
                qualifier=qualifier,
            )
            arg.sub_claims.append(claim)
            arg.updated_at = datetime.now().isoformat()
            return claim

    def add_evidence(
        self,
        argument_id: str,
        content: str,
        evidence_type: str = "empirical",
        source: str = "",
        credibility: float = 0.5,
        supports: str = "",
        weight: float = 1.0,
    ) -> Optional[Evidence]:
        """添加论据。"""
        with self._lock:
            arg = self._arguments.get(argument_id)
            if not arg:
                return None
            if evidence_type not in EVIDENCE_TYPES:
                evidence_type = "empirical"
            ev = Evidence(
                id=f"ev_{uuid.uuid4().hex[:8]}",
                content=content,
                evidence_type=evidence_type,
                source=source,
                credibility=max(0.0, min(1.0, credibility)),
                supports=supports,
                weight=weight,
            )
            arg.evidence.append(ev)
            arg.updated_at = datetime.now().isoformat()
            return ev

    def add_refutation(
        self,
        argument_id: str,
        content: str,
        refutation_type: str = "direct",
        target: str = "",
        strength: float = 0.5,
    ) -> Optional[Refutation]:
        """添加反驳。"""
        with self._lock:
            arg = self._arguments.get(argument_id)
            if not arg:
                return None
            if refutation_type not in REFUTATION_TYPES:
                refutation_type = "direct"
            ref = Refutation(
                id=f"ref_{uuid.uuid4().hex[:8]}",
                content=content,
                refutation_type=refutation_type,
                target=target,
                strength=max(0.0, min(1.0, strength)),
            )
            arg.refutations.append(ref)
            arg.updated_at = datetime.now().isoformat()
            return ref

    # ===== 文本分析 =====

    def analyze_text(self, text: str) -> dict[str, Any]:
        """分析文本中的论证结构。

        Args:
            text: 待分析文本。

        Returns:
            分析结果字典（含识别的论点、论据、反驳）。
        """
        with self._lock:
            # 分句
            sentences = self._split_sentences(text)
            # 识别论点
            claims = self._identify_claims(sentences)
            # 识别论据
            evidence = self._identify_evidence(sentences)
            # 识别反驳
            refutations = self._identify_refutations(sentences)
            # 推断论证类型
            arg_type = self._infer_argument_type(text)
            # 推断结构类型
            structure_type = self._infer_structure_type(claims, evidence)
            return {
                "sentence_count": len(sentences),
                "claims": [c.to_dict() for c in claims],
                "evidence": [e.to_dict() for e in evidence],
                "refutations": [r.to_dict() for r in refutations],
                "inferred_type": arg_type,
                "inferred_type_name": ARGUMENT_TYPES.get(arg_type, arg_type),
                "inferred_structure": structure_type,
                "inferred_structure_name": STRUCTURE_TYPES.get(structure_type, structure_type),
                "claim_count": len(claims),
                "evidence_count": len(evidence),
                "refutation_count": len(refutations),
            }

    def _split_sentences(self, text: str) -> list[str]:
        """分句。

        Args:
            text: 原始文本。

        Returns:
            句子列表。
        """
        # 按中英文句号、问号、感叹号、分号分句
        sentences = re.split(r"[。！？；!?;]\s*", text)
        return [s.strip() for s in sentences if s.strip()]

    def _identify_claims(self, sentences: list[str]) -> list[Claim]:
        """识别论点。

        Args:
            sentences: 句子列表。

        Returns:
            论点列表。
        """
        claims: list[Claim] = []
        for sent in sentences:
            for indicator in CLAIM_INDICATORS:
                if indicator in sent:
                    # 提取指示词后的内容作为论点
                    idx = sent.find(indicator)
                    content = sent[idx + len(indicator):].strip()
                    if not content:
                        content = sent
                    # 推断论点类型
                    claim_type = self._infer_claim_type(content)
                    claims.append(Claim(
                        id=f"claim_{uuid.uuid4().hex[:8]}",
                        content=content,
                        claim_type=claim_type,
                        is_main=False,
                    ))
                    break
        return claims

    def _identify_evidence(self, sentences: list[str]) -> list[Evidence]:
        """识别论据。"""
        evidence: list[Evidence] = []
        for sent in sentences:
            for indicator in EVIDENCE_INDICATORS:
                if indicator in sent:
                    ev_type = self._infer_evidence_type(sent, indicator)
                    credibility = self._assess_evidence_credibility(sent, ev_type)
                    evidence.append(Evidence(
                        id=f"ev_{uuid.uuid4().hex[:8]}",
                        content=sent,
                        evidence_type=ev_type,
                        credibility=credibility,
                    ))
                    break
        return evidence

    def _identify_refutations(self, sentences: list[str]) -> list[Refutation]:
        """识别反驳。"""
        refutations: list[Refutation] = []
        for sent in sentences:
            for indicator in REFUTATION_INDICATORS:
                if indicator in sent:
                    ref_type = self._infer_refutation_type(sent)
                    strength = self._assess_refutation_strength(sent)
                    refutations.append(Refutation(
                        id=f"ref_{uuid.uuid4().hex[:8]}",
                        content=sent,
                        refutation_type=ref_type,
                        strength=strength,
                    ))
                    break
        return refutations

    def _infer_claim_type(self, content: str) -> str:
        """推断论点类型。"""
        if any(w in content for w in ["应该", "必须", "需要", "建议", "应当"]):
            return "policy"
        if any(w in content for w in ["好", "坏", "优", "劣", "值得", "有效"]):
            return "value"
        if any(w in content for w in ["导致", "引起", "因为", "结果"]):
            return "cause"
        if any(w in content for w in ["是", "属于", "定义为"]):
            return "definition"
        if any(w in content for w in ["比", "更", "相比", "优于"]):
            return "comparison"
        return "fact"

    def _infer_evidence_type(self, sent: str, indicator: str) -> str:
        """推断论据类型。"""
        if "数据" in sent or "统计" in sent or "%" in sent:
            return "statistical"
        if "实验" in sent:
            return "experimental"
        if "观察" in sent or "调查" in sent:
            return "observational"
        if "研究" in sent or "文献" in sent or "论文" in sent:
            return "documentary"
        if "专家" in sent or "学者" in sent or "教授" in sent:
            return "authority"
        if "例如" in indicator or "比如" in indicator:
            return "anecdotal"
        return "empirical"

    def _infer_refutation_type(self, sent: str) -> str:
        """推断反驳类型。"""
        if "并非" in sent or "不成立" in sent:
            return "direct"
        if "反例" in sent or "但是" in sent:
            return "counter_evidence"
        if "未必" in sent or "不一定" in sent:
            return "undercut"
        return "direct"

    def _assess_evidence_credibility(self, sent: str, ev_type: str) -> float:
        """评估论据可信度。"""
        base = {
            "statistical": 0.8,
            "experimental": 0.85,
            "observational": 0.7,
            "documentary": 0.75,
            "authority": 0.65,
            "anecdotal": 0.3,
            "empirical": 0.6,
            "testimonial": 0.5,
            "logical": 0.7,
        }.get(ev_type, 0.5)
        # 检测是否有具体来源
        if re.search(r"\d{4}年|\d+%|p\s*[<>=]\s*0\.\d+", sent):
            base = min(1.0, base + 0.1)
        return base

    def _assess_refutation_strength(self, sent: str) -> float:
        """评估反驳强度。"""
        if "并非" in sent or "不成立" in sent or "错误" in sent:
            return 0.8
        if "未必" in sent or "不一定" in sent:
            return 0.5
        return 0.6

    def _infer_argument_type(self, text: str) -> str:
        """推断论证类型。"""
        if any(w in text for w in ["所有", "凡是", "必然", "如果...则"]):
            return "deductive"
        if any(w in text for w in ["样本", "调查", "观察", "大多数"]):
            return "inductive"
        if any(w in text for w in ["导致", "因果", "因为", "结果"]):
            return "causal"
        if any(w in text for w in ["类似", "类比", "相似", "如同"]):
            return "analogical"
        if any(w in text for w in ["数据", "统计", "显著", "p<"]):
            return "statistical"
        if any(w in text for w in ["理论", "框架", "模型"]):
            return "theoretical"
        return "empirical"

    def _infer_structure_type(
        self, claims: list[Claim], evidence: list[Evidence]
    ) -> str:
        """推断论证结构类型。"""
        if len(evidence) == 0:
            return "simple"
        if len(evidence) == 1:
            return "simple"
        # 检查是否多个论据支持同一论点
        if len(claims) <= 1 and len(evidence) > 1:
            return "convergent"
        if len(claims) > 1 and len(evidence) > 1:
            return "linked"
        return "simple"

    # ===== 结构分析 =====

    def analyze_structure(self, argument_id: str) -> Optional[ArgumentStructure]:
        """分析论证结构。

        Args:
            argument_id: 论证 ID。

        Returns:
            论证结构实例。
        """
        with self._lock:
            arg = self._arguments.get(argument_id)
            if not arg:
                return None
            nodes: list[dict[str, Any]] = []
            edges: list[dict[str, Any]] = []
            # 添加主论点节点
            if arg.main_claim:
                nodes.append({
                    "id": arg.main_claim.id,
                    "label": arg.main_claim.content[:50],
                    "type": "claim",
                    "is_main": True,
                    "color": "#dc3545",
                })
            # 添加子论点节点
            for c in arg.sub_claims:
                nodes.append({
                    "id": c.id,
                    "label": c.content[:50],
                    "type": "sub_claim",
                    "color": "#fd7e14",
                })
            # 添加论据节点
            for e in arg.evidence:
                nodes.append({
                    "id": e.id,
                    "label": e.content[:50],
                    "type": "evidence",
                    "evidence_type": e.evidence_type,
                    "credibility": e.credibility,
                    "color": "#0d6efd",
                })
            # 添加反驳节点
            for r in arg.refutations:
                nodes.append({
                    "id": r.id,
                    "label": r.content[:50],
                    "type": "refutation",
                    "refutation_type": r.refutation_type,
                    "color": "#6c757d",
                })
            # 构建边
            # 论据支持论点
            main_id = arg.main_claim.id if arg.main_claim else ""
            for e in arg.evidence:
                target = e.supports or main_id
                if target:
                    edges.append({
                        "source": e.id,
                        "target": target,
                        "relation": "supports",
                        "weight": e.weight,
                    })
            # 子论点支持主论点
            for c in arg.sub_claims:
                if main_id:
                    edges.append({
                        "source": c.id,
                        "target": main_id,
                        "relation": "supports",
                    })
            # 反驳指向目标
            for r in arg.refutations:
                target = r.target or main_id
                if target:
                    edges.append({
                        "source": r.id,
                        "target": target,
                        "relation": "refutes",
                        "weight": r.strength,
                    })
            # 推断结构类型
            structure_type = self._infer_structure_type(arg.sub_claims, arg.evidence)
            # 计算深度与宽度
            depth = self._compute_structure_depth(nodes, edges)
            width = self._compute_structure_width(nodes, edges)
            structure = ArgumentStructure(
                structure_type=structure_type,
                nodes=nodes,
                edges=edges,
                depth=depth,
                width=width,
            )
            arg.structure = structure
            return structure

    def _compute_structure_depth(
        self, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
    ) -> int:
        """计算结构深度（最长路径）。"""
        if not nodes or not edges:
            return 1
        # 构建邻接表
        adj: dict[str, list[str]] = defaultdict(list)
        for e in edges:
            adj[e["source"]].append(e["target"])
        # 找到根节点（无入边）
        all_targets = {e["target"] for e in edges}
        roots = [n["id"] for n in nodes if n["id"] not in all_targets]
        if not roots:
            return 1
        # BFS 求最大深度
        max_depth = 1
        for root in roots:
            queue: deque[tuple[str, int]] = deque([(root, 1)])
            visited: set[str] = {root}
            while queue:
                curr, d = queue.popleft()
                max_depth = max(max_depth, d)
                for nxt in adj.get(curr, []):
                    if nxt not in visited:
                        visited.add(nxt)
                        queue.append((nxt, d + 1))
        return max_depth

    def _compute_structure_width(
        self, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
    ) -> int:
        """计算结构宽度（最大层节点数）。"""
        if not nodes:
            return 0
        # 按类型统计
        type_counts: dict[str, int] = defaultdict(int)
        for n in nodes:
            type_counts[n.get("type", "unknown")] += 1
        return max(type_counts.values()) if type_counts else 1

    # ===== 强度评估 =====

    def evaluate_strength(self, argument_id: str) -> Optional[ArgumentStrength]:
        """评估论证强度。

        Args:
            argument_id: 论证 ID。

        Returns:
            强度评估实例。
        """
        with self._lock:
            arg = self._arguments.get(argument_id)
            if not arg:
                return None
            dimensions: dict[str, float] = {}
            weaknesses: list[str] = []
            recommendations: list[str] = []

            # 1. 相关性
            relevance = self._evaluate_relevance(arg)
            dimensions["relevance"] = relevance
            if relevance < 0.5:
                weaknesses.append("论据与论点相关性不足")
                recommendations.append("增加与论点直接相关的论据")

            # 2. 充分性
            sufficiency = self._evaluate_sufficiency(arg)
            dimensions["sufficiency"] = sufficiency
            if sufficiency < 0.5:
                weaknesses.append("论据数量或质量不足以支持论点")
                recommendations.append("补充更多高质量论据")

            # 3. 可信性
            credibility = self._evaluate_credibility(arg)
            dimensions["credibility"] = credibility
            if credibility < 0.5:
                weaknesses.append("论据来源可信度偏低")
                recommendations.append("引用更权威的来源（同行评审文献、官方数据）")

            # 4. 一致性
            consistency = self._evaluate_consistency(arg)
            dimensions["consistency"] = consistency
            if consistency < 0.5:
                weaknesses.append("论据之间存在矛盾")
                recommendations.append("解决论据间的矛盾或剔除冲突论据")

            # 5. 清晰性
            clarity = self._evaluate_clarity(arg)
            dimensions["clarity"] = clarity
            if clarity < 0.5:
                weaknesses.append("论点表述不够清晰")
                recommendations.append("明确论点，避免歧义")

            # 6. 完整性
            completeness = self._evaluate_completeness(arg)
            dimensions["completeness"] = completeness
            if completeness < 0.5:
                weaknesses.append("未充分考虑反面观点")
                recommendations.append("纳入并回应可能的反驳")

            # 总体评分（加权平均）
            weights = {
                "relevance": 0.2,
                "sufficiency": 0.2,
                "credibility": 0.2,
                "consistency": 0.15,
                "clarity": 0.1,
                "completeness": 0.15,
            }
            overall = sum(dimensions[d] * weights[d] for d in dimensions)
            # 考虑反驳的削弱
            if arg.refutations:
                ref_impact = sum(r.strength for r in arg.refutations) / len(arg.refutations)
                overall *= (1 - ref_impact * 0.3)
            overall = max(0.0, min(1.0, overall))
            # 确定等级
            level = "very_weak"
            for lv, threshold in STRENGTH_THRESHOLDS.items():
                if overall >= threshold:
                    level = lv
                    break
            strength = ArgumentStrength(
                overall_score=round(overall, 4),
                level=level,
                dimensions={k: round(v, 4) for k, v in dimensions.items()},
                weaknesses=weaknesses,
                recommendations=recommendations,
            )
            arg.strength = strength
            return strength

    def _evaluate_relevance(self, arg: Argument) -> float:
        """评估相关性。"""
        if not arg.evidence or not arg.main_claim:
            return 0.3
        claim_text = arg.main_claim.content
        # 简化：检测论据与论点的关键词重叠
        claim_words = set(self._extract_keywords(claim_text))
        if not claim_words:
            return 0.5
        scores = []
        for ev in arg.evidence:
            ev_words = set(self._extract_keywords(ev.content))
            if not ev_words:
                scores.append(0.3)
                continue
            overlap = len(claim_words & ev_words) / len(claim_words)
            scores.append(overlap)
        return sum(scores) / len(scores) if scores else 0.3

    def _evaluate_sufficiency(self, arg: Argument) -> float:
        """评估充分性。"""
        ev_count = len(arg.evidence)
        if ev_count == 0:
            return 0.1
        if ev_count >= 5:
            base = 0.9
        elif ev_count >= 3:
            base = 0.7
        elif ev_count >= 1:
            base = 0.5
        else:
            base = 0.2
        # 考虑论据类型多样性
        types = {e.evidence_type for e in arg.evidence}
        diversity_bonus = min(0.1, len(types) * 0.03)
        return min(1.0, base + diversity_bonus)

    def _evaluate_credibility(self, arg: Argument) -> float:
        """评估可信性。"""
        if not arg.evidence:
            return 0.3
        scores = [e.credibility for e in arg.evidence]
        return sum(scores) / len(scores)

    def _evaluate_consistency(self, arg: Argument) -> float:
        """评估一致性。"""
        if len(arg.evidence) < 2:
            return 1.0
        # 简化：检测论据间关键词冲突（出现反义词）
        # 这里用简化评估
        contradiction_words = ["不", "非", "相反", "然而", "但是"]
        contradiction_count = 0
        for ev in arg.evidence:
            for w in contradiction_words:
                if w in ev.content:
                    contradiction_count += 1
                    break
        if contradiction_count == 0:
            return 0.9
        return max(0.3, 1.0 - contradiction_count * 0.2)

    def _evaluate_clarity(self, arg: Argument) -> float:
        """评估清晰性。"""
        if not arg.main_claim:
            return 0.3
        content = arg.main_claim.content
        # 简化：检测长度与限定词
        if len(content) < 10:
            return 0.4
        if len(content) > 200:
            return 0.6
        # 有限定词通常更严谨
        qualifiers = ["可能", "或许", "在...条件下", "总体上", "一般来说"]
        has_qualifier = any(q in content for q in qualifiers)
        return 0.9 if has_qualifier else 0.7

    def _evaluate_completeness(self, arg: Argument) -> float:
        """评估完整性。"""
        if not arg.refutations:
            return 0.4  # 没有考虑反驳
        # 有反驳且已回应
        return min(0.9, 0.5 + len(arg.refutations) * 0.1)

    def _extract_keywords(self, text: str) -> list[str]:
        """提取关键词（简化版）。"""
        # 移除中英文标点
        punctuation = "，。、；：！？""''（）()[]【】《》〈〉「」『』.,;:!?'\""
        cleaned = text
        for ch in punctuation:
            cleaned = cleaned.replace(ch, " ")
        words = cleaned.split()
        # 过滤短词
        return [w for w in words if len(w) >= 2]

    # ===== 有效性检查 =====

    def check_validity(self, argument_id: str) -> dict[str, Any]:
        """检查论证有效性。

        Args:
            argument_id: 论证 ID。

        Returns:
            有效性检查结果。
        """
        with self._lock:
            arg = self._arguments.get(argument_id)
            if not arg:
                return {}
            issues: list[str] = []
            # 检查主论点
            if not arg.main_claim:
                issues.append("缺少主论点")
            # 检查论据
            if not arg.evidence:
                issues.append("缺少论据")
            # 检查论据是否支持论点
            if arg.main_claim and arg.evidence:
                unsupported = [
                    e for e in arg.evidence
                    if not e.supports or e.supports == ""
                ]
                if unsupported:
                    issues.append(f"有 {len(unsupported)} 个论据未明确支持对象")
            # 检查循环论证
            if self._has_circular_reasoning(arg):
                issues.append("存在循环论证")
            # 检查论据可信度
            low_credibility = [e for e in arg.evidence if e.credibility < 0.3]
            if low_credibility:
                issues.append(f"有 {len(low_credibility)} 个论据可信度偏低")
            # 确定有效性
            if arg.argument_type == "deductive":
                validity = "valid" if len(issues) == 0 else "invalid"
            else:
                validity = "cogent" if len(issues) == 0 else "uncogent"
            return {
                "argument_id": argument_id,
                "validity": validity,
                "validity_name": VALIDITY_STATUS.get(validity, validity),
                "is_valid": len(issues) == 0,
                "issue_count": len(issues),
                "issues": issues,
                "evidence_count": len(arg.evidence),
                "refutation_count": len(arg.refutations),
            }

    def _has_circular_reasoning(self, arg: Argument) -> bool:
        """检测循环论证。"""
        if not arg.main_claim or not arg.evidence:
            return False
        claim_text = arg.main_claim.content
        for ev in arg.evidence:
            # 简化：论据内容与论点高度相似
            if self._text_similarity(claim_text, ev.content) > 0.8:
                return True
        return False

    def _text_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度（基于 Jaccard）。"""
        words1 = set(self._extract_keywords(text1))
        words2 = set(self._extract_keywords(text2))
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union)

    # ===== 薄弱环节识别 =====

    def identify_weak_points(self, argument_id: str) -> list[dict[str, Any]]:
        """识别论证薄弱环节。

        Args:
            argument_id: 论证 ID。

        Returns:
            薄弱环节列表。
        """
        with self._lock:
            arg = self._arguments.get(argument_id)
            if not arg:
                return []
            weak_points: list[dict[str, Any]] = []
            # 1. 低可信度论据
            for ev in arg.evidence:
                if ev.credibility < 0.5:
                    weak_points.append({
                        "type": "evidence",
                        "id": ev.id,
                        "content": ev.content[:80],
                        "issue": f"论据可信度偏低（{ev.credibility:.0%}）",
                        "severity": "high" if ev.credibility < 0.3 else "medium",
                        "suggestion": "寻找更可靠的来源或补充佐证",
                    })
            # 2. 未支持论点
            for c in arg.sub_claims:
                supporting = [e for e in arg.evidence if e.supports == c.id]
                if not supporting:
                    weak_points.append({
                        "type": "claim",
                        "id": c.id,
                        "content": c.content[:80],
                        "issue": "子论点缺少论据支持",
                        "severity": "high",
                        "suggestion": "为该子论点补充论据",
                    })
            # 3. 强反驳未回应
            for r in arg.refutations:
                if r.strength > 0.7:
                    weak_points.append({
                        "type": "refutation",
                        "id": r.id,
                        "content": r.content[:80],
                        "issue": f"存在强反驳（强度 {r.strength:.0%}）",
                        "severity": "critical",
                        "suggestion": "回应该反驳或调整论点",
                    })
            # 4. 主论点无支持
            if arg.main_claim:
                supporting = [
                    e for e in arg.evidence
                    if not e.supports or e.supports == arg.main_claim.id
                ]
                if not supporting:
                    weak_points.append({
                        "type": "main_claim",
                        "id": arg.main_claim.id,
                        "content": arg.main_claim.content[:80],
                        "issue": "主论点缺少直接论据",
                        "severity": "critical",
                        "suggestion": "补充支持主论点的核心论据",
                    })
            return weak_points

    # ===== 改进建议 =====

    def generate_improvement_suggestions(
        self, argument_id: str
    ) -> list[dict[str, str]]:
        """生成论证改进建议。

        Args:
            argument_id: 论证 ID。

        Returns:
            建议列表。
        """
        with self._lock:
            arg = self._arguments.get(argument_id)
            if not arg:
                return []
            suggestions: list[dict[str, str]] = []
            # 基于强度评估
            if not arg.strength:
                self.evaluate_strength(argument_id)
            if arg.strength:
                for rec in arg.strength.recommendations:
                    suggestions.append({
                        "type": "strength",
                        "priority": "high",
                        "suggestion": rec,
                    })
            # 基于薄弱环节
            weak_points = self.identify_weak_points(argument_id)
            for wp in weak_points:
                suggestions.append({
                    "type": wp["type"],
                    "priority": wp["severity"],
                    "suggestion": f"{wp['issue']}：{wp['suggestion']}",
                })
            # 基于论证类型
            if arg.argument_type == "deductive" and len(arg.evidence) < 2:
                suggestions.append({
                    "type": "structure",
                    "priority": "high",
                    "suggestion": "演绎论证需要至少两个前提（大前提与小前提）",
                })
            if arg.argument_type == "inductive" and len(arg.evidence) < 3:
                suggestions.append({
                    "type": "structure",
                    "priority": "medium",
                    "suggestion": "归纳论证建议提供更多案例以增强说服力",
                })
            if not arg.refutations:
                suggestions.append({
                    "type": "completeness",
                    "priority": "medium",
                    "suggestion": "考虑可能的反驳并预先回应，增强论证完整性",
                })
            if not suggestions:
                suggestions.append({
                    "type": "positive",
                    "priority": "low",
                    "suggestion": "论证结构完整，建议进一步打磨语言表达",
                })
            return suggestions

    # ===== 模板推荐 =====

    def recommend_templates(
        self, argument_type: str = "empirical"
    ) -> list[dict[str, Any]]:
        """推荐论证模板。

        Args:
            argument_type: 论证类型。

        Returns:
            模板列表。
        """
        with self._lock:
            matched = [
                t for t in self._templates
                if argument_type in t.get("applicable_types", [])
            ]
            if not matched:
                return list(self._templates)
            return matched

    def get_template(self, template_id: str) -> Optional[dict[str, Any]]:
        """获取模板详情。"""
        with self._lock:
            for t in self._templates:
                if t["id"] == template_id:
                    return t
            return None

    def add_template(
        self,
        name: str,
        description: str,
        components: list[str],
        applicable_types: list[str],
    ) -> dict[str, Any]:
        """添加自定义模板。"""
        with self._lock:
            template = {
                "id": f"template_custom_{uuid.uuid4().hex[:8]}",
                "name": name,
                "description": description,
                "components": components,
                "applicable_types": applicable_types,
            }
            self._templates.append(template)
            return template

    # ===== 论证图 =====

    def build_argument_graph(self, argument_id: str) -> dict[str, Any]:
        """构建论证图（用于可视化）。

        Args:
            argument_id: 论证 ID。

        Returns:
            图数据字典（节点 + 边）。
        """
        with self._lock:
            arg = self._arguments.get(argument_id)
            if not arg:
                return {}
            if not arg.structure:
                self.analyze_structure(argument_id)
            if not arg.structure:
                return {}
            return {
                "argument_id": argument_id,
                "title": arg.title,
                "argument_type": arg.argument_type,
                "argument_type_name": ARGUMENT_TYPES.get(arg.argument_type, arg.argument_type),
                "nodes": arg.structure.nodes,
                "edges": arg.structure.edges,
                "structure_type": arg.structure.structure_type,
                "structure_type_name": STRUCTURE_TYPES.get(
                    arg.structure.structure_type, arg.structure.structure_type
                ),
                "depth": arg.structure.depth,
                "width": arg.structure.width,
                "strength": arg.strength.to_dict() if arg.strength else None,
            }

    def trace_argument_chain(
        self, argument_id: str, claim_id: str
    ) -> list[dict[str, Any]]:
        """追踪论证链（从论点到支持论据）。

        Args:
            argument_id: 论证 ID。
            claim_id: 起始论点 ID。

        Returns:
            论证链节点列表。
        """
        with self._lock:
            arg = self._arguments.get(argument_id)
            if not arg:
                return []
            chain: list[dict[str, Any]] = []
            visited: set[str] = set()
            # BFS 追踪支持关系
            queue: deque[str] = deque([claim_id])
            visited.add(claim_id)
            while queue:
                curr = queue.popleft()
                # 查找当前节点
                node_info = self._find_node(arg, curr)
                if node_info:
                    chain.append(node_info)
                # 查找支持当前节点的论据
                for ev in arg.evidence:
                    if ev.supports == curr and ev.id not in visited:
                        visited.add(ev.id)
                        queue.append(ev.id)
            return chain

    def _find_node(self, arg: Argument, node_id: str) -> Optional[dict[str, Any]]:
        """查找节点信息。"""
        if arg.main_claim and arg.main_claim.id == node_id:
            return {
                "id": arg.main_claim.id,
                "content": arg.main_claim.content,
                "type": "main_claim",
            }
        for c in arg.sub_claims:
            if c.id == node_id:
                return {
                    "id": c.id,
                    "content": c.content,
                    "type": "sub_claim",
                }
        for e in arg.evidence:
            if e.id == node_id:
                return {
                    "id": e.id,
                    "content": e.content,
                    "type": "evidence",
                    "evidence_type": e.evidence_type,
                    "credibility": e.credibility,
                }
        return None

    # ===== 查询方法 =====

    def get_argument(self, argument_id: str) -> Optional[Argument]:
        """获取论证。"""
        with self._lock:
            return self._arguments.get(argument_id)

    def list_arguments(
        self, argument_type: Optional[str] = None
    ) -> list[Argument]:
        """列出论证。"""
        with self._lock:
            args = list(self._arguments.values())
            if argument_type:
                args = [a for a in args if a.argument_type == argument_type]
            return args

    def delete_argument(self, argument_id: str) -> bool:
        """删除论证。"""
        with self._lock:
            if argument_id in self._arguments:
                del self._arguments[argument_id]
                return True
            return False

    # ===== 统计 =====

    def compute_statistics(self) -> dict[str, Any]:
        """计算分析器统计指标。"""
        with self._lock:
            total = len(self._arguments)
            if total == 0:
                return {"total_arguments": 0}
            type_counts: dict[str, int] = defaultdict(int)
            total_evidence = 0
            total_claims = 0
            total_refutations = 0
            strength_sum = 0.0
            strength_count = 0
            for arg in self._arguments.values():
                type_counts[arg.argument_type] += 1
                total_evidence += len(arg.evidence)
                total_claims += len(arg.sub_claims) + (1 if arg.main_claim else 0)
                total_refutations += len(arg.refutations)
                if arg.strength:
                    strength_sum += arg.strength.overall_score
                    strength_count += 1
            return {
                "total_arguments": total,
                "type_counts": dict(type_counts),
                "total_evidence": total_evidence,
                "total_claims": total_claims,
                "total_refutations": total_refutations,
                "avg_evidence_per_argument": round(total_evidence / total, 2),
                "avg_strength": round(strength_sum / max(strength_count, 1), 4),
                "template_count": len(self._templates),
            }

    def summary(self) -> dict[str, Any]:
        """返回分析器汇总信息。"""
        with self._lock:
            return {
                "argument_count": len(self._arguments),
                "template_count": len(self._templates),
                "supported_types": list(ARGUMENT_TYPES.keys()),
                "supported_structures": list(STRUCTURE_TYPES.keys()),
            }

    # ===== 导出 =====

    def export_argument_markdown(self, argument_id: str) -> str:
        """导出论证为 Markdown。"""
        with self._lock:
            arg = self._arguments.get(argument_id)
            if not arg:
                return ""
            lines: list[str] = []
            lines.append(f"# 论证：{arg.title}")
            lines.append("")
            lines.append(f"- **类型**：{ARGUMENT_TYPES.get(arg.argument_type, arg.argument_type)}")
            lines.append(f"- **创建时间**：{arg.created_at}")
            lines.append("")
            # 主论点
            if arg.main_claim:
                lines.append("## 主论点")
                lines.append("")
                lines.append(f"> {arg.main_claim.content}")
                if arg.main_claim.qualifier:
                    lines.append(f"> 限定：{arg.main_claim.qualifier}")
                lines.append("")
            # 子论点
            if arg.sub_claims:
                lines.append("## 子论点")
                lines.append("")
                for i, c in enumerate(arg.sub_claims, 1):
                    lines.append(f"{i}. {c.content}")
                lines.append("")
            # 论据
            if arg.evidence:
                lines.append("## 论据")
                lines.append("")
                for i, e in enumerate(arg.evidence, 1):
                    lines.append(
                        f"{i}. [{EVIDENCE_TYPES.get(e.evidence_type, e.evidence_type)}] "
                        f"{e.content}"
                    )
                    if e.source:
                        lines.append(f"   - 来源：{e.source}")
                    lines.append(f"   - 可信度：{e.credibility:.0%}")
                lines.append("")
            # 反驳
            if arg.refutations:
                lines.append("## 反驳")
                lines.append("")
                for i, r in enumerate(arg.refutations, 1):
                    lines.append(
                        f"{i}. [{REFUTATION_TYPES.get(r.refutation_type, r.refutation_type)}] "
                        f"{r.content}"
                    )
                    lines.append(f"   - 强度：{r.strength:.0%}")
                lines.append("")
            # 强度评估
            if arg.strength:
                s = arg.strength
                lines.append("## 强度评估")
                lines.append("")
                lines.append(f"- **总体评分**：{s.overall_score:.2f}")
                lines.append(f"- **等级**：{STRENGTH_LEVELS.get(s.level, s.level)}")
                lines.append("- **各维度**：")
                for dim, score in s.dimensions.items():
                    dim_name = EVALUATION_DIMENSIONS.get(dim, dim)
                    lines.append(f"  - {dim_name}：{score:.2f}")
                if s.weaknesses:
                    lines.append("- **薄弱环节**：")
                    for w in s.weaknesses:
                        lines.append(f"  - {w}")
                if s.recommendations:
                    lines.append("- **改进建议**：")
                    for r in s.recommendations:
                        lines.append(f"  - {r}")
                lines.append("")
            return "\n".join(lines)

    def export_argument_dict(self, argument_id: str) -> dict[str, Any]:
        """导出论证为字典。"""
        with self._lock:
            arg = self._arguments.get(argument_id)
            if not arg:
                return {}
            return arg.to_dict()
