"""混合检索模块（v9.0 Task 2.5）

融合 BM25 + FAISS + Qwen3Reranker 的端到端混合检索：
    1. BM25 召回稀疏匹配候选（top 3*top_k）
    2. FAISS 召回稠密语义候选（top 3*top_k）
    3. 合并去重，按权重融合分数
    4. （可选）Qwen3 重排序，输出最终 top_k

典型用法：
    hs = HybridSearch()
    hs.index([{"id": "1", "text": "..."}])
    results = hs.search("查询", top_k=5, rerank=True)
"""
from __future__ import annotations

import threading
from typing import Dict, List, Optional

from backend.retrieval.bm25_search import BM25Search
from backend.retrieval.embedding import EmbeddingEngine
from backend.retrieval.faiss_index import FAISSIndex
from backend.retrieval.reranker import Qwen3Reranker, DEFAULT_INSTRUCTION

try:
    from backend.utils.logger import get_logger

    _logger = get_logger(__name__)
except Exception:  # pragma: no cover
    import logging

    _logger = logging.getLogger(__name__)


class HybridSearch:
    """混合检索器（BM25 + FAISS + Reranker）。

    所有子组件均延迟加载，首次 index/search 时才触发模型加载。
    """

    def __init__(
        self,
        embedding_model_path: str = "all-MiniLM-L6-v2/all-MiniLM-L6-v2",
        reranker_model_path: str = "Qwen3-reranker-0.6B",
        device: str = "auto",
    ):
        """初始化混合检索器。

        Args:
            embedding_model_path: 嵌入模型路径。
            reranker_model_path: 重排序模型路径。
            device: 设备，"auto" 自动检测。
        """
        self._embedding = EmbeddingEngine(
            model_path=embedding_model_path, device=device
        )
        self._bm25 = BM25Search()
        self._faiss = FAISSIndex(dim=self._embedding.dimension)
        self._reranker = Qwen3Reranker(
            model_path=reranker_model_path, device=device
        )
        self._docs: Dict[str, str] = {}
        self._lock = threading.RLock()

    @property
    def embedding(self) -> EmbeddingEngine:
        return self._embedding

    @property
    def bm25(self) -> BM25Search:
        return self._bm25

    @property
    def faiss(self) -> FAISSIndex:
        return self._faiss

    @property
    def reranker(self) -> Qwen3Reranker:
        return self._reranker

    def index(self, documents: List[dict]) -> int:
        """索引文档到 BM25 与 FAISS。

        Args:
            documents: 文档列表，每个文档需含 "id" 与 "text" 字段。

        Returns:
            成功索引的文档数。
        """
        if not documents:
            return 0
        valid_docs: List[dict] = []
        for doc in documents:
            doc_id = str(doc.get("id", "")).strip()
            text = str(doc.get("text", ""))
            if not doc_id:
                continue
            valid_docs.append({"id": doc_id, "text": text})
        if not valid_docs:
            return 0
        # BM25 索引
        self._bm25.add_documents(valid_docs)
        # FAISS 索引（嵌入）
        texts = [d["text"] for d in valid_docs]
        ids = [d["id"] for d in valid_docs]
        embeddings = self._embedding.encode(texts)
        added = 0
        if embeddings.shape[0] == len(valid_docs):
            added = self._faiss.add(embeddings, ids)
        else:
            # 嵌入失败，回填 0
            added = 0
        with self._lock:
            for d in valid_docs:
                self._docs[d["id"]] = d["text"]
        _logger.info(
            "HybridSearch.index: 输入 %d, BM25 %d, FAISS %d",
            len(valid_docs),
            self._bm25.size(),
            self._faiss.size(),
        )
        # 返回 BM25 索引数（更稳定，因为 FAISS 可能因模型未加载而失败）
        return len(valid_docs)

    def search(
        self,
        query: str,
        top_k: int = 10,
        bm25_weight: float = 0.3,
        faiss_weight: float = 0.7,
        rerank: bool = True,
        instruction: str = DEFAULT_INSTRUCTION,
    ) -> List[dict]:
        """混合检索。

        Args:
            query: 查询字符串。
            top_k: 返回结果数。
            bm25_weight: BM25 分数权重。
            faiss_weight: FAISS 分数权重。
            rerank: 是否启用 Qwen3 重排序。
            instruction: 重排序任务描述。

        Returns:
            结果列表，每项含 id/text/score/source 字段，按分数降序。
        """
        if not query or top_k <= 0:
            return []
        candidate_k = max(top_k * 3, 10)

        # 1. BM25 召回
        bm25_results = self._bm25.search(query, top_k=candidate_k)

        # 2. FAISS 召回
        faiss_results: List[dict] = []
        query_vec = self._embedding.encode_one(query)
        if query_vec.any():
            faiss_results = self._faiss.search(query_vec, top_k=candidate_k)

        # 3. 分数归一化与融合
        bm25_scores = {r["id"]: r["score"] for r in bm25_results}
        faiss_scores = {r["id"]: r["score"] for r in faiss_results}
        all_ids = set(bm25_scores.keys()) | set(faiss_scores.keys())

        # 归一化（min-max 到 [0,1]）
        norm_bm25 = self._min_max_norm(bm25_scores)
        norm_faiss = self._min_max_norm(faiss_scores)

        merged: List[dict] = []
        for doc_id in all_ids:
            score_bm25 = norm_bm25.get(doc_id, 0.0) * bm25_weight
            score_faiss = norm_faiss.get(doc_id, 0.0) * faiss_weight
            total = score_bm25 + score_faiss
            sources = []
            if doc_id in bm25_scores:
                sources.append("bm25")
            if doc_id in faiss_scores:
                sources.append("faiss")
            source = "hybrid" if len(sources) > 1 else (sources[0] if sources else "hybrid")
            merged.append(
                {
                    "id": doc_id,
                    "text": self._docs.get(doc_id, ""),
                    "score": float(total),
                    "source": source,
                    "bm25_score": float(bm25_scores.get(doc_id, 0.0)),
                    "faiss_score": float(faiss_scores.get(doc_id, 0.0)),
                }
            )
        merged.sort(key=lambda x: x["score"], reverse=True)
        # 取前 candidate_k 进入重排序
        candidates = merged[:candidate_k]

        if not candidates:
            return []

        # 4. 重排序
        if rerank and self._reranker._ensure_loaded():
            docs_text = [c["text"] for c in candidates]
            rerank_results = self._reranker.rerank(
                query, docs_text, top_k=len(candidates), instruction=instruction
            )
            # 用 rerank 分数覆盖
            id_to_rerank: Dict[str, float] = {}
            for r in rerank_results:
                idx = r["index"]
                if 0 <= idx < len(candidates):
                    id_to_rerank[candidates[idx]["id"]] = r["score"]
            for c in candidates:
                if c["id"] in id_to_rerank:
                    c["score"] = float(id_to_rerank[c["id"]])
                    c["source"] = "rerank"
            candidates.sort(key=lambda x: x["score"], reverse=True)

        return candidates[:top_k]

    @staticmethod
    def _min_max_norm(scores: Dict[str, float]) -> Dict[str, float]:
        """min-max 归一化到 [0, 1]。"""
        if not scores:
            return {}
        vals = list(scores.values())
        lo = min(vals)
        hi = max(vals)
        if hi - lo < 1e-9:
            # 全部相同：等值映射为 1.0（若 > 0）或 0.0
            base = 1.0 if hi > 0 else 0.0
            return {k: base for k in scores}
        return {k: (v - lo) / (hi - lo) for k, v in scores.items()}

    def get_status(self) -> dict:
        """返回混合检索器状态。"""
        with self._lock:
            doc_count = len(self._docs)
        return {
            "embedding": self._embedding.get_status(),
            "bm25": self._bm25.get_status(),
            "faiss": self._faiss.get_status(),
            "reranker": self._reranker.get_status(),
            "doc_count": doc_count,
        }


# ===== 全局单例 =====

_global_instance: Optional[HybridSearch] = None
_global_lock = threading.Lock()


def get_hybrid_search() -> HybridSearch:
    """获取全局 HybridSearch 单例。"""
    global _global_instance
    if _global_instance is None:
        with _global_lock:
            if _global_instance is None:
                _global_instance = HybridSearch()
    return _global_instance


def reset_hybrid_search() -> None:
    """重置全局单例（主要用于测试）。"""
    global _global_instance
    with _global_lock:
        _global_instance = None
