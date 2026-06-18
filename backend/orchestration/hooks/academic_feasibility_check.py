"""可行性拦截钩子

基于学术日历与文献基线，对提案进行可行性校验与拦截。
"""


def run(
    proposal: dict,
    degree: str,
    timeframe_months: int = 12,
    literature_count: int = 30,
) -> dict:
    """可行性拦截钩子入口。

    校验研究周期与文献储备：时间不可行则抛出 InfeasibleError，
    文献不足则在提案中添加 warning 字段。

    Args:
        proposal: 提案字典。
        degree: 学位类型，取值为 "master" 或 "doctor"。
        timeframe_months: 研究周期（月数），默认 12。
        literature_count: 当前文献数量，默认 30。

    Returns:
        处理后的提案字典，含 feasibility_check 结果。

    Raises:
        InfeasibleError: 当研究周期超过学位允许的最大年限时。
    """
    # 延迟导入避免循环依赖
    from backend.constraints import academic_calendar, lit_baselines
    from backend.constraints.exceptions import InfeasibleError

    # 校验时间可行性
    timeframe_result = academic_calendar.validate_timeframe(degree, timeframe_months)

    # 时间不可行则抛出异常
    if not timeframe_result.get("feasible", False):
        raise InfeasibleError(timeframe_result.get("reason", "研究周期不可行"))

    # 校验文献基线
    lit_result = lit_baselines.check_literature_count(degree, literature_count)

    # 文献不足则添加警告
    if not lit_result.get("sufficient", False):
        proposal["warning"] = lit_result.get("reason", "文献储备不足")

    # 记录可行性检查结果
    proposal["feasibility_check"] = {
        "timeframe": timeframe_result,
        "literature": lit_result,
    }

    return proposal
