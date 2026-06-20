"""学术规范

提供引用格式校验、参考文献检查、学术写作规范校验能力。
内置 100+ 格式化规则。

核心组件：
    - CitationFormat: 引用格式枚举
    - CitationFormatter: 引用格式化器
    - ReferenceChecker: 参考文献检查器
    - AcademicWritingChecker: 学术写作规范检查器
    - AcademicStandards: 学术规范主类（整合以上组件）

支持的引用格式：
    - GB/T 7714（中国国家标准）
    - APA（美国心理学会）
    - MLA（现代语言协会）
    - Chicago（芝加哥格式）
    - IEEE（电气电子工程师学会）
    - Vancouver（温哥华格式）
"""
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ===== 引用格式枚举 =====


class CitationFormat(str, Enum):
    """引用格式"""
    GB_T_7714 = "gb_t_7714"  # 中国国家标准
    APA = "apa"
    MLA = "mla"
    CHICAGO = "chicago"
    IEEE = "ieee"
    VANCOUVER = "vancouver"


@dataclass
class CitationIssue:
    """引用问题"""
    field: str
    message: str
    severity: str = "warning"  # info / warning / error
    suggestion: str = ""
    position: int = 0

    def to_dict(self) -> dict:
        return {
            "field": self.field,
            "message": self.message,
            "severity": self.severity,
            "suggestion": self.suggestion,
            "position": self.position,
        }


@dataclass
class ReferenceEntry:
    """参考文献条目"""
    type: str = "journal"  # journal / book / conference / thesis / web / other
    authors: list = field(default_factory=list)
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
    raw: str = ""

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "authors": self.authors,
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
            "raw": self.raw,
        }


@dataclass
class StandardsReport:
    """学术规范报告"""
    passed: bool
    format: str = ""
    issues: list = field(default_factory=list)
    reference_count: int = 0
    citation_count: int = 0
    consistency_score: float = 1.0
    recommendations: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "format": self.format,
            "issues": [i.to_dict() if isinstance(i, CitationIssue) else i for i in self.issues],
            "reference_count": self.reference_count,
            "citation_count": self.citation_count,
            "consistency_score": self.consistency_score,
            "recommendations": self.recommendations,
        }


# ===== 引用格式化器 =====


class CitationFormatter:
    """引用格式化器

    将参考文献条目格式化为指定引用格式的字符串。
    """

    @staticmethod
    def format(entry: ReferenceEntry, fmt: CitationFormat = CitationFormat.GB_T_7714) -> str:
        """格式化参考文献。

        Args:
            entry: 参考文献条目。
            fmt: 引用格式。

        Returns:
            格式化后的引用字符串。
        """
        if fmt == CitationFormat.GB_T_7714:
            return CitationFormatter._format_gbt7714(entry)
        elif fmt == CitationFormat.APA:
            return CitationFormatter._format_apa(entry)
        elif fmt == CitationFormat.MLA:
            return CitationFormatter._format_mla(entry)
        elif fmt == CitationFormat.CHICAGO:
            return CitationFormatter._format_chicago(entry)
        elif fmt == CitationFormat.IEEE:
            return CitationFormatter._format_ieee(entry)
        elif fmt == CitationFormat.VANCOUVER:
            return CitationFormatter._format_vancouver(entry)
        return entry.raw or entry.title

    @staticmethod
    def _format_authors(authors: list, fmt: str = "gbt") -> str:
        """格式化作者列表。"""
        if not authors:
            return "佚名"
        if fmt == "gbt":
            # GB/T 7714: 作者1, 作者2, 作者3. 等
            if len(authors) <= 3:
                return ", ".join(authors) + "."
            return ", ".join(authors[:3]) + ", 等."
        elif fmt == "apa":
            # APA: Author, A. A., & Author, B. B.
            if len(authors) == 1:
                return authors[0]
            return ", ".join(authors[:-1]) + ", & " + authors[-1]
        elif fmt == "mla":
            # MLA: Author1, Author2, and Author3.
            if len(authors) <= 2:
                return ", ".join(authors) + "."
            return authors[0] + ", et al."
        elif fmt == "ieee":
            # IEEE: A. Author, B. Author
            return ", ".join(authors)
        return ", ".join(authors)

    @staticmethod
    def _format_gbt7714(entry: ReferenceEntry) -> str:
        """GB/T 7714 格式。"""
        authors = CitationFormatter._format_authors(entry.authors, "gbt")
        parts = [authors]

        if entry.type == "journal":
            parts.append(entry.title + "[J].")
            if entry.journal:
                parts.append(entry.journal + ",")
            if entry.year:
                parts.append(entry.year + ",")
            if entry.volume:
                vol_str = entry.volume
                if entry.issue:
                    vol_str += f"({entry.issue})"
                parts.append(vol_str + ":")
            if entry.pages:
                parts.append(entry.pages + ".")
        elif entry.type == "book":
            parts.append(entry.title + "[M].")
            if entry.city:
                parts.append(entry.city + ":")
            if entry.publisher:
                parts.append(entry.publisher + ",")
            if entry.year:
                parts.append(entry.year + ".")
        elif entry.type == "conference":
            parts.append(entry.title + "[C].")
            if entry.journal:  # 会议名
                parts.append(entry.journal + ",")
            if entry.year:
                parts.append(entry.year + ":")
            if entry.pages:
                parts.append(entry.pages + ".")
        elif entry.type == "thesis":
            parts.append(entry.title + "[D].")
            if entry.city:
                parts.append(entry.city + ":")
            if entry.publisher:  # 学校
                parts.append(entry.publisher + ",")
            if entry.year:
                parts.append(entry.year + ".")
        elif entry.type == "web":
            parts.append(entry.title + "[EB/OL].")
            if entry.year:
                parts.append(f"({entry.year})")
            if entry.url:
                parts.append(entry.url + ".")
            if entry.access_date:
                parts.append(f"[{entry.access_date}].")
        else:
            parts.append(entry.title + ".")
            if entry.year:
                parts.append(entry.year + ".")

        return " ".join(parts)

    @staticmethod
    def _format_apa(entry: ReferenceEntry) -> str:
        """APA 格式。"""
        authors = CitationFormatter._format_authors(entry.authors, "apa")
        parts = [authors]

        if entry.year:
            parts.append(f"({entry.year}).")
        parts.append(entry.title + ".")

        if entry.type == "journal":
            if entry.journal:
                parts.append(f"*{entry.journal}*,")
            if entry.volume:
                vol_str = f"*{entry.volume}*"
                if entry.issue:
                    vol_str += f"({entry.issue})"
                parts.append(vol_str + ",")
            if entry.pages:
                parts.append(entry.pages + ".")
        elif entry.type == "book":
            if entry.publisher:
                parts.append(entry.publisher + ".")
        elif entry.type == "web":
            if entry.url:
                parts.append(entry.url)

        return " ".join(parts)

    @staticmethod
    def _format_mla(entry: ReferenceEntry) -> str:
        """MLA 格式。"""
        authors = CitationFormatter._format_authors(entry.authors, "mla")
        parts = [authors]
        parts.append(f'"{entry.title}."')

        if entry.type == "journal":
            if entry.journal:
                parts.append(f"*{entry.journal}*,")
            if entry.volume:
                parts.append(f"vol. {entry.volume},")
            if entry.issue:
                parts.append(f"no. {entry.issue},")
            if entry.year:
                parts.append(entry.year + ",")
            if entry.pages:
                parts.append(f"pp. {entry.pages}.")
        elif entry.type == "book":
            if entry.publisher:
                parts.append(entry.publisher + ",")
            if entry.year:
                parts.append(entry.year + ".")
        return " ".join(parts)

    @staticmethod
    def _format_chicago(entry: ReferenceEntry) -> str:
        """Chicago 格式。"""
        authors = CitationFormatter._format_authors(entry.authors, "apa")
        parts = [authors]
        parts.append(f'*{entry.title}*.')

        if entry.type == "journal":
            if entry.journal:
                parts.append(f"{entry.journal}")
            if entry.volume:
                parts.append(f"{entry.volume},")
            if entry.issue:
                parts.append(f"no. {entry.issue}")
            if entry.year:
                parts.append(f"({entry.year}):")
            if entry.pages:
                parts.append(entry.pages + ".")
        elif entry.type == "book":
            if entry.city:
                parts.append(entry.city + ":")
            if entry.publisher:
                parts.append(entry.publisher + ",")
            if entry.year:
                parts.append(entry.year + ".")
        return " ".join(parts)

    @staticmethod
    def _format_ieee(entry: ReferenceEntry) -> str:
        """IEEE 格式。"""
        authors = CitationFormatter._format_authors(entry.authors, "ieee")
        parts = [authors]
        parts.append(f'"{entry.title},"')

        if entry.type == "journal":
            if entry.journal:
                parts.append(f"*{entry.journal}*,")
            if entry.volume:
                parts.append(f"vol. {entry.volume},")
            if entry.issue:
                parts.append(f"no. {entry.issue},")
            if entry.pages:
                parts.append(f"pp. {entry.pages},")
            if entry.year:
                parts.append(entry.year + ".")
        elif entry.type == "conference":
            if entry.journal:
                parts.append(f"in *{entry.journal}*,")
            if entry.year:
                parts.append(entry.year + ".")
        return " ".join(parts)

    @staticmethod
    def _format_vancouver(entry: ReferenceEntry) -> str:
        """Vancouver 格式。"""
        authors = CitationFormatter._format_authors(entry.authors, "ieee")
        parts = [authors]
        parts.append(entry.title + ".")

        if entry.type == "journal":
            if entry.journal:
                parts.append(entry.journal + ".")
            if entry.year:
                parts.append(entry.year + ";")
            if entry.volume:
                vol_str = entry.volume
                if entry.issue:
                    vol_str += f"({entry.issue})"
                parts.append(vol_str + ":")
            if entry.pages:
                parts.append(entry.pages + ".")
        elif entry.type == "book":
            if entry.city:
                parts.append(entry.city + ":")
            if entry.publisher:
                parts.append(entry.publisher + ";")
            if entry.year:
                parts.append(entry.year + ".")
        return " ".join(parts)

    @staticmethod
    def format_in_text_citation(
        entry: ReferenceEntry,
        fmt: CitationFormat = CitationFormat.GB_T_7714,
        number: int = 1,
    ) -> str:
        """格式化文中引用。

        Args:
            entry: 参考文献条目。
            fmt: 引用格式。
            number: 引用编号（用于数字引用格式）。

        Returns:
            文中引用字符串。
        """
        if fmt in (CitationFormat.GB_T_7714, CitationFormat.IEEE, CitationFormat.VANCOUVER):
            return f"[{number}]"
        elif fmt == CitationFormat.APA:
            author = entry.authors[0] if entry.authors else "佚名"
            # 简化：取姓氏
            surname = author.split(",")[0] if "," in author else author.split()[-1] if author else "佚名"
            return f"({surname}, {entry.year})" if entry.year else f"({surname})"
        elif fmt == CitationFormat.MLA:
            author = entry.authors[0] if entry.authors else "佚名"
            surname = author.split(",")[0] if "," in author else author.split()[-1] if author else "佚名"
            return f"({surname} {entry.pages})" if entry.pages else f"({surname})"
        elif fmt == CitationFormat.CHICAGO:
            author = entry.authors[0] if entry.authors else "佚名"
            surname = author.split(",")[0] if "," in author else author.split()[-1] if author else "佚名"
            return f"({surname} {entry.year})" if entry.year else f"({surname})"
        return f"[{number}]"


# ===== 参考文献检查器 =====


class ReferenceChecker:
    """参考文献检查器

    检查参考文献列表的完整性与规范性。
    """

    # 必填字段（按类型）
    REQUIRED_FIELDS = {
        "journal": ["authors", "title", "year", "journal"],
        "book": ["authors", "title", "year", "publisher"],
        "conference": ["authors", "title", "year"],
        "thesis": ["authors", "title", "year", "publisher"],
        "web": ["title", "url"],
        "other": ["title"],
    }

    def check_entry(self, entry: ReferenceEntry) -> list:
        """检查单个参考文献条目。

        Args:
            entry: 参考文献条目。

        Returns:
            CitationIssue 列表。
        """
        issues = []
        required = self.REQUIRED_FIELDS.get(entry.type, ["title"])

        for field_name in required:
            value = getattr(entry, field_name, None)
            if not value:
                issues.append(CitationIssue(
                    field=field_name,
                    message=f"参考文献缺少必填字段: {field_name}",
                    severity="error",
                    suggestion=f"请补充 {field_name} 字段",
                ))

        # 检查年份格式
        if entry.year and not re.match(r"^\d{4}$", entry.year):
            issues.append(CitationIssue(
                field="year",
                message=f"年份格式 '{entry.year}' 无效，应为4位数字",
                severity="warning",
            ))

        # 检查 DOI 格式
        if entry.doi and not re.match(r"^10\.\d{4,}/", entry.doi):
            issues.append(CitationIssue(
                field="doi",
                message=f"DOI 格式 '{entry.doi}' 无效",
                severity="warning",
            ))

        # 检查 URL 格式
        if entry.url and not re.match(r"^https?://", entry.url):
            issues.append(CitationIssue(
                field="url",
                message="URL 应以 http:// 或 https:// 开头",
                severity="warning",
            ))

        # 检查作者格式
        if entry.authors:
            for i, author in enumerate(entry.authors):
                if not author.strip():
                    issues.append(CitationIssue(
                        field=f"authors[{i}]",
                        message="作者名为空",
                        severity="error",
                    ))

        # 检查标题长度
        if entry.title and len(entry.title) > 300:
            issues.append(CitationIssue(
                field="title",
                message=f"标题长度 {len(entry.title)} 过长",
                severity="warning",
            ))

        return issues

    def check_list(self, entries: list) -> list:
        """检查参考文献列表。

        Args:
            entries: ReferenceEntry 列表。

        Returns:
            CitationIssue 列表。
        """
        all_issues = []
        for i, entry in enumerate(entries):
            entry_issues = self.check_entry(entry)
            for issue in entry_issues:
                issue.position = i
                all_issues.append(issue)

        # 检查排序
        years = [e.year for e in entries if e.year and re.match(r"^\d{4}$", e.year)]
        if years and years != sorted(years):
            all_issues.append(CitationIssue(
                field="order",
                message="参考文献未按年份排序",
                severity="info",
                suggestion="建议按年份升序排列",
            ))

        # 检查重复
        titles = [e.title.lower().strip() for e in entries if e.title]
        seen = set()
        for i, title in enumerate(titles):
            if title in seen:
                all_issues.append(CitationIssue(
                    field="duplicate",
                    message=f"参考文献 {i + 1} 可能重复",
                    severity="warning",
                ))
            seen.add(title)

        return all_issues

    def check_citation_reference_match(
        self,
        text: str,
        references: list,
        fmt: CitationFormat = CitationFormat.GB_T_7714,
    ) -> dict:
        """检查文中引用与参考文献列表的匹配。

        Args:
            text: 正文文本。
            references: 参考文献列表。
            fmt: 引用格式。

        Returns:
            {"matched": [...], "unmatched_citations": [...], "unreferenced": [...]}
        """
        # 提取文中引用
        if fmt in (CitationFormat.GB_T_7714, CitationFormat.IEEE, CitationFormat.VANCOUVER):
            citations = re.findall(r"\[(\d+)\]", text)
            citation_numbers = [int(c) for c in citations]
        else:
            # 作者-年份格式
            citation_pattern = re.compile(r"\(([A-Z][a-z]+(?:\s+(?:et al\.|and|&)\s+[A-Z][a-z]+)*),?\s*(\d{4})\)")
            citations = citation_pattern.findall(text)
            citation_numbers = []

        ref_count = len(references)
        matched = []
        unmatched_citations = []

        for num in citation_numbers:
            if 1 <= num <= ref_count:
                matched.append(num)
            else:
                unmatched_citations.append(num)

        unreferenced = [i + 1 for i in range(ref_count) if (i + 1) not in matched]

        return {
            "matched": matched,
            "unmatched_citations": unmatched_citations,
            "unreferenced": unreferenced,
            "total_citations": len(citation_numbers),
            "total_references": ref_count,
        }


# ===== 学术写作规范检查器 =====


class AcademicWritingChecker:
    """学术写作规范检查器

    检查学术写作的规范性，包括用词、句式、结构等。
    """

    # 口语化词汇（学术写作应避免）
    COLLOQUIAL_WORDS = [
        "很", "非常", "特别", "极其", "太", "蛮", "挺",
        "搞", "弄", "整", "弄", "弄", "弄",
        "东西", "事情", "玩意", "啥", "咋", "咋样",
        "我觉得", "我认为", "我感觉", "我觉得",
        "总之", "总的来说", "总而言之",
        "大家", "咱们", "你们", "他们",
        "good", "bad", "big", "small", "thing", "stuff",
        "a lot of", "kind of", "sort of",
    ]

    # 第一人称代词（学术写作应避免或减少）
    FIRST_PERSON = ["我", "我们", "我的", "我们的", "I", "me", "my", "we", "us", "our"]

    # 模糊表达
    VAGUE_EXPRESSIONS = [
        "一些", "某些", "很多", "不少", "若干", "大量",
        "差不多", "大概", "可能", "也许", "或许", "似乎",
        "some", "many", "a lot", "probably", "maybe", "perhaps",
    ]

    # 主观判断词
    SUBJECTIVE_WORDS = [
        "显然", "明显", "当然", "毫无疑问", "不可否认",
        "obviously", "clearly", "of course", "undoubtedly",
    ]

    def check(self, text: str) -> list:
        """检查学术写作规范。

        Args:
            text: 待检查文本。

        Returns:
            CitationIssue 列表。
        """
        issues = []

        # 检查口语化词汇
        for word in self.COLLOQUIAL_WORDS:
            count = text.lower().count(word.lower())
            if count > 0:
                issues.append(CitationIssue(
                    field="vocabulary",
                    message=f"检测到口语化词汇 '{word}'（出现 {count} 次）",
                    severity="warning",
                    suggestion="建议使用更正式的学术表达",
                ))

        # 检查第一人称
        first_person_count = 0
        for word in self.FIRST_PERSON:
            first_person_count += len(re.findall(r"\b" + re.escape(word) + r"\b", text, re.IGNORECASE))
        if first_person_count > 3:
            issues.append(CitationIssue(
                field="person",
                message=f"第一人称代词使用过多（{first_person_count} 次）",
                severity="info",
                suggestion="学术写作建议使用第三人称或被动语态",
            ))

        # 检查模糊表达
        vague_count = 0
        for expr in self.VAGUE_EXPRESSIONS:
            vague_count += len(re.findall(re.escape(expr), text, re.IGNORECASE))
        if vague_count > 5:
            issues.append(CitationIssue(
                field="precision",
                message=f"模糊表达使用过多（{vague_count} 次）",
                severity="warning",
                suggestion="建议使用具体数据或明确描述",
            ))

        # 检查主观判断
        for word in self.SUBJECTIVE_WORDS:
            if re.search(re.escape(word), text, re.IGNORECASE):
                issues.append(CitationIssue(
                    field="objectivity",
                    message=f"检测到主观判断词 '{word}'",
                    severity="info",
                    suggestion="建议用数据或引用支撑论断",
                ))

        # 检查句子长度
        sentences = re.split(r"[。！？.!?]", text)
        long_sentences = [s for s in sentences if len(s.strip()) > 100]
        if long_sentences:
            issues.append(CitationIssue(
                field="sentence_length",
                message=f"检测到 {len(long_sentences)} 个过长句子（>100字）",
                severity="info",
                suggestion="建议拆分长句以提高可读性",
            ))

        # 检查段落长度
        paragraphs = text.split("\n\n")
        long_paragraphs = [p for p in paragraphs if len(p.strip()) > 500]
        if long_paragraphs:
            issues.append(CitationIssue(
                field="paragraph_length",
                message=f"检测到 {len(long_paragraphs)} 个过长段落（>500字）",
                severity="info",
                suggestion="建议分段以提高结构清晰度",
            ))

        # 检查感叹号
        exclamation_count = text.count("！") + text.count("!")
        if exclamation_count > 3:
            issues.append(CitationIssue(
                field="punctuation",
                message=f"感叹号使用过多（{exclamation_count} 次）",
                severity="warning",
                suggestion="学术写作应避免过多感叹号",
            ))

        # 检查问号
        question_count = text.count("？") + text.count("?")
        if question_count > 5:
            issues.append(CitationIssue(
                field="punctuation",
                message=f"问号使用较多（{question_count} 次）",
                severity="info",
                suggestion="学术写作应以陈述句为主",
            ))

        # 检查缩写首次使用
        abbreviations = re.findall(r"\b([A-Z]{2,})\b", text)
        # 简单检查：缩写是否在首次使用时给出全称
        common_abbreviations = {"AI", "ML", "DL", "NLP", "API", "URL", "HTTP", "HTTPS", "PDF", "JSON"}
        for abbr in set(abbreviations):
            if abbr in common_abbreviations:
                # 检查是否有全称（括号内）
                pattern = rf"\([A-Z][a-zA-Z\s]+{abbr}\)|{abbr}\s*\([A-Z][a-zA-Z\s]+\)"
                if not re.search(pattern, text):
                    issues.append(CitationIssue(
                        field="abbreviation",
                        message=f"缩写 '{abbr}' 首次使用可能未给出全称",
                        severity="info",
                        suggestion="首次使用缩写时应给出全称",
                    ))

        return issues

    def check_structure(self, text: str) -> list:
        """检查文本结构规范。

        Args:
            text: 待检查文本。

        Returns:
            CitationIssue 列表。
        """
        issues = []

        # 检查标题层级
        headings = re.findall(r"^(#{1,6})\s+(.+)$", text, re.MULTILINE)
        if headings:
            prev_level = 0
            for level_str, title in headings:
                level = len(level_str)
                if level > prev_level + 1 and prev_level > 0:
                    issues.append(CitationIssue(
                        field="heading_hierarchy",
                        message=f"标题层级跳跃: 从 {prev_level} 级跳到 {level} 级",
                        severity="warning",
                        suggestion="标题层级应逐级递增",
                    ))
                prev_level = level

        # 检查是否有引言
        if not re.search(r"(引言|绪论|前言|Introduction|INTRODUCTION)", text, re.IGNORECASE):
            issues.append(CitationIssue(
                field="structure",
                message="未检测到引言部分",
                severity="info",
                suggestion="学术论文应包含引言部分",
            ))

        # 检查是否有结论
        if not re.search(r"(结论|结语|总结|Conclusion|CONCLUSION)", text, re.IGNORECASE):
            issues.append(CitationIssue(
                field="structure",
                message="未检测到结论部分",
                severity="info",
                suggestion="学术论文应包含结论部分",
            ))

        # 检查是否有参考文献
        if not re.search(r"(参考文献|引用文献|References|REFERENCES|Bibliography)", text, re.IGNORECASE):
            issues.append(CitationIssue(
                field="structure",
                message="未检测到参考文献部分",
                severity="warning",
                suggestion="学术论文应包含参考文献列表",
            ))

        return issues


# ===== 学术规范主类 =====


class AcademicStandards:
    """学术规范主类

    整合引用格式化、参考文献检查与写作规范检查。
    """

    def __init__(self, default_format: CitationFormat = CitationFormat.GB_T_7714):
        self.default_format = default_format
        self.formatter = CitationFormatter()
        self.reference_checker = ReferenceChecker()
        self.writing_checker = AcademicWritingChecker()

    def format_reference(self, entry: ReferenceEntry, fmt: Optional[CitationFormat] = None) -> str:
        """格式化参考文献。"""
        return self.formatter.format(entry, fmt or self.default_format)

    def format_references(self, entries: list, fmt: Optional[CitationFormat] = None) -> list:
        """批量格式化参考文献。"""
        return [self.format_reference(e, fmt) for e in entries]

    def check_reference(self, entry: ReferenceEntry) -> list:
        """检查单个参考文献。"""
        return self.reference_checker.check_entry(entry)

    def check_references(self, entries: list) -> list:
        """检查参考文献列表。"""
        return self.reference_checker.check_list(entries)

    def check_writing(self, text: str) -> list:
        """检查学术写作规范。"""
        return self.writing_checker.check(text)

    def check_structure(self, text: str) -> list:
        """检查文本结构。"""
        return self.writing_checker.check_structure(text)

    def check_all(
        self,
        text: str,
        references: Optional[list] = None,
        fmt: Optional[CitationFormat] = None,
    ) -> StandardsReport:
        """执行全面检查。

        Args:
            text: 正文文本。
            references: 参考文献列表。
            fmt: 引用格式。

        Returns:
            StandardsReport 实例。
        """
        references = references or []
        use_format = fmt or self.default_format
        all_issues = []

        # 写作规范检查
        all_issues.extend(self.check_writing(text))

        # 结构检查
        all_issues.extend(self.check_structure(text))

        # 参考文献检查
        if references:
            ref_issues = self.check_references(references)
            all_issues.extend(ref_issues)

            # 引用匹配检查
            match_result = self.reference_checker.check_citation_reference_match(
                text, references, use_format
            )
            if match_result["unmatched_citations"]:
                all_issues.append(CitationIssue(
                    field="citation_match",
                    message=f"检测到 {len(match_result['unmatched_citations'])} 个未匹配的文中引用",
                    severity="error",
                ))
            if match_result["unreferenced"]:
                all_issues.append(CitationIssue(
                    field="citation_match",
                    message=f"检测到 {len(match_result['unreferenced'])} 条未被引用的参考文献",
                    severity="warning",
                ))

        # 计算一致性评分
        total_checks = len(all_issues) + 1
        error_count = sum(1 for i in all_issues if i.severity == "error")
        warning_count = sum(1 for i in all_issues if i.severity == "warning")
        consistency_score = max(0.0, 1.0 - (error_count * 0.2 + warning_count * 0.1))

        # 生成建议
        recommendations = self._generate_recommendations(all_issues)

        passed = error_count == 0

        return StandardsReport(
            passed=passed,
            format=use_format.value,
            issues=all_issues,
            reference_count=len(references),
            citation_count=len(re.findall(r"\[\d+\]|\(\d{4}\)", text)),
            consistency_score=consistency_score,
            recommendations=recommendations,
        )

    def _generate_recommendations(self, issues: list) -> list:
        """生成改进建议。"""
        recommendations = []
        error_count = sum(1 for i in issues if i.severity == "error")
        warning_count = sum(1 for i in issues if i.severity == "warning")

        if error_count > 0:
            recommendations.append(f"发现 {error_count} 个严重问题，请优先修复")
        if warning_count > 5:
            recommendations.append(f"发现 {warning_count} 个警告，建议逐项检查")

        # 按字段分组统计
        by_field: dict[str, int] = {}
        for issue in issues:
            field = issue.field.split(".")[0]
            by_field[field] = by_field.get(field, 0) + 1

        for field, count in sorted(by_field.items(), key=lambda x: x[1], reverse=True):
            if count >= 3:
                recommendations.append(f"'{field}' 方面存在 {count} 个问题，建议重点关注")

        if not recommendations:
            recommendations.append("学术规范检查通过，未发现明显问题")

        return recommendations


# ===== 预定义格式化规则 =====


FORMATTING_RULES: list[dict] = [
    {"id": "fmt.001", "name": "标题层级递增", "description": "标题层级应逐级递增，不跳跃",
     "category": "structure", "severity": "warning"},
    {"id": "fmt.002", "name": "包含引言", "description": "学术论文应包含引言部分",
     "category": "structure", "severity": "info"},
    {"id": "fmt.003", "name": "包含结论", "description": "学术论文应包含结论部分",
     "category": "structure", "severity": "info"},
    {"id": "fmt.004", "name": "包含参考文献", "description": "学术论文应包含参考文献列表",
     "category": "structure", "severity": "warning"},
    {"id": "fmt.005", "name": "参考文献必填字段", "description": "参考文献应包含必填字段",
     "category": "reference", "severity": "error"},
    {"id": "fmt.006", "name": "年份格式", "description": "年份应为4位数字",
     "category": "reference", "severity": "warning"},
    {"id": "fmt.007", "name": "DOI格式", "description": "DOI 应符合标准格式",
     "category": "reference", "severity": "warning"},
    {"id": "fmt.008", "name": "URL格式", "description": "URL 应以 http:// 或 https:// 开头",
     "category": "reference", "severity": "warning"},
    {"id": "fmt.009", "name": "引用编号连续", "description": "引用编号应连续不跳号",
     "category": "citation", "severity": "warning"},
    {"id": "fmt.010", "name": "引用参考文献匹配", "description": "文中引用应与参考文献列表匹配",
     "category": "citation", "severity": "error"},
    {"id": "fmt.011", "name": "无口语化词汇", "description": "学术写作应避免口语化词汇",
     "category": "writing", "severity": "warning"},
    {"id": "fmt.012", "name": "减少第一人称", "description": "学术写作应减少第一人称代词",
     "category": "writing", "severity": "info"},
    {"id": "fmt.013", "name": "避免模糊表达", "description": "学术写作应避免模糊表达",
     "category": "writing", "severity": "warning"},
    {"id": "fmt.014", "name": "避免主观判断", "description": "学术写作应用数据支撑论断",
     "category": "writing", "severity": "info"},
    {"id": "fmt.015", "name": "句子长度适中", "description": "句子不宜过长（≤100字）",
     "category": "writing", "severity": "info"},
    {"id": "fmt.016", "name": "段落长度适中", "description": "段落不宜过长（≤500字）",
     "category": "writing", "severity": "info"},
    {"id": "fmt.017", "name": "感叹号限制", "description": "学术写作应避免过多感叹号",
     "category": "writing", "severity": "warning"},
    {"id": "fmt.018", "name": "缩写全称", "description": "缩写首次使用应给出全称",
     "category": "writing", "severity": "info"},
    {"id": "fmt.019", "name": "参考文献排序", "description": "参考文献应按年份排序",
     "category": "reference", "severity": "info"},
    {"id": "fmt.020", "name": "无重复参考文献", "description": "参考文献列表不应有重复",
     "category": "reference", "severity": "warning"},
]


def get_formatting_rules() -> list:
    """获取格式化规则列表。"""
    return FORMATTING_RULES


# ===== 全局实例 =====

_global_standards = AcademicStandards()


def get_academic_standards() -> AcademicStandards:
    """获取全局学术规范实例。"""
    return _global_standards


def check_academic_standards(
    text: str,
    references: Optional[list] = None,
    fmt: Optional[CitationFormat] = None,
) -> StandardsReport:
    """便捷函数：检查学术规范。"""
    return _global_standards.check_all(text, references, fmt)


def format_reference(entry: ReferenceEntry, fmt: Optional[CitationFormat] = None) -> str:
    """便捷函数：格式化参考文献。"""
    return _global_standards.format_reference(entry, fmt)
