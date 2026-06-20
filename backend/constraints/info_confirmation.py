"""信息确权门禁

强制联网检索近2年文献，展示摘要后等待用户确认（不可跳过）。
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class InfoConfirmationResult:
    """信息确权结果"""
    confirmed: bool
    papers: list  # 检索到的文献
    summary: str  # 文献摘要
    message: str


async def search_recent_papers(query: str, years: int = 2) -> dict:
    """检索近2年文献

    使用 SearcherAgent 进行检索，返回文献列表与摘要。
    """
    try:
        from backend.agents.agent_registry import get_agent
        searcher = get_agent("searcher")
        result = await searcher.run({"query": query, "years": years})
        return {
            "papers": result.data.get("papers", []),
            "summary": result.content,
            "citations": result.citations,
        }
    except Exception as e:
        return {"papers": [], "summary": f"检索失败: {e}", "citations": []}


def format_paper_summary(papers: list) -> str:
    """格式化文献摘要供用户确认"""
    if not papers:
        return "未检索到相关文献"

    lines = [f"共检索到 {len(papers)} 篇近2年相关文献：\n"]
    for i, paper in enumerate(papers[:10], 1):  # 最多展示10篇
        title = paper.get("title", "无标题")
        authors = paper.get("authors", "未知作者")
        year = paper.get("year", "")
        abstract = paper.get("abstract", "")[:100]
        lines.append(f"{i}. [{year}] {title}\n   作者: {authors}\n   摘要: {abstract}...\n")

    if len(papers) > 10:
        lines.append(f"\n...还有 {len(papers) - 10} 篇文献未展示")

    lines.append("\n请确认以上信息是否准确，确认后将进入创意生成阶段。")
    return "\n".join(lines)


def validate_confirmation(user_response: str) -> bool:
    """验证用户确认响应"""
    if not user_response:
        return False
    positive_keywords = ["确认", "正确", "yes", "ok", "继续", "没问题", "准确"]
    return any(kw in user_response.lower() for kw in positive_keywords)
