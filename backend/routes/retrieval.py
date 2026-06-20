"""本地混合检索路由模块（v9.0 Task 2.6）

提供文档索引、混合检索与状态查询接口：
    - POST /api/retrieval/index: 索引文档
    - POST /api/retrieval/search: 混合检索
    - GET  /api/retrieval/status: 查询状态
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.retrieval.hybrid_search import get_hybrid_search

router = APIRouter(prefix="/api/retrieval", tags=["retrieval"])


class RetrievalDocument(BaseModel):
    """待索引文档。"""

    id: str
    text: str


class IndexRequest(BaseModel):
    """索引请求。"""

    documents: list[RetrievalDocument] = Field(default_factory=list)


class SearchRequest(BaseModel):
    """检索请求。"""

    query: str
    top_k: int = 10
    bm25_weight: float = 0.3
    faiss_weight: float = 0.7
    rerank: bool = True
    instruction: str | None = None


@router.post("/index")
async def index_documents(req: IndexRequest) -> dict:
    """索引文档到 BM25 + FAISS。"""
    try:
        hs = get_hybrid_search()
        docs = [{"id": d.id, "text": d.text} for d in req.documents]
        added = hs.index(docs)
        return {
            "success": True,
            "indexed": added,
            "total_docs": hs.get_status().get("doc_count", 0),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/search")
async def search(req: SearchRequest) -> dict:
    """混合检索。"""
    try:
        hs = get_hybrid_search()
        from backend.retrieval.reranker import DEFAULT_INSTRUCTION

        instruction = req.instruction or DEFAULT_INSTRUCTION
        results = hs.search(
            query=req.query,
            top_k=req.top_k,
            bm25_weight=req.bm25_weight,
            faiss_weight=req.faiss_weight,
            rerank=req.rerank,
            instruction=instruction,
        )
        return {"success": True, "results": results, "count": len(results)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/status")
async def status() -> dict:
    """返回检索系统状态。"""
    try:
        hs = get_hybrid_search()
        return {"success": True, "status": hs.get_status()}
    except Exception as e:
        return {"success": False, "error": str(e)}
