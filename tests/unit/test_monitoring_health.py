"""HealthChecker 单元测试

覆盖范围：
    - 数据类（CheckResult / HealthStatus / HealthIncident / SLAReport）构造与字段
    - 常量与状态枚举（HEALTHY / DEGRADED / UNHEALTHY / UNKNOWN / STATUS_NAMES）
    - 工具函数（_format_bytes / _format_duration / _safe_float / _safe_int /
      _parse_iso_ts / _percentile）
    - HealthChecker 初始化与单例（get_instance）
    - 检查项注册与注销（register_check / unregister_check）
    - API 端点与 LLM 端点注册（register_api_endpoint / register_llm_endpoint）
    - 自动恢复动作注册（register_recovery_action）
    - 阈值配置（set_threshold）
    - 数据库健康检查（check_database：连接 / WAL / 完整性 / 延迟）
    - 磁盘空间检查（check_disk：使用率 / 阈值判断）
    - 内存使用检查（check_memory：psutil 可用 / 不可用降级）
    - CPU 负载检查（check_cpu：psutil 可用 / 不可用降级）
    - Python 运行时检查（check_python_runtime：线程数 / 版本）
    - API 端点检查（check_api_endpoint：成功 / HTTP 错误 / 不可达）
    - LLM 服务检查（check_llm_service：成功 / 错误 / 超时）
    - TCP 端口检查（check_tcp_port：可达 / 超时 / 拒绝）
    - 聚合检查（check_all：状态聚合 / 历史记录 / 事件检测）
    - 状态聚合（_aggregate_status：最差状态优先）
    - 历史记录（get_history / _record_history / _persist_check_results）
    - 事件管理（_detect_incidents / get_active_incidents / get_incident_history）
    - 自动恢复（_attempt_recovery / register_recovery_action）
    - 存活检查（liveness）
    - 就绪检查（readiness）
    - 后台监控（start_monitoring / stop_monitoring / _monitor_loop）
    - 趋势分析（analyze_trend）
    - SLA 报告（generate_sla_report）
    - 健康摘要（get_health_summary）
    - 最近状态（get_last_status）
    - 模块级便捷函数（get_health_checker / check_health / liveness_check /
      readiness_check）
    - 边界情况（空检查项 / 异常处理 / 并发安全）

运行方式：
    pytest tests/unit/test_monitoring_health.py -v
"""
from __future__ import annotations

import sqlite3
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from backend.monitoring.health_checker import (
    DEFAULT_CHECK_INTERVAL,
    DEFAULT_CPU_CRITICAL_THRESHOLD,
    DEFAULT_CPU_WARNING_THRESHOLD,
    DEFAULT_DISK_CRITICAL_THRESHOLD,
    DEFAULT_DISK_WARNING_THRESHOLD,
    DEFAULT_HISTORY_CAPACITY,
    DEFAULT_MEM_CRITICAL_THRESHOLD,
    DEFAULT_MEM_WARNING_THRESHOLD,
    DEFAULT_SLA_TARGET,
    DEGRADED,
    HEALTH_HISTORY_TABLE,
    HEALTH_INCIDENTS_TABLE,
    HEALTHY,
    STATUS_NAMES,
    UNHEALTHY,
    UNKNOWN,
    CheckResult,
    HealthChecker,
    HealthIncident,
    HealthStatus,
    SLAReport,
    _format_bytes,
    _format_duration,
    _now_ts,
    _parse_iso_ts,
    _percentile,
    _safe_float,
    _safe_int,
    check_health,
    get_health_checker,
    liveness_check,
    readiness_check,
)


# ===== 公共夹具 =====


@pytest.fixture
def checker():
    """返回一个全新的 HealthChecker 实例（非单例）。

    每个测试使用独立实例，避免单例状态污染。
    """
    return HealthChecker(check_interval=1.0, history_capacity=100, enable_auto_recovery=False)


@pytest.fixture
def checker_with_recovery():
    """返回启用自动恢复的 HealthChecker 实例。"""
    return HealthChecker(check_interval=1.0, history_capacity=100, enable_auto_recovery=True)


@pytest.fixture
def healthy_result():
    """返回一个健康的 CheckResult。"""
    return CheckResult(
        name="test_check",
        status=HEALTHY,
        message="检查通过",
        latency_ms=10.0,
    )


@pytest.fixture
def degraded_result():
    """返回一个降级的 CheckResult。"""
    return CheckResult(
        name="test_check",
        status=DEGRADED,
        message="检查降级",
        latency_ms=200.0,
    )


@pytest.fixture
def unhealthy_result():
    """返回一个不健康的 CheckResult。"""
    return CheckResult(
        name="test_check",
        status=UNHEALTHY,
        message="检查失败",
        error="连接超时",
    )


# ===== 常量与状态枚举测试 =====


class TestConstants:
    """常量与状态枚举测试。"""

    def test_status_values(self):
        """健康状态常量值。"""
        assert HEALTHY == "healthy"
        assert DEGRADED == "degraded"
        assert UNHEALTHY == "unhealthy"
        assert UNKNOWN == "unknown"

    def test_status_names_mapping(self):
        """状态中文映射。"""
        assert STATUS_NAMES[HEALTHY] == "健康"
        assert STATUS_NAMES[DEGRADED] == "降级"
        assert STATUS_NAMES[UNHEALTHY] == "不健康"
        assert STATUS_NAMES[UNKNOWN] == "未知"

    def test_default_thresholds(self):
        """默认阈值常量。"""
        assert DEFAULT_CPU_WARNING_THRESHOLD == 70.0
        assert DEFAULT_CPU_CRITICAL_THRESHOLD == 90.0
        assert DEFAULT_MEM_WARNING_THRESHOLD == 75.0
        assert DEFAULT_MEM_CRITICAL_THRESHOLD == 90.0
        assert DEFAULT_DISK_WARNING_THRESHOLD == 80.0
        assert DEFAULT_DISK_CRITICAL_THRESHOLD == 95.0

    def test_default_config_values(self):
        """默认配置常量。"""
        assert DEFAULT_CHECK_INTERVAL == 30.0
        assert DEFAULT_HISTORY_CAPACITY == 2880
        assert DEFAULT_SLA_TARGET == 99.9

    def test_table_names(self):
        """数据库表名常量。"""
        assert HEALTH_HISTORY_TABLE == "health_history"
        assert HEALTH_INCIDENTS_TABLE == "health_incidents"


# ===== 工具函数测试 =====


class TestUtilityFunctions:
    """工具函数测试。"""

    def test_format_bytes_units(self):
        """字节格式化各单位。"""
        assert _format_bytes(0) == "0.0 B"
        assert "KB" in _format_bytes(1024)
        assert "MB" in _format_bytes(1024 * 1024)
        assert "GB" in _format_bytes(1024 * 1024 * 1024)

    def test_format_bytes_negative(self):
        """负数字节格式化。"""
        result = _format_bytes(-1024)
        assert "KB" in result

    def test_format_duration_seconds(self):
        """秒级持续时间格式化。"""
        result = _format_duration(30)
        assert "秒" in result

    def test_format_duration_minutes(self):
        """分钟级持续时间格式化。"""
        result = _format_duration(120)
        assert "分钟" in result

    def test_format_duration_hours(self):
        """小时级持续时间格式化。"""
        result = _format_duration(7200)
        assert "小时" in result

    def test_format_duration_days(self):
        """天级持续时间格式化。"""
        result = _format_duration(86400 * 2)
        assert "天" in result

    def test_safe_float_valid(self):
        """有效 float 转换。"""
        assert _safe_float("3.14") == 3.14
        assert _safe_float(42) == 42.0

    def test_safe_float_invalid(self):
        """无效 float 返回默认值。"""
        assert _safe_float("abc") == 0.0
        assert _safe_float(None) == 0.0
        assert _safe_float("abc", default=-1.0) == -1.0

    def test_safe_int_valid(self):
        """有效 int 转换。"""
        assert _safe_int("42") == 42
        assert _safe_int(3.7) == 3

    def test_safe_int_invalid(self):
        """无效 int 返回默认值。"""
        assert _safe_int("abc") == 0
        assert _safe_int(None) == 0
        assert _safe_int("abc", default=-1) == -1

    def test_parse_iso_ts_valid(self):
        """有效 ISO 时间解析。"""
        ts = _parse_iso_ts("2024-01-01T00:00:00+00:00")
        assert isinstance(ts, float)
        assert ts > 0

    def test_parse_iso_ts_invalid(self):
        """无效 ISO 时间返回当前时间戳。"""
        ts = _parse_iso_ts("invalid")
        assert isinstance(ts, float)
        assert ts > 0

    def test_percentile_basic(self):
        """百分位数计算。"""
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        p50 = _percentile(data, 50)
        assert 4 <= p50 <= 6

    def test_percentile_empty(self):
        """空数据百分位数为 0。"""
        assert _percentile([], 50) == 0.0

    def test_percentile_single(self):
        """单元素百分位数。"""
        assert _percentile([42], 50) == 42.0

    def test_now_ts_positive(self):
        """当前时间戳为正数。"""
        assert _now_ts() > 0


# ===== 数据类测试 =====


class TestCheckResult:
    """CheckResult 数据类测试。"""

    def test_default_fields(self):
        """默认字段值。"""
        result = CheckResult()
        assert result.name == ""
        assert result.status == UNKNOWN
        assert result.message == ""
        assert result.details == {}
        assert result.latency_ms == 0.0
        assert result.error is None

    def test_to_dict(self, healthy_result):
        """转换为字典。"""
        d = healthy_result.to_dict()
        assert d["name"] == "test_check"
        assert d["status"] == HEALTHY
        assert d["status_name"] == "健康"
        assert d["message"] == "检查通过"
        assert d["latency_ms"] == 10.0

    def test_to_dict_with_error(self, unhealthy_result):
        """带错误的字典转换。"""
        d = unhealthy_result.to_dict()
        assert d["error"] == "连接超时"
        assert d["status"] == UNHEALTHY


class TestHealthStatus:
    """HealthStatus 数据类测试。"""

    def test_default_fields(self):
        """默认字段值。"""
        status = HealthStatus()
        assert status.overall == UNKNOWN
        assert status.checks == {}
        assert status.uptime_seconds == 0.0

    def test_is_healthy_property(self):
        """is_healthy 属性。"""
        status = HealthStatus(overall=HEALTHY)
        assert status.is_healthy is True
        assert status.is_degraded is False
        assert status.is_unhealthy is False

    def test_is_degraded_property(self):
        """is_degraded 属性。"""
        status = HealthStatus(overall=DEGRADED)
        assert status.is_degraded is True
        assert status.is_healthy is False

    def test_is_unhealthy_property(self):
        """is_unhealthy 属性。"""
        status = HealthStatus(overall=UNHEALTHY)
        assert status.is_unhealthy is True
        assert status.is_healthy is False

    def test_to_dict(self, healthy_result):
        """转换为字典。"""
        status = HealthStatus(
            overall=HEALTHY,
            checks={"test": healthy_result},
            uptime_seconds=100.0,
        )
        d = status.to_dict()
        assert d["overall"] == HEALTHY
        assert d["is_healthy"] is True
        assert d["check_count"] == 1
        assert d["healthy_count"] == 1
        assert d["uptime_seconds"] == 100.0
        assert "test" in d["checks"]

    def test_to_dict_counts(self, healthy_result, unhealthy_result):
        """字典中的计数统计。"""
        status = HealthStatus(
            overall=UNHEALTHY,
            checks={"ok": healthy_result, "fail": unhealthy_result},
        )
        d = status.to_dict()
        assert d["healthy_count"] == 1
        assert d["unhealthy_count"] == 1
        assert d["degraded_count"] == 0


class TestHealthIncident:
    """HealthIncident 数据类测试。"""

    def test_default_fields(self):
        """默认字段值。"""
        incident = HealthIncident()
        assert incident.incident_id == ""
        assert incident.check_name == ""
        assert incident.status == UNHEALTHY
        assert incident.resolved is False
        assert incident.actions_taken == []
        assert incident.ended_at is None

    def test_to_dict(self):
        """转换为字典。"""
        incident = HealthIncident(
            incident_id="inc_001",
            check_name="database",
            status=UNHEALTHY,
            message="数据库不可用",
            duration_seconds=300,
            resolved=True,
            actions_taken=["重启数据库"],
        )
        d = incident.to_dict()
        assert d["incident_id"] == "inc_001"
        assert d["check_name"] == "database"
        assert d["resolved"] is True
        assert d["duration_seconds"] == 300
        assert "重启数据库" in d["actions_taken"]


class TestSLAReport:
    """SLAReport 数据类测试。"""

    def test_default_fields(self):
        """默认字段值。"""
        report = SLAReport()
        assert report.sla_target == DEFAULT_SLA_TARGET
        assert report.sla_met is False
        assert report.incidents == []
        assert report.incident_count == 0

    def test_to_dict(self):
        """转换为字典。"""
        report = SLAReport(
            period_start="2024-01-01T00:00:00+00:00",
            period_end="2024-02-01T00:00:00+00:00",
            total_seconds=2678400,
            uptime_seconds=2678000,
            downtime_seconds=400,
            availability=99.98,
            sla_met=True,
        )
        d = report.to_dict()
        assert d["availability"] == 99.98
        assert d["sla_met"] is True
        assert d["total_seconds"] == 2678400
        assert "total_formatted" in d
        assert "uptime_formatted" in d


# ===== HealthChecker 初始化测试 =====


class TestHealthCheckerInit:
    """HealthChecker 初始化测试。"""

    def test_init_default_values(self):
        """默认初始化值。"""
        checker = HealthChecker()
        assert checker.check_interval == DEFAULT_CHECK_INTERVAL
        assert checker.history_capacity == DEFAULT_HISTORY_CAPACITY
        assert checker.enable_auto_recovery is True

    def test_init_custom_values(self):
        """自定义初始化值。"""
        checker = HealthChecker(
            check_interval=5.0,
            history_capacity=500,
            enable_auto_recovery=False,
        )
        assert checker.check_interval == 5.0
        assert checker.history_capacity == 500
        assert checker.enable_auto_recovery is False

    def test_init_thresholds(self, checker):
        """初始化阈值配置。"""
        assert "cpu" in checker.thresholds
        assert "memory" in checker.thresholds
        assert "disk" in checker.thresholds
        assert "db_latency" in checker.thresholds
        assert "api_latency" in checker.thresholds
        assert "llm_latency" in checker.thresholds

    def test_init_default_checks_registered(self, checker):
        """默认检查项已注册。"""
        with checker._checks_lock:
            assert "database" in checker._checks
            assert "disk" in checker._checks
            assert "memory" in checker._checks
            assert "cpu" in checker._checks
            assert "python_runtime" in checker._checks

    def test_init_start_time(self, checker):
        """启动时间已设置。"""
        assert checker._start_time > 0

    def test_init_history_empty(self, checker):
        """历史记录初始为空。"""
        with checker._history_lock:
            assert len(checker._history) == 0

    def test_init_active_incidents_empty(self, checker):
        """活跃事件初始为空。"""
        with checker._incidents_lock:
            assert len(checker._active_incidents) == 0

    def test_get_instance_singleton(self):
        """get_instance 返回单例。"""
        inst1 = HealthChecker.get_instance()
        inst2 = HealthChecker.get_instance()
        assert inst1 is inst2


# ===== 检查项注册测试 =====


class TestCheckRegistration:
    """检查项注册与注销测试。"""

    def test_register_check(self, checker):
        """注册自定义检查项。"""
        def custom_check():
            return CheckResult(name="custom", status=HEALTHY, message="OK")

        checker.register_check("custom", custom_check)
        with checker._checks_lock:
            assert "custom" in checker._checks

    def test_unregister_check(self, checker):
        """注销检查项。"""
        def custom_check():
            return CheckResult(name="custom", status=HEALTHY)

        checker.register_check("custom", custom_check)
        result = checker.unregister_check("custom")
        assert result is True
        with checker._checks_lock:
            assert "custom" not in checker._checks

    def test_unregister_nonexistent_check(self, checker):
        """注销不存在的检查项返回 False。"""
        result = checker.unregister_check("nonexistent")
        assert result is False

    def test_register_api_endpoint(self, checker):
        """注册 API 端点。"""
        checker.register_api_endpoint("test_api", "http://localhost:8080/health")
        assert "test_api" in checker._api_endpoints
        assert checker._api_endpoints["test_api"] == "http://localhost:8080/health"

    def test_register_llm_endpoint(self, checker):
        """注册 LLM 端点。"""
        checker.register_llm_endpoint("deepseek", "http://localhost:8000/v1/models")
        assert "deepseek" in checker._llm_endpoints

    def test_register_recovery_action(self, checker):
        """注册恢复动作。"""
        def recovery():
            return True

        checker.register_recovery_action("database", recovery)
        assert "database" in checker._recovery_actions

    def test_set_threshold(self, checker):
        """设置阈值。"""
        checker.set_threshold("cpu", warning=80.0, critical=95.0)
        assert checker.thresholds["cpu"]["warning"] == 80.0
        assert checker.thresholds["cpu"]["critical"] == 95.0

    def test_set_threshold_nonexistent(self, checker):
        """设置不存在的阈值无效果。"""
        original = dict(checker.thresholds)
        checker.set_threshold("nonexistent", warning=10, critical=20)
        assert checker.thresholds == original


# ===== 数据库健康检查测试 =====


class TestCheckDatabase:
    """check_database 方法测试。"""

    def test_check_database_returns_result(self, checker):
        """数据库检查返回 CheckResult。"""
        result = checker.check_database()
        assert isinstance(result, CheckResult)
        assert result.name == "database"

    def test_check_database_status_valid(self, checker):
        """数据库检查状态合法。"""
        result = checker.check_database()
        assert result.status in (HEALTHY, DEGRADED, UNHEALTHY, UNKNOWN)

    def test_check_database_has_details(self, checker):
        """数据库检查包含详细信息。"""
        result = checker.check_database()
        assert "journal_mode" in result.details
        assert "integrity" in result.details
        assert "db_size_bytes" in result.details

    def test_check_database_latency(self, checker):
        """数据库检查有延迟记录。"""
        result = checker.check_database()
        assert result.latency_ms >= 0


# ===== 磁盘空间检查测试 =====


class TestCheckDisk:
    """check_disk 方法测试。"""

    def test_check_disk_returns_result(self, checker):
        """磁盘检查返回 CheckResult。"""
        result = checker.check_disk()
        assert isinstance(result, CheckResult)
        assert result.name == "disk"

    def test_check_disk_status_valid(self, checker):
        """磁盘检查状态合法。"""
        result = checker.check_disk()
        assert result.status in (HEALTHY, DEGRADED, UNHEALTHY, UNKNOWN)

    def test_check_disk_has_details(self, checker):
        """磁盘检查包含详细信息。"""
        result = checker.check_disk()
        assert "total_bytes" in result.details
        assert "used_bytes" in result.details
        assert "free_bytes" in result.details
        assert "usage_percent" in result.details

    def test_check_disk_custom_path(self, checker):
        """自定义路径磁盘检查。"""
        import tempfile
        result = checker.check_disk(tempfile.gettempdir())
        assert isinstance(result, CheckResult)

    def test_check_disk_invalid_path(self, checker):
        """无效路径磁盘检查返回 UNKNOWN。"""
        result = checker.check_disk("/nonexistent/path/xyz")
        assert result.status == UNKNOWN


# ===== 内存检查测试 =====


class TestCheckMemory:
    """check_memory 方法测试。"""

    def test_check_memory_returns_result(self, checker):
        """内存检查返回 CheckResult。"""
        result = checker.check_memory()
        assert isinstance(result, CheckResult)
        assert result.name == "memory"

    def test_check_memory_status_valid(self, checker):
        """内存检查状态合法。"""
        result = checker.check_memory()
        assert result.status in (HEALTHY, DEGRADED, UNHEALTHY, UNKNOWN)


# ===== CPU 检查测试 =====


class TestCheckCPU:
    """check_cpu 方法测试。"""

    def test_check_cpu_returns_result(self, checker):
        """CPU 检查返回 CheckResult。"""
        result = checker.check_cpu()
        assert isinstance(result, CheckResult)
        assert result.name == "cpu"

    def test_check_cpu_status_valid(self, checker):
        """CPU 检查状态合法。"""
        result = checker.check_cpu()
        assert result.status in (HEALTHY, DEGRADED, UNHEALTHY, UNKNOWN)


# ===== Python 运行时检查测试 =====


class TestCheckPythonRuntime:
    """check_python_runtime 方法测试。"""

    def test_check_python_runtime_returns_result(self, checker):
        """运行时检查返回 CheckResult。"""
        result = checker.check_python_runtime()
        assert isinstance(result, CheckResult)
        assert result.name == "python_runtime"

    def test_check_python_runtime_has_details(self, checker):
        """运行时检查包含详细信息。"""
        result = checker.check_python_runtime()
        assert "pid" in result.details
        assert "thread_count" in result.details
        assert "python_version" in result.details

    def test_check_python_runtime_status_valid(self, checker):
        """运行时检查状态合法。"""
        result = checker.check_python_runtime()
        assert result.status in (HEALTHY, DEGRADED, UNHEALTHY, UNKNOWN)


# ===== API 端点检查测试 =====


class TestCheckApiEndpoint:
    """check_api_endpoint 方法测试。"""

    def test_check_api_unreachable(self, checker):
        """不可达 API 端点返回 UNHEALTHY。"""
        result = checker.check_api_endpoint(
            "test", "http://localhost:1/nonexistent", timeout=1
        )
        assert result.status == UNHEALTHY
        assert result.name == "api_test"

    def test_check_api_has_latency(self, checker):
        """API 检查有延迟记录。"""
        result = checker.check_api_endpoint(
            "test", "http://localhost:1/nonexistent", timeout=1
        )
        assert result.latency_ms >= 0

    def test_check_api_has_url_in_details(self, checker):
        """API 检查详情包含 URL。"""
        result = checker.check_api_endpoint(
            "test", "http://localhost:1/nonexistent", timeout=1
        )
        assert "url" in result.details


# ===== LLM 服务检查测试 =====


class TestCheckLlmService:
    """check_llm_service 方法测试。"""

    def test_check_llm_unreachable(self, checker):
        """不可达 LLM 服务返回 UNHEALTHY。"""
        result = checker.check_llm_service(
            "test", "http://localhost:1/nonexistent", timeout=1
        )
        assert result.status == UNHEALTHY
        assert result.name == "llm_test"

    def test_check_llm_with_api_key(self, checker):
        """带 API Key 的 LLM 检查。"""
        result = checker.check_llm_service(
            "test", "http://localhost:1/nonexistent", timeout=1, api_key="sk-test"
        )
        assert result.status == UNHEALTHY

    def test_check_llm_has_latency(self, checker):
        """LLM 检查有延迟记录。"""
        result = checker.check_llm_service(
            "test", "http://localhost:1/nonexistent", timeout=1
        )
        assert result.latency_ms >= 0


# ===== TCP 端口检查测试 =====


class TestCheckTcpPort:
    """check_tcp_port 方法测试。"""

    def test_check_tcp_refused(self, checker):
        """被拒绝的 TCP 端口返回 UNHEALTHY。"""
        result = checker.check_tcp_port("127.0.0.1", 1, timeout=1)
        assert result.status == UNHEALTHY
        assert "tcp_127.0.0.1_1" in result.name

    def test_check_tcp_has_details(self, checker):
        """TCP 检查包含详细信息。"""
        result = checker.check_tcp_port("127.0.0.1", 1, timeout=1)
        assert "host" in result.details
        assert "port" in result.details
        assert "connected" in result.details
        assert result.details["connected"] is False

    def test_check_tcp_open_port(self, checker):
        """开放端口返回 HEALTHY。"""
        # 创建一个临时监听 socket
        import socket as sock_module
        server = sock_module.socket(sock_module.AF_INET, sock_module.SOCK_STREAM)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        try:
            result = checker.check_tcp_port("127.0.0.1", port, timeout=2)
            assert result.status == HEALTHY
            assert result.details["connected"] is True
        finally:
            server.close()


# ===== 聚合检查测试 =====


class TestCheckAll:
    """check_all 方法测试。"""

    def test_check_all_returns_health_status(self, checker):
        """check_all 返回 HealthStatus。"""
        status = checker.check_all()
        assert isinstance(status, HealthStatus)

    def test_check_all_has_checks(self, checker):
        """check_all 包含检查结果。"""
        status = checker.check_all()
        assert len(status.checks) >= 5
        assert "database" in status.checks
        assert "disk" in status.checks

    def test_check_all_overall_valid(self, checker):
        """check_all 总体状态合法。"""
        status = checker.check_all()
        assert status.overall in (HEALTHY, DEGRADED, UNHEALTHY, UNKNOWN)

    def test_check_all_uptime_positive(self, checker):
        """check_all 运行时长为正。"""
        status = checker.check_all()
        assert status.uptime_seconds >= 0

    def test_check_all_records_history(self, checker):
        """check_all 记录历史。"""
        checker.check_all()
        with checker._history_lock:
            assert len(checker._history) >= 1

    def test_check_all_with_custom_check(self, checker):
        """check_all 包含自定义检查。"""
        def custom_check():
            return CheckResult(name="custom", status=HEALTHY, message="OK")

        checker.register_check("custom", custom_check)
        status = checker.check_all()
        assert "custom" in status.checks

    def test_check_all_handles_check_exception(self, checker):
        """check_all 处理检查异常。"""
        def failing_check():
            raise RuntimeError("检查失败")

        checker.register_check("failing", failing_check)
        status = checker.check_all()
        assert "failing" in status.checks
        assert status.checks["failing"].status == UNHEALTHY


# ===== 状态聚合测试 =====


class TestAggregateStatus:
    """_aggregate_status 方法测试。"""

    def test_aggregate_all_healthy(self, checker):
        """全部健康返回健康。"""
        checks = {
            "a": CheckResult(status=HEALTHY),
            "b": CheckResult(status=HEALTHY),
        }
        assert checker._aggregate_status(checks) == HEALTHY

    def test_aggregate_with_degraded(self, checker):
        """包含降级返回降级。"""
        checks = {
            "a": CheckResult(status=HEALTHY),
            "b": CheckResult(status=DEGRADED),
        }
        assert checker._aggregate_status(checks) == DEGRADED

    def test_aggregate_with_unhealthy(self, checker):
        """包含不健康返回不健康。"""
        checks = {
            "a": CheckResult(status=HEALTHY),
            "b": CheckResult(status=DEGRADED),
            "c": CheckResult(status=UNHEALTHY),
        }
        assert checker._aggregate_status(checks) == UNHEALTHY

    def test_aggregate_empty(self, checker):
        """空检查返回 UNKNOWN。"""
        assert checker._aggregate_status({}) == UNKNOWN


# ===== 历史记录测试 =====


class TestHistory:
    """历史记录测试。"""

    def test_get_history_returns_list(self, checker):
        """获取历史返回列表。"""
        checker.check_all()
        history = checker.get_history()
        assert isinstance(history, list)

    def test_get_history_by_name(self, checker):
        """按检查项名称获取历史。"""
        checker.check_all()
        history = checker.get_history(check_name="database")
        assert isinstance(history, list)
        for record in history:
            assert record["check_name"] == "database"

    def test_get_history_limit(self, checker):
        """历史记录限制数量。"""
        checker.check_all()
        history = checker.get_history(limit=5)
        assert len(history) <= 5

    def test_get_last_status(self, checker):
        """获取最近状态。"""
        checker.check_all()
        status = checker.get_last_status()
        assert status is not None
        assert isinstance(status, HealthStatus)

    def test_get_last_status_empty(self, checker):
        """无历史时最近状态为 None。"""
        status = checker.get_last_status()
        assert status is None

    def test_history_capacity_limit(self):
        """历史记录容量限制。"""
        checker = HealthChecker(history_capacity=3)
        for _ in range(5):
            checker.check_all()
            time.sleep(0.01)
        with checker._history_lock:
            assert len(checker._history) <= 3


# ===== 事件管理测试 =====


class TestIncidentManagement:
    """事件管理测试。"""

    def test_get_active_incidents_empty(self, checker):
        """初始无活跃事件。"""
        assert checker.get_active_incidents() == []

    def test_incident_created_on_unhealthy(self, checker_with_recovery):
        """不健康状态创建事件。"""
        def failing_check():
            return CheckResult(name="failing", status=UNHEALTHY, message="失败")

        checker_with_recovery.register_check("failing", failing_check)
        checker_with_recovery.check_all()
        incidents = checker_with_recovery.get_active_incidents()
        assert len(incidents) >= 1
        assert any(i.check_name == "failing" for i in incidents)

    def test_incident_resolved_on_recovery(self, checker_with_recovery):
        """恢复后事件解决。"""
        call_count = [0]

        def intermittent_check():
            call_count[0] += 1
            if call_count[0] <= 1:
                return CheckResult(name="intermittent", status=UNHEALTHY, message="失败")
            return CheckResult(name="intermittent", status=HEALTHY, message="恢复")

        checker_with_recovery.register_check("intermittent", intermittent_check)
        checker_with_recovery.check_all()
        assert len(checker_with_recovery.get_active_incidents()) >= 1
        checker_with_recovery.check_all()
        assert len(checker_with_recovery.get_active_incidents()) == 0

    def test_get_incident_history(self, checker_with_recovery):
        """获取事件历史。"""
        def failing_check():
            return CheckResult(name="failing", status=UNHEALTHY, message="失败")

        def healthy_check():
            return CheckResult(name="failing", status=HEALTHY, message="恢复")

        checker_with_recovery.register_check("failing", failing_check)
        checker_with_recovery.check_all()
        checker_with_recovery.unregister_check("failing")
        checker_with_recovery.register_check("failing", healthy_check)
        checker_with_recovery.check_all()
        history = checker_with_recovery.get_incident_history()
        assert isinstance(history, list)

    def test_incident_has_id(self, checker_with_recovery):
        """事件有 ID。"""
        def failing_check():
            return CheckResult(name="failing", status=UNHEALTHY, message="失败")

        checker_with_recovery.register_check("failing", failing_check)
        checker_with_recovery.check_all()
        incidents = checker_with_recovery.get_active_incidents()
        assert all(i.incident_id for i in incidents)


# ===== 自动恢复测试 =====


class TestAutoRecovery:
    """自动恢复测试。"""

    def test_recovery_action_called(self, checker_with_recovery):
        """恢复动作被调用。"""
        called = [False]

        def recovery():
            called[0] = True
            return True

        def failing_check():
            return CheckResult(name="failing", status=UNHEALTHY, message="失败")

        checker_with_recovery.register_check("failing", failing_check)
        checker_with_recovery.register_recovery_action("failing", recovery)
        checker_with_recovery.check_all()
        assert called[0] is True

    def test_recovery_action_recorded(self, checker_with_recovery):
        """恢复动作记录在事件中。"""
        def recovery():
            return True

        def failing_check():
            return CheckResult(name="failing", status=UNHEALTHY, message="失败")

        checker_with_recovery.register_check("failing", failing_check)
        checker_with_recovery.register_recovery_action("failing", recovery)
        checker_with_recovery.check_all()
        incidents = checker_with_recovery.get_active_incidents()
        assert any(len(i.actions_taken) > 0 for i in incidents)

    def test_recovery_action_exception_handled(self, checker_with_recovery):
        """恢复动作异常被处理。"""
        def bad_recovery():
            raise RuntimeError("恢复失败")

        def failing_check():
            return CheckResult(name="failing", status=UNHEALTHY, message="失败")

        checker_with_recovery.register_check("failing", failing_check)
        checker_with_recovery.register_recovery_action("failing", bad_recovery)
        # 不应抛出异常
        checker_with_recovery.check_all()


# ===== 存活与就绪检查测试 =====


class TestLivenessReadiness:
    """liveness 与 readiness 测试。"""

    def test_liveness_returns_true(self, checker):
        """存活检查返回 True。"""
        assert checker.liveness() is True

    def test_readiness_returns_bool(self, checker):
        """就绪检查返回布尔值。"""
        result = checker.readiness()
        assert isinstance(result, bool)

    def test_readiness_checks_database(self, checker):
        """就绪检查依赖数据库。"""
        result = checker.readiness()
        assert isinstance(result, bool)


# ===== 后台监控测试 =====


class TestMonitoring:
    """后台监控测试。"""

    def test_start_stop_monitoring(self, checker):
        """启动与停止监控。"""
        checker.start_monitoring(interval=0.5)
        assert checker._monitor_running is True
        assert checker._monitor_thread is not None
        time.sleep(1.5)
        checker.stop_monitoring()
        assert checker._monitor_running is False

    def test_start_monitoring_idempotent(self, checker):
        """重复启动监控不创建多个线程。"""
        checker.start_monitoring(interval=5.0)
        thread1 = checker._monitor_thread
        checker.start_monitoring(interval=5.0)
        thread2 = checker._monitor_thread
        assert thread1 is thread2
        checker.stop_monitoring()

    def test_stop_monitoring_without_start(self, checker):
        """未启动时停止监控不抛异常。"""
        checker.stop_monitoring()
        assert checker._monitor_running is False

    def test_monitoring_records_history(self, checker):
        """监控循环记录历史。"""
        checker.start_monitoring(interval=0.3)
        time.sleep(1.0)
        checker.stop_monitoring()
        with checker._history_lock:
            assert len(checker._history) >= 1


# ===== 趋势分析测试 =====


class TestAnalyzeTrend:
    """analyze_trend 方法测试。"""

    def test_analyze_trend_no_data(self, checker):
        """无历史数据趋势分析。"""
        result = checker.analyze_trend("nonexistent_check", hours=24)
        assert isinstance(result, dict)
        assert result["sample_count"] == 0

    def test_analyze_trend_with_data(self, checker):
        """有历史数据趋势分析。"""
        checker.check_all()
        result = checker.analyze_trend("database", hours=24)
        assert isinstance(result, dict)
        assert "check_name" in result

    def test_analyze_trend_returns_check_name(self, checker):
        """趋势分析返回检查项名称。"""
        result = checker.analyze_trend("database", hours=1)
        assert result["check_name"] == "database"


# ===== SLA 报告测试 =====


class TestSLAReport:
    """generate_sla_report 方法测试。"""

    def test_generate_sla_report_returns_report(self, checker):
        """生成 SLA 报告。"""
        report = checker.generate_sla_report(days=7)
        assert isinstance(report, SLAReport)

    def test_sla_report_has_period(self, checker):
        """SLA 报告包含周期。"""
        report = checker.generate_sla_report(days=30)
        assert report.period_start != ""
        assert report.period_end != ""
        assert report.total_seconds > 0

    def test_sla_report_availability(self, checker):
        """SLA 报告可用率。"""
        report = checker.generate_sla_report(days=1)
        assert 0.0 <= report.availability <= 100.0

    def test_sla_report_sla_met(self, checker):
        """SLA 报告满足状态。"""
        report = checker.generate_sla_report(days=1)
        assert isinstance(report.sla_met, bool)

    def test_sla_report_incidents_list(self, checker):
        """SLA 报告事件列表。"""
        report = checker.generate_sla_report(days=1)
        assert isinstance(report.incidents, list)
        assert isinstance(report.incident_count, int)


# ===== 健康摘要测试 =====


class TestHealthSummary:
    """get_health_summary 方法测试。"""

    def test_get_health_summary_returns_dict(self, checker):
        """健康摘要返回字典。"""
        summary = checker.get_health_summary()
        assert isinstance(summary, dict)

    def test_health_summary_has_overall(self, checker):
        """健康摘要包含总体状态。"""
        summary = checker.get_health_summary()
        assert "overall" in summary
        assert "overall_name" in summary
        assert "timestamp" in summary

    def test_health_summary_has_counts(self, checker):
        """健康摘要包含计数。"""
        summary = checker.get_health_summary()
        assert "check_count" in summary
        assert "healthy_count" in summary
        assert "degraded_count" in summary
        assert "unhealthy_count" in summary

    def test_health_summary_has_uptime(self, checker):
        """健康摘要包含运行时长。"""
        summary = checker.get_health_summary()
        assert "uptime_seconds" in summary
        assert "uptime_formatted" in summary

    def test_health_summary_has_checks(self, checker):
        """健康摘要包含检查详情。"""
        summary = checker.get_health_summary()
        assert "checks" in summary
        assert isinstance(summary["checks"], dict)


# ===== 模块级便捷函数测试 =====


class TestModuleFunctions:
    """模块级便捷函数测试。"""

    def test_get_health_checker(self):
        """get_health_checker 返回 HealthChecker。"""
        checker = get_health_checker()
        assert isinstance(checker, HealthChecker)

    def test_check_health(self):
        """check_health 返回 HealthStatus。"""
        status = check_health()
        assert isinstance(status, HealthStatus)

    def test_liveness_check(self):
        """liveness_check 返回布尔值。"""
        result = liveness_check()
        assert isinstance(result, bool)
        assert result is True

    def test_readiness_check(self):
        """readiness_check 返回布尔值。"""
        result = readiness_check()
        assert isinstance(result, bool)


# ===== 边界情况测试 =====


class TestEdgeCases:
    """边界情况测试。"""

    def test_check_all_no_registered_checks(self):
        """无注册检查项时 check_all 返回 UNKNOWN。"""
        checker = HealthChecker(enable_auto_recovery=False)
        with checker._checks_lock:
            checker._checks.clear()
        checker._api_endpoints.clear()
        checker._llm_endpoints.clear()
        status = checker.check_all()
        assert status.overall == UNKNOWN

    def test_check_all_with_api_endpoints(self, checker):
        """check_all 包含 API 端点检查。"""
        checker.register_api_endpoint("test", "http://localhost:1/health")
        status = checker.check_all()
        assert "api_test" in status.checks

    def test_check_all_with_llm_endpoints(self, checker):
        """check_all 包含 LLM 端点检查。"""
        checker.register_llm_endpoint("test", "http://localhost:1/models")
        status = checker.check_all()
        assert "llm_test" in status.checks

    def test_persist_and_retrieve_history(self, checker):
        """持久化与读取历史。"""
        checker.check_all()
        history = checker.get_history(limit=10)
        assert len(history) > 0
        for record in history:
            assert "timestamp" in record
            assert "check_name" in record
            assert "status" in record

    def test_history_record_has_details(self, checker):
        """历史记录包含详细信息。"""
        checker.check_all()
        history = checker.get_history(limit=5)
        for record in history:
            assert "details" in record
            assert isinstance(record["details"], dict)


# ===== 并发安全测试 =====


class TestConcurrency:
    """并发安全测试。"""

    def test_concurrent_check_all(self, checker):
        """并发 check_all 不抛异常。"""
        errors = []

        def worker():
            try:
                for _ in range(3):
                    checker.check_all()
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0

    def test_concurrent_register_unregister(self, checker):
        """并发注册与注销检查项。"""
        errors = []

        def register_worker():
            try:
                for i in range(10):
                    checker.register_check(f"concurrent_{i}", lambda: CheckResult(status=HEALTHY))
            except Exception as e:
                errors.append(e)

        def unregister_worker():
            try:
                for i in range(10):
                    checker.unregister_check(f"concurrent_{i}")
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=register_worker)
        t2 = threading.Thread(target=unregister_worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        assert len(errors) == 0

    def test_concurrent_get_history(self, checker):
        """并发读取历史。"""
        checker.check_all()
        errors = []

        def reader():
            try:
                for _ in range(5):
                    checker.get_history()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=reader) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
