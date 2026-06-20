# ThesisMiner v8.0 项目术语表

> 本文档定义 ThesisMiner v8.0 项目中使用的专业术语，帮助开发者与用户理解项目概念。

## 目录

- [1. 核心概念](#1-核心概念)
- [2. Agent 相关](#2-agent-相关)
- [3. 会话管理](#3-会话管理)
- [4. 约束工程](#4-约束工程)
- [5. AI 与模型](#5-ai-与模型)
- [6. 数据库](#6-数据库)
- [7. 前端](#7-前端)
- [8. 运维](#8-运维)
- [9. 学术术语](#9-学术术语)
- [10. 缩写](#10-缩写)

---

## 1. 核心概念

| 术语 | 英文 | 定义 |
|------|------|------|
| 论题挖掘 | Thesis Mining | 通过 AI 辅助发现与论证研究论题的过程 |
| 五阶段闭环 | Five-Stage Closed Loop | 信息确权→创意→校验→生成→深度辅助的完整流程 |
| 多 Agent 架构 | Multi-Agent Architecture | 多个独立 Agent 协作完成任务的架构模式 |
| 三段式 Prompt | Three-Segment Prompt | prefix/dynamic 分离的 Prompt 构造方式，用于缓存优化 |
| 谱系图谱 | Lineage Graph | 展示论题、方法、文献、导师间关系的可视化图谱 |

---

## 2. Agent 相关

| 术语 | 定义 |
|------|------|
| Orchestrator | 主管理 Agent，负责调度其他子 Agent |
| Searcher | 检索 Agent，负责联网搜索文献 |
| Reasoner | 创意 Agent，基于四维创意引擎生成候选论题 |
| Critic | 评审 Agent，评估论题新颖性与可行性 |
| Mentor | 导师 Agent，模拟导师视角给建议 |
| Writer | 写作 Agent，多粒度生成论题内容 |
| Agent 上下文 | Agent 独立维护的消息历史 |
| Agent 注册表 | 全局 Agent 注册与发现机制 |

---

## 3. 会话管理

| 术语 | 定义 |
|------|------|
| Session | 会话，顶层容器 |
| Conversation | 对话，属于某个 Session，支持多对话并存 |
| Message | 消息，对话中的单条记录 |
| 上下文隔离 | 不同对话间消息互不影响 |
| DST 压缩 | Dialog State Tracking 压缩，压缩历史消息 |
| 活跃对话 | Session 中当前激活的 Conversation |

---

## 4. 约束工程

| 术语 | 定义 |
|------|------|
| 阶段门禁 | 控制阶段进入与退出的条件 |
| 硬约束 | 必须满足的规则（标题长度等） |
| 新颖性评分 | 4 维评估论题创新性 |
| 去 AI 痕迹 | 替换模板词，调整句式 |
| 多粒度生成 | 标题/摘要/大纲/全文四种粒度 |
| 信息确权 | 强制联网检索并等待用户确认 |

---

## 5. AI 与模型

| 术语 | 定义 |
|------|------|
| LLM | Large Language Model，大语言模型 |
| 缓存前缀 | DeepSeek 缓存优化的固定 Prompt 段 |
| 缓存命中率 | cached_tokens / prompt_tokens 比率 |
| 流式响应 | SSE 方式逐步返回内容 |
| Token | LLM 处理的最小文本单元 |
| 模型路由 | 根据任务类型选择合适模型 |

---

## 6. 数据库

| 术语 | 定义 |
|------|------|
| WAL | Write-Ahead Logging，预写日志 |
| 外键级联 | 外键删除时自动删除关联记录 |
| 索引 | 加速查询的数据结构 |
| 事务 | 原子性操作序列 |
| 迁移 | 数据库 Schema 版本升级 |

---

## 7. 前端

| 术语 | 定义 |
|------|------|
| D3.js | 数据驱动文档的 JavaScript 库 |
| 力导向图 | 基于物理模拟的图谱布局 |
| SSE | Server-Sent Events，服务器推送 |
| SPA | Single Page Application，单页应用 |
| MPA | Multi-Page Application，多页应用 |

---

## 8. 运维

| 术语 | 定义 |
|------|------|
| ASGI | Async Server Gateway Interface |
| Uvicorn | ASGI 服务器 |
| 反向代理 | Nginx 等代理后端服务 |
| 负载均衡 | 分发请求到多个实例 |
| 熔断器 | 故障时快速失败的保护机制 |

---

## 9. 学术术语

| 术语 | 定义 |
|------|------|
| 开题报告 | 研究开始前的论证报告 |
| 文献综述 | 相关研究综述 |
| 答辩 | 学位论文口头答辩 |
| 导师 | 指导研究的教师 |
| 学科代码 | 教育部学科分类代码 |

---

## 10. 缩写

| 缩写 | 全称 |
|------|------|
| API | Application Programming Interface |
| CRUD | Create Read Update Delete |
| JSON | JavaScript Object Notation |
| YAML | YAML Ain't Markup Language |
| HTTP | HyperText Transfer Protocol |
| HTTPS | HTTP Secure |
| URL | Uniform Resource Locator |
| UUID | Universally Unique Identifier |
| CSV | Comma-Separated Values |
| PDF | Portable Document Format |

---

## 结语

本术语表随项目发展持续更新。如有未收录的术语，欢迎在 GitHub Issues 中提出。
