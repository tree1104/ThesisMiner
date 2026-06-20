# ThesisMiner v8.0 API 限流与配额管理

> 本文档详细描述 ThesisMiner v8.0 项目的 API 限流策略、配额管理、用户分级与流量控制机制。

## 目录

- [1. 限流概览](#1-限流概览)
- [2. 限流算法](#2-限流算法)
- [3. 限流策略](#3-限流策略)
- [4. 配额管理](#4-配额管理)
- [5. 用户分级](#5-用户分级)
- [6. 限流中间件](#6-限流中间件)
- [7. 限流响应](#7-限流响应)
- [8. 限流监控](#8-限流监控)
- [9. 限流配置](#9-限流配置)
- [10. 最佳实践](#10-最佳实践)
- [11. 附录](#11-附录)

---

## 1. 限流概览

### 1.1 限流目标

1. **保护系统**：防止过载导致服务不可用
2. **公平使用**：确保所有用户公平访问资源
3. **成本控制**：控制 LLM API 调用成本
4. **安全防护**：防止恶意攻击与滥用
5. **质量保证**：确保响应质量不受过载影响

### 1.2 限流维度

| 维度 | 说明 | 示例 |
|------|------|------|
| 用户 | 按用户 ID 限流 | 每用户 100 次/小时 |
| IP | 按 IP 地址限流 | 每 IP 1000 次/小时 |
| API | 按 API 端点限流 | /api/sessions 60 次/分钟 |
| 全局 | 全系统总流量 | 10000 次/分钟 |
| 模型 | 按 LLM 模型限流 | deepseek-v3.2 50 次/分钟 |

---

## 2. 限流算法

### 2.1 令牌桶算法

```python
import time
import threading

class TokenBucket:
    """令牌桶限流器"""
    
    def __init__(self, capacity: int, refill_rate: float):
        """
        Args:
            capacity: 桶容量（最大突发量）
            refill_rate: 令牌补充速率（个/秒）
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
        self.lock = threading.Lock()
    
    def acquire(self, tokens: int = 1) -> bool:
        """获取令牌"""
        with self.lock:
            now = time.time()
            # 补充令牌
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    def wait_time(self, tokens: int = 1) -> float:
        """计算等待时间"""
        with self.lock:
            if self.tokens >= tokens:
                return 0
            needed = tokens - self.tokens
            return needed / self.refill_rate
```

### 2.2 漏桶算法

```python
class LeakyBucket:
    """漏桶限流器"""
    
    def __init__(self, capacity: int, leak_rate: float):
        self.capacity = capacity
        self.leak_rate = leak_rate
        self.water = 0
        self.last_leak = time.time()
        self.lock = threading.Lock()
    
    def allow(self) -> bool:
        """是否允许通过"""
        with self.lock:
            now = time.time()
            # 漏水
            elapsed = now - self.last_leak
            self.water = max(0, self.water - elapsed * self.leak_rate)
            self.last_leak = now
            
            if self.water < self.capacity:
                self.water += 1
                return True
            return False
```

### 2.3 滑动窗口算法

```python
from collections import deque

class SlidingWindow:
    """滑动窗口限流器"""
    
    def __init__(self, window_size: int, max_requests: int):
        self.window_size = window_size  # 窗口大小（秒）
        self.max_requests = max_requests
        self.requests = deque()
        self.lock = threading.Lock()
    
    def allow(self) -> bool:
        """是否允许请求"""
        with self.lock:
            now = time.time()
            # 移除过期请求
            while self.requests and self.requests[0] <= now - self.window_size:
                self.requests.popleft()
            
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True
            return False
```

---

## 3. 限流策略

### 3.1 API 限流配置

```python
RATE_LIMITS = {
    # 会话管理
    "POST /api/sessions": {"limit": 10, "window": 3600},  # 10次/小时
    "GET /api/sessions": {"limit": 100, "window": 60},     # 100次/分钟
    "DELETE /api/sessions/{sid}": {"limit": 10, "window": 3600},
    
    # 对话管理
    "POST /api/sessions/{sid}/conversations": {"limit": 50, "window": 3600},
    "GET /api/sessions/{sid}/conversations": {"limit": 100, "window": 60},
    
    # 消息发送
    "POST /api/conversations/{cid}/messages": {"limit": 60, "window": 60},  # 60次/分钟
    "POST /api/conversations/{cid}/messages/stream": {"limit": 30, "window": 60},
    
    # Agent 调用
    "POST /api/agents/{aid}/invoke": {"limit": 30, "window": 60},
    
    # 谱系图谱
    "GET /api/lineage": {"limit": 60, "window": 60},
    
    # 导出
    "POST /api/export": {"limit": 10, "window": 3600},
    
    # 健康检查（不限流）
    "GET /api/health": {"limit": None, "window": None}
}
```

### 3.2 模型调用限流

```python
MODEL_RATE_LIMITS = {
    "deepseek-v3.2": {"rpm": 60, "tpm": 100000},  # 每分钟请求数、Token数
    "deepseek-r2": {"rpm": 30, "tpm": 50000},
    "claude-sonnet-4.5": {"rpm": 50, "tpm": 80000},
    "claude-opus-4.5": {"rpm": 20, "tpm": 40000},
    "gpt-4.1": {"rpm": 60, "tpm": 100000},
    "gpt-4.1-mini": {"rpm": 100, "tpm": 150000},
    "qwen3-max": {"rpm": 60, "tpm": 100000},
    "gemini-2.5-pro": {"rpm": 60, "tpm": 100000},
    "glm-4.6": {"rpm": 60, "tpm": 100000},
    "doubao-1.5-pro": {"rpm": 60, "tpm": 100000}
}
```

---

## 4. 配额管理

### 4.1 用户配额

```python
class QuotaManager:
    """配额管理器"""
    
    def __init__(self):
        self.quotas = {}
    
    def get_quota(self, user_id: str) -> dict:
        """获取用户配额"""
        return self.quotas.get(user_id, DEFAULT_QUOTA)
    
    def check_quota(self, user_id: str, resource: str, amount: int = 1) -> bool:
        """检查配额"""
        quota = self.get_quota(user_id)
        used = self.get_usage(user_id, resource)
        limit = quota.get(resource, 0)
        return used + amount <= limit
    
    def consume_quota(self, user_id: str, resource: str, amount: int = 1):
        """消耗配额"""
        if not self.check_quota(user_id, resource, amount):
            raise QuotaExceededError(f"配额不足: {resource}")
        
        self._record_usage(user_id, resource, amount)
    
    def get_usage(self, user_id: str, resource: str) -> int:
        """获取已用量"""
        return self._get_usage_from_db(user_id, resource)
```

### 4.2 配额类型

```python
QUOTA_TYPES = {
    "api_calls": {"daily": 1000, "monthly": 20000},
    "llm_calls": {"daily": 500, "monthly": 10000},
    "token_usage": {"daily": 1000000, "monthly": 20000000},
    "storage": {"limit": 1024 * 1024 * 1024},  # 1GB
    "conversations": {"limit": 100},
    "exports": {"daily": 10}
}
```

---

## 5. 用户分级

### 5.1 用户等级

```python
USER_TIERS = {
    "free": {
        "name": "免费版",
        "rate_limits": {
            "api_calls_per_minute": 10,
            "llm_calls_per_day": 50,
            "token_per_day": 100000
        },
        "features": ["basic_generation", "single_agent"]
    },
    "pro": {
        "name": "专业版",
        "rate_limits": {
            "api_calls_per_minute": 60,
            "llm_calls_per_day": 500,
            "token_per_day": 1000000
        },
        "features": ["basic_generation", "multi_agent", "export", "priority_support"]
    },
    "enterprise": {
        "name": "企业版",
        "rate_limits": {
            "api_calls_per_minute": 600,
            "llm_calls_per_day": 5000,
            "token_per_day": 10000000
        },
        "features": ["all_features", "dedicated_support", "custom_models"]
    }
}
```

---

## 6. 限流中间件

### 6.1 FastAPI 限流中间件

```python
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

class RateLimitMiddleware(BaseHTTPMiddleware):
    """限流中间件"""
    
    def __init__(self, app, limiter: RateLimiter):
        super().__init__(app)
        self.limiter = limiter
    
    async def dispatch(self, request: Request, call_next):
        # 获取限流键
        key = self._get_key(request)
        
        # 检查限流
        if not self.limiter.allow(key):
            return self._rate_limit_response(request)
        
        # 处理请求
        response = await call_next(request)
        
        # 添加限流头
        remaining = self.limiter.remaining(key)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(self.limiter.reset_time(key))
        
        return response
    
    def _get_key(self, request: Request) -> str:
        """获取限流键"""
        # 优先使用用户 ID
        user_id = request.headers.get("X-User-ID")
        if user_id:
            return f"user:{user_id}"
        
        # 其次使用 IP
        client_ip = request.client.host
        return f"ip:{client_ip}"
    
    def _rate_limit_response(self, request: Request) -> JSONResponse:
        """限流响应"""
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate_limit_exceeded",
                "message": "请求过于频繁，请稍后重试",
                "retry_after": 60
            },
            headers={
                "Retry-After": "60",
                "X-RateLimit-Remaining": "0"
            }
        )
```

---

## 7. 限流响应

### 7.1 标准 429 响应

```json
{
    "error": "rate_limit_exceeded",
    "message": "请求过于频繁，请稍后重试",
    "retry_after": 60,
    "details": {
        "limit": 60,
        "window": 60,
        "remaining": 0,
        "reset_at": "2026-06-19T10:01:00Z"
    }
}
```

### 7.2 响应头

```
HTTP/1.1 429 Too Many Requests
Content-Type: application/json
Retry-After: 60
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1718799660
```

---

## 8. 限流监控

### 8.1 监控指标

```python
class RateLimitMonitor:
    """限流监控"""
    
    def __init__(self):
        self.metrics = {
            "total_requests": 0,
            "rate_limited": 0,
            "by_endpoint": {},
            "by_user": {}
        }
    
    def record(self, endpoint: str, user_id: str, rate_limited: bool):
        self.metrics["total_requests"] += 1
        if rate_limited:
            self.metrics["rate_limited"] += 1
        
        self.metrics["by_endpoint"][endpoint] = \
            self.metrics["by_endpoint"].get(endpoint, 0) + 1
        
        if rate_limited:
            self.metrics["by_user"][user_id] = \
                self.metrics["by_user"].get(user_id, 0) + 1
    
    def get_stats(self) -> dict:
        total = self.metrics["total_requests"]
        limited = self.metrics["rate_limited"]
        return {
            "total_requests": total,
            "rate_limited": limited,
            "rate_limit_percentage": (limited / total * 100) if total > 0 else 0,
            "top_limited_users": sorted(
                self.metrics["by_user"].items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:10]
        }
```

---

## 9. 限流配置

### 9.1 配置文件

```yaml
# config/rate_limits.yaml
rate_limits:
  global:
    enabled: true
    requests_per_minute: 10000
  
  by_endpoint:
    "POST /api/sessions":
      requests_per_hour: 10
    "POST /api/conversations/*/messages":
      requests_per_minute: 60
  
  by_user_tier:
    free:
      requests_per_minute: 10
      llm_calls_per_day: 50
    pro:
      requests_per_minute: 60
      llm_calls_per_day: 500
    enterprise:
      requests_per_minute: 600
      llm_calls_per_day: 5000
  
  by_model:
    deepseek-v3.2:
      requests_per_minute: 60
      tokens_per_minute: 100000
```

---

## 10. 最佳实践

### 10.1 限流设计原则

1. **分层限流**：用户级 + API级 + 全局级
2. **合理阈值**：基于压测数据设定
3. **优雅降级**：限流时返回友好提示
4. **监控告警**：限流率异常时告警
5. **动态调整**：根据负载动态调整

### 10.2 客户端最佳实践

```javascript
// 指数退避重试
async function requestWithRetry(url, options, maxRetries = 3) {
    for (let i = 0; i < maxRetries; i++) {
        const response = await fetch(url, options);
        
        if (response.status === 429) {
            const retryAfter = parseInt(response.headers.get('Retry-After') || '60');
            await new Promise(resolve => setTimeout(resolve, retryAfter * 1000));
            continue;
        }
        
        return response;
    }
    throw new Error('Max retries exceeded');
}
```

---

## 11. 附录

### 11.1 限流算法对比

| 算法 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| 令牌桶 | 允许突发 | 实现稍复杂 | API 限流 |
| 漏桶 | 平滑流量 | 不允许突发 | 流量整形 |
| 滑动窗口 | 精确控制 | 内存占用高 | 精确限流 |
| 固定窗口 | 实现简单 | 临界问题 | 简单限流 |

### 11.2 限流状态码

| 状态码 | 含义 |
|--------|------|
| 200 | 请求成功 |
| 429 | 请求过多（限流） |
| 503 | 服务不可用（过载） |

---

## 结语

合理的限流与配额管理是保护系统稳定运行的关键。ThesisMiner v8.0 通过多维度限流、用户分级、配额管理等机制，在保障系统稳定的同时，为用户提供公平、高质量的服务。
