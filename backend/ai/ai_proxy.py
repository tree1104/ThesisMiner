"""统一 AI 调用代理模块

封装 OpenAI 客户端的创建、配置检查、异步调用、JSON 解析与流式调用，
并在每次调用后通过透明账本记录 token 用量与费用。

v7.0 升级为多模型架构：按 model_id 缓存独立客户端，支持步骤路由、
参数透传（max_tokens / enable_thinking / web_search）与思维链分流。
v9.0 新增能力开关：deep_thinking / web_search / streaming 三个顶层参数，
按模型 capabilities 字段过滤后生效，并保留对旧 supports_* 字段的回退兼容。
"""
import re
from typing import AsyncIterator, Optional

import json5
import openai

from backend.config import get_model_config, get_settings, get_step_model
from backend.budgets.estimator import estimate_cost
from backend.budgets.transparent_ledger import record_usage
from backend.ai.prompts import (
    build_dynamic_tail,
    compute_prefix_hash,
)
from backend.ai.prompt_cache import is_deepseek_model
from backend.ai.citation_parser import parse_citations

# 模块级客户端缓存，按 model_id 维度缓存（v7.0 多模型支持）
_clients: dict[str, openai.AsyncOpenAI] = {}


def get_client(model_id: str = None) -> openai.AsyncOpenAI:
    """创建并返回指定模型的 OpenAI 异步客户端（带按 model_id 缓存）。

    根据 model_id 从模型注册表读取 base_url 和 api_key。
    若模型 api_key 为空，回退到 settings.ai_api_key。

    Args:
        model_id: 模型唯一标识，为 None 时使用 settings.ai_model。

    Returns:
        配置好的 openai.AsyncOpenAI 客户端。
    """
    settings = get_settings()

    # 确定实际使用的 model_id
    if model_id is None:
        model_id = settings.ai_model

    # 命中缓存直接返回
    if model_id in _clients:
        return _clients[model_id]

    # 从模型注册表获取配置
    model_config = get_model_config(model_id)
    if model_config:
        base_url = model_config.get("base_url") or settings.ai_base_url
        api_key = model_config.get("api_key") or settings.ai_api_key
    else:
        # 回退到默认配置
        base_url = settings.ai_base_url
        api_key = settings.ai_api_key

    client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)
    _clients[model_id] = client
    return client


def check_api_configured() -> bool:
    """检查 AI API Key 是否已配置（非空）。

    Returns:
        已配置返回 True，否则返回 False。
    """
    settings = get_settings()
    return bool(settings.ai_api_key)


def get_model_capabilities(model_id: str) -> dict:
    """获取模型的能力开关配置（v9.0）。

    优先读取模型注册表中的 capabilities 字段（deep_thinking/web_search/streaming），
    若缺失则回退到旧字段别名（supports_thinking/supports_web_search/supports_streaming），
    若模型未注册则返回全 False 的默认能力。

    Args:
        model_id: 模型唯一标识。

    Returns:
        能力字典，包含 deep_thinking/web_search/streaming 三个布尔字段。
    """
    model_config = get_model_config(model_id)
    if not model_config:
        return {
            "deep_thinking": False,
            "web_search": False,
            "streaming": False,
        }
    capabilities = model_config.get("capabilities")
    if isinstance(capabilities, dict):
        return {
            "deep_thinking": bool(capabilities.get("deep_thinking", False)),
            "web_search": bool(capabilities.get("web_search", False)),
            "streaming": bool(capabilities.get("streaming", False)),
        }
    # 回退到旧字段别名
    return {
        "deep_thinking": bool(model_config.get("supports_thinking", False)),
        "web_search": bool(model_config.get("supports_web_search", False)),
        "streaming": bool(model_config.get("supports_streaming", False)),
    }


def _build_capability_kwargs(
    model_id: str,
    model_config: dict,
    deep_thinking: bool,
    web_search: bool,
) -> dict:
    """根据模型能力构建 deep_thinking/web_search 相关的请求参数（v9.0）。

    仅当模型 capabilities 声明支持对应能力时才注入参数，按 provider 差异化处理：
        - DeepSeek：extra_body={"reasoning": True}（deep_thinking）
        - OpenAI：reasoning_effort="high"（deep_thinking），tools=[{"type": "web_search"}]（web_search）
        - Anthropic：thinking={"type": "enabled", "budget_tokens": 10000}（deep_thinking）
        - 其他厂商：extra_body={"enable_thinking": True}（deep_thinking），extra_body={"enable_search": True}（web_search）

    Args:
        model_id: 模型 ID，用于查询能力开关。
        model_config: 模型配置字典，用于读取 provider。
        deep_thinking: 是否请求深度思考。
        web_search: 是否请求联网搜索。

    Returns:
        需要合并到请求 kwargs 的参数字典；可能包含 extra_body / reasoning_effort /
        thinking / tools 等键。extra_body 始终为字典，便于调用方合并。
    """
    capabilities = get_model_capabilities(model_id)
    provider = (model_config or {}).get("provider", "")
    extra: dict = {}

    if deep_thinking and capabilities.get("deep_thinking"):
        if provider == "deepseek":
            extra["extra_body"] = {"reasoning": True}
        elif provider == "openai":
            extra["reasoning_effort"] = "high"
        elif provider == "anthropic":
            extra["thinking"] = {
                "type": "enabled",
                "budget_tokens": 10000,
            }
        else:
            # zhipu / qwen / google / bytecode 等通过 extra_body 透传
            extra["extra_body"] = {"enable_thinking": True}

    if web_search and capabilities.get("web_search"):
        # OpenAI 风格的 web_search 工具
        if provider == "openai":
            extra["tools"] = [{"type": "web_search"}]
        # 通用 enable_search 开关（DeepSeek/智谱/通义等）
        extra_body = extra.get("extra_body")
        if extra_body is None:
            extra_body = {}
            extra["extra_body"] = extra_body
        extra_body["enable_search"] = True

    return extra


def _merge_extra_body(kwargs: dict, new_extra_body: dict) -> None:
    """将 new_extra_body 合并到 kwargs["extra_body"]，避免覆盖已有键（v9.0）。

    Args:
        kwargs: 请求参数字典，可能已包含 extra_body。
        new_extra_body: 待合并的 extra_body 字典。
    """
    if not new_extra_body:
        return
    existing = kwargs.get("extra_body")
    if not isinstance(existing, dict):
        existing = {}
    existing.update(new_extra_body)
    kwargs["extra_body"] = existing


async def call_llm(
    system_prompt: str,
    user_prompt: str,
    model: str = None,
    temperature: float = None,
    session_id: str = None,
    purpose: str = "unknown",
    response_format: dict = None,
    prefix_hash: str = None,
    extra_params: dict = None,
    cached_prefix: dict = None,
    deep_thinking: bool = False,
    web_search: bool = False,
    streaming: bool = False,
) -> dict:
    """异步调用大语言模型并记录用量（v7.0 多模型与参数透传，v9.0 能力开关）。

    模型选择优先级：显式 model > step_models[purpose] > ai_model。
    温度优先级：显式 temperature > 模型 default_temperature > 0.7。

    v9.0 新增能力开关（按模型 capabilities 过滤后生效）：
        - deep_thinking：启用深度思考/推理模式（DeepSeek/OpenAI/Claude 差异化注入）。
        - web_search：启用联网搜索工具。
        - streaming：委托给 call_llm_stream 返回异步生成器（调用方需 async for 消费）。

    Args:
        system_prompt: 系统提示词。
        user_prompt: 用户提示词。
        model: 模型 ID，为 None 时按 purpose 路由。
        temperature: 采样温度，为 None 时使用模型默认温度。
        session_id: 关联的会话 ID，用于账本记录。
        purpose: 调用用途，用于模型路由与账本记录。
        response_format: 可选的响应格式约束，如 {"type": "json_object"}，
            仅在模型支持时生效，用于 JSON 模式重试。
        prefix_hash: 可选的缓存前缀哈希。提供时会在系统消息上注入
            cache_control 提示（Anthropic 风格，OpenAI 会忽略但无害），
            并附加一条带 prefix_hash 注释的系统消息便于调试。
        extra_params: 透传参数，支持 max_tokens / enable_thinking / web_search，
            按模型能力过滤后生效。
        cached_prefix: 可选的三段式缓存前缀字典（Task 2.3），包含
            prefix_messages 与 dynamic_messages 两个键。当模型为 DeepSeek
            且提供此参数时，会前置 prefix_messages、追加 dynamic_messages，
            以提升缓存命中率。结果中会附带 prefix_char_count 字段用于监控。
        deep_thinking: v9.0 是否启用深度思考，需模型 capabilities.deep_thinking=True。
        web_search: v9.0 是否启用联网搜索，需模型 capabilities.web_search=True。
        streaming: v9.0 是否启用流式输出，为 True 时委托给 call_llm_stream
            返回异步生成器（不再返回字典）。

    Returns:
        调用结果字典，包含 content、model、prompt_tokens、completion_tokens、
        total_tokens、cached_tokens、cost，以及当存在思维链时附带
        reasoning_content，当 prefix_hash 非空时附带 prefix_hash 与 cache_hit，
        当 cached_prefix 非空时附带 prefix_char_count，以及从回复内容中
        解析出的 citations 列表（Task 10.3）。
        当 streaming=True 时返回 call_llm_stream 的异步生成器。

    Raises:
        ValueError: 当 AI API Key 未配置时抛出。
    """
    if not check_api_configured():
        raise ValueError("AI API Key 未配置，请在设置页配置")

    # v9.0：streaming 委托给 call_llm_stream，返回异步生成器
    if streaming:
        return call_llm_stream(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
            session_id=session_id,
            purpose=purpose,
            prefix_hash=prefix_hash,
            extra_params=extra_params,
            deep_thinking=deep_thinking,
            web_search=web_search,
        )

    # 模型选择优先级：显式 model > step_models[purpose] > ai_model
    if model:
        used_model = model
    else:
        used_model = get_step_model(purpose)

    # 获取模型配置（可能为 None，回退到空字典）
    model_config = get_model_config(used_model) or {}

    # 温度：优先用参数，其次模型默认，最后 0.7
    if temperature is None:
        temperature = model_config.get("default_temperature", 0.7)

    client = get_client(used_model)

    # 判断是否启用三段式缓存前缀（仅 DeepSeek 模型 + 提供 cached_prefix 时）
    use_cached_prefix = (
        cached_prefix is not None
        and is_deepseek_model(used_model)
        and isinstance(cached_prefix.get("prefix_messages"), list)
    )

    if use_cached_prefix:
        # 三段式：不可变前缀消息 + 动态尾部消息
        messages = list(cached_prefix["prefix_messages"])
        # 动态尾部消息（若提供则追加，否则回退到 user_prompt）
        dynamic_messages = cached_prefix.get("dynamic_messages")
        if dynamic_messages:
            messages.extend(dynamic_messages)
        else:
            messages.append({"role": "user", "content": user_prompt})
        prefix_char_count = len(
            cached_prefix.get("prefix", "").encode("utf-8")
        )
    else:
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
        prefix_char_count = 0

    # 构建请求参数，仅在指定 response_format 时附加（需模型支持）
    kwargs = {
        "model": used_model,
        "messages": messages,
        "temperature": temperature,
    }
    if response_format is not None:
        kwargs["response_format"] = response_format

    # v9.0：根据模型能力注入 deep_thinking / web_search 参数
    capability_kwargs = _build_capability_kwargs(
        used_model, model_config, deep_thinking, web_search
    )
    if "extra_body" in capability_kwargs:
        _merge_extra_body(kwargs, capability_kwargs.pop("extra_body"))
    kwargs.update(capability_kwargs)

    # 透传 extra_params（按模型能力过滤）
    if extra_params:
        if extra_params.get("max_tokens"):
            kwargs["max_tokens"] = extra_params["max_tokens"]
        # DeepSeek 思考模式：reasoner 模型自动启用思考，无需额外参数
        if extra_params.get("enable_thinking") and model_config.get(
            "supports_thinking"
        ):
            pass
        # 联网搜索（部分模型支持，通过 extra_body 传递）
        if extra_params.get("web_search") and model_config.get(
            "supports_web_search"
        ):
            _merge_extra_body(kwargs, {"enable_search": True})

    # 异步调用大模型
    response = await client.chat.completions.create(**kwargs)

    # 提取 token 用量
    usage = response.usage
    prompt_tokens = usage.prompt_tokens if usage else 0
    completion_tokens = usage.completion_tokens if usage else 0
    total_tokens = usage.total_tokens if usage else (
        prompt_tokens + completion_tokens
    )

    # 提取缓存命中 token 数（OpenAI prompt_tokens_details.cached_tokens）
    cached_tokens = 0
    if (
        usage
        and hasattr(usage, "prompt_tokens_details")
        and usage.prompt_tokens_details
    ):
        cached_tokens = (
            getattr(usage.prompt_tokens_details, "cached_tokens", 0) or 0
        )

    # 提取内容与思维链
    content = ""
    reasoning_content = None
    if response.choices:
        message = response.choices[0].message
        content = message.content or ""
        # DeepSeek 思维链字段
        if hasattr(message, "reasoning_content") and message.reasoning_content:
            reasoning_content = message.reasoning_content
        # 也检查 reasoning 字段（部分模型）
        elif hasattr(message, "reasoning") and message.reasoning:
            reasoning_content = message.reasoning

    cost = estimate_cost(used_model, prompt_tokens, completion_tokens)

    # 记录到透明账本（传入 cached_tokens，Task 5 将启用写入）
    record_usage(
        session_id=session_id,
        model=used_model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        purpose=purpose,
        cached_tokens=cached_tokens,
    )

    result = {
        "content": content,
        "model": used_model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cached_tokens": cached_tokens,
        "cost": cost,
        # Task 10.3：从回复内容中解析引用
        "citations": parse_citations(content),
    }
    if reasoning_content:
        result["reasoning_content"] = reasoning_content
    # 当注入了缓存前缀时，附带缓存追踪信息
    if prefix_hash:
        result["prefix_hash"] = prefix_hash
        result["cache_hit"] = cached_tokens > 0
    # Task 2.3：当启用三段式缓存前缀时，附带前缀字符数用于监控
    if use_cached_prefix:
        result["prefix_char_count"] = prefix_char_count
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
    deep_thinking: bool = False,
    web_search: bool = False,
    streaming: bool = False,
) -> dict:
    """异步调用大语言模型并解析响应为 JSON，带重试与容错机制。

    先调用 call_llm，再尝试将响应文本解析为 JSON；
    若首次解析失败，则附加 response_format={"type": "json_object"} 重试一次；
    重试仍失败时返回兜底结果。

    v9.0 新增 deep_thinking / web_search / streaming 透传参数，语义与 call_llm 一致。

    Args:
        system_prompt: 系统提示词。
        user_prompt: 用户提示词。
        model: 模型名称，为 None 时使用默认模型。
        temperature: 采样温度，默认 0.7。
        session_id: 关联的会话 ID。
        purpose: 调用用途。
        deep_thinking: v9.0 是否启用深度思考。
        web_search: v9.0 是否启用联网搜索。
        streaming: v9.0 是否启用流式输出（透传给 call_llm）。

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
        deep_thinking=deep_thinking,
        web_search=web_search,
        streaming=streaming,
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
            deep_thinking=deep_thinking,
            web_search=web_search,
            streaming=streaming,
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
    temperature: float = None,
    session_id: str = None,
    purpose: str = "unknown",
    prefix_hash: str = None,
    extra_params: dict = None,
    deep_thinking: bool = False,
    web_search: bool = False,
) -> AsyncIterator[dict]:
    """异步流式调用大语言模型，支持思维链分流（v7.0，v9.0 能力开关）。

    模型选择与温度策略与 call_llm 一致。

    v9.0 新增 deep_thinking / web_search 能力开关，按模型 capabilities 过滤后生效，
    注入逻辑与 call_llm 一致（通过 _build_capability_kwargs 统一处理）。

    Args:
        system_prompt: 系统提示词。
        user_prompt: 用户提示词。
        model: 模型 ID，为 None 时按 purpose 路由。
        temperature: 采样温度，为 None 时使用模型默认温度。
        session_id: 关联的会话 ID（预留，暂不记录流式用量）。
        purpose: 调用用途，用于模型路由。
        prefix_hash: 可选的缓存前缀哈希。
        extra_params: 透传参数，支持 max_tokens / web_search。
        deep_thinking: v9.0 是否启用深度思考，需模型 capabilities.deep_thinking=True。
        web_search: v9.0 是否启用联网搜索，需模型 capabilities.web_search=True。

    Yields:
        {"type": "reasoning", "content": "..."} - 思维链片段
        {"type": "content", "content": "..."} - 正文片段

    Raises:
        ValueError: 当 AI API Key 未配置时抛出。
    """
    if not check_api_configured():
        raise ValueError("AI API Key 未配置，请在设置页配置")

    # 模型选择优先级：显式 model > step_models[purpose] > ai_model
    if model:
        used_model = model
    else:
        used_model = get_step_model(purpose)

    model_config = get_model_config(used_model) or {}
    if temperature is None:
        temperature = model_config.get("default_temperature", 0.7)

    client = get_client(used_model)

    # 构建消息列表
    messages = [
        {"role": "system", "content": system_prompt},
    ]
    if prefix_hash:
        messages[0]["cache_control"] = {"type": "ephemeral"}
        messages.append(
            {"role": "system", "content": f"[cache_prefix_id:{prefix_hash}]"}
        )
    messages.append({"role": "user", "content": user_prompt})

    # 构建请求参数
    kwargs = {
        "model": used_model,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }

    # v9.0：根据模型能力注入 deep_thinking / web_search 参数
    capability_kwargs = _build_capability_kwargs(
        used_model, model_config, deep_thinking, web_search
    )
    if "extra_body" in capability_kwargs:
        _merge_extra_body(kwargs, capability_kwargs.pop("extra_body"))
    kwargs.update(capability_kwargs)

    if extra_params:
        if extra_params.get("max_tokens"):
            kwargs["max_tokens"] = extra_params["max_tokens"]
        if extra_params.get("web_search") and model_config.get(
            "supports_web_search"
        ):
            _merge_extra_body(kwargs, {"enable_search": True})

    # 异步流式调用
    response = await client.chat.completions.create(**kwargs)

    async for chunk in response:
        if chunk.choices and chunk.choices[0].delta:
            delta = chunk.choices[0].delta
            # 正文内容
            if delta.content:
                yield {"type": "content", "content": delta.content}
            # 思维链内容（DeepSeek）
            if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                yield {"type": "reasoning", "content": delta.reasoning_content}
            elif hasattr(delta, "reasoning") and delta.reasoning:
                yield {"type": "reasoning", "content": delta.reasoning}


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
