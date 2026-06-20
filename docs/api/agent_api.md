# ThesisMiner v8.0 Agent API 文档

> **版本**：v8.0
> **日期**：2026-06-19
> **适用范围**：`backend/routes/agents.py`
> **关联模块**：Agent 元数据查询、流式编排

---

## 目录

1. [API 总览](#1-api-总览)
2. [GET /api/agents - 获取所有 Agent](#2-get-apiagents---获取所有-agent)
3. [GET /api/agents/{agent_id} - 获取指定 Agent](#3-get-apiagentsagent_id---获取指定-agent)
4. [POST /api/agents/orchestrate - 流式编排](#4-post-apiagentsorchestrate---流式编排)
5. [Agent 元数据 Schema](#5-agent-元数据-schema)
6. [消息路由到指定 Agent](#6-消息路由到指定-agent)
7. [SSE 事件格式](#7-sse-事件格式)
8. [错误处理](#8-错误处理)
9. [示例](#9-示例)
10. [附录](#10-附录)

---

## 1. API 总览

### 1.1 端点清单

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/agents | 获取所有 Agent 元数据 |
| GET | /api/agents/{agent_id} | 获取指定 Agent 元数据 |
| POST | /api/agents/orchestrate | 流式编排端点（SSE） |

### 1.2 支持的 Agent

| Agent ID | 名称 | 模型 | 阶段 |
|----------|------|------|------|
| orchestrator | Orchestrator | claude-sonnet-4.5 | 全阶段调度 |
| searcher | Searcher | deepseek-v3.2 | 阶段一、三 |
| reasoner | Reasoner | deepseek-r2 | 阶段二 |
| critic | Critic | deepseek-r2 | 阶段三 |
| mentor | Mentor | gpt-4.1 | 阶段五 |
| writer | Writer | claude-opus-4.5 | 阶段四 |

---

## 2. GET /api/agents - 获取所有 Agent

### 2.1 请求

```http
GET /api/agents HTTP/1.1
Host: 127.0.0.1:8000
```

### 2.2 响应

```json
{
  "agents": [
    {
      "agent_id": "orchestrator",
      "name": "Orchestrator",
      "description": "主管理 Agent，调度五阶段流程",
      "model": "claude-sonnet-4.5",
      "temperature": 0.3,
      "max_tokens": 8192,
      "capabilities": ["streaming", "thinking", "web_search"],
      "stages": ["info_confirm", "creativity", "validation", "generation", "deep_assist"]
    },
    {
      "agent_id": "searcher",
      "name": "Searcher",
      "description": "检索 Agent，联网检索文献与新颖性评估",
      "model": "deepseek-v3.2",
      "temperature": 0.7,
      "max_tokens": 4096,
      "capabilities": ["streaming", "web_search"],
      "stages": ["info_confirm", "validation"]
    },
    {
      "agent_id": "reasoner",
      "name": "Reasoner",
      "description": "推理 Agent，四维创意生成",
      "model": "deepseek-r2",
      "temperature": 0.0,
      "max_tokens": 8192,
      "capabilities": ["streaming", "thinking"],
      "stages": ["creativity"]
    },
    {
      "agent_id": "critic",
      "name": "Critic",
      "description": "评审 Agent，硬约束校验与自动修复",
      "model": "deepseek-r2",
      "temperature": 0.0,
      "max_tokens": 4096,
      "capabilities": ["streaming", "thinking"],
      "stages": ["validation"]
    },
    {
      "agent_id": "mentor",
      "name": "Mentor",
      "description": "导师 Agent，导师视角评审与答辩预演",
      "model": "gpt-4.1",
      "temperature": 0.7,
      "max_tokens": 8192,
      "capabilities": ["streaming"],
      "stages": ["deep_assist"]
    },
    {
      "agent_id": "writer",
      "name": "Writer",
      "description": "写作 Agent，多粒度生成与降重脱敏",
      "model": "claude-opus-4.5",
      "temperature": 0.7,
      "max_tokens": 16384,
      "capabilities": ["streaming", "thinking"],
      "stages": ["generation"]
    }
  ],
  "count": 6
}
```

### 2.3 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功返回 Agent 列表 |

---

## 3. GET /api/agents/{agent_id} - 获取指定 Agent

### 3.1 请求

```http
GET /api/agents/reasoner HTTP/1.1
Host: 127.0.0.1:8000
```

### 3.2 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| agent_id | string | 是 | Agent 唯一标识 |

### 3.3 响应

```json
{
  "agent_id": "reasoner",
  "name": "Reasoner",
  "description": "推理 Agent，四维创意生成",
  "model": "deepseek-r2",
  "temperature": 0.0,
  "max_tokens": 8192,
  "capabilities": ["streaming", "thinking"],
  "stages": ["creativity"],
  "system_prompt": "...",
  "retry": {
    "max_attempts": 3,
    "base_delay": 2.0,
    "max_delay": 30.0
  },
  "fallback": {
    "strategy": "fallback_proposal",
    "confidence_score": 0.4
  }
}
```

### 3.4 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功返回 Agent 元数据 |
| 404 | Agent 不存在 |

---

## 4. POST /api/agents/orchestrate - 流式编排

### 4.1 请求

```http
POST /api/agents/orchestrate HTTP/1.1
Host: 127.0.0.1:8000
Content-Type: application/json
Accept: text/event-stream

{
  "session_id": "sess_xxx",
  "conversation_id": "conv_xxx",
  "user_input": "我是硕士生，导师在做医疗大模型，帮我生成3个论题",
  "degree": "master",
  "discipline": "计算机科学",
  "mentor_info": "导师项目：医疗大模型研发"
}
```

### 4.2 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| session_id | string | 是 | 会话 ID |
| conversation_id | string | 否 | 对话 ID（不传则创建新对话） |
| user_input | string | 是 | 用户输入 |
| degree | string | 否 | 学位（master/doctor） |
| discipline | string | 否 | 学科 |
| mentor_info | string | 否 | 导师信息 |

### 4.3 响应（SSE 流）

```text
event: orchestration_start
data: {"session_id": "sess_xxx", "conversation_id": "conv_xxx", "timestamp": "..."}

event: stage_start
data: {"stage": "info_confirm", "agent": "searcher", "timestamp": "..."}

event: agent_start
data: {"agent": "searcher", "stage": "info_confirm", "timestamp": "..."}

event: search_results
data: {"results": [...], "total": 42, "search_degraded": false}

event: agent_end
data: {"agent": "searcher", "total_tokens": 2000, "duration_ms": 3500}

event: stage_end
data: {"stage": "info_confirm", "status": "awaiting_confirmation"}

event: orchestration_pause
data: {"reason": "awaiting_user_confirmation", "next_action": "请确认是否继续"}
```

用户确认后继续：

```text
event: stage_start
data: {"stage": "creativity", "agent": "reasoner", "timestamp": "..."}

event: agent_start
data: {"agent": "reasoner", "stage": "creativity", "timestamp": "..."}

event: candidates
data: {"candidates": [...], "filtered_count": 2, "total_generated": 5}

event: agent_end
data: {"agent": "reasoner", "total_tokens": 2300, "duration_ms": 4500}

event: stage_end
data: {"stage": "creativity", "status": "completed"}

event: stage_start
data: {"stage": "validation", "agent": "critic", "timestamp": "..."}

...

event: orchestration_end
data: {"session_id": "sess_xxx", "total_tokens": 12345, "total_cost_cny": 3.5, "duration_ms": 35000}
```

### 4.4 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功启动编排（SSE 流） |
| 400 | 请求参数错误 |
| 404 | 会话不存在 |
| 500 | 编排失败 |

---

## 5. Agent 元数据 Schema

### 5.1 Schema 定义

```typescript
interface AgentMetadata {
  agent_id: string;           // Agent 唯一标识
  name: string;               // Agent 名称
  description: string;        // Agent 描述
  model: string;              // 绑定模型
  temperature: number;        // 温度参数
  max_tokens: number;         // 最大 token 数
  capabilities: string[];     // 能力列表
  stages: string[];           // 适用阶段
  system_prompt?: string;     // 系统提示词（仅单个 Agent 查询返回）
  retry?: {                   // 重试配置
    max_attempts: number;
    base_delay: number;
    max_delay: number;
  };
  fallback?: {                // 兜底配置
    strategy: string;
    confidence_score?: number;
  };
}
```

### 5.2 能力清单

| 能力 | 说明 |
|------|------|
| streaming | 支持流式输出 |
| thinking | 支持思维链 |
| web_search | 支持联网搜索 |

### 5.3 阶段清单

| 阶段 | 说明 |
|------|------|
| info_confirm | 信息确权 |
| creativity | 谱系解析与四维创意 |
| validation | 重复度评估与硬约束修复 |
| generation | 多粒度生成与降重脱敏 |
| deep_assist | 深度辅助闭环 |

---

## 6. 消息路由到指定 Agent

### 6.1 路由机制

Orchestrator 根据当前阶段自动路由消息到对应 Agent：

| 阶段 | 路由目标 Agent |
|------|----------------|
| info_confirm | Searcher |
| creativity | Reasoner |
| validation | Critic + Searcher |
| generation | Writer |
| deep_assist | Mentor |

### 6.2 显式指定 Agent

用户可通过 `POST /api/agents/orchestrate` 的 `agent_id` 参数显式指定 Agent：

```json
{
  "session_id": "sess_xxx",
  "conversation_id": "conv_xxx",
  "user_input": "请生成答辩模拟",
  "agent_id": "mentor",
  "stage": "deep_assist"
}
```

### 6.3 路由优先级

```text
路由优先级：
  1. 显式 agent_id 参数
  2. 当前阶段对应的 Agent
  3. Orchestrator 默认处理
```

---

## 7. SSE 事件格式

### 7.1 事件类型

| 事件类型 | 说明 |
|----------|------|
| orchestration_start | 编排开始 |
| orchestration_pause | 编排暂停（等待用户确认） |
| orchestration_end | 编排结束 |
| stage_start | 阶段开始 |
| stage_end | 阶段结束 |
| agent_start | Agent 调用开始 |
| agent_end | Agent 调用结束 |
| token | 流式 token |
| search_results | 检索结果 |
| candidates | 候选论题 |
| validation_results | 校验结果 |
| report | 开题报告 |
| review | 导师评审 |
| error | 错误 |

### 7.2 事件格式

```text
event: <event_type>
data: <json_data>

```

每个事件以 `event:` 开头，后跟事件类型；`data:` 后跟 JSON 数据；事件之间以空行分隔。

### 7.3 错误事件

```text
event: error
data: {
  "code": "AGENT_TIMEOUT",
  "message": "Agent 执行超时（>30s）",
  "retryable": true,
  "retry_count": 2,
  "fallback": "fallback_proposal"
}
```

---

## 8. 错误处理

### 8.1 错误响应

```json
{
  "success": false,
  "error": {
    "code": "AGENT_NOT_FOUND",
    "message": "Agent 'xxx' 不存在",
    "details": {
      "available_agents": ["orchestrator", "searcher", "reasoner", "critic", "mentor", "writer"]
    }
  }
}
```

### 8.2 错误码

| 错误码 | 说明 | HTTP 状态码 |
|--------|------|-------------|
| AGENT_NOT_FOUND | Agent 不存在 | 404 |
| SESSION_NOT_FOUND | 会话不存在 | 404 |
| AGENT_TIMEOUT | Agent 执行超时 | 500 |
| AGENT_RATE_LIMIT | Agent 被限流 | 429 |
| AGENT_JSON_PARSE | JSON 解析失败 | 500 |
| MODEL_UNAVAILABLE | 模型不可用 | 503 |
| HARD_CONSTRAINT_FAIL | 硬约束失败 | 422 |
| CONTEXT_OVERFLOW | 上下文超限 | 500 |

---

## 9. 示例

### 9.1 示例 1：获取所有 Agent

```bash
curl http://127.0.0.1:8000/api/agents
```

### 9.2 示例 2：获取指定 Agent

```bash
curl http://127.0.0.1:8000/api/agents/reasoner
```

### 9.3 示例 3：启动流式编排

```bash
curl -X POST http://127.0.0.1:8000/api/agents/orchestrate \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "session_id": "sess_xxx",
    "user_input": "我是硕士生，导师在做医疗大模型",
    "degree": "master",
    "discipline": "计算机科学"
  }'
```

### 9.4 示例 4：Python 客户端

```python
import httpx
import json

async def orchestrate():
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            "http://127.0.0.1:8000/api/agents/orchestrate",
            json={
                "session_id": "sess_xxx",
                "user_input": "我是硕士生，导师在做医疗大模型",
                "degree": "master"
            },
            timeout=60.0
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("event:"):
                    event_type = line[6:].strip()
                elif line.startswith("data:"):
                    data = json.loads(line[5:].strip())
                    print(f"[{event_type}] {data}")
```

---

## 10. 附录

### 10.1 术语表

| 术语 | 定义 |
|------|------|
| Agent | 智能体，承担单一职责的 AI 模块 |
| Orchestrator | 主管理 Agent，负责调度其他 Agent |
| SSE | Server-Sent Events，服务器推送事件 |
| 流式编排 | 通过 SSE 实时推送各 Agent 的中间结果 |
| 阶段路由 | 根据当前阶段自动路由消息到对应 Agent |

### 10.2 变更历史

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| v8.0 | 2026-06-19 | 初始版本，新增 Agent API |

---

> 文档版本 v8.0 · 最后更新 2026-06-19 · 维护者：ThesisMiner 团队
