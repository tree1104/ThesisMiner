"""本地混合检索单元测试（v9.0 Task 2.7）

覆盖范围：
    - EmbeddingEngine: 单条/批量编码、维度=384、L2 归一化
    - BM25Search: 索引、检索、相关性
    - FAISSIndex: 增删、检索、save/load
    - Qwen3Reranker: 重排序分数在 [0,1]
    - HybridSearch: 端到端检索
    - 路由: /api/retrieval/* 端到端

运行方式：
    venv\\Scripts\\python.exe -m pytest tests/unit/test_retrieval.py -v
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pytest

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.retrieval.bm25_search import BM25Search, tokenize
from backend.retrieval.embedding import EmbeddingEngine, DEFAULT_DIMENSION
from backend.retrieval.faiss_index import FAISSIndex
from backend.retrieval.hybrid_search import HybridSearch, reset_hybrid_search
from backend.retrieval.reranker import Qwen3Reranker


# ===== 测试样本（中文学术论文标题/摘要） =====

SAMPLE_DOCUMENTS = [
    {
        "id": "doc1",
        "text": "深度学习在自然语言处理中的应用研究：以 Transformer 为例",
    },
    {
        "id": "doc2",
        "text": "基于图神经网络的社交网络社区发现算法",
    },
    {
        "id": "doc3",
        "text": "强化学习在机器人路径规划中的应用",
    },
    {
        "id": "doc4",
        "text": "面向中文文本的情感分析方法研究",
    },
    {
        "id": "doc5",
        "text": "大规模预训练语言模型 BERT 与 GPT 的对比分析",
    },
    {
        "id": "doc6",
        "text": "计算机视觉中的目标检测算法综述",
    },
    {
        "id": "doc7",
        "text": "区块链技术在供应链金融中的应用研究",
    },
    {
        "id": "doc8",
        "text": "基于 Transformer 的中英机器翻译系统设计与实现",
    },
]


# ===== EmbeddingEngine 测试 =====


class TestEmbeddingEngine:
    """嵌入引擎测试。"""

    def test_encode_single_text(self):
        """单条文本编码：返回 384 维 L2 归一化向量。"""
        engine = EmbeddingEngine()
        vec = engine.encode_one("深度学习在 NLP 中的应用")
        assert isinstance(vec, np.ndarray)
        assert vec.shape == (DEFAULT_DIMENSION,)
        assert vec.dtype == np.float32
        # L2 归一化后范数应接近 1
        norm = float(np.linalg.norm(vec))
        assert 0.9 <= norm <= 1.1, f"范数不在合理范围: {norm}"

    def test_encode_batch(self):
        """批量编码：返回 (n, 384) 矩阵。"""
        engine = EmbeddingEngine()
        texts = ["深度学习", "自然语言处理", "计算机视觉"]
        mat = engine.encode(texts)
        assert isinstance(mat, np.ndarray)
        assert mat.shape == (3, DEFAULT_DIMENSION)
        assert mat.dtype == np.float32
        # 每行 L2 归一化
        norms = np.linalg.norm(mat, axis=1)
        for n in norms:
            assert 0.9 <= float(n) <= 1.1

    def test_embedding_dimension(self):
        """嵌入维度应为 384。"""
        engine = EmbeddingEngine()
        # 触发加载以更新真实维度
        engine.encode_one("test")
        assert engine.dimension == DEFAULT_DIMENSION

    def test_empty_text(self):
        """空文本返回零向量。"""
        engine = EmbeddingEngine()
        vec = engine.encode_one("")
        assert vec.shape == (DEFAULT_DIMENSION,)
        assert float(np.linalg.norm(vec)) == 0.0

    def test_empty_batch(self):
        """空批量返回 (0, dim) 数组。"""
        engine = EmbeddingEngine()
        mat = engine.encode([])
        assert mat.shape == (0, DEFAULT_DIMENSION)

    def test_status(self):
        """get_status 返回完整字段。"""
        engine = EmbeddingEngine()
        status = engine.get_status()
        assert "model_path" in status
        assert "device" in status
        assert "dimension" in status
        assert "loaded" in status


# ===== BM25Search 测试 =====


class TestBM25Search:
    """BM25 检索测试。"""

    def test_tokenize_chinese(self):
        """中文分词应返回非空 token 列表。"""
        tokens = tokenize("深度学习在自然语言处理中的应用")
        assert len(tokens) > 0

    def test_tokenize_english(self):
        """英文分词应小写化。"""
        tokens = tokenize("Deep Learning for NLP")
        assert "deep" in tokens
        assert "learning" in tokens

    def test_tokenize_empty(self):
        """空文本返回空列表。"""
        assert tokenize("") == []

    def test_index_and_search(self):
        """索引后能检索到相关文档。"""
        bm25 = BM25Search()
        bm25.index(SAMPLE_DOCUMENTS)
        assert bm25.size() == len(SAMPLE_DOCUMENTS)
        results = bm25.search("Transformer 机器翻译", top_k=3)
        assert len(results) <= 3
        assert len(results) > 0
        # doc8 应排在前列（Transformer 机器翻译）
        top_ids = [r["id"] for r in results]
        assert "doc8" in top_ids

    def test_search_relevance(self):
        """相关查询返回相关文档。"""
        bm25 = BM25Search()
        bm25.index(SAMPLE_DOCUMENTS)
        results = bm25.search("区块链 金融", top_k=2)
        assert len(results) > 0
        # doc7（区块链供应链金融）应在结果中
        ids = [r["id"] for r in results]
        assert "doc7" in ids

    def test_add_documents_incremental(self):
        """增量添加文档。"""
        bm25 = BM25Search()
        bm25.add_documents(SAMPLE_DOCUMENTS[:3])
        assert bm25.size() == 3
        bm25.add_documents(SAMPLE_DOCUMENTS[3:])
        assert bm25.size() == len(SAMPLE_DOCUMENTS)

    def test_search_empty_query(self):
        """空查询返回空列表。"""
        bm25 = BM25Search()
        bm25.index(SAMPLE_DOCUMENTS)
        assert bm25.search("", top_k=5) == []

    def test_search_no_index(self):
        """未索引时检索返回空。"""
        bm25 = BM25Search()
        assert bm25.search("test", top_k=5) == []

    def test_result_fields(self):
        """结果字段完整。"""
        bm25 = BM25Search()
        bm25.index(SAMPLE_DOCUMENTS)
        results = bm25.search("深度学习", top_k=2)
        for r in results:
            assert "id" in r
            assert "text" in r
            assert "score" in r
            assert "source" in r
            assert r["source"] == "bm25"

    def test_status(self):
        """状态字段完整。"""
        bm25 = BM25Search()
        bm25.index(SAMPLE_DOCUMENTS)
        status = bm25.get_status()
        assert "doc_count" in status
        assert "tokenizer" in status
        assert "ready" in status
        assert status["doc_count"] == len(SAMPLE_DOCUMENTS)


# ===== FAISSIndex 测试 =====


class TestFAISSIndex:
    """FAISS 索引测试。"""

    def test_add_and_search(self):
        """添加向量后能检索到最近邻。"""
        index = FAISSIndex(dim=8)
        # 构造 5 个 8 维单位向量
        rng = np.random.default_rng(42)
        embeddings = rng.standard_normal((5, 8)).astype(np.float32)
        # L2 归一化
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = embeddings / np.clip(norms, 1e-9, None)
        ids = [f"doc{i}" for i in range(5)]
        added = index.add(embeddings, ids)
        assert added == 5
        assert index.size() == 5
        # 用第 0 个向量查询，应能找到自己
        results = index.search(embeddings[0], top_k=1)
        assert len(results) == 1
        assert results[0]["id"] == "doc0"
        # 内积应接近 1（自身）
        assert results[0]["score"] > 0.99

    def test_search_top_k(self):
        """top_k 截断。"""
        index = FAISSIndex(dim=4)
        embeddings = np.eye(4, dtype=np.float32)
        ids = [f"a{i}" for i in range(4)]
        index.add(embeddings, ids)
        results = index.search(embeddings[0], top_k=2)
        assert len(results) == 2
        # 第一个应是自己
        assert results[0]["id"] == "a0"

    def test_search_empty(self):
        """空索引检索返回空。"""
        index = FAISSIndex(dim=4)
        q = np.zeros(4, dtype=np.float32)
        assert index.search(q, top_k=5) == []

    def test_dimension_mismatch(self):
        """维度不匹配时返回 0。"""
        index = FAISSIndex(dim=8)
        bad = np.zeros((2, 4), dtype=np.float32)
        assert index.add(bad, ["x", "y"]) == 0

    def test_save_and_load(self, tmp_path):
        """save/load 持久化。"""
        index = FAISSIndex(dim=4)
        embeddings = np.eye(4, dtype=np.float32)
        ids = [f"d{i}" for i in range(4)]
        index.add(embeddings, ids)
        path = str(tmp_path / "test.index")
        assert index.save(path) is True
        # 加载到新实例
        index2 = FAISSIndex(dim=4)
        assert index2.load(path) is True
        assert index2.size() == 4
        results = index2.search(embeddings[0], top_k=1)
        assert len(results) == 1
        assert results[0]["id"] == "d0"

    def test_status(self):
        """状态字段完整。"""
        index = FAISSIndex(dim=4)
        status = index.get_status()
        assert "dim" in status
        assert "size" in status
        assert "ready" in status


# ===== Qwen3Reranker 测试 =====


class TestQwen3Reranker:
    """Qwen3 重排序测试。"""

    def test_rerank_scores_in_range(self):
        """重排序分数应在 [0, 1]。"""
        reranker = Qwen3Reranker()
        query = "深度学习在自然语言处理中的应用"
        docs = [
            "深度学习在自然语言处理中的应用研究",
            "区块链技术在金融领域的探索",
            "图神经网络在社交网络中的应用",
        ]
        results = reranker.rerank(query, docs, top_k=3)
        assert len(results) == 3
        for r in results:
            assert "index" in r
            assert "text" in r
            assert "score" in r
            assert 0.0 <= r["score"] <= 1.0, f"分数越界: {r['score']}"

    def test_rerank_relevance(self):
        """相关文档应排在前面。"""
        reranker = Qwen3Reranker()
        query = "Transformer 机器翻译"
        docs = [
            "区块链在金融中的应用",
            "基于 Transformer 的中英机器翻译系统",
            "图神经网络社区发现",
        ]
        results = reranker.rerank(query, docs, top_k=3)
        # 最相关的应是 index=1
        assert results[0]["index"] == 1

    def test_rerank_empty(self):
        """空输入返回空。"""
        reranker = Qwen3Reranker()
        assert reranker.rerank("query", [], top_k=5) == []
        assert reranker.rerank("", ["a"], top_k=5) == []

    def test_rerank_top_k(self):
        """top_k 截断。"""
        reranker = Qwen3Reranker()
        docs = ["文档一", "文档二", "文档三"]
        results = reranker.rerank("测试", docs, top_k=2)
        assert len(results) == 2

    def test_status(self):
        """状态字段完整。"""
        reranker = Qwen3Reranker()
        status = reranker.get_status()
        assert "model_path" in status
        assert "device" in status
        assert "loaded" in status


# ===== HybridSearch 测试 =====


class TestHybridSearch:
    """混合检索测试。"""

    def test_index_and_search(self):
        """端到端索引与检索。"""
        hs = HybridSearch()
        added = hs.index(SAMPLE_DOCUMENTS)
        assert added == len(SAMPLE_DOCUMENTS)
        results = hs.search(
            "Transformer 机器翻译", top_k=3, bm25_weight=0.3, faiss_weight=0.7,
            rerank=False,
        )
        assert len(results) <= 3
        assert len(results) > 0
        for r in results:
            assert "id" in r
            assert "text" in r
            assert "score" in r
            assert "source" in r

    def test_search_with_rerank(self):
        """启用重排序的检索。"""
        hs = HybridSearch()
        hs.index(SAMPLE_DOCUMENTS)
        results = hs.search(
            "深度学习在 NLP 中的应用",
            top_k=3,
            bm25_weight=0.3,
            faiss_weight=0.7,
            rerank=True,
        )
        assert len(results) <= 3
        assert len(results) > 0
        # 重排序后分数应在 [0,1]
        for r in results:
            assert 0.0 <= r["score"] <= 1.0

    def test_search_empty_query(self):
        """空查询返回空。"""
        hs = HybridSearch()
        hs.index(SAMPLE_DOCUMENTS)
        assert hs.search("", top_k=5) == []

    def test_search_no_index(self):
        """未索引时检索返回空。"""
        hs = HybridSearch()
        assert hs.search("测试", top_k=5) == []

    def test_search_relevance(self):
        """相关查询返回相关文档。"""
        hs = HybridSearch()
        hs.index(SAMPLE_DOCUMENTS)
        results = hs.search(
            "区块链 金融 应用", top_k=3, rerank=False
        )
        ids = [r["id"] for r in results]
        # doc7（区块链供应链金融）应在结果中
        assert "doc7" in ids

    def test_status(self):
        """状态字段完整。"""
        hs = HybridSearch()
        hs.index(SAMPLE_DOCUMENTS)
        status = hs.get_status()
        assert "embedding" in status
        assert "bm25" in status
        assert "faiss" in status
        assert "reranker" in status
        assert "doc_count" in status
        assert status["doc_count"] == len(SAMPLE_DOCUMENTS)

    def test_singleton(self):
        """全局单例可正常获取。"""
        reset_hybrid_search()
        from backend.retrieval.hybrid_search import get_hybrid_search

        hs1 = get_hybrid_search()
        hs2 = get_hybrid_search()
        assert hs1 is hs2
        reset_hybrid_search()


# ===== 路由测试 =====


class TestRetrievalRoute:
    """路由端到端测试。"""

    def test_route_registered(self):
        """路由已注册到 FastAPI app。"""
        # 仅验证 import 与 router 对象存在
        from backend.routes.retrieval import router

        assert router is not None
        # 检查 prefix
        assert router.prefix == "/api/retrieval"
        # 检查路径（包含 prefix 的完整路径）
        paths = [r.path for r in router.routes]
        assert "/api/retrieval/index" in paths
        assert "/api/retrieval/search" in paths
        assert "/api/retrieval/status" in paths

    def test_main_app_includes_router(self):
        """main.py 已包含 retrieval 路由。"""
        import main

        # 通过 OpenAPI schema 获取所有已注册路径（兼容 FastAPI 新版的 _IncludedRouter）
        schema = main.app.openapi()
        paths = list(schema.get("paths", {}).keys())
        assert any(p.startswith("/api/retrieval") for p in paths), (
            "main.py 未注册 /api/retrieval/* 路由, 已知路径: " + str(sorted(paths))
        )
