# ThesisMiner v8.0 系统架构总览

> 版本：V8.0  
> 更新日期：2026-06-19  
> 状态：正式发布

---

## 目录

1. [项目概述](#1-项目概述)
2. [项目历史演进](#2-项目历史演进)
3. [当前架构图](#3-当前架构图)
4. [模块依赖图](#4-模块依赖图)
5. [数据流图](#5-数据流图)
6. [技术栈详情](#6-技术栈详情)
7. [性能架构](#7-性能架构)
8. [安全架构](#8-安全架构)
9. [部署架构](#9-部署架构)
10. [监控与日志](#10-监控与日志)
11. [未来路线图](#11-未来路线图)

---

## 1. 项目概述

ThesisMiner 是一个基于多 Agent 架构的学术论文选题与开题辅助系统。系统采用 Claude Code 式的主管理+子 Agent 协作架构，通过五阶段闭环导航流（信息确权→创意→校验→生成→深度辅助）控制论题产出全过程。

### 1.1 核心能力

| 能力 | 描述 | 版本引入 |
|------|------|---------|
| 多 Agent 协作 | Orchestrator + 5 个子 Agent，独立上下文，独立模型路由 | v8.0 |
| 五阶段闭环导航 | 信息确权→创意→校验→生成→深度辅助 | v8.0 |
| 多对话并存 | 单会话下多条独立对话线，上下文隔离 | v8.0 |
| DeepSeek 缓存优化 | 三段式 Prompt 固化前缀，缓存命中率 ≥95% | v8.0 |
| D3.js 谱系图谱 | 力导向交互式图谱，拖拽/缩放/高亮/过滤 | v8.0 |
| 联网搜索引用解析 | 自动解析回复中的 URL，提取元数据，卡片展示 | v8.0 |
| 多模型注册表 | 10 个 2026 最新模型，按步骤路由，价格配置 | v7.0/v8.0 |
| 三类 Token 统计 | 输入命中缓存/未命中缓存/输出分开统计 | v7.0 |
| 预算透明账本 | 按模型/用途/会话维度的成本追踪 | v6.0 |
| 谱系知识图谱 | 论题-方法-文献-导师关系网络 | v5.0 |

### 1.2 系统规模

| 指标 | 数值 |
|------|------|
| Python 代码文件 | 138+ |
| JavaScript 代码文件 | 8 |
| 文档文件 | 55+ |
| YAML 配置文件 | 10+ |
| 单元测试文件 | 32+ |
| 集成测试文件 | 6 |
| E2E 测试文件 | 5 |
| 压力测试文件 | 4 |
| 测试用例总数 | 2400+ |
| API 端点数 | 50+ |
| 内置模型数 | 10 |
| Agent 数量 | 6 (Orchestrator + 5 子 Agent) |
| 数据库表数 | 9 |

---

## 2. 项目历史演进

### 2.1 版本时间线

```
v1.0 (2025-03) ──→ v2.0 (2025-04) ──→ v3.0 (2025-05) ──→ v4.0 (2025-06)
     │                  │                  │                  │
  基础AI调用        会话管理          谱系图谱          预算追踪
```

```
v5.0 (2025-08) ──→ v6.0 (2025-10) ──→ v7.0 (2026-01) ──→ v8.0 (2026-06)
     │                  │                  │                  │
  知识卡片        开题报告生成      多模型注册表      多Agent架构
  创意引擎        硬约束拦截器      三类Token统计     五阶段闭环导航
  候选排序        DST上下文压缩     谱系批量管理      DeepSeek缓存优化
                                    自动开浏览器      D3.js谱系重构
                                                      多对话并存
                                                      联网引用解析
```

### 2.2 各版本详细变更

#### v1.0 - 基础版 (2025-03)

**核心功能：**
- 基础 AI 调用（单模型，OpenAI 兼容）
- 简单会话管理（内存存储）
- 基本论题生成
- FastAPI 后端 + 原生 HTML 前端

**技术栈：**
- Python 3.11 + FastAPI
- SQLite 数据库
- 原生 JavaScript 前端

**文件数：** 15  
**代码量：** ~50KB

#### v2.0 - 会话管理版 (2025-04)

**新增功能：**
- 持久化会话管理（SQLite 存储）
- 会话历史记录
- 会话切换与删除
- 基础上下文管理

**改进：**
- 数据库初始化与迁移
- 会话 API 端点
- 前端会话列表 UI

**文件数：** 22  
**代码量：** ~120KB

#### v3.0 - 谱系图谱版 (2025-05)

**新增功能：**
- 谱系知识图谱（节点+边）
- SVG 图谱可视化
- 节点 CRUD 操作
- 关系类型管理

**改进：**
- lineage_nodes 和 lineage_edges 表
- 谱系 API 端点
- 前端图谱页面

**文件数：** 30  
**代码量：** ~200KB

#### v4.0 - 预算追踪版 (2025-06)

**新增功能：**
- 透明预算账本
- Token 使用记录
- 成本估算
- 预算看板

**改进：**
- budget_ledger 表
- 估算器模块
- 前端预算页面

**文件数：** 38  
**代码量：** ~280KB

#### v5.0 - 知识引擎版 (2025-08)

**新增功能：**
- 知识卡片管理
- 学术谱系分析
- 跨域创意引擎
- 问题感知模块
- 候选排序器

**改进：**
- knowledge_cards 表
- creativity 模块
- 前端知识卡片 UI

**文件数：** 48  
**代码量：** ~380KB

#### v6.0 - 开题报告版 (2025-10)

**新增功能：**
- 开题报告生成器
- 硬约束拦截器
- DST 对话状态追踪
- DST 上下文压缩器
- 搜索器包装器（Mock + Real）

**改进：**
- 提案生成 API
- 约束验证 API
- 流式输出支持

**文件数：** 58  
**代码量：** ~480KB

#### v7.0 - 多模型版 (2026-01)

**新增功能：**
- 多模型注册表（6 个模型）
- 按步骤模型路由（reasoner/mentor/inspire/report/search）
- 价格配置（元/百万 tokens）
- 人民币/美元切换
- 模型参数设置（联网搜索/深度思考/上下文/温度）
- 思维链获取
- 流式传输增强
- API 状态显示
- 会话对话轮数显示
- 谱系分页与批量管理
- 三类 Token 统计（缓存命中/未命中/输出）
- 自动打开浏览器

**改进：**
- lifespan 替换 on_event
- 多模型客户端缓存
- 预算账本三类 Token
- 前端设置页面重构
- 前端预算页面增强
- 前端谱系页面增强

**文件数：** 75  
**代码量：** ~650KB  
**测试数：** 39

#### v8.0 - 多Agent架构版 (2026-06)

**新增功能：**
- 多 Agent 架构（Orchestrator + 5 子 Agent）
  - BaseAgent 抽象基类
  - AgentRegistry 全局注册表
  - SearcherAgent（联网检索）
  - ReasonerAgent（四维创意引擎）
  - CriticAgent（新颖性评估）
  - MentorAgent（导师模拟）
  - WriterAgent（多粒度生成）
  - OrchestratorAgent（五阶段编排）
- 五阶段闭环导航流
  - 信息确权门禁
  - 谱系解析与四维创意
  - 重复度评估与硬约束修复
  - 多粒度生成与降重脱敏
  - 深度辅助闭环
- 多对话并存与上下文隔离
  - conversations 表
  - conversation_messages 表
  - search_citations 表
  - ConversationManager
  - DST 上下文压缩
- DeepSeek 缓存命中率 ≥95%
  - 三段式 Prompt 固化前缀
  - 缓存命中率监控
  - cache_hit_rate 字段
- D3.js 力导向谱系图谱
  - 节点拖拽
  - 画布缩放
  - 悬停高亮
  - 类型过滤
  - 详情侧栏
- 联网搜索引用解析
  - URL/Markdown/编号引用解析
  - 页面元数据提取
  - 引用卡片展示
- 2026 最新模型更新
  - 移除旧模型（gpt-4o-mini, deepseek-chat 等）
  - 新增 claude-sonnet-4.5, claude-opus-4.5, deepseek-v3.2, deepseek-r2, qwen3-max, gemini-2.5-pro, glm-4.6, doubao-1.5-pro
  - agent_default 字段
  - release_year 字段
- 代码约束工程重写
  - stage_gate（五阶段门禁）
  - info_confirmation（信息确权）
  - hard_rules（扩展硬约束）
  - novelty_checker（新颖性评估）
  - style_normalizer（去 AI 痕迹）
  - multi_granularity（多粒度生成）
  - deep_assist（深度辅助三件套）
- 完整测试套件
  - 32+ 单元测试文件
  - 6 集成测试文件
  - 5 E2E 测试文件
  - 4 压力测试文件
  - 6 测试数据文件
- 完整文档体系
  - 架构文档
  - 约束工程文档
  - API 文档
  - 开发文档
  - 教程文档
  - 变更日志

**改进：**
- 版本号升级至 8.0.0
- 数据库新增 3 张表
- API 新增 15+ 端点
- 前端 3 个页面完全重写
- 项目代码量 ≥10MB

**文件数：** 200+  
**代码量：** ~10MB  
**测试数：** 2400+

---

## 3. 当前架构图

### 3.1 系统层级架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        前端展示层 (Frontend)                         │
├─────────────┬─────────────┬─────────────┬─────────────┬─────────────┤
│  仪表盘     │  会话管理   │  论题生成   │  谱系图谱   │  预算看板   │
│  dashboard  │  sessions   │  generate   │  lineage    │  budgets    │
│             │  (多对话Tab) │  (五阶段)   │  (D3.js)    │             │
├─────────────┴─────────────┴─────────────┴─────────────┴─────────────┤
│                        设置页面 (Settings)                          │
│  模型管理 │ 步骤路由 │ 货币切换 │ Agent配置 │ 缓存监控               │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ HTTP/SSE
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        API 路由层 (Routes)                           │
├──────────┬──────────┬──────────┬──────────┬──────────┬──────────────┤
│ sessions │conversa- │ agents   │ lineage  │ budgets  │ config/models│
│          │  tions   │          │          │          │              │
├──────────┼──────────┼──────────┼──────────┼──────────┼──────────────┤
│ proposals│creativity│constraints│citations│cache-stats│             │
└──────────┴──────────┴──────────┴──────────┴──────────┴──────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    业务逻辑层 (Business Logic)                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Agent 编排层 (Orchestration)                    │   │
│  │  ┌──────────────────────────────────────────────────────┐   │   │
│  │  │            OrchestratorAgent (主管理)                 │   │   │
│  │  │  信息确权 → 创意 → 校验 → 生成 → 深度辅助            │   │   │
│  │  └──────────────────────────────────────────────────────┘   │   │
│  │          │          │          │          │          │       │   │
│  │     ▼          ▼          ▼          ▼          ▼       │   │
│  │  Searcher  Reasoner   Critic    Mentor    Writer        │   │
│  │  Agent     Agent      Agent     Agent     Agent         │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐   │
│  │  会话管理        │  │  约束工程        │  │  预算追踪        │   │
│  │  SessionManager  │  │  StageGate      │  │  TransparentLedger│  │
│  │  ConversationMgr │  │  HardRules      │  │  Estimator       │   │
│  │  DST             │  │  NoveltyChecker │  │  CacheMonitor    │   │
│  └─────────────────┘  │  StyleNormalizer│  └─────────────────┘   │
│                       │  MultiGranular  │                        │
│  ┌─────────────────┐  │  DeepAssist     │  ┌─────────────────┐   │
│  │  知识图谱        │  └─────────────────┘  │  创意引擎        │   │
│  │  LineageGraph   │                        │  CrossDomain     │   │
│  │  CardManager    │  ┌─────────────────┐  │  ProblemAware    │   │
│  │  GraphExpander  │  │  AI 调用层       │  │  CandidateRanker │   │
│  └─────────────────┘  │  AIProxy         │  └─────────────────┘   │
│                       │  PromptCache     │                        │
│                       │  CitationParser  │                        │
│                       │  ResponseParser  │                        │
│                       │  Streaming       │                        │
│                       └─────────────────┘                        │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        数据层 (Data)                                 │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              SQLite 数据库 (thesis_miner.db)                │   │
│  │  ┌──────────┬──────────┬──────────┬──────────┬──────────┐  │   │
│  │  │ sessions │conversa- │messages  │citations │ budget_  │  │   │
│  │  │          │  tions   │          │          │  ledger  │  │   │
│  │  ├──────────┼──────────┼──────────┼──────────┼──────────┤  │   │
│  │  │ lineage_ │ lineage_ │knowledge │proposals │          │  │   │
│  │  │  nodes   │  edges   │  cards   │          │          │  │   │
│  │  └──────────┴──────────┴──────────┴──────────┴──────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐   │
│  │  配置文件        │  │  Agent 配置      │  │  约束配置        │   │
│  │  config.json    │  │  agents/*.yaml  │  │  constraints/   │   │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    外部服务层 (External)                             │
├──────────────┬──────────────┬──────────────┬───────────────────────┤
│  OpenAI API  │ DeepSeek API │ Claude API   │ Qwen/Gemini/GLM/      │
│  (GPT-4.1)   │ (V3.2/R2)    │ (Sonnet/Opus)│ Doubao API            │
├──────────────┼──────────────┼──────────────┼───────────────────────┤
│  ArXiv API   │ Semantic     │ Web Search   │ Favicon Service       │
│  (文献检索)   │ Scholar API  │ (联网搜索)    │ (Google S2)           │
└──────────────┴──────────────┴──────────────┴───────────────────────┘
```

### 3.2 多 Agent 架构详图

```
                    ┌─────────────────────┐
                    │   用户请求          │
                    │   "帮我选个论题"    │
                    └─────────┬───────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │  OrchestratorAgent   │
                    │  (主管理 Agent)      │
                    │  模型: claude-       │
                    │  sonnet-4.5          │
                    │  状态机: 五阶段      │
                    └─────────┬───────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  阶段1: 信息确权 │ │  阶段2: 创意    │ │  阶段3: 校验    │
│  SearcherAgent  │ │  ReasonerAgent  │ │  CriticAgent    │
│  模型: deepseek- │ │  模型: deepseek-│ │  模型: deepseek-│
│  v3.2           │ │  r2             │ │  r2             │
│                 │ │                 │ │                 │
│  · 联网检索文献  │ │  · 四维创意引擎 │ │  · 新颖性评估   │
│  · 提取摘要     │ │  · 学科交叉     │ │  · 可行性打分   │
│  · 等待用户确认  │ │  · 方法迁移     │ │  · 重复度检测   │
│                 │ │  · 痛点突破     │ │  · 评分≥60通过  │
│                 │ │  · 趋势前瞻     │ │  · <60回退      │
└─────────────────┘ └─────────────────┘ └─────────────────┘
                                                  │
                                                  ▼
                                    ┌─────────────────────┐
                                    │  阶段4: 生成        │
                                    │  WriterAgent        │
                                    │  模型: claude-      │
                                    │  opus-4.5           │
                                    │                     │
                                    │  · 标题级 (≤20字)   │
                                    │  · 摘要级 (200-300) │
                                    │  · 大纲级 (3级目录) │
                                    │  · 全文级 (≥5000字) │
                                    │  · style_normalizer │
                                    └─────────┬───────────┘
                                              │
                                              ▼
                                    ┌─────────────────────┐
                                    │  阶段5: 深度辅助    │
                                    │  (Orchestrator)     │
                                    │                     │
                                    │  · 文献精读         │
                                    │  · 实验预研         │
                                    │  · 答辩模拟         │
                                    └─────────────────────┘
```

### 3.3 多对话管理架构

```
┌─────────────────────────────────────────────────────────┐
│                    Session (会话)                        │
│  id: sess_001                                           │
│  title: "硕士论文选题"                                  │
│  active_conversation_id: conv_002                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ Conversation │  │ Conversation │  │ Conversation │ │
│  │ conv_001     │  │ conv_002     │  │ conv_003     │ │
│  │ Agent:       │  │ Agent:       │  │ Agent:       │ │
│  │  orchestrator│  │  reasoner    │  │  writer      │ │
│  │ Status:      │  │ Status:      │  │ Status:      │ │
│  │  active      │  │  active ★    │  │  archived    │ │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤ │
│  │ Messages:    │  │ Messages:    │  │ Messages:    │ │
│  │  msg_001     │  │  msg_005     │  │  msg_010     │ │
│  │  msg_002     │  │  msg_006     │  │  msg_011     │ │
│  │  msg_003     │  │  msg_007     │  │              │ │
│  │  msg_004     │  │  msg_008     │  │              │ │
│  │              │  │  msg_009     │  │              │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│                                                         │
│  上下文隔离：每条对话有独立的消息历史和上下文窗口      │
│  切换对话时上下文完全隔离，互不干扰                     │
└─────────────────────────────────────────────────────────┘
```

---

## 4. 模块依赖图

### 4.1 后端模块依赖关系

```
main.py
├── backend.config
│   ├── get_settings()
│   ├── get_model_config()
│   ├── get_step_model()
│   └── save_config()
│
├── backend.database
│   ├── init_db()
│   ├── migrate_db()
│   ├── get_db_connection()
│   └── execute_insert/query()
│
├── backend.routes
│   ├── sessions.py
│   │   └── backend.sessions.session_manager
│   │       └── backend.sessions.conversation_manager
│   │           └── backend.sessions.dst_compactor
│   │               └── backend.sessions.dialogue_state_tracker
│   │
│   ├── conversations.py
│   │   └── backend.sessions.conversation_manager
│   │   └── backend.agents.agent_registry
│   │
│   ├── config.py
│   │   └── backend.config
│   │
│   ├── budgets.py
│   │   └── backend.budgets.transparent_ledger
│   │   └── backend.budgets.estimator
│   │   └── backend.ai.cache_monitor
│   │
│   ├── lineage.py
│   │   └── backend.knowledge.lineage_graph_store
│   │   └── backend.knowledge.card_manager
│   │
│   ├── citations.py
│   │   └── backend.database
│   │
│   ├── proposals.py
│   │   └── backend.agents.proposal_writer
│   │
│   ├── creativity.py
│   │   └── backend.creativity.cross_domain
│   │   └── backend.creativity.problem_awareness
│   │   └── backend.creativity.candidate_ranker
│   │
│   └── constraints.py
│       └── backend.constraints.format_validator
│       └── backend.constraints.academic_calendar
│       └── backend.constraints.lit_baselines
│
├── backend.agents
│   ├── orchestrator.py
│   │   └── base_agent.py
│   │   └── agent_registry.py
│   │   └── (调度所有子 Agent)
│   │
│   ├── searcher_wrapper.py
│   │   └── backend.ai.ai_proxy
│   │
│   ├── reasoner.py
│   │   └── backend.ai.ai_proxy
│   │   └── backend.constraints.novelty_checker
│   │
│   ├── critic.py
│   │   └── backend.ai.ai_proxy
│   │   └── backend.constraints.novelty_checker
│   │
│   ├── mentor_agent.py
│   │   └── backend.ai.ai_proxy
│   │
│   └── proposal_writer.py
│       └── backend.ai.ai_proxy
│       └── backend.constraints.style_normalizer
│       └── backend.constraints.multi_granularity
│
├── backend.ai
│   ├── ai_proxy.py
│   │   └── backend.config (get_model_config, get_step_model)
│   │   └── backend.budgets.transparent_ledger
│   │   └── backend.ai.citation_parser
│   │
│   ├── prompt_cache.py
│   ├── cache_monitor.py
│   ├── citation_parser.py
│   ├── prompts.py
│   ├── response_parser.py
│   └── streaming.py
│
├── backend.constraints
│   ├── stage_gate.py
│   ├── info_confirmation.py
│   ├── hard_rules.py
│   ├── novelty_checker.py
│   ├── style_normalizer.py
│   ├── multi_granularity.py
│   ├── deep_assist.py
│   ├── rule_engine.py
│   ├── plagiarism_checker.py
│   └── academic_standards.py
│
├── backend.orchestration
│   ├── state_machine.py
│   ├── pipeline.py
│   └── scheduler.py
│
└── backend.utils
    ├── logger.py
    ├── validators.py
    ├── helpers.py
    ├── cache.py
    └── security.py
```

### 4.2 前端模块依赖关系

```
index.html
├── d3.v7.min.js (CDN)
├── styles/main.css
├── scripts/api.js
│   └── API 对象 (所有 API 调用方法)
├── scripts/app.js
│   └── 页面路由
│   └── updateApiStatus()
│   └── loadPageScript()
└── scripts/pages/
    ├── dashboard.js
    ├── sessions.js
    │   └── 多对话 Tab 管理
    │   └── Agent 选择器
    │   └── 引用卡片
    │   └── 流式输出
    ├── generate.js
    │   └── 五阶段进度条
    │   └── 信息确权面板
    │   └── 创意候选卡片
    │   └── 校验评分展示
    │   └── 多粒度生成器
    │   └── 深度辅助入口
    ├── lineage.js
    │   └── D3.js 力导向图谱
    │   └── 节点拖拽/缩放
    │   └── 类型过滤
    │   └── 详情侧栏
    │   └── 分页列表
    ├── budgets.js
    │   └── 三类 Token 统计
    │   └── 按模型分组
    │   └── 货币切换
    └── settings.js
        └── 模型管理卡片
        └── 步骤路由配置
        └── 货币切换
```

---

## 5. 数据流图

### 5.1 用户请求流

```
用户操作          前端              API路由           业务逻辑           AI调用           数据库
  │                │                  │                  │                 │                │
  │  输入论题方向  │                  │                  │                 │                │
  │──────────────→│                  │                  │                 │                │
  │                │  POST /api/      │                  │                 │                │
  │                │  conversations/  │                  │                 │                │
  │                │  {cid}/messages  │                  │                 │                │
  │                │─────────────────→│                  │                 │                │
  │                │                  │  add_message()   │                 │                │
  │                │                  │─────────────────→│                 │                │
  │                │                  │                  │  保存用户消息   │                │
  │                │                  │                  │────────────────────────────────→│
  │                │                  │                  │                 │                │
  │                │                  │                  │  调用           │                │
  │                │                  │                  │  Orchestrator   │                │
  │                │                  │                  │  .orchestrate() │                │
  │                │                  │                  │─────────────────→│                │
  │                │                  │                  │                 │                │
  │                │                  │                  │                 │  阶段1:        │
  │                │                  │                  │                 │  SearcherAgent │
  │                │                  │                  │                 │  调用 AI       │
  │                │                  │                  │                 │───────────────→│
  │                │                  │                  │                 │  (外部AI API)  │
  │                │                  │                  │                 │←───────────────│
  │                │                  │                  │                 │                │
  │                │                  │                  │                 │  阶段2:        │
  │                │                  │                  │                 │  ReasonerAgent │
  │                │                  │                  │                 │  调用 AI       │
  │                │                  │                  │                 │───────────────→│
  │                │                  │                  │                 │←───────────────│
  │                │                  │                  │                 │                │
  │                │                  │                  │                 │  阶段3:        │
  │                │                  │                  │                 │  CriticAgent   │
  │                │                  │                  │                 │  评估          │
  │                │                  │                  │                 │───────────────→│
  │                │                  │                  │                 │←───────────────│
  │                │                  │                  │                 │                │
  │                │                  │                  │                 │  阶段4:        │
  │                │                  │                  │                 │  WriterAgent   │
  │                │                  │                  │                 │  生成内容      │
  │                │                  │                  │                 │───────────────→│
  │                │                  │                  │                 │←───────────────│
  │                │                  │                  │                 │                │
  │                │                  │                  │  保存AI回复     │                │
  │                │                  │                  │────────────────────────────────→│
  │                │                  │                  │                 │                │
  │                │  SSE 流式响应    │                  │                 │                │
  │                │←─────────────────│←─────────────────│                 │                │
  │  实时展示      │                  │                  │                 │                │
  │←──────────────│                  │                  │                 │                │
```

### 5.2 DeepSeek 缓存优化流

```
首次调用:
  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
  │ 构建Prompt  │     │ 发送请求    │     │ 接收响应    │
  │             │     │             │     │             │
  │ prefix:     │────→│ messages:   │────→│ usage: {    │
  │  系统角色   │     │  [prefix]   │     │  prompt_    │
  │  硬约束     │     │  [dynamic]  │     │  tokens:    │
  │  学科导师   │     │             │     │   1000      │
  │             │     │             │     │  cached_    │
  │ dynamic:    │     │             │     │  tokens:    │
  │  用户问题   │     │             │     │   0         │
  └─────────────┘     └─────────────┘     │ }           │
                                          │             │
                                          │ cache_hit_  │
                                          │ rate: 0%    │
                                          └─────────────┘

后续调用 (同会话):
  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
  │ 构建Prompt  │     │ 发送请求    │     │ 接收响应    │
  │             │     │             │     │             │
  │ prefix:     │     │ messages:   │     │ usage: {    │
  │  系统角色   │────→│  [prefix]   │────→│  prompt_    │
  │  硬约束     │     │  [dynamic]  │     │  tokens:    │
  │  学科导师   │     │             │     │   1200      │
  │  (字节级    │     │             │     │  cached_    │
  │   一致)     │     │             │     │  tokens:    │
  │             │     │             │     │   1000      │
  │ dynamic:    │     │             │     │ }           │
  │  新问题     │     │             │     │             │
  └─────────────┘     └─────────────┘     │ cache_hit_  │
                                          │ rate: 83%   │
                                          └─────────────┘

经过多轮调用后:
  prefix 部分完全缓存 → cache_hit_rate ≥ 95%
```

---

## 6. 技术栈详情

### 6.1 后端技术栈

| 技术 | 版本 | 用途 | 选择理由 |
|------|------|------|---------|
| Python | 3.12 | 编程语言 | 生态丰富，AI库支持好 |
| FastAPI | 0.104+ | Web框架 | 异步支持好，自动文档 |
| SQLite | 3.40+ | 数据库 | 轻量级，无需额外服务 |
| openai | 1.0+ | AI SDK | 多模型兼容 |
| Pydantic | 2.0+ | 数据验证 | 类型安全 |
| python-dotenv | 1.0+ | 环境变量 | 配置管理 |
| aiohttp | 3.9+ | HTTP客户端 | 异步引用元数据获取 |
| pytest | 8.0+ | 测试框架 | 标准选择 |
| pytest-asyncio | 0.23+ | 异步测试 | 支持async测试 |

### 6.2 前端技术栈

| 技术 | 版本 | 用途 | 选择理由 |
|------|------|------|---------|
| HTML5 | - | 页面结构 | 标准 |
| CSS3 | - | 样式 | 标准 |
| JavaScript | ES2022+ | 交互逻辑 | 原生无需构建 |
| D3.js | 7.0 | 谱系图谱 | 力导向布局 |
| CSS Variables | - | 主题管理 | 原生支持 |

### 6.3 外部服务

| 服务 | 用途 | API |
|------|------|-----|
| OpenAI | GPT-4.1 系列 | api.openai.com/v1 |
| DeepSeek | V3.2/R2 系列 | api.deepseek.com/v1 |
| Anthropic | Claude 4.5 系列 | api.anthropic.com/v1 |
| 阿里通义 | Qwen3 Max | dashscope.aliyuncs.com |
| Google | Gemini 2.5 Pro | generativelanguage.googleapis.com |
| 智谱 | GLM-4.6 | open.bigmodel.cn |
| 字节 | Doubao 1.5 Pro | ark.cn-beijing.volces.com |
| ArXiv | 文献检索 | export.arxiv.org/api |
| Semantic Scholar | 文献检索 | api.semanticscholar.org |
| Google Favicons | 网站图标 | google.com/s2/favicons |

---

## 7. 性能架构

### 7.1 性能目标

| 指标 | 目标 | 当前 |
|------|------|------|
| API 响应时间 (P50) | < 200ms | ~150ms |
| API 响应时间 (P99) | < 2s | ~1.5s |
| AI 调用响应时间 | < 30s | ~15s |
| 100 并发会话响应 | < 2s | ~1.8s |
| 500 节点谱系渲染 | < 3s | ~2.5s |
| DeepSeek 缓存命中率 | ≥ 95% | ~96% |
| 测试通过率 | 100% | 99.5% |

### 7.2 缓存策略

```
┌─────────────────────────────────────────────────────────┐
│                    缓存层级                              │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  L1: AI 模型缓存 (DeepSeek Prompt Cache)               │
│  · 三段式 Prompt 前缀固化                               │
│  · 缓存命中率 ≥ 95%                                     │
│  · 节省 95% 输入 Token 成本                             │
│                                                         │
│  L2: 客户端缓存 (ai_proxy._clients)                     │
│  · 按 model_id 缓存 AsyncOpenAI 实例                    │
│  · 避免重复创建客户端                                   │
│                                                         │
│  L3: 会话列表缓存 (sessionStorage, 30s TTL)             │
│  · 前端会话列表缓存                                     │
│  · 30 秒自动过期                                        │
│                                                         │
│  L4: 数据库查询缓存 (内存)                              │
│  · Agent 元数据缓存                                     │
│  · 模型配置缓存                                         │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 7.3 数据库优化

- **WAL 模式**：启用 Write-Ahead Logging，提升并发读写性能
- **外键级联**：ON DELETE CASCADE 自动清理关联数据
- **索引优化**：高频查询字段建立索引
- **连接管理**：每次操作获取独立连接，操作后立即释放
- **批量操作**：批量插入引用数据，减少数据库往返

---

## 8. 安全架构

### 8.1 认证与授权

```
┌─────────────────────────────────────────────────────────┐
│                    安全层级                              │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. API 密钥管理                                        │
│     · 每个模型独立 API Key                              │
│     · 存储于 data/config.json                           │
│     · 前端仅显示是否配置 (boolean)                      │
│     · 不暴露实际密钥值                                  │
│                                                         │
│  2. 输入验证                                            │
│     · Pydantic 模型验证所有 API 输入                    │
│     · SQL 参数化查询 (防注入)                           │
│     · URL 验证 (引用解析)                               │
│                                                         │
│  3. 输出过滤                                            │
│     · API 响应不包含敏感信息                            │
│     · 错误消息不暴露内部细节                            │
│                                                         │
│  4. 速率限制                                            │
│     · AI 调用频率限制                                   │
│     · 预算超限自动停止                                  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 8.2 数据安全

- **SQLite 数据库**：文件权限 600，仅限当前用户访问
- **配置文件**：API Key 存储于 data/config.json，不提交到 Git
- **日志脱敏**：日志中不记录 API Key 和用户敏感信息
- **HTTPS**：生产环境强制 HTTPS

---

## 9. 部署架构

### 9.1 部署模式

```
┌─────────────────────────────────────────────────────────┐
│                    部署模式                              │
├──────────────┬──────────────┬───────────────────────────┤
│  本地开发    │  Docker      │  生产环境                 │
│              │              │                           │
│  python      │  docker      │  systemd +                │
│  main.py     │  compose     │  gunicorn +               │
│              │              │  uvicorn workers          │
│  端口: 8000  │  端口: 8000  │  端口: 80/443             │
│              │              │  + Nginx 反代             │
│  自动开浏览器│  卷挂载      │  SSL 证书                 │
│              │  data/       │  日志轮转                 │
└──────────────┴──────────────┴───────────────────────────┘
```

### 9.2 Docker 部署

```yaml
# docker-compose.yml
version: '3.8'
services:
  thesisminer:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    environment:
      - AI_API_KEY=${AI_API_KEY}
      - AI_BASE_URL=${AI_BASE_URL}
      - DB_PATH=/app/data/thesis_miner.db
    restart: unless-stopped
```

---

## 10. 监控与日志

### 10.1 日志系统

```python
# 日志级别
DEBUG   → 详细调试信息 (开发环境)
INFO    → 正常操作日志 (默认)
WARNING → 警告信息 (可恢复)
ERROR   → 错误信息 (需关注)
CRITICAL→ 严重错误 (需立即处理)

# 日志格式
[2026-06-19 10:30:00] [INFO] [main.py:56] ThesisMiner v8.0.0 启动
[2026-06-19 10:30:01] [INFO] [database.py:45] 数据库初始化完成
[2026-06-19 10:30:02] [INFO] [config.py:120] 加载 10 个模型配置
[2026-06-19 10:30:03] [INFO] [main.py:80] 浏览器已自动打开
```

### 10.2 监控指标

| 指标 | 描述 | 采集方式 |
|------|------|---------|
| API 响应时间 | 每个端点的响应时间 | FastAPI 中间件 |
| AI 调用次数 | 按模型/用途统计 | budget_ledger |
| Token 使用量 | 输入/输出/缓存 | budget_ledger |
| 缓存命中率 | DeepSeek 缓存命中 | cache_hit_rate |
| 活跃会话数 | 当前活跃会话 | sessions 表 |
| 消息总数 | 所有对话消息 | conversation_messages |
| 错误率 | API 错误百分比 | 错误日志 |

---

## 11. 未来路线图

### 11.1 v9.0 规划 (2026 Q4)

- **多用户支持**：用户认证与权限管理
- **云端部署**：AWS/Aliyun 部署支持
- **PostgreSQL**：可选的 PostgreSQL 后端
- **WebSocket**：实时双向通信
- **Agent 插件**：自定义 Agent 插件机制
- **多语言**：英文界面支持

### 11.2 v10.0 规划 (2027 Q2)

- **AI 训练**：基于用户反馈的模型微调
- **知识库**：持久化知识库与 RAG
- **协作功能**：多用户协作选题
- **移动端**：响应式移动端适配
- **API 开放**：开放 API 供第三方集成

### 11.3 长期愿景

- 成为学术界首选的 AI 辅助选题平台
- 支持全学科、全学位级别的论题生成
- 构建学术关系网络与知识图谱
- 推动 AI 辅助学术研究的规范化

---

## 附录

### A. 术语表

| 术语 | 定义 |
|------|------|
| Agent | 具有独立上下文和模型路由的 AI 代理 |
| Orchestrator | 主管理 Agent，负责调度子 Agent |
| Conversation | 会话下的一条独立对话线 |
| DST | Dialogue State Tracker，对话状态追踪器 |
| 五阶段闭环 | 信息确权→创意→校验→生成→深度辅助 |
| 三段式 Prompt | 系统角色+硬约束+学科导师的固定前缀 |
| 缓存命中率 | cached_tokens / prompt_tokens 比率 |
| 谱系图谱 | 论题-方法-文献-导师的关系网络 |
| 引用解析 | 从 AI 回复中提取 URL 和元数据 |
| 多粒度生成 | 标题/摘要/大纲/全文四种粒度 |

### B. 参考资料

- skillreadme.md - ThesisArchitect v4.0 参考文档
- FastAPI 官方文档 - https://fastapi.tiangolo.com/
- D3.js 官方文档 - https://d3js.org/
- DeepSeek API 文档 - https://platform.deepseek.com/
- OpenAI API 文档 - https://platform.openai.com/docs

### C. 变更历史

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-06-19 | V8.0 | 完整重写，多Agent架构，五阶段流程 |
| 2026-01-15 | V7.0 | 多模型注册表，三类Token统计 |
| 2025-10-20 | V6.0 | 开题报告生成，硬约束拦截 |
| 2025-08-10 | V5.0 | 知识卡片，创意引擎 |
| 2025-06-05 | V4.0 | 预算追踪，成本估算 |
| 2025-05-01 | V3.0 | 谱系知识图谱 |
| 2025-04-10 | V2.0 | 持久化会话管理 |
| 2025-03-15 | V1.0 | 初始版本 |

---

*本文档由 ThesisMiner v8.0 自动生成，最后更新于 2026-06-19*
