"""预算估算模块

根据学位分级路由模型，结合各模型定价估算单次调用与会话级预算。
"""
from backend.config import DEGREE_MODELS

# 各模型定价（单位：元/百万 token）
# 旧表保留作为回退（美元/千 token），新逻辑优先从 models 注册表读取
MODEL_PRICING_LEGACY_USD = {
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "deepseek-chat": {"input": 0.00014, "output": 0.00028},
    "deepseek-reasoner": {"input": 0.00055, "output": 0.00219},
    "qwen-plus": {"input": 0.0004, "output": 0.0012},
    "qwen-max": {"input": 0.0024, "output": 0.0096},
}

# 默认回退定价（元/百万 token）
_DEFAULT_PRICING_CNY = {
    "input_cny_per_million": 1.0,
    "output_cny_per_million": 4.0,
}

# 美元兑人民币汇率（用于 USD 显示折算）
USD_TO_CNY_RATE = 7.2

# 不同模式下单次调用的 token 估算
_MODE_TOKEN_ESTIMATE = {
    "quick": {"prompt_tokens": 2000, "completion_tokens": 1000},
    "deep": {"prompt_tokens": 5000, "completion_tokens": 3000},
}


def estimate_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    currency: str = "CNY",
) -> float:
    """根据模型定价与 token 用量计算费用。

    优先从 models 注册表读取定价（元/百万 token），
    找不到时回退到 MODEL_PRICING_LEGACY_USD（美元/千 token）并折算。

    Args:
        model: 模型名称。
        prompt_tokens: 输入 token 数。
        completion_tokens: 输出 token 数。
        currency: 返回货币单位（CNY 或 USD）。

    Returns:
        总费用，CNY 模式返回元，USD 模式返回美元。
    """
    from backend.config import get_model_config

    # 优先从模型注册表读取
    model_config = get_model_config(model)
    if model_config and model_config.get("pricing"):
        pricing = model_config["pricing"]
        input_cost = (prompt_tokens / 1_000_000) * pricing.get("input_cny_per_million", 0)
        output_cost = (completion_tokens / 1_000_000) * pricing.get("output_cny_per_million", 0)
        total_cny = input_cost + output_cost
    else:
        # 回退到旧定价表（美元/千 token → 元/百万 token）
        legacy = MODEL_PRICING_LEGACY_USD.get(model, {
            "input": _DEFAULT_PRICING_CNY["input_cny_per_million"] / USD_TO_CNY_RATE / 1000,
            "output": _DEFAULT_PRICING_CNY["output_cny_per_million"] / USD_TO_CNY_RATE / 1000,
        })
        # 美元/千 token → 元/百万 token: multiply by 1000 * 7.2
        input_cny_per_million = legacy["input"] * 1000 * USD_TO_CNY_RATE
        output_cny_per_million = legacy["output"] * 1000 * USD_TO_CNY_RATE
        input_cost = (prompt_tokens / 1_000_000) * input_cny_per_million
        output_cost = (completion_tokens / 1_000_000) * output_cny_per_million
        total_cny = input_cost + output_cost

    # 货币转换
    if currency == "USD":
        return round(total_cny / USD_TO_CNY_RATE, 6)
    return round(total_cny, 6)


def get_model_for_degree(degree: str) -> str:
    """根据学位选择对应模型。

    master 使用中等成本的 deepseek-v4，doctor 使用高上下文的 qwen3-max-2026。
    v9.0 更新：使用 2026.06 最新模型批次 ID。

    Args:
        degree: 学位类型（master / doctor）。

    Returns:
        选中的模型名称。
    """
    if degree == "doctor":
        return "qwen3-max-2026"
    # master 及其他默认使用 deepseek-v4
    return "deepseek-v4"


def estimate_session_budget(degree: str, mode: str = "quick", count: int = 3) -> dict:
    """估算会话级预算。

    根据 degree 选择模型，根据 mode 估算单次调用的 token 用量，
    再乘以生成数量 count 得到会话总预算。

    Args:
        degree: 学位类型（master / doctor）。
        mode: 生成模式，quick 或 deep。
        count: 论题生成数量。

    Returns:
        预算明细字典，包含学位、模式、数量、模型、货币、单次 token 估算、
        总 token 估算与总费用。
    """
    from backend.config import get_settings

    settings = get_settings()
    model = get_model_for_degree(degree)
    # 取该模式下的单次 token 估算，未知模式回退到 quick
    token_estimate = _MODE_TOKEN_ESTIMATE.get(mode, _MODE_TOKEN_ESTIMATE["quick"])
    prompt_per_call = token_estimate["prompt_tokens"]
    completion_per_call = token_estimate["completion_tokens"]

    total_prompt = prompt_per_call * count
    total_completion = completion_per_call * count
    total_cost = estimate_cost(model, total_prompt, total_completion, settings.currency)

    return {
        "degree": degree,
        "mode": mode,
        "count": count,
        "model": model,
        "currency": settings.currency,
        "estimated_tokens_per_call": {
            "prompt_tokens": prompt_per_call,
            "completion_tokens": completion_per_call,
            "total_tokens": prompt_per_call + completion_per_call,
        },
        "estimated_total_tokens": {
            "prompt_tokens": total_prompt,
            "completion_tokens": total_completion,
            "total_tokens": total_prompt + total_completion,
        },
        "estimated_cost": total_cost,
    }
