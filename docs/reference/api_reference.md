# ThesisMiner v8.0 API 参考文档

> **版本**：v8.0.0
> **最后更新**：2026-06-20
> **适用范围**：`backend/routes/`、`backend/api/`、`backend/middleware/`
> **文档状态**：正式发布（Stable）

---

## 目录

- [1. 文档概述](#1-文档概述)
- [2. API 架构](#2-api-架构)
- [3. 认证与授权](#3-认证与授权)
- [4. 限流策略](#4-限流策略)
- [5. Sessions API](#5-sessions-api)
- [6. Proposals API](#6-proposals-api)
- [7. Conversations API](#7-conversations-api)
- [8. Config API](#8-config-api)
- [9. Agents API](#9-agents-api)
- [10. SSE 流式接口](#10-sse-流式接口)
- [11. WebSocket 接口](#11-websocket-接口)
- [12. SDK 参考](#12-sdk-参考)
- [13. 错误码](#13-错误码)
- [14. 附录](#14-附录)

---

## 1. 文档概述

### 1.1 文档目的

本文档是 ThesisMiner v8.0 API 的完整参考手册，涵盖：

- 所有 REST API 端点
- SSE 流式接口
- WebSocket 接口
- SDK 使用方法
- 错误码定义
- 认证与限流

### 1.2 面向读者

- **前端开发者**：调用 API 构建用户界面
- **后端开发者**：扩展或修改 API
- **SDK 开发者**：开发客户端 SDK
- **运维工程师**：排查 API 相关问题

### 1.3 API 概览

| API 类别 | 端点数 | 基础路径 | 说明 |
|----------|--------|----------|------|
| Sessions | 6 | `/api/sessions` | 会话管理 |
| Proposals | 5 | `/api/proposals` | 选题生成 |
| Conversations | 4 | `/api/conversations` | 对话管理 |
| Config | 5 | `/api/config` | 配置管理 |
| Agents | 4 | `/api/agents` | Agent 管理 |
| SSE | 2 | `/api/stream` | 流式接口 |
| WebSocket | 1 | `/ws` | 实时通信 |

### 1.4 通用约定

#### 1.4.1 请求格式

- **基础 URL**：`http://localhost:8000`
- **Content-Type**：`application/json`
- **字符集**：UTF-8
- **认证**：Bearer Token（可选）

#### 1.4.2 响应格式

所有 API 返回统一的 JSON 格式：

```json
{
  "code": 200,
  "message": "success",
  "data": {...},
  "timestamp": "2026-06-20T10:30:00Z",
  "request_id": "req_abc123"
}
```

#### 1.4.3 错误响应

```json
{
  "code": 400,
  "message": "Bad Request",
  "error": {
    "type": "ValidationError",
    "details": "缺少必需参数: title"
  },
  "timestamp": "2026-06-20T10:30:00Z",
  "request_id": "req_abc123"
}
```

### 1.5 术语表

| 术语 | 英文 | 含义 |
|------|------|------|
| 端点 | Endpoint | API 的访问地址 |
| 会话 | Session | 用户与系统的交互会话 |
| 选题 | Proposal | 生成的论文选题 |
| 对话 | Conversation | 用户与 Agent 的对话 |
| 流式 | Streaming | 实时流式返回 |
| 限流 | Rate Limiting | 限制请求频率 |

---

## 2. API 架构

### 2.1 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                      客户端 (Client)                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    API 网关 (Gateway)                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  - 认证 (Auth)                                           │   │
│  │  - 限流 (Rate Limiting)                                  │   │
│  │  - 日志 (Logging)                                        │   │
│  │  - CORS                                                  │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI 路由层                                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ Sessions │ │Proposals │ │Conversa- │ │ Config   │          │
│  │  Router  │ │  Router  │ │  Router  │ │  Router  │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                       │
│  │  Agents  │ │   SSE    │ │WebSocket │                       │
│  │  Router  │ │  Router  │ │  Router  │                       │
│  └──────────┘ └──────────┘ └──────────┘                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    业务逻辑层                                    │
│  - Agent 编排                                                   │
│  - 约束检查                                                     │
│  - 数据持久化                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 路由组织

```python
# backend/main.py
from fastapi import FastAPI
from contextlib import asynccontextmanager

from backend.routes import (
    sessions, proposals, conversations, config, agents,
    sse, websocket
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    # 启动时
    await init_database()
    await warmup_agents()
    yield
    # 关闭时
    await cleanup()

app = FastAPI(
    title="ThesisMiner API",
    version="8.0.0",
    lifespan=lifespan
)

# 注册路由
app.include_router(sessions.router, prefix="/api/sessions", tags=["Sessions"])
app.include_router(proposals.router, prefix="/api/proposals", tags=["Proposals"])
app.include_router(conversations.router, prefix="/api/conversations", tags=["Conversations"])
app.include_router(config.router, prefix="/api/config", tags=["Config"])
app.include_router(agents.router, prefix="/api/agents", tags=["Agents"])
app.include_router(sse.router, prefix="/api/stream", tags=["SSE"])
app.include_router(websocket.router, tags=["WebSocket"])
```

### 2.3 中间件

```python
# backend/middleware/
backend/middleware/
├── auth.py              # 认证中间件
├── rate_limiting.py     # 限流中间件
├── logging.py           # 日志中间件
├── cors.py              # CORS 中间件
└── error_handler.py     # 错误处理中间件
```

---

## 3. 认证与授权

### 3.1 认证方式

ThesisMiner v8.0 支持 Bearer Token 认证（可选）：

```http
GET /api/sessions HTTP/1.1
Host: localhost:8000
Authorization: Bearer <token>
Content-Type: application/json
```

### 3.2 认证配置

```yaml
# config/system.yaml
security:
  auth_enabled: false          # 是否启用认证（默认关闭）
  token_header: Authorization  # Token 请求头
  token_prefix: Bearer         # Token 前缀
  token_expiry: 3600           # Token 有效期（秒）
  
  # API Key 认证
  api_key_enabled: false
  api_key_header: X-API-Key
```

### 3.3 获取 Token

```http
POST /api/auth/token HTTP/1.1
Content-Type: application/json

{
  "username": "admin",
  "password": "password"
}
```

**响应**：

```json
{
  "code": 200,
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "expires_in": 3600,
    "token_type": "Bearer"
  }
}
```

---

## 4. 限流策略

### 4.1 限流配置

```yaml
# config/system.yaml
rate_limiting:
  enabled: true
  strategy: token_bucket       # 令牌桶算法
  default_limit: 60            # 默认 60 请求/分钟
  burst_limit: 10              # 突发 10 请求
  
  # 按端点限流
  endpoints:
    /api/sessions:
      limit: 30                # 30 请求/分钟
      burst: 5
    /api/proposals:
      limit: 10                # 10 请求/分钟（生成耗时）
      burst: 2
    /api/stream:
      limit: 5                 # 5 请求/分钟
      burst: 1
```

### 4.2 限流响应

超过限流时返回 429：

```json
{
  "code": 429,
  "message": "Too Many Requests",
  "error": {
    "type": "RateLimitError",
    "details": "请求频率超过限制，请稍后重试",
    "retry_after": 60
  }
}
```

### 4.3 限流响应头

```http
HTTP/1.1 200 OK
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 59
X-RateLimit-Reset: 1718883000
```

---

## 5. Sessions API

### 5.1 创建会话

```http
POST /api/sessions HTTP/1.1
Content-Type: application/json

{
  "user_id": "user_123",
  "metadata": {
    "source": "web",
    "version": "8.0.0"
  }
}
```

**响应**：

```json
{
  "code": 200,
  "data": {
    "session_id": "sess_abc123",
    "user_id": "user_123",
    "created_at": "2026-06-20T10:30:00Z",
    "status": "active",
    "current_stage": "info_confirm"
  }
}
```

### 5.2 获取会话

```http
GET /api/sessions/{session_id} HTTP/1.1
```

**响应**：

```json
{
  "code": 200,
  "data": {
    "session_id": "sess_abc123",
    "user_id": "user_123",
    "created_at": "2026-06-20T10:30:00Z",
    "updated_at": "2026-06-20T10:35:00Z",
    "status": "active",
    "current_stage": "creativity",
    "stage_results": {
      "info_confirm": {
        "discipline": "计算机科学",
        "degree": "硕士",
        "direction": "大语言模型"
      }
    },
    "metadata": {...}
  }
}
```

### 5.3 列出会话

```http
GET /api/sessions?user_id=user_123&page=1&page_size=20 HTTP/1.1
```

**响应**：

```json
{
  "code": 200,
  "data": {
    "sessions": [
      {
        "session_id": "sess_abc123",
        "created_at": "2026-06-20T10:30:00Z",
        "status": "active",
        "current_stage": "creativity"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  }
}
```

### 5.4 更新会话

```http
PATCH /api/sessions/{session_id} HTTP/1.1
Content-Type: application/json

{
  "metadata": {
    "key": "value"
  }
}
```

### 5.5 删除会话

```http
DELETE /api/sessions/{session_id} HTTP/1.1
```

**响应**：

```json
{
  "code": 200,
  "message": "Session deleted"
}
```

### 5.6 重置会话

```http
POST /api/sessions/{session_id}/reset HTTP/1.1
```

**响应**：

```json
{
  "code": 200,
  "data": {
    "session_id": "sess_abc123",
    "current_stage": "info_confirm",
    "stage_results": {}
  }
}
```

---

## 6. Proposals API

### 6.1 生成选题

```http
POST /api/proposals/generate HTTP/1.1
Content-Type: application/json

{
  "session_id": "sess_abc123",
  "input": "我想写一篇关于大语言模型的硕士论文",
  "options": {
    "granularity": "full",
    "style": "academic",
    "max_candidates": 5
  }
}
```

**响应**：

```json
{
  "code": 200,
  "data": {
    "proposal_id": "prop_xyz789",
    "session_id": "sess_abc123",
    "status": "completed",
    "stages": {
      "info_confirm": {
        "discipline": "计算机科学",
        "degree": "硕士",
        "direction": "大语言模型"
      },
      "creativity": {
        "candidates": [
          {
            "title": "面向多模态文档的检索增强生成方法",
            "dimension": "pain_point_breakthrough",
            "innovation": "引入多模态对齐机制"
          }
        ]
      },
      "validation": {
        "evaluations": [
          {
            "title": "面向多模态文档的检索增强生成方法",
            "score": 85,
            "passed": true
          }
        ]
      },
      "generation": {
        "report": "# 开题报告\n\n## 一、研究背景\n...",
        "word_count": 12000
      }
    },
    "created_at": "2026-06-20T10:30:00Z"
  }
}
```

### 6.2 流式生成选题

```http
POST /api/proposals/generate?stream=true HTTP/1.1
Content-Type: application/json
Accept: text/event-stream

{
  "session_id": "sess_abc123",
  "input": "我想写一篇关于大语言模型的硕士论文"
}
```

**SSE 响应**：

```
event: stage_start
data: {"stage": "info_confirm"}

event: stage_complete
data: {"stage": "info_confirm", "result": {...}}

event: stage_start
data: {"stage": "creativity"}

event: progress
data: {"stage": "creativity", "progress": 50}

event: stage_complete
data: {"stage": "creativity", "result": {...}}

event: done
data: {"proposal_id": "prop_xyz789"}
```

### 6.3 获取选题

```http
GET /api/proposals/{proposal_id} HTTP/1.1
```

### 6.4 列出选题

```http
GET /api/proposals?session_id=sess_abc123&page=1&page_size=20 HTTP/1.1
```

### 6.5 获取报告

```http
GET /api/proposals/{proposal_id}/report?format=markdown HTTP/1.1
```

**响应**：

```json
{
  "code": 200,
  "data": {
    "proposal_id": "prop_xyz789",
    "format": "markdown",
    "content": "# 开题报告\n\n## 一、研究背景\n...",
    "word_count": 12000,
    "generated_at": "2026-06-20T10:30:00Z"
  }
}
```

---

## 7. Conversations API

### 7.1 发送消息

```http
POST /api/conversations/{session_id}/messages HTTP/1.1
Content-Type: application/json

{
  "message": "请生成更多候选选题",
  "context": {
    "stage": "creativity"
  }
}
```

**响应**：

```json
{
  "code": 200,
  "data": {
    "message_id": "msg_abc123",
    "session_id": "sess_abc123",
    "response": "好的，我为您生成更多候选选题...",
    "agent_id": "orchestrator",
    "stage": "creativity",
    "created_at": "2026-06-20T10:30:00Z"
  }
}
```

### 7.2 获取对话历史

```http
GET /api/conversations/{session_id}/messages?page=1&page_size=50 HTTP/1.1
```

**响应**：

```json
{
  "code": 200,
  "data": {
    "messages": [
      {
        "message_id": "msg_001",
        "role": "user",
        "content": "我想写一篇关于 LLM 的硕士论文",
        "created_at": "2026-06-20T10:30:00Z"
      },
      {
        "message_id": "msg_002",
        "role": "assistant",
        "content": "好的，我来帮您规划...",
        "agent_id": "orchestrator",
        "created_at": "2026-06-20T10:30:05Z"
      }
    ],
    "total": 2,
    "page": 1,
    "page_size": 50
  }
}
```

### 7.3 删除消息

```http
DELETE /api/conversations/{session_id}/messages/{message_id} HTTP/1.1
```

### 7.4 清空对话

```http
POST /api/conversations/{session_id}/clear HTTP/1.1
```

---

## 8. Config API

### 8.1 获取配置

```http
GET /api/config HTTP/1.1
```

**响应**：

```json
{
  "code": 200,
  "data": {
    "models": [
      {"id": "gpt-4.1-mini", "name": "GPT-4.1 Mini", "enabled": true},
      {"id": "deepseek-v3.2", "name": "DeepSeek V3.2", "enabled": true}
    ],
    "step_models": {
      "orchestrator": {"confirm": "claude-sonnet-4.5"},
      "searcher": {"search": "deepseek-v3.2"}
    },
    "constraints": {
      "title_max_length": {"master": 25, "doctor": 30},
      "novelty_threshold": 60
    }
  }
}
```

### 8.2 更新配置

```http
PUT /api/config HTTP/1.1
Content-Type: application/json

{
  "models": [
    {"id": "gpt-4.1", "enabled": true}
  ]
}
```

### 8.3 获取模型列表

```http
GET /api/config/models HTTP/1.1
```

**响应**：

```json
{
  "code": 200,
  "data": {
    "models": [
      {
        "id": "gpt-4.1-mini",
        "name": "GPT-4.1 Mini",
        "provider": "openai",
        "enabled": true,
        "capabilities": ["streaming", "function_calling"],
        "max_tokens": 128000,
        "pricing": {"input": 0.15, "output": 0.6}
      },
      {
        "id": "deepseek-v3.2",
        "name": "DeepSeek V3.2",
        "provider": "deepseek",
        "enabled": true,
        "capabilities": ["streaming", "prompt_caching"],
        "max_tokens": 64000,
        "pricing": {"input": 0.14, "output": 0.28}
      }
    ]
  }
}
```

### 8.4 更新模型配置

```http
PUT /api/config/models/{model_id} HTTP/1.1
Content-Type: application/json

{
  "enabled": true,
  "api_key": "sk-..."
}
```

### 8.5 测试模型连接

```http
POST /api/config/models/{model_id}/test HTTP/1.1
```

**响应**：

```json
{
  "code": 200,
  "data": {
    "model_id": "gpt-4.1-mini",
    "status": "ok",
    "latency_ms": 350,
    "message": "连接成功"
  }
}
```

---

## 9. Agents API

### 9.1 列出 Agents

```http
GET /api/agents HTTP/1.1
```

**响应**：

```json
{
  "code": 200,
  "data": {
    "agents": [
      {
        "agent_id": "orchestrator",
        "name": "Orchestrator",
        "model": "claude-sonnet-4.5",
        "status": "healthy",
        "messages_count": 5
      },
      {
        "agent_id": "searcher",
        "name": "Searcher",
        "model": "deepseek-v3.2",
        "status": "healthy",
        "messages_count": 2
      }
    ]
  }
}
```

### 9.2 获取 Agent 详情

```http
GET /api/agents/{agent_id} HTTP/1.1
```

### 9.3 重置 Agent 上下文

```http
POST /api/agents/{agent_id}/reset HTTP/1.1
```

### 9.4 Agent 健康检查

```http
GET /api/agents/health HTTP/1.1
```

**响应**：

```json
{
  "code": 200,
  "data": {
    "total_agents": 6,
    "healthy_agents": 6,
    "agents": {
      "orchestrator": {"healthy": true, "model": "claude-sonnet-4.5"},
      "searcher": {"healthy": true, "model": "deepseek-v3.2"},
      "reasoner": {"healthy": true, "model": "deepseek-r2"},
      "critic": {"healthy": true, "model": "deepseek-r2"},
      "mentor": {"healthy": true, "model": "gpt-4.1"},
      "writer": {"healthy": true, "model": "claude-opus-4.5"}
    }
  }
}
```

---

## 10. SSE 流式接口

### 10.1 流式生成选题

```http
POST /api/stream/proposals HTTP/1.1
Content-Type: application/json
Accept: text/event-stream

{
  "session_id": "sess_abc123",
  "input": "我想写一篇关于大语言模型的硕士论文"
}
```

**SSE 事件流**：

```
event: connected
data: {"session_id": "sess_abc123", "stream_id": "stream_123"}

event: stage_start
data: {"stage": "info_confirm", "timestamp": "2026-06-20T10:30:00Z"}

event: agent_call
data: {"agent_id": "orchestrator", "purpose": "confirm_info"}

event: progress
data: {"stage": "info_confirm", "progress": 50, "message": "解析用户输入"}

event: stage_complete
data: {"stage": "info_confirm", "result": {"discipline": "计算机科学", "degree": "硕士"}}

event: stage_start
data: {"stage": "creativity"}

event: agent_call
data: {"agent_id": "searcher", "purpose": "search"}

event: agent_complete
data: {"agent_id": "searcher", "papers_count": 10}

event: agent_call
data: {"agent_id": "reasoner", "purpose": "creativity"}

event: token
data: {"content": "基于"}

event: token
data: {"content": "知识图谱"}

event: stage_complete
data: {"stage": "creativity", "candidates": [...]}

event: done
data: {"proposal_id": "prop_xyz789", "total_duration_ms": 15000}
```

### 10.2 流式对话

```http
POST /api/stream/conversations HTTP/1.1
Content-Type: application/json
Accept: text/event-stream

{
  "session_id": "sess_abc123",
  "message": "请详细说明第一个候选"
}
```

**SSE 事件流**：

```
event: connected
data: {"session_id": "sess_abc123"}

event: token
data: {"content": "好的"}

event: token
data: {"content": "，"}

event: token
data: {"content": "我来"}

event: token
data: {"content": "详细说明"}

event: done
data: {"message_id": "msg_123", "total_tokens": 150}
```

### 10.3 SSE 客户端示例

```javascript
// JavaScript SSE 客户端
const eventSource = new EventSource('/api/stream/proposals', {
  withCredentials: true
});

eventSource.addEventListener('stage_start', (event) => {
  const data = JSON.parse(event.data);
  console.log(`阶段开始: ${data.stage}`);
});

eventSource.addEventListener('stage_complete', (event) => {
  const data = JSON.parse(event.data);
  console.log(`阶段完成: ${data.stage}`, data.result);
});

eventSource.addEventListener('token', (event) => {
  const data = JSON.parse(event.data);
  document.getElementById('output').textContent += data.content;
});

eventSource.addEventListener('done', (event) => {
  const data = JSON.parse(event.data);
  console.log(`完成，耗时 ${data.total_duration_ms}ms`);
  eventSource.close();
});

eventSource.onerror = (error) => {
  console.error('SSE 错误:', error);
  eventSource.close();
};
```

```python
# Python SSE 客户端
import requests
import json

def stream_proposals(session_id: str, user_input: str):
    """流式生成选题"""
    response = requests.post(
        'http://localhost:8000/api/stream/proposals',
        json={
            'session_id': session_id,
            'input': user_input
        },
        stream=True
    )
    
    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('event: '):
                event_type = line[7:]
            elif line.startswith('data: '):
                data = json.loads(line[6:])
                
                if event_type == 'stage_complete':
                    print(f"阶段完成: {data['stage']}")
                elif event_type == 'token':
                    print(data['content'], end='', flush=True)
                elif event_type == 'done':
                    print(f"\n完成，耗时 {data['total_duration_ms']}ms")
                    break

stream_proposals('sess_abc123', '我想写一篇关于 LLM 的硕士论文')
```

---

## 11. WebSocket 接口

### 11.1 WebSocket 连接

```
ws://localhost:8000/ws?session_id=sess_abc123
```

### 11.2 消息格式

**客户端 → 服务端**：

```json
{
  "type": "message",
  "session_id": "sess_abc123",
  "content": "请生成选题",
  "options": {...}
}
```

**服务端 → 客户端**：

```json
{
  "type": "response",
  "session_id": "sess_abc123",
  "content": "好的，我来生成选题...",
  "agent_id": "orchestrator",
  "timestamp": "2026-06-20T10:30:00Z"
}
```

### 11.3 事件类型

| 事件类型 | 方向 | 说明 |
|----------|------|------|
| `message` | C→S | 用户消息 |
| `response` | S→C | AI 响应 |
| `stage_start` | S→C | 阶段开始 |
| `stage_complete` | S→C | 阶段完成 |
| `token` | S→C | 流式 token |
| `error` | S→C | 错误 |
| `ping` | C→S | 心跳 |
| `pong` | S→C | 心跳响应 |

### 11.4 WebSocket 客户端示例

```javascript
// JavaScript WebSocket 客户端
const ws = new WebSocket('ws://localhost:8000/ws?session_id=sess_abc123');

ws.onopen = () => {
  console.log('WebSocket 连接已建立');
  
  // 发送消息
  ws.send(JSON.stringify({
    type: 'message',
    session_id: 'sess_abc123',
    content: '请生成选题'
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch (data.type) {
    case 'response':
      console.log('AI 响应:', data.content);
      break;
    case 'stage_start':
      console.log('阶段开始:', data.stage);
      break;
    case 'token':
      document.getElementById('output').textContent += data.content;
      break;
    case 'error':
      console.error('错误:', data.message);
      break;
  }
};

ws.onerror = (error) => {
  console.error('WebSocket 错误:', error);
};

ws.onclose = () => {
  console.log('WebSocket 连接已关闭');
};

// 心跳
setInterval(() => {
  ws.send(JSON.stringify({type: 'ping'}));
}, 30000);
```

```python
# Python WebSocket 客户端
import asyncio
import websockets
import json

async def websocket_client():
    """WebSocket 客户端"""
    uri = 'ws://localhost:8000/ws?session_id=sess_abc123'
    
    async with websockets.connect(uri) as ws:
        # 发送消息
        await ws.send(json.dumps({
            'type': 'message',
            'session_id': 'sess_abc123',
            'content': '请生成选题'
        }))
        
        # 接收消息
        while True:
            message = await ws.recv()
            data = json.loads(message)
            
            if data['type'] == 'response':
                print(f"AI: {data['content']}")
            elif data['type'] == 'token':
                print(data['content'], end='', flush=True)
            elif data['type'] == 'error':
                print(f"错误: {data['message']}")
                break

asyncio.run(websocket_client())
```

---

## 12. SDK 参考

### 12.1 Python SDK

```python
# thesisminer_sdk.py
import requests
from typing import Dict, List, Optional, AsyncGenerator

class ThesisMinerClient:
    """ThesisMiner Python SDK"""
    
    def __init__(self, base_url: str = 'http://localhost:8000', token: str = None):
        self.base_url = base_url
        self.session = requests.Session()
        if token:
            self.session.headers['Authorization'] = f'Bearer {token}'
    
    # === Sessions ===
    def create_session(self, user_id: str, metadata: dict = None) -> dict:
        """创建会话"""
        response = self.session.post(
            f'{self.base_url}/api/sessions',
            json={'user_id': user_id, 'metadata': metadata or {}}
        )
        return response.json()['data']
    
    def get_session(self, session_id: str) -> dict:
        """获取会话"""
        response = self.session.get(f'{self.base_url}/api/sessions/{session_id}')
        return response.json()['data']
    
    def list_sessions(self, user_id: str, page: int = 1, page_size: int = 20) -> dict:
        """列出会话"""
        response = self.session.get(
            f'{self.base_url}/api/sessions',
            params={'user_id': user_id, 'page': page, 'page_size': page_size}
        )
        return response.json()['data']
    
    def delete_session(self, session_id: str) -> dict:
        """删除会话"""
        response = self.session.delete(f'{self.base_url}/api/sessions/{session_id}')
        return response.json()
    
    def reset_session(self, session_id: str) -> dict:
        """重置会话"""
        response = self.session.post(f'{self.base_url}/api/sessions/{session_id}/reset')
        return response.json()['data']
    
    # === Proposals ===
    def generate_proposal(
        self,
        session_id: str,
        user_input: str,
        granularity: str = 'full',
        style: str = 'academic'
    ) -> dict:
        """生成选题"""
        response = self.session.post(
            f'{self.base_url}/api/proposals/generate',
            json={
                'session_id': session_id,
                'input': user_input,
                'options': {'granularity': granularity, 'style': style}
            }
        )
        return response.json()['data']
    
    def get_proposal(self, proposal_id: str) -> dict:
        """获取选题"""
        response = self.session.get(f'{self.base_url}/api/proposals/{proposal_id}')
        return response.json()['data']
    
    def list_proposals(self, session_id: str, page: int = 1, page_size: int = 20) -> dict:
        """列出选题"""
        response = self.session.get(
            f'{self.base_url}/api/proposals',
            params={'session_id': session_id, 'page': page, 'page_size': page_size}
        )
        return response.json()['data']
    
    def get_report(self, proposal_id: str, format: str = 'markdown') -> dict:
        """获取报告"""
        response = self.session.get(
            f'{self.base_url}/api/proposals/{proposal_id}/report',
            params={'format': format}
        )
        return response.json()['data']
    
    # === Conversations ===
    def send_message(self, session_id: str, message: str, context: dict = None) -> dict:
        """发送消息"""
        response = self.session.post(
            f'{self.base_url}/api/conversations/{session_id}/messages',
            json={'message': message, 'context': context or {}}
        )
        return response.json()['data']
    
    def get_messages(self, session_id: str, page: int = 1, page_size: int = 50) -> dict:
        """获取对话历史"""
        response = self.session.get(
            f'{self.base_url}/api/conversations/{session_id}/messages',
            params={'page': page, 'page_size': page_size}
        )
        return response.json()['data']
    
    # === Config ===
    def get_config(self) -> dict:
        """获取配置"""
        response = self.session.get(f'{self.base_url}/api/config')
        return response.json()['data']
    
    def get_models(self) -> dict:
        """获取模型列表"""
        response = self.session.get(f'{self.base_url}/api/config/models')
        return response.json()['data']
    
    def test_model(self, model_id: str) -> dict:
        """测试模型连接"""
        response = self.session.post(f'{self.base_url}/api/config/models/{model_id}/test')
        return response.json()['data']
    
    # === Agents ===
    def list_agents(self) -> dict:
        """列出 Agents"""
        response = self.session.get(f'{self.base_url}/api/agents')
        return response.json()['data']
    
    def get_agent(self, agent_id: str) -> dict:
        """获取 Agent 详情"""
        response = self.session.get(f'{self.base_url}/api/agents/{agent_id}')
        return response.json()['data']
    
    def reset_agent(self, agent_id: str) -> dict:
        """重置 Agent 上下文"""
        response = self.session.post(f'{self.base_url}/api/agents/{agent_id}/reset')
        return response.json()['data']
    
    def agents_health(self) -> dict:
        """Agent 健康检查"""
        response = self.session.get(f'{self.base_url}/api/agents/health')
        return response.json()['data']
```

### 12.2 SDK 使用示例

```python
# 使用 SDK
from thesisminer_sdk import ThesisMinerClient

# 创建客户端
client = ThesisMinerClient(base_url='http://localhost:8000')

# 创建会话
session = client.create_session(user_id='user_123')
print(f"会话 ID: {session['session_id']}")

# 生成选题
proposal = client.generate_proposal(
    session_id=session['session_id'],
    user_input='我想写一篇关于大语言模型的硕士论文',
    granularity='full'
)

print(f"选题 ID: {proposal['proposal_id']}")
print(f"候选数: {len(proposal['stages']['creativity']['candidates'])}")

# 获取报告
report = client.get_report(proposal['proposal_id'])
print(f"报告字数: {report['word_count']}")
print(report['content'][:500])

# 对话
response = client.send_message(
    session_id=session['session_id'],
    message='请详细说明第一个候选'
)
print(f"AI 响应: {response['response']}")

# 查看对话历史
messages = client.get_messages(session['session_id'])
for msg in messages['messages']:
    print(f"[{msg['role']}] {msg['content'][:100]}")

# 查看 Agents 状态
agents = client.list_agents()
for agent in agents['agents']:
    print(f"{agent['agent_id']}: {agent['status']}")

# 清理
client.delete_session(session['session_id'])
```

### 12.3 JavaScript SDK

```javascript
// thesisminer-sdk.js
class ThesisMinerClient {
  constructor(baseUrl = 'http://localhost:8000', token = null) {
    this.baseUrl = baseUrl;
    this.headers = {
      'Content-Type': 'application/json'
    };
    if (token) {
      this.headers['Authorization'] = `Bearer ${token}`;
    }
  }

  // === Sessions ===
  async createSession(userId, metadata = {}) {
    const response = await fetch(`${this.baseUrl}/api/sessions`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify({ user_id: userId, metadata })
    });
    const data = await response.json();
    return data.data;
  }

  async getSession(sessionId) {
    const response = await fetch(`${this.baseUrl}/api/sessions/${sessionId}`, {
      headers: this.headers
    });
    const data = await response.json();
    return data.data;
  }

  async deleteSession(sessionId) {
    const response = await fetch(`${this.baseUrl}/api/sessions/${sessionId}`, {
      method: 'DELETE',
      headers: this.headers
    });
    return response.json();
  }

  // === Proposals ===
  async generateProposal(sessionId, userInput, options = {}) {
    const response = await fetch(`${this.baseUrl}/api/proposals/generate`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify({
        session_id: sessionId,
        input: userInput,
        options
      })
    });
    const data = await response.json();
    return data.data;
  }

  // === Conversations ===
  async sendMessage(sessionId, message, context = {}) {
    const response = await fetch(`${this.baseUrl}/api/conversations/${sessionId}/messages`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify({ message, context })
    });
    const data = await response.json();
    return data.data;
  }

  // === Streaming ===
  streamProposal(sessionId, userInput, callbacks = {}) {
    const eventSource = new EventSource(
      `${this.baseUrl}/api/stream/proposals?session_id=${sessionId}&input=${encodeURIComponent(userInput)}`
    );
    
    eventSource.addEventListener('stage_start', (e) => {
      if (callbacks.onStageStart) callbacks.onStageStart(JSON.parse(e.data));
    });
    
    eventSource.addEventListener('stage_complete', (e) => {
      if (callbacks.onStageComplete) callbacks.onStageComplete(JSON.parse(e.data));
    });
    
    eventSource.addEventListener('token', (e) => {
      if (callbacks.onToken) callbacks.onToken(JSON.parse(e.data));
    });
    
    eventSource.addEventListener('done', (e) => {
      if (callbacks.onDone) callbacks.onDone(JSON.parse(e.data));
      eventSource.close();
    });
    
    eventSource.onerror = (error) => {
      if (callbacks.onError) callbacks.onError(error);
      eventSource.close();
    };
    
    return eventSource;
  }
}

// 导出
if (typeof module !== 'undefined' && module.exports) {
  module.exports = ThesisMinerClient;
}
```

### 12.4 JavaScript SDK 使用示例

```javascript
// 使用 SDK
const client = new ThesisMinerClient('http://localhost:8000');

// 创建会话
const session = await client.createSession('user_123');
console.log(`会话 ID: ${session.session_id}`);

// 流式生成选题
client.streamProposal(
  session.session_id,
  '我想写一篇关于大语言模型的硕士论文',
  {
    onStageStart: (data) => console.log(`阶段开始: ${data.stage}`),
    onStageComplete: (data) => console.log(`阶段完成: ${data.stage}`),
    onToken: (data) => process.stdout.write(data.content),
    onDone: (data) => console.log(`\n完成，耗时 ${data.total_duration_ms}ms`),
    onError: (error) => console.error('错误:', error)
  }
);
```

---

## 13. 错误码

### 13.1 HTTP 状态码

| 状态码 | 名称 | 说明 |
|--------|------|------|
| 200 | OK | 请求成功 |
| 201 | Created | 资源创建成功 |
| 400 | Bad Request | 请求参数错误 |
| 401 | Unauthorized | 未认证 |
| 403 | Forbidden | 无权限 |
| 404 | Not Found | 资源不存在 |
| 429 | Too Many Requests | 请求频率超限 |
| 500 | Internal Server Error | 服务器内部错误 |
| 503 | Service Unavailable | 服务不可用 |

### 13.2 业务错误码

| 错误码 | 名称 | 说明 |
|--------|------|------|
| 1001 | SESSION_NOT_FOUND | 会话不存在 |
| 1002 | SESSION_EXPIRED | 会话已过期 |
| 1003 | SESSION_LIMIT_EXCEEDED | 会话数量超限 |
| 2001 | PROPOSAL_NOT_FOUND | 选题不存在 |
| 2002 | PROPOSAL_GENERATION_FAILED | 选题生成失败 |
| 2003 | PROPOSAL_VALIDATION_FAILED | 选题验证失败 |
| 3001 | AGENT_NOT_FOUND | Agent 不存在 |
| 3002 | AGENT_TIMEOUT | Agent 超时 |
| 3003 | AGENT_RATE_LIMIT | Agent 限流 |
| 3004 | AGENT_JSON_PARSE | JSON 解析失败 |
| 3005 | MODEL_UNAVAILABLE | 模型不可用 |
| 4001 | CONFIG_INVALID | 配置无效 |
| 4002 | MODEL_NOT_CONFIGURED | 模型未配置 |
| 4003 | API_KEY_MISSING | API Key 缺失 |
| 5001 | CONSTRAINT_VIOLATION | 约束违反 |
| 5002 | NOVELTY_TOO_LOW | 新颖性过低 |
| 5003 | DUPLICATION_TOO_HIGH | 查重率过高 |

### 13.3 错误响应示例

```json
{
  "code": 400,
  "message": "Bad Request",
  "error": {
    "type": "ValidationError",
    "code": 1001,
    "details": "会话 sess_xxx 不存在",
    "field": "session_id"
  },
  "timestamp": "2026-06-20T10:30:00Z",
  "request_id": "req_abc123"
}
```

### 13.4 错误处理示例

```python
# Python 错误处理
from thesisminer_sdk import ThesisMinerClient

client = ThesisMinerClient()

try:
    proposal = client.generate_proposal(
        session_id='sess_invalid',
        user_input='测试'
    )
except requests.exceptions.HTTPError as e:
    error_data = e.response.json()
    print(f"错误码: {error_data['error']['code']}")
    print(f"错误信息: {error_data['error']['details']}")
    
    if error_data['error']['code'] == 1001:
        print("会话不存在，请重新创建")
    elif error_data['error']['code'] == 2002:
        print("生成失败，请重试")
```

```javascript
// JavaScript 错误处理
try {
  const proposal = await client.generateProposal('sess_invalid', '测试');
} catch (error) {
  const errorData = error.response.data;
  console.error(`错误码: ${errorData.error.code}`);
  console.error(`错误信息: ${errorData.error.details}`);
  
  if (errorData.error.code === 1001) {
    console.log('会话不存在，请重新创建');
  }
}
```

---

## 14. 附录

### 14.1 API 速查表

```
┌─────────────────────────────────────────────────────────────────┐
│                    API 速查表                                     │
├──────────────────┬──────────────────────────┬──────────────────┤
│ 端点             │ 方法                     │ 说明             │
├──────────────────┼──────────────────────────┼──────────────────┤
│ /api/sessions    │ POST                     │ 创建会话         │
│ /api/sessions/{id}│ GET / PATCH / DELETE    │ 会话 CRUD        │
│ /api/sessions/{id}/reset│ POST              │ 重置会话         │
├──────────────────┼──────────────────────────┼──────────────────┤
│ /api/proposals/generate│ POST                │ 生成选题         │
│ /api/proposals/{id}│ GET                    │ 获取选题         │
│ /api/proposals   │ GET                      │ 列出选题         │
│ /api/proposals/{id}/report│ GET             │ 获取报告         │
├──────────────────┼──────────────────────────┼──────────────────┤
│ /api/conversations/{id}/messages│ POST / GET│ 消息管理         │
│ /api/conversations/{id}/clear│ POST         │ 清空对话         │
├──────────────────┼──────────────────────────┼──────────────────┤
│ /api/config      │ GET / PUT                │ 配置管理         │
│ /api/config/models│ GET / PUT               │ 模型管理         │
│ /api/config/models/{id}/test│ POST          │ 测试模型         │
├──────────────────┼──────────────────────────┼──────────────────┤
│ /api/agents      │ GET                      │ 列出 Agents      │
│ /api/agents/{id} │ GET                      │ Agent 详情       │
│ /api/agents/{id}/reset│ POST                 │ 重置 Agent       │
│ /api/agents/health│ GET                     │ 健康检查         │
├──────────────────┼──────────────────────────┼──────────────────┤
│ /api/stream/proposals│ POST (SSE)           │ 流式生成         │
│ /api/stream/conversations│ POST (SSE)       │ 流式对话         │
├──────────────────┼──────────────────────────┼──────────────────┤
│ /ws              │ WebSocket                │ 实时通信         │
└──────────────────┴──────────────────────────┴──────────────────┘
```

### 14.2 常用 cURL 命令

```bash
# 创建会话
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user_123"}'

# 生成选题
curl -X POST http://localhost:8000/api/proposals/generate \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_abc123",
    "input": "我想写一篇关于大语言模型的硕士论文"
  }'

# 流式生成
curl -X POST http://localhost:8000/api/stream/proposals \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "session_id": "sess_abc123",
    "input": "我想写一篇关于大语言模型的硕士论文"
  }'

# 获取模型列表
curl http://localhost:8000/api/config/models

# Agent 健康检查
curl http://localhost:8000/api/agents/health
```

### 14.3 Postman 集合

```json
{
  "info": {
    "name": "ThesisMiner API",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "variable": [
    {
      "key": "base_url",
      "value": "http://localhost:8000"
    },
    {
      "key": "session_id",
      "value": ""
    }
  ],
  "item": [
    {
      "name": "Create Session",
      "request": {
        "method": "POST",
        "url": "{{base_url}}/api/sessions",
        "body": {
          "mode": "raw",
          "raw": "{\"user_id\": \"user_123\"}"
        }
      }
    },
    {
      "name": "Generate Proposal",
      "request": {
        "method": "POST",
        "url": "{{base_url}}/api/proposals/generate",
        "body": {
          "mode": "raw",
          "raw": "{\"session_id\": \"{{session_id}}\", \"input\": \"测试\"}"
        }
      }
    }
  ]
}
```

### 14.4 相关文档

- [Agent 参考](agent_reference.md)
- [约束规则参考](constraint_reference.md)
- [配置参考](configuration_reference.md)
- [故障排查参考](troubleshooting_reference.md)
- [API 教程](../tutorials/api_tutorial.md)
- [OpenAPI 规范](../api/openapi.yaml)
- [错误码](../api/error_codes.md)
- [限流策略](../api/rate_limiting.md)

### 14.5 术语表

| 术语 | 英文 | 含义 |
|------|------|------|
| 端点 | Endpoint | API 的访问地址 |
| 会话 | Session | 用户与系统的交互会话 |
| 选题 | Proposal | 生成的论文选题 |
| 对话 | Conversation | 用户与 Agent 的对话 |
| 流式 | Streaming | 实时流式返回 |
| 限流 | Rate Limiting | 限制请求频率 |
| SSE | Server-Sent Events | 服务器发送事件 |
| WebSocket | WebSocket | 全双工通信协议 |
| SDK | Software Development Kit | 软件开发工具包 |

### 14.6 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v8.0.0 | 2026-06-20 | 初始版本 |
| v7.5.0 | 2026-05-15 | 添加 SSE 流式接口 |
| v7.0.0 | 2026-04-01 | 重构为 FastAPI |
| v6.0.0 | 2026-02-10 | 添加 WebSocket |

---

## 15. API 详细规范

### 15.1 Sessions API 详细规范

#### 15.1.1 创建会话

**端点**：`POST /api/sessions`

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user_id | string | 是 | 用户 ID |
| metadata | object | 否 | 元数据 |

**请求示例**：

```json
{
  "user_id": "user_123",
  "metadata": {
    "source": "web",
    "version": "8.0.0",
    "user_agent": "Mozilla/5.0..."
  }
}
```

**响应字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| session_id | string | 会话 ID |
| user_id | string | 用户 ID |
| created_at | string | 创建时间 |
| status | string | 状态（active/inactive/closed） |
| current_stage | string | 当前阶段 |

**状态码**：

| 状态码 | 说明 |
|--------|------|
| 201 | 创建成功 |
| 400 | 参数错误 |
| 429 | 请求频率超限 |

#### 15.1.2 获取会话

**端点**：`GET /api/sessions/{session_id}`

**路径参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| session_id | string | 是 | 会话 ID |

**响应字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| session_id | string | 会话 ID |
| user_id | string | 用户 ID |
| created_at | string | 创建时间 |
| updated_at | string | 更新时间 |
| status | string | 状态 |
| current_stage | string | 当前阶段 |
| stage_results | object | 各阶段结果 |
| metadata | object | 元数据 |

#### 15.1.3 列出会话

**端点**：`GET /api/sessions`

**查询参数**：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| user_id | string | 否 | - | 用户 ID（筛选） |
| status | string | 否 | - | 状态（筛选） |
| page | int | 否 | 1 | 页码 |
| page_size | int | 否 | 20 | 每页数量（最大 100） |
| sort | string | 否 | created_at | 排序字段 |
| order | string | 否 | desc | 排序方向（asc/desc） |

### 15.2 Proposals API 详细规范

#### 15.2.1 生成选题

**端点**：`POST /api/proposals/generate`

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| session_id | string | 是 | 会话 ID |
| input | string | 是 | 用户输入 |
| options | object | 否 | 生成选项 |

**options 字段**：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| granularity | string | full | 粒度（title/abstract/outline/full） |
| style | string | academic | 风格 |
| max_candidates | int | 5 | 最大候选数 |
| skip_validation | bool | false | 跳过验证 |
| model | string | - | 指定模型 |

**响应字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| proposal_id | string | 选题 ID |
| session_id | string | 会话 ID |
| status | string | 状态 |
| stages | object | 各阶段结果 |
| created_at | string | 创建时间 |

**stages 字段结构**：

```json
{
  "info_confirm": {
    "discipline": "计算机科学",
    "degree": "硕士",
    "direction": "大语言模型",
    "complete": true
  },
  "creativity": {
    "candidates": [
      {
        "title": "...",
        "dimension": "...",
        "innovation": "..."
      }
    ]
  },
  "validation": {
    "evaluations": [
      {
        "title": "...",
        "score": 85,
        "passed": true
      }
    ]
  },
  "generation": {
    "report": "...",
    "word_count": 12000
  }
}
```

#### 15.2.2 流式生成选题

**端点**：`POST /api/proposals/generate?stream=true`

**SSE 事件类型**：

| 事件 | 说明 |
|------|------|
| connected | 连接成功 |
| stage_start | 阶段开始 |
| stage_complete | 阶段完成 |
| agent_call | Agent 调用 |
| agent_complete | Agent 完成 |
| progress | 进度更新 |
| token | 流式 token |
| error | 错误 |
| done | 完成 |

### 15.3 Conversations API 详细规范

#### 15.3.1 发送消息

**端点**：`POST /api/conversations/{session_id}/messages`

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| message | string | 是 | 消息内容 |
| context | object | 否 | 上下文 |

**context 字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| stage | string | 当前阶段 |
| agent_id | string | 指定 Agent |
| model | string | 指定模型 |

**响应字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| message_id | string | 消息 ID |
| session_id | string | 会话 ID |
| response | string | AI 响应 |
| agent_id | string | 响应 Agent |
| stage | string | 当前阶段 |
| created_at | string | 创建时间 |

### 15.4 Config API 详细规范

#### 15.4.1 获取配置

**端点**：`GET /api/config`

**响应字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| models | array | 模型列表 |
| step_models | object | 按用途路由的模型 |
| constraints | object | 约束配置 |
| agents | object | Agent 配置 |

#### 15.4.2 模型配置

**模型对象字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 模型 ID |
| name | string | 模型名称 |
| provider | string | 提供商 |
| enabled | bool | 是否启用 |
| capabilities | array | 能力列表 |
| max_tokens | int | 最大 token |
| pricing | object | 定价 |

### 15.5 Agents API 详细规范

#### 15.5.1 Agent 对象

```json
{
  "agent_id": "orchestrator",
  "name": "Orchestrator",
  "model": "claude-sonnet-4.5",
  "temperature": 0.3,
  "max_tokens": 4096,
  "status": "healthy",
  "messages_count": 5,
  "capabilities": ["streaming", "thinking"],
  "last_active": "2026-06-20T10:30:00Z"
}
```

#### 15.5.2 健康检查响应

```json
{
  "total_agents": 6,
  "healthy_agents": 6,
  "agents": {
    "orchestrator": {
      "healthy": true,
      "model": "claude-sonnet-4.5",
      "messages_count": 5,
      "last_active": "2026-06-20T10:30:00Z"
    }
  }
}
```

### 15.6 SSE 接口详细规范

#### 15.6.1 SSE 事件格式

```
event: <event_type>
data: <json_data>

```

#### 15.6.2 事件类型详解

**connected 事件**：

```
event: connected
data: {
  "session_id": "sess_abc123",
  "stream_id": "stream_123",
  "timestamp": "2026-06-20T10:30:00Z"
}
```

**stage_start 事件**：

```
event: stage_start
data: {
  "stage": "creativity",
  "timestamp": "2026-06-20T10:30:00Z",
  "expected_duration_ms": 5000
}
```

**stage_complete 事件**：

```
event: stage_complete
data: {
  "stage": "creativity",
  "result": {...},
  "duration_ms": 4500,
  "timestamp": "2026-06-20T10:30:05Z"
}
```

**agent_call 事件**：

```
event: agent_call
data: {
  "agent_id": "searcher",
  "purpose": "search",
  "model": "deepseek-v3.2",
  "timestamp": "2026-06-20T10:30:01Z"
}
```

**agent_complete 事件**：

```
event: agent_complete
data: {
  "agent_id": "searcher",
  "success": true,
  "duration_ms": 2000,
  "token_usage": {
    "prompt_tokens": 500,
    "completion_tokens": 300,
    "total_tokens": 800
  }
}
```

**progress 事件**：

```
event: progress
data: {
  "stage": "creativity",
  "progress": 50,
  "message": "正在生成候选..."
}
```

**token 事件**：

```
event: token
data: {
  "content": "基于",
  "agent_id": "writer",
  "index": 0
}
```

**error 事件**：

```
event: error
data: {
  "type": "AgentTimeoutError",
  "message": "Agent 超时",
  "stage": "creativity",
  "retry": true
}
```

**done 事件**：

```
event: done
data: {
  "proposal_id": "prop_xyz789",
  "total_duration_ms": 15000,
  "total_tokens": 5000,
  "stages_completed": ["info_confirm", "creativity", "validation", "generation"]
}
```

### 15.7 WebSocket 接口详细规范

#### 15.7.1 连接建立

```
ws://localhost:8000/ws?session_id=sess_abc123&token=xxx
```

**连接参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| session_id | string | 是 | 会话 ID |
| token | string | 否 | 认证 token |

#### 15.7.2 消息类型

**客户端消息**：

```json
{
  "type": "message",
  "session_id": "sess_abc123",
  "content": "请生成选题",
  "options": {
    "granularity": "full",
    "stream": true
  }
}
```

**服务端消息**：

```json
{
  "type": "response",
  "session_id": "sess_abc123",
  "content": "好的，我来生成选题...",
  "agent_id": "orchestrator",
  "stage": "info_confirm",
  "timestamp": "2026-06-20T10:30:00Z"
}
```

#### 15.7.3 心跳机制

**客户端心跳**：

```json
{"type": "ping"}
```

**服务端响应**：

```json
{"type": "pong", "timestamp": "2026-06-20T10:30:00Z"}
```

**心跳间隔**：30 秒

**超时断开**：90 秒无心跳则断开

### 15.8 API 安全

#### 15.8.1 CORS 配置

```yaml
# config/system.yaml
cors:
  enabled: true
  allow_origins:
    - "http://localhost:3000"
    - "https://thesisminer.example.com"
  allow_methods: ["GET", "POST", "PUT", "PATCH", "DELETE"]
  allow_headers: ["*"]
  allow_credentials: true
  max_age: 3600
```

#### 15.8.2 输入验证

```python
from pydantic import BaseModel, validator

class CreateSessionRequest(BaseModel):
    """创建会话请求"""
    user_id: str
    metadata: dict = {}
    
    @validator('user_id')
    def validate_user_id(cls, v):
        if not v or len(v) > 100:
            raise ValueError('user_id 不能为空且不超过 100 字符')
        return v

class GenerateProposalRequest(BaseModel):
    """生成选题请求"""
    session_id: str
    input: str
    options: dict = {}
    
    @validator('input')
    def validate_input(cls, v):
        if not v or len(v) > 10000:
            raise ValueError('input 不能为空且不超过 10000 字符')
        return v
```

#### 15.8.3 SQL 注入防护

```python
# 使用参数化查询
async def get_session(session_id: str):
    """获取会话（防 SQL 注入）"""
    query = "SELECT * FROM sessions WHERE session_id = ?"
    result = await db.execute(query, (session_id,))
    return result.fetchone()
```

### 15.9 API 性能

#### 15.9.1 性能指标

| 端点 | 平均响应时间 | P95 响应时间 | 吞吐量 |
|------|-------------|-------------|--------|
| POST /api/sessions | 50ms | 100ms | 1000 req/s |
| GET /api/sessions/{id} | 30ms | 60ms | 2000 req/s |
| POST /api/proposals/generate | 15000ms | 30000ms | 10 req/s |
| POST /api/conversations/{id}/messages | 3000ms | 8000ms | 50 req/s |
| GET /api/config | 20ms | 40ms | 5000 req/s |
| GET /api/agents/health | 50ms | 100ms | 1000 req/s |

#### 15.9.2 性能优化

```python
# 1. 数据库索引
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_status ON sessions(status);
CREATE INDEX idx_proposals_session_id ON proposals(session_id);

# 2. 缓存
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_cached_config() -> dict:
    """缓存配置"""
    return load_config()

# 3. 分页
async def list_sessions(user_id: str, page: int, page_size: int):
    """分页查询"""
    offset = (page - 1) * page_size
    query = "SELECT * FROM sessions WHERE user_id = ? LIMIT ? OFFSET ?"
    return await db.execute(query, (user_id, page_size, offset))

# 4. 异步处理
async def generate_proposal_async(session_id: str, input: str):
    """异步生成选题"""
    task = asyncio.create_task(_generate(session_id, input))
    return {"task_id": task.get_name(), "status": "processing"}
```

### 15.10 API 测试

#### 15.10.1 单元测试

```python
# tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

class TestSessionsAPI:
    """Sessions API 测试"""
    
    def test_create_session(self):
        """测试创建会话"""
        response = client.post('/api/sessions', json={
            'user_id': 'user_123'
        })
        assert response.status_code == 201
        data = response.json()['data']
        assert 'session_id' in data
        assert data['status'] == 'active'
    
    def test_get_session(self):
        """测试获取会话"""
        # 先创建
        create_response = client.post('/api/sessions', json={'user_id': 'user_123'})
        session_id = create_response.json()['data']['session_id']
        
        # 再获取
        response = client.get(f'/api/sessions/{session_id}')
        assert response.status_code == 200
        assert response.json()['data']['session_id'] == session_id
    
    def test_delete_session(self):
        """测试删除会话"""
        # 先创建
        create_response = client.post('/api/sessions', json={'user_id': 'user_123'})
        session_id = create_response.json()['data']['session_id']
        
        # 再删除
        response = client.delete(f'/api/sessions/{session_id}')
        assert response.status_code == 200
        
        # 验证已删除
        get_response = client.get(f'/api/sessions/{session_id}')
        assert get_response.status_code == 404

class TestProposalsAPI:
    """Proposals API 测试"""
    
    def test_generate_proposal(self):
        """测试生成选题"""
        # 先创建会话
        session = client.post('/api/sessions', json={'user_id': 'user_123'}).json()['data']
        
        # 生成选题
        response = client.post('/api/proposals/generate', json={
            'session_id': session['session_id'],
            'input': '我想写一篇关于大语言模型的硕士论文'
        })
        assert response.status_code == 200
        data = response.json()['data']
        assert 'proposal_id' in data
        assert 'stages' in data

class TestConfigAPI:
    """Config API 测试"""
    
    def test_get_config(self):
        """测试获取配置"""
        response = client.get('/api/config')
        assert response.status_code == 200
        data = response.json()['data']
        assert 'models' in data
    
    def test_get_models(self):
        """测试获取模型列表"""
        response = client.get('/api/config/models')
        assert response.status_code == 200
        data = response.json()['data']
        assert 'models' in data
        assert len(data['models']) > 0

class TestAgentsAPI:
    """Agents API 测试"""
    
    def test_list_agents(self):
        """测试列出 Agents"""
        response = client.get('/api/agents')
        assert response.status_code == 200
        data = response.json()['data']
        assert 'agents' in data
        assert len(data['agents']) == 6
    
    def test_agents_health(self):
        """测试 Agent 健康检查"""
        response = client.get('/api/agents/health')
        assert response.status_code == 200
        data = response.json()['data']
        assert data['total_agents'] == 6
        assert data['healthy_agents'] == 6
```

#### 15.10.2 集成测试

```python
# tests/test_api_integration.py
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

@pytest.mark.asyncio
async def test_full_workflow():
    """测试完整工作流"""
    # 1. 创建会话
    session = client.post('/api/sessions', json={
        'user_id': 'user_123'
    }).json()['data']
    
    # 2. 生成选题
    proposal = client.post('/api/proposals/generate', json={
        'session_id': session['session_id'],
        'input': '我想写一篇关于大语言模型的硕士论文'
    }).json()['data']
    
    # 3. 获取报告
    report = client.get(f'/api/proposals/{proposal["proposal_id"]}/report').json()['data']
    assert report['word_count'] > 0
    
    # 4. 对话
    response = client.post(f'/api/conversations/{session["session_id"]}/messages', json={
        'message': '请详细说明第一个候选'
    }).json()['data']
    assert 'response' in response
    
    # 5. 清理
    client.delete(f'/api/sessions/{session["session_id"]}')
```

### 15.11 API 版本管理

#### 15.11.1 版本策略

```
/api/v1/sessions     # v1 版本
/api/v2/sessions     # v2 版本
/api/sessions        # 最新版本
```

#### 15.11.2 版本兼容性

| 版本 | 状态 | 支持时间 |
|------|------|----------|
| v8.0 | 当前版本 | - |
| v7.x | 维护中 | 2026-12-31 |
| v6.x | 已弃用 | 2026-06-30 |

### 15.12 API 文档生成

```python
# 自动生成 OpenAPI 文档
from fastapi import FastAPI

app = FastAPI(
    title="ThesisMiner API",
    version="8.0.0",
    description="ThesisMiner 多 Agent 选题导航系统 API",
    docs_url="/docs",        # Swagger UI
    redoc_url="/redoc",      # ReDoc
    openapi_url="/openapi.json"
)

# 访问：
# http://localhost:8000/docs     - Swagger UI
# http://localhost:8000/redoc    - ReDoc
# http://localhost:8000/openapi.json - OpenAPI 规范
```

### 15.13 API 监控

#### 15.13.1 指标收集

```python
# backend/observability/api_metrics.py
from prometheus_client import Counter, Histogram, Gauge

# API 请求次数
api_requests = Counter(
    "thesisminer_api_requests_total",
    "API 请求总次数",
    ["method", "endpoint", "status"]
)

# API 响应时间
api_duration = Histogram(
    "thesisminer_api_duration_seconds",
    "API 响应时间",
    ["method", "endpoint"],
    buckets=[0.1, 0.5, 1, 5, 10, 30, 60]
)

# 活跃连接数
active_connections = Gauge(
    "thesisminer_active_connections",
    "活跃连接数"
)
```

#### 15.13.2 日志记录

```python
# API 请求日志
{
    "timestamp": "2026-06-20T10:30:00Z",
    "level": "INFO",
    "method": "POST",
    "endpoint": "/api/proposals/generate",
    "status": 200,
    "duration_ms": 15000,
    "request_id": "req_abc123",
    "user_id": "user_123",
    "session_id": "sess_abc123",
    "ip": "192.168.1.1",
    "user_agent": "Mozilla/5.0..."
}
```

### 15.14 API 部署

#### 15.14.1 生产环境配置

```yaml
# config/production/api.yaml
api:
  host: 0.0.0.0
  port: 8000
  workers: 4              # worker 数量
  reload: false           # 生产环境关闭热重载
  
  # 超时
  timeout:
    keep_alive: 30        # keep-alive 超时
    request: 120          # 请求超时（秒）
    response: 120         # 响应超时
  
  # 限流
  rate_limiting:
    enabled: true
    default_limit: 60
    burst_limit: 10
  
  # CORS
  cors:
    enabled: true
    allow_origins:
      - "https://thesisminer.example.com"
  
  # HTTPS
  https:
    enabled: true
    cert_file: "/etc/ssl/cert.pem"
    key_file: "/etc/ssl/key.pem"
```

#### 15.14.2 启动命令

```bash
# 开发环境
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 生产环境
gunicorn backend.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# Docker
docker run -p 8000:8000 thesisminer:8.0.0
```

### 15.15 API 客户端配置

#### 15.15.1 超时配置

```python
# Python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()

# 重试策略
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[500, 502, 503, 504]
)

adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("http://", adapter)
session.mount("https://", adapter)

# 超时
session.timeout = 30  # 30 秒超时
```

```javascript
// JavaScript
const axios = require('axios');

const client = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 30000,  // 30 秒超时
  retry: 3,
  retryDelay: 1000
});
```

#### 15.15.2 错误重试

```python
# 自动重试
import time
from functools import wraps

def retry_on_failure(max_attempts=3, delay=1.0):
    """失败重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_attempts - 1:
                        time.sleep(delay * (2 ** attempt))
            raise last_error
        return wrapper
    return decorator

@retry_on_failure(max_attempts=3, delay=1.0)
def call_api():
    """调用 API（带重试）"""
    return requests.get('http://localhost:8000/api/health')
```

### 15.16 API 最佳实践

#### 15.16.1 请求优化

```python
# 1. 批量请求
def batch_create_sessions(user_ids: list):
    """批量创建会话"""
    responses = []
    for user_id in user_ids:
        response = client.post('/api/sessions', json={'user_id': user_id})
        responses.append(response)
    return responses

# 2. 并行请求
import asyncio
import aiohttp

async def parallel_requests():
    """并行请求"""
    async with aiohttp.ClientSession() as session:
        tasks = [
            session.get('http://localhost:8000/api/agents'),
            session.get('http://localhost:8000/api/config')
        ]
        results = await asyncio.gather(*tasks)
        return results

# 3. 连接复用
session = requests.Session()  # 复用 TCP 连接
```

#### 15.16.2 响应处理

```python
# 1. 流式处理
def stream_proposals(session_id: str, input: str):
    """流式处理响应"""
    response = requests.post(
        '/api/stream/proposals',
        json={'session_id': session_id, 'input': input},
        stream=True
    )
    
    for line in response.iter_lines():
        if line:
            process_line(line)

# 2. 分页处理
def get_all_sessions(user_id: str):
    """获取所有会话（自动分页）"""
    all_sessions = []
    page = 1
    
    while True:
        response = client.get('/api/sessions', params={
            'user_id': user_id,
            'page': page,
            'page_size': 100
        })
        data = response.json()['data']
        
        all_sessions.extend(data['sessions'])
        
        if len(data['sessions']) < 100:
            break  # 最后一页
        
        page += 1
    
    return all_sessions
```

### 15.17 API 调试

#### 15.17.1 调试工具

```bash
# 1. curl 调试
curl -v http://localhost:8000/api/health

# 2. httpie
http POST localhost:8000/api/sessions user_id=user_123

# 3. Swagger UI
# 访问 http://localhost:8000/docs

# 4. ReDoc
# 访问 http://localhost:8000/redoc
```

#### 15.17.2 日志调试

```python
# 启用调试日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 请求日志
import httpx
httpx.LogLevels.HTTPX = logging.DEBUG
```

### 15.18 API 限流详解

#### 15.18.1 令牌桶算法

```python
# backend/middleware/rate_limiting.py
import time
from collections import defaultdict

class TokenBucket:
    """令牌桶"""
    
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity        # 桶容量
        self.refill_rate = refill_rate  # 补充速率（令牌/秒）
        self.tokens = capacity          # 当前令牌数
        self.last_refill = time.time()  # 上次补充时间
    
    def consume(self, tokens: int = 1) -> bool:
        """消费令牌"""
        # 补充令牌
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
        
        # 消费
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

# 按用户限流
buckets = defaultdict(lambda: TokenBucket(capacity=60, refill_rate=1.0))

def rate_limit(user_id: str) -> bool:
    """限流检查"""
    bucket = buckets[user_id]
    return bucket.consume()
```

#### 15.18.2 限流策略

| 端点 | 限流策略 | 说明 |
|------|----------|------|
| /api/sessions | 60 req/min | 会话管理 |
| /api/proposals/generate | 10 req/min | 生成耗时 |
| /api/stream/* | 5 req/min | 流式连接 |
| /api/config | 100 req/min | 配置查询 |
| /api/agents/* | 60 req/min | Agent 管理 |

### 15.19 API 文档维护

#### 15.19.1 文档更新流程

```
[代码变更]
    │
    ▼
[更新 OpenAPI 注解]
    │
    ▼
[生成 OpenAPI 规范]
    │
    ▼
[更新本文档]
    │
    ▼
[Review & 合并]
```

#### 15.19.2 文档规范

1. **端点描述**：清晰说明端点用途
2. **参数说明**：每个参数都有说明
3. **示例完整**：请求和响应都有示例
4. **错误码全**：列出所有可能的错误码
5. **版本标注**：标注 API 版本

---

> **文档结束**
> 
> 如有疑问，请参考相关文档或提交 Issue。
