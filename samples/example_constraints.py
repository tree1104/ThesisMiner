"""
ThesisMiner v8.0 约束系统示例代码
==================================

本文件提供 ThesisMiner 约束系统的完整示例代码，包括：
1. 自定义硬约束实现（标题长度/学科匹配/导师方向/时间可行性）
2. 新颖性评估扩展（自定义相似度算法/阈值调整/维度扩展）
3. 风格规范化器扩展（自定义替换词表/句式调整/学术规范检查）
4. 多粒度生成示例（标题级/摘要级/大纲级/全文级生成器）
5. 约束组合示例（硬约束 + 软约束组合/优先级/短路评估）

使用方法：
    python samples/example_constraints.py

依赖：
    - Python 3.10+
    - 参见 requirements.txt
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ============================================================================
# 基础数据结构
# ============================================================================

@dataclass
class ConstraintResult:
    """约束检查结果"""

    passed: bool
    constraint_name: str
    message: str
    actual_value: Any = None
    expected_value: Any = None
    score: Optional[float] = None  # 0-100，用于软约束

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "constraint_name": self.constraint_name,
            "message": self.message,
            "actual_value": self.actual_value,
            "expected_value": self.expected_value,
            "score": self.score,
        }


@dataclass
class Proposal:
    """论题数据"""

    title: str = ""
    abstract: str = ""
    outline: str = ""
    full_text: str = ""
    disciplines: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    methods: List[str] = field(default_factory=list)
    complexity: str = "medium"  # low / medium / high / very_high
    source: str = ""  # mentor_project / senior_inherit / problem_awareness / cross_domain

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "abstract": self.abstract,
            "outline": self.outline,
            "full_text": self.full_text,
            "disciplines": self.disciplines,
            "keywords": self.keywords,
            "methods": self.methods,
            "complexity": self.complexity,
            "source": self.source,
        }


@dataclass
class EvaluationContext:
    """评估上下文"""

    session_id: str = ""
    degree: str = "master"  # bachelor / master / doctor
    discipline: str = ""
    advisor_name: str = ""
    advisor_research_areas: List[str] = field(default_factory=list)
    available_months: int = 12
    has_gpu: bool = False
    trending_keywords: List[str] = field(default_factory=list)
    existing_proposals: List[str] = field(default_factory=list)


# ============================================================================
# 硬约束抽象基类
# ============================================================================

class BaseHardConstraint(ABC):
    """硬约束抽象基类

    硬约束是必须满足的条件，失败即拒绝（fail-fast）。
    """

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description

    @abstractmethod
    async def check(self, proposal: Proposal, context: EvaluationContext) -> ConstraintResult:
        """检查约束是否满足

        Args:
            proposal: 论题数据
            context: 评估上下文

        Returns:
            ConstraintResult: 检查结果
        """
        pass

    def __repr__(self):
        return f"<HardConstraint: {self.name}>"


# ============================================================================
# 内置硬约束实现
# ============================================================================

class TitleLengthConstraint(BaseHardConstraint):
    """标题长度约束

    要求论题标题长度在指定范围内。
    """

    def __init__(self, min_len: int = 15, max_len: int = 40):
        super().__init__(
            name="title_length",
            description=f"标题长度必须在 {min_len}-{max_len} 字符之间"
        )
        self.min_len = min_len
        self.max_len = max_len

    async def check(self, proposal: Proposal, context: EvaluationContext) -> ConstraintResult:
        title = proposal.title
        length = len(title)

        if length < self.min_len:
            return ConstraintResult(
                passed=False,
                constraint_name=self.name,
                message=f"标题过短：{length} 字符（最少 {self.min_len}）",
                actual_value=length,
                expected_value=f">= {self.min_len}"
            )

        if length > self.max_len:
            return ConstraintResult(
                passed=False,
                constraint_name=self.name,
                message=f"标题过长：{length} 字符（最多 {self.max_len}）",
                actual_value=length,
                expected_value=f"<= {self.max_len}"
            )

        return ConstraintResult(
            passed=True,
            constraint_name=self.name,
            message=f"标题长度合格：{length} 字符",
            actual_value=length,
            expected_value=f"{self.min_len}-{self.max_len}"
        )


class DisciplineMatchConstraint(BaseHardConstraint):
    """学科匹配约束

    检查论题是否属于用户指定的学科。
    """

    # 学科关键词映射
    DISCIPLINE_KEYWORDS: Dict[str, List[str]] = {
        "computer_science": [
            "计算机", "算法", "深度学习", "机器学习", "人工智能",
            "图像", "视觉", "自然语言", "数据挖掘", "网络"
        ],
        "electronic_engineering": [
            "电子", "电路", "信号", "通信", "射频", "嵌入式",
            "物联网", "传感器", "芯片"
        ],
        "mechanical_engineering": [
            "机械", "制造", "设计", "材料", "力学", "机器人",
            "CAD", "3D打印", "有限元"
        ],
        "medicine": [
            "医学", "临床", "诊断", "治疗", "影像", "病理",
            "药物", "基因", "细胞"
        ],
    }

    def __init__(self):
        super().__init__(
            name="discipline_match",
            description="论题必须与用户学科匹配"
        )

    async def check(self, proposal: Proposal, context: EvaluationContext) -> ConstraintResult:
        if not context.discipline:
            return ConstraintResult(
                passed=True,
                constraint_name=self.name,
                message="未指定学科，跳过检查"
            )

        keywords = self.DISCIPLINE_KEYWORDS.get(context.discipline, [])
        text = f"{proposal.title} {proposal.abstract} {' '.join(proposal.keywords)}"

        matched = [kw for kw in keywords if kw in text]

        if not matched:
            return ConstraintResult(
                passed=False,
                constraint_name=self.name,
                message=f"论题与学科 {context.discipline} 不匹配（未命中任何关键词）",
                actual_value=[],
                expected_value=keywords
            )

        return ConstraintResult(
            passed=True,
            constraint_name=self.name,
            message=f"学科匹配（命中关键词：{matched[:5]}）",
            actual_value=matched,
            expected_value=keywords
        )


class AdvisorAlignmentConstraint(BaseHardConstraint):
    """导师方向一致性约束

    检查论题是否与导师的研究方向一致。
    """

    def __init__(self, min_match: int = 1):
        super().__init__(
            name="advisor_alignment",
            description="论题应与导师研究方向一致"
        )
        self.min_match = min_match

    async def check(self, proposal: Proposal, context: EvaluationContext) -> ConstraintResult:
        if not context.advisor_research_areas:
            return ConstraintResult(
                passed=True,
                constraint_name=self.name,
                message="未提供导师研究方向，跳过检查"
            )

        text = f"{proposal.title} {proposal.abstract} {' '.join(proposal.keywords)}"

        matched_areas = []
        for area in context.advisor_research_areas:
            if area in text:
                matched_areas.append(area)

        if len(matched_areas) < self.min_match:
            return ConstraintResult(
                passed=False,
                constraint_name=self.name,
                message=f"与导师方向不一致（匹配 {len(matched_areas)} 个，需要至少 {self.min_match} 个）",
                actual_value=matched_areas,
                expected_value=context.advisor_research_areas
            )

        return ConstraintResult(
            passed=True,
            constraint_name=self.name,
            message=f"导师方向一致（匹配：{matched_areas}）",
            actual_value=matched_areas,
            expected_value=context.advisor_research_areas
        )


class TimeFeasibilityConstraint(BaseHardConstraint):
    """时间可行性约束

    根据论题复杂度与可用时间评估是否可行。
    """

    COMPLEXITY_MONTHS: Dict[str, int] = {
        "low": 6,
        "medium": 9,
        "high": 12,
        "very_high": 18,
    }

    def __init__(self):
        super().__init__(
            name="time_feasibility",
            description="评估论题在给定时间内是否可完成"
        )

    async def check(self, proposal: Proposal, context: EvaluationContext) -> ConstraintResult:
        complexity = proposal.complexity
        available = context.available_months
        required = self.COMPLEXITY_MONTHS.get(complexity, 9)

        if available < required:
            return ConstraintResult(
                passed=False,
                constraint_name=self.name,
                message=f"时间不足：需要 {required} 个月，仅有 {available} 个月",
                actual_value=available,
                expected_value=required
            )

        return ConstraintResult(
            passed=True,
            constraint_name=self.name,
            message=f"时间充足：需要 {required} 个月，有 {available} 个月",
            actual_value=available,
            expected_value=required
        )


class DuplicationConstraint(BaseHardConstraint):
    """重复度检测约束

    使用 SimHash 算法检测论题与已有论题的相似度。
    """

    def __init__(self, threshold: float = 0.30):
        super().__init__(
            name="duplication",
            description=f"重复度必须低于 {threshold * 100}%"
        )
        self.threshold = threshold

    async def check(self, proposal: Proposal, context: EvaluationContext) -> ConstraintResult:
        if not context.existing_proposals:
            return ConstraintResult(
                passed=True,
                constraint_name=self.name,
                message="无已有论题，跳过检查"
            )

        # 计算与每个已有论题的相似度
        max_similarity = 0.0
        most_similar = ""

        for existing in context.existing_proposals:
            sim = self._calculate_similarity(proposal.title, existing)
            if sim > max_similarity:
                max_similarity = sim
                most_similar = existing

        if max_similarity > self.threshold:
            return ConstraintResult(
                passed=False,
                constraint_name=self.name,
                message=f"重复度过高：{max_similarity:.1%}（阈值 {self.threshold:.0%}）",
                actual_value=max_similarity,
                expected_value=self.threshold
            )

        return ConstraintResult(
            passed=True,
            constraint_name=self.name,
            message=f"重复度合格：{max_similarity:.1%}",
            actual_value=max_similarity,
            expected_value=self.threshold
        )

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算两个文本的相似度（简化版 Jaccard）"""
        set1 = set(text1)
        set2 = set(text2)
        intersection = set1 & set2
        union = set1 | set2
        return len(intersection) / len(union) if union else 0.0


class AITraceConstraint(BaseHardConstraint):
    """AI 痕迹检测约束

    检测文本中是否含有 AI 生成的痕迹。
    """

    # AI 常用模板词
    AI_TEMPLATE_WORDS: List[str] = [
        "值得注意的是", "需要指出的是", "总而言之", "综上所述",
        "首先", "其次", "最后", "此外", "然而", "因此",
        "众所周知", "不可否认", "毫无疑问", "显而易见",
        "在当今社会", "随着时代的发展", "在信息化时代",
        "本文将", "本研究将", "本论文将",
        "旨在", "致力于", "聚焦于", "着眼于",
        "深入探讨", "全面分析", "系统研究",
        "具有重要意义", "具有广阔前景", "具有深远影响",
    ]

    def __init__(self, max_template_ratio: float = 0.15):
        super().__init__(
            name="ai_trace",
            description=f"AI 痕迹词比例必须低于 {max_template_ratio * 100}%"
        )
        self.max_template_ratio = max_template_ratio

    async def check(self, proposal: Proposal, context: EvaluationContext) -> ConstraintResult:
        text = f"{proposal.title} {proposal.abstract}"

        # 统计模板词出现次数
        template_count = 0
        found_words = []
        for word in self.AI_TEMPLATE_WORDS:
            count = text.count(word)
            if count > 0:
                template_count += count
                found_words.append(f"{word}({count})")

        # 计算比例
        total_words = len(text.split()) if text.split() else 1
        ratio = template_count / total_words if total_words > 0 else 0

        if ratio > self.max_template_ratio:
            return ConstraintResult(
                passed=False,
                constraint_name=self.name,
                message=f"AI 痕迹过多：{ratio:.1%}（阈值 {self.max_template_ratio:.0%}），"
                        f"发现：{found_words[:5]}",
                actual_value=ratio,
                expected_value=self.max_template_ratio
            )

        return ConstraintResult(
            passed=True,
            constraint_name=self.name,
            message=f"AI 痕迹合格：{ratio:.1%}",
            actual_value=ratio,
            expected_value=self.max_template_ratio
        )


# ============================================================================
# 自定义硬约束示例
# ============================================================================

class KeywordRequiredConstraint(BaseHardConstraint):
    """关键词必须包含约束

    要求论题标题或摘要中必须包含指定的关键词。
    """

    def __init__(
        self,
        required_keywords: List[str],
        field: str = "title",
        case_sensitive: bool = False
    ):
        super().__init__(
            name="keyword_required",
            description=f"要求{field}中包含关键词：{required_keywords}"
        )
        self.required_keywords = required_keywords
        self.field = field
        self.case_sensitive = case_sensitive

    async def check(self, proposal: Proposal, context: EvaluationContext) -> ConstraintResult:
        text = getattr(proposal, self.field, "")
        if not self.case_sensitive:
            text = text.lower()
            keywords = [kw.lower() for kw in self.required_keywords]
        else:
            keywords = self.required_keywords

        missing = [kw for kw in keywords if kw not in text]

        if missing:
            return ConstraintResult(
                passed=False,
                constraint_name=self.name,
                message=f"{self.field}中缺少关键词：{missing}",
                actual_value=text,
                expected_value=self.required_keywords
            )

        return ConstraintResult(
            passed=True,
            constraint_name=self.name,
            message="所有关键词均存在",
            actual_value=text,
            expected_value=self.required_keywords
        )


class ResourceAvailabilityConstraint(BaseHardConstraint):
    """资源可用性约束

    检查论题所需的资源是否可用（如 GPU、数据集等）。
    """

    def __init__(self):
        super().__init__(
            name="resource_availability",
            description="检查所需资源是否可用"
        )

    async def check(self, proposal: Proposal, context: EvaluationContext) -> ConstraintResult:
        issues = []

        # 检查 GPU 需求
        gpu_keywords = ["深度学习", "神经网络", "训练", "GPU", "CUDA"]
        text = f"{proposal.title} {proposal.abstract}"
        needs_gpu = any(kw in text for kw in gpu_keywords)

        if needs_gpu and not context.has_gpu:
            issues.append("需要 GPU 但不可用")

        # 检查数据集需求
        dataset_keywords = ["数据集", "dataset", "语料库", "corpus"]
        needs_dataset = any(kw in text for kw in dataset_keywords)
        if needs_dataset and not proposal.keywords:
            issues.append("需要数据集但未指定")

        if issues:
            return ConstraintResult(
                passed=False,
                constraint_name=self.name,
                message="；".join(issues),
                actual_value={"has_gpu": context.has_gpu},
                expected_value={"has_gpu": needs_gpu}
            )

        return ConstraintResult(
            passed=True,
            constraint_name=self.name,
            message="资源充足",
        )


# ============================================================================
# 软约束：新颖性评估
# ============================================================================

@dataclass
class NoveltyDimension:
    """新颖性维度"""
    name: str
    score: float  # 0-100
    weight: float
    reasoning: str


class NoveltyScorer:
    """新颖性评分器

    四维评估：
    1. 学科交叉（cross_discipline）
    2. 方法迁移（method_transfer）
    3. 痛点突破（pain_point）
    4. 趋势前瞻（trend_foresight）
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or {
            "cross_discipline": 0.25,
            "method_transfer": 0.25,
            "pain_point": 0.25,
            "trend_foresight": 0.25,
        }

    async def score(self, proposal: Proposal, context: EvaluationContext) -> Dict[str, Any]:
        """计算新颖性评分"""
        dimensions = [
            await self._score_cross_discipline(proposal, context),
            await self._score_method_transfer(proposal, context),
            await self._score_pain_point(proposal, context),
            await self._score_trend_foresight(proposal, context),
        ]

        total = sum(d.score * d.weight for d in dimensions)

        return {
            "total_score": round(total, 2),
            "dimensions": [
                {
                    "name": d.name,
                    "score": d.score,
                    "weight": d.weight,
                    "reasoning": d.reasoning,
                }
                for d in dimensions
            ],
            "passed": total >= 60,
        }

    async def _score_cross_discipline(self, proposal: Proposal, context: EvaluationContext) -> NoveltyDimension:
        """评估学科交叉程度"""
        disciplines = proposal.disciplines
        if len(disciplines) >= 3:
            score = 90
            reasoning = f"涉及 {len(disciplines)} 个学科，交叉程度高"
        elif len(disciplines) == 2:
            score = 70
            reasoning = f"涉及 {len(disciplines)} 个学科，有一定交叉"
        else:
            score = 40
            reasoning = "单一学科，交叉程度低"

        return NoveltyDimension(
            name="cross_discipline",
            score=score,
            weight=self.weights["cross_discipline"],
            reasoning=reasoning,
        )

    async def _score_method_transfer(self, proposal: Proposal, context: EvaluationContext) -> NoveltyDimension:
        """评估方法迁移程度"""
        if proposal.methods and proposal.disciplines:
            score = 85
            reasoning = f"将 {proposal.methods} 迁移到 {proposal.disciplines}"
        else:
            score = 50
            reasoning = "方法迁移不明显"

        return NoveltyDimension(
            name="method_transfer",
            score=score,
            weight=self.weights["method_transfer"],
            reasoning=reasoning,
        )

    async def _score_pain_point(self, proposal: Proposal, context: EvaluationContext) -> NoveltyDimension:
        """评估痛点突破程度"""
        # 简化：基于摘要中的问题关键词
        pain_keywords = ["问题", "挑战", "困难", "不足", "局限", "痛点"]
        text = proposal.abstract
        found = [kw for kw in pain_keywords if kw in text]

        if len(found) >= 2:
            score = 88
            reasoning = f"识别了多个痛点：{found}"
        elif found:
            score = 65
            reasoning = f"识别了痛点：{found}"
        else:
            score = 30
            reasoning = "未明确识别痛点"

        return NoveltyDimension(
            name="pain_point",
            score=score,
            weight=self.weights["pain_point"],
            reasoning=reasoning,
        )

    async def _score_trend_foresight(self, proposal: Proposal, context: EvaluationContext) -> NoveltyDimension:
        """评估趋势前瞻程度"""
        keywords = proposal.keywords
        trending = context.trending_keywords

        match_count = len(set(keywords) & set(trending))
        if match_count >= 3:
            score = 90
            reasoning = f"命中 {match_count} 个趋势关键词"
        elif match_count >= 1:
            score = 65
            reasoning = f"命中 {match_count} 个趋势关键词"
        else:
            score = 40
            reasoning = "未命中趋势关键词"

        return NoveltyDimension(
            name="trend_foresight",
            score=score,
            weight=self.weights["trend_foresight"],
            reasoning=reasoning,
        )


class ExtendedNoveltyScorer(NoveltyScorer):
    """扩展的新颖性评分器，增加社会价值维度"""

    def __init__(self):
        weights = {
            "cross_discipline": 0.20,
            "method_transfer": 0.20,
            "pain_point": 0.20,
            "trend_foresight": 0.20,
            "social_value": 0.20,
        }
        super().__init__(weights)

    async def score(self, proposal: Proposal, context: EvaluationContext) -> Dict[str, Any]:
        dimensions = [
            await self._score_cross_discipline(proposal, context),
            await self._score_method_transfer(proposal, context),
            await self._score_pain_point(proposal, context),
            await self._score_trend_foresight(proposal, context),
            await self._score_social_value(proposal, context),
        ]

        total = sum(d.score * d.weight for d in dimensions)

        return {
            "total_score": round(total, 2),
            "dimensions": [
                {
                    "name": d.name,
                    "score": d.score,
                    "weight": d.weight,
                    "reasoning": d.reasoning,
                }
                for d in dimensions
            ],
            "passed": total >= 60,
        }

    async def _score_social_value(self, proposal: Proposal, context: EvaluationContext) -> NoveltyDimension:
        """评估社会价值"""
        social_keywords = ["医疗", "健康", "教育", "环保", "安全", "公益"]
        text = f"{proposal.title} {proposal.abstract}"
        found = [kw for kw in social_keywords if kw in text]

        if len(found) >= 2:
            score = 90
            reasoning = f"具有显著社会价值：{found}"
        elif found:
            score = 70
            reasoning = f"有一定社会价值：{found}"
        else:
            score = 40
            reasoning = "社会价值不明显"

        return NoveltyDimension(
            name="social_value",
            score=score,
            weight=self.weights["social_value"],
            reasoning=reasoning,
        )


# ============================================================================
# 风格规范化器
# ============================================================================

class StyleNormalizer:
    """风格规范化器

    将生成的文本规范化为学术写作风格。
    """

    def __init__(self):
        self.replacement_rules: List[Tuple[str, str]] = []
        self._load_default_rules()

    def _load_default_rules(self):
        """加载默认替换规则"""
        self.replacement_rules = [
            # 口语化 → 学术化
            (r"很好", "优异"),
            (r"很大", "显著"),
            (r"很多", "大量"),
            (r"越来越", "日益"),
            (r"我觉得", "本研究认为"),
            (r"我们认为", "本研究认为"),
            (r"大家知道", "众所周知"),
            (r"所以说", "因此"),
            (r"然后", "随后"),
            (r"还有就是", "此外"),
            # AI 痕迹词
            (r"值得注意的是", ""),
            (r"需要指出的是", ""),
            (r"总而言之", "综上所述"),
        ]

    def normalize(self, text: str) -> str:
        """规范化文本"""
        for pattern, replacement in self.replacement_rules:
            text = re.sub(pattern, replacement, text)

        text = self._adjust_sentences(text)
        text = self._check_academic_norms(text)

        return text

    def _adjust_sentences(self, text: str) -> str:
        """调整句式"""
        sentences = text.split("。")
        adjusted = []
        for sent in sentences:
            if len(sent) > 80:
                parts = sent.split("，")
                if len(parts) > 2:
                    mid = len(parts) // 2
                    adjusted.append("，".join(parts[:mid]) + "。")
                    adjusted.append("，".join(parts[mid:]) + "。")
                else:
                    adjusted.append(sent + "。")
            else:
                adjusted.append(sent + "。")
        return "".join(adjusted)

    def _check_academic_norms(self, text: str) -> str:
        """检查学术规范"""
        text = re.sub(r"\[(\d+)\]", r"[\1]", text)
        return text

    def add_replacement_rule(self, pattern: str, replacement: str):
        """添加自定义替换规则"""
        self.replacement_rules.append((pattern, replacement))


class CustomStyleNormalizer(StyleNormalizer):
    """自定义风格规范化器"""

    def _load_default_rules(self):
        super()._load_default_rules()

        domain_rules = [
            (r"病人", "患者"),
            (r"看病", "就诊"),
            (r"治好", "治愈"),
            (r"做实验", "开展实验"),
            (r"得出结论", "研究结论表明"),
            (r"发现", "研究发现"),
        ]
        self.replacement_rules.extend(domain_rules)


# ============================================================================
# 约束组合器
# ============================================================================

class CompositeConstraint(BaseHardConstraint):
    """组合约束

    支持多种组合策略：
    - AND：所有约束必须通过
    - OR：任一约束通过即可
    - PRIORITY：按优先级短路评估
    """

    def __init__(
        self,
        name: str,
        constraints: List[BaseHardConstraint],
        strategy: str = "AND",
        priorities: Optional[List[int]] = None,
    ):
        super().__init__(name=name, description=f"组合约束（{strategy}）")
        self.constraints = constraints
        self.strategy = strategy
        self.priorities = priorities or list(range(len(constraints)))

    async def check(self, proposal: Proposal, context: EvaluationContext) -> ConstraintResult:
        if self.strategy == "AND":
            return await self._check_and(proposal, context)
        elif self.strategy == "OR":
            return await self._check_or(proposal, context)
        elif self.strategy == "PRIORITY":
            return await self._check_priority(proposal, context)
        else:
            raise ValueError(f"未知策略：{self.strategy}")

    async def _check_and(self, proposal: Proposal, context: EvaluationContext) -> ConstraintResult:
        """AND 策略"""
        failed = []
        for constraint in self.constraints:
            result = await constraint.check(proposal, context)
            if not result.passed:
                failed.append(result)

        if failed:
            messages = [f"[{r.constraint_name}] {r.message}" for r in failed]
            return ConstraintResult(
                passed=False,
                constraint_name=self.name,
                message="；".join(messages),
            )

        return ConstraintResult(
            passed=True,
            constraint_name=self.name,
            message="所有约束均通过"
        )

    async def _check_or(self, proposal: Proposal, context: EvaluationContext) -> ConstraintResult:
        """OR 策略"""
        for constraint in self.constraints:
            result = await constraint.check(proposal, context)
            if result.passed:
                return ConstraintResult(
                    passed=True,
                    constraint_name=self.name,
                    message=f"约束 {constraint.name} 通过"
                )

        return ConstraintResult(
            passed=False,
            constraint_name=self.name,
            message="所有约束均未通过"
        )

    async def _check_priority(self, proposal: Proposal, context: EvaluationContext) -> ConstraintResult:
        """PRIORITY 策略"""
        sorted_constraints = sorted(
            zip(self.priorities, self.constraints),
            key=lambda x: x[0]
        )

        for priority, constraint in sorted_constraints:
            result = await constraint.check(proposal, context)
            if not result.passed:
                return ConstraintResult(
                    passed=False,
                    constraint_name=self.name,
                    message=f"优先级 {priority} 约束 {constraint.name} 失败：{result.message}",
                )

        return ConstraintResult(
            passed=True,
            constraint_name=self.name,
            message="所有优先级约束均通过"
        )


# ============================================================================
# 约束注册表
# ============================================================================

CONSTRAINT_REGISTRY: Dict[str, BaseHardConstraint] = {}


def register_constraint(constraint: BaseHardConstraint):
    """注册约束"""
    CONSTRAINT_REGISTRY[constraint.name] = constraint


def get_constraint(name: str) -> BaseHardConstraint:
    """获取约束"""
    return CONSTRAINT_REGISTRY[name]


def list_constraints() -> List[str]:
    """列出所有约束"""
    return list(CONSTRAINT_REGISTRY.keys())


# ============================================================================
# 多粒度生成器
# ============================================================================

class MultiGranularityGenerator:
    """多粒度生成器

    生成不同详细程度的论题描述：
    - 标题级（15-40 字符）
    - 摘要级（200-300 字）
    - 大纲级（章节标题 + 简述）
    - 全文级（完整论题报告）
    """

    def __init__(self):
        self.templates = self._load_templates()

    def _load_templates(self) -> Dict[str, str]:
        """加载模板"""
        return {
            "title": "基于{method}的{domain}{task}方法研究",
            "abstract": (
                "{background}。然而，{problem}。"
                "本文提出一种基于{method}的{task}方法，"
                "主要贡献包括：{contributions}。"
                "在{dataset}上的实验表明，所提方法{result}。"
            ),
            "outline": (
                "第一章 绪论\n"
                "  1.1 研究背景与意义\n"
                "  1.2 国内外研究现状\n"
                "  1.3 研究内容与贡献\n"
                "  1.4 论文组织结构\n\n"
                "第二章 相关工作\n"
                "  2.1 {domain}基础\n"
                "  2.2 {method}方法\n\n"
                "第三章 方法\n"
                "  3.1 整体框架\n"
                "  3.2 核心模块设计\n\n"
                "第四章 实验\n"
                "  4.1 数据集\n"
                "  4.2 实验结果\n\n"
                "第五章 总结与展望\n"
            ),
        }

    def generate_title(self, params: Dict[str, str]) -> str:
        """生成标题"""
        return self.templates["title"].format(**params)

    def generate_abstract(self, params: Dict[str, str]) -> str:
        """生成摘要"""
        return self.templates["abstract"].format(**params)

    def generate_outline(self, params: Dict[str, str]) -> str:
        """生成大纲"""
        return self.templates["outline"].format(**params)

    def generate_all(self, params: Dict[str, str]) -> Dict[str, str]:
        """生成所有粒度"""
        return {
            "title": self.generate_title(params),
            "abstract": self.generate_abstract(params),
            "outline": self.generate_outline(params),
        }


# ============================================================================
# 示例函数
# ============================================================================

async def example_1_hard_constraints():
    """示例 1：硬约束检查"""
    print("\n" + "=" * 60)
    print("示例 1：硬约束检查")
    print("=" * 60)

    proposal = Proposal(
        title="基于半监督学习与注意力机制的小病灶检测方法研究",
        abstract="医学影像中的小病灶检测是计算机辅助诊断的关键挑战。本文提出一种基于半监督学习的方法...",
        disciplines=["computer_science", "medicine"],
        keywords=["半监督学习", "注意力机制", "小病灶检测", "医学影像"],
        methods=["半监督学习", "注意力机制"],
        complexity="medium",
        source="problem_awareness",
    )

    context = EvaluationContext(
        session_id="sess_1",
        degree="master",
        discipline="computer_science",
        advisor_name="张教授",
        advisor_research_areas=["图像识别", "深度学习", "医学影像分析"],
        available_months=12,
        has_gpu=True,
        trending_keywords=["半监督学习", "注意力机制", "Vision Transformer"],
    )

    constraints = [
        TitleLengthConstraint(min_len=15, max_len=40),
        DisciplineMatchConstraint(),
        AdvisorAlignmentConstraint(),
        TimeFeasibilityConstraint(),
        DuplicationConstraint(threshold=0.30),
        AITraceConstraint(),
    ]

    for constraint in constraints:
        result = await constraint.check(proposal, context)
        status = "✓" if result.passed else "✗"
        print(f"{status} {constraint.name}: {result.message}")


async def example_2_novelty_scoring():
    """示例 2：新颖性评分"""
    print("\n" + "=" * 60)
    print("示例 2：新颖性评分")
    print("=" * 60)

    proposal = Proposal(
        title="基于半监督学习与注意力机制的小病灶检测方法研究",
        abstract="医学影像中的小病灶检测存在标注数据稀缺的问题。本文针对此痛点提出解决方案。",
        disciplines=["computer_science", "medicine"],
        keywords=["半监督学习", "注意力机制", "小病灶检测"],
        methods=["半监督学习", "注意力机制"],
    )

    context = EvaluationContext(
        trending_keywords=["半监督学习", "注意力机制", "Vision Transformer"],
    )

    # 标准评分器
    scorer = NoveltyScorer()
    result = await scorer.score(proposal, context)
    print(f"标准评分器总分: {result['total_score']}")
    for dim in result["dimensions"]:
        print(f"  - {dim['name']}: {dim['score']} ({dim['reasoning']})")

    # 扩展评分器
    print()
    ext_scorer = ExtendedNoveltyScorer()
    ext_result = await ext_scorer.score(proposal, context)
    print(f"扩展评分器总分: {ext_result['total_score']}")
    for dim in ext_result["dimensions"]:
        print(f"  - {dim['name']}: {dim['score']} ({dim['reasoning']})")


async def example_3_style_normalization():
    """示例 3：风格规范化"""
    print("\n" + "=" * 60)
    print("示例 3：风格规范化")
    print("=" * 60)

    text = "我们做实验发现，病人的病治好了，这个方法很好。值得注意的是，效果很大。"

    normalizer = StyleNormalizer()
    normalized = normalizer.normalize(text)
    print(f"原始: {text}")
    print(f"标准: {normalized}")

    custom = CustomStyleNormalizer()
    custom_normalized = custom.normalize(text)
    print(f"自定义: {custom_normalized}")


async def example_4_composite_constraints():
    """示例 4：约束组合"""
    print("\n" + "=" * 60)
    print("示例 4：约束组合")
    print("=" * 60)

    proposal = Proposal(
        title="基于深度学习的研究",
        complexity="medium",
    )

    context = EvaluationContext(
        available_months=12,
        has_gpu=True,
    )

    # AND 组合
    and_constraint = CompositeConstraint(
        name="basic_requirements",
        constraints=[
            TitleLengthConstraint(),
            TimeFeasibilityConstraint(),
        ],
        strategy="AND",
    )
    result = await and_constraint.check(proposal, context)
    print(f"AND 策略: {'通过' if result.passed else '失败'} - {result.message}")

    # PRIORITY 组合
    priority_constraint = CompositeConstraint(
        name="priority_check",
        constraints=[
            TimeFeasibilityConstraint(),
            TitleLengthConstraint(),
        ],
        strategy="PRIORITY",
        priorities=[1, 2],
    )
    result = await priority_constraint.check(proposal, context)
    print(f"PRIORITY 策略: {'通过' if result.passed else '失败'} - {result.message}")


async def example_5_multi_granularity():
    """示例 5：多粒度生成"""
    print("\n" + "=" * 60)
    print("示例 5：多粒度生成")
    print("=" * 60)

    generator = MultiGranularityGenerator()

    params = {
        "method": "半监督学习",
        "domain": "医学影像",
        "task": "小病灶检测",
        "background": "医学影像中的小病灶检测是关键挑战",
        "problem": "标注数据稀缺且小病灶特征不明显",
        "contributions": "多尺度注意力模块、半监督学习策略、不确定性估计",
        "dataset": "ChestX-ray14",
        "result": "mAP 提升 5.3%",
    }

    results = generator.generate_all(params)

    print("标题级:")
    print(f"  {results['title']}")
    print(f"\n摘要级:")
    print(f"  {results['abstract']}")
    print(f"\n大纲级:")
    print(results['outline'])


async def example_6_registration():
    """示例 6：约束注册"""
    print("\n" + "=" * 60)
    print("示例 6：约束注册")
    print("=" * 60)

    register_constraint(TitleLengthConstraint())
    register_constraint(DisciplineMatchConstraint())
    register_constraint(AdvisorAlignmentConstraint())
    register_constraint(TimeFeasibilityConstraint())
    register_constraint(DuplicationConstraint())
    register_constraint(AITraceConstraint())
    register_constraint(KeywordRequiredConstraint(required_keywords=["研究"]))
    register_constraint(ResourceAvailabilityConstraint())

    constraints = list_constraints()
    print(f"已注册 {len(constraints)} 个约束:")
    for name in constraints:
        print(f"  - {name}")


# ============================================================================
# 主函数
# ============================================================================

async def main():
    """主函数"""
    print("=" * 60)
    print("ThesisMiner v8.0 约束系统示例代码")
    print("=" * 60)

    await example_1_hard_constraints()
    await example_2_novelty_scoring()
    await example_3_style_normalization()
    await example_4_composite_constraints()
    await example_5_multi_granularity()
    await example_6_registration()

    print("\n" + "=" * 60)
    print("所有示例执行完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
