# -*- coding: utf-8 -*-
"""
test_academic_standards.py - 学术规范模块单元测试

本测试文件覆盖 backend/constraints/academic_standards.py 中的所有组件：
- CitationFormat 枚举（GB_T_7714/APA/MLA/CHICAGO/IEEE/VANCOUVER）
- CitationIssue 数据类（field/message/severity/suggestion/position）
- ReferenceEntry 数据类（type/authors/title/year/journal/volume/issue/pages/publisher/city/doi/url）
- StandardsReport 数据类（passed/format/issues/reference_count/citation_count/consistency_score/recommendations）
- CitationFormatter 引用格式化器（format/_format_gbt7714/_format_apa/_format_mla/_format_chicago/_format_ieee/_format_vancouver）
- ReferenceChecker 参考文献检查器（check_entry/check_list/check_citation_reference_match）
- AcademicWritingChecker 学术写作检查器（check/check_structure）
- AcademicStandards 学术规范主类（format_reference/check_references/check_writing/check_all）
- FORMATTING_RULES 格式化规则（20 条）
- 全局函数（get_formatting_rules/get_academic_standards/check_academic_standards/format_reference）

作者：ThesisMiner 团队
版本：v8.0
"""

import pytest
from unittest.mock import MagicMock

from backend.constraints.academic_standards import (
    # 枚举
    CitationFormat,
    # 数据类
    CitationIssue,
    ReferenceEntry,
    StandardsReport,
    # 格式化器
    CitationFormatter,
    # 检查器
    ReferenceChecker,
    AcademicWritingChecker,
    # 主类
    AcademicStandards,
    # 规则
    FORMATTING_RULES,
    # 全局函数
    get_formatting_rules,
    get_academic_standards,
    check_academic_standards,
    format_reference as format_ref_func,
)


# ===== CitationFormat 枚举测试 =====


class TestCitationFormat:
    """测试 CitationFormat 枚举。"""

    def test_format_values(self):
        """测试引用格式值存在。"""
        assert CitationFormat.GB_T_7714
        assert CitationFormat.APA
        assert CitationFormat.MLA
        assert CitationFormat.CHICAGO
        assert CitationFormat.IEEE
        assert CitationFormat.VANCOUVER

    def test_format_count(self):
        """测试枚举成员数量。"""
        formats = list(CitationFormat)
        assert len(formats) == 6

    def test_specific_values(self):
        """测试特定枚举值。"""
        assert CitationFormat.GB_T_7714.value == "gb_t_7714"
        assert CitationFormat.APA.value == "apa"
        assert CitationFormat.MLA.value == "mla"
        assert CitationFormat.CHICAGO.value == "chicago"
        assert CitationFormat.IEEE.value == "ieee"
        assert CitationFormat.VANCOUVER.value == "vancouver"

    def test_format_inheritance(self):
        """测试枚举继承 str。"""
        assert isinstance(CitationFormat.APA, str)

    def test_format_lookup(self):
        """测试通过值查找枚举。"""
        assert CitationFormat("apa") == CitationFormat.APA
        assert CitationFormat("mla") == CitationFormat.MLA

    def test_format_uniqueness(self):
        """测试枚举值唯一性。"""
        values = [f.value for f in CitationFormat]
        assert len(values) == len(set(values))


# ===== CitationIssue 测试 =====


class TestCitationIssue:
    """测试 CitationIssue 数据类。"""

    def test_create(self):
        """测试创建引用问题。"""
        issue = CitationIssue(field="title", message="标题问题")
        assert issue.field == "title"
        assert issue.message == "标题问题"
        assert issue.severity == "warning"
        assert issue.suggestion == ""

    def test_create_with_all_fields(self):
        """测试带所有字段创建。"""
        issue = CitationIssue(
            field="year",
            message="年份格式错误",
            severity="error",
            suggestion="请使用4位数字",
            position=5,
        )
        assert issue.field == "year"
        assert issue.message == "年份格式错误"
        assert issue.severity == "error"
        assert issue.suggestion == "请使用4位数字"
        assert issue.position == 5

    def test_to_dict(self):
        """测试转换为字典。"""
        issue = CitationIssue(field="doi", message="DOI错误", severity="warning")
        d = issue.to_dict()
        assert d["field"] == "doi"
        assert d["message"] == "DOI错误"
        assert d["severity"] == "warning"
        assert "suggestion" in d
        assert "position" in d

    def test_severity_levels(self):
        """测试严重级别。"""
        for severity in ["info", "warning", "error"]:
            issue = CitationIssue(field="f", message="m", severity=severity)
            assert issue.severity == severity


# ===== ReferenceEntry 测试 =====


class TestReferenceEntry:
    """测试 ReferenceEntry 数据类。"""

    def test_create_default(self):
        """测试创建默认条目。"""
        entry = ReferenceEntry()
        assert entry.type == "journal"
        assert entry.authors == []
        assert entry.title == ""
        assert entry.year == ""

    def test_create_journal(self):
        """测试创建期刊条目。"""
        entry = ReferenceEntry(
            type="journal",
            authors=["张三", "李四"],
            title="深度学习研究",
            year="2024",
            journal="计算机学报",
            volume="30",
            issue="2",
            pages="100-110",
        )
        assert entry.type == "journal"
        assert len(entry.authors) == 2
        assert entry.title == "深度学习研究"
        assert entry.journal == "计算机学报"

    def test_create_book(self):
        """测试创建书籍条目。"""
        entry = ReferenceEntry(
            type="book",
            authors=["王五"],
            title="机器学习基础",
            year="2023",
            publisher="科学出版社",
            city="北京",
        )
        assert entry.type == "book"
        assert entry.publisher == "科学出版社"

    def test_create_web(self):
        """测试创建网页条目。"""
        entry = ReferenceEntry(
            type="web",
            title="在线资源",
            url="https://example.com",
            access_date="2024-01-01",
        )
        assert entry.type == "web"
        assert entry.url == "https://example.com"

    def test_to_dict(self):
        """测试转换为字典。"""
        entry = ReferenceEntry(
            type="journal",
            authors=["Author1"],
            title="Test Title",
            year="2024",
        )
        d = entry.to_dict()
        assert d["type"] == "journal"
        assert d["authors"] == ["Author1"]
        assert d["title"] == "Test Title"
        assert d["year"] == "2024"

    def test_to_dict_completeness(self):
        """测试字典包含所有字段。"""
        entry = ReferenceEntry()
        d = entry.to_dict()
        expected_keys = {
            "type", "authors", "title", "year", "journal", "volume",
            "issue", "pages", "publisher", "city", "doi", "url",
            "access_date", "raw",
        }
        assert set(d.keys()) == expected_keys

    def test_with_doi(self):
        """测试带 DOI 的条目。"""
        entry = ReferenceEntry(doi="10.1234/test")
        assert entry.doi == "10.1234/test"

    def test_all_types(self):
        """测试所有类型。"""
        for ref_type in ["journal", "book", "conference", "thesis", "web", "other"]:
            entry = ReferenceEntry(type=ref_type)
            assert entry.type == ref_type


# ===== StandardsReport 测试 =====


class TestStandardsReport:
    """测试 StandardsReport 数据类。"""

    def test_create(self):
        """测试创建报告。"""
        report = StandardsReport(passed=True)
        assert report.passed is True
        assert report.format == ""
        assert report.issues == []
        assert report.reference_count == 0

    def test_create_with_all_fields(self):
        """测试带所有字段创建。"""
        report = StandardsReport(
            passed=False,
            format="apa",
            issues=[CitationIssue(field="f", message="m")],
            reference_count=10,
            citation_count=8,
            consistency_score=0.7,
            recommendations=["建议1"],
        )
        assert report.passed is False
        assert report.format == "apa"
        assert report.reference_count == 10
        assert report.consistency_score == 0.7

    def test_to_dict(self):
        """测试转换为字典。"""
        report = StandardsReport(passed=True, format="mla")
        d = report.to_dict()
        assert d["passed"] is True
        assert d["format"] == "mla"

    def test_to_dict_with_issues(self):
        """测试带问题的字典转换。"""
        issue = CitationIssue(field="title", message="错误")
        report = StandardsReport(passed=False, issues=[issue])
        d = report.to_dict()
        assert len(d["issues"]) == 1
        assert d["issues"][0]["field"] == "title"

    def test_default_consistency_score(self):
        """测试默认一致性分数。"""
        report = StandardsReport(passed=True)
        assert report.consistency_score == 1.0


# ===== CitationFormatter 测试 =====


class TestCitationFormatter:
    """测试 CitationFormatter 类。"""

    def test_format_gbt7714_journal(self):
        """测试 GB/T 7714 期刊格式。"""
        entry = ReferenceEntry(
            type="journal",
            authors=["张三", "李四"],
            title="深度学习研究",
            year="2024",
            journal="计算机学报",
            volume="30",
            issue="2",
            pages="100-110",
        )
        result = CitationFormatter.format(entry, CitationFormat.GB_T_7714)
        assert isinstance(result, str)
        assert "深度学习研究" in result
        assert "2024" in result

    def test_format_gbt7714_book(self):
        """测试 GB/T 7714 书籍格式。"""
        entry = ReferenceEntry(
            type="book",
            authors=["王五"],
            title="机器学习基础",
            year="2023",
            publisher="科学出版社",
            city="北京",
        )
        result = CitationFormatter.format(entry, CitationFormat.GB_T_7714)
        assert "机器学习基础" in result
        assert "科学出版社" in result

    def test_format_apa(self):
        """测试 APA 格式。"""
        entry = ReferenceEntry(
            type="journal",
            authors=["Smith, J."],
            title="Deep Learning",
            year="2024",
            journal="Nature",
            volume="10",
            pages="1-20",
        )
        result = CitationFormatter.format(entry, CitationFormat.APA)
        assert isinstance(result, str)
        assert "Deep Learning" in result

    def test_format_mla(self):
        """测试 MLA 格式。"""
        entry = ReferenceEntry(
            type="journal",
            authors=["Smith, J."],
            title="Deep Learning",
            year="2024",
            journal="Nature",
        )
        result = CitationFormatter.format(entry, CitationFormat.MLA)
        assert isinstance(result, str)

    def test_format_chicago(self):
        """测试 Chicago 格式。"""
        entry = ReferenceEntry(
            type="book",
            authors=["Smith, J."],
            title="Deep Learning",
            year="2024",
            publisher="MIT Press",
            city="Cambridge",
        )
        result = CitationFormatter.format(entry, CitationFormat.CHICAGO)
        assert isinstance(result, str)

    def test_format_ieee(self):
        """测试 IEEE 格式。"""
        entry = ReferenceEntry(
            type="journal",
            authors=["J. Smith"],
            title="Deep Learning",
            year="2024",
            journal="IEEE Trans",
            volume="10",
        )
        result = CitationFormatter.format(entry, CitationFormat.IEEE)
        assert isinstance(result, str)

    def test_format_vancouver(self):
        """测试 Vancouver 格式。"""
        entry = ReferenceEntry(
            type="journal",
            authors=["Smith J"],
            title="Deep Learning",
            year="2024",
            journal="Nature",
            volume="10",
            pages="1-20",
        )
        result = CitationFormatter.format(entry, CitationFormat.VANCOUVER)
        assert isinstance(result, str)

    def test_format_default(self):
        """测试默认格式（GB/T 7714）。"""
        entry = ReferenceEntry(title="测试标题")
        result = CitationFormatter.format(entry)
        assert isinstance(result, str)

    def test_format_empty_entry(self):
        """测试空条目格式化。"""
        entry = ReferenceEntry()
        result = CitationFormatter.format(entry)
        assert isinstance(result, str)

    def test_format_authors_gbt(self):
        """测试 GB/T 7714 作者格式化。"""
        authors = ["张三", "李四", "王五"]
        result = CitationFormatter._format_authors(authors, "gbt")
        assert "张三" in result

    def test_format_authors_many(self):
        """测试多作者格式化（超过3人）。"""
        authors = ["作者1", "作者2", "作者3", "作者4", "作者5"]
        result = CitationFormatter._format_authors(authors, "gbt")
        assert "等" in result

    def test_format_authors_empty(self):
        """测试空作者列表。"""
        result = CitationFormatter._format_authors([], "gbt")
        assert "佚名" in result

    def test_format_authors_apa(self):
        """测试 APA 作者格式化。"""
        authors = ["Smith, J.", "Brown, K."]
        result = CitationFormatter._format_authors(authors, "apa")
        assert "Smith" in result

    def test_format_authors_mla(self):
        """测试 MLA 作者格式化。"""
        authors = ["Smith", "Brown", "Clark", "Davis"]
        result = CitationFormatter._format_authors(authors, "mla")
        assert "et al" in result or "Smith" in result

    def test_format_web_entry(self):
        """测试网页条目格式化。"""
        entry = ReferenceEntry(
            type="web",
            title="在线资源",
            url="https://example.com",
            access_date="2024-01-01",
        )
        result = CitationFormatter.format(entry, CitationFormat.GB_T_7714)
        assert isinstance(result, str)


# ===== ReferenceChecker 测试 =====


class TestReferenceChecker:
    """测试 ReferenceChecker 类。"""

    def test_create_checker(self):
        """测试创建检查器。"""
        checker = ReferenceChecker()
        assert checker is not None

    def test_required_fields(self):
        """测试必填字段配置。"""
        assert "journal" in ReferenceChecker.REQUIRED_FIELDS
        assert "book" in ReferenceChecker.REQUIRED_FIELDS
        assert "web" in ReferenceChecker.REQUIRED_FIELDS
        assert "authors" in ReferenceChecker.REQUIRED_FIELDS["journal"]
        assert "title" in ReferenceChecker.REQUIRED_FIELDS["journal"]

    def test_check_entry_valid(self):
        """测试检查有效条目。"""
        entry = ReferenceEntry(
            type="journal",
            authors=["张三"],
            title="测试标题",
            year="2024",
            journal="测试期刊",
        )
        issues = ReferenceChecker().check_entry(entry)
        # 有效条目应无错误级别问题
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) == 0

    def test_check_entry_missing_fields(self):
        """测试缺少必填字段。"""
        entry = ReferenceEntry(type="journal", title="只有标题")
        issues = ReferenceChecker().check_entry(entry)
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) > 0

    def test_check_entry_invalid_year(self):
        """测试无效年份格式。"""
        entry = ReferenceEntry(
            type="journal",
            authors=["作者"],
            title="标题",
            year="2024年",  # 非标准格式
            journal="期刊",
        )
        issues = ReferenceChecker().check_entry(entry)
        year_issues = [i for i in issues if i.field == "year"]
        assert len(year_issues) > 0

    def test_check_entry_invalid_doi(self):
        """测试无效 DOI 格式。"""
        entry = ReferenceEntry(
            type="journal",
            authors=["作者"],
            title="标题",
            year="2024",
            journal="期刊",
            doi="invalid_doi",
        )
        issues = ReferenceChecker().check_entry(entry)
        doi_issues = [i for i in issues if i.field == "doi"]
        assert len(doi_issues) > 0

    def test_check_entry_invalid_url(self):
        """测试无效 URL 格式。"""
        entry = ReferenceEntry(
            type="web",
            title="标题",
            url="not-a-url",
        )
        issues = ReferenceChecker().check_entry(entry)
        url_issues = [i for i in issues if i.field == "url"]
        assert len(url_issues) > 0

    def test_check_entry_empty_author(self):
        """测试空作者名。"""
        entry = ReferenceEntry(
            type="journal",
            authors=["", "有效作者"],
            title="标题",
            year="2024",
            journal="期刊",
        )
        issues = ReferenceChecker().check_entry(entry)
        author_issues = [i for i in issues if "authors" in i.field]
        assert len(author_issues) > 0

    def test_check_entry_long_title(self):
        """测试过长标题。"""
        entry = ReferenceEntry(
            type="journal",
            authors=["作者"],
            title="x" * 400,
            year="2024",
            journal="期刊",
        )
        issues = ReferenceChecker().check_entry(entry)
        title_issues = [i for i in issues if i.field == "title"]
        assert len(title_issues) > 0

    def test_check_list(self):
        """测试检查列表。"""
        entries = [
            ReferenceEntry(type="journal", authors=["A"], title="T1", year="2024", journal="J"),
            ReferenceEntry(type="journal", authors=["B"], title="T2", year="2023", journal="J"),
        ]
        issues = ReferenceChecker().check_list(entries)
        assert isinstance(issues, list)

    def test_check_list_unsorted(self):
        """测试未排序的列表。"""
        entries = [
            ReferenceEntry(type="journal", authors=["A"], title="T1", year="2024", journal="J"),
            ReferenceEntry(type="journal", authors=["B"], title="T2", year="2022", journal="J"),
            ReferenceEntry(type="journal", authors=["C"], title="T3", year="2023", journal="J"),
        ]
        issues = ReferenceChecker().check_list(entries)
        order_issues = [i for i in issues if i.field == "order"]
        assert len(order_issues) > 0

    def test_check_list_duplicates(self):
        """测试重复条目。"""
        entries = [
            ReferenceEntry(type="journal", authors=["A"], title="Same Title", year="2024", journal="J"),
            ReferenceEntry(type="journal", authors=["B"], title="Same Title", year="2023", journal="J"),
        ]
        issues = ReferenceChecker().check_list(entries)
        dup_issues = [i for i in issues if i.field == "duplicate"]
        assert len(dup_issues) > 0

    def test_check_citation_reference_match(self):
        """测试引用-参考文献匹配。"""
        text = "研究显示[1]该方法有效[2]"
        references = [
            ReferenceEntry(type="journal", title="Ref1", year="2024"),
            ReferenceEntry(type="journal", title="Ref2", year="2023"),
        ]
        result = ReferenceChecker().check_citation_reference_match(text, references)
        assert "matched" in result
        assert "unmatched_citations" in result
        assert "unreferenced" in result
        assert result["total_citations"] == 2
        assert result["total_references"] == 2

    def test_check_citation_unmatched(self):
        """测试未匹配的引用。"""
        text = "引用[1]和[5]"
        references = [ReferenceEntry(type="journal", title="Ref1", year="2024")]
        result = ReferenceChecker().check_citation_reference_match(text, references)
        assert len(result["unmatched_citations"]) > 0

    def test_check_unreferenced(self):
        """测试未被引用的参考文献。"""
        text = "只有引用[1]"
        references = [
            ReferenceEntry(type="journal", title="Ref1", year="2024"),
            ReferenceEntry(type="journal", title="Ref2", year="2023"),
            ReferenceEntry(type="journal", title="Ref3", year="2022"),
        ]
        result = ReferenceChecker().check_citation_reference_match(text, references)
        assert len(result["unreferenced"]) > 0


# ===== AcademicWritingChecker 测试 =====


class TestAcademicWritingChecker:
    """测试 AcademicWritingChecker 类。"""

    def test_create_checker(self):
        """测试创建检查器。"""
        checker = AcademicWritingChecker()
        assert checker is not None

    def test_colloquial_words(self):
        """测试口语化词汇列表。"""
        assert len(AcademicWritingChecker.COLLOQUIAL_WORDS) > 0
        assert "很" in AcademicWritingChecker.COLLOQUIAL_WORDS

    def test_first_person(self):
        """测试第一人称代词列表。"""
        assert len(AcademicWritingChecker.FIRST_PERSON) > 0
        assert "我" in AcademicWritingChecker.FIRST_PERSON

    def test_vague_expressions(self):
        """测试模糊表达列表。"""
        assert len(AcademicWritingChecker.VAGUE_EXPRESSIONS) > 0
        assert "一些" in AcademicWritingChecker.VAGUE_EXPRESSIONS

    def test_check_clean_text(self):
        """测试检查规范文本。"""
        checker = AcademicWritingChecker()
        text = "本研究采用实验方法验证假设。数据表明该方法有效。"
        issues = checker.check(text)
        # 规范文本应无或少问题
        assert isinstance(issues, list)

    def test_check_colloquial(self):
        """测试检查口语化文本。"""
        checker = AcademicWritingChecker()
        text = "这个东西很好，我觉得非常不错"
        issues = checker.check(text)
        assert len(issues) > 0

    def test_check_first_person(self):
        """测试检查第一人称。"""
        checker = AcademicWritingChecker()
        text = "我认为这个方法很好。我们发现结果显著。"
        issues = checker.check(text)
        assert len(issues) > 0

    def test_check_vague(self):
        """测试检查模糊表达。"""
        checker = AcademicWritingChecker()
        text = "一些研究表明可能存在某种效果"
        issues = checker.check(text)
        assert len(issues) > 0

    def test_check_structure(self):
        """测试检查文本结构。"""
        checker = AcademicWritingChecker()
        text = "这是一段学术文本。"
        issues = checker.check_structure(text)
        assert isinstance(issues, list)

    def test_check_empty_text(self):
        """测试检查空文本。"""
        checker = AcademicWritingChecker()
        issues = checker.check("")
        assert isinstance(issues, list)


# ===== AcademicStandards 测试 =====


class TestAcademicStandards:
    """测试 AcademicStandards 类。"""

    def test_create_standards(self):
        """测试创建学术规范实例。"""
        standards = AcademicStandards()
        assert standards.default_format == CitationFormat.GB_T_7714
        assert standards.formatter is not None
        assert standards.reference_checker is not None
        assert standards.writing_checker is not None

    def test_create_with_format(self):
        """测试指定格式创建。"""
        standards = AcademicStandards(default_format=CitationFormat.APA)
        assert standards.default_format == CitationFormat.APA

    def test_format_reference(self):
        """测试格式化参考文献。"""
        standards = AcademicStandards()
        entry = ReferenceEntry(
            type="journal",
            authors=["张三"],
            title="测试",
            year="2024",
            journal="期刊",
        )
        result = standards.format_reference(entry)
        assert isinstance(result, str)
        assert "测试" in result

    def test_format_reference_with_format(self):
        """测试指定格式格式化。"""
        standards = AcademicStandards()
        entry = ReferenceEntry(
            type="journal",
            authors=["Smith, J."],
            title="Test",
            year="2024",
            journal="Nature",
        )
        result = standards.format_reference(entry, CitationFormat.APA)
        assert isinstance(result, str)

    def test_format_references(self):
        """测试批量格式化。"""
        standards = AcademicStandards()
        entries = [
            ReferenceEntry(type="journal", authors=["A"], title="T1", year="2024", journal="J"),
            ReferenceEntry(type="journal", authors=["B"], title="T2", year="2023", journal="J"),
        ]
        results = standards.format_references(entries)
        assert len(results) == 2
        assert all(isinstance(r, str) for r in results)

    def test_check_reference(self):
        """测试检查单个参考文献。"""
        standards = AcademicStandards()
        entry = ReferenceEntry(type="journal", title="标题")
        issues = standards.check_reference(entry)
        assert isinstance(issues, list)

    def test_check_references(self):
        """测试检查参考文献列表。"""
        standards = AcademicStandards()
        entries = [
            ReferenceEntry(type="journal", authors=["A"], title="T1", year="2024", journal="J"),
            ReferenceEntry(type="journal", title="T2"),  # 缺少字段
        ]
        issues = standards.check_references(entries)
        assert isinstance(issues, list)

    def test_check_writing(self):
        """测试检查写作规范。"""
        standards = AcademicStandards()
        text = "本研究采用实验方法。"
        issues = standards.check_writing(text)
        assert isinstance(issues, list)

    def test_check_structure(self):
        """测试检查文本结构。"""
        standards = AcademicStandards()
        text = "这是一段文本。"
        issues = standards.check_structure(text)
        assert isinstance(issues, list)

    def test_check_all(self):
        """测试全面检查。"""
        standards = AcademicStandards()
        text = "本研究采用实验方法验证假设[1]。"
        references = [
            ReferenceEntry(type="journal", authors=["A"], title="Ref1", year="2024", journal="J"),
        ]
        report = standards.check_all(text, references)
        assert isinstance(report, StandardsReport)
        assert report.format == "gb_t_7714"
        assert report.reference_count == 1

    def test_check_all_no_references(self):
        """测试无参考文献的全面检查。"""
        standards = AcademicStandards()
        report = standards.check_all("学术文本内容")
        assert isinstance(report, StandardsReport)
        assert report.reference_count == 0

    def test_check_all_with_format(self):
        """测试指定格式的全面检查。"""
        standards = AcademicStandards()
        report = standards.check_all("文本", fmt=CitationFormat.APA)
        assert report.format == "apa"

    def test_check_all_passed(self):
        """测试通过的检查。"""
        standards = AcademicStandards()
        text = "本研究采用实验方法验证假设。数据表明该方法有效。"
        report = standards.check_all(text)
        assert isinstance(report, dict) or isinstance(report, StandardsReport)

    def test_check_all_with_issues(self):
        """测试有问题的检查。"""
        standards = AcademicStandards()
        text = "这个东西很好，我觉得非常不错"
        report = standards.check_all(text)
        assert len(report.issues) > 0

    def test_consistency_score(self):
        """测试一致性分数。"""
        standards = AcademicStandards()
        report = standards.check_all("规范学术文本。")
        assert 0.0 <= report.consistency_score <= 1.0

    def test_recommendations(self):
        """测试建议生成。"""
        standards = AcademicStandards()
        report = standards.check_all("文本内容")
        assert isinstance(report.recommendations, list)


# ===== FORMATTING_RULES 测试 =====


class TestFormattingRules:
    """测试 FORMATTING_RULES 格式化规则。"""

    def test_rules_not_empty(self):
        """测试规则非空。"""
        assert len(FORMATTING_RULES) > 0

    def test_rules_count(self):
        """测试规则数量。"""
        assert len(FORMATTING_RULES) >= 20

    def test_all_rules_have_id(self):
        """测试所有规则有 ID。"""
        for rule in FORMATTING_RULES:
            assert "id" in rule
            assert rule["id"]

    def test_all_rules_have_name(self):
        """测试所有规则有名称。"""
        for rule in FORMATTING_RULES:
            assert "name" in rule

    def test_all_rules_have_description(self):
        """测试所有规则有描述。"""
        for rule in FORMATTING_RULES:
            assert "description" in rule

    def test_all_rules_have_severity(self):
        """测试所有规则有严重级别。"""
        for rule in FORMATTING_RULES:
            assert "severity" in rule

    def test_all_rules_have_category(self):
        """测试所有规则有类别。"""
        for rule in FORMATTING_RULES:
            assert "category" in rule

    def test_rule_ids_unique(self):
        """测试规则 ID 唯一。"""
        ids = [r["id"] for r in FORMATTING_RULES]
        assert len(ids) == len(set(ids))

    def test_categories(self):
        """测试规则类别。"""
        categories = set(r["category"] for r in FORMATTING_RULES)
        assert "structure" in categories or "reference" in categories

    def test_get_formatting_rules_function(self):
        """测试 get_formatting_rules 函数。"""
        rules = get_formatting_rules()
        assert isinstance(rules, list)
        assert len(rules) == len(FORMATTING_RULES)


# ===== 全局函数测试 =====


class TestGlobalFunctions:
    """测试全局函数。"""

    def test_get_academic_standards(self):
        """测试获取全局实例。"""
        standards = get_academic_standards()
        assert standards is not None
        assert isinstance(standards, AcademicStandards)

    def test_singleton(self):
        """测试单例。"""
        s1 = get_academic_standards()
        s2 = get_academic_standards()
        assert s1 is s2

    def test_check_academic_standards(self):
        """测试便捷检查函数。"""
        report = check_academic_standards("学术文本内容")
        assert isinstance(report, StandardsReport)

    def test_check_academic_standards_with_refs(self):
        """测试带参考文献的便捷检查。"""
        refs = [ReferenceEntry(type="journal", authors=["A"], title="T", year="2024", journal="J")]
        report = check_academic_standards("文本[1]", references=refs)
        assert isinstance(report, StandardsReport)

    def test_format_reference_function(self):
        """测试便捷格式化函数。"""
        entry = ReferenceEntry(
            type="journal",
            authors=["张三"],
            title="测试",
            year="2024",
            journal="期刊",
        )
        result = format_ref_func(entry)
        assert isinstance(result, str)

    def test_format_reference_with_format(self):
        """测试指定格式的便捷格式化。"""
        entry = ReferenceEntry(
            type="journal",
            authors=["Smith, J."],
            title="Test",
            year="2024",
            journal="Nature",
        )
        result = format_ref_func(entry, CitationFormat.APA)
        assert isinstance(result, str)


# ===== 集成测试 =====


class TestIntegration:
    """集成测试。"""

    def test_full_academic_check_workflow(self):
        """测试完整学术规范检查工作流。"""
        standards = AcademicStandards()
        text = "本研究采用实验方法验证假设[1]。数据表明该方法有效[2]。"
        references = [
            ReferenceEntry(
                type="journal",
                authors=["张三", "李四"],
                title="深度学习研究",
                year="2024",
                journal="计算机学报",
                volume="30",
                pages="100-110",
            ),
            ReferenceEntry(
                type="journal",
                authors=["王五"],
                title="机器学习应用",
                year="2023",
                journal="软件学报",
            ),
        ]
        report = standards.check_all(text, references)
        assert isinstance(report, StandardsReport)
        assert report.reference_count == 2
        assert report.citation_count >= 2

    def test_format_all_citation_styles(self):
        """测试所有引用格式。"""
        entry = ReferenceEntry(
            type="journal",
            authors=["Smith, J.", "Brown, K."],
            title="Deep Learning Applications",
            year="2024",
            journal="Nature",
            volume="10",
            issue="2",
            pages="100-120",
        )
        for fmt in CitationFormat:
            result = CitationFormatter.format(entry, fmt)
            assert isinstance(result, str)
            assert len(result) > 0

    def test_reference_validation_workflow(self):
        """测试参考文献验证工作流。"""
        checker = ReferenceChecker()
        entries = [
            ReferenceEntry(type="journal", authors=["A"], title="T1", year="2024", journal="J"),
            ReferenceEntry(type="journal", title="T2"),  # 缺少字段
            ReferenceEntry(type="web", title="Web Ref", url="https://example.com"),
        ]
        issues = checker.check_list(entries)
        assert len(issues) > 0  # 应发现问题

    def test_writing_check_workflow(self):
        """测试写作检查工作流。"""
        checker = AcademicWritingChecker()
        # 不规范文本
        bad_text = "我觉得这个东西很好，非常不错。一些研究表明可能有效。"
        issues = checker.check(bad_text)
        assert len(issues) > 0

        # 规范文本
        good_text = "本研究采用定量分析方法。实验数据支持研究假设。"
        issues = checker.check(good_text)
        # 规范文本问题应更少
        assert isinstance(issues, list)

    def test_citation_match_workflow(self):
        """测试引用匹配工作流。"""
        checker = ReferenceChecker()
        text = "研究[1]表明该方法有效。另一研究[2]证实了结果。"
        references = [
            ReferenceEntry(type="journal", title="Ref1", year="2024"),
            ReferenceEntry(type="journal", title="Ref2", year="2023"),
        ]
        result = checker.check_citation_reference_match(text, references)
        assert len(result["matched"]) == 2
        assert len(result["unmatched_citations"]) == 0


# ===== 边界情况测试 =====


class TestEdgeCases:
    """边界情况测试。"""

    def test_empty_reference_entry(self):
        """测试空参考文献条目。"""
        entry = ReferenceEntry()
        issues = ReferenceChecker().check_entry(entry)
        assert len(issues) > 0  # 应有缺少字段错误

    def test_format_empty_entry(self):
        """测试格式化空条目。"""
        entry = ReferenceEntry()
        result = CitationFormatter.format(entry)
        assert isinstance(result, str)

    def test_check_empty_text(self):
        """测试检查空文本。"""
        issues = AcademicWritingChecker().check("")
        assert isinstance(issues, list)

    def test_check_all_empty(self):
        """测试空内容全面检查。"""
        report = AcademicStandards().check_all("")
        assert isinstance(report, StandardsReport)

    def test_many_authors(self):
        """测试多作者格式化。"""
        authors = [f"作者{i}" for i in range(10)]
        entry = ReferenceEntry(
            type="journal",
            authors=authors,
            title="测试",
            year="2024",
            journal="期刊",
        )
        result = CitationFormatter.format(entry, CitationFormat.GB_T_7714)
        assert "等" in result

    def test_single_author(self):
        """测试单作者格式化。"""
        entry = ReferenceEntry(
            type="journal",
            authors=["唯一作者"],
            title="测试",
            year="2024",
            journal="期刊",
        )
        result = CitationFormatter.format(entry, CitationFormat.GB_T_7714)
        assert "唯一作者" in result

    def test_no_authors(self):
        """测试无作者格式化。"""
        entry = ReferenceEntry(
            type="journal",
            authors=[],
            title="测试",
            year="2024",
            journal="期刊",
        )
        result = CitationFormatter.format(entry, CitationFormat.GB_T_7714)
        assert "佚名" in result

    def test_special_characters_in_title(self):
        """测试标题中的特殊字符。"""
        entry = ReferenceEntry(
            type="journal",
            authors=["作者"],
            title="标题含「特殊」字符",
            year="2024",
            journal="期刊",
        )
        result = CitationFormatter.format(entry)
        assert "特殊" in result

    def test_unicode_year(self):
        """测试 Unicode 年份。"""
        entry = ReferenceEntry(
            type="journal",
            authors=["作者"],
            title="标题",
            year="二零二四",
            journal="期刊",
        )
        issues = ReferenceChecker().check_entry(entry)
        year_issues = [i for i in issues if i.field == "year"]
        assert len(year_issues) > 0

    def test_long_reference_list(self):
        """测试长参考文献列表。"""
        entries = [
            ReferenceEntry(
                type="journal",
                authors=[f"作者{i}"],
                title=f"标题{i}",
                year=str(2020 + i),
                journal="期刊",
            )
            for i in range(50)
        ]
        issues = ReferenceChecker().check_list(entries)
        assert isinstance(issues, list)

    def test_mixed_reference_types(self):
        """测试混合类型参考文献。"""
        entries = [
            ReferenceEntry(type="journal", authors=["A"], title="J1", year="2024", journal="J"),
            ReferenceEntry(type="book", authors=["B"], title="B1", year="2023", publisher="P"),
            ReferenceEntry(type="web", title="W1", url="https://example.com"),
            ReferenceEntry(type="conference", authors=["C"], title="C1", year="2022"),
        ]
        issues = ReferenceChecker().check_list(entries)
        assert isinstance(issues, list)

    def test_consistency_score_range(self):
        """测试一致性分数范围。"""
        standards = AcademicStandards()
        report = standards.check_all("文本内容")
        assert 0.0 <= report.consistency_score <= 1.0

    def test_citation_count_extraction(self):
        """测试引用计数提取。"""
        standards = AcademicStandards()
        text = "引用[1]和[2]以及[3]"
        report = standards.check_all(text)
        assert report.citation_count >= 3
