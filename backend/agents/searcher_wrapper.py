"""Searcher 智能体模块

模拟文献检索与新颖性检查，不实际调用外部 API。
所有检索结果为本地模拟生成，用于在无外部检索服务时保证系统可用。

v6.0 增强：支持真实文献检索热插拔，通过工厂模式在 MockSearcher 与
RealSearcher 之间切换，并提供降级机制（真实 API 超时或异常时回退到
MockSearcher，响应附加 search_degraded 标记）。

v8.0 升级：在保留既有同步函数与异步检索器类的基础上，新增 SearcherAgent
作为 BaseAgent 子类，统一接入多 Agent 架构。既有函数与类保持兼容。
"""
import asyncio
import logging
import random
import xml.etree.ElementTree as ET

import httpx

from backend.agents.base_agent import AgentResult, BaseAgent
from backend.config import get_settings, get_step_model

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


# ==================== SearcherAgent（v8.0 新增） ====================


class SearcherAgent(BaseAgent):
    """SearcherAgent - 文献检索 Agent

    在保留既有同步/异步检索函数的基础上，包装为 BaseAgent 子类：
        1. 通过 get_searcher() 工厂获取检索器实例执行文献检索
        2. 调用 ai_proxy.call_llm 生成检索结果摘要
        3. 返回 AgentResult，data 中包含 papers 与 citations
    """

    def __init__(self):
        super().__init__(
            agent_id="searcher",
            name="Searcher",
            description="文献检索 Agent，负责近2年文献检索与汇总",
            system_prompt=self._default_system_prompt(),
            model_id=get_step_model("search"),
            temperature=0.3,
            max_tokens=2048,
            capabilities=["web_search"],
        )

    @staticmethod
    def _default_system_prompt() -> str:
        return (
            "你是 ThesisMiner 的文献检索 Agent（Searcher）。\n"
            "你的职责：\n"
            "1. 根据用户研究方向调用文献检索服务获取近2年相关文献\n"
            "2. 对检索结果进行去重、筛选与结构化整理\n"
            "3. 生成简洁的检索摘要，标注关键文献与引用\n"
            "4. 输出 JSON 格式：{\"summary\": str, \"key_findings\": list}\n"
            "保持客观、学术严谨，不臆造文献。"
        )

    async def run(self, task_input: dict) -> AgentResult:
        """执行文献检索任务

        Args:
            task_input: 包含以下字段：
                - query: 检索关键词（必填）
                - years: 检索年限，默认 2
                - count: 文献数量，默认 10

        Returns:
            AgentResult，data 包含 papers 与 citations。
        """
        query = task_input.get("query", "")
        years = task_input.get("years", 2)
        count = task_input.get("count", 10)

        if not query:
            return AgentResult(
                agent_id=self.agent_id,
                success=False,
                error="缺少检索关键词 query",
            )

        try:
            # 1. 调用既有检索器获取文献
            searcher = get_searcher()
            search_data = await searcher.search_literature(query, count=count)
            papers = search_data.get("papers", [])

            # 2. 过滤近 years 年文献（若文献含 year 字段）
            current_year = 2026
            year_threshold = current_year - years
            recent_papers = [
                p for p in papers
                if not isinstance(p.get("year"), int)
                or p.get("year", 0) >= year_threshold
            ]
            # 若过滤后为空，回退到全部文献
            if not recent_papers and papers:
                recent_papers = papers

            # 3. 构建引用列表
            citations = [
                {
                    "title": p.get("title", ""),
                    "authors": p.get("authors", []),
                    "year": p.get("year"),
                    "source": p.get("source", ""),
                }
                for p in recent_papers
            ]

            # 4. 调用 LLM 生成检索摘要（独立上下文）
            user_prompt = self._build_user_prompt(query, recent_papers, years)
            self.add_message("user", user_prompt)

            # 延迟导入以避免循环依赖
            from backend.ai.ai_proxy import call_llm

            llm_result = await call_llm(
                system_prompt=self.system_prompt,
                user_prompt=user_prompt,
                model=self.model_id,
                temperature=self.temperature,
                purpose="search",
            )

            content = llm_result.get("content", "")
            # 记录 assistant 回复到自身上下文
            self.add_message("assistant", content)

            return AgentResult(
                agent_id=self.agent_id,
                success=True,
                content=content,
                data={
                    "papers": recent_papers,
                    "citations": citations,
                    "total_found": len(recent_papers),
                    "years": years,
                    "search_degraded": search_data.get("search_degraded", False),
                },
                citations=citations,
                token_usage={
                    "prompt_tokens": llm_result.get("prompt_tokens", 0),
                    "completion_tokens": llm_result.get("completion_tokens", 0),
                    "total_tokens": llm_result.get("total_tokens", 0),
                },
            )
        except Exception as e:
            # 检索或 LLM 调用失败时返回失败结果，保留 papers 兜底
            return AgentResult(
                agent_id=self.agent_id,
                success=False,
                error=f"检索失败: {e}",
                data={"papers": [], "citations": []},
            )

    @staticmethod
    def _build_user_prompt(query: str, papers: list[dict], years: int) -> str:
        """构建 LLM 用户提示

        Args:
            query: 检索关键词。
            papers: 检索到的文献列表。
            years: 检索年限。

        Returns:
            用户提示字符串。
        """
        paper_lines = []
        for i, p in enumerate(papers[:10], 1):
            title = p.get("title", "")
            authors = ", ".join(p.get("authors", [])[:3])
            year = p.get("year", "")
            paper_lines.append(f"{i}. [{year}] {authors} - {title}")

        papers_text = "\n".join(paper_lines) if paper_lines else "（暂无文献）"

        return (
            f"研究方向：{query}\n"
            f"检索年限：近 {years} 年\n"
            f"检索到的文献：\n{papers_text}\n\n"
            f"请基于以上文献生成检索摘要，并指出关键发现。"
            f"输出 JSON：{{\"summary\": str, \"key_findings\": list}}。"
        )
