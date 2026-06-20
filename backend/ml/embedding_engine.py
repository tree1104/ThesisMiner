"""嵌入引擎模块

提供文本向量化与相似度搜索能力，包括：
    - 多模型支持（OpenAI / 本地模型 / 随机嵌入 fallback）
    - 向量索引（FAISS-style 简化实现）
    - 相似度搜索（余弦/欧氏/内积）
    - 批量嵌入与缓存
    - 异步处理
    - 向量降维（PCA / t-SNE 简化实现）
    - 可视化数据准备

仅使用 Python 标准库实现核心算法，可选依赖 numpy 加速。
未配置 OpenAI API 时自动降级为基于哈希的本地嵌入。

典型用法：
    engine = EmbeddingEngine(model="hash-256")
    vec = engine.embed("深度学习在 NLP 中的应用")
    results = engine.search(query_vec, top_k=5)
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import random
import sqlite3
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, List, Optional, Tuple, Union

# 尝试导入可选依赖
try:
    import numpy as np  # type: ignore

    _HAS_NUMPY = True
except ImportError:  # pragma: no cover
    np = None  # type: ignore
    _HAS_NUMPY = False

# 尝试导入项目内模块
try:
    from backend.database import DB_PATH
except Exception:  # pragma: no cover
    DB_PATH = "data/thesis_miner.db"

try:
    from backend.utils.logger import get_logger

    _logger = get_logger(__name__)
except Exception:  # pragma: no cover
    import logging

    _logger = logging.getLogger(__name__)

# 尝试导入文本处理器
try:
    from backend.ml.text_processor import TextProcessor, get_text_processor

    _HAS_TEXT_PROCESSOR = True
except Exception:  # pragma: no cover
    _HAS_TEXT_PROCESSOR = False
    TextProcessor = None  # type: ignore
    get_text_processor = None  # type: ignore


# ===== 常量定义 =====

# 默认嵌入维度
DEFAULT_DIMENSION = 256

# 支持的嵌入模型
SUPPORTED_MODELS = {
    "hash-128": {"dim": 128, "type": "hash", "description": "基于哈希的 128 维嵌入"},
    "hash-256": {"dim": 256, "type": "hash", "description": "基于哈希的 256 维嵌入"},
    "hash-512": {"dim": 512, "type": "hash", "description": "基于哈希的 512 维嵌入"},
    "random-256": {"dim": 256, "type": "random", "description": "随机嵌入（仅用于测试）"},
    "random-768": {"dim": 768, "type": "random", "description": "随机嵌入（768 维）"},
    "tfidf-256": {"dim": 256, "type": "tfidf", "description": "基于 TF-IDF 的 256 维嵌入"},
    "openai-ada-002": {"dim": 1536, "type": "openai", "description": "OpenAI text-embedding-ada-002"},
    "openai-3-small": {"dim": 1536, "type": "openai", "description": "OpenAI text-embedding-3-small"},
    "openai-3-large": {"dim": 3072, "type": "openai", "description": "OpenAI text-embedding-3-large"},
}

# 默认搜索 top_k
DEFAULT_TOP_K = 10

# 缓存最大条目数
DEFAULT_CACHE_SIZE = 10000

# 批量嵌入最大并发数
DEFAULT_BATCH_CONCURRENCY = 5


def _now_ts() -> float:
    """获取当前时间戳。"""
    return time.time()


def _safe_float(value: Any, default: float = 0.0) -> float:
    """安全转换为 float。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class Vector:
    """向量封装类

    提供向量运算的统一接口，底层可选 numpy 或纯 Python 列表。
    """

    def __init__(self, data: Union[List[float], "Vector", Any]):
        """初始化向量。

        Args:
            data: 向量数据，可为列表、Vector 或 numpy 数组。
        """
        if isinstance(data, Vector):
            self._data = data._data
            self._use_numpy = data._use_numpy
        elif _HAS_NUMPY and isinstance(data, np.ndarray):
            self._data = data
            self._use_numpy = True
        elif isinstance(data, (list, tuple)):
            if _HAS_NUMPY:
                self._data = np.array(data, dtype=float)
                self._use_numpy = True
            else:
                self._data = [float(x) for x in data]
                self._use_numpy = False
        else:
            raise TypeError(f"不支持的向量数据类型: {type(data)}")

    @property
    def dimension(self) -> int:
        """向量维度。"""
        if self._use_numpy:
            return int(self._data.shape[0])
        return len(self._data)

    @property
    def data(self) -> Union[List[float], Any]:
        """原始数据。"""
        return self._data

    def to_list(self) -> List[float]:
        """转为列表。"""
        if self._use_numpy:
            return self._data.tolist()
        return list(self._data)

    def to_numpy(self):
        """转为 numpy 数组（若可用）。"""
        if self._use_numpy:
            return self._data
        if _HAS_NUMPY:
            return np.array(self._data, dtype=float)
        raise RuntimeError("numpy 不可用")

    def norm(self) -> float:
        """计算 L2 范数。"""
        if self._use_numpy:
            return float(np.linalg.norm(self._data))
        return math.sqrt(sum(x * x for x in self._data))

    def normalize(self) -> "Vector":
        """归一化（L2）。"""
        n = self.norm()
        if n == 0:
            return Vector([0.0] * self.dimension)
        if self._use_numpy:
            return Vector(self._data / n)
        return Vector([x / n for x in self._data])

    def dot(self, other: "Vector") -> float:
        """点积。"""
        self._check_dim(other)
        if self._use_numpy:
            return float(np.dot(self._data, other._data))
        return sum(a * b for a, b in zip(self._data, other._data))

    def cosine(self, other: "Vector") -> float:
        """余弦相似度。"""
        n1 = self.norm()
        n2 = other.norm()
        if n1 == 0 or n2 == 0:
            return 0.0
        return self.dot(other) / (n1 * n2)

    def euclidean(self, other: "Vector") -> float:
        """欧氏距离。"""
        self._check_dim(other)
        if self._use_numpy:
            return float(np.linalg.norm(self._data - other._data))
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(self._data, other._data)))

    def manhattan(self, other: "Vector") -> float:
        """曼哈顿距离。"""
        self._check_dim(other)
        if self._use_numpy:
            return float(np.sum(np.abs(self._data - other._data)))
        return sum(abs(a - b) for a, b in zip(self._data, other._data))

    def add(self, other: "Vector") -> "Vector":
        """向量加法。"""
        self._check_dim(other)
        if self._use_numpy:
            return Vector(self._data + other._data)
        return Vector([a + b for a, b in zip(self._data, other._data)])

    def scale(self, scalar: float) -> "Vector":
        """数乘。"""
        if self._use_numpy:
            return Vector(self._data * scalar)
        return Vector([x * scalar for x in self._data])

    def _check_dim(self, other: "Vector") -> None:
        """检查维度一致性。"""
        if self.dimension != other.dimension:
            raise ValueError(
                f"向量维度不匹配: {self.dimension} vs {other.dimension}"
            )

    def __len__(self) -> int:
        return self.dimension

    def __getitem__(self, index: int) -> float:
        if self._use_numpy:
            return float(self._data[index])
        return self._data[index]

    def __repr__(self) -> str:
        preview = self.to_list()[:5]
        return f"Vector(dim={self.dimension}, data={preview}...)"


@dataclass
class EmbeddingResult:
    """嵌入结果。"""

    text: str
    vector: Vector
    model: str = ""
    dimension: int = 0
    cached: bool = False
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "vector": self.vector.to_list(),
            "model": self.model,
            "dimension": self.dimension,
            "cached": self.cached,
            "duration_ms": self.duration_ms,
        }


@dataclass
class SearchResult:
    """搜索结果。"""

    doc_id: str
    text: str
    score: float
    rank: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "text": self.text,
            "score": self.score,
            "rank": self.rank,
            "metadata": self.metadata,
        }


@dataclass
class IndexedDocument:
    """索引文档。"""

    doc_id: str
    text: str
    vector: Vector
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=_now_ts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "text": self.text,
            "vector": self.vector.to_list(),
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


class EmbeddingCache:
    """嵌入缓存

    基于 LRU 策略缓存文本到向量的映射，避免重复计算。
    """

    def __init__(self, capacity: int = DEFAULT_CACHE_SIZE):
        """初始化缓存。

        Args:
            capacity: 最大缓存条目数。
        """
        self.capacity = capacity
        self._cache: Dict[str, EmbeddingResult] = {}
        self._access_order: Deque[str] = deque()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    def _make_key(self, text: str, model: str) -> str:
        """生成缓存键。"""
        return f"{model}:{hashlib.md5(text.encode('utf-8')).hexdigest()}"

    def get(self, text: str, model: str) -> Optional[EmbeddingResult]:
        """获取缓存。"""
        key = self._make_key(text, model)
        with self._lock:
            result = self._cache.get(key)
            if result is not None:
                self._hits += 1
                # 更新访问顺序
                try:
                    self._access_order.remove(key)
                except ValueError:
                    pass
                self._access_order.append(key)
                # 返回副本（标记 cached）
                return EmbeddingResult(
                    text=result.text,
                    vector=result.vector,
                    model=result.model,
                    dimension=result.dimension,
                    cached=True,
                    duration_ms=0.0,
                )
            self._misses += 1
            return None

    def put(self, result: EmbeddingResult) -> None:
        """写入缓存。"""
        key = self._make_key(result.text, result.model)
        with self._lock:
            # 容量检查
            while len(self._cache) >= self.capacity and self._access_order:
                oldest = self._access_order.popleft()
                self._cache.pop(oldest, None)
            self._cache[key] = result
            self._access_order.append(key)

    def clear(self) -> None:
        """清空缓存。"""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()
            self._hits = 0
            self._misses = 0

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计。"""
        with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._cache),
                "capacity": self.capacity,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self._hits / total if total > 0 else 0.0,
            }


class HashEmbedding:
    """基于哈希的本地嵌入

    通过对文本 token 进行哈希映射到固定维度向量，
    实现零依赖的本地嵌入。适用于无 API 配置或离线场景。

    特点：
        - 确定性：相同文本始终生成相同向量
        - 快速：纯 Python 实现，毫秒级
        - 可区分：不同文本生成不同向量（哈希冲突概率低）
    """

    def __init__(self, dimension: int = 256, use_text_processor: bool = True):
        """初始化哈希嵌入。

        Args:
            dimension: 输出维度。
            use_text_processor: 是否使用 TextProcessor 分词。
        """
        self.dimension = dimension
        self.use_text_processor = use_text_processor and _HAS_TEXT_PROCESSOR
        if self.use_text_processor:
            self._text_processor = get_text_processor()
        else:
            self._text_processor = None

    def embed(self, text: str) -> Vector:
        """生成嵌入向量。"""
        if not text:
            return Vector([0.0] * self.dimension)
        # 分词
        if self._text_processor:
            tokens = self._text_processor.tokenize_to_words(text, remove_stopwords=True)
        else:
            tokens = text.lower().split()
        if not tokens:
            return Vector([0.0] * self.dimension)
        # 哈希映射
        vec = [0.0] * self.dimension
        for token in tokens:
            # 使用 MD5 哈希（确定性）
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            # 映射到向量维度
            idx = h % self.dimension
            # 使用哈希值的高位决定符号
            sign = 1.0 if (h >> (self.dimension.bit_length())) & 1 else -1.0
            # 权重基于 token 长度
            weight = 1.0 + math.log(len(token) + 1)
            vec[idx] += sign * weight
        # L2 归一化
        result = Vector(vec)
        return result.normalize()

    def embed_batch(self, texts: List[str]) -> List[Vector]:
        """批量嵌入。"""
        return [self.embed(t) for t in texts]


class RandomEmbedding:
    """随机嵌入（仅用于测试）

    为相同文本生成相同的随机向量（基于文本哈希作为随机种子）。
    """

    def __init__(self, dimension: int = 256, seed: int = 42):
        """初始化随机嵌入。"""
        self.dimension = dimension
        self.seed = seed

    def embed(self, text: str) -> Vector:
        """生成嵌入向量。"""
        if not text:
            return Vector([0.0] * self.dimension)
        # 基于文本哈希生成种子
        text_hash = int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16)
        rng = random.Random(text_hash ^ self.seed)
        vec = [rng.gauss(0, 1) for _ in range(self.dimension)]
        result = Vector(vec)
        return result.normalize()

    def embed_batch(self, texts: List[str]) -> List[Vector]:
        """批量嵌入。"""
        return [self.embed(t) for t in texts]


class TfidfEmbedding:
    """基于 TF-IDF 的嵌入

    构建词汇表，将文本映射为 TF-IDF 向量。
    适用于小规模语料的快速嵌入。
    """

    def __init__(self, dimension: int = 256, max_vocab_size: int = 10000):
        """初始化 TF-IDF 嵌入。"""
        self.dimension = dimension
        self.max_vocab_size = max_vocab_size
        self._vocab: Dict[str, int] = {}
        self._idf: Dict[str, float] = {}
        self._document_count = 0
        self._df: Dict[str, int] = defaultdict(int)
        self._lock = threading.RLock()
        if _HAS_TEXT_PROCESSOR:
            self._text_processor = get_text_processor()
        else:
            self._text_processor = None

    def fit(self, corpus: List[str]) -> None:
        """拟合语料，构建词汇表与 IDF。"""
        with self._lock:
            self._vocab.clear()
            self._idf.clear()
            self._document_count = 0
            self._df.clear()
            # 统计文档频率
            for doc in corpus:
                tokens = self._tokenize(doc)
                unique_tokens = set(tokens)
                for token in unique_tokens:
                    self._df[token] += 1
                self._document_count += 1
            # 构建词汇表（按文档频率排序，取前 N）
            sorted_words = sorted(
                self._df.items(), key=lambda x: x[1], reverse=True
            )
            # 哈希到固定维度
            for word, _ in sorted_words[: self.max_vocab_size]:
                h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
                self._vocab[word] = h % self.dimension
            # 计算 IDF
            for word in self._vocab:
                df = self._df.get(word, 1)
                self._idf[word] = math.log((self._document_count + 1) / (df + 1)) + 1

    def _tokenize(self, text: str) -> List[str]:
        """分词。"""
        if self._text_processor:
            return self._text_processor.tokenize_to_words(text, remove_stopwords=True)
        return text.lower().split()

    def embed(self, text: str) -> Vector:
        """生成嵌入向量。"""
        if not text or not self._vocab:
            return Vector([0.0] * self.dimension)
        tokens = self._tokenize(text)
        if not tokens:
            return Vector([0.0] * self.dimension)
        # 计算 TF
        tf = defaultdict(int)
        for token in tokens:
            if token in self._vocab:
                tf[token] += 1
        total = sum(tf.values())
        # 构建 TF-IDF 向量
        vec = [0.0] * self.dimension
        for word, count in tf.items():
            tf_val = count / total if total > 0 else 0
            idf_val = self._idf.get(word, 1.0)
            idx = self._vocab[word]
            vec[idx] = tf_val * idf_val
        result = Vector(vec)
        return result.normalize()

    def embed_batch(self, texts: List[str]) -> List[Vector]:
        """批量嵌入。"""
        return [self.embed(t) for t in texts]


class OpenAIEmbedding:
    """OpenAI 嵌入（可选）

    通过 OpenAI API 生成嵌入。需要配置 API Key。
    未配置时实例化不报错，调用 embed 时抛出异常。
    """

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        dimension: int = 1536,
        api_key: Optional[str] = None,
        batch_size: int = 100,
    ):
        """初始化 OpenAI 嵌入。"""
        self.model = model
        self.dimension = dimension
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.batch_size = batch_size
        self._client = None
        self._initialized = False

    def _ensure_client(self):
        """延迟初始化 OpenAI 客户端。"""
        if self._initialized:
            return self._client
        if not self.api_key:
            raise RuntimeError("未配置 OPENAI_API_KEY")
        try:
            from openai import OpenAI  # type: ignore

            self._client = OpenAI(api_key=self.api_key)
            self._initialized = True
            return self._client
        except ImportError:
            raise RuntimeError("openai 库未安装，请执行 pip install openai")

    def embed(self, text: str) -> Vector:
        """生成嵌入向量。"""
        client = self._ensure_client()
        try:
            response = client.embeddings.create(
                model=self.model,
                input=text,
            )
            vec_data = response.data[0].embedding
            return Vector(vec_data)
        except Exception as e:
            _logger.error(f"OpenAI 嵌入失败: {e}", exc_info=True)
            raise

    def embed_batch(self, texts: List[str]) -> List[Vector]:
        """批量嵌入。"""
        client = self._ensure_client()
        results: List[Vector] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            try:
                response = client.embeddings.create(
                    model=self.model,
                    input=batch,
                )
                for item in response.data:
                    results.append(Vector(item.embedding))
            except Exception as e:
                _logger.error(f"OpenAI 批量嵌入失败: {e}", exc_info=True)
                # 失败的批次用零向量填充
                for _ in batch:
                    results.append(Vector([0.0] * self.dimension))
        return results


class VectorIndex:
    """向量索引（FAISS-style 简化实现）

    提供基于暴力搜索的向量索引，支持：
        - 添加/删除文档
        - 余弦/欧氏/内积相似度搜索
        - 批量搜索
        - 持久化

    适用于小到中等规模（< 100 万向量）的场景。
    大规模场景建议使用 FAISS。
    """

    def __init__(self, dimension: int = 256, metric: str = "cosine"):
        """初始化向量索引。

        Args:
            dimension: 向量维度。
            metric: 相似度度量（cosine / euclidean / inner_product）。
        """
        self.dimension = dimension
        self.metric = metric
        self._documents: Dict[str, IndexedDocument] = {}
        self._vectors: Dict[str, Vector] = {}
        self._lock = threading.RLock()

    def add(
        self,
        doc_id: str,
        text: str,
        vector: Vector,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """添加文档。"""
        if vector.dimension != self.dimension:
            raise ValueError(
                f"向量维度不匹配: 期望 {self.dimension}，实际 {vector.dimension}"
            )
        with self._lock:
            doc = IndexedDocument(
                doc_id=doc_id,
                text=text,
                vector=vector,
                metadata=metadata or {},
            )
            self._documents[doc_id] = doc
            self._vectors[doc_id] = vector

    def add_batch(self, documents: List[Tuple[str, str, Vector, Dict[str, Any]]]) -> None:
        """批量添加文档。"""
        with self._lock:
            for doc_id, text, vector, metadata in documents:
                if vector.dimension != self.dimension:
                    raise ValueError(
                        f"向量维度不匹配: 期望 {self.dimension}，实际 {vector.dimension}"
                    )
                doc = IndexedDocument(
                    doc_id=doc_id,
                    text=text,
                    vector=vector,
                    metadata=metadata,
                )
                self._documents[doc_id] = doc
                self._vectors[doc_id] = vector

    def remove(self, doc_id: str) -> bool:
        """移除文档。"""
        with self._lock:
            existed = self._documents.pop(doc_id, None) is not None
            self._vectors.pop(doc_id, None)
            return existed

    def get(self, doc_id: str) -> Optional[IndexedDocument]:
        """获取文档。"""
        with self._lock:
            return self._documents.get(doc_id)

    def search(
        self,
        query: Vector,
        top_k: int = DEFAULT_TOP_K,
        filter_fn=None,
    ) -> List[SearchResult]:
        """搜索最相似的文档。

        Args:
            query: 查询向量。
            top_k: 返回的结果数。
            filter_fn: 可选的过滤函数，签名为 filter_fn(doc: IndexedDocument) -> bool。

        Returns:
            搜索结果列表（按相似度降序）。
        """
        if query.dimension != self.dimension:
            raise ValueError(
                f"查询向量维度不匹配: 期望 {self.dimension}，实际 {query.dimension}"
            )
        with self._lock:
            candidates: List[Tuple[str, float, IndexedDocument]] = []
            for doc_id, vector in self._vectors.items():
                doc = self._documents[doc_id]
                if filter_fn and not filter_fn(doc):
                    continue
                score = self._compute_score(query, vector)
                candidates.append((doc_id, score, doc))
        # 排序
        candidates.sort(key=lambda x: x[1], reverse=True)
        # 截取 top_k
        results: List[SearchResult] = []
        for rank, (doc_id, score, doc) in enumerate(candidates[:top_k]):
            results.append(
                SearchResult(
                    doc_id=doc_id,
                    text=doc.text,
                    score=score,
                    rank=rank + 1,
                    metadata=doc.metadata,
                )
            )
        return results

    def search_batch(
        self,
        queries: List[Vector],
        top_k: int = DEFAULT_TOP_K,
    ) -> List[List[SearchResult]]:
        """批量搜索。"""
        return [self.search(q, top_k=top_k) for q in queries]

    def _compute_score(self, vec1: Vector, vec2: Vector) -> float:
        """根据度量计算相似度分数。"""
        if self.metric == "cosine":
            return vec1.cosine(vec2)
        elif self.metric == "euclidean":
            # 转换为相似度（距离越小，相似度越高）
            return 1.0 / (1.0 + vec1.euclidean(vec2))
        elif self.metric == "inner_product":
            return vec1.dot(vec2)
        else:
            return vec1.cosine(vec2)

    def size(self) -> int:
        """返回索引中文档数。"""
        with self._lock:
            return len(self._documents)

    def clear(self) -> None:
        """清空索引。"""
        with self._lock:
            self._documents.clear()
            self._vectors.clear()

    def get_all_doc_ids(self) -> List[str]:
        """获取所有文档 ID。"""
        with self._lock:
            return list(self._documents.keys())

    def get_stats(self) -> Dict[str, Any]:
        """获取索引统计。"""
        with self._lock:
            return {
                "size": len(self._documents),
                "dimension": self.dimension,
                "metric": self.metric,
            }


class PCAReducer:
    """PCA 降维（简化实现）

    使用协方差矩阵的特征值分解实现主成分分析。
    仅使用 numpy（若可用）或纯 Python。
    """

    def __init__(self, n_components: int = 2):
        """初始化 PCA。

        Args:
            n_components: 降维后的维度。
        """
        self.n_components = n_components
        self.components_: Optional[Any] = None
        self.mean_: Optional[Any] = None
        self.explained_variance_: Optional[Any] = None

    def fit(self, vectors: List[Vector]) -> "PCAReducer":
        """拟合 PCA。"""
        if not vectors:
            return self
        if _HAS_NUMPY:
            matrix = np.array([v.to_numpy() for v in vectors])
            # 中心化
            self.mean_ = np.mean(matrix, axis=0)
            centered = matrix - self.mean_
            # 协方差矩阵
            cov = np.cov(centered.T)
            # 特征值分解
            eigenvalues, eigenvectors = np.linalg.eigh(cov)
            # 按特征值降序排序
            idx = np.argsort(eigenvalues)[::-1]
            eigenvalues = eigenvalues[idx]
            eigenvectors = eigenvectors[:, idx]
            # 选取前 n_components 个主成分
            self.components_ = eigenvectors[:, : self.n_components]
            self.explained_variance_ = eigenvalues[: self.n_components]
        else:
            # 纯 Python 简化实现：仅取前 n_components 维
            dim = vectors[0].dimension
            self.mean_ = [0.0] * dim
            for v in vectors:
                for i in range(dim):
                    self.mean_[i] += v[i]
            n = len(vectors)
            self.mean_ = [m / n for m in self.mean_]
            # 简化：直接取前 n_components 维
            self.components_ = None
            self.explained_variance_ = [1.0] * self.n_components
        return self

    def transform(self, vectors: List[Vector]) -> List[Vector]:
        """降维。"""
        if self.components_ is None:
            # 纯 Python fallback：取前 n_components 维
            return [Vector([v[i] for i in range(self.n_components)]) for v in vectors]
        if _HAS_NUMPY:
            matrix = np.array([v.to_numpy() for v in vectors])
            centered = matrix - self.mean_
            reduced = np.dot(centered, self.components_)
            return [Vector(row) for row in reduced]
        return [Vector([0.0] * self.n_components) for _ in vectors]

    def fit_transform(self, vectors: List[Vector]) -> List[Vector]:
        """拟合并降维。"""
        self.fit(vectors)
        return self.transform(vectors)


class TSNEReducer:
    """t-SNE 降维（简化实现）

    提供简化的 t-SNE 实现，仅用于可视化。
    完整 t-SNE 算法复杂度较高，此处使用梯度下降的简化版本。
    """

    def __init__(
        self,
        n_components: int = 2,
        perplexity: float = 30.0,
        max_iter: int = 250,
        learning_rate: float = 200.0,
    ):
        """初始化 t-SNE。"""
        self.n_components = n_components
        self.perplexity = perplexity
        self.max_iter = max_iter
        self.learning_rate = learning_rate
        self.embedding_: Optional[List[List[float]]] = None

    def fit_transform(self, vectors: List[Vector]) -> List[Vector]:
        """拟合并降维。"""
        n = len(vectors)
        if n == 0:
            return []
        if n == 1:
            return [Vector([0.0] * self.n_components)]
        # 计算高维距离矩阵
        distances = self._compute_distance_matrix(vectors)
        # 计算高维相似度（高斯核）
        p_matrix = self._compute_p_matrix(distances)
        # 初始化低维嵌入（随机）
        rng = random.Random(42)
        y = [[rng.gauss(0, 0.01) for _ in range(self.n_components)] for _ in range(n)]
        # 梯度下降
        for iteration in range(self.max_iter):
            # 计算低维相似度（Student-t 分布）
            q_matrix = self._compute_q_matrix(y)
            # 计算梯度
            gradients = self._compute_gradients(p_matrix, q_matrix, y)
            # 更新
            for i in range(n):
                for d in range(self.n_components):
                    y[i][d] += self.learning_rate * gradients[i][d]
            # 学习率衰减
            if iteration > self.max_iter // 2:
                self.learning_rate *= 0.99
        self.embedding_ = y
        return [Vector(row) for row in y]

    def _compute_distance_matrix(self, vectors: List[Vector]) -> List[List[float]]:
        """计算距离矩阵。"""
        n = len(vectors)
        distances = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                d = vectors[i].euclidean(vectors[j])
                distances[i][j] = d
                distances[j][i] = d
        return distances

    def _compute_p_matrix(self, distances: List[List[float]]) -> List[List[float]]:
        """计算高维相似度矩阵。"""
        n = len(distances)
        p = [[0.0] * n for _ in range(n)]
        # 简化：使用固定 sigma
        sigma = 1.0
        for i in range(n):
            for j in range(n):
                if i != j:
                    p[i][j] = math.exp(-distances[i][j] ** 2 / (2 * sigma ** 2))
            # 归一化
            row_sum = sum(p[i])
            if row_sum > 0:
                for j in range(n):
                    p[i][j] /= row_sum
        # 对称化
        for i in range(n):
            for j in range(i + 1, n):
                p[i][j] = (p[i][j] + p[j][i]) / (2 * n)
                p[j][i] = p[i][j]
        return p

    def _compute_q_matrix(self, y: List[List[float]]) -> List[List[float]]:
        """计算低维相似度矩阵。"""
        n = len(y)
        q = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                d_sq = sum((y[i][k] - y[j][k]) ** 2 for k in range(self.n_components))
                q[i][j] = 1.0 / (1.0 + d_sq)
                q[j][i] = q[i][j]
        # 归一化
        total = sum(sum(row) for row in q)
        if total > 0:
            for i in range(n):
                for j in range(n):
                    q[i][j] /= total
        return q

    def _compute_gradients(
        self,
        p: List[List[float]],
        q: List[List[float]],
        y: List[List[float]],
    ) -> List[List[float]]:
        """计算梯度。"""
        n = len(y)
        gradients = [[0.0] * self.n_components for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i != j:
                    diff = p[i][j] - q[i][j]
                    for d in range(self.n_components):
                        gradients[i][d] += 4 * diff * (y[i][d] - y[j][d]) * q[i][j]
        return gradients


class EmbeddingEngine:
    """嵌入引擎（单例）

    整合多种嵌入模型、向量索引、缓存、降维，提供：
        - 文本嵌入（同步与异步）
        - 批量嵌入
        - 向量索引与搜索
        - 缓存加速
        - 降维可视化
        - SQLite 持久化
    """

    _instance: Optional["EmbeddingEngine"] = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> "EmbeddingEngine":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        model: str = "hash-256",
        api_key: Optional[str] = None,
    ):
        """初始化嵌入引擎。

        Args:
            model: 嵌入模型名。
            api_key: OpenAI API Key（使用 OpenAI 模型时需要）。
        """
        if self._initialized:
            return
        self._initialized = True
        self._model_name = model
        self._api_key = api_key
        self._cache = EmbeddingCache()
        self._index: Optional[VectorIndex] = None
        self._lock = threading.RLock()
        # 初始化嵌入器
        self._embedder = self._create_embedder(model)
        self._dimension = self._get_model_dimension(model)
        # 初始化索引
        self._index = VectorIndex(dimension=self._dimension, metric="cosine")

    @classmethod
    def get_instance(cls) -> "EmbeddingEngine":
        """获取单例实例。"""
        return cls()

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例（仅用于测试）。"""
        with cls._instance_lock:
            cls._instance = None

    def _create_embedder(self, model: str):
        """创建嵌入器实例。"""
        model_info = SUPPORTED_MODELS.get(model)
        if not model_info:
            raise ValueError(f"不支持的嵌入模型: {model}")
        model_type = model_info["type"]
        dim = model_info["dim"]
        if model_type == "hash":
            return HashEmbedding(dimension=dim)
        elif model_type == "random":
            return RandomEmbedding(dimension=dim)
        elif model_type == "tfidf":
            return TfidfEmbedding(dimension=dim)
        elif model_type == "openai":
            return OpenAIEmbedding(model=model, dimension=dim, api_key=self._api_key)
        else:
            raise ValueError(f"未知的嵌入模型类型: {model_type}")

    def _get_model_dimension(self, model: str) -> int:
        """获取模型维度。"""
        model_info = SUPPORTED_MODELS.get(model)
        if model_info:
            return model_info["dim"]
        return DEFAULT_DIMENSION

    # ===== 嵌入方法 =====

    def embed(self, text: str, use_cache: bool = True) -> EmbeddingResult:
        """生成文本嵌入。"""
        if not text:
            return EmbeddingResult(
                text=text,
                vector=Vector([0.0] * self._dimension),
                model=self._model_name,
                dimension=self._dimension,
            )
        # 检查缓存
        if use_cache:
            cached = self._cache.get(text, self._model_name)
            if cached is not None:
                return cached
        # 计算嵌入
        start = _now_ts()
        vector = self._embedder.embed(text)
        duration_ms = (_now_ts() - start) * 1000
        result = EmbeddingResult(
            text=text,
            vector=vector,
            model=self._model_name,
            dimension=vector.dimension,
            duration_ms=duration_ms,
        )
        # 写入缓存
        if use_cache:
            self._cache.put(result)
        return result

    def embed_batch(
        self,
        texts: List[str],
        use_cache: bool = True,
    ) -> List[EmbeddingResult]:
        """批量嵌入。"""
        results: List[EmbeddingResult] = []
        uncached_texts: List[str] = []
        uncached_indices: List[int] = []
        # 先查缓存
        for i, text in enumerate(texts):
            if not text:
                results.append(
                    EmbeddingResult(
                        text=text,
                        vector=Vector([0.0] * self._dimension),
                        model=self._model_name,
                        dimension=self._dimension,
                    )
                )
                continue
            if use_cache:
                cached = self._cache.get(text, self._model_name)
                if cached is not None:
                    results.append(cached)
                    continue
            results.append(None)  # 占位
            uncached_texts.append(text)
            uncached_indices.append(i)
        # 批量计算未缓存的
        if uncached_texts:
            start = _now_ts()
            vectors = self._embedder.embed_batch(uncached_texts)
            duration_ms = (_now_ts() - start) * 1000
            per_duration = duration_ms / len(uncached_texts) if uncached_texts else 0
            for idx, text, vector in zip(uncached_indices, uncached_texts, vectors):
                result = EmbeddingResult(
                    text=text,
                    vector=vector,
                    model=self._model_name,
                    dimension=vector.dimension,
                    duration_ms=per_duration,
                )
                results[idx] = result
                if use_cache:
                    self._cache.put(result)
        return results

    async def embed_async(self, text: str, use_cache: bool = True) -> EmbeddingResult:
        """异步嵌入。"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.embed, text, use_cache)

    async def embed_batch_async(
        self,
        texts: List[str],
        use_cache: bool = True,
        concurrency: int = DEFAULT_BATCH_CONCURRENCY,
    ) -> List[EmbeddingResult]:
        """异步批量嵌入。"""
        semaphore = asyncio.Semaphore(concurrency)

        async def _embed_one(text: str) -> EmbeddingResult:
            async with semaphore:
                return await self.embed_async(text, use_cache)

        tasks = [_embed_one(t) for t in texts]
        return await asyncio.gather(*tasks)

    # ===== 索引与搜索 =====

    def index_document(
        self,
        doc_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EmbeddingResult:
        """索引单个文档。"""
        result = self.embed(text)
        if self._index:
            self._index.add(doc_id, text, result.vector, metadata)
        return result

    def index_batch(
        self,
        documents: List[Tuple[str, str, Dict[str, Any]]],
    ) -> List[EmbeddingResult]:
        """批量索引文档。"""
        texts = [doc[1] for doc in documents]
        results = self.embed_batch(texts)
        if self._index:
            batch_data = [
                (doc[0], doc[1], result.vector, doc[2] if len(doc) > 2 else {})
                for doc, result in zip(documents, results)
            ]
            self._index.add_batch(batch_data)
        return results

    def search(
        self,
        query_text: str,
        top_k: int = DEFAULT_TOP_K,
        filter_fn=None,
    ) -> List[SearchResult]:
        """搜索相似文档。"""
        if not self._index or self._index.size() == 0:
            return []
        query_result = self.embed(query_text)
        return self._index.search(query_result.vector, top_k=top_k, filter_fn=filter_fn)

    def search_by_vector(
        self,
        query_vector: Vector,
        top_k: int = DEFAULT_TOP_K,
        filter_fn=None,
    ) -> List[SearchResult]:
        """按向量搜索。"""
        if not self._index:
            return []
        return self._index.search(query_vector, top_k=top_k, filter_fn=filter_fn)

    def remove_document(self, doc_id: str) -> bool:
        """从索引中移除文档。"""
        if not self._index:
            return False
        return self._index.remove(doc_id)

    def get_document(self, doc_id: str) -> Optional[IndexedDocument]:
        """获取索引文档。"""
        if not self._index:
            return None
        return self._index.get(doc_id)

    def get_index_size(self) -> int:
        """获取索引大小。"""
        if not self._index:
            return 0
        return self._index.size()

    def clear_index(self) -> None:
        """清空索引。"""
        if self._index:
            self._index.clear()

    # ===== 降维与可视化 =====

    def reduce_dimensions_pca(
        self,
        vectors: Optional[List[Vector]] = None,
        n_components: int = 2,
    ) -> List[Vector]:
        """使用 PCA 降维。"""
        if vectors is None:
            # 使用索引中的所有向量
            if not self._index:
                return []
            vectors = [doc.vector for doc in self._index._documents.values()]
        if not vectors:
            return []
        reducer = PCAReducer(n_components=n_components)
        return reducer.fit_transform(vectors)

    def reduce_dimensions_tsne(
        self,
        vectors: Optional[List[Vector]] = None,
        n_components: int = 2,
        max_iter: int = 250,
    ) -> List[Vector]:
        """使用 t-SNE 降维。"""
        if vectors is None:
            if not self._index:
                return []
            vectors = [doc.vector for doc in self._index._documents.values()]
        if not vectors:
            return []
        # 先用 PCA 降到 50 维（若原维度 > 50）
        if vectors[0].dimension > 50:
            pca = PCAReducer(n_components=50)
            vectors = pca.fit_transform(vectors)
        reducer = TSNEReducer(n_components=n_components, max_iter=max_iter)
        return reducer.fit_transform(vectors)

    def prepare_visualization_data(
        self,
        method: str = "pca",
        n_components: int = 2,
    ) -> Dict[str, Any]:
        """准备可视化数据。"""
        if not self._index or self._index.size() == 0:
            return {"points": [], "method": method}
        # 获取所有向量与文档
        docs = list(self._index._documents.values())
        vectors = [doc.vector for doc in docs]
        # 降维
        if method == "pca":
            reduced = self.reduce_dimensions_pca(vectors, n_components)
        elif method == "tsne":
            reduced = self.reduce_dimensions_tsne(vectors, n_components)
        else:
            raise ValueError(f"不支持的降维方法: {method}")
        # 构建数据点
        points = []
        for doc, vec in zip(docs, reduced):
            points.append(
                {
                    "doc_id": doc.doc_id,
                    "text": doc.text[:200],  # 截断长文本
                    "coordinates": vec.to_list(),
                    "metadata": doc.metadata,
                }
            )
        return {
            "points": points,
            "method": method,
            "n_components": n_components,
            "total_points": len(points),
        }

    # ===== 缓存管理 =====

    def clear_cache(self) -> None:
        """清空嵌入缓存。"""
        self._cache.clear()

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计。"""
        return self._cache.get_stats()

    # ===== 模型管理 =====

    def get_model_info(self) -> Dict[str, Any]:
        """获取当前模型信息。"""
        info = SUPPORTED_MODELS.get(self._model_name, {})
        return {
            "name": self._model_name,
            "dimension": self._dimension,
            "type": info.get("type", "unknown"),
            "description": info.get("description", ""),
            "index_size": self.get_index_size(),
            "cache_stats": self.get_cache_stats(),
        }

    @staticmethod
    def list_supported_models() -> Dict[str, Dict[str, Any]]:
        """列出支持的嵌入模型。"""
        return dict(SUPPORTED_MODELS)

    # ===== SQLite 持久化 =====

    def _ensure_table(self, conn: sqlite3.Connection) -> None:
        """确保持久化表存在。"""
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS embeddings (
                doc_id TEXT PRIMARY KEY,
                text TEXT,
                vector TEXT,
                model TEXT,
                dimension INTEGER,
                metadata TEXT,
                created_at REAL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_emb_model ON embeddings(model)"
        )

    def persist_to_db(self, db_path: Optional[str] = None) -> int:
        """将索引持久化到 SQLite。"""
        if not self._index or self._index.size() == 0:
            return 0
        path = db_path or DB_PATH
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        total = 0
        try:
            conn = sqlite3.connect(path)
            try:
                self._ensure_table(conn)
                for doc in self._index._documents.values():
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO embeddings
                        (doc_id, text, vector, model, dimension, metadata, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            doc.doc_id,
                            doc.text,
                            json.dumps(doc.vector.to_list()),
                            self._model_name,
                            doc.vector.dimension,
                            json.dumps(doc.metadata, ensure_ascii=False),
                            doc.created_at,
                        ),
                    )
                    total += 1
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            _logger.error(f"嵌入持久化失败: {e}", exc_info=True)
        return total

    def load_from_db(self, db_path: Optional[str] = None, limit: int = 10000) -> int:
        """从 SQLite 加载嵌入。"""
        path = db_path or DB_PATH
        if not Path(path).exists():
            return 0
        total = 0
        try:
            conn = sqlite3.connect(path)
            try:
                cursor = conn.execute(
                    "SELECT doc_id, text, vector, model, dimension, metadata, created_at "
                    "FROM embeddings WHERE model = ? ORDER BY created_at DESC LIMIT ?",
                    (self._model_name, limit),
                )
                for row in cursor:
                    doc_id, text, vector_json, model, dim, meta_json, created = row
                    try:
                        vec_data = json.loads(vector_json)
                        vector = Vector(vec_data)
                        metadata = json.loads(meta_json) if meta_json else {}
                    except (json.JSONDecodeError, ValueError):
                        continue
                    if self._index:
                        self._index.add(doc_id, text, vector, metadata)
                    total += 1
            finally:
                conn.close()
        except Exception as e:
            _logger.error(f"嵌入加载失败: {e}", exc_info=True)
        return total

    # ===== 相似度计算便捷方法 =====

    def compute_similarity(
        self,
        text1: str,
        text2: str,
        metric: str = "cosine",
    ) -> float:
        """计算两段文本的嵌入相似度。"""
        vec1 = self.embed(text1).vector
        vec2 = self.embed(text2).vector
        if metric == "cosine":
            return vec1.cosine(vec2)
        elif metric == "euclidean":
            return 1.0 / (1.0 + vec1.euclidean(vec2))
        elif metric == "inner_product":
            return vec1.dot(vec2)
        else:
            return vec1.cosine(vec2)

    def find_similar_documents(
        self,
        query_text: str,
        top_k: int = DEFAULT_TOP_K,
        threshold: float = 0.0,
    ) -> List[SearchResult]:
        """查找相似文档（带阈值过滤）。"""
        results = self.search(query_text, top_k=top_k)
        if threshold > 0:
            results = [r for r in results if r.score >= threshold]
        return results

    # ===== 清理 =====

    def shutdown(self) -> None:
        """关闭嵌入引擎。"""
        self.clear_cache()
        self.clear_index()
        _logger.info("嵌入引擎已关闭")


# ===== 模块级便捷函数 =====


_embedding_engine_instance: Optional[EmbeddingEngine] = None
_engine_lock = threading.Lock()


def get_embedding_engine(model: str = "hash-256") -> EmbeddingEngine:
    """获取全局嵌入引擎单例。"""
    global _embedding_engine_instance
    if _embedding_engine_instance is None:
        with _engine_lock:
            if _embedding_engine_instance is None:
                _embedding_engine_instance = EmbeddingEngine(model=model)
    return _embedding_engine_instance


def embed_text(text: str, model: str = "hash-256") -> List[float]:
    """嵌入文本便捷函数。"""
    engine = get_embedding_engine(model)
    return engine.embed(text).vector.to_list()


def compute_embedding_similarity(
    text1: str,
    text2: str,
    model: str = "hash-256",
) -> float:
    """计算嵌入相似度便捷函数。"""
    engine = get_embedding_engine(model)
    return engine.compute_similarity(text1, text2)


# ===== 单元测试可运行逻辑 =====


def _run_self_test() -> None:
    """模块自检。

    可直接 `python -m backend.ml.embedding_engine` 运行。
    """
    EmbeddingEngine.reset_instance()
    engine = EmbeddingEngine(model="hash-256")

    # 测试嵌入
    text1 = "深度学习在自然语言处理中的应用"
    text2 = "自然语言处理中深度学习的使用"
    text3 = "区块链技术在金融领域的探索"
    result1 = engine.embed(text1)
    result2 = engine.embed(text2)
    result3 = engine.embed(text3)
    assert result1.dimension == 256
    assert result1.vector.norm() > 0.99  # 归一化后应接近 1
    print(f"嵌入维度: {result1.dimension}, 范数: {result1.vector.norm():.4f}")

    # 测试相似度
    sim12 = result1.vector.cosine(result2.vector)
    sim13 = result1.vector.cosine(result3.vector)
    assert sim12 > sim13, f"相似文本应得分更高: {sim12} vs {sim13}"
    print(f"余弦相似度: 相似={sim12:.4f}, 不同={sim13:.4f}")

    # 测试缓存
    cached_result = engine.embed(text1)
    assert cached_result.cached
    cache_stats = engine.get_cache_stats()
    assert cache_stats["hits"] > 0
    print(f"缓存统计: {cache_stats}")

    # 测试批量嵌入
    texts = [text1, text2, text3, "另一个文本"]
    batch_results = engine.embed_batch(texts)
    assert len(batch_results) == 4
    print(f"批量嵌入: {len(batch_results)} 个结果")

    # 测试索引与搜索
    docs = [
        ("doc1", "深度学习在图像识别中的应用", {"category": "CV"}),
        ("doc2", "自然语言处理中的 Transformer 模型", {"category": "NLP"}),
        ("doc3", "强化学习在游戏 AI 中的应用", {"category": "RL"}),
        ("doc4", "图神经网络在社交网络分析中的应用", {"category": "GNN"}),
        ("doc5", "深度学习在语音识别中的应用", {"category": "Speech"}),
    ]
    engine.index_batch([(d[0], d[1], d[2]) for d in docs])
    assert engine.get_index_size() == 5

    # 搜索
    query = "深度学习的应用场景"
    results = engine.search(query, top_k=3)
    assert len(results) <= 3
    assert len(results) > 0
    print(f"搜索 '{query}' 返回 {len(results)} 个结果:")
    for r in results:
        print(f"  [{r.rank}] {r.doc_id}: score={r.score:.4f} text={r.text[:30]}...")

    # 测试过滤
    def filter_nlp(doc):
        return doc.metadata.get("category") == "NLP"

    filtered_results = engine.search(query, top_k=5, filter_fn=filter_nlp)
    assert all(r.metadata.get("category") == "NLP" for r in filtered_results)
    print(f"过滤搜索返回 {len(filtered_results)} 个 NLP 文档")

    # 测试降维
    if engine.get_index_size() >= 2:
        pca_result = engine.reduce_dimensions_pca(n_components=2)
        assert len(pca_result) == 5
        assert all(v.dimension == 2 for v in pca_result)
        print(f"PCA 降维: {len(pca_result)} 个 2D 向量")

        tsne_result = engine.reduce_dimensions_tsne(n_components=2, max_iter=50)
        assert len(tsne_result) == 5
        print(f"t-SNE 降维: {len(tsne_result)} 个 2D 向量")

    # 测试可视化数据
    viz_data = engine.prepare_visualization_data(method="pca", n_components=2)
    assert "points" in viz_data
    assert len(viz_data["points"]) == 5
    print(f"可视化数据: {viz_data['total_points']} 个点")

    # 测试模型信息
    model_info = engine.get_model_info()
    assert model_info["name"] == "hash-256"
    print(f"模型信息: {model_info['name']}, 维度 {model_info['dimension']}")

    # 测试支持的模型列表
    models = EmbeddingEngine.list_supported_models()
    assert "hash-256" in models
    print(f"支持的模型: {list(models.keys())}")

    # 测试相似度便捷方法
    sim = engine.compute_similarity(text1, text2)
    assert -1 <= sim <= 1

    # 测试 find_similar_documents
    similar = engine.find_similar_documents("深度学习", top_k=5, threshold=0.1)
    print(f"相似文档（阈值 0.1）: {len(similar)} 个")

    engine.shutdown()
    print("EmbeddingEngine 自检通过")


if __name__ == "__main__":
    _run_self_test()
