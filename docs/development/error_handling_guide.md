# ThesisMiner v8.0 错误处理与异常恢复指南

> 本文档详细描述 ThesisMiner v8.0 项目的错误处理体系、异常分类、恢复策略、重试机制与降级方案。

## 目录

- [1. 错误处理概览](#1-错误处理概览)
- [2. 异常分类体系](#2-异常分类体系)
- [3. 错误码规范](#3-错误码规范)
- [4. 错误响应格式](#4-错误响应格式)
- [5. 重试机制](#5-重试机制)
- [6. 降级策略](#6-降级策略)
- [7. 熔断器模式](#7-熔断器模式)
- [8. 超时处理](#8-超时处理)
- [9. 错误日志](#9-错误日志)
- [10. 错误监控](#10-错误监控)
- [11. 用户友好提示](#11-用户友好提示)
- [12. 附录](#12-附录)

---

## 1. 错误处理概览

### 1.1 设计原则

1. **快速失败**：检测到错误立即返回，不掩盖问题
2. **优雅降级**：非核心功能失败不影响核心功能
3. **可恢复**：提供明确的恢复路径
4. **可观测**：所有错误都有日志与监控
5. **用户友好**：错误提示对用户有意义

### 1.2 错误处理层次

```
用户请求 → 输入验证 → 业务逻辑 → 外部调用 → 数据持久化
   ↓           ↓          ↓          ↓           ↓
400错误    422错误    500错误    502错误    500错误
```

---

## 2. 异常分类体系

### 2.1 异常层次结构

```python
class ThesisMinerError(Exception):
    """所有 ThesisMiner 异常的基类"""
    error_code = "TM_0000"
    status_code = 500
    user_message = "系统内部错误"

class ValidationError(ThesisMinerError):
    """输入验证错误"""
    error_code = "TM_1001"
    status_code = 400
    user_message = "输入参数无效"

class AuthenticationError(ThesisMinerError):
    """认证错误"""
    error_code = "TM_2001"
    status_code = 401
    user_message = "请先登录"

class AuthorizationError(ThesisMinerError):
    """授权错误"""
    error_code = "TM_2002"
    status_code = 403
    user_message = "无权访问"

class NotFoundError(ThesisMinerError):
    """资源未找到"""
    error_code = "TM_3001"
    status_code = 404
    user_message = "资源不存在"

class ConflictError(ThesisMinerError):
    """资源冲突"""
    error_code = "TM_3002"
    status_code = 409
    user_message = "资源已存在"

class RateLimitError(ThesisMinerError):
    """限流错误"""
    error_code = "TM_4001"
    status_code = 429
    user_message = "请求过于频繁"

class LLMError(ThesisMinerError):
    """LLM 调用错误"""
    error_code = "TM_5001"
    status_code = 502
    user_message = "AI 服务暂时不可用"

class DatabaseError(ThesisMinerError):
    """数据库错误"""
    error_code = "TM_6001"
    status_code = 500
    user_message = "数据存储异常"

class AgentError(ThesisMinerError):
    """Agent 执行错误"""
    error_code = "TM_7001"
    status_code = 500
    user_message = "Agent 执行失败"

class ConstraintError(ThesisMinerError):
    """约束违反错误"""
    error_code = "TM_8001"
    status_code = 422
    user_message = "约束校验失败"
```

---

## 3. 错误码规范

### 3.1 错误码格式

```
TM_XYYY
│  │└─┴─ 具体错误编号（001-999）
│  └───── 错误类别（1-9）
└──────── ThesisMiner 标识
```

### 3.2 错误类别

| 类别 | 范围 | 说明 |
|------|------|------|
| 1 | TM_1001-TM_1999 | 验证错误 |
| 2 | TM_2001-TM_2999 | 认证授权错误 |
| 3 | TM_3001-TM_3999 | 资源错误 |
| 4 | TM_4001-TM_4999 | 限流配额错误 |
| 5 | TM_5001-TM_5999 | LLM 错误 |
| 6 | TM_6001-TM_6999 | 数据库错误 |
| 7 | TM_7001-TM_7999 | Agent 错误 |
| 8 | TM_8001-TM_8999 | 约束错误 |
| 9 | TM_9001-TM_9999 | 系统错误 |

---

## 4. 错误响应格式

### 4.1 标准错误响应

```json
{
    "error": {
        "code": "TM_1001",
        "type": "ValidationError",
        "message": "标题长度不能超过100字符",
        "details": {
            "field": "title",
            "max_length": 100,
            "actual_length": 120
        },
        "request_id": "req_abc123",
        "timestamp": "2026-06-19T10:00:00Z"
    }
}
```

### 4.2 字段验证错误

```json
{
    "error": {
        "code": "TM_1002",
        "type": "ValidationError",
        "message": "多个字段验证失败",
        "details": {
            "errors": [
                {"field": "title", "message": "标题不能为空"},
                {"field": "discipline", "message": "学科代码无效"}
            ]
        }
    }
}
```

---

## 5. 重试机制

### 5.1 指数退避重试

```python
import asyncio
import random

async def retry_with_backoff(
    func,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple = (Exception,)
):
    """指数退避重试"""
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return await func()
        except exceptions as e:
            last_exception = e
            if attempt == max_retries:
                raise
            
            # 计算延迟（指数退避 + 抖动）
            delay = min(base_delay * (2 ** attempt), max_delay)
            delay = delay * (0.5 + random.random() * 0.5)  # 抖动
            
            await asyncio.sleep(delay)
    
    raise last_exception
```

### 5.2 可重试错误判断

```python
RETRYABLE_ERRORS = {
    "TM_5001": True,   # LLM 调用错误（可重试）
    "TM_5002": True,   # LLM 超时（可重试）
    "TM_6001": False,  # 数据库连接错误（不重试，需检查配置）
    "TM_6002": True,   # 数据库锁超时（可重试）
    "TM_7001": True,   # Agent 执行错误（可重试）
}

def is_retryable(error: ThesisMinerError) -> bool:
    return RETRYABLE_ERRORS.get(error.error_code, False)
```

---

## 6. 降级策略

### 6.1 LLM 降级链

```python
LLM_FALLBACK_CHAIN = {
    "claude-opus-4.5": ["claude-sonnet-4.5", "gpt-4.1", "deepseek-v3.2"],
    "claude-sonnet-4.5": ["gpt-4.1", "deepseek-v3.2", "qwen3-max"],
    "gpt-4.1": ["deepseek-v3.2", "qwen3-max", "glm-4.6"],
    "deepseek-v3.2": ["qwen3-max", "glm-4.6", "gpt-4.1-mini"]
}

async def call_llm_with_fallback(model_id: str, messages: list):
    """带降级的 LLM 调用"""
    chain = [model_id] + LLM_FALLBACK_CHAIN.get(model_id, [])
    
    for model in chain:
        try:
            return await call_llm(model, messages)
        except LLMError as e:
            logger.warning(f"模型 {model} 调用失败: {e}，尝试降级")
            continue
    
    raise LLMError("所有模型均不可用")
```

### 6.2 功能降级

```python
class DegradationManager:
    """降级管理器"""
    
    def __init__(self):
        self.degraded_features = set()
    
    def is_available(self, feature: str) -> bool:
        return feature not in self.degraded_features
    
    def degrade(self, feature: str, reason: str):
        self.degraded_features.add(feature)
        logger.warning(f"功能降级: {feature}, 原因: {reason}")
    
    def recover(self, feature: str):
        if feature in self.degraded_features:
            self.degraded_features.remove(feature)
            logger.info(f"功能恢复: {feature}")
```

---

## 7. 熔断器模式

### 7.1 熔断器实现

```python
import time
from enum import Enum

class CircuitState(Enum):
    CLOSED = "closed"      # 正常
    OPEN = "open"          # 熔断
    HALF_OPEN = "half_open"  # 半开

class CircuitBreaker:
    """熔断器"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
    
    async def call(self, func, *args, **kwargs):
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitBreakerOpenError("熔断器开启")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        self.failure_count = 0
        self.state = CircuitState.CLOSED
    
    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
```

---

## 8. 超时处理

### 8.1 超时配置

```python
TIMEOUT_CONFIG = {
    "llm_call": 30,          # LLM 调用 30 秒
    "llm_streaming": 120,    # 流式 120 秒
    "database_query": 5,     # 数据库查询 5 秒
    "http_request": 10,      # HTTP 请求 10 秒
    "agent_execution": 60,   # Agent 执行 60 秒
    "orchestration": 300     # 编排 5 分钟
}

async def call_with_timeout(coro, timeout_key: str):
    """带超时的调用"""
    timeout = TIMEOUT_CONFIG.get(timeout_key, 30)
    try:
        return await asyncio.wait_for(coro, timeout)
    except asyncio.TimeoutError:
        raise TimeoutError(f"操作超时: {timeout_key} ({timeout}s)")
```

---

## 9. 错误日志

### 9.1 结构化错误日志

```python
import logging
import json
from datetime import datetime

class ErrorLogger:
    """错误日志器"""
    
    def __init__(self):
        self.logger = logging.getLogger("thesisminer.error")
    
    def log_error(self, error: Exception, context: dict = None):
        """记录错误"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "error_code": getattr(error, "error_code", None),
            "stack_trace": traceback.format_exc(),
            "context": context or {}
        }
        
        self.logger.error(json.dumps(log_data, ensure_ascii=False))
```

---

## 10. 错误监控

### 10.1 错误指标

```python
class ErrorMonitor:
    """错误监控"""
    
    def __init__(self):
        self.error_counts = {}
        self.error_rates = {}
    
    def record_error(self, error_code: str):
        self.error_counts[error_code] = self.error_counts.get(error_code, 0) + 1
    
    def get_error_stats(self) -> dict:
        total = sum(self.error_counts.values())
        return {
            "total_errors": total,
            "by_code": self.error_counts,
            "top_errors": sorted(
                self.error_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
        }
```

---

## 11. 用户友好提示

### 11.1 错误提示映射

```python
USER_FRIENDLY_MESSAGES = {
    "TM_1001": "您输入的信息有误，请检查后重试",
    "TM_2001": "登录已过期，请重新登录",
    "TM_3001": "您查找的内容不存在",
    "TM_4001": "操作过于频繁，请稍后再试",
    "TM_5001": "AI 服务暂时不可用，正在尝试恢复",
    "TM_6001": "系统存储异常，请联系管理员",
    "TM_7001": "处理过程中出现问题，请重试",
    "TM_8001": "内容不符合学术规范，请根据提示修改"
}

def get_user_message(error_code: str) -> str:
    return USER_FRIENDLY_MESSAGES.get(error_code, "系统异常，请稍后重试")
```

---

## 12. 附录

### 12.1 错误处理检查清单

- [ ] 所有外部调用都有 try-catch
- [ ] 错误有明确的错误码
- [ ] 错误响应符合标准格式
- [ ] 可重试错误有重试机制
- [ ] 关键服务有熔断器
- [ ] 所有调用有超时控制
- [ ] 错误有结构化日志
- [ ] 错误有监控告警
- [ ] 用户提示友好易懂
- [ ] 有降级方案

---

## 结语

完善的错误处理是系统稳定性的保障。ThesisMiner v8.0 通过分层的异常体系、智能的重试机制、优雅的降级策略，确保系统在异常情况下仍能提供可用服务。
