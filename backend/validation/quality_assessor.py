"""质量评估器模块

提供完整的多维度学术质量评估，包括：
    - 创新性评估
    - 学术规范性评估
    - 逻辑性评估
    - 实用性评估
    - 评估指标体系、权重配置、评分模型
    - 评估报告生成、雷达图数据、改进建议
    - 历史评估对比、趋势分析、标杆对比

设计原则：
    1. 零外部依赖：仅使用 Python 标准库
    2. 线程安全：所有公共方法通过 RLock 保护
    3. 指标可配置：评估指标与权重支持动态调整
    4. 可扩展：支持新增评估维度
"""
from __future__ import annotations

import math
import re
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Callable, Optional


# ===== 枚举与常量 =====


class QualityDimension:
    """质量评估维度常量。"""

    INNOVATION = "innovation"        # 创新性
    ACADEMIC_RIGOR = "academic_rigor"  # 学术规范性
    LOGIC = "logic"                  # 逻辑性
    PRACTICALITY = "practicality"    # 实用性
    COMPLETENESS = "completeness"    # 完整性
    CLARITY = "clarity"              # 表达清晰度
    METHODOLOGY = "methodology"      # 方法论
    IMPACT = "impact"                # 影响力


# 维度中文名
DIMENSION_NAMES = {
    QualityDimension.INNOVATION: "创新性",
    QualityDimension.ACADEMIC_RIGOR: "学术规范性",
    QualityDimension.LOGIC: "逻辑性",
    QualityDimension.PRACTICALITY: "实用性",
    QualityDimension.COMPLETENESS: "完整性",
    QualityDimension.CLARITY: "表达清晰度",
    QualityDimension.METHODOLOGY: "方法论",
    QualityDimension.IMPACT: "影响力",
}

# 默认维度权重
DEFAULT_DIMENSION_WEIGHTS = {
    QualityDimension.INNOVATION: 0.2,
    QualityDimension.ACADEMIC_RIGOR: 0.15,
    QualityDimension.LOGIC: 0.15,
    QualityDimension.PRACTICALITY: 0.15,
    QualityDimension.COMPLETENESS: 0.1,
    QualityDimension.CLARITY: 0.1,
    QualityDimension.METHODOLOGY: 0.1,
    QualityDimension.IMPACT: 0.05,
}

# 评分等级
SCORE_GRADES = {
    (90, 100): "A",
    (80, 90): "B",
    (70, 80): "C",
    (60, 70): "D",
    (0, 60): "F",
}

# 评分等级描述
GRADE_DESCRIPTIONS = {
    "A": "优秀",
    "B": "良好",
    "C": "合格",
    "D": "需改进",
    "F": "不合格",
}

# 创新类型
INNOVATION_TYPES = {
    "theoretical": "理论创新",
    "methodological": "方法创新",
    "empirical": "实证创新",
    "applied": "应用创新",
    "data": "数据创新",
    "perspective": "视角创新",
}

# 学术规范检查项
ACADEMIC_NORM_ITEMS = {
    "citation_format": "引用格式规范",
    "reference_completeness": "参考文献完整",
    "terminology_accuracy": "术语使用准确",
    "structure_compliance": "结构符合规范",
    "language_formality": "语言正式性",
    "data_attribution": "数据来源标注",
}


# ===== 数据结构 =====


@dataclass
class AssessmentIndicator:
    """评估指标。

    Attributes:
        id: 指标 ID。
        name: 指标名称。
        dimension: 所属维度。
        description: 指标描述。
        weight: 权重（0-1）。
        max_score: 满分。
        scoring_criteria: 评分标准（等级 -> 描述）。
        evaluator: 评估函数。
    """

    id: str = ""
    name: str = ""
    dimension: str = ""
    description: str = ""
    weight: float = 1.0
    max_score: float = 100.0
    scoring_criteria: dict[str, str] = field(default_factory=dict)
    evaluator: Optional[Callable[[dict[str, Any]], float]] = None

    def evaluate(self, data: dict[str, Any]) -> float:
        """执行评估。"""
        if self.evaluator is None:
            return 0.0
        try:
            score = self.evaluator(data)
            return max(0.0, min(self.max_score, float(score)))
        except Exception:
            return 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "dimension": self.dimension,
            "description": self.description,
            "weight": self.weight,
            "max_score": self.max_score,
            "scoring_criteria": self.scoring_criteria,
        }


@dataclass
class DimensionScore:
    """维度评分结果。

    Attributes:
        dimension: 维度名。
        score: 评分（0-100）。
        weight: 权重。
        weighted_score: 加权得分。
        indicators: 各指标得分。
        strengths: 优势点。
        weaknesses: 不足点。
        suggestions: 改进建议。
    """

    dimension: str = ""
    score: float = 0.0
    weight: float = 0.0
    weighted_score: float = 0.0
    indicators: dict[str, float] = field(default_factory=dict)
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "dimension_name": DIMENSION_NAMES.get(self.dimension, self.dimension),
            "score": round(self.score, 2),
            "weight": self.weight,
            "weighted_score": round(self.weighted_score, 2),
            "indicators": {k: round(v, 2) for k, v in self.indicators.items()},
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "suggestions": self.suggestions,
        }


@dataclass
class QualityReport:
    """质量评估报告。

    Attributes:
        id: 报告 ID。
        thesis_id: 论题 ID。
        timestamp: 评估时间。
        overall_score: 综合评分（0-100）。
        grade: 评分等级。
        dimension_scores: 各维度评分。
        radar_data: 雷达图数据。
        strengths: 总体优势。
        weaknesses: 总体不足。
        suggestions: 总体建议。
        benchmark_comparison: 标杆对比。
        metadata: 元数据。
    """

    id: str = ""
    thesis_id: str = ""
    timestamp: str = ""
    overall_score: float = 0.0
    grade: str = ""
    dimension_scores: dict[str, DimensionScore] = field(default_factory=dict)
    radar_data: dict[str, Any] = field(default_factory=dict)
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    benchmark_comparison: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "thesis_id": self.thesis_id,
            "timestamp": self.timestamp,
            "overall_score": round(self.overall_score, 2),
            "grade": self.grade,
            "grade_description": GRADE_DESCRIPTIONS.get(self.grade, ""),
            "dimension_scores": {
                k: v.to_dict() for k, v in self.dimension_scores.items()
            },
            "radar_data": self.radar_data,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "suggestions": self.suggestions,
            "benchmark_comparison": self.benchmark_comparison,
            "metadata": self.metadata,
        }


# ===== 工具函数 =====


def _now_iso() -> str:
    """返回当前时间的 ISO 格式字符串。"""
    return datetime.now().isoformat()


def _new_id(prefix: str = "report") -> str:
    """生成带前缀的唯一 ID。"""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _count_words(text: str) -> int:
    """统计字数。"""
    if not text:
        return 0
    cn_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    en_words = re.findall(r"[a-zA-Z]+", text)
    return cn_count + len(en_words)


def _count_sentences(text: str) -> int:
    """统计句子数。"""
    if not text:
        return 0
    return len(re.findall(r"[。！？\.!\?]+", text))


def _score_to_grade(score: float) -> str:
    """分数转等级。"""
    for (low, high), grade in SCORE_GRADES.items():
        if low <= score < high:
            return grade
    return "F"


# ===== 创新性评估器 =====


class InnovationAssessor:
    """创新性评估器。"""

    def assess(self, data: dict[str, Any]) -> DimensionScore:
        """评估创新性。"""
        result = DimensionScore(
            dimension=QualityDimension.INNOVATION,
            weight=DEFAULT_DIMENSION_WEIGHTS[QualityDimension.INNOVATION],
        )
        differentiation = data.get("differentiation", "")
        inspiration_source = data.get("inspiration_source", "")
        title = data.get("title", "")
        # 指标1：创新点明确性
        clarity_score = self._score_innovation_clarity(differentiation)
        result.indicators["innovation_clarity"] = clarity_score
        # 指标2：创新类型多样性
        diversity_score = self._score_innovation_diversity(differentiation)
        result.indicators["innovation_diversity"] = diversity_score
        # 指标3：创新程度
        degree_score = self._score_innovation_degree(differentiation, title)
        result.indicators["innovation_degree"] = degree_score
        # 指标4：灵感来源清晰度
        source_score = self._score_inspiration_source(inspiration_source)
        result.indicators["inspiration_source"] = source_score
        # 综合维度评分
        result.score = (
            clarity_score * 0.3
            + diversity_score * 0.25
            + degree_score * 0.35
            + source_score * 0.1
        )
        result.weighted_score = result.score * result.weight
        # 优势与不足
        if clarity_score >= 80:
            result.strengths.append("创新点表述清晰明确")
        if degree_score >= 80:
            result.strengths.append("创新程度较高")
        if clarity_score < 60:
            result.weaknesses.append("创新点表述不够清晰")
        if diversity_score < 50:
            result.weaknesses.append("创新类型单一")
        if degree_score < 60:
            result.weaknesses.append("创新程度不足")
        # 建议
        if clarity_score < 70:
            result.suggestions.append("明确区分本研究与已有研究的差异点")
        if diversity_score < 60:
            result.suggestions.append("考虑从理论、方法、应用等多维度创新")
        return result

    def _score_innovation_clarity(self, differentiation: str) -> float:
        """评分创新点明确性。"""
        if not differentiation:
            return 0.0
        score = 50.0
        # 检查是否明确表述
        if any(kw in differentiation for kw in ["首次", "首创", "提出", "构建", "创新"]):
            score += 20
        # 检查是否与已有研究对比
        if any(kw in differentiation for kw in ["不同于", "区别于", "相比", "优于", "改进"]):
            score += 15
        # 检查长度
        word_count = _count_words(differentiation)
        if word_count >= 100:
            score += 15
        elif word_count >= 50:
            score += 10
        return min(100, score)

    def _score_innovation_diversity(self, differentiation: str) -> float:
        """评分创新类型多样性。"""
        if not differentiation:
            return 0.0
        types_found = 0
        for inn_type, keywords in {
            "theoretical": ["理论", "概念", "框架", "模型"],
            "methodological": ["方法", "算法", "技术", "工具"],
            "empirical": ["实证", "数据", "实验", "验证"],
            "applied": ["应用", "场景", "实践", "落地"],
            "data": ["数据集", "语料", "样本"],
            "perspective": ["视角", "角度", "观点"],
        }.items():
            if any(kw in differentiation for kw in keywords):
                types_found += 1
        # 1种60分，2种80分，3种及以上100分
        if types_found >= 3:
            return 100.0
        elif types_found == 2:
            return 80.0
        elif types_found == 1:
            return 60.0
        return 30.0

    def _score_innovation_degree(self, differentiation: str, title: str) -> float:
        """评分创新程度。"""
        score = 50.0
        if not differentiation:
            return score
        # 强创新表述
        if any(kw in differentiation for kw in ["首次", "首创", "开创", "原创"]):
            score += 30
        # 中等创新
        elif any(kw in differentiation for kw in ["改进", "优化", "扩展", "融合"]):
            score += 20
        # 弱创新
        elif any(kw in differentiation for kw in ["应用", "验证", "复现"]):
            score += 10
        # 跨学科创新加分
        if any(kw in differentiation for kw in ["跨学科", "交叉", "融合"]):
            score += 10
        return min(100, score)

    def _score_inspiration_source(self, source: str) -> float:
        """评分灵感来源清晰度。"""
        if not source:
            return 30.0
        score = 60.0
        if len(source) >= 50:
            score += 20
        if any(kw in source for kw in ["基于", "受到", "源于", "来自"]):
            score += 10
        if any(kw in source for kw in ["文献", "实践", "观察", "问题"]):
            score += 10
        return min(100, score)


# ===== 学术规范性评估器 =====


class AcademicRigorAssessor:
    """学术规范性评估器。"""

    def assess(self, data: dict[str, Any]) -> DimensionScore:
        """评估学术规范性。"""
        result = DimensionScore(
            dimension=QualityDimension.ACADEMIC_RIGOR,
            weight=DEFAULT_DIMENSION_WEIGHTS[QualityDimension.ACADEMIC_RIGOR],
        )
        references = data.get("references", [])
        abstract = data.get("abstract", "")
        outline = data.get("outline", "")
        # 指标1：引用规范
        citation_score = self._score_citation_format(references)
        result.indicators["citation_format"] = citation_score
        # 指标2：参考文献完整性
        ref_score = self._score_reference_completeness(references)
        result.indicators["reference_completeness"] = ref_score
        # 指标3：术语准确性（简单实现）
        terminology_score = self._score_terminology(abstract)
        result.indicators["terminology_accuracy"] = terminology_score
        # 指标4：结构规范
        structure_score = self._score_structure(outline)
        result.indicators["structure_compliance"] = structure_score
        # 指标5：语言正式性
        language_score = self._score_language_formality(abstract)
        result.indicators["language_formality"] = language_score
        # 综合
        result.score = (
            citation_score * 0.25
            + ref_score * 0.25
            + terminology_score * 0.2
            + structure_score * 0.2
            + language_score * 0.1
        )
        result.weighted_score = result.score * result.weight
        # 优势与不足
        if citation_score >= 80:
            result.strengths.append("引用格式规范")
        if ref_score >= 80:
            result.strengths.append("参考文献完整")
        if language_score < 60:
            result.weaknesses.append("语言不够正式")
        if structure_score < 60:
            result.weaknesses.append("结构不符合规范")
        # 建议
        if citation_score < 70:
            result.suggestions.append("规范引用格式，确保统一")
        if ref_score < 70:
            result.suggestions.append("补充完整的参考文献信息")
        return result

    def _score_citation_format(self, references: list[Any]) -> float:
        """评分引用格式。"""
        if not references:
            return 30.0
        score = 70.0
        # 检查格式一致性
        formats_found = set()
        for ref in references[:10]:
            ref_text = ref if isinstance(ref, str) else str(ref)
            if re.search(r"\(\w+,\s*\d{4}\)", ref_text):
                formats_found.add("apa")
            if re.search(r"\[\d+\]", ref_text):
                formats_found.add("numbered")
            if "期刊" in ref_text or "Journal" in ref_text:
                formats_found.add("journal")
        if len(formats_found) == 1:
            score += 20  # 格式统一
        elif len(formats_found) > 2:
            score -= 20  # 格式混乱
        return min(100, max(0, score))

    def _score_reference_completeness(self, references: list[Any]) -> float:
        """评分参考文献完整性。"""
        if not references:
            return 30.0
        complete_count = 0
        for ref in references:
            ref_text = ref if isinstance(ref, str) else str(ref)
            # 检查是否含作者、年份、标题
            has_author = bool(re.search(r"[A-Za-z\u4e00-\u9fff]{2,}", ref_text))
            has_year = bool(re.search(r"\b(19|20)\d{2}\b", ref_text))
            has_title = len(ref_text) > 20
            if has_author and has_year and has_title:
                complete_count += 1
        ratio = complete_count / len(references) if references else 0
        return min(100, ratio * 100)

    def _score_terminology(self, text: str) -> float:
        """评分术语准确性（简单实现）。"""
        if not text:
            return 50.0
        score = 70.0
        # 检查是否使用专业术语
        professional_terms = re.findall(r"[A-Z]{2,}|[a-z]{4,}", text)
        if len(professional_terms) >= 3:
            score += 15
        # 检查口语化表达
        informal_words = ["很好", "非常", "特别", "挺", "蛮"]
        informal_count = sum(1 for w in informal_words if w in text)
        if informal_count > 0:
            score -= informal_count * 10
        return min(100, max(0, score))

    def _score_structure(self, outline: str) -> float:
        """评分结构规范性。"""
        if not outline:
            return 40.0
        score = 60.0
        # 检查是否有标准章节
        if re.search(r"第[一二三四五六七八九十]+章", outline):
            score += 20
        if "文献综述" in outline or "研究现状" in outline:
            score += 10
        if "研究方法" in outline or "研究设计" in outline:
            score += 10
        return min(100, score)

    def _score_language_formality(self, text: str) -> float:
        """评分语言正式性。"""
        if not text:
            return 50.0
        score = 70.0
        # 检查第一人称
        if "我" in text and "本文" not in text and "本研究" not in text:
            score -= 15
        # 检查口语词
        informal = ["觉得", "感觉", "好像", "大概", "差不多"]
        for w in informal:
            if w in text:
                score -= 10
        # 检查学术表达
        if any(kw in text for kw in ["本文", "本研究", "研究表明", "结果显示"]):
            score += 15
        return min(100, max(0, score))


# ===== 逻辑性评估器 =====


class LogicAssessor:
    """逻辑性评估器。"""

    def assess(self, data: dict[str, Any]) -> DimensionScore:
        """评估逻辑性。"""
        result = DimensionScore(
            dimension=QualityDimension.LOGIC,
            weight=DEFAULT_DIMENSION_WEIGHTS[QualityDimension.LOGIC],
        )
        outline = data.get("outline", "")
        abstract = data.get("abstract", "")
        research_content = data.get("research_content", [])
        # 指标1：结构逻辑
        structure_score = self._score_structure_logic(outline)
        result.indicators["structure_logic"] = structure_score
        # 指标2：论证逻辑
        argument_score = self._score_argument_logic(abstract)
        result.indicators["argument_logic"] = argument_score
        # 指标3：内容连贯性
        coherence_score = self._score_coherence(research_content)
        result.indicators["content_coherence"] = coherence_score
        # 指标4：因果清晰度
        causal_score = self._score_causal_clarity(abstract)
        result.indicators["causal_clarity"] = causal_score
        # 综合
        result.score = (
            structure_score * 0.3
            + argument_score * 0.3
            + coherence_score * 0.2
            + causal_score * 0.2
        )
        result.weighted_score = result.score * result.weight
        if structure_score >= 80:
            result.strengths.append("结构逻辑清晰")
        if argument_score < 60:
            result.weaknesses.append("论证逻辑不够严密")
        if coherence_score < 60:
            result.weaknesses.append("内容连贯性不足")
        if structure_score < 70:
            result.suggestions.append("优化章节结构，增强逻辑递进")
        if argument_score < 70:
            result.suggestions.append("加强论证链条，确保逻辑严密")
        return result

    def _score_structure_logic(self, outline: str) -> float:
        """评分结构逻辑。"""
        if not outline:
            return 40.0
        score = 60.0
        lines = [l.strip() for l in outline.split("\n") if l.strip()]
        # 检查章节顺序
        chapter_titles = [l for l in lines if re.match(r"^第[一二三四五六七八九十]+章", l)]
        if len(chapter_titles) >= 3:
            score += 15
        # 检查是否有递进关系
        if any(kw in outline for kw in ["基础", "理论", "方法", "应用", "结论"]):
            score += 15
        # 检查是否有逻辑连接
        if any(kw in outline for kw in ["基于", "在此基础上", "进一步", "因此"]):
            score += 10
        return min(100, score)

    def _score_argument_logic(self, abstract: str) -> float:
        """评分论证逻辑。"""
        if not abstract:
            return 40.0
        score = 60.0
        # 检查是否有问题-方法-结果结构
        has_problem = any(kw in abstract for kw in ["问题", "挑战", "不足"])
        has_method = any(kw in abstract for kw in ["方法", "采用", "通过", "基于"])
        has_result = any(kw in abstract for kw in ["结果", "发现", "表明", "显示"])
        if has_problem and has_method and has_result:
            score += 30
        elif has_problem and has_method:
            score += 20
        elif has_method and has_result:
            score += 15
        # 检查逻辑连接词
        connectors = ["因此", "所以", "由于", "因为", "从而", "进而", "由此"]
        connector_count = sum(1 for c in connectors if c in abstract)
        score += min(10, connector_count * 5)
        return min(100, score)

    def _score_coherence(self, research_content: list[Any]) -> float:
        """评分内容连贯性。"""
        if not research_content:
            return 50.0
        score = 70.0
        # 检查内容条目数量
        if len(research_content) >= 3:
            score += 15
        # 检查是否有递进关系
        content_text = " ".join(str(c) for c in research_content)
        if any(kw in content_text for kw in ["首先", "其次", "然后", "最后", "此外"]):
            score += 15
        return min(100, score)

    def _score_causal_clarity(self, abstract: str) -> float:
        """评分因果清晰度。"""
        if not abstract:
            return 50.0
        score = 60.0
        causal_words = ["导致", "引起", "使得", "促使", "因为", "由于", "因此", "所以"]
        count = sum(1 for w in causal_words if w in abstract)
        if count >= 2:
            score += 25
        elif count >= 1:
            score += 15
        return min(100, score)


# ===== 实用性评估器 =====


class PracticalityAssessor:
    """实用性评估器。"""

    def assess(self, data: dict[str, Any]) -> DimensionScore:
        """评估实用性。"""
        result = DimensionScore(
            dimension=QualityDimension.PRACTICALITY,
            weight=DEFAULT_DIMENSION_WEIGHTS[QualityDimension.PRACTICALITY],
        )
        significance = data.get("research_significance", {})
        if isinstance(significance, str):
            practical_text = significance
        elif isinstance(significance, dict):
            practical_text = significance.get("practical", "")
        else:
            practical_text = str(significance)
        feasibility = data.get("feasibility_analysis", "")
        # 指标1：实践意义
        practical_score = self._score_practical_significance(practical_text)
        result.indicators["practical_significance"] = practical_score
        # 指标2：可行性
        feasibility_score = self._score_feasibility(feasibility)
        result.indicators["feasibility"] = feasibility_score
        # 指标3：应用前景
        application_score = self._score_application_prospect(practical_text, feasibility)
        result.indicators["application_prospect"] = application_score
        # 指标4：成果转化潜力
        transform_score = self._score_transformation_potential(data)
        result.indicators["transformation_potential"] = transform_score
        # 综合
        result.score = (
            practical_score * 0.3
            + feasibility_score * 0.3
            + application_score * 0.2
            + transform_score * 0.2
        )
        result.weighted_score = result.score * result.weight
        if practical_score >= 80:
            result.strengths.append("实践意义明确")
        if feasibility_score >= 80:
            result.strengths.append("可行性高")
        if practical_score < 60:
            result.weaknesses.append("实践意义不明确")
        if feasibility_score < 60:
            result.weaknesses.append("可行性不足")
        if practical_score < 70:
            result.suggestions.append("明确研究的实践价值与应用场景")
        if feasibility_score < 70:
            result.suggestions.append("加强可行性分析，确保研究可落地")
        return result

    def _score_practical_significance(self, text: str) -> float:
        """评分实践意义。"""
        if not text:
            return 30.0
        score = 60.0
        if any(kw in text for kw in ["应用", "实践", "实际", "现实"]):
            score += 20
        if any(kw in text for kw in ["解决", "改善", "优化", "提升"]):
            score += 15
        if len(text) >= 100:
            score += 5
        return min(100, score)

    def _score_feasibility(self, text: str) -> float:
        """评分可行性。"""
        if not text:
            return 40.0
        score = 60.0
        # 检查是否涵盖关键维度
        dimensions = 0
        for dim_keywords in [
            ["技术", "方法", "工具"],
            ["数据", "样本", "资料"],
            ["时间", "周期", "进度"],
            ["经费", "资源", "设备"],
        ]:
            if any(kw in text for kw in dim_keywords):
                dimensions += 1
        score += dimensions * 8
        if len(text) >= 100:
            score += 8
        return min(100, score)

    def _score_application_prospect(self, text1: str, text2: str) -> float:
        """评分应用前景。"""
        combined = text1 + " " + text2
        score = 60.0
        if any(kw in combined for kw in ["推广", "应用前景", "产业", "行业", "领域"]):
            score += 25
        if any(kw in combined for kw in ["转化", "落地", "实施", "部署"]):
            score += 15
        return min(100, score)

    def _score_transformation_potential(self, data: dict[str, Any]) -> float:
        """评分成果转化潜力。"""
        score = 50.0
        method = data.get("method", "")
        if any(kw in method for kw in ["实验", "原型", "系统", "平台"]):
            score += 25
        differentiation = data.get("differentiation", "")
        if any(kw in differentiation for kw in ["应用", "实践", "落地"]):
            score += 25
        return min(100, score)


# ===== 完整性评估器 =====


class CompletenessAssessor:
    """完整性评估器。"""

    REQUIRED_FIELDS = [
        "title", "abstract", "outline", "references",
        "method", "feasibility_analysis", "differentiation",
        "research_significance", "inspiration_source",
    ]

    def assess(self, data: dict[str, Any]) -> DimensionScore:
        """评估完整性。"""
        result = DimensionScore(
            dimension=QualityDimension.COMPLETENESS,
            weight=DEFAULT_DIMENSION_WEIGHTS[QualityDimension.COMPLETENESS],
        )
        # 指标1：必填字段完整度
        field_score = self._score_required_fields(data)
        result.indicators["required_fields"] = field_score
        # 指标2：内容充实度
        content_score = self._score_content_richness(data)
        result.indicators["content_richness"] = content_score
        # 综合
        result.score = field_score * 0.6 + content_score * 0.4
        result.weighted_score = result.score * result.weight
        if field_score >= 90:
            result.strengths.append("字段完整")
        if field_score < 70:
            result.weaknesses.append("部分必填字段缺失")
        if content_score < 60:
            result.weaknesses.append("内容不够充实")
        if field_score < 80:
            missing = self._find_missing_fields(data)
            result.suggestions.append(f"补充缺失字段：{', '.join(missing)}")
        return result

    def _score_required_fields(self, data: dict[str, Any]) -> float:
        """评分必填字段完整度。"""
        total = len(self.REQUIRED_FIELDS)
        present = 0
        for field_name in self.REQUIRED_FIELDS:
            value = data.get(field_name)
            if value is not None and (
                (isinstance(value, str) and value.strip())
                or (isinstance(value, (list, dict)) and value)
            ):
                present += 1
        return present / total * 100 if total > 0 else 0

    def _find_missing_fields(self, data: dict[str, Any]) -> list[str]:
        """找出缺失字段。"""
        missing: list[str] = []
        for field_name in self.REQUIRED_FIELDS:
            value = data.get(field_name)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing.append(field_name)
        return missing

    def _score_content_richness(self, data: dict[str, Any]) -> float:
        """评分内容充实度。"""
        score = 50.0
        abstract = data.get("abstract", "")
        if abstract and _count_words(abstract) >= 200:
            score += 15
        outline = data.get("outline", "")
        if outline and len(outline.split("\n")) >= 5:
            score += 15
        references = data.get("references", [])
        if references and len(references) >= 20:
            score += 10
        feasibility = data.get("feasibility_analysis", "")
        if feasibility and _count_words(feasibility) >= 100:
            score += 10
        return min(100, score)


# ===== 表达清晰度评估器 =====


class ClarityAssessor:
    """表达清晰度评估器。"""

    def assess(self, data: dict[str, Any]) -> DimensionScore:
        """评估表达清晰度。"""
        result = DimensionScore(
            dimension=QualityDimension.CLARITY,
            weight=DEFAULT_DIMENSION_WEIGHTS[QualityDimension.CLARITY],
        )
        title = data.get("title", "")
        abstract = data.get("abstract", "")
        # 指标1：标题清晰度
        title_score = self._score_title_clarity(title)
        result.indicators["title_clarity"] = title_score
        # 指标2：摘要清晰度
        abstract_score = self._score_abstract_clarity(abstract)
        result.indicators["abstract_clarity"] = abstract_score
        # 指标3：语言简洁度
        conciseness_score = self._score_conciseness(abstract)
        result.indicators["conciseness"] = conciseness_score
        # 综合
        result.score = (
            title_score * 0.3
            + abstract_score * 0.4
            + conciseness_score * 0.3
        )
        result.weighted_score = result.score * result.weight
        if title_score >= 80:
            result.strengths.append("标题清晰明确")
        if abstract_score < 60:
            result.weaknesses.append("摘要表达不够清晰")
        if conciseness_score < 60:
            result.weaknesses.append("语言不够简洁")
        if abstract_score < 70:
            result.suggestions.append("优化摘要表达，突出核心内容")
        return result

    def _score_title_clarity(self, title: str) -> float:
        """评分标题清晰度。"""
        if not title:
            return 30.0
        score = 70.0
        if 10 <= len(title) <= 25:
            score += 20
        if "：" in title or "——" in title:
            score += 10  # 副标题增强清晰度
        return min(100, score)

    def _score_abstract_clarity(self, abstract: str) -> float:
        """评分摘要清晰度。"""
        if not abstract:
            return 40.0
        score = 60.0
        # 检查是否有明确陈述
        if any(kw in abstract for kw in ["本文", "本研究", "本研究提出"]):
            score += 20
        # 检查句子长度（避免过长）
        sentences = re.split(r"[。！？\.!\?]+", abstract)
        avg_length = sum(len(s) for s in sentences) / max(len(sentences), 1)
        if avg_length <= 50:
            score += 10
        elif avg_length <= 80:
            score += 5
        else:
            score -= 10
        return min(100, max(0, score))

    def _score_conciseness(self, text: str) -> float:
        """评分语言简洁度。"""
        if not text:
            return 50.0
        score = 70.0
        # 检查冗余表达
        redundant = ["进行了", "做出了", "实现了", "完成了"]
        for w in redundant:
            if w in text:
                score -= 5
        # 检查重复词
        words = re.findall(r"[\u4e00-\u9fff]+", text)
        word_freq = defaultdict(int)
        for w in words:
            word_freq[w] += 1
        repeats = sum(1 for c in word_freq.values() if c > 3)
        score -= repeats * 5
        return min(100, max(0, score))


# ===== 方法论评估器 =====


class MethodologyAssessor:
    """方法论评估器。"""

    def assess(self, data: dict[str, Any]) -> DimensionScore:
        """评估方法论。"""
        result = DimensionScore(
            dimension=QualityDimension.METHODOLOGY,
            weight=DEFAULT_DIMENSION_WEIGHTS[QualityDimension.METHODOLOGY],
        )
        method = data.get("method", "")
        method_detail = data.get("method_detail", "")
        # 指标1：方法适当性
        appropriateness_score = self._score_method_appropriateness(method, data)
        result.indicators["method_appropriateness"] = appropriateness_score
        # 指标2：方法描述详细度
        detail_score = self._score_method_detail(method_detail)
        result.indicators["method_detail"] = detail_score
        # 指标3：方法严谨性
        rigor_score = self._score_method_rigor(method, method_detail)
        result.indicators["method_rigor"] = rigor_score
        # 综合
        result.score = (
            appropriateness_score * 0.4
            + detail_score * 0.3
            + rigor_score * 0.3
        )
        result.weighted_score = result.score * result.weight
        if appropriateness_score >= 80:
            result.strengths.append("研究方法选择适当")
        if detail_score < 60:
            result.weaknesses.append("方法描述不够详细")
        if rigor_score < 60:
            result.weaknesses.append("方法严谨性不足")
        if detail_score < 70:
            result.suggestions.append("详细描述研究方法的设计与实施")
        return result

    def _score_method_appropriateness(self, method: str, data: dict[str, Any]) -> float:
        """评分方法适当性。"""
        if not method:
            return 30.0
        score = 70.0
        # 检查方法与研究问题匹配
        title = data.get("title", "")
        if any(kw in title for kw in ["影响", "关系", "因素"]) and "回归" in method:
            score += 20
        if any(kw in title for kw in ["机制", "过程", "体验"]) and any(
            kw in method for kw in ["访谈", "案例", "民族志"]
        ):
            score += 20
        return min(100, score)

    def _score_method_detail(self, detail: str) -> float:
        """评分方法描述详细度。"""
        if not detail:
            return 30.0
        score = 60.0
        word_count = _count_words(detail)
        if word_count >= 200:
            score += 25
        elif word_count >= 100:
            score += 15
        # 检查是否含关键要素
        elements = ["样本", "数据", "工具", "步骤", "分析"]
        found = sum(1 for e in elements if e in detail)
        score += found * 3
        return min(100, score)

    def _score_method_rigor(self, method: str, detail: str) -> float:
        """评分方法严谨性。"""
        score = 60.0
        combined = method + " " + detail
        # 检查是否提及信效度
        if any(kw in combined for kw in ["信度", "效度", "validity", "reliability"]):
            score += 20
        # 检查是否提及控制变量
        if any(kw in combined for kw in ["控制", "对照", "随机"]):
            score += 10
        # 检查是否提及伦理
        if any(kw in combined for kw in ["伦理", "知情同意", "匿名"]):
            score += 10
        return min(100, score)


# ===== 影响力评估器 =====


class ImpactAssessor:
    """影响力评估器。"""

    def assess(self, data: dict[str, Any]) -> DimensionScore:
        """评估影响力。"""
        result = DimensionScore(
            dimension=QualityDimension.IMPACT,
            weight=DEFAULT_DIMENSION_WEIGHTS[QualityDimension.IMPACT],
        )
        significance = data.get("research_significance", {})
        if isinstance(significance, dict):
            theoretical = significance.get("theoretical", "")
            practical = significance.get("practical", "")
        else:
            theoretical = str(significance)
            practical = ""
        differentiation = data.get("differentiation", "")
        # 指标1：理论影响
        theoretical_score = self._score_theoretical_impact(theoretical, differentiation)
        result.indicators["theoretical_impact"] = theoretical_score
        # 指标2：实践影响
        practical_score = self._score_practical_impact(practical)
        result.indicators["practical_impact"] = practical_score
        # 指标3：领域贡献
        field_score = self._score_field_contribution(data)
        result.indicators["field_contribution"] = field_score
        # 综合
        result.score = (
            theoretical_score * 0.4
            + practical_score * 0.4
            + field_score * 0.2
        )
        result.weighted_score = result.score * result.weight
        if theoretical_score >= 80:
            result.strengths.append("理论贡献突出")
        if practical_score >= 80:
            result.strengths.append("实践价值显著")
        if theoretical_score < 60 and practical_score < 60:
            result.weaknesses.append("影响力不足")
        if theoretical_score < 70:
            result.suggestions.append("明确研究的理论贡献")
        return result

    def _score_theoretical_impact(self, theoretical: str, differentiation: str) -> float:
        """评分理论影响。"""
        score = 50.0
        combined = theoretical + " " + differentiation
        if any(kw in combined for kw in ["理论", "框架", "模型", "概念"]):
            score += 25
        if any(kw in combined for kw in ["拓展", "丰富", "完善", "推进"]):
            score += 15
        if any(kw in combined for kw in ["突破", "创新", "颠覆"]):
            score += 10
        return min(100, score)

    def _score_practical_impact(self, practical: str) -> float:
        """评分实践影响。"""
        if not practical:
            return 40.0
        score = 50.0
        if any(kw in practical for kw in ["解决", "改善", "优化", "提升"]):
            score += 25
        if any(kw in practical for kw in ["应用", "推广", "产业", "行业"]):
            score += 15
        if any(kw in practical for kw in ["政策", "决策", "管理"]):
            score += 10
        return min(100, score)

    def _score_field_contribution(self, data: dict[str, Any]) -> float:
        """评分领域贡献。"""
        score = 50.0
        references = data.get("references", [])
        if references and len(references) >= 30:
            score += 20
        differentiation = data.get("differentiation", "")
        if differentiation and len(differentiation) >= 100:
            score += 15
        if any(kw in differentiation for kw in ["填补", "空白", "首次"]):
            score += 15
        return min(100, score)


# ===== 质量评估器主类 =====


class QualityAssessor:
    """质量评估器主类。

    整合多个维度评估器，提供：
        - 多维度质量评估（创新性/规范性/逻辑性/实用性等）
        - 评估指标体系管理
        - 权重配置
        - 评分模型
        - 评估报告生成
        - 雷达图数据
        - 改进建议
        - 历史评估对比
        - 趋势分析
        - 标杆对比

    线程安全：所有公共方法通过 RLock 保护。
    """

    def __init__(self) -> None:
        """初始化质量评估器，注册内置维度评估器。"""
        self._lock = threading.RLock()
        # 维度评估器
        self._assessors: dict[str, Callable[[dict[str, Any]], DimensionScore]] = {
            QualityDimension.INNOVATION: InnovationAssessor().assess,
            QualityDimension.ACADEMIC_RIGOR: AcademicRigorAssessor().assess,
            QualityDimension.LOGIC: LogicAssessor().assess,
            QualityDimension.PRACTICALITY: PracticalityAssessor().assess,
            QualityDimension.COMPLETENESS: CompletenessAssessor().assess,
            QualityDimension.CLARITY: ClarityAssessor().assess,
            QualityDimension.METHODOLOGY: MethodologyAssessor().assess,
            QualityDimension.IMPACT: ImpactAssessor().assess,
        }
        # 维度权重
        self._weights: dict[str, float] = dict(DEFAULT_DIMENSION_WEIGHTS)
        # 自定义指标
        self._custom_indicators: dict[str, list[AssessmentIndicator]] = defaultdict(list)
        # 评估历史
        self._history: list[QualityReport] = []
        # 标杆数据
        self._benchmarks: dict[str, QualityReport] = {}

    def set_dimension_weight(self, dimension: str, weight: float) -> None:
        """设置维度权重。"""
        with self._lock:
            self._weights[dimension] = max(0.0, min(1.0, weight))

    def register_assessor(self, dimension: str,
                          assessor: Callable[[dict[str, Any]], DimensionScore]) -> None:
        """注册维度评估器。"""
        with self._lock:
            self._assessors[dimension] = assessor

    def add_custom_indicator(self, dimension: str, indicator: AssessmentIndicator) -> None:
        """添加自定义评估指标。"""
        with self._lock:
            self._custom_indicators[dimension].append(indicator)

    def assess(self, thesis_data: dict[str, Any],
               dimensions: Optional[list[str]] = None) -> QualityReport:
        """执行质量评估。

        Args:
            thesis_data: 论题数据字典。
            dimensions: 指定评估的维度列表。None 表示全部。

        Returns:
            质量评估报告。
        """
        with self._lock:
            report = QualityReport(
                id=_new_id("qreport"),
                thesis_id=thesis_data.get("id", ""),
                timestamp=_now_iso(),
            )
            target_dimensions = dimensions or list(self._assessors.keys())
            # 归一化权重
            active_weights = {
                d: self._weights.get(d, 0.1) for d in target_dimensions
            }
            total_weight = sum(active_weights.values())
            if total_weight == 0:
                total_weight = 1.0
            normalized_weights = {
                d: w / total_weight for d, w in active_weights.items()
            }
            # 执行各维度评估
            overall_score = 0.0
            for dim in target_dimensions:
                assessor = self._assessors.get(dim)
                if assessor is None:
                    continue
                try:
                    result = assessor(thesis_data)
                except Exception as e:
                    result = DimensionScore(
                        dimension=dim,
                        score=0.0,
                        weight=normalized_weights.get(dim, 0.1),
                        weaknesses=[f"评估异常: {e}"],
                    )
                # 应用归一化权重
                result.weight = normalized_weights.get(dim, 0.1)
                result.weighted_score = result.score * result.weight
                # 执行自定义指标
                for indicator in self._custom_indicators.get(dim, []):
                    indicator_score = indicator.evaluate(thesis_data)
                    result.indicators[indicator.name] = indicator_score
                report.dimension_scores[dim] = result
                overall_score += result.weighted_score
            report.overall_score = overall_score
            report.grade = _score_to_grade(overall_score)
            # 生成雷达图数据
            report.radar_data = self._generate_radar_data(report.dimension_scores)
            # 汇总优势与不足
            report.strengths = self._collect_strengths(report.dimension_scores)
            report.weaknesses = self._collect_weaknesses(report.dimension_scores)
            report.suggestions = self._collect_suggestions(report.dimension_scores)
            # 标杆对比
            if self._benchmarks:
                report.benchmark_comparison = self._compare_with_benchmark(report)
            # 保存历史
            self._history.append(report)
            return report

    def _generate_radar_data(self, dimension_scores: dict[str, DimensionScore]) -> dict[str, Any]:
        """生成雷达图数据。"""
        labels: list[str] = []
        values: list[float] = []
        for dim, score in dimension_scores.items():
            labels.append(DIMENSION_NAMES.get(dim, dim))
            values.append(round(score.score, 2))
        return {
            "labels": labels,
            "values": values,
            "max_value": 100,
            "datasets": [
                {
                    "label": "当前评估",
                    "data": values,
                    "fill": True,
                }
            ],
        }

    def _collect_strengths(self, dimension_scores: dict[str, DimensionScore]) -> list[str]:
        """收集优势点。"""
        strengths: list[str] = []
        for dim, result in dimension_scores.items():
            dim_name = DIMENSION_NAMES.get(dim, dim)
            for s in result.strengths:
                strengths.append(f"【{dim_name}】{s}")
        return strengths

    def _collect_weaknesses(self, dimension_scores: dict[str, DimensionScore]) -> list[str]:
        """收集不足点。"""
        weaknesses: list[str] = []
        for dim, result in dimension_scores.items():
            dim_name = DIMENSION_NAMES.get(dim, dim)
            for w in result.weaknesses:
                weaknesses.append(f"【{dim_name}】{w}")
        return weaknesses

    def _collect_suggestions(self, dimension_scores: dict[str, DimensionScore]) -> list[str]:
        """收集改进建议。"""
        suggestions: list[str] = []
        # 按维度评分升序，优先改进低分维度
        sorted_dims = sorted(dimension_scores.items(), key=lambda x: x[1].score)
        for dim, result in sorted_dims:
            dim_name = DIMENSION_NAMES.get(dim, dim)
            for s in result.suggestions:
                suggestions.append(f"【{dim_name}】{s}")
        return suggestions

    # ===== 标杆管理 =====

    def set_benchmark(self, benchmark_id: str, report: QualityReport) -> None:
        """设置标杆评估报告。"""
        with self._lock:
            self._benchmarks[benchmark_id] = report

    def _compare_with_benchmark(self, report: QualityReport) -> dict[str, Any]:
        """与标杆对比。"""
        comparisons: dict[str, Any] = {}
        for bm_id, bm_report in self._benchmarks.items():
            dimension_diff: dict[str, float] = {}
            for dim, result in report.dimension_scores.items():
                bm_result = bm_report.dimension_scores.get(dim)
                if bm_result:
                    dimension_diff[dim] = round(result.score - bm_result.score, 2)
            comparisons[bm_id] = {
                "benchmark_score": bm_report.overall_score,
                "current_score": report.overall_score,
                "score_diff": round(report.overall_score - bm_report.overall_score, 2),
                "dimension_diff": dimension_diff,
            }
        return comparisons

    # ===== 历史与趋势 =====

    def get_history(self, thesis_id: Optional[str] = None,
                    limit: int = 10) -> list[QualityReport]:
        """获取评估历史。"""
        with self._lock:
            if thesis_id:
                reports = [r for r in self._history if r.thesis_id == thesis_id]
            else:
                reports = list(self._history)
            return reports[-limit:]

    def analyze_trend(self, thesis_id: str) -> dict[str, Any]:
        """分析评估趋势。

        Args:
            thesis_id: 论题 ID。

        Returns:
            趋势分析结果。
        """
        with self._lock:
            reports = [r for r in self._history if r.thesis_id == thesis_id]
            if len(reports) < 2:
                return {
                    "thesis_id": thesis_id,
                    "trend": "insufficient_data",
                    "message": "评估次数不足，无法分析趋势",
                }
            # 按时间排序
            reports.sort(key=lambda x: x.timestamp)
            scores = [r.overall_score for r in reports]
            # 计算趋势
            if len(scores) >= 2:
                recent_change = scores[-1] - scores[-2]
                if recent_change > 5:
                    trend = "improving"
                elif recent_change < -5:
                    trend = "declining"
                else:
                    trend = "stable"
            else:
                trend = "stable"
            # 各维度趋势
            dimension_trends: dict[str, list[float]] = defaultdict(list)
            for r in reports:
                for dim, result in r.dimension_scores.items():
                    dimension_trends[dim].append(result.score)
            return {
                "thesis_id": thesis_id,
                "trend": trend,
                "assessment_count": len(reports),
                "score_history": scores,
                "latest_score": scores[-1],
                "best_score": max(scores),
                "worst_score": min(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
                "improvement": round(scores[-1] - scores[0], 2),
                "dimension_trends": {
                    dim: history for dim, history in dimension_trends.items()
                },
                "first_assessment": reports[0].timestamp,
                "last_assessment": reports[-1].timestamp,
            }

    def compare_assessments(self, report_id1: str, report_id2: str) -> dict[str, Any]:
        """对比两次评估。"""
        with self._lock:
            r1 = next((r for r in self._history if r.id == report_id1), None)
            r2 = next((r for r in self._history if r.id == report_id2), None)
            if r1 is None or r2 is None:
                return {"error": "报告不存在"}
            dimension_comparison: dict[str, dict[str, float]] = {}
            for dim in r1.dimension_scores:
                s1 = r1.dimension_scores[dim].score
                s2 = r2.dimension_scores.get(dim, DimensionScore()).score
                dimension_comparison[dim] = {
                    "score1": round(s1, 2),
                    "score2": round(s2, 2),
                    "change": round(s2 - s1, 2),
                    "improved": s2 > s1,
                }
            return {
                "report1": {
                    "id": r1.id,
                    "timestamp": r1.timestamp,
                    "overall_score": r1.overall_score,
                    "grade": r1.grade,
                },
                "report2": {
                    "id": r2.id,
                    "timestamp": r2.timestamp,
                    "overall_score": r2.overall_score,
                    "grade": r2.grade,
                },
                "overall_change": round(r2.overall_score - r1.overall_score, 2),
                "grade_change": r2.grade if r2.grade == r1.grade else f"{r1.grade} -> {r2.grade}",
                "dimension_comparison": dimension_comparison,
                "improved": r2.overall_score > r1.overall_score,
            }

    # ===== 统计 =====

    def stats(self) -> dict[str, Any]:
        """返回评估器统计信息。"""
        with self._lock:
            if not self._history:
                return {
                    "total_assessments": 0,
                    "avg_score": 0.0,
                    "grade_distribution": {},
                }
            total = len(self._history)
            avg_score = sum(r.overall_score for r in self._history) / total
            grade_dist: dict[str, int] = defaultdict(int)
            for r in self._history:
                grade_dist[r.grade] += 1
            # 各维度平均分
            dimension_avg: dict[str, float] = defaultdict(float)
            dimension_count: dict[str, int] = defaultdict(int)
            for r in self._history:
                for dim, result in r.dimension_scores.items():
                    dimension_avg[dim] += result.score
                    dimension_count[dim] += 1
            dimension_stats = {
                dim: round(dimension_avg[dim] / dimension_count[dim], 2)
                for dim in dimension_avg
            }
            return {
                "total_assessments": total,
                "avg_score": round(avg_score, 2),
                "grade_distribution": dict(grade_dist),
                "dimension_avg_scores": dimension_stats,
                "benchmarks_count": len(self._benchmarks),
                "custom_indicators_count": sum(
                    len(v) for v in self._custom_indicators.values()
                ),
            }


# ===== 模块级单例 =====


_global_instance: Optional[QualityAssessor] = None
_global_lock = threading.Lock()


def get_quality_assessor() -> QualityAssessor:
    """获取全局质量评估器单例。"""
    global _global_instance
    if _global_instance is None:
        with _global_lock:
            if _global_instance is None:
                _global_instance = QualityAssessor()
    return _global_instance


def reset_quality_assessor() -> None:
    """重置全局单例（主要用于测试）。"""
    global _global_instance
    with _global_lock:
        _global_instance = None
