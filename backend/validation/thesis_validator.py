"""论题验证器模块

提供完整的多维度论题质量验证，包括：
    - 标题验证（长度/规范性/新颖性）
    - 摘要验证（结构/完整性/准确性）
    - 大纲验证（层次/逻辑/完整性）
    - 参考文献验证（格式/数量/时效性）
    - 研究方法验证
    - 研究方案可行性验证
    - 验证报告生成、问题清单、修改建议
    - 完整的验证规则引擎、评分算法

设计原则：
    1. 零外部依赖：仅使用 Python 标准库
    2. 线程安全：所有公共方法通过 RLock 保护
    3. 规则可配置：验证规则支持动态添加
    4. 可扩展：新增验证维度无需修改核心逻辑
"""
from __future__ import annotations

import re
import threading
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Callable, Optional


# ===== 枚举与常量 =====


class SeverityLevel:
    """问题严重级别。"""

    INFO = "info"        # 提示
    WARNING = "warning"  # 警告
    ERROR = "error"      # 错误
    CRITICAL = "critical"  # 严重错误


# 严重级别权重（用于评分）
SEVERITY_WEIGHTS = {
    SeverityLevel.INFO: 0.05,
    SeverityLevel.WARNING: 0.15,
    SeverityLevel.ERROR: 0.3,
    SeverityLevel.CRITICAL: 0.5,
}

# 严重级别中文名
SEVERITY_NAMES = {
    SeverityLevel.INFO: "提示",
    SeverityLevel.WARNING: "警告",
    SeverityLevel.ERROR: "错误",
    SeverityLevel.CRITICAL: "严重错误",
}

# 验证维度
VALIDATION_DIMENSIONS = {
    "title": "标题验证",
    "abstract": "摘要验证",
    "outline": "大纲验证",
    "references": "参考文献验证",
    "method": "研究方法验证",
    "feasibility": "可行性验证",
    "novelty": "新颖性验证",
    "completeness": "完整性验证",
}

# 维度权重（用于综合评分）
DIMENSION_WEIGHTS = {
    "title": 0.1,
    "abstract": 0.15,
    "outline": 0.15,
    "references": 0.15,
    "method": 0.15,
    "feasibility": 0.15,
    "novelty": 0.1,
    "completeness": 0.05,
}

# 标题长度限制
TITLE_MIN_LENGTH = 5
TITLE_MAX_LENGTH = 30  # 学位论文标题通常不超过30字

# 摘要长度限制
ABSTRACT_MIN_LENGTH = 200
ABSTRACT_MAX_LENGTH = 1000

# 参考文献数量基线
REFERENCE_COUNT_BASELINE = {
    "master": 30,
    "doctor": 50,
}

# 参考文献时效性（近5年占比阈值）
RECENT_YEARS_THRESHOLD = 5
RECENT_RATIO_MIN = 0.3

# 标题常见问题模式
TITLE_FORBIDDEN_PATTERNS = [
    (r"^(关于|有关)", "标题不应以「关于/有关」开头"),
    (r"(研究$|的研究$)", "标题结尾「研究」过于宽泛，建议具体化"),
    (r"(浅谈|浅析|初探|试论)", "标题含「浅谈/浅析/初探/试论」，学术性不足"),
    (r"(。|，|；|！|？)", "标题不应包含标点符号"),
    (r"^\d+", "标题不应以数字开头"),
]

# 摘要结构关键词
ABSTRACT_STRUCTURE_KEYWORDS = {
    "background": ["背景", "现状", "近年来", "随着", "目前"],
    "problem": ["问题", "挑战", "不足", "缺陷", "瓶颈"],
    "method": ["方法", "采用", "基于", "通过", "提出", "构建"],
    "result": ["结果", "发现", "表明", "显示", "得到"],
    "conclusion": ["结论", "意义", "贡献", "价值", "启示"],
}

# 大纲层级标记
OUTLINE_LEVEL_PATTERNS = [
    re.compile(r"^第[一二三四五六七八九十]+章\s"),
    re.compile(r"^[一二三四五六七八九十]+、"),
    re.compile(r"^\d+\.\d+\s"),
    re.compile(r"^\d+\.\d+\.\d+\s"),
    re.compile(r"^（[一二三四五六七八九十]+）"),
]


# ===== 数据结构 =====


@dataclass
class ValidationIssue:
    """验证问题。

    Attributes:
        id: 问题 ID。
        dimension: 验证维度。
        severity: 严重级别。
        code: 问题代码。
        message: 问题描述。
        location: 问题位置（如章节、字段）。
        suggestion: 修改建议。
        context: 问题上下文。
    """

    id: str = ""
    dimension: str = ""
    severity: str = SeverityLevel.WARNING
    code: str = ""
    message: str = ""
    location: str = ""
    suggestion: str = ""
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DimensionResult:
    """单维度验证结果。

    Attributes:
        dimension: 维度名。
        score: 评分（0-100）。
        issues: 该维度的问题列表。
        passed: 是否通过。
        summary: 维度总结。
    """

    dimension: str = ""
    score: float = 0.0
    issues: list[ValidationIssue] = field(default_factory=list)
    passed: bool = True
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "score": self.score,
            "issues": [i.to_dict() for i in self.issues],
            "passed": self.passed,
            "summary": self.summary,
        }


@dataclass
class ValidationReport:
    """验证报告。

    Attributes:
        id: 报告 ID。
        thesis_id: 论题 ID。
        timestamp: 验证时间。
        overall_score: 综合评分（0-100）。
        dimension_results: 各维度结果。
        all_issues: 所有问题列表。
        critical_count: 严重问题数。
        error_count: 错误数。
        warning_count: 警告数。
        info_count: 提示数。
        passed: 是否整体通过。
        recommendations: 总体建议。
        metadata: 元数据。
    """

    id: str = ""
    thesis_id: str = ""
    timestamp: str = ""
    overall_score: float = 0.0
    dimension_results: dict[str, DimensionResult] = field(default_factory=dict)
    all_issues: list[ValidationIssue] = field(default_factory=list)
    critical_count: int = 0
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    passed: bool = False
    recommendations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "thesis_id": self.thesis_id,
            "timestamp": self.timestamp,
            "overall_score": round(self.overall_score, 2),
            "dimension_results": {
                k: v.to_dict() for k, v in self.dimension_results.items()
            },
            "all_issues": [i.to_dict() for i in self.all_issues],
            "issue_counts": {
                "critical": self.critical_count,
                "error": self.error_count,
                "warning": self.warning_count,
                "info": self.info_count,
                "total": len(self.all_issues),
            },
            "passed": self.passed,
            "recommendations": self.recommendations,
            "metadata": self.metadata,
        }


# ===== 验证规则 =====


@dataclass
class ValidationRule:
    """验证规则。

    Attributes:
        id: 规则 ID。
        name: 规则名称。
        dimension: 所属维度。
        severity: 违反时的严重级别。
        description: 规则描述。
        validator: 验证函数。
        enabled: 是否启用。
    """

    id: str = ""
    name: str = ""
    dimension: str = ""
    severity: str = SeverityLevel.WARNING
    description: str = ""
    validator: Optional[Callable[[dict[str, Any]], list[ValidationIssue]]] = None
    enabled: bool = True

    def validate(self, data: dict[str, Any]) -> list[ValidationIssue]:
        """执行验证。"""
        if not self.enabled or self.validator is None:
            return []
        try:
            return self.validator(data) or []
        except Exception as e:
            return [ValidationIssue(
                id=str(uuid.uuid4().hex[:8]),
                dimension=self.dimension,
                severity=SeverityLevel.ERROR,
                code="rule_execution_error",
                message=f"规则执行异常: {e}",
                location=self.name,
            )]


# ===== 工具函数 =====


def _now_iso() -> str:
    """返回当前时间的 ISO 格式字符串。"""
    return datetime.now().isoformat()


def _new_id(prefix: str = "issue") -> str:
    """生成带前缀的唯一 ID。"""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _count_chinese_chars(text: str) -> int:
    """统计中文字符数。"""
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def _count_words(text: str) -> int:
    """统计字数（中文按字，英文按词）。"""
    cn_count = _count_chinese_chars(text)
    en_words = re.findall(r"[a-zA-Z]+", text)
    return cn_count + len(en_words)


def _extract_year(text: str) -> Optional[int]:
    """从文本中提取年份。"""
    match = re.search(r"\b(19|20)\d{2}\b", text)
    if match:
        return int(match.group())
    return None


# ===== 标题验证器 =====


class TitleValidator:
    """标题验证器。"""

    def validate(self, data: dict[str, Any]) -> list[ValidationIssue]:
        """验证标题。"""
        title = data.get("title", "")
        issues: list[ValidationIssue] = []
        if not title:
            issues.append(self._make_issue(
                "title_empty", SeverityLevel.CRITICAL,
                "标题为空", "title",
                "请提供论题标题",
            ))
            return issues
        # 长度验证
        char_count = len(title)
        if char_count < TITLE_MIN_LENGTH:
            issues.append(self._make_issue(
                "title_too_short", SeverityLevel.ERROR,
                f"标题过短（{char_count}字），建议至少{TITLE_MIN_LENGTH}字",
                "title",
                f"扩展标题，使其更具体地反映研究内容",
            ))
        if char_count > TITLE_MAX_LENGTH:
            issues.append(self._make_issue(
                "title_too_long", SeverityLevel.WARNING,
                f"标题过长（{char_count}字），建议不超过{TITLE_MAX_LENGTH}字",
                "title",
                "精简标题，去除冗余词汇",
            ))
        # 规范性验证
        for pattern, message in TITLE_FORBIDDEN_PATTERNS:
            if re.search(pattern, title):
                issues.append(self._make_issue(
                    "title_format", SeverityLevel.WARNING,
                    message, "title",
                    "参考优秀学位论文标题格式",
                ))
        # 新颖性验证（简单实现：检查是否过于宽泛）
        vague_words = ["研究", "分析", "探讨", "应用"]
        vague_count = sum(1 for w in vague_words if w in title)
        if vague_count >= 2:
            issues.append(self._make_issue(
                "title_vague", SeverityLevel.WARNING,
                "标题含多个宽泛词汇，针对性不足",
                "title",
                "明确研究对象、方法或视角，提升标题具体性",
            ))
        # 检查是否含问号（疑问式标题）
        if "？" in title or "?" in title:
            issues.append(self._make_issue(
                "title_question", SeverityLevel.INFO,
                "标题为疑问句式，需确保学术规范允许",
                "title",
                "确认所在学科是否接受疑问式标题",
            ))
        return issues

    def _make_issue(self, code: str, severity: str, message: str,
                    location: str, suggestion: str) -> ValidationIssue:
        """构造验证问题。"""
        return ValidationIssue(
            id=_new_id(),
            dimension="title",
            severity=severity,
            code=code,
            message=message,
            location=location,
            suggestion=suggestion,
        )


# ===== 摘要验证器 =====


class AbstractValidator:
    """摘要验证器。"""

    def validate(self, data: dict[str, Any]) -> list[ValidationIssue]:
        """验证摘要。"""
        abstract = data.get("abstract", "")
        issues: list[ValidationIssue] = []
        if not abstract:
            issues.append(self._make_issue(
                "abstract_empty", SeverityLevel.CRITICAL,
                "摘要为空", "abstract",
                "请提供论题摘要",
            ))
            return issues
        # 长度验证
        word_count = _count_words(abstract)
        if word_count < ABSTRACT_MIN_LENGTH:
            issues.append(self._make_issue(
                "abstract_too_short", SeverityLevel.ERROR,
                f"摘要过短（{word_count}字），建议至少{ABSTRACT_MIN_LENGTH}字",
                "abstract",
                "补充研究背景、方法、结果等内容",
            ))
        if word_count > ABSTRACT_MAX_LENGTH:
            issues.append(self._make_issue(
                "abstract_too_long", SeverityLevel.WARNING,
                f"摘要过长（{word_count}字），建议不超过{ABSTRACT_MAX_LENGTH}字",
                "abstract",
                "精简摘要，突出核心内容",
            ))
        # 结构完整性验证
        structure_issues = self._check_structure(abstract)
        issues.extend(structure_issues)
        # 准确性验证（简单实现）
        if "本文" in abstract and ("提出" in abstract or "构建" in abstract):
            pass  # 良好
        else:
            issues.append(self._make_issue(
                "abstract_lack_statement", SeverityLevel.INFO,
                "摘要未明确表述本文的核心贡献",
                "abstract",
                "建议使用「本文提出/构建/发现...」明确陈述贡献",
            ))
        # 检查是否有数据支撑
        has_numbers = bool(re.search(r"\d+%|\d+\.\d+|[\d,]+个|[\d,]+项", abstract))
        if not has_numbers:
            issues.append(self._make_issue(
                "abstract_lack_data", SeverityLevel.INFO,
                "摘要缺少具体数据支撑",
                "abstract",
                "建议补充关键数据指标",
            ))
        return issues

    def _check_structure(self, abstract: str) -> list[ValidationIssue]:
        """检查摘要结构完整性。"""
        issues: list[ValidationIssue] = []
        for section, keywords in ABSTRACT_STRUCTURE_KEYWORDS.items():
            found = any(kw in abstract for kw in keywords)
            if not found:
                section_names = {
                    "background": "研究背景",
                    "problem": "问题陈述",
                    "method": "研究方法",
                    "result": "研究结果",
                    "conclusion": "研究结论",
                }
                issues.append(self._make_issue(
                    f"abstract_missing_{section}", SeverityLevel.WARNING,
                    f"摘要缺少{section_names[section]}部分",
                    "abstract",
                    f"补充{section_names[section]}相关内容",
                ))
        return issues

    def _make_issue(self, code: str, severity: str, message: str,
                    location: str, suggestion: str) -> ValidationIssue:
        return ValidationIssue(
            id=_new_id(),
            dimension="abstract",
            severity=severity,
            code=code,
            message=message,
            location=location,
            suggestion=suggestion,
        )


# ===== 大纲验证器 =====


class OutlineValidator:
    """大纲验证器。"""

    def validate(self, data: dict[str, Any]) -> list[ValidationIssue]:
        """验证大纲。"""
        outline = data.get("outline", "")
        issues: list[ValidationIssue] = []
        if not outline:
            issues.append(self._make_issue(
                "outline_empty", SeverityLevel.CRITICAL,
                "大纲为空", "outline",
                "请提供论题大纲",
            ))
            return issues
        # 解析大纲层次
        lines = [line.strip() for line in outline.split("\n") if line.strip()]
        if not lines:
            issues.append(self._make_issue(
                "outline_empty", SeverityLevel.CRITICAL,
                "大纲无有效内容", "outline",
                "请提供有效的章节结构",
            ))
            return issues
        # 层次验证
        hierarchy_issues = self._check_hierarchy(lines)
        issues.extend(hierarchy_issues)
        # 逻辑性验证
        logic_issues = self._check_logic(lines)
        issues.extend(logic_issues)
        # 完整性验证
        completeness_issues = self._check_completeness(lines)
        issues.extend(completeness_issues)
        # 章节数量验证
        chapter_count = sum(1 for line in lines if re.match(r"^第[一二三四五六七八九十]+章", line))
        if chapter_count < 3:
            issues.append(self._make_issue(
                "outline_few_chapters", SeverityLevel.WARNING,
                f"章节数过少（{chapter_count}章），建议至少3章",
                "outline",
                "补充必要章节，如文献综述、研究方法、结果分析等",
            ))
        if chapter_count > 8:
            issues.append(self._make_issue(
                "outline_many_chapters", SeverityLevel.INFO,
                f"章节数较多（{chapter_count}章），注意结构平衡",
                "outline",
                "考虑合并相近章节",
            ))
        return issues

    def _check_hierarchy(self, lines: list[str]) -> list[ValidationIssue]:
        """检查层次结构。"""
        issues: list[ValidationIssue] = []
        prev_level = 0
        for i, line in enumerate(lines):
            level = self._get_level(line)
            if level == 0:
                continue
            # 检查层级跳跃
            if level > prev_level + 1 and prev_level > 0:
                issues.append(self._make_issue(
                    "outline_hierarchy_jump", SeverityLevel.WARNING,
                    f"第{i+1}行层级跳跃（从{prev_level}级跳到{level}级）",
                    f"line {i+1}",
                    "保持层级递进，避免跨级",
                ))
            prev_level = level
        return issues

    def _get_level(self, line: str) -> int:
        """获取行的层级。"""
        for i, pattern in enumerate(OUTLINE_LEVEL_PATTERNS):
            if pattern.match(line):
                return i + 1
        return 0

    def _check_logic(self, lines: list[str]) -> list[ValidationIssue]:
        """检查逻辑性。"""
        issues: list[ValidationIssue] = []
        # 检查是否有文献综述章节
        has_lit_review = any(
            "文献综述" in line or "文献回顾" in line or "研究现状" in line
            for line in lines
        )
        if not has_lit_review:
            issues.append(self._make_issue(
                "outline_no_lit_review", SeverityLevel.ERROR,
                "大纲缺少文献综述章节",
                "outline",
                "添加文献综述章节，梳理已有研究",
            ))
        # 检查是否有研究方法章节
        has_method = any(
            "研究方法" in line or "方法论" in line or "研究设计" in line
            for line in lines
        )
        if not has_method:
            issues.append(self._make_issue(
                "outline_no_method", SeverityLevel.ERROR,
                "大纲缺少研究方法章节",
                "outline",
                "添加研究方法章节，说明研究设计",
            ))
        # 检查是否有结论章节
        has_conclusion = any(
            "结论" in line or "总结" in line or "结语" in line
            for line in lines
        )
        if not has_conclusion:
            issues.append(self._make_issue(
                "outline_no_conclusion", SeverityLevel.ERROR,
                "大纲缺少结论章节",
                "outline",
                "添加结论章节，总结研究发现",
            ))
        return issues

    def _check_completeness(self, lines: list[str]) -> list[ValidationIssue]:
        """检查完整性。"""
        issues: list[ValidationIssue] = []
        # 检查章节标题是否过短
        for i, line in enumerate(lines):
            level = self._get_level(line)
            if level > 0:
                # 去除层级标记后的内容
                content = re.sub(r"^(第[一二三四五六七八九十]+章\s|[一二三四五六七八九十]+、|\d+\.\d+\s*|\d+\.\d+\.\d+\s*|（[一二三四五六七八九十]+）)", "", line).strip()
                if content and len(content) < 4:
                    issues.append(self._make_issue(
                        "outline_short_title", SeverityLevel.INFO,
                        f"第{i+1}行章节标题过短「{content}」",
                        f"line {i+1}",
                        "扩展章节标题，使其更明确",
                    ))
        return issues

    def _make_issue(self, code: str, severity: str, message: str,
                    location: str, suggestion: str) -> ValidationIssue:
        return ValidationIssue(
            id=_new_id(),
            dimension="outline",
            severity=severity,
            code=code,
            message=message,
            location=location,
            suggestion=suggestion,
        )


# ===== 参考文献验证器 =====


class ReferencesValidator:
    """参考文献验证器。"""

    def validate(self, data: dict[str, Any]) -> list[ValidationIssue]:
        """验证参考文献。"""
        references = data.get("references", [])
        degree = data.get("degree", "master")
        issues: list[ValidationIssue] = []
        if not references:
            issues.append(self._make_issue(
                "references_empty", SeverityLevel.CRITICAL,
                "参考文献为空", "references",
                "请提供参考文献列表",
            ))
            return issues
        # 数量验证
        count = len(references)
        baseline = REFERENCE_COUNT_BASELINE.get(degree, 30)
        if count < baseline:
            issues.append(self._make_issue(
                "references_insufficient", SeverityLevel.ERROR,
                f"参考文献数量不足（{count}篇），{degree}建议至少{baseline}篇",
                "references",
                f"补充参考文献至{baseline}篇以上",
            ))
        # 格式验证
        format_issues = self._check_format(references)
        issues.extend(format_issues)
        # 时效性验证
        timeliness_issues = self._check_timeliness(references)
        issues.extend(timeliness_issues)
        # 类型多样性验证
        diversity_issues = self._check_diversity(references)
        issues.extend(diversity_issues)
        return issues

    def _check_format(self, references: list[Any]) -> list[ValidationIssue]:
        """检查格式规范性。"""
        issues: list[ValidationIssue] = []
        for i, ref in enumerate(references):
            if isinstance(ref, str):
                ref_text = ref
            elif isinstance(ref, dict):
                ref_text = ref.get("text", "") or ref.get("title", "")
            else:
                ref_text = str(ref)
            # 检查是否含作者
            if not re.search(r"[A-Za-z\u4e00-\u9fff].*\.", ref_text):
                issues.append(self._make_issue(
                    "ref_no_author", SeverityLevel.WARNING,
                    f"第{i+1}条参考文献可能缺少作者信息",
                    f"reference {i+1}",
                    "补充作者姓名",
                ))
            # 检查是否含年份
            if not _extract_year(ref_text):
                issues.append(self._make_issue(
                    "ref_no_year", SeverityLevel.WARNING,
                    f"第{i+1}条参考文献缺少年份",
                    f"reference {i+1}",
                    "补充发表年份",
                ))
            # 检查是否含标题
            if len(ref_text) < 20:
                issues.append(self._make_issue(
                    "ref_too_short", SeverityLevel.WARNING,
                    f"第{i+1}条参考文献信息不完整",
                    f"reference {i+1}",
                    "补充完整的出版信息",
                ))
        return issues

    def _check_timeliness(self, references: list[Any]) -> list[ValidationIssue]:
        """检查时效性。"""
        issues: list[ValidationIssue] = []
        current_year = datetime.now().year
        recent_count = 0
        total_with_year = 0
        years: list[int] = []
        for ref in references:
            ref_text = ref if isinstance(ref, str) else str(ref)
            year = _extract_year(ref_text)
            if year:
                total_with_year += 1
                years.append(year)
                if current_year - year <= RECENT_YEARS_THRESHOLD:
                    recent_count += 1
        if total_with_year > 0:
            recent_ratio = recent_count / total_with_year
            if recent_ratio < RECENT_RATIO_MIN:
                issues.append(self._make_issue(
                    "references_outdated", SeverityLevel.WARNING,
                    f"近{RECENT_YEARS_THRESHOLD}年文献占比过低（{recent_ratio:.0%}）",
                    "references",
                    f"增加近{RECENT_YEARS_THRESHOLD}年发表的文献，占比建议≥{RECENT_RATIO_MIN:.0%}",
                ))
            # 检查是否有过于陈旧的文献
            if years:
                oldest = min(years)
                if current_year - oldest > 20:
                    issues.append(self._make_issue(
                        "references_very_old", SeverityLevel.INFO,
                        f"存在{current_year - oldest}年前的文献，确认是否为经典文献",
                        "references",
                        "经典文献可保留，但需确保研究前沿性",
                    ))
        return issues

    def _check_diversity(self, references: list[Any]) -> list[ValidationIssue]:
        """检查类型多样性。"""
        issues: list[ValidationIssue] = []
        # 简单分类
        journal_count = 0
        book_count = 0
        conference_count = 0
        other_count = 0
        for ref in references:
            ref_text = ref if isinstance(ref, str) else str(ref)
            if any(kw in ref_text for kw in ["Journal", "期刊", "学报", "Vol", "pp."]):
                journal_count += 1
            elif any(kw in ref_text for kw in ["Press", "出版社", "出版"]):
                book_count += 1
            elif any(kw in ref_text for kw in ["Conference", "会议", "Proceedings", "Symposium"]):
                conference_count += 1
            else:
                other_count += 1
        total = len(references)
        if total > 0:
            if journal_count / total < 0.5:
                issues.append(self._make_issue(
                    "references_few_journals", SeverityLevel.INFO,
                    f"期刊文献占比偏低（{journal_count}/{total}）",
                    "references",
                    "增加学术期刊论文比例",
                ))
            if book_count == 0 and total > 10:
                issues.append(self._make_issue(
                    "references_no_books", SeverityLevel.INFO,
                    "参考文献中无专著",
                    "references",
                    "适当引用经典专著",
                ))
        return issues

    def _make_issue(self, code: str, severity: str, message: str,
                    location: str, suggestion: str) -> ValidationIssue:
        return ValidationIssue(
            id=_new_id(),
            dimension="references",
            severity=severity,
            code=code,
            message=message,
            location=location,
            suggestion=suggestion,
        )


# ===== 研究方法验证器 =====


class MethodValidator:
    """研究方法验证器。"""

    def validate(self, data: dict[str, Any]) -> list[ValidationIssue]:
        """验证研究方法。"""
        method = data.get("method", "")
        method_detail = data.get("method_detail", "")
        issues: list[ValidationIssue] = []
        if not method:
            issues.append(self._make_issue(
                "method_empty", SeverityLevel.CRITICAL,
                "未指定研究方法", "method",
                "请明确研究方法",
            ))
            return issues
        # 方法描述充分性
        if not method_detail:
            issues.append(self._make_issue(
                "method_no_detail", SeverityLevel.ERROR,
                "研究方法缺少详细说明",
                "method",
                "详细描述方法的设计、实施与分析过程",
            ))
        else:
            word_count = _count_words(method_detail)
            if word_count < 100:
                issues.append(self._make_issue(
                    "method_detail_short", SeverityLevel.WARNING,
                    f"研究方法描述过短（{word_count}字）",
                    "method",
                    "扩展方法描述，包括样本、工具、流程等",
                ))
        # 方法-学科匹配（简单实现）
        discipline = data.get("discipline", "")
        if discipline and method:
            match_issues = self._check_method_discipline_match(method, discipline)
            issues.extend(match_issues)
        # 方法合理性检查
        if "实验" in method and "样本" not in method_detail and "被试" not in method_detail:
            issues.append(self._make_issue(
                "method_no_sample", SeverityLevel.WARNING,
                "实验研究未说明样本情况",
                "method",
                "明确样本来源、数量与特征",
            ))
        if "问卷" in method and "信度" not in method_detail and "效度" not in method_detail:
            issues.append(self._make_issue(
                "method_no_reliability", SeverityLevel.WARNING,
                "问卷调查未提及信效度检验",
                "method",
                "说明问卷的信度与效度检验方法",
            ))
        if "访谈" in method and "编码" not in method_detail:
            issues.append(self._make_issue(
                "method_no_coding", SeverityLevel.INFO,
                "访谈研究未说明编码方法",
                "method",
                "说明访谈数据的编码与分析方法",
            ))
        return issues

    def _check_method_discipline_match(self, method: str, discipline: str) -> list[ValidationIssue]:
        """检查方法与学科匹配度。"""
        issues: list[ValidationIssue] = []
        # 简单规则：人文学科偏好定性方法，理工科偏好定量方法
        humanities_codes = ["01", "05", "06"]
        science_codes = ["07", "08", "10"]
        gate_code = discipline[:2] if len(discipline) >= 2 else ""
        if gate_code in humanities_codes and any(
            kw in method for kw in ["回归", "方差分析", "结构方程", "量化"]
        ):
            issues.append(self._make_issue(
                "method_discipline_mismatch", SeverityLevel.INFO,
                "人文学科使用定量方法，需说明合理性",
                "method",
                "说明在人文研究中使用定量方法的依据",
            ))
        if gate_code in science_codes and any(
            kw in method for kw in ["民族志", "田野调查", "叙事分析"]
        ):
            issues.append(self._make_issue(
                "method_discipline_mismatch", SeverityLevel.INFO,
                "理工科使用定性方法，需说明合理性",
                "method",
                "说明在理工研究中使用定性方法的依据",
            ))
        return issues

    def _make_issue(self, code: str, severity: str, message: str,
                    location: str, suggestion: str) -> ValidationIssue:
        return ValidationIssue(
            id=_new_id(),
            dimension="method",
            severity=severity,
            code=code,
            message=message,
            location=location,
            suggestion=suggestion,
        )


# ===== 可行性验证器 =====


class FeasibilityValidator:
    """研究方案可行性验证器。"""

    def validate(self, data: dict[str, Any]) -> list[ValidationIssue]:
        """验证可行性。"""
        feasibility = data.get("feasibility_analysis", "")
        timeline = data.get("timeline", "")
        resources = data.get("resources", "")
        issues: list[ValidationIssue] = []
        # 可行性分析
        if not feasibility:
            issues.append(self._make_issue(
                "feasibility_empty", SeverityLevel.ERROR,
                "缺少可行性分析", "feasibility",
                "从技术、资源、时间等维度分析可行性",
            ))
        else:
            word_count = _count_words(feasibility)
            if word_count < 100:
                issues.append(self._make_issue(
                    "feasibility_short", SeverityLevel.WARNING,
                    f"可行性分析过短（{word_count}字）",
                    "feasibility",
                    "详细分析技术、数据、时间、经费等可行性",
                ))
            # 检查是否涵盖关键维度
            dimensions_covered = []
            for dim, keywords in {
                "技术": ["技术", "方法", "工具", "平台"],
                "数据": ["数据", "样本", "资料", "来源"],
                "时间": ["时间", "周期", "进度", "计划"],
                "资源": ["经费", "设备", "人员", "资源"],
            }.items():
                if any(kw in feasibility for kw in keywords):
                    dimensions_covered.append(dim)
            missing = ["技术", "数据", "时间", "资源"]
            for dim in missing:
                if dim not in dimensions_covered:
                    issues.append(self._make_issue(
                        f"feasibility_no_{dim}", SeverityLevel.WARNING,
                        f"可行性分析未涉及{dim}维度",
                        "feasibility",
                        f"补充{dim}可行性分析",
                    ))
        # 时间规划
        if not timeline:
            issues.append(self._make_issue(
                "timeline_empty", SeverityLevel.WARNING,
                "缺少时间规划", "feasibility",
                "制定详细的研究进度计划",
            ))
        # 资源说明
        if not resources:
            issues.append(self._make_issue(
                "resources_empty", SeverityLevel.INFO,
                "未说明资源需求", "feasibility",
                "说明所需设备、数据、经费等资源",
            ))
        return issues

    def _make_issue(self, code: str, severity: str, message: str,
                    location: str, suggestion: str) -> ValidationIssue:
        return ValidationIssue(
            id=_new_id(),
            dimension="feasibility",
            severity=severity,
            code=code,
            message=message,
            location=location,
            suggestion=suggestion,
        )


# ===== 新颖性验证器 =====


class NoveltyValidator:
    """新颖性验证器。"""

    def validate(self, data: dict[str, Any]) -> list[ValidationIssue]:
        """验证新颖性。"""
        differentiation = data.get("differentiation", "")
        inspiration_source = data.get("inspiration_source", "")
        issues: list[ValidationIssue] = []
        if not differentiation:
            issues.append(self._make_issue(
                "novelty_empty", SeverityLevel.ERROR,
                "缺少创新点/差异化说明", "novelty",
                "明确本研究与已有研究的差异",
            ))
        else:
            # 检查创新点表述
            if "首次" in differentiation or "首创" in differentiation:
                issues.append(self._make_issue(
                    "novelty_claim_strong", SeverityLevel.INFO,
                    "创新点表述较强（首次/首创），需充分论证",
                    "novelty",
                    "提供文献证据支持「首次」的表述",
                ))
            # 检查创新维度
            innovation_dims = []
            for dim, keywords in {
                "理论创新": ["理论", "概念", "框架", "模型"],
                "方法创新": ["方法", "算法", "技术", "工具"],
                "数据创新": ["数据", "样本", "语料", "数据集"],
                "应用创新": ["应用", "场景", "领域", "实践"],
            }.items():
                if any(kw in differentiation for kw in keywords):
                    innovation_dims.append(dim)
            if not innovation_dims:
                issues.append(self._make_issue(
                    "novelty_unclear", SeverityLevel.WARNING,
                    "创新点类型不明确",
                    "novelty",
                    "明确是理论/方法/数据/应用创新",
                ))
        # 灵感来源
        if not inspiration_source:
            issues.append(self._make_issue(
                "inspiration_empty", SeverityLevel.INFO,
                "未说明研究灵感来源", "novelty",
                "说明研究想法的来源与演进",
            ))
        return issues

    def _make_issue(self, code: str, severity: str, message: str,
                    location: str, suggestion: str) -> ValidationIssue:
        return ValidationIssue(
            id=_new_id(),
            dimension="novelty",
            severity=severity,
            code=code,
            message=message,
            location=location,
            suggestion=suggestion,
        )


# ===== 完整性验证器 =====


class CompletenessValidator:
    """完整性验证器。"""

    REQUIRED_FIELDS = [
        "title", "abstract", "outline", "references",
        "method", "feasibility_analysis", "differentiation",
    ]

    def validate(self, data: dict[str, Any]) -> list[ValidationIssue]:
        """验证完整性。"""
        issues: list[ValidationIssue] = []
        for field_name in self.REQUIRED_FIELDS:
            value = data.get(field_name)
            if value is None or (isinstance(value, str) and not value.strip()) or (
                isinstance(value, list) and len(value) == 0
            ):
                field_names = {
                    "title": "标题",
                    "abstract": "摘要",
                    "outline": "大纲",
                    "references": "参考文献",
                    "method": "研究方法",
                    "feasibility_analysis": "可行性分析",
                    "differentiation": "创新点",
                }
                issues.append(self._make_issue(
                    f"missing_{field_name}", SeverityLevel.ERROR,
                    f"缺少必填字段：{field_names.get(field_name, field_name)}",
                    field_name,
                    f"补充{field_names.get(field_name, field_name)}",
                ))
        return issues

    def _make_issue(self, code: str, severity: str, message: str,
                    location: str, suggestion: str) -> ValidationIssue:
        return ValidationIssue(
            id=_new_id(),
            dimension="completeness",
            severity=severity,
            code=code,
            message=message,
            location=location,
            suggestion=suggestion,
        )


# ===== 论题验证器主类 =====


class ThesisValidator:
    """论题验证器主类。

    整合多个维度验证器，提供：
        - 多维度验证（标题/摘要/大纲/参考文献/方法/可行性/新颖性/完整性）
        - 验证规则引擎（支持动态添加规则）
        - 评分算法（基于问题严重级别）
        - 验证报告生成
        - 问题清单与修改建议

    线程安全：所有公共方法通过 RLock 保护。
    """

    def __init__(self) -> None:
        """初始化验证器，注册内置验证器。"""
        self._lock = threading.RLock()
        # 维度验证器
        self._validators: dict[str, Callable[[dict[str, Any]], list[ValidationIssue]]] = {
            "title": TitleValidator().validate,
            "abstract": AbstractValidator().validate,
            "outline": OutlineValidator().validate,
            "references": ReferencesValidator().validate,
            "method": MethodValidator().validate,
            "feasibility": FeasibilityValidator().validate,
            "novelty": NoveltyValidator().validate,
            "completeness": CompletenessValidator().validate,
        }
        # 自定义规则
        self._custom_rules: list[ValidationRule] = []
        # 历史报告
        self._history: list[ValidationReport] = []

    def register_validator(self, dimension: str,
                           validator: Callable[[dict[str, Any]], list[ValidationIssue]]) -> None:
        """注册维度验证器。

        Args:
            dimension: 维度名。
            validator: 验证函数。
        """
        with self._lock:
            self._validators[dimension] = validator

    def add_rule(self, rule: ValidationRule) -> None:
        """添加自定义验证规则。"""
        with self._lock:
            self._custom_rules.append(rule)

    def remove_rule(self, rule_id: str) -> bool:
        """移除自定义规则。"""
        with self._lock:
            for i, rule in enumerate(self._custom_rules):
                if rule.id == rule_id:
                    self._custom_rules.pop(i)
                    return True
            return False

    def validate(self, thesis_data: dict[str, Any],
                 dimensions: Optional[list[str]] = None) -> ValidationReport:
        """执行完整验证。

        Args:
            thesis_data: 论题数据字典。
            dimensions: 指定验证的维度列表。None 表示全部。

        Returns:
            验证报告。
        """
        with self._lock:
            report = ValidationReport(
                id=_new_id("report"),
                thesis_id=thesis_data.get("id", ""),
                timestamp=_now_iso(),
            )
            target_dimensions = dimensions or list(self._validators.keys())
            all_issues: list[ValidationIssue] = []
            for dim in target_dimensions:
                validator = self._validators.get(dim)
                if validator is None:
                    continue
                try:
                    issues = validator(thesis_data)
                except Exception as e:
                    issues = [ValidationIssue(
                        id=_new_id(),
                        dimension=dim,
                        severity=SeverityLevel.ERROR,
                        code="validator_error",
                        message=f"验证器执行异常: {e}",
                        location=dim,
                    )]
                # 执行自定义规则
                for rule in self._custom_rules:
                    if rule.dimension == dim:
                        issues.extend(rule.validate(thesis_data))
                # 计算维度评分
                score = self._compute_dimension_score(issues)
                passed = score >= 60 and not any(
                    i.severity == SeverityLevel.CRITICAL for i in issues
                )
                summary = self._generate_dimension_summary(dim, issues, score)
                report.dimension_results[dim] = DimensionResult(
                    dimension=dim,
                    score=score,
                    issues=issues,
                    passed=passed,
                    summary=summary,
                )
                all_issues.extend(issues)
            # 统计问题
            report.all_issues = all_issues
            report.critical_count = sum(1 for i in all_issues if i.severity == SeverityLevel.CRITICAL)
            report.error_count = sum(1 for i in all_issues if i.severity == SeverityLevel.ERROR)
            report.warning_count = sum(1 for i in all_issues if i.severity == SeverityLevel.WARNING)
            report.info_count = sum(1 for i in all_issues if i.severity == SeverityLevel.INFO)
            # 综合评分
            report.overall_score = self._compute_overall_score(report.dimension_results)
            # 是否通过
            report.passed = (
                report.critical_count == 0
                and report.overall_score >= 60
                and all(r.passed for r in report.dimension_results.values())
            )
            # 总体建议
            report.recommendations = self._generate_recommendations(report)
            # 保存历史
            self._history.append(report)
            return report

    def _compute_dimension_score(self, issues: list[ValidationIssue]) -> float:
        """计算维度评分。

        基础分100，按问题严重级别扣分。

        Args:
            issues: 该维度的问题列表。

        Returns:
            评分（0-100）。
        """
        score = 100.0
        for issue in issues:
            penalty = SEVERITY_WEIGHTS.get(issue.severity, 0.1) * 100
            score -= penalty
        return max(0.0, min(100.0, score))

    def _compute_overall_score(self, dimension_results: dict[str, DimensionResult]) -> float:
        """计算综合评分。

        基于各维度评分与权重的加权平均。

        Args:
            dimension_results: 各维度结果。

        Returns:
            综合评分（0-100）。
        """
        total_weight = 0.0
        weighted_sum = 0.0
        for dim, result in dimension_results.items():
            weight = DIMENSION_WEIGHTS.get(dim, 0.1)
            weighted_sum += result.score * weight
            total_weight += weight
        if total_weight == 0:
            return 0.0
        return weighted_sum / total_weight

    def _generate_dimension_summary(self, dimension: str,
                                    issues: list[ValidationIssue],
                                    score: float) -> str:
        """生成维度总结。"""
        dim_name = VALIDATION_DIMENSIONS.get(dimension, dimension)
        if not issues:
            return f"{dim_name}验证通过，评分{score:.1f}"
        critical = sum(1 for i in issues if i.severity == SeverityLevel.CRITICAL)
        error = sum(1 for i in issues if i.severity == SeverityLevel.ERROR)
        warning = sum(1 for i in issues if i.severity == SeverityLevel.WARNING)
        parts: list[str] = []
        if critical:
            parts.append(f"{critical}个严重问题")
        if error:
            parts.append(f"{error}个错误")
        if warning:
            parts.append(f"{warning}个警告")
        info = sum(1 for i in issues if i.severity == SeverityLevel.INFO)
        if info:
            parts.append(f"{info}个提示")
        return f"{dim_name}评分{score:.1f}，存在{'、'.join(parts)}"

    def _generate_recommendations(self, report: ValidationReport) -> list[str]:
        """生成总体建议。"""
        recommendations: list[str] = []
        # 严重问题优先
        if report.critical_count > 0:
            recommendations.append(
                f"⚠ 存在{report.critical_count}个严重问题，必须修复后方可继续"
            )
        # 按维度排序的建议
        sorted_dims = sorted(
            report.dimension_results.items(),
            key=lambda x: x[1].score,
        )
        for dim, result in sorted_dims:
            if result.score < 60:
                dim_name = VALIDATION_DIMENSIONS.get(dim, dim)
                top_issue = result.issues[0] if result.issues else None
                if top_issue:
                    recommendations.append(
                        f"【{dim_name}】优先处理：{top_issue.message}"
                    )
        # 整体评价
        if report.overall_score >= 80:
            recommendations.append(f"✓ 整体质量良好（{report.overall_score:.1f}分），可继续完善")
        elif report.overall_score >= 60:
            recommendations.append(f"整体质量合格（{report.overall_score:.1f}分），建议针对低分维度改进")
        else:
            recommendations.append(f"⚠ 整体质量不达标（{report.overall_score:.1f}分），需大幅修改")
        return recommendations

    # ===== 历史与统计 =====

    def get_history(self, thesis_id: Optional[str] = None,
                    limit: int = 10) -> list[ValidationReport]:
        """获取验证历史。"""
        with self._lock:
            if thesis_id:
                reports = [r for r in self._history if r.thesis_id == thesis_id]
            else:
                reports = list(self._history)
            return reports[-limit:]

    def compare_reports(self, report_id1: str, report_id2: str) -> dict[str, Any]:
        """对比两份验证报告。"""
        with self._lock:
            r1 = next((r for r in self._history if r.id == report_id1), None)
            r2 = next((r for r in self._history if r.id == report_id2), None)
            if r1 is None or r2 is None:
                return {"error": "报告不存在"}
            return {
                "report1": {
                    "id": r1.id,
                    "timestamp": r1.timestamp,
                    "overall_score": r1.overall_score,
                    "issue_counts": {
                        "critical": r1.critical_count,
                        "error": r1.error_count,
                        "warning": r1.warning_count,
                        "info": r1.info_count,
                    },
                },
                "report2": {
                    "id": r2.id,
                    "timestamp": r2.timestamp,
                    "overall_score": r2.overall_score,
                    "issue_counts": {
                        "critical": r2.critical_count,
                        "error": r2.error_count,
                        "warning": r2.warning_count,
                        "info": r2.info_count,
                    },
                },
                "score_change": r2.overall_score - r1.overall_score,
                "issue_change": {
                    "critical": r2.critical_count - r1.critical_count,
                    "error": r2.error_count - r1.error_count,
                    "warning": r2.warning_count - r1.warning_count,
                    "info": r2.info_count - r1.info_count,
                },
                "improved": r2.overall_score > r1.overall_score,
            }

    def stats(self) -> dict[str, Any]:
        """返回验证器统计信息。"""
        with self._lock:
            if not self._history:
                return {
                    "total_validations": 0,
                    "avg_score": 0.0,
                    "pass_rate": 0.0,
                }
            total = len(self._history)
            avg_score = sum(r.overall_score for r in self._history) / total
            passed = sum(1 for r in self._history if r.passed)
            return {
                "total_validations": total,
                "avg_score": round(avg_score, 2),
                "pass_rate": round(passed / total, 4),
                "total_issues": sum(len(r.all_issues) for r in self._history),
                "custom_rules": len(self._custom_rules),
                "dimensions": list(self._validators.keys()),
            }


# ===== 模块级单例 =====


_global_instance: Optional[ThesisValidator] = None
_global_lock = threading.Lock()


def get_thesis_validator() -> ThesisValidator:
    """获取全局论题验证器单例。"""
    global _global_instance
    if _global_instance is None:
        with _global_lock:
            if _global_instance is None:
                _global_instance = ThesisValidator()
    return _global_instance


def reset_thesis_validator() -> None:
    """重置全局单例（主要用于测试）。"""
    global _global_instance
    with _global_lock:
        _global_instance = None
