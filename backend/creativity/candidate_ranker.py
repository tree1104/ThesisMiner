"""多候选排序模块

基于灵感来源权重为候选打分并排序，筛选出最优候选集合。
"""

# 灵感来源权重映射
# mentor_project 与 senior_inherit 因谱系延续性更高而权重更高；
# cross_domain 与 trend_graft 因创新性较高但风险也较高而权重略低；
# problem_awareness 居中。
INSPIRATION_WEIGHTS = {
    "mentor_project": 0.9,
    "senior_inherit": 0.8,
    "cross_domain": 0.7,
    "trend_graft": 0.6,
    "problem_awareness": 0.75,
}

# 排序后保留的最大候选数量
MAX_RETAINED_CANDIDATES = 5


def rank_candidates(candidates: list[dict], degree: str = "master") -> list[dict]:
    """为每个候选计算分数并按分数降序排序。

    分数基于候选的 inspiration_source 字段对应的权重计算。
    未知来源的候选权重为 0。

    Args:
        candidates: 候选字典列表，每个字典需包含 inspiration_source 字段。
        degree: 学位类型，预留参数以便后续按学位调整权重，默认 "master"。

    Returns:
        排序后的候选列表（保留前 5 个），每个候选新增 score 字段。
    """
    scored: list[dict] = []
    for candidate in candidates:
        source = candidate.get("inspiration_source", "")
        # problem_awareness 类型候选可能使用 discipline_type 字段标识
        if not source and "discipline_type" in candidate:
            source = "problem_awareness"
        score = INSPIRATION_WEIGHTS.get(source, 0.0)
        # 复制候选并添加 score 字段，避免修改原字典
        ranked = dict(candidate)
        ranked["score"] = score
        scored.append(ranked)

    # 按分数降序排序
    scored.sort(key=lambda c: c["score"], reverse=True)

    # 保留前 5 个
    return scored[:MAX_RETAINED_CANDIDATES]


def select_top_candidates(candidates: list[dict], count: int = 3) -> list[dict]:
    """返回前 count 个候选。

    Args:
        candidates: 候选字典列表。
        count: 需要返回的候选数量，默认 3。

    Returns:
        前 count 个候选组成的列表。
    """
    return candidates[:count]
