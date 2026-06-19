"""统一 AI 调用代理模块

封装 OpenAI 客户端的创建、配置检查、异步调用、JSON 解析与流式调用，
并在每次调用后通过透明账本记录 token 用量与费用。
"""
import re
from typing import AsyncIterator, Optional

import json5
import openai

from backend.config import get_settings
from backend.budgets.estimator import estimate_cost
from backend.budgets.transparent_ledger import record_usage
from backend.ai.prompts import (
    build_dynamic_tail,
    compute_prefix_hash,
)

# 模块级客户端缓存，避免每次调用都创建新客户端
_client: Optional[openai.AsyncOpenAI] = None


def get_client() -> openai.AsyncOpenAI:
    """创建并返回 OpenAI 异步客户端实例（带模块级缓存）。

    从全局 settings 读取 api_key 与 base_url。
    首次调用时创建客户端并缓存，后续调用直接复用。

    Returns:
        配置好的 openai.AsyncOpenAI 客户端。
    """
    global _client
    if _client is None:
        settings = get_settings()
        _client = openai.AsyncOpenAI(
            api_key=settings.ai_api_key,
            base_url=settings.ai_base_url,
        )
    return _client


def check_api_configured() -> bool:
    """检查 AI API Key 是否已配置（非空）。

    Returns:
        已配置返回 True，否则返回 False。
    """
    settings = get_settings()
    return bool(settings.ai_api_key)


async def call_llm(
    system_prompt: str,
    user_prompt: str,
    model: str = None,
    temperature: float = 0.7,
    session_id: str = None,
    purpose: str = "unknown",
    response_format: dict = None,
    prefix_hash: str = None,
) -> dict:
    """异步调用大语言模型并记录用量。

    Args:
        system_prompt: 系统提示词。
        user_prompt: 用户提示词。
        model: 模型名称，为 None 时使用 settings 中的默认模型。
        temperature: 采样温度，默认 0.7。
        session_id: 关联的会话 ID，用于账本记录。
        purpose: 调用用途，用于账本记录。
        response_format: 可选的响应格式约束，如 {"type": "json_object"}，
            仅在模型支持时生效，用于 JSON 模式重试。
        prefix_hash: 可选的缓存前缀哈希。提供时会在系统消息上注入
            cache_control 提示（Anthropic 风格，OpenAI 会忽略但无害），
            并附加一条带 prefix_hash 注释的系统消息便于调试。

    Returns:
        调用结果字典，包含 content、model、prompt_tokens、
        completion_tokens、total_tokens、cost，以及当 prefix_hash
        非空时附带 prefix_hash 与 cache_hit 字段。

    Raises:
        ValueError: 当 AI API Key 未配置时抛出。
    """
    if not check_api_configured():
        raise ValueError("AI API Key 未配置，请在设置页配置")

    settings = get_settings()
    used_model = model if model else settings.ai_model
    client = get_client()

    # 构建消息列表，系统提示在前，用户提示在后
    messages = [
        {"role": "system", "content": system_prompt},
    ]
    # 注入缓存控制提示（仅当提供 prefix_hash 时）
    if prefix_hash:
        # Anthropic 风格的 cache_control 提示（OpenAI 会忽略但无害）
        messages[0]["cache_control"] = {"type": "ephemeral"}
        # 附加 prefix_hash 注释的系统消息，便于调试与缓存追踪
        messages.append(
            {"role": "system", "content": f"[cache_prefix_id:{prefix_hash}]"}
        )
    messages.append({"role": "user", "content": user_prompt})

    # 构建请求参数，仅在指定 response_format 时附加（需模型支持）
    kwargs = {
        "model": used_model,
        "messages": messages,
        "temperature": temperature,
    }
    if response_format is not None:
        kwargs["response_format"] = response_format

    # 异步调用大模型
    response = await client.chat.completions.create(**kwargs)

    # 提取 token 用量
    usage = response.usage
    prompt_tokens = usage.prompt_tokens if usage else 0
    completion_tokens = usage.completion_tokens if usage else 0
    total_tokens = usage.total_tokens if usage else (prompt_tokens + completion_tokens)

    content = response.choices[0].message.content if response.choices else ""
    cost = estimate_cost(used_model, prompt_tokens, completion_tokens)

    # 记录到透明账本（record_usage 为同步函数，直接调用即可）
    record_usage(
        session_id=session_id,
        model=used_model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        purpose=purpose,
    )

    result = {
        "content": content,
        "model": used_model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cost": cost,
    }
    # 当注入了缓存前缀时，附带缓存追踪信息
    if prefix_hash:
        result["prefix_hash"] = prefix_hash
        # OpenAI 暂不返回缓存命中详情，默认标记为 False；
        # 后续可结合 response 中的 cached_tokens 字段细化
        result["cache_hit"] = False
    return result


async def call_llm_three_segment(
    base: str,
    profile: str,
    query: str,
    dst_state: dict = None,
    model: str = None,
    temperature: float = 0.7,
    session_id: str = None,
    purpose: str = "unknown",
    response_format: dict = None,
) -> dict:
    """三段式 Prompt 调用便捷封装（Task 6.4）。

    将 Prompt 拆分为 [Immutable Base] + [Immutable Profile] + [Compressed DST] + [Current Query]：
        - base + profile 拼接为系统提示，并计算前缀哈希注入缓存控制；
        - query + dst_state 通过 build_dynamic_tail 构建动态尾部段作为用户提示。

    该函数是 call_llm 的便捷封装，不替换 call_llm。

    Args:
        base: 不可变基础段字符串。
        profile: 不可变画像段字符串。
        query: 当前用户查询字符串。
        dst_state: 可选的 DST 状态字典。
        model: 模型名称，为 None 时使用默认模型。
        temperature: 采样温度，默认 0.7。
        session_id: 关联的会话 ID。
        purpose: 调用用途。
        response_format: 可选的响应格式约束。

    Returns:
        调用结果字典（含 prefix_hash 与 cache_hit 字段）。

    Raises:
        ValueError: 当 AI API Key 未配置时抛出。
    """
    # 构建动态尾部段（DST 状态 + 当前查询）
    dynamic_tail = build_dynamic_tail(query, dst_state)
    # 计算前缀哈希用于缓存标识
    prefix_hash = compute_prefix_hash(base, profile)
    # 拼接不可变段作为系统提示
    system_prompt = base + "\n" + profile

    # 调用 call_llm 并注入缓存控制
    return await call_llm(
        system_prompt=system_prompt,
        user_prompt=dynamic_tail,
        model=model,
        temperature=temperature,
        session_id=session_id,
        purpose=purpose,
        response_format=response_format,
        prefix_hash=prefix_hash,
    )


async def call_llm_json(
    system_prompt: str,
    user_prompt: str,
    model: str = None,
    temperature: float = 0.7,
    session_id: str = None,
    purpose: str = "unknown",
) -> dict:
    """异步调用大语言模型并解析响应为 JSON，带重试与容错机制。

    先调用 call_llm，再尝试将响应文本解析为 JSON；
    若首次解析失败，则附加 response_format={"type": "json_object"} 重试一次；
    重试仍失败时返回兜底结果。

    Args:
        system_prompt: 系统提示词。
        user_prompt: 用户提示词。
        model: 模型名称，为 None 时使用默认模型。
        temperature: 采样温度，默认 0.7。
        session_id: 关联的会话 ID。
        purpose: 调用用途。

    Returns:
        解析后的 JSON 字典；解析失败时返回兜底结果
        {"error": "JSON 解析失败", "raw_content": 原始内容}。

    Raises:
        ValueError: 当 AI API Key 未配置时抛出。
    """
    # 第一次调用
    result = await call_llm(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
        temperature=temperature,
        session_id=session_id,
        purpose=purpose,
    )

    content = result["content"]
    parsed = _parse_json(content)

    # 首次解析成功，直接返回
    if parsed is not None:
        result["content"] = parsed
        return result

    # 首次解析失败，附加 response_format 重试一次（仅当模型支持时生效）
    try:
        retry_result = await call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
            session_id=session_id,
            purpose=purpose,
            response_format={"type": "json_object"},
        )
        retry_content = retry_result["content"]
        retry_parsed = _parse_json(retry_content)
        if retry_parsed is not None:
            retry_result["content"] = retry_parsed
            return retry_result
        # 重试仍解析失败，使用重试结果作为兜底原始内容
        raw_content = retry_content
    except Exception:
        # 模型不支持 response_format 或调用失败，沿用首次原始内容
        raw_content = content

    # 全部失败，返回兜底结果
    return {"error": "JSON 解析失败", "raw_content": raw_content}


async def call_llm_stream(
    system_prompt: str,
    user_prompt: str,
    model: str = None,
    temperature: float = 0.7,
) -> AsyncIterator[str]:
    """异步流式调用大语言模型，逐块返回文本。

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

    # 异步流式调用
    stream = await client.chat.completions.create(
        model=used_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        stream=True,
    )

    async for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield delta.content


def _parse_json(text: str) -> Optional[dict]:
    """从文本中解析 JSON，支持代码块包裹、裸 JSON 及容错解析。

    解析顺序：
        1. 优先使用 json5.loads 直接解析（支持尾随逗号、单引号等）。
        2. 提取 ```json ... ``` 代码块后再用 json5 解析。
        3. 提取第一个 '{' 到最后一个 '}' 的子串后再用 json5 解析。
        4. 全部失败时返回 None。

    Args:
        text: 待解析的文本。

    Returns:
        解析后的字典；无法解析时返回 None。
    """
    if not isinstance(text, str):
        return None

    # 1. 优先直接用 json5 解析（兼容尾随逗号、单引号等宽松语法）
    try:
        return json5.loads(text)
    except (ValueError, TypeError):
        pass

    # 2. 尝试提取 ```json ... ``` 代码块后再用 json5 解析
    code_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if code_block_match:
        try:
            return json5.loads(code_block_match.group(1))
        except (ValueError, TypeError):
            pass

    # 3. 尝试提取第一个 '{' 到最后一个 '}' 的子串后再用 json5 解析
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        substring = text[first_brace : last_brace + 1]
        try:
            return json5.loads(substring)
        except (ValueError, TypeError):
            pass

    # 4. 全部失败，返回 None
    return None
