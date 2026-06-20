"""预算与缓存命中率样本数据

提供 budget_ledger 表的样本数据，供集成测试、E2E 测试与压测使用：
- 预算账本条目（含 token 统计与成本）
- 缓存命中率记录（DeepSeek 三段式 Prompt 缓存）
- 多模型成本对比数据
- 会话级预算汇总
- 缓存命中率阈值验证数据

数据覆盖场景：
- 高命中率场景（≥95%，DeepSeek 缓存生效）
- 低命中率场景（首次调用无缓存）
- 混合命中率场景（部分命中部分未命中）
- 多模型成本对比（DeepSeek vs GPT vs Claude）
- 超预算告警场景
"""
from typing import Optional
from datetime import datetime, timedelta


# ===== 预算账本样本 =====
# 每条记录对应一次 LLM 调用，包含 token 统计、成本与缓存命中率
SAMPLE_BUDGET_LEDGER: list[dict] = [
    # DeepSeek 高命中率调用（缓存生效）
    {
        "id": "ledger_001",
        "session_id": "sess_sample_001",
        "model": "deepseek-chat-v3",
        "prompt_tokens": 1500,
        "completion_tokens": 300,
        "total_tokens": 1800,
        "cached_prompt_tokens": 1450,
        "cost": 0.0024,
        "purpose": "info_confirm_search",
        "cache_hit_rate": 0.9667,
        "created_at": "2026-01-15T10:00:00",
    },
    {
        "id": "ledger_002",
        "session_id": "sess_sample_001",
        "model": "deepseek-chat-v3",
        "prompt_tokens": 2000,
        "completion_tokens": 500,
        "total_tokens": 2500,
        "cached_prompt_tokens": 1950,
        "cost": 0.0033,
        "purpose": "creativity_generate",
        "cache_hit_rate": 0.9750,
        "created_at": "2026-01-15T10:01:00",
    },
    {
        "id": "ledger_003",
        "session_id": "sess_sample_001",
        "model": "deepseek-reasoner",
        "prompt_tokens": 3000,
        "completion_tokens": 800,
        "total_tokens": 3800,
        "cached_prompt_tokens": 2900,
        "cost": 0.0152,
        "purpose": "validation_critic",
        "cache_hit_rate": 0.9667,
        "created_at": "2026-01-15T10:02:00",
    },
    {
        "id": "ledger_004",
        "session_id": "sess_sample_001",
        "model": "deepseek-chat-v3",
        "prompt_tokens": 2500,
        "completion_tokens": 600,
        "total_tokens": 3100,
        "cached_prompt_tokens": 2400,
        "cost": 0.0041,
        "purpose": "generation_report",
        "cache_hit_rate": 0.9600,
        "created_at": "2026-01-15T10:03:00",
    },
    {
        "id": "ledger_005",
        "session_id": "sess_sample_001",
        "model": "deepseek-chat-v3",
        "prompt_tokens": 1800,
        "completion_tokens": 400,
        "total_tokens": 2200,
        "cached_prompt_tokens": 1750,
        "cost": 0.0029,
        "purpose": "deep_assist_literature",
        "cache_hit_rate": 0.9722,
        "created_at": "2026-01-15T10:04:00",
    },

    # DeepSeek 首次调用（无缓存）
    {
        "id": "ledger_006",
        "session_id": "sess_sample_002",
        "model": "deepseek-chat-v3",
        "prompt_tokens": 1200,
        "completion_tokens": 200,
        "total_tokens": 1400,
        "cached_prompt_tokens": 0,
        "cost": 0.0019,
        "purpose": "info_confirm_search",
        "cache_hit_rate": 0.0,
        "created_at": "2026-01-15T11:00:00",
    },
    {
        "id": "ledger_007",
        "session_id": "sess_sample_002",
        "model": "deepseek-chat-v3",
        "prompt_tokens": 1500,
        "completion_tokens": 300,
        "total_tokens": 1800,
        "cached_prompt_tokens": 1200,
        "cost": 0.0024,
        "purpose": "creativity_generate",
        "cache_hit_rate": 0.8000,
        "created_at": "2026-01-15T11:01:00",
    },

    # GPT-4.1 调用（无 DeepSeek 缓存）
    {
        "id": "ledger_008",
        "session_id": "sess_sample_003",
        "model": "gpt-4.1",
        "prompt_tokens": 2000,
        "completion_tokens": 500,
        "total_tokens": 2500,
        "cached_prompt_tokens": 0,
        "cost": 0.0500,
        "purpose": "mentor_advice",
        "cache_hit_rate": 0.0,
        "created_at": "2026-01-15T12:00:00",
    },
    {
        "id": "ledger_009",
        "session_id": "sess_sample_003",
        "model": "gpt-4.1-mini",
        "prompt_tokens": 1000,
        "completion_tokens": 200,
        "total_tokens": 1200,
        "cached_prompt_tokens": 0,
        "cost": 0.0018,
        "purpose": "quick_qa",
        "cache_hit_rate": 0.0,
        "created_at": "2026-01-15T12:01:00",
    },

    # Claude 调用
    {
        "id": "ledger_010",
        "session_id": "sess_sample_004",
        "model": "claude-sonnet-4.5",
        "prompt_tokens": 2500,
        "completion_tokens": 600,
        "total_tokens": 3100,
        "cached_prompt_tokens": 0,
        "cost": 0.0465,
        "purpose": "orchestrator_decision",
        "cache_hit_rate": 0.0,
        "created_at": "2026-01-15T13:00:00",
    },
    {
        "id": "ledger_011",
        "session_id": "sess_sample_004",
        "model": "claude-opus-4.5",
        "prompt_tokens": 3000,
        "completion_tokens": 1000,
        "total_tokens": 4000,
        "cached_prompt_tokens": 0,
        "cost": 0.1200,
        "purpose": "generation_full_report",
        "cache_hit_rate": 0.0,
        "created_at": "2026-01-15T13:01:00",
    },

    # Qwen 调用
    {
        "id": "ledger_012",
        "session_id": "sess_sample_005",
        "model": "qwen3-max",
        "prompt_tokens": 1800,
        "completion_tokens": 400,
        "total_tokens": 2200,
        "cached_prompt_tokens": 0,
        "cost": 0.0088,
        "purpose": "creativity_inspire",
        "cache_hit_rate": 0.0,
        "created_at": "2026-01-15T14:00:00",
    },

    # DeepSeek 高命中率批量调用（压测场景）
    {
        "id": "ledger_013",
        "session_id": "sess_sample_006",
        "model": "deepseek-chat-v3",
        "prompt_tokens": 2000,
        "completion_tokens": 400,
        "total_tokens": 2400,
        "cached_prompt_tokens": 1950,
        "cost": 0.0032,
        "purpose": "batch_call_01",
        "cache_hit_rate": 0.9750,
        "created_at": "2026-01-15T15:00:00",
    },
    {
        "id": "ledger_014",
        "session_id": "sess_sample_006",
        "model": "deepseek-chat-v3",
        "prompt_tokens": 2000,
        "completion_tokens": 400,
        "total_tokens": 2400,
        "cached_prompt_tokens": 1950,
        "cost": 0.0032,
        "purpose": "batch_call_02",
        "cache_hit_rate": 0.9750,
        "created_at": "2026-01-15T15:00:01",
    },
    {
        "id": "ledger_015",
        "session_id": "sess_sample_006",
        "model": "deepseek-chat-v3",
        "prompt_tokens": 2000,
        "completion_tokens": 400,
        "total_tokens": 2400,
        "cached_prompt_tokens": 1950,
        "cost": 0.0032,
        "purpose": "batch_call_03",
        "cache_hit_rate": 0.9750,
        "created_at": "2026-01-15T15:00:02",
    },
    {
        "id": "ledger_016",
        "session_id": "sess_sample_006",
        "model": "deepseek-chat-v3",
        "prompt_tokens": 2000,
        "completion_tokens": 400,
        "total_tokens": 2400,
        "cached_prompt_tokens": 1950,
        "cost": 0.0032,
        "purpose": "batch_call_04",
        "cache_hit_rate": 0.9750,
        "created_at": "2026-01-15T15:00:03",
    },
    {
        "id": "ledger_017",
        "session_id": "sess_sample_006",
        "model": "deepseek-chat-v3",
        "prompt_tokens": 2000,
        "completion_tokens": 400,
        "total_tokens": 2400,
        "cached_prompt_tokens": 1950,
        "cost": 0.0032,
        "purpose": "batch_call_05",
        "cache_hit_rate": 0.9750,
        "created_at": "2026-01-15T15:00:04",
    },

    # 低命中率场景（前缀变化导致缓存失效）
    {
        "id": "ledger_018",
        "session_id": "sess_sample_007",
        "model": "deepseek-chat-v3",
        "prompt_tokens": 1500,
        "completion_tokens": 300,
        "total_tokens": 1800,
        "cached_prompt_tokens": 200,
        "cost": 0.0024,
        "purpose": "prefix_changed_01",
        "cache_hit_rate": 0.1333,
        "created_at": "2026-01-15T16:00:00",
    },
    {
        "id": "ledger_019",
        "session_id": "sess_sample_007",
        "model": "deepseek-chat-v3",
        "prompt_tokens": 1500,
        "completion_tokens": 300,
        "total_tokens": 1800,
        "cached_prompt_tokens": 100,
        "cost": 0.0024,
        "purpose": "prefix_changed_02",
        "cache_hit_rate": 0.0667,
        "created_at": "2026-01-15T16:01:00",
    },

    # 超预算场景
    {
        "id": "ledger_020",
        "session_id": "sess_sample_008",
        "model": "claude-opus-4.5",
        "prompt_tokens": 5000,
        "completion_tokens": 2000,
        "total_tokens": 7000,
        "cached_prompt_tokens": 0,
        "cost": 0.2100,
        "purpose": "expensive_call_01",
        "cache_hit_rate": 0.0,
        "created_at": "2026-01-15T17:00:00",
    },
    {
        "id": "ledger_021",
        "session_id": "sess_sample_008",
        "model": "claude-opus-4.5",
        "prompt_tokens": 4000,
        "completion_tokens": 1500,
        "total_tokens": 5500,
        "cached_prompt_tokens": 0,
        "cost": 0.1650,
        "purpose": "expensive_call_02",
        "cache_hit_rate": 0.0,
        "created_at": "2026-01-15T17:01:00",
    },
]


# ===== 按模型分组的预算数据 =====
BUDGET_BY_MODEL: dict[str, dict] = {
    "deepseek-chat-v3": {
        "total_calls": 12,
        "total_prompt_tokens": 22000,
        "total_completion_tokens": 3900,
        "total_tokens": 25900,
        "total_cached_tokens": 16700,
        "total_cost": 0.0347,
        "avg_cache_hit_rate": 0.7591,
        "cost_per_1k_tokens": 0.00134,
    },
    "deepseek-reasoner": {
        "total_calls": 1,
        "total_prompt_tokens": 3000,
        "total_completion_tokens": 800,
        "total_tokens": 3800,
        "total_cached_tokens": 2900,
        "total_cost": 0.0152,
        "avg_cache_hit_rate": 0.9667,
        "cost_per_1k_tokens": 0.00400,
    },
    "gpt-4.1": {
        "total_calls": 1,
        "total_prompt_tokens": 2000,
        "total_completion_tokens": 500,
        "total_tokens": 2500,
        "total_cached_tokens": 0,
        "total_cost": 0.0500,
        "avg_cache_hit_rate": 0.0,
        "cost_per_1k_tokens": 0.02000,
    },
    "gpt-4.1-mini": {
        "total_calls": 1,
        "total_prompt_tokens": 1000,
        "total_completion_tokens": 200,
        "total_tokens": 1200,
        "total_cached_tokens": 0,
        "total_cost": 0.0018,
        "avg_cache_hit_rate": 0.0,
        "cost_per_1k_tokens": 0.00150,
    },
    "claude-sonnet-4.5": {
        "total_calls": 1,
        "total_prompt_tokens": 2500,
        "total_completion_tokens": 600,
        "total_tokens": 3100,
        "total_cached_tokens": 0,
        "total_cost": 0.0465,
        "avg_cache_hit_rate": 0.0,
        "cost_per_1k_tokens": 0.01500,
    },
    "claude-opus-4.5": {
        "total_calls": 2,
        "total_prompt_tokens": 8000,
        "total_completion_tokens": 3000,
        "total_tokens": 11000,
        "total_cached_tokens": 0,
        "total_cost": 0.3300,
        "avg_cache_hit_rate": 0.0,
        "cost_per_1k_tokens": 0.03000,
    },
    "qwen3-max": {
        "total_calls": 1,
        "total_prompt_tokens": 1800,
        "total_completion_tokens": 400,
        "total_tokens": 2200,
        "total_cached_tokens": 0,
        "total_cost": 0.0088,
        "avg_cache_hit_rate": 0.0,
        "cost_per_1k_tokens": 0.00400,
    },
}


# ===== 按会话分组的预算汇总 =====
BUDGET_BY_SESSION: dict[str, dict] = {
    "sess_sample_001": {
        "total_calls": 5,
        "total_cost": 0.0279,
        "total_tokens": 13400,
        "models_used": ["deepseek-chat-v3", "deepseek-reasoner"],
        "avg_cache_hit_rate": 0.9677,
        "stages": ["info_confirm", "creativity", "validation", "generation", "deep_assist"],
    },
    "sess_sample_002": {
        "total_calls": 2,
        "total_cost": 0.0043,
        "total_tokens": 3200,
        "models_used": ["deepseek-chat-v3"],
        "avg_cache_hit_rate": 0.4000,
        "stages": ["info_confirm", "creativity"],
    },
    "sess_sample_003": {
        "total_calls": 2,
        "total_cost": 0.0518,
        "total_tokens": 3700,
        "models_used": ["gpt-4.1", "gpt-4.1-mini"],
        "avg_cache_hit_rate": 0.0,
        "stages": ["mentor_advice", "quick_qa"],
    },
    "sess_sample_004": {
        "total_calls": 2,
        "total_cost": 0.1665,
        "total_tokens": 7100,
        "models_used": ["claude-sonnet-4.5", "claude-opus-4.5"],
        "avg_cache_hit_rate": 0.0,
        "stages": ["orchestrator", "generation"],
    },
    "sess_sample_005": {
        "total_calls": 1,
        "total_cost": 0.0088,
        "total_tokens": 2200,
        "models_used": ["qwen3-max"],
        "avg_cache_hit_rate": 0.0,
        "stages": ["creativity"],
    },
    "sess_sample_006": {
        "total_calls": 5,
        "total_cost": 0.0160,
        "total_tokens": 12000,
        "models_used": ["deepseek-chat-v3"],
        "avg_cache_hit_rate": 0.9750,
        "stages": ["batch_test"],
    },
    "sess_sample_007": {
        "total_calls": 2,
        "total_cost": 0.0048,
        "total_tokens": 3600,
        "models_used": ["deepseek-chat-v3"],
        "avg_cache_hit_rate": 0.1000,
        "stages": ["prefix_changed_test"],
    },
    "sess_sample_008": {
        "total_calls": 2,
        "total_cost": 0.3750,
        "total_tokens": 12500,
        "models_used": ["claude-opus-4.5"],
        "avg_cache_hit_rate": 0.0,
        "stages": ["expensive_calls"],
    },
}


# ===== 缓存命中率场景数据 =====
# 用于验证不同缓存命中率场景的统计计算
CACHE_HIT_RATE_SCENARIOS: list[dict] = [
    {
        "name": "全高命中率场景",
        "description": "所有调用均命中缓存，命中率≥95%",
        "records": [
            {"prompt_tokens": 1000, "cached_tokens": 980, "expected_rate": 0.98},
            {"prompt_tokens": 1500, "cached_tokens": 1450, "expected_rate": 0.9667},
            {"prompt_tokens": 2000, "cached_tokens": 1950, "expected_rate": 0.975},
            {"prompt_tokens": 1800, "cached_tokens": 1750, "expected_rate": 0.9722},
            {"prompt_tokens": 1200, "cached_tokens": 1180, "expected_rate": 0.9833},
        ],
        "expected_avg_rate": 0.9754,
        "expected_overall_rate": 0.9744,
    },
    {
        "name": "全低命中率场景",
        "description": "所有调用均未命中缓存（首次调用）",
        "records": [
            {"prompt_tokens": 1000, "cached_tokens": 0, "expected_rate": 0.0},
            {"prompt_tokens": 1500, "cached_tokens": 0, "expected_rate": 0.0},
            {"prompt_tokens": 2000, "cached_tokens": 0, "expected_rate": 0.0},
        ],
        "expected_avg_rate": 0.0,
        "expected_overall_rate": 0.0,
    },
    {
        "name": "混合命中率场景",
        "description": "80% 高命中率 + 20% 低命中率",
        "records": [
            {"prompt_tokens": 1000, "cached_tokens": 980, "expected_rate": 0.98},
            {"prompt_tokens": 1000, "cached_tokens": 970, "expected_rate": 0.97},
            {"prompt_tokens": 1000, "cached_tokens": 960, "expected_rate": 0.96},
            {"prompt_tokens": 1000, "cached_tokens": 950, "expected_rate": 0.95},
            {"prompt_tokens": 1000, "cached_tokens": 0, "expected_rate": 0.0},
        ],
        "expected_avg_rate": 0.772,
        "expected_overall_rate": 0.772,
    },
    {
        "name": "渐进命中率场景",
        "description": "命中率随调用次数递增（缓存预热）",
        "records": [
            {"prompt_tokens": 1000, "cached_tokens": 0, "expected_rate": 0.0},
            {"prompt_tokens": 1000, "cached_tokens": 500, "expected_rate": 0.5},
            {"prompt_tokens": 1000, "cached_tokens": 800, "expected_rate": 0.8},
            {"prompt_tokens": 1000, "cached_tokens": 950, "expected_rate": 0.95},
            {"prompt_tokens": 1000, "cached_tokens": 980, "expected_rate": 0.98},
        ],
        "expected_avg_rate": 0.646,
        "expected_overall_rate": 0.646,
    },
]


# ===== 模型定价表 =====
MODEL_PRICING: dict[str, dict] = {
    "deepseek-chat-v3": {
        "input_per_1k": 0.001,
        "cached_input_per_1k": 0.0001,
        "output_per_1k": 0.002,
        "currency": "CNY",
        "release_year": 2025,
    },
    "deepseek-reasoner": {
        "input_per_1k": 0.004,
        "cached_input_per_1k": 0.0004,
        "output_per_1k": 0.016,
        "currency": "CNY",
        "release_year": 2025,
    },
    "gpt-4.1": {
        "input_per_1k": 0.01,
        "cached_input_per_1k": 0.005,
        "output_per_1k": 0.03,
        "currency": "USD",
        "release_year": 2025,
    },
    "gpt-4.1-mini": {
        "input_per_1k": 0.0005,
        "cached_input_per_1k": 0.00025,
        "output_per_1k": 0.0015,
        "currency": "USD",
        "release_year": 2025,
    },
    "claude-sonnet-4.5": {
        "input_per_1k": 0.003,
        "cached_input_per_1k": 0.003,
        "output_per_1k": 0.015,
        "currency": "USD",
        "release_year": 2025,
    },
    "claude-opus-4.5": {
        "input_per_1k": 0.015,
        "cached_input_per_1k": 0.015,
        "output_per_1k": 0.075,
        "currency": "USD",
        "release_year": 2025,
    },
    "qwen3-max": {
        "input_per_1k": 0.002,
        "cached_input_per_1k": 0.001,
        "output_per_1k": 0.006,
        "currency": "CNY",
        "release_year": 2025,
    },
    "gemini-2.5-pro": {
        "input_per_1k": 0.003,
        "cached_input_per_1k": 0.0015,
        "output_per_1k": 0.012,
        "currency": "USD",
        "release_year": 2025,
    },
    "glm-4.6": {
        "input_per_1k": 0.002,
        "cached_input_per_1k": 0.001,
        "output_per_1k": 0.006,
        "currency": "CNY",
        "release_year": 2025,
    },
    "doubao-1.5-pro": {
        "input_per_1k": 0.0008,
        "cached_input_per_1k": 0.0004,
        "output_per_1k": 0.002,
        "currency": "CNY",
        "release_year": 2025,
    },
}


# ===== 预算阈值配置 =====
BUDGET_THRESHOLDS: dict = {
    "warning_threshold": 0.8,
    "critical_threshold": 0.95,
    "default_session_budget_cny": 10.0,
    "default_session_budget_usd": 2.0,
    "cache_hit_rate_target": 0.95,
    "cache_hit_rate_warning": 0.80,
    "cache_hit_rate_critical": 0.50,
}


# ===== 超预算告警样本 =====
BUDGET_ALERTS: list[dict] = [
    {
        "session_id": "sess_sample_008",
        "alert_type": "critical",
        "message": "会话预算已使用 187.5%，超出预算上限",
        "current_spend": 0.3750,
        "budget_limit": 0.2000,
        "usage_percentage": 187.5,
        "triggered_at": "2026-01-15T17:01:01",
    },
    {
        "session_id": "sess_sample_004",
        "alert_type": "warning",
        "message": "会话预算已使用 83.3%，接近预算上限",
        "current_spend": 0.1665,
        "budget_limit": 0.2000,
        "usage_percentage": 83.3,
        "triggered_at": "2026-01-15T13:01:01",
    },
    {
        "session_id": "sess_sample_001",
        "alert_type": "info",
        "message": "缓存命中率 96.77%，达到目标值 95%",
        "current_spend": 0.0279,
        "budget_limit": 10.0,
        "usage_percentage": 0.279,
        "cache_hit_rate": 0.9677,
        "triggered_at": "2026-01-15T10:04:01",
    },
]


# ===== 辅助函数 =====

def get_ledger_by_session(session_id: str) -> list[dict]:
    """按会话 ID 获取预算账本记录

    Args:
        session_id: 会话 ID。

    Returns:
        匹配会话的账本记录列表。
    """
    return [r for r in SAMPLE_BUDGET_LEDGER if r["session_id"] == session_id]


def get_ledger_by_model(model: str) -> list[dict]:
    """按模型获取预算账本记录

    Args:
        model: 模型 ID。

    Returns:
        匹配模型的账本记录列表。
    """
    return [r for r in SAMPLE_BUDGET_LEDGER if r["model"] == model]


def get_deepseek_records() -> list[dict]:
    """获取所有 DeepSeek 模型的调用记录

    Returns:
        DeepSeek 模型的账本记录列表。
    """
    return [r for r in SAMPLE_BUDGET_LEDGER if "deepseek" in r["model"].lower()]


def get_high_cache_hit_records(threshold: float = 0.95) -> list[dict]:
    """获取高缓存命中率的记录

    Args:
        threshold: 命中率阈值，默认 0.95。

    Returns:
        命中率≥阈值的记录列表。
    """
    return [r for r in SAMPLE_BUDGET_LEDGER if r["cache_hit_rate"] >= threshold]


def calculate_session_cost(session_id: str) -> float:
    """计算指定会话的总成本

    Args:
        session_id: 会话 ID。

    Returns:
        会话总成本。
    """
    records = get_ledger_by_session(session_id)
    return sum(r["cost"] for r in records)


def calculate_avg_cache_hit_rate(session_id: str) -> float:
    """计算指定会话的平均缓存命中率

    Args:
        session_id: 会话 ID。

    Returns:
        平均缓存命中率，无记录时返回 0.0。
    """
    records = get_ledger_by_session(session_id)
    if not records:
        return 0.0
    rates = [r["cache_hit_rate"] for r in records]
    return sum(rates) / len(rates)


def calculate_overall_cache_hit_rate(session_id: str) -> float:
    """计算指定会话的总体缓存命中率（加权平均）

    Args:
        session_id: 会话 ID。

    Returns:
        总体缓存命中率 = sum(cached_tokens) / sum(prompt_tokens)。
    """
    records = get_ledger_by_session(session_id)
    total_prompt = sum(r["prompt_tokens"] for r in records)
    total_cached = sum(r["cached_prompt_tokens"] for r in records)
    return total_cached / total_prompt if total_prompt > 0 else 0.0


def get_budget_summary() -> dict:
    """获取全局预算汇总

    Returns:
        包含总调用数、总成本、总 token 数、平均命中率的汇总字典。
    """
    records = SAMPLE_BUDGET_LEDGER
    total_calls = len(records)
    total_cost = sum(r["cost"] for r in records)
    total_prompt = sum(r["prompt_tokens"] for r in records)
    total_completion = sum(r["completion_tokens"] for r in records)
    total_cached = sum(r["cached_prompt_tokens"] for r in records)
    deepseek_records = get_deepseek_records()
    deepseek_rates = [r["cache_hit_rate"] for r in deepseek_records]

    return {
        "total_calls": total_calls,
        "total_cost": total_cost,
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_completion,
        "total_tokens": total_prompt + total_completion,
        "total_cached_tokens": total_cached,
        "avg_cache_hit_rate": sum(deepseek_rates) / len(deepseek_rates) if deepseek_rates else 0.0,
        "overall_cache_hit_rate": total_cached / total_prompt if total_prompt > 0 else 0.0,
        "models_used": list(set(r["model"] for r in records)),
        "sessions_count": len(set(r["session_id"] for r in records)),
    }


def get_cost_comparison() -> dict:
    """获取各模型成本对比

    Returns:
        按模型分组的成本统计字典。
    """
    return BUDGET_BY_MODEL


def check_budget_alert(session_id: str, budget_limit: float) -> Optional[dict]:
    """检查会话是否超预算

    Args:
        session_id: 会话 ID。
        budget_limit: 预算上限。

    Returns:
        超预算时返回告警字典，否则返回 None。
    """
    current_spend = calculate_session_cost(session_id)
    usage_pct = (current_spend / budget_limit * 100) if budget_limit > 0 else 0

    if usage_pct >= BUDGET_THRESHOLDS["critical_threshold"] * 100:
        alert_type = "critical"
        message = f"会话预算已使用 {usage_pct:.1f}%，超出预算上限"
    elif usage_pct >= BUDGET_THRESHOLDS["warning_threshold"] * 100:
        alert_type = "warning"
        message = f"会话预算已使用 {usage_pct:.1f}%，接近预算上限"
    else:
        return None

    return {
        "session_id": session_id,
        "alert_type": alert_type,
        "message": message,
        "current_spend": current_spend,
        "budget_limit": budget_limit,
        "usage_percentage": usage_pct,
    }


def build_ledger_entry(
    session_id: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int = 0,
    purpose: str = "test",
) -> dict:
    """构建单条预算账本记录

    Args:
        session_id: 会话 ID。
        model: 模型 ID。
        prompt_tokens: 输入 token 数。
        completion_tokens: 输出 token 数。
        cached_tokens: 缓存命中的 token 数。
        purpose: 调用用途。

    Returns:
        预算账本记录字典。
    """
    hit_rate = cached_tokens / prompt_tokens if prompt_tokens > 0 else 0.0
    pricing = MODEL_PRICING.get(model, {})
    input_cost = (prompt_tokens - cached_tokens) / 1000 * pricing.get("input_per_1k", 0.001)
    cached_cost = cached_tokens / 1000 * pricing.get("cached_input_per_1k", 0.0001)
    output_cost = completion_tokens / 1000 * pricing.get("output_per_1k", 0.002)
    total_cost = input_cost + cached_cost + output_cost

    return {
        "id": f"ledger_generated_{session_id}_{prompt_tokens}_{completion_tokens}",
        "session_id": session_id,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "cached_prompt_tokens": cached_tokens,
        "cost": round(total_cost, 4),
        "purpose": purpose,
        "cache_hit_rate": round(hit_rate, 4),
        "created_at": datetime.now().isoformat(),
    }


def generate_batch_ledger_entries(
    session_id: str,
    model: str,
    count: int,
    prompt_tokens: int = 2000,
    completion_tokens: int = 400,
    cached_tokens: int = 1950,
) -> list[dict]:
    """批量生成预算账本记录

    Args:
        session_id: 会话 ID。
        model: 模型 ID。
        count: 生成数量。
        prompt_tokens: 每条记录的输入 token 数。
        completion_tokens: 每条记录的输出 token 数。
        cached_tokens: 每条记录的缓存命中 token 数。

    Returns:
        预算账本记录列表。
    """
    entries = []
    base_time = datetime.now()
    for i in range(count):
        entry = build_ledger_entry(
            session_id=session_id,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_tokens=cached_tokens,
            purpose=f"batch_call_{i:04d}",
        )
        entry["id"] = f"ledger_batch_{session_id}_{i:04d}"
        entry["created_at"] = (base_time + timedelta(seconds=i)).isoformat()
        entries.append(entry)
    return entries


# 模块导入时断言样本数量满足要求
assert len(SAMPLE_BUDGET_LEDGER) >= 20, f"预算账本样本不足20条，当前 {len(SAMPLE_BUDGET_LEDGER)}"
assert len(BUDGET_BY_MODEL) >= 7, f"模型预算统计不足7个，当前 {len(BUDGET_BY_MODEL)}"
assert len(CACHE_HIT_RATE_SCENARIOS) >= 4, f"缓存命中率场景不足4个，当前 {len(CACHE_HIT_RATE_SCENARIOS)}"
assert len(MODEL_PRICING) >= 8, f"模型定价不足8个，当前 {len(MODEL_PRICING)}"
assert len(BUDGET_ALERTS) >= 3, f"预算告警样本不足3个，当前 {len(BUDGET_ALERTS)}"
