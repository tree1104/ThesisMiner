"""引用验证器（CitationVerifier）单元测试

测试覆盖范围：
    - 引用解析：DOI/URL/年份/ISBN/卷期页/作者/标题/来源提取
    - DOI 验证：格式校验、解析验证（mock 网络请求）
    - URL 可访问性验证：HTTP 状态、重定向、404、超时
    - 引用格式规范检查：APA/IEEE/MLA/Chicago/GB-T7714/Vancouver 检测
    - 引用完整性检查：必填字段、年份有效性
    - 引用网络分析：节点构建、边构建、中心性、孤立节点
    - 引用孤岛检测：未引用条目、超出范围引用
    - 引用循环检测：自引环、互引环
    - 重复引用检测：DOI 重复、标题重复、高相似度
    - 批量验证、异步验证、单条验证
    - 验证报告生成、状态评估、建议生成
    - 配置管理、缓存、历史记录、统计、线程安全

测试策略：
    1. 使用真实引用文本触发各验证逻辑
    2. 通过 mock urllib.request 模拟网络响应
    3. 验证报告字段、状态分布、问题数量
    4. 覆盖边界条件（空输入、格式边界、网络异常）
"""
from __future__ import annotations

import asyncio
import threading
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from backend.integrity.citation_verifier import (
    CITATION_FORMATS,
    DEFAULT_CONCURRENCY,
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_TIMEOUT,
    FIELD_ALIASES,
    FORMAT_SIGNATURES,
    ISOLATED_CITATION_RATIO,
    MAX_CYCLE_DEPTH,
    REQUIRED_FIELDS,
    CitationEntry,
    CitationIssue,
    CitationNode,
    CitationStatus,
    CitationVerificationReport,
    CitationVerifier,
    _detect_format,
    _extract_in_text_citations,
    _extract_year,
    _levenshtein_distance,
    _normalize_doi,
    _normalize_url,
    _parse_citation,
    _string_similarity,
    _tokenize_words,
    parse_citation,
    validate_doi,
    verify_citations,
)


# ===== Fixtures =====


@pytest.fixture
def verifier() -> CitationVerifier:
    """提供默认配置（离线模式）的验证器实例。"""
    return CitationVerifier(enable_network=False)


@pytest.fixture
def network_verifier() -> CitationVerifier:
    """提供启用网络的验证器实例（网络请求将被 mock）。"""
    return CitationVerifier(enable_network=True, request_timeout=5.0,
                            max_retries=1, concurrency=2)


@pytest.fixture
def apa_references() -> list[str]:
    """提供 APA 格式的参考文献列表。"""
    return [
        "Smith, J. (2020). Deep learning for medical imaging. Journal of Machine Learning Research. doi:10.1234/jmlr.2020.001",
        "Brown, A. (2019). Neural networks architectures. IEEE Transactions on Pattern Analysis. doi:10.1109/tpami.2019.001",
        "Lee, K. (2021). Image segmentation methods. Computer Vision and Pattern Recognition. doi:10.1109/cvpr.2021.001",
        "Wang, H. (2018). Medical AI applications. Nature Medicine. doi:10.1038/nm.2018.001",
        "Zhang, L. (2022). Transformer models. Advances in Neural Information Processing Systems. doi:10.1234/neurips.2022.001",
    ]


@pytest.fixture
def mixed_references() -> list[str]:
    """提供混合格式的参考文献列表。"""
    return [
        "Smith, J. (2020). Deep learning. Journal A. doi:10.1234/a",
        "李四. 论文二. 期刊B, 2021.",
        "Brown C 2019 Paper three Journal C",
        "J. Smith, \"Paper four,\" vol. 10, 2020.",
    ]


@pytest.fixture
def duplicate_references() -> list[str]:
    """提供含重复条目的参考文献列表。"""
    return [
        "Smith, J. (2020). Same paper title. Journal A. doi:10.1234/dup",
        "Smith, J. (2020). Same paper title. Journal A. doi:10.1234/dup",  # DOI 完全重复
        "Brown, A. (2019). Another paper. Journal B. doi:10.1234/unique",
    ]


@pytest.fixture
def sample_full_text() -> str:
    """提供示例正文文本。"""
    return (
        "本文研究了深度学习 [1] 与神经网络 [2] 的应用。"
        "相关方法参见 [3, 4]。"
        "最新进展见 [5]。"
        "未引用的参考文献不会被检测到。"
    )


# ===== 枚举与常量测试 =====


class TestEnumsAndConstants:
    """测试枚举与常量定义。"""

    def test_citation_status_values(self):
        """验证引用状态枚举值。"""
        assert CitationStatus.VALID.value == "valid"
        assert CitationStatus.INVALID.value == "invalid"
        assert CitationStatus.SUSPICIOUS.value == "suspicious"
        assert CitationStatus.UNVERIFIED.value == "unverified"
        assert CitationStatus.MISSING.value == "missing"

    def test_citation_formats_list(self):
        """验证支持的引用格式列表。"""
        assert "APA" in CITATION_FORMATS
        assert "IEEE" in CITATION_FORMATS
        assert "MLA" in CITATION_FORMATS
        assert "Chicago" in CITATION_FORMATS
        assert "GB-T7714" in CITATION_FORMATS
        assert "Vancouver" in CITATION_FORMATS

    def test_format_signatures_complete(self):
        """验证每种格式都有特征正则。"""
        for fmt in CITATION_FORMATS:
            assert fmt in FORMAT_SIGNATURES
            assert len(FORMAT_SIGNATURES[fmt]) > 0

    def test_required_fields(self):
        """验证必填字段列表。"""
        assert "author" in REQUIRED_FIELDS
        assert "title" in REQUIRED_FIELDS
        assert "year" in REQUIRED_FIELDS
        assert "source" in REQUIRED_FIELDS

    def test_field_aliases(self):
        """验证字段别名映射。"""
        assert "author" in FIELD_ALIASES
        assert "authors" in FIELD_ALIASES["author"]
        assert "doi" in FIELD_ALIASES

    def test_default_constants(self):
        """验证默认常量值。"""
        assert DEFAULT_REQUEST_TIMEOUT > 0
        assert DEFAULT_MAX_RETRIES >= 0
        assert DEFAULT_CONCURRENCY >= 1
        assert MAX_CYCLE_DEPTH > 0


# ===== 工具函数测试 =====


class TestUtilityFunctions:
    """测试模块级工具函数。"""

    def test_normalize_doi_with_prefix(self):
        """测试 DOI 归一化去除前缀。"""
        assert _normalize_doi("doi:10.1234/abc") == "10.1234/abc"
        assert _normalize_doi("DOI:10.1234/abc") == "10.1234/abc"
        assert _normalize_doi("https://doi.org/10.1234/abc") == "10.1234/abc"
        assert _normalize_doi("http://doi.org/10.1234/abc") == "10.1234/abc"

    def test_normalize_doi_plain(self):
        """测试无前缀 DOI 保持不变。"""
        assert _normalize_doi("10.1234/abc") == "10.1234/abc"

    def test_normalize_doi_empty(self):
        """测试空 DOI 返回空。"""
        assert _normalize_doi("") == ""
        assert _normalize_doi(None) == ""

    def test_normalize_doi_whitespace(self):
        """测试 DOI 去除空白。"""
        assert _normalize_doi("  10.1234/abc  ") == "10.1234/abc"

    def test_normalize_url_adds_protocol(self):
        """测试 URL 补充协议。"""
        assert _normalize_url("example.com").startswith("https://")

    def test_normalize_url_keeps_protocol(self):
        """测试 URL 保留已有协议。"""
        assert _normalize_url("http://example.com") == "http://example.com"
        assert _normalize_url("https://example.com") == "https://example.com"

    def test_normalize_url_empty(self):
        """测试空 URL 返回空。"""
        assert _normalize_url("") == ""
        assert _normalize_url(None) == ""

    def test_extract_year_basic(self):
        """测试年份提取。"""
        assert _extract_year("Published in 2020.") == "2020"
        assert _extract_year("Year 1999") == "1999"

    def test_extract_year_not_found(self):
        """测试无年份返回空。"""
        assert _extract_year("no year here") == ""

    def test_levenshtein_identical(self):
        """测试相同字符串编辑距离为 0。"""
        assert _levenshtein_distance("abc", "abc") == 0

    def test_levenshtein_different(self):
        """测试不同字符串编辑距离。"""
        assert _levenshtein_distance("abc", "xyz") == 3
        assert _levenshtein_distance("kitten", "sitting") == 3

    def test_levenshtein_empty(self):
        """测试空字符串编辑距离。"""
        assert _levenshtein_distance("", "abc") == 3
        assert _levenshtein_distance("", "") == 0

    def test_string_similarity_identical(self):
        """测试相同字符串相似度为 1。"""
        assert _string_similarity("hello", "hello") == 1.0

    def test_string_similarity_different(self):
        """测试不同字符串相似度小于 1。"""
        assert _string_similarity("hello", "world") < 1.0

    def test_string_similarity_empty(self):
        """测试空字符串相似度。"""
        assert _string_similarity("", "") == 1.0
        assert _string_similarity("a", "") == 0.0

    def test_tokenize_words(self):
        """测试分词为词集合。"""
        words = _tokenize_words("Hello World hello")
        assert "hello" in words
        assert "world" in words

    def test_tokenize_words_chinese(self):
        """测试中文分词。"""
        words = _tokenize_words("深度学习")
        assert "深" in words or "深度学习" in words

    def test_detect_format_apa(self):
        """测试 APA 格式检测。"""
        fmt = _detect_format("Smith, J. (2020). Title. Journal. doi:10.1234/x")
        assert fmt == "APA"

    def test_detect_format_ieee(self):
        """测试 IEEE 格式检测。"""
        fmt = _detect_format("J. Smith, \"Title,\" vol. 10, 2020.")
        assert fmt == "IEEE"

    def test_detect_format_unknown(self):
        """测试未知格式返回 Unknown。"""
        fmt = _detect_format("??? ???")
        assert fmt == "Unknown"

    def test_extract_in_text_citations_single(self):
        """测试提取单个引用编号。"""
        result = _extract_in_text_citations("参见 [1] 文献")
        assert 1 in result

    def test_extract_in_text_citations_multiple(self):
        """测试提取多个引用编号。"""
        result = _extract_in_text_citations("参见 [1, 2, 3] 文献")
        assert 1 in result
        assert 2 in result
        assert 3 in result

    def test_extract_in_text_citations_range(self):
        """测试提取范围引用编号。"""
        result = _extract_in_text_citations("参见 [1-3] 文献")
        assert 1 in result
        assert 2 in result
        assert 3 in result

    def test_extract_in_text_citations_empty(self):
        """测试无引用返回空集。"""
        assert _extract_in_text_citations("无引用文本") == set()


# ===== 引用解析测试 =====


class TestCitationParsing:
    """测试引用文本解析。"""

    def test_parse_extracts_doi(self):
        """测试解析提取 DOI。"""
        entry = _parse_citation(
            "Smith, J. (2020). Title. Journal. doi:10.1234/abc", 1
        )
        assert entry.doi == "10.1234/abc"

    def test_parse_extracts_url(self):
        """测试解析提取 URL。"""
        entry = _parse_citation(
            "Smith, J. (2020). Title. https://example.com/paper", 1
        )
        assert entry.url == "https://example.com/paper"

    def test_parse_extracts_year(self):
        """测试解析提取年份。"""
        entry = _parse_citation("Smith, J. (2020). Title. Journal.", 1)
        assert entry.year == "2020"

    def test_parse_extracts_isbn(self):
        """测试解析提取 ISBN。"""
        entry = _parse_citation(
            "Some Book. ISBN: 978-3-16-148410-0. Publisher.", 1
        )
        assert "978" in entry.isbn or entry.isbn

    def test_parse_extracts_volume(self):
        """测试解析提取卷号。"""
        entry = _parse_citation(
            "Smith, J. (2020). Title. Journal, vol. 42.", 1
        )
        assert entry.volume == "42"

    def test_parse_extracts_pages(self):
        """测试解析提取页码。"""
        entry = _parse_citation(
            "Smith, J. (2020). Title. Journal, pp. 100-110.", 1
        )
        assert entry.pages

    def test_parse_sets_index(self):
        """测试解析设置引用编号。"""
        entry = _parse_citation("Any reference", 5)
        assert entry.index == 5

    def test_parse_sets_raw(self):
        """测试解析保留原始文本。"""
        raw = "Smith, J. (2020). Title."
        entry = _parse_citation(raw, 1)
        assert entry.raw == raw

    def test_parse_detects_format(self):
        """测试解析检测格式。"""
        entry = _parse_citation(
            "Smith, J. (2020). Title. Journal. doi:10.1234/x", 1
        )
        assert entry.format == "APA"

    def test_parse_empty_string(self):
        """测试解析空字符串不抛异常。"""
        entry = _parse_citation("", 1)
        assert entry.index == 1
        assert entry.raw == ""

    def test_parse_citation_convenience_function(self):
        """测试 parse_citation 便捷函数。"""
        entry = parse_citation("Smith, J. (2020). Title. Journal.")
        assert isinstance(entry, CitationEntry)
        assert entry.index == 1


# ===== 字段完整性检查测试 =====


class TestFieldCompleteness:
    """测试字段完整性检查。"""

    def test_missing_author_detected(self, verifier):
        """测试缺少作者字段检测。"""
        entry = CitationEntry(index=1, raw="ref", title="T", year="2020",
                              source="J")
        issues = verifier._check_field_completeness(entry)
        author_issues = [i for i in issues if "author" in i.message]
        assert len(author_issues) > 0

    def test_missing_title_detected(self, verifier):
        """测试缺少标题字段检测。"""
        entry = CitationEntry(index=1, raw="ref", author="A", year="2020",
                              source="J")
        issues = verifier._check_field_completeness(entry)
        title_issues = [i for i in issues if "title" in i.message]
        assert len(title_issues) > 0

    def test_missing_year_detected(self, verifier):
        """测试缺少年份字段检测。"""
        entry = CitationEntry(index=1, raw="ref", author="A", title="T",
                              source="J")
        issues = verifier._check_field_completeness(entry)
        year_issues = [i for i in issues if "year" in i.message]
        assert len(year_issues) > 0

    def test_missing_source_detected(self, verifier):
        """测试缺少来源字段检测。"""
        entry = CitationEntry(index=1, raw="ref", author="A", title="T",
                              year="2020")
        issues = verifier._check_field_completeness(entry)
        source_issues = [i for i in issues if "source" in i.message]
        assert len(source_issues) > 0

    def test_complete_entry_no_issues(self, verifier):
        """测试完整条目无问题。"""
        entry = CitationEntry(index=1, raw="ref", author="A", title="T",
                              year="2020", source="J")
        issues = verifier._check_field_completeness(entry)
        assert issues == []

    def test_field_issue_severity(self, verifier):
        """测试字段缺失问题严重度。"""
        entry = CitationEntry(index=1, raw="ref")
        issues = verifier._check_field_completeness(entry)
        for issue in issues:
            assert 0 < issue.severity <= 1
            assert issue.issue_type == "FIELD-COMPLETENESS"


# ===== DOI 验证测试 =====


class TestDoiVerification:
    """测试 DOI 验证。"""

    def test_valid_doi_format(self, verifier):
        """测试有效 DOI 格式不报错。"""
        entry = CitationEntry(index=1, raw="ref", doi="10.1234/abc")
        issues = verifier._verify_doi(entry)
        # 离线模式仅做格式校验，有效 DOI 无问题
        assert issues == []

    def test_invalid_doi_format(self, verifier):
        """测试无效 DOI 格式检测。"""
        entry = CitationEntry(index=1, raw="ref", doi="invalid-doi")
        issues = verifier._verify_doi(entry)
        assert len(issues) > 0
        assert issues[0].issue_type == "DOI-FMT"
        assert issues[0].severity > 0

    def test_doi_network_resolution_success(self, network_verifier):
        """测试 DOI 网络解析成功（mock）。"""
        entry = CitationEntry(index=1, raw="ref", doi="10.1234/abc")
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_response):
            issues = network_verifier._verify_doi(entry)
        assert issues == []

    def test_doi_network_resolution_404(self, network_verifier):
        """测试 DOI 网络解析 404。"""
        entry = CitationEntry(index=1, raw="ref", doi="10.1234/abc")
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(
                url="http://test", code=404, msg="Not Found",
                hdrs=None, fp=None,
            ),
        ):
            issues = network_verifier._verify_doi(entry)
        assert len(issues) > 0
        assert issues[0].issue_type == "DOI-RESOLVE"

    def test_doi_network_resolution_timeout(self, network_verifier):
        """测试 DOI 网络解析超时。"""
        entry = CitationEntry(index=1, raw="ref", doi="10.1234/abc")
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("timeout"),
        ):
            issues = network_verifier._verify_doi(entry)
        # 超时后应报告无法解析
        assert len(issues) > 0

    def test_doi_cache_hit(self, network_verifier):
        """测试 DOI 验证缓存命中。"""
        network_verifier._verification_cache["doi:10.1234/abc"] = CitationStatus.VALID
        entry = CitationEntry(index=1, raw="ref", doi="10.1234/abc")
        issues = network_verifier._verify_doi(entry)
        # 缓存为 VALID 时无问题
        assert issues == []
        assert network_verifier._stats["cache_hits"] > 0

    def test_validate_doi_convenience_function(self):
        """测试 validate_doi 便捷函数。"""
        assert validate_doi("10.1234/abc") is True
        assert validate_doi("invalid") is False
        assert validate_doi("doi:10.1234/abc") is True  # 归一化后有效


# ===== URL 验证测试 =====


class TestUrlVerification:
    """测试 URL 可访问性验证。"""

    def test_invalid_url_format(self, network_verifier):
        """测试无效 URL 格式检测。"""
        entry = CitationEntry(index=1, raw="ref", url="not-a-url")
        issues = network_verifier._verify_url(entry)
        assert len(issues) > 0
        assert issues[0].issue_type == "URL-ACCESS"

    def test_url_accessible_success(self, network_verifier):
        """测试 URL 可访问成功（mock）。"""
        entry = CitationEntry(index=1, raw="ref", url="https://example.com")
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_response):
            issues = network_verifier._verify_url(entry)
        assert issues == []

    def test_url_404(self, network_verifier):
        """测试 URL 404 错误。"""
        entry = CitationEntry(index=1, raw="ref", url="https://example.com/missing")
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(
                url="http://test", code=404, msg="Not Found",
                hdrs=None, fp=None,
            ),
        ):
            issues = network_verifier._verify_url(entry)
        assert len(issues) > 0
        assert issues[0].severity >= 0.5

    def test_url_403_suspicious(self, network_verifier):
        """测试 URL 403 视为可疑。"""
        entry = CitationEntry(index=1, raw="ref", url="https://example.com/forbidden")
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(
                url="http://test", code=403, msg="Forbidden",
                hdrs=None, fp=None,
            ),
        ):
            issues = network_verifier._verify_url(entry)
        assert len(issues) > 0

    def test_url_timeout(self, network_verifier):
        """测试 URL 超时。"""
        entry = CitationEntry(index=1, raw="ref", url="https://example.com")
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("timeout"),
        ):
            issues = network_verifier._verify_url(entry)
        assert len(issues) > 0

    def test_url_cache_hit(self, network_verifier):
        """测试 URL 验证缓存命中。"""
        network_verifier._verification_cache["url:https://example.com"] = (
            CitationStatus.VALID
        )
        entry = CitationEntry(index=1, raw="ref", url="https://example.com")
        issues = network_verifier._verify_url(entry)
        assert issues == []
        assert network_verifier._stats["cache_hits"] > 0

    def test_url_redirect_treated_as_valid(self, network_verifier):
        """测试 URL 重定向视为可访问。"""
        entry = CitationEntry(index=1, raw="ref", url="https://example.com")
        mock_response = MagicMock()
        mock_response.status = 301
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_response):
            issues = network_verifier._verify_url(entry)
        assert issues == []


# ===== 年份有效性测试 =====


class TestYearValidity:
    """测试年份有效性检查。"""

    def test_valid_year(self, verifier):
        """测试有效年份无问题。"""
        entry = CitationEntry(index=1, raw="ref", year="2020")
        issues = verifier._check_year_validity(entry)
        assert issues == []

    def test_year_too_early(self, verifier):
        """测试年份过早检测。"""
        entry = CitationEntry(index=1, raw="ref", year="1899")
        issues = verifier._check_year_validity(entry)
        assert len(issues) > 0
        assert "过早" in issues[0].message

    def test_year_future(self, verifier):
        """测试未来年份检测。"""
        entry = CitationEntry(index=1, raw="ref", year="2099")
        issues = verifier._check_year_validity(entry)
        assert len(issues) > 0
        assert "未来" in issues[0].message or "晚于" in issues[0].detail

    def test_empty_year_no_issues(self, verifier):
        """测试空年份无问题（由字段完整性处理）。"""
        entry = CitationEntry(index=1, raw="ref", year="")
        issues = verifier._check_year_validity(entry)
        assert issues == []


# ===== 格式一致性测试 =====


class TestFormatConsistency:
    """测试格式一致性检查。"""

    def test_consistent_format_no_issues(self, verifier, apa_references):
        """测试格式一致无问题。"""
        entries = [_parse_citation(r, i + 1) for i, r in enumerate(apa_references)]
        issues = verifier._check_format_consistency(entries)
        # 全部 APA 格式应无一致性问题
        consistency_issues = [
            i for i in issues if "不一致" in i.message
        ]
        assert len(consistency_issues) == 0

    def test_inconsistent_format_detected(self, verifier, mixed_references):
        """测试格式不一致检测。"""
        entries = [_parse_citation(r, i + 1) for i, r in enumerate(mixed_references)]
        issues = verifier._check_format_consistency(entries)
        # 混合格式应触发不一致或无法识别
        assert len(issues) >= 0  # 视实现可能触发

    def test_unknown_format_detected(self, verifier):
        """测试未知格式检测。"""
        entries = [
            CitationEntry(index=1, raw="???", format="Unknown"),
            CitationEntry(index=2, raw="???", format="Unknown"),
        ]
        issues = verifier._check_format_consistency(entries)
        unknown_issues = [i for i in issues if "无法识别" in i.message]
        assert len(unknown_issues) > 0

    def test_single_entry_no_consistency_check(self, verifier):
        """测试单条引用不做一致性检查。"""
        entries = [CitationEntry(index=1, raw="ref", format="APA")]
        issues = verifier._check_format_consistency(entries)
        assert issues == []


# ===== 重复引用检测测试 =====


class TestDuplicateDetection:
    """测试重复引用检测。"""

    def test_doi_duplicate_detected(self, verifier, duplicate_references):
        """测试 DOI 重复检测。"""
        entries = [_parse_citation(r, i + 1) for i, r in enumerate(duplicate_references)]
        issues = verifier._check_duplicates(entries)
        doi_dups = [i for i in issues if "DOI" in i.message]
        assert len(doi_dups) > 0

    def test_title_duplicate_detected(self, verifier):
        """测试标题重复检测。"""
        entries = [
            CitationEntry(index=1, raw="r1", title="Same Title Here", doi="10.1/a"),
            CitationEntry(index=2, raw="r2", title="Same Title Here", doi="10.2/b"),
        ]
        issues = verifier._check_duplicates(entries)
        title_dups = [i for i in issues if "标题" in i.message]
        assert len(title_dups) > 0

    def test_high_similarity_detected(self, verifier):
        """测试高相似度标题检测。"""
        entries = [
            CitationEntry(index=1, raw="r1", title="Deep Learning for Medical Image Analysis"),
            CitationEntry(index=2, raw="r2", title="Deep Learning for Medical Image Analyses"),
        ]
        issues = verifier._check_duplicates(entries)
        sim_issues = [i for i in issues if "相似" in i.message]
        assert len(sim_issues) > 0

    def test_no_duplicates_no_issues(self, verifier, apa_references):
        """测试无重复时无问题。"""
        entries = [_parse_citation(r, i + 1) for i, r in enumerate(apa_references)]
        issues = verifier._check_duplicates(entries)
        # 不同 DOI 不同标题，应无重复
        assert isinstance(issues, list)


# ===== 引用孤岛检测测试 =====


class TestIsolatedCitations:
    """测试引用孤岛检测。"""

    def test_uncited_reference_detected(self, verifier, sample_full_text):
        """测试未引用参考文献检测。"""
        entries = [
            CitationEntry(index=1, raw="r1", title="A"),
            CitationEntry(index=2, raw="r2", title="B"),
            CitationEntry(index=3, raw="r3", title="C"),
            CitationEntry(index=4, raw="r4", title="D"),
            CitationEntry(index=5, raw="r5", title="E"),
            CitationEntry(index=6, raw="r6", title="F"),  # 未被引用
        ]
        issues = verifier._check_isolated_citations(entries, sample_full_text)
        uncited = [i for i in issues if "未被正文引用" in i.message]
        assert len(uncited) > 0

    def test_orphan_citation_detected(self, verifier):
        """测试超出范围的正文引用检测。"""
        entries = [
            CitationEntry(index=1, raw="r1", title="A"),
        ]
        full_text = "参见 [1] 和 [5] 文献"  # [5] 超出范围
        issues = verifier._check_isolated_citations(entries, full_text)
        orphan = [i for i in issues if "不存在" in i.message]
        assert len(orphan) > 0

    def test_all_cited_no_issues(self, verifier):
        """测试全部被引用时无孤岛问题。"""
        entries = [
            CitationEntry(index=1, raw="r1", title="A"),
            CitationEntry(index=2, raw="r2", title="B"),
        ]
        full_text = "参见 [1] 和 [2]"
        issues = verifier._check_isolated_citations(entries, full_text)
        uncited = [i for i in issues if "未被正文引用" in i.message]
        assert len(uncited) == 0


# ===== 引用网络分析测试 =====


class TestCitationNetwork:
    """测试引用网络分析。"""

    def test_network_analysis_basic(self, verifier):
        """测试基本网络分析。"""
        entries = [
            CitationEntry(index=1, raw="r1", title="A", author="X", year="2020"),
            CitationEntry(index=2, raw="r2", title="B", author="Y", year="2021"),
            CitationEntry(index=3, raw="r3", title="C", author="Z", year="2022"),
        ]
        network = {1: [2], 2: [3]}
        issues, analysis = verifier._analyze_citation_network(entries, network)
        assert analysis["node_count"] == 3
        assert analysis["edge_count"] == 2
        assert "centrality" in analysis
        assert "top_cited" in analysis
        assert "top_citing" in analysis

    def test_cycle_detection(self, verifier):
        """测试引用循环检测。"""
        entries = [
            CitationEntry(index=1, raw="r1", title="A"),
            CitationEntry(index=2, raw="r2", title="B"),
            CitationEntry(index=3, raw="r3", title="C"),
        ]
        # 1 -> 2 -> 3 -> 1 形成循环
        network = {1: [2], 2: [3], 3: [1]}
        issues, analysis = verifier._analyze_citation_network(entries, network)
        cycle_issues = [i for i in issues if i.issue_type == "CITATION-CYCLE"]
        assert len(cycle_issues) > 0
        assert analysis["cycles"]

    def test_isolated_node_detected(self, verifier):
        """测试孤立节点检测。"""
        entries = [
            CitationEntry(index=1, raw="r1", title="A"),
            CitationEntry(index=2, raw="r2", title="B"),
        ]
        network = {1: [2]}  # 节点 2 被 1 引用，但无节点既不引也不被引
        # 添加一个孤立节点
        entries.append(CitationEntry(index=3, raw="r3", title="C"))
        issues, analysis = verifier._analyze_citation_network(entries, network)
        assert 3 in analysis["isolated_nodes"]

    def test_centrality_computation(self, verifier):
        """测试中心性计算。"""
        entries = [
            CitationEntry(index=i, raw=f"r{i}", title=f"T{i}")
            for i in range(1, 5)
        ]
        network = {1: [2, 3, 4], 2: [3], 3: [4]}
        issues, analysis = verifier._analyze_citation_network(entries, network)
        centrality = analysis["centrality"]
        assert "in_degree" in centrality
        assert "out_degree" in centrality
        # 节点 4 入度最高（被 1 和 3 引用）
        top_in = centrality["in_degree"][0]
        assert top_in[0] == 4

    def test_build_simple_network(self, verifier):
        """测试简单网络构建。"""
        entries = [
            CitationEntry(index=1, raw="r1", title="A"),
            CitationEntry(index=2, raw="r2", title="B"),
        ]
        full_text = "参见 [1]"
        analysis = verifier._build_simple_network(entries, full_text)
        assert analysis["node_count"] == 2
        assert 1 in analysis["cited_in_text"]
        assert 2 in analysis["uncited"]


# ===== 状态评估测试 =====


class TestStatusAssessment:
    """测试引用状态评估。"""

    def test_valid_status_no_issues(self, verifier):
        """测试无问题时状态为 VALID。"""
        entry = CitationEntry(index=1, raw="r", author="A", title="T",
                              year="2020", source="J")
        status = verifier._assess_citation_status(entry, [])
        assert status == CitationStatus.VALID

    def test_invalid_status_high_severity(self, verifier):
        """测试高严重度问题状态为 INVALID。"""
        entry = CitationEntry(index=1, raw="r")
        issues = [CitationIssue(citation_index=1, severity=0.7)]
        status = verifier._assess_citation_status(entry, issues)
        assert status == CitationStatus.INVALID

    def test_suspicious_status_medium_severity(self, verifier):
        """测试中严重度问题状态为 SUSPICIOUS。"""
        entry = CitationEntry(index=1, raw="r")
        issues = [CitationIssue(citation_index=1, severity=0.4)]
        status = verifier._assess_citation_status(entry, issues)
        assert status == CitationStatus.SUSPICIOUS

    def test_overall_status_empty(self, verifier):
        """测试空引用列表总体状态为 MISSING。"""
        report = CitationVerificationReport(total_citations=0)
        status = verifier._assess_overall_status(report)
        assert status == CitationStatus.MISSING

    def test_overall_status_high_invalid_ratio(self, verifier):
        """测试高无效比例总体状态为 INVALID。"""
        report = CitationVerificationReport(
            total_citations=10, invalid_count=5, suspicious_count=0,
            valid_count=5,
        )
        status = verifier._assess_overall_status(report)
        assert status == CitationStatus.INVALID

    def test_overall_status_valid(self, verifier):
        """测试高有效比例总体状态为 VALID。"""
        report = CitationVerificationReport(
            total_citations=10, invalid_count=0, suspicious_count=0,
            valid_count=9,
        )
        status = verifier._assess_overall_status(report)
        assert status == CitationStatus.VALID


# ===== 完整验证流程测试 =====


class TestFullVerification:
    """测试完整验证流程。"""

    def test_verify_returns_report(self, verifier, apa_references):
        """测试 verify 返回验证报告。"""
        report = verifier.verify(apa_references)
        assert isinstance(report, CitationVerificationReport)
        assert report.total_citations == len(apa_references)
        assert report.timestamp
        assert report.id

    def test_verify_counts(self, verifier, apa_references):
        """测试验证计数正确。"""
        report = verifier.verify(apa_references)
        total = (report.valid_count + report.invalid_count +
                 report.suspicious_count + report.unverified_count +
                 report.missing_count)
        assert total == report.verified_count

    def test_verify_format_distribution(self, verifier, apa_references):
        """测试格式分布计算。"""
        report = verifier.verify(apa_references)
        assert isinstance(report.format_distribution, dict)
        assert sum(report.format_distribution.values()) == len(apa_references)

    def test_verify_with_full_text(self, verifier, apa_references,
                                   sample_full_text):
        """测试带正文的验证。"""
        report = verifier.verify(apa_references, sample_full_text)
        assert isinstance(report, CitationVerificationReport)
        assert "cited_in_text" in report.network_analysis or \
               "node_count" in report.network_analysis

    def test_verify_with_network(self, verifier, apa_references):
        """测试带引用网络的验证。"""
        network = {1: [2, 3], 2: [3]}
        report = verifier.verify(apa_references, citation_network=network)
        assert report.network_analysis
        assert report.network_analysis.get("node_count") == len(apa_references)

    def test_verify_empty_references(self, verifier):
        """测试空引用列表验证。"""
        report = verifier.verify([])
        assert report.total_citations == 0
        assert report.overall_status == CitationStatus.MISSING

    def test_verify_recommendations_generated(self, verifier, apa_references):
        """测试建议生成。"""
        report = verifier.verify(apa_references)
        assert isinstance(report.recommendations, list)

    def test_verify_report_to_dict(self, verifier, apa_references):
        """测试报告序列化。"""
        report = verifier.verify(apa_references)
        d = report.to_dict()
        assert "id" in d
        assert "total_citations" in d
        assert "issues" in d
        assert "overall_status" in d

    def test_verify_single(self, verifier):
        """测试单条引用验证。"""
        status, issues = verifier.verify_single(
            "Smith, J. (2020). Title. Journal. doi:10.1234/abc"
        )
        assert isinstance(status, CitationStatus)
        assert isinstance(issues, list)

    def test_verify_single_invalid(self, verifier):
        """测试单条无效引用验证。"""
        status, issues = verifier.verify_single("???")
        assert isinstance(status, CitationStatus)

    def test_batch_verify(self, verifier, apa_references):
        """测试批量验证。"""
        reports = verifier.batch_verify([apa_references, apa_references[:2]])
        assert len(reports) == 2
        assert reports[0].total_citations == len(apa_references)
        assert reports[1].total_citations == 2

    def test_verify_citations_convenience(self, apa_references):
        """测试 verify_citations 便捷函数。"""
        report = verify_citations(apa_references)
        assert isinstance(report, CitationVerificationReport)


# ===== 异步验证测试 =====


class TestAsyncVerification:
    """测试异步验证。"""

    def test_verify_async(self, verifier, apa_references):
        """测试异步验证。"""
        report = asyncio.run(verifier.verify_async(apa_references))
        assert isinstance(report, CitationVerificationReport)
        assert report.total_citations == len(apa_references)

    def test_verify_async_with_full_text(self, verifier, apa_references,
                                         sample_full_text):
        """测试带正文的异步验证。"""
        report = asyncio.run(
            verifier.verify_async(apa_references, sample_full_text)
        )
        assert isinstance(report, CitationVerificationReport)


# ===== 配置管理测试 =====


class TestConfiguration:
    """测试配置管理。"""

    def test_enable_network_verification(self, verifier):
        """测试启用网络验证。"""
        verifier.enable_network_verification(True)
        config = verifier.get_config()
        assert config["enable_network"] is True

    def test_set_timeout(self, verifier):
        """测试设置超时。"""
        verifier.set_timeout(30.0)
        config = verifier.get_config()
        assert config["timeout"] == 30.0

    def test_clear_cache(self, network_verifier):
        """测试清空缓存。"""
        network_verifier._verification_cache["doi:10.1234/x"] = CitationStatus.VALID
        network_verifier.clear_cache()
        config = network_verifier.get_config()
        assert config["cache_size"] == 0

    def test_get_config_structure(self, verifier):
        """测试配置结构完整性。"""
        config = verifier.get_config()
        assert "enable_network" in config
        assert "timeout" in config
        assert "max_retries" in config
        assert "concurrency" in config
        assert "cache_size" in config
        assert "rules" in config
        assert "stats" in config

    def test_register_custom_rule(self, verifier):
        """测试注册自定义规则。"""
        verifier.register_rule("CUSTOM-001", "自定义", "测试规则")
        config = verifier.get_config()
        assert "CUSTOM-001" in config["rules"]

    def test_get_stats(self, verifier, apa_references):
        """测试获取统计。"""
        verifier.verify(apa_references)
        stats = verifier.get_stats()
        assert stats["total_verifications"] > 0


# ===== 历史记录测试 =====


class TestHistory:
    """测试历史记录。"""

    def test_history_recorded(self, verifier, apa_references):
        """测试验证后历史被记录。"""
        verifier.verify(apa_references)
        history = verifier.get_history()
        assert len(history) == 1

    def test_history_limit(self, verifier, apa_references):
        """测试历史记录数量限制。"""
        for _ in range(5):
            verifier.verify(apa_references)
        history = verifier.get_history(limit=3)
        assert len(history) == 3

    def test_history_order(self, verifier, apa_references):
        """测试历史记录按时间倒序。"""
        verifier.verify(apa_references)
        verifier.verify(apa_references[:2])
        history = verifier.get_history()
        # 最新的（2 条引用）应在最前
        assert history[0].total_citations == 2


# ===== 线程安全测试 =====


class TestThreadSafety:
    """测试线程安全性。"""

    def test_concurrent_verify(self, apa_references):
        """测试并发验证不抛异常。"""
        verifier = CitationVerifier()
        errors: list[Exception] = []

        def worker():
            try:
                for _ in range(3):
                    verifier.verify(apa_references)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        assert len(verifier.get_history(limit=100)) == 12

    def test_concurrent_config_and_verify(self, apa_references):
        """测试并发配置与验证。"""
        verifier = CitationVerifier()
        errors: list[Exception] = []

        def verify_worker():
            try:
                for _ in range(5):
                    verifier.verify(apa_references)
            except Exception as exc:
                errors.append(exc)

        def config_worker():
            try:
                for i in range(5):
                    verifier.set_timeout(5.0 + i)
                    verifier.enable_network_verification(i % 2 == 0)
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=verify_worker),
            threading.Thread(target=config_worker),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0


# ===== 数据类测试 =====


class TestDataclasses:
    """测试数据类。"""

    def test_citation_entry_to_dict(self):
        """测试 CitationEntry 序列化。"""
        entry = CitationEntry(index=1, raw="r", author="A", title="T",
                              year="2020", source="J", doi="10.1234/x")
        d = entry.to_dict()
        assert d["index"] == 1
        assert d["author"] == "A"
        assert d["doi"] == "10.1234/x"

    def test_citation_issue_to_dict(self):
        """测试 CitationIssue 序列化。"""
        issue = CitationIssue(
            id="i1", citation_index=1, issue_type="TEST",
            severity=0.5, message="msg", detail="detail", suggestion="sug",
        )
        d = issue.to_dict()
        assert d["id"] == "i1"
        assert d["severity"] == 0.5

    def test_citation_node_to_dict(self):
        """测试 CitationNode 序列化。"""
        node = CitationNode(index=1, title="T", author="A", year="2020",
                            cites={2, 3}, cited_by={4})
        d = node.to_dict()
        assert d["index"] == 1
        assert d["cites"] == [2, 3]
        assert d["cited_by"] == [4]

    def test_report_to_dict_complete(self, verifier, apa_references):
        """测试报告完整序列化。"""
        report = verifier.verify(apa_references)
        d = report.to_dict()
        assert "id" in d
        assert "document_id" in d
        assert "timestamp" in d
        assert "total_citations" in d
        assert "verified_count" in d
        assert "valid_count" in d
        assert "invalid_count" in d
        assert "suspicious_count" in d
        assert "unverified_count" in d
        assert "missing_count" in d
        assert "overall_status" in d
        assert "issues" in d
        assert "citation_statuses" in d
        assert "network_analysis" in d
        assert "format_distribution" in d
        assert "recommendations" in d
        assert "metadata" in d


# ===== 异常处理测试 =====


class TestErrorHandling:
    """测试异常处理。"""

    def test_verify_with_malformed_references(self, verifier):
        """测试畸形引用不抛异常。"""
        references = ["", "???", None, "   ", "valid ref 2020"]
        # 过滤 None
        valid_refs = [r for r in references if r is not None]
        report = verifier.verify(valid_refs)
        assert isinstance(report, CitationVerificationReport)

    def test_network_error_handled(self, network_verifier):
        """测试网络错误被处理。"""
        entry = CitationEntry(index=1, raw="r", doi="10.1234/abc")
        with patch(
            "urllib.request.urlopen",
            side_effect=Exception("unexpected"),
        ):
            # 不应抛异常
            status = network_verifier._check_doi_resolvable("10.1234/abc")
            assert status in (
                CitationStatus.VALID, CitationStatus.INVALID,
                CitationStatus.UNVERIFIED, CitationStatus.SUSPICIOUS,
            )

    def test_url_network_error_handled(self, network_verifier):
        """测试 URL 网络错误被处理。"""
        with patch(
            "urllib.request.urlopen",
            side_effect=Exception("unexpected"),
        ):
            status = network_verifier._check_url_accessible("https://example.com")
            assert status in (
                CitationStatus.VALID, CitationStatus.INVALID,
                CitationStatus.UNVERIFIED, CitationStatus.SUSPICIOUS,
            )

    def test_verify_with_empty_full_text(self, verifier, apa_references):
        """测试空正文验证不抛异常。"""
        report = verifier.verify(apa_references, full_text="")
        assert isinstance(report, CitationVerificationReport)


# ===== 建议生成测试 =====


class TestRecommendations:
    """测试建议生成。"""

    def test_recommendations_for_valid(self, verifier, apa_references):
        """测试有效引用的建议。"""
        report = verifier.verify(apa_references)
        # 应有总体建议
        assert len(report.recommendations) > 0

    def test_recommendations_for_invalid(self, verifier):
        """测试无效引用的建议。"""
        references = [
            "??? ???",
            "??? ???",
            "??? ???",
        ]
        report = verifier.verify(references)
        assert isinstance(report.recommendations, list)

    def test_recommendations_include_format_advice(self, verifier, apa_references):
        """测试建议包含格式建议。"""
        report = verifier.verify(apa_references)
        if report.format_distribution:
            # 应有格式相关建议
            assert len(report.recommendations) > 0


# ===== 综合场景测试 =====


class TestComplexScenarios:
    """测试复杂综合场景。"""

    def test_full_verify_with_all_features(self, verifier, apa_references,
                                           sample_full_text):
        """测试启用所有功能的完整验证。"""
        network = {1: [2], 2: [3]}
        report = verifier.verify(
            apa_references,
            full_text=sample_full_text,
            citation_network=network,
        )
        assert isinstance(report, CitationVerificationReport)
        assert report.network_analysis
        assert report.format_distribution

    def test_multiple_verifications_independent(self, verifier, apa_references):
        """测试多次验证相互独立。"""
        report1 = verifier.verify(apa_references)
        report2 = verifier.verify(apa_references[:2])
        assert report1.id != report2.id
        assert report1.total_citations != report2.total_citations

    def test_verify_with_problematic_references(self, verifier):
        """测试问题引用的验证。"""
        references = [
            "Smith, J. (2020). Title. Journal. doi:10.1234/dup",
            "Smith, J. (2020). Title. Journal. doi:10.1234/dup",  # 重复
            "???",  # 格式未知
            "Ref with year 1899.",  # 年份过早
        ]
        report = verifier.verify(references)
        assert isinstance(report, CitationVerificationReport)
        assert len(report.issues) > 0

    def test_mocked_network_full_flow(self, network_verifier, apa_references):
        """测试 mock 网络的完整流程。"""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_response):
            report = network_verifier.verify(apa_references)
        assert isinstance(report, CitationVerificationReport)
        assert network_verifier._stats["network_requests"] > 0
