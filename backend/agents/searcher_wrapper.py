"""Searcher 智能体模块

模拟文献检索与新颖性检查，不实际调用外部 API。
所有检索结果为本地模拟生成，用于在无外部检索服务时保证系统可用。

v6.0 增强：支持真实文献检索热插拔，通过工厂模式在 MockSearcher 与
RealSearcher 之间切换，并提供降级机制（真实 API 超时或异常时回退到
MockSearcher，响应附加 search_degraded 标记）。

既有同步函数保持不变以兼容旧调用方；新增 MockSearcher / RealSearcher
类提供统一异步接口，由 get_searcher() 工厂按配置返回实例。
"""
import asyncio
import logging
import random
import xml.etree.ElementTree as ET

import httpx

from backend.config import get_settings

logger = logging.getLogger(__name__)


def search_literature(keyword: str, count: int = 10) -> list[dict]:
    """模拟文献检索，返回指定数量的模拟文献。

    不实际调用外部 API，仅根据关键词与数量生成模拟文献条目。

    Args:
        keyword: 检索关键词。
        count: 返回文献数量，默认 10。

    Returns:
        模拟文献字典列表，每项包含 title、authors、year、abstract、source。
    """
    papers = []
    for i in range(count):
        papers.append({
            "title": f"关于{keyword}的研究{i + 1}",
            "authors": ["作者A", "作者B"],
            "year": 2020 + i,
            "abstract": f"本文围绕{keyword}展开研究，探讨其核心问题与方法，是第{i + 1}篇模拟文献。",
            "source": "模拟数据库",
        })
    return papers


def check_novelty(title: str, existing_titles: list[str] = None) -> dict:
    """检查标题与已有标题的相似度，评估新颖性。

    通过字符串包含关系与编辑距离计算相似度，再据此评估创新等级。

    评估标准（基于与已有标题的最大相似度）：
        - <0.4：高创新
        - 0.4-0.7：常规创新
        - 0.7-0.85：微创新
        - >0.85：预警

    Args:
        title: 待检查的标题。
        existing_titles: 已有标题列表，默认为空。

    Returns:
        包含以下字段的字典：
        - novelty_score: 与已有标题的最大相似度（0-1）。
        - similar_titles: 相似度≥0.7 的已有标题列表。
        - assessment: 创新等级评估。
    """
    if existing_titles is None:
        existing_titles = []

    similar_titles = []
    max_similarity = 0.0

    for existing in existing_titles:
        similarity = _calculate_similarity(title, existing)
        if similarity > max_similarity:
            max_similarity = similarity
        # 相似度≥0.7 视为相似标题
        if similarity >= 0.7:
            similar_titles.append(existing)

    novelty_score = round(max_similarity, 2)

    # 评估标准
    if novelty_score > 0.85:
        assessment = "预警"
    elif novelty_score >= 0.7:
        assessment = "微创新"
    elif novelty_score >= 0.4:
        assessment = "常规创新"
    else:
        assessment = "高创新"

    return {
        "novelty_score": novelty_score,
        "similar_titles": similar_titles,
        "assessment": assessment,
    }


def _calculate_similarity(s1: str, s2: str) -> float:
    """计算两个字符串的相似度（0-1）。

    优先判断包含关系，否则基于 Levenshtein 编辑距离计算相似度。

    Args:
        s1: 字符串一。
        s2: 字符串二。

    Returns:
        相似度，范围 0-1，越大表示越相似。
    """
    if not s1 or not s2:
        return 0.0

    # 完全相同
    if s1 == s2:
        return 1.0

    # 包含关系：一方完全包含另一方则相似度为 1.0
    if s1 in s2 or s2 in s1:
        return 1.0

    # 基于编辑距离计算相似度
    distance = _levenshtein_distance(s1, s2)
    max_len = max(len(s1), len(s2))
    similarity = 1.0 - (distance / max_len)
    return max(0.0, min(1.0, similarity))


def _levenshtein_distance(s1: str, s2: str) -> int:
    """计算两个字符串的 Levenshtein 编辑距离。

    Args:
        s1: 字符串一。
        s2: 字符串二。

    Returns:
        编辑距离，即将 s1 转换为 s2 所需的最少单字符编辑操作数。
    """
    # 确保 s1 为较长字符串，减少内存分配
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (0 if c1 == c2 else 1)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def estimate_literature_count(keyword: str) -> int:
    """模拟估算关键词相关文献数量。

    基于关键词长度生成 20-100 之间的伪随机数。

    Args:
        keyword: 检索关键词。

    Returns:
        估算的相关文献数量（20-100）。
    """
    seed = len(keyword) if keyword else 1
    # 使用局部随机实例，避免影响全局随机状态
    rng = random.Random(seed)
    return rng.randint(20, 100)


def search_and_summarize(keyword: str, count: int = 5) -> dict:
    """检索文献并返回汇总信息。

    调用 search_literature 获取文献列表，并附加汇总摘要。

    Args:
        keyword: 检索关键词。
        count: 返回文献数量，默认 5。

    Returns:
        包含以下字段的字典：
        - keyword: 检索关键词。
        - total_found: 找到的文献数量。
        - papers: 文献列表。
        - summary: 汇总摘要文本。
    """
    papers = search_literature(keyword, count)
    return {
        "keyword": keyword,
        "total_found": count,
        "papers": papers,
        "summary": f"找到{count}篇相关文献",
    }


# ==================== 异步检索器类（v6.0 新增） ====================


class MockSearcher:
    """模拟检索器，包装既有同步 mock 函数为统一异步接口。

    所有方法返回的字典均包含 search_degraded 字段（恒为 False），
    表示当前为正常模拟模式而非降级模式。
    """

    async def search_literature(self, keyword: str, count: int = 10) -> dict:
        """模拟文献检索。"""
        papers = search_literature(keyword, count)
        return {
            "papers": papers,
            "search_degraded": False,
            "source": "mock",
        }

    async def check_novelty(
        self, title: str, existing_titles: list[str] = None
    ) -> dict:
        """模拟新颖性检查。"""
        result = check_novelty(title, existing_titles)
        result["search_degraded"] = False
        return result

    async def estimate_literature_count(self, keyword: str) -> dict:
        """模拟估算文献数量。"""
        count = estimate_literature_count(keyword)
        return {
            "count": count,
            "search_degraded": False,
            "source": "mock",
        }

    async def search_and_summarize(self, keyword: str, count: int = 5) -> dict:
        """模拟检索并汇总。"""
        result = search_and_summarize(keyword, count)
        result["search_degraded"] = False
        result["source"] = "mock"
        return result


class RealSearcher:
    """真实检索器，异步调用 arXiv 与 Semantic Scholar API。

    通过 httpx.AsyncClient 并发请求两个数据源，合并去重后返回结果。
    当 API 超时（>5s）或异常时，自动降级到 MockSearcher 并在响应中
    附加 search_degraded: True 标记。
    """

    # arXiv Atom API
    ARXIV_API = "http://export.arxiv.org/api/query"
    # Semantic Scholar Graph API
    SEMANTIC_SCHOLAR_API = (
        "https://api.semanticscholar.org/graph/v1/paper/search"
    )
    # 统一 5 秒超时
    TIMEOUT = httpx.Timeout(5.0)

    def __init__(self) -> None:
        settings = get_settings()
        self._arxiv_key: str = settings.search_api_keys.get("arxiv", "")
        self._ss_key: str = settings.search_api_keys.get("semantic_scholar", "")
        # 降级时使用的 MockSearcher 实例
        self._mock = MockSearcher()

    # ---------- 公共异步接口 ----------

    async def search_literature(self, keyword: str, count: int = 10) -> dict:
        """真实文献检索，失败时降级到 MockSearcher。"""
        try:
            papers = await self._fetch_papers(keyword, count)
            return {
                "papers": papers,
                "search_degraded": False,
                "source": "real",
            }
        except Exception as e:  # noqa: BLE001 - 降级需捕获所有异常
            logger.warning("真实文献检索失败，降级到 MockSearcher: %s", e)
            result = await self._mock.search_literature(keyword, count)
            result["search_degraded"] = True
            return result

    async def check_novelty(
        self, title: str, existing_titles: list[str] = None
    ) -> dict:
        """新颖性检查：先用真实检索补充已有标题，再做相似度比较。

        失败时降级到仅使用传入的 existing_titles。
        """
        try:
            papers = await self._fetch_papers(title, 20)
            real_titles = [p["title"] for p in papers if p.get("title")]
            all_titles = list(existing_titles or []) + real_titles
            result = check_novelty(title, all_titles)
            result["search_degraded"] = False
            return result
        except Exception as e:  # noqa: BLE001
            logger.warning("真实新颖性检查失败，降级处理: %s", e)
            result = check_novelty(title, existing_titles)
            result["search_degraded"] = True
            return result

    async def estimate_literature_count(self, keyword: str) -> dict:
        """估算文献数量：以真实检索返回的结果数作为下限估计。"""
        try:
            papers = await self._fetch_papers(keyword, 50)
            return {
                "count": len(papers),
                "search_degraded": False,
                "source": "real",
            }
        except Exception as e:  # noqa: BLE001
            logger.warning("真实文献计数失败，降级到 MockSearcher: %s", e)
            result = await self._mock.estimate_literature_count(keyword)
            result["search_degraded"] = True
            return result

    async def search_and_summarize(self, keyword: str, count: int = 5) -> dict:
        """真实检索并汇总，失败时降级到 MockSearcher。"""
        try:
            papers = await self._fetch_papers(keyword, count)
            return {
                "keyword": keyword,
                "total_found": len(papers),
                "papers": papers,
                "summary": f"找到{len(papers)}篇相关文献",
                "search_degraded": False,
                "source": "real",
            }
        except Exception as e:  # noqa: BLE001
            logger.warning("真实检索汇总失败，降级到 MockSearcher: %s", e)
            result = await self._mock.search_and_summarize(keyword, count)
            result["search_degraded"] = True
            return result

    # ---------- 内部实现 ----------

    async def _fetch_papers(self, keyword: str, count: int) -> list[dict]:
        """并发请求 arXiv 与 Semantic Scholar，合并去重后返回。

        任一数据源失败时仅记录警告，只要至少一个数据源有结果即返回；
        若全部失败则抛出异常以触发上层降级。
        """
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            arxiv_task = self._fetch_arxiv(client, keyword, count)
            ss_task = self._fetch_semantic_scholar(client, keyword, count)
            arxiv_results, ss_results = await asyncio.gather(
                arxiv_task, ss_task, return_exceptions=True
            )

        papers: list[dict] = []
        if isinstance(arxiv_results, list):
            papers.extend(arxiv_results)
        elif isinstance(arxiv_results, BaseException):
            logger.warning("arXiv 检索异常: %s", arxiv_results)

        if isinstance(ss_results, list):
            papers.extend(ss_results)
        elif isinstance(ss_results, BaseException):
            logger.warning("Semantic Scholar 检索异常: %s", ss_results)

        if not papers:
            raise RuntimeError("arXiv 与 Semantic Scholar 均无结果")

        # 按标题去重（大小写无关）
        seen: set[str] = set()
        unique: list[dict] = []
        for p in papers:
            key = (p.get("title") or "").strip().lower()
            if key and key not in seen:
                seen.add(key)
                unique.append(p)
        return unique

    async def _fetch_arxiv(
        self, client: httpx.AsyncClient, keyword: str, count: int
    ) -> list[dict]:
        """请求 arXiv API 并解析 Atom XML。"""
        params = {
            "search_query": f"all:{keyword}",
            "start": 0,
            "max_results": count,
        }
        resp = await client.get(self.ARXIV_API, params=params)
        resp.raise_for_status()
        return self._parse_arxiv_xml(resp.text)

    @staticmethod
    def _parse_arxiv_xml(xml_text: str) -> list[dict]:
        """解析 arXiv Atom feed XML，提取标题/作者/年份/摘要。"""
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(xml_text)
        papers: list[dict] = []
        for entry in root.findall("atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            title = (
                title_el.text.strip()
                if title_el is not None and title_el.text
                else ""
            )
            # 作者列表
            authors: list[str] = []
            for author in entry.findall("atom:author", ns):
                name_el = author.find("atom:name", ns)
                if name_el is not None and name_el.text:
                    authors.append(name_el.text.strip())
            # 发表年份
            year = None
            published_el = entry.find("atom:published", ns)
            if published_el is not None and published_el.text:
                try:
                    year = int(published_el.text[:4])
                except ValueError:
                    year = None
            # 摘要
            summary_el = entry.find("atom:summary", ns)
            abstract = (
                summary_el.text.strip()
                if summary_el is not None and summary_el.text
                else ""
            )
            papers.append(
                {
                    "title": title,
                    "authors": authors,
                    "year": year,
                    "abstract": abstract,
                    "source": "arxiv",
                }
            )
        return papers

    async def _fetch_semantic_scholar(
        self, client: httpx.AsyncClient, keyword: str, count: int
    ) -> list[dict]:
        """请求 Semantic Scholar API 并解析 JSON。"""
        params = {
            "query": keyword,
            "limit": count,
            "fields": "title,authors,year,abstract",
        }
        headers: dict = {}
        if self._ss_key:
            headers["x-api-key"] = self._ss_key
        resp = await client.get(
            self.SEMANTIC_SCHOLAR_API, params=params, headers=headers
        )
        resp.raise_for_status()
        data = resp.json()
        papers: list[dict] = []
        for item in data.get("data", []) or []:
            authors: list[str] = []
            for a in item.get("authors", []) or []:
                name = a.get("name")
                if name:
                    authors.append(name)
            papers.append(
                {
                    "title": item.get("title", "") or "",
                    "authors": authors,
                    "year": item.get("year"),
                    "abstract": item.get("abstract", "") or "",
                    "source": "semantic_scholar",
                }
            )
        return papers


# ==================== 工厂函数 ====================


def get_searcher() -> MockSearcher | RealSearcher:
    """根据配置返回检索器实例。

    当 settings.real_search_enabled 为 True 时返回 RealSearcher，
    否则返回 MockSearcher。实现检索策略的热插拔。
    """
    settings = get_settings()
    if settings.real_search_enabled:
        return RealSearcher()
    return MockSearcher()
