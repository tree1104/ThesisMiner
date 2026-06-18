"""前置检索钩子

在创意发散阶段，整合学术谱系、问题意识与跨域联想，
为后续精炼流程提供候选集合。
"""


def _parse_mentor_info(mentor_info: str) -> tuple[list[str], list[str]]:
    """解析导师信息，分离导师项目与同门论文。

    解析规则：
        - 以换行分隔多条信息。
        - 显式前缀："项目:"/"导师项目:" 归为导师项目；"论文:"/"同门:" 归为同门论文。
        - 无前缀时，含"论文"或以"《"开头的行归为同门论文，其余归为导师项目。

    Args:
        mentor_info: 导师信息原始字符串。

    Returns:
        二元组 (mentor_projects, senior_theses)。
    """
    mentor_projects: list[str] = []
    senior_theses: list[str] = []

    if not mentor_info:
        return mentor_projects, senior_theses

    for line in mentor_info.splitlines():
        line = line.strip()
        if not line:
            continue

        lower_line = line.lower()

        # 显式前缀识别：导师项目
        if lower_line.startswith(("项目:", "导师项目:", "项目：", "导师项目：")):
            for prefix in ("导师项目:", "导师项目：", "项目:", "项目："):
                if lower_line.startswith(prefix):
                    content = line[len(prefix):].strip()
                    break
            mentor_projects.append(content)
            continue

        # 显式前缀识别：同门论文
        if lower_line.startswith(("论文:", "同门:", "论文：", "同门：")):
            for prefix in ("同门:", "同门：", "论文:", "论文："):
                if lower_line.startswith(prefix):
                    content = line[len(prefix):].strip()
                    break
            senior_theses.append(content)
            continue

        # 无前缀启发式判断：含"论文"或以"《"开头视为同门论文
        if line.startswith("《") or "论文" in line:
            senior_theses.append(line)
        else:
            mentor_projects.append(line)

    return mentor_projects, senior_theses


def run(degree: str, discipline: str, mentor_info: str, context: str = "") -> dict:
    """前置检索钩子入口。

    依次调用学术谱系、问题意识、跨域联想模块生成候选集合。

    Args:
        degree: 学位类型，取值为 "master" 或 "doctor"。
        discipline: 学科类型，取值为 "humanities_social" 或 "science_engineering"。
        mentor_info: 导师信息，可能包含导师项目与同门论文，用换行分隔。
        context: 可选上下文信息。

    Returns:
        包含以下字段的字典：
        - candidates: 候选列表。
        - problem_awareness: 问题意识激发结果。
        - context_enriched: 富化后的上下文。
    """
    # 延迟导入避免循环依赖
    from backend.creativity import academic_lineage, problem_awareness, cross_domain

    # 解析导师信息，分离导师项目与同门论文
    mentor_projects, senior_theses = _parse_mentor_info(mentor_info)

    # 调用学术谱系链接器生成谱系候选
    candidates = academic_lineage.generate_lineage_candidates(
        mentor_projects, senior_theses
    )

    # 激发问题意识：以第一个项目或论文作为主题，缺省时回退到学科类型
    all_topics = mentor_projects + senior_theses
    topic = all_topics[0] if all_topics else discipline
    problem_awareness_result = problem_awareness.inspire(discipline, topic, context)

    # 跨域联想：若 mentor_info 含多个领域（多个不同主题），进行方法嫁接
    if len(all_topics) >= 2:
        cross_candidate = cross_domain.cross_domain_association(
            all_topics[0], all_topics[1]
        )
        candidates.append(cross_candidate)

    # 富化上下文：将解析出的主题拼入上下文
    context_enriched = context
    if all_topics:
        context_enriched = f"{context}\n相关主题：{', '.join(all_topics)}".strip()

    return {
        "candidates": candidates,
        "problem_awareness": problem_awareness_result,
        "context_enriched": context_enriched,
    }
