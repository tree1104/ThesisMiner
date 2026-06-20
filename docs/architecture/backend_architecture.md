# ThesisMiner v8.0 后端架构与设计规范

> 本文档详细描述 ThesisMiner v8.0 项目的后端架构、模块设计、数据流、错误处理、性能优化与最佳实践。

## 目录

- [1. 后端概览](#1-后端概览)
- [2. 技术栈](#2-技术栈)
- [3. 目录结构](#3-目录结构)
- [4. 模块体系](#4-模块体系)
- [5. Agent 架构](#5-agent-架构)
- [6. 会话管理](#6-会话管理)
- [7. 约束工程](#7-约束工程)
- [8. 编排系统](#8-编排系统)
- [9. AI 代理层](#9-ai-代理层)
- [10. 数据库设计](#10-数据库设计)
- [11. API 设计](#11-api-设计)
- [12. 错误处理](#12-错误处理)
- [13. 日志系统](#13-日志系统)
- [14. 配置管理](#14-配置管理)
- [15. 缓存策略](#15-缓存策略)
- [16. 安全设计](#16-安全设计)
- [17. 性能优化](#17-性能优化)
- [18. 并发处理](#18-并发处理)
- [19. 异步编程](#19-异步编程)
- [20. 测试策略](#20-测试策略)
- [21. 部署架构](#21-部署架构)
- [22. 监控告警](#22-监控告警)
- [23. 扩展性设计](#23-扩展性设计)
- [24. 代码规范](#24-代码规范)
- [25. 版本管理](#25-版本管理)
- [26. 附录](#26-附录)

---

## 1. 后端概览

### 1.1 设计目标

ThesisMiner v8.0 后端围绕以下目标设计：

1. **多 Agent 协作**：Orchestrator + 5 个子 Agent，独立上下文，协同工作
2. **五阶段闭环**：信息确权→创意→校验→生成→深度辅助，门禁控制
3. **高缓存命中**：DeepSeek 三段式 Prompt，缓存命中率 ≥95%
4. **多对话隔离**：多对话并存，上下文完全隔离
5. **可扩展**：模块化设计，易于新增功能
6. **可观测**：完善的日志、指标、追踪
7. **高性能**：响应时间 < 200ms，吞吐量 ≥1000 QPS

### 1.2 架构总览

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI 应用                          │
├─────────────────────────────────────────────────────────┤
│  路由层 (routes/)                                        │
│  ├── sessions.py    ├── conversations.py                │
│  ├── citations.py   ├── budgets.py                      │
│  └── lineage.py     ├── generate.py                     │
├─────────────────────────────────────────────────────────┤
│  业务层                                                  │
│  ├── agents/         (6 个 Agent)                       │
│  ├── sessions/       (会话/对话管理)                     │
│  ├── constraints/    (约束工程)                          │
│  ├── orchestration/  (编排系统)                          │
│  ├── ai/             (AI 代理层)                         │
│  ├── analytics/      (分析监控)                          │
│  ├── ml/             (机器学习)                          │
│  ├── export/         (导出)                              │
│  ├── knowledge/      (知识库)                            │
│  ├── validation/     (验证)                              │
│  ├── routing/        (路由)                              │
│  ├── integrity/      (学术诚信)                          │
│  ├── optimization/   (优化)                              │
│  ├── nlp/            (NLP)                               │
│  ├── monitoring/     (监控)                              │
│  ├── planning/       (规划)                              │
│  ├── reasoning/      (推理)                              │
│  └── utils/          (工具)                              │
├─────────────────────────────────────────────────────────┤
│  数据层                                                  │
│  ├── database.py     (SQLite + WAL)                     │
│  └── config.py       (配置管理)                          │
└─────────────────────────────────────────────────────────┘
```

---

## 2. 技术栈

### 2.1 核心技术

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.11+ | 编程语言 |
| FastAPI | 0.110+ | Web 框架 |
| Uvicorn | 0.27+ | ASGI 服务器 |
| SQLite | 3.40+ | 数据库 |
| Pydantic | 2.x | 数据验证 |
| httpx | 0.27+ | HTTP 客户端 |
| pytest | 8.x | 测试框架 |

### 2.2 为什么选 FastAPI？

1. **异步原生**：原生支持 async/await，适合 IO 密集型场景
2. **类型安全**：基于 Pydantic，自动类型校验
3. **自动文档**：自动生成 OpenAPI 文档
4. **高性能**：基于 Starlette，性能优异
5. **生态丰富**：中间件、依赖注入、插件丰富

---

## 3. 目录结构

```
backend/
├── __init__.py
├── config.py              # 配置管理
├── database.py            # 数据库
├── agents/                # Agent 模块
│   ├── __init__.py
│   ├── base_agent.py      # Agent 基类
│   ├── agent_registry.py  # Agent 注册表
│   ├── orchestrator.py    # 主管理 Agent
│   ├── reasoner.py        # 创意 Agent
│   ├── critic.py          # 评审 Agent
│   ├── mentor_agent.py    # 导师 Agent
│   ├── proposal_writer.py # 写作 Agent
│   ├── searcher_wrapper.py# 检索 Agent
│   ├── agent_context.py   # 上下文管理
│   └── agent_communicator.py # Agent 通信
├── sessions/              # 会话模块
│   ├── __init__.py
│   ├── conversation_manager.py
│   ├── session_manager.py
│   └── context_manager.py
├── constraints/           # 约束工程
│   ├── __init__.py
│   ├── stage_gate.py
│   ├── hard_rules.py
│   ├── novelty_checker.py
│   ├── style_normalizer.py
│   ├── multi_granularity.py
│   ├── deep_assist.py
│   ├── info_confirmation.py
│   ├── rule_engine.py
│   ├── plagiarism_checker.py
│   └── academic_standards.py
├── orchestration/         # 编排系统
│   ├── __init__.py
│   ├── state_machine.py
│   ├── pipeline.py
│   └── scheduler.py
├── ai/                    # AI 代理层
│   ├── __init__.py
│   ├── ai_proxy.py
│   ├── prompts.py
│   ├── prompt_cache.py
│   ├── cache_monitor.py
│   ├── citation_parser.py
│   ├── response_parser.py
│   └── streaming.py
├── analytics/             # 分析监控
│   ├── __init__.py
│   ├── metrics_collector.py
│   ├── performance_monitor.py
│   └── usage_tracker.py
├── ml/                    # 机器学习
│   ├── __init__.py
│   ├── text_processor.py
│   ├── embedding_engine.py
│   └── similarity_scorer.py
├── export/                # 导出
│   ├── __init__.py
│   ├── document_exporter.py
│   ├── report_generator.py
│   └── citation_formatter.py
├── knowledge/             # 知识库
│   ├── __init__.py
│   ├── knowledge_base.py
│   ├── discipline_taxonomy.py
│   └── method_library.py
├── validation/            # 验证
│   ├── __init__.py
│   ├── thesis_validator.py
│   ├── plagiarism_detector.py
│   └── quality_assessor.py
├── routing/               # 路由
│   ├── __init__.py
│   └── model_router.py
├── integrity/             # 学术诚信
│   ├── __init__.py
│   ├── academic_integrity.py
│   ├── citation_verifier.py
│   └── data_authenticator.py
├── optimization/          # 优化
│   ├── __init__.py
│   ├── cache_optimizer.py
│   ├── query_optimizer.py
│   └── resource_manager.py
├── nlp/                   # NLP
│   ├── __init__.py
│   ├── chinese_processor.py
│   ├── academic_parser.py
│   └── terminology_extractor.py
├── monitoring/            # 监控
│   ├── __init__.py
│   ├── health_checker.py
│   ├── alert_manager.py
│   └── audit_logger.py
├── planning/              # 规划
│   ├── __init__.py
│   ├── research_planner.py
│   ├── timeline_generator.py
│   └── milestone_tracker.py
├── reasoning/             # 推理
│   ├── __init__.py
│   ├── logical_reasoner.py
│   ├── argument_analyzer.py
│   └── hypothesis_tester.py
└── utils/                 # 工具
    ├── __init__.py
    ├── logger.py
    ├── validators.py
    ├── helpers.py
    ├── cache.py
    └── security.py
```

---

## 4. 模块体系

### 4.1 模块设计原则

1. **单一职责**：每个模块只做一件事
2. **高内聚低耦合**：模块内高内聚，模块间低耦合
3. **依赖倒置**：依赖抽象，不依赖具体
4. **开闭原则**：对扩展开放，对修改关闭
5. **接口隔离**：小接口优于大接口

### 4.2 模块依赖关系

```
agents/ ──→ ai/ ──→ utils/
  │           │
  ├──→ constraints/
  ├──→ sessions/
  ├──→ orchestration/
  └──→ routing/

orchestration/ ──→ agents/
              ──→ constraints/

sessions/ ──→ database/
          ──→ utils/

ai/ ──→ database/
    ──→ utils/
    ──→ routing/
```

---

## 5. Agent 架构

### 5.1 Agent 基类

```python
# backend/agents/base_agent.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

@dataclass
class AgentResult:
    """Agent 执行结果"""
    success: bool
    content: str = ""
    reasoning: str = ""
    data: dict = field(default_factory=dict)
    error: Optional[str] = None
    token_usage: dict = field(default_factory=dict)

class BaseAgent(ABC):
    """Agent 抽象基类"""
    
    def __init__(self, agent_id: str, model_id: str, system_prompt: str):
        self.agent_id = agent_id
        self.model_id = model_id
        self.system_prompt = system_prompt
        self.context = AgentContext()
    
    @abstractmethod
    async def run(self, task_input: dict) -> AgentResult:
        """执行任务"""
        pass
    
    def reset_context(self):
        """重置上下文"""
        self.context.clear()
```

### 5.2 Agent 注册表

```python
# backend/agents/agent_registry.py
from typing import Dict, Type
from backend.agents.base_agent import BaseAgent

AGENT_REGISTRY: Dict[str, Type[BaseAgent]] = {}

def register_agent(agent_id: str):
    """Agent 注册装饰器"""
    def decorator(cls: Type[BaseAgent]):
        AGENT_REGISTRY[agent_id] = cls
        return cls
    return decorator

def get_agent(agent_id: str) -> BaseAgent:
    """获取 Agent 实例"""
    cls = AGENT_REGISTRY.get(agent_id)
    if not cls:
        raise ValueError(f"Agent not found: {agent_id}")
    return cls()

def list_agents() -> list:
    """列出所有 Agent"""
    return [
        {"id": aid, "name": cls.__name__}
        for aid, cls in AGENT_REGISTRY.items()
    ]
```

### 5.3 Orchestrator 主管理 Agent

```python
# backend/agents/orchestrator.py
@register_agent("orchestrator")
class OrchestratorAgent(BaseAgent):
    """主管理 Agent"""
    
    def __init__(self):
        super().__init__(
            agent_id="orchestrator",
            model_id="claude-sonnet-4.5",
            system_prompt="你是 ThesisMiner 的主管理 Agent..."
        )
        self.stage = Stage.INFO_CONFIRM
        self.sub_agents = {
            "searcher": get_agent("searcher"),
            "reasoner": get_agent("reasoner"),
            "critic": get_agent("critic"),
            "mentor": get_agent("mentor"),
            "writer": get_agent("writer")
        }
    
    async def orchestrate(self, user_input: str, conversation_id: str):
        """编排五阶段流程"""
        # 阶段1：信息确权
        yield await self._run_info_confirm(user_input)
        
        # 阶段2：创意
        yield await self._run_creativity()
        
        # 阶段3：校验
        yield await self._run_validation()
        
        # 阶段4：生成
        yield await self._run_generation()
        
        # 阶段5：深度辅助
        yield await self._run_deep_assist()
```

---

## 6. 会话管理

### 6.1 数据模型

```
Session (会话)
├── id: str
├── title: str
├── discipline: str
├── advisor: str
├── created_at: datetime
├── active_conversation_id: str
└── conversations: List[Conversation]

Conversation (对话)
├── id: str
├── session_id: str
├── title: str
├── agent_id: str
├── status: str
├── created_at: datetime
└── messages: List[Message]

Message (消息)
├── id: str
├── conversation_id: str
├── agent_id: str
├── role: str (user/assistant/system)
├── content: str
├── reasoning: str
├── token_usage: dict
├── created_at: datetime
└── citations: List[Citation]
```

### 6.2 上下文隔离

```python
class ConversationManager:
    def get_context_window(self, conversation_id: str, max_tokens: int) -> list:
        """获取对话上下文窗口（DST 压缩）"""
        messages = self.get_messages(conversation_id)
        
        # 按时间倒序，从最新消息开始
        messages.reverse()
        
        context = []
        total_tokens = 0
        
        for msg in messages:
            msg_tokens = self._count_tokens(msg.content)
            if total_tokens + msg_tokens > max_tokens:
                # 压缩旧消息
                compressed = self._compress_message(msg)
                context.append(compressed)
                break
            
            context.append(msg)
            total_tokens += msg_tokens
        
        context.reverse()
        return context
```

---

## 7. 约束工程

### 7.1 五阶段门禁

```python
class StageGate:
    """阶段门禁"""
    
    def check_enter(self, stage: Stage, context: dict) -> GateResult:
        """检查是否可进入阶段"""
        rules = STAGE_GATES[stage]
        for rule in rules:
            if not rule.check(context):
                return GateResult(passed=False, reason=rule.reason)
        return GateResult(passed=True)
    
    def check_exit(self, stage: Stage, context: dict) -> GateResult:
        """检查是否可退出阶段"""
        rules = STAGE_EXIT_GATES[stage]
        for rule in rules:
            if not rule.check(context):
                return GateResult(passed=False, reason=rule.reason)
        return GateResult(passed=True)
```

### 7.2 新颖性评分

```python
class NoveltyChecker:
    """新颖性评估器"""
    
    WEIGHTS = {
        "cross_discipline": 0.30,
        "method_transfer": 0.25,
        "pain_point": 0.25,
        "trend_foresight": 0.20
    }
    
    def assess(self, topic: str, context: dict) -> dict:
        scores = {
            "cross_discipline": self.score_cross_discipline(topic, context),
            "method_transfer": self.score_method_transfer(topic, context),
            "pain_point": self.score_pain_point(topic, context),
            "trend_foresight": self.score_trend_foresight(topic, context)
        }
        
        total = sum(scores[k] * self.WEIGHTS[k] for k in scores)
        return {"total": total, "dimensions": scores}
```

---

## 8. 编排系统

### 8.1 状态机

```python
class Stage(Enum):
    INFO_CONFIRM = "info_confirm"
    CREATIVITY = "creativity"
    VALIDATION = "validation"
    GENERATION = "generation"
    DEEP_ASSIST = "deep_assist"

class Event(Enum):
    USER_CONFIRMED = "user_confirmed"
    CANDIDATES_GENERATED = "candidates_generated"
    SCORE_PASSED = "score_passed"
    SCORE_FAILED = "score_failed"
    GENERATION_COMPLETED = "generation_completed"

TRANSITIONS = {
    (Stage.INFO_CONFIRM, Event.USER_CONFIRMED): Stage.CREATIVITY,
    (Stage.CREATIVITY, Event.CANDIDATES_GENERATED): Stage.VALIDATION,
    (Stage.VALIDATION, Event.SCORE_PASSED): Stage.GENERATION,
    (Stage.VALIDATION, Event.SCORE_FAILED): Stage.CREATIVITY,
    (Stage.GENERATION, Event.GENERATION_COMPLETED): Stage.DEEP_ASSIST,
}

def transition(current: Stage, event: Event) -> Stage:
    key = (current, event)
    if key not in TRANSITIONS:
        raise InvalidTransitionError(f"非法转移: {current} + {event}")
    return TRANSITIONS[key]
```

---

## 9. AI 代理层

### 9.1 三段式 Prompt 缓存

```python
class PromptCache:
    """三段式 Prompt 缓存"""
    
    def build_cached_prefix(self, system_role: str, hard_constraints: str, 
                           degree_discipline_advisor: str) -> str:
        """构建缓存前缀（字节级一致）"""
        return f"{system_role}\n{hard_constraints}\n{degree_discipline_advisor}"
    
    def build_prompt_with_cache(self, prefix: str, dynamic: str) -> list:
        """构建带缓存的 Prompt"""
        return [
            {"role": "system", "content": prefix},
            {"role": "user", "content": dynamic}
        ]
```

### 9.2 LLM 调用

```python
async def call_llm(model_id: str, messages: list, cached_prefix: str = None) -> dict:
    """调用 LLM"""
    # DeepSeek 模型使用缓存前缀
    if is_deepseek_model(model_id) and cached_prefix:
        # 确保 prefix 字节级一致
        messages = [
            {"role": "system", "content": cached_prefix},
            *messages
        ]
    
    response = await httpx_client.post(
        f"{API_BASE}/{model_id}/chat",
        json={"messages": messages}
    )
    
    # 记录缓存命中
    if is_deepseek_model(model_id):
        cache_monitor.record_cache_hit(
            model=model_id,
            cached_tokens=response.json().get("cached_tokens", 0),
            prompt_tokens=response.json().get("prompt_tokens", 0)
        )
    
    return response.json()
```

---

## 10. 数据库设计

### 10.1 SQLite 配置

```python
# backend/database.py
import sqlite3

DB_PATH = "data/thesisminer.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn
```

### 10.2 表结构

```sql
-- 会话表
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    discipline TEXT,
    advisor TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT,
    active_conversation_id TEXT
);

-- 对话表
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    title TEXT NOT NULL,
    agent_id TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

-- 消息表
CREATE TABLE conversation_messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    agent_id TEXT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    reasoning TEXT,
    search_results_json TEXT,
    token_usage_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

-- 引用表
CREATE TABLE search_citations (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    snippet TEXT,
    source_domain TEXT,
    favicon TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (message_id) REFERENCES conversation_messages(id) ON DELETE CASCADE
);
```

---

## 11. API 设计

### 11.1 RESTful 端点

```python
# 会话管理
POST   /api/sessions                          # 创建会话
GET    /api/sessions                          # 列出会话
GET    /api/sessions/{sid}                    # 获取会话
PUT    /api/sessions/{sid}                    # 更新会话
DELETE /api/sessions/{sid}                    # 删除会话

# 对话管理
POST   /api/sessions/{sid}/conversations      # 创建对话
GET    /api/sessions/{sid}/conversations      # 列出对话
GET    /api/conversations/{cid}               # 获取对话
PUT    /api/conversations/{cid}               # 更新对话
DELETE /api/conversations/{cid}               # 删除对话

# 消息管理
POST   /api/conversations/{cid}/messages      # 发送消息
GET    /api/conversations/{cid}/messages      # 列出消息
GET    /api/messages/{mid}/citations          # 获取引用

# Agent
GET    /api/agents                            # 列出 Agent

# 缓存
GET    /api/cache-stats                       # 缓存统计
```

### 11.2 SSE 流式响应

```python
from fastapi.responses import StreamingResponse

@app.post("/api/conversations/{cid}/messages/stream")
async def stream_message(cid: str, data: dict):
    async def event_stream():
        async for chunk in orchestrator.orchestrate(data["content"], cid):
            yield f"data: {json.dumps(chunk)}\n\n"
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

---

## 12. 错误处理

### 12.1 异常层次

```python
class ThesisMinerError(Exception):
    """基础异常"""
    pass

class ValidationError(ThesisMinerError):
    """验证错误"""
    pass

class NotFoundError(ThesisMinerError):
    """未找到"""
    pass

class AuthenticationError(ThesisMinerError):
    """认证错误"""
    pass

class RateLimitError(ThesisMinerError):
    """限流"""
    pass

class LLMError(ThesisMinerError):
    """LLM 调用错误"""
    pass
```

### 12.2 全局异常处理

```python
@app.exception_handler(ThesisMinerError)
async def thesisminer_error_handler(request, exc):
    status_map = {
        ValidationError: 400,
        NotFoundError: 404,
        AuthenticationError: 401,
        RateLimitError: 429,
        LLMError: 502
    }
    status = status_map.get(type(exc), 500)
    return JSONResponse(
        status_code=status,
        content={"error": str(exc), "type": type(exc).__name__}
    )
```

---

## 13. 日志系统

### 13.1 结构化日志

```python
import logging
import json

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data, ensure_ascii=False)

logger = logging.getLogger("thesisminer")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger.addHandler(handler)
```

---

## 14. 配置管理

### 14.1 配置层次

1. **环境变量**：最高优先级
2. **config.json**：用户配置
3. **默认值**：代码内置

```python
class Config:
    def __init__(self):
        self._settings = self._load()
    
    def _load(self):
        settings = DEFAULT_SETTINGS.copy()
        
        # 加载 config.json
        config_path = Path("data/config.json")
        if config_path.exists():
            with config_path.open() as f:
                user_config = json.load(f)
            settings.update(user_config)
        
        # 环境变量覆盖
        for key in settings:
            env_value = os.environ.get(key.upper())
            if env_value is not None:
                settings[key] = self._cast(env_value, type(settings[key]))
        
        return settings
```

---

## 15. 缓存策略

### 15.1 多级缓存

```python
class CacheOptimizer:
    """多级缓存"""
    
    def __init__(self):
        self.memory_cache = LRUCache(max_size=1000)
        self.disk_cache = DiskCache(path="data/cache")
    
    async def get(self, key: str):
        # L1: 内存
        value = self.memory_cache.get(key)
        if value is not None:
            return value
        
        # L2: 磁盘
        value = await self.disk_cache.get(key)
        if value is not None:
            self.memory_cache.set(key, value)
            return value
        
        return None
    
    async def set(self, key: str, value, ttl: int = 3600):
        self.memory_cache.set(key, value, ttl)
        await self.disk_cache.set(key, value, ttl)
```

---

## 16. 安全设计

### 16.1 API 密钥管理

```python
import os
from pathlib import Path

class SecretManager:
    def __init__(self):
        self._secrets = {}
        self._load()
    
    def _load(self):
        # 从环境变量加载
        for key in ["OPENAI_API_KEY", "DEEPSEEK_API_KEY", "ANTHROPIC_API_KEY"]:
            value = os.environ.get(key)
            if value:
                self._secrets[key] = value
        
        # 从 .env 文件加载
        env_path = Path(".env")
        if env_path.exists():
            with env_path.open() as f:
                for line in f:
                    if "=" in line and not line.startswith("#"):
                        k, v = line.strip().split("=", 1)
                        self._secrets[k] = v
    
    def get(self, key: str) -> str:
        return self._secrets.get(key)
```

---

## 17. 性能优化

### 17.1 数据库优化

```python
# 批量插入
def batch_insert_messages(messages: list):
    conn = get_db_connection()
    conn.executemany(
        "INSERT INTO conversation_messages VALUES (?,?,?,?,?,?,?,?)",
        [msg.to_tuple() for msg in messages]
    )
    conn.commit()

# 索引优化
CREATE INDEX idx_messages_conversation ON conversation_messages(conversation_id, created_at);
CREATE INDEX idx_citations_message ON search_citations(message_id);
```

### 17.2 连接池

```python
import threading
from queue import Queue

class ConnectionPool:
    def __init__(self, max_connections=10):
        self.pool = Queue(max_connections)
        for _ in range(max_connections):
            self.pool.put(self._create_connection())
    
    def get(self):
        return self.pool.get()
    
    def put(self, conn):
        self.pool.put(conn)
```

---

## 18. 并发处理

### 18.1 异步锁

```python
import asyncio

class AsyncLock:
    def __init__(self):
        self._lock = asyncio.Lock()
    
    async def __aenter__(self):
        await self._lock.acquire()
        return self
    
    async def __aexit__(self, *args):
        self._lock.release()
```

---

## 19. 异步编程

### 19.1 异步模式

```python
# 并发执行多个 Agent
async def run_agents_parallel(agents: list, input_data: dict):
    tasks = [agent.run(input_data) for agent in agents]
    results = await asyncio.gather(*tasks)
    return results

# 超时控制
async def call_with_timeout(coro, timeout=30):
    try:
        return await asyncio.wait_for(coro, timeout)
    except asyncio.TimeoutError:
        raise LLMError("LLM 调用超时")
```

---

## 20. 测试策略

### 20.1 测试金字塔

```
单元测试 (75%) → 集成测试 (20%) → E2E测试 (5%)
```

### 20.2 测试覆盖率目标

| 模块 | 行覆盖率 | 分支覆盖率 |
|------|---------|----------|
| agents | ≥90% | ≥85% |
| sessions | ≥95% | ≥90% |
| constraints | ≥95% | ≥90% |
| ai | ≥85% | ≥80% |
| 总体 | ≥85% | ≥80% |

---

## 21. 部署架构

### 21.1 开发环境

```bash
# 启动开发服务器
python main.py --reload

# 运行测试
pytest
```

### 21.2 生产环境

```bash
# 使用 uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## 22. 监控告警

### 22.1 健康检查

```python
@app.get("/api/health")
async def health_check():
    checks = {
        "database": await check_database(),
        "disk": check_disk_space(),
        "memory": check_memory()
    }
    all_healthy = all(checks.values())
    return {
        "status": "healthy" if all_healthy else "unhealthy",
        "checks": checks
    }
```

---

## 23. 扩展性设计

### 23.1 插件机制

```python
class PluginManager:
    def __init__(self):
        self._plugins = {}
    
    def register(self, name: str, plugin):
        self._plugins[name] = plugin
    
    def get(self, name: str):
        return self._plugins.get(name)
```

---

## 24. 代码规范

### 24.1 Python 规范

- 遵循 PEP 8
- 使用类型注解
- 4 空格缩进
- 行宽 100 字符
- 中文注释

---

## 25. 版本管理

### 25.1 语义化版本

```
MAJOR.MINOR.PATCH
8.0.0
```

---

## 26. 附录

### 26.1 开发命令速查

```bash
# 安装依赖
pip install -r requirements.txt

# 启动开发服务器
python main.py

# 运行测试
pytest

# 运行特定测试
pytest tests/unit/test_orchestrator.py

# 生成覆盖率报告
pytest --cov=backend --cov-report=html

# 类型检查
mypy backend/

# 代码格式化
black backend/
isort backend/
```

---

## 结语

ThesisMiner v8.0 后端采用模块化、异步化、可扩展的架构设计，通过多 Agent 协作、五阶段闭环、三段式缓存等核心机制，实现了高性能、高可用的论题挖掘系统。完善的测试体系、监控告警、文档体系确保了系统的可维护性与可演进性。
