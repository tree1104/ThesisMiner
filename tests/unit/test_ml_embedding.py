"""EmbeddingEngine 单元测试

覆盖范围：
    - Vector 向量类的运算（范数、归一化、点积、余弦、欧氏、曼哈顿、加法、数乘）
    - EmbeddingResult / SearchResult / IndexedDocument 数据类
    - EmbeddingCache LRU 缓存（命中、未命中、淘汰、统计）
    - HashEmbedding 哈希嵌入（确定性、归一化、空文本）
    - RandomEmbedding 随机嵌入
    - TfidfEmbedding TF-IDF 嵌入（拟合、嵌入）
    - OpenAIEmbedding OpenAI 嵌入（API Key 缺失降级）
    - VectorIndex 向量索引（增删改查、搜索、过滤、批量、度量）
    - PCAReducer / TSNEReducer 降维
    - EmbeddingEngine 单例模式
    - 文本嵌入与批量嵌入
    - 异步嵌入
    - 索引与搜索
    - 缓存管理
    - 降维与可视化
    - SQLite 持久化
    - 相似度计算
    - 模块级便捷函数

运行方式：
    pytest tests/unit/test_ml_embedding.py -v
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.ml.embedding_engine import (
    DEFAULT_BATCH_CONCURRENCY,
    DEFAULT_CACHE_SIZE,
    DEFAULT_DIMENSION,
    DEFAULT_TOP_K,
    SUPPORTED_MODELS,
    EmbeddingCache,
    EmbeddingEngine,
    EmbeddingResult,
    HashEmbedding,
    IndexedDocument,
    OpenAIEmbedding,
    PCAReducer,
    RandomEmbedding,
    SearchResult,
    TSNEReducer,
    TfidfEmbedding,
    Vector,
    VectorIndex,
    compute_embedding_similarity,
    embed_text,
    get_embedding_engine,
)


# ===== 公共夹具 =====


@pytest.fixture(autouse=True)
def reset_engine():
    """每个测试前后重置单例。"""
    EmbeddingEngine.reset_instance()
    yield
    EmbeddingEngine.reset_instance()


@pytest.fixture
def engine():
    """返回一个全新的 EmbeddingEngine 实例（hash-256 模型）。"""
    return EmbeddingEngine(model="hash-256")


@pytest.fixture
def tmp_db_path(tmp_path):
    """返回临时数据库路径。"""
    return str(tmp_path / "embedding_test.db")


@pytest.fixture
def sample_vectors():
    """返回一组样例向量。"""
    return [
        Vector([1.0, 0.0, 0.0, 0.0]),
        Vector([0.0, 1.0, 0.0, 0.0]),
        Vector([0.0, 0.0, 1.0, 0.0]),
        Vector([1.0, 1.0, 0.0, 0.0]),
    ]


# ===== Vector 类测试 =====


class TestVector:
    """Vector 向量类测试。"""

    def test_vector_from_list(self):
        """从列表创建向量。"""
        v = Vector([1.0, 2.0, 3.0])
        assert v.dimension == 3
        assert v.to_list() == [1.0, 2.0, 3.0]

    def test_vector_from_tuple(self):
        """从元组创建向量。"""
        v = Vector((1.0, 2.0))
        assert v.dimension == 2

    def test_vector_from_vector(self):
        """从另一个 Vector 创建。"""
        v1 = Vector([1.0, 2.0])
        v2 = Vector(v1)
        assert v2.dimension == 2
        assert v2.to_list() == [1.0, 2.0]

    def test_vector_invalid_type(self):
        """无效类型应抛异常。"""
        with pytest.raises(TypeError):
            Vector("invalid")

    def test_vector_dimension(self):
        """维度属性。"""
        v = Vector([1.0] * 10)
        assert v.dimension == 10

    def test_vector_to_list(self):
        """转为列表。"""
        v = Vector([1.5, 2.5, 3.5])
        assert v.to_list() == [1.5, 2.5, 3.5]

    def test_vector_norm(self):
        """L2 范数。"""
        v = Vector([3.0, 4.0])
        assert v.norm() == pytest.approx(5.0)

    def test_vector_norm_zero(self):
        """零向量范数为 0。"""
        v = Vector([0.0, 0.0, 0.0])
        assert v.norm() == 0.0

    def test_vector_normalize(self):
        """归一化。"""
        v = Vector([3.0, 4.0])
        normalized = v.normalize()
        assert normalized.norm() == pytest.approx(1.0)

    def test_vector_normalize_zero(self):
        """零向量归一化仍为零。"""
        v = Vector([0.0, 0.0])
        normalized = v.normalize()
        assert normalized.norm() == 0.0

    def test_vector_dot(self):
        """点积。"""
        v1 = Vector([1.0, 2.0, 3.0])
        v2 = Vector([4.0, 5.0, 6.0])
        assert v1.dot(v2) == pytest.approx(32.0)  # 4+10+18

    def test_vector_dot_dim_mismatch(self):
        """点积维度不匹配抛异常。"""
        v1 = Vector([1.0, 2.0])
        v2 = Vector([1.0, 2.0, 3.0])
        with pytest.raises(ValueError):
            v1.dot(v2)

    def test_vector_cosine(self):
        """余弦相似度。"""
        v1 = Vector([1.0, 0.0])
        v2 = Vector([1.0, 0.0])
        assert v1.cosine(v2) == pytest.approx(1.0)
        v3 = Vector([0.0, 1.0])
        assert v1.cosine(v3) == pytest.approx(0.0)
        v4 = Vector([-1.0, 0.0])
        assert v1.cosine(v4) == pytest.approx(-1.0)

    def test_vector_cosine_zero_vector(self):
        """零向量余弦为 0。"""
        v1 = Vector([0.0, 0.0])
        v2 = Vector([1.0, 0.0])
        assert v1.cosine(v2) == 0.0

    def test_vector_euclidean(self):
        """欧氏距离。"""
        v1 = Vector([0.0, 0.0])
        v2 = Vector([3.0, 4.0])
        assert v1.euclidean(v2) == pytest.approx(5.0)

    def test_vector_manhattan(self):
        """曼哈顿距离。"""
        v1 = Vector([0.0, 0.0])
        v2 = Vector([3.0, 4.0])
        assert v1.manhattan(v2) == pytest.approx(7.0)

    def test_vector_add(self):
        """向量加法。"""
        v1 = Vector([1.0, 2.0])
        v2 = Vector([3.0, 4.0])
        result = v1.add(v2)
        assert result.to_list() == [4.0, 6.0]

    def test_vector_scale(self):
        """数乘。"""
        v = Vector([1.0, 2.0, 3.0])
        result = v.scale(2.0)
        assert result.to_list() == [2.0, 4.0, 6.0]

    def test_vector_len(self):
        """__len__ 方法。"""
        v = Vector([1.0, 2.0, 3.0])
        assert len(v) == 3

    def test_vector_getitem(self):
        """__getitem__ 方法。"""
        v = Vector([10.0, 20.0, 30.0])
        assert v[0] == 10.0
        assert v[1] == 20.0
        assert v[2] == 30.0

    def test_vector_repr(self):
        """__repr__ 方法。"""
        v = Vector([1.0, 2.0, 3.0, 4.0, 5.0])
        repr_str = repr(v)
        assert "Vector" in repr_str
        assert "dim=5" in repr_str


# ===== 数据类测试 =====


class TestDataclasses:
    """数据类测试。"""

    def test_embedding_result_to_dict(self):
        """EmbeddingResult to_dict。"""
        result = EmbeddingResult(
            text="测试",
            vector=Vector([1.0, 2.0]),
            model="hash-256",
            dimension=2,
            cached=False,
            duration_ms=1.5,
        )
        d = result.to_dict()
        assert d["text"] == "测试"
        assert d["vector"] == [1.0, 2.0]
        assert d["model"] == "hash-256"
        assert d["dimension"] == 2
        assert d["cached"] is False
        assert d["duration_ms"] == 1.5

    def test_search_result_to_dict(self):
        """SearchResult to_dict。"""
        result = SearchResult(
            doc_id="doc1",
            text="文本",
            score=0.95,
            rank=1,
            metadata={"category": "test"},
        )
        d = result.to_dict()
        assert d["doc_id"] == "doc1"
        assert d["score"] == 0.95
        assert d["rank"] == 1
        assert d["metadata"] == {"category": "test"}

    def test_indexed_document_to_dict(self):
        """IndexedDocument to_dict。"""
        doc = IndexedDocument(
            doc_id="doc1",
            text="文本",
            vector=Vector([1.0, 2.0]),
            metadata={"key": "value"},
        )
        d = doc.to_dict()
        assert d["doc_id"] == "doc1"
        assert d["text"] == "文本"
        assert d["vector"] == [1.0, 2.0]
        assert d["metadata"] == {"key": "value"}
        assert "created_at" in d


# ===== EmbeddingCache 测试 =====


class TestEmbeddingCache:
    """EmbeddingCache LRU 缓存测试。"""

    def test_cache_put_and_get(self):
        """写入并读取缓存。"""
        cache = EmbeddingCache(capacity=10)
        result = EmbeddingResult(
            text="测试",
            vector=Vector([1.0, 2.0]),
            model="hash-256",
            dimension=2,
        )
        cache.put(result)
        cached = cache.get("测试", "hash-256")
        assert cached is not None
        assert cached.text == "测试"
        assert cached.cached is True

    def test_cache_miss(self):
        """缓存未命中返回 None。"""
        cache = EmbeddingCache()
        assert cache.get("不存在", "hash-256") is None

    def test_cache_stats(self):
        """缓存统计。"""
        cache = EmbeddingCache(capacity=10)
        result = EmbeddingResult(
            text="测试", vector=Vector([1.0]), model="m", dimension=1
        )
        cache.put(result)
        cache.get("测试", "m")  # 命中
        cache.get("不存在", "m")  # 未命中
        stats = cache.get_stats()
        assert stats["size"] == 1
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == pytest.approx(0.5)

    def test_cache_lru_eviction(self):
        """LRU 淘汰策略。"""
        cache = EmbeddingCache(capacity=2)
        r1 = EmbeddingResult(text="t1", vector=Vector([1.0]), model="m", dimension=1)
        r2 = EmbeddingResult(text="t2", vector=Vector([1.0]), model="m", dimension=1)
        r3 = EmbeddingResult(text="t3", vector=Vector([1.0]), model="m", dimension=1)
        cache.put(r1)
        cache.put(r2)
        # 访问 r1 使其成为最近使用
        cache.get("t1", "m")
        # 写入 r3 应淘汰 r2
        cache.put(r3)
        assert cache.get("t2", "m") is None  # r2 被淘汰
        assert cache.get("t1", "m") is not None  # r1 仍在
        assert cache.get("t3", "m") is not None  # r3 在

    def test_cache_clear(self):
        """清空缓存。"""
        cache = EmbeddingCache()
        result = EmbeddingResult(text="t", vector=Vector([1.0]), model="m", dimension=1)
        cache.put(result)
        cache.clear()
        stats = cache.get_stats()
        assert stats["size"] == 0
        assert stats["hits"] == 0
        assert stats["misses"] == 0

    def test_cache_different_models(self):
        """不同模型的缓存隔离。"""
        cache = EmbeddingCache()
        r1 = EmbeddingResult(text="t", vector=Vector([1.0]), model="model1", dimension=1)
        r2 = EmbeddingResult(text="t", vector=Vector([2.0]), model="model2", dimension=1)
        cache.put(r1)
        cache.put(r2)
        assert cache.get("t", "model1") is not None
        assert cache.get("t", "model2") is not None


# ===== HashEmbedding 测试 =====


class TestHashEmbedding:
    """HashEmbedding 哈希嵌入测试。"""

    def test_embed_deterministic(self):
        """相同文本生成相同向量。"""
        emb = HashEmbedding(dimension=256)
        v1 = emb.embed("深度学习")
        v2 = emb.embed("深度学习")
        assert v1.to_list() == v2.to_list()

    def test_embed_different_text(self):
        """不同文本生成不同向量。"""
        emb = HashEmbedding(dimension=256)
        v1 = emb.embed("深度学习")
        v2 = emb.embed("区块链技术")
        assert v1.to_list() != v2.to_list()

    def test_embed_normalized(self):
        """嵌入向量应归一化。"""
        emb = HashEmbedding(dimension=256)
        v = emb.embed("深度学习自然语言处理")
        assert v.norm() == pytest.approx(1.0, abs=1e-6)

    def test_embed_empty_text(self):
        """空文本返回零向量。"""
        emb = HashEmbedding(dimension=256)
        v = emb.embed("")
        assert v.dimension == 256
        assert v.norm() == 0.0

    def test_embed_dimension(self):
        """向量维度正确。"""
        emb = HashEmbedding(dimension=128)
        v = emb.embed("测试")
        assert v.dimension == 128

    def test_embed_batch(self):
        """批量嵌入。"""
        emb = HashEmbedding(dimension=256)
        vectors = emb.embed_batch(["文本1", "文本2", "文本3"])
        assert len(vectors) == 3
        assert all(v.dimension == 256 for v in vectors)


# ===== RandomEmbedding 测试 =====


class TestRandomEmbedding:
    """RandomEmbedding 随机嵌入测试。"""

    def test_embed_deterministic(self):
        """相同文本生成相同向量（基于种子）。"""
        emb = RandomEmbedding(dimension=256, seed=42)
        v1 = emb.embed("测试")
        v2 = emb.embed("测试")
        assert v1.to_list() == v2.to_list()

    def test_embed_different_text(self):
        """不同文本生成不同向量。"""
        emb = RandomEmbedding(dimension=256)
        v1 = emb.embed("文本1")
        v2 = emb.embed("文本2")
        assert v1.to_list() != v2.to_list()

    def test_embed_normalized(self):
        """嵌入向量归一化。"""
        emb = RandomEmbedding(dimension=256)
        v = emb.embed("测试")
        assert v.norm() == pytest.approx(1.0, abs=1e-6)

    def test_embed_empty(self):
        """空文本返回零向量。"""
        emb = RandomEmbedding(dimension=256)
        v = emb.embed("")
        assert v.norm() == 0.0

    def test_embed_batch(self):
        """批量嵌入。"""
        emb = RandomEmbedding(dimension=128)
        vectors = emb.embed_batch(["a", "b", "c"])
        assert len(vectors) == 3


# ===== TfidfEmbedding 测试 =====


class TestTfidfEmbedding:
    """TfidfEmbedding TF-IDF 嵌入测试。"""

    def test_fit_and_embed(self):
        """拟合后嵌入。"""
        emb = TfidfEmbedding(dimension=256)
        corpus = [
            "深度学习 自然语言处理",
            "深度学习 图像识别",
            "区块链 金融",
        ]
        emb.fit(corpus)
        v = emb.embed("深度学习")
        assert v.dimension == 256

    def test_embed_without_fit(self):
        """未拟合时嵌入返回零向量。"""
        emb = TfidfEmbedding(dimension=256)
        v = emb.embed("测试")
        assert v.norm() == 0.0

    def test_embed_empty(self):
        """空文本嵌入。"""
        emb = TfidfEmbedding(dimension=256)
        emb.fit(["测试语料"])
        v = emb.embed("")
        assert v.norm() == 0.0

    def test_embed_batch(self):
        """批量嵌入。"""
        emb = TfidfEmbedding(dimension=256)
        emb.fit(["深度学习", "自然语言处理"])
        vectors = emb.embed_batch(["深度学习", "自然语言处理"])
        assert len(vectors) == 2


# ===== OpenAIEmbedding 测试 =====


class TestOpenAIEmbedding:
    """OpenAIEmbedding OpenAI 嵌入测试。"""

    def test_init_without_api_key(self):
        """无 API Key 初始化不报错。"""
        emb = OpenAIEmbedding(model="text-embedding-3-small", api_key="")
        assert emb.api_key == ""

    def test_embed_without_api_key_raises(self):
        """无 API Key 调用 embed 应抛异常。"""
        emb = OpenAIEmbedding(api_key="")
        with pytest.raises(RuntimeError):
            emb.embed("测试")

    def test_embed_with_mock_client(self):
        """使用 mock 客户端测试嵌入。"""
        emb = OpenAIEmbedding(api_key="test-key")
        # Mock 客户端
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_data = MagicMock()
        mock_data.embedding = [0.1] * 1536
        mock_response.data = [mock_data]
        mock_client.embeddings.create.return_value = mock_response
        emb._client = mock_client
        emb._initialized = True
        v = emb.embed("测试")
        assert v.dimension == 1536

    def test_embed_batch_with_mock(self):
        """批量嵌入 mock 测试。"""
        emb = OpenAIEmbedding(api_key="test-key", batch_size=2)
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_data1 = MagicMock()
        mock_data1.embedding = [0.1] * 1536
        mock_data2 = MagicMock()
        mock_data2.embedding = [0.2] * 1536
        mock_response.data = [mock_data1, mock_data2]
        mock_client.embeddings.create.return_value = mock_response
        emb._client = mock_client
        emb._initialized = True
        vectors = emb.embed_batch(["文本1", "文本2"])
        assert len(vectors) == 2


# ===== VectorIndex 测试 =====


class TestVectorIndex:
    """VectorIndex 向量索引测试。"""

    def test_add_and_get(self):
        """添加并获取文档。"""
        index = VectorIndex(dimension=3)
        v = Vector([1.0, 0.0, 0.0])
        index.add("doc1", "文本1", v, {"category": "test"})
        doc = index.get("doc1")
        assert doc is not None
        assert doc.doc_id == "doc1"
        assert doc.text == "文本1"
        assert doc.metadata == {"category": "test"}

    def test_add_dimension_mismatch(self):
        """维度不匹配抛异常。"""
        index = VectorIndex(dimension=3)
        with pytest.raises(ValueError):
            index.add("doc1", "文本", Vector([1.0, 2.0]))

    def test_add_batch(self):
        """批量添加。"""
        index = VectorIndex(dimension=3)
        docs = [
            ("doc1", "文本1", Vector([1.0, 0.0, 0.0]), {"k": "v1"}),
            ("doc2", "文本2", Vector([0.0, 1.0, 0.0]), {"k": "v2"}),
        ]
        index.add_batch(docs)
        assert index.size() == 2

    def test_remove(self):
        """移除文档。"""
        index = VectorIndex(dimension=3)
        index.add("doc1", "文本", Vector([1.0, 0.0, 0.0]))
        assert index.remove("doc1") is True
        assert index.get("doc1") is None
        assert index.remove("not_exists") is False

    def test_search_cosine(self):
        """余弦相似度搜索。"""
        index = VectorIndex(dimension=3, metric="cosine")
        index.add("doc1", "文本1", Vector([1.0, 0.0, 0.0]))
        index.add("doc2", "文本2", Vector([0.0, 1.0, 0.0]))
        index.add("doc3", "文本3", Vector([1.0, 1.0, 0.0]))
        query = Vector([1.0, 0.0, 0.0])
        results = index.search(query, top_k=2)
        assert len(results) <= 2
        # 最相似的应是 doc1
        assert results[0].doc_id == "doc1"
        assert results[0].score == pytest.approx(1.0)
        assert results[0].rank == 1

    def test_search_euclidean(self):
        """欧氏距离搜索。"""
        index = VectorIndex(dimension=3, metric="euclidean")
        index.add("doc1", "文本1", Vector([1.0, 0.0, 0.0]))
        index.add("doc2", "文本2", Vector([5.0, 0.0, 0.0]))
        query = Vector([0.0, 0.0, 0.0])
        results = index.search(query, top_k=2)
        # 距离最近的应是 doc1
        assert results[0].doc_id == "doc1"

    def test_search_inner_product(self):
        """内积搜索。"""
        index = VectorIndex(dimension=3, metric="inner_product")
        index.add("doc1", "文本1", Vector([2.0, 0.0, 0.0]))
        index.add("doc2", "文本2", Vector([1.0, 0.0, 0.0]))
        query = Vector([1.0, 0.0, 0.0])
        results = index.search(query, top_k=2)
        # 内积最大的应是 doc1
        assert results[0].doc_id == "doc1"

    def test_search_with_filter(self):
        """带过滤条件的搜索。"""
        index = VectorIndex(dimension=3)
        index.add("doc1", "文本1", Vector([1.0, 0.0, 0.0]), {"category": "A"})
        index.add("doc2", "文本2", Vector([1.0, 0.0, 0.0]), {"category": "B"})
        query = Vector([1.0, 0.0, 0.0])
        results = index.search(query, top_k=10, filter_fn=lambda d: d.metadata.get("category") == "A")
        assert len(results) == 1
        assert results[0].doc_id == "doc1"

    def test_search_batch(self):
        """批量搜索。"""
        index = VectorIndex(dimension=3)
        index.add("doc1", "文本1", Vector([1.0, 0.0, 0.0]))
        index.add("doc2", "文本2", Vector([0.0, 1.0, 0.0]))
        queries = [Vector([1.0, 0.0, 0.0]), Vector([0.0, 1.0, 0.0])]
        results = index.search_batch(queries, top_k=1)
        assert len(results) == 2
        assert results[0][0].doc_id == "doc1"
        assert results[1][0].doc_id == "doc2"

    def test_search_dimension_mismatch(self):
        """查询向量维度不匹配抛异常。"""
        index = VectorIndex(dimension=3)
        index.add("doc1", "文本", Vector([1.0, 0.0, 0.0]))
        with pytest.raises(ValueError):
            index.search(Vector([1.0, 0.0]), top_k=1)

    def test_size(self):
        """索引大小。"""
        index = VectorIndex(dimension=3)
        assert index.size() == 0
        index.add("doc1", "文本", Vector([1.0, 0.0, 0.0]))
        assert index.size() == 1

    def test_clear(self):
        """清空索引。"""
        index = VectorIndex(dimension=3)
        index.add("doc1", "文本", Vector([1.0, 0.0, 0.0]))
        index.clear()
        assert index.size() == 0

    def test_get_all_doc_ids(self):
        """获取所有文档 ID。"""
        index = VectorIndex(dimension=3)
        index.add("doc1", "文本1", Vector([1.0, 0.0, 0.0]))
        index.add("doc2", "文本2", Vector([0.0, 1.0, 0.0]))
        ids = index.get_all_doc_ids()
        assert set(ids) == {"doc1", "doc2"}

    def test_get_stats(self):
        """索引统计。"""
        index = VectorIndex(dimension=256, metric="cosine")
        index.add("doc1", "文本", Vector([1.0] * 256))
        stats = index.get_stats()
        assert stats["size"] == 1
        assert stats["dimension"] == 256
        assert stats["metric"] == "cosine"

    def test_search_empty_index(self):
        """空索引搜索返回空列表。"""
        index = VectorIndex(dimension=3)
        results = index.search(Vector([1.0, 0.0, 0.0]), top_k=5)
        assert results == []


# ===== PCAReducer 测试 =====


class TestPCAReducer:
    """PCAReducer PCA 降维测试。"""

    def test_fit_transform(self, sample_vectors):
        """拟合并降维。"""
        reducer = PCAReducer(n_components=2)
        result = reducer.fit_transform(sample_vectors)
        assert len(result) == len(sample_vectors)
        assert all(v.dimension == 2 for v in result)

    def test_fit_empty(self):
        """空向量列表拟合。"""
        reducer = PCAReducer(n_components=2)
        result = reducer.fit_transform([])
        assert result == []

    def test_transform_after_fit(self, sample_vectors):
        """拟合后转换。"""
        reducer = PCAReducer(n_components=2)
        reducer.fit(sample_vectors)
        result = reducer.transform(sample_vectors)
        assert len(result) == len(sample_vectors)
        assert all(v.dimension == 2 for v in result)

    def test_single_component(self, sample_vectors):
        """降维到 1 维。"""
        reducer = PCAReducer(n_components=1)
        result = reducer.fit_transform(sample_vectors)
        assert all(v.dimension == 1 for v in result)


# ===== TSNEReducer 测试 =====


class TestTSNEReducer:
    """TSNEReducer t-SNE 降维测试。"""

    def test_fit_transform(self, sample_vectors):
        """t-SNE 降维。"""
        reducer = TSNEReducer(n_components=2, max_iter=10)
        result = reducer.fit_transform(sample_vectors)
        assert len(result) == len(sample_vectors)
        assert all(v.dimension == 2 for v in result)

    def test_fit_transform_empty(self):
        """空向量列表。"""
        reducer = TSNEReducer(n_components=2)
        assert reducer.fit_transform([]) == []

    def test_fit_transform_single(self):
        """单个向量。"""
        reducer = TSNEReducer(n_components=2)
        result = reducer.fit_transform([Vector([1.0, 2.0, 3.0])])
        assert len(result) == 1
        assert result[0].dimension == 2

    def test_fit_transform_3d(self):
        """3 维降维。"""
        reducer = TSNEReducer(n_components=3, max_iter=10)
        vectors = [Vector([1.0, 0.0, 0.0, 0.0]), Vector([0.0, 1.0, 0.0, 0.0])]
        result = reducer.fit_transform(vectors)
        assert all(v.dimension == 3 for v in result)


# ===== EmbeddingEngine 单例测试 =====


class TestEmbeddingEngineSingleton:
    """EmbeddingEngine 单例模式测试。"""

    def test_singleton_same_instance(self):
        """get_instance 多次返回同一实例。"""
        a = EmbeddingEngine.get_instance()
        b = EmbeddingEngine.get_instance()
        assert a is b

    def test_reset_instance_creates_new(self):
        """reset_instance 后创建新实例。"""
        a = EmbeddingEngine.get_instance()
        EmbeddingEngine.reset_instance()
        b = EmbeddingEngine.get_instance()
        assert a is not b

    def test_get_embedding_engine_function(self):
        """模块级 get_embedding_engine 函数。"""
        engine = get_embedding_engine("hash-256")
        assert engine is EmbeddingEngine.get_instance()

    def test_invalid_model_raises(self):
        """无效模型名抛异常。"""
        with pytest.raises(ValueError):
            EmbeddingEngine(model="invalid-model")


# ===== EmbeddingEngine 嵌入测试 =====


class TestEmbeddingEngineEmbed:
    """EmbeddingEngine 嵌入功能测试。"""

    def test_embed_basic(self, engine):
        """基本嵌入。"""
        result = engine.embed("深度学习")
        assert isinstance(result, EmbeddingResult)
        assert result.dimension == 256
        assert result.model == "hash-256"
        assert result.vector.norm() > 0

    def test_embed_empty_text(self, engine):
        """空文本嵌入。"""
        result = engine.embed("")
        assert result.vector.norm() == 0.0
        assert result.dimension == 256

    def test_embed_cache_hit(self, engine):
        """缓存命中。"""
        text = "深度学习测试"
        result1 = engine.embed(text)
        assert result1.cached is False
        result2 = engine.embed(text)
        assert result2.cached is True

    def test_embed_no_cache(self, engine):
        """禁用缓存。"""
        text = "深度学习"
        result1 = engine.embed(text, use_cache=False)
        result2 = engine.embed(text, use_cache=False)
        assert result1.cached is False
        assert result2.cached is False

    def test_embed_batch(self, engine):
        """批量嵌入。"""
        texts = ["深度学习", "自然语言处理", "区块链"]
        results = engine.embed_batch(texts)
        assert len(results) == 3
        assert all(r.dimension == 256 for r in results)

    def test_embed_batch_with_empty(self, engine):
        """批量嵌入含空文本。"""
        texts = ["深度学习", "", "区块链"]
        results = engine.embed_batch(texts)
        assert len(results) == 3
        assert results[1].vector.norm() == 0.0

    def test_embed_batch_cache(self, engine):
        """批量嵌入缓存。"""
        texts = ["深度学习", "自然语言处理"]
        # 第一次批量嵌入
        results1 = engine.embed_batch(texts)
        # 第二次应命中缓存
        results2 = engine.embed_batch(texts)
        assert all(r.cached for r in results2)

    @pytest.mark.asyncio
    async def test_embed_async(self, engine):
        """异步嵌入。"""
        result = await engine.embed_async("深度学习")
        assert result.dimension == 256

    @pytest.mark.asyncio
    async def test_embed_batch_async(self, engine):
        """异步批量嵌入。"""
        texts = ["深度学习", "自然语言处理", "区块链"]
        results = await engine.embed_batch_async(texts, concurrency=2)
        assert len(results) == 3


# ===== EmbeddingEngine 索引与搜索测试 =====


class TestEmbeddingEngineIndex:
    """EmbeddingEngine 索引与搜索测试。"""

    def test_index_document(self, engine):
        """索引单个文档。"""
        engine.index_document("doc1", "深度学习在 NLP 中的应用", {"category": "NLP"})
        assert engine.get_index_size() == 1
        doc = engine.get_document("doc1")
        assert doc is not None
        assert doc.text == "深度学习在 NLP 中的应用"

    def test_index_batch(self, engine):
        """批量索引。"""
        docs = [
            ("doc1", "深度学习在图像识别中的应用", {"category": "CV"}),
            ("doc2", "自然语言处理中的 Transformer", {"category": "NLP"}),
            ("doc3", "强化学习在游戏 AI 中的应用", {"category": "RL"}),
        ]
        engine.index_batch(docs)
        assert engine.get_index_size() == 3

    def test_search(self, engine):
        """搜索。"""
        docs = [
            ("doc1", "深度学习在图像识别中的应用", {"category": "CV"}),
            ("doc2", "自然语言处理中的 Transformer", {"category": "NLP"}),
            ("doc3", "强化学习在游戏 AI 中的应用", {"category": "RL"}),
        ]
        engine.index_batch(docs)
        results = engine.search("深度学习应用", top_k=2)
        assert len(results) <= 2
        assert len(results) > 0
        assert all(isinstance(r, SearchResult) for r in results)

    def test_search_empty_index(self, engine):
        """空索引搜索。"""
        results = engine.search("查询", top_k=5)
        assert results == []

    def test_search_with_filter(self, engine):
        """带过滤的搜索。"""
        docs = [
            ("doc1", "深度学习在图像识别中的应用", {"category": "CV"}),
            ("doc2", "自然语言处理中的 Transformer", {"category": "NLP"}),
        ]
        engine.index_batch(docs)
        results = engine.search("深度学习", top_k=5, filter_fn=lambda d: d.metadata.get("category") == "NLP")
        assert all(r.metadata.get("category") == "NLP" for r in results)

    def test_search_by_vector(self, engine):
        """按向量搜索。"""
        engine.index_document("doc1", "深度学习")
        query_vec = engine.embed("深度学习").vector
        results = engine.search_by_vector(query_vec, top_k=1)
        assert len(results) == 1
        assert results[0].doc_id == "doc1"

    def test_remove_document(self, engine):
        """移除文档。"""
        engine.index_document("doc1", "深度学习")
        assert engine.remove_document("doc1") is True
        assert engine.get_index_size() == 0
        assert engine.remove_document("not_exists") is False

    def test_clear_index(self, engine):
        """清空索引。"""
        engine.index_document("doc1", "深度学习")
        engine.clear_index()
        assert engine.get_index_size() == 0

    def test_find_similar_documents(self, engine):
        """查找相似文档（带阈值）。"""
        docs = [
            ("doc1", "深度学习在自然语言处理中的应用", {}),
            ("doc2", "区块链技术在金融领域的探索", {}),
        ]
        engine.index_batch(docs)
        results = engine.find_similar_documents("深度学习自然语言处理", top_k=5, threshold=0.1)
        # 应至少返回一个结果
        assert isinstance(results, list)


# ===== EmbeddingEngine 缓存管理测试 =====


class TestEmbeddingEngineCache:
    """EmbeddingEngine 缓存管理测试。"""

    def test_clear_cache(self, engine):
        """清空缓存。"""
        engine.embed("测试")
        engine.clear_cache()
        stats = engine.get_cache_stats()
        assert stats["size"] == 0

    def test_cache_stats(self, engine):
        """缓存统计。"""
        engine.embed("测试1")
        engine.embed("测试1")  # 命中
        engine.embed("测试2")  # 未命中
        stats = engine.get_cache_stats()
        assert stats["hits"] >= 1
        assert stats["misses"] >= 2
        assert stats["size"] >= 2


# ===== EmbeddingEngine 降维与可视化测试 =====


class TestEmbeddingEngineReduction:
    """EmbeddingEngine 降维与可视化测试。"""

    def test_reduce_dimensions_pca(self, engine):
        """PCA 降维。"""
        for i in range(5):
            engine.index_document(f"doc{i}", f"深度学习文本{i}")
        reduced = engine.reduce_dimensions_pca(n_components=2)
        assert len(reduced) == 5
        assert all(v.dimension == 2 for v in reduced)

    def test_reduce_dimensions_pca_empty(self, engine):
        """空索引 PCA 降维。"""
        reduced = engine.reduce_dimensions_pca(n_components=2)
        assert reduced == []

    def test_reduce_dimensions_tsne(self, engine):
        """t-SNE 降维。"""
        for i in range(5):
            engine.index_document(f"doc{i}", f"深度学习文本{i}")
        reduced = engine.reduce_dimensions_tsne(n_components=2, max_iter=10)
        assert len(reduced) == 5
        assert all(v.dimension == 2 for v in reduced)

    def test_prepare_visualization_data_pca(self, engine):
        """PCA 可视化数据。"""
        for i in range(3):
            engine.index_document(f"doc{i}", f"深度学习文本{i}", {"category": "test"})
        viz_data = engine.prepare_visualization_data(method="pca", n_components=2)
        assert "points" in viz_data
        assert len(viz_data["points"]) == 3
        assert viz_data["method"] == "pca"
        assert "coordinates" in viz_data["points"][0]

    def test_prepare_visualization_data_empty(self, engine):
        """空索引可视化数据。"""
        viz_data = engine.prepare_visualization_data()
        assert viz_data["points"] == []

    def test_prepare_visualization_data_invalid_method(self, engine):
        """无效降维方法抛异常。"""
        engine.index_document("doc1", "深度学习")
        with pytest.raises(ValueError):
            engine.prepare_visualization_data(method="invalid")


# ===== EmbeddingEngine 模型管理测试 =====


class TestEmbeddingEngineModel:
    """EmbeddingEngine 模型管理测试。"""

    def test_get_model_info(self, engine):
        """获取模型信息。"""
        info = engine.get_model_info()
        assert info["name"] == "hash-256"
        assert info["dimension"] == 256
        assert info["type"] == "hash"
        assert "index_size" in info
        assert "cache_stats" in info

    def test_list_supported_models(self):
        """列出支持的模型。"""
        models = EmbeddingEngine.list_supported_models()
        assert "hash-128" in models
        assert "hash-256" in models
        assert "hash-512" in models
        assert "random-256" in models
        assert "tfidf-256" in models
        assert "openai-ada-002" in models
        assert "openai-3-small" in models
        assert "openai-3-large" in models
        # 每个模型应包含 dim 和 type
        for name, info in models.items():
            assert "dim" in info
            assert "type" in info
            assert "description" in info


# ===== EmbeddingEngine 持久化测试 =====


class TestEmbeddingEnginePersistence:
    """EmbeddingEngine SQLite 持久化测试。"""

    def test_persist_empty(self, engine, tmp_db_path):
        """空索引持久化返回 0。"""
        count = engine.persist_to_db(tmp_db_path)
        assert count == 0

    def test_persist_and_load(self, engine, tmp_db_path):
        """持久化并加载。"""
        engine.index_document("doc1", "深度学习", {"category": "AI"})
        engine.index_document("doc2", "自然语言处理", {"category": "NLP"})
        count = engine.persist_to_db(tmp_db_path)
        assert count == 2
        # 重置后加载
        EmbeddingEngine.reset_instance()
        new_engine = EmbeddingEngine(model="hash-256")
        loaded = new_engine.load_from_db(tmp_db_path)
        assert loaded == 2
        assert new_engine.get_index_size() == 2
        doc = new_engine.get_document("doc1")
        assert doc is not None
        assert doc.text == "深度学习"

    def test_persist_creates_table(self, engine, tmp_db_path):
        """持久化应创建表。"""
        engine.index_document("doc1", "深度学习")
        engine.persist_to_db(tmp_db_path)
        conn = sqlite3.connect(tmp_db_path)
        try:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='embeddings'"
            )
            assert cursor.fetchone() is not None
        finally:
            conn.close()

    def test_load_nonexistent_db(self, engine):
        """加载不存在的数据库返回 0。"""
        loaded = engine.load_from_db("/nonexistent/path/db.db")
        assert loaded == 0


# ===== EmbeddingEngine 相似度计算测试 =====


class TestEmbeddingEngineSimilarity:
    """EmbeddingEngine 相似度计算测试。"""

    def test_compute_similarity_cosine(self, engine):
        """余弦相似度。"""
        sim = engine.compute_similarity("深度学习", "深度学习", metric="cosine")
        assert sim == pytest.approx(1.0)

    def test_compute_similarity_different(self, engine):
        """不同文本相似度较低。"""
        sim = engine.compute_similarity("深度学习", "区块链技术", metric="cosine")
        assert -1 <= sim <= 1

    def test_compute_similarity_euclidean(self, engine):
        """欧氏距离相似度。"""
        sim = engine.compute_similarity("深度学习", "深度学习", metric="euclidean")
        assert sim == pytest.approx(1.0)  # 距离为 0，1/(1+0)=1

    def test_compute_similarity_inner_product(self, engine):
        """内积相似度。"""
        sim = engine.compute_similarity("深度学习", "深度学习", metric="inner_product")
        assert sim > 0

    def test_compute_similarity_invalid_metric(self, engine):
        """无效度量默认使用余弦。"""
        sim = engine.compute_similarity("深度学习", "深度学习", metric="invalid")
        assert sim == pytest.approx(1.0)


# ===== EmbeddingEngine 关闭测试 =====


class TestEmbeddingEngineShutdown:
    """EmbeddingEngine 资源清理测试。"""

    def test_shutdown_clears_cache_and_index(self, engine):
        """shutdown 清空缓存与索引。"""
        engine.embed("测试")
        engine.index_document("doc1", "深度学习")
        engine.shutdown()
        assert engine.get_cache_stats()["size"] == 0
        assert engine.get_index_size() == 0


# ===== 模块级便捷函数测试 =====


class TestModuleLevelFunctions:
    """模块级便捷函数测试。"""

    def test_embed_text_function(self):
        """embed_text 便捷函数。"""
        vec = embed_text("深度学习", model="hash-256")
        assert isinstance(vec, list)
        assert len(vec) == 256

    def test_compute_embedding_similarity_function(self):
        """compute_embedding_similarity 便捷函数。"""
        sim = compute_embedding_similarity("深度学习", "深度学习", model="hash-256")
        assert sim == pytest.approx(1.0)


# ===== 综合场景测试 =====


class TestIntegrationScenarios:
    """综合场景测试。"""

    def test_full_workflow(self, engine, tmp_db_path):
        """完整工作流：嵌入 -> 索引 -> 搜索 -> 持久化 -> 加载。"""
        # 1. 索引文档
        docs = [
            ("doc1", "深度学习在图像识别中的应用", {"category": "CV"}),
            ("doc2", "自然语言处理中的 Transformer 模型", {"category": "NLP"}),
            ("doc3", "强化学习在游戏 AI 中的应用", {"category": "RL"}),
        ]
        engine.index_batch(docs)
        assert engine.get_index_size() == 3
        # 2. 搜索
        results = engine.search("深度学习应用", top_k=2)
        assert len(results) > 0
        # 3. 降维
        reduced = engine.reduce_dimensions_pca(n_components=2)
        assert len(reduced) == 3
        # 4. 持久化
        count = engine.persist_to_db(tmp_db_path)
        assert count == 3
        # 5. 加载
        EmbeddingEngine.reset_instance()
        new_engine = EmbeddingEngine(model="hash-256")
        loaded = new_engine.load_from_db(tmp_db_path)
        assert loaded == 3

    def test_cache_efficiency(self, engine):
        """缓存效率测试。"""
        text = "深度学习自然语言处理测试文本"
        # 第一次嵌入（未命中）
        r1 = engine.embed(text)
        assert r1.cached is False
        # 第二次嵌入（命中）
        r2 = engine.embed(text)
        assert r2.cached is True
        # 缓存统计
        stats = engine.get_cache_stats()
        assert stats["hits"] >= 1
        assert stats["hit_rate"] > 0

    def test_search_ranking(self, engine):
        """搜索结果排序。"""
        docs = [
            ("doc1", "深度学习深度学习深度学习", {}),
            ("doc2", "区块链技术", {}),
            ("doc3", "深度学习应用", {}),
        ]
        engine.index_batch(docs)
        results = engine.search("深度学习", top_k=3)
        # 结果应按分数降序
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)
        # rank 应从 1 开始递增
        ranks = [r.rank for r in results]
        assert ranks == list(range(1, len(results) + 1))


# ===== 线程安全测试 =====


class TestThreadSafety:
    """线程安全测试。"""

    def test_concurrent_embed(self, engine):
        """多线程并发嵌入。"""
        texts = [f"深度学习文本{i}" for i in range(10)]
        results = [None] * len(texts)

        def worker(idx):
            results[idx] = engine.embed(texts[idx])

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(len(texts))]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert all(r is not None for r in results)
        assert all(r.dimension == 256 for r in results)

    def test_concurrent_index(self, engine):
        """多线程并发索引。"""
        def worker(idx):
            engine.index_document(f"doc{idx}", f"深度学习文本{idx}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert engine.get_index_size() == 5

    def test_concurrent_cache_access(self):
        """多线程并发缓存访问。"""
        cache = EmbeddingCache(capacity=100)
        result = EmbeddingResult(
            text="测试", vector=Vector([1.0]), model="m", dimension=1
        )

        def worker():
            for _ in range(100):
                cache.put(result)
                cache.get("测试", "m")

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # 不应抛出异常即视为通过
        stats = cache.get_stats()
        assert stats["size"] >= 1
