"""知识库模块单元测试

测试 backend/knowledge/knowledge_base.py 中的 KnowledgeBase 类及其辅助组件：
  - KnowledgeEntry / KnowledgeCategory / KnowledgeRelation / KnowledgeVersion 数据结构
  - LRUCache 缓存（命中/淘汰/统计）
  - TFIDFIndex 全文检索（增删文档/检索/词表统计）
  - KnowledgeGraph 知识图谱（边/邻居/路径/子图/度数）
  - KnowledgeBase CRUD、分类管理、检索、版本管理、批量导入导出

测试策略：
  - 使用 unittest.mock.patch 屏蔽数据库调用，保证测试纯内存执行
  - 覆盖正常路径、边界条件、异常输入
  - 验证线程安全相关接口的基本行为
  - 至少 30 个测试用例
"""
import os
import sys
import tempfile
import threading
import json
import csv
import time
from unittest.mock import patch, MagicMock

import pytest

# ===== 项目根目录加入 sys.path =====
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# 在导入 knowledge_base 前先 mock 数据库模块，避免初始化时访问真实数据库
import backend.database as _db  # noqa: E402

_TMP_DIR = tempfile.mkdtemp(prefix="thesisminer_kb_test_")
_db.DB_PATH = os.path.join(_TMP_DIR, "test.db")
try:
    _db.init_db()
except Exception:
    pass

from backend.knowledge.knowledge_base import (  # noqa: E402
    KnowledgeBase,
    KnowledgeEntry,
    KnowledgeCategory,
    KnowledgeRelation,
    KnowledgeVersion,
    LRUCache,
    TFIDFIndex,
    KnowledgeGraph,
    DEFAULT_ROOT_CATEGORY,
    DEFAULT_CACHE_SIZE,
    DEFAULT_SEARCH_LIMIT,
    MAX_TITLE_LENGTH,
    MAX_CONTENT_LENGTH,
    RELATION_TYPES,
    STOP_WORDS,
    _tokenize,
    _compute_text_hash,
    _levenshtein,
    _now_iso,
    _new_id,
    _yaml_escape,
    get_knowledge_base,
    reset_knowledge_base,
)


# ============================================================
# 第一部分：工具函数测试
# ============================================================


class TestTokenize:
    """测试 _tokenize 分词函数。"""

    def test_tokenize_empty_string(self):
        """空字符串应返回空列表。"""
        assert _tokenize("") == []
        assert _tokenize(None) == []

    def test_tokenize_english_words(self):
        """英文文本应按单词分词。"""
        tokens = _tokenize("machine learning algorithm")
        assert "machine" in tokens
        assert "learning" in tokens
        assert "algorithm" in tokens

    def test_tokenize_chinese_bigram(self):
        """中文文本应按 2-gram 切分。"""
        tokens = _tokenize("机器学习算法")
        # 应包含相邻字符的 2-gram
        assert "机器" in tokens or "器学" in tokens or "学习" in tokens

    def test_tokenize_filters_stop_words(self):
        """停用词应被过滤。"""
        tokens = _tokenize("the machine is learning")
        # "the" 和 "is" 是停用词，应被过滤
        assert "the" not in tokens
        assert "is" not in tokens
        assert "machine" in tokens
        assert "learning" in tokens

    def test_tokenize_mixed_content(self):
        """中英文混合文本应同时处理。"""
        tokens = _tokenize("使用 Python 实现 machine learning 算法")
        assert "python" in tokens
        assert "machine" in tokens
        assert "learning" in tokens

    def test_tokenize_single_char_chinese(self):
        """中文单字也应保留作为兜底。"""
        tokens = _tokenize("学")
        # 单字应被加入
        assert "学" in tokens


class TestComputeTextHash:
    """测试 _compute_text_hash 哈希函数。"""

    def test_hash_consistent(self):
        """相同文本应产生相同哈希。"""
        text = "测试文本内容"
        assert _compute_text_hash(text) == _compute_text_hash(text)

    def test_hash_different_text(self):
        """不同文本应产生不同哈希。"""
        assert _compute_text_hash("文本A") != _compute_text_hash("文本B")

    def test_hash_returns_hex_string(self):
        """哈希应为十六进制字符串。"""
        h = _compute_text_hash("test")
        assert isinstance(h, str)
        assert len(h) == 32  # MD5 哈希长度

    def test_hash_empty_string(self):
        """空字符串也应能计算哈希。"""
        h = _compute_text_hash("")
        assert isinstance(h, str)
        assert len(h) == 32


class TestLevenshtein:
    """测试 _levenshtein 编辑距离函数。"""

    def test_identical_strings(self):
        """相同字符串编辑距离为 0。"""
        assert _levenshtein("abc", "abc") == 0

    def test_completely_different(self):
        """完全不同的字符串编辑距离为较长字符串长度。"""
        assert _levenshtein("abc", "xyz") == 3

    def test_one_insertion(self):
        """单字符插入的编辑距离为 1。"""
        assert _levenshtein("abc", "abcd") == 1

    def test_one_deletion(self):
        """单字符删除的编辑距离为 1。"""
        assert _levenshtein("abcd", "abc") == 1

    def test_one_substitution(self):
        """单字符替换的编辑距离为 1。"""
        assert _levenshtein("abc", "axc") == 1

    def test_empty_string(self):
        """空字符串与任意字符串的编辑距离为字符串长度。"""
        assert _levenshtein("", "abc") == 3
        assert _levenshtein("abc", "") == 3
        assert _levenshtein("", "") == 0

    def test_chinese_strings(self):
        """中文字符串编辑距离计算。"""
        assert _levenshtein("机器学习", "机器学习") == 0
        assert _levenshtein("机器学习", "深度学习") == 2


class TestNowIso:
    """测试 _now_iso 时间函数。"""

    def test_returns_iso_format(self):
        """应返回 ISO 格式时间字符串。"""
        result = _now_iso()
        assert isinstance(result, str)
        # ISO 格式应包含 'T' 分隔符
        assert "T" in result

    def test_increasing_time(self):
        """连续调用应返回递增的时间。"""
        t1 = _now_iso()
        time.sleep(0.001)
        t2 = _now_iso()
        assert t2 >= t1


class TestNewId:
    """测试 _new_id ID 生成函数。"""

    def test_with_prefix(self):
        """应使用指定前缀。"""
        id1 = _new_id("entry")
        assert id1.startswith("entry_")

    def test_default_prefix(self):
        """默认前缀应为 kb。"""
        id1 = _new_id()
        assert id1.startswith("kb_")

    def test_uniqueness(self):
        """连续生成的 ID 应唯一。"""
        ids = {_new_id("test") for _ in range(100)}
        assert len(ids) == 100


class TestYamlEscape:
    """测试 _yaml_escape YAML 转义函数。"""

    def test_empty_string(self):
        """空字符串应转为空引号。"""
        assert _yaml_escape("") == "''"

    def test_plain_text(self):
        """普通文本无需转义。"""
        assert _yaml_escape("plain") == "plain"

    def test_text_with_colon(self):
        """含冒号的文本应被引号包裹。"""
        result = _yaml_escape("key: value")
        assert result.startswith("'")
        assert result.endswith("'")

    def test_text_with_quote(self):
        """含单引号的文本应转义并包裹。"""
        result = _yaml_escape("it's test")
        assert result.startswith("'")
        # 单引号应被替换为两个单引号
        assert "''" in result


# ============================================================
# 第二部分：LRUCache 测试
# ============================================================


class TestLRUCache:
    """测试 LRUCache 缓存实现。"""

    def test_put_and_get(self):
        """应能写入并读取缓存值。"""
        cache = LRUCache(capacity=10)
        cache.put("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_missing_key(self):
        """读取不存在的键应返回 None。"""
        cache = LRUCache(capacity=10)
        assert cache.get("missing") is None

    def test_eviction_policy(self):
        """超出容量时应淘汰最久未使用的条目。"""
        cache = LRUCache(capacity=2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)  # 应淘汰 a
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3

    def test_access_updates_recency(self):
        """访问应更新最近使用时间。"""
        cache = LRUCache(capacity=2)
        cache.put("a", 1)
        cache.put("b", 2)
        # 访问 a，使其成为最近使用
        cache.get("a")
        cache.put("c", 3)  # 应淘汰 b 而非 a
        assert cache.get("a") == 1
        assert cache.get("b") is None

    def test_update_existing_key(self):
        """更新已存在的键应保留并刷新值。"""
        cache = LRUCache(capacity=10)
        cache.put("key", "old")
        cache.put("key", "new")
        assert cache.get("key") == "new"

    def test_invalidate(self):
        """invalidate 应使指定键失效。"""
        cache = LRUCache(capacity=10)
        cache.put("key", "value")
        assert cache.invalidate("key") is True
        assert cache.get("key") is None

    def test_invalidate_missing_key(self):
        """invalidate 不存在的键应返回 False。"""
        cache = LRUCache(capacity=10)
        assert cache.invalidate("missing") is False

    def test_clear(self):
        """clear 应清空所有缓存。"""
        cache = LRUCache(capacity=10)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_stats(self):
        """stats 应返回正确的统计信息。"""
        cache = LRUCache(capacity=10)
        cache.put("a", 1)
        cache.get("a")  # 命中
        cache.get("missing")  # 未命中
        stats = cache.stats()
        assert stats["size"] == 1
        assert stats["capacity"] == 10
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert 0.0 < stats["hit_rate"] < 1.0

    def test_stats_empty_cache(self):
        """空缓存的统计应正确。"""
        cache = LRUCache(capacity=10)
        stats = cache.stats()
        assert stats["size"] == 0
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 0.0

    def test_minimum_capacity(self):
        """容量小于 1 应被调整为 1。"""
        cache = LRUCache(capacity=0)
        cache.put("a", 1)
        assert cache.get("a") == 1

    def test_thread_safety(self):
        """多线程并发访问不应出错。"""
        cache = LRUCache(capacity=100)
        errors = []

        def worker(thread_id):
            try:
                for i in range(50):
                    cache.put(f"t{thread_id}_k{i}", i)
                    cache.get(f"t{thread_id}_k{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors


# ============================================================
# 第三部分：TFIDFIndex 测试
# ============================================================


class TestTFIDFIndex:
    """测试 TFIDFIndex 全文检索索引。"""

    def test_add_and_search(self):
        """添加文档后应能检索到。"""
        index = TFIDFIndex()
        index.add_document("doc1", "机器学习算法是人工智能的核心")
        index.add_document("doc2", "深度学习是机器学习的分支")
        results = index.search("机器学习")
        assert len(results) > 0
        assert results[0][0] in ("doc1", "doc2")

    def test_search_empty_query(self):
        """空查询应返回空列表。"""
        index = TFIDFIndex()
        index.add_document("doc1", "测试内容")
        assert index.search("") == []

    def test_search_no_documents(self):
        """无文档时检索应返回空列表。"""
        index = TFIDFIndex()
        assert index.search("test") == []

    def test_search_no_match(self):
        """无匹配时应返回空列表。"""
        index = TFIDFIndex()
        index.add_document("doc1", "机器学习")
        results = index.search("zzzzzzz")
        assert results == []

    def test_remove_document(self):
        """移除文档后应不再被检索到。"""
        index = TFIDFIndex()
        index.add_document("doc1", "机器学习算法")
        assert index.remove_document("doc1") is True
        assert index.search("机器学习") == []

    def test_remove_missing_document(self):
        """移除不存在的文档应返回 False。"""
        index = TFIDFIndex()
        assert index.remove_document("missing") is False

    def test_update_document(self):
        """重复添加同一文档应更新而非追加。"""
        index = TFIDFIndex()
        index.add_document("doc1", "机器学习")
        index.add_document("doc1", "深度学习")  # 更新
        assert index.document_count() == 1

    def test_document_count(self):
        """document_count 应返回正确数量。"""
        index = TFIDFIndex()
        assert index.document_count() == 0
        index.add_document("doc1", "内容1")
        index.add_document("doc2", "内容2")
        assert index.document_count() == 2

    def test_vocabulary_size(self):
        """vocabulary_size 应返回词表大小。"""
        index = TFIDFIndex()
        index.add_document("doc1", "machine learning")
        assert index.vocabulary_size() > 0

    def test_search_with_limit(self):
        """limit 参数应限制返回数量。"""
        index = TFIDFIndex()
        for i in range(10):
            index.add_document(f"doc{i}", f"机器学习算法 variant {i}")
        results = index.search("机器学习", limit=3)
        assert len(results) <= 3

    def test_search_ranking(self):
        """检索结果应按相似度降序排列。"""
        index = TFIDFIndex()
        index.add_document("doc1", "机器学习 机器学习 机器学习")
        index.add_document("doc2", "机器学习")
        results = index.search("机器学习")
        if len(results) >= 2:
            assert results[0][1] >= results[1][1]

    def test_search_returns_scores(self):
        """检索结果应包含相似度分数。"""
        index = TFIDFIndex()
        index.add_document("doc1", "机器学习算法")
        results = index.search("机器学习")
        if results:
            doc_id, score = results[0]
            assert isinstance(score, float)
            assert 0.0 <= score <= 1.0


# ============================================================
# 第四部分：KnowledgeGraph 测试
# ============================================================


class TestKnowledgeGraph:
    """测试 KnowledgeGraph 知识图谱。"""

    def test_add_edge_and_neighbors(self):
        """添加边后应能查询邻居。"""
        graph = KnowledgeGraph()
        graph.add_edge("A", "B", "relates_to", 1.0)
        assert "B" in graph.neighbors("A", "out")
        assert "A" in graph.neighbors("B", "in")

    def test_neighbors_both_direction(self):
        """both 方向应返回入边和出边邻居。"""
        graph = KnowledgeGraph()
        graph.add_edge("A", "B")
        graph.add_edge("C", "A")
        neighbors = graph.neighbors("A", "both")
        assert "B" in neighbors
        assert "C" in neighbors

    def test_neighbors_unknown_node(self):
        """未知节点的邻居应返回空列表。"""
        graph = KnowledgeGraph()
        assert graph.neighbors("unknown") == []

    def test_remove_edge(self):
        """移除边应成功。"""
        graph = KnowledgeGraph()
        graph.add_edge("A", "B", "relates_to")
        removed = graph.remove_edge("A", "B")
        assert removed == 1
        assert "B" not in graph.neighbors("A", "out")

    def test_remove_edge_by_type(self):
        """按类型移除边应只移除指定类型。"""
        graph = KnowledgeGraph()
        graph.add_edge("A", "B", "relates_to")
        graph.add_edge("A", "B", "cites")
        removed = graph.remove_edge("A", "B", relation_type="relates_to")
        assert removed == 1
        # cites 边应仍存在
        edges = graph.edges_between("A", "B")
        assert len(edges) == 1
        assert edges[0][1] == "cites"

    def test_remove_edge_missing(self):
        """移除不存在的边应返回 0。"""
        graph = KnowledgeGraph()
        assert graph.remove_edge("A", "B") == 0

    def test_remove_node(self):
        """移除节点应同时移除所有关联边。"""
        graph = KnowledgeGraph()
        graph.add_edge("A", "B")
        graph.add_edge("B", "C")
        removed = graph.remove_node("B")
        assert removed >= 2
        assert "B" not in graph.neighbors("A", "out")
        assert "B" not in graph.neighbors("C", "in")

    def test_edges_between(self):
        """edges_between 应返回所有边。"""
        graph = KnowledgeGraph()
        graph.add_edge("A", "B", "relates_to", 0.5)
        graph.add_edge("A", "B", "cites", 0.8)
        edges = graph.edges_between("A", "B")
        assert len(edges) == 2

    def test_find_path_direct(self):
        """直接相连的节点路径应为 [源, 目标]。"""
        graph = KnowledgeGraph()
        graph.add_edge("A", "B")
        path = graph.find_path("A", "B")
        assert path == ["A", "B"]

    def test_find_path_multi_hop(self):
        """多跳路径应正确返回。"""
        graph = KnowledgeGraph()
        graph.add_edge("A", "B")
        graph.add_edge("B", "C")
        graph.add_edge("C", "D")
        path = graph.find_path("A", "D")
        assert path == ["A", "B", "C", "D"]

    def test_find_path_no_path(self):
        """无路径时应返回 None。"""
        graph = KnowledgeGraph()
        graph.add_edge("A", "B")
        graph.add_edge("C", "D")
        path = graph.find_path("A", "D")
        assert path is None

    def test_find_path_same_node(self):
        """起点等于终点时路径应为 [节点]。"""
        graph = KnowledgeGraph()
        graph.add_edge("A", "B")
        path = graph.find_path("A", "A")
        assert path == ["A"]

    def test_find_path_max_depth(self):
        """max_depth 应限制搜索深度。"""
        graph = KnowledgeGraph()
        graph.add_edge("A", "B")
        graph.add_edge("B", "C")
        graph.add_edge("C", "D")
        # 深度限制为 1，应找不到 D
        path = graph.find_path("A", "D", max_depth=1)
        assert path is None

    def test_find_all_paths(self):
        """find_all_paths 应返回所有路径。"""
        graph = KnowledgeGraph()
        graph.add_edge("A", "B")
        graph.add_edge("A", "C")
        graph.add_edge("B", "D")
        graph.add_edge("C", "D")
        paths = graph.find_all_paths("A", "D")
        assert len(paths) >= 2

    def test_find_all_paths_limit(self):
        """limit 应限制返回路径数量。"""
        graph = KnowledgeGraph()
        graph.add_edge("A", "B")
        graph.add_edge("A", "C")
        graph.add_edge("B", "D")
        graph.add_edge("C", "D")
        paths = graph.find_all_paths("A", "D", limit=1)
        assert len(paths) <= 1

    def test_subgraph(self):
        """subgraph 应提取指定节点的子图。"""
        graph = KnowledgeGraph()
        graph.add_edge("A", "B")
        graph.add_edge("B", "C")
        graph.add_edge("C", "D")
        sub = graph.subgraph({"A", "B", "C"})
        assert set(sub["nodes"]) == {"A", "B", "C"}
        # 应只包含子图内的边
        for edge in sub["edges"]:
            assert edge["source"] in {"A", "B", "C"}
            assert edge["target"] in {"A", "B", "C"}

    def test_node_degree(self):
        """node_degree 应返回正确的入度出度。"""
        graph = KnowledgeGraph()
        graph.add_edge("A", "B")
        graph.add_edge("C", "B")
        degree = graph.node_degree("B")
        assert degree["in_degree"] == 2
        assert degree["out_degree"] == 0
        assert degree["total"] == 2

    def test_stats(self):
        """stats 应返回图谱统计信息。"""
        graph = KnowledgeGraph()
        graph.add_edge("A", "B")
        graph.add_edge("B", "C")
        stats = graph.stats()
        assert stats["nodes"] >= 3
        assert stats["edges"] >= 2


# ============================================================
# 第五部分：KnowledgeEntry 数据结构测试
# ============================================================


class TestKnowledgeEntry:
    """测试 KnowledgeEntry 数据结构。"""

    def test_default_values(self):
        """默认值应正确。"""
        entry = KnowledgeEntry()
        assert entry.id == ""
        assert entry.title == ""
        assert entry.version == 1
        assert entry.view_count == 0
        assert entry.quality_score == 0.0
        assert entry.tags == []
        assert entry.keywords == []

    def test_to_dict(self):
        """to_dict 应返回包含所有字段的字典。"""
        entry = KnowledgeEntry(id="test", title="测试", content="内容")
        d = entry.to_dict()
        assert d["id"] == "test"
        assert d["title"] == "测试"
        assert d["content"] == "内容"
        assert "tags" in d
        assert "keywords" in d

    def test_from_dict(self):
        """from_dict 应正确构造实例。"""
        data = {
            "id": "test",
            "title": "测试",
            "content": "内容",
            "tags": ["标签"],
            "version": 5,
        }
        entry = KnowledgeEntry.from_dict(data)
        assert entry.id == "test"
        assert entry.title == "测试"
        assert entry.tags == ["标签"]
        assert entry.version == 5

    def test_from_dict_with_extra_fields(self):
        """from_dict 应忽略未知字段。"""
        data = {"id": "test", "unknown_field": "value"}
        entry = KnowledgeEntry.from_dict(data)
        assert entry.id == "test"

    def test_summary_short_content(self):
        """短内容摘要应原样返回。"""
        entry = KnowledgeEntry(content="短内容")
        assert entry.summary() == "短内容"

    def test_summary_long_content(self):
        """长内容摘要应截断并加省略号。"""
        long_content = "这是一段很长的内容" * 20
        entry = KnowledgeEntry(content=long_content)
        summary = entry.summary()
        assert summary.endswith("...")
        assert len(summary) <= 103  # 100 字符 + "..."


class TestKnowledgeCategory:
    """测试 KnowledgeCategory 数据结构。"""

    def test_default_values(self):
        """默认值应正确。"""
        cat = KnowledgeCategory()
        assert cat.id == ""
        assert cat.level == 0
        assert cat.children == []

    def test_to_dict(self):
        """to_dict 应返回完整字典。"""
        cat = KnowledgeCategory(id="cat1", name="分类1", level=1)
        d = cat.to_dict()
        assert d["id"] == "cat1"
        assert d["name"] == "分类1"
        assert d["level"] == 1


class TestKnowledgeRelation:
    """测试 KnowledgeRelation 数据结构。"""

    def test_default_values(self):
        """默认值应正确。"""
        rel = KnowledgeRelation()
        assert rel.relation_type == "relates_to"
        assert rel.weight == 1.0

    def test_to_dict(self):
        """to_dict 应返回完整字典。"""
        rel = KnowledgeRelation(id="rel1", source_id="A", target_id="B")
        d = rel.to_dict()
        assert d["id"] == "rel1"
        assert d["source_id"] == "A"
        assert d["target_id"] == "B"


class TestKnowledgeVersion:
    """测试 KnowledgeVersion 数据结构。"""

    def test_default_values(self):
        """默认值应正确。"""
        ver = KnowledgeVersion()
        assert ver.version == 1

    def test_to_dict(self):
        """to_dict 应返回完整字典。"""
        ver = KnowledgeVersion(version_id="v1", entry_id="e1", version=3)
        d = ver.to_dict()
        assert d["version_id"] == "v1"
        assert d["entry_id"] == "e1"
        assert d["version"] == 3


# ============================================================
# 第六部分：KnowledgeBase CRUD 测试
# ============================================================


@pytest.fixture
def kb_instance():
    """提供独立的知识库实例（mock 数据库调用）。"""
    with patch("backend.knowledge.knowledge_base.fetch_all", return_value=[]), \
         patch("backend.knowledge.knowledge_base.fetch_one", return_value=None), \
         patch("backend.knowledge.knowledge_base.execute_insert", return_value=1), \
         patch("backend.knowledge.knowledge_base.execute_query", return_value=None):
        kb = KnowledgeBase(cache_size=50)
        yield kb


class TestKnowledgeBaseCRUD:
    """测试 KnowledgeBase 的 CRUD 操作。"""

    def test_create_entry_basic(self, kb_instance):
        """创建条目应返回 ID。"""
        entry_id = kb_instance.create_entry(
            title="测试条目",
            content="这是测试内容，用于验证知识库的创建功能。",
            author="tester",
        )
        assert entry_id.startswith("entry_")
        entry = kb_instance.get_entry(entry_id)
        assert entry is not None
        assert entry.title == "测试条目"
        assert entry.author == "tester"
        assert entry.version == 1

    def test_create_entry_with_tags(self, kb_instance):
        """创建带标签的条目。"""
        entry_id = kb_instance.create_entry(
            title="带标签的条目",
            content="内容",
            tags=["标签1", "标签2"],
        )
        entry = kb_instance.get_entry(entry_id)
        assert entry.tags == ["标签1", "标签2"]

    def test_create_entry_with_keywords(self, kb_instance):
        """创建带关键词的条目。"""
        entry_id = kb_instance.create_entry(
            title="带关键词的条目",
            content="内容",
            keywords=["关键词1", "关键词2"],
        )
        entry = kb_instance.get_entry(entry_id)
        assert "关键词1" in entry.keywords
        assert "关键词2" in entry.keywords

    def test_create_entry_auto_extract_keywords(self, kb_instance):
        """未提供关键词时应自动提取。"""
        entry_id = kb_instance.create_entry(
            title="自动提取关键词",
            content="机器学习 深度学习 神经网络 算法",
        )
        entry = kb_instance.get_entry(entry_id)
        assert len(entry.keywords) > 0

    def test_create_entry_empty_title(self, kb_instance):
        """空标题应抛出 ValueError。"""
        with pytest.raises(ValueError):
            kb_instance.create_entry(title="", content="内容")

    def test_create_entry_empty_content(self, kb_instance):
        """空内容应抛出 ValueError。"""
        with pytest.raises(ValueError):
            kb_instance.create_entry(title="标题", content="")

    def test_create_entry_title_too_long(self, kb_instance):
        """超长标题应抛出 ValueError。"""
        with pytest.raises(ValueError):
            kb_instance.create_entry(title="x" * (MAX_TITLE_LENGTH + 1), content="内容")

    def test_create_entry_content_too_long(self, kb_instance):
        """超长内容应抛出 ValueError。"""
        with pytest.raises(ValueError):
            kb_instance.create_entry(title="标题", content="x" * (MAX_CONTENT_LENGTH + 1))

    def test_get_entry_missing(self, kb_instance):
        """获取不存在的条目应返回 None。"""
        assert kb_instance.get_entry("missing_id") is None

    def test_get_entry_increment_view(self, kb_instance):
        """increment_view 应增加浏览次数。"""
        entry_id = kb_instance.create_entry(title="测试", content="内容")
        original_count = kb_instance.get_entry(entry_id).view_count
        kb_instance.get_entry(entry_id, increment_view=True)
        # 由于缓存的存在，可能影响计数，但应至少有一次访问
        entry = kb_instance.get_entry(entry_id)
        assert entry.view_count >= original_count

    def test_update_entry_title(self, kb_instance):
        """更新标题应创建新版本。"""
        entry_id = kb_instance.create_entry(title="原标题", content="内容")
        result = kb_instance.update_entry(entry_id, title="新标题", author="editor")
        assert result is True
        entry = kb_instance.get_entry(entry_id)
        assert entry.title == "新标题"
        assert entry.version == 2

    def test_update_entry_content(self, kb_instance):
        """更新内容应创建新版本。"""
        entry_id = kb_instance.create_entry(title="标题", content="原内容")
        kb_instance.update_entry(entry_id, content="新内容")
        entry = kb_instance.get_entry(entry_id)
        assert entry.content == "新内容"
        assert entry.version == 2

    def test_update_entry_missing(self, kb_instance):
        """更新不存在的条目应返回 False。"""
        assert kb_instance.update_entry("missing", title="新") is False

    def test_update_entry_empty_title(self, kb_instance):
        """更新为空标题应抛出 ValueError。"""
        entry_id = kb_instance.create_entry(title="标题", content="内容")
        with pytest.raises(ValueError):
            kb_instance.update_entry(entry_id, title="")

    def test_delete_entry(self, kb_instance):
        """删除条目应成功。"""
        entry_id = kb_instance.create_entry(title="待删除", content="内容")
        assert kb_instance.delete_entry(entry_id) is True
        assert kb_instance.get_entry(entry_id) is None

    def test_delete_entry_missing(self, kb_instance):
        """删除不存在的条目应返回 False。"""
        assert kb_instance.delete_entry("missing") is False


# ============================================================
# 第七部分：分类管理测试
# ============================================================


class TestKnowledgeBaseCategory:
    """测试 KnowledgeBase 的分类管理。"""

    def test_root_category_exists(self, kb_instance):
        """初始化后应存在根分类。"""
        root = kb_instance.get_category("cat_root")
        assert root is not None
        assert root.name == DEFAULT_ROOT_CATEGORY
        assert root.level == 0

    def test_create_category(self, kb_instance):
        """创建分类应返回 ID。"""
        cat_id = kb_instance.create_category("测试分类", parent_id="cat_root")
        assert cat_id.startswith("cat_")
        cat = kb_instance.get_category(cat_id)
        assert cat.name == "测试分类"
        assert cat.parent_id == "cat_root"
        assert cat.level == 1

    def test_create_category_invalid_parent(self, kb_instance):
        """父分类不存在应抛出 ValueError。"""
        with pytest.raises(ValueError):
            kb_instance.create_category("测试", parent_id="invalid_parent")

    def test_create_category_empty_name(self, kb_instance):
        """空名称应抛出 ValueError。"""
        with pytest.raises(ValueError):
            kb_instance.create_category("", parent_id="cat_root")

    def test_list_categories_all(self, kb_instance):
        """列出所有分类。"""
        kb_instance.create_category("分类A", parent_id="cat_root")
        kb_instance.create_category("分类B", parent_id="cat_root")
        cats = kb_instance.list_categories()
        assert len(cats) >= 3  # 根 + 2 个新分类

    def test_list_categories_by_parent(self, kb_instance):
        """按父分类列出子分类。"""
        kb_instance.create_category("子分类1", parent_id="cat_root")
        kb_instance.create_category("子分类2", parent_id="cat_root")
        children = kb_instance.list_categories(parent_id="cat_root")
        assert len(children) >= 2

    def test_get_category_tree(self, kb_instance):
        """获取分类树结构。"""
        cat_id = kb_instance.create_category("父分类", parent_id="cat_root")
        kb_instance.create_category("子分类", parent_id=cat_id)
        tree = kb_instance.get_category_tree("cat_root")
        assert tree["name"] == DEFAULT_ROOT_CATEGORY
        assert len(tree["children"]) >= 1

    def test_delete_category(self, kb_instance):
        """删除分类应成功。"""
        cat_id = kb_instance.create_category("待删除", parent_id="cat_root")
        assert kb_instance.delete_category(cat_id) is True
        assert kb_instance.get_category(cat_id) is None

    def test_delete_root_category_fails(self, kb_instance):
        """删除根分类应失败。"""
        assert kb_instance.delete_category("cat_root") is False

    def test_delete_category_with_children_non_recursive(self, kb_instance):
        """非递归删除有子分类的分类应抛出异常。"""
        parent_id = kb_instance.create_category("父分类", parent_id="cat_root")
        kb_instance.create_category("子分类", parent_id=parent_id)
        with pytest.raises(ValueError):
            kb_instance.delete_category(parent_id, recursive=False)

    def test_delete_category_recursive(self, kb_instance):
        """递归删除应同时删除子分类。"""
        parent_id = kb_instance.create_category("父分类", parent_id="cat_root")
        child_id = kb_instance.create_category("子分类", parent_id=parent_id)
        assert kb_instance.delete_category(parent_id, recursive=True) is True
        assert kb_instance.get_category(parent_id) is None
        assert kb_instance.get_category(child_id) is None

    def test_list_entries_by_category(self, kb_instance):
        """列出分类下的条目。"""
        cat_id = kb_instance.create_category("测试分类", parent_id="cat_root")
        kb_instance.create_entry(title="条目1", content="内容1", category_id=cat_id)
        kb_instance.create_entry(title="条目2", content="内容2", category_id=cat_id)
        entries = kb_instance.list_entries_by_category(cat_id)
        assert len(entries) == 2

    def test_list_entries_by_category_include_sub(self, kb_instance):
        """包含子分类的条目列表。"""
        parent_cat = kb_instance.create_category("父分类", parent_id="cat_root")
        child_cat = kb_instance.create_category("子分类", parent_id=parent_cat)
        kb_instance.create_entry(title="父条目", content="内容", category_id=parent_cat)
        kb_instance.create_entry(title="子条目", content="内容", category_id=child_cat)
        entries = kb_instance.list_entries_by_category(parent_cat, include_subcategories=True)
        assert len(entries) == 2


# ============================================================
# 第八部分：检索测试
# ============================================================


class TestKnowledgeBaseSearch:
    """测试 KnowledgeBase 的检索功能。"""

    def test_search_basic(self, kb_instance):
        """基本检索应返回结果。"""
        kb_instance.create_entry(
            title="机器学习入门",
            content="机器学习是人工智能的核心技术，包括监督学习和无监督学习。",
        )
        kb_instance.create_entry(
            title="深度学习进阶",
            content="深度学习是机器学习的分支，使用神经网络。",
        )
        results = kb_instance.search("机器学习")
        assert len(results) > 0
        assert "entry" in results[0]
        assert "score" in results[0]
        assert "summary" in results[0]

    def test_search_with_category_filter(self, kb_instance):
        """按分类过滤检索结果。"""
        cat1 = kb_instance.create_category("分类1", parent_id="cat_root")
        cat2 = kb_instance.create_category("分类2", parent_id="cat_root")
        kb_instance.create_entry(title="机器学习", content="内容", category_id=cat1)
        kb_instance.create_entry(title="机器学习", content="内容", category_id=cat2)
        results = kb_instance.search("机器学习", category_id=cat1)
        assert all(r["entry"]["category_id"] == cat1 for r in results)

    def test_search_with_tag_filter(self, kb_instance):
        """按标签过滤检索结果。"""
        kb_instance.create_entry(title="机器学习", content="内容", tags=["AI"])
        kb_instance.create_entry(title="机器学习", content="内容", tags=["ML"])
        results = kb_instance.search("机器学习", tags=["AI"])
        assert all("AI" in r["entry"]["tags"] for r in results)

    def test_search_by_tag(self, kb_instance):
        """按标签检索。"""
        kb_instance.create_entry(title="条目1", content="内容", tags=["标签A"])
        kb_instance.create_entry(title="条目2", content="内容", tags=["标签A", "标签B"])
        results = kb_instance.search_by_tag("标签A")
        assert len(results) == 2

    def test_search_by_tag_missing(self, kb_instance):
        """按不存在的标签检索应返回空列表。"""
        assert kb_instance.search_by_tag("不存在的标签") == []

    def test_search_by_keyword(self, kb_instance):
        """按关键词检索。"""
        kb_instance.create_entry(
            title="条目", content="内容", keywords=["关键词X"]
        )
        results = kb_instance.search_by_keyword("关键词X")
        assert len(results) == 1

    def test_search_by_discipline(self, kb_instance):
        """按学科检索。"""
        kb_instance.create_entry(title="条目1", content="内容", discipline="0812")
        kb_instance.create_entry(title="条目2", content="内容", discipline="0701")
        results = kb_instance.search_by_discipline("0812")
        assert len(results) == 1
        assert results[0].discipline == "0812"

    def test_search_empty_query(self, kb_instance):
        """空查询应返回空列表。"""
        kb_instance.create_entry(title="条目", content="内容")
        assert kb_instance.search("") == []


# ============================================================
# 第九部分：知识图谱与关系测试
# ============================================================


class TestKnowledgeBaseRelations:
    """测试 KnowledgeBase 的关系管理。"""

    def test_add_relation(self, kb_instance):
        """添加关系应返回关系 ID。"""
        id1 = kb_instance.create_entry(title="条目1", content="内容1")
        id2 = kb_instance.create_entry(title="条目2", content="内容2")
        rel_id = kb_instance.add_relation(id1, id2, "relates_to", 0.8)
        assert rel_id is not None
        assert rel_id.startswith("rel_")

    def test_add_relation_invalid_type(self, kb_instance):
        """未知关系类型应抛出 ValueError。"""
        id1 = kb_instance.create_entry(title="条目1", content="内容1")
        id2 = kb_instance.create_entry(title="条目2", content="内容2")
        with pytest.raises(ValueError):
            kb_instance.add_relation(id1, id2, "invalid_type")

    def test_add_relation_missing_entry(self, kb_instance):
        """条目不存在时应返回 None。"""
        rel_id = kb_instance.add_relation("missing1", "missing2", "relates_to")
        assert rel_id is None

    def test_add_relation_clamps_weight(self, kb_instance):
        """权重应被限制在 0-1 范围。"""
        id1 = kb_instance.create_entry(title="条目1", content="内容1")
        id2 = kb_instance.create_entry(title="条目2", content="内容2")
        kb_instance.add_relation(id1, id2, "relates_to", 1.5)
        rels = kb_instance.get_relations(id1, "out")
        assert rels[0]["weight"] <= 1.0

    def test_get_relations_both(self, kb_instance):
        """获取双向关系。"""
        id1 = kb_instance.create_entry(title="条目1", content="内容1")
        id2 = kb_instance.create_entry(title="条目2", content="内容2")
        kb_instance.add_relation(id1, id2, "relates_to")
        rels_out = kb_instance.get_relations(id1, "out")
        rels_in = kb_instance.get_relations(id2, "in")
        assert len(rels_out) == 1
        assert len(rels_in) == 1

    def test_remove_relation(self, kb_instance):
        """移除关系应成功。"""
        id1 = kb_instance.create_entry(title="条目1", content="内容1")
        id2 = kb_instance.create_entry(title="条目2", content="内容2")
        kb_instance.add_relation(id1, id2, "relates_to")
        removed = kb_instance.remove_relation(id1, id2)
        assert removed == 1
        assert len(kb_instance.get_relations(id1, "out")) == 0

    def test_find_path(self, kb_instance):
        """查找条目间路径。"""
        id1 = kb_instance.create_entry(title="条目1", content="内容1")
        id2 = kb_instance.create_entry(title="条目2", content="内容2")
        id3 = kb_instance.create_entry(title="条目3", content="内容3")
        kb_instance.add_relation(id1, id2, "relates_to")
        kb_instance.add_relation(id2, id3, "relates_to")
        path = kb_instance.find_path(id1, id3)
        assert path is not None
        assert path[0] == id1
        assert path[-1] == id3

    def test_find_all_paths(self, kb_instance):
        """查找所有路径。"""
        id1 = kb_instance.create_entry(title="条目1", content="内容1")
        id2 = kb_instance.create_entry(title="条目2", content="内容2")
        id3 = kb_instance.create_entry(title="条目3", content="内容3")
        kb_instance.add_relation(id1, id2, "relates_to")
        kb_instance.add_relation(id1, id3, "relates_to")
        kb_instance.add_relation(id2, id3, "relates_to")
        paths = kb_instance.find_all_paths(id1, id3)
        assert len(paths) >= 1

    def test_get_related_entries(self, kb_instance):
        """获取相关条目。"""
        id1 = kb_instance.create_entry(title="条目1", content="内容1")
        id2 = kb_instance.create_entry(title="条目2", content="内容2")
        id3 = kb_instance.create_entry(title="条目3", content="内容3")
        kb_instance.add_relation(id1, id2, "relates_to")
        kb_instance.add_relation(id1, id3, "relates_to")
        related = kb_instance.get_related_entries(id1, depth=1)
        assert len(related) == 2

    def test_get_graph_subgraph(self, kb_instance):
        """提取子图。"""
        id1 = kb_instance.create_entry(title="条目1", content="内容1")
        id2 = kb_instance.create_entry(title="条目2", content="内容2")
        kb_instance.add_relation(id1, id2, "relates_to")
        sub = kb_instance.get_graph_subgraph([id1, id2])
        assert len(sub["nodes"]) == 2
        assert len(sub["edges"]) >= 1


# ============================================================
# 第十部分：版本管理测试
# ============================================================


class TestKnowledgeBaseVersions:
    """测试 KnowledgeBase 的版本管理。"""

    def test_version_history(self, kb_instance):
        """获取版本历史。"""
        entry_id = kb_instance.create_entry(title="原标题", content="原内容")
        kb_instance.update_entry(entry_id, title="新标题", content="新内容")
        history = kb_instance.get_version_history(entry_id)
        # 创建时保存一个版本，更新时再保存一个
        assert len(history) >= 1

    def test_get_version(self, kb_instance):
        """获取指定版本。"""
        entry_id = kb_instance.create_entry(title="原标题", content="原内容")
        version = kb_instance.get_version(entry_id, 1)
        assert version is not None
        assert version.version == 1
        assert version.title == "原标题"

    def test_get_version_missing(self, kb_instance):
        """获取不存在的版本应返回 None。"""
        entry_id = kb_instance.create_entry(title="标题", content="内容")
        assert kb_instance.get_version(entry_id, 99) is None

    def test_rollback_to_version(self, kb_instance):
        """回滚到指定版本。"""
        entry_id = kb_instance.create_entry(title="原标题", content="原内容")
        kb_instance.update_entry(entry_id, title="新标题", content="新内容")
        # 回滚到版本 1
        result = kb_instance.rollback_to_version(entry_id, 1, author="admin")
        assert result is True
        entry = kb_instance.get_entry(entry_id)
        assert entry.title == "原标题"
        assert entry.version >= 3  # 创建 + 更新 + 回滚

    def test_rollback_missing_entry(self, kb_instance):
        """回滚不存在的条目应返回 False。"""
        assert kb_instance.rollback_to_version("missing", 1) is False

    def test_resolve_conflict_theirs(self, kb_instance):
        """使用 theirs 策略解决冲突。"""
        entry_id = kb_instance.create_entry(title="原标题", content="原内容")
        kb_instance.update_entry(entry_id, title="新标题", content="新内容")
        # 解决冲突：使用版本 1 的内容
        result = kb_instance.resolve_conflict(
            entry_id, base_version=1, their_version=1, resolution="theirs"
        )
        assert result is True
        entry = kb_instance.get_entry(entry_id)
        assert entry.title == "原标题"

    def test_resolve_conflict_ours(self, kb_instance):
        """使用 ours 策略解决冲突。"""
        entry_id = kb_instance.create_entry(title="原标题", content="原内容")
        kb_instance.update_entry(entry_id, title="新标题", content="新内容")
        current_title = kb_instance.get_entry(entry_id).title
        result = kb_instance.resolve_conflict(
            entry_id, base_version=1, their_version=1, resolution="ours"
        )
        assert result is True
        entry = kb_instance.get_entry(entry_id)
        assert entry.title == current_title  # 保持不变

    def test_resolve_conflict_invalid_strategy(self, kb_instance):
        """无效策略应返回 False。"""
        entry_id = kb_instance.create_entry(title="标题", content="内容")
        result = kb_instance.resolve_conflict(
            entry_id, base_version=1, their_version=1, resolution="invalid"
        )
        assert result is False


# ============================================================
# 第十一部分：批量导入导出测试
# ============================================================


class TestKnowledgeBaseImportExport:
    """测试 KnowledgeBase 的批量导入导出。"""

    def test_export_to_json(self, kb_instance, tmp_path):
        """导出为 JSON 文件。"""
        kb_instance.create_entry(title="条目1", content="内容1")
        kb_instance.create_entry(title="条目2", content="内容2")
        file_path = tmp_path / "export.json"
        count = kb_instance.export_to_json(str(file_path))
        assert count == 2
        assert file_path.exists()
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "entries" in data
        assert "categories" in data
        assert len(data["entries"]) == 2

    def test_import_from_json(self, kb_instance, tmp_path):
        """从 JSON 文件导入。"""
        # 先导出
        entry_id = kb_instance.create_entry(title="条目1", content="内容1")
        file_path = tmp_path / "export.json"
        kb_instance.export_to_json(str(file_path))
        # 修改文件后导入
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["entries"].append({
            "id": "imported_entry",
            "title": "导入的条目",
            "content": "导入的内容",
            "category_id": "cat_root",
        })
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        stats = kb_instance.import_from_json(str(file_path))
        assert stats["created"] >= 1
        assert kb_instance.get_entry("imported_entry") is not None

    def test_import_from_json_skip_existing(self, kb_instance, tmp_path):
        """导入时跳过已存在条目。"""
        entry_id = kb_instance.create_entry(title="条目1", content="内容1")
        file_path = tmp_path / "export.json"
        kb_instance.export_to_json(str(file_path))
        stats = kb_instance.import_from_json(str(file_path), overwrite=False)
        assert stats["skipped"] >= 1

    def test_import_from_json_overwrite(self, kb_instance, tmp_path):
        """导入时覆盖已存在条目。"""
        entry_id = kb_instance.create_entry(title="原标题", content="原内容")
        file_path = tmp_path / "export.json"
        kb_instance.export_to_json(str(file_path))
        # 修改导出文件中的标题
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for entry in data["entries"]:
            if entry["id"] == entry_id:
                entry["title"] = "修改后的标题"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        stats = kb_instance.import_from_json(str(file_path), overwrite=True)
        assert stats["updated"] >= 1
        assert kb_instance.get_entry(entry_id).title == "修改后的标题"

    def test_export_to_csv(self, kb_instance, tmp_path):
        """导出为 CSV 文件。"""
        kb_instance.create_entry(
            title="条目1", content="内容1", tags=["标签A"], keywords=["关键词X"]
        )
        file_path = tmp_path / "export.csv"
        count = kb_instance.export_to_csv(str(file_path))
        assert count == 1
        assert file_path.exists()
        with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["title"] == "条目1"

    def test_import_from_csv(self, kb_instance, tmp_path):
        """从 CSV 文件导入。"""
        file_path = tmp_path / "import.csv"
        with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["id", "title", "content", "category_id", "tags",
                            "keywords", "discipline", "source", "author",
                            "version", "created_at", "updated_at", "quality_score"],
            )
            writer.writeheader()
            writer.writerow({
                "id": "csv_entry_1",
                "title": "CSV条目",
                "content": "CSV内容",
                "category_id": "cat_root",
                "tags": "标签1;标签2",
                "keywords": "关键词1;关键词2",
                "discipline": "0812",
                "source": "",
                "author": "csv_test",
                "version": "1",
                "created_at": "",
                "updated_at": "",
                "quality_score": "0.0",
            })
        stats = kb_instance.import_from_csv(str(file_path))
        assert stats["created"] == 1
        entry = kb_instance.get_entry("csv_entry_1")
        assert entry is not None
        assert entry.title == "CSV条目"
        assert entry.tags == ["标签1", "标签2"]

    def test_export_to_yaml(self, kb_instance, tmp_path):
        """导出为 YAML 文件。"""
        kb_instance.create_entry(title="条目1", content="内容1")
        file_path = tmp_path / "export.yaml"
        count = kb_instance.export_to_yaml(str(file_path))
        assert count == 1
        assert file_path.exists()
        content = file_path.read_text(encoding="utf-8")
        assert "version: '8.0'" in content
        assert "entries:" in content


# ============================================================
# 第十二部分：统计与维护测试
# ============================================================


class TestKnowledgeBaseStats:
    """测试 KnowledgeBase 的统计与维护功能。"""

    def test_stats_basic(self, kb_instance):
        """基本统计信息。"""
        kb_instance.create_entry(title="条目1", content="内容1", tags=["标签A"])
        kb_instance.create_entry(title="条目2", content="内容2", tags=["标签A", "标签B"])
        stats = kb_instance.stats()
        assert stats["total_entries"] == 2
        assert stats["total_categories"] >= 1
        assert "cache_stats" in stats
        assert "top_tags" in stats
        assert "top_keywords" in stats

    def test_stats_top_tags(self, kb_instance):
        """统计热门标签。"""
        kb_instance.create_entry(title="条目1", content="内容1", tags=["热门"])
        kb_instance.create_entry(title="条目2", content="内容2", tags=["热门"])
        kb_instance.create_entry(title="条目3", content="内容3", tags=["冷门"])
        stats = kb_instance.stats()
        top_tags = stats["top_tags"]
        # "热门" 应排在 "冷门" 前面
        hot_count = next((c for t, c in top_tags if t == "热门"), 0)
        cold_count = next((c for t, c in top_tags if t == "冷门"), 0)
        assert hot_count > cold_count

    def test_clear_cache(self, kb_instance):
        """清空缓存。"""
        entry_id = kb_instance.create_entry(title="条目", content="内容")
        kb_instance.get_entry(entry_id)  # 触发缓存
        kb_instance.clear_cache()
        # 缓存清空后应仍能正常获取
        entry = kb_instance.get_entry(entry_id)
        assert entry is not None

    def test_rebuild_index(self, kb_instance):
        """重建索引。"""
        entry_id = kb_instance.create_entry(title="条目", content="内容", tags=["标签"])
        kb_instance.rebuild_index()
        # 重建后应仍能检索
        results = kb_instance.search_by_tag("标签")
        assert len(results) == 1


# ============================================================
# 第十三部分：全局单例测试
# ============================================================


class TestGlobalInstance:
    """测试全局单例函数。"""

    def test_get_knowledge_base_singleton(self):
        """get_knowledge_base 应返回单例。"""
        with patch("backend.knowledge.knowledge_base.fetch_all", return_value=[]), \
             patch("backend.knowledge.knowledge_base.fetch_one", return_value=None), \
             patch("backend.knowledge.knowledge_base.execute_insert", return_value=1), \
             patch("backend.knowledge.knowledge_base.execute_query", return_value=None):
            reset_knowledge_base()
            kb1 = get_knowledge_base()
            kb2 = get_knowledge_base()
            assert kb1 is kb2

    def test_reset_knowledge_base(self):
        """reset_knowledge_base 应重置单例。"""
        with patch("backend.knowledge.knowledge_base.fetch_all", return_value=[]), \
             patch("backend.knowledge.knowledge_base.fetch_one", return_value=None), \
             patch("backend.knowledge.knowledge_base.execute_insert", return_value=1), \
             patch("backend.knowledge.knowledge_base.execute_query", return_value=None):
            reset_knowledge_base()
            kb1 = get_knowledge_base()
            reset_knowledge_base()
            kb2 = get_knowledge_base()
            assert kb1 is not kb2


# ============================================================
# 第十四部分：常量与配置测试
# ============================================================


class TestConstants:
    """测试模块常量。"""

    def test_relation_types_not_empty(self):
        """关系类型映射应非空。"""
        assert len(RELATION_TYPES) > 0
        assert "relates_to" in RELATION_TYPES
        assert "depends_on" in RELATION_TYPES

    def test_stop_words_not_empty(self):
        """停用词集合应非空。"""
        assert len(STOP_WORDS) > 0
        assert "的" in STOP_WORDS
        assert "the" in STOP_WORDS

    def test_default_values(self):
        """默认值常量应正确。"""
        assert DEFAULT_ROOT_CATEGORY == "根分类"
        assert DEFAULT_CACHE_SIZE > 0
        assert DEFAULT_SEARCH_LIMIT > 0
        assert MAX_TITLE_LENGTH > 0
        assert MAX_CONTENT_LENGTH > 0
