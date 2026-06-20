# ThesisMiner v8.0 集成架构设计文档

> **版本**: v8.0.0  
> **最后更新**: 2026-06-20  
> **文档状态**: 正式发布  
> **维护者**: ThesisMiner Architecture Team

---

## 目录

1. [文档概述](#1-文档概述)
2. [集成架构总览](#2-集成架构总览)
3. [外部系统集成](#3-外部系统集成)
4. [LLM API 集成](#4-llm-api-集成)
5. [学术数据库集成](#5-学术数据库集成)
6. [引文管理工具集成](#6-引文管理工具集成)
7. [API 集成模式](#7-api-集成模式)
8. [数据同步与 ETL](#8-数据同步与-etl)
9. [认证集成](#9-认证集成)
10. [错误处理与重试](#10-错误处理与重试)
11. [集成测试](#11-集成测试)
12. [Webhook 与事件集成](#12-webhook-与事件集成)
13. [文件格式集成](#13-文件格式集成)
14. [消息协议设计](#14-消息协议设计)
15. [集成安全](#15-集成安全)
16. [集成监控](#16-集成监控)
17. [集成版本管理](#17-集成版本管理)
18. [集成性能优化](#18-集成性能优化)
19. [集成故障排查](#19-集成故障排查)
20. [附录](#20-附录)

---

## 1. 文档概述

### 1.1 文档目的

本文档阐述 ThesisMiner v8.0 系统与外部系统的集成架构设计。ThesisMiner 作为论文挖掘与分析平台，需要与多种外部系统协作，包括 LLM（大语言模型）API、学术数据库、引文管理工具等。本文档定义了集成的模式、协议、安全策略与测试方案，确保集成的可靠性、安全性与可维护性。

### 1.2 文档范围

本文档覆盖以下集成场景：

- LLM API 集成（DeepSeek、OpenAI 兼容接口）
- 学术数据库集成（arXiv、Semantic Scholar、CrossRef、Google Scholar）
- 引文管理工具集成（Zotero、Mendeley、BibTeX、EndNote）
- API 集成模式（同步、异步、流式、批处理）
- 数据同步与 ETL 流程
- 认证与授权集成
- 错误处理与重试策略
- 集成测试策略
- Webhook 与事件驱动集成
- 文件格式集成（PDF、LaTeX、Word、Markdown）

### 1.3 术语表

| 术语 | 英文 | 说明 |
|------|------|------|
| 集成 | Integration | 系统间连接与数据交换 |
| API | Application Programming Interface | 应用编程接口 |
| Webhook | Webhook | 事件回调通知 |
| ETL | Extract-Transform-Load | 数据抽取-转换-加载 |
| OAuth | Open Authorization | 开放授权协议 |
| JWT | JSON Web Token | JSON Web 令牌 |
| Idempotent | Idempotent | 幂等性（多次调用结果相同） |
| Circuit Breaker | Circuit Breaker | 熔断器 |
| Backpressure | Backpressure | 背压 |
| SLA | Service Level Agreement | 服务等级协议 |
| Rate Limit | Rate Limit | 速率限制 |
| Idempotency Key | Idempotency Key | 幂等键 |

### 1.4 设计原则

ThesisMiner v8.0 的集成设计遵循以下原则：

1. **松耦合 (Loose Coupling)**：集成双方通过明确接口交互，不依赖内部实现
2. **契约优先 (Contract First)**：先定义接口契约，再实现
3. **幂等性 (Idempotency)**：集成操作支持幂等重试
4. **弹性 (Resilience)**：集成失败不影响核心功能
5. **可观测 (Observability)**：集成过程可监控、可追踪
6. **安全 (Security)**：认证、授权、加密传输
7. **版本兼容 (Versioning)**：接口版本化管理，向后兼容

### 1.5 集成目标

| 目标 | 指标 | 说明 |
|------|------|------|
| 可用性 | 99.5% | 集成服务可用率 |
| 延迟 | < 5s | 集成调用平均延迟 |
| 成功率 | > 99% | 集成调用成功率 |
| 重试成功率 | > 90% | 重试后成功比例 |
| 故障恢复 | < 60s | 集成故障恢复时间 |
| 数据一致性 | 100% | 数据同步一致性 |

---

## 2. 集成架构总览

### 2.1 整体集成架构

```
┌─────────────────────────────────────────────────────────────────┐
│  ThesisMiner v8.0 集成架构                                       │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  ThesisMiner 核心                                          │   │
│  │  ┌────────────────────────────────────────────────────┐  │   │
│  │  │  集成层 (Integration Layer)                          │  │   │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐           │  │   │
│  │  │  │LLM 适配器│ │学术库适配│ │引文适配器│           │  │   │
│  │  │  └──────────┘ └──────────┘ └──────────┘           │  │   │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐           │  │   │
│  │  │  │文件适配器│ │认证适配器│ │Webhook   │           │  │   │
│  │  │  └──────────┘ └──────────┘ └──────────┘           │  │   │
│  │  └────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
│         │            │            │            │                 │
│  ┌──────▼────────────▼────────────▼────────────▼─────────────┐  │
│  │  外部系统                                                    │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐      │  │
│  │  │DeepSeek │  │ arXiv   │  │CrossRef │  │ Zotero  │      │  │
│  │  │ LLM API │  │ API     │  │ API     │  │ API     │      │  │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘      │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐      │  │
│  │  │Semantic │  │ Google  │  │ OpenAI  │  │ Mendeley│      │  │
│  │  │Scholar  │  │ Scholar │  │ API     │  │ API     │      │  │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘      │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 集成模式分类

| 集成模式 | 说明 | 适用场景 | 示例 |
|---------|------|---------|------|
| 同步调用 | 请求-响应 | 实时查询 | LLM 分析、论文检索 |
| 异步回调 | 请求-回调 | 耗时操作 | 大规模分析、导出 |
| 流式传输 | Server-Sent Events | 实时数据流 | LLM 流式输出 |
| 批处理 | 批量请求 | 大量数据 | 批量论文导入 |
| 事件驱动 | Pub/Sub | 解耦通知 | Webhook 通知 |
| 轮询 | 定时拉取 | 数据同步 | 定期同步论文库 |
| 文件交换 | 文件传输 | 离线数据 | BibTeX 导入导出 |

### 2.3 集成层架构

```
┌─────────────────────────────────────────────────────────────────┐
│  集成层架构                                                      │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  API 层 (接口暴露)                                          │   │
│  │  - REST API                                                 │   │
│  │  - WebSocket                                                │   │
│  │  - GraphQL (可选)                                           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              ↓                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  适配器层 (协议转换)                                        │   │
│  │  ┌──────────────────────────────────────────────────┐    │   │
│  │  │  适配器模式 (Adapter Pattern)                      │    │   │
│  │  │  - 统一接口 → 各外部系统专有协议                    │    │   │
│  │  │  - 数据格式转换                                    │    │   │
│  │  │  - 错误码映射                                      │    │   │
│  │  └──────────────────────────────────────────────────┘    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              ↓                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  弹性层 (容错)                                              │   │
│  │  - 重试 (Retry)                                            │   │
│  │  - 熔断 (Circuit Breaker)                                  │   │
│  │  - 限流 (Rate Limit)                                       │   │
│  │  - 超时 (Timeout)                                          │   │
│  │  - 降级 (Fallback)                                         │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              ↓                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  传输层 (通信)                                              │   │
│  │  - HTTP/HTTPS                                               │   │
│  │  - gRPC (可选)                                              │   │
│  │  - WebSocket                                                │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 外部系统集成

### 3.1 外部系统清单

| 系统 | 类型 | 协议 | 认证 | 用途 |
|------|------|------|------|------|
| DeepSeek | LLM | HTTPS REST | API Key | 论文分析、创意生成 |
| OpenAI | LLM | HTTPS REST | API Key | 备用 LLM |
| arXiv | 学术库 | HTTPS REST | 无 | 论文检索 |
| Semantic Scholar | 学术库 | HTTPS REST | API Key | 论文元数据 |
| CrossRef | 学术库 | HTTPS REST | 无 (Polite) | DOI 解析 |
| Google Scholar | 学术库 | Web Scraping | 无 | 引用统计 |
| Zotero | 引文管理 | HTTPS REST | API Key | 文献管理 |
| Mendeley | 引文管理 | HTTPS REST | OAuth 2.0 | 文献管理 |
| ORCID | 认证 | HTTPS REST | OAuth 2.0 | 作者认证 |

### 3.2 集成优先级

| 优先级 | 系统 | 状态 | 说明 |
|--------|------|------|------|
| P0 | DeepSeek LLM | 已集成 | 核心 LLM 服务 |
| P0 | arXiv | 已集成 | 论文检索 |
| P1 | Semantic Scholar | 已集成 | 论文元数据 |
| P1 | CrossRef | 已集成 | DOI 解析 |
| P2 | Zotero | 规划中 | 文献管理 |
| P2 | Mendeley | 规划中 | 文献管理 |
| P3 | Google Scholar | 规划中 | 引用统计 |
| P3 | ORCID | 规划中 | 作者认证 |

---

## 4. LLM API 集成

### 4.1 LLM 集成架构

```
┌─────────────────────────────────────────────────────────────────┐
│  LLM API 集成架构                                                │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  LLM 客户端层                                               │   │
│  │  ┌──────────────────────────────────────────────────┐    │   │
│  │  │  LLMClient (统一接口)                              │    │   │
│  │  │  - chat()        对话                              │    │   │
│  │  │  - chat_stream() 流式对话                          │    │   │
│  │  │  - embed()       向量嵌入                          │    │   │
│  │  └──────────────────────────────────────────────────┘    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              ↓                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  适配器层                                                   │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │   │
│  │  │ DeepSeek     │  │ OpenAI       │  │ Custom       │   │   │
│  │  │ Adapter      │  │ Adapter      │  │ Adapter      │   │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              ↓                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  弹性层                                                     │   │
│  │  - 三段式 Prompt 缓存                                       │   │
│  │  - 请求重试 (指数退避)                                       │   │
│  │  - 熔断器                                                   │   │
│  │  - 速率限制                                                 │   │
│  │  - 超时控制                                                 │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              ↓                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  传输层                                                     │   │
│  │  - HTTP/HTTPS (httpx)                                      │   │
│  │  - SSE (Server-Sent Events)                                │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 LLM 客户端接口

```python
# backend/integration/llm/client.py
"""LLM 客户端统一接口"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, AsyncIterator, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class LLMMessage:
    """LLM 消息"""
    role: str  # system / user / assistant
    content: str


@dataclass
class LLMRequest:
    """LLM 请求"""
    messages: List[LLMMessage]
    model: str = "deepseek-chat"
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 1.0
    stream: bool = False
    # 三段式 Prompt 缓存支持
    cache_prefix: Optional[str] = None  # 系统提示缓存键
    # 幂等性
    idempotency_key: Optional[str] = None
    # 超时
    timeout: float = 120.0
    # 额外参数
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """LLM 响应"""
    content: str
    model: str
    finish_reason: str
    usage: Dict[str, int]  # prompt_tokens, completion_tokens, total_tokens
    cached: bool = False
    raw: Optional[Dict] = None


class LLMAdapter(ABC):
    """LLM 适配器抽象基类"""

    @abstractmethod
    async def chat(self, request: LLMRequest) -> LLMResponse:
        """同步对话"""
        pass

    @abstractmethod
    async def chat_stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """流式对话"""
        pass

    @abstractmethod
    async def embed(self, text: str, model: str = "") -> List[float]:
        """向量嵌入"""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        pass


class LLMClient:
    """LLM 客户端

    统一管理多个 LLM 适配器，支持故障切换。
    """

    def __init__(self):
        self._adapters: Dict[str, LLMAdapter] = {}
        self._primary: Optional[str] = None
        self._fallback: List[str] = []

    def register_adapter(self, name: str, adapter: LLMAdapter, is_primary: bool = False):
        """注册适配器"""
        self._adapters[name] = adapter
        if is_primary:
            self._primary = name
        else:
            self._fallback.append(name)

    async def chat(self, request: LLMRequest) -> LLMResponse:
        """对话（带故障切换）"""
        # 尝试主适配器
        if self._primary and self._primary in self._adapters:
            try:
                return await self._adapters[self._primary].chat(request)
            except Exception as e:
                logger.warning(f"主 LLM {self._primary} 失败: {e}")

        # 尝试备用适配器
        for name in self._fallback:
            if name in self._adapters:
                try:
                    logger.info(f"切换到备用 LLM: {name}")
                    return await self._adapters[name].chat(request)
                except Exception as e:
                    logger.warning(f"备用 LLM {name} 失败: {e}")

        raise LLMUnavailableError("所有 LLM 适配器均不可用")

    async def chat_stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """流式对话"""
        request.stream = True
        if self._primary and self._primary in self._adapters:
            async for chunk in self._adapters[self._primary].chat_stream(request):
                yield chunk
        else:
            raise LLMUnavailableError("无可用 LLM 适配器")


class LLMUnavailableError(Exception):
    pass
```

### 4.3 DeepSeek 适配器实现

```python
# backend/integration/llm/deepseek_adapter.py
"""DeepSeek LLM 适配器"""
import logging
import httpx
import json
from typing import AsyncIterator, Optional, List

logger = logging.getLogger(__name__)


class DeepSeekAdapter(LLMAdapter):
    """DeepSeek API 适配器

    支持 OpenAI 兼容接口 + 三段式 Prompt 缓存。
    """

    BASE_URL = "https://api.deepseek.com/v1"

    def __init__(self, api_key: str, base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url or self.BASE_URL
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(120.0, connect=10.0),
        )

    async def chat(self, request: LLMRequest) -> LLMResponse:
        """同步对话"""
        payload = self._build_payload(request)
        response = await self._client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]
        return LLMResponse(
            content=choice["message"]["content"],
            model=data.get("model", request.model),
            finish_reason=choice.get("finish_reason", "stop"),
            usage=data.get("usage", {}),
            raw=data,
        )

    async def chat_stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """流式对话"""
        payload = self._build_payload(request)
        payload["stream"] = True

        async with self._client.stream(
            "POST", "/chat/completions", json=payload
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    delta = chunk["choices"][0].get("delta", {})
                    if "content" in delta:
                        yield delta["content"]

    async def embed(self, text: str, model: str = "") -> List[float]:
        """向量嵌入"""
        payload = {
            "model": model or "text-embedding-ada-002",
            "input": text,
        }
        response = await self._client.post("/embeddings", json=payload)
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            response = await self._client.get("/models")
            return response.status_code == 200
        except Exception:
            return False

    def _build_payload(self, request: LLMRequest) -> dict:
        """构建请求 payload"""
        messages = [
            {"role": msg.role, "content": msg.content}
            for msg in request.messages
        ]
        payload = {
            "model": request.model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "top_p": request.top_p,
        }
        # 三段式 Prompt 缓存
        if request.cache_prefix:
            payload["cache_prefix"] = request.cache_prefix
        # 幂等性 Key
        if request.idempotency_key:
            payload["idempotency_key"] = request.idempotency_key
        # 额外参数
        payload.update(request.extra)
        return payload

    async def close(self):
        """关闭客户端"""
        await self._client.aclose()
```

### 4.4 三段式 Prompt 缓存

```python
# backend/integration/llm/prompt_cache.py
"""三段式 Prompt 缓存

DeepSeek 支持三段式 Prompt 缓存:
1. 系统提示 (System Prompt) - 固定不变
2. 上下文 (Context) - 会话内变化
3. 用户输入 (User Input) - 每次变化

通过缓存前两段，减少 token 消耗和延迟。
"""
import hashlib
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)


class ThreeSegmentPromptCache:
    """三段式 Prompt 缓存管理器"""

    def __init__(self, cache_client):
        self.cache = cache_client

    def build_cached_prompt(
        self,
        system_prompt: str,
        context: str,
        user_input: str,
    ) -> List[LLMMessage]:
        """构建带缓存的三段式 Prompt"""
        # 计算缓存键
        system_hash = self._hash(system_prompt)
        context_hash = self._hash(context)
        cache_key = f"prompt:{system_hash}:{context_hash}"

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=f"{context}\n\n{user_input}"),
        ]

        return messages, cache_key

    def _hash(self, text: str) -> str:
        """计算文本哈希"""
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    async def get_cached_response(self, cache_key: str) -> Optional[str]:
        """获取缓存的响应"""
        return await self.cache.get(f"llm_response:{cache_key}")

    async def set_cached_response(self, cache_key: str, response: str, ttl: int = 3600):
        """设置缓存响应"""
        await self.cache.set(f"llm_response:{cache_key}", response, ttl=ttl)
```

### 4.5 LLM 调用弹性策略

```python
# backend/integration/llm/resilience.py
"""LLM 调用弹性策略"""
import asyncio
import logging
import time
from typing import Optional, Callable, Any

logger = logging.getLogger(__name__)


class LLMResilienceWrapper:
    """LLM 调用弹性包装器

    集成重试、熔断、限流、超时、降级。
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        timeout: float = 120.0,
        rate_limit: int = 50,  # 每分钟最大调用
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.timeout = timeout
        self.rate_limiter = TokenBucketRateLimiter(
            capacity=rate_limit,
            refill_rate=rate_limit / 60.0,
        )
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60,
        )

    async def call_with_resilience(
        self,
        func: Callable,
        *args,
        fallback: Optional[Callable] = None,
        **kwargs,
    ) -> Any:
        """带弹性的调用"""
        # 1. 熔断检查
        if not self._circuit_breaker.can_call():
            logger.warning("LLM 熔断中，尝试降级")
            if fallback:
                return await fallback(*args, **kwargs)
            raise CircuitBreakerOpenError("LLM 熔断器开启")

        # 2. 限流
        await self.rate_limiter.acquire()

        # 3. 重试
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=self.timeout,
                )
                self._circuit_breaker.record_success()
                return result
            except asyncio.TimeoutError:
                last_error = TimeoutError(f"LLM 调用超时 ({self.timeout}s)")
                logger.warning(f"LLM 超时 (attempt {attempt+1})")
            except Exception as e:
                last_error = e
                if self._is_retryable(e):
                    logger.warning(
                        f"LLM 调用失败 (attempt {attempt+1}): {e}"
                    )
                else:
                    raise

            if attempt < self.max_retries:
                delay = min(
                    self.base_delay * (2 ** attempt),
                    self.max_delay,
                )
                await asyncio.sleep(delay)

        self._circuit_breaker.record_failure()

        # 4. 降级
        if fallback:
            logger.info("LLM 调用失败，使用降级策略")
            return await fallback(*args, **kwargs)

        raise last_error

    def _is_retryable(self, error: Exception) -> bool:
        """判断错误是否可重试"""
        if isinstance(error, (httpx.TimeoutException, httpx.NetworkError)):
            return True
        if isinstance(error, httpx.HTTPStatusError):
            # 429 Too Many Requests, 500+ Server Error
            return error.response.status_code in (429, 500, 502, 503, 504)
        return False


class TokenBucketRateLimiter:
    """令牌桶限流器"""

    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self._tokens = capacity
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        """获取令牌"""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(
                self.capacity,
                self._tokens + elapsed * self.refill_rate,
            )
            self._last_refill = now

            if self._tokens < 1:
                wait_time = (1 - self._tokens) / self.refill_rate
                await asyncio.sleep(wait_time)
                self._tokens = 0
            else:
                self._tokens -= 1


class CircuitBreakerOpenError(Exception):
    pass
```

### 4.6 LLM 集成监控

| 指标 | 类型 | 说明 | 告警阈值 |
|------|------|------|---------|
| llm_request_total | Counter | LLM 请求总数 | - |
| llm_request_duration_seconds | Histogram | 请求耗时 P99 | > 30s |
| llm_error_total | Counter | 错误总数 | 错误率 > 5% |
| llm_retry_total | Counter | 重试次数 | 重试率 > 20% |
| llm_tokens_used_total | Counter | Token 使用量 | - |
| llm_cache_hit_total | Counter | 缓存命中 | 命中率 < 30% |
| llm_circuit_breaker_state | Gauge | 熔断器状态 | open |
| llm_rate_limit_triggered | Counter | 限流触发 | > 0 |

---

## 5. 学术数据库集成

### 5.1 学术数据库集成架构

```
┌─────────────────────────────────────────────────────────────────┐
│  学术数据库集成架构                                               │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  统一检索接口                                                │   │
│  │  ┌──────────────────────────────────────────────────┐    │   │
│  │  │  AcademicSearchClient                              │    │   │
│  │  │  - search(query) → List[Paper]                    │    │   │
│  │  │  - get_paper(id) → Paper                          │    │   │
│  │  │  - get_references(id) → List[Paper]               │    │   │
│  │  │  - get_citations(id) → List[Paper]                │    │   │
│  │  └──────────────────────────────────────────────────┘    │   │
│  └──────────────────────────────────────────────────────────┘   │
│         │            │            │            │                 │
│  ┌──────▼──────┐ ┌───▼─────┐ ┌───▼─────┐ ┌───▼─────┐          │
│  │ arXiv       │ │Semantic │ │CrossRef │ │Google   │          │
│  │ Adapter     │ │Scholar  │ │Adapter  │ │Scholar  │          │
│  │             │ │Adapter  │ │         │ │Adapter  │          │
│  └─────────────┘ └─────────┘ └─────────┘ └─────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 统一论文模型

```python
# backend/integration/academic/models.py
"""统一论文数据模型"""
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


@dataclass
class Author:
    """作者"""
    name: str
    affiliation: Optional[str] = None
    orcid: Optional[str] = None
    email: Optional[str] = None


@dataclass
class Paper:
    """论文（统一模型）"""
    # 标识
    id: str                          # 内部 ID
    source: str                      # 来源: arxiv / semantic_scholar / crossref
    source_id: str                   # 来源系统 ID
    # 基本信息
    title: str
    authors: List[Author] = field(default_factory=list)
    abstract: Optional[str] = None
    # 出版信息
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    journal: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    year: Optional[int] = None
    published_date: Optional[datetime] = None
    # 分类
    keywords: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    language: str = "en"
    # 链接
    url: Optional[str] = None
    pdf_url: Optional[str] = None
    # 引用
    citation_count: int = 0
    reference_count: int = 0
    references: List[str] = field(default_factory=list)  # 引用的论文 ID
    # 元数据
    fetched_at: Optional[datetime] = None
    raw: Optional[dict] = None  # 原始数据


@dataclass
class SearchResult:
    """检索结果"""
    papers: List[Paper]
    total: int
    page: int
    page_size: int
    has_next: bool
    source: str
```

### 5.3 arXiv 适配器

```python
# backend/integration/academic/arxiv_adapter.py
"""arXiv API 适配器"""
import logging
import httpx
from datetime import datetime
from typing import List, Optional
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)


class ArxivAdapter:
    """arXiv API 适配器

    arXiv 提供 Atom XML 格式的 API。
    API 文档: https://info.arxiv.org/help/api/index.html
    """

    BASE_URL = "http://export.arxiv.org/api/query"
    NAMESPACE = {"atom": "http://www.w3.org/2005/Atom"}

    def __init__(self):
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={"User-Agent": "ThesisMiner/8.0"},
        )

    async def search(
        self,
        query: str,
        start: int = 0,
        max_results: int = 20,
        sort_by: str = "relevance",
        sort_order: str = "descending",
    ) -> SearchResult:
        """搜索论文"""
        params = {
            "search_query": query,
            "start": start,
            "max_results": max_results,
            "sortBy": sort_by,
            "sortOrder": sort_order,
        }
        response = await self._client.get(self.BASE_URL, params=params)
        response.raise_for_status()

        papers, total = self._parse_response(response.text)
        return SearchResult(
            papers=papers,
            total=total,
            page=start // max_results if max_results > 0 else 0,
            page_size=max_results,
            has_next=(start + max_results) < total,
            source="arxiv",
        )

    async def get_paper(self, arxiv_id: str) -> Optional[Paper]:
        """获取单篇论文"""
        params = {"id_list": arxiv_id}
        response = await self._client.get(self.BASE_URL, params=params)
        response.raise_for_status()
        papers, _ = self._parse_response(response.text)
        return papers[0] if papers else None

    def _parse_response(self, xml_text: str) -> tuple:
        """解析 arXiv API 响应"""
        root = ET.fromstring(xml_text)
        total = int(root.find("{http://a9.com/-/spec/opensearch/1.1/}total").text)

        papers = []
        for entry in root.findall("atom:entry", self.NAMESPACE):
            paper = self._parse_entry(entry)
            papers.append(paper)

        return papers, total

    def _parse_entry(self, entry) -> Paper:
        """解析单条论文"""
        ns = self.NAMESPACE

        arxiv_id = entry.find("atom:id", ns).text.split("/")[-1]
        title = entry.find("atom:title", ns).text.strip()
        summary = entry.find("atom:summary", ns).text.strip()

        authors = []
        for author_elem in entry.findall("atom:author", ns):
            name_elem = author_elem.find("atom:name", ns)
            if name_elem is not None:
                authors.append(Author(name=name_elem.text))

        published = entry.find("atom:published", ns)
        published_date = None
        year = None
        if published is not None:
            published_date = datetime.fromisoformat(
                published.text.replace("Z", "+00:00")
            )
            year = published_date.year

        pdf_url = None
        for link in entry.findall("atom:link", ns):
            if link.get("title") == "pdf":
                pdf_url = link.get("href")

        categories = []
        for category in entry.findall("{http://arxiv.org/schemas/atom}primary_category"):
            categories.append(category.get("term"))

        return Paper(
            id=f"arxiv:{arxiv_id}",
            source="arxiv",
            source_id=arxiv_id,
            title=title,
            authors=authors,
            abstract=summary,
            arxiv_id=arxiv_id,
            year=year,
            published_date=published_date,
            url=entry.find("atom:id", ns).text,
            pdf_url=pdf_url,
            categories=categories,
            fetched_at=datetime.utcnow(),
        )

    async def close(self):
        await self._client.aclose()
```

### 5.4 Semantic Scholar 适配器

```python
# backend/integration/academic/semantic_scholar_adapter.py
"""Semantic Scholar API 适配器"""
import logging
import httpx
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


class SemanticScholarAdapter:
    """Semantic Scholar API 适配器

    API 文档: https://api.semanticscholar.org/
    """

    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, api_key: Optional[str] = None):
        headers = {"User-Agent": "ThesisMiner/8.0"}
        if api_key:
            headers["x-api-key"] = api_key
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers=headers,
        )

    async def search(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
        fields: str = "title,authors,abstract,year,doi,citationCount,externalIds",
    ) -> SearchResult:
        """搜索论文"""
        params = {
            "query": query,
            "limit": min(limit, 100),
            "offset": offset,
            "fields": fields,
        }
        response = await self._client.get("/paper/search", params=params)
        response.raise_for_status()
        data = response.json()

        papers = [self._parse_paper(p) for p in data.get("data", [])]
        total = data.get("total", 0)

        return SearchResult(
            papers=papers,
            total=total,
            page=offset // limit if limit > 0 else 0,
            page_size=limit,
            has_next=(offset + limit) < total,
            source="semantic_scholar",
        )

    async def get_paper(self, paper_id: str) -> Optional[Paper]:
        """获取单篇论文"""
        response = await self._client.get(
            f"/paper/{paper_id}",
            params={"fields": "title,authors,abstract,year,doi,citationCount,externalIds,references,citations"},
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return self._parse_paper(response.json())

    async def get_references(self, paper_id: str) -> List[Paper]:
        """获取引用的论文"""
        response = await self._client.get(
            f"/paper/{paper_id}/references",
            params={"fields": "title,authors,year,doi"},
        )
        response.raise_for_status()
        data = response.json()
        return [
            self._parse_paper(ref.get("citedPaper", {}))
            for ref in data.get("data", [])
        ]

    async def get_citations(self, paper_id: str) -> List[Paper]:
        """获取被引用的论文"""
        response = await self._client.get(
            f"/paper/{paper_id}/citations",
            params={"fields": "title,authors,year,doi"},
        )
        response.raise_for_status()
        data = response.json()
        return [
            self._parse_paper(cite.get("citingPaper", {}))
            for cite in data.get("data", [])
        ]

    def _parse_paper(self, data: dict) -> Paper:
        """解析论文数据"""
        authors = [
            Author(name=a.get("name", ""))
            for a in data.get("authors", [])
        ]
        external_ids = data.get("externalIds", {})
        return Paper(
            id=f"ss:{data.get('paperId', '')}",
            source="semantic_scholar",
            source_id=data.get("paperId", ""),
            title=data.get("title", ""),
            authors=authors,
            abstract=data.get("abstract"),
            doi=external_ids.get("DOI"),
            arxiv_id=external_ids.get("ArXiv"),
            year=data.get("year"),
            citation_count=data.get("citationCount", 0),
            fetched_at=datetime.utcnow(),
            raw=data,
        )

    async def close(self):
        await self._client.aclose()
```

### 5.5 CrossRef 适配器

```python
# backend/integration/academic/crossref_adapter.py
"""CrossRef API 适配器"""
import logging
import httpx
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class CrossRefAdapter:
    """CrossRef API 适配器

    CrossRef 提供 DOI 解析与元数据查询。
    使用 Polite Pool 需提供联系邮箱。
    API 文档: https://api.crossref.org
    """

    BASE_URL = "https://api.crossref.org"

    def __init__(self, mailto: str = "admin@thesisminer.local"):
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={
                "User-Agent": f"ThesisMiner/8.0 (mailto:{mailto})",
            },
        )

    async def search(self, query: str, rows: int = 20, offset: int = 0) -> SearchResult:
        """搜索论文"""
        params = {
            "query": query,
            "rows": min(rows, 100),
            "offset": offset,
        }
        response = await self._client.get("/works", params=params)
        response.raise_for_status()
        data = response.json()["message"]

        papers = [self._parse_work(item) for item in data.get("items", [])]
        total = data.get("total-results", 0)

        return SearchResult(
            papers=papers,
            total=total,
            page=offset // rows if rows > 0 else 0,
            page_size=rows,
            has_next=(offset + rows) < total,
            source="crossref",
        )

    async def get_by_doi(self, doi: str) -> Optional[Paper]:
        """通过 DOI 获取论文"""
        response = await self._client.get(f"/works/{doi}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()["message"]
        return self._parse_work(data)

    def _parse_work(self, item: dict) -> Paper:
        """解析 CrossRef Work 数据"""
        authors = []
        for author in item.get("author", []):
            name = f"{author.get('given', '')} {author.get('family', '')}".strip()
            authors.append(Author(
                name=name,
                affiliation=author.get("affiliation", [{}])[0].get("name") if author.get("affiliation") else None,
                orcid=author.get("ORCID"),
            ))

        date_parts = item.get("published-print", item.get("published-online", {})).get("date-parts", [[None]])[0]
        year = date_parts[0] if date_parts else None

        return Paper(
            id=f"crossref:{item.get('DOI', '')}",
            source="crossref",
            source_id=item.get("DOI", ""),
            title=item.get("title", [""])[0] if item.get("title") else "",
            authors=authors,
            abstract=item.get("abstract"),
            doi=item.get("DOI"),
            journal=item.get("container-title", [""])[0] if item.get("container-title") else None,
            volume=item.get("volume"),
            issue=item.get("issue"),
            pages=item.get("page"),
            year=year,
            url=item.get("URL"),
            fetched_at=datetime.utcnow(),
            raw=item,
        )

    async def close(self):
        await self._client.aclose()
```

### 5.6 多源聚合检索

```python
# backend/integration/academic/aggregator.py
"""多源聚合检索"""
import asyncio
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class AcademicSearchAggregator:
    """多源聚合检索器

    并行查询多个学术数据库，聚合去重后返回。
    """

    def __init__(self, adapters: dict):
        """adapters: {"arxiv": ArxivAdapter(), "ss": SemanticScholarAdapter(), ...}"""
        self.adapters = adapters

    async def search_all(
        self,
        query: str,
        max_per_source: int = 10,
    ) -> SearchResult:
        """并行搜索所有源"""
        tasks = []
        for name, adapter in self.adapters.items():
            task = self._safe_search(name, adapter, query, max_per_source)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_papers = []
        total = 0
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"搜索失败: {result}")
                continue
            all_papers.extend(result.papers)
            total += result.total

        # 去重 (按 DOI 或标题)
        deduplicated = self._deduplicate(all_papers)

        return SearchResult(
            papers=deduplicated,
            total=total,
            page=0,
            page_size=len(deduplicated),
            has_next=False,
            source="aggregated",
        )

    async def _safe_search(self, name, adapter, query, max_results):
        """安全搜索（捕获异常）"""
        try:
            return await adapter.search(query, max_results=max_results)
        except Exception as e:
            logger.error(f"源 {name} 搜索失败: {e}")
            raise

    def _deduplicate(self, papers: List[Paper]) -> List[Paper]:
        """去重"""
        seen = set()
        unique = []
        for paper in papers:
            # 优先用 DOI 去重
            key = paper.doi or paper.title.lower().strip()
            if key and key not in seen:
                seen.add(key)
                unique.append(paper)
        return unique
```

---

## 6. 引文管理工具集成

### 6.1 引文管理集成架构

```
┌─────────────────────────────────────────────────────────────────┐
│  引文管理工具集成                                                 │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  统一引文接口                                                │   │
│  │  - export(papers, format) → bytes                          │   │
│  │  - import(data, format) → List[Paper]                     │   │
│  └──────────────────────────────────────────────────────────┘   │
│         │            │            │            │                 │
│  ┌──────▼──────┐ ┌───▼─────┐ ┌───▼─────┐ ┌───▼─────┐          │
│  │ BibTeX      │ │ RIS     │ │ Zotero  │ │ EndNote │          │
│  │ Adapter     │ │ Adapter │ │ API     │ │ XML     │          │
│  └─────────────┘ └─────────┘ └─────────┘ └─────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 BibTeX 集成

```python
# backend/integration/citation/bibtex_adapter.py
"""BibTeX 格式集成"""
import logging
import re
from typing import List

logger = logging.getLogger(__name__)


class BibtexAdapter:
    """BibTeX 格式适配器"""

    def export(self, papers: List[Paper]) -> str:
        """导出为 BibTeX 格式"""
        entries = []
        for paper in papers:
            entry = self._paper_to_bibtex(paper)
            entries.append(entry)
        return "\n\n".join(entries)

    def import_data(self, bibtex_text: str) -> List[Paper]:
        """从 BibTeX 导入"""
        papers = []
        # 解析 BibTeX 条目
        pattern = r"@(\w+)\s*\{\s*([^,]+),\s*(.*?)\n\}"
        matches = re.findall(pattern, bibtex_text, re.DOTALL)

        for entry_type, cite_key, fields_text in matches:
            paper = self._parse_bibtex_entry(entry_type, cite_key, fields_text)
            if paper:
                papers.append(paper)

        return papers

    def _paper_to_bibtex(self, paper: Paper) -> str:
        """论文转 BibTeX"""
        cite_key = self._generate_cite_key(paper)
        entry_type = self._get_entry_type(paper)

        fields = []
        if paper.authors:
            author_str = " and ".join(a.name for a in paper.authors)
            fields.append(f"  author = {{{author_str}}}")
        if paper.title:
            fields.append(f"  title = {{{{{paper.title}}}}}")
        if paper.journal:
            fields.append(f"  journal = {{{paper.journal}}}")
        if paper.volume:
            fields.append(f"  volume = {{{paper.volume}}}")
        if paper.issue:
            fields.append(f"  number = {{{paper.issue}}}")
        if paper.pages:
            fields.append(f"  pages = {{{paper.pages}}}")
        if paper.year:
            fields.append(f"  year = {{{paper.year}}}")
        if paper.doi:
            fields.append(f"  doi = {{{paper.doi}}}")
        if paper.url:
            fields.append(f"  url = {{{paper.url}}}")

        fields_str = ",\n".join(fields)
        return f"@{entry_type}{{{cite_key},\n{fields_str}\n}}"

    def _generate_cite_key(self, paper: Paper) -> str:
        """生成引用键"""
        first_author = paper.authors[0] if paper.authors else None
        last_name = first_author.name.split()[-1].lower() if first_author else "unknown"
        year = paper.year or "nd"
        title_word = paper.title.split()[0].lower() if paper.title else "untitled"
        return f"{last_name}{year}{title_word}"

    def _get_entry_type(self, paper: Paper) -> str:
        """获取 BibTeX 条目类型"""
        if paper.journal:
            return "article"
        if paper.arxiv_id:
            return "misc"
        return "article"

    def _parse_bibtex_entry(self, entry_type, cite_key, fields_text) -> Paper:
        """解析 BibTeX 条目"""
        fields = {}
        field_pattern = r"(\w+)\s*=\s*[\{\"](.*?)[\}\"]"
        for match in re.finditer(field_pattern, fields_text, re.DOTALL):
            key, value = match.group(1).lower(), match.group(2).strip()
            fields[key] = value

        authors = [
            Author(name=name.strip())
            for name in fields.get("author", "").split(" and ")
            if name.strip()
        ]

        return Paper(
            id=f"bibtex:{cite_key}",
            source="bibtex",
            source_id=cite_key,
            title=fields.get("title", ""),
            authors=authors,
            abstract=fields.get("abstract"),
            doi=fields.get("doi"),
            journal=fields.get("journal"),
            volume=fields.get("volume"),
            issue=fields.get("number"),
            pages=fields.get("pages"),
            year=int(fields["year"]) if fields.get("year", "").isdigit() else None,
            url=fields.get("url"),
        )
```

### 6.3 RIS 格式集成

```python
# backend/integration/citation/ris_adapter.py
"""RIS 格式集成"""
import logging
from typing import List

logger = logging.getLogger(__name__)


class RisAdapter:
    """RIS 格式适配器"""

    # RIS 字段映射
    FIELD_MAP = {
        "TY": "type",
        "TI": "title",
        "AU": "author",
        "AB": "abstract",
        "JO": "journal",
        "VL": "volume",
        "IS": "issue",
        "SP": "pages",
        "PY": "year",
        "DO": "doi",
        "UR": "url",
        "KW": "keywords",
    }

    def export(self, papers: List[Paper]) -> str:
        """导出为 RIS 格式"""
        entries = []
        for paper in papers:
            entry = self._paper_to_ris(paper)
            entries.append(entry)
        return "\n\n".join(entries)

    def import_data(self, ris_text: str) -> List[Paper]:
        """从 RIS 导入"""
        papers = []
        current_entry = {}
        current_field = None

        for line in ris_text.split("\n"):
            line = line.strip()
            if len(line) < 6 or line[2] != " " or line[3] != "-":
                if current_field and current_field in current_entry:
                    continue
                continue

            field = line[:2]
            value = line[4:].strip()

            if field == "TY":
                current_entry = {"type": value}
            elif field == "ER":
                if current_entry:
                    paper = self._parse_ris_entry(current_entry)
                    papers.append(paper)
                current_entry = {}
            else:
                field_name = self.FIELD_MAP.get(field, field.lower())
                if field_name in current_entry:
                    if isinstance(current_entry[field_name], list):
                        current_entry[field_name].append(value)
                    else:
                        current_entry[field_name] = [current_entry[field_name], value]
                else:
                    current_entry[field_name] = value

        return papers

    def _paper_to_ris(self, paper: Paper) -> str:
        """论文转 RIS"""
        lines = ["TY  - JOUR"]
        if paper.title:
            lines.append(f"TI  - {paper.title}")
        for author in paper.authors:
            lines.append(f"AU  - {author.name}")
        if paper.abstract:
            lines.append(f"AB  - {paper.abstract}")
        if paper.journal:
            lines.append(f"JO  - {paper.journal}")
        if paper.volume:
            lines.append(f"VL  - {paper.volume}")
        if paper.issue:
            lines.append(f"IS  - {paper.issue}")
        if paper.pages:
            lines.append(f"SP  - {paper.pages}")
        if paper.year:
            lines.append(f"PY  - {paper.year}")
        if paper.doi:
            lines.append(f"DO  - {paper.doi}")
        if paper.url:
            lines.append(f"UR  - {paper.url}")
        for kw in paper.keywords:
            lines.append(f"KW  - {kw}")
        lines.append("ER  - ")
        return "\n".join(lines)

    def _parse_ris_entry(self, entry: dict) -> Paper:
        """解析 RIS 条目"""
        authors = []
        author_data = entry.get("author", [])
        if isinstance(author_data, str):
            author_data = [author_data]
        for name in author_data:
            authors.append(Author(name=name))

        year = None
        if "year" in entry and str(entry["year"]).isdigit():
            year = int(entry["year"])

        keywords = entry.get("keywords", [])
        if isinstance(keywords, str):
            keywords = [keywords]

        return Paper(
            id=f"ris:{entry.get('title', 'unknown')[:20]}",
            source="ris",
            source_id=entry.get("title", ""),
            title=entry.get("title", ""),
            authors=authors,
            abstract=entry.get("abstract"),
            doi=entry.get("doi"),
            journal=entry.get("journal"),
            volume=entry.get("volume"),
            issue=entry.get("issue"),
            pages=entry.get("pages"),
            year=year,
            url=entry.get("url"),
            keywords=keywords,
        )
```

### 6.4 Zotero API 集成

```python
# backend/integration/citation/zotero_adapter.py
"""Zotero API 集成"""
import logging
import httpx
from typing import List, Optional

logger = logging.getLogger(__name__)


class ZoteroAdapter:
    """Zotero API 适配器

    API 文档: https://www.zotero.org/support/dev/web_api/v3
    """

    BASE_URL = "https://api.zotero.org"

    def __init__(self, api_key: str, user_id: str):
        self.api_key = api_key
        self.user_id = user_id
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={
                "Zotero-API-Key": api_key,
                "Zotero-API-Version": "3",
            },
        )

    async def list_collections(self) -> List[dict]:
        """列出文献集合"""
        response = await self._client.get(f"/users/{self.user_id}/collections")
        response.raise_for_status()
        return response.json()

    async def list_items(self, collection_id: Optional[str] = None, limit: int = 50) -> List[Paper]:
        """列出文献条目"""
        url = f"/users/{self.user_id}/items"
        if collection_id:
            url = f"/users/{self.user_id}/collections/{collection_id}/items"
        params = {"limit": min(limit, 100), "itemType": "-attachment"}
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return [self._parse_zotero_item(item) for item in data]

    async def create_item(self, paper: Paper, collection_id: Optional[str] = None) -> dict:
        """创建文献条目"""
        item = self._paper_to_zotero(paper, collection_id)
        response = await self._client.post(
            f"/users/{self.user_id}/items",
            json=[item],
        )
        response.raise_for_status()
        return response.json()

    def _parse_zotero_item(self, item: dict) -> Paper:
        """解析 Zotero 条目"""
        data = item.get("data", {})
        creators = data.get("creators", [])
        authors = [
            Author(name=f"{c.get('firstName', '')} {c.get('lastName', '')}".strip())
            for c in creators
            if c.get("creatorType") == "author"
        ]
        return Paper(
            id=f"zotero:{item.get('key', '')}",
            source="zotero",
            source_id=item.get("key", ""),
            title=data.get("title", ""),
            authors=authors,
            abstract=data.get("abstractNote"),
            doi=data.get("DOI"),
            journal=data.get("publicationTitle"),
            volume=data.get("volume"),
            issue=data.get("issue"),
            pages=data.get("pages"),
            year=int(data["date"][:4]) if data.get("date", "")[:4].isdigit() else None,
            url=data.get("url"),
            fetched_at=datetime.utcnow(),
            raw=item,
        )

    def _paper_to_zotero(self, paper: Paper, collection_id: Optional[str] = None) -> dict:
        """论文转 Zotero 格式"""
        creators = [
            {
                "creatorType": "author",
                "firstName": " ".join(a.name.split()[:-1]),
                "lastName": a.name.split()[-1] if a.name.split() else "",
            }
            for a in paper.authors
        ]
        item = {
            "itemType": "journalArticle",
            "title": paper.title,
            "creators": creators,
            "abstractNote": paper.abstract or "",
            "publicationTitle": paper.journal or "",
            "volume": paper.volume or "",
            "issue": paper.issue or "",
            "pages": paper.pages or "",
            "date": str(paper.year) if paper.year else "",
            "DOI": paper.doi or "",
            "url": paper.url or "",
        }
        if collection_id:
            item["collections"] = [collection_id]
        return item

    async def close(self):
        await self._client.aclose()
```

---

## 7. API 集成模式

### 7.1 集成模式对比

| 模式 | 同步性 | 延迟 | 复杂度 | 适用场景 |
|------|--------|------|--------|---------|
| 同步调用 | 同步 | 低 | 低 | 实时查询 |
| 异步回调 | 异步 | 高 | 中 | 耗时操作 |
| 流式传输 | 流式 | 实时 | 中 | LLM 输出 |
| 批处理 | 异步 | 高 | 中 | 批量操作 |
| 事件驱动 | 异步 | 中 | 高 | 解耦通知 |
| 轮询 | 异步 | 高 | 低 | 数据同步 |

### 7.2 同步调用模式

```python
# backend/integration/patterns/synchronous.py
"""同步调用模式"""
import logging
from typing import TypeVar, Callable, Awaitable

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


class SynchronousIntegration:
    """同步集成模式

    请求-响应模式，调用方等待响应。
    适用于低延迟、实时性要求高的场景。
    """

    async def call(
        self,
        func: Callable[..., Awaitable[R]],
        *args,
        timeout: float = 30.0,
        **kwargs,
    ) -> R:
        """同步调用"""
        import asyncio
        result = await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
        return result
```

### 7.3 异步回调模式

```python
# backend/integration/patterns/asynchronous.py
"""异步回调模式"""
import logging
import uuid
from typing import Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AsyncJob:
    """异步任务"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.PENDING
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    callback_url: Optional[str] = None


class AsynchronousIntegration:
    """异步集成模式

    提交任务后返回任务 ID，通过回调或轮询获取结果。
    适用于耗时操作。
    """

    def __init__(self):
        self._jobs: dict = {}

    async def submit(
        self,
        func: Callable,
        *args,
        callback_url: Optional[str] = None,
        **kwargs,
    ) -> str:
        """提交异步任务"""
        job = AsyncJob(callback_url=callback_url)
        self._jobs[job.id] = job

        # 异步执行
        import asyncio
        asyncio.create_task(self._execute(job, func, *args, **kwargs))

        return job.id

    async def _execute(self, job: AsyncJob, func, *args, **kwargs):
        """执行任务"""
        job.status = JobStatus.PROCESSING
        try:
            result = await func(*args, **kwargs)
            job.result = result
            job.status = JobStatus.COMPLETED
        except Exception as e:
            job.error = str(e)
            job.status = JobStatus.FAILED
            logger.error(f"异步任务失败 {job.id}: {e}")
        finally:
            job.completed_at = datetime.utcnow()

        # 回调通知
        if job.callback_url:
            await self._notify_callback(job)

    async def _notify_callback(self, job: AsyncJob):
        """回调通知"""
        import httpx
        payload = {
            "job_id": job.id,
            "status": job.status.value,
            "result": job.result,
            "error": job.error,
        }
        try:
            async with httpx.AsyncClient() as client:
                await client.post(job.callback_url, json=payload, timeout=10.0)
        except Exception as e:
            logger.error(f"回调通知失败 {job.id}: {e}")

    async def get_status(self, job_id: str) -> Optional[dict]:
        """查询任务状态"""
        job = self._jobs.get(job_id)
        if job is None:
            return None
        return {
            "id": job.id,
            "status": job.status.value,
            "result": job.result,
            "error": job.error,
        }
```

### 7.4 流式传输模式

```python
# backend/integration/patterns/streaming.py
"""流式传输模式"""
import logging
import asyncio
from typing import AsyncIterator, Callable, Awaitable

logger = logging.getLogger(__name__)


class StreamingIntegration:
    """流式集成模式

    使用 Server-Sent Events (SSE) 实时传输数据。
    适用于 LLM 流式输出、实时日志等。
    """

    async def stream(
        self,
        source: Callable[..., AsyncIterator[str]],
        *args,
        **kwargs,
    ) -> AsyncIterator[str]:
        """流式传输"""
        async for chunk in source(*args, **kwargs):
            yield chunk

    async def stream_to_sse(
        self,
        source: Callable[..., AsyncIterator[str]],
        *args,
        **kwargs,
    ) -> AsyncIterator[str]:
        """转换为 SSE 格式"""
        async for chunk in source(*args, **kwargs):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"
```

### 7.5 批处理模式

```python
# backend/integration/patterns/batch.py
"""批处理模式"""
import asyncio
import logging
from typing import List, Callable, Awaitable, TypeVar, Any

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


class BatchIntegration:
    """批处理集成模式

    将多个请求合并为批量请求，减少网络开销。
    """

    def __init__(self, batch_size: int = 50, max_concurrency: int = 5):
        self.batch_size = batch_size
        self.max_concurrency = max_concurrency

    async def batch_process(
        self,
        items: List[T],
        processor: Callable[[List[T]], Awaitable[List[R]]],
    ) -> List[R]:
        """批处理"""
        # 分批
        batches = [
            items[i:i + self.batch_size]
            for i in range(0, len(items), self.batch_size)
        ]

        # 并发处理
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def process_batch(batch):
            async with semaphore:
                return await processor(batch)

        results = await asyncio.gather(
            *[process_batch(b) for b in batches]
        )

        # 合并结果
        all_results = []
        for batch_result in results:
            all_results.extend(batch_result)
        return all_results
```

---

## 8. 数据同步与 ETL

### 8.1 ETL 架构

```
┌─────────────────────────────────────────────────────────────────┐
│  ETL 架构                                                        │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Extract (抽取)                                             │   │
│  │  - 从外部数据源获取数据                                       │   │
│  │  - 增量/全量抽取                                             │   │
│  │  - 数据源: arXiv / Semantic Scholar / CrossRef              │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              ↓                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Transform (转换)                                           │   │
│  │  - 数据清洗                                                  │   │
│  │  - 格式标准化                                                │   │
│  │  - 字段映射                                                  │   │
│  │  - 去重                                                      │   │
│  │  - 富化 (补充缺失字段)                                       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              ↓                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Load (加载)                                                │   │
│  │  - 写入本地数据库                                            │   │
│  │  - 更新索引                                                  │   │
│  │  - 缓存预热                                                  │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 ETL 实现

```python
# backend/integration/etl/pipeline.py
"""ETL 管道"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ETLConfig:
    """ETL 配置"""
    source: str                    # 数据源名称
    batch_size: int = 50           # 批量大小
    max_concurrency: int = 3       # 最大并发
    incremental: bool = True       # 增量同步
    retry_count: int = 3           # 重试次数
    retry_delay: float = 5.0       # 重试延迟


class ETLPipeline:
    """ETL 管道"""

    def __init__(self, config: ETLConfig):
        self.config = config
        self._stats = {
            "extracted": 0,
            "transformed": 0,
            "loaded": 0,
            "failed": 0,
            "skipped": 0,
        }

    async def run(
        self,
        extractor: Callable,
        transformer: Callable,
        loader: Callable,
        since: Optional[datetime] = None,
    ):
        """执行 ETL"""
        logger.info(f"ETL 开始: source={self.config.source}")

        # Extract
        raw_data = await self._extract(extractor, since)

        # Transform
        transformed = await self._transform(transformer, raw_data)

        # Load
        await self._load(loader, transformed)

        logger.info(f"ETL 完成: {self._stats}")
        return self._stats

    async def _extract(self, extractor, since: Optional[datetime]) -> List:
        """抽取数据"""
        logger.info(f"抽取数据: since={since}")
        try:
            if self.config.incremental and since:
                data = await extractor(since=since)
            else:
                data = await extractor()
            self._stats["extracted"] = len(data)
            logger.info(f"抽取完成: {len(data)} 条")
            return data
        except Exception as e:
            logger.error(f"抽取失败: {e}")
            raise

    async def _transform(self, transformer, raw_data: List) -> List:
        """转换数据"""
        logger.info(f"转换数据: {len(raw_data)} 条")

        # 分批处理
        batches = [
            raw_data[i:i + self.config.batch_size]
            for i in range(0, len(raw_data), self.config.batch_size)
        ]

        semaphore = asyncio.Semaphore(self.config.max_concurrency)
        transformed_all = []

        async def process_batch(batch):
            async with semaphore:
                result = await transformer(batch)
                return result

        results = await asyncio.gather(
            *[process_batch(b) for b in batches],
            return_exceptions=True,
        )

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"转换失败: {result}")
                self._stats["failed"] += 1
            else:
                transformed_all.extend(result)
                self._stats["transformed"] += len(result)

        return transformed_all

    async def _load(self, loader, data: List):
        """加载数据"""
        logger.info(f"加载数据: {len(data)} 条")

        batches = [
            data[i:i + self.config.batch_size]
            for i in range(0, len(data), self.config.batch_size)
        ]

        for batch in batches:
            try:
                loaded = await loader(batch)
                self._stats["loaded"] += loaded
            except Exception as e:
                logger.error(f"加载失败: {e}")
                self._stats["failed"] += len(batch)
```

### 8.3 增量同步

```python
# backend/integration/etl/incremental_sync.py
"""增量同步"""
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class IncrementalSync:
    """增量同步管理器"""

    def __init__(self, state_store):
        self.state = state_store

    async def sync(
        self,
        source_name: str,
        extractor,
        transformer,
        loader,
    ):
        """执行增量同步"""
        # 获取上次同步时间
        last_sync = await self.state.get(f"sync:{source_name}:last_time")
        since = datetime.fromisoformat(last_sync) if last_sync else None

        logger.info(f"增量同步 {source_name}: since={since}")

        # 执行 ETL
        pipeline = ETLPipeline(ETLConfig(source=source_name, incremental=True))
        stats = await pipeline.run(extractor, transformer, loader, since=since)

        # 更新同步时间
        await self.state.set(
            f"sync:{source_name}:last_time",
            datetime.utcnow().isoformat(),
        )

        return stats

    async def full_resync(self, source_name: str, extractor, transformer, loader):
        """全量重新同步"""
        logger.info(f"全量重新同步 {source_name}")
        # 清除同步状态
        await self.state.delete(f"sync:{source_name}:last_time")
        # 执行全量同步
        pipeline = ETLPipeline(ETLConfig(source=source_name, incremental=False))
        return await pipeline.run(extractor, transformer, loader)
```

---

## 9. 认证集成

### 9.1 认证方式对比

| 认证方式 | 安全性 | 复杂度 | 适用场景 |
|---------|--------|--------|---------|
| API Key | 中 | 低 | 服务间调用 |
| Bearer Token | 中 | 低 | API 访问 |
| OAuth 2.0 | 高 | 高 | 第三方授权 |
| JWT | 高 | 中 | 无状态认证 |
| mTLS | 高 | 高 | 服务网格 |

### 9.2 API Key 认证

```python
# backend/integration/auth/api_key.py
"""API Key 认证"""
import hashlib
import secrets
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class APIKeyAuth:
    """API Key 认证管理"""

    @staticmethod
    def generate() -> str:
        """生成 API Key"""
        return f"tm_{secrets.token_urlsafe(32)}"

    @staticmethod
    def hash_key(key: str) -> str:
        """哈希 API Key"""
        return hashlib.sha256(key.encode()).hexdigest()

    @staticmethod
    def verify(key: str, stored_hash: str) -> bool:
        """验证 API Key"""
        return APIKeyAuth.hash_key(key) == stored_hash
```

### 9.3 OAuth 2.0 集成

```python
# backend/integration/auth/oauth.py
"""OAuth 2.0 集成"""
import logging
import httpx
from typing import Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class OAuthToken:
    """OAuth 令牌"""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600
    refresh_token: Optional[str] = None
    scope: Optional[str] = None
    obtained_at: datetime = None

    @property
    def is_expired(self) -> bool:
        if not self.obtained_at:
            return True
        return datetime.utcnow() > self.obtained_at + timedelta(seconds=self.expires_in - 60)


class OAuthClient:
    """OAuth 2.0 客户端"""

    def __init__(self, client_id: str, client_secret: str, token_url: str, authorize_url: str = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self.authorize_url = authorize_url
        self._token: Optional[OAuthToken] = None

    def get_authorize_url(self, redirect_uri: str, state: str, scope: str = "") -> str:
        """获取授权 URL"""
        from urllib.parse import urlencode
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": scope,
        }
        return f"{self.authorize_url}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> OAuthToken:
        """用授权码换取令牌"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
            response.raise_for_status()
            data = response.json()

        self._token = OAuthToken(
            access_token=data["access_token"],
            token_type=data.get("token_type", "Bearer"),
            expires_in=data.get("expires_in", 3600),
            refresh_token=data.get("refresh_token"),
            scope=data.get("scope"),
            obtained_at=datetime.utcnow(),
        )
        return self._token

    async def refresh_token(self) -> OAuthToken:
        """刷新令牌"""
        if not self._token or not self._token.refresh_token:
            raise ValueError("无刷新令牌")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self._token.refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
            response.raise_for_status()
            data = response.json()

        self._token = OAuthToken(
            access_token=data["access_token"],
            token_type=data.get("token_type", "Bearer"),
            expires_in=data.get("expires_in", 3600),
            refresh_token=data.get("refresh_token", self._token.refresh_token),
            scope=data.get("scope"),
            obtained_at=datetime.utcnow(),
        )
        return self._token

    async def get_valid_token(self) -> str:
        """获取有效令牌（自动刷新）"""
        if not self._token or self._token.is_expired:
            if self._token and self._token.refresh_token:
                await self.refresh_token()
            else:
                raise ValueError("无有效令牌，请重新授权")
        return self._token.access_token
```

---

## 10. 错误处理与重试

### 10.1 错误分类

| 错误类型 | HTTP 状态码 | 可重试 | 处理策略 |
|---------|------------|--------|---------|
| 客户端错误 | 400, 401, 403 | 否 | 修正请求 |
| 未找到 | 404 | 否 | 返回空结果 |
| 速率限制 | 429 | 是 | 退避重试 |
| 服务端错误 | 500, 502, 503 | 是 | 退避重试 |
| 网关超时 | 504 | 是 | 退避重试 |
| 网络错误 | - | 是 | 退避重试 |
| 超时 | - | 是 | 退避重试 |

### 10.2 重试策略

```python
# backend/integration/resilience/retry.py
"""重试策略"""
import asyncio
import logging
import random
from typing import Callable, Awaitable, TypeVar, Optional
from enum import Enum

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryStrategy(str, Enum):
    FIXED = "fixed"           # 固定间隔
    LINEAR = "linear"         # 线性退避
    EXPONENTIAL = "exponential"  # 指数退避
    JITTERED = "jittered"     # 带抖动的指数退避


class RetryPolicy:
    """重试策略"""

    def __init__(
        self,
        max_retries: int = 3,
        strategy: RetryStrategy = RetryStrategy.JITTERED,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        retryable_exceptions: tuple = (Exception,),
    ):
        self.max_retries = max_retries
        self.strategy = strategy
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.retryable_exceptions = retryable_exceptions

    def get_delay(self, attempt: int) -> float:
        """计算重试延迟"""
        if self.strategy == RetryStrategy.FIXED:
            delay = self.base_delay
        elif self.strategy == RetryStrategy.LINEAR:
            delay = self.base_delay * (attempt + 1)
        elif self.strategy == RetryStrategy.EXPONENTIAL:
            delay = self.base_delay * (2 ** attempt)
        elif self.strategy == RetryStrategy.JITTERED:
            delay = self.base_delay * (2 ** attempt)
            delay = delay * (0.5 + random.random() * 0.5)  # 50%-100% 抖动
        else:
            delay = self.base_delay

        return min(delay, self.max_delay)

    async def execute(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        """执行带重试的调用"""
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except self.retryable_exceptions as e:
                last_error = e
                if attempt < self.max_retries:
                    delay = self.get_delay(attempt)
                    logger.warning(
                        f"调用失败 (attempt {attempt + 1}/{self.max_retries + 1}): "
                        f"{e}, {delay:.1f}s 后重试"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"调用最终失败: {e}")
        raise last_error
```

### 10.3 熔断器

```python
# backend/integration/resilience/circuit_breaker.py
"""熔断器"""
import asyncio
import time
import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"      # 正常，允许调用
    OPEN = "open"          # 熔断，拒绝调用
    HALF_OPEN = "half_open"  # 半开，试探性调用


class CircuitBreaker:
    """熔断器

    状态转换:
    CLOSED → (失败率超阈值) → OPEN
    OPEN → (冷却时间到) → HALF_OPEN
    HALF_OPEN → (成功) → CLOSED
    HALF_OPEN → (失败) → OPEN
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 3,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0
        self._lock = asyncio.Lock()

    async def call(self, func, *args, **kwargs):
        """通过熔断器调用"""
        async with self._lock:
            if self._state == CircuitState.OPEN:
                if time.monotonic() - self._last_failure_time > self.recovery_timeout:
                    logger.info("熔断器进入半开状态")
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                else:
                    raise CircuitBreakerOpenError("熔断器开启中")

        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise

    async def _on_success(self):
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    logger.info("熔断器关闭（恢复正常）")
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    async def _on_failure(self):
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._state == CircuitState.HALF_OPEN:
                logger.warning("半开状态调用失败，熔断器重新开启")
                self._state = CircuitState.OPEN
            elif self._failure_count >= self.failure_threshold:
                logger.warning(f"失败次数达阈值 ({self._failure_count})，熔断器开启")
                self._state = CircuitState.OPEN

    @property
    def state(self) -> CircuitState:
        return self._state


class CircuitBreakerOpenError(Exception):
    pass
```

### 10.4 降级策略

```python
# backend/integration/resilience/fallback.py
"""降级策略"""
import logging
from typing import Optional, Callable, Awaitable, Any

logger = logging.getLogger(__name__)


class FallbackHandler:
    """降级处理器"""

    async def with_fallback(
        self,
        primary: Callable[..., Awaitable[Any]],
        fallback: Callable[..., Awaitable[Any]],
        *args,
        **kwargs,
    ) -> Any:
        """带降级的调用"""
        try:
            return await primary(*args, **kwargs)
        except Exception as e:
            logger.warning(f"主调用失败，使用降级: {e}")
            return await fallback(*args, **kwargs)

    async def with_cache_fallback(
        self,
        primary: Callable[..., Awaitable[Any]],
        cache_get: Callable[..., Awaitable[Any]],
        cache_set: Callable[..., Awaitable[Any]],
        cache_key: str,
        *args,
        **kwargs,
    ) -> Any:
        """带缓存降级的调用"""
        try:
            result = await primary(*args, **kwargs)
            # 成功则更新缓存
            await cache_set(cache_key, result)
            return result
        except Exception as e:
            # 失败则尝试缓存
            cached = await cache_get(cache_key)
            if cached is not None:
                logger.info(f"使用缓存降级: {cache_key}")
                return cached
            raise

    async def with_default_fallback(
        self,
        primary: Callable[..., Awaitable[Any]],
        default_value: Any,
        *args,
        **kwargs,
    ) -> Any:
        """带默认值降级的调用"""
        try:
            return await primary(*args, **kwargs)
        except Exception as e:
            logger.warning(f"主调用失败，使用默认值: {e}")
            return default_value
```

---

## 11. 集成测试

### 11.1 集成测试策略

| 测试类型 | 范围 | 工具 | 频率 |
|---------|------|------|------|
| 契约测试 | 接口契约 | Pact | 每次提交 |
| 集成测试 | 模块间集成 | pytest | 每次提交 |
| 端到端测试 | 完整流程 | pytest + httpx | 每日 |
| 负载测试 | 性能验证 | locust | 每周 |
| 混沌测试 | 故障注入 | chaos-mesh | 每月 |

### 11.2 集成测试实现

```python
# tests/integration/test_llm_integration.py
"""LLM 集成测试"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from backend.integration.llm.client import LLMClient, LLMRequest, LLMMessage
from backend.integration.llm.deepseek_adapter import DeepSeekAdapter


@pytest.fixture
def mock_httpx_client():
    """Mock httpx 客户端"""
    client = AsyncMock()
    return client


@pytest.fixture
def deepseek_adapter(mock_httpx_client):
    """DeepSeek 适配器（Mock）"""
    adapter = DeepSeekAdapter(api_key="test-key")
    adapter._client = mock_httpx_client
    return adapter


class TestDeepSeekAdapter:
    """DeepSeek 适配器测试"""

    @pytest.mark.asyncio
    async def test_chat_success(self, deepseek_adapter, mock_httpx_client):
        """测试对话成功"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello"}, "finish_reason": "stop"}],
            "model": "deepseek-chat",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_response.raise_for_status = MagicMock()
        mock_httpx_client.post.return_value = mock_response

        request = LLMRequest(
            messages=[LLMMessage(role="user", content="Hi")]
        )
        response = await deepseek_adapter.chat(request)

        assert response.content == "Hello"
        assert response.model == "deepseek-chat"
        assert response.usage["total_tokens"] == 15

    @pytest.mark.asyncio
    async def test_chat_with_cache_prefix(self, deepseek_adapter, mock_httpx_client):
        """测试带缓存前缀的对话"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "cached response"}}],
            "usage": {},
        }
        mock_response.raise_for_status = MagicMock()
        mock_httpx_client.post.return_value = mock_response

        request = LLMRequest(
            messages=[LLMMessage(role="user", content="Hi")],
            cache_prefix="system_prompt_hash",
        )
        await deepseek_adapter.chat(request)

        call_args = mock_httpx_client.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["cache_prefix"] == "system_prompt_hash"

    @pytest.mark.asyncio
    async def test_chat_stream(self, deepseek_adapter, mock_httpx_client):
        """测试流式对话"""
        async def mock_stream_lines():
            lines = [
                'data: {"choices":[{"delta":{"content":"Hello"}}]}',
                'data: {"choices":[{"delta":{"content":" World"}}]}',
                'data: [DONE]',
            ]
            for line in lines:
                yield line

        mock_stream_response = AsyncMock()
        mock_stream_response.aiter_lines = mock_stream_lines
        mock_stream_response.raise_for_status = MagicMock()

        mock_httpx_client.stream.return_value.__aenter__ = AsyncMock(
            return_value=mock_stream_response
        )
        mock_httpx_client.stream.return_value.__aexit__ = AsyncMock()

        request = LLMRequest(
            messages=[LLMMessage(role="user", content="Hi")],
            stream=True,
        )
        chunks = []
        async for chunk in deepseek_adapter.chat_stream(request):
            chunks.append(chunk)

        assert chunks == ["Hello", " World"]

    @pytest.mark.asyncio
    async def test_health_check(self, deepseek_adapter, mock_httpx_client):
        """测试健康检查"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_httpx_client.get.return_value = mock_response

        result = await deepseek_adapter.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, deepseek_adapter, mock_httpx_client):
        """测试健康检查失败"""
        mock_httpx_client.get.side_effect = Exception("Connection error")

        result = await deepseek_adapter.health_check()
        assert result is False


class TestLLMClient:
    """LLM 客户端测试"""

    @pytest.mark.asyncio
    async def test_failover(self):
        """测试故障切换"""
        primary = AsyncMock()
        primary.chat.side_effect = Exception("Primary failed")

        fallback = AsyncMock()
        fallback.chat.return_value = MagicMock(content="fallback response")

        client = LLMClient()
        client.register_adapter("primary", primary, is_primary=True)
        client.register_adapter("fallback", fallback)

        request = LLMRequest(messages=[LLMMessage(role="user", content="Hi")])
        response = await client.chat(request)

        assert response.content == "fallback response"
        primary.chat.assert_called_once()
        fallback.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_all_adapters_failed(self):
        """测试所有适配器失败"""
        adapter1 = AsyncMock()
        adapter1.chat.side_effect = Exception("Failed")

        adapter2 = AsyncMock()
        adapter2.chat.side_effect = Exception("Failed")

        client = LLMClient()
        client.register_adapter("adapter1", adapter1, is_primary=True)
        client.register_adapter("adapter2", adapter2)

        request = LLMRequest(messages=[LLMMessage(role="user", content="Hi")])
        with pytest.raises(LLMUnavailableError):
            await client.chat(request)
```

### 11.3 学术数据库集成测试

```python
# tests/integration/test_academic_integration.py
"""学术数据库集成测试"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.integration.academic.arxiv_adapter import ArxivAdapter
from backend.integration.academic.semantic_scholar_adapter import SemanticScholarAdapter
from backend.integration.academic.crossref_adapter import CrossRefAdapter
from backend.integration.academic.aggregator import AcademicSearchAggregator


ARXIV_SAMPLE_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <opensearch:totalResults xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">1</opensearch:totalResults>
  <entry>
    <id>http://arxiv.org/abs/2401.00001v1</id>
    <title>Sample Paper Title</title>
    <summary>This is a sample abstract.</summary>
    <author><name>Author One</name></author>
    <author><name>Author Two</name></author>
    <published>2024-01-15T00:00:00Z</published>
    <link href="http://arxiv.org/pdf/2401.00001v1" title="pdf" type="application/pdf"/>
    <arxiv:primary_category xmlns:arxiv="http://arxiv.org/schemas/atom" term="cs.AI"/>
  </entry>
</feed>"""


class TestArxivAdapter:
    """arXiv 适配器测试"""

    @pytest.mark.asyncio
    async def test_search(self):
        """测试搜索"""
        adapter = ArxivAdapter()
        mock_response = MagicMock()
        mock_response.text = ARXIV_SAMPLE_RESPONSE
        mock_response.raise_for_status = MagicMock()
        adapter._client.get = AsyncMock(return_value=mock_response)

        result = await adapter.search("machine learning", max_results=10)

        assert result.total == 1
        assert len(result.papers) == 1
        paper = result.papers[0]
        assert paper.title == "Sample Paper Title"
        assert paper.source == "arxiv"
        assert len(paper.authors) == 2
        assert paper.authors[0].name == "Author One"
        assert paper.year == 2024

    @pytest.mark.asyncio
    async def test_get_paper(self):
        """测试获取单篇论文"""
        adapter = ArxivAdapter()
        mock_response = MagicMock()
        mock_response.text = ARXIV_SAMPLE_RESPONSE
        mock_response.raise_for_status = MagicMock()
        adapter._client.get = AsyncMock(return_value=mock_response)

        paper = await adapter.get_paper("2401.00001")

        assert paper is not None
        assert paper.arxiv_id == "2401.00001v1"

    @pytest.mark.asyncio
    async def test_parse_empty_response(self):
        """测试空响应解析"""
        adapter = ArxivAdapter()
        empty_xml = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <opensearch:totalResults xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">0</opensearch:totalResults>
</feed>"""
        papers, total = adapter._parse_response(empty_xml)
        assert total == 0
        assert len(papers) == 0


class TestSemanticScholarAdapter:
    """Semantic Scholar 适配器测试"""

    @pytest.mark.asyncio
    async def test_search(self):
        """测试搜索"""
        adapter = SemanticScholarAdapter()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "total": 1,
            "data": [
                {
                    "paperId": "abc123",
                    "title": "Sample Paper",
                    "authors": [{"name": "Test Author"}],
                    "abstract": "Sample abstract",
                    "year": 2024,
                    "doi": "10.1000/test",
                    "citationCount": 5,
                    "externalIds": {"DOI": "10.1000/test", "ArXiv": "2401.00001"},
                }
            ],
        }
        mock_response.raise_for_status = MagicMock()
        adapter._client.get = AsyncMock(return_value=mock_response)

        result = await adapter.search("test query")

        assert result.total == 1
        assert len(result.papers) == 1
        paper = result.papers[0]
        assert paper.title == "Sample Paper"
        assert paper.doi == "10.1000/test"
        assert paper.citation_count == 5

    @pytest.mark.asyncio
    async def test_get_paper_not_found(self):
        """测试论文不存在"""
        adapter = SemanticScholarAdapter()
        mock_response = MagicMock()
        mock_response.status_code = 404
        adapter._client.get = AsyncMock(return_value=mock_response)

        paper = await adapter.get_paper("nonexistent")
        assert paper is None


class TestCrossRefAdapter:
    """CrossRef 适配器测试"""

    @pytest.mark.asyncio
    async def test_search(self):
        """测试搜索"""
        adapter = CrossRefAdapter()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {
                "total-results": 1,
                "items": [
                    {
                        "DOI": "10.1000/test",
                        "title": ["Test Paper"],
                        "author": [
                            {"given": "John", "family": "Doe", "ORCID": "0000-0001-0002-0003"}
                        ],
                        "container-title": ["Test Journal"],
                        "published-print": {"date-parts": [[2024, 1, 15]]},
                        "volume": "10",
                        "issue": "1",
                        "page": "1-10",
                    }
                ],
            }
        }
        mock_response.raise_for_status = MagicMock()
        adapter._client.get = AsyncMock(return_value=mock_response)

        result = await adapter.search("test")

        assert result.total == 1
        paper = result.papers[0]
        assert paper.doi == "10.1000/test"
        assert paper.title == "Test Paper"
        assert paper.authors[0].name == "John Doe"
        assert paper.authors[0].orcid == "0000-0001-0002-0003"
        assert paper.year == 2024

    @pytest.mark.asyncio
    async def test_get_by_doi(self):
        """测试 DOI 查询"""
        adapter = CrossRefAdapter()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {
                "DOI": "10.1000/test",
                "title": ["Test Paper"],
                "author": [],
            }
        }
        mock_response.raise_for_status = MagicMock()
        adapter._client.get = AsyncMock(return_value=mock_response)

        paper = await adapter.get_by_doi("10.1000/test")
        assert paper is not None
        assert paper.doi == "10.1000/test"


class TestAcademicSearchAggregator:
    """聚合检索测试"""

    @pytest.mark.asyncio
    async def test_aggregate_search(self):
        """测试聚合搜索"""
        from backend.integration.academic.models import SearchResult, Paper, Author

        adapter1 = AsyncMock()
        adapter1.search.return_value = SearchResult(
            papers=[
                Paper(id="1", source="arxiv", source_id="1", title="Paper A", doi="10.1/a", authors=[Author(name="A")]),
            ],
            total=1, page=0, page_size=1, has_next=False, source="arxiv",
        )

        adapter2 = AsyncMock()
        adapter2.search.return_value = SearchResult(
            papers=[
                Paper(id="2", source="ss", source_id="2", title="Paper B", doi="10.1/b", authors=[Author(name="B")]),
                # 重复 (同 DOI)
                Paper(id="3", source="ss", source_id="3", title="Paper A", doi="10.1/a", authors=[Author(name="A")]),
            ],
            total=2, page=0, page_size=2, has_next=False, source="ss",
        )

        aggregator = AcademicSearchAggregator({"arxiv": adapter1, "ss": adapter2})
        result = await aggregator.search_all("test")

        # 去重后应为 2 篇
        assert len(result.papers) == 2

    @pytest.mark.asyncio
    async def test_partial_failure(self):
        """测试部分源失败"""
        from backend.integration.academic.models import SearchResult, Paper

        adapter1 = AsyncMock()
        adapter1.search.return_value = SearchResult(
            papers=[Paper(id="1", source="arxiv", source_id="1", title="Paper A")],
            total=1, page=0, page_size=1, has_next=False, source="arxiv",
        )

        adapter2 = AsyncMock()
        adapter2.search.side_effect = Exception("Network error")

        aggregator = AcademicSearchAggregator({"arxiv": adapter1, "ss": adapter2})
        result = await aggregator.search_all("test")

        # 一个源失败，仍返回成功源的结果
        assert len(result.papers) == 1
```

---

## 12. Webhook 与事件集成

### 12.1 Webhook 架构

```
┌─────────────────────────────────────────────────────────────────┐
│  Webhook 架构                                                    │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  事件产生                                                   │   │
│  │  - 论文分析完成                                             │   │
│  │  - 导出完成                                                 │   │
│  │  - 任务状态变更                                             │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              ↓                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  事件分发                                                   │   │
│  │  - 查找订阅者                                               │   │
│  │  - 签名事件                                                 │   │
│  │  - HTTP POST 推送                                           │   │
│  │  - 重试失败                                                 │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              ↓                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  订阅者                                                     │   │
│  │  - 接收 Webhook                                             │   │
│  │  - 验证签名                                                 │   │
│  │  - 处理事件                                                 │   │
│  │  - 返回 200                                                 │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 12.2 Webhook 实现

```python
# backend/integration/webhook/manager.py
"""Webhook 管理器"""
import asyncio
import hashlib
import hmac
import json
import logging
import httpx
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class WebhookSubscription:
    """Webhook 订阅"""
    id: str
    url: str
    events: List[str]  # 订阅的事件类型
    secret: str        # 签名密钥
    active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class WebhookEvent:
    """Webhook 事件"""
    id: str
    event_type: str
    payload: dict
    timestamp: datetime = field(default_factory=datetime.utcnow)
    attempts: int = 0


class WebhookManager:
    """Webhook 管理器"""

    def __init__(self):
        self._subscriptions: dict = {}
        self._http_client = httpx.AsyncClient(timeout=30.0)

    async def register(self, subscription: WebhookSubscription):
        """注册订阅"""
        self._subscriptions[subscription.id] = subscription
        logger.info(f"Webhook 注册: {subscription.id} -> {subscription.url}")

    async def unregister(self, subscription_id: str):
        """取消注册"""
        self._subscriptions.pop(subscription_id, None)

    async def dispatch(self, event: WebhookEvent):
        """分发事件"""
        # 查找匹配的订阅
        subscribers = [
            sub for sub in self._subscriptions.values()
            if sub.active and event.event_type in sub.events
        ]

        tasks = [self._deliver(sub, event) for sub in subscribers]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _deliver(self, subscription: WebhookSubscription, event: WebhookEvent):
        """投递事件"""
        payload = {
            "id": event.id,
            "type": event.event_type,
            "timestamp": event.timestamp.isoformat(),
            "data": event.payload,
        }
        body = json.dumps(payload, ensure_ascii=False)

        # 签名
        signature = self._sign(body, subscription.secret)

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Event": event.event_type,
            "X-Webhook-Signature": signature,
            "X-Webhook-Id": event.id,
        }

        # 重试投递
        for attempt in range(3):
            try:
                response = await self._http_client.post(
                    subscription.url,
                    content=body,
                    headers=headers,
                )
                if response.status_code < 300:
                    logger.info(f"Webhook 投递成功: {subscription.id}")
                    return
                logger.warning(
                    f"Webhook 投递失败 (status={response.status_code}): "
                    f"{subscription.id}, attempt {attempt+1}"
                )
            except Exception as e:
                logger.warning(
                    f"Webhook 投递异常: {subscription.id}, attempt {attempt+1}: {e}"
                )
            await asyncio.sleep(2 ** attempt)

        logger.error(f"Webhook 投递最终失败: {subscription.id}")

    def _sign(self, body: str, secret: str) -> str:
        """签名"""
        return hmac.new(
            secret.encode(),
            body.encode(),
            hashlib.sha256,
        ).hexdigest()

    def verify_signature(self, body: str, signature: str, secret: str) -> bool:
        """验证签名"""
        expected = self._sign(body, secret)
        return hmac.compare_digest(expected, signature)

    async def close(self):
        await self._http_client.aclose()
```

---

## 13. 文件格式集成

### 13.1 支持的文件格式

| 格式 | 扩展名 | 用途 | 解析方式 |
|------|--------|------|---------|
| PDF | .pdf | 论文正文 | PyMuPDF / pdfplumber |
| LaTeX | .tex | 论文源码 | 正则 + 语法解析 |
| Word | .docx | 文档 | python-docx |
| Markdown | .md | 文档 | markdown |
| BibTeX | .bib | 引文 | bibtex-parser |
| RIS | .ris | 引文 | 自定义解析 |
| JSON | .json | 数据交换 | json |
| CSV | .csv | 表格数据 | csv |
| XML | .xml | 数据交换 | ElementTree |

### 13.2 文件解析器

```python
# backend/integration/file/parser.py
"""文件格式解析器"""
import logging
import io
from typing import Optional
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class FileParser(ABC):
    """文件解析器基类"""

    @abstractmethod
    async def parse(self, content: bytes, filename: str) -> dict:
        """解析文件内容"""
        pass


class PDFParser(FileParser):
    """PDF 解析器"""

    async def parse(self, content: bytes, filename: str) -> dict:
        """解析 PDF"""
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(stream=content, filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()

            return {
                "format": "pdf",
                "filename": filename,
                "text": text,
                "page_count": len(text.split("\f")),
                "metadata": {},
            }
        except ImportError:
            logger.error("PyMuPDF 未安装")
            raise
        except Exception as e:
            logger.error(f"PDF 解析失败: {e}")
            raise


class MarkdownParser(FileParser):
    """Markdown 解析器"""

    async def parse(self, content: bytes, filename: str) -> dict:
        """解析 Markdown"""
        text = content.decode("utf-8")
        return {
            "format": "markdown",
            "filename": filename,
            "text": text,
            "metadata": {},
        }


class FileParserRegistry:
    """文件解析器注册表"""

    def __init__(self):
        self._parsers: dict = {}

    def register(self, format: str, parser: FileParser):
        """注册解析器"""
        self._parsers[format] = parser

    def get_parser(self, filename: str) -> Optional[FileParser]:
        """获取解析器"""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        format_map = {
            "pdf": "pdf",
            "md": "markdown",
            "markdown": "markdown",
            "txt": "text",
            "tex": "latex",
            "docx": "word",
            "bib": "bibtex",
            "ris": "ris",
        }
        format_name = format_map.get(ext)
        return self._parsers.get(format_name)


# 全局注册表
registry = FileParserRegistry()
registry.register("pdf", PDFParser())
registry.register("markdown", MarkdownParser())
```

---

## 14. 消息协议设计

### 14.1 API 请求/响应协议

```python
# backend/integration/protocol/api_protocol.py
"""API 协议定义"""
from dataclasses import dataclass, field
from typing import Optional, Any, List
from datetime import datetime


@dataclass
class APIRequest:
    """统一 API 请求"""
    method: str
    path: str
    headers: dict = field(default_factory=dict)
    params: dict = field(default_factory=dict)
    body: Optional[Any] = None
    timeout: float = 30.0
    # 幂等性
    idempotency_key: Optional[str] = None
    # 追踪
    trace_id: Optional[str] = None


@dataclass
class APIResponse:
    """统一 API 响应"""
    status_code: int
    headers: dict = field(default_factory=dict)
    body: Optional[Any] = None
    elapsed: float = 0.0
    cached: bool = False
    retried: bool = False


@dataclass
class APIError:
    """统一 API 错误"""
    code: str
    message: str
    details: Optional[dict] = None
    retryable: bool = False
    status_code: Optional[int] = None
```

### 14.2 标准错误码

| 错误码 | 说明 | HTTP 状态码 | 可重试 |
|--------|------|------------|--------|
| RATE_LIMITED | 速率限制 | 429 | 是 |
| UNAUTHORIZED | 未授权 | 401 | 否 |
| FORBIDDEN | 禁止访问 | 403 | 否 |
| NOT_FOUND | 未找到 | 404 | 否 |
| VALIDATION_ERROR | 参数错误 | 400 | 否 |
| INTERNAL_ERROR | 内部错误 | 500 | 是 |
| SERVICE_UNAVAILABLE | 服务不可用 | 503 | 是 |
| GATEWAY_TIMEOUT | 网关超时 | 504 | 是 |
| NETWORK_ERROR | 网络错误 | - | 是 |
| TIMEOUT | 超时 | - | 是 |

---

## 15. 集成安全

### 15.1 安全措施

| 安全层面 | 措施 | 实现 |
|---------|------|------|
| 传输安全 | HTTPS/TLS | 全链路加密 |
| 认证 | API Key / OAuth | 密钥管理 |
| 授权 | RBAC | 权限控制 |
| 数据安全 | 加密存储 | AES-256 |
| 审计 | 日志记录 | 审计日志 |
| 防重放 | Nonce + Timestamp | 请求签名 |
| 限流 | 速率限制 | 令牌桶 |

### 15.2 请求签名

```python
# backend/integration/security/request_signer.py
"""请求签名"""
import hashlib
import hmac
import time
from typing import Optional


class RequestSigner:
    """请求签名器"""

    def __init__(self, secret: str):
        self.secret = secret

    def sign(
        self,
        method: str,
        path: str,
        body: str = "",
        timestamp: Optional[int] = None,
    ) -> dict:
        """生成签名"""
        ts = timestamp or int(time.time())
        # 签名内容: method + path + body + timestamp
        sign_content = f"{method.upper()}\n{path}\n{body}\n{ts}"
        signature = hmac.new(
            self.secret.encode(),
            sign_content.encode(),
            hashlib.sha256,
        ).hexdigest()

        return {
            "X-Timestamp": str(ts),
            "X-Signature": signature,
        }

    def verify(
        self,
        method: str,
        path: str,
        body: str,
        timestamp: int,
        signature: str,
        max_age: int = 300,
    ) -> bool:
        """验证签名"""
        # 检查时间戳（防重放）
        now = int(time.time())
        if abs(now - timestamp) > max_age:
            return False

        expected = self.sign(method, path, body, timestamp)["X-Signature"]
        return hmac.compare_digest(expected, signature)
```

---

## 16. 集成监控

### 16.1 集成监控指标

| 指标 | 类型 | 说明 | 告警阈值 |
|------|------|------|---------|
| integration_request_total | Counter | 集成请求总数 | - |
| integration_request_duration | Histogram | 请求耗时 P99 | > 10s |
| integration_error_total | Counter | 错误总数 | 错误率 > 5% |
| integration_retry_total | Counter | 重试次数 | 重试率 > 20% |
| integration_circuit_breaker | Gauge | 熔断器状态 | open |
| integration_rate_limit | Counter | 限流触发 | > 0 |
| integration_cache_hit | Counter | 缓存命中 | 命中率 < 50% |
| integration_active_connections | Gauge | 活跃连接 | > 最大 80% |

### 16.2 集成健康检查

```python
# backend/integration/monitoring/health.py
"""集成健康检查"""
import asyncio
import logging
from typing import dict

logger = logging.getLogger(__name__)


class IntegrationHealthChecker:
    """集成健康检查器"""

    def __init__(self):
        self._integrations: dict = {}

    def register(self, name: str, adapter):
        """注册集成"""
        self._integrations[name] = adapter

    async def check_all(self) -> dict:
        """检查所有集成"""
        results = {}
        tasks = [
            self._check_one(name, adapter)
            for name, adapter in self._integrations.items()
        ]
        checks = await asyncio.gather(*tasks, return_exceptions=True)

        for (name, _), result in zip(self._integrations.items(), checks):
            if isinstance(result, Exception):
                results[name] = {"healthy": False, "error": str(result)}
            else:
                results[name] = result

        return results

    async def _check_one(self, name: str, adapter) -> dict:
        """检查单个集成"""
        try:
            if hasattr(adapter, "health_check"):
                healthy = await adapter.health_check()
            else:
                healthy = True
            return {"healthy": healthy}
        except Exception as e:
            return {"healthy": False, "error": str(e)}
```

---

## 17. 集成版本管理

### 17.1 API 版本策略

| 策略 | 说明 | 优点 | 缺点 |
|------|------|------|------|
| URL 版本 | /v1/api | 清晰 | URL 变化 |
| Header 版本 | Accept: v2 | URL 不变 | 不直观 |
| 查询参数 | ?version=2 | 灵活 | 易遗漏 |

### 17.2 版本兼容性

```python
# backend/integration/versioning/compatibility.py
"""版本兼容性管理"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class VersionCompatibility:
    """版本兼容性管理"""

    # 支持的版本范围
    SUPPORTED_VERSIONS = ["v1", "v2"]

    @staticmethod
    def is_supported(version: str) -> bool:
        """检查版本是否支持"""
        return version in VersionCompatibility.SUPPORTED_VERSIONS

    @staticmethod
    def negotiate_version(requested: str) -> str:
        """版本协商"""
        if requested in VersionCompatibility.SUPPORTED_VERSIONS:
            return requested
        # 降级到最低支持版本
        logger.warning(f"不支持的版本 {requested}，降级到 v1")
        return "v1"
```

---

## 18. 集成性能优化

### 18.1 性能优化策略

| 策略 | 说明 | 效果 |
|------|------|------|
| 连接复用 | HTTP Keep-Alive | 减少连接开销 |
| 请求批处理 | 合并请求 | 减少网络往返 |
| 响应缓存 | 缓存结果 | 减少调用 |
| 并行调用 | 并发请求 | 降低延迟 |
| 压缩传输 | Gzip | 减少带宽 |
| 预取 | 提前加载 | 降低延迟 |
| 增量同步 | 只同步变化 | 减少数据量 |

### 18.2 连接复用

```python
# backend/integration/performance/connection_reuse.py
"""连接复用"""
import httpx
import logging

logger = logging.getLogger(__name__)


class ConnectionPool:
    """HTTP 连接池"""

    def __init__(self, max_connections: int = 100, max_keepalive: int = 20):
        self._client = httpx.AsyncClient(
            limits=httpx.Limits(
                max_connections=max_connections,
                max_keepalive_connections=max_keepalive,
                keepalive_expiry=30.0,
            ),
            timeout=httpx.Timeout(30.0, connect=5.0),
            http2=True,  # 启用 HTTP/2
        )

    async def request(self, method: str, url: str, **kwargs):
        """发送请求（复用连接）"""
        return await self._client.request(method, url, **kwargs)

    async def close(self):
        await self._client.aclose()
```

---

## 19. 集成故障排查

### 19.1 常见故障

| 故障 | 现象 | 排查步骤 |
|------|------|---------|
| 连接超时 | 请求无响应 | 1.检查网络 2.检查防火墙 3.检查 DNS |
| 认证失败 | 401/403 | 1.检查 API Key 2.检查权限 3.检查过期 |
| 速率限制 | 429 | 1.检查限流 2.降低频率 3.申请提额 |
| 数据格式错误 | 400 | 1.检查请求体 2.检查 Content-Type |
| 服务不可用 | 503 | 1.检查服务状态 2.重试 3.降级 |
| SSL 错误 | 证书错误 | 1.检查证书 2.检查时间 3.更新 CA |

### 19.2 调试工具

```python
# backend/integration/debug/proxy.py
"""集成调试代理"""
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)


class IntegrationDebugger:
    """集成调试器"""

    def __init__(self):
        self._logs: list = []

    def log_request(self, integration: str, method: str, url: str, headers: dict, body: Any = None):
        """记录请求"""
        entry = {
            "type": "request",
            "integration": integration,
            "timestamp": datetime.utcnow().isoformat(),
            "method": method,
            "url": url,
            "headers": {k: v for k, v in headers.items() if not k.lower().startswith("auth")},
            "body": body,
        }
        self._logs.append(entry)
        logger.debug(f"集成请求: {integration} {method} {url}")

    def log_response(self, integration: str, status_code: int, body: Any = None, elapsed: float = 0):
        """记录响应"""
        entry = {
            "type": "response",
            "integration": integration,
            "timestamp": datetime.utcnow().isoformat(),
            "status_code": status_code,
            "body": body,
            "elapsed": elapsed,
        }
        self._logs.append(entry)
        logger.debug(f"集成响应: {integration} {status_code} ({elapsed:.3f}s)")

    def get_logs(self, integration: Optional[str] = None) -> list:
        """获取日志"""
        if integration:
            return [l for l in self._logs if l.get("integration") == integration]
        return self._logs

    def clear(self):
        """清空日志"""
        self._logs.clear()
```

---

## 20. 附录

### 20.1 集成检查清单

```markdown
## 集成检查清单

### 接口设计
- [ ] 接口契约已定义
- [ ] 版本管理策略已确定
- [ ] 错误码已标准化
- [ ] 幂等性已保证

### 安全
- [ ] 认证机制已实现
- [ ] 传输加密已配置
- [ ] 密钥管理已就绪
- [ ] 请求签名已实现

### 弹性
- [ ] 重试策略已配置
- [ ] 熔断器已配置
- [ ] 限流已配置
- [ ] 降级策略已实现
- [ ] 超时已配置

### 监控
- [ ] 请求指标已采集
- [ ] 错误指标已采集
- [ ] 延迟指标已采集
- [ ] 告警规则已配置

### 测试
- [ ] 契约测试已编写
- [ ] 集成测试已编写
- [ ] 端到端测试已编写
- [ ] 故障测试已编写
```

### 20.2 外部 API 速查

| API | Base URL | 认证 | 限流 |
|-----|----------|------|------|
| DeepSeek | https://api.deepseek.com/v1 | Bearer Token | 60 req/min |
| OpenAI | https://api.openai.com/v1 | Bearer Token | 60 req/min |
| arXiv | http://export.arxiv.org/api/query | 无 | 1 req/3s |
| Semantic Scholar | https://api.semanticscholar.org/graph/v1 | API Key | 100 req/5min |
| CrossRef | https://api.crossref.org | Polite (mailto) | 50 req/s |
| Zotero | https://api.zotero.org | API Key | 100 req/hour |

### 20.3 参考文档

| 文档 | 说明 |
|------|------|
| [DeepSeek API](https://platform.deepseek.com/api-docs) | DeepSeek LLM API |
| [arXiv API](https://info.arxiv.org/help/api/index.html) | arXiv 检索 API |
| [Semantic Scholar API](https://api.semanticscholar.org/) | 学术论文 API |
| [CrossRef API](https://api.crossref.org) | DOI 解析 API |
| [Zotero API](https://www.zotero.org/support/dev/web_api/v3) | 文献管理 API |
| [OAuth 2.0](https://oauth.net/2/) | OAuth 协议 |

### 20.4 变更记录

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|---------|------|
| v8.0.0 | 2026-06-20 | 初始版本 | ThesisMiner Team |

---

**文档结束**
