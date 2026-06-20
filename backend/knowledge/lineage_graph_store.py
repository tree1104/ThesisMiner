"""谱系图存储模块

基于 SQLite 的 lineage_nodes 与 lineage_edges 表，提供学脉图谱的
节点与边 CRUD 能力，metadata 字段在存储时序列化、读取时反序列化。
"""
import json
import uuid
from datetime import datetime

from backend.database import (
    execute_insert,
    execute_query,
    fetch_all,
    fetch_one,
)


def _now_iso() -> str:
    """返回当前时间的 ISO 格式字符串。"""
    return datetime.now().isoformat()


def _new_id() -> str:
    """生成新的唯一 ID。"""
    return uuid.uuid4().hex


def _deserialize_metadata(raw: str | None) -> dict:
    """将 metadata 字段的 JSON 字符串反序列化为字典。

    Args:
        raw: metadata 字段的原始字符串值，可能为 None 或非法 JSON。

    Returns:
        反序列化后的字典；若为空或非法则返回空字典。
    """
    if not raw:
        return {}
    try:
        result = json.loads(raw)
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, TypeError):
        pass
    return {}


def add_node(node_type: str, title: str, abstract: str = "", metadata: dict = None) -> str:
    """新增一个谱系节点。

    Args:
        node_type: 节点类型（如 paper、topic、method 等）。
        title: 节点标题。
        abstract: 节点摘要，默认空字符串。
        metadata: 节点元数据字典，默认 None（存储为空字典）。

    Returns:
        新增节点的 node_id。
    """
    node_id = _new_id()
    execute_insert(
        "lineage_nodes",
        {
            "id": node_id,
            "node_type": node_type,
            "title": title,
            "abstract": abstract,
            "metadata": metadata if metadata is not None else {},
            "created_at": _now_iso(),
        },
    )
    return node_id


def add_edge(
    source_id: str, target_id: str, relation_type: str, weight: float = 1.0
) -> str:
    """新增一条谱系边。

    Args:
        source_id: 起始节点 ID。
        target_id: 目标节点 ID。
        relation_type: 关系类型（如 extends、cites、derives_from 等）。
        weight: 关系权重，默认 1.0。

    Returns:
        新增边的 edge_id。
    """
    edge_id = _new_id()
    execute_insert(
        "lineage_edges",
        {
            "id": edge_id,
            "source_id": source_id,
            "target_id": target_id,
            "relation_type": relation_type,
            "weight": weight,
            "created_at": _now_iso(),
        },
    )
    return edge_id


def get_all_nodes() -> list[dict]:
    """查询所有谱系节点。

    Returns:
        节点字典列表，metadata 字段已反序列化为字典。
    """
    rows = fetch_all("SELECT * FROM lineage_nodes ORDER BY created_at DESC;")
    nodes: list[dict] = []
    for row in rows:
        row["metadata"] = _deserialize_metadata(row.get("metadata"))
        nodes.append(row)
    return nodes


def get_all_edges() -> list[dict]:
    """查询所有谱系边。

    Returns:
        边字典列表。
    """
    return fetch_all("SELECT * FROM lineage_edges ORDER BY created_at DESC;")


def get_graph() -> dict:
    """返回完整图谱（节点与边）。

    Returns:
        包含 nodes 与 edges 两个列表的字典。
    """
    return {"nodes": get_all_nodes(), "edges": get_all_edges()}


def delete_node(node_id: str) -> int:
    """删除指定节点及其关联的所有边。

    Args:
        node_id: 待删除节点的 ID。

    Returns:
        删除的节点行数（0 或 1）。
    """
    # 先删除关联边（作为 source 或 target）
    execute_query(
        "DELETE FROM lineage_edges WHERE source_id = ? OR target_id = ?;",
        (node_id, node_id),
    )
    # 再删除节点本身
    return execute_query("DELETE FROM lineage_nodes WHERE id = ?;", (node_id,))


def search_nodes(keyword: str) -> list[dict]:
    """按标题模糊查询节点。

    Args:
        keyword: 查询关键词。

    Returns:
        标题包含关键词的节点字典列表，metadata 字段已反序列化。
    """
    rows = fetch_all(
        "SELECT * FROM lineage_nodes WHERE title LIKE ? ORDER BY created_at DESC;",
        (f"%{keyword}%",),
    )
    nodes: list[dict] = []
    for row in rows:
        row["metadata"] = _deserialize_metadata(row.get("metadata"))
        nodes.append(row)
    return nodes
