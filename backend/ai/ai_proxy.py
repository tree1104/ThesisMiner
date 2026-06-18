"""统一 AI 调用代理模块

封装 OpenAI 客户端的创建、配置检查、同步调用、JSON 解析与流式调用，
并在每次调用后通过透明账本记录 token 用量与费用。
"""
import json
import re
from typing import Iterator

import openai

from backend.config import get_settings
from backend.budgets.estimator import estimate_cost
from backend.budgets.transparent_ledger import record_usage


def get_client() -> openai.OpenAI:
    """创建并返回 OpenAI 客户端实例。

    从全局 settings 读取 api_key 与 base_url。

    Returns:
        配置好的 openai.OpenAI 客户端。
    """
    settings = get_settings()
    return openai.OpenAI(
        api_key=settings.ai_api_key,
        base_url=settings.ai_base_url,
    )


def check_api_configured() -> bool:
    """检查 AI API Key 是否已配置（非空）。

    Returns:
        已配置返回 True，否则返回 False。
    """
    settings = get_settings()
    return bool(settings.ai_api_key)


def call_llm(
    system_prompt: str,
    user_prompt: str,
    model: str = None,
    temperature: float = 0.7,
    session_id: str = None,
    purpose: str = "unknown",
) -> dict:
    """同步调用大语言模型并记录用量。

    Args:
        system_prompt: 系统提示词。
        user_prompt: 用户提示词。
        model: 模型名称，为 None 时使用 settings 中的默认模型。
        temperature: 采样温度，默认 0.7。
        session_id: 关联的会话 ID，用于账本记录。
        purpose: 调用用途，用于账本记录。

    Returns:
        调用结果字典，包含 content、model、prompt_tokens、
        completion_tokens、total_tokens、cost。

    Raises:
        ValueError: 当 AI API Key 未配置时抛出。
    """
    if not check_api_configured():
        raise ValueError("AI API Key 未配置，请在设置页配置")

    settings = get_settings()
    used_model = model if model else settings.ai_model
    client = get_client()

    response = client.chat.completions.create(
        model=used_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
    )

    # 提取 token 用量
    usage = response.usage
    prompt_tokens = usage.prompt_tokens if usage else 0
    completion_tokens = usage.completion_tokens if usage else 0
    total_tokens = usage.total_tokens if usage else (prompt_tokens + completion_tokens)

    content = response.choices[0].message.content if response.choices else ""
    cost = estimate_cost(used_model, prompt_tokens, completion_tokens)

    # 记录到透明账本
    record_usage(
        session_id=session_id,
        model=used_model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        purpose=purpose,
    )

    return {
        "content": content,
        "model": used_model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cost": cost,
    }


def call_llm_json(
    system_prompt: str,
    user_prompt: str,
    model: str = None,
    temperature: float = 0.7,
    session_id: str = None,
    purpose: str = "unknown",
) -> dict:
    """调用大语言模型并解析响应为 JSON。

    先调用 call_llm，再尝试将响应文本解析为 JSON；
    若直接解析失败，则尝试从文本中提取 JSON 代码块或对象片段。

    Args:
        system_prompt: 系统提示词。
        user_prompt: 用户提示词。
        model: 模型名称，为 None 时使用默认模型。
        temperature: 采样温度，默认 0.7。
        session_id: 关联的会话 ID。
        purpose: 调用用途。

    Returns:
        解析后的 JSON 字典。

    Raises:
        ValueError: 当 AI API Key 未配置时抛出。
        json.JSONDecodeError: 当响应无法解析为 JSON 时抛出。
    """
    result = call_llm(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
        temperature=temperature,
        session_id=session_id,
        purpose=purpose,
    )

    content = result["content"]
    parsed = _parse_json(content)
    result["content"] = parsed
    return result


def call_llm_stream(
    system_prompt: str,
    user_prompt: str,
    model: str = None,
    temperature: float = 0.7,
) -> Iterator[str]:
    """流式调用大语言模型，逐块返回文本。

    Args:
        system_prompt: 系统提示词。
        user_prompt: 用户提示词。
        model: 模型名称，为 None 时使用默认模型。
        temperature: 采样温度，默认 0.7。

    Yields:
        每个增量文本块。

    Raises:
        ValueError: 当 AI API Key 未配置时抛出。
    """
    if not check_api_configured():
        raise ValueError("AI API Key 未配置，请在设置页配置")

    settings = get_settings()
    used_model = model if model else settings.ai_model
    client = get_client()

    stream = client.chat.completions.create(
        model=used_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        stream=True,
    )

    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield delta.content


def _parse_json(text: str) -> dict:
    """从文本中解析 JSON，支持代码块包裹与裸 JSON 两种情况。

    Args:
        text: 待解析的文本。

    Returns:
        解析后的字典。

    Raises:
        json.JSONDecodeError: 当无法解析为 JSON 时抛出。
    """
    # 先尝试直接解析
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    # 尝试提取 ```json ... ``` 代码块
    code_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if code_block_match:
        return json.loads(code_block_match.group(1))

    # 尝试提取首个 JSON 对象片段
    object_match = re.search(r"\{.*\}", text, re.DOTALL)
    if object_match:
        return json.loads(object_match.group(0))

    # 全部失败，抛出原始异常
    raise json.JSONDecodeError("无法从响应中解析 JSON", text, 0)
