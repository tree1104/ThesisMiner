"""假设检验器模块

提供完整的研究假设检验能力，包括：
    - 假设形式化、假设分类、假设可测试性评估
    - 统计检验方法选择、样本量计算、功效分析
    - 检验结果解释、效应量计算、置信区间
    - 多重检验校正、贝叶斯假设检验
    - 完整的统计检验实现、决策规则

设计原则：
    1. 零外部依赖：仅使用 Python 标准库（math 模块实现统计计算）
    2. 线程安全：所有公共方法通过 RLock 保护
    3. 可持久化：基于 dataclass，支持序列化
    4. 科学严谨：基于经典统计理论与贝叶斯方法

核心数据结构：
    - Hypothesis: 假设（含原假设、备择假设、类型）
    - StatisticalTest: 统计检验（含方法、参数、结果）
    - TestResult: 检验结果（含统计量、p 值、效应量、决策）
"""
from __future__ import annotations

import math
import re
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Iterable, Optional


# ===== 常量定义 =====

# 假设类型
HYPOTHESIS_TYPES = {
    "null": "原假设（H₀）",
    "alternative": "备择假设（H₁）",
    "directional": "方向性假设",
    "non_directional": "非方向性假设",
    "research": "研究假设",
    "statistical": "统计假设",
}

# 假设方向
HYPOTHESIS_DIRECTIONS = {
    "two_tailed": "双侧检验",
    "one_tailed_greater": "单侧检验（大于）",
    "one_tailed_less": "单侧检验（小于）",
}

# 检验方法
TEST_METHODS = {
    "t_test_one_sample": "单样本 t 检验",
    "t_test_independent": "独立样本 t 检验",
    "t_test_paired": "配对样本 t 检验",
    "z_test": "Z 检验",
    "chi_square_goodness": "卡方拟合优度检验",
    "chi_square_independence": "卡方独立性检验",
    "anova_one_way": "单因素方差分析",
    "anova_two_way": "双因素方差分析",
    "mann_whitney": "Mann-Whitney U 检验",
    "wilcoxon": "Wilcoxon 符号秩检验",
    "kruskal_wallis": "Kruskal-Wallis 检验",
    "fisher_exact": "Fisher 精确检验",
    "correlation_pearson": "Pearson 相关检验",
    "correlation_spearman": "Spearman 秩相关检验",
    "regression": "回归分析",
    "proportion_test": "比例检验",
    "f_test": "F 检验",
    "levene_test": "Levene 方差齐性检验",
}

# 检验方法类别
TEST_CATEGORIES = {
    "parametric": "参数检验",
    "nonparametric": "非参数检验",
    "bayesian": "贝叶斯检验",
}

# 方法与类别映射
METHOD_CATEGORIES = {
    "t_test_one_sample": "parametric",
    "t_test_independent": "parametric",
    "t_test_paired": "parametric",
    "z_test": "parametric",
    "chi_square_goodness": "parametric",
    "chi_square_independence": "parametric",
    "anova_one_way": "parametric",
    "anova_two_way": "parametric",
    "mann_whitney": "nonparametric",
    "wilcoxon": "nonparametric",
    "kruskal_wallis": "nonparametric",
    "fisher_exact": "nonparametric",
    "correlation_pearson": "parametric",
    "correlation_spearman": "nonparametric",
    "regression": "parametric",
    "proportion_test": "parametric",
    "f_test": "parametric",
    "levene_test": "parametric",
}

# 效应量类型
EFFECT_SIZE_TYPES = {
    "cohens_d": "Cohen's d（均值差异）",
    "cohens_g": "Cohen's g（配对差异）",
    "pearson_r": "Pearson r（相关）",
    "r_squared": "R²（决定系数）",
    "eta_squared": "η²（方差分析）",
    "omega_squared": "ω²（方差分析）",
    "cramers_v": "Cramér's V（卡方）",
    "odds_ratio": "优势比（OR）",
    "hedges_g": "Hedges' g",
}

# 效应量大小解释
EFFECT_SIZE_INTERPRETATIONS = {
    "cohens_d": {
        "small": 0.2,
        "medium": 0.5,
        "large": 0.8,
    },
    "pearson_r": {
        "small": 0.1,
        "medium": 0.3,
        "large": 0.5,
    },
    "eta_squared": {
        "small": 0.01,
        "medium": 0.06,
        "large": 0.14,
    },
    "cramers_v": {
        "small": 0.1,
        "medium": 0.3,
        "large": 0.5,
    },
}

# 决策结果
DECISION_RESULTS = {
    "reject_null": "拒绝原假设",
    "fail_to_reject_null": "未能拒绝原假设",
    "inconclusive": "无法确定",
}

# 显著性水平
SIGNIFICANCE_LEVELS = [0.10, 0.05, 0.01, 0.001]

# 多重检验校正方法
CORRECTION_METHODS = {
    "bonferroni": "Bonferroni 校正",
    "holm": "Holm 校正（逐步降序）",
    "bh": "Benjamini-Hochberg（控制 FDR）",
    "by": "Benjamini-Yekutieli",
    "none": "不校正",
}

# 可测试性评估维度
TESTABILITY_DIMENSIONS = {
    "operationalizable": "可操作化（变量可测量）",
    "falsifiable": "可证伪（存在可能被拒绝的情况）",
    "measurable": "可测量（结果可量化）",
    "replicable": "可重复（他人可重复检验）",
    "specific": "具体明确（无歧义）",
    "feasible": "可行（资源与技术允许）",
}

# 数据类型
DATA_TYPES = {
    "continuous": "连续型",
    "ordinal": "有序型",
    "nominal": "名义型",
    "binary": "二分型",
    "count": "计数型",
    "ratio": "比率型",
    "interval": "区间型",
}

# 样本量计算方法
SAMPLE_SIZE_METHODS = {
    "t_test": "t 检验样本量",
    "proportion": "比例检验样本量",
    "anova": "方差分析样本量",
    "correlation": "相关分析样本量",
    "regression": "回归分析样本量",
    "chi_square": "卡方检验样本量",
}


# ===== 数据结构 =====


@dataclass
class Hypothesis:
    """假设数据结构。

    Attributes:
        id: 假设 ID。
        name: 假设名称。
        null_hypothesis: 原假设（H₀）。
        alternative_hypothesis: 备择假设（H₁）。
        hypothesis_type: 假设类型。
        direction: 检验方向。
        variables: 涉及变量列表。
        expected_effect: 预期效应方向。
        testability_score: 可测试性评分（0-1）。
        metadata: 扩展元数据。
    """

    id: str = ""
    name: str = ""
    null_hypothesis: str = ""
    alternative_hypothesis: str = ""
    hypothesis_type: str = "research"
    direction: str = "two_tailed"
    variables: list[str] = field(default_factory=list)
    expected_effect: str = ""
    testability_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "id": self.id,
            "name": self.name,
            "null_hypothesis": self.null_hypothesis,
            "alternative_hypothesis": self.alternative_hypothesis,
            "hypothesis_type": self.hypothesis_type,
            "hypothesis_type_name": HYPOTHESIS_TYPES.get(self.hypothesis_type, self.hypothesis_type),
            "direction": self.direction,
            "direction_name": HYPOTHESIS_DIRECTIONS.get(self.direction, self.direction),
            "variables": self.variables,
            "expected_effect": self.expected_effect,
            "testability_score": self.testability_score,
            "metadata": self.metadata,
        }


@dataclass
class TestResult:
    """检验结果数据结构。

    Attributes:
        id: 结果 ID。
        test_method: 检验方法。
        statistic: 检验统计量。
        p_value: p 值。
        effect_size: 效应量。
        effect_size_type: 效应量类型。
        confidence_interval: 置信区间。
        decision: 决策结果。
        significance_level: 显著性水平。
        interpretation: 结果解释。
        degrees_of_freedom: 自由度。
        metadata: 扩展元数据。
    """

    id: str = ""
    test_method: str = ""
    statistic: float = 0.0
    p_value: float = 1.0
    effect_size: float = 0.0
    effect_size_type: str = ""
    confidence_interval: tuple[float, float] = (0.0, 0.0)
    decision: str = "fail_to_reject_null"
    significance_level: float = 0.05
    interpretation: str = ""
    degrees_of_freedom: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "id": self.id,
            "test_method": self.test_method,
            "test_method_name": TEST_METHODS.get(self.test_method, self.test_method),
            "statistic": round(self.statistic, 6),
            "p_value": round(self.p_value, 6),
            "effect_size": round(self.effect_size, 6),
            "effect_size_type": self.effect_size_type,
            "effect_size_name": EFFECT_SIZE_TYPES.get(self.effect_size_type, self.effect_size_type),
            "confidence_interval": [round(self.confidence_interval[0], 6), round(self.confidence_interval[1], 6)],
            "decision": self.decision,
            "decision_name": DECISION_RESULTS.get(self.decision, self.decision),
            "significance_level": self.significance_level,
            "interpretation": self.interpretation,
            "degrees_of_freedom": self.degrees_of_freedom,
            "metadata": self.metadata,
        }

    @property
    def is_significant(self) -> bool:
        """是否统计显著。"""
        return self.p_value < self.significance_level


@dataclass
class StatisticalTest:
    """统计检验数据结构。

    Attributes:
        id: 检验 ID。
        hypothesis_id: 关联假设 ID。
        method: 检验方法。
        category: 检验类别。
        parameters: 检验参数。
        assumptions: 前提假设列表。
        result: 检验结果。
        sample_size: 样本量。
        power: 检验功效。
        created_at: 创建时间。
        metadata: 扩展元数据。
    """

    id: str = ""
    hypothesis_id: str = ""
    method: str = "t_test_one_sample"
    category: str = "parametric"
    parameters: dict[str, Any] = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)
    result: Optional[TestResult] = None
    sample_size: int = 0
    power: float = 0.0
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "id": self.id,
            "hypothesis_id": self.hypothesis_id,
            "method": self.method,
            "method_name": TEST_METHODS.get(self.method, self.method),
            "category": self.category,
            "category_name": TEST_CATEGORIES.get(self.category, self.category),
            "parameters": self.parameters,
            "assumptions": self.assumptions,
            "result": self.result.to_dict() if self.result else None,
            "sample_size": self.sample_size,
            "power": self.power,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


# ===== 主类实现 =====


class HypothesisTester:
    """假设检验器主类。

    提供假设形式化、假设分类、假设可测试性评估、统计检验方法选择、
    样本量计算、功效分析、检验结果解释、效应量计算、置信区间、
    多重检验校正、贝叶斯假设检验等能力。

    线程安全：所有公共方法通过 RLock 保护。
    """

    def __init__(self):
        """初始化假设检验器。"""
        self._lock = threading.RLock()
        self._hypotheses: dict[str, Hypothesis] = {}
        self._tests: dict[str, StatisticalTest] = {}

    # ===== 假设管理 =====

    def create_hypothesis(
        self,
        name: str,
        null_hypothesis: str,
        alternative_hypothesis: str,
        hypothesis_type: str = "research",
        direction: str = "two_tailed",
        variables: Optional[list[str]] = None,
        expected_effect: str = "",
    ) -> Hypothesis:
        """创建假设。

        Args:
            name: 假设名称。
            null_hypothesis: 原假设（H₀）。
            alternative_hypothesis: 备择假设（H₁）。
            hypothesis_type: 假设类型。
            direction: 检验方向。
            variables: 涉及变量列表。
            expected_effect: 预期效应方向。

        Returns:
            创建的 Hypothesis 实例。
        """
        with self._lock:
            if hypothesis_type not in HYPOTHESIS_TYPES:
                hypothesis_type = "research"
            if direction not in HYPOTHESIS_DIRECTIONS:
                direction = "two_tailed"
            hyp_id = f"hyp_{uuid.uuid4().hex[:10]}"
            hyp = Hypothesis(
                id=hyp_id,
                name=name,
                null_hypothesis=null_hypothesis,
                alternative_hypothesis=alternative_hypothesis,
                hypothesis_type=hypothesis_type,
                direction=direction,
                variables=variables or [],
                expected_effect=expected_effect,
            )
            # 自动评估可测试性
            hyp.testability_score = self.assess_testability(hyp)
            self._hypotheses[hyp_id] = hyp
            return hyp

    def get_hypothesis(self, hypothesis_id: str) -> Optional[Hypothesis]:
        """获取假设。"""
        with self._lock:
            return self._hypotheses.get(hypothesis_id)

    def list_hypotheses(
        self, hypothesis_type: Optional[str] = None
    ) -> list[Hypothesis]:
        """列出假设。"""
        with self._lock:
            hyps = list(self._hypotheses.values())
            if hypothesis_type:
                hyps = [h for h in hyps if h.hypothesis_type == hypothesis_type]
            return hyps

    def delete_hypothesis(self, hypothesis_id: str) -> bool:
        """删除假设。"""
        with self._lock:
            if hypothesis_id in self._hypotheses:
                del self._hypotheses[hypothesis_id]
                # 同时删除关联的检验
                to_delete = [
                    tid for tid, t in self._tests.items()
                    if t.hypothesis_id == hypothesis_id
                ]
                for tid in to_delete:
                    del self._tests[tid]
                return True
            return False

    # ===== 可测试性评估 =====

    def assess_testability(self, hypothesis: Hypothesis) -> float:
        """评估假设可测试性。

        Args:
            hypothesis: 假设实例。

        Returns:
            可测试性评分（0-1）。
        """
        scores: dict[str, float] = {}
        # 1. 可操作化：变量是否明确
        if hypothesis.variables:
            scores["operationalizable"] = min(1.0, len(hypothesis.variables) / 3.0)
        else:
            scores["operationalizable"] = 0.2
        # 2. 可证伪：备择假设是否与原假设对立
        if hypothesis.null_hypothesis and hypothesis.alternative_hypothesis:
            # 检测是否包含对立表述
            opposition_words = ["不", "非", "无", "差异", "不同", "大于", "小于", "相关"]
            has_opposition = any(
                w in hypothesis.alternative_hypothesis for w in opposition_words
            )
            scores["falsifiable"] = 0.9 if has_opposition else 0.5
        else:
            scores["falsifiable"] = 0.2
        # 3. 可测量：是否包含量化表述
        quant_words = ["显著", "差异", "相关", "影响", "效应", "大于", "小于", "等于"]
        has_quant = any(
            w in hypothesis.alternative_hypothesis for w in quant_words
        ) if hypothesis.alternative_hypothesis else False
        scores["measurable"] = 0.8 if has_quant else 0.4
        # 4. 可重复：假设是否具体
        if len(hypothesis.alternative_hypothesis) > 20:
            scores["replicable"] = 0.8
        else:
            scores["replicable"] = 0.4
        # 5. 具体明确：是否包含模糊词
        vague_words = ["可能", "也许", "大概", "似乎", "某种"]
        has_vague = any(
            w in hypothesis.alternative_hypothesis for w in vague_words
        ) if hypothesis.alternative_hypothesis else True
        scores["specific"] = 0.3 if has_vague else 0.9
        # 6. 可行性：变量数量适中
        var_count = len(hypothesis.variables)
        if 1 <= var_count <= 5:
            scores["feasible"] = 0.9
        elif var_count <= 10:
            scores["feasible"] = 0.6
        else:
            scores["feasible"] = 0.3
        # 加权平均
        weights = {
            "operationalizable": 0.2,
            "falsifiable": 0.25,
            "measurable": 0.2,
            "replicable": 0.1,
            "specific": 0.15,
            "feasible": 0.1,
        }
        overall = sum(scores[d] * weights[d] for d in scores)
        return round(overall, 4)

    def get_testability_detail(
        self, hypothesis_id: str
    ) -> dict[str, Any]:
        """获取可测试性详情。

        Args:
            hypothesis_id: 假设 ID。

        Returns:
            可测试性详情字典。
        """
        with self._lock:
            hyp = self._hypotheses.get(hypothesis_id)
            if not hyp:
                return {}
            score = hyp.testability_score
            if score >= 0.8:
                level = "高"
            elif score >= 0.6:
                level = "中"
            elif score >= 0.4:
                level = "偏低"
            else:
                level = "低"
            return {
                "hypothesis_id": hypothesis_id,
                "name": hyp.name,
                "overall_score": score,
                "level": level,
                "dimensions": {
                    dim: {
                        "name": TESTABILITY_DIMENSIONS.get(dim, dim),
                        "score": self._score_dimension(hyp, dim),
                    }
                    for dim in TESTABILITY_DIMENSIONS
                },
                "suggestions": self._generate_testability_suggestions(hyp),
            }

    def _score_dimension(self, hyp: Hypothesis, dim: str) -> float:
        """评估单个维度得分。"""
        if dim == "operationalizable":
            return min(1.0, len(hyp.variables) / 3.0) if hyp.variables else 0.2
        if dim == "falsifiable":
            if hyp.null_hypothesis and hyp.alternative_hypothesis:
                opposition_words = ["不", "非", "无", "差异", "不同"]
                has = any(w in hyp.alternative_hypothesis for w in opposition_words)
                return 0.9 if has else 0.5
            return 0.2
        if dim == "measurable":
            quant_words = ["显著", "差异", "相关", "影响", "效应"]
            has = any(w in hyp.alternative_hypothesis for w in quant_words) if hyp.alternative_hypothesis else False
            return 0.8 if has else 0.4
        if dim == "replicable":
            return 0.8 if len(hyp.alternative_hypothesis) > 20 else 0.4
        if dim == "specific":
            vague_words = ["可能", "也许", "大概", "似乎"]
            has = any(w in hyp.alternative_hypothesis for w in vague_words) if hyp.alternative_hypothesis else True
            return 0.3 if has else 0.9
        if dim == "feasible":
            vc = len(hyp.variables)
            if 1 <= vc <= 5:
                return 0.9
            elif vc <= 10:
                return 0.6
            return 0.3
        return 0.5

    def _generate_testability_suggestions(self, hyp: Hypothesis) -> list[str]:
        """生成可测试性改进建议。"""
        suggestions: list[str] = []
        if not hyp.variables:
            suggestions.append("明确涉及的变量，使其可操作化")
        if not hyp.null_hypothesis or not hyp.alternative_hypothesis:
            suggestions.append("同时明确原假设与备择假设")
        if hyp.alternative_hypothesis:
            vague_words = ["可能", "也许", "大概", "似乎"]
            if any(w in hyp.alternative_hypothesis for w in vague_words):
                suggestions.append("去除模糊表述，使假设更具体")
            quant_words = ["显著", "差异", "相关", "影响"]
            if not any(w in hyp.alternative_hypothesis for w in quant_words):
                suggestions.append("使用量化表述（如「显著差异」「正相关」）")
        if len(hyp.variables) > 10:
            suggestions.append("变量过多，建议聚焦核心变量")
        if not suggestions:
            suggestions.append("假设可测试性良好")
        return suggestions

    # ===== 检验方法选择 =====

    def recommend_test_method(
        self,
        hypothesis_id: str,
        data_type: str = "continuous",
        group_count: int = 2,
        paired: bool = False,
        normal_distribution: bool = True,
        equal_variance: bool = True,
    ) -> list[dict[str, Any]]:
        """推荐统计检验方法。

        Args:
            hypothesis_id: 假设 ID。
            data_type: 数据类型。
            group_count: 组数。
            paired: 是否配对。
            normal_distribution: 是否正态分布。
            equal_variance: 方差是否齐性。

        Returns:
            推荐方法列表（含方法名、适用性、理由）。
        """
        with self._lock:
            hyp = self._hypotheses.get(hypothesis_id)
            if not hyp:
                return []
            scored: list[tuple[float, dict[str, Any]]] = []
            for method_id, method_name in TEST_METHODS.items():
                score = 0.0
                reasons: list[str] = []
                category = METHOD_CATEGORIES.get(method_id, "parametric")
                # 正态分布匹配
                if normal_distribution and category == "parametric":
                    score += 0.3
                    reasons.append("数据正态分布，适用参数检验")
                elif not normal_distribution and category == "nonparametric":
                    score += 0.4
                    reasons.append("数据非正态，适用非参数检验")
                # 数据类型匹配
                if data_type == "continuous":
                    if method_id.startswith("t_test") or method_id.startswith("anova"):
                        score += 0.3
                        reasons.append("适用于连续型数据")
                    elif method_id in ("correlation_pearson", "regression"):
                        score += 0.3
                        reasons.append("适用于连续型变量关系")
                elif data_type in ("nominal", "binary"):
                    if "chi_square" in method_id or method_id == "fisher_exact":
                        score += 0.4
                        reasons.append("适用于分类数据")
                    elif method_id == "proportion_test":
                        score += 0.4
                        reasons.append("适用于比例数据")
                elif data_type == "ordinal":
                    if method_id in ("mann_whitney", "wilcoxon", "kruskal_wallis", "correlation_spearman"):
                        score += 0.4
                        reasons.append("适用于有序数据")
                # 组数匹配
                if group_count == 2:
                    if method_id in ("t_test_independent", "t_test_paired", "mann_whitney", "wilcoxon"):
                        score += 0.2
                        reasons.append("适用于两组比较")
                elif group_count > 2:
                    if method_id in ("anova_one_way", "kruskal_wallis"):
                        score += 0.3
                        reasons.append("适用于多组比较")
                # 配对匹配
                if paired:
                    if method_id in ("t_test_paired", "wilcoxon"):
                        score += 0.3
                        reasons.append("适用于配对设计")
                if score > 0:
                    scored.append((score, {
                        "method_id": method_id,
                        "method_name": method_name,
                        "category": category,
                        "category_name": TEST_CATEGORIES.get(category, category),
                        "score": round(score, 3),
                        "reasons": reasons,
                        "assumptions": self._get_method_assumptions(method_id),
                    }))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [s[1] for s in scored[:5]]

    def _get_method_assumptions(self, method_id: str) -> list[str]:
        """获取检验方法的前提假设。"""
        assumptions_map = {
            "t_test_one_sample": [
                "数据服从正态分布",
                "观测值独立",
                "连续型变量",
            ],
            "t_test_independent": [
                "两组数据均服从正态分布",
                "两组方差齐性",
                "观测值独立",
                "连续型变量",
            ],
            "t_test_paired": [
                "差值服从正态分布",
                "配对观测",
                "连续型变量",
            ],
            "anova_one_way": [
                "各组数据服从正态分布",
                "各组方差齐性",
                "观测值独立",
                "连续型变量",
            ],
            "chi_square_independence": [
                "期望频数 ≥ 5",
                "观测值独立",
                "分类变量",
            ],
            "mann_whitney": [
                "两组分布形状相同",
                "观测值独立",
                "至少有序变量",
            ],
            "wilcoxon": [
                "差值对称分布",
                "配对观测",
                "至少有序变量",
            ],
            "correlation_pearson": [
                "两变量服从二元正态分布",
                "线性关系",
                "连续型变量",
            ],
            "correlation_spearman": [
                "至少有序变量",
                "单调关系",
            ],
            "regression": [
                "线性关系",
                "残差独立",
                "残差正态分布",
                "同方差性",
                "无多重共线性",
            ],
        }
        return assumptions_map.get(method_id, ["观测值独立"])

    # ===== 样本量计算 =====

    def compute_sample_size(
        self,
        method: str = "t_test",
        effect_size: float = 0.5,
        alpha: float = 0.05,
        power: float = 0.8,
        group_count: int = 2,
    ) -> dict[str, Any]:
        """计算所需样本量。

        Args:
            method: 检验方法。
            effect_size: 预期效应量。
            alpha: 显著性水平。
            power: 检验功效。
            group_count: 组数。

        Returns:
            样本量计算结果。
        """
        with self._lock:
            # Z 值（近似）
            z_alpha = self._z_from_p(alpha / 2)  # 双侧
            z_beta = self._z_from_p(1 - power)
            if method == "t_test":
                # 两组比较：n = 2 * ((z_alpha + z_beta) / d)^2
                if effect_size <= 0:
                    return {"error": "效应量必须大于 0"}
                n_per_group = 2 * ((z_alpha + z_beta) / effect_size) ** 2
                n_per_group = math.ceil(n_per_group)
                total = n_per_group * group_count
                return {
                    "method": method,
                    "method_name": SAMPLE_SIZE_METHODS.get(method, method),
                    "effect_size": effect_size,
                    "alpha": alpha,
                    "power": power,
                    "n_per_group": n_per_group,
                    "total_n": total,
                    "group_count": group_count,
                }
            elif method == "proportion":
                # 比例检验：n = (z_alpha + z_beta)^2 * (p1(1-p1) + p2(1-p2)) / (p1-p2)^2
                # 简化：假设 p1=0.5, p2=0.5+effect_size
                p1 = 0.5
                p2 = 0.5 + effect_size / 2
                if abs(p1 - p2) < 1e-9:
                    return {"error": "比例差异为 0"}
                n_per_group = ((z_alpha + z_beta) ** 2 * (p1 * (1 - p1) + p2 * (1 - p2))) / (p1 - p2) ** 2
                n_per_group = math.ceil(n_per_group)
                total = n_per_group * group_count
                return {
                    "method": method,
                    "method_name": SAMPLE_SIZE_METHODS.get(method, method),
                    "effect_size": effect_size,
                    "alpha": alpha,
                    "power": power,
                    "n_per_group": n_per_group,
                    "total_n": total,
                    "group_count": group_count,
                    "p1": p1,
                    "p2": p2,
                }
            elif method == "correlation":
                # 相关检验：n = ((z_alpha + z_beta) / arctanh(r))^2 + 3
                r = effect_size
                if abs(r) >= 1:
                    return {"error": "相关系数必须在 -1 到 1 之间"}
                arctanh_r = 0.5 * math.log((1 + r) / (1 - r))
                if abs(arctanh_r) < 1e-9:
                    return {"error": "相关系数为 0"}
                n = ((z_alpha + z_beta) / arctanh_r) ** 2 + 3
                n = math.ceil(n)
                return {
                    "method": method,
                    "method_name": SAMPLE_SIZE_METHODS.get(method, method),
                    "effect_size": effect_size,
                    "alpha": alpha,
                    "power": power,
                    "n_per_group": n,
                    "total_n": n,
                }
            elif method == "anova":
                # 方差分析：n = ((z_alpha + z_beta)^2 * k) / (f^2 * (k-1))
                f = effect_size
                k = group_count
                if f <= 0:
                    return {"error": "效应量必须大于 0"}
                n_per_group = ((z_alpha + z_beta) ** 2 * k) / (f ** 2 * (k - 1))
                n_per_group = math.ceil(n_per_group)
                total = n_per_group * k
                return {
                    "method": method,
                    "method_name": SAMPLE_SIZE_METHODS.get(method, method),
                    "effect_size": effect_size,
                    "alpha": alpha,
                    "power": power,
                    "n_per_group": n_per_group,
                    "total_n": total,
                    "group_count": k,
                }
            elif method == "regression":
                # 回归：n >= 8 / f^2 + (k+1)，k 为预测变量数
                f = effect_size
                k = group_count  # 这里复用为预测变量数
                if f <= 0:
                    return {"error": "效应量必须大于 0"}
                n = max(8 / (f ** 2) + k + 1, 50)
                n = math.ceil(n)
                return {
                    "method": method,
                    "method_name": SAMPLE_SIZE_METHODS.get(method, method),
                    "effect_size": effect_size,
                    "alpha": alpha,
                    "power": power,
                    "n_per_group": n,
                    "total_n": n,
                    "predictor_count": k,
                }
            elif method == "chi_square":
                # 卡方：n = (z_alpha + z_beta)^2 / (w^2)
                w = effect_size
                if w <= 0:
                    return {"error": "效应量必须大于 0"}
                n = ((z_alpha + z_beta) ** 2) / (w ** 2)
                n = math.ceil(n)
                return {
                    "method": method,
                    "method_name": SAMPLE_SIZE_METHODS.get(method, method),
                    "effect_size": effect_size,
                    "alpha": alpha,
                    "power": power,
                    "n_per_group": n,
                    "total_n": n,
                }
            return {"error": f"不支持的检验方法: {method}"}

    def _z_from_p(self, p: float) -> float:
        """从 p 值近似计算 Z 值（使用逆误差函数近似）。"""
        if p <= 0:
            return -3.5
        if p >= 1:
            return 3.5
        # 使用 Beasley-Springer-Moro 近似
        # 简化版：使用查表近似
        z_table = [
            (0.001, -3.09), (0.005, -2.58), (0.01, -2.33), (0.025, -1.96),
            (0.05, -1.64), (0.10, -1.28), (0.20, -0.84), (0.30, -0.52),
            (0.40, -0.25), (0.50, 0.0), (0.60, 0.25), (0.70, 0.52),
            (0.80, 0.84), (0.90, 1.28), (0.95, 1.64), (0.975, 1.96),
            (0.99, 2.33), (0.995, 2.58), (0.999, 3.09),
        ]
        # 找最近的
        closest = min(z_table, key=lambda x: abs(x[0] - p))
        # 线性插值
        idx = z_table.index(closest)
        if idx > 0 and z_table[idx - 1][0] < p < closest[0]:
            prev = z_table[idx - 1]
            ratio = (p - prev[0]) / (closest[0] - prev[0])
            return prev[1] + ratio * (closest[1] - prev[1])
        if idx < len(z_table) - 1 and closest[0] < p < z_table[idx + 1][0]:
            nxt = z_table[idx + 1]
            ratio = (p - closest[0]) / (nxt[0] - closest[0])
            return closest[1] + ratio * (nxt[1] - closest[1])
        return closest[1]

    # ===== 功效分析 =====

    def compute_power(
        self,
        method: str = "t_test",
        sample_size: int = 30,
        effect_size: float = 0.5,
        alpha: float = 0.05,
        group_count: int = 2,
    ) -> dict[str, Any]:
        """计算检验功效。

        Args:
            method: 检验方法。
            sample_size: 样本量（每组）。
            effect_size: 效应量。
            alpha: 显著性水平。
            group_count: 组数。

        Returns:
            功效分析结果。
        """
        with self._lock:
            z_alpha = self._z_from_p(1 - alpha / 2)
            if method == "t_test":
                # 功效 = P(Z > z_alpha - d*sqrt(n/2))
                n = sample_size
                d = effect_size
                if n <= 0:
                    return {"error": "样本量必须大于 0"}
                noncentrality = d * math.sqrt(n / 2)
                # 近似功效
                z_beta = noncentrality - z_alpha
                power = self._norm_cdf(z_beta)
                return {
                    "method": method,
                    "sample_size_per_group": n,
                    "total_sample_size": n * group_count,
                    "effect_size": d,
                    "alpha": alpha,
                    "power": round(power, 4),
                    "is_adequate": power >= 0.8,
                }
            elif method == "correlation":
                n = sample_size
                r = effect_size
                if abs(r) >= 1 or n <= 3:
                    return {"error": "参数无效"}
                arctanh_r = 0.5 * math.log((1 + r) / (1 - r))
                noncentrality = arctanh_r * math.sqrt(n - 3)
                z_beta = noncentrality - z_alpha
                power = self._norm_cdf(z_beta)
                return {
                    "method": method,
                    "sample_size": n,
                    "effect_size": r,
                    "alpha": alpha,
                    "power": round(power, 4),
                    "is_adequate": power >= 0.8,
                }
            elif method == "proportion":
                n = sample_size
                p1 = 0.5
                p2 = 0.5 + effect_size / 2
                if abs(p1 - p2) < 1e-9 or n <= 0:
                    return {"error": "参数无效"}
                noncentrality = abs(p1 - p2) * math.sqrt(n / (p1 * (1 - p1) + p2 * (1 - p2)))
                z_beta = noncentrality - z_alpha
                power = self._norm_cdf(z_beta)
                return {
                    "method": method,
                    "sample_size_per_group": n,
                    "total_sample_size": n * group_count,
                    "effect_size": effect_size,
                    "alpha": alpha,
                    "power": round(power, 4),
                    "is_adequate": power >= 0.8,
                }
            return {"error": f"不支持的检验方法: {method}"}

    def _norm_cdf(self, z: float) -> float:
        """标准正态分布累积分布函数（近似）。"""
        # 使用误差函数近似
        # Φ(z) = 0.5 * (1 + erf(z / sqrt(2)))
        return 0.5 * (1 + self._erf(z / math.sqrt(2)))

    def _erf(self, x: float) -> float:
        """误差函数近似（Abramowitz & Stegun 7.1.26）。"""
        a1 = 0.254829592
        a2 = -0.284496736
        a3 = 1.421413741
        a4 = -1.453152027
        a5 = 1.061405429
        p = 0.3275911
        sign = 1 if x >= 0 else -1
        x = abs(x)
        t = 1.0 / (1.0 + p * x)
        y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)
        return sign * y

    # ===== 检验执行 =====

    def run_t_test_one_sample(
        self,
        hypothesis_id: str,
        data: list[float],
        mu: float = 0.0,
        alpha: float = 0.05,
    ) -> Optional[StatisticalTest]:
        """执行单样本 t 检验。

        Args:
            hypothesis_id: 假设 ID。
            data: 样本数据。
            mu: 原假设的总体均值。
            alpha: 显著性水平。

        Returns:
            统计检验实例。
        """
        with self._lock:
            hyp = self._hypotheses.get(hypothesis_id)
            if not hyp:
                return None
            n = len(data)
            if n < 2:
                return None
            # 计算均值与标准差
            mean = sum(data) / n
            variance = sum((x - mean) ** 2 for x in data) / (n - 1)
            std = math.sqrt(variance)
            if std == 0:
                return None
            # t 统计量
            se = std / math.sqrt(n)
            t_stat = (mean - mu) / se
            # 自由度
            df = n - 1
            # p 值（近似）
            p_value = self._t_distribution_p(t_stat, df, hyp.direction)
            # 效应量（Cohen's d）
            cohens_d = (mean - mu) / std
            # 置信区间
            t_crit = self._t_critical_value(df, alpha, "two_tailed")
            ci_lower = mean - t_crit * se
            ci_upper = mean + t_crit * se
            # 决策
            decision = "reject_null" if p_value < alpha else "fail_to_reject_null"
            # 解释
            interpretation = self._interpret_t_test(
                t_stat, p_value, cohens_d, decision, alpha, hyp
            )
            result = TestResult(
                id=f"res_{uuid.uuid4().hex[:8]}",
                test_method="t_test_one_sample",
                statistic=t_stat,
                p_value=p_value,
                effect_size=cohens_d,
                effect_size_type="cohens_d",
                confidence_interval=(ci_lower, ci_upper),
                decision=decision,
                significance_level=alpha,
                interpretation=interpretation,
                degrees_of_freedom=df,
            )
            test = StatisticalTest(
                id=f"test_{uuid.uuid4().hex[:10]}",
                hypothesis_id=hypothesis_id,
                method="t_test_one_sample",
                category="parametric",
                parameters={"mu": mu, "n": n, "mean": mean, "std": std},
                assumptions=[
                    "数据服从正态分布",
                    "观测值独立",
                    "连续型变量",
                ],
                result=result,
                sample_size=n,
                power=self.compute_power("t_test", n, cohens_d, alpha)["power"] if cohens_d > 0 else 0.0,
                created_at=datetime.now().isoformat(),
            )
            self._tests[test.id] = test
            return test

    def run_t_test_independent(
        self,
        hypothesis_id: str,
        group1: list[float],
        group2: list[float],
        alpha: float = 0.05,
        equal_variance: bool = True,
    ) -> Optional[StatisticalTest]:
        """执行独立样本 t 检验。

        Args:
            hypothesis_id: 假设 ID。
            group1: 第一组数据。
            group2: 第二组数据。
            alpha: 显著性水平。
            equal_variance: 是否方差齐性。

        Returns:
            统计检验实例。
        """
        with self._lock:
            hyp = self._hypotheses.get(hypothesis_id)
            if not hyp:
                return None
            n1, n2 = len(group1), len(group2)
            if n1 < 2 or n2 < 2:
                return None
            # 计算各组均值与方差
            mean1 = sum(group1) / n1
            mean2 = sum(group2) / n2
            var1 = sum((x - mean1) ** 2 for x in group1) / (n1 - 1)
            var2 = sum((x - mean2) ** 2 for x in group2) / (n2 - 1)
            # 合并方差（方差齐性）或 Welch 校正
            if equal_variance:
                pooled_var = ((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2)
                se = math.sqrt(pooled_var * (1 / n1 + 1 / n2))
                df = n1 + n2 - 2
            else:
                se = math.sqrt(var1 / n1 + var2 / n2)
                # Welch-Satterthwaite 自由度
                df_num = (var1 / n1 + var2 / n2) ** 2
                df_den = (var1 / n1) ** 2 / (n1 - 1) + (var2 / n2) ** 2 / (n2 - 1)
                df = df_num / df_den if df_den > 0 else n1 + n2 - 2
            if se == 0:
                return None
            # t 统计量
            t_stat = (mean1 - mean2) / se
            # p 值
            p_value = self._t_distribution_p(t_stat, df, hyp.direction)
            # 敟应量
            pooled_std = math.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
            cohens_d = (mean1 - mean2) / pooled_std if pooled_std > 0 else 0.0
            # 置信区间
            t_crit = self._t_critical_value(df, alpha, "two_tailed")
            ci_lower = (mean1 - mean2) - t_crit * se
            ci_upper = (mean1 - mean2) + t_crit * se
            # 决策
            decision = "reject_null" if p_value < alpha else "fail_to_reject_null"
            interpretation = self._interpret_t_test(
                t_stat, p_value, cohens_d, decision, alpha, hyp
            )
            result = TestResult(
                id=f"res_{uuid.uuid4().hex[:8]}",
                test_method="t_test_independent",
                statistic=t_stat,
                p_value=p_value,
                effect_size=cohens_d,
                effect_size_type="cohens_d",
                confidence_interval=(ci_lower, ci_upper),
                decision=decision,
                significance_level=alpha,
                interpretation=interpretation,
                degrees_of_freedom=df,
            )
            test = StatisticalTest(
                id=f"test_{uuid.uuid4().hex[:10]}",
                hypothesis_id=hypothesis_id,
                method="t_test_independent",
                category="parametric",
                parameters={
                    "n1": n1, "n2": n2,
                    "mean1": mean1, "mean2": mean2,
                    "var1": var1, "var2": var2,
                    "equal_variance": equal_variance,
                },
                assumptions=[
                    "两组数据均服从正态分布",
                    "观测值独立" + ("，方差齐性" if equal_variance else "（Welch 校正）"),
                    "连续型变量",
                ],
                result=result,
                sample_size=n1 + n2,
                power=self.compute_power("t_test", min(n1, n2), cohens_d, alpha)["power"] if cohens_d > 0 else 0.0,
                created_at=datetime.now().isoformat(),
            )
            self._tests[test.id] = test
            return test

    def run_correlation_test(
        self,
        hypothesis_id: str,
        x: list[float],
        y: list[float],
        method: str = "correlation_pearson",
        alpha: float = 0.05,
    ) -> Optional[StatisticalTest]:
        """执行相关检验。

        Args:
            hypothesis_id: 假设 ID。
            x: 变量 X 数据。
            y: 变量 Y 数据。
            method: 检验方法（pearson/spearman）。
            alpha: 显著性水平。

        Returns:
            统计检验实例。
        """
        with self._lock:
            hyp = self._hypotheses.get(hypothesis_id)
            if not hyp:
                return None
            n = len(x)
            if n != len(y) or n < 3:
                return None
            if method == "correlation_spearman":
                # 转换为秩
                x = self._rank(x)
                y = self._rank(y)
            # 计算 Pearson r
            mean_x = sum(x) / n
            mean_y = sum(y) / n
            cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
            var_x = sum((xi - mean_x) ** 2 for xi in x)
            var_y = sum((yi - mean_y) ** 2 for yi in y)
            if var_x == 0 or var_y == 0:
                return None
            r = cov / math.sqrt(var_x * var_y)
            # t 统计量
            df = n - 2
            if df <= 0:
                return None
            t_stat = r * math.sqrt(df / (1 - r * r)) if abs(r) < 1 else float('inf')
            # p 值
            p_value = self._t_distribution_p(t_stat, df, hyp.direction)
            # 决策
            decision = "reject_null" if p_value < alpha else "fail_to_reject_null"
            # 解释
            interpretation = self._interpret_correlation(
                r, p_value, decision, alpha, n, hyp
            )
            result = TestResult(
                id=f"res_{uuid.uuid4().hex[:8]}",
                test_method=method,
                statistic=t_stat,
                p_value=p_value,
                effect_size=r,
                effect_size_type="pearson_r",
                confidence_interval=(min(r, 1.0), max(r, -1.0)),
                decision=decision,
                significance_level=alpha,
                interpretation=interpretation,
                degrees_of_freedom=df,
            )
            test = StatisticalTest(
                id=f"test_{uuid.uuid4().hex[:10]}",
                hypothesis_id=hypothesis_id,
                method=method,
                category=METHOD_CATEGORIES.get(method, "parametric"),
                parameters={"n": n, "r": r},
                assumptions=[
                    "两变量服从二元正态分布" if method == "correlation_pearson" else "至少有序变量",
                    "线性关系" if method == "correlation_pearson" else "单调关系",
                    "观测值独立",
                ],
                result=result,
                sample_size=n,
                power=self.compute_power("correlation", n, abs(r), alpha)["power"] if r != 0 else 0.0,
                created_at=datetime.now().isoformat(),
            )
            self._tests[test.id] = test
            return test

    def run_chi_square_test(
        self,
        hypothesis_id: str,
        observed: list[list[int]],
        expected: Optional[list[list[float]]] = None,
        alpha: float = 0.05,
    ) -> Optional[StatisticalTest]:
        """执行卡方检验。

        Args:
            hypothesis_id: 假设 ID。
            observed: 观测频数矩阵。
            expected: 期望频数矩阵（可选，默认按独立性计算）。
            alpha: 显著性水平。

        Returns:
            统计检验实例。
        """
        with self._lock:
            hyp = self._hypotheses.get(hypothesis_id)
            if not hyp:
                return None
            rows = len(observed)
            cols = len(observed[0]) if rows > 0 else 0
            if rows < 2 or cols < 2:
                return None
            # 计算期望频数（独立性检验）
            if expected is None:
                total = sum(sum(row) for row in observed)
                if total == 0:
                    return None
                row_sums = [sum(row) for row in observed]
                col_sums = [sum(observed[i][j] for i in range(rows)) for j in range(cols)]
                expected = [
                    [row_sums[i] * col_sums[j] / total for j in range(cols)]
                    for i in range(rows)
                ]
            # 卡方统计量
            chi2 = 0.0
            for i in range(rows):
                for j in range(cols):
                    if expected[i][j] > 0:
                        chi2 += (observed[i][j] - expected[i][j]) ** 2 / expected[i][j]
            # 自由度
            df = (rows - 1) * (cols - 1)
            # p 值（使用卡方分布近似）
            p_value = self._chi_square_p(chi2, df)
            # 效应量（Cramér's V）
            total = sum(sum(row) for row in observed)
            min_dim = min(rows - 1, cols - 1)
            cramers_v = math.sqrt(chi2 / (total * min_dim)) if min_dim > 0 and total > 0 else 0.0
            # 决策
            decision = "reject_null" if p_value < alpha else "fail_to_reject_null"
            interpretation = self._interpret_chi_square(
                chi2, p_value, cramers_v, decision, alpha, df, hyp
            )
            result = TestResult(
                id=f"res_{uuid.uuid4().hex[:8]}",
                test_method="chi_square_independence",
                statistic=chi2,
                p_value=p_value,
                effect_size=cramers_v,
                effect_size_type="cramers_v",
                confidence_interval=(0.0, 1.0),
                decision=decision,
                significance_level=alpha,
                interpretation=interpretation,
                degrees_of_freedom=df,
            )
            test = StatisticalTest(
                id=f"test_{uuid.uuid4().hex[:10]}",
                hypothesis_id=hypothesis_id,
                method="chi_square_independence",
                category="parametric",
                parameters={
                    "rows": rows, "cols": cols,
                    "observed": observed, "expected": expected,
                },
                assumptions=[
                    "期望频数 ≥ 5",
                    "观测值独立",
                    "分类变量",
                ],
                result=result,
                sample_size=total,
                created_at=datetime.now().isoformat(),
            )
            self._tests[test.id] = test
            return test

    # ===== 统计分布近似 =====

    def _t_distribution_p(self, t: float, df: float, direction: str) -> float:
        """计算 t 分布的 p 值（近似）。

        Args:
            t: t 统计量。
            df: 自由度。
            direction: 检验方向。

        Returns:
            p 值。
        """
        # 使用正态近似（df 较大时）
        if df > 30:
            if direction == "two_tailed":
                p = 2 * (1 - self._norm_cdf(abs(t)))
            elif direction == "one_tailed_greater":
                p = 1 - self._norm_cdf(t)
            else:
                p = self._norm_cdf(t)
            return max(0.0, min(1.0, p))
        # 小样本：使用 t 分布近似
        # 简化：使用 Beta 函数近似
        x = df / (df + t * t)
        # 不完全 Beta 函数近似
        p_one_tail = 0.5 * self._incomplete_beta(df / 2, 0.5, x)
        if direction == "two_tailed":
            return max(0.0, min(1.0, 2 * p_one_tail))
        elif direction == "one_tailed_greater":
            if t > 0:
                return max(0.0, min(1.0, p_one_tail))
            return max(0.0, min(1.0, 1 - p_one_tail))
        else:  # one_tailed_less
            if t < 0:
                return max(0.0, min(1.0, p_one_tail))
            return max(0.0, min(1.0, 1 - p_one_tail))

    def _incomplete_beta(self, a: float, b: float, x: float) -> float:
        """不完全 Beta 函数近似（连分式展开）。"""
        if x <= 0:
            return 0.0
        if x >= 1:
            return 1.0
        # 使用连分式近似（Lentz 算法）
        lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
        front = math.exp(math.log(x) * a + math.log(1 - x) * b - lbeta) / a
        # 连分式
        qab = a + b
        qap = a + 1
        qam = a - 1
        c = 1.0
        d = 1.0 - qab * x / qap
        if abs(d) < 1e-30:
            d = 1e-30
        d = 1.0 / d
        result = d
        for m in range(1, 100):
            m2 = 2 * m
            aa = m * (b - m) * x / ((qam + m2) * (a + m2))
            d = 1.0 + aa * d
            if abs(d) < 1e-30:
                d = 1e-30
            c = 1.0 + aa / c
            if abs(c) < 1e-30:
                c = 1e-30
            d = 1.0 / d
            result *= d * c
            aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
            d = 1.0 + aa * d
            if abs(d) < 1e-30:
                d = 1e-30
            c = 1.0 + aa / c
            if abs(c) < 1e-30:
                c = 1e-30
            d = 1.0 / d
            delta = d * c
            result *= delta
            if abs(delta - 1.0) < 1e-10:
                break
        return front * result

    def _chi_square_p(self, chi2: float, df: float) -> float:
        """计算卡方分布的 p 值（近似）。

        Args:
            chi2: 卡方统计量。
            df: 自由度。

        Returns:
            p 值。
        """
        if chi2 <= 0:
            return 1.0
        if df <= 0:
            return 1.0
        # 使用不完全 Gamma 函数
        # P = 1 - Gamma(df/2, chi2/2) / Gamma(df/2)
        # 即上侧概率
        return max(0.0, min(1.0, self._upper_incomplete_gamma(df / 2, chi2 / 2)))

    def _upper_incomplete_gamma(self, s: float, x: float) -> float:
        """上侧不完全 Gamma 函数（归一化）。"""
        if x < 0 or s <= 0:
            return 1.0
        if x == 0:
            return 1.0
        # 使用级数展开或连分式
        if x < s + 1:
            # 级数展开
            return math.exp(-x + s * math.log(x) - math.lgamma(s)) * self._gamma_series(s, x)
        else:
            # 连分式
            return 1.0 - math.exp(-x + s * math.log(x) - math.lgamma(s)) * self._gamma_cf(s, x)

    def _gamma_series(self, s: float, x: float) -> float:
        """Gamma 函数级数展开。"""
        total = 1.0 / s
        term = 1.0 / s
        for _ in range(100):
            term *= x / (s + _ + 1)
            total += term
            if abs(term) < abs(total) * 1e-10:
                break
        return total

    def _gamma_cf(self, s: float, x: float) -> float:
        """Gamma 函数连分式展开。"""
        b = x + 1 - s
        c = 1e30
        d = 1.0 / b
        h = d
        for i in range(1, 100):
            an = -i * (i - s)
            b += 2
            d = an * d + b
            if abs(d) < 1e-30:
                d = 1e-30
            c = b + an / c
            if abs(c) < 1e-30:
                c = 1e-30
            d = 1.0 / d
            delta = d * c
            h *= delta
            if abs(delta - 1.0) < 1e-10:
                break
        return h

    def _t_critical_value(
        self, df: float, alpha: float, direction: str
    ) -> float:
        """计算 t 临界值（近似）。"""
        # 使用正态近似
        if direction == "two_tailed":
            return abs(self._z_from_p(1 - alpha / 2))
        else:
            return abs(self._z_from_p(1 - alpha))

    def _rank(self, data: list[float]) -> list[float]:
        """计算数据的秩（用于 Spearman 相关）。"""
        indexed = sorted(enumerate(data), key=lambda x: x[1])
        ranks = [0.0] * len(data)
        i = 0
        while i < len(indexed):
            # 处理并列
            j = i
            while j < len(indexed) - 1 and indexed[j + 1][1] == indexed[i][1]:
                j += 1
            avg_rank = (i + j) / 2 + 1  # 平均秩（从 1 开始）
            for k in range(i, j + 1):
                ranks[indexed[k][0]] = avg_rank
            i = j + 1
        return ranks

    # ===== 结果解释 =====

    def _interpret_t_test(
        self,
        t_stat: float,
        p_value: float,
        effect_size: float,
        decision: str,
        alpha: float,
        hyp: Hypothesis,
    ) -> str:
        """解释 t 检验结果。"""
        parts: list[str] = []
        if decision == "reject_null":
            parts.append(
                f"t 检验结果统计显著（t = {t_stat:.4f}, p = {p_value:.4f} < {alpha}），"
                f"拒绝原假设。"
            )
        else:
            parts.append(
                f"t 检验结果不显著（t = {t_stat:.4f}, p = {p_value:.4f} ≥ {alpha}），"
                f"未能拒绝原假设。"
            )
        # 效应量解释
        size = self._interpret_effect_size(effect_size, "cohens_d")
        parts.append(f"效应量 Cohen's d = {effect_size:.4f}（{size}）。")
        # 结论
        if decision == "reject_null":
            parts.append(f"支持备择假设：{hyp.alternative_hypothesis}")
        else:
            parts.append(f"缺乏足够证据支持备择假设，原假设{hyp.null_hypothesis}未被推翻。")
        return " ".join(parts)

    def _interpret_correlation(
        self,
        r: float,
        p_value: float,
        decision: str,
        alpha: float,
        n: int,
        hyp: Hypothesis,
    ) -> str:
        """解释相关检验结果。"""
        parts: list[str] = []
        # 相关方向与强度
        direction = "正" if r > 0 else "负"
        size = self._interpret_effect_size(abs(r), "pearson_r")
        parts.append(f"相关系数 r = {r:.4f}，呈{direction}相关（{size}）。")
        if decision == "reject_null":
            parts.append(
                f"相关显著（p = {p_value:.4f} < {alpha}），拒绝原假设。"
            )
            parts.append(f"支持备择假设：{hyp.alternative_hypothesis}")
        else:
            parts.append(
                f"相关不显著（p = {p_value:.4f} ≥ {alpha}），未能拒绝原假设。"
            )
        parts.append(f"样本量 n = {n}。")
        return " ".join(parts)

    def _interpret_chi_square(
        self,
        chi2: float,
        p_value: float,
        cramers_v: float,
        decision: str,
        alpha: float,
        df: float,
        hyp: Hypothesis,
    ) -> str:
        """解释卡方检验结果。"""
        parts: list[str] = []
        if decision == "reject_null":
            parts.append(
                f"卡方检验结果显著（χ² = {chi2:.4f}, df = {df:.0f}, "
                f"p = {p_value:.4f} < {alpha}），拒绝原假设。"
            )
            parts.append("变量之间存在显著关联。")
        else:
            parts.append(
                f"卡方检验结果不显著（χ² = {chi2:.4f}, df = {df:.0f}, "
                f"p = {p_value:.4f} ≥ {alpha}），未能拒绝原假设。"
            )
            parts.append("变量之间无显著关联。")
        size = self._interpret_effect_size(cramers_v, "cramers_v")
        parts.append(f"效应量 Cramér's V = {cramers_v:.4f}（{size}）。")
        return " ".join(parts)

    def _interpret_effect_size(self, value: float, es_type: str) -> str:
        """解释效应量大小。"""
        thresholds = EFFECT_SIZE_INTERPRETATIONS.get(es_type, {})
        if not thresholds:
            return "未定义"
        if value < thresholds.get("small", 0):
            return "可忽略"
        if value < thresholds.get("medium", 0):
            return "小"
        if value < thresholds.get("large", 0):
            return "中"
        return "大"

    # ===== 多重检验校正 =====

    def correct_multiple_tests(
        self,
        p_values: list[float],
        method: str = "bh",
        alpha: float = 0.05,
    ) -> dict[str, Any]:
        """多重检验校正。

        Args:
            p_values: 原始 p 值列表。
            method: 校正方法（bonferroni/holm/bh/by）。
            alpha: 显著性水平。

        Returns:
            校正结果字典。
        """
        with self._lock:
            if method not in CORRECTION_METHODS:
                method = "bh"
            m = len(p_values)
            if m == 0:
                return {}
            # 按原始 p 值排序
            indexed = sorted(enumerate(p_values), key=lambda x: x[1])
            adjusted = [0.0] * m
            if method == "bonferroni":
                for i, (orig_idx, p) in enumerate(indexed):
                    adjusted[orig_idx] = min(1.0, p * m)
            elif method == "holm":
                # 逐步降序
                for rank in range(m - 1, -1, -1):
                    orig_idx, p = indexed[rank]
                    adjusted[orig_idx] = min(1.0, p * (m - rank))
                    # 确保单调性
                    if rank < m - 1:
                        next_orig_idx = indexed[rank + 1][0]
                        adjusted[orig_idx] = max(adjusted[orig_idx], adjusted[next_orig_idx])
            elif method == "bh":
                # Benjamini-Hochberg
                for rank in range(m - 1, -1, -1):
                    orig_idx, p = indexed[rank]
                    adjusted[orig_idx] = min(1.0, p * m / (rank + 1))
                    if rank < m - 1:
                        next_orig_idx = indexed[rank + 1][0]
                        adjusted[orig_idx] = min(adjusted[orig_idx], adjusted[next_orig_idx])
            elif method == "by":
                # Benjamini-Yekutieli
                c_m = sum(1.0 / i for i in range(1, m + 1))
                for rank in range(m - 1, -1, -1):
                    orig_idx, p = indexed[rank]
                    adjusted[orig_idx] = min(1.0, p * m * c_m / (rank + 1))
                    if rank < m - 1:
                        next_orig_idx = indexed[rank + 1][0]
                        adjusted[orig_idx] = min(adjusted[orig_idx], adjusted[next_orig_idx])
            # 统计显著数
            significant_count = sum(1 for a in adjusted if a < alpha)
            return {
                "method": method,
                "method_name": CORRECTION_METHODS.get(method, method),
                "original_p_values": p_values,
                "adjusted_p_values": [round(a, 6) for a in adjusted],
                "alpha": alpha,
                "test_count": m,
                "significant_count": significant_count,
                "is_significant": [a < alpha for a in adjusted],
            }

    # ===== 贝叶斯假设检验 =====

    def bayesian_test(
        self,
        hypothesis_id: str,
        data: list[float],
        mu_null: float = 0.0,
        prior_mean: float = 0.0,
        prior_variance: float = 1.0,
    ) -> dict[str, Any]:
        """贝叶斯假设检验（简化版）。

        使用贝叶斯因子比较 H₀ 与 H₁。

        Args:
            hypothesis_id: 假设 ID。
            data: 样本数据。
            mu_null: 原假设下的均值。
            prior_mean: 先验均值。
            prior_variance: 先验方差。

        Returns:
            贝叶斯检验结果。
        """
        with self._lock:
            hyp = self._hypotheses.get(hypothesis_id)
            if not hyp:
                return {}
            n = len(data)
            if n < 2:
                return {}
            # 计算样本统计量
            sample_mean = sum(data) / n
            sample_var = sum((x - sample_mean) ** 2 for x in data) / (n - 1)
            sample_se = math.sqrt(sample_var / n)
            # 简化贝叶斯因子计算（基于 BIC 近似）
            # BF_10 = exp((BIC_H0 - BIC_H1) / 2)
            # BIC = n * ln(SSE/n) + k * ln(n)
            sse_h0 = sum((x - mu_null) ** 2 for x in data)
            sse_h1 = sum((x - sample_mean) ** 2 for x in data)
            bic_h0 = n * math.log(sse_h0 / n) + 1 * math.log(n)
            bic_h1 = n * math.log(sse_h1 / n) + 2 * math.log(n)
            log_bf_10 = (bic_h0 - bic_h1) / 2
            bf_10 = math.exp(log_bf_10)
            # 解释贝叶斯因子
            if bf_10 > 100:
                evidence = "决定性证据支持 H₁"
            elif bf_10 > 30:
                evidence = "很强证据支持 H₁"
            elif bf_10 > 10:
                evidence = "强证据支持 H₁"
            elif bf_10 > 3:
                evidence = "中等证据支持 H₁"
            elif bf_10 > 1:
                evidence = "弱证据支持 H₁"
            elif bf_10 > 1 / 3:
                evidence = "证据不足"
            elif bf_10 > 1 / 10:
                evidence = "弱证据支持 H₀"
            elif bf_10 > 1 / 30:
                evidence = "中等证据支持 H₀"
            elif bf_10 > 1 / 100:
                evidence = "强证据支持 H₀"
            else:
                evidence = "决定性证据支持 H₀"
            # 后验概率（简化）
            posterior_h1 = bf_10 / (1 + bf_10)
            posterior_h0 = 1 - posterior_h1
            return {
                "hypothesis_id": hypothesis_id,
                "bayes_factor_10": round(bf_10, 6),
                "bayes_factor_01": round(1 / bf_10, 6),
                "log_bf_10": round(log_bf_10, 6),
                "posterior_h0": round(posterior_h0, 6),
                "posterior_h1": round(posterior_h1, 6),
                "evidence": evidence,
                "sample_mean": round(sample_mean, 6),
                "sample_se": round(sample_se, 6),
                "n": n,
            }

    # ===== 查询与统计 =====

    def get_test(self, test_id: str) -> Optional[StatisticalTest]:
        """获取检验。"""
        with self._lock:
            return self._tests.get(test_id)

    def list_tests(
        self, hypothesis_id: Optional[str] = None
    ) -> list[StatisticalTest]:
        """列出检验。"""
        with self._lock:
            tests = list(self._tests.values())
            if hypothesis_id:
                tests = [t for t in tests if t.hypothesis_id == hypothesis_id]
            return tests

    def compute_statistics(self) -> dict[str, Any]:
        """计算检验器统计指标。"""
        with self._lock:
            total_hyp = len(self._hypotheses)
            total_tests = len(self._tests)
            if total_hyp == 0:
                return {"total_hypotheses": 0, "total_tests": 0}
            # 假设统计
            type_counts: dict[str, int] = defaultdict(int)
            testability_scores = []
            for hyp in self._hypotheses.values():
                type_counts[hyp.hypothesis_type] += 1
                testability_scores.append(hyp.testability_score)
            # 检验统计
            method_counts: dict[str, int] = defaultdict(int)
            significant_count = 0
            for test in self._tests.values():
                method_counts[test.method] += 1
                if test.result and test.result.is_significant:
                    significant_count += 1
            return {
                "total_hypotheses": total_hyp,
                "total_tests": total_tests,
                "hypothesis_type_counts": dict(type_counts),
                "avg_testability": round(
                    sum(testability_scores) / len(testability_scores), 4
                ) if testability_scores else 0,
                "method_counts": dict(method_counts),
                "significant_results": significant_count,
                "non_significant_results": total_tests - significant_count,
            }

    def summary(self) -> dict[str, Any]:
        """返回检验器汇总信息。"""
        with self._lock:
            return {
                "hypothesis_count": len(self._hypotheses),
                "test_count": len(self._tests),
                "supported_methods": list(TEST_METHODS.keys()),
                "supported_corrections": list(CORRECTION_METHODS.keys()),
            }

    # ===== 导出 =====

    def export_hypothesis_markdown(self, hypothesis_id: str) -> str:
        """导出假设为 Markdown。"""
        with self._lock:
            hyp = self._hypotheses.get(hypothesis_id)
            if not hyp:
                return ""
            lines: list[str] = []
            lines.append(f"# 假设：{hyp.name}")
            lines.append("")
            lines.append(f"- **类型**：{HYPOTHESIS_TYPES.get(hyp.hypothesis_type, hyp.hypothesis_type)}")
            lines.append(f"- **方向**：{HYPOTHESIS_DIRECTIONS.get(hyp.direction, hyp.direction)}")
            lines.append(f"- **可测试性评分**：{hyp.testability_score:.2f}")
            lines.append("")
            lines.append("## 假设陈述")
            lines.append("")
            lines.append(f"- **原假设（H₀）**：{hyp.null_hypothesis}")
            lines.append(f"- **备择假设（H₁）**：{hyp.alternative_hypothesis}")
            if hyp.expected_effect:
                lines.append(f"- **预期效应**：{hyp.expected_effect}")
            if hyp.variables:
                lines.append(f"- **涉及变量**：{', '.join(hyp.variables)}")
            lines.append("")
            # 关联检验
            tests = self.list_tests(hypothesis_id)
            if tests:
                lines.append("## 检验结果")
                lines.append("")
                for test in tests:
                    if test.result:
                        r = test.result
                        lines.append(f"### {TEST_METHODS.get(test.method, test.method)}")
                        lines.append("")
                        lines.append(f"- **统计量**：{r.statistic:.4f}")
                        lines.append(f"- **p 值**：{r.p_value:.4f}")
                        lines.append(f"- **效应量**：{r.effect_size:.4f}（{EFFECT_SIZE_TYPES.get(r.effect_size_type, r.effect_size_type)}）")
                        lines.append(f"- **决策**：{DECISION_RESULTS.get(r.decision, r.decision)}")
                        lines.append(f"- **解释**：{r.interpretation}")
                        lines.append("")
            return "\n".join(lines)

    def export_test_dict(self, test_id: str) -> dict[str, Any]:
        """导出检验为字典。"""
        with self._lock:
            test = self._tests.get(test_id)
            if not test:
                return {}
            return test.to_dict()
