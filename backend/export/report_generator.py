"""报告生成器模块

提供各类学术报告的生成能力，包括：
    - 开题报告（含研究背景、意义、内容、方法、进度等）
    - 文献综述（含文献梳理、研究脉络、对比分析）
    - 答辩 PPT 大纲（含幻灯片结构、要点、备注）
    - 进度报告（含已完成工作、待完成任务、问题与风险）
    - 自定义报告模板

支持多种输出格式（Markdown / HTML / LaTeX / 纯文本），
内置图表生成（ASCII 表格、Markdown 表格）、引用格式化。

典型用法：
    generator = ReportGenerator()
    report = generator.generate_proposal_report(proposal_data)
    ppt_outline = generator.generate_defense_ppt_outline(thesis_data)
    generator.export_report(report, "output.md", format="markdown")
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# 尝试导入日志
try:
    from backend.utils.logger import get_logger

    _logger = get_logger(__name__)
except Exception:  # pragma: no cover
    import logging

    _logger = logging.getLogger(__name__)

# 尝试导入文档导出器
try:
    from backend.export.document_exporter import (
        Document,
        DocumentExporter,
        DocumentReference,
        DocumentSection,
        DocumentTable,
        ExportFormat,
        ExportOptions,
    )

    _HAS_EXPORTER = True
except Exception:  # pragma: no cover
    _HAS_EXPORTER = False
    Document = None  # type: ignore
    DocumentExporter = None  # type: ignore
    DocumentReference = None  # type: ignore
    DocumentSection = None  # type: ignore
    DocumentTable = None  # type: ignore
    ExportFormat = None  # type: ignore
    ExportOptions = None  # type: ignore


# ===== 枚举与常量 =====


class ReportType(str, Enum):
    """报告类型枚举。"""

    PROPOSAL = "proposal"  # 开题报告
    LITERATURE_REVIEW = "literature_review"  # 文献综述
    DEFENSE_PPT = "defense_ppt"  # 答辩 PPT 大纲
    PROGRESS = "progress"  # 进度报告
    WEEKLY = "weekly"  # 周报
    MONTHLY = "monthly"  # 月报
    FINAL = "final"  # 结题报告
    CUSTOM = "custom"  # 自定义


# 默认报告模板配置
DEFAULT_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "proposal": {
        "title_template": "{degree}学位论文开题报告",
        "sections": [
            "封面信息",
            "研究背景与意义",
            "国内外研究现状",
            "研究目标与内容",
            "研究方法与技术路线",
            "创新点与特色",
            "研究计划与进度安排",
            "预期成果",
            "参考文献",
        ],
    },
    "literature_review": {
        "title_template": "文献综述：{topic}",
        "sections": [
            "引言",
            "研究背景",
            "文献检索策略",
            "研究主题分类",
            "研究脉络梳理",
            "对比分析",
            "研究空白与展望",
            "结论",
            "参考文献",
        ],
    },
    "defense_ppt": {
        "title_template": "{title} - 答辩报告",
        "sections": [
            "封面",
            "研究背景与问题",
            "研究目标",
            "相关工作",
            "研究方法",
            "实验与结果",
            "结论与创新点",
            "未来工作",
            "致谢",
        ],
    },
    "progress": {
        "title_template": "研究进度报告",
        "sections": [
            "基本信息",
            "已完成工作",
            "进行中工作",
            "待完成任务",
            "问题与风险",
            "下一步计划",
        ],
    },
    "weekly": {
        "title_template": "周报 - {week}",
        "sections": ["本周工作", "进展详情", "问题与困难", "下周计划"],
    },
    "monthly": {
        "title_template": "月报 - {month}",
        "sections": ["本月工作总结", "关键进展", "问题分析", "下月计划"],
    },
    "final": {
        "title_template": "结题报告 - {title}",
        "sections": [
            "项目概述",
            "研究目标完成情况",
            "主要研究成果",
            "创新点总结",
            "成果清单",
            "经费使用情况",
            "存在问题与改进",
            "后续工作展望",
        ],
    },
}


@dataclass
class ProposalData:
    """开题报告数据。"""

    title: str = ""
    author: str = ""
    advisor: str = ""  # 导师
    degree: str = ""  # 学位（硕士/博士）
    discipline: str = ""  # 学科
    school: str = ""  # 学院
    research_background: str = ""
    research_significance: str = ""
    research_status: str = ""  # 国内外研究现状
    research_goals: List[str] = field(default_factory=list)
    research_content: List[str] = field(default_factory=list)
    research_method: str = ""
    technical_route: str = ""  # 技术路线
    innovation_points: List[str] = field(default_factory=list)
    schedule: List[Dict[str, str]] = field(default_factory=list)  # 进度安排
    expected_results: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "author": self.author,
            "advisor": self.advisor,
            "degree": self.degree,
            "discipline": self.discipline,
            "school": self.school,
            "research_background": self.research_background,
            "research_significance": self.research_significance,
            "research_status": self.research_status,
            "research_goals": self.research_goals,
            "research_content": self.research_content,
            "research_method": self.research_method,
            "technical_route": self.technical_route,
            "innovation_points": self.innovation_points,
            "schedule": self.schedule,
            "expected_results": self.expected_results,
            "references": self.references,
            "keywords": self.keywords,
            "metadata": self.metadata,
        }


@dataclass
class LiteratureData:
    """文献综述数据。"""

    topic: str = ""
    author: str = ""
    introduction: str = ""
    background: str = ""
    search_strategy: str = ""
    categories: List[Dict[str, Any]] = field(default_factory=list)  # 主题分类
    timeline: List[Dict[str, str]] = field(default_factory=list)  # 研究脉络
    comparisons: List[Dict[str, Any]] = field(default_factory=list)  # 对比分析
    gaps: List[str] = field(default_factory=list)  # 研究空白
    future_work: List[str] = field(default_factory=list)
    conclusion: str = ""
    references: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "author": self.author,
            "introduction": self.introduction,
            "background": self.background,
            "search_strategy": self.search_strategy,
            "categories": self.categories,
            "timeline": self.timeline,
            "comparisons": self.comparisons,
            "gaps": self.gaps,
            "future_work": self.future_work,
            "conclusion": self.conclusion,
            "references": self.references,
            "keywords": self.keywords,
        }


@dataclass
class DefenseData:
    """答辩数据。"""

    title: str = ""
    author: str = ""
    advisor: str = ""
    degree: str = ""
    discipline: str = ""
    defense_date: str = ""
    background: str = ""
    problem_statement: str = ""
    research_goals: List[str] = field(default_factory=list)
    related_work: str = ""
    methodology: str = ""
    experiments: List[Dict[str, Any]] = field(default_factory=list)
    results: List[Dict[str, Any]] = field(default_factory=list)
    conclusions: List[str] = field(default_factory=list)
    innovations: List[str] = field(default_factory=list)
    future_work: List[str] = field(default_factory=list)
    acknowledgments: str = ""
    references: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "author": self.author,
            "advisor": self.advisor,
            "degree": self.degree,
            "discipline": self.discipline,
            "defense_date": self.defense_date,
            "background": self.background,
            "problem_statement": self.problem_statement,
            "research_goals": self.research_goals,
            "related_work": self.related_work,
            "methodology": self.methodology,
            "experiments": self.experiments,
            "results": self.results,
            "conclusions": self.conclusions,
            "innovations": self.innovations,
            "future_work": self.future_work,
            "acknowledgments": self.acknowledgments,
            "references": self.references,
        }


@dataclass
class ProgressData:
    """进度报告数据。"""

    title: str = ""
    author: str = ""
    advisor: str = ""
    report_date: str = ""
    period: str = ""  # 报告周期
    completed_work: List[Dict[str, str]] = field(default_factory=list)
    ongoing_work: List[Dict[str, str]] = field(default_factory=list)
    pending_tasks: List[Dict[str, str]] = field(default_factory=list)
    issues: List[Dict[str, str]] = field(default_factory=list)
    risks: List[Dict[str, str]] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "author": self.author,
            "advisor": self.advisor,
            "report_date": self.report_date,
            "period": self.period,
            "completed_work": self.completed_work,
            "ongoing_work": self.ongoing_work,
            "pending_tasks": self.pending_tasks,
            "issues": self.issues,
            "risks": self.risks,
            "next_steps": self.next_steps,
            "metadata": self.metadata,
        }


@dataclass
class SlideContent:
    """幻灯片内容。"""

    title: str = ""
    bullet_points: List[str] = field(default_factory=list)
    content: str = ""
    notes: str = ""  # 演讲备注
    layout: str = "title_content"  # title_content / two_column / image / table
    table: Optional[Dict[str, Any]] = None
    image_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "bullet_points": self.bullet_points,
            "content": self.content,
            "notes": self.notes,
            "layout": self.layout,
            "table": self.table,
            "image_path": self.image_path,
        }


@dataclass
class ReportResult:
    """报告生成结果。"""

    report_type: str
    title: str
    content: str = ""
    document: Optional[Any] = None  # Document 对象
    slides: List[SlideContent] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    generated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_type": self.report_type,
            "title": self.title,
            "content": self.content,
            "document": self.document.to_dict() if self.document else None,
            "slides": [s.to_dict() for s in self.slides],
            "metadata": self.metadata,
            "generated_at": self.generated_at,
        }


class ReportGenerator:
    """报告生成器（单例）

    提供多种类型学术报告的生成能力。
    """

    _instance: Optional["ReportGenerator"] = None
    _instance_lock = __import__("threading").Lock()

    def __new__(cls) -> "ReportGenerator":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._templates: Dict[str, Dict[str, Any]] = dict(DEFAULT_TEMPLATES)
        self._custom_sections: Dict[str, List[str]] = {}

    @classmethod
    def get_instance(cls) -> "ReportGenerator":
        """获取单例实例。"""
        return cls()

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例。"""
        with cls._instance_lock:
            cls._instance = None

    def register_template(
        self,
        name: str,
        template: Dict[str, Any],
    ) -> None:
        """注册自定义报告模板。"""
        self._templates[name] = template

    def get_template(self, name: str) -> Optional[Dict[str, Any]]:
        """获取模板。"""
        return self._templates.get(name)

    def list_templates(self) -> List[str]:
        """列出所有模板。"""
        return list(self._templates.keys())

    # ===== 开题报告 =====

    def generate_proposal_report(
        self,
        data: ProposalData,
        output_format: str = "markdown",
    ) -> ReportResult:
        """生成开题报告。

        Args:
            data: 开题报告数据。
            output_format: 输出格式（markdown / html / latex / text）。

        Returns:
            报告结果。
        """
        template = self._templates.get("proposal", {})
        title = template.get("title_template", "{degree}学位论文开题报告").format(
            degree=data.degree or "硕士",
            title=data.title,
        )
        # 构建 Document 对象
        if _HAS_EXPORTER:
            doc = Document(
                title=title,
                author=data.author,
                date=datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
                abstract=data.research_significance[:500] if data.research_significance else "",
                keywords=data.keywords,
                metadata={
                    "advisor": data.advisor,
                    "degree": data.degree,
                    "discipline": data.discipline,
                    "school": data.school,
                },
            )
            # 封面信息
            doc.sections.append(self._make_cover_section(data))
            # 研究背景与意义
            doc.sections.append(
                DocumentSection(
                    title="一、研究背景与意义",
                    level=1,
                    content=self._format_background_section(data),
                )
            )
            # 国内外研究现状
            doc.sections.append(
                DocumentSection(
                    title="二、国内外研究现状",
                    level=1,
                    content=data.research_status or "（请补充国内外研究现状）",
                )
            )
            # 研究目标与内容
            doc.sections.append(
                DocumentSection(
                    title="三、研究目标与内容",
                    level=1,
                    content=self._format_goals_section(data),
                )
            )
            # 研究方法与技术路线
            doc.sections.append(
                DocumentSection(
                    title="四、研究方法与技术路线",
                    level=1,
                    content=self._format_method_section(data),
                )
            )
            # 创新点与特色
            doc.sections.append(
                DocumentSection(
                    title="五、创新点与特色",
                    level=1,
                    content=self._format_innovation_section(data),
                )
            )
            # 研究计划与进度安排
            doc.sections.append(
                DocumentSection(
                    title="六、研究计划与进度安排",
                    level=1,
                    content=self._format_schedule_section(data),
                )
            )
            # 预期成果
            doc.sections.append(
                DocumentSection(
                    title="七、预期成果",
                    level=1,
                    content=self._format_expected_results_section(data),
                )
            )
            # 参考文献
            if data.references:
                doc.references = [
                    DocumentReference(ref_id=str(i + 1), text=ref)
                    for i, ref in enumerate(data.references)
                ]
            # 进度安排表格
            if data.schedule:
                doc.tables.append(self._make_schedule_table(data))
            # 生成内容
            content = self._render_document(doc, output_format)
        else:
            # 降级：纯文本生成
            doc = None
            content = self._generate_proposal_text(data, title)
        return ReportResult(
            report_type=ReportType.PROPOSAL.value,
            title=title,
            content=content,
            document=doc,
            metadata={"format": output_format, "data": data.to_dict()},
            generated_at=datetime.now(tz=timezone.utc).isoformat(),
        )

    def _make_cover_section(self, data: ProposalData) -> Any:
        """生成封面章节。"""
        content_parts = []
        if data.title:
            content_parts.append(f"**论文题目**: {data.title}")
        if data.author:
            content_parts.append(f"**研究生**: {data.author}")
        if data.advisor:
            content_parts.append(f"**指导教师**: {data.advisor}")
        if data.degree:
            content_parts.append(f"**学位类型**: {data.degree}")
        if data.discipline:
            content_parts.append(f"**学科专业**: {data.discipline}")
        if data.school:
            content_parts.append(f"**所在学院**: {data.school}")
        content_parts.append(f"**开题日期**: {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d')}")
        return DocumentSection(
            title="封面信息",
            level=1,
            content="\n\n".join(content_parts),
        )

    def _format_background_section(self, data: ProposalData) -> str:
        """格式化研究背景部分。"""
        parts = []
        if data.research_background:
            parts.append("### 研究背景\n")
            parts.append(data.research_background)
        if data.research_significance:
            parts.append("\n### 研究意义\n")
            parts.append(data.research_significance)
        return "\n\n".join(parts) if parts else "（请补充研究背景与意义）"

    def _format_goals_section(self, data: ProposalData) -> str:
        """格式化研究目标部分。"""
        parts = []
        if data.research_goals:
            parts.append("### 研究目标\n")
            for i, goal in enumerate(data.research_goals, 1):
                parts.append(f"{i}. {goal}")
        if data.research_content:
            parts.append("\n### 研究内容\n")
            for i, content in enumerate(data.research_content, 1):
                parts.append(f"{i}. {content}")
        return "\n".join(parts) if parts else "（请补充研究目标与内容）"

    def _format_method_section(self, data: ProposalData) -> str:
        """格式化研究方法部分。"""
        parts = []
        if data.research_method:
            parts.append("### 研究方法\n")
            parts.append(data.research_method)
        if data.technical_route:
            parts.append("\n### 技术路线\n")
            parts.append(data.technical_route)
        return "\n\n".join(parts) if parts else "（请补充研究方法与技术路线）"

    def _format_innovation_section(self, data: ProposalData) -> str:
        """格式化创新点部分。"""
        if not data.innovation_points:
            return "（请补充创新点与特色）"
        parts = ["本研究的主要创新点如下：\n"]
        for i, point in enumerate(data.innovation_points, 1):
            parts.append(f"{i}. {point}")
        return "\n".join(parts)

    def _format_schedule_section(self, data: ProposalData) -> str:
        """格式化进度安排部分。"""
        if not data.schedule:
            return "（请补充研究计划与进度安排）"
        parts = ["研究进度安排如下：\n"]
        for item in data.schedule:
            time_period = item.get("time", "")
            task = item.get("task", "")
            parts.append(f"- **{time_period}**: {task}")
        return "\n".join(parts)

    def _format_expected_results_section(self, data: ProposalData) -> str:
        """格式化预期成果部分。"""
        if not data.expected_results:
            return "（请补充预期成果）"
        parts = ["预期研究成果如下：\n"]
        for i, result in enumerate(data.expected_results, 1):
            parts.append(f"{i}. {result}")
        return "\n".join(parts)

    def _make_schedule_table(self, data: ProposalData) -> Any:
        """生成进度安排表格。"""
        headers = ["序号", "时间阶段", "研究任务", "备注"]
        rows = []
        for i, item in enumerate(data.schedule, 1):
            rows.append([
                str(i),
                item.get("time", ""),
                item.get("task", ""),
                item.get("note", ""),
            ])
        return DocumentTable(
            caption="表1：研究进度安排",
            headers=headers,
            rows=rows,
        )

    # ===== 文献综述 =====

    def generate_literature_review(
        self,
        data: LiteratureData,
        output_format: str = "markdown",
    ) -> ReportResult:
        """生成文献综述。"""
        template = self._templates.get("literature_review", {})
        title = template.get("title_template", "文献综述：{topic}").format(
            topic=data.topic or "未命名主题"
        )
        if _HAS_EXPORTER:
            doc = Document(
                title=title,
                author=data.author,
                date=datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
                abstract=data.introduction[:500] if data.introduction else "",
                keywords=data.keywords,
            )
            # 引言
            doc.sections.append(
                DocumentSection(
                    title="一、引言",
                    level=1,
                    content=data.introduction or "（请补充引言）",
                )
            )
            # 研究背景
            doc.sections.append(
                DocumentSection(
                    title="二、研究背景",
                    level=1,
                    content=data.background or "（请补充研究背景）",
                )
            )
            # 文献检索策略
            doc.sections.append(
                DocumentSection(
                    title="三、文献检索策略",
                    level=1,
                    content=data.search_strategy or "（请补充文献检索策略）",
                )
            )
            # 研究主题分类
            doc.sections.append(
                DocumentSection(
                    title="四、研究主题分类",
                    level=1,
                    content=self._format_categories_section(data),
                )
            )
            # 研究脉络梳理
            doc.sections.append(
                DocumentSection(
                    title="五、研究脉络梳理",
                    level=1,
                    content=self._format_timeline_section(data),
                )
            )
            # 对比分析
            doc.sections.append(
                DocumentSection(
                    title="六、对比分析",
                    level=1,
                    content=self._format_comparisons_section(data),
                )
            )
            # 研究空白与展望
            doc.sections.append(
                DocumentSection(
                    title="七、研究空白与展望",
                    level=1,
                    content=self._format_gaps_section(data),
                )
            )
            # 结论
            doc.sections.append(
                DocumentSection(
                    title="八、结论",
                    level=1,
                    content=data.conclusion or "（请补充结论）",
                )
            )
            # 参考文献
            if data.references:
                doc.references = [
                    DocumentReference(ref_id=str(i + 1), text=ref)
                    for i, ref in enumerate(data.references)
                ]
            # 对比分析表格
            if data.comparisons:
                doc.tables.append(self._make_comparison_table(data))
            content = self._render_document(doc, output_format)
        else:
            doc = None
            content = self._generate_literature_text(data, title)
        return ReportResult(
            report_type=ReportType.LITERATURE_REVIEW.value,
            title=title,
            content=content,
            document=doc,
            metadata={"format": output_format, "data": data.to_dict()},
            generated_at=datetime.now(tz=timezone.utc).isoformat(),
        )

    def _format_categories_section(self, data: LiteratureData) -> str:
        """格式化主题分类部分。"""
        if not data.categories:
            return "（请补充研究主题分类）"
        parts = ["根据研究内容，可将相关文献分为以下几类：\n"]
        for cat in data.categories:
            name = cat.get("name", "")
            description = cat.get("description", "")
            count = cat.get("count", 0)
            parts.append(f"### {name}（{count} 篇）\n")
            parts.append(description)
            parts.append("")
        return "\n".join(parts)

    def _format_timeline_section(self, data: LiteratureData) -> str:
        """格式化研究脉络部分。"""
        if not data.timeline:
            return "（请补充研究脉络梳理）"
        parts = ["研究发展脉络如下：\n"]
        for item in data.timeline:
            year = item.get("year", "")
            event = item.get("event", "")
            parts.append(f"- **{year}**: {event}")
        return "\n".join(parts)

    def _format_comparisons_section(self, data: LiteratureData) -> str:
        """格式化对比分析部分。"""
        if not data.comparisons:
            return "（请补充对比分析）"
        parts = ["各方法对比分析如下：\n"]
        for comp in data.comparisons:
            method = comp.get("method", "")
            advantages = comp.get("advantages", "")
            disadvantages = comp.get("disadvantages", "")
            parts.append(f"### {method}\n")
            parts.append(f"**优点**: {advantages}\n")
            parts.append(f"**缺点**: {disadvantages}\n")
        return "\n".join(parts)

    def _format_gaps_section(self, data: LiteratureData) -> str:
        """格式化研究空白部分。"""
        parts = []
        if data.gaps:
            parts.append("### 研究空白\n")
            for i, gap in enumerate(data.gaps, 1):
                parts.append(f"{i}. {gap}")
        if data.future_work:
            parts.append("\n### 未来研究方向\n")
            for i, work in enumerate(data.future_work, 1):
                parts.append(f"{i}. {work}")
        return "\n".join(parts) if parts else "（请补充研究空白与展望）"

    def _make_comparison_table(self, data: LiteratureData) -> Any:
        """生成对比分析表格。"""
        headers = ["序号", "方法", "优点", "缺点"]
        rows = []
        for i, comp in enumerate(data.comparisons, 1):
            rows.append([
                str(i),
                comp.get("method", ""),
                comp.get("advantages", ""),
                comp.get("disadvantages", ""),
            ])
        return DocumentTable(
            caption="表1：方法对比分析",
            headers=headers,
            rows=rows,
        )

    # ===== 答辩 PPT 大纲 =====

    def generate_defense_ppt_outline(
        self,
        data: DefenseData,
        output_format: str = "markdown",
    ) -> ReportResult:
        """生成答辩 PPT 大纲。"""
        template = self._templates.get("defense_ppt", {})
        title = template.get("title_template", "{title} - 答辩报告").format(
            title=data.title or "未命名"
        )
        slides: List[SlideContent] = []
        # 幻灯片 1: 封面
        slides.append(
            SlideContent(
                title=data.title or "论文答辩",
                content=f"\n作者: {data.author}\n导师: {data.advisor}\n"
                f"学位: {data.degree}\n专业: {data.discipline}\n"
                f"日期: {data.defense_date}",
                layout="title",
                notes="开场致辞，介绍论文基本信息",
            )
        )
        # 幻灯片 2: 研究背景与问题
        slides.append(
            SlideContent(
                title="研究背景与问题",
                bullet_points=self._extract_bullet_points(data.background),
                content=data.background,
                notes="阐述研究背景，引出研究问题",
            )
        )
        # 幻灯片 3: 研究目标
        slides.append(
            SlideContent(
                title="研究目标",
                bullet_points=data.research_goals,
                notes="明确研究目标，说明研究意义",
            )
        )
        # 幻灯片 4: 相关工作
        slides.append(
            SlideContent(
                title="相关工作",
                bullet_points=self._extract_bullet_points(data.related_work),
                content=data.related_work,
                notes="回顾相关工作，指出研究空白",
            )
        )
        # 幻灯片 5: 研究方法
        slides.append(
            SlideContent(
                title="研究方法",
                bullet_points=self._extract_bullet_points(data.methodology),
                content=data.methodology,
                notes="详细介绍研究方法与技术路线",
            )
        )
        # 幻灯片 6-N: 实验与结果
        for i, exp in enumerate(data.experiments, 1):
            slides.append(
                SlideContent(
                    title=f"实验 {i}: {exp.get('name', '')}",
                    bullet_points=exp.get("details", []),
                    content=exp.get("description", ""),
                    table=exp.get("table"),
                    notes=exp.get("notes", f"介绍实验 {i} 的设置与结果"),
                )
            )
        # 结果总结
        if data.results:
            slides.append(
                SlideContent(
                    title="实验结果总结",
                    bullet_points=[
                        r.get("summary", "") if isinstance(r, dict) else str(r)
                        for r in data.results
                    ],
                    notes="总结实验结果，强调关键发现",
                )
            )
        # 结论与创新点
        slides.append(
            SlideContent(
                title="结论与创新点",
                bullet_points=data.conclusions + ["**创新点**:"] + data.innovations,
                notes="总结研究结论，突出创新贡献",
            )
        )
        # 未来工作
        slides.append(
            SlideContent(
                title="未来工作",
                bullet_points=data.future_work,
                notes="展望未来研究方向",
            )
        )
        # 致谢
        slides.append(
            SlideContent(
                title="致谢",
                content=data.acknowledgments or "感谢导师与各位老师！",
                layout="title",
                notes="致谢，结束答辩",
            )
        )
        # 生成大纲内容
        content = self._render_ppt_outline(slides, title, output_format)
        # 构建 Document 对象
        doc = None
        if _HAS_EXPORTER:
            doc = Document(
                title=title,
                author=data.author,
                date=data.defense_date,
            )
            for i, slide in enumerate(slides, 1):
                doc.sections.append(
                    DocumentSection(
                        title=f"幻灯片 {i}: {slide.title}",
                        level=1,
                        content=self._slide_to_text(slide),
                    )
                )
        return ReportResult(
            report_type=ReportType.DEFENSE_PPT.value,
            title=title,
            content=content,
            document=doc,
            slides=slides,
            metadata={"format": output_format, "slide_count": len(slides)},
            generated_at=datetime.now(tz=timezone.utc).isoformat(),
        )

    def _extract_bullet_points(self, text: str, max_points: int = 5) -> List[str]:
        """从文本提取要点。"""
        if not text:
            return []
        # 按句子分割
        sentences = []
        current = ""
        for ch in text:
            if ch in "。！？；\n":
                if current.strip():
                    sentences.append(current.strip())
                current = ""
            else:
                current += ch
        if current.strip():
            sentences.append(current.strip())
        # 取前 max_points 句
        return sentences[:max_points]

    def _slide_to_text(self, slide: SlideContent) -> str:
        """将幻灯片转为文本。"""
        parts = []
        if slide.bullet_points:
            parts.append("**要点**:")
            for point in slide.bullet_points:
                parts.append(f"- {point}")
        if slide.content:
            parts.append(f"\n**内容**:\n{slide.content}")
        if slide.notes:
            parts.append(f"\n**备注**: {slide.notes}")
        return "\n".join(parts)

    def _render_ppt_outline(
        self,
        slides: List[SlideContent],
        title: str,
        output_format: str,
    ) -> str:
        """渲染 PPT 大纲。"""
        if output_format == "markdown":
            return self._render_ppt_markdown(slides, title)
        elif output_format == "html":
            return self._render_ppt_html(slides, title)
        elif output_format == "latex":
            return self._render_ppt_latex(slides, title)
        else:
            return self._render_ppt_text(slides, title)

    def _render_ppt_markdown(self, slides: List[SlideContent], title: str) -> str:
        """渲染 PPT 大纲为 Markdown。"""
        parts = [f"# {title}\n"]
        parts.append(f"> 共 {len(slides)} 张幻灯片\n")
        for i, slide in enumerate(slides, 1):
            parts.append(f"## 幻灯片 {i}: {slide.title}\n")
            if slide.bullet_points:
                for point in slide.bullet_points:
                    parts.append(f"- {point}")
                parts.append("")
            if slide.content:
                parts.append(slide.content)
                parts.append("")
            if slide.notes:
                parts.append(f"> **备注**: {slide.notes}\n")
        return "\n".join(parts)

    def _render_ppt_html(self, slides: List[SlideContent], title: str) -> str:
        """渲染 PPT 大纲为 HTML。"""
        parts = ["<!DOCTYPE html>", "<html>", "<head>", f"<title>{title}</title>", "</head>", "<body>"]
        parts.append(f"<h1>{title}</h1>")
        parts.append(f"<p>共 {len(slides)} 张幻灯片</p>")
        for i, slide in enumerate(slides, 1):
            parts.append(f"<h2>幻灯片 {i}: {slide.title}</h2>")
            if slide.bullet_points:
                parts.append("<ul>")
                for point in slide.bullet_points:
                    parts.append(f"<li>{point}</li>")
                parts.append("</ul>")
            if slide.content:
                parts.append(f"<p>{slide.content}</p>")
            if slide.notes:
                parts.append(f"<p><em>备注: {slide.notes}</em></p>")
        parts.append("</body>", "</html>")
        return "\n".join(parts)

    def _render_ppt_latex(self, slides: List[SlideContent], title: str) -> str:
        """渲染 PPT 大纲为 LaTeX。"""
        parts = [
            "\\documentclass{beamer}",
            "\\usepackage{ctex}",
            f"\\title{{{title}}}",
            "\\begin{document}",
            f"\\maketitle",
        ]
        for i, slide in enumerate(slides, 1):
            parts.append(f"\\begin{{frame}}{{{slide.title}}}")
            if slide.bullet_points:
                parts.append("\\begin{itemize}")
                for point in slide.bullet_points:
                    parts.append(f"\\item {point}")
                parts.append("\\end{itemize}")
            if slide.content:
                parts.append(slide.content)
            parts.append("\\end{frame}")
        parts.append("\\end{document}")
        return "\n".join(parts)

    def _render_ppt_text(self, slides: List[SlideContent], title: str) -> str:
        """渲染 PPT 大纲为纯文本。"""
        parts = [title, "=" * 40, f"共 {len(slides)} 张幻灯片", ""]
        for i, slide in enumerate(slides, 1):
            parts.append(f"【幻灯片 {i}】{slide.title}")
            parts.append("-" * 40)
            if slide.bullet_points:
                for point in slide.bullet_points:
                    parts.append(f"  • {point}")
            if slide.content:
                parts.append(slide.content)
            if slide.notes:
                parts.append(f"  [备注] {slide.notes}")
            parts.append("")
        return "\n".join(parts)

    # ===== 进度报告 =====

    def generate_progress_report(
        self,
        data: ProgressData,
        output_format: str = "markdown",
    ) -> ReportResult:
        """生成进度报告。"""
        template = self._templates.get("progress", {})
        title = template.get("title_template", "研究进度报告").format(
            title=data.title or "未命名"
        )
        if _HAS_EXPORTER:
            doc = Document(
                title=title,
                author=data.author,
                date=data.report_date or datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
                metadata={"advisor": data.advisor, "period": data.period},
            )
            # 基本信息
            doc.sections.append(
                DocumentSection(
                    title="一、基本信息",
                    level=1,
                    content=self._format_progress_basic(data),
                )
            )
            # 已完成工作
            doc.sections.append(
                DocumentSection(
                    title="二、已完成工作",
                    level=1,
                    content=self._format_completed_work(data),
                )
            )
            # 进行中工作
            doc.sections.append(
                DocumentSection(
                    title="三、进行中工作",
                    level=1,
                    content=self._format_ongoing_work(data),
                )
            )
            # 待完成任务
            doc.sections.append(
                DocumentSection(
                    title="四、待完成任务",
                    level=1,
                    content=self._format_pending_tasks(data),
                )
            )
            # 问题与风险
            doc.sections.append(
                DocumentSection(
                    title="五、问题与风险",
                    level=1,
                    content=self._format_issues_risks(data),
                )
            )
            # 下一步计划
            doc.sections.append(
                DocumentSection(
                    title="六、下一步计划",
                    level=1,
                    content=self._format_next_steps(data),
                )
            )
            # 已完成工作表格
            if data.completed_work:
                doc.tables.append(self._make_progress_table(data.completed_work, "已完成工作"))
            content = self._render_document(doc, output_format)
        else:
            doc = None
            content = self._generate_progress_text(data, title)
        return ReportResult(
            report_type=ReportType.PROGRESS.value,
            title=title,
            content=content,
            document=doc,
            metadata={"format": output_format, "data": data.to_dict()},
            generated_at=datetime.now(tz=timezone.utc).isoformat(),
        )

    def _format_progress_basic(self, data: ProgressData) -> str:
        """格式化基本信息。"""
        parts = []
        if data.title:
            parts.append(f"**研究课题**: {data.title}")
        if data.author:
            parts.append(f"**研究生**: {data.author}")
        if data.advisor:
            parts.append(f"**指导教师**: {data.advisor}")
        if data.period:
            parts.append(f"**报告周期**: {data.period}")
        parts.append(f"**报告日期**: {data.report_date or datetime.now(tz=timezone.utc).strftime('%Y-%m-%d')}")
        return "\n\n".join(parts)

    def _format_completed_work(self, data: ProgressData) -> str:
        """格式化已完成工作。"""
        if not data.completed_work:
            return "（暂无已完成工作）"
        parts = ["已完成的工作如下：\n"]
        for i, work in enumerate(data.completed_work, 1):
            name = work.get("name", "")
            description = work.get("description", "")
            date = work.get("date", "")
            parts.append(f"{i}. **{name}** ({date})\n   {description}")
        return "\n".join(parts)

    def _format_ongoing_work(self, data: ProgressData) -> str:
        """格式化进行中工作。"""
        if not data.ongoing_work:
            return "（暂无进行中工作）"
        parts = ["正在进行的工作：\n"]
        for i, work in enumerate(data.ongoing_work, 1):
            name = work.get("name", "")
            description = work.get("description", "")
            progress = work.get("progress", "")
            parts.append(f"{i}. **{name}** (进度: {progress})\n   {description}")
        return "\n".join(parts)

    def _format_pending_tasks(self, data: ProgressData) -> str:
        """格式化待完成任务。"""
        if not data.pending_tasks:
            return "（暂无待完成任务）"
        parts = ["待完成的任务：\n"]
        for i, task in enumerate(data.pending_tasks, 1):
            name = task.get("name", "")
            deadline = task.get("deadline", "")
            priority = task.get("priority", "")
            parts.append(f"{i}. **{name}** (截止: {deadline}, 优先级: {priority})")
        return "\n".join(parts)

    def _format_issues_risks(self, data: ProgressData) -> str:
        """格式化问题与风险。"""
        parts = []
        if data.issues:
            parts.append("### 存在的问题\n")
            for i, issue in enumerate(data.issues, 1):
                description = issue.get("description", "")
                impact = issue.get("impact", "")
                parts.append(f"{i}. {description} (影响: {impact})")
        if data.risks:
            parts.append("\n### 风险评估\n")
            for i, risk in enumerate(data.risks, 1):
                description = risk.get("description", "")
                probability = risk.get("probability", "")
                impact = risk.get("impact", "")
                parts.append(f"{i}. {description} (概率: {probability}, 影响: {impact})")
        return "\n".join(parts) if parts else "（暂无问题与风险）"

    def _format_next_steps(self, data: ProgressData) -> str:
        """格式化下一步计划。"""
        if not data.next_steps:
            return "（请补充下一步计划）"
        parts = ["下一步工作计划：\n"]
        for i, step in enumerate(data.next_steps, 1):
            parts.append(f"{i}. {step}")
        return "\n".join(parts)

    def _make_progress_table(self, work_list: List[Dict[str, str]], caption: str) -> Any:
        """生成进度表格。"""
        headers = ["序号", "工作名称", "描述", "日期/进度"]
        rows = []
        for i, work in enumerate(work_list, 1):
            rows.append([
                str(i),
                work.get("name", ""),
                work.get("description", ""),
                work.get("date", work.get("progress", "")),
            ])
        return DocumentTable(caption=caption, headers=headers, rows=rows)

    # ===== 周报/月报 =====

    def generate_weekly_report(
        self,
        data: ProgressData,
        output_format: str = "markdown",
    ) -> ReportResult:
        """生成周报。"""
        template = self._templates.get("weekly", {})
        week = data.period or datetime.now(tz=timezone.utc).strftime("%Y-W%W")
        title = template.get("title_template", "周报 - {week}").format(week=week)
        if _HAS_EXPORTER:
            doc = Document(
                title=title,
                author=data.author,
                date=data.report_date or datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
            )
            doc.sections.append(
                DocumentSection(
                    title="一、本周工作",
                    level=1,
                    content=self._format_completed_work(data),
                )
            )
            doc.sections.append(
                DocumentSection(
                    title="二、进展详情",
                    level=1,
                    content=self._format_ongoing_work(data),
                )
            )
            doc.sections.append(
                DocumentSection(
                    title="三、问题与困难",
                    level=1,
                    content=self._format_issues_risks(data),
                )
            )
            doc.sections.append(
                DocumentSection(
                    title="四、下周计划",
                    level=1,
                    content=self._format_next_steps(data),
                )
            )
            content = self._render_document(doc, output_format)
        else:
            doc = None
            content = self._generate_progress_text(data, title)
        return ReportResult(
            report_type=ReportType.WEEKLY.value,
            title=title,
            content=content,
            document=doc,
            metadata={"format": output_format, "week": week},
            generated_at=datetime.now(tz=timezone.utc).isoformat(),
        )

    def generate_monthly_report(
        self,
        data: ProgressData,
        output_format: str = "markdown",
    ) -> ReportResult:
        """生成月报。"""
        template = self._templates.get("monthly", {})
        month = data.period or datetime.now(tz=timezone.utc).strftime("%Y-%m")
        title = template.get("title_template", "月报 - {month}").format(month=month)
        if _HAS_EXPORTER:
            doc = Document(
                title=title,
                author=data.author,
                date=data.report_date or datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
            )
            doc.sections.append(
                DocumentSection(
                    title="一、本月工作总结",
                    level=1,
                    content=self._format_completed_work(data),
                )
            )
            doc.sections.append(
                DocumentSection(
                    title="二、关键进展",
                    level=1,
                    content=self._format_ongoing_work(data),
                )
            )
            doc.sections.append(
                DocumentSection(
                    title="三、问题分析",
                    level=1,
                    content=self._format_issues_risks(data),
                )
            )
            doc.sections.append(
                DocumentSection(
                    title="四、下月计划",
                    level=1,
                    content=self._format_next_steps(data),
                )
            )
            content = self._render_document(doc, output_format)
        else:
            doc = None
            content = self._generate_progress_text(data, title)
        return ReportResult(
            report_type=ReportType.MONTHLY.value,
            title=title,
            content=content,
            document=doc,
            metadata={"format": output_format, "month": month},
            generated_at=datetime.now(tz=timezone.utc).isoformat(),
        )

    # ===== 结题报告 =====

    def generate_final_report(
        self,
        data: ProposalData,
        output_format: str = "markdown",
    ) -> ReportResult:
        """生成结题报告。"""
        template = self._templates.get("final", {})
        title = template.get("title_template", "结题报告 - {title}").format(
            title=data.title or "未命名"
        )
        if _HAS_EXPORTER:
            doc = Document(
                title=title,
                author=data.author,
                date=datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
                keywords=data.keywords,
            )
            doc.sections.append(
                DocumentSection(
                    title="一、项目概述",
                    level=1,
                    content=data.research_background or "（请补充项目概述）",
                )
            )
            doc.sections.append(
                DocumentSection(
                    title="二、研究目标完成情况",
                    level=1,
                    content=self._format_goals_section(data),
                )
            )
            doc.sections.append(
                DocumentSection(
                    title="三、主要研究成果",
                    level=1,
                    content=self._format_expected_results_section(data),
                )
            )
            doc.sections.append(
                DocumentSection(
                    title="四、创新点总结",
                    level=1,
                    content=self._format_innovation_section(data),
                )
            )
            doc.sections.append(
                DocumentSection(
                    title="五、成果清单",
                    level=1,
                    content=self._format_results_list(data),
                )
            )
            doc.sections.append(
                DocumentSection(
                    title="六、后续工作展望",
                    level=1,
                    content=data.research_status or "（请补充后续工作展望）",
                )
            )
            if data.references:
                doc.references = [
                    DocumentReference(ref_id=str(i + 1), text=ref)
                    for i, ref in enumerate(data.references)
                ]
            content = self._render_document(doc, output_format)
        else:
            doc = None
            content = self._generate_proposal_text(data, title)
        return ReportResult(
            report_type=ReportType.FINAL.value,
            title=title,
            content=content,
            document=doc,
            metadata={"format": output_format},
            generated_at=datetime.now(tz=timezone.utc).isoformat(),
        )

    def _format_results_list(self, data: ProposalData) -> str:
        """格式化成果清单。"""
        if not data.expected_results:
            return "（请补充成果清单）"
        parts = ["研究成果清单：\n"]
        for i, result in enumerate(data.expected_results, 1):
            parts.append(f"{i}. {result}")
        return "\n".join(parts)

    # ===== 自定义报告 =====

    def generate_custom_report(
        self,
        title: str,
        sections: List[Dict[str, Any]],
        author: str = "",
        output_format: str = "markdown",
    ) -> ReportResult:
        """生成自定义报告。

        Args:
            title: 报告标题。
            sections: 章节列表，每项为 {"title": ..., "content": ..., "level": ...}。
            author: 作者。
            output_format: 输出格式。

        Returns:
            报告结果。
        """
        if _HAS_EXPORTER:
            doc = Document(
                title=title,
                author=author,
                date=datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
            )
            for sec_data in sections:
                doc.sections.append(
                    DocumentSection(
                        title=sec_data.get("title", ""),
                        level=sec_data.get("level", 1),
                        content=sec_data.get("content", ""),
                    )
                )
            content = self._render_document(doc, output_format)
        else:
            doc = None
            parts = [f"# {title}\n"]
            if author:
                parts.append(f"**作者**: {author}\n")
            for sec in sections:
                level = sec.get("level", 1)
                heading = "#" * (level + 1)
                parts.append(f"{heading} {sec.get('title', '')}\n")
                parts.append(sec.get("content", ""))
                parts.append("")
            content = "\n".join(parts)
        return ReportResult(
            report_type=ReportType.CUSTOM.value,
            title=title,
            content=content,
            document=doc,
            metadata={"format": output_format, "section_count": len(sections)},
            generated_at=datetime.now(tz=timezone.utc).isoformat(),
        )

    # ===== 图表生成 =====

    def generate_ascii_table(
        self,
        headers: List[str],
        rows: List[List[str]],
        caption: str = "",
    ) -> str:
        """生成 ASCII 表格。"""
        if not headers:
            return ""
        col_count = len(headers)
        col_widths = [len(str(h)) for h in headers]
        for row in rows:
            for i, cell in enumerate(row[:col_count]):
                col_widths[i] = max(col_widths[i], len(str(cell)))
        # 分隔线
        separator = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
        lines = []
        if caption:
            lines.append(caption)
            lines.append("")
        lines.append(separator)
        # 表头
        header_cells = [f" {str(h):<{col_widths[i]}} " for i, h in enumerate(headers)]
        lines.append("|" + "|".join(header_cells) + "|")
        lines.append(separator)
        # 数据行
        for row in rows:
            row_cells = []
            for i in range(col_count):
                cell = str(row[i]) if i < len(row) else ""
                row_cells.append(f" {cell:<{col_widths[i]}} ")
            lines.append("|" + "|".join(row_cells) + "|")
        lines.append(separator)
        return "\n".join(lines)

    def generate_markdown_table(
        self,
        headers: List[str],
        rows: List[List[str]],
        caption: str = "",
    ) -> str:
        """生成 Markdown 表格。"""
        if not headers:
            return ""
        lines = []
        if caption:
            lines.append(f"**{caption}**\n")
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        for row in rows:
            while len(row) < len(headers):
                row.append("")
            lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
        return "\n".join(lines)

    def generate_progress_bar(
        self,
        current: int,
        total: int,
        width: int = 20,
    ) -> str:
        """生成 ASCII 进度条。"""
        if total <= 0:
            return "[" + " " * width + "] 0%"
        ratio = min(current / total, 1.0)
        filled = int(ratio * width)
        bar = "█" * filled + "░" * (width - filled)
        percent = int(ratio * 100)
        return f"[{bar}] {percent}% ({current}/{total})"

    def generate_gantt_chart(
        self,
        tasks: List[Dict[str, str]],
        total_weeks: int = 16,
    ) -> str:
        """生成简易 ASCII 甘特图。

        Args:
            tasks: 任务列表，每项含 name / start_week / end_week。
            total_weeks: 总周数。

        Returns:
            ASCII 甘特图字符串。
        """
        if not tasks:
            return "（无任务）"
        lines = []
        # 表头
        header = "任务".ljust(20) + "|"
        for w in range(1, total_weeks + 1):
            header += str(w % 10)
        lines.append(header)
        lines.append("-" * len(header))
        # 任务行
        for task in tasks:
            name = task.get("name", "")[:20].ljust(20)
            start = int(task.get("start_week", 1))
            end = int(task.get("end_week", start))
            row = name + "|"
            for w in range(1, total_weeks + 1):
                if start <= w <= end:
                    row += "█"
                else:
                    row += " "
            lines.append(row)
        return "\n".join(lines)

    # ===== 导出方法 =====

    def export_report(
        self,
        report: ReportResult,
        file_path: str,
        format: Optional[str] = None,
    ) -> Any:
        """导出报告到文件。"""
        if not _HAS_EXPORTER:
            # 降级：直接写文本
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(report.content)
            return None
        exporter = DocumentExporter.get_instance()
        if report.document:
            return exporter.export_to_file(report.document, file_path, format)
        else:
            # 无 Document 对象，直接写内容
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(report.content)
            return None

    def export_report_as_format(
        self,
        report: ReportResult,
        output_format: str,
    ) -> str:
        """以指定格式导出报告内容。"""
        if not _HAS_EXPORTER or not report.document:
            return report.content
        exporter = DocumentExporter.get_instance()
        if output_format == "markdown":
            return exporter.export_markdown(report.document)
        elif output_format == "html":
            return exporter.export_html(report.document)
        elif output_format == "latex":
            return exporter.export_latex(report.document)
        elif output_format == "text":
            return exporter.export_text(report.document)
        elif output_format == "json":
            return exporter.export_json(report.document)
        else:
            return report.content

    # ===== 渲染辅助方法 =====

    def _render_document(self, doc: Any, output_format: str) -> str:
        """渲染 Document 对象为指定格式。"""
        if not _HAS_EXPORTER:
            return ""
        exporter = DocumentExporter.get_instance()
        if output_format == "markdown":
            return exporter.export_markdown(doc)
        elif output_format == "html":
            return exporter.export_html(doc)
        elif output_format == "latex":
            return exporter.export_latex(doc)
        elif output_format == "text":
            return exporter.export_text(doc)
        elif output_format == "json":
            return exporter.export_json(doc)
        else:
            return exporter.export_markdown(doc)

    def _generate_proposal_text(self, data: ProposalData, title: str) -> str:
        """降级：生成开题报告纯文本。"""
        parts = [title, "=" * 40, ""]
        if data.author:
            parts.append(f"作者: {data.author}")
        if data.advisor:
            parts.append(f"导师: {data.advisor}")
        parts.append("")
        if data.research_background:
            parts.append("【研究背景】")
            parts.append(data.research_background)
            parts.append("")
        if data.research_significance:
            parts.append("【研究意义】")
            parts.append(data.research_significance)
            parts.append("")
        if data.research_goals:
            parts.append("【研究目标】")
            for i, goal in enumerate(data.research_goals, 1):
                parts.append(f"{i}. {goal}")
            parts.append("")
        if data.research_content:
            parts.append("【研究内容】")
            for i, content in enumerate(data.research_content, 1):
                parts.append(f"{i}. {content}")
            parts.append("")
        if data.innovation_points:
            parts.append("【创新点】")
            for i, point in enumerate(data.innovation_points, 1):
                parts.append(f"{i}. {point}")
            parts.append("")
        if data.references:
            parts.append("【参考文献】")
            for i, ref in enumerate(data.references, 1):
                parts.append(f"[{i}] {ref}")
        return "\n".join(parts)

    def _generate_literature_text(self, data: LiteratureData, title: str) -> str:
        """降级：生成文献综述纯文本。"""
        parts = [title, "=" * 40, ""]
        if data.introduction:
            parts.append("【引言】")
            parts.append(data.introduction)
            parts.append("")
        if data.background:
            parts.append("【研究背景】")
            parts.append(data.background)
            parts.append("")
        if data.gaps:
            parts.append("【研究空白】")
            for i, gap in enumerate(data.gaps, 1):
                parts.append(f"{i}. {gap}")
            parts.append("")
        if data.references:
            parts.append("【参考文献】")
            for i, ref in enumerate(data.references, 1):
                parts.append(f"[{i}] {ref}")
        return "\n".join(parts)

    def _generate_progress_text(self, data: ProgressData, title: str) -> str:
        """降级：生成进度报告纯文本。"""
        parts = [title, "=" * 40, ""]
        if data.author:
            parts.append(f"作者: {data.author}")
        if data.period:
            parts.append(f"周期: {data.period}")
        parts.append("")
        if data.completed_work:
            parts.append("【已完成工作】")
            for i, work in enumerate(data.completed_work, 1):
                parts.append(f"{i}. {work.get('name', '')}: {work.get('description', '')}")
            parts.append("")
        if data.ongoing_work:
            parts.append("【进行中工作】")
            for i, work in enumerate(data.ongoing_work, 1):
                parts.append(f"{i}. {work.get('name', '')}: {work.get('description', '')}")
            parts.append("")
        if data.next_steps:
            parts.append("【下一步计划】")
            for i, step in enumerate(data.next_steps, 1):
                parts.append(f"{i}. {step}")
        return "\n".join(parts)

    def shutdown(self) -> None:
        """关闭报告生成器。"""
        _logger.info("报告生成器已关闭")


# ===== 模块级便捷函数 =====


def get_report_generator() -> ReportGenerator:
    """获取全局报告生成器单例。"""
    return ReportGenerator.get_instance()


def generate_proposal_report(data: ProposalData, output_format: str = "markdown") -> str:
    """生成开题报告便捷函数。"""
    generator = get_report_generator()
    result = generator.generate_proposal_report(data, output_format)
    return result.content


def generate_progress_report(data: ProgressData, output_format: str = "markdown") -> str:
    """生成进度报告便捷函数。"""
    generator = get_report_generator()
    result = generator.generate_progress_report(data, output_format)
    return result.content


# ===== 单元测试可运行逻辑 =====


def _run_self_test() -> None:
    """模块自检。"""
    ReportGenerator.reset_instance()
    generator = ReportGenerator()

    # 测试开题报告生成
    proposal_data = ProposalData(
        title="基于深度学习的中文文本分类研究",
        author="张三",
        advisor="李教授",
        degree="硕士",
        discipline="计算机科学与技术",
        school="信息学院",
        research_background="随着互联网的发展，文本数据量急剧增长，文本分类成为重要研究课题。",
        research_significance="本研究对提升中文文本分类性能具有重要意义。",
        research_status="目前已有多种文本分类方法，但中文场景下仍有改进空间。",
        research_goals=["提出一种改进的文本分类模型", "在公开数据集上验证有效性"],
        research_content=["模型设计", "数据集构建", "实验验证", "性能分析"],
        research_method="采用深度学习方法，结合预训练模型与微调策略。",
        technical_route="数据预处理 → 模型设计 → 训练优化 → 实验评估",
        innovation_points=["提出新的注意力机制", "结合领域知识适配"],
        schedule=[
            {"time": "2026.09-2026.12", "task": "文献调研与模型设计"},
            {"time": "2027.01-2027.03", "task": "实验实施与数据分析"},
            {"time": "2027.04-2027.05", "task": "论文撰写与答辩准备"},
        ],
        expected_results=["发表学术论文 1 篇", "完成学位论文"],
        references=[
            "Vaswani, A. et al. (2017). Attention is all you need.",
            "Devlin, J. et al. (2018). BERT: Pre-training of deep bidirectional transformers.",
        ],
        keywords=["深度学习", "文本分类", "预训练模型"],
    )
    proposal_result = generator.generate_proposal_report(proposal_data, "markdown")
    assert "开题报告" in proposal_result.title
    assert "研究背景" in proposal_result.content
    assert "创新点" in proposal_result.content
    print(f"开题报告生成成功，长度 {len(proposal_result.content)} 字符")

    # 测试 HTML 格式
    proposal_html = generator.generate_proposal_report(proposal_data, "html")
    assert "<!DOCTYPE html>" in proposal_html.content
    print("开题报告 HTML 格式生成成功")

    # 测试文献综述生成
    lit_data = LiteratureData(
        topic="深度学习在自然语言处理中的应用",
        author="张三",
        introduction="本文综述深度学习在 NLP 领域的应用进展。",
        background="NLP 是人工智能的重要分支。",
        search_strategy="使用 Google Scholar 与 CNKI 检索相关文献。",
        categories=[
            {"name": "文本分类", "description": "包括传统方法与深度学习方法。", "count": 25},
            {"name": "机器翻译", "description": "基于 Seq2Seq 与 Transformer 的方法。", "count": 30},
        ],
        timeline=[
            {"year": "2014", "event": "Seq2Seq 模型提出"},
            {"year": "2017", "event": "Transformer 架构提出"},
            {"year": "2018", "event": "BERT 模型发布"},
        ],
        comparisons=[
            {"method": "RNN", "advantages": "适合序列建模", "disadvantages": "训练速度慢"},
            {"method": "Transformer", "advantages": "并行计算", "disadvantages": "计算资源需求高"},
        ],
        gaps=["中文预训练模型资源有限", "领域适配仍有挑战"],
        future_work=["多模态融合", "低资源场景学习"],
        conclusion="深度学习在 NLP 领域取得了显著进展，但仍存在挑战。",
        references=["[1] Vaswani et al. 2017.", "[2] Devlin et al. 2018."],
        keywords=["深度学习", "NLP", "综述"],
    )
    lit_result = generator.generate_literature_review(lit_data, "markdown")
    assert "文献综述" in lit_result.title
    assert "研究主题分类" in lit_result.content
    print(f"文献综述生成成功，长度 {len(lit_result.content)} 字符")

    # 测试答辩 PPT 大纲生成
    defense_data = DefenseData(
        title="基于深度学习的中文文本分类研究",
        author="张三",
        advisor="李教授",
        degree="硕士",
        discipline="计算机科学与技术",
        defense_date="2027-06-01",
        background="文本分类是 NLP 的基础任务。",
        problem_statement="现有方法在中文长文本分类上效果不佳。",
        research_goals=["提升分类准确率", "降低计算成本"],
        related_work="已有多种文本分类方法。",
        methodology="采用改进的 BERT 模型。",
        experiments=[
            {"name": "数据集测试", "details": ["THUCNews", "ChnSentiCorp"], "description": "在公开数据集上评估。"},
        ],
        results=[{"summary": "准确率提升 3.2%"}],
        conclusions=["提出的方法有效提升了分类性能"],
        innovations=["新的注意力机制", "领域适配策略"],
        future_work=["扩展到多模态场景"],
        acknowledgments="感谢导师与各位老师！",
    )
    ppt_result = generator.generate_defense_ppt_outline(defense_data, "markdown")
    assert len(ppt_result.slides) >= 5
    assert "幻灯片" in ppt_result.content
    print(f"答辩 PPT 大纲生成成功，共 {len(ppt_result.slides)} 张幻灯片")

    # 测试进度报告生成
    progress_data = ProgressData(
        title="基于深度学习的中文文本分类研究",
        author="张三",
        advisor="李教授",
        report_date="2026-06-19",
        period="2026年6月",
        completed_work=[
            {"name": "文献调研", "description": "完成 50 篇文献阅读", "date": "2026-06-10"},
            {"name": "数据集准备", "description": "收集并清洗 THUCNews 数据", "date": "2026-06-15"},
        ],
        ongoing_work=[
            {"name": "模型设计", "description": "设计改进的 BERT 架构", "progress": "60%"},
        ],
        pending_tasks=[
            {"name": "实验验证", "deadline": "2026-07-15", "priority": "高"},
        ],
        issues=[{"description": "GPU 资源不足", "impact": "影响训练速度"}],
        risks=[{"description": "数据集质量风险", "probability": "中", "impact": "中"}],
        next_steps=["完成模型训练", "进行对比实验", "撰写论文初稿"],
    )
    progress_result = generator.generate_progress_report(progress_data, "markdown")
    assert "进度报告" in progress_result.title
    assert "已完成工作" in progress_result.content
    print(f"进度报告生成成功，长度 {len(progress_result.content)} 字符")

    # 测试周报生成
    weekly_result = generator.generate_weekly_report(progress_data, "markdown")
    assert "周报" in weekly_result.title
    print("周报生成成功")

    # 测试月报生成
    monthly_result = generator.generate_monthly_report(progress_data, "markdown")
    assert "月报" in monthly_result.title
    print("月报生成成功")

    # 测试结题报告生成
    final_result = generator.generate_final_report(proposal_data, "markdown")
    assert "结题报告" in final_result.title
    print("结题报告生成成功")

    # 测试自定义报告
    custom_result = generator.generate_custom_report(
        title="自定义报告",
        sections=[
            {"title": "第一章", "content": "内容1", "level": 1},
            {"title": "第二章", "content": "内容2", "level": 1},
        ],
        author="张三",
        output_format="markdown",
    )
    assert "自定义报告" in custom_result.title
    print("自定义报告生成成功")

    # 测试图表生成
    table = generator.generate_ascii_table(
        headers=["模型", "准确率", "F1"],
        rows=[["BERT", "92.3%", "91.8%"], ["GPT", "90.1%", "89.5%"]],
        caption="性能对比",
    )
    assert "BERT" in table
    print("ASCII 表格生成成功")

    md_table = generator.generate_markdown_table(
        headers=["模型", "准确率"],
        rows=[["BERT", "92.3%"]],
    )
    assert "|" in md_table
    print("Markdown 表格生成成功")

    progress_bar = generator.generate_progress_bar(7, 10)
    assert "70%" in progress_bar
    print(f"进度条: {progress_bar}")

    gantt = generator.generate_gantt_chart(
        tasks=[
            {"name": "文献调研", "start_week": 1, "end_week": 4},
            {"name": "模型设计", "start_week": 3, "end_week": 8},
            {"name": "实验验证", "start_week": 7, "end_week": 12},
        ],
        total_weeks=16,
    )
    assert "文献调研" in gantt
    print("甘特图生成成功")

    # 测试模板管理
    templates = generator.list_templates()
    assert "proposal" in templates
    print(f"已注册模板: {templates}")

    # 测试自定义模板注册
    generator.register_template("custom_template", {
        "title_template": "自定义: {title}",
        "sections": ["第一节", "第二节"],
    })
    assert "custom_template" in generator.list_templates()
    print("自定义模板注册成功")

    generator.shutdown()
    print("ReportGenerator 自检通过")


if __name__ == "__main__":
    _run_self_test()
