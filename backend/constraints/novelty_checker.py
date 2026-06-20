"""新颖性评估模块

基于检索结果计算候选论题与已有文献的相似度，返回 novelty_score（0-100）。
四维创意权重：学科交叉(30%) / 方法迁移(25%) / 痛点突破(25%) / 趋势前瞻(20%)
"""
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class NoveltyResult:
    """新颖性评估结果"""
    score: int  # 0-100
    dimensions: dict  # 4个维度分数
    similarity: float  # 与已有文献的最大相似度
    issues: list[str]
    suggestions: list[str]


# 四维创意权重
DIMENSION_WEIGHTS = {
    "cross_discipline": 0.30,  # 学科交叉
    "method_transfer": 0.25,   # 方法迁移
    "pain_point": 0.25,        # 痛点突破
    "trend_foresight": 0.20,   # 趋势前瞻
}


def calculate_similarity(topic: str, existing_titles: list[str]) -> float:
    """计算论题与已有文献标题的相似度（基于关键词重叠）"""
    if not existing_titles:
        return 0.0

    topic_words = set(_tokenize(topic))
    if not topic_words:
        return 0.0

    max_sim = 0.0
    for title in existing_titles:
        title_words = set(_tokenize(title))
        if not title_words:
            continue
        # Jaccard 相似度
        intersection = topic_words & title_words
        union = topic_words | title_words
        sim = len(intersection) / len(union) if union else 0
        max_sim = max(max_sim, sim)

    return max_sim


def _tokenize(text: str) -> list[str]:
    """简单分词（中文按字，英文按词）"""
    # 英文单词
    en_words = re.findall(r'[a-zA-Z]+', text.lower())
    # 中文字符（2-gram）
    cn_chars = re.findall(r'[\u4e00-\u9fff]', text)
    cn_grams = []
    for i in range(len(cn_chars) - 1):
        cn_grams.append(cn_chars[i] + cn_chars[i + 1])

    return en_words + cn_grams + cn_chars


def score_cross_discipline(topic: str, discipline: str = "") -> int:
    """学科交叉维度评分"""
    if not topic:
        return 0
    # 检测是否包含跨学科关键词
    cross_keywords = ["跨", "交叉", "融合", "多学科", "interdisciplinary", "cross"]
    score = 50  # 基础分
    for kw in cross_keywords:
        if kw in topic.lower():
            score += 20
    return min(score, 100)


def score_method_transfer(topic: str) -> int:
    """方法迁移维度评分"""
    if not topic:
        return 0
    transfer_keywords = ["迁移", "借鉴", "应用", "引入", "transfer", "adapt"]
    score = 50
    for kw in transfer_keywords:
        if kw in topic.lower():
            score += 15
    return min(score, 100)


def score_pain_point(topic: str) -> int:
    """痛点突破维度评分"""
    if not topic:
        return 0
    pain_keywords = ["问题", "挑战", "难点", "瓶颈", "problem", "challenge", "issue"]
    score = 50
    for kw in pain_keywords:
        if kw in topic.lower():
            score += 15
    return min(score, 100)


def score_trend_foresight(topic: str) -> int:
    """趋势前瞻维度评分"""
    if not topic:
        return 0
    trend_keywords = ["趋势", "未来", "新兴", "前沿", "trend", "future", "emerging"]
    score = 50
    for kw in trend_keywords:
        if kw in topic.lower():
            score += 15
    return min(score, 100)


def assess_novelty(topic: str, existing_papers: list[dict] = None, discipline: str = "") -> NoveltyResult:
    """评估论题新颖性

    Args:
        topic: 候选论题
        existing_papers: 已有文献列表（含 title 字段）
        discipline: 学科领域

    Returns:
        NoveltyResult: 新颖性评估结果
    """
    existing_papers = existing_papers or []
    existing_titles = [p.get("title", "") for p in existing_papers if p.get("title")]

    # 计算相似度
    similarity = calculate_similarity(topic, existing_titles)

    # 四维评分
    dimensions = {
        "cross_discipline": score_cross_discipline(topic, discipline),
        "method_transfer": score_method_transfer(topic),
        "pain_point": score_pain_point(topic),
        "trend_foresight": score_trend_foresight(topic),
    }

    # 加权总分
    total_score = sum(dimensions[k] * w for k, w in DIMENSION_WEIGHTS.items())

    # 相似度惩罚（相似度越高，分数越低）
    penalty = similarity * 30  # 最多扣30分
    total_score = max(0, total_score - penalty)

    # 生成问题与建议
    issues = []
    suggestions = []

    if similarity > 0.3:
        issues.append(f"与已有文献相似度较高({similarity:.1%})")
        suggestions.append("建议调整研究方向，增加差异化要素")

    for dim, score in dimensions.items():
        if score < 40:
            dim_name = {
                "cross_discipline": "学科交叉",
                "method_transfer": "方法迁移",
                "pain_point": "痛点突破",
                "trend_foresight": "趋势前瞻",
            }.get(dim, dim)
            issues.append(f"{dim_name}维度评分偏低({score})")
            suggestions.append(f"建议增强{dim_name}方面的创新性")

    return NoveltyResult(
        score=int(total_score),
        dimensions=dimensions,
        similarity=similarity,
        issues=issues,
        suggestions=suggestions,
    )
