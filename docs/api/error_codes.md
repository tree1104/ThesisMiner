# ThesisMiner v8.0 错误码完整参考文档

> **文档版本**：v8.0.0  
> **最后更新**：2026-06-19  
> **文档定位**：ThesisMiner 全部错误码的权威参考，涵盖 HTTP 状态码、业务错误码、Agent 错误码、约束错误码、缓存错误码  
> **适用对象**：开发者、运维人员、API 集成方  

---

## 目录

- [1. 错误码体系总览](#1-错误码体系总览)
- [2. HTTP 4xx 客户端错误码](#2-http-4xx-客户端错误码)
- [3. HTTP 5xx 服务端错误码](#3-http-5xx-服务端错误码)
- [4. 业务错误码](#4-业务错误码)
- [5. Agent 错误码](#5-agent-错误码)
- [6. 约束错误码](#6-约束错误码)
- [7. 缓存错误码](#7-缓存错误码)
- [8. 错误响应格式规范](#8-错误响应格式规范)
- [9. 故障排查指南](#9-故障排查指南)
- [10. 错误码速查表](#10-错误码速查表)

---

## 1. 错误码体系总览

ThesisMiner v8.0 的错误码体系分为五大类别，共计 100+ 错误码，覆盖系统运行中可能出现的所有异常情况。

```
┌─────────────────────────────────────────────────────────────────┐
│                  ThesisMiner 错误码体系架构                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              HTTP 状态码 (4xx / 5xx)                     │   │
│  │  400 / 401 / 403 / 404 / 409 / 422 / 429                │   │
│  │  500 / 502 / 503 / 504                                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              业务错误码 (BIZ_*)                           │   │
│  │  SESSION_* / CONVERSATION_* / PROPOSAL_*                 │   │
│  │  LINEAGE_* / BUDGET_* / CONFIG_*                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Agent 错误码 (AGENT_*)                      │   │
│  │  AGENT_TIMEOUT / AGENT_FAILURE / AGENT_CONTEXT_OVERFLOW  │   │
│  │  AGENT_MODEL_UNAVAILABLE / AGENT_PARSE_ERROR             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              约束错误码 (CONSTRAINT_*)                    │   │
│  │  CONSTRAINT_VIOLATION / NOVELTY_LOW / STYLE_FAIL         │   │
│  │  DUPLICATION_HIGH / FORMAT_ERROR / TIME_INFEASIBLE       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              缓存错误码 (CACHE_*)                         │   │
│  │  CACHE_MISS / CACHE_INVALID / CACHE_EXPIRED              │   │
│  │  CACHE_PREFIX_MISMATCH / CACHE_COMPRESSION_ERROR         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**错误码命名规范**：

```
错误码格式：{CATEGORY}_{SUBCATEGORY}_{SPECIFIC}_{SEQUENCE}

示例：
- BIZ_SESSION_CREATE_001：业务错误-会话-创建-001
- AGENT_TIMEOUT_001：Agent错误-超时-001
- CONSTRAINT_VIOLATION_TITLE_001：约束错误-违规-标题-001
- CACHE_MISS_001：缓存错误-未命中-001
```

---

## 2. HTTP 4xx 客户端错误码

### 2.1 400 Bad Request

**错误码**：`HTTP_400_BAD_REQUEST`

| 属性 | 值 |
|------|---|
| HTTP 状态码 | 400 |
| 错误类型 | 客户端请求错误 |
| 严重程度 | 低 |
| 可重试 | 否（需修正请求） |

**含义**：服务器无法理解客户端的请求，通常由于请求参数格式错误、缺少必填字段或参数类型不匹配。

**常见原因**：

1. 请求体 JSON 格式错误（缺少括号、引号不匹配等）
2. 必填参数缺失（如创建会话时未提供 `degree` 字段）
3. 参数类型不匹配（如 `degree` 字段传入了数字而非字符串）
4. 参数值超出允许范围（如 `degree` 字段传入了 "bachelor" 而非 "master" 或 "doctor"）
5. 请求体过大（超过 1MB 限制）

**解决方案**：

1. 检查请求体 JSON 格式是否正确
2. 对照 API 文档检查必填参数是否齐全
3. 验证参数类型和取值范围
4. 缩减请求体大小

**示例**：

```json
// 请求
POST /api/sessions
Content-Type: application/json

{
  "degree": "master",
  "discipline": "计算机科学"
  // 缺少逗号，JSON 格式错误
}

// 响应
{
  "error": {
    "code": "HTTP_400_BAD_REQUEST",
    "message": "请求体 JSON 格式错误：第 3 行缺少逗号",
    "details": {
      "line": 3,
      "column": 3,
      "expected": ",",
      "found": "\"discipline\""
    },
    "timestamp": "2026-06-19T10:30:00Z",
    "request_id": "req-abc123"
  }
}
```

### 2.2 401 Unauthorized

**错误码**：`HTTP_401_UNAUTHORIZED`

| 属性 | 值 |
|------|---|
| HTTP 状态码 | 401 |
| 错误类型 | 认证失败 |
| 严重程度 | 中 |
| 可重试 | 是（修正认证信息后重试） |

**含义**：客户端未提供有效的认证信息，或认证信息已过期。

**常见原因**：

1. 未提供 API Key（`Authorization` 头缺失）
2. API Key 无效或已过期
3. API Key 格式错误（应为 `Bearer <token>` 格式）
4. 会话 Token 已过期

**解决方案**：

1. 检查 `Authorization` 头是否存在且格式正确
2. 确认 API Key 有效且未过期
3. 重新获取会话 Token

**示例**：

```json
// 请求
GET /api/sessions
// 缺少 Authorization 头

// 响应
{
  "error": {
    "code": "HTTP_401_UNAUTHORIZED",
    "message": "未提供认证信息，请在请求头中添加 Authorization",
    "details": {
      "expected_header": "Authorization: Bearer <token>",
      "documentation_url": "/docs/api/authentication"
    },
    "timestamp": "2026-06-19T10:30:00Z",
    "request_id": "req-def456"
  }
}
```

### 2.3 403 Forbidden

**错误码**：`HTTP_403_FORBIDDEN`

| 属性 | 值 |
|------|---|
| HTTP 状态码 | 403 |
| 错误类型 | 权限不足 |
| 严重程度 | 中 |
| 可重试 | 否（需提升权限） |

**含义**：客户端已认证，但无权访问请求的资源。

**常见原因**：

1. 尝试访问他人的会话数据
2. 尝试执行需要管理员权限的操作
3. API Key 权限不足（如只读 Key 尝试写入）
4. IP 地址被加入黑名单

**解决方案**：

1. 确认是否有权访问目标资源
2. 联系管理员提升 API Key 权限
3. 检查 IP 是否被封禁

**示例**：

```json
// 请求
DELETE /api/sessions/sess-others-user
Authorization: Bearer <token>

// 响应
{
  "error": {
    "code": "HTTP_403_FORBIDDEN",
    "message": "无权删除此会话：会话属于其他用户",
    "details": {
      "session_id": "sess-others-user",
      "current_user": "user-current",
      "session_owner": "user-other"
    },
    "timestamp": "2026-06-19T10:30:00Z",
    "request_id": "req-ghi789"
  }
}
```

### 2.4 404 Not Found

**错误码**：`HTTP_404_NOT_FOUND`

| 属性 | 值 |
|------|---|
| HTTP 状态码 | 404 |
| 错误类型 | 资源不存在 |
| 严重程度 | 低 |
| 可重试 | 否（需修正请求路径） |

**含义**：客户端请求的资源不存在。

**常见原因**：

1. 会话 ID 不存在或已删除
2. 论题 ID 不存在
3. API 路径拼写错误
4. 资源已被永久删除

**解决方案**：

1. 检查请求路径是否正确
2. 确认资源 ID 是否存在
3. 查询资源列表获取有效 ID

**示例**：

```json
// 请求
GET /api/sessions/sess-nonexistent

// 响应
{
  "error": {
    "code": "HTTP_404_NOT_FOUND",
    "message": "会话不存在",
    "details": {
      "resource_type": "session",
      "resource_id": "sess-nonexistent",
      "suggestion": "请调用 GET /api/sessions 获取有效会话列表"
    },
    "timestamp": "2026-06-19T10:30:00Z",
    "request_id": "req-jkl012"
  }
}
```

### 2.5 409 Conflict

**错误码**：`HTTP_409_CONFLICT`

| 属性 | 值 |
|------|---|
| HTTP 状态码 | 409 |
| 错误类型 | 资源冲突 |
| 严重程度 | 低 |
| 可重试 | 是（解决冲突后重试） |

**含义**：请求与服务器当前状态冲突。

**常见原因**：

1. 创建会话时使用了已存在的会话名称
2. 并发修改同一资源导致冲突
3. 资源状态不允许当前操作（如尝试删除正在生成论题的会话）

**解决方案**：

1. 使用不同的资源名称
2. 重新获取资源状态后重试
3. 等待当前操作完成后再执行

**示例**：

```json
// 请求
POST /api/sessions
{
  "name": "我的论题会话",
  "degree": "master"
}

// 响应
{
  "error": {
    "code": "HTTP_409_CONFLICT",
    "message": "会话名称已存在",
    "details": {
      "conflict_field": "name",
      "conflict_value": "我的论题会话",
      "existing_session_id": "sess-abc123",
      "suggestion": "请使用不同的会话名称"
    },
    "timestamp": "2026-06-19T10:30:00Z",
    "request_id": "req-mno345"
  }
}
```

### 2.6 422 Unprocessable Entity

**错误码**：`HTTP_422_UNPROCESSABLE_ENTITY`

| 属性 | 值 |
|------|---|
| HTTP 状态码 | 422 |
| 错误类型 | 实体验证失败 |
| 严重程度 | 中 |
| 可重试 | 否（需修正请求内容） |

**含义**：请求格式正确，但由于语义错误无法处理。在 ThesisMiner 中，这通常表示硬约束违规。

**常见原因**：

1. 标题格式不合规（超过 20 字、含主动动词等）
2. 研究周期超出学位规定时间
3. 文献数量低于基线要求
4. 学科与学位级别不匹配

**解决方案**：

1. 根据错误详情修正请求内容
2. 参考约束文档了解格式要求
3. 使用自动重写功能修正标题

**示例**：

```json
// 请求
POST /api/proposals/generate
{
  "session_id": "sess-abc123",
  "title": "基于深度学习技术的图像识别算法研究与应用系统设计"
  // 标题超过 20 字
}

// 响应
{
  "error": {
    "code": "HTTP_422_UNPROCESSABLE_ENTITY",
    "message": "标题格式不合规",
    "details": {
      "constraint": "title_length",
      "violation": "标题长度超过 20 字限制",
      "current_length": 24,
      "max_length": 20,
      "suggested_title": "基于深度学习的图像识别研究",
      "auto_rewrite_available": true
    },
    "timestamp": "2026-06-19T10:30:00Z",
    "request_id": "req-pqr678"
  }
}
```

### 2.7 429 Too Many Requests

**错误码**：`HTTP_429_TOO_MANY_REQUESTS`

| 属性 | 值 |
|------|---|
| HTTP 状态码 | 429 |
| 错误类型 | 速率限制 |
| 严重程度 | 低 |
| 可重试 | 是（等待后重试） |

**含义**：客户端在短时间内发送了过多请求，触发了速率限制。

**常见原因**：

1. 超过每分钟请求限制（默认 60 次/分钟）
2. 超过每日请求配额（默认 1000 次/天）
3. 超过 AI 模型调用限制（默认 30 次/小时）

**解决方案**：

1. 等待 `Retry-After` 头指定的时间后重试
2. 使用指数退避策略重试
3. 升级到更高级别的 API 配额

**示例**：

```json
// 响应
HTTP/1.1 429 Too Many Requests
Retry-After: 30
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1718798100

{
  "error": {
    "code": "HTTP_429_TOO_MANY_REQUESTS",
    "message": "请求频率超过限制",
    "details": {
      "limit": 60,
      "window": "60s",
      "retry_after": 30,
      "upgrade_url": "/docs/api/rate_limiting#upgrade"
    },
    "timestamp": "2026-06-19T10:30:00Z",
    "request_id": "req-stu901"
  }
}
```

---

## 3. HTTP 5xx 服务端错误码

### 3.1 500 Internal Server Error

**错误码**：`HTTP_500_INTERNAL_SERVER_ERROR`

| 属性 | 值 |
|------|---|
| HTTP 状态码 | 500 |
| 错误类型 | 服务器内部错误 |
| 严重程度 | 高 |
| 可重试 | 是（使用指数退避） |

**含义**：服务器遇到意外情况，无法完成请求。

**常见原因**：

1. 数据库连接失败
2. 未处理的 Python 异常
3. 内存不足（OOM）
4. 文件系统权限错误
5. 配置文件损坏

**解决方案**：

1. 查看服务器日志获取详细错误信息
2. 检查数据库连接状态
3. 检查系统资源使用情况
4. 联系系统管理员

**示例**：

```json
{
  "error": {
    "code": "HTTP_500_INTERNAL_SERVER_ERROR",
    "message": "服务器内部错误",
    "details": {
      "error_id": "err-internal-001",
      "log_reference": "log-20260619-103000-abc123",
      "suggestion": "请联系管理员并提供 error_id 和 log_reference"
    },
    "timestamp": "2026-06-19T10:30:00Z",
    "request_id": "req-vwx234"
  }
}
```

### 3.2 502 Bad Gateway

**错误码**：`HTTP_502_BAD_GATEWAY`

| 属性 | 值 |
|------|---|
| HTTP 状态码 | 502 |
| 错误类型 | 网关错误 |
| 严重程度 | 高 |
| 可重试 | 是 |

**含义**：服务器作为网关或代理时，从上游服务器收到无效响应。

**常见原因**：

1. AI 模型服务不可用（OpenAI/DeepSeek API 宕机）
2. 反向代理配置错误
3. 上游服务超时

**解决方案**：

1. 检查 AI 模型服务状态
2. 验证反向代理配置
3. 增加上游服务超时时间

### 3.3 503 Service Unavailable

**错误码**：`HTTP_503_SERVICE_UNAVAILABLE`

| 属性 | 值 |
|------|---|
| HTTP 状态码 | 503 |
| 错误类型 | 服务不可用 |
| 严重程度 | 高 |
| 可重试 | 是（等待后重试） |

**含义**：服务器暂时无法处理请求，通常由于维护或过载。

**常见原因**：

1. 服务器正在进行维护
2. 服务器负载过高
3. 依赖服务不可用
4. 数据库锁定

**解决方案**：

1. 等待服务恢复
2. 检查服务器负载
3. 查看维护公告

### 3.4 504 Gateway Timeout

**错误码**：`HTTP_504_GATEWAY_TIMEOUT`

| 属性 | 值 |
|------|---|
| HTTP 状态码 | 504 |
| 错误类型 | 网关超时 |
| 严重程度 | 高 |
| 可重试 | 是 |

**含义**：服务器作为网关或代理时，未及时从上游服务器收到响应。

**常见原因**：

1. AI 模型调用超时（超过 120 秒）
2. 数据库查询超时
3. 网络延迟过高

**解决方案**：

1. 增加 AI 模型调用超时时间
2. 优化数据库查询
3. 检查网络连接

---

## 4. 业务错误码

### 4.1 会话管理错误码（SESSION_*）

| 错误码 | HTTP 状态码 | 含义 | 原因 | 解决方案 |
|--------|------------|------|------|---------|
| `BIZ_SESSION_CREATE_001` | 500 | 会话创建失败 | 数据库写入失败 | 检查数据库连接 |
| `BIZ_SESSION_CREATE_002` | 400 | 会话创建参数无效 | 缺少必填字段 | 补全必填参数 |
| `BIZ_SESSION_CREATE_003` | 409 | 会话名称重复 | 名称已存在 | 更换会话名称 |
| `BIZ_SESSION_LIST_001` | 500 | 会话列表查询失败 | 数据库读取失败 | 检查数据库连接 |
| `BIZ_SESSION_LIST_002` | 400 | 分页参数无效 | page/size 参数错误 | 修正分页参数 |
| `BIZ_SESSION_DETAIL_001` | 404 | 会话不存在 | ID 错误或已删除 | 检查会话 ID |
| `BIZ_SESSION_DETAIL_002` | 403 | 无权访问会话 | 权限不足 | 确认访问权限 |
| `BIZ_SESSION_UPDATE_001` | 404 | 会话更新失败-不存在 | ID 错误 | 检查会话 ID |
| `BIZ_SESSION_UPDATE_002` | 400 | 会话更新参数无效 | 参数格式错误 | 修正参数 |
| `BIZ_SESSION_UPDATE_003` | 409 | 会话状态冲突 | 状态不允许更新 | 等待操作完成 |
| `BIZ_SESSION_DELETE_001` | 404 | 会话删除失败-不存在 | ID 错误 | 检查会话 ID |
| `BIZ_SESSION_DELETE_002` | 409 | 会话删除冲突 | 正在生成论题 | 等待生成完成 |
| `BIZ_SESSION_STATE_001` | 400 | 状态转换无效 | 状态机不允许此转换 | 检查状态机规则 |
| `BIZ_SESSION_STATE_002` | 500 | 状态更新失败 | 数据库错误 | 检查数据库 |
| `BIZ_SESSION_CONTEXT_001` | 500 | 上下文压缩失败 | DST 压缩异常 | 检查 DST 配置 |
| `BIZ_SESSION_CONTEXT_002` | 400 | 上下文长度超限 | 历史消息过多 | 增加压缩频率 |

### 4.2 对话管理错误码（CONVERSATION_*）

| 错误码 | HTTP 状态码 | 含义 | 原因 | 解决方案 |
|--------|------------|------|------|---------|
| `BIZ_CONVERSATION_CREATE_001` | 400 | 对话创建参数无效 | 缺少 session_id | 提供有效的 session_id |
| `BIZ_CONVERSATION_CREATE_002` | 404 | 关联会话不存在 | session_id 错误 | 检查 session_id |
| `BIZ_CONVERSATION_SEND_001` | 400 | 消息内容为空 | 消息体为空 | 提供消息内容 |
| `BIZ_CONVERSATION_SEND_002` | 400 | 消息内容过长 | 超过 10000 字 | 缩减消息长度 |
| `BIZ_CONVERSATION_SEND_003` | 422 | 消息触发硬约束 | 内容不合规 | 修正消息内容 |
| `BIZ_CONVERSATION_SEND_004` | 429 | AI 调用频率超限 | 超过模型调用限制 | 等待后重试 |
| `BIZ_CONVERSATION_SEND_005` | 502 | AI 模型不可用 | 模型服务宕机 | 切换备用模型 |
| `BIZ_CONVERSATION_SEND_006` | 504 | AI 模型调用超时 | 超过 120 秒 | 增加超时时间 |
| `BIZ_CONVERSATION_STREAM_001` | 500 | 流式输出中断 | 网络断开 | 重新发起请求 |
| `BIZ_CONVERSATION_STREAM_002` | 500 | SSE 编码错误 | 内部序列化失败 | 检查数据格式 |
| `BIZ_CONVERSATION_HISTORY_001` | 404 | 历史消息不存在 | 对话 ID 错误 | 检查对话 ID |
| `BIZ_CONVERSATION_HISTORY_002` | 400 | 历史查询参数无效 | 分页参数错误 | 修正参数 |
| `BIZ_CONVERSATION_DELETE_001` | 404 | 对话删除失败-不存在 | ID 错误 | 检查对话 ID |
| `BIZ_CONVERSATION_RENAME_001` | 404 | 对话重命名失败-不存在 | ID 错误 | 检查对话 ID |
| `BIZ_CONVERSATION_RENAME_002` | 400 | 新名称无效 | 为空或过长 | 提供有效名称 |

### 4.3 论题管理错误码（PROPOSAL_*）

| 错误码 | HTTP 状态码 | 含义 | 原因 | 解决方案 |
|--------|------------|------|------|---------|
| `BIZ_PROPOSAL_GENERATE_001` | 400 | 论题生成参数无效 | 缺少必填字段 | 补全参数 |
| `BIZ_PROPOSAL_GENERATE_002` | 404 | 关联会话不存在 | session_id 错误 | 检查 session_id |
| `BIZ_PROPOSAL_GENERATE_003` | 422 | 论题生成被约束拦截 | 硬约束违规 | 修正输入参数 |
| `BIZ_PROPOSAL_GENERATE_004` | 429 | 生成频率超限 | 超过限制 | 等待后重试 |
| `BIZ_PROPOSAL_GENERATE_005` | 502 | AI 模型不可用 | 模型服务宕机 | 切换模型 |
| `BIZ_PROPOSAL_GENERATE_006` | 504 | 生成超时 | 超过 180 秒 | 增加超时 |
| `BIZ_PROPOSAL_GENERATE_007` | 500 | 生成失败-Reasoner | Reasoner Agent 异常 | 查看日志 |
| `BIZ_PROPOSAL_GENERATE_008` | 500 | 生成失败-Mentor | Mentor Agent 异常 | 查看日志 |
| `BIZ_PROPOSAL_GENERATE_009` | 500 | 生成失败-Searcher | Searcher Agent 异常 | 查看日志 |
| `BIZ_PROPOSAL_GENERATE_010` | 500 | 编排状态机异常 | 状态转换失败 | 检查状态机 |
| `BIZ_PROPOSAL_LIST_001` | 500 | 论题列表查询失败 | 数据库错误 | 检查数据库 |
| `BIZ_PROPOSAL_DETAIL_001` | 404 | 论题不存在 | ID 错误 | 检查论题 ID |
| `BIZ_PROPOSAL_DETAIL_002` | 403 | 无权访问论题 | 权限不足 | 确认权限 |
| `BIZ_PROPOSAL_DELETE_001` | 404 | 论题删除失败-不存在 | ID 错误 | 检查论题 ID |
| `BIZ_PROPOSAL_DELETE_002` | 409 | 论题删除冲突 | 正在使用中 | 等待操作完成 |
| `BIZ_PROPOSAL_EXPORT_001` | 404 | 导出失败-论题不存在 | ID 错误 | 检查论题 ID |
| `BIZ_PROPOSAL_EXPORT_002` | 500 | 导出失败-格式不支持 | 格式参数错误 | 使用支持的格式 |
| `BIZ_PROPOSAL_REPORT_001` | 404 | 开题报告生成失败-论题不存在 | ID 错误 | 检查论题 ID |
| `BIZ_PROPOSAL_REPORT_002` | 500 | 开题报告生成失败 | AI 调用失败 | 查看日志 |
| `BIZ_PROPOSAL_REPORT_003` | 504 | 开题报告生成超时 | 超过 300 秒 | 增加超时 |

### 4.4 谱系管理错误码（LINEAGE_*）

| 错误码 | HTTP 状态码 | 含义 | 原因 | 解决方案 |
|--------|------------|------|------|---------|
| `BIZ_LINEAGE_NODE_CREATE_001` | 400 | 节点创建参数无效 | 缺少必填字段 | 补全参数 |
| `BIZ_LINEAGE_NODE_CREATE_002` | 409 | 节点已存在 | ID 重复 | 使用不同 ID |
| `BIZ_LINEAGE_NODE_LIST_001` | 500 | 节点列表查询失败 | 数据库错误 | 检查数据库 |
| `BIZ_LINEAGE_NODE_DETAIL_001` | 404 | 节点不存在 | ID 错误 | 检查节点 ID |
| `BIZ_LINEAGE_NODE_UPDATE_001` | 404 | 节点更新失败-不存在 | ID 错误 | 检查节点 ID |
| `BIZ_LINEAGE_NODE_DELETE_001` | 404 | 节点删除失败-不存在 | ID 错误 | 检查节点 ID |
| `BIZ_LINEAGE_NODE_DELETE_002` | 409 | 节点删除冲突 | 存在关联边 | 先删除关联边 |
| `BIZ_LINEAGE_EDGE_CREATE_001` | 400 | 边创建参数无效 | 缺少必填字段 | 补全参数 |
| `BIZ_LINEAGE_EDGE_CREATE_002` | 404 | 源节点不存在 | source_id 错误 | 检查源节点 |
| `BIZ_LINEAGE_EDGE_CREATE_003` | 404 | 目标节点不存在 | target_id 错误 | 检查目标节点 |
| `BIZ_LINEAGE_EDGE_CREATE_004` | 409 | 边已存在 | 重复创建 | 检查已有边 |
| `BIZ_LINEAGE_EDGE_DELETE_001` | 404 | 边删除失败-不存在 | ID 错误 | 检查边 ID |
| `BIZ_LINEAGE_SEARCH_001` | 400 | 搜索参数无效 | 关键词为空 | 提供搜索关键词 |
| `BIZ_LINEAGE_SEARCH_002` | 500 | 搜索失败 | 索引错误 | 重建索引 |
| `BIZ_LINEAGE_EXPAND_001` | 404 | 图谱扩展失败-节点不存在 | ID 错误 | 检查节点 ID |
| `BIZ_LINEAGE_EXPAND_002` | 500 | 图谱扩展失败 | AI 解析失败 | 查看日志 |
| `BIZ_LINEAGE_CARD_CREATE_001` | 400 | 知识卡片创建参数无效 | 缺少必填字段 | 补全参数 |
| `BIZ_LINEAGE_CARD_LIST_001` | 500 | 卡片列表查询失败 | 数据库错误 | 检查数据库 |
| `BIZ_LINEAGE_CARD_DELETE_001` | 404 | 卡片删除失败-不存在 | ID 错误 | 检查卡片 ID |
| `BIZ_LINEAGE_BATCH_DELETE_001` | 400 | 批量删除参数无效 | ID 列表为空 | 提供 ID 列表 |
| `BIZ_LINEAGE_BATCH_DELETE_002` | 500 | 批量删除部分失败 | 部分 ID 不存在 | 检查返回详情 |

### 4.5 预算管理错误码（BUDGET_*）

| 错误码 | HTTP 状态码 | 含义 | 原因 | 解决方案 |
|--------|------------|------|------|---------|
| `BIZ_BUDGET_LEDGER_001` | 500 | 账本记录失败 | 数据库写入失败 | 检查数据库 |
| `BIZ_BUDGET_LEDGER_002` | 404 | 账本记录不存在 | 记录 ID 错误 | 检查记录 ID |
| `BIZ_BUDGET_LEDGER_003` | 400 | 账本查询参数无效 | 时间范围错误 | 修正时间范围 |
| `BIZ_BUDGET_SUMMARY_001` | 500 | 汇总统计失败 | 数据库聚合错误 | 检查数据库 |
| `BIZ_BUDGET_SUMMARY_002` | 400 | 汇总参数无效 | 维度参数错误 | 修正维度参数 |
| `BIZ_BUDGET_ESTIMATE_001` | 400 | 预算估算参数无效 | 缺少必填字段 | 补全参数 |
| `BIZ_BUDGET_ESTIMATE_002` | 500 | 预算估算失败 | 模型定价缺失 | 配置模型定价 |
| `BIZ_BUDGET_EXCEED_001` | 429 | 预算超限 | 超过配额 | 升级配额 |
| `BIZ_BUDGET_EXCEED_002` | 429 | 日预算超限 | 超过日限额 | 等待次日 |
| `BIZ_BUDGET_EXCEED_003` | 429 | 会话预算超限 | 超过会话限额 | 开启新会话 |
| `BIZ_BUDGET_EXPORT_001` | 500 | 账本导出失败 | 序列化错误 | 检查数据格式 |
| `BIZ_BUDGET_EXPORT_002` | 400 | 导出格式不支持 | 格式参数错误 | 使用支持的格式 |

### 4.6 配置管理错误码（CONFIG_*）

| 错误码 | HTTP 状态码 | 含义 | 原因 | 解决方案 |
|--------|------------|------|------|---------|
| `BIZ_CONFIG_MODEL_001` | 400 | 模型配置参数无效 | 缺少必填字段 | 补全参数 |
| `BIZ_CONFIG_MODEL_002` | 409 | 模型 ID 已存在 | ID 重复 | 使用不同 ID |
| `BIZ_CONFIG_MODEL_003` | 404 | 模型不存在 | ID 错误 | 检查模型 ID |
| `BIZ_CONFIG_MODEL_004` | 400 | 模型定价无效 | 价格格式错误 | 修正价格格式 |
| `BIZ_CONFIG_MODEL_005` | 400 | 步骤路由无效 | 步骤名称错误 | 使用有效步骤名 |
| `BIZ_CONFIG_API_KEY_001` | 400 | API Key 格式无效 | 格式错误 | 修正格式 |
| `BIZ_CONFIG_API_KEY_002` | 401 | API Key 无效 | 认证失败 | 检查 API Key |
| `BIZ_CONFIG_API_KEY_003` | 500 | API Key 加密失败 | 加密服务异常 | 检查加密配置 |
| `BIZ_CONFIG_ROUTE_001` | 400 | 路由配置无效 | 步骤-模型映射错误 | 修正映射 |
| `BIZ_CONFIG_ROUTE_002` | 404 | 路由目标模型不存在 | 模型 ID 错误 | 检查模型 ID |
| `BIZ_CONFIG_CURRENCY_001` | 400 | 货币代码无效 | 不支持的货币 | 使用 CNY 或 USD |
| `BIZ_CONFIG_SAVE_001` | 500 | 配置保存失败 | 文件写入失败 | 检查文件权限 |
| `BIZ_CONFIG_LOAD_001` | 500 | 配置加载失败 | 文件读取失败 | 检查文件存在 |
| `BIZ_CONFIG_LOAD_002` | 500 | 配置解析失败 | JSON 格式错误 | 修正 JSON 格式 |

---

## 5. Agent 错误码

### 5.1 Reasoner Agent 错误码

| 错误码 | HTTP 状态码 | 含义 | 原因 | 解决方案 |
|--------|------------|------|------|---------|
| `AGENT_REASONER_TIMEOUT_001` | 504 | Reasoner 调用超时 | 超过 120 秒 | 增加超时或简化输入 |
| `AGENT_REASONER_TIMEOUT_002` | 504 | Reasoner 流式超时 | 流式中断超过 30 秒 | 检查网络连接 |
| `AGENT_REASONER_FAILURE_001` | 502 | Reasoner 调用失败 | 模型返回错误 | 查看模型错误信息 |
| `AGENT_REASONER_FAILURE_002` | 500 | Reasoner 内部错误 | 代码异常 | 查看错误日志 |
| `AGENT_REASONER_PARSE_001` | 500 | Reasoner 响应解析失败 | JSON 格式错误 | 检查模型输出 |
| `AGENT_REASONER_PARSE_002` | 500 | Reasoner 响应字段缺失 | 缺少必填字段 | 检查 Prompt 模板 |
| `AGENT_REASONER_CONTEXT_001` | 500 | Reasoner 上下文溢出 | 超过模型上下文窗口 | 增加 DST 压缩 |
| `AGENT_REASONER_CONTEXT_002` | 500 | Reasoner 上下文构建失败 | DST 状态异常 | 检查 DST 配置 |
| `AGENT_REASONER_MODEL_001` | 503 | Reasoner 模型不可用 | 模型服务宕机 | 切换备用模型 |
| `AGENT_REASONER_MODEL_002` | 503 | Reasoner 模型限流 | 超过模型速率限制 | 等待后重试 |

### 5.2 Mentor Agent 错误码

| 错误码 | HTTP 状态码 | 含义 | 原因 | 解决方案 |
|--------|------------|------|------|---------|
| `AGENT_MENTOR_TIMEOUT_001` | 504 | Mentor 调用超时 | 超过 90 秒 | 增加超时 |
| `AGENT_MENTOR_FAILURE_001` | 502 | Mentor 调用失败 | 模型返回错误 | 查看错误信息 |
| `AGENT_MENTOR_FAILURE_002` | 500 | Mentor 内部错误 | 代码异常 | 查看日志 |
| `AGENT_MENTOR_PARSE_001` | 500 | Mentor 响应解析失败 | JSON 格式错误 | 检查输出 |
| `AGENT_MENTOR_CONTEXT_001` | 500 | Mentor 上下文溢出 | 超过上下文窗口 | 增加压缩 |
| `AGENT_MENTOR_MODEL_001` | 503 | Mentor 模型不可用 | 服务宕机 | 切换模型 |
| `AGENT_MENTOR_MODEL_002` | 503 | Mentor 模型限流 | 超过限制 | 等待重试 |
| `AGENT_MENTOR_REVIEW_001` | 500 | Mentor 评审失败 | 评审逻辑异常 | 查看日志 |

### 5.3 Searcher Agent 错误码

| 错误码 | HTTP 状态码 | 含义 | 原因 | 解决方案 |
|--------|------------|------|------|---------|
| `AGENT_SEARCHER_TIMEOUT_001` | 504 | Searcher 检索超时 | 超过 5 秒 | 使用模拟检索 |
| `AGENT_SEARCHER_TIMEOUT_002` | 504 | Searcher API 超时 | arXiv/S2 超时 | 检查网络 |
| `AGENT_SEARCHER_FAILURE_001` | 502 | Searcher 检索失败 | API 返回错误 | 查看错误 |
| `AGENT_SEARCHER_FAILURE_002` | 500 | Searcher 内部错误 | 代码异常 | 查看日志 |
| `AGENT_SEARCHER_PARSE_001` | 500 | Searcher 结果解析失败 | XML/JSON 格式错误 | 检查 API 输出 |
| `AGENT_SEARCHER_DEGRADE_001` | 200 | Searcher 降级到模拟 | 真实检索不可用 | 检查 API 配置 |
| `AGENT_SEARCHER_EMPTY_001` | 200 | Searcher 结果为空 | 无匹配文献 | 调整关键词 |
| `AGENT_SEARCHER_RATE_001` | 429 | Searcher API 限流 | 超过 API 限制 | 等待重试 |

### 5.4 通用 Agent 错误码

| 错误码 | HTTP 状态码 | 含义 | 原因 | 解决方案 |
|--------|------------|------|------|---------|
| `AGENT_TIMEOUT_001` | 504 | Agent 通用超时 | 超过配置超时 | 增加超时 |
| `AGENT_TIMEOUT_002` | 504 | Agent 重试超时 | 重试次数耗尽 | 检查模型可用性 |
| `AGENT_FAILURE_001` | 502 | Agent 通用失败 | 模型返回错误 | 查看错误 |
| `AGENT_FAILURE_002` | 500 | Agent 内部错误 | 代码异常 | 查看日志 |
| `AGENT_FAILURE_003` | 500 | Agent 状态错误 | 状态机异常 | 检查状态机 |
| `AGENT_CONTEXT_OVERFLOW_001` | 500 | Agent 上下文溢出 | 超过窗口 | 增加压缩 |
| `AGENT_CONTEXT_OVERFLOW_002` | 500 | Agent 上下文构建失败 | DST 异常 | 检查 DST |
| `AGENT_MODEL_UNAVAILABLE_001` | 503 | Agent 模型不可用 | 服务宕机 | 切换模型 |
| `AGENT_MODEL_UNAVAILABLE_002` | 503 | Agent 模型限流 | 超过限制 | 等待重试 |
| `AGENT_MODEL_UNAVAILABLE_003` | 503 | Agent 模型配置缺失 | 未配置模型 | 配置模型 |
| `AGENT_PARSE_ERROR_001` | 500 | Agent 响应解析失败 | JSON 格式错误 | 检查输出 |
| `AGENT_PARSE_ERROR_002` | 500 | Agent 响应字段缺失 | 缺少必填字段 | 检查 Prompt |
| `AGENT_PARSE_ERROR_003` | 500 | Agent 响应类型错误 | 字段类型不匹配 | 检查 Prompt |
| `AGENT_REGISTRY_001` | 500 | Agent 注册失败 | ID 重复 | 使用不同 ID |
| `AGENT_REGISTRY_002` | 404 | Agent 未注册 | ID 不存在 | 检查 Agent ID |
| `AGENT_REGISTRY_003` | 500 | Agent 注销失败 | Agent 正在运行 | 等待完成 |
| `AGENT_HOOK_001` | 500 | Hook 执行失败 | Hook 代码异常 | 检查 Hook |
| `AGENT_HOOK_002` | 500 | Hook 超时 | 超过 30 秒 | 优化 Hook |
| `AGENT_HOOK_003` | 422 | Hook 拦截请求 | 约束违规 | 修正输入 |
| `AGENT_ORCHESTRATION_001` | 500 | 编排状态机错误 | 非法状态转换 | 检查状态机 |
| `AGENT_ORCHESTRATION_002` | 500 | 编排流程中断 | Agent 失败 | 查看日志 |
| `AGENT_ORCHESTRATION_003` | 500 | 编排结果聚合失败 | 结果格式不一致 | 检查 Agent 输出 |

---

## 6. 约束错误码

### 6.1 标题约束错误码

| 错误码 | HTTP 状态码 | 含义 | 原因 | 解决方案 |
|--------|------------|------|------|---------|
| `CONSTRAINT_TITLE_LENGTH_001` | 422 | 标题过长 | 超过 20 字 | 缩减标题 |
| `CONSTRAINT_TITLE_LENGTH_002` | 422 | 标题过短 | 少于 5 字 | 增加标题内容 |
| `CONSTRAINT_TITLE_VERB_001` | 422 | 标题含主动动词 | 包含"研究/设计/实现"等 | 使用名词性短语 |
| `CONSTRAINT_TITLE_VERB_002` | 422 | 标题含第一人称 | 包含"我/我们" | 使用第三人称 |
| `CONSTRAINT_TITLE_FORMAT_001` | 422 | 标题格式错误 | 含特殊字符 | 移除特殊字符 |
| `CONSTRAINT_TITLE_FORMAT_002` | 422 | 标题含问句 | 以问号结尾 | 改为陈述句 |
| `CONSTRAINT_TITLE_FORMAT_003` | 422 | 标题含感叹 | 以感叹号结尾 | 改为陈述句 |
| `CONSTRAINT_TITLE_DUPLICATE_001` | 422 | 标题重复 | 与已有论题重复 | 修改标题 |

### 6.2 时间约束错误码

| 错误码 | HTTP 状态码 | 含义 | 原因 | 解决方案 |
|--------|------------|------|------|---------|
| `CONSTRAINT_TIME_MASTER_001` | 422 | 硕士周期超长 | 超过 12 个月 | 缩减研究范围 |
| `CONSTRAINT_TIME_MASTER_002` | 422 | 硕士周期过短 | 少于 6 个月 | 增加研究深度 |
| `CONSTRAINT_TIME_DOCTOR_001` | 422 | 博士周期超长 | 超过 36 个月 | 缩减研究范围 |
| `CONSTRAINT_TIME_DOCTOR_002` | 422 | 博士周期过短 | 少于 18 个月 | 增加研究深度 |
| `CONSTRAINT_TIME_PHASE_001` | 422 | 阶段时间分配不当 | 某阶段过长/过短 | 调整时间分配 |
| `CONSTRAINT_TIME_BUFFER_001` | 422 | 缺少缓冲时间 | 未预留修改时间 | 增加缓冲 |

### 6.3 文献约束错误码

| 错误码 | HTTP 状态码 | 含义 | 原因 | 解决方案 |
|--------|------------|------|------|---------|
| `CONSTRAINT_LIT_MASTER_001` | 422 | 硕士文献不足 | 少于 30 篇 | 增加文献 |
| `CONSTRAINT_LIT_DOCTOR_001` | 422 | 博士文献不足 | 少于 50 篇 | 增加文献 |
| `CONSTRAINT_LIT_RECENT_001` | 422 | 近期文献不足 | 近 5 年文献 <40% | 增加新文献 |
| `CONSTRAINT_LIT_TYPE_001` | 422 | 期刊文献不足 | 期刊 <50% | 增加期刊文献 |
| `CONSTRAINT_LIT_TYPE_002` | 422 | 会议文献不足 | 会议 <20% | 增加会议文献 |
| `CONSTRAINT_LIT_QUALITY_001` | 422 | 高质量文献不足 | SCI/SSCI 文献不足 | 增加高质量文献 |

### 6.4 新颖性约束错误码

| 错误码 | HTTP 状态码 | 含义 | 原因 | 解决方案 |
|--------|------------|------|------|---------|
| `CONSTRAINT_NOVELTY_LOW_001` | 422 | 新颖性评分过低 | <40 分 | 增加创新点 |
| `CONSTRAINT_NOVELTY_LOW_002` | 422 | 学科交叉度低 | <30 分 | 增加学科交叉 |
| `CONSTRAINT_NOVELTY_LOW_003` | 422 | 方法迁移度低 | <30 分 | 增加方法创新 |
| `CONSTRAINT_NOVELTY_LOW_004` | 422 | 痛点突破度低 | <30 分 | 聚焦核心痛点 |
| `CONSTRAINT_NOVELTY_LOW_005` | 422 | 趋势前瞻度低 | <30 分 | 选择前沿方向 |
| `CONSTRAINT_NOVELTY_PENALTY_001` | 422 | 新颖性惩罚 | 多维度低分 | 全面改进 |

### 6.5 风格约束错误码

| 错误码 | HTTP 状态码 | 含义 | 原因 | 解决方案 |
|--------|------------|------|------|---------|
| `CONSTRAINT_STYLE_FAIL_001` | 422 | 风格质量不达标 | <60 分 | 改进写作风格 |
| `CONSTRAINT_STYLE_DIVERSITY_001` | 422 | 句式多样性不足 | <40 分 | 交替使用句式 |
| `CONSTRAINT_STYLE_VOCAB_001` | 422 | 词汇丰富度不足 | <40 分 | 增加学术词汇 |
| `CONSTRAINT_STYLE_COHERENCE_001` | 422 | 逻辑连贯性不足 | <40 分 | 增加连接词 |
| `CONSTRAINT_STYLE_NORMATIVITY_001` | 422 | 学术规范性不足 | <40 分 | 检查学术规范 |
| `CONSTRAINT_STYLE_PERSON_001` | 422 | 人称不规范 | 使用第一/二人称 | 使用第三人称 |
| `CONSTRAINT_STYLE_COLLOQUIAL_001` | 422 | 用语口语化 | 含口语表达 | 使用学术用语 |

### 6.6 重复度约束错误码

| 错误码 | HTTP 状态码 | 含义 | 原因 | 解决方案 |
|--------|------------|------|------|---------|
| `CONSTRAINT_DUPLICATION_HIGH_001` | 422 | 重复度过高 | >30% | 重写重复部分 |
| `CONSTRAINT_DUPLICATION_HIGH_002` | 422 | 重复度严重 | >50% | 全面重写 |
| `CONSTRAINT_DUPLICATION_SIMHASH_001` | 422 | SimHash 重复度高 | >30% | 修改文本 |
| `CONSTRAINT_DUPLICATION_MINHASH_001` | 422 | MinHash 重复度高 | >30% | 修改片段 |
| `CONSTRAINT_DUPLICATION_COSINE_001` | 422 | 余弦相似度高 | >30% | 调整主题 |

### 6.7 AI 痕迹约束错误码

| 错误码 | HTTP 状态码 | 含义 | 原因 | 解决方案 |
|--------|------------|------|------|---------|
| `CONSTRAINT_AI_TRACE_HIGH_001` | 422 | AI 痕迹置信度高 | >80% | 重写 AI 痕迹 |
| `CONSTRAINT_AI_TRACE_HIGH_002` | 422 | AI 痕迹风险高 | 高风险 | 修改模板词 |
| `CONSTRAINT_AI_TEMPLATE_001` | 422 | 模板词过多 | >10 个/千字 | 减少模板词 |
| `CONSTRAINT_AI_PATTERN_001` | 422 | AI 句式模式 | 匹配 AI 典型句式 | 调整句式 |
| `CONSTRAINT_AI_STRUCTURE_001` | 422 | AI 结构特征 | 匹配 AI 典型结构 | 调整结构 |

### 6.8 通用约束错误码

| 错误码 | HTTP 状态码 | 含义 | 原因 | 解决方案 |
|--------|------------|------|------|---------|
| `CONSTRAINT_VIOLATION_001` | 422 | 通用约束违规 | 约束检查失败 | 查看详情 |
| `CONSTRAINT_VIOLATION_002` | 422 | 多重约束违规 | 多个约束失败 | 逐个修正 |
| `CONSTRAINT_INTERCEPT_001` | 422 | 硬约束拦截 | HardRule 拦截 | 修正违规项 |
| `CONSTRAINT_INTERCEPT_002` | 422 | 可行性拦截 | FeasibilityCheck 拦截 | 调整可行性 |
| `CONSTRAINT_INTERCEPT_003` | 422 | 后置拦截 | PostReasoner 拦截 | 修正标题 |
| `CONSTRAINT_INTERCEPT_004` | 422 | 前置拦截 | PreSearch 拦截 | 修正输入 |
| `CONSTRAINT_REWRITE_001` | 200 | 自动重写触发 | 标题需重写 | 查看重写结果 |
| `CONSTRAINT_REWRITE_002` | 422 | 自动重写失败 | 重写后仍不合规 | 手动修改 |
| `CONSTRAINT_RETRY_001` | 422 | 约束重试耗尽 | 重试次数用完 | 手动修改 |
| `CONSTRAINT_DEGRADE_001` | 200 | 约束降级 | 降级到宽松模式 | 检查配置 |

---

## 7. 缓存错误码

### 7.1 缓存命中错误码

| 错误码 | HTTP 状态码 | 含义 | 原因 | 解决方案 |
|--------|------------|------|------|---------|
| `CACHE_MISS_001` | 200 | 缓存未命中 | 首次请求 | 正常行为 |
| `CACHE_MISS_002` | 200 | 缓存未命中-前缀变化 | DST 状态变化 | 检查 DST 压缩 |
| `CACHE_MISS_003` | 200 | 缓存未命中-会话切换 | 会话上下文变化 | 正常行为 |
| `CACHE_HIT_001` | 200 | 缓存命中 | 前缀匹配 | 正常行为 |
| `CACHE_PARTIAL_001` | 200 | 部分缓存命中 | 前缀命中但后缀不同 | 正常行为 |

### 7.2 缓存有效性错误码

| 错误码 | HTTP 状态码 | 含义 | 原因 | 解决方案 |
|--------|------------|------|------|---------|
| `CACHE_INVALID_001` | 500 | 缓存无效 | 缓存数据损坏 | 清除缓存 |
| `CACHE_INVALID_002` | 500 | 缓存格式错误 | 序列化失败 | 清除缓存 |
| `CACHE_INVALID_003` | 500 | 缓存版本不匹配 | 缓存版本过期 | 清除缓存 |
| `CACHE_EXPIRED_001` | 200 | 缓存过期 | 超过 TTL | 正常行为 |
| `CACHE_EXPIRED_002` | 200 | 缓存提前过期 | 被手动清除 | 正常行为 |

### 7.3 缓存前缀错误码

| 错误码 | HTTP 状态码 | 含义 | 原因 | 解决方案 |
|--------|------------|------|------|---------|
| `CACHE_PREFIX_MISMATCH_001` | 500 | 前缀不匹配 | SHA-256 哈希不一致 | 检查前缀固化 |
| `CACHE_PREFIX_MISMATCH_002` | 500 | 前缀计算失败 | 哈希计算异常 | 检查哈希算法 |
| `CACHE_PREFIX_MISMATCH_003` | 500 | 前缀长度不一致 | 前缀长度变化 | 检查前缀配置 |
| `CACHE_PREFIX_EMPTY_001` | 500 | 前缀为空 | 前缀未设置 | 配置前缀 |

### 7.4 缓存压缩错误码

| 错误码 | HTTP 状态码 | 含义 | 原因 | 解决方案 |
|--------|------------|------|------|---------|
| `CACHE_COMPRESSION_ERROR_001` | 500 | DST 压缩失败 | 压缩算法异常 | 检查 DST 配置 |
| `CACHE_COMPRESSION_ERROR_002` | 500 | DST 压缩后过长 | 压缩效果不佳 | 调整压缩参数 |
| `CACHE_COMPRESSION_ERROR_003` | 500 | DST 解压失败 | 解压数据损坏 | 清除缓存 |
| `CACHE_COMPRESSION_ERROR_004` | 500 | DST 状态丢失 | 状态序列化失败 | 检查 DST |

### 7.5 缓存管理错误码

| 错误码 | HTTP 状态码 | 含义 | 原因 | 解决方案 |
|--------|------------|------|------|---------|
| `CACHE_CLEAR_001` | 500 | 缓存清除失败 | 清除操作异常 | 重启服务 |
| `CACHE_CLEAR_002` | 400 | 缓存清除参数无效 | 范围参数错误 | 修正参数 |
| `CACHE_STATS_001` | 500 | 缓存统计失败 | 统计查询异常 | 检查数据库 |
| `CACHE_STATS_002` | 404 | 缓存统计不存在 | 统计数据未生成 | 先运行统计 |
| `CACHE_CONFIG_001` | 400 | 缓存配置无效 | 参数错误 | 修正配置 |
| `CACHE_CONFIG_002` | 500 | 缓存配置保存失败 | 文件写入失败 | 检查权限 |

---

## 8. 错误响应格式规范

### 8.1 标准错误响应格式

```json
{
  "error": {
    "code": "错误码",
    "message": "错误简要描述",
    "details": {
      "field": "具体字段",
      "value": "当前值",
      "expected": "期望值",
      "suggestion": "改进建议"
    },
    "timestamp": "2026-06-19T10:30:00Z",
    "request_id": "req-unique-id",
    "documentation_url": "/docs/api/error_codes#错误码"
  }
}
```

### 8.2 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `error.code` | string | 是 | 错误码，格式为 `CATEGORY_SPECIFIC_SEQUENCE` |
| `error.message` | string | 是 | 错误的简要描述，不超过 200 字 |
| `error.details` | object | 否 | 错误详情，包含具体字段、当前值、期望值等 |
| `error.timestamp` | string | 是 | 错误发生时间，ISO 8601 格式 |
| `error.request_id` | string | 是 | 请求唯一标识，用于追踪 |
| `error.documentation_url` | string | 否 | 错误文档链接 |

### 8.3 批量错误响应格式

```json
{
  "errors": [
    {
      "code": "CONSTRAINT_TITLE_LENGTH_001",
      "message": "标题过长",
      "details": {
        "current_length": 25,
        "max_length": 20
      }
    },
    {
      "code": "CONSTRAINT_TITLE_VERB_001",
      "message": "标题含主动动词",
      "details": {
        "found_verbs": ["研究", "设计"],
        "suggestion": "使用名词性短语"
      }
    }
  ],
  "timestamp": "2026-06-19T10:30:00Z",
  "request_id": "req-batch-001"
}
```

---

## 9. 故障排查指南

### 9.1 按错误码类别诊断流程

```
┌──────────────────────────────────────────────────────┐
│              错误诊断流程图                            │
├──────────────────────────────────────────────────────┤
│                                                      │
│  收到错误响应                                         │
│       │                                              │
│       ▼                                              │
│  ┌─────────────┐                                    │
│  │ 检查 HTTP   │                                    │
│  │ 状态码      │                                    │
│  └──────┬──────┘                                    │
│         │                                            │
│    ┌────┼────┬────────┐                             │
│    │    │    │        │                             │
│    ▼    ▼    ▼        ▼                             │
│  4xx  5xx BIZ_*   AGENT_*                           │
│    │    │    │        │                             │
│    ▼    ▼    ▼        ▼                             │
│ ┌────┐┌────┐┌────┐  ┌────┐                         │
│ │客户端││服务端││业务 │  │Agent│                      │
│ │错误 ││错误 ││错误 │  │错误 │                      │
│ └─┬──┘└─┬──┘└─┬──┘  └─┬──┘                         │
│   │      │      │       │                            │
│   ▼      ▼      ▼       ▼                            │
│ 修正    查看    修正    检查                          │
│ 请求    日志    参数    模型                          │
│        检查            可用性                        │
│        资源                                          │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### 9.2 常见错误诊断

**诊断 1：HTTP 400 Bad Request**

```
步骤 1：检查请求体 JSON 格式
  → 使用 JSON 验证工具验证格式
  → 检查是否有缺少逗号、引号不匹配等

步骤 2：检查必填参数
  → 对照 API 文档检查必填字段
  → 确认参数类型正确

步骤 3：检查参数值范围
  → 确认枚举值在允许范围内
  → 确认数值在合理范围内
```

**诊断 2：HTTP 422 Unprocessable Entity**

```
步骤 1：查看 error.details 中的 constraint 字段
  → 确定是哪个约束违规

步骤 2：根据约束类型修正
  → 标题约束：缩减长度、移除动词
  → 时间约束：调整研究周期
  → 文献约束：增加文献数量
  → 新颖性约束：增加创新点

步骤 3：使用自动重写功能
  → 对于标题约束，可使用 auto_rewrite 功能
```

**诊断 3：HTTP 502 Bad Gateway**

```
步骤 1：检查 AI 模型服务状态
  → 访问模型服务商状态页面
  → 尝试直接调用模型 API

步骤 2：检查模型配置
  → 确认 API Key 有效
  → 确认 base_url 正确
  → 确认模型名称正确

步骤 3：切换备用模型
  → 配置备用模型
  → 更新步骤路由
```

**诊断 4：AGENT_TIMEOUT_001**

```
步骤 1：检查输入复杂度
  → 简化输入文本
  → 减少 DST 历史长度

步骤 2：增加超时时间
  → 修改配置中的 timeout 参数
  → 默认 120 秒，可增加到 180 秒

步骤 3：检查模型负载
  → 模型可能在高负载下响应慢
  → 切换到负载较低的模型
```

**诊断 5：CACHE_MISS_002（前缀变化）**

```
步骤 1：检查 DST 压缩配置
  → 确认 DST 压缩参数稳定
  → 避免频繁调整压缩参数

步骤 2：检查会话切换
  → 确认未频繁切换会话
  → 每次切换会话会导致前缀变化

步骤 3：检查 Prompt 模板
  → 确认 Prompt 前缀部分未变化
  → 前缀部分应保持稳定
```

### 9.3 错误日志分析

**日志位置**：`logs/thesisminer.log`

**日志格式**：

```
2026-06-19 10:30:00.123 | ERROR | main:handle_request:123 | request_id=req-abc123 | error_code=HTTP_500_INTERNAL_SERVER_ERROR | error_msg=数据库连接失败 | stack_trace=...
```

**日志级别**：

| 级别 | 用途 | 示例 |
|------|------|------|
| DEBUG | 调试信息 | 请求参数、响应内容 |
| INFO | 正常操作 | 会话创建、论题生成 |
| WARNING | 警告信息 | 缓存未命中、降级操作 |
| ERROR | 错误信息 | 4xx/5xx 错误 |
| CRITICAL | 严重错误 | 服务崩溃、数据丢失 |

**日志分析命令**：

```bash
# 查看最近 100 条错误日志
tail -n 100 logs/thesisminer.log | grep ERROR

# 按错误码过滤
grep "error_code=AGENT_TIMEOUT" logs/thesisminer.log

# 按请求 ID 追踪
grep "request_id=req-abc123" logs/thesisminer.log

# 按时间范围过滤
grep "2026-06-19 10:" logs/thesisminer.log | grep ERROR
```

---

## 10. 错误码速查表

### 10.1 按严重程度分类

| 严重程度 | 错误码前缀 | 处理方式 |
|---------|-----------|---------|
| 致命 | HTTP_500, HTTP_502 | 立即处理，影响所有用户 |
| 严重 | HTTP_503, HTTP_504, AGENT_* | 尽快处理，影响部分功能 |
| 中等 | HTTP_422, CONSTRAINT_* | 用户自行修正 |
| 低 | HTTP_400, HTTP_404, HTTP_409 | 用户修正请求 |
| 信息 | CACHE_MISS, CACHE_EXPIRED | 正常行为，无需处理 |

### 10.2 按可重试性分类

| 可重试 | 错误码 | 重试策略 |
|--------|--------|---------|
| 可重试 | HTTP_429, HTTP_502, HTTP_503, HTTP_504, AGENT_TIMEOUT | 指数退避 |
| 不可重试 | HTTP_400, HTTP_401, HTTP_403, HTTP_404, HTTP_422 | 修正请求 |
| 需判断 | HTTP_409, BIZ_* | 根据具体错误判断 |

### 10.3 完整错误码索引

| 序号 | 错误码 | 类别 | HTTP | 含义 |
|------|--------|------|------|------|
| 1 | HTTP_400_BAD_REQUEST | HTTP | 400 | 请求格式错误 |
| 2 | HTTP_401_UNAUTHORIZED | HTTP | 401 | 认证失败 |
| 3 | HTTP_403_FORBIDDEN | HTTP | 403 | 权限不足 |
| 4 | HTTP_404_NOT_FOUND | HTTP | 404 | 资源不存在 |
| 5 | HTTP_409_CONFLICT | HTTP | 409 | 资源冲突 |
| 6 | HTTP_422_UNPROCESSABLE_ENTITY | HTTP | 422 | 实体验证失败 |
| 7 | HTTP_429_TOO_MANY_REQUESTS | HTTP | 429 | 速率限制 |
| 8 | HTTP_500_INTERNAL_SERVER_ERROR | HTTP | 500 | 服务器内部错误 |
| 9 | HTTP_502_BAD_GATEWAY | HTTP | 502 | 网关错误 |
| 10 | HTTP_503_SERVICE_UNAVAILABLE | HTTP | 503 | 服务不可用 |
| 11 | HTTP_504_GATEWAY_TIMEOUT | HTTP | 504 | 网关超时 |
| 12-27 | BIZ_SESSION_* | 业务 | 各种 | 会话管理错误 |
| 28-42 | BIZ_CONVERSATION_* | 业务 | 各种 | 对话管理错误 |
| 43-62 | BIZ_PROPOSAL_* | 业务 | 各种 | 论题管理错误 |
| 63-83 | BIZ_LINEAGE_* | 业务 | 各种 | 谱系管理错误 |
| 84-95 | BIZ_BUDGET_* | 业务 | 各种 | 预算管理错误 |
| 96-109 | BIZ_CONFIG_* | 业务 | 各种 | 配置管理错误 |
| 110-119 | AGENT_REASONER_* | Agent | 各种 | Reasoner 错误 |
| 120-127 | AGENT_MENTOR_* | Agent | 各种 | Mentor 错误 |
| 128-135 | AGENT_SEARCHER_* | Agent | 各种 | Searcher 错误 |
| 136-157 | AGENT_* | Agent | 各种 | 通用 Agent 错误 |
| 158-165 | CONSTRAINT_TITLE_* | 约束 | 422 | 标题约束错误 |
| 166-171 | CONSTRAINT_TIME_* | 约束 | 422 | 时间约束错误 |
| 172-177 | CONSTRAINT_LIT_* | 约束 | 422 | 文献约束错误 |
| 178-183 | CONSTRAINT_NOVELTY_* | 约束 | 422 | 新颖性约束错误 |
| 184-190 | CONSTRAINT_STYLE_* | 约束 | 422 | 风格约束错误 |
| 191-195 | CONSTRAINT_DUPLICATION_* | 约束 | 422 | 重复度约束错误 |
| 196-200 | CONSTRAINT_AI_* | 约束 | 422 | AI 痕迹约束错误 |
| 201-210 | CONSTRAINT_* | 约束 | 422 | 通用约束错误 |
| 211-215 | CACHE_MISS_* | 缓存 | 200 | 缓存未命中 |
| 216-220 | CACHE_INVALID_* | 缓存 | 500 | 缓存无效 |
| 221-225 | CACHE_EXPIRED_* | 缓存 | 200 | 缓存过期 |
| 226-230 | CACHE_PREFIX_* | 缓存 | 500 | 前缀错误 |
| 231-235 | CACHE_COMPRESSION_* | 缓存 | 500 | 压缩错误 |
| 236-240 | CACHE_* | 缓存 | 各种 | 缓存管理错误 |

---

> **文档结束**  
> 本文档包含 ThesisMiner v8.0 的全部错误码参考，共计 240+ 错误码。如需了解特定错误码的详细信息，请使用文档内搜索功能查找对应章节。