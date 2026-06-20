"""MetricsCollector 单元测试

覆盖范围：
    - Counter / Gauge / Histogram 三种指标类型的基础行为
    - 多维度标签（labels）的校验与查询
    - 滑动窗口统计与过期样本清理
    - 百分位计算（p50 / p90 / p99）
    - Prometheus 文本格式导出
    - JSON 序列化导出
    - 时序数据存储与查询
    - 批量上报与回调
    - SQLite 持久化
    - 异步定时持久化任务
    - 线程安全（多线程并发写入）
    - 单例模式与重置
    - 延迟测量上下文管理器
    - 模块级便捷函数

运行方式：
    pytest tests/unit/test_analytics_metrics.py -v
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.analytics.metrics_collector import (
    DEFAULT_BATCH_BUFFER_SIZE,
    DEFAULT_HISTOGRAM_BUCKETS,
    DEFAULT_PERCENTILES,
    DEFAULT_WINDOW_SECONDS,
    Counter,
    Gauge,
    Histogram,
    MetricSample,
    MetricsCollector,
    TimeSeriesPoint,
    TimeSeriesStore,
    _format_labels,
    _labels_to_key,
    _quantile,
    get_metrics_collector,
    record_api_request,
    record_cache_event,
    record_llm_call,
    update_concurrent_gauge,
)


# ===== 公共夹具 =====


@pytest.fixture(autouse=True)
def reset_collector():
    """每个测试前后重置单例，保证测试间隔离。"""
    MetricsCollector.reset_instance()
    yield
    MetricsCollector.reset_instance()


@pytest.fixture
def collector():
    """返回一个全新的 MetricsCollector 实例。"""
    return MetricsCollector.get_instance()


@pytest.fixture
def tmp_db_path(tmp_path):
    """返回临时数据库路径。"""
    return str(tmp_path / "metrics_test.db")


# ===== 辅助函数测试 =====


class TestHelperFunctions:
    """模块级辅助函数测试。"""

    def test_labels_to_key_empty(self):
        """空标签应返回空字符串。"""
        assert _labels_to_key(None) == ""
        assert _labels_to_key({}) == ""

    def test_labels_to_key_sorted(self):
        """标签应按键名排序后拼接。"""
        labels = {"b": "2", "a": "1"}
        assert _labels_to_key(labels) == "a=1,b=2"

    def test_labels_to_key_multi(self):
        """多标签应按稳定顺序输出。"""
        labels = {"method": "GET", "path": "/sessions", "status": "200"}
        key = _labels_to_key(labels)
        assert key == "method=GET,path=/sessions,status=200"

    def test_format_labels_empty(self):
        """空标签格式化后应为空字符串。"""
        assert _format_labels(None) == ""
        assert _format_labels({}) == ""

    def test_format_labels_prometheus_style(self):
        """标签应格式化为 Prometheus 文本格式。"""
        result = _format_labels({"method": "GET", "path": "/sessions"})
        assert result == '{method="GET",path="/sessions"}'

    def test_format_labels_escape_special(self):
        """特殊字符（换行、引号、反斜杠）应被转义。"""
        result = _format_labels({"msg": 'a"b\\c\nd'})
        assert '\\"' in result
        assert "\\\\" in result
        assert "\\n" in result

    def test_quantile_empty_list(self):
        """空列表的分位数应为 0.0。"""
        assert _quantile([], 0.5) == 0.0

    def test_quantile_single_value(self):
        """单元素列表任意分位数应等于该元素。"""
        assert _quantile([5.0], 0.0) == 5.0
        assert _quantile([5.0], 0.5) == 5.0
        assert _quantile([5.0], 1.0) == 5.0

    def test_quantile_boundaries(self):
        """q=0 返回最小值，q=1 返回最大值。"""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert _quantile(values, 0.0) == 1.0
        assert _quantile(values, 1.0) == 5.0

    def test_quantile_linear_interpolation(self):
        """分位数应使用线性插值法。"""
        # 4 个元素 [1,2,3,4]，q=0.5 -> pos=1.5 -> 2*0.5+3*0.5=2.5
        values = [1.0, 2.0, 3.0, 4.0]
        result = _quantile(values, 0.5)
        assert result == pytest.approx(2.5)

    def test_quantile_out_of_range_clamped(self):
        """q 超出 [0,1] 应被截断到边界。"""
        values = [1.0, 2.0, 3.0]
        assert _quantile(values, -0.5) == 1.0
        assert _quantile(values, 1.5) == 3.0


# ===== Counter 测试 =====


class TestCounter:
    """Counter 指标类型测试。"""

    def test_counter_basic_inc(self):
        """Counter 基本自增。"""
        c = Counter("test_total", "测试计数器")
        c.inc()
        assert c.get() == 1.0
        c.inc(5)
        assert c.get() == 6.0

    def test_counter_inc_with_labels(self):
        """带标签的 Counter 自增。"""
        c = Counter("requests_total", "请求总数", ["method", "status"])
        c.inc(labels={"method": "GET", "status": "200"})
        c.inc(3, labels={"method": "GET", "status": "200"})
        c.inc(labels={"method": "POST", "status": "201"})
        assert c.get(labels={"method": "GET", "status": "200"}) == 4.0
        assert c.get(labels={"method": "POST", "status": "201"}) == 1.0

    def test_counter_negative_amount_raises(self):
        """Counter 不允许负增量。"""
        c = Counter("test_total")
        with pytest.raises(ValueError):
            c.inc(-1)

    def test_counter_label_mismatch_raises(self):
        """标签键不匹配应抛出 ValueError。"""
        c = Counter("test_total", "", ["method"])
        with pytest.raises(ValueError):
            c.inc(labels={"path": "/x"})
        with pytest.raises(ValueError):
            c.inc(labels={"method": "GET", "extra": "x"})

    def test_counter_get_default_zero(self):
        """未记录的标签组合应返回 0。"""
        c = Counter("test_total", "", ["method"])
        assert c.get(labels={"method": "GET"}) == 0.0

    def test_counter_get_all(self):
        """get_all 应返回所有标签组合。"""
        c = Counter("test_total", "", ["method"])
        c.inc(labels={"method": "GET"})
        c.inc(2, labels={"method": "POST"})
        all_values = c.get_all()
        assert len(all_values) == 2
        labels_values = {frozenset(l.items()): v for l, v in all_values}
        assert labels_values[frozenset({"method": "GET"}.items())] == 1.0
        assert labels_values[frozenset({"method": "POST"}.items())] == 2.0

    def test_counter_reset(self):
        """reset 应清空所有值。"""
        c = Counter("test_total")
        c.inc(10)
        c.reset()
        assert c.get() == 0.0

    def test_counter_export_prometheus(self):
        """Prometheus 导出应包含 HELP/TYPE 行与值行。"""
        c = Counter("requests_total", "请求总数", ["method"])
        c.inc(labels={"method": "GET"})
        lines = c.export_prometheus()
        text = "\n".join(lines)
        assert "# HELP requests_total 请求总数" in text
        assert "# TYPE requests_total counter" in text
        assert 'requests_total{method="GET"} 1.0' in text or 'requests_total{method="GET"} 1' in text

    def test_counter_to_dict(self):
        """to_dict 应返回正确的字典结构。"""
        c = Counter("requests_total", "请求总数", ["method"])
        c.inc(labels={"method": "GET"})
        d = c.to_dict()
        assert d["name"] == "requests_total"
        assert d["type"] == "counter"
        assert d["description"] == "请求总数"
        assert d["label_names"] == ["method"]
        assert len(d["values"]) == 1
        assert d["values"][0]["labels"] == {"method": "GET"}
        assert d["values"][0]["value"] == 1.0

    def test_counter_no_description_omits_help(self):
        """无描述时不应输出 HELP 行。"""
        c = Counter("test_total")
        c.inc()
        lines = c.export_prometheus()
        assert not any(line.startswith("# HELP") for line in lines)
        assert any(line.startswith("# TYPE") for line in lines)


# ===== Gauge 测试 =====


class TestGauge:
    """Gauge 指标类型测试。"""

    def test_gauge_set(self):
        """Gauge set 应直接覆盖。"""
        g = Gauge("queue_size", "队列大小")
        g.set(10)
        assert g.get() == 10.0
        g.set(5)
        assert g.get() == 5.0

    def test_gauge_inc_dec(self):
        """Gauge inc/dec 应正确增减。"""
        g = Gauge("queue_size", "队列大小")
        g.set(10)
        g.inc(5)
        assert g.get() == 15.0
        g.dec(3)
        assert g.get() == 12.0

    def test_gauge_negative_value(self):
        """Gauge 允许负值。"""
        g = Gauge("temperature", "温度")
        g.set(-10.5)
        assert g.get() == -10.5

    def test_gauge_with_labels(self):
        """带标签的 Gauge。"""
        g = Gauge("queue_size", "", ["queue"])
        g.set(10, labels={"queue": "default"})
        g.set(20, labels={"queue": "priority"})
        assert g.get(labels={"queue": "default"}) == 10.0
        assert g.get(labels={"queue": "priority"}) == 20.0

    def test_gauge_label_mismatch_raises(self):
        """Gauge 标签不匹配应抛出异常。"""
        g = Gauge("queue_size", "", ["queue"])
        with pytest.raises(ValueError):
            g.set(10, labels={"other": "x"})

    def test_gauge_get_all(self):
        """Gauge get_all 返回所有标签组合。"""
        g = Gauge("queue_size", "", ["queue"])
        g.set(10, labels={"queue": "a"})
        g.set(20, labels={"queue": "b"})
        all_values = g.get_all()
        assert len(all_values) == 2

    def test_gauge_reset(self):
        """Gauge reset 清空。"""
        g = Gauge("queue_size")
        g.set(10)
        g.reset()
        assert g.get() == 0.0

    def test_gauge_export_prometheus(self):
        """Gauge Prometheus 导出。"""
        g = Gauge("queue_size", "队列大小", ["queue"])
        g.set(10, labels={"queue": "default"})
        lines = g.export_prometheus()
        text = "\n".join(lines)
        assert "# TYPE queue_size gauge" in text
        assert 'queue_size{queue="default"}' in text

    def test_gauge_to_dict(self):
        """Gauge to_dict 结构。"""
        g = Gauge("queue_size", "队列大小")
        g.set(10)
        d = g.to_dict()
        assert d["type"] == "gauge"
        assert d["name"] == "queue_size"
        assert d["values"][0]["value"] == 10.0


# ===== Histogram 测试 =====


class TestHistogram:
    """Histogram 指标类型测试。"""

    def test_histogram_observe_basic(self):
        """Histogram 基本观测。"""
        h = Histogram("latency_seconds", "延迟", buckets=[0.1, 1.0, 10.0])
        h.observe(0.05)
        h.observe(0.5)
        h.observe(5.0)
        assert h.get_count() == 3
        assert h.get_sum() == pytest.approx(5.55)

    def test_histogram_negative_value_raises(self):
        """Histogram 不允许负值。"""
        h = Histogram("latency_seconds")
        with pytest.raises(ValueError):
            h.observe(-1)

    def test_histogram_avg(self):
        """Histogram 平均值。"""
        h = Histogram("latency_seconds", buckets=[1.0, 10.0])
        h.observe(1.0)
        h.observe(3.0)
        h.observe(5.0)
        assert h.get_avg() == pytest.approx(3.0)

    def test_histogram_avg_empty(self):
        """无观测时平均值为 0。"""
        h = Histogram("latency_seconds")
        assert h.get_avg() == 0.0
        assert h.get_count() == 0
        assert h.get_sum() == 0.0

    def test_histogram_with_labels(self):
        """带标签的 Histogram。"""
        h = Histogram("latency_seconds", "", buckets=[1.0], label_names=["endpoint"])
        h.observe(0.5, labels={"endpoint": "/api"})
        h.observe(1.5, labels={"endpoint": "/api"})
        h.observe(0.3, labels={"endpoint": "/web"})
        assert h.get_count(labels={"endpoint": "/api"}) == 2
        assert h.get_count(labels={"endpoint": "/web"}) == 1

    def test_histogram_label_mismatch_raises(self):
        """Histogram 标签不匹配抛异常。"""
        h = Histogram("latency_seconds", "", label_names=["endpoint"])
        with pytest.raises(ValueError):
            h.observe(0.5, labels={"other": "x"})

    def test_histogram_percentile_window(self):
        """基于滑动窗口的百分位计算。"""
        h = Histogram("latency_seconds", buckets=[1.0, 10.0], window_seconds=300)
        for v in [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]:
            h.observe(v)
        p50 = h.get_percentile(0.5, use_window=True)
        p90 = h.get_percentile(0.9, use_window=True)
        p99 = h.get_percentile(0.99, use_window=True)
        # p50 应在 5 附近，p90 应在 9 附近，p99 接近 10
        assert 4.0 <= p50 <= 6.0
        assert p90 >= p50
        assert p99 >= p90

    def test_histogram_percentile_bucket(self):
        """基于桶的百分位估算。"""
        h = Histogram("latency_seconds", buckets=[0.1, 1.0, 10.0])
        for _ in range(10):
            h.observe(0.05)
        for _ in range(5):
            h.observe(0.5)
        p50 = h.get_percentile(0.5, use_window=False)
        # 50% 分位应落在 0.1 桶内
        assert p50 <= 0.1

    def test_histogram_percentile_empty(self):
        """无观测时百分位为 0。"""
        h = Histogram("latency_seconds")
        assert h.get_percentile(0.5) == 0.0

    def test_histogram_percentiles_batch(self):
        """批量获取分位数。"""
        h = Histogram("latency_seconds", buckets=[1.0, 10.0])
        for v in [1.0, 2.0, 3.0, 4.0, 5.0]:
            h.observe(v)
        percentiles = h.get_percentiles([0.5, 0.9, 0.99])
        assert "p50" in percentiles
        assert "p90" in percentiles
        assert "p99" in percentiles
        assert percentiles["p50"] <= percentiles["p99"]

    def test_histogram_get_all_label_sets(self):
        """获取所有标签组合。"""
        h = Histogram("latency_seconds", "", label_names=["endpoint"])
        h.observe(0.5, labels={"endpoint": "/api"})
        h.observe(0.3, labels={"endpoint": "/web"})
        label_sets = h.get_all_label_sets()
        assert len(label_sets) == 2

    def test_histogram_reset(self):
        """Histogram reset。"""
        h = Histogram("latency_seconds")
        h.observe(0.5)
        h.reset()
        assert h.get_count() == 0

    def test_histogram_export_prometheus(self):
        """Histogram Prometheus 导出包含 bucket/sum/count。"""
        h = Histogram("latency_seconds", "延迟", buckets=[0.1, 1.0])
        h.observe(0.05)
        h.observe(0.5)
        lines = h.export_prometheus()
        text = "\n".join(lines)
        assert "# TYPE latency_seconds histogram" in text
        assert "latency_seconds_bucket" in text
        assert "latency_seconds_sum" in text
        assert "latency_seconds_count" in text
        assert 'le="+Inf"' in text

    def test_histogram_to_dict(self):
        """Histogram to_dict 结构。"""
        h = Histogram("latency_seconds", "延迟", buckets=[0.1, 1.0])
        h.observe(0.5)
        d = h.to_dict()
        assert d["type"] == "histogram"
        assert d["name"] == "latency_seconds"
        assert "buckets" in d
        assert "series" in d
        assert len(d["series"]) == 1
        assert "percentiles" in d["series"][0]

    def test_histogram_default_buckets(self):
        """未指定 buckets 时使用默认桶。"""
        h = Histogram("latency_seconds")
        assert h.buckets == DEFAULT_HISTOGRAM_BUCKETS

    def test_histogram_custom_buckets_sorted(self):
        """自定义桶应被排序。"""
        h = Histogram("latency_seconds", buckets=[10.0, 1.0, 0.1])
        assert h.buckets == (0.1, 1.0, 10.0)

    def test_histogram_window_prune(self):
        """滑动窗口应清理过期样本。"""
        h = Histogram("latency_seconds", buckets=[1.0], window_seconds=1.0)
        # 记录一个旧样本
        h.observe(0.5)
        # 手动将样本时间戳改为过去
        with h._lock:
            for state in h._states.values():
                state["samples"][0] = (time.time() - 100, 0.5)
        # 再记录新样本
        h.observe(0.3)
        # 百分位应只基于新样本
        p50 = h.get_percentile(0.5, use_window=True)
        assert p50 == pytest.approx(0.3)

    def test_histogram_max_samples_limit(self):
        """max_samples 限制窗口内样本数。"""
        h = Histogram("latency_seconds", buckets=[1.0], max_samples=5)
        for i in range(10):
            h.observe(float(i))
        # 滑动窗口最多保留 5 个样本
        with h._lock:
            for state in h._states.values():
                assert len(state["samples"]) == 5


# ===== TimeSeriesStore 测试 =====


class TestTimeSeriesStore:
    """时序数据存储测试。"""

    def test_record_and_get(self):
        """记录并获取时序数据。"""
        store = TimeSeriesStore()
        store.record("cpu_usage", 50.0)
        store.record("cpu_usage", 60.0)
        points = store.get_series("cpu_usage")
        assert len(points) == 2
        assert points[0].value == 50.0
        assert points[1].value == 60.0

    def test_record_with_labels(self):
        """带标签的时序数据。"""
        store = TimeSeriesStore()
        store.record("queue_size", 10, labels={"queue": "a"})
        store.record("queue_size", 20, labels={"queue": "b"})
        assert len(store.get_series("queue_size", labels={"queue": "a"})) == 1
        assert len(store.get_series("queue_size", labels={"queue": "b"})) == 1

    def test_record_with_custom_timestamp(self):
        """自定义时间戳记录。"""
        store = TimeSeriesStore()
        ts = 1000.0
        store.record("metric", 1.0, timestamp=ts)
        points = store.get_series("metric")
        assert points[0].timestamp == ts

    def test_get_series_with_time_range(self):
        """按时间范围过滤。"""
        store = TimeSeriesStore()
        for i in range(10):
            store.record("metric", float(i), timestamp=1000.0 + i)
        points = store.get_series("metric", start_ts=1003.0, end_ts=1006.0)
        assert len(points) == 4
        assert points[0].timestamp == 1003.0
        assert points[-1].timestamp == 1006.0

    def test_get_all_series_names(self):
        """获取所有指标名。"""
        store = TimeSeriesStore()
        store.record("a", 1.0)
        store.record("b", 2.0)
        names = store.get_all_series_names()
        assert set(names) == {"a", "b"}

    def test_clear_all(self):
        """清空所有时序数据。"""
        store = TimeSeriesStore()
        store.record("a", 1.0)
        store.record("b", 2.0)
        store.clear()
        assert store.get_all_series_names() == []

    def test_clear_single_metric(self):
        """清空单个指标。"""
        store = TimeSeriesStore()
        store.record("a", 1.0)
        store.record("b", 2.0)
        store.clear("a")
        assert "a" not in store.get_all_series_names()
        assert "b" in store.get_all_series_names()

    def test_capacity_limit(self):
        """容量限制应丢弃最旧的数据。"""
        store = TimeSeriesStore(capacity=3)
        for i in range(5):
            store.record("metric", float(i))
        points = store.get_series("metric")
        assert len(points) == 3
        assert points[0].value == 2.0
        assert points[-1].value == 4.0

    def test_to_dict(self):
        """to_dict 序列化。"""
        store = TimeSeriesStore()
        store.record("metric", 1.0, labels={"k": "v"})
        d = store.to_dict()
        assert "metric" in d
        assert "" in d["metric"] or any(d["metric"].values())

    def test_to_dict_single_metric(self):
        """to_dict 指定单个指标。"""
        store = TimeSeriesStore()
        store.record("a", 1.0)
        store.record("b", 2.0)
        d = store.to_dict("a")
        assert "a" in d
        assert "b" not in d


# ===== MetricsCollector 单例测试 =====


class TestMetricsCollectorSingleton:
    """MetricsCollector 单例模式测试。"""

    def test_singleton_same_instance(self):
        """get_instance 多次返回同一实例。"""
        a = MetricsCollector.get_instance()
        b = MetricsCollector.get_instance()
        assert a is b

    def test_reset_instance_creates_new(self):
        """reset_instance 后应创建新实例。"""
        a = MetricsCollector.get_instance()
        MetricsCollector.reset_instance()
        b = MetricsCollector.get_instance()
        assert a is not b

    def test_get_metrics_collector_function(self):
        """模块级 get_metrics_collector 函数。"""
        c = get_metrics_collector()
        assert c is MetricsCollector.get_instance()

    def test_builtin_metrics_registered(self):
        """初始化时应注册内置指标。"""
        c = MetricsCollector.get_instance()
        names = c.list_metric_names()
        assert "metrics_collector_operations_total" in names["counter"]
        assert "metrics_collector_registered_metrics" in names["gauge"]
        assert "metrics_collector_export_duration_seconds" in names["histogram"]


# ===== MetricsCollector 指标注册测试 =====


class TestMetricsCollectorRegistration:
    """MetricsCollector 指标注册与管理测试。"""

    def test_register_counter(self, collector):
        """注册 Counter。"""
        c = collector.counter("test_total", "测试", ["method"])
        assert c.name == "test_total"
        assert collector.get_counter("test_total") is c

    def test_register_gauge(self, collector):
        """注册 Gauge。"""
        g = collector.gauge("test_gauge", "测试")
        assert g.name == "test_gauge"
        assert collector.get_gauge("test_gauge") is g

    def test_register_histogram(self, collector):
        """注册 Histogram。"""
        h = collector.histogram("test_hist", "测试", buckets=[1.0])
        assert h.name == "test_hist"
        assert collector.get_histogram("test_hist") is h

    def test_register_duplicate_returns_same(self, collector):
        """重复注册同名指标返回同一实例。"""
        c1 = collector.counter("test_total", "测试")
        c2 = collector.counter("test_total", "测试")
        assert c1 is c2

    def test_register_name_conflict_across_types(self, collector):
        """不同类型同名冲突应抛异常。"""
        collector.counter("shared_name", "测试")
        with pytest.raises(ValueError):
            collector.gauge("shared_name", "测试")
        with pytest.raises(ValueError):
            collector.histogram("shared_name", "测试")

    def test_list_metric_names(self, collector):
        """列出所有指标名。"""
        collector.counter("c1")
        collector.gauge("g1")
        collector.histogram("h1")
        names = collector.list_metric_names()
        assert "c1" in names["counter"]
        assert "g1" in names["gauge"]
        assert "h1" in names["histogram"]

    def test_remove_metric(self, collector):
        """移除指标。"""
        collector.counter("to_remove")
        assert collector.remove_metric("to_remove") is True
        assert collector.get_counter("to_remove") is None
        assert collector.remove_metric("not_exists") is False

    def test_clear_all(self, collector):
        """清空所有指标后应重新注册内置指标。"""
        collector.counter("custom")
        collector.clear_all()
        names = collector.list_metric_names()
        # 内置指标应仍存在
        assert "metrics_collector_operations_total" in names["counter"]
        # 自定义指标应被清除
        assert "custom" not in names["counter"]

    def test_registered_metrics_gauge_updated(self, collector):
        """注册新指标后 registered_metrics gauge 应更新。"""
        g = collector.gauge("metrics_collector_registered_metrics")
        before = g.get(labels={"metric_type": "counter"})
        collector.counter("new_counter")
        after = g.get(labels={"metric_type": "counter"})
        assert after == before + 1


# ===== MetricsCollector 导出测试 =====


class TestMetricsCollectorExport:
    """MetricsCollector 导出功能测试。"""

    def test_export_prometheus(self, collector):
        """Prometheus 导出包含所有指标。"""
        collector.counter("c1", "计数器").inc()
        collector.gauge("g1", "仪表").set(5)
        collector.histogram("h1", "直方图", buckets=[1.0]).observe(0.5)
        text = collector.export_prometheus()
        assert "c1" in text
        assert "g1" in text
        assert "h1_bucket" in text

    def test_export_prometheus_empty(self, collector):
        """空收集器导出应包含内置指标。"""
        text = collector.export_prometheus()
        assert "metrics_collector_operations_total" in text

    def test_export_json(self, collector):
        """JSON 导出可被解析。"""
        collector.counter("c1", "计数器").inc()
        data = json.loads(collector.export_json())
        assert "counters" in data
        assert "gauges" in data
        assert "histograms" in data
        assert "timestamp" in data

    def test_export_json_with_indent(self, collector):
        """带缩进的 JSON 导出。"""
        text = collector.export_json(indent=2)
        assert "\n" in text

    def test_export_dict(self, collector):
        """字典导出。"""
        collector.counter("c1").inc()
        d = collector.export_dict()
        assert isinstance(d, dict)
        assert len(d["counters"]) >= 1

    def test_snapshot_equals_export_dict(self, collector):
        """snapshot 与 export_dict 等价。"""
        collector.counter("c1").inc()
        assert collector.snapshot() == collector.export_dict()

    def test_export_records_duration(self, collector):
        """导出应记录耗时到内置 histogram。"""
        collector.export_prometheus()
        h = collector.get_histogram("metrics_collector_export_duration_seconds")
        assert h.get_count() == 1


# ===== MetricsCollector 时序数据测试 =====


class TestMetricsCollectorTimeSeries:
    """MetricsCollector 时序数据功能测试。"""

    def test_record_and_get_timeseries(self, collector):
        """记录并查询时序数据。"""
        collector.record_timeseries("cpu_usage", 50.0)
        collector.record_timeseries("cpu_usage", 60.0)
        points = collector.get_timeseries("cpu_usage")
        assert len(points) == 2

    def test_record_timeseries_with_labels(self, collector):
        """带标签的时序记录。"""
        collector.record_timeseries("queue_size", 10, labels={"queue": "a"})
        collector.record_timeseries("queue_size", 20, labels={"queue": "b"})
        assert len(collector.get_timeseries("queue_size", labels={"queue": "a"})) == 1
        assert len(collector.get_timeseries("queue_size", labels={"queue": "b"})) == 1

    def test_snapshot_all_to_timeseries(self, collector):
        """快照所有指标到时序存储。"""
        g = collector.gauge("test_gauge", "", ["tag"])
        g.set(10, labels={"tag": "x"})
        h = collector.histogram("test_hist", buckets=[1.0])
        h.observe(0.5)
        collector.snapshot_all_to_timeseries()
        # gauge 应被记录
        points = collector.get_timeseries("test_gauge", labels={"tag": "x"})
        assert len(points) >= 1
        # histogram 的 avg 与 p99 应被记录
        avg_points = collector.get_timeseries("test_hist_avg")
        p99_points = collector.get_timeseries("test_hist_p99")
        assert len(avg_points) >= 1
        assert len(p99_points) >= 1


# ===== MetricsCollector 批量上报测试 =====


class TestMetricsCollectorBatch:
    """MetricsCollector 批量上报测试。"""

    def test_record_sample(self, collector):
        """记录采样点到缓冲区。"""
        collector.record_sample("metric", 1.0)
        collector.record_sample("metric", 2.0)
        # 未刷新前缓冲区有数据
        assert collector.flush_batch() == 2

    def test_flush_batch_empty(self, collector):
        """空缓冲区刷新返回 0。"""
        assert collector.flush_batch() == 0

    def test_batch_callback_invoked(self, collector):
        """刷新时应调用回调。"""
        received = []
        collector.add_batch_callback(received.extend)
        collector.record_sample("m", 1.0)
        collector.record_sample("m", 2.0)
        count = collector.flush_batch()
        assert count == 2
        assert len(received) == 2
        assert all(isinstance(s, MetricSample) for s in received)

    def test_batch_callback_exception_swallowed(self, collector):
        """回调异常应被吞掉不影响其他回调。"""
        def bad_callback(samples):
            raise RuntimeError("回调异常")

        good_received = []
        collector.add_batch_callback(bad_callback)
        collector.add_batch_callback(good_received.extend)
        collector.record_sample("m", 1.0)
        # 不应抛出异常
        count = collector.flush_batch()
        assert count == 1
        assert len(good_received) == 1

    def test_batch_auto_flush_on_full(self, collector):
        """缓冲区满时应自动刷新。"""
        received = []
        collector.add_batch_callback(received.extend)
        # 写入超过缓冲区大小
        for i in range(DEFAULT_BATCH_BUFFER_SIZE + 1):
            collector.record_sample("m", float(i))
        # 至少触发了一次自动刷新
        assert len(received) >= DEFAULT_BATCH_BUFFER_SIZE


# ===== MetricsCollector 持久化测试 =====


class TestMetricsCollectorPersistence:
    """MetricsCollector SQLite 持久化测试。"""

    def test_persist_to_db(self, collector, tmp_db_path):
        """持久化时序数据到 SQLite。"""
        collector.record_timeseries("metric", 1.0)
        collector.record_timeseries("metric", 2.0)
        count = collector.persist_to_db(tmp_db_path)
        assert count == 2
        # 验证数据库文件存在
        assert Path(tmp_db_path).exists()

    def test_persist_creates_table(self, collector, tmp_db_path):
        """持久化应创建表。"""
        collector.record_timeseries("metric", 1.0)
        collector.persist_to_db(tmp_db_path)
        conn = sqlite3.connect(tmp_db_path)
        try:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='metrics_timeseries'"
            )
            assert cursor.fetchone() is not None
        finally:
            conn.close()

    def test_load_from_db(self, collector, tmp_db_path):
        """从 SQLite 加载时序数据。"""
        collector.record_timeseries("metric", 1.0, labels={"k": "v"})
        collector.persist_to_db(tmp_db_path)
        # 重置后重新加载
        MetricsCollector.reset_instance()
        new_collector = MetricsCollector.get_instance()
        loaded = new_collector.load_from_db(tmp_db_path)
        assert loaded == 1
        points = new_collector.get_timeseries("metric", labels={"k": "v"})
        assert len(points) == 1
        assert points[0].value == 1.0

    def test_load_from_db_with_name_filter(self, collector, tmp_db_path):
        """按指标名过滤加载。"""
        collector.record_timeseries("a", 1.0)
        collector.record_timeseries("b", 2.0)
        collector.persist_to_db(tmp_db_path)
        MetricsCollector.reset_instance()
        new_collector = MetricsCollector.get_instance()
        loaded = new_collector.load_from_db(tmp_db_path, name="a")
        assert loaded == 1
        assert len(new_collector.get_timeseries("a")) == 1
        assert len(new_collector.get_timeseries("b")) == 0

    def test_load_from_db_nonexistent_file(self, collector):
        """加载不存在的数据库应返回 0。"""
        loaded = collector.load_from_db("/nonexistent/path/db.db")
        assert loaded == 0

    def test_persist_empty(self, collector, tmp_db_path):
        """空时序数据持久化应返回 0。"""
        count = collector.persist_to_db(tmp_db_path)
        assert count == 0


# ===== MetricsCollector 异步任务测试 =====


class TestMetricsCollectorAsync:
    """MetricsCollector 异步任务测试。"""

    @pytest.mark.asyncio
    async def test_start_and_stop_persist_task(self, collector, tmp_db_path):
        """启动并停止异步持久化任务。"""
        collector.record_timeseries("metric", 1.0)
        # 用很短的间隔测试
        with patch.object(collector, "persist_to_db", return_value=1) as mock_persist:
            await collector.start_persist_task(interval=0.05)
            await asyncio_sleep(0.15)
            assert collector._persist_enabled is True
            await collector.stop_persist_task()
            assert collector._persist_enabled is False
            assert collector._persist_task is None
            # 至少调用过一次 persist_to_db
            assert mock_persist.call_count >= 1

    @pytest.mark.asyncio
    async def test_start_persist_task_idempotent(self, collector):
        """重复启动持久化任务应是幂等的。"""
        with patch.object(collector, "snapshot_all_to_timeseries"), \
             patch.object(collector, "persist_to_db", return_value=0):
            await collector.start_persist_task(interval=1.0)
            first_task = collector._persist_task
            await collector.start_persist_task(interval=1.0)
            assert collector._persist_task is first_task
            await collector.stop_persist_task()


# ===== MetricsCollector 线程安全测试 =====


class TestMetricsCollectorThreadSafety:
    """MetricsCollector 线程安全测试。"""

    def test_counter_concurrent_inc(self, collector):
        """多线程并发自增 Counter。"""
        c = collector.counter("concurrent_total", "", ["worker"])
        n_threads = 10
        n_per_thread = 100

        def worker(tid):
            for _ in range(n_per_thread):
                c.inc(labels={"worker": str(tid)})

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # 每个线程应记录 100 次
        for i in range(n_threads):
            assert c.get(labels={"worker": str(i)}) == n_per_thread

    def test_histogram_concurrent_observe(self, collector):
        """多线程并发观测 Histogram。"""
        h = collector.histogram("concurrent_latency", buckets=[1.0])
        n_threads = 8
        n_per_thread = 50

        def worker():
            for i in range(n_per_thread):
                h.observe(0.001 * (i % 10))

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert h.get_count() == n_threads * n_per_thread

    def test_gauge_concurrent_set_inc(self, collector):
        """多线程并发操作 Gauge。"""
        g = collector.gauge("concurrent_gauge")
        g.set(0)
        n_threads = 10
        n_per_thread = 100

        def worker():
            for _ in range(n_per_thread):
                g.inc(1)
                g.dec(1)

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # 所有线程 inc 后 dec，最终值应为 0
        assert g.get() == 0.0

    def test_record_sample_concurrent(self, collector):
        """多线程并发记录采样点。"""
        received = []
        received_lock = threading.Lock()

        def callback(samples):
            with received_lock:
                received.extend(samples)

        collector.add_batch_callback(callback)
        n_threads = 5
        n_per_thread = 50

        def worker(tid):
            for i in range(n_per_thread):
                collector.record_sample("m", float(tid * 1000 + i))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        collector.flush_batch()
        assert len(received) == n_threads * n_per_thread


# ===== MetricsCollector 延迟测量测试 =====


class TestMeasureLatency:
    """measure_latency 上下文管理器测试。"""

    def test_measure_latency_records(self, collector):
        """measure_latency 应记录耗时。"""
        with collector.measure_latency("api_latency"):
            time.sleep(0.01)
        h = collector.get_histogram("api_latency")
        assert h is not None
        assert h.get_count() == 1
        assert h.get_sum() > 0

    def test_measure_latency_with_labels(self, collector):
        """带标签的延迟测量。"""
        with collector.measure_latency("api_latency", labels={"path": "/x"}):
            pass
        h = collector.get_histogram("api_latency")
        # 注意：measure_latency 内部会重新注册 histogram（无 label_names）
        # 这里仅验证 histogram 存在且有记录
        assert h is not None
        assert h.get_count() >= 1

    def test_measure_latency_multiple_calls(self, collector):
        """多次调用 measure_latency 累积记录。"""
        for _ in range(3):
            with collector.measure_latency("op_latency"):
                time.sleep(0.001)
        h = collector.get_histogram("op_latency")
        assert h.get_count() == 3


# ===== 模块级便捷函数测试 =====


class TestModuleLevelFunctions:
    """模块级便捷函数测试。"""

    def test_record_api_request(self, collector):
        """record_api_request 应记录请求与延迟。"""
        record_api_request("GET", "/sessions", 200, 0.05)
        c = collector.get_counter("http_requests_total")
        assert c is not None
        assert c.get(labels={"method": "GET", "path": "/sessions", "status": "200"}) == 1
        h = collector.get_histogram("http_request_duration_seconds")
        assert h is not None
        assert h.get_count(labels={"method": "GET", "path": "/sessions"}) == 1

    def test_record_llm_call(self, collector):
        """record_llm_call 应记录调用与延迟。"""
        record_llm_call("deepseek", "deepseek-chat", "summary", 1.5, True)
        c = collector.get_counter("llm_calls_total")
        assert c.get(
            labels={"provider": "deepseek", "model": "deepseek-chat", "stage": "summary", "result": "success"}
        ) == 1

    def test_record_llm_call_failure(self, collector):
        """record_llm_call 失败记录。"""
        record_llm_call("openai", "gpt-4", "translate", 0.5, False)
        c = collector.get_counter("llm_calls_total")
        assert c.get(
            labels={"provider": "openai", "model": "gpt-4", "stage": "translate", "result": "failure"}
        ) == 1

    def test_record_cache_event(self, collector):
        """record_cache_event 记录缓存事件。"""
        record_cache_event("embedding", True)
        record_cache_event("embedding", False)
        c = collector.get_counter("cache_events_total")
        assert c.get(labels={"cache_type": "embedding", "result": "hit"}) == 1
        assert c.get(labels={"cache_type": "embedding", "result": "miss"}) == 1

    def test_update_concurrent_gauge(self, collector):
        """update_concurrent_gauge 更新并发数。"""
        update_concurrent_gauge("active_sessions", 5)
        g = collector.get_gauge("active_sessions")
        assert g is not None
        assert g.get() == 5.0


# ===== MetricSample 数据类测试 =====


class TestMetricSample:
    """MetricSample 数据类测试。"""

    def test_metric_sample_to_dict(self):
        """MetricSample to_dict。"""
        s = MetricSample(name="m", value=1.0, labels={"k": "v"})
        d = s.to_dict()
        assert d["name"] == "m"
        assert d["value"] == 1.0
        assert d["labels"] == {"k": "v"}
        assert "timestamp" in d

    def test_metric_sample_default_labels(self):
        """MetricSample 默认标签为空字典。"""
        s = MetricSample(name="m", value=1.0)
        assert s.labels == {}

    def test_metric_sample_default_timestamp(self):
        """MetricSample 默认时间戳为当前时间。"""
        before = time.time()
        s = MetricSample(name="m", value=1.0)
        after = time.time()
        assert before <= s.timestamp <= after


# ===== TimeSeriesPoint 数据类测试 =====


class TestTimeSeriesPoint:
    """TimeSeriesPoint 数据类测试。"""

    def test_timeseries_point_default_labels(self):
        """TimeSeriesPoint 默认标签为空。"""
        p = TimeSeriesPoint(timestamp=1.0, value=2.0)
        assert p.labels == {}

    def test_timeseries_point_with_labels(self):
        """TimeSeriesPoint 带标签。"""
        p = TimeSeriesPoint(timestamp=1.0, value=2.0, labels={"k": "v"})
        assert p.labels == {"k": "v"}


# ===== 综合场景测试 =====


class TestIntegrationScenarios:
    """综合场景测试。"""

    def test_full_workflow(self, collector, tmp_db_path):
        """完整工作流：注册 -> 记录 -> 导出 -> 持久化 -> 加载。"""
        # 1. 注册并记录
        c = collector.counter("workflow_total", "工作流", ["stage"])
        c.inc(labels={"stage": "start"})
        c.inc(5, labels={"stage": "process"})
        c.inc(labels={"stage": "end"})

        g = collector.gauge("workflow_queue", "队列", ["queue"])
        g.set(10, labels={"queue": "default"})

        h = collector.histogram("workflow_latency", "延迟", buckets=[0.1, 1.0])
        for v in [0.05, 0.1, 0.5, 1.0, 2.0]:
            h.observe(v)

        # 2. 导出
        prom_text = collector.export_prometheus()
        assert "workflow_total" in prom_text
        json_data = json.loads(collector.export_json())
        assert len(json_data["counters"]) >= 1

        # 3. 时序快照
        collector.snapshot_all_to_timeseries()
        ts_points = collector.get_timeseries("workflow_queue", labels={"queue": "default"})
        assert len(ts_points) >= 1

        # 4. 持久化
        persisted = collector.persist_to_db(tmp_db_path)
        assert persisted > 0

        # 5. 加载
        MetricsCollector.reset_instance()
        new_collector = MetricsCollector.get_instance()
        loaded = new_collector.load_from_db(tmp_db_path)
        assert loaded > 0
        loaded_points = new_collector.get_timeseries("workflow_queue", labels={"queue": "default"})
        assert len(loaded_points) >= 1

    def test_get_metric_summary(self, collector):
        """获取单个指标摘要。"""
        collector.counter("summary_test", "摘要测试").inc()
        summary = collector.get_metric_summary("summary_test")
        assert summary is not None
        assert summary["name"] == "summary_test"

        # 不存在的指标返回 None
        assert collector.get_metric_summary("nonexistent") is None

    def test_get_all_summaries(self, collector):
        """获取所有指标摘要。"""
        collector.counter("s1").inc()
        collector.gauge("s2").set(1)
        summaries = collector.get_all_summaries()
        assert "counters" in summaries
        assert "gauges" in summaries
        assert "histograms" in summaries


# ===== 异步辅助函数 =====


async def asyncio_sleep(seconds: float):
    """异步睡眠辅助函数（避免直接导入 asyncio）。"""
    import asyncio
    await asyncio.sleep(seconds)
