"""citation_parser 模块单元测试

测试 backend/ai/citation_parser.py 的引用解析功能：
  - Citation 数据类
  - parse_citations 解析 URL / Markdown 链接 / 编号引用
  - extract_domain 域名提取
  - enrich_citation / enrich_citations 异步丰富引用信息
  - 优先级与去重逻辑
  - 边界条件（空字符串、无引用、重复 URL）
"""
import asyncio
import os
import sys
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ===== 项目根目录加入 sys.path =====
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ===== 临时数据库初始化 =====
_TMP_DIR = tempfile.mkdtemp(prefix="thesisminer_citation_test_")
import backend.database as _db
_db.DB_PATH = os.path.join(_TMP_DIR, "test.db")
_db.init_db()

from backend.ai.citation_parser import (
    Citation,
    URL_PATTERN,
    MARKDOWN_LINK_PATTERN,
    NUMBERED_CITATION_PATTERN,
    parse_citations,
    extract_domain,
    enrich_citation,
    enrich_citations,
)


# ===== Citation 数据类测试 =====


class TestCitationDataclass:
    """Citation 数据类测试"""

    def test_citation_default_values(self):
        """测试：Citation 默认值应为空字符串与 url 类型"""
        c = Citation(url="https://example.com")
        assert c.url == "https://example.com"
        assert c.title == ""
        assert c.snippet == ""
        assert c.source_domain == ""
        assert c.favicon == ""
        assert c.citation_type == "url"

    def test_citation_with_all_fields(self):
        """测试：Citation 可设置所有字段"""
        c = Citation(
            url="https://example.com/page",
            title="示例页面",
            snippet="这是示例摘要",
            source_domain="example.com",
            favicon="https://icon.example.com",
            citation_type="markdown",
        )
        assert c.url == "https://example.com/page"
        assert c.title == "示例页面"
        assert c.snippet == "这是示例摘要"
        assert c.source_domain == "example.com"
        assert c.favicon == "https://icon.example.com"
        assert c.citation_type == "markdown"

    def test_citation_is_mutable(self):
        """测试：Citation 实例字段可修改"""
        c = Citation(url="https://example.com")
        c.title = "新标题"
        c.snippet = "新摘要"
        assert c.title == "新标题"
        assert c.snippet == "新摘要"

    def test_citation_equality(self):
        """测试：相同字段的 Citation 实例相等"""
        c1 = Citation(url="https://a.com", title="A")
        c2 = Citation(url="https://a.com", title="A")
        assert c1 == c2


# ===== extract_domain 测试 =====


class TestExtractDomain:
    """extract_domain 函数测试"""

    def test_extract_domain_simple_url(self):
        """测试：简单 URL 的域名提取"""
        assert extract_domain("https://example.com/path") == "example.com"

    def test_extract_domain_with_www_prefix(self):
        """测试：带 www. 前缀的域名应去除 www."""
        assert extract_domain("https://www.example.com/page") == "example.com"

    def test_extract_domain_with_subdomain(self):
        """测试：带子域名的 URL"""
        # 注意：extract_domain 只去除 www.，其他子域名保留
        result = extract_domain("https://blog.example.com/post")
        assert "example.com" in result

    def test_extract_domain_http_protocol(self):
        """测试：http 协议的 URL"""
        assert extract_domain("http://example.com") == "example.com"

    def test_extract_domain_with_port(self):
        """测试：带端口号的 URL"""
        result = extract_domain("https://example.com:8080/path")
        assert "example.com" in result

    def test_extract_domain_with_query_params(self):
        """测试：带查询参数的 URL"""
        result = extract_domain("https://example.com/search?q=test&page=1")
        assert "example.com" in result

    def test_extract_domain_empty_string(self):
        """测试：空字符串应返回空字符串"""
        assert extract_domain("") == ""

    def test_extract_domain_invalid_url(self):
        """测试：无效 URL 应返回空字符串"""
        assert extract_domain("not-a-url") == ""

    def test_extract_domain_no_protocol(self):
        """测试：无协议的 URL"""
        result = extract_domain("example.com/path")
        # 无协议时 netloc 可能为空
        assert isinstance(result, str)

    def test_extract_domain_complex_url(self):
        """测试：复杂 URL 的域名提取"""
        url = "https://scholar.google.com/scholar?q=machine+learning&hl=zh-CN"
        result = extract_domain(url)
        assert "google.com" in result


# ===== parse_citations 测试 =====


class TestParseCitations:
    """parse_citations 函数测试"""

    def test_parse_empty_content(self):
        """测试：空内容应返回空列表"""
        assert parse_citations("") == []

    def test_parse_no_urls(self):
        """测试：无 URL 的内容应返回空列表"""
        content = "这是一段普通文本，没有任何链接。"
        assert parse_citations(content) == []

    def test_parse_single_bare_url(self):
        """测试：解析单个裸 URL"""
        content = "请参考 https://example.com/article 了解更多。"
        citations = parse_citations(content)
        assert len(citations) == 1
        assert citations[0].url == "https://example.com/article"
        assert citations[0].citation_type == "url"
        assert citations[0].source_domain == "example.com"

    def test_parse_multiple_bare_urls(self):
        """测试：解析多个裸 URL"""
        content = (
            "文献1: https://a.com/paper1\n"
            "文献2: https://b.com/paper2\n"
            "文献3: https://c.com/paper3"
        )
        citations = parse_citations(content)
        assert len(citations) == 3
        urls = [c.url for c in citations]
        assert "https://a.com/paper1" in urls
        assert "https://b.com/paper2" in urls
        assert "https://c.com/paper3" in urls

    def test_parse_markdown_link(self):
        """测试：解析 Markdown 链接 [text](url)"""
        content = "详见 [示例论文](https://example.com/paper) 获取详情。"
        citations = parse_citations(content)
        assert len(citations) == 1
        assert citations[0].url == "https://example.com/paper"
        assert citations[0].title == "示例论文"
        assert citations[0].citation_type == "markdown"

    def test_parse_numbered_citation(self):
        """测试：解析编号引用 [1] https://..."""
        content = "相关研究 [1] https://example.com/ref1 表明..."
        citations = parse_citations(content)
        assert len(citations) == 1
        assert citations[0].url == "https://example.com/ref1"
        assert citations[0].title == "引用 [1]"
        assert citations[0].citation_type == "numbered"

    def test_parse_mixed_citation_types(self):
        """测试：混合引用类型解析"""
        content = (
            "详见 [论文A](https://a.com/paper) 与 [1] https://b.com/ref "
            "以及 https://c.com/bare"
        )
        citations = parse_citations(content)
        assert len(citations) == 3
        types = [c.citation_type for c in citations]
        assert "markdown" in types
        assert "numbered" in types
        assert "url" in types

    def test_parse_deduplication_same_url(self):
        """测试：同一 URL 只保留首次出现的形式"""
        content = (
            "首次出现 [论文](https://example.com/dup) "
            "再次出现 https://example.com/dup"
        )
        citations = parse_citations(content)
        assert len(citations) == 1
        # Markdown 形式优先级更高，应保留 Markdown 形式
        assert citations[0].citation_type == "markdown"
        assert citations[0].title == "论文"

    def test_parse_markdown_priority_over_url(self):
        """测试：Markdown 链接优先于裸 URL"""
        content = "[标题](https://example.com/page)"
        citations = parse_citations(content)
        assert len(citations) == 1
        assert citations[0].citation_type == "markdown"

    def test_parse_numbered_priority_over_url(self):
        """测试：编号引用优先于裸 URL"""
        content = "[1] https://example.com/numbered"
        citations = parse_citations(content)
        assert len(citations) == 1
        assert citations[0].citation_type == "numbered"

    def test_parse_url_with_trailing_dot(self):
        """测试：URL 末尾的英文句点应被去除"""
        content = "参见 https://example.com/article."
        citations = parse_citations(content)
        assert len(citations) == 1
        # URL 末尾的英文句点应被去除（rstrip('.,;')）
        assert not citations[0].url.endswith(".")

    def test_parse_url_with_trailing_comma(self):
        """测试：URL 末尾的逗号应被去除"""
        content = "参见 https://example.com/article, 然后继续。"
        citations = parse_citations(content)
        assert len(citations) == 1
        assert not citations[0].url.endswith(",")

    def test_parse_favicon_generated(self):
        """测试：解析后 favicon URL 应被生成"""
        content = "https://example.com/page"
        citations = parse_citations(content)
        assert len(citations) == 1
        assert "favicon" in citations[0].favicon.lower()
        assert "example.com" in citations[0].favicon

    def test_parse_source_domain_extracted(self):
        """测试：解析后 source_domain 应被提取"""
        content = "https://www.example.com/page"
        citations = parse_citations(content)
        assert len(citations) == 1
        assert citations[0].source_domain == "example.com"

    def test_parse_http_and_https(self):
        """测试：同时解析 http 和 https URL"""
        content = "http://a.com 和 https://b.com"
        citations = parse_citations(content)
        assert len(citations) == 2

    def test_parse_multiple_numbered_citations(self):
        """测试：多个编号引用"""
        content = (
            "[1] https://a.com/ref1\n"
            "[2] https://b.com/ref2\n"
            "[3] https://c.com/ref3"
        )
        citations = parse_citations(content)
        assert len(citations) == 3
        assert citations[0].title == "引用 [1]"
        assert citations[1].title == "引用 [2]"
        assert citations[2].title == "引用 [3]"

    def test_parse_multiple_markdown_links(self):
        """测试：多个 Markdown 链接"""
        content = (
            "[论文A](https://a.com/paper1) 和 "
            "[论文B](https://b.com/paper2)"
        )
        citations = parse_citations(content)
        assert len(citations) == 2
        assert citations[0].title == "论文A"
        assert citations[1].title == "论文B"


# ===== 正则模式测试 =====


class TestRegexPatterns:
    """正则表达式模式测试"""

    def test_url_pattern_matches_https(self):
        """测试：URL_PATTERN 匹配 https URL"""
        match = URL_PATTERN.search("see https://example.com/page")
        assert match is not None
        assert "https://example.com/page" in match.group(0)

    def test_url_pattern_matches_http(self):
        """测试：URL_PATTERN 匹配 http URL"""
        match = URL_PATTERN.search("see http://example.com/page")
        assert match is not None

    def test_url_pattern_no_match_plain_text(self):
        """测试：URL_PATTERN 不匹配普通文本"""
        match = URL_PATTERN.search("这是普通文本")
        assert match is None

    def test_markdown_link_pattern_matches(self):
        """测试：MARKDOWN_LINK_PATTERN 匹配 Markdown 链接"""
        match = MARKDOWN_LINK_PATTERN.search("[标题](https://example.com)")
        assert match is not None
        assert match.group(1) == "标题"
        assert match.group(2) == "https://example.com"

    def test_numbered_citation_pattern_matches(self):
        """测试：NUMBERED_CITATION_PATTERN 匹配编号引用"""
        match = NUMBERED_CITATION_PATTERN.search("[1] https://example.com")
        assert match is not None
        assert match.group(1) == "1"
        assert match.group(2) == "https://example.com"


# ===== enrich_citation 异步测试 =====


class TestEnrichCitation:
    """enrich_citation 异步函数测试

    注意：aiohttp 在 enrich_citation 函数内部动态导入。
    若 aiohttp 未安装，函数应优雅降级返回原始 Citation。
    这些测试验证异常处理与优雅降级行为。
    """

    def test_enrich_citation_returns_original_on_failure(self):
        """测试：aiohttp 不可用时应返回原始 Citation（优雅降级）"""
        citation = Citation(url="https://example.com", title="原标题")
        # enrich_citation 内部 import aiohttp 可能失败，
        # 异常被捕获后返回原始对象
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(enrich_citation(citation, timeout=0.1))
        finally:
            loop.close()
        assert result.url == "https://example.com"
        assert result.title == "原标题"

    def test_enrich_citation_preserves_url(self):
        """测试：enrich_citation 后 URL 不变"""
        citation = Citation(url="https://example.com/page")
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(enrich_citation(citation, timeout=0.1))
        finally:
            loop.close()
        assert result.url == "https://example.com/page"

    def test_enrich_citation_preserves_existing_title(self):
        """测试：已有 title 保留不变"""
        citation = Citation(url="https://example.com", title="已有标题")
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(enrich_citation(citation, timeout=0.1))
        finally:
            loop.close()
        assert result.title == "已有标题"

    def test_enrich_citation_does_not_crash_with_invalid_url(self):
        """测试：无效 URL 不导致崩溃"""
        citation = Citation(url="not-a-valid-url")
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(enrich_citation(citation, timeout=0.1))
        finally:
            loop.close()
        assert result.url == "not-a-valid-url"

    def test_enrich_citation_returns_citation_type(self):
        """测试：返回值是 Citation 类型"""
        citation = Citation(url="https://example.com")
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(enrich_citation(citation, timeout=0.1))
        finally:
            loop.close()
        assert isinstance(result, Citation)


# ===== enrich_citations 批量测试 =====


class TestEnrichCitations:
    """enrich_citations 批量异步函数测试"""

    def test_enrich_citations_empty_list(self):
        """测试：空列表应返回空列表"""
        result = asyncio.new_event_loop().run_until_complete(enrich_citations([]))
        assert result == []

    def test_enrich_citations_multiple(self):
        """测试：批量丰富多个引用"""
        citations = [
            Citation(url="https://a.com", title="A"),
            Citation(url="https://b.com", title="B"),
        ]
        # mock enrich_citation 避免真实网络请求
        with patch("backend.ai.citation_parser.enrich_citation") as mock_enrich:
            async def mock_fn(c, timeout=3.0):
                c.snippet = f"摘要-{c.title}"
                return c
            mock_enrich.side_effect = mock_fn
            result = asyncio.new_event_loop().run_until_complete(
                enrich_citations(citations)
            )
        assert len(result) == 2
        assert result[0].snippet == "摘要-A"
        assert result[1].snippet == "摘要-B"

    def test_enrich_citations_preserves_order(self):
        """测试：批量丰富后顺序保持一致"""
        citations = [
            Citation(url="https://a.com", title="第一"),
            Citation(url="https://b.com", title="第二"),
            Citation(url="https://c.com", title="第三"),
        ]
        with patch("backend.ai.citation_parser.enrich_citation") as mock_enrich:
            async def mock_fn(c, timeout=3.0):
                return c
            mock_enrich.side_effect = mock_fn
            result = asyncio.new_event_loop().run_until_complete(
                enrich_citations(citations)
            )
        assert [c.title for c in result] == ["第一", "第二", "第三"]


# ===== 集成测试 =====


class TestCitationParserIntegration:
    """引用解析集成测试"""

    def test_full_parse_workflow(self):
        """测试：完整解析工作流"""
        content = (
            "根据最新研究 [1] https://arxiv.org/paper1 ，"
            "以及 [详细论文](https://scholar.google.com/paper2) 的结果，"
            "还可以参考 https://github.com/repo3 。"
        )
        citations = parse_citations(content)
        # 应解析出 3 个不同 URL
        assert len(citations) == 3
        urls = [c.url for c in citations]
        assert "https://arxiv.org/paper1" in urls
        assert "https://scholar.google.com/paper2" in urls
        assert "https://github.com/repo3" in urls

    def test_parse_with_chinese_text(self):
        """测试：中文文本中的 URL 解析"""
        content = "最新研究显示，详见 https://example.com/cn 了解详情。"
        citations = parse_citations(content)
        assert len(citations) == 1
        assert citations[0].url == "https://example.com/cn"

    def test_parse_long_content(self):
        """测试：长文本中的多个引用"""
        urls = [f"https://example.com/paper{i}" for i in range(10)]
        content = "参考文献：\n" + "\n".join(urls)
        citations = parse_citations(content)
        assert len(citations) == 10

    def test_parse_url_with_special_chars(self):
        """测试：带特殊字符的 URL"""
        content = "https://example.com/search?q=machine+learning&lang=zh"
        citations = parse_citations(content)
        assert len(citations) >= 1
        assert "example.com" in citations[0].source_domain
