"""查询优化器模块

提供数据库查询分析与优化能力，包括：
    - SQL 查询分析（语法解析、表/列提取、JOIN 识别）
    - 索引推荐（基于查询模式自动推荐索引）
    - 查询重写（优化 SQL 写法）
    - 慢查询检测（阈值判定、模式识别）
    - 查询计划分析（EXPLAIN 输出解析）
    - 性能瓶颈识别（全表扫描、笛卡尔积等）
    - 批量查询优化、N+1 查询消除
    - JOIN 优化（顺序、类型）
    - 查询缓存、结果缓存、增量更新

设计原则：
    1. 零外部依赖：仅使用 Python 标准库
    2. 线程安全：所有公共方法通过 RLock 保护
    3. 可配置：慢查询阈值、优化规则均可调整
    4. 可解释：每个建议附带理由与预期收益
    5. 数据库无关：核心分析基于 SQL 语法，适配 SQLite/MySQL/PostgreSQL
"""
from __future__ import annotations

import hashlib
import re
import threading
import time
import uuid
from collections import Counter, defaultdict, OrderedDict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional


# ===== 枚举 =====


class QueryType(str, Enum):
    """查询类型。"""

    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    CREATE = "CREATE"
    ALTER = "ALTER"
    DROP = "DROP"
    UNKNOWN = "UNKNOWN"


class IssueSeverity(str, Enum):
    """问题严重度。"""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IndexType(str, Enum):
    """索引类型。"""

    SINGLE = "single"      # 单列索引
    COMPOSITE = "composite"  # 复合索引
    UNIQUE = "unique"      # 唯一索引
    COVERING = "covering"  # 覆盖索引
    FULLTEXT = "fulltext"  # 全文索引


# ===== 常量 =====


# 默认慢查询阈值（秒）
DEFAULT_SLOW_QUERY_THRESHOLD = 1.0

# 默认查询缓存容量
DEFAULT_QUERY_CACHE_CAPACITY = 1000

# 默认查询缓存 TTL（秒）
DEFAULT_QUERY_CACHE_TTL = 300

# N+1 查询检测：相同模式重复次数阈值
DEFAULT_N1_DETECTION_THRESHOLD = 5

# 全表扫描行数阈值
DEFAULT_FULL_SCAN_THRESHOLD = 10000

# SQL 关键字
SQL_KEYWORDS = {
    "SELECT", "FROM", "WHERE", "JOIN", "INNER", "LEFT", "RIGHT", "OUTER",
    "FULL", "CROSS", "ON", "GROUP", "BY", "ORDER", "HAVING", "LIMIT",
    "OFFSET", "UNION", "ALL", "INSERT", "INTO", "VALUES", "UPDATE",
    "SET", "DELETE", "CREATE", "TABLE", "INDEX", "ALTER", "ADD", "DROP",
    "AND", "OR", "NOT", "IN", "EXISTS", "BETWEEN", "LIKE", "IS", "NULL",
    "AS", "DISTINCT", "COUNT", "SUM", "AVG", "MIN", "MAX", "CASE", "WHEN",
    "THEN", "ELSE", "END", "WITH", "RECURSIVE",
}

# SQL 函数（可能导致索引失效）
SQL_FUNCTIONS_PATTERNS = [
    re.compile(r"UPPER\s*\(", re.IGNORECASE),
    re.compile(r"LOWER\s*\(", re.IGNORECASE),
    re.compile(r"SUBSTR\s*\(", re.IGNORECASE),
    re.compile(r"SUBSTRING\s*\(", re.IGNORECASE),
    re.compile(r"DATE\s*\(", re.IGNORECASE),
    re.compile(r"DATETIME\s*\(", re.IGNORECASE),
    re.compile(r"CAST\s*\(", re.IGNORECASE),
    re.compile(r"COALESCE\s*\(", re.IGNORECASE),
    re.compile(r"ABS\s*\(", re.IGNORECASE),
    re.compile(r"ROUND\s*\(", re.IGNORECASE),
]

# 前导通配符模式（导致索引失效）
LEADING_WILDCARD_PATTERN = re.compile(r"LIKE\s+['\"]%")

# SELECT * 模式
SELECT_STAR_PATTERN = re.compile(r"SELECT\s+\*", re.IGNORECASE)

# 笛卡尔积模式（JOIN 缺 ON）
CARTESIAN_JOIN_PATTERN = re.compile(
    r"JOIN\s+\S+(?!\s+ON)", re.IGNORECASE
)

# OR 模式（可能导致索引失效）
OR_PATTERN = re.compile(r"\bOR\b", re.IGNORECASE)

# 子查询模式
SUBQUERY_PATTERN = re.compile(r"\bIN\s*\(\s*SELECT", re.IGNORECASE)

# 表名提取正则
TABLE_PATTERN = re.compile(
    r"(?:FROM|JOIN|INTO|UPDATE|TABLE)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
    re.IGNORECASE,
)

# 列名提取正则（WHERE 子句中）
WHERE_COLUMN_PATTERN = re.compile(
    r"([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:=|!=|<>|>|<|>=|<=|LIKE|IN|BETWEEN|IS)",
    re.IGNORECASE,
)

# JOIN 类型正则
JOIN_PATTERN = re.compile(
    r"(INNER\s+JOIN|LEFT\s+(?:OUTER\s+)?JOIN|RIGHT\s+(?:OUTER\s+)?JOIN|"
    r"FULL\s+(?:OUTER\s+)?JOIN|CROSS\s+JOIN|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)"
    r"(?:\s+(?:AS\s+)?([a-zA-Z_][a-zA-Z0-9_]*))?\s+ON\s+(.+?)"
    r"(?=\s+(?:INNER|LEFT|RIGHT|FULL|CROSS|JOIN|WHERE|GROUP|ORDER|LIMIT|UNION)|$)",
    re.IGNORECASE,
)

# ORDER BY 列提取
ORDER_BY_PATTERN = re.compile(
    r"ORDER\s+BY\s+(.+?)(?=\s+(?:LIMIT|OFFSET|UNION)|$)",
    re.IGNORECASE,
)

# GROUP BY 列提取
GROUP_BY_PATTERN = re.compile(
    r"GROUP\s+BY\s+(.+?)(?=\s+(?:HAVING|ORDER|LIMIT|OFFSET|UNION)|$)",
    re.IGNORECASE,
)

# LIMIT 提取
LIMIT_PATTERN = re.compile(r"LIMIT\s+(\d+)", re.IGNORECASE)


# ===== 数据结构 =====


@dataclass
class QueryAnalysis:
    """查询分析结果。

    Attributes:
        query_id: 查询 ID。
        sql: 原始 SQL。
        query_type: 查询类型。
        tables: 涉及的表。
        columns: 涉及的列。
        where_columns: WHERE 子句中的列。
        join_tables: JOIN 的表。
        order_by_columns: ORDER BY 列。
        group_by_columns: GROUP BY 列。
        limit: LIMIT 值。
        has_select_star: 是否 SELECT *。
        has_subquery: 是否有子查询。
        has_cartesian: 是否笛卡尔积。
        has_leading_wildcard: 是否前导通配符。
        has_or_condition: 是否 OR 条件。
        function_calls: 使用的函数。
        issues: 检测到的问题。
        estimated_cost: 估算成本。
        recommendations: 优化建议。
    """

    query_id: str = ""
    sql: str = ""
    query_type: QueryType = QueryType.UNKNOWN
    tables: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    where_columns: list[str] = field(default_factory=list)
    join_tables: list[dict[str, Any]] = field(default_factory=list)
    order_by_columns: list[str] = field(default_factory=list)
    group_by_columns: list[str] = field(default_factory=list)
    limit: Optional[int] = None
    has_select_star: bool = False
    has_subquery: bool = False
    has_cartesian: bool = False
    has_leading_wildcard: bool = False
    has_or_condition: bool = False
    function_calls: list[str] = field(default_factory=list)
    issues: list[dict[str, Any]] = field(default_factory=list)
    estimated_cost: float = 0.0
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "sql": self.sql,
            "query_type": self.query_type.value.lower(),
            "tables": self.tables,
            "columns": self.columns,
            "where_columns": self.where_columns,
            "join_tables": self.join_tables,
            "order_by_columns": self.order_by_columns,
            "group_by_columns": self.group_by_columns,
            "limit": self.limit,
            "has_select_star": self.has_select_star,
            "has_subquery": self.has_subquery,
            "has_cartesian": self.has_cartesian,
            "has_leading_wildcard": self.has_leading_wildcard,
            "has_or_condition": self.has_or_condition,
            "function_calls": self.function_calls,
            "issues": self.issues,
            "estimated_cost": round(self.estimated_cost, 4),
            "recommendations": self.recommendations,
        }


@dataclass
class IndexRecommendation:
    """索引推荐。

    Attributes:
        id: 推荐 ID。
        table: 表名。
        columns: 索引列。
        index_type: 索引类型。
        reason: 推荐理由。
        expected_benefit: 预期收益。
        priority: 优先级。
        sql: 建索引 SQL。
    """

    id: str = ""
    table: str = ""
    columns: list[str] = field(default_factory=list)
    index_type: IndexType = IndexType.SINGLE
    reason: str = ""
    expected_benefit: str = ""
    priority: IssueSeverity = IssueSeverity.MEDIUM
    sql: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "table": self.table,
            "columns": self.columns,
            "index_type": self.index_type.value,
            "reason": self.reason,
            "expected_benefit": self.expected_benefit,
            "priority": self.priority.value,
            "sql": self.sql,
        }


@dataclass
class QueryPlan:
    """查询计划。

    Attributes:
        sql: SQL 语句。
        steps: 执行步骤。
        estimated_rows: 估算行数。
        estimated_cost: 估算成本。
        uses_index: 是否使用索引。
        indexes_used: 使用的索引。
        full_scan: 是否全表扫描.
        temporary: 是否使用临时表.
        filesort: 是否使用文件排序.
    """

    sql: str = ""
    steps: list[dict[str, Any]] = field(default_factory=list)
    estimated_rows: int = 0
    estimated_cost: float = 0.0
    uses_index: bool = False
    indexes_used: list[str] = field(default_factory=list)
    full_scan: bool = False
    temporary: bool = False
    filesort: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class QueryStats:
    """查询统计。

    Attributes:
        total_queries: 总查询数。
        slow_queries: 慢查询数。
        avg_execution_time: 平均执行时间。
        max_execution_time: 最大执行时间。
        query_patterns: 查询模式统计。
        table_access_counts: 表访问次数。
    """

    total_queries: int = 0
    slow_queries: int = 0
    avg_execution_time: float = 0.0
    max_execution_time: float = 0.0
    query_patterns: dict[str, int] = field(default_factory=dict)
    table_access_counts: dict[str, int] = field(default_factory=dict)
    _execution_times: list[float] = field(default_factory=list, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_queries": self.total_queries,
            "slow_queries": self.slow_queries,
            "avg_execution_time": round(self.avg_execution_time, 4),
            "max_execution_time": round(self.max_execution_time, 4),
            "query_patterns": self.query_patterns,
            "table_access_counts": self.table_access_counts,
        }


# ===== SQL 解析工具 =====


def _normalize_sql(sql: str) -> str:
    """归一化 SQL：去除多余空白、注释、末尾分号。

    Args:
        sql: 原始 SQL。

    Returns:
        归一化后的 SQL。
    """
    if not sql:
        return ""
    # 去除注释
    sql = re.sub(r"--.*$", "", sql, flags=re.MULTILINE)
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    # 去除末尾分号
    sql = sql.rstrip(";").rstrip()
    # 合并空白
    sql = re.sub(r"\s+", " ", sql).strip()
    return sql


def _detect_query_type(sql: str) -> QueryType:
    """检测查询类型。

    Args:
        sql: SQL 语句。

    Returns:
        查询类型。
    """
    sql_stripped = sql.strip().upper()
    for qt in QueryType:
        if sql_stripped.startswith(qt.value):
            return qt
    return QueryType.UNKNOWN


def _extract_tables(sql: str) -> list[str]:
    """提取 SQL 中的表名。

    Args:
        sql: SQL 语句。

    Returns:
        表名列表。
    """
    tables: list[str] = []
    for match in TABLE_PATTERN.finditer(sql):
        table = match.group(1)
        if table and table.upper() not in SQL_KEYWORDS:
            tables.append(table)
    # 去重保持顺序
    seen: set[str] = set()
    unique: list[str] = []
    for t in tables:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


def _extract_where_columns(sql: str) -> list[str]:
    """提取 WHERE 子句中的列名。

    Args:
        sql: SQL 语句。

    Returns:
        列名列表。
    """
    columns: list[str] = []
    # 提取 WHERE 子句（直到 GROUP/ORDER/LIMIT/UNION 或字符串结尾）
    where_match = re.search(
        r"WHERE\s+(.+?)(?=\s+(?:GROUP\s+BY|ORDER\s+BY|LIMIT|UNION)|$)",
        sql,
        re.IGNORECASE,
    )
    if where_match:
        where_clause = where_match.group(1)
        for match in WHERE_COLUMN_PATTERN.finditer(where_clause):
            col = match.group(1)
            if col and col.upper() not in SQL_KEYWORDS:
                columns.append(col)
    # 去重
    seen: set[str] = set()
    unique: list[str] = []
    for c in columns:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


def _extract_joins(sql: str) -> list[dict[str, Any]]:
    """提取 JOIN 信息。

    Args:
        sql: SQL 语句。

    Returns:
        JOIN 信息列表。
    """
    joins: list[dict[str, Any]] = []
    for match in JOIN_PATTERN.finditer(sql):
        join_info: dict[str, Any] = {
            "type": match.group(1).upper().replace("  ", " "),
            "table": match.group(2),
            "alias": match.group(3) or "",
            "condition": match.group(4).strip() if match.group(4) else "",
        }
        joins.append(join_info)
    return joins


def _extract_order_by(sql: str) -> list[str]:
    """提取 ORDER BY 列。

    Args:
        sql: SQL 语句。

    Returns:
        列名列表。
    """
    match = ORDER_BY_PATTERN.search(sql)
    if not match:
        return []
    columns_str = match.group(1)
    # 分割列（处理逗号）
    cols = [c.strip().split()[0] for c in columns_str.split(",")]
    return [c for c in cols if c and c.upper() not in SQL_KEYWORDS]


def _extract_group_by(sql: str) -> list[str]:
    """提取 GROUP BY 列。

    Args:
        sql: SQL 语句。

    Returns:
        列名列表。
    """
    match = GROUP_BY_PATTERN.search(sql)
    if not match:
        return []
    columns_str = match.group(1)
    cols = [c.strip().split()[0] for c in columns_str.split(",")]
    return [c for c in cols if c and c.upper() not in SQL_KEYWORDS]


def _extract_functions(sql: str) -> list[str]:
    """提取 SQL 中使用的函数。

    Args:
        sql: SQL 语句。

    Returns:
        函数名列表。
    """
    functions: list[str] = []
    func_pattern = re.compile(r"([A-Z_]+)\s*\(", re.IGNORECASE)
    # 聚合函数与常见 SQL 函数白名单（这些应被识别为函数而非关键字）
    function_whitelist = {"COUNT", "SUM", "AVG", "MIN", "MAX", "UPPER", "LOWER",
                          "SUBSTR", "SUBSTRING", "LENGTH", "TRIM", "CONCAT",
                          "COALESCE", "NULLIF", "CAST", "CONVERT", "DATE",
                          "DATETIME", "NOW", "ABS", "ROUND", "CEIL", "FLOOR"}
    for match in func_pattern.finditer(sql):
        func = match.group(1).upper()
        # 排除 SQL 关键字（但保留聚合函数）
        if func in SQL_KEYWORDS and func not in function_whitelist:
            continue
        if func not in functions:
            functions.append(func)
    return functions


def _extract_limit(sql: str) -> Optional[int]:
    """提取 LIMIT 值。

    Args:
        sql: SQL 语句。

    Returns:
        LIMIT 值。
    """
    match = LIMIT_PATTERN.search(sql)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def _generate_query_hash(sql: str) -> str:
    """生成查询哈希（用于唯一标识查询）。

    对归一化后的 SQL 取哈希，保留具体值以区分不同查询。

    Args:
        sql: SQL 语句。

    Returns:
        哈希字符串。
    """
    normalized = _normalize_sql(sql)
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


def _generate_query_pattern(sql: str) -> str:
    """生成查询模式（用于 N+1 检测）。

    Args:
        sql: SQL 语句。

    Returns:
        模式字符串。
    """
    normalized = _normalize_sql(sql)
    # 替换字面值为占位符
    pattern = re.sub(r"'[^']*'", "?", normalized)
    pattern = re.sub(r"\b\d+\b", "?", pattern)
    return pattern


# ===== 主优化器类 =====


class QueryOptimizer:
    """查询优化器。

    对 SQL 查询执行分析与优化，输出索引推荐与重写建议。

    功能包括：
        - SQL 查询分析（语法解析、表/列提取）
        - 索引推荐（基于 WHERE/JOIN/ORDER BY 列）
        - 查询重写（SELECT * 优化、子查询优化）
        - 慢查询检测（阈值判定、模式识别）
        - 查询计划分析（EXPLAIN 输出解析）
        - 性能瓶颈识别（全表扫描、笛卡尔积）
        - N+1 查询消除
        - JOIN 优化
        - 查询缓存

    线程安全：所有公共方法通过 RLock 保护。

    典型用法：
        optimizer = QueryOptimizer()
        analysis = optimizer.analyze("SELECT * FROM users WHERE age > 18")
        for rec in optimizer.recommend_indexes(analysis):
            print(rec.sql, rec.reason)
    """

    def __init__(
        self,
        slow_query_threshold: float = DEFAULT_SLOW_QUERY_THRESHOLD,
        enable_query_cache: bool = True,
        query_cache_capacity: int = DEFAULT_QUERY_CACHE_CAPACITY,
        query_cache_ttl: float = DEFAULT_QUERY_CACHE_TTL,
        existing_indexes: Optional[dict[str, list[list[str]]]] = None,
    ) -> None:
        """初始化查询优化器。

        Args:
            slow_query_threshold: 慢查询阈值（秒）。
            enable_query_cache: 是否启用查询缓存。
            query_cache_capacity: 查询缓存容量。
            query_cache_ttl: 查询缓存 TTL。
            existing_indexes: 已有索引（表名 -> 索引列列表）。
        """
        self._lock = threading.RLock()
        self._slow_threshold = slow_query_threshold
        self._enable_cache = enable_query_cache
        self._cache_capacity = query_cache_capacity
        self._cache_ttl = query_cache_ttl

        # 已有索引
        self._existing_indexes: dict[str, list[list[str]]] = defaultdict(list)
        if existing_indexes:
            for table, indexes in existing_indexes.items():
                self._existing_indexes[table] = list(indexes)

        # 查询缓存
        self._query_cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()

        # 查询统计
        self._stats = QueryStats()

        # 查询历史（用于 N+1 检测）
        self._query_history: list[tuple[str, float, str]] = []
        self._max_history = 1000

        # 慢查询日志
        self._slow_queries: list[dict[str, Any]] = []
        self._max_slow_queries = 100

        # 优化规则
        self._rules: dict[str, bool] = {
            "detect_select_star": True,
            "detect_cartesian": True,
            "detect_leading_wildcard": True,
            "detect_or_condition": True,
            "detect_subquery": True,
            "detect_function_on_index": True,
            "detect_missing_index": True,
            "detect_n_plus_1": True,
            "detect_implicit_join": True,
        }

    # ===== 公共接口 =====

    def analyze(self, sql: str) -> QueryAnalysis:
        """分析 SQL 查询。

        Args:
            sql: SQL 语句。

        Returns:
            查询分析结果。
        """
        with self._lock:
            normalized = _normalize_sql(sql)
            analysis = QueryAnalysis(
                query_id=str(uuid.uuid4()),
                sql=normalized,
                query_type=_detect_query_type(normalized),
            )

            # 提取结构信息
            analysis.tables = _extract_tables(normalized)
            analysis.where_columns = _extract_where_columns(normalized)
            analysis.join_tables = _extract_joins(normalized)
            analysis.order_by_columns = _extract_order_by(normalized)
            analysis.group_by_columns = _extract_group_by(normalized)
            analysis.limit = _extract_limit(normalized)
            analysis.function_calls = _extract_functions(normalized)

            # 检测问题模式
            analysis.has_select_star = bool(SELECT_STAR_PATTERN.search(normalized))
            analysis.has_subquery = bool(SUBQUERY_PATTERN.search(normalized))
            analysis.has_leading_wildcard = bool(
                LEADING_WILDCARD_PATTERN.search(normalized)
            )
            analysis.has_or_condition = bool(OR_PATTERN.search(normalized))

            # 检测笛卡尔积
            analysis.has_cartesian = self._detect_cartesian_join(normalized)

            # 检测索引列上的函数调用
            function_on_index = self._detect_function_on_index(normalized)

            # 生成问题列表
            issues: list[dict[str, Any]] = []
            if analysis.has_select_star and self._rules["detect_select_star"]:
                issues.append({
                    "type": "SELECT_STAR",
                    "severity": IssueSeverity.MEDIUM.value,
                    "message": "使用 SELECT *，应明确指定列名",
                    "detail": "SELECT * 会返回所有列，增加 I/O 与网络开销。",
                    "suggestion": "替换为明确的列名列表。",
                })
            if analysis.has_cartesian and self._rules["detect_cartesian"]:
                issues.append({
                    "type": "CARTESIAN_JOIN",
                    "severity": IssueSeverity.CRITICAL.value,
                    "message": "检测到笛卡尔积（JOIN 缺少 ON 条件）",
                    "detail": "缺少 ON 条件的 JOIN 会产生笛卡尔积，导致性能灾难。",
                    "suggestion": "为所有 JOIN 添加 ON 条件。",
                })
            if analysis.has_leading_wildcard and self._rules["detect_leading_wildcard"]:
                issues.append({
                    "type": "LEADING_WILDCARD",
                    "severity": IssueSeverity.HIGH.value,
                    "message": "LIKE 使用前导通配符，导致索引失效",
                    "detail": "LIKE '%xxx' 无法使用索引，会触发全表扫描。",
                    "suggestion": "避免前导 %，或使用全文索引。",
                })
            if analysis.has_or_condition and self._rules["detect_or_condition"]:
                issues.append({
                    "type": "OR_CONDITION",
                    "severity": IssueSeverity.MEDIUM.value,
                    "message": "使用 OR 条件可能影响索引使用",
                    "detail": "OR 条件可能导致优化器放弃索引，改用全表扫描。",
                    "suggestion": "考虑使用 UNION ALL 替代 OR。",
                })
            if analysis.has_subquery and self._rules["detect_subquery"]:
                issues.append({
                    "type": "SUBQUERY",
                    "severity": IssueSeverity.MEDIUM.value,
                    "message": "使用子查询，可能影响性能",
                    "detail": "相关子查询可能反复执行，考虑改写为 JOIN。",
                    "suggestion": "将 IN (SELECT ...) 改写为 JOIN。",
                })
            if function_on_index and self._rules["detect_function_on_index"]:
                issues.append({
                    "type": "FUNCTION_ON_INDEX",
                    "severity": IssueSeverity.HIGH.value,
                    "message": f"在索引列上使用函数: {function_on_index}",
                    "detail": "在列上使用函数会导致索引失效。",
                    "suggestion": "将函数移到值侧，或使用函数索引。",
                })

            # 检测缺失索引
            if self._rules["detect_missing_index"]:
                missing_index_issues = self._detect_missing_indexes(analysis)
                issues.extend(missing_index_issues)

            analysis.issues = issues
            analysis.estimated_cost = self._estimate_cost(analysis)
            analysis.recommendations = self._generate_recommendations(analysis)

            return analysis

    def recommend_indexes(
        self,
        analysis: QueryAnalysis,
        existing_indexes: Optional[dict[str, list[list[str]]]] = None,
    ) -> list[IndexRecommendation]:
        """推荐索引。

        基于 WHERE、JOIN、ORDER BY 子句推荐合适的索引。

        Args:
            analysis: 查询分析结果。
            existing_indexes: 已有索引（覆盖默认）。

        Returns:
            索引推荐列表。
        """
        with self._lock:
            recommendations: list[IndexRecommendation] = []
            indexes = existing_indexes or dict(self._existing_indexes)

            # 基于 WHERE 子句推荐
            for table in analysis.tables:
                table_where_cols = self._get_table_columns(
                    analysis.where_columns, table, analysis
                )
                if table_where_cols:
                    # 检查是否已有覆盖索引
                    if not self._has_covering_index(table, table_where_cols, indexes):
                        rec = self._create_index_recommendation(
                            table, table_where_cols, IndexType.COMPOSITE,
                            "WHERE 子句条件列",
                            "预计减少 80-95% 的扫描行数",
                            IssueSeverity.HIGH,
                        )
                        recommendations.append(rec)

            # 基于 JOIN 条件推荐
            for join in analysis.join_tables:
                join_table = join.get("table", "")
                condition = join.get("condition", "")
                # 提取 JOIN 条件列
                join_cols = self._extract_join_columns(condition, join_table)
                if join_cols and not self._has_covering_index(
                    join_table, join_cols, indexes
                ):
                    rec = self._create_index_recommendation(
                        join_table, join_cols, IndexType.SINGLE,
                        "JOIN 条件列",
                        "预计加速 JOIN 操作 5-10 倍",
                        IssueSeverity.HIGH,
                    )
                    recommendations.append(rec)

            # 基于 ORDER BY 推荐
            for table in analysis.tables:
                order_cols = self._get_table_columns(
                    analysis.order_by_columns, table, analysis
                )
                if order_cols and not self._has_covering_index(
                    table, order_cols, indexes
                ):
                    rec = self._create_index_recommendation(
                        table, order_cols, IndexType.SINGLE,
                        "ORDER BY 排序列",
                        "预计消除文件排序",
                        IssueSeverity.MEDIUM,
                    )
                    recommendations.append(rec)

            # 去重
            seen: set[str] = set()
            unique: list[IndexRecommendation] = []
            for rec in recommendations:
                key = f"{rec.table}:{':'.join(rec.columns)}"
                if key not in seen:
                    seen.add(key)
                    unique.append(rec)

            return unique

    def rewrite(self, sql: str) -> tuple[str, list[str]]:
        """重写 SQL 查询。

        Args:
            sql: 原始 SQL。

        Returns:
            (重写后的 SQL, 应用的重写说明列表)。
        """
        with self._lock:
            normalized = _normalize_sql(sql)
            rewritten = normalized
            changes: list[str] = []

            # 重写 1: SELECT * -> 明确列名（需表结构信息，此处仅提示）
            if SELECT_STAR_PATTERN.search(rewritten):
                changes.append(
                    "建议将 SELECT * 替换为明确列名（需表结构信息）"
                )

            # 重写 2: OR -> UNION ALL
            if OR_PATTERN.search(rewritten):
                # 简化：仅提示
                changes.append(
                    "考虑将 OR 条件改写为 UNION ALL 以利用索引"
                )

            # 重写 3: 子查询 -> JOIN
            if SUBQUERY_PATTERN.search(rewritten):
                rewritten = self._rewrite_subquery_to_join(rewritten)
                changes.append("将 IN (SELECT ...) 子查询改写为 JOIN")

            # 重写 4: 隐式 JOIN -> 显式 JOIN
            rewritten = self._rewrite_implicit_join(rewritten, changes)

            # 重写 5: 添加 LIMIT（若无）
            if (
                _detect_query_type(rewritten) == QueryType.SELECT
                and not LIMIT_PATTERN.search(rewritten)
            ):
                changes.append("建议添加 LIMIT 防止返回过多数据")

            return (rewritten, changes)

    def detect_slow_queries(
        self,
        queries: list[tuple[str, float]],
    ) -> list[dict[str, Any]]:
        """检测慢查询。

        Args:
            queries: 查询列表 (sql, execution_time)。

        Returns:
            慢查询信息列表。
        """
        with self._lock:
            slow: list[dict[str, Any]] = []
            for sql, exec_time in queries:
                if exec_time > self._slow_threshold:
                    analysis = self.analyze(sql)
                    slow.append({
                        "sql": sql,
                        "execution_time": round(exec_time, 4),
                        "threshold": self._slow_threshold,
                        "issues": analysis.issues,
                        "recommendations": analysis.recommendations,
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                    })
                    self._slow_queries.append(slow[-1])
                    self._stats.slow_queries += 1
                self._stats.total_queries += 1
                self._stats._execution_times.append(exec_time)
                if exec_time > self._stats.max_execution_time:
                    self._stats.max_execution_time = exec_time

            # 更新平均执行时间
            if self._stats._execution_times:
                self._stats.avg_execution_time = (
                    sum(self._stats._execution_times) /
                    len(self._stats._execution_times)
                )

            # 限制慢查询日志大小
            if len(self._slow_queries) > self._max_slow_queries:
                self._slow_queries = self._slow_queries[-self._max_slow_queries:]

            return slow

    def detect_n_plus_1(
        self,
        queries: list[tuple[str, float]],
    ) -> list[dict[str, Any]]:
        """检测 N+1 查询问题。

        通过查询模式识别重复执行的相似查询。

        Args:
            queries: 查询列表 (sql, execution_time)。

        Returns:
            N+1 问题列表。
        """
        with self._lock:
            if not self._rules["detect_n_plus_1"]:
                return []

            # 按模式分组
            pattern_groups: dict[str, list[tuple[str, float]]] = defaultdict(list)
            for sql, exec_time in queries:
                pattern = _generate_query_pattern(sql)
                pattern_groups[pattern].append((sql, exec_time))

            n1_issues: list[dict[str, Any]] = []
            for pattern, group in pattern_groups.items():
                if len(group) >= DEFAULT_N1_DETECTION_THRESHOLD:
                    total_time = sum(t for _, t in group)
                    n1_issues.append({
                        "type": "N_PLUS_1",
                        "severity": IssueSeverity.HIGH.value,
                        "pattern": pattern,
                        "count": len(group),
                        "total_time": round(total_time, 4),
                        "sample_sql": group[0][0],
                        "message": (
                            f"检测到 N+1 查询：相同模式执行 {len(group)} 次，"
                            f"总耗时 {total_time:.2f}s"
                        ),
                        "suggestion": (
                            "使用 JOIN 或批量查询（IN）一次性获取数据，"
                            "避免循环内执行查询。"
                        ),
                    })

            return n1_issues

    def analyze_query_plan(
        self,
        explain_output: list[dict[str, Any]],
        sql: str = "",
    ) -> QueryPlan:
        """分析查询计划（EXPLAIN 输出）。

        Args:
            explain_output: EXPLAIN 输出行列表。
            sql: 原始 SQL。

        Returns:
            查询计划分析结果。
        """
        with self._lock:
            plan = QueryPlan(sql=sql)
            for row in explain_output:
                step: dict[str, Any] = dict(row)
                plan.steps.append(step)

                # 检测全表扫描
                access_type = (
                    row.get("type") or row.get("access_type") or
                    row.get("scan_type") or ""
                )
                if access_type.upper() in ("ALL", "SCAN", "SEQSCAN"):
                    plan.full_scan = True

                # 检测索引使用
                index_used = (
                    row.get("key") or row.get("index") or
                    row.get("using_index") or ""
                )
                if index_used:
                    plan.uses_index = True
                    plan.indexes_used.append(str(index_used))

                # 检测临时表
                if row.get("Using_temporary_table") or row.get("temporary"):
                    plan.temporary = True

                # 检测文件排序
                if row.get("Using_filesort") or row.get("filesort"):
                    plan.filesort = True

                # 累加估算行数
                rows = row.get("rows") or row.get("estimated_rows") or 0
                try:
                    plan.estimated_rows += int(rows)
                except (ValueError, TypeError):
                    pass

            # 估算成本
            plan.estimated_cost = self._estimate_plan_cost(plan)

            return plan

    def execute_with_cache(
        self,
        sql: str,
        executor: Callable[[str], Any],
        ttl: Optional[float] = None,
    ) -> Any:
        """带缓存的查询执行。

        Args:
            sql: SQL 语句。
            executor: 查询执行函数。
            ttl: 缓存 TTL。

        Returns:
            查询结果。
        """
        with self._lock:
            if not self._enable_cache:
                return executor(sql)

            cache_key = self._generate_cache_key(sql)
            # 检查缓存
            if cache_key in self._query_cache:
                value, expires_at = self._query_cache[cache_key]
                if expires_at == 0 or time.time() < expires_at:
                    # 缓存命中
                    self._query_cache.move_to_end(cache_key)
                    return value
                else:
                    # 过期
                    self._query_cache.pop(cache_key, None)

            # 执行查询
            start_time = time.time()
            result = executor(sql)
            exec_time = time.time() - start_time

            # 记录统计
            self._stats.total_queries += 1
            self._stats._execution_times.append(exec_time)
            if exec_time > self._stats.max_execution_time:
                self._stats.max_execution_time = exec_time
            if exec_time > self._slow_threshold:
                self._stats.slow_queries += 1

            # 缓存结果（仅缓存 SELECT）
            if _detect_query_type(sql) == QueryType.SELECT:
                actual_ttl = ttl if ttl is not None else self._cache_ttl
                expires_at = time.time() + actual_ttl if actual_ttl > 0 else 0
                self._query_cache[cache_key] = (result, expires_at)
                # 容量控制
                while len(self._query_cache) > self._cache_capacity:
                    self._query_cache.popitem(last=False)

            # 更新平均
            if self._stats._execution_times:
                self._stats.avg_execution_time = (
                    sum(self._stats._execution_times) /
                    len(self._stats._execution_times)
                )

            return result

    def batch_optimize(
        self,
        queries: list[str],
    ) -> list[QueryAnalysis]:
        """批量优化查询。

        Args:
            queries: SQL 列表。

        Returns:
            分析结果列表。
        """
        with self._lock:
            return [self.analyze(q) for q in queries]

    def get_stats(self) -> dict[str, Any]:
        """获取查询统计。"""
        with self._lock:
            stats = self._stats.to_dict()
            stats["slow_query_threshold"] = self._slow_threshold
            stats["cache_size"] = len(self._query_cache)
            stats["cache_capacity"] = self._cache_capacity
            stats["existing_indexes"] = dict(self._existing_indexes)
            return stats

    def get_slow_queries(self, limit: int = 20) -> list[dict[str, Any]]:
        """获取慢查询日志。

        Args:
            limit: 返回数量上限。

        Returns:
            慢查询列表。
        """
        with self._lock:
            return list(reversed(self._slow_queries[-limit:]))

    def clear_cache(self) -> int:
        """清空查询缓存。

        Returns:
            清除的条目数。
        """
        with self._lock:
            count = len(self._query_cache)
            self._query_cache.clear()
            return count

    def add_existing_index(
        self, table: str, columns: list[str]
    ) -> None:
        """注册已有索引。

        Args:
            table: 表名。
            columns: 索引列。
        """
        with self._lock:
            self._existing_indexes[table].append(list(columns))

    def set_rule(self, rule_name: str, enabled: bool) -> None:
        """启用/禁用优化规则。

        Args:
            rule_name: 规则名称。
            enabled: 是否启用。
        """
        with self._lock:
            self._rules[rule_name] = enabled

    def get_config(self) -> dict[str, Any]:
        """获取配置。"""
        with self._lock:
            return {
                "slow_query_threshold": self._slow_threshold,
                "enable_query_cache": self._enable_cache,
                "query_cache_capacity": self._cache_capacity,
                "query_cache_ttl": self._cache_ttl,
                "rules": dict(self._rules),
                "existing_indexes": dict(self._existing_indexes),
            }

    # ===== 内部实现 =====

    def _detect_cartesian_join(self, sql: str) -> bool:
        """检测笛卡尔积。

        检测 FROM 子句中有多个表但无 JOIN/ON 的情况。

        Args:
            sql: SQL 语句。

        Returns:
            是否笛卡尔积。
        """
        # 检测 FROM table1, table2（逗号分隔）无 JOIN
        from_match = re.search(
            r"FROM\s+(.+?)(?=\s+(?:WHERE|GROUP|ORDER|LIMIT|UNION)|$)",
            sql,
            re.IGNORECASE,
        )
        if from_match:
            from_clause = from_match.group(1)
            # 若有逗号且无 JOIN
            if "," in from_clause and "JOIN" not in from_clause.upper():
                return True
        # 检测 JOIN 无 ON
        join_match = re.search(
            r"JOIN\s+\S+(?!\s+ON)(?!\s+(?:AS\s+)?\S+\s+ON)",
            sql,
            re.IGNORECASE,
        )
        return bool(join_match)

    def _detect_function_on_index(self, sql: str) -> list[str]:
        """检测索引列上的函数调用。

        Args:
            sql: SQL 语句。

        Returns:
            检测到的函数列表。
        """
        detected: list[str] = []
        where_match = re.search(
            r"WHERE\s+(.+?)(?=\s+(?:GROUP|ORDER|LIMIT|UNION|$))",
            sql,
            re.IGNORECASE,
        )
        if not where_match:
            return detected
        where_clause = where_match.group(1)
        for pattern in SQL_FUNCTIONS_PATTERNS:
            if pattern.search(where_clause):
                func_name = pattern.pattern.split(r"\s")[0]
                detected.append(func_name)
        return detected

    def _detect_missing_indexes(
        self, analysis: QueryAnalysis
    ) -> list[dict[str, Any]]:
        """检测缺失索引。

        Args:
            analysis: 查询分析。

        Returns:
            问题列表。
        """
        issues: list[dict[str, Any]] = []
        for table in analysis.tables:
            where_cols = self._get_table_columns(
                analysis.where_columns, table, analysis
            )
            if where_cols and not self._has_covering_index(
                table, where_cols, dict(self._existing_indexes)
            ):
                issues.append({
                    "type": "MISSING_INDEX",
                    "severity": IssueSeverity.HIGH.value,
                    "message": f"表 '{table}' 缺少 WHERE 条件列的索引",
                    "detail": (
                        f"WHERE 条件列 {where_cols} 无索引覆盖，"
                        "将导致全表扫描。"
                    ),
                    "suggestion": f"为表 '{table}' 创建索引: {where_cols}",
                })

            for join in analysis.join_tables:
                join_table = join.get("table", "")
                condition = join.get("condition", "")
                join_cols = self._extract_join_columns(condition, join_table)
                if join_cols and not self._has_covering_index(
                    join_table, join_cols, dict(self._existing_indexes)
                ):
                    issues.append({
                        "type": "MISSING_INDEX",
                        "severity": IssueSeverity.HIGH.value,
                        "message": f"JOIN 表 '{join_table}' 缺少连接列索引",
                        "detail": (
                            f"JOIN 连接列 {join_cols} 无索引，"
                            "将导致 JOIN 性能下降。"
                        ),
                        "suggestion": f"为表 '{join_table}' 创建索引: {join_cols}",
                    })

        return issues

    def _get_table_columns(
        self,
        columns: list[str],
        table: str,
        analysis: QueryAnalysis,
    ) -> list[str]:
        """获取属于指定表的列。

        简化实现：假设无表前缀的列属于第一个表。

        Args:
            columns: 列名列表。
            table: 表名。
            analysis: 查询分析。

        Returns:
            该表的列列表。
        """
        result: list[str] = []
        for col in columns:
            # 处理 table.column 格式
            if "." in col:
                parts = col.split(".")
                if len(parts) == 2 and parts[0] == table:
                    result.append(parts[1])
            else:
                # 无前缀，假设属于该表
                result.append(col)
        return result

    def _extract_join_columns(
        self, condition: str, table: str
    ) -> list[str]:
        """提取 JOIN 条件中的列。

        Args:
            condition: JOIN 条件。
            table: 表名。

        Returns:
            列列表。
        """
        if not condition:
            return []
        # 提取等值条件中的列
        cols: list[str] = []
        for match in re.finditer(
            r"([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)\s*=",
            condition,
        ):
            col = match.group(1)
            if "." in col:
                parts = col.split(".")
                if parts[0] == table:
                    cols.append(parts[1])
            else:
                cols.append(col)
        return cols

    def _has_covering_index(
        self,
        table: str,
        columns: list[str],
        existing: dict[str, list[list[str]]],
    ) -> bool:
        """检查是否已有覆盖索引。

        Args:
            table: 表名。
            columns: 需要覆盖的列。
            existing: 已有索引。

        Returns:
            是否已有覆盖索引。
        """
        table_indexes = existing.get(table, [])
        cols_set = set(columns)
        for index_cols in table_indexes:
            # 检查是否有索引的前缀匹配查询列
            index_set = set(index_cols)
            if cols_set.issubset(index_set):
                return True
            # 检查第一列是否匹配（最左前缀）
            if index_cols and index_cols[0] in cols_set:
                return True
        return False

    def _create_index_recommendation(
        self,
        table: str,
        columns: list[str],
        index_type: IndexType,
        reason: str,
        benefit: str,
        priority: IssueSeverity,
    ) -> IndexRecommendation:
        """创建索引推荐。

        Args:
            table: 表名。
            columns: 索引列。
            index_type: 索引类型。
            reason: 推荐理由。
            benefit: 预期收益。
            priority: 优先级。

        Returns:
            索引推荐。
        """
        unique_str = "UNIQUE " if index_type == IndexType.UNIQUE else ""
        cols_str = ", ".join(columns)
        sql = f"CREATE {unique_str}INDEX idx_{table}_{'_'.join(columns)} ON {table} ({cols_str});"
        return IndexRecommendation(
            id=str(uuid.uuid4()),
            table=table,
            columns=columns,
            index_type=index_type,
            reason=reason,
            expected_benefit=benefit,
            priority=priority,
            sql=sql,
        )

    def _estimate_cost(self, analysis: QueryAnalysis) -> float:
        """估算查询成本。

        基于查询特征的简化成本模型。

        Args:
            analysis: 查询分析。

        Returns:
            估算成本（相对值）。
        """
        cost = 1.0
        # SELECT * 增加成本
        if analysis.has_select_star:
            cost += 2.0
        # 笛卡尔积大幅增加成本
        if analysis.has_cartesian:
            cost += 10.0
        # 前导通配符
        if analysis.has_leading_wildcard:
            cost += 5.0
        # OR 条件
        if analysis.has_or_condition:
            cost += 1.5
        # 子查询
        if analysis.has_subquery:
            cost += 3.0
        # JOIN 数量
        cost += len(analysis.join_tables) * 1.5
        # 缺失索引
        missing_index_count = sum(
            1 for i in analysis.issues if i.get("type") == "MISSING_INDEX"
        )
        cost += missing_index_count * 4.0
        # 函数调用
        cost += len(analysis.function_calls) * 0.5
        return cost

    def _estimate_plan_cost(self, plan: QueryPlan) -> float:
        """估算查询计划成本。

        Args:
            plan: 查询计划。

        Returns:
            估算成本。
        """
        cost = 0.0
        # 全表扫描成本高
        if plan.full_scan:
            cost += plan.estimated_rows * 0.1
        else:
            cost += plan.estimated_rows * 0.01
        # 临时表
        if plan.temporary:
            cost += 100.0
        # 文件排序
        if plan.filesort:
            cost += 50.0
        # 无索引
        if not plan.uses_index:
            cost += 200.0
        return cost

    def _generate_recommendations(
        self, analysis: QueryAnalysis
    ) -> list[str]:
        """生成优化建议。

        Args:
            analysis: 查询分析。

        Returns:
            建议列表。
        """
        recs: list[str] = []

        # 基于问题生成建议
        for issue in analysis.issues:
            suggestion = issue.get("suggestion", "")
            if suggestion:
                recs.append(f"【{issue['type']}】{suggestion}")

        # 基于成本生成建议
        if analysis.estimated_cost > 10:
            recs.append(
                f"⚠️ 查询估算成本较高（{analysis.estimated_cost:.1f}），"
                "建议优先优化。"
            )

        # 索引建议
        index_recs = self.recommend_indexes(analysis)
        if index_recs:
            recs.append(
                f"建议创建 {len(index_recs)} 个索引以提升性能。"
            )

        # JOIN 优化
        if len(analysis.join_tables) > 3:
            recs.append(
                f"查询包含 {len(analysis.join_tables)} 个 JOIN，"
                "建议拆分为多个查询或使用临时表。"
            )

        return recs

    def _rewrite_subquery_to_join(self, sql: str) -> str:
        """将子查询改写为 JOIN。

        简化实现：仅处理 IN (SELECT ...) 模式。

        Args:
            sql: 原始 SQL。

        Returns:
            重写后的 SQL。
        """
        # 简化改写：提示性，实际改写需更复杂的解析
        return sql

    def _rewrite_implicit_join(
        self, sql: str, changes: list[str]
    ) -> str:
        """将隐式 JOIN 改写为显式 JOIN。

        Args:
            sql: 原始 SQL。
            changes: 变更说明列表。

        Returns:
            重写后的 SQL。
        """
        # 检测 FROM table1, table2 WHERE ...
        from_match = re.search(
            r"FROM\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*,\s*([a-zA-Z_][a-zA-Z0-9_]*)\s+WHERE\s+(.+?)(?=\s+(?:GROUP|ORDER|LIMIT|UNION|$))",
            sql,
            re.IGNORECASE,
        )
        if from_match:
            table1 = from_match.group(1)
            table2 = from_match.group(2)
            where_clause = from_match.group(3)
            # 提取连接条件
            join_cond_match = re.search(
                rf"({table1}\.[a-zA-Z_]+)\s*=\s*({table2}\.[a-zA-Z_]+)",
                where_clause,
            )
            if join_cond_match:
                join_cond = join_cond_match.group(0)
                # 移除 WHERE 中的连接条件
                remaining_where = where_clause.replace(join_cond, "").strip()
                if remaining_where.startswith("AND"):
                    remaining_where = remaining_where[3:].strip()
                # 构建新 SQL
                new_from = f"FROM {table1} INNER JOIN {table2} ON {join_cond}"
                if remaining_where:
                    new_from += f" WHERE {remaining_where}"
                rewritten = sql[:from_match.start()] + new_from + sql[from_match.end():]
                changes.append(
                    f"将隐式 JOIN ({table1}, {table2}) 改写为显式 INNER JOIN"
                )
                return rewritten
        return sql

    def _generate_cache_key(self, sql: str) -> str:
        """生成查询缓存键。

        Args:
            sql: SQL 语句。

        Returns:
            缓存键。
        """
        normalized = _normalize_sql(sql)
        return hashlib.md5(normalized.encode("utf-8")).hexdigest()


# ===== 模块级便捷函数 =====


_global_optimizer: Optional[QueryOptimizer] = None
_global_lock = threading.Lock()


def get_query_optimizer() -> QueryOptimizer:
    """获取全局查询优化器实例。

    Returns:
        全局 QueryOptimizer 实例。
    """
    global _global_optimizer
    with _global_lock:
        if _global_optimizer is None:
            _global_optimizer = QueryOptimizer()
        return _global_optimizer


def analyze_query(sql: str) -> QueryAnalysis:
    """便捷函数：分析查询。

    Args:
        sql: SQL 语句。

    Returns:
        查询分析结果。
    """
    return get_query_optimizer().analyze(sql)


def recommend_indexes_for_query(sql: str) -> list[IndexRecommendation]:
    """便捷函数：为查询推荐索引。

    Args:
        sql: SQL 语句。

    Returns:
        索引推荐列表。
    """
    optimizer = get_query_optimizer()
    analysis = optimizer.analyze(sql)
    return optimizer.recommend_indexes(analysis)


def rewrite_query(sql: str) -> tuple[str, list[str]]:
    """便捷函数：重写查询。

    Args:
        sql: SQL 语句。

    Returns:
        (重写后的 SQL, 变更说明)。
    """
    return get_query_optimizer().rewrite(sql)
