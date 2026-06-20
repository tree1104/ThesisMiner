"""ThesisMiner 文档导出与报告生成模块

提供多种格式的文档导出与报告生成能力，包括：
    - Markdown / HTML / PDF / Word / LaTeX 导出
    - 开题报告 / 文献综述 / 答辩 PPT 大纲 / 进度报告生成
    - GB/T 7714 / APA / MLA / Chicago / IEEE 引用格式化

子模块：
    - document_exporter: 文档导出器
    - report_generator: 报告生成器
    - citation_formatter: 引用格式化器

设计原则：
    1. 零外部依赖：仅使用 Python 标准库实现核心逻辑
    2. 模板化：通过模板系统支持自定义格式
    3. 可扩展：新增格式只需实现对应渲染器
"""
from backend.export.document_exporter import (
    DocumentExporter,
    ExportFormat,
    get_document_exporter,
)
from backend.export.report_generator import (
    ReportGenerator,
    ReportType,
    get_report_generator,
)
from backend.export.citation_formatter import (
    CitationFormatter,
    CitationStyle,
    get_citation_formatter,
)

__all__ = [
    # 文档导出
    "DocumentExporter",
    "ExportFormat",
    "get_document_exporter",
    # 报告生成
    "ReportGenerator",
    "ReportType",
    "get_report_generator",
    # 引用格式化
    "CitationFormatter",
    "CitationStyle",
    "get_citation_formatter",
]
