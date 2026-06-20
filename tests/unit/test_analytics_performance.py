"""PerformanceMonitor 单元测试

覆盖范围：
    - CPU / 内存 / 磁盘 / 网络 / 进程快照数据结构
    - PerformanceSnapshot 综合快照与序列化
    - AlertManager 告警规则管理、阈值检测、持续触发、恢复事件
    - PerformanceBaseline 基线计算、3-sigma 异常检测
    - PerformanceMonitor 单例模式与重置
    - 快照采集与历史数据管理
    - 异步定时采样任务
    - 性能报告生成（字典与文本格式）
    - 趋势分析与图表数据准备
    - SQLite 持久化与加载
    - 瓶颈识别
    - 模块级便捷函数
    - psutil 缺失时的降级行为

运行方式：
    pytest tests/unit/test_analytics_performance.py -v
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.analytics.performance_monitor import (
    DEFAULT_ALERT_SUSTAIN_SECONDS,
    DEFAULT_BASELINE_MIN_SAMPLES,
    DEFAULT_BASELINE_WINDOW,
    DEFAULT_CPU_CRITICAL_THRESHOLD,
    DEFAULT_CPU_WARNING_THRESHOLD,
    DEFAULT_DISK_CRITICAL_THRESHOLD,
    DEFAULT_DISK_WARNING_THRESHOLD,
    DEFAULT_HISTORY_CAPACITY,
    DEFAULT_MEM_CRITICAL_THRESHOLD,
    DEFAULT_MEM_WARNING_THRESHOLD,
    DEFAULT_SAMPLE_INTERVAL,
    AlertEvent,
    AlertManager,
    AlertRule,
    CpuSnapshot,
    DiskSnapshot,
    MemorySnapshot,
    NetworkSnapshot,
    PerformanceBaseline,
    PerformanceMonitor,
    PerformanceSnapshot,
    ProcessSnapshot,
    check_health,
    get_performance_monitor,
    quick_snapshot,
)


# ===== 公共夹具 =====


@pytest.fixture(autouse=True)
def reset_monitor():
    """每个测试前后重置单例，保证测试间隔离。"""
    PerformanceMonitor.reset_instance()
    yield
    PerformanceMonitor.reset_instance()


@pytest.fixture
def monitor():
    """返回一个全新的 PerformanceMonitor 实例。"""
    return PerformanceMonitor.get_instance()


@pytest.fixture
def tmp_db_path(tmp_path):
    """返回临时数据库路径。"""
    return str(tmp_path / "perf_test.db")


def make_snapshot(
    cpu_sys: float = 10.0,
    cpu_proc: float = 5.0,
    mem_used: float = 40.0,
    mem_proc: float = 20.0,
    disk_used: float = 50.0,
    proc_cpu: float = 5.0,
    proc_mem: float = 20.0,
    timestamp: float = None,
) -> PerformanceSnapshot:
    """构造一个用于测试的性能快照。"""
    snap = PerformanceSnapshot()
    snap.cpu.system_percent = cpu_sys
    snap.cpu.process_percent = cpu_proc
    snap.cpu.core_count = 4
    snap.memory.used_percent = mem_used
    snap.memory.process_percent = mem_proc
    snap.memory.total_bytes = 8 * 1024 * 1024 * 1024
    snap.memory.available_bytes = 4 * 1024 * 1024 * 1024
    snap.memory.used_bytes = 4 * 1024 * 1024 * 1024
    snap.memory.process_rss = 100 * 1024 * 1024
    snap.disk.used_percent = disk_used
    snap.disk.read_bytes_per_sec = 1024.0
    snap.disk.write_bytes_per_sec = 2048.0
    snap.network.bytes_sent_per_sec = 512.0
    snap.network.bytes_recv_per_sec = 1024.0
    snap.process.cpu_percent = proc_cpu
    snap.process.memory_percent = proc_mem
    snap.process.pid = 1234
    snap.process.thread_count = 10
    if timestamp is not None:
        snap.timestamp = timestamp
        snap.cpu.timestamp = timestamp
        snap.memory.timestamp = timestamp
        snap.disk.timestamp = timestamp
        snap.network.timestamp = timestamp
        snap.process.timestamp = timestamp
    return snap


# ===== 快照数据类测试 =====


class TestSnapshotDataclasses:
    """快照数据类测试。"""

    def test_cpu_snapshot_defaults(self):
        """CpuSnapshot 默认值应为 0。"""
        s = CpuSnapshot()
        assert s.system_percent == 0.0
        assert s.process_percent == 0.0
        assert s.core_count == 0
        assert s.timestamp > 0

    def test_memory_snapshot_defaults(self):
        """MemorySnapshot 默认值应为 0。"""
        s = MemorySnapshot()
        assert s.total_bytes == 0
        assert s.used_percent == 0.0
        assert s.process_rss == 0

    def test_disk_snapshot_defaults(self):
        """DiskSnapshot 默认值应为 0。"""
        s = DiskSnapshot()
        assert s.total_bytes == 0
        assert s.used_percent == 0.0
        assert s.read_bytes_per_sec == 0.0

    def test_network_snapshot_defaults(self):
        """NetworkSnapshot 默认值应为 0。"""
        s = NetworkSnapshot()
        assert s.bytes_sent == 0
        assert s.bytes_recv == 0
        assert s.bytes_sent_per_sec == 0.0

    def test_process_snapshot_defaults(self):
        """ProcessSnapshot 默认值。"""
        s = ProcessSnapshot()
        assert s.pid == 0
        assert s.name == ""
        assert s.cpu_percent == 0.0

    def test_performance_snapshot_to_dict(self):
        """PerformanceSnapshot to_dict 应包含所有子快照。"""
        snap = make_snapshot(cpu_sys=50.0)
        d = snap.to_dict()
        assert "cpu" in d
        assert "memory" in d
        assert "disk" in d
        assert "network" in d
        assert "process" in d
        assert "timestamp" in d
        assert "iso_timestamp" in d
        assert d["cpu"]["system_percent"] == 50.0

    def test_performance_snapshot_nested_dict(self):
        """PerformanceSnapshot to_dict 子字段正确。"""
        snap = make_snapshot(mem_used=75.5, disk_used=80.0)
        d = snap.to_dict()
        assert d["memory"]["used_percent"] == 75.5
        assert d["disk"]["used_percent"] == 80.0


# ===== AlertRule / AlertEvent 测试 =====


class TestAlertRuleAndEvent:
    """AlertRule 与 AlertEvent 数据类测试。"""

    def test_alert_rule_defaults(self):
        """AlertRule 默认值。"""
        rule = AlertRule(
            name="test",
            metric_path="cpu.system_percent",
            warning_threshold=70.0,
            critical_threshold=90.0,
        )
        assert rule.sustain_seconds == DEFAULT_ALERT_SUSTAIN_SECONDS
        assert rule.comparison == ">"
        assert rule.enabled is True
        assert rule.description == ""

    def test_alert_rule_custom(self):
        """AlertRule 自定义值。"""
        rule = AlertRule(
            name="low_mem",
            metric_path="memory.available_bytes",
            warning_threshold=1e9,
            critical_threshold=5e8,
            sustain_seconds=10.0,
            comparison="<",
            enabled=False,
            description="可用内存过低",
        )
        assert rule.comparison == "<"
        assert rule.enabled is False
        assert rule.sustain_seconds == 10.0

    def test_alert_event_to_dict(self):
        """AlertEvent to_dict。"""
        event = AlertEvent(
            rule_name="high_cpu",
            level="critical",
            metric_path="cpu.system_percent",
            value=95.0,
            threshold=90.0,
            message="CPU 过高",
        )
        d = event.to_dict()
        assert d["rule_name"] == "high_cpu"
        assert d["level"] == "critical"
        assert d["value"] == 95.0
        assert "timestamp" in d
        assert "iso_timestamp" in d


# ===== AlertManager 测试 =====


class TestAlertManager:
    """AlertManager 告警管理器测试。"""

    def test_add_and_remove_rule(self):
        """添加与移除告警规则。"""
        mgr = AlertManager()
        rule = AlertRule("r1", "cpu.system_percent", 70, 90, sustain_seconds=0)
        mgr.add_rule(rule)
        assert len(mgr.get_rules()) == 1
        assert mgr.remove_rule("r1") is True
        assert mgr.remove_rule("not_exists") is False
        assert len(mgr.get_rules()) == 0

    def test_evaluate_warning_triggered(self):
        """超 warning 阈值应触发告警。"""
        mgr = AlertManager()
        rule = AlertRule(
            "high_cpu", "cpu.system_percent", 70, 90,
            sustain_seconds=0,  # 立即触发
        )
        mgr.add_rule(rule)
        snap = make_snapshot(cpu_sys=75.0)
        events = mgr.evaluate(snap)
        assert len(events) == 1
        assert events[0].level == "warning"
        assert events[0].rule_name == "high_cpu"

    def test_evaluate_critical_triggered(self):
        """超 critical 阈值应触发 critical 告警。"""
        mgr = AlertManager()
        rule = AlertRule("high_cpu", "cpu.system_percent", 70, 90, sustain_seconds=0)
        mgr.add_rule(rule)
        snap = make_snapshot(cpu_sys=95.0)
        events = mgr.evaluate(snap)
        assert len(events) == 1
        assert events[0].level == "critical"

    def test_evaluate_no_trigger_below_threshold(self):
        """低于阈值不应触发告警。"""
        mgr = AlertManager()
        rule = AlertRule("high_cpu", "cpu.system_percent", 70, 90, sustain_seconds=0)
        mgr.add_rule(rule)
        snap = make_snapshot(cpu_sys=50.0)
        events = mgr.evaluate(snap)
        assert len(events) == 0

    def test_evaluate_disabled_rule_skipped(self):
        """禁用的规则不应触发。"""
        mgr = AlertManager()
        rule = AlertRule("high_cpu", "cpu.system_percent", 70, 90, sustain_seconds=0, enabled=False)
        mgr.add_rule(rule)
        snap = make_snapshot(cpu_sys=95.0)
        events = mgr.evaluate(snap)
        assert len(events) == 0

    def test_evaluate_sustain_seconds(self):
        """持续时间未满不应触发告警。"""
        mgr = AlertManager()
        rule = AlertRule("high_cpu", "cpu.system_percent", 70, 90, sustain_seconds=10.0)
        mgr.add_rule(rule)
        # 第一次评估，记录持续开始时间
        snap1 = make_snapshot(cpu_sys=95.0, timestamp=1000.0)
        events1 = mgr.evaluate(snap1)
        assert len(events1) == 0
        # 5 秒后仍未达持续阈值
        snap2 = make_snapshot(cpu_sys=95.0, timestamp=1005.0)
        events2 = mgr.evaluate(snap2)
        assert len(events2) == 0
        # 11 秒后达到持续阈值
        snap3 = make_snapshot(cpu_sys=95.0, timestamp=1011.0)
        events3 = mgr.evaluate(snap3)
        assert len(events3) == 1
        assert events3[0].level == "critical"

    def test_evaluate_recovered_event(self):
        """恢复正常时应生成 recovered 事件。"""
        mgr = AlertManager()
        rule = AlertRule("high_cpu", "cpu.system_percent", 70, 90, sustain_seconds=0)
        mgr.add_rule(rule)
        # 先触发告警
        snap1 = make_snapshot(cpu_sys=95.0, timestamp=1000.0)
        mgr.evaluate(snap1)
        assert len(mgr.get_active_alerts()) == 1
        # 恢复正常
        snap2 = make_snapshot(cpu_sys=50.0, timestamp=1001.0)
        events = mgr.evaluate(snap2)
        assert len(events) == 1
        assert events[0].level == "recovered"
        assert len(mgr.get_active_alerts()) == 0

    def test_evaluate_comparison_less_than(self):
        """comparison='<' 时低值触发告警。"""
        mgr = AlertManager()
        rule = AlertRule(
            "low_mem", "memory.available_bytes", 1e9, 5e8,
            sustain_seconds=0, comparison="<",
        )
        mgr.add_rule(rule)
        snap = make_snapshot()
        snap.memory.available_bytes = 1e8  # 低于 critical
        events = mgr.evaluate(snap)
        assert len(events) == 1
        assert events[0].level == "critical"

    def test_evaluate_invalid_metric_path_skipped(self):
        """无效指标路径应跳过。"""
        mgr = AlertManager()
        rule = AlertRule("bad", "nonexistent.path", 70, 90, sustain_seconds=0)
        mgr.add_rule(rule)
        snap = make_snapshot()
        events = mgr.evaluate(snap)
        assert len(events) == 0

    def test_callback_invoked(self):
        """告警回调应被调用。"""
        mgr = AlertManager()
        received = []
        mgr.add_callback(lambda e: received.append(e))
        rule = AlertRule("high_cpu", "cpu.system_percent", 70, 90, sustain_seconds=0)
        mgr.add_rule(rule)
        snap = make_snapshot(cpu_sys=95.0)
        mgr.evaluate(snap)
        assert len(received) == 1

    def test_callback_exception_swallowed(self):
        """回调异常应被吞掉。"""
        mgr = AlertManager()
        mgr.add_callback(lambda e: (_ for _ in ()).throw(RuntimeError("bad")))
        rule = AlertRule("high_cpu", "cpu.system_percent", 70, 90, sustain_seconds=0)
        mgr.add_rule(rule)
        snap = make_snapshot(cpu_sys=95.0)
        # 不应抛出
        events = mgr.evaluate(snap)
        assert len(events) == 1

    def test_get_active_alerts(self):
        """获取活跃告警。"""
        mgr = AlertManager()
        rule = AlertRule("high_cpu", "cpu.system_percent", 70, 90, sustain_seconds=0)
        mgr.add_rule(rule)
        snap = make_snapshot(cpu_sys=95.0)
        mgr.evaluate(snap)
        active = mgr.get_active_alerts()
        assert len(active) == 1
        assert active[0].rule_name == "high_cpu"

    def test_get_history(self):
        """获取告警历史。"""
        mgr = AlertManager()
        rule = AlertRule("high_cpu", "cpu.system_percent", 70, 90, sustain_seconds=0)
        mgr.add_rule(rule)
        snap = make_snapshot(cpu_sys=95.0)
        mgr.evaluate(snap)
        history = mgr.get_history()
        assert len(history) == 1
        # 限制数量
        assert len(mgr.get_history(limit=5)) == 1

    def test_clear(self):
        """清空告警状态。"""
        mgr = AlertManager()
        rule = AlertRule("high_cpu", "cpu.system_percent", 70, 90, sustain_seconds=0)
        mgr.add_rule(rule)
        snap = make_snapshot(cpu_sys=95.0)
        mgr.evaluate(snap)
        mgr.clear()
        assert len(mgr.get_active_alerts()) == 0
        assert len(mgr.get_history()) == 0

    def test_no_duplicate_same_level(self):
        """同级别告警不应重复触发。"""
        mgr = AlertManager()
        rule = AlertRule("high_cpu", "cpu.system_percent", 70, 90, sustain_seconds=0)
        mgr.add_rule(rule)
        snap = make_snapshot(cpu_sys=95.0, timestamp=1000.0)
        events1 = mgr.evaluate(snap)
        snap2 = make_snapshot(cpu_sys=96.0, timestamp=1001.0)
        events2 = mgr.evaluate(snap2)
        assert len(events1) == 1
        assert len(events2) == 0  # 同级别不重复

    def test_level_upgrade_triggers_new(self):
        """告警级别升级应触发新事件。"""
        mgr = AlertManager()
        rule = AlertRule("high_cpu", "cpu.system_percent", 70, 90, sustain_seconds=0)
        mgr.add_rule(rule)
        # 先 warning
        snap1 = make_snapshot(cpu_sys=75.0, timestamp=1000.0)
        events1 = mgr.evaluate(snap1)
        assert len(events1) == 1
        assert events1[0].level == "warning"
        # 升级到 critical
        snap2 = make_snapshot(cpu_sys=95.0, timestamp=1001.0)
        events2 = mgr.evaluate(snap2)
        assert len(events2) == 1
        assert events2[0].level == "critical"


# ===== PerformanceBaseline 测试 =====


class TestPerformanceBaseline:
    """PerformanceBaseline 性能基线测试。"""

    def test_update_and_get_stats_insufficient(self):
        """样本不足时 get_stats 返回 None。"""
        bl = PerformanceBaseline()
        for i in range(10):
            bl.update("cpu.system_percent", float(i))
        assert bl.get_stats("cpu.system_percent") is None

    def test_get_stats_sufficient(self):
        """样本足够时返回统计元组。"""
        bl = PerformanceBaseline(window=100)
        for i in range(DEFAULT_BASELINE_MIN_SAMPLES):
            bl.update("cpu.system_percent", 50.0)
        stats = bl.get_stats("cpu.system_percent")
        assert stats is not None
        mean, std, lower, upper = stats
        assert mean == pytest.approx(50.0)
        assert std == pytest.approx(0.0)
        assert lower <= mean <= upper

    def test_get_stats_with_variance(self):
        """有方差时统计正确。"""
        bl = PerformanceBaseline(window=1000)
        values = [10.0, 20.0, 30.0, 40.0, 50.0] * (DEFAULT_BASELINE_MIN_SAMPLES // 5 + 1)
        for v in values:
            bl.update("metric", v)
        stats = bl.get_stats("metric")
        assert stats is not None
        mean, std, lower, upper = stats
        assert mean == pytest.approx(30.0)
        assert std > 0
        assert lower < mean < upper

    def test_is_anomaly_false_when_no_baseline(self):
        """无基线时 is_anomaly 返回 False。"""
        bl = PerformanceBaseline()
        assert bl.is_anomaly("metric", 100.0) is False

    def test_is_anomaly_true_when_out_of_range(self):
        """超出 3-sigma 范围应为异常。"""
        bl = PerformanceBaseline(window=1000)
        for _ in range(DEFAULT_BASELINE_MIN_SAMPLES):
            bl.update("metric", 50.0)
        # 均值 50，std 0，3-sigma 范围 [50, 50]
        assert bl.is_anomaly("metric", 100.0) is True
        assert bl.is_anomaly("metric", 50.0) is False

    def test_is_anomaly_with_variance(self):
        """有方差时的异常检测。"""
        bl = PerformanceBaseline(window=1000)
        # 构造均值 50，std 约 14.5 的样本
        for _ in range(DEFAULT_BASELINE_MIN_SAMPLES):
            bl.update("metric", 50.0)
            bl.update("metric", 30.0)
            bl.update("metric", 70.0)
        stats = bl.get_stats("metric")
        mean, std, lower, upper = stats
        # 极端值应被判为异常
        assert bl.is_anomaly("metric", mean + 10 * std) is True
        assert bl.is_anomaly("metric", mean - 10 * std) is True

    def test_get_all_baselines(self):
        """获取所有指标的基线。"""
        bl = PerformanceBaseline(window=1000)
        for _ in range(DEFAULT_BASELINE_MIN_SAMPLES):
            bl.update("a", 1.0)
            bl.update("b", 2.0)
        all_bl = bl.get_all_baselines()
        assert "a" in all_bl
        assert "b" in all_bl
        assert all_bl["a"]["mean"] == pytest.approx(1.0)
        assert all_bl["b"]["mean"] == pytest.approx(2.0)
        assert "sample_count" in all_bl["a"]

    def test_clear(self):
        """清空基线。"""
        bl = PerformanceBaseline()
        bl.update("metric", 1.0)
        bl.clear()
        assert bl.get_stats("metric") is None

    def test_window_limit(self):
        """窗口限制应丢弃最旧样本。"""
        bl = PerformanceBaseline(window=10)
        for i in range(20):
            bl.update("metric", float(i))
        # 只保留最近 10 个样本（10-19）
        samples = list(bl._samples["metric"])
        assert len(samples) == 10
        assert samples[0] == 10.0


# ===== PerformanceMonitor 单例测试 =====


class TestPerformanceMonitorSingleton:
    """PerformanceMonitor 单例模式测试。"""

    def test_singleton_same_instance(self):
        """get_instance 多次返回同一实例。"""
        a = PerformanceMonitor.get_instance()
        b = PerformanceMonitor.get_instance()
        assert a is b

    def test_reset_instance_creates_new(self):
        """reset_instance 后创建新实例。"""
        a = PerformanceMonitor.get_instance()
        PerformanceMonitor.reset_instance()
        b = PerformanceMonitor.get_instance()
        assert a is not b

    def test_get_performance_monitor_function(self):
        """模块级 get_performance_monitor 函数。"""
        m = get_performance_monitor()
        assert m is PerformanceMonitor.get_instance()

    def test_default_alerts_registered(self):
        """初始化时应注册默认告警规则。"""
        m = PerformanceMonitor.get_instance()
        rules = m.alert_manager.get_rules()
        rule_names = [r.name for r in rules]
        assert "high_cpu" in rule_names
        assert "high_memory" in rule_names
        assert "high_disk" in rule_names
        assert "process_high_cpu" in rule_names
        assert "process_high_memory" in rule_names

    def test_default_alert_thresholds(self):
        """默认告警阈值正确。"""
        m = PerformanceMonitor.get_instance()
        rules = {r.name: r for r in m.alert_manager.get_rules()}
        assert rules["high_cpu"].warning_threshold == DEFAULT_CPU_WARNING_THRESHOLD
        assert rules["high_cpu"].critical_threshold == DEFAULT_CPU_CRITICAL_THRESHOLD
        assert rules["high_memory"].warning_threshold == DEFAULT_MEM_WARNING_THRESHOLD
        assert rules["high_disk"].warning_threshold == DEFAULT_DISK_WARNING_THRESHOLD


# ===== PerformanceMonitor 快照与历史测试 =====


class TestPerformanceMonitorSnapshot:
    """PerformanceMonitor 快照与历史管理测试。"""

    def test_snapshot_returns_performance_snapshot(self, monitor):
        """snapshot 返回 PerformanceSnapshot。"""
        snap = monitor.snapshot()
        assert isinstance(snap, PerformanceSnapshot)
        assert snap.timestamp > 0

    def test_snapshot_stored_in_history(self, monitor):
        """快照应存入历史。"""
        monitor.snapshot()
        assert len(monitor.get_history()) == 1

    def test_get_history_limit(self, monitor):
        """get_history limit 参数。"""
        for _ in range(5):
            monitor.snapshot()
        assert len(monitor.get_history(limit=3)) == 3
        assert len(monitor.get_history(limit=0)) == 5  # limit=0 表示全部

    def test_get_history_time_range(self, monitor):
        """get_history 时间范围过滤。"""
        # 手动构造历史
        for i in range(5):
            snap = make_snapshot(timestamp=1000.0 + i * 100)
            with monitor._lock:
                monitor._history.append(snap)
        # 时间范围 [1100, 1300]
        result = monitor.get_history(start_ts=1100.0, end_ts=1300.0)
        assert len(result) == 3
        assert result[0].timestamp == 1100.0
        assert result[-1].timestamp == 1300.0

    def test_get_latest(self, monitor):
        """get_latest 返回最近快照。"""
        assert monitor.get_latest() is None
        monitor.snapshot()
        latest = monitor.get_latest()
        assert latest is not None

    def test_clear_history(self, monitor):
        """clear_history 清空历史。"""
        monitor.snapshot()
        monitor.clear_history()
        assert len(monitor.get_history()) == 0
        assert monitor.get_latest() is None

    def test_snapshot_updates_baseline(self, monitor):
        """快照应更新基线。"""
        monitor.snapshot()
        # 基线样本应被更新
        with monitor.baseline._lock:
            assert len(monitor.baseline._samples["cpu.system_percent"]) >= 1

    def test_snapshot_evaluates_alerts(self, monitor):
        """快照应评估告警。"""
        # 设置 sustain_seconds=0 让告警立即触发
        for rule in monitor.alert_manager.get_rules():
            rule.sustain_seconds = 0
        # 构造一个高 CPU 快照
        with patch.object(monitor, "_sample_cpu", return_value=CpuSnapshot(system_percent=95.0)):
            monitor.snapshot()
        # 应有活跃告警
        assert len(monitor.alert_manager.get_active_alerts()) >= 1

    def test_history_capacity_limit(self, monitor):
        """历史容量限制。"""
        # 直接操作内部 deque
        from collections import deque
        monitor._history = deque(maxlen=5)
        for _ in range(10):
            monitor._history.append(make_snapshot())
        assert len(monitor.get_history()) == 5


# ===== PerformanceMonitor 异步采样测试 =====


class TestPerformanceMonitorSampling:
    """PerformanceMonitor 异步采样测试。"""

    def test_is_sampling_default_false(self, monitor):
        """默认不在采样状态。"""
        assert monitor.is_sampling() is False

    @pytest.mark.asyncio
    async def test_start_and_stop_sampling(self, monitor):
        """启动并停止采样。"""
        await monitor.start_sampling(interval=0.05)
        assert monitor.is_sampling() is True
        await asyncio.sleep(0.15)
        assert len(monitor.get_history()) >= 1
        await monitor.stop_sampling()
        assert monitor.is_sampling() is False
        assert monitor._sample_task is None

    @pytest.mark.asyncio
    async def test_start_sampling_idempotent(self, monitor):
        """重复启动采样应幂等。"""
        await monitor.start_sampling(interval=1.0)
        first_task = monitor._sample_task
        await monitor.start_sampling(interval=1.0)
        assert monitor._sample_task is first_task
        await monitor.stop_sampling()

    @pytest.mark.asyncio
    async def test_sampling_collects_multiple(self, monitor):
        """采样应收集多个快照。"""
        await monitor.start_sampling(interval=0.02)
        await asyncio.sleep(0.1)
        await monitor.stop_sampling()
        assert len(monitor.get_history()) >= 2


# ===== PerformanceMonitor 报告生成测试 =====


class TestPerformanceMonitorReport:
    """PerformanceMonitor 报告生成测试。"""

    def test_generate_report_empty(self, monitor):
        """无历史数据时的报告。"""
        report = monitor.generate_report()
        assert report["sample_count"] == 0
        assert "message" in report

    def test_generate_report_with_data(self, monitor):
        """有数据时的报告。"""
        for i in range(3):
            snap = make_snapshot(cpu_sys=50.0 + i, timestamp=1000.0 + i)
            with monitor._lock:
                monitor._history.append(snap)
        report = monitor.generate_report()
        assert report["sample_count"] == 3
        assert "summary" in report
        assert "cpu" in report["summary"]
        assert "latest" in report
        assert "bottlenecks" in report
        assert "alerts" in report

    def test_generate_report_window(self, monitor):
        """带时间窗口的报告。"""
        now = time.time()
        snap = make_snapshot(cpu_sys=50.0, timestamp=now - 10)
        with monitor._lock:
            monitor._history.append(snap)
        report = monitor.generate_report(window_seconds=60)
        assert report["sample_count"] == 1
        # 窗口外的数据不应包含
        old_snap = make_snapshot(cpu_sys=99.0, timestamp=now - 1000)
        with monitor._lock:
            monitor._history.append(old_snap)
        report = monitor.generate_report(window_seconds=60)
        assert report["sample_count"] == 1

    def test_generate_text_report(self, monitor):
        """文本报告生成。"""
        monitor.snapshot()
        text = monitor.generate_text_report()
        assert "ThesisMiner 性能报告" in text
        assert "样本数" in text

    def test_generate_text_report_empty(self, monitor):
        """无数据时的文本报告。"""
        text = monitor.generate_text_report()
        assert "ThesisMiner 性能报告" in text

    def test_summarize_series(self, monitor):
        """_summarize_series 统计摘要。"""
        result = monitor._summarize_series([1.0, 2.0, 3.0, 4.0, 5.0])
        assert result["min"] == 1.0
        assert result["max"] == 5.0
        assert result["avg"] == pytest.approx(3.0)
        assert "p50" in result
        assert "p90" in result
        assert "p99" in result

    def test_summarize_series_empty(self, monitor):
        """空序列统计摘要。"""
        result = monitor._summarize_series([])
        assert result["min"] == 0
        assert result["avg"] == 0


# ===== PerformanceMonitor 瓶颈识别测试 =====


class TestBottleneckIdentification:
    """瓶颈识别测试。"""

    def test_identify_bottlenecks_empty(self, monitor):
        """空快照列表无瓶颈。"""
        assert monitor._identify_bottlenecks([]) == []

    def test_identify_cpu_bottleneck(self, monitor):
        """CPU 瓶颈识别。"""
        snap = make_snapshot(cpu_sys=95.0)
        bottlenecks = monitor._identify_bottlenecks([snap])
        cpu_bottlenecks = [b for b in bottlenecks if b["type"] == "cpu"]
        assert len(cpu_bottlenecks) >= 1
        assert cpu_bottlenecks[0]["severity"] == "critical"

    def test_identify_memory_bottleneck(self, monitor):
        """内存瓶颈识别。"""
        snap = make_snapshot(mem_used=85.0)
        bottlenecks = monitor._identify_bottlenecks([snap])
        mem_bottlenecks = [b for b in bottlenecks if b["type"] == "memory"]
        assert len(mem_bottlenecks) >= 1

    def test_identify_disk_bottleneck(self, monitor):
        """磁盘瓶颈识别。"""
        snap = make_snapshot(disk_used=96.0)
        bottlenecks = monitor._identify_bottlenecks([snap])
        disk_bottlenecks = [b for b in bottlenecks if b["type"] == "disk_space"]
        assert len(disk_bottlenecks) >= 1

    def test_identify_process_memory_bottleneck(self, monitor):
        """进程内存瓶颈识别。"""
        snap = make_snapshot(proc_mem=60.0)
        bottlenecks = monitor._identify_bottlenecks([snap])
        proc_mem_bottlenecks = [b for b in bottlenecks if b["type"] == "process_memory"]
        assert len(proc_mem_bottlenecks) >= 1

    def test_identify_no_bottleneck(self, monitor):
        """正常情况无瓶颈。"""
        snap = make_snapshot(cpu_sys=10.0, mem_used=30.0, disk_used=40.0, proc_mem=10.0)
        bottlenecks = monitor._identify_bottlenecks([snap])
        # 不应有 cpu/memory/disk/process_memory 瓶颈
        types = [b["type"] for b in bottlenecks]
        assert "cpu" not in types
        assert "memory" not in types
        assert "disk_space" not in types


# ===== PerformanceMonitor 趋势分析测试 =====


class TestTrendAnalysis:
    """趋势分析测试。"""

    def test_analyze_trend_insufficient_samples(self, monitor):
        """样本不足时返回 unknown。"""
        result = monitor.analyze_trend("cpu.system_percent")
        assert result["trend"] == "unknown"
        assert "message" in result

    def test_analyze_trend_increasing(self, monitor):
        """上升趋势。"""
        for i in range(10):
            snap = make_snapshot(cpu_sys=float(i), timestamp=1000.0 + i)
            with monitor._lock:
                monitor._history.append(snap)
        result = monitor.analyze_trend("cpu.system_percent")
        assert result["trend"] == "increasing"
        assert result["slope"] > 0
        assert result["sample_count"] == 10

    def test_analyze_trend_decreasing(self, monitor):
        """下降趋势。"""
        for i in range(10):
            snap = make_snapshot(cpu_sys=100.0 - i, timestamp=1000.0 + i)
            with monitor._lock:
                monitor._history.append(snap)
        result = monitor.analyze_trend("cpu.system_percent")
        assert result["trend"] == "decreasing"
        assert result["slope"] < 0

    def test_analyze_trend_stable(self, monitor):
        """稳定趋势。"""
        for i in range(10):
            snap = make_snapshot(cpu_sys=50.0, timestamp=1000.0 + i)
            with monitor._lock:
                monitor._history.append(snap)
        result = monitor.analyze_trend("cpu.system_percent")
        assert result["trend"] == "stable"

    def test_analyze_trend_invalid_path(self, monitor):
        """无效指标路径。"""
        for i in range(5):
            snap = make_snapshot(timestamp=1000.0 + i)
            with monitor._lock:
                monitor._history.append(snap)
        result = monitor.analyze_trend("nonexistent.path")
        assert result["trend"] == "unknown"

    def test_analyze_trend_change_rate(self, monitor):
        """变化率计算。"""
        for i in range(5):
            snap = make_snapshot(cpu_sys=10.0 + i * 10, timestamp=1000.0 + i)
            with monitor._lock:
                monitor._history.append(snap)
        result = monitor.analyze_trend("cpu.system_percent")
        # first=10, last=50, change_rate = (50-10)/10*100 = 400
        assert result["change_rate_percent"] == pytest.approx(400.0)


# ===== PerformanceMonitor 图表数据测试 =====


class TestChartData:
    """图表数据准备测试。"""

    def test_prepare_chart_data_empty(self, monitor):
        """无数据时的图表数据。"""
        result = monitor.prepare_chart_data(["cpu.system_percent"])
        assert "series" in result
        assert "cpu.system_percent" in result["series"]
        assert len(result["series"]["cpu.system_percent"]) == 0

    def test_prepare_chart_data_with_data(self, monitor):
        """有数据时的图表数据。"""
        for i in range(5):
            snap = make_snapshot(cpu_sys=float(i), timestamp=1000.0 + i)
            with monitor._lock:
                monitor._history.append(snap)
        result = monitor.prepare_chart_data(["cpu.system_percent", "memory.used_percent"])
        assert len(result["series"]["cpu.system_percent"]) == 5
        assert len(result["series"]["memory.used_percent"]) == 5
        # 时间戳应为毫秒
        assert result["series"]["cpu.system_percent"][0][0] == 1000.0 * 1000

    def test_prepare_chart_data_downsample(self, monitor):
        """数据点超过 max_points 时降采样。"""
        for i in range(100):
            snap = make_snapshot(cpu_sys=float(i), timestamp=1000.0 + i)
            with monitor._lock:
                monitor._history.append(snap)
        result = monitor.prepare_chart_data(["cpu.system_percent"], max_points=10)
        assert len(result["series"]["cpu.system_percent"]) <= 10
        assert result["point_count"] <= 10


# ===== PerformanceMonitor 持久化测试 =====


class TestPerformanceMonitorPersistence:
    """PerformanceMonitor SQLite 持久化测试。"""

    def test_persist_to_db_empty(self, monitor, tmp_db_path):
        """空历史持久化返回 0。"""
        count = monitor.persist_to_db(tmp_db_path)
        assert count == 0

    def test_persist_to_db_with_data(self, monitor, tmp_db_path):
        """持久化快照到 SQLite。"""
        monitor.snapshot()
        count = monitor.persist_to_db(tmp_db_path)
        assert count == 1
        assert Path(tmp_db_path).exists()

    def test_persist_creates_table(self, monitor, tmp_db_path):
        """持久化应创建表。"""
        monitor.snapshot()
        monitor.persist_to_db(tmp_db_path)
        conn = sqlite3.connect(tmp_db_path)
        try:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='performance_snapshots'"
            )
            assert cursor.fetchone() is not None
        finally:
            conn.close()

    def test_load_from_db(self, monitor, tmp_db_path):
        """从 SQLite 加载快照。"""
        # 先持久化
        snap = make_snapshot(cpu_sys=42.0)
        with monitor._lock:
            monitor._history.append(snap)
        monitor.persist_to_db(tmp_db_path)
        # 重置后加载
        PerformanceMonitor.reset_instance()
        new_monitor = PerformanceMonitor.get_instance()
        loaded = new_monitor.load_from_db(tmp_db_path)
        assert loaded == 1
        history = new_monitor.get_history()
        assert len(history) >= 1
        assert history[-1].cpu.system_percent == pytest.approx(42.0)

    def test_load_from_db_nonexistent(self, monitor):
        """加载不存在的数据库返回 0。"""
        loaded = monitor.load_from_db("/nonexistent/path/db.db")
        assert loaded == 0

    def test_persist_multiple(self, monitor, tmp_db_path):
        """持久化多个快照。"""
        for i in range(5):
            with monitor._lock:
                monitor._history.append(make_snapshot(cpu_sys=float(i)))
        count = monitor.persist_to_db(tmp_db_path)
        assert count == 5


# ===== PerformanceMonitor 导出测试 =====


class TestPerformanceMonitorExport:
    """PerformanceMonitor 导出测试。"""

    def test_export_json(self, monitor):
        """JSON 导出。"""
        monitor.snapshot()
        text = monitor.export_json()
        data = json.loads(text)
        assert "sample_count" in data

    def test_export_json_with_indent(self, monitor):
        """带缩进的 JSON 导出。"""
        monitor.snapshot()
        text = monitor.export_json(indent=2)
        assert "\n" in text

    def test_export_json_empty(self, monitor):
        """空历史 JSON 导出。"""
        text = monitor.export_json()
        data = json.loads(text)
        assert data["sample_count"] == 0


# ===== PerformanceMonitor 关闭测试 =====


class TestPerformanceMonitorShutdown:
    """PerformanceMonitor 资源清理测试。"""

    def test_shutdown_stops_sampling(self, monitor):
        """shutdown 应停止采样。"""
        monitor._sampling = True
        monitor.shutdown()
        assert monitor._sampling is False

    def test_shutdown_clears_process(self, monitor):
        """shutdown 应清理进程对象。"""
        monitor._process = MagicMock()
        monitor.shutdown()
        assert monitor._process is None


# ===== 模块级便捷函数测试 =====


class TestModuleLevelFunctions:
    """模块级便捷函数测试。"""

    def test_quick_snapshot(self, monitor):
        """quick_snapshot 返回字典。"""
        result = quick_snapshot()
        assert isinstance(result, dict)
        assert "cpu" in result
        assert "memory" in result

    def test_check_health_no_data(self, monitor):
        """无数据时健康检查应采集快照。"""
        health = check_health()
        assert "healthy" in health
        assert "cpu_percent" in health
        assert "memory_percent" in health
        assert "bottlenecks" in health
        assert "active_alerts" in health

    def test_check_health_with_data(self, monitor):
        """有数据时健康检查。"""
        monitor.snapshot()
        health = check_health()
        assert "healthy" in health
        assert isinstance(health["bottlenecks"], list)


# ===== psutil 降级测试 =====


class TestPsutilFallback:
    """psutil 缺失时的降级行为测试。"""

    def test_sample_cpu_without_psutil(self):
        """无 psutil 时 CPU 采样返回零值快照。"""
        with patch("backend.analytics.performance_monitor._HAS_PSUTIL", False):
            m = PerformanceMonitor.get_instance()
            snap = m._sample_cpu()
            assert snap.system_percent == 0.0
            assert snap.core_count == 0

    def test_sample_memory_without_psutil(self):
        """无 psutil 时内存采样返回零值快照。"""
        with patch("backend.analytics.performance_monitor._HAS_PSUTIL", False):
            m = PerformanceMonitor.get_instance()
            snap = m._sample_memory()
            assert snap.total_bytes == 0
            assert snap.used_percent == 0.0

    def test_sample_disk_without_psutil(self):
        """无 psutil 时磁盘采样返回零值快照。"""
        with patch("backend.analytics.performance_monitor._HAS_PSUTIL", False):
            m = PerformanceMonitor.get_instance()
            snap = m._sample_disk()
            assert snap.used_percent == 0.0

    def test_sample_network_without_psutil(self):
        """无 psutil 时网络采样返回零值快照。"""
        with patch("backend.analytics.performance_monitor._HAS_PSUTIL", False):
            m = PerformanceMonitor.get_instance()
            snap = m._sample_network()
            assert snap.bytes_sent == 0

    def test_sample_process_without_psutil(self):
        """无 psutil 时进程采样返回基本快照。"""
        with patch("backend.analytics.performance_monitor._HAS_PSUTIL", False):
            m = PerformanceMonitor.get_instance()
            snap = m._sample_process()
            assert snap.pid > 0  # 仍返回当前 PID
            assert snap.cpu_percent == 0.0


# ===== 综合场景测试 =====


class TestIntegrationScenarios:
    """综合场景测试。"""

    def test_full_workflow(self, monitor, tmp_db_path):
        """完整工作流：采样 -> 报告 -> 持久化 -> 加载。"""
        # 1. 采集多个样本
        for i in range(3):
            with monitor._lock:
                monitor._history.append(make_snapshot(cpu_sys=30.0 + i * 10, timestamp=1000.0 + i))
        # 2. 生成报告
        report = monitor.generate_report()
        assert report["sample_count"] == 3
        # 3. 趋势分析
        trend = monitor.analyze_trend("cpu.system_percent")
        assert trend["trend"] == "increasing"
        # 4. 持久化
        count = monitor.persist_to_db(tmp_db_path)
        assert count == 3
        # 5. 加载
        PerformanceMonitor.reset_instance()
        new_monitor = PerformanceMonitor.get_instance()
        loaded = new_monitor.load_from_db(tmp_db_path)
        assert loaded == 3

    def test_alert_workflow(self, monitor):
        """告警工作流：触发 -> 升级 -> 恢复。"""
        # 设置即时触发
        for rule in monitor.alert_manager.get_rules():
            rule.sustain_seconds = 0
        # 1. 触发 warning
        with patch.object(monitor, "_sample_cpu", return_value=CpuSnapshot(system_percent=75.0)):
            monitor.snapshot()
        assert len(monitor.alert_manager.get_active_alerts()) >= 1
        # 2. 升级到 critical
        with patch.object(monitor, "_sample_cpu", return_value=CpuSnapshot(system_percent=95.0)):
            monitor.snapshot()
        active = monitor.alert_manager.get_active_alerts()
        cpu_alerts = [a for a in active if "cpu" in a.rule_name and "process" not in a.rule_name]
        if cpu_alerts:
            assert cpu_alerts[0].level == "critical"
        # 3. 恢复
        with patch.object(monitor, "_sample_cpu", return_value=CpuSnapshot(system_percent=10.0)):
            monitor.snapshot()
        # 告警历史应包含恢复事件
        history = monitor.alert_manager.get_history()
        recovered = [h for h in history if h.level == "recovered"]
        assert len(recovered) >= 1

    def test_dict_to_snapshot_roundtrip(self, monitor):
        """快照字典序列化往返。"""
        original = make_snapshot(cpu_sys=42.0, mem_used=60.0)
        d = original.to_dict()
        restored = monitor._dict_to_snapshot(d)
        assert restored.cpu.system_percent == pytest.approx(42.0)
        assert restored.memory.used_percent == pytest.approx(60.0)

    def test_get_metric_by_path(self, monitor):
        """_get_metric_by_path 路径解析。"""
        snap = make_snapshot(cpu_sys=42.0)
        assert monitor._get_metric_by_path(snap, "cpu.system_percent") == 42.0
        assert monitor._get_metric_by_path(snap, "memory.used_percent") == 40.0
        assert monitor._get_metric_by_path(snap, "nonexistent.path") is None
        # 非数值属性返回 None
        assert monitor._get_metric_by_path(snap, "cpu") is None


# ===== 线程安全测试 =====


class TestThreadSafety:
    """线程安全测试。"""

    def test_concurrent_snapshot(self, monitor):
        """多线程并发快照。"""
        n_threads = 5
        n_per_thread = 10

        def worker():
            for _ in range(n_per_thread):
                monitor.snapshot()

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(monitor.get_history()) == n_threads * n_per_thread

    def test_concurrent_baseline_update(self, monitor):
        """多线程并发更新基线。"""
        n_threads = 5
        n_per_thread = 20

        def worker():
            for i in range(n_per_thread):
                monitor.baseline.update("metric", float(i))

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        with monitor.baseline._lock:
            assert len(monitor.baseline._samples["metric"]) == n_threads * n_per_thread

    def test_concurrent_alert_evaluate(self, monitor):
        """多线程并发评估告警。"""
        rule = AlertRule("test", "cpu.system_percent", 70, 90, sustain_seconds=0)
        monitor.alert_manager.add_rule(rule)

        def worker():
            for _ in range(10):
                monitor.alert_manager.evaluate(make_snapshot(cpu_sys=95.0))

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # 不应抛出异常即视为通过
        assert True
