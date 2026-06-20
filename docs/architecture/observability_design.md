# ThesisMiner v8.0 可观测性设计文档

> **文档版本**：v8.0.0
> **最后更新**：2026-06-20
> **文档负责**：ThesisMiner Architecture Team
> **审阅状态**：Approved
> **适用范围**：ThesisMiner v8.0 全部生产环境与预发环境

---

## 目录

- [1. 概述](#1-概述)
  - [1.1 文档目的](#11-文档目的)
  - [1.2 可观测性定义](#12-可观测性定义)
  - [1.3 设计原则](#13-设计原则)
  - [1.4 术语表](#14-术语表)
- [2. 可观测性三大支柱](#2-可观测性三大支柱)
  - [2.1 Logging 日志](#21-logging-日志)
  - [2.2 Metrics 指标](#22-metrics-指标)
  - [2.3 Tracing 追踪](#23-tracing-追踪)
  - [2.4 三者关系](#24-三者关系)
- [3. 日志体系设计](#3-日志体系设计)
  - [3.1 结构化日志格式](#31-结构化日志格式)
  - [3.2 日志级别](#32-日志级别)
  - [3.3 日志分类](#33-日志分类)
  - [3.4 日志采集](#34-日志采集)
  - [3.5 日志聚合](#35-日志聚合)
  - [3.6 日志检索](#36-日志检索)
  - [3.7 日志存储与生命周期](#37-日志存储与生命周期)
  - [3.8 日志安全与脱敏](#38-日志安全与脱敏)
- [4. 指标体系设计](#4-指标体系设计)
  - [4.1 指标分类](#41-指标分类)
  - [4.2 业务指标](#42-业务指标)
  - [4.3 系统指标](#43-系统指标)
  - [4.4 自定义指标](#44-自定义指标)
  - [4.5 指标聚合](#45-指标聚合)
  - [4.6 指标采集与存储](#46-指标采集与存储)
  - [4.7 指标查询与导出](#47-指标查询与导出)
- [5. 分布式追踪设计](#5-分布式追踪设计)
  - [5.1 追踪模型](#51-追踪模型)
  - [5.2 Span 与 SpanContext](#52-span-与-spancontext)
  - [5.3 上下文传播](#53-上下文传播)
  - [5.4 采样策略](#54-采样策略)
  - [5.5 追踪后端](#55-追踪后端)
  - [5.6 链路分析与可视化](#56-链路分析与可视化)
- [6. 告警体系设计](#6-告警体系设计)
  - [6.1 告警架构](#61-告警架构)
  - [6.2 告警规则](#62-告警规则)
  - [6.3 告警级别](#63-告警级别)
  - [6.4 告警通知](#64-告警通知)
  - [6.5 告警抑制与去重](#65-告警抑制与去重)
  - [6.6 告警路由](#66-告警路由)
  - [6.7 告警闭环管理](#67-告警闭环管理)
- [7. 仪表盘与可视化](#7-仪表盘与可视化)
  - [7.1 仪表盘设计原则](#71-仪表盘设计原则)
  - [7.2 业务仪表盘](#72-业务仪表盘)
  - [7.3 系统仪表盘](#73-系统仪表盘)
  - [7.4 SLO 仪表盘](#74-slo-仪表盘)
  - [7.5 报表与导出](#75-报表与导出)
- [8. 服务网格可观测性](#8-服务网格可观测性)
  - [8.1 Istio/Envoy 集成](#81-istioenvoy-集成)
  - [8.2 网格指标](#82-网格指标)
  - [8.3 网格追踪](#83-网格追踪)
  - [8.4 网格日志](#84-网格日志)
- [9. SRE 方法论](#9-sre-方法论)
  - [9.1 SLI/SLO/SLA](#91-slislosla)
  - [9.2 错误预算](#92-错误预算)
  - [9.3 Toil 管理](#93-toil-管理)
  - [9.4 事故管理](#94-事故管理)
- [10. 实施与最佳实践](#10-实施与最佳实践)
  - [10.1 部署架构](#101-部署架构)
  - [10.2 容量规划](#102-容量规划)
  - [10.3 性能优化](#103-性能优化)
  - [10.4 最佳实践清单](#104-最佳实践清单)
- [11. 附录](#11-附录)
  - [11.1 配置示例](#111-配置示例)
  - [11.2 常用查询](#112-常用查询)
  - [11.3 故障排查](#113-故障排查)
  - [11.4 变更记录](#114-变更记录)

---

## 1. 概述

### 1.1 文档目的

本文档定义 ThesisMiner v8.0 系统的可观测性（Observability）设计规范，覆盖日志（Logging）、指标（Metrics）、追踪（Tracing）三大支柱，以及告警、仪表盘、服务网格可观测性、SRE 方法论等延伸主题。文档面向以下读者：

- **平台工程师**：负责可观测性基础设施的部署、运维与容量规划
- **后端开发工程师**：负责在 ThesisMiner 各模块（`backend/agents`、`backend/sessions`、`backend/orchestration`、`backend/ai`、`backend/analytics`、`backend/ml`、`backend/export`、`backend/knowledge`、`backend/validation`、`backend/routing`、`backend/integrity`、`backend/optimization`、`backend/nlp`、`backend/monitoring`、`backend/planning`、`backend/reasoning` 等）中埋点
- **SRE 与运维工程师**：负责制定 SLO、告警策略、值班响应
- **架构师**：评审可观测性方案的合理性、扩展性、成本
- **QA 与测试工程师**：验证可观测性数据准确性、完整性

文档目标是让任何一名工程师在阅读后能够：

1. 理解 ThesisMiner v8.0 可观测性整体架构
2. 知道在哪里、如何埋点日志、指标、追踪
3. 能够编写符合规范的告警规则
4. 能够使用仪表盘定位线上问题
5. 能够基于 SRE 方法论制定 SLO 与错误预算

### 1.2 可观测性定义

可观测性（Observability）源自控制论，指通过外部输出推断系统内部状态的能力。在云原生语境下，可观测性指：**当系统出现异常时，工程师能够基于已有的日志、指标、追踪数据，无需修改代码即可定位根因**。

可观测性 ≠ 监控。监控（Monitoring）告诉系统"出了什么问题"，可观测性告诉工程师"为什么出问题"。两者关系如下：

```
+-------------------+        +-------------------+
|     监控 Monitoring|        | 可观测性 Observability |
|  - 告警触发        |  -->   |  - 根因定位          |
|  - 阈值检查        |        |  - 上下文还原        |
|  - 已知问题发现    |        |  - 未知问题探索      |
+-------------------+        +-------------------+
        |                              |
        v                              v
   "数据库 CPU 90%"            "为什么 CPU 高？是慢查询 X"
```

ThesisMiner v8.0 采用 Multi-Agent 架构（Orchestrator + 5 sub-agents：Searcher、Reasoner、Critic、Mentor、Writer），五阶段闭环导航（Five-Stage Closed-Loop），三段式 Prompt 缓存（Three-Segment Prompt Caching），多会话上下文隔离（Multi-Conversation Context Isolation）。这种复杂度要求可观测性必须做到：

- **跨 Agent 链路追踪**：一次用户请求经过 Orchestrator 分发到多个 sub-agent，必须能完整还原调用链
- **阶段级指标**：五阶段（Topic Clarification、Literature Mapping、Method Design、Writing、Refinement）每阶段都要有独立指标
- **缓存命中率监控**：三段式 Prompt 缓存（System Prompt、Session Context、User Query）的命中率直接影响成本与延迟
- **会话隔离可观测**：多会话场景下，每个会话的指标必须可按 `session_id` 维度切片

### 1.3 设计原则

ThesisMiner v8.0 可观测性设计遵循以下七项原则：

| 编号 | 原则 | 说明 |
|------|------|------|
| P1 | **低侵入** | 埋点代码与业务代码解耦，使用装饰器、中间件、SDK 抽象 |
| P2 | **结构化优先** | 日志必须 JSON 结构化，指标必须带 label，追踪必须带 attribute |
| P3 | **可关联** | 日志、指标、追踪通过 `trace_id`、`span_id`、`session_id` 关联 |
| P4 | **成本可控** | 采样、保留策略、降采样（downsampling）必须可配置 |
| P5 | **故障优先** | 可观测性系统自身故障不能阻塞业务，必须降级而非中断 |
| P6 | **安全合规** | 敏感数据（用户论文内容、API Key）必须脱敏，访问审计可追溯 |
| P7 | **SRE 驱动** | 指标与告警围绕 SLI/SLO 设计，避免"告警风暴" |

### 1.4 术语表

| 术语 | 英文 | 说明 |
|------|------|------|
| 日志 | Log | 离散事件记录，带时间戳 |
| 指标 | Metric | 可聚合的数值时序数据 |
| 追踪 | Trace | 一次请求的完整调用链 |
| Span | Span | 追踪中的一个操作单元 |
| SpanContext | Span Context | Span 的上下文，含 trace_id、span_id |
| 采样 | Sampling | 按比例采集追踪数据 |
| 服务级别指标 | SLI | Service Level Indicator |
| 服务级别目标 | SLO | Service Level Objective |
| 服务级别协议 | SLA | Service Level Agreement |
| 错误预算 | Error Budget | 100% - SLO |
| 仪表盘 | Dashboard | 可视化面板 |
| 告警 | Alert | 异常触发的通知 |
| 抑制 | Inhibition | 告警去重与抑制 |
| Toil | Toil | 重复、可自动化、低价值的工作 |
| 事故 | Incident | 影响业务的事件 |
| Postmortem | Postmortem | 事故复盘 |

---

## 2. 可观测性三大支柱

### 2.1 Logging 日志

日志记录离散事件，回答"发生了什么"。ThesisMiner v8.0 的日志覆盖：

- **请求日志**：HTTP 请求/响应、FastAPI 中间件日志
- **Agent 日志**：Orchestrator 分发决策、sub-agent 执行结果
- **阶段日志**：五阶段闭环每阶段的进入/退出、耗时
- **缓存日志**：三段式 Prompt 缓存命中/未命中、写入
- **会话日志**：会话创建、切换、销毁、上下文隔离事件
- **数据库日志**：SQLite WAL 模式下的读写、checkpoint
- **AI 调用日志**：DeepSeek API 调用、token 用量、错误重试
- **导出日志**：论文导出（PDF/DOCX/Markdown）事件
- **系统日志**：启动、关闭、配置加载、健康检查

### 2.2 Metrics 指标

指标记录可聚合的数值时序数据，回答"趋势如何"。ThesisMiner v8.0 的指标覆盖：

- **业务指标**：论文生成数、阶段完成率、用户活跃数、导出成功率
- **系统指标**：CPU、内存、磁盘、网络、文件描述符
- **应用指标**：QPS、延迟分位数（P50/P90/P99）、错误率
- **AI 指标**：DeepSeek 调用 QPS、token 消耗、缓存命中率
- **数据库指标**：SQLite 连接数、WAL 大小、慢查询数
- **Agent 指标**：每个 sub-agent 的调用次数、耗时、失败率

### 2.3 Tracing 追踪

追踪记录一次请求的完整调用链，回答"在哪里、为什么慢"。ThesisMiner v8.0 的追踪覆盖：

- **入口 Span**：HTTP 请求入口
- **Orchestrator Span**：编排决策
- **Sub-Agent Span**：每个 sub-agent 的执行
- **阶段 Span**：五阶段每阶段
- **AI 调用 Span**：DeepSeek API 调用
- **数据库 Span**：SQLite 查询
- **缓存 Span**：Prompt 缓存读写
- **导出 Span**：论文导出

### 2.4 三者关系

日志、指标、追踪通过 `trace_id` 关联，形成"三维"可观测性：

```
                    指标 (Metrics)
                    - QPS: 120
                    - P99: 850ms
                    - Error Rate: 0.5%
                         |
                         | (trace_id 关联)
                         v
    日志 (Logs)  <------>  追踪 (Trace)
    - ERROR trace_id=abc  - Trace abc
    - span_id=def         - Span def (Orchestrator)
    - "DeepSeek timeout"  - Span ghi (DeepSeek call) 850ms
```

**关联示例**：

1. 仪表盘显示 P99 延迟突增（指标）
2. 点击异常点跳转到对应时间段的追踪列表（追踪）
3. 找到慢 Trace，展开看到 DeepSeek 调用 Span 耗时 850ms
4. 点击 Span 关联的日志，看到 "DeepSeek timeout, retry 3 times"（日志）
5. 根因定位：DeepSeek API 限流

---

## 3. 日志体系设计

### 3.1 结构化日志格式

ThesisMiner v8.0 强制使用 JSON 结构化日志，便于 ELK/Loki 等系统解析与检索。基础格式如下：

```json
{
  "timestamp": "2026-06-20T10:30:45.123Z",
  "level": "INFO",
  "logger": "thesisminer.orchestrator",
  "trace_id": "abc123def456",
  "span_id": "span789",
  "parent_span_id": "span456",
  "session_id": "sess-2026-06-20-001",
  "conversation_id": "conv-001",
  "user_id": "user-001",
  "agent": "orchestrator",
  "stage": "literature_mapping",
  "event": "agent_dispatch",
  "message": "Dispatched to Reasoner agent",
  "target_agent": "reasoner",
  "duration_ms": 12,
  "extra": {
    "cache_hit": true,
    "cache_segment": "session_context",
    "prompt_tokens": 1200
  }
}
```

**字段规范**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| timestamp | string (ISO 8601) | 是 | UTC 时间，毫秒精度 |
| level | enum | 是 | DEBUG/INFO/WARN/ERROR/FATAL |
| logger | string | 是 | 模块名，点分层级 |
| trace_id | string | 是 | 追踪 ID，32 位 hex |
| span_id | string | 是 | 当前 Span ID，16 位 hex |
| parent_span_id | string | 否 | 父 Span ID |
| session_id | string | 是 | 会话 ID |
| conversation_id | string | 否 | 会话内对话 ID |
| user_id | string | 否 | 用户 ID（脱敏） |
| agent | string | 否 | Agent 名（orchestrator/searcher/...） |
| stage | string | 否 | 五阶段之一 |
| event | string | 是 | 事件类型，snake_case |
| message | string | 是 | 人类可读描述 |
| duration_ms | int | 否 | 耗时（毫秒） |
| extra | object | 否 | 扩展字段 |

**Python 实现示例**（`backend/monitoring/logger.py`）：

```python
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional


class ThesisMinerJsonFormatter(logging.Formatter):
    """ThesisMiner 结构化 JSON 日志格式化器。"""

    # 必填字段
    REQUIRED_FIELDS = ("timestamp", "level", "logger", "trace_id",
                       "span_id", "event", "message")

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "trace_id": getattr(record, "trace_id", "-"),
            "span_id": getattr(record, "span_id", "-"),
            "session_id": getattr(record, "session_id", "-"),
            "event": getattr(record, "event", record.getMessage().split()[0]
                             if record.getMessage() else "log"),
            "message": record.getMessage(),
        }

        # 可选字段
        for field in ("parent_span_id", "conversation_id", "user_id",
                      "agent", "stage", "duration_ms"):
            value = getattr(record, field, None)
            if value is not None:
                log_entry[field] = value

        # 异常信息
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # 扩展字段
        extra = getattr(record, "extra", None)
        if extra and isinstance(extra, dict):
            log_entry["extra"] = extra

        return json.dumps(log_entry, ensure_ascii=False, default=str)


def setup_logger(name: str, level: str = "INFO") -> logging.Logger:
    """初始化 ThesisMiner 标准日志器。"""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(ThesisMinerJsonFormatter())
        logger.addHandler(handler)

    return logger
```

### 3.2 日志级别

ThesisMiner v8.0 采用五级日志体系：

| 级别 | 数值 | 使用场景 | 生产环境 | 预发环境 | 开发环境 |
|------|------|----------|----------|----------|----------|
| DEBUG | 10 | 详细调试信息，如变量值、SQL 语句 | 关闭 | 开启 | 开启 |
| INFO | 20 | 正常业务流程，如请求处理、Agent 分发 | 开启 | 开启 | 开启 |
| WARN | 30 | 异常但可恢复，如重试、降级、缓存未命中 | 开启 | 开启 | 开启 |
| ERROR | 40 | 错误，影响单次请求，如 API 调用失败 | 开启 | 开启 | 开启 |
| FATAL | 50 | 致命错误，进程需退出，如配置加载失败 | 开启 | 开启 | 开启 |

**级别选择指南**：

- **DEBUG**：仅用于本地调试或线上临时排查，禁止长期开启。例如打印 DeepSeek 返回的完整 JSON。
- **INFO**：业务关键节点。例如"用户提交论文生成请求"、"Reasoner agent 完成"、"论文导出成功"。
- **WARN**：非预期但可恢复。例如"DeepSeek API 超时，第 2 次重试"、"Prompt 缓存未命中，回退到全量计算"。
- **ERROR**：单次请求失败。例如"DeepSeek API 返回 429"、"SQLite 写入失败"、"导出 PDF 失败"。
- **FATAL**：进程无法继续。例如"配置文件解析失败"、"SQLite 数据库锁定无法恢复"、"端口被占用且无法释放"。

**反模式**：

```python
# 错误：把 INFO 当 DEBUG 用，生产环境日志爆炸
logger.info(f"User input: {user_input}")  # 用户输入可能含敏感信息

# 错误：把 ERROR 当 WARN 用，触发不必要的告警
logger.error("Cache miss, falling back to full computation")  # 应为 WARN

# 错误：把异常吞掉只记 DEBUG
try:
    risky_operation()
except Exception as e:
    logger.debug(f"Failed: {e}")  # 应至少 WARN，关键路径应 ERROR
```

### 3.3 日志分类

ThesisMiner v8.0 日志按用途分为七大类：

#### 3.3.1 访问日志（Access Log）

记录所有 HTTP 请求，由 FastAPI 中间件生成：

```python
# backend/monitoring/middleware.py
import time
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class AccessLogMiddleware(BaseHTTPMiddleware):
    """HTTP 访问日志中间件。"""

    async def dispatch(self, request: Request, call_next):
        trace_id = request.headers.get("X-Trace-Id", uuid.uuid4().hex)
        start_time = time.time()

        response: Response = await call_next(request)

        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "HTTP request completed",
            extra={
                "event": "http_access",
                "trace_id": trace_id,
                "span_id": uuid.uuid4().hex[:16],
                "extra": {
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "client_ip": request.client.host if request.client else "-",
                    "user_agent": request.headers.get("User-Agent", "-"),
                    "content_length": response.headers.get("Content-Length", "0"),
                }
            }
        )

        response.headers["X-Trace-Id"] = trace_id
        return response
```

#### 3.3.2 业务日志（Business Log）

记录业务关键事件，由各模块主动埋点：

```python
# backend/agents/orchestrator.py
logger = setup_logger("thesisminer.orchestrator")


class Orchestrator:
    async def dispatch(self, query: str, session_id: str, stage: str):
        logger.info(
            "Orchestrator dispatching to sub-agent",
            extra={
                "event": "agent_dispatch",
                "session_id": session_id,
                "agent": "orchestrator",
                "stage": stage,
                "extra": {
                    "query_length": len(query),
                    "target_agent": self._select_agent(query, stage),
                }
            }
        )
```

#### 3.3.3 审计日志（Audit Log）

记录安全相关事件，单独存储、不可篡改：

```json
{
  "timestamp": "2026-06-20T10:30:45.123Z",
  "level": "INFO",
  "logger": "thesisminer.audit",
  "event": "user_login",
  "user_id": "user-001",
  "extra": {
    "auth_method": "oauth",
    "client_ip": "192.168.1.100",
    "user_agent": "Mozilla/5.0...",
    "success": true,
    "session_id": "sess-001"
  }
}
```

审计事件类型：`user_login`、`user_logout`、`permission_denied`、`config_change`、`data_export`、`admin_operation`、`api_key_rotation`。

#### 3.3.4 错误日志（Error Log）

记录 ERROR 及以上级别，单独索引以便告警：

```python
try:
    result = await deepseek_client.complete(prompt)
except DeepSeekRateLimitError as e:
    logger.error(
        "DeepSeek API rate limited",
        extra={
            "event": "ai_rate_limited",
            "agent": "reasoner",
            "extra": {
                "retry_after": e.retry_after,
                "attempt": e.attempt,
                "prompt_tokens": len(prompt) // 4,
            }
        },
        exc_info=True
    )
    raise
```

#### 3.3.5 性能日志（Performance Log）

记录耗时操作，用于性能分析：

```python
import time
from contextlib import contextmanager


@contextmanager
def log_duration(logger, event: str, **extra):
    """记录代码块耗时的上下文管理器。"""
    start = time.time()
    try:
        yield
    finally:
        duration_ms = int((time.time() - start) * 1000)
        logger.info(
            f"{event} completed",
            extra={
                "event": event,
                "duration_ms": duration_ms,
                "extra": extra
            }
        )


# 使用示例
with log_duration(logger, "deepseek_call", agent="reasoner", stage="method_design"):
    result = await deepseek_client.complete(prompt)
```

#### 3.3.6 缓存日志（Cache Log）

记录三段式 Prompt 缓存事件：

```python
# backend/ai/prompt_cache.py
class ThreeSegmentPromptCache:
    SEGMENTS = ("system_prompt", "session_context", "user_query")

    async def get(self, segment: str, key: str) -> Optional[str]:
        value = await self._backend.get(segment, key)
        logger.info(
            "Prompt cache access",
            extra={
                "event": "cache_access",
                "agent": "cache",
                "extra": {
                    "segment": segment,
                    "key_hash": hash(key),
                    "hit": value is not None,
                }
            }
        )
        return value
```

#### 3.3.7 数据库日志（Database Log）

记录 SQLite 操作：

```python
# backend/sessions/database.py
logger = setup_logger("thesisminer.database")


class SessionDatabase:
    async def execute(self, sql: str, params: tuple):
        start = time.time()
        try:
            result = await self._conn.execute(sql, params)
            logger.info(
                "SQL executed",
                extra={
                    "event": "sql_execute",
                    "duration_ms": int((time.time() - start) * 1000),
                    "extra": {
                        "sql_hash": hash(sql),
                        "param_count": len(params),
                        "rows_affected": result.rowcount,
                    }
                }
            )
            return result
        except Exception as e:
            logger.error(
                "SQL failed",
                extra={
                    "event": "sql_error",
                    "extra": {
                        "sql_hash": hash(sql),
                        "error_type": type(e).__name__,
                    }
                },
                exc_info=True
            )
            raise
```

### 3.4 日志采集

ThesisMiner v8.0 采用 Filebeat + Kafka 的采集架构：

```
+----------+     +----------+     +---------+     +-------+     +-------+
| App Pod  | --> | stdout   | --> |Filebeat | --> | Kafka | --> |Logstash|
| (JSON)   |     | (container|    | (DaemonSet)|   |       |     |       |
+----------+     |  logs)   |     +---------+     +-------+     +-------+
                 +----------+                                     |
                                                                  v
                                                              +-------+
                                                              | Elasticsearch |
                                                              | / Loki        |
                                                              +-------+
                                                                  |
                                                                  v
                                                              +-------+
                                                              | Kibana |
                                                              | / Grafana|
                                                              +-------+
```

**Filebeat 配置示例**（`deploy/filebeat/filebeat.yml`）：

```yaml
filebeat.inputs:
- type: container
  paths:
    - /var/lib/docker/containers/*/*.log
  processors:
    - decode_json_fields:
        fields: ["message"]
        target: "thesisminer"
    - add_kubernetes_metadata:
        host: ${NODE_NAME}
        matchers:
        - logs_path:
            logs_path: "/var/lib/docker/containers/"

processors:
  - drop_fields:
      fields: ["agent", "ecs", "host", "input", "log", "stream"]
  - add_fields:
      target: ""
      fields:
        service: "thesisminer"
        version: "8.0.0"
        environment: "${ENVIRONMENT}"

output.kafka:
  hosts: ["kafka-0:9092", "kafka-1:9092", "kafka-2:9092"]
  topic: "thesisminer-logs"
  partition.round_robin:
    reachable_only: true
  required_acks: 1
  compression: snappy
  max_message_bytes: 1000000
```

### 3.5 日志聚合

日志经 Kafka 进入 Logstash/Vector 进行聚合处理：

```ruby
# deploy/logstash/logstash.conf
input {
  kafka {
    bootstrap_servers => "kafka-0:9092,kafka-1:9092,kafka-2:9092"
    topics => ["thesisminer-logs"]
    group_id => "logstash-thesisminer"
    codec => json
  }
}

filter {
  # 解析时间戳
  date {
    match => ["timestamp", "ISO8601"]
    target => "@timestamp"
  }

  # 按 level 分级
  mutate {
    add_field => {
      "log_level" => "%{level}"
    }
  }

  # 敏感字段脱敏
  mutate {
    gsub => [
      "message", "(?i)(password|api_key|token)\s*[=:]\s*\S+", "\1=***REDACTED***",
      "extra.user_input", "(?i)(身份证号|手机号|邮箱)", "***REDACTED***"
    ]
  }

  # 按服务分流
  if [service] == "thesisminer" {
    mutate {
      add_field => { "index_type" => "thesisminer" }
    }
  }
}

output {
  if [log_level] in ["ERROR", "FATAL"] {
    elasticsearch {
      hosts => ["es-0:9200", "es-1:9200"]
      index => "thesisminer-errors-%{+YYYY.MM.dd}"
    }
  } else {
    elasticsearch {
      hosts => ["es-0:9200", "es-1:9200"]
      index => "thesisminer-logs-%{+YYYY.MM.dd}"
    }
  }
}
```

### 3.6 日志检索

ThesisMiner v8.0 使用 Kibana / Grafana Loki 作为日志检索前端。

**常用查询场景**：

**场景 1：按 trace_id 查询完整调用链日志**

```kql
trace_id: "abc123def456"
```

**场景 2：查询某会话所有 ERROR 日志**

```kql
session_id: "sess-2026-06-20-001" AND level: "ERROR"
```

**场景 3：查询 DeepSeek API 超时**

```kql
event: "ai_timeout" AND agent: "reasoner"
```

**场景 4：查询五阶段中"方法设计"阶段的所有日志**

```kql
stage: "method_design" AND level in ("WARN", "ERROR")
```

**场景 5：查询缓存命中率低于阈值的时段**

```kql
event: "cache_access" AND extra.hit: false AND extra.segment: "session_context"
```

**场景 6：查询慢 SQL（>100ms）**

```kql
event: "sql_execute" AND duration_ms: [100 TO *]
```

### 3.7 日志存储与生命周期

日志按级别与环境制定不同的保留策略：

| 日志类型 | 环境 | 存储后端 | 保留期 | 滚动策略 |
|----------|------|----------|--------|----------|
| 访问日志 | 生产 | Elasticsearch hot + warm | 30 天 | hot 7 天 → warm 23 天 → 删除 |
| 业务日志 | 生产 | Elasticsearch hot + warm | 90 天 | hot 14 天 → warm 76 天 → 删除 |
| 错误日志 | 生产 | Elasticsearch hot + cold | 365 天 | hot 30 天 → cold 335 天 → 删除 |
| 审计日志 | 生产 | Elasticsearch + S3 归档 | 2555 天（7 年） | ES 90 天 → S3 2465 天 |
| 调试日志 | 预发/开发 | Loki | 7 天 | 直接删除 |

**Elasticsearch ILM 策略**：

```json
PUT _ilm/policy/thesisminer-logs-policy
{
  "policy": {
    "phases": {
      "hot": {
        "min_age": "0ms",
        "actions": {
          "rollover": {
            "max_size": "50gb",
            "max_age": "1d"
          },
          "set_priority": {
            "priority": 100
          }
        }
      },
      "warm": {
        "min_age": "7d",
        "actions": {
          "shrink": {
            "number_of_shards": 1
          },
          "forcemerge": {
            "max_num_segments": 1
          },
          "set_priority": {
            "priority": 50
          }
        }
      },
      "cold": {
        "min_age": "30d",
        "actions": {
          "freeze": {},
          "set_priority": {
            "priority": 0
          }
        }
      },
      "delete": {
        "min_age": "90d",
        "actions": {
          "delete": {}
        }
      }
    }
  }
}
```

### 3.8 日志安全与脱敏

#### 3.8.1 脱敏规则

ThesisMiner v8.0 处理用户论文内容，属于敏感数据。脱敏规则如下：

| 数据类型 | 脱敏方式 | 示例 |
|----------|----------|------|
| 用户论文正文 | 不记录正文，仅记录 hash 与长度 | `content_hash: "a1b2c3", length: 12000` |
| API Key | 全替换 | `api_key: "***REDACTED***"` |
| 用户邮箱 | 保留域名 | `u***@example.com` |
| 手机号 | 保留前 3 后 4 | `138****5678` |
| 身份证号 | 保留前 6 后 4 | `110101********5678` |
| 银行卡号 | 保留后 4 | `************1234` |
| IP 地址 | 保留前 3 段 | `192.168.1.*` |

#### 3.8.2 脱敏实现

```python
# backend/monitoring/redactor.py
import re
import hashlib
from typing import Any


class LogRedactor:
    """日志脱敏器。"""

    PATTERNS = {
        "email": (re.compile(r"[\w.-]+@[\w.-]+\.\w+"), _mask_email),
        "phone": (re.compile(r"1[3-9]\d{9}"), _mask_phone),
        "id_card": (re.compile(r"\d{17}[\dXx]"), _mask_id_card),
        "api_key": (re.compile(r"(?i)api[_-]?key\s*[=:]\s*\S+"),
                    lambda m: "api_key=***REDACTED***"),
        "bank_card": (re.compile(r"\d{16,19}"), _mask_bank_card),
    }

    @classmethod
    def redact(cls, value: Any) -> Any:
        if isinstance(value, str):
            for name, (pattern, masker) in cls.PATTERNS.items():
                value = pattern.sub(masker, value)
        elif isinstance(value, dict):
            return {k: cls.redact(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [cls.redact(v) for v in value]
        return value


def _mask_email(match: re.Match) -> str:
    email = match.group()
    local, domain = email.split("@")
    return f"{local[0]}***@{domain}"


def _mask_phone(match: re.Match) -> str:
    phone = match.group()
    return f"{phone[:3]}****{phone[-4:]}"


def _mask_id_card(match: re.Match) -> str:
    id_card = match.group()
    return f"{id_card[:6]}********{id_card[-4:]}"


def _mask_bank_card(match: re.Match) -> str:
    card = match.group()
    return f"{'*' * (len(card) - 4)}{card[-4:]}"
```

#### 3.8.3 访问控制

- Kibana / Grafana 通过 OIDC 集成统一身份认证
- 日志查询权限按角色分级：
  - **viewer**：只能查看业务日志，不能查看审计日志
  - **developer**：可查看所有日志，不能导出
  - **sre**：可查看、导出所有日志
  - **admin**：可配置日志策略、脱敏规则
- 所有日志查询操作记录审计日志

---

## 4. 指标体系设计

### 4.1 指标分类

ThesisMiner v8.0 指标按类型分为四类：

| 类型 | 说明 | 示例 |
|------|------|------|
| Counter | 单调递增计数器 | 请求总数、错误总数 |
| Gauge | 可增可减的瞬时值 | 当前连接数、队列长度 |
| Histogram | 分布统计 | 请求延迟分布 |
| Summary | 分位数统计 | P50/P90/P99 延迟 |

按维度分为三类：

| 维度 | 说明 | 示例 |
|------|------|------|
| 业务指标 | 反映业务状态 | 论文生成数、阶段完成率 |
| 系统指标 | 反映资源状态 | CPU、内存、磁盘 |
| 自定义指标 | 应用特有 | 缓存命中率、Agent 调用数 |

### 4.2 业务指标

#### 4.2.1 论文生成指标

| 指标名 | 类型 | Labels | 说明 |
|--------|------|--------|------|
| `thesisminer_thesis_generated_total` | Counter | stage, status | 论文生成总数 |
| `thesisminer_thesis_generation_duration_seconds` | Histogram | stage | 生成耗时 |
| `thesisminer_thesis_exported_total` | Counter | format, status | 导出总数 |
| `thesisminer_thesis_in_progress` | Gauge | stage | 进行中数量 |
| `thesisminer_thesis_failed_total` | Counter | stage, error_type | 失败总数 |

**埋点示例**：

```python
# backend/monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge, Summary

thesis_generated_total = Counter(
    "thesisminer_thesis_generated_total",
    "Total number of theses generated",
    ["stage", "status"]
)

thesis_generation_duration = Histogram(
    "thesisminer_thesis_generation_duration_seconds",
    "Time spent generating thesis",
    ["stage"],
    buckets=(0.1, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300, 600)
)

thesis_in_progress = Gauge(
    "thesisminer_thesis_in_progress",
    "Number of theses currently being generated",
    ["stage"]
)
```

#### 4.2.2 五阶段闭环指标

ThesisMiner v8.0 五阶段：Topic Clarification、Literature Mapping、Method Design、Writing、Refinement。

| 指标名 | 类型 | Labels | 说明 |
|--------|------|--------|------|
| `thesisminer_stage_started_total` | Counter | stage | 阶段启动数 |
| `thesisminer_stage_completed_total` | Counter | stage, status | 阶段完成数 |
| `thesisminer_stage_duration_seconds` | Histogram | stage | 阶段耗时 |
| `thesisminer_stage_iteration_count` | Histogram | stage | 阶段迭代次数 |
| `thesisminer_stage_loop_back_total` | Counter | from_stage, to_stage | 阶段回环数 |

**五阶段回环示意**：

```
+-------------------+    +-------------------+    +-------------------+
| Topic             |    | Literature        |    | Method            |
| Clarification     |--->| Mapping           |--->| Design            |
+-------------------+    +-------------------+    +-------------------+
        ^                                                |
        |              loop_back_total                  |
        +------------------------------------------------+
                                                          |
                                                          v
                                            +-------------------+
                                            | Writing           |
                                            +-------------------+
                                                      |
                                                      v
                                            +-------------------+
                                            | Refinement        |
                                            +-------------------+
```

#### 4.2.3 多会话指标

| 指标名 | 类型 | Labels | 说明 |
|--------|------|--------|------|
| `thesisminer_session_active` | Gauge | - | 活跃会话数 |
| `thesisminer_session_created_total` | Counter | - | 会话创建总数 |
| `thesisminer_session_duration_seconds` | Histogram | - | 会话时长 |
| `thesisminer_conversation_total` | Counter | session_id | 会话内对话数 |
| `thesisminer_context_isolation_violation_total` | Counter | - | 上下文隔离违规数 |

#### 4.2.4 用户指标

| 指标名 | 类型 | Labels | 说明 |
|--------|------|--------|------|
| `thesisminer_user_active` | Gauge | - | 活跃用户数 |
| `thesisminer_user_registered_total` | Counter | - | 注册总数 |
| `thesisminer_user_satisfaction_score` | Summary | - | 用户满意度评分 |

### 4.3 系统指标

#### 4.3.1 容器与进程指标

通过 Node Exporter 与 cAdvisor 采集：

| 指标名 | 说明 |
|--------|------|
| `container_cpu_usage_seconds_total` | 容器 CPU 使用 |
| `container_memory_usage_bytes` | 容器内存使用 |
| `container_fs_usage_bytes` | 容器文件系统使用 |
| `container_network_receive_bytes_total` | 容器网络接收 |
| `process_resident_memory_bytes` | 进程驻留内存 |
| `process_open_fds` | 进程打开文件描述符 |

#### 4.3.2 数据库指标（SQLite + WAL）

| 指标名 | 类型 | Labels | 说明 |
|--------|------|--------|------|
| `thesisminer_db_connections` | Gauge | state | 连接数 |
| `thesisminer_db_query_duration_seconds` | Histogram | operation | 查询耗时 |
| `thesisminer_db_query_total` | Counter | operation, status | 查询总数 |
| `thesisminer_db_wal_size_bytes` | Gauge | - | WAL 文件大小 |
| `thesisminer_db_wal_checkpoint_total` | Counter | - | Checkpoint 次数 |
| `thesisminer_db_wal_checkpoint_duration_seconds` | Histogram | - | Checkpoint 耗时 |
| `thesisminer_db_lock_contention_total` | Counter | - | 锁竞争次数 |

#### 4.3.3 网络与 HTTP 指标

| 指标名 | 类型 | Labels | 说明 |
|--------|------|--------|------|
| `http_requests_total` | Counter | method, path, status | HTTP 请求总数 |
| `http_request_duration_seconds` | Histogram | method, path | HTTP 请求耗时 |
| `http_requests_in_progress` | Gauge | method | 进行中请求数 |
| `http_response_size_bytes` | Histogram | method, path | 响应大小 |

### 4.4 自定义指标

#### 4.4.1 DeepSeek AI 调用指标

| 指标名 | 类型 | Labels | 说明 |
|--------|------|--------|------|
| `thesisminer_ai_calls_total` | Counter | agent, model, status | AI 调用总数 |
| `thesisminer_ai_call_duration_seconds` | Histogram | agent, model | AI 调用耗时 |
| `thesisminer_ai_tokens_total` | Counter | agent, type (prompt/completion) | Token 用量 |
| `thesisminer_ai_cost_usd` | Counter | agent, model | 调用成本（美元） |
| `thesisminer_ai_rate_limit_total` | Counter | agent | 限流次数 |
| `thesisminer_ai_retry_total` | Counter | agent, attempt | 重试次数 |

#### 4.4.2 三段式 Prompt 缓存指标

| 指标名 | 类型 | Labels | 说明 |
|--------|------|--------|------|
| `thesisminer_cache_hits_total` | Counter | segment | 缓存命中数 |
| `thesisminer_cache_misses_total` | Counter | segment | 缓存未命中数 |
| `thesisminer_cache_hit_rate` | Gauge | segment | 缓存命中率 |
| `thesisminer_cache_size_bytes` | Gauge | segment | 缓存大小 |
| `thesisminer_cache_evictions_total` | Counter | segment, reason | 缓存淘汰数 |
| `thesisminer_cache_lookup_duration_seconds` | Histogram | segment | 缓存查询耗时 |

**缓存命中率计算**：

```python
# backend/ai/cache_metrics.py
from prometheus_client import Counter, Gauge

cache_hits = Counter(
    "thesisminer_cache_hits_total",
    "Cache hits",
    ["segment"]
)

cache_misses = Counter(
    "thesisminer_cache_misses_total",
    "Cache misses",
    ["segment"]
)

cache_hit_rate = Gauge(
    "thesisminer_cache_hit_rate",
    "Cache hit rate",
    ["segment"]
)


def update_hit_rate(segment: str):
    """更新缓存命中率指标。"""
    hits = cache_hits.labels(segment=segment)._value.get()
    misses = cache_misses.labels(segment=segment)._value.get()
    total = hits + misses
    rate = hits / total if total > 0 else 0
    cache_hit_rate.labels(segment=segment).set(rate)
```

#### 4.4.3 Multi-Agent 指标

| 指标名 | 类型 | Labels | 说明 |
|--------|------|--------|------|
| `thesisminer_agent_invocations_total` | Counter | agent, status | Agent 调用数 |
| `thesisminer_agent_duration_seconds` | Histogram | agent | Agent 执行耗时 |
| `thesisminer_agent_errors_total` | Counter | agent, error_type | Agent 错误数 |
| `thesisminer_orchestrator_dispatch_total` | Counter | target_agent | 编排分发数 |
| `thesisminer_orchestrator_dispatch_duration_seconds` | Histogram | - | 分发决策耗时 |

### 4.5 指标聚合

#### 4.5.1 PromQL 聚合示例

**QPS 计算**：

```promql
sum(rate(http_requests_total{service="thesisminer"}[5m])) by (path)
```

**P99 延迟**：

```promql
histogram_quantile(0.99,
  sum(rate(http_request_duration_seconds_bucket{service="thesisminer"}[5m])) by (le, path)
)
```

**错误率**：

```promql
sum(rate(http_requests_total{service="thesisminer", status=~"5.."}[5m]))
/
sum(rate(http_requests_total{service="thesisminer"}[5m]))
```

**缓存命中率**：

```promql
sum(rate(thesisminer_cache_hits_total[5m])) by (segment)
/
(
  sum(rate(thesisminer_cache_hits_total[5m])) by (segment)
  +
  sum(rate(thesisminer_cache_misses_total[5m])) by (segment)
)
```

**五阶段完成率**：

```promql
sum(rate(thesisminer_stage_completed_total{status="success"}[1h])) by (stage)
/
sum(rate(thesisminer_stage_started_total[1h])) by (stage)
```

**DeepSeek Token 成本（每小时美元）**：

```promql
sum(rate(thesisminer_ai_cost_usd[1h])) by (agent)
```

#### 4.5.2 Recording Rules

为高频查询预计算，降低 Prometheus 压力：

```yaml
# deploy/prometheus/rules/thesisminer-recording.yml
groups:
- name: thesisminer-recording
  interval: 30s
  rules:
  - record: thesisminer:http_requests:rate5m
    expr: sum(rate(http_requests_total{service="thesisminer"}[5m])) by (path)

  - record: thesisminer:http_errors:rate5m
    expr: sum(rate(http_requests_total{service="thesisminer", status=~"5.."}[5m])) by (path)

  - record: thesisminer:http_error_rate:ratio5m
    expr: thesisminer:http_errors:rate5m / thesisminer:http_requests:rate5m

  - record: thesisminer:p99_latency:5m
    expr: |
      histogram_quantile(0.99,
        sum(rate(http_request_duration_seconds_bucket{service="thesisminer"}[5m])) by (le, path)
      )

  - record: thesisminer:cache_hit_rate:5m
    expr: |
      sum(rate(thesisminer_cache_hits_total[5m])) by (segment)
      /
      (sum(rate(thesisminer_cache_hits_total[5m])) by (segment)
       + sum(rate(thesisminer_cache_misses_total[5m])) by (segment))

  - record: thesisminer:stage_completion_rate:1h
    expr: |
      sum(rate(thesisminer_stage_completed_total{status="success"}[1h])) by (stage)
      /
      sum(rate(thesisminer_stage_started_total[1h])) by (stage)

  - record: thesisminer:ai_cost_usd:1h
    expr: sum(rate(thesisminer_ai_cost_usd[1h])) by (agent)
```

### 4.6 指标采集与存储

#### 4.6.1 采集架构

```
+----------+     +-------------+     +-------------+     +-----------+
| App Pod  | --> | /metrics    | --> | Prometheus  | --> | Thanos/   |
| (exporter|     | endpoint    |     | (scrape 15s)|     | Cortex    |
+----------+     +-------------+     +-------------+     +-----------+
                                                           |
+----------+     +-------------+     +-------------+        |
| Node     | --> | node_export | --> | Prometheus  | -------+
| Exporter |     | er          |     |             |        |
+----------+     +-------------+     +-------------+        |
                                                           v
+----------+     +-------------+     +-------------+   +-----------+
| cAdvisor | --> | /metrics    | --> | Prometheus  |   | Long-term |
+----------+     +-------------+     +-------------+   | Storage   |
                                                                       | (S3)     |
                                                                       +-----------+
```

#### 4.6.2 Prometheus 配置

```yaml
# deploy/prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: "thesisminer-prod"
    environment: "production"

rule_files:
  - /etc/prometheus/rules/*.yml

alerting:
  alertmanagers:
  - static_configs:
    - targets: ["alertmanager:9093"]

scrape_configs:
- job_name: "thesisminer-app"
  kubernetes_sd_configs:
  - role: pod
  relabel_configs:
  - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
    action: keep
    regex: true
  - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
    action: replace
    target_label: __metrics_path__
    regex: (.+)
  - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_port, __meta_kubernetes_pod_ip]
    action: replace
    target_label: __address__
    regex: (.+);(.+)
    replacement: $2:$1

- job_name: "kubernetes-nodes"
  kubernetes_sd_configs:
  - role: node
  relabel_configs:
  - source_labels: [__address__]
    action: replace
    target_label: __address__
    regex: (.+):.*
    replacement: $1:9100

- job_name: "kubernetes-cadvisor"
  kubernetes_sd_configs:
  - role: node
  relabel_configs:
  - source_labels: [__address__]
    action: replace
    target_label: __address__
    regex: (.+):.*
    replacement: $1:10250
  - source_labels: [__meta_kubernetes_node_name]
    target_label: node
  metric_relabel_configs:
  - source_labels: [__name__]
    regex: "(container_cpu_usage_seconds_total|container_memory_usage_bytes|container_fs_usage_bytes)"
    action: keep
```

#### 4.6.3 长期存储

Prometheus 本地存储 15 天，超过通过 Thanos Send 上传到对象存储：

```yaml
# thanos-sidecar 参数
- --tsdb.path=/prometheus
- --objstore.config-file=/etc/thanos/objstore.yml
- --shipper.upload-compacted
```

```yaml
# objstore.yml
type: S3
config:
  bucket: "thesisminer-metrics"
  endpoint: "s3.cn-north-1.amazonaws.com.cn"
  region: "cn-north-1"
  access_key: "${S3_ACCESS_KEY}"
  secret_key: "${S3_SECRET_KEY}"
```

### 4.7 指标查询与导出

#### 4.7.1 Grafana 查询

Grafana 通过 Prometheus 数据源查询，支持 PromQL 与 PromQL Builder。

#### 4.7.2 API 导出

通过 Prometheus HTTP API 导出指标：

```bash
# 导出某时间范围的指标
curl -G 'http://prometheus:9090/api/v1/query_range' \
  --data-urlencode 'query=thesisminer:http_requests:rate5m' \
  --data-urlencode 'start=2026-06-20T00:00:00Z' \
  --data-urlencode 'end=2026-06-20T23:59:59Z' \
  --data-urlencode 'step=300s'
```

#### 4.7.3 自定义导出脚本

```python
# scripts/export_metrics.py
import requests
import csv
from datetime import datetime, timedelta


def export_metrics(prometheus_url: str, query: str,
                   start: datetime, end: datetime,
                   step: str = "300s", output_file: str = "metrics.csv"):
    """从 Prometheus 导出指标到 CSV。"""
    params = {
        "query": query,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "step": step
    }
    response = requests.get(
        f"{prometheus_url}/api/v1/query_range",
        params=params
    )
    response.raise_for_status()
    data = response.json()

    with open(output_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "value"] + list(
            data["data"]["result"][0]["metric"].keys()
        ))
        for result in data["data"]["result"]:
            metric = result["metric"]
            for timestamp, value in result["values"]:
                dt = datetime.fromtimestamp(int(timestamp))
                writer.writerow([dt, value] + list(metric.values()))


if __name__ == "__main__":
    export_metrics(
        "http://prometheus:9090",
        'thesisminer:http_requests:rate5m{path="/api/v1/thesis/generate"}',
        datetime(2026, 6, 20, 0, 0),
        datetime(2026, 6, 20, 23, 59),
        output_file="thesis_generation_qps_20260620.csv"
    )
```

---

## 5. 分布式追踪设计

### 5.1 追踪模型

ThesisMiner v8.0 采用 OpenTelemetry 标准，追踪模型如下：

```
Trace (一次完整请求)
  |
  +-- Span A: HTTP Request (root span)
        |
        +-- Span B: Orchestrator Dispatch
        |     |
        |     +-- Span C: Searcher Agent
        |     |     |
        |     |     +-- Span D: DeepSeek API Call
        |     |     +-- Span E: Knowledge Base Query
        |     |
        |     +-- Span F: Reasoner Agent
        |           |
        |           +-- Span G: DeepSeek API Call
        |           +-- Span H: Prompt Cache Lookup
        |
        +-- Span I: Stage Transition (literature_mapping -> method_design)
        +-- Span J: Database Write (session state)
```

### 5.2 Span 与 SpanContext

#### 5.2.1 Span 结构

```python
# backend/monitoring/tracing.py
from opentelemetry import trace
from opentelemetry.trace import Span, SpanContext, Status, StatusCode
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter
)
from opentelemetry.sdk.resources import Resource


def setup_tracing(service_name: str = "thesisminer",
                  service_version: str = "8.0.0",
                  otlp_endpoint: str = "http://otel-collector:4317"):
    """初始化 OpenTelemetry 追踪。"""
    resource = Resource.create({
        "service.name": service_name,
        "service.version": service_version,
        "deployment.environment": "${ENVIRONMENT}",
    })

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint=otlp_endpoint)
        )
    )
    trace.set_tracer_provider(provider)


def get_tracer(name: str = "thesisminer"):
    return trace.get_tracer(name)
```

#### 5.2.2 Span 属性规范

每个 Span 必须包含以下属性：

| 属性 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `thesisminer.session_id` | string | 是 | 会话 ID |
| `thesisminer.conversation_id` | string | 否 | 对话 ID |
| `thesisminer.user_id` | string | 否 | 用户 ID（脱敏） |
| `thesisminer.agent` | string | 否 | Agent 名 |
| `thesisminer.stage` | string | 否 | 五阶段之一 |
| `thesisminer.cache_segment` | string | 否 | 缓存段 |
| `http.method` | string | HTTP Span | GET/POST/... |
| `http.url` | string | HTTP Span | 请求 URL |
| `http.status_code` | int | HTTP Span | 状态码 |
| `db.system` | string | DB Span | sqlite |
| `db.statement` | string | DB Span | SQL 语句（脱敏） |

#### 5.2.3 Span 创建示例

```python
# backend/agents/orchestrator.py
from backend.monitoring.tracing import get_tracer

tracer = get_tracer("thesisminer.orchestrator")


class Orchestrator:
    @tracer.start_as_current_span("orchestrator.dispatch")
    async def dispatch(self, query: str, session_id: str, stage: str):
        span = trace.get_current_span()
        span.set_attribute("thesisminer.session_id", session_id)
        span.set_attribute("thesisminer.stage", stage)
        span.set_attribute("thesisminer.agent", "orchestrator")
        span.set_attribute("query.length", len(query))

        target_agent = self._select_agent(query, stage)
        span.set_attribute("thesisminer.target_agent", target_agent)

        try:
            result = await self._invoke_agent(target_agent, query, session_id)
            span.set_status(Status(StatusCode.OK))
            return result
        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            raise
```

### 5.3 上下文传播

#### 5.3.1 HTTP 传播

通过 W3C Trace Context 标准传播 `traceparent` 头：

```python
# backend/monitoring/middleware.py
from opentelemetry import trace
from opentelemetry.propagate import inject, extract


class TracingMiddleware:
    async def dispatch(self, request: Request, call_next):
        # 从请求头提取上下文
        context = extract(request.headers)

        # 创建 root span
        tracer = trace.get_tracer("thesisminer.http")
        with tracer.start_as_current_span(
            f"{request.method} {request.url.path}",
            context=context,
            kind=trace.SpanKind.SERVER
        ) as span:
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.url", str(request.url))
            span.set_attribute("http.scheme", request.url.scheme)
            span.set_attribute("http.host", request.url.host)
            span.set_attribute("net.peer.ip", request.client.host
                               if request.client else "")

            response = await call_next(request)

            span.set_attribute("http.status_code", response.status_code)
            if response.status_code >= 500:
                span.set_status(Status(StatusCode.ERROR))
            else:
                span.set_status(Status(StatusCode.OK))

            # 注入上下文到响应头
            inject(response.headers)
            return response
```

#### 5.3.2 异步任务传播

Multi-Agent 架构中，Orchestrator 异步分发到 sub-agent，需手动传播上下文：

```python
# backend/orchestration/async_dispatch.py
import asyncio
from opentelemetry import trace
from opentelemetry.context import attach, detach, get_current


class AsyncDispatcher:
    async def dispatch_all(self, agents: list, query: str, session_id: str):
        """并行分发到多个 agent，保留追踪上下文。"""
        parent_context = get_current()

        async def run_with_context(agent_name: str):
            token = attach(parent_context)
            try:
                tracer = trace.get_tracer("thesisminer.dispatcher")
                with tracer.start_as_current_span(
                    f"async.{agent_name}",
                    kind=trace.SpanKind.INTERNAL
                ) as span:
                    span.set_attribute("thesisminer.agent", agent_name)
                    span.set_attribute("thesisminer.session_id", session_id)
                    return await self._invoke(agent_name, query, session_id)
            finally:
                detach(token)

        tasks = [run_with_context(agent) for agent in agents]
        return await asyncio.gather(*tasks, return_exceptions=True)
```

#### 5.3.3 数据库上下文传播

```python
# backend/sessions/database.py
from opentelemetry.instrumentation.sqlite3 import SQLite3Instrumentor

# 自动埋点 SQLite
SQLite3Instrumentor().instrument()


# 手动埋点示例
class TracedDatabase:
    @tracer.start_as_current_span("db.execute")
    async def execute(self, sql: str, params: tuple):
        span = trace.get_current_span()
        span.set_attribute("db.system", "sqlite")
        span.set_attribute("db.operation", self._extract_operation(sql))
        span.set_attribute("db.statement", self._redact_sql(sql))
        span.set_attribute("db.param_count", len(params))

        start = time.time()
        try:
            result = await self._conn.execute(sql, params)
            span.set_attribute("db.rows_affected", result.rowcount)
            return result
        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            raise
        finally:
            span.set_attribute("db.duration_ms", int((time.time() - start) * 1000))
```

### 5.4 采样策略

全量追踪成本过高，ThesisMiner v8.0 采用分层采样：

| 采样类型 | 比例 | 触发条件 | 说明 |
|----------|------|----------|------|
| 全量采样 | 100% | ERROR/FATAL 请求 | 所有错误请求必采 |
| 高比例采样 | 50% | 慢请求（P99 以上） | 慢请求高比例采样 |
| 常规采样 | 10% | 正常请求 | 常规请求按比例 |
| 业务关键 | 100% | 论文生成、导出 | 关键业务必采 |
| 调试采样 | 100% | 带 `X-Debug: true` 头 | 主动调试必采 |

**OpenTelemetry Sampler 配置**：

```python
# backend/monitoring/sampler.py
from opentelemetry.sdk.trace.sampling import (
    Sampler, SamplingResult, Decision,
    ParentBased, TraceIdRatioBased, ALWAYS_ON
)
from opentelemetry.trace import Link, SpanKind
from opentelemetry.trace.span import TraceState


class ThesisMinerSampler(Sampler):
    """ThesisMiner 自定义采样器。"""

    def __init__(self):
        self._default_sampler = ParentBased(
            TraceIdRatioBased(rate=0.1)
        )

    def should_sample(self, parent_context, trace_id, name,
                      kind=None, attributes=None, links=None):
        attributes = attributes or {}

        # 错误请求全量采样
        if attributes.get("http.status_code", 0) >= 500:
            return SamplingResult(Decision.RECORD_AND_SAMPLE, attributes)

        # 慢请求高比例采样
        duration = attributes.get("http.duration_ms", 0)
        if duration > 1000:
            return SamplingResult(Decision.RECORD_AND_SAMPLE, attributes)

        # 关键业务全量采样
        path = attributes.get("http.path", "")
        if path in ("/api/v1/thesis/generate", "/api/v1/thesis/export"):
            return SamplingResult(Decision.RECORD_AND_SAMPLE, attributes)

        # 调试请求全量采样
        if attributes.get("http.header.x-debug") == "true":
            return SamplingResult(Decision.RECORD_AND_SAMPLE, attributes)

        # 默认 10% 采样
        return self._default_sampler.should_sample(
            parent_context, trace_id, name, kind, attributes, links
        )

    def get_description(self):
        return "ThesisMinerSampler"
```

### 5.5 追踪后端

ThesisMiner v8.0 使用 Jaeger 作为追踪后端，通过 OpenTelemetry Collector 转发：

```
+----------+     +------------------+     +-----------+
| App Pod  | --> | OTLP gRPC/HTTP   | --> | OTel      |
| (SDK)    |     | 4317/4318        |     | Collector |
+----------+     +------------------+     +-----------+
                                                   |
                          +------------------------+------------------------+
                          |                        |                        |
                          v                        v                        v
                    +-----------+           +-----------+           +-----------+
                    | Jaeger    |           | Prometheus |           | Loki      |
                    | (traces)  |           | (metrics   |           | (logs)    |
                    +-----------+           |  from span)|           +-----------+
                          |                 +-----------+
                          v
                    +-----------+
                    | Elasticsearch |
                    | (storage)     |
                    +-----------+
```

**OTel Collector 配置**：

```yaml
# deploy/otel-collector/config.yml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 5s
    send_batch_size: 1000

  memory_limiter:
    check_interval: 1s
    limit_mib: 512
    spike_limit_mib: 128

  # 从 span 生成指标
  spanmetrics:
    metrics_exporter: prometheus
    latency_histogram_buckets:
      [100us, 1ms, 5ms, 10ms, 50ms, 100ms, 500ms, 1s, 5s, 10s]

  # 资源属性处理
  resource:
    attributes:
    - key: deployment.environment
      value: "${ENVIRONMENT}"
      action: upsert

  # 敏感属性过滤
  filter:
    error_mode: ignore
    traces:
      span:
      - 'attributes["http.request.body"] != nil'
      - 'attributes["thesisminer.user_input"] != nil'

exporters:
  jaeger:
    endpoint: jaeger-collector:14250
    tls:
      insecure: true

  prometheus:
    endpoint: 0.0.0.0:8889

  loki:
    endpoint: http://loki:3100/loki/api/v1/push
    labels:
      attributes:
        thesisminer.agent: "agent"
        thesisminer.stage: "stage"

service:
  pipelines:
  traces:
    receivers: [otlp]
    processors: [memory_limiter, filter, resource, batch, spanmetrics]
    exporters: [jaeger, loki]

  metrics:
    receivers: [otlp]
    processors: [memory_limiter, resource, batch]
    exporters: [prometheus]
```

### 5.6 链路分析与可视化

#### 5.6.1 Jaeger UI 查询

**按服务查询**：选择 `thesisminer` 服务，查看所有 Trace。

**按操作查询**：选择 `orchestrator.dispatch` 操作，查看所有分发链路。

**按标签查询**：

```
thesisminer.stage=method_design AND thesisminer.agent=reasoner
```

**按耗时查询**：

```
duration>1s
```

#### 5.6.2 链路分析维度

| 分析维度 | 说明 | 应用场景 |
|----------|------|----------|
| 服务依赖图 | 服务间调用关系 | 识别耦合、循环依赖 |
| 耗时分布 | Span 耗时分布 | 定位慢调用 |
| 错误率 | Span 错误率 | 定位错误热点 |
| 调用拓扑 | 调用路径 | 理解请求流 |
| 对比分析 | 正常 vs 异常 Trace | 根因定位 |

#### 5.6.3 服务依赖图示例

```
                +-----------------+
                | API Gateway     |
                +-----------------+
                         |
                         v
                +-----------------+
                | ThesisMiner App |
                | (FastAPI)       |
                +-----------------+
                    |   |   |
        +-----------+   |   +-----------+
        v               v               v
+----------------+ +----------+ +----------------+
| DeepSeek API   | | SQLite   | | Prompt Cache   |
| (external)     | | (WAL)    | | (Redis)        |
+----------------+ +----------+ +----------------+
```

---

## 6. 告警体系设计

### 6.1 告警架构

```
+----------+     +-----------+     +-------------+     +-----------+
| Metrics  | --> | Prometheus| --> | Alertmanager| --> | Notification|
| /Logs    |     | (rules)   |     | (route/     |     | Channels   |
| /Traces  |     |           |     |  inhibit)   |     | (Slack/Pager|
+----------+     +-----------+     +-------------+     | Duty/Email)|
                                                       +-----------+
```

### 6.2 告警规则

#### 6.2.1 系统告警规则

```yaml
# deploy/prometheus/rules/system-alerts.yml
groups:
- name: thesisminer-system
  rules:

  # CPU 使用率过高
  - alert: HighCpuUsage
    expr: |
      100 - avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100 > 80
    for: 10m
    labels:
      severity: warning
      team: sre
    annotations:
      summary: "CPU usage > 80% on {{ $labels.instance }}"
      description: "CPU usage is {{ $value }}% for 10 minutes."
      runbook: "https://wiki.thesisminer.io/runbooks/high-cpu"

  # 内存使用率过高
  - alert: HighMemoryUsage
    expr: |
      (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100 > 85
    for: 5m
    labels:
      severity: warning
      team: sre
    annotations:
      summary: "Memory usage > 85% on {{ $labels.instance }}"

  # 磁盘空间不足
  - alert: DiskSpaceLow
    expr: |
      (1 - node_filesystem_avail_bytes{fstype!~"tmpfs|overlay"} /
            node_filesystem_size_bytes{fstype!~"tmpfs|overlay"}) * 100 > 85
    for: 5m
    labels:
      severity: critical
      team: sre
    annotations:
      summary: "Disk space < 15% on {{ $labels.instance }}"

  # 文件描述符耗尽
  - alert: FileDescriptorsExhaustion
    expr: |
      process_open_fds / process_max_fds > 0.8
    for: 5m
    labels:
      severity: warning
      team: sre
```

#### 6.2.2 应用告警规则

```yaml
# deploy/prometheus/rules/app-alerts.yml
groups:
- name: thesisminer-app
  rules:

  # HTTP 5xx 错误率过高
  - alert: HighHttpErrorRate
    expr: |
      thesisminer:http_error_rate:ratio5m > 0.05
    for: 5m
    labels:
      severity: critical
      team: backend
    annotations:
      summary: "HTTP 5xx error rate > 5%"
      description: "Path {{ $labels.path }} error rate is {{ $value }}"

  # P99 延迟过高
  - alert: HighLatencyP99
    expr: |
      thesisminer:p99_latency:5m > 5
    for: 10m
    labels:
      severity: warning
      team: backend
    annotations:
      summary: "P99 latency > 5s on {{ $labels.path }}"

  # 服务不可用
  - alert: ServiceDown
    expr: up{job="thesisminer-app"} == 0
    for: 1m
    labels:
      severity: critical
      team: sre
    annotations:
      summary: "ThesisMiner service down on {{ $labels.instance }}"

  # Pod 重启次数过多
  - alert: PodRestartLoop
    expr: |
      increase(kube_pod_container_status_restarts_total{container="thesisminer"}[1h]) > 5
    for: 5m
    labels:
      severity: warning
      team: sre
```

#### 6.2.3 业务告警规则

```yaml
# deploy/prometheus/rules/business-alerts.yml
groups:
- name: thesisminer-business
  rules:

  # 论文生成失败率过高
  - alert: HighThesisFailureRate
    expr: |
      sum(rate(thesisminer_thesis_failed_total[15m])) by (stage)
      /
      sum(rate(thesisminer_thesis_generated_total[15m])) by (stage)
      > 0.1
    for: 10m
    labels:
      severity: critical
      team: backend
    annotations:
      summary: "Thesis generation failure rate > 10% for stage {{ $labels.stage }}"

  # 五阶段完成率过低
  - alert: LowStageCompletionRate
    expr: |
      thesisminer:stage_completion_rate:1h < 0.9
    for: 30m
    labels:
      severity: warning
      team: backend
    annotations:
      summary: "Stage completion rate < 90% for {{ $labels.stage }}"

  # 阶段回环次数过多
  - alert: ExcessiveStageLoopBack
    expr: |
      increase(thesisminer_stage_loop_back_total[1h]) > 50
    for: 5m
    labels:
      severity: warning
      team: backend
    annotations:
      summary: "Stage loop-back > 50 times in 1h"
      description: "From {{ $labels.from_stage }} to {{ $labels.to_stage }}"

  # 上下文隔离违规
  - alert: ContextIsolationViolation
    expr: |
      increase(thesisminer_context_isolation_violation_total[5m]) > 0
    for: 1m
    labels:
      severity: critical
      team: backend
    annotations:
      summary: "Context isolation violation detected"
```

#### 6.2.4 AI 调用告警规则

```yaml
# deploy/prometheus/rules/ai-alerts.yml
groups:
- name: thesisminer-ai
  rules:

  # DeepSeek API 错误率过高
  - alert: HighDeepSeekErrorRate
    expr: |
      sum(rate(thesisminer_ai_calls_total{status="error"}[5m])) by (agent)
      /
      sum(rate(thesisminer_ai_calls_total[5m])) by (agent)
      > 0.1
    for: 5m
    labels:
      severity: critical
      team: backend
    annotations:
      summary: "DeepSeek API error rate > 10% for agent {{ $labels.agent }}"

  # DeepSeek 限流
  - alert: DeepSeekRateLimited
    expr: |
      increase(thesisminer_ai_rate_limit_total[5m]) > 10
    for: 2m
    labels:
      severity: warning
      team: backend
    annotations:
      summary: "DeepSeek rate limited > 10 times in 5m"

  # 缓存命中率过低
  - alert: LowCacheHitRate
    expr: |
      thesisminer:cache_hit_rate:5m{segment="session_context"} < 0.5
    for: 30m
    labels:
      severity: warning
      team: backend
    annotations:
      summary: "Prompt cache hit rate < 50% for {{ $labels.segment }}"

  # AI 成本异常
  - alert: AiCostAnomaly
    expr: |
      thesisminer:ai_cost_usd:1h > 100
    for: 1h
    labels:
      severity: warning
      team: backend
    annotations:
      summary: "AI cost > $100/hour for agent {{ $labels.agent }}"
```

#### 6.2.5 数据库告警规则

```yaml
# deploy/prometheus/rules/database-alerts.yml
groups:
- name: thesisminer-database
  rules:

  # SQLite WAL 文件过大
  - alert: LargeWalFile
    expr: |
      thesisminer_db_wal_size_bytes > 1073741824  # 1GB
    for: 10m
    labels:
      severity: warning
      team: backend
    annotations:
      summary: "SQLite WAL file > 1GB"

  # 数据库锁竞争
  - alert: DatabaseLockContention
    expr: |
      increase(thesisminer_db_lock_contention_total[5m]) > 100
    for: 5m
    labels:
      severity: critical
      team: backend
    annotations:
      summary: "SQLite lock contention > 100 in 5m"

  # 慢查询
  - alert: SlowDatabaseQuery
    expr: |
      rate(thesisminer_db_query_duration_seconds_bucket{le="1"}[5m]) > 0
    for: 5m
    labels:
      severity: warning
      team: backend
    annotations:
      summary: "Slow SQLite query detected (>1s)"
```

### 6.3 告警级别

ThesisMiner v8.0 采用四级告警：

| 级别 | 标签 | 响应时间 | 通知方式 | 示例 |
|------|------|----------|----------|------|
| P0 Critical | `severity=critical` | 立即（< 5 分钟） | PagerDuty + 电话 + Slack | 服务宕机、数据丢失 |
| P1 High | `severity=high` | 15 分钟 | PagerDuty + Slack | 错误率 > 10% |
| P2 Warning | `severity=warning` | 1 小时 | Slack | CPU > 80% |
| P3 Info | `severity=info` | 工作日处理 | Slack（静默） | 缓存命中率下降 |

### 6.4 告警通知

#### 6.4.1 Alertmanager 配置

```yaml
# deploy/alertmanager/config.yml
global:
  resolve_timeout: 5m
  slack_api_url: "${SLACK_WEBHOOK_URL}"

templates:
- /etc/alertmanager/templates/*.tmpl

receivers:
- name: "pagerduty-critical"
  pagerduty_configs:
  - service_key: "${PAGERDUTY_SERVICE_KEY}"
    severity: critical
    send_resolved: true

- name: "slack-critical"
  slack_configs:
  - channel: "#thesisminer-alerts"
    send_resolved: true
    title: '{{ .CommonLabels.alertname }}'
    text: '{{ .CommonAnnotations.summary }}'

- name: "slack-warning"
  slack_configs:
  - channel: "#thesisminer-warnings"
    send_resolved: true

- name: "email"
  email_configs:
  - to: "sre@thesisminer.io"
    send_resolved: true

route:
  group_by: ["alertname", "cluster", "severity"]
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: "slack-warning"

  routes:
  - match:
      severity: critical
    receiver: "pagerduty-critical"
    group_wait: 10s
    repeat_interval: 1h
    continue: true

  - match:
      severity: critical
    receiver: "slack-critical"

  - match:
      severity: warning
    receiver: "slack-warning"

  - match:
      team: backend
    receiver: "slack-backend"
    group_by: ["alertname", "stage"]

  - match_re:
      severity: info
    receiver: "slack-info"
    group_wait: 1h
    repeat_interval: 24h
```

#### 6.4.2 通知模板

```go
// deploy/alertmanager/templates/thesisminer.tmpl
{{ define "thesisminer.title" -}}
[{{ .Status | toUpper }}] {{ .CommonLabels.alertname }}
{{- end }}

{{ define "thesisminer.text" -}}
{{ range .Alerts }}
*Alert:* {{ .Labels.alertname }}
*Severity:* {{ .Labels.severity }}
*Stage:* {{ .Labels.stage | default "N/A" }}
*Summary:* {{ .Annotations.summary }}
*Description:* {{ .Annotations.description }}
*Started:* {{ .StartsAt.Format "2006-01-02 15:04:05" }}
*Runbook:* {{ .Annotations.runbook | default "N/A" }}
{{ if .GeneratorURL }}*Source:* {{ .GeneratorURL }}{{ end }}
{{ end }}
{{- end }}
```

### 6.5 告警抑制与去重

#### 6.5.1 抑制规则

当高级别告警触发时，抑制相关低级别告警，避免"告警风暴"：

```yaml
# deploy/alertmanager/config.yml (inhibit_rules)
inhibit_rules:

# 服务宕机时，抑制该服务的其他告警
- source_match:
    alertname: ServiceDown
    severity: critical
  target_match:
    severity: warning
  equal: ["instance", "service"]

# 数据库宕机时，抑制数据库相关告警
- source_match:
    alertname: DatabaseDown
    severity: critical
  target_match_re:
    alertname: "(SlowDatabaseQuery|LargeWalFile|DatabaseLockContention)"
  equal: ["instance"]

# 网络分区时，抑制应用告警
- source_match:
    alertname: NetworkPartition
    severity: critical
  target_match_re:
    alertname: "(HighHttpErrorRate|HighLatencyP99)"
  equal: ["cluster"]

# DeepSeek API 全局故障时，抑制单 agent 告警
- source_match:
    alertname: DeepSeekGlobalOutage
    severity: critical
  target_match_re:
    alertname: "(HighDeepSeekErrorRate|DeepSeekRateLimited)"
```

#### 6.5.2 去重策略

Alertmanager 通过 `group_by` 自动去重：

```yaml
group_by: ["alertname", "cluster", "severity", "stage", "agent"]
```

相同 `group_by` 的告警合并为一个通知，避免重复打扰。

### 6.6 告警路由

按团队路由告警到不同渠道：

```yaml
route:
  routes:
  # SRE 团队：基础设施告警
  - match:
      team: sre
    receiver: "pagerduty-sre"
    group_by: ["alertname", "instance"]

  # Backend 团队：应用告警
  - match:
      team: backend
    receiver: "slack-backend"
    group_by: ["alertname", "stage", "agent"]

  # Data 团队：数据相关告警
  - match:
      team: data
    receiver: "slack-data"

  # 工作时间外，P3 告警静默
  - match:
      severity: info
    active_time_intervals:
    - business_hours
    receiver: "slack-info"

time_intervals:
- name: business_hours
  time_intervals:
  - weekdays: ["monday:friday"]
    times:
    - start_time: 09:00
      end_time: 18:00
```

### 6.7 告警闭环管理

#### 6.7.1 告警生命周期

```
[触发] --> [通知] --> [确认] --> [处理] --> [恢复] --> [复盘]
   |          |          |          |          |          |
   v          v          v          v          v          v
 Prometheus  Alertmgr   OnCall    Engineer   Auto/      Postmortem
                                                        Manual
```

#### 6.7.2 告警质量度量

| 指标 | 目标 | 说明 |
|------|------|------|
| 告警准确率 | > 95% | 触发后确实存在问题的比例 |
| 告警恢复率 | > 90% | 自动恢复的比例 |
| 平均响应时间 | < 5 分钟（P0） | 从通知到确认的时间 |
| 平均处理时间 | < 30 分钟（P0） | 从确认到恢复的时间 |
| 告警噪音率 | < 5% | 误告警 + 重复告警比例 |

#### 6.7.3 告警治理流程

1. **每周告警审查**：SRE 团队每周审查告警，识别噪音
2. **告警调优**：调整阈值、for 时长、抑制规则
3. **告警归档**：废弃的告警规则归档，避免复活
4. **告警 Runbook**：每个告警必须有对应 Runbook，说明处理步骤

---

## 7. 仪表盘与可视化

### 7.1 仪表盘设计原则

ThesisMiner v8.0 仪表盘设计遵循以下原则：

| 原则 | 说明 |
|------|------|
| **目的明确** | 每个仪表盘回答一个核心问题 |
| **层次清晰** | 从概览到细节，逐层下钻 |
| **色彩克制** | 绿/黄/红三色，避免彩虹色 |
| **实时性** | 关键指标 5-15 秒刷新 |
| **可下钻** | 点击图表跳转到日志/追踪 |
| **可分享** | 支持生成快照、链接、PDF |

### 7.2 业务仪表盘

#### 7.2.1 论文生成概览仪表盘

**Panel 1：论文生成 QPS（时序图）**

```promql
sum(rate(thesisminer_thesis_generated_total[5m])) by (stage)
```

**Panel 2：阶段完成率（时序图）**

```promql
thesisminer:stage_completion_rate:1h
```

**Panel 3：生成耗时分布（热力图）**

```promql
sum(rate(thesisminer_thesis_generation_duration_seconds_bucket[5m])) by (le, stage)
```

**Panel 4：失败原因 Top 10（饼图）**

```promql
topk(10, sum by (error_type) (rate(thesisminer_thesis_failed_total[1h])))
```

**Panel 5：当前进行中（仪表盘）**

```promql
sum(thesisminer_thesis_in_progress)
```

#### 7.2.2 Multi-Agent 仪表盘

**Panel 1：Agent 调用 QPS**

```promql
sum(rate(thesisminer_agent_invocations_total[5m])) by (agent)
```

**Panel 2：Agent 耗时 P99**

```promql
histogram_quantile(0.99,
  sum(rate(thesisminer_agent_duration_seconds_bucket[5m])) by (le, agent)
)
```

**Panel 3：Agent 错误率**

```promql
sum(rate(thesisminer_agent_errors_total[5m])) by (agent)
/
sum(rate(thesisminer_agent_invocations_total[5m])) by (agent)
```

**Panel 4：Orchestrator 分发分布**

```promql
sum(rate(thesisminer_orchestrator_dispatch_total[5m])) by (target_agent)
```

#### 7.2.3 五阶段闭环仪表盘

**Panel 1：阶段流转桑基图（Sankey）**

展示五阶段间的流转关系，宽度代表流量。

**Panel 2：阶段回环次数**

```promql
sum(increase(thesisminer_stage_loop_back_total[1h])) by (from_stage, to_stage)
```

**Panel 3：阶段迭代次数分布**

```promql
histogram_quantile(0.95,
  sum(rate(thesisminer_stage_iteration_count_bucket[1h])) by (le, stage)
)
```

### 7.3 系统仪表盘

#### 7.3.1 资源概览仪表盘

**Panel 1：CPU 使用率（多实例）**

```promql
100 - avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100
```

**Panel 2：内存使用率**

```promql
(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100
```

**Panel 3：磁盘使用率**

```promql
(1 - node_filesystem_avail_bytes / node_filesystem_size_bytes) * 100
```

**Panel 4：网络流量**

```promql
rate(node_network_receive_bytes_total[5m]) * 8
```

#### 7.3.2 数据库仪表盘

**Panel 1：SQLite 连接数**

```promql
thesisminer_db_connections
```

**Panel 2：WAL 文件大小**

```promql
thesisminer_db_wal_size_bytes
```

**Panel 3：查询耗时 P99**

```promql
histogram_quantile(0.99,
  sum(rate(thesisminer_db_query_duration_seconds_bucket[5m])) by (le, operation)
)
```

**Panel 4：Checkpoint 频率**

```promql
rate(thesisminer_db_wal_checkpoint_total[1h])
```

### 7.4 SLO 仪表盘

#### 7.4.1 SLO 概览

| SLO | 目标 | 当前 | 错误预算剩余 |
|-----|------|------|--------------|
| 论文生成可用性 | 99.9% | 99.95% | 75% |
| API 延迟 P99 < 5s | 99% | 99.5% | 60% |
| 五阶段完成率 | 95% | 96% | 80% |

#### 7.4.2 错误预算燃烧率

```promql
# 1 小时燃烧率
1 - (
  sum(rate(thesisminer_thesis_generated_total{status="success"}[1h]))
  /
  sum(rate(thesisminer_thesis_generated_total[1h]))
) / (1 - 0.999)
```

```promql
# 30 天错误预算剩余
1 - (
  1 - (
    sum(rate(thesisminer_thesis_generated_total{status="success"}[30d]))
    /
    sum(rate(thesisminer_thesis_generated_total[30d]))
  )
) / (1 - 0.999)
```

### 7.5 报表与导出

#### 7.5.1 日报

每天 09:00 自动生成并发送：

- 昨日论文生成数、成功率、平均耗时
- 昨日 DeepSeek 调用次数、Token 消耗、成本
- 昨日告警数、处理时长
- 昨日 Top 5 慢请求

#### 7.5.2 周报

每周一 09:00 自动生成：

- 上周 SLO 达成情况
- 上周错误预算燃烧情况
- 上周事故列表
- 上周容量变化

#### 7.5.3 月报

每月 1 日 09:00 自动生成：

- 上月业务指标趋势
- 上月成本分析
- 上月容量规划建议
- 上月 Postmortem 汇总

---

## 8. 服务网格可观测性

### 8.1 Istio/Envoy 集成

ThesisMiner v8.0 在 Kubernetes 上使用 Istio 服务网格，自动获得网格级可观测性。

#### 8.1.1 Istio 架构

```
+------------------+     +------------------+     +------------------+
| Control Plane    |     | Data Plane       |     | Observability    |
| (istiod)         |     | (Envoy sidecar)  |     | Stack            |
+------------------+     +------------------+     +------------------+
        |                        |                        |
        |  config push           |  metrics/logs/traces   |
        v                        v                        v
+------------------+     +------------------+     +------------------+
| Pilot            |     | Pod A (Envoy)    | --> | Prometheus       |
| Citadel          |     | Pod B (Envoy)    | --> | Jaeger           |
| Galley           |     | Pod C (Envoy)    | --> | Kibana           |
+------------------+     +------------------+     +------------------+
```

#### 8.1.2 启用可观测性

```yaml
# deploy/istio/istio-operator.yaml
apiVersion: install.istio.io/v1alpha1
kind: IstioOperator
metadata:
  namespace: istio-system
  name: thesisminer-istio
spec:
  meshConfig:
    accessLogFile: /dev/stdout
    accessLogEncoding: JSON
    accessLogFormat: |
      {"timestamp":"%START_TIME%","method":"%REQ(:METHOD)%",
       "path":"%REQ(X-ENVOY-ORIGINAL-PATH?:PATH)%",
       "protocol":"%PROTOCOL%","response_code":"%RESPONSE_CODE%",
       "response_flags":"%RESPONSE_FLAGS%","duration":"%DURATION%",
       "upstream_service":"%UPSTREAM_HOST%","trace_id":"%REQ(X-B3-TRACEID)%",
       "span_id":"%REQ(X-B3-SPANID)%","bytes_sent":"%BYTES_SENT%",
       "bytes_received":"%BYTES_RECEIVED%"}

    defaultConfig:
      tracing:
        sampling: 10.0
        max_path_tag_length: 256

  values:
    tracing:
      jaeger:
        hub: jaegertracing
        tag: "1.39"

    kiali:
      enabled: true

    prometheus:
      enabled: true
```

### 8.2 网格指标

Istio 自动生成黄金信号指标：

| 指标 | 说明 |
|------|------|
| `istio_requests_total` | 请求总数 |
| `istio_request_duration_milliseconds` | 请求耗时 |
| `istio_request_bytes` | 请求大小 |
| `istio_response_bytes` | 响应大小 |
| `istio_tcp_connections_opened_total` | TCP 连接打开数 |
| `istio_tcp_connections_closed_total` | TCP 连接关闭数 |

**网格级 QPS**：

```promql
sum(rate(istio_requests_total{destination_service=~"thesisminer.*"}[5m])) by (destination_service)
```

**网格级错误率**：

```promql
sum(rate(istio_requests_total{destination_service=~"thesisminer.*", response_code=~"5.."}[5m]))
/
sum(rate(istio_requests_total{destination_service=~"thesisminer.*"}[5m]))
```

### 8.3 网格追踪

Istio 自动为网格内调用注入追踪头（W3C Trace Context / B3）：

```
Client --> Envoy (inject trace) --> Server Envoy (extract trace) --> Server App
```

无需修改应用代码即可获得网格内调用链。

### 8.4 网格日志

Envoy access log 自动记录每个请求：

```json
{
  "timestamp": "2026-06-20T10:30:45.123Z",
  "method": "POST",
  "path": "/api/v1/thesis/generate",
  "protocol": "HTTP/1.1",
  "response_code": 200,
  "response_flags": "-",
  "duration": 1234,
  "upstream_service": "thesisminer-app.default.svc.cluster.local:8000",
  "trace_id": "abc123def456",
  "span_id": "span789",
  "bytes_sent": 2048,
  "bytes_received": 512
}
```

`response_flags` 字段含义：

| Flag | 含义 |
|------|------|
| `-` | 正常 |
| `UH` | 上游无健康主机 |
| `UF` | 上游连接失败 |
| `UO` | 上游溢出（熔断） |
| `NR` | 无路由 |
| `DI` | 请求被拒绝（断路） |
| `RL` | 限流 |

---

## 9. SRE 方法论

### 9.1 SLI/SLO/SLA

#### 9.1.1 定义

| 概念 | 说明 | ThesisMiner 示例 |
|------|------|------------------|
| SLI | 服务级别指标 | 论文生成成功率 |
| SLO | 服务级别目标 | 成功率 ≥ 99.9% |
| SLA | 服务级别协议 | 成功率 < 99% 时赔偿 |

#### 9.1.2 ThesisMiner v8.0 SLI/SLO

| SLI | 计算 | SLO | 窗口 |
|-----|------|-----|------|
| 论文生成可用性 | 成功请求数 / 总请求数 | 99.9% | 30 天滚动 |
| API 延迟 | P99 < 5s 的请求比例 | 99% | 30 天滚动 |
| 五阶段完成率 | 完成数 / 启动数 | 95% | 30 天滚动 |
| 导出成功率 | 成功导出数 / 总导出数 | 99.5% | 30 天滚动 |
| DeepSeek 调用成功率 | 成功调用数 / 总调用数 | 99% | 30 天滚动 |

#### 9.1.3 SLI 实现示例

```python
# backend/monitoring/sli.py
from prometheus_client import Counter


class ThesisAvailabilitySLI:
    """论文生成可用性 SLI。"""

    def __init__(self):
        self.good_events = Counter(
            "thesisminer_sli_thesis_availability_good",
            "Good events for thesis availability SLI"
        )
        self.bad_events = Counter(
            "thesisminer_sli_thesis_availability_bad",
            "Bad events for thesis availability SLI"
        )

    def record_success(self):
        self.good_events.inc()

    def record_failure(self):
        self.bad_events.inc()


# SLO 查询
# good / (good + bad) >= 0.999
```

### 9.2 错误预算

#### 9.2.1 计算

错误预算 = 1 - SLO

对于 SLO = 99.9%，30 天窗口：

- 总分钟数 = 30 * 24 * 60 = 43200 分钟
- 允许不可用 = 43200 * 0.1% = 43.2 分钟

#### 9.2.2 错误预算策略

| 错误预算剩余 | 策略 |
|--------------|------|
| > 50% | 正常发布，可推进新功能 |
| 25% - 50% | 谨慎发布，优先修复稳定性问题 |
| < 25% | 冻结非紧急发布，全员聚焦稳定性 |
| < 0 | 紧急修复，停止所有非紧急变更 |

#### 9.2.3 错误预算告警

```yaml
# 错误预算燃烧率告警（基于多窗口多燃烧率）
groups:
- name: error-budget
  rules:

  # 快速燃烧：2% 预算在 1 小时内耗尽
  - alert: ErrorBudgetFastBurn
    expr: |
      (
        job:slo_errors_per_request:ratio_rate1h > 14.4 * 0.001
        and
        job:slo_errors_per_request:ratio_rate5m > 14.4 * 0.001
      )
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "Error budget burning fast"

  # 慢速燃烧：10% 预算在 3 天内耗尽
  - alert: ErrorBudgetSlowBurn
    expr: |
      (
        job:slo_errors_per_request:ratio_rate3d > 1 * 0.001
        and
        job:slo_errors_per_request:ratio_rate6h > 1 * 0.001
      )
    for: 1h
    labels:
      severity: warning
    annotations:
      summary: "Error budget burning slow"
```

### 9.3 Toil 管理

#### 9.3.1 Toil 定义

Toil 是指：**重复的、可自动化的、无持久价值的运维工作**。

#### 9.3.2 Toil 上限

SRE 团队 Toil 工作时间应 < 50%，剩余时间用于工程化。

#### 9.3.3 Toil 识别与消除

| Toil 类型 | 自动化方案 |
|-----------|------------|
| 手动重启服务 | 自动重启 + 自愈 |
| 手动扩容 | HPA 自动扩容 |
| 手动清理日志 | ILM 自动滚动 |
| 手动处理告警 | Runbook Automation |
| 手动备份验证 | 自动化备份验证 |

### 9.4 事故管理

#### 9.4.1 事故分级

| 级别 | 影响 | 响应 | 示例 |
|------|------|------|------|
| SEV-1 | 全站不可用 | 立即，全员 | 数据库宕机 |
| SEV-2 | 核心功能不可用 | 15 分钟，相关团队 | 论文生成失败 |
| SEV-3 | 部分功能受影响 | 1 小时 | 导出功能异常 |
| SEV-4 | 轻微影响 | 工作日处理 | UI 显示问题 |

#### 9.4.2 事故响应流程

```
[检测] --> [分级] --> [响应] --> [缓解] --> [恢复] --> [复盘]
   |          |          |          |          |          |
   v          v          v          v          v          v
 告警/用户   IC 分级   OnCall     临时修复   根因修复   Postmortem
            指定      响应
```

#### 9.4.3 事故指挥（Incident Commander）

- **IC 角色**：协调响应，不直接修复
- **IC 职责**：分级、协调、沟通、决策
- **IC 轮值**：SRE 团队成员轮流担任

#### 9.4.4 Postmortem 模板

```markdown
# Postmortem: [事故标题]

## 事故摘要
- **事故 ID**: INC-2026-001
- **发生时间**: 2026-06-20 10:30 UTC
- **恢复时间**: 2026-06-20 11:15 UTC
- **影响时长**: 45 分钟
- **影响范围**: 论文生成功能不可用
- **影响用户**: 约 200 名活跃用户
- **严重级别**: SEV-2

## 事故时间线
| 时间 | 事件 |
|------|------|
| 10:30 | 告警触发：HighThesisFailureRate |
| 10:32 | OnCall 确认告警 |
| 10:35 | 初步定位：DeepSeek API 限流 |
| 10:40 | 启用备用 API Key |
| 10:50 | 错误率下降 |
| 11:15 | 完全恢复 |

## 根因分析
DeepSeek API 配额耗尽，主 API Key 触发限流，备用 Key 未自动切换。

## 影响分析
- 业务影响：约 50 篇论文生成失败
- 用户影响：200 名用户无法使用
- 财务影响：约 $200 退款

## 改进措施
| 行动项 | 负责人 | 截止日期 | 状态 |
|--------|--------|----------|------|
| 实现多 API Key 自动切换 | 张三 | 2026-06-27 | 进行中 |
| 增加 API 配额监控 | 李四 | 2026-06-24 | 完成 |
| 更新 Runbook | 王五 | 2026-06-23 | 完成 |

## 经验教训
1. 单点依赖（单一 API Key）是高风险
2. 配额监控应提前预警，而非触发限流后告警
3. 自动切换机制应作为标配
```

---

## 10. 实施与最佳实践

### 10.1 部署架构

```
+------------------------------------------------------------------+
|                    Kubernetes Cluster                            |
|                                                                  |
|  +-------------------+        +-------------------+              |
|  | thesisminer-app   |        | thesisminer-app   |   ...        |
|  | (FastAPI)         |        | (FastAPI)         |              |
|  | + Envoy sidecar   |        | + Envoy sidecar   |              |
|  +-------------------+        +-------------------+              |
|          |                            |                          |
|          v                            v                          |
|  +---------------------------------------------------+          |
|  |           OTel Collector (DaemonSet)              |          |
|  +---------------------------------------------------+          |
|          |                                                       |
|          +------> Jaeger  +------> Prometheus  +------> Loki     |
|                    |                  |                |         |
|                    v                  v                v         |
|               Elasticsearch      Thanos Store      Elasticsearch |
|                                                                  |
+------------------------------------------------------------------+
                              |
                              v
                    +-------------------+
                    | Grafana           |
                    | (统一可视化)       |
                    +-------------------+
                              |
                              v
                    +-------------------+
                    | Alertmanager      |
                    | + PagerDuty/Slack |
                    +-------------------+
```

### 10.2 容量规划

#### 10.2.1 数据量估算

假设：

- QPS: 100
- 每请求产生日志: 20 条
- 每请求产生 Span: 15 个（采样 10% 后 1.5 个）
- 每请求产生指标: 50 个

日数据量估算：

| 数据类型 | 计算 | 日量 | 月量 |
|----------|------|------|------|
| 日志 | 100 * 20 * 86400 * 1KB | 172 GB | 5 TB |
| 追踪 | 100 * 1.5 * 86400 * 2KB | 25 GB | 750 GB |
| 指标 | 50 * 4（15s 采样）* 86400 * 100B | 1.7 GB | 50 GB |

#### 10.2.2 资源规划

| 组件 | CPU | 内存 | 磁盘 | 副本数 |
|------|-----|------|------|--------|
| Prometheus | 4 核 | 16 GB | 500 GB SSD | 2（HA） |
| Alertmanager | 1 核 | 1 GB | 10 GB | 3（HA） |
| Jaeger | 2 核 | 4 GB | 100 GB | 1 |
| Elasticsearch | 4 核 | 16 GB | 2 TB SSD | 3 |
| Grafana | 1 核 | 2 GB | 10 GB | 2 |
| OTel Collector | 2 核 | 4 GB | 50 GB | 3 |
| Loki | 2 核 | 8 GB | 1 TB | 1 |

### 10.3 性能优化

#### 10.3.1 日志优化

- **异步写入**：使用 `logging.handlers.QueueHandler` 异步写日志
- **批量发送**：Filebeat 批量发送，减少网络开销
- **压缩存储**：Elasticsearch 启用 LZ4 压缩
- **冷热分离**：热数据 SSD，冷数据 HDD

#### 10.3.2 指标优化

- **Recording Rules**：高频查询预计算
- **降采样**：长期数据降采样到 1 分钟粒度
- **Label 控制**：避免高基数 label（如 `user_id`）
- **Histogram Bucket**：合理设置 bucket，避免过多

#### 10.3.3 追踪优化

- **采样**：按比例采样，错误请求全采
- **Span 数量控制**：单 Trace Span 数 < 100
- **属性精简**：避免大对象作为 Span 属性
- **异步导出**：BatchSpanProcessor 异步导出

### 10.4 最佳实践清单

#### 10.4.1 日志最佳实践

- [ ] 所有日志 JSON 结构化
- [ ] 日志包含 `trace_id`、`span_id`、`session_id`
- [ ] 日志级别合理（生产 INFO，调试 DEBUG）
- [ ] 敏感数据脱敏
- [ ] 日志不包含大对象（如完整论文正文）
- [ ] 异常记录 `exc_info=True`
- [ ] 日志有保留策略

#### 10.4.2 指标最佳实践

- [ ] 指标命名遵循 `thesisminer_` 前缀
- [ ] 指标有合理 label（避免高基数）
- [ ] Histogram bucket 合理
- [ ] 高频查询有 Recording Rule
- [ ] 指标有文档说明

#### 10.4.3 追踪最佳实践

- [ ] 关键路径都有 Span
- [ ] Span 包含必要属性
- [ ] 错误 Span 记录 exception
- [ ] 采样策略合理
- [ ] 上下文正确传播

#### 10.4.4 告警最佳实践

- [ ] 每个告警有 Runbook
- [ ] 告警分级合理
- [ ] 抑制规则避免告警风暴
- [ ] 定期审查告警质量
- [ ] 告警准确率 > 95%

#### 10.4.5 SRE 最佳实践

- [ ] 定义清晰的 SLI/SLO
- [ ] 错误预算有告警
- [ ] 事故有 Postmortem
- [ ] Toil < 50%
- [ ] 定期演练

---

## 11. 附录

### 11.1 配置示例

#### 11.1.1 完整 Python 日志配置

```python
# backend/monitoring/config.py
import logging
import logging.config
from pythonjsonlogger import jsonlogger


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "thesisminer.monitoring.logger.ThesisMinerJsonFormatter",
        },
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "level": "INFO",
            "stream": "ext://sys.stdout"
        },
        "error_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "json",
            "level": "ERROR",
            "filename": "/var/log/thesisminer/error.log",
            "maxBytes": 104857600,  # 100MB
            "backupCount": 10
        },
        "audit_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "json",
            "level": "INFO",
            "filename": "/var/log/thesisminer/audit.log",
            "maxBytes": 104857600,
            "backupCount": 30
        }
    },
    "loggers": {
        "thesisminer": {
            "level": "INFO",
            "handlers": ["console", "error_file"],
            "propagate": False
        },
        "thesisminer.audit": {
            "level": "INFO",
            "handlers": ["audit_file"],
            "propagate": False
        },
        "uvicorn": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False
        }
    },
    "root": {
        "level": "WARN",
        "handlers": ["console"]
    }
}


def setup_logging():
    logging.config.dictConfig(LOGGING_CONFIG)
```

#### 11.1.2 OpenTelemetry 完整配置

```python
# backend/monitoring/otel.py
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor


def setup_otel(service_name: str = "thesisminer",
               service_version: str = "8.0.0",
               otlp_endpoint: str = "http://otel-collector:4317"):
    """初始化 OpenTelemetry。"""
    resource = Resource.create({
        "service.name": service_name,
        "service.version": service_version,
        "deployment.environment": "${ENVIRONMENT}",
    })

    # Tracing
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint=otlp_endpoint)
        )
    )
    trace.set_tracer_provider(tracer_provider)

    # Metrics
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=otlp_endpoint),
        export_interval_millis=15000
    )
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[metric_reader]
    )
    metrics.set_meter_provider(meter_provider)

    # 自动埋点
    LoggingInstrumentor().instrument(set_logging_format=True)
    HTTPXClientInstrumentor().instrument()


def instrument_app(app):
    """埋点 FastAPI 应用。"""
    FastAPIInstrumentor.instrument_app(app)
```

### 11.2 常用查询

#### 11.2.1 日志查询（Kibana KQL）

```kql
# 查询某 trace 完整日志
trace_id: "abc123def456"

# 查询某会话所有错误
session_id: "sess-001" AND level: "ERROR"

# 查询五阶段中方法设计阶段的所有日志
stage: "method_design"

# 查询 DeepSeek 超时
event: "ai_timeout"

# 查询缓存未命中
event: "cache_access" AND extra.hit: false

# 查询慢 SQL
event: "sql_execute" AND duration_ms: [100 TO *]
```

#### 11.2.2 指标查询（PromQL）

```promql
# QPS
sum(rate(http_requests_total{service="thesisminer"}[5m]))

# P99 延迟
histogram_quantile(0.99,
  sum(rate(http_request_duration_seconds_bucket{service="thesisminer"}[5m])) by (le)
)

# 错误率
sum(rate(http_requests_total{service="thesisminer", status=~"5.."}[5m]))
/
sum(rate(http_requests_total{service="thesisminer"}[5m]))

# 缓存命中率
sum(rate(thesisminer_cache_hits_total[5m]))
/
(sum(rate(thesisminer_cache_hits_total[5m])) + sum(rate(thesisminer_cache_misses_total[5m])))

# 五阶段完成率
sum(rate(thesisminer_stage_completed_total{status="success"}[1h])) by (stage)
/
sum(rate(thesisminer_stage_started_total[1h])) by (stage)

# DeepSeek Token 成本
sum(rate(thesisminer_ai_cost_usd[1h])) by (agent)
```

#### 11.2.3 追踪查询（Jaeger）

```
# 按服务
service: thesisminer

# 按操作
operation: orchestrator.dispatch

# 按标签
tags: {"thesisminer.stage":"method_design"}

# 按耗时
minDuration: 1s

# 按时间范围
start: 2026-06-20T10:00:00Z
end: 2026-06-20T11:00:00Z
```

### 11.3 故障排查

#### 11.3.1 日志查询不到

**可能原因**：

1. Filebeat 未运行
2. Logstash 过滤错误
3. Elasticsearch 索引未创建
4. 时间范围错误

**排查步骤**：

```bash
# 1. 检查 Filebeat
kubectl logs -n monitoring ds/filebeat

# 2. 检查 Kafka topic
kafka-topics.sh --bootstrap-server kafka:9092 --describe --topic thesisminer-logs

# 3. 检查 Logstash
kubectl logs -n monitoring sts/logstash

# 4. 检查 Elasticsearch 索引
curl -s "elasticsearch:9200/_cat/indices/thesisminer-*?v"
```

#### 11.3.2 指标缺失

**可能原因**：

1. Prometheus 抓取失败
2. 应用 /metrics 端点未暴露
3. 指标命名错误
4. Label 不匹配

**排查步骤**：

```bash
# 1. 检查 Prometheus targets
curl -s "prometheus:9090/api/v1/targets" | jq '.data.activeTargets[] | select(.labels.job=="thesisminer-app")'

# 2. 检查应用 /metrics
curl -s "thesisminer-app:8000/metrics" | grep thesisminer

# 3. 检查 Prometheus 配置
curl -s "prometheus:9090/api/v1/status/config"
```

#### 11.3.3 追踪缺失

**可能原因**：

1. 采样比例过低
2. OTel Collector 故障
3. Jaeger 存储满
4. 上下文未传播

**排查步骤**：

```bash
# 1. 检查 OTel Collector
kubectl logs -n monitoring ds/otel-collector

# 2. 检查 Jaeger
kubectl logs -n monitoring sts/jaeger-collector

# 3. 检查采样配置
kubectl get pod -n thesisminer thesisminer-app-xxx -o yaml | grep -A5 SAMPLING

# 4. 验证上下文传播
# 在请求头添加 X-Debug: true，确保全量采样
curl -H "X-Debug: true" -H "X-Trace-Id: test123" http://thesisminer-app:8000/api/v1/thesis/generate
```

### 11.4 变更记录

| 版本 | 日期 | 变更 | 作者 |
|------|------|------|------|
| v1.0 | 2026-01-15 | 初始版本，定义日志/指标/追踪基础架构 | Architecture Team |
| v2.0 | 2026-03-20 | 增加 OpenTelemetry 集成 | Architecture Team |
| v3.0 | 2026-05-10 | 增加服务网格可观测性 | SRE Team |
| v4.0 | 2026-06-15 | 增加 SRE 方法论、错误预算 | SRE Team |
| v8.0 | 2026-06-20 | 适配 ThesisMiner v8.0 Multi-Agent 架构 | Architecture Team |

---

## 12. 参考资源

### 12.1 官方文档

- [OpenTelemetry](https://opentelemetry.io/docs/)
- [Prometheus](https://prometheus.io/docs/)
- [Grafana](https://grafana.com/docs/)
- [Jaeger](https://www.jaegertracing.io/docs/)
- [Elasticsearch](https://www.elastic.co/guide/)
- [Istio](https://istio.io/latest/docs/)
- [Alertmanager](https://prometheus.io/docs/alerting/latest/alertmanager/)

### 12.2 推荐阅读

- 《Site Reliability Engineering》- Google
- 《The Site Reliability Workbook》- Google
- 《Observability Engineering》- Charity Majors
- 《Distributed Tracing in Practice》- Austin Parker
- 《SRE Workbook》- Google

### 12.3 内部资源

- ThesisMiner v8.0 架构文档：`docs/architecture/system_overview.md`
- ThesisMiner v8.0 部署文档：`docs/architecture/deployment_architecture.md`
- ThesisMiner v8.0 安全设计：`docs/architecture/security_design.md`
- ThesisMiner v8.0 性能设计：`docs/architecture/performance_design.md`
- ThesisMiner v8.0 扩展性设计：`docs/architecture/scalability_design.md`

---

## 13. FAQ

### Q1: 日志、指标、追踪应该优先建设哪个？

**A**: 建议优先级：指标 > 日志 > 追踪。指标用于告警与概览，日志用于排查，追踪用于深度分析。三者缺一不可，但建设顺序按价值与成本权衡。

### Q2: 采样率应该设多少？

**A**: ThesisMiner v8.0 建议常规请求 10%，错误请求 100%，关键业务 100%。具体根据流量与成本调整。

### Q3: 日志保留多久？

**A**: 业务日志 90 天，错误日志 365 天，审计日志 7 年（合规要求）。具体根据合规与成本调整。

### Q4: SLO 应该设多高？

**A**: 不要盲目追求 99.99%。建议从 99% 或 99.9% 开始，根据错误预算消耗情况逐步提高。过高的 SLO 会导致发布冻结。

### Q5: 告警太多怎么办？

**A**: 1) 定期审查告警，删除噪音；2) 调整阈值与 for 时长；3) 增加抑制规则；4) 区分告警级别，低级别静默。

### Q6: 如何衡量可观测性建设效果？

**A**: 关键指标：1) MTTD（平均检测时间）；2) MTTR（平均恢复时间）；3) 告警准确率；4) Postmortem 数量与质量；5) 用户主动报告比例（应 < 30%）。

### Q7: Multi-Agent 架构下如何追踪？

**A**: Orchestrator 创建 root span，分发到 sub-agent 时创建 child span，通过 OpenTelemetry context propagation 传播 trace_id。异步分发需手动 attach/detach context。

### Q8: 三段式 Prompt 缓存如何监控？

**A**: 为每段（system_prompt、session_context、user_query）分别记录 hit/miss Counter，计算命中率 Gauge。命中率低于 50% 触发告警。

### Q9: 多会话上下文隔离如何监控？

**A**: 记录 `context_isolation_violation_total` Counter，任何违规立即告警（P0）。定期审计会话间数据隔离。

### Q10: SQLite WAL 模式如何监控？

**A**: 监控 WAL 文件大小（>1GB 告警）、Checkpoint 频率与耗时、锁竞争次数。WAL 过大会影响读取性能。

---

## 14. 结语

可观测性不是一次性工程，而是持续演进的能力。ThesisMiner v8.0 通过日志、指标、追踪三大支柱，结合告警、仪表盘、SRE 方法论，构建了完整的可观测性体系。随着系统演进，可观测性建设应同步迭代，确保任何异常都能被快速发现、定位、恢复。

**核心要点回顾**：

1. **结构化优先**：日志 JSON、指标带 label、追踪带 attribute
2. **三维关联**：通过 `trace_id` 关联日志、指标、追踪
3. **SRE 驱动**：围绕 SLI/SLO 设计指标与告警
4. **成本可控**：采样、保留策略、降采样
5. **故障优先**：可观测性系统自身故障不能阻塞业务
6. **持续演进**：定期审查、调优、迭代

---

**文档结束**

> 本文档由 ThesisMiner Architecture Team 维护，最后更新于 2026-06-20。
> 如有疑问或建议，请联系 `architecture@thesisminer.io` 或在内部 Wiki 提交 Issue。
