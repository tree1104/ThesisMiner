"""预算估算模块

根据学位分级路由模型，结合各模型定价估算单次调用与会话级预算。
"""
from backend.config import DEGREE_MODELS

# 各模型每千 token 定价（单位：美元）
MODEL_PRICING = {
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "deepseek-chat": {"input": 0.00014, "output": 0.00028},
    "deepseek-reasoner": {"input": 0.00055, "output": 0.00219},
    "qwen-plus": {"input": 0.0004, "output": 0.0012},
    "qwen-max": {"input": 0.0024, "output": 0.0096},
}

# 默认兜底模型定价
_DEFAULT_PRICING = MODEL_PRICING["gpt-4o-mini"]

# 不同模式下单次调用的 token 估算
_MODE_TOKEN_ESTIMATE = {
    "quick": {"prompt_tokens": 2000, "completion_tokens": 1000},
    "deep": {"prompt_tokens": 5000, "completion_tokens": 3000},
}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """根据模型定价与 token 用量计算费用。

    若模型不在 MODEL_PRICING 中，则使用 gpt-4o-mini 的定价作为默认。

    Args:
        model: 模型名称。
        prompt_tokens: 输入 token 数。
        completion_tokens: 输出 token 数。

    Returns:
        总费用（美元），按每千 token 单价计算。
    """
    pricing = MODEL_PRICING.get(model, _DEFAULT_PRICING)
    # 定价为每千 token，因此除以 1000
    input_cost = (prompt_tokens / 1000) * pricing["input"]
    output_cost = (completion_tokens / 1000) * pricing["output"]
    return round(input_cost + output_cost, 6)


def get_model_for_degree(degree: str) -> str:
    """根据学位选择对应模型。

    master 使用中等成本的 deepseek-chat，doctor 使用高上下文的 qwen-max。

    Args:
        degree: 学位类型（master / doctor）。

    Returns:
        选中的模型名称。
    """
    if degree == "doctor":
        return "qwen-max"
    # master 及其他默认使用 deepseek-chat
    return "deepseek-chat"


def estimate_session_budget(degree: str, mode: str = "quick", count: int = 3) -> dict:
    """估算会话级预算。

    根据 degree 选择模型，根据 mode 估算单次调用的 token 用量，
    再乘以生成数量 count 得到会话总预算。

    Args:
        degree: 学位类型（master / doctor）。
        mode: 生成模式，quick 或 deep。
        count: 论题生成数量。

    Returns:
        预算明细字典，包含学位、模式、数量、模型、单次 token 估算、
        总 token 估算与总费用。
    """
    model = get_model_for_degree(degree)
    # 取该模式下的单次 token 估算，未知模式回退到 quick
    token_estimate = _MODE_TOKEN_ESTIMATE.get(mode, _MODE_TOKEN_ESTIMATE["quick"])
    prompt_per_call = token_estimate["prompt_tokens"]
    completion_per_call = token_estimate["completion_tokens"]

    total_prompt = prompt_per_call * count
    total_completion = completion_per_call * count
    total_cost = estimate_cost(model, total_prompt, total_completion)

    return {
        "degree": degree,
        "mode": mode,
        "count": count,
        "model": model,
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
