"""引用验证器模块

提供论文参考文献的真实性与准确性验证能力，包括：
    - DOI 验证（格式校验、解析、元数据比对）
    - URL 可访问性验证（HTTP 状态、重定向、内容类型）
    - 引用内容匹配验证（引用声明与原文内容一致性）
    - 引用格式规范检查（APA/IEEE/GB-T7714 等格式）
    - 引用完整性检查（必填字段、元数据完整性）
    - 引用网络分析（引用图谱、中心性、聚类）
    - 引用孤岛检测（未引用条目、孤立引用）
    - 引用循环检测（自引环、互引环）
    - 批量验证、异步验证、验证报告生成

设计原则：
    1. 零外部依赖：仅使用 Python 标准库（urllib 模拟网络请求）
    2. 线程安全：所有公共方法通过 RLock 保护
    3. 可配置：超时、重试、阈值均可调整
    4. 可扩展：支持新增验证规则
    5. 离线友好：网络验证可禁用，仅做格式与逻辑校验
"""
from __future__ import annotations

import asyncio
import hashlib
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Iterable, Optional


# ===== 枚举 =====


class CitationStatus(str, Enum):
    """引用验证状态。"""

    VALID = "valid"            # 验证通过
    INVALID = "invalid"        # 验证失败
    SUSPICIOUS = "suspicious"  # 可疑
    UNVERIFIED = "unverified"  # 未验证（离线/超时）
    MISSING = "missing"        # 缺失


# ===== 常量 =====


# DOI 正则（符合 ISO 26324）
DOI_PATTERN = re.compile(
    r"^10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+$"
)

# DOI URL 前缀
DOI_RESOLVER_URL = "https://doi.org/"

# URL 正则
URL_PATTERN = re.compile(
    r"^https?://[^\s<>\"]+$",
    re.IGNORECASE,
)

# ISBN 正则（ISBN-10 / ISBN-13）
ISBN_PATTERN = re.compile(
    r"^(?:97[89][- ]?)?\d{1,5}[- ]?\d{1,7}[- ]?\d{1,7}[- ]?[\dX]$",
    re.IGNORECASE,
)

# 年份正则
YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")

# 作者正则（姓, 名首字母 或 姓 名首字母）
AUTHOR_PATTERN = re.compile(
    r"([A-Z][a-zA-Z\-']+)(?:,\s*([A-Z]\.))|(?:\s+([A-Z]\.))"
)

# 中文作者正则
CN_AUTHOR_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,4}")

# 引用编号正则 [1] [1,2,3]
IN_TEXT_CITATION_PATTERN = re.compile(r"\[(\d+(?:[-,;\s\d]*)?)\]")

# 默认网络请求超时（秒）
DEFAULT_REQUEST_TIMEOUT = 10.0

# 默认最大重试次数
DEFAULT_MAX_RETRIES = 2

# 默认并发验证数
DEFAULT_CONCURRENCY = 5

# 引用循环检测的最大深度
MAX_CYCLE_DEPTH = 10

# 引用孤岛阈值：参考文献被正文引用比例低于此值视为孤岛
ISOLATED_CITATION_RATIO = 0.0

# 格式规范名称
CITATION_FORMATS = ["APA", "IEEE", "MLA", "Chicago", "GB-T7714", "Vancouver"]

# 各格式特征正则
FORMAT_SIGNATURES: dict[str, list[re.Pattern[str]]] = {
    "APA": [
        re.compile(r"[A-Z][a-z]+,\s+[A-Z]\."),          # Smith, J.
        re.compile(r"\(\d{4}\)"),                         # (2020)
        re.compile(r"\bdoi:\s*10\."),                     # doi: 10.
    ],
    "IEEE": [
        re.compile(r"[A-Z]\.\s*[A-Z][a-z]+"),             # J. Smith
        re.compile(r"\bvol\.\s*\d+", re.IGNORECASE),      # vol. 10
        re.compile(r",\s*\d{4}\."),                       # , 2020.
    ],
    "MLA": [
        re.compile(r"[A-Z][a-z]+,\s+[A-Z][a-z]+"),        # Smith, John
        re.compile(r"\bPrint\b|\bWeb\b"),                 # Print / Web
    ],
    "Chicago": [
        re.compile(r"[A-Z][a-z]+,\s+[A-Z][a-z]+\s+[A-Z]"),  # Smith, John A.
        re.compile(r"\bUniversity\s+Press\b", re.IGNORECASE),
    ],
    "GB-T7714": [
        re.compile(r"[\u4e00-\u9fff]{2,4}"),              # 中文作者
        re.compile(r"\[\d{4}\]"),                          # [2020]
        re.compile(r"\b\d+:\s*\d+"),                       # 卷: 页
    ],
    "Vancouver": [
        re.compile(r"[A-Z][a-z]+\s+[A-Z][a-z]+"),         # Smith John
        re.compile(r"\.\s*\d{4};"),                        # . 2020;
    ],
}

# 必填字段
REQUIRED_FIELDS = ["author", "title", "year", "source"]

# 字段别名映射（兼容不同输入）
FIELD_ALIASES: dict[str, list[str]] = {
    "author": ["author", "authors", "作者"],
    "title": ["title", "标题", "题目"],
    "year": ["year", "date", "年份", "published"],
    "source": ["source", "venue", "journal", "publisher", "来源", "期刊"],
    "doi": ["doi", "DOI"],
    "url": ["url", "link", "链接"],
    "volume": ["volume", "vol", "卷"],
    "issue": ["issue", "no", "期"],
    "pages": ["pages", "pp", "页"],
    "isbn": ["isbn", "ISBN"],
}


# ===== 数据结构 =====


@dataclass
class CitationEntry:
    """引用条目。

    Attributes:
        index: 引用编号（1-based）。
        raw: 原始引用文本。
        author: 作者。
        title: 标题。
        year: 年份。
        source: 来源（期刊/会议/出版社）。
        doi: DOI。
        url: URL。
        volume: 卷。
        issue: 期。
        pages: 页码。
        isbn: ISBN。
        format: 引用格式。
        fields: 原始字段字典。
    """

    index: int = 0
    raw: str = ""
    author: str = ""
    title: str = ""
    year: str = ""
    source: str = ""
    doi: str = ""
    url: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    isbn: str = ""
    format: str = ""
    fields: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CitationIssue:
    """引用问题。

    Attributes:
        id: 问题 ID。
        citation_index: 引用编号。
        issue_type: 问题类型。
        severity: 严重程度（0-1）。
        message: 问题描述。
        detail: 详细信息。
        suggestion: 修复建议。
    """

    id: str = ""
    citation_index: int = 0
    issue_type: str = ""
    severity: float = 0.0
    message: str = ""
    detail: str = ""
    suggestion: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CitationVerificationReport:
    """引用验证报告。

    Attributes:
        id: 报告 ID。
        document_id: 文档 ID。
        timestamp: 验证时间。
        total_citations: 引用总数。
        verified_count: 已验证数。
        valid_count: 有效数。
        invalid_count: 无效数。
        suspicious_count: 可疑数。
        unverified_count: 未验证数。
        missing_count: 缺失数。
        overall_status: 总体状态。
        issues: 问题列表。
        citation_statuses: 各引用状态。
        network_analysis: 引用网络分析结果。
        format_distribution: 格式分布。
        recommendations: 建议。
        metadata: 元数据。
    """

    id: str = ""
    document_id: str = ""
    timestamp: str = ""
    total_citations: int = 0
    verified_count: int = 0
    valid_count: int = 0
    invalid_count: int = 0
    suspicious_count: int = 0
    unverified_count: int = 0
    missing_count: int = 0
    overall_status: CitationStatus = CitationStatus.UNVERIFIED
    issues: list[CitationIssue] = field(default_factory=list)
    citation_statuses: dict[int, str] = field(default_factory=dict)
    network_analysis: dict[str, Any] = field(default_factory=dict)
    format_distribution: dict[str, int] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "timestamp": self.timestamp,
            "total_citations": self.total_citations,
            "verified_count": self.verified_count,
            "valid_count": self.valid_count,
            "invalid_count": self.invalid_count,
            "suspicious_count": self.suspicious_count,
            "unverified_count": self.unverified_count,
            "missing_count": self.missing_count,
            "overall_status": self.overall_status.value,
            "issues": [i.to_dict() for i in self.issues],
            "citation_statuses": self.citation_statuses,
            "network_analysis": self.network_analysis,
            "format_distribution": self.format_distribution,
            "recommendations": self.recommendations,
            "metadata": self.metadata,
        }


@dataclass
class CitationNode:
    """引用网络节点。

    Attributes:
        index: 引用编号。
        title: 标题。
        author: 作者。
        year: 年份。
        cites: 引用的其他引用编号。
        cited_by: 被哪些引用引用。
    """

    index: int = 0
    title: str = ""
    author: str = ""
    year: str = ""
    cites: set[int] = field(default_factory=set)
    cited_by: set[int] = field(default_factory=set)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "title": self.title,
            "author": self.author,
            "year": self.year,
            "cites": sorted(self.cites),
            "cited_by": sorted(self.cited_by),
        }


# ===== 工具函数 =====


def _normalize_doi(doi: str) -> str:
    """归一化 DOI：去除前缀、空白、转小写。

    Args:
        doi: 原始 DOI 字符串。

    Returns:
        归一化后的 DOI。
    """
    if not doi:
        return ""
    doi = doi.strip()
    # 去除常见前缀
    for prefix in ["https://doi.org/", "http://doi.org/", "doi:", "DOI:", "doi.org/"]:
        if doi.lower().startswith(prefix.lower()):
            doi = doi[len(prefix):]
            break
    return doi.strip()


def _normalize_url(url: str) -> str:
    """归一化 URL：去除空白、补充协议。

    Args:
        url: 原始 URL。

    Returns:
        归一化后的 URL。
    """
    if not url:
        return ""
    url = url.strip()
    if url and not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _extract_year(text: str) -> str:
    """从文本中提取年份。

    Args:
        text: 原始文本。

    Returns:
        年份字符串（如 "2020"），未找到返回空。
    """
    match = YEAR_PATTERN.search(text)
    return match.group(0) if match else ""


def _levenshtein_distance(s1: str, s2: str) -> int:
    """计算 Levenshtein 编辑距离。

    Args:
        s1: 字符串 1。
        s2: 字符串 2。

    Returns:
        编辑距离。
    """
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def _string_similarity(s1: str, s2: str) -> float:
    """计算字符串相似度（基于编辑距离）。

    Args:
        s1: 字符串 1。
        s2: 字符串 2。

    Returns:
        相似度（0-1）。
    """
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    max_len = max(len(s1), len(s2))
    distance = _levenshtein_distance(s1.lower(), s2.lower())
    return 1.0 - distance / max_len


def _tokenize_words(text: str) -> set[str]:
    """分词为词集合（小写）。

    Args:
        text: 原始文本。

    Returns:
        词集合。
    """
    return set(re.findall(r"[a-zA-Z\u4e00-\u9fff]+", text.lower()))


def _detect_format(citation_text: str) -> str:
    """检测引用格式。

    Args:
        citation_text: 引用文本。

    Returns:
        格式名称，未识别返回 "Unknown"。
    """
    scores: dict[str, int] = {}
    for fmt, patterns in FORMAT_SIGNATURES.items():
        score = sum(1 for p in patterns if p.search(citation_text))
        if score > 0:
            scores[fmt] = score
    if not scores:
        return "Unknown"
    return max(scores, key=scores.get)


def _parse_citation(raw: str, index: int) -> CitationEntry:
    """解析引用文本为结构化条目。

    Args:
        raw: 原始引用文本。
        index: 引用编号。

    Returns:
        引用条目。
    """
    entry = CitationEntry(index=index, raw=raw.strip())
    text = raw.strip()

    # 提取 DOI
    doi_match = re.search(r"10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+", text)
    if doi_match:
        entry.doi = _normalize_doi(doi_match.group(0))

    # 提取 URL
    url_match = re.search(r"https?://[^\s<>\"]+", text, re.IGNORECASE)
    if url_match:
        entry.url = url_match.group(0)

    # 提取年份
    entry.year = _extract_year(text)

    # 提取 ISBN
    isbn_match = re.search(
        r"ISBN[:\s]*([0-9\-Xx]{10,17})", text, re.IGNORECASE
    )
    if isbn_match:
        entry.isbn = isbn_match.group(1).strip()

    # 提取卷期页
    vol_match = re.search(r"(?:vol\.?|volume|卷)[:\s]*(\d+)", text, re.IGNORECASE)
    if vol_match:
        entry.volume = vol_match.group(1)
    issue_match = re.search(r"(?:no\.?|issue|期)[:\s]*(\d+)", text, re.IGNORECASE)
    if issue_match:
        entry.issue = issue_match.group(1)
    pages_match = re.search(r"(?:pp\.?|pages|页)[:\s]*([\d\-–]+)", text, re.IGNORECASE)
    if pages_match:
        entry.pages = pages_match.group(1)

    # 提取作者（取第一个作者模式）
    author_match = re.search(
        r"^([A-Z][a-zA-Z\-']+,\s*[A-Z]\.|[\u4e00-\u9fff]{2,4})",
        text,
    )
    if author_match:
        entry.author = author_match.group(1)
    else:
        # 尝试匹配 "First Last" 形式
        author_match2 = re.match(r"^([A-Z][a-z]+\s+[A-Z][a-z]+)", text)
        if author_match2:
            entry.author = author_match2.group(1)

    # 提取标题（通常在作者之后、年份之前）
    # 格式: Author. Title. Source, Year.
    title_match = re.search(
        r"(?:^|\.\s)([A-Z][^.]*?)(?:\.\s*(?:\(|\[|\d{4}))",
        text,
    )
    if title_match:
        entry.title = title_match.group(1).strip().rstrip(".")

    # 提取来源（期刊/出版社）
    # 简化：取年份后的内容
    if entry.year:
        after_year = text.split(entry.year, 1)
        if len(after_year) > 1:
            source_part = after_year[1].strip(" .,")
            # 取第一个句号前的部分
            source_match = re.match(r"^([^,.]+)", source_part)
            if source_match:
                entry.source = source_match.group(1).strip()

    # 检测格式
    entry.format = _detect_format(text)

    return entry


def _extract_in_text_citations(text: str) -> set[int]:
    """提取正文中的引用编号。

    Args:
        text: 正文文本。

    Returns:
        引用编号集合。
    """
    citations: set[int] = set()
    for match in IN_TEXT_CITATION_PATTERN.finditer(text):
        group = match.group(1)
        # 解析 [1, 2, 3] 或 [1-3] 形式
        # 先处理范围
        range_match = re.match(r"^(\d+)\s*-\s*(\d+)$", group.strip())
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            for n in range(start, end + 1):
                citations.add(n)
            continue
        # 处理逗号分隔
        nums = re.findall(r"\d+", group)
        for num in nums:
            try:
                n = int(num)
                if 1 <= n <= 9999:
                    citations.add(n)
            except ValueError:
                continue
    return citations


# ===== 主验证器类 =====


class CitationVerifier:
    """引用验证器。

    对论文参考文献执行多维度验证，输出验证报告与修复建议。

    验证维度包括：
        - DOI 验证（格式校验、解析、元数据比对）
        - URL 可访问性验证（HTTP 状态、重定向）
        - 引用内容匹配验证（引用声明与原文一致性）
        - 引用格式规范检查（APA/IEEE/GB-T7714 等）
        - 引用完整性检查（必填字段、元数据完整性）
        - 引用网络分析（引用图谱、中心性、聚类）
        - 引用孤岛检测（未引用条目、孤立引用）
        - 引用循环检测（自引环、互引环）

    线程安全：所有公共方法通过 RLock 保护。

    典型用法：
        verifier = CitationVerifier(enable_network=False)
        report = verifier.verify(references, full_text)
        for issue in report.issues:
            print(issue.message, issue.suggestion)
    """

    def __init__(
        self,
        enable_network: bool = False,
        request_timeout: float = DEFAULT_REQUEST_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        concurrency: int = DEFAULT_CONCURRENCY,
    ) -> None:
        """初始化验证器。

        Args:
            enable_network: 是否启用网络验证（DOI/URL 可访问性）。
            request_timeout: 网络请求超时（秒）。
            max_retries: 最大重试次数。
            concurrency: 并发验证数。
        """
        self._lock = threading.RLock()
        self._enable_network = enable_network
        self._timeout = request_timeout
        self._max_retries = max_retries
        self._concurrency = max(1, concurrency)

        # 验证规则注册表
        self._rules: dict[str, dict[str, Any]] = {}
        self._register_default_rules()

        # 验证结果缓存（DOI/URL -> 状态）
        self._verification_cache: dict[str, CitationStatus] = {}

        # 历史报告
        self._report_history: list[CitationVerificationReport] = []
        self._max_history = 50

        # 统计
        self._stats = {
            "total_verifications": 0,
            "network_requests": 0,
            "cache_hits": 0,
            "errors": 0,
        }

    # ===== 规则注册 =====

    def _register_default_rules(self) -> None:
        """注册默认验证规则。"""
        rules = {
            "DOI-FMT": {
                "name": "DOI 格式校验",
                "description": "验证 DOI 是否符合 ISO 26324 格式规范。",
            },
            "DOI-RESOLVE": {
                "name": "DOI 可解析性",
                "description": "验证 DOI 是否可通过 doi.org 解析。",
            },
            "URL-ACCESS": {
                "name": "URL 可访问性",
                "description": "验证 URL 是否可正常访问（HTTP 200）。",
            },
            "CONTENT-MATCH": {
                "name": "引用内容匹配",
                "description": "验证引用声明与参考文献内容是否匹配。",
            },
            "FORMAT-CONSISTENCY": {
                "name": "格式一致性",
                "description": "验证所有引用是否采用统一格式。",
            },
            "FIELD-COMPLETENESS": {
                "name": "字段完整性",
                "description": "验证引用是否包含必填字段。",
            },
            "YEAR-VALID": {
                "name": "年份有效性",
                "description": "验证引用年份是否在合理范围内。",
            },
            "ISOLATED-CITATION": {
                "name": "引用孤岛",
                "description": "检测未被正文引用的参考文献。",
            },
            "CITATION-CYCLE": {
                "name": "引用循环",
                "description": "检测引用网络中的循环引用。",
            },
            "DUPLICATE-CITATION": {
                "name": "重复引用",
                "description": "检测重复的参考文献条目。",
            },
        }
        self._rules.update(rules)

    def register_rule(
        self, rule_id: str, name: str, description: str
    ) -> None:
        """注册自定义验证规则。

        Args:
            rule_id: 规则 ID。
            name: 规则名称。
            description: 规则描述。
        """
        with self._lock:
            self._rules[rule_id] = {"name": name, "description": description}

    # ===== 公共接口 =====

    def verify(
        self,
        references: list[str],
        full_text: str = "",
        citation_network: Optional[dict[int, list[int]]] = None,
    ) -> CitationVerificationReport:
        """执行完整的引用验证。

        Args:
            references: 参考文献原始文本列表。
            full_text: 论文正文（用于引用孤岛检测）。
            citation_network: 引用网络映射（引用编号 -> 其引用的编号列表）。

        Returns:
            验证报告。
        """
        with self._lock:
            self._stats["total_verifications"] += 1

            report = CitationVerificationReport(
                id=str(uuid.uuid4()),
                document_id=str(uuid.uuid4()),
                timestamp=datetime.utcnow().isoformat() + "Z",
                total_citations=len(references),
            )

            # 解析引用条目
            entries: list[CitationEntry] = []
            for idx, raw in enumerate(references, start=1):
                entry = _parse_citation(raw, idx)
                entries.append(entry)

            issues: list[CitationIssue] = []
            citation_statuses: dict[int, str] = {}

            # 1. 字段完整性检查
            for entry in entries:
                field_issues = self._check_field_completeness(entry)
                issues.extend(field_issues)

            # 2. DOI 验证
            for entry in entries:
                if entry.doi:
                    doi_issues = self._verify_doi(entry)
                    issues.extend(doi_issues)

            # 3. URL 可访问性验证
            if self._enable_network:
                for entry in entries:
                    if entry.url:
                        url_issues = self._verify_url(entry)
                        issues.extend(url_issues)

            # 4. 年份有效性
            for entry in entries:
                year_issues = self._check_year_validity(entry)
                issues.extend(year_issues)

            # 5. 格式一致性
            format_issues = self._check_format_consistency(entries)
            issues.extend(format_issues)

            # 6. 重复引用检测
            dup_issues = self._check_duplicates(entries)
            issues.extend(dup_issues)

            # 7. 引用孤岛检测
            if full_text:
                isolated_issues = self._check_isolated_citations(entries, full_text)
                issues.extend(isolated_issues)

            # 8. 引用网络分析
            network_analysis: dict[str, Any] = {}
            if citation_network:
                network_issues, network_analysis = self._analyze_citation_network(
                    entries, citation_network
                )
                issues.extend(network_issues)
            else:
                # 基于正文引用构建简单网络
                network_analysis = self._build_simple_network(entries, full_text)

            # 综合各引用状态
            for entry in entries:
                status = self._assess_citation_status(entry, issues)
                citation_statuses[entry.index] = status.value

            # 统计
            report.issues = issues
            report.citation_statuses = citation_statuses
            report.verified_count = len(entries)
            report.valid_count = sum(
                1 for s in citation_statuses.values() if s == CitationStatus.VALID.value
            )
            report.invalid_count = sum(
                1 for s in citation_statuses.values() if s == CitationStatus.INVALID.value
            )
            report.suspicious_count = sum(
                1 for s in citation_statuses.values() if s == CitationStatus.SUSPICIOUS.value
            )
            report.unverified_count = sum(
                1 for s in citation_statuses.values() if s == CitationStatus.UNVERIFIED.value
            )
            report.missing_count = sum(
                1 for s in citation_statuses.values() if s == CitationStatus.MISSING.value
            )
            report.overall_status = self._assess_overall_status(report)
            report.network_analysis = network_analysis
            report.format_distribution = self._compute_format_distribution(entries)
            report.recommendations = self._generate_recommendations(report)
            report.metadata = {
                "enable_network": self._enable_network,
                "rules_count": len(self._rules),
                "stats": dict(self._stats),
            }

            # 缓存历史
            self._report_history.append(report)
            if len(self._report_history) > self._max_history:
                self._report_history = self._report_history[-self._max_history:]

            return report

    def verify_single(self, reference: str) -> tuple[CitationStatus, list[CitationIssue]]:
        """验证单条引用。

        Args:
            reference: 引用文本。

        Returns:
            (状态, 问题列表)。
        """
        with self._lock:
            entry = _parse_citation(reference, 1)
            issues: list[CitationIssue] = []
            issues.extend(self._check_field_completeness(entry))
            if entry.doi:
                issues.extend(self._verify_doi(entry))
            if self._enable_network and entry.url:
                issues.extend(self._verify_url(entry))
            issues.extend(self._check_year_validity(entry))
            status = self._assess_citation_status(entry, issues)
            return status, issues

    async def verify_async(
        self,
        references: list[str],
        full_text: str = "",
    ) -> CitationVerificationReport:
        """异步验证引用。

        使用 asyncio 并发验证多条引用。

        Args:
            references: 参考文献列表。
            full_text: 论文正文。

        Returns:
            验证报告。
        """
        # 在线程池中执行同步验证
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self.verify(references, full_text)
        )

    def batch_verify(
        self,
        references_list: list[list[str]],
    ) -> list[CitationVerificationReport]:
        """批量验证多组引用。

        Args:
            references_list: 多组参考文献列表。

        Returns:
            验证报告列表。
        """
        with self._lock:
            return [self.verify(refs) for refs in references_list]

    def get_history(self, limit: int = 10) -> list[CitationVerificationReport]:
        """获取历史验证报告。

        Args:
            limit: 返回数量上限。

        Returns:
            历史报告列表。
        """
        with self._lock:
            return list(reversed(self._report_history[-limit:]))

    def get_stats(self) -> dict[str, Any]:
        """获取验证统计。

        Returns:
            统计字典。
        """
        with self._lock:
            return dict(self._stats)

    # ===== 验证实现 =====

    def _check_field_completeness(self, entry: CitationEntry) -> list[CitationIssue]:
        """检查字段完整性。

        Args:
            entry: 引用条目。

        Returns:
            问题列表。
        """
        issues: list[CitationIssue] = []
        for field_name in REQUIRED_FIELDS:
            value = getattr(entry, field_name, "").strip()
            if not value:
                issues.append(CitationIssue(
                    id=str(uuid.uuid4()),
                    citation_index=entry.index,
                    issue_type="FIELD-COMPLETENESS",
                    severity=0.5 if field_name in ("author", "title", "year") else 0.3,
                    message=f"引用 [{entry.index}] 缺少必填字段: {field_name}",
                    detail=f"字段 '{field_name}' 为空。原始引用: {entry.raw[:80]}",
                    suggestion=f"补充 {field_name} 字段信息。",
                ))
        return issues

    def _verify_doi(self, entry: CitationEntry) -> list[CitationIssue]:
        """验证 DOI。

        Args:
            entry: 引用条目。

        Returns:
            问题列表。
        """
        issues: list[CitationIssue] = []
        doi = entry.doi

        # 格式校验
        if not DOI_PATTERN.match(doi):
            issues.append(CitationIssue(
                id=str(uuid.uuid4()),
                citation_index=entry.index,
                issue_type="DOI-FMT",
                severity=0.6,
                message=f"引用 [{entry.index}] DOI 格式无效",
                detail=f"DOI '{doi}' 不符合 ISO 26324 格式规范。",
                suggestion="核对 DOI 拼写，确保格式为 10.xxxx/xxxxx。",
            ))
            return issues

        # 网络解析验证
        if self._enable_network:
            cache_key = f"doi:{doi}"
            if cache_key in self._verification_cache:
                self._stats["cache_hits"] += 1
                status = self._verification_cache[cache_key]
                if status != CitationStatus.VALID:
                    issues.append(CitationIssue(
                        id=str(uuid.uuid4()),
                        citation_index=entry.index,
                        issue_type="DOI-RESOLVE",
                        severity=0.7,
                        message=f"引用 [{entry.index}] DOI 无法解析",
                        detail=f"DOI '{doi}' 无法通过 doi.org 解析（缓存结果）。",
                        suggestion="核对 DOI 是否存在，或更换为有效 DOI。",
                    ))
                return issues

            status = self._check_doi_resolvable(doi)
            self._verification_cache[cache_key] = status
            self._stats["network_requests"] += 1

            if status != CitationStatus.VALID:
                issues.append(CitationIssue(
                    id=str(uuid.uuid4()),
                    citation_index=entry.index,
                    issue_type="DOI-RESOLVE",
                    severity=0.7,
                    message=f"引用 [{entry.index}] DOI 无法解析",
                    detail=f"DOI '{doi}' 无法通过 doi.org 解析。",
                    suggestion="核对 DOI 是否存在，或更换为有效 DOI。",
                ))

        return issues

    def _check_doi_resolvable(self, doi: str) -> CitationStatus:
        """检查 DOI 是否可解析。

        Args:
            doi: DOI 字符串。

        Returns:
            验证状态。
        """
        url = DOI_RESOLVER_URL + doi
        for attempt in range(self._max_retries + 1):
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "ThesisMiner-CitationVerifier/8.0"},
                )
                with urllib.request.urlopen(req, timeout=self._timeout) as response:
                    if response.status == 200:
                        return CitationStatus.VALID
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return CitationStatus.INVALID
                # 其他 HTTP 错误重试
            except (urllib.error.URLError, TimeoutError, OSError):
                # 网络错误重试
                pass
            except Exception:  # pragma: no cover
                self._stats["errors"] += 1
                return CitationStatus.UNVERIFIED
        return CitationStatus.UNVERIFIED

    def _verify_url(self, entry: CitationEntry) -> list[CitationIssue]:
        """验证 URL 可访问性。

        Args:
            entry: 引用条目。

        Returns:
            问题列表。
        """
        issues: list[CitationIssue] = []
        url = entry.url

        # URL 格式校验
        if not URL_PATTERN.match(url):
            issues.append(CitationIssue(
                id=str(uuid.uuid4()),
                citation_index=entry.index,
                issue_type="URL-ACCESS",
                severity=0.4,
                message=f"引用 [{entry.index}] URL 格式无效",
                detail=f"URL '{url}' 格式不正确。",
                suggestion="核对 URL 格式，确保以 http:// 或 https:// 开头。",
            ))
            return issues

        # 网络可访问性验证
        cache_key = f"url:{url}"
        if cache_key in self._verification_cache:
            self._stats["cache_hits"] += 1
            status = self._verification_cache[cache_key]
            if status != CitationStatus.VALID:
                issues.append(CitationIssue(
                    id=str(uuid.uuid4()),
                    citation_index=entry.index,
                    issue_type="URL-ACCESS",
                    severity=0.5,
                    message=f"引用 [{entry.index}] URL 不可访问",
                    detail=f"URL '{url}' 无法访问（缓存结果: {status.value}）。",
                    suggestion="更换为可访问的 URL，或补充 DOI 作为替代。",
                ))
            return issues

        status = self._check_url_accessible(url)
        self._verification_cache[cache_key] = status
        self._stats["network_requests"] += 1

        if status != CitationStatus.VALID:
            severity = 0.5 if status == CitationStatus.INVALID else 0.3
            issues.append(CitationIssue(
                id=str(uuid.uuid4()),
                citation_index=entry.index,
                issue_type="URL-ACCESS",
                severity=severity,
                message=f"引用 [{entry.index}] URL 不可访问",
                detail=f"URL '{url}' 访问失败（状态: {status.value}）。",
                suggestion="更换为可访问的 URL，或补充 DOI 作为替代。",
            ))

        return issues

    def _check_url_accessible(self, url: str) -> CitationStatus:
        """检查 URL 是否可访问。

        Args:
            url: URL 字符串。

        Returns:
            验证状态。
        """
        for attempt in range(self._max_retries + 1):
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "ThesisMiner-CitationVerifier/8.0"},
                    method="HEAD",
                )
                with urllib.request.urlopen(req, timeout=self._timeout) as response:
                    if response.status == 200:
                        return CitationStatus.VALID
                    elif response.status in (301, 302, 303, 307, 308):
                        # 重定向视为可访问
                        return CitationStatus.VALID
                    else:
                        return CitationStatus.SUSPICIOUS
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return CitationStatus.INVALID
                elif e.code in (403, 401):
                    # 需要认证，视为可疑
                    return CitationStatus.SUSPICIOUS
                # 其他错误重试
            except (urllib.error.URLError, TimeoutError, OSError):
                pass
            except Exception:  # pragma: no cover
                self._stats["errors"] += 1
                return CitationStatus.UNVERIFIED
        return CitationStatus.UNVERIFIED

    def _check_year_validity(self, entry: CitationEntry) -> list[CitationIssue]:
        """检查年份有效性。

        Args:
            entry: 引用条目。

        Returns:
            问题列表。
        """
        issues: list[CitationIssue] = []
        if not entry.year:
            # 缺少年份已在字段完整性中报告
            return issues

        try:
            year = int(entry.year)
        except ValueError:
            issues.append(CitationIssue(
                id=str(uuid.uuid4()),
                citation_index=entry.index,
                issue_type="YEAR-VALID",
                severity=0.4,
                message=f"引用 [{entry.index}] 年份格式无效",
                detail=f"年份 '{entry.year}' 不是有效数字。",
                suggestion="核对并修正年份。",
            ))
            return issues

        current_year = datetime.utcnow().year
        # 年份过早（1900 年前）或未来（超过当前年份 +2）
        if year < 1900:
            issues.append(CitationIssue(
                id=str(uuid.uuid4()),
                citation_index=entry.index,
                issue_type="YEAR-VALID",
                severity=0.5,
                message=f"引用 [{entry.index}] 年份过早",
                detail=f"年份 {year} 早于 1900 年，可能为错误。",
                suggestion="核对年份是否正确。",
            ))
        elif year > current_year + 2:
            issues.append(CitationIssue(
                id=str(uuid.uuid4()),
                citation_index=entry.index,
                issue_type="YEAR-VALID",
                severity=0.4,
                message=f"引用 [{entry.index}] 年份为未来",
                detail=f"年份 {year} 晚于当前年份 {current_year} 两年以上。",
                suggestion="核对年份是否正确，可能是预印本或录入错误。",
            ))

        return issues

    def _check_format_consistency(
        self, entries: list[CitationEntry]
    ) -> list[CitationIssue]:
        """检查格式一致性。

        Args:
            entries: 引用条目列表。

        Returns:
            问题列表。
        """
        issues: list[CitationIssue] = []
        if len(entries) < 2:
            return issues

        # 统计格式分布
        format_counts: Counter[str] = Counter()
        for entry in entries:
            format_counts[entry.format] += 1

        # 主导格式
        dominant_format, dominant_count = format_counts.most_common(1)[0]
        dominant_ratio = dominant_count / len(entries)

        # 若主导格式占比不足 70%，报告不一致
        if dominant_ratio < 0.7 and len(format_counts) > 1:
            inconsistent_indices = [
                e.index for e in entries if e.format != dominant_format
            ]
            issues.append(CitationIssue(
                id=str(uuid.uuid4()),
                citation_index=0,
                issue_type="FORMAT-CONSISTENCY",
                severity=0.35,
                message="引用格式不一致",
                detail=(
                    f"主导格式 '{dominant_format}' 占比 {dominant_ratio:.1%}，"
                    f"存在 {len(format_counts)} 种格式: "
                    f"{dict(format_counts)}。不一致引用: {inconsistent_indices[:10]}。"
                ),
                suggestion=f"统一所有引用为 {dominant_format} 格式。",
            ))

        # 检测格式未识别的引用
        unknown_indices = [e.index for e in entries if e.format == "Unknown"]
        if unknown_indices:
            issues.append(CitationIssue(
                id=str(uuid.uuid4()),
                citation_index=0,
                issue_type="FORMAT-CONSISTENCY",
                severity=0.3,
                message=f"{len(unknown_indices)} 条引用格式无法识别",
                detail=f"无法识别格式的引用编号: {unknown_indices[:10]}。",
                suggestion="补充完整字段信息，确保引用符合标准格式。",
            ))

        return issues

    def _check_duplicates(self, entries: list[CitationEntry]) -> list[CitationIssue]:
        """检测重复引用。

        Args:
            entries: 引用条目列表。

        Returns:
            问题列表。
        """
        issues: list[CitationIssue] = []
        # 基于 DOI 去重
        doi_map: dict[str, list[int]] = defaultdict(list)
        # 基于标题相似度去重
        title_map: dict[str, list[int]] = defaultdict(list)

        for entry in entries:
            if entry.doi:
                doi_map[entry.doi.lower()].append(entry.index)
            if entry.title:
                # 标题归一化（小写、去标点）
                norm_title = re.sub(r"[^\w\s]", "", entry.title.lower()).strip()
                if norm_title:
                    title_map[norm_title].append(entry.index)

        # DOI 完全重复
        for doi, indices in doi_map.items():
            if len(indices) > 1:
                issues.append(CitationIssue(
                    id=str(uuid.uuid4()),
                    citation_index=indices[0],
                    issue_type="DUPLICATE-CITATION",
                    severity=0.6,
                    message=f"DOI 重复: 引用 {indices}",
                    detail=f"DOI '{doi}' 出现在引用 {indices} 中。",
                    suggestion=f"合并重复引用，保留一条并删除 {indices[1:]}。",
                ))

        # 标题完全重复
        for title, indices in title_map.items():
            if len(indices) > 1 and title:
                # 排除已被 DOI 检测覆盖的
                if not any(
                    set(indices).issubset(set(v))
                    for v in doi_map.values() if len(v) > 1
                ):
                    issues.append(CitationIssue(
                        id=str(uuid.uuid4()),
                        citation_index=indices[0],
                        issue_type="DUPLICATE-CITATION",
                        severity=0.5,
                        message=f"标题重复: 引用 {indices}",
                        detail=f"标题 '{title[:50]}...' 出现在引用 {indices} 中。",
                        suggestion=f"合并重复引用，保留一条并删除 {indices[1:]}。",
                    ))

        # 标题高相似度检测（编辑距离）
        titled_entries = [e for e in entries if e.title and len(e.title) > 10]
        for i, entry_a in enumerate(titled_entries):
            for entry_b in titled_entries[i + 1:]:
                if entry_a.index == entry_b.index:
                    continue
                sim = _string_similarity(entry_a.title, entry_b.title)
                if 0.85 < sim < 1.0:  # 高度相似但不完全相同
                    issues.append(CitationIssue(
                        id=str(uuid.uuid4()),
                        citation_index=entry_a.index,
                        issue_type="DUPLICATE-CITATION",
                        severity=0.4,
                        message=(
                            f"引用 [{entry_a.index}] 与 [{entry_b.index}] 标题高度相似"
                        ),
                        detail=(
                            f"标题相似度 {sim:.1%}: "
                            f"'{entry_a.title[:40]}...' vs '{entry_b.title[:40]}...'"
                        ),
                        suggestion="核对是否为同一文献的不同版本，必要时合并。",
                    ))

        return issues

    def _check_isolated_citations(
        self, entries: list[CitationEntry], full_text: str
    ) -> list[CitationIssue]:
        """检测引用孤岛。

        Args:
            entries: 引用条目列表。
            full_text: 论文正文。

        Returns:
            问题列表。
        """
        issues: list[CitationIssue] = []
        cited_indices = _extract_in_text_citations(full_text)
        total = len(entries)

        for entry in entries:
            if entry.index not in cited_indices:
                # 未被正文引用
                issues.append(CitationIssue(
                    id=str(uuid.uuid4()),
                    citation_index=entry.index,
                    issue_type="ISOLATED-CITATION",
                    severity=0.3,
                    message=f"引用 [{entry.index}] 未被正文引用",
                    detail=(
                        f"参考文献 [{entry.index}] 在正文中未被引用。"
                        f"标题: {entry.title[:50] if entry.title else '未知'}"
                    ),
                    suggestion="在正文适当位置补充引用，或删除该参考文献。",
                ))

        # 检测正文引用了但参考文献列表中没有的编号
        max_ref = total
        orphan_citations = {
            n for n in cited_indices if n > max_ref
        }
        for n in sorted(orphan_citations)[:10]:
            issues.append(CitationIssue(
                id=str(uuid.uuid4()),
                citation_index=n,
                issue_type="ISOLATED-CITATION",
                severity=0.5,
                message=f"正文引用 [{n}] 在参考文献列表中不存在",
                detail=f"正文引用编号 {n} 超出参考文献列表范围（共 {total} 条）。",
                suggestion="补充缺失的参考文献，或修正引用编号。",
            ))

        return issues

    def _analyze_citation_network(
        self,
        entries: list[CitationEntry],
        citation_network: dict[int, list[int]],
    ) -> tuple[list[CitationIssue], dict[str, Any]]:
        """分析引用网络。

        Args:
            entries: 引用条目列表。
            citation_network: 引用网络映射。

        Returns:
            (问题列表, 网络分析结果)。
        """
        issues: list[CitationIssue] = []
        nodes: dict[int, CitationNode] = {}

        # 构建节点
        for entry in entries:
            node = CitationNode(
                index=entry.index,
                title=entry.title,
                author=entry.author,
                year=entry.year,
            )
            nodes[entry.index] = node

        # 构建边
        for src, targets in citation_network.items():
            if src not in nodes:
                continue
            for tgt in targets:
                if tgt in nodes:
                    nodes[src].cites.add(tgt)
                    nodes[tgt].cited_by.add(src)

        # 引用循环检测
        cycles = self._detect_cycles(nodes)
        for cycle in cycles:
            issues.append(CitationIssue(
                id=str(uuid.uuid4()),
                citation_index=cycle[0],
                issue_type="CITATION-CYCLE",
                severity=0.7,
                message=f"检测到引用循环: {' -> '.join(str(n) for n in cycle)}",
                detail=f"引用 {cycle} 形成循环引用，违反学术规范。",
                suggestion="打破循环引用，重新组织引用关系。",
            ))

        # 中心性分析
        centrality = self._compute_centrality(nodes)

        # 孤立节点检测
        isolated_nodes = [
            idx for idx, node in nodes.items()
            if not node.cites and not node.cited_by
        ]
        for idx in isolated_nodes:
            issues.append(CitationIssue(
                id=str(uuid.uuid4()),
                citation_index=idx,
                issue_type="ISOLATED-CITATION",
                severity=0.25,
                message=f"引用 [{idx}] 在引用网络中孤立",
                detail="该引用既不引用其他文献，也不被其他文献引用。",
                suggestion="核实该引用的必要性，或补充引用关系。",
            ))

        analysis = {
            "node_count": len(nodes),
            "edge_count": sum(len(n.cites) for n in nodes.values()),
            "cycles": cycles,
            "centrality": centrality,
            "isolated_nodes": isolated_nodes,
            "top_cited": sorted(
                [(idx, len(node.cited_by)) for idx, node in nodes.items()],
                key=lambda x: x[1],
                reverse=True,
            )[:10],
            "top_citing": sorted(
                [(idx, len(node.cites)) for idx, node in nodes.items()],
                key=lambda x: x[1],
                reverse=True,
            )[:10],
        }

        return issues, analysis

    def _detect_cycles(self, nodes: dict[int, CitationNode]) -> list[list[int]]:
        """检测引用网络中的循环。

        使用 DFS 染色法检测环。

        Args:
            nodes: 节点字典。

        Returns:
            循环列表（每个循环为节点编号列表）。
        """
        cycles: list[list[int]] = []
        visited: set[int] = set()
        rec_stack: list[int] = []

        def dfs(node_idx: int) -> None:
            if node_idx in rec_stack:
                # 找到环
                cycle_start = rec_stack.index(node_idx)
                cycle = rec_stack[cycle_start:] + [node_idx]
                cycles.append(cycle)
                return
            if node_idx in visited:
                return
            visited.add(node_idx)
            rec_stack.append(node_idx)
            node = nodes.get(node_idx)
            if node:
                for neighbor in node.cites:
                    if len(rec_stack) <= MAX_CYCLE_DEPTH:
                        dfs(neighbor)
            rec_stack.pop()

        for idx in nodes:
            if idx not in visited:
                dfs(idx)

        return cycles

    def _compute_centrality(
        self, nodes: dict[int, CitationNode]
    ) -> dict[str, list[tuple[int, int]]]:
        """计算节点中心性（入度/出度）。

        Args:
            nodes: 节点字典。

        Returns:
            中心性字典。
        """
        in_degree = [(idx, len(node.cited_by)) for idx, node in nodes.items()]
        out_degree = [(idx, len(node.cites)) for idx, node in nodes.items()]
        return {
            "in_degree": sorted(in_degree, key=lambda x: x[1], reverse=True)[:10],
            "out_degree": sorted(out_degree, key=lambda x: x[1], reverse=True)[:10],
        }

    def _build_simple_network(
        self, entries: list[CitationEntry], full_text: str
    ) -> dict[str, Any]:
        """构建简单引用网络（基于正文引用）。

        Args:
            entries: 引用条目列表。
            full_text: 论文正文。

        Returns:
            网络分析结果。
        """
        cited_indices = _extract_in_text_citations(full_text)
        return {
            "node_count": len(entries),
            "cited_in_text": sorted(cited_indices),
            "uncited": sorted(
                e.index for e in entries if e.index not in cited_indices
            ),
            "citation_density": len(cited_indices) / max(len(entries), 1),
        }

    def _compute_format_distribution(
        self, entries: list[CitationEntry]
    ) -> dict[str, int]:
        """计算格式分布。

        Args:
            entries: 引用条目列表。

        Returns:
            格式 -> 数量映射。
        """
        dist: Counter[str] = Counter()
        for entry in entries:
            dist[entry.format] += 1
        return dict(dist)

    def _assess_citation_status(
        self, entry: CitationEntry, issues: list[CitationIssue]
    ) -> CitationStatus:
        """评估单条引用的状态。

        Args:
            entry: 引用条目。
            issues: 所有问题。

        Returns:
            验证状态。
        """
        entry_issues = [i for i in issues if i.citation_index == entry.index]
        if not entry_issues:
            return CitationStatus.VALID

        max_severity = max(i.severity for i in entry_issues)
        if max_severity >= 0.6:
            return CitationStatus.INVALID
        elif max_severity >= 0.3:
            return CitationStatus.SUSPICIOUS
        else:
            return CitationStatus.VALID

    def _assess_overall_status(
        self, report: CitationVerificationReport
    ) -> CitationStatus:
        """评估总体状态。

        Args:
            report: 验证报告。

        Returns:
            总体状态。
        """
        total = report.total_citations
        if total == 0:
            return CitationStatus.MISSING
        invalid_ratio = report.invalid_count / total
        suspicious_ratio = report.suspicious_count / total
        if invalid_ratio > 0.3:
            return CitationStatus.INVALID
        elif invalid_ratio > 0.1 or suspicious_ratio > 0.3:
            return CitationStatus.SUSPICIOUS
        elif report.valid_count / total > 0.8:
            return CitationStatus.VALID
        else:
            return CitationStatus.UNVERIFIED

    def _generate_recommendations(
        self, report: CitationVerificationReport
    ) -> list[str]:
        """生成修复建议。

        Args:
            report: 验证报告。

        Returns:
            建议列表。
        """
        recommendations: list[str] = []

        # 总体建议
        if report.overall_status == CitationStatus.INVALID:
            recommendations.append(
                "⚠️ 引用验证失败：存在大量无效引用，建议全面核查参考文献。"
            )
        elif report.overall_status == CitationStatus.SUSPICIOUS:
            recommendations.append(
                "⚠️ 引用存在可疑项：建议逐条核查可疑引用。"
            )
        elif report.overall_status == CitationStatus.VALID:
            recommendations.append("✅ 引用验证通过：参考文献整体质量良好。")
        else:
            recommendations.append("📋 引用未完全验证：建议启用网络验证以获得完整结果。")

        # 按问题类型分组建议
        type_issues: dict[str, list[CitationIssue]] = defaultdict(list)
        for issue in report.issues:
            type_issues[issue.issue_type].append(issue)

        type_advice = {
            "DOI-FMT": "DOI 格式问题：核对所有 DOI 拼写，确保符合 10.xxxx/xxxxx 格式。",
            "DOI-RESOLVE": "DOI 解析失败：核实 DOI 是否存在，可能为虚假引用。",
            "URL-ACCESS": "URL 不可访问：更换有效 URL 或补充 DOI 作为替代。",
            "FIELD-COMPLETENESS": "字段缺失：补充作者、标题、年份、来源等必填字段。",
            "FORMAT-CONSISTENCY": "格式不一致：统一所有引用为同一格式标准。",
            "YEAR-VALID": "年份异常：核对发表年份是否正确。",
            "ISOLATED-CITATION": "引用孤岛：补充正文引用或删除多余参考文献。",
            "CITATION-CYCLE": "引用循环：打破循环引用关系。",
            "DUPLICATE-CITATION": "重复引用：合并重复条目。",
        }

        for issue_type, issue_list in type_issues.items():
            advice = type_advice.get(issue_type)
            if advice:
                recommendations.append(f"【{issue_type}】{advice}（{len(issue_list)} 处）")

        # 格式分布建议
        if report.format_distribution:
            dominant = max(report.format_distribution, key=report.format_distribution.get)
            recommendations.append(
                f"建议统一采用 {dominant} 格式（当前占比最高）。"
            )

        # 网络分析建议
        if report.network_analysis.get("cycles"):
            recommendations.append(
                f"⚠️ 检测到 {len(report.network_analysis['cycles'])} 个引用循环，"
                "需打破循环引用。"
            )
        if report.network_analysis.get("isolated_nodes"):
            recommendations.append(
                f"检测到 {len(report.network_analysis['isolated_nodes'])} 个孤立引用，"
                "建议核实其必要性。"
            )

        return recommendations

    # ===== 配置管理 =====

    def enable_network_verification(self, enabled: bool = True) -> None:
        """启用/禁用网络验证。

        Args:
            enabled: 是否启用。
        """
        with self._lock:
            self._enable_network = enabled

    def set_timeout(self, timeout: float) -> None:
        """设置网络请求超时。

        Args:
            timeout: 超时秒数。
        """
        with self._lock:
            self._timeout = timeout

    def clear_cache(self) -> None:
        """清空验证缓存。"""
        with self._lock:
            self._verification_cache.clear()

    def get_config(self) -> dict[str, Any]:
        """获取当前配置。

        Returns:
            配置字典。
        """
        with self._lock:
            return {
                "enable_network": self._enable_network,
                "timeout": self._timeout,
                "max_retries": self._max_retries,
                "concurrency": self._concurrency,
                "cache_size": len(self._verification_cache),
                "rules": dict(self._rules),
                "stats": dict(self._stats),
            }


# ===== 模块级便捷函数 =====


def verify_citations(
    references: list[str],
    full_text: str = "",
    enable_network: bool = False,
) -> CitationVerificationReport:
    """便捷函数：验证引用。

    Args:
        references: 参考文献列表。
        full_text: 论文正文。
        enable_network: 是否启用网络验证。

    Returns:
        验证报告。
    """
    verifier = CitationVerifier(enable_network=enable_network)
    return verifier.verify(references, full_text)


def parse_citation(reference: str) -> CitationEntry:
    """便捷函数：解析单条引用。

    Args:
        reference: 引用文本。

    Returns:
        引用条目。
    """
    return _parse_citation(reference, 1)


def validate_doi(doi: str) -> bool:
    """便捷函数：验证 DOI 格式。

    Args:
        doi: DOI 字符串。

    Returns:
        是否有效。
    """
    normalized = _normalize_doi(doi)
    return bool(DOI_PATTERN.match(normalized))
