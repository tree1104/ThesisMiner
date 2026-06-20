"""DocumentExporter 单元测试模块

本测试模块覆盖 backend.export.document_exporter 的全部功能，包括：
    - 数据结构：Document / DocumentSection / DocumentTable / DocumentFigure / DocumentReference
    - 导出选项与结果：ExportOptions / ExportResult
    - 渲染器：MarkdownRenderer / HTMLRenderer / LaTeXRenderer / TextRenderer / JSONRenderer / DOCXRenderer / PDFRenderer
    - 导出器主类：DocumentExporter 单例、export / export_to_file / export_batch / export_to_zip
    - 模板系统、进度回调、文档合并、从字典创建文档
    - 模块级便捷函数
    - 线程安全与集成场景

所有注释使用中文编写。
"""
from __future__ import annotations

import io
import json
import os
import threading
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Tuple
from unittest.mock import MagicMock, patch

import pytest

from backend.export.document_exporter import (
    DEFAULT_CSS,
    DEFAULT_LATEX_TEMPLATE,
    BaseRenderer,
    DOCXRenderer,
    Document,
    DocumentExporter,
    DocumentFigure,
    DocumentReference,
    DocumentSection,
    DocumentTable,
    ExportFormat,
    ExportOptions,
    ExportResult,
    HTMLRenderer,
    JSONRenderer,
    LaTeXRenderer,
    MarkdownRenderer,
    PDFRenderer,
    TextRenderer,
    export_to_file,
    export_to_html,
    export_to_markdown,
    get_document_exporter,
)


# ===== 测试夹具 =====


@pytest.fixture(autouse=True)
def reset_exporter():
    """每个测试前后重置 DocumentExporter 单例，保证测试隔离。"""
    DocumentExporter.reset_instance()
    yield
    DocumentExporter.reset_instance()


@pytest.fixture
def simple_section() -> DocumentSection:
    """构造一个简单的章节。"""
    return DocumentSection(
        title="引言",
        level=1,
        content="本节介绍研究背景与意义。",
    )


@pytest.fixture
def nested_sections() -> List[DocumentSection]:
    """构造含子章节的章节列表。"""
    return [
        DocumentSection(
            title="引言",
            level=1,
            content="引言内容。",
            subsections=[
                DocumentSection(
                    title="研究背景",
                    level=2,
                    content="背景描述。",
                ),
                DocumentSection(
                    title="研究意义",
                    level=2,
                    content="意义描述。",
                ),
            ],
        ),
        DocumentSection(
            title="方法",
            level=1,
            content="方法描述。",
        ),
    ]


@pytest.fixture
def sample_table() -> DocumentTable:
    """构造示例表格。"""
    return DocumentTable(
        caption="表1：模型性能对比",
        headers=["模型", "准确率", "F1 分数"],
        rows=[
            ["BERT", "92.3%", "91.8%"],
            ["GPT", "90.1%", "89.5%"],
            ["Ours", "94.5%", "93.9%"],
        ],
    )


@pytest.fixture
def sample_figure() -> DocumentFigure:
    """构造示例图片。"""
    return DocumentFigure(
        caption="图1：模型架构图",
        alt_text="模型架构示意图",
        image_path="images/arch.png",
        width="80%",
    )


@pytest.fixture
def sample_references() -> List[DocumentReference]:
    """构造示例参考文献。"""
    return [
        DocumentReference(ref_id="1", text="Vaswani, A. et al. (2017). Attention is all you need."),
        DocumentReference(ref_id="2", text="Devlin, J. et al. (2018). BERT: Pre-training of deep bidirectional transformers."),
    ]


@pytest.fixture
def sample_document(
    nested_sections,
    sample_table,
    sample_figure,
    sample_references,
) -> Document:
    """构造完整的示例文档。"""
    return Document(
        title="深度学习在自然语言处理中的应用研究",
        author="张三",
        date="2026-06-19",
        abstract="本文研究深度学习在自然语言处理领域的应用，提出了一种基于 Transformer 的改进模型。",
        keywords=["深度学习", "自然语言处理", "Transformer", "文本分类"],
        sections=nested_sections,
        tables=[sample_table],
        figures=[sample_figure],
        references=sample_references,
        metadata={"project": "ThesisMiner", "version": "8.0"},
    )


@pytest.fixture
def empty_document() -> Document:
    """构造空文档。"""
    return Document()


# ===== 数据结构测试 =====


class TestDocumentSection:
    """DocumentSection 数据结构测试。"""

    def test_default_values(self):
        """测试默认值。"""
        section = DocumentSection()
        assert section.title == ""
        assert section.level == 1
        assert section.content == ""
        assert section.subsections == []
        assert section.metadata == {}

    def test_custom_values(self, simple_section):
        """测试自定义值。"""
        assert simple_section.title == "引言"
        assert simple_section.level == 1
        assert simple_section.content == "本节介绍研究背景与意义。"

    def test_to_dict(self, simple_section):
        """测试转换为字典。"""
        d = simple_section.to_dict()
        assert d["title"] == "引言"
        assert d["level"] == 1
        assert d["content"] == "本节介绍研究背景与意义。"
        assert d["subsections"] == []
        assert d["metadata"] == {}

    def test_nested_to_dict(self, nested_sections):
        """测试嵌套章节转字典。"""
        d = nested_sections[0].to_dict()
        assert d["title"] == "引言"
        assert len(d["subsections"]) == 2
        assert d["subsections"][0]["title"] == "研究背景"
        assert d["subsections"][1]["title"] == "研究意义"

    def test_metadata_storage(self):
        """测试元数据存储。"""
        section = DocumentSection(
            title="测试",
            metadata={"key": "value", "number": 42},
        )
        assert section.metadata["key"] == "value"
        assert section.metadata["number"] == 42


class TestDocumentTable:
    """DocumentTable 数据结构测试。"""

    def test_default_values(self):
        """测试默认值。"""
        table = DocumentTable()
        assert table.headers == []
        assert table.rows == []
        assert table.caption == ""
        assert table.style == "default"

    def test_custom_values(self, sample_table):
        """测试自定义值。"""
        assert sample_table.caption == "表1：模型性能对比"
        assert len(sample_table.headers) == 3
        assert len(sample_table.rows) == 3
        assert sample_table.headers[0] == "模型"

    def test_to_dict(self, sample_table):
        """测试转换为字典。"""
        d = sample_table.to_dict()
        assert d["caption"] == "表1：模型性能对比"
        assert d["headers"] == ["模型", "准确率", "F1 分数"]
        assert len(d["rows"]) == 3
        assert d["style"] == "default"

    def test_empty_table_to_dict(self):
        """测试空表格转字典。"""
        table = DocumentTable()
        d = table.to_dict()
        assert d["headers"] == []
        assert d["rows"] == []


class TestDocumentFigure:
    """DocumentFigure 数据结构测试。"""

    def test_default_values(self):
        """测试默认值。"""
        fig = DocumentFigure()
        assert fig.caption == ""
        assert fig.image_path == ""
        assert fig.width == "100%"
        assert fig.alt_text == ""

    def test_custom_values(self, sample_figure):
        """测试自定义值。"""
        assert sample_figure.caption == "图1：模型架构图"
        assert sample_figure.image_path == "images/arch.png"
        assert sample_figure.width == "80%"
        assert sample_figure.alt_text == "模型架构示意图"

    def test_to_dict(self, sample_figure):
        """测试转换为字典。"""
        d = sample_figure.to_dict()
        assert d["caption"] == "图1：模型架构图"
        assert d["image_path"] == "images/arch.png"
        assert d["width"] == "80%"
        assert d["alt_text"] == "模型架构示意图"


class TestDocumentReference:
    """DocumentReference 数据结构测试。"""

    def test_default_values(self):
        """测试默认值。"""
        ref = DocumentReference()
        assert ref.ref_id == ""
        assert ref.text == ""
        assert ref.ref_type == ""

    def test_custom_values(self):
        """测试自定义值。"""
        ref = DocumentReference(ref_id="5", text="测试引用", ref_type="journal")
        assert ref.ref_id == "5"
        assert ref.text == "测试引用"
        assert ref.ref_type == "journal"

    def test_to_dict(self):
        """测试转换为字典。"""
        ref = DocumentReference(ref_id="5", text="测试引用", ref_type="book")
        d = ref.to_dict()
        assert d["ref_id"] == "5"
        assert d["text"] == "测试引用"
        assert d["ref_type"] == "book"


class TestDocument:
    """Document 数据结构测试。"""

    def test_default_values(self, empty_document):
        """测试默认值。"""
        assert empty_document.title == ""
        assert empty_document.author == ""
        assert empty_document.sections == []
        assert empty_document.tables == []
        assert empty_document.figures == []
        assert empty_document.references == []
        assert empty_document.keywords == []
        assert empty_document.metadata == {}

    def test_to_dict(self, sample_document):
        """测试转换为字典。"""
        d = sample_document.to_dict()
        assert d["title"] == "深度学习在自然语言处理中的应用研究"
        assert d["author"] == "张三"
        assert d["date"] == "2026-06-19"
        assert len(d["sections"]) == 2
        assert len(d["tables"]) == 1
        assert len(d["figures"]) == 1
        assert len(d["references"]) == 2
        assert d["keywords"] == ["深度学习", "自然语言处理", "Transformer", "文本分类"]

    def test_from_dict_roundtrip(self, sample_document):
        """测试字典往返转换。"""
        d = sample_document.to_dict()
        restored = Document.from_dict(d)
        assert restored.title == sample_document.title
        assert restored.author == sample_document.author
        assert restored.date == sample_document.date
        assert restored.abstract == sample_document.abstract
        assert restored.keywords == sample_document.keywords
        assert len(restored.sections) == len(sample_document.sections)
        assert len(restored.tables) == len(sample_document.tables)
        assert len(restored.figures) == len(sample_document.figures)
        assert len(restored.references) == len(sample_document.references)

    def test_from_dict_with_nested_sections(self, nested_sections):
        """测试从字典构建嵌套章节。"""
        doc = Document(title="测试", sections=nested_sections)
        d = doc.to_dict()
        restored = Document.from_dict(d)
        assert len(restored.sections) == 2
        assert restored.sections[0].title == "引言"
        assert len(restored.sections[0].subsections) == 2
        assert restored.sections[0].subsections[0].title == "研究背景"

    def test_from_dict_empty(self):
        """测试从空字典构建。"""
        doc = Document.from_dict({})
        assert doc.title == ""
        assert doc.sections == []
        assert doc.tables == []

    def test_from_dict_partial(self):
        """测试从部分字典构建。"""
        data = {"title": "部分文档", "author": "作者"}
        doc = Document.from_dict(data)
        assert doc.title == "部分文档"
        assert doc.author == "作者"
        assert doc.sections == []


# ===== 导出选项与结果测试 =====


class TestExportOptions:
    """ExportOptions 测试。"""

    def test_default_values(self):
        """测试默认值。"""
        opts = ExportOptions()
        assert opts.include_toc is True
        assert opts.include_metadata is True
        assert opts.include_references is True
        assert opts.include_figures is True
        assert opts.include_tables is True
        assert opts.css_style == DEFAULT_CSS
        assert opts.template == "academic"
        assert opts.encoding == "utf-8"
        assert opts.page_size == "A4"
        assert opts.margin == "2.5cm"
        assert opts.font_family == "SimSun"
        assert opts.font_size == "12pt"
        assert opts.line_spacing == 1.8

    def test_custom_values(self):
        """测试自定义值。"""
        opts = ExportOptions(
            include_toc=False,
            include_metadata=False,
            template="custom",
            font_size="14pt",
        )
        assert opts.include_toc is False
        assert opts.include_metadata is False
        assert opts.template == "custom"
        assert opts.font_size == "14pt"

    def test_custom_css(self):
        """测试自定义 CSS。"""
        custom_css = "body { color: red; }"
        opts = ExportOptions(css_style=custom_css)
        assert opts.css_style == custom_css


class TestExportResult:
    """ExportResult 测试。"""

    def test_default_values(self):
        """测试默认值。"""
        result = ExportResult(format="markdown")
        assert result.format == "markdown"
        assert result.content == ""
        assert result.file_path == ""
        assert result.file_size == 0
        assert result.success is True
        assert result.error_message == ""
        assert result.metadata == {}

    def test_failed_result(self):
        """测试失败结果。"""
        result = ExportResult(
            format="pdf",
            success=False,
            error_message="导出失败",
        )
        assert result.success is False
        assert result.error_message == "导出失败"

    def test_to_dict(self):
        """测试转换为字典。"""
        result = ExportResult(
            format="html",
            content="<html></html>",
            file_path="/tmp/test.html",
            file_size=100,
            success=True,
            metadata={"key": "value"},
        )
        d = result.to_dict()
        assert d["format"] == "html"
        assert d["content_length"] == len("<html></html>")
        assert d["file_path"] == "/tmp/test.html"
        assert d["file_size"] == 100
        assert d["success"] is True
        assert d["metadata"] == {"key": "value"}


# ===== 枚举测试 =====


class TestExportFormat:
    """ExportFormat 枚举测试。"""

    def test_enum_values(self):
        """测试枚举值。"""
        assert ExportFormat.MARKDOWN.value == "markdown"
        assert ExportFormat.HTML.value == "html"
        assert ExportFormat.PDF.value == "pdf"
        assert ExportFormat.DOCX.value == "docx"
        assert ExportFormat.LATEX.value == "latex"
        assert ExportFormat.TEXT.value == "text"
        assert ExportFormat.JSON.value == "json"

    def test_enum_count(self):
        """测试枚举数量。"""
        assert len(list(ExportFormat)) == 7

    def test_enum_from_string(self):
        """测试从字符串创建枚举。"""
        assert ExportFormat("markdown") == ExportFormat.MARKDOWN
        assert ExportFormat("html") == ExportFormat.HTML

    def test_enum_is_str(self):
        """测试枚举继承 str。"""
        assert isinstance(ExportFormat.MARKDOWN, str)


# ===== 渲染器基类测试 =====


class TestBaseRenderer:
    """BaseRenderer 基类测试。"""

    def test_init_default_options(self):
        """测试默认选项初始化。"""
        renderer = BaseRenderer()
        assert isinstance(renderer.options, ExportOptions)

    def test_init_custom_options(self):
        """测试自定义选项初始化。"""
        opts = ExportOptions(include_toc=False)
        renderer = BaseRenderer(opts)
        assert renderer.options.include_toc is False

    def test_render_not_implemented(self, empty_document):
        """测试 render 抛出 NotImplementedError。"""
        renderer = BaseRenderer()
        with pytest.raises(NotImplementedError):
            renderer.render(empty_document)

    def test_render_section_not_implemented(self, simple_section):
        """测试 render_section 抛出 NotImplementedError。"""
        renderer = BaseRenderer()
        with pytest.raises(NotImplementedError):
            renderer.render_section(simple_section)

    def test_render_table_not_implemented(self, sample_table):
        """测试 render_table 抛出 NotImplementedError。"""
        renderer = BaseRenderer()
        with pytest.raises(NotImplementedError):
            renderer.render_table(sample_table)

    def test_render_figure_not_implemented(self, sample_figure):
        """测试 render_figure 抛出 NotImplementedError。"""
        renderer = BaseRenderer()
        with pytest.raises(NotImplementedError):
            renderer.render_figure(sample_figure)

    def test_render_references_not_implemented(self, sample_references):
        """测试 render_references 抛出 NotImplementedError。"""
        renderer = BaseRenderer()
        with pytest.raises(NotImplementedError):
            renderer.render_references(sample_references)


# ===== Markdown 渲染器测试 =====


class TestMarkdownRenderer:
    """MarkdownRenderer 测试。"""

    def test_render_title(self, sample_document):
        """测试标题渲染。"""
        renderer = MarkdownRenderer()
        md = renderer.render(sample_document)
        assert "# 深度学习在自然语言处理中的应用研究" in md

    def test_render_abstract(self, sample_document):
        """测试摘要渲染。"""
        renderer = MarkdownRenderer()
        md = renderer.render(sample_document)
        assert "## 摘要" in md
        assert sample_document.abstract in md

    def test_render_keywords(self, sample_document):
        """测试关键词渲染。"""
        renderer = MarkdownRenderer()
        md = renderer.render(sample_document)
        assert "**关键词**" in md
        assert "深度学习" in md

    def test_render_toc(self, sample_document):
        """测试目录渲染。"""
        renderer = MarkdownRenderer()
        md = renderer.render(sample_document)
        assert "## 目录" in md
        assert "[引言]" in md

    def test_render_sections(self, sample_document):
        """测试章节渲染。"""
        renderer = MarkdownRenderer()
        md = renderer.render(sample_document)
        assert "## 引言" in md
        assert "### 研究背景" in md
        assert "### 研究意义" in md
        assert "## 方法" in md

    def test_render_table(self, sample_document):
        """测试表格渲染。"""
        renderer = MarkdownRenderer()
        md = renderer.render(sample_document)
        assert "| 模型 | 准确率 | F1 分数 |" in md
        assert "| --- |" in md
        assert "BERT" in md
        assert "94.5%" in md

    def test_render_figure(self, sample_document):
        """测试图片渲染。"""
        renderer = MarkdownRenderer()
        md = renderer.render(sample_document)
        assert "![模型架构示意图](images/arch.png)" in md
        assert "*图：图1：模型架构图*" in md

    def test_render_references(self, sample_document):
        """测试参考文献渲染。"""
        renderer = MarkdownRenderer()
        md = renderer.render(sample_document)
        assert "## 参考文献" in md
        assert "[1] Vaswani" in md
        assert "[2] Devlin" in md

    def test_render_empty_document(self, empty_document):
        """测试空文档渲染。"""
        renderer = MarkdownRenderer()
        md = renderer.render(empty_document)
        assert md == ""

    def test_render_without_toc(self, sample_document):
        """测试不包含目录的渲染。"""
        opts = ExportOptions(include_toc=False)
        renderer = MarkdownRenderer(opts)
        md = renderer.render(sample_document)
        assert "## 目录" not in md

    def test_render_without_references(self, sample_document):
        """测试不包含参考文献的渲染。"""
        opts = ExportOptions(include_references=False)
        renderer = MarkdownRenderer(opts)
        md = renderer.render(sample_document)
        assert "## 参考文献" not in md

    def test_render_without_tables(self, sample_document):
        """测试不包含表格的渲染。"""
        opts = ExportOptions(include_tables=False)
        renderer = MarkdownRenderer(opts)
        md = renderer.render(sample_document)
        assert "| 模型 |" not in md

    def test_render_without_figures(self, sample_document):
        """测试不包含图片的渲染。"""
        opts = ExportOptions(include_figures=False)
        renderer = MarkdownRenderer(opts)
        md = renderer.render(sample_document)
        assert "![模型架构示意图]" not in md

    def test_render_table_caption(self, sample_table):
        """测试表格标题渲染。"""
        renderer = MarkdownRenderer()
        result = renderer.render_table(sample_table)
        assert "**表1：模型性能对比**" in result

    def test_render_table_empty_headers(self):
        """测试空表头表格。"""
        renderer = MarkdownRenderer()
        table = DocumentTable()
        result = renderer.render_table(table)
        assert result == ""

    def test_render_figure_without_image(self):
        """测试无路径图片渲染。"""
        renderer = MarkdownRenderer()
        fig = DocumentFigure(caption="测试图", alt_text="替代文本")
        result = renderer.render_figure(fig)
        assert "_[图片: 测试图]_" in result

    def test_render_metadata(self, sample_document):
        """测试元数据渲染。"""
        renderer = MarkdownRenderer()
        md = renderer.render(sample_document)
        assert "**作者**: 张三" in md
        assert "**日期**: 2026-06-19" in md

    def test_render_section_level_limit(self):
        """测试章节层级限制。"""
        renderer = MarkdownRenderer()
        # 创建深层嵌套章节
        deep_section = DocumentSection(title="深层", level=1)
        current = deep_section
        for _ in range(10):
            sub = DocumentSection(title="子章节", level=1)
            current.subsections.append(sub)
            current = sub
        result = renderer.render_section(deep_section, level=1)
        # Markdown 最多 6 个 #
        assert "###### 子章节" in result


# ===== HTML 渲染器测试 =====


class TestHTMLRenderer:
    """HTMLRenderer 测试。"""

    def test_render_doctype(self, sample_document):
        """测试 DOCTYPE 声明。"""
        renderer = HTMLRenderer()
        html = renderer.render(sample_document)
        assert "<!DOCTYPE html>" in html
        assert '<html lang="zh-CN">' in html

    def test_render_head(self, sample_document):
        """测试 head 部分。"""
        renderer = HTMLRenderer()
        html = renderer.render(sample_document)
        assert "<head>" in html
        assert '<meta charset="utf-8">' in html
        assert "<title>深度学习在自然语言处理中的应用研究</title>" in html
        assert "<style>" in html

    def test_render_css(self, sample_document):
        """测试 CSS 样式嵌入。"""
        renderer = HTMLRenderer()
        html = renderer.render(sample_document)
        assert DEFAULT_CSS in html

    def test_render_title_h1(self, sample_document):
        """测试标题 h1 渲染。"""
        renderer = HTMLRenderer()
        html = renderer.render(sample_document)
        assert "<h1>深度学习在自然语言处理中的应用研究</h1>" in html

    def test_render_metadata_div(self, sample_document):
        """测试元数据 div 渲染。"""
        renderer = HTMLRenderer()
        html = renderer.render(sample_document)
        assert '<div class="metadata">' in html
        assert "<strong>作者</strong>: 张三" in html

    def test_render_abstract_div(self, sample_document):
        """测试摘要 div 渲染。"""
        renderer = HTMLRenderer()
        html = renderer.render(sample_document)
        assert '<div class="abstract">' in html
        assert "<h2>摘要</h2>" in html

    def test_render_keywords_div(self, sample_document):
        """测试关键词 div 渲染。"""
        renderer = HTMLRenderer()
        html = renderer.render(sample_document)
        assert '<div class="keywords">' in html

    def test_render_toc_div(self, sample_document):
        """测试目录 div 渲染。"""
        renderer = HTMLRenderer()
        html = renderer.render(sample_document)
        assert '<div class="toc">' in html
        assert "<h2>目录</h2>" in html

    def test_render_sections(self, sample_document):
        """测试章节渲染。"""
        renderer = HTMLRenderer()
        html = renderer.render(sample_document)
        assert "<section" in html
        assert "<h2>引言</h2>" in html
        assert "<h3>研究背景</h3>" in html

    def test_render_table_html(self, sample_document):
        """测试 HTML 表格渲染。"""
        renderer = HTMLRenderer()
        html = renderer.render(sample_document)
        assert "<table>" in html
        assert "<thead>" in html
        assert "<th>模型</th>" in html
        assert "<td>BERT</td>" in html

    def test_render_figure_html(self, sample_document):
        """测试 HTML 图片渲染。"""
        renderer = HTMLRenderer()
        html = renderer.render(sample_document)
        assert '<div class="figure">' in html
        assert "<img" in html
        assert 'src="images/arch.png"' in html

    def test_render_references_html(self, sample_document):
        """测试 HTML 参考文献渲染。"""
        renderer = HTMLRenderer()
        html = renderer.render(sample_document)
        assert '<div class="references">' in html
        assert "<h2>参考文献</h2>" in html

    def test_html_escape(self):
        """测试 HTML 转义。"""
        renderer = HTMLRenderer()
        doc = Document(title="<script>alert('xss')</script>")
        html = renderer.render(doc)
        assert "<script>alert" not in html
        assert "&lt;script&gt;" in html

    def test_render_empty_document(self, empty_document):
        """测试空文档渲染。"""
        renderer = HTMLRenderer()
        html = renderer.render(empty_document)
        assert "<!DOCTYPE html>" in html
        assert "<html" in html

    def test_render_without_metadata(self, sample_document):
        """测试不包含元数据的渲染。"""
        opts = ExportOptions(include_metadata=False)
        renderer = HTMLRenderer(opts)
        html = renderer.render(sample_document)
        assert '<div class="metadata">' not in html

    def test_render_table_with_caption(self, sample_table):
        """测试带标题表格渲染。"""
        renderer = HTMLRenderer()
        result = renderer.render_table(sample_table)
        assert "<caption>表1：模型性能对比</caption>" in result


# ===== LaTeX 渲染器测试 =====


class TestLaTeXRenderer:
    """LaTeXRenderer 测试。"""

    def test_render_documentclass(self, sample_document):
        """测试 documentclass 渲染。"""
        renderer = LaTeXRenderer()
        latex = renderer.render(sample_document)
        assert "\\documentclass" in latex
        assert "\\begin{document}" in latex
        assert "\\end{document}" in latex

    def test_render_title_author_date(self, sample_document):
        """测试标题作者日期渲染。"""
        renderer = LaTeXRenderer()
        latex = renderer.render(sample_document)
        assert "\\title{" in latex
        assert "\\author{" in latex
        assert "\\maketitle" in latex

    def test_render_abstract(self, sample_document):
        """测试摘要渲染。"""
        renderer = LaTeXRenderer()
        latex = renderer.render(sample_document)
        assert "\\begin{abstract}" in latex
        assert "\\end{abstract}" in latex

    def test_render_keywords(self, sample_document):
        """测试关键词渲染。"""
        renderer = LaTeXRenderer()
        latex = renderer.render(sample_document)
        assert "\\paragraph{关键词}" in latex

    def test_render_sections(self, sample_document):
        """测试章节渲染。"""
        renderer = LaTeXRenderer()
        latex = renderer.render(sample_document)
        assert "\\section{引言}" in latex
        assert "\\subsection{研究背景}" in latex
        assert "\\subsection{研究意义}" in latex
        assert "\\section{方法}" in latex

    def test_render_table_latex(self, sample_document):
        """测试 LaTeX 表格渲染。"""
        renderer = LaTeXRenderer()
        latex = renderer.render(sample_document)
        assert "\\begin{table}" in latex
        assert "\\begin{tabular}" in latex
        assert "\\toprule" in latex
        assert "\\midrule" in latex
        assert "\\bottomrule" in latex

    def test_render_figure_latex(self, sample_document):
        """测试 LaTeX 图片渲染。"""
        renderer = LaTeXRenderer()
        latex = renderer.render(sample_document)
        assert "\\begin{figure}" in latex
        assert "\\includegraphics" in latex
        assert "\\caption{" in latex

    def test_render_references_latex(self, sample_document):
        """测试 LaTeX 参考文献渲染。"""
        renderer = LaTeXRenderer()
        latex = renderer.render(sample_document)
        assert "\\begin{thebibliography}" in latex
        assert "\\end{thebibliography}" in latex
        assert "\\bibitem" in latex

    def test_latex_escape(self):
        """测试 LaTeX 特殊字符转义。"""
        renderer = LaTeXRenderer()
        doc = Document(title="测试 100% 的效果 & 其他#1")
        latex = renderer.render(doc)
        assert "\\%" in latex
        assert "\\&" in latex
        assert "\\#" in latex

    def test_custom_template(self):
        """测试自定义模板。"""
        custom_template = r"\documentclass{article}\title{__TITLE__}\begin{document}__CONTENT__\end{document}"
        renderer = LaTeXRenderer(template=custom_template)
        doc = Document(title="测试标题")
        latex = renderer.render(doc)
        assert "\\title{测试标题}" in latex

    def test_render_empty_document(self, empty_document):
        """测试空文档渲染。"""
        renderer = LaTeXRenderer()
        latex = renderer.render(empty_document)
        assert "\\documentclass" in latex
        assert "\\begin{document}" in latex

    def test_section_level_commands(self):
        """测试不同层级章节命令。"""
        renderer = LaTeXRenderer()
        section = DocumentSection(
            title="一级",
            level=1,
            subsections=[
                DocumentSection(
                    title="二级",
                    level=2,
                    subsections=[
                        DocumentSection(title="三级", level=3),
                    ],
                ),
            ],
        )
        result = renderer.render_section(section, level=1)
        assert "\\section{一级}" in result
        assert "\\subsection{二级}" in result
        assert "\\subsubsection{三级}" in result


# ===== 纯文本渲染器测试 =====


class TestTextRenderer:
    """TextRenderer 测试。"""

    def test_render_title(self, sample_document):
        """测试标题渲染。"""
        renderer = TextRenderer()
        text = renderer.render(sample_document)
        assert sample_document.title in text
        assert "=" in text

    def test_render_metadata(self, sample_document):
        """测试元数据渲染。"""
        renderer = TextRenderer()
        text = renderer.render(sample_document)
        assert "作者: 张三" in text
        assert "日期: 2026-06-19" in text

    def test_render_abstract(self, sample_document):
        """测试摘要渲染。"""
        renderer = TextRenderer()
        text = renderer.render(sample_document)
        assert "【摘要】" in text
        assert sample_document.abstract in text

    def test_render_keywords(self, sample_document):
        """测试关键词渲染。"""
        renderer = TextRenderer()
        text = renderer.render(sample_document)
        assert "关键词:" in text
        assert "深度学习" in text

    def test_render_sections(self, sample_document):
        """测试章节渲染。"""
        renderer = TextRenderer()
        text = renderer.render(sample_document)
        assert "# 引言" in text
        assert "## 研究背景" in text
        assert "# 方法" in text

    def test_render_table_text(self, sample_document):
        """测试纯文本表格渲染。"""
        renderer = TextRenderer()
        text = renderer.render(sample_document)
        assert "+" in text
        assert "|" in text
        assert "BERT" in text

    def test_render_references_text(self, sample_document):
        """测试纯文本参考文献渲染。"""
        renderer = TextRenderer()
        text = renderer.render(sample_document)
        assert "【参考文献】" in text
        assert "[1] Vaswani" in text

    def test_render_empty_document(self, empty_document):
        """测试空文档渲染。"""
        renderer = TextRenderer()
        text = renderer.render(empty_document)
        assert text == ""

    def test_table_ascii_format(self, sample_table):
        """测试 ASCII 表格格式。"""
        renderer = TextRenderer()
        result = renderer.render_table(sample_table)
        lines = result.split("\n")
        # 应包含分隔线
        assert any(line.startswith("+") and line.endswith("+") for line in lines)
        # 应包含表头行
        assert any("模型" in line for line in lines)


# ===== JSON 渲染器测试 =====


class TestJSONRenderer:
    """JSONRenderer 测试。"""

    def test_render_valid_json(self, sample_document):
        """测试生成有效 JSON。"""
        renderer = JSONRenderer()
        json_str = renderer.render(sample_document)
        parsed = json.loads(json_str)
        assert parsed["title"] == sample_document.title
        assert parsed["author"] == sample_document.author

    def test_render_export_metadata(self, sample_document):
        """测试导出元数据。"""
        renderer = JSONRenderer()
        json_str = renderer.render(sample_document)
        parsed = json.loads(json_str)
        assert "_export_metadata" in parsed
        assert parsed["_export_metadata"]["exporter"] == "ThesisMiner v8.0"
        assert parsed["_export_metadata"]["format"] == "json"

    def test_render_sections(self, sample_document):
        """测试章节渲染。"""
        renderer = JSONRenderer()
        json_str = renderer.render(sample_document)
        parsed = json.loads(json_str)
        assert len(parsed["sections"]) == 2
        assert parsed["sections"][0]["title"] == "引言"

    def test_render_tables(self, sample_document):
        """测试表格渲染。"""
        renderer = JSONRenderer()
        json_str = renderer.render(sample_document)
        parsed = json.loads(json_str)
        assert len(parsed["tables"]) == 1
        assert parsed["tables"][0]["headers"] == ["模型", "准确率", "F1 分数"]

    def test_render_empty_document(self, empty_document):
        """测试空文档渲染。"""
        renderer = JSONRenderer()
        json_str = renderer.render(empty_document)
        parsed = json.loads(json_str)
        assert parsed["title"] == ""
        assert "_export_metadata" in parsed

    def test_render_section_json(self, simple_section):
        """测试单个章节 JSON 渲染。"""
        renderer = JSONRenderer()
        json_str = renderer.render_section(simple_section)
        parsed = json.loads(json_str)
        assert parsed["title"] == "引言"

    def test_render_table_json(self, sample_table):
        """测试单个表格 JSON 渲染。"""
        renderer = JSONRenderer()
        json_str = renderer.render_table(sample_table)
        parsed = json.loads(json_str)
        assert parsed["caption"] == "表1：模型性能对比"

    def test_render_references_json(self, sample_references):
        """测试参考文献 JSON 渲染。"""
        renderer = JSONRenderer()
        json_str = renderer.render_references(sample_references)
        parsed = json.loads(json_str)
        assert len(parsed) == 2
        assert parsed[0]["ref_id"] == "1"

    def test_chinese_not_escaped(self, sample_document):
        """测试中文不被转义。"""
        renderer = JSONRenderer()
        json_str = renderer.render(sample_document)
        assert "深度学习" in json_str
        assert "\\u" not in json_str


# ===== DOCX 渲染器测试 =====


class TestDOCXRenderer:
    """DOCXRenderer 测试。"""

    def test_render_returns_xml(self, sample_document):
        """测试 render 返回 XML 字符串。"""
        renderer = DOCXRenderer()
        result = renderer.render(sample_document)
        assert isinstance(result, str)
        assert "<w:document" in result
        assert "<w:body>" in result

    def test_render_to_bytes_returns_zip(self, sample_document):
        """测试 render_to_bytes 返回 ZIP 数据。"""
        renderer = DOCXRenderer()
        data = renderer.render_to_bytes(sample_document)
        assert isinstance(data, bytes)
        assert len(data) > 0
        # ZIP 文件以 PK 开头
        assert data[:2] == b"PK"

    def test_docx_is_valid_zip(self, sample_document):
        """测试 DOCX 是有效的 ZIP 文件。"""
        renderer = DOCXRenderer()
        data = renderer.render_to_bytes(sample_document)
        buffer = io.BytesIO(data)
        with zipfile.ZipFile(buffer, "r") as zf:
            names = zf.namelist()
            # 应包含必需的 OOXML 文件
            assert "[Content_Types].xml" in names
            assert "_rels/.rels" in names
            assert "word/document.xml" in names
            assert "word/styles.xml" in names
            assert "docProps/core.xml" in names
            assert "docProps/app.xml" in names

    def test_docx_contains_title(self, sample_document):
        """测试 DOCX 包含标题。"""
        renderer = DOCXRenderer()
        data = renderer.render_to_bytes(sample_document)
        buffer = io.BytesIO(data)
        with zipfile.ZipFile(buffer, "r") as zf:
            doc_xml = zf.read("word/document.xml").decode("utf-8")
        assert sample_document.title in doc_xml

    def test_docx_contains_sections(self, sample_document):
        """测试 DOCX 包含章节。"""
        renderer = DOCXRenderer()
        data = renderer.render_to_bytes(sample_document)
        buffer = io.BytesIO(data)
        with zipfile.ZipFile(buffer, "r") as zf:
            doc_xml = zf.read("word/document.xml").decode("utf-8")
        assert "引言" in doc_xml
        assert "研究背景" in doc_xml

    def test_docx_contains_references(self, sample_document):
        """测试 DOCX 包含参考文献。"""
        renderer = DOCXRenderer()
        data = renderer.render_to_bytes(sample_document)
        buffer = io.BytesIO(data)
        with zipfile.ZipFile(buffer, "r") as zf:
            doc_xml = zf.read("word/document.xml").decode("utf-8")
        assert "参考文献" in doc_xml
        assert "Vaswani" in doc_xml

    def test_docx_core_xml_contains_title(self, sample_document):
        """测试 core.xml 包含标题。"""
        renderer = DOCXRenderer()
        data = renderer.render_to_bytes(sample_document)
        buffer = io.BytesIO(data)
        with zipfile.ZipFile(buffer, "r") as zf:
            core_xml = zf.read("docProps/core.xml").decode("utf-8")
        assert sample_document.title in core_xml
        assert sample_document.author in core_xml

    def test_docx_app_xml(self, sample_document):
        """测试 app.xml 内容。"""
        renderer = DOCXRenderer()
        data = renderer.render_to_bytes(sample_document)
        buffer = io.BytesIO(data)
        with zipfile.ZipFile(buffer, "r") as zf:
            app_xml = zf.read("docProps/app.xml").decode("utf-8")
        assert "ThesisMiner" in app_xml

    def test_docx_empty_document(self, empty_document):
        """测试空文档 DOCX 生成。"""
        renderer = DOCXRenderer()
        data = renderer.render_to_bytes(empty_document)
        assert data[:2] == b"PK"
        assert len(data) > 0

    def test_docx_table_xml(self, sample_table):
        """测试表格 XML 生成。"""
        renderer = DOCXRenderer()
        result = renderer.render_table(sample_table)
        assert "<w:tbl>" in result
        assert "<w:tr>" in result
        assert "<w:tc>" in result


# ===== PDF 渲染器测试 =====


class TestPDFRenderer:
    """PDFRenderer 测试。"""

    def test_render_returns_text(self, sample_document):
        """测试 render 返回文本预览。"""
        renderer = PDFRenderer()
        result = renderer.render(sample_document)
        assert isinstance(result, str)
        assert sample_document.title in result

    def test_render_to_bytes_returns_pdf(self, sample_document):
        """测试 render_to_bytes 返回 PDF 数据。"""
        renderer = PDFRenderer()
        data = renderer.render_to_bytes(sample_document)
        assert isinstance(data, bytes)
        assert len(data) > 0
        # PDF 文件以 %PDF- 开头
        assert data[:5] == b"%PDF-"

    def test_pdf_contains_version(self, sample_document):
        """测试 PDF 包含版本号。"""
        renderer = PDFRenderer()
        data = renderer.render_to_bytes(sample_document)
        assert b"%PDF-1.4" in data

    def test_pdf_contains_eof(self, sample_document):
        """测试 PDF 包含 EOF 标记。"""
        renderer = PDFRenderer()
        data = renderer.render_to_bytes(sample_document)
        assert b"%%EOF" in data

    def test_pdf_contains_xref(self, sample_document):
        """测试 PDF 包含 xref 表。"""
        renderer = PDFRenderer()
        data = renderer.render_to_bytes(sample_document)
        assert b"xref" in data
        assert b"trailer" in data

    def test_pdf_contains_objects(self, sample_document):
        """测试 PDF 包含对象。"""
        renderer = PDFRenderer()
        data = renderer.render_to_bytes(sample_document)
        assert b"obj" in data
        assert b"endobj" in data
        assert b"Catalog" in data or b"/Catalog" in data
        assert b"Pages" in data or b"/Pages" in data

    def test_pdf_empty_document(self, empty_document):
        """测试空文档 PDF 生成。"""
        renderer = PDFRenderer()
        data = renderer.render_to_bytes(empty_document)
        assert data[:5] == b"%PDF-"
        assert b"%%EOF" in data

    def test_pdf_font_definition(self, sample_document):
        """测试 PDF 字体定义。"""
        renderer = PDFRenderer()
        data = renderer.render_to_bytes(sample_document)
        assert b"/Font" in data
        assert b"/F1" in data
        assert b"Helvetica" in data


# ===== DocumentExporter 单例测试 =====


class TestDocumentExporterSingleton:
    """DocumentExporter 单例模式测试。"""

    def test_singleton_identity(self):
        """测试单例身份一致性。"""
        exporter1 = DocumentExporter()
        exporter2 = DocumentExporter()
        assert exporter1 is exporter2

    def test_get_instance(self):
        """测试 get_instance 方法。"""
        exporter1 = DocumentExporter.get_instance()
        exporter2 = DocumentExporter.get_instance()
        assert exporter1 is exporter2

    def test_reset_instance(self):
        """测试 reset_instance 方法。"""
        exporter1 = DocumentExporter()
        DocumentExporter.reset_instance()
        exporter2 = DocumentExporter()
        assert exporter1 is not exporter2

    def test_list_supported_formats(self):
        """测试列出支持格式。"""
        exporter = DocumentExporter()
        formats = exporter.list_supported_formats()
        assert "markdown" in formats
        assert "html" in formats
        assert "pdf" in formats
        assert "docx" in formats
        assert "latex" in formats
        assert "text" in formats
        assert "json" in formats
        assert len(formats) == 7


# ===== DocumentExporter 导出测试 =====


class TestDocumentExporterExport:
    """DocumentExporter 导出方法测试。"""

    def test_export_markdown(self, sample_document):
        """测试 Markdown 导出。"""
        exporter = DocumentExporter()
        result = exporter.export(sample_document, ExportFormat.MARKDOWN)
        assert result.success is True
        assert result.format == "markdown"
        assert "# 深度学习" in result.content
        assert len(result.content) > 0

    def test_export_html(self, sample_document):
        """测试 HTML 导出。"""
        exporter = DocumentExporter()
        result = exporter.export(sample_document, ExportFormat.HTML)
        assert result.success is True
        assert "<!DOCTYPE html>" in result.content

    def test_export_latex(self, sample_document):
        """测试 LaTeX 导出。"""
        exporter = DocumentExporter()
        result = exporter.export(sample_document, ExportFormat.LATEX)
        assert result.success is True
        assert "\\documentclass" in result.content

    def test_export_text(self, sample_document):
        """测试纯文本导出。"""
        exporter = DocumentExporter()
        result = exporter.export(sample_document, ExportFormat.TEXT)
        assert result.success is True
        assert sample_document.title in result.content

    def test_export_json(self, sample_document):
        """测试 JSON 导出。"""
        exporter = DocumentExporter()
        result = exporter.export(sample_document, ExportFormat.JSON)
        assert result.success is True
        parsed = json.loads(result.content)
        assert parsed["title"] == sample_document.title

    def test_export_with_string_format(self, sample_document):
        """测试使用字符串格式导出。"""
        exporter = DocumentExporter()
        result = exporter.export(sample_document, "markdown")
        assert result.success is True
        assert result.format == "markdown"

    def test_export_unsupported_format(self, sample_document):
        """测试不支持的格式。"""
        exporter = DocumentExporter()
        result = exporter.export(sample_document, "unsupported")
        assert result.success is False
        assert "不支持" in result.error_message

    def test_export_with_custom_options(self, sample_document):
        """测试使用自定义选项导出。"""
        exporter = DocumentExporter()
        opts = ExportOptions(include_toc=False, include_metadata=False)
        result = exporter.export(sample_document, ExportFormat.MARKDOWN, opts)
        assert result.success is True
        assert "## 目录" not in result.content

    def test_export_markdown_method(self, sample_document):
        """测试 export_markdown 便捷方法。"""
        exporter = DocumentExporter()
        md = exporter.export_markdown(sample_document)
        assert "# 深度学习" in md

    def test_export_html_method(self, sample_document):
        """测试 export_html 便捷方法。"""
        exporter = DocumentExporter()
        html = exporter.export_html(sample_document)
        assert "<!DOCTYPE html>" in html

    def test_export_latex_method(self, sample_document):
        """测试 export_latex 便捷方法。"""
        exporter = DocumentExporter()
        latex = exporter.export_latex(sample_document)
        assert "\\documentclass" in latex

    def test_export_text_method(self, sample_document):
        """测试 export_text 便捷方法。"""
        exporter = DocumentExporter()
        text = exporter.export_text(sample_document)
        assert sample_document.title in text

    def test_export_json_method(self, sample_document):
        """测试 export_json 便捷方法。"""
        exporter = DocumentExporter()
        json_str = exporter.export_json(sample_document)
        parsed = json.loads(json_str)
        assert parsed["title"] == sample_document.title

    def test_export_docx_bytes(self, sample_document):
        """测试 DOCX 二进制导出。"""
        exporter = DocumentExporter()
        data = exporter.export_docx_bytes(sample_document)
        assert isinstance(data, bytes)
        assert data[:2] == b"PK"

    def test_export_pdf_bytes(self, sample_document):
        """测试 PDF 二进制导出。"""
        exporter = DocumentExporter()
        data = exporter.export_pdf_bytes(sample_document)
        assert isinstance(data, bytes)
        assert data[:5] == b"%PDF-"

    def test_export_result_metadata(self, sample_document):
        """测试导出结果元数据。"""
        exporter = DocumentExporter()
        result = exporter.export(sample_document, ExportFormat.MARKDOWN)
        assert "exported_at" in result.metadata
        assert result.metadata["format"] == "markdown"
        assert result.metadata["content_length"] == len(result.content)


# ===== 文件导出测试 =====


class TestDocumentExporterFileExport:
    """DocumentExporter 文件导出测试。"""

    def test_export_to_file_markdown(self, sample_document, tmp_path):
        """测试导出 Markdown 文件。"""
        exporter = DocumentExporter()
        file_path = str(tmp_path / "test.md")
        result = exporter.export_to_file(sample_document, file_path, ExportFormat.MARKDOWN)
        assert result.success is True
        assert Path(file_path).exists()
        assert result.file_path == file_path
        assert result.file_size > 0

    def test_export_to_file_html(self, sample_document, tmp_path):
        """测试导出 HTML 文件。"""
        exporter = DocumentExporter()
        file_path = str(tmp_path / "test.html")
        result = exporter.export_to_file(sample_document, file_path, ExportFormat.HTML)
        assert result.success is True
        assert Path(file_path).exists()

    def test_export_to_file_latex(self, sample_document, tmp_path):
        """测试导出 LaTeX 文件。"""
        exporter = DocumentExporter()
        file_path = str(tmp_path / "test.tex")
        result = exporter.export_to_file(sample_document, file_path, ExportFormat.LATEX)
        assert result.success is True
        assert Path(file_path).exists()

    def test_export_to_file_text(self, sample_document, tmp_path):
        """测试导出文本文件。"""
        exporter = DocumentExporter()
        file_path = str(tmp_path / "test.txt")
        result = exporter.export_to_file(sample_document, file_path, ExportFormat.TEXT)
        assert result.success is True
        assert Path(file_path).exists()

    def test_export_to_file_json(self, sample_document, tmp_path):
        """测试导出 JSON 文件。"""
        exporter = DocumentExporter()
        file_path = str(tmp_path / "test.json")
        result = exporter.export_to_file(sample_document, file_path, ExportFormat.JSON)
        assert result.success is True
        assert Path(file_path).exists()
        content = Path(file_path).read_text(encoding="utf-8")
        parsed = json.loads(content)
        assert parsed["title"] == sample_document.title

    def test_export_to_file_docx(self, sample_document, tmp_path):
        """测试导出 DOCX 文件。"""
        exporter = DocumentExporter()
        file_path = str(tmp_path / "test.docx")
        result = exporter.export_to_file(sample_document, file_path, ExportFormat.DOCX)
        assert result.success is True
        assert Path(file_path).exists()
        data = Path(file_path).read_bytes()
        assert data[:2] == b"PK"

    def test_export_to_file_pdf(self, sample_document, tmp_path):
        """测试导出 PDF 文件。"""
        exporter = DocumentExporter()
        file_path = str(tmp_path / "test.pdf")
        result = exporter.export_to_file(sample_document, file_path, ExportFormat.PDF)
        assert result.success is True
        assert Path(file_path).exists()
        data = Path(file_path).read_bytes()
        assert data[:5] == b"%PDF-"

    def test_export_to_file_infer_format(self, sample_document, tmp_path):
        """测试根据扩展名推断格式。"""
        exporter = DocumentExporter()
        file_path = str(tmp_path / "inferred.md")
        result = exporter.export_to_file(sample_document, file_path)
        assert result.success is True
        assert result.format == "markdown"

    def test_export_to_file_creates_parent_dir(self, sample_document, tmp_path):
        """测试自动创建父目录。"""
        exporter = DocumentExporter()
        file_path = str(tmp_path / "subdir" / "nested" / "test.md")
        result = exporter.export_to_file(sample_document, file_path, ExportFormat.MARKDOWN)
        assert result.success is True
        assert Path(file_path).exists()

    def test_export_to_file_empty_document(self, empty_document, tmp_path):
        """测试空文档文件导出。"""
        exporter = DocumentExporter()
        file_path = str(tmp_path / "empty.md")
        result = exporter.export_to_file(empty_document, file_path, ExportFormat.MARKDOWN)
        assert result.success is True


# ===== 批量导出与 ZIP 打包测试 =====


class TestDocumentExporterBatchExport:
    """DocumentExporter 批量导出测试。"""

    def test_export_batch_markdown(self, sample_document, tmp_path):
        """测试批量导出 Markdown。"""
        exporter = DocumentExporter()
        docs = [("doc1", sample_document), ("doc2", sample_document)]
        results = exporter.export_batch(docs, str(tmp_path), ExportFormat.MARKDOWN)
        assert len(results) == 2
        assert all(r.success for r in results)
        assert Path(tmp_path / "doc1.md").exists()
        assert Path(tmp_path / "doc2.md").exists()

    def test_export_batch_html(self, sample_document, tmp_path):
        """测试批量导出 HTML。"""
        exporter = DocumentExporter()
        docs = [("doc1", sample_document), ("doc2", sample_document)]
        results = exporter.export_batch(docs, str(tmp_path), ExportFormat.HTML)
        assert len(results) == 2
        assert all(r.success for r in results)
        assert Path(tmp_path / "doc1.html").exists()

    def test_export_batch_docx(self, sample_document, tmp_path):
        """测试批量导出 DOCX。"""
        exporter = DocumentExporter()
        docs = [("doc1", sample_document), ("doc2", sample_document)]
        results = exporter.export_batch(docs, str(tmp_path), ExportFormat.DOCX)
        assert len(results) == 2
        assert all(r.success for r in results)
        assert Path(tmp_path / "doc1.docx").exists()

    def test_export_batch_pdf(self, sample_document, tmp_path):
        """测试批量导出 PDF。"""
        exporter = DocumentExporter()
        docs = [("doc1", sample_document), ("doc2", sample_document)]
        results = exporter.export_batch(docs, str(tmp_path), ExportFormat.PDF)
        assert len(results) == 2
        assert all(r.success for r in results)

    def test_export_batch_empty_list(self, tmp_path):
        """测试空列表批量导出。"""
        exporter = DocumentExporter()
        results = exporter.export_batch([], str(tmp_path), ExportFormat.MARKDOWN)
        assert len(results) == 0

    def test_export_to_zip_markdown(self, sample_document, tmp_path):
        """测试 ZIP 打包 Markdown。"""
        exporter = DocumentExporter()
        docs = [("doc1", sample_document), ("doc2", sample_document)]
        zip_path = str(tmp_path / "batch.zip")
        result = exporter.export_to_zip(docs, zip_path, ExportFormat.MARKDOWN)
        assert result.success is True
        assert Path(zip_path).exists()
        assert result.file_size > 0
        assert result.metadata["document_count"] == 2

    def test_export_to_zip_docx(self, sample_document, tmp_path):
        """测试 ZIP 打包 DOCX。"""
        exporter = DocumentExporter()
        docs = [("doc1", sample_document), ("doc2", sample_document)]
        zip_path = str(tmp_path / "batch.zip")
        result = exporter.export_to_zip(docs, zip_path, ExportFormat.DOCX)
        assert result.success is True
        assert Path(zip_path).exists()

    def test_export_to_zip_pdf(self, sample_document, tmp_path):
        """测试 ZIP 打包 PDF。"""
        exporter = DocumentExporter()
        docs = [("doc1", sample_document), ("doc2", sample_document)]
        zip_path = str(tmp_path / "batch.zip")
        result = exporter.export_to_zip(docs, zip_path, ExportFormat.PDF)
        assert result.success is True
        assert Path(zip_path).exists()

    def test_export_to_zip_content_verification(self, sample_document, tmp_path):
        """测试 ZIP 内容验证。"""
        exporter = DocumentExporter()
        docs = [("doc1", sample_document), ("doc2", sample_document)]
        zip_path = str(tmp_path / "batch.zip")
        result = exporter.export_to_zip(docs, zip_path, ExportFormat.MARKDOWN)
        assert result.success is True
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            assert "doc1.md" in names
            assert "doc2.md" in names
            content = zf.read("doc1.md").decode("utf-8")
            assert sample_document.title in content

    def test_export_to_zip_creates_parent_dir(self, sample_document, tmp_path):
        """测试 ZIP 自动创建父目录。"""
        exporter = DocumentExporter()
        docs = [("doc1", sample_document)]
        zip_path = str(tmp_path / "subdir" / "batch.zip")
        result = exporter.export_to_zip(docs, zip_path, ExportFormat.MARKDOWN)
        assert result.success is True
        assert Path(zip_path).exists()


# ===== 选项与模板测试 =====


class TestDocumentExporterOptions:
    """DocumentExporter 选项与模板测试。"""

    def test_set_options(self):
        """测试设置选项。"""
        exporter = DocumentExporter()
        opts = ExportOptions(include_toc=False)
        exporter.set_options(opts)
        assert exporter.get_options().include_toc is False

    def test_get_options(self):
        """测试获取选项。"""
        exporter = DocumentExporter()
        opts = exporter.get_options()
        assert isinstance(opts, ExportOptions)
        assert opts.include_toc is True

    def test_register_template(self):
        """测试注册模板。"""
        exporter = DocumentExporter()
        exporter.register_template("custom", "模板内容")
        assert "custom" in exporter._templates
        assert exporter._templates["custom"] == "模板内容"

    def test_set_options_affects_renderers(self, sample_document):
        """测试设置选项影响渲染器。"""
        exporter = DocumentExporter()
        opts = ExportOptions(include_toc=False, include_metadata=False)
        exporter.set_options(opts)
        md = exporter.export_markdown(sample_document)
        assert "## 目录" not in md
        assert "**作者**" not in md


# ===== 进度回调测试 =====


class TestProgressCallback:
    """进度回调测试。"""

    def test_add_progress_callback(self):
        """测试添加进度回调。"""
        exporter = DocumentExporter()
        callback = MagicMock()
        exporter.add_progress_callback(callback)
        assert callback in exporter._progress_callbacks

    def test_progress_callback_called(self, sample_document):
        """测试进度回调被调用。"""
        exporter = DocumentExporter()
        callback = MagicMock()
        exporter.add_progress_callback(callback)
        exporter.export(sample_document, ExportFormat.MARKDOWN)
        assert callback.call_count >= 2
        # 检查第一次调用参数
        first_call = callback.call_args_list[0]
        assert first_call[0][0] == 0  # current
        assert first_call[0][1] == 1  # total

    def test_progress_callback_batch(self, sample_document, tmp_path):
        """测试批量导出进度回调。"""
        exporter = DocumentExporter()
        callback = MagicMock()
        exporter.add_progress_callback(callback)
        docs = [("doc1", sample_document), ("doc2", sample_document)]
        exporter.export_batch(docs, str(tmp_path), ExportFormat.MARKDOWN)
        assert callback.call_count >= 3

    def test_progress_callback_exception_handling(self, sample_document):
        """测试进度回调异常处理。"""
        exporter = DocumentExporter()

        def failing_callback(current, total, message):
            raise RuntimeError("回调失败")

        exporter.add_progress_callback(failing_callback)
        # 不应抛出异常
        result = exporter.export(sample_document, ExportFormat.MARKDOWN)
        assert result.success is True

    def test_multiple_progress_callbacks(self, sample_document):
        """测试多个进度回调。"""
        exporter = DocumentExporter()
        cb1 = MagicMock()
        cb2 = MagicMock()
        exporter.add_progress_callback(cb1)
        exporter.add_progress_callback(cb2)
        exporter.export(sample_document, ExportFormat.MARKDOWN)
        assert cb1.call_count >= 2
        assert cb2.call_count >= 2


# ===== 文档合并与字典创建测试 =====


class TestDocumentMergeAndDict:
    """文档合并与字典创建测试。"""

    def test_create_document_from_dict(self, sample_document):
        """测试从字典创建文档。"""
        exporter = DocumentExporter()
        d = sample_document.to_dict()
        doc = exporter.create_document_from_dict(d)
        assert doc.title == sample_document.title
        assert doc.author == sample_document.author
        assert len(doc.sections) == len(sample_document.sections)

    def test_merge_documents(self, sample_document):
        """测试合并文档。"""
        exporter = DocumentExporter()
        doc2 = Document(
            title="第二个文档",
            sections=[DocumentSection(title="附录", content="附录内容")],
        )
        merged = exporter.merge_documents([sample_document, doc2])
        assert merged.title == sample_document.title
        assert len(merged.sections) == len(sample_document.sections) + 1

    def test_merge_documents_empty_list(self):
        """测试合并空列表。"""
        exporter = DocumentExporter()
        merged = exporter.merge_documents([])
        assert merged.title == ""
        assert merged.sections == []

    def test_merge_documents_preserves_first_metadata(self, sample_document):
        """测试合并保留第一个文档元数据。"""
        exporter = DocumentExporter()
        doc2 = Document(title="第二", abstract="第二摘要")
        merged = exporter.merge_documents([sample_document, doc2])
        assert merged.abstract == sample_document.abstract
        assert merged.keywords == sample_document.keywords

    def test_merge_documents_accumulates_sections(self):
        """测试合并累积章节。"""
        exporter = DocumentExporter()
        doc1 = Document(sections=[DocumentSection(title="第一章")])
        doc2 = Document(sections=[DocumentSection(title="第二章")])
        doc3 = Document(sections=[DocumentSection(title="第三章")])
        merged = exporter.merge_documents([doc1, doc2, doc3])
        assert len(merged.sections) == 3

    def test_merge_documents_accumulates_tables(self, sample_table):
        """测试合并累积表格。"""
        exporter = DocumentExporter()
        doc1 = Document(tables=[sample_table])
        doc2 = Document(tables=[sample_table])
        merged = exporter.merge_documents([doc1, doc2])
        assert len(merged.tables) == 2


# ===== 关闭与清理测试 =====


class TestDocumentExporterShutdown:
    """DocumentExporter 关闭测试。"""

    def test_shutdown_clears_callbacks(self):
        """测试关闭清理回调。"""
        exporter = DocumentExporter()
        callback = MagicMock()
        exporter.add_progress_callback(callback)
        assert len(exporter._progress_callbacks) == 1
        exporter.shutdown()
        assert len(exporter._progress_callbacks) == 0

    def test_shutdown_idempotent(self):
        """测试关闭可重复调用。"""
        exporter = DocumentExporter()
        exporter.shutdown()
        exporter.shutdown()  # 不应抛出异常


# ===== 模块级函数测试 =====


class TestModuleLevelFunctions:
    """模块级便捷函数测试。"""

    def test_get_document_exporter(self):
        """测试 get_document_exporter 函数。"""
        exporter = get_document_exporter()
        assert isinstance(exporter, DocumentExporter)

    def test_get_document_exporter_singleton(self):
        """测试 get_document_exporter 返回单例。"""
        exporter1 = get_document_exporter()
        exporter2 = get_document_exporter()
        assert exporter1 is exporter2

    def test_export_to_markdown_function(self, sample_document):
        """测试 export_to_markdown 函数。"""
        md = export_to_markdown(sample_document)
        assert "# 深度学习" in md

    def test_export_to_html_function(self, sample_document):
        """测试 export_to_html 函数。"""
        html = export_to_html(sample_document)
        assert "<!DOCTYPE html>" in html

    def test_export_to_file_function(self, sample_document, tmp_path):
        """测试 export_to_file 函数。"""
        file_path = str(tmp_path / "func_test.md")
        result = export_to_file(sample_document, file_path)
        assert result.success is True
        assert Path(file_path).exists()


# ===== 集成场景测试 =====


class TestIntegrationScenarios:
    """集成场景测试。"""

    def test_full_export_pipeline(self, sample_document, tmp_path):
        """测试完整导出流水线。"""
        exporter = DocumentExporter()
        # 导出所有格式
        formats = [
            (ExportFormat.MARKDOWN, "test.md"),
            (ExportFormat.HTML, "test.html"),
            (ExportFormat.LATEX, "test.tex"),
            (ExportFormat.TEXT, "test.txt"),
            (ExportFormat.JSON, "test.json"),
            (ExportFormat.DOCX, "test.docx"),
            (ExportFormat.PDF, "test.pdf"),
        ]
        for fmt, filename in formats:
            result = exporter.export_to_file(sample_document, str(tmp_path / filename), fmt)
            assert result.success is True, f"导出 {filename} 失败: {result.error_message}"
            assert Path(tmp_path / filename).exists()

    def test_export_with_progress_tracking(self, sample_document, tmp_path):
        """测试带进度跟踪的导出。"""
        exporter = DocumentExporter()
        progress_log = []

        def callback(current, total, message):
            progress_log.append((current, total, message))

        exporter.add_progress_callback(callback)
        docs = [("doc1", sample_document), ("doc2", sample_document)]
        exporter.export_batch(docs, str(tmp_path), ExportFormat.MARKDOWN)
        assert len(progress_log) >= 3
        # 最后一条应为完成消息
        assert progress_log[-1][0] == 2
        assert progress_log[-1][1] == 2

    def test_export_options_propagation(self, sample_document):
        """测试导出选项传播。"""
        exporter = DocumentExporter()
        opts = ExportOptions(
            include_toc=False,
            include_metadata=False,
            include_references=False,
            include_tables=False,
            include_figures=False,
        )
        md = exporter.export_markdown(sample_document, opts)
        assert "## 目录" not in md
        assert "**作者**" not in md
        assert "## 参考文献" not in md
        assert "| 模型 |" not in md
        assert "![模型架构示意图]" not in md

    def test_roundtrip_json_export_import(self, sample_document):
        """测试 JSON 导出导入往返。"""
        exporter = DocumentExporter()
        json_str = exporter.export_json(sample_document)
        parsed = json.loads(json_str)
        restored = Document.from_dict(parsed)
        assert restored.title == sample_document.title
        assert restored.author == sample_document.author
        assert len(restored.sections) == len(sample_document.sections)
        assert len(restored.tables) == len(sample_document.tables)

    def test_batch_zip_with_multiple_formats(self, sample_document, tmp_path):
        """测试多格式批量 ZIP 打包。"""
        exporter = DocumentExporter()
        docs = [("doc1", sample_document), ("doc2", sample_document), ("doc3", sample_document)]
        for fmt in [ExportFormat.MARKDOWN, ExportFormat.HTML, ExportFormat.TEXT]:
            zip_path = str(tmp_path / f"batch_{fmt.value}.zip")
            result = exporter.export_to_zip(docs, zip_path, fmt)
            assert result.success is True
            assert Path(zip_path).exists()
            with zipfile.ZipFile(zip_path, "r") as zf:
                assert len(zf.namelist()) == 3


# ===== 线程安全测试 =====


class TestThreadSafety:
    """线程安全测试。"""

    def test_concurrent_export_markdown(self, sample_document):
        """测试并发 Markdown 导出。"""
        exporter = DocumentExporter()
        results = []
        errors = []

        def worker():
            try:
                md = exporter.export_markdown(sample_document)
                results.append(md)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 5
        # 所有结果应一致
        assert all(r == results[0] for r in results)

    def test_concurrent_export_different_formats(self, sample_document):
        """测试并发不同格式导出。"""
        exporter = DocumentExporter()
        errors = []

        def worker(fmt):
            try:
                if fmt == ExportFormat.MARKDOWN:
                    exporter.export_markdown(sample_document)
                elif fmt == ExportFormat.HTML:
                    exporter.export_html(sample_document)
                elif fmt == ExportFormat.LATEX:
                    exporter.export_latex(sample_document)
                elif fmt == ExportFormat.TEXT:
                    exporter.export_text(sample_document)
                elif fmt == ExportFormat.JSON:
                    exporter.export_json(sample_document)
            except Exception as e:
                errors.append(e)

        formats = [ExportFormat.MARKDOWN, ExportFormat.HTML, ExportFormat.LATEX,
                   ExportFormat.TEXT, ExportFormat.JSON]
        threads = [threading.Thread(target=worker, args=(fmt,)) for fmt in formats]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_concurrent_docx_bytes(self, sample_document):
        """测试并发 DOCX 二进制导出。"""
        exporter = DocumentExporter()
        results = []
        errors = []

        def worker():
            try:
                data = exporter.export_docx_bytes(sample_document)
                results.append(data)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 3
        # 所有结果应为有效 ZIP
        for data in results:
            assert data[:2] == b"PK"

    def test_singleton_thread_safe(self):
        """测试单例线程安全。"""
        instances = []

        def worker():
            instances.append(DocumentExporter())

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 所有实例应为同一对象
        assert all(inst is instances[0] for inst in instances)
