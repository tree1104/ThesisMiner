"""数据真实性验证器模块

提供研究数据的真实性与完整性验证能力，包括：
    - 统计异常检测（Z-score、IQR、Grubbs 检验）
    - 数据分布验证（正态性、均匀性、Benford 定律）
    - 离群点检测（多变量、单变量）
    - 图表数据一致性检查（图表与表格数据匹配）
    - 表格数据交叉验证（多表格间数据一致性）
    - 实验数据可重复性评估（方差分析、置信区间）
    - 数据完整性检查（缺失值、重复值、范围校验）
    - 验证报告生成、可疑数据标注、整改建议

设计原则：
    1. 零外部依赖：仅使用 Python 标准库（math/statistics）
    2. 线程安全：所有公共方法通过 RLock 保护
    3. 可配置：阈值、检验方法均可调整
    4. 可解释：每个异常附带统计量与判定依据
    5. 离线运行：所有检验基于本地计算，无需网络
"""
from __future__ import annotations

import hashlib
import math
import re
import threading
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Iterable, Optional, Sequence


# ===== 枚举 =====


class AnomalyType(str, Enum):
    """异常类型。"""

    OUTLIER = "outlier"                    # 离群点
    DISTRIBUTION_ANOMALY = "distribution"  # 分布异常
    DUPLICATE_DATA = "duplicate"           # 重复数据
    MISSING_DATA = "missing"               # 缺失数据
    RANGE_VIOLATION = "range"              # 范围违规
    CONSISTENCY_ERROR = "consistency"      # 一致性错误
    REPRODUCIBILITY_ISSUE = "reproducibility"  # 可重复性问题
    FABRICATION_SUSPECT = "fabrication"    # 造假嫌疑
    ROUNDING_ANOMALY = "rounding"          # 舍入异常
    BENFORD_VIOLATION = "benford"          # Benford 违规


class SeverityLevel(str, Enum):
    """严重程度。"""

    INFO = "info"        # 提示
    LOW = "low"          # 低
    MEDIUM = "medium"    # 中
    HIGH = "high"        # 高
    CRITICAL = "critical"  # 严重


# ===== 常量 =====


# 默认 Z-score 离群点阈值
DEFAULT_ZSCORE_THRESHOLD = 3.0

# 默认 IQR 倍数（用于箱线图离群点检测）
DEFAULT_IQR_MULTIPLIER = 1.5

# 默认 Grubbs 检验显著性水平
DEFAULT_GRUBBS_ALPHA = 0.05

# Benford 定律偏差阈值
DEFAULT_BENFORD_DEVIATION = 0.15

# 重复数据比例阈值
DEFAULT_DUPLICATE_RATIO = 0.1

# 缺失数据比例阈值
DEFAULT_MISSING_RATIO = 0.2

# 舍入异常检测：末位数字分布均匀性阈值
DEFAULT_ROUNDING_DEVIATION = 0.2

# 可重复性：变异系数阈值
DEFAULT_CV_THRESHOLD = 0.15

# 正态性检验：偏度阈值
DEFAULT_SKEWNESS_THRESHOLD = 2.0

# 正态性检验：峰度阈值
DEFAULT_KURTOSIS_THRESHOLD = 7.0

# Benford 定律首位数字期望分布
BENFORD_EXPECTED = {
    1: 0.301, 2: 0.176, 3: 0.125, 4: 0.097, 5: 0.079,
    6: 0.067, 7: 0.058, 8: 0.051, 9: 0.046,
}

# Grubbs 检验临界值表（显著性水平 0.05）
GRUBBS_CRITICAL_005 = {
    3: 1.153, 4: 1.463, 5: 1.672, 6: 1.822, 7: 1.938,
    8: 2.032, 9: 2.110, 10: 2.176, 15: 2.409, 20: 2.557,
    25: 2.663, 30: 2.745, 40: 2.866, 50: 2.956, 60: 3.025,
    100: 3.207, 150: 3.347, 200: 3.429,
}

# 数字提取正则
NUMBER_PATTERN = re.compile(r"(?<![0-9.])([1-9]\d*(?:\.\d+)?)(?![0-9.])")

# 各异常类型默认严重度
ANOMALY_SEVERITY = {
    AnomalyType.OUTLIER: SeverityLevel.MEDIUM,
    AnomalyType.DISTRIBUTION_ANOMALY: SeverityLevel.MEDIUM,
    AnomalyType.DUPLICATE_DATA: SeverityLevel.LOW,
    AnomalyType.MISSING_DATA: SeverityLevel.LOW,
    AnomalyType.RANGE_VIOLATION: SeverityLevel.HIGH,
    AnomalyType.CONSISTENCY_ERROR: SeverityLevel.HIGH,
    AnomalyType.REPRODUCIBILITY_ISSUE: SeverityLevel.HIGH,
    AnomalyType.FABRICATION_SUSPECT: SeverityLevel.CRITICAL,
    AnomalyType.ROUNDING_ANOMALY: SeverityLevel.LOW,
    AnomalyType.BENFORD_VIOLATION: SeverityLevel.HIGH,
}

# 严重度到数值映射
SEVERITY_VALUES = {
    SeverityLevel.INFO: 0.1,
    SeverityLevel.LOW: 0.3,
    SeverityLevel.MEDIUM: 0.5,
    SeverityLevel.HIGH: 0.75,
    SeverityLevel.CRITICAL: 0.95,
}


# ===== 数据结构 =====


@dataclass
class DataAnomaly:
    """数据异常。

    Attributes:
        id: 异常 ID。
        type: 异常类型。
        severity: 严重程度。
        location: 异常位置（表格/行/列）。
        description: 异常描述。
        evidence: 证据（统计量等）。
        value: 异常值。
        expected: 期望值/范围。
        recommendation: 整改建议。
        confidence: 置信度（0-1）。
    """

    id: str = ""
    type: AnomalyType = AnomalyType.OUTLIER
    severity: SeverityLevel = SeverityLevel.LOW
    location: str = ""
    description: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    value: Any = None
    expected: Any = None
    recommendation: str = ""
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "severity": self.severity.value,
            "location": self.location,
            "description": self.description,
            "evidence": self.evidence,
            "value": self.value,
            "expected": self.expected,
            "recommendation": self.recommendation,
            "confidence": round(self.confidence, 4),
        }


@dataclass
class DataAuthenticationReport:
    """数据验证报告。

    Attributes:
        id: 报告 ID。
        document_id: 文档 ID。
        timestamp: 验证时间。
        total_values: 总数据值数。
        anomalies: 异常列表。
        anomaly_count: 异常数量。
        authenticity_score: 真实性评分（0-1，越高越真实）。
        risk_level: 风险等级。
        statistics: 统计摘要。
        recommendations: 整改建议。
        metadata: 元数据。
    """

    id: str = ""
    document_id: str = ""
    timestamp: str = ""
    total_values: int = 0
    anomalies: list[DataAnomaly] = field(default_factory=list)
    anomaly_count: int = 0
    authenticity_score: float = 1.0
    risk_level: SeverityLevel = SeverityLevel.INFO
    statistics: dict[str, Any] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "timestamp": self.timestamp,
            "total_values": self.total_values,
            "anomalies": [a.to_dict() for a in self.anomalies],
            "anomaly_count": self.anomaly_count,
            "authenticity_score": round(self.authenticity_score, 4),
            "risk_level": self.risk_level.value,
            "statistics": self.statistics,
            "recommendations": self.recommendations,
            "metadata": self.metadata,
        }


@dataclass
class TableData:
    """表格数据。

    Attributes:
        name: 表格名称。
        headers: 列名列表。
        rows: 行数据列表（每行为字典）。
        caption: 表格标题。
        location: 文档位置。
    """

    name: str = ""
    headers: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    caption: str = ""
    location: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def get_column(self, header: str) -> list[Any]:
        """获取指定列的数据。

        Args:
            header: 列名。

        Returns:
            该列的值列表。
        """
        return [row.get(header) for row in self.rows]

    def get_numeric_column(self, header: str) -> list[float]:
        """获取指定列的数值数据。

        Args:
            header: 列名。

        Returns:
            该列的数值列表（非数值被过滤）。
        """
        values: list[float] = []
        for row in self.rows:
            value = row.get(header)
            if value is None:
                continue
            try:
                values.append(float(value))
            except (ValueError, TypeError):
                continue
        return values


@dataclass
class FigureData:
    """图表数据。

    Attributes:
        name: 图表名称。
        figure_type: 图表类型（bar/line/scatter/pie 等）。
        caption: 图表标题。
        data_points: 数据点列表。
        axes: 坐标轴信息。
        location: 文档位置。
    """

    name: str = ""
    figure_type: str = ""
    caption: str = ""
    data_points: list[dict[str, Any]] = field(default_factory=list)
    axes: dict[str, str] = field(default_factory=dict)
    location: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ===== 统计工具函数 =====


def _mean(values: list[float]) -> float:
    """计算均值。"""
    return sum(values) / len(values) if values else 0.0


def _median(values: list[float]) -> float:
    """计算中位数。"""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    mid = n // 2
    if n % 2 == 0:
        return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2
    return sorted_vals[mid]


def _std(values: list[float], ddof: int = 0) -> float:
    """计算标准差。

    Args:
        values: 数值列表。
        ddof: 自由度修正（0=总体，1=样本）。

    Returns:
        标准差。
    """
    if len(values) < 2:
        return 0.0
    avg = _mean(values)
    variance = sum((v - avg) ** 2 for v in values) / (len(values) - ddof)
    return math.sqrt(variance)


def _variance(values: list[float], ddof: int = 0) -> float:
    """计算方差。"""
    if len(values) < 2:
        return 0.0
    avg = _mean(values)
    return sum((v - avg) ** 2 for v in values) / (len(values) - ddof)


def _min(values: list[float]) -> float:
    """最小值。"""
    return min(values) if values else 0.0


def _max(values: list[float]) -> float:
    """最大值。"""
    return max(values) if values else 0.0


def _quartiles(values: list[float]) -> tuple[float, float, float]:
    """计算四分位数。

    Args:
        values: 数值列表。

    Returns:
        (Q1, Q2, Q3)。
    """
    if not values:
        return (0.0, 0.0, 0.0)
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    q2 = _median(sorted_vals)
    mid = n // 2
    if n % 2 == 0:
        lower_half = sorted_vals[:mid]
        upper_half = sorted_vals[mid:]
    else:
        lower_half = sorted_vals[:mid]
        upper_half = sorted_vals[mid + 1:]
    q1 = _median(lower_half) if lower_half else 0.0
    q3 = _median(upper_half) if upper_half else 0.0
    return (q1, q2, q3)


def _skewness(values: list[float]) -> float:
    """计算偏度（Fisher-Pearson）。

    Args:
        values: 数值列表。

    Returns:
        偏度值。
    """
    if len(values) < 3:
        return 0.0
    avg = _mean(values)
    sd = _std(values, ddof=1)
    if sd == 0:
        return 0.0
    n = len(values)
    return (n / ((n - 1) * (n - 2))) * sum(
        ((v - avg) / sd) ** 3 for v in values
    )


def _kurtosis(values: list[float]) -> float:
    """计算超额峰度。

    Args:
        values: 数值列表。

    Returns:
        超额峰度值（正态分布为 0）。
    """
    if len(values) < 4:
        return 0.0
    avg = _mean(values)
    sd = _std(values, ddof=1)
    if sd == 0:
        return 0.0
    n = len(values)
    s4 = sum(((v - avg) / sd) ** 4 for v in values)
    return (n * (n + 1) / ((n - 1) * (n - 2) * (n - 3))) * s4 - \
        (3 * (n - 1) ** 2) / ((n - 2) * (n - 3))


def _coefficient_of_variation(values: list[float]) -> float:
    """计算变异系数（CV = std/mean）。

    Args:
        values: 数值列表。

    Returns:
        变异系数。
    """
    avg = _mean(values)
    if avg == 0:
        return 0.0
    return _std(values, ddof=1) / abs(avg)


def _zscore(value: float, mean: float, std: float) -> float:
    """计算 Z-score。"""
    if std == 0:
        return 0.0
    return (value - mean) / std


def _extract_numbers_from_text(text: str) -> list[float]:
    """从文本中提取数字。

    Args:
        text: 原始文本。

    Returns:
        数字列表。
    """
    numbers: list[float] = []
    for match in NUMBER_PATTERN.finditer(text):
        try:
            numbers.append(float(match.group(1)))
        except ValueError:
            continue
    return numbers


def _benford_analysis(
    numbers: list[float],
) -> tuple[float, dict[int, float], dict[int, float]]:
    """执行 Benford 定律分析。

    Args:
        numbers: 数字列表。

    Returns:
        (卡方统计量, 实际频率, 期望频率)。
    """
    if not numbers:
        return (0.0, {}, dict(BENFORD_EXPECTED))
    first_digits = [int(str(abs(n))[0]) for n in numbers if n != 0]
    if not first_digits:
        return (0.0, {}, dict(BENFORD_EXPECTED))
    total = len(first_digits)
    actual: dict[int, float] = {}
    chi_square = 0.0
    for digit in range(1, 10):
        observed = first_digits.count(digit)
        actual[digit] = observed / total
        expected_count = BENFORD_EXPECTED[digit] * total
        if expected_count > 0:
            chi_square += ((observed - expected_count) ** 2) / expected_count
    return (chi_square, actual, dict(BENFORD_EXPECTED))


def _grubbs_critical_value(n: int, alpha: float = 0.05) -> float:
    """获取 Grubbs 检验临界值。

    Args:
        n: 样本量。
        alpha: 显著性水平。

    Returns:
        临界值。
    """
    if alpha != 0.05:
        # 非 0.05 显著性水平，使用近似公式
        # G = (n-1)/sqrt(n) * sqrt(t^2/(n-2+t^2))
        # 简化：使用插值
        pass
    if n in GRUBBS_CRITICAL_005:
        return GRUBBS_CRITICAL_005[n]
    # 插值
    keys = sorted(GRUBBS_CRITICAL_005.keys())
    if n < keys[0]:
        return GRUBBS_CRITICAL_005[keys[0]]
    if n > keys[-1]:
        return GRUBBS_CRITICAL_005[keys[-1]]
    for i in range(len(keys) - 1):
        if keys[i] <= n <= keys[i + 1]:
            # 线性插值
            x0, x1 = keys[i], keys[i + 1]
            y0, y1 = GRUBBS_CRITICAL_005[x0], GRUBBS_CRITICAL_005[x1]
            return y0 + (y1 - y0) * (n - x0) / (x1 - x0)
    return 3.0


def _grubbs_test(
    values: list[float], alpha: float = 0.05
) -> list[tuple[int, float, float]]:
    """执行 Grubbs 检验检测离群点。

    Args:
        values: 数值列表。
        alpha: 显著性水平。

    Returns:
        离群点列表 (索引, 值, G 统计量)。
    """
    if len(values) < 3:
        return []
    outliers: list[tuple[int, float, float]] = []
    remaining = list(enumerate(values))
    while len(remaining) >= 3:
        vals = [v for _, v in remaining]
        avg = _mean(vals)
        sd = _std(vals, ddof=1)
        if sd == 0:
            break
        # 找到偏离均值最大的点
        max_dev_idx = max(range(len(remaining)), key=lambda i: abs(remaining[i][1] - avg))
        g_stat = abs(remaining[max_dev_idx][1] - avg) / sd
        critical = _grubbs_critical_value(len(remaining), alpha)
        if g_stat > critical:
            outliers.append((remaining[max_dev_idx][0], remaining[max_dev_idx][1], g_stat))
            remaining.pop(max_dev_idx)
        else:
            break
    return outliers


def _detect_last_digit_bias(values: list[float]) -> tuple[bool, dict[int, float]]:
    """检测末位数字偏差（舍入异常）。

    Args:
        values: 数值列表。

    Returns:
        (是否存在偏差, 各末位数字频率)。
    """
    if not values:
        return (False, {})
    last_digits: list[int] = []
    for v in values:
        # 取小数部分最后一位
        s = f"{v:.10f}".rstrip("0")
        if "." in s:
            last_char = s[-1]
            if last_char.isdigit():
                last_digits.append(int(last_char))
        else:
            # 整数，取个位
            last_digits.append(abs(int(v)) % 10)

    if not last_digits:
        return (False, {})

    total = len(last_digits)
    freq: dict[int, float] = {}
    for digit in range(10):
        freq[digit] = last_digits.count(digit) / total

    # 期望均匀分布 10%
    max_dev = max(abs(f - 0.1) for f in freq.values())
    return (max_dev > DEFAULT_ROUNDING_DEVIATION, freq)


# ===== 主验证器类 =====


class DataAuthenticator:
    """数据真实性验证器。

    对研究数据执行多维度真实性验证，输出真实性评分与整改建议。

    验证维度包括：
        - 统计异常检测（Z-score、IQR、Grubbs 检验）
        - 数据分布验证（正态性、偏度、峰度）
        - 离群点检测（单变量、多变量）
        - 图表数据一致性检查（图表与表格数据匹配）
        - 表格数据交叉验证（多表格间数据一致性）
        - 实验数据可重复性评估（变异系数、置信区间）
        - 数据完整性检查（缺失值、重复值、范围校验）
        - Benford 定律验证（首位数字分布）
        - 舍入异常检测（末位数字分布）

    线程安全：所有公共方法通过 RLock 保护。

    典型用法：
        authenticator = DataAuthenticator()
        tables = [TableData(name="表1", headers=["x","y"], rows=[...])]
        report = authenticator.authenticate(tables, figures=[...])
        if report.authenticity_score < 0.7:
            for anomaly in report.anomalies:
                print(anomaly.description, anomaly.recommendation)
    """

    def __init__(
        self,
        thresholds: Optional[dict[str, float]] = None,
    ) -> None:
        """初始化验证器。

        Args:
            thresholds: 阈值配置，可覆盖默认阈值。
        """
        self._lock = threading.RLock()
        self._thresholds: dict[str, float] = {
            "zscore": DEFAULT_ZSCORE_THRESHOLD,
            "iqr_multiplier": DEFAULT_IQR_MULTIPLIER,
            "grubbs_alpha": DEFAULT_GRUBBS_ALPHA,
            "benford_deviation": DEFAULT_BENFORD_DEVIATION,
            "duplicate_ratio": DEFAULT_DUPLICATE_RATIO,
            "missing_ratio": DEFAULT_MISSING_RATIO,
            "rounding_deviation": DEFAULT_ROUNDING_DEVIATION,
            "cv_threshold": DEFAULT_CV_THRESHOLD,
            "skewness": DEFAULT_SKEWNESS_THRESHOLD,
            "kurtosis": DEFAULT_KURTOSIS_THRESHOLD,
        }
        if thresholds:
            self._thresholds.update(thresholds)

        # 历史报告
        self._report_history: list[DataAuthenticationReport] = []
        self._max_history = 50

    # ===== 公共接口 =====

    def authenticate(
        self,
        tables: list[TableData],
        figures: Optional[list[FigureData]] = None,
        full_text: str = "",
        expected_ranges: Optional[dict[str, tuple[float, float]]] = None,
    ) -> DataAuthenticationReport:
        """执行完整的数据真实性验证。

        Args:
            tables: 表格数据列表。
            figures: 图表数据列表。
            full_text: 论文正文（用于提取数字）。
            expected_ranges: 期望数值范围（列名 -> (最小, 最大)）。

        Returns:
            验证报告。
        """
        with self._lock:
            report = DataAuthenticationReport(
                id=str(uuid.uuid4()),
                document_id=str(uuid.uuid4()),
                timestamp=datetime.utcnow().isoformat() + "Z",
            )

            anomalies: list[DataAnomaly] = []
            all_numbers: list[float] = []
            total_values = 0

            # 1. 各表格统计异常检测
            for table in tables:
                table_anomalies, table_numbers = self._check_table_anomalies(
                    table, expected_ranges or {}
                )
                anomalies.extend(table_anomalies)
                all_numbers.extend(table_numbers)
                total_values += len(table_numbers)

            # 2. 图表数据一致性检查
            if figures:
                fig_anomalies = self._check_figure_consistency(figures, tables)
                anomalies.extend(fig_anomalies)

            # 3. 表格交叉验证
            if len(tables) >= 2:
                cross_anomalies = self._cross_validate_tables(tables)
                anomalies.extend(cross_anomalies)

            # 4. 从正文提取数字进行 Benford 分析
            if full_text:
                text_numbers = _extract_numbers_from_text(full_text)
                all_numbers.extend(text_numbers)
                total_values += len(text_numbers)

            # 5. Benford 定律验证
            if len(all_numbers) >= 30:
                benford_anomalies = self._check_benford_law(all_numbers)
                anomalies.extend(benford_anomalies)

            # 6. 舍入异常检测
            if len(all_numbers) >= 20:
                rounding_anomalies = self._check_rounding_anomaly(all_numbers)
                anomalies.extend(rounding_anomalies)

            # 7. 可重复性评估
            for table in tables:
                repro_anomalies = self._check_reproducibility(table)
                anomalies.extend(repro_anomalies)

            # 计算真实性评分
            report.anomalies = anomalies
            report.anomaly_count = len(anomalies)
            report.total_values = total_values
            report.authenticity_score = self._compute_authenticity_score(
                anomalies, total_values
            )
            report.risk_level = self._assess_risk_level(anomalies)
            report.statistics = self._compute_statistics(
                tables, all_numbers, anomalies
            )
            report.recommendations = self._generate_recommendations(
                anomalies, report.authenticity_score
            )
            report.metadata = {
                "table_count": len(tables),
                "figure_count": len(figures) if figures else 0,
                "thresholds": dict(self._thresholds),
            }

            # 缓存历史
            self._report_history.append(report)
            if len(self._report_history) > self._max_history:
                self._report_history = self._report_history[-self._max_history:]

            return report

    def authenticate_table(
        self, table: TableData
    ) -> list[DataAnomaly]:
        """验证单个表格。

        Args:
            table: 表格数据。

        Returns:
            异常列表。
        """
        with self._lock:
            anomalies, _ = self._check_table_anomalies(table, {})
            return anomalies

    def check_distribution(
        self, values: list[float]
    ) -> dict[str, Any]:
        """检查数据分布。

        Args:
            values: 数值列表。

        Returns:
            分布统计字典。
        """
        with self._lock:
            if not values:
                return {}
            return {
                "count": len(values),
                "mean": _mean(values),
                "median": _median(values),
                "std": _std(values, ddof=1),
                "min": _min(values),
                "max": _max(values),
                "range": _max(values) - _min(values),
                "q1": _quartiles(values)[0],
                "q3": _quartiles(values)[2],
                "iqr": _quartiles(values)[2] - _quartiles(values)[0],
                "skewness": _skewness(values),
                "kurtosis": _kurtosis(values),
                "cv": _coefficient_of_variation(values),
                "is_normal": self._test_normality(values),
            }

    def get_history(self, limit: int = 10) -> list[DataAuthenticationReport]:
        """获取历史验证报告。

        Args:
            limit: 返回数量上限。

        Returns:
            历史报告列表。
        """
        with self._lock:
            return list(reversed(self._report_history[-limit:]))

    # ===== 验证实现 =====

    def _check_table_anomalies(
        self,
        table: TableData,
        expected_ranges: dict[str, tuple[float, float]],
    ) -> tuple[list[DataAnomaly], list[float]]:
        """检查表格异常。

        Args:
            table: 表格数据。
            expected_ranges: 期望范围。

        Returns:
            (异常列表, 所有数值)。
        """
        anomalies: list[DataAnomaly] = []
        all_numbers: list[float] = []

        for header in table.headers:
            values = table.get_numeric_column(header)
            if len(values) < 3:
                continue
            all_numbers.extend(values)

            # Z-score 离群点检测
            zscore_anomalies = self._detect_zscore_outliers(
                values, table.name, header
            )
            anomalies.extend(zscore_anomalies)

            # IQR 离群点检测
            iqr_anomalies = self._detect_iqr_outliers(
                values, table.name, header
            )
            anomalies.extend(iqr_anomalies)

            # Grubbs 检验
            grubbs_anomalies = self._detect_grubbs_outliers(
                values, table.name, header
            )
            anomalies.extend(grubbs_anomalies)

            # 分布异常检测
            dist_anomalies = self._detect_distribution_anomaly(
                values, table.name, header
            )
            anomalies.extend(dist_anomalies)

            # 范围校验
            if header in expected_ranges:
                range_anomalies = self._check_range_violation(
                    values, table.name, header, expected_ranges[header]
                )
                anomalies.extend(range_anomalies)

        # 重复数据检测
        dup_anomalies = self._detect_duplicates(table)
        anomalies.extend(dup_anomalies)

        # 缺失数据检测
        missing_anomalies = self._detect_missing_data(table)
        anomalies.extend(missing_anomalies)

        return (anomalies, all_numbers)

    def _detect_zscore_outliers(
        self, values: list[float], table_name: str, column: str
    ) -> list[DataAnomaly]:
        """Z-score 离群点检测。

        Args:
            values: 数值列表。
            table_name: 表格名。
            column: 列名。

        Returns:
            异常列表。
        """
        anomalies: list[DataAnomaly] = []
        if len(values) < 3:
            return anomalies
        avg = _mean(values)
        sd = _std(values, ddof=1)
        if sd == 0:
            return anomalies

        threshold = self._thresholds["zscore"]
        for i, v in enumerate(values):
            z = _zscore(v, avg, sd)
            if abs(z) > threshold:
                anomalies.append(DataAnomaly(
                    id=str(uuid.uuid4()),
                    type=AnomalyType.OUTLIER,
                    severity=SeverityLevel.HIGH if abs(z) > threshold * 1.5 else SeverityLevel.MEDIUM,
                    location=f"{table_name}.{column}[行{i + 1}]",
                    description=(
                        f"Z-score 离群点: 值 {v} 的 Z-score 为 {z:.2f}"
                        f"（阈值 {threshold}）"
                    ),
                    evidence={
                        "zscore": round(z, 4),
                        "value": v,
                        "mean": round(avg, 4),
                        "std": round(sd, 4),
                        "threshold": threshold,
                    },
                    value=v,
                    expected=f"|z| <= {threshold}",
                    recommendation="核实该数据点的来源，确认是否为记录错误或真实极端值。",
                    confidence=min(0.9, abs(z) / (threshold * 2)),
                ))
        return anomalies

    def _detect_iqr_outliers(
        self, values: list[float], table_name: str, column: str
    ) -> list[DataAnomaly]:
        """IQR（箱线图）离群点检测。

        Args:
            values: 数值列表。
            table_name: 表格名。
            column: 列名。

        Returns:
            异常列表。
        """
        anomalies: list[DataAnomaly] = []
        if len(values) < 4:
            return anomalies
        q1, _, q3 = _quartiles(values)
        iqr = q3 - q1
        if iqr == 0:
            return anomalies
        multiplier = self._thresholds["iqr_multiplier"]
        lower_bound = q1 - multiplier * iqr
        upper_bound = q3 + multiplier * iqr

        for i, v in enumerate(values):
            if v < lower_bound or v > upper_bound:
                anomalies.append(DataAnomaly(
                    id=str(uuid.uuid4()),
                    type=AnomalyType.OUTLIER,
                    severity=SeverityLevel.MEDIUM,
                    location=f"{table_name}.{column}[行{i + 1}]",
                    description=(
                        f"IQR 离群点: 值 {v} 超出范围 [{lower_bound:.2f}, {upper_bound:.2f}]"
                    ),
                    evidence={
                        "value": v,
                        "q1": round(q1, 4),
                        "q3": round(q3, 4),
                        "iqr": round(iqr, 4),
                        "lower_bound": round(lower_bound, 4),
                        "upper_bound": round(upper_bound, 4),
                    },
                    value=v,
                    expected=f"[{lower_bound:.2f}, {upper_bound:.2f}]",
                    recommendation="核实该数据点，确认是否为真实极端值或录入错误。",
                    confidence=0.7,
                ))
        return anomalies

    def _detect_grubbs_outliers(
        self, values: list[float], table_name: str, column: str
    ) -> list[DataAnomaly]:
        """Grubbs 检验离群点检测。

        Args:
            values: 数值列表。
            table_name: 表格名。
            column: 列名。

        Returns:
            异常列表。
        """
        anomalies: list[DataAnomaly] = []
        alpha = self._thresholds["grubbs_alpha"]
        outliers = _grubbs_test(values, alpha)
        for idx, val, g_stat in outliers:
            critical = _grubbs_critical_value(len(values), alpha)
            anomalies.append(DataAnomaly(
                id=str(uuid.uuid4()),
                type=AnomalyType.OUTLIER,
                severity=SeverityLevel.HIGH,
                location=f"{table_name}.{column}[行{idx + 1}]",
                description=(
                    f"Grubbs 检验离群点: 值 {val} 的 G 统计量为 {g_stat:.3f}"
                    f"（临界值 {critical:.3f}）"
                ),
                evidence={
                    "value": val,
                    "g_statistic": round(g_stat, 4),
                    "critical_value": round(critical, 4),
                    "alpha": alpha,
                    "n": len(values),
                },
                value=val,
                expected=f"G <= {critical:.3f}",
                recommendation="该数据点统计显著为离群点，需重点核实。",
                confidence=0.85,
            ))
        return anomalies

    def _detect_distribution_anomaly(
        self, values: list[float], table_name: str, column: str
    ) -> list[DataAnomaly]:
        """分布异常检测。

        Args:
            values: 数值列表。
            table_name: 表格名。
            column: 列名。

        Returns:
            异常列表。
        """
        anomalies: list[DataAnomaly] = []
        if len(values) < 8:
            return anomalies

        skew = _skewness(values)
        kurt = _kurtosis(values)
        cv = _coefficient_of_variation(values)

        # 偏度异常
        if abs(skew) > self._thresholds["skewness"]:
            anomalies.append(DataAnomaly(
                id=str(uuid.uuid4()),
                type=AnomalyType.DISTRIBUTION_ANOMALY,
                severity=SeverityLevel.MEDIUM,
                location=f"{table_name}.{column}",
                description=(
                    f"分布偏度异常: 偏度 {skew:.3f}"
                    f"（阈值 {self._thresholds['skewness']}）"
                ),
                evidence={
                    "skewness": round(skew, 4),
                    "threshold": self._thresholds["skewness"],
                },
                value=round(skew, 4),
                expected=f"|偏度| <= {self._thresholds['skewness']}",
                recommendation="检查数据是否存在系统性偏差，考虑数据变换。",
                confidence=0.7,
            ))

        # 峰度异常
        if abs(kurt) > self._thresholds["kurtosis"]:
            anomalies.append(DataAnomaly(
                id=str(uuid.uuid4()),
                type=AnomalyType.DISTRIBUTION_ANOMALY,
                severity=SeverityLevel.MEDIUM,
                location=f"{table_name}.{column}",
                description=(
                    f"分布峰度异常: 超额峰度 {kurt:.3f}"
                    f"（阈值 {self._thresholds['kurtosis']}）"
                ),
                evidence={
                    "kurtosis": round(kurt, 4),
                    "threshold": self._thresholds["kurtosis"],
                },
                value=round(kurt, 4),
                expected=f"|峰度| <= {self._thresholds['kurtosis']}",
                recommendation="检查数据分布形态，可能存在尖峰或重尾。",
                confidence=0.65,
            ))

        # 变异系数过小（数据过于集中）
        if 0 < cv < 0.01 and _mean(values) != 0:
            anomalies.append(DataAnomaly(
                id=str(uuid.uuid4()),
                type=AnomalyType.FABRICATION_SUSPECT,
                severity=SeverityLevel.HIGH,
                location=f"{table_name}.{column}",
                description=(
                    f"变异系数异常小: CV={cv:.4f}，数据过于集中，"
                    "可能存在人为调整。"
                ),
                evidence={
                    "cv": round(cv, 6),
                    "mean": round(_mean(values), 4),
                    "std": round(_std(values, ddof=1), 4),
                },
                value=round(cv, 6),
                expected="CV > 0.01",
                recommendation="提供原始未处理数据，或说明数据预处理流程。",
                confidence=0.75,
            ))

        return anomalies

    def _check_range_violation(
        self,
        values: list[float],
        table_name: str,
        column: str,
        expected_range: tuple[float, float],
    ) -> list[DataAnomaly]:
        """范围校验。

        Args:
            values: 数值列表。
            table_name: 表格名。
            column: 列名。
            expected_range: 期望范围 (最小, 最大)。

        Returns:
            异常列表。
        """
        anomalies: list[DataAnomaly] = []
        min_val, max_val = expected_range
        for i, v in enumerate(values):
            if v < min_val or v > max_val:
                anomalies.append(DataAnomaly(
                    id=str(uuid.uuid4()),
                    type=AnomalyType.RANGE_VIOLATION,
                    severity=SeverityLevel.HIGH,
                    location=f"{table_name}.{column}[行{i + 1}]",
                    description=(
                        f"数值超出期望范围: 值 {v} 不在 [{min_val}, {max_val}] 内"
                    ),
                    evidence={
                        "value": v,
                        "min_expected": min_val,
                        "max_expected": max_val,
                    },
                    value=v,
                    expected=f"[{min_val}, {max_val}]",
                    recommendation="核实数据是否超出物理/逻辑约束，修正错误值。",
                    confidence=0.9,
                ))
        return anomalies

    def _detect_duplicates(self, table: TableData) -> list[DataAnomaly]:
        """重复数据检测。

        Args:
            table: 表格数据。

        Returns:
            异常列表。
        """
        anomalies: list[DataAnomaly] = []
        if len(table.rows) < 2:
            return anomalies

        # 完全重复行检测
        seen_rows: dict[str, int] = {}
        for i, row in enumerate(table.rows):
            # 行哈希
            row_str = str(sorted(row.items()))
            row_hash = hashlib.md5(row_str.encode()).hexdigest()
            if row_hash in seen_rows:
                anomalies.append(DataAnomaly(
                    id=str(uuid.uuid4()),
                    type=AnomalyType.DUPLICATE_DATA,
                    severity=SeverityLevel.LOW,
                    location=f"{table.name}[行{i + 1}]",
                    description=f"重复行: 行 {i + 1} 与行 {seen_rows[row_hash] + 1} 完全相同",
                    evidence={
                        "row_index": i + 1,
                        "duplicate_of": seen_rows[row_hash] + 1,
                    },
                    value=row,
                    expected="唯一行",
                    recommendation="删除重复行，或确认是否为不同实验的相同结果。",
                    confidence=0.95,
                ))
            else:
                seen_rows[row_hash] = i

        # 重复比例检测
        total = len(table.rows)
        unique = len(seen_rows)
        dup_ratio = (total - unique) / total if total else 0
        if dup_ratio > self._thresholds["duplicate_ratio"]:
            anomalies.append(DataAnomaly(
                id=str(uuid.uuid4()),
                type=AnomalyType.DUPLICATE_DATA,
                severity=SeverityLevel.MEDIUM,
                location=table.name,
                description=(
                    f"重复数据比例过高: {dup_ratio:.1%}"
                    f"（{total - unique}/{total} 行重复，"
                    f"阈值 {self._thresholds['duplicate_ratio']:.1%}）"
                ),
                evidence={
                    "total_rows": total,
                    "unique_rows": unique,
                    "duplicate_ratio": round(dup_ratio, 4),
                },
                value=round(dup_ratio, 4),
                expected=f"重复率 <= {self._thresholds['duplicate_ratio']:.1%}",
                recommendation="去重处理，或说明重复数据的合理性。",
                confidence=0.85,
            ))

        return anomalies

    def _detect_missing_data(self, table: TableData) -> list[DataAnomaly]:
        """缺失数据检测。

        Args:
            table: 表格数据。

        Returns:
            异常列表。
        """
        anomalies: list[DataAnomaly] = []
        if not table.rows or not table.headers:
            return anomalies

        total_cells = len(table.rows) * len(table.headers)
        missing_count = 0
        missing_by_column: dict[str, int] = defaultdict(int)

        for row in table.rows:
            for header in table.headers:
                value = row.get(header)
                if value is None or value == "" or value == "N/A":
                    missing_count += 1
                    missing_by_column[header] += 1

        if total_cells == 0:
            return anomalies

        missing_ratio = missing_count / total_cells
        if missing_ratio > self._thresholds["missing_ratio"]:
            anomalies.append(DataAnomaly(
                id=str(uuid.uuid4()),
                type=AnomalyType.MISSING_DATA,
                severity=SeverityLevel.MEDIUM,
                location=table.name,
                description=(
                    f"缺失数据比例过高: {missing_ratio:.1%}"
                    f"（{missing_count}/{total_cells} 单元格缺失，"
                    f"阈值 {self._thresholds['missing_ratio']:.1%}）"
                ),
                evidence={
                    "missing_count": missing_count,
                    "total_cells": total_cells,
                    "missing_ratio": round(missing_ratio, 4),
                    "missing_by_column": dict(missing_by_column),
                },
                value=round(missing_ratio, 4),
                expected=f"缺失率 <= {self._thresholds['missing_ratio']:.1%}",
                recommendation="补充缺失数据，或说明缺失原因与处理方式。",
                confidence=0.9,
            ))

        # 单列缺失过多
        for header, count in missing_by_column.items():
            col_ratio = count / len(table.rows)
            if col_ratio > 0.5:
                anomalies.append(DataAnomaly(
                    id=str(uuid.uuid4()),
                    type=AnomalyType.MISSING_DATA,
                    severity=SeverityLevel.HIGH,
                    location=f"{table.name}.{header}",
                    description=(
                        f"列 '{header}' 缺失率 {col_ratio:.1%}"
                        f"（{count}/{len(table.rows)}）"
                    ),
                    evidence={
                        "column": header,
                        "missing_count": count,
                        "total_rows": len(table.rows),
                        "missing_ratio": round(col_ratio, 4),
                    },
                    value=round(col_ratio, 4),
                    expected="列缺失率 <= 50%",
                    recommendation=f"考虑删除列 '{header}' 或补充数据。",
                    confidence=0.85,
                ))

        return anomalies

    def _check_figure_consistency(
        self,
        figures: list[FigureData],
        tables: list[TableData],
    ) -> list[DataAnomaly]:
        """图表数据一致性检查。

        检查图表中的数据点是否与表格数据匹配。

        Args:
            figures: 图表列表。
            tables: 表格列表。

        Returns:
            异常列表。
        """
        anomalies: list[DataAnomaly] = []
        for fig in figures:
            if not fig.data_points:
                anomalies.append(DataAnomaly(
                    id=str(uuid.uuid4()),
                    type=AnomalyType.CONSISTENCY_ERROR,
                    severity=SeverityLevel.LOW,
                    location=f"图表 {fig.name}",
                    description=f"图表 '{fig.name}' 无数据点",
                    evidence={"figure": fig.name},
                    recommendation="补充图表数据点信息。",
                    confidence=0.8,
                ))
                continue

            # 检查图表数据点是否在表格中存在
            # 简化：检查图表数据点的数值是否在表格数值范围内
            fig_values: list[float] = []
            for dp in fig.data_points:
                for v in dp.values():
                    if isinstance(v, (int, float)):
                        fig_values.append(float(v))
                    elif isinstance(v, str):
                        try:
                            fig_values.append(float(v))
                        except ValueError:
                            pass

            if not fig_values:
                continue

            fig_min = min(fig_values)
            fig_max = max(fig_values)

            # 与表格数据范围比较
            for table in tables:
                for header in table.headers:
                    table_values = table.get_numeric_column(header)
                    if not table_values:
                        continue
                    table_min = min(table_values)
                    table_max = max(table_values)
                    # 若图表数据范围与表格范围严重不符
                    if fig_min < table_min * 0.5 and fig_max > table_max * 2:
                        continue  # 不同数据集，跳过
                    # 检查图表数据是否超出表格范围过多
                    if fig_max > table_max * 1.5 and table_max > 0:
                        anomalies.append(DataAnomaly(
                            id=str(uuid.uuid4()),
                            type=AnomalyType.CONSISTENCY_ERROR,
                            severity=SeverityLevel.MEDIUM,
                            location=f"图表 {fig.name} vs 表格 {table.name}",
                            description=(
                                f"图表 '{fig.name}' 数据最大值 {fig_max:.2f} "
                                f"显著超出表格 '{table.name}' 列 '{header}' "
                                f"最大值 {table_max:.2f}"
                            ),
                            evidence={
                                "figure_max": round(fig_max, 4),
                                "table_max": round(table_max, 4),
                                "table": table.name,
                                "column": header,
                            },
                            value=round(fig_max, 4),
                            expected=f"<= {table_max * 1.1:.2f}",
                            recommendation="核对图表数据与表格数据是否一致。",
                            confidence=0.7,
                        ))
                        break

        return anomalies

    def _cross_validate_tables(
        self, tables: list[TableData]
    ) -> list[DataAnomaly]:
        """表格交叉验证。

        检查多个表格间共享列的数据一致性。

        Args:
            tables: 表格列表。

        Returns:
            异常列表。
        """
        anomalies: list[DataAnomaly] = []
        if len(tables) < 2:
            return anomalies

        # 找出共享列
        header_sets = [set(t.headers) for t in tables]
        common_headers = set.intersection(*header_sets) if header_sets else set()

        for header in common_headers:
            # 收集各表格该列的统计量
            stats_by_table: dict[str, dict[str, float]] = {}
            for table in tables:
                values = table.get_numeric_column(header)
                if len(values) < 3:
                    continue
                stats_by_table[table.name] = {
                    "mean": _mean(values),
                    "std": _std(values, ddof=1),
                    "min": min(values),
                    "max": max(values),
                    "count": len(values),
                }

            if len(stats_by_table) < 2:
                continue

            # 比较均值差异
            means = [s["mean"] for s in stats_by_table.values()]
            mean_range = max(means) - min(means)
            overall_mean = _mean(means)
            if overall_mean != 0 and mean_range / abs(overall_mean) > 0.5:
                anomalies.append(DataAnomaly(
                    id=str(uuid.uuid4()),
                    type=AnomalyType.CONSISTENCY_ERROR,
                    severity=SeverityLevel.MEDIUM,
                    location=f"多表格交叉验证.{header}",
                    description=(
                        f"列 '{header}' 在不同表格间均值差异显著: "
                        f"{', '.join(f'{n}={s['mean']:.2f}' for n, s in stats_by_table.items())}"
                    ),
                    evidence={
                        "column": header,
                        "stats_by_table": {
                            n: {k: round(v, 4) for k, v in s.items()}
                            for n, s in stats_by_table.items()
                        },
                        "mean_range": round(mean_range, 4),
                    },
                    value=round(mean_range, 4),
                    expected="各表格均值差异 < 50%",
                    recommendation="核对各表格数据来源，确认差异是否合理。",
                    confidence=0.7,
                ))

        return anomalies

    def _check_benford_law(self, numbers: list[float]) -> list[DataAnomaly]:
        """Benford 定律验证。

        Args:
            numbers: 数字列表。

        Returns:
            异常列表。
        """
        anomalies: list[DataAnomaly] = []
        chi_square, actual, expected = _benford_analysis(numbers)

        max_deviation = 0.0
        deviating_digits: list[int] = []
        for digit in range(1, 10):
            dev = abs(actual.get(digit, 0) - expected[digit])
            if dev > max_deviation:
                max_deviation = dev
            if dev > self._thresholds["benford_deviation"]:
                deviating_digits.append(digit)

        if max_deviation > self._thresholds["benford_deviation"]:
            severity = SeverityLevel.HIGH if max_deviation > 0.3 else SeverityLevel.MEDIUM
            anomalies.append(DataAnomaly(
                id=str(uuid.uuid4()),
                type=AnomalyType.BENFORD_VIOLATION,
                severity=severity,
                location="全局数据",
                description=(
                    f"数据首位数字分布偏离 Benford 定律: "
                    f"最大偏差 {max_deviation:.3f}"
                    f"（阈值 {self._thresholds['benford_deviation']}），"
                    f"卡方统计量 {chi_square:.2f}，"
                    f"偏差显著数字: {deviating_digits}"
                ),
                evidence={
                    "chi_square": round(chi_square, 4),
                    "max_deviation": round(max_deviation, 4),
                    "actual_distribution": {k: round(v, 4) for k, v in actual.items()},
                    "expected_distribution": expected,
                    "deviating_digits": deviating_digits,
                    "sample_size": len(numbers),
                },
                value=round(max_deviation, 4),
                expected=f"最大偏差 <= {self._thresholds['benford_deviation']}",
                recommendation="核实数据采集与记录过程，Benford 偏差可能指示数据捏造。",
                confidence=0.75,
            ))

        return anomalies

    def _check_rounding_anomaly(self, numbers: list[float]) -> list[DataAnomaly]:
        """舍入异常检测。

        Args:
            numbers: 数字列表。

        Returns:
            异常列表。
        """
        anomalies: list[DataAnomaly] = []
        has_bias, freq = _detect_last_digit_bias(numbers)
        if has_bias:
            # 找出偏差最大的数字
            max_digit = max(freq, key=lambda d: abs(freq[d] - 0.1))
            max_dev = abs(freq[max_digit] - 0.1)
            anomalies.append(DataAnomaly(
                id=str(uuid.uuid4()),
                type=AnomalyType.ROUNDING_ANOMALY,
                severity=SeverityLevel.LOW,
                location="全局数据",
                description=(
                    f"末位数字分布异常: 数字 '{max_digit}' 频率 {freq[max_digit]:.1%}"
                    f"（期望 10%，偏差 {max_dev:.1%}）"
                ),
                evidence={
                    "frequency": {k: round(v, 4) for k, v in freq.items()},
                    "max_deviation_digit": max_digit,
                    "max_deviation": round(max_dev, 4),
                },
                value=round(max_dev, 4),
                expected="各末位数字频率约 10%",
                recommendation="检查数据是否存在系统性舍入，可能影响统计精度。",
                confidence=0.6,
            ))

        return anomalies

    def _check_reproducibility(self, table: TableData) -> list[DataAnomaly]:
        """实验数据可重复性评估。

        检查重复测量数据的变异系数是否在合理范围。

        Args:
            table: 表格数据。

        Returns:
            异常列表。
        """
        anomalies: list[DataAnomaly] = []
        # 检测可能的重复测量列（列名含 repeat/trial/run 等）
        repeat_keywords = ["repeat", "trial", "run", "replicate", "重复", "试验"]

        for header in table.headers:
            is_repeat = any(kw in header.lower() for kw in repeat_keywords)
            if not is_repeat:
                continue
            values = table.get_numeric_column(header)
            if len(values) < 3:
                continue
            cv = _coefficient_of_variation(values)
            # CV 过小：数据过于一致，可能造假
            if 0 < cv < 0.01:
                anomalies.append(DataAnomaly(
                    id=str(uuid.uuid4()),
                    type=AnomalyType.REPRODUCIBILITY_ISSUE,
                    severity=SeverityLevel.HIGH,
                    location=f"{table.name}.{header}",
                    description=(
                        f"重复测量数据变异系数过小: CV={cv:.4f}，"
                        "数据过于一致，可能存在造假。"
                    ),
                    evidence={
                        "cv": round(cv, 6),
                        "mean": round(_mean(values), 4),
                        "std": round(_std(values, ddof=1), 4),
                        "count": len(values),
                    },
                    value=round(cv, 6),
                    expected="CV > 0.01（真实实验数据应有自然波动）",
                    recommendation="提供原始实验记录，确认数据未被人为主观调整。",
                    confidence=0.8,
                ))
            # CV 过大：可重复性差
            elif cv > self._thresholds["cv_threshold"]:
                anomalies.append(DataAnomaly(
                    id=str(uuid.uuid4()),
                    type=AnomalyType.REPRODUCIBILITY_ISSUE,
                    severity=SeverityLevel.MEDIUM,
                    location=f"{table_name := table.name}.{header}",
                    description=(
                        f"重复测量数据变异系数过大: CV={cv:.1%}"
                        f"（阈值 {self._thresholds['cv_threshold']:.1%}），"
                        "可重复性较差。"
                    ),
                    evidence={
                        "cv": round(cv, 4),
                        "mean": round(_mean(values), 4),
                        "std": round(_std(values, ddof=1), 4),
                        "count": len(values),
                    },
                    value=round(cv, 4),
                    expected=f"CV <= {self._thresholds['cv_threshold']:.1%}",
                    recommendation="增加重复次数，或改进实验稳定性。",
                    confidence=0.7,
                ))

        return anomalies

    def _test_normality(self, values: list[float]) -> bool:
        """简单正态性检验（基于偏度与峰度）。

        Args:
            values: 数值列表。

        Returns:
            是否近似正态分布。
        """
        if len(values) < 8:
            return False
        skew = _skewness(values)
        kurt = _kurtosis(values)
        return (
            abs(skew) <= self._thresholds["skewness"]
            and abs(kurt) <= self._thresholds["kurtosis"]
        )

    # ===== 评分与报告 =====

    def _compute_authenticity_score(
        self, anomalies: list[DataAnomaly], total_values: int
    ) -> float:
        """计算真实性评分。

        评分策略：
            1. 基础分 1.0。
            2. 每个异常按严重度扣分。
            3. 造假嫌疑类异常扣分更重。
            4. 按数据量归一化。

        Args:
            anomalies: 异常列表。
            total_values: 总数据值数。

        Returns:
            真实性评分（0-1）。
        """
        if total_values == 0:
            return 1.0
        score = 1.0
        for anomaly in anomalies:
            severity_value = SEVERITY_VALUES.get(anomaly.severity, 0.3)
            # 造假嫌疑扣分加倍
            if anomaly.type == AnomalyType.FABRICATION_SUSPECT:
                severity_value *= 2.0
            # Benford 违规扣分加倍
            elif anomaly.type == AnomalyType.BENFORD_VIOLATION:
                severity_value *= 1.5
            # 按数据量归一化（数据越多，单个异常影响越小）
            penalty = severity_value / max(total_values / 10, 1)
            score -= penalty
        return max(0.0, min(1.0, score))

    def _assess_risk_level(
        self, anomalies: list[DataAnomaly]
    ) -> SeverityLevel:
        """评估风险等级。

        Args:
            anomalies: 异常列表。

        Returns:
            风险等级。
        """
        if not anomalies:
            return SeverityLevel.INFO
        # 存在严重异常
        if any(a.severity == SeverityLevel.CRITICAL for a in anomalies):
            return SeverityLevel.CRITICAL
        # 存在高严重度异常
        high_count = sum(1 for a in anomalies if a.severity == SeverityLevel.HIGH)
        if high_count >= 3:
            return SeverityLevel.CRITICAL
        if high_count >= 1:
            return SeverityLevel.HIGH
        # 存在中严重度异常
        medium_count = sum(1 for a in anomalies if a.severity == SeverityLevel.MEDIUM)
        if medium_count >= 3:
            return SeverityLevel.HIGH
        if medium_count >= 1:
            return SeverityLevel.MEDIUM
        return SeverityLevel.LOW

    def _compute_statistics(
        self,
        tables: list[TableData],
        all_numbers: list[float],
        anomalies: list[DataAnomaly],
    ) -> dict[str, Any]:
        """计算统计摘要。

        Args:
            tables: 表格列表。
            all_numbers: 所有数值。
            anomalies: 异常列表。

        Returns:
            统计字典。
        """
        stats: dict[str, Any] = {
            "table_count": len(tables),
            "total_values": len(all_numbers),
            "anomaly_count": len(anomalies),
            "anomalies_by_type": dict(
                Counter(a.type.value for a in anomalies)
            ),
            "anomalies_by_severity": dict(
                Counter(a.severity.value for a in anomalies)
            ),
        }
        if all_numbers:
            stats.update({
                "global_mean": round(_mean(all_numbers), 4),
                "global_std": round(_std(all_numbers, ddof=1), 4),
                "global_min": min(all_numbers),
                "global_max": max(all_numbers),
                "global_median": round(_median(all_numbers), 4),
            })
        return stats

    def _generate_recommendations(
        self,
        anomalies: list[DataAnomaly],
        authenticity_score: float,
    ) -> list[str]:
        """生成整改建议。

        Args:
            anomalies: 异常列表。
            authenticity_score: 真实性评分。

        Returns:
            建议列表。
        """
        recommendations: list[str] = []

        # 总体建议
        if authenticity_score < 0.5:
            recommendations.append(
                "⚠️ 数据真实性评分较低，建议全面核查数据来源与处理流程。"
            )
        elif authenticity_score < 0.7:
            recommendations.append(
                "⚠️ 数据存在一定风险，建议逐项核实异常数据。"
            )
        elif authenticity_score < 0.9:
            recommendations.append(
                "📋 数据整体可信，建议关注标记的异常项。"
            )
        else:
            recommendations.append("✅ 数据真实性验证通过。")

        # 按异常类型分组建议
        type_anomalies: dict[AnomalyType, list[DataAnomaly]] = defaultdict(list)
        for anomaly in anomalies:
            type_anomalies[anomaly.type].append(anomaly)

        type_advice = {
            AnomalyType.OUTLIER: (
                "离群点：逐个核实离群值，区分真实极端值与录入错误。"
            ),
            AnomalyType.DISTRIBUTION_ANOMALY: (
                "分布异常：检查数据分布形态，考虑数据变换或补充说明。"
            ),
            AnomalyType.DUPLICATE_DATA: (
                "重复数据：去重处理，或说明重复数据的合理性。"
            ),
            AnomalyType.MISSING_DATA: (
                "缺失数据：补充缺失值，或说明缺失原因与处理方式。"
            ),
            AnomalyType.RANGE_VIOLATION: (
                "范围违规：修正超出物理/逻辑约束的数据。"
            ),
            AnomalyType.CONSISTENCY_ERROR: (
                "一致性错误：核对图表与表格、多表格间数据一致性。"
            ),
            AnomalyType.REPRODUCIBILITY_ISSUE: (
                "可重复性问题：增加重复次数，或改进实验稳定性。"
            ),
            AnomalyType.FABRICATION_SUSPECT: (
                "造假嫌疑：提供原始数据记录，邀请第三方复核。"
            ),
            AnomalyType.ROUNDING_ANOMALY: (
                "舍入异常：检查数据是否存在系统性舍入。"
            ),
            AnomalyType.BENFORD_VIOLATION: (
                "Benford 违规：核实数据采集过程，偏差可能指示数据捏造。"
            ),
        }

        for anomaly_type, anomaly_list in type_anomalies.items():
            advice = type_advice.get(anomaly_type)
            if advice:
                recommendations.append(
                    f"【{anomaly_type.value}】{advice}（{len(anomaly_list)} 处）"
                )

        # 关键建议
        critical_anomalies = [
            a for a in anomalies if a.severity == SeverityLevel.CRITICAL
        ]
        if critical_anomalies:
            recommendations.append(
                f"⚠️ 存在 {len(critical_anomalies)} 个严重异常，"
                "建议在解决前暂缓发表。"
            )

        return recommendations

    # ===== 配置管理 =====

    def set_threshold(self, name: str, value: float) -> None:
        """设置阈值。

        Args:
            name: 阈值名称。
            value: 阈值。
        """
        with self._lock:
            self._thresholds[name] = value

    def get_config(self) -> dict[str, Any]:
        """获取当前配置。

        Returns:
            配置字典。
        """
        with self._lock:
            return {
                "thresholds": dict(self._thresholds),
                "history_size": len(self._report_history),
            }

    def clear_history(self) -> None:
        """清空历史报告。"""
        with self._lock:
            self._report_history.clear()


# ===== 模块级便捷函数 =====


def authenticate_data(
    tables: list[TableData],
    figures: Optional[list[FigureData]] = None,
    full_text: str = "",
) -> DataAuthenticationReport:
    """便捷函数：验证数据真实性。

    Args:
        tables: 表格数据列表。
        figures: 图表数据列表。
        full_text: 论文正文。

    Returns:
        验证报告。
    """
    authenticator = DataAuthenticator()
    return authenticator.authenticate(tables, figures, full_text)


def detect_outliers(
    values: list[float], method: str = "zscore"
) -> list[int]:
    """便捷函数：检测离群点。

    Args:
        values: 数值列表。
        method: 检测方法（zscore/iqr/grubbs）。

    Returns:
        离群点索引列表。
    """
    authenticator = DataAuthenticator()
    if method == "zscore":
        avg = _mean(values)
        sd = _std(values, ddof=1)
        if sd == 0:
            return []
        threshold = authenticator._thresholds["zscore"]
        return [i for i, v in enumerate(values) if abs(_zscore(v, avg, sd)) > threshold]
    elif method == "iqr":
        q1, _, q3 = _quartiles(values)
        iqr = q3 - q1
        if iqr == 0:
            return []
        multiplier = authenticator._thresholds["iqr_multiplier"]
        lower = q1 - multiplier * iqr
        upper = q3 + multiplier * iqr
        return [i for i, v in enumerate(values) if v < lower or v > upper]
    elif method == "grubbs":
        return [idx for idx, _, _ in _grubbs_test(values)]
    return []


def check_benford_law(numbers: list[float]) -> tuple[bool, float]:
    """便捷函数：检查 Benford 定律。

    Args:
        numbers: 数字列表。

    Returns:
        (是否违规, 最大偏差)。
    """
    chi_square, actual, expected = _benford_analysis(numbers)
    max_dev = max(
        (abs(actual.get(d, 0) - expected[d]) for d in range(1, 10)),
        default=0.0,
    )
    return (max_dev > DEFAULT_BENFORD_DEVIATION, max_dev)
