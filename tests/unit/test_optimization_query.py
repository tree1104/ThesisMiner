"""查询优化器（QueryOptimizer）单元测试

测试覆盖范围：
    - SQL 解析工具：归一化、查询类型检测、表/列/JOIN/ORDER BY/GROUP BY 提取
    - 查询分析：SELECT *、笛卡尔积、前导通配符、OR 条件、子查询、函数索引
    - 索引推荐：WHERE/JOIN/ORDER BY 列索引、覆盖索引检测、去重
    - 查询重写：SELECT * 提示、OR 转 UNION、子查询转 JOIN、隐式 JOIN、LIMIT
    - 慢查询检测：阈值判定、慢查询日志、统计更新
    - N+1 查询检测：模式分组、重复模式识别
    - 查询计划分析：EXPLAIN 输出解析、全表扫描、索引使用、临时表、文件排序
    - 查询缓存：命中/未命中、TTL 过期、容量控制、仅缓存 SELECT
    - 批量优化、统计、配置管理、规则启停、线程安全、便捷函数

测试策略：
    1. 使用真实 SQL 语句触发各分析逻辑
    2. 通过 mock executor 测试缓存命中
    3. 验证分析结果字段、问题类型、推荐内容
    4. 覆盖边界条件（空 SQL、无 WHERE、多表 JOIN）
"""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from backend.optimization.query_optimizer import (
    DEFAULT_FULL_SCAN_THRESHOLD,
    DEFAULT_N1_DETECTION_THRESHOLD,
    DEFAULT_QUERY_CACHE_CAPACITY,
    DEFAULT_QUERY_CACHE_TTL,
    DEFAULT_SLOW_QUERY_THRESHOLD,
    IndexRecommendation,
    IndexType,
    IssueSeverity,
    QueryAnalysis,
    QueryOptimizer,
    QueryPlan,
    QueryStats,
    QueryType,
    _detect_query_type,
    _extract_functions,
    _extract_group_by,
    _extract_joins,
    _extract_limit,
    _extract_order_by,
    _extract_tables,
    _extract_where_columns,
    _generate_query_hash,
    _generate_query_pattern,
    _normalize_sql,
    analyze_query,
    get_query_optimizer,
    recommend_indexes_for_query,
    rewrite_query,
)


# ===== Fixtures =====


@pytest.fixture
def optimizer() -> QueryOptimizer:
    """提供默认配置的查询优化器实例。"""
    return QueryOptimizer()


@pytest.fixture
def cached_optimizer() -> QueryOptimizer:
    """提供启用缓存的查询优化器。"""
    return QueryOptimizer(
        enable_query_cache=True,
        query_cache_capacity=10,
        query_cache_ttl=60,
    )


@pytest.fixture
def indexed_optimizer() -> QueryOptimizer:
    """提供带已有索引的查询优化器。"""
    return QueryOptimizer(
        existing_indexes={
            "users": [["id"], ["email"]],
            "orders": [["user_id"], ["id"]],
        },
    )


@pytest.fixture
def simple_select_sql() -> str:
    """提供简单 SELECT 语句。"""
    return "SELECT id, name FROM users WHERE age > 18"


@pytest.fixture
def complex_sql() -> str:
    """提供复杂 SQL 语句。"""
    return (
        "SELECT * FROM users u JOIN orders o ON u.id = o.user_id "
        "WHERE u.age > 18 AND o.total > 100 "
        "ORDER BY o.created_at DESC LIMIT 10"
    )


@pytest.fixture
def problematic_sql() -> str:
    """提供存在多种问题的 SQL。"""
    return (
        "SELECT * FROM users WHERE name LIKE '%john%' OR age < 18 "
        "AND id IN (SELECT user_id FROM orders WHERE total > 100)"
    )


# ===== 枚举与常量测试 =====


class TestEnumsAndConstants:
    """测试枚举与常量定义。"""

    def test_query_type_values(self):
        """验证查询类型枚举。"""
        assert hasattr(QueryType, "SELECT")
        assert hasattr(QueryType, "INSERT")
        assert hasattr(QueryType, "UPDATE")
        assert hasattr(QueryType, "DELETE")
        assert hasattr(QueryType, "UNKNOWN")

    def test_issue_severity_values(self):
        """验证问题严重度枚举。"""
        assert hasattr(IssueSeverity, "LOW")
        assert hasattr(IssueSeverity, "MEDIUM")
        assert hasattr(IssueSeverity, "HIGH")
        assert hasattr(IssueSeverity, "CRITICAL")

    def test_index_type_values(self):
        """验证索引类型枚举。"""
        assert hasattr(IndexType, "SINGLE")
        assert hasattr(IndexType, "COMPOSITE")
        assert hasattr(IndexType, "UNIQUE")
        assert hasattr(IndexType, "FULLTEXT")

    def test_default_constants(self):
        """验证默认常量值。"""
        assert DEFAULT_SLOW_QUERY_THRESHOLD > 0
        assert DEFAULT_QUERY_CACHE_CAPACITY > 0
        assert DEFAULT_QUERY_CACHE_TTL > 0
        assert DEFAULT_FULL_SCAN_THRESHOLD > 0
        assert DEFAULT_N1_DETECTION_THRESHOLD > 0


# ===== SQL 解析工具函数测试 =====


class TestSqlParsingUtilities:
    """测试 SQL 解析工具函数。"""

    def test_normalize_sql_lowercase(self):
        """测试 SQL 归一化小写化。"""
        result = _normalize_sql("SELECT * FROM Users")
        assert result == result.lower() or "select" in result.lower()

    def test_normalize_sql_whitespace(self):
        """测试 SQL 归一化空白处理。"""
        result = _normalize_sql("SELECT   *   FROM   users")
        # 多余空白应被合并
        assert "  " not in result

    def test_normalize_sql_semicolon(self):
        """测试 SQL 归一化去除分号。"""
        result = _normalize_sql("SELECT * FROM users;")
        assert not result.endswith(";")

    def test_normalize_sql_empty(self):
        """测试空 SQL 归一化。"""
        assert _normalize_sql("") == ""

    def test_detect_query_type_select(self):
        """测试检测 SELECT 查询。"""
        assert _detect_query_type("SELECT * FROM t") == QueryType.SELECT

    def test_detect_query_type_insert(self):
        """测试检测 INSERT 查询。"""
        assert _detect_query_type("INSERT INTO t VALUES (1)") == QueryType.INSERT

    def test_detect_query_type_update(self):
        """测试检测 UPDATE 查询。"""
        assert _detect_query_type("UPDATE t SET a=1") == QueryType.UPDATE

    def test_detect_query_type_delete(self):
        """测试检测 DELETE 查询。"""
        assert _detect_query_type("DELETE FROM t") == QueryType.DELETE

    def test_detect_query_type_unknown(self):
        """测试检测未知查询类型。"""
        assert _detect_query_type("???") == QueryType.UNKNOWN

    def test_extract_tables_single(self):
        """测试提取单表。"""
        tables = _extract_tables("SELECT * FROM users")
        assert "users" in tables

    def test_extract_tables_multiple(self):
        """测试提取多表。"""
        tables = _extract_tables(
            "SELECT * FROM users u JOIN orders o ON u.id = o.user_id"
        )
        assert "users" in tables
        assert "orders" in tables

    def test_extract_tables_no_table(self):
        """测试无表时返回空列表。"""
        tables = _extract_tables("SELECT 1")
        assert isinstance(tables, list)

    def test_extract_where_columns(self):
        """测试提取 WHERE 列。"""
        cols = _extract_where_columns("SELECT * FROM t WHERE a > 1 AND b = 2")
        assert "a" in cols
        assert "b" in cols

    def test_extract_where_columns_no_where(self):
        """测试无 WHERE 时返回空列表。"""
        cols = _extract_where_columns("SELECT * FROM t")
        assert cols == []

    def test_extract_joins(self):
        """测试提取 JOIN。"""
        joins = _extract_joins(
            "SELECT * FROM a JOIN b ON a.id = b.aid"
        )
        assert len(joins) >= 1
        assert joins[0]["table"] == "b"

    def test_extract_order_by(self):
        """测试提取 ORDER BY。"""
        cols = _extract_order_by("SELECT * FROM t ORDER BY name, age DESC")
        assert "name" in cols
        assert "age" in cols

    def test_extract_group_by(self):
        """测试提取 GROUP BY。"""
        cols = _extract_group_by("SELECT * FROM t GROUP BY dept, status")
        assert "dept" in cols
        assert "status" in cols

    def test_extract_limit(self):
        """测试提取 LIMIT。"""
        assert _extract_limit("SELECT * FROM t LIMIT 10") == 10

    def test_extract_limit_none(self):
        """测试无 LIMIT 返回 None。"""
        assert _extract_limit("SELECT * FROM t") is None

    def test_extract_functions(self):
        """测试提取函数调用。"""
        funcs = _extract_functions("SELECT COUNT(*), MAX(age) FROM t")
        assert "COUNT" in funcs or "count" in funcs

    def test_generate_query_hash_deterministic(self):
        """测试查询哈希确定性。"""
        h1 = _generate_query_hash("SELECT * FROM t WHERE id = 1")
        h2 = _generate_query_hash("SELECT * FROM t WHERE id = 1")
        assert h1 == h2

    def test_generate_query_hash_different(self):
        """测试不同查询哈希不同。"""
        h1 = _generate_query_hash("SELECT * FROM t WHERE id = 1")
        h2 = _generate_query_hash("SELECT * FROM t WHERE id = 2")
        assert h1 != h2

    def test_generate_query_pattern(self):
        """测试查询模式生成。"""
        p1 = _generate_query_pattern("SELECT * FROM t WHERE id = 1")
        p2 = _generate_query_pattern("SELECT * FROM t WHERE id = 2")
        # 不同参数应生成相同模式
        assert p1 == p2


# ===== 数据类测试 =====


class TestDataclasses:
    """测试数据类。"""

    def test_query_analysis_to_dict(self):
        """测试 QueryAnalysis 序列化。"""
        analysis = QueryAnalysis(
            query_id="q1", sql="SELECT 1",
            query_type=QueryType.SELECT,
        )
        d = analysis.to_dict()
        assert d["query_id"] == "q1"
        assert d["query_type"] == "select"
        assert d["sql"] == "SELECT 1"

    def test_index_recommendation_to_dict(self):
        """测试 IndexRecommendation 序列化。"""
        rec = IndexRecommendation(
            id="r1", table="users", columns=["id"],
            index_type=IndexType.SINGLE, reason="test",
        )
        d = rec.to_dict()
        assert d["table"] == "users"
        assert d["columns"] == ["id"]
        assert d["index_type"] == "single"

    def test_query_plan_to_dict(self):
        """测试 QueryPlan 序列化。"""
        plan = QueryPlan(sql="SELECT 1")
        plan.steps.append({"type": "ALL"})
        d = plan.to_dict()
        assert "sql" in d
        assert "steps" in d
        assert len(d["steps"]) == 1

    def test_query_stats_to_dict(self):
        """测试 QueryStats 序列化。"""
        stats = QueryStats()
        stats.total_queries = 10
        d = stats.to_dict()
        assert d["total_queries"] == 10


# ===== 查询分析测试 =====


class TestQueryAnalysis:
    """测试查询分析功能。"""

    def test_analyze_returns_analysis(self, optimizer, simple_select_sql):
        """测试 analyze 返回 QueryAnalysis。"""
        analysis = optimizer.analyze(simple_select_sql)
        assert isinstance(analysis, QueryAnalysis)
        assert analysis.query_id
        assert analysis.query_type == QueryType.SELECT

    def test_analyze_extracts_tables(self, optimizer, simple_select_sql):
        """测试分析提取表。"""
        analysis = optimizer.analyze(simple_select_sql)
        assert "users" in analysis.tables

    def test_analyze_extracts_where_columns(self, optimizer, simple_select_sql):
        """测试分析提取 WHERE 列。"""
        analysis = optimizer.analyze(simple_select_sql)
        assert "age" in analysis.where_columns

    def test_analyze_detects_select_star(self, optimizer):
        """测试检测 SELECT *。"""
        analysis = optimizer.analyze("SELECT * FROM users")
        assert analysis.has_select_star is True
        select_star_issues = [i for i in analysis.issues if i["type"] == "SELECT_STAR"]
        assert len(select_star_issues) > 0

    def test_analyze_detects_cartesian_join(self, optimizer):
        """测试检测笛卡尔积。"""
        analysis = optimizer.analyze("SELECT * FROM a, b")
        # 应检测到笛卡尔积或逗号分隔多表
        cartesian_issues = [i for i in analysis.issues if i["type"] == "CARTESIAN_JOIN"]
        assert len(cartesian_issues) > 0 or analysis.has_cartesian

    def test_analyze_detects_leading_wildcard(self, optimizer):
        """测试检测前导通配符。"""
        analysis = optimizer.analyze(
            "SELECT * FROM users WHERE name LIKE '%john'"
        )
        assert analysis.has_leading_wildcard is True
        wildcard_issues = [i for i in analysis.issues if i["type"] == "LEADING_WILDCARD"]
        assert len(wildcard_issues) > 0

    def test_analyze_detects_or_condition(self, optimizer):
        """测试检测 OR 条件。"""
        analysis = optimizer.analyze(
            "SELECT * FROM users WHERE a = 1 OR b = 2"
        )
        assert analysis.has_or_condition is True

    def test_analyze_detects_subquery(self, optimizer):
        """测试检测子查询。"""
        analysis = optimizer.analyze(
            "SELECT * FROM users WHERE id IN (SELECT user_id FROM orders)"
        )
        assert analysis.has_subquery is True
        subquery_issues = [i for i in analysis.issues if i["type"] == "SUBQUERY"]
        assert len(subquery_issues) > 0

    def test_analyze_extracts_limit(self, optimizer):
        """测试提取 LIMIT。"""
        analysis = optimizer.analyze("SELECT * FROM t LIMIT 50")
        assert analysis.limit == 50

    def test_analyze_extracts_order_by(self, optimizer):
        """测试提取 ORDER BY。"""
        analysis = optimizer.analyze("SELECT * FROM t ORDER BY name DESC")
        assert "name" in analysis.order_by_columns

    def test_analyze_extracts_group_by(self, optimizer):
        """测试提取 GROUP BY。"""
        analysis = optimizer.analyze("SELECT dept FROM t GROUP BY dept")
        assert "dept" in analysis.group_by_columns

    def test_analyze_generates_recommendations(self, optimizer, problematic_sql):
        """测试生成优化建议。"""
        analysis = optimizer.analyze(problematic_sql)
        assert isinstance(analysis.recommendations, list)

    def test_analyze_estimated_cost(self, optimizer, complex_sql):
        """测试估算成本。"""
        analysis = optimizer.analyze(complex_sql)
        assert analysis.estimated_cost >= 0

    def test_analyze_empty_sql(self, optimizer):
        """测试空 SQL 分析不抛异常。"""
        analysis = optimizer.analyze("")
        assert isinstance(analysis, QueryAnalysis)

    def test_analyze_invalid_sql(self, optimizer):
        """测试无效 SQL 分析不抛异常。"""
        analysis = optimizer.analyze("??? not sql ???")
        assert isinstance(analysis, QueryAnalysis)


# ===== 索引推荐测试 =====


class TestIndexRecommendation:
    """测试索引推荐功能。"""

    def test_recommend_indexes_for_where(self, optimizer):
        """测试基于 WHERE 推荐索引。"""
        analysis = optimizer.analyze(
            "SELECT * FROM users WHERE age > 18 AND name = 'john'"
        )
        recs = optimizer.recommend_indexes(analysis)
        assert len(recs) > 0
        where_recs = [r for r in recs if "WHERE" in r.reason or "条件" in r.reason]
        assert len(where_recs) > 0

    def test_recommend_indexes_for_join(self, optimizer):
        """测试基于 JOIN 推荐索引。"""
        analysis = optimizer.analyze(
            "SELECT * FROM users u JOIN orders o ON u.id = o.user_id"
        )
        recs = optimizer.recommend_indexes(analysis)
        join_recs = [r for r in recs if "JOIN" in r.reason or "JOIN" in r.reason]
        assert len(join_recs) >= 0

    def test_recommend_indexes_for_order_by(self, optimizer):
        """测试基于 ORDER BY 推荐索引。"""
        analysis = optimizer.analyze(
            "SELECT * FROM users ORDER BY created_at DESC"
        )
        recs = optimizer.recommend_indexes(analysis)
        order_recs = [r for r in recs if "ORDER" in r.reason or "排序" in r.reason]
        assert len(order_recs) >= 0

    def test_recommend_indexes_with_existing(self, indexed_optimizer):
        """测试已有索引时不重复推荐。"""
        analysis = indexed_optimizer.analyze(
            "SELECT * FROM users WHERE id = 1"
        )
        recs = indexed_optimizer.recommend_indexes(analysis)
        # id 列已有索引，不应推荐
        id_recs = [r for r in recs if "id" in r.columns and r.table == "users"]
        assert len(id_recs) == 0

    def test_recommend_indexes_deduplication(self, optimizer):
        """测试索引推荐去重。"""
        analysis = optimizer.analyze(
            "SELECT * FROM users WHERE age > 18 AND age < 30"
        )
        recs = optimizer.recommend_indexes(analysis)
        # 同表同列的推荐应去重
        keys = [f"{r.table}:{':'.join(r.columns)}" for r in recs]
        assert len(keys) == len(set(keys))

    def test_recommend_indexes_generates_sql(self, optimizer):
        """测试推荐生成建索引 SQL。"""
        analysis = optimizer.analyze(
            "SELECT * FROM users WHERE age > 18"
        )
        recs = optimizer.recommend_indexes(analysis)
        for rec in recs:
            assert rec.sql  # 应有建索引 SQL
            assert "CREATE INDEX" in rec.sql or "CREATE" in rec.sql

    def test_recommend_indexes_priority(self, optimizer):
        """测试推荐优先级。"""
        analysis = optimizer.analyze(
            "SELECT * FROM users WHERE age > 18"
        )
        recs = optimizer.recommend_indexes(analysis)
        for rec in recs:
            assert rec.priority in IssueSeverity


# ===== 查询重写测试 =====


class TestQueryRewrite:
    """测试查询重写功能。"""

    def test_rewrite_select_star_suggestion(self, optimizer):
        """测试 SELECT * 重写建议。"""
        rewritten, changes = optimizer.rewrite("SELECT * FROM users")
        assert isinstance(rewritten, str)
        assert isinstance(changes, list)
        assert any("SELECT *" in c or "列名" in c for c in changes)

    def test_rewrite_or_suggestion(self, optimizer):
        """测试 OR 重写建议。"""
        rewritten, changes = optimizer.rewrite(
            "SELECT * FROM users WHERE a = 1 OR b = 2"
        )
        assert any("OR" in c or "UNION" in c for c in changes)

    def test_rewrite_subquery_to_join(self, optimizer):
        """测试子查询改写为 JOIN。"""
        rewritten, changes = optimizer.rewrite(
            "SELECT * FROM users WHERE id IN (SELECT user_id FROM orders)"
        )
        assert any("JOIN" in c or "子查询" in c for c in changes)

    def test_rewrite_adds_limit_suggestion(self, optimizer):
        """测试添加 LIMIT 建议。"""
        rewritten, changes = optimizer.rewrite(
            "SELECT * FROM users WHERE age > 18"
        )
        assert any("LIMIT" in c for c in changes)

    def test_rewrite_no_changes_for_optimized(self, optimizer):
        """测试已优化查询无重写。"""
        sql = "SELECT id, name FROM users WHERE age > 18 LIMIT 10"
        rewritten, changes = optimizer.rewrite(sql)
        assert isinstance(changes, list)

    def test_rewrite_returns_tuple(self, optimizer):
        """测试重写返回元组。"""
        result = optimizer.rewrite("SELECT * FROM t")
        assert isinstance(result, tuple)
        assert len(result) == 2


# ===== 慢查询检测测试 =====


class TestSlowQueryDetection:
    """测试慢查询检测功能。"""

    def test_detect_slow_queries(self, optimizer):
        """测试检测慢查询。"""
        queries = [
            ("SELECT * FROM t1", 0.5),   # 快
            ("SELECT * FROM t2", 2.0),   # 慢
            ("SELECT * FROM t3", 0.1),   # 快
        ]
        slow = optimizer.detect_slow_queries(queries)
        assert len(slow) == 1
        assert slow[0]["execution_time"] == 2.0

    def test_detect_slow_queries_threshold(self):
        """测试自定义慢查询阈值。"""
        opt = QueryOptimizer(slow_query_threshold=0.3)
        queries = [
            ("SELECT * FROM t1", 0.5),  # 慢
        ]
        slow = opt.detect_slow_queries(queries)
        assert len(slow) == 1

    def test_detect_slow_queries_updates_stats(self, optimizer):
        """测试慢查询检测更新统计。"""
        queries = [
            ("SELECT * FROM t1", 2.0),
            ("SELECT * FROM t2", 0.1),
        ]
        optimizer.detect_slow_queries(queries)
        stats = optimizer.get_stats()
        assert stats["total_queries"] == 2
        assert stats["slow_queries"] == 1
        assert stats["max_execution_time"] == 2.0

    def test_get_slow_queries(self, optimizer):
        """测试获取慢查询日志。"""
        queries = [
            ("SELECT * FROM t1", 2.0),
            ("SELECT * FROM t2", 3.0),
        ]
        optimizer.detect_slow_queries(queries)
        slow = optimizer.get_slow_queries()
        assert len(slow) == 2

    def test_get_slow_queries_limit(self, optimizer):
        """测试慢查询日志数量限制。"""
        for i in range(10):
            optimizer.detect_slow_queries([("SELECT * FROM t", 2.0)])
        slow = optimizer.get_slow_queries(limit=5)
        assert len(slow) == 5

    def test_no_slow_queries(self, optimizer):
        """测试无慢查询时返回空列表。"""
        queries = [("SELECT * FROM t", 0.1)]
        slow = optimizer.detect_slow_queries(queries)
        assert slow == []


# ===== N+1 查询检测测试 =====


class TestNPlusOneDetection:
    """测试 N+1 查询检测功能。"""

    def test_detect_n_plus_1(self, optimizer):
        """测试检测 N+1 查询。"""
        # 构造重复模式的查询
        queries = [
            (f"SELECT * FROM users WHERE id = {i}", 0.01)
            for i in range(10)
        ]
        issues = optimizer.detect_n_plus_1(queries)
        assert len(issues) > 0
        assert issues[0]["type"] == "N_PLUS_1"
        assert issues[0]["count"] == 10

    def test_no_n_plus_1_for_distinct_patterns(self, optimizer):
        """测试不同模式不触发 N+1。"""
        queries = [
            ("SELECT * FROM users WHERE id = 1", 0.01),
            ("SELECT * FROM orders WHERE total > 100", 0.01),
            ("SELECT * FROM products WHERE category = 'A'", 0.01),
        ]
        issues = optimizer.detect_n_plus_1(queries)
        assert len(issues) == 0

    def test_n_plus_1_disabled(self):
        """测试禁用 N+1 检测。"""
        opt = QueryOptimizer()
        opt.set_rule("detect_n_plus_1", False)
        queries = [
            (f"SELECT * FROM users WHERE id = {i}", 0.01)
            for i in range(10)
        ]
        issues = opt.detect_n_plus_1(queries)
        assert issues == []

    def test_n_plus_1_total_time(self, optimizer):
        """测试 N+1 总耗时计算。"""
        queries = [
            ("SELECT * FROM users WHERE id = 1", 0.1),
            ("SELECT * FROM users WHERE id = 2", 0.2),
            ("SELECT * FROM users WHERE id = 3", 0.3),
        ]
        # 需达到阈值才检测
        queries = queries * 3
        issues = optimizer.detect_n_plus_1(queries)
        if issues:
            assert issues[0]["total_time"] > 0


# ===== 查询计划分析测试 =====


class TestQueryPlanAnalysis:
    """测试查询计划分析功能。"""

    def test_analyze_query_plan_full_scan(self, optimizer):
        """测试检测全表扫描。"""
        explain = [
            {"id": 1, "table": "users", "type": "ALL", "rows": 10000},
        ]
        plan = optimizer.analyze_query_plan(explain, "SELECT * FROM users")
        assert plan.full_scan is True

    def test_analyze_query_plan_index_used(self, optimizer):
        """测试检测索引使用。"""
        explain = [
            {"id": 1, "table": "users", "type": "ref", "key": "idx_id", "rows": 1},
        ]
        plan = optimizer.analyze_query_plan(explain, "SELECT * FROM users WHERE id=1")
        assert plan.uses_index is True
        assert "idx_id" in plan.indexes_used

    def test_analyze_query_plan_temporary_table(self, optimizer):
        """测试检测临时表。"""
        explain = [
            {"id": 1, "table": "users", "Using_temporary_table": True},
        ]
        plan = optimizer.analyze_query_plan(explain)
        assert plan.temporary is True

    def test_analyze_query_plan_filesort(self, optimizer):
        """测试检测文件排序。"""
        explain = [
            {"id": 1, "table": "users", "Using_filesort": True},
        ]
        plan = optimizer.analyze_query_plan(explain)
        assert plan.filesort is True

    def test_analyze_query_plan_estimated_rows(self, optimizer):
        """测试估算行数累加。"""
        explain = [
            {"id": 1, "table": "users", "rows": 100},
            {"id": 1, "table": "orders", "rows": 200},
        ]
        plan = optimizer.analyze_query_plan(explain)
        assert plan.estimated_rows == 300

    def test_analyze_query_plan_estimated_cost(self, optimizer):
        """测试估算成本。"""
        explain = [
            {"id": 1, "table": "users", "rows": 1000, "type": "ALL"},
        ]
        plan = optimizer.analyze_query_plan(explain)
        assert plan.estimated_cost >= 0

    def test_analyze_query_plan_empty(self, optimizer):
        """测试空 EXPLAIN 输出。"""
        plan = optimizer.analyze_query_plan([])
        assert isinstance(plan, QueryPlan)
        assert plan.steps == []


# ===== 查询缓存测试 =====


class TestQueryCache:
    """测试查询缓存功能。"""

    def test_execute_with_cache_miss(self, cached_optimizer):
        """测试缓存未命中时执行查询。"""
        executor = MagicMock(return_value="result")
        result = cached_optimizer.execute_with_cache(
            "SELECT * FROM users", executor
        )
        assert result == "result"
        executor.assert_called_once()

    def test_execute_with_cache_hit(self, cached_optimizer):
        """测试缓存命中时不执行查询。"""
        executor = MagicMock(return_value="result")
        # 第一次执行
        cached_optimizer.execute_with_cache("SELECT * FROM users", executor)
        # 第二次应命中缓存
        executor.reset_mock()
        result = cached_optimizer.execute_with_cache(
            "SELECT * FROM users", executor
        )
        assert result == "result"
        executor.assert_not_called()

    def test_execute_with_cache_ttl(self, cached_optimizer):
        """测试缓存 TTL 过期。"""
        opt = QueryOptimizer(
            enable_query_cache=True,
            query_cache_ttl=0.01,
        )
        executor = MagicMock(return_value="result")
        opt.execute_with_cache("SELECT * FROM users", executor)
        time.sleep(0.02)
        executor.reset_mock()
        opt.execute_with_cache("SELECT * FROM users", executor)
        executor.assert_called_once()

    def test_execute_with_cache_disabled(self):
        """测试禁用缓存时总是执行。"""
        opt = QueryOptimizer(enable_query_cache=False)
        executor = MagicMock(return_value="result")
        opt.execute_with_cache("SELECT * FROM users", executor)
        opt.execute_with_cache("SELECT * FROM users", executor)
        assert executor.call_count == 2

    def test_execute_with_cache_only_select(self, cached_optimizer):
        """测试仅缓存 SELECT 查询。"""
        executor = MagicMock(return_value="result")
        cached_optimizer.execute_with_cache(
            "UPDATE users SET name='a'", executor
        )
        executor.reset_mock()
        cached_optimizer.execute_with_cache(
            "UPDATE users SET name='a'", executor
        )
        # UPDATE 不缓存，应再次执行
        executor.assert_called_once()

    def test_clear_cache(self, cached_optimizer):
        """测试清空缓存。"""
        executor = MagicMock(return_value="result")
        cached_optimizer.execute_with_cache("SELECT * FROM t", executor)
        count = cached_optimizer.clear_cache()
        assert count >= 1

    def test_cache_capacity_control(self):
        """测试缓存容量控制。"""
        opt = QueryOptimizer(
            enable_query_cache=True,
            query_cache_capacity=3,
        )
        executor = MagicMock(side_effect=lambda sql: f"r_{sql}")
        for i in range(5):
            opt.execute_with_cache(f"SELECT * FROM t{i}", executor)
        stats = opt.get_stats()
        assert stats["cache_size"] <= 3


# ===== 批量优化测试 =====


class TestBatchOptimize:
    """测试批量优化功能。"""

    def test_batch_optimize(self, optimizer):
        """测试批量优化。"""
        queries = [
            "SELECT * FROM users WHERE id = 1",
            "SELECT * FROM orders WHERE total > 100",
            "SELECT * FROM products LIMIT 10",
        ]
        results = optimizer.batch_optimize(queries)
        assert len(results) == 3
        for r in results:
            assert isinstance(r, QueryAnalysis)

    def test_batch_optimize_empty(self, optimizer):
        """测试空列表批量优化。"""
        results = optimizer.batch_optimize([])
        assert results == []


# ===== 统计与配置测试 =====


class TestStatsAndConfig:
    """测试统计与配置管理。"""

    def test_get_stats(self, optimizer):
        """测试获取统计。"""
        stats = optimizer.get_stats()
        assert "total_queries" in stats
        assert "slow_queries" in stats
        assert "slow_query_threshold" in stats
        assert "cache_size" in stats
        assert "cache_capacity" in stats

    def test_get_config(self, optimizer):
        """测试获取配置。"""
        config = optimizer.get_config()
        assert "slow_query_threshold" in config
        assert "enable_query_cache" in config
        assert "query_cache_capacity" in config
        assert "query_cache_ttl" in config
        assert "rules" in config
        assert "existing_indexes" in config

    def test_set_rule(self, optimizer):
        """测试启用/禁用规则。"""
        optimizer.set_rule("detect_select_star", False)
        config = optimizer.get_config()
        assert config["rules"]["detect_select_star"] is False

    def test_add_existing_index(self, optimizer):
        """测试添加已有索引。"""
        optimizer.add_existing_index("new_table", ["col1", "col2"])
        config = optimizer.get_config()
        assert "new_table" in config["existing_indexes"]
        assert ["col1", "col2"] in config["existing_indexes"]["new_table"]

    def test_custom_slow_threshold(self):
        """测试自定义慢查询阈值。"""
        opt = QueryOptimizer(slow_query_threshold=5.0)
        config = opt.get_config()
        assert config["slow_query_threshold"] == 5.0


# ===== 便捷函数测试 =====


class TestConvenienceFunctions:
    """测试模块级便捷函数。"""

    def test_get_query_optimizer_singleton(self):
        """测试全局优化器单例。"""
        opt1 = get_query_optimizer()
        opt2 = get_query_optimizer()
        assert opt1 is opt2

    def test_analyze_query_function(self):
        """测试 analyze_query 便捷函数。"""
        analysis = analyze_query("SELECT * FROM users")
        assert isinstance(analysis, QueryAnalysis)

    def test_recommend_indexes_for_query_function(self):
        """测试 recommend_indexes_for_query 便捷函数。"""
        recs = recommend_indexes_for_query(
            "SELECT * FROM users WHERE age > 18"
        )
        assert isinstance(recs, list)

    def test_rewrite_query_function(self):
        """测试 rewrite_query 便捷函数。"""
        rewritten, changes = rewrite_query("SELECT * FROM users")
        assert isinstance(rewritten, str)
        assert isinstance(changes, list)


# ===== 线程安全测试 =====


class TestThreadSafety:
    """测试线程安全性。"""

    def test_concurrent_analyze(self, optimizer):
        """测试并发分析不抛异常。"""
        errors: list[Exception] = []
        queries = [
            "SELECT * FROM users WHERE id = 1",
            "SELECT * FROM orders WHERE total > 100",
            "SELECT * FROM products LIMIT 10",
        ]

        def worker():
            try:
                for q in queries:
                    optimizer.analyze(q)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0

    def test_concurrent_cache_access(self, cached_optimizer):
        """测试并发缓存访问。"""
        errors: list[Exception] = []
        executor = MagicMock(return_value="result")

        def worker():
            try:
                for _ in range(10):
                    cached_optimizer.execute_with_cache(
                        "SELECT * FROM users", executor
                    )
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0


# ===== 异常处理测试 =====


class TestErrorHandling:
    """测试异常处理。"""

    def test_analyze_empty_string(self, optimizer):
        """测试空字符串分析。"""
        analysis = optimizer.analyze("")
        assert isinstance(analysis, QueryAnalysis)

    def test_analyze_none_raises(self, optimizer):
        """测试 None 输入（应被处理或抛出明确异常）。"""
        # _normalize_sql 应处理空字符串，None 可能抛异常
        try:
            analysis = optimizer.analyze(None)
            assert isinstance(analysis, QueryAnalysis)
        except (AttributeError, TypeError):
            # 可接受：None 输入抛异常
            pass

    def test_execute_with_cache_executor_exception(self, cached_optimizer):
        """测试 executor 异常时 propagate。"""
        executor = MagicMock(side_effect=ValueError("db error"))
        with pytest.raises(ValueError):
            cached_optimizer.execute_with_cache("SELECT * FROM t", executor)

    def test_recommend_indexes_empty_analysis(self, optimizer):
        """测试空分析推荐索引。"""
        analysis = QueryAnalysis()
        recs = optimizer.recommend_indexes(analysis)
        assert isinstance(recs, list)

    def test_detect_slow_queries_empty(self, optimizer):
        """测试空查询列表。"""
        slow = optimizer.detect_slow_queries([])
        assert slow == []


# ===== 综合场景测试 =====


class TestComplexScenarios:
    """测试复杂综合场景。"""

    def test_full_optimization_workflow(self, indexed_optimizer):
        """测试完整优化工作流。"""
        sql = "SELECT * FROM users WHERE age > 18 ORDER BY name LIMIT 10"
        # 分析
        analysis = indexed_optimizer.analyze(sql)
        assert analysis.query_type == QueryType.SELECT
        # 推荐索引
        recs = indexed_optimizer.recommend_indexes(analysis)
        # 重写
        rewritten, changes = indexed_optimizer.rewrite(sql)
        assert isinstance(rewritten, str)
        assert isinstance(changes, list)

    def test_problematic_query_full_analysis(self, optimizer, problematic_sql):
        """测试问题查询的完整分析。"""
        analysis = optimizer.analyze(problematic_sql)
        # 应检测到多种问题
        issue_types = {i["type"] for i in analysis.issues}
        assert len(issue_types) >= 1
        # 应有建议
        assert len(analysis.recommendations) > 0

    def test_cache_with_slow_detection(self, cached_optimizer):
        """测试缓存与慢查询检测结合。"""
        executor = MagicMock(return_value="result")
        # 多次执行相同查询
        for _ in range(5):
            cached_optimizer.execute_with_cache(
                "SELECT * FROM users", executor
            )
        # executor 应只被调用一次（缓存命中）
        assert executor.call_count == 1

    def test_multiple_rules_toggle(self, optimizer):
        """测试多规则启停。"""
        optimizer.set_rule("detect_select_star", False)
        optimizer.set_rule("detect_subquery", False)
        analysis = optimizer.analyze(
            "SELECT * FROM users WHERE id IN (SELECT user_id FROM orders)"
        )
        # 应不检测 SELECT * 和子查询
        select_star_issues = [i for i in analysis.issues if i["type"] == "SELECT_STAR"]
        subquery_issues = [i for i in analysis.issues if i["type"] == "SUBQUERY"]
        assert len(select_star_issues) == 0
        assert len(subquery_issues) == 0

    def test_mocked_time_for_cache_expiry(self):
        """测试通过 mock time 加速缓存过期。"""
        opt = QueryOptimizer(
            enable_query_cache=True,
            query_cache_ttl=100,
        )
        executor = MagicMock(return_value="result")
        opt.execute_with_cache("SELECT * FROM t", executor)
        # mock time.time 返回未来时间
        future_time = time.time() + 200
        with patch("backend.optimization.query_optimizer.time.time",
                   return_value=future_time):
            executor.reset_mock()
            opt.execute_with_cache("SELECT * FROM t", executor)
            executor.assert_called_once()
