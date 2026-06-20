# ThesisMiner v8.0 Agent 参考文档

> **版本**：v8.0.0
> **最后更新**：2026-06-20
> **适用范围**：`backend/agents/`、`backend/orchestration/`、`backend/ai/`
> **文档状态**：正式发布（Stable）

---

## 目录

- [1. 文档概述](#1-文档概述)
- [2. Agent 架构总览](#2-agent-架构总览)
- [3. BaseAgent 基类参考](#3-baseagent-基类参考)
- [4. Orchestrator 主管理 Agent](#4-orchestrator-主管理-agent)
- [5. Searcher 文献检索 Agent](#5-searcher-文献检索-agent)
- [6. Reasoner 四维创意引擎 Agent](#6-reasoner-四维创意引擎-agent)
- [7. Critic 候选评估 Agent](#7-critic-候选评估-agent)
- [8. Mentor 导师视角 Agent](#8-mentor-导师视角-agent)
- [9. Writer 多粒度生成 Agent](#9-writer-多粒度生成-agent)
- [10. Agent 间通信协议](#10-agent-间通信协议)
- [11. Agent 协作模式](#11-agent-协作模式)
- [12. 冲突解决机制](#12-冲突解决机制)
- [13. Agent 扩展开发指南](#13-agent-扩展开发指南)
- [14. 自定义 Agent 开发](#14-自定义-agent-开发)
- [15. Agent 性能指标](#15-agent-性能指标)
- [16. Agent 错误处理](#16-agent-错误处理)
- [17. Agent 配置参考](#17-agent-配置参考)
- [18. 附录](#18-附录)

---

## 1. 文档概述

### 1.1 文档目的

本文档是 ThesisMiner v8.0 多 Agent 架构的完整参考手册，面向以下读者：

- **后端开发者**：需要扩展或修改 Agent 行为的开发人员
- **架构师**：需要理解多 Agent 协作机制的系统设计人员
- **运维工程师**：需要排查 Agent 相关故障的运维人员
- **研究者**：希望了解多 Agent 系统设计的学术研究人员
- **二次开发者**：基于 ThesisMiner 进行二次开发的工程师

### 1.2 文档范围

本文档涵盖 ThesisMiner v8.0 中所有 6 个 Agent 的完整参考：

| Agent ID | 名称 | 职责 | 默认模型 |
|----------|------|------|----------|
| `orchestrator` | Orchestrator 主管理 Agent | 五阶段闭环调度、上下文管理、阶段门控 | claude-sonnet-4.5 |
| `searcher` | Searcher 文献检索 Agent | arXiv/Semantic Scholar 检索、新颖性检查 | deepseek-v3.2 |
| `reasoner` | Reasoner 四维创意引擎 Agent | 跨学科/方法迁移/痛点突破/趋势预测 | deepseek-r2 |
| `critic` | Critic 候选评估 Agent | 本地新颖性 + LLM 评估、阈值门控 | deepseek-r2 |
| `mentor` | Mentor 导师视角 Agent | 导师视角评审、批量评审、兜底评审 | gpt-4.1 |
| `writer` | Writer 多粒度生成 Agent | title/abstract/outline/full 四粒度生成 | claude-opus-4.5 |

### 1.3 设计理念

ThesisMiner v8.0 的 Agent 系统遵循 Claude Code 的"主管理 + 子 Agent"模式：

```
┌─────────────────────────────────────────────────────────────────┐
│                     用户会话 (Session)                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              Orchestrator (主管理 Agent)                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  - 五阶段状态机调度                                      │   │
│  │  - 阶段门控 (Stage Gate)                                 │   │
│  │  - 上下文压缩与路由                                      │   │
│  │  - 重试与兜底降级                                        │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
        │           │           │           │           │
        ▼           ▼           ▼           ▼           ▼
   ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
   │Searcher│ │Reasoner│ │ Critic │ │ Mentor │ │ Writer │
   └────────┘ └────────┘ └────────┘ └────────┘ └────────┘
```

### 1.4 术语表

| 术语 | 英文 | 含义 |
|------|------|------|
| 主管理 Agent | Orchestrator | 负责调度其他子 Agent 的核心 Agent |
| 子 Agent | Sub-Agent | 由 Orchestrator 调度的具体执行 Agent |
| 阶段门控 | Stage Gate | 控制阶段流转的验证机制 |
| Agent 结果 | AgentResult | Agent 执行后返回的标准化数据结构 |
| 上下文 | Context | Agent 维护的对话历史与状态 |
| 模型路由 | Model Routing | 根据用途选择 LLM 模型的机制 |
| 兜底降级 | Fallback | Agent 失败时的备用方案 |
| 阶段缓存 | Stage Cache | 已完成阶段结果的缓存机制 |

---

## 2. Agent 架构总览

### 2.1 架构层次

ThesisMiner v8.0 的 Agent 架构分为四个层次：

```
┌─────────────────────────────────────────────────────────────────┐
│ L4: 接入层 (API Layer)                                          │
│   FastAPI Routes → Orchestrator.orchestrate()                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ L3: 编排层 (Orchestration Layer)                                │
│   OrchestratorAgent + StageGate + RetryPolicy                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ L2: Agent 层 (Agent Layer)                                      │
│   BaseAgent ← Searcher/Reasoner/Critic/Mentor/Writer            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ L1: 基础设施层 (Infrastructure Layer)                           │
│   AI Proxy + Prompt Cache + SQLite + Search APIs                │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Agent 注册表

所有 Agent 通过 `agent_registry.py` 中的全局注册表管理：

```python
# backend/agents/agent_registry.py
from typing import Dict, Optional, Type
from backend.agents.base_agent import BaseAgent

AGENT_REGISTRY: Dict[str, Type[BaseAgent]] = {}
_AGENT_INSTANCES: Dict[str, BaseAgent] = {}

def register_agent(agent_id: str, agent_class: Type[BaseAgent]) -> None:
    """注册 Agent 类到全局注册表"""
    AGENT_REGISTRY[agent_id] = agent_class

def get_agent(agent_id: str) -> BaseAgent:
    """获取 Agent 单例（首次调用时实例化）"""
    if agent_id not in _AGENT_INSTANCES:
        if agent_id not in AGENT_REGISTRY:
            raise KeyError(f"Agent '{agent_id}' not registered")
        _AGENT_INSTANCES[agent_id] = AGENT_REGISTRY[agent_id]()
    return _AGENT_INSTANCES[agent_id]

def list_agents() -> list:
    """列出所有已注册的 Agent"""
    return list(AGENT_REGISTRY.keys())

def reset_all_contexts() -> None:
    """重置所有 Agent 的上下文（用于新会话）"""
    for agent in _AGENT_INSTANCES.values():
        agent.reset_context()
```

### 2.3 Agent 生命周期

```
[注册阶段]
    │
    ▼
register_agent("searcher", SearcherAgent)
    │
    ▼
[首次调用]
    │
    ▼
get_agent("searcher") → 实例化 SearcherAgent()
    │
    ▼
[会话内复用]
    │
    ▼
agent.run(input) → agent.run(input) → ...
    │
    ▼
[会话结束]
    │
    ▼
reset_all_contexts() → 清空 messages，保留实例
    │
    ▼
[下次会话]
    │
    ▼
get_agent("searcher") → 复用实例（上下文已清空）
```

### 2.4 五阶段闭环流程

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  info_confirm │────▶│  creativity  │────▶│  validation  │
│  (信息确认)   │     │  (创意生成)   │     │  (验证评估)   │
└──────────────┘     └──────────────┘     └──────────────┘
                                                  │
                                                  ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ deep_assist  │◀────│  generation  │◀────│  Gate:       │
│ (深度辅助)    │     │  (报告生成)   │     │  score≥60    │
└──────────────┘     └──────────────┘     └──────────────┘
```

| 阶段 | 调用 Agent | 门控条件 | 失败处理 |
|------|-----------|----------|----------|
| info_confirm | Orchestrator | 用户确认信息完整 | 追问补充 |
| creativity | Reasoner + Searcher | 生成 ≥3 个候选 | 重试或兜底 |
| validation | Critic + Searcher | score ≥ 60 | 重试或降级 |
| generation | Writer + Mentor | 报告生成成功 | 模板兜底 |
| deep_assist | Orchestrator | 用户主动结束 | 循环追问 |

---

## 3. BaseAgent 基类参考

### 3.1 类定义

`BaseAgent` 是所有 Agent 的抽象基类，定义了统一的接口和行为：

```python
# backend/agents/base_agent.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncGenerator, Optional

@dataclass
class AgentResult:
    """Agent 执行结果的标准数据结构"""
    agent_id: str                    # Agent 标识
    success: bool                    # 是否成功
    content: str = ""                # 主要输出内容
    reasoning: str = ""              # 推理过程（thinking）
    data: dict = field(default_factory=dict)  # 结构化数据
    citations: list = field(default_factory=list)  # 引用列表
    token_usage: dict = field(default_factory=dict)  # token 消耗
    error: str = ""                  # 错误信息

class BaseAgent(ABC):
    """所有 Agent 的抽象基类"""
    
    agent_id: str = "base"
    default_model: str = "gpt-4.1-mini"
    default_temperature: float = 0.3
    default_max_tokens: int = 2048
    
    def __init__(self):
        self.messages: list = []  # 独立的上下文
        self.model_config = self._load_model_config()
    
    @abstractmethod
    async def run(self, input_data: dict) -> AgentResult:
        """执行 Agent 核心逻辑（子类必须实现）"""
        pass
    
    def reset_context(self) -> None:
        """重置上下文（保留 system prompt）"""
        if self.messages and self.messages[0].get("role") == "system":
            self.messages = [self.messages[0]]
        else:
            self.messages = []
    
    def get_model(self, purpose: str = "default") -> str:
        """获取模型（模型路由）"""
        from backend.config import get_step_model
        return get_step_model(self.agent_id, purpose)
```

### 3.2 AgentResult 字段详解

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `agent_id` | str | 是 | Agent 标识，如 `"searcher"` |
| `success` | bool | 是 | 执行是否成功 |
| `content` | str | 否 | 主要输出文本（如生成的报告） |
| `reasoning` | str | 否 | 推理过程（thinking 模式输出） |
| `data` | dict | 否 | 结构化数据（如候选列表、评分） |
| `citations` | list | 否 | 引用文献列表 |
| `token_usage` | dict | 否 | token 消耗统计 |
| `error` | str | 否 | 错误信息（success=False 时填写） |

### 3.3 token_usage 字段结构

```python
token_usage = {
    "prompt_tokens": 1250,      # 输入 token
    "completion_tokens": 800,   # 输出 token
    "total_tokens": 2050,        # 总 token
    "cache_hit_tokens": 1180,   # 缓存命中 token
    "cache_miss_tokens": 70,    # 缓存未命中 token
    "cost_usd": 0.0035,         # 预估成本（美元）
    "model": "deepseek-v3.2",   # 使用的模型
    "duration_ms": 2300         # 耗时（毫秒）
}
```

### 3.4 上下文管理

每个 Agent 维护独立的 `messages` 列表，遵循以下规则：

```python
# 初始状态
agent.messages = []

# 首次调用 run() 后
agent.messages = [
    {"role": "system", "content": "你是 Searcher Agent..."},
    {"role": "user", "content": "检索关于 LLM 的论文"},
    {"role": "assistant", "content": "找到 10 篇相关论文..."}
]

# 第二次调用（保留历史）
agent.messages = [
    {"role": "system", "content": "你是 Searcher Agent..."},
    {"role": "user", "content": "检索关于 LLM 的论文"},
    {"role": "assistant", "content": "找到 10 篇相关论文..."},
    {"role": "user", "content": "再检索关于 RAG 的论文"},
    {"role": "assistant", "content": "找到 8 篇相关论文..."}
]

# reset_context() 后（仅保留 system）
agent.messages = [
    {"role": "system", "content": "你是 Searcher Agent..."}
]
```

### 3.5 模型路由机制

Agent 通过 `get_model()` 方法获取模型，路由优先级：

```
1. 显式指定的 model 参数（最高优先级）
       │
       ▼
2. step_models[purpose] 配置（如 step_models["search"]）
       │
       ▼
3. models[0].id（配置文件中的第一个模型）
       │
       ▼
4. ai_model（环境变量 AI_MODEL，最低优先级）
```

```python
# backend/config.py
def get_step_model(agent_id: str, purpose: str) -> str:
    """获取指定 Agent 指定用途的模型"""
    settings = get_settings()
    
    # 优先级 1: step_models 配置
    step_models = settings.step_models or {}
    agent_step = step_models.get(agent_id, {})
    if purpose in agent_step:
        return agent_step[purpose]
    
    # 优先级 2: models[0].id
    if settings.models:
        return settings.models[0].id
    
    # 优先级 3: ai_model 环境变量
    return settings.ai_model or "gpt-4.1-mini"
```

### 3.6 错误处理模式

BaseAgent 推荐的错误处理模式：

```python
async def run(self, input_data: dict) -> AgentResult:
    try:
        # 1. 输入校验
        if not input_data.get("query"):
            return AgentResult(
                agent_id=self.agent_id,
                success=False,
                error="缺少必需参数: query"
            )
        
        # 2. 调用 LLM
        response = await call_llm(
            model=self.get_model(),
            messages=self.messages,
            temperature=self.default_temperature
        )
        
        # 3. 解析结果
        result = self._parse_response(response)
        
        # 4. 返回成功结果
        return AgentResult(
            agent_id=self.agent_id,
            success=True,
            content=result.content,
            data=result.data,
            token_usage=response.token_usage
        )
        
    except TimeoutError as e:
        return AgentResult(
            agent_id=self.agent_id,
            success=False,
            error=f"Agent 超时: {e}"
        )
    except Exception as e:
        return AgentResult(
            agent_id=self.agent_id,
            success=False,
            error=f"Agent 异常: {e}"
        )
```

---

## 4. Orchestrator 主管理 Agent

### 4.1 类定义与职责

`OrchestratorAgent` 是整个系统的核心调度 Agent，负责：

- 五阶段闭环状态机调度
- 阶段门控（Stage Gate）验证
- 上下文压缩与路由
- 重试与兜底降级
- 阶段结果缓存

```python
# backend/agents/orchestrator.py
from typing import AsyncGenerator
from backend.agents.base_agent import BaseAgent, AgentResult

STAGES = ["info_confirm", "creativity", "validation", "generation", "deep_assist"]

class OrchestratorAgent(BaseAgent):
    agent_id = "orchestrator"
    default_model = "claude-sonnet-4.5"
    default_temperature = 0.3
    default_max_tokens = 4096
    
    def __init__(self):
        super().__init__()
        self.current_stage: str = "info_confirm"
        self.stage_results: dict = {}  # 阶段结果缓存
        self.session_context: dict = {}  # 会话级上下文
```

### 4.2 核心方法

#### 4.2.1 orchestrate() - 主调度方法

```python
async def orchestrate(self, user_input: str) -> AsyncGenerator[dict, None]:
    """主调度方法，按阶段流式返回结果"""
    
    for stage in STAGES:
        self.current_stage = stage
        
        try:
            # 阶段门控检查
            if not self._check_gate(stage):
                yield {
                    "type": "stage_skip",
                    "stage": stage,
                    "reason": "门控条件未满足"
                }
                continue
            
            # 执行阶段
            result = await self._execute_stage(stage, user_input)
            
            # 缓存阶段结果
            self.stage_results[stage] = result
            
            # 流式返回
            yield {
                "type": "stage_complete",
                "stage": stage,
                "result": result
            }
            
            # 检查是否需要终止
            if result.get("terminate"):
                break
                
        except Exception as e:
            # 兜底降级
            fallback_result = await self._fallback(stage, e)
            yield {
                "type": "stage_fallback",
                "stage": stage,
                "error": str(e),
                "fallback": fallback_result
            }
```

#### 4.2.2 confirm_info() - 信息确认

```python
async def confirm_info(self, user_input: str) -> dict:
    """信息确认阶段：解析用户输入，提取关键信息"""
    
    prompt = self._build_info_confirm_prompt(user_input)
    response = await call_llm(
        model=self.get_model("confirm"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1  # 低温度保证稳定
    )
    
    info = self._parse_info(response.content)
    
    # 校验必需字段
    missing = self._check_missing_fields(info)
    if missing:
        return {
            "complete": False,
            "missing_fields": missing,
            "followup_question": self._generate_followup(missing)
        }
    
    return {
        "complete": True,
        "info": info,
        "summary": self._summarize_info(info)
    }
```

#### 4.2.3 reset() - 重置状态

```python
def reset(self) -> None:
    """重置 Orchestrator 状态（用于新会话）"""
    self.current_stage = "info_confirm"
    self.stage_results = {}
    self.session_context = {}
    self.reset_context()  # 清空 messages
```

### 4.3 阶段门控详解

```python
# backend/constraints/stage_gate.py
from enum import Enum
from dataclasses import dataclass

class Stage(str, Enum):
    INFO_CONFIRM = "info_confirm"
    CREATIVITY = "creativity"
    VALIDATION = "validation"
    GENERATION = "generation"
    DEEP_ASSIST = "deep_assist"

@dataclass
class GateResult:
    passed: bool
    stage: str
    score: Optional[float] = None
    reason: str = ""
    retry_allowed: bool = True

@dataclass
class StageGate:
    stage: str
    required_fields: list
    min_score: float = 0.0
    max_retries: int = 3
    
    def check(self, result: dict) -> GateResult:
        """检查阶段结果是否满足门控条件"""
        # 检查必需字段
        for field in self.required_fields:
            if field not in result:
                return GateResult(
                    passed=False,
                    stage=self.stage,
                    reason=f"缺少必需字段: {field}"
                )
        
        # 检查分数阈值
        score = result.get("score", 0)
        if score < self.min_score:
            return GateResult(
                passed=False,
                stage=self.stage,
                score=score,
                reason=f"分数 {score} 低于阈值 {self.min_score}"
            )
        
        return GateResult(
            passed=True,
            stage=self.stage,
            score=score
        )

STAGE_GATES = {
    "info_confirm": StageGate(
        stage="info_confirm",
        required_fields=["discipline", "degree", "direction"]
    ),
    "creativity": StageGate(
        stage="creativity",
        required_fields=["candidates"],
        min_score=0.0
    ),
    "validation": StageGate(
        stage="validation",
        required_fields=["evaluations"],
        min_score=60.0  # 关键阈值
    ),
    "generation": StageGate(
        stage="generation",
        required_fields=["report"]
    ),
    "deep_assist": StageGate(
        stage="deep_assist",
        required_fields=[]
    )
}
```

### 4.4 重试与兜底降级

```python
# config/agents/orchestrator.yaml
retry:
  max_attempts: 3
  base_delay: 2.0
  max_delay: 30.0
  backoff: exponential
  retryable_errors:
    - AGENT_TIMEOUT
    - AGENT_RATE_LIMIT
    - AGENT_JSON_PARSE
    - MODEL_UNAVAILABLE

fallback:
  strategy: fallback_proposal
  confidence_score: 0.4
  cascade:
    - searcher: mock_searcher
    - reasoner: fallback_proposal
    - critic: mark_warning
    - mentor: skip_mentor
    - writer: template_mode
```

### 4.5 上下文压缩策略

当上下文超过阈值时，Orchestrator 会触发压缩：

```python
def _compress_context(self) -> None:
    """压缩上下文（保留 system + 最近 N 轮）"""
    max_rounds = 5  # 最大保留轮数
    recent_rounds = 2  # 最近完整保留的轮数
    
    if len(self.messages) > max_rounds * 2 + 1:
        system = self.messages[0]
        recent = self.messages[-(recent_rounds * 2):]
        
        # 压缩中间历史
        middle = self.messages[1:-(recent_rounds * 2)]
        summary = self._summarize_history(middle)
        
        self.messages = [
            system,
            {"role": "system", "content": f"历史摘要: {summary}"},
            *recent
        ]
```

### 4.6 系统提示词

```markdown
# docs/constraints/prompt_templates/orchestrator_system.md

你是 ThesisMiner 的 Orchestrator 主管理 Agent，负责调度五阶段闭环流程。

## 你的职责

1. **信息确认阶段**：解析用户输入，提取学科、学位、研究方向等关键信息
2. **创意生成阶段**：调度 Reasoner 生成 ≥3 个候选选题
3. **验证评估阶段**：调度 Critic 评估候选，分数 ≥60 才通过
4. **报告生成阶段**：调度 Writer 生成多粒度报告
5. **深度辅助阶段**：与用户交互，提供深度修改建议

## 调度原则

- 严格按阶段顺序执行，不跳过门控
- 失败时优先重试，超过 max_attempts 后兜底降级
- 上下文超过阈值时自动压缩
- 每个阶段结果缓存到 stage_results，避免重复计算

## 输出格式

每个阶段完成后，输出 JSON：
```json
{
  "stage": "creativity",
  "status": "complete",
  "result": {...},
  "next_stage": "validation"
}
```
```

### 4.7 使用示例

```python
import asyncio
from backend.agents.agent_registry import get_agent

async def main():
    orchestrator = get_agent("orchestrator")
    
    # 流式接收各阶段结果
    async for event in orchestrator.orchestrate("我想写一篇关于 LLM 的硕士论文"):
        if event["type"] == "stage_complete":
            print(f"阶段 {event['stage']} 完成")
            print(f"结果: {event['result']}")
        elif event["type"] == "stage_fallback":
            print(f"阶段 {event['stage']} 兜底降级")
            print(f"错误: {event['error']}")

asyncio.run(main())
```

---

## 5. Searcher 文献检索 Agent

### 5.1 类定义与职责

`SearcherAgent` 负责文献检索和新颖性检查，支持双模式：

- **MockSearcher**：本地 mock 数据，用于测试和离线场景
- **RealSearcher**：调用 arXiv 和 Semantic Scholar API

```python
# backend/agents/searcher_wrapper.py
from typing import List, Dict
import asyncio
from backend.agents.base_agent import BaseAgent, AgentResult

class SearcherAgent(BaseAgent):
    agent_id = "searcher"
    default_model = "deepseek-v3.2"
    default_temperature = 0.3
    default_max_tokens = 2048
    
    def __init__(self, mode: str = "auto"):
        super().__init__()
        self.mode = mode  # "mock" / "real" / "auto"
        self.mock_searcher = MockSearcher()
        self.real_searcher = RealSearcher()
    
    async def run(self, input_data: dict) -> AgentResult:
        query = input_data.get("query", "")
        top_k = input_data.get("top_k", 10)
        
        # 选择 searcher
        searcher = self._select_searcher()
        
        # 执行检索
        papers = await searcher.search(query, top_k=top_k)
        
        # 新颖性检查
        novelty_scores = await self.check_novelty(query, papers)
        
        return AgentResult(
            agent_id=self.agent_id,
            success=True,
            data={
                "papers": papers,
                "novelty_scores": novelty_scores,
                "total_found": len(papers)
            },
            citations=[p["title"] for p in papers]
        )
```

### 5.2 MockSearcher 本地检索

```python
class MockSearcher:
    """本地 mock 检索器（用于测试）"""
    
    MOCK_PAPERS = [
        {
            "title": "Attention Is All You Need",
            "authors": ["Vaswani et al."],
            "year": 2017,
            "abstract": "提出 Transformer 架构...",
            "url": "https://arxiv.org/abs/1706.03762",
            "citation_count": 90000
        },
        # ... 更多 mock 论文
    ]
    
    async def search(self, query: str, top_k: int = 10) -> List[Dict]:
        """模拟检索（基于关键词匹配）"""
        query_lower = query.lower()
        scored = []
        
        for paper in self.MOCK_PAPERS:
            score = self._calculate_relevance(query_lower, paper)
            scored.append((score, paper))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in scored[:top_k]]
    
    def _calculate_relevance(self, query: str, paper: dict) -> float:
        """计算相关性分数"""
        title = paper["title"].lower()
        abstract = paper["abstract"].lower()
        
        score = 0.0
        for word in query.split():
            if word in title:
                score += 0.5
            if word in abstract:
                score += 0.2
        
        return score
```

### 5.3 RealSearcher 真实检索

```python
class RealSearcher:
    """真实检索器（arXiv + Semantic Scholar）"""
    
    ARXIV_API = "http://export.arxiv.org/api/query"
    SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"
    
    async def search(self, query: str, top_k: int = 10) -> List[Dict]:
        """并行调用 arXiv 和 Semantic Scholar"""
        tasks = [
            self._search_arxiv(query, top_k),
            self._search_semantic_scholar(query, top_k)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        papers = []
        for result in results:
            if isinstance(result, Exception):
                continue  # 单个源失败不影响整体
            papers.extend(result)
        
        # 去重 + 排序
        papers = self._deduplicate(papers)
        papers = self._sort_by_relevance(papers, query)
        
        return papers[:top_k]
    
    async def _search_arxiv(self, query: str, top_k: int) -> List[Dict]:
        """调用 arXiv API"""
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": top_k,
            "sortBy": "relevance",
            "sortOrder": "descending"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(self.ARXIV_API, params=params) as resp:
                xml = await resp.text()
                return self._parse_arxiv_xml(xml)
    
    async def _search_semantic_scholar(self, query: str, top_k: int) -> List[Dict]:
        """调用 Semantic Scholar API"""
        params = {
            "query": query,
            "limit": top_k,
            "fields": "title,authors,year,abstract,url,citationCount"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(self.SEMANTIC_SCHOLAR_API, params=params) as resp:
                data = await resp.json()
                return self._parse_s2_response(data)
```

### 5.4 新颖性检查

```python
async def check_novelty(self, query: str, papers: List[Dict]) -> List[Dict]:
    """检查查询与已有论文的新颖性"""
    scores = []
    
    for paper in papers:
        similarity = self._calculate_similarity(query, paper["title"])
        novelty = 1.0 - similarity
        
        scores.append({
            "paper_title": paper["title"],
            "similarity": similarity,
            "novelty_score": novelty,
            "risk_level": self._get_risk_level(novelty)
        })
    
    return scores

def _calculate_similarity(self, s1: str, s2: str) -> float:
    """基于 Levenshtein 距离计算相似度"""
    distance = self._levenshtein_distance(s1, s2)
    max_len = max(len(s1), len(s2))
    if max_len == 0:
        return 1.0
    return 1.0 - (distance / max_len)

def _levenshtein_distance(self, s1: str, s2: str) -> int:
    """计算 Levenshtein 编辑距离"""
    if len(s1) < len(s2):
        return self._levenshtein_distance(s2, s1)
    
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]

def _get_risk_level(self, novelty: float) -> str:
    """根据新颖性分数判断风险等级"""
    if novelty >= 0.7:
        return "low"      # 低风险（新颖性高）
    elif novelty >= 0.4:
        return "medium"   # 中风险
    else:
        return "high"     # 高风险（与已有论文太相似）
```

### 5.5 配置参考

```yaml
# config/agents/searcher.yaml
agent_id: searcher
model: deepseek-v3.2
temperature: 0.3
max_tokens: 2048

search:
  mode: auto  # mock / real / auto
  top_k: 10
  timeout: 30  # 秒
  sources:
    - arxiv
    - semantic_scholar
  
arxiv:
  api_url: http://export.arxiv.org/api/query
  max_results: 20
  sort_by: relevance
  sort_order: descending

semantic_scholar:
  api_url: https://api.semanticscholar.org/graph/v1/paper/search
  max_results: 20
  fields:
    - title
    - authors
    - year
    - abstract
    - url
    - citationCount

novelty:
  algorithm: levenshtein
  high_risk_threshold: 0.4
  medium_risk_threshold: 0.7
  min_novelty_for_pass: 0.5
```

### 5.6 使用示例

```python
import asyncio
from backend.agents.agent_registry import get_agent

async def main():
    searcher = get_agent("searcher")
    
    result = await searcher.run({
        "query": "大语言模型在教育领域的应用",
        "top_k": 10
    })
    
    if result.success:
        print(f"找到 {result.data['total_found']} 篇论文")
        for paper in result.data["papers"]:
            print(f"- {paper['title']} ({paper['year']})")
        
        print("\n新颖性检查:")
        for score in result.data["novelty_scores"]:
            print(f"- {score['paper_title']}: {score['novelty_score']:.2f} ({score['risk_level']})")

asyncio.run(main())
```

---

## 6. Reasoner 四维创意引擎 Agent

### 6.1 类定义与职责

`ReasonerAgent` 负责通过四个维度生成创意选题候选：

- **cross_discipline**：跨学科融合
- **method_transfer**：方法迁移
- **pain_point_breakthrough**：痛点突破
- **trend_forecast**：趋势预测

```python
# backend/agents/reasoner.py
from typing import List, Dict
from backend.agents.base_agent import BaseAgent, AgentResult

FOUR_DIMENSIONS = [
    "cross_discipline",          # 跨学科融合
    "method_transfer",           # 方法迁移
    "pain_point_breakthrough",   # 痛点突破
    "trend_forecast"             # 趋势预测
]

class ReasonerAgent(BaseAgent):
    agent_id = "reasoner"
    default_model = "deepseek-r2"
    default_temperature = 0.8  # 高温度保证创意性
    default_max_tokens = 4096
    
    async def run(self, input_data: dict) -> AgentResult:
        info = input_data.get("info", {})
        literature = input_data.get("literature", [])
        
        # 构建四维创意 prompt
        prompt = self._build_creativity_prompt(info, literature)
        
        # 调用 LLM
        response = await call_llm(
            model=self.get_model("creativity"),
            messages=[{"role": "user", "content": prompt}],
            temperature=self.default_temperature,
            max_tokens=self.default_max_tokens
        )
        
        # 解析候选（三种模式）
        candidates = self._parse_candidates(response.content)
        
        # 兜底：如果解析失败，使用 fallback
        if not candidates:
            candidates = self._fallback_candidates(info)
        
        return AgentResult(
            agent_id=self.agent_id,
            success=True,
            content=response.content,
            data={"candidates": candidates},
            token_usage=response.token_usage
        )
```

### 6.2 四维创意维度详解

#### 6.2.1 跨学科融合（cross_discipline）

```
学科 A (主)  ──┐
               ├──▶ 融合点 ──▶ 新选题
学科 B (辅)  ──┘
```

示例：
- 主学科：计算机科学（LLM）
- 辅学科：心理学（认知负荷理论）
- 融合选题：基于认知负荷理论的 LLM 提示词优化研究

#### 6.2.2 方法迁移（method_transfer）

```
领域 A 的方法  ──▶ 迁移到领域 B  ──▶ 新选题
```

示例：
- 源方法：CV 领域的对比学习
- 目标领域：NLP 的文本表示
- 迁移选题：对比学习在中文文本表示中的应用研究

#### 6.2.3 痛点突破（pain_point_breakthrough）

```
现有问题  ──▶ 分析根因  ──▶ 提出方案  ──▶ 新选题
```

示例：
- 痛点：LLM 幻觉问题严重
- 根因：缺乏事实校验机制
- 选题：基于知识图谱的 LLM 幻觉检测与缓解方法

#### 6.2.4 趋势预测（trend_forecast）

```
当前热点  ──▶ 技术演进  ──▶ 未来方向  ──▶ 新选题
```

示例：
- 当前：RAG（检索增强生成）
- 演进：多模态 RAG
- 选题：面向多模态文档的 RAG 系统设计与优化

### 6.3 候选解析三种模式

```python
def _parse_candidates(self, content: str) -> List[Dict]:
    """三种模式解析候选"""
    
    # 模式 1: 标准 JSON
    candidates = self._extract_json_candidates(content)
    if candidates:
        return candidates
    
    # 模式 2: Markdown 结构化
    candidates = self._extract_markdown_candidates(content)
    if candidates:
        return candidates
    
    # 模式 3: 自由文本启发式
    candidates = self._extract_heuristic_candidates(content)
    return candidates

def _extract_json_candidates(self, content: str) -> List[Dict]:
    """模式 1: 提取 JSON 格式的候选"""
    import json
    import re
    
    # 尝试提取 ```json ... ``` 代码块
    pattern = r"```json\s*(.*?)\s*```"
    matches = re.findall(pattern, content, re.DOTALL)
    
    for match in matches:
        try:
            data = json.loads(match)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "candidates" in data:
                return data["candidates"]
        except json.JSONDecodeError:
            continue
    
    # 尝试直接解析整个内容
    try:
        data = json.loads(content)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    
    return []

def _extract_markdown_candidates(self, content: str) -> List[Dict]:
    """模式 2: 提取 Markdown 结构化的候选"""
    candidates = []
    current = {}
    
    for line in content.split("\n"):
        if line.startswith("## 候选"):
            if current:
                candidates.append(current)
            current = {}
        elif line.startswith("- **标题**:"):
            current["title"] = line.replace("- **标题**:", "").strip()
        elif line.startswith("- **维度**:"):
            current["dimension"] = line.replace("- **维度**:", "").strip()
        elif line.startswith("- **创新点**:"):
            current["innovation"] = line.replace("- **创新点**:", "").strip()
    
    if current:
        candidates.append(current)
    
    return candidates

def _extract_heuristic_candidates(self, content: str) -> List[Dict]:
    """模式 3: 启发式提取（兜底）"""
    import re
    
    # 匹配 "选题 N: xxx" 或 "N. xxx" 模式
    pattern = r"(?:选题\s*)?(\d+)[.、:：]\s*(.+)"
    matches = re.findall(pattern, content)
    
    return [
        {
            "title": match[1].strip(),
            "dimension": "unknown",
            "innovation": "",
            "source": "heuristic"
        }
        for match in matches
    ]
```

### 6.4 兜底候选生成

```python
def _fallback_candidates(self, info: dict) -> List[Dict]:
    """兜底候选生成（LLM 失败时使用）"""
    discipline = info.get("discipline", "计算机科学")
    direction = info.get("direction", "人工智能")
    
    return [
        {
            "title": f"基于{direction}的{discipline}应用研究",
            "dimension": "pain_point_breakthrough",
            "innovation": "针对实际应用痛点的解决方案",
            "source": "fallback"
        },
        {
            "title": f"{direction}在{discipline}中的方法迁移研究",
            "dimension": "method_transfer",
            "innovation": "跨领域方法迁移",
            "source": "fallback"
        },
        {
            "title": f"{direction}的发展趋势与未来展望",
            "dimension": "trend_forecast",
            "innovation": "前瞻性趋势分析",
            "source": "fallback"
        }
    ]
```

### 6.5 配置参考

```yaml
# config/agents/reasoner.yaml
agent_id: reasoner
model: deepseek-r2
temperature: 0.8
max_tokens: 4096

dimensions:
  - cross_discipline
  - method_transfer
  - pain_point_breakthrough
  - trend_forecast

generation:
  min_candidates: 3
  max_candidates: 5
  require_all_dimensions: true
  
parsing:
  modes:
    - json
    - markdown
    - heuristic
  fallback_on_failure: true

weights:  # 四维权重（用于评分）
  cross_discipline: 0.30
  method_transfer: 0.25
  pain_point_breakthrough: 0.25
  trend_forecast: 0.20
```

### 6.6 使用示例

```python
import asyncio
from backend.agents.agent_registry import get_agent

async def main():
    reasoner = get_agent("reasoner")
    
    result = await reasoner.run({
        "info": {
            "discipline": "计算机科学",
            "degree": "硕士",
            "direction": "大语言模型"
        },
        "literature": [
            {"title": "Attention Is All You Need", "year": 2017},
            {"title": "BERT", "year": 2018}
        ]
    })
    
    if result.success:
        print(f"生成 {len(result.data['candidates'])} 个候选:")
        for i, candidate in enumerate(result.data["candidates"], 1):
            print(f"\n候选 {i}:")
            print(f"  标题: {candidate['title']}")
            print(f"  维度: {candidate['dimension']}")
            print(f"  创新点: {candidate.get('innovation', 'N/A')}")

asyncio.run(main())
```

---

## 7. Critic 候选评估 Agent

### 7.1 类定义与职责

`CriticAgent` 负责评估候选选题，结合本地新颖性检查和 LLM 评估：

```python
# backend/agents/critic.py
from typing import List, Dict
from backend.agents.base_agent import BaseAgent, AgentResult

SCORE_THRESHOLD = 60  # 通过阈值

class CriticAgent(BaseAgent):
    agent_id = "critic"
    default_model = "deepseek-r2"
    default_temperature = 0.2  # 低温度保证评估稳定
    default_max_tokens = 4096
    
    async def run(self, input_data: dict) -> AgentResult:
        candidates = input_data.get("candidates", [])
        literature = input_data.get("literature", [])
        
        # 1. 本地新颖性检查（调用 Searcher）
        novelty_results = await self._check_novelty_local(candidates, literature)
        
        # 2. LLM 评估
        llm_evaluations = await self._llm_evaluate(candidates, novelty_results)
        
        # 3. 融合评分
        evaluations = self._parse_evaluations(llm_evaluations, novelty_results)
        
        # 4. 筛选通过的候选
        passed = [e for e in evaluations if e["score"] >= SCORE_THRESHOLD]
        
        return AgentResult(
            agent_id=self.agent_id,
            success=True,
            data={
                "evaluations": evaluations,
                "passed": passed,
                "threshold": SCORE_THRESHOLD,
                "all_passed": len(passed) == len(evaluations)
            }
        )
```

### 7.2 本地新颖性检查

```python
async def _check_novelty_local(self, candidates: List[Dict], literature: List[Dict]) -> List[Dict]:
    """调用 Searcher 的本地新颖性检查"""
    from backend.agents.agent_registry import get_agent
    
    searcher = get_agent("searcher")
    results = []
    
    for candidate in candidates:
        # 检查与已有文献的相似度
        novelty_scores = await searcher.check_novelty(
            candidate["title"],
            literature
        )
        
        # 取最低新颖性（最高相似度）作为风险指标
        min_novelty = min(s["novelty_score"] for s in novelty_scores) if novelty_scores else 1.0
        
        results.append({
            "candidate_title": candidate["title"],
            "novelty_scores": novelty_scores,
            "min_novelty": min_novelty,
            "risk_level": searcher._get_risk_level(min_novelty)
        })
    
    return results
```

### 7.3 LLM 评估

```python
async def _llm_evaluate(self, candidates: List[Dict], novelty_results: List[Dict]) -> str:
    """调用 LLM 进行深度评估"""
    
    prompt = self._build_evaluation_prompt(candidates, novelty_results)
    
    response = await call_llm(
        model=self.get_model("evaluate"),
        messages=[{"role": "user", "content": prompt}],
        temperature=self.default_temperature,
        max_tokens=self.default_max_tokens
    )
    
    return response.content

def _build_evaluation_prompt(self, candidates: List[Dict], novelty_results: List[Dict]) -> str:
    """构建评估 prompt"""
    prompt = "请对以下候选选题进行评估，每个选题给出 0-100 分的评分：\n\n"
    
    for i, (candidate, novelty) in enumerate(zip(candidates, novelty_results), 1):
        prompt += f"## 候选 {i}\n"
        prompt += f"- 标题: {candidate['title']}\n"
        prompt += f"- 维度: {candidate.get('dimension', 'N/A')}\n"
        prompt += f"- 创新点: {candidate.get('innovation', 'N/A')}\n"
        prompt += f"- 本地新颖性: {novelty['min_novelty']:.2f} ({novelty['risk_level']})\n\n"
    
    prompt += "## 评估维度\n"
    prompt += "- 创新性 (30%): 选题是否具有新颖性\n"
    prompt += "- 可行性 (25%): 是否可在学位论文周期内完成\n"
    prompt += "- 学术价值 (25%): 对学科发展的贡献\n"
    prompt += "- 方法论严谨性 (20%): 研究方法是否科学\n\n"
    prompt += "## 输出格式\n"
    prompt += "```json\n"
    prompt += "[\n"
    prompt += '  {"title": "...", "score": 85, "reasons": {...}, "suggestions": "..."}\n'
    prompt += "]\n"
    prompt += "```"
    
    return prompt
```

### 7.4 评分融合

```python
def _parse_evaluations(self, llm_content: str, novelty_results: List[Dict]) -> List[Dict]:
    """融合 LLM 评估和本地新颖性检查"""
    import json
    import re
    
    # 解析 LLM 输出
    llm_evals = []
    pattern = r"```json\s*(.*?)\s*```"
    matches = re.findall(pattern, llm_content, re.DOTALL)
    
    for match in matches:
        try:
            data = json.loads(match)
            if isinstance(data, list):
                llm_evals.extend(data)
                break
        except json.JSONDecodeError:
            continue
    
    # 融合评分（取 min 作为最终分数，保守策略）
    evaluations = []
    for i, (llm_eval, novelty) in enumerate(zip(llm_evals, novelty_results)):
        llm_score = llm_eval.get("score", 0)
        novelty_score = novelty["min_novelty"] * 100  # 转换为 0-100
        
        # 融合：取两者最小值
        final_score = min(llm_score, novelty_score) if novelty_score > 0 else llm_score
        
        evaluations.append({
            "title": llm_eval.get("title", ""),
            "score": final_score,
            "llm_score": llm_score,
            "novelty_score": novelty_score,
            "risk_level": novelty["risk_level"],
            "reasons": llm_eval.get("reasons", {}),
            "suggestions": llm_eval.get("suggestions", ""),
            "passed": final_score >= SCORE_THRESHOLD
        })
    
    return evaluations
```

### 7.5 配置参考

```yaml
# config/agents/critic.yaml
agent_id: critic
model: deepseek-r2
temperature: 0.2
max_tokens: 4096

evaluation:
  threshold: 60
  dimensions:
    - name: innovation
      weight: 0.30
    - name: feasibility
      weight: 0.25
    - name: academic_value
      weight: 0.25
    - name: methodology
      weight: 0.20
  
fusion:
  strategy: min  # min / max / weighted_avg
  use_local_novelty: true
  
retry:
  max_attempts: 2
  on_low_score: regenerate
```

### 7.6 使用示例

```python
import asyncio
from backend.agents.agent_registry import get_agent

async def main():
    critic = get_agent("critic")
    
    result = await critic.run({
        "candidates": [
            {"title": "基于 RAG 的 LLM 幻觉缓解", "dimension": "pain_point_breakthrough"},
            {"title": "多模态对比学习", "dimension": "method_transfer"}
        ],
        "literature": [
            {"title": "RAG: Retrieval-Augmented Generation", "year": 2020}
        ]
    })
    
    if result.success:
        print(f"阈值: {result.data['threshold']}")
        print(f"全部通过: {result.data['all_passed']}")
        for eval in result.data["evaluations"]:
            status = "✓ 通过" if eval["passed"] else "✗ 未通过"
            print(f"\n{status} {eval['title']}")
            print(f"  最终分数: {eval['score']:.1f}")
            print(f"  LLM 分数: {eval['llm_score']}")
            print(f"  新颖性分数: {eval['novelty_score']:.1f}")
            print(f"  风险等级: {eval['risk_level']}")

asyncio.run(main())
```

---

## 8. Mentor 导师视角 Agent

### 8.1 类定义与职责

`MentorAgent` 模拟导师视角，对选题进行评审：

```python
# backend/agents/mentor_agent.py
from typing import List, Dict, Optional
from backend.agents.base_agent import BaseAgent, AgentResult

class MentorAgent(BaseAgent):
    agent_id = "mentor"
    default_model = "gpt-4.1"
    default_temperature = 0.4
    default_max_tokens = 2048
    
    async def run(self, input_data: dict) -> AgentResult:
        proposal = input_data.get("proposal", {})
        mode = input_data.get("mode", "single")  # single / batch
        
        if mode == "batch":
            return await self.batch_review(input_data.get("proposals", []))
        else:
            return await self.review_proposal(proposal)
    
    async def review_proposal(self, proposal: dict) -> AgentResult:
        """单个选题评审"""
        prompt = self._build_review_prompt(proposal)
        
        try:
            response = await call_llm(
                model=self.get_model("review"),
                messages=[{"role": "user", "content": prompt}],
                temperature=self.default_temperature,
                max_tokens=self.default_max_tokens
            )
            
            review = self._parse_review(response.content)
            
            return AgentResult(
                agent_id=self.agent_id,
                success=True,
                content=response.content,
                data={"review": review},
                token_usage=response.token_usage
            )
        except Exception as e:
            # 兜底评审
            review = self.fallback_review(proposal)
            return AgentResult(
                agent_id=self.agent_id,
                success=True,  # 兜底也算成功
                data={"review": review, "fallback": True},
                error=str(e)
            )
```

### 8.2 批量评审

```python
async def batch_review(self, proposals: List[dict]) -> AgentResult:
    """批量评审多个选题"""
    prompt = self._build_batch_prompt(proposals)
    
    response = await call_llm(
        model=self.get_model("batch_review"),
        messages=[{"role": "user", "content": prompt}],
        temperature=self.default_temperature,
        max_tokens=self.default_max_tokens * 2  # 批量需要更多 token
    )
    
    reviews = self._parse_batch_reviews(response.content)
    
    return AgentResult(
        agent_id=self.agent_id,
        success=True,
        content=response.content,
        data={"reviews": reviews},
        token_usage=response.token_usage
    )
```

### 8.3 兜底评审

```python
def fallback_review(self, proposal: dict) -> dict:
    """兜底评审（LLM 失败时使用）"""
    title = proposal.get("title", "")
    
    return {
        "overall_comment": "该选题具有一定的研究价值，建议进一步明确研究问题和方法论。",
        "strengths": [
            "选题方向符合学科发展趋势",
            "具有一定的实际应用价值"
        ],
        "weaknesses": [
            "研究问题需要进一步聚焦",
            "方法论需要更详细的论述"
        ],
        "suggestions": [
            "明确研究的核心问题",
            "细化研究方法和技术路线",
            "补充相关文献综述"
        ],
        "score": 70,  # 兜底默认分数
        "recommendation": "modify",  # accept / modify / reject
        "source": "fallback"
    }
```

### 8.4 配置参考

```yaml
# config/agents/mentor.yaml
agent_id: mentor
model: gpt-4.1
temperature: 0.4
max_tokens: 2048

review:
  modes:
    - single
    - batch
  batch_size: 5
  dimensions:
    - academic_value
    - feasibility
    - innovation
    - methodology
    - writing_quality
  
recommendation_levels:
  - accept      # 接受
  - modify      # 修改后接受
  - reject      # 拒绝
  
fallback:
  enabled: true
  default_score: 70
  default_recommendation: modify
```

### 8.5 使用示例

```python
import asyncio
from backend.agents.agent_registry import get_agent

async def main():
    mentor = get_agent("mentor")
    
    # 单个评审
    result = await mentor.run({
        "mode": "single",
        "proposal": {
            "title": "基于 RAG 的 LLM 幻觉缓解研究",
            "abstract": "本研究提出...",
            "outline": ["引言", "相关工作", "方法", "实验", "结论"]
        }
    })
    
    if result.success:
        review = result.data["review"]
        print(f"评分: {review['score']}")
        print(f"建议: {review['recommendation']}")
        print(f"总评: {review['overall_comment']}")
        print(f"优点: {review['strengths']}")
        print(f"不足: {review['weaknesses']}")
        print(f"建议: {review['suggestions']}")

asyncio.run(main())
```

---

## 9. Writer 多粒度生成 Agent

### 9.1 类定义与职责

`WriterAgent` 支持四种粒度的报告生成：

```python
# backend/agents/proposal_writer.py
from typing import List, Dict
from backend.agents.base_agent import BaseAgent, AgentResult

GRANULARITIES = ("title", "abstract", "outline", "full")

class WriterAgent(BaseAgent):
    agent_id = "writer"
    default_model = "claude-opus-4.5"
    default_temperature = 0.6
    default_max_tokens = 8192
    
    async def run(self, input_data: dict) -> AgentResult:
        topic = input_data.get("topic", {})
        granularity = input_data.get("granularity", "full")
        style = input_data.get("style", "academic")
        
        if granularity not in GRANULARITIES:
            return AgentResult(
                agent_id=self.agent_id,
                success=False,
                error=f"不支持的粒度: {granularity}"
            )
        
        # 构建生成 prompt
        prompt = self._build_generation_prompt(topic, granularity, style)
        
        # 调用 LLM
        response = await call_llm(
            model=self.get_model(f"generate_{granularity}"),
            messages=[{"role": "user", "content": prompt}],
            temperature=self.default_temperature,
            max_tokens=self.default_max_tokens
        )
        
        # 应用样式规范化
        content = self._apply_style_normalizer(response.content, style)
        
        return AgentResult(
            agent_id=self.agent_id,
            success=True,
            content=content,
            data={
                "granularity": granularity,
                "style": style,
                "word_count": len(content)
            },
            token_usage=response.token_usage
        )
```

### 9.2 四种粒度详解

#### 9.2.1 title（标题）

```python
def _build_title_prompt(self, topic: dict) -> str:
    return f"""请基于以下信息生成 3-5 个候选标题：

研究方向: {topic.get('direction', '')}
学位类型: {topic.get('degree', '')}
关键内容: {topic.get('keywords', '')}

要求:
1. 硕士标题 ≤25 字，博士标题 ≤30 字
2. 避免使用"基于"开头
3. 避免空泛词汇（如"研究"、"应用"单独出现）
4. 体现研究方法或创新点

输出格式:
```json
["标题1", "标题2", "标题3"]
```
"""
```

#### 9.2.2 abstract（摘要）

```python
def _build_abstract_prompt(self, topic: dict) -> str:
    return f"""请基于以下信息生成论文摘要（300-500 字）：

标题: {topic.get('title', '')}
研究方向: {topic.get('direction', '')}
创新点: {topic.get('innovation', '')}

要求:
1. 包含背景、问题、方法、结果、贡献五要素
2. 避免使用"本文"、"本研究"等第一人称
3. 不出现"显著"、"重要"等空泛修饰
4. 字数控制在 300-500 字

输出格式: 直接输出摘要文本，不要额外说明。
"""
```

#### 9.2.3 outline（大纲）

```python
def _build_outline_prompt(self, topic: dict) -> str:
    return f"""请基于以下信息生成论文大纲：

标题: {topic.get('title', '')}
摘要: {topic.get('abstract', '')}
学位类型: {topic.get('degree', '')}

要求:
1. 硕士论文 5-6 章，博士论文 6-8 章
2. 每章包含 3-5 节
3. 结构完整：引言 → 相关工作 → 方法 → 实验 → 结论
4. 体现研究逻辑和创新点

输出格式:
```json
{{
  "chapters": [
    {{
      "title": "第一章 引言",
      "sections": ["1.1 研究背景", "1.2 研究问题"]
    }}
  ]
}}
```
"""
```

#### 9.2.4 full（完整报告）

```python
def _build_full_prompt(self, topic: dict) -> str:
    return f"""请基于以下信息生成完整的开题报告：

标题: {topic.get('title', '')}
摘要: {topic.get('abstract', '')}
大纲: {topic.get('outline', '')}
参考文献: {topic.get('references', '')}

要求:
1. 字数 8000-15000 字
2. 包含：引言、相关工作、研究内容、方法、计划、参考文献
3. 学术风格，避免口语化
4. 引用格式统一（GB/T 7714）

输出格式: Markdown 格式的完整报告。
"""
```

### 9.3 样式规范化

```python
def _apply_style_normalizer(self, content: str, style: str) -> str:
    """应用样式规范化"""
    
    # 1. 去除 AI 痕迹
    content = self._remove_ai_traces(content)
    
    # 2. 学术风格转换
    if style == "academic":
        content = self._to_academic_style(content)
    
    # 3. 统一引用格式
    content = self._normalize_citations(content)
    
    # 4. 术语统一
    content = self._normalize_terminology(content)
    
    return content

def _remove_ai_traces(self, content: str) -> str:
    """去除 AI 生成痕迹"""
    import re
    
    # 去除常见 AI 词汇
    ai_phrases = [
        r"总之[，,]?",
        r"综上所述[，,]?",
        r"值得注意的是[，,]?",
        r"需要指出的是[，,]?",
        r"总的来说[，,]?",
        r"由此可见[，,]?"
    ]
    
    for pattern in ai_phrases:
        content = re.sub(pattern, "", content)
    
    return content
```

### 9.4 配置参考

```yaml
# config/agents/writer.yaml
agent_id: writer
model: claude-opus-4.5
temperature: 0.6
max_tokens: 8192

granularities:
  - title
  - abstract
  - outline
  - full

generation:
  title:
    max_count: 5
    master_max_length: 25
    doctor_max_length: 30
  abstract:
    min_words: 300
    max_words: 500
  outline:
    master_chapters: [5, 6]
    doctor_chapters: [6, 8]
    sections_per_chapter: [3, 5]
  full:
    min_words: 8000
    max_words: 15000

style:
  default: academic
  normalize: true
  remove_ai_traces: true
  citation_format: GB/T 7714
```

### 9.5 使用示例

```python
import asyncio
from backend.agents.agent_registry import get_agent

async def main():
    writer = get_agent("writer")
    
    # 生成完整报告
    result = await writer.run({
        "topic": {
            "title": "基于 RAG 的 LLM 幻觉缓解研究",
            "direction": "大语言模型",
            "degree": "硕士",
            "innovation": "引入知识图谱校验"
        },
        "granularity": "full",
        "style": "academic"
    })
    
    if result.success:
        print(f"生成 {result.data['granularity']} 报告")
        print(f"字数: {result.data['word_count']}")
        print(f"\n{result.content[:500]}...")

asyncio.run(main())
```

---

## 10. Agent 间通信协议

### 10.1 通信架构

ThesisMiner v8.0 的 Agent 间通信采用"中心化"模式，所有通信通过 Orchestrator 中转：

```
┌─────────────────────────────────────────────────────────┐
│                   Orchestrator                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │  - 接收用户输入                                   │  │
│  │  - 调度子 Agent                                   │  │
│  │  - 传递上下文                                     │  │
│  │  - 融合结果                                       │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
        │           │           │           │           │
        ▼           ▼           ▼           ▼           ▼
   ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
   │Searcher│ │Reasoner│ │ Critic │ │ Mentor │ │ Writer │
   └────────┘ └────────┘ └────────┘ └────────┘ └────────┘
```

### 10.2 通信数据结构

Agent 间通过 `AgentResult` 和 `dict` 传递数据：

```python
# Orchestrator → Searcher
input_data = {
    "query": "大语言模型在教育领域的应用",
    "top_k": 10,
    "session_id": "sess_123"
}

# Searcher → Orchestrator
result = AgentResult(
    agent_id="searcher",
    success=True,
    data={
        "papers": [...],
        "novelty_scores": [...]
    }
)

# Orchestrator → Reasoner（携带 Searcher 结果）
input_data = {
    "info": {...},
    "literature": result.data["papers"]  # 传递文献
}
```

### 10.3 通信时序图

```
用户          Orchestrator      Searcher      Reasoner      Critic       Writer
 │                │                │             │            │             │
 │──输入─────────▶│                │             │            │             │
 │                │                │             │            │             │
 │                │──检索─────────▶│             │            │             │
 │                │◀──论文列表─────│             │            │             │
 │                │                │             │            │             │
 │                │──生成候选───────────────────▶│            │             │
 │                │◀──候选列表───────────────────│            │             │
 │                │                │             │            │             │
 │                │──评估候选───────────────────────────────▶│             │
 │                │◀──评估结果───────────────────────────────│             │
 │                │                │             │            │             │
 │                │──生成报告────────────────────────────────────────────▶│
 │                │◀──完整报告────────────────────────────────────────────│
 │                │                │             │            │             │
 │◀──最终结果─────│                │             │            │             │
```

### 10.4 上下文传递规则

```python
# Orchestrator 在调度子 Agent 时，会传递必要的上下文：

# 阶段 1: info_confirm
# Orchestrator 自己处理，不调用子 Agent

# 阶段 2: creativity
# 传递：info（用户信息）
orchestrator._execute_creativity({
    "info": session_context["info"]
})

# Searcher 检索文献
searcher_result = await searcher.run({
    "query": info["direction"],
    "top_k": 10
})

# Reasoner 生成候选（携带文献）
reasoner_result = await reasoner.run({
    "info": info,
    "literature": searcher_result.data["papers"]
})

# 阶段 3: validation
# Critic 评估（携带候选 + 文献）
critic_result = await critic.run({
    "candidates": reasoner_result.data["candidates"],
    "literature": searcher_result.data["papers"]
})

# 阶段 4: generation
# Writer 生成报告（携带通过的候选）
writer_result = await writer.run({
    "topic": critic_result.data["passed"][0],  # 取最高分候选
    "granularity": "full"
})

# Mentor 评审
mentor_result = await mentor.run({
    "proposal": {
        "title": writer_result.content[:100],
        "content": writer_result.content
    }
})
```

---

## 11. Agent 协作模式

### 11.1 串行模式（默认）

```
Searcher → Reasoner → Critic → Writer → Mentor
```

特点：
- 严格顺序执行
- 前一个 Agent 的输出作为后一个的输入
- 任一 Agent 失败则整个流程中断

### 11.2 并行模式

```python
# 某些场景下，可以并行调用多个 Agent
async def parallel_creativity(self, info: dict):
    """并行调用 Searcher 和 Reasoner"""
    tasks = [
        searcher.run({"query": info["direction"]}),
        reasoner.run({"info": info, "literature": []})  # 先不传文献
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 融合结果
    searcher_result, reasoner_result = results
    
    # 如果 Searcher 成功，补充文献给 Reasoner 重试
    if isinstance(searcher_result, AgentResult) and searcher_result.success:
        reasoner_result = await reasoner.run({
            "info": info,
            "literature": searcher_result.data["papers"]
        })
    
    return searcher_result, reasoner_result
```

### 11.3 重试模式

```python
async def retry_with_backoff(self, agent, input_data, max_attempts=3):
    """带退避的重试"""
    base_delay = 2.0
    max_delay = 30.0
    
    for attempt in range(max_attempts):
        try:
            result = await agent.run(input_data)
            if result.success:
                return result
        except Exception as e:
            if attempt == max_attempts - 1:
                raise
            
            # 指数退避
            delay = min(base_delay * (2 ** attempt), max_delay)
            await asyncio.sleep(delay)
    
    return AgentResult(
        agent_id=agent.agent_id,
        success=False,
        error=f"重试 {max_attempts} 次后仍失败"
    )
```

### 11.4 兜底降级模式

```python
async def fallback_cascade(self, stage: str, error: Exception):
    """兜底降级级联"""
    fallback_map = {
        "searcher": self._fallback_searcher,
        "reasoner": self._fallback_reasoner,
        "critic": self._fallback_critic,
        "mentor": self._fallback_mentor,
        "writer": self._fallback_writer
    }
    
    fallback_fn = fallback_map.get(stage)
    if fallback_fn:
        return await fallback_fn(error)
    
    return AgentResult(
        agent_id=stage,
        success=False,
        error=f"无兜底方案: {error}"
    )

async def _fallback_searcher(self, error: Exception):
    """Searcher 兜底：使用 MockSearcher"""
    mock = MockSearcher()
    papers = await mock.search("fallback", top_k=5)
    return AgentResult(
        agent_id="searcher",
        success=True,
        data={"papers": papers, "fallback": True},
        error=f"使用 MockSearcher 兜底: {error}"
    )

async def _fallback_writer(self, error: Exception):
    """Writer 兜底：使用模板生成"""
    template_content = """
# 开题报告

## 一、研究背景
（待补充）

## 二、研究问题
（待补充）

## 三、研究方法
（待补充）
"""
    return AgentResult(
        agent_id="writer",
        success=True,
        content=template_content,
        data={"fallback": True, "template": True},
        error=f"使用模板兜底: {error}"
    )
```

---

## 12. 冲突解决机制

### 12.1 冲突类型

| 冲突类型 | 描述 | 示例 |
|----------|------|------|
| 评分冲突 | Critic 与 Mentor 评分差异大 | Critic: 85, Mentor: 50 |
| 候选冲突 | Reasoner 生成的候选重复 | 两个候选标题相似度 > 0.8 |
| 文献冲突 | Searcher 与本地库不一致 | API 返回 vs 本地缓存 |
| 阶段冲突 | 阶段结果与门控矛盾 | score < 60 但标记为 passed |

### 12.2 评分冲突解决

```python
def resolve_score_conflict(self, critic_score: float, mentor_score: float) -> dict:
    """解决 Critic 与 Mentor 的评分冲突"""
    diff = abs(critic_score - mentor_score)
    
    if diff <= 10:
        # 差异小：取平均
        final_score = (critic_score + mentor_score) / 2
        strategy = "average"
    elif diff <= 20:
        # 差异中等：取较低分（保守）
        final_score = min(critic_score, mentor_score)
        strategy = "conservative_min"
    else:
        # 差异大：触发仲裁
        final_score = self._arbitrate(critic_score, mentor_score)
        strategy = "arbitration"
    
    return {
        "final_score": final_score,
        "critic_score": critic_score,
        "mentor_score": mentor_score,
        "strategy": strategy,
        "conflict": diff > 10
    }

async def _arbitrate(self, critic_score: float, mentor_score: float) -> float:
    """仲裁：调用更高层 LLM 重新评估"""
    # 使用更强的模型仲裁
    response = await call_llm(
        model="claude-opus-4.5",  # 最强模型
        messages=[{
            "role": "user",
            "content": f"Critic 评分 {critic_score}，Mentor 评分 {mentor_score}，请给出最终评分（0-100）"
        }],
        temperature=0.1
    )
    
    import re
    match = re.search(r"\d+", response.content)
    return float(match.group()) if match else min(critic_score, mentor_score)
```

### 12.3 候选去重冲突

```python
def deduplicate_candidates(self, candidates: List[dict], threshold: float = 0.8) -> List[dict]:
    """候选去重"""
    unique = []
    
    for candidate in candidates:
        is_duplicate = False
        for existing in unique:
            similarity = self._calculate_similarity(
                candidate["title"],
                existing["title"]
            )
            if similarity > threshold:
                is_duplicate = True
                # 保留分数更高的
                if candidate.get("score", 0) > existing.get("score", 0):
                    unique.remove(existing)
                    unique.append(candidate)
                break
        
        if not is_duplicate:
            unique.append(candidate)
    
    return unique
```

---

## 13. Agent 扩展开发指南

### 13.1 扩展点列表

| 扩展点 | 位置 | 用途 |
|--------|------|------|
| 自定义 Agent | `backend/agents/` | 添加新的 Agent 类型 |
| 自定义 Searcher | `backend/agents/searcher_wrapper.py` | 添加新的检索源 |
| 自定义评估维度 | `backend/agents/critic.py` | 添加评估维度 |
| 自定义生成粒度 | `backend/agents/proposal_writer.py` | 添加生成粒度 |
| 自定义门控 | `backend/constraints/stage_gate.py` | 添加阶段门控 |

### 13.2 扩展开发步骤

#### 步骤 1: 创建 Agent 类

```python
# backend/agents/translator_agent.py
from backend.agents.base_agent import BaseAgent, AgentResult

class TranslatorAgent(BaseAgent):
    agent_id = "translator"
    default_model = "gpt-4.1"
    default_temperature = 0.3
    
    async def run(self, input_data: dict) -> AgentResult:
        text = input_data.get("text", "")
        target_lang = input_data.get("target_lang", "en")
        
        prompt = f"请将以下文本翻译为 {target_lang}:\n{text}"
        
        response = await call_llm(
            model=self.get_model(),
            messages=[{"role": "user", "content": prompt}],
            temperature=self.default_temperature
        )
        
        return AgentResult(
            agent_id=self.agent_id,
            success=True,
            content=response.content,
            token_usage=response.token_usage
        )
```

#### 步骤 2: 注册 Agent

```python
# backend/agents/__init__.py
from backend.agents.translator_agent import TranslatorAgent
from backend.agents.agent_registry import register_agent

register_agent("translator", TranslatorAgent)
```

#### 步骤 3: 添加配置

```yaml
# config/agents/translator.yaml
agent_id: translator
model: gpt-4.1
temperature: 0.3
max_tokens: 2048

languages:
  - en
  - zh
  - ja
  - ko
```

#### 步骤 4: 使用 Agent

```python
from backend.agents.agent_registry import get_agent

translator = get_agent("translator")
result = await translator.run({
    "text": "大语言模型",
    "target_lang": "en"
})
print(result.content)  # Large Language Model
```

### 13.3 扩展 Searcher

```python
# 添加新的检索源（如 Google Scholar）
class GoogleScholarSearcher:
    GOOGLE_SCHOLAR_API = "https://api.serpdog.io/scholar"
    
    async def search(self, query: str, top_k: int = 10) -> List[Dict]:
        params = {
            "q": query,
            "num": top_k,
            "api_key": os.getenv("SERPDOG_API_KEY")
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(self.GOOGLE_SCHOLAR_API, params=params) as resp:
                data = await resp.json()
                return self._parse_response(data)

# 在 RealSearcher 中集成
class RealSearcher:
    def __init__(self):
        self.google_scholar = GoogleScholarSearcher()
    
    async def search(self, query: str, top_k: int = 10) -> List[Dict]:
        tasks = [
            self._search_arxiv(query, top_k),
            self._search_semantic_scholar(query, top_k),
            self.google_scholar.search(query, top_k)  # 新增
        ]
        # ...
```

---

## 14. 自定义 Agent 开发

### 14.1 完整示例：TranslatorAgent

```python
# backend/agents/translator_agent.py
from typing import Optional
from backend.agents.base_agent import BaseAgent, AgentResult
from backend.ai.ai_proxy import call_llm

SUPPORTED_LANGUAGES = {
    "en": "English",
    "zh": "中文",
    "ja": "日本語",
    "ko": "한국어",
    "fr": "Français",
    "de": "Deutsch"
}

class TranslatorAgent(BaseAgent):
    """翻译 Agent：支持多语言互译"""
    
    agent_id = "translator"
    default_model = "gpt-4.1"
    default_temperature = 0.3
    default_max_tokens = 2048
    
    def __init__(self):
        super().__init__()
        self.supported_languages = SUPPORTED_LANGUAGES
    
    async def run(self, input_data: dict) -> AgentResult:
        # 1. 参数校验
        text = input_data.get("text", "").strip()
        target_lang = input_data.get("target_lang", "en")
        source_lang = input_data.get("source_lang", "auto")
        
        if not text:
            return AgentResult(
                agent_id=self.agent_id,
                success=False,
                error="缺少必需参数: text"
            )
        
        if target_lang not in self.supported_languages:
            return AgentResult(
                agent_id=self.agent_id,
                success=False,
                error=f"不支持的目标语言: {target_lang}，支持: {list(self.supported_languages.keys())}"
            )
        
        # 2. 构建 prompt
        prompt = self._build_prompt(text, source_lang, target_lang)
        
        # 3. 调用 LLM
        try:
            response = await call_llm(
                model=self.get_model(),
                messages=[{"role": "user", "content": prompt}],
                temperature=self.default_temperature,
                max_tokens=self.default_max_tokens
            )
            
            # 4. 返回结果
            return AgentResult(
                agent_id=self.agent_id,
                success=True,
                content=response.content.strip(),
                data={
                    "source_lang": source_lang,
                    "target_lang": target_lang,
                    "char_count": len(response.content)
                },
                token_usage=response.token_usage
            )
            
        except Exception as e:
            return AgentResult(
                agent_id=self.agent_id,
                success=False,
                error=f"翻译失败: {e}"
            )
    
    def _build_prompt(self, text: str, source_lang: str, target_lang: str) -> str:
        source_name = self.supported_languages.get(source_lang, "自动检测")
        target_name = self.supported_languages[target_lang]
        
        return f"""请将以下{source_name}文本翻译为{target_name}，只输出翻译结果，不要额外说明：

{text}
"""
```

### 14.2 注册与使用

```python
# 注册
from backend.agents.translator_agent import TranslatorAgent
from backend.agents.agent_registry import register_agent

register_agent("translator", TranslatorAgent)

# 使用
from backend.agents.agent_registry import get_agent

translator = get_agent("translator")
result = await translator.run({
    "text": "大语言模型在教育领域的应用",
    "target_lang": "en"
})

if result.success:
    print(result.content)
    # Output: Applications of Large Language Models in Education
```

### 14.3 测试自定义 Agent

```python
# tests/test_translator_agent.py
import pytest
from unittest.mock import AsyncMock, patch
from backend.agents.translator_agent import TranslatorAgent
from backend.agents.base_agent import AgentResult

@pytest.mark.asyncio
async def test_translator_success():
    """测试翻译成功"""
    translator = TranslatorAgent()
    
    with patch("backend.agents.translator_agent.call_llm") as mock_call:
        mock_call.return_value = AsyncMock(
            content="Large Language Model",
            token_usage={"total_tokens": 100}
        )
        
        result = await translator.run({
            "text": "大语言模型",
            "target_lang": "en"
        })
        
        assert result.success is True
        assert result.content == "Large Language Model"
        assert result.data["target_lang"] == "en"

@pytest.mark.asyncio
async def test_translator_missing_text():
    """测试缺少 text 参数"""
    translator = TranslatorAgent()
    
    result = await translator.run({
        "target_lang": "en"
    })
    
    assert result.success is False
    assert "text" in result.error

@pytest.mark.asyncio
async def test_translator_unsupported_lang():
    """测试不支持的语言"""
    translator = TranslatorAgent()
    
    result = await translator.run({
        "text": "hello",
        "target_lang": "xx"  # 不支持
    })
    
    assert result.success is False
    assert "不支持" in result.error
```

---

## 15. Agent 性能指标

### 15.1 性能指标定义

| 指标 | 单位 | 说明 | 目标值 |
|------|------|------|--------|
| 响应时间 | ms | Agent 单次执行耗时 | < 5000 |
| 吞吐量 | req/s | 每秒处理请求数 | > 10 |
| 成功率 | % | 成功执行的比例 | > 95% |
| Token 消耗 | tokens | 单次执行平均 token | < 3000 |
| 缓存命中率 | % | Prompt 缓存命中比例 | > 95% |
| 错误率 | % | 失败执行的比例 | < 5% |

### 15.2 各 Agent 性能基准

```python
# 基准测试结果（v8.0.0）
PERFORMANCE_BENCHMARKS = {
    "orchestrator": {
        "avg_response_ms": 3200,
        "p95_response_ms": 5800,
        "p99_response_ms": 8500,
        "success_rate": 0.97,
        "avg_tokens": 2500,
        "cache_hit_rate": 0.96
    },
    "searcher": {
        "avg_response_ms": 1800,
        "p95_response_ms": 3500,
        "p99_response_ms": 6000,
        "success_rate": 0.98,
        "avg_tokens": 800,
        "cache_hit_rate": 0.92
    },
    "reasoner": {
        "avg_response_ms": 4500,
        "p95_response_ms": 8000,
        "p99_response_ms": 12000,
        "success_rate": 0.94,
        "avg_tokens": 3500,
        "cache_hit_rate": 0.95
    },
    "critic": {
        "avg_response_ms": 3800,
        "p95_response_ms": 6500,
        "p99_response_ms": 9500,
        "success_rate": 0.96,
        "avg_tokens": 2800,
        "cache_hit_rate": 0.94
    },
    "mentor": {
        "avg_response_ms": 2800,
        "p95_response_ms": 5000,
        "p99_response_ms": 7500,
        "success_rate": 0.97,
        "avg_tokens": 1800,
        "cache_hit_rate": 0.93
    },
    "writer": {
        "avg_response_ms": 6500,
        "p95_response_ms": 12000,
        "p99_response_ms": 18000,
        "success_rate": 0.93,
        "avg_tokens": 6000,
        "cache_hit_rate": 0.97
    }
}
```

### 15.3 性能监控

```python
# backend/observability/agent_metrics.py
import time
from functools import wraps
from typing import Callable

class AgentMetrics:
    """Agent 性能指标收集器"""
    
    def __init__(self):
        self.metrics = {}
    
    def record(self, agent_id: str, duration_ms: float, success: bool, tokens: int):
        """记录单次执行指标"""
        if agent_id not in self.metrics:
            self.metrics[agent_id] = {
                "count": 0,
                "total_duration_ms": 0,
                "success_count": 0,
                "total_tokens": 0,
                "durations": []
            }
        
        m = self.metrics[agent_id]
        m["count"] += 1
        m["total_duration_ms"] += duration_ms
        m["durations"].append(duration_ms)
        if success:
            m["success_count"] += 1
        m["total_tokens"] += tokens
    
    def get_summary(self, agent_id: str) -> dict:
        """获取指标摘要"""
        m = self.metrics.get(agent_id, {})
        count = m.get("count", 0)
        
        if count == 0:
            return {}
        
        durations = sorted(m["durations"])
        p95_idx = int(len(durations) * 0.95)
        
        return {
            "count": count,
            "avg_duration_ms": m["total_duration_ms"] / count,
            "p95_duration_ms": durations[p95_idx] if durations else 0,
            "success_rate": m["success_count"] / count,
            "avg_tokens": m["total_tokens"] / count
        }

# 全局指标实例
agent_metrics = AgentMetrics()

def with_metrics(agent_id: str):
    """装饰器：自动记录 Agent 指标"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.time()
            success = False
            tokens = 0
            
            try:
                result = await func(*args, **kwargs)
                success = result.success
                tokens = result.token_usage.get("total_tokens", 0)
                return result
            finally:
                duration_ms = (time.time() - start) * 1000
                agent_metrics.record(agent_id, duration_ms, success, tokens)
        
        return wrapper
    return decorator
```

### 15.4 性能优化建议

#### 15.4.1 减少 Token 消耗

```python
# 1. 启用 Prompt 缓存
from backend.ai.prompt_cache import build_cached_prefix

cached_prefix = build_cached_prefix(
    system_prompt="你是 Searcher Agent...",
    user_info={"discipline": "CS"}
)

# 2. 压缩上下文
def compress_messages(messages: list, max_rounds: int = 5) -> list:
    """压缩对话历史"""
    if len(messages) > max_rounds * 2 + 1:
        system = messages[0]
        recent = messages[-(max_rounds * 2):]
        return [system] + recent
    return messages

# 3. 使用更短的 prompt
SHORT_PROMPT = "检索: {query}"  # 而不是长篇大论
```

#### 15.4.2 提高缓存命中率

```python
# 1. 保持 system prompt 稳定
SYSTEM_PROMPT = """你是 Searcher Agent，负责文献检索。
职责：调用 arXiv 和 Semantic Scholar API
"""  # 不要动态修改

# 2. 用户信息放在固定位置
def build_prompt(query: str, user_info: dict) -> str:
    return f"""
[用户信息]
学科: {user_info['discipline']}
学位: {user_info['degree']}

[查询]
{query}
"""

# 3. 避免在 cached prefix 中放时间戳
# 错误：f"当前时间: {datetime.now()}"
# 正确：将时间戳放在 non-cached 部分
```

---

## 16. Agent 错误处理

### 16.1 错误分类

| 错误类型 | 错误码 | 描述 | 处理策略 |
|----------|--------|------|----------|
| 超时 | AGENT_TIMEOUT | Agent 执行超时 | 重试 + 兜底 |
| 限流 | AGENT_RATE_LIMIT | LLM API 限流 | 退避重试 |
| JSON 解析 | AGENT_JSON_PARSE | LLM 输出 JSON 解析失败 | 重新请求 |
| 模型不可用 | MODEL_UNAVAILABLE | 模型服务不可用 | 切换备用模型 |
| 输入无效 | AGENT_INVALID_INPUT | 输入参数校验失败 | 直接返回错误 |
| 未知错误 | AGENT_UNKNOWN | 未分类错误 | 兜底降级 |

### 16.2 错误处理代码

```python
# backend/agents/exceptions.py
class AgentError(Exception):
    """Agent 基础错误"""
    def __init__(self, code: str, message: str, retryable: bool = False):
        self.code = code
        self.message = message
        self.retryable = retryable
        super().__init__(message)

class AgentTimeoutError(AgentError):
    def __init__(self, message: str = "Agent 执行超时"):
        super().__init__("AGENT_TIMEOUT", message, retryable=True)

class AgentRateLimitError(AgentError):
    def __init__(self, message: str = "API 限流"):
        super().__init__("AGENT_RATE_LIMIT", message, retryable=True)

class AgentJsonParseError(AgentError):
    def __init__(self, message: str = "JSON 解析失败"):
        super().__init__("AGENT_JSON_PARSE", message, retryable=True)

class ModelUnavailableError(AgentError):
    def __init__(self, model: str):
        super().__init__("MODEL_UNAVAILABLE", f"模型 {model} 不可用", retryable=True)

class AgentInvalidInputError(AgentError):
    def __init__(self, message: str):
        super().__init__("AGENT_INVALID_INPUT", message, retryable=False)
```

### 16.3 错误处理流程

```python
async def safe_execute(agent, input_data: dict) -> AgentResult:
    """安全的 Agent 执行（带完整错误处理）"""
    
    try:
        result = await agent.run(input_data)
        
        if not result.success:
            # 记录业务错误
            logger.warning(
                f"Agent {agent.agent_id} 业务失败: {result.error}"
            )
        
        return result
        
    except AgentTimeoutError as e:
        logger.error(f"Agent {agent.agent_id} 超时: {e}")
        return AgentResult(
            agent_id=agent.agent_id,
            success=False,
            error=f"超时: {e.message}"
        )
        
    except AgentRateLimitError as e:
        logger.warning(f"Agent {agent.agent_id} 限流: {e}")
        # 退避重试
        await asyncio.sleep(5)
        return await agent.run(input_data)
        
    except AgentJsonParseError as e:
        logger.error(f"Agent {agent.agent_id} JSON 解析失败: {e}")
        # 重新请求（带格式提示）
        input_data["force_json_format"] = True
        return await agent.run(input_data)
        
    except ModelUnavailableError as e:
        logger.error(f"Agent {agent.agent_id} 模型不可用: {e}")
        # 切换备用模型
        return await agent.run({**input_data, "model": "gpt-4.1-mini"})
        
    except Exception as e:
        logger.exception(f"Agent {agent.agent_id} 未知错误: {e}")
        return AgentResult(
            agent_id=agent.agent_id,
            success=False,
            error=f"未知错误: {e}"
        )
```

### 16.4 重试策略

```python
# backend/agents/retry.py
import asyncio
from typing import Type, Tuple

class RetryPolicy:
    """重试策略"""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 2.0,
        max_delay: float = 30.0,
        backoff: str = "exponential",
        retryable_errors: Tuple[Type[Exception], ...] = (Exception,)
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff = backoff
        self.retryable_errors = retryable_errors
    
    async def execute(self, func, *args, **kwargs):
        """执行带重试的函数"""
        last_error = None
        
        for attempt in range(self.max_attempts):
            try:
                return await func(*args, **kwargs)
            except self.retryable_errors as e:
                last_error = e
                if attempt < self.max_attempts - 1:
                    delay = self._calculate_delay(attempt)
                    logger.info(f"第 {attempt + 1} 次重试，{delay}s 后执行")
                    await asyncio.sleep(delay)
        
        raise last_error
    
    def _calculate_delay(self, attempt: int) -> float:
        """计算退避延迟"""
        if self.backoff == "exponential":
            delay = self.base_delay * (2 ** attempt)
        elif self.backoff == "linear":
            delay = self.base_delay * (attempt + 1)
        else:  # fixed
            delay = self.base_delay
        
        return min(delay, self.max_delay)

# 默认重试策略
DEFAULT_RETRY_POLICY = RetryPolicy(
    max_attempts=3,
    base_delay=2.0,
    max_delay=30.0,
    backoff="exponential",
    retryable_errors=(AgentTimeoutError, AgentRateLimitError, AgentJsonParseError)
)
```

---

## 17. Agent 配置参考

### 17.1 全局配置

```yaml
# config/agents/orchestrator.yaml
agent_id: orchestrator
model: claude-sonnet-4.5
temperature: 0.3
max_tokens: 4096

# 五阶段配置
stages:
  info_confirm:
    require_user_confirm: true
    min_info_fields:
      - discipline
      - degree
      - direction
  
  creativity:
    min_candidates: 3
    max_candidates: 5
    require_all_dimensions: true
  
  validation:
    min_score: 60
    max_retries: 2
    fallback: mark_warning
  
  generation:
    report_generated: true
    style_normalizer_applied: true
    fallback: template_mode
  
  deep_assist:
    require_menu_render: true
    require_user_end: true
    loop: true

# 重试配置
retry:
  max_attempts: 3
  base_delay: 2.0
  max_delay: 30.0
  backoff: exponential
  retryable_errors:
    - AGENT_TIMEOUT
    - AGENT_RATE_LIMIT
    - AGENT_JSON_PARSE
    - MODEL_UNAVAILABLE

# 兜底降级配置
fallback:
  strategy: fallback_proposal
  confidence_score: 0.4
  cascade:
    - searcher: mock_searcher
    - reasoner: fallback_proposal
    - critic: mark_warning
    - mentor: skip_mentor
    - writer: template_mode

# 上下文配置
context:
  max_history_rounds: 5
  recent_history_rounds: 2
  dst_compression_threshold: 5
  context_overflow_threshold: 0.8

# 缓存配置
cache:
  enabled: true
  prefix_version: v8.0.1
  warmup_on_session_create: true
  target_hit_rate: 0.95

# 可观测性
observability:
  log_level: INFO
  record_tokens: true
  record_duration: true
  record_cache_stats: true
```

### 17.2 各 Agent 配置对比

| 配置项 | Orchestrator | Searcher | Reasoner | Critic | Mentor | Writer |
|--------|--------------|----------|----------|--------|--------|--------|
| model | claude-sonnet-4.5 | deepseek-v3.2 | deepseek-r2 | deepseek-r2 | gpt-4.1 | claude-opus-4.5 |
| temperature | 0.3 | 0.3 | 0.8 | 0.2 | 0.4 | 0.6 |
| max_tokens | 4096 | 2048 | 4096 | 4096 | 2048 | 8192 |
| capabilities | streaming,thinking,web_search | web_search | thinking | thinking | - | streaming |
| retry_max | 3 | 3 | 3 | 2 | 2 | 3 |
| fallback | fallback_proposal | mock_searcher | fallback_proposal | mark_warning | skip_mentor | template_mode |
| cache_enabled | true | true | true | true | true | true |

### 17.3 模型路由配置

```yaml
# config/agents/model_routing.yaml
routing:
  # 全局默认模型
  default_model: gpt-4.1-mini
  
  # 各 Agent 默认模型
  agent_models:
    orchestrator: claude-sonnet-4.5
    searcher: deepseek-v3.2
    reasoner: deepseek-r2
    critic: deepseek-r2
    mentor: gpt-4.1
    writer: claude-opus-4.5
  
  # 按用途路由（覆盖 agent_models）
  step_models:
    orchestrator:
      confirm: claude-sonnet-4.5
      compress: gpt-4.1-mini
      fallback: gpt-4.1-mini
    
    searcher:
      search: deepseek-v3.2
      novelty_check: deepseek-v3.2
    
    reasoner:
      creativity: deepseek-r2
      fallback: gpt-4.1-mini
    
    critic:
      evaluate: deepseek-r2
      arbitrate: claude-opus-4.5
    
    mentor:
      review: gpt-4.1
      batch_review: gpt-4.1
    
    writer:
      generate_title: claude-opus-4.5
      generate_abstract: claude-opus-4.5
      generate_outline: claude-opus-4.5
      generate_full: claude-opus-4.5
  
  # 备用模型（主模型不可用时）
  fallback_models:
    - gpt-4.1-mini
    - deepseek-v3.2
    - qwen3-max
```

### 17.4 上下文管理配置

```yaml
# config/agents/context.yaml
context:
  # 全局上下文配置
  global:
    max_history_rounds: 5          # 最大保留轮数
    recent_history_rounds: 2       # 最近完整保留的轮数
    compression_threshold: 5       # 触发压缩的轮数阈值
    overflow_threshold: 0.8        # 上下文溢出阈值（占 max_tokens 比例）
  
  # 各 Agent 上下文配置（覆盖 global）
  agents:
    orchestrator:
      max_history_rounds: 10       # Orchestrator 需要更多历史
      recent_history_rounds: 3
      compression_strategy: summary  # summary / truncate / hybrid
    
    searcher:
      max_history_rounds: 3        # Searcher 不需要太多历史
      recent_history_rounds: 1
      compression_strategy: truncate
    
    reasoner:
      max_history_rounds: 5
      recent_history_rounds: 2
      compression_strategy: summary
    
    critic:
      max_history_rounds: 5
      recent_history_rounds: 2
      compression_strategy: summary
    
    mentor:
      max_history_rounds: 3
      recent_history_rounds: 1
      compression_strategy: truncate
    
    writer:
      max_history_rounds: 3
      recent_history_rounds: 1
      compression_strategy: truncate
```

### 17.5 缓存配置

```yaml
# config/agents/cache.yaml
cache:
  # 全局缓存配置
  global:
    enabled: true
    prefix_version: v8.0.1
    target_hit_rate: 0.95
    warmup_on_session_create: true
  
  # DeepSeek 模型特殊配置（支持 prompt caching）
  deepseek:
    enabled: true
    cache_tokens_threshold: 1024   # 超过 1024 token 才缓存
    max_cache_tokens: 16384        # 最大缓存 token
    ttl: 3600                      # 缓存 TTL（秒）
  
  # 各 Agent 缓存策略
  agents:
    orchestrator:
      cache_system_prompt: true
      cache_user_info: true
      cache_history: false         # 历史不缓存（动态变化）
    
    searcher:
      cache_system_prompt: true
      cache_query_template: true   # 查询模板缓存
    
    reasoner:
      cache_system_prompt: true
      cache_dimension_prompts: true  # 四维 prompt 缓存
    
    critic:
      cache_system_prompt: true
      cache_evaluation_rubric: true  # 评估标准缓存
    
    mentor:
      cache_system_prompt: true
    
    writer:
      cache_system_prompt: true
      cache_style_guide: true       # 风格指南缓存
```

---

## 18. 附录

### 18.1 Agent 速查表

```
┌─────────────────────────────────────────────────────────────────┐
│                    Agent 速查表                                  │
├──────────────┬──────────────────┬─────────────┬────────────────┤
│ Agent ID     │ 职责             │ 默认模型    │ 关键方法       │
├──────────────┼──────────────────┼─────────────┼────────────────┤
│ orchestrator │ 五阶段调度       │ claude-     │ orchestrate()  │
│              │                  │ sonnet-4.5  │ confirm_info() │
│              │                  │             │ reset()        │
├──────────────┼──────────────────┼─────────────┼────────────────┤
│ searcher     │ 文献检索         │ deepseek-   │ run()          │
│              │ 新颖性检查       │ v3.2        │ check_novelty()│
├──────────────┼──────────────────┼─────────────┼────────────────┤
│ reasoner     │ 四维创意生成     │ deepseek-r2 │ run()          │
│              │                  │             │ _parse_        │
│              │                  │             │   candidates() │
├──────────────┼──────────────────┼─────────────┼────────────────┤
│ critic       │ 候选评估         │ deepseek-r2 │ run()          │
│              │ 阈值门控         │             │ _parse_        │
│              │                  │             │   evaluations()│
├──────────────┼──────────────────┼─────────────┼────────────────┤
│ mentor       │ 导师视角评审     │ gpt-4.1     │ review_        │
│              │                  │             │   proposal()   │
│              │                  │             │ batch_review() │
│              │                  │             │ fallback_      │
│              │                  │             │   review()     │
├──────────────┼──────────────────┼─────────────┼────────────────┤
│ writer       │ 多粒度生成       │ claude-     │ run()          │
│              │ (title/abstract/ │ opus-4.5    │ generate_      │
│              │  outline/full)   │             │   report()     │
└──────────────┴──────────────────┴─────────────┴────────────────┘
```

### 18.2 常用代码片段

#### 18.2.1 获取 Agent 单例

```python
from backend.agents.agent_registry import get_agent

# 获取各 Agent
orchestrator = get_agent("orchestrator")
searcher = get_agent("searcher")
reasoner = get_agent("reasoner")
critic = get_agent("critic")
mentor = get_agent("mentor")
writer = get_agent("writer")
```

#### 18.2.2 执行单个 Agent

```python
import asyncio
from backend.agents.agent_registry import get_agent

async def run_searcher():
    searcher = get_agent("searcher")
    result = await searcher.run({
        "query": "大语言模型",
        "top_k": 10
    })
    return result

result = asyncio.run(run_searcher())
```

#### 18.2.3 执行完整流程

```python
import asyncio
from backend.agents.agent_registry import get_agent

async def run_full_pipeline():
    orchestrator = get_agent("orchestrator")
    
    async for event in orchestrator.orchestrate("我想写一篇关于 LLM 的硕士论文"):
        if event["type"] == "stage_complete":
            print(f"✓ {event['stage']} 完成")
        elif event["type"] == "stage_fallback":
            print(f"✗ {event['stage']} 兜底降级")

asyncio.run(run_full_pipeline())
```

#### 18.2.4 重置所有 Agent 上下文

```python
from backend.agents.agent_registry import reset_all_contexts

# 在新会话开始时调用
reset_all_contexts()
```

### 18.3 调试技巧

#### 18.3.1 启用调试日志

```python
import logging

# 启用 Agent 调试日志
logging.getLogger("backend.agents").setLevel(logging.DEBUG)

# 启用 AI Proxy 调试日志
logging.getLogger("backend.ai").setLevel(logging.DEBUG)

# 启用 Orchestrator 调试日志
logging.getLogger("backend.agents.orchestrator").setLevel(logging.DEBUG)
```

#### 18.3.2 查看 Agent 上下文

```python
from backend.agents.agent_registry import get_agent

searcher = get_agent("searcher")

# 查看上下文
print(f"消息数: {len(searcher.messages)}")
for msg in searcher.messages:
    print(f"[{msg['role']}] {msg['content'][:100]}...")

# 查看模型配置
print(f"模型: {searcher.get_model()}")
print(f"温度: {searcher.default_temperature}")
```

#### 18.3.3 模拟 Agent 失败

```python
from unittest.mock import AsyncMock, patch
from backend.agents.base_agent import AgentResult

# 模拟 Searcher 失败
with patch("backend.agents.searcher_wrapper.SearcherAgent.run") as mock_run:
    mock_run.return_value = AgentResult(
        agent_id="searcher",
        success=False,
        error="模拟失败"
    )
    
    # 测试兜底逻辑
    orchestrator = get_agent("orchestrator")
    async for event in orchestrator.orchestrate("测试"):
        if event["type"] == "stage_fallback":
            print(f"兜底触发: {event['fallback']}")
```

### 18.4 上下文管理详解

#### 18.4.1 上下文生命周期

```
[会话开始]
    │
    ▼
reset_all_contexts()  ← 清空所有 Agent 的 messages
    │
    ▼
[阶段 1: info_confirm]
    │
    │  Orchestrator.messages += [user, assistant]
    │
    ▼
[阶段 2: creativity]
    │
    │  Searcher.messages += [user, assistant]
    │  Reasoner.messages += [user, assistant]
    │
    ▼
[阶段 3: validation]
    │
    │  Critic.messages += [user, assistant]
    │  (Searcher 已有历史，可复用)
    │
    ▼
[阶段 4: generation]
    │
    │  Writer.messages += [user, assistant]
    │  Mentor.messages += [user, assistant]
    │
    ▼
[阶段 5: deep_assist]
    │
    │  Orchestrator.messages += [user, assistant]  (循环)
    │
    ▼
[会话结束]
    │
    ▼
reset_all_contexts()  ← 清空所有 Agent 的 messages
```

#### 18.4.2 上下文压缩算法

```python
def compress_context(messages: list, config: dict) -> list:
    """上下文压缩算法"""
    max_rounds = config.get("max_history_rounds", 5)
    recent_rounds = config.get("recent_history_rounds", 2)
    strategy = config.get("compression_strategy", "summary")
    
    # 计算当前轮数
    total_rounds = (len(messages) - 1) // 2  # 减去 system
    
    if total_rounds <= max_rounds:
        return messages  # 不需要压缩
    
    # 分割消息
    system = messages[0]
    history = messages[1:-(recent_rounds * 2)]
    recent = messages[-(recent_rounds * 2):]
    
    if strategy == "truncate":
        # 截断：直接丢弃历史
        return [system] + recent
    
    elif strategy == "summary":
        # 摘要：用 LLM 压缩历史
        summary = asyncio.run(summarize_history(history))
        return [
            system,
            {"role": "system", "content": f"历史摘要: {summary}"},
            *recent
        ]
    
    elif strategy == "hybrid":
        # 混合：保留关键信息 + 摘要
        key_points = extract_key_points(history)
        summary = asyncio.run(summarize_history(history))
        return [
            system,
            {"role": "system", "content": f"关键信息: {key_points}\n历史摘要: {summary}"},
            *recent
        ]
    
    return messages

async def summarize_history(history: list) -> str:
    """用 LLM 摘要历史对话"""
    from backend.ai.ai_proxy import call_llm
    
    history_text = "\n".join([
        f"[{m['role']}]: {m['content'][:200]}"
        for m in history
    ])
    
    response = await call_llm(
        model="gpt-4.1-mini",  # 用便宜模型摘要
        messages=[{
            "role": "user",
            "content": f"请摘要以下对话（200字以内）:\n{history_text}"
        }],
        temperature=0.1,
        max_tokens=300
    )
    
    return response.content
```

### 18.5 模型路由详解

#### 18.5.1 路由优先级

```
┌─────────────────────────────────────────────────────────────────┐
│                    模型路由优先级                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. 显式指定的 model 参数（最高优先级）                          │
│     ↓                                                           │
│  2. step_models[agent_id][purpose] 配置                         │
│     ↓                                                           │
│  3. agent_models[agent_id] 配置                                 │
│     ↓                                                           │
│  4. models[0].id（配置文件中的第一个模型）                       │
│     ↓                                                           │
│  5. ai_model 环境变量（最低优先级）                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 18.5.2 路由示例

```python
# 示例 1: 显式指定模型
result = await searcher.run({
    "query": "LLM",
    "model": "gpt-4.1"  # 优先级 1，覆盖所有配置
})

# 示例 2: 通过 purpose 路由
model = searcher.get_model("novelty_check")
# 返回 step_models["searcher"]["novelty_check"] = "deepseek-v3.2"

# 示例 3: 默认路由
model = searcher.get_model()
# 返回 agent_models["searcher"] = "deepseek-v3.2"

# 示例 4: 全局默认
model = base_agent.get_model()
# 如果未配置 agent_models，返回 models[0].id
```

### 18.6 可观测性

#### 18.6.1 日志结构

```python
# Agent 执行日志结构
{
    "timestamp": "2026-06-20T10:30:00Z",
    "level": "INFO",
    "agent_id": "searcher",
    "session_id": "sess_123",
    "stage": "creativity",
    "event": "agent_start",
    "input": {
        "query": "大语言模型",
        "top_k": 10
    },
    "model": "deepseek-v3.2",
    "tokens": {
        "prompt": 1250,
        "completion": 800,
        "total": 2050,
        "cache_hit": 1180
    },
    "duration_ms": 2300,
    "success": true
}
```

#### 18.6.2 指标收集

```python
# backend/observability/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Agent 执行次数
agent_executions = Counter(
    "thesisminer_agent_executions_total",
    "Agent 执行总次数",
    ["agent_id", "status"]
)

# Agent 执行耗时
agent_duration = Histogram(
    "thesisminer_agent_duration_seconds",
    "Agent 执行耗时（秒）",
    ["agent_id"],
    buckets=[0.5, 1, 2, 5, 10, 30, 60]
)

# Agent token 消耗
agent_tokens = Counter(
    "thesisminer_agent_tokens_total",
    "Agent token 消耗",
    ["agent_id", "type"]  # type: prompt/completion/cache_hit
)

# 缓存命中率
cache_hit_rate = Gauge(
    "thesisminer_cache_hit_rate",
    "Prompt 缓存命中率",
    ["agent_id"]
)

# 当前活跃 Agent 数
active_agents = Gauge(
    "thesisminer_active_agents",
    "当前活跃 Agent 数"
)
```

#### 18.6.3 分布式追踪

```python
# backend/observability/tracing.py
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

async def traced_agent_run(agent, input_data: dict):
    """带追踪的 Agent 执行"""
    with tracer.start_as_current_span(f"agent.{agent.agent_id}.run") as span:
        span.set_attribute("agent.id", agent.agent_id)
        span.set_attribute("agent.model", agent.get_model())
        span.set_attribute("agent.input_size", len(str(input_data)))
        
        try:
            result = await agent.run(input_data)
            
            span.set_attribute("agent.success", result.success)
            span.set_attribute("agent.tokens", result.token_usage.get("total_tokens", 0))
            
            return result
            
        except Exception as e:
            span.record_exception(e)
            span.set_attribute("agent.error", str(e))
            raise
```

### 18.7 测试指南

#### 18.7.1 单元测试

```python
# tests/test_searcher_agent.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.agents.searcher_wrapper import SearcherAgent, MockSearcher, RealSearcher
from backend.agents.base_agent import AgentResult

@pytest.fixture
def searcher_agent():
    return SearcherAgent(mode="mock")

@pytest.mark.asyncio
async def test_searcher_mock_mode(searcher_agent):
    """测试 Mock 模式检索"""
    result = await searcher_agent.run({
        "query": "大语言模型",
        "top_k": 5
    })
    
    assert result.success is True
    assert result.agent_id == "searcher"
    assert len(result.data["papers"]) <= 5
    assert "novelty_scores" in result.data

@pytest.mark.asyncio
async def test_searcher_empty_query(searcher_agent):
    """测试空查询"""
    result = await searcher_agent.run({
        "query": "",
        "top_k": 5
    })
    
    # 空查询应该返回空结果或错误
    assert result.success in [True, False]

@pytest.mark.asyncio
async def test_searcher_novelty_check(searcher_agent):
    """测试新颖性检查"""
    papers = [
        {"title": "Attention Is All You Need", "year": 2017},
        {"title": "BERT", "year": 2018}
    ]
    
    scores = await searcher_agent.check_novelty("大语言模型", papers)
    
    assert len(scores) == 2
    for score in scores:
        assert "similarity" in score
        assert "novelty_score" in score
        assert "risk_level" in score
        assert 0 <= score["similarity"] <= 1
        assert 0 <= score["novelty_score"] <= 1

def test_levenshtein_distance(searcher_agent):
    """测试 Levenshtein 距离计算"""
    # 相同字符串
    assert searcher_agent._levenshtein_distance("hello", "hello") == 0
    
    # 单字符差异
    assert searcher_agent._levenshtein_distance("hello", "hallo") == 1
    
    # 完全不同
    assert searcher_agent._levenshtein_distance("abc", "xyz") == 3

def test_calculate_similarity(searcher_agent):
    """测试相似度计算"""
    # 相同字符串
    assert searcher_agent._calculate_similarity("hello", "hello") == 1.0
    
    # 完全不同
    assert searcher_agent._calculate_similarity("abc", "xyz") == 0.0

def test_get_risk_level(searcher_agent):
    """测试风险等级判断"""
    assert searcher_agent._get_risk_level(0.8) == "low"
    assert searcher_agent._get_risk_level(0.5) == "medium"
    assert searcher_agent._get_risk_level(0.3) == "high"
```

#### 18.7.2 集成测试

```python
# tests/test_agent_integration.py
import pytest
from backend.agents.agent_registry import get_agent, reset_all_contexts

@pytest.fixture(autouse=True)
def reset_agents():
    """每个测试前重置 Agent"""
    reset_all_contexts()
    yield
    reset_all_contexts()

@pytest.mark.asyncio
async def test_full_pipeline():
    """测试完整流程"""
    orchestrator = get_agent("orchestrator")
    
    stages_completed = []
    
    async for event in orchestrator.orchestrate("我想写一篇关于 LLM 的硕士论文"):
        if event["type"] == "stage_complete":
            stages_completed.append(event["stage"])
    
    assert "info_confirm" in stages_completed
    # 其他阶段取决于实现

@pytest.mark.asyncio
async def test_searcher_to_reasoner():
    """测试 Searcher → Reasoner 协作"""
    searcher = get_agent("searcher")
    reasoner = get_agent("reasoner")
    
    # Searcher 检索
    searcher_result = await searcher.run({
        "query": "大语言模型",
        "top_k": 10
    })
    
    assert searcher_result.success
    
    # Reasoner 生成候选（携带文献）
    reasoner_result = await reasoner.run({
        "info": {
            "discipline": "计算机科学",
            "degree": "硕士",
            "direction": "大语言模型"
        },
        "literature": searcher_result.data["papers"]
    })
    
    assert reasoner_result.success
    assert len(reasoner_result.data["candidates"]) >= 3
```

#### 18.7.3 Mock 测试

```python
# tests/test_with_mocks.py
import pytest
from unittest.mock import AsyncMock, patch
from backend.agents.base_agent import AgentResult
from backend.agents.agent_registry import get_agent

@pytest.mark.asyncio
async def test_orchestrator_with_mock_searcher():
    """使用 Mock 测试 Orchestrator"""
    orchestrator = get_agent("orchestrator")
    
    # Mock Searcher
    mock_searcher = AsyncMock()
    mock_searcher.run.return_value = AgentResult(
        agent_id="searcher",
        success=True,
        data={
            "papers": [
                {"title": "Test Paper", "year": 2025}
            ]
        }
    )
    
    with patch("backend.agents.agent_registry.get_agent", return_value=mock_searcher):
        async for event in orchestrator.orchestrate("测试"):
            if event["type"] == "stage_complete":
                assert event["stage"] in ["info_confirm", "creativity"]

@pytest.mark.asyncio
async def test_fallback_on_failure():
    """测试失败时的兜底降级"""
    searcher = get_agent("searcher")
    
    # Mock RealSearcher 失败
    with patch.object(searcher.real_searcher, "search", side_effect=Exception("API 错误")):
        result = await searcher.run({"query": "测试"})
        
        # 应该使用 MockSearcher 兜底
        assert result.success is True
        assert result.data.get("fallback") is True
```

### 18.8 常见问题

#### Q1: Agent 上下文如何隔离？

**A**: 每个 Agent 维护独立的 `messages` 列表，互不影响。Orchestrator 负责在 Agent 间传递必要的数据，而不是共享上下文。

```python
# 各 Agent 上下文独立
orchestrator.messages = [...]  # Orchestrator 的上下文
searcher.messages = [...]      # Searcher 的上下文（独立）
reasoner.messages = [...]      # Reasoner 的上下文（独立）
```

#### Q2: 如何切换 Agent 使用的模型？

**A**: 三种方式：

```python
# 方式 1: 修改配置文件
# config/agents/searcher.yaml
model: gpt-4.1  # 修改默认模型

# 方式 2: 运行时指定
result = await searcher.run({
    "query": "LLM",
    "model": "gpt-4.1"  # 临时指定
})

# 方式 3: 通过 API 修改
# POST /api/config/models
```

#### Q3: Agent 失败后如何恢复？

**A**: Orchestrator 有完整的重试和兜底机制：

1. **重试**：失败后按指数退避重试（最多 3 次）
2. **兜底**：重试失败后使用兜底方案（如 MockSearcher）
3. **降级**：兜底也失败则降级到模板模式

#### Q4: 如何添加新的 Agent？

**A**: 参见第 14 节"自定义 Agent 开发"，步骤：

1. 创建 Agent 类（继承 BaseAgent）
2. 实现 `run()` 方法
3. 注册到 AGENT_REGISTRY
4. 添加配置文件
5. 编写测试

#### Q5: Prompt 缓存如何工作？

**A**: ThesisMiner v8.0 使用三段式 Prompt 缓存：

```
[Cached Prefix]  ← 缓存（system prompt + 用户信息）
[User Message]   ← 不缓存（动态变化）
[Assistant]      ← 不缓存
```

DeepSeek 模型支持 prompt caching，缓存命中率 ≥95%，可节省约 80% 的 token 成本。

### 18.9 Agent 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v8.0.0 | 2026-06-20 | 初始版本，支持 6 个 Agent |
| v7.5.0 | 2026-05-15 | 添加 Mentor Agent |
| v7.0.0 | 2026-04-01 | 重构为 BaseAgent 架构 |
| v6.0.0 | 2026-02-10 | 添加五阶段闭环流程 |
| v5.0.0 | 2026-01-05 | 初始多 Agent 架构 |

### 18.10 相关文档

- [约束规则参考](constraint_reference.md)
- [API 参考](api_reference.md)
- [配置参考](configuration_reference.md)
- [故障排查参考](troubleshooting_reference.md)
- [Agent 架构设计](../architecture/agent_architecture.md)
- [五阶段流程设计](../architecture/five_stage_flow.md)
- [缓存策略设计](../architecture/cache_strategy.md)
- [Prompt 模板](../constraints/prompt_templates/)

### 18.11 术语表

| 术语 | 英文 | 含义 |
|------|------|------|
| Agent | Agent | 智能体，执行特定任务的 AI 模块 |
| Orchestrator | Orchestrator | 主管理 Agent，负责调度 |
| BaseAgent | Base Agent | 所有 Agent 的抽象基类 |
| AgentResult | Agent Result | Agent 执行结果的标准数据结构 |
| Stage Gate | Stage Gate | 阶段门控，控制流程流转 |
| Model Routing | Model Routing | 模型路由，根据用途选择模型 |
| Fallback | Fallback | 兜底降级，失败时的备用方案 |
| Prompt Cache | Prompt Cache | Prompt 缓存，提高效率降低成本 |
| Context | Context | 上下文，Agent 维护的对话历史 |
| Novelty Check | Novelty Check | 新颖性检查，评估选题与已有文献的相似度 |
| Granularity | Granularity | 粒度，生成的详细程度（title/abstract/outline/full） |
| Levenshtein Distance | Levenshtein Distance | 编辑距离，衡量字符串相似度 |
| Token Usage | Token Usage | Token 消耗统计 |
| Cache Hit Rate | Cache Hit Rate | 缓存命中率 |
| Retry Policy | Retry Policy | 重试策略 |
| Backoff | Backoff | 退避策略（指数退避） |

### 18.12 Agent 通信时序详解

#### 18.12.1 完整五阶段时序

```
用户          Orchestrator      Searcher      Reasoner      Critic       Writer      Mentor
 │                │                │             │            │             │           │
 │──输入─────────▶│                │             │            │             │           │
 │                │                │             │            │             │           │
 │  [阶段1: info_confirm]         │             │            │             │           │
 │                │                │             │            │             │           │
 │◀──追问─────────│                │             │            │             │           │
 │──补充─────────▶│                │             │            │             │           │
 │◀──确认─────────│                │             │            │             │           │
 │                │                │             │            │             │           │
 │  [阶段2: creativity]           │             │            │             │           │
 │                │                │             │            │             │           │
 │                │──检索─────────▶│             │            │             │           │
 │                │◀──论文列表─────│             │            │             │           │
 │                │                │             │            │             │           │
 │                │──生成候选───────────────────▶│            │             │           │
 │                │◀──候选列表───────────────────│            │             │           │
 │                │                │             │            │             │           │
 │  [阶段3: validation]            │             │            │             │           │
 │                │                │             │            │             │           │
 │                │──新颖性检查───▶│             │            │             │           │
 │                │◀──新颖性分数───│             │            │             │           │
 │                │                │             │            │             │           │
 │                │──评估候选───────────────────────────────▶│             │           │
 │                │◀──评估结果───────────────────────────────│             │           │
 │                │                │             │            │             │           │
 │  [阶段4: generation]            │             │            │             │           │
 │                │                │             │            │             │           │
 │                │──生成报告────────────────────────────────────────────▶│           │
 │                │◀──完整报告────────────────────────────────────────────│           │
 │                │                │             │            │             │           │
 │                │──导师评审───────────────────────────────────────────────────────▶│
 │                │◀──评审意见───────────────────────────────────────────────────────│
 │                │                │             │            │             │           │
 │  [阶段5: deep_assist]           │             │            │             │           │
 │                │                │             │            │             │           │
 │◀──深度辅助─────│                │             │            │             │           │
 │──追问─────────▶│                │             │            │             │           │
 │◀──回复─────────│                │             │            │             │           │
 │──结束─────────▶│                │             │            │             │           │
 │                │                │             │            │             │           │
 │◀──最终结果─────│                │             │            │             │           │
```

#### 18.12.2 失败兜底时序

```
用户          Orchestrator      Searcher      Reasoner
 │                │                │             │
 │──输入─────────▶│                │             │
 │                │                │             │
 │                │──检索─────────▶│             │
 │                │  ✗ 失败        │             │
 │                │                │             │
 │                │──重试1────────▶│             │
 │                │  ✗ 失败        │             │
 │                │                │             │
 │                │──重试2────────▶│             │
 │                │  ✗ 失败        │             │
 │                │                │             │
 │                │──兜底(Mock)───▶│             │
 │                │◀──Mock结果─────│             │
 │                │                │             │
 │                │──生成候选───────────────────▶│
 │                │◀──候选列表───────────────────│
 │                │                │             │
 │◀──结果(带警告)─│                │             │
```

### 18.13 Agent 扩展示例：PlannerAgent

```python
# backend/agents/planner_agent.py
"""规划 Agent：生成研究计划"""
from typing import List, Dict
from backend.agents.base_agent import BaseAgent, AgentResult
from backend.ai.ai_proxy import call_llm

class PlannerAgent(BaseAgent):
    """规划 Agent：根据选题生成研究计划"""
    
    agent_id = "planner"
    default_model = "gpt-4.1"
    default_temperature = 0.4
    default_max_tokens = 4096
    
    async def run(self, input_data: dict) -> AgentResult:
        topic = input_data.get("topic", {})
        timeline = input_data.get("timeline", {})  # {"start": "2026-09", "end": "2027-06"}
        
        # 1. 参数校验
        if not topic.get("title"):
            return AgentResult(
                agent_id=self.agent_id,
                success=False,
                error="缺少选题标题"
            )
        
        # 2. 构建规划 prompt
        prompt = self._build_planning_prompt(topic, timeline)
        
        # 3. 调用 LLM
        try:
            response = await call_llm(
                model=self.get_model(),
                messages=[{"role": "user", "content": prompt}],
                temperature=self.default_temperature,
                max_tokens=self.default_max_tokens
            )
            
            # 4. 解析计划
            plan = self._parse_plan(response.content)
            
            return AgentResult(
                agent_id=self.agent_id,
                success=True,
                content=response.content,
                data={"plan": plan},
                token_usage=response.token_usage
            )
            
        except Exception as e:
            # 5. 兜底：生成模板计划
            plan = self._fallback_plan(topic, timeline)
            return AgentResult(
                agent_id=self.agent_id,
                success=True,
                data={"plan": plan, "fallback": True},
                error=str(e)
            )
    
    def _build_planning_prompt(self, topic: dict, timeline: dict) -> str:
        return f"""请基于以下信息生成详细的研究计划：

选题: {topic.get('title', '')}
摘要: {topic.get('abstract', '')}
学位: {topic.get('degree', '')}
时间: {timeline.get('start', '')} - {timeline.get('end', '')}

要求:
1. 分阶段规划（文献调研、方法研究、实验、写作、修改）
2. 每阶段包含：目标、任务、时间、里程碑
3. 考虑风险点和应对措施

输出格式:
```json
{{
  "phases": [
    {{
      "name": "文献调研",
      "start": "2026-09",
      "end": "2026-11",
      "goals": ["目标1", "目标2"],
      "tasks": ["任务1", "任务2"],
      "milestones": ["里程碑1"],
      "risks": ["风险1"]
    }}
  ]
}}
```
"""
    
    def _parse_plan(self, content: str) -> dict:
        """解析计划"""
        import json
        import re
        
        pattern = r"```json\s*(.*?)\s*```"
        match = re.search(pattern, content, re.DOTALL)
        
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        
        return {"raw_content": content}
    
    def _fallback_plan(self, topic: dict, timeline: dict) -> dict:
        """兜底计划"""
        return {
            "phases": [
                {
                    "name": "文献调研",
                    "start": timeline.get("start", ""),
                    "end": "阶段1结束",
                    "goals": ["梳理相关文献"],
                    "tasks": ["检索论文", "阅读总结"],
                    "milestones": ["文献综述初稿"],
                    "risks": ["文献过多"]
                },
                {
                    "name": "方法研究",
                    "start": "阶段2开始",
                    "end": "阶段2结束",
                    "goals": ["确定研究方法"],
                    "tasks": ["方法选型", "技术验证"],
                    "milestones": ["方法确定"],
                    "risks": ["方法不可行"]
                }
            ],
            "fallback": True
        }
```

### 18.14 性能调优指南

#### 18.14.1 减少延迟

```python
# 1. 并行化独立任务
async def parallel_pipeline():
    """并行执行独立的 Agent"""
    tasks = [
        searcher.run({"query": "LLM"}),
        mentor.run({"proposal": {"title": "预设选题"}})  # 不依赖 Searcher
    ]
    results = await asyncio.gather(*tasks)
    return results

# 2. 使用流式输出
async def stream_writer():
    """Writer 流式输出"""
    writer = get_agent("writer")
    async for chunk in writer.run_stream({"topic": {...}}):
        yield chunk  # 实时输出

# 3. 缓存阶段结果
async def cached_pipeline():
    """缓存阶段结果，避免重复计算"""
    orchestrator = get_agent("orchestrator")
    
    # 如果阶段已缓存，跳过
    if "creativity" in orchestrator.stage_results:
        return orchestrator.stage_results["creativity"]
    
    # 否则执行
    result = await reasoner.run({...})
    orchestrator.stage_results["creativity"] = result
    return result
```

#### 18.14.2 降低成本

```python
# 1. 使用便宜模型做简单任务
async def cheap_search():
    """用便宜模型做检索"""
    return await searcher.run({
        "query": "LLM",
        "model": "gpt-4.1-mini"  # 而不是 deepseek-v3.2
    })

# 2. 启用 Prompt 缓存
from backend.ai.prompt_cache import build_cached_prefix

cached_prefix = build_cached_prefix(
    system_prompt="你是 Searcher Agent...",
    user_info={"discipline": "CS"}
)
# 缓存命中后，token 成本降低 80%

# 3. 压缩上下文
def compress_if_needed(messages: list) -> list:
    """超过阈值时压缩"""
    if len(messages) > 10:
        return compress_context(messages, {"strategy": "summary"})
    return messages
```

### 18.15 安全注意事项

#### 18.15.1 输入校验

```python
from backend.security.input_validator import validate_input

async def safe_agent_run(agent, input_data: dict) -> AgentResult:
    """带输入校验的 Agent 执行"""
    
    # 1. 校验输入
    try:
        validated = validate_input(input_data, agent.agent_id)
    except ValidationError as e:
        return AgentResult(
            agent_id=agent.agent_id,
            success=False,
            error=f"输入校验失败: {e}"
        )
    
    # 2. 限制输入大小
    if len(str(validated)) > 10000:
        return AgentResult(
            agent_id=agent.agent_id,
            success=False,
            error="输入过大"
        )
    
    # 3. 执行 Agent
    return await agent.run(validated)
```

#### 18.15.2 敏感信息过滤

```python
def filter_sensitive_info(content: str) -> str:
    """过滤敏感信息"""
    import re
    
    # 过滤手机号
    content = re.sub(r"1[3-9]\d{9}", "***-****-****", content)
    
    # 过滤邮箱
    content = re.sub(r"[\w.-]+@[\w.-]+", "***@***.***", content)
    
    # 过滤身份证号
    content = re.sub(r"\d{17}[\dXx]", "*******************", content)
    
    return content
```

### 18.16 部署注意事项

#### 18.16.1 生产环境配置

```yaml
# config/production/agents.yaml
agents:
  # 生产环境使用更强模型
  orchestrator:
    model: claude-sonnet-4.5
    temperature: 0.3
  
  # 启用所有缓存
  cache:
    enabled: true
    warmup_on_session_create: true
  
  # 严格的重试策略
  retry:
    max_attempts: 3
    base_delay: 2.0
    max_delay: 30.0
  
  # 启用可观测性
  observability:
    log_level: INFO
    record_tokens: true
    record_duration: true
    record_cache_stats: true
    enable_tracing: true
  
  # 限流
  rate_limiting:
    enabled: true
    max_requests_per_minute: 60
    max_concurrent: 10
```

#### 18.16.2 健康检查

```python
# backend/routes/health.py
from fastapi import APIRouter
from backend.agents.agent_registry import list_agents, get_agent

router = APIRouter()

@router.get("/health/agents")
async def agents_health():
    """Agent 健康检查"""
    agents = list_agents()
    status = {}
    
    for agent_id in agents:
        try:
            agent = get_agent(agent_id)
            status[agent_id] = {
                "healthy": True,
                "model": agent.get_model(),
                "messages_count": len(agent.messages)
            }
        except Exception as e:
            status[agent_id] = {
                "healthy": False,
                "error": str(e)
            }
    
    return {
        "total_agents": len(agents),
        "healthy_agents": sum(1 for s in status.values() if s["healthy"]),
        "agents": status
    }
```

### 18.17 总结

ThesisMiner v8.0 的多 Agent 架构通过以下设计实现了高效、可靠的选题导航：

1. **清晰的职责分离**：6 个 Agent 各司其职，通过 Orchestrator 统一调度
2. **灵活的模型路由**：根据用途选择最合适的模型，平衡成本与质量
3. **完善的错误处理**：重试 + 兜底 + 降级，确保系统健壮性
4. **高效缓存机制**：三段式 Prompt 缓存，命中率 ≥95%
5. **可观测性**：完整的日志、指标、追踪支持
6. **可扩展性**：通过 BaseAgent 抽象，轻松添加新 Agent

---

> **文档结束**
> 
> 如有疑问，请参考：
> - [故障排查参考](troubleshooting_reference.md)
> - [配置参考](configuration_reference.md)
> - [API 参考](api_reference.md)
> 
> 或提交 Issue 到项目仓库。
