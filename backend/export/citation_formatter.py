"""引用格式化器模块

提供学术参考文献的多种引用格式化能力，包括：
    - GB/T 7714-2015（中国国家标准）
    - APA（美国心理学会第 7 版）
    - MLA（现代语言协会第 9 版）
    - Chicago（芝加哥格式第 17 版）
    - IEEE（电气电子工程师学会）

支持的文献类型：
    - 期刊论文（Journal Article）
    - 会议论文（Conference Paper）
    - 图书专著（Book）
    - 图书章节（Book Chapter）
    - 学位论文（Thesis / Dissertation）
    - 网页资源（Web Page）
    - 技术报告（Technical Report）
    - 专利（Patent）
    - 标准（Standard）
    - 报纸文章（Newspaper Article）

核心功能：
    - 单条参考文献格式化（正文引用 + 参考文献列表）
    - 批量格式化与统一风格
    - 参考文献排序（按作者/年份/标题）
    - 参考文献去重（基于 DOI/标题哈希）
    - 引用解析（从字符串解析为结构化数据）
    - 引用校验（必填字段、格式规范）
    - 统计报告（文献类型分布、格式一致性）

仅使用 Python 标准库实现，无外部依赖。

典型用法：
    formatter = CitationFormatter()
    ref = Reference(
        type=ReferenceType.JOURNAL,
        authors=[Author("张", "三"), Author("李", "四")],
        title="深度学习在自然语言处理中的应用",
        year="2024",
        journal="计算机学报",
        volume="47",
        issue="3",
        pages="512-528",
        doi="10.3724/SP.J.1016.2024.00512",
    )
    # 格式化为 GB/T 7714
    bib = formatter.format_bibliography(ref, CitationStyle.GB_T_7714)
    in_text = formatter.format_in_text(ref, CitationStyle.GB_T_7714)
    # 批量格式化
    refs = [ref1, ref2, ref3]
    bibliography = formatter.format_bibliography_batch(refs, CitationStyle.APA, sort=True)
"""
from __future__ import annotations

import hashlib
import re
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

# 尝试导入日志
try:
    from backend.utils.logger import get_logger

    _logger = get_logger(__name__)
except Exception:  # pragma: no cover
    import logging

    _logger = logging.getLogger(__name__)


# ===== 枚举定义 =====


class CitationStyle(str, Enum):
    """引用格式风格枚举。

    每种风格对应一套完整的引用格式规范，
    包括正文引用格式与参考文献列表格式。
    """

    GB_T_7714 = "gb_t_7714"  # 中国国家标准 GB/T 7714-2015
    APA = "apa"  # 美国心理学会第 7 版
    MLA = "mla"  # 现代语言协会第 9 版
    CHICAGO = "chicago"  # 芝加哥格式第 17 版（注释与参考文献制）
    IEEE = "ieee"  # IEEE 引用格式


class ReferenceType(str, Enum):
    """参考文献类型枚举。

    对应 GB/T 7714 中的文献类型标识，
    也映射到其他格式的等效类型。
    """

    JOURNAL = "journal"  # 期刊论文 [J]
    CONFERENCE = "conference"  # 会议论文 [C]
    BOOK = "book"  # 图书专著 [M]
    BOOK_CHAPTER = "book_chapter"  # 图书章节 [M]
    THESIS = "thesis"  # 学位论文 [D]
    DISSERTATION = "dissertation"  # 博士学位论文 [D]
    WEB_PAGE = "web_page"  # 网页资源 [EB/OL]
    TECH_REPORT = "tech_report"  # 技术报告 [R]
    PATENT = "patent"  # 专利 [P]
    STANDARD = "standard"  # 标准 [S]
    NEWSPAPER = "newspaper"  # 报纸文章 [N]
    SOFTWARE = "software"  # 软件 [CP]
    DATASET = "dataset"  # 数据集 [DS]
    OTHER = "other"  # 其他 [Z]


class SortKey(str, Enum):
    """参考文献排序键枚举。"""

    AUTHOR = "author"  # 按第一作者姓氏排序
    YEAR = "year"  # 按出版年份排序
    TITLE = "title"  # 按标题排序
    TYPE = "type"  # 按文献类型排序
    DOI = "doi"  # 按 DOI 排序


class CitationError(Exception):
    """引用格式化异常基类。"""

    pass


class ParseError(CitationError):
    """引用解析异常。"""

    pass


class ValidationError(CitationError):
    """引用校验异常。"""

    pass


# ===== 数据结构 =====


@dataclass
class Author:
    """作者信息。

    支持中英文作者名。对于中文作者，family 为姓，given 为名；
    对于英文作者，family 为姓氏，given 为名字。

    Attributes:
        family: 姓氏（中文为姓，英文为 last name）
        given: 名字（中文为名，英文为 first name）
        middle: 中间名（英文作者可能有）
        suffix: 后缀（如 Jr.、III 等）
        is_corporate: 是否为机构/团体作者
    """

    family: str = ""
    given: str = ""
    middle: str = ""
    suffix: str = ""
    is_corporate: bool = False

    def __post_init__(self) -> None:
        """初始化后处理：去除首尾空白。"""
        self.family = self.family.strip()
        self.given = self.given.strip()
        self.middle = self.middle.strip()
        self.suffix = self.suffix.strip()

    @property
    def is_chinese(self) -> bool:
        """判断是否为中文名（包含中文字符）。"""
        combined = self.family + self.given
        return any("\u4e00" <= ch <= "\u9fff" for ch in combined)

    @property
    def full_name(self) -> str:
        """获取完整姓名。

        中文作者返回"姓+名"，英文作者返回"First Middle Last"。
        机构作者直接返回机构名。
        """
        if self.is_corporate:
            return self.family
        if self.is_chinese:
            return f"{self.family}{self.given}"
        parts = [p for p in [self.given, self.middle, self.family] if p]
        return " ".join(parts)

    @property
    def display_name(self) -> str:
        """获取显示用姓名（姓在前，名缩写）。"""
        if self.is_corporate:
            return self.family
        if self.is_chinese:
            return f"{self.family}{self.given}"
        # 英文：Last, F. M.
        given_initial = f"{self.given[0]}." if self.given else ""
        middle_initial = f"{self.middle[0]}." if self.middle else ""
        initials = " ".join(p for p in [given_initial, middle_initial] if p)
        if initials:
            return f"{self.family}, {initials}"
        return self.family

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return {
            "family": self.family,
            "given": self.given,
            "middle": self.middle,
            "suffix": self.suffix,
            "is_corporate": self.is_corporate,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Author":
        """从字典创建作者实例。"""
        return cls(
            family=data.get("family", ""),
            given=data.get("given", ""),
            middle=data.get("middle", ""),
            suffix=data.get("suffix", ""),
            is_corporate=data.get("is_corporate", False),
        )

    @classmethod
    def parse(cls, raw: str) -> "Author":
        """从原始字符串解析作者。

        支持以下格式：
        - 中文："张三" 或 "张，三"
        - 英文："Smith, John" 或 "John Smith" 或 "Smith, J."
        - 机构："World Health Organization"

        Args:
            raw: 原始作者字符串

        Returns:
            Author 实例
        """
        raw = raw.strip()
        if not raw:
            return cls()

        # 判断是否为中文
        is_chinese = any("\u4e00" <= ch <= "\u9fff" for ch in raw)

        if is_chinese:
            # 中文作者处理
            if "，" in raw or "," in raw:
                # "张，三" 格式
                parts = re.split(r"[，,]", raw, maxsplit=1)
                return cls(family=parts[0].strip(), given=parts[1].strip() if len(parts) > 1 else "")
            elif len(raw) >= 2:
                # "张三" 格式：第一个字为姓，其余为名
                return cls(family=raw[0], given=raw[1:])
            else:
                return cls(family=raw)
        else:
            # 英文作者处理
            if "," in raw:
                # "Smith, John" 或 "Smith, J. M." 格式
                parts = raw.split(",", 1)
                family = parts[0].strip()
                given_part = parts[1].strip() if len(parts) > 1 else ""
                given_tokens = given_part.split()
                if len(given_tokens) >= 2:
                    # 可能包含中间名
                    given = given_tokens[0]
                    middle = " ".join(given_tokens[1:])
                else:
                    given = given_part
                    middle = ""
                return cls(family=family, given=given, middle=middle)
            else:
                # "John Smith" 或 "John M. Smith" 格式
                tokens = raw.split()
                if len(tokens) == 1:
                    # 可能是机构名
                    return cls(family=tokens[0], is_corporate=True)
                elif len(tokens) == 2:
                    return cls(family=tokens[1], given=tokens[0])
                else:
                    # "John M. Smith" - 最后一个为姓，第一个为名，中间为中间名
                    family = tokens[-1]
                    given = tokens[0]
                    middle = " ".join(tokens[1:-1])
                    return cls(family=family, given=given, middle=middle)


@dataclass
class Reference:
    """参考文献数据结构。

    表示一条完整的参考文献信息，支持多种文献类型。
    不同类型使用不同的字段组合。

    Attributes:
        type: 文献类型
        authors: 作者列表
        title: 标题
        year: 出版年份
        journal: 期刊名称（期刊论文用）
        volume: 卷号
        issue: 期号
        pages: 页码范围（如 "512-528"）
        publisher: 出版社
        city: 出版城市
        doi: 数字对象标识符
        url: 网址
        access_date: 访问日期（网页资源用）
        book_title: 书名（图书章节用）
        editors: 编者列表
        edition: 版次
        series: 丛书名
        isbn: ISBN 号
        issn: ISSN 号
        conference_name: 会议名称
        conference_location: 会议地点
        conference_date: 会议日期
        degree: 学位级别（学位论文用）
        university: 授予学位大学（学位论文用）
        patent_number: 专利号
        patent_country: 专利国别
        standard_number: 标准号
        newspaper_name: 报纸名称
        pub_date: 出版日期（精确到日）
        language: 语言
        note: 备注
        raw: 原始引用字符串
    """

    type: ReferenceType = ReferenceType.JOURNAL
    authors: List[Author] = field(default_factory=list)
    title: str = ""
    year: str = ""
    journal: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    publisher: str = ""
    city: str = ""
    doi: str = ""
    url: str = ""
    access_date: str = ""
    book_title: str = ""
    editors: List[Author] = field(default_factory=list)
    edition: str = ""
    series: str = ""
    isbn: str = ""
    issn: str = ""
    conference_name: str = ""
    conference_location: str = ""
    conference_date: str = ""
    degree: str = ""
    university: str = ""
    patent_number: str = ""
    patent_country: str = ""
    standard_number: str = ""
    newspaper_name: str = ""
    pub_date: str = ""
    language: str = "zh"
    note: str = ""
    raw: str = ""

    def __post_init__(self) -> None:
        """初始化后处理。"""
        # 确保年份为字符串
        if self.year and not isinstance(self.year, str):
            self.year = str(self.year)
        self.year = self.year.strip()

    @property
    def first_author(self) -> Optional[Author]:
        """获取第一作者。"""
        return self.authors[0] if self.authors else None

    @property
    def author_count(self) -> int:
        """作者数量。"""
        return len(self.authors)

    @property
    def has_doi(self) -> bool:
        """是否有 DOI。"""
        return bool(self.doi and self.doi.strip())

    @property
    def has_url(self) -> bool:
        """是否有 URL。"""
        return bool(self.url and self.url.strip())

    @property
    def is_online_resource(self) -> bool:
        """是否为在线资源。"""
        return self.has_url or self.type in (
            ReferenceType.WEB_PAGE,
            ReferenceType.SOFTWARE,
            ReferenceType.DATASET,
        )

    @property
    def type_label_cn(self) -> str:
        """获取中文文献类型标签。"""
        labels = {
            ReferenceType.JOURNAL: "期刊论文",
            ReferenceType.CONFERENCE: "会议论文",
            ReferenceType.BOOK: "图书专著",
            ReferenceType.BOOK_CHAPTER: "图书章节",
            ReferenceType.THESIS: "学位论文",
            ReferenceType.DISSERTATION: "博士学位论文",
            ReferenceType.WEB_PAGE: "网页资源",
            ReferenceType.TECH_REPORT: "技术报告",
            ReferenceType.PATENT: "专利",
            ReferenceType.STANDARD: "标准",
            ReferenceType.NEWSPAPER: "报纸文章",
            ReferenceType.SOFTWARE: "软件",
            ReferenceType.DATASET: "数据集",
            ReferenceType.OTHER: "其他",
        }
        return labels.get(self.type, "其他")

    @property
    def gbt_type_code(self) -> str:
        """获取 GB/T 7714 文献类型代码。"""
        codes = {
            ReferenceType.JOURNAL: "J",
            ReferenceType.CONFERENCE: "C",
            ReferenceType.BOOK: "M",
            ReferenceType.BOOK_CHAPTER: "M",
            ReferenceType.THESIS: "D",
            ReferenceType.DISSERTATION: "D",
            ReferenceType.WEB_PAGE: "EB/OL",
            ReferenceType.TECH_REPORT: "R",
            ReferenceType.PATENT: "P",
            ReferenceType.STANDARD: "S",
            ReferenceType.NEWSPAPER: "N",
            ReferenceType.SOFTWARE: "CP",
            ReferenceType.DATASET: "DS",
            ReferenceType.OTHER: "Z",
        }
        return codes.get(self.type, "Z")

    def fingerprint(self) -> str:
        """生成参考文献的唯一指纹（用于去重）。

        基于 DOI（若有）或标题+第一作者+年份生成哈希。

        Returns:
            指纹字符串（MD5 哈希的前 16 位）
        """
        if self.has_doi:
            key = f"doi:{self.doi.lower().strip()}"
        else:
            first_author = self.first_author.family.lower() if self.first_author else ""
            title_key = re.sub(r"[^\w]", "", self.title.lower())[:100]
            key = f"title:{title_key}|author:{first_author}|year:{self.year}"
        return hashlib.md5(key.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return {
            "type": self.type.value,
            "authors": [a.to_dict() for a in self.authors],
            "title": self.title,
            "year": self.year,
            "journal": self.journal,
            "volume": self.volume,
            "issue": self.issue,
            "pages": self.pages,
            "publisher": self.publisher,
            "city": self.city,
            "doi": self.doi,
            "url": self.url,
            "access_date": self.access_date,
            "book_title": self.book_title,
            "editors": [e.to_dict() for e in self.editors],
            "edition": self.edition,
            "series": self.series,
            "isbn": self.isbn,
            "issn": self.issn,
            "conference_name": self.conference_name,
            "conference_location": self.conference_location,
            "conference_date": self.conference_date,
            "degree": self.degree,
            "university": self.university,
            "patent_number": self.patent_number,
            "patent_country": self.patent_country,
            "standard_number": self.standard_number,
            "newspaper_name": self.newspaper_name,
            "pub_date": self.pub_date,
            "language": self.language,
            "note": self.note,
            "raw": self.raw,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Reference":
        """从字典创建参考文献实例。"""
        # 处理类型
        type_val = data.get("type", "journal")
        if isinstance(type_val, str):
            try:
                ref_type = ReferenceType(type_val)
            except ValueError:
                ref_type = ReferenceType.OTHER
        elif isinstance(type_val, ReferenceType):
            ref_type = type_val
        else:
            ref_type = ReferenceType.OTHER

        # 处理作者列表
        authors_data = data.get("authors", [])
        authors = []
        for a in authors_data:
            if isinstance(a, Author):
                authors.append(a)
            elif isinstance(a, dict):
                authors.append(Author.from_dict(a))
            elif isinstance(a, str):
                authors.append(Author.parse(a))

        # 处理编者列表
        editors_data = data.get("editors", [])
        editors = []
        for e in editors_data:
            if isinstance(e, Author):
                editors.append(e)
            elif isinstance(e, dict):
                editors.append(Author.from_dict(e))
            elif isinstance(e, str):
                editors.append(Author.parse(e))

        return cls(
            type=ref_type,
            authors=authors,
            title=data.get("title", ""),
            year=str(data.get("year", "")),
            journal=data.get("journal", ""),
            volume=data.get("volume", ""),
            issue=data.get("issue", ""),
            pages=data.get("pages", ""),
            publisher=data.get("publisher", ""),
            city=data.get("city", ""),
            doi=data.get("doi", ""),
            url=data.get("url", ""),
            access_date=data.get("access_date", ""),
            book_title=data.get("book_title", ""),
            editors=editors,
            edition=data.get("edition", ""),
            series=data.get("series", ""),
            isbn=data.get("isbn", ""),
            issn=data.get("issn", ""),
            conference_name=data.get("conference_name", ""),
            conference_location=data.get("conference_location", ""),
            conference_date=data.get("conference_date", ""),
            degree=data.get("degree", ""),
            university=data.get("university", ""),
            patent_number=data.get("patent_number", ""),
            patent_country=data.get("patent_country", ""),
            standard_number=data.get("standard_number", ""),
            newspaper_name=data.get("newspaper_name", ""),
            pub_date=data.get("pub_date", ""),
            language=data.get("language", "zh"),
            note=data.get("note", ""),
            raw=data.get("raw", ""),
        )


@dataclass
class ValidationResult:
    """引用校验结果。"""

    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        """添加错误。"""
        self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str) -> None:
        """添加警告。"""
        self.warnings.append(message)

    def add_missing(self, field_name: str) -> None:
        """添加缺失字段。"""
        self.missing_fields.append(field_name)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "missing_fields": self.missing_fields,
        }


@dataclass
class FormatStats:
    """格式化统计信息。"""

    total: int = 0
    by_type: Dict[str, int] = field(default_factory=dict)
    by_style: Dict[str, int] = field(default_factory=dict)
    duplicates: int = 0
    invalid: int = 0
    with_doi: int = 0
    with_url: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return {
            "total": self.total,
            "by_type": dict(self.by_type),
            "by_style": dict(self.by_style),
            "duplicates": self.duplicates,
            "invalid": self.invalid,
            "with_doi": self.with_doi,
            "with_url": self.with_url,
        }


# ===== 作者格式化辅助函数 =====


def format_authors_gbt(authors: List[Author], max_authors: int = 3) -> str:
    """按 GB/T 7714 格式化作者列表。

    GB/T 7714 规定：作者不超过 3 人时全部列出，超过 3 人时只列前 3 人，后加"等"。

    Args:
        authors: 作者列表
        max_authors: 最大列出作者数

    Returns:
        格式化后的作者字符串
    """
    if not authors:
        return ""
    if len(authors) <= max_authors:
        names = [a.full_name for a in authors]
        return ", ".join(names)
    else:
        names = [a.full_name for a in authors[:max_authors]]
        return ", ".join(names) + ", 等"


def format_authors_apa(authors: List[Author], max_authors: int = 20) -> str:
    """按 APA 第 7 版格式化作者列表。

    APA 7 规定：
    - 1-20 位作者：全部列出，最后一位前用 "&"
    - 超过 20 位：列出前 19 位，加 "..."，再列最后一位
    - 英文作者：姓在前，名缩写为首字母

    Args:
        authors: 作者列表
        max_authors: 最大列出作者数

    Returns:
        格式化后的作者字符串
    """
    if not authors:
        return ""

    def format_single(a: Author) -> str:
        """格式化单个作者。"""
        if a.is_corporate:
            return a.family
        if a.is_chinese:
            return a.full_name
        # 英文：Last, F. M.
        return a.display_name

    if len(authors) == 1:
        return format_single(authors[0])
    elif len(authors) <= max_authors:
        formatted = [format_single(a) for a in authors[:-1]]
        last = format_single(authors[-1])
        return ", ".join(formatted) + ", & " + last
    else:
        # 超过 20 位
        formatted = [format_single(a) for a in authors[:19]]
        last = format_single(authors[-1])
        return ", ".join(formatted) + ", . . . " + last


def format_authors_mla(authors: List[Author]) -> str:
    """按 MLA 第 9 版格式化作者列表。

    MLA 9 规定：
    - 1 位作者：Last, First
    - 2 位作者：Last, First, and First Last
    - 3 位及以上：第一位 + "et al."
    - 英文作者：姓在前，名在后

    Args:
        authors: 作者列表

    Returns:
        格式化后的作者字符串
    """
    if not authors:
        return ""

    def format_first(a: Author) -> str:
        """格式化第一位作者（姓在前）。"""
        if a.is_corporate:
            return a.family
        if a.is_chinese:
            return a.full_name
        # 英文：Last, First Middle
        parts = [a.family]
        if a.given:
            parts.append(a.given)
        if a.middle:
            parts.append(a.middle)
        if len(parts) > 1:
            return parts[0] + ", " + " ".join(parts[1:])
        return parts[0]

    def format_subsequent(a: Author) -> str:
        """格式化后续作者（名在前）。"""
        if a.is_corporate:
            return a.family
        if a.is_chinese:
            return a.full_name
        return a.full_name

    if len(authors) == 1:
        return format_first(authors[0])
    elif len(authors) == 2:
        return format_first(authors[0]) + ", and " + format_subsequent(authors[1])
    else:
        return format_first(authors[0]) + ", et al."


def format_authors_chicago(authors: List[Author], max_authors: int = 10) -> str:
    """按芝加哥格式第 17 版格式化作者列表。

    Chicago 17 规定：
    - 参考文献列表中：1-10 位作者全部列出，第一位姓在前，其余名在前
    - 超过 10 位：列出前 7 位，加 "et al."

    Args:
        authors: 作者列表
        max_authors: 最大列出作者数

    Returns:
        格式化后的作者字符串
    """
    if not authors:
        return ""

    def format_first(a: Author) -> str:
        """格式化第一位作者（姓在前）。"""
        if a.is_corporate:
            return a.family
        if a.is_chinese:
            return a.full_name
        parts = [a.family]
        if a.given:
            parts.append(a.given)
        if a.middle:
            parts.append(a.middle)
        if len(parts) > 1:
            return parts[0] + ", " + " ".join(parts[1:])
        return parts[0]

    def format_subsequent(a: Author) -> str:
        """格式化后续作者（名在前）。"""
        if a.is_corporate:
            return a.family
        if a.is_chinese:
            return a.full_name
        return a.full_name

    if len(authors) == 1:
        return format_first(authors[0])
    elif len(authors) <= max_authors:
        parts = [format_first(authors[0])]
        for a in authors[1:]:
            parts.append(format_subsequent(a))
        return ", ".join(parts[:-1]) + ", and " + parts[-1]
    else:
        parts = [format_first(authors[0])]
        for a in authors[1:7]:
            parts.append(format_subsequent(a))
        return ", ".join(parts) + ", et al."


def format_authors_ieee(authors: List[Author]) -> str:
    """按 IEEE 格式格式化作者列表。

    IEEE 规定：
    - 作者格式：F. M. Last
    - 1 位作者：直接列出
    - 2 位作者：A and B
    - 3-6 位作者：A, B, C, . . ., and F
    - 超过 6 位：第一位 + "et al."

    Args:
        authors: 作者列表

    Returns:
        格式化后的作者字符串
    """
    if not authors:
        return ""

    def format_single(a: Author) -> str:
        """格式化单个作者（名缩写在姓前）。"""
        if a.is_corporate:
            return a.family
        if a.is_chinese:
            return a.full_name
        # 英文：F. M. Last
        initials = []
        if a.given:
            initials.append(f"{a.given[0]}.")
        if a.middle:
            initials.append(f"{a.middle[0]}.")
        if initials:
            return " ".join(initials) + " " + a.family
        return a.family

    if len(authors) == 1:
        return format_single(authors[0])
    elif len(authors) == 2:
        return format_single(authors[0]) + " and " + format_single(authors[1])
    elif len(authors) <= 6:
        formatted = [format_single(a) for a in authors[:-1]]
        last = format_single(authors[-1])
        return ", ".join(formatted) + ", and " + last
    else:
        return format_single(authors[0]) + " et al."


# ===== 页码格式化辅助函数 =====


def format_pages_gbt(pages: str) -> str:
    """按 GB/T 7714 格式化页码。

    GB/T 7714 使用 "512-528" 格式（保留完整页码）。

    Args:
        pages: 原始页码字符串

    Returns:
        格式化后的页码字符串
    """
    if not pages:
        return ""
    pages = pages.strip()
    # 处理各种分隔符
    pages = re.sub(r"\s*[-–—]\s*", "-", pages)
    return pages


def format_pages_apa(pages: str) -> str:
    """按 APA 第 7 版格式化页码。

    APA 7 使用 "512-528" 格式，但若起止页码有共同前缀则省略，
    如 "512-528" 保持不变，"512-512" 变为 "512"。

    Args:
        pages: 原始页码字符串

    Returns:
        格式化后的页码字符串
    """
    if not pages:
        return ""
    pages = pages.strip()
    parts = re.split(r"[-–—]", pages)
    if len(parts) == 2:
        start = parts[0].strip()
        end = parts[1].strip()
        if start == end:
            return start
        return f"{start}-{end}"
    return pages


def format_pages_mla(pages: str) -> str:
    """按 MLA 第 9 版格式化页码。

    MLA 9 使用 "512-28" 格式（省略共同前缀）。

    Args:
        pages: 原始页码字符串

    Returns:
        格式化后的页码字符串
    """
    if not pages:
        return ""
    pages = pages.strip()
    parts = re.split(r"[-–—]", pages)
    if len(parts) == 2:
        start = parts[0].strip()
        end = parts[1].strip()
        if start == end:
            return start
        # 省略共同前缀
        if len(end) < len(start):
            common_len = len(start) - len(end)
            if start[:common_len] == end[: len(end) - len(start) + common_len]:
                # 不做复杂处理，直接返回
                pass
        # MLA 简化：如果起止页码第二位不同，只保留不同的部分
        if len(start) >= 2 and len(end) >= 1:
            # 找到共同前缀
            common = 0
            min_len = min(len(start), len(end))
            for i in range(min_len):
                if start[i] == end[i]:
                    common = i + 1
                else:
                    break
            if common > 0 and common < len(start):
                end_short = end[common:]
                if end_short:
                    return f"{start}-{end_short}"
        return f"{start}-{end}"
    return pages


def format_pages_chicago(pages: str) -> str:
    """按芝加哥格式格式化页码。

    Chicago 17 使用 "512-28" 格式（省略共同前缀），
    但百位以上页码变化时保留完整。

    Args:
        pages: 原始页码字符串

    Returns:
        格式化后的页码字符串
    """
    if not pages:
        return ""
    pages = pages.strip()
    parts = re.split(r"[-–—]", pages)
    if len(parts) == 2:
        start = parts[0].strip()
        end = parts[1].strip()
        if start == end:
            return start
        # Chicago: 如果百位相同，省略百位
        if len(start) == 3 and len(end) == 3 and start[0] == end[0]:
            return f"{start}-{end[1:]}"
        elif len(start) == 4 and len(end) == 4 and start[:2] == end[:2]:
            return f"{start}-{end[2:]}"
        return f"{start}-{end}"
    return pages


def format_pages_ieee(pages: str) -> str:
    """按 IEEE 格式格式化页码。

    IEEE 使用 "pp. 512-528" 格式。

    Args:
        pages: 原始页码字符串

    Returns:
        格式化后的页码字符串
    """
    if not pages:
        return ""
    pages = pages.strip()
    parts = re.split(r"[-–—]", pages)
    if len(parts) == 2:
        start = parts[0].strip()
        end = parts[1].strip()
        if start == end:
            return f"p. {start}"
        return f"pp. {start}-{end}"
    return f"pp. {pages}"


# ===== GB/T 7714 格式化器 =====


class GBT7714Formatter:
    """GB/T 7714-2015 引用格式化器。

    实现中国国家标准 GB/T 7714-2015《信息与文献 参考文献著录规则》。
    """

    @staticmethod
    def format_bibliography(ref: Reference) -> str:
        """格式化参考文献列表条目。

        Args:
            ref: 参考文献数据

        Returns:
            格式化后的参考文献字符串
        """
        parts: List[str] = []

        # 作者
        authors_str = format_authors_gbt(ref.authors)
        if authors_str:
            parts.append(authors_str)

        # 标题 + 文献类型标识
        title = ref.title.strip()
        if title:
            type_code = ref.gbt_type_code
            if ref.is_online_resource:
                if type_code == "EB/OL":
                    title = f"{title}[{type_code}]"
                else:
                    title = f"{title}[{type_code}/OL]"
            else:
                title = f"{title}[{type_code}]"
            parts.append(title)

        # 根据类型添加不同字段
        if ref.type == ReferenceType.JOURNAL:
            # 期刊论文：刊名, 年, 卷(期): 页码
            if ref.journal:
                parts.append(ref.journal)
            pub_info = ref.year
            if ref.volume:
                pub_info += f", {ref.volume}"
                if ref.issue:
                    pub_info += f"({ref.issue})"
            elif ref.issue:
                pub_info += f"({ref.issue})"
            if ref.pages:
                pub_info += f": {format_pages_gbt(ref.pages)}"
            parts.append(pub_info)

        elif ref.type in (ReferenceType.CONFERENCE,):
            # 会议论文：会议名, 会议地点, 会议日期: 页码
            if ref.conference_name:
                parts.append(ref.conference_name)
            location_date = []
            if ref.conference_location:
                location_date.append(ref.conference_location)
            if ref.conference_date:
                location_date.append(ref.conference_date)
            elif ref.year:
                location_date.append(ref.year)
            if location_date:
                parts.append(", ".join(location_date))
            if ref.pages:
                parts.append(f": {format_pages_gbt(ref.pages)}")

        elif ref.type in (ReferenceType.BOOK, ReferenceType.BOOK_CHAPTER):
            # 图书：出版地: 出版社, 年: 页码
            pub_parts = []
            if ref.city:
                pub_parts.append(ref.city)
            if ref.publisher:
                pub_parts.append(ref.publisher)
            if ref.year:
                pub_parts.append(ref.year)
            if pub_parts:
                parts.append(": ".join(pub_parts[:1] + [", ".join(pub_parts[1:])]) if len(pub_parts) > 1 else pub_parts[0])
            if ref.edition:
                parts.append(f"{ref.edition}版")
            if ref.pages and ref.type == ReferenceType.BOOK_CHAPTER:
                parts.append(f": {format_pages_gbt(ref.pages)}")

        elif ref.type in (ReferenceType.THESIS, ReferenceType.DISSERTATION):
            # 学位论文：授予学位单位, 年
            if ref.university:
                parts.append(ref.university)
            if ref.year:
                parts.append(ref.year)

        elif ref.type == ReferenceType.WEB_PAGE:
            # 网页：出版地: 出版者, 年(更新日期)[引用日期]
            if ref.publisher:
                parts.append(ref.publisher)
            date_parts = []
            if ref.pub_date:
                date_parts.append(ref.pub_date)
            elif ref.year:
                date_parts.append(ref.year)
            if ref.access_date:
                date_parts.append(f"[{ref.access_date}]")
            if date_parts:
                parts.append("".join(date_parts))
            if ref.url:
                parts.append(ref.url)

        elif ref.type == ReferenceType.TECH_REPORT:
            # 技术报告：出版地: 机构, 年
            if ref.city:
                parts.append(ref.city)
            if ref.publisher:
                parts.append(ref.publisher)
            if ref.year:
                parts.append(ref.year)

        elif ref.type == ReferenceType.PATENT:
            # 专利：专利国别, 专利号
            if ref.patent_country:
                parts.append(ref.patent_country)
            if ref.patent_number:
                parts.append(ref.patent_number)
            if ref.year:
                parts.append(ref.year)

        elif ref.type == ReferenceType.STANDARD:
            # 标准：出版地: 出版社, 年
            if ref.standard_number:
                parts.append(ref.standard_number)
            if ref.year:
                parts.append(ref.year)

        elif ref.type == ReferenceType.NEWSPAPER:
            # 报纸：报纸名, 出版日期(版次)
            if ref.newspaper_name:
                parts.append(ref.newspaper_name)
            if ref.pub_date:
                parts.append(ref.pub_date)
            if ref.year:
                parts.append(ref.year)

        else:
            # 其他类型
            if ref.publisher:
                parts.append(ref.publisher)
            if ref.year:
                parts.append(ref.year)

        # DOI
        if ref.has_doi:
            parts.append(f"DOI:{ref.doi}")

        return ". ".join(parts) + "." if parts else ""

    @staticmethod
    def format_in_text(ref: Reference, mode: str = "sequential") -> str:
        """格式化正文引用。

        GB/T 7714 支持两种正文引用方式：
        - 顺序编码制：[1] 或 [1-3]
        - 著者-出版年制：(张三, 2024) 或 (Smith, 2024)

        Args:
            ref: 参考文献数据
            mode: 引用模式，"sequential"（顺序编码）或 "author_date"（著者-出版年）

        Returns:
            正文引用字符串
        """
        if mode == "author_date":
            # 著者-出版年制
            if ref.first_author:
                author_name = ref.first_author.family if ref.first_author.is_chinese else ref.first_author.family
                if ref.year:
                    return f"({author_name}, {ref.year})"
                else:
                    return f"({author_name})"
            elif ref.year:
                return f"({ref.year})"
            return ""
        else:
            # 顺序编码制：需要外部编号，这里返回占位符
            return "[?]"
        # 注：顺序编码制的实际编号由 CitationFormatter 统一管理


# ===== APA 格式化器 =====


class APAFormatter:
    """APA 第 7 版引用格式化器。

    实现美国心理学会（APA）第 7 版引用格式。
    """

    @staticmethod
    def format_bibliography(ref: Reference) -> str:
        """格式化参考文献列表条目。

        Args:
            ref: 参考文献数据

        Returns:
            格式化后的参考文献字符串
        """
        parts: List[str] = []

        # 作者
        authors_str = format_authors_apa(ref.authors)
        if authors_str:
            parts.append(authors_str)

        # 年份
        if ref.year:
            parts.append(f"({ref.year}).")
        else:
            parts.append("(n.d.).")

        # 标题
        if ref.title:
            # APA: 期刊论文标题不斜体，书名斜体
            if ref.type in (ReferenceType.BOOK, ReferenceType.BOOK_CHAPTER):
                parts.append(f"*{ref.title}*.")
            else:
                parts.append(f"{ref.title}.")

        # 根据类型添加不同字段
        if ref.type == ReferenceType.JOURNAL:
            # 期刊：期刊名(斜体), 卷(斜体)(期), 页码
            if ref.journal:
                journal_str = f"*{ref.journal}*"
                if ref.volume:
                    journal_str += f", *{ref.volume}*"
                    if ref.issue:
                        journal_str += f"({ref.issue})"
                parts.append(journal_str)
            if ref.pages:
                parts.append(format_pages_apa(ref.pages))

        elif ref.type == ReferenceType.CONFERENCE:
            # 会议论文：会议名(斜体), 页码
            if ref.conference_name:
                parts.append(f"*{ref.conference_name}*.")
            if ref.pages:
                parts.append(format_pages_apa(ref.pages))

        elif ref.type in (ReferenceType.BOOK,):
            # 图书：版次, 出版社
            if ref.edition:
                parts.append(f"({ref.edition} ed.).")
            if ref.publisher:
                parts.append(ref.publisher)

        elif ref.type == ReferenceType.BOOK_CHAPTER:
            # 图书章节：In Editors (Eds.), Book title (pp. xxx-xxx). Publisher
            if ref.editors:
                editors_str = format_authors_apa(ref.editors)
                parts.append(f"In {editors_str} (Eds.),")
            else:
                parts.append("In")
            if ref.book_title:
                parts.append(f"*{ref.book_title}*")
            if ref.pages:
                parts.append(f"({format_pages_apa(ref.pages)}).")
            if ref.publisher:
                parts.append(ref.publisher)

        elif ref.type in (ReferenceType.THESIS, ReferenceType.DISSERTATION):
            # 学位论文：大学, 数据库/机构
            degree_type = "Doctoral dissertation" if ref.type == ReferenceType.DISSERTATION else "Master's thesis"
            parts.append(f"[{degree_type}]")
            if ref.university:
                parts.append(f"{ref.university}.")

        elif ref.type == ReferenceType.WEB_PAGE:
            # 网页：网站名, URL
            if ref.publisher:
                parts.append(f"{ref.publisher}.")
            if ref.access_date:
                parts.append(f"Retrieved {ref.access_date}")
            if ref.url:
                parts.append(f"from {ref.url}")

        elif ref.type == ReferenceType.TECH_REPORT:
            # 技术报告
            if ref.publisher:
                parts.append(f"{ref.publisher}.")
            if ref.pages:
                parts.append(format_pages_apa(ref.pages))

        elif ref.type == ReferenceType.NEWSPAPER:
            # 报纸文章
            if ref.newspaper_name:
                parts.append(f"*{ref.newspaper_name}*.")
            if ref.pub_date:
                parts.append(ref.pub_date)

        else:
            if ref.publisher:
                parts.append(ref.publisher)

        # DOI
        if ref.has_doi:
            parts.append(f"https://doi.org/{ref.doi}")

        return " ".join(parts)

    @staticmethod
    def format_in_text(ref: Reference, mode: str = "parenthetical") -> str:
        """格式化正文引用。

        APA 7 支持两种正文引用：
        - 括号引用：(Smith, 2024) 或 (Smith & Jones, 2024)
        - 叙述引用：Smith (2024)

        Args:
            ref: 参考文献数据
            mode: "parenthetical"（括号引用）或 "narrative"（叙述引用）

        Returns:
            正文引用字符串
        """
        if not ref.authors:
            if ref.title:
                short_title = ref.title[:30] + ("..." if len(ref.title) > 30 else "")
                if ref.year:
                    return f"({short_title}, {ref.year})"
                return f"({short_title}, n.d.)"
            return ""

        if mode == "narrative":
            # 叙述引用：Smith (2024)
            if len(ref.authors) == 1:
                author = ref.authors[0]
                name = author.family if not author.is_chinese else author.full_name
            elif len(ref.authors) == 2:
                names = []
                for a in ref.authors:
                    name = a.family if not a.is_chinese else a.full_name
                    names.append(name)
                name = " and ".join(names)
            else:
                first = ref.authors[0]
                name = first.family if not first.is_chinese else first.full_name
                name += " et al."
            year = ref.year if ref.year else "n.d."
            return f"{name} ({year})"
        else:
            # 括号引用：(Smith, 2024)
            if len(ref.authors) == 1:
                author = ref.authors[0]
                name = author.family if not author.is_chinese else author.full_name
            elif len(ref.authors) == 2:
                names = []
                for a in ref.authors:
                    n = a.family if not a.is_chinese else a.full_name
                    names.append(n)
                name = " & ".join(names)
            else:
                first = ref.authors[0]
                name = first.family if not first.is_chinese else first.full_name
                name += " et al."
            year = ref.year if ref.year else "n.d."
            return f"({name}, {year})"


# ===== MLA 格式化器 =====


class MLAFormatter:
    """MLA 第 9 版引用格式化器。

    实现现代语言协会（MLA）第 9 版引用格式。
    """

    @staticmethod
    def format_bibliography(ref: Reference) -> str:
        """格式化参考文献列表条目（Works Cited）。

        Args:
            ref: 参考文献数据

        Returns:
            格式化后的参考文献字符串
        """
        parts: List[str] = []

        # 作者
        authors_str = format_authors_mla(ref.authors)
        if authors_str:
            parts.append(authors_str + ".")

        # 标题
        if ref.title:
            # MLA: 文章标题用引号，书名/期刊名用斜体
            if ref.type in (ReferenceType.JOURNAL, ReferenceType.CONFERENCE,
                            ReferenceType.NEWSPAPER, ReferenceType.WEB_PAGE,
                            ReferenceType.BOOK_CHAPTER):
                parts.append(f'"{ref.title}."')
            else:
                parts.append(f"*{ref.title}.*")

        # 根据类型添加不同字段
        if ref.type == ReferenceType.JOURNAL:
            # 期刊：*期刊名*, vol. X, no. Y, 年, pp. xxx-xxx.
            if ref.journal:
                parts.append(f"*{ref.journal},*")
            vol_issue = []
            if ref.volume:
                vol_issue.append(f"vol. {ref.volume}")
            if ref.issue:
                vol_issue.append(f"no. {ref.issue}")
            if ref.year:
                vol_issue.append(ref.year)
            if vol_issue:
                parts.append(", ".join(vol_issue) + ",")
            if ref.pages:
                parts.append(f"{format_pages_mla(ref.pages)}.")

        elif ref.type == ReferenceType.CONFERENCE:
            # 会议论文
            if ref.conference_name:
                parts.append(f"*{ref.conference_name},*")
            if ref.year:
                parts.append(f"{ref.year},")
            if ref.pages:
                parts.append(f"{format_pages_mla(ref.pages)}.")

        elif ref.type in (ReferenceType.BOOK,):
            # 图书：Publisher, Year.
            if ref.publisher:
                parts.append(f"{ref.publisher},")
            if ref.year:
                parts.append(f"{ref.year}.")

        elif ref.type == ReferenceType.BOOK_CHAPTER:
            # 图书章节
            if ref.editors:
                editors_str = format_authors_mla(ref.editors)
                parts.append(f"edited by {editors_str},")
            if ref.book_title:
                parts.append(f"*{ref.book_title},*")
            if ref.publisher:
                parts.append(f"{ref.publisher},")
            if ref.year:
                parts.append(f"{ref.year},")
            if ref.pages:
                parts.append(f"{format_pages_mla(ref.pages)}.")

        elif ref.type in (ReferenceType.THESIS, ReferenceType.DISSERTATION):
            # 学位论文
            degree = "PhD dissertation" if ref.type == ReferenceType.DISSERTATION else "Master's thesis"
            parts.append(f"{degree},")
            if ref.university:
                parts.append(f"{ref.university},")
            if ref.year:
                parts.append(f"{ref.year}.")

        elif ref.type == ReferenceType.WEB_PAGE:
            # 网页
            if ref.publisher:
                parts.append(f"{ref.publisher},")
            if ref.pub_date or ref.year:
                parts.append(f"{ref.pub_date or ref.year}.")
            if ref.url:
                if ref.access_date:
                    parts.append(f"Accessed {ref.access_date},")
                parts.append(ref.url + ".")

        elif ref.type == ReferenceType.NEWSPAPER:
            # 报纸
            if ref.newspaper_name:
                parts.append(f"*{ref.newspaper_name},*")
            if ref.pub_date or ref.year:
                parts.append(f"{ref.pub_date or ref.year},")
            if ref.pages:
                parts.append(f"{format_pages_mla(ref.pages)}.")

        else:
            if ref.publisher:
                parts.append(f"{ref.publisher},")
            if ref.year:
                parts.append(f"{ref.year}.")

        return " ".join(parts)

    @staticmethod
    def format_in_text(ref: Reference) -> str:
        """格式化正文引用。

        MLA 使用括号引用：(Smith 123) 或 (Smith and Jones 123)。
        若无页码则只标注作者。

        Args:
            ref: 参考文献数据

        Returns:
            正文引用字符串
        """
        if not ref.authors:
            if ref.title:
                short_title = ref.title.split(":")[0][:30]
                return f'("{short_title}")'
            return ""

        if len(ref.authors) == 1:
            author = ref.authors[0]
            name = author.family if not author.is_chinese else author.full_name
        elif len(ref.authors) == 2:
            names = []
            for a in ref.authors:
                n = a.family if not a.is_chinese else a.full_name
                names.append(n)
            name = " and ".join(names)
        else:
            first = ref.authors[0]
            name = first.family if not first.is_chinese else first.full_name
            name += " et al."

        if ref.pages:
            return f"({name} {format_pages_mla(ref.pages).split('-')[0]})"
        return f"({name})"


# ===== Chicago 格式化器 =====


class ChicagoFormatter:
    """芝加哥格式第 17 版引用格式化器。

    实现芝加哥格式第 17 版（Notes and Bibliography 制）。
    """

    @staticmethod
    def format_bibliography(ref: Reference) -> str:
        """格式化参考文献列表条目。

        Args:
            ref: 参考文献数据

        Returns:
            格式化后的参考文献字符串
        """
        parts: List[str] = []

        # 作者
        authors_str = format_authors_chicago(ref.authors)
        if authors_str:
            parts.append(authors_str + ".")

        # 标题
        if ref.title:
            # Chicago: 文章标题用引号，书名/期刊名用斜体
            if ref.type in (ReferenceType.JOURNAL, ReferenceType.CONFERENCE,
                            ReferenceType.NEWSPAPER, ReferenceType.BOOK_CHAPTER,
                            ReferenceType.WEB_PAGE):
                parts.append(f'"{ref.title}."')
            else:
                parts.append(f"*{ref.title}.*")

        # 根据类型添加不同字段
        if ref.type == ReferenceType.JOURNAL:
            # 期刊：*期刊名* X, no. Y (Year): xxx-xxx.
            if ref.journal:
                journal_str = f"*{ref.journal}*"
                if ref.volume:
                    journal_str += f" {ref.volume}"
                    if ref.issue:
                        journal_str += f", no. {ref.issue}"
                elif ref.issue:
                    journal_str += f", no. {ref.issue}"
                parts.append(journal_str)
            date_str = ""
            if ref.year:
                date_str = f"({ref.year})"
            if date_str:
                parts.append(date_str)
            if ref.pages:
                parts.append(f": {format_pages_chicago(ref.pages)}.")

        elif ref.type == ReferenceType.CONFERENCE:
            # 会议论文
            if ref.conference_name:
                parts.append(f"In *{ref.conference_name}*.")
            if ref.year:
                parts.append(f"{ref.year}.")
            if ref.pages:
                parts.append(f"{format_pages_chicago(ref.pages)}.")

        elif ref.type in (ReferenceType.BOOK,):
            # 图书：Place: Publisher, Year.
            pub_parts = []
            if ref.city:
                pub_parts.append(ref.city)
            if ref.publisher:
                pub_parts.append(ref.publisher)
            if ref.year:
                pub_parts.append(ref.year)
            if pub_parts:
                parts.append(": ".join([pub_parts[0]] + [", ".join(pub_parts[1:])]) if len(pub_parts) > 1 else pub_parts[0])

        elif ref.type == ReferenceType.BOOK_CHAPTER:
            # 图书章节：In Book, edited by Editors, xxx-xxx. Place: Publisher, Year.
            if ref.book_title:
                parts.append(f"In *{ref.book_title},*")
            if ref.editors:
                editors_str = format_authors_chicago(ref.editors)
                parts.append(f"edited by {editors_str},")
            if ref.pages:
                parts.append(f"{format_pages_chicago(ref.pages)}.")
            pub_parts = []
            if ref.city:
                pub_parts.append(ref.city)
            if ref.publisher:
                pub_parts.append(ref.publisher)
            if ref.year:
                pub_parts.append(ref.year)
            if pub_parts:
                parts.append(": ".join([pub_parts[0]] + [", ".join(pub_parts[1:])]) if len(pub_parts) > 1 else pub_parts[0])

        elif ref.type in (ReferenceType.THESIS, ReferenceType.DISSERTATION):
            # 学位论文
            degree = "PhD diss." if ref.type == ReferenceType.DISSERTATION else "Master's thesis"
            parts.append(degree + ",")
            if ref.university:
                parts.append(f"{ref.university},")
            if ref.year:
                parts.append(f"{ref.year}.")

        elif ref.type == ReferenceType.WEB_PAGE:
            # 网页
            if ref.publisher:
                parts.append(f"{ref.publisher}.")
            if ref.pub_date or ref.year:
                parts.append(f"{ref.pub_date or ref.year}.")
            if ref.url:
                parts.append(ref.url + ".")

        elif ref.type == ReferenceType.NEWSPAPER:
            # 报纸
            if ref.newspaper_name:
                parts.append(f"*{ref.newspaper_name},*")
            if ref.pub_date or ref.year:
                parts.append(f"{ref.pub_date or ref.year}.")

        else:
            if ref.publisher:
                parts.append(f"{ref.publisher},")
            if ref.year:
                parts.append(f"{ref.year}.")

        return " ".join(parts)

    @staticmethod
    def format_note(ref: Reference, note_num: int = 1) -> str:
        """格式化脚注/尾注。

        Chicago 注释制使用脚注或尾注。

        Args:
            ref: 参考文献数据
            note_num: 注释编号

        Returns:
            注释字符串
        """
        # 脚注格式与参考文献列表类似，但作者名为"名在前"
        parts: List[str] = []

        if ref.authors:
            first = ref.authors[0]
            if first.is_corporate:
                parts.append(first.family)
            elif first.is_chinese:
                parts.append(first.full_name)
            else:
                # 脚注：First Last
                name_parts = [p for p in [first.given, first.middle, first.family] if p]
                parts.append(" ".join(name_parts))
            # 其余作者
            if len(ref.authors) > 1:
                rest = ref.authors[1:]
                if len(rest) <= 2:
                    for a in rest:
                        if a.is_corporate:
                            parts.append(a.family)
                        elif a.is_chinese:
                            parts.append(a.full_name)
                        else:
                            name_parts = [p for p in [a.given, a.middle, a.family] if p]
                            parts.append(" ".join(name_parts))
                else:
                    parts.append("et al.")

        if ref.title:
            if ref.type in (ReferenceType.JOURNAL, ReferenceType.CONFERENCE,
                            ReferenceType.NEWSPAPER, ReferenceType.BOOK_CHAPTER,
                            ReferenceType.WEB_PAGE):
                parts.append(f'"{ref.title},"')
            else:
                parts.append(f"*{ref.title}*,")

        if ref.type == ReferenceType.JOURNAL:
            if ref.journal:
                parts.append(f"*{ref.journal}*")
            vol_info = ref.volume or ""
            if ref.issue:
                vol_info += f", no. {ref.issue}"
            if ref.year:
                vol_info += f" ({ref.year})"
            if vol_info:
                parts.append(vol_info)
            if ref.pages:
                parts.append(f": {format_pages_chicago(ref.pages)}")

        elif ref.type in (ReferenceType.BOOK,):
            pub_parts = []
            if ref.city:
                pub_parts.append(ref.city)
            if ref.publisher:
                pub_parts.append(ref.publisher)
            if ref.year:
                pub_parts.append(ref.year)
            if pub_parts:
                parts.append(": ".join([pub_parts[0]] + [", ".join(pub_parts[1:])]) if len(pub_parts) > 1 else pub_parts[0])

        return f'{note_num}. {" ".join(parts)}.'

    @staticmethod
    def format_in_text(ref: Reference) -> str:
        """格式化正文引用（作者-日期制）。

        Chicago 作者-日期制使用 (Author Year, pages) 格式。

        Args:
            ref: 参考文献数据

        Returns:
            正文引用字符串
        """
        if not ref.authors:
            if ref.title:
                short = ref.title[:30]
                return f"({short} {ref.year})" if ref.year else f"({short})"
            return ""

        if len(ref.authors) == 1:
            author = ref.authors[0]
            name = author.family if not author.is_chinese else author.full_name
        elif len(ref.authors) <= 3:
            names = []
            for a in ref.authors:
                n = a.family if not a.is_chinese else a.full_name
                names.append(n)
            name = ", ".join(names[:-1]) + ", and " + names[-1]
        else:
            first = ref.authors[0]
            name = first.family if not first.is_chinese else first.full_name
            name += " et al."

        year = ref.year or "n.d."
        if ref.pages:
            page_str = format_pages_chicago(ref.pages).split("-")[0]
            return f"({name} {year}, {page_str})"
        return f"({name} {year})"


# ===== IEEE 格式化器 =====


class IEEEFormatter:
    """IEEE 引用格式化器。

    实现电气电子工程师学会（IEEE）引用格式。
    """

    @staticmethod
    def format_bibliography(ref: Reference, number: int = 1) -> str:
        """格式化参考文献列表条目。

        Args:
            ref: 参考文献数据
            number: 引用编号

        Returns:
            格式化后的参考文献字符串
        """
        parts: List[str] = [f"[{number}]"]

        # 作者
        authors_str = format_authors_ieee(ref.authors)
        if authors_str:
            parts.append(authors_str + ",")

        # 标题
        if ref.title:
            if ref.type in (ReferenceType.BOOK, ReferenceType.BOOK_CHAPTER,
                            ReferenceType.CONFERENCE):
                parts.append(f'*{ref.title},*')
            else:
                parts.append(f'"{ref.title},"')

        # 根据类型添加不同字段
        if ref.type == ReferenceType.JOURNAL:
            # 期刊：*Journal Name*, vol. X, no. Y, pp. xxx-xxx, Month Year.
            if ref.journal:
                parts.append(f"*{ref.journal},*")
            if ref.volume:
                parts.append(f"vol. {ref.volume},")
            if ref.issue:
                parts.append(f"no. {ref.issue},")
            if ref.pages:
                parts.append(f"{format_pages_ieee(ref.pages)},")
            if ref.year:
                parts.append(f"{ref.year}.")

        elif ref.type == ReferenceType.CONFERENCE:
            # 会议论文：in Proc. Conf. Name, City, Year, pp. xxx-xxx.
            if ref.conference_name:
                conf_name = ref.conference_name
                if not conf_name.lower().startswith("proc"):
                    conf_name = f"Proc. {conf_name}"
                parts.append(f"in {conf_name},")
            if ref.conference_location:
                parts.append(f"{ref.conference_location},")
            if ref.year:
                parts.append(f"{ref.year},")
            if ref.pages:
                parts.append(f"{format_pages_ieee(ref.pages)}.")

        elif ref.type in (ReferenceType.BOOK,):
            # 图书：City: Publisher, Year.
            if ref.city:
                parts.append(f"{ref.city}:")
            if ref.publisher:
                parts.append(f"{ref.publisher},")
            if ref.year:
                parts.append(f"{ref.year}.")

        elif ref.type == ReferenceType.BOOK_CHAPTER:
            # 图书章节：in Book, Ed. Editor. City: Publisher, Year, pp. xxx-xxx.
            if ref.book_title:
                parts.append(f"in *{ref.book_title},*")
            if ref.editors:
                editors_str = format_authors_ieee(ref.editors)
                parts.append(f"Ed. {editors_str}.")
            if ref.city:
                parts.append(f"{ref.city}:")
            if ref.publisher:
                parts.append(f"{ref.publisher},")
            if ref.year:
                parts.append(f"{ref.year},")
            if ref.pages:
                parts.append(f"{format_pages_ieee(ref.pages)}.")

        elif ref.type in (ReferenceType.THESIS, ReferenceType.DISSERTATION):
            # 学位论文
            degree = "Ph.D. dissertation" if ref.type == ReferenceType.DISSERTATION else "M.S. thesis"
            parts.append(degree + ",")
            if ref.university:
                parts.append(f"{ref.university},")
            if ref.city:
                parts.append(f"{ref.city},")
            if ref.year:
                parts.append(f"{ref.year}.")

        elif ref.type == ReferenceType.WEB_PAGE:
            # 网页
            if ref.publisher:
                parts.append(f"{ref.publisher}.")
            if ref.url:
                parts.append(f"[Online]. Available: {ref.url}")
            if ref.access_date:
                parts.append(f"(accessed {ref.access_date}).")

        elif ref.type == ReferenceType.TECH_REPORT:
            # 技术报告
            if ref.city:
                parts.append(f"{ref.city}:")
            if ref.publisher:
                parts.append(f"{ref.publisher},")
            if ref.year:
                parts.append(f"{ref.year}.")

        elif ref.type == ReferenceType.PATENT:
            # 专利
            if ref.patent_number:
                parts.append(f"{ref.patent_number},")
            if ref.patent_country:
                parts.append(f"{ref.patent_country},")
            if ref.year:
                parts.append(f"{ref.year}.")

        elif ref.type == ReferenceType.STANDARD:
            # 标准
            if ref.standard_number:
                parts.append(f"{ref.standard_number},")
            if ref.year:
                parts.append(f"{ref.year}.")

        else:
            if ref.publisher:
                parts.append(f"{ref.publisher},")
            if ref.year:
                parts.append(f"{ref.year}.")

        return " ".join(parts)

    @staticmethod
    def format_in_text(ref: Reference, number: int = 1) -> str:
        """格式化正文引用。

        IEEE 使用方括号编号引用：[1] 或 [1, p. 512]。

        Args:
            ref: 参考文献数据
            number: 引用编号

        Returns:
            正文引用字符串
        """
        if ref.pages:
            page = format_pages_ieee(ref.pages).replace("pp. ", "").replace("p. ", "").split("-")[0]
            return f"[{number}, p. {page}]"
        return f"[{number}]"


# ===== 引用解析器 =====


class CitationParser:
    """引用解析器。

    从原始引用字符串解析为结构化 Reference 对象。
    支持多种格式的自动识别与解析。
    """

    # DOI 正则
    DOI_PATTERN = re.compile(r"10\.\d{4,}/[^\s]+", re.IGNORECASE)
    # URL 正则
    URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)
    # 年份正则
    YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")
    # 页码正则
    PAGES_PATTERN = re.compile(r"(?:pp?\.?\s*)?(\d+)\s*[-–—]\s*(\d+)")
    # GB/T 7714 类型标识
    GBT_TYPE_PATTERN = re.compile(r"\[([A-Z]+(?:/[A-Z]+)?)\]")

    @classmethod
    def parse(cls, raw: str, style: Optional[CitationStyle] = None) -> Reference:
        """解析引用字符串。

        Args:
            raw: 原始引用字符串
            style: 指定格式（若为 None 则自动识别）

        Returns:
            Reference 对象

        Raises:
            ParseError: 解析失败
        """
        if not raw or not raw.strip():
            raise ParseError("引用字符串为空")

        raw = raw.strip()
        ref = Reference(raw=raw)

        # 自动识别格式
        if style is None:
            style = cls.detect_style(raw)

        # 提取 DOI
        doi_match = cls.DOI_PATTERN.search(raw)
        if doi_match:
            ref.doi = doi_match.group(0).rstrip(".")

        # 提取 URL
        url_match = cls.URL_PATTERN.search(raw)
        if url_match:
            ref.url = url_match.group(0).rstrip(".")

        # 提取年份
        year_match = cls.YEAR_PATTERN.search(raw)
        if year_match:
            ref.year = year_match.group(0)

        # 提取页码
        pages_match = cls.PAGES_PATTERN.search(raw)
        if pages_match:
            ref.pages = f"{pages_match.group(1)}-{pages_match.group(2)}"

        # 根据格式解析
        if style == CitationStyle.GB_T_7714:
            cls._parse_gbt(raw, ref)
        elif style == CitationStyle.APA:
            cls._parse_apa(raw, ref)
        elif style == CitationStyle.MLA:
            cls._parse_mla(raw, ref)
        elif style == CitationStyle.CHICAGO:
            cls._parse_chicago(raw, ref)
        elif style == CitationStyle.IEEE:
            cls._parse_ieee(raw, ref)

        return ref

    @classmethod
    def detect_style(cls, raw: str) -> CitationStyle:
        """自动识别引用格式。

        Args:
            raw: 原始引用字符串

        Returns:
            识别到的引用格式
        """
        # IEEE: 以 [数字] 开头
        if re.match(r"^\[\d+\]", raw):
            return CitationStyle.IEEE

        # GB/T 7714: 包含 [J]、[M]、[C] 等类型标识
        if cls.GBT_TYPE_PATTERN.search(raw):
            return CitationStyle.GB_T_7714

        # APA: 包含 (年份). 格式
        if re.search(r"\(\d{4}\)\.", raw) or re.search(r"\(n\.d\.\)\.", raw):
            return CitationStyle.APA

        # MLA: 包含 "标题." 格式
        if re.search(r'"[^"]+"\.', raw):
            return CitationStyle.MLA

        # Chicago: 默认
        return CitationStyle.CHICAGO

    @classmethod
    def _parse_gbt(cls, raw: str, ref: Reference) -> None:
        """解析 GB/T 7714 格式。"""
        # 提取类型标识
        type_match = cls.GBT_TYPE_PATTERN.search(raw)
        if type_match:
            type_code = type_match.group(1)
            type_map = {
                "J": ReferenceType.JOURNAL,
                "C": ReferenceType.CONFERENCE,
                "M": ReferenceType.BOOK,
                "D": ReferenceType.THESIS,
                "R": ReferenceType.TECH_REPORT,
                "P": ReferenceType.PATENT,
                "S": ReferenceType.STANDARD,
                "N": ReferenceType.NEWSPAPER,
                "EB/OL": ReferenceType.WEB_PAGE,
                "Z": ReferenceType.OTHER,
            }
            ref.type = type_map.get(type_code, ReferenceType.OTHER)

        # 提取作者（第一个句点前）
        parts = raw.split(".")
        if parts:
            author_str = parts[0].strip()
            if author_str:
                # 处理"等"
                if "等" in author_str:
                    author_str = author_str.replace(", 等", "").replace("等", "")
                # 分割作者
                author_list = re.split(r"[,，]", author_str)
                ref.authors = [Author.parse(a.strip()) for a in author_list if a.strip()]

        # 提取标题（类型标识前的内容）
        if type_match:
            title_end = type_match.start()
            title_part = raw[:title_end].strip()
            # 去除作者部分
            if parts and ref.authors:
                title_part = title_part[len(parts[0]):].lstrip(". ").strip()
            ref.title = title_part

    @classmethod
    def _parse_apa(cls, raw: str, ref: Reference) -> None:
        """解析 APA 格式。"""
        # APA: Author, A. A., & Author, B. B. (Year). Title. Journal, vol(issue), pages.
        # 提取作者（年份括号前）
        year_paren = re.search(r"\((\d{4}|n\.d\.)\)", raw)
        if year_paren:
            author_str = raw[: year_paren.start()].strip().rstrip(",").strip()
            if author_str:
                # 分割作者
                author_parts = re.split(r",\s*&\s*|,\s+|\s+&\s+", author_str)
                ref.authors = [Author.parse(a.strip()) for a in author_parts if a.strip()]

        # 提取标题（年份后到下一个句点）
        if year_paren:
            after_year = raw[year_paren.end():].lstrip(". ").strip()
            title_match = re.match(r"(.+?)\.(?:\s|$)", after_year)
            if title_match:
                ref.title = title_match.group(1).strip().strip("*")

    @classmethod
    def _parse_mla(cls, raw: str, ref: Reference) -> None:
        """解析 MLA 格式。"""
        # MLA: Author. "Title." Journal, vol, no, Year, pp.
        parts = raw.split(".")
        if parts:
            # 第一部分为作者
            author_str = parts[0].strip()
            if author_str and not author_str.startswith('"'):
                if "et al" in author_str:
                    author_str = author_str.replace(", et al", "").replace("et al", "")
                author_list = re.split(r",\s+and\s+|,\s+", author_str)
                ref.authors = [Author.parse(a.strip()) for a in author_list if a.strip()]

            # 查找标题（引号内）
            title_match = re.search(r'"([^"]+)"', raw)
            if title_match:
                ref.title = title_match.group(1)

    @classmethod
    def _parse_chicago(cls, raw: str, ref: Reference) -> None:
        """解析 Chicago 格式。"""
        # Chicago: Author. Title. Journal vol, no. Y (Year): pages.
        parts = raw.split(".")
        if parts:
            author_str = parts[0].strip()
            if author_str:
                author_list = re.split(r",\s+and\s+|,\s+", author_str)
                ref.authors = [Author.parse(a.strip()) for a in author_list if a.strip()]

            # 标题
            if len(parts) > 1:
                title_candidate = parts[1].strip().strip("*").strip('"')
                if title_candidate:
                    ref.title = title_candidate

    @classmethod
    def _parse_ieee(cls, raw: str, ref: Reference) -> None:
        """解析 IEEE 格式。"""
        # IEEE: [N] A. Author, "Title," Journal, vol. X, no. Y, pp. xxx-xxx, Year.
        # 去除编号
        raw_clean = re.sub(r"^\[\d+\]\s*", "", raw)

        # 提取标题（引号内）
        title_match = re.search(r'"([^"]+)"', raw_clean)
        if title_match:
            ref.title = title_match.group(1)

        # 提取作者（标题前）
        if title_match:
            author_str = raw_clean[: title_match.start()].strip().rstrip(",")
            if author_str:
                author_list = re.split(r",\s+and\s+|,\s+|\s+and\s+", author_str)
                ref.authors = [Author.parse(a.strip()) for a in author_list if a.strip()]


# ===== 引用校验器 =====


class CitationValidator:
    """引用校验器。

    校验参考文献数据的完整性与规范性。
    """

    # 各类型必填字段
    REQUIRED_FIELDS: Dict[ReferenceType, List[str]] = {
        ReferenceType.JOURNAL: ["authors", "title", "year", "journal"],
        ReferenceType.CONFERENCE: ["authors", "title", "year", "conference_name"],
        ReferenceType.BOOK: ["authors", "title", "year", "publisher"],
        ReferenceType.BOOK_CHAPTER: ["authors", "title", "year", "book_title", "publisher"],
        ReferenceType.THESIS: ["authors", "title", "year", "university"],
        ReferenceType.DISSERTATION: ["authors", "title", "year", "university"],
        ReferenceType.WEB_PAGE: ["title", "url"],
        ReferenceType.TECH_REPORT: ["authors", "title", "year", "publisher"],
        ReferenceType.PATENT: ["title", "patent_number"],
        ReferenceType.STANDARD: ["title", "standard_number"],
        ReferenceType.NEWSPAPER: ["authors", "title", "newspaper_name"],
    }

    # DOI 格式正则
    DOI_FORMAT = re.compile(r"^10\.\d{4,}/.+$")

    # URL 格式正则
    URL_FORMAT = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)

    @classmethod
    def validate(cls, ref: Reference) -> ValidationResult:
        """校验参考文献。

        Args:
            ref: 参考文献数据

        Returns:
            校验结果
        """
        result = ValidationResult()

        # 检查必填字段
        required = cls.REQUIRED_FIELDS.get(ref.type, ["title"])
        for field_name in required:
            value = getattr(ref, field_name, None)
            if not value or (isinstance(value, str) and not value.strip()) or (isinstance(value, list) and len(value) == 0):
                result.add_missing(field_name)
                result.add_error(f"缺少必填字段: {field_name}")

        # 校验 DOI 格式
        if ref.doi:
            if not cls.DOI_FORMAT.match(ref.doi):
                result.add_warning(f"DOI 格式不规范: {ref.doi}")

        # 校验 URL 格式
        if ref.url:
            if not cls.URL_FORMAT.match(ref.url):
                result.add_warning(f"URL 格式不规范: {ref.url}")

        # 校验年份
        if ref.year:
            if not ref.year.isdigit() or len(ref.year) != 4:
                result.add_warning(f"年份格式不规范: {ref.year}")
            else:
                year_int = int(ref.year)
                if year_int < 1900 or year_int > 2100:
                    result.add_warning(f"年份超出合理范围: {ref.year}")

        # 校验页码
        if ref.pages:
            if not re.match(r"^\d+\s*[-–—]\s*\d+$|^\d+$", ref.pages):
                result.add_warning(f"页码格式不规范: {ref.pages}")

        # 校验作者
        if ref.authors:
            for i, author in enumerate(ref.authors):
                if not author.family and not author.is_corporate:
                    result.add_warning(f"第 {i+1} 位作者缺少姓氏")

        # 网页资源应有访问日期
        if ref.type == ReferenceType.WEB_PAGE and not ref.access_date:
            result.add_warning("网页资源建议标注访问日期")

        # 在线资源应有 URL
        if ref.is_online_resource and not ref.url:
            result.add_warning("在线资源应有 URL")

        return result

    @classmethod
    def validate_batch(cls, refs: List[Reference]) -> List[ValidationResult]:
        """批量校验参考文献。

        Args:
            refs: 参考文献列表

        Returns:
            校验结果列表
        """
        return [cls.validate(ref) for ref in refs]


# ===== 主格式化器 =====


class CitationFormatter:
    """引用格式化器主类。

    提供统一的引用格式化接口，支持多种引用格式与文献类型。
    采用单例模式确保全局一致性。

    典型用法：
        formatter = CitationFormatter()
        # 格式化单条参考文献
        bib = formatter.format_bibliography(ref, CitationStyle.APA)
        in_text = formatter.format_in_text(ref, CitationStyle.APA)
        # 批量格式化
        bibs = formatter.format_bibliography_batch(refs, CitationStyle.GB_T_7714, sort=True)
        # 去重
        unique_refs = formatter.deduplicate(refs)
        # 解析
        ref = formatter.parse("[1] 张三. 深度学习[J]. 计算机学报, 2024, 47(3): 512-528.")
    """

    _instance: Optional["CitationFormatter"] = None
    _lock = threading.RLock()

    def __new__(cls) -> "CitationFormatter":
        """单例模式创建实例。"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """初始化格式化器。"""
        if self._initialized:
            return
        with self._lock:
            if self._initialized:
                return
            # 格式化器映射
            self._formatters: Dict[CitationStyle, Any] = {
                CitationStyle.GB_T_7714: GBT7714Formatter(),
                CitationStyle.APA: APAFormatter(),
                CitationStyle.MLA: MLAFormatter(),
                CitationStyle.CHICAGO: ChicagoFormatter(),
                CitationStyle.IEEE: IEEEFormatter(),
            }
            # 引用编号映射（用于顺序编码制）
            self._citation_numbers: Dict[str, int] = {}
            self._next_number: int = 1
            self._initialized = True
            _logger.debug("CitationFormatter 初始化完成")

    def reset_numbering(self) -> None:
        """重置引用编号（用于顺序编码制）。"""
        with self._lock:
            self._citation_numbers.clear()
            self._next_number = 1

    def get_citation_number(self, ref: Reference) -> int:
        """获取或分配引用编号（用于顺序编码制）。

        Args:
            ref: 参考文献数据

        Returns:
            引用编号
        """
        fingerprint = ref.fingerprint()
        with self._lock:
            if fingerprint not in self._citation_numbers:
                self._citation_numbers[fingerprint] = self._next_number
                self._next_number += 1
            return self._citation_numbers[fingerprint]

    def format_bibliography(
        self,
        ref: Reference,
        style: CitationStyle = CitationStyle.GB_T_7714,
    ) -> str:
        """格式化参考文献列表条目。

        Args:
            ref: 参考文献数据
            style: 引用格式

        Returns:
            格式化后的参考文献字符串

        Raises:
            CitationError: 格式化失败
        """
        try:
            formatter = self._formatters.get(style)
            if formatter is None:
                raise CitationError(f"不支持的引用格式: {style}")

            if style == CitationStyle.IEEE:
                # IEEE 需要编号
                number = self.get_citation_number(ref)
                return formatter.format_bibliography(ref, number=number)
            else:
                return formatter.format_bibliography(ref)
        except CitationError:
            raise
        except Exception as e:
            _logger.error(f"格式化参考文献失败: {e}")
            raise CitationError(f"格式化失败: {e}") from e

    def format_bibliography_batch(
        self,
        refs: List[Reference],
        style: CitationStyle = CitationStyle.GB_T_7714,
        sort: bool = False,
        sort_key: SortKey = SortKey.AUTHOR,
        deduplicate: bool = False,
    ) -> List[str]:
        """批量格式化参考文献列表。

        Args:
            refs: 参考文献列表
            style: 引用格式
            sort: 是否排序
            sort_key: 排序键
            deduplicate: 是否去重

        Returns:
            格式化后的参考文献字符串列表
        """
        # 去重
        if deduplicate:
            refs = self.deduplicate(refs)

        # 排序
        if sort:
            refs = self.sort_references(refs, sort_key)

        # 重置编号（IEEE 顺序编码）
        if style == CitationStyle.IEEE:
            self.reset_numbering()

        # 格式化
        results: List[str] = []
        for ref in refs:
            try:
                formatted = self.format_bibliography(ref, style)
                results.append(formatted)
            except CitationError as e:
                _logger.warning(f"格式化参考文献失败: {e}")
                results.append(f"[格式化错误] {ref.title or ref.raw}")

        return results

    def format_in_text(
        self,
        ref: Reference,
        style: CitationStyle = CitationStyle.GB_T_7714,
        mode: str = "default",
    ) -> str:
        """格式化正文引用。

        Args:
            ref: 参考文献数据
            style: 引用格式
            mode: 引用模式（不同格式有不同选项）

        Returns:
            正文引用字符串
        """
        try:
            formatter = self._formatters.get(style)
            if formatter is None:
                raise CitationError(f"不支持的引用格式: {style}")

            if style == CitationStyle.GB_T_7714:
                actual_mode = mode if mode != "default" else "sequential"
                return formatter.format_in_text(ref, mode=actual_mode)
            elif style == CitationStyle.APA:
                actual_mode = mode if mode != "default" else "parenthetical"
                return formatter.format_in_text(ref, mode=actual_mode)
            elif style == CitationStyle.IEEE:
                number = self.get_citation_number(ref)
                return formatter.format_in_text(ref, number=number)
            else:
                return formatter.format_in_text(ref)
        except CitationError:
            raise
        except Exception as e:
            _logger.error(f"格式化正文引用失败: {e}")
            raise CitationError(f"格式化失败: {e}") from e

    def format_in_text_batch(
        self,
        refs: List[Reference],
        style: CitationStyle = CitationStyle.GB_T_7714,
        mode: str = "default",
    ) -> List[str]:
        """批量格式化正文引用。

        Args:
            refs: 参考文献列表
            style: 引用格式
            mode: 引用模式

        Returns:
            正文引用字符串列表
        """
        results: List[str] = []
        for ref in refs:
            try:
                formatted = self.format_in_text(ref, style, mode)
                results.append(formatted)
            except CitationError as e:
                _logger.warning(f"格式化正文引用失败: {e}")
                results.append("[?]")
        return results

    def sort_references(
        self,
        refs: List[Reference],
        key: SortKey = SortKey.AUTHOR,
        reverse: bool = False,
    ) -> List[Reference]:
        """排序参考文献。

        Args:
            refs: 参考文献列表
            key: 排序键
            reverse: 是否降序

        Returns:
            排序后的参考文献列表
        """
        def sort_key_func(ref: Reference) -> Tuple[str, ...]:
            """生成排序键。"""
            if key == SortKey.AUTHOR:
                first = ref.first_author
                if first:
                    return (first.family.lower(), ref.year, ref.title.lower())
                return ("zzz", ref.year, ref.title.lower())
            elif key == SortKey.YEAR:
                return (ref.year or "0000", ref.title.lower())
            elif key == SortKey.TITLE:
                return (ref.title.lower(), ref.year)
            elif key == SortKey.TYPE:
                return (ref.type.value, ref.title.lower())
            elif key == SortKey.DOI:
                return (ref.doi.lower() if ref.doi else "zzz", ref.title.lower())
            return (ref.title.lower(),)

        return sorted(refs, key=sort_key_func, reverse=reverse)

    def deduplicate(self, refs: List[Reference]) -> List[Reference]:
        """参考文献去重。

        基于 DOI（若有）或标题+作者+年份的指纹去重。

        Args:
            refs: 参考文献列表

        Returns:
            去重后的参考文献列表
        """
        seen: Dict[str, Reference] = {}
        duplicates: List[Reference] = []

        for ref in refs:
            fingerprint = ref.fingerprint()
            if fingerprint in seen:
                duplicates.append(ref)
                _logger.debug(f"发现重复参考文献: {ref.title}")
            else:
                seen[fingerprint] = ref

        if duplicates:
            _logger.info(f"去重完成: 原始 {len(refs)} 条，重复 {len(duplicates)} 条，保留 {len(seen)} 条")

        return list(seen.values())

    def parse(self, raw: str, style: Optional[CitationStyle] = None) -> Reference:
        """解析引用字符串。

        Args:
            raw: 原始引用字符串
            style: 指定格式（若为 None 则自动识别）

        Returns:
            Reference 对象

        Raises:
            ParseError: 解析失败
        """
        return CitationParser.parse(raw, style)

    def parse_batch(
        self,
        raws: List[str],
        style: Optional[CitationStyle] = None,
    ) -> List[Reference]:
        """批量解析引用字符串。

        Args:
            raws: 原始引用字符串列表
            style: 指定格式

        Returns:
            Reference 对象列表
        """
        results: List[Reference] = []
        for raw in raws:
            try:
                ref = self.parse(raw, style)
                results.append(ref)
            except ParseError as e:
                _logger.warning(f"解析引用失败: {raw[:50]}... 错误: {e}")
        return results

    def validate(self, ref: Reference) -> ValidationResult:
        """校验参考文献。

        Args:
            ref: 参考文献数据

        Returns:
            校验结果
        """
        return CitationValidator.validate(ref)

    def validate_batch(self, refs: List[Reference]) -> List[ValidationResult]:
        """批量校验参考文献。

        Args:
            refs: 参考文献列表

        Returns:
            校验结果列表
        """
        return CitationValidator.validate_batch(refs)

    def get_stats(self, refs: List[Reference], style: Optional[CitationStyle] = None) -> FormatStats:
        """获取参考文献统计信息。

        Args:
            refs: 参考文献列表
            style: 引用格式（用于统计格式分布）

        Returns:
            统计信息
        """
        stats = FormatStats()
        stats.total = len(refs)

        for ref in refs:
            # 按类型统计
            type_key = ref.type.value
            stats.by_type[type_key] = stats.by_type.get(type_key, 0) + 1

            # 按格式统计
            if style:
                style_key = style.value
                stats.by_style[style_key] = stats.by_style.get(style_key, 0) + 1

            # DOI/URL 统计
            if ref.has_doi:
                stats.with_doi += 1
            if ref.has_url:
                stats.with_url += 1

            # 校验
            result = self.validate(ref)
            if not result.is_valid:
                stats.invalid += 1

        # 去重统计
        unique = self.deduplicate(refs)
        stats.duplicates = len(refs) - len(unique)

        return stats

    def format_bibliography_with_numbers(
        self,
        refs: List[Reference],
        style: CitationStyle = CitationStyle.GB_T_7714,
        sort: bool = True,
        deduplicate: bool = True,
    ) -> str:
        """格式化带编号的参考文献列表（完整文档）。

        Args:
            refs: 参考文献列表
            style: 引用格式
            sort: 是否排序
            deduplicate: 是否去重

        Returns:
            完整的参考文献列表字符串
        """
        # 去重
        if deduplicate:
            refs = self.deduplicate(refs)

        # 排序
        if sort:
            refs = self.sort_references(refs, SortKey.AUTHOR)

        # 重置编号
        self.reset_numbering()

        # 格式化
        lines: List[str] = []
        for ref in refs:
            try:
                formatted = self.format_bibliography(ref, style)
                lines.append(formatted)
            except CitationError as e:
                lines.append(f"[格式化错误] {ref.title or ref.raw}: {e}")

        return "\n".join(lines)

    def export_to_markdown(
        self,
        refs: List[Reference],
        style: CitationStyle = CitationStyle.GB_T_7714,
        title: str = "参考文献",
        sort: bool = True,
        deduplicate: bool = True,
    ) -> str:
        """导出为 Markdown 格式的参考文献列表。

        Args:
            refs: 参考文献列表
            style: 引用格式
            title: 标题
            sort: 是否排序
            deduplicate: 是否去重

        Returns:
            Markdown 格式的参考文献列表
        """
        lines: List[str] = [f"## {title}", ""]

        formatted_list = self.format_bibliography_with_numbers(
            refs, style, sort, deduplicate
        )

        if formatted_list:
            lines.append(formatted_list)
        else:
            lines.append("*（暂无参考文献）*")

        return "\n".join(lines)

    def export_to_html(
        self,
        refs: List[Reference],
        style: CitationStyle = CitationStyle.GB_T_7714,
        title: str = "参考文献",
        sort: bool = True,
        deduplicate: bool = True,
    ) -> str:
        """导出为 HTML 格式的参考文献列表。

        Args:
            refs: 参考文献列表
            style: 引用格式
            title: 标题
            sort: 是否排序
            deduplicate: 是否去重

        Returns:
            HTML 格式的参考文献列表
        """
        from html import escape as html_escape

        lines: List[str] = [
            '<div class="references">',
            f'<h2>{html_escape(title)}</h2>',
            '<ol class="reference-list">',
        ]

        # 去重与排序
        if deduplicate:
            refs = self.deduplicate(refs)
        if sort:
            refs = self.sort_references(refs, SortKey.AUTHOR)

        # 重置编号
        self.reset_numbering()

        for ref in refs:
            try:
                formatted = self.format_bibliography(ref, style)
                lines.append(f'<li class="reference-item">{html_escape(formatted)}</li>')
            except CitationError as e:
                lines.append(f'<li class="reference-item error">[格式化错误] {html_escape(ref.title or ref.raw)}</li>')

        lines.extend(["</ol>", "</div>"])
        return "\n".join(lines)

    def export_to_bibtex(self, ref: Reference) -> str:
        """导出为 BibTeX 格式。

        Args:
            ref: 参考文献数据

        Returns:
            BibTeX 格式字符串
        """
        # BibTeX 类型映射
        type_map = {
            ReferenceType.JOURNAL: "article",
            ReferenceType.CONFERENCE: "inproceedings",
            ReferenceType.BOOK: "book",
            ReferenceType.BOOK_CHAPTER: "incollection",
            ReferenceType.THESIS: "mastersthesis",
            ReferenceType.DISSERTATION: "phdthesis",
            ReferenceType.WEB_PAGE: "misc",
            ReferenceType.TECH_REPORT: "techreport",
            ReferenceType.PATENT: "misc",
            ReferenceType.STANDARD: "misc",
            ReferenceType.NEWSPAPER: "article",
        }

        bib_type = type_map.get(ref.type, "misc")

        # 生成引用键
        first_author = ref.first_author
        if first_author:
            key_author = first_author.family.lower().replace(" ", "")
        else:
            key_author = "anon"
        key_year = ref.year or "nd"
        key_title = ref.title.split()[0].lower() if ref.title else "untitled"
        citation_key = f"{key_author}{key_year}{key_title}"

        lines: List[str] = [f"@{bib_type}{{{citation_key},"]

        # 作者
        if ref.authors:
            author_str = " and ".join(a.full_name for a in ref.authors)
            lines.append(f"  author = {{{author_str}}},")

        # 标题
        if ref.title:
            lines.append(f"  title = {{{ref.title}}},")

        # 年份
        if ref.year:
            lines.append(f"  year = {{{ref.year}}},")

        # 期刊
        if ref.journal:
            lines.append(f"  journal = {{{ref.journal}}},")

        # 卷
        if ref.volume:
            lines.append(f"  volume = {{{ref.volume}}},")

        # 期
        if ref.issue:
            lines.append(f"  number = {{{ref.issue}}},")

        # 页码
        if ref.pages:
            lines.append(f"  pages = {{{ref.pages}}},")

        # 出版社
        if ref.publisher:
            lines.append(f"  publisher = {{{ref.publisher}}},")

        # 地址
        if ref.city:
            lines.append(f"  address = {{{ref.city}}},")

        # DOI
        if ref.doi:
            lines.append(f"  doi = {{{ref.doi}}},")

        # URL
        if ref.url:
            lines.append(f"  url = {{{ref.url}}},")

        # 书名
        if ref.book_title:
            lines.append(f"  booktitle = {{{ref.book_title}}},")

        # 大学
        if ref.university:
            lines.append(f"  school = {{{ref.university}}},")

        # 会议名
        if ref.conference_name:
            lines.append(f"  booktitle = {{{ref.conference_name}}},")

        # 最后一行去掉逗号
        if lines[-1].endswith(","):
            lines[-1] = lines[-1][:-1]

        lines.append("}")
        return "\n".join(lines)

    def export_to_bibtex_batch(self, refs: List[Reference]) -> str:
        """批量导出为 BibTeX 格式。

        Args:
            refs: 参考文献列表

        Returns:
            BibTeX 格式字符串
        """
        entries: List[str] = []
        for ref in refs:
            try:
                entry = self.export_to_bibtex(ref)
                entries.append(entry)
            except Exception as e:
                _logger.warning(f"导出 BibTeX 失败: {e}")
        return "\n\n".join(entries)

    def convert_style(
        self,
        ref: Reference,
        from_style: CitationStyle,
        to_style: CitationStyle,
    ) -> str:
        """转换引用格式。

        将参考文献从一种格式转换为另一种格式。

        Args:
            ref: 参考文献数据
            from_style: 原格式（仅用于参考）
            to_style: 目标格式

        Returns:
            目标格式的参考文献字符串
        """
        return self.format_bibliography(ref, to_style)

    def convert_style_batch(
        self,
        refs: List[Reference],
        to_style: CitationStyle,
        sort: bool = False,
        deduplicate: bool = False,
    ) -> List[str]:
        """批量转换引用格式。

        Args:
            refs: 参考文献列表
            to_style: 目标格式
            sort: 是否排序
            deduplicate: 是否去重

        Returns:
            目标格式的参考文献字符串列表
        """
        return self.format_bibliography_batch(refs, to_style, sort=sort, deduplicate=deduplicate)

    def get_supported_styles(self) -> List[CitationStyle]:
        """获取支持的引用格式列表。"""
        return list(CitationStyle)

    def get_supported_types(self) -> List[ReferenceType]:
        """获取支持的文献类型列表。"""
        return list(ReferenceType)

    def get_style_description(self, style: CitationStyle) -> str:
        """获取引用格式的描述信息。

        Args:
            style: 引用格式

        Returns:
            格式描述字符串
        """
        descriptions = {
            CitationStyle.GB_T_7714: "GB/T 7714-2015 中国国家标准参考文献著录规则",
            CitationStyle.APA: "APA 第 7 版（美国心理学会）引用格式",
            CitationStyle.MLA: "MLA 第 9 版（现代语言协会）引用格式",
            CitationStyle.CHICAGO: "芝加哥格式第 17 版（注释与参考文献制）",
            CitationStyle.IEEE: "IEEE（电气电子工程师学会）引用格式",
        }
        return descriptions.get(style, "未知格式")

    def get_type_description(self, ref_type: ReferenceType) -> str:
        """获取文献类型的描述信息。

        Args:
            ref_type: 文献类型

        Returns:
            类型描述字符串
        """
        descriptions = {
            ReferenceType.JOURNAL: "期刊论文 [J]",
            ReferenceType.CONFERENCE: "会议论文 [C]",
            ReferenceType.BOOK: "图书专著 [M]",
            ReferenceType.BOOK_CHAPTER: "图书章节 [M]",
            ReferenceType.THESIS: "硕士学位论文 [D]",
            ReferenceType.DISSERTATION: "博士学位论文 [D]",
            ReferenceType.WEB_PAGE: "网页资源 [EB/OL]",
            ReferenceType.TECH_REPORT: "技术报告 [R]",
            ReferenceType.PATENT: "专利 [P]",
            ReferenceType.STANDARD: "标准 [S]",
            ReferenceType.NEWSPAPER: "报纸文章 [N]",
            ReferenceType.SOFTWARE: "软件 [CP]",
            ReferenceType.DATASET: "数据集 [DS]",
            ReferenceType.OTHER: "其他 [Z]",
        }
        return descriptions.get(ref_type, "未知类型")


# ===== 模块级便捷函数 =====


def get_citation_formatter() -> CitationFormatter:
    """获取 CitationFormatter 单例实例。

    Returns:
        CitationFormatter 实例
    """
    return CitationFormatter()


def format_reference(
    ref: Reference,
    style: CitationStyle = CitationStyle.GB_T_7714,
) -> str:
    """格式化参考文献（便捷函数）。

    Args:
        ref: 参考文献数据
        style: 引用格式

    Returns:
        格式化后的参考文献字符串
    """
    return get_citation_formatter().format_bibliography(ref, style)


def format_in_text_citation(
    ref: Reference,
    style: CitationStyle = CitationStyle.GB_T_7714,
    mode: str = "default",
) -> str:
    """格式化正文引用（便捷函数）。

    Args:
        ref: 参考文献数据
        style: 引用格式
        mode: 引用模式

    Returns:
        正文引用字符串
    """
    return get_citation_formatter().format_in_text(ref, style, mode)


def format_references_batch(
    refs: List[Reference],
    style: CitationStyle = CitationStyle.GB_T_7714,
    sort: bool = False,
    deduplicate: bool = False,
) -> List[str]:
    """批量格式化参考文献（便捷函数）。

    Args:
        refs: 参考文献列表
        style: 引用格式
        sort: 是否排序
        deduplicate: 是否去重

    Returns:
        格式化后的参考文献字符串列表
    """
    return get_citation_formatter().format_bibliography_batch(
        refs, style, sort=sort, deduplicate=deduplicate
    )


def parse_citation(raw: str, style: Optional[CitationStyle] = None) -> Reference:
    """解析引用字符串（便捷函数）。

    Args:
        raw: 原始引用字符串
        style: 指定格式

    Returns:
        Reference 对象
    """
    return get_citation_formatter().parse(raw, style)


def validate_reference(ref: Reference) -> ValidationResult:
    """校验参考文献（便捷函数）。

    Args:
        ref: 参考文献数据

    Returns:
        校验结果
    """
    return get_citation_formatter().validate(ref)


def deduplicate_references(refs: List[Reference]) -> List[Reference]:
    """参考文献去重（便捷函数）。

    Args:
        refs: 参考文献列表

    Returns:
        去重后的参考文献列表
    """
    return get_citation_formatter().deduplicate(refs)


def sort_references(
    refs: List[Reference],
    key: SortKey = SortKey.AUTHOR,
    reverse: bool = False,
) -> List[Reference]:
    """排序参考文献（便捷函数）。

    Args:
        refs: 参考文献列表
        key: 排序键
        reverse: 是否降序

    Returns:
        排序后的参考文献列表
    """
    return get_citation_formatter().sort_references(refs, key, reverse)


# ===== 自测函数 =====


def _run_self_test() -> None:
    """模块自测函数。

    创建示例参考文献并验证格式化功能。
    """
    formatter = CitationFormatter()

    # 创建示例参考文献
    refs: List[Reference] = [
        Reference(
            type=ReferenceType.JOURNAL,
            authors=[Author("张", "三"), Author("李", "四")],
            title="深度学习在自然语言处理中的应用研究",
            year="2024",
            journal="计算机学报",
            volume="47",
            issue="3",
            pages="512-528",
            doi="10.3724/SP.J.1016.2024.00512",
        ),
        Reference(
            type=ReferenceType.JOURNAL,
            authors=[Author("Smith", "John", "A."), Author("Jones", "Mary", "B.")],
            title="A Survey of Deep Learning Techniques",
            year="2023",
            journal="IEEE Transactions on Neural Networks",
            volume="34",
            issue="5",
            pages="2345-2367",
            doi="10.1109/TNN.2023.1234567",
        ),
        Reference(
            type=ReferenceType.BOOK,
            authors=[Author("王", "五")],
            title="机器学习导论",
            year="2022",
            publisher="清华大学出版社",
            city="北京",
            edition="第2版",
            isbn="978-7-302-12345-6",
        ),
        Reference(
            type=ReferenceType.CONFERENCE,
            authors=[Author("Brown", "David"), Author("Wilson", "Sarah")],
            title="Attention Is All You Need",
            year="2017",
            conference_name="Advances in Neural Information Processing Systems",
            conference_location="Long Beach, CA, USA",
            pages="5998-6008",
        ),
        Reference(
            type=ReferenceType.THESIS,
            authors=[Author("赵", "六")],
            title="基于深度学习的文本分类研究",
            year="2023",
            university="北京大学",
            degree="硕士",
        ),
        Reference(
            type=ReferenceType.WEB_PAGE,
            authors=[Author("OpenAI", is_corporate=True)],
            title="GPT-4 Technical Report",
            year="2024",
            url="https://openai.com/research/gpt-4",
            access_date="2024-06-15",
        ),
    ]

    print("=" * 80)
    print("CitationFormatter 自测")
    print("=" * 80)

    # 测试各种格式
    for style in CitationStyle:
        print(f"\n--- {formatter.get_style_description(style)} ---")
        formatter.reset_numbering()
        for ref in refs:
            try:
                bib = formatter.format_bibliography(ref, style)
                in_text = formatter.format_in_text(ref, style)
                print(f"\n[{ref.type_label_cn}] {ref.title[:40]}...")
                print(f"  参考文献: {bib}")
                print(f"  正文引用: {in_text}")
            except Exception as e:
                print(f"  错误: {e}")

    # 测试批量格式化
    print("\n--- 批量格式化（GB/T 7714，排序+去重）---")
    formatter.reset_numbering()
    bibs = formatter.format_bibliography_batch(
        refs, CitationStyle.GB_T_7714, sort=True, deduplicate=True
    )
    for i, bib in enumerate(bibs, 1):
        print(f"  {i}. {bib}")

    # 测试统计
    print("\n--- 统计信息 ---")
    stats = formatter.get_stats(refs, CitationStyle.GB_T_7714)
    print(f"  总数: {stats.total}")
    print(f"  类型分布: {stats.by_type}")
    print(f"  有 DOI: {stats.with_doi}")
    print(f"  有 URL: {stats.with_url}")
    print(f"  重复: {stats.duplicates}")
    print(f"  无效: {stats.invalid}")

    # 测试解析
    print("\n--- 引用解析 ---")
    raw = "张三, 李四. 深度学习在自然语言处理中的应用研究[J]. 计算机学报, 2024, 47(3): 512-528."
    try:
        parsed = formatter.parse(raw)
        print(f"  原始: {raw}")
        print(f"  类型: {parsed.type_label_cn}")
        print(f"  作者: {[a.full_name for a in parsed.authors]}")
        print(f"  标题: {parsed.title}")
        print(f"  年份: {parsed.year}")
        print(f"  页码: {parsed.pages}")
    except ParseError as e:
        print(f"  解析失败: {e}")

    # 测试 BibTeX 导出
    print("\n--- BibTeX 导出 ---")
    bibtex = formatter.export_to_bibtex(refs[0])
    print(bibtex)

    # 测试 Markdown 导出
    print("\n--- Markdown 导出 ---")
    md = formatter.export_to_markdown(refs, CitationStyle.GB_T_7714)
    print(md[:500] + "..." if len(md) > 500 else md)

    print("\n" + "=" * 80)
    print("自测完成")
    print("=" * 80)


if __name__ == "__main__":
    _run_self_test()
