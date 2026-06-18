"""文献基线校验模块

基于学位对应的文献基线数量，校验当前文献储备是否充足。
硕士基线 30 篇，博士基线 50 篇。
"""
from backend.config import LITERATURE_BASELINE


def check_literature_count(degree: str, count: int) -> dict:
    """校验文献数量是否达到学位基线要求。

    Args:
        degree: 学位类型，取值为 "master" 或 "doctor"。
        count: 当前文献数量。

    Returns:
        包含 sufficient、current、baseline 字段的校验结果字典。
        若不足，额外包含 reason 字段说明原因。
    """
    baseline = LITERATURE_BASELINE.get(degree)
    if baseline is None:
        return {
            "sufficient": False,
            "current": count,
            "baseline": 0,
            "reason": f"未知学位类型：{degree}",
        }

    if count < baseline:
        return {
            "sufficient": False,
            "current": count,
            "baseline": baseline,
            "reason": f"文献数量{count}低于{degree}生基线{baseline}篇",
        }

    return {
        "sufficient": True,
        "current": count,
        "baseline": baseline,
    }


def get_baseline(degree: str) -> int:
    """返回指定学位的文献基线值。

    Args:
        degree: 学位类型，取值为 "master" 或 "doctor"。

    Returns:
        该学位对应的文献基线篇数；若学位未知则返回 0。
    """
    baseline = LITERATURE_BASELINE.get(degree)
    return baseline if baseline is not None else 0
