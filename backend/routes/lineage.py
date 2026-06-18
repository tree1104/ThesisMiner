"""谱系管理路由模块

提供谱系节点/边的查询、导入、搜索、删除及知识卡片管理接口。
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.knowledge import card_manager, lineage_graph_store
from backend.models import ApiResponse, LineageImportRequest

router = APIRouter(prefix="/api/lineage", tags=["lineage"])


class CardCreate(BaseModel):
    """知识卡片创建请求。"""

    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    source: str = ""


@router.get("")
def list_nodes():
    """列出所有谱系节点。"""
    try:
        nodes = lineage_graph_store.get_all_nodes()
        return {"nodes": nodes, "count": len(nodes)}
    except Exception as e:
        return ApiResponse(success=False, error=str(e))


@router.post("/import")
def import_lineage(payload: LineageImportRequest):
    """批量导入谱系节点与边。"""
    try:
        imported_nodes = 0
        imported_edges = 0
        # 遍历节点列表，逐个新增
        for node in payload.nodes:
            lineage_graph_store.add_node(
                node_type=node.get("node_type", ""),
                title=node.get("title", ""),
                abstract=node.get("abstract", ""),
                metadata=node.get("metadata", {}),
            )
            imported_nodes += 1
        # 遍历边列表，逐个新增
        for edge in payload.edges:
            lineage_graph_store.add_edge(
                source_id=edge.get("source_id", ""),
                target_id=edge.get("target_id", ""),
                relation_type=edge.get("relation_type", ""),
                weight=edge.get("weight", 1.0),
            )
            imported_edges += 1
        return {"imported_nodes": imported_nodes, "imported_edges": imported_edges}
    except Exception as e:
        return ApiResponse(success=False, error=str(e))


@router.get("/graph")
def get_graph():
    """获取完整图谱（节点与边）。"""
    try:
        graph = lineage_graph_store.get_graph()
        return {"nodes": graph.get("nodes", []), "edges": graph.get("edges", [])}
    except Exception as e:
        return ApiResponse(success=False, error=str(e))


@router.get("/search")
def search_nodes(keyword: str):
    """按关键词模糊搜索节点。"""
    try:
        results = lineage_graph_store.search_nodes(keyword)
        return {"results": results, "count": len(results)}
    except Exception as e:
        return ApiResponse(success=False, error=str(e))


@router.delete("/{node_id}")
def delete_node(node_id: str):
    """删除指定节点及其关联边。"""
    try:
        lineage_graph_store.delete_node(node_id)
        return ApiResponse(success=True, message="节点已删除")
    except Exception as e:
        return ApiResponse(success=False, error=str(e))


@router.post("/cards")
def add_card(payload: CardCreate):
    """新增知识卡片。"""
    try:
        card_id = card_manager.add_card(
            title=payload.title,
            content=payload.content,
            tags=payload.tags,
            source=payload.source,
        )
        return {"card_id": card_id}
    except Exception as e:
        return ApiResponse(success=False, error=str(e))


@router.get("/cards")
def list_cards(tag: str | None = None):
    """列出知识卡片，可选按标签过滤。"""
    try:
        cards = card_manager.list_cards(tag)
        return {"cards": cards, "count": len(cards)}
    except Exception as e:
        return ApiResponse(success=False, error=str(e))
