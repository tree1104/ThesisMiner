"""Searcher 智能体模块

模拟文献检索与新颖性检查，不实际调用外部 API。
所有检索结果为本地模拟生成，用于在无外部检索服务时保证系统可用。
"""
import random


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
