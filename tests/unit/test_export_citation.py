"""CitationFormatter 单元测试模块

本测试模块覆盖 backend.export.citation_formatter 的全部功能，包括：
    - 枚举：CitationStyle / ReferenceType / SortKey
    - 异常：CitationError / ParseError / ValidationError
    - 数据结构：Author / Reference / ValidationResult / FormatStats
    - 辅助函数：format_authors_* / format_pages_*
    - 格式化器：GBT7714Formatter / APAFormatter / MLAFormatter / ChicagoFormatter / IEEEFormatter
    - 解析器：CitationParser（自动识别 + 各格式解析）
    - 校验器：CitationValidator（必填字段、DOI/URL/年份/页码校验）
    - 主类：CitationFormatter 单例（格式化、批量、排序、去重、解析、校验、统计、导出）
    - BibTeX 导出、Markdown/HTML 导出、格式转换
    - 模块级便捷函数
    - 线程安全与集成场景

所有注释使用中文编写。
"""
from __future__ import annotations

import threading
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from backend.export.citation_formatter import (
    APAFormatter,
    Author,
    ChicagoFormatter,
    CitationError,
    CitationFormatter,
    CitationParser,
    CitationStyle,
    CitationValidator,
    FormatStats,
    GBT7714Formatter,
    IEEEFormatter,
    MLAFormatter,
    ParseError,
    Reference,
    ReferenceType,
    SortKey,
    ValidationError,
    ValidationResult,
    deduplicate_references,
    format_authors_apa,
    format_authors_chicago,
    format_authors_gbt,
    format_authors_ieee,
    format_authors_mla,
    format_in_text_citation,
    format_pages_apa,
    format_pages_chicago,
    format_pages_gbt,
    format_pages_ieee,
    format_pages_mla,
    format_reference,
    format_references_batch,
    get_citation_formatter,
    parse_citation,
    sort_references,
    validate_reference,
)


# ===== 测试夹具 =====


@pytest.fixture(autouse=True)
def reset_formatter():
    """每个测试前后重置 CitationFormatter 单例状态。"""
    formatter = CitationFormatter()
    formatter.reset_numbering()
    yield
    formatter.reset_numbering()


@pytest.fixture
def chinese_journal_ref() -> Reference:
    """中文期刊论文参考文献。"""
    return Reference(
        type=ReferenceType.JOURNAL,
        authors=[Author(family="张", given="三"), Author(family="李", given="四")],
        title="深度学习在自然语言处理中的应用研究",
        year="2024",
        journal="计算机学报",
        volume="47",
        issue="3",
        pages="512-528",
        doi="10.3724/SP.J.1016.2024.00512",
    )


@pytest.fixture
def english_journal_ref() -> Reference:
    """英文期刊论文参考文献。"""
    return Reference(
        type=ReferenceType.JOURNAL,
        authors=[
            Author(family="Smith", given="John", middle="A."),
            Author(family="Jones", given="Mary", middle="B."),
        ],
        title="A Survey of Deep Learning Techniques",
        year="2023",
        journal="IEEE Transactions on Neural Networks",
        volume="34",
        issue="5",
        pages="2345-2367",
        doi="10.1109/TNN.2023.1234567",
    )


@pytest.fixture
def book_ref() -> Reference:
    """图书参考文献。"""
    return Reference(
        type=ReferenceType.BOOK,
        authors=[Author(family="王", given="五")],
        title="机器学习导论",
        year="2022",
        publisher="清华大学出版社",
        city="北京",
        edition="第2版",
        isbn="978-7-302-12345-6",
    )


@pytest.fixture
def conference_ref() -> Reference:
    """会议论文参考文献。"""
    return Reference(
        type=ReferenceType.CONFERENCE,
        authors=[Author(family="Brown", given="David"), Author(family="Wilson", given="Sarah")],
        title="Attention Is All You Need",
        year="2017",
        conference_name="Advances in Neural Information Processing Systems",
        conference_location="Long Beach, CA, USA",
        pages="5998-6008",
    )


@pytest.fixture
def thesis_ref() -> Reference:
    """学位论文参考文献。"""
    return Reference(
        type=ReferenceType.THESIS,
        authors=[Author(family="赵", given="六")],
        title="基于深度学习的文本分类研究",
        year="2023",
        university="北京大学",
        degree="硕士",
    )


@pytest.fixture
def web_ref() -> Reference:
    """网页资源参考文献。"""
    return Reference(
        type=ReferenceType.WEB_PAGE,
        authors=[Author(family="OpenAI", is_corporate=True)],
        title="GPT-4 Technical Report",
        year="2024",
        url="https://openai.com/research/gpt-4",
        access_date="2024-06-15",
    )


@pytest.fixture
def all_refs(
    chinese_journal_ref,
    english_journal_ref,
    book_ref,
    conference_ref,
    thesis_ref,
    web_ref,
) -> List[Reference]:
    """所有类型的参考文献列表。"""
    return [
        chinese_journal_ref,
        english_journal_ref,
        book_ref,
        conference_ref,
        thesis_ref,
        web_ref,
    ]


# ===== 枚举测试 =====


class TestCitationStyle:
    """CitationStyle 枚举测试。"""

    def test_enum_values(self):
        """测试枚举值。"""
        assert CitationStyle.GB_T_7714.value == "gb_t_7714"
        assert CitationStyle.APA.value == "apa"
        assert CitationStyle.MLA.value == "mla"
        assert CitationStyle.CHICAGO.value == "chicago"
        assert CitationStyle.IEEE.value == "ieee"

    def test_enum_count(self):
        """测试枚举数量。"""
        assert len(list(CitationStyle)) == 5

    def test_enum_from_string(self):
        """测试从字符串创建枚举。"""
        assert CitationStyle("apa") == CitationStyle.APA
        assert CitationStyle("mla") == CitationStyle.MLA

    def test_enum_is_str(self):
        """测试枚举继承 str。"""
        assert isinstance(CitationStyle.APA, str)


class TestReferenceType:
    """ReferenceType 枚举测试。"""

    def test_enum_values(self):
        """测试枚举值。"""
        assert ReferenceType.JOURNAL.value == "journal"
        assert ReferenceType.CONFERENCE.value == "conference"
        assert ReferenceType.BOOK.value == "book"
        assert ReferenceType.BOOK_CHAPTER.value == "book_chapter"
        assert ReferenceType.THESIS.value == "thesis"
        assert ReferenceType.WEB_PAGE.value == "web_page"

    def test_enum_count(self):
        """测试枚举数量。"""
        assert len(list(ReferenceType)) == 14

    def test_all_types(self):
        """测试所有类型存在。"""
        expected_types = [
            "journal", "conference", "book", "book_chapter",
            "thesis", "dissertation", "web_page", "tech_report",
            "patent", "standard", "newspaper", "software",
            "dataset", "other",
        ]
        actual_values = [t.value for t in ReferenceType]
        for expected in expected_types:
            assert expected in actual_values


class TestSortKey:
    """SortKey 枚举测试。"""

    def test_enum_values(self):
        """测试枚举值。"""
        assert SortKey.AUTHOR.value == "author"
        assert SortKey.YEAR.value == "year"
        assert SortKey.TITLE.value == "title"
        assert SortKey.TYPE.value == "type"
        assert SortKey.DOI.value == "doi"

    def test_enum_count(self):
        """测试枚举数量。"""
        assert len(list(SortKey)) == 5


# ===== 异常测试 =====


class TestExceptions:
    """异常类测试。"""

    def test_citation_error(self):
        """测试 CitationError。"""
        with pytest.raises(CitationError):
            raise CitationError("测试错误")

    def test_parse_error_inherits(self):
        """测试 ParseError 继承 CitationError。"""
        assert issubclass(ParseError, CitationError)
        with pytest.raises(CitationError):
            raise ParseError("解析错误")

    def test_validation_error_inherits(self):
        """测试 ValidationError 继承 CitationError。"""
        assert issubclass(ValidationError, CitationError)
        with pytest.raises(CitationError):
            raise ValidationError("校验错误")


# ===== Author 数据结构测试 =====


class TestAuthor:
    """Author 数据结构测试。"""

    def test_default_values(self):
        """测试默认值。"""
        author = Author()
        assert author.family == ""
        assert author.given == ""
        assert author.middle == ""
        assert author.suffix == ""
        assert author.is_corporate is False

    def test_chinese_author(self):
        """测试中文作者。"""
        author = Author(family="张", given="三")
        assert author.is_chinese is True
        assert author.full_name == "张三"
        assert author.display_name == "张三"

    def test_english_author(self):
        """测试英文作者。"""
        author = Author(family="Smith", given="John", middle="A.")
        assert author.is_chinese is False
        assert author.full_name == "John A. Smith"
        assert author.display_name == "Smith, J. A."

    def test_corporate_author(self):
        """测试机构作者。"""
        author = Author(family="World Health Organization", is_corporate=True)
        assert author.is_corporate is True
        assert author.full_name == "World Health Organization"
        assert author.display_name == "World Health Organization"

    def test_english_author_no_middle(self):
        """测试无中间名的英文作者。"""
        author = Author(family="Brown", given="David")
        assert author.full_name == "David Brown"
        assert author.display_name == "Brown, D."

    def test_author_strip_whitespace(self):
        """测试去除首尾空白。"""
        author = Author(family="  张  ", given="  三  ")
        assert author.family == "张"
        assert author.given == "三"

    def test_to_dict(self):
        """测试转换为字典。"""
        author = Author(family="张", given="三", is_corporate=False)
        d = author.to_dict()
        assert d["family"] == "张"
        assert d["given"] == "三"
        assert d["is_corporate"] is False

    def test_from_dict(self):
        """测试从字典创建。"""
        data = {"family": "Smith", "given": "John", "middle": "A."}
        author = Author.from_dict(data)
        assert author.family == "Smith"
        assert author.given == "John"
        assert author.middle == "A."

    def test_parse_chinese_simple(self):
        """测试解析简单中文姓名。"""
        author = Author.parse("张三")
        assert author.family == "张"
        assert author.given == "三"
        assert author.is_chinese is True

    def test_parse_chinese_with_comma(self):
        """测试解析带逗号的中文姓名。"""
        author = Author.parse("张，三")
        assert author.family == "张"
        assert author.given == "三"

    def test_parse_english_last_first(self):
        """测试解析英文姓在前格式。"""
        author = Author.parse("Smith, John")
        assert author.family == "Smith"
        assert author.given == "John"

    def test_parse_english_first_last(self):
        """测试解析英文名在前格式。"""
        author = Author.parse("John Smith")
        assert author.family == "Smith"
        assert author.given == "John"

    def test_parse_english_with_middle(self):
        """测试解析带中间名的英文姓名。"""
        author = Author.parse("John M. Smith")
        assert author.family == "Smith"
        assert author.given == "John"
        assert "M." in author.middle

    def test_parse_empty(self):
        """测试解析空字符串。"""
        author = Author.parse("")
        assert author.family == ""
        assert author.given == ""

    def test_parse_single_token(self):
        """测试解析单个词（机构名）。"""
        author = Author.parse("OpenAI")
        assert author.is_corporate is True
        assert author.family == "OpenAI"


# ===== Reference 数据结构测试 =====


class TestReference:
    """Reference 数据结构测试。"""

    def test_default_values(self):
        """测试默认值。"""
        ref = Reference()
        assert ref.type == ReferenceType.JOURNAL
        assert ref.authors == []
        assert ref.title == ""
        assert ref.year == ""
        assert ref.language == "zh"

    def test_first_author(self, chinese_journal_ref):
        """测试第一作者属性。"""
        assert chinese_journal_ref.first_author is not None
        assert chinese_journal_ref.first_author.family == "张"

    def test_first_author_none(self):
        """测试无作者时第一作者为 None。"""
        ref = Reference(title="测试")
        assert ref.first_author is None

    def test_author_count(self, chinese_journal_ref):
        """测试作者数量。"""
        assert chinese_journal_ref.author_count == 2

    def test_has_doi(self, chinese_journal_ref):
        """测试是否有 DOI。"""
        assert chinese_journal_ref.has_doi is True

    def test_has_doi_false(self):
        """测试无 DOI。"""
        ref = Reference(title="测试", doi="")
        assert ref.has_doi is False

    def test_has_url(self, web_ref):
        """测试是否有 URL。"""
        assert web_ref.has_url is True

    def test_has_url_false(self, chinese_journal_ref):
        """测试无 URL。"""
        assert chinese_journal_ref.has_url is False

    def test_is_online_resource_web(self, web_ref):
        """测试网页为在线资源。"""
        assert web_ref.is_online_resource is True

    def test_is_online_resource_journal(self, chinese_journal_ref):
        """测试期刊论文非在线资源。"""
        assert chinese_journal_ref.is_online_resource is False

    def test_type_label_cn(self, chinese_journal_ref, book_ref, web_ref):
        """测试中文类型标签。"""
        assert chinese_journal_ref.type_label_cn == "期刊论文"
        assert book_ref.type_label_cn == "图书专著"
        assert web_ref.type_label_cn == "网页资源"

    def test_gbt_type_code(self, chinese_journal_ref, book_ref, web_ref, thesis_ref):
        """测试 GB/T 7714 类型代码。"""
        assert chinese_journal_ref.gbt_type_code == "J"
        assert book_ref.gbt_type_code == "M"
        assert web_ref.gbt_type_code == "EB/OL"
        assert thesis_ref.gbt_type_code == "D"

    def test_fingerprint_with_doi(self, chinese_journal_ref):
        """测试带 DOI 的指纹。"""
        fp1 = chinese_journal_ref.fingerprint()
        # 同一 DOI 应产生相同指纹
        ref2 = Reference(
            title="不同标题",
            doi=chinese_journal_ref.doi,
        )
        fp2 = ref2.fingerprint()
        assert fp1 == fp2

    def test_fingerprint_without_doi(self, book_ref):
        """测试无 DOI 的指纹。"""
        fp1 = book_ref.fingerprint()
        ref2 = Reference(
            title=book_ref.title,
            authors=book_ref.authors,
            year=book_ref.year,
        )
        fp2 = ref2.fingerprint()
        assert fp1 == fp2

    def test_fingerprint_length(self, chinese_journal_ref):
        """测试指纹长度。"""
        fp = chinese_journal_ref.fingerprint()
        assert len(fp) == 16

    def test_year_string_conversion(self):
        """测试年份转换为字符串。"""
        ref = Reference(year=2024)
        assert ref.year == "2024"
        assert isinstance(ref.year, str)

    def test_to_dict(self, chinese_journal_ref):
        """测试转换为字典。"""
        d = chinese_journal_ref.to_dict()
        assert d["type"] == "journal"
        assert d["title"] == "深度学习在自然语言处理中的应用研究"
        assert d["year"] == "2024"
        assert len(d["authors"]) == 2

    def test_from_dict(self, chinese_journal_ref):
        """测试从字典创建。"""
        d = chinese_journal_ref.to_dict()
        ref = Reference.from_dict(d)
        assert ref.title == chinese_journal_ref.title
        assert ref.year == chinese_journal_ref.year
        assert len(ref.authors) == 2
        assert ref.authors[0].family == "张"

    def test_from_dict_with_string_authors(self):
        """测试从字典创建时处理字符串作者。"""
        data = {
            "title": "测试",
            "authors": ["张三", "李四"],
        }
        ref = Reference.from_dict(data)
        assert len(ref.authors) == 2
        assert ref.authors[0].family == "张"

    def test_from_dict_invalid_type(self):
        """测试从字典创建时处理无效类型。"""
        data = {"title": "测试", "type": "invalid_type"}
        ref = Reference.from_dict(data)
        assert ref.type == ReferenceType.OTHER


# ===== ValidationResult 与 FormatStats 测试 =====


class TestValidationResult:
    """ValidationResult 测试。"""

    def test_default_values(self):
        """测试默认值。"""
        result = ValidationResult()
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []
        assert result.missing_fields == []

    def test_add_error(self):
        """测试添加错误。"""
        result = ValidationResult()
        result.add_error("测试错误")
        assert result.is_valid is False
        assert "测试错误" in result.errors

    def test_add_warning(self):
        """测试添加警告。"""
        result = ValidationResult()
        result.add_warning("测试警告")
        assert result.is_valid is True
        assert "测试警告" in result.warnings

    def test_add_missing(self):
        """测试添加缺失字段。"""
        result = ValidationResult()
        result.add_missing("title")
        assert "title" in result.missing_fields

    def test_to_dict(self):
        """测试转换为字典。"""
        result = ValidationResult()
        result.add_error("错误1")
        result.add_warning("警告1")
        result.add_missing("title")
        d = result.to_dict()
        assert d["is_valid"] is False
        assert "错误1" in d["errors"]
        assert "警告1" in d["warnings"]
        assert "title" in d["missing_fields"]


class TestFormatStats:
    """FormatStats 测试。"""

    def test_default_values(self):
        """测试默认值。"""
        stats = FormatStats()
        assert stats.total == 0
        assert stats.by_type == {}
        assert stats.by_style == {}
        assert stats.duplicates == 0
        assert stats.invalid == 0
        assert stats.with_doi == 0
        assert stats.with_url == 0

    def test_to_dict(self):
        """测试转换为字典。"""
        stats = FormatStats(total=10, duplicates=2, with_doi=5)
        d = stats.to_dict()
        assert d["total"] == 10
        assert d["duplicates"] == 2
        assert d["with_doi"] == 5


# ===== 作者格式化辅助函数测试 =====


class TestFormatAuthorsGBT:
    """GB/T 7714 作者格式化测试。"""

    def test_empty_authors(self):
        """测试空作者列表。"""
        assert format_authors_gbt([]) == ""

    def test_single_author(self):
        """测试单个作者。"""
        authors = [Author(family="张", given="三")]
        result = format_authors_gbt(authors)
        assert "张三" in result

    def test_three_authors(self):
        """测试三个作者（全部列出）。"""
        authors = [
            Author(family="张", given="三"),
            Author(family="李", given="四"),
            Author(family="王", given="五"),
        ]
        result = format_authors_gbt(authors)
        assert "张三" in result
        assert "李四" in result
        assert "王五" in result
        assert "等" not in result

    def test_more_than_three_authors(self):
        """测试超过三个作者（加"等"）。"""
        authors = [
            Author(family="张", given="三"),
            Author(family="李", given="四"),
            Author(family="王", given="五"),
            Author(family="赵", given="六"),
        ]
        result = format_authors_gbt(authors)
        assert "张三" in result
        assert "等" in result
        assert "赵六" not in result

    def test_english_authors(self):
        """测试英文作者。"""
        authors = [Author(family="Smith", given="John")]
        result = format_authors_gbt(authors)
        assert "John Smith" in result


class TestFormatAuthorsAPA:
    """APA 作者格式化测试。"""

    def test_empty_authors(self):
        """测试空作者列表。"""
        assert format_authors_apa([]) == ""

    def test_single_author(self):
        """测试单个作者。"""
        authors = [Author(family="Smith", given="John", middle="A.")]
        result = format_authors_apa(authors)
        assert "Smith" in result

    def test_two_authors_with_ampersand(self):
        """测试两位作者用 & 连接。"""
        authors = [
            Author(family="Smith", given="John"),
            Author(family="Jones", given="Mary"),
        ]
        result = format_authors_apa(authors)
        assert "&" in result

    def test_chinese_author_apa(self):
        """测试中文作者 APA 格式。"""
        authors = [Author(family="张", given="三")]
        result = format_authors_apa(authors)
        assert "张三" in result

    def test_corporate_author(self):
        """测试机构作者。"""
        authors = [Author(family="World Health Organization", is_corporate=True)]
        result = format_authors_apa(authors)
        assert "World Health Organization" in result


class TestFormatAuthorsMLA:
    """MLA 作者格式化测试。"""

    def test_empty_authors(self):
        """测试空作者列表。"""
        assert format_authors_mla([]) == ""

    def test_single_author(self):
        """测试单个作者。"""
        authors = [Author(family="Smith", given="John")]
        result = format_authors_mla(authors)
        assert "Smith" in result

    def test_two_authors_with_and(self):
        """测试两位作者用 and 连接。"""
        authors = [
            Author(family="Smith", given="John"),
            Author(family="Brown", given="David"),
        ]
        result = format_authors_mla(authors)
        assert "and" in result

    def test_three_authors_et_al(self):
        """测试三位及以上作者用 et al.。"""
        authors = [
            Author(family="Smith", given="John"),
            Author(family="Brown", given="David"),
            Author(family="Wilson", given="Sarah"),
        ]
        result = format_authors_mla(authors)
        assert "et al." in result


class TestFormatAuthorsChicago:
    """Chicago 作者格式化测试。"""

    def test_empty_authors(self):
        """测试空作者列表。"""
        assert format_authors_chicago([]) == ""

    def test_single_author(self):
        """测试单个作者。"""
        authors = [Author(family="Smith", given="John")]
        result = format_authors_chicago(authors)
        assert "Smith" in result

    def test_two_authors(self):
        """测试两位作者。"""
        authors = [
            Author(family="Smith", given="John"),
            Author(family="Brown", given="David"),
        ]
        result = format_authors_chicago(authors)
        assert "and" in result

    def test_more_than_ten_authors(self):
        """测试超过十位作者。"""
        authors = [Author(family=f"Author{i}", given=f"First{i}") for i in range(11)]
        result = format_authors_chicago(authors)
        assert "et al." in result


class TestFormatAuthorsIEEE:
    """IEEE 作者格式化测试。"""

    def test_empty_authors(self):
        """测试空作者列表。"""
        assert format_authors_ieee([]) == ""

    def test_single_author(self):
        """测试单个作者。"""
        authors = [Author(family="Smith", given="John")]
        result = format_authors_ieee(authors)
        assert "Smith" in result

    def test_two_authors_with_and(self):
        """测试两位作者用 and 连接。"""
        authors = [
            Author(family="Smith", given="John"),
            Author(family="Brown", given="David"),
        ]
        result = format_authors_ieee(authors)
        assert "and" in result

    def test_more_than_six_authors(self):
        """测试超过六位作者用 et al.。"""
        authors = [Author(family=f"Author{i}", given=f"First{i}") for i in range(7)]
        result = format_authors_ieee(authors)
        assert "et al." in result

    def test_ieee_initials_format(self):
        """测试 IEEE 名缩写格式。"""
        authors = [Author(family="Smith", given="John", middle="A.")]
        result = format_authors_ieee(authors)
        assert "J." in result
        assert "A." in result


# ===== 页码格式化测试 =====


class TestFormatPages:
    """页码格式化函数测试。"""

    def test_format_pages_gbt(self):
        """测试 GB/T 7714 页码格式。"""
        assert format_pages_gbt("512-528") == "512-528"
        assert format_pages_gbt("512 – 528") == "512-528"
        assert format_pages_gbt("") == ""

    def test_format_pages_apa(self):
        """测试 APA 页码格式。"""
        assert format_pages_apa("512-528") == "512-528"
        assert format_pages_apa("512-512") == "512"
        assert format_pages_apa("") == ""

    def test_format_pages_mla(self):
        """测试 MLA 页码格式。"""
        assert format_pages_mla("512-528") == "512-28"
        assert format_pages_mla("") == ""

    def test_format_pages_chicago(self):
        """测试 Chicago 页码格式。"""
        assert format_pages_chicago("512-528") == "512-28"
        assert format_pages_chicago("") == ""

    def test_format_pages_ieee(self):
        """测试 IEEE 页码格式。"""
        result = format_pages_ieee("512-528")
        assert "pp." in result
        assert "512-528" in result
        result_single = format_pages_ieee("512-512")
        assert "p." in result_single
        assert format_pages_ieee("") == ""


# ===== GB/T 7714 格式化器测试 =====


class TestGBT7714Formatter:
    """GBT7714Formatter 测试。"""

    def test_format_journal(self, chinese_journal_ref):
        """测试期刊论文格式化。"""
        result = GBT7714Formatter.format_bibliography(chinese_journal_ref)
        assert "张三" in result
        assert "深度学习" in result
        assert "[J]" in result
        assert "计算机学报" in result
        assert "2024" in result
        assert "47(3)" in result
        assert "512-528" in result
        assert "DOI" in result

    def test_format_book(self, book_ref):
        """测试图书格式化。"""
        result = GBT7714Formatter.format_bibliography(book_ref)
        assert "王五" in result
        assert "机器学习导论" in result
        assert "[M]" in result
        assert "清华大学出版社" in result

    def test_format_conference(self, conference_ref):
        """测试会议论文格式化。"""
        result = GBT7714Formatter.format_bibliography(conference_ref)
        assert "Brown" in result
        assert "[C]" in result

    def test_format_thesis(self, thesis_ref):
        """测试学位论文格式化。"""
        result = GBT7714Formatter.format_bibliography(thesis_ref)
        assert "赵六" in result
        assert "[D]" in result
        assert "北京大学" in result

    def test_format_web_page(self, web_ref):
        """测试网页资源格式化。"""
        result = GBT7714Formatter.format_bibliography(web_ref)
        assert "GPT-4" in result
        assert "[EB/OL]" in result
        assert "https://openai.com" in result

    def test_format_in_text_sequential(self, chinese_journal_ref):
        """测试顺序编码制正文引用。"""
        result = GBT7714Formatter.format_in_text(chinese_journal_ref, mode="sequential")
        assert result == "[?]"

    def test_format_in_text_author_date(self, chinese_journal_ref):
        """测试著者-出版年制正文引用。"""
        result = GBT7714Formatter.format_in_text(chinese_journal_ref, mode="author_date")
        assert "张" in result
        assert "2024" in result

    def test_format_in_text_author_date_no_year(self):
        """测试无年份的著者-出版年制。"""
        ref = Reference(
            authors=[Author(family="Smith", given="John")],
            title="测试",
        )
        result = GBT7714Formatter.format_in_text(ref, mode="author_date")
        assert "Smith" in result

    def test_format_empty_ref(self):
        """测试空参考文献格式化。"""
        ref = Reference()
        result = GBT7714Formatter.format_bibliography(ref)
        assert result == ""


# ===== APA 格式化器测试 =====


class TestAPAFormatter:
    """APAFormatter 测试。"""

    def test_format_journal(self, english_journal_ref):
        """测试期刊论文格式化。"""
        result = APAFormatter.format_bibliography(english_journal_ref)
        assert "Smith" in result
        assert "(2023)" in result
        assert "IEEE Transactions" in result
        assert "https://doi.org/" in result

    def test_format_book(self, book_ref):
        """测试图书格式化。"""
        result = APAFormatter.format_bibliography(book_ref)
        assert "王五" in result
        assert "(2022)" in result
        assert "*" in result  # 书名斜体标记

    def test_format_no_year(self):
        """测试无年份格式化。"""
        ref = Reference(
            type=ReferenceType.JOURNAL,
            authors=[Author(family="Smith", given="John")],
            title="测试",
            journal="Journal",
        )
        result = APAFormatter.format_bibliography(ref)
        assert "n.d." in result

    def test_format_in_text_parenthetical(self, english_journal_ref):
        """测试括号引用。"""
        result = APAFormatter.format_in_text(english_journal_ref, mode="parenthetical")
        assert "Smith" in result
        assert "2023" in result
        assert result.startswith("(")

    def test_format_in_text_narrative(self, english_journal_ref):
        """测试叙述引用。"""
        result = APAFormatter.format_in_text(english_journal_ref, mode="narrative")
        assert "Smith" in result
        assert "(2023)" in result

    def test_format_in_text_two_authors(self):
        """测试两位作者正文引用。"""
        ref = Reference(
            authors=[
                Author(family="Smith", given="John"),
                Author(family="Jones", given="Mary"),
            ],
            year="2024",
        )
        result = APAFormatter.format_in_text(ref, mode="parenthetical")
        assert "&" in result

    def test_format_in_text_three_authors(self):
        """测试三位作者正文引用（et al.）。"""
        ref = Reference(
            authors=[
                Author(family="Smith", given="John"),
                Author(family="Jones", given="Mary"),
                Author(family="Brown", given="David"),
            ],
            year="2024",
        )
        result = APAFormatter.format_in_text(ref, mode="parenthetical")
        assert "et al." in result

    def test_format_in_text_no_authors(self):
        """测试无作者正文引用。"""
        ref = Reference(title="测试标题", year="2024")
        result = APAFormatter.format_in_text(ref, mode="parenthetical")
        assert "测试标题" in result


# ===== MLA 格式化器测试 =====


class TestMLAFormatter:
    """MLAFormatter 测试。"""

    def test_format_journal(self, english_journal_ref):
        """测试期刊论文格式化。"""
        result = MLAFormatter.format_bibliography(english_journal_ref)
        assert "Smith" in result
        assert '"A Survey' in result or '"A Survey of Deep Learning Techniques."' in result

    def test_format_book(self, book_ref):
        """测试图书格式化。"""
        result = MLAFormatter.format_bibliography(book_ref)
        assert "王五" in result
        assert "*机器学习导论.*" in result

    def test_format_in_text_single_author(self):
        """测试单作者正文引用。"""
        ref = Reference(
            authors=[Author(family="Smith", given="John")],
            pages="123-145",
        )
        result = MLAFormatter.format_in_text(ref)
        assert "Smith" in result

    def test_format_in_text_two_authors(self):
        """测试两作者正文引用。"""
        ref = Reference(
            authors=[
                Author(family="Smith", given="John"),
                Author(family="Jones", given="Mary"),
            ],
        )
        result = MLAFormatter.format_in_text(ref)
        assert "and" in result

    def test_format_in_text_three_authors(self):
        """测试三作者正文引用（et al.）。"""
        ref = Reference(
            authors=[
                Author(family="Smith", given="John"),
                Author(family="Jones", given="Mary"),
                Author(family="Brown", given="David"),
            ],
        )
        result = MLAFormatter.format_in_text(ref)
        assert "et al." in result

    def test_format_in_text_no_authors(self):
        """测试无作者正文引用。"""
        ref = Reference(title="测试标题: 副标题")
        result = MLAFormatter.format_in_text(ref)
        assert "测试标题" in result


# ===== Chicago 格式化器测试 =====


class TestChicagoFormatter:
    """ChicagoFormatter 测试。"""

    def test_format_journal(self, english_journal_ref):
        """测试期刊论文格式化。"""
        result = ChicagoFormatter.format_bibliography(english_journal_ref)
        assert "Smith" in result
        assert '"A Survey' in result

    def test_format_book(self, book_ref):
        """测试图书格式化。"""
        result = ChicagoFormatter.format_bibliography(book_ref)
        assert "王五" in result
        assert "*机器学习导论.*" in result

    def test_format_note(self, english_journal_ref):
        """测试脚注格式化。"""
        result = ChicagoFormatter.format_note(english_journal_ref, note_num=1)
        assert result.startswith("1.")

    def test_format_in_text(self, english_journal_ref):
        """测试正文引用。"""
        result = ChicagoFormatter.format_in_text(english_journal_ref)
        assert "Smith" in result
        assert "2023" in result

    def test_format_in_text_with_pages(self):
        """测试带页码的正文引用。"""
        ref = Reference(
            authors=[Author(family="Smith", given="John")],
            year="2024",
            pages="100-110",
        )
        result = ChicagoFormatter.format_in_text(ref)
        assert "100" in result

    def test_format_in_text_multiple_authors(self):
        """测试多作者正文引用。"""
        ref = Reference(
            authors=[
                Author(family="Smith", given="John"),
                Author(family="Jones", given="Mary"),
                Author(family="Brown", given="David"),
            ],
            year="2024",
        )
        result = ChicagoFormatter.format_in_text(ref)
        assert "and" in result


# ===== IEEE 格式化器测试 =====


class TestIEEEFormatter:
    """IEEEFormatter 测试。"""

    def test_format_journal(self, english_journal_ref):
        """测试期刊论文格式化。"""
        result = IEEEFormatter.format_bibliography(english_journal_ref, number=1)
        assert result.startswith("[1]")
        assert "Smith" in result
        assert "IEEE Transactions" in result
        assert "vol." in result

    def test_format_conference(self, conference_ref):
        """测试会议论文格式化。"""
        result = IEEEFormatter.format_bibliography(conference_ref, number=2)
        assert result.startswith("[2]")
        assert "Proc." in result or "Advances" in result

    def test_format_book(self, book_ref):
        """测试图书格式化。"""
        result = IEEEFormatter.format_bibliography(book_ref, number=3)
        assert result.startswith("[3]")

    def test_format_in_text(self, english_journal_ref):
        """测试正文引用。"""
        result = IEEEFormatter.format_in_text(english_journal_ref, number=1)
        assert result == "[1]"

    def test_format_in_text_with_pages(self):
        """测试带页码的正文引用。"""
        ref = Reference(pages="512-528")
        result = IEEEFormatter.format_in_text(ref, number=1)
        assert "[1" in result
        assert "p." in result

    def test_format_web_page(self, web_ref):
        """测试网页资源格式化。"""
        result = IEEEFormatter.format_bibliography(web_ref, number=5)
        assert "[5]" in result
        assert "[Online]" in result
        assert "https://openai.com" in result


# ===== CitationParser 测试 =====


class TestCitationParser:
    """CitationParser 测试。"""

    def test_parse_empty_raises(self):
        """测试解析空字符串抛出异常。"""
        with pytest.raises(ParseError):
            CitationParser.parse("")

    def test_parse_whitespace_raises(self):
        """测试解析空白字符串抛出异常。"""
        with pytest.raises(ParseError):
            CitationParser.parse("   ")

    def test_detect_style_ieee(self):
        """测试识别 IEEE 格式。"""
        raw = "[1] A. Smith, \"Title,\" Journal, 2024."
        assert CitationParser.detect_style(raw) == CitationStyle.IEEE

    def test_detect_style_gbt(self):
        """测试识别 GB/T 7714 格式。"""
        raw = "张三. 深度学习[J]. 计算机学报, 2024, 47(3): 512-528."
        assert CitationParser.detect_style(raw) == CitationStyle.GB_T_7714

    def test_detect_style_apa(self):
        """测试识别 APA 格式。"""
        raw = "Smith, J. (2024). Deep learning. Journal, 5(2), 1-10."
        assert CitationParser.detect_style(raw) == CitationStyle.APA

    def test_detect_style_mla(self):
        """测试识别 MLA 格式。"""
        raw = 'Smith, John. "Deep Learning." Journal, 2024.'
        assert CitationParser.detect_style(raw) == CitationStyle.MLA

    def test_detect_style_default_chicago(self):
        """测试默认识别为 Chicago 格式。"""
        raw = "Smith, John. Deep Learning. Publisher, 2024."
        assert CitationParser.detect_style(raw) == CitationStyle.CHICAGO

    def test_parse_extracts_doi(self):
        """测试解析提取 DOI。"""
        raw = "Smith, J. (2024). Title. Journal. 10.1109/TEST.2024.123"
        ref = CitationParser.parse(raw)
        assert "10.1109/TEST.2024.123" in ref.doi

    def test_parse_extracts_url(self):
        """测试解析提取 URL。"""
        raw = "Title. https://example.com/page"
        ref = CitationParser.parse(raw)
        assert "https://example.com/page" in ref.url

    def test_parse_extracts_year(self):
        """测试解析提取年份。"""
        raw = "Smith, J. (2024). Title. Journal."
        ref = CitationParser.parse(raw)
        assert ref.year == "2024"

    def test_parse_extracts_pages(self):
        """测试解析提取页码。"""
        raw = "Smith, J. Title. Journal, 512-528."
        ref = CitationParser.parse(raw)
        assert "512" in ref.pages
        assert "528" in ref.pages

    def test_parse_gbt_format(self):
        """测试解析 GB/T 7714 格式。"""
        raw = "张三, 李四. 深度学习[J]. 计算机学报, 2024, 47(3): 512-528."
        ref = CitationParser.parse(raw, CitationStyle.GB_T_7714)
        assert ref.type == ReferenceType.JOURNAL
        assert len(ref.authors) >= 1
        assert ref.year == "2024"

    def test_parse_ieee_format(self):
        """测试解析 IEEE 格式。"""
        raw = '[1] A. Smith, "Deep Learning," Journal, vol. 5, 2024.'
        ref = CitationParser.parse(raw, CitationStyle.IEEE)
        assert ref.title == "Deep Learning"
        assert len(ref.authors) >= 1

    def test_parse_apa_format(self):
        """测试解析 APA 格式。"""
        raw = "Smith, J. (2024). Deep learning techniques. Journal."
        ref = CitationParser.parse(raw, CitationStyle.APA)
        assert len(ref.authors) >= 1
        assert ref.year == "2024"

    def test_parse_with_explicit_style(self):
        """测试指定格式解析。"""
        raw = "张三. 深度学习[J]. 计算机学报, 2024."
        ref = CitationParser.parse(raw, CitationStyle.GB_T_7714)
        assert ref.type == ReferenceType.JOURNAL


# ===== CitationValidator 测试 =====


class TestCitationValidator:
    """CitationValidator 测试。"""

    def test_validate_valid_journal(self, chinese_journal_ref):
        """测试校验有效期刊论文。"""
        result = CitationValidator.validate(chinese_journal_ref)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_missing_required_field(self):
        """测试缺少必填字段。"""
        ref = Reference(type=ReferenceType.JOURNAL, title="测试")
        result = CitationValidator.validate(ref)
        assert result.is_valid is False
        assert "authors" in result.missing_fields
        assert "year" in result.missing_fields
        assert "journal" in result.missing_fields

    def test_validate_invalid_doi_format(self):
        """测试无效 DOI 格式。"""
        ref = Reference(
            type=ReferenceType.JOURNAL,
            authors=[Author(family="张", given="三")],
            title="测试",
            year="2024",
            journal="期刊",
            doi="invalid-doi",
        )
        result = CitationValidator.validate(ref)
        assert any("DOI" in w for w in result.warnings)

    def test_validate_invalid_url_format(self):
        """测试无效 URL 格式。"""
        ref = Reference(
            type=ReferenceType.WEB_PAGE,
            title="测试",
            url="not-a-url",
        )
        result = CitationValidator.validate(ref)
        assert any("URL" in w for w in result.warnings)

    def test_validate_invalid_year(self):
        """测试无效年份。"""
        ref = Reference(
            type=ReferenceType.JOURNAL,
            authors=[Author(family="张", given="三")],
            title="测试",
            year="abc",
            journal="期刊",
        )
        result = CitationValidator.validate(ref)
        assert any("年份" in w for w in result.warnings)

    def test_validate_year_out_of_range(self):
        """测试年份超出范围。"""
        ref = Reference(
            type=ReferenceType.JOURNAL,
            authors=[Author(family="张", given="三")],
            title="测试",
            year="1800",
            journal="期刊",
        )
        result = CitationValidator.validate(ref)
        assert any("年份" in w for w in result.warnings)

    def test_validate_web_page_without_access_date(self):
        """测试网页无访问日期。"""
        ref = Reference(
            type=ReferenceType.WEB_PAGE,
            title="测试",
            url="https://example.com",
        )
        result = CitationValidator.validate(ref)
        assert any("访问日期" in w for w in result.warnings)

    def test_validate_batch(self, all_refs):
        """测试批量校验。"""
        results = CitationValidator.validate_batch(all_refs)
        assert len(results) == len(all_refs)

    def test_validate_patent(self):
        """测试专利校验。"""
        ref = Reference(
            type=ReferenceType.PATENT,
            title="测试专利",
            patent_number="CN123456",
        )
        result = CitationValidator.validate(ref)
        assert result.is_valid is True

    def test_validate_standard(self):
        """测试标准校验。"""
        ref = Reference(
            type=ReferenceType.STANDARD,
            title="测试标准",
            standard_number="GB/T 7714-2015",
        )
        result = CitationValidator.validate(ref)
        assert result.is_valid is True


# ===== CitationFormatter 单例测试 =====


class TestCitationFormatterSingleton:
    """CitationFormatter 单例模式测试。"""

    def test_singleton_identity(self):
        """测试单例身份一致性。"""
        formatter1 = CitationFormatter()
        formatter2 = CitationFormatter()
        assert formatter1 is formatter2

    def test_get_citation_formatter(self):
        """测试 get_citation_formatter 函数。"""
        formatter1 = get_citation_formatter()
        formatter2 = get_citation_formatter()
        assert formatter1 is formatter2

    def test_reset_numbering(self):
        """测试重置编号。"""
        formatter = CitationFormatter()
        ref = Reference(title="测试", authors=[Author(family="张", given="三")])
        num1 = formatter.get_citation_number(ref)
        formatter.reset_numbering()
        num2 = formatter.get_citation_number(ref)
        assert num1 == num2  # 重置后重新编号

    def test_get_citation_number_consistent(self):
        """测试同一参考文献编号一致。"""
        formatter = CitationFormatter()
        ref = Reference(title="测试", authors=[Author(family="张", given="三")])
        num1 = formatter.get_citation_number(ref)
        num2 = formatter.get_citation_number(ref)
        assert num1 == num2

    def test_get_citation_number_increments(self):
        """测试不同参考文献编号递增。"""
        formatter = CitationFormatter()
        formatter.reset_numbering()
        ref1 = Reference(title="测试1", authors=[Author(family="张", given="三")])
        ref2 = Reference(title="测试2", authors=[Author(family="李", given="四")])
        num1 = formatter.get_citation_number(ref1)
        num2 = formatter.get_citation_number(ref2)
        assert num2 == num1 + 1


# ===== CitationFormatter 格式化测试 =====


class TestCitationFormatterFormat:
    """CitationFormatter 格式化方法测试。"""

    def test_format_bibliography_gbt(self, chinese_journal_ref):
        """测试 GB/T 7714 格式化。"""
        formatter = CitationFormatter()
        result = formatter.format_bibliography(chinese_journal_ref, CitationStyle.GB_T_7714)
        assert "张三" in result
        assert "[J]" in result

    def test_format_bibliography_apa(self, english_journal_ref):
        """测试 APA 格式化。"""
        formatter = CitationFormatter()
        result = formatter.format_bibliography(english_journal_ref, CitationStyle.APA)
        assert "Smith" in result
        assert "(2023)" in result

    def test_format_bibliography_mla(self, english_journal_ref):
        """测试 MLA 格式化。"""
        formatter = CitationFormatter()
        result = formatter.format_bibliography(english_journal_ref, CitationStyle.MLA)
        assert "Smith" in result

    def test_format_bibliography_chicago(self, english_journal_ref):
        """测试 Chicago 格式化。"""
        formatter = CitationFormatter()
        result = formatter.format_bibliography(english_journal_ref, CitationStyle.CHICAGO)
        assert "Smith" in result

    def test_format_bibliography_ieee(self, english_journal_ref):
        """测试 IEEE 格式化。"""
        formatter = CitationFormatter()
        formatter.reset_numbering()
        result = formatter.format_bibliography(english_journal_ref, CitationStyle.IEEE)
        assert result.startswith("[1]")
        assert "Smith" in result

    def test_format_bibliography_default_style(self, chinese_journal_ref):
        """测试默认格式（GB/T 7714）。"""
        formatter = CitationFormatter()
        result = formatter.format_bibliography(chinese_journal_ref)
        assert "[J]" in result

    def test_format_in_text_gbt(self, chinese_journal_ref):
        """测试 GB/T 7714 正文引用。"""
        formatter = CitationFormatter()
        result = formatter.format_in_text(chinese_journal_ref, CitationStyle.GB_T_7714)
        assert result == "[?]"

    def test_format_in_text_apa(self, english_journal_ref):
        """测试 APA 正文引用。"""
        formatter = CitationFormatter()
        result = formatter.format_in_text(english_journal_ref, CitationStyle.APA)
        assert "Smith" in result
        assert "2023" in result

    def test_format_in_text_ieee(self, english_journal_ref):
        """测试 IEEE 正文引用。"""
        formatter = CitationFormatter()
        formatter.reset_numbering()
        result = formatter.format_in_text(english_journal_ref, CitationStyle.IEEE)
        assert "[" in result and "]" in result

    def test_format_in_text_mla(self, english_journal_ref):
        """测试 MLA 正文引用。"""
        formatter = CitationFormatter()
        result = formatter.format_in_text(english_journal_ref, CitationStyle.MLA)
        assert "Smith" in result


# ===== 批量格式化测试 =====


class TestCitationFormatterBatch:
    """CitationFormatter 批量操作测试。"""

    def test_format_bibliography_batch(self, all_refs):
        """测试批量格式化。"""
        formatter = CitationFormatter()
        results = formatter.format_bibliography_batch(all_refs, CitationStyle.GB_T_7714)
        assert len(results) == len(all_refs)

    def test_format_bibliography_batch_with_sort(self, all_refs):
        """测试批量格式化带排序。"""
        formatter = CitationFormatter()
        results = formatter.format_bibliography_batch(
            all_refs, CitationStyle.GB_T_7714, sort=True
        )
        assert len(results) == len(all_refs)

    def test_format_bibliography_batch_with_deduplicate(self):
        """测试批量格式化带去重。"""
        formatter = CitationFormatter()
        ref1 = Reference(
            title="测试",
            authors=[Author(family="张", given="三")],
            year="2024",
            doi="10.1234/test",
        )
        ref2 = Reference(
            title="不同标题",
            doi="10.1234/test",  # 相同 DOI
        )
        results = formatter.format_bibliography_batch(
            [ref1, ref2], CitationStyle.GB_T_7714, deduplicate=True
        )
        assert len(results) == 1

    def test_format_in_text_batch(self, all_refs):
        """测试批量正文引用。"""
        formatter = CitationFormatter()
        results = formatter.format_in_text_batch(all_refs, CitationStyle.APA)
        assert len(results) == len(all_refs)

    def test_format_bibliography_batch_sort_by_year(self, all_refs):
        """测试按年份排序。"""
        formatter = CitationFormatter()
        results = formatter.format_bibliography_batch(
            all_refs, CitationStyle.GB_T_7714, sort=True, sort_key=SortKey.YEAR
        )
        assert len(results) == len(all_refs)

    def test_format_bibliography_batch_sort_by_title(self, all_refs):
        """测试按标题排序。"""
        formatter = CitationFormatter()
        results = formatter.format_bibliography_batch(
            all_refs, CitationStyle.GB_T_7714, sort=True, sort_key=SortKey.TITLE
        )
        assert len(results) == len(all_refs)


# ===== 排序与去重测试 =====


class TestSortAndDeduplicate:
    """排序与去重测试。"""

    def test_sort_by_author(self, all_refs):
        """测试按作者排序。"""
        formatter = CitationFormatter()
        sorted_refs = formatter.sort_references(all_refs, SortKey.AUTHOR)
        assert len(sorted_refs) == len(all_refs)
        # 验证已排序
        first_authors = [r.first_author.family.lower() if r.first_author else "zzz" for r in sorted_refs]
        assert first_authors == sorted(first_authors)

    def test_sort_by_year(self, all_refs):
        """测试按年份排序。"""
        formatter = CitationFormatter()
        sorted_refs = formatter.sort_references(all_refs, SortKey.YEAR)
        years = [r.year or "0000" for r in sorted_refs]
        assert years == sorted(years)

    def test_sort_by_title(self, all_refs):
        """测试按标题排序。"""
        formatter = CitationFormatter()
        sorted_refs = formatter.sort_references(all_refs, SortKey.TITLE)
        titles = [r.title.lower() for r in sorted_refs]
        assert titles == sorted(titles)

    def test_sort_reverse(self, all_refs):
        """测试降序排序。"""
        formatter = CitationFormatter()
        sorted_refs = formatter.sort_references(all_refs, SortKey.YEAR, reverse=True)
        years = [r.year or "0000" for r in sorted_refs]
        assert years == sorted(years, reverse=True)

    def test_deduplicate_by_doi(self):
        """测试按 DOI 去重。"""
        formatter = CitationFormatter()
        ref1 = Reference(title="测试1", doi="10.1234/test")
        ref2 = Reference(title="测试2", doi="10.1234/test")
        result = formatter.deduplicate([ref1, ref2])
        assert len(result) == 1

    def test_deduplicate_by_title_author(self):
        """测试按标题+作者去重。"""
        formatter = CitationFormatter()
        ref1 = Reference(
            title="相同标题",
            authors=[Author(family="张", given="三")],
            year="2024",
        )
        ref2 = Reference(
            title="相同标题",
            authors=[Author(family="张", given="三")],
            year="2024",
        )
        result = formatter.deduplicate([ref1, ref2])
        assert len(result) == 1

    def test_deduplicate_no_duplicates(self, all_refs):
        """测试无重复时不去重。"""
        formatter = CitationFormatter()
        result = formatter.deduplicate(all_refs)
        assert len(result) == len(all_refs)

    def test_deduplicate_empty_list(self):
        """测试空列表去重。"""
        formatter = CitationFormatter()
        result = formatter.deduplicate([])
        assert len(result) == 0


# ===== 解析与校验测试 =====


class TestCitationFormatterParseValidate:
    """CitationFormatter 解析与校验测试。"""

    def test_parse_auto_detect(self):
        """测试自动识别格式解析。"""
        formatter = CitationFormatter()
        raw = "张三. 深度学习[J]. 计算机学报, 2024, 47(3): 512-528."
        ref = formatter.parse(raw)
        assert ref.type == ReferenceType.JOURNAL
        assert ref.year == "2024"

    def test_parse_with_style(self):
        """测试指定格式解析。"""
        formatter = CitationFormatter()
        raw = "张三. 深度学习[J]. 计算机学报, 2024."
        ref = formatter.parse(raw, CitationStyle.GB_T_7714)
        assert ref.type == ReferenceType.JOURNAL

    def test_parse_empty_raises(self):
        """测试解析空字符串抛出异常。"""
        formatter = CitationFormatter()
        with pytest.raises(ParseError):
            formatter.parse("")

    def test_parse_batch(self):
        """测试批量解析。"""
        formatter = CitationFormatter()
        raws = [
            "张三. 深度学习[J]. 计算机学报, 2024.",
            "Smith, J. (2023). Deep learning. Journal.",
        ]
        refs = formatter.parse_batch(raws)
        assert len(refs) == 2

    def test_parse_batch_with_invalid(self):
        """测试批量解析含无效字符串。"""
        formatter = CitationFormatter()
        raws = [
            "张三. 深度学习[J]. 计算机学报, 2024.",
            "",  # 无效
        ]
        refs = formatter.parse_batch(raws)
        assert len(refs) == 1  # 无效的被跳过

    def test_validate_valid_ref(self, chinese_journal_ref):
        """测试校验有效参考文献。"""
        formatter = CitationFormatter()
        result = formatter.validate(chinese_journal_ref)
        assert result.is_valid is True

    def test_validate_invalid_ref(self):
        """测试校验无效参考文献。"""
        formatter = CitationFormatter()
        ref = Reference(type=ReferenceType.JOURNAL, title="测试")
        result = formatter.validate(ref)
        assert result.is_valid is False

    def test_validate_batch(self, all_refs):
        """测试批量校验。"""
        formatter = CitationFormatter()
        results = formatter.validate_batch(all_refs)
        assert len(results) == len(all_refs)


# ===== 统计与导出测试 =====


class TestStatsAndExport:
    """统计与导出测试。"""

    def test_get_stats(self, all_refs):
        """测试获取统计信息。"""
        formatter = CitationFormatter()
        stats = formatter.get_stats(all_refs, CitationStyle.GB_T_7714)
        assert stats.total == len(all_refs)
        assert "journal" in stats.by_type
        assert stats.with_doi > 0
        assert stats.with_url > 0

    def test_get_stats_no_style(self, all_refs):
        """测试无格式统计。"""
        formatter = CitationFormatter()
        stats = formatter.get_stats(all_refs)
        assert stats.total == len(all_refs)
        assert stats.by_style == {}

    def test_get_stats_duplicates(self):
        """测试统计重复数量。"""
        formatter = CitationFormatter()
        ref1 = Reference(title="测试", doi="10.1234/test")
        ref2 = Reference(title="不同", doi="10.1234/test")
        stats = formatter.get_stats([ref1, ref2])
        assert stats.duplicates == 1

    def test_format_bibliography_with_numbers(self, all_refs):
        """测试带编号的参考文献列表。"""
        formatter = CitationFormatter()
        result = formatter.format_bibliography_with_numbers(
            all_refs, CitationStyle.GB_T_7714
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_export_to_markdown(self, all_refs):
        """测试导出 Markdown。"""
        formatter = CitationFormatter()
        result = formatter.export_to_markdown(all_refs, CitationStyle.GB_T_7714)
        assert "## 参考文献" in result

    def test_export_to_html(self, all_refs):
        """测试导出 HTML。"""
        formatter = CitationFormatter()
        result = formatter.export_to_html(all_refs, CitationStyle.GB_T_7714)
        assert '<div class="references">' in result
        assert "<h2>参考文献</h2>" in result
        assert "<ol" in result

    def test_export_to_bibtex(self, chinese_journal_ref):
        """测试导出 BibTeX。"""
        formatter = CitationFormatter()
        result = formatter.export_to_bibtex(chinese_journal_ref)
        assert "@article{" in result
        assert "title =" in result
        assert "year =" in result
        assert "journal =" in result

    def test_export_to_bibtex_book(self, book_ref):
        """测试图书 BibTeX 导出。"""
        formatter = CitationFormatter()
        result = formatter.export_to_bibtex(book_ref)
        assert "@book{" in result

    def test_export_to_bibtex_batch(self, all_refs):
        """测试批量 BibTeX 导出。"""
        formatter = CitationFormatter()
        result = formatter.export_to_bibtex_batch(all_refs)
        entries = result.split("\n\n")
        assert len(entries) == len(all_refs)

    def test_export_to_markdown_empty(self):
        """测试空列表 Markdown 导出。"""
        formatter = CitationFormatter()
        result = formatter.export_to_markdown([], CitationStyle.GB_T_7714)
        assert "暂无" in result


# ===== 格式转换测试 =====


class TestStyleConversion:
    """格式转换测试。"""

    def test_convert_style(self, chinese_journal_ref):
        """测试单条格式转换。"""
        formatter = CitationFormatter()
        result = formatter.convert_style(
            chinese_journal_ref,
            CitationStyle.GB_T_7714,
            CitationStyle.APA,
        )
        assert "张三" in result or "Zhang" in result

    def test_convert_style_batch(self, all_refs):
        """测试批量格式转换。"""
        formatter = CitationFormatter()
        results = formatter.convert_style_batch(
            all_refs, CitationStyle.APA
        )
        assert len(results) == len(all_refs)

    def test_convert_style_batch_with_sort(self, all_refs):
        """测试批量格式转换带排序。"""
        formatter = CitationFormatter()
        results = formatter.convert_style_batch(
            all_refs, CitationStyle.MLA, sort=True
        )
        assert len(results) == len(all_refs)

    def test_convert_style_batch_with_deduplicate(self):
        """测试批量格式转换带去重。"""
        formatter = CitationFormatter()
        ref1 = Reference(title="测试", doi="10.1234/test")
        ref2 = Reference(title="不同", doi="10.1234/test")
        results = formatter.convert_style_batch(
            [ref1, ref2], CitationStyle.APA, deduplicate=True
        )
        assert len(results) == 1


# ===== 描述信息测试 =====


class TestDescriptions:
    """描述信息测试。"""

    def test_get_supported_styles(self):
        """测试获取支持的格式列表。"""
        formatter = CitationFormatter()
        styles = formatter.get_supported_styles()
        assert CitationStyle.GB_T_7714 in styles
        assert CitationStyle.APA in styles
        assert len(styles) == 5

    def test_get_supported_types(self):
        """测试获取支持的类型列表。"""
        formatter = CitationFormatter()
        types = formatter.get_supported_types()
        assert ReferenceType.JOURNAL in types
        assert len(types) == 14

    def test_get_style_description(self):
        """测试获取格式描述。"""
        formatter = CitationFormatter()
        desc = formatter.get_style_description(CitationStyle.GB_T_7714)
        assert "GB/T 7714" in desc
        assert "中国国家标准" in desc

    def test_get_style_description_apa(self):
        """测试 APA 格式描述。"""
        formatter = CitationFormatter()
        desc = formatter.get_style_description(CitationStyle.APA)
        assert "APA" in desc

    def test_get_type_description(self):
        """测试获取类型描述。"""
        formatter = CitationFormatter()
        desc = formatter.get_type_description(ReferenceType.JOURNAL)
        assert "期刊" in desc
        assert "[J]" in desc

    def test_get_type_description_thesis(self):
        """测试学位论文类型描述。"""
        formatter = CitationFormatter()
        desc = formatter.get_type_description(ReferenceType.THESIS)
        assert "硕士" in desc
        assert "[D]" in desc


# ===== 模块级函数测试 =====


class TestModuleLevelFunctions:
    """模块级便捷函数测试。"""

    def test_get_citation_formatter(self):
        """测试 get_citation_formatter 函数。"""
        formatter = get_citation_formatter()
        assert isinstance(formatter, CitationFormatter)

    def test_format_reference(self, chinese_journal_ref):
        """测试 format_reference 函数。"""
        result = format_reference(chinese_journal_ref, CitationStyle.GB_T_7714)
        assert "张三" in result
        assert "[J]" in result

    def test_format_in_text_citation(self, english_journal_ref):
        """测试 format_in_text_citation 函数。"""
        result = format_in_text_citation(english_journal_ref, CitationStyle.APA)
        assert "Smith" in result

    def test_format_references_batch(self, all_refs):
        """测试 format_references_batch 函数。"""
        results = format_references_batch(all_refs, CitationStyle.GB_T_7714)
        assert len(results) == len(all_refs)

    def test_parse_citation(self):
        """测试 parse_citation 函数。"""
        raw = "张三. 深度学习[J]. 计算机学报, 2024."
        ref = parse_citation(raw)
        assert ref.type == ReferenceType.JOURNAL

    def test_validate_reference(self, chinese_journal_ref):
        """测试 validate_reference 函数。"""
        result = validate_reference(chinese_journal_ref)
        assert result.is_valid is True

    def test_deduplicate_references(self):
        """测试 deduplicate_references 函数。"""
        ref1 = Reference(title="测试", doi="10.1234/test")
        ref2 = Reference(title="不同", doi="10.1234/test")
        result = deduplicate_references([ref1, ref2])
        assert len(result) == 1

    def test_sort_references(self, all_refs):
        """测试 sort_references 函数。"""
        result = sort_references(all_refs, SortKey.YEAR)
        assert len(result) == len(all_refs)


# ===== 集成场景测试 =====


class TestIntegrationScenarios:
    """集成场景测试。"""

    def test_full_pipeline_all_styles(self, all_refs):
        """测试所有格式的完整流水线。"""
        formatter = CitationFormatter()
        for style in CitationStyle:
            formatter.reset_numbering()
            results = formatter.format_bibliography_batch(all_refs, style)
            assert len(results) == len(all_refs)
            # 每条结果应为非空字符串
            for r in results:
                assert isinstance(r, str)

    def test_parse_then_format(self):
        """测试解析后重新格式化。"""
        formatter = CitationFormatter()
        raw = "张三. 深度学习[J]. 计算机学报, 2024, 47(3): 512-528."
        ref = formatter.parse(raw)
        result = formatter.format_bibliography(ref, CitationStyle.GB_T_7714)
        assert "深度学习" in result
        assert "[J]" in result

    def test_validate_then_export(self, all_refs):
        """测试校验后导出。"""
        formatter = CitationFormatter()
        # 校验
        results = formatter.validate_batch(all_refs)
        # 导出
        md = formatter.export_to_markdown(all_refs, CitationStyle.GB_T_7714)
        assert "## 参考文献" in md

    def test_deduplicate_sort_export(self):
        """测试去重排序后导出。"""
        formatter = CitationFormatter()
        ref1 = Reference(
            title="B 标题",
            authors=[Author(family="张", given="三")],
            year="2024",
            doi="10.1234/test1",
        )
        ref2 = Reference(
            title="A 标题",
            authors=[Author(family="李", given="四")],
            year="2023",
            doi="10.1234/test2",
        )
        ref3 = Reference(
            title="B 标题",  # 重复
            authors=[Author(family="张", given="三")],
            year="2024",
            doi="10.1234/test1",
        )
        refs = [ref1, ref2, ref3]
        md = formatter.export_to_markdown(refs, CitationStyle.GB_T_7714, sort=True, deduplicate=True)
        assert "## 参考文献" in md

    def test_bibtex_roundtrip(self, chinese_journal_ref):
        """测试 BibTeX 导出往返。"""
        formatter = CitationFormatter()
        bibtex = formatter.export_to_bibtex(chinese_journal_ref)
        assert "@article{" in bibtex
        assert "title = {深度学习在自然语言处理中的应用研究}" in bibtex
        assert "year = {2024}" in bibtex

    def test_all_types_formatting(self, all_refs):
        """测试所有文献类型的格式化。"""
        formatter = CitationFormatter()
        for ref in all_refs:
            for style in CitationStyle:
                formatter.reset_numbering()
                result = formatter.format_bibliography(ref, style)
                assert isinstance(result, str)
                assert len(result) > 0


# ===== 线程安全测试 =====


class TestThreadSafety:
    """线程安全测试。"""

    def test_concurrent_format_bibliography(self, all_refs):
        """测试并发格式化参考文献。"""
        formatter = CitationFormatter()
        errors = []
        results = []

        def worker():
            try:
                for ref in all_refs:
                    result = formatter.format_bibliography(ref, CitationStyle.GB_T_7714)
                    results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 5 * len(all_refs)

    def test_concurrent_citation_numbering(self):
        """测试并发引用编号。"""
        formatter = CitationFormatter()
        formatter.reset_numbering()
        errors = []
        numbers = []

        def worker():
            try:
                ref = Reference(
                    title="测试",
                    authors=[Author(family="张", given="三")],
                )
                num = formatter.get_citation_number(ref)
                numbers.append(num)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # 所有线程获取同一参考文献的编号应一致
        assert len(set(numbers)) == 1

    def test_concurrent_parse(self):
        """测试并发解析。"""
        formatter = CitationFormatter()
        raw = "张三. 深度学习[J]. 计算机学报, 2024, 47(3): 512-528."
        errors = []
        results = []

        def worker():
            try:
                ref = formatter.parse(raw)
                results.append(ref)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 5
        # 所有解析结果应一致
        assert all(r.title == results[0].title for r in results)

    def test_concurrent_deduplicate(self, all_refs):
        """测试并发去重。"""
        formatter = CitationFormatter()
        errors = []
        results = []

        def worker():
            try:
                result = formatter.deduplicate(all_refs)
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 3
        assert all(len(r) == len(results[0]) for r in results)
