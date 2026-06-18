"""图谱扩展模块

从论文文本中抽取实体与关系，生成可入库的节点与边建议，
辅助构建学脉知识图谱。
"""
import re

# 关系触发词：句子中包含这些词时，认为存在实体间关系
_RELATION_TRIGGERS = ["基于", "通过", "使用"]


def extract_entities_from_text(text: str) -> list[dict]:
    """从文本中抽取实体关系三元组。

    简单实现：按句号分割文本，提取包含"基于"、"通过"、"使用"等触发词的句子，
    将触发词前后的片段作为实体与目标，构造关系三元组。

    Args:
        text: 待抽取的文本（如论文摘要）。

    Returns:
        关系三元组字典列表，每个元素包含 entity、relation、target 字段。
    """
    if not text:
        return []

    # 按中文句号、英文句号、换行符分割
    sentences = re.split(r"[。.\n]+", text)
    triples: list[dict] = []

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        for trigger in _RELATION_TRIGGERS:
            idx = sentence.find(trigger)
            if idx == -1:
                continue

            # 触发词之前作为实体，之后作为目标
            entity = sentence[:idx].strip()
            target = sentence[idx + len(trigger):].strip()

            # 过滤过短或无意义的片段
            if not entity or not target:
                continue
            if len(entity) < 2 or len(target) < 2:
                continue

            triples.append(
                {
                    "entity": entity,
                    "relation": trigger,
                    "target": target,
                }
            )

    return triples


def expand_from_paper(title: str, abstract: str) -> dict:
    """从论文标题与摘要扩展图谱节点与边建议。

    Args:
        title: 论文标题。
        abstract: 论文摘要。

    Returns:
        包含以下字段的字典：
        - paper_title: 论文标题。
        - entities: 抽取的实体关系三元组列表。
        - suggested_nodes: 建议新增的节点列表。
        - suggested_edges: 建议新增的边列表。
    """
    entities = extract_entities_from_text(abstract)

    # 建议节点：论文本身 + 各实体
    suggested_nodes: list[dict] = [
        {"node_type": "paper", "title": title, "abstract": abstract}
    ]
    seen_titles: set[str] = {title}
    for triple in entities:
        for entity_title in (triple["entity"], triple["target"]):
            if entity_title and entity_title not in seen_titles:
                suggested_nodes.append(
                    {"node_type": "concept", "title": entity_title, "abstract": ""}
                )
                seen_titles.add(entity_title)

    # 建议边：论文 → 实体（涉及），实体 → 目标（关系）
    suggested_edges: list[dict] = []
    for triple in entities:
        suggested_edges.append(
            {
                "source_title": title,
                "target_title": triple["entity"],
                "relation_type": "involves",
                "weight": 1.0,
            }
        )
        suggested_edges.append(
            {
                "source_title": triple["entity"],
                "target_title": triple["target"],
                "relation_type": triple["relation"],
                "weight": 1.0,
            }
        )

    return {
        "paper_title": title,
        "entities": entities,
        "suggested_nodes": suggested_nodes,
        "suggested_edges": suggested_edges,
    }
