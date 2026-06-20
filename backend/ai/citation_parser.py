"""模型回复中的引用解析器

解析 URL、Markdown 链接 [text](url)、编号引用 [1] 等格式。
支持异步丰富引用信息（获取网页标题与摘要）。
"""
import re
import urllib.parse
from dataclasses import dataclass
from typing import Optional
import asyncio


@dataclass
class Citation:
    url: str
    title: str = ""
    snippet: str = ""
    source_domain: str = ""
    favicon: str = ""
    citation_type: str = "url"  # url / markdown / numbered


# URL 正则
URL_PATTERN = re.compile(r'https?://[^\s<>"\)\]\)]+', re.IGNORECASE)
# Markdown 链接 [text](url)
MARKDOWN_LINK_PATTERN = re.compile(r'\[([^\]]+)\]\((https?://[^\s\)]+)\)', re.IGNORECASE)
# 编号引用 [1] https://...
NUMBERED_CITATION_PATTERN = re.compile(r'\[(\d+)\]\s*(https?://[^\s]+)')


def parse_citations(content: str) -> list[Citation]:
    """解析回复内容中的所有引用。

    解析优先级：Markdown 链接 > 编号引用 > 裸 URL。
    同一 URL 只保留首次出现的形式。

    Args:
        content: 模型回复文本。

    Returns:
        Citation 对象列表。
    """
    seen_urls = set()
    citations = []

    # 先解析 Markdown 链接（优先级最高，有标题）
    for match in MARKDOWN_LINK_PATTERN.finditer(content):
        title, url = match.group(1), match.group(2)
        if url not in seen_urls:
            seen_urls.add(url)
            domain = extract_domain(url)
            citations.append(Citation(
                url=url, title=title, source_domain=domain,
                favicon=f"https://www.google.com/s2/favicons?domain={domain}&sz=32",
                citation_type="markdown",
            ))

    # 解析编号引用
    for match in NUMBERED_CITATION_PATTERN.finditer(content):
        num, url = match.group(1), match.group(2)
        if url not in seen_urls:
            seen_urls.add(url)
            domain = extract_domain(url)
            citations.append(Citation(
                url=url, title=f"引用 [{num}]", source_domain=domain,
                favicon=f"https://www.google.com/s2/favicons?domain={domain}&sz=32",
                citation_type="numbered",
            ))

    # 解析裸 URL
    for match in URL_PATTERN.finditer(content):
        url = match.group(0).rstrip('.,;')
        if url not in seen_urls:
            seen_urls.add(url)
            domain = extract_domain(url)
            citations.append(Citation(
                url=url, title=domain, source_domain=domain,
                favicon=f"https://www.google.com/s2/favicons?domain={domain}&sz=32",
                citation_type="url",
            ))

    return citations


def extract_domain(url: str) -> str:
    """提取 URL 的域名（去除 www. 前缀）。

    Args:
        url: 完整 URL 字符串。

    Returns:
        域名字符串；解析失败时返回空字符串。
    """
    try:
        parsed = urllib.parse.urlparse(url)
        return parsed.netloc.replace("www.", "")
    except Exception:
        return ""


async def enrich_citation(citation: Citation, timeout: float = 3.0) -> Citation:
    """异步获取网页标题与摘要（超时跳过）。

    Args:
        citation: 待丰富的 Citation 对象。
        timeout: 超时秒数，默认 3.0。

    Returns:
        丰富后的 Citation 对象（原地修改）。
    """
    try:
        import aiohttp
        async with asyncio.timeout(timeout):
            async with aiohttp.ClientSession() as session:
                async with session.get(citation.url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                    if resp.status == 200:
                        html = await resp.text(errors="ignore")
                        # 提取 title
                        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
                        if title_match and not citation.title:
                            citation.title = title_match.group(1).strip()[:200]
                        # 提取 meta description
                        desc_match = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
                        if desc_match:
                            citation.snippet = desc_match.group(1).strip()[:300]
    except (asyncio.TimeoutError, Exception):
        pass
    return citation


async def enrich_citations(citations: list[Citation]) -> list[Citation]:
    """批量异步丰富引用信息。

    Args:
        citations: Citation 对象列表。

    Returns:
        丰富后的 Citation 对象列表。
    """
    tasks = [enrich_citation(c) for c in citations]
    return await asyncio.gather(*tasks)
