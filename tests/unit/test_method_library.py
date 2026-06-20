"""研究方法库模块单元测试

测试 backend/knowledge/method_library.py 中的 MethodLibrary 类及其辅助组件：
  - MethodStep / MethodParameter / ResearchMethod 数据结构
  - 工具函数：_tokenize / _jaccard / _now_iso / _new_id
  - MethodLibrary 方法 CRUD、分类查询、方法对比
  - 方法组合推荐、方法-论题匹配、方法迁移建议
  - 方法评估、智能推荐、统计

测试策略：
  - 使用真实初始化的默认研究方法数据
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

from backend.knowledge.method_library import (  # noqa: E402
    MethodLibrary,
    ResearchMethod,
    MethodStep,
    MethodParameter,
    MethodCategory,
    CATEGORY_NAMES,
    DIFFICULTY_LEVELS,
    DEFAULT_METHODS,
    _tokenize,
    _jaccard,
    _now_iso,
    _new_id,
    get_method_library,
    reset_method_library,
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

    def test_tokenize_chinese_bigram(self):
        """中文文本应按 2-gram 切分。"""
        tokens = _tokenize("问卷调查")
        assert "问卷" in tokens
        assert "调查" in tokens

    def test_tokenize_mixed(self):
        """中英文混合文本。"""
        tokens = _tokenize("使用 SPSS 进行统计分析")
        assert "spss" in tokens

    def test_tokenize_with_numbers(self):
        """含数字的文本。"""
        tokens = _tokenize("python3 analysis")
        assert "python3" in tokens


class TestJaccard:
    """测试 _jaccard 相似度函数。"""

    def test_identical_sets(self):
        """相同集合相似度为 1。"""
        s = {"a", "b", "c"}
        assert _jaccard(s, s) == 1.0

    def test_disjoint_sets(self):
        """不相交集合相似度为 0。"""
        assert _jaccard({"a"}, {"b"}) == 0.0

    def test_empty_sets(self):
        """两个空集合相似度为 0。"""
        assert _jaccard(set(), set()) == 0.0

    def test_partial_overlap(self):
        """部分重叠的集合。"""
        s1 = {"a", "b", "c"}
        s2 = {"b", "c", "d"}
        assert _jaccard(s1, s2) == 0.5


class TestNowIso:
    """测试 _now_iso 时间函数。"""

    def test_returns_iso_format(self):
        """应返回 ISO 格式时间字符串。"""
        result = _now_iso()
        assert isinstance(result, str)
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
        id1 = _new_id("method")
        assert id1.startswith("method_")

    def test_default_prefix(self):
        """默认前缀应为 method。"""
        id1 = _new_id()
        assert id1.startswith("method_")

    def test_uniqueness(self):
        """连续生成的 ID 应唯一。"""
        ids = {_new_id() for _ in range(100)}
        assert len(ids) == 100


# ============================================================
# 第二部分：数据结构测试
# ============================================================


class TestMethodStep:
    """测试 MethodStep 数据结构。"""

    def test_default_values(self):
        """默认值应正确。"""
        step = MethodStep()
        assert step.order == 0
        assert step.name == ""
        assert step.required is True
        assert step.tips == []

    def test_to_dict(self):
        """to_dict 应返回完整字典。"""
        step = MethodStep(order=1, name="步骤1", description="描述")
        d = step.to_dict()
        assert d["order"] == 1
        assert d["name"] == "步骤1"
        assert d["description"] == "描述"


class TestMethodParameter:
    """测试 MethodParameter 数据结构。"""

    def test_default_values(self):
        """默认值应正确。"""
        param = MethodParameter()
        assert param.name == ""
        assert param.param_type == "string"
        assert param.required is False

    def test_to_dict(self):
        """to_dict 应返回完整字典。"""
        param = MethodParameter(
            name="sample_size",
            param_type="int",
            default=100,
            min_value=10,
            max_value=1000,
        )
        d = param.to_dict()
        assert d["name"] == "sample_size"
        assert d["param_type"] == "int"
        assert d["default"] == 100
        assert d["min_value"] == 10
        assert d["max_value"] == 1000


class TestResearchMethod:
    """测试 ResearchMethod 数据结构。"""

    def test_default_values(self):
        """默认值应正确。"""
        method = ResearchMethod()
        assert method.id == ""
        assert method.category == MethodCategory.QUANTITATIVE
        assert method.difficulty == 3
        assert method.time_cost == "中"
        assert method.cost_level == "低"

    def test_to_dict(self):
        """to_dict 应返回完整字典。"""
        method = ResearchMethod(id="m1", name="测试方法", category="quantitative")
        d = method.to_dict()
        assert d["id"] == "m1"
        assert d["name"] == "测试方法"
        assert d["category"] == "quantitative"

    def test_from_dict(self):
        """from_dict 应正确构造实例。"""
        data = {
            "id": "m1",
            "name": "测试方法",
            "category": "qualitative",
            "difficulty": 4,
            "aliases": ["别名"],
        }
        method = ResearchMethod.from_dict(data)
        assert method.id == "m1"
        assert method.name == "测试方法"
        assert method.category == "qualitative"
        assert method.difficulty == 4
        assert method.aliases == ["别名"]

    def test_from_dict_ignores_unknown_fields(self):
        """from_dict 应忽略未知字段。"""
        data = {"id": "m1", "unknown": "value"}
        method = ResearchMethod.from_dict(data)
        assert method.id == "m1"

    def test_get_detailed_steps(self):
        """获取详细步骤对象列表。"""
        method = ResearchMethod(
            steps=["步骤1", "步骤2", "步骤3"]
        )
        steps = method.get_detailed_steps()
        assert len(steps) == 3
        assert steps[0].order == 1
        assert steps[0].name == "步骤1"
        assert steps[1].order == 2
        assert steps[2].order == 3

    def test_get_parameters(self):
        """获取参数对象列表。"""
        method = ResearchMethod(
            parameters={
                "sample_size": {"type": "int", "default": 100, "min": 10, "max": 1000},
                "method_type": {"type": "enum", "options": ["a", "b"], "default": "a"},
            }
        )
        params = method.get_parameters()
        assert len(params) == 2
        names = [p.name for p in params]
        assert "sample_size" in names
        assert "method_type" in names

    def test_get_parameters_empty(self):
        """无参数时应返回空列表。"""
        method = ResearchMethod()
        assert method.get_parameters() == []


# ============================================================
# 第三部分：常量测试
# ============================================================


class TestConstants:
    """测试模块常量。"""

    def test_method_category_constants(self):
        """方法分类常量应正确。"""
        assert MethodCategory.QUANTITATIVE == "quantitative"
        assert MethodCategory.QUALITATIVE == "qualitative"
        assert MethodCategory.MIXED == "mixed"
        assert MethodCategory.THEORETICAL == "theoretical"
        assert MethodCategory.EMPIRICAL == "empirical"

    def test_category_names_complete(self):
        """分类名称映射应完整。"""
        assert len(CATEGORY_NAMES) == 5
        assert CATEGORY_NAMES[MethodCategory.QUANTITATIVE] == "定量方法"
        assert CATEGORY_NAMES[MethodCategory.QUALITATIVE] == "定性方法"

    def test_difficulty_levels(self):
        """难度等级映射应正确。"""
        assert len(DIFFICULTY_LEVELS) == 5
        assert DIFFICULTY_LEVELS[1] == "入门"
        assert DIFFICULTY_LEVELS[5] == "高级"

    def test_default_methods_not_empty(self):
        """默认方法列表应非空。"""
        assert len(DEFAULT_METHODS) > 0
        # 应包含问卷调查法
        names = [m["name"] for m in DEFAULT_METHODS]
        assert "问卷调查法" in names
        assert "实验研究法" in names


# ============================================================
# 第四部分：MethodLibrary 初始化与 CRUD 测试
# ============================================================


@pytest.fixture
def library():
    """提供独立的方法库实例。"""
    return MethodLibrary()


class TestMethodLibraryInit:
    """测试 MethodLibrary 初始化。"""

    def test_init_loads_default_methods(self, library):
        """初始化应加载默认方法。"""
        methods = library.list_all()
        assert len(methods) == len(DEFAULT_METHODS)

    def test_init_creates_name_index(self, library):
        """初始化应创建名称索引。"""
        method = library.get_by_name("问卷调查法")
        assert method is not None
        assert method.id == "method_survey"

    def test_init_creates_alias_index(self, library):
        """初始化应创建别名索引。"""
        method = library.get_by_name("survey")
        assert method is not None
        assert method.id == "method_survey"

    def test_init_creates_category_index(self, library):
        """初始化应创建分类索引。"""
        quant_methods = library.list_by_category(MethodCategory.QUANTITATIVE)
        assert len(quant_methods) > 0

    def test_init_creates_discipline_index(self, library):
        """初始化应创建学科索引。"""
        # 问卷调查法适用于 0401（教育学）
        methods = library.list_by_discipline("0401")
        assert len(methods) > 0


class TestMethodLibraryCRUD:
    """测试 MethodLibrary 方法 CRUD。"""

    def test_add_method_basic(self, library):
        """添加方法应返回 ID。"""
        method_id = library.add_method(
            name="测试方法",
            category=MethodCategory.QUANTITATIVE,
            description="测试描述",
        )
        assert method_id.startswith("method_")
        method = library.get_method(method_id)
        assert method is not None
        assert method.name == "测试方法"
        assert method.category == MethodCategory.QUANTITATIVE

    def test_add_method_with_all_params(self, library):
        """添加带所有参数的方法。"""
        method_id = library.add_method(
            name="完整方法",
            category=MethodCategory.QUALITATIVE,
            description="描述",
            aliases=["别名1", "别名2"],
            applicable_scenarios=["场景1"],
            advantages=["优点1"],
            disadvantages=["缺点1"],
            steps=["步骤1", "步骤2"],
            parameters={"param1": {"type": "int", "default": 10}},
            applicable_disciplines=["0812"],
            data_types=["文本数据"],
            tools=["Python"],
            difficulty=4,
            time_cost="高",
            cost_level="中",
            keywords=["关键词"],
            related_methods=["method_survey"],
        )
        method = library.get_method(method_id)
        assert method.name == "完整方法"
        assert method.aliases == ["别名1", "别名2"]
        assert method.difficulty == 4
        assert method.time_cost == "高"

    def test_add_method_empty_name(self, library):
        """空名称应抛出 ValueError。"""
        with pytest.raises(ValueError):
            library.add_method(name="", category=MethodCategory.QUANTITATIVE)

    def test_add_method_invalid_category(self, library):
        """无效分类应抛出 ValueError。"""
        with pytest.raises(ValueError):
            library.add_method(name="测试", category="invalid_category")

    def test_add_method_clamps_difficulty(self, library):
        """难度应被限制在 1-5 范围。"""
        method_id = library.add_method(
            name="测试", category=MethodCategory.QUANTITATIVE, difficulty=10
        )
        method = library.get_method(method_id)
        assert method.difficulty == 5

        method_id = library.add_method(
            name="测试2", category=MethodCategory.QUANTITATIVE, difficulty=0
        )
        method = library.get_method(method_id)
        assert method.difficulty == 1

    def test_add_method_auto_extracts_keywords(self, library):
        """未提供关键词时应自动提取。"""
        method_id = library.add_method(
            name="自动提取",
            category=MethodCategory.QUANTITATIVE,
            description="机器学习算法分析",
        )
        method = library.get_method(method_id)
        assert len(method.keywords) > 0
        assert "自动提取" in method.keywords  # 名称应被加入关键词

    def test_get_method_missing(self, library):
        """获取不存在的方法应返回 None。"""
        assert library.get_method("missing") is None

    def test_get_by_name_missing(self, library):
        """按名称获取不存在的方法应返回 None。"""
        assert library.get_by_name("不存在的方法") is None

    def test_get_by_name_via_alias(self, library):
        """通过别名获取方法。"""
        method_id = library.add_method(
            name="原名",
            category=MethodCategory.QUANTITATIVE,
            aliases=["别名A"],
        )
        method = library.get_by_name("别名A")
        assert method is not None
        assert method.id == method_id

    def test_update_method(self, library):
        """更新方法。"""
        method_id = library.add_method(
            name="原名", category=MethodCategory.QUANTITATIVE
        )
        result = library.update_method(method_id, name="新名", difficulty=5)
        assert result is True
        method = library.get_method(method_id)
        assert method.name == "新名"
        assert method.difficulty == 5

    def test_update_method_missing(self, library):
        """更新不存在的方法应返回 False。"""
        assert library.update_method("missing", name="新") is False

    def test_update_method_rebuilds_indexes(self, library):
        """更新后应重建索引。"""
        method_id = library.add_method(
            name="原名",
            category=MethodCategory.QUANTITATIVE,
            aliases=["原别名"],
        )
        library.update_method(method_id, name="新名", aliases=["新别名"])
        # 旧名称索引应被移除
        assert library.get_by_name("原名") is None
        assert library.get_by_name("原别名") is None
        # 新名称索引应存在
        assert library.get_by_name("新名") is not None
        assert library.get_by_name("新别名") is not None

    def test_delete_method(self, library):
        """删除方法。"""
        method_id = library.add_method(
            name="待删除", category=MethodCategory.QUANTITATIVE
        )
        result = library.delete_method(method_id)
        assert result is True
        assert library.get_method(method_id) is None

    def test_delete_method_missing(self, library):
        """删除不存在的方法应返回 False。"""
        assert library.delete_method("missing") is False

    def test_delete_method_clears_indexes(self, library):
        """删除方法应清理索引。"""
        method_id = library.add_method(
            name="待删除",
            category=MethodCategory.QUANTITATIVE,
            aliases=["别名"],
            applicable_disciplines=["0812"],
        )
        library.delete_method(method_id)
        assert library.get_by_name("待删除") is None
        assert library.get_by_name("别名") is None
        # 学科索引中应不再包含该方法
        disc_methods = library.list_by_discipline("0812")
        assert all(m.id != method_id for m in disc_methods)


# ============================================================
# 第五部分：分类查询测试
# ============================================================


class TestMethodLibraryQuery:
    """测试 MethodLibrary 分类查询。"""

    def test_list_by_category_quantitative(self, library):
        """列出定量方法。"""
        methods = library.list_by_category(MethodCategory.QUANTITATIVE)
        assert len(methods) > 0
        for m in methods:
            assert m.category == MethodCategory.QUANTITATIVE

    def test_list_by_category_qualitative(self, library):
        """列出定性方法。"""
        methods = library.list_by_category(MethodCategory.QUALITATIVE)
        assert len(methods) > 0
        for m in methods:
            assert m.category == MethodCategory.QUALITATIVE

    def test_list_by_category_mixed(self, library):
        """列出混合方法。"""
        methods = library.list_by_category(MethodCategory.MIXED)
        assert len(methods) > 0

    def test_list_by_category_theoretical(self, library):
        """列出理论方法。"""
        methods = library.list_by_category(MethodCategory.THEORETICAL)
        assert len(methods) > 0

    def test_list_by_category_invalid(self, library):
        """无效分类应返回空列表。"""
        assert library.list_by_category("invalid") == []

    def test_list_all(self, library):
        """列出所有方法。"""
        methods = library.list_all()
        assert len(methods) == len(DEFAULT_METHODS)

    def test_list_by_discipline(self, library):
        """按学科列出方法。"""
        # 0401（教育学）应包含问卷调查法
        methods = library.list_by_discipline("0401")
        assert len(methods) > 0
        names = [m.name for m in methods]
        assert "问卷调查法" in names

    def test_list_by_discipline_no_match(self, library):
        """无匹配学科的方法应返回空列表。"""
        assert library.list_by_discipline("9999") == []

    def test_list_by_difficulty(self, library):
        """按难度列出方法。"""
        methods = library.list_by_difficulty(2)
        for m in methods:
            assert m.difficulty <= 2

    def test_list_by_difficulty_all(self, library):
        """难度 5 应包含所有方法。"""
        methods = library.list_by_difficulty(5)
        assert len(methods) == len(DEFAULT_METHODS)

    def test_list_by_data_type(self, library):
        """按数据类型列出方法。"""
        methods = library.list_by_data_type("截面数据")
        assert len(methods) > 0
        for m in methods:
            assert "截面数据" in m.data_types

    def test_list_by_data_type_no_match(self, library):
        """无匹配数据类型应返回空列表。"""
        assert library.list_by_data_type("不存在的数据类型") == []


# ============================================================
# 第六部分：方法对比测试
# ============================================================


class TestMethodComparison:
    """测试方法对比功能。"""

    def test_compare_methods_basic(self, library):
        """基本方法对比。"""
        result = library.compare_methods(["method_survey", "method_experiment"])
        assert "methods" in result
        assert "comparison" in result
        assert len(result["methods"]) == 2
        assert "difficulty" in result["comparison"]
        assert "common_advantages" in result

    def test_compare_methods_single(self, library):
        """单个方法对比应返回错误。"""
        result = library.compare_methods(["method_survey"])
        assert "error" in result

    def test_compare_methods_empty(self, library):
        """空列表对比应返回错误。"""
        result = library.compare_methods([])
        assert "error" in result

    def test_compare_methods_with_invalid_id(self, library):
        """包含无效 ID 的对比应忽略无效方法。"""
        result = library.compare_methods(["method_survey", "invalid_id"])
        # 只有一个有效方法，应返回错误
        assert "error" in result

    def test_compare_methods_common_disciplines(self, library):
        """对比应找出共同学科。"""
        # 问卷调查法和实验研究法都适用于 0402（心理学）
        result = library.compare_methods(["method_survey", "method_experiment"])
        assert "common_disciplines" in result
        # 应包含 0402
        assert "0402" in result["common_disciplines"]

    def test_compare_methods_includes_counts(self, library):
        """对比应包含各项计数。"""
        result = library.compare_methods(["method_survey", "method_experiment"])
        comp = result["comparison"]
        assert "advantages_count" in comp
        assert "disadvantages_count" in comp
        assert "steps_count" in comp
        assert "disciplines_count" in comp


# ============================================================
# 第七部分：方法组合推荐测试
# ============================================================


class TestMethodCombination:
    """测试方法组合推荐。"""

    def test_recommend_combination_basic(self, library):
        """基本组合推荐。"""
        results = library.recommend_combination(
            "用户满意度问卷调查分析", discipline_code="0401", max_methods=3
        )
        assert isinstance(results, list)
        assert len(results) <= 3
        for r in results:
            assert "method" in r
            assert "role" in r
            assert "match_score" in r
            assert "reason" in r

    def test_recommend_combination_caches(self, library):
        """组合推荐应被缓存。"""
        results1 = library.recommend_combination("问卷调查", max_methods=2)
        results2 = library.recommend_combination("问卷调查", max_methods=2)
        # 应返回相同结果（缓存命中）
        assert len(results1) == len(results2)

    def test_recommend_combination_no_match(self, library):
        """无匹配的组合推荐。"""
        results = library.recommend_combination("zzzzzzzzz")
        assert results == []

    def test_recommend_combination_with_discipline(self, library):
        """带学科的组合推荐。"""
        results = library.recommend_combination(
            "教育研究", discipline_code="0401", max_methods=2
        )
        # 学科匹配的方法应优先
        if results:
            for r in results:
                assert "method" in r

    def test_recommend_combination_roles(self, library):
        """组合推荐应分配角色。"""
        results = library.recommend_combination(
            "问卷调查与深度访谈", max_methods=3
        )
        if len(results) >= 2:
            roles = [r["role"] for r in results]
            # 第一个应为 primary
            assert roles[0] == "primary"

    def test_recommend_combination_diverse_categories(self, library):
        """组合推荐应优先不同分类的方法。"""
        results = library.recommend_combination(
            "问卷与访谈结合研究", max_methods=3
        )
        if len(results) >= 2:
            categories = [r["method"]["category"] for r in results]
            # 应有不同分类
            assert len(set(categories)) > 1


# ============================================================
# 第八部分：方法-论题匹配测试
# ============================================================


class TestMethodTopicMatching:
    """测试方法-论题匹配。"""

    def test_match_topic_basic(self, library):
        """基本论题匹配。"""
        results = library.match_topic("用户满意度问卷调查", top_k=5)
        assert isinstance(results, list)
        for r in results:
            assert "method" in r
            assert "match_score" in r
            assert "match_reasons" in r
            assert 0.0 <= r["match_score"] <= 1.0

    def test_match_topic_with_discipline(self, library):
        """带学科的论题匹配。"""
        results = library.match_topic(
            "教育研究", discipline_code="0401", top_k=5
        )
        for r in results:
            assert "discipline_match" in r

    def test_match_topic_no_match(self, library):
        """无匹配的论题。"""
        results = library.match_topic("zzzzzzzzz")
        assert results == []

    def test_match_topic_includes_reasons(self, library):
        """匹配结果应包含理由。"""
        results = library.match_topic("问卷调查", top_k=3)
        for r in results:
            assert len(r["match_reasons"]) > 0

    def test_match_topic_top_k(self, library):
        """top_k 应限制返回数量。"""
        results = library.match_topic("研究方法", top_k=2)
        assert len(results) <= 2

    def test_match_topic_discipline_match_boost(self, library):
        """学科匹配应加分。"""
        # 问卷调查法适用于 0401
        results_with_disc = library.match_topic(
            "问卷调查", discipline_code="0401", top_k=5
        )
        results_without_disc = library.match_topic("问卷调查", top_k=5)
        # 有学科匹配的方法应得分更高或相等
        if results_with_disc and results_without_disc:
            for r in results_with_disc:
                if r["discipline_match"]:
                    # 学科匹配的方法得分应被加分
                    assert r["match_score"] > 0


# ============================================================
# 第九部分：方法迁移建议测试
# ============================================================


class TestMethodTransfer:
    """测试方法迁移建议。"""

    def test_suggest_method_transfer_basic(self, library):
        """基本方法迁移建议。"""
        result = library.suggest_method_transfer("method_survey", "0812")
        assert "method" in result
        assert "target_discipline" in result
        assert "feasibility_score" in result
        assert "feasibility_level" in result
        assert "adjustments" in result
        assert "potential_advantages" in result
        assert "potential_challenges" in result

    def test_suggest_method_transfer_missing_method(self, library):
        """不存在的方应返回错误。"""
        result = library.suggest_method_transfer("missing", "0812")
        assert "error" in result

    def test_suggest_method_transfer_already_applicable(self, library):
        """已适用的方法。"""
        # 问卷调查法适用于 0401
        result = library.suggest_method_transfer("method_survey", "0401")
        assert result["already_applicable"] is True

    def test_suggest_method_transfer_feasibility_score_range(self, library):
        """可行性分数应在 0-100 范围。"""
        result = library.suggest_method_transfer("method_survey", "0812")
        assert 0 <= result["feasibility_score"] <= 100

    def test_suggest_method_transfer_feasibility_level(self, library):
        """可行性级别应为 high/medium/low。"""
        result = library.suggest_method_transfer("method_experiment", "0812")
        assert result["feasibility_level"] in ("high", "medium", "low")

    def test_suggest_method_transfer_includes_existing_methods(self, library):
        """迁移建议应包含目标学科已有方法。"""
        result = library.suggest_method_transfer("method_survey", "0401")
        assert "existing_methods_in_discipline" in result
        assert isinstance(result["existing_methods_in_discipline"], list)

    def test_suggest_method_transfer_includes_adjustments(self, library):
        """迁移建议应包含调整建议。"""
        result = library.suggest_method_transfer("method_survey", "0812")
        assert len(result["adjustments"]) > 0

    def test_suggest_method_transfer_high_difficulty_challenges(self, library):
        """高难度方法应有更多挑战。"""
        # 实验研究法难度为 4
        result = library.suggest_method_transfer("method_experiment", "0812")
        assert len(result["potential_challenges"]) > 0


# ============================================================
# 第十部分：方法评估测试
# ============================================================


class TestMethodEvaluation:
    """测试方法评估功能。"""

    def test_evaluate_method_basic(self, library):
        """基本方法评估。"""
        result = library.evaluate_method("method_survey")
        assert "method_id" in result
        assert "method_name" in result
        assert "scores" in result
        assert "overall_score" in result
        assert "recommendation" in result
        assert "notes" in result

    def test_evaluate_method_missing(self, library):
        """评估不存在的方法应返回错误。"""
        result = library.evaluate_method("missing")
        assert "error" in result

    def test_evaluate_method_scores_dimensions(self, library):
        """评估应包含所有维度。"""
        result = library.evaluate_method("method_survey")
        scores = result["scores"]
        assert "applicability" in scores
        assert "feasibility" in scores
        assert "rigor" in scores
        assert "efficiency" in scores
        assert "innovation" in scores

    def test_evaluate_method_score_range(self, library):
        """各维度评分应在 0-100 范围。"""
        result = library.evaluate_method("method_survey")
        for dim, score in result["scores"].items():
            assert 0 <= score <= 100

    def test_evaluate_method_overall_score_range(self, library):
        """综合评分应在 0-100 范围。"""
        result = library.evaluate_method("method_survey")
        assert 0 <= result["overall_score"] <= 100

    def test_evaluate_method_recommendation_levels(self, library):
        """推荐等级应为预定义值。"""
        result = library.evaluate_method("method_survey")
        assert result["recommendation"] in (
            "强烈推荐", "推荐", "可考虑", "需谨慎", "不推荐"
        )

    def test_evaluate_method_with_context(self, library):
        """带上下文的方法评估。"""
        context = {
            "discipline": "0401",
            "topic": "用户满意度",
            "time_constraint": "tight",
            "budget": "low",
            "researcher_level": "beginner",
        }
        result = library.evaluate_method("method_survey", context)
        assert "overall_score" in result

    def test_evaluate_method_discipline_match(self, library):
        """学科匹配应提高适用性评分。"""
        # 问卷调查法适用于 0401
        result_match = library.evaluate_method(
            "method_survey", {"discipline": "0401"}
        )
        result_no_match = library.evaluate_method(
            "method_survey", {"discipline": "9999"}
        )
        assert result_match["scores"]["applicability"] >= result_no_match["scores"]["applicability"]

    def test_evaluate_method_time_constraint(self, library):
        """时间约束应影响可行性评分。"""
        # 实验研究法时间成本为"高"
        result_tight = library.evaluate_method(
            "method_experiment", {"time_constraint": "tight"}
        )
        result_relaxed = library.evaluate_method(
            "method_experiment", {"time_constraint": ""}
        )
        assert result_tight["scores"]["feasibility"] <= result_relaxed["scores"]["feasibility"]


# ============================================================
# 第十一部分：智能推荐测试
# ============================================================


class TestSmartRecommendation:
    """测试智能推荐功能。"""

    def test_recommend_for_research_basic(self, library):
        """基本综合推荐。"""
        result = library.recommend_for_research(
            "用户满意度调查", discipline_code="0401"
        )
        assert "topic" in result
        assert "discipline" in result
        assert "single_method_recommendations" in result
        assert "combination_recommendations" in result
        assert "summary" in result

    def test_recommend_for_research_with_constraints(self, library):
        """带约束的综合推荐。"""
        result = library.recommend_for_research(
            "教育研究",
            discipline_code="0401",
            constraints={"time": "tight", "budget": "low", "level": "beginner"},
        )
        assert "constraints" in result
        assert result["constraints"]["time"] == "tight"

    def test_recommend_for_research_no_match(self, library):
        """无匹配的综合推荐。"""
        result = library.recommend_for_research("zzzzzzzzz")
        assert "summary" in result
        assert "未找到" in result["summary"] or len(result["single_method_recommendations"]) == 0

    def test_recommend_for_research_includes_evaluations(self, library):
        """综合推荐应包含方法评估。"""
        result = library.recommend_for_research("问卷调查", discipline_code="0401")
        for rec in result["single_method_recommendations"]:
            assert "evaluation" in rec
            assert "overall_score" in rec["evaluation"]


# ============================================================
# 第十二部分：统计与序列化测试
# ============================================================


class TestMethodLibraryStats:
    """测试 MethodLibrary 统计与序列化。"""

    def test_stats_basic(self, library):
        """基本统计信息。"""
        stats = library.stats()
        assert stats["total_methods"] == len(DEFAULT_METHODS)
        assert "category_distribution" in stats
        assert "difficulty_distribution" in stats
        assert stats["total_disciplines_covered"] > 0
        assert stats["total_keywords"] > 0

    def test_stats_category_distribution(self, library):
        """分类分布应正确。"""
        stats = library.stats()
        dist = stats["category_distribution"]
        assert dist.get(MethodCategory.QUANTITATIVE, 0) > 0
        assert dist.get(MethodCategory.QUALITATIVE, 0) > 0

    def test_stats_difficulty_distribution(self, library):
        """难度分布应正确。"""
        stats = library.stats()
        dist = stats["difficulty_distribution"]
        # 应包含难度 1-5 的方法
        assert sum(dist.values()) == len(DEFAULT_METHODS)

    def test_to_dict(self, library):
        """序列化为字典。"""
        d = library.to_dict()
        assert "methods" in d
        assert len(d["methods"]) == len(DEFAULT_METHODS)

    def test_to_dict_after_modification(self, library):
        """修改后序列化应反映变化。"""
        original_count = len(library.list_all())
        library.add_method(name="新方法", category=MethodCategory.QUANTITATIVE)
        d = library.to_dict()
        assert len(d["methods"]) == original_count + 1


# ============================================================
# 第十三部分：全局单例测试
# ============================================================


class TestGlobalInstance:
    """测试全局单例函数。"""

    def test_get_method_library_singleton(self):
        """get_method_library 应返回单例。"""
        reset_method_library()
        l1 = get_method_library()
        l2 = get_method_library()
        assert l1 is l2

    def test_reset_method_library(self):
        """reset_method_library 应重置单例。"""
        reset_method_library()
        l1 = get_method_library()
        reset_method_library()
        l2 = get_method_library()
        assert l1 is not l2


# ============================================================
# 第十四部分：线程安全测试
# ============================================================


class TestThreadSafety:
    """测试线程安全性。"""

    def test_concurrent_add_method(self, library):
        """并发添加方法不应出错。"""
        errors = []

        def worker(thread_id):
            try:
                for i in range(5):
                    library.add_method(
                        name=f"线程{thread_id}方法{i}",
                        category=MethodCategory.QUANTITATIVE,
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors

    def test_concurrent_read(self, library):
        """并发读取不应出错。"""
        errors = []

        def worker():
            try:
                for _ in range(20):
                    library.list_all()
                    library.list_by_category(MethodCategory.QUANTITATIVE)
                    library.get_by_name("问卷调查法")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors


# ============================================================
# 第十五部分：边界条件测试
# ============================================================


class TestEdgeCases:
    """测试边界条件。"""

    def test_add_method_minimal(self, library):
        """最小参数添加方法。"""
        method_id = library.add_method(
            name="最小方法", category=MethodCategory.QUANTITATIVE
        )
        method = library.get_method(method_id)
        assert method.name == "最小方法"
        assert method.description == ""
        assert method.aliases == []

    def test_add_method_with_special_chars(self, library):
        """含特殊字符的方法名。"""
        method_id = library.add_method(
            name="方法（测试）-v1.0",
            category=MethodCategory.QUANTITATIVE,
        )
        method = library.get_method(method_id)
        assert method.name == "方法（测试）-v1.0"

    def test_update_method_category(self, library):
        """更新方法分类。"""
        method_id = library.add_method(
            name="测试", category=MethodCategory.QUANTITATIVE
        )
        library.update_method(method_id, category=MethodCategory.QUALITATIVE)
        method = library.get_method(method_id)
        assert method.category == MethodCategory.QUALITATIVE

    def test_compare_methods_all_same(self, library):
        """对比相同方法。"""
        result = library.compare_methods(["method_survey", "method_survey"])
        # 应能正常返回（虽然对比相同方法意义不大）
        assert "methods" in result or "error" in result

    def test_evaluate_method_empty_context(self, library):
        """空上下文评估。"""
        result = library.evaluate_method("method_survey", {})
        assert "overall_score" in result

    def test_evaluate_method_none_context(self, library):
        """None 上下文评估。"""
        result = library.evaluate_method("method_survey", None)
        assert "overall_score" in result

    def test_recommend_combination_max_methods_limit(self, library):
        """max_methods 应限制推荐数量。"""
        results = library.recommend_combination(
            "研究方法", max_methods=1
        )
        assert len(results) <= 1

    def test_match_topic_empty_string(self, library):
        """空字符串论题匹配。"""
        results = library.match_topic("")
        assert results == []

    def test_suggest_method_transfer_to_invalid_discipline(self, library):
        """迁移到无效学科代码。"""
        result = library.suggest_method_transfer("method_survey", "invalid_code")
        # 应不抛出异常，返回正常结构
        assert "method" in result or "error" in result

    def test_get_detailed_steps_with_dict_steps(self, library):
        """get_detailed_steps 处理字典格式的步骤。"""
        method = ResearchMethod(
            steps=[{"name": "步骤1", "description": "描述1"}, "步骤2"]
        )
        steps = method.get_detailed_steps()
        assert len(steps) == 2
        assert steps[0].name == "步骤1"
        assert steps[1].name == "步骤2"
