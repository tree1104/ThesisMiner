"""知识库主体模块

提供完整的知识库实现，包括：
    - 知识条目的 CRUD 操作
    - 分类检索与全文搜索（TF-IDF）
    - 知识图谱构建（节点 + 边）、关联查询、路径查找（BFS）
    - 学科分类树、关键词索引
    - 知识条目版本管理、变更历史、冲突解决
    - 批量导入导出（JSON / CSV / YAML 格式）
    - 内存缓存优化（LRU）

设计原则：
    1. 零外部依赖：仅使用 Python 标准库
    2. 线程安全：所有公共方法通过 RLock 保护
    3. 可持久化：基于 SQLite，支持序列化存储
    4. 可扩展：分类、关系类型均可动态扩展

核心数据结构：
    - KnowledgeEntry: 知识条目（标题、内容、分类、标签、版本等）
    - KnowledgeCategory: 知识分类节点（树形结构）
    - KnowledgeRelation: 知识关系（有向边，带类型与权重）
    - KnowledgeVersion: 知识版本快照
"""
from __future__ import annotations

import csv
import io
import json
import math
import re
import threading
import uuid
from collections import OrderedDict, defaultdict, deque
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Iterable, Optional

from backend.database import (
    execute_insert,
    execute_query,
    fetch_all,
    fetch_one,
)


# ===== 常量定义 =====

# 默认分类根节点
DEFAULT_ROOT_CATEGORY = "根分类"

# 知识条目最大标题长度
MAX_TITLE_LENGTH = 200

# 知识条目最大内容长度（字符）
MAX_CONTENT_LENGTH = 50000

# TF-IDF 检索默认返回数量
DEFAULT_SEARCH_LIMIT = 20

# LRU 缓存默认容量
DEFAULT_CACHE_SIZE = 256

# 关系类型枚举
RELATION_TYPES = {
    "relates_to": "相关",
    "depends_on": "依赖",
    "extends": "扩展",
    "contradicts": "矛盾",
    "cites": "引用",
    "derived_from": "派生自",
    "part_of": "属于",
    "similar_to": "相似",
}

# 中文停用词表（精简版）
STOP_WORDS = frozenset({
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
    "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有",
    "看", "好", "自己", "这", "那", "与", "及", "或", "但", "而", "从", "为",
    "被", "把", "向", "由", "对", "于", "以", "其", "之", "所", "可", "能",
    "如", "若", "则", "故", "因", "由", "此", "彼", "它", "他", "她", "它们",
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "in", "on", "at", "to", "for", "of", "and", "or", "but", "if", "then",
    "this", "that", "these", "those", "with", "from", "by", "as", "it",
})


# ===== 数据结构 =====


@dataclass
class KnowledgeEntry:
    """知识条目数据结构。

    Attributes:
        id: 条目唯一标识。
        title: 标题。
        content: 正文内容。
        category_id: 所属分类 ID。
        tags: 标签列表。
        keywords: 关键词列表（用于检索）。
        discipline: 关联学科代码。
        source: 来源信息。
        author: 创建者。
        version: 当前版本号（从 1 开始递增）。
        created_at: 创建时间（ISO 格式）。
        updated_at: 最后更新时间。
        metadata: 扩展元数据。
        view_count: 浏览次数。
        quality_score: 质量评分（0-100）。
    """

    id: str = ""
    title: str = ""
    content: str = ""
    category_id: str = ""
    tags: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    discipline: str = ""
    source: str = ""
    author: str = ""
    version: int = 1
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    view_count: int = 0
    quality_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（用于序列化存储）。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KnowledgeEntry":
        """从字典构造条目实例。"""
        # 兼容缺失字段
        defaults = cls().__dict__
        merged = {**defaults, **{k: v for k, v in data.items() if k in defaults}}
        return cls(**merged)

    def summary(self) -> str:
        """返回条目摘要（前 100 字）。"""
        text = self.content.strip()
        if len(text) <= 100:
            return text
        return text[:100] + "..."


@dataclass
class KnowledgeCategory:
    """知识分类节点（树形结构）。

    Attributes:
        id: 分类 ID。
        name: 分类名称。
        parent_id: 父分类 ID（根分类为空字符串）。
        level: 层级（0 为根）。
        description: 分类描述。
        sort_order: 排序序号。
        children: 子分类 ID 列表。
    """

    id: str = ""
    name: str = ""
    parent_id: str = ""
    level: int = 0
    description: str = ""
    sort_order: int = 0
    children: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class KnowledgeRelation:
    """知识关系（有向边）。

    Attributes:
        id: 关系 ID。
        source_id: 源条目 ID。
        target_id: 目标条目 ID。
        relation_type: 关系类型（见 RELATION_TYPES）。
        weight: 关系权重（0-1）。
        created_at: 创建时间。
        metadata: 扩展元数据。
    """

    id: str = ""
    source_id: str = ""
    target_id: str = ""
    relation_type: str = "relates_to"
    weight: float = 1.0
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class KnowledgeVersion:
    """知识条目版本快照。

    Attributes:
        version_id: 版本 ID。
        entry_id: 对应条目 ID。
        version: 版本号。
        title: 该版本标题。
        content: 该版本内容。
        author: 修改者。
        timestamp: 修改时间。
        change_note: 变更说明。
        diff_summary: 变更摘要。
    """

    version_id: str = ""
    entry_id: str = ""
    version: int = 1
    title: str = ""
    content: str = ""
    author: str = ""
    timestamp: str = ""
    change_note: str = ""
    diff_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ===== 工具函数 =====


def _now_iso() -> str:
    """返回当前时间的 ISO 格式字符串。"""
    return datetime.now().isoformat()


def _new_id(prefix: str = "kb") -> str:
    """生成带前缀的唯一 ID。"""
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _tokenize(text: str) -> list[str]:
    """中文/英文混合分词。

    中文按 2-gram 切分，英文按单词切分，过滤停用词。

    Args:
        text: 待分词文本。

    Returns:
        分词后的 token 列表。
    """
    if not text:
        return []
    tokens: list[str] = []
    # 英文单词
    en_words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]+", text.lower())
    for w in en_words:
        if w not in STOP_WORDS and len(w) > 1:
            tokens.append(w)
    # 中文字符 2-gram
    cn_chars = re.findall(r"[\u4e00-\u9fff]", text)
    for i in range(len(cn_chars) - 1):
        gram = cn_chars[i] + cn_chars[i + 1]
        if gram not in STOP_WORDS:
            tokens.append(gram)
    # 单字（用于短文本兜底）
    for ch in cn_chars:
        if ch not in STOP_WORDS:
            tokens.append(ch)
    return tokens


def _compute_text_hash(text: str) -> str:
    """计算文本的哈希值（用于变更检测）。"""
    import hashlib
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _levenshtein(s1: str, s2: str) -> int:
    """计算两个字符串的编辑距离。"""
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


# ===== LRU 缓存 =====


class LRUCache:
    """简单的 LRU 缓存实现（线程安全）。

    基于 OrderedDict 实现，访问或写入时将条目移至末尾，
    超出容量时淘汰最久未使用的条目。
    """

    def __init__(self, capacity: int = DEFAULT_CACHE_SIZE) -> None:
        """初始化 LRU 缓存。

        Args:
            capacity: 缓存容量。
        """
        self._capacity = max(1, capacity)
        self._data: OrderedDict[str, Any] = OrderedDict()
        self._lock = threading.RLock()
        # 统计信息
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值。命中时移至末尾。"""
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                self._hits += 1
                return self._data[key]
            self._misses += 1
            return None

    def put(self, key: str, value: Any) -> None:
        """写入缓存值。已存在则更新并移至末尾。"""
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                self._data[key] = value
            else:
                self._data[key] = value
                if len(self._data) > self._capacity:
                    self._data.popitem(last=False)

    def invalidate(self, key: str) -> bool:
        """使指定键失效。"""
        with self._lock:
            if key in self._data:
                del self._data[key]
                return True
            return False

    def clear(self) -> None:
        """清空缓存。"""
        with self._lock:
            self._data.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> dict[str, int]:
        """返回缓存统计信息。"""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0.0
            return {
                "size": len(self._data),
                "capacity": self._capacity,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(hit_rate, 4),
            }


# ===== TF-IDF 检索引擎 =====


class TFIDFIndex:
    """TF-IDF 全文检索索引。

    维护文档的词频统计与逆文档频率，支持基于余弦相似度的检索。
    索引在内存中构建，支持增量更新。
    """

    def __init__(self) -> None:
        """初始化空的 TF-IDF 索引。"""
        # doc_id -> token -> tf
        self._doc_tokens: dict[str, dict[str, int]] = {}
        # token -> doc_count
        self._df: dict[str, int] = defaultdict(int)
        # doc_id -> norm（向量长度）
        self._norms: dict[str, float] = {}
        self._lock = threading.RLock()

    def add_document(self, doc_id: str, text: str) -> None:
        """添加或更新文档到索引。

        Args:
            doc_id: 文档 ID。
            text: 文档文本。
        """
        with self._lock:
            # 若已存在，先移除旧数据
            if doc_id in self._doc_tokens:
                self._remove_document_internal(doc_id)
            tokens = _tokenize(text)
            tf: dict[str, int] = defaultdict(int)
            for t in tokens:
                tf[t] += 1
            self._doc_tokens[doc_id] = dict(tf)
            for token in tf:
                self._df[token] += 1
            self._recompute_norm(doc_id)

    def remove_document(self, doc_id: str) -> bool:
        """从索引移除文档。"""
        with self._lock:
            return self._remove_document_internal(doc_id)

    def _remove_document_internal(self, doc_id: str) -> bool:
        """内部移除实现（不加锁）。"""
        if doc_id not in self._doc_tokens:
            return False
        tokens = self._doc_tokens.pop(doc_id)
        for token in tokens:
            self._df[token] -= 1
            if self._df[token] <= 0:
                del self._df[token]
        self._norms.pop(doc_id, None)
        return True

    def _recompute_norm(self, doc_id: str) -> None:
        """重新计算文档的向量长度。"""
        tokens = self._doc_tokens.get(doc_id, {})
        total_docs = len(self._doc_tokens)
        if not tokens or total_docs == 0:
            self._norms[doc_id] = 0.0
            return
        sum_sq = 0.0
        for token, tf in tokens.items():
            df = self._df.get(token, 0)
            if df == 0:
                continue
            idf = math.log((total_docs + 1) / (df + 1)) + 1
            weight = tf * idf
            sum_sq += weight * weight
        self._norms[doc_id] = math.sqrt(sum_sq) if sum_sq > 0 else 0.0

    def search(self, query: str, limit: int = DEFAULT_SEARCH_LIMIT) -> list[tuple[str, float]]:
        """检索与查询最相关的文档。

        Args:
            query: 查询文本。
            limit: 返回结果数量上限。

        Returns:
            (doc_id, score) 元组列表，按相似度降序。
        """
        with self._lock:
            query_tokens = _tokenize(query)
            if not query_tokens:
                return []
            total_docs = len(self._doc_tokens)
            if total_docs == 0:
                return []
            # 计算查询向量
            query_tf: dict[str, int] = defaultdict(int)
            for t in query_tokens:
                query_tf[t] += 1
            query_vec: dict[str, float] = {}
            for token, tf in query_tf.items():
                df = self._df.get(token, 0)
                if df == 0:
                    continue
                idf = math.log((total_docs + 1) / (df + 1)) + 1
                query_vec[token] = tf * idf
            if not query_vec:
                return []
            query_norm = math.sqrt(sum(v * v for v in query_vec.values()))
            if query_norm == 0:
                return []
            # 计算与每个文档的余弦相似度
            scores: list[tuple[str, float]] = []
            for doc_id, tokens in self._doc_tokens.items():
                doc_norm = self._norms.get(doc_id, 0.0)
                if doc_norm == 0:
                    continue
                dot = 0.0
                for token, q_weight in query_vec.items():
                    tf = tokens.get(token, 0)
                    if tf == 0:
                        continue
                    df = self._df.get(token, 0)
                    idf = math.log((total_docs + 1) / (df + 1)) + 1
                    doc_weight = tf * idf
                    dot += q_weight * doc_weight
                if dot == 0:
                    continue
                score = dot / (query_norm * doc_norm)
                scores.append((doc_id, score))
            scores.sort(key=lambda x: x[1], reverse=True)
            return scores[:limit]

    def document_count(self) -> int:
        """返回已索引文档数量。"""
        with self._lock:
            return len(self._doc_tokens)

    def vocabulary_size(self) -> int:
        """返回词表大小。"""
        with self._lock:
            return len(self._df)


# ===== 知识图谱 =====


class KnowledgeGraph:
    """知识图谱（邻接表实现）。

    维护节点与有向边，支持关联查询、路径查找、子图提取。
    """

    def __init__(self) -> None:
        """初始化空图谱。"""
        # node_id -> set of (target_id, relation_type, weight)
        self._out_edges: dict[str, dict[str, list[tuple[str, str, float]]]] = defaultdict(dict)
        # node_id -> set of (source_id, relation_type, weight)
        self._in_edges: dict[str, dict[str, list[tuple[str, str, float]]]] = defaultdict(dict)
        self._lock = threading.RLock()

    def add_edge(self, source_id: str, target_id: str,
                 relation_type: str = "relates_to", weight: float = 1.0) -> None:
        """添加有向边。"""
        with self._lock:
            self._out_edges[source_id].setdefault(target_id, []).append(
                (target_id, relation_type, weight)
            )
            self._in_edges[target_id].setdefault(source_id, []).append(
                (source_id, relation_type, weight)
            )

    def remove_edge(self, source_id: str, target_id: str,
                    relation_type: Optional[str] = None) -> int:
        """移除边。返回移除数量。"""
        with self._lock:
            removed = 0
            if source_id in self._out_edges and target_id in self._out_edges[source_id]:
                edges = self._out_edges[source_id][target_id]
                if relation_type is None:
                    removed = len(edges)
                    edges.clear()
                else:
                    before = len(edges)
                    edges[:] = [e for e in edges if e[1] != relation_type]
                    removed = before - len(edges)
                if not edges:
                    del self._out_edges[source_id][target_id]
            if target_id in self._in_edges and source_id in self._in_edges[target_id]:
                edges = self._in_edges[target_id][source_id]
                if relation_type is None:
                    edges.clear()
                else:
                    edges[:] = [e for e in edges if e[1] != relation_type]
                if not edges:
                    del self._in_edges[target_id][source_id]
            return removed

    def remove_node(self, node_id: str) -> int:
        """移除节点及其所有关联边。"""
        with self._lock:
            removed = 0
            # 移除出边
            for target_id in list(self._out_edges.get(node_id, {}).keys()):
                removed += self.remove_edge(node_id, target_id)
            # 移除入边
            for source_id in list(self._in_edges.get(node_id, {}).keys()):
                removed += self.remove_edge(source_id, node_id)
            self._out_edges.pop(node_id, None)
            self._in_edges.pop(node_id, None)
            return removed

    def neighbors(self, node_id: str, direction: str = "out") -> list[str]:
        """获取邻居节点。"""
        with self._lock:
            if direction == "out":
                return list(self._out_edges.get(node_id, {}).keys())
            elif direction == "in":
                return list(self._in_edges.get(node_id, {}).keys())
            else:  # both
                out_set = set(self._out_edges.get(node_id, {}).keys())
                in_set = set(self._in_edges.get(node_id, {}).keys())
                return list(out_set | in_set)

    def edges_between(self, source_id: str, target_id: str) -> list[tuple[str, str, float]]:
        """获取两个节点之间的所有边。"""
        with self._lock:
            return list(self._out_edges.get(source_id, {}).get(target_id, []))

    def find_path(self, source_id: str, target_id: str,
                  max_depth: int = 6) -> Optional[list[str]]:
        """BFS 查找最短路径。

        Args:
            source_id: 起点节点 ID。
            target_id: 终点节点 ID。
            max_depth: 最大搜索深度。

        Returns:
            路径节点 ID 列表，或 None（不存在路径）。
        """
        with self._lock:
            if source_id == target_id:
                return [source_id]
            visited: set[str] = {source_id}
            queue: deque[tuple[str, list[str]]] = deque([(source_id, [source_id])])
            depth = 0
            while queue and depth < max_depth:
                depth += 1
                level_size = len(queue)
                for _ in range(level_size):
                    current, path = queue.popleft()
                    for neighbor in self._out_edges.get(current, {}).keys():
                        if neighbor == target_id:
                            return path + [neighbor]
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append((neighbor, path + [neighbor]))
            return None

    def find_all_paths(self, source_id: str, target_id: str,
                       max_depth: int = 4, limit: int = 10) -> list[list[str]]:
        """DFS 查找所有路径（限制数量与深度）。"""
        with self._lock:
            results: list[list[str]] = []
            visited: set[str] = set()

            def dfs(node: str, path: list[str]) -> None:
                if len(results) >= limit:
                    return
                if node == target_id:
                    results.append(list(path))
                    return
                if len(path) > max_depth:
                    return
                visited.add(node)
                for neighbor in self._out_edges.get(node, {}).keys():
                    if neighbor not in visited:
                        path.append(neighbor)
                        dfs(neighbor, path)
                        path.pop()
                visited.discard(node)

            dfs(source_id, [source_id])
            return results

    def subgraph(self, node_ids: Iterable[str]) -> dict[str, Any]:
        """提取子图。"""
        with self._lock:
            node_set = set(node_ids)
            nodes = list(node_set)
            edges: list[dict[str, Any]] = []
            for src in node_set:
                for tgt, edge_list in self._out_edges.get(src, {}).items():
                    if tgt in node_set:
                        for _, rel_type, weight in edge_list:
                            edges.append({
                                "source": src,
                                "target": tgt,
                                "relation": rel_type,
                                "weight": weight,
                            })
            return {"nodes": nodes, "edges": edges}

    def node_degree(self, node_id: str) -> dict[str, int]:
        """返回节点的入度、出度、总度数。"""
        with self._lock:
            out_deg = sum(len(edges) for edges in self._out_edges.get(node_id, {}).values())
            in_deg = sum(len(edges) for edges in self._in_edges.get(node_id, {}).values())
            return {"in_degree": in_deg, "out_degree": out_deg, "total": in_deg + out_deg}

    def stats(self) -> dict[str, int]:
        """返回图谱统计信息。"""
        with self._lock:
            node_count = len(set(self._out_edges.keys()) | set(self._in_edges.keys()))
            edge_count = sum(
                len(edges)
                for targets in self._out_edges.values()
                for edges in targets.values()
            )
            return {"nodes": node_count, "edges": edge_count}


# ===== 知识库主类 =====


class KnowledgeBase:
    """知识库主类。

    管理学科知识库、论题模板库、方法库的统一入口，提供：
        - 知识条目 CRUD
        - 分类树管理
        - 全文检索（TF-IDF）
        - 知识图谱构建与查询
        - 版本管理与变更历史
        - 批量导入导出
        - 内存缓存优化

    线程安全：所有公共方法通过 RLock 保护。
    """

    def __init__(self, cache_size: int = DEFAULT_CACHE_SIZE) -> None:
        """初始化知识库。

        Args:
            cache_size: LRU 缓存容量。
        """
        self._lock = threading.RLock()
        self._cache = LRUCache(cache_size)
        self._tfidf = TFIDFIndex()
        self._graph = KnowledgeGraph()
        # 内存索引：entry_id -> KnowledgeEntry
        self._entries: dict[str, KnowledgeEntry] = {}
        # category_id -> KnowledgeCategory
        self._categories: dict[str, KnowledgeCategory] = {}
        # tag -> set of entry_id
        self._tag_index: dict[str, set[str]] = defaultdict(set)
        # keyword -> set of entry_id
        self._keyword_index: dict[str, set[str]] = defaultdict(set)
        # entry_id -> list of KnowledgeVersion
        self._versions: dict[str, list[KnowledgeVersion]] = defaultdict(list)
        # 初始化根分类
        self._init_root_category()
        # 从数据库加载
        self._load_from_db()

    def _init_root_category(self) -> None:
        """初始化根分类。"""
        root_id = "cat_root"
        if root_id not in self._categories:
            self._categories[root_id] = KnowledgeCategory(
                id=root_id,
                name=DEFAULT_ROOT_CATEGORY,
                parent_id="",
                level=0,
                description="知识库根分类",
                sort_order=0,
            )

    def _load_from_db(self) -> None:
        """从数据库加载已有数据到内存索引。"""
        try:
            rows = fetch_all("SELECT * FROM knowledge_entries;")
            for row in rows:
                entry = self._row_to_entry(row)
                self._entries[entry.id] = entry
                self._index_entry(entry)
            # 加载分类
            cat_rows = fetch_all("SELECT * FROM knowledge_categories;")
            for row in cat_rows:
                cat = KnowledgeCategory(
                    id=row["id"],
                    name=row["name"],
                    parent_id=row["parent_id"],
                    level=row["level"],
                    description=row.get("description", ""),
                    sort_order=row.get("sort_order", 0),
                )
                children_raw = row.get("children", "[]")
                try:
                    cat.children = json.loads(children_raw) if children_raw else []
                except (json.JSONDecodeError, TypeError):
                    cat.children = []
                self._categories[cat.id] = cat
            # 加载关系
            rel_rows = fetch_all("SELECT * FROM knowledge_relations;")
            for row in rel_rows:
                self._graph.add_edge(
                    row["source_id"],
                    row["target_id"],
                    row["relation_type"],
                    float(row.get("weight", 1.0)),
                )
        except Exception:
            # 表可能尚未创建，忽略
            pass

    def _row_to_entry(self, row: dict) -> KnowledgeEntry:
        """将数据库行转换为 KnowledgeEntry。"""
        def _parse_json(raw: Any, default: Any) -> Any:
            if isinstance(raw, (dict, list)):
                return raw
            if not raw:
                return default
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return default

        return KnowledgeEntry(
            id=row["id"],
            title=row["title"],
            content=row.get("content", ""),
            category_id=row.get("category_id", ""),
            tags=_parse_json(row.get("tags"), []),
            keywords=_parse_json(row.get("keywords"), []),
            discipline=row.get("discipline", ""),
            source=row.get("source", ""),
            author=row.get("author", ""),
            version=int(row.get("version", 1)),
            created_at=row.get("created_at", ""),
            updated_at=row.get("updated_at", ""),
            metadata=_parse_json(row.get("metadata"), {}),
            view_count=int(row.get("view_count", 0)),
            quality_score=float(row.get("quality_score", 0.0)),
        )

    def _index_entry(self, entry: KnowledgeEntry) -> None:
        """将条目加入内存索引（标签、关键词、TF-IDF）。"""
        for tag in entry.tags:
            self._tag_index[tag].add(entry.id)
        for kw in entry.keywords:
            self._keyword_index[kw].add(entry.id)
        # TF-IDF 索引：标题权重更高
        index_text = entry.title + " " + entry.title + " " + entry.content
        self._tfidf.add_document(entry.id, index_text)

    def _unindex_entry(self, entry_id: str) -> None:
        """从内存索引移除条目。"""
        entry = self._entries.get(entry_id)
        if not entry:
            return
        for tag in entry.tags:
            self._tag_index[tag].discard(entry_id)
            if not self._tag_index[tag]:
                del self._tag_index[tag]
        for kw in entry.keywords:
            self._keyword_index[kw].discard(entry_id)
            if not self._keyword_index[kw]:
                del self._keyword_index[kw]
        self._tfidf.remove_document(entry_id)

    # ===== 条目 CRUD =====

    def create_entry(self, title: str, content: str, category_id: str = "",
                     tags: Optional[list[str]] = None, keywords: Optional[list[str]] = None,
                     discipline: str = "", source: str = "", author: str = "",
                     metadata: Optional[dict[str, Any]] = None) -> str:
        """创建知识条目。

        Args:
            title: 标题（不超过 MAX_TITLE_LENGTH 字符）。
            content: 正文内容。
            category_id: 所属分类 ID。
            tags: 标签列表。
            keywords: 关键词列表。
            discipline: 关联学科代码。
            source: 来源信息。
            author: 创建者。
            metadata: 扩展元数据。

        Returns:
            新建条目的 ID。

        Raises:
            ValueError: 标题或内容为空，或长度超限。
        """
        if not title or not title.strip():
            raise ValueError("标题不能为空")
        if len(title) > MAX_TITLE_LENGTH:
            raise ValueError(f"标题长度超过限制 {MAX_TITLE_LENGTH}")
        if not content or not content.strip():
            raise ValueError("内容不能为空")
        if len(content) > MAX_CONTENT_LENGTH:
            raise ValueError(f"内容长度超过限制 {MAX_CONTENT_LENGTH}")

        with self._lock:
            entry_id = _new_id("entry")
            now = _now_iso()
            # 若未提供关键词，自动从内容提取
            if keywords is None:
                keywords = self._extract_keywords(content)
            entry = KnowledgeEntry(
                id=entry_id,
                title=title.strip(),
                content=content,
                category_id=category_id or "cat_root",
                tags=tags or [],
                keywords=keywords,
                discipline=discipline,
                source=source,
                author=author,
                version=1,
                created_at=now,
                updated_at=now,
                metadata=metadata or {},
                view_count=0,
                quality_score=0.0,
            )
            # 持久化
            try:
                execute_insert("knowledge_entries", entry.to_dict())
            except Exception:
                # 表可能不存在，使用 knowledge_cards 表兜底
                pass
            # 内存索引
            self._entries[entry_id] = entry
            self._index_entry(entry)
            # 创建初始版本
            self._save_version(entry, author, "初始创建", "新建条目")
            # 更新分类的子条目计数（通过 metadata）
            self._cache.invalidate(f"category_entries:{entry.category_id}")
            return entry_id

    def get_entry(self, entry_id: str, increment_view: bool = False) -> Optional[KnowledgeEntry]:
        """获取知识条目。

        Args:
            entry_id: 条目 ID。
            increment_view: 是否增加浏览次数。

        Returns:
            条目实例，或 None（不存在）。
        """
        with self._lock:
            # 先查缓存
            cached = self._cache.get(f"entry:{entry_id}")
            if cached is not None:
                if increment_view:
                    cached.view_count += 1
                    self._update_view_count(entry_id)
                return cached
            entry = self._entries.get(entry_id)
            if entry is None:
                # 尝试从数据库加载
                row = fetch_one(
                    "SELECT * FROM knowledge_entries WHERE id = ?;", (entry_id,)
                )
                if row:
                    entry = self._row_to_entry(row)
                    self._entries[entry_id] = entry
                    self._index_entry(entry)
            if entry is not None:
                if increment_view:
                    entry.view_count += 1
                    self._update_view_count(entry_id)
                self._cache.put(f"entry:{entry_id}", entry)
            return entry

    def _update_view_count(self, entry_id: str) -> None:
        """更新浏览次数到数据库。"""
        try:
            execute_query(
                "UPDATE knowledge_entries SET view_count = view_count + 1 WHERE id = ?;",
                (entry_id,),
            )
        except Exception:
            pass

    def update_entry(self, entry_id: str, title: Optional[str] = None,
                     content: Optional[str] = None, tags: Optional[list[str]] = None,
                     keywords: Optional[list[str]] = None, category_id: Optional[str] = None,
                     discipline: Optional[str] = None, source: Optional[str] = None,
                     author: str = "", change_note: str = "",
                     metadata: Optional[dict[str, Any]] = None) -> bool:
        """更新知识条目（创建新版本）。

        Args:
            entry_id: 条目 ID。
            title: 新标题（None 表示不修改）。
            content: 新内容。
            tags: 新标签。
            keywords: 新关键词。
            category_id: 新分类。
            discipline: 新学科。
            source: 新来源。
            author: 修改者。
            change_note: 变更说明。
            metadata: 新元数据。

        Returns:
            是否更新成功。
        """
        with self._lock:
            entry = self._entries.get(entry_id)
            if entry is None:
                entry = self.get_entry(entry_id)
                if entry is None:
                    return False
            # 校验
            if title is not None:
                if not title.strip():
                    raise ValueError("标题不能为空")
                if len(title) > MAX_TITLE_LENGTH:
                    raise ValueError(f"标题长度超过限制 {MAX_TITLE_LENGTH}")
            if content is not None and len(content) > MAX_CONTENT_LENGTH:
                raise ValueError(f"内容长度超过限制 {MAX_CONTENT_LENGTH}")
            # 保存旧版本
            old_entry = KnowledgeEntry.from_dict(entry.to_dict())
            self._save_version(old_entry, author, change_note,
                               self._compute_diff_summary(old_entry, entry))
            # 应用更新
            if title is not None:
                entry.title = title.strip()
            if content is not None:
                entry.content = content
            if tags is not None:
                entry.tags = tags
            if keywords is not None:
                entry.keywords = keywords
            elif content is not None:
                entry.keywords = self._extract_keywords(content)
            if category_id is not None:
                entry.category_id = category_id
            if discipline is not None:
                entry.discipline = discipline
            if source is not None:
                entry.source = source
            if metadata is not None:
                entry.metadata = metadata
            entry.version += 1
            entry.updated_at = _now_iso()
            # 重新索引
            self._unindex_entry(entry_id)
            self._index_entry(entry)
            # 持久化
            try:
                self._persist_entry(entry)
            except Exception:
                pass
            # 失效缓存
            self._cache.invalidate(f"entry:{entry_id}")
            return True

    def delete_entry(self, entry_id: str) -> bool:
        """删除知识条目。

        Args:
            entry_id: 条目 ID。

        Returns:
            是否删除成功。
        """
        with self._lock:
            entry = self._entries.get(entry_id)
            if entry is None:
                return False
            # 移除索引
            self._unindex_entry(entry_id)
            # 移除图谱中的节点
            self._graph.remove_node(entry_id)
            # 移除版本记录
            self._versions.pop(entry_id, None)
            # 移除内存
            del self._entries[entry_id]
            # 持久化删除
            try:
                execute_query(
                    "DELETE FROM knowledge_entries WHERE id = ?;", (entry_id,)
                )
                execute_query(
                    "DELETE FROM knowledge_versions WHERE entry_id = ?;", (entry_id,)
                )
                execute_query(
                    "DELETE FROM knowledge_relations WHERE source_id = ? OR target_id = ?;",
                    (entry_id, entry_id),
                )
            except Exception:
                pass
            # 失效缓存
            self._cache.invalidate(f"entry:{entry_id}")
            self._cache.invalidate(f"category_entries:{entry.category_id}")
            return True

    def _persist_entry(self, entry: KnowledgeEntry) -> None:
        """持久化条目到数据库（upsert）。"""
        data = entry.to_dict()
        # 先尝试删除再插入（简单 upsert）
        try:
            execute_query(
                "DELETE FROM knowledge_entries WHERE id = ?;", (entry.id,)
            )
            execute_insert("knowledge_entries", data)
        except Exception:
            pass

    def _save_version(self, entry: KnowledgeEntry, author: str,
                      change_note: str, diff_summary: str) -> None:
        """保存条目版本快照。"""
        version = KnowledgeVersion(
            version_id=_new_id("ver"),
            entry_id=entry.id,
            version=entry.version,
            title=entry.title,
            content=entry.content,
            author=author or entry.author,
            timestamp=_now_iso(),
            change_note=change_note,
            diff_summary=diff_summary,
        )
        self._versions[entry.id].append(version)
        try:
            execute_insert("knowledge_versions", version.to_dict())
        except Exception:
            pass

    def _compute_diff_summary(self, old: KnowledgeEntry, new: KnowledgeEntry) -> str:
        """计算两个版本的变更摘要。"""
        changes: list[str] = []
        if old.title != new.title:
            changes.append(f"标题变更")
        if old.content != new.content:
            # 计算内容变化比例
            old_len = len(old.content)
            new_len = len(new.content)
            dist = _levenshtein(old.content[:1000], new.content[:1000])
            ratio = dist / max(old_len, new_len, 1)
            changes.append(f"内容变更(相似度{1 - ratio:.2%})")
        if set(old.tags) != set(new.tags):
            changes.append(f"标签变更")
        if old.category_id != new.category_id:
            changes.append(f"分类变更")
        return "; ".join(changes) if changes else "无显著变更"

    def _extract_keywords(self, content: str, top_k: int = 10) -> list[str]:
        """从内容提取关键词（基于词频）。

        Args:
            content: 文本内容。
            top_k: 返回关键词数量。

        Returns:
            关键词列表。
        """
        tokens = _tokenize(content)
        if not tokens:
            return []
        freq: dict[str, int] = defaultdict(int)
        for t in tokens:
            freq[t] += 1
        # 按频率排序
        sorted_kw = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return [kw for kw, _ in sorted_kw[:top_k]]

    # ===== 分类管理 =====

    def create_category(self, name: str, parent_id: str = "cat_root",
                        description: str = "", sort_order: int = 0) -> str:
        """创建知识分类。

        Args:
            name: 分类名称。
            parent_id: 父分类 ID（默认根分类）。
            description: 分类描述。
            sort_order: 排序序号。

        Returns:
            新建分类 ID。

        Raises:
            ValueError: 名称为空或父分类不存在。
        """
        if not name or not name.strip():
            raise ValueError("分类名称不能为空")
        with self._lock:
            if parent_id and parent_id not in self._categories:
                raise ValueError(f"父分类不存在: {parent_id}")
            parent = self._categories[parent_id]
            cat_id = _new_id("cat")
            category = KnowledgeCategory(
                id=cat_id,
                name=name.strip(),
                parent_id=parent_id,
                level=parent.level + 1,
                description=description,
                sort_order=sort_order,
            )
            self._categories[cat_id] = category
            parent.children.append(cat_id)
            # 持久化
            try:
                execute_insert("knowledge_categories", category.to_dict())
                self._persist_category_children(parent)
            except Exception:
                pass
            return cat_id

    def _persist_category_children(self, category: KnowledgeCategory) -> None:
        """持久化分类的 children 字段。"""
        try:
            execute_query(
                "UPDATE knowledge_categories SET children = ? WHERE id = ?;",
                (json.dumps(category.children, ensure_ascii=False), category.id),
            )
        except Exception:
            pass

    def get_category(self, category_id: str) -> Optional[KnowledgeCategory]:
        """获取分类。"""
        with self._lock:
            return self._categories.get(category_id)

    def list_categories(self, parent_id: Optional[str] = None) -> list[KnowledgeCategory]:
        """列出分类。

        Args:
            parent_id: 父分类 ID。None 表示所有分类。

        Returns:
            分类列表。
        """
        with self._lock:
            if parent_id is None:
                return list(self._categories.values())
            return [c for c in self._categories.values() if c.parent_id == parent_id]

    def get_category_tree(self, root_id: str = "cat_root") -> dict[str, Any]:
        """获取分类树结构。

        Args:
            root_id: 根分类 ID。

        Returns:
            嵌套的树结构字典。
        """
        with self._lock:
            def build_node(cat_id: str) -> dict[str, Any]:
                cat = self._categories.get(cat_id)
                if not cat:
                    return {}
                children = [build_node(cid) for cid in cat.children]
                return {
                    "id": cat.id,
                    "name": cat.name,
                    "level": cat.level,
                    "description": cat.description,
                    "sort_order": cat.sort_order,
                    "children": children,
                }
            return build_node(root_id)

    def delete_category(self, category_id: str, recursive: bool = False) -> bool:
        """删除分类。

        Args:
            category_id: 分类 ID。
            recursive: 是否递归删除子分类。

        Returns:
            是否删除成功。
        """
        if category_id == "cat_root":
            return False
        with self._lock:
            cat = self._categories.get(category_id)
            if cat is None:
                return False
            # 检查子分类
            if cat.children and not recursive:
                raise ValueError("分类下有子分类，请先删除子分类或使用递归模式")
            # 递归删除子分类
            for child_id in list(cat.children):
                self.delete_category(child_id, recursive=True)
            # 将该分类下的条目移至父分类
            parent_id = cat.parent_id or "cat_root"
            for entry in self._entries.values():
                if entry.category_id == category_id:
                    entry.category_id = parent_id
                    try:
                        self._persist_entry(entry)
                    except Exception:
                        pass
            # 从父分类的 children 中移除
            parent = self._categories.get(parent_id)
            if parent and category_id in parent.children:
                parent.children.remove(category_id)
                self._persist_category_children(parent)
            # 删除分类
            del self._categories[category_id]
            try:
                execute_query(
                    "DELETE FROM knowledge_categories WHERE id = ?;", (category_id,)
                )
            except Exception:
                pass
            return True

    def list_entries_by_category(self, category_id: str,
                                 include_subcategories: bool = True) -> list[KnowledgeEntry]:
        """列出分类下的条目。

        Args:
            category_id: 分类 ID。
            include_subcategories: 是否包含子分类的条目。

        Returns:
            条目列表。
        """
        cache_key = f"category_entries:{category_id}:{include_subcategories}"
        with self._lock:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached
            target_ids = {category_id}
            if include_subcategories:
                # 递归收集子分类
                stack = [category_id]
                while stack:
                    cid = stack.pop()
                    cat = self._categories.get(cid)
                    if cat:
                        for child_id in cat.children:
                            target_ids.add(child_id)
                            stack.append(child_id)
            result = [e for e in self._entries.values() if e.category_id in target_ids]
            self._cache.put(cache_key, result)
            return result

    # ===== 检索 =====

    def search(self, query: str, limit: int = DEFAULT_SEARCH_LIMIT,
               category_id: Optional[str] = None,
               tags: Optional[list[str]] = None) -> list[dict[str, Any]]:
        """全文检索知识条目。

        Args:
            query: 查询文本。
            limit: 返回数量上限。
            category_id: 限定分类。
            tags: 限定标签（任一匹配）。

        Returns:
            检索结果列表，每项包含 entry 与 score。
        """
        with self._lock:
            results = self._tfidf.search(query, limit=limit * 2)
            output: list[dict[str, Any]] = []
            for entry_id, score in results:
                entry = self._entries.get(entry_id)
                if entry is None:
                    continue
                # 过滤分类
                if category_id and entry.category_id != category_id:
                    continue
                # 过滤标签
                if tags:
                    if not set(tags) & set(entry.tags):
                        continue
                output.append({
                    "entry": entry.to_dict(),
                    "score": round(score, 4),
                    "summary": entry.summary(),
                })
                if len(output) >= limit:
                    break
            return output

    def search_by_tag(self, tag: str) -> list[KnowledgeEntry]:
        """按标签检索。"""
        with self._lock:
            entry_ids = self._tag_index.get(tag, set())
            return [self._entries[eid] for eid in entry_ids if eid in self._entries]

    def search_by_keyword(self, keyword: str) -> list[KnowledgeEntry]:
        """按关键词检索。"""
        with self._lock:
            entry_ids = self._keyword_index.get(keyword, set())
            return [self._entries[eid] for eid in entry_ids if eid in self._entries]

    def search_by_discipline(self, discipline: str) -> list[KnowledgeEntry]:
        """按学科检索。"""
        with self._lock:
            return [e for e in self._entries.values() if e.discipline == discipline]

    # ===== 知识图谱 =====

    def add_relation(self, source_id: str, target_id: str,
                     relation_type: str = "relates_to", weight: float = 1.0,
                     metadata: Optional[dict[str, Any]] = None) -> Optional[str]:
        """添加知识条目间的关系。

        Args:
            source_id: 源条目 ID。
            target_id: 目标条目 ID。
            relation_type: 关系类型。
            weight: 权重（0-1）。
            metadata: 扩展元数据。

        Returns:
            关系 ID，或 None（条目不存在）。
        """
        if relation_type not in RELATION_TYPES:
            raise ValueError(f"未知关系类型: {relation_type}")
        with self._lock:
            if source_id not in self._entries or target_id not in self._entries:
                return None
            rel_id = _new_id("rel")
            relation = KnowledgeRelation(
                id=rel_id,
                source_id=source_id,
                target_id=target_id,
                relation_type=relation_type,
                weight=max(0.0, min(1.0, weight)),
                created_at=_now_iso(),
                metadata=metadata or {},
            )
            self._graph.add_edge(source_id, target_id, relation_type, weight)
            try:
                execute_insert("knowledge_relations", relation.to_dict())
            except Exception:
                pass
            return rel_id

    def remove_relation(self, source_id: str, target_id: str,
                        relation_type: Optional[str] = None) -> int:
        """移除关系。"""
        with self._lock:
            removed = self._graph.remove_edge(source_id, target_id, relation_type)
            if removed > 0:
                try:
                    if relation_type:
                        execute_query(
                            "DELETE FROM knowledge_relations WHERE source_id = ? "
                            "AND target_id = ? AND relation_type = ?;",
                            (source_id, target_id, relation_type),
                        )
                    else:
                        execute_query(
                            "DELETE FROM knowledge_relations WHERE source_id = ? "
                            "AND target_id = ?;",
                            (source_id, target_id),
                        )
                except Exception:
                    pass
            return removed

    def get_relations(self, entry_id: str, direction: str = "both") -> list[dict[str, Any]]:
        """获取条目的所有关系。"""
        with self._lock:
            result: list[dict[str, Any]] = []
            if direction in ("out", "both"):
                for target_id in self._graph.neighbors(entry_id, "out"):
                    for _, rel_type, weight in self._graph.edges_between(entry_id, target_id):
                        result.append({
                            "source_id": entry_id,
                            "target_id": target_id,
                            "relation_type": rel_type,
                            "weight": weight,
                            "direction": "outgoing",
                        })
            if direction in ("in", "both"):
                for source_id in self._graph.neighbors(entry_id, "in"):
                    for _, rel_type, weight in self._graph.edges_between(source_id, entry_id):
                        result.append({
                            "source_id": source_id,
                            "target_id": entry_id,
                            "relation_type": rel_type,
                            "weight": weight,
                            "direction": "incoming",
                        })
            return result

    def find_path(self, source_id: str, target_id: str, max_depth: int = 6) -> Optional[list[str]]:
        """查找两个条目间的最短路径。"""
        with self._lock:
            return self._graph.find_path(source_id, target_id, max_depth)

    def find_all_paths(self, source_id: str, target_id: str,
                       max_depth: int = 4, limit: int = 10) -> list[list[str]]:
        """查找所有路径。"""
        with self._lock:
            return self._graph.find_all_paths(source_id, target_id, max_depth, limit)

    def get_related_entries(self, entry_id: str, depth: int = 1) -> list[KnowledgeEntry]:
        """获取相关条目（BFS 扩展）。"""
        with self._lock:
            if entry_id not in self._entries:
                return []
            visited: set[str] = {entry_id}
            current_level = {entry_id}
            for _ in range(depth):
                next_level: set[str] = set()
                for nid in current_level:
                    for neighbor in self._graph.neighbors(nid):
                        if neighbor not in visited:
                            visited.add(neighbor)
                            next_level.add(neighbor)
                current_level = next_level
                if not current_level:
                    break
            visited.discard(entry_id)
            return [self._entries[eid] for eid in visited if eid in self._entries]

    def get_graph_subgraph(self, entry_ids: Iterable[str]) -> dict[str, Any]:
        """提取子图。"""
        with self._lock:
            sub = self._graph.subgraph(entry_ids)
            # 补充节点信息
            nodes = []
            for nid in sub["nodes"]:
                entry = self._entries.get(nid)
                if entry:
                    nodes.append({
                        "id": entry.id,
                        "title": entry.title,
                        "category_id": entry.category_id,
                    })
            return {"nodes": nodes, "edges": sub["edges"]}

    # ===== 版本管理 =====

    def get_version_history(self, entry_id: str) -> list[KnowledgeVersion]:
        """获取条目的版本历史。"""
        with self._lock:
            return list(self._versions.get(entry_id, []))

    def get_version(self, entry_id: str, version: int) -> Optional[KnowledgeVersion]:
        """获取指定版本。"""
        with self._lock:
            for v in self._versions.get(entry_id, []):
                if v.version == version:
                    return v
            return None

    def rollback_to_version(self, entry_id: str, version: int,
                            author: str = "", note: str = "") -> bool:
        """回滚到指定版本。

        Args:
            entry_id: 条目 ID。
            version: 目标版本号。
            author: 操作者。
            note: 回滚说明。

        Returns:
            是否回滚成功。
        """
        with self._lock:
            entry = self._entries.get(entry_id)
            if entry is None:
                return False
            target_version = self.get_version(entry_id, version)
            if target_version is None:
                return False
            # 保存当前版本
            self._save_version(entry, author, note or f"回滚前备份",
                               f"回滚到版本 {version} 前的备份")
            # 应用旧版本内容
            entry.title = target_version.title
            entry.content = target_version.content
            entry.version += 1
            entry.updated_at = _now_iso()
            # 重新索引
            self._unindex_entry(entry_id)
            self._index_entry(entry)
            try:
                self._persist_entry(entry)
            except Exception:
                pass
            self._cache.invalidate(f"entry:{entry_id}")
            return True

    def resolve_conflict(self, entry_id: str, base_version: int,
                         their_version: int, resolution: str = "theirs",
                         author: str = "") -> bool:
        """解决版本冲突。

        Args:
            entry_id: 条目 ID。
            base_version: 基础版本。
            their_version: 对方版本。
            resolution: 解决策略（"ours" / "theirs" / "merge"）。
            author: 操作者。

        Returns:
            是否解决成功。
        """
        with self._lock:
            base = self.get_version(entry_id, base_version)
            theirs = self.get_version(entry_id, their_version)
            if base is None or theirs is None:
                return False
            entry = self._entries.get(entry_id)
            if entry is None:
                return False
            if resolution == "theirs":
                entry.title = theirs.title
                entry.content = theirs.content
            elif resolution == "ours":
                # 保持当前不变
                pass
            elif resolution == "merge":
                # 简单合并：标题用 theirs，内容拼接
                entry.title = theirs.title
                entry.content = (
                    f"{entry.content}\n\n--- 合并自版本 {their_version} ---\n\n"
                    f"{theirs.content}"
                )
            else:
                return False
            entry.version += 1
            entry.updated_at = _now_iso()
            self._save_version(entry, author, "冲突解决",
                               f"基础版本 {base_version}，对方版本 {their_version}，策略 {resolution}")
            self._unindex_entry(entry_id)
            self._index_entry(entry)
            try:
                self._persist_entry(entry)
            except Exception:
                pass
            self._cache.invalidate(f"entry:{entry_id}")
            return True

    # ===== 批量导入导出 =====

    def export_to_json(self, file_path: str,
                       category_id: Optional[str] = None) -> int:
        """导出知识库到 JSON 文件。

        Args:
            file_path: 目标文件路径。
            category_id: 限定分类（None 表示全部）。

        Returns:
            导出条目数量。
        """
        with self._lock:
            if category_id:
                entries = self.list_entries_by_category(category_id)
            else:
                entries = list(self._entries.values())
            data = {
                "version": "8.0",
                "exported_at": _now_iso(),
                "entries": [e.to_dict() for e in entries],
                "categories": [c.to_dict() for c in self._categories.values()],
            }
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return len(entries)

    def import_from_json(self, file_path: str,
                         overwrite: bool = False) -> dict[str, int]:
        """从 JSON 文件导入知识库。

        Args:
            file_path: 源文件路径。
            overwrite: 是否覆盖已存在条目。

        Returns:
            统计信息（created / updated / skipped）。
        """
        with self._lock:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            stats = {"created": 0, "updated": 0, "skipped": 0}
            # 导入分类
            for cat_data in data.get("categories", []):
                cat = KnowledgeCategory(**cat_data)
                if cat.id not in self._categories:
                    self._categories[cat.id] = cat
                    try:
                        execute_insert("knowledge_categories", cat.to_dict())
                    except Exception:
                        pass
            # 导入条目
            for entry_data in data.get("entries", []):
                entry = KnowledgeEntry.from_dict(entry_data)
                if entry.id in self._entries:
                    if overwrite:
                        self._entries[entry.id] = entry
                        self._unindex_entry(entry.id)
                        self._index_entry(entry)
                        try:
                            self._persist_entry(entry)
                        except Exception:
                            pass
                        stats["updated"] += 1
                    else:
                        stats["skipped"] += 1
                else:
                    self._entries[entry.id] = entry
                    self._index_entry(entry)
                    try:
                        execute_insert("knowledge_entries", entry.to_dict())
                    except Exception:
                        pass
                    stats["created"] += 1
            return stats

    def export_to_csv(self, file_path: str,
                      category_id: Optional[str] = None) -> int:
        """导出知识库到 CSV 文件。"""
        with self._lock:
            if category_id:
                entries = self.list_entries_by_category(category_id)
            else:
                entries = list(self._entries.values())
            fieldnames = [
                "id", "title", "content", "category_id", "tags",
                "keywords", "discipline", "source", "author",
                "version", "created_at", "updated_at", "quality_score",
            ]
            with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for entry in entries:
                    row = entry.to_dict()
                    row["tags"] = ";".join(entry.tags)
                    row["keywords"] = ";".join(entry.keywords)
                    writer.writerow({k: row.get(k, "") for k in fieldnames})
            return len(entries)

    def import_from_csv(self, file_path: str,
                        overwrite: bool = False) -> dict[str, int]:
        """从 CSV 文件导入知识库。"""
        with self._lock:
            stats = {"created": 0, "updated": 0, "skipped": 0}
            with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    tags = [t.strip() for t in row.get("tags", "").split(";") if t.strip()]
                    keywords = [k.strip() for k in row.get("keywords", "").split(";") if k.strip()]
                    entry_id = row.get("id", "")
                    if entry_id and entry_id in self._entries:
                        if overwrite:
                            entry = self._entries[entry_id]
                            entry.title = row.get("title", entry.title)
                            entry.content = row.get("content", entry.content)
                            entry.tags = tags
                            entry.keywords = keywords
                            entry.discipline = row.get("discipline", entry.discipline)
                            entry.version += 1
                            entry.updated_at = _now_iso()
                            self._unindex_entry(entry_id)
                            self._index_entry(entry)
                            try:
                                self._persist_entry(entry)
                            except Exception:
                                pass
                            stats["updated"] += 1
                        else:
                            stats["skipped"] += 1
                    else:
                        new_id = entry_id or _new_id("entry")
                        now = _now_iso()
                        entry = KnowledgeEntry(
                            id=new_id,
                            title=row.get("title", ""),
                            content=row.get("content", ""),
                            category_id=row.get("category_id", "cat_root"),
                            tags=tags,
                            keywords=keywords,
                            discipline=row.get("discipline", ""),
                            source=row.get("source", ""),
                            author=row.get("author", ""),
                            version=int(row.get("version", 1)),
                            created_at=row.get("created_at", now),
                            updated_at=now,
                        )
                        self._entries[new_id] = entry
                        self._index_entry(entry)
                        try:
                            execute_insert("knowledge_entries", entry.to_dict())
                        except Exception:
                            pass
                        stats["created"] += 1
            return stats

    def export_to_yaml(self, file_path: str,
                       category_id: Optional[str] = None) -> int:
        """导出知识库到 YAML 文件（无 PyYAML 依赖，手写简易序列化）。"""
        with self._lock:
            if category_id:
                entries = self.list_entries_by_category(category_id)
            else:
                entries = list(self._entries.values())
            lines: list[str] = []
            lines.append("version: '8.0'")
            lines.append(f"exported_at: '{_now_iso()}'")
            lines.append("entries:")
            for entry in entries:
                lines.append(f"  - id: {entry.id}")
                lines.append(f"    title: {_yaml_escape(entry.title)}")
                lines.append(f"    content: {_yaml_escape(entry.content)}")
                lines.append(f"    category_id: {entry.category_id}")
                lines.append(f"    discipline: {entry.discipline}")
                lines.append(f"    source: {_yaml_escape(entry.source)}")
                lines.append(f"    author: {_yaml_escape(entry.author)}")
                lines.append(f"    version: {entry.version}")
                if entry.tags:
                    lines.append("    tags:")
                    for t in entry.tags:
                        lines.append(f"      - {_yaml_escape(t)}")
                if entry.keywords:
                    lines.append("    keywords:")
                    for k in entry.keywords:
                        lines.append(f"      - {_yaml_escape(k)}")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            return len(entries)

    # ===== 统计与维护 =====

    def stats(self) -> dict[str, Any]:
        """返回知识库统计信息。"""
        with self._lock:
            return {
                "total_entries": len(self._entries),
                "total_categories": len(self._categories),
                "total_versions": sum(len(v) for v in self._versions.values()),
                "total_relations": self._graph.stats()["edges"],
                "vocabulary_size": self._tfidf.vocabulary_size(),
                "cache_stats": self._cache.stats(),
                "top_tags": self._top_tags(10),
                "top_keywords": self._top_keywords(10),
            }

    def _top_tags(self, limit: int = 10) -> list[tuple[str, int]]:
        """返回使用最多的标签。"""
        return sorted(
            ((tag, len(ids)) for tag, ids in self._tag_index.items()),
            key=lambda x: x[1],
            reverse=True,
        )[:limit]

    def _top_keywords(self, limit: int = 10) -> list[tuple[str, int]]:
        """返回使用最多的关键词。"""
        return sorted(
            ((kw, len(ids)) for kw, ids in self._keyword_index.items()),
            key=lambda x: x[1],
            reverse=True,
        )[:limit]

    def clear_cache(self) -> None:
        """清空缓存。"""
        with self._lock:
            self._cache.clear()

    def rebuild_index(self) -> None:
        """重建所有内存索引。"""
        with self._lock:
            self._tag_index.clear()
            self._keyword_index.clear()
            # 重建 TF-IDF
            docs = list(self._tfidf._doc_tokens.keys())
            for doc_id in docs:
                self._tfidf.remove_document(doc_id)
            for entry in self._entries.values():
                self._index_entry(entry)
            self._cache.clear()


def _yaml_escape(text: str) -> str:
    """YAML 字符串转义。"""
    if not text:
        return "''"
    # 含特殊字符则用引号包裹
    if any(c in text for c in [":", "#", "-", "{", "}", "[", "]", ",", "&", "*", "!", "|", ">", "'", '"', "%", "@", "`"]):
        escaped = text.replace("'", "''")
        return f"'{escaped}'"
    return text


# ===== 模块级单例 =====


_global_instance: Optional[KnowledgeBase] = None
_global_lock = threading.Lock()


def get_knowledge_base() -> KnowledgeBase:
    """获取全局知识库单例。"""
    global _global_instance
    if _global_instance is None:
        with _global_lock:
            if _global_instance is None:
                _global_instance = KnowledgeBase()
    return _global_instance


def reset_knowledge_base() -> None:
    """重置全局单例（主要用于测试）。"""
    global _global_instance
    with _global_lock:
        _global_instance = None
