# ThesisMiner v8.0 会话与对话数据模型

> **版本**：v8.0
> **日期**：2026-06-19
> **适用范围**：`backend/sessions/`、`backend/routes/sessions.py`、`backend/routes/conversations.py`
> **关联模块**：sessions → conversations → messages → citations

---

## 目录

1. [数据模型总览](#1-数据模型总览)
2. [实体关系图](#2-实体关系图)
3. [sessions 表（会话）](#3-sessions-表会话)
4. [conversations 表（对话）](#4-conversations-表对话)
5. [messages 表（消息）](#5-messages-表消息)
6. [citations 表（引用）](#6-citations-表引用)
7. [上下文窗口管理](#7-上下文窗口管理)
8. [DST 压缩策略](#8-dst-压缩策略)
9. [多对话隔离机制](#9-多对话隔离机制)
10. [历史与分页](#10-历史与分页)
11. [从 v7 单线程模型迁移](#11-从-v7-单线程模型迁移)
12. [缓存字段与命中率](#12-缓存字段与命中率)
13. [数据生命周期](#13-数据生命周期)
14. [索引与查询优化](#14-索引与查询优化)
15. [附录](#15-附录)

---

## 1. 数据模型总览

### 1.1 设计目标

ThesisMiner v8.0 在 v7.0 单一会话表基础上，引入**多对话（conversation）隔离**机制，允许单个会话下挂载多个独立对话线程，每个对话线程拥有独立的消息历史与上下文。设计目标如下：

1. **多对话支持**：单个会话可包含多个对话线程，便于用户在同一会话下探索多个论题方向。
2. **上下文隔离**：每个对话线程拥有独立的上下文窗口，互不污染。
3. **DST 压缩**：对话历史超过阈值时自动压缩，控制 token 用量线性增长。
4. **引用追溯**：每条 AI 消息可关联多条文献引用，支持溯源。
5. **缓存优化**：会话级缓存前缀哈希，提升 DeepSeek KV Cache 命中率。
6. **向后兼容**：v7 单线程会话可平滑迁移到 v8 多对话模型。

### 1.2 核心实体

| 实体 | 中文名 | 说明 | 关联 |
|------|--------|------|------|
| session | 会话 | 顶层容器，包含学位、学科、导师信息 | 1:N conversations |
| conversation | 对话 | 会话下的独立对话线程 | N:1 session, 1:N messages |
| message | 消息 | 对话中的单条消息（用户/AI/系统） | N:1 conversation, 1:N citations |
| citation | 引用 | AI 消息关联的文献引用 | N:1 message |

### 1.3 与 v7 的差异

| 维度 | v7 | v8 |
|------|-----|-----|
| 会话模型 | 单线程（session → context.history） | 多线程（session → conversations → messages） |
| 上下文存储 | sessions.context JSON 字段 | conversations.context + messages 表 |
| 对话轮数 | sessions.context.history 长度 | conversations.dialog_rounds 字段 |
| 引用追溯 | 无 | citations 表，AI 消息可关联文献 |
| 缓存字段 | cache_prefix_hash / cache_id / cache_hit_rate | 同 v7，但按对话维度统计 |
| 多对话隔离 | 不支持 | 支持，每个对话独立上下文 |

---

## 2. 实体关系图

### 2.1 ER 图

```text
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│    sessions     │       │ conversations   │       │    messages     │       │   citations     │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id (PK)         │◄──┐   │ id (PK)         │◄──┐   │ id (PK)         │◄──┐   │ id (PK)         │
│ title           │   │   │ session_id (FK) │   │   │ conversation_id │   │   │ message_id (FK) │
│ degree          │   └───│ title           │   └───│ role            │   └───│ title           │
│ discipline      │       │ status          │       │ content         │       │ authors         │
│ mentor_info     │       │ dialog_rounds   │       │ tokens          │       │ year            │
│ status          │       │ context (JSON)  │       │ agent_id        │       │ venue           │
│ context (JSON)  │       │ cache_prefix    │       │ model           │       │ abstract        │
│ cache_prefix    │       │ created_at      │       │ created_at      │       │ url             │
│ cache_id        │       │ updated_at      │       │ metadata (JSON) │       │ source          │
│ cache_hit_rate  │       └─────────────────┘       └─────────────────┘       └─────────────────┘
│ created_at      │
│ updated_at      │
└─────────────────┘
```

### 2.2 关系说明

- **sessions → conversations**：一对多。一个会话可包含多个对话线程，删除会话时级联删除其下所有对话。
- **conversations → messages**：一对多。一个对话包含多条消息，删除对话时级联删除其下所有消息。
- **messages → citations**：一对多。一条 AI 消息可关联多条文献引用，删除消息时级联删除其引用。

### 2.3 级联删除规则

```text
DELETE session → CASCADE DELETE conversations → CASCADE DELETE messages → CASCADE DELETE citations
```

通过 SQLite 的 `ON DELETE CASCADE` 外键约束实现，需在 `PRAGMA foreign_keys = ON` 时生效。

---

## 3. sessions 表（会话）

### 3.1 表结构

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | TEXT | PRIMARY KEY | 会话唯一标识（UUID） |
| title | TEXT | NOT NULL | 会话标题 |
| degree | TEXT | NOT NULL | 学位（master/doctor） |
| discipline | TEXT | | 学科 |
| mentor_info | TEXT | | 导师信息（多行文本） |
| status | TEXT | NOT NULL DEFAULT 'active' | 状态（active/closed/completed） |
| context | TEXT | | 上下文 JSON（v7 兼容字段） |
| cache_prefix_hash | TEXT | | Prompt 前缀 SHA-256 哈希 |
| cache_id | TEXT | | DeepSeek 缓存 ID |
| cache_hit_rate | REAL | DEFAULT 0.0 | 缓存命中率 |
| created_at | TEXT | NOT NULL | 创建时间（ISO 8601） |
| updated_at | TEXT | NOT NULL | 更新时间（ISO 8601） |

### 3.2 建表 SQL

```sql
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    degree TEXT NOT NULL,
    discipline TEXT,
    mentor_info TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    context TEXT,
    cache_prefix_hash TEXT,
    cache_id TEXT,
    cache_hit_rate REAL DEFAULT 0.0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions(created_at DESC);
```

### 3.3 context 字段结构（v7 兼容）

```json
{
  "history": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." }
  ],
  "candidates": [...],
  "dst_state": {
    "selected_topic": "...",
    "confirmed_methods": [...],
    "confirmed_discipline": "...",
    "open_questions": [...],
    "iteration_count": 0
  }
}
```

> v8 中，新会话的 `context.history` 为空，对话历史存储在 `messages` 表。v7 旧会话的 `context.history` 保留，迁移时自动转换为 `messages` 记录。

---

## 4. conversations 表（对话）

### 4.1 表结构

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | TEXT | PRIMARY KEY | 对话唯一标识（UUID） |
| session_id | TEXT | NOT NULL, FK | 所属会话 ID |
| title | TEXT | NOT NULL | 对话标题（如「医疗大模型方向探索」） |
| status | TEXT | NOT NULL DEFAULT 'active' | 状态（active/closed） |
| dialog_rounds | INTEGER | DEFAULT 0 | 对话轮数 |
| context | TEXT | | 对话级上下文 JSON（DST 状态） |
| cache_prefix_hash | TEXT | | 对话级 Prompt 前缀哈希 |
| created_at | TEXT | NOT NULL | 创建时间 |
| updated_at | TEXT | NOT NULL | 更新时间 |

### 4.2 建表 SQL

```sql
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    dialog_rounds INTEGER DEFAULT 0,
    context TEXT,
    cache_prefix_hash TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_conversations_session_id ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_conversations_status ON conversations(status);
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at DESC);
```

### 4.3 context 字段结构

```json
{
  "dst_state": {
    "selected_topic": "...",
    "confirmed_methods": [...],
    "confirmed_discipline": "...",
    "open_questions": [...],
    "iteration_count": 0
  },
  "current_stage": "creativity",
  "active_agent": "reasoner",
  "compressed_history": "DST 压缩后的历史摘要"
}
```

---

## 5. messages 表（消息）

### 5.1 表结构

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | TEXT | PRIMARY KEY | 消息唯一标识（UUID） |
| conversation_id | TEXT | NOT NULL, FK | 所属对话 ID |
| role | TEXT | NOT NULL | 角色（user/assistant/system） |
| content | TEXT | NOT NULL | 消息内容 |
| tokens | INTEGER | DEFAULT 0 | 消息 token 数 |
| agent_id | TEXT | | 生成该消息的 Agent ID（仅 assistant） |
| model | TEXT | | 生成该消息的模型（仅 assistant） |
| metadata | TEXT | | 元数据 JSON（如 stage、cache_hit） |
| created_at | TEXT | NOT NULL | 创建时间 |

### 5.2 建表 SQL

```sql
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    tokens INTEGER DEFAULT 0,
    agent_id TEXT,
    model TEXT,
    metadata TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role);
```

### 5.3 metadata 字段结构

```json
{
  "stage": "creativity",
  "cache_hit": true,
  "cached_tokens": 1200,
  "prompt_tokens": 1500,
  "completion_tokens": 800,
  "cost_cny": 0.012,
  "duration_ms": 3500,
  "agent_metadata": {
    "strategy": "advisor_extension",
    "score": 8.5
  }
}
```

---

## 6. citations 表（引用）

### 6.1 表结构

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | TEXT | PRIMARY KEY | 引用唯一标识 |
| message_id | TEXT | NOT NULL, FK | 关联的消息 ID |
| title | TEXT | NOT NULL | 文献标题 |
| authors | TEXT | | 作者列表（JSON 数组） |
| year | INTEGER | | 发表年份 |
| venue | TEXT | | 发表场所（会议/期刊） |
| abstract | TEXT | | 摘要 |
| url | TEXT | | 文献 URL |
| source | TEXT | | 来源（arxiv/semantic_scholar/other） |

### 6.2 建表 SQL

```sql
CREATE TABLE IF NOT EXISTS citations (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL,
    title TEXT NOT NULL,
    authors TEXT,
    year INTEGER,
    venue TEXT,
    abstract TEXT,
    url TEXT,
    source TEXT,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_citations_message_id ON citations(message_id);
CREATE INDEX IF NOT EXISTS idx_citations_year ON citations(year);
CREATE INDEX IF NOT EXISTS idx_citations_source ON citations(source);
```

---

## 7. 上下文窗口管理

### 7.1 上下文层级

```text
会话级上下文（session.context）
  ├── 学位、学科、导师信息（静态）
  └── 候选论题列表（跨对话共享）

对话级上下文（conversation.context）
  ├── DST 状态（动态）
  ├── 当前阶段（current_stage）
  ├── 活动 Agent（active_agent）
  └── 压缩历史（compressed_history）

消息级上下文（message.metadata）
  ├── 阶段标记（stage）
  ├── 缓存命中（cache_hit）
  └── Agent 元数据（agent_metadata）
```

### 7.2 上下文组装

每次 Agent 调用时，Orchestrator 按以下顺序组装上下文：

```text
最终上下文 = 系统提示词（Agent 专属）
           + 会话级上下文（学位、学科、导师信息）
           + 对话级上下文（DST 状态、当前阶段）
           + 最近 N 轮消息原文（N=2，来自 messages 表）
           + 用户当前输入
```

### 7.3 上下文窗口阈值

| 模型 | max_context | 上下文阈值（80%） | 触发压缩 |
|------|-------------|-------------------|----------|
| claude-sonnet-4.5 | 200K | 160K | 是 |
| claude-opus-4.5 | 200K | 160K | 是 |
| deepseek-r2 | 128K | 102K | 是 |
| deepseek-v3.2 | 128K | 102K | 是 |
| gpt-4.1 | 1M | 800K | 否（足够大） |
| qwen3-max | 131K | 105K | 是 |

### 7.4 上下文裁剪规则

当组装后的上下文超过阈值时，按以下顺序裁剪：

1. 移除最早的消息原文（保留最近 2 轮）。
2. 触发 DST 压缩，将早期历史压缩为摘要。
3. 若仍超限，移除候选论题列表中的低分候选。
4. 若仍超限，截断单条消息内容（保留前 2000 字 + 末尾 500 字）。

---

## 8. DST 压缩策略

### 8.1 DST 状态槽

Dialogue State Tracker（DST）维护以下状态槽：

| 状态槽 | 类型 | 说明 |
|--------|------|------|
| selected_topic | string | 用户已选定的论题 |
| confirmed_methods | list[string] | 用户已确认的研究方法 |
| confirmed_discipline | string | 用户已确认的学科 |
| open_questions | list[string] | 待解决的问题列表 |
| iteration_count | integer | 迭代轮数 |
| confirmed_granularity | string | 用户已确认的报告颗粒度 |
| confirmed_timeframe | integer | 用户已确认的研究周期（月） |

### 8.2 压缩触发条件

```text
当对话历史轮数 > 5 时，触发 DST 压缩：
  1. 调用 dialogue_state_tracker.extract_state(history) 提取状态槽
  2. 调用 dst_compactor.compact_history(history, dst_state) 压缩历史
  3. 压缩后的上下文 = DST 摘要 + 最近 2 轮原文
  4. 写回 conversation.context
```

### 8.3 压缩算法

```python
def compact_history(history: list, dst_state: dict) -> dict:
    """
    压缩对话历史。

    Args:
        history: 完整对话历史
        dst_state: DST 状态槽

    Returns:
        压缩后的上下文，包含 DST 摘要与最近 2 轮原文
    """
    if len(history) <= 5:
        return {"history": history, "compressed": False}

    # 提取 DST 摘要
    summary = generate_dst_summary(dst_state)

    # 保留最近 2 轮原文
    recent = history[-4:]  # 2 轮 = 4 条消息（user + assistant）

    return {
        "compressed_history": summary,
        "recent_history": recent,
        "compressed": True,
        "original_length": len(history),
        "compressed_length": len(recent) + 1  # +1 for summary
    }
```

### 8.4 压缩示例

```text
原始历史（8 轮，16 条消息）：
  轮1: 用户问医疗大模型方向 → AI 给出 3 个候选
  轮2: 用户选定「中文问诊微调」→ AI 确认并询问方法
  轮3: 用户确认用 LoRA → AI 生成研究内容
  轮4: 用户询问可行性 → AI 给出可行性分析
  轮5: 用户确认周期 10 个月 → AI 确认
  轮6: 用户要求生成报告 → AI 生成标准报告
  轮7: 用户要求精简版 → AI 生成精简报告
  轮8: 用户要求答辩模拟 → AI 生成答辩问题

压缩后：
  DST 摘要：
    selected_topic: "中文问诊微调"
    confirmed_methods: ["LoRA"]
    confirmed_discipline: "计算机科学"
    confirmed_timeframe: 10
    iteration_count: 8
  
  最近 2 轮原文：
    轮7: 用户要求精简版 → AI 生成精简报告
    轮8: 用户要求答辩模拟 → AI 生成答辩问题
```

---

## 9. 多对话隔离机制

### 9.1 隔离原则

同一会话下的多个对话线程完全隔离：

1. **上下文隔离**：每个对话有独立的 `context` 字段，DST 状态不共享。
2. **历史隔离**：每个对话的消息历史独立存储在 `messages` 表，按 `conversation_id` 过滤。
3. **缓存隔离**：每个对话有独立的 `cache_prefix_hash`，避免缓存串扰。
4. **阶段隔离**：每个对话的当前阶段（current_stage）独立，可同时处于不同阶段。

### 9.2 隔离实现

```python
def get_conversation_context(conversation_id: str) -> dict:
    """获取对话上下文，确保隔离。"""
    conversation = fetch_one(
        "SELECT * FROM conversations WHERE id = ?",
        (conversation_id,)
    )
    messages = fetch_all(
        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at",
        (conversation_id,)
    )
    return {
        "conversation": conversation,
        "messages": messages,
        "dst_state": json.loads(conversation["context"]).get("dst_state", {})
    }
```

### 9.3 跨对话共享

仅以下信息在会话级共享（跨对话可见）：

- 学位、学科、导师信息（sessions 表）
- 候选论题列表（sessions.context.candidates）
- 谱系图（lineage_nodes / lineage_edges 表）

---

## 10. 历史与分页

### 10.1 会话分页

```sql
-- 按创建时间降序分页查询会话
SELECT * FROM sessions
ORDER BY created_at DESC
LIMIT ? OFFSET ?;

-- 返回总数
SELECT COUNT(*) FROM sessions;
```

### 10.2 对话分页

```sql
-- 按会话 ID 过滤，按创建时间降序分页查询对话
SELECT * FROM conversations
WHERE session_id = ?
ORDER BY created_at DESC
LIMIT ? OFFSET ?;
```

### 10.3 消息分页

```sql
-- 按对话 ID 过滤，按创建时间升序分页查询消息
SELECT * FROM messages
WHERE conversation_id = ?
ORDER BY created_at ASC
LIMIT ? OFFSET ?;
```

### 10.4 引用查询

```sql
-- 按消息 ID 查询关联引用
SELECT * FROM citations
WHERE message_id = ?;
```

### 10.5 分页参数规范

| 参数 | 默认值 | 最大值 | 说明 |
|------|--------|--------|------|
| limit | 20 | 100 | 每页条数 |
| offset | 0 | - | 偏移量 |

---

## 11. 从 v7 单线程模型迁移

### 11.1 迁移策略

v7 的 `sessions.context.history` 需迁移到 v8 的 `messages` 表：

```text
迁移步骤：
  1. 检测 sessions.context.history 是否非空
  2. 为每个 v7 会话创建一个默认对话（title="默认对话"）
  3. 遍历 history，为每条消息创建 messages 记录：
     - role: history[i].role
     - content: history[i].content
     - conversation_id: 默认对话 ID
     - created_at: 会话创建时间（近似）
  4. 将 sessions.context.dst_state 迁移到 conversations.context
  5. 清空 sessions.context.history（保留 candidates）
```

### 11.2 迁移脚本

```python
def migrate_v7_to_v8():
    """v7 单线程会话迁移到 v8 多对话模型。"""
    sessions = fetch_all("SELECT * FROM sessions WHERE context IS NOT NULL")
    for session in sessions:
        context = json.loads(session["context"])
        history = context.get("history", [])
        if not history:
            continue

        # 创建默认对话
        conversation_id = str(uuid.uuid4())
        execute_insert(
            "INSERT INTO conversations (id, session_id, title, status, dialog_rounds, context, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (conversation_id, session["id"], "默认对话", "active",
             len(history) // 2, json.dumps({"dst_state": context.get("dst_state", {})}),
             session["created_at"], session["updated_at"])
        )

        # 迁移消息
        for msg in history:
            message_id = str(uuid.uuid4())
            execute_insert(
                "INSERT INTO messages (id, conversation_id, role, content, tokens, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (message_id, conversation_id, msg["role"], msg["content"], 0, session["created_at"])
            )

        # 清空 history
        context["history"] = []
        execute_query(
            "UPDATE sessions SET context = ? WHERE id = ?",
            (json.dumps(context), session["id"])
        )
```

### 11.3 向后兼容

v8 保留 `sessions.context` 字段用于向后兼容：

- v7 客户端读取 `sessions.context.history` 时返回空数组（已迁移）。
- v8 客户端通过 `/api/conversations/{session_id}` 获取对话列表。
- v8 客户端通过 `/api/messages/{conversation_id}` 获取消息历史。

---

## 12. 缓存字段与命中率

### 12.1 缓存字段

| 表 | 字段 | 说明 |
|----|------|------|
| sessions | cache_prefix_hash | 会话级 Prompt 前缀哈希 |
| sessions | cache_id | DeepSeek 缓存 ID |
| sessions | cache_hit_rate | 会话级缓存命中率 |
| conversations | cache_prefix_hash | 对话级 Prompt 前缀哈希 |
| messages | metadata.cache_hit | 消息级缓存命中标记 |
| messages | metadata.cached_tokens | 缓存命中的 token 数 |

### 12.2 命中率计算

```text
会话级命中率 = Σ(消息 cached_tokens) / Σ(消息 prompt_tokens)
对话级命中率 = Σ(对话内消息 cached_tokens) / Σ(对话内消息 prompt_tokens)
```

### 12.3 命中率监控

通过 `/api/cache-stats` 端点查询：

```json
{
  "total_requests": 1234,
  "cache_hits": 1187,
  "cache_hit_rate": 0.962,
  "by_session": {
    "sess_xxx": { "hits": 245, "misses": 12, "hit_rate": 0.953 }
  },
  "by_conversation": {
    "conv_xxx": { "hits": 87, "misses": 3, "hit_rate": 0.966 }
  },
  "by_agent": {
    "orchestrator": { "hits": 245, "misses": 12, "hit_rate": 0.953 },
    "reasoner": { "hits": 312, "misses": 8, "hit_rate": 0.975 }
  }
}
```

---

## 13. 数据生命周期

### 13.1 数据保留策略

| 数据类型 | 保留期 | 清理方式 |
|----------|--------|----------|
| 活跃会话 | 永久 | 用户手动删除 |
| 关闭会话 | 90 天 | 定时任务清理 |
| 已完成会话 | 180 天 | 定时任务清理 |
| 预算账本 | 永久 | 不清理（审计需要） |
| 谱系图 | 永久 | 用户手动删除 |

### 13.2 软删除 vs 硬删除

- **软删除**：将会话状态设为 `closed`，保留数据 90 天后硬删除。
- **硬删除**：直接从数据库删除，级联删除关联数据。

默认采用硬删除（用户主动删除时立即生效），软删除仅用于定时清理任务。

### 13.3 备份策略

```text
SQLite WAL 模式支持热备：
  1. 定时任务每小时执行一次 .backup 命令
  2. 备份文件存储在 data/backups/ 目录
  3. 保留最近 24 小时的备份
  4. 每日备份保留 7 天
  5. 每周备份保留 4 周
```

---

## 14. 索引与查询优化

### 14.1 索引清单

| 表 | 索引名 | 字段 | 用途 |
|----|--------|------|------|
| sessions | idx_sessions_status | status | 按状态过滤 |
| sessions | idx_sessions_created_at | created_at DESC | 按时间排序 |
| conversations | idx_conversations_session_id | session_id | 按会话查询对话 |
| conversations | idx_conversations_status | status | 按状态过滤 |
| conversations | idx_conversations_created_at | created_at DESC | 按时间排序 |
| messages | idx_messages_conversation_id | conversation_id | 按对话查询消息 |
| messages | idx_messages_created_at | created_at | 按时间排序 |
| messages | idx_messages_role | role | 按角色过滤 |
| citations | idx_citations_message_id | message_id | 按消息查询引用 |
| citations | idx_citations_year | year | 按年份过滤 |
| citations | idx_citations_source | source | 按来源过滤 |

### 14.2 查询优化建议

1. **分页查询**：使用 `LIMIT ? OFFSET ?` 避免全表扫描。
2. **关联查询**：使用 JOIN 替代多次查询，减少数据库往返。
3. **批量插入**：使用事务批量插入消息，提升写入性能。
4. **索引覆盖**：确保常用查询字段有索引覆盖。
5. **WAL 模式**：启用 WAL 模式提升并发读性能。

### 14.3 性能基准

| 操作 | 数据量 | 耗时（目标） |
|------|--------|-------------|
| 创建会话 | 1 | < 10ms |
| 查询会话列表 | 1000 | < 50ms |
| 查询对话列表 | 100 | < 30ms |
| 查询消息历史 | 100 | < 50ms |
| 插入消息 | 1 | < 10ms |
| 查询引用 | 10 | < 20ms |

---

## 15. 附录

### 15.1 数据模型 Pydantic Schema

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class Session(BaseModel):
    id: str
    title: str
    degree: str
    discipline: Optional[str] = None
    mentor_info: Optional[str] = None
    status: str = "active"
    context: Optional[dict] = None
    cache_prefix_hash: Optional[str] = None
    cache_id: Optional[str] = None
    cache_hit_rate: float = 0.0
    created_at: datetime
    updated_at: datetime

class Conversation(BaseModel):
    id: str
    session_id: str
    title: str
    status: str = "active"
    dialog_rounds: int = 0
    context: Optional[dict] = None
    cache_prefix_hash: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class Message(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    tokens: int = 0
    agent_id: Optional[str] = None
    model: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: datetime

class Citation(BaseModel):
    id: str
    message_id: str
    title: str
    authors: Optional[list[str]] = None
    year: Optional[int] = None
    venue: Optional[str] = None
    abstract: Optional[str] = None
    url: Optional[str] = None
    source: Optional[str] = None
```

### 15.2 API 端点与数据模型映射

| API 端点 | 方法 | 数据模型 | 说明 |
|----------|------|----------|------|
| /api/sessions | GET | Session[] | 会话列表 |
| /api/sessions | POST | Session | 创建会话 |
| /api/sessions/{id} | GET | Session | 会话详情 |
| /api/sessions/{id} | DELETE | - | 删除会话 |
| /api/sessions/{id}/status | PATCH | Session | 更新状态 |
| /api/conversations | GET | Conversation[] | 对话列表 |
| /api/conversations | POST | Conversation | 创建对话 |
| /api/conversations/{id} | GET | Conversation | 对话详情 |
| /api/conversations/{id} | DELETE | - | 删除对话 |
| /api/messages | GET | Message[] | 消息列表 |
| /api/messages | POST | Message | 创建消息 |
| /api/messages/{id}/citations | GET | Citation[] | 消息引用 |
| /api/cache-stats | GET | dict | 缓存统计 |

### 15.3 术语表

| 术语 | 定义 |
|------|------|
| session | 会话，顶层容器 |
| conversation | 对话，会话下的独立线程 |
| message | 消息，对话中的单条记录 |
| citation | 引用，AI 消息关联的文献 |
| DST | Dialogue State Tracker，对话状态追踪器 |
| context | 上下文，JSON 格式的状态数据 |
| cache_prefix_hash | Prompt 前缀的 SHA-256 哈希 |
| cache_hit_rate | 缓存命中率 |
| dialog_rounds | 对话轮数 |
| 级联删除 | 删除父记录时自动删除子记录 |

### 15.4 变更历史

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| v8.0 | 2026-06-19 | 初始版本，引入多对话模型 |
| v8.1 | （规划中） | 新增对话级缓存预热 |
| v8.2 | （规划中） | 新增对话分支与合并 |

---

> 文档版本 v8.0 · 最后更新 2026-06-19 · 维护者：ThesisMiner 团队
