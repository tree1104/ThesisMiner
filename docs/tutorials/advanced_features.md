# ThesisMiner v8.0 高级特性教程

> 本教程面向已掌握 ThesisMiner 基础用法的开发者与高级用户，将深入介绍自定义 Agent 开发、约束扩展、缓存优化、深度辅助三件套、API 集成、D3.js 谱系定制、多模型策略等高级特性。完成本教程后，你将能够根据自身需求深度定制 ThesisMiner，并将其集成到更大的科研工作流中。

---

## 目录

- [1. 教程概述](#1-教程概述)
- [2. 自定义 Agent 开发](#2-自定义-agent-开发)
  - [2.1 BaseAgent 架构解析](#21-baseagent-架构解析)
  - [2.2 实现自定义 Agent](#22-实现自定义-agent)
  - [2.3 Agent 注册与编排](#23-agent-注册与编排)
  - [2.4 前端展示自定义 Agent](#24-前端展示自定义-agent)
  - [2.5 Agent 调试技巧](#25-agent-调试技巧)
- [3. 约束系统扩展](#3-约束系统扩展)
  - [3.1 约束架构总览](#31-约束架构总览)
  - [3.2 自定义硬约束](#32-自定义硬约束)
  - [3.3 新颖性评估扩展](#33-新颖性评估扩展)
  - [3.4 风格规范化器扩展](#34-风格规范化器扩展)
  - [3.5 约束组合与优先级](#35-约束组合与优先级)
- [4. 缓存优化技巧](#4-缓存优化技巧)
  - [4.1 缓存架构原理](#41-缓存架构原理)
  - [4.2 前缀固化策略](#42-前缀固化策略)
  - [4.3 DST 压缩调优](#43-dst-压缩调优)
  - [4.4 会话切换的缓存处理](#44-会话切换的缓存处理)
  - [4.5 命中率监控与诊断](#45-命中率监控与诊断)
- [5. 深度辅助三件套实战](#5-深度辅助三件套实战)
  - [5.1 文献精读高级用法](#51-文献精读高级用法)
  - [5.2 实验预研模板定制](#52-实验预研模板定制)
  - [5.3 答辩模拟进阶](#53-答辩模拟进阶)
- [6. API 集成与 SDK 封装](#6-api-集成与-sdk-封装)
  - [6.1 REST API 高级用法](#61-rest-api-高级用法)
  - [6.2 流式 SSE 处理](#62-流式-sse-处理)
  - [6.3 Webhook 配置](#63-webhook-配置)
  - [6.4 Python SDK 封装](#64-python-sdk-封装)
- [7. D3.js 谱系图谱定制](#7-d3js-谱系图谱定制)
  - [7.1 节点样式定制](#71-节点样式定制)
  - [7.2 边类型扩展](#72-边类型扩展)
  - [7.3 布局算法切换](#73-布局算法切换)
  - [7.4 导出 SVG 与交互](#74-导出-svg-与交互)
- [8. 多模型策略](#8-多模型策略)
  - [8.1 步骤路由配置](#81-步骤路由配置)
  - [8.2 模型 A/B 测试](#82-模型-ab-测试)
  - [8.3 降级策略](#83-降级策略)
  - [8.4 成本优化](#84-成本优化)
- [9. 编排状态机与 Hook](#9-编排状态机与-hook)
  - [9.1 OrchestrationStateMachine 原理](#91-orchestrationstatemachine-原理)
  - [9.2 Hook 机制详解](#92-hook-机制详解)
  - [9.3 自定义 Hook 实现](#93-自定义-hook-实现)
- [10. 性能调优实战](#10-性能调优实战)

---

## 1. 教程概述

### 1.1 前置要求

在开始本教程前，请确保你已完成以下准备：

- 已完成入门教程，能够正常运行 ThesisMiner 并走通五阶段流程
- 熟悉 Python 3.10+ 语法，了解 async/await 异步编程
- 了解 FastAPI 基本概念（路由、依赖注入、Pydantic 模型）
- 具备基本的 JavaScript/CSS 知识（用于前端定制）
- 拥有至少一个可用的 AI 模型 API Key

### 1.2 学习目标

完成本教程后，你将能够：

1. 实现自定义 Agent 并注册到编排系统
2. 扩展约束系统，添加自定义硬约束与软约束
3. 优化缓存命中率，降低 API 成本
4. 深度使用文献精读、实验预研、答辩模拟三件套
5. 通过 REST API 与 SDK 集成 ThesisMiner 到外部系统
6. 定制 D3.js 谱系图谱的样式与布局
7. 配置多模型策略，实现 A/B 测试与降级
8. 理解编排状态机与 Hook 机制，实现自定义流程

### 1.3 教程结构

本教程采用「原理 → 示例 → 实战」的结构，每个章节先讲解架构原理，再提供代码示例，最后给出实战练习。建议按顺序学习，但各章节相对独立，也可按需查阅。

---

## 2. 自定义 Agent 开发

### 2.1 BaseAgent 架构解析

ThesisMiner v8.0 的多 Agent 架构基于 `BaseAgent` 抽象基类。所有内置 Agent（Reasoner、Mentor、Searcher、Critic）都继承自此类。

#### 2.1.1 BaseAgent 类图

```
+---------------------------+
|       BaseAgent           |
+---------------------------+
| - name: str               |
| - model: str              |
| - context: AgentContext   |
| - config: AgentConfig     |
+---------------------------+
| + run(input) -> Result   |
| + stream(input) -> Gen   |
| + reset()                |
| - _call_model()          |
| - _parse_response()      |
+---------------------------+
        ^
        |
+-------+-------+--------+--------+
|               |        |        |
+-------+   +---+---+ +--+--+ +---+---+
|Reasoner|   |Mentor | |Searcher| |Critic|
+-------+   +---+---+ +--+--+ +---+---+
                ^
                |
        +-------+-------+
        |               |
    +---+---+       +---+---+
    |Custom |       |Custom |
    |Agent A|       |Agent B|
    +-------+       +-------+
```

#### 2.1.2 BaseAgent 核心属性

```python
# backend/agents/base_agent.py（简化版）

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional
from dataclasses import dataclass, field

@dataclass
class AgentContext:
    """Agent 运行上下文"""
    session_id: str
    conversation_id: str
    stage: str                          # 当前阶段
    history: list = field(default_factory=list)  # 历史消息
    metadata: dict = field(default_factory=dict)  # 元数据

@dataclass
class AgentConfig:
    """Agent 配置"""
    model: str = "deepseek-r2"
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 60
    retry_count: int = 3

@dataclass
class AgentResult:
    """Agent 执行结果"""
    success: bool
    content: str
    metadata: dict = field(default_factory=dict)
    error: Optional[str] = None
    tokens_used: int = 0
    cost_usd: float = 0.0

class BaseAgent(ABC):
    """所有 Agent 的抽象基类"""

    def __init__(
        self,
        name: str,
        model: str,
        context: AgentContext,
        config: Optional[AgentConfig] = None
    ):
        self.name = name
        self.model = model
        self.context = context
        self.config = config or AgentConfig(model=model)

    @abstractmethod
    async def run(self, input: str) -> AgentResult:
        """执行 Agent 任务（非流式）"""
        pass

    async def stream(self, input: str) -> AsyncGenerator[str, None]:
        """执行 Agent 任务（流式），默认实现调用 run"""
        result = await self.run(input)
        yield result.content

    def reset(self):
        """重置 Agent 上下文"""
        self.context.history.clear()
        self.context.metadata.clear()

    async def _call_model(self, messages: list) -> str:
        """调用底层模型（内部方法）"""
        # 实现略，调用 httpx 与模型 API 通信
        pass

    def _parse_response(self, response: str) -> dict:
        """解析模型响应（内部方法）"""
        # 实现略，解析 JSON 或结构化输出
        pass
```

#### 2.1.3 Agent 生命周期

```
创建 Agent
    |
    v
初始化上下文 (AgentContext)
    |
    v
+-------------------+
| 接收输入          |
+-------------------+
    |
    v
+-------------------+
| 构建 Prompt       |  <-- 三段式：稳定前缀 + 动态中间 + DST 尾部
+-------------------+
    |
    v
+-------------------+
| 调用模型          |  <-- 支持 retry / fallback
+-------------------+
    |
    v
+-------------------+
| 解析响应          |
+-------------------+
    |
    v
+-------------------+
| 返回 AgentResult  |
+-------------------+
    |
    v
更新上下文 / 写入账本
```

### 2.2 实现自定义 Agent

本节将实现一个「LiteratureAgent」，用于深度分析文献并提取关键信息。

#### 2.2.1 创建 Agent 文件

在 `backend/agents/` 目录下创建 `literature_agent.py`：

```python
# backend/agents/literature_agent.py

"""文献分析 Agent - 深度分析文献并提取关键信息"""

import json
from typing import AsyncGenerator, Optional

from .base_agent import BaseAgent, AgentContext, AgentConfig, AgentResult
from ..prompts.literature import LITERATURE_SYSTEM_PROMPT, LITERATURE_USER_TEMPLATE


class LiteratureAgent(BaseAgent):
    """文献分析 Agent

    功能：
    - 提取文献的研究问题、方法、结果
    - 评估文献与当前论题的关联度
    - 生成可借鉴点与改进空间
    """

    def __init__(
        self,
        context: AgentContext,
        config: Optional[AgentConfig] = None,
        model: str = "claude-opus-4.5"
    ):
        super().__init__(
            name="LiteratureAgent",
            model=model,
            context=context,
            config=config or AgentConfig(
                model=model,
                temperature=0.3,      # 低温度，保证分析准确
                max_tokens=8192,       # 长输出
                timeout=120,           # 文献分析耗时较长
                retry_count=2
            )
        )

    async def run(self, input: str) -> AgentResult:
        """分析文献

        Args:
            input: 文献内容（摘要或全文）

        Returns:
            AgentResult: 包含分析结果
        """
        try:
            # 构建消息
            messages = self._build_messages(input)

            # 调用模型
            response = await self._call_model(messages)

            # 解析响应
            analysis = self._parse_analysis(response)

            return AgentResult(
                success=True,
                content=json.dumps(analysis, ensure_ascii=False, indent=2),
                metadata={
                    "agent": self.name,
                    "model": self.model,
                    "analysis_type": "literature"
                },
                tokens_used=analysis.get("_tokens", 0),
                cost_usd=analysis.get("_cost", 0.0)
            )

        except Exception as e:
            return AgentResult(
                success=False,
                content="",
                error=str(e),
                metadata={"agent": self.name}
            )

    async def stream(self, input: str) -> AsyncGenerator[str, None]:
        """流式分析文献"""
        messages = self._build_messages(input)

        async for chunk in self._call_model_stream(messages):
            yield chunk

    def _build_messages(self, literature: str) -> list:
        """构建消息列表（三段式 Prompt）"""
        return [
            # 稳定前缀：系统提示
            {"role": "system", "content": LITERATURE_SYSTEM_PROMPT},

            # 动态中间：用户输入
            {"role": "user", "content": LITERATURE_USER_TEMPLATE.format(
                literature=literature,
                context=self._get_context_summary()
            )},

            # DST 尾部：历史对话压缩
            {"role": "assistant", "content": self._get_dst_summary()}
        ]

    def _get_context_summary(self) -> str:
        """获取当前上下文摘要"""
        return f"当前论题：{self.context.metadata.get('topic', '未设定')}"

    def _get_dst_summary(self) -> str:
        """获取 DST 压缩摘要"""
        if not self.context.history:
            return "（无历史对话）"

        # 简化版 DST 压缩：取最近 3 轮
        recent = self.context.history[-3:]
        summary = "\n".join(
            f"{msg['role']}: {msg['content'][:200]}..."
            for msg in recent
        )
        return f"历史摘要：\n{summary}"

    def _parse_analysis(self, response: str) -> dict:
        """解析模型响应为结构化分析"""
        try:
            # 尝试解析 JSON
            if response.strip().startswith("{"):
                return json.loads(response)

            # 否则按段落解析
            sections = response.split("\n\n")
            return {
                "research_problem": sections[0] if len(sections) > 0 else "",
                "methodology": sections[1] if len(sections) > 1 else "",
                "results": sections[2] if len(sections) > 2 else "",
                "relevance": sections[3] if len(sections) > 3 else "",
                "takeaways": sections[4] if len(sections) > 4 else "",
                "limitations": sections[5] if len(sections) > 5 else "",
            }
        except json.JSONDecodeError:
            return {"raw_response": response}
```

#### 2.2.2 创建 Prompt 模板

在 `backend/prompts/literature.py` 中创建 Prompt 模板：

```python
# backend/prompts/literature.py

LITERATURE_SYSTEM_PROMPT = """你是一位学术文献分析专家。你的任务是深度分析给定的文献，并提取以下维度的信息：

1. 研究问题与动机：文献试图解决什么问题？为什么这个问题重要？
2. 方法核心创新：文献提出了什么新方法？核心创新点是什么？
3. 实验设计与结果：文献如何验证方法？主要结果是什么？
4. 与当前论题的关联：文献与用户当前的研究论题有何关联？
5. 可借鉴之处：用户可以从文献中借鉴什么？
6. 局限性与改进空间：文献有什么局限？可以如何改进？

请以 JSON 格式返回分析结果，包含以下字段：
- research_problem: 研究问题与动机
- methodology: 方法核心创新
- results: 实验设计与结果
- relevance: 与当前论题的关联（含关联度评分 0-100）
- takeaways: 可借鉴之处（列表）
- limitations: 局限性与改进空间

确保分析准确、深入、有见地。"""

LITERATURE_USER_TEMPLATE = """请分析以下文献：

{literature}

当前研究上下文：
{context}

请按照系统提示的格式返回分析结果。"""
```

#### 2.2.3 使用自定义 Agent

```python
# 使用示例
import asyncio
from backend.agents.base_agent import AgentContext, AgentConfig
from backend.agents.literature_agent import LiteratureAgent

async def main():
    # 创建上下文
    context = AgentContext(
        session_id="sess_abc123",
        conversation_id="conv_xyz789",
        stage="deep_assistance",
        metadata={"topic": "基于半监督学习的小病灶检测"}
    )

    # 创建 Agent
    agent = LiteratureAgent(context=context)

    # 分析文献
    literature = """
    Title: Semi-supervised Medical Image Segmentation with Consistency Regularization
    Abstract: Medical image segmentation suffers from limited annotated data...
    """

    result = await agent.run(literature)

    if result.success:
        print("分析结果：")
        print(result.content)
        print(f"\nToken 使用：{result.tokens_used}")
        print(f"成本：${result.cost_usd:.4f}")
    else:
        print(f"分析失败：{result.error}")

asyncio.run(main())
```

### 2.3 Agent 注册与编排

#### 2.3.1 注册到 AGENT_REGISTRY

ThesisMiner 使用全局注册表管理所有 Agent：

```python
# backend/agents/registry.py

from typing import Type, Dict
from .base_agent import BaseAgent

# 全局 Agent 注册表
AGENT_REGISTRY: Dict[str, Type[BaseAgent]] = {}

def register_agent(name: str, agent_class: Type[BaseAgent]):
    """注册 Agent 到全局注册表

    Args:
        name: Agent 名称（唯一标识）
        agent_class: Agent 类（BaseAgent 子类）
    """
    if name in AGENT_REGISTRY:
        raise ValueError(f"Agent '{name}' 已注册")
    AGENT_REGISTRY[name] = agent_class
    print(f"[AgentRegistry] 已注册 Agent: {name}")

def get_agent_class(name: str) -> Type[BaseAgent]:
    """获取已注册的 Agent 类"""
    if name not in AGENT_REGISTRY:
        raise KeyError(f"Agent '{name}' 未注册")
    return AGENT_REGISTRY[name]

def list_agents() -> list:
    """列出所有已注册的 Agent"""
    return list(AGENT_REGISTRY.keys())
```

注册自定义 Agent：

```python
# backend/agents/__init__.py

from .registry import register_agent
from .base_agent import BaseAgent
from .reasoner_agent import ReasonerAgent
from .mentor_agent import MentorAgent
from .searcher_agent import SearcherAgent
from .critic_agent import CriticAgent
from .literature_agent import LiteratureAgent  # 自定义 Agent

# 注册内置 Agent
register_agent("Reasoner", ReasonerAgent)
register_agent("Mentor", MentorAgent)
register_agent("Searcher", SearcherAgent)
register_agent("Critic", CriticAgent)

# 注册自定义 Agent
register_agent("Literature", LiteratureAgent)
```

#### 2.3.2 编排 Agent 协作

ThesisMiner 使用 `Orchestrator` 编排多个 Agent 的协作：

```python
# backend/orchestrator.py（简化版）

from typing import List
from .agents.base_agent import BaseAgent, AgentContext, AgentResult
from .agents.registry import get_agent_class

class Orchestrator:
    """Agent 编排器，管理多 Agent 协作流程"""

    def __init__(self, context: AgentContext):
        self.context = context
        self.agents: List[BaseAgent] = []
        self.results: List[AgentResult] = []

    def add_agent(self, agent_name: str, model: str = None) -> "Orchestrator":
        """添加 Agent 到编排流程"""
        agent_class = get_agent_class(agent_name)
        agent = agent_class(context=self.context, model=model or "deepseek-r2")
        self.agents.append(agent)
        return self  # 支持链式调用

    async def run_sequential(self, input: str) -> List[AgentResult]:
        """顺序执行所有 Agent（前一个的输出作为后一个的输入）"""
        current_input = input
        for agent in self.agents:
            result = await agent.run(current_input)
            self.results.append(result)
            if not result.success:
                break
            current_input = result.content  # 传递输出
        return self.results

    async def run_parallel(self, input: str) -> List[AgentResult]:
        """并行执行所有 Agent（输入相同）"""
        import asyncio
        tasks = [agent.run(input) for agent in self.agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        self.results = [r for r in results if not isinstance(r, Exception)]
        return self.results

    async def run_pipeline(self, inputs: List[str]) -> List[AgentResult]:
        """管道执行（每个 Agent 处理不同的输入）"""
        if len(inputs) != len(self.agents):
            raise ValueError("输入数量与 Agent 数量不匹配")
        import asyncio
        tasks = [agent.run(inp) for agent, inp in zip(self.agents, inputs)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        self.results = [r for r in results if not isinstance(r, Exception)]
        return self.results
```

使用编排器：

```python
# 编排示例：文献分析 + 创意生成
async def analyze_and_ideate(literature: str):
    context = AgentContext(
        session_id="sess_abc123",
        conversation_id="conv_xyz789",
        stage="deep_assistance"
    )

    orchestrator = Orchestrator(context)
    orchestrator.add_agent("Literature", model="claude-opus-4.5")
    orchestrator.add_agent("Mentor", model="claude-opus-4.5")

    # 顺序执行：先分析文献，再基于分析结果生成创意
    results = await orchestrator.run_sequential(literature)

    for i, result in enumerate(results):
        print(f"Agent {i+1} 结果：")
        print(result.content[:500])
        print()
```

### 2.4 前端展示自定义 Agent

#### 2.4.1 注册前端 Agent 信息

在前端配置文件中注册 Agent 的展示信息：

```javascript
// frontend/src/config/agents.js

export const AGENT_CONFIG = {
  // 内置 Agent
  Reasoner: {
    name: "Reasoner",
    displayName: "推理 Agent",
    icon: "🧠",
    color: "#4CAF50",
    description: "负责信息确权与逻辑推理"
  },
  Mentor: {
    name: "Mentor",
    displayName: "导师 Agent",
    icon: "👨‍🏫",
    color: "#2196F3",
    description: "负责创意生成与指导"
  },
  Searcher: {
    name: "Searcher",
    displayName: "检索 Agent",
    icon: "🔍",
    color: "#FF9800",
    description: "负责文献检索与谱系构建"
  },
  Critic: {
    name: "Critic",
    displayName: "评审 Agent",
    icon: "⚖️",
    color: "#F44336",
    description: "负责约束校验与评分"
  },
  // 自定义 Agent
  Literature: {
    name: "Literature",
    displayName: "文献分析 Agent",
    icon: "📚",
    color: "#9C27B0",
    description: "深度分析文献并提取关键信息"
  }
};
```

#### 2.4.2 自定义 Agent 输出渲染

```javascript
// frontend/src/components/AgentOutput.jsx

import React from 'react';
import { AGENT_CONFIG } from '../config/agents';

const AgentOutput = ({ agentName, content, metadata }) => {
  const config = AGENT_CONFIG[agentName] || {
    displayName: agentName,
    icon: '🤖',
    color: '#607D8B',
    description: ''
  };

  // 自定义渲染：LiteratureAgent 的输出按字段渲染
  if (agentName === 'Literature') {
    return <LiteratureOutput content={content} config={config} />;
  }

  // 默认渲染
  return (
    <div className="agent-output" style={{ borderLeft: `4px solid ${config.color}` }}>
      <div className="agent-header">
        <span className="agent-icon">{config.icon}</span>
        <span className="agent-name">{config.displayName}</span>
      </div>
      <div className="agent-content">{content}</div>
    </div>
  );
};

const LiteratureOutput = ({ content, config }) => {
  let analysis;
  try {
    analysis = JSON.parse(content);
  } catch {
    analysis = { raw_response: content };
  }

  return (
    <div className="agent-output literature-output"
         style={{ borderLeft: `4px solid ${config.color}` }}>
      <div className="agent-header">
        <span className="agent-icon">{config.icon}</span>
        <span className="agent-name">{config.displayName}</span>
      </div>
      <div className="analysis-sections">
        <Section title="研究问题与动机" content={analysis.research_problem} />
        <Section title="方法核心创新" content={analysis.methodology} />
        <Section title="实验设计与结果" content={analysis.results} />
        <Section title="与当前论题的关联" content={analysis.relevance} />
        <Section title="可借鉴之处"
                 content={Array.isArray(analysis.takeaways)
                   ? analysis.takeaways.map((t, i) => `${i+1}. ${t}`).join('\n')
                   : analysis.takeaways} />
        <Section title="局限性与改进空间" content={analysis.limitations} />
      </div>
    </div>
  );
};

const Section = ({ title, content }) => (
  <div className="analysis-section">
    <h4>{title}</h4>
    <p>{content}</p>
  </div>
);

export default AgentOutput;
```

### 2.5 Agent 调试技巧

#### 2.5.1 启用详细日志

```python
# 在 .env 中设置
LOG_LEVEL=DEBUG

# 或在代码中临时启用
import logging
logging.getLogger("backend.agents").setLevel(logging.DEBUG)
```

#### 2.5.2 使用 Agent 调试模式

```python
# backend/agents/base_agent.py 中的调试方法

class BaseAgent(ABC):
    # ... 其他方法 ...

    def debug_prompt(self, input: str) -> str:
        """调试：查看将发送给模型的完整 Prompt"""
        messages = self._build_messages(input)
        prompt = ""
        for msg in messages:
            prompt += f"--- {msg['role'].upper()} ---\n"
            prompt += msg['content'] + "\n\n"
        return prompt

    async def dry_run(self, input: str) -> dict:
        """调试：模拟运行，不实际调用模型"""
        return {
            "agent": self.name,
            "model": self.model,
            "prompt_preview": self.debug_prompt(input)[:500] + "...",
            "context_history_count": len(self.context.history),
            "estimated_tokens": len(input) // 4  # 粗略估算
        }
```

使用调试方法：

```python
agent = LiteratureAgent(context=context)

# 查看 Prompt
print(agent.debug_prompt(literature))

# 模拟运行
debug_info = await agent.dry_run(literature)
print(f"预计 Token 数：{debug_info['estimated_tokens']}")
```

---

## 3. 约束系统扩展

### 3.1 约束架构总览

ThesisMiner v8.0 的约束系统分为硬约束与软约束：

```
+---------------------------+
|     约束系统              |
+---------------------------+
|                           |
|  +-------------------+    |
|  |    硬约束         |    |  失败即拒绝（fail-fast）
|  +-------------------+    |
|  | - 标题长度        |    |
|  | - 学科匹配        |    |
|  | - 导师方向        |    |
|  | - 时间可行性      |    |
|  | - 重复度          |    |
|  | - AI 痕迹         |    |
|  +-------------------+    |
|                           |
|  +-------------------+    |
|  |    软约束         |    |  评分制，影响排序
|  +-------------------+    |
|  | - 新颖性评分      |    |
|  | - 可行性评估      |    |
|  | - 风格质量        |    |
|  +-------------------+    |
|                           |
+---------------------------+
```

### 3.2 自定义硬约束

#### 3.2.1 硬约束接口

```python
# backend/constraints/base_constraint.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

@dataclass
class ConstraintResult:
    """约束检查结果"""
    passed: bool
    constraint_name: str
    message: str
    actual_value: Any = None
    expected_value: Any = None

class BaseHardConstraint(ABC):
    """硬约束抽象基类"""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description

    @abstractmethod
    async def check(self, proposal: dict, context: dict) -> ConstraintResult:
        """检查约束是否满足

        Args:
            proposal: 论题数据（含 title, abstract, methods 等）
            context: 上下文（含 session_id, advisor_info 等）

        Returns:
            ConstraintResult: 检查结果
        """
        pass

    def __repr__(self):
        return f"<HardConstraint: {self.name}>"
```

#### 3.2.2 实现自定义硬约束

以下实现一个「关键词必须包含」约束：

```python
# backend/constraints/keyword_constraint.py

from .base_constraint import BaseHardConstraint, ConstraintResult

class KeywordRequiredConstraint(BaseHardConstraint):
    """关键词必须包含约束

    要求论题标题或摘要中必须包含指定的关键词。
    """

    def __init__(
        self,
        required_keywords: list,
        field: str = "title",
        case_sensitive: bool = False
    ):
        super().__init__(
            name="keyword_required",
            description=f"要求{field}中包含关键词：{required_keywords}"
        )
        self.required_keywords = required_keywords
        self.field = field
        self.case_sensitive = case_sensitive

    async def check(self, proposal: dict, context: dict) -> ConstraintResult:
        text = proposal.get(self.field, "")
        if not self.case_sensitive:
            text = text.lower()
            keywords = [kw.lower() for kw in self.required_keywords]
        else:
            keywords = self.required_keywords

        missing = [kw for kw in keywords if kw not in text]

        if missing:
            return ConstraintResult(
                passed=False,
                constraint_name=self.name,
                message=f"{self.field}中缺少关键词：{missing}",
                actual_value=text,
                expected_value=self.required_keywords
            )

        return ConstraintResult(
            passed=True,
            constraint_name=self.name,
            message=f"所有关键词均存在",
            actual_value=text,
            expected_value=self.required_keywords
        )
```

#### 3.2.3 实现时间可行性约束

```python
# backend/constraints/time_feasibility_constraint.py

from datetime import datetime, timedelta
from .base_constraint import BaseHardConstraint, ConstraintResult

class TimeFeasibilityConstraint(BaseHardConstraint):
    """时间可行性约束

    根据论题复杂度与可用时间评估是否可行。
    """

    # 复杂度等级与所需月数
    COMPLEXITY_MONTHS = {
        "low": 6,       # 低复杂度：6 个月
        "medium": 9,    # 中复杂度：9 个月
        "high": 12,     # 高复杂度：12 个月
        "very_high": 18 # 极高复杂度：18 个月
    }

    def __init__(self):
        super().__init__(
            name="time_feasibility",
            description="评估论题在给定时间内是否可完成"
        )

    async def check(self, proposal: dict, context: dict) -> ConstraintResult:
        complexity = proposal.get("complexity", "medium")
        available_months = context.get("available_months", 12)

        required_months = self.COMPLEXITY_MONTHS.get(complexity, 9)

        if available_months < required_months:
            return ConstraintResult(
                passed=False,
                constraint_name=self.name,
                message=f"时间不足：需要 {required_months} 个月，"
                        f"仅有 {available_months} 个月",
                actual_value=available_months,
                expected_value=required_months
            )

        return ConstraintResult(
            passed=True,
            constraint_name=self.name,
            message=f"时间充足：需要 {required_months} 个月，"
                    f"有 {available_months} 个月",
            actual_value=available_months,
            expected_value=required_months
        )
```

#### 3.2.4 注册硬约束

```python
# backend/constraints/registry.py

from typing import List, Dict
from .base_constraint import BaseHardConstraint

# 全局约束注册表
CONSTRAINT_REGISTRY: Dict[str, BaseHardConstraint] = {}

def register_constraint(constraint: BaseHardConstraint):
    """注册约束"""
    CONSTRAINT_REGISTRY[constraint.name] = constraint

def get_constraint(name: str) -> BaseHardConstraint:
    """获取已注册的约束"""
    return CONSTRAINT_REGISTRY[name]

def list_constraints() -> List[str]:
    """列出所有约束"""
    return list(CONSTRAINT_REGISTRY.keys())

# 注册内置约束
from .title_length_constraint import TitleLengthConstraint
from .discipline_match_constraint import DisciplineMatchConstraint
from .duplication_constraint import DuplicationConstraint
from .keyword_constraint import KeywordRequiredConstraint
from .time_feasibility_constraint import TimeFeasibilityConstraint

register_constraint(TitleLengthConstraint(min_len=15, max_len=40))
register_constraint(DisciplineMatchConstraint())
register_constraint(DuplicationConstraint(threshold=0.30))
register_constraint(KeywordRequiredConstraint(
    required_keywords=["研究", "方法"],
    field="title"
))
register_constraint(TimeFeasibilityConstraint())
```

### 3.3 新颖性评估扩展

#### 3.3.1 新颖性评估架构

```python
# backend/constraints/novelty_scorer.py

from typing import List
from dataclasses import dataclass

@dataclass
class NoveltyDimension:
    """新颖性维度"""
    name: str
    score: float       # 0-100
    weight: float      # 权重，总和应为 1.0
    reasoning: str     # 评分理由

class NoveltyScorer:
    """新颖性评分器

    四维评估：
    1. 学科交叉（cross_discipline）
    2. 方法迁移（method_transfer）
    3. 痛点突破（pain_point）
    4. 趋势前瞻（trend_foresight）
    """

    def __init__(self, weights: dict = None):
        self.weights = weights or {
            "cross_discipline": 0.25,
            "method_transfer": 0.25,
            "pain_point": 0.25,
            "trend_foresight": 0.25
        }

    async def score(self, proposal: dict, context: dict) -> dict:
        """计算新颖性评分"""
        dimensions = []

        # 维度 1：学科交叉
        dimensions.append(await self._score_cross_discipline(proposal, context))

        # 维度 2：方法迁移
        dimensions.append(await self._score_method_transfer(proposal, context))

        # 维度 3：痛点突破
        dimensions.append(await self._score_pain_point(proposal, context))

        # 维度 4：趋势前瞻
        dimensions.append(await self._score_trend_foresight(proposal, context))

        # 计算加权总分
        total = sum(d.score * d.weight for d in dimensions)

        return {
            "total_score": total,
            "dimensions": [
                {
                    "name": d.name,
                    "score": d.score,
                    "weight": d.weight,
                    "reasoning": d.reasoning
                }
                for d in dimensions
            ]
        }

    async def _score_cross_discipline(self, proposal: dict, context: dict) -> NoveltyDimension:
        """评估学科交叉程度"""
        # 简化实现：检查论题是否涉及多个学科
        disciplines = proposal.get("disciplines", [])
        if len(disciplines) >= 3:
            score = 90
            reasoning = f"涉及 {len(disciplines)} 个学科，交叉程度高"
        elif len(disciplines) == 2:
            score = 70
            reasoning = f"涉及 {len(disciplines)} 个学科，有一定交叉"
        else:
            score = 40
            reasoning = "单一学科，交叉程度低"

        return NoveltyDimension(
            name="cross_discipline",
            score=score,
            weight=self.weights["cross_discipline"],
            reasoning=reasoning
        )

    async def _score_method_transfer(self, proposal: dict, context: dict) -> NoveltyDimension:
        """评估方法迁移程度"""
        source_methods = proposal.get("source_methods", [])
        target_domain = proposal.get("target_domain", "")

        if source_methods and target_domain:
            score = 85
            reasoning = f"将 {source_methods} 迁移到 {target_domain}"
        else:
            score = 50
            reasoning = "方法迁移不明显"

        return NoveltyDimension(
            name="method_transfer",
            score=score,
            weight=self.weights["method_transfer"],
            reasoning=reasoning
        )

    async def _score_pain_point(self, proposal: dict, context: dict) -> NoveltyDimension:
        """评估痛点突破程度"""
        pain_points = proposal.get("pain_points", [])
        solutions = proposal.get("solutions", [])

        if pain_points and solutions and len(solutions) >= len(pain_points):
            score = 88
            reasoning = f"针对 {len(pain_points)} 个痛点提出 {len(solutions)} 个解决方案"
        elif pain_points:
            score = 60
            reasoning = "识别了痛点但解决方案不充分"
        else:
            score = 30
            reasoning = "未明确识别痛点"

        return NoveltyDimension(
            name="pain_point",
            score=score,
            weight=self.weights["pain_point"],
            reasoning=reasoning
        )

    async def _score_trend_foresight(self, proposal: dict, context: dict) -> NoveltyDimension:
        """评估趋势前瞻程度"""
        keywords = proposal.get("keywords", [])
        trending_keywords = context.get("trending_keywords", [])

        match_count = len(set(keywords) & set(trending_keywords))
        if match_count >= 3:
            score = 90
            reasoning = f"命中 {match_count} 个趋势关键词"
        elif match_count >= 1:
            score = 65
            reasoning = f"命中 {match_count} 个趋势关键词"
        else:
            score = 40
            reasoning = "未命中趋势关键词"

        return NoveltyDimension(
            name="trend_foresight",
            score=score,
            weight=self.weights["trend_foresight"],
            reasoning=reasoning
        )
```

#### 3.3.2 扩展自定义维度

```python
# 添加自定义维度：社会价值
class ExtendedNoveltyScorer(NoveltyScorer):
    """扩展的新颖性评分器，增加社会价值维度"""

    def __init__(self):
        weights = {
            "cross_discipline": 0.20,
            "method_transfer": 0.20,
            "pain_point": 0.20,
            "trend_foresight": 0.20,
            "social_value": 0.20  # 新增维度
        }
        super().__init__(weights)

    async def score(self, proposal: dict, context: dict) -> dict:
        # 重写以包含新维度
        dimensions = [
            await self._score_cross_discipline(proposal, context),
            await self._score_method_transfer(proposal, context),
            await self._score_pain_point(proposal, context),
            await self._score_trend_foresight(proposal, context),
            await self._score_social_value(proposal, context)  # 新维度
        ]

        total = sum(d.score * d.weight for d in dimensions)

        return {
            "total_score": total,
            "dimensions": [
                {
                    "name": d.name,
                    "score": d.score,
                    "weight": d.weight,
                    "reasoning": d.reasoning
                }
                for d in dimensions
            ]
        }

    async def _score_social_value(self, proposal: dict, context: dict) -> NoveltyDimension:
        """评估社会价值"""
        social_impact = proposal.get("social_impact", "low")
        scores = {"high": 90, "medium": 70, "low": 40}
        score = scores.get(social_impact, 50)
        reasoning = f"社会影响等级：{social_impact}"

        return NoveltyDimension(
            name="social_value",
            score=score,
            weight=self.weights["social_value"],
            reasoning=reasoning
        )
```

### 3.4 风格规范化器扩展

#### 3.4.1 风格规范化器架构

```python
# backend/constraints/style_normalizer.py

import re
from typing import List, Tuple

class StyleNormalizer:
    """风格规范化器

    将生成的文本规范化为学术写作风格：
    1. 替换口语化表达
    2. 调整句式结构
    3. 检查学术规范
    """

    def __init__(self):
        self.replacement_rules: List[Tuple[str, str]] = []
        self.sentence_rules: List[Tuple[str, str]] = []
        self._load_default_rules()

    def _load_default_rules(self):
        """加载默认替换规则"""
        self.replacement_rules = [
            # 口语化 → 学术化
            (r"很好", "优异"),
            (r"很大", "显著"),
            (r"很多", "大量"),
            (r"越来越", "日益"),
            (r"我觉得", "本研究认为"),
            (r"我们认为", "本研究认为"),
            (r"大家知道", "众所周知"),
            (r"所以说", "因此"),
            (r"然后", "随后"),
            (r"还有就是", "此外"),
            # AI 痕迹词
            (r"值得注意的是", ""),
            (r"需要指出的是", ""),
            (r"总而言之", "综上所述"),
            (r"首先.*?其次.*?最后", "本研究依次"),  # 简化处理
        ]

    def normalize(self, text: str) -> str:
        """规范化文本"""
        # 应用替换规则
        for pattern, replacement in self.replacement_rules:
            text = re.sub(pattern, replacement, text)

        # 调整句式
        text = self._adjust_sentences(text)

        # 检查学术规范
        text = self._check_academic_norms(text)

        return text

    def _adjust_sentences(self, text: str) -> str:
        """调整句式"""
        # 长句拆分
        sentences = text.split("。")
        adjusted = []
        for sent in sentences:
            if len(sent) > 80:  # 超过 80 字的句子尝试拆分
                # 在逗号处拆分
                parts = sent.split("，")
                if len(parts) > 2:
                    mid = len(parts) // 2
                    adjusted.append("，".join(parts[:mid]) + "。")
                    adjusted.append("，".join(parts[mid:]) + "。")
                else:
                    adjusted.append(sent + "。")
            else:
                adjusted.append(sent + "。")
        return "".join(adjusted)

    def _check_academic_norms(self, text: str) -> str:
        """检查学术规范"""
        # 检查引用格式
        text = re.sub(r"\[(\d+)\]", r"[\1]", text)  # 统一引用格式

        # 检查数字使用
        text = re.sub(r"第([0-9]+)", r"第\1", text)  # 章节编号

        return text

    def add_replacement_rule(self, pattern: str, replacement: str):
        """添加自定义替换规则"""
        self.replacement_rules.append((pattern, replacement))

    def add_replacement_rules(self, rules: List[Tuple[str, str]]):
        """批量添加替换规则"""
        self.replacement_rules.extend(rules)
```

#### 3.4.2 扩展自定义替换词表

```python
# 创建自定义风格规范化器
class CustomStyleNormalizer(StyleNormalizer):
    """自定义风格规范化器"""

    def _load_default_rules(self):
        super()._load_default_rules()

        # 添加领域特定规则
        domain_rules = [
            # 医学领域
            (r"病人", "患者"),
            (r"看病", "就诊"),
            (r"治好", "治愈"),
            # 计算机领域
            (r"代码", "程序代码"),
            (r"程序", "算法程序"),
            # 通用学术
            (r"做实验", "开展实验"),
            (r"得出结论", "研究结论表明"),
            (r"发现", "研究发现"),
        ]
        self.replacement_rules.extend(domain_rules)

# 使用
normalizer = CustomStyleNormalizer()
text = "我们做实验发现，病人的病治好了，这个方法很好。"
normalized = normalizer.normalize(text)
print(normalized)
# 输出：本研究开展实验研究发现，患者的病治愈了，这个方法优异。
```

### 3.5 约束组合与优先级

#### 3.5.1 约束组合器

```python
# backend/constraints/composite.py

from typing import List
from .base_constraint import BaseHardConstraint, ConstraintResult

class CompositeConstraint(BaseHardConstraint):
    """组合约束

    支持多种组合策略：
    - AND：所有约束必须通过
    - OR：任一约束通过即可
    - PRIORITY：按优先级短路评估
    """

    def __init__(
        self,
        name: str,
        constraints: List[BaseHardConstraint],
        strategy: str = "AND",
        priorities: List[int] = None
    ):
        super().__init__(name=name, description=f"组合约束（{strategy}）")
        self.constraints = constraints
        self.strategy = strategy
        self.priorities = priorities or list(range(len(constraints)))

    async def check(self, proposal: dict, context: dict) -> ConstraintResult:
        if self.strategy == "AND":
            return await self._check_and(proposal, context)
        elif self.strategy == "OR":
            return await self._check_or(proposal, context)
        elif self.strategy == "PRIORITY":
            return await self._check_priority(proposal, context)
        else:
            raise ValueError(f"未知策略：{self.strategy}")

    async def _check_and(self, proposal: dict, context: dict) -> ConstraintResult:
        """AND 策略：所有约束必须通过"""
        failed = []
        for constraint in self.constraints:
            result = await constraint.check(proposal, context)
            if not result.passed:
                failed.append(result)

        if failed:
            messages = [f"[{r.constraint_name}] {r.message}" for r in failed]
            return ConstraintResult(
                passed=False,
                constraint_name=self.name,
                message="；".join(messages),
                actual_value=failed
            )

        return ConstraintResult(
            passed=True,
            constraint_name=self.name,
            message="所有约束均通过"
        )

    async def _check_or(self, proposal: dict, context: dict) -> ConstraintResult:
        """OR 策略：任一约束通过即可"""
        for constraint in self.constraints:
            result = await constraint.check(proposal, context)
            if result.passed:
                return ConstraintResult(
                    passed=True,
                    constraint_name=self.name,
                    message=f"约束 {constraint.name} 通过"
                )

        return ConstraintResult(
            passed=False,
            constraint_name=self.name,
            message="所有约束均未通过"
        )

    async def _check_priority(self, proposal: dict, context: dict) -> ConstraintResult:
        """PRIORITY 策略：按优先级短路评估"""
        # 按优先级排序
        sorted_constraints = sorted(
            zip(self.priorities, self.constraints),
            key=lambda x: x[0]
        )

        for priority, constraint in sorted_constraints:
            result = await constraint.check(proposal, context)
            if not result.passed:
                return ConstraintResult(
                    passed=False,
                    constraint_name=self.name,
                    message=f"优先级 {priority} 约束 {constraint.name} 失败：{result.message}",
                    actual_value=result
                )

        return ConstraintResult(
            passed=True,
            constraint_name=self.name,
            message="所有优先级约束均通过"
        )
```

#### 3.5.2 使用组合约束

```python
# 创建组合约束
from backend.constraints.composite import CompositeConstraint
from backend.constraints.keyword_constraint import KeywordRequiredConstraint
from backend.constraints.time_feasibility_constraint import TimeFeasibilityConstraint

# AND 组合
and_constraint = CompositeConstraint(
    name="basic_requirements",
    constraints=[
        KeywordRequiredConstraint(required_keywords=["研究"], field="title"),
        TimeFeasibilityConstraint()
    ],
    strategy="AND"
)

# PRIORITY 组合（先检查时间，再检查关键词）
priority_constraint = CompositeConstraint(
    name="priority_check",
    constraints=[
        TimeFeasibilityConstraint(),
        KeywordRequiredConstraint(required_keywords=["研究"], field="title")
    ],
    strategy="PRIORITY",
    priorities=[1, 2]  # 时间优先级 1（先检查），关键词优先级 2
)

# 执行检查
proposal = {
    "title": "基于深度学习的研究",
    "complexity": "medium"
}
context = {
    "available_months": 12
}

result = await priority_constraint.check(proposal, context)
print(f"通过：{result.passed}")
print(f"消息：{result.message}")
```

---

## 4. 缓存优化技巧

### 4.1 缓存架构原理

ThesisMiner v8.0 使用基于 SHA-256 前缀哈希的缓存机制，与 DeepSeek API 的上下文缓存兼容。

#### 4.1.1 缓存架构图

```
+---------------------------+
|       请求入口            |
+---------------------------+
         |
         v
+---------------------------+
|   构建 Prompt             |
|   (三段式)                |
+---------------------------+
         |
         v
+---------------------------+
|   计算前缀哈希            |
|   SHA-256(stable_prefix) |
+---------------------------+
         |
         v
+----------------+----------+
|                |          |
v                v          v
+-------+   +----------+   +-------+
| 缓存  |   | 缓存未命中|   | 缓存  |
| 命中  |   |          |   | 过期  |
+-------+   +----------+   +-------+
    |            |              |
    v            v              v
返回缓存    调用模型 API    删除旧缓存
(0 成本)    (正常计费)     重新缓存
```

#### 4.1.2 三段式 Prompt 与缓存

```python
# backend/prompts/builder.py

import hashlib
from typing import List, Dict

class PromptBuilder:
    """三段式 Prompt 构建器

    结构：
    1. 稳定前缀（stable_prefix）：系统提示、角色定义、规则说明
       → 这部分是缓存的 key
    2. 动态中间（dynamic_middle）：用户输入、当前任务
       → 这部分不参与缓存
    3. DST 尾部（dst_tail）：历史对话压缩
       → 这部分可能变化，影响缓存命中
    """

    def __init__(self, system_prompt: str, rules: List[str] = None):
        self.system_prompt = system_prompt
        self.rules = rules or []

    def build(self, user_input: str, dst_summary: str = "") -> List[Dict]:
        """构建三段式 Prompt"""
        # 稳定前缀
        stable_prefix = self.system_prompt
        if self.rules:
            stable_prefix += "\n\n规则：\n" + "\n".join(self.rules)

        # 动态中间
        dynamic_middle = user_input

        # DST 尾部
        dst_tail = dst_summary

        return [
            {"role": "system", "content": stable_prefix},
            {"role": "user", "content": dynamic_middle},
            {"role": "assistant", "content": dst_tail}
        ]

    def get_cache_key(self) -> str:
        """计算缓存 key（基于稳定前缀的 SHA-256）"""
        stable_content = self.system_prompt
        if self.rules:
            stable_content += "\n".join(self.rules)
        return hashlib.sha256(stable_content.encode()).hexdigest()
```

### 4.2 前缀固化策略

#### 4.2.1 问题：动态前缀导致缓存失效

```python
# ❌ 错误示例：前缀包含动态内容
class BadPromptBuilder:
    def build(self, user_input: str, session_id: str, timestamp: str):
        return [
            # 系统提示中包含 session_id 和 timestamp，导致每次都不同
            {"role": "system", "content": f"你是助手。会话：{session_id}，时间：{timestamp}"},
            {"role": "user", "content": user_input}
        ]
    # 结果：缓存永远不会命中
```

#### 4.2.2 解决：分离稳定与动态内容

```python
# ✓ 正确示例：稳定前缀 + 动态中间
class GoodPromptBuilder:
    def __init__(self):
        # 稳定前缀：不含任何动态内容
        self.stable_prefix = (
            "你是一位学术论题生成助手。"
            "你的任务是根据用户的需求，生成高质量的学术论题。"
            "请遵循以下规则：\n"
            "1. 论题标题长度 15-40 字符\n"
            "2. 论题应具有新颖性\n"
            "3. 论题应具有可行性\n"
        )

    def build(self, user_input: str, session_id: str, timestamp: str):
        return [
            # 稳定前缀
            {"role": "system", "content": self.stable_prefix},
            # 动态中间：用户输入 + 会话信息
            {"role": "user", "content": f"会话：{session_id}\n时间：{timestamp}\n\n{user_input}"}
        ]
    # 结果：稳定前缀不变，缓存可以命中
```

#### 4.2.3 前缀固化检查工具

```python
# backend/utils/cache_analyzer.py

import hashlib
from collections import Counter

class CacheAnalyzer:
    """缓存分析工具"""

    @staticmethod
    def analyze_prefix_stability(prompts: list) -> dict:
        """分析前缀稳定性

        Args:
            prompts: 历史 Prompt 列表（每个是 messages 列表）

        Returns:
            分析报告
        """
        prefixes = []
        for messages in prompts:
            if messages and messages[0]["role"] == "system":
                prefixes.append(messages[0]["content"])

        if not prefixes:
            return {"error": "无系统提示"}

        # 计算每个前缀的哈希
        hashes = [hashlib.sha256(p.encode()).hexdigest()[:16] for p in prefixes]
        hash_counts = Counter(hashes)

        # 计算稳定性
        unique_hashes = len(hash_counts)
        total = len(hashes)
        stability = (total - unique_hashes + 1) / total * 100

        return {
            "total_prompts": total,
            "unique_prefixes": unique_hashes,
            "stability_percent": round(stability, 2),
            "hash_distribution": dict(hash_counts.most_common(5)),
            "recommendation": (
                "前缀稳定，缓存命中率高" if stability > 80
                else "前缀不稳定，建议固化前缀" if stability > 50
                else "前缀严重不稳定，必须重构"
            )
        }

    @staticmethod
    def find_unstable_parts(prefix: str, other_prefixes: list) -> list:
        """找出前缀中不稳定的部分"""
        # 简化实现：按行对比
        lines = prefix.split("\n")
        unstable = []
        for other in other_prefixes:
            other_lines = other.split("\n")
            for i, (line1, line2) in enumerate(zip(lines, other_lines)):
                if line1 != line2 and i not in unstable:
                    unstable.append(i)
        return unstable
```

### 4.3 DST 压缩调优

#### 4.3.1 DST 压缩原理

```
原始对话历史（10 轮，5000 tokens）：
+---+---+---+---+---+---+---+---+---+---+
| 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10|
+---+---+---+---+---+---+---+---+---+---+

DST 压缩后（保留最近 3 轮 + 摘要，1500 tokens）：
+-----------+---+---+---+
|  摘要     | 8 | 9 | 10|
| (1-7轮)   |   |   |   |
+-----------+---+---+---+

缓存命中：稳定前缀 + DST 摘要 → 可缓存部分增大
```

#### 4.3.2 DST 压缩实现

```python
# backend/agents/dst_compressor.py

from typing import List, Dict
import json

class DSTCompressor:
    """DST（Dialog State Tracking）压缩器"""

    def __init__(
        self,
        max_recent_turns: int = 3,
        max_summary_tokens: int = 500,
        compression_threshold: int = 10
    ):
        self.max_recent_turns = max_recent_turns
        self.max_summary_tokens = max_summary_tokens
        self.compression_threshold = compression_threshold

    def compress(self, history: List[Dict]) -> Dict:
        """压缩对话历史

        Args:
            history: 完整对话历史

        Returns:
            {
                "summary": "压缩摘要",
                "recent_turns": [最近几轮对话],
                "compressed_count": 被压缩的轮数
            }
        """
        if len(history) <= self.compression_threshold:
            return {
                "summary": "",
                "recent_turns": history,
                "compressed_count": 0
            }

        # 分割：需要压缩的部分 + 保留的部分
        to_compress = history[:-self.max_recent_turns]
        to_keep = history[-self.max_recent_turns:]

        # 生成摘要
        summary = self._generate_summary(to_compress)

        return {
            "summary": summary,
            "recent_turns": to_keep,
            "compressed_count": len(to_compress)
        }

    def _generate_summary(self, turns: List[Dict]) -> str:
        """生成对话摘要"""
        summary_parts = []
        for turn in turns:
            role = turn.get("role", "unknown")
            content = turn.get("content", "")

            # 提取关键信息
            if role == "user":
                # 用户消息：提取意图
                intent = self._extract_intent(content)
                summary_parts.append(f"用户询问：{intent}")
            elif role == "assistant":
                # 助手消息：提取要点
                points = self._extract_key_points(content)
                summary_parts.append(f"助手回答：{points}")

        return "；".join(summary_parts)

    def _extract_intent(self, content: str) -> str:
        """提取用户意图（简化实现）"""
        # 取前 50 字符作为意图
        return content[:50].replace("\n", " ")

    def _extract_key_points(self, content: str) -> str:
        """提取助手回答要点（简化实现）"""
        # 取前 100 字符作为要点
        return content[:100].replace("\n", " ")
```

#### 4.3.3 DST 调优参数

```python
# 不同场景的 DST 配置
DST_CONFIGS = {
    # 短对话场景：保留更多近期轮次
    "short_conversation": {
        "max_recent_turns": 5,
        "max_summary_tokens": 300,
        "compression_threshold": 8
    },
    # 长对话场景：更激进的压缩
    "long_conversation": {
        "max_recent_turns": 2,
        "max_summary_tokens": 800,
        "compression_threshold": 5
    },
    # 缓存优化场景：最大化稳定部分
    "cache_optimized": {
        "max_recent_turns": 1,
        "max_summary_tokens": 1000,
        "compression_threshold": 3
    }
}

# 使用
compressor = DSTCompressor(**DST_CONFIGS["cache_optimized"])
```

### 4.4 会话切换的缓存处理

#### 4.4.1 会话切换缓存策略

```python
# backend/cache/session_cache_manager.py

import hashlib
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: str
    created_at: datetime
    hit_count: int = 0
    session_id: str = ""
    conversation_id: str = ""

class SessionCacheManager:
    """会话级缓存管理器"""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self.cache: Dict[str, CacheEntry] = {}
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds

    def get_cache_key(
        self,
        stable_prefix: str,
        session_id: str,
        conversation_id: str
    ) -> str:
        """计算缓存 key

        策略：
        - 稳定前缀相同 → 可以共享缓存
        - 会话 ID 不同 → 缓存隔离
        - 对话 ID 不同 → 缓存隔离
        """
        content = f"{stable_prefix}|{session_id}|{conversation_id}"
        return hashlib.sha256(content.encode()).hexdigest()

    def get(self, key: str) -> Optional[str]:
        """获取缓存"""
        if key not in self.cache:
            return None

        entry = self.cache[key]

        # 检查 TTL
        age = (datetime.now() - entry.created_at).total_seconds()
        if age > self.ttl_seconds:
            del self.cache[key]
            return None

        entry.hit_count += 1
        return entry.value

    def set(
        self,
        key: str,
        value: str,
        session_id: str,
        conversation_id: str
    ):
        """设置缓存"""
        # LRU 淘汰
        if len(self.cache) >= self.max_size:
            self._evict_lru()

        self.cache[key] = CacheEntry(
            key=key,
            value=value,
            created_at=datetime.now(),
            session_id=session_id,
            conversation_id=conversation_id
        )

    def invalidate_session(self, session_id: str):
        """使会话的所有缓存失效"""
        keys_to_delete = [
            k for k, v in self.cache.items()
            if v.session_id == session_id
        ]
        for k in keys_to_delete:
            del self.cache[k]

    def invalidate_conversation(self, conversation_id: str):
        """使对话的所有缓存失效"""
        keys_to_delete = [
            k for k, v in self.cache.items()
            if v.conversation_id == conversation_id
        ]
        for k in keys_to_delete:
            del self.cache[k]

    def _evict_lru(self):
        """LRU 淘汰"""
        if not self.cache:
            return
        # 找到 hit_count 最少的条目
        lru_key = min(self.cache, key=lambda k: self.cache[k].hit_count)
        del self.cache[lru_key]

    def get_stats(self) -> dict:
        """获取缓存统计"""
        total = len(self.cache)
        hits = sum(e.hit_count for e in self.cache.values())
        return {
            "total_entries": total,
            "total_hits": hits,
            "avg_hits_per_entry": hits / total if total > 0 else 0,
            "max_size": self.max_size,
            "ttl_seconds": self.ttl_seconds
        }
```

### 4.5 命中率监控与诊断

#### 4.5.1 命中率监控仪表板

```python
# backend/monitoring/cache_monitor.py

from typing import List, Dict
from datetime import datetime, timedelta
from collections import defaultdict

class CacheMonitor:
    """缓存监控器"""

    def __init__(self):
        self.records: List[Dict] = []

    def record(
        self,
        cache_key: str,
        hit: bool,
        model: str,
        stage: str,
        session_id: str,
        tokens_saved: int = 0
    ):
        """记录缓存事件"""
        self.records.append({
            "timestamp": datetime.now(),
            "cache_key": cache_key,
            "hit": hit,
            "model": model,
            "stage": stage,
            "session_id": session_id,
            "tokens_saved": tokens_saved if hit else 0
        })

    def get_hit_rate(
        self,
        time_range: timedelta = None,
        by_model: bool = False,
        by_stage: bool = False
    ) -> dict:
        """获取命中率"""
        records = self._filter_by_time(time_range)

        if not records:
            return {"hit_rate": 0, "total": 0, "hits": 0}

        if by_model:
            return self._group_hit_rate(records, "model")
        elif by_stage:
            return self._group_hit_rate(records, "stage")
        else:
            total = len(records)
            hits = sum(1 for r in records if r["hit"])
            return {
                "hit_rate": hits / total,
                "total": total,
                "hits": hits,
                "tokens_saved": sum(r["tokens_saved"] for r in records)
            }

    def _group_hit_rate(self, records: List[Dict], key: str) -> dict:
        """按字段分组计算命中率"""
        groups = defaultdict(list)
        for r in records:
            groups[r[key]].append(r)

        result = {}
        for group_name, group_records in groups.items():
            total = len(group_records)
            hits = sum(1 for r in group_records if r["hit"])
            result[group_name] = {
                "hit_rate": hits / total,
                "total": total,
                "hits": hits,
                "tokens_saved": sum(r["tokens_saved"] for r in group_records)
            }
        return result

    def _filter_by_time(self, time_range: timedelta) -> List[Dict]:
        """按时间范围过滤"""
        if time_range is None:
            return self.records
        cutoff = datetime.now() - time_range
        return [r for r in self.records if r["timestamp"] > cutoff]

    def diagnose_low_hit_rate(self) -> dict:
        """诊断低命中率原因"""
        by_stage = self.get_hit_rate(by_stage=True)

        issues = []
        for stage, stats in by_stage.items():
            if stats["hit_rate"] < 0.5:
                issues.append({
                    "stage": stage,
                    "hit_rate": stats["hit_rate"],
                    "issue": "命中率低于 50%",
                    "suggestion": "检查该阶段的 Prompt 前缀是否稳定"
                })

        return {
            "issues": issues,
            "overall_hit_rate": self.get_hit_rate()["hit_rate"],
            "recommendation": (
                "整体命中率良好" if not issues
                else f"发现 {len(issues)} 个低命中率阶段，建议优化"
            )
        }
```

---

## 5. 深度辅助三件套实战

### 5.1 文献精读高级用法

#### 5.1.1 批量文献精读

```python
# backend/agents/batch_literature_agent.py

import asyncio
from typing import List, Dict
from .literature_agent import LiteratureAgent
from .base_agent import AgentContext

class BatchLiteratureAgent:
    """批量文献精读 Agent"""

    def __init__(self, context: AgentContext, max_concurrent: int = 3):
        self.context = context
        self.max_concurrent = max_concurrent

    async def analyze_batch(self, literatures: List[str]) -> List[Dict]:
        """批量分析文献

        Args:
            literatures: 文献内容列表

        Returns:
            分析结果列表
        """
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def analyze_one(lit: str) -> Dict:
            async with semaphore:
                agent = LiteratureAgent(context=self.context)
                result = await agent.run(lit)
                return {
                    "success": result.success,
                    "analysis": result.content if result.success else None,
                    "error": result.error
                }

        tasks = [analyze_one(lit) for lit in literatures]
        results = await asyncio.gather(*tasks)
        return results

    async def generate_summary(self, analyses: List[Dict]) -> str:
        """生成综合摘要"""
        successful = [a for a in analyses if a["success"]]
        if not successful:
            return "所有文献分析均失败"

        # 提取所有分析的关键信息
        all_takeaways = []
        all_limitations = []
        for a in successful:
            try:
                import json
                analysis = json.loads(a["analysis"])
                if "takeaways" in analysis:
                    all_takeaways.extend(analysis["takeaways"])
                if "limitations" in analysis:
                    all_limitations.append(analysis["limitations"])
            except:
                pass

        summary = f"""批量文献分析综合摘要
==================================================
共分析 {len(successful)}/{len(analyses)} 篇文献

可借鉴之处（共 {len(all_takeaways)} 条）：
{chr(10).join(f'- {t}' for t in all_takeaways)}

共性问题/局限（共 {len(all_limitations)} 条）：
{chr(10).join(f'- {l}' for l in all_limitations)}
"""
        return summary
```

#### 5.1.2 文献对比分析

```python
async def compare_literatures(literatures: List[str], context: AgentContext):
    """对比多篇文献"""
    agent = LiteratureAgent(context=context)

    # 分别分析每篇文献
    analyses = []
    for lit in literatures:
        result = await agent.run(lit)
        if result.success:
            import json
            analyses.append(json.loads(result.content))

    # 生成对比表
    comparison = "文献对比分析\n"
    comparison += "=" * 80 + "\n"
    comparison += f"{'维度':<20} {'文献1':<30} {'文献2':<30}\n"
    comparison += "-" * 80 + "\n"

    dimensions = ["research_problem", "methodology", "results"]
    for dim in dimensions:
        val1 = analyses[0].get(dim, "N/A")[:28] if len(analyses) > 0 else "N/A"
        val2 = analyses[1].get(dim, "N/A")[:28] if len(analyses) > 1 else "N/A"
        comparison += f"{dim:<20} {val1:<30} {val2:<30}\n"

    return comparison
```

### 5.2 实验预研模板定制

#### 5.2.1 自定义实验预研模板

```python
# backend/templates/experiment_template.py

from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class ExperimentTemplate:
    """实验预研模板"""
    name: str
    description: str
    sections: List[dict] = field(default_factory=list)

    def add_section(self, title: str, required: bool = True, hint: str = ""):
        """添加章节"""
        self.sections.append({
            "title": title,
            "required": required,
            "hint": hint
        })

    def to_prompt(self) -> str:
        """转换为 Prompt"""
        prompt = f"实验预研模板：{self.name}\n"
        prompt += f"说明：{self.description}\n\n"
        prompt += "请按以下结构生成实验预研报告：\n"
        for i, section in enumerate(self.sections, 1):
            req = "（必填）" if section["required"] else "（选填）"
            prompt += f"{i}. {section['title']} {req}\n"
            if section["hint"]:
                prompt += f"   提示：{section['hint']}\n"
        return prompt

# 预定义模板
def get_default_template() -> ExperimentTemplate:
    """默认实验预研模板"""
    template = ExperimentTemplate(
        name="标准实验预研",
        description="适用于大多数计算机科学实验"
    )
    template.add_section("实验目标", required=True, hint="明确要验证的假设")
    template.add_section("数据集", required=True, hint="列出数据集名称、规模、来源")
    template.add_section("评价指标", required=True, hint="列出指标及计算方法")
    template.add_section("对比方法", required=True, hint="列出基线方法")
    template.add_section("实验环境", required=True, hint="硬件、软件配置")
    template.add_section("实现细节", required=True, hint="超参数、训练策略")
    template.add_section("消融实验", required=False, hint="验证各组件贡献")
    template.add_section("预期结果", required=True, hint="量化预期")
    template.add_section("风险分析", required=False, hint="可能的问题与应对")
    return template

def get_medical_template() -> ExperimentTemplate:
    """医学实验预研模板"""
    template = ExperimentTemplate(
        name="医学影像实验预研",
        description="适用于医学影像分析实验"
    )
    template.add_section("临床问题", required=True, hint="明确临床需求")
    template.add_section("数据集", required=True, hint="含伦理审批、数据来源")
    template.add_section("数据预处理", required=True, hint="去标识化、归一化")
    template.add_section("评价指标", required=True, hint="含临床相关指标")
    template.add_section("对比方法", required=True)
    template.add_section("实验环境", required=True)
    template.add_section("实现细节", required=True)
    template.add_section("消融实验", required=False)
    template.add_section("临床验证", required=True, hint="如何在临床场景验证")
    template.add_section("伦理考量", required=True, hint="数据隐私、公平性")
    template.add_section("预期结果", required=True)
    return template
```

### 5.3 答辩模拟进阶

#### 5.3.1 自定义评委角色

```python
# backend/agents/defense_simulator.py

from typing import List, Dict
from .base_agent import BaseAgent, AgentContext, AgentResult

class DefenseSimulator(BaseAgent):
    """答辩模拟器"""

    JUDGE_PROFILES = {
        "friendly": {
            "name": "友善型评委",
            "style": "多鼓励，少追问，关注亮点",
            "question_types": ["clarification", "strength"],
            "follow_up_probability": 0.3
        },
        "rigorous": {
            "name": "严谨型评委",
            "style": "追问细节，质疑方法，关注严谨性",
            "question_types": ["detail", "methodology", "limitation"],
            "follow_up_probability": 0.7
        },
        "challenging": {
            "name": "挑战型评委",
            "style": "强烈质疑，压力测试，关注创新性",
            "question_types": ["challenge", "comparison", "future"],
            "follow_up_probability": 0.9
        }
    }

    def __init__(
        self,
        context: AgentContext,
        judge_style: str = "rigorous",
        num_questions: int = 15
    ):
        super().__init__(
            name="DefenseSimulator",
            model="claude-opus-4.5",
            context=context
        )
        self.judge_style = judge_style
        self.num_questions = num_questions
        self.questions_asked: List[Dict] = []

    async def run(self, input: str) -> AgentResult:
        """运行答辩模拟"""
        profile = self.JUDGE_PROFILES.get(self.judge_style, self.JUDGE_PROFILES["rigorous"])

        # 生成问题
        questions = await self._generate_questions(input, profile, self.num_questions)

        return AgentResult(
            success=True,
            content="\n\n".join(q["question"] for q in questions),
            metadata={
                "judge_style": self.judge_style,
                "num_questions": len(questions),
                "questions": questions
            }
        )

    async def _generate_questions(
        self,
        thesis_summary: str,
        profile: dict,
        count: int
    ) -> List[Dict]:
        """生成问题列表"""
        # 简化实现：基于模板生成
        templates = {
            "clarification": "请详细解释你提到的「{concept}」是什么意思？",
            "strength": "你的方法最大的亮点是什么？",
            "detail": "请详细说明你的{component}是如何实现的？",
            "methodology": "为什么选择{method}而不是其他方法？",
            "limitation": "你的方法有什么局限性？",
            "challenge": "如果{scenario}，你的方法还能work吗？",
            "comparison": "你的方法与{baseline}相比有什么本质区别？",
            "future": "这个工作未来可以如何扩展？"
        }

        questions = []
        for q_type in profile["question_types"]:
            template = templates.get(q_type, "请谈谈你的看法。")
            questions.append({
                "type": q_type,
                "question": template.format(
                    concept="半监督学习",
                    component="注意力模块",
                    method="一致性正则化",
                    scenario="标注数据更少",
                    baseline="Mean Teacher"
                )
            })

        return questions[:count]

    async def evaluate_response(self, question: str, response: str) -> dict:
        """评估答辩回答"""
        # 简化实现
        scores = {
            "clarity": 80,
            "depth": 75,
            "accuracy": 85,
            "confidence": 78
        }
        overall = sum(scores.values()) / len(scores)

        return {
            "scores": scores,
            "overall": overall,
            "feedback": "回答基本清晰，建议加强对方法细节的理解。"
        }
```

---

## 6. API 集成与 SDK 封装

### 6.1 REST API 高级用法

#### 6.1.1 批量操作 API

```python
# 批量创建会话
import httpx
import asyncio

async def batch_create_sessions(count: int):
    """批量创建会话"""
    async with httpx.AsyncClient() as client:
        tasks = []
        for i in range(count):
            task = client.post(
                "http://localhost:8000/api/sessions",
                json={
                    "name": f"批量会话 {i+1}",
                    "degree": "master",
                    "discipline": "computer_science"
                }
            )
            tasks.append(task)

        responses = await asyncio.gather(*tasks)
        return [r.json() for r in responses]

# 批量提交信息确权
async def batch_confirm(sessions: list, info: dict):
    """批量提交信息确权"""
    async with httpx.AsyncClient() as client:
        tasks = []
        for session in sessions:
            task = client.post(
                f"http://localhost:8000/api/sessions/{session['session_id']}/confirm",
                json=info
            )
            tasks.append(task)

        responses = await asyncio.gather(*tasks)
        return [r.json() for r in responses]
```

#### 6.1.2 分页与过滤

```python
# 获取会话列表（分页）
async def list_sessions(page: int = 1, size: int = 20, degree: str = None):
    """获取会话列表"""
    params = {"page": page, "size": size}
    if degree:
        params["degree"] = degree

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8000/api/sessions",
            params=params
        )
        return response.json()

# 结果示例
{
    "items": [...],
    "total": 150,
    "page": 1,
    "size": 20,
    "pages": 8
}
```

### 6.2 流式 SSE 处理

#### 6.2.1 Python SSE 客户端

```python
# backend/utils/sse_client.py

import httpx
import json
from typing import AsyncGenerator

class SSEClient:
    """SSE 客户端"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url

    async def stream_ideation(
        self,
        session_id: str,
        count: int = 10
    ) -> AsyncGenerator[dict, None]:
        """流式获取创意生成结果"""
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/sessions/{session_id}/ideate",
                json={"count": count},
                timeout=300
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        try:
                            event = json.loads(data)
                            yield event
                        except json.JSONDecodeError:
                            continue

# 使用示例
async def main():
    client = SSEClient()
    async for event in client.stream_ideation("sess_abc123", count=10):
        if event["type"] == "progress":
            print(f"进度：{event['progress']}% - {event.get('agent', '')}")
        elif event["type"] == "idea":
            print(f"创意：{event['title']}（评分：{event['score']}）")
        elif event["type"] == "complete":
            print(f"完成，共 {event['total_ideas']} 个创意")
            break
```

#### 6.2.2 JavaScript SSE 客户端

```javascript
// frontend/src/utils/sseClient.js

export class SSEClient {
  constructor(baseUrl = 'http://localhost:8000') {
    this.baseUrl = baseUrl;
  }

  async *streamIdeation(sessionId, count = 10) {
    const response = await fetch(`${this.baseUrl}/api/sessions/${sessionId}/ideate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ count })
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            yield JSON.parse(line.slice(6));
          } catch (e) {
            console.error('SSE parse error:', e);
          }
        }
      }
    }
  }
}

// 使用示例
const client = new SSEClient();
for await (const event of client.streamIdeation('sess_abc123', 10)) {
  if (event.type === 'progress') {
    updateProgressBar(event.progress);
  } else if (event.type === 'idea') {
    addIdeaToList(event);
  } else if (event.type === 'complete') {
    showCompleteMessage(event.total_ideas);
  }
}
```

### 6.3 Webhook 配置

#### 6.3.1 Webhook 注册

```python
# 注册 Webhook
import httpx

async def register_webhook():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/webhooks",
            json={
                "url": "https://your-app.com/webhook/thesisminer",
                "events": [
                    "proposal.generated",
                    "validation.completed",
                    "budget.threshold_exceeded"
                ],
                "secret": "your-webhook-secret"
            }
        )
        return response.json()

# 响应
{
    "webhook_id": "wh_abc123",
    "url": "https://your-app.com/webhook/thesisminer",
    "events": ["proposal.generated", "validation.completed", "budget.threshold_exceeded"],
    "created_at": "2026-06-19T12:00:00Z"
}
```

#### 6.3.2 Webhook 接收端

```python
# your-app.com 的 Webhook 接收端
from fastapi import FastAPI, Request, HTTPException
import hmac
import hashlib

app = FastAPI()

WEBHOOK_SECRET = "your-webhook-secret"

@app.post("/webhook/thesisminer")
async def receive_webhook(request: Request):
    # 验证签名
    signature = request.headers.get("X-ThesisMiner-Signature", "")
    body = await request.body()

    expected_signature = hmac.new(
        WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # 处理事件
    event = await request.json()
    event_type = event.get("type")

    if event_type == "proposal.generated":
        await handle_proposal_generated(event["data"])
    elif event_type == "validation.completed":
        await handle_validation_completed(event["data"])
    elif event_type == "budget.threshold_exceeded":
        await handle_budget_alert(event["data"])

    return {"status": "received"}

async def handle_proposal_generated(data):
    print(f"新论题生成：{data['title']}")
    # 发送通知、更新数据库等

async def handle_validation_completed(data):
    print(f"校验完成：{'通过' if data['passed'] else '未通过'}")

async def handle_budget_alert(data):
    print(f"预算告警：已用 {data['used']} / {data['limit']}")
```

### 6.4 Python SDK 封装

```python
# thesisminer_sdk/client.py

import httpx
import asyncio
from typing import Optional, List, Dict, AsyncGenerator

class ThesisMinerClient:
    """ThesisMiner Python SDK"""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout: int = 300
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {}
        )

    async def close(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    # ============ 会话管理 ============

    async def create_session(
        self,
        name: str,
        degree: str,
        discipline: str
    ) -> Dict:
        """创建会话"""
        response = await self._client.post("/api/sessions", json={
            "name": name,
            "degree": degree,
            "discipline": discipline
        })
        response.raise_for_status()
        return response.json()

    async def list_sessions(
        self,
        page: int = 1,
        size: int = 20
    ) -> Dict:
        """列出会话"""
        response = await self._client.get("/api/sessions", params={
            "page": page,
            "size": size
        })
        response.raise_for_status()
        return response.json()

    async def delete_session(self, session_id: str) -> Dict:
        """删除会话"""
        response = await self._client.delete(f"/api/sessions/{session_id}")
        response.raise_for_status()
        return response.json()

    # ============ 五阶段流程 ============

    async def confirm_information(
        self,
        session_id: str,
        research_direction: str,
        interests: List[str],
        advisor: Dict,
        constraints: Dict
    ) -> Dict:
        """信息确权"""
        response = await self._client.post(
            f"/api/sessions/{session_id}/confirm",
            json={
                "research_direction": research_direction,
                "interests": interests,
                "advisor": advisor,
                "constraints": constraints
            }
        )
        response.raise_for_status()
        return response.json()

    async def generate_ideas(
        self,
        session_id: str,
        count: int = 10
    ) -> AsyncGenerator[Dict, None]:
        """生成创意（流式）"""
        async with self._client.stream(
            "POST",
            f"/api/sessions/{session_id}/ideate",
            json={"count": count}
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    import json
                    yield json.loads(line[6:])

    async def validate_idea(self, session_id: str, idea_id: str) -> Dict:
        """校验论题"""
        response = await self._client.post(
            f"/api/sessions/{session_id}/validate",
            json={"idea_id": idea_id}
        )
        response.raise_for_status()
        return response.json()

    async def generate_proposal(
        self,
        session_id: str,
        idea_id: str,
        granularities: List[str]
    ) -> Dict:
        """多粒度生成"""
        response = await self._client.post(
            f"/api/sessions/{session_id}/generate",
            json={
                "idea_id": idea_id,
                "granularities": granularities
            }
        )
        response.raise_for_status()
        return response.json()

    # ============ 预算查询 ============

    async def get_budget_summary(self, session_id: str) -> Dict:
        """获取预算摘要"""
        response = await self._client.get(
            f"/api/sessions/{session_id}/budget/summary"
        )
        response.raise_for_status()
        return response.json()

    async def export_budget(
        self,
        session_id: str,
        format: str = "csv"
    ) -> bytes:
        """导出预算报表"""
        response = await self._client.get(
            f"/api/sessions/{session_id}/budget/export",
            params={"format": format}
        )
        response.raise_for_status()
        return response.content

    # ============ 谱系图谱 ============

    async def get_lineage(
        self,
        session_id: str,
        node_types: Optional[List[str]] = None
    ) -> Dict:
        """获取谱系图谱"""
        params = {}
        if node_types:
            params["node_types"] = ",".join(node_types)

        response = await self._client.get(
            f"/api/sessions/{session_id}/lineage",
            params=params
        )
        response.raise_for_status()
        return response.json()


# 使用示例
async def main():
    async with ThesisMinerClient("http://localhost:8000") as client:
        # 创建会话
        session = await client.create_session(
            name="SDK 测试",
            degree="master",
            discipline="computer_science"
        )
        session_id = session["session_id"]

        # 信息确权
        await client.confirm_information(
            session_id=session_id,
            research_direction="computer_vision",
            interests=["image_classification", "object_detection"],
            advisor={"name": "张教授", "research_areas": ["deep_learning"]},
            constraints={"thesis_type": "applied", "duration_months": 12}
        )

        # 生成创意（流式）
        async for event in client.generate_ideas(session_id, count=5):
            if event["type"] == "idea":
                print(f"创意：{event['title']}")

        # 获取预算
        budget = await client.get_budget_summary(session_id)
        print(f"总成本：${budget['total_cost_usd']:.2f}")

asyncio.run(main())
```

---

## 7. D3.js 谱系图谱定制

### 7.1 节点样式定制

#### 7.1.1 自定义节点渲染

```javascript
// frontend/src/components/lineage/CustomNodeRenderer.js

import * as d3 from 'd3';

export class CustomNodeRenderer {
  constructor(svg) {
    this.svg = svg;
  }

  renderNode(node, config = {}) {
    const {
      shape = 'circle',      // circle | rect | diamond | star
      size = 30,
      color = '#4CAF50',
      icon = '',
      label = node.label || node.id,
      strokeWidth = 2,
      strokeColor = '#fff'
    } = config;

    const nodeGroup = this.svg.append('g')
      .attr('class', 'node')
      .attr('transform', `translate(${node.x}, ${node.y})`)
      .datum(node);

    // 根据形状渲染
    switch (shape) {
      case 'circle':
        this._renderCircle(nodeGroup, size, color, strokeWidth, strokeColor);
        break;
      case 'rect':
        this._renderRect(nodeGroup, size, color, strokeWidth, strokeColor);
        break;
      case 'diamond':
        this._renderDiamond(nodeGroup, size, color, strokeWidth, strokeColor);
        break;
      case 'star':
        this._renderStar(nodeGroup, size, color, strokeWidth, strokeColor);
        break;
    }

    // 添加图标
    if (icon) {
      nodeGroup.append('text')
        .attr('text-anchor', 'middle')
        .attr('dy', '0.35em')
        .attr('font-size', size * 0.6)
        .text(icon);
    }

    // 添加标签
    nodeGroup.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', size + 15)
      .attr('font-size', 12)
      .text(label);

    return nodeGroup;
  }

  _renderCircle(group, size, color, strokeWidth, strokeColor) {
    group.append('circle')
      .attr('r', size)
      .attr('fill', color)
      .attr('stroke', strokeColor)
      .attr('stroke-width', strokeWidth);
  }

  _renderRect(group, size, color, strokeWidth, strokeColor) {
    group.append('rect')
      .attr('x', -size)
      .attr('y', -size)
      .attr('width', size * 2)
      .attr('height', size * 2)
      .attr('rx', 5)
      .attr('fill', color)
      .attr('stroke', strokeColor)
      .attr('stroke-width', strokeWidth);
  }

  _renderDiamond(group, size, color, strokeWidth, strokeColor) {
    const points = `0,${-size} ${size},0 0,${size} ${-size},0`;
    group.append('polygon')
      .attr('points', points)
      .attr('fill', color)
      .attr('stroke', strokeColor)
      .attr('stroke-width', strokeWidth);
  }

  _renderStar(group, size, color, strokeWidth, strokeColor) {
    const star = d3.symbol().type(d3.symbolStar).size(size * size * 2);
    group.append('path')
      .attr('d', star)
      .attr('fill', color)
      .attr('stroke', strokeColor)
      .attr('stroke-width', strokeWidth);
  }
}
```

#### 7.1.2 节点样式配置

```javascript
// frontend/src/config/nodeStyles.js

export const NODE_STYLES = {
  advisor: {
    shape: 'circle',
    size: 35,
    color: '#2196F3',
    icon: '👨‍🏫',
    label: '导师'
  },
  senior: {
    shape: 'rect',
    size: 28,
    color: '#4CAF50',
    icon: '🎓',
    label: '前辈'
  },
  proposal: {
    shape: 'diamond',
    size: 30,
    color: '#FF9800',
    icon: '📝',
    label: '论题'
  },
  literature: {
    shape: 'circle',
    size: 22,
    color: '#9C27B0',
    icon: '📄',
    label: '文献'
  },
  project: {
    shape: 'rect',
    size: 25,
    color: '#F44336',
    icon: '🔬',
    label: '项目'
  },
  current: {
    shape: 'star',
    size: 40,
    color: '#FFD700',
    icon: '⭐',
    label: '当前论题'
  }
};
```

### 7.2 边类型扩展

```javascript
// frontend/src/components/lineage/CustomEdgeRenderer.js

export class CustomEdgeRenderer {
  constructor(svg) {
    this.svg = svg;
  }

  renderEdge(edge, source, target, config = {}) {
    const {
      type = 'line',         // line | dashed | dotted | curved
      color = '#999',
      width = 2,
      arrow = true,
      label = ''
    } = config;

    // 创建路径
    let pathDef;
    switch (type) {
      case 'line':
        pathDef = `M${source.x},${source.y} L${target.x},${target.y}`;
        break;
      case 'curved':
        const dx = target.x - source.x;
        const dy = target.y - source.y;
        const dr = Math.sqrt(dx * dx + dy * dy);
        pathDef = `M${source.x},${source.y} A${dr},${dr} 0 0,1 ${target.x},${target.y}`;
        break;
      default:
        pathDef = `M${source.x},${source.y} L${target.x},${target.y}`;
    }

    // 绘制路径
    const path = this.svg.append('path')
      .attr('d', pathDef)
      .attr('fill', 'none')
      .attr('stroke', color)
      .attr('stroke-width', width);

    // 设置线型
    if (type === 'dashed') {
      path.attr('stroke-dasharray', '10,5');
    } else if (type === 'dotted') {
      path.attr('stroke-dasharray', '2,3');
    }

    // 添加箭头
    if (arrow) {
      path.attr('marker-end', 'url(#arrow)');
    }

    // 添加标签
    if (label) {
      const midX = (source.x + target.x) / 2;
      const midY = (source.y + target.y) / 2;
      this.svg.append('text')
        .attr('x', midX)
        .attr('y', midY - 5)
        .attr('text-anchor', 'middle')
        .attr('font-size', 10)
        .attr('fill', '#666')
        .text(label);
    }

    return path;
  }
}

// 边类型配置
export const EDGE_STYLES = {
  mentor_student: { type: 'line', color: '#2196F3', width: 3, label: '指导' },
  inheritance: { type: 'dashed', color: '#4CAF50', width: 2, label: '继承' },
  citation: { type: 'dotted', color: '#9C27B0', width: 1, label: '引用' },
  project_relation: { type: 'line', color: '#F44336', width: 3, label: '关联' }
};
```

### 7.3 布局算法切换

```javascript
// frontend/src/components/lineage/LayoutManager.js

import * as d3 from 'd3';

export class LayoutManager {
  constructor(width, height) {
    this.width = width;
    this.height = height;
  }

  forceLayout(nodes, links) {
    """力导向布局"""
    const simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id(d => d.id).distance(100))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(this.width / 2, this.height / 2))
      .force('collision', d3.forceCollide().radius(40));

    return simulation;
  }

  treeLayout(nodes, links) {
    """树形布局"""
    const root = d3.hierarchy({ children: nodes });
    const treeLayout = d3.tree().size([this.height, this.width - 200]);
    const treeData = treeLayout(root);

    return treeData;
  }

  radialLayout(nodes, links) {
    """径向布局"""
    const root = d3.hierarchy({ children: nodes });
    const treeLayout = d3.tree()
      .size([2 * Math.PI, Math.min(this.width, this.height) / 2 - 100]);
    const treeData = treeLayout(root);

    // 转换为笛卡尔坐标
    treeData.each(d => {
      d.x = d.x * 180 / Math.PI;
    });

    return treeData;
  }

  clusterLayout(nodes, links) {
    """聚类布局"""
    // 按类型分组
    const groups = {};
    nodes.forEach(node => {
      const type = node.type || 'default';
      if (!groups[type]) groups[type] = [];
      groups[type].push(node);
    });

    // 为每组分配中心点
    const groupKeys = Object.keys(groups);
    const angleStep = 2 * Math.PI / groupKeys.length;
    const radius = Math.min(this.width, this.height) / 3;

    groupKeys.forEach((key, i) => {
      const centerX = this.width / 2 + radius * Math.cos(i * angleStep);
      const centerY = this.height / 2 + radius * Math.sin(i * angleStep);

      groups[key].forEach((node, j) => {
        const nodeRadius = 50;
        const nodeAngle = 2 * Math.PI * j / groups[key].length;
        node.x = centerX + nodeRadius * Math.cos(nodeAngle);
        node.y = centerY + nodeRadius * Math.sin(nodeAngle);
      });
    });

    return nodes;
  }
}
```

### 7.4 导出 SVG 与交互

```javascript
// frontend/src/utils/svgExporter.js

export class SVGExporter {
  static exportSVG(svgElement, filename = 'lineage.svg') {
    // 克隆 SVG
    const clone = svgElement.cloneNode(true);

    // 添加 XML 声明
    const xmlDeclaration = '<?xml version="1.0" encoding="UTF-8"?>\n';
    const svgDoctype = '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">\n';

    // 序列化
    const serializer = new XMLSerializer();
    const svgString = xmlDeclaration + svgDoctype + serializer.serializeToString(clone);

    // 创建下载链接
    const blob = new Blob([svgString], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();

    URL.revokeObjectURL(url);
  }

  static exportPNG(svgElement, filename = 'lineage.png', scale = 2) {
    const serializer = new XMLSerializer();
    const svgString = serializer.serializeToString(svgElement);

    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    const img = new Image();

    img.onload = () => {
      const rect = svgElement.getBoundingClientRect();
      canvas.width = rect.width * scale;
      canvas.height = rect.height * scale;

      ctx.scale(scale, scale);
      ctx.fillStyle = '#fff';
      ctx.fillRect(0, 0, rect.width, rect.height);
      ctx.drawImage(img, 0, 0);

      canvas.toBlob(blob => {
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        link.click();
        URL.revokeObjectURL(url);
      });
    };

    img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svgString)));
  }
}
```

---

## 8. 多模型策略

### 8.1 步骤路由配置

#### 8.1.1 路由配置文件

```python
# backend/config/model_routing.py

from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class ModelConfig:
    """模型配置"""
    name: str
    provider: str
    api_key: str
    base_url: str
    max_tokens: int
    cost_per_1k_input: float
    cost_per_1k_output: float
    supports_cache: bool = False
    timeout: int = 60

@dataclass
class RoutingRule:
    """路由规则"""
    stage: str
    model: str
    fallback_model: Optional[str] = None
    condition: Optional[str] = None  # 条件表达式

class ModelRouter:
    """模型路由器"""

    def __init__(self, models: Dict[str, ModelConfig], rules: List[RoutingRule]):
        self.models = models
        self.rules = {rule.stage: rule for rule in rules}

    def get_model(self, stage: str, context: dict = None) -> ModelConfig:
        """获取阶段对应的模型"""
        rule = self.rules.get(stage)
        if not rule:
            # 默认模型
            return self.models.get("deepseek-r2")

        # 检查条件
        if rule.condition and context:
            try:
                if not eval(rule.condition, {}, context):
                    # 条件不满足，使用 fallback
                    if rule.fallback_model:
                        return self.models.get(rule.fallback_model)
            except:
                pass

        return self.models.get(rule.model)

    def get_fallback(self, stage: str) -> Optional[ModelConfig]:
        """获取 fallback 模型"""
        rule = self.rules.get(stage)
        if rule and rule.fallback_model:
            return self.models.get(rule.fallback_model)
        return None

# 默认路由配置
DEFAULT_ROUTING_RULES = [
    RoutingRule(
        stage="information_confirmation",
        model="deepseek-r2",
        fallback_model="gpt-4.1"
    ),
    RoutingRule(
        stage="ideation",
        model="claude-opus-4.5",
        fallback_model="gpt-4.1",
        condition="degree == 'doctor'"  # 博士用 Claude，硕士用 fallback
    ),
    RoutingRule(
        stage="validation",
        model="deepseek-r2",
        fallback_model="gpt-4.1"
    ),
    RoutingRule(
        stage="generation",
        model="gpt-4.1",
        fallback_model="claude-opus-4.5"
    ),
    RoutingRule(
        stage="deep_assistance",
        model="claude-opus-4.5",
        fallback_model="gpt-4.1"
    ),
]
```

### 8.2 模型 A/B 测试

```python
# backend/experiments/ab_test.py

import random
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ABTestConfig:
    """A/B 测试配置"""
    name: str
    stage: str
    model_a: str
    model_b: str
    ratio_a: float = 0.5  # 模型 A 的流量比例
    start_time: datetime = None
    end_time: datetime = None
    enabled: bool = True

class ABTestManager:
    """A/B 测试管理器"""

    def __init__(self):
        self.tests: Dict[str, ABTestConfig] = {}
        self.results: Dict[str, List[dict]] = {}

    def create_test(self, config: ABTestConfig):
        """创建 A/B 测试"""
        self.tests[config.name] = config
        self.results[config.name] = []

    def get_model(self, stage: str, user_id: str) -> str:
        """获取 A/B 测试中的模型"""
        for test in self.tests.values():
            if test.enabled and test.stage == stage:
                # 基于 user_id 确定性分配（同一用户始终用同一模型）
                hash_val = hash(user_id + test.name) % 100
                if hash_val < test.ratio_a * 100:
                    model = test.model_a
                else:
                    model = test.model_b

                # 记录分配
                self.results[test.name].append({
                    "user_id": user_id,
                    "model": model,
                    "timestamp": datetime.now()
                })

                return model

        return None  # 无 A/B 测试，使用默认路由

    def record_outcome(
        self,
        test_name: str,
        user_id: str,
        metrics: dict
    ):
        """记录测试结果"""
        for result in self.results.get(test_name, []):
            if result["user_id"] == user_id and "metrics" not in result:
                result["metrics"] = metrics
                break

    def get_results(self, test_name: str) -> dict:
        """获取测试结果"""
        results = self.results.get(test_name, [])
        if not results:
            return {}

        model_a_results = [r for r in results if r["model"] == self.tests[test_name].model_a]
        model_b_results = [r for r in results if r["model"] == self.tests[test_name].model_b]

        def avg_metric(results_list, metric_name):
            values = [r.get("metrics", {}).get(metric_name, 0) for r in results_list]
            return sum(values) / len(values) if values else 0

        return {
            "test_name": test_name,
            "model_a": self.tests[test_name].model_a,
            "model_b": self.tests[test_name].model_b,
            "count_a": len(model_a_results),
            "count_b": len(model_b_results),
            "avg_score_a": avg_metric(model_a_results, "score"),
            "avg_score_b": avg_metric(model_b_results, "score"),
            "avg_cost_a": avg_metric(model_a_results, "cost"),
            "avg_cost_b": avg_metric(model_b_results, "cost"),
            "avg_latency_a": avg_metric(model_a_results, "latency"),
            "avg_latency_b": avg_metric(model_b_results, "latency")
        }
```

### 8.3 降级策略

```python
# backend/resilience/fallback.py

import asyncio
from typing import List, Optional, Callable
from dataclasses import dataclass

@dataclass
class FallbackConfig:
    """降级配置"""
    primary_model: str
    fallback_models: List[str]
    retry_count: int = 3
    retry_delay: float = 1.0
    timeout: int = 60

class FallbackExecutor:
    """降级执行器"""

    def __init__(self, config: FallbackConfig):
        self.config = config

    async def execute_with_fallback(
        self,
        execute_fn: Callable,
        input_data: str
    ) -> dict:
        """带降级的执行

        Args:
            execute_fn: 执行函数，接受 (model, input) 参数
            input_data: 输入数据

        Returns:
            执行结果
        """
        models_to_try = [self.config.primary_model] + self.config.fallback_models

        last_error = None
        for model in models_to_try:
            for attempt in range(self.config.retry_count):
                try:
                    result = await asyncio.wait_for(
                        execute_fn(model, input_data),
                        timeout=self.config.timeout
                    )
                    return {
                        "success": True,
                        "model": model,
                        "result": result,
                        "attempts": attempt + 1
                    }
                except asyncio.TimeoutError:
                    last_error = f"模型 {model} 超时"
                    print(f"[Fallback] {last_error}（尝试 {attempt + 1}/{self.config.retry_count}）")
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                except Exception as e:
                    last_error = f"模型 {model} 错误：{str(e)}"
                    print(f"[Fallback] {last_error}")
                    break  # 非超时错误，直接尝试下一个模型

            print(f"[Fallback] 模型 {model} 失败，尝试下一个模型")

        return {
            "success": False,
            "error": last_error,
            "models_tried": models_to_try
        }
```

### 8.4 成本优化

```python
# backend/optimization/cost_optimizer.py

from typing import Dict, List
from datetime import datetime, timedelta

class CostOptimizer:
    """成本优化器"""

    def __init__(self, budget_ledger):
        self.ledger = budget_ledger

    def analyze_costs(self, days: int = 7) -> dict:
        """分析成本"""
        cutoff = datetime.now() - timedelta(days=days)
        records = self.ledger.get_records(since=cutoff)

        # 按模型统计
        by_model = {}
        for r in records:
            model = r["model"]
            if model not in by_model:
                by_model[model] = {"tokens": 0, "cost": 0, "count": 0}
            by_model[model]["tokens"] += r["total_tokens"]
            by_model[model]["cost"] += r["cost_usd"]
            by_model[model]["count"] += 1

        # 按阶段统计
        by_stage = {}
        for r in records:
            stage = r["stage"]
            if stage not in by_stage:
                by_stage[stage] = {"tokens": 0, "cost": 0}
            by_stage[stage]["tokens"] += r["total_tokens"]
            by_stage[stage]["cost"] += r["cost_usd"]

        # 计算优化建议
        suggestions = self._generate_suggestions(by_model, by_stage)

        return {
            "total_cost": sum(r["cost_usd"] for r in records),
            "total_tokens": sum(r["total_tokens"] for r in records),
            "by_model": by_model,
            "by_stage": by_stage,
            "suggestions": suggestions
        }

    def _generate_suggestions(self, by_model: dict, by_stage: dict) -> List[dict]:
        """生成优化建议"""
        suggestions = []

        # 建议 1：高成本模型替换
        for model, stats in by_model.items():
            if stats["cost"] / stats["tokens"] > 0.00003:  # 高单价
                suggestions.append({
                    "type": "model_replacement",
                    "priority": "high",
                    "message": f"模型 {model} 单价较高，考虑替换为更经济的模型",
                    "potential_savings": stats["cost"] * 0.5
                })

        # 建议 2：缓存命中率低的阶段
        for stage, stats in by_stage.items():
            if stats["tokens"] > 100000:  # 高用量
                suggestions.append({
                    "type": "cache_optimization",
                    "priority": "medium",
                    "message": f"阶段 {stage} 用量高，建议优化缓存",
                    "potential_savings": stats["cost"] * 0.3
                })

        return suggestions
```

---

## 9. 编排状态机与 Hook

### 9.1 OrchestrationStateMachine 原理

```python
# backend/orchestrator/state_machine.py

from enum import Enum
from typing import Dict, List, Callable, Optional
from dataclasses import dataclass, field

class State(Enum):
    """编排状态"""
    IDLE = "idle"
    INFORMATION_CONFIRMATION = "information_confirmation"
    IDEATION = "ideation"
    VALIDATION = "validation"
    GENERATION = "generation"
    DEEP_ASSISTANCE = "deep_assistance"
    COMPLETED = "completed"
    FAILED = "failed"

class EventType(Enum):
    """事件类型"""
    ENTER_STATE = "enter_state"
    EXIT_STATE = "exit_state"
    PRE_SEARCH = "pre_search"
    POST_REASONER = "post_reasoner"
    FEASIBILITY = "feasibility"
    HARD_RULE = "hard_rule"

@dataclass
class Transition:
    """状态转换"""
    from_state: State
    to_state: State
    event: str
    condition: Optional[Callable] = None
    action: Optional[Callable] = None

class OrchestrationStateMachine:
    """编排状态机"""

    # 状态转换表
    TRANSITIONS = [
        Transition(State.IDLE, State.INFORMATION_CONFIRMATION, "start"),
        Transition(State.INFORMATION_CONFIRMATION, State.IDEATION, "confirmed"),
        Transition(State.IDEATION, State.VALIDATION, "idea_selected"),
        Transition(State.VALIDATION, State.GENERATION, "validation_passed"),
        Transition(State.VALIDATION, State.IDEATION, "validation_failed"),  # 回退
        Transition(State.GENERATION, State.DEEP_ASSISTANCE, "generation_completed"),
        Transition(State.DEEP_ASSISTANCE, State.COMPLETED, "assistance_completed"),
        Transition(State.DEEP_ASSISTANCE, State.COMPLETED, "skip_assistance"),
        # 任意状态都可以失败
        Transition(State.INFORMATION_CONFIRMATION, State.FAILED, "error"),
        Transition(State.IDEATION, State.FAILED, "error"),
        Transition(State.VALIDATION, State.FAILED, "error"),
        Transition(State.GENERATION, State.FAILED, "error"),
        Transition(State.DEEP_ASSISTANCE, State.FAILED, "error"),
    ]

    def __init__(self):
        self.current_state = State.IDLE
        self.hooks: Dict[EventType, List[Callable]] = {
            et: [] for et in EventType
        }
        self.history: List[dict] = []

    def register_hook(self, event_type: EventType, hook: Callable):
        """注册 Hook"""
        self.hooks[event_type].append(hook)

    async def transition(self, event: str, context: dict = None) -> bool:
        """触发状态转换"""
        # 查找转换
        transition = None
        for t in self.TRANSITIONS:
            if t.from_state == self.current_state and t.event == event:
                if t.condition is None or t.condition(context):
                    transition = t
                    break

        if not transition:
            return False

        # 执行 EXIT_STATE hooks
        await self._run_hooks(EventType.EXIT_STATE, {
            "from_state": self.current_state,
            "to_state": transition.to_state,
            "context": context
        })

        # 执行特定事件 hooks
        event_map = {
            "pre_search": EventType.PRE_SEARCH,
            "post_reasoner": EventType.POST_REASONER,
            "feasibility": EventType.FEASIBILITY,
            "hard_rule": EventType.HARD_RULE
        }
        if event in event_map:
            await self._run_hooks(event_map[event], context)

        # 执行转换动作
        if transition.action:
            await transition.action(context)

        # 更新状态
        old_state = self.current_state
        self.current_state = transition.to_state

        # 执行 ENTER_STATE hooks
        await self._run_hooks(EventType.ENTER_STATE, {
            "from_state": old_state,
            "to_state": self.current_state,
            "context": context
        })

        # 记录历史
        self.history.append({
            "from_state": old_state,
            "to_state": self.current_state,
            "event": event,
            "timestamp": datetime.now()
        })

        return True

    async def _run_hooks(self, event_type: EventType, data: dict):
        """执行 Hooks"""
        for hook in self.hooks[event_type]:
            try:
                result = hook(data)
                if hasattr(result, "__await__"):
                    await result
            except Exception as e:
                print(f"[Hook] {event_type.value} hook 执行失败：{e}")
```

### 9.2 Hook 机制详解

#### 9.2.1 内置 Hook 类型

| Hook 类型 | 触发时机 | 用途 |
|-----------|----------|------|
| `ENTER_STATE` | 进入新状态时 | 初始化资源、记录日志 |
| `EXIT_STATE` | 离开当前状态时 | 清理资源、保存状态 |
| `PRE_SEARCH` | 检索前 | 修改检索查询、添加过滤条件 |
| `POST_REASONER` | Reasoner 执行后 | 验证推理结果、补充信息 |
| `FEASIBILITY` | 可行性评估时 | 自定义评估逻辑 |
| `HARD_RULE` | 硬约束检查时 | 添加自定义约束 |

#### 9.2.2 Hook 执行流程

```
状态转换请求
    |
    v
+-------------------+
| 查找转换规则      |
+-------------------+
    |
    v
+-------------------+
| 执行 EXIT_STATE   |  <-- 离开旧状态
| hooks             |
+-------------------+
    |
    v
+-------------------+
| 执行特定事件      |  <-- 如 PRE_SEARCH
| hooks             |
+-------------------+
    |
    v
+-------------------+
| 执行转换动作      |
+-------------------+
    |
    v
+-------------------+
| 更新状态          |
+-------------------+
    |
    v
+-------------------+
| 执行 ENTER_STATE  |  <-- 进入新状态
| hooks             |
+-------------------+
    |
    v
+-------------------+
| 记录历史          |
+-------------------+
```

### 9.3 自定义 Hook 实现

```python
# backend/hooks/custom_hooks.py

from backend.orchestrator.state_machine import EventType, OrchestrationStateMachine
from datetime import datetime

# ============ 日志 Hook ============

async def logging_hook(data: dict):
    """日志记录 Hook"""
    print(f"[LOG] {datetime.now()} - {data}")

# ============ 审计 Hook ============

async def audit_hook(data: dict):
    """审计 Hook"""
    # 记录到审计日志
    audit_record = {
        "timestamp": datetime.now(),
        "event": data.get("event"),
        "from_state": data.get("from_state"),
        "to_state": data.get("to_state"),
        "user_id": data.get("context", {}).get("user_id"),
        "session_id": data.get("context", {}).get("session_id")
    }
    # 写入数据库...
    print(f"[AUDIT] {audit_record}")

# ============ 预算检查 Hook ============

async def budget_check_hook(data: dict):
    """预算检查 Hook"""
    context = data.get("context", {})
    session_id = context.get("session_id")

    if session_id:
        # 查询当前预算使用情况
        # used = await get_budget_used(session_id)
        # limit = await get_budget_limit(session_id)
        used = 50.0
        limit = 100.0

        if used >= limit * 0.9:
            print(f"[BUDGET] 警告：预算已使用 {used/limit*100:.1f}%")
        if used >= limit:
            raise Exception("预算超限，停止执行")

# ============ 检索增强 Hook ============

async def pre_search_hook(data: dict):
    """检索前增强 Hook"""
    context = data.get("context", {})
    query = context.get("query", "")

    # 添加同义词扩展
    synonyms = {
        "深度学习": ["deep learning", "神经网络"],
        "图像识别": ["image recognition", "计算机视觉"]
    }

    enhanced_query = query
    for term, syns in synonyms.items():
        if term in query:
            enhanced_query += " OR " + " OR ".join(syns)

    context["enhanced_query"] = enhanced_query
    print(f"[SEARCH] 增强查询：{enhanced_query}")

# ============ 可行性增强 Hook ============

async def feasibility_hook(data: dict):
    """可行性评估增强 Hook"""
    context = data.get("context", {})
    proposal = context.get("proposal", {})

    # 自定义可行性检查
    checks = []

    # 检查数据集可用性
    datasets = proposal.get("datasets", [])
    if not datasets:
        checks.append({"check": "dataset_available", "passed": False, "message": "未指定数据集"})

    # 检查计算资源
    requires_gpu = proposal.get("requires_gpu", False)
    has_gpu = context.get("has_gpu", False)
    if requires_gpu and not has_gpu:
        checks.append({"check": "gpu_available", "passed": False, "message": "需要 GPU 但不可用"})

    context["feasibility_checks"] = checks

    failed = [c for c in checks if not c["passed"]]
    if failed:
        print(f"[FEASIBILITY] 可行性检查失败：{failed}")

# ============ 注册 Hooks ============

def register_custom_hooks(state_machine: OrchestrationStateMachine):
    """注册自定义 Hooks"""
    state_machine.register_hook(EventType.ENTER_STATE, logging_hook)
    state_machine.register_hook(EventType.ENTER_STATE, audit_hook)
    state_machine.register_hook(EventType.ENTER_STATE, budget_check_hook)
    state_machine.register_hook(EventType.PRE_SEARCH, pre_search_hook)
    state_machine.register_hook(EventType.FEASIBILITY, feasibility_hook)

# 使用
state_machine = OrchestrationStateMachine()
register_custom_hooks(state_machine)

# 触发状态转换
await state_machine.transition("start", {"session_id": "sess_abc123"})
```

---

## 10. 性能调优实战

### 10.1 并发优化

```python
# backend/optimization/concurrency.py

import asyncio
from typing import List, Callable

class ConcurrencyOptimizer:
    """并发优化器"""

    @staticmethod
    async def run_with_semaphore(
        tasks: List[Callable],
        max_concurrent: int = 5
    ) -> List:
        """使用信号量控制并发"""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def run_one(task):
            async with semaphore:
                return await task()

        return await asyncio.gather(*[run_one(t) for t in tasks])

    @staticmethod
    async def run_with_rate_limit(
        tasks: List[Callable],
        rate_per_second: int = 10
    ) -> List:
        """速率限制执行"""
        results = []
        for i, task in enumerate(tasks):
            if i > 0 and i % rate_per_second == 0:
                await asyncio.sleep(1)
            results.append(await task())
        return results
```

### 10.2 数据库优化

```python
# backend/database/optimization.py

import sqlite3
from contextlib import contextmanager

class DatabaseOptimizer:
    """数据库优化器"""

    @staticmethod
    def enable_wal_mode(db_path: str):
        """启用 WAL 模式（提高并发性能）"""
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")  # 平衡安全性与性能
        conn.close()

    @staticmethod
    def create_indexes(db_path: str):
        """创建索引"""
        conn = sqlite3.connect(db_path)
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_budget_session ON budget_ledger(session_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_cache_key ON cache_entries(cache_key)"
        ]
        for idx_sql in indexes:
            conn.execute(idx_sql)
        conn.commit()
        conn.close()

    @staticmethod
    def analyze_query(db_path: str, query: str):
        """分析查询计划"""
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(f"EXPLAIN QUERY PLAN {query}")
        plan = cursor.fetchall()
        conn.close()
        return plan
```

### 10.3 前端性能优化

```javascript
// frontend/src/utils/performance.js

export class PerformanceOptimizer {
  // 虚拟滚动（大数据列表）
  static virtualScroll(container, items, renderItem, itemHeight = 50) {
    const visibleHeight = container.clientHeight;
    const visibleCount = Math.ceil(visibleHeight / itemHeight);

    let scrollTop = 0;

    container.addEventListener('scroll', () => {
      scrollTop = container.scrollTop;
      const startIdx = Math.floor(scrollTop / itemHeight);
      const endIdx = Math.min(startIdx + visibleCount, items.length);

      // 只渲染可见项
      const visibleItems = items.slice(startIdx, endIdx);
      container.innerHTML = visibleItems
        .map((item, i) => renderItem(item, startIdx + i))
        .join('');

      // 设置 padding 模拟完整列表
      container.style.paddingTop = `${startIdx * itemHeight}px`;
      container.style.paddingBottom = `${(items.length - endIdx) * itemHeight}px`;
    });
  }

  // 防抖
  static debounce(fn, delay = 300) {
    let timer;
    return function(...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), delay);
    };
  }

  // 节流
  static throttle(fn, delay = 100) {
    let lastCall = 0;
    return function(...args) {
      const now = Date.now();
      if (now - lastCall >= delay) {
        lastCall = now;
        return fn.apply(this, args);
      }
    };
  }

  // 懒加载
  static lazyLoad(elementSelector, callback) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          callback(entry.target);
          observer.unobserve(entry.target);
        }
      });
    });

    document.querySelectorAll(elementSelector).forEach(el => {
      observer.observe(el);
    });
  }
}
```

---

## 附录 A：高级配置参考

```yaml
# config/advanced.yml

# 高级配置示例
optimization:
  cache:
    enabled: true
    max_size: 5000
    ttl_seconds: 7200
    prefix_stability_threshold: 0.8

  concurrency:
    max_concurrent_agents: 5
    max_concurrent_api_calls: 10
    rate_limit_per_second: 20

  database:
    journal_mode: WAL
    synchronous: NORMAL
    cache_size: -64000  # 64MB

agents:
  custom_agents:
    - name: LiteratureAgent
      model: claude-opus-4.5
      temperature: 0.3
      max_tokens: 8192

  hooks:
    enter_state:
      - logging_hook
      - audit_hook
      - budget_check_hook
    pre_search:
      - pre_search_hook
    feasibility:
      - feasibility_hook

routing:
  ab_tests:
    - name: ideation_test
      stage: ideation
      model_a: claude-opus-4.5
      model_b: gpt-4.1
      ratio_a: 0.5

  fallback:
    primary: deepseek-r2
    fallbacks:
      - gpt-4.1
      - claude-opus-4.5
    retry_count: 3
    timeout: 60
```

---

## 附录 B：调试工具速查

| 工具 | 用途 | 使用方式 |
|------|------|----------|
| `agent.debug_prompt()` | 查看 Agent Prompt | `print(agent.debug_prompt(input))` |
| `agent.dry_run()` | 模拟 Agent 运行 | `await agent.dry_run(input)` |
| `CacheAnalyzer` | 分析缓存稳定性 | `CacheAnalyzer.analyze_prefix_stability(prompts)` |
| `CacheMonitor` | 监控缓存命中率 | `monitor.get_hit_rate(by_stage=True)` |
| `CostOptimizer` | 分析成本 | `optimizer.analyze_costs(days=7)` |
| `ABTestManager` | A/B 测试 | `manager.get_results(test_name)` |
| `DatabaseOptimizer` | 数据库优化 | `DatabaseOptimizer.enable_wal_mode(db_path)` |

---

> 本教程最后更新：2026-06-19
> 适用于 ThesisMiner v8.0 及以上版本
> 如需了解更多，请参阅 API 文档与架构文档
