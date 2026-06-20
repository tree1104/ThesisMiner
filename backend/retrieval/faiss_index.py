"""FAISS 向量索引模块（v9.0 Task 2.3）

基于 faiss-cpu 的稠密向量索引：
    - 使用 IndexFlatIP（内积）配合 L2 归一化向量实现精确余弦相似度检索
    - 维护 id <-> faiss 内部行号的映射
    - 支持持久化（save/load）

典型用法：
    index = FAISSIndex(dim=384)
    index.add(embeddings, ids=["1", "2"])
    results = index.search(query_vec, top_k=5)
"""
from __future__ import annotations

import json
import os
import threading
from typing import Dict, List, Optional

import numpy as np

try:
    from backend.utils.logger import get_logger

    _logger = get_logger(__name__)
except Exception:  # pragma: no cover
    import logging

    _logger = logging.getLogger(__name__)


class FAISSIndex:
    """基于 faiss.IndexFlatIP 的向量索引。

    使用内积（Inner Product）作为相似度度量，配合 L2 归一化的向量
    即可得到余弦相似度。适用于中小规模（< 1M）精确检索场景。
    """

    def __init__(self, dim: int = 384):
        """初始化索引。

        Args:
            dim: 向量维度。
        """
        self.dim = int(dim)
        self._index = None
        self._ids: List[str] = []
        self._id_to_row: Dict[str, int] = {}
        self._lock = threading.RLock()
        self._init_index()

    def _init_index(self) -> None:
        """创建底层 faiss 索引。"""
        try:
            import faiss

            self._faiss = faiss
            self._index = faiss.IndexFlatIP(self.dim)
        except Exception as e:
            _logger.error("FAISS 初始化失败: %s", e, exc_info=True)
            self._faiss = None
            self._index = None

    def add(self, embeddings: np.ndarray, ids: List[str]) -> int:
        """添加向量到索引。

        Args:
            embeddings: 形状为 (n, dim) 的 float32 数组。
            ids: 长度为 n 的 id 列表。

        Returns:
            成功添加的向量数。
        """
        if embeddings is None or len(ids) == 0:
            return 0
        try:
            arr = np.asarray(embeddings, dtype=np.float32)
        except Exception as e:
            _logger.error("FAISS add: 向量转换失败: %s", e)
            return 0
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        if arr.shape[1] != self.dim:
            _logger.error(
                "FAISS add: 维度不匹配, 期望 %d, 实际 %d", self.dim, arr.shape[1]
            )
            return 0
        if arr.shape[0] != len(ids):
            _logger.error("FAISS add: 数量不匹配, %d vs %d", arr.shape[0], len(ids))
            return 0
        if self._index is None:
            self._init_index()
            if self._index is None:
                return 0
        with self._lock:
            # 若已存在相同 id，先不特殊处理（追加，查询时去重）
            start = self._index.ntotal
            try:
                self._index.add(arr)
            except Exception as e:
                _logger.error("FAISS add 失败: %s", e, exc_info=True)
                return 0
            for i, doc_id in enumerate(ids):
                self._ids.append(str(doc_id))
                self._id_to_row[str(doc_id)] = start + i
            return arr.shape[0]

    def search(
        self, query_embedding: np.ndarray, top_k: int = 10
    ) -> List[dict]:
        """检索 top_k 最相似向量。

        Args:
            query_embedding: 形状为 (dim,) 或 (1, dim) 的 float32 查询向量。
            top_k: 返回结果数。

        Returns:
            结果列表，每项含 id/score 字段，按分数降序。
        """
        if self._index is None or self._index.ntotal == 0 or top_k <= 0:
            return []
        try:
            arr = np.asarray(query_embedding, dtype=np.float32)
        except Exception as e:
            _logger.error("FAISS search: 向量转换失败: %s", e)
            return []
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        if arr.shape[1] != self.dim:
            _logger.error(
                "FAISS search: 维度不匹配, 期望 %d, 实际 %d",
                self.dim,
                arr.shape[1],
            )
            return []
        with self._lock:
            k = min(top_k, int(self._index.ntotal))
            try:
                scores, indices = self._index.search(arr, k)
            except Exception as e:
                _logger.error("FAISS search 失败: %s", e, exc_info=True)
                return []
            ids_snapshot = list(self._ids)
        results: List[dict] = []
        for row in range(indices.shape[0]):
            for col in range(indices.shape[1]):
                row_idx = int(indices[row, col])
                if row_idx < 0 or row_idx >= len(ids_snapshot):
                    continue
                try:
                    score = float(scores[row, col])
                except Exception:
                    score = 0.0
                results.append(
                    {
                        "id": ids_snapshot[row_idx],
                        "score": score,
                        "source": "faiss",
                    }
                )
        return results[:top_k]

    def size(self) -> int:
        """返回索引向量数。"""
        with self._lock:
            return int(self._index.ntotal) if self._index is not None else 0

    def save(self, path: str) -> bool:
        """保存索引到磁盘。

        Args:
            path: 索引文件路径（.index）。

        Returns:
            是否保存成功。
        """
        if self._index is None or self._faiss is None:
            return False
        try:
            with self._lock:
                os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
                self._faiss.write_index(self._index, path)
                # 同时保存 id 映射
                meta_path = path + ".meta.json"
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(
                        {"dim": self.dim, "ids": self._ids},
                        f,
                        ensure_ascii=False,
                    )
            return True
        except Exception as e:
            _logger.error("FAISS 保存失败: %s", e, exc_info=True)
            return False

    def load(self, path: str) -> bool:
        """从磁盘加载索引。

        Args:
            path: 索引文件路径（.index）。

        Returns:
            是否加载成功。
        """
        if self._faiss is None:
            return False
        try:
            with self._lock:
                if not os.path.exists(path):
                    return False
                self._index = self._faiss.read_index(path)
                meta_path = path + ".meta.json"
                if os.path.exists(meta_path):
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    self._ids = [str(i) for i in meta.get("ids", [])]
                    self._id_to_row = {
                        doc_id: i for i, doc_id in enumerate(self._ids)
                    }
                else:
                    # 无元数据时按行号生成占位 id
                    self._ids = [str(i) for i in range(self._index.ntotal)]
                    self._id_to_row = {
                        doc_id: i for i, doc_id in enumerate(self._ids)
                    }
            return True
        except Exception as e:
            _logger.error("FAISS 加载失败: %s", e, exc_info=True)
            return False

    def get_status(self) -> dict:
        """返回状态信息。"""
        with self._lock:
            return {
                "dim": self.dim,
                "size": int(self._index.ntotal) if self._index is not None else 0,
                "ready": self._index is not None,
            }
