"""预算估算模块单元测试

测试 backend/budgets/estimator.py。
覆盖以下功能：
  - MODEL_PRICING_LEGACY_USD: 旧版模型定价表
  - _DEFAULT_PRICING_CNY: 默认回退定价
  - USD_TO_CNY_RATE: 美元兑人民币汇率
  - _MODE_TOKEN_ESTIMATE: 模式 token 估算
  - estimate_cost: 费用计算
  - get_model_for_degree: 按学位选择模型
  - estimate_session_budget: 会话级预算估算

测试策略：
  - 纯逻辑测试为主
  - 覆盖 CNY/USD 两种货币
  - 边界条件：零 token、未知模型、不同学位
"""
import os
import sys

import pytest

# ===== 项目根目录加入 sys.path =====
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.budgets.estimator import (
    MODEL_PRICING_LEGACY_USD,
    _DEFAULT_PRICING_CNY,
    USD_TO_CNY_RATE,
    _MODE_TOKEN_ESTIMATE,
    estimate_cost,
    get_model_for_degree,
    estimate_session_budget,
)


# ===== 测试类：MODEL_PRICING_LEGACY_USD =====

class TestModelPricingLegacy:
    """测试 MODEL_PRICING_LEGACY_USD 常量。"""

    def test_is_dict(self):
        """应为字典。"""
        assert isinstance(MODEL_PRICING_LEGACY_USD, dict)

    def test_not_empty(self):
        """不应为空。"""
        assert len(MODEL_PRICING_LEGACY_USD) > 0

    def test_contains_input_output_keys(self):
        """每个模型定价应含 input 与 output。"""
        for model, pricing in MODEL_PRICING_LEGACY_USD.items():
            assert "input" in pricing
            assert "output" in pricing

    def test_pricing_values_positive(self):
        """定价值应为正数。"""
        for model, pricing in MODEL_PRICING_LEGACY_USD.items():
            assert pricing["input"] > 0
            assert pricing["output"] > 0


# ===== 测试类：_DEFAULT_PRICING_CNY =====

class TestDefaultPricingCny:
    """测试 _DEFAULT_PRICING_CNY 常量。"""

    def test_contains_input_key(self):
        """应含 input_cny_per_million。"""
        assert "input_cny_per_million" in _DEFAULT_PRICING_CNY

    def test_contains_output_key(self):
        """应含 output_cny_per_million。"""
        assert "output_cny_per_million" in _DEFAULT_PRICING_CNY

    def test_values_positive(self):
        """值应为正数。"""
        assert _DEFAULT_PRICING_CNY["input_cny_per_million"] > 0
        assert _DEFAULT_PRICING_CNY["output_cny_per_million"] > 0


# ===== 测试类：USD_TO_CNY_RATE =====

class TestUsdToCnyRate:
    """测试 USD_TO_CNY_RATE 常量。"""

    def test_is_positive(self):
        """应为正数。"""
        assert USD_TO_CNY_RATE > 0

    def test_reasonable_value(self):
        """应在合理范围内（6-8）。"""
        assert 6 <= USD_TO_CNY_RATE <= 8


# ===== 测试类：_MODE_TOKEN_ESTIMATE =====

class TestModeTokenEstimate:
    """测试 _MODE_TOKEN_ESTIMATE 常量。"""

    def test_contains_quick_mode(self):
        """应含 quick 模式。"""
        assert "quick" in _MODE_TOKEN_ESTIMATE

    def test_contains_deep_mode(self):
        """应含 deep 模式。"""
        assert "deep" in _MODE_TOKEN_ESTIMATE

    def test_quick_mode_tokens(self):
        """quick 模式 token 估算应正确。"""
        quick = _MODE_TOKEN_ESTIMATE["quick"]
        assert "prompt_tokens" in quick
        assert "completion_tokens" in quick

    def test_deep_mode_more_tokens_than_quick(self):
        """deep 模式 token 应多于 quick。"""
        quick_total = (_MODE_TOKEN_ESTIMATE["quick"]["prompt_tokens"]
                      + _MODE_TOKEN_ESTIMATE["quick"]["completion_tokens"])
        deep_total = (_MODE_TOKEN_ESTIMATE["deep"]["prompt_tokens"]
                     + _MODE_TOKEN_ESTIMATE["deep"]["completion_tokens"])
        assert deep_total > quick_total


# ===== 测试类：estimate_cost =====

class TestEstimateCost:
    """测试 estimate_cost 函数。"""

    def test_returns_float(self):
        """应返回浮点数。"""
        cost = estimate_cost("deepseek-chat", 100, 50)
        assert isinstance(cost, float)

    def test_zero_tokens_zero_cost(self):
        """零 token 应返回零费用。"""
        cost = estimate_cost("deepseek-chat", 0, 0)
        assert cost == 0.0

    def test_positive_cost_for_tokens(self):
        """有 token 应返回正费用。"""
        cost = estimate_cost("deepseek-chat", 1000, 500)
        assert cost > 0

    def test_cny_currency(self):
        """CNY 模式应返回人民币。"""
        cost_cny = estimate_cost("deepseek-chat", 1000, 500, currency="CNY")
        assert isinstance(cost_cny, float)

    def test_usd_currency(self):
        """USD 模式应返回美元。"""
        cost_usd = estimate_cost("deepseek-chat", 1000, 500, currency="USD")
        assert isinstance(cost_usd, float)

    def test_usd_less_than_cny(self):
        """USD 费用应小于 CNY 费用。"""
        cost_cny = estimate_cost("deepseek-chat", 1000, 500, currency="CNY")
        cost_usd = estimate_cost("deepseek-chat", 1000, 500, currency="USD")
        assert cost_usd < cost_cny

    def test_more_tokens_higher_cost(self):
        """更多 token 应产生更高费用。"""
        cost_low = estimate_cost("deepseek-chat", 100, 50)
        cost_high = estimate_cost("deepseek-chat", 1000, 500)
        assert cost_high > cost_low

    def test_unknown_model_uses_default(self):
        """未知模型应使用默认定价。"""
        cost = estimate_cost("unknown-model-xyz", 1000, 500)
        assert cost > 0

    def test_new_model_from_registry(self):
        """v9.0 新模型应从注册表读取定价。"""
        # deepseek-v4 是 v9.0 新模型
        cost = estimate_cost("deepseek-v4", 1000, 500)
        assert cost > 0

    def test_cost_rounded(self):
        """费用应被四舍五入到 6 位小数。"""
        cost = estimate_cost("deepseek-chat", 100, 50)
        # 检查小数位数不超过 6
        assert round(cost, 6) == cost


# ===== 测试类：get_model_for_degree =====

class TestGetModelForDegree:
    """测试 get_model_for_degree 函数。"""

    def test_master_returns_model(self):
        """硕士应返回模型名。"""
        model = get_model_for_degree("master")
        assert isinstance(model, str)
        assert len(model) > 0

    def test_doctor_returns_model(self):
        """博士应返回模型名。"""
        model = get_model_for_degree("doctor")
        assert isinstance(model, str)
        assert len(model) > 0

    def test_doctor_different_from_master(self):
        """博士与硕士模型应不同。"""
        master_model = get_model_for_degree("master")
        doctor_model = get_model_for_degree("doctor")
        assert master_model != doctor_model

    def test_unknown_degree_returns_default(self):
        """未知学位应返回默认（master）模型。"""
        model = get_model_for_degree("unknown")
        assert isinstance(model, str)


# ===== 测试类：estimate_session_budget =====

class TestEstimateSessionBudget:
    """测试 estimate_session_budget 函数。"""

    def test_returns_dict(self):
        """应返回字典。"""
        result = estimate_session_budget("master")
        assert isinstance(result, dict)

    def test_contains_required_fields(self):
        """应包含所有必需字段。"""
        result = estimate_session_budget("master")
        assert "degree" in result
        assert "mode" in result
        assert "count" in result
        assert "model" in result
        assert "currency" in result
        assert "estimated_tokens_per_call" in result
        assert "estimated_total_tokens" in result
        assert "estimated_cost" in result

    def test_master_degree_budget(self):
        """硕士预算估算。"""
        result = estimate_session_budget("master")
        assert result["degree"] == "master"
        assert result["count"] == 3

    def test_doctor_degree_budget(self):
        """博士预算估算。"""
        result = estimate_session_budget("doctor")
        assert result["degree"] == "doctor"

    def test_quick_mode(self):
        """quick 模式预算。"""
        result = estimate_session_budget("master", mode="quick")
        assert result["mode"] == "quick"

    def test_deep_mode(self):
        """deep 模式预算。"""
        result = estimate_session_budget("master", mode="deep")
        assert result["mode"] == "deep"

    def test_custom_count(self):
        """自定义数量。"""
        result = estimate_session_budget("master", count=5)
        assert result["count"] == 5

    def test_total_tokens_scale_with_count(self):
        """总 token 应随数量缩放。"""
        result3 = estimate_session_budget("master", count=3)
        result5 = estimate_session_budget("master", count=5)
        assert result5["estimated_total_tokens"]["total_tokens"] > result3["estimated_total_tokens"]["total_tokens"]

    def test_deep_mode_more_tokens(self):
        """deep 模式应有更多 token。"""
        quick = estimate_session_budget("master", mode="quick")
        deep = estimate_session_budget("master", mode="deep")
        assert deep["estimated_tokens_per_call"]["total_tokens"] > quick["estimated_tokens_per_call"]["total_tokens"]

    def test_estimated_cost_positive(self):
        """估算费用应为正数。"""
        result = estimate_session_budget("master")
        assert result["estimated_cost"] > 0

    def test_tokens_per_call_structure(self):
        """单次 token 估算应含三个字段。"""
        result = estimate_session_budget("master")
        per_call = result["estimated_tokens_per_call"]
        assert "prompt_tokens" in per_call
        assert "completion_tokens" in per_call
        assert "total_tokens" in per_call

    def test_total_tokens_structure(self):
        """总 token 估算应含三个字段。"""
        result = estimate_session_budget("master")
        total = result["estimated_total_tokens"]
        assert "prompt_tokens" in total
        assert "completion_tokens" in total
        assert "total_tokens" in total


# ===== 集成测试 =====

class TestEstimatorIntegration:
    """预算估算集成测试。"""

    def test_full_budget_estimation_flow(self):
        """测试完整预算估算流程。"""
        # 1. 获取学位对应模型
        model = get_model_for_degree("master")
        assert len(model) > 0
        # 2. 估算单次费用
        cost = estimate_cost(model, 2000, 1000)
        assert cost > 0
        # 3. 估算会话预算
        budget = estimate_session_budget("master", mode="quick", count=3)
        assert budget["estimated_cost"] > 0
        # 4. 验证总 token = 单次 token * 数量
        per_call = budget["estimated_tokens_per_call"]["total_tokens"]
        total = budget["estimated_total_tokens"]["total_tokens"]
        assert total == per_call * 3

    def test_master_vs_doctor_budget_comparison(self):
        """比较硕士与博士的预算。"""
        master_budget = estimate_session_budget("master", count=3)
        doctor_budget = estimate_session_budget("doctor", count=3)
        # 两者都应有正费用
        assert master_budget["estimated_cost"] > 0
        assert doctor_budget["estimated_cost"] > 0
        # 模型应不同
        assert master_budget["model"] != doctor_budget["model"]
