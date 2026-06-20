# ThesisMiner v8.0 对话 API 文档

> **版本**：v8.0
> **日期**：2026-06-19
> **适用范围**：`backend/routes/conversations.py`、`backend/routes/messages.py`
> **关联模块**：对话 CRUD、消息管理、引用检索、上下文窗口

---

## 目录

1. [API 总览](#1-api-总览)
2. [对话 CRUD](#2-对话-crud)
3. [消息管理](#3-消息管理)
4. [引用检索](#4-引用检索)
5. [上下文窗口 API](#5-上下文窗口-api)
6. [示例](#6-示例)
7. [错误处理](#7-错误处理)
8. [附录](#8-附录)

---

## 1. API 总览

### 1.1 端点清单

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/conversations | 分页查询对话列表 |
| POST | /api/conversations | 创建新对话 |
| GET | /api/conversations/{conversation_id} | 获取对话详情 |
| DELETE | /api/conversations/{conversation_id} | 删除对话 |
| GET | /api/messages | 分页查询消息列表 |
| POST | /api/messages | 创建新消息 |
| GET | /api/messages/{message_id}/citations | 获取消息引用 |
| GET | /api/conversations/{conversation_id}/context | 获取对话上下文窗口 |
| PUT | /api/conversations/{conversation_id}/context | 更新对话上下文 |

### 1.2 数据模型关系

```text
session (会话)
  └── conversation (对话)
        └── message (消息)
              └── citation (引用)
```

---

## 2. 对话 CRUD

### 2.1 GET /api/conversations - 分页查询对话列表

#### 请求

```http
GET /api/conversations?session_id=sess_xxx&limit=20&offset=0 HTTP/1.1
Host: 127.0.0.1:8000
```

#### 查询参数

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| session_id | string | 是 | - | 会话 ID |
| limit | integer | 否 | 20 | 每页条数（最大 100） |
| offset | integer | 否 | 0 | 偏移量 |

#### 响应

```json
{
  "conversations": [
    {
      "id": "conv_xxx",
      "session_id": "sess_xxx",
      "title": "医疗大模型方向探索",
      "status": "active",
      "dialog_rounds": 8,
      "context": {
        "current_stage": "deep_assist",
        "active_agent": "mentor"
      },
      "cache_prefix_hash": "abc123...",
      "created_at": "2026-06-19T10:00:00",
      "updated_at": "2026-06-19T14:30:00"
    }
  ],
  "total": 1
}
```

### 2.2 POST /api/conversations - 创建新对话

#### 请求

```http
POST /api/conversations HTTP/1.1
Host: 127.0.0.1:8000
Content-Type: application/json

{
  "session_id": "sess_xxx",
  "title": "医疗大模型方向探索"
}
```

#### 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| session_id | string | 是 | 所属会话 ID |
| title | string | 是 | 对话标题 |

#### 响应

```json
{
  "id": "conv_xxx",
  "session_id": "sess_xxx",
  "title": "医疗大模型方向探索",
  "status": "active",
  "dialog_rounds": 0,
  "context": {},
  "cache_prefix_hash": null,
  "created_at": "2026-06-19T10:00:00",
  "updated_at": "2026-06-19T10:00:00"
}
```

### 2.3 GET /api/conversations/{conversation_id} - 获取对话详情

#### 请求

```http
GET /api/conversations/conv_xxx HTTP/1.1
Host: 127.0.0.1:8000
```

#### 响应

```json
{
  "id": "conv_xxx",
  "session_id": "sess_xxx",
  "title": "医疗大模型方向探索",
  "status": "active",
  "dialog_rounds": 8,
  "context": {
    "current_stage": "deep_assist",
    "active_agent": "mentor",
    "dst_state": {
      "selected_topic": "中文医疗问诊的小样本微调",
      "confirmed_methods": ["LoRA"],
      "iteration_count": 8
    }
  },
  "cache_prefix_hash": "abc123...",
  "created_at": "2026-06-19T10:00:00",
  "updated_at": "2026-06-19T14:30:00"
}
```

#### 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功返回对话详情 |
| 404 | 对话不存在 |

### 2.4 DELETE /api/conversations/{conversation_id} - 删除对话

#### 请求

```http
DELETE /api/conversations/conv_xxx HTTP/1.1
Host: 127.0.0.1:8000
```

#### 响应

```json
{
  "success": true,
  "message": "对话已删除，关联消息与引用已级联清理"
}
```

#### 说明

删除对话时会级联删除其下所有消息与引用（通过 SQLite 的 `ON DELETE CASCADE` 外键约束）。

---

## 3. 消息管理

### 3.1 GET /api/messages - 分页查询消息列表

#### 请求

```http
GET /api/messages?conversation_id=conv_xxx&limit=50&offset=0 HTTP/1.1
Host: 127.0.0.1:8000
```

#### 查询参数

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| conversation_id | string | 是 | - | 对话 ID |
| limit | integer | 否 | 50 | 每页条数 |
| offset | integer | 否 | 0 | 偏移量 |

#### 响应

```json
{
  "messages": [
    {
      "id": "msg_xxx",
      "conversation_id": "conv_xxx",
      "role": "user",
      "content": "我是硕士生，导师在做医疗大模型",
      "tokens": 20,
      "agent_id": null,
      "model": null,
      "metadata": null,
      "created_at": "2026-06-19T10:00:00"
    },
    {
      "id": "msg_yyy",
      "conversation_id": "conv_xxx",
      "role": "assistant",
      "content": "好的，我先检索近2年医疗大模型相关文献...",
      "tokens": 800,
      "agent_id": "searcher",
      "model": "deepseek-v3.2",
      "metadata": {
        "stage": "info_confirm",
        "cache_hit": true,
        "cached_tokens": 1200,
        "prompt_tokens": 1500,
        "completion_tokens": 800,
        "cost_cny": 0.012,
        "duration_ms": 3500
      },
      "created_at": "2026-06-19T10:00:05"
    }
  ],
  "total": 2
}
```

### 3.2 POST /api/messages - 创建新消息

#### 请求

```http
POST /api/messages HTTP/1.1
Host: 127.0.0.1:8000
Content-Type: application/json

{
  "conversation_id": "conv_xxx",
  "role": "user",
  "content": "继续生成论题"
}
```

#### 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| conversation_id | string | 是 | 对话 ID |
| role | string | 是 | 角色（user/assistant/system） |
| content | string | 是 | 消息内容 |
| agent_id | string | 否 | 生成该消息的 Agent ID（仅 assistant） |
| model | string | 否 | 生成该消息的模型（仅 assistant） |

#### 响应

```json
{
  "id": "msg_zzz",
  "conversation_id": "conv_xxx",
  "role": "user",
  "content": "继续生成论题",
  "tokens": 8,
  "agent_id": null,
  "model": null,
  "metadata": null,
  "created_at": "2026-06-19T10:01:00"
}
```

#### 说明

创建消息后，会自动更新对话的 `dialog_rounds` 字段（每创建一对 user+assistant 消息，dialog_rounds +1）。

---

## 4. 引用检索

### 4.1 GET /api/messages/{message_id}/citations - 获取消息引用

#### 请求

```http
GET /api/messages/msg_yyy/citations HTTP/1.1
Host: 127.0.0.1:8000
```

#### 响应

```json
{
  "citations": [
    {
      "id": "cit_xxx",
      "message_id": "msg_yyy",
      "title": "Medical LLM Safety Alignment",
      "authors": ["Zhang, Y.", "Li, X."],
      "year": 2025,
      "venue": "ACL 2025",
      "abstract": "本文提出了一种医疗大模型安全对齐方法...",
      "url": "https://aclanthology.org/2025.xxx",
      "source": "semantic_scholar"
    },
    {
      "id": "cit_yyy",
      "message_id": "msg_yyy",
      "title": "Chinese Medical QA Dataset",
      "authors": ["Wang, H."],
      "year": 2025,
      "venue": "arXiv preprint",
      "abstract": "本文构建了一个中文医疗问答数据集...",
      "url": "https://arxiv.org/abs/2025.xxx",
      "source": "arxiv"
    }
  ],
  "total": 2
}
```

#### 说明

- 仅 assistant 消息可能有引用（user 消息无引用）。
- 引用来源包括 arxiv、semantic_scholar、other。
- 引用是 AI 消息生成时由 Searcher 检索并关联的。

---

## 5. 上下文窗口 API

### 5.1 GET /api/conversations/{conversation_id}/context - 获取对话上下文窗口

#### 请求

```http
GET /api/conversations/conv_xxx/context HTTP/1.1
Host: 127.0.0.1:8000
```

#### 响应

```json
{
  "conversation_id": "conv_xxx",
  "current_stage": "deep_assist",
  "active_agent": "mentor",
  "dst_state": {
    "selected_topic": "中文医疗问诊的小样本微调",
    "confirmed_methods": ["LoRA"],
    "confirmed_discipline": "计算机科学",
    "open_questions": [],
    "iteration_count": 8,
    "confirmed_granularity": "standard",
    "confirmed_timeframe": 10
  },
  "compressed_history": "DST 压缩后的历史摘要...",
  "recent_messages": [
    {
      "role": "user",
      "content": "请生成答辩模拟"
    },
    {
      "role": "assistant",
      "content": "好的，我来生成答辩模拟..."
    }
  ],
  "context_window": {
    "total_tokens": 8500,
    "max_tokens": 128000,
    "utilization": 0.066,
    "compressed": true,
    "original_length": 16,
    "compressed_length": 5
  }
}
```

### 5.2 PUT /api/conversations/{conversation_id}/context - 更新对话上下文

#### 请求

```http
PUT /api/conversations/conv_xxx/context HTTP/1.1
Host: 127.0.0.1:8000
Content-Type: application/json

{
  "current_stage": "generation",
  "active_agent": "writer",
  "dst_state": {
    "selected_topic": "中文医疗问诊的小样本微调",
    "confirmed_methods": ["LoRA"],
    "confirmed_granularity": "standard"
  }
}
```

#### 响应

```json
{
  "success": true,
  "message": "对话上下文已更新"
}
```

---

## 6. 示例

### 6.1 示例 1：完整对话流程

```bash
# 1. 创建会话
curl -X POST http://127.0.0.1:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"title": "医疗大模型开题", "degree": "master", "discipline": "计算机科学"}'

# 2. 创建对话
curl -X POST http://127.0.0.1:8000/api/conversations \
  -H "Content-Type: application/json" \
  -d '{"session_id": "sess_xxx", "title": "方向探索"}'

# 3. 发送用户消息
curl -X POST http://127.0.0.1:8000/api/messages \
  -H "Content-Type: application/json" \
  -d '{"conversation_id": "conv_xxx", "role": "user", "content": "我是硕士生，导师在做医疗大模型"}'

# 4. 查询消息列表
curl http://127.0.0.1:8000/api/messages?conversation_id=conv_xxx

# 5. 查询消息引用
curl http://127.0.0.1:8000/api/messages/msg_yyy/citations

# 6. 查询上下文窗口
curl http://127.0.0.1:8000/api/conversations/conv_xxx/context

# 7. 删除对话
curl -X DELETE http://127.0.0.1:8000/api/conversations/conv_xxx
```

### 6.2 示例 2：Python 客户端

```python
import httpx

class ThesisMinerClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url
        self.client = httpx.Client()

    def create_session(self, title: str, degree: str, discipline: str = None):
        response = self.client.post(f"{self.base_url}/api/sessions", json={
            "title": title,
            "degree": degree,
            "discipline": discipline
        })
        return response.json()

    def create_conversation(self, session_id: str, title: str):
        response = self.client.post(f"{self.base_url}/api/conversations", json={
            "session_id": session_id,
            "title": title
        })
        return response.json()

    def send_message(self, conversation_id: str, role: str, content: str):
        response = self.client.post(f"{self.base_url}/api/messages", json={
            "conversation_id": conversation_id,
            "role": role,
            "content": content
        })
        return response.json()

    def get_messages(self, conversation_id: str, limit: int = 50, offset: int = 0):
        response = self.client.get(f"{self.base_url}/api/messages", params={
            "conversation_id": conversation_id,
            "limit": limit,
            "offset": offset
        })
        return response.json()

    def get_citations(self, message_id: str):
        response = self.client.get(f"{self.base_url}/api/messages/{message_id}/citations")
        return response.json()

    def get_context(self, conversation_id: str):
        response = self.client.get(f"{self.base_url}/api/conversations/{conversation_id}/context")
        return response.json()


# 使用示例
client = ThesisMinerClient()
session = client.create_session("医疗大模型开题", "master", "计算机科学")
conversation = client.create_conversation(session["id"], "方向探索")
client.send_message(conversation["id"], "user", "我是硕士生，导师在做医疗大模型")
messages = client.get_messages(conversation["id"])
print(messages)
```

### 6.3 示例 3：JavaScript 客户端

```javascript
class ThesisMinerClient {
  constructor(baseUrl = 'http://127.0.0.1:8000') {
    this.baseUrl = baseUrl;
  }

  async createConversation(sessionId, title) {
    const response = await fetch(`${this.baseUrl}/api/conversations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, title: title })
    });
    return response.json();
  }

  async sendMessage(conversationId, role, content) {
    const response = await fetch(`${this.baseUrl}/api/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        conversation_id: conversationId,
        role: role,
        content: content
      })
    });
    return response.json();
  }

  async getMessages(conversationId, limit = 50, offset = 0) {
    const response = await fetch(
      `${this.baseUrl}/api/messages?conversation_id=${conversationId}&limit=${limit}&offset=${offset}`
    );
    return response.json();
  }

  async getCitations(messageId) {
    const response = await fetch(`${this.baseUrl}/api/messages/${messageId}/citations`);
    return response.json();
  }
}

// 使用示例
const client = new ThesisMinerClient();
const conversation = await client.createConversation('sess_xxx', '方向探索');
await client.sendMessage(conversation.id, 'user', '我是硕士生');
const messages = await client.getMessages(conversation.id);
console.log(messages);
```

---

## 7. 错误处理

### 7.1 错误响应格式

```json
{
  "success": false,
  "error": {
    "code": "CONVERSATION_NOT_FOUND",
    "message": "对话 'xxx' 不存在"
  }
}
```

### 7.2 错误码

| 错误码 | 说明 | HTTP 状态码 |
|--------|------|-------------|
| CONVERSATION_NOT_FOUND | 对话不存在 | 404 |
| MESSAGE_NOT_FOUND | 消息不存在 | 404 |
| SESSION_NOT_FOUND | 会话不存在 | 404 |
| INVALID_ROLE | 无效的角色 | 400 |
| CONTEXT_OVERFLOW | 上下文超限 | 500 |

### 7.3 错误处理示例

```python
try:
    response = client.get_messages("invalid_conv_id")
    if not response.get("success", True):
        error = response.get("error", {})
        print(f"错误：{error.get('code')} - {error.get('message')}")
except httpx.HTTPError as e:
    print(f"HTTP 错误：{e}")
```

---

## 8. 附录

### 8.1 数据模型 Schema

#### Conversation

```typescript
interface Conversation {
  id: string;
  session_id: string;
  title: string;
  status: 'active' | 'closed';
  dialog_rounds: number;
  context: {
    current_stage?: string;
    active_agent?: string;
    dst_state?: object;
    compressed_history?: string;
  };
  cache_prefix_hash: string | null;
  created_at: string;
  updated_at: string;
}
```

#### Message

```typescript
interface Message {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  tokens: number;
  agent_id: string | null;
  model: string | null;
  metadata: {
    stage?: string;
    cache_hit?: boolean;
    cached_tokens?: number;
    prompt_tokens?: number;
    completion_tokens?: number;
    cost_cny?: number;
    duration_ms?: number;
  } | null;
  created_at: string;
}
```

#### Citation

```typescript
interface Citation {
  id: string;
  message_id: string;
  title: string;
  authors: string[];
  year: number;
  venue: string;
  abstract: string;
  url: string;
  source: 'arxiv' | 'semantic_scholar' | 'other';
}
```

### 8.2 术语表

| 术语 | 定义 |
|------|------|
| conversation | 对话，会话下的独立线程 |
| message | 消息，对话中的单条记录 |
| citation | 引用，AI 消息关联的文献 |
| DST | Dialogue State Tracker，对话状态追踪器 |
| context window | 上下文窗口，对话的上下文容量 |
| dialog_rounds | 对话轮数 |
| cache_prefix_hash | Prompt 前缀的 SHA-256 哈希 |

### 8.3 变更历史

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| v8.0 | 2026-06-19 | 初始版本，新增对话 API |

---

> 文档版本 v8.0 · 最后更新 2026-06-19 · 维护者：ThesisMiner 团队
