# ThesisMiner v8.0 数据流架构文档

> **文档版本**：v8.0
> **最后更新**：2026-06-19
> **适用版本**：ThesisMiner v8.0
> **文档类型**：数据流架构设计文档
> **目标读者**：后端工程师、架构师、性能工程师、SRE
> **维护者**：ThesisMiner 核心团队

---

## 目录

1. [文档概述](#1-文档概述)
2. [数据流总体架构](#2-数据流总体架构)
3. [用户请求入口数据流](#3-用户请求入口数据流)
4. [路由层分发数据流](#4-路由层分发数据流)
5. [Orchestrator 编排数据流](#5-orchestrator-编排数据流)
6. [子 Agent 调度数据流](#6-子-agent-调度数据流)
7. [AI Proxy 转发数据流](#7-ai-proxy-转发数据流)
8. [LLM 调用与响应数据流](#8-llm-调用与响应数据流)
9. [响应解析数据流](#9-响应解析数据流)
10. [引用解析数据流](#10-引用解析数据流)
11. [流式输出数据流](#11-流式输出数据流)
12. [前端渲染数据流](#12-前端渲染数据流)
13. [五阶段数据流详解](#13-五阶段数据流详解)
14. [信息确权阶段数据流](#14-信息确权阶段数据流)
15. [创意阶段数据流](#15-创意阶段数据流)
16. [校验阶段数据流](#16-校验阶段数据流)
17. [生成阶段数据流](#17-生成阶段数据流)
18. [深度辅助阶段数据流](#18-深度辅助阶段数据流)
19. [多对话上下文隔离数据流](#19-多对话上下文隔离数据流)
20. [DST 压缩算法数据流](#20-dst-压缩算法数据流)
21. [缓存命中数据流](#21-缓存命中数据流)
22. [错误处理数据流](#22-错误处理数据流)
23. [重试机制数据流](#23-重试机制数据流)
24. [降级策略数据流](#24-降级策略数据流)
25. [性能关键路径分析](#25-性能关键路径分析)
26. [瓶颈识别与优化建议](#26-瓶颈识别与优化建议)
27. [数据流监控与可观测性](#27-数据流监控与可观测性)
28. [附录](#28-附录)

---

## 1. 文档概述

### 1.1 文档目的

本文档是 ThesisMiner v8.0 系统的**数据流架构权威文档**，全面、深入地描述系统中所有数据流的流转过程、状态变更、转换规则与异常处理路径。文档面向以下场景：

- **架构评审**：新功能开发前的数据流影响评估
- **性能调优**：识别关键路径上的性能瓶颈
- **故障排查**：通过数据流追踪定位异常根因
- **新人培训**：理解系统端到端的工作机制
- **容量规划**：评估各数据流节点的资源消耗

### 1.2 数据流分类体系

ThesisMiner v8.0 系统中的数据流按照**业务维度**与**技术维度**双重分类：

#### 1.2.1 业务维度分类

| 数据流类别 | 核心场景 | 触发源 | 关键组件 | 平均耗时 |
|------------|----------|--------|----------|----------|
| 用户请求流 | HTTP 请求生命周期 | 前端用户操作 | FastAPI Router → Business Layer | 50-200ms |
| 多 Agent 编排流 | 论题生成编排 | OrchestratorAgent | StateMachine + Hooks + SubAgents | 5-30s |
| 会话管理流 | 多轮对话状态维护 | 用户消息 | SessionManager + DST + Compactor | 10-50ms |
| 引用解析流 | 谱系链接与图谱扩展 | 搜索结果返回 | CitationParser + GraphExpander | 100-500ms |
| 缓存优化流 | Prompt 缓存与 KV Cache | LLM 调用前 | CacheManager + SHA-256 Hash | 1-5ms |
| 错误处理流 | 异常传播与降级 | 任意节点异常 | Exception Handler + Fallback | 10-100ms |
| 预算控制流 | Token 消耗追踪 | 每次 LLM 调用 | BudgetLedger + Estimator | 5-20ms |
| 约束校验流 | 硬规则拦截 | 阶段门禁 | RuleEngine + HardRules | 5-30ms |

#### 1.2.2 技术维度分类

| 数据流类别 | 传输介质 | 序列化格式 | 同步/异步 | 典型数据量 |
|------------|----------|------------|-----------|------------|
| HTTP 请求流 | TCP Socket | JSON | 异步(async/await) | 1-50KB |
| 数据库 IO 流 | 文件系统 | SQLite Row | 同步 | 0.1-100KB |
| LLM 调用流 | HTTPS | JSON/SSE | 异步流式 | 2-32KB |
| 内存数据流 | 进程内内存 | Python 对象 | 同步 | 0.5-10MB |
| 前端渲染流 | WebSocket/SSE | JSON Chunk | 异步流式 | 1-100KB |

### 1.3 数据流设计原则

ThesisMiner v8.0 数据流设计遵循以下核心原则：

1. **单向数据流（Unidirectional Data Flow）**：数据从入口到出口单向流转，避免循环依赖
2. **不可变数据传递（Immutable Data Passing）**：阶段间传递的数据快照不可变，修改需创建新副本
3. **显式状态变更（Explicit State Mutation）**：所有状态变更通过状态机显式触发，可追溯
4. **故障隔离（Fault Isolation）**：单个数据流节点的故障不扩散到其他流
5. **可观测性（Observability）**：每个数据流节点均输出结构化日志与指标
6. **缓存优先（Cache First）**：所有可缓存的数据流节点优先查询缓存
7. **流式优先（Streaming First）**：长耗时数据流采用流式传输，降低首字节延迟

### 1.4 文档约定

#### 1.4.1 ASCII 图例说明

```
┌─────────────┐     方框表示系统组件/服务
│  Component  │
└─────────────┘

    ──────▶    实线箭头表示同步调用
    ══════▶    双线箭头表示异步流式调用
    ─ ─ ─ ▶    虚线箭头表示可选/异常路径
    ◀══════    反向双线表示响应回流

┌─────────────┐
│   Cache     │ ⚡  闪电符号表示缓存节点
└─────────────┘
```

#### 1.4.2 数据结构表示约定

```python
# 数据包结构示例
DataPacket = {
    "trace_id": "uuid-v4",          # 全链路追踪 ID
    "session_id": "session-xxx",    # 会话 ID
    "conversation_id": "conv-xxx",  # 对话 ID
    "stage": "info_confirm",        # 当前阶段
    "payload": {...},               # 业务数据
    "metadata": {                   # 元数据
        "timestamp": "ISO-8601",
        "source": "frontend",
        "version": "8.0"
    }
}
```

### 1.5 术语表

| 术语 | 英文 | 含义 |
|------|------|------|
| 数据流 | Data Flow | 数据在系统组件间的流转路径 |
| 状态机 | State Machine | 管理阶段转换的有限状态自动机 |
| 编排 | Orchestration | 协调多个组件完成复杂任务 |
| 钩子 | Hook | 在特定时机执行的可插拔逻辑 |
| 门禁 | Gate | 阶段推进前的校验检查点 |
| 降级 | Fallback | 异常时切换到备选方案 |
| 流式 | Streaming | 分块传输而非一次性返回 |
| 缓存命中 | Cache Hit | 请求的数据在缓存中找到 |
| 前缀哈希 | Prefix Hash | 不可变 Prompt 前缀的 SHA-256 值 |
| DST | Dialogue State Tracker | 对话状态追踪器 |

---

## 2. 数据流总体架构

### 2.1 系统级数据流全景图

以下是 ThesisMiner v8.0 系统的端到端数据流全景图，展示了从用户操作到最终渲染的完整数据流转路径：

```
                          ┌─────────────────────────────────────────────────────────┐
                          │                    用户浏览器 (Frontend)                  │
                          │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
                          │  │ Dashboard│  │ Sessions │  │ Generate │  │Lineage │ │
                          │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └───┬────┘ │
                          │       └─────────────┴─────────────┴─────────────┘      │
                          │                           │                             │
                          │                  ┌────────▼────────┐                    │
                          │                  │  api.js (Fetch) │                    │
                          │                  └────────┬────────┘                    │
                          └───────────────────────────┼─────────────────────────────┘
                                                       │ HTTP/SSE
                                                       ▼
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              FastAPI Backend (Uvicorn)                                │
│                                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                          路由层 (Routes Layer)                                │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐         │   │
│  │  │ sessions │ │conversa- │ │proposals │ │ lineage  │ │ budgets  │  ...    │   │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘         │   │
│  │       └─────────────┴─────────────┴─────────────┴───────────┘               │   │
│  └───────────────────────────────────┼─────────────────────────────────────────┘   │
│                                      │                                              │
│  ┌───────────────────────────────────▼─────────────────────────────────────────┐   │
│  │                       业务编排层 (Orchestration Layer)                       │   │
│  │  ┌──────────────────────────────────────────────────────────────────────┐  │   │
│  │  │                  OrchestratorAgent (主管理 Agent)                     │  │   │
│  │  │  ┌─────────────┐  ┌──────────────────┐  ┌──────────────────────┐   │  │   │
│  │  │  │ StateMachine│  │ Pipeline Executor│  │  Hook Registry       │   │  │   │
│  │  │  └─────────────┘  └──────────────────┘  └──────────────────────┘   │  │   │
│  │  └──────────────────────────────────────────────────────────────────────┘  │   │
│  │  ┌───────────┬───────────┬───────────┬───────────┬───────────┐            │   │
│  │  ▼           ▼           ▼           ▼           ▼           ▼            │   │
│  │ ┌─────┐   ┌─────┐   ┌─────┐   ┌─────┐   ┌─────┐                          │   │
│  │ │Sear-│   │Reas-│   │Crit-│   │Men- │   │Wri- │                          │   │
│  │ │cher │   │oner │   │ic   │   │tor  │   │ter  │                          │   │
│  │ └──┬──┘   └──┬──┘   └──┬──┘   └──┬──┘   └──┬──┘                          │   │
│  └────┼─────────┼──────────┼──────────┼──────────┼──────────────────────────┘   │
│       │         │          │          │          │                               │
│  ┌────▼─────────▼──────────▼──────────▼──────────▼─────────────────────────┐   │
│  │                          AI Proxy 层 (AI Layer)                          │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │   │
│  │  │ PromptCache  │  │  AIProxy     │  │ResponseParser│  │ Streaming  │ │   │
│  │  │  (三段式)    │  │  (HTTP调用)  │  │  (JSON解析)  │  │  (SSE)     │ │   │
│  │  └──────────────┘  └──────┬───────┘  └──────────────┘  └────────────┘ │   │
│  └───────────────────────────┼────────────────────────────────────────────┘   │
│  ┌───────────────────────────▼────────────────────────────────────────────┐   │
│  │                       基础设施层 (Infrastructure)                        │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐             │   │
│  │  │ SQLite   │  │  Logger  │  │  Cache   │  │ Budget   │             │   │
│  │  │ (WAL)    │  │  (JSON)  │  │ (Memory) │  │ Ledger   │             │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘             │   │
│  └────────────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────┼──────────────────────────────────────────┘
                                     │ HTTPS
                                     ▼
                    ┌────────────────────────────────┐
                    │     DeepSeek API (外部 LLM)     │
                    │   ┌──────────────────────────┐ │
                    │   │   KV Cache (Prefix Cache)│ │
                    │   └──────────────────────────┘ │
                    └────────────────────────────────┘
```

### 2.2 数据流分层模型

ThesisMiner v8.0 采用**五层数据流架构**，每层有明确的职责边界与数据契约：

#### 2.2.1 表现层（Presentation Layer）

```
┌─────────────────────────────────────────────────────────┐
│                    表现层 (Frontend)                     │
│                                                         │
│  职责：                                                  │
│  • 接收用户输入，构造 HTTP 请求                          │
│  • 渲染服务端响应为可视化界面                            │
│  • 处理 SSE 流式数据，增量渲染                           │
│  • 管理前端状态（会话列表、对话历史、谱系图）            │
│                                                         │
│  数据格式：JSON / SSE Chunk                              │
│  传输协议：HTTP/1.1 (keep-alive) / SSE                  │
│  关键文件：frontend/scripts/api.js, app.js, pages/*.js  │
└─────────────────────────────────────────────────────────┘
```

#### 2.2.2 接入层（Access Layer）

```
┌─────────────────────────────────────────────────────────┐
│                    接入层 (Routes)                       │
│                                                         │
│  职责：                                                  │
│  • HTTP 请求路由分发                                    │
│  • 请求参数校验（Pydantic Model）                       │
│  • 身份认证与鉴权（预留接口）                            │
│  • 请求日志记录与链路追踪 ID 注入                       │
│  • 响应序列化与 HTTP 状态码映射                         │
│                                                         │
│  数据格式：HTTP Request → Pydantic Model → JSON Response│
│  关键文件：backend/routes/*.py                          │
└─────────────────────────────────────────────────────────┘
```

#### 2.2.3 编排层（Orchestration Layer）

```
┌─────────────────────────────────────────────────────────┐
│                  编排层 (Orchestration)                  │
│                                                         │
│  职责：                                                  │
│  • 五阶段状态机驱动                                     │
│  • 子 Agent 任务分解与调度                              │
│  • 阶段间门禁控制（硬规则校验）                         │
│  • 上下文管理与 DST 压缩                                │
│  • 错误处理与降级策略                                   │
│                                                         │
│  关键组件：                                             │
│  • OrchestratorAgent: 主管理 Agent                      │
│  • OrchestrationStateMachine: 状态机                    │
│  • Pipeline: 管道执行器                                 │
│  • HookRegistry: 钩子注册表                             │
│  • SessionManager: 会话管理                             │
│                                                         │
│  关键文件：backend/agents/orchestrator.py,              │
│           backend/orchestration/*.py                    │
└─────────────────────────────────────────────────────────┘
```

#### 2.2.4 能力层（Capability Layer）

```
┌─────────────────────────────────────────────────────────┐
│                   能力层 (AI Proxy)                      │
│                                                         │
│  职责：                                                  │
│  • 三段式 Prompt 构建与缓存前缀计算                     │
│  • LLM API 调用（同步/流式）                            │
│  • 响应解析（JSON 提取、字段校验）                      │
│  • 引用解析（URL 提取、元数据获取）                     │
│  • Token 用量统计与预算扣减                             │
│  • 缓存命中监控                                         │
│                                                         │
│  关键组件：                                             │
│  • PromptCache: 三段式缓存构建器                        │
│  • AIProxy: LLM 调用代理                                │
│  • ResponseParser: 响应解析器                           │
│  • CitationParser: 引用解析器                           │
│  • StreamingHandler: 流式输出处理器                     │
│  • CacheMonitor: 缓存监控器                             │
│                                                         │
│  关键文件：backend/ai/*.py                              │
└─────────────────────────────────────────────────────────┘
```

#### 2.2.5 基础设施层（Infrastructure Layer）

```
┌─────────────────────────────────────────────────────────┐
│                 基础设施层 (Infrastructure)              │
│                                                         │
│  职责：                                                  │
│  • 数据持久化（SQLite WAL）                             │
│  • 日志记录（结构化 JSON 日志）                         │
│  • 内存缓存（LRU/TTL）                                  │
│  • 配置管理（YAML 配置文件）                            │
│  • 安全工具（输入校验、脱敏）                           │
│                                                         │
│  关键组件：                                             │
│  • database.py: SQLite 连接管理                         │
│  • logger.py: 日志记录器                                │
│  • cache.py: 内存缓存                                   │
│  • config.py: 配置加载                                  │
│  • security.py: 安全工具                                │
│                                                         │
│  关键文件：backend/database.py, backend/utils/*.py      │
└─────────────────────────────────────────────────────────┘
```

### 2.3 数据流核心契约

各层之间的数据流通过**显式契约**约束，确保层间解耦：

#### 2.3.1 表现层 ↔ 接入层契约

```python
# 请求契约（前端 → 后端）
class RequestContract:
    method: str                    # HTTP 方法
    path: str                      # 路由路径
    headers: dict                  # 请求头
    body: dict | None              # 请求体（JSON）
    query_params: dict             # 查询参数

# 响应契约（后端 → 前端）
class ResponseContract:
    status_code: int               # HTTP 状态码
    headers: dict                  # 响应头
    body: dict                     # 响应体（JSON）
    trace_id: str                  # 链路追踪 ID
```

#### 2.3.2 接入层 ↔ 编排层契约

```python
# 接入层调用编排层的标准接口
class OrchestrationRequest:
    session_id: str                # 会话 ID
    conversation_id: str           # 对话 ID
    user_input: str                # 用户输入
    context: dict                  # 上下文快照
    stage: str                     # 目标阶段

class OrchestrationResponse:
    success: bool                  # 是否成功
    stage: str                     # 完成的阶段
    data: dict                     # 业务数据
    error: str | None              # 错误信息
    metadata: dict                 # 元数据（耗时、token 用量等）
```

#### 2.3.3 编排层 ↔ 能力层契约

```python
# Agent 调用 AI Proxy 的标准接口
class AIRequest:
    agent_id: str                  # 调用方 Agent ID
    system_prompt: str             # 系统提示词
    user_prompt: str               # 用户提示词
    model_id: str                  # 目标模型
    temperature: float             # 采样温度
    max_tokens: int                # 最大生成 token 数
    stream: bool                   # 是否流式
    cache_prefix_hash: str         # 缓存前缀哈希

class AIResponse:
    content: str                   # 生成内容
    reasoning: str | None          # 思维链内容
    citations: list[dict]          # 引用列表
    token_usage: dict              # token 用量
    cache_hit: bool                # 是否命中缓存
    latency_ms: int                # 调用耗时
```

### 2.4 数据流时序总览

以下是典型用户请求的端到端时序图，展示各层交互的时间维度：

```
用户      前端      路由层    Orchestrator   子Agent    AIProxy    LLM API    SQLite
 │         │          │           │            │          │          │          │
 │  操作   │          │           │            │          │          │          │
 ├────────▶│          │           │            │          │          │          │
 │         │  POST    │           │            │          │          │          │
 │         ├─────────▶│           │            │          │          │          │
 │         │          │  调用     │            │          │          │          │
 │         │          ├──────────▶│            │          │          │          │
 │         │          │           │  查询会话  │          │          │          │
 │         │          │           │ ─────────────────────────────────────────▶  │
 │         │          │           │  ◀───────────────────────────────────────── │
 │         │          │           │  调度      │          │          │          │
 │         │          │           ├───────────▶│          │          │          │
 │         │          │           │            │  调用    │          │          │
 │         │          │           │            ├─────────▶│          │          │
 │         │          │           │            │          │  HTTPS   │          │
 │         │          │           │            │          ├─────────▶│          │
 │         │          │           │            │          │  ◀══════ │          │
 │         │          │           │            │  ◀══════ │          │          │
 │         │          │           │            │  解析    │          │          │
 │         │          │           │            │ ◀────────│          │          │
 │         │          │           │  ◀════════ │          │          │          │
 │         │          │           │  持久化    │          │          │          │
 │         │          │           │ ─────────────────────────────────────────▶  │
 │         │          │           │  ◀───────────────────────────────────────── │
 │         │          │  ◀════════│            │          │          │          │
 │         │  ◀══════│            │            │          │          │          │
 │  ◀══════│          │           │            │          │          │          │

时间轴：─── 同步调用    ═══ 流式响应回流
```

### 2.5 数据流版本演进

ThesisMiner 数据流架构在不同版本的演进历程：

| 版本 | 关键变化 | 数据流影响 |
|------|----------|------------|
| v1.0 | 单 Agent 架构 | 简单的请求-响应流 |
| v3.0 | 引入 Reasoner/Mentor 双 Agent | 增加 Agent 间通信流 |
| v5.0 | 引入 Pipeline 管道 | 阶段化数据流 |
| v7.0 | 引入状态机 | 显式状态转换流 |
| v8.0 | 五阶段闭环 + 三段式缓存 | 多对话隔离 + 缓存优化流 |

---

## 3. 用户请求入口数据流

### 3.1 请求入口概述

用户请求入口数据流是所有业务数据流的起点，负责接收前端浏览器的 HTTP 请求，完成初步校验后转发至路由层。该数据流的设计目标是**低延迟、高吞吐、可观测**。

### 3.2 请求入口数据流图

```
┌────────────┐     ┌─────────────────┐     ┌──────────────┐     ┌────────────┐
│  用户浏览器 │     │   Uvicorn ASGI  │     │  FastAPI App │     │ Middleware │
│  (Fetch API)│────▶│   Server        │────▶│  (lifespan)  │────▶│  Stack     │
└────────────┘     └─────────────────┘     └──────────────┘     └─────┬──────┘
                                                                        │
                                                                        ▼
                                                                  ┌──────────┐
                                                                  │  Router  │
                                                                  │ Dispatch │
                                                                  └──────────┘
```

### 3.3 请求入口详细流程

#### 3.3.1 Uvicorn ASGI 接收阶段

Uvicorn 作为 ASGI 服务器，负责接收底层 TCP 连接并解析 HTTP 协议：

```python
# main.py 启动入口
import uvicorn
from backend.config import get_config

if __name__ == "__main__":
    config = get_config()
    uvicorn.run(
        "backend.main:app",
        host=config.host,           # 默认 0.0.0.0
        port=config.port,           # 默认 8000
        reload=config.debug,        # 开发模式热重载
        log_level=config.log_level, # 日志级别
        workers=config.workers,     # 工作进程数
    )
```

**数据流转换**：

| 输入 | 处理 | 输出 |
|------|------|------|
| TCP 字节流 | HTTP 协议解析 | ASGI Scope 字典 |
| HTTP Headers | 提取 Content-Type | 决定 Body 解析方式 |
| HTTP Body | JSON 反序列化 | Python dict |

**ASGI Scope 数据结构**：

```python
scope = {
    "type": "http",
    "asgi": {"version": "3.0"},
    "http_version": "1.1",
    "method": "POST",
    "scheme": "http",
    "path": "/api/sessions",
    "query_string": b"",
    "headers": [
        (b"host", b"localhost:8000"),
        (b"content-type", b"application/json"),
        (b"authorization", b"Bearer xxx"),
    ],
    "client": ("127.0.0.1", 12345),
    "server": ("0.0.0.0", 8000),
}
```

#### 3.3.2 FastAPI 应用 lifespan 阶段

FastAPI 应用通过 `lifespan` 上下文管理器在启动时初始化全局资源：

```python
# backend/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from backend.database import init_db
from backend.agents.agent_registry import init_agents

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理

    启动时执行：
    1. 初始化数据库（建表、迁移）
    2. 注册所有 Agent
    3. 预热 Prompt 缓存
    4. 加载配置文件

    关闭时执行：
    1. 刷新日志缓冲
    2. 关闭数据库连接池
    3. 释放缓存资源
    """
    # ===== 启动阶段 =====
    logger.info("ThesisMiner v8.0 启动中...")

    # 1. 数据库初始化
    init_db()
    logger.info("数据库初始化完成")

    # 2. Agent 注册
    init_agents()
    logger.info("Agent 注册完成")

    # 3. 缓存预热
    await warmup_cache()
    logger.info("Prompt 缓存预热完成")

    # 4. 配置加载
    config = get_config()
    logger.info(f"配置加载完成: {config.env}")

    yield  # 应用运行期间

    # ===== 关闭阶段 =====
    logger.info("ThesisMiner v8.0 关闭中...")

app = FastAPI(
    title="ThesisMiner",
    version="8.0.0",
    lifespan=lifespan,
)
```

**lifespan 数据流**：

```
应用启动
    │
    ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  init_db()   │────▶│ init_agents()│────▶│warmup_cache()│────▶│ load_config()│
│              │     │              │     │              │     │              │
│ • CREATE TABLE│    │ • 注册 6 个  │     │ • 预构建基础 │     │ • 加载 YAML │
│ • ALTER TABLE│     │   Agent 实例 │     │   Prompt 前缀│     │ • 合并环境变量│
│ • 索引创建   │     │ • 注入依赖   │     │ • 计算 SHA   │     │ • 校验必填项 │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
    │                      │                    │                    │
    └──────────────────────┴────────────────────┴────────────────────┘
                                        │
                                        ▼
                                ┌──────────────┐
                                │  yield 运行  │
                                │  (处理请求)  │
                                └──────────────┘
                                        │
                                        ▼
                                ┌──────────────┐
                                │  清理资源    │
                                └──────────────┘
```

#### 3.3.3 中间件栈处理阶段

FastAPI 中间件栈按**洋葱模型**处理请求，从外到内执行请求预处理，从内到外执行响应后处理：

```python
# 中间件栈结构（从外到内）
@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    """链路追踪 ID 注入中间件（最外层）"""
    trace_id = request.headers.get("X-Trace-Id") or str(uuid.uuid4())
    request.state.trace_id = trace_id
    response = await call_next(request)
    response.headers["X-Trace-Id"] = trace_id
    return response

@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """请求日志中间件"""
    start_time = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000
    logger.info({
        "trace_id": request.state.trace_id,
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "duration_ms": round(duration_ms, 2),
    })
    return response

@app.middleware("http")
async def error_handler_middleware(request: Request, call_next):
    """全局异常处理中间件（最内层）"""
    try:
        return await call_next(request)
    except Exception as e:
        logger.exception({
            "trace_id": request.state.trace_id,
            "error": str(e),
            "type": type(e).__name__,
        })
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "trace_id": request.state.trace_id,
                "message": str(e),
            }
        )
```

**中间件洋葱模型数据流**：

```
请求进入
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  trace_id_middleware (外层)                                  │
│  • 生成/提取 trace_id                                       │
│  • 注入 request.state                                       │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  logging_middleware (中层)                              │ │
│  │  • 记录请求开始时间                                     │ │
│  │  ┌─────────────────────────────────────────────────┐ │ │
│  │  │  error_handler_middleware (内层)                 │ │ │
│  │  │  • try/except 包裹                              │ │ │
│  │  │  ┌─────────────────────────────────────────┐    │ │ │
│  │  │  │           路由处理函数                    │    │ │ │
│  │  │  │           (业务逻辑)                     │    │ │ │
│  │  │  └─────────────────────────────────────────┘    │ │ │
│  │  │  • 异常时返回 500                               │ │ │
│  │  └─────────────────────────────────────────────────┘ │ │
│  │  • 记录响应耗时                                       │ │
│  └───────────────────────────────────────────────────────┘ │
│  • 响应头注入 trace_id                                      │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
响应返回
```

### 3.4 请求入口数据包结构

请求经过入口数据流后，形成标准化的请求数据包：

```python
# 标准化请求数据包
class IncomingRequest:
    """经过入口处理后的标准化请求"""

    # ===== 元数据 =====
    trace_id: str                    # 链路追踪 ID
    received_at: str                 # 接收时间（ISO-8601）
    client_ip: str                   # 客户端 IP

    # ===== HTTP 信息 =====
    method: str                      # HTTP 方法
    path: str                        # 请求路径
    query_params: dict               # 查询参数
    headers: dict                    # 请求头

    # ===== 业务数据 =====
    body: dict | None                # 请求体（已反序列化）

    # ===== 上下文 =====
    state: dict                      # 请求级状态（中间件共享）
```

### 3.5 请求入口性能指标

请求入口数据流的性能指标基线：

| 指标 | 目标值 | 告警阈值 | 测量方法 |
|------|--------|----------|----------|
| 入口处理延迟 | < 5ms | > 20ms | logging_middleware 记录 |
| 中间件栈开销 | < 2ms | > 10ms | trace_id 注入到路由前 |
| 异常捕获率 | 100% | < 99% | error_handler 统计 |
| trace_id 注入率 | 100% | < 100% | 响应头检查 |

### 3.6 请求入口安全检查

请求入口数据流还负责初步的安全检查：

```python
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """安全检查中间件

    数据流：
    1. 检查请求大小限制
    2. 检查 Content-Type
    3. 基础输入验证
    """
    # 1. 请求大小限制（防止 DoS）
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 10 * 1024 * 1024:  # 10MB
        return JSONResponse(
            status_code=413,
            content={"error": "Request too large"}
        )

    # 2. Content-Type 检查（POST/PUT 请求）
    if request.method in ("POST", "PUT", "PATCH"):
        content_type = request.headers.get("content-type", "")
        if "application/json" not in content_type:
            return JSONResponse(
                status_code=415,
                content={"error": "Unsupported Media Type"}
            )

    # 3. 路径安全检查（防止路径遍历）
    if ".." in request.url.path or "//" in request.url.path:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid path"}
        )

    return await call_next(request)
```

---

## 4. 路由层分发数据流

### 4.1 路由层概述

路由层是接入层的核心组件，负责将 HTTP 请求分发到对应的业务处理函数。ThesisMiner v8.0 采用**按业务域划分**的路由组织方式，每个业务域对应一个独立的路由模块。

### 4.2 路由层结构图

```
┌──────────────────────────────────────────────────────────────┐
│                      路由层 (Routes Layer)                    │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                    APIRouter 注册表                     │ │
│  │  prefix="/api"                                          │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────┐ │
│  │  sessions  │ │conversations│ │ proposals  │ │ lineage  │ │
│  │  .py       │ │  .py       │ │  .py       │ │  .py     │ │
│  │            │ │            │ │            │ │          │ │
│  │ • POST /   │ │ • POST /   │ │ • POST /   │ │ • GET /  │ │
│  │ • GET /    │ │ • GET /    │ │   generate │ │   nodes  │ │
│  │ • GET /{id}│ │ • GET /{id}│ │ • POST /   │ │ • POST / │ │
│  │ • DELETE / │ │ • DELETE / │ │   rewrite  │ │   import │ │
│  │ • PATCH /  │ │ • POST /   │ │            │ │ • GET /  │ │
│  │            │ │   {id}/msg │ │            │ │   edges  │ │
│  └────────────┘ └────────────┘ └────────────┘ └──────────┘ │
│                                                              │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────┐ │
│  │  budgets   │ │ citations  │ │  config    │ │constraints│ │
│  │  .py       │ │  .py       │ │  .py       │ │  .py     │ │
│  └────────────┘ └────────────┘ └────────────┘ └──────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### 4.3 路由分发数据流详解

#### 4.3.1 路由匹配阶段

FastAPI 使用 Starlette 的路由匹配器，基于**路径模式匹配**找到对应的处理函数：

```python
# backend/routes/sessions.py
from fastapi import APIRouter, Depends, HTTPException
from backend.models import SessionCreate, SessionResponse

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

@router.post("/", response_model=SessionResponse)
async def create_session(req: SessionCreate):
    """创建新会话

    数据流：
    1. 接收 SessionCreate 请求体（Pydantic 自动校验）
    2. 调用 SessionManager 创建会话
    3. 持久化到 SQLite
    4. 返回 SessionResponse
    """
    session = await session_manager.create_session(
        title=req.title,
        degree=req.degree,
        discipline=req.discipline,
        mentor_info=req.mentor_info,
        mode=req.mode,
    )
    return session
```

**路由匹配数据流**：

```
请求路径: POST /api/sessions
    │
    ▼
┌─────────────────────────┐
│  路由匹配器             │
│  • 遍历已注册路由       │
│  • 匹配路径模式         │
│  • 匹配 HTTP 方法       │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  依赖注入解析           │
│  • 解析路径参数         │
│  • 解析查询参数         │
│  • 解析请求体           │
│  • 解析 Header 依赖     │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Pydantic 校验          │
│  • 类型校验             │
│  • 约束校验（Field）    │
│  • 自定义验证器         │
└───────────┬─────────────┘
            │ 校验通过
            ▼
┌─────────────────────────┐
│  调用处理函数           │
│  • 执行业务逻辑         │
│  • 返回响应数据         │
└─────────────────────────┘
```

#### 4.3.2 Pydantic 参数校验数据流

Pydantic 模型在路由层完成请求参数的**类型校验**与**业务约束校验**：

```python
# backend/models.py 中的请求模型定义
class SessionCreate(BaseModel):
    """创建会话请求模型"""
    title: str = Field(..., min_length=1, max_length=200, description="会话标题")
    degree: DegreeType = Field(..., description="学位类型")
    discipline: DisciplineType = Field(..., description="学科类型")
    mentor_info: str = Field(..., min_length=1, max_length=2000, description="导师信息")
    mode: str = Field(default="quick", pattern="^(quick|deep)$", description="生成模式")
```

**校验数据流转换**：

| 输入 | 校验规则 | 失败处理 | 输出 |
|------|----------|----------|------|
| `title: ""` | min_length=1 | 422 Unprocessable Entity | `{"detail": [...]}` |
| `degree: "bachelor"` | 枚举校验 | 422 Unprocessable Entity | `{"detail": [...]}` |
| `mode: "invalid"` | pattern 正则 | 422 Unprocessable Entity | `{"detail": [...]}` |
| `title: "有效标题"` | 全部通过 | - | `SessionCreate` 实例 |

**校验失败响应结构**：

```json
{
  "detail": [
    {
      "loc": ["body", "title"],
      "msg": "ensure this value has at least 1 characters",
      "type": "value_error.any_str.min_length"
    },
    {
      "loc": ["body", "degree"],
      "msg": "value is not a valid enumeration member",
      "type": "type_error.enum"
    }
  ]
}
```

#### 4.3.3 路由处理函数调用数据流

路由处理函数是业务逻辑的入口，负责协调各业务模块完成请求处理：

```python
# backend/routes/conversations.py
@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    req: MessageCreateRequest,
    session_id: str = Depends(get_session_id),
):
    """发送对话消息

    数据流：
    1. 验证 conversation_id 存在性
    2. 加载会话上下文
    3. 调用 OrchestratorAgent 处理消息
    4. 流式返回响应
    """
    # 1. 验证对话存在
    conversation = await conversation_manager.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # 2. 加载上下文
    context = await context_manager.load_context(session_id, conversation_id)

    # 3. 调用 Orchestrator
    orchestrator = get_agent("orchestrator")

    # 4. 流式返回
    async def stream_generator():
        async for chunk in orchestrator.orchestrate(
            user_input=req.content,
            conversation_id=conversation_id,
            context=context,
        ):
            yield f"data: {json.dumps(chunk)}\n\n"

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
    )
```

### 4.4 路由层数据包流转

路由层处理完成后，数据包从 HTTP 请求转换为业务调用参数：

```
HTTP Request
    │
    ▼
┌─────────────────────────────────────┐
│  原始请求数据                       │
│  {                                  │
│    "method": "POST",                │
│    "path": "/api/sessions",         │
│    "body": {                        │
│      "title": "深度学习论题",        │
│      "degree": "master",            │
│      "discipline": "science_eng",   │
│      "mentor_info": "张教授...",    │
│      "mode": "deep"                 │
│    }                                │
│  }                                  │
└─────────────────┬───────────────────┘
                  │ Pydantic 校验
                  ▼
┌─────────────────────────────────────┐
│  SessionCreate 实例                 │
│  • title: "深度学习论题"             │
│  • degree: DegreeType.master        │
│  • discipline: DisciplineType.      │
│      science_engineering            │
│  • mentor_info: "张教授..."         │
│  • mode: "deep"                     │
└─────────────────┬───────────────────┘
                  │ 业务调用
                  ▼
┌─────────────────────────────────────┐
│  session_manager.create_session(    │
│    title="深度学习论题",             │
│    degree=DegreeType.master,        │
│    discipline=DisciplineType.       │
│        science_engineering,         │
│    mentor_info="张教授...",         │
│    mode="deep"                      │
│  )                                  │
└─────────────────────────────────────┘
```

### 4.5 路由层错误处理数据流

路由层的错误处理遵循**分层捕获**原则，不同层级的异常返回不同的 HTTP 状态码：

```python
# 错误处理数据流
class RouteErrorHandler:
    """路由层错误处理"""

    STATUS_MAP = {
        "ValidationError": 422,       # 参数校验失败
        "NotFoundError": 404,         # 资源不存在
        "ConflictError": 409,         # 资源冲突
        "AuthorizationError": 403,    # 无权限
        "RateLimitError": 429,        # 限流
        "BudgetExceededError": 402,   # 预算超限
        "LLMUnavailableError": 503,   # LLM 不可用
        "InternalError": 500,         # 内部错误
    }

    async def handle(self, error: Exception) -> JSONResponse:
        error_type = type(error).__name__
        status_code = self.STATUS_MAP.get(error_type, 500)

        return JSONResponse(
            status_code=status_code,
            content={
                "error": error_type,
                "message": str(error),
                "trace_id": get_current_trace_id(),
            }
        )
```

**错误处理数据流图**：

```
业务异常抛出
    │
    ▼
┌─────────────────────┐
│  异常类型判断       │
└─────────┬───────────┘
          │
    ┌─────┼─────┬─────┬─────┬─────┐
    ▼     ▼     ▼     ▼     ▼     ▼
  422   404   409   403   429   500
  参数  资源  冲突  权限  限流  内部
  错误  不存在            超限  错误
    │     │     │     │     │     │
    └─────┴─────┴─────┴─────┴─────┘
                  │
                  ▼
        ┌─────────────────┐
        │  JSONResponse   │
        │  {              │
        │    "error": "", │
        │    "message":"",│
        │    "trace_id":""│
        │  }              │
        └─────────────────┘
```

### 4.6 路由层完整端点清单

以下是 ThesisMiner v8.0 所有路由端点的完整清单：

| 模块 | 方法 | 路径 | 功能 | 请求体 | 响应 |
|------|------|------|------|--------|------|
| sessions | POST | /api/sessions | 创建会话 | SessionCreate | SessionResponse |
| sessions | GET | /api/sessions | 列出会话 | - | SessionResponse[] |
| sessions | GET | /api/sessions/{id} | 获取会话 | - | SessionResponse |
| sessions | DELETE | /api/sessions/{id} | 删除会话 | - | {deleted: bool} |
| sessions | PATCH | /api/sessions/{id} | 更新会话 | SessionUpdate | SessionResponse |
| conversations | POST | /api/conversations | 创建对话 | ConversationCreate | ConversationResponse |
| conversations | GET | /api/conversations | 列出对话 | - | ConversationResponse[] |
| conversations | GET | /api/conversations/{id} | 获取对话 | - | ConversationResponse |
| conversations | DELETE | /api/conversations/{id} | 删除对话 | - | {deleted: bool} |
| conversations | POST | /api/conversations/{id}/messages | 发送消息 | MessageCreate | SSE Stream |
| proposals | POST | /api/proposals/generate | 生成提案 | ProposalGenerateRequest | ProposalResponse |
| proposals | POST | /api/proposals/rewrite | 改写提案 | RewriteRequest | ProposalResponse |
| lineage | GET | /api/lineage/nodes | 列出节点 | - | NodeResponse[] |
| lineage | POST | /api/lineage/nodes | 创建节点 | NodeCreate | NodeResponse |
| lineage | POST | /api/lineage/import | 批量导入 | ImportRequest | {imported: int} |
| lineage | GET | /api/lineage/edges | 列出边 | - | EdgeResponse[] |
| budgets | GET | /api/budgets/summary | 预算汇总 | - | BudgetSummary |
| budgets | GET | /api/budgets/{session_id} | 会话预算 | - | BudgetDetail |
| citations | GET | /api/citations/{message_id} | 获取引用 | - | Citation[] |
| citations | POST | /api/citations/parse | 解析引用 | ParseRequest | Citation[] |
| config | GET | /api/config/models | 模型配置 | - | ModelConfig[] |
| config | GET | /api/config/system | 系统配置 | - | SystemConfig |
| config | PUT | /api/config/system | 更新配置 | SystemConfig | SystemConfig |
| constraints | GET | /api/constraints/rules | 约束规则 | - | Rule[] |
| constraints | POST | /api/constraints/check | 校验内容 | CheckRequest | CheckResult |

---

## 5. Orchestrator 编排数据流

### 5.1 Orchestrator 概述

OrchestratorAgent 是 ThesisMiner v8.0 的**核心编排组件**，采用 Claude Code 式的主管理架构。它维护五阶段状态机，按阶段调度子 Agent，控制阶段间门禁，并汇总各阶段结果返回给用户。

### 5.2 Orchestrator 数据流架构

```
┌──────────────────────────────────────────────────────────────────┐
│                    OrchestratorAgent 数据流                       │
│                                                                  │
│  ┌────────────┐                                                  │
│  │  请求入口  │ ◀──── 路由层调用                                 │
│  └──────┬─────┘                                                  │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              上下文加载 (Context Loading)                 │   │
│  │  • 加载 session 信息                                     │   │
│  │  • 加载 conversation 历史                                │   │
│  │  • 加载 DST 压缩状态                                     │   │
│  │  • 加载缓存前缀哈希                                      │   │
│  └──────────────────────┬───────────────────────────────────┘   │
│                         │                                        │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │            状态机决策 (State Machine)                     │   │
│  │  • 当前阶段: info_confirm                                │   │
│  │  • 触发事件: USER_CONFIRM                                 │   │
│  │  • 目标阶段: creativity                                   │   │
│  └──────────────────────┬───────────────────────────────────┘   │
│                         │                                        │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │            前置钩子执行 (Pre-Hooks)                       │   │
│  │  • pre_search: 预检索增强                                │   │
│  │  • hard_rule_interceptor: 硬规则拦截                     │   │
│  └──────────────────────┬───────────────────────────────────┘   │
│                         │                                        │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │            子 Agent 调度 (Sub-Agent Dispatch)             │   │
│  │  • 根据阶段选择 Agent                                    │   │
│  │  • 构建任务输入                                          │   │
│  │  • 调用 Agent.run() / Agent.stream()                     │   │
│  └──────────────────────┬───────────────────────────────────┘   │
│                         │                                        │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │            后置钩子执行 (Post-Hooks)                      │   │
│  │  • post_reasoner: 结果后处理                             │   │
│  │  • academic_feasibility_check: 可行性检查                 │   │
│  └──────────────────────┬───────────────────────────────────┘   │
│                         │                                        │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │            门禁校验 (Gate Check)                          │   │
│  │  • 评分是否达标?                                         │   │
│  │  • 硬约束是否满足?                                       │   │
│  │  • 是否需要回退?                                         │   │
│  └──────────────────────┬───────────────────────────────────┘   │
│                         │                                        │
│                ┌────────┴────────┐                               │
│                │                 │                               │
│             通过              不通过                              │
│                │                 │                               │
│                ▼                 ▼                               │
│  ┌──────────────────┐  ┌──────────────────┐                     │
│  │  状态推进        │  │  状态回退        │                     │
│  │  transition()    │  │  transition()    │                     │
│  │  → 下一阶段      │  │  → 上一阶段      │                     │
│  └────────┬─────────┘  └────────┬─────────┘                     │
│           │                     │                               │
│           └──────────┬──────────┘                               │
│                      │                                          │
│                      ▼                                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │            结果汇总与持久化                               │   │
│  │  • 保存消息到 conversation_messages                      │   │
│  │  • 更新 DST 状态                                         │   │
│  │  • 记录预算消耗                                          │   │
│  │  • 返回流式响应                                          │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### 5.3 Orchestrator 核心数据结构

```python
# OrchestratorAgent 内部状态
class OrchestratorState:
    """Orchestrator 运行时状态"""

    # ===== 会话级状态 =====
    session_id: str                          # 当前会话 ID
    conversation_id: str                     # 当前对话 ID
    current_stage: str                       # 当前阶段
    stage_results: dict[str, AgentResult]    # 各阶段结果缓存

    # ===== 上下文 =====
    context: OrchestrationContext            # 编排上下文
    dst_state: dict                          # DST 压缩状态
    cache_prefix_hash: str                   # 缓存前缀哈希

    # ===== 执行追踪 =====
    trace_id: str                            # 链路追踪 ID
    started_at: float                        # 开始时间戳
    stage_timings: dict[str, float]          # 各阶段耗时


# 编排上下文
@dataclass
class OrchestrationContext:
    """编排上下文（在阶段间传递）"""

    # ===== 用户输入 =====
    user_input: str                          # 用户原始输入
    degree: str                              # 学位层次
    discipline: str                          # 学科领域
    mentor_info: str                         # 导师信息

    # ===== 阶段产出 =====
    confirmed_info: dict | None              # 信息确权结果
    candidates: list[dict] | None            # 创意候选
    evaluation_result: dict | None           # 校验结果
    proposal: dict | None                    # 生成的提案
    deep_assist_result: dict | None          # 深度辅助结果

    # ===== 元数据 =====
    retry_count: int = 0                     # 当前阶段重试次数
    max_retries: int = 3                     # 最大重试次数
```

### 5.4 Orchestrator 编排流程详解

#### 5.4.1 orchestrate() 主流程

```python
# backend/agents/orchestrator.py
class OrchestratorAgent(BaseAgent):

    async def orchestrate(
        self,
        user_input: str,
        conversation_id: str,
        context: dict | None = None,
    ) -> AsyncGenerator[dict, None]:
        """编排主流程（流式生成器）

        数据流：
        1. 加载上下文与状态
        2. 根据当前阶段调度子 Agent
        3. 执行前置/后置钩子
        4. 门禁校验，决定推进或回退
        5. 流式产出阶段结果
        """
        # 1. 加载上下文
        ctx = await self._load_context(conversation_id, context)
        ctx.user_input = user_input

        # 2. 状态机循环
        while not self._is_complete(ctx):
            stage = ctx.current_stage

            # 2.1 执行前置钩子
            await self._run_pre_hooks(stage, ctx)

            # 2.2 调度子 Agent
            agent = self._select_agent(stage)
            async for chunk in agent.stream(ctx.to_agent_input()):
                # 2.3 流式转发 chunk
                yield {
                    "stage": stage.value,
                    "agent": agent.agent_id,
                    "chunk": chunk,
                    "trace_id": ctx.trace_id,
                }

            # 2.4 执行后置钩子
            await self._run_post_hooks(stage, ctx)

            # 2.5 门禁校验
            gate_result = self._check_gate(stage, ctx)
            if gate_result.passed:
                ctx.current_stage = self._next_stage(stage)
            else:
                if ctx.retry_count < ctx.max_retries:
                    ctx.current_stage = gate_result.fallback_stage
                    ctx.retry_count += 1
                else:
                    ctx.current_stage = self._next_stage(stage)

        # 3. 持久化最终结果
        await self._persist_result(ctx)
```

#### 5.4.2 上下文加载数据流

```python
async def _load_context(
    self,
    conversation_id: str,
    context_override: dict | None,
) -> OrchestrationContext:
    """加载编排上下文

    数据流：
    1. 从 DB 加载 conversation
    2. 从 DB 加载 session
    3. 从 DB 加载最近消息（DST 输入）
    4. 调用 DST Compactor 压缩历史
    5. 构建 OrchestrationContext
    """
    # 1. 加载对话
    conversation = await conversation_manager.get_conversation(conversation_id)

    # 2. 加载会话
    session = await session_manager.get_session(conversation["session_id"])

    # 3. 加载最近 N 条消息
    messages = await conversation_manager.get_messages(
        conversation_id, limit=20
    )

    # 4. DST 压缩
    dst_state = await dst_compactor.compress(messages)

    # 5. 构建上下文
    ctx = OrchestrationContext(
        user_input="",
        degree=session["degree"],
        discipline=session["discipline"],
        mentor_info=session["mentor_info"],
        dst_state=dst_state,
        cache_prefix_hash=session.get("cache_prefix_hash", ""),
        current_stage=Stage(conversation.get("current_stage", "info_confirm")),
    )

    # 6. 应用覆盖
    if context_override:
        for k, v in context_override.items():
            setattr(ctx, k, v)

    return ctx
```

**上下文加载数据流图**：

```
conversation_id
      │
      ▼
┌──────────────────┐
│ conversation =   │     ┌──────────────┐
│  get_conversation│────▶│  SQLite      │
│  (conv_id)       │◀────│  conversations│
└────────┬─────────┘     └──────────────┘
         │
         ▼
┌──────────────────┐
│ session =        │     ┌──────────────┐
│  get_session     │────▶│  SQLite      │
│  (sess_id)       │◀────│  sessions    │
└────────┬─────────┘     └──────────────┘
         │
         ▼
┌──────────────────┐
│ messages =       │     ┌──────────────┐
│  get_messages    │────▶│  SQLite      │
│  (conv_id, 20)   │◀────│  conv_msgs   │
└────────┬─────────┘     └──────────────┘
         │
         ▼
┌──────────────────┐
│ dst_state =      │
│  dst_compactor   │
│  .compress(msgs) │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ OrchestrationCtx │
│  • degree        │
│  • discipline    │
│  • mentor_info   │
│  • dst_state     │
│  • current_stage │
└──────────────────┘
```

### 5.5 状态机驱动数据流

Orchestrator 的核心是五阶段状态机，它定义了阶段间的合法转移规则：

```python
# backend/orchestration/state_machine.py
class Stage(str, Enum):
    """五阶段状态枚举"""
    INFO_CONFIRM = "info_confirm"      # 信息确权
    CREATIVITY = "creativity"          # 创意
    VALIDATION = "validation"          # 校验
    GENERATION = "generation"          # 生成
    DEEP_ASSIST = "deep_assist"        # 深度辅助


class Event(str, Enum):
    """状态机事件枚举"""
    START = "start"
    USER_CONFIRM = "user_confirm"
    CANDIDATES_GENERATED = "candidates_generated"
    EVALUATION_DONE = "evaluation_done"
    SCORE_PASS = "score_pass"
    SCORE_FAIL = "score_fail"
    GENERATION_DONE = "generation_done"
    ENTER_DEEP_ASSIST = "enter_deep_assist"
    RESET = "reset"


# 状态转移表
TRANSITIONS = {
    (Stage.INFO_CONFIRM, Event.USER_CONFIRM): Stage.CREATIVITY,
    (Stage.CREATIVITY, Event.CANDIDATES_GENERATED): Stage.VALIDATION,
    (Stage.VALIDATION, Event.SCORE_PASS): Stage.GENERATION,
    (Stage.VALIDATION, Event.SCORE_FAIL): Stage.CREATIVITY,  # 回退
    (Stage.GENERATION, Event.GENERATION_DONE): Stage.DEEP_ASSIST,
    (Stage.DEEP_ASSIST, Event.RESET): Stage.INFO_CONFIRM,
}
```

**状态机状态转换图**：

```
              ┌─────────────┐  USER_CONFIRM   ┌─────────────┐
              │ INFO_CONFIRM│──────────────▶│  CREATIVITY  │
              │             │                │             │
              └─────────────┘                └─────┬───────┘
                    ▲                              │
                    │ RESET                        │ CANDIDATES_GENERATED
                    │                              ▼
              ┌─────┴───────┐                ┌─────────────┐
              │ DEEP_ASSIST │                │ VALIDATION  │
              │             │                │             │
              └─────────────┘                └──────┬──────┘
                    ▲                              │
                    │ GENERATION_DONE             │ SCORE_PASS
                    │                              ▼
              ┌─────┴───────┐                ┌─────────────┐
              │ GENERATION  │◀───────────────│             │
              │             │                │             │
              └─────────────┘                └─────────────┘

              SCORE_FAIL 时 VALIDATION → CREATIVITY (回退)
```

### 5.6 钩子机制数据流

Orchestrator 通过钩子机制实现**可插拔**的前置/后置处理：

```python
# backend/orchestration/hooks/__init__.py
class HookRegistry:
    """钩子注册表"""

    def __init__(self):
        self.pre_hooks: dict[str, list[Hook]] = defaultdict(list)
        self.post_hooks: dict[str, list[Hook]] = defaultdict(list)

    def register_pre(self, stage: str, hook: Hook):
        """注册前置钩子"""
        self.pre_hooks[stage].append(hook)

    def register_post(self, stage: str, hook: Hook):
        """注册后置钩子"""
        self.post_hooks[stage].append(hook)

    async def run_pre_hooks(self, stage: str, ctx: OrchestrationContext):
        """执行前置钩子链"""
        for hook in self.pre_hooks.get(stage, []):
            await hook.run(ctx)
            if ctx.should_abort:
                break

    async def run_post_hooks(self, stage: str, ctx: OrchestrationContext):
        """执行后置钩子链"""
        for hook in self.post_hooks.get(stage, []):
            await hook.run(ctx)


# 已注册的钩子
hook_registry = HookRegistry()
hook_registry.register_pre("info_confirm", PreSearchHook())
hook_registry.register_pre("creativity", HardRuleInterceptorHook())
hook_registry.register_post("creativity", PostReasonerHook())
hook_registry.register_post("validation", AcademicFeasibilityCheckHook())
```

**钩子执行数据流**：

```
阶段开始
    │
    ▼
┌─────────────────────────────────────────┐
│         前置钩子链 (Pre-Hooks)           │
│  ┌───────────┐  ┌───────────┐  ┌─────┐ │
│  │ Hook 1    │─▶│ Hook 2    │─▶│ ... │ │
│  │ pre_search│  │hard_rule  │  │     │ │
│  └───────────┘  └───────────┘  └─────┘ │
│         │ should_abort?                 │
│    ┌────┴────┐                          │
│    │ Yes  No │                          │
│    └────┬────┘                          │
│         │ No                            │
└─────────┼───────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────┐
│         子 Agent 执行                    │
│  agent.stream(input)                    │
└─────────┬───────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────┐
│         后置钩子链 (Post-Hooks)          │
│  ┌───────────┐  ┌───────────┐  ┌─────┐ │
│  │ Hook 1    │─▶│ Hook 2    │─▶│ ... │ │
│  │post_reason│  │feasibility│  │     │ │
│  └───────────┘  └───────────┘  └─────┘ │
└─────────┬───────────────────────────────┘
          │
          ▼
       阶段结束
```

### 5.7 门禁校验数据流

门禁校验是阶段推进的关键决策点，决定流程是前进、回退还是终止：

```python
class GateChecker:
    """门禁校验器"""

    THRESHOLDS = {
        Stage.CREATIVITY: {
            "min_candidates": 1,
            "max_candidates": 5,
        },
        Stage.VALIDATION: {
            "min_score": 60,
            "required_dimensions": ["novelty", "feasibility", "norm"],
        },
        Stage.GENERATION: {
            "required_fields": ["title", "research_content"],
            "min_confidence": 0.5,
        },
    }

    def check(self, stage: Stage, ctx: OrchestrationContext) -> GateResult:
        """执行门禁校验"""
        thresholds = self.THRESHOLDS.get(stage, {})

        if stage == Stage.CREATIVITY:
            return self._check_creativity(ctx, thresholds)
        elif stage == Stage.VALIDATION:
            return self._check_validation(ctx, thresholds)
        elif stage == Stage.GENERATION:
            return self._check_generation(ctx, thresholds)
        else:
            return GateResult(passed=True)
```

---

## 6. 子 Agent 调度数据流

### 6.1 子 Agent 概述

ThesisMiner v8.0 包含 5 个专业子 Agent，每个 Agent 负责特定能力域：

| Agent | 标识 | 职责 | 调用阶段 | 模型 |
|-------|------|------|----------|------|
| SearcherAgent | `searcher` | 联网检索近 2 年文献 | info_confirm | deepseek-chat |
| ReasonerAgent | `reasoner` | 生成候选论题 | creativity | deepseek-reasoner |
| CriticAgent | `critic` | 评估新颖性与可行性 | validation | deepseek-chat |
| MentorAgent | `mentor` | 导师视角评审 | validation | deepseek-chat |
| WriterAgent | `writer` | 多粒度生成开题内容 | generation | deepseek-chat |

### 6.2 Agent 注册与发现数据流

```python
# backend/agents/agent_registry.py
class AgentRegistry:
    """Agent 注册表（单例）"""

    _instance = None
    _agents: dict[str, BaseAgent] = {}

    @classmethod
    def register(cls, agent: BaseAgent):
        """注册 Agent"""
        cls._agents[agent.agent_id] = agent

    @classmethod
    def get(cls, agent_id: str) -> BaseAgent:
        """获取 Agent 实例"""
        if agent_id not in cls._agents:
            raise AgentNotFoundError(f"Agent not found: {agent_id}")
        return cls._agents[agent_id]

    @classmethod
    def list_agents(cls) -> list[str]:
        """列出所有已注册 Agent"""
        return list(cls._agents.keys())


def init_agents():
    """初始化所有 Agent（在 lifespan 中调用）"""
    registry = AgentRegistry()
    registry.register(OrchestratorAgent())
    registry.register(SearcherAgent())
    registry.register(ReasonerAgent())
    registry.register(CriticAgent())
    registry.register(MentorAgent())
    registry.register(WriterAgent())


def get_agent(agent_id: str) -> BaseAgent:
    """获取 Agent（便捷函数）"""
    return AgentRegistry.get(agent_id)
```

**Agent 注册数据流**：

```
应用启动 (lifespan)
        │
        ▼
┌───────────────────┐
│  init_agents()    │
└────────┬──────────┘
         │
    ┌────┼────┬────┬────┬────┐
    ▼    ▼    ▼    ▼    ▼    ▼
  Orch Sear Reas Crit Ment Writ
    │    │    │    │    │    │
    └────┴────┴────┴────┴────┘
              │
              ▼
    ┌──────────────────┐
    │  AgentRegistry   │
    │  _agents = {     │
    │    "orchestrator"│
    │    "searcher"    │
    │    "reasoner"    │
    │    "critic"      │
    │    "mentor"      │
    │    "writer"      │
    │  }               │
    └──────────────────┘
```

### 6.3 Agent 选择数据流

Orchestrator 根据当前阶段选择对应的子 Agent：

```python
class OrchestratorAgent(BaseAgent):

    AGENT_STAGE_MAP = {
        Stage.INFO_CONFIRM: "searcher",
        Stage.CREATIVITY: "reasoner",
        Stage.VALIDATION: "critic",
        Stage.GENERATION: "writer",
        Stage.DEEP_ASSIST: "mentor",
    }

    def _select_agent(self, stage: Stage) -> BaseAgent:
        """根据阶段选择子 Agent"""
        agent_id = self.AGENT_STAGE_MAP[stage]
        return get_agent(agent_id)
```

**Agent 选择数据流图**：

```
当前阶段
    │
    ▼
┌─────────────────────┐
│ AGENT_STAGE_MAP     │
│ 查找映射            │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ get_agent(agent_id) │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ 返回 Agent 实例     │
└─────────────────────┘

映射关系：
  info_confirm  ──▶  searcher
  creativity    ──▶  reasoner
  validation    ──▶  critic (+ mentor 辅助)
  generation    ──▶  writer
  deep_assist   ──▶  mentor
```

### 6.4 Agent 调用数据流

每个子 Agent 继承自 `BaseAgent`，提供统一的 `run()` 与 `stream()` 接口：

```python
# backend/agents/base_agent.py
class BaseAgent(ABC):
    """Agent 基类"""

    def __init__(
        self,
        agent_id: str,
        name: str,
        description: str,
        system_prompt: str,
        model_id: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        capabilities: list[str] = None,
    ):
        self.agent_id = agent_id
        self.name = name
        self.description = description
        self.system_prompt = system_prompt
        self.model_id = model_id
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.capabilities = capabilities or []

    @abstractmethod
    async def run(self, task_input: dict) -> AgentResult:
        """同步执行（返回完整结果）"""
        pass

    @abstractmethod
    async def stream(self, task_input: dict) -> AsyncGenerator[dict, None]:
        """流式执行（yield chunk）"""
        pass

    async def call_llm(
        self,
        user_prompt: str,
        stream: bool = False,
    ) -> str | AsyncGenerator[str, None]:
        """调用 LLM（通过 AIProxy）

        数据流：
        1. 构建三段式 Prompt（base + profile + dynamic）
        2. 计算前缀哈希
        3. 调用 AIProxy
        4. 返回结果
        """
        cached_prefix = build_cached_prefix(
            system_role=self.system_prompt,
            hard_constraints=self._get_hard_constraints(),
            degree=task_input.get("degree", ""),
            discipline=task_input.get("discipline", ""),
            advisor=task_input.get("mentor_info", ""),
        )
        cached_prefix.dynamic = user_prompt

        if stream:
            return ai_proxy.stream_chat(
                model=self.model_id,
                prefix=cached_prefix,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        else:
            return await ai_proxy.chat(
                model=self.model_id,
                prefix=cached_prefix,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
```

### 6.5 Agent 间通信数据流

Agent 之间通过 `AgentCommunicator` 进行通信，支持**同步请求-响应**与**异步消息**两种模式：

```python
# backend/agents/agent_communicator.py
class AgentCommunicator:
    """Agent 间通信组件"""

    async def request(
        self,
        from_agent: str,
        to_agent: str,
        message: dict,
        timeout: float = 30.0,
    ) -> dict:
        """同步请求-响应"""
        logger.info({
            "type": "agent_communication",
            "from": from_agent,
            "to": to_agent,
            "message_size": len(str(message)),
        })

        target_agent = get_agent(to_agent)
        result = await asyncio.wait_for(
            target_agent.run(message),
            timeout=timeout,
        )
        return result.to_dict()

    async def broadcast(
        self,
        from_agent: str,
        message: dict,
        filter_fn: Callable = None,
    ) -> list[dict]:
        """广播消息（并行调用多个 Agent）"""
        target_ids = [
            aid for aid in AgentRegistry.list_agents()
            if aid != from_agent and (filter_fn is None or filter_fn(aid))
        ]

        tasks = [
            self.request(from_agent, aid, message)
            for aid in target_ids
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
```

**Agent 间通信数据流图**：

```
Orchestrator
    │
    │ request(to="reasoner", msg={...})
    ▼
┌──────────────────────┐
│ AgentCommunicator    │
│  • 记录日志          │
│  • 获取目标 Agent    │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ ReasonerAgent.run()  │
│  • 构建 Prompt       │
│  • 调用 LLM          │
│  • 解析响应          │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ AgentResult          │
│  • content           │
│  • reasoning         │
│  • citations         │
│  • token_usage       │
└──────────┬───────────┘
           │
           ▼
    返回给 Orchestrator
```

### 6.6 各子 Agent 数据流详解

#### 6.6.1 SearcherAgent 数据流

```python
# backend/agents/searcher_wrapper.py
class SearcherAgent(BaseAgent):
    """检索 Agent

    职责：联网检索近 2 年文献，为信息确权提供证据支撑。
    """

    async def run(self, task_input: dict) -> AgentResult:
        """执行检索

        数据流：
        1. 解析检索关键词
        2. 调用 LLM 生成检索策略
        3. 执行联网搜索（通过 LLM 的 web_search 能力）
        4. 解析搜索结果，提取引用
        5. 返回结构化结果
        """
        query = task_input.get("query", "")
        degree = task_input.get("degree", "")
        discipline = task_input.get("discipline", "")

        # 1. 构建检索 Prompt
        search_prompt = self._build_search_prompt(query, degree, discipline)

        # 2. 调用 LLM（启用 web_search）
        response = await self.call_llm(
            user_prompt=search_prompt,
            stream=False,
        )

        # 3. 解析响应
        parsed = response_parser.parse_search_response(response)

        # 4. 提取引用
        citations = citation_parser.extract_citations(parsed["content"])

        return AgentResult(
            agent_id=self.agent_id,
            content=parsed["content"],
            reasoning=parsed.get("reasoning"),
            citations=citations,
            token_usage=parsed.get("token_usage", {}),
        )
```

**SearcherAgent 数据流图**：

```
task_input = {query, degree, discipline}
            │
            ▼
┌───────────────────────────┐
│ 1. 构建检索 Prompt         │
│    "请检索近2年关于..."     │
└───────────┬───────────────┘
            │
            ▼
┌───────────────────────────┐
│ 2. 调用 LLM (web_search)   │
│    AIProxy.chat()          │
└───────────┬───────────────┘
            │
            ▼
┌───────────────────────────┐
│ 3. LLM 返回                │
│    • content (含引用标记)  │
│    • reasoning (检索策略)  │
│    • search_results        │
└───────────┬───────────────┘
            │
            ▼
┌───────────────────────────┐
│ 4. ResponseParser 解析     │
│    • 提取 JSON             │
│    • 分离 content/reasoning│
└───────────┬───────────────┘
            │
            ▼
┌───────────────────────────┐
│ 5. CitationParser 提取引用 │
│    • URL 提取              │
│    • 标题解析              │
│    • 摘要提取              │
└───────────┬───────────────┘
            │
            ▼
AgentResult {
    content: "...",
    reasoning: "...",
    citations: [{url, title, snippet}],
    token_usage: {...}
}
```

#### 6.6.2 ReasonerAgent 数据流

```python
# backend/agents/reasoner.py
class ReasonerAgent(BaseAgent):
    """论题生成 Agent

    职责：基于检索结果与用户输入，生成直通开题报告的论题候选。
    使用 deepseek-reasoner 模型，支持思维链推理。
    """

    async def run(self, task_input: dict) -> AgentResult:
        """生成论题候选

        数据流：
        1. 加载检索结果（来自 SearcherAgent）
        2. 构建生成 Prompt（含 DST 状态）
        3. 调用 deepseek-reasoner
        4. 解析 JSON 响应为 AcademicThesisProposal
        5. 自动改写（标题规范化等）
        """
        search_results = task_input.get("search_results", [])
        dst_state = task_input.get("dst_state", {})

        prompt = build_reasoner_prompt(
            degree=task_input["degree"],
            discipline=task_input["discipline"],
            mentor_info=task_input["mentor_info"],
            context=self._format_search_context(search_results),
        )

        response = await self.call_llm(
            user_prompt=prompt,
            stream=False,
        )

        proposal_dict = response_parser.parse_json_response(response)
        proposal = AcademicThesisProposal(**proposal_dict)

        if not self._is_title_valid(proposal.title):
            proposal = await self._auto_rewrite(proposal)
            proposal.auto_rewritten = True

        return AgentResult(
            agent_id=self.agent_id,
            content=proposal.dict(),
            reasoning=response.reasoning,
        )
```

#### 6.6.3 CriticAgent 数据流

```python
# backend/agents/critic.py
class CriticAgent(BaseAgent):
    """评审 Agent

    职责：从新颖性、可行性、学术规范三个维度评估论题候选。
    """

    async def run(self, task_input: dict) -> AgentResult:
        """评估论题

        数据流：
        1. 接收论题候选列表
        2. 对每个候选构建评审 Prompt
        3. 调用 LLM 评分
        4. 聚合评分，排序候选
        5. 返回评审结果
        """
        candidates = task_input.get("candidates", [])

        tasks = [
            self._evaluate_single(c, task_input)
            for c in candidates
        ]
        evaluations = await asyncio.gather(*tasks)

        ranked = self._rank_candidates(evaluations)

        return AgentResult(
            agent_id=self.agent_id,
            content={
                "evaluations": evaluations,
                "ranked_candidates": ranked,
                "best_candidate": ranked[0] if ranked else None,
            },
        )
```

#### 6.6.4 WriterAgent 数据流

```python
# backend/agents/proposal_writer.py
class WriterAgent(BaseAgent):
    """开题内容生成 Agent

    职责：多粒度生成开题报告内容（标题级/段落级/章节级）。
    """

    async def run(self, task_input: dict) -> AgentResult:
        """生成开题内容

        数据流：
        1. 接收选定的论题
        2. 根据粒度选择生成策略
        3. 调用 LLM 生成内容
        4. 风格规范化
        5. 返回结构化内容
        """
        proposal = task_input["proposal"]
        granularity = task_input.get("granularity", "section")

        if granularity == "title":
            content = await self._generate_titles(proposal)
        elif granularity == "paragraph":
            content = await self._generate_paragraphs(proposal)
        else:
            content = await self._generate_sections(proposal)

        content = style_normalizer.normalize(content)

        return AgentResult(
            agent_id=self.agent_id,
            content=content,
        )
```

#### 6.6.5 MentorAgent 数据流

```python
# backend/agents/mentor_agent.py
class MentorAgent(BaseAgent):
    """导师 Agent

    职责：以导师视角提供深度评审与建议，支持文献精读、实验预研、答辩模拟。
    """

    async def run(self, task_input: dict) -> AgentResult:
        """导师视角评审

        数据流：
        1. 接收论题与上下文
        2. 构建导师视角 Prompt
        3. 调用 LLM 生成评审意见
        4. 返回结构化建议
        """
        proposal = task_input["proposal"]
        mode = task_input.get("mode", "review")

        prompt = self._build_mentor_prompt(proposal, mode)
        response = await self.call_llm(user_prompt=prompt)

        return AgentResult(
            agent_id=self.agent_id,
            content=response,
        )
```

---

## 7. AI Proxy 转发数据流

### 7.1 AI Proxy 概述

AI Proxy 是能力层的核心组件，负责将 Agent 的 LLM 调用请求转发至外部 LLM API（DeepSeek）。它封装了三段式 Prompt 缓存构建、HTTP 调用、响应解析、流式处理等逻辑。

### 7.2 AI Proxy 数据流架构

```
┌──────────────────────────────────────────────────────────────────┐
│                       AIProxy 数据流                              │
│                                                                  │
│  ┌──────────┐                                                    │
│  │ Agent    │ ◀── 调用 ai_proxy.chat() / stream_chat()           │
│  └────┬─────┘                                                    │
│       │                                                          │
│       ▼                                                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Prompt 构建与缓存优化                        │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │   │
│  │  │ build_cached │  │ compute_hash │  │ check_cache  │   │   │
│  │  │ _prefix()    │─▶│ (SHA-256)    │─▶│ _hit()       │   │   │
│  │  └──────────────┘  └──────────────┘  └──────┬───────┘   │   │
│  └─────────────────────────────────────────────┼───────────┘   │
│                                       ┌────────┴────────┐       │
│                                       │                 │       │
│                                    命中              未命中      │
│                                       ▼                 ▼       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              HTTP 请求构建                               │   │
│  │  • 构建 messages 数组                                    │   │
│  │  • 设置 model/temperature/max_tokens                    │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              HTTP 调用 (httpx.AsyncClient)               │   │
│  │  • POST https://api.deepseek.com/v1/chat/completions     │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              响应处理                                    │   │
│  │  • 解析 JSON 响应                                        │   │
│  │  • 提取 content / reasoning / usage                     │   │
│  │  • 记录缓存命中信息                                      │   │
│  │  • 扣减预算                                              │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### 7.3 AI Proxy 核心实现

```python
# backend/ai/ai_proxy.py
import httpx
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


class AIProxy:
    """LLM 调用代理

    封装 DeepSeek API 调用，支持：
    - 三段式 Prompt 缓存优化
    - 同步与流式调用
    - 自动重试与降级
    - Token 用量统计
    """

    def __init__(self):
        self.api_base = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.timeout = httpx.Timeout(
            connect=10.0,
            read=120.0,
            write=10.0,
            pool=5.0,
        )
        self.client = httpx.AsyncClient(
            base_url=self.api_base,
            timeout=self.timeout,
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
            ),
        )

    async def chat(
        self,
        model: str,
        prefix: CachedPrefix,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> dict:
        """同步调用 LLM

        数据流：
        1. 构建 messages 数组
        2. 发送 HTTP POST
        3. 解析响应
        4. 记录指标
        """
        messages = self._build_messages(prefix)

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        start_time = time.time()
        try:
            response = await self.client.post(
                "/v1/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"LLM API 错误: {e.response.status_code}")
            raise LLMUnavailableError(f"HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"LLM API 网络错误: {e}")
            raise LLMUnavailableError(str(e))

        data = response.json()
        latency_ms = (time.time() - start_time) * 1000

        result = {
            "content": data["choices"][0]["message"]["content"],
            "reasoning": data["choices"][0]["message"].get("reasoning_content"),
            "token_usage": data.get("usage", {}),
            "cache_hit": data.get("usage", {}).get("prompt_cache_hit_tokens", 0) > 0,
            "latency_ms": latency_ms,
        }

        await self._record_metrics(model, result, latency_ms)

        return result

    async def stream_chat(
        self,
        model: str,
        prefix: CachedPrefix,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[dict, None]:
        """流式调用 LLM

        数据流：
        1. 构建 messages（stream=True）
        2. 发送 HTTP POST（流式）
        3. 逐 chunk 解析 SSE
        4. yield 给调用方
        """
        messages = self._build_messages(prefix)
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        async with self.client.stream(
            "POST",
            "/v1/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    chunk_str = line[6:]
                    if chunk_str == "[DONE]":
                        break
                    chunk = json.loads(chunk_str)
                    yield self._parse_stream_chunk(chunk)

    def _build_messages(self, prefix: CachedPrefix) -> list[dict]:
        """构建 messages 数组"""
        messages = []
        messages.extend(prefix.prefix_messages)
        messages.append({"role": "user", "content": prefix.dynamic})
        return messages


ai_proxy = AIProxy()
```

### 7.4 AI Proxy 数据包流转

```
Agent 调用
    │
    ▼
┌─────────────────────────────────────────┐
│  输入: CachedPrefix                     │
│  {                                      │
│    prefix: "[SYSTEM_ROLE]\n你是...",    │
│    prefix_messages: [                   │
│      {role: "system", content: "..."}   │
│    ],                                   │
│    dynamic: "当前查询: 深度学习..."      │
│  }                                      │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  转换为 HTTP 请求体                     │
│  {                                      │
│    "model": "deepseek-chat",            │
│    "messages": [                        │
│      {"role": "system",                 │
│       "content": "[SYSTEM_ROLE]..."},   │
│      {"role": "user",                   │
│       "content": "当前查询: ..."}       │
│    ],                                   │
│    "temperature": 0.7,                  │
│    "max_tokens": 4096,                  │
│    "stream": false                      │
│  }                                      │
└─────────────────┬───────────────────────┘
                  │ HTTPS POST
                  ▼
┌─────────────────────────────────────────┐
│  DeepSeek API                           │
│  • KV Cache 匹配前缀                    │
│  • 生成响应                             │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  响应: {                                │
│    "choices": [{                        │
│      "message": {                       │
│        "content": "...",                │
│        "reasoning_content": "..."       │
│      }                                  │
│    }],                                  │
│    "usage": {                           │
│      "prompt_tokens": 1234,             │
│      "completion_tokens": 567,          │
│      "prompt_cache_hit_tokens": 1100    │
│    }                                    │
│  }                                      │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  标准化结果:                            │
│  {                                      │
│    content: "...",                      │
│    reasoning: "...",                    │
│    token_usage: {...},                  │
│    cache_hit: true,                     │
│    latency_ms: 1234.5                   │
│  }                                      │
└─────────────────────────────────────────┘
```

---

## 8. LLM 调用与响应数据流

### 8.1 LLM 调用概述

LLM 调用是 ThesisMiner v8.0 中**最耗时**的数据流环节，平均耗时 2-15 秒。本节详细描述从 Prompt 构建到响应接收的完整数据流。

### 8.2 LLM 调用数据流时序图

```
Agent          AIProxy        httpx        DeepSeek API     KV Cache
  │              │              │              │               │
  │  call_llm()  │              │              │               │
  ├─────────────▶│              │              │               │
  │              │ build_msg    │              │               │
  │              │ compute_hash │              │               │
  │              │  POST        │              │               │
  │              ├─────────────▶│              │               │
  │              │              │  HTTPS       │               │
  │              │              ├─────────────▶│               │
  │              │              │              │ cache lookup  │
  │              │              │              │ ◀─────────────│
  │              │              │              │ prefill       │
  │              │              │              │ decode        │
  │              │              │  Response    │               │
  │              │              │ ◀────────────│               │
  │              │ ◀────────────│              │               │
  │              │ parse        │              │               │
  │              │ record       │              │               │
  │  result      │              │              │               │
  │ ◀────────────│              │              │               │

时序说明：
  build_msg:     ~1ms
  compute_hash:  ~1ms
  HTTPS RTT:     ~50-200ms
  prefill:       100-2000ms (cache hit 则 <50ms)
  decode:        500-10000ms (取决于 max_tokens)
  parse:         ~5ms
  record:        ~5ms
```

### 8.3 三段式 Prompt 构建数据流

三段式 Prompt 是 ThesisMiner v8.0 的核心优化，通过将 Prompt 拆分为不可变前缀与动态尾部，最大化 DeepSeek KV Cache 命中率：

```python
# backend/ai/prompt_cache.py
@dataclass
class CachedPrefix:
    """缓存前缀数据结构"""
    prefix: str              # 不可变前缀文本
    prefix_messages: list    # 不可变前缀消息列表
    dynamic: str             # 动态尾部文本
    prefix_char_count: int   # 前缀字符数


def build_cached_prefix(
    system_role: str,
    hard_constraints: list[str],
    degree: str = "",
    discipline: str = "",
    advisor: str = "",
) -> CachedPrefix:
    """构建三段式缓存前缀

    数据流：
    1. 拼接 [SYSTEM_ROLE] 段
    2. 拼接 [HARD_CONSTRAINTS] 段
    3. 拼接 [ACADEMIC_CONTEXT] 段
    4. 计算前缀字符数
    5. 返回 CachedPrefix
    """
    prefix_parts = []

    # 段 1: 系统角色（全局不变）
    prefix_parts.append(f"[SYSTEM_ROLE]\n{system_role}\n")

    # 段 2: 硬约束（全局不变）
    if hard_constraints:
        prefix_parts.append("[HARD_CONSTRAINTS]")
        for i, c in enumerate(hard_constraints, 1):
            prefix_parts.append(f"{i}. {c}")
        prefix_parts.append("")

    # 段 3: 学术上下文（会话级不变）
    if degree or discipline or advisor:
        prefix_parts.append("[ACADEMIC_CONTEXT]")
        if degree:
            prefix_parts.append(f"学位: {degree}")
        if discipline:
            prefix_parts.append(f"学科: {discipline}")
        if advisor:
            prefix_parts.append(f"导师方向: {advisor}")
        prefix_parts.append("")

    prefix_text = "\n".join(prefix_parts)

    return CachedPrefix(
        prefix=prefix_text,
        prefix_messages=[{"role": "system", "content": prefix_text}],
        dynamic="",
        prefix_char_count=len(prefix_text.encode("utf-8")),
    )
```

**三段式 Prompt 结构图**：

```
┌──────────────────────────────────────────────────────────────┐
│                    完整 Prompt 结构                           │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  段 1: [SYSTEM_ROLE] (全局不变)                         │ │
│  │  "你是学术论题生成专家 Reasoner..."                     │ │
│  │  缓存属性: 全局缓存 (跨会话共享)                        │ │
│  │  变更频率: 永不变更                                     │ │
│  │  预估 token: ~200 tokens                               │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  段 2: [HARD_CONSTRAINTS] (全局不变)                    │ │
│  │  1. 必须输出 JSON 格式...                               │ │
│  │  2. title 必须为限 20 字以内...                         │ │
│  │  3. confidence_score 取值范围 0-1                       │ │
│  │  缓存属性: 全局缓存 (跨会话共享)                        │ │
│  │  变更频率: 版本升级时变更                               │ │
│  │  预估 token: ~150 tokens                               │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  段 3: [ACADEMIC_CONTEXT] (会话级不变)                  │ │
│  │  学位: master                                          │ │
│  │  学科: science_engineering                              │ │
│  │  导师方向: 深度学习、计算机视觉                         │ │
│  │  缓存属性: 会话级缓存 (同会话共享)                      │ │
│  │  变更频率: 每个新会话变更                               │ │
│  │  预估 token: ~50 tokens                                │ │
│  └────────────────────────────────────────────────────────┘ │
│  ══════════════════════════════════════════════════════════ │
│  │  以上三段构成不可变前缀，参与 KV Cache                  │ │
│  │  前缀哈希: SHA-256(prefix_text)                        │ │
│  ══════════════════════════════════════════════════════════ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  段 4: 动态尾部 (每轮变化)                              │ │
│  │  "当前查询: 请生成关于 Transformer 的论题"              │ │
│  │  "DST 状态: {selected_topic: ...}"                     │ │
│  │  缓存属性: 不缓存 (每轮不同)                            │ │
│  │  变更频率: 每次调用变更                                 │ │
│  │  预估 token: ~100-500 tokens                           │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### 8.4 缓存前缀哈希计算

```python
import hashlib

def compute_prefix_hash(prefix_text: str) -> str:
    """计算前缀哈希（SHA-256）

    用于：
    1. 会话级缓存前缀一致性校验
    2. 缓存命中监控
    3. 调试时快速定位前缀变更
    """
    return hashlib.sha256(prefix_text.encode("utf-8")).hexdigest()


def save_session_prefix_hash(session_id: str, prefix_text: str):
    """持久化会话的前缀哈希"""
    prefix_hash = compute_prefix_hash(prefix_text)
    execute_query(
        "UPDATE sessions SET cache_prefix_hash = ? WHERE id = ?",
        (prefix_hash, session_id)
    )
```

### 8.5 LLM 响应解析数据流

```python
# backend/ai/response_parser.py
class ResponseParser:
    """LLM 响应解析器"""

    def parse_json_response(self, response: dict) -> dict:
        """解析 JSON 响应

        数据流：
        1. 提取 content
        2. 清理 Markdown 代码块标记
        3. JSON 反序列化
        4. 字段校验
        """
        content = response["content"]

        # 1. 清理 Markdown 标记
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        # 2. JSON 解析
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            raise ResponseParseError(f"Invalid JSON: {e}")

        # 3. 字段校验
        self._validate_fields(data)

        return data

    def _validate_fields(self, data: dict):
        """校验响应字段完整性"""
        required_fields = [
            "title", "inspiration_source", "problem_awareness",
            "research_significance", "literature_review_outline",
            "differentiation", "research_content",
            "feasibility_analysis", "confidence_score"
        ]
        for field in required_fields:
            if field not in data:
                raise ResponseParseError(f"Missing field: {field}")
```

### 8.6 LLM 调用预算扣减数据流

每次 LLM 调用后，需要将 token 用量记录到预算账本：

```python
# backend/budgets/transparent_ledger.py
class TransparentLedger:
    """透明预算账本"""

    async def record(
        self,
        session_id: str,
        agent_id: str,
        model: str,
        usage: dict,
        purpose: str,
        cache_hit_rate: float = 0,
    ):
        """记录预算消耗

        数据流：
        1. 计算 token 费用
        2. 插入 budget_ledger 表
        3. 更新会话累计消耗
        """
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        cached_tokens = usage.get("prompt_cache_hit_tokens", 0)

        cost = self._calculate_cost(
            model, prompt_tokens, completion_tokens, cached_tokens
        )

        execute_insert("budget_ledger", {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cached_prompt_tokens": cached_tokens,
            "cost": cost,
            "purpose": f"{agent_id}:{purpose}",
            "cache_hit_rate": cache_hit_rate,
        })

    def _calculate_cost(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cached_tokens: int,
    ) -> float:
        """计算费用

        DeepSeek 定价（示例）：
        - prompt: $0.14 / 1M tokens
        - cached prompt: $0.014 / 1M tokens (1/10)
        - completion: $0.28 / 1M tokens
        """
        prompt_cost = (prompt_tokens - cached_tokens) * 0.14 / 1_000_000
        cached_cost = cached_tokens * 0.014 / 1_000_000
        completion_cost = completion_tokens * 0.28 / 1_000_000

        return round(prompt_cost + cached_cost + completion_cost, 6)
```

---

## 9. 响应解析数据流

### 9.1 响应解析概述

响应解析数据流负责将 LLM 返回的非结构化文本转换为结构化的业务对象。ThesisMiner v8.0 的响应解析器支持 JSON 解析、字段校验、类型转换、默认值填充等功能。

### 9.2 响应解析数据流架构

```
┌──────────────────────────────────────────────────────────────┐
│                    响应解析数据流                              │
│                                                              │
│  ┌──────────────┐                                            │
│  │ LLM 响应     │                                            │
│  │ {content,    │                                            │
│  │  reasoning,  │                                            │
│  │  usage}      │                                            │
│  └──────┬───────┘                                            │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────┐     ┌──────────────┐                       │
│  │ JSON 提取器  │────▶│ 正则匹配     │                       │
│  │ extract_json │     │ ```json ...  │                       │
│  └──────┬───────┘     └──────┬───────┘                       │
│         │                    │                               │
│         ▼                    ▼                               │
│  ┌──────────────────────────────────┐                        │
│  │        JSON 解析器               │                        │
│  │   json.loads / json_repair       │                        │
│  └──────────────┬───────────────────┘                        │
│                 │                                            │
│                 ▼                                            │
│  ┌──────────────────────────────────┐                        │
│  │        字段校验器                │                        │
│  │   Pydantic Model Validation      │                        │
│  └──────────────┬───────────────────┘                        │
│                 │                                            │
│           ┌─────┴─────┐                                      │
│           │           │                                      │
│           ▼           ▼                                      │
│     ┌─────────┐  ┌─────────┐                                 │
│     │ 校验通过│  │ 校验失败│                                 │
│     └────┬────┘  └────┬────┘                                 │
│          │            │                                      │
│          ▼            ▼                                      │
│   ┌──────────┐  ┌──────────────┐                             │
│   │ 类型转换 │  │ 默认值填充   │                             │
│   │ + 返回   │  │ + 重试/降级  │                             │
│   └──────────┘  └──────────────┘                             │
└──────────────────────────────────────────────────────────────┘
```

### 9.3 JSON 提取与修复

LLM 返回的内容可能包含 Markdown 代码块包裹（如 ` ```json ... ``` `），也可能因为生成截断导致 JSON 不完整。响应解析器首先需要从原始文本中提取 JSON 片段，并尝试修复不完整的 JSON。

```python
# backend/ai/response_parser.py
import json
import re
from typing import Any
from json_repair import repair_json


def extract_json(content: str) -> str:
    """从 LLM 响应文本中提取 JSON 字符串

    支持以下格式：
    1. 纯 JSON：{"key": "value"}
    2. Markdown 代码块：```json\n{...}\n```
    3. 混合文本：前缀文字 + JSON + 后缀文字
    """
    # 策略1：尝试直接解析
    content_stripped = content.strip()
    if content_stripped.startswith("{") or content_stripped.startswith("["):
        return content_stripped

    # 策略2：提取 Markdown 代码块中的 JSON
    code_block_pattern = r"```(?:json)?\s*\n?(.*?)\n?```"
    matches = re.findall(code_block_pattern, content, re.DOTALL)
    if matches:
        return matches[0].strip()

    # 策略3：提取第一个 { 到最后一个 } 之间的内容
    first_brace = content.find("{")
    last_brace = content.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return content[first_brace : last_brace + 1]

    # 策略4：提取第一个 [ 到最后一个 ] 之间的内容
    first_bracket = content.find("[")
    last_bracket = content.rfind("]")
    if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
        return content[first_bracket : last_bracket + 1]

    return content_stripped


def parse_json_safe(content: str) -> dict | list | None:
    """安全解析 JSON，支持自动修复

    解析流程：
    1. 提取 JSON 字符串
    2. 尝试 json.loads 标准解析
    3. 若失败，使用 json_repair 修复后解析
    4. 若仍失败，返回 None
    """
    json_str = extract_json(content)

    # 第一次尝试：标准 JSON 解析
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    # 第二次尝试：json_repair 修复
    try:
        repaired = repair_json(json_str, return_objects=True)
        if isinstance(repaired, (dict, list)):
            return repaired
    except Exception:
        pass

    # 第三次尝试：移除控制字符后重试
    try:
        clean_str = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", json_str)
        return json.loads(clean_str)
    except json.JSONDecodeError:
        return None
```

### 9.4 Pydantic 字段校验

提取并解析 JSON 后，响应解析器使用 Pydantic 模型对字段进行校验。每个 Agent 的输出都有对应的 Pydantic 模型，定义了必需字段、可选字段、类型约束和默认值。

```python
# backend/agents/schemas.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum


class CandidateDimension(str, Enum):
    """论题创意维度"""
    NEW_APPLICATION = "new_application"      # 新应用场景
    METHOD_FUSION = "method_fusion"          # 方法融合
    CROSS_DISCIPLINE = "cross_discipline"    # 跨学科
    THEORY_EXTENSION = "theory_extension"    # 理论延伸


class ThesisCandidate(BaseModel):
    """论题候选模型"""
    title: str = Field(..., min_length=5, max_length=200, description="论题标题")
    dimension: CandidateDimension = Field(..., description="创意维度")
    rationale: str = Field(..., min_length=10, max_length=1000, description="选题理由")
    feasibility: Optional[int] = Field(None, ge=1, le=10, description="可行性评分")
    novelty: Optional[int] = Field(None, ge=1, le=10, description="新颖性评分")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """标题校验：不允许以句号结尾"""
        v = v.strip()
        if v.endswith(("。", ".", "，", ",")):
            raise ValueError("标题不应以标点符号结尾")
        return v


class CreativityResult(BaseModel):
    """Reasoner Agent 输出模型"""
    candidates: list[ThesisCandidate] = Field(
        ..., min_length=1, max_length=5, description="候选论题列表"
    )
    summary: str = Field(..., description="创意生成总结")


class EvaluationItem(BaseModel):
    """Critic Agent 单项评估模型"""
    title: str = Field(..., description="被评估的论题标题")
    scores: dict[str, int] = Field(..., description="各维度评分")
    recommendation: str = Field(..., description="推荐意见")
    issues: list[str] = Field(default_factory=list, description="存在问题")


class CriticResult(BaseModel):
    """Critic Agent 输出模型"""
    evaluations: list[EvaluationItem] = Field(
        ..., min_length=1, description="评估结果列表"
    )
    best_index: int = Field(..., ge=0, description="最佳候选索引")


# ---------- 校验入口 ----------

def validate_agent_result(agent_id: str, raw: dict) -> BaseModel:
    """根据 agent_id 选择对应的 Pydantic 模型进行校验

    Args:
        agent_id: Agent 标识（reasoner / critic / mentor / searcher / writer）
        raw: 解析后的字典

    Returns:
        校验通过的 Pydantic 模型实例

    Raises:
        ValidationError: 字段校验失败
    """
    MODEL_MAP = {
        "reasoner": CreativityResult,
        "critic": CriticResult,
        # mentor / searcher / writer 略
    }
    model_cls = MODEL_MAP.get(agent_id)
    if model_cls is None:
        raise ValueError(f"未知 agent_id: {agent_id}")
    return model_cls.model_validate(raw)
```

### 9.5 默认值填充与降级

当 Pydantic 校验失败时，响应解析器会尝试填充默认值或降级处理，避免因 LLM 输出不规范导致整个流程中断。

```python
# backend/ai/response_parser.py
from pydantic import ValidationError


def parse_and_validate(
    content: str,
    agent_id: str,
    allow_fallback: bool = True,
) -> tuple[BaseModel | None, list[str]]:
    """解析并校验 Agent 响应

    Returns:
        (model, errors): 校验通过的模型实例（失败时为 None）与错误信息列表
    """
    errors: list[str] = []

    # Step 1: JSON 解析
    raw = parse_json_safe(content)
    if raw is None:
        errors.append("JSON 解析失败：无法从响应中提取有效 JSON")
        if not allow_fallback:
            return None, errors
        # 降级：构造空结果
        raw = {"candidates": [], "summary": "解析失败，返回空结果"}

    # Step 2: Pydantic 校验
    try:
        model = validate_agent_result(agent_id, raw)
        return model, errors
    except ValidationError as e:
        errors.append(f"Pydantic 校验失败: {e}")
        if not allow_fallback:
            return None, errors

    # Step 3: 降级 - 逐字段填充默认值
    try:
        if isinstance(raw, dict):
            # 确保必需字段存在
            raw.setdefault("candidates", [])
            raw.setdefault("summary", "降级处理：自动填充")
            model = validate_agent_result(agent_id, raw)
            return model, errors
    except ValidationError as e:
        errors.append(f"降级填充后仍校验失败: {e}")

    return None, errors
```

### 9.6 响应解析数据流时序图

```
 Agent        ResponseParser      Pydantic       业务层
   │                │                 │              │
   │  raw_content   │                 │              │
   │───────────────▶│                 │              │
   │                │                 │              │
   │                │  extract_json   │              │
   │                │  (正则/代码块)  │              │
   │                │────┐            │              │
   │                │    │            │              │
   │                │◀───┘            │              │
   │                │  json_str       │              │
   │                │                 │              │
   │                │  json.loads     │              │
   │                │  或 repair_json │              │
   │                │────┐            │              │
   │                │    │            │              │
   │                │◀───┘            │              │
   │                │  dict           │              │
   │                │                 │              │
   │                │  model_validate │              │
   │                │────────────────▶│              │
   │                │                 │              │
   │                │                 │  字段校验    │
   │                │                 │  类型转换    │
   │                │                 │  约束检查    │
   │                │                 │              │
   │                │  ◀───── 成功 ───│              │
   │                │  model 实例     │              │
   │                │                 │              │
   │                │  返回模型       │              │
   │                │───────────────────────────────▶│
   │                │                 │              │
   │                │                 │              │  后续业务处理
   │                │                 │              │  (存储/展示)
   │                │                 │              │
   │                │  ◀──── 失败 ────│              │
   │                │  ValidationError│              │
   │                │                 │              │
   │                │  默认值填充     │              │
   │                │  降级处理       │              │
   │                │────┐            │              │
   │                │    │            │              │
   │                │◀───┘            │              │
   │                │  fallback model │              │
   │                │───────────────────────────────▶│
   │                │                 │              │
```

---

## 10. 引用解析数据流

### 10.1 引用解析概述

当 Searcher Agent 执行文献检索时，返回的搜索结果中包含大量 URL 引用。引用解析数据流负责从搜索结果中提取 URL、获取页面元数据（标题、摘要、作者、发布时间）、进行 SSRF 防护校验、持久化存储，并在前端展示时关联到对应的论题或知识卡片。

### 10.2 引用解析数据流架构

```
┌──────────────────────────────────────────────────────────────────┐
│                      引用解析数据流                                │
│                                                                  │
│  ┌──────────┐                                                    │
│  │ Searcher │  搜索结果: [{"title": "...", "url": "...", ...}]   │
│  │  Agent   │                                                    │
│  └────┬─────┘                                                    │
│       │                                                          │
│       ▼                                                          │
│  ┌──────────────────┐                                            │
│  │ URL 提取器       │  从搜索结果中提取所有 URL                   │
│  │ extract_urls()   │                                            │
│  └────────┬─────────┘                                            │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────┐                                            │
│  │ SSRF 校验器      │  检查 URL 是否指向内网/保留地址             │
│  │ validate_url()   │  - 拒绝 127.0.0.0/8                       │
│  │                  │  - 拒绝 10.0.0.0/8, 172.16.0.0/12         │
│  │                  │  - 拒绝 192.168.0.0/16                     │
│  │                  │  - 拒绝 169.254.0.0/16 (link-local)       │
│  │                  │  - 仅允许 http/https 协议                  │
│  └────────┬─────────┘                                            │
│           │                                                      │
│     ┌─────┴─────┐                                                │
│     │           │                                                │
│     ▼           ▼                                                │
│ ┌────────┐  ┌────────┐                                           │
│ │ 通过   │  │ 拒绝   │                                           │
│ └───┬────┘  └───┬────┘                                           │
│     │           │                                                │
│     ▼           ▼                                                │
│ ┌──────────┐  ┌──────────────┐                                   │
│ │ 元数据   │  │ 记录拒绝日志 │                                   │
│ │ 获取器   │  │ 跳过该 URL   │                                   │
│ │ fetch_   │  └──────────────┘                                   │
│ │ metadata │                                                    │
│ └─────┬────┘                                                    │
│       │                                                          │
│       ▼                                                          │
│ ┌──────────────────┐                                            │
│ │ 引用持久化       │  写入 search_citations 表                   │
│ │ persist_citation │  - url, title, snippet                     │
│  │                 │  - source, published_at                    │
│  │                 │  - proposal_id / knowledge_card_id         │
│  └────────┬─────────┘                                            │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────┐                                            │
│  │ 前端展示         │  在论题详情/知识卡片页面展示引用列表        │
│  │ render_citations │  - 可点击跳转                              │
│  │                  │  - 显示来源与摘要                          │
│  └──────────────────┘                                            │
└──────────────────────────────────────────────────────────────────┘
```

### 10.3 SSRF 防护实现

SSRF（Server-Side Request Forgery）防护是引用解析数据流中的关键安全环节。ThesisMiner v8.0 对所有外部 URL 执行严格的地址校验，防止服务端请求伪造攻击。

```python
# backend/utils/ssrf_guard.py
import ipaddress
import socket
from urllib.parse import urlparse
from typing import Optional


# 保留 IP 地址段
RESERVED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),        # 本网络
    ipaddress.ip_network("10.0.0.0/8"),       # 私有网络 A 类
    ipaddress.ip_network("127.0.0.0/8"),      # 环回地址
    ipaddress.ip_network("169.254.0.0/16"),   # 链路本地
    ipaddress.ip_network("172.16.0.0/12"),    # 私有网络 B 类
    ipaddress.ip_network("192.168.0.0/16"),   # 私有网络 C 类
    ipaddress.ip_network("::1/128"),          # IPv6 环回
    ipaddress.ip_network("fc00::/7"),         # IPv6 唯一本地
    ipaddress.ip_network("fe80::/10"),        # IPv6 链路本地
]

ALLOWED_SCHEMES = {"http", "https"}


def validate_url(url: str) -> tuple[bool, Optional[str]]:
    """校验 URL 安全性，防止 SSRF 攻击

    Args:
        url: 待校验的 URL 字符串

    Returns:
        (is_safe, reason): 是否安全及拒绝原因
    """
    # 1. 解析 URL
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "URL 解析失败"

    # 2. 协议校验
    if parsed.scheme not in ALLOWED_SCHEMES:
        return False, f"不允许的协议: {parsed.scheme}"

    # 3. 主机名校验
    hostname = parsed.hostname
    if not hostname:
        return False, "缺少主机名"

    # 4. DNS 解析 - 获取所有 IP 地址
    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False, f"DNS 解析失败: {hostname}"

    # 5. 检查每个解析到的 IP 地址
    for addr_info in addr_infos:
        ip_str = addr_info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return False, f"无效 IP 地址: {ip_str}"

        for network in RESERVED_NETWORKS:
            if ip in network:
                return False, f"IP {ip_str} 位于保留网络 {network}"

    return True, None
```

### 10.4 元数据获取

通过 SSRF 校验后，引用解析器使用 httpx 异步获取页面元数据。为避免长时间阻塞，设置 5 秒超时，并在失败时降级为仅存储 URL 和搜索结果中的摘要。

```python
# backend/agents/citation_parser.py
import httpx
from selectolax.parser import HTMLParser
from typing import Optional


async def fetch_metadata(
    url: str,
    timeout: float = 5.0,
) -> dict:
    """异步获取 URL 页面的元数据

    Returns:
        {
            "title": 页面标题,
            "description": meta description,
            "og_title": Open Graph 标题,
            "og_description": Open Graph 描述,
            "og_image": Open Graph 图片 URL,
        }
    """
    metadata = {
        "title": "",
        "description": "",
        "og_title": "",
        "og_description": "",
        "og_image": "",
    }

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            max_redirects=3,
            headers={"User-Agent": "ThesisMiner/8.0 CitationBot"},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

            tree = HTMLParser(response.text)

            # 提取 <title>
            title_node = tree.css_first("title")
            if title_node:
                metadata["title"] = title_node.text(strip=True)[:500]

            # 提取 <meta name="description">
            desc_node = tree.css_first('meta[name="description"]')
            if desc_node and desc_node.attributes.get("content"):
                metadata["description"] = desc_node.attributes["content"][:1000]

            # 提取 Open Graph 元数据
            og_title = tree.css_first('meta[property="og:title"]')
            if og_title and og_title.attributes.get("content"):
                metadata["og_title"] = og_title.attributes["content"][:500]

            og_desc = tree.css_first('meta[property="og:description"]')
            if og_desc and og_desc.attributes.get("content"):
                metadata["og_description"] = og_desc.attributes["content"][:1000]

            og_image = tree.css_first('meta[property="og:image"]')
            if og_image and og_image.attributes.get("content"):
                metadata["og_image"] = og_image.attributes["content"][:1000]

    except httpx.TimeoutException:
        metadata["title"] = "[获取超时]"
    except httpx.HTTPError as e:
        metadata["title"] = f"[HTTP 错误: {type(e).__name__}]"
    except Exception:
        metadata["title"] = "[解析失败]"

    return metadata
```

### 10.5 引用持久化

获取元数据后，引用解析器将引用信息写入 `search_citations` 表，关联到对应的论题或知识卡片。

```python
# backend/agents/citation_parser.py
import sqlite3
from datetime import datetime


def persist_citation(
    conn: sqlite3.Connection,
    url: str,
    title: str,
    snippet: str,
    source: str,
    proposal_id: int | None = None,
    knowledge_card_id: int | None = None,
    metadata: dict | None = None,
) -> int:
    """将引用信息持久化到 search_citations 表

    Args:
        conn: SQLite 连接
        url: 引用 URL
        title: 引用标题
        snippet: 摘要片段
        source: 来源（arxiv / semantic_scholar / web_search）
        proposal_id: 关联论题 ID（可选）
        knowledge_card_id: 关联知识卡片 ID（可选）
        metadata: 额外元数据

    Returns:
        插入的引用 ID
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO search_citations (
            url, title, snippet, source,
            proposal_id, knowledge_card_id,
            metadata_json, fetched_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            url,
            title,
            snippet,
            source,
            proposal_id,
            knowledge_card_id,
            json.dumps(metadata or {}, ensure_ascii=False),
            datetime.utcnow().isoformat(),
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    return cursor.lastrowid
```

### 10.6 引用解析时序图

```
 Searcher    SSRFGuard    CitationParser    Database    Frontend
   │            │              │               │           │
   │ 搜索结果   │              │               │           │
   │───────────▶│              │               │           │
   │            │              │               │           │
   │            │ validate_url │               │           │
   │            │────┐         │               │           │
   │            │    │         │               │           │
   │            │◀───┘         │               │           │
   │            │ (safe,reason)│               │           │
   │            │              │               │           │
   │            │  通过的 URL  │               │           │
   │            │─────────────▶│               │           │
   │            │              │               │           │
   │            │              │ fetch_metadata│           │
   │            │              │ (httpx GET)   │           │
   │            │              │────┐          │           │
   │            │              │    │ 5s 超时  │           │
   │            │              │◀───┘          │           │
   │            │              │ metadata      │           │
   │            │              │               │           │
   │            │              │ INSERT        │           │
   │            │              │──────────────▶│           │
   │            │              │               │           │
   │            │              │   citation_id │           │
   │            │              │◀──────────────│           │
   │            │              │               │           │
   │            │              │               │  查询引用 │
   │            │              │               │◀──────────│
   │            │              │               │           │
   │            │              │               │ 引用列表  │
   │            │              │               │──────────▶│
   │            │              │               │           │
```

---

## 11. 流式输出数据流

### 11.1 流式输出概述

ThesisMiner v8.0 的流式输出采用 Server-Sent Events（SSE）协议，将 LLM 的增量响应实时推送到前端。流式输出贯穿四个层级：DeepSeek API → httpx 流式接收 → FastAPI StreamingResponse → 前端 EventSource 消费。这种设计显著降低了首字节延迟（TTFB），用户无需等待完整响应生成即可看到逐步输出的内容。

### 11.2 流式输出数据流架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                       流式输出数据流架构                              │
│                                                                     │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐         │
│  │ Frontend │   │ FastAPI  │   │ AIProxy  │   │ DeepSeek │         │
│  │EventSource│   │Streaming │   │ httpx    │   │   API    │         │
│  │ Consumer │   │Response  │   │ Stream   │   │  Stream  │         │
│  └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘         │
│       │               │              │              │               │
│       │               │              │   POST       │               │
│       │               │              │  stream=true │               │
│       │               │              │─────────────▶│               │
│       │               │              │              │               │
│       │               │              │              │  chunk 1      │
│       │               │              │◀─────────────│               │
│       │               │              │  data: {...} │               │
│       │               │              │              │               │
│       │               │              │  yield chunk │               │
│       │               │              │────┐         │               │
│       │               │              │    │         │               │
│       │               │              │◀───┘         │               │
│       │               │              │              │               │
│       │               │  yield SSE   │              │               │
│       │               │◀─────────────│              │               │
│       │  data: chunk1 │              │              │               │
│       │◀──────────────│              │              │               │
│       │               │              │              │               │
│       │               │              │              │  chunk 2      │
│       │               │              │◀─────────────│               │
│       │               │              │  yield chunk │               │
│       │               │  yield SSE   │              │               │
│       │               │◀─────────────│              │               │
│       │  data: chunk2 │              │              │               │
│       │◀──────────────│              │              │               │
│       │               │              │              │               │
│       │          ...  │              │              │  ...          │
│       │               │              │              │               │
│       │               │              │              │  [DONE]       │
│       │               │              │◀─────────────│               │
│       │               │              │  stream end  │               │
│       │               │  yield [DONE]│              │               │
│       │               │◀─────────────│              │               │
│       │  data: [DONE] │              │              │               │
│       │◀──────────────│              │              │               │
│       │               │              │              │               │
│       │  close stream │              │              │               │
│       │               │              │              │               │
└─────────────────────────────────────────────────────────────────────┘
```

### 11.3 SSE 事件类型定义

ThesisMiner v8.0 定义了 7 种 SSE 事件类型，覆盖流式输出的全生命周期：

| 事件类型 | 事件字段 | 数据格式 | 触发时机 | 前端处理 |
|---------|---------|---------|---------|---------|
| `meta` | event: meta | `{"agent_id": "...", "stage": "...", "model": "..."}` | 流开始 | 显示 Agent 信息与阶段 |
| `delta` | event: delta | `{"content": "增量文本"}` | 每个 chunk 到达 | 追加到输出区域 |
| `reasoning` | event: reasoning | `{"content": "推理文本"}` | DeepSeek R2 推理 | 显示推理过程（折叠） |
| `tool_call` | event: tool_call | `{"tool": "...", "args": {...}}` | 工具调用时 | 显示工具调用状态 |
| `usage` | event: usage | `{"prompt_tokens": N, "completion_tokens": N}` | 流结束时 | 更新 token 统计 |
| `error` | event: error | `{"code": "...", "message": "..."}` | 发生错误时 | 显示错误提示 |
| `done` | event: done | `{"result": {...}}` | 流正常结束 | 关闭流，处理最终结果 |

### 11.4 后端流式输出实现

```python
# backend/api/routes/conversations.py
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from backend.ai.proxy import AIProxy
from backend.agents.orchestrator import Orchestrator

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.post("/{conversation_id}/messages/stream")
async def send_message_stream(
    conversation_id: str,
    request: SendMessageRequest,
):
    """流式发送消息并接收 SSE 响应

    返回 StreamingResponse，Content-Type: text/event-stream
    """
    async def event_generator():
        # 1. 发送 meta 事件
        meta_event = {
            "agent_id": "orchestrator",
            "stage": "info_confirm",
            "model": "deepseek-chat",
            "timestamp": datetime.utcnow().isoformat(),
        }
        yield f"event: meta\ndata: {json.dumps(meta_event, ensure_ascii=False)}\n\n"

        # 2. 调用 Orchestrator 流式处理
        try:
            async for event in orchestrator.process_stream(
                conversation_id=conversation_id,
                user_message=request.content,
            ):
                event_type = event.get("type", "delta")
                event_data = event.get("data", {})
                yield f"event: {event_type}\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"

            # 3. 发送 done 事件
            done_event = {"result": "success", "conversation_id": conversation_id}
            yield f"event: done\ndata: {json.dumps(done_event, ensure_ascii=False)}\n\n"

        except Exception as e:
            # 4. 发送 error 事件
            error_event = {
                "code": "STREAM_ERROR",
                "message": str(e),
            }
            yield f"event: error\ndata: {json.dumps(error_event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx 关闭缓冲
        },
    )
```

### 11.5 AIProxy 流式转发

AIProxy 使用 httpx 的 `stream()` 方法接收 DeepSeek API 的流式响应，并将每个 chunk 转换为统一的事件格式后向上游 yield。

```python
# backend/ai/proxy.py
import httpx
import json
from typing import AsyncGenerator


class AIProxy:
    """AI 代理层，负责转发请求到 LLM API"""

    async def stream_chat(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncGenerator[dict, None]:
        """流式调用 LLM API

        Yields:
            事件字典，格式为 {"type": "...", "data": {...}}
        """
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            **kwargs,
        }

        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue

                    data_str = line[6:]  # 移除 "data: " 前缀

                    if data_str.strip() == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})

                        # 内容增量
                        if "content" in delta and delta["content"]:
                            yield {
                                "type": "delta",
                                "data": {"content": delta["content"]},
                            }

                        # 推理增量（DeepSeek R2）
                        if "reasoning_content" in delta and delta["reasoning_content"]:
                            yield {
                                "type": "reasoning",
                                "data": {"content": delta["reasoning_content"]},
                            }

                        # 用量统计（最后一个 chunk）
                        if "usage" in chunk:
                            yield {
                                "type": "usage",
                                "data": chunk["usage"],
                            }

                    except json.JSONDecodeError:
                        continue
```

### 11.6 前端 EventSource 消费

前端使用原生 `EventSource` API 或 `fetch` + `ReadableStream` 消费 SSE 流。由于 `EventSource` 仅支持 GET 请求，ThesisMiner v8.0 使用 `fetch` 配合 `ReadableStream` 来支持 POST 请求的流式消费。

```javascript
// frontend/js/sse_client.js
class SSEClient {
  constructor(url) {
    this.url = url;
    this.controller = null;
    this.handlers = new Map();
  }

  /**
   * 注册事件处理器
   * @param {string} eventType - 事件类型（meta/delta/reasoning/usage/error/done）
   * @param {Function} handler - 处理函数
   */
  on(eventType, handler) {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, []);
    }
    this.handlers.get(eventType).push(handler);
  }

  /**
   * 发起流式请求
   * @param {Object} body - 请求体
   */
  async connect(body) {
    this.controller = new AbortController();

    try {
      const response = await fetch(this.url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "text/event-stream",
        },
        body: JSON.stringify(body),
        signal: this.controller.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // 按 \n\n 分割 SSE 事件
        const events = buffer.split("\n\n");
        buffer = events.pop(); // 保留最后一个不完整的片段

        for (const eventStr of events) {
          this._dispatchEvent(eventStr);
        }
      }

      // 处理缓冲区中剩余的数据
      if (buffer.trim()) {
        this._dispatchEvent(buffer);
      }
    } catch (err) {
      if (err.name !== "AbortError") {
        this._emit("error", { code: "FETCH_ERROR", message: err.message });
      }
    }
  }

  /**
   * 解析并分发 SSE 事件
   */
  _dispatchEvent(eventStr) {
    const lines = eventStr.split("\n");
    let eventType = "message";
    let data = "";

    for (const line of lines) {
      if (line.startsWith("event: ")) {
        eventType = line.slice(7).trim();
      } else if (line.startsWith("data: ")) {
        data += line.slice(6);
      }
    }

    try {
      const parsed = JSON.parse(data);
      this._emit(eventType, parsed);
    } catch {
      // 非 JSON 数据，原样传递
      this._emit(eventType, data);
    }
  }

  _emit(eventType, data) {
    const handlers = this.handlers.get(eventType) || [];
    for (const handler of handlers) {
      handler(data);
    }
  }

  /**
   * 断开连接
   */
  disconnect() {
    if (this.controller) {
      this.controller.abort();
      this.controller = null;
    }
  }
}

// 使用示例
const sse = new SSEClient("/api/conversations/conv-123/messages/stream");
sse.on("meta", (data) => {
  console.log(`Agent: ${data.agent_id}, Stage: ${data.stage}`);
  updateAgentBadge(data.agent_id, data.stage);
});

sse.on("delta", (data) => {
  appendToOutput(data.content);
});

sse.on("reasoning", (data) => {
  appendToReasoningPanel(data.content);
});

sse.on("usage", (data) => {
  updateTokenCounter(data.prompt_tokens, data.completion_tokens);
});

sse.on("error", (data) => {
  showErrorToast(data.message);
});

sse.on("done", (data) => {
  finalizeOutput(data.result);
});

sse.connect({ content: "帮我生成3个关于大模型的论题" });
```

### 11.7 断线重连机制

网络不稳定可能导致 SSE 连接中断。ThesisMiner v8.0 实现了指数退避重连机制，在连接断开后自动尝试恢复。

```javascript
// frontend/js/sse_reconnect.js
class ReconnectingSSEClient extends SSEClient {
  constructor(url, options = {}) {
    super(url);
    this.maxRetries = options.maxRetries || 3;
    this.baseDelay = options.baseDelay || 1000;  // 1 秒
    this.maxDelay = options.maxDelay || 30000;   // 30 秒
    this.retryCount = 0;
    this.lastEventId = null;
  }

  async connectWithRetry(body) {
    while (this.retryCount < this.maxRetries) {
      try {
        await this.connect(body);
        this.retryCount = 0;  // 成功后重置计数
        return;
      } catch (err) {
        this.retryCount++;
        if (this.retryCount >= this.maxRetries) {
          this._emit("error", {
            code: "MAX_RETRIES_EXCEEDED",
            message: `重连失败，已达到最大重试次数 ${this.maxRetries}`,
          });
          return;
        }

        const delay = Math.min(
          this.baseDelay * Math.pow(2, this.retryCount - 1) +
            Math.random() * 1000,
          this.maxDelay
        );

        console.warn(`连接断开，${delay}ms 后重试 (${this.retryCount}/${this.maxRetries})`);
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    }
  }
}
```

---

## 12. 前端渲染数据流

### 12.1 前端渲染概述

前端渲染数据流负责将后端返回的结构化数据转换为用户可见的界面元素。ThesisMiner v8.0 的前端采用原生 JavaScript + Tailwind CSS + D3.js v7 技术栈，无框架依赖，通过事件驱动的方式管理 UI 状态更新。

### 12.2 前端渲染数据流架构

```
┌──────────────────────────────────────────────────────────────────┐
│                     前端渲染数据流                                 │
│                                                                  │
│  ┌──────────┐                                                    │
│  │ SSE 事件 │  event: delta / done / meta / error               │
│  └────┬─────┘                                                    │
│       │                                                          │
│       ▼                                                          │
│  ┌──────────────────┐                                            │
│  │ 事件分发器       │  根据事件类型路由到对应处理器               │
│  │ EventDispatcher  │                                            │
│  └────────┬─────────┘                                            │
│           │                                                      │
│     ┌─────┼─────┬──────┬──────┬──────┐                          │
│     │     │     │      │      │      │                          │
│     ▼     ▼     ▼      ▼      ▼      ▼                          │
│  ┌─────┐┌─────┐┌─────┐┌─────┐┌─────┐┌─────┐                     │
│  │meta ││delta││reas-││usage││error││done │                     │
│  │处理 ││处理 ││oning││处理 ││处理 ││处理 │                     │
│  └──┬──┘└──┬──┘└──┬──┘└──┬──┘└──┬──┘└──┬──┘                     │
│     │      │      │      │      │      │                        │
│     ▼      ▼      ▼      ▼      ▼      ▼                        │
│  ┌──────────────────────────────────────────┐                    │
│  │           DOM 更新层                     │                    │
│  │  - appendToOutput()    追加输出文本      │                    │
│  │  - updateAgentBadge()  更新 Agent 标签   │                    │
│  │  - updateTokenCounter()更新 token 计数   │                    │
│  │  - showErrorToast()    显示错误提示      │                    │
│  │  - renderLineageGraph()渲染谱系图        │                    │
│  │  - renderCandidates()  渲染候选论题      │                    │
│  └──────────────────┬───────────────────────┘                    │
│                     │                                            │
│                     ▼                                            │
│  ┌──────────────────────────────────────────┐                    │
│  │           D3.js 谱系图渲染               │                    │
│  │  - forceSimulation()  力导向布局         │                    │
│  │  - drag()             节点拖拽           │                    │
│  │  - zoom()             缩放               │                    │
│  │  - link/arrows        边与箭头           │                    │
│  └──────────────────────────────────────────┘                    │
└──────────────────────────────────────────────────────────────────┘
```

### 12.3 D3.js 谱系图渲染

谱系图是 ThesisMiner v8.0 的核心可视化组件，使用 D3.js v7 的力导向布局（force-directed layout）展示导师与论题之间的传承关系。

```javascript
// frontend/js/lineage_graph.js
class LineageGraph {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.width = this.container.clientWidth;
    this.height = 600;
    this.svg = null;
    this.simulation = null;
    this.nodes = [];
    this.links = [];
    this.init();
  }

  init() {
    // 创建 SVG 画布
    this.svg = d3.select(this.container)
      .append("svg")
      .attr("width", this.width)
      .attr("height", this.height)
      .attr("viewBox", [0, 0, this.width, this.height]);

    // 定义箭头标记
    const defs = this.svg.append("defs");
    defs.append("marker")
      .attr("id", "arrowhead")
      .attr("viewBox", "0 -5 10 10")
      .attr("refX", 20)
      .attr("refY", 0)
      .attr("markerWidth", 8)
      .attr("markerHeight", 8)
      .attr("orient", "auto")
      .append("path")
      .attr("d", "M0,-5L10,0L0,5")
      .attr("fill", "#6b7280");

    // 创建力导向模拟
    this.simulation = d3.forceSimulation()
      .force("link", d3.forceLink().id(d => d.id).distance(120))
      .force("charge", d3.forceManyBody().strength(-300))
      .force("center", d3.forceCenter(this.width / 2, this.height / 2))
      .force("collision", d3.forceCollide().radius(d => d.radius + 5));
  }

  /**
   * 渲染谱系图
   * @param {Object} graphData - {nodes: [...], links: [...]}
   */
  render(graphData) {
    this.nodes = graphData.nodes.map(d => ({ ...d }));
    this.links = graphData.links.map(d => ({ ...d }));

    // 绘制边
    const link = this.svg.selectAll(".link")
      .data(this.links)
      .enter()
      .append("line")
      .attr("class", "link")
      .attr("stroke", "#9ca3af")
      .attr("stroke-width", 1.5)
      .attr("marker-end", "url(#arrowhead)");

    // 绘制节点组
    const node = this.svg.selectAll(".node")
      .data(this.nodes)
      .enter()
      .append("g")
      .attr("class", "node")
      .call(this.drag(this.simulation));

    // 节点圆形
    node.append("circle")
      .attr("r", d => d.radius || 20)
      .attr("fill", d => this.getNodeColor(d.type))
      .attr("stroke", "#fff")
      .attr("stroke-width", 2);

    // 节点文本
    node.append("text")
      .text(d => d.label)
      .attr("x", 0)
      .attr("y", d => (d.radius || 20) + 15)
      .attr("text-anchor", "middle")
      .attr("font-size", "12px")
      .attr("fill", "#374151");

    // 更新力导向布局
    this.simulation
      .nodes(this.nodes)
      .on("tick", () => {
        link
          .attr("x1", d => d.source.x)
          .attr("y1", d => d.source.y)
          .attr("x2", d => d.target.x)
          .attr("y2", d => d.target.y);
        node.attr("transform", d => `translate(${d.x},${d.y})`);
      });

    this.simulation.force("link").links(this.links);
  }

  /**
   * 根据节点类型获取颜色
   */
  getNodeColor(type) {
    const colors = {
      advisor: "#3b82f6",      // 导师 - 蓝色
      student: "#10b981",      // 学生 - 绿色
      thesis: "#f59e0b",       // 论题 - 橙色
      topic: "#8b5cf6",        // 主题 - 紫色
    };
    return colors[type] || "#6b7280";
  }

  /**
   * 拖拽行为
   */
  drag(simulation) {
    const dragstarted = (event, d) => {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      d.fx = d.x;
      d.fy = d.y;
    };
    const dragged = (event, d) => {
      d.fx = event.x;
      d.fy = event.y;
    };
    const dragended = (event, d) => {
      if (!event.active) simulation.alphaTarget(0);
      d.fx = null;
      d.fy = null;
    };
    return d3.drag()
      .on("start", dragstarted)
      .on("drag", dragged)
      .on("end", dragended);
  }
}
```

### 12.4 候选论题渲染

当 Reasoner Agent 返回候选论题后，前端将候选列表渲染为可交互的卡片组件，用户可以点击选择或展开详情。

```javascript
// frontend/js/candidate_renderer.js
class CandidateRenderer {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
  }

  /**
   * 渲染候选论题列表
   * @param {Array} candidates - 候选论题数组
   */
  render(candidates) {
    this.container.innerHTML = "";
    candidates.forEach((candidate, index) => {
      const card = this.createCard(candidate, index);
      this.container.appendChild(card);
    });
  }

  createCard(candidate, index) {
    const card = document.createElement("div");
    card.className = "candidate-card bg-white rounded-lg shadow-md p-6 mb-4 hover:shadow-lg transition-shadow cursor-pointer";
    card.innerHTML = `
      <div class="flex items-start justify-between mb-3">
        <span class="dimension-badge px-3 py-1 rounded-full text-xs font-medium ${this.getDimensionClass(candidate.dimension)}">
          ${this.getDimensionLabel(candidate.dimension)}
        </span>
        <span class="text-gray-400 text-sm">#${index + 1}</span>
      </div>
      <h3 class="text-lg font-semibold text-gray-800 mb-2">${candidate.title}</h3>
      <p class="text-gray-600 text-sm leading-relaxed">${candidate.rationale}</p>
      ${this.renderScores(candidate)}
      <div class="mt-4 flex gap-2">
        <button class="select-btn px-4 py-2 bg-blue-500 text-white rounded-md text-sm hover:bg-blue-600 transition-colors"
                onclick="selectCandidate(${index})">
          选择此论题
        </button>
        <button class="detail-btn px-4 py-2 bg-gray-100 text-gray-700 rounded-md text-sm hover:bg-gray-200 transition-colors"
                onclick="showCandidateDetail(${index})">
          查看详情
        </button>
      </div>
    `;
    return card;
  }

  renderScores(candidate) {
    if (!candidate.feasibility && !candidate.novelty) return "";
    return `
      <div class="mt-3 flex gap-4">
        ${candidate.feasibility ? `
          <div class="flex items-center gap-1">
            <span class="text-xs text-gray-500">可行性</span>
            <span class="text-sm font-medium text-green-600">${candidate.feasibility}/10</span>
          </div>
        ` : ""}
        ${candidate.novelty ? `
          <div class="flex items-center gap-1">
            <span class="text-xs text-gray-500">新颖性</span>
            <span class="text-sm font-medium text-purple-600">${candidate.novelty}/10</span>
          </div>
        ` : ""}
      </div>
    `;
  }

  getDimensionLabel(dimension) {
    const labels = {
      new_application: "新应用场景",
      method_fusion: "方法融合",
      cross_discipline: "跨学科",
      theory_extension: "理论延伸",
    };
    return labels[dimension] || dimension;
  }

  getDimensionClass(dimension) {
    const classes = {
      new_application: "bg-blue-100 text-blue-700",
      method_fusion: "bg-green-100 text-green-700",
      cross_discipline: "bg-purple-100 text-purple-700",
      theory_extension: "bg-orange-100 text-orange-700",
    };
    return classes[dimension] || "bg-gray-100 text-gray-700";
  }
}
```

---

## 13. 五阶段数据流详解

### 13.1 信息确权阶段（INFO_CONFIRM）

信息确权是五阶段闭环导航的第一个阶段，负责收集和确认用户的基本信息（学位、学科、导师、时间约束等），为后续的创意生成提供上下文基础。

```
┌──────────────────────────────────────────────────────────────────┐
│                  信息确权阶段数据流                                │
│                                                                  │
│  用户输入          Orchestrator          Mentor Agent             │
│     │                   │                      │                 │
│     │  "我是硕士生"     │                      │                 │
│     │──────────────────▶│                      │                 │
│     │                   │                      │                 │
│     │                   │  提取信息             │                 │
│     │                   │  degree=master       │                 │
│     │                   │                      │                 │
│     │                   │  调用 Mentor         │                 │
│     │                   │─────────────────────▶│                 │
│     │                   │                      │                 │
│     │                   │                      │  分析缺失字段   │
│     │                   │                      │  - discipline?  │
│     │                   │                      │  - advisor?     │
│     │                   │                      │  - timeline?    │
│     │                   │                      │                 │
│     │                   │  追问问题             │                 │
│     │                   │◀─────────────────────│                 │
│     │                   │                      │                 │
│     │  "你的学科是？"  │                      │                 │
│     │◀──────────────────│                      │                 │
│     │                   │                      │                 │
│     │  "计算机科学"    │                      │                 │
│     │──────────────────▶│                      │                 │
│     │                   │                      │                 │
│     │                   │  更新 DST            │                 │
│     │                   │  discipline=CS       │                 │
│     │                   │                      │                 │
│     │                   │  所有字段已确认       │                 │
│     │                   │  → 触发 USER_CONFIRM │                 │
│     │                   │  → 进入 CREATIVITY   │                 │
│     │                   │                      │                 │
└──────────────────────────────────────────────────────────────────┘
```

**输入数据**：
- 用户自然语言消息
- 当前 DST 状态（可能为空）

**输出数据**：
- 更新后的 DST（包含 degree、discipline、advisor、timeline 等字段）
- 确认完成事件（USER_CONFIRM）

**状态变更**：
- `Stage.INFO_CONFIRM` → `Stage.CREATIVITY`

### 13.2 创意阶段（CREATIVITY）

创意阶段调用 Reasoner Agent 基于已确认的用户信息生成 3-5 个候选论题，每个论题标注创意维度（新应用/方法融合/跨学科/理论延伸）。

```python
# backend/agents/orchestrator.py - 创意阶段处理
async def _handle_creativity(self, dst: DialogueState) -> AsyncGenerator[dict, None]:
    """创意阶段：调用 Reasoner 生成候选论题"""

    # 1. 构建 Reasoner 的输入
    reasoner_input = {
        "degree": dst.degree,
        "discipline": dst.discipline,
        "advisor": dst.advisor,
        "timeline": dst.timeline,
        "constraints": dst.constraints,
    }

    # 2. 调用 Reasoner Agent（流式）
    async for event in self.reasoner.run_stream(reasoner_input):
        yield event  # 转发 delta/reasoning 事件到前端

    # 3. 获取 Reasoner 的最终结果
    result = self.reasoner.get_result()  # CreativityResult

    # 4. 持久化候选论题
    for candidate in result.candidates:
        self.db.save_proposal(
            session_id=dst.session_id,
            title=candidate.title,
            dimension=candidate.dimension.value,
            rationale=candidate.rationale,
            stage="creativity",
        )

    # 5. 触发状态转换
    self.state_machine.trigger(Event.CANDIDATES_GENERATED)
    yield {
        "type": "stage_transition",
        "data": {
            "from": "creativity",
            "to": "validation",
            "candidates_count": len(result.candidates),
        },
    }
```

**输入数据**：
- DST（degree、discipline、advisor、timeline、constraints）

**输出数据**：
- 候选论题列表（3-5 个，每个含 title、dimension、rationale）
- 持久化到 proposals 表

**状态变更**：
- `Stage.CREATIVITY` → `Stage.VALIDATION`

### 13.3 校验阶段（VALIDATION）

校验阶段调用 Critic Agent 对候选论题进行多维度评估（可行性、新颖性、文献基线、时间可行性），并根据评分决定是否通过或回退到创意阶段。

```
┌──────────────────────────────────────────────────────────────────┐
│                  校验阶段数据流                                    │
│                                                                  │
│  候选论题         Critic Agent         评分引擎         状态机    │
│     │                  │                   │               │      │
│     │  candidates      │                   │               │      │
│     │─────────────────▶│                   │               │      │
│     │                  │                   │               │      │
│     │                  │  评估每个论题     │               │      │
│     │                  │  - 可行性 1-10    │               │      │
│     │                  │  - 新颖性 1-10    │               │      │
│     │                  │  - 文献基线       │               │      │
│     │                  │  - 时间可行性     │               │      │
│     │                  │                   │               │      │
│     │                  │  evaluations      │               │      │
│     │                  │──────────────────▶│               │      │
│     │                  │                   │               │      │
│     │                  │                   │  计算总分     │      │
│     │                  │                   │  best_index   │      │
│     │                  │                   │               │      │
│     │                  │                   │  总分 ≥ 阈值? │      │
│     │                  │                   │────┐          │      │
│     │                  │                   │    │          │      │
│     │                  │                   │◀───┘          │      │
│     │                  │                   │               │      │
│     │                  │                   │  SCORE_PASS   │      │
│     │                  │                   │──────────────▶│      │
│     │                  │                   │               │      │
│     │                  │                   │               │  → GENERATION
│     │                  │                   │               │      │
│     │                  │                   │  SCORE_FAIL   │      │
│     │                  │                   │──────────────▶│      │
│     │                  │                   │               │      │
│     │                  │                   │               │  → CREATIVITY (回退)
│     │                  │                   │               │      │
└──────────────────────────────────────────────────────────────────┘
```

**输入数据**：
- 候选论题列表

**输出数据**：
- 评估结果（每个论题的评分与推荐意见）
- 最佳候选索引
- 通过/失败事件

**状态变更**：
- 通过：`Stage.VALIDATION` → `Stage.GENERATION`
- 失败：`Stage.VALIDATION` → `Stage.CREATIVITY`（回退）

### 13.4 生成阶段（GENERATION）

生成阶段调用 Writer Agent 基于最佳候选论题生成完整的开题报告，包含研究背景、文献综述、研究内容、技术路线、预期成果等章节。

```python
# backend/agents/orchestrator.py - 生成阶段处理
async def _handle_generation(self, dst: DialogueState) -> AsyncGenerator[dict, None]:
    """生成阶段：调用 Writer 生成开题报告"""

    best_candidate = dst.get_best_candidate()

    # 1. 构建 Writer 的输入
    writer_input = {
        "title": best_candidate.title,
        "dimension": best_candidate.dimension,
        "rationale": best_candidate.rationale,
        "degree": dst.degree,
        "discipline": dst.discipline,
        "timeline": dst.timeline,
        "evaluations": dst.evaluations,
    }

    # 2. 调用 Writer Agent（流式生成报告）
    async for event in self.writer.run_stream(writer_input):
        yield event  # 转发 delta 事件到前端

    # 3. 获取完整报告
    report = self.writer.get_result()

    # 4. 持久化报告
    self.db.update_proposal(
        proposal_id=best_candidate.id,
        stage="generation",
        report_content=report.content,
        report_sections=report.sections,
    )

    # 5. 触发状态转换
    self.state_machine.trigger(Event.GENERATION_DONE)
    yield {
        "type": "stage_transition",
        "data": {
            "from": "generation",
            "to": "deep_assist",
            "report_length": len(report.content),
        },
    }
```

### 13.5 深度辅助阶段（DEEP_ASSIST）

深度辅助阶段提供文献精读、实验预研、答辩模拟等扩展功能，用户可以选择进入或重置开始新的会话。

**状态变更**：
- 重置：`Stage.DEEP_ASSIST` → `Stage.INFO_CONFIRM`

---

## 14. 多对话上下文隔离数据流

### 14.1 多对话隔离概述

ThesisMiner v8.0 支持单个会话下创建多个对话（conversation），每个对话拥有独立的上下文与 DST 状态。多对话隔离确保用户可以同时探索多个论题方向，互不干扰。

### 14.2 上下文隔离架构

```
┌──────────────────────────────────────────────────────────────────┐
│                  多对话上下文隔离架构                              │
│                                                                  │
│                     ┌──────────────┐                             │
│                     │   Session    │                             │
│                     │  session-001 │                             │
│                     └──────┬───────┘                             │
│                            │                                     │
│              ┌─────────────┼─────────────┐                       │
│              │             │             │                       │
│              ▼             ▼             ▼                       │
│      ┌──────────┐  ┌──────────┐  ┌──────────┐                   │
│      │ Conv-A   │  │ Conv-B   │  │ Conv-C   │                   │
│      │ 大模型   │  │ 数据挖掘 │  │ 跨学科   │                   │
│      │ 方向     │  │ 方向     │  │ 方向     │                   │
│      └────┬─────┘  └────┬─────┘  └────┬─────┘                   │
│           │             │             │                         │
│           ▼             ▼             ▼                         │
│      ┌──────────┐  ┌──────────┐  ┌──────────┐                   │
│      │ DST-A    │  │ DST-B    │  │ DST-C    │                   │
│      │ degree=  │  │ degree=  │  │ degree=  │                   │
│      │  master  │  │  phd     │  │  master  │                   │
│      │ disc=CS  │  │ disc=CS  │  │ disc=CS  │                   │
│      │ stage=   │  │ stage=   │  │ stage=   │                   │
│      │ creative │  │ validat  │  │ info     │                   │
│      └──────────┘  └──────────┘  └──────────┘                   │
│           │             │             │                         │
│           ▼             ▼             ▼                         │
│      ┌──────────┐  ┌──────────┐  ┌──────────┐                   │
│      │ Messages │  │ Messages │  │ Messages │                   │
│      │  [m1,m2, │  │  [m1,m2, │  │  [m1]    │                   │
│      │   m3...] │  │   m3...] │  │          │                   │
│      └──────────┘  └──────────┘  └──────────┘                   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 14.3 对话隔离实现

```python
# backend/sessions/conversation_manager.py
import sqlite3
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class ConversationContext:
    """对话上下文：每个对话独立的 DST 与消息历史"""
    conversation_id: str
    session_id: str
    dst: DialogueState
    messages: list[dict] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class ConversationManager:
    """多对话管理器：负责对话的创建、切换、隔离"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._context_cache: dict[str, ConversationContext] = {}

    def create_conversation(
        self,
        session_id: str,
        title: str = "新对话",
    ) -> str:
        """创建新对话，返回 conversation_id"""
        conversation_id = f"conv-{uuid4().hex[:12]}"
        now = datetime.utcnow().isoformat()

        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT INTO conversations
                (id, session_id, title, dst_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (conversation_id, session_id, title, "{}", now, now),
        )
        conn.commit()
        conn.close()

        # 初始化上下文缓存
        self._context_cache[conversation_id] = ConversationContext(
            conversation_id=conversation_id,
            session_id=session_id,
            dst=DialogueState(session_id=session_id),
            created_at=now,
            updated_at=now,
        )

        return conversation_id

    def get_context(self, conversation_id: str) -> Optional[ConversationContext]:
        """获取对话上下文（优先从缓存读取）"""
        if conversation_id in self._context_cache:
            return self._context_cache[conversation_id]

        # 缓存未命中，从数据库加载
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        conn.close()

        if not row:
            return None

        # 反序列化 DST
        dst = DialogueState.from_json(row["dst_json"])
        context = ConversationContext(
            conversation_id=row["id"],
            session_id=row["session_id"],
            dst=dst,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

        # 加载消息历史
        context.messages = self._load_messages(conversation_id)

        # 写入缓存
        self._context_cache[conversation_id] = context
        return context

    def save_context(self, conversation_id: str):
        """持久化对话上下文到数据库"""
        context = self._context_cache.get(conversation_id)
        if not context:
            return

        now = datetime.utcnow().isoformat()
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            UPDATE conversations
            SET dst_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (context.dst.to_json(), now, conversation_id),
        )
        conn.commit()
        conn.close()

    def switch_conversation(
        self,
        session_id: str,
        target_conversation_id: str,
    ) -> Optional[ConversationContext]:
        """切换到目标对话（验证归属权）"""
        context = self.get_context(target_conversation_id)
        if not context or context.session_id != session_id:
            return None  # 不属于当前会话
        return context
```

---

## 15. DST 压缩算法

### 15.1 DST 压缩概述

Dialogue State Tracker（DST）是 ThesisMiner v8.0 管理对话状态的核心数据结构。随着对话轮次增加，DST 中的消息历史会不断增长，导致 Prompt token 数量膨胀、缓存命中率下降。DST 压缩算法通过摘要提取、关键字段保留、历史消息归档等方式，将长对话压缩为紧凑的状态表示。

### 15.2 DST 压缩触发条件

```python
# backend/sessions/dst_compressor.py
class DSTCompressor:
    """DST 压缩器"""

    # 压缩触发阈值
    MAX_MESSAGE_COUNT = 20       # 消息数超过 20 条时触发
    MAX_TOKEN_ESTIMATE = 8000    # 估算 token 超过 8000 时触发
    MAX_CHAR_COUNT = 32000       # 字符数超过 32000 时触发

    def should_compress(self, dst: DialogueState) -> tuple[bool, str]:
        """判断是否需要压缩"""
        message_count = len(dst.messages)
        char_count = sum(len(m.get("content", "")) for m in dst.messages)
        token_estimate = char_count // 4  # 粗略估算：4 字符 ≈ 1 token

        if message_count >= self.MAX_MESSAGE_COUNT:
            return True, f"消息数 {message_count} 超过阈值 {self.MAX_MESSAGE_COUNT}"
        if token_estimate >= self.MAX_TOKEN_ESTIMATE:
            return True, f"估算 token {token_estimate} 超过阈值 {self.MAX_TOKEN_ESTIMATE}"
        if char_count >= self.MAX_CHAR_COUNT:
            return True, f"字符数 {char_count} 超过阈值 {self.MAX_CHAR_COUNT}"

        return False, ""
```

### 15.3 DST 压缩算法实现

```python
# backend/sessions/dst_compressor.py
from datetime import datetime


class DSTCompressor:
    """DST 压缩器：将长对话历史压缩为摘要 + 关键字段"""

    def compress(self, dst: DialogueState) -> DialogueState:
        """执行 DST 压缩

        压缩策略：
        1. 保留最近 N 条消息（N=5）不压缩
        2. 将较早的消息通过 LLM 生成摘要
        3. 保留所有结构化字段（degree/discipline/advisor 等）
        4. 将压缩前的完整历史归档到数据库
        """
        messages = dst.messages
        if len(messages) <= 5:
            return dst  # 消息较少，无需压缩

        # 1. 分割消息：需要压缩的旧消息 + 保留的新消息
        old_messages = messages[:-5]
        recent_messages = messages[-5:]

        # 2. 归档完整历史
        self._archive_messages(dst.conversation_id, old_messages)

        # 3. 生成摘要（调用 LLM）
        summary = self._generate_summary(old_messages, dst)

        # 4. 构建压缩后的消息列表
        compressed_messages = [
            {
                "role": "system",
                "content": f"[对话历史摘要]\n{summary}\n[以下是最近的对话]",
            }
        ] + recent_messages

        # 5. 更新 DST
        dst.messages = compressed_messages
        dst.compressed = True
        dst.compression_count += 1
        dst.last_compressed_at = datetime.utcnow().isoformat()

        return dst

    def _generate_summary(self, messages: list[dict], dst: DialogueState) -> str:
        """调用 LLM 生成对话摘要"""
        summary_prompt = f"""请将以下对话历史压缩为一段简洁的摘要，保留关键信息：

用户背景：学位={dst.degree}, 学科={dst.discipline}
当前阶段：{dst.stage}

对话历史：
"""
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            summary_prompt += f"\n[{role}]: {content[:200]}...\n"

        summary_prompt += "\n请生成 200 字以内的摘要，保留：用户需求、已确认的信息、已生成的论题、评估结果。"

        # 调用 LLM（使用低成本模型）
        response = self.ai_proxy.chat(
            messages=[{"role": "user", "content": summary_prompt}],
            model="deepseek-chat",
            temperature=0.1,
            max_tokens=500,
        )
        return response.content

    def _archive_messages(self, conversation_id: str, messages: list[dict]):
        """将压缩前的消息归档到数据库"""
        conn = sqlite3.connect(self.db_path)
        for msg in messages:
            conn.execute(
                """
                INSERT INTO archived_messages
                    (conversation_id, role, content, archived_at)
                VALUES (?, ?, ?, ?)
                """,
                (conversation_id, msg["role"], msg["content"], datetime.utcnow().isoformat()),
            )
        conn.commit()
        conn.close()
```

### 15.4 DST 压缩数据流

```
┌──────────────────────────────────────────────────────────────────┐
│                    DST 压缩数据流                                  │
│                                                                  │
│  ┌──────────────┐                                                │
│  │ 原始 DST     │  messages: [m1, m2, ..., m20]  (20 条)         │
│  │ (膨胀状态)   │  char_count: 35000  token_est: 8750            │
│  └──────┬───────┘                                                │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────┐                                                │
│  │ 触发判断     │  should_compress()? → True (token > 8000)     │
│  └──────┬───────┘                                                │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────┐                                                │
│  │ 消息分割     │  old = [m1..m15]  recent = [m16..m20]          │
│  └──────┬───────┘                                                │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────┐                                                │
│  │ 归档旧消息   │  INSERT INTO archived_messages                 │
│  └──────┬───────┘                                                │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────┐                                                │
│  │ LLM 摘要生成 │  调用 deepseek-chat 生成 200 字摘要            │
│  └──────┬───────┘                                                │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────┐                                                │
│  │ 构建压缩 DST │  messages = [summary_msg, m16..m20]  (6 条)   │
│  │              │  char_count: 5000  token_est: 1250             │
│  └──────┬───────┘                                                │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────┐                                                │
│  │ 持久化       │  UPDATE conversations SET dst_json = ?         │
│  └──────────────┘                                                │
│                                                                  │
│  压缩效果：token 8750 → 1250 (减少 85.7%)                        │
└──────────────────────────────────────────────────────────────────┘
```

---

## 16. 缓存命中数据流

### 16.1 缓存命中概述

DeepSeek API 支持 Prompt 缓存机制：当请求的 Prompt 前缀与之前请求完全一致时，缓存命中的 token 按 1/10 价格计费。ThesisMiner v8.0 通过三段式 Prompt 架构（prefix/dynamic/tail）和 SHA-256 前缀哈希，确保 ≥95% 的缓存命中率。

### 16.2 缓存命中数据流

```
┌──────────────────────────────────────────────────────────────────┐
│                    缓存命中数据流                                  │
│                                                                  │
│  ┌──────────────┐                                                │
│  │ 构建消息列表 │  [system_prompt, user_msg_1, user_msg_2, ...]  │
│  └──────┬───────┘                                                │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────────┐                                            │
│  │ 三段式分割       │  prefix = system_prompt + 固化上下文       │
│  │ split_segments() │  dynamic = 动态上下文（DST 摘要）          │
│  │                  │  tail = 当前用户消息                       │
│  └────────┬─────────┘                                            │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────┐                                            │
│  │ SHA-256 前缀哈希 │  prefix_hash = sha256(prefix)[:16]         │
│  └────────┬─────────┘                                            │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────┐                                            │
│  │ 缓存查询         │  cached = cache.get(prefix_hash)           │
│  └────────┬─────────┘                                            │
│           │                                                      │
│     ┌─────┴─────┐                                                │
│     │           │                                                │
│     ▼           ▼                                                │
│  ┌──────┐   ┌──────────┐                                        │
│  │ 命中 │   │ 未命中   │                                        │
│  └──┬───┘   └────┬─────┘                                        │
│     │            │                                               │
│     ▼            ▼                                               │
│  ┌──────────┐  ┌──────────────┐                                  │
│  │ 使用缓存 │  │ 发送完整     │                                  │
│  │ 前缀     │  │ prefix      │                                  │
│  │ cached_  │  │ 并缓存      │                                  │
│  │ prompt_  │  │ cache.set(  │                                  │
│  │ tokens   │  │   hash,     │                                  │
│  │ = true   │  │   prefix)   │                                  │
│  └────┬─────┘  └──────┬──────┘                                  │
│       │               │                                          │
│       ▼               ▼                                          │
│  ┌────────────────────────┐                                      │
│  │ 发送到 DeepSeek API    │                                      │
│  │ POST /chat/completions │                                      │
│  └────────────┬───────────┘                                      │
│               │                                                  │
│               ▼                                                  │
│  ┌────────────────────────┐                                      │
│  │ 响应包含 usage         │                                      │
│  │ prompt_tokens: 5000    │                                      │
│  │ cached_prompt_tokens:  │                                      │
│  │   4800 (96%)           │                                      │
│  └────────────┬───────────┘                                      │
│               │                                                  │
│               ▼                                                  │
│  ┌────────────────────────┐                                      │
│  │ 记录预算               │                                      │
│  │ - prompt_cost: 200 tok │                                      │
│  │ - cached_cost: 4800 tok│                                      │
│  │ - cache_hit_rate: 96%  │                                      │
│  └────────────────────────┘                                      │
└──────────────────────────────────────────────────────────────────┘
```

### 16.3 缓存命中统计

```python
# backend/ai/cache_tracker.py
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class CacheStats:
    """缓存命中统计"""
    total_requests: int = 0
    cache_hit_requests: int = 0
    total_prompt_tokens: int = 0
    total_cached_tokens: int = 0

    @property
    def hit_rate(self) -> float:
        """缓存命中率（按请求数）"""
        if self.total_requests == 0:
            return 0.0
        return self.cache_hit_requests / self.total_requests

    @property
    def token_hit_rate(self) -> float:
        """缓存命中率（按 token 数）"""
        if self.total_prompt_tokens == 0:
            return 0.0
        return self.total_cached_tokens / self.total_prompt_tokens


class CacheTracker:
    """缓存命中追踪器"""

    def __init__(self):
        self.stats: dict[str, CacheStats] = defaultdict(CacheStats)

    def record(
        self,
        agent_id: str,
        prompt_tokens: int,
        cached_tokens: int,
    ):
        """记录一次 API 调用的缓存命中情况"""
        stats = self.stats[agent_id]
        stats.total_requests += 1
        stats.total_prompt_tokens += prompt_tokens
        stats.total_cached_tokens += cached_tokens
        if cached_tokens > 0:
            stats.cache_hit_requests += 1

    def get_report(self) -> dict:
        """生成缓存命中报告"""
        report = {}
        for agent_id, stats in self.stats.items():
            report[agent_id] = {
                "total_requests": stats.total_requests,
                "hit_rate": f"{stats.hit_rate:.1%}",
                "token_hit_rate": f"{stats.token_hit_rate:.1%}",
                "total_prompt_tokens": stats.total_prompt_tokens,
                "total_cached_tokens": stats.total_cached_tokens,
                "estimated_savings": f"${self._calc_savings(stats):.4f}",
            }
        return report

    def _calc_savings(self, stats: CacheStats) -> float:
        """计算节省的费用"""
        # 正常 prompt: $0.14/1M, 缓存 prompt: $0.014/1M
        normal_cost = stats.total_prompt_tokens * 0.14 / 1_000_000
        actual_cost = (
            (stats.total_prompt_tokens - stats.total_cached_tokens) * 0.14 / 1_000_000
            + stats.total_cached_tokens * 0.014 / 1_000_000
        )
        return normal_cost - actual_cost
```

---

## 17. 错误处理数据流

### 17.1 错误处理概述

ThesisMiner v8.0 的错误处理数据流覆盖从用户请求到 AI 响应的全链路，采用分层捕获、分类处理、优雅降级的策略，确保系统在异常情况下仍能提供可用响应。

### 17.2 错误分类与处理策略

| 错误类别 | 错误码 | 触发场景 | 处理策略 | HTTP 状态码 |
|---------|--------|---------|---------|------------|
| 请求校验错误 | VALIDATION_ERROR | Pydantic 校验失败 | 返回字段级错误详情 | 422 |
| 认证错误 | AUTH_ERROR | API Key 缺失/无效 | 返回认证失败提示 | 401 |
| 权限错误 | FORBIDDEN | 会话归属权校验失败 | 返回无权访问提示 | 403 |
| 资源不存在 | NOT_FOUND | 会话/对话/论题不存在 | 返回资源不存在提示 | 404 |
| 速率限制 | RATE_LIMIT | 请求频率超限 | 返回重试等待时间 | 429 |
| AI 调用错误 | AI_ERROR | LLM API 返回错误 | 重试 3 次后降级 | 502 |
| AI 超时 | AI_TIMEOUT | LLM 响应超时（>120s） | 重试 1 次后降级 | 504 |
| JSON 解析错误 | PARSE_ERROR | LLM 返回非 JSON | json_repair 修复 | 200（降级） |
| 硬约束拦截 | CONSTRAINT_VIOLATION | 请求违反硬约束 | 返回违规详情 | 422 |
| 内部错误 | INTERNAL_ERROR | 未捕获异常 | 记录日志，返回通用错误 | 500 |

### 17.3 错误处理数据流

```
┌──────────────────────────────────────────────────────────────────┐
│                    错误处理数据流                                  │
│                                                                  │
│  请求 → 中间件 → 路由 → 业务逻辑 → AI 调用 → 响应                │
│           │        │        │          │                          │
│           │        │        │          │  AI_ERROR / AI_TIMEOUT   │
│           │        │        │          │────┐                     │
│           │        │        │          │    │                     │
│           │        │        │          │◀───┘                     │
│           │        │        │          │                          │
│           │        │        │          ▼                          │
│           │        │        │    ┌──────────┐                     │
│           │        │        │    │ 重试机制 │                     │
│           │        │        │    │ max=3    │                     │
│           │        │        │    │ delay=2s │                     │
│           │        │        │    └────┬─────┘                     │
│           │        │        │         │                           │
│           │        │        │    ┌────┴─────┐                     │
│           │        │        │    │ 重试成功?│                     │
│           │        │        │    └────┬─────┘                     │
│           │        │        │    ┌────┴────┐  是                  │
│           │        │        │    │         ├────→ 正常响应        │
│           │        │        │    │ 否      │                     │
│           │        │        │    └────┬────┘                     │
│           │        │        │         │ 否                       │
│           │        │        │         ▼                          │
│           │        │        │    ┌──────────┐                     │
│           │        │        │    │ 降级策略 │                     │
│           │        │        │    │ - 备用模型│                    │
│           │        │        │    │ - 空结果 │                     │
│           │        │        │    │ - 缓存   │                     │
│           │        │        │    └────┬─────┘                     │
│           │        │        │         │                           │
│           │        │        │         ▼                          │
│           │  VALIDATION_ERROR / CONSTRAINT_VIOLATION              │
│           │        │        │                                     │
│           │        │        ▼                                     │
│           │        │  ┌──────────────┐                           │
│           │        │  │ HTTPException│                           │
│           │        │  │ 422 / 429    │                           │
│           │        │  └──────────────┘                           │
│           │        │                                              │
│           │        ▼                                              │
│           │  ┌──────────────┐                                    │
│           │  │ 路由级错误   │                                    │
│           │  │ 404 / 403    │                                    │
│           │  └──────────────┘                                    │
│           │                                                      │
│           ▼                                                      │
│      ┌──────────────┐                                            │
│      │ 全局异常处理 │  INTERNAL_ERROR → 500                      │
│      └──────────────┘                                            │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 17.4 全局异常处理中间件

```python
# backend/api/middleware/error_handler.py
import logging
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

logger = logging.getLogger(__name__)


async def global_exception_handler(request: Request, exc: Exception):
    """全局未捕获异常处理器"""
    logger.exception(f"未捕获异常: {exc}", extra={
        "path": request.url.path,
        "method": request.method,
    })
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "服务器内部错误，请稍后重试",
                "request_id": getattr(request.state, "request_id", "unknown"),
            }
        },
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """请求校验异常处理器"""
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "请求参数校验失败",
                "details": exc.errors(),
            }
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP 异常处理器"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.detail.get("code", "HTTP_ERROR") if isinstance(exc.detail, dict) else "HTTP_ERROR",
                "message": exc.detail.get("message", str(exc.detail)) if isinstance(exc.detail, dict) else str(exc.detail),
            }
        },
    )
```

---

## 18. 重试机制

### 18.1 重试机制概述

当 AI 调用失败时（网络错误、5xx 错误、超时），ThesisMiner v8.0 采用指数退避重试机制，最多重试 3 次，每次间隔按 2^n 秒递增（2s → 4s → 8s），并加入随机抖动（jitter）避免雪崩。

### 18.2 重试机制实现

```python
# backend/ai/retry.py
import asyncio
import random
from functools import wraps
from typing import Callable, Type, Tuple
import httpx


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 30.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (
        httpx.TimeoutException,
        httpx.ConnectError,
        httpx.HTTPStatusError,
    ),
):
    """指数退避重试装饰器

    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟（秒）
        max_delay: 最大延迟（秒）
        retryable_exceptions: 可重试的异常类型
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt >= max_retries:
                        logger.error(
                            f"重试 {max_retries} 次后仍失败: {e}",
                            extra={"function": func.__name__, "attempt": attempt},
                        )
                        raise

                    # 计算延迟：base * 2^attempt + jitter
                    delay = min(
                        base_delay * (2 ** attempt) + random.uniform(0, 1),
                        max_delay,
                    )
                    logger.warning(
                        f"第 {attempt + 1} 次重试，{delay:.1f}s 后执行: {e}",
                        extra={"function": func.__name__, "attempt": attempt, "delay": delay},
                    )
                    await asyncio.sleep(delay)

            raise last_exception
        return wrapper
    return decorator


# 使用示例
class AIProxy:
    @retry_with_backoff(max_retries=3, base_delay=2.0)
    async def chat(self, messages: list[dict], model: str, **kwargs) -> dict:
        """带重试的 LLM 调用"""
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json={"model": model, "messages": messages, **kwargs},
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()
            return response.json()
```

### 18.3 重试数据流时序图

```
 调用方      AIProxy      DeepSeek API
   │           │               │
   │  chat()   │               │
   │──────────▶│               │
   │           │  POST         │
   │           │──────────────▶│
   │           │               │
   │           │  503 错误     │
   │           │◀──────────────│
   │           │               │
   │           │  重试1 (2s后) │
   │           │  ────┐        │
   │           │      │ 2s     │
   │           │◀─────┘        │
   │           │  POST         │
   │           │──────────────▶│
   │           │               │
   │           │  503 错误     │
   │           │◀──────────────│
   │           │               │
   │           │  重试2 (4s后) │
   │           │  ────┐        │
   │           │      │ 4s     │
   │           │◀─────┘        │
   │           │  POST         │
   │           │──────────────▶│
   │           │               │
   │           │  200 成功     │
   │           │◀──────────────│
   │           │               │
   │  result   │               │
   │◀──────────│               │
   │           │               │
```

---

## 19. 降级策略

### 19.1 降级策略概述

当重试耗尽后仍无法成功调用 AI 时，ThesisMiner v8.0 启动降级策略，确保系统可用性。降级策略按优先级分为：备用模型切换 → 缓存响应返回 → 空结果返回 → 错误提示。

### 19.2 降级策略实现

```python
# backend/ai/fallback.py
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class FallbackManager:
    """降级管理器"""

    # 模型降级链：主模型 → 备用模型1 → 备用模型2
    MODEL_FALLBACK_CHAIN = {
        "deepseek-reasoner": ["deepseek-chat", "gpt-4o-mini"],
        "deepseek-chat": ["gpt-4o-mini", "qwen-plus"],
        "gpt-4.1": ["deepseek-chat", "qwen-plus"],
    }

    async def call_with_fallback(
        self,
        messages: list[dict],
        primary_model: str,
        **kwargs,
    ) -> Optional[dict]:
        """带降级的 AI 调用

        降级顺序：
        1. 主模型（已重试 3 次失败）
        2. 备用模型1
        3. 备用模型2
        4. 返回 None（由调用方处理空结果）
        """
        fallback_chain = self.MODEL_FALLBACK_CHAIN.get(
            primary_model, [primary_model]
        )
        all_models = [primary_model] + fallback_chain

        for i, model in enumerate(all_models):
            try:
                if i == 0:
                    continue  # 主模型已在重试中调用过

                logger.info(f"降级到备用模型: {model}")
                result = await self.ai_proxy.chat(
                    messages=messages,
                    model=model,
                    **kwargs,
                )
                logger.info(f"备用模型 {model} 调用成功")
                return result

            except Exception as e:
                logger.warning(f"备用模型 {model} 调用失败: {e}")
                continue

        # 所有模型都失败，返回降级响应
        logger.error("所有模型均不可用，返回降级响应")
        return self._get_degraded_response(messages, primary_model)

    def _get_degraded_response(
        self,
        messages: list[dict],
        model: str,
    ) -> dict:
        """构造降级响应"""
        return {
            "content": "抱歉，AI 服务暂时不可用。请稍后重试或联系管理员。",
            "model": f"{model} (degraded)",
            "usage": {"prompt_tokens": 0, "completion_tokens": 0},
            "degraded": True,
        }
```

---

## 20. 性能关键路径分析

### 20.1 关键路径定义

性能关键路径是指从用户发送请求到收到首个响应字节（TTFB）所经过的最长链路。ThesisMiner v8.0 的关键路径为：

```
用户请求 → Uvicorn → FastAPI 路由 → 中间件链 → Orchestrator → Agent → AIProxy → DeepSeek API → 首个 chunk
```

### 20.2 关键路径耗时分析

| 阶段 | 平均耗时 | P95 耗时 | 占比 | 优化空间 |
|------|---------|---------|------|---------|
| Uvicorn 接收 | 1ms | 3ms | 0.02% | 极小 |
| FastAPI 路由匹配 | 2ms | 5ms | 0.03% | 极小 |
| 中间件链（CORS/日志/限流） | 5ms | 10ms | 0.08% | 小 |
| Orchestrator 状态机 | 3ms | 8ms | 0.05% | 小 |
| Agent Prompt 构建 | 10ms | 20ms | 0.16% | 中（缓存优化） |
| AIProxy HTTP 连接 | 50ms | 200ms | 3.3% | 中（连接池复用） |
| DeepSeek API TTFB | 1200ms | 3000ms | 95% | 大（模型优化） |
| **总计（TTFB）** | **1271ms** | **3246ms** | 100% | - |

### 20.3 性能瓶颈识别

```
┌──────────────────────────────────────────────────────────────────┐
│                  性能瓶颈分布（TTFB 3246ms）                      │
│                                                                  │
│  DeepSeek API TTFB   ████████████████████████████████████ 92.6%  │
│  AIProxy HTTP 连接   ██ 6.2%                                    │
│  Prompt 构建         █ 0.6%                                     │
│  中间件链             ▏ 0.3%                                     │
│  其他                 ▏ 0.3%                                     │
│                                                                  │
│  结论：DeepSeek API 的 TTFB 是绝对瓶颈，                          │
│  本地优化空间有限，需通过缓存命中降低 token 数量                   │
└──────────────────────────────────────────────────────────────────┘
```

### 20.4 优化建议

1. **缓存命中优化**（优先级：高）
   - 固化 system prompt 前缀，确保 ≥95% 缓存命中率
   - 使用 SHA-256 前缀哈希验证缓存一致性
   - 缓存命中可减少 90% 的 prompt token 费用，但不减少 TTFB

2. **连接池复用**（优先级：中）
   - httpx AsyncClient 全局复用，避免每次请求重建 TCP 连接
   - 启用 HTTP/2 多路复用

3. **流式输出**（优先级：高）
   - 使用 SSE 流式输出，TTFB 降低至 DeepSeek 首个 chunk 到达时间
   - 用户无需等待完整响应生成

4. **DST 压缩**（优先级：中）
   - 定期压缩对话历史，减少 prompt token 数量
   - 降低 API 调用费用与延迟

---

## 21. 数据流监控

### 21.1 监控指标定义

| 指标名 | 类型 | 描述 | 采集方式 |
|--------|------|------|---------|
| `request_total` | Counter | 请求总数 | 中间件递增 |
| `request_duration_seconds` | Histogram | 请求耗时分布 | 中间件计时 |
| `ai_call_total` | Counter | AI 调用总数 | AIProxy 递增 |
| `ai_call_duration_seconds` | Histogram | AI 调用耗时 | AIProxy 计时 |
| `cache_hit_rate` | Gauge | 缓存命中率 | CacheTracker |
| `token_usage_total` | Counter | token 使用量 | BudgetLedger |
| `active_conversations` | Gauge | 活跃对话数 | ConversationManager |
| `error_total` | Counter | 错误总数 | 异常处理器 |
| `sse_active_connections` | Gauge | SSE 活跃连接数 | 路由层 |

### 21.2 监控数据流

```
┌──────────────────────────────────────────────────────────────────┐
│                    数据流监控架构                                  │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │ 请求中间件│  │ AIProxy  │  │ Agent    │  │ 异常处理 │         │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘         │
│       │             │             │             │               │
│       │  metrics    │  metrics    │  metrics    │  metrics      │
│       │────────────▶│────────────▶│────────────▶│               │
│       │             │             │             │               │
│       ▼             ▼             ▼             ▼               │
│  ┌──────────────────────────────────────────────────┐           │
│  │              MetricsCollector                    │           │
│  │  (内存中的 Prometheus 格式指标)                  │           │
│  └──────────────────────┬───────────────────────────┘           │
│                         │                                        │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────┐           │
│  │              /metrics 端点                       │           │
│  │  (Prometheus 文本格式暴露)                       │           │
│  └──────────────────────┬───────────────────────────┘           │
│                         │                                        │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────┐           │
│  │              Prometheus Server                   │           │
│  │  (定期 scrape /metrics)                          │           │
│  └──────────────────────┬───────────────────────────┘           │
│                         │                                        │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────┐           │
│  │              Grafana Dashboard                   │           │
│  │  (可视化面板 + 告警规则)                         │           │
│  └──────────────────────────────────────────────────┘           │
└──────────────────────────────────────────────────────────────────┘
```

### 21.3 监控指标采集实现

```python
# backend/monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from time import time
from functools import wraps


# 指标定义
REQUEST_TOTAL = Counter(
    "thesisminer_request_total",
    "请求总数",
    ["method", "endpoint", "status"],
)
REQUEST_DURATION = Histogram(
    "thesisminer_request_duration_seconds",
    "请求耗时（秒）",
    ["method", "endpoint"],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60],
)
AI_CALL_TOTAL = Counter(
    "thesisminer_ai_call_total",
    "AI 调用总数",
    ["agent_id", "model", "status"],
)
AI_CALL_DURATION = Histogram(
    "thesisminer_ai_call_duration_seconds",
    "AI 调用耗时（秒）",
    ["agent_id", "model"],
    buckets=[0.5, 1, 2, 5, 10, 30, 60, 120],
)
CACHE_HIT_RATE = Gauge(
    "thesisminer_cache_hit_rate",
    "缓存命中率",
    ["agent_id"],
)
TOKEN_USAGE = Counter(
    "thesisminer_token_usage_total",
    "token 使用总量",
    ["agent_id", "model", "type"],
)
ACTIVE_CONVERSATIONS = Gauge(
    "thesisminer_active_conversations",
    "活跃对话数",
)
ERROR_TOTAL = Counter(
    "thesisminer_error_total",
    "错误总数",
    ["type", "code"],
)


async def metrics_middleware(request: Request, call_next):
    """请求指标采集中间件"""
    start_time = time()
    method = request.method
    endpoint = request.url.path

    try:
        response = await call_next(request)
        status = response.status_code
    except Exception as e:
        status = 500
        ERROR_TOTAL.labels(type="unhandled", code=type(e).__name__).inc()
        raise
    finally:
        duration = time() - start_time
        REQUEST_TOTAL.labels(method=method, endpoint=endpoint, status=str(status)).inc()
        REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)

    return response
```

---

## 22. 附录

### 22.1 数据流相关文件索引

| 文件路径 | 职责 |
|---------|------|
| `backend/main.py` | FastAPI 应用入口，lifespan 上下文管理 |
| `backend/api/routes/*.py` | API 路由定义（25 个端点） |
| `backend/api/middleware/*.py` | 中间件（CORS/日志/限流/错误处理） |
| `backend/agents/orchestrator.py` | Orchestrator 状态机编排 |
| `backend/agents/base.py` | BaseAgent 抽象基类 |
| `backend/agents/reasoner.py` | Reasoner Agent（创意生成） |
| `backend/agents/critic.py` | Critic Agent（论题评估） |
| `backend/agents/mentor.py` | Mentor Agent（信息确权） |
| `backend/agents/searcher.py` | Searcher Agent（文献检索） |
| `backend/agents/writer.py` | Writer Agent（报告生成） |
| `backend/ai/proxy.py` | AIProxy 代理层（httpx 转发） |
| `backend/ai/response_parser.py` | 响应解析器（JSON 提取/校验） |
| `backend/ai/cache_tracker.py` | 缓存命中追踪器 |
| `backend/ai/retry.py` | 重试装饰器 |
| `backend/ai/fallback.py` | 降级管理器 |
| `backend/sessions/dst.py` | DST 对话状态追踪器 |
| `backend/sessions/dst_compressor.py` | DST 压缩器 |
| `backend/sessions/conversation_manager.py` | 多对话管理器 |
| `backend/agents/citation_parser.py` | 引用解析器 |
| `backend/utils/ssrf_guard.py` | SSRF 防护 |
| `backend/monitoring/metrics.py` | 监控指标采集 |
| `frontend/js/sse_client.js` | SSE 客户端 |
| `frontend/js/lineage_graph.js` | D3.js 谱系图渲染 |

### 22.2 数据流相关数据库表

| 表名 | 用途 |
|------|------|
| `sessions` | 会话管理 |
| `conversations` | 对话管理（多对话隔离） |
| `conversation_messages` | 消息历史 |
| `proposals` | 候选论题与开题报告 |
| `lineage_nodes` | 谱系图节点 |
| `lineage_edges` | 谱系图边 |
| `budget_ledger` | 预算账本（token 使用记录） |
| `knowledge_cards` | 知识卡片 |
| `search_citations` | 搜索引用 |

### 22.3 术语表

| 术语 | 英文 | 定义 |
|------|------|------|
| 编排器 | Orchestrator | 五阶段闭环导航的核心调度器 |
| 对话状态追踪器 | DST (Dialogue State Tracker) | 管理对话上下文与状态的数据结构 |
| 三段式 Prompt | Three-segment Prompt | prefix/dynamic/tail 分割的 Prompt 架构 |
| 前缀哈希 | Prefix Hash | SHA-256 哈希的前 16 字符，用于缓存一致性校验 |
| 缓存命中 | Cache Hit | DeepSeek API 的 Prompt 前缀缓存命中 |
| 首字节延迟 | TTFB (Time To First Byte) | 从请求发送到收到首个响应字节的时间 |
| 服务端推送事件 | SSE (Server-Sent Events) | 基于 HTTP 的单向流式推送协议 |
| 服务端请求伪造 | SSRF (Server-Side Request Forgery) | 攻击者利用服务端发起内网请求的攻击手法 |
| 指数退避 | Exponential Backoff | 重试间隔按 2^n 递增的重试策略 |
| 降级 | Fallback | 主服务不可用时切换到备用方案的策略 |
| 力导向布局 | Force-directed Layout | D3.js 的图布局算法，基于物理模拟 |
| 预算账本 | Budget Ledger | 记录 token 使用量与费用的数据表 |

### 22.4 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v8.0 | 2026-06-19 | 初始版本，覆盖完整数据流架构 |

---

> **文档结束** | ThesisMiner v8.0 数据流架构文档 | 共 22 章
│         ▼                                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              内容预处理                              │   │
│  │  • 去除 Markdown 代码块标记                          │   │
│  │  • 去除首尾空白                                      │   │
│  │  • 统一换行符                                        │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         │                                    │
│                         ▼                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              格式识别与解析                          │   │
│  │  • JSON 格式 → json.loads                           │   │
│  │  • 失败 → 容错提取 (正则匹配 {...})                  │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         │                                    │
│                         ▼                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              字段校验与转换                          │   │
│  │  • 必填字段检查                                     │   │
│  │  • 类型转换 (str→int/float/list)                    │   │
│  │  • 默认值填充                                       │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         │                                    │
│                         ▼                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              结构化输出                              │   │
│  │  • Pydantic Model 实例化                             │   │
│  │  • 返回业务对象                                     │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### 9.3 JSON 响应解析详细流程

```python
# backend/ai/response_parser.py
class ResponseParser:

    def parse_json_response(self, response: dict) -> dict:
        """解析 JSON 格式的 LLM 响应

        完整数据流：
        1. 提取 content 字段
        2. 预处理（清理 Markdown）
        3. 容错 JSON 解析
        4. 字段校验
        5. 类型转换
        6. 默认值填充
        """
        content = response.get("content", "")
        if not content:
            raise ResponseParseError("Empty content")

        # 1. 预处理
        cleaned = self._preprocess(content)

        # 2. JSON 解析（容错）
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            data = self._extract_json_fallback(cleaned)

        # 3. 字段校验与转换
        data = self._transform_fields(data)

        return data

    def _preprocess(self, content: str) -> str:
        """预处理内容

        数据流转换：
        - 输入: "```json\n{\"title\": \"...\"}\n```"
        - 输出: "{\"title\": \"...\"}"
        """
        content = re.sub(r'^```(?:json)?\s*\n?', '', content)
        content = re.sub(r'\n?```\s*$', '', content)
        content = content.strip()
        return content

    def _extract_json_fallback(self, text: str) -> dict:
        """容错 JSON 提取"""
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if not match:
            raise ResponseParseError("No JSON found in response")

        json_str = match.group()
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ResponseParseError(f"JSON parse failed: {e}")

    def _transform_fields(self, data: dict) -> dict:
        """字段类型转换"""
        rc = data.get("research_content")
        if isinstance(rc, str):
            data["research_content"] = [
                line.strip() for line in rc.split("\n") if line.strip()
            ]

        cs = data.get("confidence_score")
        if isinstance(cs, str):
            data["confidence_score"] = float(cs)

        rs = data.get("research_significance")
        if isinstance(rs, str):
            try:
                data["research_significance"] = json.loads(rs)
            except json.JSONDecodeError:
                data["research_significance"] = {
                    "theoretical": rs,
                    "practical": rs,
                }

        return data
```

### 9.4 响应解析错误处理

```python
class ResponseParseError(Exception):
    """响应解析错误"""
    pass


async def safe_parse_response(response: dict, agent_id: str) -> dict:
    """安全解析响应（带错误处理）

    数据流：
    1. 尝试解析
    2. 失败时记录日志
    3. 返回降级结果或抛出异常
    """
    try:
        return response_parser.parse_json_response(response)
    except ResponseParseError as e:
        logger.error({
            "error": "response_parse_failed",
            "agent": agent_id,
            "message": str(e),
            "content_preview": response.get("content", "")[:200],
        })

        return {
            "title": "解析失败",
            "inspiration_source": "",
            "problem_awareness": "",
            "research_significance": {
                "theoretical": "",
                "practical": "",
            },
            "literature_review_outline": "",
            "differentiation": "",
            "research_content": [],
            "feasibility_analysis": "",
            "confidence_score": 0.0,
            "_parse_error": str(e),
        }
```

---

## 10. 引用解析数据流

### 10.1 引用解析概述

引用解析数据流负责从 LLM 生成的响应中提取引用链接（URL），并解析其元数据（标题、摘要、来源域名、favicon）。这些引用信息会持久化到 `search_citations` 表，并在前端渲染为可点击的引用标记。

### 10.2 引用解析数据流架构

```
┌──────────────────────────────────────────────────────────────┐
│                    引用解析数据流                              │
│                                                              │
│  ┌──────────────┐                                            │
│  │ LLM 响应     │                                            │
│  │ content =    │                                            │
│  │ "...参见     │                                            │
│  │  [1]..."     │                                            │
│  └──────┬───────┘                                            │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              URL 提取                                 │   │
│  │  • 正则匹配 https?://...                              │   │
│  │  • 去重                                              │   │
│  │  • URL 合法性校验                                    │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         │                                    │
│                         ▼                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              元数据解析                               │   │
│  │  • 解析域名 (source_domain)                          │   │
│  │  • 生成 favicon URL                                  │   │
│  │  • 提取上下文摘要 (snippet)                          │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         │                                    │
│                         ▼                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              持久化                                   │   │
│  │  • INSERT INTO search_citations                      │   │
│  │  • 关联 message_id                                   │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         │                                    │
│                         ▼                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              返回引用列表                             │   │
│  │  [{url, title, snippet, source_domain, favicon}]     │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### 10.3 CitationParser 实现

```python
# backend/ai/citation_parser.py
import re
from urllib.parse import urlparse, urlunparse
from dataclasses import dataclass


@dataclass
class Citation:
    """引用数据结构"""
    url: str
    title: str = ""
    snippet: str = ""
    source_domain: str = ""
    favicon: str = ""


class CitationParser:
    """引用解析器"""

    URL_PATTERN = re.compile(
        r'https?://[^\s<>"\)\]\}]+',
        re.IGNORECASE,
    )

    BLOCKED_DOMAINS = {
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "example.com",
        "example.org",
    }

    def extract_citations(
        self,
        content: str,
        context_window: int = 100,
    ) -> list[Citation]:
        """提取引用

        数据流：
        1. 正则匹配所有 URL
        2. 去重
        3. 校验合法性
        4. 解析元数据
        5. 返回 Citation 列表
        """
        urls = self.URL_PATTERN.findall(content)

        seen = set()
        unique_urls = []
        for url in urls:
            normalized = self._normalize_url(url)
            if normalized not in seen:
                seen.add(normalized)
                unique_urls.append(url)

        citations = []
        for url in unique_urls:
            if not self._is_valid_url(url):
                continue
            citation = self._parse_citation(url, content, context_window)
            citations.append(citation)

        return citations

    def _normalize_url(self, url: str) -> str:
        """URL 规范化"""
        url = url.rstrip(".,;:!?)")
        parsed = urlparse(url)
        if parsed.scheme == "http":
            parsed = parsed._replace(scheme="https")
        parsed = parsed._replace(fragment="")
        return urlunparse(parsed)

    def _is_valid_url(self, url: str) -> bool:
        """URL 合法性校验（含 SSRF 防护）"""
        try:
            parsed = urlparse(url)
        except Exception:
            return False

        if not parsed.scheme or not parsed.netloc:
            return False

        domain = parsed.netloc.lower()
        if domain in self.BLOCKED_DOMAINS:
            return False

        if self._is_internal_address(domain):
            return False

        return True

    def _is_internal_address(self, host: str) -> bool:
        """检查是否为内网地址（SSRF 防护）"""
        if ":" in host:
            host = host.split(":")[0]

        if re.match(r'^\d+\.\d+\.\d+\.\d+$', host):
            parts = [int(p) for p in host.split(".")]
            if parts[0] == 10:
                return True
            if parts[0] == 172 and 16 <= parts[1] <= 31:
                return True
            if parts[0] == 192 and parts[1] == 168:
                return True
            if parts[0] == 127:
                return True

        return False

    def _parse_citation(
        self,
        url: str,
        content: str,
        context_window: int,
    ) -> Citation:
        """解析单个引用的元数据"""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        favicon = f"https://www.google.com/s2/favicons?domain={domain}"
        snippet = self._extract_snippet(url, content, context_window)

        return Citation(
            url=url,
            title="",
            snippet=snippet,
            source_domain=domain,
            favicon=favicon,
        )

    def _extract_snippet(
        self,
        url: str,
        content: str,
        window: int,
    ) -> str:
        """提取 URL 周围的上下文作为摘要"""
        idx = content.find(url)
        if idx == -1:
            return ""

        start = max(0, idx - window)
        end = min(len(content), idx + len(url) + window)

        snippet = content[start:end]
        snippet = re.sub(r'\s+', ' ', snippet).strip()

        return snippet


citation_parser = CitationParser()
```

### 10.4 引用持久化数据流

```python
# backend/routes/citations.py
@router.post("/parse/{message_id}")
async def parse_and_save_citations(message_id: str):
    """解析消息中的引用并持久化

    数据流：
    1. 从 DB 加载消息内容
    2. 调用 CitationParser 提取引用
    3. 批量插入 search_citations 表
    4. 返回引用列表
    """
    message = fetch_one(
        "SELECT content FROM conversation_messages WHERE id = ?",
        (message_id,)
    )
    if not message:
        raise HTTPException(404, "Message not found")

    citations = citation_parser.extract_citations(message["content"])

    for cite in citations:
        execute_insert("search_citations", {
            "id": str(uuid.uuid4()),
            "message_id": message_id,
            "url": cite.url,
            "title": cite.title,
            "snippet": cite.snippet,
            "source_domain": cite.source_domain,
            "favicon": cite.favicon,
        })

    return {"citations": [c.__dict__ for c in citations]}
```

**引用持久化数据流图**：

```
message_id
    │
    ▼
┌──────────────────────┐     ┌──────────────────┐
│  加载消息内容         │────▶│  SQLite          │
│  SELECT content      │◀────│  conv_messages   │
└──────────┬───────────┘     └──────────────────┘
           │
           ▼
┌──────────────────────┐
│  CitationParser      │
│  .extract_citations  │
│  • URL 提取          │
│  • 元数据解析        │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  citations = [       │
│    Citation(url,..), │
│    Citation(url,..), │
│  ]                   │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐     ┌──────────────────┐
│  批量 INSERT         │────▶│  SQLite          │
│  INSERT INTO         │     │  search_citations│
│  search_citations    │◀────│                  │
└──────────┬───────────┘     └──────────────────┘
           │
           ▼
┌──────────────────────┐
│  返回引用列表        │
│  {citations: [...]}  │
└──────────────────────┘
```

---

## 11. 流式输出数据流

### 11.1 流式输出概述

流式输出是 ThesisMiner v8.0 提升**用户感知性能**的关键机制。通过 Server-Sent Events (SSE) 技术，将 LLM 生成的 token 实时推送到前端，避免用户等待完整响应生成完毕。

### 11.2 流式输出数据流架构

```
┌──────────────────────────────────────────────────────────────────┐
│                    流式输出数据流                                  │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │ Agent    │  │ AIProxy  │  │ httpx    │  │ DeepSeek │         │
│  │ .stream()│  │.stream() │  │ .stream()│  │   API    │         │
│  └────┬