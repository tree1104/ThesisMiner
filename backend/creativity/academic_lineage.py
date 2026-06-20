"""学术谱系链接器

基于导师在研项目与同门师兄姐论文，生成可继承的子课题候选，
确保新论题在学术谱系内具备延续性与可行性。
"""


def extend_mentor_project(mentor_project: str, timeframe_years: int = 1) -> dict:
    """基于导师在研项目生成子课题候选。

    Args:
        mentor_project: 导师在研项目名称。
        timeframe_years: 预期完成年限，默认 1 年。

    Returns:
        包含 inspiration_source、direction、suggestion、prompt 字段的候选字典。
    """
    return {
        "inspiration_source": "mentor_project",
        "direction": f"基于《{mentor_project}》的子课题",
        "suggestion": f"聚焦于某个具体参数优化/流程改进，可在{timeframe_years}年内完成",
        "prompt": f"基于导师{mentor_project}的既定研究框架，设计一个能在{timeframe_years}年内完成的子课题",
    }


def inherit_senior_work(senior_thesis: str, adjacent_scenario: str = "") -> dict:
    """继承同门师兄姐论文的未走完之路。

    Args:
        senior_thesis: 同门师兄姐论文标题。
        adjacent_scenario: 相邻场景名称，可选。

    Returns:
        包含 inspiration_source、direction、suggestion、prompt 字段的候选字典。
    """
    scenario = adjacent_scenario or "相邻场景"
    return {
        "inspiration_source": "senior_inherit",
        "direction": f"继承《{senior_thesis}》的未走完之路",
        "suggestion": f"将其实验方法迁移至{scenario}，或引入新变量进行稳健性检验",
        "prompt": f"在{senior_thesis}的基础上，将其实验方法迁移至{scenario}",
    }


def generate_lineage_candidates(
    mentor_projects: list[str], senior_theses: list[str]
) -> list[dict]:
    """遍历导师项目与同门论文，生成谱系候选列表。

    Args:
        mentor_projects: 导师在研项目名称列表。
        senior_theses: 同门师兄姐论文标题列表。

    Returns:
        候选字典列表，每个元素为 extend_mentor_project 或 inherit_senior_work 的返回值。
    """
    candidates: list[dict] = []
    for project in mentor_projects:
        candidates.append(extend_mentor_project(project))
    for thesis in senior_theses:
        candidates.append(inherit_senior_work(thesis))
    return candidates
