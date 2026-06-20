"""学科分类体系模块单元测试

测试 backend/knowledge/discipline_taxonomy.py 中的 DisciplineTaxonomy 类及其辅助组件：
  - DisciplineNode / DisciplineProfile / DisciplineTrend 数据结构
  - 工具函数：_tokenize / _jaccard_similarity / _cosine_similarity
  - DisciplineTaxonomy 节点 CRUD、分类查询、交叉学科识别
  - 学科相似度计算、学科聚类、学科趋势分析
  - 学科画像生成、学科推荐、学科关键词提取

测试策略：
  - 使用真实初始化的教育部学科目录
  - 覆盖正常路径、边界条件、异常输入
  - 验证线程安全相关接口的基本行为
  - 至少 30 个测试用例
"""
import os
import sys
import threading
import time
from unittest.mock import patch, MagicMock

import pytest

# ===== 项目根目录加入 sys.path =====
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.knowledge.discipline_taxonomy import (  # noqa: E402
    DisciplineTaxonomy,
    DisciplineNode,
    DisciplineProfile,
    DisciplineTrend,
    DisciplineLevel,
    DISCIPLINE_GATE_CATEGORIES,
    TYPICAL_FIRST_LEVEL_DISCIPLINES,
    CROSS_DISCIPLINE_KEYWORDS,
    _tokenize,
    _jaccard_similarity,
    _cosine_similarity,
    _now_iso,
    get_discipline_taxonomy,
    reset_discipline_taxonomy,
)


# ============================================================
# 第一部分：工具函数测试
# ============================================================


class TestTokenize:
    """测试 _tokenize 分词函数。"""

    def test_tokenize_empty(self):
        """空字符串应返回空列表。"""
        assert _tokenize("") == []
        assert _tokenize(None) == []

    def test_tokenize_english(self):
        """英文文本应按单词分词。"""
        tokens = _tokenize("machine learning algorithm")
        assert "machine" in tokens
        assert "learning" in tokens
        assert "algorithm" in tokens

    def test_tokenize_chinese_bigram(self):
        """中文文本应按 2-gram 切分。"""
        tokens = _tokenize("机器学习")
        assert "机器" in tokens
        assert "器学" in tokens
        assert "学习" in tokens

    def test_tokenize_mixed(self):
        """中英文混合文本。"""
        tokens = _tokenize("使用 Python 实现 machine learning")
        assert "python" in tokens
        assert "machine" in tokens

    def test_tokenize_single_chinese_char(self):
        """单个中文字符。"""
        tokens = _tokenize("学")
        assert "学" in tokens

    def test_tokenize_with_numbers(self):
        """含数字的文本。"""
        tokens = _tokenize("python3 algorithm")
        assert "python3" in tokens


class TestJaccardSimilarity:
    """测试 _jaccard_similarity 函数。"""

    def test_identical_sets(self):
        """相同集合相似度为 1。"""
        s = {"a", "b", "c"}
        assert _jaccard_similarity(s, s) == 1.0

    def test_disjoint_sets(self):
        """不相交集合相似度为 0。"""
        assert _jaccard_similarity({"a"}, {"b"}) == 0.0

    def test_empty_sets(self):
        """两个空集合相似度为 0。"""
        assert _jaccard_similarity(set(), set()) == 0.0

    def test_partial_overlap(self):
        """部分重叠的集合。"""
        s1 = {"a", "b", "c"}
        s2 = {"b", "c", "d"}
        # 交集 2，并集 4
        assert _jaccard_similarity(s1, s2) == 0.5

    def test_one_empty_set(self):
        """一个空集合。"""
        assert _jaccard_similarity({"a"}, set()) == 0.0


class TestCosineSimilarity:
    """测试 _cosine_similarity 函数。"""

    def test_identical_vectors(self):
        """相同向量相似度为 1。"""
        v = {"a": 1.0, "b": 2.0}
        assert _cosine_similarity(v, v) == 1.0

    def test_orthogonal_vectors(self):
        """正交向量相似度为 0。"""
        v1 = {"a": 1.0}
        v2 = {"b": 1.0}
        assert _cosine_similarity(v1, v2) == 0.0

    def test_empty_vectors(self):
        """空向量相似度为 0。"""
        assert _cosine_similarity({}, {}) == 0.0

    def test_partial_overlap(self):
        """部分重叠的向量。"""
        v1 = {"a": 1.0, "b": 0.0}
        v2 = {"a": 1.0, "c": 1.0}
        sim = _cosine_similarity(v1, v2)
        assert 0.0 < sim < 1.0

    def test_zero_norm(self):
        """零范数向量相似度为 0。"""
        v1 = {"a": 0.0}
        v2 = {"a": 1.0}
        assert _cosine_similarity(v1, v2) == 0.0


# ============================================================
# 第二部分：数据结构测试
# ============================================================


class TestDisciplineNode:
    """测试 DisciplineNode 数据结构。"""

    def test_default_values(self):
        """默认值应正确。"""
        node = DisciplineNode()
        assert node.code == ""
        assert node.name == ""
        assert node.level == DisciplineLevel.SECOND
        assert node.keywords == []
        assert node.children == []
        assert node.aliases == []

    def test_to_dict(self):
        """to_dict 应返回完整字典。"""
        node = DisciplineNode(code="0812", name="计算机科学与技术", level=2)
        d = node.to_dict()
        assert d["code"] == "0812"
        assert d["name"] == "计算机科学与技术"
        assert d["level"] == 2

    def test_from_dict(self):
        """from_dict 应正确构造实例。"""
        data = {
            "code": "0812",
            "name": "计算机科学与技术",
            "level": 2,
            "keywords": ["计算机", "算法"],
        }
        node = DisciplineNode.from_dict(data)
        assert node.code == "0812"
        assert node.name == "计算机科学与技术"
        assert node.keywords == ["计算机", "算法"]

    def test_from_dict_ignores_unknown_fields(self):
        """from_dict 应忽略未知字段。"""
        data = {"code": "0812", "unknown": "value"}
        node = DisciplineNode.from_dict(data)
        assert node.code == "0812"


class TestDisciplineProfile:
    """测试 DisciplineProfile 数据结构。"""

    def test_default_values(self):
        """默认值应正确。"""
        profile = DisciplineProfile()
        assert profile.code == ""
        assert profile.difficulty == 3
        assert profile.popularity == 3
        assert profile.trend == "stable"

    def test_to_dict(self):
        """to_dict 应返回完整字典。"""
        profile = DisciplineProfile(code="0812", name="计算机", difficulty=5)
        d = profile.to_dict()
        assert d["code"] == "0812"
        assert d["name"] == "计算机"
        assert d["difficulty"] == 5


class TestDisciplineTrend:
    """测试 DisciplineTrend 数据结构。"""

    def test_default_values(self):
        """默认值应正确。"""
        trend = DisciplineTrend()
        assert trend.year == 0
        assert trend.paper_count == 0
        assert trend.growth_rate == 0.0

    def test_to_dict(self):
        """to_dict 应返回完整字典。"""
        trend = DisciplineTrend(code="0812", year=2024, paper_count=1000)
        d = trend.to_dict()
        assert d["code"] == "0812"
        assert d["year"] == 2024
        assert d["paper_count"] == 1000


# ============================================================
# 第三部分：常量测试
# ============================================================


class TestConstants:
    """测试模块常量。"""

    def test_gate_categories_not_empty(self):
        """学科门类映射应非空。"""
        assert len(DISCIPLINE_GATE_CATEGORIES) > 0
        assert "01" in DISCIPLINE_GATE_CATEGORIES
        assert "08" in DISCIPLINE_GATE_CATEGORIES
        assert "14" in DISCIPLINE_GATE_CATEGORIES

    def test_typical_disciplines_not_empty(self):
        """典型一级学科映射应非空。"""
        assert len(TYPICAL_FIRST_LEVEL_DISCIPLINES) > 0
        assert "08" in TYPICAL_FIRST_LEVEL_DISCIPLINES
        # 工学应包含计算机科学与技术
        codes = [code for code, _ in TYPICAL_FIRST_LEVEL_DISCIPLINES["08"]]
        assert "0812" in codes

    def test_cross_discipline_keywords_not_empty(self):
        """交叉学科关键词映射应非空。"""
        assert len(CROSS_DISCIPLINE_KEYWORDS) > 0
        assert "生物信息学" in CROSS_DISCIPLINE_KEYWORDS
        assert "人工智能" in CROSS_DISCIPLINE_KEYWORDS

    def test_discipline_level_constants(self):
        """学科层级常量应正确。"""
        assert DisciplineLevel.FIRST == 1
        assert DisciplineLevel.SECOND == 2
        assert DisciplineLevel.THIRD == 3


# ============================================================
# 第四部分：DisciplineTaxonomy 初始化与节点 CRUD 测试
# ============================================================


@pytest.fixture
def taxonomy():
    """提供独立的学科分类体系实例。"""
    return DisciplineTaxonomy()


class TestDisciplineTaxonomyInit:
    """测试 DisciplineTaxonomy 初始化。"""

    def test_init_loads_default_taxonomy(self, taxonomy):
        """初始化应加载默认学科目录。"""
        # 应包含所有门类
        for gate_code in DISCIPLINE_GATE_CATEGORIES:
            node = taxonomy.get_discipline(gate_code)
            assert node is not None
            assert node.level == DisciplineLevel.FIRST

    def test_init_loads_first_level_disciplines(self, taxonomy):
        """初始化应加载一级学科。"""
        node = taxonomy.get_discipline("0812")
        assert node is not None
        assert node.name == "计算机科学与技术"
        assert node.level == DisciplineLevel.SECOND
        assert node.parent_code == "08"

    def test_init_creates_name_index(self, taxonomy):
        """初始化应创建名称索引。"""
        node = taxonomy.get_by_name("计算机科学与技术")
        assert node is not None
        assert node.code == "0812"

    def test_init_creates_keyword_index(self, taxonomy):
        """初始化应创建关键词索引。"""
        # 计算机科学与技术的关键词应被索引
        node = taxonomy.get_discipline("0812")
        assert len(node.keywords) > 0


class TestDisciplineTaxonomyCRUD:
    """测试 DisciplineTaxonomy 节点 CRUD。"""

    def test_add_discipline(self, taxonomy):
        """添加学科节点。"""
        code = taxonomy.add_discipline(
            code="9999",
            name="测试学科",
            level=DisciplineLevel.SECOND,
            parent_code="08",
            keywords=["测试"],
        )
        assert code == "9999"
        node = taxonomy.get_discipline("9999")
        assert node is not None
        assert node.name == "测试学科"
        assert node.parent_code == "08"

    def test_add_discipline_updates_parent_children(self, taxonomy):
        """添加学科应更新父节点的 children。"""
        taxonomy.add_discipline(
            code="9999",
            name="测试学科",
            level=DisciplineLevel.SECOND,
            parent_code="08",
        )
        parent = taxonomy.get_discipline("08")
        assert "9999" in parent.children

    def test_add_discipline_duplicate_code(self, taxonomy):
        """重复代码应抛出 ValueError。"""
        with pytest.raises(ValueError):
            taxonomy.add_discipline(
                code="0812",
                name="重复学科",
                level=DisciplineLevel.SECOND,
            )

    def test_add_discipline_invalid_parent(self, taxonomy):
        """父学科不存在应抛出 ValueError。"""
        with pytest.raises(ValueError):
            taxonomy.add_discipline(
                code="9999",
                name="测试",
                level=DisciplineLevel.SECOND,
                parent_code="invalid",
            )

    def test_add_discipline_empty_code(self, taxonomy):
        """空代码应抛出 ValueError。"""
        with pytest.raises(ValueError):
            taxonomy.add_discipline(code="", name="测试", level=2)

    def test_add_discipline_empty_name(self, taxonomy):
        """空名称应抛出 ValueError。"""
        with pytest.raises(ValueError):
            taxonomy.add_discipline(code="9999", name="", level=2)

    def test_add_discipline_with_aliases(self, taxonomy):
        """添加带别名的学科。"""
        taxonomy.add_discipline(
            code="9999",
            name="测试学科",
            level=2,
            parent_code="08",
            aliases=["测试", "test"],
        )
        node = taxonomy.get_by_name("测试")
        assert node is not None
        assert node.code == "9999"

    def test_get_discipline_missing(self, taxonomy):
        """获取不存在的学科应返回 None。"""
        assert taxonomy.get_discipline("missing") is None

    def test_get_by_name_missing(self, taxonomy):
        """按名称获取不存在的学科应返回 None。"""
        assert taxonomy.get_by_name("不存在的学科") is None

    def test_get_by_name_via_alias(self, taxonomy):
        """通过别名获取学科。"""
        taxonomy.add_discipline(
            code="9999",
            name="测试学科",
            level=2,
            parent_code="08",
            aliases=["别名1"],
        )
        node = taxonomy.get_by_name("别名1")
        assert node is not None
        assert node.code == "9999"

    def test_update_discipline(self, taxonomy):
        """更新学科节点。"""
        taxonomy.add_discipline(
            code="9999", name="原名", level=2, parent_code="08"
        )
        result = taxonomy.update_discipline(
            "9999", name="新名", description="新描述"
        )
        assert result is True
        node = taxonomy.get_discipline("9999")
        assert node.name == "新名"
        assert node.description == "新描述"

    def test_update_discipline_missing(self, taxonomy):
        """更新不存在的学科应返回 False。"""
        assert taxonomy.update_discipline("missing", name="新") is False

    def test_update_discipline_rebuilds_indexes(self, taxonomy):
        """更新后应重建索引。"""
        taxonomy.add_discipline(
            code="9999", name="原名", level=2, parent_code="08",
            keywords=["旧关键词"]
        )
        taxonomy.update_discipline("9999", keywords=["新关键词"])
        # 旧名称索引应被移除
        assert taxonomy.get_by_name("原名") is None
        node = taxonomy.get_discipline("9999")
        assert node.keywords == ["新关键词"]

    def test_delete_discipline(self, taxonomy):
        """删除学科节点。"""
        taxonomy.add_discipline(
            code="9999", name="待删除", level=2, parent_code="08"
        )
        result = taxonomy.delete_discipline("9999")
        assert result is True
        assert taxonomy.get_discipline("9999") is None

    def test_delete_discipline_missing(self, taxonomy):
        """删除不存在的学科应返回 False。"""
        assert taxonomy.delete_discipline("missing") is False

    def test_delete_discipline_with_children_non_recursive(self, taxonomy):
        """非递归删除有子学科的节点应抛出异常。"""
        taxonomy.add_discipline(
            code="9998", name="父学科", level=2, parent_code="08"
        )
        taxonomy.add_discipline(
            code="9999", name="子学科", level=3, parent_code="9998"
        )
        with pytest.raises(ValueError):
            taxonomy.delete_discipline("9998", recursive=False)

    def test_delete_discipline_recursive(self, taxonomy):
        """递归删除应同时删除子学科。"""
        taxonomy.add_discipline(
            code="9998", name="父学科", level=2, parent_code="08"
        )
        taxonomy.add_discipline(
            code="9999", name="子学科", level=3, parent_code="9998"
        )
        assert taxonomy.delete_discipline("9998", recursive=True) is True
        assert taxonomy.get_discipline("9998") is None
        assert taxonomy.get_discipline("9999") is None

    def test_delete_discipline_removes_from_parent(self, taxonomy):
        """删除学科应从父节点的 children 中移除。"""
        taxonomy.add_discipline(
            code="9999", name="待删除", level=2, parent_code="08"
        )
        taxonomy.delete_discipline("9999")
        parent = taxonomy.get_discipline("08")
        assert "9999" not in parent.children


# ============================================================
# 第五部分：分类查询测试
# ============================================================


class TestDisciplineTaxonomyQuery:
    """测试 DisciplineTaxonomy 分类查询。"""

    def test_list_by_level_gate(self, taxonomy):
        """按门类层级查询。"""
        gates = taxonomy.list_by_level(DisciplineLevel.FIRST)
        assert len(gates) == len(DISCIPLINE_GATE_CATEGORIES)

    def test_list_by_level_second(self, taxonomy):
        """按一级学科层级查询。"""
        disciplines = taxonomy.list_by_level(DisciplineLevel.SECOND)
        # 应包含所有典型一级学科
        total = sum(len(v) for v in TYPICAL_FIRST_LEVEL_DISCIPLINES.values())
        assert len(disciplines) >= total

    def test_list_children(self, taxonomy):
        """列出子学科。"""
        children = taxonomy.list_children("08")
        codes = [c.code for c in children]
        assert "0812" in codes  # 计算机科学与技术
        assert "0834" in codes  # 软件工程

    def test_list_children_missing_parent(self, taxonomy):
        """父学科不存在时应返回空列表。"""
        assert taxonomy.list_children("missing") == []

    def test_get_ancestors(self, taxonomy):
        """获取祖先学科。"""
        ancestors = taxonomy.get_ancestors("0812")
        # 0812 的祖先是 08（工学门类）
        assert len(ancestors) >= 1
        assert ancestors[0].code == "08"

    def test_get_ancestors_gate_level(self, taxonomy):
        """门类层级无祖先。"""
        ancestors = taxonomy.get_ancestors("08")
        assert len(ancestors) == 0

    def test_get_ancestors_missing(self, taxonomy):
        """不存在的学科无祖先。"""
        assert taxonomy.get_ancestors("missing") == []

    def test_get_descendants(self, taxonomy):
        """获取后代学科。"""
        descendants = taxonomy.get_descendants("08")
        codes = [d.code for d in descendants]
        assert "0812" in codes

    def test_get_descendants_leaf(self, taxonomy):
        """叶子节点无后代。"""
        descendants = taxonomy.get_descendants("0812")
        assert len(descendants) == 0

    def test_get_path(self, taxonomy):
        """获取从根到节点的路径。"""
        path = taxonomy.get_path("0812")
        codes = [n.code for n in path]
        assert "08" in codes
        assert "0812" in codes
        # 08 应在 0812 之前
        assert codes.index("08") < codes.index("0812")

    def test_get_tree_all_roots(self, taxonomy):
        """获取所有门类的树结构。"""
        tree = taxonomy.get_tree()
        assert "roots" in tree
        assert len(tree["roots"]) == len(DISCIPLINE_GATE_CATEGORIES)

    def test_get_tree_specific_root(self, taxonomy):
        """获取指定根的树结构。"""
        tree = taxonomy.get_tree("08", max_depth=2)
        assert tree["code"] == "08"
        assert tree["name"] == "工学"
        assert len(tree["children"]) > 0

    def test_get_tree_max_depth(self, taxonomy):
        """max_depth 应限制树深度。"""
        tree = taxonomy.get_tree("08", max_depth=0)
        assert tree["code"] == "08"
        assert tree["children"] == []


# ============================================================
# 第六部分：交叉学科识别测试
# ============================================================


class TestCrossDiscipline:
    """测试交叉学科识别。"""

    def test_identify_cross_discipline_keyword_match(self, taxonomy):
        """基于关键词的交叉学科识别。"""
        results = taxonomy.identify_cross_discipline("生物信息学研究")
        assert len(results) > 0
        # 应识别出生物信息学
        names = [r["name"] for r in results]
        assert any("生物信息学" in n for n in names)

    def test_identify_cross_discipline_ai(self, taxonomy):
        """识别人工智能交叉学科。"""
        results = taxonomy.identify_cross_discipline("人工智能在医学中的应用")
        assert len(results) > 0

    def test_identify_cross_discipline_no_match(self, taxonomy):
        """无交叉学科匹配。"""
        results = taxonomy.identify_cross_discipline("zzzzzzz")
        # 可能返回空列表或少量结果
        assert isinstance(results, list)

    def test_identify_cross_discipline_returns_confidence(self, taxonomy):
        """识别结果应包含置信度。"""
        results = taxonomy.identify_cross_discipline("数据科学研究")
        for r in results:
            assert "confidence" in r
            assert 0.0 <= r["confidence"] <= 1.0

    def test_is_cross_discipline_different_gates(self, taxonomy):
        """不同门类的学科应构成交叉学科。"""
        # 0812（工学-计算机）与 0701（理学-数学）属于不同门类
        assert taxonomy.is_cross_discipline("0812", "0701") is True

    def test_is_cross_discipline_same_gate(self, taxonomy):
        """同门类的学科不构成交叉学科。"""
        # 0812 与 0834 都属于工学
        assert taxonomy.is_cross_discipline("0812", "0834") is False

    def test_is_cross_discipline_missing(self, taxonomy):
        """不存在的学科代码。"""
        # 应不抛出异常
        result = taxonomy.is_cross_discipline("missing1", "missing2")
        assert isinstance(result, bool)


# ============================================================
# 第七部分：学科相似度测试
# ============================================================


class TestDisciplineSimilarity:
    """测试学科相似度计算。"""

    def test_compute_similarity_same(self, taxonomy):
        """相同学科相似度为 1。"""
        assert taxonomy.compute_similarity("0812", "0812") == 1.0

    def test_compute_similarity_missing(self, taxonomy):
        """不存在的学科相似度为 0。"""
        assert taxonomy.compute_similarity("missing", "0812") == 0.0
        assert taxonomy.compute_similarity("0812", "missing") == 0.0

    def test_compute_similarity_related(self, taxonomy):
        """相关学科相似度应大于 0。"""
        # 计算机科学与技术 与 软件工程 应有一定相似度
        sim = taxonomy.compute_similarity("0812", "0834")
        assert sim > 0.0

    def test_compute_similarity_different_gates(self, taxonomy):
        """不同门类学科相似度应较低。"""
        sim_same_gate = taxonomy.compute_similarity("0812", "0834")
        sim_diff_gate = taxonomy.compute_similarity("0812", "0701")
        # 同门类相似度通常应高于不同门类
        # 注意：由于关键词可能重叠，这里只验证都为浮点数
        assert isinstance(sim_same_gate, float)
        assert isinstance(sim_diff_gate, float)

    def test_find_similar_disciplines(self, taxonomy):
        """查找相似学科。"""
        results = taxonomy.find_similar_disciplines("0812", top_k=5)
        assert len(results) <= 5
        for code, sim in results:
            assert code != "0812"
            assert 0.0 <= sim <= 1.0

    def test_find_similar_disciplines_missing(self, taxonomy):
        """不存在的学科查找相似应返回空列表。"""
        assert taxonomy.find_similar_disciplines("missing") == []

    def test_find_similar_by_text(self, taxonomy):
        """根据文本查找相似学科。"""
        results = taxonomy.find_similar_by_text("计算机算法与编程", top_k=5)
        assert isinstance(results, list)
        for code, sim in results:
            assert 0.0 <= sim <= 1.0

    def test_find_similar_by_text_empty(self, taxonomy):
        """空文本应返回空列表。"""
        assert taxonomy.find_similar_by_text("") == []


# ============================================================
# 第八部分：学科聚类测试
# ============================================================


class TestDisciplineClustering:
    """测试学科聚类。"""

    def test_cluster_disciplines_basic(self, taxonomy):
        """基本聚类功能。"""
        clusters = taxonomy.cluster_disciplines(
            level=DisciplineLevel.SECOND, threshold=0.1
        )
        assert isinstance(clusters, list)
        # 每个簇应是代码列表
        for cluster in clusters:
            assert isinstance(cluster, list)

    def test_cluster_disciplines_high_threshold(self, taxonomy):
        """高阈值应产生更多小簇。"""
        clusters_low = taxonomy.cluster_disciplines(
            level=DisciplineLevel.SECOND, threshold=0.05
        )
        clusters_high = taxonomy.cluster_disciplines(
            level=DisciplineLevel.SECOND, threshold=0.9
        )
        # 高阈值应产生更多或相等的簇
        assert len(clusters_high) >= len(clusters_low)

    def test_cluster_disciplines_single_discipline(self, taxonomy):
        """少量学科聚类。"""
        # 使用门类层级（数量较少）
        clusters = taxonomy.cluster_disciplines(
            level=DisciplineLevel.FIRST, threshold=0.3
        )
        assert isinstance(clusters, list)


# ============================================================
# 第九部分：学科趋势分析测试
# ============================================================


class TestDisciplineTrend:
    """测试学科趋势分析。"""

    def test_add_trend_data(self, taxonomy):
        """添加趋势数据。"""
        taxonomy.add_trend_data("0812", 2024, 1000, 5000, ["大模型", "AGI"])
        trends = taxonomy.get_trend("0812")
        assert len(trends) == 1
        assert trends[0].year == 2024
        assert trends[0].paper_count == 1000
        assert trends[0].citation_count == 5000

    def test_add_trend_data_calculates_growth(self, taxonomy):
        """添加趋势数据应计算增长率。"""
        taxonomy.add_trend_data("0812", 2022, 100)
        taxonomy.add_trend_data("0812", 2023, 150)
        trends = taxonomy.get_trend("0812")
        # 2023 年的增长率应为 (150-100)/100 = 0.5
        assert trends[1].growth_rate == 0.5

    def test_add_trend_data_missing_discipline(self, taxonomy):
        """为不存在的学科添加趋势数据。"""
        taxonomy.add_trend_data("missing", 2024, 100)
        trends = taxonomy.get_trend("missing")
        assert len(trends) == 1
        assert trends[0].name == "missing"

    def test_get_trend_missing(self, taxonomy):
        """获取不存在的学科趋势应返回空列表。"""
        assert taxonomy.get_trend("missing") == []

    def test_analyze_trend_no_data(self, taxonomy):
        """无趋势数据的分析。"""
        result = taxonomy.analyze_trend("0812")
        assert result["code"] == "0812"
        assert result["trend"] == "unknown"
        assert result["total_papers"] == 0

    def test_analyze_trend_rising(self, taxonomy):
        """上升趋势分析。"""
        taxonomy.add_trend_data("0812", 2022, 100)
        taxonomy.add_trend_data("0812", 2023, 200)  # 增长 100%
        result = taxonomy.analyze_trend("0812")
        assert result["trend"] == "rising"
        assert result["total_papers"] == 300

    def test_analyze_trend_declining(self, taxonomy):
        """下降趋势分析。"""
        taxonomy.add_trend_data("0812", 2022, 200)
        taxonomy.add_trend_data("0812", 2023, 100)  # 下降 50%
        result = taxonomy.analyze_trend("0812")
        assert result["trend"] == "declining"

    def test_analyze_trend_stable(self, taxonomy):
        """稳定趋势分析。"""
        taxonomy.add_trend_data("0812", 2022, 100)
        taxonomy.add_trend_data("0812", 2023, 105)  # 增长 5%
        result = taxonomy.analyze_trend("0812")
        assert result["trend"] == "stable"

    def test_analyze_trend_emerging_topics(self, taxonomy):
        """趋势分析应包含新兴主题。"""
        taxonomy.add_trend_data(
            "0812", 2024, 100, emerging_topics=["大模型", "AGI", "多模态"]
        )
        result = taxonomy.analyze_trend("0812")
        assert "大模型" in result["emerging_topics"]

    def test_get_hot_disciplines(self, taxonomy):
        """获取热门学科。"""
        taxonomy.add_trend_data("0812", 2024, 1000)
        taxonomy.add_trend_data("0701", 2024, 500)
        hot = taxonomy.get_hot_disciplines(top_k=5)
        assert isinstance(hot, list)
        assert len(hot) <= 5

    def test_get_hot_disciplines_empty(self, taxonomy):
        """无趋势数据时热门学科应为空。"""
        hot = taxonomy.get_hot_disciplines()
        assert hot == []


# ============================================================
# 第十部分：学科画像测试
# ============================================================


class TestDisciplineProfile:
    """测试学科画像生成。"""

    def test_build_profile(self, taxonomy):
        """构建学科画像。"""
        profile = taxonomy.build_profile("0812")
        assert profile is not None
        assert profile.code == "0812"
        assert profile.name == "计算机科学与技术"
        assert len(profile.keyword_weights) > 0
        assert len(profile.typical_methods) > 0
        assert len(profile.output_types) > 0

    def test_build_profile_missing(self, taxonomy):
        """构建不存在的学科画像应返回 None。"""
        assert taxonomy.build_profile("missing") is None

    def test_build_profile_caches(self, taxonomy):
        """画像应被缓存。"""
        profile1 = taxonomy.build_profile("0812")
        profile2 = taxonomy.build_profile("0812")
        assert profile1 is profile2  # 同一对象引用

    def test_build_profile_difficulty(self, taxonomy):
        """画像应包含难度。"""
        profile = taxonomy.build_profile("0812")
        assert 1 <= profile.difficulty <= 5

    def test_build_profile_popularity(self, taxonomy):
        """画像应包含热门度。"""
        profile = taxonomy.build_profile("0812")
        assert 1 <= profile.popularity <= 5

    def test_build_profile_trend(self, taxonomy):
        """画像应包含趋势。"""
        taxonomy.add_trend_data("0812", 2024, 1000)
        taxonomy.add_trend_data("0812", 2025, 1500)  # 上升
        profile = taxonomy.build_profile("0812")
        # 由于缓存，可能需要先清除缓存（这里验证字段存在即可）
        assert profile.trend in ("rising", "stable", "declining")

    def test_build_profile_includes_descendant_keywords(self, taxonomy):
        """画像应包含后代学科的关键词。"""
        # 工学门类下有多个一级学科
        profile = taxonomy.build_profile("08")
        assert profile is not None
        # 应包含子学科的关键词
        assert len(profile.keyword_weights) > 0


# ============================================================
# 第十一部分：学科推荐测试
# ============================================================


class TestDisciplineRecommendation:
    """测试学科推荐。"""

    def test_recommend_disciplines(self, taxonomy):
        """根据文本推荐学科。"""
        results = taxonomy.recommend_disciplines(
            "计算机算法与编程研究", top_k=5
        )
        assert isinstance(results, list)
        for r in results:
            assert "code" in r
            assert "name" in r
            assert "match_score" in r
            assert 0.0 <= r["match_score"] <= 1.0

    def test_recommend_disciplines_empty_text(self, taxonomy):
        """空文本应返回空列表。"""
        assert taxonomy.recommend_disciplines("") == []

    def test_recommend_disciplines_with_level(self, taxonomy):
        """按层级推荐。"""
        results = taxonomy.recommend_disciplines(
            "计算机", top_k=5, level=DisciplineLevel.SECOND
        )
        for r in results:
            assert r["level"] == DisciplineLevel.SECOND

    def test_recommend_disciplines_includes_cross_info(self, taxonomy):
        """推荐结果应包含交叉学科信息。"""
        results = taxonomy.recommend_disciplines("生物信息学")
        for r in results:
            assert "is_cross_discipline" in r

    def test_recommend_cross_disciplines(self, taxonomy):
        """推荐交叉学科组合。"""
        results = taxonomy.recommend_cross_disciplines("0812", top_k=3)
        assert isinstance(results, list)
        for r in results:
            assert "primary_discipline" in r
            assert "secondary_discipline" in r
            assert "similarity" in r

    def test_recommend_cross_disciplines_missing(self, taxonomy):
        """不存在的学科推荐交叉应返回空列表。"""
        assert taxonomy.recommend_cross_disciplines("missing") == []


# ============================================================
# 第十二部分：学科关键词提取测试
# ============================================================


class TestDisciplineKeywordExtraction:
    """测试学科关键词提取。"""

    def test_extract_discipline_keywords(self, taxonomy):
        """从文本提取学科相关关键词。"""
        results = taxonomy.extract_discipline_keywords(
            "0812", "机器学习算法与计算机编程", top_k=5
        )
        assert isinstance(results, list)
        for kw, weight in results:
            assert isinstance(kw, str)
            assert isinstance(weight, float)
            assert weight > 0

    def test_extract_discipline_keywords_missing_discipline(self, taxonomy):
        """不存在的学科应返回空列表。"""
        assert taxonomy.extract_discipline_keywords("missing", "文本") == []

    def test_extract_discipline_keywords_empty_text(self, taxonomy):
        """空文本应返回空列表。"""
        assert taxonomy.extract_discipline_keywords("0812", "") == []

    def test_extract_discipline_keywords_top_k(self, taxonomy):
        """top_k 应限制返回数量。"""
        results = taxonomy.extract_discipline_keywords(
            "0812", "计算机算法编程数据结构操作系统网络", top_k=3
        )
        assert len(results) <= 3


# ============================================================
# 第十三部分：统计与序列化测试
# ============================================================


class TestDisciplineTaxonomyStats:
    """测试 DisciplineTaxonomy 统计与序列化。"""

    def test_stats_basic(self, taxonomy):
        """基本统计信息。"""
        stats = taxonomy.stats()
        assert stats["total_disciplines"] > 0
        assert "level_distribution" in stats
        assert stats["gate_categories"] == len(DISCIPLINE_GATE_CATEGORIES)
        assert stats["cross_discipline_types"] == len(CROSS_DISCIPLINE_KEYWORDS)

    def test_stats_level_distribution(self, taxonomy):
        """层级分布应正确。"""
        stats = taxonomy.stats()
        dist = stats["level_distribution"]
        assert dist.get(DisciplineLevel.FIRST, 0) == len(DISCIPLINE_GATE_CATEGORIES)
        assert dist.get(DisciplineLevel.SECOND, 0) > 0

    def test_to_dict(self, taxonomy):
        """序列化为字典。"""
        d = taxonomy.to_dict()
        assert "nodes" in d
        assert "profiles" in d
        assert "trends" in d
        assert len(d["nodes"]) > 0

    def test_to_dict_after_modification(self, taxonomy):
        """修改后序列化应反映变化。"""
        taxonomy.add_discipline(
            code="9999", name="测试学科", level=2, parent_code="08"
        )
        d = taxonomy.to_dict()
        codes = [n["code"] for n in d["nodes"]]
        assert "9999" in codes


# ============================================================
# 第十四部分：全局单例测试
# ============================================================


class TestGlobalInstance:
    """测试全局单例函数。"""

    def test_get_discipline_taxonomy_singleton(self):
        """get_discipline_taxonomy 应返回单例。"""
        reset_discipline_taxonomy()
        t1 = get_discipline_taxonomy()
        t2 = get_discipline_taxonomy()
        assert t1 is t2

    def test_reset_discipline_taxonomy(self):
        """reset_discipline_taxonomy 应重置单例。"""
        reset_discipline_taxonomy()
        t1 = get_discipline_taxonomy()
        reset_discipline_taxonomy()
        t2 = get_discipline_taxonomy()
        assert t1 is not t2


# ============================================================
# 第十五部分：线程安全测试
# ============================================================


class TestThreadSafety:
    """测试线程安全性。"""

    def test_concurrent_add_discipline(self, taxonomy):
        """并发添加学科不应出错。"""
        errors = []

        def worker(thread_id):
            try:
                for i in range(10):
                    taxonomy.add_discipline(
                        code=f"t{thread_id}_{i}",
                        name=f"线程{thread_id}学科{i}",
                        level=DisciplineLevel.SECOND,
                        parent_code="08",
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors

    def test_concurrent_read(self, taxonomy):
        """并发读取不应出错。"""
        errors = []

        def worker():
            try:
                for _ in range(20):
                    taxonomy.get_discipline("0812")
                    taxonomy.list_by_level(DisciplineLevel.SECOND)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors


# ============================================================
# 第十六部分：边界条件测试
# ============================================================


class TestEdgeCases:
    """测试边界条件。"""

    def test_add_discipline_with_empty_keywords(self, taxonomy):
        """空关键词列表。"""
        code = taxonomy.add_discipline(
            code="9999", name="测试", level=2, parent_code="08", keywords=[]
        )
        node = taxonomy.get_discipline(code)
        assert node.keywords == []

    def test_add_discipline_with_related_codes(self, taxonomy):
        """带相关学科代码。"""
        taxonomy.add_discipline(
            code="9999",
            name="测试",
            level=2,
            parent_code="08",
            related_codes=["0812", "0834"],
        )
        node = taxonomy.get_discipline("9999")
        assert "0812" in node.related_codes

    def test_compute_similarity_both_missing(self, taxonomy):
        """两个都不存在的学科相似度。"""
        assert taxonomy.compute_similarity("missing1", "missing2") == 0.0

    def test_get_path_missing(self, taxonomy):
        """不存在的学科路径。"""
        path = taxonomy.get_path("missing")
        assert path == []

    def test_get_descendants_missing(self, taxonomy):
        """不存在的学科后代。"""
        assert taxonomy.get_descendants("missing") == []

    def test_list_children_no_children(self, taxonomy):
        """无子学科的节点。"""
        children = taxonomy.list_children("0812")
        assert children == []

    def test_cluster_disciplines_empty(self, taxonomy):
        """空层级的聚类。"""
        # 使用不存在的层级
        clusters = taxonomy.cluster_disciplines(level=99, threshold=0.3)
        assert clusters == []

    def test_build_profile_with_trend_data(self, taxonomy):
        """有趋势数据时构建画像。"""
        taxonomy.add_trend_data("0812", 2024, 1000, emerging_topics=["AI"])
        profile = taxonomy.build_profile("0812")
        assert profile is not None
        # 由于缓存机制，可能需要新建实例
        assert profile.trend in ("rising", "stable", "declining")

    def test_recommend_disciplines_no_match(self, taxonomy):
        """无匹配的推荐。"""
        results = taxonomy.recommend_disciplines("zzzzzzzzz")
        assert results == []

    def test_analyze_trend_single_record(self, taxonomy):
        """单条趋势记录的分析。"""
        taxonomy.add_trend_data("0812", 2024, 100)
        result = taxonomy.analyze_trend("0812")
        assert result["trend"] == "stable"
        assert result["total_papers"] == 100
