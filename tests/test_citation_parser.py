"""Task 10.5：引用解析器测试

验证：
- URL 解析（裸 URL）
- Markdown 链接解析 [text](url)
- 编号引用解析 [1] url
- 域名提取
- 去重逻辑
"""
import os
import sys

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.ai.citation_parser import (
    Citation,
    parse_citations,
    extract_domain,
    URL_PATTERN,
    MARKDOWN_LINK_PATTERN,
    NUMBERED_CITATION_PATTERN,
)


def test_parse_bare_url():
    """测试裸 URL 解析"""
    content = "请参考 https://www.example.com/article 了解更多。"
    citations = parse_citations(content)
    assert len(citations) == 1
    assert citations[0].url == "https://www.example.com/article"
    assert citations[0].citation_type == "url"
    # extract_domain 会去除 www. 前缀
    assert citations[0].source_domain == "example.com"
    print("✓ 裸 URL 解析")


def test_parse_url_with_trailing_punctuation():
    """测试 URL 末尾标点剥离"""
    content = "参见 https://arxiv.org/abs/2401.00001."
    citations = parse_citations(content)
    assert len(citations) == 1
    # 末尾的句号应被剥离
    assert citations[0].url == "https://arxiv.org/abs/2401.00001"
    print("✓ URL 末尾标点剥离")


def test_parse_markdown_link():
    """测试 Markdown 链接解析"""
    content = "详见 [深度学习综述](https://example.com/dl-survey) 一文。"
    citations = parse_citations(content)
    assert len(citations) == 1
    assert citations[0].url == "https://example.com/dl-survey"
    assert citations[0].title == "深度学习综述"
    assert citations[0].citation_type == "markdown"
    print("✓ Markdown 链接解析")


def test_parse_numbered_citation():
    """测试编号引用解析"""
    content = "相关研究 [1] https://arxiv.org/abs/2024.12345 提出了该方法。"
    citations = parse_citations(content)
    assert len(citations) == 1
    assert citations[0].url == "https://arxiv.org/abs/2024.12345"
    assert citations[0].title == "引用 [1]"
    assert citations[0].citation_type == "numbered"
    print("✓ 编号引用解析")


def test_parse_mixed_citations():
    """测试混合引用解析（Markdown + 编号 + 裸 URL）"""
    content = (
        "详见 [综述A](https://example.com/a) 与 "
        "[2] https://example.com/b "
        "另见 https://example.com/c"
    )
    citations = parse_citations(content)
    assert len(citations) == 3
    urls = [c.url for c in citations]
    assert "https://example.com/a" in urls
    assert "https://example.com/b" in urls
    assert "https://example.com/c" in urls
    print("✓ 混合引用解析")


def test_parse_dedup():
    """测试同一 URL 去重（Markdown 优先）"""
    content = (
        "详见 [综述](https://example.com/dup) 与 "
        "https://example.com/dup 重复链接。"
    )
    citations = parse_citations(content)
    # 同一 URL 只保留首次出现的形式（Markdown）
    assert len(citations) == 1
    assert citations[0].citation_type == "markdown"
    assert citations[0].title == "综述"
    print("✓ 同一 URL 去重")


def test_parse_no_citations():
    """测试无引用内容"""
    content = "这是一段没有引用的普通文本。"
    citations = parse_citations(content)
    assert len(citations) == 0
    print("✓ 无引用内容")


def test_parse_empty_content():
    """测试空内容"""
    citations = parse_citations("")
    assert len(citations) == 0
    print("✓ 空内容")


def test_extract_domain():
    """测试域名提取"""
    assert extract_domain("https://www.example.com/path") == "example.com"
    assert extract_domain("https://example.com") == "example.com"
    assert extract_domain("http://sub.example.com/page") == "sub.example.com"
    assert extract_domain("https://arxiv.org/abs/1234") == "arxiv.org"
    print("✓ 域名提取")


def test_extract_domain_invalid():
    """测试无效 URL 域名提取"""
    assert extract_domain("not a url") == ""
    print("✓ 无效 URL 域名提取")


def test_citation_favicon():
    """测试 favicon 生成"""
    content = "参见 https://example.com/article"
    citations = parse_citations(content)
    assert len(citations) == 1
    assert "favicons" in citations[0].favicon
    assert "example.com" in citations[0].favicon
    print("✓ favicon 生成")


def test_citation_dataclass():
    """测试 Citation 数据结构默认值"""
    c = Citation(url="https://example.com")
    assert c.url == "https://example.com"
    assert c.title == ""
    assert c.snippet == ""
    assert c.source_domain == ""
    assert c.favicon == ""
    assert c.citation_type == "url"
    print("✓ Citation 数据结构默认值")


def test_url_pattern():
    """测试 URL 正则匹配"""
    matches = URL_PATTERN.findall("参见 https://example.com/a 和 http://test.org/b")
    assert len(matches) == 2
    print("✓ URL 正则匹配")


def test_markdown_link_pattern():
    """测试 Markdown 链接正则匹配"""
    matches = MARKDOWN_LINK_PATTERN.findall("详见 [文本](https://example.com) 这里")
    assert len(matches) == 1
    assert matches[0][0] == "文本"
    assert matches[0][1] == "https://example.com"
    print("✓ Markdown 链接正则匹配")


def test_numbered_citation_pattern():
    """测试编号引用正则匹配"""
    matches = NUMBERED_CITATION_PATTERN.findall("参见 [1] https://example.com")
    assert len(matches) == 1
    assert matches[0][0] == "1"
    assert matches[0][1] == "https://example.com"
    print("✓ 编号引用正则匹配")


if __name__ == "__main__":
    test_parse_bare_url()
    test_parse_url_with_trailing_punctuation()
    test_parse_markdown_link()
    test_parse_numbered_citation()
    test_parse_mixed_citations()
    test_parse_dedup()
    test_parse_no_citations()
    test_parse_empty_content()
    test_extract_domain()
    test_extract_domain_invalid()
    test_citation_favicon()
    test_citation_dataclass()
    test_url_pattern()
    test_markdown_link_pattern()
    test_numbered_citation_pattern()
    print("\n所有引用解析测试通过 ✓")
