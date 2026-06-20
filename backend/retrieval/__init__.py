"""本地混合检索模块（v9.0 Task 2）

提供基于本地模型的混合检索能力，包含：
    - EmbeddingEngine: 基于 all-MiniLM-L6-v2 的稠密向量嵌入
    - BM25Search: 基于 rank_bm25 的稀疏关键词检索
    - FAISSIndex: 基于 faiss-cpu 的向量索引
    - Qwen3Reranker: 基于 Qwen3-reranker-0.6B 的重排序
    - HybridSearch: 融合 BM25 + FAISS + Reranker 的混合检索

所有模型均采用延迟加载（首次使用时加载），避免启动缓慢。
"""
from backend.retrieval.embedding import EmbeddingEngine
from backend.retrieval.bm25_search import BM25Search
from backend.retrieval.faiss_index import FAISSIndex
from backend.retrieval.reranker import Qwen3Reranker
from backend.retrieval.hybrid_search import HybridSearch

__all__ = [
    "EmbeddingEngine",
    "BM25Search",
    "FAISSIndex",
    "Qwen3Reranker",
    "HybridSearch",
]
