"""集成测试：引用管线验证

覆盖：
- 引用解析 → 存储 → 检索的完整管线
- 引用丰富（enrichment）
- 引用展示 API
- 消息中的引用卡片

运行方式：python -m pytest tests/integration/test_citation_pipeline.py -v
"""
import asyncio
import os
import sys
import tempfile
from unittest.mock import AsyncMock, patch

import pytest

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 切换到临时数据库
import backend.database as _db

_tmp_dir = tempfile.mkdtemp(prefix="thesisminer_citation_")
_tmp_db = os.path.join(_tmp_dir, "test_citation.db")
_db.DB_PATH = _tmp_db
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
from backend.sessions.conversation_manager import get_conversation_manager
from backend.sessions import session_manager
from backend.models import SessionCreate, DegreeType, DisciplineType


# ===== 辅助函数 =====

def _make_session(title: str = "引用管线测试") -> str:
    """创建测试会话"""
    req = SessionCreate(
        title=title,
        degree=DegreeType.master,
        discipline=DisciplineType.science_engineering,
        mentor_info="测试导师",
    )
    return session_manager.create_session(req)["id"]


def _make_conversation(session_id: str, title: str = "引用测试对话") -> str:
    """创建测试对话"""
    cm = get_conversation_manager()
    return cm.create_conversation(session_id, title=title)["id"]


# ===== 引用解析测试 =====

class TestCitationParsing:
    """引用解析测试"""

    def test_parse_markdown_link(self):
        """解析 Markdown 链接"""
        content = "参见 [Graph Neural Networks](https://arxiv.org/abs/2024.001) 了解详情"
        citations = parse_citations(content)
        assert len(citations) == 1
        assert citations[0].url == "https://arxiv.org/abs/2024.001"
        assert citations[0].title == "Graph Neural Networks"
        assert citations[0].citation_type == "markdown"

    def test_parse_numbered_citation(self):
        """解析编号引用"""
        content = "[1] https://arxiv.org/abs/2024.001 是一篇重要文献"
        citations = parse_citations(content)
        assert len(citations) == 1
        assert citations[0].url == "https://arxiv.org/abs/2024.001"
        assert citations[0].title == "引用 [1]"
        assert citations[0].citation_type == "numbered"

    def test_parse_bare_url(self):
        """解析裸 URL"""
        content = "更多详情请访问 https://arxiv.org/abs/2024.001"
        citations = parse_citations(content)
        assert len(citations) == 1
        assert citations[0].url == "https://arxiv.org/abs/2024.001"
        assert citations[0].citation_type == "url"

    def test_parse_multiple_citations(self):
        """解析多个引用"""
        content = (
            "[1] https://arxiv.org/abs/001\n"
            "[2] https://arxiv.org/abs/002\n"
            "[3] https://arxiv.org/abs/003"
        )
        citations = parse_citations(content)
        assert len(citations) == 3

    def test_parse_mixed_citation_types(self):
        """解析混合类型的引用"""
        content = (
            "参见 [Markdown链接](https://example.com/1) 与 "
            "[1] https://example.com/2 以及 "
            "https://example.com/3"
        )
        citations = parse_citations(content)
        assert len(citations) == 3
        types = [c.citation_type for c in citations]
        assert "markdown" in types
        assert "numbered" in types
        assert "url" in types

    def test_parse_deduplicates_same_url(self):
        """同一 URL 应去重"""
        content = (
            "https://example.com/duplicate 出现了，"
            "https://example.com/duplicate 又出现了"
        )
        citations = parse_citations(content)
        assert len(citations) == 1

    def test_parse_empty_content(self):
        """空内容应返回空列表"""
        citations = parse_citations("")
        assert citations == []

    def test_parse_no_urls(self):
        """无 URL 的内容应返回空列表"""
        citations = parse_citations("这是一段没有URL的纯文本内容")
        assert citations == []

    def test_parse_extracts_domain(self):
        """应提取域名"""
        content = "https://www.arxiv.org/abs/2024.001"
        citations = parse_citations(content)
        assert len(citations) == 1
        assert citations[0].source_domain == "arxiv.org"

    def test_parse_generates_favicon_url(self):
        """应生成 favicon URL"""
        content = "https://arxiv.org/abs/2024.001"
        citations = parse_citations(content)
        assert len(citations) == 1
        assert "favicon" in citations[0].favicon
        assert "arxiv.org" in citations[0].favicon


# ===== 域名提取测试 =====

class TestDomainExtraction:
    """域名提取测试"""

    def test_extract_domain_simple(self):
        """提取简单域名"""
        assert extract_domain("https://arxiv.org/abs/001") == "arxiv.org"

    def test_extract_domain_with_www(self):
        """提取带 www 的域名（应去除 www.）"""
        assert extract_domain("https://www.arxiv.org/abs/001") == "arxiv.org"

    def test_extract_domain_with_subdomain(self):
        """提取带子域名的域名"""
        domain = extract_domain("https://docs.example.com/page")
        assert "example.com" in domain

    def test_extract_domain_invalid_url(self):
        """无效 URL 应返回空字符串"""
        assert extract_domain("not-a-url") == ""

    def test_extract_domain_empty_string(self):
        """空字符串应返回空字符串"""
        assert extract_domain("") == ""


# ===== 引用丰富测试 =====

class TestCitationEnrichment:
    """引用丰富测试"""

    @pytest.mark.asyncio
    async def test_enrich_citation_returns_citation(self):
        """enrich_citation 应返回 Citation 对象"""
        citation = Citation(url="https://example.com", title="")
        result = await enrich_citation(citation, timeout=0.1)
        assert isinstance(result, Citation)
        assert result.url == "https://example.com"

    @pytest.mark.asyncio
    async def test_enrich_citations_batch(self):
        """enrich_citations 应批量处理"""
        citations = [
            Citation(url="https://example.com/1", title=""),
            Citation(url="https://example.com/2", title=""),
            Citation(url="https://example.com/3", title=""),
        ]
        results = await enrich_citations(citations)
        assert len(results) == 3
        for r in results:
            assert isinstance(r, Citation)

    @pytest.mark.asyncio
    async def test_enrich_citation_handles_timeout(self):
        """enrich_citation 应处理超时"""
        citation = Citation(url="https://slow-server.example.com", title="")
        # 使用极短超时触发超时
        result = await enrich_citation(citation, timeout=0.001)
        assert isinstance(result, Citation)
        # 超时后 title 应保持为空（未被丰富）
        assert result.title == ""


# ===== 引用存储与检索测试 =====

class TestCitationStorageRetrieval:
    """引用存储与检索测试"""

    def test_store_and_retrieve_citations(self):
        """存储并检索引用"""
        sid = _make_session("存储检索测试")
        cm = get_conversation_manager()
        conv_id = _make_conversation(sid)

        citations = [
            {"url": "https://arxiv.org/abs/001", "title": "论文1", "snippet": "摘要1"},
            {"url": "https://arxiv.org/abs/002", "title": "论文2", "snippet": "摘要2"},
        ]
        msg = cm.add_message(conv_id, "assistant", "带引用的回复", citations=citations)

        retrieved = cm.get_message_citations(msg["id"])
        assert len(retrieved) == 2
        assert retrieved[0]["url"] == "https://arxiv.org/abs/001"
        assert retrieved[0]["title"] == "论文1"
        assert retrieved[1]["url"] == "https://arxiv.org/abs/002"

    def test_retrieve_citations_empty_for_no_citations(self):
        """无引用的消息应返回空列表"""
        sid = _make_session("无引用测试")
        cm = get_conversation_manager()
        conv_id = _make_conversation(sid)

        msg = cm.add_message(conv_id, "user", "无引用消息")
        cites = cm.get_message_citations(msg["id"])
        assert cites == []

    def test_citations_cascade_delete_with_message(self):
        """删除消息应级联删除引用"""
        sid = _make_session("级联删除引用测试")
        cm = get_conversation_manager()
        conv_id = _make_conversation(sid)

        citations = [{"url": "https://example.com/1", "title": "引用1"}]
        msg = cm.add_message(conv_id, "assistant", "带引用", citations=citations)

        # 验证引用存在
        assert len(cm.get_message_citations(msg["id"])) == 1

        # 删除对话（级联删除消息和引用）
        cm.delete_conversation(conv_id)

        # 验证消息和引用都已删除
        assert cm.get_message(msg["id"]) is None

    def test_multiple_messages_with_citations(self):
        """多条消息各有引用"""
        sid = _make_session("多消息引用测试")
        cm = get_conversation_manager()
        conv_id = _make_conversation(sid)

        msg1 = cm.add_message(conv_id, "assistant", "回复1",
                              citations=[{"url": "https://example.com/1", "title": "引用1"}])
        msg2 = cm.add_message(conv_id, "assistant", "回复2",
                              citations=[{"url": "https://example.com/2", "title": "引用2"},
                                         {"url": "https://example.com/3", "title": "引用3"}])

        cites1 = cm.get_message_citations(msg1["id"])
        cites2 = cm.get_message_citations(msg2["id"])

        assert len(cites1) == 1
        assert len(cites2) == 2

    def test_citation_preserves_all_fields(self):
        """引用应保留所有字段"""
        sid = _make_session("引用字段保留测试")
        cm = get_conversation_manager()
        conv_id = _make_conversation(sid)

        citations = [{
            "url": "https://arxiv.org/abs/001",
            "title": "GNN for Vulnerability Detection",
            "snippet": "A comprehensive survey of GNN-based methods.",
            "source_domain": "arxiv.org",
            "favicon": "https://www.google.com/s2/favicons?domain=arxiv.org&sz=32",
        }]
        msg = cm.add_message(conv_id, "assistant", "回复", citations=citations)

        cite = cm.get_message_citations(msg["id"])[0]
        assert cite["url"] == "https://arxiv.org/abs/001"
        assert cite["title"] == "GNN for Vulnerability Detection"
        assert cite["snippet"] == "A comprehensive survey of GNN-based methods."
        assert cite["source_domain"] == "arxiv.org"
        assert "favicon" in cite["favicon"]


# ===== 引用解析→存储完整管线测试 =====

class TestCitationPipelineIntegration:
    """引用解析→存储完整管线测试"""

    def test_parse_then_store_pipeline(self):
        """解析引用后存储到 DB"""
        sid = _make_session("完整管线测试")
        cm = get_conversation_manager()
        conv_id = _make_conversation(sid)

        # 模拟 AI 回复内容
        ai_content = (
            "根据检索结果，推荐以下文献：\n"
            "[1] https://arxiv.org/abs/2024.001 - GNN Survey\n"
            "[2] https://arxiv.org/abs/2024.002 - Devign\n"
            "更多详情参见 [Devign论文](https://arxiv.org/abs/1909.03496)"
        )

        # 1. 解析引用
        citations = parse_citations(ai_content)
        assert len(citations) >= 3

        # 2. 转换为存储格式
        cite_dicts = [
            {
                "url": c.url,
                "title": c.title,
                "snippet": c.snippet,
                "source_domain": c.source_domain,
                "favicon": c.favicon,
            }
            for c in citations
        ]

        # 3. 存储到 DB
        msg = cm.add_message(conv_id, "assistant", ai_content, citations=cite_dicts)

        # 4. 检索验证
        retrieved = cm.get_message_citations(msg["id"])
        assert len(retrieved) == len(citations)

        # 验证 URL 一致
        original_urls = {c.url for c in citations}
        retrieved_urls = {c["url"] for c in retrieved}
        assert original_urls == retrieved_urls

    def test_pipeline_with_real_ai_response(self):
        """使用真实 AI 回复样本测试管线"""
        from tests.fixtures.sample_responses import get_response_with_citations

        sid = _make_session("真实回复测试")
        cm = get_conversation_manager()
        conv_id = _make_conversation(sid)

        # 获取样本回复
        response = get_response_with_citations("searcher")
        content = response["content"]
        original_citations = response["citations"]

        # 存储消息与引用
        msg = cm.add_message(conv_id, "assistant", content, citations=original_citations)

        # 检索验证
        retrieved = cm.get_message_citations(msg["id"])
        assert len(retrieved) == len(original_citations)

        # 验证每个引用的 URL
        original_urls = {c["url"] for c in original_citations}
        retrieved_urls = {c["url"] for c in retrieved}
        assert original_urls == retrieved_urls

    def test_pipeline_preserves_citation_order(self):
        """引用顺序应被保留"""
        sid = _make_session("顺序保留测试")
        cm = get_conversation_manager()
        conv_id = _make_conversation(sid)

        citations = [
            {"url": "https://example.com/1", "title": "第一"},
            {"url": "https://example.com/2", "title": "第二"},
            {"url": "https://example.com/3", "title": "第三"},
        ]
        msg = cm.add_message(conv_id, "assistant", "回复", citations=citations)

        retrieved = cm.get_message_citations(msg["id"])
        assert len(retrieved) == 3
        # 按 id 排序（插入顺序）
        retrieved.sort(key=lambda c: c["id"])
        assert retrieved[0]["title"] == "第一"
        assert retrieved[1]["title"] == "第二"
        assert retrieved[2]["title"] == "第三"


# ===== 引用展示测试 =====

class TestCitationDisplay:
    """引用展示测试"""

    def test_citation_has_display_fields(self):
        """引用应有展示所需字段"""
        sid = _make_session("展示字段测试")
        cm = get_conversation_manager()
        conv_id = _make_conversation(sid)

        citations = [{
            "url": "https://arxiv.org/abs/001",
            "title": "展示测试论文",
            "snippet": "这是用于展示测试的摘要",
            "source_domain": "arxiv.org",
            "favicon": "https://www.google.com/s2/favicons?domain=arxiv.org&sz=32",
        }]
        msg = cm.add_message(conv_id, "assistant", "回复", citations=citations)

        cite = cm.get_message_citations(msg["id"])[0]
        # 展示所需字段
        assert "url" in cite
        assert "title" in cite
        assert "snippet" in cite
        assert "source_domain" in cite
        assert "favicon" in cite

    def test_citation_with_empty_fields(self):
        """空字段的引用应能正常存储"""
        sid = _make_session("空字段测试")
        cm = get_conversation_manager()
        conv_id = _make_conversation(sid)

        citations = [{"url": "https://example.com/empty", "title": "", "snippet": ""}]
        msg = cm.add_message(conv_id, "assistant", "回复", citations=citations)

        cite = cm.get_message_citations(msg["id"])[0]
        assert cite["url"] == "https://example.com/empty"
        assert cite["title"] == ""
        assert cite["snippet"] == ""


# ===== Citation 数据类测试 =====

class TestCitationDataclass:
    """Citation 数据类测试"""

    def test_citation_default_values(self):
        """Citation 应有正确的默认值"""
        c = Citation(url="https://example.com")
        assert c.url == "https://example.com"
        assert c.title == ""
        assert c.snippet == ""
        assert c.source_domain == ""
        assert c.favicon == ""
        assert c.citation_type == "url"

    def test_citation_with_all_fields(self):
        """Citation 应能设置所有字段"""
        c = Citation(
            url="https://example.com",
            title="标题",
            snippet="摘要",
            source_domain="example.com",
            favicon="favicon.ico",
            citation_type="markdown",
        )
        assert c.url == "https://example.com"
        assert c.title == "标题"
        assert c.snippet == "摘要"
        assert c.source_domain == "example.com"
        assert c.favicon == "favicon.ico"
        assert c.citation_type == "markdown"


# ===== 正则模式测试 =====

class TestCitationPatterns:
    """引用正则模式测试"""

    def test_url_pattern_matches_http(self):
        """URL_PATTERN 应匹配 http 链接"""
        match = URL_PATTERN.search("访问 http://example.com 查看")
        assert match is not None

    def test_url_pattern_matches_https(self):
        """URL_PATTERN 应匹配 https 链接"""
        match = URL_PATTERN.search("访问 https://example.com 查看")
        assert match is not None

    def test_markdown_link_pattern_matches(self):
        """MARKDOWN_LINK_PATTERN 应匹配 Markdown 链接"""
        match = MARKDOWN_LINK_PATTERN.search("[标题](https://example.com)")
        assert match is not None
        assert match.group(1) == "标题"
        assert match.group(2) == "https://example.com"

    def test_numbered_citation_pattern_matches(self):
        """NUMBERED_CITATION_PATTERN 应匹配编号引用"""
        match = NUMBERED_CITATION_PATTERN.search("[1] https://example.com")
        assert match is not None
        assert match.group(1) == "1"
        assert match.group(2) == "https://example.com"
