#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ThesisMiner v8.0 集成示例代码
================================

本文件提供 ThesisMiner v8.0 与外部系统集成的完整示例，涵盖五大场景：

    1. 第三方模型集成（非 OpenAI 兼容模型 / 自定义客户端 / 适配器模式）
    2. 外部检索源接入（PubMed API / arXiv API / Google Scholar / 自定义检索源）
    3. Webhook 集成（论题生成完成通知 / Slack / 钉钉 / 企业微信）
    4. CI/CD 集成（GitHub Actions / 自动化测试 / 部署流水线）
    5. 监控集成（Prometheus 指标 / Grafana 面板 / 告警规则）

所有示例均可独立运行，开发者可根据实际需求裁剪组合。
本文件仅作示例用途，不构成生产环境直接可用代码。

作者：ThesisMiner 团队
版本：v8.0.0
许可证：MIT
"""

from __future__ import annotations

# =============================================================================
# 标准库导入
# =============================================================================
import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    Tuple,
    Union,
)
from urllib.parse import quote_plus, urlencode

# =============================================================================
# 第三方库导入（示例中使用，实际运行需安装）
# =============================================================================
# import httpx              # HTTP 客户端
# import prometheus_client  # Prometheus 指标导出
# import yaml               # YAML 配置解析
# from cryptography.fernet import Fernet  # 加密

# =============================================================================
# 全局日志配置
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("thesisminer.integrations")


# =============================================================================
# 第一部分：公共定义
# =============================================================================

class IntegrationType(Enum):
    """集成类型枚举。"""

    MODEL_PROVIDER = "model_provider"       # 第三方模型提供商
    SEARCH_SOURCE = "search_source"         # 外部检索源
    WEBHOOK = "webhook"                     # Webhook 通知
    CICD = "cicd"                           # CI/CD 流水线
    MONITORING = "monitoring"               # 监控系统


@dataclass
class IntegrationConfig:
    """
    集成配置基类。

    所有集成配置均继承此类，确保统一的配置管理接口。

    Attributes:
        name: 集成名称，用于日志和注册表标识
        enabled: 是否启用该集成
        timeout: 请求超时时间（秒）
        retry_count: 失败重试次数
        retry_backoff: 重试退避基数（秒），实际退避 = backoff * 2^attempt
    """

    name: str
    enabled: bool = True
    timeout: float = 30.0
    retry_count: int = 3
    retry_backoff: float = 1.0

    def validate(self) -> List[str]:
        """校验配置有效性，返回错误信息列表。"""
        errors: List[str] = []
        if not self.name or not self.name.strip():
            errors.append("集成名称不能为空")
        if self.timeout <= 0:
            errors.append(f"超时时间必须大于 0，当前值：{self.timeout}")
        if self.retry_count < 0:
            errors.append(f"重试次数不能为负数，当前值：{self.retry_count}")
        if self.retry_backoff <= 0:
            errors.append(f"重试退避必须大于 0，当前值：{self.retry_backoff}")
        return errors


@dataclass
class IntegrationResult:
    """
    集成调用结果。

    统一封装所有集成调用的返回值，便于上层处理。

    Attributes:
        success: 是否成功
        data: 返回数据（成功时）
        error: 错误信息（失败时）
        elapsed: 耗时（秒）
        metadata: 额外元数据
    """

    success: bool
    data: Any = None
    error: Optional[str] = None
    elapsed: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, data: Any, elapsed: float = 0.0, **metadata: Any) -> "IntegrationResult":
        """创建成功结果。"""
        return cls(success=True, data=data, elapsed=elapsed, metadata=metadata)

    @classmethod
    def fail(cls, error: str, elapsed: float = 0.0, **metadata: Any) -> "IntegrationResult":
        """创建失败结果。"""
        return cls(success=False, error=error, elapsed=elapsed, metadata=metadata)

    def __str__(self) -> str:
        status = "成功" if self.success else "失败"
        return f"IntegrationResult({status}, 耗时={self.elapsed:.3f}s)"


class IntegrationRegistry:
    """
    集成注册表。

    管理所有已注册的集成实例，支持按名称和类型检索。

    用法示例::

        registry = IntegrationRegistry()
        registry.register("my_model", model_integration)
        integration = registry.get("my_model")
    """

    def __init__(self) -> None:
        self._integrations: Dict[str, Any] = {}
        self._by_type: Dict[IntegrationType, Dict[str, Any]] = defaultdict(dict)

    def register(self, name: str, integration: Any, itype: IntegrationType) -> None:
        """注册集成实例。"""
        if name in self._integrations:
            raise ValueError(f"集成名称已存在：{name}")
        self._integrations[name] = integration
        self._by_type[itype][name] = integration
        logger.info("已注册集成：%s（类型：%s）", name, itype.value)

    def get(self, name: str) -> Optional[Any]:
        """按名称获取集成实例。"""
        return self._integrations.get(name)

    def get_by_type(self, itype: IntegrationType) -> Dict[str, Any]:
        """按类型获取所有集成实例。"""
        return dict(self._by_type.get(itype, {}))

    def unregister(self, name: str) -> bool:
        """注销集成实例。"""
        if name not in self._integrations:
            return False
        self._integrations.pop(name)
        for itype_dict in self._by_type.values():
            itype_dict.pop(name, None)
        logger.info("已注销集成：%s", name)
        return True

    def list_all(self) -> List[str]:
        """列出所有已注册的集成名称。"""
        return list(self._integrations.keys())

    def __len__(self) -> int:
        return len(self._integrations)

    def __contains__(self, name: str) -> bool:
        return name in self._integrations


# 全局注册表实例
global_registry = IntegrationRegistry()


# =============================================================================
# 第二部分：第三方模型集成
# =============================================================================
# 本部分演示如何将非 OpenAI 兼容的模型接入 ThesisMiner。
#
# ThesisMiner 默认支持 OpenAI 兼容 API（如 DeepSeek、通义千问等），
# 但部分模型（如百度文心、讯飞星火、自部署 vLLM）使用不同的 API 格式，
# 需要通过适配器模式进行封装。
# =============================================================================


@dataclass
class ModelProviderConfig(IntegrationConfig):
    """
    模型提供商配置。

    Attributes:
        api_base: API 基础 URL
        api_key: API 密钥
        model_name: 模型名称
        max_tokens: 最大生成 token 数
        temperature: 采样温度（0.0-2.0）
        top_p: 核采样概率（0.0-1.0）
        extra_params: 额外参数（提供商特定）
    """

    api_base: str = ""
    api_key: str = ""
    model_name: str = ""
    max_tokens: int = 4096
    temperature: float = 0.7
    top_p: float = 0.9
    extra_params: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> List[str]:
        """校验配置。"""
        errors = super().validate()
        if not self.api_base:
            errors.append("API 基础 URL 不能为空")
        if not self.model_name:
            errors.append("模型名称不能为空")
        if not (0.0 <= self.temperature <= 2.0):
            errors.append(f"temperature 必须在 0.0-2.0 之间，当前值：{self.temperature}")
        if not (0.0 <= self.top_p <= 1.0):
            errors.append(f"top_p 必须在 0.0-1.0 之间，当前值：{self.top_p}")
        if self.max_tokens <= 0:
            errors.append(f"max_tokens 必须大于 0，当前值：{self.max_tokens}")
        return errors

    def mask_key(self) -> str:
        """脱敏显示 API Key。"""
        if not self.api_key or len(self.api_key) <= 8:
            return "***"
        return self.api_key[:4] + "*" * (len(self.api_key) - 8) + self.api_key[-4:]


@dataclass
class ChatMessage:
    """对话消息。"""

    role: str  # "system" | "user" | "assistant"
    content: str

    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}

    @classmethod
    def system(cls, content: str) -> "ChatMessage":
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> "ChatMessage":
        return cls(role="user", content=content)

    @classmethod
    def assistant(cls, content: str) -> "ChatMessage":
        return cls(role="assistant", content=content)


@dataclass
class ChatResponse:
    """模型响应。"""

    content: str
    model: str
    usage: Dict[str, int] = field(default_factory=dict)
    finish_reason: str = "stop"
    raw: Optional[Dict[str, Any]] = None

    @property
    def total_tokens(self) -> int:
        return self.usage.get("total_tokens", 0)

    @property
    def prompt_tokens(self) -> int:
        return self.usage.get("prompt_tokens", 0)

    @property
    def completion_tokens(self) -> int:
        return self.usage.get("completion_tokens", 0)


class BaseModelAdapter(ABC):
    """
    模型适配器抽象基类。

    所有第三方模型适配器均需继承此类并实现 ``chat`` 和 ``stream_chat`` 方法。
    适配器负责将 ThesisMiner 统一的 ChatMessage 格式转换为目标模型的 API 格式，
    并将响应转换回 ChatResponse。

    设计模式：适配器模式（Adapter Pattern）

    用法示例::

        class MyModelAdapter(BaseModelAdapter):
            def chat(self, messages, **kwargs):
                # 实现具体调用逻辑
                ...

        adapter = MyModelAdapter(config)
        response = adapter.chat([ChatMessage.user("你好")])
    """

    def __init__(self, config: ModelProviderConfig) -> None:
        self.config = config
        errors = config.validate()
        if errors:
            raise ValueError(f"模型配置校验失败：{'; '.join(errors)}")
        self._call_count = 0
        self._total_tokens = 0
        self._error_count = 0
        logger.debug(
            "初始化模型适配器：%s（模型：%s，API：%s，Key：%s）",
            config.name, config.model_name, config.api_base, config.mask_key(),
        )

    @abstractmethod
    async def chat(
        self, messages: List[ChatMessage], **kwargs: Any
    ) -> IntegrationResult:
        """
        对话接口（async）。

        Args:
            messages: 对话消息列表
            **kwargs: 额外参数（覆盖配置中的默认值）

        Returns:
            IntegrationResult，data 字段为 ChatResponse
        """
        ...

    @abstractmethod
    async def stream_chat(
        self, messages: List[ChatMessage], **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """
        流式对话接口。

        Args:
            messages: 对话消息列表
            **kwargs: 额外参数

        Yields:
            增量文本片段
        """
        ...
        yield ""  # pragma: no cover

    def get_stats(self) -> Dict[str, Any]:
        """获取调用统计。"""
        return {
            "name": self.config.name,
            "model": self.config.model_name,
            "call_count": self._call_count,
            "total_tokens": self._total_tokens,
            "error_count": self._error_count,
            "error_rate": self._error_count / max(self._call_count, 1),
        }

    def _record_success(self, response: ChatResponse) -> None:
        """记录成功调用。"""
        self._call_count += 1
        self._total_tokens += response.total_tokens

    def _record_error(self) -> None:
        """记录失败调用。"""
        self._call_count += 1
        self._error_count += 1

    async def _retry_with_backoff(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> IntegrationResult:
        """
        带指数退避的重试包装器。

        Args:
            func: 异步函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            IntegrationResult
        """
        last_error: Optional[str] = None
        start_time = time.time()

        for attempt in range(self.config.retry_count + 1):
            try:
                result = await func(*args, **kwargs)
                elapsed = time.time() - start_time
                if isinstance(result, IntegrationResult):
                    result.elapsed = elapsed
                    return result
                return IntegrationResult.ok(result, elapsed=elapsed)
            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "调用失败（尝试 %d/%d）：%s",
                    attempt + 1, self.config.retry_count + 1, last_error,
                )
                if attempt < self.config.retry_count:
                    backoff = self.config.retry_backoff * (2 ** attempt)
                    logger.info("等待 %.1f 秒后重试...", backoff)
                    await asyncio.sleep(backoff)

        elapsed = time.time() - start_time
        return IntegrationResult.fail(
            last_error or "未知错误",
            elapsed=elapsed,
            attempts=self.config.retry_count + 1,
        )


# -----------------------------------------------------------------------------
# 示例 2.1：百度文心一言（ERNIE Bot）适配器
# -----------------------------------------------------------------------------
# 百度文心一言使用 OAuth 2.0 获取 access_token，API 格式与 OpenAI 不同。
# 本适配器演示如何处理 token 刷新和非标准响应格式。
# -----------------------------------------------------------------------------


class ErnieBotAdapter(BaseModelAdapter):
    """
    百度文心一言（ERNIE Bot）模型适配器。

    百度文心 API 特点：
        - 使用 OAuth 2.0 获取 access_token（有效期 30 天）
        - 请求体使用 ``messages`` 数组，但 role 仅支持 user/assistant
        - system 消息需通过单独的 ``system`` 字段传递
        - 响应体使用 ``result`` 字段而非 ``choices[0].message.content``

    配置示例::

        config = ModelProviderConfig(
            name="ernie-bot",
            api_base="https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions",
            api_key="your_api_key",  # 实际为 client_id
            model_name="ernie-bot-4",
            extra_params={"client_secret": "your_client_secret"},
        )
    """

    def __init__(self, config: ModelProviderConfig) -> None:
        super().__init__(config)
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._client_secret: str = config.extra_params.get("client_secret", "")

    async def _ensure_token(self) -> str:
        """
        确保 access_token 有效，过期则自动刷新。

        Returns:
            有效的 access_token

        Raises:
            RuntimeError: 获取 token 失败
        """
        if self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token

        logger.info("正在刷新百度文心 access_token...")
        # 实际实现应使用 httpx 发起 HTTP 请求
        # token_url = (
        #     "https://aip.baidubce.com/oauth/2.0/token?"
        #     f"grant_type=client_credentials&client_id={self.config.api_key}"
        #     f"&client_secret={self._client_secret}"
        # )
        # async with httpx.AsyncClient() as client:
        #     resp = await client.post(token_url, timeout=self.config.timeout)
        #     data = resp.json()
        #     self._access_token = data["access_token"]
        #     self._token_expires_at = time.time() + data.get("expires_in", 2592000)

        # 示例模拟
        self._access_token = f"mock_token_{uuid.uuid4().hex[:16]}"
        self._token_expires_at = time.time() + 2592000  # 30 天
        logger.info("access_token 刷新成功")
        return self._access_token

    def _convert_messages(self, messages: List[ChatMessage]) -> Tuple[List[Dict], str]:
        """
        将统一消息格式转换为文心 API 格式。

        文心 API 的 system 消息需单独传递，不能放在 messages 数组中。

        Args:
            messages: 统一格式消息列表

        Returns:
            (messages_list, system_prompt) 元组
        """
        system_parts: List[str] = []
        converted: List[Dict[str, str]] = []

        for msg in messages:
            if msg.role == "system":
                system_parts.append(msg.content)
            else:
                converted.append(msg.to_dict())

        system_prompt = "\n".join(system_parts)
        return converted, system_prompt

    async def chat(
        self, messages: List[ChatMessage], **kwargs: Any
    ) -> IntegrationResult:
        """
        调用文心一言对话接口。

        Args:
            messages: 对话消息列表
            **kwargs: 额外参数（temperature, max_tokens 等）

        Returns:
            IntegrationResult，data 为 ChatResponse
        """
        start_time = time.time()

        async def _do_chat() -> ChatResponse:
            token = await self._ensure_token()
            msg_list, system_prompt = self._convert_messages(messages)

            request_body: Dict[str, Any] = {
                "messages": msg_list,
                "temperature": kwargs.get("temperature", self.config.temperature),
                "max_output_tokens": kwargs.get("max_tokens", self.config.max_tokens),
                "top_p": kwargs.get("top_p", self.config.top_p),
            }
            if system_prompt:
                request_body["system"] = system_prompt

            # 实际 HTTP 调用（示例中省略）
            # url = f"{self.config.api_base}?access_token={token}"
            # async with httpx.AsyncClient() as client:
            #     resp = await client.post(url, json=request_body, timeout=self.config.timeout)
            #     data = resp.json()
            #     if "error_code" in data:
            #         raise RuntimeError(f"文心 API 错误：{data['error_code']}")

            # 模拟响应
            data = {
                "result": f"[文心一言回复] 收到您的请求，共 {len(msg_list)} 条消息。",
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                },
                "finish_reason": "stop",
            }

            response = ChatResponse(
                content=data["result"],
                model=self.config.model_name,
                usage=data.get("usage", {}),
                finish_reason=data.get("finish_reason", "stop"),
                raw=data,
            )
            self._record_success(response)
            return response

        result = await self._retry_with_backoff(_do_chat)
        if not result.success:
            self._record_error()
        return result

    async def stream_chat(
        self, messages: List[ChatMessage], **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """
        流式调用文心一言。

        文心 API 流式响应使用 SSE 格式，每个事件的 data 字段包含增量文本。
        """
        token = await self._ensure_token()
        msg_list, system_prompt = self._convert_messages(messages)

        # 模拟流式输出
        mock_chunks = [
            "[文心一言] ",
            "正在流式 ",
            "输出回复内容...",
            f"\n共处理 {len(msg_list)} 条消息。",
        ]
        for chunk in mock_chunks:
            await asyncio.sleep(0.05)  # 模拟网络延迟
            yield chunk


# -----------------------------------------------------------------------------
# 示例 2.2：讯飞星火（Spark）适配器
# -----------------------------------------------------------------------------
# 讯飞星火使用 WebSocket 协议，并要求对请求进行 HMAC-SHA256 签名。
# 本适配器演示如何处理签名认证和 WebSocket 通信。
# -----------------------------------------------------------------------------


class SparkAdapter(BaseModelAdapter):
    """
    讯飞星火（Spark）模型适配器。

    讯飞星火 API 特点：
        - 使用 WebSocket 协议（wss://）
        - 请求需 HMAC-SHA256 签名认证
        - 签名串包含 host, date, request-line
        - 响应通过 WebSocket 帧推送

    配置示例::

        config = ModelProviderConfig(
            name="spark",
            api_base="wss://spark-api.xf-yun.com/v3.5/chat",
            api_key="your_api_secret",  # 实际为 APISecret
            model_name="spark-v3.5",
            extra_params={
                "appid": "your_appid",
                "api_key": "your_api_key",
            },
        )
    """

    def __init__(self, config: ModelProviderConfig) -> None:
        super().__init__(config)
        self._appid: str = config.extra_params.get("appid", "")
        self._api_key: str = config.extra_params.get("api_key", "")
        if not self._appid or not self._api_key:
            logger.warning("讯飞星火适配器缺少 appid 或 api_key")

    def _generate_auth_url(self) -> str:
        """
        生成带签名的 WebSocket URL。

        讯飞星火要求对请求进行 HMAC-SHA256 签名，
        签名串格式为：host\ndate\nrequest-line

        签名算法::

            1. 构造签名串：host\\ndate\\nGET {path} HTTP/1.1
            2. 使用 HMAC-SHA256 对签名串加密
            3. Base64 编码签名结果
            4. 构造 authorization：api_key, signature
            5. URL 编码后拼接到 URL
        """
        host = "spark-api.xf-yun.com"
        path = "/v3.5/chat"
        date_str = datetime.now(timezone.utc).strftime(
            "%a, %d %b %Y %H:%M:%S GMT"
        )

        # 构造签名串
        signature_origin = f"host: {host}\ndate: {date_str}\nGET {path} HTTP/1.1"

        # HMAC-SHA256 签名
        signature_sha = hmac.new(
            self.config.api_key.encode("utf-8"),
            signature_origin.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        signature_b64 = base64.b64encode(signature_sha).decode("utf-8")

        # 构造 authorization
        authorization_origin = (
            f'api_key="{self._api_key}", '
            f'algorithm="hmac-sha256", '
            f'headers="host date request-line", '
            f'signature="{signature_b64}"'
        )
        authorization = base64.b64encode(
            authorization_origin.encode("utf-8")
        ).decode("utf-8")

        # 拼接最终 URL
        params = urlencode(
            {
                "authorization": authorization,
                "date": date_str,
                "host": host,
            }
        )
        return f"wss://{host}{path}?{params}"

    def _build_request(self, messages: List[ChatMessage]) -> Dict[str, Any]:
        """
        构造讯飞星火请求体。

        星火 API 的消息格式与 OpenAI 类似，但 header 和 parameter 结构不同。

        Args:
            messages: 统一格式消息列表

        Returns:
            星火 API 请求体
        """
        return {
            "header": {
                "app_id": self._appid,
                "uid": str(uuid.uuid4()),
            },
            "parameter": {
                "chat": {
                    "domain": self.config.model_name,
                    "temperature": self.config.temperature,
                    "max_tokens": self.config.max_tokens,
                    "top_k": int(1 / self.config.top_p * 10),
                }
            },
            "payload": {
                "message": {
                    "text": [msg.to_dict() for msg in messages]
                }
            },
        }

    async def chat(
        self, messages: List[ChatMessage], **kwargs: Any
    ) -> IntegrationResult:
        """
        调用讯飞星火对话接口。

        通过 WebSocket 发送请求，接收完整响应后返回。

        Args:
            messages: 对话消息列表
            **kwargs: 额外参数

        Returns:
            IntegrationResult
        """
        start_time = time.time()

        async def _do_chat() -> ChatResponse:
            auth_url = self._generate_auth_url()
            request_body = self._build_request(messages)

            # 实际 WebSocket 调用（示例中省略）
            # import websockets
            # async with websockets.connect(auth_url) as ws:
            #     await ws.send(json.dumps(request_body))
            #     full_content = ""
            #     usage = {}
            #     while True:
            #         response = json.loads(await ws.recv())
            #         if response["header"]["code"] != 0:
            #             raise RuntimeError(f"星火 API 错误：{response['header']['message']}")
            #         full_content += response["payload"]["choices"]["text"][0]["content"]
            #         usage = response["payload"].get("usage", {})
            #         if response["header"]["status"] == 2:  # 2 表示结束
            #             break

            # 模拟响应
            full_content = f"[讯飞星火回复] 收到 {len(messages)} 条消息。"
            usage = {"prompt_tokens": 80, "completion_tokens": 40, "total_tokens": 120}

            response = ChatResponse(
                content=full_content,
                model=self.config.model_name,
                usage=usage,
                finish_reason="stop",
            )
            self._record_success(response)
            return response

        result = await self._retry_with_backoff(_do_chat)
        if not result.success:
            self._record_error()
        return result

    async def stream_chat(
        self, messages: List[ChatMessage], **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """流式调用讯飞星火。"""
        # 模拟流式输出
        mock_chunks = [
            "[讯飞星火] ",
            "WebSocket ",
            "流式输出中...",
            f"\n模型：{self.config.model_name}",
        ]
        for chunk in mock_chunks:
            await asyncio.sleep(0.05)
            yield chunk


# -----------------------------------------------------------------------------
# 示例 2.3：自部署 vLLM 适配器
# -----------------------------------------------------------------------------
# vLLM 是高性能 LLM 推理引擎，支持 OpenAI 兼容 API，
# 但部分高级功能（如 prefix caching 提示）需要自定义处理。
# -----------------------------------------------------------------------------


class VLLMAdapter(BaseModelAdapter):
    """
    自部署 vLLM 模型适配器。

    vLLM 特点：
        - 兼容 OpenAI API 格式，可直接使用 /v1/chat/completions
        - 支持 PagedAttention，吞吐量高
        - 支持 prefix caching，可通过 prompt_logprobs 优化
        - 支持张量并行（tensor_parallel_size）

    配置示例::

        config = ModelProviderConfig(
            name="vllm-local",
            api_base="http://localhost:8000/v1",
            api_key="EMPTY",  # vLLM 默认不需要 key
            model_name="meta-llama/Llama-3-70B-Instruct",
            max_tokens=2048,
            extra_params={
                "tensor_parallel_size": 2,
                "enable_prefix_caching": True,
            },
        )
    """

    def __init__(self, config: ModelProviderConfig) -> None:
        super().__init__(config)
        self._prefix_cache: Dict[str, str] = {}  # prefix_hash -> cached_response

    def _compute_prefix_hash(self, messages: List[ChatMessage]) -> str:
        """
        计算消息前缀的 SHA-256 哈希。

        用于 prefix caching 优化：当 system prompt 和前几条消息相同时，
        可复用缓存的 KV cache，减少推理延迟。

        Args:
            messages: 消息列表

        Returns:
            前 32 字符的 SHA-256 哈希（十六进制）
        """
        prefix_text = ""
        for msg in messages[:3]:  # 取前 3 条消息作为前缀
            prefix_text += f"{msg.role}:{msg.content[:200]};"
        return hashlib.sha256(prefix_text.encode("utf-8")).hexdigest()[:32]

    def _build_request(self, messages: List[ChatMessage]) -> Dict[str, Any]:
        """
        构造 vLLM 请求体。

        vLLM 兼容 OpenAI 格式，但额外支持以下参数：
            - use_cache: 是否使用 prefix cache
            - prompt_logprobs: 返回 prompt 的 logprobs

        Args:
            messages: 消息列表

        Returns:
            vLLM 请求体
        """
        request: Dict[str, Any] = {
            "model": self.config.model_name,
            "messages": [msg.to_dict() for msg in messages],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
        }

        # vLLM 特有参数
        if self.config.extra_params.get("enable_prefix_caching"):
            prefix_hash = self._compute_prefix_hash(messages)
            request["prompt_cache_id"] = prefix_hash

        return request

    async def chat(
        self, messages: List[ChatMessage], **kwargs: Any
    ) -> IntegrationResult:
        """
        调用 vLLM 对话接口。

        Args:
            messages: 消息列表
            **kwargs: 额外参数

        Returns:
            IntegrationResult
        """
        start_time = time.time()

        async def _do_chat() -> ChatResponse:
            request_body = self._build_request(messages)

            # 实际 HTTP 调用
            # url = f"{self.config.api_base}/chat/completions"
            # headers = {"Authorization": f"Bearer {self.config.api_key}"}
            # async with httpx.AsyncClient() as client:
            #     resp = await client.post(
            #         url, json=request_body, headers=headers,
            #         timeout=self.config.timeout
            #     )
            #     data = resp.json()

            # 模拟响应
            data = {
                "choices": [
                    {
                        "message": {
                            "content": f"[vLLM 回复] 模型 {self.config.model_name} 处理完成。",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 120,
                    "completion_tokens": 60,
                    "total_tokens": 180,
                },
            }

            content = data["choices"][0]["message"]["content"]
            response = ChatResponse(
                content=content,
                model=self.config.model_name,
                usage=data.get("usage", {}),
                finish_reason=data["choices"][0].get("finish_reason", "stop"),
                raw=data,
            )
            self._record_success(response)
            return response

        result = await self._retry_with_backoff(_do_chat)
        if not result.success:
            self._record_error()
        return result

    async def stream_chat(
        self, messages: List[ChatMessage], **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """流式调用 vLLM。"""
        # 模拟流式输出
        mock_chunks = [
            "[vLLM] ",
            "PagedAttention ",
            "加速推理中...",
            f"\n模型：{self.config.model_name}",
            "\n前缀缓存：已启用" if self.config.extra_params.get("enable_prefix_caching") else "",
        ]
        for chunk in mock_chunks:
            await asyncio.sleep(0.03)  # vLLM 推理速度快，延迟更短
            yield chunk


# -----------------------------------------------------------------------------
# 示例 2.4：模型路由器（多模型 A/B 测试与降级）
# -----------------------------------------------------------------------------


class ModelRouter:
    """
    模型路由器。

    根据策略将请求路由到不同的模型适配器，支持：
        - 加权随机（A/B 测试）
        - 故障转移（failover）
        - 成本优先（选择最便宜的可用模型）
        - 延迟优先（选择最快的可用模型）

    用法示例::

        router = ModelRouter()
        router.add_adapter("ernie", ernie_adapter, weight=0.3, cost_per_1k=0.012)
        router.add_adapter("spark", spark_adapter, weight=0.3, cost_per_1k=0.015)
        router.add_adapter("vllm", vllm_adapter, weight=0.4, cost_per_1k=0.001)

        result = await router.route(messages)
    """

    def __init__(self, strategy: str = "weighted") -> None:
        """
        初始化路由器。

        Args:
            strategy: 路由策略
                - "weighted": 加权随机（A/B 测试）
                - "failover": 故障转移（按优先级顺序）
                - "cost": 成本优先
                - "latency": 延迟优先
        """
        self.strategy = strategy
        self._adapters: Dict[str, BaseModelAdapter] = {}
        self._weights: Dict[str, float] = {}
        self._costs: Dict[str, float] = {}  # 每 1K token 成本（美元）
        self._latencies: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self._health: Dict[str, bool] = {}

    def add_adapter(
        self,
        name: str,
        adapter: BaseModelAdapter,
        weight: float = 1.0,
        cost_per_1k: float = 0.0,
    ) -> None:
        """
        添加模型适配器。

        Args:
            name: 适配器名称
            adapter: 适配器实例
            weight: 权重（用于加权随机策略）
            cost_per_1k: 每 1K token 成本（美元）
        """
        self._adapters[name] = adapter
        self._weights[name] = weight
        self._costs[name] = cost_per_1k
        self._health[name] = True
        logger.info(
            "路由器添加模型：%s（权重：%.2f，成本：$%.4f/1K）",
            name, weight, cost_per_1k,
        )

    def _select_adapter(self) -> Tuple[str, BaseModelAdapter]:
        """
        根据策略选择适配器。

        Returns:
            (名称, 适配器) 元组

        Raises:
            RuntimeError: 没有可用的适配器
        """
        available = {
            name: adapter
            for name, adapter in self._adapters.items()
            if self._health.get(name, True)
        }
        if not available:
            raise RuntimeError("没有可用的模型适配器")

        if self.strategy == "failover":
            # 按添加顺序返回第一个可用的
            name = next(iter(available))
            return name, available[name]

        if self.strategy == "cost":
            # 选择成本最低的
            name = min(available, key=lambda n: self._costs.get(n, float("inf")))
            return name, available[name]

        if self.strategy == "latency":
            # 选择平均延迟最低的
            def avg_latency(n: str) -> float:
                latencies = self._latencies.get(n)
                if not latencies:
                    return 0.0
                return sum(latencies) / len(latencies)
            name = min(available, key=avg_latency)
            return name, available[name]

        # 默认加权随机
        import random
        names = list(available.keys())
        weights = [self._weights.get(n, 1.0) for n in names]
        name = random.choices(names, weights=weights, k=1)[0]
        return name, available[name]

    async def route(
        self, messages: List[ChatMessage], **kwargs: Any
    ) -> IntegrationResult:
        """
        路由请求到选定的模型适配器。

        如果选定的适配器失败，自动尝试下一个（故障转移）。

        Args:
            messages: 消息列表
            **kwargs: 额外参数

        Returns:
            IntegrationResult
        """
        tried: List[str] = []
        start_time = time.time()

        while True:
            try:
                name, adapter = self._select_adapter()
            except RuntimeError:
                return IntegrationResult.fail(
                    f"所有模型适配器均不可用，已尝试：{tried}",
                    elapsed=time.time() - start_time,
                )

            if name in tried:
                # 已经试过这个，找下一个
                self._health[name] = False
                continue

            tried.append(name)
            logger.info("路由到模型：%s（已尝试：%s）", name, tried)

            result = await adapter.chat(messages, **kwargs)
            self._latencies[name].append(result.elapsed)

            if result.success:
                # 恢复健康状态
                self._health[name] = True
                result.metadata["routed_to"] = name
                result.metadata["tried_models"] = tried
                return result

            # 标记为不健康
            self._health[name] = False
            logger.warning("模型 %s 调用失败，尝试故障转移", name)

            if len(tried) >= len(self._adapters):
                return IntegrationResult.fail(
                    f"所有模型均调用失败，已尝试：{tried}",
                    elapsed=time.time() - start_time,
                    tried_models=tried,
                )

    def get_routing_stats(self) -> Dict[str, Any]:
        """获取路由统计。"""
        stats: Dict[str, Any] = {}
        for name, adapter in self._adapters.items():
            latencies = self._latencies.get(name, deque())
            stats[name] = {
                **adapter.get_stats(),
                "weight": self._weights.get(name, 0),
                "cost_per_1k": self._costs.get(name, 0),
                "healthy": self._health.get(name, True),
                "avg_latency": sum(latencies) / len(latencies) if latencies else 0,
            }
        return stats


# =============================================================================
# 第三部分：外部检索源接入
# =============================================================================
# 本部分演示如何将外部学术检索源接入 ThesisMiner 的 Searcher Agent。
#
# ThesisMiner 默认支持 Semantic Scholar API，但研究者常需要检索
# PubMed（医学）、arXiv（计算机/物理/数学）、Google Scholar（综合）等。
# 通过实现统一的 SearchSource 接口，可无缝接入新的检索源。
# =============================================================================


@dataclass
class SearchSourceConfig(IntegrationConfig):
    """检索源配置。"""

    api_base: str = ""
    api_key: str = ""
    max_results: int = 20
    rate_limit_per_sec: float = 3.0  # 每秒最大请求数
    timeout: float = 15.0

    def validate(self) -> List[str]:
        errors = super().validate()
        if not self.api_base:
            errors.append("API 基础 URL 不能为空")
        if self.max_results <= 0 or self.max_results > 100:
            errors.append(f"max_results 应在 1-100 之间，当前值：{self.max_results}")
        if self.rate_limit_per_sec <= 0:
            errors.append(f"rate_limit_per_sec 必须大于 0，当前值：{self.rate_limit_per_sec}")
        return errors


@dataclass
class SearchResult:
    """
    检索结果。

    统一封装不同检索源的返回数据。

    Attributes:
        title: 标题
        authors: 作者列表
        abstract: 摘要
        year: 发表年份
        venue: 发表场所（期刊/会议）
        doi: DOI
        url: 原文链接
        citations: 引用数
        keywords: 关键词列表
        source: 检索源名称
        raw: 原始数据
    """

    title: str
    authors: List[str] = field(default_factory=list)
    abstract: str = ""
    year: Optional[int] = None
    venue: str = ""
    doi: str = ""
    url: str = ""
    citations: int = 0
    keywords: List[str] = field(default_factory=list)
    source: str = ""
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return {
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract,
            "year": self.year,
            "venue": self.venue,
            "doi": self.doi,
            "url": self.url,
            "citations": self.citations,
            "keywords": self.keywords,
            "source": self.source,
        }

    def brief(self, max_length: int = 100) -> str:
        """返回简要信息。"""
        authors_str = ", ".join(self.authors[:3])
        if len(self.authors) > 3:
            authors_str += " et al."
        year_str = f" ({self.year})" if self.year else ""
        abstract_brief = self.abstract[:max_length]
        if len(self.abstract) > max_length:
            abstract_brief += "..."
        return f"{self.title}{year_str} - {authors_str}\n{abstract_brief}"


class BaseSearchSource(ABC):
    """
    检索源抽象基类。

    所有外部检索源均需继承此类并实现 ``search`` 方法。
    检索源负责将统一查询转换为目标 API 的请求格式，
    并将响应转换回 SearchResult 列表。

    设计模式：策略模式（Strategy Pattern）

    内置速率限制器，防止触发 API 限流。
    """

    def __init__(self, config: SearchSourceConfig) -> None:
        self.config = config
        errors = config.validate()
        if errors:
            raise ValueError(f"检索源配置校验失败：{'; '.join(errors)}")
        self._request_times: deque = deque(maxlen=100)
        self._total_searches = 0
        self._total_results = 0
        logger.debug("初始化检索源：%s（API：%s）", config.name, config.api_base)

    @abstractmethod
    async def search(
        self, query: str, **kwargs: Any
    ) -> IntegrationResult:
        """
        执行检索。

        Args:
            query: 检索关键词
            **kwargs: 额外参数（max_results, year_from, year_to 等）

        Returns:
            IntegrationResult，data 为 List[SearchResult]
        """
        ...

    async def _enforce_rate_limit(self) -> None:
        """
        执行速率限制。

        使用滑动窗口算法确保请求频率不超过配置上限。
        """
        min_interval = 1.0 / self.config.rate_limit_per_sec
        now = time.time()

        # 清理过期记录
        while self._request_times and now - self._request_times[0] > 1.0:
            self._request_times.popleft()

        # 如果 1 秒内请求数已达上限，等待
        if len(self._request_times) >= self.config.rate_limit_per_sec:
            sleep_time = 1.0 - (now - self._request_times[0])
            if sleep_time > 0:
                logger.debug("速率限制：等待 %.2f 秒", sleep_time)
                await asyncio.sleep(sleep_time)

        # 确保两次请求间隔不小于 min_interval
        if self._request_times:
            elapsed = time.time() - self._request_times[-1]
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)

        self._request_times.append(time.time())

    def get_stats(self) -> Dict[str, Any]:
        """获取检索统计。"""
        avg_results = self._total_results / max(self._total_searches, 1)
        return {
            "name": self.config.name,
            "total_searches": self._total_searches,
            "total_results": self._total_results,
            "avg_results_per_search": round(avg_results, 2),
        }

    def _record_search(self, result_count: int) -> None:
        """记录检索统计。"""
        self._total_searches += 1
        self._total_results += result_count


# -----------------------------------------------------------------------------
# 示例 3.1：PubMed 检索源
# -----------------------------------------------------------------------------
# PubMed 是美国国家医学图书馆的生物医学文献数据库，收录 3500 万篇文献。
# 使用 E-utilities API（esearch + efetch）进行检索。
# -----------------------------------------------------------------------------


class PubMedSearchSource(BaseSearchSource):
    """
    PubMed 检索源。

    PubMed API 特点：
        - 使用 E-utilities API（NCBI 提供）
        - 两步检索：esearch 获取 PMID 列表 → efetch 获取详细信息
        - 支持 MeSH 术语检索
        - 返回 XML 格式（efetch）或 JSON 格式（esearch）
        - 无需 API Key，但有速率限制（无 key 3 req/s，有 key 10 req/s）

    配置示例::

        config = SearchSourceConfig(
            name="pubmed",
            api_base="https://eutils.ncbi.nlm.nih.gov/entrez/eutils",
            max_results=20,
            rate_limit_per_sec=3.0,
        )
    """

    def __init__(self, config: SearchSourceConfig) -> None:
        super().__init__(config)
        self._api_key = config.api_key  # 可选

    def _build_esearch_url(self, query: str, max_results: int) -> str:
        """
        构造 esearch 请求 URL。

        esearch 用于检索 PMID 列表。

        Args:
            query: 检索关键词
            max_results: 最大结果数

        Returns:
            完整的 esearch URL
        """
        params: Dict[str, str] = {
            "db": "pubmed",
            "term": query,
            "retmax": str(max_results),
            "retmode": "json",
            "sort": "relevance",
        }
        if self._api_key:
            params["api_key"] = self._api_key

        return f"{self.config.api_base}/esearch.fcgi?{urlencode(params)}"

    def _build_efetch_url(self, pmids: List[str]) -> str:
        """
        构造 efetch 请求 URL。

        efetch 用于根据 PMID 列表获取文献详细信息。

        Args:
            pmids: PMID 列表

        Returns:
            完整的 efetch URL
        """
        params: Dict[str, str] = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
            "rettype": "abstract",
        }
        if self._api_key:
            params["api_key"] = self._api_key

        return f"{self.config.api_base}/efetch.fcgi?{urlencode(params)}"

    def _parse_efetch_response(self, xml_text: str) -> List[SearchResult]:
        """
        解析 efetch XML 响应。

        PubMed efetch 返回 XML 格式，包含 PubmedArticle 节点。
        本方法使用正则表达式简化解析（生产环境应使用 xml.etree.ElementTree）。

        Args:
            xml_text: XML 响应文本

        Returns:
            SearchResult 列表
        """
        results: List[SearchResult] = []

        # 简化的 XML 解析（实际应使用 ElementTree）
        article_pattern = re.compile(
            r"<PubmedArticle>(.*?)</PubmedArticle>", re.DOTALL
        )
        title_pattern = re.compile(r"<ArticleTitle>(.*?)</ArticleTitle>", re.DOTALL)
        abstract_pattern = re.compile(r"<AbstractText>(.*?)</AbstractText>", re.DOTALL)
        year_pattern = re.compile(r"<PubDate>.*?<Year>(\d+)</Year>.*?</PubDate>", re.DOTALL)
        doi_pattern = re.compile(r"<ArticleId IdType=\"doi\">(.*?)</ArticleId>")
        author_pattern = re.compile(
            r"<Author>.*?<LastName>(.*?)</LastName>.*?<ForeName>(.*?)</ForeName>.*?</Author>",
            re.DOTALL,
        )

        for match in article_pattern.finditer(xml_text):
            article_xml = match.group(1)

            title_match = title_pattern.search(article_xml)
            title = title_match.group(1) if title_match else "无标题"

            abstract_matches = abstract_pattern.findall(article_xml)
            abstract = " ".join(abstract_matches) if abstract_matches else ""

            year_match = year_pattern.search(article_xml)
            year = int(year_match.group(1)) if year_match else None

            doi_match = doi_pattern.search(article_xml)
            doi = doi_match.group(1) if doi_match else ""

            authors: List[str] = []
            for author_match in author_pattern.finditer(article_xml):
                last_name = author_match.group(1)
                fore_name = author_match.group(2)
                authors.append(f"{fore_name} {last_name}")

            results.append(
                SearchResult(
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    year=year,
                    doi=doi,
                    url=f"https://pubmed.ncbi.nlm.nih.gov/?term={doi}" if doi else "",
                    source="pubmed",
                )
            )

        return results

    async def search(
        self, query: str, **kwargs: Any
    ) -> IntegrationResult:
        """
        执行 PubMed 检索。

        检索流程：
            1. 调用 esearch 获取 PMID 列表
            2. 调用 efetch 获取文献详细信息
            3. 解析 XML 响应并转换为 SearchResult

        Args:
            query: 检索关键词（支持 MeSH 术语，如 "diabetes[MeSH]"）
            **kwargs: 额外参数
                - max_results: 最大结果数（覆盖配置）
                - year_from: 起始年份
                - year_to: 结束年份

        Returns:
            IntegrationResult
        """
        await self._enforce_rate_limit()
        start_time = time.time()
        max_results = kwargs.get("max_results", self.config.max_results)

        # 构造查询（添加年份过滤）
        full_query = query
        year_from = kwargs.get("year_from")
        year_to = kwargs.get("year_to")
        if year_from and year_to:
            full_query = f"({query}) AND (\"{year_from}\"[PDAT] : \"{year_to}\"[PDAT])"
        elif year_from:
            full_query = f"({query}) AND (\"{year_from}\"[PDAT] : \"3000\"[PDAT])"

        try:
            # 步骤 1：esearch 获取 PMID
            esearch_url = self._build_esearch_url(full_query, max_results)
            logger.debug("PubMed esearch URL: %s", esearch_url)

            # 模拟 PMID 列表
            pmids = [str(10000000 + i) for i in range(min(max_results, 5))]

            if not pmids:
                self._record_search(0)
                return IntegrationResult.ok(
                    [], elapsed=time.time() - start_time, query=full_query
                )

            # 步骤 2：efetch 获取详细信息
            await self._enforce_rate_limit()
            efetch_url = self._build_efetch_url(pmids)
            logger.debug("PubMed efetch URL: %s", efetch_url)

            # 模拟 XML 响应
            mock_xml = self._generate_mock_xml(pmids, query)
            results = self._parse_efetch_response(mock_xml)

            self._record_search(len(results))
            return IntegrationResult.ok(
                results,
                elapsed=time.time() - start_time,
                query=full_query,
                pmids=pmids,
            )

        except Exception as exc:
            logger.error("PubMed 检索失败：%s", exc)
            return IntegrationResult.fail(
                str(exc), elapsed=time.time() - start_time, query=full_query
            )

    def _generate_mock_xml(self, pmids: List[str], query: str) -> str:
        """生成模拟 XML 响应（仅用于示例）。"""
        articles = []
        for i, pmid in enumerate(pmids):
            articles.append(f"""
            <PubmedArticle>
                <MedlineCitation>
                    <PMID>{pmid}</PMID>
                    <Article>
                        <ArticleTitle>关于 {query} 的研究 #{i + 1}</ArticleTitle>
                        <Abstract>
                            <AbstractText>本研究探讨了 {query} 的相关问题，
                            通过实验方法验证了假设，结果表明该领域仍有大量研究空间。</AbstractText>
                        </Abstract>
                        <AuthorList>
                            <Author>
                                <LastName>Wang</LastName>
                                <ForeName>Wei</ForeName>
                            </Author>
                            <Author>
                                <LastName>Li</LastName>
                                <ForeName>Ming</ForeName>
                            </Author>
                        </AuthorList>
                        <Journal>
                            <JournalInfo>
                                <PubDate>
                                    <Year>2024</Year>
                                </PubDate>
                            </JournalInfo>
                        </Journal>
                        <ELocationID EIdType="doi">10.1234/example.{pmid}</ELocationID>
                    </Article>
                </MedlineCitation>
            </PubmedArticle>""")
        return f"<PubmedArticleSet>{''.join(articles)}</PubmedArticleSet>"


# -----------------------------------------------------------------------------
# 示例 3.2：arXiv 检索源
# -----------------------------------------------------------------------------
# arXiv 是计算机科学、物理学、数学领域的预印本平台。
# 使用 Atom XML API 进行检索。
# -----------------------------------------------------------------------------


class ArxivSearchSource(BaseSearchSource):
    """
    arXiv 检索源。

    arXiv API 特点：
        - 使用 Atom 1.0 XML 格式
        - 单步检索（无需两步）
        - 支持字段前缀：ti（标题）、au（作者）、abs（摘要）、cat（分类）
        - 无需 API Key
        - 速率限制：1 请求/3 秒（建议间隔 3 秒）

    配置示例::

        config = SearchSourceConfig(
            name="arxiv",
            api_base="http://export.arxiv.org/api/query",
            max_results=20,
            rate_limit_per_sec=0.33,  # 约 1 请求/3 秒
        )
    """

    # arXiv 分类映射
    CATEGORY_MAP: Dict[str, str] = {
        "cs.AI": "人工智能",
        "cs.CL": "计算语言学",
        "cs.CV": "计算机视觉",
        "cs.LG": "机器学习",
        "cs.NE": "神经网络",
        "cs.SE": "软件工程",
        "math.ST": "统计学理论",
        "physics.data-an": "数据分析",
        "q-bio.QM": "定量方法",
    }

    def _build_query(self, keywords: str, **kwargs: Any) -> str:
        """
        构造 arXiv 查询字符串。

        arXiv 支持字段前缀检索：
            - ti: 标题
            - au: 作者
            - abs: 摘要
            - cat: 分类

        Args:
            keywords: 关键词
            **kwargs: 额外参数
                - category: 分类过滤（如 "cs.AI"）
                - author: 作者过滤

        Returns:
            arXiv 查询字符串
        """
        parts: List[str] = []
        parts.append(f"all:{quote_plus(keywords)}")

        category = kwargs.get("category")
        if category:
            parts.append(f"cat:{category}")

        author = kwargs.get("author")
        if author:
            parts.append(f"au:{quote_plus(author)}")

        return "+AND+".join(parts)

    def _build_url(self, query: str, max_results: int, start: int = 0) -> str:
        """构造完整请求 URL。"""
        params = {
            "search_query": query,
            "start": str(start),
            "max_results": str(max_results),
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        return f"{self.config.api_base}?{urlencode(params)}"

    def _parse_atom_response(self, xml_text: str) -> List[SearchResult]:
        """
        解析 arXiv Atom XML 响应。

        arXiv 使用 Atom 1.0 格式，每个 entry 包含：
            - title: 标题
            - summary: 摘要
            - author/name: 作者
            - published: 发布日期
            - arxiv:doi: DOI

        Args:
            xml_text: Atom XML 文本

        Returns:
            SearchResult 列表
        """
        results: List[SearchResult] = []

        entry_pattern = re.compile(r"<entry>(.*?)</entry>", re.DOTALL)
        title_pattern = re.compile(r"<title>(.*?)</title>", re.DOTALL)
        summary_pattern = re.compile(r"<summary>(.*?)</summary>", re.DOTALL)
        published_pattern = re.compile(r"<published>(\d{4})-\d{2}-\d{2}")
        doi_pattern = re.compile(r"<arxiv:doi[^>]*>(.*?)</arxiv:doi>")
        author_pattern = re.compile(r"<name>(.*?)</name>")
        link_pattern = re.compile(r'<id>(http://arxiv\.org/abs/.*?)</id>')
        category_pattern = re.compile(r'<arxiv:primary_category[^>]*term="([^"]+)"')

        for match in entry_pattern.finditer(xml_text):
            entry_xml = match.group(1)

            title_match = title_pattern.search(entry_xml)
            title = title_match.group(1).strip() if title_match else "无标题"

            summary_match = summary_pattern.search(entry_xml)
            abstract = summary_match.group(1).strip() if summary_match else ""

            published_match = published_pattern.search(entry_xml)
            year = int(published_match.group(1)) if published_match else None

            doi_match = doi_pattern.search(entry_xml)
            doi = doi_match.group(1) if doi_match else ""

            authors = author_pattern.findall(entry_xml)

            link_match = link_pattern.search(entry_xml)
            url = link_match.group(1) if link_match else ""

            category_match = category_pattern.search(entry_xml)
            keywords = []
            if category_match:
                cat = category_match.group(1)
                keywords.append(self.CATEGORY_MAP.get(cat, cat))

            results.append(
                SearchResult(
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    year=year,
                    venue="arXiv",
                    doi=doi,
                    url=url,
                    keywords=keywords,
                    source="arxiv",
                )
            )

        return results

    async def search(
        self, query: str, **kwargs: Any
    ) -> IntegrationResult:
        """
        执行 arXiv 检索。

        Args:
            query: 检索关键词
            **kwargs: 额外参数
                - category: 分类过滤（如 "cs.AI"）
                - author: 作者过滤
                - max_results: 最大结果数

        Returns:
            IntegrationResult
        """
        await self._enforce_rate_limit()
        start_time = time.time()
        max_results = kwargs.get("max_results", self.config.max_results)

        try:
            arxiv_query = self._build_query(query, **kwargs)
            url = self._build_url(arxiv_query, max_results)
            logger.debug("arXiv 查询 URL: %s", url)

            # 模拟 Atom XML 响应
            mock_xml = self._generate_mock_atom(query, max_results)
            results = self._parse_atom_response(mock_xml)

            self._record_search(len(results))
            return IntegrationResult.ok(
                results,
                elapsed=time.time() - start_time,
                query=arxiv_query,
            )

        except Exception as exc:
            logger.error("arXiv 检索失败：%s", exc)
            return IntegrationResult.fail(
                str(exc), elapsed=time.time() - start_time, query=query
            )

    def _generate_mock_atom(self, query: str, count: int) -> str:
        """生成模拟 Atom XML（仅用于示例）。"""
        entries = []
        for i in range(min(count, 5)):
            entries.append(f"""
            <entry>
                <id>http://arxiv.org/abs/2401.{10000 + i}v1</id>
                <title>{query}: A Comprehensive Study #{i + 1}</title>
                <summary>This paper presents a comprehensive study on {query}.
                We propose a novel approach that significantly outperforms
                existing methods. Experimental results demonstrate the
                effectiveness of our approach.</summary>
                <published>2024-01-{15 + i:02d}T00:00:00Z</published>
                <author><name>Alice Chen</name></author>
                <author><name>Bob Zhang</name></author>
                <arxiv:primary_category term="cs.AI" />
                <arxiv:doi>10.48550/arXiv.2401.{10000 + i}</arxiv:doi>
            </entry>""")
        return f"""<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
            {''.join(entries)}
        </feed>"""


# -----------------------------------------------------------------------------
# 示例 3.3：Google Scholar 检索源（通过 SerpAPI）
# -----------------------------------------------------------------------------


class GoogleScholarSearchSource(BaseSearchSource):
    """
    Google Scholar 检索源（通过 SerpAPI）。

    Google Scholar 特点：
        - 无官方 API，需通过 SerpAPI 等第三方服务
        - 覆盖面广（含期刊、会议、预印本、学位论文等）
        - 引用数据较完整
        - SerpAPI 为付费服务，有免费额度

    配置示例::

        config = SearchSourceConfig(
            name="google_scholar",
            api_base="https://serpapi.com/search",
            api_key="your_serpapi_key",
            max_results=20,
            rate_limit_per_sec=1.0,
        )
    """

    def _build_url(self, query: str, max_results: int, **kwargs: Any) -> str:
        """构造 SerpAPI 请求 URL。"""
        params: Dict[str, str] = {
            "engine": "google_scholar",
            "q": query,
            "num": str(min(max_results, 20)),  # SerpAPI 最多 20 条
            "api_key": self.config.api_key,
        }

        year_from = kwargs.get("year_from")
        year_to = kwargs.get("year_to")
        if year_from:
            params["as_ylo"] = str(year_from)
        if year_to:
            params["as_yhi"] = str(year_to)

        lang = kwargs.get("lang", "zh-CN")
        params["hl"] = lang

        return f"{self.config.api_base}?{urlencode(params)}"

    def _parse_serpapi_response(self, data: Dict[str, Any]) -> List[SearchResult]:
        """
        解析 SerpAPI JSON 响应。

        SerpAPI 返回 organic_results 数组，每个结果包含：
            - title: 标题
            - publication_info: 出版信息（含作者、年份、期刊）
            - snippet: 摘要片段
            - inline_links: 引用链接（含引用数）
            - link: 原文链接

        Args:
            data: SerpAPI JSON 响应

        Returns:
            SearchResult 列表
        """
        results: List[SearchResult] = []
        organic = data.get("organic_results", [])

        for item in organic:
            title = item.get("title", "无标题")
            snippet = item.get("snippet", "")

            # 解析出版信息
            pub_info = item.get("publication_info", {})
            pub_summary = pub_info.get("summary", "")

            # 从 summary 提取作者和年份
            authors: List[str] = []
            year: Optional[int] = None
            venue = ""

            if pub_summary:
                # 尝试提取年份
                year_match = re.search(r"(\d{4})", pub_summary)
                if year_match:
                    year = int(year_match.group(1))

                # 尝试提取作者（逗号分隔的第一部分）
                parts = pub_summary.split(" - ")
                if parts:
                    author_part = parts[0]
                    authors = [a.strip() for a in author_part.split(",")]
                    if len(parts) > 1:
                        venue = parts[1].split(",")[0].strip()

            # 解析引用数
            citations = 0
            inline_links = item.get("inline_links", {})
            cited_by = inline_links.get("cited_by", {})
            if isinstance(cited_by, dict):
                citations = cited_by.get("total", 0)

            link = item.get("link", "")
            resource = item.get("resource", {})
            doi = resource.get("doi", "") if isinstance(resource, dict) else ""

            results.append(
                SearchResult(
                    title=title,
                    authors=authors,
                    abstract=snippet,
                    year=year,
                    venue=venue,
                    doi=doi,
                    url=link,
                    citations=citations,
                    source="google_scholar",
                )
            )

        return results

    async def search(
        self, query: str, **kwargs: Any
    ) -> IntegrationResult:
        """
        执行 Google Scholar 检索。

        Args:
            query: 检索关键词
            **kwargs: 额外参数
                - max_results: 最大结果数
                - year_from: 起始年份
                - year_to: 结束年份
                - lang: 语言（默认 zh-CN）

        Returns:
            IntegrationResult
        """
        await self._enforce_rate_limit()
        start_time = time.time()
        max_results = kwargs.get("max_results", self.config.max_results)

        try:
            url = self._build_url(query, max_results, **kwargs)
            logger.debug("Google Scholar URL: %s", url)

            # 模拟响应
            mock_data = {
                "organic_results": [
                    {
                        "title": f"{query}：综述与展望 #{i + 1}",
                        "publication_info": {
                            "summary": f"张三, 李四 - 期刊{i + 1}, 2024"
                        },
                        "snippet": f"本文对 {query} 进行了全面综述，分析了当前研究现状...",
                        "link": f"https://example.com/paper{i + 1}",
                        "inline_links": {
                            "cited_by": {"total": 50 - i * 5}
                        },
                    }
                    for i in range(min(max_results, 5))
                ]
            }

            results = self._parse_serpapi_response(mock_data)
            self._record_search(len(results))

            return IntegrationResult.ok(
                results,
                elapsed=time.time() - start_time,
                query=query,
            )

        except Exception as exc:
            logger.error("Google Scholar 检索失败：%s", exc)
            return IntegrationResult.fail(
                str(exc), elapsed=time.time() - start_time, query=query
            )


# -----------------------------------------------------------------------------
# 示例 3.4：多源聚合检索器
# -----------------------------------------------------------------------------


class MultiSourceSearcher:
    """
    多源聚合检索器。

    同时查询多个检索源，合并去重后返回结果。

    功能：
        - 并行查询多个检索源
        - 结果去重（基于标题相似度）
        - 按引用数/相关度排序
        - 支持源权重配置

    用法示例::

        searcher = MultiSourceSearcher()
        searcher.add_source("pubmed", pubmed_source, weight=1.0)
        searcher.add_source("arxiv", arxiv_source, weight=1.2)
        searcher.add_source("scholar", scholar_source, weight=1.0)

        result = await searcher.search("深度学习 医学影像", max_results=30)
    """

    def __init__(self) -> None:
        self._sources: Dict[str, Tuple[BaseSearchSource, float]] = {}

    def add_source(self, name: str, source: BaseSearchSource, weight: float = 1.0) -> None:
        """添加检索源。"""
        self._sources[name] = (source, weight)
        logger.info("聚合检索器添加源：%s（权重：%.2f）", name, weight)

    async def search(
        self, query: str, max_results: int = 30, **kwargs: Any
    ) -> IntegrationResult:
        """
        并行查询所有检索源，合并结果。

        Args:
            query: 检索关键词
            max_results: 合并后最大结果数
            **kwargs: 传递给各检索源的额外参数

        Returns:
            IntegrationResult
        """
        start_time = time.time()

        # 并行查询所有源
        tasks = []
        source_names = []
        for name, (source, _) in self._sources.items():
            per_source_max = max_results // len(self._sources) + 5
            tasks.append(source.search(query, max_results=per_source_max, **kwargs))
            source_names.append(name)

        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        # 合并结果
        all_results: List[SearchResult] = []
        source_stats: Dict[str, Any] = {}

        for name, result in zip(source_names, results_list):
            if isinstance(result, Exception):
                source_stats[name] = {"success": False, "error": str(result)}
                logger.warning("检索源 %s 异常：%s", name, result)
                continue

            if result.success:
                all_results.extend(result.data)
                source_stats[name] = {
                    "success": True,
                    "count": len(result.data),
                    "elapsed": result.elapsed,
                }
            else:
                source_stats[name] = {"success": False, "error": result.error}

        # 去重（基于标题相似度）
        unique_results = self._deduplicate(all_results)

        # 排序：引用数降序 + 年份降序
        unique_results.sort(
            key=lambda r: (r.citations, r.year or 0),
            reverse=True,
        )

        # 截断到 max_results
        final_results = unique_results[:max_results]

        elapsed = time.time() - start_time
        return IntegrationResult.ok(
            final_results,
            elapsed=elapsed,
            query=query,
            source_stats=source_stats,
            total_before_dedup=len(all_results),
            total_after_dedup=len(unique_results),
            total_returned=len(final_results),
        )

    def _deduplicate(self, results: List[SearchResult]) -> List[SearchResult]:
        """
        基于标题相似度去重。

        使用简单的 Jaccard 相似度（基于词集）判断重复。
        阈值 0.8 以上视为重复。

        Args:
            results: 待去重的结果列表

        Returns:
            去重后的结果列表
        """
        if not results:
            return []

        unique: List[SearchResult] = []
        seen_title_sets: List[set] = []

        for result in results:
            title_words = set(result.title.lower().split())
            is_dup = False

            for seen_set in seen_title_sets:
                # Jaccard 相似度
                intersection = len(title_words & seen_set)
                union = len(title_words | seen_set)
                similarity = intersection / union if union > 0 else 0

                if similarity > 0.8:
                    is_dup = True
                    break

            if not is_dup:
                unique.append(result)
                seen_title_sets.append(title_words)

        removed = len(results) - len(unique)
        if removed > 0:
            logger.info("去重：移除 %d 条重复结果", removed)

        return unique


# =============================================================================
# 第四部分：Webhook 集成
# =============================================================================
# 本部分演示如何通过 Webhook 将 ThesisMiner 的事件通知到外部系统。
#
# 支持的通知渠道：
#   - Slack：通过 Incoming Webhook
#   - 钉钉（DingTalk）：通过自定义机器人
#   - 企业微信（WeChat Work）：通过群机器人
#   - 通用 Webhook：自定义 HTTP 端点
# =============================================================================


@dataclass
class WebhookConfig(IntegrationConfig):
    """Webhook 配置。"""

    webhook_url: str = ""
    secret: str = ""  # 钉钉/企业微信的加签密钥
    channel: str = "generic"  # slack | dingtalk | wechat_work | generic

    def validate(self) -> List[str]:
        errors = super().validate()
        if not self.webhook_url:
            errors.append("Webhook URL 不能为空")
        if self.channel not in ("slack", "dingtalk", "wechat_work", "generic"):
            errors.append(f"不支持的渠道：{self.channel}")
        return errors


@dataclass
class WebhookEvent:
    """
    Webhook 事件。

    Attributes:
        event_type: 事件类型
        title: 通知标题
        message: 通知内容
        timestamp: 事件时间戳
        severity: 严重级别（info/warning/error/critical）
        metadata: 额外元数据
    """

    event_type: str
    title: str
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    severity: str = "info"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_slack_payload(self) -> Dict[str, Any]:
        """转换为 Slack 消息格式。"""
        color_map = {
            "info": "#36a64f",      # 绿色
            "warning": "#ff9900",   # 橙色
            "error": "#ff0000",     # 红色
            "critical": "#b22222",  # 深红
        }
        color = color_map.get(self.severity, "#36a64f")

        fields = []
        for key, value in self.metadata.items():
            fields.append({
                "title": key,
                "value": str(value),
                "short": len(str(value)) < 30,
            })

        return {
            "attachments": [
                {
                    "color": color,
                    "title": self.title,
                    "text": self.message,
                    "fields": fields,
                    "footer": "ThesisMiner",
                    "ts": int(self.timestamp.timestamp()),
                }
            ]
        }

    def to_dingtalk_payload(self, secret: str = "") -> Tuple[Dict[str, Any], Optional[Dict[str, str]]]:
        """
        转换为钉钉消息格式。

        钉钉机器人支持加签验证，需在 URL 上附加签名参数。

        Args:
            secret: 加签密钥

        Returns:
            (请求体, URL 参数) 元组
        """
        is_at_all = self.severity in ("error", "critical")

        payload: Dict[str, Any] = {
            "msgtype": "markdown",
            "markdown": {
                "title": self.title,
                "text": f"### {self.title}\n\n"
                        f"**级别**：{self.severity.upper()}\n\n"
                        f"**时间**：{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                        f"**内容**：{self.message}\n\n"
                        + "\n\n".join(
                            f"- **{k}**：{v}" for k, v in self.metadata.items()
                        ),
            },
            "at": {
                "isAtAll": is_at_all,
            },
        }

        url_params: Optional[Dict[str, str]] = None
        if secret:
            timestamp = str(round(time.time() * 1000))
            string_to_sign = f"{timestamp}\n{secret}"
            hmac_code = hmac.new(
                secret.encode("utf-8"),
                string_to_sign.encode("utf-8"),
                hashlib.sha256,
            ).digest()
            sign = quote_plus(base64.b64encode(hmac_code))
            url_params = {"timestamp": timestamp, "sign": sign}

        return payload, url_params

    def to_wechat_work_payload(self) -> Dict[str, Any]:
        """转换为企业微信消息格式。"""
        mentioned_list = "@all" if self.severity in ("error", "critical") else ""

        return {
            "msgtype": "markdown",
            "markdown": {
                "content": f"## {self.title}\n"
                           f"> **级别**：{self.severity.upper()}\n"
                           f"> **时间**：{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                           f"> **内容**：{self.message}\n"
                           + "".join(f"> **{k}**：{v}\n" for k, v in self.metadata.items()),
                "mentioned_list": mentioned_list,
            }
        }


class BaseWebhookNotifier(ABC):
    """Webhook 通知器抽象基类。"""

    def __init__(self, config: WebhookConfig) -> None:
        self.config = config
        errors = config.validate()
        if errors:
            raise ValueError(f"Webhook 配置校验失败：{'; '.join(errors)}")
        self._sent_count = 0
        self._error_count = 0
        logger.debug("初始化 Webhook 通知器：%s（渠道：%s）", config.name, config.channel)

    @abstractmethod
    async def send(self, event: WebhookEvent) -> IntegrationResult:
        """发送通知。"""
        ...

    def _build_headers(self) -> Dict[str, str]:
        """构建请求头。"""
        return {
            "Content-Type": "application/json",
            "User-Agent": "ThesisMiner/8.0",
        }

    def get_stats(self) -> Dict[str, Any]:
        """获取统计。"""
        return {
            "name": self.config.name,
            "channel": self.config.channel,
            "sent": self._sent_count,
            "errors": self._error_count,
            "success_rate": (
                (self._sent_count - self._error_count) / max(self._sent_count, 1)
            ),
        }


class SlackWebhookNotifier(BaseWebhookNotifier):
    """Slack Webhook 通知器。"""

    def __init__(self, config: WebhookConfig) -> None:
        config.channel = "slack"
        super().__init__(config)

    async def send(self, event: WebhookEvent) -> IntegrationResult:
        """发送 Slack 通知。"""
        start_time = time.time()
        payload = event.to_slack_payload()

        try:
            # 实际 HTTP 调用（示例中省略）
            # async with httpx.AsyncClient() as client:
            #     resp = await client.post(
            #         self.config.webhook_url,
            #         json=payload,
            #         headers=self._build_headers(),
            #         timeout=self.config.timeout,
            #     )
            #     if resp.status_code != 200:
            #         raise RuntimeError(f"Slack 返回 {resp.status_code}")

            logger.info("Slack 通知已发送：%s", event.title)
            self._sent_count += 1
            return IntegrationResult.ok(
                {"status": "sent", "channel": "slack"},
                elapsed=time.time() - start_time,
            )
        except Exception as exc:
            self._sent_count += 1
            self._error_count += 1
            logger.error("Slack 通知发送失败：%s", exc)
            return IntegrationResult.fail(
                str(exc), elapsed=time.time() - start_time
            )


class DingTalkWebhookNotifier(BaseWebhookNotifier):
    """钉钉 Webhook 通知器。"""

    def __init__(self, config: WebhookConfig) -> None:
        config.channel = "dingtalk"
        super().__init__(config)

    async def send(self, event: WebhookEvent) -> IntegrationResult:
        """发送钉钉通知。"""
        start_time = time.time()
        payload, url_params = event.to_dingtalk_payload(self.config.secret)

        try:
            url = self.config.webhook_url
            if url_params:
                query_string = urlencode(url_params)
                url = f"{url}&{query_string}"

            # 实际 HTTP 调用（示例中省略）
            # async with httpx.AsyncClient() as client:
            #     resp = await client.post(url, json=payload, headers=self._build_headers(), timeout=self.config.timeout)
            #     data = resp.json()
            #     if data.get("errcode") != 0:
            #         raise RuntimeError(f"钉钉返回错误：{data.get('errmsg')}")

            logger.info("钉钉通知已发送：%s", event.title)
            self._sent_count += 1
            return IntegrationResult.ok(
                {"status": "sent", "channel": "dingtalk"},
                elapsed=time.time() - start_time,
            )
        except Exception as exc:
            self._sent_count += 1
            self._error_count += 1
            logger.error("钉钉通知发送失败：%s", exc)
            return IntegrationResult.fail(
                str(exc), elapsed=time.time() - start_time
            )


class WeChatWorkWebhookNotifier(BaseWebhookNotifier):
    """企业微信 Webhook 通知器。"""

    def __init__(self, config: WebhookConfig) -> None:
        config.channel = "wechat_work"
        super().__init__(config)

    async def send(self, event: WebhookEvent) -> IntegrationResult:
        """发送企业微信通知。"""
        start_time = time.time()
        payload = event.to_wechat_work_payload()

        try:
            # 实际 HTTP 调用（示例中省略）
            # async with httpx.AsyncClient() as client:
            #     resp = await client.post(
            #         self.config.webhook_url,
            #         json=payload,
            #         headers=self._build_headers(),
            #         timeout=self.config.timeout,
            #     )
            #     data = resp.json()
            #     if data.get("errcode") != 0:
            #         raise RuntimeError(f"企业微信返回错误：{data.get('errmsg')}")

            logger.info("企业微信通知已发送：%s", event.title)
            self._sent_count += 1
            return IntegrationResult.ok(
                {"status": "sent", "channel": "wechat_work"},
                elapsed=time.time() - start_time,
            )
        except Exception as exc:
            self._sent_count += 1
            self._error_count += 1
            logger.error("企业微信通知发送失败：%s", exc)
            return IntegrationResult.fail(
                str(exc), elapsed=time.time() - start_time
            )


class WebhookManager:
    """
    Webhook 管理器。

    管理多个 Webhook 通知器，支持：
        - 多渠道并行通知
        - 事件过滤（按类型/严重级别）
        - 失败重试
        - 通知历史记录

    用法示例::

        manager = WebhookManager()
        manager.add_notifier("slack", slack_notifier)
        manager.add_notifier("dingtalk", dingtalk_notifier)

        event = WebhookEvent(
            event_type="proposal.generated",
            title="论题生成完成",
            message="论题「基于深度学习的医学影像分析」已生成",
            severity="info",
            metadata={"session_id": "xxx", "cost": "$0.05"},
        )
        await manager.notify_all(event)
    """

    def __init__(self) -> None:
        self._notifiers: Dict[str, BaseWebhookNotifier] = {}
        self._event_filters: Dict[str, set] = {}  # name -> {event_types}
        self._history: deque = deque(maxlen=1000)

    def add_notifier(
        self,
        name: str,
        notifier: BaseWebhookNotifier,
        event_types: Optional[set] = None,
    ) -> None:
        """
        添加通知器。

        Args:
            name: 通知器名称
            notifier: 通知器实例
            event_types: 订阅的事件类型集合（None 表示订阅所有）
        """
        self._notifiers[name] = notifier
        self._event_filters[name] = event_types or set()
        logger.info("Webhook 管理器添加通知器：%s", name)

    async def notify_all(self, event: WebhookEvent) -> Dict[str, IntegrationResult]:
        """
        向所有匹配的通知器发送通知。

        Args:
            event: Webhook 事件

        Returns:
            各通知器的发送结果
        """
        results: Dict[str, IntegrationResult] = {}
        self._history.append({
            "event": event,
            "timestamp": datetime.now(timezone.utc),
        })

        tasks = []
        names = []

        for name, notifier in self._notifiers.items():
            # 事件类型过滤
            filters = self._event_filters.get(name, set())
            if filters and event.event_type not in filters:
                logger.debug("通知器 %s 未订阅事件 %s，跳过", name, event.event_type)
                continue

            tasks.append(notifier.send(event))
            names.append(name)

        if not tasks:
            logger.warning("没有通知器订阅事件 %s", event.event_type)
            return results

        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        for name, result in zip(names, results_list):
            if isinstance(result, Exception):
                results[name] = IntegrationResult.fail(str(result))
            else:
                results[name] = result

        return results

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取通知历史。"""
        history = list(self._history)
        history.reverse()  # 最新的在前
        return [
            {
                "event_type": item["event"].event_type,
                "title": item["event"].title,
                "severity": item["event"].severity,
                "timestamp": item["timestamp"].isoformat(),
            }
            for item in history[:limit]
        ]


# =============================================================================
# 第五部分：CI/CD 集成
# =============================================================================
# 本部分提供 CI/CD 流水线相关的集成代码，包括：
#   - GitHub Actions 工作流生成
#   - 自动化测试运行器
#   - 部署流水线
#   - 版本发布管理
# =============================================================================


@dataclass
class CICDConfig(IntegrationConfig):
    """CI/CD 配置。"""

    repo_url: str = ""
    branch: str = "main"
    python_version: str = "3.11"
    node_version: str = "20"
    deploy_target: str = "docker"  # docker | bare_metal | k8s
    registry_url: str = ""
    image_name: str = "thesisminer"

    def validate(self) -> List[str]:
        errors = super().validate()
        if self.deploy_target not in ("docker", "bare_metal", "k8s"):
            errors.append(f"不支持的部署目标：{self.deploy_target}")
        return errors


class GitHubActionsGenerator:
    """
    GitHub Actions 工作流生成器。

    生成 ThesisMiner 的 CI/CD 工作流文件，包括：
        - 代码检查（linting）
        - 单元测试
        - 集成测试
        - Docker 镜像构建
        - 自动部署

    用法示例::

        generator = GitHubActionsGenerator(config)
        workflow = generator.generate_test_workflow()
        print(workflow)
    """

    def __init__(self, config: CICDConfig) -> None:
        self.config = config

    def generate_test_workflow(self) -> str:
        """生成测试工作流 YAML。"""
        return f"""# ThesisMiner CI 测试工作流
# 由 example_integrations.py 自动生成
name: CI Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

env:
  PYTHON_VERSION: "{self.config.python_version}"
  NODE_VERSION: "{self.config.node_version}"

jobs:
  # 代码检查
  lint:
    name: 代码检查
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: 设置 Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{{{ env.PYTHON_VERSION }}}}
      - name: 安装依赖
        run: |
          python -m pip install --upgrade pip
          pip install ruff black mypy
      - name: Ruff 检查
        run: ruff check src/ tests/
      - name: Black 格式检查
        run: black --check src/ tests/
      - name: Mypy 类型检查
        run: mypy src/

  # 单元测试
  unit-test:
    name: 单元测试
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - name: 设置 Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{{{ matrix.python-version }}}}
      - name: 安装依赖
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      - name: 运行单元测试
        run: |
          pytest tests/unit/ \\
            --cov=src \\
            --cov-report=xml \\
            --cov-fail-under=80 \\
            -v

  # 集成测试
  integration-test:
    name: 集成测试
    runs-on: ubuntu-latest
    needs: [lint, unit-test]
    steps:
      - uses: actions/checkout@v4
      - name: 设置 Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{{{ env.PYTHON_VERSION }}}}
      - name: 安装依赖
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      - name: 运行集成测试
        env:
          THESISMINER_ENV: test
        run: pytest tests/integration/ -v

  # 前端测试
  frontend-test:
    name: 前端测试
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: 设置 Node
        uses: actions/setup-node@v4
        with:
          node-version: ${{{{ env.NODE_VERSION }}}}
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - name: 安装依赖
        run: cd frontend && npm ci
      - name: 单元测试
        run: cd frontend && npm test -- --coverage
      - name: 构建检查
        run: cd frontend && npm run build
"""

    def generate_deploy_workflow(self) -> str:
        """生成部署工作流 YAML。"""
        registry = self.config.registry_url or "ghcr.io"
        image = self.config.image_name
        return f"""# ThesisMiner CD 部署工作流
name: Deploy

on:
  push:
    tags: ['v*']
  workflow_dispatch:
    inputs:
      environment:
        description: '部署环境'
        required: true
        default: 'staging'
        type: choice
        options:
          - staging
          - production

env:
  REGISTRY: {registry}
  IMAGE_NAME: {image}

jobs:
  build-image:
    name: 构建 Docker 镜像
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: 设置 Docker Buildx
        uses: docker/setup-buildx-action@v3
      - name: 登录镜像仓库
        uses: docker/login-action@v3
        with:
          registry: ${{{{ env.REGISTRY }}}}
          username: ${{{{ secrets.REGISTRY_USERNAME }}}}
          password: ${{{{ secrets.REGISTRY_PASSWORD }}}}
      - name: 构建并推送
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{{{ env.REGISTRY }}}}/${{{{ env.IMAGE_NAME }}}}:latest
          cache-from: type=registry,ref=${{{{ env.REGISTRY }}}}/${{{{ env.IMAGE_NAME }}}}:cache
          cache-to: type=registry,ref=${{{{ env.REGISTRY }}}}/${{{{ env.IMAGE_NAME }}}}:cache,mode=max

  deploy-staging:
    name: 部署到 Staging
    runs-on: ubuntu-latest
    needs: build-image
    if: github.event.inputs.environment == 'staging'
    environment:
      name: staging
      url: https://staging.thesisminer.example.com
    steps:
      - name: 部署
        run: echo "部署到 Staging"

  deploy-production:
    name: 部署到 Production
    runs-on: ubuntu-latest
    needs: build-image
    if: github.event.inputs.environment == 'production'
    environment:
      name: production
      url: https://thesisminer.example.com
    steps:
      - name: 部署
        run: echo "部署到 Production"
      - name: Slack 通知
        uses: rtCamp/action-slack-notify@v2
        env:
          SLACK_WEBHOOK: ${{{{ secrets.SLACK_WEBHOOK }}}}
          SLACK_TITLE: 'ThesisMiner 部署完成'
"""

    def generate_dockerfile(self) -> str:
        """
        生成多阶段 Dockerfile。

        采用多阶段构建：
            1. builder 阶段：安装依赖、构建前端
            2. runtime 阶段：精简运行时镜像
        """
        return """# ThesisMiner Dockerfile（多阶段构建）
# 阶段 1：前端构建
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 阶段 2：Python 依赖安装
FROM python:3.11-slim AS python-builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# 阶段 3：运行时镜像
FROM python:3.11-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \\
    curl sqlite3 nginx && \\
    rm -rf /var/lib/apt/lists/*
COPY --from=python-builder /root/.local /root/.local
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist
WORKDIR /app
COPY src/ ./src/
COPY config/ ./config/
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV THESISMINER_ENV=production
ENV THESISMINER_DB_PATH=/data/thesisminer.db
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \\
    CMD curl -f http://localhost:8000/health || exit 1
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "src.main:app", \\
     "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
"""


class TestRunner:
    """
    测试运行器。

    封装 pytest 调用，支持：
        - 分层测试（单元/集成/端到端）
        - 并行执行
        - 覆盖率收集
        - 测试报告生成

    用法示例::

        runner = TestRunner()
        result = runner.run_unit_tests()
        print(f"通过率：{result.pass_rate:.1%}")
    """

    def __init__(self, project_root: str = ".") -> None:
        self.project_root = project_root

    def run_unit_tests(
        self, parallel: bool = True, coverage: bool = True
    ) -> "TestResult":
        """运行单元测试。"""
        cmd = ["python", "-m", "pytest", "tests/unit/", "-v"]
        if parallel:
            cmd.extend(["-n", "auto"])
        if coverage:
            cmd.extend([
                "--cov=src",
                "--cov-report=term-missing",
                "--cov-report=json:coverage.json",
                "--cov-fail-under=80",
            ])
        return self._execute_tests(cmd, "单元测试")

    def run_integration_tests(self) -> "TestResult":
        """运行集成测试。"""
        cmd = ["python", "-m", "pytest", "tests/integration/", "-v"]
        return self._execute_tests(cmd, "集成测试")

    def run_e2e_tests(self) -> "TestResult":
        """运行端到端测试。"""
        cmd = ["python", "-m", "pytest", "tests/e2e/", "-v"]
        return self._execute_tests(cmd, "端到端测试")

    def run_lint(self) -> "TestResult":
        """运行代码检查。"""
        cmd = ["ruff", "check", "src/", "tests/"]
        return self._execute_tests(cmd, "代码检查")

    def _execute_tests(self, cmd: List[str], name: str) -> "TestResult":
        """执行测试命令并解析结果。"""
        start_time = time.time()
        logger.info("开始执行%s：%s", name, " ".join(cmd))

        try:
            # 实际执行（示例中模拟）
            # proc = subprocess.run(cmd, capture_output=True, text=True, cwd=self.project_root, timeout=600)
            # stdout, stderr, returncode = proc.stdout, proc.stderr, proc.returncode

            # 模拟结果
            stdout = "===== 50 passed, 0 failed in 12.5s ====="
            returncode = 0
            elapsed = time.time() - start_time

            passed = len(re.findall(r"passed", stdout))
            failed = len(re.findall(r"failed", stdout))
            errors = len(re.findall(r"error", stdout))

            result = TestResult(
                name=name, passed=passed, failed=failed, errors=errors,
                elapsed=elapsed, returncode=returncode, output=stdout,
            )

            if result.is_success:
                logger.info("%s通过：%s", name, result.summary)
            else:
                logger.warning("%s失败：%s", name, result.summary)
            return result

        except subprocess.TimeoutExpired:
            return TestResult(
                name=name, passed=0, failed=0, errors=1,
                elapsed=time.time() - start_time, returncode=-1, output="测试超时",
            )
        except Exception as exc:
            return TestResult(
                name=name, passed=0, failed=0, errors=1,
                elapsed=time.time() - start_time, returncode=-1, output=str(exc),
            )


@dataclass
class TestResult:
    """测试结果。"""

    name: str
    passed: int
    failed: int
    errors: int
    elapsed: float
    returncode: int
    output: str = ""

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.errors

    @property
    def is_success(self) -> bool:
        return self.failed == 0 and self.errors == 0 and self.returncode == 0

    @property
    def pass_rate(self) -> float:
        return self.passed / max(self.total, 1)

    @property
    def summary(self) -> str:
        return (
            f"通过 {self.passed}，失败 {self.failed}，"
            f"错误 {self.errors}，耗时 {self.elapsed:.1f}s"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name, "passed": self.passed, "failed": self.failed,
            "errors": self.errors, "total": self.total,
            "pass_rate": round(self.pass_rate, 4),
            "elapsed": round(self.elapsed, 2), "success": self.is_success,
        }


# =============================================================================
# 第六部分：监控集成
# =============================================================================
# 本部分提供 Prometheus 指标导出和 Grafana 面板配置。
#
# 监控指标分类：
#   - 请求指标：QPS、延迟、错误率
#   - Agent 指标：调用次数、执行时间、成功率
#   - 模型指标：token 用量、成本、缓存命中率
#   - 系统指标：CPU、内存、磁盘、连接数
# =============================================================================


class MetricsCollector:
    """
    Prometheus 指标收集器。

    收集 ThesisMiner 的运行指标并通过 Prometheus 格式导出。

    指标类型：
        - Counter：只增不减的计数器（如请求总数）
        - Gauge：可增可减的仪表（如当前连接数）
        - Histogram：直方图（如请求延迟分布）
        - Summary：摘要（如延迟分位数）

    用法示例::

        collector = MetricsCollector()
        collector.record_request(method="POST", endpoint="/api/chat", status=200, duration=0.5)
        collector.record_agent_call(agent="reasoner", success=True, duration=1.2)
        collector.record_model_usage(model="deepseek-r2", prompt_tokens=100, completion_tokens=50)
        print(collector.export_prometheus())
    """

    def __init__(self) -> None:
        # 请求指标
        self._request_count: Dict[str, int] = defaultdict(int)
        self._request_duration_sum: Dict[str, float] = defaultdict(float)
        self._request_duration_count: Dict[str, int] = defaultdict(int)
        self._request_errors: Dict[str, int] = defaultdict(int)

        # Agent 指标
        self._agent_calls: Dict[str, int] = defaultdict(int)
        self._agent_errors: Dict[str, int] = defaultdict(int)
        self._agent_duration_sum: Dict[str, float] = defaultdict(float)

        # 模型指标
        self._model_tokens: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"prompt": 0, "completion": 0, "total": 0}
        )
        self._model_cost: Dict[str, float] = defaultdict(float)
        self._cache_hits: Dict[str, int] = defaultdict(int)
        self._cache_misses: Dict[str, int] = defaultdict(int)

        # 系统指标
        self._active_sessions: int = 0
        self._active_conversations: int = 0
        self._db_connections: int = 0

        # 延迟直方图桶
        self._latency_buckets = [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        self._latency_histogram: Dict[str, List[int]] = defaultdict(
            lambda: [0] * len(self._latency_buckets)
        )

    def record_request(
        self, method: str, endpoint: str, status: int, duration: float,
    ) -> None:
        """记录 HTTP 请求。"""
        key = f'{method}:{endpoint}:{status}'
        self._request_count[key] += 1
        self._request_duration_sum[key] += duration
        self._request_duration_count[key] += 1

        if status >= 400:
            error_key = f'{method}:{endpoint}'
            self._request_errors[error_key] += 1

        # 更新延迟直方图
        hist_key = f'{method}:{endpoint}'
        for i, bucket in enumerate(self._latency_buckets):
            if duration <= bucket:
                self._latency_histogram[hist_key][i] += 1
                break

    def record_agent_call(
        self, agent: str, success: bool, duration: float,
    ) -> None:
        """记录 Agent 调用。"""
        self._agent_calls[agent] += 1
        self._agent_duration_sum[agent] += duration
        if not success:
            self._agent_errors[agent] += 1

    def record_model_usage(
        self, model: str, prompt_tokens: int, completion_tokens: int, cost: float = 0.0,
    ) -> None:
        """记录模型 token 使用量。"""
        self._model_tokens[model]["prompt"] += prompt_tokens
        self._model_tokens[model]["completion"] += completion_tokens
        self._model_tokens[model]["total"] += prompt_tokens + completion_tokens
        self._model_cost[model] += cost

    def record_cache(self, model: str, hit: bool) -> None:
        """记录缓存命中/未命中。"""
        if hit:
            self._cache_hits[model] += 1
        else:
            self._cache_misses[model] += 1

    def set_active_sessions(self, count: int) -> None:
        """设置当前活跃会话数。"""
        self._active_sessions = count

    def set_active_conversations(self, count: int) -> None:
        """设置当前活跃对话数。"""
        self._active_conversations = count

    def set_db_connections(self, count: int) -> None:
        """设置数据库连接数。"""
        self._db_connections = count

    def get_cache_hit_rate(self, model: str) -> float:
        """获取缓存命中率。"""
        hits = self._cache_hits.get(model, 0)
        misses = self._cache_misses.get(model, 0)
        total = hits + misses
        return hits / total if total > 0 else 0.0

    def export_prometheus(self) -> str:
        """
        导出 Prometheus 格式指标。

        输出格式遵循 Prometheus exposition format v0.0.4。

        Returns:
            Prometheus 格式文本
        """
        lines: List[str] = []

        # 请求指标
        lines.append("# HELP thesisminer_http_requests_total HTTP 请求总数")
        lines.append("# TYPE thesisminer_http_requests_total counter")
        for key, count in sorted(self._request_count.items()):
            method, endpoint, status = key.split(":")
            lines.append(
                f'thesisminer_http_requests_total{{method="{method}",'
                f'endpoint="{endpoint}",status="{status}"}} {count}'
            )

        lines.append("")
        lines.append("# HELP thesisminer_http_request_duration_seconds HTTP 请求延迟")
        lines.append("# TYPE thesisminer_http_request_duration_seconds histogram")
        for key, hist in sorted(self._latency_histogram.items()):
            method, endpoint = key.split(":")
            cumulative = 0
            for i, bucket in enumerate(self._latency_buckets):
                cumulative += hist[i]
                lines.append(
                    f'thesisminer_http_request_duration_seconds_bucket'
                    f'{{method="{method}",endpoint="{endpoint}",'
                    f'le="{bucket}"}} {cumulative}'
                )
            lines.append(
                f'thesisminer_http_request_duration_seconds_bucket'
                f'{{method="{method}",endpoint="{endpoint}",le="+Inf"}} '
                f'{self._request_duration_count.get(key, 0)}'
            )
            sum_val = self._request_duration_sum.get(key, 0)
            count_val = self._request_duration_count.get(key, 0)
            lines.append(
                f'thesisminer_http_request_duration_seconds_sum'
                f'{{method="{method}",endpoint="{endpoint}"}} {sum_val}'
            )
            lines.append(
                f'thesisminer_http_request_duration_seconds_count'
                f'{{method="{method}",endpoint="{endpoint}"}} {count_val}'
            )

        # Agent 指标
        lines.append("")
        lines.append("# HELP thesisminer_agent_calls_total Agent 调用总数")
        lines.append("# TYPE thesisminer_agent_calls_total counter")
        for agent, count in sorted(self._agent_calls.items()):
            lines.append(f'thesisminer_agent_calls_total{{agent="{agent}"}} {count}')

        lines.append("")
        lines.append("# HELP thesisminer_agent_errors_total Agent 错误总数")
        lines.append("# TYPE thesisminer_agent_errors_total counter")
        for agent, count in sorted(self._agent_errors.items()):
            lines.append(f'thesisminer_agent_errors_total{{agent="{agent}"}} {count}')

        lines.append("")
        lines.append("# HELP thesisminer_agent_duration_seconds Agent 执行耗时")
        lines.append("# TYPE thesisminer_agent_duration_seconds summary")
        for agent, duration in sorted(self._agent_duration_sum.items()):
            count = self._agent_calls.get(agent, 1)
            lines.append(
                f'thesisminer_agent_duration_seconds_sum{{agent="{agent}"}} {duration}'
            )
            lines.append(
                f'thesisminer_agent_duration_seconds_count{{agent="{agent}"}} {count}'
            )

        # 模型指标
        lines.append("")
        lines.append("# HELP thesisminer_model_tokens_total 模型 token 使用总量")
        lines.append("# TYPE thesisminer_model_tokens_total counter")
        for model, tokens in sorted(self._model_tokens.items()):
            lines.append(
                f'thesisminer_model_tokens_total{{model="{model}",'
                f'type="prompt"}} {tokens["prompt"]}'
            )
            lines.append(
                f'thesisminer_model_tokens_total{{model="{model}",'
                f'type="completion"}} {tokens["completion"]}'
            )

        lines.append("")
        lines.append("# HELP thesisminer_model_cost_dollars 模型成本（美元）")
        lines.append("# TYPE thesisminer_model_cost_dollars counter")
        for model, cost in sorted(self._model_cost.items()):
            lines.append(f'thesisminer_model_cost_dollars{{model="{model}"}} {cost}')

        lines.append("")
        lines.append("# HELP thesisminer_cache_hits_total 缓存命中总数")
        lines.append("# TYPE thesisminer_cache_hits_total counter")
        for model, count in sorted(self._cache_hits.items()):
            lines.append(f'thesisminer_cache_hits_total{{model="{model}"}} {count}')

        lines.append("")
        lines.append("# HELP thesisminer_cache_misses_total 缓存未命中总数")
        lines.append("# TYPE thesisminer_cache_misses_total counter")
        for model, count in sorted(self._cache_misses.items()):
            lines.append(f'thesisminer_cache_misses_total{{model="{model}"}} {count}')

        # 系统指标
        lines.append("")
        lines.append("# HELP thesisminer_active_sessions 当前活跃会话数")
        lines.append("# TYPE thesisminer_active_sessions gauge")
        lines.append(f"thesisminer_active_sessions {self._active_sessions}")

        lines.append("")
        lines.append("# HELP thesisminer_active_conversations 当前活跃对话数")
        lines.append("# TYPE thesisminer_active_conversations gauge")
        lines.append(f"thesisminer_active_conversations {self._active_conversations}")

        lines.append("")
        lines.append("# HELP thesisminer_db_connections 数据库连接数")
        lines.append("# TYPE thesisminer_db_connections gauge")
        lines.append(f"thesisminer_db_connections {self._db_connections}")

        return "\n".join(lines) + "\n"


class GrafanaDashboardGenerator:
    """
    Grafana 面板配置生成器。

    生成 ThesisMiner 的 Grafana 面板 JSON 配置，包括：
        - 请求概览面板（QPS、延迟、错误率）
        - Agent 性能面板（调用次数、成功率、耗时）
        - 模型成本面板（token 用量、成本趋势）
        - 缓存性能面板（命中率、节省成本）
        - 系统资源面板（会话数、连接数）

    用法示例::

        generator = GrafanaDashboardGenerator()
        dashboard = generator.generate_overview_dashboard()
        # 导入到 Grafana
    """

    def generate_overview_dashboard(self) -> Dict[str, Any]:
        """
        生成概览面板。

        包含以下图表：
            1. 请求 QPS（时间序列）
            2. 请求延迟 P50/P95/P99（时间序列）
            3. 错误率（仪表盘）
            4. 活跃会话数（仪表盘）
            5. Agent 调用热力图
            6. 模型成本趋势（柱状图）
        """
        return {
            "dashboard": {
                "id": None,
                "uid": "thesisminer-overview",
                "title": "ThesisMiner 概览",
                "tags": ["thesisminer", "overview"],
                "timezone": "browser",
                "schemaVersion": 39,
                "version": 1,
                "refresh": "30s",
                "time": {"from": "now-6h", "to": "now"},
                "panels": [
                    {
                        "id": 1,
                        "title": "请求 QPS",
                        "type": "timeseries",
                        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
                        "datasource": {"type": "prometheus", "uid": "prometheus"},
                        "targets": [
                            {
                                "expr": 'sum(rate(thesisminer_http_requests_total[5m])) by (endpoint)',
                                "legendFormat": "{{endpoint}}",
                                "refId": "A",
                            }
                        ],
                        "fieldConfig": {
                            "defaults": {
                                "unit": "reqps",
                                "custom": {"drawStyle": "line", "lineWidth": 2},
                            }
                        },
                    },
                    {
                        "id": 2,
                        "title": "请求延迟（P50/P95/P99）",
                        "type": "timeseries",
                        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
                        "datasource": {"type": "prometheus", "uid": "prometheus"},
                        "targets": [
                            {
                                "expr": 'histogram_quantile(0.50, sum(rate(thesisminer_http_request_duration_seconds_bucket[5m])) by (le))',
                                "legendFormat": "P50",
                                "refId": "A",
                            },
                            {
                                "expr": 'histogram_quantile(0.95, sum(rate(thesisminer_http_request_duration_seconds_bucket[5m])) by (le))',
                                "legendFormat": "P95",
                                "refId": "B",
                            },
                            {
                                "expr": 'histogram_quantile(0.99, sum(rate(thesisminer_http_request_duration_seconds_bucket[5m])) by (le))',
                                "legendFormat": "P99",
                                "refId": "C",
                            },
                        ],
                        "fieldConfig": {"defaults": {"unit": "s"}},
                    },
                    {
                        "id": 3,
                        "title": "错误率",
                        "type": "gauge",
                        "gridPos": {"h": 8, "w": 6, "x": 0, "y": 8},
                        "datasource": {"type": "prometheus", "uid": "prometheus"},
                        "targets": [
                            {
                                "expr": 'sum(rate(thesisminer_http_requests_total{status=~"5.."}[5m])) / sum(rate(thesisminer_http_requests_total[5m])) * 100',
                                "refId": "A",
                            }
                        ],
                        "fieldConfig": {
                            "defaults": {
                                "unit": "percent", "min": 0, "max": 100,
                                "thresholds": {
                                    "steps": [
                                        {"color": "green", "value": 0},
                                        {"color": "yellow", "value": 1},
                                        {"color": "red", "value": 5},
                                    ]
                                },
                            }
                        },
                    },
                    {
                        "id": 4,
                        "title": "活跃会话数",
                        "type": "stat",
                        "gridPos": {"h": 8, "w": 6, "x": 6, "y": 8},
                        "datasource": {"type": "prometheus", "uid": "prometheus"},
                        "targets": [{"expr": "thesisminer_active_sessions", "refId": "A"}],
                        "fieldConfig": {
                            "defaults": {
                                "color": {"mode": "thresholds"},
                                "thresholds": {
                                    "steps": [
                                        {"color": "blue", "value": 0},
                                        {"color": "green", "value": 10},
                                        {"color": "yellow", "value": 50},
                                    ]
                                },
                            }
                        },
                    },
                    {
                        "id": 5,
                        "title": "Agent 调用次数",
                        "type": "bargauge",
                        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
                        "datasource": {"type": "prometheus", "uid": "prometheus"},
                        "targets": [
                            {
                                "expr": 'sum(rate(thesisminer_agent_calls_total[5m])) by (agent) * 60',
                                "legendFormat": "{{agent}}",
                                "refId": "A",
                            }
                        ],
                        "fieldConfig": {"defaults": {"unit": "calls/min"}},
                    },
                    {
                        "id": 6,
                        "title": "模型成本趋势（每小时）",
                        "type": "timeseries",
                        "gridPos": {"h": 8, "w": 24, "x": 0, "y": 16},
                        "datasource": {"type": "prometheus", "uid": "prometheus"},
                        "targets": [
                            {
                                "expr": 'sum(rate(thesisminer_model_cost_dollars[1h])) by (model) * 3600',
                                "legendFormat": "{{model}}",
                                "refId": "A",
                            }
                        ],
                        "fieldConfig": {
                            "defaults": {
                                "unit": "currencyUSD",
                                "custom": {"drawStyle": "bars", "fillOpacity": 50},
                            }
                        },
                    },
                ],
            },
            "overwrite": True,
        }


class AlertRuleGenerator:
    """
    告警规则生成器。

    生成 Prometheus 告警规则，包括：
        - 高错误率告警
        - 高延迟告警
        - Agent 失败告警
        - 模型成本超限告警
        - 缓存命中率低告警
        - 服务不可用告警

    用法示例::

        generator = AlertRuleGenerator()
        rules = generator.generate_rules()
        print(rules)  # YAML 格式的告警规则
    """

    ALERT_RULES: Dict[str, Dict[str, Any]] = {
        "HighErrorRate": {
            "alert": "ThesisMinerHighErrorRate",
            "expr": 'sum(rate(thesisminer_http_requests_total{status=~"5.."}[5m])) / sum(rate(thesisminer_http_requests_total[5m])) > 0.05',
            "for": "5m",
            "labels": {"severity": "critical", "team": "thesisminer"},
            "annotations": {
                "summary": "错误率超过 5%",
                "description": "ThesisMiner 5xx 错误率超过 5% 阈值",
            },
        },
        "HighLatency": {
            "alert": "ThesisMinerHighLatency",
            "expr": 'histogram_quantile(0.95, sum(rate(thesisminer_http_request_duration_seconds_bucket[5m])) by (le)) > 5',
            "for": "10m",
            "labels": {"severity": "warning", "team": "thesisminer"},
            "annotations": {
                "summary": "P95 延迟超过 5 秒",
                "description": "当前 P95 延迟超过 5s 阈值",
            },
        },
        "AgentFailure": {
            "alert": "ThesisMinerAgentFailure",
            "expr": 'sum(rate(thesisminer_agent_errors_total[5m])) / sum(rate(thesisminer_agent_calls_total[5m])) > 0.1',
            "for": "5m",
            "labels": {"severity": "warning", "team": "thesisminer"},
            "annotations": {
                "summary": "Agent 错误率超过 10%",
                "description": "Agent 错误率超过 10% 阈值",
            },
        },
        "ModelCostExceeded": {
            "alert": "ThesisMinerModelCostExceeded",
            "expr": 'sum(rate(thesisminer_model_cost_dollars[1h])) * 3600 > 10',
            "for": "15m",
            "labels": {"severity": "warning", "team": "thesisminer"},
            "annotations": {
                "summary": "模型成本超过 $10/小时",
                "description": "当前成本率超过 $10/h 阈值",
            },
        },
        "LowCacheHitRate": {
            "alert": "ThesisMinerLowCacheHitRate",
            "expr": 'sum(rate(thesisminer_cache_hits_total[1h])) / (sum(rate(thesisminer_cache_hits_total[1h])) + sum(rate(thesisminer_cache_misses_total[1h]))) < 0.3',
            "for": "30m",
            "labels": {"severity": "info", "team": "thesisminer"},
            "annotations": {
                "summary": "缓存命中率低于 30%",
                "description": "当前缓存命中率低于 30% 阈值",
            },
        },
        "ServiceDown": {
            "alert": "ThesisMinerServiceDown",
            "expr": 'up{job="thesisminer"} == 0',
            "for": "1m",
            "labels": {"severity": "critical", "team": "thesisminer"},
            "annotations": {
                "summary": "ThesisMiner 服务不可用",
                "description": "服务已离线超过 1 分钟",
            },
        },
        "HighDbConnections": {
            "alert": "ThesisMinerHighDbConnections",
            "expr": "thesisminer_db_connections > 80",
            "for": "5m",
            "labels": {"severity": "warning", "team": "thesisminer"},
            "annotations": {
                "summary": "数据库连接数过高",
                "description": "当前连接数超过 80 阈值",
            },
        },
    }

    def generate_rules(self) -> str:
        """生成 Prometheus 告警规则 YAML。"""
        rules_yaml = "# ThesisMiner Prometheus 告警规则\n# 由 example_integrations.py 生成\ngroups:\n  - name: thesisminer-alerts\n    rules:\n"
        for rule in self.ALERT_RULES.values():
            rules_yaml += f"      - alert: {rule['alert']}\n"
            rules_yaml += f"        expr: {rule['expr']}\n"
            rules_yaml += f"        for: {rule['for']}\n"
            rules_yaml += "        labels:\n"
            for k, v in rule["labels"].items():
                rules_yaml += f"          {k}: {v}\n"
            rules_yaml += "        annotations:\n"
            for k, v in rule["annotations"].items():
                rules_yaml += f'          {k}: "{v}"\n'
        return rules_yaml

    def get_rule_count(self) -> int:
        """获取告警规则数量。"""
        return len(self.ALERT_RULES)


# =============================================================================
# 第七部分：综合示例函数
# =============================================================================
# 以下函数演示如何将上述组件组合使用。
# =============================================================================


async def example_model_integration() -> None:
    """
    示例：第三方模型集成。

    演示如何创建多个模型适配器，并通过路由器进行 A/B 测试和故障转移。
    """
    print("\n" + "=" * 70)
    print("示例 1：第三方模型集成")
    print("=" * 70)

    # 创建模型配置
    ernie_config = ModelProviderConfig(
        name="ernie-bot",
        api_base="https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions",
        api_key="mock_client_id",
        model_name="ernie-bot-4",
        max_tokens=2048,
        temperature=0.7,
        extra_params={"client_secret": "mock_client_secret"},
    )
    spark_config = ModelProviderConfig(
        name="spark",
        api_base="wss://spark-api.xf-yun.com/v3.5/chat",
        api_key="mock_api_secret",
        model_name="spark-v3.5",
        max_tokens=2048,
        extra_params={"appid": "mock_appid", "api_key": "mock_api_key"},
    )
    vllm_config = ModelProviderConfig(
        name="vllm-local",
        api_base="http://localhost:8000/v1",
        api_key="EMPTY",
        model_name="meta-llama/Llama-3-70B-Instruct",
        max_tokens=2048,
        extra_params={"enable_prefix_caching": True},
    )

    # 创建适配器
    ernie_adapter = ErnieBotAdapter(ernie_config)
    spark_adapter = SparkAdapter(spark_config)
    vllm_adapter = VLLMAdapter(vllm_config)

    # 创建路由器（加权随机策略）
    router = ModelRouter(strategy="weighted")
    router.add_adapter("ernie", ernie_adapter, weight=0.3, cost_per_1k=0.012)
    router.add_adapter("spark", spark_adapter, weight=0.3, cost_per_1k=0.015)
    router.add_adapter("vllm", vllm_adapter, weight=0.4, cost_per_1k=0.001)

    # 构造消息
    messages = [
        ChatMessage.system("你是一个学术论题生成助手。"),
        ChatMessage.user("请为计算机科学专业的硕士生生成 3 个论题。"),
    ]

    # 路由调用
    print("\n--- 路由调用 ---")
    result = await router.route(messages)
    if result.success:
        response: ChatResponse = result.data
        print(f"路由到：{result.metadata.get('routed_to')}")
        print(f"模型：{response.model}")
        print(f"回复：{response.content}")
        print(f"Token 用量：{response.total_tokens}")
    else:
        print(f"调用失败：{result.error}")

    # 流式调用
    print("\n--- 流式调用（vLLM）---")
    async for chunk in vllm_adapter.stream_chat(messages):
        print(chunk, end="", flush=True)
    print()

    # 路由统计
    print("\n--- 路由统计 ---")
    stats = router.get_routing_stats()
    for name, stat in stats.items():
        print(f"  {name}: 调用 {stat['call_count']} 次, "
              f"token {stat['total_tokens']}, "
              f"健康={'是' if stat['healthy'] else '否'}")


async def example_search_integration() -> None:
    """示例：外部检索源接入。"""
    print("\n" + "=" * 70)
    print("示例 2：外部检索源接入")
    print("=" * 70)

    # 创建检索源
    pubmed_config = SearchSourceConfig(
        name="pubmed",
        api_base="https://eutils.ncbi.nlm.nih.gov/entrez/eutils",
        max_results=10, rate_limit_per_sec=3.0,
    )
    arxiv_config = SearchSourceConfig(
        name="arxiv",
        api_base="http://export.arxiv.org/api/query",
        max_results=10, rate_limit_per_sec=0.33,
    )
    scholar_config = SearchSourceConfig(
        name="google_scholar",
        api_base="https://serpapi.com/search",
        api_key="mock_serpapi_key",
        max_results=10, rate_limit_per_sec=1.0,
    )

    pubmed = PubMedSearchSource(pubmed_config)
    arxiv = ArxivSearchSource(arxiv_config)
    scholar = GoogleScholarSearchSource(scholar_config)

    # 单源检索
    print("\n--- PubMed 检索 ---")
    result = await pubmed.search("deep learning medical imaging", year_from=2020, year_to=2024)
    if result.success:
        print(f"检索到 {len(result.data)} 条结果（耗时 {result.elapsed:.2f}s）")
        for i, paper in enumerate(result.data[:3], 1):
            print(f"  [{i}] {paper.brief(80)}")

    print("\n--- arXiv 检索 ---")
    result = await arxiv.search("transformer attention mechanism", category="cs.AI")
    if result.success:
        print(f"检索到 {len(result.data)} 条结果（耗时 {result.elapsed:.2f}s）")
        for i, paper in enumerate(result.data[:3], 1):
            print(f"  [{i}] {paper.brief(80)}")

    # 多源聚合检索
    print("\n--- 多源聚合检索 ---")
    searcher = MultiSourceSearcher()
    searcher.add_source("pubmed", pubmed, weight=1.0)
    searcher.add_source("arxiv", arxiv, weight=1.2)
    searcher.add_source("scholar", scholar, weight=1.0)

    result = await searcher.search("deep learning medical imaging", max_results=15)
    if result.success:
        print(f"聚合检索到 {len(result.data)} 条结果（耗时 {result.elapsed:.2f}s）")
        print(f"去重前：{result.metadata.get('total_before_dedup')}，"
              f"去重后：{result.metadata.get('total_after_dedup')}")
        print("\n各源统计：")
        for source_name, stat in result.metadata.get("source_stats", {}).items():
            if stat.get("success"):
                print(f"  {source_name}: {stat['count']} 条（{stat['elapsed']:.2f}s）")
            else:
                print(f"  {source_name}: 失败 - {stat.get('error')}")

        print("\n前 5 条结果：")
        for i, paper in enumerate(result.data[:5], 1):
            print(f"  [{i}] [{paper.source}] {paper.brief(60)}")

    # 检索统计
    print("\n--- 检索统计 ---")
    for source in [pubmed, arxiv, scholar]:
        stat = source.get_stats()
        print(f"  {stat['name']}: 检索 {stat['total_searches']} 次, "
              f"结果 {stat['total_results']} 条, "
              f"平均 {stat['avg_results_per_search']} 条/次")


async def example_webhook_integration() -> None:
    """示例：Webhook 集成。"""
    print("\n" + "=" * 70)
    print("示例 3：Webhook 集成")
    print("=" * 70)

    # 创建通知器配置
    slack_config = WebhookConfig(
        name="slack-notify",
        webhook_url="https://example.com/webhook/slack-placeholder",
        channel="slack",
    )
    dingtalk_config = WebhookConfig(
        name="dingtalk-notify",
        webhook_url="https://oapi.dingtalk.com/robot/send?access_token=XXXXXXXX",
        secret="SECXXXXXXXXXXXXXXXX",
        channel="dingtalk",
    )
    wechat_config = WebhookConfig(
        name="wechat-notify",
        webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=XXXXXXXX",
        channel="wechat_work",
    )

    # 创建通知器
    slack_notifier = SlackWebhookNotifier(slack_config)
    dingtalk_notifier = DingTalkWebhookNotifier(dingtalk_config)
    wechat_notifier = WeChatWorkWebhookNotifier(wechat_config)

    # 创建管理器
    manager = WebhookManager()
    manager.add_notifier("slack", slack_notifier, event_types={"proposal.generated", "budget.exceeded"})
    manager.add_notifier("dingtalk", dingtalk_notifier)  # 订阅所有事件
    manager.add_notifier("wechat", wechat_notifier, event_types={"proposal.generated", "system.error"})

    # 发送通知：论题生成完成
    print("\n--- 发送通知：论题生成完成 ---")
    event1 = WebhookEvent(
        event_type="proposal.generated",
        title="论题生成完成",
        message="论题「基于深度学习的医学影像分割方法研究」已成功生成。",
        severity="info",
        metadata={
            "session_id": "sess_abc123",
            "cost": "$0.05",
            "duration": "12.5s",
            "model": "deepseek-r2",
        },
    )
    results = await manager.notify_all(event1)
    for name, result in results.items():
        status = "成功" if result.success else f"失败({result.error})"
        print(f"  {name}: {status}")

    # 发送通知：预算超限
    print("\n--- 发送通知：预算超限 ---")
    event2 = WebhookEvent(
        event_type="budget.exceeded",
        title="预算超限警告",
        message="会话 sess_abc123 的 token 预算已超过 80%。",
        severity="warning",
        metadata={
            "session_id": "sess_abc123",
            "used": "$8.50",
            "budget": "$10.00",
            "percentage": "85%",
        },
    )
    results = await manager.notify_all(event2)
    for name, result in results.items():
        status = "成功" if result.success else f"失败({result.error})"
        print(f"  {name}: {status}")

    # 发送通知：系统错误
    print("\n--- 发送通知：系统错误 ---")
    event3 = WebhookEvent(
        event_type="system.error",
        title="系统错误",
        message="数据库连接池耗尽，请检查连接配置。",
        severity="critical",
        metadata={
            "error": "ConnectionPoolExhausted",
            "active_connections": 100,
            "max_connections": 100,
        },
    )
    results = await manager.notify_all(event3)
    for name, result in results.items():
        status = "成功" if result.success else f"失败({result.error})"
        print(f"  {name}: {status}")

    # 通知历史
    print("\n--- 通知历史 ---")
    history = manager.get_history(limit=5)
    for item in history:
        print(f"  [{item['severity'].upper()}] {item['title']} ({item['event_type']})")

    # 通知器统计
    print("\n--- 通知器统计 ---")
    for notifier in [slack_notifier, dingtalk_notifier, wechat_notifier]:
        stat = notifier.get_stats()
        print(f"  {stat['name']} ({stat['channel']}): "
              f"发送 {stat['sent']}, 错误 {stat['errors']}, "
              f"成功率 {stat['success_rate']:.1%}")


def example_cicd_integration() -> None:
    """示例：CI/CD 集成。"""
    print("\n" + "=" * 70)
    print("示例 4：CI/CD 集成")
    print("=" * 70)

    # 创建配置
    config = CICDConfig(
        name="thesisminer-cicd",
        repo_url="https://github.com/example/thesisminer",
        branch="main",
        python_version="3.11",
        node_version="20",
        deploy_target="docker",
        registry_url="ghcr.io",
        image_name="thesisminer",
    )

    # 生成工作流
    generator = GitHubActionsGenerator(config)

    print("\n--- 测试工作流（前 20 行）---")
    test_workflow = generator.generate_test_workflow()
    for i, line in enumerate(test_workflow.split("\n")[:20], 1):
        print(f"  {i:3d} | {line}")

    print("\n--- 部署工作流（前 20 行）---")
    deploy_workflow = generator.generate_deploy_workflow()
    for i, line in enumerate(deploy_workflow.split("\n")[:20], 1):
        print(f"  {i:3d} | {line}")

    print("\n--- Dockerfile（前 20 行）---")
    dockerfile = generator.generate_dockerfile()
    for i, line in enumerate(dockerfile.split("\n")[:20], 1):
        print(f"  {i:3d} | {line}")

    # 运行测试
    print("\n--- 运行测试 ---")
    runner = TestRunner()
    test_result = runner.run_unit_tests()
    print(f"  单元测试：{test_result.summary}")
    print(f"  通过率：{test_result.pass_rate:.1%}")

    lint_result = runner.run_lint()
    print(f"  代码检查：{lint_result.summary}")


def example_monitoring_integration() -> None:
    """示例：监控集成。"""
    print("\n" + "=" * 70)
    print("示例 5：监控集成")
    print("=" * 70)

    # 创建指标收集器
    collector = MetricsCollector()

    # 记录请求
    collector.record_request("POST", "/api/chat", 200, 0.5)
    collector.record_request("POST", "/api/chat", 200, 0.8)
    collector.record_request("POST", "/api/chat", 500, 1.2)
    collector.record_request("GET", "/api/sessions", 200, 0.1)
    collector.record_request("GET", "/api/proposals", 200, 0.3)

    # 记录 Agent 调用
    collector.record_agent_call("reasoner", success=True, duration=1.5)
    collector.record_agent_call("mentor", success=True, duration=2.0)
    collector.record_agent_call("searcher", success=True, duration=0.8)
    collector.record_agent_call("critic", success=False, duration=0.5)

    # 记录模型使用
    collector.record_model_usage("deepseek-r2", prompt_tokens=500, completion_tokens=200, cost=0.003)
    collector.record_model_usage("deepseek-r2", prompt_tokens=300, completion_tokens=150, cost=0.002)
    collector.record_model_usage("claude-opus-4.5", prompt_tokens=400, completion_tokens=180, cost=0.015)

    # 记录缓存
    collector.record_cache("deepseek-r2", hit=True)
    collector.record_cache("deepseek-r2", hit=True)
    collector.record_cache("deepseek-r2", hit=False)
    collector.record_cache("claude-opus-4.5", hit=True)
    collector.record_cache("claude-opus-4.5", hit=False)

    # 设置系统指标
    collector.set_active_sessions(15)
    collector.set_active_conversations(42)
    collector.set_db_connections(8)

    # 导出 Prometheus 指标
    print("\n--- Prometheus 指标（前 30 行）---")
    prometheus_output = collector.export_prometheus()
    for i, line in enumerate(prometheus_output.split("\n")[:30], 1):
        print(f"  {i:3d} | {line}")

    # 缓存命中率
    print("\n--- 缓存命中率 ---")
    for model in ["deepseek-r2", "claude-opus-4.5"]:
        rate = collector.get_cache_hit_rate(model)
        print(f"  {model}: {rate:.1%}")

    # 生成 Grafana 面板
    print("\n--- Grafana 面板 ---")
    grafana_gen = GrafanaDashboardGenerator()
    dashboard = grafana_gen.generate_overview_dashboard()
    print(f"  面板标题：{dashboard['dashboard']['title']}")
    print(f"  面板数量：{len(dashboard['dashboard']['panels'])}")
    for panel in dashboard["dashboard"]["panels"]:
        print(f"    [{panel['id']}] {panel['title']} ({panel['type']})")

    # 生成告警规则
    print("\n--- 告警规则 ---")
    alert_gen = AlertRuleGenerator()
    rules_yaml = alert_gen.generate_rules()
    print(f"  规则数量：{alert_gen.get_rule_count()}")
    print("\n  规则内容（前 20 行）：")
    for i, line in enumerate(rules_yaml.split("\n")[:20], 1):
        print(f"  {i:3d} | {line}")


async def run_all_examples() -> None:
    """运行所有示例。"""
    print("=" * 70)
    print("ThesisMiner v8.0 集成示例")
    print("=" * 70)
    print(f"运行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python 版本：{sys.version.split()[0]}")

    await example_model_integration()
    await example_search_integration()
    await example_webhook_integration()
    example_cicd_integration()
    example_monitoring_integration()

    print("\n" + "=" * 70)
    print("所有示例运行完成！")
    print("=" * 70)


# =============================================================================
# 主入口
# =============================================================================
if __name__ == "__main__":
    asyncio.run(run_all_examples())
