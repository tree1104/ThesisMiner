"""BM25 稀疏检索模块（v9.0 Task 2.2）

基于 rank_bm25.BM25Okapi 实现的关键词检索：
    - 支持中英文混合分词（优先 jieba，未安装时回退到正则切分）
    - 支持增量索引（add_documents）
    - 返回带分数的 top_k 结果

典型用法：
    bm25 = BM25Search()
    bm25.index([{"id": "1", "text": "深度学习"}])
    results = bm25.search("深度学习", top_k=5)
"""
from __future__ import annotations

import re
import threading
from typing import Dict, List, Optional

from rank_bm25 import BM25Okapi

try:
    from backend.utils.logger import get_logger

    _logger = get_logger(__name__)
except Exception:  # pragma: no cover
    import logging

    _logger = logging.getLogger(__name__)


# 中文字符正则
_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]")
# 英文/数字 token 正则
_WORD_PATTERN = re.compile(r"[A-Za-z0-9_]+")

# 尝试导入 jieba（可选）
try:
    import jieba  # type: ignore

    _HAS_JIEBA = True
except Exception:  # pragma: no cover
    _HAS_JIEBA = False
    jieba = None  # type: ignore


def tokenize(text: str) -> List[str]:
    """中英文混合分词。

    优先使用 jieba；若未安装，则对中文按字切分、英文按词切分。

    Args:
        text: 待分词文本。

    Returns:
        token 列表（小写化）。
    """
    if not text:
        return []
    if _HAS_JIEBA:
        try:
            return [t.lower() for t in jieba.lcut(text.strip()) if t.strip()]
        except Exception:
            pass
    # 回退：中文按字、英文按词
    tokens: List[str] = []
    # 提取英文/数字词
    for m in _WORD_PATTERN.findall(text):
        tokens.append(m.lower())
    # 提取中文字符（按字切分）
    for ch in text:
        if _CJK_PATTERN.match(ch):
            tokens.append(ch)
    return tokens


class BM25Search:
    """基于 BM25Okapi 的稀疏检索。

    维护文档 id -> 原文/分词 的映射，支持增量添加。
    每次索引更新后重建 BM25 实例（小规模语料下开销可接受）。
    """

    def __init__(self):
        """初始化空语料。"""
        self._ids: List[str] = []
        self._texts: Dict[str, str] = {}
        self._tokenized: Dict[str, List[str]] = {}
        self._bm25: Optional[BM25Okapi] = None
        self._lock = threading.RLock()

    def index(self, documents: List[dict]) -> int:
        """索引文档（覆盖式）。

        Args:
            documents: 文档列表，每个文档需含 "id" 与 "text" 字段。

        Returns:
            成功索引的文档数。
        """
        with self._lock:
            self._ids = []
            self._texts = {}
            self._tokenized = {}
            self._bm25 = None
        return self.add_documents(documents)

    def add_documents(self, documents: List[dict]) -> int:
        """增量添加文档。

        Args:
            documents: 文档列表，每个文档需含 "id" 与 "text" 字段。

        Returns:
            成功添加的文档数。
        """
        added = 0
        with self._lock:
            for doc in documents:
                doc_id = str(doc.get("id", "")).strip()
                text = str(doc.get("text", ""))
                if not doc_id:
                    continue
                if doc_id not in self._texts:
                    self._ids.append(doc_id)
                self._texts[doc_id] = text
                self._tokenized[doc_id] = tokenize(text)
                added += 1
            self._rebuild()
        return added

    def _rebuild(self) -> None:
        """重建 BM25 实例（在锁内调用）。"""
        if not self._ids:
            self._bm25 = None
            return
        corpus = [self._tokenized[doc_id] for doc_id in self._ids]
        try:
            self._bm25 = BM25Okapi(corpus)
        except Exception as e:
            _logger.error("BM25 重建失败: %s", e, exc_info=True)
            self._bm25 = None

    def search(self, query: str, top_k: int = 10) -> List[dict]:
        """检索 top_k 相关文档。

        Args:
            query: 查询字符串。
            top_k: 返回结果数。

        Returns:
            结果列表，每项含 id/text/score 字段，按分数降序。
        """
        if not query or top_k <= 0:
            return []
        with self._lock:
            if not self._bm25 or not self._ids:
                return []
            bm25 = self._bm25
            ids = list(self._ids)
            texts = dict(self._texts)
        try:
            query_tokens = tokenize(query)
            if not query_tokens:
                return []
            scores = bm25.get_scores(query_tokens)
        except Exception as e:
            _logger.error("BM25 检索失败: %s", e, exc_info=True)
            return []
        # 组装并排序
        results = []
        for idx, score in enumerate(scores):
            if idx >= len(ids):
                break
            try:
                score_val = float(score)
            except Exception:
                score_val = 0.0
            results.append(
                {
                    "id": ids[idx],
                    "text": texts.get(ids[idx], ""),
                    "score": score_val,
                    "source": "bm25",
                }
            )
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def size(self) -> int:
        """返回已索引文档数。"""
        with self._lock:
            return len(self._ids)

    def get_status(self) -> dict:
        """返回状态信息。"""
        with self._lock:
            return {
                "doc_count": len(self._ids),
                "tokenizer": "jieba" if _HAS_JIEBA else "regex",
                "ready": self._bm25 is not None,
            }
