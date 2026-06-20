# ThesisMiner v8.0 限流与配额管理文档

> **文档版本**：v8.0.0  
> **最后更新**：2026-06-19  
> **文档定位**：ThesisMiner API 限流策略、配额管理、分级限流、超限处理与监控告警的完整参考  
> **适用对象**：API 集成方、运维人员、管理员  

---

## 目录

- [1. 限流架构总览](#1-限流架构总览)
- [2. 限流策略](#2-限流策略)
- [3. 配额管理](#3-配额管理)
- [4. 分级限流](#4-分级限流)
- [5. 超限处理](#5-超限处理)
- [6. 客户端重试策略](#6-客户端重试策略)
- [7. 监控与告警](#7-监控与告警)
- [8. 配置参考](#8-配置参考)
- [9. 最佳实践](#9-最佳实践)
- [10. 常见问题](#10-常见问题)

---

## 1. 限流架构总览

ThesisMiner v8.0 采用多维度限流架构，从请求频率、Token 用量、AI 调用次数三个维度对 API 访问进行控制，确保系统稳定性和公平性。

```
┌─────────────────────────────────────────────────────────────────┐
│                  ThesisMiner 限流架构                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   请求入口层                              │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐              │   │
│  │  │ IP 限流  │  │ 用户限流 │  │ API Key  │              │   │
│  │  │          │  │          │  │ 限流     │              │   │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘              │   │
│  │       └─────────────┼─────────────┘                     │   │
│  │                     ▼                                     │   │
│  │            ┌──────────────┐                              │   │
│  │            │ 滑动窗口     │                              │   │
│  │            │ 限流器       │                              │   │
│  │            └──────┬───────┘                              │   │
│  └───────────────────┼─────────────────────────────────────┘   │
│                      │                                          │
│                      ▼                                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   业务限流层                              │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐              │   │
│  │  │ 会话限流 │  │ 模型限流 │  │ Agent    │              │   │
│  │  │          │  │          │  │ 限流     │              │   │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘              │   │
│  │       └─────────────┼─────────────┘                     │   │
│  │                     ▼                                     │   │
│  │            ┌──────────────┐                              │   │
│  │            │ 配额检查器   │                              │   │
│  │            └──────┬───────┘                              │   │
│  └───────────────────┼─────────────────────────────────────┘   │
│                      │                                          │
│                      ▼                                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   Token 预算层                            │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐              │   │
│  │  │ 日预算   │  │ 会话预算 │  │ 模型预算 │              │   │
│  │  │ 检查     │  │ 检查     │  │ 检查     │              │   │
│  │  └──────────┘  └──────────┘  └──────────┘              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**限流维度概览**：

| 维度 | 限流对象 | 默认限制 | 说明 |
|------|---------|---------|------|
| IP 限流 | 客户端 IP | 120 次/分钟 | 防止单 IP 滥用 |
| 用户限流 | 用户 ID | 60 次/分钟 | 防止单用户滥用 |
| API Key 限流 | API Key | 60 次/分钟 | 防止单 Key 滥用 |
| 会话限流 | 会话 ID | 30 次/分钟 | 防止单会话过载 |
| 模型限流 | 模型名称 | 30 次/小时 | 防止模型超载 |
| Agent 限流 | Agent 类型 | 20 次/分钟 | 防止 Agent 过载 |
| 日预算 | 用户 ID | $10/天 | 控制日成本 |
| 会话预算 | 会话 ID | $2/会话 | 控制会话成本 |

---

## 2. 限流策略

### 2.1 滑动窗口算法

ThesisMiner 采用滑动窗口（Sliding Window）算法进行限流，相比固定窗口算法，滑动窗口能够更精确地控制请求速率，避免窗口边界处的突发流量。

**算法原理**：

```
┌──────────────────────────────────────────────────────┐
│              滑动窗口算法原理                          │
├──────────────────────────────────────────────────────┤
│                                                      │
│  固定窗口算法的问题：                                  │
│  ──────────────────                                  │
│  窗口 1 (0:00-1:00)    窗口 2 (1:00-2:00)            │
│  ┌────────────────┐   ┌────────────────┐            │
│  │ 60 次请求      │   │ 60 次请求      │            │
│  │ (集中在 0:55)  │   │ (集中在 1:05)  │            │
│  └────────────────┘   └────────────────┘            │
│                                                      │
│  问题：0:55-1:05 的 10 秒内有 120 次请求              │
│  超过 60 次/分钟的限制                                │
│                                                      │
│  滑动窗口算法的解决：                                  │
│  ──────────────────                                  │
│  任意时刻向前看 60 秒的窗口                            │
│  窗口内请求数 ≤ 60 才允许通过                          │
│                                                      │
│  0:55 ────────────── 1:55                           │
│  ┌──────────────────────────────┐                   │
│  │ 滑动窗口 (60 秒)              │                   │
│  │ 当前请求数 = 45               │                   │
│  │ 允许新请求 (45 < 60)          │                   │
│  └──────────────────────────────┘                   │
│                                                      │
└──────────────────────────────────────────────────────┘
```

**算法实现**：

```python
import time
from collections import deque
from threading import Lock


class SlidingWindowRateLimiter:
    """滑动窗口限流器"""

    def __init__(self, max_requests: int, window_seconds: int):
        """
        Args:
            max_requests: 窗口内最大请求数
            window_seconds: 窗口大小（秒）
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = deque()  # 存储请求时间戳
        self.lock = Lock()

    def is_allowed(self) -> bool:
        """检查是否允许请求通过"""
        now = time.time()

        with self.lock:
            # 移除窗口外的旧请求
            while self.requests and self.requests[0] <= now - self.window_seconds:
                self.requests.popleft()

            # 检查是否超限
            if len(self.requests) >= self.max_requests:
                return False

            # 记录新请求
            self.requests.append(now)
            return True

    def get_remaining(self) -> int:
        """获取剩余可用请求数"""
        now = time.time()

        with self.lock:
            # 移除窗口外的旧请求
            while self.requests and self.requests[0] <= now - self.window_seconds:
                self.requests.popleft()

            return max(0, self.max_requests - len(self.requests))

    def get_retry_after(self) -> float:
        """获取需要等待的秒数"""
        now = time.time()

        with self.lock:
            if len(self.requests) < self.max_requests:
                return 0

            # 最早请求的过期时间
            oldest = self.requests[0]
            return max(0, oldest + self.window_seconds - now)

    def reset(self):
        """重置限流器"""
        with self.lock:
            self.requests.clear()
```

### 2.2 令牌桶算法（Token Bucket）

对于需要支持突发流量的场景，ThesisMiner 使用令牌桶算法：

```python
import time
from threading import Lock


class TokenBucketRateLimiter:
    """令牌桶限流器"""

    def __init__(self, capacity: float, refill_rate: float):
        """
        Args:
            capacity: 桶容量（最大突发量）
            refill_rate: 令牌补充速率（个/秒）
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
        self.lock = Lock()

    def _refill(self):
        """补充令牌"""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def is_allowed(self, tokens_needed: float = 1) -> bool:
        """检查是否有足够令牌"""
        with self.lock:
            self._refill()
            if self.tokens >= tokens_needed:
                self.tokens -= tokens_needed
                return True
            return False

    def get_remaining(self) -> float:
        """获取剩余令牌数"""
        with self.lock:
            self._refill()
            return self.tokens
```

### 2.3 限流配置参数

```python
RATE_LIMIT_CONFIG = {
    # IP 限流
    "ip_limit": {
        "max_requests": 120,
        "window_seconds": 60,
        "algorithm": "sliding_window",
    },

    # 用户限流
    "user_limit": {
        "max_requests": 60,
        "window_seconds": 60,
        "algorithm": "sliding_window",
    },

    # API Key 限流
    "api_key_limit": {
        "max_requests": 60,
        "window_seconds": 60,
        "algorithm": "sliding_window",
    },

    # 会话限流
    "session_limit": {
        "max_requests": 30,
        "window_seconds": 60,
        "algorithm": "sliding_window",
    },

    # 模型限流
    "model_limit": {
        "max_requests": 30,
        "window_seconds": 3600,  # 1 小时
        "algorithm": "sliding_window",
    },

    # Agent 限流
    "agent_limit": {
        "max_requests": 20,
        "window_seconds": 60,
        "algorithm": "sliding_window",
    },

    # 流式输出限流
    "stream_limit": {
        "capacity": 10,
        "refill_rate": 2,  # 2 个/秒
        "algorithm": "token_bucket",
    },
}
```

---

## 3. 配额管理

### 3.1 按会话配额

每个会话有独立的配额限制，防止单个会话消耗过多资源。

```python
SESSION_QUOTA_CONFIG = {
    "max_messages_per_session": 100,      # 每会话最大消息数
    "max_proposals_per_session": 20,      # 每会话最大论题生成数
    "max_tokens_per_session": 500000,     # 每会话最大 Token 数
    "max_cost_per_session": 2.0,          # 每会话最大成本（美元）
    "session_timeout": 3600,              # 会话超时（秒）
}
```

**会话配额检查流程**：

```
┌──────────────────────────────────────────────────────┐
│              会话配额检查流程                          │
├──────────────────────────────────────────────────────┤
│                                                      │
│  请求到达                                            │
│      │                                               │
│      ▼                                               │
│  ┌──────────────┐                                   │
│  │ 检查消息数   │──超限──→ 返回 429                 │
│  └──────┬───────┘                                   │
│         │ 通过                                      │
│         ▼                                           │
│  ┌──────────────┐                                   │
│  │ 检查论题数   │──超限──→ 返回 429                 │
│  └──────┬───────┘                                   │
│         │ 通过                                      │
│         ▼                                           │
│  ┌──────────────┐                                   │
│  │ 检查 Token 数│──超限──→ 返回 429                 │
│  └──────┬───────┘                                   │
│         │ 通过                                      │
│         ▼                                           │
│  ┌──────────────┐                                   │
│  │ 检查成本     │──超限──→ 返回 429                 │
│  └──────┬───────┘                                   │
│         │ 通过                                      │
│         ▼                                           │
│  允许请求                                            │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### 3.2 按用户配额

```python
USER_QUOTA_CONFIG = {
    "max_sessions_per_user": 10,         # 每用户最大会话数
    "max_requests_per_day": 1000,        # 每用户日请求限制
    "max_tokens_per_day": 2000000,       # 每用户日 Token 限制
    "max_cost_per_day": 10.0,            # 每用户日成本限制（美元）
    "max_concurrent_sessions": 3,        # 最大并发会话数
}
```

### 3.3 按模型配额

```python
MODEL_QUOTA_CONFIG = {
    "gpt-4.1": {
        "max_calls_per_hour": 30,
        "max_tokens_per_hour": 100000,
        "max_cost_per_hour": 5.0,
    },
    "deepseek-chat-v3": {
        "max_calls_per_hour": 60,
        "max_tokens_per_hour": 200000,
        "max_cost_per_hour": 1.0,
    },
    "deepseek-reasoner": {
        "max_calls_per_hour": 20,
        "max_tokens_per_hour": 80000,
        "max_cost_per_hour": 2.0,
    },
    "claude-opus-4.5": {
        "max_calls_per_hour": 15,
        "max_tokens_per_hour": 50000,
        "max_cost_per_hour": 8.0,
    },
}
```

### 3.4 按 Agent 配额

```python
AGENT_QUOTA_CONFIG = {
    "reasoner": {
        "max_calls_per_minute": 10,
        "max_calls_per_hour": 100,
        "timeout_seconds": 120,
    },
    "mentor": {
        "max_calls_per_minute": 8,
        "max_calls_per_hour": 80,
        "timeout_seconds": 90,
    },
    "searcher": {
        "max_calls_per_minute": 20,
        "max_calls_per_hour": 200,
        "timeout_seconds": 5,
    },
    "writer": {
        "max_calls_per_minute": 5,
        "max_calls_per_hour": 50,
        "timeout_seconds": 300,
    },
}
```

---

## 4. 分级限流

ThesisMiner 提供三档限流级别，用户可根据需求选择合适的级别。

### 4.1 免费版（Free）

| 限流项 | 限制值 | 说明 |
|--------|--------|------|
| 每分钟请求数 | 10 | 基础请求频率 |
| 每日请求数 | 100 | 日请求总量 |
| 每日 Token 数 | 50,000 | 日 Token 总量 |
| 每日成本 | $0.50 | 日成本上限 |
| 并发会话数 | 1 | 同时只能 1 个会话 |
| 可用模型 | deepseek-chat-v3 | 仅基础模型 |
| Agent 调用 | 20 次/天 | 有限 Agent 调用 |
| 流式输出 | 不支持 | 不支持 SSE |
| 优先级 | 低 | 低优先级队列 |

### 4.2 标准版（Standard）

| 限流项 | 限制值 | 说明 |
|--------|--------|------|
| 每分钟请求数 | 60 | 标准请求频率 |
| 每日请求数 | 1,000 | 日请求总量 |
| 每日 Token 数 | 500,000 | 日 Token 总量 |
| 每日成本 | $5.00 | 日成本上限 |
| 并发会话数 | 3 | 最多 3 个并发会话 |
| 可用模型 | deepseek-chat-v3, deepseek-reasoner, gpt-4.1-mini | 多模型可选 |
| Agent 调用 | 200 次/天 | 标准 Agent 调用 |
| 流式输出 | 支持 | 支持 SSE |
| 优先级 | 中 | 中优先级队列 |

### 4.3 高级版（Premium）

| 限流项 | 限制值 | 说明 |
|--------|--------|------|
| 每分钟请求数 | 120 | 高请求频率 |
| 每日请求数 | 5,000 | 日请求总量 |
| 每日 Token 数 | 2,000,000 | 日 Token 总量 |
| 每日成本 | $20.00 | 日成本上限 |
| 并发会话数 | 10 | 最多 10 个并发会话 |
| 可用模型 | 全部模型 | 所有模型可用 |
| Agent 调用 | 无限 | 不限制 Agent 调用 |
| 流式输出 | 支持 | 支持 SSE |
| 优先级 | 高 | 高优先级队列 |
| 专属支持 | 是 | 专属技术支持 |

### 4.4 分级限流配置

```python
TIER_CONFIG = {
    "free": {
        "rate_limits": {
            "per_minute": 10,
            "per_hour": 200,
            "per_day": 100,
        },
        "token_limits": {
            "per_day": 50000,
        },
        "cost_limits": {
            "per_day": 0.50,
        },
        "concurrent_sessions": 1,
        "available_models": ["deepseek-chat-v3"],
        "agent_calls_per_day": 20,
        "streaming": False,
        "priority": "low",
    },
    "standard": {
        "rate_limits": {
            "per_minute": 60,
            "per_hour": 1000,
            "per_day": 1000,
        },
        "token_limits": {
            "per_day": 500000,
        },
        "cost_limits": {
            "per_day": 5.00,
        },
        "concurrent_sessions": 3,
        "available_models": [
            "deepseek-chat-v3",
            "deepseek-reasoner",
            "gpt-4.1-mini",
        ],
        "agent_calls_per_day": 200,
        "streaming": True,
        "priority": "medium",
    },
    "premium": {
        "rate_limits": {
            "per_minute": 120,
            "per_hour": 5000,
            "per_day": 5000,
        },
        "token_limits": {
            "per_day": 2000000,
        },
        "cost_limits": {
            "per_day": 20.00,
        },
        "concurrent_sessions": 10,
        "available_models": "all",
        "agent_calls_per_day": -1,  # 无限
        "streaming": True,
        "priority": "high",
    },
}
```

---

## 5. 超限处理

### 5.1 429 响应格式

当请求被限流时，服务器返回 HTTP 429 状态码，响应体包含详细的限流信息。

```json
{
  "error": {
    "code": "HTTP_429_TOO_MANY_REQUESTS",
    "message": "请求频率超过限制",
    "details": {
      "limit_type": "rate_limit",
      "limit_scope": "user",
      "limit": 60,
      "window": "60s",
      "retry_after": 30,
      "current_usage": 60,
      "reset_at": "2026-06-19T10:31:00Z",
      "upgrade_url": "/docs/api/rate_limiting#upgrade"
    },
    "timestamp": "2026-06-19T10:30:00Z",
    "request_id": "req-abc123"
  }
}
```

### 5.2 响应头

429 响应包含以下标准限流头：

| 响应头 | 说明 | 示例 |
|--------|------|------|
| `Retry-After` | 建议重试等待时间（秒） | `30` |
| `X-RateLimit-Limit` | 窗口内限制总数 | `60` |
| `X-RateLimit-Remaining` | 窗口内剩余请求数 | `0` |
| `X-RateLimit-Reset` | 窗口重置时间（Unix 时间戳） | `1718798100` |
| `X-RateLimit-Scope` | 限流范围 | `user` |
| `X-RateLimit-Type` | 限流类型 | `rate_limit` |

### 5.3 不同限流类型的响应

**频率限流**：

```json
{
  "error": {
    "code": "HTTP_429_TOO_MANY_REQUESTS",
    "message": "请求频率超过限制",
    "details": {
      "limit_type": "rate_limit",
      "limit_scope": "user",
      "limit": 60,
      "window": "60s",
      "retry_after": 30
    }
  }
}
```

**配额限流**：

```json
{
  "error": {
    "code": "BIZ_BUDGET_EXCEED_002",
    "message": "日预算超限",
    "details": {
      "limit_type": "quota_limit",
      "limit_scope": "user",
      "quota": "daily_cost",
      "limit": 5.00,
      "current": 5.02,
      "reset_at": "2026-06-20T00:00:00Z",
      "upgrade_url": "/docs/api/rate_limiting#upgrade"
    }
  }
}
```

**并发限流**：

```json
{
  "error": {
    "code": "HTTP_429_TOO_MANY_REQUESTS",
    "message": "并发会话数超限",
    "details": {
      "limit_type": "concurrent_limit",
      "limit_scope": "user",
      "limit": 3,
      "current": 3,
      "suggestion": "请等待现有会话完成或关闭部分会话"
    }
  }
}
```

---

## 6. 客户端重试策略

### 6.1 指数退避策略

当收到 429 响应时，客户端应使用指数退避策略进行重试：

```python
import time
import requests


def request_with_retry(
    url: str,
    max_retries: int = 5,
    initial_delay: float = 1.0,
    max_delay: float = 60.0
):
    """
    带指数退避的请求重试

    Args:
        url: 请求 URL
        max_retries: 最大重试次数
        initial_delay: 初始延迟（秒）
        max_delay: 最大延迟（秒）
    """
    delay = initial_delay

    for attempt in range(max_retries + 1):
        response = requests.get(url)

        if response.status_code != 429:
            return response

        # 从响应头获取 Retry-After
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            delay = float(retry_after)
        else:
            # 指数退避 + 随机抖动
            import random
            jitter = random.uniform(0, 0.1 * delay)
            delay = min(delay * 2 + jitter, max_delay)

        if attempt < max_retries:
            print(f"请求被限流，{delay:.1f} 秒后重试（第 {attempt + 1} 次）")
            time.sleep(delay)
        else:
            print(f"已达到最大重试次数 {max_retries}")
            return response
```

### 6.2 Python SDK 重试示例

```python
class ThesisMinerClient:
    """ThesisMiner API 客户端"""

    def __init__(self, api_key: str, base_url: str = "http://localhost:8000"):
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {api_key}"

    def request_with_retry(
        self,
        method: str,
        endpoint: str,
        max_retries: int = 5,
        **kwargs
    ):
        """带自动重试的请求"""
        url = f"{self.base_url}{endpoint}"
        delay = 1.0

        for attempt in range(max_retries + 1):
            response = self.session.request(method, url, **kwargs)

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    delay = float(retry_after)
                else:
                    delay = min(delay * 2, 60)

                if attempt < max_retries:
                    time.sleep(delay)
                    continue

            # 检查限流头
            remaining = response.headers.get("X-RateLimit-Remaining")
            if remaining and int(remaining) <= 5:
                print(f"警告：剩余请求次数不足 ({remaining})")

            return response

        return response
```

### 6.3 JavaScript 重试示例

```javascript
class ThesisMinerClient {
    constructor(apiKey, baseUrl = 'http://localhost:8000') {
        this.apiKey = apiKey;
        this.baseUrl = baseUrl;
    }

    async requestWithRetry(method, endpoint, maxRetries = 5, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        let delay = 1000; // 毫秒

        for (let attempt = 0; attempt <= maxRetries; attempt++) {
            const response = await fetch(url, {
                method,
                headers: {
                    'Authorization': `Bearer ${this.apiKey}`,
                    'Content-Type': 'application/json',
                    ...options.headers,
                },
                body: options.body ? JSON.stringify(options.body) : undefined,
            });

            if (response.status === 429) {
                const retryAfter = response.headers.get('Retry-After');
                if (retryAfter) {
                    delay = parseFloat(retryAfter) * 1000;
                } else {
                    delay = Math.min(delay * 2, 60000);
                }

                if (attempt < maxRetries) {
                    await new Promise(resolve => setTimeout(resolve, delay));
                    continue;
                }
            }

            return response;
        }
    }
}
```

---

## 7. 监控与告警

### 7.1 限流指标

ThesisMiner 暴露以下 Prometheus 指标用于监控限流状态：

| 指标名称 | 类型 | 标签 | 说明 |
|---------|------|------|------|
| `thesisminer_rate_limit_total` | Counter | `scope`, `result` | 限流检查总数 |
| `thesisminer_rate_limit_blocked` | Counter | `scope` | 被限流阻止的请求数 |
| `thesisminer_rate_limit_remaining` | Gauge | `scope`, `user_id` | 剩余可用请求数 |
| `thesisminer_quota_usage` | Gauge | `scope`, `user_id`, `quota_type` | 配额使用量 |
| `thesisminer_quota_exceeded` | Counter | `scope`, `quota_type` | 配额超限次数 |
| `thesisminer_concurrent_sessions` | Gauge | `user_id` | 当前并发会话数 |
| `thesisminer_request_duration` | Histogram | `endpoint`, `method` | 请求处理耗时 |

### 7.2 Prometheus 监控配置

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'thesisminer'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

### 7.3 Grafana 面板配置

**面板一：限流概览**

```json
{
  "panels": [
    {
      "title": "请求总数 vs 被限流数",
      "type": "graph",
      "targets": [
        {
          "expr": "rate(thesisminer_rate_limit_total[5m])",
          "legendFormat": "{{scope}} - {{result}}"
        },
        {
          "expr": "rate(thesisminer_rate_limit_blocked[5m])",
          "legendFormat": "{{scope}} - blocked"
        }
      ]
    },
    {
      "title": "限流阻止率",
      "type": "stat",
      "targets": [
        {
          "expr": "sum(rate(thesisminer_rate_limit_blocked[5m])) / sum(rate(thesisminer_rate_limit_total[5m])) * 100",
          "legendFormat": "阻止率 %"
        }
      ]
    }
  ]
}
```

**面板二：配额使用**

```json
{
  "panels": [
    {
      "title": "日配额使用率",
      "type": "gauge",
      "targets": [
        {
          "expr": "thesisminer_quota_usage{quota_type=\"daily_cost\"} / 5.0 * 100",
          "legendFormat": "{{user_id}}"
        }
      ]
    },
    {
      "title": "配额超限次数",
      "type": "graph",
      "targets": [
        {
          "expr": "rate(thesisminer_quota_exceeded[1h])",
          "legendFormat": "{{scope}} - {{quota_type}}"
        }
      ]
    }
  ]
}
```

### 7.4 告警规则

```yaml
# alerts.yml
groups:
  - name: thesisminer_rate_limit
    rules:
      # 限流阻止率过高
      - alert: HighRateLimitBlockRate
        expr: |
          sum(rate(thesisminer_rate_limit_blocked[5m])) /
          sum(rate(thesisminer_rate_limit_total[5m])) > 0.1
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "限流阻止率过高"
          description: "过去 5 分钟内限流阻止率超过 10%"

      # 配额超限频繁
      - alert: FrequentQuotaExceeded
        expr: rate(thesisminer_quota_exceeded[1h]) > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "配额超限频繁"
          description: "过去 1 小时内配额超限超过 10 次"

      # 并发会话数过高
      - alert: HighConcurrentSessions
        expr: sum(thesisminer_concurrent_sessions) > 50
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "并发会话数过高"
          description: "当前并发会话总数超过 50"

      # 单用户并发会话过高
      - alert: UserHighConcurrentSessions
        expr: thesisminer_concurrent_sessions > 5
        for: 10m
        labels:
          severity: info
        annotations:
          summary: "单用户并发会话过高"
          description: "用户 {{ $labels.user_id }} 的并发会话数超过 5"
```

---

## 8. 配置参考

### 8.1 完整限流配置

```python
# backend/config.py 中的限流配置

RATE_LIMITING_CONFIG = {
    # 全局开关
    "enabled": True,

    # 限流算法
    "default_algorithm": "sliding_window",

    # 限流维度
    "dimensions": {
        "ip": {
            "enabled": True,
            "max_requests": 120,
            "window_seconds": 60,
        },
        "user": {
            "enabled": True,
            "max_requests": 60,
            "window_seconds": 60,
        },
        "api_key": {
            "enabled": True,
            "max_requests": 60,
            "window_seconds": 60,
        },
        "session": {
            "enabled": True,
            "max_requests": 30,
            "window_seconds": 60,
        },
        "model": {
            "enabled": True,
            "max_requests": 30,
            "window_seconds": 3600,
        },
        "agent": {
            "enabled": True,
            "max_requests": 20,
            "window_seconds": 60,
        },
    },

    # 配额管理
    "quotas": {
        "session": {
            "max_messages": 100,
            "max_proposals": 20,
            "max_tokens": 500000,
            "max_cost": 2.0,
        },
        "user": {
            "max_sessions": 10,
            "max_requests_per_day": 1000,
            "max_tokens_per_day": 2000000,
            "max_cost_per_day": 10.0,
            "max_concurrent_sessions": 3,
        },
    },

    # 分级限流
    "tiers": {
        "free": { ... },
        "standard": { ... },
        "premium": { ... },
    },

    # 超限处理
    "exceeded_handling": {
        "retry_after_header": True,
        "rate_limit_headers": True,
        "upgrade_suggestion": True,
    },

    # 监控
    "monitoring": {
        "prometheus_enabled": True,
        "metrics_path": "/metrics",
        "alert_enabled": True,
    },
}
```

### 8.2 环境变量配置

```bash
# .env 文件

# 限流全局开关
RATE_LIMITING_ENABLED=true

# IP 限流
RATE_LIMIT_IP_MAX=120
RATE_LIMIT_IP_WINDOW=60

# 用户限流
RATE_LIMIT_USER_MAX=60
RATE_LIMIT_USER_WINDOW=60

# 会话限流
RATE_LIMIT_SESSION_MAX=30
RATE_LIMIT_SESSION_WINDOW=60

# 模型限流
RATE_LIMIT_MODEL_MAX=30
RATE_LIMIT_MODEL_WINDOW=3600

# 日预算
QUOTA_USER_DAILY_COST=10.0
QUOTA_USER_DAILY_TOKENS=2000000

# 会话预算
QUOTA_SESSION_MAX_COST=2.0
QUOTA_SESSION_MAX_TOKENS=500000
```

---

## 9. 最佳实践

### 9.1 客户端最佳实践

1. **实现自动重试**：所有 API 调用都应实现指数退避重试
2. **监控限流头**：检查 `X-RateLimit-Remaining` 头，提前调整请求频率
3. **缓存响应**：对不变的数据进行客户端缓存，减少 API 调用
4. **批量操作**：使用批量 API 减少请求次数
5. **错峰请求**：避免在高峰期集中发送请求

### 9.2 服务端最佳实践

1. **合理设置限流阈值**：根据系统容量设置合理的限流阈值
2. **分级限流**：对不同级别的用户设置不同的限流策略
3. **监控限流指标**：定期检查限流阻止率，调整限流配置
4. **预留缓冲**：限流阈值应低于系统最大容量，预留缓冲
5. **优雅降级**：超限时提供降级服务而非完全拒绝

### 9.3 升级建议

| 场景 | 建议级别 | 原因 |
|------|---------|------|
| 个人学习/试用 | 免费版 | 请求量小，基础功能足够 |
| 研究生日常使用 | 标准版 | 需要多模型支持和流式输出 |
| 团队研究项目 | 高级版 | 高并发、多模型、优先支持 |
| 生产环境部署 | 高级版 | 高可用、高并发、专属支持 |

---

## 10. 常见问题

**Q1：如何查看当前限流状态？**  
A：检查 API 响应头中的 `X-RateLimit-Remaining` 和 `X-RateLimit-Reset` 字段。

**Q2：429 错误后应该等待多久？**  
A：查看响应头中的 `Retry-After` 字段，该字段指示了建议的等待时间（秒）。

**Q3：如何提高限流配额？**  
A：升级到更高级别的订阅（标准版或高级版），或联系管理员调整配额。

**Q4：限流是按 IP 还是按用户？**  
A：ThesisMiner 同时实施 IP 限流和用户限流，两者独立计算，任一触发都会返回 429。

**Q5：流式输出是否消耗限流配额？**  
A：是的，流式输出请求同样消耗限流配额，且使用令牌桶算法进行额外控制。

**Q6：并发会话数超限怎么办？**  
A：关闭部分不活跃的会话，或升级到支持更多并发会话的级别。

**Q7：日预算超限后何时恢复？**  
A：日预算在 UTC 时间 00:00 重置，届时配额自动恢复。

**Q8：如何监控限流指标？**  
A：访问 `/metrics` 端点获取 Prometheus 指标，或配置 Grafana 面板进行可视化监控。

---

> **文档结束**  
> 本文档涵盖 ThesisMiner v8.0 的限流策略、配额管理、分级限流、超限处理与监控告警。如需了解更多信息，请参阅错误码参考文档和 API 文档。