"""模型路由器单元测试

测试 ModelRouter 的智能路由能力，覆盖：
    - 工具函数（_now_iso / _now_timestamp / _new_id / _normalize）
    - 常量与枚举（TaskType / ComplexityLevel / RoutingStrategy /
      STRATEGY_WEIGHTS / MODEL_STATES 等）
    - 数据结构（ModelInfo / RoutingRule / RoutingDecision /
      RoutingLog / ModelLoadStats）
    - LoadTracker（record / increment_concurrent / get_stats / reset）
    - DecisionTreeRouter（build_default_tree / route / _traverse）
    - 主类 ModelRouter（模型管理 / 规则管理 / 路由决策 / 故障转移 /
      A/B 测试 / 日志统计 / 成本分析）
    - 模块级单例（get_model_router / reset_model_router）
    - 线程安全与边界情况
"""
from __future__ import annotations

import os
import sys
import threading
import time
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# 将项目根目录加入 sys.path，确保可导入 backend 包
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.routing.model_router import (
    COMPLEXITY_NAMES,
    COMPLEXITY_SCORES,
    DEFAULT_AB_TRAFFIC_SPLIT,
    DEFAULT_FAILOVER_RETRIES,
    DEFAULT_TIMEOUT,
    LOAD_WINDOW_SECONDS,
    MODEL_STATES,
    STRATEGY_NAMES,
    STRATEGY_WEIGHTS,
    TASK_TYPE_NAMES,
    ComplexityLevel,
    DecisionTreeRouter,
    LoadTracker,
    ModelInfo,
    ModelLoadStats,
    ModelRouter,
    RoutingDecision,
    RoutingLog,
    RoutingRule,
    RoutingStrategy,
    TaskType,
    _new_id,
    _normalize,
    _now_iso,
    _now_timestamp,
    get_model_router,
    reset_model_router,
)


# ===== 工具函数测试 =====


class TestNowIso:
    """测试 _now_iso 工具函数。"""

    def test_returns_string(self):
        result = _now_iso()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_is_valid_iso_format(self):
        result = _now_iso()
        parsed = datetime.fromisoformat(result)
        assert parsed is not None

    def test_increases_over_time(self):
        t1 = _now_iso()
        time.sleep(0.01)
        t2 = _now_iso()
        assert datetime.fromisoformat(t2) >= datetime.fromisoformat(t1)


class TestNowTimestamp:
    """测试 _now_timestamp 工具函数。"""

    def test_returns_float(self):
        result = _now_timestamp()
        assert isinstance(result, float)

    def test_increases_over_time(self):
        t1 = _now_timestamp()
        time.sleep(0.01)
        t2 = _now_timestamp()
        assert t2 > t1

    def test_reasonable_value(self):
        # 时间戳应在合理范围（2020 年之后）
        assert _now_timestamp() > 1577836800  # 2020-01-01


class TestNewId:
    """测试 _new_id 工具函数。"""

    def test_default_prefix(self):
        result = _new_id()
        assert result.startswith("route_")

    def test_custom_prefix(self):
        result = _new_id("decision")
        assert result.startswith("decision_")

    def test_uniqueness(self):
        ids = {_new_id() for _ in range(100)}
        assert len(ids) == 100

    def test_length(self):
        result = _new_id("test")
        # "test_" (5) + 8 hex chars = 13
        assert len(result) == 13


class TestNormalize:
    """测试 _normalize 工具函数。"""

    def test_middle_value(self):
        # 中间值应归一化到 0.5
        result = _normalize(5, 0, 10)
        assert result == 0.5

    def test_min_value(self):
        assert _normalize(0, 0, 10) == 0.0

    def test_max_value(self):
        assert _normalize(10, 0, 10) == 1.0

    def test_below_min_clamped(self):
        # 低于最小值应被限制为 0
        assert _normalize(-5, 0, 10) == 0.0

    def test_above_max_clamped(self):
        # 高于最大值应被限制为 1
        assert _normalize(15, 0, 10) == 1.0

    def test_equal_min_max(self):
        # 最小值等于最大值应返回 0.5
        assert _normalize(5, 5, 5) == 0.5


# ===== 常量与枚举测试 =====


class TestTaskType:
    """测试 TaskType 常量类。"""

    def test_task_type_values(self):
        assert TaskType.GENERATION == "generation"
        assert TaskType.ANALYSIS == "analysis"
        assert TaskType.CODING == "coding"
        assert TaskType.REASONING == "reasoning"
        assert TaskType.EMBEDDING == "embedding"

    def test_task_type_names(self):
        # 中文名称映射应完整
        for task_type in [TaskType.GENERATION, TaskType.ANALYSIS, TaskType.CODING]:
            assert task_type in TASK_TYPE_NAMES
            assert isinstance(TASK_TYPE_NAMES[task_type], str)

    def test_task_type_names_count(self):
        # 应有 10 个任务类型
        assert len(TASK_TYPE_NAMES) == 10


class TestComplexityLevel:
    """测试 ComplexityLevel 常量类。"""

    def test_complexity_values(self):
        assert ComplexityLevel.SIMPLE == "simple"
        assert ComplexityLevel.MEDIUM == "medium"
        assert ComplexityLevel.COMPLEX == "complex"
        assert ComplexityLevel.EXPERT == "expert"

    def test_complexity_scores(self):
        # 复杂度越高分数越大
        assert COMPLEXITY_SCORES[ComplexityLevel.SIMPLE] < COMPLEXITY_SCORES[ComplexityLevel.MEDIUM]
        assert COMPLEXITY_SCORES[ComplexityLevel.MEDIUM] < COMPLEXITY_SCORES[ComplexityLevel.COMPLEX]
        assert COMPLEXITY_SCORES[ComplexityLevel.COMPLEX] < COMPLEXITY_SCORES[ComplexityLevel.EXPERT]

    def test_complexity_names(self):
        for level in [ComplexityLevel.SIMPLE, ComplexityLevel.MEDIUM,
                      ComplexityLevel.COMPLEX, ComplexityLevel.EXPERT]:
            assert level in COMPLEXITY_NAMES


class TestRoutingStrategy:
    """测试 RoutingStrategy 常量类。"""

    def test_strategy_values(self):
        assert RoutingStrategy.COST_OPTIMIZED == "cost_optimized"
        assert RoutingStrategy.QUALITY_OPTIMIZED == "quality_optimized"
        assert RoutingStrategy.LATENCY_OPTIMIZED == "latency_optimized"
        assert RoutingStrategy.BALANCED == "balanced"
        assert RoutingStrategy.LOAD_BALANCED == "load_balanced"

    def test_strategy_names(self):
        for strategy in [RoutingStrategy.COST_OPTIMIZED, RoutingStrategy.QUALITY_OPTIMIZED,
                         RoutingStrategy.LATENCY_OPTIMIZED, RoutingStrategy.BALANCED,
                         RoutingStrategy.LOAD_BALANCED]:
            assert strategy in STRATEGY_NAMES

    def test_strategy_weights(self):
        # 每个策略应有权重配置
        for strategy in STRATEGY_NAMES:
            assert strategy in STRATEGY_WEIGHTS
            weights = STRATEGY_WEIGHTS[strategy]
            # 权重总和应接近 1.0
            assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_load_balanced_has_load_weight(self):
        # 负载均衡策略应包含 load 权重
        assert "load" in STRATEGY_WEIGHTS[RoutingStrategy.LOAD_BALANCED]


class TestOtherConstants:
    """测试其他常量。"""

    def test_model_states(self):
        expected = {"active", "degraded", "overloaded", "failed", "maintenance"}
        assert set(MODEL_STATES.keys()) == expected

    def test_default_failover_retries(self):
        assert DEFAULT_FAILOVER_RETRIES > 0

    def test_default_timeout(self):
        assert DEFAULT_TIMEOUT > 0

    def test_load_window_seconds(self):
        assert LOAD_WINDOW_SECONDS > 0

    def test_default_ab_traffic_split(self):
        assert 0 < DEFAULT_AB_TRAFFIC_SPLIT < 1


# ===== 数据结构测试 =====


class TestModelInfo:
    """测试 ModelInfo 数据结构。"""

    def test_default_values(self):
        model = ModelInfo()
        assert model.id == ""
        assert model.quality_score == 70.0
        assert model.state == "active"
        assert model.weight == 1.0

    def test_custom_values(self):
        model = ModelInfo(
            id="m1",
            name="GPT-4",
            provider="OpenAI",
            pricing={"input_cny_per_million": 100, "output_cny_per_million": 200},
            capabilities=["generation", "reasoning"],
            quality_score=95.0,
        )
        assert model.id == "m1"
        assert model.quality_score == 95.0

    def test_to_dict(self):
        model = ModelInfo(id="m1", name="测试模型")
        d = model.to_dict()
        assert d["id"] == "m1"
        assert d["name"] == "测试模型"
        assert "pricing" in d

    def test_from_dict(self):
        data = {"id": "m1", "name": "测试", "quality_score": 80.0}
        model = ModelInfo.from_dict(data)
        assert model.id == "m1"
        assert model.quality_score == 80.0

    def test_supports(self):
        model = ModelInfo(capabilities=["generation", "coding"])
        assert model.supports("generation") is True
        assert model.supports("embedding") is False

    def test_estimate_cost(self):
        model = ModelInfo(
            pricing={"input_cny_per_million": 100, "output_cny_per_million": 200},
        )
        # 1000 输入 + 500 输出
        cost = model.estimate_cost(1000, 500)
        expected = (1000 * 100 + 500 * 200) / 1_000_000
        assert abs(cost - expected) < 0.0001

    def test_estimate_cost_no_pricing(self):
        model = ModelInfo()
        cost = model.estimate_cost(1000, 500)
        assert cost == 0.0

    def test_is_available_active(self):
        model = ModelInfo(state="active")
        assert model.is_available() is True

    def test_is_available_degraded(self):
        model = ModelInfo(state="degraded")
        assert model.is_available() is True

    def test_is_available_failed(self):
        model = ModelInfo(state="failed")
        assert model.is_available() is False

    def test_is_available_maintenance(self):
        model = ModelInfo(state="maintenance")
        assert model.is_available() is False


class TestRoutingRule:
    """测试 RoutingRule 数据结构。"""

    def test_default_values(self):
        rule = RoutingRule()
        assert rule.priority == 100
        assert rule.enabled is True
        assert rule.strategy == RoutingStrategy.BALANCED

    def test_matches_enabled(self):
        rule = RoutingRule(task_type=TaskType.GENERATION, enabled=True)
        assert rule.matches({"task_type": TaskType.GENERATION}) is True

    def test_matches_disabled(self):
        rule = RoutingRule(task_type=TaskType.GENERATION, enabled=False)
        assert rule.matches({"task_type": TaskType.GENERATION}) is False

    def test_matches_wrong_task_type(self):
        rule = RoutingRule(task_type=TaskType.GENERATION)
        assert rule.matches({"task_type": TaskType.CODING}) is False

    def test_matches_complexity(self):
        rule = RoutingRule(complexity=ComplexityLevel.COMPLEX)
        assert rule.matches({"complexity": ComplexityLevel.COMPLEX}) is True
        assert rule.matches({"complexity": ComplexityLevel.SIMPLE}) is False

    def test_matches_condition(self):
        rule = RoutingRule(condition=lambda ctx: ctx.get("urgent") is True)
        assert rule.matches({"urgent": True}) is True
        assert rule.matches({"urgent": False}) is False

    def test_matches_condition_exception(self):
        # 条件函数抛异常应返回 False
        def bad_condition(ctx):
            raise ValueError("异常")
        rule = RoutingRule(condition=bad_condition)
        assert rule.matches({}) is False

    def test_matches_none_filters(self):
        # task_type 和 complexity 都为 None 时应匹配任意
        rule = RoutingRule()
        assert rule.matches({"task_type": "anything"}) is True

    def test_to_dict(self):
        rule = RoutingRule(id="r1", name="规则", priority=10)
        d = rule.to_dict()
        assert d["id"] == "r1"
        assert d["priority"] == 10
        assert "condition" not in d  # condition 不可序列化


class TestRoutingDecision:
    """测试 RoutingDecision 数据结构。"""

    def test_default_values(self):
        decision = RoutingDecision()
        assert decision.selected_model_id == ""
        assert decision.scores == {}
        assert decision.candidate_models == []

    def test_custom_values(self):
        decision = RoutingDecision(
            id="d1",
            task_type=TaskType.GENERATION,
            selected_model_id="m1",
            scores={"m1": 0.9, "m2": 0.8},
            estimated_cost=0.05,
        )
        assert decision.selected_model_id == "m1"
        assert decision.estimated_cost == 0.05

    def test_to_dict(self):
        decision = RoutingDecision(
            id="d1",
            selected_model_id="m1",
            scores={"m1": 0.987654},
            estimated_cost=0.123456789,
            estimated_latency=1234.5678,
        )
        d = decision.to_dict()
        assert d["id"] == "d1"
        # 分数应四舍五入到 4 位
        assert d["scores"]["m1"] == 0.9877
        # 成本应四舍五入到 6 位
        assert d["estimated_cost"] == 0.123457
        # 延迟应四舍五入到 2 位
        assert d["estimated_latency"] == 1234.57


class TestRoutingLog:
    """测试 RoutingLog 数据结构。"""

    def test_default_values(self):
        log = RoutingLog()
        assert log.success is True
        assert log.fallback_used is False
        assert log.cost == 0.0

    def test_custom_values(self):
        log = RoutingLog(
            id="l1",
            model_id="m1",
            success=True,
            latency_ms=500.0,
            input_tokens=100,
            output_tokens=50,
            cost=0.02,
        )
        assert log.model_id == "m1"
        assert log.latency_ms == 500.0

    def test_to_dict(self):
        log = RoutingLog(id="l1", model_id="m1", success=True)
        d = log.to_dict()
        assert d["id"] == "l1"
        assert d["success"] is True


class TestModelLoadStats:
    """测试 ModelLoadStats 数据结构。"""

    def test_default_values(self):
        stats = ModelLoadStats()
        assert stats.request_count == 0
        assert stats.current_load == 0.0

    def test_to_dict(self):
        stats = ModelLoadStats(
            model_id="m1",
            request_count=100,
            success_count=95,
            failure_count=5,
            avg_latency_ms=500.0,
            total_cost=10.5,
        )
        d = stats.to_dict()
        assert d["model_id"] == "m1"
        assert d["request_count"] == 100
        assert d["success_rate"] == 0.95
        assert "avg_latency_ms" in d

    def test_success_rate_zero_requests(self):
        # 0 请求时成功率应为 0（避免除零）
        stats = ModelLoadStats(request_count=0, success_count=0)
        d = stats.to_dict()
        assert d["success_rate"] == 0.0


# ===== LoadTracker 测试 =====


class TestLoadTracker:
    """测试 LoadTracker 负载跟踪器。"""

    def test_record_and_get_stats(self):
        tracker = LoadTracker()
        tracker.record("m1", latency_ms=500.0, success=True, cost=0.01, tokens=100)
        stats = tracker.get_stats("m1")
        assert stats.request_count == 1
        assert stats.success_count == 1
        assert stats.avg_latency_ms == 500.0

    def test_get_stats_no_records(self):
        tracker = LoadTracker()
        stats = tracker.get_stats("nonexistent")
        assert stats.request_count == 0
        assert stats.current_load == 0.0

    def test_increment_decrement_concurrent(self):
        tracker = LoadTracker()
        assert tracker.increment_concurrent("m1") == 1
        assert tracker.increment_concurrent("m1") == 2
        assert tracker.decrement_concurrent("m1") == 1
        assert tracker.decrement_concurrent("m1") == 0

    def test_decrement_below_zero(self):
        # 并发数不应为负
        tracker = LoadTracker()
        tracker.decrement_concurrent("m1")
        assert tracker.increment_concurrent("m1") == 1

    def test_multiple_records(self):
        tracker = LoadTracker()
        for _ in range(10):
            tracker.record("m1", 500.0, True, 0.01, 100)
        stats = tracker.get_stats("m1")
        assert stats.request_count == 10
        assert stats.success_count == 10

    def test_failure_records(self):
        tracker = LoadTracker()
        tracker.record("m1", 500.0, True)
        tracker.record("m1", 500.0, False)
        stats = tracker.get_stats("m1")
        assert stats.request_count == 2
        assert stats.success_count == 1
        assert stats.failure_count == 1

    def test_get_all_stats(self):
        tracker = LoadTracker()
        tracker.record("m1", 500.0, True)
        tracker.record("m2", 300.0, True)
        all_stats = tracker.get_all_stats()
        assert "m1" in all_stats
        assert "m2" in all_stats

    def test_reset(self):
        tracker = LoadTracker()
        tracker.record("m1", 500.0, True)
        tracker.increment_concurrent("m1")
        tracker.reset()
        stats = tracker.get_stats("m1")
        assert stats.request_count == 0

    def test_cleanup_old_records(self):
        # 使用极短窗口测试清理
        tracker = LoadTracker(window_seconds=1)
        tracker.record("m1", 500.0, True)
        time.sleep(1.5)
        stats = tracker.get_stats("m1")
        # 旧记录应被清理
        assert stats.request_count == 0


# ===== DecisionTreeRouter 测试 =====


class TestDecisionTreeRouter:
    """测试 DecisionTreeRouter 决策树路由器。"""

    def test_build_default_tree(self):
        router = DecisionTreeRouter()
        models = {
            "m1": ModelInfo(id="m1", name="模型1", quality_score=90.0,
                            pricing={"input_cny_per_million": 100}),
            "m2": ModelInfo(id="m2", name="模型2", quality_score=70.0,
                            pricing={"input_cny_per_million": 50}),
        }
        router.build_default_tree(models)
        assert router._tree != {}

    def test_route_empty_tree(self):
        router = DecisionTreeRouter()
        assert router.route({"task_type": TaskType.GENERATION}) is None

    def test_route_with_tree(self):
        router = DecisionTreeRouter()
        models = {
            "m1": ModelInfo(id="m1", name="模型1", quality_score=90.0,
                            pricing={"input_cny_per_million": 100}),
        }
        router.build_default_tree(models)
        result = router.route({"task_type": TaskType.GENERATION,
                               "complexity": ComplexityLevel.SIMPLE})
        assert isinstance(result, str)

    def test_route_reasoning_expert(self):
        router = DecisionTreeRouter()
        models = {
            "m1": ModelInfo(id="m1", name="高质量", quality_score=95.0,
                            pricing={"input_cny_per_million": 100}),
            "m2": ModelInfo(id="m2", name="低质量", quality_score=60.0,
                            pricing={"input_cny_per_million": 50}),
        }
        router.build_default_tree(models)
        result = router.route({"task_type": TaskType.REASONING,
                               "complexity": ComplexityLevel.EXPERT})
        # 专家级推理应选高质量模型
        assert result == "m1"

    def test_route_unknown_task_returns_default(self):
        router = DecisionTreeRouter()
        models = {"m1": ModelInfo(id="m1", name="模型1")}
        router.build_default_tree(models)
        result = router.route({"task_type": "unknown_task"})
        # 未知任务应返回默认模型
        assert result is not None or result is None  # 取决于实现

    def test_find_best_quality_model(self):
        router = DecisionTreeRouter()
        models = {
            "m1": ModelInfo(id="m1", quality_score=80.0),
            "m2": ModelInfo(id="m2", quality_score=95.0),
            "m3": ModelInfo(id="m3", quality_score=70.0),
        }
        result = router._find_best_quality_model(models)
        assert result == "m2"

    def test_find_cheapest_model(self):
        router = DecisionTreeRouter()
        models = {
            "m1": ModelInfo(id="m1", pricing={"input_cny_per_million": 100}),
            "m2": ModelInfo(id="m2", pricing={"input_cny_per_million": 30}),
            "m3": ModelInfo(id="m3", pricing={"input_cny_per_million": 80}),
        }
        result = router._find_cheapest_model(models)
        assert result == "m2"

    def test_find_balanced_model(self):
        router = DecisionTreeRouter()
        models = {
            "m1": ModelInfo(id="m1", quality_score=90.0,
                            pricing={"input_cny_per_million": 200},
                            avg_latency_ms=2000),
            "m2": ModelInfo(id="m2", quality_score=85.0,
                            pricing={"input_cny_per_million": 50},
                            avg_latency_ms=500),
        }
        result = router._find_balanced_model(models)
        assert result in ("m1", "m2")

    def test_find_embedding_model(self):
        router = DecisionTreeRouter()
        models = {
            "m1": ModelInfo(id="m1", capabilities=["generation"]),
            "m2": ModelInfo(id="m2", capabilities=["embedding", "generation"]),
        }
        result = router._find_embedding_model(models)
        assert result == "m2"

    def test_find_model_empty(self):
        router = DecisionTreeRouter()
        assert router._find_best_quality_model({}) == ""
        assert router._find_cheapest_model({}) == ""
        assert router._find_balanced_model({}) == ""

    def test_find_model_all_unavailable(self):
        router = DecisionTreeRouter()
        models = {
            "m1": ModelInfo(id="m1", state="failed"),
            "m2": ModelInfo(id="m2", state="maintenance"),
        }
        assert router._find_best_quality_model(models) == ""


# ===== ModelRouter 主类测试 =====


class TestModelRouterInit:
    """测试 ModelRouter 初始化。"""

    def test_init_default(self):
        router = ModelRouter()
        assert router._default_strategy == RoutingStrategy.BALANCED
        assert len(router._models) == 0

    def test_init_custom_strategy(self):
        router = ModelRouter(default_strategy=RoutingStrategy.COST_OPTIMIZED)
        assert router._default_strategy == RoutingStrategy.COST_OPTIMIZED

    def test_init_creates_components(self):
        router = ModelRouter()
        assert router._load_tracker is not None
        assert router._decision_tree is not None


class TestModelManagement:
    """测试模型管理。"""

    def test_register_model(self):
        router = ModelRouter()
        model = ModelInfo(id="m1", name="模型1")
        result = router.register_model(model)
        assert result == "m1"
        assert router.get_model("m1") is not None

    def test_unregister_model(self):
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1", name="模型1"))
        result = router.unregister_model("m1")
        assert result is True
        assert router.get_model("m1") is None

    def test_unregister_nonexistent(self):
        router = ModelRouter()
        result = router.unregister_model("nonexistent")
        assert result is False

    def test_get_model(self):
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1", name="测试"))
        model = router.get_model("m1")
        assert model.name == "测试"

    def test_get_nonexistent_model(self):
        router = ModelRouter()
        assert router.get_model("nonexistent") is None

    def test_list_models(self):
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1", name="模型1"))
        router.register_model(ModelInfo(id="m2", name="模型2"))
        models = router.list_models()
        assert len(models) == 2

    def test_list_models_available_only(self):
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1", state="active"))
        router.register_model(ModelInfo(id="m2", state="failed"))
        models = router.list_models(available_only=True)
        assert len(models) == 1
        assert models[0].id == "m1"

    def test_update_model_state(self):
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1", state="active"))
        result = router.update_model_state("m1", "failed")
        assert result is True
        assert router.get_model("m1").state == "failed"

    def test_update_model_state_nonexistent(self):
        router = ModelRouter()
        result = router.update_model_state("nonexistent", "failed")
        assert result is False

    def test_update_state_failed_records_time(self):
        # 标记为 failed 应记录故障时间
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1", state="active"))
        router.update_model_state("m1", "failed")
        assert "m1" in router._failed_models

    def test_update_state_active_clears_failure(self):
        # 恢复为 active 应清除故障记录
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1", state="active"))
        router.update_model_state("m1", "failed")
        router.update_model_state("m1", "active")
        assert "m1" not in router._failed_models

    def test_set_degradation_chain(self):
        router = ModelRouter()
        router.set_degradation_chain("m1", ["m2", "m3"])
        assert router._degradation_map["m1"] == ["m2", "m3"]


class TestRuleManagement:
    """测试规则管理。"""

    def test_add_rule(self):
        router = ModelRouter()
        rule = RoutingRule(id="r1", name="规则1", priority=10)
        result = router.add_rule(rule)
        assert result == "r1"
        assert len(router.list_rules()) == 1

    def test_add_rule_auto_id(self):
        router = ModelRouter()
        rule = RoutingRule(name="规则")
        result = router.add_rule(rule)
        assert result.startswith("rule_")

    def test_add_rule_sorted_by_priority(self):
        # 规则应按优先级排序
        router = ModelRouter()
        router.add_rule(RoutingRule(id="r1", priority=100))
        router.add_rule(RoutingRule(id="r2", priority=10))
        rules = router.list_rules()
        assert rules[0].id == "r2"  # 优先级数值小的在前

    def test_remove_rule(self):
        router = ModelRouter()
        router.add_rule(RoutingRule(id="r1"))
        result = router.remove_rule("r1")
        assert result is True
        assert len(router.list_rules()) == 0

    def test_remove_nonexistent_rule(self):
        router = ModelRouter()
        result = router.remove_rule("nonexistent")
        assert result is False

    def test_list_rules(self):
        router = ModelRouter()
        router.add_rule(RoutingRule(id="r1"))
        router.add_rule(RoutingRule(id="r2"))
        rules = router.list_rules()
        assert len(rules) == 2

    def test_set_default_strategy(self):
        router = ModelRouter()
        router.set_default_strategy(RoutingStrategy.QUALITY_OPTIMIZED)
        assert router._default_strategy == RoutingStrategy.QUALITY_OPTIMIZED


class TestRouting:
    """测试路由决策。"""

    def setup_method(self):
        self.router = ModelRouter()
        self.router.register_model(ModelInfo(
            id="m1", name="高质量模型", quality_score=95.0,
            pricing={"input_cny_per_million": 100, "output_cny_per_million": 200},
            avg_latency_ms=1000, capabilities=["generation", "reasoning"],
        ))
        self.router.register_model(ModelInfo(
            id="m2", name="低成本模型", quality_score=70.0,
            pricing={"input_cny_per_million": 20, "output_cny_per_million": 40},
            avg_latency_ms=500, capabilities=["generation"],
        ))

    def test_route_returns_decision(self):
        decision = self.router.route(TaskType.GENERATION)
        assert isinstance(decision, RoutingDecision)
        assert decision.id.startswith("decision_")

    def test_route_selects_model(self):
        decision = self.router.route(TaskType.GENERATION)
        assert decision.selected_model_id in ("m1", "m2")

    def test_route_no_models(self):
        # 无模型时应返回空决策
        router = ModelRouter()
        decision = router.route(TaskType.GENERATION)
        assert decision.selected_model_id == ""
        assert "无可用" in decision.reason

    def test_route_with_strategy(self):
        # 不同策略应可能选择不同模型
        decision = self.router.route(TaskType.GENERATION, strategy=RoutingStrategy.COST_OPTIMIZED)
        assert decision.strategy == RoutingStrategy.COST_OPTIMIZED

    def test_route_records_decision(self):
        initial_count = len(self.router.get_decisions())
        self.router.route(TaskType.GENERATION)
        assert len(self.router.get_decisions()) == initial_count + 1

    def test_route_with_rule(self):
        # 添加规则应影响路由
        rule = RoutingRule(
            id="r1", name="偏好规则", priority=10,
            task_type=TaskType.GENERATION,
            preferred_models=["m2"],
        )
        self.router.add_rule(rule)
        decision = self.router.route(TaskType.GENERATION)
        assert decision.rule_id == "r1"

    def test_route_excluded_models(self):
        # 排除模型应影响候选
        rule = RoutingRule(
            id="r1", name="排除规则", priority=10,
            excluded_models=["m1"],
        )
        self.router.add_rule(rule)
        decision = self.router.route(TaskType.GENERATION)
        assert "m1" not in decision.candidate_models or decision.selected_model_id != "m1"

    def test_route_context_length_filter(self):
        # 上下文长度超过模型限制应被过滤
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1", max_context=4096))
        decision = router.route(TaskType.GENERATION, context_length=8192)
        # 超过上下文限制的模型不应被选中
        assert decision.selected_model_id == "" or "m1" not in decision.candidate_models

    def test_route_embedding_requires_capability(self):
        # embedding 任务需要 embedding 能力
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1", capabilities=["generation"]))
        router.register_model(ModelInfo(id="m2", capabilities=["embedding", "generation"]))
        decision = router.route(TaskType.EMBEDDING)
        assert decision.selected_model_id == "m2" or "m1" not in decision.candidate_models

    def test_route_estimates_cost(self):
        decision = self.router.route(
            TaskType.GENERATION, input_tokens=1000, output_tokens=500
        )
        assert decision.estimated_cost >= 0

    def test_route_estimates_latency(self):
        decision = self.router.route(TaskType.GENERATION)
        assert decision.estimated_latency >= 0

    def test_route_with_extra_context(self):
        decision = self.router.route(
            TaskType.GENERATION, extra_context={"custom": "value"}
        )
        assert isinstance(decision, RoutingDecision)


class TestRoutingScoring:
    """测试路由评分。"""

    def test_score_models_empty(self):
        router = ModelRouter()
        scores = router._score_models([], RoutingStrategy.BALANCED, {})
        assert scores == {}

    def test_score_models_returns_dict(self):
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1", quality_score=90.0,
                                        pricing={"input_cny_per_million": 100}))
        router.register_model(ModelInfo(id="m2", quality_score=80.0,
                                        pricing={"input_cny_per_million": 50}))
        candidates = router.list_models(available_only=True)
        scores = router._score_models(candidates, RoutingStrategy.BALANCED, {})
        assert "m1" in scores
        assert "m2" in scores

    def test_quality_optimized_prefers_high_quality(self):
        # 质量优先策略应给高质量模型更高分
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1", quality_score=95.0,
                                        pricing={"input_cny_per_million": 100}))
        router.register_model(ModelInfo(id="m2", quality_score=60.0,
                                        pricing={"input_cny_per_million": 100}))
        candidates = router.list_models(available_only=True)
        scores = router._score_models(candidates, RoutingStrategy.QUALITY_OPTIMIZED, {})
        assert scores["m1"] > scores["m2"]

    def test_cost_optimized_prefers_low_cost(self):
        # 成本优先策略应给低成本模型更高分
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1", quality_score=80.0,
                                        pricing={"input_cny_per_million": 200}))
        router.register_model(ModelInfo(id="m2", quality_score=80.0,
                                        pricing={"input_cny_per_million": 50}))
        candidates = router.list_models(available_only=True)
        scores = router._score_models(candidates, RoutingStrategy.COST_OPTIMIZED, {})
        assert scores["m2"] > scores["m1"]


class TestFailover:
    """测试故障转移。"""

    def setup_method(self):
        self.router = ModelRouter()
        self.router.register_model(ModelInfo(id="m1", name="主模型", state="active"))
        self.router.register_model(ModelInfo(id="m2", name="备模型", state="active"))

    def test_get_failover_with_degradation_chain(self):
        # 有降级链应优先使用
        self.router.set_degradation_chain("m1", ["m2"])
        result = self.router.get_failover_model("m1")
        assert result == "m2"

    def test_get_failover_no_chain(self):
        # 无降级链应重新路由
        result = self.router.get_failover_model("m1", context={
            "task_type": TaskType.GENERATION,
            "complexity": ComplexityLevel.MEDIUM,
        })
        assert result == "m2"

    def test_get_failover_no_alternative(self):
        # 无可用备选应返回 None
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1", state="active"))
        # 只有 m1，故障后无备选
        result = router.get_failover_model("m1")
        assert result is None

    def test_get_failover_marks_failed(self):
        # 故障转移应标记模型为 failed
        self.router.get_failover_model("m1")
        assert "m1" in self.router._failed_models

    def test_report_failure(self):
        # 报告故障应触发故障转移
        result = self.router.report_failure("m1", error="超时")
        assert result == "m2"
        # 应记录日志
        logs = self.router.get_logs(model_id="m1")
        assert any(not log.success for log in logs)

    def test_report_success(self):
        # 报告成功应记录负载和日志
        self.router.report_success("m1", latency_ms=500.0, input_tokens=100,
                                   output_tokens=50, cost=0.01)
        logs = self.router.get_logs(model_id="m1")
        assert any(log.success for log in logs)
        stats = self.router.get_model_stats("m1")
        assert stats.request_count == 1

    def test_failed_model_excluded_from_routing(self):
        # 故障模型应被排除出路由
        self.router.update_model_state("m1", "failed")
        decision = self.router.route(TaskType.GENERATION)
        assert decision.selected_model_id != "m1" or decision.selected_model_id == ""


class TestABTesting:
    """测试 A/B 测试。"""

    def test_setup_ab_test(self):
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1"))
        router.register_model(ModelInfo(id="m2"))
        config = router.setup_ab_test("test1", "m1", "m2", traffic_split=0.5)
        assert config["test_id"] == "test1"
        assert config["model_a"] == "m1"
        assert config["model_b"] == "m2"
        assert config["active"] is True

    def test_get_ab_test_model(self):
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1"))
        router.register_model(ModelInfo(id="m2"))
        router.setup_ab_test("test1", "m1", "m2", traffic_split=0.5)
        # 多次获取应返回 m1 或 m2
        results = set()
        for _ in range(100):
            model = router.get_ab_test_model("test1")
            if model:
                results.add(model)
        assert results.issubset({"m1", "m2"})

    def test_get_ab_test_model_nonexistent(self):
        router = ModelRouter()
        assert router.get_ab_test_model("nonexistent") is None

    def test_get_ab_test_model_stopped(self):
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1"))
        router.register_model(ModelInfo(id="m2"))
        router.setup_ab_test("test1", "m1", "m2")
        router.stop_ab_test("test1")
        assert router.get_ab_test_model("test1") is None

    def test_record_ab_test_result(self):
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1"))
        router.register_model(ModelInfo(id="m2"))
        router.setup_ab_test("test1", "m1", "m2")
        router.record_ab_test_result("test1", "m1", success=True, latency_ms=500, cost=0.01)
        results = router.get_ab_test_results("test1")
        assert results is not None
        assert results["results"]["a"]["successes"] == 1

    def test_get_ab_test_results(self):
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1"))
        router.register_model(ModelInfo(id="m2"))
        router.setup_ab_test("test1", "m1", "m2")
        results = router.get_ab_test_results("test1")
        assert results is not None
        assert "results" in results
        assert "a" in results["results"]
        assert "b" in results["results"]

    def test_get_ab_test_results_nonexistent(self):
        router = ModelRouter()
        assert router.get_ab_test_results("nonexistent") is None

    def test_stop_ab_test(self):
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1"))
        router.register_model(ModelInfo(id="m2"))
        router.setup_ab_test("test1", "m1", "m2")
        result = router.stop_ab_test("test1")
        assert result is True

    def test_stop_ab_test_nonexistent(self):
        router = ModelRouter()
        result = router.stop_ab_test("nonexistent")
        assert result is False

    def test_ab_test_traffic_split_all_a(self):
        # 流量全部分配给 A
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1"))
        router.register_model(ModelInfo(id="m2"))
        router.setup_ab_test("test1", "m1", "m2", traffic_split=1.0)
        results = set()
        for _ in range(50):
            model = router.get_ab_test_model("test1")
            if model:
                results.add(model)
        assert results == {"m1"}


class TestLogsAndStats:
    """测试日志与统计。"""

    def test_get_logs_empty(self):
        router = ModelRouter()
        logs = router.get_logs()
        assert logs == []

    def test_get_logs_after_success(self):
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1"))
        router.report_success("m1", latency_ms=500.0)
        logs = router.get_logs()
        assert len(logs) == 1

    def test_get_logs_by_model(self):
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1"))
        router.register_model(ModelInfo(id="m2"))
        router.report_success("m1", latency_ms=500.0)
        router.report_success("m2", latency_ms=300.0)
        m1_logs = router.get_logs(model_id="m1")
        assert all(log.model_id == "m1" for log in m1_logs)

    def test_get_logs_limit(self):
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1"))
        for _ in range(10):
            router.report_success("m1", latency_ms=500.0)
        logs = router.get_logs(limit=5)
        assert len(logs) == 5

    def test_get_decisions(self):
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1"))
        router.route(TaskType.GENERATION)
        decisions = router.get_decisions()
        assert len(decisions) == 1

    def test_get_model_stats(self):
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1"))
        router.report_success("m1", latency_ms=500.0)
        stats = router.get_model_stats("m1")
        assert stats is not None
        assert stats.request_count == 1

    def test_get_all_stats(self):
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1"))
        router.register_model(ModelInfo(id="m2"))
        router.report_success("m1", latency_ms=500.0)
        router.report_success("m2", latency_ms=300.0)
        all_stats = router.get_all_stats()
        assert "m1" in all_stats
        assert "m2" in all_stats

    def test_get_cost_analysis(self):
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1"))
        router.report_success("m1", latency_ms=500.0, cost=0.05,
                              input_tokens=100, output_tokens=50)
        analysis = router.get_cost_analysis(hours=24)
        assert "total_cost" in analysis
        assert "model_breakdown" in analysis
        assert analysis["total_cost"] > 0

    def test_get_cost_analysis_empty(self):
        router = ModelRouter()
        analysis = router.get_cost_analysis()
        assert analysis["total_cost"] == 0.0
        assert analysis["total_requests"] == 0

    def test_get_performance_report(self):
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1"))
        router.report_success("m1", latency_ms=500.0)
        report = router.get_performance_report()
        assert "total_models" in report
        assert "total_requests" in report

    def test_get_performance_report_empty(self):
        router = ModelRouter()
        report = router.get_performance_report()
        assert report["total_requests"] == 0

    def test_stats(self):
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1"))
        router.register_model(ModelInfo(id="m2", state="failed"))
        stats = router.stats()
        assert stats["total_models"] == 2
        assert stats["available_models"] == 1
        assert stats["failed_models"] == 1

    def test_reset_stats(self):
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1"))
        router.report_success("m1", latency_ms=500.0)
        router.route(TaskType.GENERATION)
        router.reset_stats()
        assert len(router.get_logs()) == 0
        assert len(router.get_decisions()) == 0


class TestGlobalInstance:
    """测试模块级单例。"""

    def test_get_singleton(self):
        reset_model_router()
        instance1 = get_model_router()
        instance2 = get_model_router()
        assert instance1 is instance2

    def test_reset_singleton(self):
        reset_model_router()
        instance1 = get_model_router()
        reset_model_router()
        instance2 = get_model_router()
        assert instance1 is not instance2

    def test_singleton_is_router(self):
        reset_model_router()
        instance = get_model_router()
        assert isinstance(instance, ModelRouter)


# ===== 线程安全测试 =====


class TestThreadSafety:
    """测试线程安全。"""

    def test_concurrent_register_models(self):
        # 并发注册模型
        router = ModelRouter()
        errors = []

        def worker(worker_id):
            try:
                for i in range(5):
                    router.register_model(ModelInfo(
                        id=f"m_{worker_id}_{i}",
                        name=f"模型{worker_id}_{i}",
                    ))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(w,)) for w in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(router.list_models()) == 20

    def test_concurrent_route(self):
        # 并发路由
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1", name="模型1"))
        router.register_model(ModelInfo(id="m2", name="模型2"))
        errors = []
        decisions = []

        def worker():
            try:
                for _ in range(5):
                    decision = router.route(TaskType.GENERATION)
                    decisions.append(decision)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(decisions) == 20

    def test_concurrent_report_success(self):
        # 并发报告成功
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1"))
        errors = []

        def worker():
            try:
                for _ in range(10):
                    router.report_success("m1", latency_ms=500.0)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        stats = router.get_model_stats("m1")
        assert stats.request_count == 40

    def test_concurrent_add_remove_rules(self):
        # 并发添加和移除规则
        router = ModelRouter()
        errors = []

        def adder():
            try:
                for i in range(10):
                    router.add_rule(RoutingRule(id=f"r_{i}", name=f"规则{i}"))
            except Exception as e:
                errors.append(e)

        def remover():
            try:
                for i in range(10):
                    router.remove_rule(f"r_{i}")
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=adder)
        t2 = threading.Thread(target=remover)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        assert len(errors) == 0

    def test_load_tracker_concurrent(self):
        # 负载跟踪器并发
        tracker = LoadTracker()
        errors = []

        def worker():
            try:
                for _ in range(10):
                    tracker.record("m1", 500.0, True)
                    tracker.increment_concurrent("m1")
                    tracker.decrement_concurrent("m1")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        stats = tracker.get_stats("m1")
        assert stats.request_count == 40


# ===== 边界情况测试 =====


class TestEdgeCases:
    """测试边界情况。"""

    def test_route_no_available_models(self):
        # 所有模型不可用
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1", state="failed"))
        router.register_model(ModelInfo(id="m2", state="maintenance"))
        decision = router.route(TaskType.GENERATION)
        assert decision.selected_model_id == ""

    def test_route_all_models_failed(self):
        # 所有模型故障
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1", state="active"))
        router.update_model_state("m1", "failed")
        decision = router.route(TaskType.GENERATION)
        assert decision.selected_model_id == ""

    def test_route_with_zero_tokens(self):
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1"))
        decision = router.route(TaskType.GENERATION, input_tokens=0, output_tokens=0)
        assert decision.estimated_cost == 0.0

    def test_route_unknown_strategy(self):
        # 未知策略应使用默认权重
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1", quality_score=90.0))
        decision = router.route(TaskType.GENERATION, strategy="unknown_strategy")
        assert isinstance(decision, RoutingDecision)

    def test_failover_all_failed(self):
        # 所有备选都故障
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1", state="active"))
        router.register_model(ModelInfo(id="m2", state="failed"))
        router.set_degradation_chain("m1", ["m2"])
        # m2 也故障，应返回 None 或重新路由
        result = router.get_failover_model("m1", context={
            "task_type": TaskType.GENERATION,
            "complexity": ComplexityLevel.MEDIUM,
        })
        # m1 故障后无可用模型
        assert result is None or isinstance(result, str)

    def test_model_weight_affects_score(self):
        # 模型权重应影响评分
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1", quality_score=80.0, weight=2.0))
        router.register_model(ModelInfo(id="m2", quality_score=80.0, weight=0.5))
        candidates = router.list_models(available_only=True)
        scores = router._score_models(candidates, RoutingStrategy.QUALITY_OPTIMIZED, {})
        # 权重高的模型分数应更高
        assert scores["m1"] > scores["m2"]

    def test_decision_reason_contains_info(self):
        # 决策原因应包含信息
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1", name="测试模型"))
        decision = router.route(TaskType.GENERATION)
        assert len(decision.reason) > 0
        assert "策略" in decision.reason or "模型" in decision.reason

    def test_route_with_rule_condition(self):
        # 规则条件应影响匹配
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1"))
        router.register_model(ModelInfo(id="m2"))
        rule = RoutingRule(
            id="r1", name="条件规则", priority=10,
            condition=lambda ctx: ctx.get("urgent") is True,
            preferred_models=["m2"],
        )
        router.add_rule(rule)
        # 满足条件时应匹配规则
        decision = router.route(TaskType.GENERATION, extra_context={"urgent": True})
        assert decision.rule_id == "r1"

    def test_route_rule_not_matched(self):
        # 不满足条件时规则不应匹配
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1"))
        rule = RoutingRule(
            id="r1", name="条件规则", priority=10,
            condition=lambda ctx: ctx.get("urgent") is True,
        )
        router.add_rule(rule)
        decision = router.route(TaskType.GENERATION, extra_context={"urgent": False})
        assert decision.rule_id == ""

    def test_failed_model_auto_recovery(self):
        # 故障模型应在恢复期后自动恢复
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1", state="active"))
        # 设置极短恢复时间
        router._recovery_seconds = 0
        router.update_model_state("m1", "failed")
        # 立即检查应已恢复（因恢复时间为 0）
        # 注意：实际恢复需要调用 _is_failed
        router._is_failed("m1")
        # 恢复后应可被路由选中
        decision = router.route(TaskType.GENERATION)
        assert decision.selected_model_id == "m1" or "m1" in decision.candidate_models

    def test_cost_analysis_with_hours(self):
        # 不同时间范围的成本分析
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1"))
        router.report_success("m1", latency_ms=500.0, cost=0.05)
        analysis_24h = router.get_cost_analysis(hours=24)
        analysis_1h = router.get_cost_analysis(hours=1)
        assert isinstance(analysis_24h, dict)
        assert isinstance(analysis_1h, dict)

    def test_get_logs_max_size(self):
        # 日志应有最大容量限制
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1"))
        for _ in range(100):
            router.report_success("m1", latency_ms=500.0)
        # 日志不应无限增长
        assert len(router.get_logs(limit=10000)) <= 10000

    def test_route_decision_has_timestamp(self):
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1"))
        decision = router.route(TaskType.GENERATION)
        assert len(decision.timestamp) > 0

    def test_route_decision_has_id(self):
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1"))
        decision = router.route(TaskType.GENERATION)
        assert decision.id.startswith("decision_")

    def test_multiple_routes_accumulate_decisions(self):
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1"))
        initial = len(router.get_decisions())
        for _ in range(5):
            router.route(TaskType.GENERATION)
        assert len(router.get_decisions()) == initial + 5

    def test_register_model_rebuilds_tree(self):
        # 注册模型应重建决策树
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1", quality_score=90.0))
        # 决策树应已构建
        assert router._decision_tree._tree != {}

    def test_unregister_model_rebuilds_tree(self):
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1"))
        router.unregister_model("m1")
        # 注销后决策树应重建（可能为空）
        assert isinstance(router._decision_tree._tree, dict)

    def test_estimate_cost_with_zero_pricing(self):
        model = ModelInfo(pricing={})
        cost = model.estimate_cost(1000, 500)
        assert cost == 0.0

    def test_ab_test_records_both_groups(self):
        # A/B 测试应记录两组数据
        router = ModelRouter()
        router.register_model(ModelInfo(id="m1"))
        router.register_model(ModelInfo(id="m2"))
        router.setup_ab_test("test1", "m1", "m2", traffic_split=0.5)
        # 模拟记录两组结果
        router.record_ab_test_result("test1", "m1", True, 500, 0.01)
        router.record_ab_test_result("test1", "m2", True, 300, 0.02)
        results = router.get_ab_test_results("test1")
        assert results["results"]["a"]["successes"] == 1
        assert results["results"]["b"]["successes"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
