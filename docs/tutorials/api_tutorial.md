# ThesisMiner v8.0 API 完整教程

> 版本：v8.0.0
> 适用对象：后端开发者、前端集成工程师、第三方接入方、运维与 SRE
> 文档更新日期：2026-06-20
> 维护团队：ThesisMiner Core Team

---

## 目录

- [1. 教程概述](#1-教程概述)
  - [1.1 文档目标](#11-文档目标)
  - [1.2 读者画像](#12-读者画像)
  - [1.3 阅读路径建议](#13-阅读路径建议)
  - [1.4 术语表](#14-术语表)
- [2. API 总览](#2-api-总览)
  - [2.1 架构定位](#21-架构定位)
  - [2.2 端点清单](#22-端点清单)
  - [2.3 请求/响应约定](#23-请求响应约定)
  - [2.4 内容类型与编码](#24-内容类型与编码)
- [3. 认证与授权](#3-认证与授权)
  - [3.1 本地部署模式](#31-本地部署模式)
  - [3.2 API Key 模式](#32-api-key-模式)
  - [3.3 多用户隔离](#33-多用户隔离)
- [4. 速率限制](#4-速率限制)
  - [4.1 限制策略](#41-限制策略)
  - [4.2 限流响应头](#42-限流响应头)
  - [4.3 客户端退避策略](#43-客户端退避策略)
- [5. 分页、过滤与排序](#5-分页过滤与排序)
  - [5.1 分页参数](#51-分页参数)
  - [5.2 过滤参数](#52-过滤参数)
  - [5.3 排序参数](#53-排序参数)
  - [5.4 游标分页](#54-游标分页)
- [6. 会话管理 API](#6-会话管理-api)
  - [6.1 创建会话](#61-创建会话)
  - [6.2 查询会话列表](#62-查询会话列表)
  - [6.3 获取会话详情](#63-获取会话详情)
  - [6.4 更新会话状态](#64-更新会话状态)
  - [6.5 删除会话](#65-删除会话)
- [7. 对话管理 API](#7-对话管理-api)
  - [7.1 创建对话](#71-创建对话)
  - [7.2 查询会话下的对话列表](#72-查询会话下的对话列表)
  - [7.3 获取对话详情](#73-获取对话详情)
  - [7.4 删除对话](#74-删除对话)
- [8. 消息管理 API](#8-消息管理-api)
  - [8.1 发送消息](#81-发送消息)
  - [8.2 查询消息历史](#82-查询消息历史)
  - [8.3 获取消息详情](#83-获取消息详情)
  - [8.4 消息引用查询](#84-消息引用查询)
- [9. Agent 管理 API](#9-agent-管理-api)
  - [9.1 查询 Agent 注册表](#91-查询-agent-注册表)
  - [9.2 查询 Agent 路由](#92-查询-agent-路由)
  - [9.3 切换 Agent 模型](#93-切换-agent-模型)
- [10. 引用管理 API](#10-引用管理-api)
  - [10.1 查询消息引用](#101-查询消息引用)
  - [10.2 引用解析](#102-引用解析)
  - [10.3 引用导出](#103-引用导出)
- [11. 缓存统计 API](#11-缓存统计-api)
  - [11.1 查询缓存命中率](#111-查询缓存命中率)
  - [11.2 重置缓存统计](#112-重置缓存统计)
  - [11.3 缓存事件流](#113-缓存事件流)
- [12. 谱系管理 API](#12-谱系管理-api)
  - [12.1 查询谱系图](#121-查询谱系图)
  - [12.2 查询节点详情](#122-查询节点详情)
  - [12.3 查询边详情](#123-查询边详情)
  - [12.4 导出谱系](#124-导出谱系)
- [13. 论题生成 API](#13-论题生成-api)
  - [13.1 触发生成](#131-触发生成)
  - [13.2 查询生成状态](#132-查询生成状态)
  - [13.3 取消生成](#133-取消生成)
- [14. 创意引擎 API](#14-创意引擎-api)
  - [14.1 触发创意](#141-触发创意)
  - [14.2 查询创意结果](#142-查询创意结果)
- [15. 约束校验 API](#15-约束校验-api)
  - [15.1 触发校验](#151-触发校验)
  - [15.2 查询校验结果](#152-查询校验结果)
- [16. 预算管理 API](#16-预算管理-api)
  - [16.1 查询预算账本](#161-查询预算账本)
  - [16.2 预算估算](#162-预算估算)
  - [16.3 预算告警](#163-预算告警)
- [17. 配置管理 API](#17-配置管理-api)
  - [17.1 查询配置](#171-查询配置)
  - [17.2 更新配置](#172-更新配置)
  - [17.3 模型列表](#173-模型列表)
- [18. SSE 流式响应](#18-sse-流式响应)
  - [18.1 SSE 协议概述](#181-sse-协议概述)
  - [18.2 事件类型清单](#182-事件类型清单)
  - [18.3 客户端实现](#183-客户端实现)
- [19. WebSocket 支持](#19-websocket-支持)
  - [19.1 连接建立](#191-连接建立)
  - [19.2 消息格式](#192-消息格式)
  - [19.3 心跳与重连](#193-心跳与重连)
- [20. 完整使用示例](#20-完整使用示例)
  - [20.1 curl 示例集](#201-curl-示例集)
  - [20.2 Python 示例集](#202-python-示例集)
  - [20.3 JavaScript 示例集](#203-javascript-示例集)
- [21. 错误处理与重试策略](#21-错误处理与重试策略)
  - [21.1 错误响应格式](#211-错误响应格式)
  - [21.2 错误码分类](#212-错误码分类)
  - [21.3 重试策略](#213-重试策略)
  - [21.4 幂等性](#214-幂等性)
- [22. SDK 使用与客户端封装](#22-sdk-使用与客户端封装)
  - [22.1 Python SDK](#221-python-sdk)
  - [22.2 JavaScript SDK](#222-javascript-sdk)
  - [22.3 自定义客户端封装](#223-自定义客户端封装)
- [23. API 版本管理](#23-api-版本管理)
  - [23.1 版本策略](#231-版本策略)
  - [23.2 向后兼容](#232-向后兼容)
  - [23.3 废弃流程](#233-废弃流程)
- [24. 最佳实践](#24-最佳实践)
  - [24.1 会话生命周期管理](#241-会话生命周期管理)
  - [24.2 流式响应消费](#242-流式响应消费)
  - [24.3 错误恢复](#243-错误恢复)
  - [24.4 性能调优](#244-性能调优)
- [25. 附录](#25-附录)
  - [25.1 状态码速查](#251-状态码速查)
  - [25.2 错误码速查](#252-错误码速查)
  - [25.3 事件类型速查](#253-事件类型速查)
  - [25.4 变更日志](#254-变更日志)

---

## 1. 教程概述

### 1.1 文档目标

本教程系统性地介绍 ThesisMiner v8.0 的全部 HTTP API、SSE 流式接口与 WebSocket 通道。读者在阅读完本教程后，应当能够：

1. 独立完成 ThesisMiner 后端的接入与集成；
2. 熟练使用会话、对话、消息、Agent、引用、缓存、谱系、生成、预算、配置等全部接口；
3. 正确处理流式响应与 WebSocket 长连接，构建低延迟的前端体验；
4. 在生产环境中实施错误处理、重试、幂等性、限流退避等可靠性策略；
5. 基于 SDK 或自定义客户端封装，构建可维护的应用层代码。

本教程不涉及前端 UI 实现细节，也不涉及模型训练与微调。相关内容请分别参阅 `developer_guide.md` 与 `model_configuration_guide.md`。

### 1.2 读者画像

| 读者类型 | 推荐章节 | 阅读深度 |
|---------|---------|---------|
| 后端集成工程师 | 第 2-17 章、第 21 章 | 全量精读 |
| 前端集成工程师 | 第 6-19 章、第 22 章 | 全量精读 |
| 第三方接入方 | 第 2-5 章、第 20 章、第 23 章 | 选择性精读 |
| 运维与 SRE | 第 4 章、第 11 章、第 16 章、第 21 章 | 选择性精读 |
| 技术评估人员 | 第 1-2 章、第 25 章 | 通读 |

### 1.3 阅读路径建议

```
┌─────────────────────────────────────────────────────────────┐
│  入门路径：1 → 2 → 3 → 6 → 7 → 8 → 18 → 20                 │
│  进阶路径：4 → 5 → 9 → 10 → 11 → 12 → 13 → 14 → 15 → 16    │
│  高级路径：17 → 19 → 21 → 22 → 23 → 24                     │
└─────────────────────────────────────────────────────────────┘
```

### 1.4 术语表

| 术语 | 英文 | 释义 |
|------|------|------|
| 会话 | Session | 一次完整的论题探索过程，包含多轮对话 |
| 对话 | Conversation | 会话内的一次主题讨论，包含多条消息 |
| 消息 | Message | 对话中的一条用户输入或 Agent 输出 |
| Agent | Agent | 子智能体，如 Orchestrator/Searcher/Reasoner/Critic/Mentor/Writer |
| 引用 | Citation | Agent 输出中标注的文献来源 |
| 谱系 | Lineage | 论题从创意到成稿的演化关系图 |
| 缓存 | Cache | DeepSeek Prompt 缓存，用于降低重复请求成本 |
| 预算 | Budget | 单次会话的 Token 与费用上限 |
| 五阶段 | Five Stages | info_confirm→creativity→validation→generation→deep_assist |
| DST | Dialogue State Tracker | 对话状态跟踪器，用于上下文压缩 |
| 账本 | Ledger | 透明预算账本，记录每次 LLM 调用的成本 |

---

## 2. API 总览

### 2.1 架构定位

ThesisMiner v8.0 的 API 层位于 FastAPI 应用之上，向下对接 SQLite 持久化层与多 Agent 编排层，向上服务于前端 SPA 与第三方集成方。整体架构如下：

```
┌──────────────────────────────────────────────────────────────┐
│                     前端 SPA / 第三方客户端                    │
└────────────────────────┬─────────────────────────────────────┘
                         │  HTTP / SSE / WebSocket
┌────────────────────────▼─────────────────────────────────────┐
│                    FastAPI 路由层（API 层）                    │
│  sessions │ conversations │ citations │ budgets │ lineage    │
│  creativity │ proposals │ constraints │ config │ cache-stats │
└────────────────────────┬─────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────┐
│                    业务编排层（多 Agent）                      │
│  Orchestrator → Searcher / Reasoner / Critic / Mentor / Writer│
└────────────────────────┬─────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────┐
│  AI 代理层（ai_proxy）  │  缓存层（prompt_cache + cache_monitor）│
└────────────────────────┬─────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────┐
│  外部 LLM 提供商（OpenAI / DeepSeek / Anthropic / Qwen ...）  │
└──────────────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────┐
│            持久化层（SQLite + WAL，data/thesis_miner.db）      │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 端点清单

下表列出 v8.0 全部公开端点。所有端点默认监听 `127.0.0.1:8000`，可通过环境变量 `HOST`/`PORT` 调整。

| 模块 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 会话 | POST | `/api/sessions` | 创建会话 |
| 会话 | GET | `/api/sessions` | 查询会话列表 |
| 会话 | GET | `/api/sessions/{session_id}` | 获取会话详情 |
| 会话 | PATCH | `/api/sessions/{session_id}` | 更新会话状态 |
| 会话 | DELETE | `/api/sessions/{session_id}` | 删除会话 |
| 对话 | POST | `/api/sessions/{session_id}/conversations` | 创建对话 |
| 对话 | GET | `/api/sessions/{session_id}/conversations` | 查询对话列表 |
| 对话 | GET | `/api/sessions/{session_id}/conversations/{conv_id}` | 获取对话详情 |
| 对话 | DELETE | `/api/sessions/{session_id}/conversations/{conv_id}` | 删除对话 |
| 消息 | POST | `/api/sessions/{session_id}/conversations/{conv_id}/messages` | 发送消息 |
| 消息 | GET | `/api/sessions/{session_id}/conversations/{conv_id}/messages` | 查询消息历史 |
| 消息 | GET | `/api/messages/{message_id}` | 获取消息详情 |
| 引用 | GET | `/api/messages/{message_id}/citations` | 查询消息引用 |
| 缓存 | GET | `/api/cache-stats` | 查询缓存命中率 |
| 缓存 | DELETE | `/api/cache-stats` | 重置缓存统计 |
| 谱系 | GET | `/api/lineage/{session_id}` | 查询谱系图 |
| 谱系 | GET | `/api/lineage/{session_id}/nodes/{node_id}` | 查询节点详情 |
| 谱系 | GET | `/api/lineage/{session_id}/export` | 导出谱系 |
| 生成 | POST | `/api/proposals/generate` | 触发论题生成 |
| 生成 | GET | `/api/proposals/{proposal_id}` | 查询生成状态 |
| 生成 | DELETE | `/api/proposals/{proposal_id}` | 取消生成 |
| 创意 | POST | `/api/creativity/spark` | 触发创意 |
| 创意 | GET | `/api/creativity/{spark_id}` | 查询创意结果 |
| 约束 | POST | `/api/constraints/validate` | 触发约束校验 |
| 约束 | GET | `/api/constraints/{validation_id}` | 查询校验结果 |
| 预算 | GET | `/api/budgets/{session_id}` | 查询预算账本 |
| 预算 | POST | `/api/budgets/estimate` | 预算估算 |
| 配置 | GET | `/api/config` | 查询配置 |
| 配置 | PATCH | `/api/config` | 更新配置 |
| 配置 | GET | `/api/config/models` | 查询模型列表 |

### 2.3 请求/响应约定

**请求约定**：

- 除 GET/DELETE 外，所有写操作均使用 JSON 请求体，`Content-Type: application/json`；
- 路径参数使用花括号占位，如 `/api/sessions/{session_id}`；
- 查询参数使用小写下划线命名，如 `?limit=20&offset=0`；
- 时间字段统一使用 ISO 8601 UTC 字符串，如 `2026-06-20T08:30:00Z`。

**响应约定**：

- 成功响应：HTTP 2xx，响应体为业务数据 JSON；
- 失败响应：HTTP 4xx/5xx，响应体为标准错误结构（详见第 21 章）；
- 列表响应统一包含 `count`/`limit`/`offset` 字段；
- 详情响应包含 `id` 与 `created_at`/`updated_at` 时间戳。

**统一响应包装**：

部分端点使用 `ApiResponse` 包装结构：

```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```

失败时：

```json
{
  "success": false,
  "data": null,
  "error": "会话不存在"
}
```

### 2.4 内容类型与编码

- 请求体与响应体统一使用 UTF-8 编码的 JSON；
- 文件导出端点返回 `application/octet-stream` 或 `text/markdown`；
- SSE 流返回 `text/event-stream`；
- WebSocket 通道使用文本帧传输 JSON。

---

## 3. 认证与授权

### 3.1 本地部署模式

ThesisMiner 默认以本地单用户模式部署，监听 `127.0.0.1:8000`，不强制鉴权。该模式适用于：

- 个人研究者在本地工作站使用；
- 内网开发环境调试；
- 教学演示场景。

在该模式下，所有端点可直接访问，无需携带任何凭证。但出于安全考虑，建议：

1. 不要将服务暴露到公网；
2. 在共享主机上部署时启用反向代理鉴权；
3. 定期备份 `data/thesis_miner.db`。

### 3.2 API Key 模式

当需要将 ThesisMiner 暴露到内网或公网时，可通过环境变量启用 API Key 鉴权：

```bash
# .env
THESISMINER_API_KEY=sk-tm-xxxxxxxxxxxxxxxxxxxx
THESISMINER_API_KEY_ENABLED=true
```

启用后，所有请求必须在 `Authorization` 头中携带 API Key：

```
Authorization: Bearer sk-tm-xxxxxxxxxxxxxxxxxxxx
```

服务端校验逻辑：

```python
def verify_api_key(authorization: str = Header(None)) -> None:
    """校验 API Key。"""
    if not settings.api_key_enabled:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少有效的 Authorization 头")
    token = authorization.removeprefix("Bearer ").strip()
    if token != settings.api_key:
        raise HTTPException(status_code=401, detail="API Key 无效")
```

校验失败返回：

```json
HTTP/1.1 401 Unauthorized
{
  "success": false,
  "error": "API Key 无效",
  "code": "AUTH_INVALID_KEY"
}
```

### 3.3 多用户隔离

v8.0 的多用户隔离通过 `owner` 字段实现。每个会话、对话、消息在创建时绑定 `owner` 标识，查询时自动按 `owner` 过滤。第三方接入方应在请求头中携带：

```
X-Owner-Id: user-12345
```

服务端将该值注入到所有后续查询的 WHERE 子句中，确保数据隔离。

```
┌────────────┐     X-Owner-Id: user-A     ┌──────────────┐
│  Client A  │ ──────────────────────────▶ │              │
└────────────┘                              │   FastAPI    │
┌────────────┐     X-Owner-Id: user-B     │              │
│  Client B  │ ──────────────────────────▶ │  按 owner 过滤│
└────────────┘                              └──────────────┘
```

---

## 4. 速率限制

### 4.1 限制策略

ThesisMiner v8.0 在应用层实施两级速率限制：

| 层级 | 维度 | 默认上限 | 窗口 |
|------|------|---------|------|
| 全局 | IP | 600 请求 | 60 秒 |
| 单会话 | session_id | 60 请求 | 60 秒 |
| 生成类 | session_id | 5 请求 | 60 秒 |

生成类端点（`POST /api/proposals/generate`、`POST /api/creativity/spark`、`POST /api/constraints/validate`）因涉及昂贵的 LLM 调用，单独施加更严格的限制。

速率限制配置可通过环境变量调整：

```bash
RATE_LIMIT_GLOBAL=600/60
RATE_LIMIT_SESSION=60/60
RATE_LIMIT_GENERATION=5/60
```

### 4.2 限流响应头

每个响应都携带以下限流相关头：

```
X-RateLimit-Limit: 600
X-RateLimit-Remaining: 598
X-RateLimit-Reset: 1718870460
```

当触发限流时，返回 HTTP 429：

```json
HTTP/1.1 429 Too Many Requests
Retry-After: 42
{
  "success": false,
  "error": "请求过于频繁，请稍后重试",
  "code": "RATE_LIMIT_EXCEEDED",
  "retry_after": 42
}
```

### 4.3 客户端退避策略

推荐的客户端退避策略为指数退避加抖动：

```python
import random
import time

def request_with_backoff(client, url, max_retries=5):
    """带指数退避的请求封装。"""
    for attempt in range(max_retries):
        response = client.get(url)
        if response.status_code != 429:
            return response
        retry_after = int(response.headers.get("Retry-After", 2 ** attempt))
        jitter = random.uniform(0, 0.5)
        time.sleep(retry_after + jitter)
    raise Exception(f"超过最大重试次数 {max_retries}")
```

退避曲线示意：

```
延迟(秒)
  │
8 │                              *
  │                     *
4 │            *
  │   *
2 │*
  └───────────────────────────────── 尝试次数
    1    2    3    4    5
```

---

## 5. 分页、过滤与排序

### 5.1 分页参数

所有列表端点支持以下分页参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `limit` | int | 20 | 每页条数，最大 100 |
| `offset` | int | 0 | 偏移量 |

请求示例：

```
GET /api/sessions?limit=10&offset=20
```

响应包含分页元信息：

```json
{
  "sessions": [ ... ],
  "count": 10,
  "limit": 10,
  "offset": 20,
  "total": 156
}
```

### 5.2 过滤参数

不同端点支持不同的过滤参数：

| 端点 | 过滤参数 | 示例 |
|------|---------|------|
| `/api/sessions` | `status`, `degree`, `discipline` | `?status=active&degree=master` |
| `/api/sessions/{sid}/conversations` | `stage`, `agent` | `?stage=creativity` |
| `/api/messages/{mid}/citations` | `type`, `source` | `?type=journal` |
| `/api/budgets/{sid}` | `agent`, `model` | `?agent=orchestrator` |

### 5.3 排序参数

排序通过 `sort` 参数指定，格式为 `field:order`：

```
GET /api/sessions?sort=created_at:desc
GET /api/budgets/{sid}?sort=cost:asc
```

支持多字段排序：

```
GET /api/sessions?sort=degree:asc,created_at:desc
```

### 5.4 游标分页

对于消息历史等可能产生大量数据的端点，v8.0 支持游标分页：

```
GET /api/sessions/{sid}/conversations/{cid}/messages?cursor=eyJpZCI6Im1zZ18xMjMifQ&limit=50
```

响应：

```json
{
  "messages": [ ... ],
  "next_cursor": "eyJpZCI6Im1zZ18yMDAifQ",
  "has_more": true
}
```

游标为 Base64 编码的 JSON，包含上一页最后一条记录的 `id` 与排序字段值。客户端应将 `next_cursor` 原样回传，不要解析或修改。

---

## 6. 会话管理 API

会话（Session）是 ThesisMiner 的顶层资源，承载一次完整的论题探索过程。每个会话绑定学位、学科、研究背景等元信息，并作为对话、消息、谱系、预算等子资源的容器。

### 6.1 创建会话

**请求**：

```
POST /api/sessions
Content-Type: application/json
```

**请求体**：

```json
{
  "degree": "master",
  "discipline": "computer_science",
  "research_background": "本人研究方向为图神经网络，希望探索其在药物分子设计中的应用。",
  "initial_topic": "基于图神经网络的药物分子性质预测",
  "constraints": {
    "max_years": 1,
    "literature_count": 30,
    "must_include_keywords": ["GNN", "分子图", "性质预测"]
  },
  "metadata": {
    "source": "web-ui",
    "user_agent": "Mozilla/5.0"
  }
}
```

**字段说明**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `degree` | string | 是 | 学位类型，`master`/`doctor` |
| `discipline` | string | 是 | 学科类型，见枚举表 |
| `research_background` | string | 否 | 研究背景描述 |
| `initial_topic` | string | 否 | 初始论题 |
| `constraints` | object | 否 | 硬约束 |
| `metadata` | object | 否 | 自定义元数据 |

**响应**：

```json
HTTP/1.1 200 OK
{
  "success": true,
  "data": {
    "id": "ses_20260620_a1b2c3d4",
    "degree": "master",
    "discipline": "computer_science",
    "research_background": "本人研究方向为图神经网络...",
    "initial_topic": "基于图神经网络的药物分子性质预测",
    "status": "active",
    "stage": "info_confirm",
    "created_at": "2026-06-20T08:30:00Z",
    "updated_at": "2026-06-20T08:30:00Z",
    "dialog_rounds": 0
  }
}
```

**错误码**：

| HTTP | code | 说明 |
|------|------|------|
| 400 | `VALIDATION_ERROR` | 字段校验失败 |
| 422 | `UNPROCESSABLE_ENTITY` | Pydantic 校验失败 |

**学位枚举**：

- `master`：硕士
- `doctor`：博士

**学科枚举（部分）**：

- `computer_science`、`software_engineering`、`artificial_intelligence`
- `mathematics`、`physics`、`chemistry`
- `biology`、`medicine`、`pharmacy`
- `economics`、`management`、`finance`
- `literature`、`history`、`philosophy`
- `education`、`psychology`、`sociology`

### 6.2 查询会话列表

**请求**：

```
GET /api/sessions?limit=20&offset=0&status=active&degree=master
```

**查询参数**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `limit` | int | 20 | 每页条数 |
| `offset` | int | 0 | 偏移量 |
| `status` | string | - | 过滤状态 |
| `degree` | string | - | 过滤学位 |
| `discipline` | string | - | 过滤学科 |
| `sort` | string | `created_at:desc` | 排序字段 |

**响应**：

```json
{
  "sessions": [
    {
      "id": "ses_20260620_a1b2c3d4",
      "degree": "master",
      "discipline": "computer_science",
      "initial_topic": "基于图神经网络的药物分子性质预测",
      "status": "active",
      "stage": "creativity",
      "created_at": "2026-06-20T08:30:00Z",
      "updated_at": "2026-06-20T09:15:00Z",
      "dialog_rounds": 3
    }
  ],
  "count": 1,
  "limit": 20,
  "offset": 0,
  "total": 1
}
```

### 6.3 获取会话详情

**请求**：

```
GET /api/sessions/{session_id}
```

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `session_id` | string | 会话 ID |

**响应**：

```json
{
  "id": "ses_20260620_a1b2c3d4",
  "degree": "master",
  "discipline": "computer_science",
  "research_background": "本人研究方向为图神经网络...",
  "initial_topic": "基于图神经网络的药物分子性质预测",
  "status": "active",
  "stage": "creativity",
  "constraints": {
    "max_years": 1,
    "literature_count": 30,
    "must_include_keywords": ["GNN", "分子图", "性质预测"]
  },
  "metadata": {
    "source": "web-ui"
  },
  "created_at": "2026-06-20T08:30:00Z",
  "updated_at": "2026-06-20T09:15:00Z",
  "dialog_rounds": 3
}
```

**错误码**：

| HTTP | code | 说明 |
|------|------|------|
| 404 | `SESSION_NOT_FOUND` | 会话不存在 |

### 6.4 更新会话状态

**请求**：

```
PATCH /api/sessions/{session_id}
Content-Type: application/json
```

**请求体**：

```json
{
  "status": "archived"
}
```

**可选状态值**：

- `active`：活跃
- `paused`：暂停
- `archived`：归档
- `deleted`：软删除

**响应**：

```json
{
  "success": true,
  "data": {
    "id": "ses_20260620_a1b2c3d4",
    "status": "archived",
    "updated_at": "2026-06-20T10:00:00Z"
  }
}
```

### 6.5 删除会话

**请求**：

```
DELETE /api/sessions/{session_id}
```

**响应**：

```json
HTTP/1.1 200 OK
{
  "success": true,
  "data": null,
  "error": null
}
```

删除会话将级联删除其下所有对话、消息、引用、谱系节点与预算记录。该操作不可逆，建议在生产环境先调用 `PATCH` 将状态置为 `archived`，再定期清理。

---

## 7. 对话管理 API

对话（Conversation）是会话内的次级资源，用于组织同一主题下的多轮消息交互。一个会话可包含多个对话，每个对话独立维护上下文。

### 7.1 创建对话

**请求**：

```
POST /api/sessions/{session_id}/conversations
Content-Type: application/json
```

**请求体**：

```json
{
  "title": "探索 GNN 在分子性质预测中的可行性",
  "stage": "creativity",
  "parent_conversation_id": "conv_20260620_x1y2z3",
  "metadata": {
    "trigger": "user-click"
  }
}
```

**字段说明**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `title` | string | 否 | 对话标题 |
| `stage` | string | 否 | 五阶段之一 |
| `parent_conversation_id` | string | 否 | 父对话 ID，用于谱系追溯 |
| `metadata` | object | 否 | 自定义元数据 |

**响应**：

```json
{
  "success": true,
  "data": {
    "id": "conv_20260620_a1b2c3d4",
    "session_id": "ses_20260620_a1b2c3d4",
    "title": "探索 GNN 在分子性质预测中的可行性",
    "stage": "creativity",
    "parent_conversation_id": "conv_20260620_x1y2z3",
    "status": "active",
    "created_at": "2026-06-20T09:00:00Z",
    "updated_at": "2026-06-20T09:00:00Z",
    "message_count": 0
  }
}
```

### 7.2 查询会话下的对话列表

**请求**：

```
GET /api/sessions/{session_id}/conversations?stage=creativity&limit=20
```

**响应**：

```json
{
  "conversations": [
    {
      "id": "conv_20260620_a1b2c3d4",
      "title": "探索 GNN 在分子性质预测中的可行性",
      "stage": "creativity",
      "status": "active",
      "created_at": "2026-06-20T09:00:00Z",
      "message_count": 4
    }
  ],
  "count": 1,
  "limit": 20,
  "offset": 0
}
```

### 7.3 获取对话详情

**请求**：

```
GET /api/sessions/{session_id}/conversations/{conversation_id}
```

**响应**：

```json
{
  "id": "conv_20260620_a1b2c3d4",
  "session_id": "ses_20260620_a1b2c3d4",
  "title": "探索 GNN 在分子性质预测中的可行性",
  "stage": "creativity",
  "parent_conversation_id": "conv_20260620_x1y2z3",
  "status": "active",
  "metadata": {
    "trigger": "user-click"
  },
  "created_at": "2026-06-20T09:00:00Z",
  "updated_at": "2026-06-20T09:30:00Z",
  "message_count": 4,
  "last_message_preview": "建议从消息传递机制入手..."
}
```

### 7.4 删除对话

**请求**：

```
DELETE /api/sessions/{session_id}/conversations/{conversation_id}
```

**响应**：

```json
{
  "success": true,
  "data": null,
  "error": null
}
```

删除对话会级联删除其下所有消息与引用，但不会影响谱系图中已生成的节点。

---

## 8. 消息管理 API

消息（Message）是对话中的最小交互单元，分为用户消息与 Agent 消息。Agent 消息可能携带引用、思考过程、工具调用等附加信息。

### 8.1 发送消息

**请求**：

```
POST /api/sessions/{session_id}/conversations/{conversation_id}/messages
Content-Type: application/json
```

**请求体（同步模式）**：

```json
{
  "role": "user",
  "content": "请帮我分析 GNN 在分子性质预测中的优势与挑战。",
  "stream": false,
  "agent_hint": "reasoner",
  "metadata": {
    "client_message_id": "client-uuid-1234"
  }
}
```

**请求体（流式模式）**：

```json
{
  "role": "user",
  "content": "请帮我分析 GNN 在分子性质预测中的优势与挑战。",
  "stream": true,
  "agent_hint": "reasoner"
}
```

**字段说明**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `role` | string | 是 | `user`/`assistant`/`system` |
| `content` | string | 是 | 消息内容 |
| `stream` | bool | 否 | 是否流式返回，默认 false |
| `agent_hint` | string | 否 | 指定 Agent，如 `orchestrator`/`reasoner` |
| `metadata` | object | 否 | 元数据，可携带 `client_message_id` 用于幂等 |

**同步响应**：

```json
{
  "success": true,
  "data": {
    "user_message": {
      "id": "msg_20260620_u1",
      "role": "user",
      "content": "请帮我分析 GNN 在分子性质预测中的优势与挑战。",
      "created_at": "2026-06-20T09:30:00Z"
    },
    "assistant_message": {
      "id": "msg_20260620_a1",
      "role": "assistant",
      "agent": "reasoner",
      "content": "GNN 在分子性质预测中的优势主要体现在...",
      "citations": [
        {
          "id": "cit_1",
          "text": "消息传递神经网络（MPNN）",
          "source": "Gilmer et al., 2017"
        }
      ],
      "usage": {
        "prompt_tokens": 1200,
        "completion_tokens": 450,
        "total_tokens": 1650
      },
      "cost_cny": 0.0042,
      "created_at": "2026-06-20T09:30:05Z"
    }
  }
}
```

**流式响应**：详见第 18 章 SSE 流式响应。

### 8.2 查询消息历史

**请求**：

```
GET /api/sessions/{session_id}/conversations/{conversation_id}/messages?limit=50&cursor=eyJpZCI6Im1zZ18xMjMifQ
```

**响应**：

```json
{
  "messages": [
    {
      "id": "msg_20260620_u1",
      "role": "user",
      "content": "请帮我分析 GNN 在分子性质预测中的优势与挑战。",
      "created_at": "2026-06-20T09:30:00Z"
    },
    {
      "id": "msg_20260620_a1",
      "role": "assistant",
      "agent": "reasoner",
      "content": "GNN 在分子性质预测中的优势主要体现在...",
      "citations_count": 3,
      "usage": {
        "prompt_tokens": 1200,
        "completion_tokens": 450,
        "total_tokens": 1650
      },
      "cost_cny": 0.0042,
      "created_at": "2026-06-20T09:30:05Z"
    }
  ],
  "count": 2,
  "limit": 50,
  "next_cursor": null,
  "has_more": false
}
```

### 8.3 获取消息详情

**请求**：

```
GET /api/messages/{message_id}
```

**响应**：

```json
{
  "id": "msg_20260620_a1",
  "conversation_id": "conv_20260620_a1b2c3d4",
  "session_id": "ses_20260620_a1b2c3d4",
  "role": "assistant",
  "agent": "reasoner",
  "model": "deepseek-r2",
  "content": "GNN 在分子性质预测中的优势主要体现在...",
  "thinking": "用户询问 GNN 的优势与挑战，我需要从...",
  "tool_calls": [
    {
      "name": "literature_search",
      "arguments": {"query": "GNN molecular property prediction"},
      "result_summary": "找到 12 篇相关文献"
    }
  ],
  "citations_count": 3,
  "usage": {
    "prompt_tokens": 1200,
    "completion_tokens": 450,
    "total_tokens": 1650,
    "cached_tokens": 980
  },
  "cost_cny": 0.0042,
  "latency_ms": 3200,
  "created_at": "2026-06-20T09:30:05Z"
}
```

### 8.4 消息引用查询

详见第 10 章 引用管理 API。

---

## 9. Agent 管理 API

ThesisMiner v8.0 采用多 Agent 架构，包含 1 个 Orchestrator 与 5 个子 Agent。本组 API 用于查询 Agent 注册表与路由配置。

### 9.1 查询 Agent 注册表

**请求**：

```
GET /api/agents
```

**响应**：

```json
{
  "agents": [
    {
      "id": "orchestrator",
      "name": "Orchestrator",
      "role": "编排者",
      "description": "负责任务分解、Agent 调度与结果汇总",
      "default_model": "claude-sonnet-4.5",
      "capabilities": ["planning", "routing", "summarization"],
      "is_sub_agent": false
    },
    {
      "id": "searcher",
      "name": "Searcher",
      "role": "检索者",
      "description": "负责文献检索与信息收集",
      "default_model": "deepseek-v3.2",
      "capabilities": ["web_search", "literature_retrieval"],
      "is_sub_agent": true
    },
    {
      "id": "reasoner",
      "name": "Reasoner",
      "role": "推理者",
      "description": "负责深度推理与可行性分析",
      "default_model": "deepseek-r2",
      "capabilities": ["reasoning", "thinking", "analysis"],
      "is_sub_agent": true
    },
    {
      "id": "critic",
      "name": "Critic",
      "role": "评审者",
      "description": "负责硬约束校验与风险评估",
      "default_model": "gpt-4.1",
      "capabilities": ["validation", "risk_assessment"],
      "is_sub_agent": true
    },
    {
      "id": "mentor",
      "name": "Mentor",
      "role": "导师",
      "description": "负责学术指导与方法论建议",
      "default_model": "gpt-4.1",
      "capabilities": ["mentoring", "methodology"],
      "is_sub_agent": true
    },
    {
      "id": "writer",
      "name": "Writer",
      "role": "撰写者",
      "description": "负责论题报告与开题文档生成",
      "default_model": "claude-opus-4.5",
      "capabilities": ["writing", "formatting", "citation"],
      "is_sub_agent": true
    }
  ],
  "count": 6
}
```

### 9.2 查询 Agent 路由

**请求**：

```
GET /api/agents/routing
```

**响应**：

```json
{
  "routing": {
    "orchestrator": "claude-sonnet-4.5",
    "reasoner": "deepseek-r2",
    "mentor": "gpt-4.1",
    "inspire": "qwen3-max",
    "report": "claude-opus-4.5",
    "search": "deepseek-v3.2"
  },
  "fallback": {
    "orchestrator": "gpt-4.1",
    "reasoner": "claude-sonnet-4.5",
    "mentor": "glm-4.6",
    "inspire": "gpt-4.1-mini",
    "report": "claude-sonnet-4.5",
    "search": "doubao-1.5-pro"
  }
}
```

### 9.3 切换 Agent 模型

**请求**：

```
PATCH /api/agents/{agent_id}/model
Content-Type: application/json
```

**请求体**：

```json
{
  "model_id": "gpt-4.1",
  "scope": "session",
  "session_id": "ses_20260620_a1b2c3d4"
}
```

**响应**：

```json
{
  "success": true,
  "data": {
    "agent_id": "reasoner",
    "model_id": "gpt-4.1",
    "scope": "session",
    "session_id": "ses_20260620_a1b2c3d4",
    "updated_at": "2026-06-20T10:00:00Z"
  }
}
```

`scope` 可选值：

- `global`：全局生效
- `session`：仅对指定会话生效
- `conversation`：仅对指定对话生效（需额外提供 `conversation_id`）

---

## 10. 引用管理 API

引用（Citation）是 Agent 输出中标注的文献来源，用于支持论点的可信度。每条引用关联到消息中的具体文本片段。

### 10.1 查询消息引用

**请求**：

```
GET /api/messages/{message_id}/citations
```

**响应**：

```json
{
  "message_id": "msg_20260620_a1",
  "citations": [
    {
      "id": "cit_1",
      "text": "消息传递神经网络（MPNN）",
      "start_offset": 12,
      "end_offset": 25,
      "source": {
        "type": "journal",
        "title": "Neural Message Passing for Quantum Chemistry",
        "authors": ["Gilmer, J.", "Schoenholz, S.S.", "Riley, P.F."],
        "venue": "ICML 2017",
        "year": 2017,
        "doi": "10.48550/arXiv.1704.01212",
        "url": "https://arxiv.org/abs/1704.01212"
      },
      "confidence": 0.95
    },
    {
      "id": "cit_2",
      "text": "图同构网络（GIN）",
      "start_offset": 45,
      "end_offset": 54,
      "source": {
        "type": "journal",
        "title": "How Powerful are Graph Neural Networks?",
        "authors": ["Xu, K.", "Hu, W.", "Leskovec, J."],
        "venue": "ICLR 2019",
        "year": 2019,
        "doi": "10.48550/arXiv.1810.00826",
        "url": "https://arxiv.org/abs/1810.00826"
      },
      "confidence": 0.92
    }
  ],
  "count": 2
}
```

### 10.2 引用解析

**请求**：

```
POST /api/citations/parse
Content-Type: application/json
```

**请求体**：

```json
{
  "text": "近年来，GNN 在分子性质预测领域取得了显著进展 [1][2]。",
  "known_references": [
    {"id": "1", "title": "MPNN", "doi": "10.48550/arXiv.1704.01212"},
    {"id": "2", "title": "GIN", "doi": "10.48550/arXiv.1810.00826"}
  ]
}
```

**响应**：

```json
{
  "success": true,
  "data": {
    "parsed_citations": [
      {
        "marker": "[1]",
        "start_offset": 28,
        "end_offset": 31,
        "reference_id": "1",
        "resolved": true
      },
      {
        "marker": "[2]",
        "start_offset": 31,
        "end_offset": 34,
        "reference_id": "2",
        "resolved": true
      }
    ],
    "unresolved_markers": []
  }
}
```

### 10.3 引用导出

**请求**：

```
GET /api/messages/{message_id}/citations/export?format=bibtex
```

**支持的格式**：

- `bibtex`：BibTeX 格式
- `ris`：RIS 格式
- `json`：CSL-JSON 格式
- `apa`：APA 引用格式

**响应（bibtex）**：

```
HTTP/1.1 200 OK
Content-Type: application/x-bibtex

@inproceedings{gilmer2017mpnn,
  title={Neural Message Passing for Quantum Chemistry},
  author={Gilmer, Justin and Schoenholz, Samuel S. and Riley, Patrick F. and Vinyals, Oriol and Dahl, George E.},
  booktitle={ICML},
  year={2017}
}

@inproceedings{xu2019gin,
  title={How Powerful are Graph Neural Networks?},
  author={Xu, Keyulu and Hu, Weihua and Leskovec, Jure and Jegelka, Stefanie},
  booktitle={ICLR},
  year={2019}
}
```

---

## 11. 缓存统计 API

ThesisMiner v8.0 利用 DeepSeek 的 Prompt 缓存能力，将三段式前缀（系统提示+Agent 角色定义+会话上下文）缓存到服务端，命中率可达 95% 以上。本组 API 用于监控缓存效果。

### 11.1 查询缓存命中率

**请求**：

```
GET /api/cache-stats?session_id=ses_20260620_a1b2c3d4
```

**查询参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `session_id` | string | 可选，按会话过滤 |
| `start_time` | string | 可选，ISO 8601 起始时间 |
| `end_time` | string | 可选，ISO 8601 结束时间 |
| `group_by` | string | 可选，`agent`/`model`/`hour` |

**响应**：

```json
{
  "summary": {
    "total_requests": 1240,
    "cache_hits": 1188,
    "cache_misses": 52,
    "hit_rate": 0.9581,
    "saved_tokens": 1425600,
    "saved_cost_cny": 1.4256
  },
  "by_agent": {
    "orchestrator": {
      "total_requests": 320,
      "cache_hits": 312,
      "hit_rate": 0.9750
    },
    "reasoner": {
      "total_requests": 280,
      "cache_hits": 268,
      "hit_rate": 0.9571
    },
    "searcher": {
      "total_requests": 410,
      "cache_hits": 392,
      "hit_rate": 0.9561
    },
    "writer": {
      "total_requests": 230,
      "cache_hits": 216,
      "hit_rate": 0.9391
    }
  },
  "by_hour": [
    {"hour": "2026-06-20T08:00:00Z", "hit_rate": 0.94},
    {"hour": "2026-06-20T09:00:00Z", "hit_rate": 0.96},
    {"hour": "2026-06-20T10:00:00Z", "hit_rate": 0.97}
  ]
}
```

### 11.2 重置缓存统计

**请求**：

```
DELETE /api/cache-stats
```

**响应**：

```json
{
  "success": true,
  "data": {
    "reset_at": "2026-06-20T10:00:00Z"
  }
}
```

该操作仅清除统计计数器，不影响 DeepSeek 服务端的实际缓存内容。

### 11.3 缓存事件流

**请求**：

```
GET /api/cache-stats/stream
Accept: text/event-stream
```

**SSE 事件示例**：

```
event: cache_hit
data: {"session_id":"ses_20260620_a1b2c3d4","agent":"reasoner","saved_tokens":980,"timestamp":"2026-06-20T10:00:01Z"}

event: cache_miss
data: {"session_id":"ses_20260620_a1b2c3d4","agent":"reasoner","reason":"prefix_changed","timestamp":"2026-06-20T10:00:05Z"}

event: cache_hit
data: {"session_id":"ses_20260620_a1b2c3d4","agent":"searcher","saved_tokens":1200,"timestamp":"2026-06-20T10:00:10Z"}
```

---

## 12. 谱系管理 API

谱系（Lineage）记录论题从初始创意到最终成稿的完整演化路径，以有向无环图（DAG）形式存储。前端使用 D3.js v7 力导向图渲染。

### 12.1 查询谱系图

**请求**：

```
GET /api/lineage/{session_id}
```

**响应**：

```json
{
  "session_id": "ses_20260620_a1b2c3d4",
  "nodes": [
    {
      "id": "node_1",
      "type": "topic",
      "label": "基于图神经网络的药物分子性质预测",
      "stage": "info_confirm",
      "created_at": "2026-06-20T08:30:00Z",
      "metadata": {"degree": "master"}
    },
    {
      "id": "node_2",
      "type": "idea",
      "label": "MPNN 在分子图上的应用",
      "stage": "creativity",
      "created_at": "2026-06-20T09:00:00Z",
      "metadata": {"agent": "inspire", "score": 0.85}
    },
    {
      "id": "node_3",
      "type": "validated_topic",
      "label": "基于 MPNN 的分子溶解度预测",
      "stage": "validation",
      "created_at": "2026-06-20T09:30:00Z",
      "metadata": {"agent": "critic", "score": 0.92}
    },
    {
      "id": "node_4",
      "type": "proposal",
      "label": "开题报告 v1",
      "stage": "generation",
      "created_at": "2026-06-20T10:00:00Z",
      "metadata": {"agent": "writer"}
    }
  ],
  "edges": [
    {"source": "node_1", "target": "node_2", "type": "derived_from"},
    {"source": "node_2", "target": "node_3", "type": "validated_to"},
    {"source": "node_3", "target": "node_4", "type": "generated_to"}
  ],
  "stats": {
    "node_count": 4,
    "edge_count": 3,
    "depth": 4,
    "branches": 1
  }
}
```

**节点类型**：

- `topic`：初始论题
- `idea`：创意分支
- `validated_topic`：校验通过的论题
- `rejected_topic`：被否决的论题
- `proposal`：生成的开题报告
- `refinement`：迭代优化节点

**边类型**：

- `derived_from`：派生自
- `validated_to`：校验通过为
- `rejected_to`：被否决为
- `generated_to`：生成为
- `refined_to`：优化为

### 12.2 查询节点详情

**请求**：

```
GET /api/lineage/{session_id}/nodes/{node_id}
```

**响应**：

```json
{
  "id": "node_3",
  "session_id": "ses_20260620_a1b2c3d4",
  "type": "validated_topic",
  "label": "基于 MPNN 的分子溶解度预测",
  "stage": "validation",
  "content": "本论题探索消息传递神经网络（MPNN）在分子溶解度预测任务中的应用...",
  "parent_ids": ["node_2"],
  "child_ids": ["node_4"],
  "validation_result": {
    "passed": true,
    "score": 0.92,
    "checks": [
      {"name": "novelty", "passed": true, "score": 0.88},
      {"name": "feasibility", "passed": true, "score": 0.95},
      {"name": "literature_coverage", "passed": true, "score": 0.90}
    ]
  },
  "created_at": "2026-06-20T09:30:00Z",
  "created_by_agent": "critic"
}
```

### 12.3 查询边详情

**请求**：

```
GET /api/lineage/{session_id}/edges/{source_id}/{target_id}
```

**响应**：

```json
{
  "source": "node_2",
  "target": "node_3",
  "type": "validated_to",
  "session_id": "ses_20260620_a1b2c3d4",
  "metadata": {
    "validation_score": 0.92,
    "agent": "critic"
  },
  "created_at": "2026-06-20T09:30:00Z"
}
```

### 12.4 导出谱系

**请求**：

```
GET /api/lineage/{session_id}/export?format=json
```

**支持的格式**：

- `json`：原始 JSON
- `dot`：Graphviz DOT 格式
- `mermaid`：Mermaid 流程图格式
- `png`：PNG 图片（服务端渲染）

**响应（mermaid）**：

```
HTTP/1.1 200 OK
Content-Type: text/x-mermaid

graph TD
    node_1[基于图神经网络的药物分子性质预测]
    node_2[MPNN 在分子图上的应用]
    node_3[基于 MPNN 的分子溶解度预测]
    node_4[开题报告 v1]
    node_1 --> node_2
    node_2 --> node_3
    node_3 --> node_4
```

---

## 13. 论题生成 API

论题生成是 ThesisMiner 的核心能力，由 Orchestrator 协调多个子 Agent，经过五阶段闭环流程，最终输出开题报告。

### 13.1 触发生成

**请求**：

```
POST /api/proposals/generate
Content-Type: application/json
```

**请求体**：

```json
{
  "session_id": "ses_20260620_a1b2c3d4",
  "mode": "full_pipeline",
  "stream": true,
  "options": {
    "max_ideas": 5,
    "max_validated": 2,
    "literature_count": 30,
    "include_citations": true,
    "output_format": "markdown",
    "language": "zh-CN"
  },
  "callbacks": {
    "on_stage_change": "https://your-server.com/webhooks/stage",
    "on_complete": "https://your-server.com/webhooks/complete"
  }
}
```

**字段说明**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `session_id` | string | 是 | 会话 ID |
| `mode` | string | 否 | 生成模式，默认 `full_pipeline` |
| `stream` | bool | 否 | 是否流式返回 |
| `options` | object | 否 | 生成选项 |
| `callbacks` | object | 否 | Webhook 回调 |

**生成模式**：

- `full_pipeline`：完整五阶段流程
- `creativity_only`：仅执行创意阶段
- `validation_only`：仅执行校验阶段
- `generation_only`：仅执行报告生成
- `deep_assist`：深度辅助模式

**同步响应**：

```json
{
  "success": true,
  "data": {
    "proposal_id": "prop_20260620_a1b2c3d4",
    "session_id": "ses_20260620_a1b2c3d4",
    "status": "queued",
    "estimated_duration_seconds": 180,
    "stages": [
      "info_confirm",
      "creativity",
      "validation",
      "generation",
      "deep_assist"
    ],
    "created_at": "2026-06-20T10:00:00Z"
  }
}
```

**流式响应**：详见第 18 章。

### 13.2 查询生成状态

**请求**：

```
GET /api/proposals/{proposal_id}
```

**响应**：

```json
{
  "id": "prop_20260620_a1b2c3d4",
  "session_id": "ses_20260620_a1b2c3d4",
  "status": "running",
  "current_stage": "validation",
  "stage_progress": {
    "info_confirm": {"status": "completed", "duration_seconds": 12},
    "creativity": {"status": "completed", "duration_seconds": 45, "ideas_generated": 5},
    "validation": {"status": "running", "started_at": "2026-06-20T10:01:00Z"},
    "generation": {"status": "pending"},
    "deep_assist": {"status": "pending"}
  },
  "progress_percent": 60,
  "estimated_remaining_seconds": 72,
  "created_at": "2026-06-20T10:00:00Z",
  "updated_at": "2026-06-20T10:01:30Z"
}
```

**状态值**：

- `queued`：排队中
- `running`：运行中
- `paused`：已暂停
- `completed`：已完成
- `failed`：失败
- `cancelled`：已取消

### 13.3 取消生成

**请求**：

```
DELETE /api/proposals/{proposal_id}
```

**响应**：

```json
{
  "success": true,
  "data": {
    "proposal_id": "prop_20260620_a1b2c3d4",
    "status": "cancelled",
    "cancelled_at": "2026-06-20T10:02:00Z",
    "partial_result_available": true
  }
}
```

取消后，已完成阶段的中间结果仍可查询，但不会进入下一阶段。

---

## 14. 创意引擎 API

创意引擎（Creativity Engine）对应五阶段中的 `creativity` 阶段，由 Inspire Agent（默认 `qwen3-max`）驱动，生成多个候选论题方向。

### 14.1 触发创意

**请求**：

```
POST /api/creativity/spark
Content-Type: application/json
```

**请求体**：

```json
{
  "session_id": "ses_20260620_a1b2c3d4",
  "seed_topic": "基于图神经网络的药物分子性质预测",
  "dimensions": ["methodology", "application", "dataset", "evaluation"],
  "max_ideas": 5,
  "diversity_weight": 0.7,
  "stream": false
}
```

**字段说明**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `session_id` | string | 是 | 会话 ID |
| `seed_topic` | string | 否 | 种子论题 |
| `dimensions` | array | 否 | 创意维度 |
| `max_ideas` | int | 否 | 最大创意数，默认 5 |
| `diversity_weight` | float | 否 | 多样性权重 0-1 |
| `stream` | bool | 否 | 是否流式返回 |

**响应**：

```json
{
  "success": true,
  "data": {
    "spark_id": "spark_20260620_a1b2c3d4",
    "session_id": "ses_20260620_a1b2c3d4",
    "ideas": [
      {
        "id": "idea_1",
        "title": "基于 MPNN 的分子溶解度预测",
        "dimension": "application",
        "novelty_score": 0.85,
        "feasibility_score": 0.92,
        "description": "将消息传递神经网络应用于分子溶解度预测任务..."
      },
      {
        "id": "idea_2",
        "title": "基于 GIN 的分子毒性预测",
        "dimension": "application",
        "novelty_score": 0.78,
        "feasibility_score": 0.88,
        "description": "利用图同构网络进行分子毒性预测..."
      },
      {
        "id": "idea_3",
        "title": "对比学习增强的分子图表示",
        "dimension": "methodology",
        "novelty_score": 0.91,
        "feasibility_score": 0.75,
        "description": "通过对比学习提升分子图表征的判别能力..."
      }
    ],
    "diversity_score": 0.82,
    "total_tokens": 3200,
    "cost_cny": 0.031,
    "created_at": "2026-06-20T09:00:00Z"
  }
}
```

### 14.2 查询创意结果

**请求**：

```
GET /api/creativity/{spark_id}
```

**响应**：

```json
{
  "id": "spark_20260620_a1b2c3d4",
  "session_id": "ses_20260620_a1b2c3d4",
  "ideas": [ ... ],
  "diversity_score": 0.82,
  "agent": "inspire",
  "model": "qwen3-max",
  "usage": {
    "prompt_tokens": 1800,
    "completion_tokens": 1400,
    "total_tokens": 3200,
    "cached_tokens": 1200
  },
  "cost_cny": 0.031,
  "created_at": "2026-06-20T09:00:00Z"
}
```

---

## 15. 约束校验 API

约束校验（Constraints Validation）对应五阶段中的 `validation` 阶段，由 Critic Agent（默认 `gpt-4.1`）执行硬约束校验。

### 15.1 触发校验

**请求**：

```
POST /api/constraints/validate
Content-Type: application/json
```

**请求体**：

```json
{
  "session_id": "ses_20260620_a1b2c3d4",
  "topic": "基于 MPNN 的分子溶解度预测",
  "constraints": {
    "max_years": 1,
    "literature_count": 30,
    "must_include_keywords": ["GNN", "分子图", "溶解度"],
    "must_exclude_keywords": ["已废弃方法"],
    "data_availability": "public_dataset",
    "ethical_compliance": true
  },
  "stream": false
}
```

**响应**：

```json
{
  "success": true,
  "data": {
    "validation_id": "val_20260620_a1b2c3d4",
    "session_id": "ses_20260620_a1b2c3d4",
    "overall_passed": true,
    "overall_score": 0.92,
    "checks": [
      {
        "name": "novelty",
        "passed": true,
        "score": 0.88,
        "message": "论题在方法论上具有一定新意"
      },
      {
        "name": "feasibility",
        "passed": true,
        "score": 0.95,
        "message": "数据集公开可获取，技术路径可行"
      },
      {
        "name": "literature_coverage",
        "passed": true,
        "score": 0.90,
        "message": "相关文献数量充足，覆盖核心方法"
      },
      {
        "name": "keyword_inclusion",
        "passed": true,
        "score": 1.0,
        "message": "所有必需关键词均已包含"
      },
      {
        "name": "time_constraint",
        "passed": true,
        "score": 0.85,
        "message": "预计 10 个月内可完成"
      }
    ],
    "risks": [
      {
        "level": "medium",
        "description": "对比基线较多，需谨慎选择",
        "mitigation": "建议聚焦 3-4 个主流基线"
      }
    ],
    "agent": "critic",
    "model": "gpt-4.1",
    "cost_cny": 0.025,
    "created_at": "2026-06-20T09:30:00Z"
  }
}
```

### 15.2 查询校验结果

**请求**：

```
GET /api/constraints/{validation_id}
```

**响应**：同 15.1 响应结构。

---

## 16. 预算管理 API

ThesisMiner v8.0 实施透明预算账本（Transparent Ledger）机制，记录每次 LLM 调用的 Token 用量与费用，支持预算上限与告警。

### 16.1 查询预算账本

**请求**：

```
GET /api/budgets/{session_id}?agent=reasoner&limit=50
```

**响应**：

```json
{
  "session_id": "ses_20260620_a1b2c3d4",
  "summary": {
    "total_cost_cny": 12.56,
    "total_tokens": 1256000,
    "total_cached_tokens": 1188000,
    "cache_savings_cny": 1.188,
    "budget_limit_cny": 50.0,
    "budget_used_percent": 25.12,
    "call_count": 1240,
    "by_agent": {
      "orchestrator": {"cost_cny": 3.20, "calls": 320},
      "reasoner": {"cost_cny": 2.80, "calls": 280},
      "searcher": {"cost_cny": 4.10, "calls": 410},
      "critic": {"cost_cny": 1.56, "calls": 230},
      "writer": {"cost_cny": 0.90, "calls": 0}
    },
    "by_model": {
      "claude-sonnet-4.5": {"cost_cny": 3.20, "calls": 320},
      "deepseek-r2": {"cost_cny": 2.80, "calls": 280},
      "deepseek-v3.2": {"cost_cny": 4.10, "calls": 410},
      "gpt-4.1": {"cost_cny": 1.56, "calls": 230}
    }
  },
  "ledger": [
    {
      "id": "led_1",
      "session_id": "ses_20260620_a1b2c3d4",
      "agent": "reasoner",
      "model": "deepseek-r2",
      "prompt_tokens": 1200,
      "completion_tokens": 450,
      "cached_tokens": 980,
      "cost_cny": 0.0042,
      "endpoint": "/api/sessions/.../messages",
      "created_at": "2026-06-20T09:30:05Z"
    }
  ],
  "count": 50,
  "limit": 50,
  "offset": 0,
  "total": 1240
}
```

### 16.2 预算估算

**请求**：

```
POST /api/budgets/estimate
Content-Type: application/json
```

**请求体**：

```json
{
  "degree": "master",
  "discipline": "computer_science",
  "mode": "full_pipeline",
  "options": {
    "max_ideas": 5,
    "literature_count": 30,
    "include_citations": true
  }
}
```

**响应**：

```json
{
  "success": true,
  "data": {
    "estimated_cost_cny": {
      "min": 8.5,
      "expected": 15.2,
      "max": 28.0
    },
    "estimated_tokens": {
      "prompt": 1200000,
      "completion": 560000,
      "total": 1760000
    },
    "estimated_duration_seconds": 180,
    "breakdown": {
      "info_confirm": {"cost_cny": 0.5, "calls": 2},
      "creativity": {"cost_cny": 3.2, "calls": 5},
      "validation": {"cost_cny": 2.8, "calls": 5},
      "generation": {"cost_cny": 6.5, "calls": 3},
      "deep_assist": {"cost_cny": 2.2, "calls": 4}
    },
    "assumptions": {
      "cache_hit_rate": 0.95,
      "avg_prompt_tokens": 1500,
      "avg_completion_tokens": 700
    }
  }
}
```

### 16.3 预算告警

**请求**：

```
POST /api/budgets/{session_id}/alerts
Content-Type: application/json
```

**请求体**：

```json
{
  "thresholds": [
    {"percent": 50, "action": "notify"},
    {"percent": 80, "action": "notify"},
    {"percent": 100, "action": "block"}
  ],
  "webhook_url": "https://your-server.com/webhooks/budget"
}
```

**响应**：

```json
{
  "success": true,
  "data": {
    "alert_id": "alert_20260620_a1b2c3d4",
    "session_id": "ses_20260620_a1b2c3d4",
    "thresholds": [
      {"percent": 50, "action": "notify", "triggered": false},
      {"percent": 80, "action": "notify", "triggered": false},
      {"percent": 100, "action": "block", "triggered": false}
    ],
    "created_at": "2026-06-20T10:00:00Z"
  }
}
```

当预算达到阈值时，系统会向 `webhook_url` 发送 POST 请求：

```json
{
  "event": "budget_alert",
  "session_id": "ses_20260620_a1b2c3d4",
  "threshold_percent": 80,
  "current_cost_cny": 40.2,
  "budget_limit_cny": 50.0,
  "action": "notify",
  "timestamp": "2026-06-20T11:00:00Z"
}
```

---

## 17. 配置管理 API

配置管理 API 用于查询与更新 ThesisMiner 的运行时配置，包括模型列表、Agent 路由、缓存策略等。

### 17.1 查询配置

**请求**：

```
GET /api/config
```

**响应**：

```json
{
  "ai": {
    "default_model": "deepseek-v3.2",
    "default_base_url": "https://api.deepseek.com/v1",
    "streaming_enabled": true,
    "thinking_enabled": true
  },
  "cache": {
    "enabled": true,
    "strategy": "three_stage_prefix",
    "target_hit_rate": 0.95
  },
  "budget": {
    "default_limit_cny": 50.0,
    "hard_limit_cny": 200.0,
    "alert_thresholds": [50, 80, 100]
  },
  "database": {
    "path": "data/thesis_miner.db",
    "wal_enabled": true,
    "backup_interval_hours": 24
  },
  "server": {
    "host": "127.0.0.1",
    "port": 8000,
    "cors_origins": ["*"]
  },
  "rate_limit": {
    "global": "600/60",
    "session": "60/60",
    "generation": "5/60"
  }
}
```

### 17.2 更新配置

**请求**：

```
PATCH /api/config
Content-Type: application/json
```

**请求体**：

```json
{
  "ai": {
    "default_model": "claude-sonnet-4.5"
  },
  "budget": {
    "default_limit_cny": 100.0
  }
}
```

**响应**：

```json
{
  "success": true,
  "data": {
    "updated_fields": ["ai.default_model", "budget.default_limit_cny"],
    "updated_at": "2026-06-20T10:00:00Z",
    "requires_restart": false
  }
}
```

部分配置项（如 `server.host`、`server.port`）需要重启服务才能生效，响应中会标记 `requires_restart: true`。

### 17.3 模型列表

**请求**：

```
GET /api/config/models
```

**响应**：

```json
{
  "models": [
    {
      "id": "gpt-4.1-mini",
      "label": "GPT-4.1 Mini",
      "base_url": "https://api.openai.com/v1",
      "pricing": {"input_cny_per_million": 0.7, "output_cny_per_million": 2.8},
      "supports_streaming": true,
      "supports_thinking": false,
      "supports_web_search": false,
      "max_context": 1000000,
      "default_temperature": 0.7,
      "agent_default": "mentor",
      "release_year": 2025,
      "configured": true
    },
    {
      "id": "deepseek-v3.2",
      "label": "DeepSeek V3.2 (2026)",
      "base_url": "https://api.deepseek.com/v1",
      "pricing": {"input_cny_per_million": 1, "output_cny_per_million": 4},
      "supports_streaming": true,
      "supports_thinking": false,
      "supports_web_search": true,
      "max_context": 128000,
      "default_temperature": 0.7,
      "agent_default": "search",
      "release_year": 2026,
      "configured": true
    }
  ],
  "count": 10,
  "default_step_models": {
    "orchestrator": "claude-sonnet-4.5",
    "reasoner": "deepseek-r2",
    "mentor": "gpt-4.1",
    "inspire": "qwen3-max",
    "report": "claude-opus-4.5",
    "search": "deepseek-v3.2"
  }
}
```

---

## 18. SSE 流式响应

### 18.1 SSE 协议概述

ThesisMiner v8.0 使用 Server-Sent Events（SSE）协议向客户端推送流式数据。SSE 基于 HTTP 长连接，服务端持续向客户端推送事件，客户端通过 `EventSource` API 或自定义 HTTP 客户端消费。

SSE 协议特点：

- 单向通信（服务端到客户端）；
- 基于 HTTP/1.1，兼容现有基础设施；
- 自动重连机制；
- 文本协议，易于调试。

**SSE 帧格式**：

```
event: <event_type>
data: <json_payload>

event: <event_type>
data: <json_payload>

```

每个事件由 `event` 行、`data` 行与空行分隔。`data` 行内容为 JSON 字符串。

### 18.2 事件类型清单

ThesisMiner v8.0 定义了 11 种 SSE 事件类型：

| 事件类型 | 触发场景 | payload 关键字段 |
|---------|---------|-----------------|
| `stage_change` | 五阶段切换 | `stage`, `previous_stage` |
| `agent_start` | Agent 开始执行 | `agent`, `task` |
| `agent_thinking` | Agent 思考过程 | `agent`, `thinking` |
| `agent_message` | Agent 输出消息片段 | `agent`, `delta` |
| `agent_tool_call` | Agent 调用工具 | `agent`, `tool`, `arguments` |
| `agent_complete` | Agent 执行完成 | `agent`, `usage`, `cost` |
| `citation` | 引用产生 | `citation`, `message_id` |
| `cache_hit` | 缓存命中 | `saved_tokens`, `agent` |
| `error` | 错误发生 | `code`, `message`, `recoverable` |
| `progress` | 进度更新 | `percent`, `current_stage` |
| `done` | 整体完成 | `result`, `total_cost` |

**事件流示例**：

```
event: stage_change
data: {"stage":"creativity","previous_stage":"info_confirm","timestamp":"2026-06-20T09:00:00Z"}

event: agent_start
data: {"agent":"inspire","task":"generate_ideas","timestamp":"2026-06-20T09:00:01Z"}

event: agent_thinking
data: {"agent":"inspire","thinking":"用户希望探索 GNN 在分子性质预测中的应用，我需要从方法论、应用、数据集等维度生成创意...","timestamp":"2026-06-20T09:00:02Z"}

event: agent_message
data: {"agent":"inspire","delta":"基于","message_id":"msg_20260620_a1","timestamp":"2026-06-20T09:00:03Z"}

event: agent_message
data: {"agent":"inspire","delta":"消息传递神经网络","message_id":"msg_20260620_a1","timestamp":"2026-06-20T09:00:03Z"}

event: agent_message
data: {"agent":"inspire","delta":"（MPNN）","message_id":"msg_20260620_a1","timestamp":"2026-06-20T09:00:04Z"}

event: citation
data: {"citation":{"id":"cit_1","text":"MPNN","source":"Gilmer et al., 2017"},"message_id":"msg_20260620_a1","timestamp":"2026-06-20T09:00:04Z"}

event: cache_hit
data: {"agent":"inspire","saved_tokens":980,"timestamp":"2026-06-20T09:00:05Z"}

event: agent_complete
data: {"agent":"inspire","usage":{"prompt_tokens":1800,"completion_tokens":1400,"cached_tokens":980},"cost_cny":0.031,"timestamp":"2026-06-20T09:00:10Z"}

event: progress
data: {"percent":40,"current_stage":"creativity","timestamp":"2026-06-20T09:00:10Z"}

event: done
data: {"result":{"proposal_id":"prop_20260620_a1b2c3d4","status":"completed"},"total_cost_cny":12.56,"total_duration_seconds":180,"timestamp":"2026-06-20T09:03:00Z"}
```

### 18.3 客户端实现

**JavaScript（EventSource）**：

```javascript
const eventSource = new EventSource('/api/proposals/generate/stream?session_id=ses_20260620_a1b2c3d4');

eventSource.addEventListener('stage_change', (event) => {
  const data = JSON.parse(event.data);
  console.log(`阶段切换：${data.previous_stage} → ${data.stage}`);
  updateStageUI(data.stage);
});

eventSource.addEventListener('agent_message', (event) => {
  const data = JSON.parse(event.data);
  appendToMessage(data.message_id, data.delta);
});

eventSource.addEventListener('citation', (event) => {
  const data = JSON.parse(event.data);
  addCitationToMessage(data.message_id, data.citation);
});

eventSource.addEventListener('error', (event) => {
  if (event.target.readyState === EventSource.CLOSED) {
    console.log('SSE 连接已关闭');
  } else {
    console.error('SSE 错误', event);
  }
});

eventSource.addEventListener('done', (event) => {
  const data = JSON.parse(event.data);
  console.log('完成，总成本：', data.total_cost_cny);
  eventSource.close();
});
```

**Python（httpx-sse）**：

```python
import httpx
from httpx_sse import connect_sse

def consume_stream(session_id: str):
    url = f"http://127.0.0.1:8000/api/proposals/generate/stream"
    params = {"session_id": session_id}
    with httpx.Client() as client:
        with connect_sse(client, "GET", url, params=params) as event_source:
            for event in event_source.iter_sse():
                if event.event == "agent_message":
                    data = json.loads(event.data)
                    print(data["delta"], end="", flush=True)
                elif event.event == "done":
                    data = json.loads(event.data)
                    print(f"\n完成，总成本：{data['total_cost_cny']}")
                    break
                elif event.event == "error":
                    data = json.loads(event.data)
                    print(f"\n错误：{data['message']}")
                    break
```

**curl**：

```bash
curl -N "http://127.0.0.1:8000/api/proposals/generate/stream?session_id=ses_20260620_a1b2c3d4"
```

`-N` 参数禁用缓冲，确保实时输出。

---

## 19. WebSocket 支持

### 19.1 连接建立

ThesisMiner v8.0 提供 WebSocket 通道用于双向实时通信，适用于需要客户端主动控制（如暂停/恢复生成）的场景。

**连接 URL**：

```
ws://127.0.0.1:8000/ws/sessions/{session_id}?token=optional_api_key
```

**握手过程**：

```
客户端                              服务端
  │                                   │
  │ ─── WS Upgrade Request ─────────▶ │
  │                                   │
  │ ◀── 101 Switching Protocols ──── │
  │                                   │
  │ ◀── hello event                  │
  │                                   │
  │ ─── subscribe event ───────────▶ │
  │                                   │
  │ ◀── subscribed event             │
  │                                   │
  │ ◀── agent_message event          │
  │ ◀── agent_message event          │
  │ ◀── done event                   │
  │                                   │
  │ ─── close ─────────────────────▶ │
  │                                   │
```

### 19.2 消息格式

WebSocket 消息统一为 JSON 文本帧，格式如下：

```json
{
  "type": "<message_type>",
  "payload": { ... },
  "id": "<optional_message_id>",
  "timestamp": "2026-06-20T10:00:00Z"
}
```

**客户端可发送的消息类型**：

| type | 说明 | payload |
|------|------|---------|
| `subscribe` | 订阅会话事件 | `{"session_id": "..."}` |
| `unsubscribe` | 取消订阅 | `{"session_id": "..."}` |
| `send_message` | 发送消息 | `{"conversation_id": "...", "content": "..."}` |
| `pause_generation` | 暂停生成 | `{"proposal_id": "..."}` |
| `resume_generation` | 恢复生成 | `{"proposal_id": "..."}` |
| `cancel_generation` | 取消生成 | `{"proposal_id": "..."}` |
| `ping` | 心跳 | `{}` |

**服务端发送的消息类型**：

| type | 说明 |
|------|------|
| `hello` | 连接建立确认 |
| `subscribed` | 订阅成功 |
| `stage_change` | 阶段切换 |
| `agent_message` | Agent 消息片段 |
| `agent_complete` | Agent 完成 |
| `citation` | 引用产生 |
| `error` | 错误 |
| `done` | 整体完成 |
| `pong` | 心跳响应 |

**示例会话**：

```json
// 服务端 → 客户端
{"type":"hello","payload":{"server_version":"8.0.0","connection_id":"ws_12345"}}

// 客户端 → 服务端
{"type":"subscribe","payload":{"session_id":"ses_20260620_a1b2c3d4"}}

// 服务端 → 客户端
{"type":"subscribed","payload":{"session_id":"ses_20260620_a1b2c3d4"}}

// 客户端 → 服务端
{"type":"send_message","payload":{"conversation_id":"conv_20260620_a1b2c3d4","content":"请继续"}}

// 服务端 → 客户端
{"type":"agent_message","payload":{"agent":"reasoner","delta":"好的，我继续分析..."}}

// 客户端 → 服务端
{"type":"pause_generation","payload":{"proposal_id":"prop_20260620_a1b2c3d4"}}

// 服务端 → 客户端
{"type":"error","payload":{"code":"GENERATION_PAUSED","message":"生成已暂停"}}
```

### 19.3 心跳与重连

**心跳机制**：

客户端应每 30 秒发送一次 `ping`：

```javascript
const heartbeatInterval = setInterval(() => {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({type: 'ping', payload: {}}));
  }
}, 30000);
```

服务端在 60 秒内未收到 `ping` 将主动关闭连接。

**重连策略**：

```javascript
class ReconnectingWebSocket {
  constructor(url, options = {}) {
    this.url = url;
    this.options = {maxRetries: 5, ...options};
    this.retries = 0;
    this.connect();
  }

  connect() {
    this.ws = new WebSocket(this.url);
    this.ws.onopen = () => {
      this.retries = 0;
      this.onOpen?.();
    };
    this.ws.onclose = (event) => {
      this.onClose?.(event);
      if (this.retries < this.options.maxRetries) {
        const delay = Math.min(1000 * 2 ** this.retries, 30000);
        setTimeout(() => this.connect(), delay);
        this.retries++;
      }
    };
    this.ws.onmessage = (event) => this.onMessage?.(JSON.parse(event.data));
    this.ws.onerror = (error) => this.onError?.(error);
  }

  send(data) {
    this.ws.send(JSON.stringify(data));
  }

  close() {
    this.options.maxRetries = 0;
    this.ws.close();
  }
}
```

---

## 20. 完整使用示例

### 20.1 curl 示例集

**示例 1：创建会话**

```bash
curl -X POST "http://127.0.0.1:8000/api/sessions" \
  -H "Content-Type: application/json" \
  -d '{
    "degree": "master",
    "discipline": "computer_science",
    "research_background": "本人研究方向为图神经网络，希望探索其在药物分子设计中的应用。",
    "initial_topic": "基于图神经网络的药物分子性质预测"
  }'
```

**示例 2：查询会话列表**

```bash
curl -X GET "http://127.0.0.1:8000/api/sessions?limit=10&offset=0&status=active"
```

**示例 3：获取会话详情**

```bash
curl -X GET "http://127.0.0.1:8000/api/sessions/ses_20260620_a1b2c3d4"
```

**示例 4：更新会话状态**

```bash
curl -X PATCH "http://127.0.0.1:8000/api/sessions/ses_20260620_a1b2c3d4" \
  -H "Content-Type: application/json" \
  -d '{"status": "archived"}'
```

**示例 5：删除会话**

```bash
curl -X DELETE "http://127.0.0.1:8000/api/sessions/ses_20260620_a1b2c3d4"
```

**示例 6：创建对话**

```bash
curl -X POST "http://127.0.0.1:8000/api/sessions/ses_20260620_a1b2c3d4/conversations" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "探索 GNN 在分子性质预测中的可行性",
    "stage": "creativity"
  }'
```

**示例 7：查询对话列表**

```bash
curl -X GET "http://127.0.0.1:8000/api/sessions/ses_20260620_a1b2c3d4/conversations?stage=creativity"
```

**示例 8：发送消息（同步）**

```bash
curl -X POST "http://127.0.0.1:8000/api/sessions/ses_20260620_a1b2c3d4/conversations/conv_20260620_a1b2c3d4/messages" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "user",
    "content": "请帮我分析 GNN 在分子性质预测中的优势与挑战。",
    "stream": false,
    "agent_hint": "reasoner"
  }'
```

**示例 9：发送消息（流式）**

```bash
curl -N -X POST "http://127.0.0.1:8000/api/sessions/ses_20260620_a1b2c3d4/conversations/conv_20260620_a1b2c3d4/messages" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "user",
    "content": "请帮我分析 GNN 在分子性质预测中的优势与挑战。",
    "stream": true,
    "agent_hint": "reasoner"
  }'
```

**示例 10：查询消息历史**

```bash
curl -X GET "http://127.0.0.1:8000/api/sessions/ses_20260620_a1b2c3d4/conversations/conv_20260620_a1b2c3d4/messages?limit=50"
```

**示例 11：获取消息详情**

```bash
curl -X GET "http://127.0.0.1:8000/api/messages/msg_20260620_a1"
```

**示例 12：查询消息引用**

```bash
curl -X GET "http://127.0.0.1:8000/api/messages/msg_20260620_a1/citations"
```

**示例 13：导出引用为 BibTeX**

```bash
curl -X GET "http://127.0.0.1:8000/api/messages/msg_20260620_a1/citations/export?format=bibtex" \
  -o citations.bib
```

**示例 14：查询 Agent 注册表**

```bash
curl -X GET "http://127.0.0.1:8000/api/agents"
```

**示例 15：查询 Agent 路由**

```bash
curl -X GET "http://127.0.0.1:8000/api/agents/routing"
```

**示例 16：切换 Agent 模型**

```bash
curl -X PATCH "http://127.0.0.1:8000/api/agents/reasoner/model" \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "gpt-4.1",
    "scope": "session",
    "session_id": "ses_20260620_a1b2c3d4"
  }'
```

**示例 17：查询缓存命中率**

```bash
curl -X GET "http://127.0.0.1:8000/api/cache-stats?session_id=ses_20260620_a1b2c3d4"
```

**示例 18：重置缓存统计**

```bash
curl -X DELETE "http://127.0.0.1:8000/api/cache-stats"
```

**示例 19：查询谱系图**

```bash
curl -X GET "http://127.0.0.1:8000/api/lineage/ses_20260620_a1b2c3d4"
```

**示例 20：导出谱系为 Mermaid**

```bash
curl -X GET "http://127.0.0.1:8000/api/lineage/ses_20260620_a1b2c3d4/export?format=mermaid" \
  -o lineage.mmd
```

**示例 21：触发论题生成（流式）**

```bash
curl -N -X POST "http://127.0.0.1:8000/api/proposals/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "ses_20260620_a1b2c3d4",
    "mode": "full_pipeline",
    "stream": true,
    "options": {
      "max_ideas": 5,
      "literature_count": 30,
      "include_citations": true
    }
  }'
```

**示例 22：查询生成状态**

```bash
curl -X GET "http://127.0.0.1:8000/api/proposals/prop_20260620_a1b2c3d4"
```

**示例 23：取消生成**

```bash
curl -X DELETE "http://127.0.0.1:8000/api/proposals/prop_20260620_a1b2c3d4"
```

**示例 24：触发创意**

```bash
curl -X POST "http://127.0.0.1:8000/api/creativity/spark" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "ses_20260620_a1b2c3d4",
    "seed_topic": "基于图神经网络的药物分子性质预测",
    "max_ideas": 5,
    "diversity_weight": 0.7
  }'
```

**示例 25：触发约束校验**

```bash
curl -X POST "http://127.0.0.1:8000/api/constraints/validate" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "ses_20260620_a1b2c3d4",
    "topic": "基于 MPNN 的分子溶解度预测",
    "constraints": {
      "max_years": 1,
      "literature_count": 30,
      "must_include_keywords": ["GNN", "分子图", "溶解度"]
    }
  }'
```

**示例 26：查询预算账本**

```bash
curl -X GET "http://127.0.0.1:8000/api/budgets/ses_20260620_a1b2c3d4?limit=50"
```

**示例 27：预算估算**

```bash
curl -X POST "http://127.0.0.1:8000/api/budgets/estimate" \
  -H "Content-Type: application/json" \
  -d '{
    "degree": "master",
    "discipline": "computer_science",
    "mode": "full_pipeline"
  }'
```

**示例 28：设置预算告警**

```bash
curl -X POST "http://127.0.0.1:8000/api/budgets/ses_20260620_a1b2c3d4/alerts" \
  -H "Content-Type: application/json" \
  -d '{
    "thresholds": [
      {"percent": 50, "action": "notify"},
      {"percent": 100, "action": "block"}
    ],
    "webhook_url": "https://your-server.com/webhooks/budget"
  }'
```

**示例 29：查询配置**

```bash
curl -X GET "http://127.0.0.1:8000/api/config"
```

**示例 30：查询模型列表**

```bash
curl -X GET "http://127.0.0.1:8000/api/config/models"
```

**示例 31：更新配置**

```bash
curl -X PATCH "http://127.0.0.1:8000/api/config" \
  -H "Content-Type: application/json" \
  -d '{
    "ai": {"default_model": "claude-sonnet-4.5"},
    "budget": {"default_limit_cny": 100.0}
  }'
```

**示例 32：携带 API Key 请求**

```bash
curl -X GET "http://127.0.0.1:8000/api/sessions" \
  -H "Authorization: Bearer sk-tm-xxxxxxxxxxxxxxxxxxxx"
```

**示例 33：携带 Owner ID 请求**

```bash
curl -X GET "http://127.0.0.1:8000/api/sessions" \
  -H "X-Owner-Id: user-12345"
```

### 20.2 Python 示例集

**示例 1：完整会话流程**

```python
import httpx

BASE_URL = "http://127.0.0.1:8000"

def full_workflow():
    with httpx.Client(timeout=300) as client:
        # 1. 创建会话
        resp = client.post(f"{BASE_URL}/api/sessions", json={
            "degree": "master",
            "discipline": "computer_science",
            "research_background": "研究方向为图神经网络",
            "initial_topic": "基于 GNN 的分子性质预测"
        })
        session = resp.json()["data"]
        session_id = session["id"]
        print(f"会话已创建：{session_id}")

        # 2. 创建对话
        resp = client.post(f"{BASE_URL}/api/sessions/{session_id}/conversations", json={
            "title": "探索 GNN 应用",
            "stage": "creativity"
        })
        conversation = resp.json()["data"]
        conversation_id = conversation["id"]
        print(f"对话已创建：{conversation_id}")

        # 3. 发送消息
        resp = client.post(
            f"{BASE_URL}/api/sessions/{session_id}/conversations/{conversation_id}/messages",
            json={
                "role": "user",
                "content": "请分析 GNN 在分子性质预测中的优势。",
                "stream": False,
                "agent_hint": "reasoner"
            }
        )
        result = resp.json()["data"]
        print(f"Agent 回复：{result['assistant_message']['content'][:100]}...")
        print(f"本次成本：{result['assistant_message']['cost_cny']} CNY")

        # 4. 触发完整生成
        resp = client.post(f"{BASE_URL}/api/proposals/generate", json={
            "session_id": session_id,
            "mode": "full_pipeline",
            "stream": False,
            "options": {"max_ideas": 5, "literature_count": 30}
        })
        proposal = resp.json()["data"]
        print(f"生成任务已提交：{proposal['proposal_id']}")

        # 5. 查询预算
        resp = client.get(f"{BASE_URL}/api/budgets/{session_id}")
        budget = resp.json()["summary"]
        print(f"总成本：{budget['total_cost_cny']} CNY")
        print(f"缓存节省：{budget['cache_savings_cny']} CNY")

full_workflow()
```

**示例 2：流式消费**

```python
import httpx
import json
from httpx_sse import connect_sse

def stream_generation(session_id: str):
    url = f"http://127.0.0.1:8000/api/proposals/generate"
    payload = {
        "session_id": session_id,
        "mode": "full_pipeline",
        "stream": True,
        "options": {"max_ideas": 5}
    }
    with httpx.Client(timeout=None) as client:
        with connect_sse(client, "POST", url, json=payload) as event_source:
            current_message = ""
            for event in event_source.iter_sse():
                data = json.loads(event.data)
                if event.event == "stage_change":
                    print(f"\n[阶段] {data['previous_stage']} → {data['stage']}")
                elif event.event == "agent_message":
                    current_message += data["delta"]
                    print(data["delta"], end="", flush=True)
                elif event.event == "citation":
                    print(f"\n[引用] {data['citation']['text']} → {data['citation']['source']}")
                elif event.event == "cache_hit":
                    print(f"\n[缓存] 命中，节省 {data['saved_tokens']} tokens")
                elif event.event == "error":
                    print(f"\n[错误] {data['message']}")
                    break
                elif event.event == "done":
                    print(f"\n[完成] 总成本：{data['total_cost_cny']} CNY")
                    break

stream_generation("ses_20260620_a1b2c3d4")
```

**示例 3：WebSocket 客户端**

```python
import asyncio
import json
import websockets

async def ws_client(session_id: str):
    uri = f"ws://127.0.0.1:8000/ws/sessions/{session_id}"
    async with websockets.connect(uri) as ws:
        # 接收 hello
        hello = json.loads(await ws.recv())
        print(f"连接建立：{hello['payload']['connection_id']}")

        # 订阅会话
        await ws.send(json.dumps({
            "type": "subscribe",
            "payload": {"session_id": session_id}
        }))

        # 接收事件
        while True:
            msg = json.loads(await ws.recv())
            if msg["type"] == "agent_message":
                print(msg["payload"]["delta"], end="", flush=True)
            elif msg["type"] == "done":
                print(f"\n完成：{msg['payload']}")
                break
            elif msg["type"] == "error":
                print(f"\n错误：{msg['payload']['message']}")
                break

asyncio.run(ws_client("ses_20260620_a1b2c3d4"))
```

**示例 4：带重试的请求封装**

```python
import time
import random
import httpx

class ThesisMinerClient:
    def __init__(self, base_url: str, api_key: str = None, max_retries: int = 5):
        self.base_url = base_url
        self.max_retries = max_retries
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self.client = httpx.Client(headers=headers, timeout=300)

    def request(self, method: str, path: str, **kwargs):
        url = f"{self.base_url}{path}"
        for attempt in range(self.max_retries):
            try:
                resp = self.client.request(method, url, **kwargs)
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 2 ** attempt))
                    time.sleep(retry_after + random.uniform(0, 0.5))
                    continue
                resp.raise_for_status()
                return resp.json()
            except httpx.RequestError as e:
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(2 ** attempt + random.uniform(0, 0.5))
        raise Exception(f"超过最大重试次数 {self.max_retries}")

    def create_session(self, degree: str, discipline: str, **kwargs):
        payload = {"degree": degree, "discipline": discipline, **kwargs}
        return self.request("POST", "/api/sessions", json=payload)

    def send_message(self, session_id: str, conversation_id: str, content: str, **kwargs):
        path = f"/api/sessions/{session_id}/conversations/{conversation_id}/messages"
        payload = {"role": "user", "content": content, **kwargs}
        return self.request("POST", path, json=payload)

    def generate_proposal(self, session_id: str, **kwargs):
        payload = {"session_id": session_id, **kwargs}
        return self.request("POST", "/api/proposals/generate", json=payload)

client = ThesisMinerClient("http://127.0.0.1:8000")
session = client.create_session("master", "computer_science")
print(session["data"]["id"])
```

**示例 5：批量查询与分页**

```python
def fetch_all_sessions(client):
    """分页获取全部会话。"""
    all_sessions = []
    offset = 0
    limit = 100
    while True:
        resp = client.request("GET", f"/api/sessions?limit={limit}&offset={offset}")
        sessions = resp["sessions"]
        all_sessions.extend(sessions)
        if len(sessions) < limit:
            break
        offset += limit
    return all_sessions
```

### 20.3 JavaScript 示例集

**示例 1：浏览器端 SSE 消费**

```javascript
async function startGeneration(sessionId) {
  const eventSource = new EventSource(
    `/api/proposals/generate/stream?session_id=${sessionId}`
  );

  const messageBuffer = {};

  eventSource.addEventListener('stage_change', (e) => {
    const data = JSON.parse(e.data);
    document.getElementById('stage').textContent = data.stage;
  });

  eventSource.addEventListener('agent_message', (e) => {
    const data = JSON.parse(e.data);
    if (!messageBuffer[data.message_id]) {
      messageBuffer[data.message_id] = '';
      createMessageElement(data.message_id);
    }
    messageBuffer[data.message_id] += data.delta;
    updateMessageElement(data.message_id, messageBuffer[data.message_id]);
  });

  eventSource.addEventListener('citation', (e) => {
    const data = JSON.parse(e.data);
    addCitation(data.message_id, data.citation);
  });

  eventSource.addEventListener('done', (e) => {
    const data = JSON.parse(e.data);
    showCompletion(data.total_cost_cny);
    eventSource.close();
  });

  eventSource.addEventListener('error', (e) => {
    console.error('SSE 错误', e);
    if (eventSource.readyState === EventSource.CLOSED) {
      showReconnectPrompt();
    }
  });
}
```

**示例 2：fetch + ReadableStream 消费**

```javascript
async function sendMessageStream(sessionId, conversationId, content) {
  const resp = await fetch(
    `/api/sessions/${sessionId}/conversations/${conversationId}/messages`,
    {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({role: 'user', content, stream: true})
    }
  );

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const {done, value} = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, {stream: true});
    const lines = buffer.split('\n');
    buffer = lines.pop();
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));
        if (data.delta) {
          appendToUI(data.delta);
        }
      }
    }
  }
}
```

**示例 3：WebSocket 客户端类**

```javascript
class ThesisMinerWS {
  constructor(sessionId, options = {}) {
    this.sessionId = sessionId;
    this.options = {maxRetries: 5, ...options};
    this.retries = 0;
    this.handlers = {};
    this.connect();
  }

  connect() {
    const url = `ws://${location.host}/ws/sessions/${this.sessionId}`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.retries = 0;
      this.emit('open');
      this.startHeartbeat();
    };

    this.ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      this.emit(msg.type, msg.payload);
    };

    this.ws.onclose = () => {
      this.stopHeartbeat();
      this.emit('close');
      if (this.retries < this.options.maxRetries) {
        const delay = Math.min(1000 * 2 ** this.retries, 30000);
        setTimeout(() => this.connect(), delay);
        this.retries++;
      }
    };

    this.ws.onerror = (error) => this.emit('error', error);
  }

  on(event, handler) {
    this.handlers[event] = this.handlers[event] || [];
    this.handlers[event].push(handler);
  }

  emit(event, payload) {
    (this.handlers[event] || []).forEach(h => h(payload));
  }

  send(type, payload) {
    this.ws.send(JSON.stringify({type, payload}));
  }

  startHeartbeat() {
    this.heartbeat = setInterval(() => {
      if (this.ws.readyState === WebSocket.OPEN) {
        this.send('ping', {});
      }
    }, 30000);
  }

  stopHeartbeat() {
    clearInterval(this.heartbeat);
  }

  close() {
    this.options.maxRetries = 0;
    this.ws.close();
  }
}

// 使用
const ws = new ThesisMinerWS('ses_20260620_a1b2c3d4');
ws.on('agent_message', (payload) => appendToUI(payload.delta));
ws.on('done', (payload) => showCompletion(payload));
ws.on('error', (error) => console.error(error));
```

**示例 4：Node.js 完整集成**

```javascript
const axios = require('axios');
const {WebSocket} = require('ws');

class ThesisMinerNodeClient {
  constructor(baseUrl, apiKey) {
    this.baseUrl = baseUrl;
    this.client = axios.create({
      baseURL: baseUrl,
      headers: apiKey ? {Authorization: `Bearer ${apiKey}`} : {},
      timeout: 300000
    });
  }

  async createSession(degree, discipline, extra = {}) {
    const {data} = await this.client.post('/api/sessions', {
      degree, discipline, ...extra
    });
    return data.data;
  }

  async sendMessage(sessionId, conversationId, content, options = {}) {
    const {data} = await this.client.post(
      `/api/sessions/${sessionId}/conversations/${conversationId}/messages`,
      {role: 'user', content, stream: false, ...options}
    );
    return data.data;
  }

  async generateProposal(sessionId, options = {}) {
    const {data} = await this.client.post('/api/proposals/generate', {
      session_id: sessionId, stream: false, ...options
    });
    return data.data;
  }

  async getBudget(sessionId) {
    const {data} = await this.client.get(`/api/budgets/${sessionId}`);
    return data.summary;
  }

  connectWS(sessionId) {
    const url = `${this.baseUrl.replace('http', 'ws')}/ws/sessions/${sessionId}`;
    return new WebSocket(url);
  }
}

module.exports = ThesisMinerNodeClient;
```

**示例 5：React Hook 封装**

```javascript
import {useEffect, useState, useRef, useCallback} from 'react';

function useThesisMinerStream(sessionId) {
  const [stage, setStage] = useState('idle');
  const [messages, setMessages] = useState([]);
  const [citations, setCitations] = useState([]);
  const [cost, setCost] = useState(0);
  const [isStreaming, setIsStreaming] = useState(false);
  const eventSourceRef = useRef(null);

  const start = useCallback(() => {
    setIsStreaming(true);
    const es = new EventSource(`/api/proposals/generate/stream?session_id=${sessionId}`);
    eventSourceRef.current = es;

    es.addEventListener('stage_change', (e) => {
      setStage(JSON.parse(e.data).stage);
    });

    es.addEventListener('agent_message', (e) => {
      const data = JSON.parse(e.data);
      setMessages(prev => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last && last.id === data.message_id) {
          next[next.length - 1] = {...last, content: last.content + data.delta};
        } else {
          next.push({id: data.message_id, content: data.delta, agent: data.agent});
        }
        return next;
      });
    });

    es.addEventListener('citation', (e) => {
      setCitations(prev => [...prev, JSON.parse(e.data).citation]);
    });

    es.addEventListener('done', (e) => {
      setCost(JSON.parse(e.data).total_cost_cny);
      setIsStreaming(false);
      es.close();
    });

    es.addEventListener('error', () => {
      setIsStreaming(false);
    });
  }, [sessionId]);

  const stop = useCallback(() => {
    eventSourceRef.current?.close();
    setIsStreaming(false);
  }, []);

  useEffect(() => () => eventSourceRef.current?.close(), []);

  return {stage, messages, citations, cost, isStreaming, start, stop};
}
```

---

## 21. 错误处理与重试策略

### 21.1 错误响应格式

所有错误响应统一采用以下结构：

```json
{
  "success": false,
  "data": null,
  "error": "会话不存在",
  "code": "SESSION_NOT_FOUND",
  "details": {
    "session_id": "ses_invalid"
  },
  "request_id": "req_20260620_abc123",
  "timestamp": "2026-06-20T10:00:00Z"
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | bool | 固定为 `false` |
| `data` | null | 固定为 `null` |
| `error` | string | 人类可读的错误描述 |
| `code` | string | 机器可读的错误码 |
| `details` | object | 可选的错误详情 |
| `request_id` | string | 请求追踪 ID |
| `timestamp` | string | 错误发生时间 |

### 21.2 错误码分类

ThesisMiner v8.0 的错误码按前缀分类：

| 前缀 | 类别 | HTTP 状态码范围 | 示例 |
|------|------|----------------|------|
| `AUTH_` | 认证授权 | 401, 403 | `AUTH_INVALID_KEY` |
| `VALIDATION_` | 参数校验 | 400, 422 | `VALIDATION_ERROR` |
| `RESOURCE_` | 资源不存在 | 404 | `RESOURCE_NOT_FOUND` |
| `STATE_` | 状态冲突 | 409 | `STATE_CONFLICT` |
| `RATE_LIMIT_` | 限流 | 429 | `RATE_LIMIT_EXCEEDED` |
| `BUDGET_` | 预算超限 | 402, 409 | `BUDGET_EXCEEDED` |
| `AGENT_` | Agent 错误 | 500, 503 | `AGENT_TIMEOUT` |
| `MODEL_` | 模型错误 | 502, 503 | `MODEL_UNAVAILABLE` |
| `CACHE_` | 缓存错误 | 500 | `CACHE_INCONSISTENT` |
| `INTERNAL_` | 内部错误 | 500 | `INTERNAL_ERROR` |

**常见错误码详表**：

| code | HTTP | 说明 | 是否可重试 |
|------|------|------|-----------|
| `AUTH_INVALID_KEY` | 401 | API Key 无效 | 否 |
| `AUTH_MISSING_KEY` | 401 | 缺少 API Key | 否 |
| `AUTH_PERMISSION_DENIED` | 403 | 权限不足 | 否 |
| `VALIDATION_ERROR` | 400 | 请求参数校验失败 | 否 |
| `RESOURCE_NOT_FOUND` | 404 | 资源不存在 | 否 |
| `SESSION_NOT_FOUND` | 404 | 会话不存在 | 否 |
| `CONVERSATION_NOT_FOUND` | 404 | 对话不存在 | 否 |
| `MESSAGE_NOT_FOUND` | 404 | 消息不存在 | 否 |
| `STATE_CONFLICT` | 409 | 状态冲突 | 否 |
| `SESSION_ALREADY_ACTIVE` | 409 | 会话已处于活跃状态 | 否 |
| `RATE_LIMIT_EXCEEDED` | 429 | 触发限流 | 是 |
| `BUDGET_EXCEEDED` | 402 | 预算超限 | 否 |
| `BUDGET_ALERT_TRIGGERED` | 409 | 预算告警触发 | 否 |
| `AGENT_TIMEOUT` | 504 | Agent 执行超时 | 是 |
| `AGENT_FAILURE` | 500 | Agent 执行失败 | 是 |
| `MODEL_UNAVAILABLE` | 503 | 模型服务不可用 | 是 |
| `MODEL_RATE_LIMITED` | 429 | 上游模型限流 | 是 |
| `CACHE_INCONSISTENT` | 500 | 缓存不一致 | 是 |
| `INTERNAL_ERROR` | 500 | 内部错误 | 是 |

### 21.3 重试策略

**可重试错误**：

对于 `RATE_LIMIT_EXCEEDED`、`AGENT_TIMEOUT`、`MODEL_UNAVAILABLE`、`MODEL_RATE_LIMITED`、`INTERNAL_ERROR` 等可重试错误，推荐使用指数退避策略：

```python
import time
import random

def retry_with_backoff(func, max_retries=5, base_delay=1, max_delay=60):
    """带指数退避与抖动的重试封装。"""
    for attempt in range(max_retries):
        try:
            return func()
        except RetryableError as e:
            if attempt == max_retries - 1:
                raise
            delay = min(base_delay * (2 ** attempt), max_delay)
            delay += random.uniform(0, delay * 0.1)
            time.sleep(delay)
```

**不可重试错误**：

对于 `AUTH_*`、`VALIDATION_*`、`RESOURCE_*`、`STATE_*`、`BUDGET_*` 等不可重试错误，应直接返回给上层处理，不进行重试。

**重试决策流程**：

```
┌─────────────────────────────────────────────────────┐
│  收到错误响应                                        │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
            ┌─────────────────┐
            │  是否可重试？    │
            └────────┬────────┘
                     │
        ┌────────────┴────────────┐
        │ 是                      │ 否
        ▼                         ▼
┌──────────────────┐    ┌──────────────────────┐
│  计算退避时间     │    │  直接返回上层         │
│  delay = 2^attempt│    │  不重试              │
└────────┬─────────┘    └──────────────────────┘
         │
         ▼
┌──────────────────┐
│  sleep(delay)    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  重新发起请求     │
└────────┬─────────┘
         │
         ▼
   ┌─────────────┐
   │ 达到最大次数?│
   └──────┬──────┘
          │
   ┌──────┴──────┐
   │ 是          │ 否
   ▼             ▼
┌─────────┐  ┌──────────────┐
│ 抛出异常 │  │ 继续重试循环  │
└─────────┘  └──────────────┘
```

### 21.4 幂等性

ThesisMiner v8.0 对写操作支持基于 `client_message_id` 的幂等性：

```bash
curl -X POST "http://127.0.0.1:8000/api/sessions/ses_.../conversations/conv_.../messages" \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: client-uuid-1234" \
  -d '{"role": "user", "content": "请分析..."}'
```

服务端在收到带 `X-Idempotency-Key` 的请求时：

1. 检查该 key 是否已处理过；
2. 若已处理，返回之前的响应（含相同的 `message_id`）；
3. 若未处理，正常执行并记录 key 与响应的映射。

幂等性窗口为 24 小时，超期后 key 将被清理，相同 key 的请求会被重新执行。

**适用端点**：

- `POST /api/sessions`
- `POST /api/sessions/{sid}/conversations`
- `POST /api/sessions/{sid}/conversations/{cid}/messages`
- `POST /api/proposals/generate`
- `POST /api/creativity/spark`
- `POST /api/constraints/validate`

---

## 22. SDK 使用与客户端封装

### 22.1 Python SDK

ThesisMiner 提供官方 Python SDK `thesisminer`，封装了全部 API 与流式处理：

**安装**：

```bash
pip install thesisminer
```

**基础用法**：

```python
from thesisminer import ThesisMinerClient

client = ThesisMinerClient(
    base_url="http://127.0.0.1:8000",
    api_key="sk-tm-xxxxxxxxxxxxxxxxxxxx"
)

# 创建会话
session = client.sessions.create(
    degree="master",
    discipline="computer_science",
    research_background="研究方向为图神经网络",
    initial_topic="基于 GNN 的分子性质预测"
)

# 创建对话
conversation = client.conversations.create(
    session_id=session.id,
    title="探索 GNN 应用",
    stage="creativity"
)

# 发送消息
result = client.messages.send(
    session_id=session.id,
    conversation_id=conversation.id,
    content="请分析 GNN 的优势。",
    agent_hint="reasoner"
)
print(result.assistant_message.content)

# 流式生成
for event in client.proposals.generate_stream(
    session_id=session.id,
    mode="full_pipeline"
):
    if event.type == "agent_message":
        print(event.delta, end="", flush=True)
    elif event.type == "done":
        print(f"\n总成本：{event.total_cost_cny}")
```

**异步用法**：

```python
import asyncio
from thesisminer import AsyncThesisMinerClient

async def main():
    client = AsyncThesisMinerClient(base_url="http://127.0.0.1:8000")
    session = await client.sessions.create(degree="master", discipline="computer_science")
    async for event in client.proposals.generate_stream(session_id=session.id):
        if event.type == "agent_message":
            print(event.delta, end="", flush=True)

asyncio.run(main())
```

**上下文管理**：

```python
with ThesisMinerClient(base_url="http://127.0.0.1:8000") as client:
    session = client.sessions.create(...)
    # 自动关闭连接
```

### 22.2 JavaScript SDK

**安装**：

```bash
npm install @thesisminer/client
```

**基础用法**：

```javascript
import {ThesisMinerClient} from '@thesisminer/client';

const client = new ThesisMinerClient({
  baseUrl: 'http://127.0.0.1:8000',
  apiKey: 'sk-tm-xxxxxxxxxxxxxxxxxxxx'
});

const session = await client.sessions.create({
  degree: 'master',
  discipline: 'computer_science',
  initialTopic: '基于 GNN 的分子性质预测'
});

const conversation = await client.conversations.create({
  sessionId: session.id,
  title: '探索 GNN 应用'
});

const result = await client.messages.send({
  sessionId: session.id,
  conversationId: conversation.id,
  content: '请分析 GNN 的优势。',
  agentHint: 'reasoner'
});

console.log(result.assistantMessage.content);

// 流式生成
const stream = client.proposals.generateStream({
  sessionId: session.id,
  mode: 'full_pipeline'
});

for await (const event of stream) {
  if (event.type === 'agent_message') {
    process.stdout.write(event.delta);
  } else if (event.type === 'done') {
    console.log(`\n总成本：${event.totalCostCny}`);
  }
}
```

### 22.3 自定义客户端封装

对于不使用官方 SDK 的场景，推荐以下封装模式：

**Python 自定义封装**：

```python
import httpx
import json
from typing import Optional, Iterator

class CustomThesisMinerClient:
    """自定义 ThesisMiner 客户端封装。"""

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.Client(headers=headers, timeout=300)

    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{self.base_url}{path}"
        resp = self._client.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def _stream(self, method: str, path: str, **kwargs) -> Iterator[dict]:
        url = f"{self.base_url}{path}"
        with self._client.stream(method, url, **kwargs) as resp:
            resp.raise_for_status()
            buffer = ""
            for chunk in resp.iter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    event_str, buffer = buffer.split("\n\n", 1)
                    event = self._parse_sse(event_str)
                    if event:
                        yield event

    @staticmethod
    def _parse_sse(raw: str) -> Optional[dict]:
        event_type = None
        data = ""
        for line in raw.split("\n"):
            if line.startswith("event: "):
                event_type = line[7:]
            elif line.startswith("data: "):
                data += line[6:]
        if event_type and data:
            return {"type": event_type, "data": json.loads(data)}
        return None

    # 业务方法
    def create_session(self, **kwargs) -> dict:
        return self._request("POST", "/api/sessions", json=kwargs)

    def send_message(self, session_id: str, conversation_id: str, content: str, **kwargs):
        path = f"/api/sessions/{session_id}/conversations/{conversation_id}/messages"
        return self._request("POST", path, json={"role": "user", "content": content, **kwargs})

    def generate_stream(self, session_id: str, **kwargs) -> Iterator[dict]:
        path = "/api/proposals/generate"
        payload = {"session_id": session_id, "stream": True, **kwargs}
        return self._stream("POST", path, json=payload)

    def close(self):
        self._client.close()
```

**TypeScript 自定义封装**：

```typescript
interface SessionCreateParams {
  degree: string;
  discipline: string;
  researchBackground?: string;
  initialTopic?: string;
}

interface SendMessageParams {
  sessionId: string;
  conversationId: string;
  content: string;
  agentHint?: string;
  stream?: boolean;
}

class CustomThesisMinerClient {
  private baseUrl: string;
  private headers: Record<string, string>;

  constructor(baseUrl: string, apiKey?: string) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.headers = {'Content-Type': 'application/json'};
    if (apiKey) {
      this.headers['Authorization'] = `Bearer ${apiKey}`;
    }
  }

  async createSession(params: SessionCreateParams): Promise<any> {
    const resp = await fetch(`${this.baseUrl}/api/sessions`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify(params)
    });
    return resp.json();
  }

  async sendMessage(params: SendMessageParams): Promise<any> {
    const {sessionId, conversationId, ...body} = params;
    const resp = await fetch(
      `${this.baseUrl}/api/sessions/${sessionId}/conversations/${conversationId}/messages`,
      {
        method: 'POST',
        headers: this.headers,
        body: JSON.stringify({role: 'user', stream: false, ...body})
      }
    );
    return resp.json();
  }

  async *generateStream(sessionId: string, options: Record<string, any> = {}): AsyncGenerator<any> {
    const resp = await fetch(`${this.baseUrl}/api/proposals/generate`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify({session_id: sessionId, stream: true, ...options})
    });

    const reader = resp.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, {stream: true});
      const events = buffer.split('\n\n');
      buffer = events.pop() || '';
      for (const eventStr of events) {
        const event = this.parseSse(eventStr);
        if (event) yield event;
      }
    }
  }

  private parseSse(raw: string): any | null {
    let type = '';
    let data = '';
    for (const line of raw.split('\n')) {
      if (line.startsWith('event: ')) type = line.slice(7);
      else if (line.startsWith('data: ')) data += line.slice(6);
    }
    return type && data ? {type, data: JSON.parse(data)} : null;
  }
}
```

---

## 23. API 版本管理

### 23.1 版本策略

ThesisMiner v8.0 采用语义化版本（Semantic Versioning）：

```
MAJOR.MINOR.PATCH
   8    .  0  .  0
```

- **MAJOR**：包含不兼容的 API 变更；
- **MINOR**：向后兼容的功能新增；
- **PATCH**：向后兼容的缺陷修复。

API 版本通过 URL 前缀标识（规划中）：

- 当前：`/api/...`（默认 v8）
- 未来：`/api/v8/...`、`/api/v9/...`

在 v8 生命周期内，所有端点保持向后兼容，不引入破坏性变更。

### 23.2 向后兼容

**兼容性保证**：

1. 已有端点路径不会变更；
2. 已有请求字段不会移除；
3. 已有响应字段不会移除（可能新增）；
4. 已有错误码不会重定义；
5. 已有事件类型语义不会改变。

**新增兼容**：

1. 可能新增端点；
2. 可能新增可选请求字段；
3. 可能新增响应字段（客户端应忽略未知字段）；
4. 可能新增错误码；
5. 可能新增事件类型。

**字段废弃流程**：

```
┌────────────────┐    ┌────────────────┐    ┌────────────────┐
│  标记 deprecated│ →  │  文档警告       │ →  │  返回警告头     │
│  (v8.1)        │    │  (v8.1-v8.x)   │    │  X-Deprecated  │
└────────────────┘    └────────────────┘    └────────────────┘
                                                       │
                                                       ▼
                            ┌────────────────┐    ┌────────────────┐
                            │  移除字段       │ ←  │  主版本升级     │
                            │  (v9.0)        │    │  (v9.0)        │
                            └────────────────┘    └────────────────┘
```

### 23.3 废弃流程

当某个端点或字段需要废弃时，将经历以下阶段：

**阶段 1：标记废弃（当前版本）**

- 在文档中标注 `deprecated`；
- 在响应头中返回 `X-Deprecated: true` 与 `X-Deprecation-Date: 2026-12-31`；
- 在响应体中新增 `warnings` 字段：

```json
{
  "success": true,
  "data": {...},
  "warnings": [
    {
      "code": "DEPRECATED_FIELD",
      "message": "字段 'agent_hint' 已废弃，请使用 'agent' 代替",
      "deprecated_since": "8.1.0",
      "removal_version": "9.0.0"
    }
  ]
}
```

**阶段 2：日志警告（下一版本）**

- 在服务端日志中记录废弃字段的使用情况；
- 在响应头中返回 `Sunset: 2026-12-31`。

**阶段 3：移除（主版本升级）**

- 在下一个主版本中移除废弃字段；
- 移除前至少提前 6 个月公告。

---

## 24. 最佳实践

### 24.1 会话生命周期管理

**推荐流程**：

```
创建会话 → 创建对话 → 发送消息 → 触发生成 → 查询结果 → 归档会话
   │           │           │           │           │           │
   ▼           ▼           ▼           ▼           ▼           ▼
 POST       POST        POST        POST        GET       PATCH
/sessions  /conversations /messages  /proposals  /proposals  /sessions
                          /generate  /{id}        /{id}
```

**注意事项**：

1. 一个会话建议承载一次完整的论题探索，避免在同一会话中混合多个不相关主题；
2. 长时间不活跃的会话应主动归档（`PATCH` 状态为 `archived`），释放上下文资源；
3. 删除会话前应导出谱系与引用，避免数据丢失；
4. 单会话对话数建议不超过 20 个，避免上下文膨胀导致缓存命中率下降。

**会话状态机**：

```
┌──────────┐  create   ┌────────┐  archive  ┌──────────┐
│  (none)  │ ────────▶ │ active │ ────────▶ │ archived │
└──────────┘           └────┬───┘           └──────────┘
                            │ │
                    pause   │ │ resume
                            ▼ │
                       ┌────────┐
                       │ paused │
                       └────────┘
```

### 24.2 流式响应消费

**推荐模式**：

1. 优先使用 SSE 流式接口，提供更好的用户体验；
2. 对长文本生成（如开题报告）必须使用流式，避免长时间无响应；
3. 客户端应实现增量渲染，避免等待完整响应；
4. 流式过程中应展示进度（阶段切换、Agent 思考）。

**错误恢复**：

当 SSE 连接中断时，应：

1. 记录已接收的 `message_id` 与 `delta` 偏移；
2. 重新建立连接，使用 `Last-Event-ID` 头恢复；
3. 若服务端不支持断点续传，重新发起完整请求。

```javascript
eventSource.addEventListener('open', () => {
  console.log('SSE 连接已建立');
});

eventSource.addEventListener('error', (e) => {
  if (e.target.readyState === EventSource.CONNECTING) {
    console.log('正在重连...');
  } else if (e.target.readyState === EventSource.CLOSED) {
    console.log('连接已关闭，需手动重连');
    setTimeout(() => startGeneration(sessionId), 5000);
  }
});
```

### 24.3 错误恢复

**分层错误处理**：

```
┌─────────────────────────────────────────────┐
│  UI 层：展示友好错误提示，提供重试按钮         │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  业务层：判断错误类型，决定重试或降级         │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  传输层：指数退避重试，处理网络抖动           │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  API 层：返回标准错误结构，携带错误码         │
└─────────────────────────────────────────────┘
```

**降级策略**：

当主模型不可用时，可降级到备选模型：

```python
def call_with_fallback(client, session_id, content):
    """带降级的调用封装。"""
    models = ["claude-sonnet-4.5", "gpt-4.1", "deepseek-v3.2"]
    for model in models:
        try:
            return client.send_message(
                session_id=session_id,
                content=content,
                agent_hint="reasoner",
                model_override=model
            )
        except ModelUnavailableError:
            continue
    raise Exception("所有模型均不可用")
```

### 24.4 性能调优

**客户端优化**：

1. 使用 HTTP/2 连接复用，减少握手开销；
2. 对列表查询启用客户端缓存，设置合理的 TTL；
3. 批量操作时使用并发请求，但不超过速率限制；
4. 流式响应使用增量解析，避免缓冲完整响应。

**服务端优化**：

1. 启用 SQLite WAL 模式，提升并发读性能；
2. 定期执行 `VACUUM` 与 `ANALYZE`，优化查询计划；
3. 监控缓存命中率，确保 DeepSeek 缓存稳定生效；
4. 对热点会话的预算查询建立索引。

**性能指标**：

| 指标 | 目标值 | 监控方式 |
|------|--------|---------|
| API P99 延迟 | < 500ms（非生成类） | APM |
| 缓存命中率 | ≥ 95% | `/api/cache-stats` |
| SSE 首字节延迟 | < 2s | 客户端埋点 |
| 生成任务完成率 | ≥ 98% | `/api/proposals/{id}` |
| 错误率 | < 1% | 日志统计 |

---

## 25. 附录

### 25.1 状态码速查

| HTTP 状态码 | 含义 | 典型场景 |
|------------|------|---------|
| 200 | OK | 成功响应 |
| 201 | Created | 资源创建成功 |
| 204 | No Content | 删除成功 |
| 400 | Bad Request | 参数校验失败 |
| 401 | Unauthorized | 未认证 |
| 402 | Payment Required | 预算超限 |
| 403 | Forbidden | 权限不足 |
| 404 | Not Found | 资源不存在 |
| 409 | Conflict | 状态冲突 |
| 422 | Unprocessable Entity | Pydantic 校验失败 |
| 429 | Too Many Requests | 触发限流 |
| 500 | Internal Server Error | 内部错误 |
| 502 | Bad Gateway | 上游模型错误 |
| 503 | Service Unavailable | 服务不可用 |
| 504 | Gateway Timeout | Agent 超时 |

### 25.2 错误码速查

| code | HTTP | 可重试 |
|------|------|--------|
| `AUTH_INVALID_KEY` | 401 | 否 |
| `AUTH_MISSING_KEY` | 401 | 否 |
| `AUTH_PERMISSION_DENIED` | 403 | 否 |
| `VALIDATION_ERROR` | 400 | 否 |
| `RESOURCE_NOT_FOUND` | 404 | 否 |
| `SESSION_NOT_FOUND` | 404 | 否 |
| `CONVERSATION_NOT_FOUND` | 404 | 否 |
| `MESSAGE_NOT_FOUND` | 404 | 否 |
| `STATE_CONFLICT` | 409 | 否 |
| `RATE_LIMIT_EXCEEDED` | 429 | 是 |
| `BUDGET_EXCEEDED` | 402 | 否 |
| `AGENT_TIMEOUT` | 504 | 是 |
| `AGENT_FAILURE` | 500 | 是 |
| `MODEL_UNAVAILABLE` | 503 | 是 |
| `MODEL_RATE_LIMITED` | 429 | 是 |
| `INTERNAL_ERROR` | 500 | 是 |

### 25.3 事件类型速查

| 事件类型 | 方向 | 说明 |
|---------|------|------|
| `stage_change` | SSE/WS | 五阶段切换 |
| `agent_start` | SSE/WS | Agent 开始执行 |
| `agent_thinking` | SSE/WS | Agent 思考过程 |
| `agent_message` | SSE/WS | Agent 输出片段 |
| `agent_tool_call` | SSE/WS | Agent 工具调用 |
| `agent_complete` | SSE/WS | Agent 执行完成 |
| `citation` | SSE/WS | 引用产生 |
| `cache_hit` | SSE | 缓存命中 |
| `cache_miss` | SSE | 缓存未命中 |
| `progress` | SSE/WS | 进度更新 |
| `error` | SSE/WS | 错误发生 |
| `done` | SSE/WS | 整体完成 |
| `hello` | WS | 连接建立 |
| `subscribed` | WS | 订阅成功 |
| `pong` | WS | 心跳响应 |

### 25.4 变更日志

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| 8.0.0 | 2026-06-20 | 初始版本，支持全部 API、SSE、WebSocket |
| 8.0.1 | 2026-06-25 | 修复 SSE 重连后事件丢失问题 |
| 8.1.0 | 2026-07-01 | 新增 `/api/agents/{id}/model` 端点，支持运行时切换模型 |
| 8.1.1 | 2026-07-10 | 优化缓存统计聚合查询性能 |
| 8.2.0 | 2026-07-20 | 新增预算告警 Webhook 回调 |

---

## 参考资源

- **项目仓库**：ThesisMiner v8.0 源代码
- **入门教程**：`docs/tutorials/getting_started.md`
- **开发者指南**：`docs/tutorials/developer_guide.md`
- **模型配置指南**：`docs/tutorials/model_configuration_guide.md`
- **高级特性**：`docs/tutorials/advanced_features.md`
- **管理指南**：`docs/tutorials/admin_guide.md`
- **错误码参考**：`docs/api/error_codes.md`

---

## 反馈与支持

- **问题反馈**：通过 GitHub Issues 提交问题
- **功能建议**：通过 GitHub Discussions 讨论
- **安全漏洞**：通过私有渠道报告安全问题
- **文档错误**：直接提交 PR 修正

---

> 本教程由 ThesisMiner Core Team 维护，最后更新于 2026-06-20。如需了解最新变更，请参阅变更日志或项目仓库的 commit 历史。