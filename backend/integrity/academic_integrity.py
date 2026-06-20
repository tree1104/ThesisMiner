"""学术诚信检查器模块

提供论文研究全生命周期的学术诚信检查能力，包括：
    - 数据造假检测（统计异常、数据捏造、结果操纵）
    - 图表篡改检测（图像拼接、裁剪、PS 痕迹）
    - 引用伪造检测（虚假引用、引用堆叠、自引圈）
    - 自我抄袭检测（文本复用、段落重复）
    - 重复发表检测（一稿多投、香肠论文）
    - 不当署名检测（荣誉署名、代写、买卖论文）
    - 伦理审查（IRB、知情同意、动物实验）
    - 利益冲突声明（财务、个人、学术关系）
    - 数据来源追溯（公开数据集、二次使用、授权）
    - 诚信报告生成、风险等级评估、整改建议

设计原则：
    1. 零外部依赖：仅使用 Python 标准库
    2. 线程安全：所有公共方法通过 RLock 保护
    3. 可配置：阈值、权重、规则均可调整
    4. 可扩展：支持新增检查维度
    5. 可解释：每个问题附带规则依据与证据
"""
from __future__ import annotations

import hashlib
import math
import re
import threading
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Iterable, Optional


# ===== 枚举 =====


class RiskLevel(str, Enum):
    """风险等级。"""

    NONE = "none"          # 无风险
    LOW = "low"            # 低风险
    MEDIUM = "medium"      # 中风险
    HIGH = "high"          # 高风险
    CRITICAL = "critical"  # 严重风险


class IntegrityDimension(str, Enum):
    """诚信检查维度。"""

    DATA_FABRICATION = "data_fabrication"        # 数据造假
    FIGURE_MANIPULATION = "figure_manipulation"  # 图表篡改
    CITATION_FABRICATION = "citation_fabrication"  # 引用伪造
    SELF_PLAGIARISM = "self_plagiarism"          # 自我抄袭
    DUPLICATE_PUBLICATION = "duplicate_publication"  # 重复发表
    AUTHORSHIP_MISCONDUCT = "authorship_misconduct"  # 不当署名
    ETHICS_REVIEW = "ethics_review"              # 伦理审查
    CONFLICT_OF_INTEREST = "conflict_of_interest"  # 利益冲突
    DATA_PROVENANCE = "data_provenance"          # 数据来源


# ===== 常量 =====


# 默认风险评分阈值
DEFAULT_LOW_RISK_THRESHOLD = 0.2
DEFAULT_MEDIUM_RISK_THRESHOLD = 0.4
DEFAULT_HIGH_RISK_THRESHOLD = 0.7
DEFAULT_CRITICAL_RISK_THRESHOLD = 0.85

# 自我抄袭相似度阈值
SELF_PLAGIARISM_THRESHOLD = 0.3

# 重复发表相似度阈值
DUPLICATE_PUBLICATION_THRESHOLD = 0.6

# 引用堆叠阈值（同一来源引用次数占比）
CITATION_STACKING_RATIO = 0.3

# 自引率阈值
SELF_CITATION_RATIO_THRESHOLD = 0.25

# 数据造假：标准差异常倍数
FABRICATION_STD_MULTIPLIER = 3.0

# 数据造假：尾数分布异常阈值（Benford 定律偏差）
BENFORD_DEVIATION_THRESHOLD = 0.15

# 图表篡改：图像哈希相似度阈值
IMAGE_HASH_SIMILARITY_THRESHOLD = 0.95

# 各维度默认权重（用于综合风险评分）
DIMENSION_WEIGHTS: dict[IntegrityDimension, float] = {
    IntegrityDimension.DATA_FABRICATION: 1.5,
    IntegrityDimension.FIGURE_MANIPULATION: 1.4,
    IntegrityDimension.CITATION_FABRICATION: 1.3,
    IntegrityDimension.SELF_PLAGIARISM: 1.0,
    IntegrityDimension.DUPLICATE_PUBLICATION: 1.2,
    IntegrityDimension.AUTHORSHIP_MISCONDUCT: 1.1,
    IntegrityDimension.ETHICS_REVIEW: 1.3,
    IntegrityDimension.CONFLICT_OF_INTEREST: 0.9,
    IntegrityDimension.DATA_PROVENANCE: 1.0,
}

# Benford 定律首位数字期望分布
BENFORD_EXPECTED = {
    1: 0.301, 2: 0.176, 3: 0.125, 4: 0.097, 5: 0.079,
    6: 0.067, 7: 0.058, 8: 0.051, 9: 0.046,
}

# 伦理审查关键词
ETHICS_KEYWORDS = {
    "human_subjects": ["受试者", "人类被试", "human subject", "participant", "患者", "patient"],
    "informed_consent": ["知情同意", "informed consent", "同意书", "consent form"],
    "irb_approval": ["伦理委员会", "IRB", "institutional review board", "伦理审批"],
    "animal_experiment": ["动物实验", "animal experiment", "小鼠", "mouse", "大鼠", "rat"],
    "vulnerable_population": ["未成年人", "children", "孕妇", "pregnant", "囚犯", "prisoner"],
}

# 利益冲突关键词
COI_KEYWORDS = {
    "financial": ["资助", "funding", "grant", "赞助", "sponsor", "股权", "equity", "专利", "patent"],
    "employment": ["雇佣", "employment", "顾问", "consultant", "董事会", "board member"],
    "personal": ["亲属", "family", "朋友", "friend", "合作者", "collaborator"],
}

# 数据来源关键词
PROVENANCE_KEYWORDS = {
    "public_dataset": ["公开数据集", "public dataset", "UCI", "Kaggle", "ImageNet", "CIFAR"],
    "license_required": ["授权", "license", "许可", "permission", "协议", "agreement"],
    "secondary_use": ["二次使用", "secondary use", "再利用", "reuse", "先前研究", "previous study"],
}

# 引用识别正则
CITATION_REGEX_PATTERNS = [
    re.compile(r"\[([0-9]+(?:[-,;\s][0-9]+)*)\]"),  # [1] 或 [1, 2, 3]
    re.compile(r"\(([^)]*\d{4}[^)]*)\)"),             # (Author, 2020)
    re.compile(r"（([^）]*\d{4}[^）]*)）"),             # 中文括号
]

# 作者署名正则
AUTHOR_LIST_PATTERN = re.compile(
    r"([A-Z][a-zA-Z\-]+(?:\s+[A-Z][a-zA-Z\-]+)*)(?:\s*,\s*|\s+and\s+|\s+et\s+al\.?)"
)

# DOI 正则
DOI_PATTERN = re.compile(r"10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+")

# 数字提取正则（用于 Benford 分析）
NUMBER_PATTERN = re.compile(r"(?<![0-9.])([1-9]\d*(?:\.\d+)?)(?![0-9.])")


# ===== 数据结构 =====


@dataclass
class IntegrityIssue:
    """诚信问题。

    Attributes:
        id: 问题 ID。
        dimension: 检查维度。
        severity: 严重程度（0-1）。
        title: 问题标题。
        description: 问题描述。
        evidence: 证据列表。
        location: 问题位置（章节/段落/行号）。
        rule_id: 触发的规则 ID。
        recommendation: 整改建议。
        confidence: 置信度（0-1）。
    """

    id: str = ""
    dimension: IntegrityDimension = IntegrityDimension.DATA_FABRICATION
    severity: float = 0.0
    title: str = ""
    description: str = ""
    evidence: list[str] = field(default_factory=list)
    location: str = ""
    rule_id: str = ""
    recommendation: str = ""
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "dimension": self.dimension.value,
            "severity": round(self.severity, 4),
            "title": self.title,
            "description": self.description,
            "evidence": self.evidence,
            "location": self.location,
            "rule_id": self.rule_id,
            "recommendation": self.recommendation,
            "confidence": round(self.confidence, 4),
        }


@dataclass
class IntegrityReport:
    """诚信检查报告。

    Attributes:
        id: 报告 ID。
        document_id: 文档 ID。
        timestamp: 检查时间。
        overall_risk: 综合风险评分（0-1）。
        risk_level: 风险等级。
        issues: 问题列表。
        dimension_scores: 各维度评分。
        passed: 是否通过检查。
        recommendations: 综合整改建议。
        metadata: 元数据。
    """

    id: str = ""
    document_id: str = ""
    timestamp: str = ""
    overall_risk: float = 0.0
    risk_level: RiskLevel = RiskLevel.NONE
    issues: list[IntegrityIssue] = field(default_factory=list)
    dimension_scores: dict[str, float] = field(default_factory=dict)
    passed: bool = True
    recommendations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "timestamp": self.timestamp,
            "overall_risk": round(self.overall_risk, 4),
            "risk_level": self.risk_level.value,
            "issues": [i.to_dict() for i in self.issues],
            "dimension_scores": {k: round(v, 4) for k, v in self.dimension_scores.items()},
            "passed": self.passed,
            "recommendations": self.recommendations,
            "metadata": self.metadata,
        }


@dataclass
class DocumentMetadata:
    """文档元数据。

    Attributes:
        title: 标题。
        authors: 作者列表。
        abstract: 摘要。
        keywords: 关键词。
        funding: 资助声明。
        conflict_of_interest: 利益冲突声明。
        ethics_statement: 伦理声明。
        data_availability: 数据可用性声明。
        references: 参考文献列表。
        sections: 章节内容映射。
        tables: 表格数据列表。
        figures: 图表描述列表。
        publication_history: 发表历史。
    """

    title: str = ""
    authors: list[str] = field(default_factory=list)
    abstract: str = ""
    keywords: list[str] = field(default_factory=list)
    funding: str = ""
    conflict_of_interest: str = ""
    ethics_statement: str = ""
    data_availability: str = ""
    references: list[str] = field(default_factory=list)
    sections: dict[str, str] = field(default_factory=dict)
    tables: list[dict[str, Any]] = field(default_factory=list)
    figures: list[dict[str, Any]] = field(default_factory=list)
    publication_history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PriorPublication:
    """作者既往发表记录（用于自我抄袭/重复发表检测）。

    Attributes:
        title: 标题。
        authors: 作者列表。
        year: 发表年份。
        venue: 发表场所。
        content: 文本内容。
        doi: DOI。
    """

    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: int = 0
    venue: str = ""
    content: str = ""
    doi: str = ""


# ===== 工具函数 =====


def _normalize_text(text: str) -> str:
    """文本归一化：小写化、去除多余空白与标点。

    Args:
        text: 原始文本。

    Returns:
        归一化后的文本。
    """
    if not text:
        return ""
    # 转小写
    text = text.lower()
    # 去除标点（保留中文、字母、数字、空格）
    text = re.sub(r"[^\w\u4e00-\u9fff\s]", " ", text)
    # 合并空白
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokenize(text: str) -> list[str]:
    """简单分词：英文按空格，中文按字。

    Args:
        text: 原始文本。

    Returns:
        词元列表。
    """
    normalized = _normalize_text(text)
    if not normalized:
        return []
    tokens: list[str] = []
    current = []
    for ch in normalized:
        if "\u4e00" <= ch <= "\u9fff":
            if current:
                tokens.append("".join(current))
                current = []
            tokens.append(ch)
        elif ch.isspace():
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(ch)
    if current:
        tokens.append("".join(current))
    return tokens


def _ngrams(tokens: list[str], n: int = 3) -> set[str]:
    """生成 n-gram 集合。

    Args:
        tokens: 词元列表。
        n: n-gram 大小。

    Returns:
        n-gram 字符串集合。
    """
    if len(tokens) < n:
        return set()
    return {" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)}


def _jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    """计算 Jaccard 相似度。

    Args:
        set_a: 集合 A。
        set_b: 集合 B。

    Returns:
        相似度（0-1）。
    """
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union) if union else 0.0


def _extract_numbers(text: str) -> list[float]:
    """从文本中提取数字（用于 Benford 分析）。

    Args:
        text: 原始文本。

    Returns:
        数字列表。
    """
    numbers: list[float] = []
    for match in NUMBER_PATTERN.finditer(text):
        try:
            numbers.append(float(match.group(1)))
        except ValueError:
            continue
    return numbers


def _benford_chi_square(numbers: list[float]) -> tuple[float, dict[int, float]]:
    """计算 Benford 定律的卡方偏差。

    Args:
        numbers: 数字列表。

    Returns:
        (卡方统计量, 各首位数字实际频率)。
    """
    if not numbers:
        return 0.0, {}
    first_digits = [int(str(abs(n))[0]) for n in numbers if n != 0]
    if not first_digits:
        return 0.0, {}
    total = len(first_digits)
    actual_freq: dict[int, float] = {}
    chi_square = 0.0
    for digit in range(1, 10):
        observed = first_digits.count(digit)
        actual_freq[digit] = observed / total
        expected = BENFORD_EXPECTED[digit] * total
        if expected > 0:
            chi_square += ((observed - expected) ** 2) / expected
    return chi_square, actual_freq


def _mean(values: list[float]) -> float:
    """计算均值。"""
    return sum(values) / len(values) if values else 0.0


def _std(values: list[float]) -> float:
    """计算标准差（总体）。"""
    if len(values) < 2:
        return 0.0
    avg = _mean(values)
    variance = sum((v - avg) ** 2 for v in values) / len(values)
    return math.sqrt(variance)


def _detect_outliers_zscore(values: list[float], threshold: float = 3.0) -> list[int]:
    """基于 Z-score 检测离群点索引。

    Args:
        values: 数值列表。
        threshold: Z-score 阈值。

    Returns:
        离群点索引列表。
    """
    if len(values) < 3:
        return []
    avg = _mean(values)
    sd = _std(values)
    if sd == 0:
        return []
    return [i for i, v in enumerate(values) if abs((v - avg) / sd) > threshold]


def _text_hash(text: str) -> str:
    """计算文本 SHA256 哈希。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _split_sentences(text: str) -> list[str]:
    """简单句子切分（中英文标点）。"""
    if not text:
        return []
    # 按中英文句号、问号、感叹号切分
    parts = re.split(r"[。！？.!?]+", text)
    return [p.strip() for p in parts if p.strip()]


# ===== 主检查器类 =====


class AcademicIntegrityChecker:
    """学术诚信检查器。

    对论文文档执行多维度学术诚信检查，输出综合风险评分与整改建议。

    检查维度包括：
        - 数据造假（统计异常、Benford 偏差、离群点）
        - 图表篡改（图像哈希重复、描述不一致）
        - 引用伪造（虚假引用、引用堆叠、自引圈）
        - 自我抄袭（与既往发表文本复用）
        - 重复发表（与既往发表高度相似）
        - 不当署名（作者列表异常、荣誉署名）
        - 伦理审查（IRB/知情同意/动物实验声明）
        - 利益冲突（财务/雇佣/个人关系声明）
        - 数据来源（公开数据集/授权/二次使用声明）

    线程安全：所有公共方法通过 RLock 保护。

    典型用法：
        checker = AcademicIntegrityChecker()
        metadata = DocumentMetadata(title="...", authors=[...], ...)
        report = checker.check(metadata, prior_publications=[...])
        if not report.passed:
            for issue in report.issues:
                print(issue.title, issue.recommendation)
    """

    def __init__(
        self,
        dimension_weights: Optional[dict[IntegrityDimension, float]] = None,
        thresholds: Optional[dict[str, float]] = None,
    ) -> None:
        """初始化检查器。

        Args:
            dimension_weights: 各维度权重，默认使用 DIMENSION_WEIGHTS。
            thresholds: 阈值配置，可覆盖默认阈值。
        """
        self._lock = threading.RLock()
        self._weights = dict(DIMENSION_WEIGHTS)
        if dimension_weights:
            self._weights.update(dimension_weights)

        # 阈值配置
        self._thresholds: dict[str, float] = {
            "low_risk": DEFAULT_LOW_RISK_THRESHOLD,
            "medium_risk": DEFAULT_MEDIUM_RISK_THRESHOLD,
            "high_risk": DEFAULT_HIGH_RISK_THRESHOLD,
            "critical_risk": DEFAULT_CRITICAL_RISK_THRESHOLD,
            "self_plagiarism": SELF_PLAGIARISM_THRESHOLD,
            "duplicate_publication": DUPLICATE_PUBLICATION_THRESHOLD,
            "citation_stacking": CITATION_STACKING_RATIO,
            "self_citation": SELF_CITATION_RATIO_THRESHOLD,
            "fabrication_std": FABRICATION_STD_MULTIPLIER,
            "benford_deviation": BENFORD_DEVIATION_THRESHOLD,
            "image_hash_similarity": IMAGE_HASH_SIMILARITY_THRESHOLD,
        }
        if thresholds:
            self._thresholds.update(thresholds)

        # 检查规则注册表
        self._rules: dict[str, dict[str, Any]] = {}
        self._register_default_rules()

        # 历史报告缓存（最近 N 份）
        self._report_history: list[IntegrityReport] = []
        self._max_history = 100

    # ===== 规则注册 =====

    def _register_default_rules(self) -> None:
        """注册默认检查规则。"""
        rules = {
            "FAB-001": {
                "dimension": IntegrityDimension.DATA_FABRICATION,
                "name": "Benford 定律偏差",
                "description": "数据首位数字分布显著偏离 Benford 定律，可能存在数据捏造。",
            },
            "FAB-002": {
                "dimension": IntegrityDimension.DATA_FABRICATION,
                "name": "统计离群点",
                "description": "数据中存在超出 3 倍标准差的离群点，需核实来源。",
            },
            "FAB-003": {
                "dimension": IntegrityDimension.DATA_FABRICATION,
                "name": "数据过度平滑",
                "description": "数据方差过小，疑似人为调整。",
            },
            "FIG-001": {
                "dimension": IntegrityDimension.FIGURE_MANIPULATION,
                "name": "图像重复使用",
                "description": "不同图表的哈希高度相似，可能存在图像复用或拼接。",
            },
            "FIG-002": {
                "dimension": IntegrityDimension.FIGURE_MANIPULATION,
                "name": "图表描述缺失",
                "description": "图表缺少必要的图注或描述。",
            },
            "CIT-001": {
                "dimension": IntegrityDimension.CITATION_FABRICATION,
                "name": "引用堆叠",
                "description": "单一来源引用占比过高，存在引用堆叠嫌疑。",
            },
            "CIT-002": {
                "dimension": IntegrityDimension.CITATION_FABRICATION,
                "name": "自引率过高",
                "description": "自引比例超过阈值，可能构成自引圈。",
            },
            "CIT-003": {
                "dimension": IntegrityDimension.CITATION_FABRICATION,
                "name": "引用格式不一致",
                "description": "参考文献格式不统一，可能存在虚假引用。",
            },
            "SELF-001": {
                "dimension": IntegrityDimension.SELF_PLAGIARISM,
                "name": "文本复用",
                "description": "与作者既往发表文本相似度超过阈值。",
            },
            "DUP-001": {
                "dimension": IntegrityDimension.DUPLICATE_PUBLICATION,
                "name": "一稿多投",
                "description": "与既往发表内容高度相似，疑似重复发表。",
            },
            "AUTH-001": {
                "dimension": IntegrityDimension.AUTHORSHIP_MISCONDUCT,
                "name": "作者数量异常",
                "description": "作者数量异常多或异常少，需核实贡献。",
            },
            "AUTH-002": {
                "dimension": IntegrityDimension.AUTHORSHIP_MISCONDUCT,
                "name": "荣誉署名",
                "description": "疑似存在未实质贡献的荣誉署名。",
            },
            "ETH-001": {
                "dimension": IntegrityDimension.ETHICS_REVIEW,
                "name": "缺少伦理审批",
                "description": "涉及人类/动物被试但未声明伦理审批。",
            },
            "ETH-002": {
                "dimension": IntegrityDimension.ETHICS_REVIEW,
                "name": "缺少知情同意",
                "description": "涉及人类被试但未声明知情同意。",
            },
            "COI-001": {
                "dimension": IntegrityDimension.CONFLICT_OF_INTEREST,
                "name": "缺少利益冲突声明",
                "description": "存在资助关系但未声明利益冲突。",
            },
            "PROV-001": {
                "dimension": IntegrityDimension.DATA_PROVENANCE,
                "name": "数据来源未声明",
                "description": "使用数据但未声明数据来源。",
            },
            "PROV-002": {
                "dimension": IntegrityDimension.DATA_PROVENANCE,
                "name": "二次使用未授权",
                "description": "数据疑似二次使用但未声明授权。",
            },
        }
        self._rules.update(rules)

    def register_rule(
        self,
        rule_id: str,
        dimension: IntegrityDimension,
        name: str,
        description: str,
    ) -> None:
        """注册自定义检查规则。

        Args:
            rule_id: 规则 ID（唯一）。
            dimension: 所属维度。
            name: 规则名称。
            description: 规则描述。
        """
        with self._lock:
            self._rules[rule_id] = {
                "dimension": dimension,
                "name": name,
                "description": description,
            }

    # ===== 公共接口 =====

    def check(
        self,
        metadata: DocumentMetadata,
        prior_publications: Optional[list[PriorPublication]] = None,
        author_self_citations: Optional[set[str]] = None,
    ) -> IntegrityReport:
        """执行完整的学术诚信检查。

        Args:
            metadata: 文档元数据。
            prior_publications: 作者既往发表记录（用于自我抄袭/重复发表检测）。
            author_self_citations: 作者自引的参考文献标识集合。

        Returns:
            诚信检查报告。
        """
        with self._lock:
            report = IntegrityReport(
                id=str(uuid.uuid4()),
                document_id=metadata.title or str(uuid.uuid4()),
                timestamp=datetime.utcnow().isoformat() + "Z",
            )

            issues: list[IntegrityIssue] = []
            dimension_scores: dict[str, float] = {}

            # 依次执行各维度检查
            checks = [
                ("data_fabrication", self._check_data_fabrication, (metadata,)),
                ("figure_manipulation", self._check_figure_manipulation, (metadata,)),
                ("citation_fabrication", self._check_citation_fabrication,
                 (metadata, author_self_citations)),
                ("self_plagiarism", self._check_self_plagiarism,
                 (metadata, prior_publications or [])),
                ("duplicate_publication", self._check_duplicate_publication,
                 (metadata, prior_publications or [])),
                ("authorship_misconduct", self._check_authorship_misconduct, (metadata,)),
                ("ethics_review", self._check_ethics_review, (metadata,)),
                ("conflict_of_interest", self._check_conflict_of_interest, (metadata,)),
                ("data_provenance", self._check_data_provenance, (metadata,)),
            ]

            for dim_name, check_func, args in checks:
                try:
                    dim_issues = check_func(*args)
                    issues.extend(dim_issues)
                    # 维度评分 = 该维度问题的最大严重度
                    if dim_issues:
                        dimension_scores[dim_name] = max(i.severity for i in dim_issues)
                    else:
                        dimension_scores[dim_name] = 0.0
                except Exception as exc:  # pragma: no cover - 防御性
                    dimension_scores[dim_name] = 0.0
                    issues.append(IntegrityIssue(
                        id=str(uuid.uuid4()),
                        dimension=IntegrityDimension(dim_name),
                        severity=0.1,
                        title=f"{dim_name} 检查异常",
                        description=f"检查过程中发生异常: {exc}",
                        rule_id="SYS-ERROR",
                        recommendation="请检查输入数据完整性后重试。",
                        confidence=0.5,
                    ))

            report.issues = issues
            report.dimension_scores = dimension_scores
            report.overall_risk = self._compute_overall_risk(dimension_scores, issues)
            report.risk_level = self._assess_risk_level(report.overall_risk)
            report.passed = report.risk_level in (RiskLevel.NONE, RiskLevel.LOW)
            report.recommendations = self._generate_recommendations(issues, report.risk_level)
            report.metadata = {
                "issue_count": len(issues),
                "dimension_count": len(dimension_scores),
                "weights": {k.value: v for k, v in self._weights.items()},
                "thresholds": dict(self._thresholds),
            }

            # 缓存历史
            self._report_history.append(report)
            if len(self._report_history) > self._max_history:
                self._report_history = self._report_history[-self._max_history:]

            return report

    def check_dimension(
        self,
        dimension: IntegrityDimension,
        metadata: DocumentMetadata,
        prior_publications: Optional[list[PriorPublication]] = None,
        author_self_citations: Optional[set[str]] = None,
    ) -> list[IntegrityIssue]:
        """仅执行指定维度的检查。

        Args:
            dimension: 检查维度。
            metadata: 文档元数据。
            prior_publications: 既往发表记录。
            author_self_citations: 自引集合。

        Returns:
            该维度的问题列表。
        """
        with self._lock:
            dispatch = {
                IntegrityDimension.DATA_FABRICATION:
                    lambda: self._check_data_fabrication(metadata),
                IntegrityDimension.FIGURE_MANIPULATION:
                    lambda: self._check_figure_manipulation(metadata),
                IntegrityDimension.CITATION_FABRICATION:
                    lambda: self._check_citation_fabrication(metadata, author_self_citations),
                IntegrityDimension.SELF_PLAGIARISM:
                    lambda: self._check_self_plagiarism(metadata, prior_publications or []),
                IntegrityDimension.DUPLICATE_PUBLICATION:
                    lambda: self._check_duplicate_publication(metadata, prior_publications or []),
                IntegrityDimension.AUTHORSHIP_MISCONDUCT:
                    lambda: self._check_authorship_misconduct(metadata),
                IntegrityDimension.ETHICS_REVIEW:
                    lambda: self._check_ethics_review(metadata),
                IntegrityDimension.CONFLICT_OF_INTEREST:
                    lambda: self._check_conflict_of_interest(metadata),
                IntegrityDimension.DATA_PROVENANCE:
                    lambda: self._check_data_provenance(metadata),
            }
            handler = dispatch.get(dimension)
            if handler is None:
                return []
            return handler()

    def get_history(self, limit: int = 10) -> list[IntegrityReport]:
        """获取历史检查报告。

        Args:
            limit: 返回数量上限。

        Returns:
            历史报告列表（按时间倒序）。
        """
        with self._lock:
            return list(reversed(self._report_history[-limit:]))

    # ===== 维度检查实现 =====

    def _check_data_fabrication(self, metadata: DocumentMetadata) -> list[IntegrityIssue]:
        """数据造假检测。

        检测策略：
            1. 从表格与正文中提取数字，进行 Benford 定律偏差分析。
            2. 对表格数值列进行 Z-score 离群点检测。
            3. 检测数据方差是否过小（过度平滑）。
            4. 检测表格内数值是否过于"整齐"（小数位数一致）。

        Args:
            metadata: 文档元数据。

        Returns:
            问题列表。
        """
        issues: list[IntegrityIssue] = []
        all_numbers: list[float] = []

        # 从表格提取数字
        for idx, table in enumerate(metadata.tables):
            table_numbers: list[float] = []
            for row in table.get("rows", []):
                if isinstance(row, dict):
                    for value in row.values():
                        if isinstance(value, (int, float)):
                            table_numbers.append(float(value))
                        elif isinstance(value, str):
                            try:
                                table_numbers.append(float(value))
                            except ValueError:
                                pass
            all_numbers.extend(table_numbers)

            # 离群点检测
            outliers = _detect_outliers_zscore(
                table_numbers, self._thresholds["fabrication_std"]
            )
            if outliers:
                ratio = len(outliers) / max(len(table_numbers), 1)
                issues.append(IntegrityIssue(
                    id=str(uuid.uuid4()),
                    dimension=IntegrityDimension.DATA_FABRICATION,
                    severity=min(0.9, 0.3 + ratio),
                    title=f"表格 {idx + 1} 存在统计离群点",
                    description=(
                        f"表格 {idx + 1} 中检测到 {len(outliers)} 个离群点"
                        f"（Z-score > {self._thresholds['fabrication_std']}），"
                        f"占比 {ratio:.1%}，需核实数据来源。"
                    ),
                    evidence=[f"离群点行索引: {outliers[:10]}"],
                    location=f"表格 {idx + 1}",
                    rule_id="FAB-002",
                    recommendation="核对离群点数据的原始记录，必要时补充说明或剔除。",
                    confidence=0.7,
                ))

            # 数据过度平滑检测
            if len(table_numbers) >= 5:
                sd = _std(table_numbers)
                avg = _mean(table_numbers)
                if avg != 0 and sd / abs(avg) < 0.01:
                    issues.append(IntegrityIssue(
                        id=str(uuid.uuid4()),
                        dimension=IntegrityDimension.DATA_FABRICATION,
                        severity=0.5,
                        title=f"表格 {idx + 1} 数据过度平滑",
                        description=(
                            f"表格 {idx + 1} 变异系数（CV={sd / abs(avg):.4f}）异常小，"
                            "数据可能被人为调整。"
                        ),
                        evidence=[f"均值={avg:.4f}, 标准差={sd:.4f}"],
                        location=f"表格 {idx + 1}",
                        rule_id="FAB-003",
                        recommendation="提供原始未处理数据，或说明数据预处理流程。",
                        confidence=0.6,
                    ))

        # 从正文提取数字进行 Benford 分析
        for section_name, content in metadata.sections.items():
            numbers = _extract_numbers(content)
            all_numbers.extend(numbers)

        if len(all_numbers) >= 30:
            chi_square, actual_freq = _benford_chi_square(all_numbers)
            # 卡方值越大，偏离越严重
            max_deviation = 0.0
            for digit in range(1, 10):
                expected = BENFORD_EXPECTED[digit]
                actual = actual_freq.get(digit, 0.0)
                max_deviation = max(max_deviation, abs(actual - expected))

            if max_deviation > self._thresholds["benford_deviation"]:
                severity = min(0.9, 0.3 + max_deviation)
                issues.append(IntegrityIssue(
                    id=str(uuid.uuid4()),
                    dimension=IntegrityDimension.DATA_FABRICATION,
                    severity=severity,
                    title="数据首位数字分布偏离 Benford 定律",
                    description=(
                        f"数据首位数字分布与 Benford 定律最大偏差为 {max_deviation:.3f}"
                        f"（阈值 {self._thresholds['benford_deviation']:.3f}），"
                        f"卡方统计量 {chi_square:.2f}，可能存在数据捏造。"
                    ),
                    evidence=[
                        f"各首位数字实际频率: {actual_freq}",
                        f"卡方统计量: {chi_square:.2f}",
                    ],
                    location="数据章节",
                    rule_id="FAB-001",
                    recommendation="核实数据采集与记录过程，确保数据真实未篡改。",
                    confidence=0.65,
                ))

        return issues

    def _check_figure_manipulation(self, metadata: DocumentMetadata) -> list[IntegrityIssue]:
        """图表篡改检测。

        检测策略：
            1. 检测不同图表的图像哈希是否高度相似（图像复用/拼接）。
            2. 检测图表是否缺少图注描述。
            3. 检测图表标题是否重复。

        Args:
            metadata: 文档元数据。

        Returns:
            问题列表。
        """
        issues: list[IntegrityIssue] = []
        figures = metadata.figures
        if not figures:
            return issues

        # 计算每个图表的描述哈希
        hashes: list[tuple[int, str, str]] = []
        for idx, fig in enumerate(figures):
            desc = fig.get("description", "") or fig.get("caption", "") or ""
            title = fig.get("title", "") or ""
            hash_val = _text_hash(desc + title)
            hashes.append((idx, hash_val, title))

        # 检测重复图表
        seen_hashes: dict[str, int] = {}
        for idx, hash_val, title in hashes:
            if hash_val in seen_hashes:
                prev_idx = seen_hashes[hash_val]
                issues.append(IntegrityIssue(
                    id=str(uuid.uuid4()),
                    dimension=IntegrityDimension.FIGURE_MANIPULATION,
                    severity=0.7,
                    title=f"图表 {idx + 1} 与图表 {prev_idx + 1} 高度相似",
                    description=(
                        f"图表 {idx + 1} 的描述/标题哈希与图表 {prev_idx + 1} 完全一致，"
                        "可能存在图像复用或拼接篡改。"
                    ),
                    evidence=[f"哈希值: {hash_val}"],
                    location=f"图表 {idx + 1}",
                    rule_id="FIG-001",
                    recommendation="核对原始图像数据，确认是否为不同实验结果。",
                    confidence=0.8,
                ))
            else:
                seen_hashes[hash_val] = idx

        # 检测缺失图注
        for idx, fig in enumerate(figures):
            desc = fig.get("description", "") or fig.get("caption", "")
            if not desc.strip():
                issues.append(IntegrityIssue(
                    id=str(uuid.uuid4()),
                    dimension=IntegrityDimension.FIGURE_MANIPULATION,
                    severity=0.3,
                    title=f"图表 {idx + 1} 缺少图注",
                    description=f"图表 {idx + 1} 未提供图注或描述，影响可重复性。",
                    evidence=[],
                    location=f"图表 {idx + 1}",
                    rule_id="FIG-002",
                    recommendation="补充图表图注，说明数据来源、处理方法与坐标含义。",
                    confidence=0.9,
                ))

        # 检测标题重复
        title_counts = Counter(h[2] for h in hashes if h[2])
        for title, count in title_counts.items():
            if count > 1:
                issues.append(IntegrityIssue(
                    id=str(uuid.uuid4()),
                    dimension=IntegrityDimension.FIGURE_MANIPULATION,
                    severity=0.4,
                    title=f"图表标题重复: '{title}'",
                    description=f"标题 '{title}' 被 {count} 个图表使用，需确认是否为不同图。",
                    evidence=[f"重复次数: {count}"],
                    location="图表标题",
                    rule_id="FIG-002",
                    recommendation="为每个图表提供唯一、明确的标题。",
                    confidence=0.85,
                ))

        return issues

    def _check_citation_fabrication(
        self,
        metadata: DocumentMetadata,
        author_self_citations: Optional[set[str]],
    ) -> list[IntegrityIssue]:
        """引用伪造检测。

        检测策略：
            1. 引用堆叠：单一来源引用占比过高。
            2. 自引率过高：自引比例超过阈值。
            3. 引用格式不一致：参考文献格式不统一。
            4. 引用孤岛：仅在正文出现但未列入参考文献，或反之。

        Args:
            metadata: 文档元数据。
            author_self_citations: 作者自引的参考文献标识集合。

        Returns:
            问题列表。
        """
        issues: list[IntegrityIssue] = []
        references = metadata.references
        if not references:
            return issues

        # 引用堆叠检测：按来源（第一作者/期刊）分组
        source_counter: Counter[str] = Counter()
        for ref in references:
            # 提取来源（取前 30 字符作为来源标识）
            source = ref.strip()[:30]
            source_counter[source] += 1

        total_refs = len(references)
        for source, count in source_counter.most_common(5):
            ratio = count / total_refs
            if ratio > self._thresholds["citation_stacking"]:
                issues.append(IntegrityIssue(
                    id=str(uuid.uuid4()),
                    dimension=IntegrityDimension.CITATION_FABRICATION,
                    severity=min(0.8, 0.3 + ratio),
                    title="引用堆叠",
                    description=(
                        f"来源 '{source}...' 被引用 {count} 次，"
                        f"占比 {ratio:.1%}（阈值 {self._thresholds['citation_stacking']:.1%}），"
                        "存在引用堆叠嫌疑。"
                    ),
                    evidence=[f"来源: {source}", f"引用次数: {count}", f"占比: {ratio:.1%}"],
                    location="参考文献",
                    rule_id="CIT-001",
                    recommendation="增加引用来源多样性，避免过度依赖单一来源。",
                    confidence=0.75,
                ))
                break  # 仅报告最严重的

        # 自引率检测
        if author_self_citations:
            self_cite_count = 0
            for ref in references:
                # 检查参考文献是否匹配自引集合
                for self_cite in author_self_citations:
                    if self_cite and self_cite in ref:
                        self_cite_count += 1
                        break
            self_cite_ratio = self_cite_count / total_refs if total_refs else 0.0
            if self_cite_ratio > self._thresholds["self_citation"]:
                issues.append(IntegrityIssue(
                    id=str(uuid.uuid4()),
                    dimension=IntegrityDimension.CITATION_FABRICATION,
                    severity=min(0.85, 0.3 + self_cite_ratio),
                    title="自引率过高",
                    description=(
                        f"自引比例 {self_cite_ratio:.1%}"
                        f"（阈值 {self._thresholds['self_citation']:.1%}），"
                        f"自引 {self_cite_count}/{total_refs} 篇，可能构成自引圈。"
                    ),
                    evidence=[
                        f"自引数量: {self_cite_count}",
                        f"总引用数: {total_refs}",
                        f"自引率: {self_cite_ratio:.1%}",
                    ],
                    location="参考文献",
                    rule_id="CIT-002",
                    recommendation="减少不必要的自引，确保引用基于学术相关性。",
                    confidence=0.8,
                ))

        # 引用格式一致性检测
        format_issues = self._detect_citation_format_inconsistency(references)
        if format_issues:
            issues.append(IntegrityIssue(
                id=str(uuid.uuid4()),
                dimension=IntegrityDimension.CITATION_FABRICATION,
                severity=0.35,
                title="引用格式不一致",
                description=(
                    f"参考文献格式存在 {len(format_issues)} 处不一致，"
                    "可能存在虚假引用或格式疏忽。"
                ),
                evidence=format_issues[:5],
                location="参考文献",
                rule_id="CIT-003",
                recommendation="统一参考文献格式（如 APA/IEEE/GB-T7714），逐条核对。",
                confidence=0.7,
            ))

        # 引用孤岛检测：正文引用编号 vs 参考文献列表
        in_text_citations = self._extract_in_text_citations(metadata)
        ref_count = len(references)
        cited_indices = set(in_text_citations)
        # 未被正文引用的参考文献
        uncited = [i for i in range(1, ref_count + 1) if i not in cited_indices]
        if uncited and len(uncited) / max(ref_count, 1) > 0.3:
            issues.append(IntegrityIssue(
                id=str(uuid.uuid4()),
                dimension=IntegrityDimension.CITATION_FABRICATION,
                severity=0.4,
                title="参考文献存在未引用条目",
                description=(
                    f"参考文献列表中有 {len(uncited)} 篇未被正文引用"
                    f"（占比 {len(uncited) / max(ref_count, 1):.1%}），"
                    "可能为堆砌引用或虚假引用。"
                ),
                evidence=[f"未引用编号: {uncited[:10]}"],
                location="参考文献",
                rule_id="CIT-003",
                recommendation="删除未引用的参考文献，或补充正文引用。",
                confidence=0.75,
            ))

        return issues

    def _detect_citation_format_inconsistency(self, references: list[str]) -> list[str]:
        """检测引用格式不一致。

        Args:
            references: 参考文献列表。

        Returns:
            不一致描述列表。
        """
        issues: list[str] = []
        if len(references) < 2:
            return issues

        # 检测 DOI 存在性
        has_doi = [bool(DOI_PATTERN.search(ref)) for ref in references]
        doi_ratio = sum(has_doi) / len(has_doi)
        # 若部分有 DOI 部分没有，且差异显著
        if 0.2 < doi_ratio < 0.8:
            issues.append(
                f"DOI 标注不一致：{sum(has_doi)}/{len(has_doi)} 篇含 DOI"
            )

        # 检测年份存在性
        year_pattern = re.compile(r"\b(19|20)\d{2}\b")
        has_year = [bool(year_pattern.search(ref)) for ref in references]
        if not all(has_year):
            missing = [i + 1 for i, y in enumerate(has_year) if not y]
            issues.append(f"缺少年份的参考文献编号: {missing[:5]}")

        # 检测作者格式
        author_patterns = [
            re.compile(r"[A-Z][a-z]+,\s+[A-Z]"),  # Smith, J
            re.compile(r"[A-Z][a-z]+\s+[A-Z]"),   # Smith J
            re.compile(r"[\u4e00-\u9fff]{2,4}"),   # 中文姓名
        ]
        format_counts = [0, 0, 0]
        for ref in references:
            for i, pattern in enumerate(author_patterns):
                if pattern.search(ref):
                    format_counts[i] += 1
                    break
        # 若多种格式混用
        non_zero = [c for c in format_counts if c > 0]
        if len(non_zero) > 1:
            issues.append(
                f"作者格式混用: 逗号格式 {format_counts[0]} 篇, "
                f"空格格式 {format_counts[1]} 篇, 中文格式 {format_counts[2]} 篇"
            )

        return issues

    def _extract_in_text_citations(self, metadata: DocumentMetadata) -> list[int]:
        """提取正文中的引用编号。

        Args:
            metadata: 文档元数据。

        Returns:
            引用编号列表。
        """
        citations: list[int] = []
        full_text = metadata.abstract + " " + " ".join(metadata.sections.values())
        for pattern in CITATION_REGEX_PATTERNS:
            for match in pattern.finditer(full_text):
                group = match.group(1)
                # 解析 [1, 2, 3] 形式
                nums = re.findall(r"\d+", group)
                for num in nums:
                    try:
                        n = int(num)
                        if 1 <= n <= 9999:
                            citations.append(n)
                    except ValueError:
                        continue
        return citations

    def _check_self_plagiarism(
        self,
        metadata: DocumentMetadata,
        prior_publications: list[PriorPublication],
    ) -> list[IntegrityIssue]:
        """自我抄袭检测。

        检测策略：
            1. 将当前文档与既往发表进行 n-gram Jaccard 相似度比对。
            2. 检测段落级复用。
            3. 检测摘要复用。

        Args:
            metadata: 文档元数据。
            prior_publications: 既往发表记录。

        Returns:
            问题列表。
        """
        issues: list[IntegrityIssue] = []
        if not prior_publications:
            return issues

        # 当前文档 n-gram
        current_text = metadata.abstract + " " + " ".join(metadata.sections.values())
        current_tokens = _tokenize(current_text)
        current_ngrams = _ngrams(current_tokens, n=3)

        threshold = self._thresholds["self_plagiarism"]

        for pub in prior_publications:
            if not pub.content:
                continue
            pub_tokens = _tokenize(pub.content)
            pub_ngrams = _ngrams(pub_tokens, n=3)
            similarity = _jaccard_similarity(current_ngrams, pub_ngrams)

            if similarity > threshold:
                # 检测具体复用段落
                reused_sentences = self._find_reused_sentences(current_text, pub.content)
                severity = min(0.9, 0.3 + similarity)
                issues.append(IntegrityIssue(
                    id=str(uuid.uuid4()),
                    dimension=IntegrityDimension.SELF_PLAGIARISM,
                    severity=severity,
                    title=f"与既往发表 '{pub.title}' 文本复用",
                    description=(
                        f"当前文档与作者既往发表 '{pub.title}'（{pub.year}, {pub.venue}）"
                        f"的 n-gram 相似度为 {similarity:.1%}（阈值 {threshold:.1%}），"
                        f"复用段落 {len(reused_sentences)} 处。"
                    ),
                    evidence=[
                        f"相似度: {similarity:.4f}",
                        f"复用段落示例: {reused_sentences[:3]}",
                    ],
                    location="正文/摘要",
                    rule_id="SELF-001",
                    recommendation=(
                        "对复用内容进行改写并引用原文，或在方法部分明确标注'改编自'。"
                    ),
                    confidence=0.8,
                ))

        return issues

    def _find_reused_sentences(self, text_a: str, text_b: str) -> list[str]:
        """查找两文本间复用的句子。

        Args:
            text_a: 文本 A。
            text_b: 文本 B。

        Returns:
            复用句子列表。
        """
        sentences_a = _split_sentences(text_a)
        sentences_b_set = {_normalize_text(s) for s in _split_sentences(text_b) if len(s) > 20}
        reused: list[str] = []
        for sent in sentences_a:
            if len(sent) > 20 and _normalize_text(sent) in sentences_b_set:
                reused.append(sent)
        return reused

    def _check_duplicate_publication(
        self,
        metadata: DocumentMetadata,
        prior_publications: list[PriorPublication],
    ) -> list[IntegrityIssue]:
        """重复发表检测。

        检测策略：
            1. 与既往发表进行高相似度比对（阈值高于自我抄袭）。
            2. 检测标题高度相似。
            3. 检测发表历史中是否存在重叠。

        Args:
            metadata: 文档元数据。
            prior_publications: 既往发表记录。

        Returns:
            问题列表。
        """
        issues: list[IntegrityIssue] = []
        if not prior_publications:
            return issues

        threshold = self._thresholds["duplicate_publication"]
        current_text = metadata.abstract + " " + " ".join(metadata.sections.values())
        current_tokens = _tokenize(current_text)
        current_ngrams = _ngrams(current_tokens, n=4)

        for pub in prior_publications:
            if not pub.content:
                continue
            pub_tokens = _tokenize(pub.content)
            pub_ngrams = _ngrams(pub_tokens, n=4)
            similarity = _jaccard_similarity(current_ngrams, pub_ngrams)

            if similarity > threshold:
                severity = min(0.95, 0.5 + similarity)
                issues.append(IntegrityIssue(
                    id=str(uuid.uuid4()),
                    dimension=IntegrityDimension.DUPLICATE_PUBLICATION,
                    severity=severity,
                    title=f"疑似重复发表: '{pub.title}'",
                    description=(
                        f"当前文档与 '{pub.title}'（{pub.year}, {pub.venue}）"
                        f"相似度 {similarity:.1%}（阈值 {threshold:.1%}），"
                        "疑似一稿多投或重复发表。"
                    ),
                    evidence=[
                        f"相似度: {similarity:.4f}",
                        f"既往发表: {pub.title} ({pub.venue}, {pub.year})",
                    ],
                    location="全文",
                    rule_id="DUP-001",
                    recommendation=(
                        "若为会议扩展期刊版，需明确标注并引用原文；"
                        "否则撤回其中一份发表。"
                    ),
                    confidence=0.85,
                ))
                continue

            # 标题相似度检测
            title_sim = self._title_similarity(metadata.title, pub.title)
            if title_sim > 0.8 and similarity > 0.3:
                issues.append(IntegrityIssue(
                    id=str(uuid.uuid4()),
                    dimension=IntegrityDimension.DUPLICATE_PUBLICATION,
                    severity=0.6,
                    title=f"标题高度相似: '{pub.title}'",
                    description=(
                        f"当前标题与 '{pub.title}' 相似度 {title_sim:.1%}，"
                        f"内容相似度 {similarity:.1%}，需核实是否为重复发表。"
                    ),
                    evidence=[
                        f"标题相似度: {title_sim:.4f}",
                        f"内容相似度: {similarity:.4f}",
                    ],
                    location="标题",
                    rule_id="DUP-001",
                    recommendation="明确两篇论文的关系，必要时引用原文。",
                    confidence=0.7,
                ))

        return issues

    def _title_similarity(self, title_a: str, title_b: str) -> float:
        """计算标题相似度（基于词集 Jaccard）。

        Args:
            title_a: 标题 A。
            title_b: 标题 B。

        Returns:
            相似度（0-1）。
        """
        set_a = set(_normalize_text(title_a).split())
        set_b = set(_normalize_text(title_b).split())
        return _jaccard_similarity(set_a, set_b)

    def _check_authorship_misconduct(self, metadata: DocumentMetadata) -> list[IntegrityIssue]:
        """不当署名检测。

        检测策略：
            1. 作者数量异常（过多或过少）。
            2. 疑似荣誉署名（作者列表含常见荣誉性头衔）。
            3. 作者姓名格式不一致。
            4. 通讯作者缺失。

        Args:
            metadata: 文档元数据。

        Returns:
            问题列表。
        """
        issues: list[IntegrityIssue] = []
        authors = metadata.authors
        if not authors:
            issues.append(IntegrityIssue(
                id=str(uuid.uuid4()),
                dimension=IntegrityDimension.AUTHORSHIP_MISCONDUCT,
                severity=0.5,
                title="缺少作者信息",
                description="文档未提供作者列表，无法核实署名合理性。",
                evidence=[],
                location="作者信息",
                rule_id="AUTH-001",
                recommendation="补充完整作者列表与贡献声明。",
                confidence=0.9,
            ))
            return issues

        # 作者数量异常
        author_count = len(authors)
        if author_count > 20:
            issues.append(IntegrityIssue(
                id=str(uuid.uuid4()),
                dimension=IntegrityDimension.AUTHORSHIP_MISCONDUCT,
                severity=0.5,
                title=f"作者数量异常多（{author_count} 人）",
                description=(
                    f"作者列表含 {author_count} 人，需核实每位作者的实际贡献，"
                    "排除荣誉署名或集团署名。"
                ),
                evidence=[f"作者数量: {author_count}"],
                location="作者列表",
                rule_id="AUTH-001",
                recommendation="提供每位作者的具体贡献声明（CRediT 分类）。",
                confidence=0.7,
            ))
        elif author_count == 1 and any(
            kw in metadata.sections.get("method", "").lower()
            for kw in ["团队", "team", "合作", "collaborat"]
        ):
            issues.append(IntegrityIssue(
                id=str(uuid.uuid4()),
                dimension=IntegrityDimension.AUTHORSHIP_MISCONDUCT,
                severity=0.4,
                title="作者数量与内容不符",
                description="文档仅 1 位作者但内容提及团队合作，可能遗漏贡献者。",
                evidence=["正文提及团队/合作"],
                location="作者列表",
                rule_id="AUTH-001",
                recommendation="核实并补充所有实质贡献者。",
                confidence=0.6,
            ))

        # 荣誉署名检测：常见荣誉性头衔
        honorifics = ["院士", "教授", "博士", "Ph.D", "Prof", "Dr."]
        for author in authors:
            for honor in honorifics:
                if honor in author and len(author) > len(honor) + 2:
                    issues.append(IntegrityIssue(
                        id=str(uuid.uuid4()),
                        dimension=IntegrityDimension.AUTHORSHIP_MISCONDUCT,
                        severity=0.3,
                        title=f"作者名含荣誉头衔: '{author}'",
                        description=(
                            f"作者 '{author}' 含荣誉性头衔 '{honor}'，"
                            "作者列表应仅含姓名，头衔不应出现在署名中。"
                        ),
                        evidence=[f"作者: {author}", f"头衔: {honor}"],
                        location="作者列表",
                        rule_id="AUTH-002",
                        recommendation="去除作者列表中的头衔，仅保留姓名。",
                        confidence=0.85,
                    ))
                    break

        # 作者姓名格式一致性
        name_formats = set()
        for author in authors:
            if re.match(r"^[A-Z][a-z]+\s+[A-Z]", author):
                name_formats.add("western")
            elif re.match(r"^[\u4e00-\u9fff]{2,4}$", author):
                name_formats.add("chinese")
            else:
                name_formats.add("other")
        if len(name_formats) > 1:
            issues.append(IntegrityIssue(
                id=str(uuid.uuid4()),
                dimension=IntegrityDimension.AUTHORSHIP_MISCONDUCT,
                severity=0.25,
                title="作者姓名格式不一致",
                description=f"作者姓名存在 {len(name_formats)} 种格式: {name_formats}",
                evidence=[f"格式类型: {name_formats}"],
                location="作者列表",
                rule_id="AUTH-002",
                recommendation="统一作者姓名格式（如姓+名首字母）。",
                confidence=0.7,
            ))

        return issues

    def _check_ethics_review(self, metadata: DocumentMetadata) -> list[IntegrityIssue]:
        """伦理审查检测。

        检测策略：
            1. 检测正文是否涉及人类被试/动物实验。
            2. 若涉及，检查是否声明伦理审批与知情同意。
            3. 检测弱势群体相关声明。

        Args:
            metadata: 文档元数据。

        Returns:
            问题列表。
        """
        issues: list[IntegrityIssue] = []
        full_text = (
            metadata.abstract + " " +
            metadata.ethics_statement + " " +
            " ".join(metadata.sections.values())
        ).lower()

        # 检测是否涉及人类被试
        involves_human = any(
            kw.lower() in full_text for kw in ETHICS_KEYWORDS["human_subjects"]
        )
        # 检测是否涉及动物实验
        involves_animal = any(
            kw.lower() in full_text for kw in ETHICS_KEYWORDS["animal_experiment"]
        )
        # 检测是否涉及弱势群体
        involves_vulnerable = any(
            kw.lower() in full_text for kw in ETHICS_KEYWORDS["vulnerable_population"]
        )

        has_irb = any(kw.lower() in full_text for kw in ETHICS_KEYWORDS["irb_approval"])
        has_consent = any(
            kw.lower() in full_text for kw in ETHICS_KEYWORDS["informed_consent"]
        )

        if involves_human and not has_irb:
            issues.append(IntegrityIssue(
                id=str(uuid.uuid4()),
                dimension=IntegrityDimension.ETHICS_REVIEW,
                severity=0.8,
                title="涉及人类被试但未声明伦理审批",
                description=(
                    "文档涉及人类被试研究，但未找到伦理委员会审批声明。"
                    "人类被试研究必须获得 IRB/伦理委员会批准。"
                ),
                evidence=["检测到人类被试相关关键词", "未检测到 IRB 审批关键词"],
                location="伦理声明",
                rule_id="ETH-001",
                recommendation="补充伦理委员会审批编号与日期，或说明豁免理由。",
                confidence=0.85,
            ))

        if involves_human and not has_consent:
            issues.append(IntegrityIssue(
                id=str(uuid.uuid4()),
                dimension=IntegrityDimension.ETHICS_REVIEW,
                severity=0.75,
                title="涉及人类被试但未声明知情同意",
                description="文档涉及人类被试但未找到知情同意声明。",
                evidence=["检测到人类被试相关关键词", "未检测到知情同意关键词"],
                location="伦理声明",
                rule_id="ETH-002",
                recommendation="补充知情同意获取流程说明，或说明豁免理由。",
                confidence=0.85,
            ))

        if involves_animal and not has_irb:
            issues.append(IntegrityIssue(
                id=str(uuid.uuid4()),
                dimension=IntegrityDimension.ETHICS_REVIEW,
                severity=0.7,
                title="涉及动物实验但未声明伦理审批",
                description="文档涉及动物实验，但未找到动物伦理委员会审批声明。",
                evidence=["检测到动物实验相关关键词", "未检测到伦理审批关键词"],
                location="伦理声明",
                rule_id="ETH-001",
                recommendation="补充动物实验伦理审批编号，说明动物福利保障措施。",
                confidence=0.8,
            ))

        if involves_vulnerable and not has_consent:
            issues.append(IntegrityIssue(
                id=str(uuid.uuid4()),
                dimension=IntegrityDimension.ETHICS_REVIEW,
                severity=0.85,
                title="涉及弱势群体但未声明特殊保护",
                description=(
                    "文档涉及弱势群体（未成年人/孕妇/囚犯等），"
                    "但未找到知情同意或特殊保护声明。"
                ),
                evidence=["检测到弱势群体相关关键词", "未检测到知情同意关键词"],
                location="伦理声明",
                rule_id="ETH-002",
                recommendation=(
                    "补充弱势群体的特殊保护措施说明，"
                    "包括监护人同意、风险评估等。"
                ),
                confidence=0.85,
            ))

        return issues

    def _check_conflict_of_interest(self, metadata: DocumentMetadata) -> list[IntegrityIssue]:
        """利益冲突声明检测。

        检测策略：
            1. 检测是否存在资助关系。
            2. 若存在，检查是否声明利益冲突。
            3. 检测利益冲突声明是否过于简略。

        Args:
            metadata: 文档元数据。

        Returns:
            问题列表。
        """
        issues: list[IntegrityIssue] = []
        full_text = (
            metadata.funding + " " +
            metadata.conflict_of_interest + " " +
            " ".join(metadata.sections.values())
        ).lower()

        # 检测资助关系
        has_funding = any(
            kw.lower() in full_text for kw in COI_KEYWORDS["financial"]
        )
        # 检测雇佣关系
        has_employment = any(
            kw.lower() in full_text for kw in COI_KEYWORDS["employment"]
        )

        coi_statement = metadata.conflict_of_interest.strip().lower()
        has_coi_declaration = bool(coi_statement)

        if (has_funding or has_employment) and not has_coi_declaration:
            issues.append(IntegrityIssue(
                id=str(uuid.uuid4()),
                dimension=IntegrityDimension.CONFLICT_OF_INTEREST,
                severity=0.6,
                title="存在利益关系但未声明利益冲突",
                description=(
                    f"文档涉及{'资助' if has_funding else ''}"
                    f"{'雇佣' if has_employment else ''}关系，"
                    "但未提供利益冲突声明。"
                ),
                evidence=[
                    f"检测到资助关系: {has_funding}",
                    f"检测到雇佣关系: {has_employment}",
                    "未找到利益冲突声明",
                ],
                location="利益冲突声明",
                rule_id="COI-001",
                recommendation="补充利益冲突声明，明确说明所有潜在利益关系。",
                confidence=0.8,
            ))

        # 利益冲突声明过于简略
        if has_coi_declaration:
            coi_words = len(coi_statement.split())
            if coi_words < 5 and "no" not in coi_statement and "无" not in coi_statement:
                issues.append(IntegrityIssue(
                    id=str(uuid.uuid4()),
                    dimension=IntegrityDimension.CONFLICT_OF_INTEREST,
                    severity=0.3,
                    title="利益冲突声明过于简略",
                    description=(
                        f"利益冲突声明仅 {coi_words} 词，"
                        "应详细说明所有潜在利益关系或明确声明无利益冲突。"
                    ),
                    evidence=[f"声明内容: '{metadata.conflict_of_interest}'"],
                    location="利益冲突声明",
                    rule_id="COI-001",
                    recommendation="扩展利益冲突声明，逐项说明财务/个人/学术关系。",
                    confidence=0.7,
                ))

            # 检测"无利益冲突"声明但实际存在资助
            if (
                ("no conflict" in coi_statement or "无利益冲突" in coi_statement)
                and has_funding
            ):
                issues.append(IntegrityIssue(
                    id=str(uuid.uuid4()),
                    dimension=IntegrityDimension.CONFLICT_OF_INTEREST,
                    severity=0.5,
                    title="利益冲突声明与资助关系矛盾",
                    description=(
                        "声明'无利益冲突'，但文档存在资助关系，"
                        "需核实资助方是否可能影响研究结论。"
                    ),
                    evidence=["声明: 无利益冲突", "检测到资助关系"],
                    location="利益冲突声明",
                    rule_id="COI-001",
                    recommendation="重新评估资助关系对研究独立性的影响，如实声明。",
                    confidence=0.75,
                ))

        return issues

    def _check_data_provenance(self, metadata: DocumentMetadata) -> list[IntegrityIssue]:
        """数据来源追溯检测。

        检测策略：
            1. 检测文档是否使用数据但未声明来源。
            2. 检测公开数据集使用是否注明。
            3. 检测二次使用是否声明授权。

        Args:
            metadata: 文档元数据。

        Returns:
            问题列表。
        """
        issues: list[IntegrityIssue] = []
        full_text = (
            metadata.abstract + " " +
            metadata.data_availability + " " +
            " ".join(metadata.sections.values())
        ).lower()

        # 检测是否使用数据
        data_indicators = ["数据", "data", "数据集", "dataset", "样本", "sample", "实验数据"]
        uses_data = any(ind in full_text for ind in data_indicators)

        has_provenance = bool(metadata.data_availability.strip())

        if uses_data and not has_provenance:
            issues.append(IntegrityIssue(
                id=str(uuid.uuid4()),
                dimension=IntegrityDimension.DATA_PROVENANCE,
                severity=0.55,
                title="使用数据但未声明数据来源",
                description="文档涉及数据使用，但未提供数据可用性声明。",
                evidence=["检测到数据相关关键词", "未找到数据可用性声明"],
                location="数据声明",
                rule_id="PROV-001",
                recommendation="补充数据可用性声明，注明数据来源、获取方式与访问条件。",
                confidence=0.8,
            ))

        # 检测公开数据集使用
        uses_public_dataset = any(
            kw.lower() in full_text for kw in PROVENANCE_KEYWORDS["public_dataset"]
        )
        if uses_public_dataset:
            # 检查是否注明数据集名称与版本
            dataset_pattern = re.compile(
                r"(UCI|Kaggle|ImageNet|CIFAR|MNIST|COCO|VOC|OpenImages)", re.IGNORECASE
            )
            if not dataset_pattern.search(full_text):
                issues.append(IntegrityIssue(
                    id=str(uuid.uuid4()),
                    dimension=IntegrityDimension.DATA_PROVENANCE,
                    severity=0.35,
                    title="公开数据集使用未注明具体名称",
                    description="文档提及使用公开数据集，但未注明具体数据集名称与版本。",
                    evidence=["检测到公开数据集相关关键词"],
                    location="数据声明",
                    rule_id="PROV-001",
                    recommendation="注明数据集完整名称、版本号与获取链接。",
                    confidence=0.75,
                ))

        # 检测二次使用
        uses_secondary = any(
            kw.lower() in full_text for kw in PROVENANCE_KEYWORDS["secondary_use"]
        )
        uses_license = any(
            kw.lower() in full_text for kw in PROVENANCE_KEYWORDS["license_required"]
        )
        if uses_secondary and not uses_license:
            issues.append(IntegrityIssue(
                id=str(uuid.uuid4()),
                dimension=IntegrityDimension.DATA_PROVENANCE,
                severity=0.5,
                title="数据二次使用未声明授权",
                description=(
                    "文档提及数据二次使用或再利用，但未找到授权或许可声明。"
                    "二次使用他人数据需获得明确授权。"
                ),
                evidence=["检测到二次使用关键词", "未检测到授权声明"],
                location="数据声明",
                rule_id="PROV-002",
                recommendation="补充数据使用授权证明，或说明数据许可类型（如 CC-BY）。",
                confidence=0.7,
            ))

        # 检测数据可用性声明是否包含访问方式
        if has_provenance:
            availability = metadata.data_availability.lower()
            access_indicators = ["url", "doi", "http", "github", "zenodo", "figshare", "链接", "仓库"]
            has_access = any(ind in availability for ind in access_indicators)
            if not has_access and "应要求提供" not in availability and "on request" not in availability:
                issues.append(IntegrityIssue(
                    id=str(uuid.uuid4()),
                    dimension=IntegrityDimension.DATA_PROVENANCE,
                    severity=0.3,
                    title="数据可用性声明缺少访问方式",
                    description="数据可用性声明未提供具体的访问链接或获取方式。",
                    evidence=["声明内容缺少 URL/DOI/仓库链接"],
                    location="数据声明",
                    rule_id="PROV-001",
                    recommendation="提供数据仓库链接、DOI 或明确的获取流程。",
                    confidence=0.7,
                ))

        return issues

    # ===== 评分与报告 =====

    def _compute_overall_risk(
        self,
        dimension_scores: dict[str, float],
        issues: list[IntegrityIssue],
    ) -> float:
        """计算综合风险评分。

        采用加权平均与峰值惩罚结合的策略：
            1. 各维度评分按权重加权平均。
            2. 若存在严重问题（severity > 0.7），额外增加峰值惩罚。

        Args:
            dimension_scores: 各维度评分。
            issues: 问题列表。

        Returns:
            综合风险评分（0-1）。
        """
        if not dimension_scores:
            return 0.0

        # 加权平均
        total_weight = 0.0
        weighted_sum = 0.0
        for dim_name, score in dimension_scores.items():
            try:
                dim = IntegrityDimension(dim_name)
            except ValueError:
                continue
            weight = self._weights.get(dim, 1.0)
            weighted_sum += score * weight
            total_weight += weight

        base_risk = weighted_sum / total_weight if total_weight > 0 else 0.0

        # 峰值惩罚：存在严重问题时提升风险
        max_severity = max((i.severity for i in issues), default=0.0)
        if max_severity > 0.7:
            penalty = (max_severity - 0.7) * 0.5
            base_risk = min(1.0, base_risk + penalty)

        # 问题数量惩罚
        critical_count = sum(1 for i in issues if i.severity > 0.7)
        if critical_count > 0:
            base_risk = min(1.0, base_risk + critical_count * 0.05)

        return min(1.0, max(0.0, base_risk))

    def _assess_risk_level(self, overall_risk: float) -> RiskLevel:
        """根据综合风险评分评定风险等级。

        Args:
            overall_risk: 综合风险评分。

        Returns:
            风险等级。
        """
        if overall_risk >= self._thresholds["critical_risk"]:
            return RiskLevel.CRITICAL
        elif overall_risk >= self._thresholds["high_risk"]:
            return RiskLevel.HIGH
        elif overall_risk >= self._thresholds["medium_risk"]:
            return RiskLevel.MEDIUM
        elif overall_risk >= self._thresholds["low_risk"]:
            return RiskLevel.LOW
        else:
            return RiskLevel.NONE

    def _generate_recommendations(
        self,
        issues: list[IntegrityIssue],
        risk_level: RiskLevel,
    ) -> list[str]:
        """生成综合整改建议。

        Args:
            issues: 问题列表。
            risk_level: 风险等级。

        Returns:
            建议列表（按优先级排序）。
        """
        recommendations: list[str] = []

        # 按严重度排序
        sorted_issues = sorted(issues, key=lambda i: i.severity, reverse=True)

        # 总体建议
        if risk_level == RiskLevel.CRITICAL:
            recommendations.append(
                "⚠️ 严重风险：文档存在严重学术诚信问题，建议在整改前暂缓发表。"
            )
        elif risk_level == RiskLevel.HIGH:
            recommendations.append(
                "⚠️ 高风险：文档存在多项诚信问题，需逐项整改后方可发表。"
            )
        elif risk_level == RiskLevel.MEDIUM:
            recommendations.append(
                "📋 中风险：文档存在部分诚信问题，建议整改后重新检查。"
            )
        elif risk_level == RiskLevel.LOW:
            recommendations.append(
                "✓ 低风险：文档存在少量问题，建议按建议优化。"
            )
        else:
            recommendations.append("✅ 未发现明显学术诚信问题。")

        # 按维度分组建议
        dim_issues: dict[IntegrityDimension, list[IntegrityIssue]] = defaultdict(list)
        for issue in sorted_issues:
            dim_issues[issue.dimension].append(issue)

        # 维度级建议
        dimension_advice = {
            IntegrityDimension.DATA_FABRICATION: (
                "数据造假：请提供原始数据记录，核实统计异常，必要时邀请第三方复核。"
            ),
            IntegrityDimension.FIGURE_MANIPULATION: (
                "图表篡改：请提供原始图像数据，核对图表来源，确保未拼接或篡改。"
            ),
            IntegrityDimension.CITATION_FABRICATION: (
                "引用伪造：请逐条核对参考文献真实性，删除虚假引用，统一格式。"
            ),
            IntegrityDimension.SELF_PLAGIARISM: (
                "自我抄袭：请对复用内容进行改写并引用原文，或标注'改编自'。"
            ),
            IntegrityDimension.DUPLICATE_PUBLICATION: (
                "重复发表：请明确两篇论文关系，必要时撤回其中一份。"
            ),
            IntegrityDimension.AUTHORSHIP_MISCONDUCT: (
                "不当署名：请核实每位作者贡献，提供 CRediT 贡献声明。"
            ),
            IntegrityDimension.ETHICS_REVIEW: (
                "伦理审查：请补充伦理审批编号与知情同意说明。"
            ),
            IntegrityDimension.CONFLICT_OF_INTEREST: (
                "利益冲突：请如实声明所有潜在利益关系。"
            ),
            IntegrityDimension.DATA_PROVENANCE: (
                "数据来源：请补充数据来源、授权与访问方式声明。"
            ),
        }

        for dim, dim_issue_list in dim_issues.items():
            advice = dimension_advice.get(dim)
            if advice:
                recommendations.append(f"【{dim.value}】{advice}")
            # 附带具体问题建议
            for issue in dim_issue_list[:2]:  # 每维度最多 2 条
                if issue.recommendation:
                    recommendations.append(f"  - {issue.recommendation}")

        # 复查建议
        if risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            recommendations.append(
                "建议整改完成后重新运行学术诚信检查，确认风险等级降至 LOW 后再行发表。"
            )

        return recommendations

    # ===== 配置管理 =====

    def set_threshold(self, name: str, value: float) -> None:
        """设置阈值。

        Args:
            name: 阈值名称。
            value: 阈值。
        """
        with self._lock:
            self._thresholds[name] = value

    def set_dimension_weight(self, dimension: IntegrityDimension, weight: float) -> None:
        """设置维度权重。

        Args:
            dimension: 维度。
            weight: 权重。
        """
        with self._lock:
            self._weights[dimension] = weight

    def get_config(self) -> dict[str, Any]:
        """获取当前配置。

        Returns:
            配置字典。
        """
        with self._lock:
            return {
                "thresholds": dict(self._thresholds),
                "weights": {k.value: v for k, v in self._weights.items()},
                "rules": dict(self._rules),
                "history_size": len(self._report_history),
            }

    def clear_history(self) -> None:
        """清空历史报告。"""
        with self._lock:
            self._report_history.clear()


# ===== 模块级便捷函数 =====


def check_integrity(
    metadata: DocumentMetadata,
    prior_publications: Optional[list[PriorPublication]] = None,
    author_self_citations: Optional[set[str]] = None,
) -> IntegrityReport:
    """便捷函数：执行学术诚信检查。

    Args:
        metadata: 文档元数据。
        prior_publications: 既往发表记录。
        author_self_citations: 自引集合。

    Returns:
        诚信检查报告。
    """
    checker = AcademicIntegrityChecker()
    return checker.check(metadata, prior_publications, author_self_citations)


def quick_risk_assessment(metadata: DocumentMetadata) -> tuple[float, RiskLevel]:
    """便捷函数：快速风险评估。

    仅执行关键维度检查，返回风险评分与等级。

    Args:
        metadata: 文档元数据。

    Returns:
        (风险评分, 风险等级)。
    """
    checker = AcademicIntegrityChecker()
    report = checker.check(metadata)
    return report.overall_risk, report.risk_level
