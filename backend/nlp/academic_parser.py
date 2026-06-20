"""学术文本解析器模块

提供面向学术论文的结构化解析能力，包括：
    - 论文结构识别（标题/摘要/关键词/引言/方法/结果/讨论/结论/参考文献）
    - 章节层次结构与目录生成
    - 图表标题提取与表格结构解析
    - 公式识别与定位
    - 引用标记识别与参考文献列表解析
    - 引用-参考文献匹配
    - 页码识别
    - 多格式支持（Markdown/HTML/LaTeX/纯文本）

仅使用 Python 标准库实现，不依赖外部解析库。
针对中文学术论文场景进行专项优化，同时兼容英文论文。

典型用法：
    parser = AcademicParser()
    structure = parser.parse(text, format="markdown")
    sections = parser.identify_sections(text)
    refs = parser.parse_references(text)
    figures = parser.extract_figures(text)
    matched = parser.match_citations(text)
"""
from __future__ import annotations

import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# 尝试导入项目内模块
try:
    from backend.utils.logger import get_logger

    _logger = get_logger(__name__)
except Exception:  # pragma: no cover
    import logging

    _logger = logging.getLogger(__name__)

try:
    from backend.nlp.chinese_processor import ChineseProcessor, get_chinese_processor
except Exception:  # pragma: no cover
    ChineseProcessor = None  # type: ignore
    get_chinese_processor = None  # type: ignore


# ===== 常量定义 =====

# 论文结构章节关键词（中文）
SECTION_KEYWORDS_ZH = {
    "title": ["标题", "题目", "论文题目"],
    "abstract": ["摘要", "内容提要", "提要"],
    "keywords": ["关键词", "关键字", "主题词"],
    "introduction": ["引言", "绪论", "前言", "背景", "研究背景", "导论", "引子"],
    "related_work": ["相关工作", "文献综述", "研究现状", "国内外研究现状", "研究进展"],
    "method": ["方法", "方法论", "研究方法", "方法学", "材料与方法", "实验方法",
               "模型", "算法", "技术路线", "方案设计", "系统设计"],
    "experiment": ["实验", "实验设计", "实验设置", "实验环境", "实验配置"],
    "result": ["结果", "实验结果", "结果分析", "结果与讨论", "数据分析", "评估结果"],
    "discussion": ["讨论", "分析与讨论", "讨论分析", "问题讨论"],
    "conclusion": ["结论", "总结", "结语", "小结", "总结与展望", "结论与展望"],
    "acknowledgement": ["致谢", "鸣谢", "感谢"],
    "references": ["参考文献", "文献", "引用文献", "参考资料"],
    "appendix": ["附录", "补充材料", "附加材料"],
    "author_bio": ["作者简介", "作者信息"],
}

# 论文结构章节关键词（英文）
SECTION_KEYWORDS_EN = {
    "title": ["title"],
    "abstract": ["abstract", "summary"],
    "keywords": ["keywords", "key words", "index terms"],
    "introduction": ["introduction", "background", "overview"],
    "related_work": ["related work", "literature review", "prior work", "state of the art"],
    "method": ["method", "methodology", "approach", "model", "algorithm", "design",
               "materials and methods", "methods", "system design", "framework"],
    "experiment": ["experiment", "experimental setup", "experimental design",
                   "evaluation setup", "implementation details"],
    "result": ["results", "experimental results", "evaluation", "analysis",
               "results and analysis", "findings"],
    "discussion": ["discussion"],
    "conclusion": ["conclusion", "conclusions", "concluding remarks", "summary",
                   "future work", "conclusion and future work"],
    "acknowledgement": ["acknowledgement", "acknowledgments", "acknowledgment"],
    "references": ["references", "bibliography", "works cited"],
    "appendix": ["appendix", "appendices", "supplementary material"],
    "author_bio": ["author biography", "about the author", "author information"],
}

# 章节标题正则模式
SECTION_TITLE_PATTERNS = [
    # 中文：第X章/节/部分/篇 标题
    re.compile(r"^第[一二三四五六七八九十百千零\d]+[章节部分篇][\s　]*(.+)$"),
    # 中文：一、二、三、标题
    re.compile(r"^([一二三四五六七八九十百千零]+)[、.\s　]+(.+)$"),
    # 中文：（一）（二）标题
    re.compile(r"^[（(][一二三四五六七八九十百千零\d]+[)）][\s　]*(.+)$"),
    # 数字编号：1. 标题 / 1.1 标题 / 1.1.1 标题
    re.compile(r"^(\d+(?:\.\d+)*)[.\s　]+(.+)$"),
    # Markdown 标题：# 标题 / ## 标题
    re.compile(r"^(#{1,6})\s+(.+)$"),
    # LaTeX 标题：\section{标题} / \subsection{标题}
    re.compile(r"^\\(?:section|subsection|subsubsection|chapter|part|paragraph)\{([^}]+)\}"),
    # HTML 标题：<h1>标题</h1>
    re.compile(r"^<h([1-6])[^>]*>(.+?)</h\1>$", re.IGNORECASE),
]

# 图标题模式（中英文）
FIGURE_CAPTION_PATTERNS = [
    re.compile(r"^图\s*(\d+(?:\.\d+)*)\s*[.、:：\s]\s*(.+)$"),  # 图 1. 标题
    re.compile(r"^图\s*(\d+(?:\.\d+)*)\s*(.+)$"),  # 图1 标题
    re.compile(r"^Figure\s+(\d+(?:\.\d+)*)\s*[.:\s]\s*(.+)$", re.IGNORECASE),  # Figure 1. caption
    re.compile(r"^Fig\.?\s*(\d+(?:\.\d+)*)\s*[.:\s]\s*(.+)$", re.IGNORECASE),  # Fig. 1 caption
]

# 表标题模式（中英文）
TABLE_CAPTION_PATTERNS = [
    re.compile(r"^表\s*(\d+(?:\.\d+)*)\s*[.、:：\s]\s*(.+)$"),  # 表 1. 标题
    re.compile(r"^表\s*(\d+(?:\.\d+)*)\s*(.+)$"),  # 表1 标题
    re.compile(r"^Table\s+(\d+(?:\.\d+)*)\s*[.:\s]\s*(.+)$", re.IGNORECASE),  # Table 1. caption
    re.compile(r"^Tab\.?\s*(\d+(?:\.\d+)*)\s*[.:\s]\s*(.+)$", re.IGNORECASE),  # Tab. 1 caption
]

# 引用标记模式
CITATION_PATTERNS = [
    re.compile(r"\[\d+(?:[-,]\s*\d+)*\]"),  # [1] / [1,2,3] / [1-3]
    re.compile(r"\(\s*[A-Z][a-zA-Z]+(?:\s+et\s+al\.?)?\s*,\s*\d{4}\s*\)"),  # (Smith, 2020)
    re.compile(r"\(\s*[A-Z][a-zA-Z]+(?:\s+(?:and|&)\s+[A-Z][a-zA-Z]+)?\s*,\s*\d{4}\s*\)"),
    re.compile(r"[\u4e00-\u9fff]{2,4}（\d{4}）"),  # 张三（2020）
    re.compile(r"[\u4e00-\u9fff]{2,4}等（\d{4}）"),  # 张三等（2020）
    re.compile(r"\[\s*[A-Z][a-zA-Z]+\d{4}[a-z]?\s*\]"),  # [Smith2020]
]

# 参考文献条目模式
REFERENCE_PATTERNS = [
    # [1] 作者. 标题. 期刊, 年.
    re.compile(r"^\[(\d+)\]\s*(.+)$"),
    # 1. 作者. 标题. 期刊, 年.
    re.compile(r"^(\d+)[.\s]\s*(.+)$"),
    # 作者. 标题. 期刊, 年.（无编号）
    re.compile(r"^([A-Z][a-zA-Z]+(?:,\s*[A-Z]\.)+(?:\s+(?:and|&)\s+[A-Z][a-zA-Z]+(?:,\s*[A-Z]\.)*)*)\s*(\d{4})\.?\s*(.+)$"),
]

# 公式模式
FORMULA_PATTERNS = [
    re.compile(r"\$\$[^$]+\$\$", re.DOTALL),  # $$...$$ 块级公式
    re.compile(r"\$[^$\n]+\$"),  # $...$ 行内公式
    re.compile(r"\\\([^)]+\\\)"),  # \(...\)
    re.compile(r"\\\[[^\]]+\\\]"),  # \[...\]
    re.compile(r"\\begin\{equation\}.*?\\end\{equation\}", re.DOTALL),  # LaTeX equation
    re.compile(r"\\begin\{align\}.*?\\end\{align\}", re.DOTALL),  # LaTeX align
    re.compile(r"\((?:公式|式)\s*\d+(?:\.\d+)*\)"),  # （公式 1）
]

# 页码模式
PAGE_NUMBER_PATTERNS = [
    re.compile(r"^-\s*\d+\s*-$"),  # - 1 -
    re.compile(r"^\d+\s*$"),  # 1
    re.compile(r"^第\s*\d+\s*页$"),  # 第 1 页
    re.compile(r"^Page\s+\d+$", re.IGNORECASE),  # Page 1
    re.compile(r"^\d+\s*/\s*\d+$"),  # 1/10
]

# 章节类型枚举映射
SECTION_TYPE_NAMES = {
    "title": "标题",
    "abstract": "摘要",
    "keywords": "关键词",
    "introduction": "引言",
    "related_work": "相关工作",
    "method": "方法",
    "experiment": "实验",
    "result": "结果",
    "discussion": "讨论",
    "conclusion": "结论",
    "acknowledgement": "致谢",
    "references": "参考文献",
    "appendix": "附录",
    "author_bio": "作者简介",
    "unknown": "未知",
}

# 支持的输入格式
SUPPORTED_FORMATS = {"markdown", "html", "latex", "text", "plain"}


# ===== 数据类定义 =====

@dataclass
class Section:
    """论文章节。

    Attributes:
        section_type: 章节类型（title/abstract/introduction/method 等）。
        title: 章节标题文本。
        content: 章节正文内容。
        level: 章节层级（1 为顶级，2 为二级，以此类推）。
        number: 章节编号（如 "1" / "1.1" / "2.3.1"）。
        start: 在原文中的起始偏移。
        end: 在原文中的结束偏移。
        children: 子章节列表。
        parent: 父章节（若有）。
    """
    section_type: str = "unknown"
    title: str = ""
    content: str = ""
    level: int = 1
    number: str = ""
    start: int = 0
    end: int = 0
    children: List["Section"] = field(default_factory=list)
    parent: Optional["Section"] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典表示。"""
        return {
            "section_type": self.section_type,
            "type_name": SECTION_TYPE_NAMES.get(self.section_type, "未知"),
            "title": self.title,
            "content": self.content[:200] + "..." if len(self.content) > 200 else self.content,
            "content_length": len(self.content),
            "level": self.level,
            "number": self.number,
            "start": self.start,
            "end": self.end,
            "children_count": len(self.children),
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class Figure:
    """图表信息。

    Attributes:
        figure_type: 类型（figure/table）。
        number: 编号（如 "1" / "1.1"）。
        caption: 标题文本。
        start: 起始偏移。
        end: 结束偏移。
        label: 标签（如 "fig:example"）。
        referenced: 是否在正文中被引用。
    """
    figure_type: str = "figure"
    number: str = ""
    caption: str = ""
    start: int = 0
    end: int = 0
    label: Optional[str] = None
    referenced: bool = False


@dataclass
class Table:
    """表格信息。

    Attributes:
        number: 表格编号。
        caption: 表格标题。
        headers: 表头列表。
        rows: 数据行列表（每行为单元格列表）。
        start: 起始偏移。
        end: 结束偏移。
        row_count: 行数。
        col_count: 列数。
    """
    number: str = ""
    caption: str = ""
    headers: List[str] = field(default_factory=list)
    rows: List[List[str]] = field(default_factory=list)
    start: int = 0
    end: int = 0
    row_count: int = 0
    col_count: int = 0


@dataclass
class Formula:
    """公式信息。

    Attributes:
        text: 公式文本。
        formula_type: 公式类型（inline/block/latex）。
        number: 公式编号（若有）。
        start: 起始偏移。
        end: 结束偏移。
    """
    text: str = ""
    formula_type: str = "inline"
    number: str = ""
    start: int = 0
    end: int = 0


@dataclass
class Reference:
    """参考文献条目。

    Attributes:
        number: 编号。
        raw_text: 原始文本。
        authors: 作者列表。
        title: 文献标题。
        venue: 发表期刊/会议。
        year: 发表年份。
        volume: 卷号。
        issue: 期号。
        pages: 页码范围。
        publisher: 出版社。
        doi: DOI。
        url: URL。
        ref_type: 文献类型（journal/conference/book/thesis/web）。
    """
    number: str = ""
    raw_text: str = ""
    authors: List[str] = field(default_factory=list)
    title: str = ""
    venue: str = ""
    year: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    publisher: str = ""
    doi: str = ""
    url: str = ""
    ref_type: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典表示。"""
        return {
            "number": self.number,
            "authors": self.authors,
            "title": self.title,
            "venue": self.venue,
            "year": self.year,
            "volume": self.volume,
            "issue": self.issue,
            "pages": self.pages,
            "publisher": self.publisher,
            "doi": self.doi,
            "url": self.url,
            "ref_type": self.ref_type,
            "raw_text": self.raw_text[:100] + "..." if len(self.raw_text) > 100 else self.raw_text,
        }


@dataclass
class Citation:
    """引用标记。

    Attributes:
        text: 引用文本。
        citation_type: 引用类型（numeric/author_year/chinese）。
        start: 起始偏移。
        end: 结束偏移。
        ref_ids: 引用的参考文献编号列表。
        matched: 是否匹配到参考文献。
    """
    text: str = ""
    citation_type: str = "numeric"
    start: int = 0
    end: int = 0
    ref_ids: List[str] = field(default_factory=list)
    matched: bool = False


@dataclass
class DocumentStructure:
    """文档结构化解析结果。

    Attributes:
        title: 文档标题。
        authors: 作者列表。
        abstract: 摘要文本。
        keywords: 关键词列表。
        sections: 章节列表。
        figures: 图列表。
        tables: 表列表。
        formulas: 公式列表。
        references: 参考文献列表。
        citations: 引用标记列表。
        format: 输入格式。
        page_count: 估算页数。
        word_count: 词数。
        language: 语言（zh/en/mixed）。
    """
    title: str = ""
    authors: List[str] = field(default_factory=list)
    abstract: str = ""
    keywords: List[str] = field(default_factory=list)
    sections: List[Section] = field(default_factory=list)
    figures: List[Figure] = field(default_factory=list)
    tables: List[Table] = field(default_factory=list)
    formulas: List[Formula] = field(default_factory=list)
    references: List[Reference] = field(default_factory=list)
    citations: List[Citation] = field(default_factory=list)
    format: str = "text"
    page_count: int = 0
    word_count: int = 0
    language: str = "zh"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典表示。"""
        return {
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract[:200] + "..." if len(self.abstract) > 200 else self.abstract,
            "abstract_length": len(self.abstract),
            "keywords": self.keywords,
            "sections": [s.to_dict() for s in self.sections],
            "section_count": len(self.sections),
            "figures": [
                {"number": f.number, "caption": f.caption, "type": f.figure_type}
                for f in self.figures
            ],
            "figure_count": len(self.figures),
            "tables": [
                {"number": t.number, "caption": t.caption, "rows": t.row_count, "cols": t.col_count}
                for t in self.tables
            ],
            "table_count": len(self.tables),
            "formula_count": len(self.formulas),
            "reference_count": len(self.references),
            "citation_count": len(self.citations),
            "matched_citations": sum(1 for c in self.citations if c.matched),
            "format": self.format,
            "page_count": self.page_count,
            "word_count": self.word_count,
            "language": self.language,
        }


# ===== 主类：学术文本解析器 =====

class AcademicParser:
    """学术文本解析器。

    提供学术论文的结构化解析能力，支持 Markdown、HTML、LaTeX、纯文本四种格式。
    可识别论文的标准结构（标题/摘要/关键词/引言/方法/结果/讨论/结论/参考文献），
    提取图表、公式、引用标记，并完成引用-参考文献匹配。

    线程安全说明：本类为无状态解析器，可在多线程环境共享实例。

    Attributes:
        chinese_processor: 中文处理器实例（用于分词与语言检测）。
    """

    # 单例实例
    _instance: Optional["AcademicParser"] = None

    def __init__(
        self,
        chinese_processor: Optional[ChineseProcessor] = None,
    ) -> None:
        """初始化学术解析器。

        Args:
            chinese_processor: 自定义中文处理器，为 None 时使用全局单例。
        """
        # 中文处理器
        if chinese_processor is not None:
            self.chinese_processor = chinese_processor
        elif get_chinese_processor is not None:
            try:
                self.chinese_processor = get_chinese_processor()
            except Exception:  # pragma: no cover
                self.chinese_processor = None
        else:
            self.chinese_processor = None
        # 章节关键词映射（合并中英文）
        self.section_keywords: Dict[str, List[str]] = {}
        for sec_type in set(list(SECTION_KEYWORDS_ZH.keys()) + list(SECTION_KEYWORDS_EN.keys())):
            zh_kw = SECTION_KEYWORDS_ZH.get(sec_type, [])
            en_kw = SECTION_KEYWORDS_EN.get(sec_type, [])
            self.section_keywords[sec_type] = zh_kw + en_kw
        _logger.debug("AcademicParser 初始化完成")

    @classmethod
    def get_instance(cls) -> "AcademicParser":
        """获取全局单例实例。"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ===== 主解析入口 =====

    def parse(
        self,
        text: str,
        format: str = "text",
        extract_figures: bool = True,
        extract_tables: bool = True,
        extract_formulas: bool = True,
        extract_references: bool = True,
        match_citations: bool = True,
    ) -> DocumentStructure:
        """解析学术论文。

        主解析入口，依次执行：格式预处理、章节识别、元数据提取、
        图表/公式/参考文献提取、引用匹配。

        Args:
            text: 论文文本。
            format: 输入格式（markdown/html/latex/text）。
            extract_figures: 是否提取图表。
            extract_tables: 是否提取表格。
            extract_formulas: 是否提取公式。
            extract_references: 是否提取参考文献。
            match_citations: 是否进行引用-参考文献匹配。

        Returns:
            文档结构化解析结果。
        """
        if not text:
            return DocumentStructure()
        format = format.lower()
        if format not in SUPPORTED_FORMATS:
            format = "text"
        # 格式预处理：将 HTML/LaTeX 转为纯文本（保留结构标记）
        processed_text = self._preprocess(text, format)
        # 初始化结构
        structure = DocumentStructure(format=format)
        structure.language = self._detect_language(processed_text)
        structure.word_count = len(processed_text)
        structure.page_count = max(1, structure.word_count // 1500)  # 估算页数
        # 章节识别
        structure.sections = self.identify_sections(processed_text)
        # 元数据提取（标题、作者、摘要、关键词）
        self._extract_metadata(processed_text, structure)
        # 图表提取
        if extract_figures:
            structure.figures = self.extract_figures(processed_text)
        if extract_tables:
            structure.tables = self.parse_tables(processed_text)
        # 公式提取
        if extract_formulas:
            structure.formulas = self.extract_formulas(processed_text)
        # 参考文献提取
        if extract_references:
            structure.references = self.parse_references(processed_text)
        # 引用标记识别
        structure.citations = self.identify_citations(processed_text)
        # 引用-参考文献匹配
        if match_citations and structure.references:
            self._match_citations_with_references(structure)
        _logger.debug(
            "解析完成：章节=%d，图=%d，表=%d，公式=%d，参考文献=%d，引用=%d",
            len(structure.sections), len(structure.figures),
            len(structure.tables), len(structure.formulas),
            len(structure.references), len(structure.citations),
        )
        return structure

    def _preprocess(self, text: str, format: str) -> str:
        """格式预处理。

        将不同格式的输入统一为带结构标记的纯文本。

        Args:
            text: 原始文本。
            format: 输入格式。

        Returns:
            预处理后的文本。
        """
        if format == "html":
            return self._html_to_text(text)
        elif format == "latex":
            return self._latex_to_text(text)
        elif format == "markdown":
            return self._markdown_to_text(text)
        else:
            return text

    def _html_to_text(self, html: str) -> str:
        """将 HTML 转为纯文本（保留标题标签）。

        Args:
            html: HTML 文本。

        Returns:
            纯文本。
        """
        # 移除脚本与样式
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        # 将标题标签转为 Markdown 风格
        for i in range(1, 7):
            prefix = "#" * i
            text = re.sub(
                rf"<h{i}[^>]*>(.+?)</h{i}>",
                rf"{prefix} \1",
                text, flags=re.DOTALL | re.IGNORECASE,
            )
        # 将段落与换行标签转为换行符
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<p[^>]*>", "\n\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</p>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"<div[^>]*>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</div>", "", text, flags=re.IGNORECASE)
        # 移除所有其他标签
        text = re.sub(r"<[^>]+>", "", text)
        # 解码 HTML 实体
        entities = {
            "&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">",
            "&quot;": '"', "&#39;": "'", "&hellip;": "…",
            "&mdash;": "—", "&ndash;": "–",
        }
        for entity, char in entities.items():
            text = text.replace(entity, char)
        # 数字实体
        text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)
        # 规整空白
        text = re.sub(r"[^\S\n]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _latex_to_text(self, text: str) -> str:
        """将 LaTeX 转为纯文本（保留章节命令）。

        Args:
            text: LaTeX 文本。

        Returns:
            纯文本。
        """
        # 移除注释
        text = re.sub(r"(?<!\\)%.*$", "", text, flags=re.MULTILINE)
        # 将章节命令转为 Markdown 风格
        text = re.sub(r"\\chapter\{([^}]+)\}", r"# \1", text)
        text = re.sub(r"\\section\{([^}]+)\}", r"## \1", text)
        text = re.sub(r"\\subsection\{([^}]+)\}", r"### \1", text)
        text = re.sub(r"\\subsubsection\{([^}]+)\}", r"#### \1", text)
        text = re.sub(r"\\paragraph\{([^}]+)\}", r"##### \1", text)
        # 处理标题与摘要
        text = re.sub(r"\\title\{([^}]+)\}", r"# \1", text)
        text = re.sub(r"\\begin\{abstract\}", "## 摘要\n", text)
        text = re.sub(r"\\end\{abstract\}", "", text)
        # 处理列表
        text = re.sub(r"\\begin\{itemize\}", "", text)
        text = re.sub(r"\\end\{itemize\}", "", text)
        text = re.sub(r"\\begin\{enumerate\}", "", text)
        text = re.sub(r"\\end\{enumerate\}", "", text)
        text = re.sub(r"\\item\s+", "- ", text)
        # 移除其他环境
        text = re.sub(r"\\begin\{[^}]+\}", "", text)
        text = re.sub(r"\\end\{[^}]+\}", "", text)
        # 处理引用
        text = re.sub(r"\\cite\{([^}]+)\}", r"[\1]", text)
        text = re.sub(r"\\ref\{([^}]+)\}", r"\1", text)
        text = re.sub(r"\\label\{([^}]+)\}", "", text)
        # 移除其他命令（保留参数）
        text = re.sub(r"\\textbf\{([^}]+)\}", r"\1", text)
        text = re.sub(r"\\textit\{([^}]+)\}", r"\1", text)
        text = re.sub(r"\\emph\{([^}]+)\}", r"\1", text)
        text = re.sub(r"\\underline\{([^}]+)\}", r"\1", text)
        # 移除剩余的 LaTeX 命令
        text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{[^}]*\})?", "", text)
        # 移除特殊字符
        text = text.replace("\\%", "%").replace("\\&", "&").replace("\\#", "#")
        text = text.replace("\\_", "_").replace("\\{", "{").replace("\\}", "}")
        # 规整空白
        text = re.sub(r"[^\S\n]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _markdown_to_text(self, text: str) -> str:
        """将 Markdown 转为纯文本（保留标题标记）。

        Args:
            text: Markdown 文本。

        Returns:
            纯文本。
        """
        # 移除代码块（保留内容）
        text = re.sub(r"```[a-zA-Z]*\n(.*?)```", r"\1", text, flags=re.DOTALL)
        # 移除行内代码标记
        text = re.sub(r"`([^`]+)`", r"\1", text)
        # 处理链接：[text](url) -> text
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        # 处理图片：![alt](url) -> [图片: alt]
        text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"[图片: \1]", text)
        # 移除强调标记
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        text = re.sub(r"__([^_]+)__", r"\1", text)
        text = re.sub(r"\*([^*]+)\*", r"\1", text)
        text = re.sub(r"_([^_]+)_", r"\1", text)
        text = re.sub(r"~~([^~]+)~~", r"\1", text)
        # 移除引用标记
        text = re.sub(r"^>\s*", "", text, flags=re.MULTILINE)
        # 移除列表标记
        text = re.sub(r"^[\s]*[-*+]\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"^[\s]*\d+\.\s+", "", text, flags=re.MULTILINE)
        # 移除水平分割线
        text = re.sub(r"^---+$", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\*\*\*+$", "", text, flags=re.MULTILINE)
        # 规整空白
        text = re.sub(r"[^\S\n]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _detect_language(self, text: str) -> str:
        """检测文本语言。"""
        if self.chinese_processor is not None:
            try:
                return self.chinese_processor.detect_language(text)
            except Exception:  # pragma: no cover
                pass
        # 降级：简单统计
        cjk_count = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
        alpha_count = sum(1 for ch in text if ch.isalpha() and not ("\u4e00" <= ch <= "\u9fff"))
        total = cjk_count + alpha_count
        if total == 0:
            return "zh"
        if cjk_count / total > 0.6:
            return "zh"
        elif alpha_count / total > 0.8:
            return "en"
        return "mixed"

    # ===== 章节识别 =====

    def identify_sections(self, text: str) -> List[Section]:
        """识别论文章节结构。

        基于章节标题模式与关键词匹配，识别论文的标准结构章节，
        并构建层次化的章节树。

        Args:
            text: 论文文本。

        Returns:
            顶级章节列表（包含子章节）。
        """
        if not text:
            return []
        # 按行分析
        lines = text.split("\n")
        sections: List[Section] = []
        current_section: Optional[Section] = None
        current_content_lines: List[str] = []
        current_offset = 0
        # 用于构建层次结构
        section_stack: List[Section] = []
        for line_num, line in enumerate(lines):
            line_stripped = line.strip()
            # 尝试匹配章节标题
            title_info = self._match_section_title(line_stripped)
            if title_info:
                # 保存前一个章节的内容
                if current_section is not None:
                    current_section.content = "\n".join(current_content_lines).strip()
                    current_section.end = current_offset
                # 创建新章节
                new_section = Section(
                    section_type=title_info["section_type"],
                    title=title_info["title"],
                    level=title_info["level"],
                    number=title_info["number"],
                    start=current_offset,
                )
                # 构建层次结构
                while section_stack and section_stack[-1].level >= new_section.level:
                    section_stack.pop()
                if section_stack:
                    new_section.parent = section_stack[-1]
                    section_stack[-1].children.append(new_section)
                else:
                    sections.append(new_section)
                section_stack.append(new_section)
                current_section = new_section
                current_content_lines = []
            else:
                # 累积内容
                if current_section is None:
                    # 标题前的内容：创建一个前言章节
                    current_section = Section(
                        section_type="preamble",
                        title="前言",
                        level=1,
                        start=0,
                    )
                    sections.append(current_section)
                    section_stack.append(current_section)
                current_content_lines.append(line)
            current_offset += len(line) + 1  # +1 为换行符
        # 保存最后一个章节的内容
        if current_section is not None:
            current_section.content = "\n".join(current_content_lines).strip()
            current_section.end = current_offset
        # 章节类型推断（若未通过标题匹配）
        for section in sections:
            self._infer_section_type(section)
        return sections

    def _match_section_title(self, line: str) -> Optional[Dict[str, Any]]:
        """匹配章节标题。

        Args:
            line: 待匹配的行文本。

        Returns:
            标题信息字典，包含 section_type、title、level、number。
            若不匹配返回 None。
        """
        if not line or len(line) > 100:  # 标题不应过长
            return None
        # 尝试每种标题模式
        for pattern in SECTION_TITLE_PATTERNS:
            m = pattern.match(line)
            if m:
                # 解析标题信息
                info = self._parse_title_match(m, line)
                if info:
                    return info
        # 基于关键词匹配（无编号的标题）
        section_type = self._match_section_keyword(line)
        if section_type:
            return {
                "section_type": section_type,
                "title": line,
                "level": 1,
                "number": "",
            }
        return None

    def _parse_title_match(self, match: re.Match, line: str) -> Optional[Dict[str, Any]]:
        """解析标题匹配结果。"""
        groups = match.groups()
        # Markdown 标题：## 标题
        if line.startswith("#"):
            level = len(match.group(1))
            title = match.group(2).strip()
            section_type = self._match_section_keyword(title)
            return {
                "section_type": section_type or "unknown",
                "title": title,
                "level": level,
                "number": "",
            }
        # LaTeX 标题
        if line.startswith("\\"):
            title = match.group(1).strip()
            cmd = line.split("{")[0].strip("\\")
            level_map = {
                "chapter": 1, "part": 1, "section": 2,
                "subsection": 3, "subsubsection": 4, "paragraph": 5,
            }
            level = level_map.get(cmd, 2)
            section_type = self._match_section_keyword(title)
            return {
                "section_type": section_type or "unknown",
                "title": title,
                "level": level,
                "number": "",
            }
        # 中文编号：第X章 标题
        if line.startswith("第"):
            title = match.group(1).strip()
            section_type = self._match_section_keyword(title)
            # 推断层级
            if "章" in line or "篇" in line:
                level = 1
            elif "节" in line:
                level = 2
            else:
                level = 3
            return {
                "section_type": section_type or "unknown",
                "title": title,
                "level": level,
                "number": "",
            }
        # 数字编号：1.1 标题
        number_match = re.match(r"^(\d+(?:\.\d+)*)", line)
        if number_match:
            number = number_match.group(1)
            title = line[len(number):].lstrip(".、\\s　").strip()
            level = number.count(".") + 1
            section_type = self._match_section_keyword(title)
            return {
                "section_type": section_type or "unknown",
                "title": title,
                "level": level,
                "number": number,
            }
        return None

    def _match_section_keyword(self, title: str) -> Optional[str]:
        """基于关键词匹配章节类型。

        Args:
            title: 标题文本。

        Returns:
            章节类型字符串，若不匹配返回 None。
        """
        title_lower = title.lower().strip()
        # 精确匹配
        for sec_type, keywords in self.section_keywords.items():
            for kw in keywords:
                if title_lower == kw.lower():
                    return sec_type
        # 包含匹配
        for sec_type, keywords in self.section_keywords.items():
            for kw in keywords:
                if kw.lower() in title_lower and len(kw) >= 2:
                    return sec_type
        return None

    def _infer_section_type(self, section: Section) -> None:
        """推断章节类型（若仍为 unknown）。

        基于章节内容的关键词分布推断类型。

        Args:
            section: 待推断的章节。
        """
        if section.section_type != "unknown":
            # 递归处理子章节
            for child in section.children:
                self._infer_section_type(child)
            return
        content = section.content.lower()
        title = section.title.lower()
        # 基于内容关键词推断
        type_scores: Dict[str, int] = defaultdict(int)
        for sec_type, keywords in self.section_keywords.items():
            for kw in keywords:
                kw_lower = kw.lower()
                if kw_lower in title:
                    type_scores[sec_type] += 3
                if kw_lower in content:
                    type_scores[sec_type] += 1
        if type_scores:
            best_type = max(type_scores.items(), key=lambda x: x[1])
            if best_type[1] >= 3:
                section.section_type = best_type[0]
        # 递归处理子章节
        for child in section.children:
            self._infer_section_type(child)

    # ===== 元数据提取 =====

    def _extract_metadata(self, text: str, structure: DocumentStructure) -> None:
        """提取论文元数据（标题、作者、摘要、关键词）。

        Args:
            text: 论文文本。
            structure: 文档结构（原地修改）。
        """
        # 从章节中提取
        for section in structure.sections:
            if section.section_type == "title" and not structure.title:
                structure.title = section.content.strip().split("\n")[0] if section.content else section.title
            elif section.section_type == "abstract" and not structure.abstract:
                structure.abstract = section.content.strip()
            elif section.section_type == "keywords" and not structure.keywords:
                structure.keywords = self._parse_keywords(section.content)
        # 若未找到，尝试从全文提取
        if not structure.title:
            structure.title = self._extract_title_from_text(text)
        if not structure.abstract:
            structure.abstract = self._extract_abstract_from_text(text)
        if not structure.keywords:
            structure.keywords = self._extract_keywords_from_text(text)
        # 作者提取
        structure.authors = self._extract_authors(text, structure.title)

    def _parse_keywords(self, content: str) -> List[str]:
        """解析关键词内容。

        Args:
            content: 关键词章节内容。

        Returns:
            关键词列表。
        """
        if not content:
            return []
        # 移除"关键词"标签
        content = re.sub(r"^(关键词|关键字|主题词|Keywords|Key\s*words|Index\s*Terms)[:：\s]*",
                         "", content, flags=re.IGNORECASE).strip()
        # 按分号、逗号分隔
        parts = re.split(r"[;；,，、\s]+", content)
        keywords = [p.strip() for p in parts if p.strip() and len(p.strip()) >= 2]
        return keywords[:20]  # 限制最大数量

    def _extract_title_from_text(self, text: str) -> str:
        """从全文提取标题。"""
        lines = text.strip().split("\n")
        # 取第一个非空行
        for line in lines[:10]:
            line = line.strip()
            if line and len(line) <= 200 and not line.startswith("#"):
                # 排除明显的非标题行
                if not re.match(r"^(摘要|Abstract|关键词|Keywords|第[一二三四五六七八九十\d]+[章节])", line, re.IGNORECASE):
                    return line
        return ""

    def _extract_abstract_from_text(self, text: str) -> str:
        """从全文提取摘要。"""
        # 查找"摘要"或"Abstract"标记
        patterns = [
            re.compile(r"(?:摘要|内容提要|提要)[:：\s]*(.+?)(?=关键词|关键字|Keywords|引言|绪论|1\.\s|Introduction|$)", re.DOTALL | re.IGNORECASE),
            re.compile(r"(?:Abstract|Summary)[:：\s]*(.+?)(?=Keywords|Key\s*words|Introduction|1\.\s|$)", re.DOTALL | re.IGNORECASE),
        ]
        for pattern in patterns:
            m = pattern.search(text)
            if m:
                abstract = m.group(1).strip()
                # 清理多余空白
                abstract = re.sub(r"\s+", " ", abstract)
                return abstract[:2000]  # 限制最大长度
        return ""

    def _extract_keywords_from_text(self, text: str) -> List[str]:
        """从全文提取关键词。"""
        patterns = [
            re.compile(r"(?:关键词|关键字|主题词)[:：\s]*([^\n]+)", re.IGNORECASE),
            re.compile(r"(?:Keywords|Key\s*words|Index\s*Terms)[:：\s]*([^\n]+)", re.IGNORECASE),
        ]
        for pattern in patterns:
            m = pattern.search(text)
            if m:
                return self._parse_keywords(m.group(1))
        return []

    def _extract_authors(self, text: str, title: str) -> List[str]:
        """提取作者列表。

        Args:
            text: 论文文本。
            title: 论文标题。

        Returns:
            作者列表。
        """
        authors: List[str] = []
        # 在标题之后查找作者行
        if title:
            title_idx = text.find(title)
            if title_idx >= 0:
                after_title = text[title_idx + len(title):title_idx + len(title) + 500]
                lines = after_title.strip().split("\n")
                for line in lines[:5]:
                    line = line.strip()
                    if not line or line == title:
                        continue
                    # 作者行通常包含逗号分隔的姓名或"作者"标记
                    if re.match(r"^[\u4e00-\u9fffa-zA-Z][\u4e00-\u9fffa-zA-Z\s,，、]+$", line):
                        # 按逗号分隔
                        parts = re.split(r"[,，、;；]", line)
                        for part in parts:
                            part = part.strip()
                            if part and 2 <= len(part) <= 30:
                                authors.append(part)
                        if authors:
                            break
        return authors[:20]

    # ===== 图表提取 =====

    def extract_figures(self, text: str) -> List[Figure]:
        """提取图表标题。

        识别"图 1. xxx"、"Figure 1. xxx"、"表 1. xxx"、"Table 1. xxx"等模式。

        Args:
            text: 论文文本。

        Returns:
            图表信息列表。
        """
        if not text:
            return []
        figures: List[Figure] = []
        lines = text.split("\n")
        offset = 0
        for line in lines:
            line_stripped = line.strip()
            # 匹配图标题
            for pattern in FIGURE_CAPTION_PATTERNS:
                m = pattern.match(line_stripped)
                if m:
                    figures.append(Figure(
                        figure_type="figure",
                        number=m.group(1),
                        caption=m.group(2).strip(),
                        start=offset,
                        end=offset + len(line),
                    ))
                    break
            else:
                # 匹配表标题
                for pattern in TABLE_CAPTION_PATTERNS:
                    m = pattern.match(line_stripped)
                    if m:
                        figures.append(Figure(
                            figure_type="table",
                            number=m.group(1),
                            caption=m.group(2).strip(),
                            start=offset,
                            end=offset + len(line),
                        ))
                        break
            offset += len(line) + 1
        # 检查图表是否在正文中被引用
        for fig in figures:
            ref_patterns = [
                rf"(?:图|Figure|Fig\.?)\s*{re.escape(fig.number)}",
                rf"(?:表|Table|Tab\.?)\s*{re.escape(fig.number)}",
            ]
            for pattern in ref_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    fig.referenced = True
                    break
        return figures

    # ===== 表格解析 =====

    def parse_tables(self, text: str) -> List[Table]:
        """解析表格结构。

        支持 Markdown 表格与简单的文本对齐表格。

        Args:
            text: 论文文本。

        Returns:
            表格信息列表。
        """
        if not text:
            return []
        tables: List[Table] = []
        lines = text.split("\n")
        i = 0
        offset = 0
        offsets = []
        cum_offset = 0
        for line in lines:
            offsets.append(cum_offset)
            cum_offset += len(line) + 1
        while i < len(lines):
            line = lines[i].strip()
            # 检测表格标题
            table_caption: Optional[str] = None
            table_number = ""
            for pattern in TABLE_CAPTION_PATTERNS:
                m = pattern.match(line)
                if m:
                    table_number = m.group(1)
                    table_caption = m.group(2).strip()
                    i += 1
                    break
            # 检测 Markdown 表格
            if i < len(lines) and "|" in lines[i]:
                table_lines: List[str] = []
                table_start = offsets[i] if i < len(offsets) else 0
                while i < len(lines) and "|" in lines[i]:
                    table_lines.append(lines[i].strip())
                    i += 1
                if len(table_lines) >= 2:
                    table = self._parse_markdown_table(table_lines, table_number, table_caption)
                    if table:
                        table.start = table_start
                        table.end = offsets[i - 1] + len(lines[i - 1]) if i > 0 else table_start
                        tables.append(table)
                    continue
            i += 1
        return tables

    def _parse_markdown_table(
        self,
        table_lines: List[str],
        number: str,
        caption: Optional[str],
    ) -> Optional[Table]:
        """解析 Markdown 表格。

        Args:
            table_lines: 表格行文本列表。
            number: 表格编号。
            caption: 表格标题。

        Returns:
            表格信息对象。
        """
        if len(table_lines) < 2:
            return None
        # 解析表头
        headers = self._parse_table_row(table_lines[0])
        if not headers:
            return None
        # 跳过分隔行（第二行通常是 |---|---|）
        data_start = 1
        if len(table_lines) > 1 and re.match(r"^\|?[\s\-:|]+\|?$", table_lines[1]):
            data_start = 2
        # 解析数据行
        rows: List[List[str]] = []
        for line in table_lines[data_start:]:
            row = self._parse_table_row(line)
            if row:
                rows.append(row)
        if not headers and not rows:
            return None
        return Table(
            number=number,
            caption=caption or "",
            headers=headers,
            rows=rows,
            row_count=len(rows),
            col_count=max(len(headers), max((len(r) for r in rows), default=0)),
        )

    def _parse_table_row(self, line: str) -> List[str]:
        """解析表格行。

        Args:
            line: 表格行文本。

        Returns:
            单元格列表。
        """
        # 移除首尾的 |
        line = line.strip()
        if line.startswith("|"):
            line = line[1:]
        if line.endswith("|"):
            line = line[:-1]
        # 按 | 分隔
        cells = [c.strip() for c in line.split("|")]
        # 过滤空行（分隔行）
        if all(re.match(r"^[\s\-:]+$", c) for c in cells if c):
            return []
        return cells

    # ===== 公式提取 =====

    def extract_formulas(self, text: str) -> List[Formula]:
        """提取公式。

        识别 LaTeX 公式（$...$、$$...$$、\\(...\\)、\\[...\\]）与 equation 环境。

        Args:
            text: 论文文本。

        Returns:
            公式信息列表。
        """
        if not text:
            return []
        formulas: List[Formula] = []
        for pattern, ftype in [
            (re.compile(r"\$\$([^$]+)\$\$", re.DOTALL), "block"),
            (re.compile(r"\$([^$\n]+)\$"), "inline"),
            (re.compile(r"\\\(([^)]+)\\\)"), "inline"),
            (re.compile(r"\\\[([^\]]+)\\\]"), "block"),
            (re.compile(r"\\begin\{equation\}(.*?)\\end\{equation\}", re.DOTALL), "block"),
            (re.compile(r"\\begin\{align\}(.*?)\\end\{align\}", re.DOTALL), "block"),
        ]:
            for m in pattern.finditer(text):
                formula_text = m.group(0)
                inner = m.group(1).strip() if m.groups() else ""
                # 尝试提取公式编号
                number = ""
                num_match = re.search(r"\\tag\{([^}]+)\}", inner)
                if num_match:
                    number = num_match.group(1)
                # 尝试提取公式编号（如 (1)）
                num_match2 = re.search(r"\((\d+(?:\.\d+)*)\)\s*$", formula_text)
                if num_match2:
                    number = num_match2.group(1)
                formulas.append(Formula(
                    text=formula_text,
                    formula_type=ftype,
                    number=number,
                    start=m.start(),
                    end=m.end(),
                ))
        # 去重（嵌套匹配）
        formulas.sort(key=lambda f: (f.start, -(f.end - f.start)))
        unique: List[Formula] = []
        for f in formulas:
            if not any(u.start <= f.start < u.end for u in unique):
                unique.append(f)
        return unique

    # ===== 参考文献解析 =====

    def parse_references(self, text: str) -> List[Reference]:
        """解析参考文献列表。

        识别参考文献章节，并解析每条参考文献的结构化信息。

        Args:
            text: 论文文本。

        Returns:
            参考文献列表。
        """
        if not text:
            return []
        # 定位参考文献章节
        ref_section = self._find_reference_section(text)
        if not ref_section:
            return []
        ref_text = ref_section
        # 按行解析参考文献条目
        references: List[Reference] = []
        lines = ref_text.split("\n")
        current_ref: Optional[Reference] = None
        current_lines: List[str] = []
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue
            # 检测新条目
            ref_match = re.match(r"^\[(\d+)\]\s*(.+)$", line_stripped)
            if ref_match:
                # 保存前一条
                if current_ref is not None:
                    current_ref.raw_text = " ".join(current_lines).strip()
                    self._parse_reference_details(current_ref)
                    references.append(current_ref)
                current_ref = Reference(
                    number=ref_match.group(1),
                    raw_text=ref_match.group(2),
                )
                current_lines = [ref_match.group(2)]
            elif re.match(r"^\d+[.\s]\s*\S", line_stripped):
                # 无括号编号：1. xxx
                if current_ref is not None:
                    current_ref.raw_text = " ".join(current_lines).strip()
                    self._parse_reference_details(current_ref)
                    references.append(current_ref)
                num_match = re.match(r"^(\d+)[.\s]\s*(.+)$", line_stripped)
                if num_match:
                    current_ref = Reference(
                        number=num_match.group(1),
                        raw_text=num_match.group(2),
                    )
                    current_lines = [num_match.group(2)]
            else:
                # 续行
                if current_ref is not None:
                    current_lines.append(line_stripped)
        # 保存最后一条
        if current_ref is not None:
            current_ref.raw_text = " ".join(current_lines).strip()
            self._parse_reference_details(current_ref)
            references.append(current_ref)
        return references

    def _find_reference_section(self, text: str) -> Optional[str]:
        """定位参考文献章节。

        Args:
            text: 论文文本。

        Returns:
            参考文献章节文本。
        """
        # 查找"参考文献"标记
        patterns = [
            re.compile(r"(?:参考文献|引用文献|参考资料|References|Bibliography)\s*\n(.+)$", re.DOTALL | re.IGNORECASE),
            re.compile(r"(?:参考文献|引用文献|参考资料|References|Bibliography)[:：\s]*\n(.+)$", re.DOTALL | re.IGNORECASE),
        ]
        for pattern in patterns:
            m = pattern.search(text)
            if m:
                ref_text = m.group(1)
                # 截断到下一个主要章节
                next_section = re.search(
                    r"\n(?:附录|致谢|作者简介|Appendix|Acknowledgment|About\s+the\s+Author)",
                    ref_text, re.IGNORECASE,
                )
                if next_section:
                    ref_text = ref_text[:next_section.start()]
                return ref_text
        return None

    def _parse_reference_details(self, ref: Reference) -> None:
        """解析参考文献的详细信息。

        从原始文本中提取作者、标题、期刊、年份等结构化信息。

        Args:
            ref: 参考文献对象（原地修改）。
        """
        text = ref.raw_text
        if not text:
            return
        # 提取年份
        year_match = re.search(r"\b(19|20)\d{2}\b", text)
        if year_match:
            ref.year = year_match.group(0)
        # 提取 DOI
        doi_match = re.search(r"(?:doi|DOI)[:：\s]*(10\.\d+/[^\s]+)", text)
        if doi_match:
            ref.doi = doi_match.group(1).rstrip(".")
        # 提取 URL
        url_match = re.search(r"https?://[^\s)]+", text)
        if url_match:
            ref.url = url_match.group(0).rstrip(".")
        # 提取页码
        pages_match = re.search(r"(?:pp?\.?\s*)(\d+\s*[-–—]\s*\d+)", text)
        if pages_match:
            ref.pages = pages_match.group(1).replace("–", "-").replace("—", "-")
        # 提取卷号与期号
        vol_match = re.search(r"(?:vol\.?|volume)?\s*(\d+)\s*(?:\((\d+)\))?", text, re.IGNORECASE)
        if vol_match:
            ref.volume = vol_match.group(1)
            if vol_match.group(2):
                ref.issue = vol_match.group(2)
        # 判断文献类型
        ref.ref_type = self._classify_reference(text)
        # 提取作者与标题（简化）
        self._extract_authors_and_title(ref)

    def _classify_reference(self, text: str) -> str:
        """分类参考文献类型。

        Args:
            text: 参考文献文本。

        Returns:
            类型字符串（journal/conference/book/thesis/web/technical_report/unknown）。
        """
        text_lower = text.lower()
        # 会议论文
        conf_keywords = ["proceedings", "conference", "symposium", "workshop", "meeting", "会议", "论文集"]
        if any(kw in text_lower for kw in conf_keywords):
            return "conference"
        # 期刊论文
        journal_keywords = ["journal", "transactions", "letters", "review", "magazine", "学报", "期刊"]
        if any(kw in text_lower for kw in journal_keywords):
            return "journal"
        # 学位论文
        thesis_keywords = ["ph.d", "phd", "master", "thesis", "dissertation", "学位论文", "博士论文", "硕士论文"]
        if any(kw in text_lower for kw in thesis_keywords):
            return "thesis"
        # 书籍
        book_keywords = ["press", "publisher", "publishing", "出版社", "著", "编"]
        if any(kw in text_lower for kw in book_keywords):
            return "book"
        # 技术报告
        report_keywords = ["technical report", "tech report", "技术报告"]
        if any(kw in text_lower for kw in report_keywords):
            return "technical_report"
        # 网页
        if "http" in text_lower or "www" in text_lower:
            return "web"
        return "unknown"

    def _extract_authors_and_title(self, ref: Reference) -> None:
        """提取作者与标题（简化版）。

        Args:
            ref: 参考文献对象（原地修改）。
        """
        text = ref.raw_text
        if not text:
            return
        # 按句号分割
        parts = [p.strip() for p in text.split(".") if p.strip()]
        if not parts:
            return
        # 第一部分通常是作者
        if parts[0] and len(parts[0]) < 200:
            # 按逗号分隔作者
            author_str = parts[0]
            # 处理 "Smith, J., Brown, K." 格式
            if "," in author_str:
                # 简化：按逗号分割，每两个为一组
                tokens = [t.strip() for t in author_str.split(",")]
                authors: List[str] = []
                i = 0
                while i < len(tokens):
                    if i + 1 < len(tokens) and len(tokens[i]) <= 20 and len(tokens[i + 1]) <= 5:
                        authors.append(f"{tokens[i]}, {tokens[i + 1]}")
                        i += 2
                    else:
                        authors.append(tokens[i])
                        i += 1
                ref.authors = authors[:10]
            else:
                ref.authors = [author_str]
        # 第二部分通常是标题
        if len(parts) > 1 and parts[1] and len(parts[1]) >= 10:
            ref.title = parts[1].strip()
        # 第三部分通常是期刊/会议
        if len(parts) > 2 and parts[2] and len(parts[2]) >= 5:
            ref.venue = parts[2].strip()

    # ===== 引用标记识别 =====

    def identify_citations(self, text: str) -> List[Citation]:
        """识别引用标记。

        识别数字引用（[1]）、作者-年份引用（Smith, 2020）、中文引用（张三，2020）。

        Args:
            text: 论文文本。

        Returns:
            引用标记列表。
        """
        if not text:
            return []
        citations: List[Citation] = []
        for pattern, ctype in [
            (CITATION_PATTERNS[0], "numeric"),
            (CITATION_PATTERNS[1], "author_year"),
            (CITATION_PATTERNS[2], "author_year"),
            (CITATION_PATTERNS[3], "chinese"),
            (CITATION_PATTERNS[4], "chinese"),
            (CITATION_PATTERNS[5], "alpha_numeric"),
        ]:
            for m in pattern.finditer(text):
                ref_ids = self._parse_citation_ref_ids(m.group(), ctype)
                citations.append(Citation(
                    text=m.group(),
                    citation_type=ctype,
                    start=m.start(),
                    end=m.end(),
                    ref_ids=ref_ids,
                ))
        # 去重与排序
        citations.sort(key=lambda c: c.start)
        # 合并重叠的引用
        unique: List[Citation] = []
        for c in citations:
            if not unique or c.start >= unique[-1].end:
                unique.append(c)
            else:
                # 保留较长的
                if c.end - c.start > unique[-1].end - unique[-1].start:
                    unique[-1] = c
        return unique

    def _parse_citation_ref_ids(self, citation_text: str, ctype: str) -> List[str]:
        """解析引用标记中的参考文献编号。

        Args:
            citation_text: 引用文本。
            ctype: 引用类型。

        Returns:
            参考文献编号列表。
        """
        try:
            if ctype == "numeric":
                # [1] / [1,2,3] / [1-3]
                inner = citation_text.strip("[]").replace(" ", "")
                ids: List[str] = []
                for part in inner.split(","):
                    part = part.strip()
                    if "-" in part:
                        # 范围：1-3 -> 1,2,3
                        range_match = re.match(r"^(\d+)-(\d+)$", part)
                        if range_match:
                            start = int(range_match.group(1))
                            end = int(range_match.group(2))
                            ids.extend(str(i) for i in range(start, end + 1))
                    elif part.isdigit():
                        ids.append(part)
                return ids
            elif ctype == "author_year":
                # (Smith, 2020) -> Smith:2020
                m = re.match(r"\(\s*([A-Z][a-zA-Z]+).*?,\s*(\d{4})\s*\)", citation_text)
                if m:
                    return [f"{m.group(1)}:{m.group(2)}"]
            elif ctype == "chinese":
                # 张三（2020） -> 张三:2020
                m = re.match(r"([\u4e00-\u9fff]{2,4})等?（(\d{4})）", citation_text)
                if m:
                    return [f"{m.group(1)}:{m.group(2)}"]
            elif ctype == "alpha_numeric":
                # [Smith2020] -> Smith2020
                inner = citation_text.strip("[]").strip()
                return [inner]
        except Exception:  # pragma: no cover
            pass
        return []

    # ===== 引用-参考文献匹配 =====

    def _match_citations_with_references(self, structure: DocumentStructure) -> None:
        """匹配引用标记与参考文献。

        Args:
            structure: 文档结构（原地修改 citations 的 matched 字段）。
        """
        # 构建参考文献索引
        ref_by_number: Dict[str, Reference] = {r.number: r for r in structure.references if r.number}
        ref_by_author_year: Dict[str, Reference] = {}
        for ref in structure.references:
            if ref.year and ref.authors:
                # 取第一作者姓
                first_author = ref.authors[0]
                # 提取姓
                if "," in first_author:
                    surname = first_author.split(",")[0].strip()
                else:
                    surname = first_author.split()[0] if first_author.split() else first_author
                key = f"{surname}:{ref.year}"
                ref_by_author_year[key] = ref
        # 匹配引用
        for citation in structure.citations:
            citation.matched = False
            for ref_id in citation.ref_ids:
                if ref_id in ref_by_number:
                    citation.matched = True
                    break
                if ref_id in ref_by_author_year:
                    citation.matched = True
                    break

    # ===== 目录生成 =====

    def generate_table_of_contents(
        self,
        sections: List[Section],
        max_level: int = 3,
    ) -> List[Dict[str, Any]]:
        """生成目录。

        Args:
            sections: 章节列表。
            max_level: 最大显示层级。

        Returns:
            目录条目列表，每个条目包含 number、title、level、type。
        """
        toc: List[Dict[str, Any]] = []

        def walk(section: Section, level: int) -> None:
            if level > max_level:
                return
            toc.append({
                "number": section.number,
                "title": section.title or SECTION_TYPE_NAMES.get(section.section_type, ""),
                "level": level,
                "type": section.section_type,
                "type_name": SECTION_TYPE_NAMES.get(section.section_type, "未知"),
                "start": section.start,
                "end": section.end,
            })
            for child in section.children:
                walk(child, level + 1)

        for section in sections:
            walk(section, 1)
        return toc

    # ===== 页码识别 =====

    def identify_page_numbers(self, text: str) -> List[Dict[str, Any]]:
        """识别页码标记。

        Args:
            text: 论文文本。

        Returns:
            页码信息列表，每个条目包含 page、start、end。
        """
        if not text:
            return []
        pages: List[Dict[str, Any]] = []
        lines = text.split("\n")
        offset = 0
        for line in lines:
            line_stripped = line.strip()
            for pattern in PAGE_NUMBER_PATTERNS:
                if pattern.match(line_stripped):
                    # 提取页码数字
                    num_match = re.search(r"\d+", line_stripped)
                    if num_match:
                        pages.append({
                            "page": int(num_match.group(0)),
                            "start": offset,
                            "end": offset + len(line),
                            "text": line_stripped,
                        })
                    break
            offset += len(line) + 1
        return pages

    # ===== 章节内容提取 =====

    def get_section_by_type(
        self,
        structure: DocumentStructure,
        section_type: str,
    ) -> Optional[Section]:
        """按类型获取章节。

        Args:
            structure: 文档结构。
            section_type: 章节类型。

        Returns:
            章节对象，若不存在返回 None。
        """
        def search(sections: List[Section]) -> Optional[Section]:
            for section in sections:
                if section.section_type == section_type:
                    return section
                result = search(section.children)
                if result:
                    return result
            return None
        return search(structure.sections)

    def get_section_content(
        self,
        structure: DocumentStructure,
        section_type: str,
    ) -> str:
        """获取指定类型章节的内容。

        Args:
            structure: 文档结构。
            section_type: 章节类型。

        Returns:
            章节内容文本，若不存在返回空字符串。
        """
        section = self.get_section_by_type(structure, section_type)
        return section.content if section else ""

    # ===== 批量解析 =====

    def batch_parse(
        self,
        texts: List[str],
        format: str = "text",
    ) -> List[DocumentStructure]:
        """批量解析论文。

        Args:
            texts: 论文文本列表。
            format: 输入格式。

        Returns:
            文档结构列表。
        """
        return [self.parse(t, format=format) for t in texts]

    # ===== 完整性检查 =====

    def check_completeness(self, structure: DocumentStructure) -> Dict[str, Any]:
        """检查论文结构完整性。

        Args:
            structure: 文档结构。

        Returns:
            完整性报告字典，包含缺失的章节、警告等。
        """
        required_sections = ["title", "abstract", "keywords", "introduction",
                             "method", "result", "conclusion", "references"]
        found_sections = {s.section_type for s in structure.sections}
        # 递归收集所有章节类型
        def collect_types(sections: List[Section], types: Set[str]) -> None:
            for s in sections:
                types.add(s.section_type)
                collect_types(s.children, types)
        collect_types(structure.sections, found_sections)
        # 检查缺失
        missing = [s for s in required_sections if s not in found_sections]
        # 警告
        warnings: List[str] = []
        if not structure.title:
            warnings.append("未找到论文标题")
        if not structure.abstract:
            warnings.append("未找到摘要")
        if not structure.keywords:
            warnings.append("未找到关键词")
        if not structure.references:
            warnings.append("未找到参考文献")
        # 引用匹配率
        if structure.citations:
            matched = sum(1 for c in structure.citations if c.matched)
            match_rate = matched / len(structure.citations)
            if match_rate < 0.5:
                warnings.append(f"引用匹配率较低：{match_rate:.1%}")
        else:
            if structure.references:
                warnings.append("正文未检测到引用标记")
        return {
            "complete": len(missing) == 0,
            "missing_sections": missing,
            "found_sections": list(found_sections),
            "warnings": warnings,
            "section_count": len(structure.sections),
            "reference_count": len(structure.references),
            "citation_count": len(structure.citations),
            "figure_count": len(structure.figures),
            "table_count": len(structure.tables),
            "formula_count": len(structure.formulas),
        }

    # ===== 摘要质量评估 =====

    def evaluate_abstract(self, abstract: str) -> Dict[str, Any]:
        """评估摘要质量。

        Args:
            abstract: 摘要文本。

        Returns:
            质量评估字典，包含长度、句子数、关键词覆盖等。
        """
        if not abstract:
            return {
                "length": 0, "sentence_count": 0, "avg_sentence_length": 0,
                "has_background": False, "has_method": False,
                "has_result": False, "has_conclusion": False,
                "score": 0.0, "issues": ["摘要为空"],
            }
        # 基本统计
        length = len(abstract)
        # 句子分割
        if self.chinese_processor is not None:
            sentences = self.chinese_processor.split_sentences(abstract)
        else:
            sentences = [s for s in re.split(r"[。！？!?；;\n]", abstract) if s.strip()]
        sentence_count = len(sentences)
        avg_sent_len = length / sentence_count if sentence_count > 0 else 0
        # 结构要素检测
        abstract_lower = abstract.lower()
        has_background = any(kw in abstract_lower for kw in
                             ["背景", "近年来", "目前", "现有", "传统", "background", "recently", "currently"])
        has_method = any(kw in abstract_lower for kw in
                         ["方法", "提出", "采用", "设计", "实现", "method", "propose", "approach", "design"])
        has_result = any(kw in abstract_lower for kw in
                         ["结果", "表明", "显示", "实验", "性能", "result", "show", "demonstrate", "experiment"])
        has_conclusion = any(kw in abstract_lower for kw in
                             ["结论", "意义", "应用", "展望", "conclusion", "significance", "future"])
        # 评分
        score = 0.0
        issues: List[str] = []
        if length < 100:
            issues.append("摘要过短（建议 200-500 字）")
            score += 0.2
        elif length > 1000:
            issues.append("摘要过长（建议 200-500 字）")
            score += 0.5
        else:
            score += 0.3
        if sentence_count < 3:
            issues.append("摘要句子过少（建议 3-8 句）")
            score += 0.1
        else:
            score += 0.2
        if has_background:
            score += 0.1
        else:
            issues.append("缺少研究背景")
        if has_method:
            score += 0.15
        else:
            issues.append("缺少方法描述")
        if has_result:
            score += 0.15
        else:
            issues.append("缺少结果说明")
        if has_conclusion:
            score += 0.1
        else:
            issues.append("缺少结论陈述")
        return {
            "length": length,
            "sentence_count": sentence_count,
            "avg_sentence_length": round(avg_sent_len, 2),
            "has_background": has_background,
            "has_method": has_method,
            "has_result": has_result,
            "has_conclusion": has_conclusion,
            "score": round(min(1.0, score), 2),
            "issues": issues,
        }


# ===== 模块级单例访问 =====

def get_academic_parser() -> AcademicParser:
    """获取全局学术解析器单例。"""
    return AcademicParser.get_instance()


def parse_paper(text: str, format: str = "text") -> DocumentStructure:
    """模块级论文解析便捷函数。"""
    return get_academic_parser().parse(text, format=format)


def identify_sections(text: str) -> List[Section]:
    """模块级章节识别便捷函数。"""
    return get_academic_parser().identify_sections(text)


def parse_references(text: str) -> List[Reference]:
    """模块级参考文献解析便捷函数。"""
    return get_academic_parser().parse_references(text)
