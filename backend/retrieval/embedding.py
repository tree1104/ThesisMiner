"""嵌入引擎模块（v9.0 Task 2.1）

基于 all-MiniLM-L6-v2 本地模型提供文本向量化能力：
    - 384 维 float32 向量
    - L2 归一化（便于使用内积近似余弦相似度）
    - GPU 自动检测（CUDA 可用时优先使用）
    - 延迟加载（首次 encode 时才加载模型权重）

典型用法：
    engine = EmbeddingEngine()
    vec = engine.encode_one("深度学习在 NLP 中的应用")
    mat = engine.encode(["文本1", "文本2"])
"""
from __future__ import annotations

import os
import threading
from typing import List, Optional

import numpy as np

# 延迟导入 torch / sentence_transformers，避免模块导入时即加载

try:
    from backend.utils.logger import get_logger

    _logger = get_logger(__name__)
except Exception:  # pragma: no cover
    import logging

    _logger = logging.getLogger(__name__)


# 项目根目录（main.py 所在目录）
_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

# 默认嵌入维度（all-MiniLM-L6-v2 输出 384 维）
DEFAULT_DIMENSION = 384


class EmbeddingEngine:
    """基于 sentence-transformers 的本地嵌入引擎。

    使用 all-MiniLM-L6-v2 模型生成 384 维 L2 归一化向量。
    模型在首次调用 encode/encode_one 时才加载（延迟加载）。
    """

    def __init__(
        self,
        model_path: str = "all-MiniLM-L6-v2/all-MiniLM-L6-v2",
        device: str = "auto",
    ):
        """初始化嵌入引擎。

        Args:
            model_path: 模型路径，可为相对项目根目录的路径或绝对路径。
            device: 设备，"auto" 时自动检测（cuda 优先），否则使用指定设备。
        """
        self.model_path = model_path
        self.device = device
        self._model = None
        self._lock = threading.Lock()
        self._dimension = DEFAULT_DIMENSION
        self._loaded = False
        self._load_error: Optional[str] = None

    def _resolve_model_path(self) -> str:
        """解析模型路径为绝对路径。"""
        if os.path.isabs(self.model_path) and os.path.exists(self.model_path):
            return self.model_path
        candidate = os.path.join(_PROJECT_ROOT, self.model_path)
        if os.path.exists(candidate):
            return candidate
        # 兜底：直接返回相对路径，由 SentenceTransformer 自行解析
        return self.model_path

    def _resolve_device(self) -> str:
        """解析实际设备字符串。"""
        if self.device == "auto":
            try:
                import torch

                if torch.cuda.is_available():
                    return "cuda"
            except Exception:
                pass
            return "cpu"
        return self.device

    def _ensure_loaded(self) -> bool:
        """延迟加载模型，仅加载一次。返回是否成功。"""
        if self._loaded:
            return self._model is not None
        with self._lock:
            if self._loaded:
                return self._model is not None
            try:
                from sentence_transformers import SentenceTransformer

                resolved_path = self._resolve_model_path()
                device = self._resolve_device()
                _logger.info(
                    "加载嵌入模型: path=%s, device=%s", resolved_path, device
                )
                self._model = SentenceTransformer(resolved_path, device=device)
                # 读取真实维度
                try:
                    # 兼容新旧版本 sentence-transformers
                    if hasattr(self._model, "get_embedding_dimension"):
                        self._dimension = int(self._model.get_embedding_dimension())
                    else:
                        self._dimension = int(
                            self._model.get_sentence_embedding_dimension()
                        )
                except Exception:
                    self._dimension = DEFAULT_DIMENSION
                self._loaded = True
                _logger.info(
                    "嵌入模型加载成功，维度=%d, device=%s",
                    self._dimension,
                    device,
                )
                return True
            except Exception as e:
                self._load_error = str(e)
                _logger.error("嵌入模型加载失败: %s", e, exc_info=True)
                self._loaded = True
                self._model = None
                return False

    @property
    def dimension(self) -> int:
        """返回嵌入维度。"""
        return self._dimension

    def is_loaded(self) -> bool:
        """模型是否已成功加载。"""
        return self._model is not None

    def encode(self, texts: List[str]) -> np.ndarray:
        """批量编码文本为嵌入向量。

        Args:
            texts: 文本列表。

        Returns:
            形状为 (len(texts), dim) 的 float32 numpy 数组，已 L2 归一化。
            若模型加载失败，返回空数组。
        """
        if not texts:
            return np.zeros((0, self._dimension), dtype=np.float32)
        if not self._ensure_loaded() or self._model is None:
            return np.zeros((len(texts), self._dimension), dtype=np.float32)
        try:
            # SentenceTransformer 自带 normalize_embeddings 参数
            embeddings = self._model.encode(
                texts,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            embeddings = np.asarray(embeddings, dtype=np.float32)
            if embeddings.ndim == 1:
                embeddings = embeddings.reshape(1, -1)
            return embeddings
        except Exception as e:
            _logger.error("批量嵌入失败: %s", e, exc_info=True)
            return np.zeros((len(texts), self._dimension), dtype=np.float32)

    def encode_one(self, text: str) -> np.ndarray:
        """编码单条文本为嵌入向量。

        Args:
            text: 文本字符串。

        Returns:
            形状为 (dim,) 的 float32 numpy 数组，已 L2 归一化。
            若模型加载失败，返回零向量。
        """
        if not text:
            return np.zeros(self._dimension, dtype=np.float32)
        result = self.encode([text])
        if result.shape[0] == 0:
            return np.zeros(self._dimension, dtype=np.float32)
        return result[0]

    def get_status(self) -> dict:
        """返回引擎状态信息。"""
        return {
            "model_path": self.model_path,
            "device": self._resolve_device() if self.device == "auto" else self.device,
            "dimension": self._dimension,
            "loaded": self._model is not None,
            "load_error": self._load_error,
        }
