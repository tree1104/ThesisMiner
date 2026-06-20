"""学术时间约束模块

基于学位对应的学术日历，校验研究周期是否在允许年限内。
硕士最长 1 年，博士最长 2 年。
"""
from backend.config import ACADEMIC_CALENDAR


def validate_timeframe(degree: str, timeframe_months: int) -> dict:
    """校验研究周期是否在学位允许的最大年限内。

    Args:
        degree: 学位类型，取值为 "master" 或 "doctor"。
        timeframe_months: 研究周期（月数）。

    Returns:
        包含 feasible、reason、max_months 字段的校验结果字典。
        若不可行，reason 字段说明超期原因。
    """
    calendar = ACADEMIC_CALENDAR.get(degree)
    if calendar is None:
        return {
            "feasible": False,
            "reason": f"未知学位类型：{degree}",
            "max_months": 0,
        }

    max_years = calendar["max_years"]
    max_months = max_years * 12

    if timeframe_months > max_months:
        return {
            "feasible": False,
            "reason": f"研究周期{timeframe_months}个月超过{degree}生{max_years}年限制",
            "max_months": max_months,
        }

    return {"feasible": True, "max_months": max_months}


def get_calendar(degree: str) -> dict:
    """返回指定学位的时间约束信息。

    Args:
        degree: 学位类型，取值为 "master" 或 "doctor"。

    Returns:
        该学位对应的学术日历字典，包含 max_years、description 字段；
        若学位未知则返回空字典。
    """
    calendar = ACADEMIC_CALENDAR.get(degree)
    if calendar is None:
        return {}
    # 返回副本以避免外部修改常量
    return dict(calendar)
