"""文档导出器模块

提供多种格式的文档导出能力，包括：
    - Markdown 导出（含表格、代码块、引用）
    - HTML 导出（含 CSS 样式、目录、元数据）
    - PDF 导出（简化实现，基于 HTML 转换思路）
    - Word 导出（python-docx 风格 API 模拟，生成 OOXML）
    - LaTeX 导出（学术文档标准格式）
    - 纯文本导出
    - 模板系统（支持自定义模板与样式配置）
    - 元数据嵌入
    - 批量导出与压缩打包
    - 进度回调

仅使用 Python 标准库实现，无外部依赖。
Word 导出生成符合 OOXML 规范的 .docx 文件（ZIP 包）。

典型用法：
    exporter = DocumentExporter()
    content = exporter.export_markdown(document, template="academic")
    exporter.export_to_file(document, "output.docx", format="docx")
"""
from __future__ import annotations

import io
import json
import os
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from html import escape as html_escape
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Union
from xml.sax.saxutils import escape as xml_escape

# 尝试导入日志
try:
    from backend.utils.logger import get_logger

    _logger = get_logger(__name__)
except Exception:  # pragma: no cover
    import logging

    _logger = logging.getLogger(__name__)


# ===== 枚举与常量 =====


class ExportFormat(str, Enum):
    """导出格式枚举。"""

    MARKDOWN = "markdown"
    HTML = "html"
    PDF = "pdf"
    DOCX = "docx"
    LATEX = "latex"
    TEXT = "text"
    JSON = "json"


# 默认 CSS 样式
DEFAULT_CSS = """
body {
    font-family: "SimSun", "Times New Roman", serif;
    font-size: 12pt;
    line-height: 1.8;
    margin: 2.5cm;
    color: #000;
}
h1 {
    font-size: 18pt;
    text-align: center;
    margin-top: 24pt;
    margin-bottom: 12pt;
    font-family: "SimHei", "Arial Black", sans-serif;
}
h2 {
    font-size: 16pt;
    margin-top: 18pt;
    margin-bottom: 8pt;
    font-family: "SimHei", "Arial Black", sans-serif;
}
h3 {
    font-size: 14pt;
    margin-top: 14pt;
    margin-bottom: 6pt;
    font-family: "SimHei", "Arial Black", sans-serif;
}
h4 {
    font-size: 12pt;
    margin-top: 12pt;
    margin-bottom: 4pt;
    font-family: "SimHei", "Arial Black", sans-serif;
}
p {
    text-indent: 2em;
    margin: 6pt 0;
}
.abstract p, .keywords p {
    text-indent: 2em;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin: 12pt 0;
    font-size: 10.5pt;
}
th, td {
    border: 1px solid #000;
    padding: 4pt 8pt;
    text-align: left;
}
th {
    background-color: #f0f0f0;
    font-weight: bold;
}
code {
    font-family: "Consolas", "Courier New", monospace;
    background-color: #f5f5f5;
    padding: 2pt 4pt;
    border-radius: 2pt;
}
pre {
    background-color: #f5f5f5;
    padding: 8pt;
    border: 1px solid #ddd;
    border-radius: 4pt;
    overflow-x: auto;
}
pre code {
    background: none;
    padding: 0;
}
blockquote {
    border-left: 4pt solid #ccc;
    margin: 12pt 0;
    padding: 6pt 12pt;
    color: #555;
    background-color: #f9f9f9;
}
.figure {
    text-align: center;
    margin: 12pt 0;
}
.figure-caption {
    font-size: 10.5pt;
    color: #555;
    margin-top: 4pt;
}
.formula {
    text-align: center;
    margin: 12pt 0;
    font-family: "Times New Roman", serif;
    font-style: italic;
}
.references p {
    text-indent: -2em;
    padding-left: 2em;
    font-size: 10.5pt;
}
.metadata {
    font-size: 10pt;
    color: #666;
    margin-bottom: 12pt;
    border-bottom: 1px solid #ccc;
    padding-bottom: 6pt;
}
.toc {
    margin: 12pt 0;
}
.toc ul {
    list-style: none;
    padding-left: 0;
}
.toc li {
    margin: 4pt 0;
}
.toc a {
    text-decoration: none;
    color: #000;
}
"""


# 默认 LaTeX 模板
DEFAULT_LATEX_TEMPLATE = r"""\documentclass[12pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage{ctex}
\usepackage{geometry}
\usepackage{hyperref}
\usepackage{graphicx}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{cite}
\geometry{left=2.5cm,right=2.5cm,top=2.5cm,bottom=2.5cm}

\title{__TITLE__}
\author{__AUTHOR__}
\date{__DATE__}

\begin{document}
\maketitle

__CONTENT__

\bibliographystyle{plain}
\bibliography{references}

\end{document}
"""


@dataclass
class DocumentSection:
    """文档章节。"""

    title: str = ""
    level: int = 1  # 1=H1, 2=H2, ...
    content: str = ""
    subsections: List["DocumentSection"] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "level": self.level,
            "content": self.content,
            "subsections": [s.to_dict() for s in self.subsections],
            "metadata": self.metadata,
        }


@dataclass
class DocumentTable:
    """文档表格。"""

    headers: List[str] = field(default_factory=list)
    rows: List[List[str]] = field(default_factory=list)
    caption: str = ""
    style: str = "default"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "headers": self.headers,
            "rows": self.rows,
            "caption": self.caption,
            "style": self.style,
        }


@dataclass
class DocumentFigure:
    """文档图片。"""

    caption: str = ""
    image_path: str = ""
    width: str = "100%"
    alt_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "caption": self.caption,
            "image_path": self.image_path,
            "width": self.width,
            "alt_text": self.alt_text,
        }


@dataclass
class DocumentReference:
    """文档引用条目。"""

    ref_id: str = ""
    text: str = ""
    ref_type: str = ""  # journal / conference / book / thesis / web

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ref_id": self.ref_id,
            "text": self.text,
            "ref_type": self.ref_type,
        }


@dataclass
class Document:
    """文档数据结构。"""

    title: str = ""
    author: str = ""
    date: str = ""
    abstract: str = ""
    keywords: List[str] = field(default_factory=list)
    sections: List[DocumentSection] = field(default_factory=list)
    tables: List[DocumentTable] = field(default_factory=list)
    figures: List[DocumentFigure] = field(default_factory=list)
    references: List[DocumentReference] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "author": self.author,
            "date": self.date,
            "abstract": self.abstract,
            "keywords": self.keywords,
            "sections": [s.to_dict() for s in self.sections],
            "tables": [t.to_dict() for t in self.tables],
            "figures": [f.to_dict() for f in self.figures],
            "references": [r.to_dict() for r in self.references],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Document":
        """从字典构建文档。"""
        doc = cls(
            title=data.get("title", ""),
            author=data.get("author", ""),
            date=data.get("date", ""),
            abstract=data.get("abstract", ""),
            keywords=data.get("keywords", []),
            metadata=data.get("metadata", {}),
        )
        for section_data in data.get("sections", []):
            doc.sections.append(_section_from_dict(section_data))
        for table_data in data.get("tables", []):
            doc.tables.append(DocumentTable(**table_data))
        for fig_data in data.get("figures", []):
            doc.figures.append(DocumentFigure(**fig_data))
        for ref_data in data.get("references", []):
            doc.references.append(DocumentReference(**ref_data))
        return doc


def _section_from_dict(data: Dict[str, Any]) -> DocumentSection:
    """从字典构建章节。"""
    section = DocumentSection(
        title=data.get("title", ""),
        level=data.get("level", 1),
        content=data.get("content", ""),
        metadata=data.get("metadata", {}),
    )
    for sub_data in data.get("subsections", []):
        section.subsections.append(_section_from_dict(sub_data))
    return section


@dataclass
class ExportOptions:
    """导出选项。"""

    include_toc: bool = True
    include_metadata: bool = True
    include_references: bool = True
    include_figures: bool = True
    include_tables: bool = True
    css_style: str = DEFAULT_CSS
    template: str = "academic"
    encoding: str = "utf-8"
    page_size: str = "A4"
    margin: str = "2.5cm"
    font_family: str = "SimSun"
    font_size: str = "12pt"
    line_spacing: float = 1.8


@dataclass
class ExportResult:
    """导出结果。"""

    format: str
    content: str = ""
    file_path: str = ""
    file_size: int = 0
    success: bool = True
    error_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "format": self.format,
            "content_length": len(self.content),
            "file_path": self.file_path,
            "file_size": self.file_size,
            "success": self.success,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


# ===== 渲染器基类 =====


class BaseRenderer:
    """渲染器基类。"""

    def __init__(self, options: Optional[ExportOptions] = None):
        """初始化渲染器。"""
        self.options = options or ExportOptions()

    def render(self, document: Document) -> str:
        """渲染文档。"""
        raise NotImplementedError

    def render_section(self, section: DocumentSection, level: int = 1) -> str:
        """渲染章节。"""
        raise NotImplementedError

    def render_table(self, table: DocumentTable) -> str:
        """渲染表格。"""
        raise NotImplementedError

    def render_figure(self, figure: DocumentFigure) -> str:
        """渲染图片。"""
        raise NotImplementedError

    def render_references(self, references: List[DocumentReference]) -> str:
        """渲染参考文献。"""
        raise NotImplementedError


# ===== Markdown 渲染器 =====


class MarkdownRenderer(BaseRenderer):
    """Markdown 渲染器。"""

    def render(self, document: Document) -> str:
        """渲染完整文档为 Markdown。"""
        lines: List[str] = []
        # 标题
        if document.title:
            lines.append(f"# {document.title}")
            lines.append("")
        # 元数据
        if self.options.include_metadata and (document.author or document.date):
            meta_parts = []
            if document.author:
                meta_parts.append(f"**作者**: {document.author}")
            if document.date:
                meta_parts.append(f"**日期**: {document.date}")
            lines.append(" | ".join(meta_parts))
            lines.append("")
        # 摘要
        if document.abstract:
            lines.append("## 摘要")
            lines.append("")
            lines.append(document.abstract)
            lines.append("")
        # 关键词
        if document.keywords:
            lines.append(f"**关键词**: {'；'.join(document.keywords)}")
            lines.append("")
        # 目录
        if self.options.include_toc and document.sections:
            lines.append("## 目录")
            lines.append("")
            self._render_toc(document.sections, lines, level=1)
            lines.append("")
        # 章节
        for section in document.sections:
            lines.append(self.render_section(section, level=1))
        # 表格
        if self.options.include_tables and document.tables:
            lines.append("")
            for table in document.tables:
                lines.append(self.render_table(table))
                lines.append("")
        # 图片
        if self.options.include_figures and document.figures:
            lines.append("")
            for figure in document.figures:
                lines.append(self.render_figure(figure))
                lines.append("")
        # 参考文献
        if self.options.include_references and document.references:
            lines.append("## 参考文献")
            lines.append("")
            lines.append(self.render_references(document.references))
        return "\n".join(lines)

    def _render_toc(
        self,
        sections: List[DocumentSection],
        lines: List[str],
        level: int,
    ) -> None:
        """渲染目录。"""
        for section in sections:
            indent = "  " * (level - 1)
            anchor = self._make_anchor(section.title)
            lines.append(f"{indent}- [{section.title}](#{anchor})")
            if section.subsections:
                self._render_toc(section.subsections, lines, level + 1)

    def _make_anchor(self, title: str) -> str:
        """生成锚点。"""
        return title.lower().replace(" ", "-").replace("　", "-")

    def render_section(self, section: DocumentSection, level: int = 1) -> str:
        """渲染章节。"""
        lines: List[str] = []
        heading = "#" * min(level + 1, 6)
        lines.append(f"{heading} {section.title}")
        lines.append("")
        if section.content:
            lines.append(section.content)
            lines.append("")
        for subsection in section.subsections:
            lines.append(self.render_section(subsection, level + 1))
        return "\n".join(lines)

    def render_table(self, table: DocumentTable) -> str:
        """渲染表格。"""
        if not table.headers:
            return ""
        lines: List[str] = []
        if table.caption:
            lines.append(f"**{table.caption}**")
            lines.append("")
        # 表头
        lines.append("| " + " | ".join(table.headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(table.headers)) + " |")
        # 数据行
        for row in table.rows:
            # 补齐列数
            while len(row) < len(table.headers):
                row.append("")
            lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
        return "\n".join(lines)

    def render_figure(self, figure: DocumentFigure) -> str:
        """渲染图片。"""
        alt = figure.alt_text or figure.caption
        if figure.image_path:
            line = f"![{alt}]({figure.image_path})"
        else:
            line = f"_[图片: {alt}]_"
        if figure.caption:
            line += f"\n\n*图：{figure.caption}*"
        return line

    def render_references(self, references: List[DocumentReference]) -> str:
        """渲染参考文献。"""
        lines: List[str] = []
        for i, ref in enumerate(references, 1):
            ref_id = ref.ref_id or str(i)
            lines.append(f"[{ref_id}] {ref.text}")
        return "\n".join(lines)


# ===== HTML 渲染器 =====


class HTMLRenderer(BaseRenderer):
    """HTML 渲染器。"""

    def render(self, document: Document) -> str:
        """渲染完整文档为 HTML。"""
        parts: List[str] = []
        # HTML 头部
        parts.append("<!DOCTYPE html>")
        parts.append('<html lang="zh-CN">')
        parts.append("<head>")
        parts.append('<meta charset="utf-8">')
        parts.append(f'<title>{html_escape(document.title)}</title>')
        if self.options.include_metadata:
            parts.append('<meta name="author" content="{}">'.format(html_escape(document.author)))
            parts.append('<meta name="date" content="{}">'.format(html_escape(document.date)))
            parts.append('<meta name="generator" content="ThesisMiner v8.0">')
        parts.append("<style>")
        parts.append(self.options.css_style)
        parts.append("</style>")
        parts.append("</head>")
        parts.append("<body>")
        # 标题
        if document.title:
            parts.append(f"<h1>{html_escape(document.title)}</h1>")
        # 元数据
        if self.options.include_metadata and (document.author or document.date):
            parts.append('<div class="metadata">')
            if document.author:
                parts.append(f"<p><strong>作者</strong>: {html_escape(document.author)}</p>")
            if document.date:
                parts.append(f"<p><strong>日期</strong>: {html_escape(document.date)}</p>")
            parts.append("</div>")
        # 摘要
        if document.abstract:
            parts.append('<div class="abstract">')
            parts.append("<h2>摘要</h2>")
            parts.append(f"<p>{html_escape(document.abstract)}</p>")
            parts.append("</div>")
        # 关键词
        if document.keywords:
            parts.append('<div class="keywords">')
            parts.append(f"<p><strong>关键词</strong>: {html_escape('；'.join(document.keywords))}</p>")
            parts.append("</div>")
        # 目录
        if self.options.include_toc and document.sections:
            parts.append('<div class="toc">')
            parts.append("<h2>目录</h2>")
            parts.append("<ul>")
            self._render_toc_html(document.sections, parts, level=1)
            parts.append("</ul>")
            parts.append("</div>")
        # 章节
        for section in document.sections:
            parts.append(self.render_section(section, level=1))
        # 表格
        if self.options.include_tables and document.tables:
            for table in document.tables:
                parts.append(self.render_table(table))
        # 图片
        if self.options.include_figures and document.figures:
            for figure in document.figures:
                parts.append(self.render_figure(figure))
        # 参考文献
        if self.options.include_references and document.references:
            parts.append('<div class="references">')
            parts.append("<h2>参考文献</h2>")
            parts.append(self.render_references(document.references))
            parts.append("</div>")
        parts.append("</body>")
        parts.append("</html>")
        return "\n".join(parts)

    def _render_toc_html(
        self,
        sections: List[DocumentSection],
        parts: List[str],
        level: int,
    ) -> None:
        """渲染 HTML 目录。"""
        for section in sections:
            anchor = self._make_anchor(section.title)
            parts.append(f'<li><a href="#{anchor}">{html_escape(section.title)}</a>')
            if section.subsections:
                parts.append("<ul>")
                self._render_toc_html(section.subsections, parts, level + 1)
                parts.append("</ul>")
            parts.append("</li>")

    def _make_anchor(self, title: str) -> str:
        """生成锚点。"""
        import re
        import unicodedata
        normalized = unicodedata.normalize("NFKD", title)
        ascii_only = re.sub(r"[^\w\s-]", "", normalized).strip().lower()
        return re.sub(r"[\s-]+", "-", ascii_only) or "section"

    def render_section(self, section: DocumentSection, level: int = 1) -> str:
        """渲染章节。"""
        parts: List[str] = []
        tag = f"h{min(level + 1, 6)}"
        anchor = self._make_anchor(section.title)
        parts.append(f'<section id="{anchor}">')
        parts.append(f"<{tag}>{html_escape(section.title)}</{tag}>")
        if section.content:
            # 按段落分割
            for para in section.content.split("\n\n"):
                if para.strip():
                    parts.append(f"<p>{html_escape(para.strip())}</p>")
        for subsection in section.subsections:
            parts.append(self.render_section(subsection, level + 1))
        parts.append("</section>")
        return "\n".join(parts)

    def render_table(self, table: DocumentTable) -> str:
        """渲染表格。"""
        if not table.headers:
            return ""
        parts: List[str] = []
        parts.append("<table>")
        if table.caption:
            parts.append(f"<caption>{html_escape(table.caption)}</caption>")
        parts.append("<thead><tr>")
        for header in table.headers:
            parts.append(f"<th>{html_escape(str(header))}</th>")
        parts.append("</tr></thead>")
        parts.append("<tbody>")
        for row in table.rows:
            parts.append("<tr>")
            for i, cell in enumerate(row):
                if i < len(table.headers):
                    parts.append(f"<td>{html_escape(str(cell))}</td>")
            parts.append("</tr>")
        parts.append("</tbody>")
        parts.append("</table>")
        return "\n".join(parts)

    def render_figure(self, figure: DocumentFigure) -> str:
        """渲染图片。"""
        parts: List[str] = []
        parts.append('<div class="figure">')
        if figure.image_path:
            parts.append(
                f'<img src="{html_escape(figure.image_path)}" '
                f'alt="{html_escape(figure.alt_text or figure.caption)}" '
                f'style="width: {figure.width}">'
            )
        else:
            parts.append(f"<p>[图片占位: {html_escape(figure.alt_text or figure.caption)}]</p>")
        if figure.caption:
            parts.append(f'<p class="figure-caption">{html_escape(figure.caption)}</p>')
        parts.append("</div>")
        return "\n".join(parts)

    def render_references(self, references: List[DocumentReference]) -> str:
        """渲染参考文献。"""
        parts: List[str] = []
        for i, ref in enumerate(references, 1):
            ref_id = ref.ref_id or str(i)
            parts.append(f"<p>[{ref_id}] {html_escape(ref.text)}</p>")
        return "\n".join(parts)


# ===== LaTeX 渲染器 =====


class LaTeXRenderer(BaseRenderer):
    """LaTeX 渲染器。"""

    def __init__(self, options: Optional[ExportOptions] = None, template: str = ""):
        """初始化。"""
        super().__init__(options)
        self.template = template or DEFAULT_LATEX_TEMPLATE

    def render(self, document: Document) -> str:
        """渲染完整文档为 LaTeX。"""
        # 渲染内容
        content_parts: List[str] = []
        # 摘要
        if document.abstract:
            content_parts.append("\\begin{abstract}")
            content_parts.append(self._escape_latex(document.abstract))
            content_parts.append("\\end{abstract}")
            content_parts.append("")
        # 关键词
        if document.keywords:
            keywords_str = "；".join(self._escape_latex(k) for k in document.keywords)
            content_parts.append(f"\\paragraph{{关键词}} {keywords_str}")
            content_parts.append("")
        # 章节
        for section in document.sections:
            content_parts.append(self.render_section(section, level=1))
        # 表格
        if self.options.include_tables and document.tables:
            for table in document.tables:
                content_parts.append(self.render_table(table))
        # 图片
        if self.options.include_figures and document.figures:
            for figure in document.figures:
                content_parts.append(self.render_figure(figure))
        # 参考文献
        if self.options.include_references and document.references:
            content_parts.append(self.render_references(document.references))
        content = "\n".join(content_parts)
        # 填充模板
        result = self.template.replace("__TITLE__", self._escape_latex(document.title))
        result = result.replace("__AUTHOR__", self._escape_latex(document.author))
        result = result.replace(
            "__DATE__", self._escape_latex(document.date) or "\\today"
        )
        result = result.replace("__CONTENT__", content)
        return result

    def _escape_latex(self, text: str) -> str:
        """转义 LaTeX 特殊字符。"""
        if not text:
            return ""
        replacements = {
            "\\": r"\textbackslash{}",
            "&": r"\&",
            "%": r"\%",
            "$": r"\$",
            "#": r"\#",
            "_": r"\_",
            "{": r"\{",
            "}": r"\}",
            "~": r"\textasciitilde{}",
            "^": r"\textasciicircum{}",
        }
        result = text
        for char, replacement in replacements.items():
            result = result.replace(char, replacement)
        return result

    def render_section(self, section: DocumentSection, level: int = 1) -> str:
        """渲染章节。"""
        parts: List[str] = []
        # 根据层级选择命令
        commands = {1: "section", 2: "subsection", 3: "subsubsection", 4: "paragraph"}
        cmd = commands.get(level, "paragraph")
        parts.append(f"\\{cmd}{{{self._escape_latex(section.title)}}}")
        parts.append("")
        if section.content:
            parts.append(self._escape_latex(section.content))
            parts.append("")
        for subsection in section.subsections:
            parts.append(self.render_section(subsection, level + 1))
        return "\n".join(parts)

    def render_table(self, table: DocumentTable) -> str:
        """渲染表格。"""
        if not table.headers:
            return ""
        parts: List[str] = []
        col_count = len(table.headers)
        col_spec = "l" * col_count
        parts.append("\\begin{table}[htbp]")
        parts.append("\\centering")
        if table.caption:
            parts.append(f"\\caption{{{self._escape_latex(table.caption)}}}")
        parts.append(f"\\begin{{tabular}}{{{col_spec}}}")
        parts.append("\\toprule")
        # 表头
        headers_escaped = [self._escape_latex(h) for h in table.headers]
        parts.append(" & ".join(headers_escaped) + " \\\\")
        parts.append("\\midrule")
        # 数据行
        for row in table.rows:
            while len(row) < col_count:
                row.append("")
            cells = [self._escape_latex(str(cell)) for cell in row[:col_count]]
            parts.append(" & ".join(cells) + " \\\\")
        parts.append("\\bottomrule")
        parts.append("\\end{tabular}")
        parts.append("\\end{table}")
        return "\n".join(parts)

    def render_figure(self, figure: DocumentFigure) -> str:
        """渲染图片。"""
        parts: List[str] = []
        parts.append("\\begin{figure}[htbp]")
        parts.append("\\centering")
        if figure.image_path:
            parts.append(
                f"\\includegraphics[width={figure.width}]"
                f"{{{self._escape_latex(figure.image_path)}}}"
            )
        else:
            parts.append("% 图片占位")
        if figure.caption:
            parts.append(f"\\caption{{{self._escape_latex(figure.caption)}}}")
        parts.append("\\end{figure}")
        return "\n".join(parts)

    def render_references(self, references: List[DocumentReference]) -> str:
        """渲染参考文献。"""
        parts: List[str] = []
        parts.append("\\begin{thebibliography}{99}")
        for i, ref in enumerate(references, 1):
            ref_id = ref.ref_id or str(i)
            parts.append(
                f"\\bibitem{{{ref_id}}} {self._escape_latex(ref.text)}"
            )
        parts.append("\\end{thebibliography}")
        return "\n".join(parts)


# ===== 纯文本渲染器 =====


class TextRenderer(BaseRenderer):
    """纯文本渲染器。"""

    def render(self, document: Document) -> str:
        """渲染为纯文本。"""
        lines: List[str] = []
        if document.title:
            lines.append(document.title)
            lines.append("=" * len(document.title.encode("gbk", errors="replace")))
            lines.append("")
        if document.author or document.date:
            meta_parts = []
            if document.author:
                meta_parts.append(f"作者: {document.author}")
            if document.date:
                meta_parts.append(f"日期: {document.date}")
            lines.append(" | ".join(meta_parts))
            lines.append("")
        if document.abstract:
            lines.append("【摘要】")
            lines.append(document.abstract)
            lines.append("")
        if document.keywords:
            lines.append(f"关键词: {'；'.join(document.keywords)}")
            lines.append("")
        for section in document.sections:
            lines.append(self.render_section(section, level=1))
        if self.options.include_tables and document.tables:
            for table in document.tables:
                lines.append(self.render_table(table))
                lines.append("")
        if self.options.include_references and document.references:
            lines.append("【参考文献】")
            lines.append(self.render_references(document.references))
        return "\n".join(lines)

    def render_section(self, section: DocumentSection, level: int = 1) -> str:
        """渲染章节。"""
        lines: List[str] = []
        indent = "  " * (level - 1)
        prefix = "#" * level
        lines.append(f"{indent}{prefix} {section.title}")
        lines.append("")
        if section.content:
            lines.append(section.content)
            lines.append("")
        for subsection in section.subsections:
            lines.append(self.render_section(subsection, level + 1))
        return "\n".join(lines)

    def render_table(self, table: DocumentTable) -> str:
        """渲染表格（ASCII 表格）。"""
        if not table.headers:
            return ""
        lines: List[str] = []
        if table.caption:
            lines.append(table.caption)
            lines.append("")
        # 计算列宽
        col_count = len(table.headers)
        col_widths = [len(str(h)) for h in table.headers]
        for row in table.rows:
            for i, cell in enumerate(row[:col_count]):
                col_widths[i] = max(col_widths[i], len(str(cell)))
        # 分隔线
        separator = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
        lines.append(separator)
        # 表头
        header_cells = []
        for i, h in enumerate(table.headers):
            header_cells.append(f" {str(h):<{col_widths[i]}} ")
        lines.append("|" + "|".join(header_cells) + "|")
        lines.append(separator)
        # 数据行
        for row in table.rows:
            row_cells = []
            for i in range(col_count):
                cell = str(row[i]) if i < len(row) else ""
                row_cells.append(f" {cell:<{col_widths[i]}} ")
            lines.append("|" + "|".join(row_cells) + "|")
        lines.append(separator)
        return "\n".join(lines)

    def render_figure(self, figure: DocumentFigure) -> str:
        """渲染图片（占位）。"""
        lines = [f"[图片: {figure.caption or figure.alt_text}]"]
        if figure.image_path:
            lines.append(f"  路径: {figure.image_path}")
        return "\n".join(lines)

    def render_references(self, references: List[DocumentReference]) -> str:
        """渲染参考文献。"""
        lines: List[str] = []
        for i, ref in enumerate(references, 1):
            ref_id = ref.ref_id or str(i)
            lines.append(f"[{ref_id}] {ref.text}")
        return "\n".join(lines)


# ===== JSON 渲染器 =====


class JSONRenderer(BaseRenderer):
    """JSON 渲染器。"""

    def render(self, document: Document) -> str:
        """渲染为 JSON。"""
        data = document.to_dict()
        data["_export_metadata"] = {
            "exported_at": datetime.now(tz=timezone.utc).isoformat(),
            "exporter": "ThesisMiner v8.0",
            "format": "json",
        }
        return json.dumps(data, ensure_ascii=False, indent=2, default=str)

    def render_section(self, section: DocumentSection, level: int = 1) -> str:
        """渲染章节。"""
        return json.dumps(section.to_dict(), ensure_ascii=False, indent=2)

    def render_table(self, table: DocumentTable) -> str:
        """渲染表格。"""
        return json.dumps(table.to_dict(), ensure_ascii=False, indent=2)

    def render_figure(self, figure: DocumentFigure) -> str:
        """渲染图片。"""
        return json.dumps(figure.to_dict(), ensure_ascii=False, indent=2)

    def render_references(self, references: List[DocumentReference]) -> str:
        """渲染参考文献。"""
        return json.dumps(
            [r.to_dict() for r in references], ensure_ascii=False, indent=2
        )


# ===== Word (DOCX) 渲染器 =====


class DOCXRenderer(BaseRenderer):
    """Word DOCX 渲染器

    生成符合 OOXML 规范的 .docx 文件。
    .docx 本质是 ZIP 包，包含 XML 文件。
    """

    def render(self, document: Document) -> str:
        """渲染为 DOCX（返回文件路径占位，实际通过 render_to_bytes 获取二进制）。"""
        # 此方法返回 XML 内容字符串（用于调试）
        return self._generate_document_xml(document)

    def render_to_bytes(self, document: Document) -> bytes:
        """渲染为 DOCX 二进制数据。"""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # 写入必需的 OOXML 文件
            zf.writestr(
                "[Content_Types].xml",
                self._generate_content_types_xml(),
            )
            zf.writestr(
                "_rels/.rels",
                self._generate_rels_xml(),
            )
            zf.writestr(
                "word/_rels/document.xml.rels",
                self._generate_document_rels_xml(),
            )
            zf.writestr(
                "word/document.xml",
                self._generate_document_xml(document),
            )
            zf.writestr(
                "word/styles.xml",
                self._generate_styles_xml(),
            )
            zf.writestr(
                "docProps/core.xml",
                self._generate_core_xml(document),
            )
            zf.writestr(
                "docProps/app.xml",
                self._generate_app_xml(),
            )
        return buffer.getvalue()

    def _generate_content_types_xml(self) -> str:
        """生成 [Content_Types].xml。"""
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '<Override PartName="/word/styles.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
            '<Override PartName="/docProps/core.xml" '
            'ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
            '<Override PartName="/docProps/app.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
            "</Types>"
        )

    def _generate_rels_xml(self) -> str:
        """生成 _rels/.rels。"""
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="word/document.xml"/>'
            '<Relationship Id="rId2" '
            'Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" '
            'Target="docProps/core.xml"/>'
            '<Relationship Id="rId3" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" '
            'Target="docProps/app.xml"/>'
            "</Relationships>"
        )

    def _generate_document_rels_xml(self) -> str:
        """生成 word/_rels/document.xml.rels。"""
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
            'Target="styles.xml"/>'
            "</Relationships>"
        )

    def _generate_document_xml(self, document: Document) -> str:
        """生成 word/document.xml。"""
        parts: List[str] = []
        parts.append(
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        )
        parts.append("<w:body>")
        # 标题
        if document.title:
            parts.append(self._make_heading(document.title, level=0))
        # 元数据
        if document.author or document.date:
            parts.append("<w:p>")
            parts.append("<w:pPr><w:jc w:val=\"center\"/></w:pPr>")
            meta_text = " | ".join(
                [t for t in [f"作者: {document.author}", f"日期: {document.date}"] if t]
            )
            parts.append(self._make_run(meta_text, italic=True))
            parts.append("</w:p>")
        # 摘要
        if document.abstract:
            parts.append(self._make_heading("摘要", level=2))
            parts.append(self._make_paragraph(document.abstract))
        # 关键词
        if document.keywords:
            parts.append(
                self._make_paragraph(
                    f"关键词: {'；'.join(document.keywords)}",
                    bold_prefix="关键词: ",
                )
            )
        # 章节
        for section in document.sections:
            parts.append(self._render_section_xml(section, level=1))
        # 表格
        if self.options.include_tables and document.tables:
            for table in document.tables:
                parts.append(self._render_table_xml(table))
        # 参考文献
        if self.options.include_references and document.references:
            parts.append(self._make_heading("参考文献", level=2))
            for i, ref in enumerate(document.references, 1):
                ref_id = ref.ref_id or str(i)
                parts.append(
                    self._make_paragraph(f"[{ref_id}] {ref.text}")
                )
        # 文档结尾标记
        parts.append(
            '<w:sectPr>'
            '<w:pgSz w:w="11906" w:h="16838"/>'
            '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" '
            'w:header="720" w:footer="720" w:gutter="0"/>'
            "</w:sectPr>"
        )
        parts.append("</w:body>")
        parts.append("</w:document>")
        return "".join(parts)

    def _render_section_xml(self, section: DocumentSection, level: int) -> str:
        """渲染章节为 XML。"""
        parts: List[str] = []
        parts.append(self._make_heading(section.title, level=level))
        if section.content:
            for para in section.content.split("\n\n"):
                if para.strip():
                    parts.append(self._make_paragraph(para.strip()))
        for subsection in section.subsections:
            parts.append(self._render_section_xml(subsection, level + 1))
        return "".join(parts)

    def _render_table_xml(self, table: DocumentTable) -> str:
        """渲染表格为 XML。"""
        if not table.headers:
            return ""
        parts: List[str] = []
        col_count = len(table.headers)
        parts.append("<w:tbl>")
        # 表格属性
        parts.append(
            "<w:tblPr>"
            '<w:tblW w:w="5000" w:type="pct"/>'
            '<w:tblBorders>'
            '<w:top w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
            '<w:left w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
            '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
            '<w:right w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
            '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
            '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
            "</w:tblBorders>"
            "</w:tblPr>"
        )
        # 表格网格
        parts.append("<w:tblGrid>")
        for _ in range(col_count):
            parts.append('<w:gridCol w:w="2000"/>')
        parts.append("</w:tblGrid>")
        # 表头行
        parts.append("<w:tr>")
        for header in table.headers:
            parts.append("<w:tc>")
            parts.append("<w:tcPr><w:tcW w:w=\"2000\" w:type=\"dxa\"/></w:tcPr>")
            parts.append("<w:p>")
            parts.append(self._make_run(str(header), bold=True))
            parts.append("</w:p>")
            parts.append("</w:tc>")
        parts.append("</w:tr>")
        # 数据行
        for row in table.rows:
            parts.append("<w:tr>")
            for i in range(col_count):
                cell = str(row[i]) if i < len(row) else ""
                parts.append("<w:tc>")
                parts.append("<w:tcPr><w:tcW w:w=\"2000\" w:type=\"dxa\"/></w:tcPr>")
                parts.append("<w:p>")
                parts.append(self._make_run(cell))
                parts.append("</w:p>")
                parts.append("</w:tc>")
            parts.append("</w:tr>")
        parts.append("</w:tbl>")
        # 表格后空段落
        parts.append("<w:p/>")
        return "".join(parts)

    def _make_heading(self, text: str, level: int) -> str:
        """生成标题段落。"""
        if level == 0:
            # 文档主标题
            return (
                "<w:p>"
                '<w:pPr><w:jc w:val="center"/>'
                '<w:spacing w:before="240" w:after="240"/>'
                '<w:rPr><w:b/><w:sz w:val="36"/><w:szCs w:val="36"/></w:rPr>'
                "</w:pPr>"
                + self._make_run(text, bold=True, size=36)
                + "</w:p>"
            )
        size_map = {1: 32, 2: 28, 3: 24, 4: 22}
        size = size_map.get(level, 22)
        return (
            "<w:p>"
            f'<w:pPr><w:spacing w:before="200" w:after="100"/>'
            f'<w:rPr><w:b/><w:sz w:val="{size}"/><w:szCs w:val="{size}"/></w:rPr>'
            "</w:pPr>"
            + self._make_run(text, bold=True, size=size)
            + "</w:p>"
        )

    def _make_paragraph(
        self, text: str, bold: bool = False, italic: bool = False, bold_prefix: str = ""
    ) -> str:
        """生成段落。"""
        parts = ["<w:p>"]
        parts.append(
            '<w:pPr><w:spacing w:line="360" w:lineRule="auto"/>'
            '<w:ind w:firstLine="480"/>'
            "</w:pPr>"
        )
        if bold_prefix:
            parts.append(self._make_run(bold_prefix, bold=True))
            remaining = text[len(bold_prefix):] if text.startswith(bold_prefix) else text
            parts.append(self._make_run(remaining, bold=bold, italic=italic))
        else:
            parts.append(self._make_run(text, bold=bold, italic=italic))
        parts.append("</w:p>")
        return "".join(parts)

    def _make_run(
        self,
        text: str,
        bold: bool = False,
        italic: bool = False,
        size: int = 24,
    ) -> str:
        """生成文本运行。"""
        rpr_parts = ["<w:rPr>"]
        if bold:
            rpr_parts.append("<w:b/>")
        if italic:
            rpr_parts.append("<w:i/>")
        rpr_parts.append(f'<w:sz w:val="{size}"/>')
        rpr_parts.append(f'<w:szCs w:val="{size}"/>')
        rpr_parts.append("</w:rPr>")
        rpr = "".join(rpr_parts)
        # 转义 XML 特殊字符
        escaped = xml_escape(text)
        return f"<w:r>{rpr}<w:t xml:space=\"preserve\">{escaped}</w:t></w:r>"

    def _generate_styles_xml(self) -> str:
        """生成 word/styles.xml。"""
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:docDefaults>'
            '<w:rPrDefault><w:rPr>'
            '<w:rFonts w:ascii="SimSun" w:eastAsia="SimSun" w:hAnsi="SimSun" w:cs="SimSun"/>'
            '<w:sz w:val="24"/><w:szCs w:val="24"/>'
            "</w:rPr></w:rPrDefault>"
            '<w:pPrDefault><w:pPr>'
            '<w:spacing w:line="360" w:lineRule="auto"/>'
            "</w:pPr></w:pPrDefault>"
            "</w:docDefaults>"
            '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
            '<w:name w:val="Normal"/>'
            "</w:style>"
            '<w:style w:type="paragraph" w:styleId="Heading1">'
            '<w:name w:val="heading 1"/>'
            '<w:pPr><w:spacing w:before="240" w:after="120"/></w:pPr>'
            '<w:rPr><w:b/><w:sz w:val="32"/></w:rPr>'
            "</w:style>"
            '<w:style w:type="paragraph" w:styleId="Heading2">'
            '<w:name w:val="heading 2"/>'
            '<w:pPr><w:spacing w:before="200" w:after="100"/></w:pPr>'
            '<w:rPr><w:b/><w:sz w:val="28"/></w:rPr>'
            "</w:style>"
            "</w:styles>"
        )

    def _generate_core_xml(self, document: Document) -> str:
        """生成 docProps/core.xml。"""
        now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f"<dc:title>{xml_escape(document.title)}</dc:title>"
            f"<dc:creator>{xml_escape(document.author)}</dc:creator>"
            f"<cp:lastModifiedBy>{xml_escape(document.author)}</cp:lastModifiedBy>"
            f"<dcterms:created xsi:type=\"dcterms:W3CDTF\">{now}</dcterms:created>"
            f"<dcterms:modified xsi:type=\"dcterms:W3CDTF\">{now}</dcterms:modified>"
            "</cp:coreProperties>"
        )

    def _generate_app_xml(self) -> str:
        """生成 docProps/app.xml。"""
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
            "<Application>ThesisMiner v8.0</Application>"
            "<AppVersion>8.0</AppVersion>"
            "</Properties>"
        )

    def render_section(self, section: DocumentSection, level: int = 1) -> str:
        """渲染章节。"""
        return self._render_section_xml(section, level)

    def render_table(self, table: DocumentTable) -> str:
        """渲染表格。"""
        return self._render_table_xml(table)

    def render_figure(self, figure: DocumentFigure) -> str:
        """渲染图片（占位段落）。"""
        return self._make_paragraph(f"[图片: {figure.caption or figure.alt_text}]")

    def render_references(self, references: List[DocumentReference]) -> str:
        """渲染参考文献。"""
        parts: List[str] = []
        for i, ref in enumerate(references, 1):
            ref_id = ref.ref_id or str(i)
            parts.append(self._make_paragraph(f"[{ref_id}] {ref.text}"))
        return "".join(parts)


# ===== PDF 渲染器（简化实现） =====


class PDFRenderer(BaseRenderer):
    """PDF 渲染器（简化实现）

    生成简化的 PDF 文件。完整 PDF 生成需要 reportlab 等库，
    此处生成符合 PDF 规范的最小可用文件。
    """

    def render(self, document: Document) -> str:
        """渲染为 PDF 文本内容（用于预览）。"""
        # 返回纯文本预览
        text_renderer = TextRenderer(self.options)
        return text_renderer.render(document)

    def render_to_bytes(self, document: Document) -> bytes:
        """渲染为 PDF 二进制数据。"""
        text_renderer = TextRenderer(self.options)
        text_content = text_renderer.render(document)
        return self._generate_pdf_bytes(text_content, document.title)

    def _generate_pdf_bytes(self, content: str, title: str = "") -> bytes:
        """生成简化的 PDF 二进制数据。"""
        # 这是一个非常简化的 PDF 实现
        # 实际生产环境建议使用 reportlab 或 weasyprint
        lines = []
        # PDF 头部
        lines.append(b"%PDF-1.4\n")
        # 对象 1: Catalog
        obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        # 对象 2: Pages
        obj2 = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        # 对象 3: Page
        obj3 = (
            b"3 0 obj\n"
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\n"
            b"endobj\n"
        )
        # 对象 4: Content stream
        # 简化：将文本按行写入
        stream_lines = []
        stream_lines.append(b"BT")
        stream_lines.append(b"/F1 12 Tf")
        stream_lines.append(b"1 0 0 1 50 800 Tm")
        stream_lines.append(b"20 TL")
        for line in content.split("\n")[:50]:  # 限制行数
            try:
                encoded = line.encode("latin-1", errors="replace")
            except Exception:
                encoded = b""
            escaped = encoded.replace(b"(", b"\\(").replace(b")", b"\\)")
            stream_lines.append(b"(" + escaped + b") Tj")
            stream_lines.append(b"T*")
        stream_lines.append(b"ET")
        stream = b"\n".join(stream_lines)
        obj4 = (
            b"4 0 obj\n"
            b"<< /Length " + str(len(stream)).encode() + b" >>\n"
            b"stream\n" + stream + b"\nendstream\nendobj\n"
        )
        # 对象 5: Font
        obj5 = (
            b"5 0 obj\n"
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\n"
            b"endobj\n"
        )
        # 组装
        offsets = []
        current_offset = len(lines[0])
        offsets.append(current_offset)
        lines.append(obj1)
        current_offset += len(obj1)
        offsets.append(current_offset)
        lines.append(obj2)
        current_offset += len(obj2)
        offsets.append(current_offset)
        lines.append(obj3)
        current_offset += len(obj3)
        offsets.append(current_offset)
        lines.append(obj4)
        current_offset += len(obj4)
        offsets.append(current_offset)
        lines.append(obj5)
        current_offset += len(obj5)
        # xref
        xref_offset = current_offset
        xref = b"xref\n"
        xref += b"0 6\n"
        xref += b"0000000000 65535 f \n"
        for offset in offsets:
            xref += f"{offset:010d} 00000 n \n".encode()
        # Trailer
        trailer = (
            b"trailer\n"
            b"<< /Size 6 /Root 1 0 R >>\n"
            b"startxref\n"
            + str(xref_offset).encode() + b"\n"
            b"%%EOF\n"
        )
        return b"".join(lines) + xref + trailer


# ===== 文档导出器主类 =====


class DocumentExporter:
    """文档导出器（单例）

    整合多种渲染器，提供统一的文档导出接口。
    """

    _instance: Optional["DocumentExporter"] = None
    _instance_lock = __import__("threading").Lock()

    def __new__(cls) -> "DocumentExporter":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, options: Optional[ExportOptions] = None):
        """初始化导出器。"""
        if self._initialized:
            return
        self._initialized = True
        self._options = options or ExportOptions()
        self._renderers: Dict[str, BaseRenderer] = {
            ExportFormat.MARKDOWN.value: MarkdownRenderer(self._options),
            ExportFormat.HTML.value: HTMLRenderer(self._options),
            ExportFormat.LATEX.value: LaTeXRenderer(self._options),
            ExportFormat.TEXT.value: TextRenderer(self._options),
            ExportFormat.JSON.value: JSONRenderer(self._options),
            ExportFormat.DOCX.value: DOCXRenderer(self._options),
            ExportFormat.PDF.value: PDFRenderer(self._options),
        }
        self._templates: Dict[str, str] = {}
        self._progress_callbacks: List[Callable[[int, int, str], None]] = []

    @classmethod
    def get_instance(cls) -> "DocumentExporter":
        """获取单例实例。"""
        return cls()

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例。"""
        with cls._instance_lock:
            cls._instance = None

    def set_options(self, options: ExportOptions) -> None:
        """设置导出选项。"""
        self._options = options
        # 重新初始化渲染器
        for renderer in self._renderers.values():
            renderer.options = options

    def get_options(self) -> ExportOptions:
        """获取当前选项。"""
        return self._options

    def register_template(self, name: str, template: str) -> None:
        """注册自定义模板。"""
        self._templates[name] = template

    def add_progress_callback(self, callback: Callable[[int, int, str], None]) -> None:
        """添加进度回调。

        回调签名: callback(current, total, message)
        """
        self._progress_callbacks.append(callback)

    def _notify_progress(self, current: int, total: int, message: str) -> None:
        """通知进度。"""
        for callback in self._progress_callbacks:
            try:
                callback(current, total, message)
            except Exception as e:
                _logger.debug(f"进度回调失败: {e}")

    # ===== 导出方法 =====

    def export(
        self,
        document: Document,
        format: Union[ExportFormat, str],
        options: Optional[ExportOptions] = None,
    ) -> ExportResult:
        """导出文档。

        Args:
            document: 文档对象。
            format: 导出格式。
            options: 导出选项（覆盖默认）。

        Returns:
            导出结果。
        """
        fmt_value = format.value if isinstance(format, ExportFormat) else str(format)
        renderer = self._renderers.get(fmt_value)
        if not renderer:
            return ExportResult(
                format=fmt_value,
                success=False,
                error_message=f"不支持的导出格式: {fmt_value}",
            )
        if options:
            renderer.options = options
        try:
            self._notify_progress(0, 1, f"开始导出 {fmt_value}")
            content = renderer.render(document)
            self._notify_progress(1, 1, f"导出完成 {fmt_value}")
            return ExportResult(
                format=fmt_value,
                content=content,
                success=True,
                metadata={
                    "format": fmt_value,
                    "content_length": len(content),
                    "exported_at": datetime.now(tz=timezone.utc).isoformat(),
                },
            )
        except Exception as e:
            _logger.error(f"导出失败 ({fmt_value}): {e}", exc_info=True)
            return ExportResult(
                format=fmt_value,
                success=False,
                error_message=str(e),
            )

    def export_markdown(
        self,
        document: Document,
        options: Optional[ExportOptions] = None,
    ) -> str:
        """导出为 Markdown。"""
        result = self.export(document, ExportFormat.MARKDOWN, options)
        return result.content if result.success else ""

    def export_html(
        self,
        document: Document,
        options: Optional[ExportOptions] = None,
    ) -> str:
        """导出为 HTML。"""
        result = self.export(document, ExportFormat.HTML, options)
        return result.content if result.success else ""

    def export_latex(
        self,
        document: Document,
        options: Optional[ExportOptions] = None,
    ) -> str:
        """导出为 LaTeX。"""
        result = self.export(document, ExportFormat.LATEX, options)
        return result.content if result.success else ""

    def export_text(
        self,
        document: Document,
        options: Optional[ExportOptions] = None,
    ) -> str:
        """导出为纯文本。"""
        result = self.export(document, ExportFormat.TEXT, options)
        return result.content if result.success else ""

    def export_json(
        self,
        document: Document,
        options: Optional[ExportOptions] = None,
    ) -> str:
        """导出为 JSON。"""
        result = self.export(document, ExportFormat.JSON, options)
        return result.content if result.success else ""

    def export_docx_bytes(
        self,
        document: Document,
        options: Optional[ExportOptions] = None,
    ) -> bytes:
        """导出为 DOCX 二进制数据。"""
        renderer = self._renderers.get(ExportFormat.DOCX.value)
        if not renderer or not isinstance(renderer, DOCXRenderer):
            return b""
        if options:
            renderer.options = options
        return renderer.render_to_bytes(document)

    def export_pdf_bytes(
        self,
        document: Document,
        options: Optional[ExportOptions] = None,
    ) -> bytes:
        """导出为 PDF 二进制数据。"""
        renderer = self._renderers.get(ExportFormat.PDF.value)
        if not renderer or not isinstance(renderer, PDFRenderer):
            return b""
        if options:
            renderer.options = options
        return renderer.render_to_bytes(document)

    def export_to_file(
        self,
        document: Document,
        file_path: str,
        format: Optional[Union[ExportFormat, str]] = None,
        options: Optional[ExportOptions] = None,
    ) -> ExportResult:
        """导出到文件。

        Args:
            document: 文档对象。
            file_path: 文件路径。
            format: 导出格式，None 则根据文件扩展名推断。
            options: 导出选项。

        Returns:
            导出结果。
        """
        # 推断格式
        if format is None:
            ext = Path(file_path).suffix.lower().lstrip(".")
            format = ext or "markdown"
        fmt_value = format.value if isinstance(format, ExportFormat) else str(format)
        # 二进制格式特殊处理
        try:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            if fmt_value == ExportFormat.DOCX.value:
                data = self.export_docx_bytes(document, options)
                with open(file_path, "wb") as f:
                    f.write(data)
                return ExportResult(
                    format=fmt_value,
                    file_path=file_path,
                    file_size=len(data),
                    success=True,
                )
            elif fmt_value == ExportFormat.PDF.value:
                data = self.export_pdf_bytes(document, options)
                with open(file_path, "wb") as f:
                    f.write(data)
                return ExportResult(
                    format=fmt_value,
                    file_path=file_path,
                    file_size=len(data),
                    success=True,
                )
            else:
                result = self.export(document, format, options)
                if not result.success:
                    return result
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(result.content)
                result.file_path = file_path
                result.file_size = len(result.content.encode("utf-8"))
                return result
        except Exception as e:
            _logger.error(f"导出文件失败: {e}", exc_info=True)
            return ExportResult(
                format=fmt_value,
                file_path=file_path,
                success=False,
                error_message=str(e),
            )

    def export_batch(
        self,
        documents: List[Tuple[str, Document]],
        output_dir: str,
        format: Union[ExportFormat, str],
        options: Optional[ExportOptions] = None,
    ) -> List[ExportResult]:
        """批量导出文档。

        Args:
            documents: (filename, document) 列表。
            output_dir: 输出目录。
            format: 导出格式。
            options: 导出选项。

        Returns:
            导出结果列表。
        """
        results: List[ExportResult] = []
        total = len(documents)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        fmt_value = format.value if isinstance(format, ExportFormat) else str(format)
        ext_map = {
            "markdown": ".md",
            "html": ".html",
            "latex": ".tex",
            "text": ".txt",
            "json": ".json",
            "docx": ".docx",
            "pdf": ".pdf",
        }
        ext = ext_map.get(fmt_value, ".txt")
        for i, (filename, doc) in enumerate(documents):
            self._notify_progress(i, total, f"导出 {filename}")
            file_path = str(Path(output_dir) / f"{filename}{ext}")
            result = self.export_to_file(doc, file_path, format, options)
            results.append(result)
        self._notify_progress(total, total, "批量导出完成")
        return results

    def export_to_zip(
        self,
        documents: List[Tuple[str, Document]],
        zip_path: str,
        format: Union[ExportFormat, str],
        options: Optional[ExportOptions] = None,
    ) -> ExportResult:
        """批量导出并打包为 ZIP。"""
        fmt_value = format.value if isinstance(format, ExportFormat) else str(format)
        ext_map = {
            "markdown": ".md",
            "html": ".html",
            "latex": ".tex",
            "text": ".txt",
            "json": ".json",
            "docx": ".docx",
            "pdf": ".pdf",
        }
        ext = ext_map.get(fmt_value, ".txt")
        try:
            Path(zip_path).parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                total = len(documents)
                for i, (filename, doc) in enumerate(documents):
                    self._notify_progress(i, total, f"打包 {filename}")
                    if fmt_value in (ExportFormat.DOCX.value, ExportFormat.PDF.value):
                        if fmt_value == ExportFormat.DOCX.value:
                            data = self.export_docx_bytes(doc, options)
                        else:
                            data = self.export_pdf_bytes(doc, options)
                        zf.writestr(f"{filename}{ext}", data)
                    else:
                        result = self.export(doc, format, options)
                        if result.success:
                            zf.writestr(f"{filename}{ext}", result.content)
            file_size = Path(zip_path).stat().st_size
            self._notify_progress(total, total, "打包完成")
            return ExportResult(
                format=fmt_value,
                file_path=zip_path,
                file_size=file_size,
                success=True,
                metadata={"document_count": len(documents)},
            )
        except Exception as e:
            _logger.error(f"打包失败: {e}", exc_info=True)
            return ExportResult(
                format=fmt_value,
                file_path=zip_path,
                success=False,
                error_message=str(e),
            )

    # ===== 工具方法 =====

    def list_supported_formats(self) -> List[str]:
        """列出支持的导出格式。"""
        return list(self._renderers.keys())

    def create_document_from_dict(self, data: Dict[str, Any]) -> Document:
        """从字典创建文档对象。"""
        return Document.from_dict(data)

    def merge_documents(self, documents: List[Document]) -> Document:
        """合并多个文档。"""
        if not documents:
            return Document()
        merged = Document(
            title=documents[0].title,
            author=documents[0].author,
            date=documents[0].date,
        )
        for doc in documents:
            merged.sections.extend(doc.sections)
            merged.tables.extend(doc.tables)
            merged.figures.extend(doc.figures)
            merged.references.extend(doc.references)
            if doc.abstract and not merged.abstract:
                merged.abstract = doc.abstract
            if doc.keywords and not merged.keywords:
                merged.keywords = doc.keywords
        return merged

    def shutdown(self) -> None:
        """关闭导出器。"""
        self._progress_callbacks.clear()
        _logger.info("文档导出器已关闭")


# ===== 模块级便捷函数 =====


def get_document_exporter() -> DocumentExporter:
    """获取全局文档导出器单例。"""
    return DocumentExporter.get_instance()


def export_to_markdown(document: Document) -> str:
    """导出为 Markdown 便捷函数。"""
    return get_document_exporter().export_markdown(document)


def export_to_html(document: Document) -> str:
    """导出为 HTML 便捷函数。"""
    return get_document_exporter().export_html(document)


def export_to_file(
    document: Document,
    file_path: str,
    format: Optional[str] = None,
) -> ExportResult:
    """导出到文件便捷函数。"""
    return get_document_exporter().export_to_file(document, file_path, format)


# ===== 单元测试可运行逻辑 =====


def _run_self_test() -> None:
    """模块自检。"""
    DocumentExporter.reset_instance()
    exporter = DocumentExporter()

    # 创建测试文档
    doc = Document(
        title="深度学习在自然语言处理中的应用研究",
        author="张三",
        date="2026-06-19",
        abstract="本文研究深度学习在自然语言处理领域的应用，提出了一种基于 Transformer 的改进模型。",
        keywords=["深度学习", "自然语言处理", "Transformer", "文本分类"],
        sections=[
            DocumentSection(
                title="引言",
                level=1,
                content="近年来，深度学习技术在自然语言处理领域取得了显著进展。",
                subsections=[
                    DocumentSection(
                        title="研究背景",
                        level=2,
                        content="传统的 NLP 方法在处理长文本时存在局限性。",
                    ),
                    DocumentSection(
                        title="研究意义",
                        level=2,
                        content="本研究对推动 NLP 技术发展具有重要意义。",
                    ),
                ],
            ),
            DocumentSection(
                title="相关工作",
                level=1,
                content="本节回顾相关工作。",
            ),
            DocumentSection(
                title="方法",
                level=1,
                content="我们提出了一种新的模型架构。",
            ),
        ],
        tables=[
            DocumentTable(
                caption="表1：模型性能对比",
                headers=["模型", "准确率", "F1 分数"],
                rows=[
                    ["BERT", "92.3%", "91.8%"],
                    ["GPT", "90.1%", "89.5%"],
                    ["Ours", "94.5%", "93.9%"],
                ],
            ),
        ],
        figures=[
            DocumentFigure(
                caption="图1：模型架构图",
                alt_text="模型架构示意图",
            ),
        ],
        references=[
            DocumentReference(ref_id="1", text="Vaswani, A. et al. (2017). Attention is all you need."),
            DocumentReference(ref_id="2", text="Devlin, J. et al. (2018). BERT: Pre-training of deep bidirectional transformers."),
        ],
    )

    # 测试 Markdown 导出
    md = exporter.export_markdown(doc)
    assert "# 深度学习在自然语言处理中的应用研究" in md
    assert "## 摘要" in md
    assert "## 引言" in md
    assert "| 模型 | 准确率 |" in md
    print(f"Markdown 导出成功，长度 {len(md)} 字符")

    # 测试 HTML 导出
    html = exporter.export_html(doc)
    assert "<!DOCTYPE html>" in html
    assert "<h1>" in html
    assert "<table>" in html
    print(f"HTML 导出成功，长度 {len(html)} 字符")

    # 测试 LaTeX 导出
    latex = exporter.export_latex(doc)
    assert "\\documentclass" in latex
    assert "\\title{" in latex
    assert "\\section{" in latex
    print(f"LaTeX 导出成功，长度 {len(latex)} 字符")

    # 测试纯文本导出
    text = exporter.export_text(doc)
    assert doc.title in text
    assert "【摘要】" in text
    print(f"文本导出成功，长度 {len(text)} 字符")

    # 测试 JSON 导出
    json_text = exporter.export_json(doc)
    import json as json_module
    parsed = json_module.loads(json_text)
    assert parsed["title"] == doc.title
    print(f"JSON 导出成功，长度 {len(json_text)} 字符")

    # 测试 DOCX 导出
    docx_bytes = exporter.export_docx_bytes(doc)
    assert len(docx_bytes) > 0
    assert docx_bytes[:2] == b"PK"  # ZIP 文件头
    print(f"DOCX 导出成功，大小 {len(docx_bytes)} 字节")

    # 测试 PDF 导出
    pdf_bytes = exporter.export_pdf_bytes(doc)
    assert len(pdf_bytes) > 0
    assert pdf_bytes[:5] == b"%PDF-"
    print(f"PDF 导出成功，大小 {len(pdf_bytes)} 字节")

    # 测试文件导出
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        # Markdown 文件
        result = exporter.export_to_file(doc, str(Path(tmpdir) / "test.md"))
        assert result.success
        assert Path(result.file_path).exists()
        # DOCX 文件
        result = exporter.export_to_file(doc, str(Path(tmpdir) / "test.docx"))
        assert result.success
        assert Path(result.file_path).exists()
        # PDF 文件
        result = exporter.export_to_file(doc, str(Path(tmpdir) / "test.pdf"))
        assert result.success
        assert Path(result.file_path).exists()
        print("文件导出测试通过")

        # 测试批量导出
        docs = [("doc1", doc), ("doc2", doc)]
        results = exporter.export_batch(docs, tmpdir, "markdown")
        assert len(results) == 2
        assert all(r.success for r in results)
        print(f"批量导出 {len(results)} 个文档成功")

        # 测试 ZIP 打包
        zip_result = exporter.export_to_zip(docs, str(Path(tmpdir) / "batch.zip"), "markdown")
        assert zip_result.success
        assert Path(zip_result.file_path).exists()
        print(f"ZIP 打包成功，大小 {zip_result.file_size} 字节")

    # 测试支持的格式列表
    formats = exporter.list_supported_formats()
    assert "markdown" in formats
    assert "html" in formats
    print(f"支持的格式: {formats}")

    # 测试文档合并
    doc2 = Document(title="第二个文档", sections=[DocumentSection(title="附录", content="附录内容")])
    merged = exporter.merge_documents([doc, doc2])
    assert len(merged.sections) == len(doc.sections) + len(doc2.sections)
    print(f"文档合并成功，共 {len(merged.sections)} 个章节")

    exporter.shutdown()
    print("DocumentExporter 自检通过")


if __name__ == "__main__":
    _run_self_test()
