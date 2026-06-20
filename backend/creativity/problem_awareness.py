"""问题意识激发器

按学科类型路由，针对人文社科与理工科分别激发问题意识，
帮助研究者从现实张力或工程痛点切入论题。
"""


def inspire_humanities_social(topic: str, context: str = "") -> dict:
    """针对人文社科激发问题意识。

    扫描社会热点与政策文件，匹配学科理论，寻找现实与理论的张力。

    Args:
        topic: 研究主题。
        context: 可选上下文信息。

    Returns:
        包含 discipline_type、problem、angle、prompt 字段的激发结果字典。
    """
    return {
        "discipline_type": "humanities_social",
        "problem": f"针对{topic}的现实与理论张力",
        "angle": "社会热点与政策文件匹配学科理论",
        "prompt": f"扫描{topic}相关的社会热点与政策文件，匹配学科理论，寻找现实与理论的张力",
    }


def inspire_science_engineering(topic: str, context: str = "") -> dict:
    """针对理工科激发问题意识。

    从工程应用背景出发，定位系统故障、算法精度、耗时等具体痛点。

    Args:
        topic: 研究主题。
        context: 可选上下文信息。

    Returns:
        包含 discipline_type、problem、angle、prompt 字段的激发结果字典。
    """
    return {
        "discipline_type": "science_engineering",
        "problem": f"针对{topic}的工程痛点",
        "angle": "系统故障/算法精度/耗时过长等具体痛点",
        "prompt": f"从{topic}的工程应用背景出发，定位系统故障多、算法精度不够、耗时过长等具体痛点",
    }


def inspire(discipline: str, topic: str, context: str = "") -> dict:
    """根据学科类型路由到对应的问题意识激发函数。

    Args:
        discipline: 学科类型，取值为 "humanities_social" 或 "science_engineering"。
        topic: 研究主题。
        context: 可选上下文信息。

    Returns:
        对应学科类型的激发结果字典。

    Raises:
        ValueError: 当 discipline 不在支持的学科类型中时抛出。
    """
    if discipline == "humanities_social":
        return inspire_humanities_social(topic, context)
    if discipline == "science_engineering":
        return inspire_science_engineering(topic, context)
    raise ValueError(f"不支持的学科类型：{discipline}")
