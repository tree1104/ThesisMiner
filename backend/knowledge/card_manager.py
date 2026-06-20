"""知识卡片管理模块

基于 SQLite 的 knowledge_cards 表，提供知识卡片的增删查改能力，
tags 字段在存储时序列化、读取时反序列化。
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


def _deserialize_tags(raw: str | None) -> list[str]:
    """将 tags 字段的 JSON 字符串反序列化为列表。

    Args:
        raw: tags 字段的原始字符串值，可能为 None 或非法 JSON。

    Returns:
        反序列化后的标签列表；若为空或非法则返回空列表。
    """
    if not raw:
        return []
    try:
        result = json.loads(raw)
        if isinstance(result, list):
            return result
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def add_card(title: str, content: str, tags: list[str] = None, source: str = "") -> str:
    """新增一张知识卡片。

    Args:
        title: 卡片标题。
        content: 卡片正文内容。
        tags: 标签列表，默认 None（存储为空列表）。
        source: 来源信息，默认空字符串。

    Returns:
        新增卡片的 card_id。
    """
    card_id = _new_id()
    execute_insert(
        "knowledge_cards",
        {
            "id": card_id,
            "title": title,
            "content": content,
            "tags": tags if tags is not None else [],
            "source": source,
            "created_at": _now_iso(),
        },
    )
    return card_id


def get_card(card_id: str) -> dict | None:
    """根据 ID 查询知识卡片。

    Args:
        card_id: 卡片 ID。

    Returns:
        卡片字典（tags 已反序列化）；若不存在则返回 None。
    """
    row = fetch_one("SELECT * FROM knowledge_cards WHERE id = ?;", (card_id,))
    if row is None:
        return None
    row["tags"] = _deserialize_tags(row.get("tags"))
    return row


def list_cards(tag: str = None) -> list[dict]:
    """列出所有知识卡片，可选按标签过滤。

    Args:
        tag: 可选标签字符串，提供时仅返回包含该标签的卡片。

    Returns:
        卡片字典列表，tags 已反序列化。
    """
    if tag:
        # tags 以 JSON 数组形式存储，使用 LIKE 进行模糊匹配
        rows = fetch_all(
            "SELECT * FROM knowledge_cards WHERE tags LIKE ? ORDER BY created_at DESC;",
            (f'%"{tag}"%',),
        )
    else:
        rows = fetch_all(
            "SELECT * FROM knowledge_cards ORDER BY created_at DESC;"
        )

    cards: list[dict] = []
    for row in rows:
        row["tags"] = _deserialize_tags(row.get("tags"))
        cards.append(row)
    return cards


def delete_card(card_id: str) -> int:
    """删除指定知识卡片。

    Args:
        card_id: 待删除卡片的 ID。

    Returns:
        删除的行数（0 或 1）。
    """
    return execute_query("DELETE FROM knowledge_cards WHERE id = ?;", (card_id,))


def search_cards(keyword: str) -> list[dict]:
    """按关键词模糊查询知识卡片（匹配标题或正文）。

    Args:
        keyword: 查询关键词。

    Returns:
        匹配的卡片字典列表，tags 已反序列化。
    """
    rows = fetch_all(
        "SELECT * FROM knowledge_cards WHERE title LIKE ? OR content LIKE ? "
        "ORDER BY created_at DESC;",
        (f"%{keyword}%", f"%{keyword}%",),
    )
    cards: list[dict] = []
    for row in rows:
        row["tags"] = _deserialize_tags(row.get("tags"))
        cards.append(row)
    return cards
