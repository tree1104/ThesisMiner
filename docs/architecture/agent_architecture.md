# ThesisMiner v8.0 多智能体架构设计文档

> **版本**：v8.0
> **日期**：2026-06-19
> **适用范围**：ThesisMiner 后端 `backend/agents/`、`backend/orchestration/`、`backend/routes/agents.py`
> **关联模块**：Orchestrator + Searcher + Reasoner + Critic + Mentor + Writer

---

## 目录

1. [架构总览](#1-架构总览)
2. [Orchestrator 主管理 Agent](#2-orchestrator-主管理-agent)
3. [Searcher 检索 Agent](#3-searcher-检索-agent)
4. [Reasoner 推理 Agent](#4-reasoner-推理-agent)
5. [Critic 评审 Agent](#5-critic-评审-agent)
6. [Mentor 导师 Agent](#6-mentor-导师-agent)
7. [Writer 写作 Agent](#7-writer-写作-agent)
8. [Agent 责任矩阵](#8-agent-责任矩阵)
9. [Agent 间通信协议](#9-agent-间通信协议)
10. [上下文隔离机制](#10-上下文隔离机制)
11. [模型路由策略](#11-模型路由策略)
12. [时序图与流程编排](#12-时序图与流程编排)
13. [错误处理与重试逻辑](#13-错误处理与重试逻辑)
14. [性能考量与可观测性](#14-性能考量与可观测性)
15. [扩展性与未来演进](#15-扩展性与未来演进)

---

## 1. 架构总览

### 1.1 设计目标

ThesisMiner v8.0 在 v7.0 单线编排状态机基础上，引入**多智能体协作架构**，将原本由 `OrchestrationStateMachine` 串行承担的「创意发散 → 精炼 → 校验 → 报告生成」流程拆解为六个职责单一、可独立扩展的智能体。设计目标如下：

1. **职责单一**：每个 Agent 仅承担一类任务，避免单一模块承担过多职责导致难以维护与测试。
2. **上下文隔离**：各 Agent 拥有独立的上下文窗口与系统提示词，互不污染，便于精确控制 token 用量与缓存命中率。
3. **模型路由灵活**：不同 Agent 可绑定不同模型（如 Reasoner 绑定 DeepSeek-R2 推理模型，Writer 绑定 Claude Opus 4.5 长文生成模型），按任务特性选优。
4. **可观测**：每次 Agent 调用通过透明账本记录 token 用量、费用、缓存命中、耗时，便于成本归因与性能调优。
5. **可重试**：Agent 调用失败时支持指数退避重试，单点失败不阻塞整体流程，提供兜底降级路径。
6. **可扩展**：新增 Agent 只需实现统一接口（`Agent.invoke()`）并注册到 Orchestrator，无需改动其他 Agent 代码。

### 1.2 六个 Agent 一览

| Agent | 中文名 | 主模型 | 核心职责 | 输入 | 输出 |
|-------|--------|--------|----------|------|------|
| Orchestrator | 主管理 Agent | claude-sonnet-4.5 | 调度五阶段流程、阶段门禁判定、上下文路由 | 用户原始输入 + 会话状态 | 阶段调度指令 + 最终汇总 |
| Searcher | 检索 Agent | deepseek-v3.2 | 联网检索文献、生成检索式、新颖性评估 | 检索意图 + 时间窗口 | 文献摘要列表 + 新颖性风险评级 |
| Reasoner | 推理 Agent | deepseek-r2 | 四维创意生成、谱系解析、候选打分 | LineageGraph + search_feeds | 候选提案列表（含 score） |
| Critic | 评审 Agent | deepseek-r2 | 硬约束校验、自动修复、重复度评估 | 单个候选提案 | 修复后提案 + WARNING 标记 |
| Mentor | 导师 Agent | gpt-4.1 | 模拟导师视角评审、答辩预演提问 | 候选提案 + 学科背景 | 导师评语 + 改进建议 |
| Writer | 写作 Agent | claude-opus-4.5 | 多粒度开题报告生成、降重脱敏 | 最优提案 + 颗粒度参数 | Markdown 报告 + 文件路径 |

### 1.3 架构分层图

```text
┌─────────────────────────────────────────────────────────────────┐
│                       前端层（SPA）                              │
│   仪表盘 / 论题生成 / 谱系管理 / 会话历史 / 预算看板 / 设置       │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP / SSE（统一 /api 前缀）
┌───────────────────────────┴─────────────────────────────────────┐
│                    API 路由层（FastAPI）                         │
│   /api/agents  /api/conversations  /api/messages  /api/cache-stats│
└───────────────────────────┬─────────────────────────────────────┘
                            │ 函数调用
┌───────────────────────────┴─────────────────────────────────────┐
│              Orchestrator 主管理 Agent（调度核心）                │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │  阶段门禁判定 · 上下文路由 · 重试编排 · 兜底降级         │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│   │ Searcher │→ │ Reasoner │→ │  Critic  │→ │  Mentor  │        │
│   │  检索    │  │  推理    │  │  评审    │  │  导师    │        │
│   └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
│                          │                                      │
│                          ▼                                      │
│                   ┌──────────┐                                  │
│                   │  Writer  │                                  │
│                   │  写作    │                                  │
│                   └──────────┘                                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────┴─────────────────────────────────────┐
│                      基础设施层                                   │
│   ai/ai_proxy（OpenAI 代理 + 账本）  │ sessions（DST 压缩）       │
│   budgets（透明账本）                 │ database（SQLite WAL）    │
└─────────────────────────────────────────────────────────────────┘
```

### 1.4 与 v7.0 的差异

| 维度 | v7.0 | v8.0 |
|------|------|------|
| 编排方式 | 单线状态机 `OrchestrationStateMachine` | 多智能体协作，Orchestrator 调度 |
| Agent 数量 | 3 个（Reasoner/Mentor/Searcher） | 6 个（新增 Orchestrator/Critic/Writer） |
| 模型路由 | 按学位分级 + 步骤路由 | 按 Agent 角色绑定模型，支持流式编排 |
| 上下文管理 | 单会话单上下文 | 多会话多对话隔离，DST 压缩 |
| 缓存策略 | 三段式 Prompt | 三段式 Prompt + 前缀哈希 + 命中率监控 |
| 错误处理 | try/except 兜底 | 指数退避重试 + 兜底降级 + 状态回滚 |
| 可观测性 | 透明账本 | 透明账本 + Agent 级耗时统计 + 缓存命中率 |

---

## 2. Orchestrator 主管理 Agent

### 2.1 角色定位

Orchestrator 是整个多智能体系统的「大脑」，负责：

1. **意图识别**：解析用户输入，识别当前所处的五阶段流程位置。
2. **阶段调度**：根据当前阶段与门禁判定结果，决定下一步调用哪个 Agent。
3. **上下文路由**：将上一阶段的输出转换为下一阶段的输入，必要时进行格式转换。
4. **门禁判定**：在每个阶段结束时执行门禁规则（如信息确权门禁、硬约束门禁），不通过则回退或重试。
5. **兜底降级**：当某个 Agent 调用失败且重试耗尽时，触发兜底逻辑（如 Reasoner 失败回退到 `fallback_proposal()`）。
6. **流式编排**：通过 SSE（Server-Sent Events）将各 Agent 的中间结果实时推送给前端。

### 2.2 模型选择

Orchestrator 绑定 `claude-sonnet-4.5`，原因如下：

- **长上下文**：200K 上下文窗口，可容纳完整会话历史与多阶段中间结果。
- **思维链能力**：支持 `thinking` 模式，适合复杂的阶段调度决策。
- **联网能力**：支持 `web_search`，可在阶段一信息确权时直接调用。
- **成本可控**：相比 Opus 4.5，Sonnet 4.5 在调度任务上的性价比更高。

### 2.3 系统提示词骨架

```text
你是 ThesisMiner 的主管理 Agent（Orchestrator），负责调度五阶段闭环导航流。

你的核心职责：
1. 解析用户输入，识别当前所处的阶段（信息确权 / 谱系解析 / 重复度评估 / 多粒度生成 / 深度辅助）。
2. 根据阶段门禁规则，决定下一步调用哪个子 Agent（Searcher/Reasoner/Critic/Mentor/Writer）。
3. 将上一阶段的输出转换为下一阶段的输入，必要时进行格式转换。
4. 监控各 Agent 的执行状态，失败时触发重试或兜底降级。
5. 通过 SSE 将中间结果实时推送给前端。

阶段门禁规则：
- 阶段一 → 阶段二：必须完成联网检索并展示文献摘要，等待用户确认。
- 阶段二 → 阶段三：候选提案必须 ≥3 个，且每个提案的 score ≥6 分。
- 阶段三 → 阶段四：硬约束校验通过（标题格式、学术日历、文献基线、逻辑自洽）。
- 阶段四 → 阶段五：开题报告生成成功，且 style_normalizer 已执行。
- 阶段五：进入后置交互循环，不主动结束对话。

输出格式：
- 调度指令：{ "next_agent": "...", "input": {...}, "stage": "..." }
- 中间结果：{ "agent": "...", "output": {...}, "tokens_used": N }
- 错误信息：{ "error": "...", "retryable": true/false, "fallback": "..." }
```

### 2.4 阶段调度状态机

```text
                  ┌──────────────────┐
                  │   用户输入        │
                  └────────┬─────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │  阶段一：信息确权  │ ←──┐
                  │  Agent: Searcher  │    │
                  └────────┬─────────┘    │
                           │              │
                  ┌────────▼─────────┐    │
                  │  门禁：用户确认？  │────┘ 否（回退）
                  └────────┬─────────┘
                           │ 是
                           ▼
                  ┌──────────────────┐
                  │  阶段二：谱系解析  │ ←──┐
                  │  Agent: Reasoner  │    │
                  └────────┬─────────┘    │
                           │              │
                  ┌────────▼─────────┐    │
                  │  门禁：≥3 候选？   │────┘ 否（重试）
                  └────────┬─────────┘
                           │ 是
                           ▼
                  ┌──────────────────┐
                  │  阶段三：重复度    │ ←──┐
                  │  Agent: Critic    │    │
                  └────────┬─────────┘    │
                           │              │
                  ┌────────▼─────────┐    │
                  │  门禁：硬约束通过？│────┘ 否（修复重试）
                  └────────┬─────────┘
                           │ 是
                           ▼
                  ┌──────────────────┐
                  │  阶段四：多粒度    │
                  │  Agent: Writer    │
                  └────────┬─────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │  阶段五：深度辅助  │ ←──┐
                  │  Agent: Mentor    │    │
                  └────────┬─────────┘    │
                           │              │
                  ┌────────▼─────────┐    │
                  │  门禁：用户结束？  │────┘ 否（继续循环）
                  └────────┬─────────┘
                           │ 是
                           ▼
                  ┌──────────────────┐
                  │   流程结束        │
                  └──────────────────┘
```

### 2.5 兜底降级策略

| 失败场景 | 兜底策略 |
|----------|----------|
| Searcher 联网检索超时（>5s） | 降级为 MockSearcher，返回模拟文献，标记 `search_degraded=true` |
| Reasoner 生成失败 | 回退到 `fallback_proposal()`，基于候选信息拼装简化提案（confidence_score=0.4） |
| Critic 校验失败且重试耗尽 | 标记 `WARNING` 但不阻塞，将原始提案传递给 Writer |
| Mentor 评审失败 | 跳过导师评审，直接进入 Writer，记录 `mentor_skipped=true` |
| Writer 报告生成失败 | 回退到模板兜底模式（`mode=template`），生成 6 章节标准报告 |
| Orchestrator 自身失败 | 返回 HTTP 500，记录错误日志，提示用户重试 |

---

## 3. Searcher 检索 Agent

### 3.1 角色定位

Searcher 负责所有联网检索任务，包括：

1. **阶段一信息确权**：基于用户输入生成检索式，联网检索近 2 年文献，展示摘要。
2. **阶段三重复度评估**：基于候选标题联网检索近 5 年硕博论文与期刊，输出新颖性风险评级。
3. **文献基线补全**：当文献数量不足时，自动补充子方向检索词与数据库建议。

### 3.2 模型选择

Searcher 绑定 `deepseek-v3.2`，原因如下：

- **联网能力**：原生支持 `web_search`，无需额外集成搜索 API。
- **低成本**：输入 1 元/百万 token，输出 4 元/百万 token，适合高频检索场景。
- **快速响应**：128K 上下文，响应速度快，适合阶段一的实时交互。

### 3.3 检索策略

Searcher 内部维护两套检索实现：

- **RealSearcher**：使用 `httpx.AsyncClient` 异步请求 arXiv + Semantic Scholar，5 秒超时自动降级。
- **MockSearcher**：返回模拟文献，用于开发测试与真实检索不可用时的兜底。

通过 `get_searcher()` 工厂函数根据 `real_search_enabled` 配置切换。

### 3.4 检索式生成规则

```text
检索式 = (学科关键词 OR 同义词) AND (时间窗口) AND (文献类型)

示例（信息确权阶段）：
  学科：计算机科学
  时间窗口：2024-2026
  检索式：("large language model" OR "LLM") AND (2024 OR 2025 OR 2026) AND (paper OR preprint)

示例（重复度评估阶段）：
  候选标题：医疗大模型在中文问诊中的小样本微调
  时间窗口：2021-2026
  检索式：("medical LLM" OR "healthcare AI") AND ("Chinese" OR "Mandarin") AND ("few-shot" OR "fine-tuning") AND (2021 OR 2022 OR 2023 OR 2024 OR 2025 OR 2026)
```

### 3.5 输出格式

```json
{
  "status": "success",
  "data": {
    "query": "检索式",
    "time_window": "2024-2026",
    "total_results": 42,
    "results": [
      {
        "title": "论文标题",
        "authors": ["作者1", "作者2"],
        "year": 2025,
        "venue": "会议/期刊",
        "abstract": "摘要",
        "url": "https://...",
        "source": "arxiv"
      }
    ],
    "novelty_risk": "low|medium|high",
    "differentiation_gaps": ["差异化空档1", "差异化空档2"]
  },
  "tokens_used": {
    "prompt": 1200,
    "completion": 800,
    "cached": 1000
  }
}
```

---

## 4. Reasoner 推理 Agent

### 4.1 角色定位

Reasoner 是四维创意引擎的核心，负责：

1. **谱系解析**：调用 `lineage_parser.parse_lineage(text)` 解析非结构化谱系文本，构建 `LineageGraph`。
2. **四维创意生成**：并行执行四个策略生成候选论题：
   - 导师项目延伸（advisor_extension）
   - 同门成果继承（peer_inheritance）
   - 跨域联想（cross_domain）
   - 矛盾驱动挖掘（contradiction_driven）
3. **自评分过滤**：按 `可行性 × 0.4 + 创新度 × 0.3 + 谱系贴合度 × 0.3` 打分，过滤 < 6 分的候选。
4. **search_feeds 注入**：将阶段一检索到的热点文献作为种子语料，提升候选论题的时效性。

### 4.2 模型选择

Reasoner 绑定 `deepseek-r2`，原因如下：

- **推理能力**：DeepSeek R2 是推理模型（Reasoner），支持 `thinking` 模式，适合复杂的创意生成与谱系分析。
- **结构化输出**：擅长生成结构化 JSON，便于下游 Critic 解析。
- **成本适中**：输入 4 元/百万 token，输出 16 元/百万 token，相比 Claude Opus 更经济。

### 4.3 四维创意策略详解

#### 4.3.1 导师项目延伸（advisor_extension）

将导师的大项目拆解为可在学制内完成的子课题。

```text
输入：导师项目「医疗大模型研发」
输出候选：
  - 特定科室的问询微调
  - 医疗知识图谱构建
  - 多模态病历理解
  - 医疗对话安全对齐
```

#### 4.3.2 同门成果继承（peer_inheritance）

基于边缘探测的局限点，引入新变量或迁移至新场景。

```text
输入：同门论文「英文医疗问诊的微调」+ 边缘探测点「未覆盖中文场景」
输出候选：
  - 中文医疗问诊的小样本微调
  - 中英双语医疗对话对齐
  - 跨语言医疗知识迁移
```

#### 4.3.3 跨域联想（cross_domain）

识别多个不相关学科概念，生成「A 领域方法解 B 领域问题」候选。

```text
输入：领域 A「强化学习」+ 领域 B「医疗问诊」
输出候选：
  - 用强化学习反馈机制优化医疗问诊的安全对齐
  - 基于 RLHF 的医疗对话奖励建模
```

#### 4.3.4 矛盾驱动挖掘（contradiction_driven）

检测「现有方法能力边界」与「实际需求」的语义矛盾，基于矛盾生成论题。

```text
输入：矛盾点「需要高精度但现有方法在噪声下失效」
输出候选：
  - 噪声鲁棒的医疗命名实体识别
  - 低资源场景下的医疗文本去噪
```

### 4.4 自评分机制

每个候选生成后，按以下公式打分（满分 10 分）：

```text
总分 = 可行性 × 0.4 + 创新度 × 0.3 + 谱系贴合度 × 0.3
```

- **可行性（0-10）**：学制内可完成度、数据/算力可获得性、技术成熟度。
- **创新度（0-10）**：与同门已有工作的差异化程度、方法新颖性。
- **谱系贴合度（0-10）**：与导师项目目标的对齐程度、对边缘点的承接程度。

**过滤规则**：总分低于 6 分的候选直接丢弃，不向用户展示；最终保留 Top 3-5 个方向。

### 4.5 输出格式

```json
{
  "status": "success",
  "data": {
    "lineage_graph": {
      "advisor_projects": [...],
      "peer_papers": [...],
      "edge_opportunities": [...]
    },
    "candidates": [
      {
        "title": "候选论题标题",
        "strategy": "advisor_extension",
        "score": 8.5,
        "score_breakdown": {
          "feasibility": 9,
          "novelty": 8,
          "lineage_fit": 8.5
        },
        "inspiration_source": "导师项目：医疗大模型研发",
        "research_significance": "...",
        "research_content": [...]
      }
    ]
  }
}
```

---

## 5. Critic 评审 Agent

### 5.1 角色定位

Critic 是硬约束的守护者，负责：

1. **标题格式校验**：长度（≤25 字硕士/≤30 字博士）、无主动动词开头、不匹配「基于 X 的 Y 研究」模式。
2. **学术日历校验**：硕士 ≤12 个月，博士 ≤24 个月。
3. **文献基线校验**：硕士 ≥30 篇，博士 ≥50 篇。
4. **逻辑自洽校验**：研究内容与研究目标语义重合度 ≤70%。
5. **重复度评估**：基于候选标题联网检索近 5 年硕博论文与期刊，输出新颖性风险评级。
6. **自动修复**：对不合规的提案执行确定性修复（如标题截取、动词前置转换、模式重组）。

### 5.2 模型选择

Critic 绑定 `deepseek-r2`，原因如下：

- **推理能力**：硬约束校验需要精确的逻辑判断，DeepSeek R2 的推理能力适合此类任务。
- **结构化输出**：校验结果需要结构化 JSON，便于下游 Writer 解析。
- **与 Reasoner 同模型**：减少模型切换开销，便于缓存复用。

### 5.3 硬约束规则库

| 约束类型 | 规则 | 自动修复方式 | 严重级别 |
|----------|------|-------------|----------|
| 标题长度 | 硕士 ≤25 字，博士 ≤30 字 | 依存句法截取核心名词短语 | error |
| 标题动词 | 不以「研究/分析/探讨/设计/构建/实现」开头 | 动词前置转名词性短语（「研究 X」→「X 的研究」） | error |
| 标题模式 | 不匹配「基于 X 的 Y 研究」 | 重组为突出核心贡献的名词短语 | error |
| 学术日历 | 硕士 ≤12 月，博士 ≤24 月 | 注入「分阶段并行执行」降级策略 | warning |
| 文献基线 | 硕士 ≥30 篇，博士 ≥50 篇 | 补充子方向检索词与数据库建议 | warning |
| 逻辑自洽 | 内容与目标重合度 ≤70% | 标记 `WARNING: 内容与目标重合度过高` | warning |

### 5.4 重复度评估算法

```text
输入：候选标题 + 时间窗口（默认近 5 年）
流程：
  1. 调用 Searcher.check_novelty(title, window) 联网检索
  2. 计算候选标题与检索结果的语义相似度（基于嵌入向量）
  3. 统计相似度分布：
     - max_similarity：最高相似度
     - avg_similarity：平均相似度
     - high_similarity_count：相似度 > 0.7 的数量
  4. 输出风险评级：
     - low：max_similarity < 0.5
     - medium：0.5 ≤ max_similarity < 0.7
     - high：max_similarity ≥ 0.7
  5. 输出差异化空档（differentiation_gaps）：列出与高相似文献的差异点
```

### 5.5 输出格式

```json
{
  "status": "success",
  "data": {
    "proposal": {
      "title": "修复后的标题",
      "auto_rewritten": true,
      "rewrite_reason": "原标题超长，已截取核心名词短语"
    },
    "validation_results": {
      "title_format": "pass",
      "academic_calendar": "pass",
      "literature_baseline": "warning",
      "logic_consistency": "pass"
    },
    "novelty_assessment": {
      "risk_level": "low",
      "max_similarity": 0.42,
      "differentiation_gaps": ["差异点1", "差异点2"]
    },
    "warnings": ["文献基线不足，已补充检索建议"]
  }
}
```

---

## 6. Mentor 导师 Agent

### 6.1 角色定位

Mentor 模拟真实导师的视角，对候选提案进行评审与提问，负责：

1. **导师视角评审**：从可行性、创新性、与课题组方向的契合度三个维度给出评语。
2. **答辩预演提问**：模拟答辩评委的提问风格，生成 3-5 个关键问题。
3. **改进建议**：针对提案的薄弱环节给出具体的改进方向。
4. **深度辅助闭环**：在阶段五提供文献精读工作簿、实验预研映射、答辩模拟三件套。

### 6.2 模型选择

Mentor 绑定 `gpt-4.1`，原因如下：

- **通用能力强**：GPT-4.1 在多领域知识覆盖与自然语言表达上表现优秀，适合模拟导师评语。
- **长上下文**：1M 上下文窗口，可容纳完整提案与历史对话。
- **稳定性**：GPT 系列在指令遵循上稳定，适合需要严格格式的评审任务。

### 6.3 评审维度

```text
导师评审报告：

一、可行性评估
  - 学制内可完成性：[高/中/低]
  - 数据可获得性：[高/中/低]
  - 算力需求：[高/中/低]
  - 技术成熟度：[高/中/低]

二、创新性评估
  - 与同门工作的差异化：[高/中/低]
  - 方法新颖性：[高/中/低]
  - 理论贡献潜力：[高/中/低]

三、谱系契合度评估
  - 与导师项目目标的对齐：[高/中/低]
  - 对边缘探测点的承接：[高/中/低]
  - 课题组资源支持：[高/中/低]

四、关键问题（答辩预演）
  1. [问题1]
  2. [问题2]
  3. [问题3]

五、改进建议
  1. [建议1]
  2. [建议2]
```

### 6.4 深度辅助三件套

在阶段五，Mentor 提供三个深度辅助入口：

1. **文献精读工作簿**（`literature_deep_reader`）：基于研究现状生成阅读顺序、关键问题、对比矩阵。
2. **实验预研映射**（`experiment_designer`）：基于研究内容与学科生成变量、对照组、数据集建议。
3. **答辩模拟轮次**（`thesis_defense_simulator`）：基于关键问题生成评委视角提问、参考回答、追问预案。

---

## 7. Writer 写作 Agent

### 7.1 角色定位

Writer 负责开题报告的最终生成，包括：

1. **多粒度渲染**：按 `concise`/`standard`/`detailed` 三级颗粒度渲染 Markdown。
2. **降重脱敏**：调用 `style_normalizer.remove_ai_traces(text)` 执行 200+ 禁用词替换、句首过滤、语态互换。
3. **文件输出**：在文件输出模式下，将报告写入 `output/draft_<timestamp>.md`。
4. **模板兜底**：AI 增强模式失败时，回退到模板兜底模式生成 6 章节标准报告。

### 7.2 模型选择

Writer 绑定 `claude-opus-4.5`，原因如下：

- **长文生成能力**：Claude Opus 4.5 在长文生成与结构化表达上表现卓越，适合开题报告。
- **中文学术写作**：Claude 系列在中文长文写作上质量稳定，AI 痕迹较少。
- **思维链能力**：支持 `thinking` 模式，可在生成前规划章节结构。

### 7.3 多粒度配置

| 颗粒度 | markdown_depth | 字数阈值 | 适用场景 |
|--------|----------------|----------|----------|
| concise（精简） | 2 | 3000-5000 字 | 快速预览、内部讨论 |
| standard（标准） | 3 | 6000-10000 字 | 标准开题报告 |
| detailed（详实） | 4 | 12000-20000 字 | 详尽开题报告、盲审准备 |

### 7.4 降重脱敏规则

Writer 在生成 Markdown 后，强制调用 `style_normalizer.remove_ai_traces(text)`：

1. **禁用词替换**（200+ 条）：
   - 「首先」→「」（删除，直接切入）
   - 「其次」→「接着」
   - 「最后」→「最终」
   - 「综上所述」→「总的来看」
   - 「值得注意的是」→「」
   - 「需要指出的是」→「」
2. **句首过滤**：删除以「首先/其次/再次/最后/此外/另外」开头的句子。
3. **语态互换**：将被动语态转换为主动语态（在合适场景下）。
4. **句长分布**：目标均值 15-25 字，标准差 8-12，避免过长或过短句子堆积。
5. **并列结构检测**：检测连续 ≥3 个并列结构并打破，避免模板化。

### 7.5 输出格式

```json
{
  "status": "success",
  "data": {
    "report": "# 开题报告\n\n## 一、基本信息\n...",
    "mode": "ai|template",
    "granularity": "standard",
    "word_count": 8542,
    "style_normalizer_applied": true,
    "replacements_count": 47,
    "high_risk_sections": ["国内外研究现状"],
    "file_path": "output/draft_20260619_143022.md"
  }
}
```

---

## 8. Agent 责任矩阵

### 8.1 RACI 矩阵

| 任务 | Orchestrator | Searcher | Reasoner | Critic | Mentor | Writer |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| 意图识别 | R/A | I | I | I | I | I |
| 阶段调度 | R/A | I | I | I | I | I |
| 联网检索 | I | R/A | I | I | I | I |
| 谱系解析 | I | I | R/A | I | I | I |
| 四维创意 | I | I | R/A | I | I | I |
| 硬约束校验 | I | I | I | R/A | I | I |
| 重复度评估 | I | C | I | R/A | I | I |
| 导师评审 | I | I | I | I | R/A | I |
| 答辩预演 | I | I | I | I | R/A | I |
| 报告生成 | I | I | I | I | I | R/A |
| 降重脱敏 | I | I | I | I | I | R/A |
| 兜底降级 | R/A | C | C | C | C | C |
| 流式推送 | R/A | I | I | I | I | I |

> R=Responsible（执行），A=Accountable（负责），C=Consulted（咨询），I=Informed（知情）

### 8.2 输入输出契约

| Agent | 输入 | 输出 | 下游消费者 |
|-------|------|------|-----------|
| Orchestrator | 用户输入 + 会话状态 | 调度指令 + SSE 事件 | 所有子 Agent |
| Searcher | 检索意图 + 时间窗口 | 文献摘要 + 新颖性评级 | Reasoner, Critic |
| Reasoner | LineageGraph + search_feeds | 候选提案列表（含 score） | Critic, Mentor |
| Critic | 单个候选提案 | 修复后提案 + WARNING | Writer, Mentor |
| Mentor | 候选提案 + 学科背景 | 导师评语 + 改进建议 | 用户, Orchestrator |
| Writer | 最优提案 + 颗粒度 | Markdown 报告 + 文件路径 | 用户 |

---

## 9. Agent 间通信协议

### 9.1 同步调用协议

Agent 间默认采用同步函数调用，调用方阻塞等待被调用方返回结果。

```python
# Orchestrator 调用 Reasoner 的伪代码
result = await reasoner.invoke(
    input_data={
        "lineage_graph": lineage_graph,
        "search_feeds": search_feeds,
        "degree": "master",
        "strategy": "all"
    },
    context={
        "session_id": session_id,
        "stage": "creativity",
        "parent_agent": "orchestrator"
    }
)
```

### 9.2 异步流式协议

对于长耗时任务（如 Writer 生成报告），采用 SSE 流式推送：

```text
event: agent_start
data: {"agent": "writer", "stage": "generation", "timestamp": "..."}

event: token
data: {"content": "# 开题报告\n\n## 一、", "tokens": 5}

event: token
data: {"content": "基本信息\n...", "tokens": 8}

event: agent_end
data: {"agent": "writer", "total_tokens": 8542, "duration_ms": 12345}
```

### 9.3 上下文传递

Agent 间通过 `context` 字典传递会话上下文，包含：

```json
{
  "session_id": "会话ID",
  "conversation_id": "对话ID",
  "stage": "当前阶段",
  "parent_agent": "调用方Agent",
  "history": [...],
  "dst_state": {...},
  "cache_prefix_hash": "前缀哈希"
}
```

### 9.4 错误传递

Agent 调用失败时，返回标准化错误结构：

```json
{
  "status": "error",
  "error": {
    "code": "AGENT_TIMEOUT",
    "message": "Agent 执行超时（>30s）",
    "retryable": true,
    "retry_count": 2,
    "fallback": "fallback_proposal"
  }
}
```

---

## 10. 上下文隔离机制

### 10.1 隔离原则

每个 Agent 拥有独立的上下文窗口，互不污染：

1. **系统提示词隔离**：每个 Agent 有专属的 `system_prompt`，不共享。
2. **历史隔离**：Agent 只能看到传递给它的 `history`，而非完整会话历史。
3. **DST 状态隔离**：每个 Agent 接收的 `dst_state` 是经过裁剪的，仅包含与当前任务相关的状态槽。
4. **缓存前缀隔离**：每个 Agent 的 Prompt 前缀独立计算 SHA-256 哈希，避免缓存串扰。

### 10.2 上下文裁剪规则

```text
Orchestrator 上下文 = 完整会话历史 + DST 状态 + 当前阶段信息
Searcher 上下文 = 检索意图 + 时间窗口（不含会话历史）
Reasoner 上下文 = LineageGraph + search_feeds + 学位信息（不含会话历史）
Critic 上下文 = 单个候选提案 + 硬约束规则库（不含会话历史）
Mentor 上下文 = 候选提案 + 学科背景 + 最近 2 轮对话
Writer 上下文 = 最优提案 + 颗粒度参数 + 报告模板（不含会话历史）
```

### 10.3 上下文压缩

当 Agent 的上下文超过模型 `max_context` 的 80% 时，触发 DST 压缩：

1. 调用 `dst_compactor.compact_history(history, dst_state)` 将早期历史压缩为 DST 摘要。
2. 保留最近 2 轮原文，其余替换为 DST 摘要。
3. 压缩后的上下文写回 `sessions.context`，供下一轮调用使用。

---

## 11. 模型路由策略

### 11.1 路由优先级

```text
模型路由优先级：
  1. 显式 model 参数（API 请求中指定）
  2. Agent 绑定模型（config/agents/*.yaml 中的 model 字段）
  3. step_models[purpose]（按步骤路由）
  4. settings.ai_model（默认模型）
```

### 11.2 Agent 模型绑定

| Agent | 绑定模型 | 备选模型 | 切换条件 |
|-------|----------|----------|----------|
| Orchestrator | claude-sonnet-4.5 | gemini-2.5-pro | Claude 不可用时切换 |
| Searcher | deepseek-v3.2 | doubao-1.5-pro | DeepSeek 不可用时切换 |
| Reasoner | deepseek-r2 | gemini-2.5-pro | DeepSeek 不可用时切换 |
| Critic | deepseek-r2 | glm-4.6 | DeepSeek 不可用时切换 |
| Mentor | gpt-4.1 | glm-4.6 | GPT 不可用时切换 |
| Writer | claude-opus-4.5 | qwen3-max | Claude 不可用时切换 |

### 11.3 模型能力校验

在调用 Agent 前，Orchestrator 会校验绑定模型的能力：

```python
def validate_model_capability(agent_id: str, required_capabilities: list) -> bool:
    model_config = get_model_config(get_agent_config(agent_id)["model"])
    for cap in required_capabilities:
        if not model_config.get(f"supports_{cap}", False):
            return False
    return True
```

若校验失败，Orchestrator 会尝试切换到备选模型，并记录告警日志。

---

## 12. 时序图与流程编排

### 12.1 完整五阶段时序图

```text
用户      前端      Orchestrator    Searcher    Reasoner    Critic     Mentor     Writer
 │         │            │              │            │          │          │          │
 │  输入    │            │              │            │          │          │          │
 ├────────►│            │              │            │          │          │          │
 │         │  POST      │              │            │          │          │          │
 │         ├───────────►│              │            │          │          │          │
 │         │            │  阶段一调度   │            │          │          │          │
 │         │            ├─────────────►│            │          │          │          │
 │         │            │              │  联网检索   │          │          │          │
 │         │            │              │  (arXiv)   │          │          │          │
 │         │            │  SSE: 摘要   │            │          │          │          │
 │         │◄───────────┤◄─────────────┤            │          │          │          │
 │  确认    │            │              │            │          │          │          │
 ├────────►│            │              │            │          │          │          │
 │         │  确认事件   │              │            │          │          │          │
 │         ├───────────►│              │            │          │          │          │
 │         │            │  阶段二调度   │            │          │          │          │
 │         │            ├──────────────────────────►│          │          │          │
 │         │            │              │            │ 四维创意  │          │          │
 │         │            │              │            │ 自评分   │          │          │
 │         │            │  SSE: 候选   │            │          │          │          │
 │         │◄───────────┤◄─────────────────────────┤          │          │          │
 │         │            │  阶段三调度   │            │          │          │          │
 │         │            ├─────────────────────────────────────►│          │          │
 │         │            │              │            │          │ 硬约束   │          │
 │         │            │              │            │          │ 修复    │          │
 │         │            │  SSE: 校验   │            │          │          │          │
 │         │◄───────────┤◄────────────────────────────────────┤          │          │
 │         │            │  阶段四调度   │            │          │          │          │
 │         │            ├────────────────────────────────────────────────►│          │
 │         │            │              │            │          │          │ 多粒度   │
 │         │            │              │            │          │          │ 生成     │
 │         │            │              │            │          │          │ 降重     │
 │         │            │  SSE: 报告   │            │          │          │          │
 │         │◄───────────┤◄───────────────────────────────────────────────┤          │
 │         │            │  阶段五调度   │            │          │          │          │
 │         │            ├───────────────────────────────────────────────────────────►│
 │         │            │              │            │          │          │  导师    │
 │         │            │              │            │          │          │  评审    │
 │         │            │  SSE: 评语   │            │          │          │          │
 │         │◄───────────┤◄──────────────────────────────────────────────────────────┤
 │  报告    │            │              │            │          │          │          │
 │◄────────┤            │              │            │          │          │          │
```

### 12.2 并行调用时序

在某些场景下，Orchestrator 会并行调用多个 Agent 以提升性能：

```text
场景：阶段三同时执行硬约束校验与导师评审

Orchestrator
    │
    ├──► Critic（硬约束校验）
    │       │
    │       └──► 返回修复后提案
    │
    └──► Mentor（导师评审）  ← 并行执行
            │
            └──► 返回导师评语

Orchestrator 合并结果 → 进入阶段四
```

### 12.3 重试时序

```text
Orchestrator
    │
    ├──► Reasoner.invoke()  ← 第 1 次调用
    │       │
    │       └──► 失败（超时）
    │
    ├──► 等待 2 秒（指数退避）
    │
    ├──► Reasoner.invoke()  ← 第 2 次调用
    │       │
    │       └──► 失败（JSON 解析错误）
    │
    ├──► 等待 4 秒（指数退避）
    │
    ├──► Reasoner.invoke()  ← 第 3 次调用
    │       │
    │       └──► 失败（API 错误）
    │
    └──► 触发兜底：fallback_proposal()
            │
            └──► 返回简化提案（confidence_score=0.4）
```

---

## 13. 错误处理与重试逻辑

### 13.1 错误分类

| 错误类型 | 错误码 | 严重级别 | 是否可重试 | 兜底策略 |
|----------|--------|----------|-----------|----------|
| API 超时 | AGENT_TIMEOUT | error | 是 | 指数退避重试 3 次 |
| API 限流 | AGENT_RATE_LIMIT | error | 是 | 指数退避重试 5 次 |
| JSON 解析失败 | AGENT_JSON_PARSE | error | 是 | 重试 2 次，仍失败则兜底 |
| 模型不可用 | MODEL_UNAVAILABLE | error | 是 | 切换备选模型 |
| 硬约束失败 | HARD_CONSTRAINT_FAIL | warning | 否 | 自动修复或标记 WARNING |
| 上下文超限 | CONTEXT_OVERFLOW | error | 是 | DST 压缩后重试 |
| 沙盒写入失败 | SANDBOX_WRITE_FAIL | error | 否 | 返回错误，提示用户 |

### 13.2 重试策略

```python
# 伪代码：指数退避重试装饰器
async def retry_with_backoff(
    func,
    max_retries: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 30.0,
    retryable_errors: list = ["AGENT_TIMEOUT", "AGENT_RATE_LIMIT"]
):
    for attempt in range(max_retries + 1):
        try:
            return await func()
        except AgentError as e:
            if e.code not in retryable_errors or attempt == max_retries:
                raise
            delay = min(base_delay * (2 ** attempt), max_delay)
            await asyncio.sleep(delay)
```

### 13.3 兜底降级链

```text
正常流程：
  Agent.invoke() → 成功 → 返回结果

重试流程：
  Agent.invoke() → 失败 → 重试 1 → 失败 → 重试 2 → 失败 → 重试 3

兜底流程：
  重试耗尽 → 触发兜底：
    - Searcher → MockSearcher（模拟文献）
    - Reasoner → fallback_proposal()（简化提案）
    - Critic → 跳过校验，标记 WARNING
    - Mentor → 跳过评审，记录 mentor_skipped
    - Writer → 模板兜底模式（mode=template）
    - Orchestrator → 返回 HTTP 500，记录日志
```

### 13.4 错误日志

所有 Agent 错误通过透明账本记录，包含：

```json
{
  "timestamp": "2026-06-19T14:30:22.123Z",
  "session_id": "sess_xxx",
  "agent_id": "reasoner",
  "model": "deepseek-r2",
  "error_code": "AGENT_TIMEOUT",
  "error_message": "Agent 执行超时（>30s）",
  "retry_count": 3,
  "fallback_triggered": true,
  "fallback_strategy": "fallback_proposal",
  "duration_ms": 35200
}
```

---

## 14. 性能考量与可观测性

### 14.1 性能指标

| 指标 | 目标值 | 监控方式 |
|------|--------|----------|
| 端到端延迟（五阶段） | < 60 秒 | Orchestrator 计时 |
| 单 Agent 延迟 | < 15 秒 | Agent 级计时 |
| 缓存命中率 | ≥ 95% | cache_stats API |
| 重试率 | < 5% | 错误日志统计 |
| 兜底触发率 | < 1% | 错误日志统计 |
| Token 用量（单会话） | < 50K | 透明账本汇总 |

### 14.2 可观测性面板

通过 `/api/cache-stats` 与 `/api/budgets/summary` 端点提供可观测性数据：

```json
{
  "cache_stats": {
    "total_requests": 1234,
    "cache_hits": 1187,
    "cache_hit_rate": 0.962,
    "by_agent": {
      "orchestrator": { "hits": 245, "misses": 12, "hit_rate": 0.953 },
      "reasoner": { "hits": 312, "misses": 8, "hit_rate": 0.975 },
      "writer": { "hits": 187, "misses": 23, "hit_rate": 0.890 }
    }
  },
  "budget_summary": {
    "total_calls": 1234,
    "total_tokens": 1234567,
    "total_cost_cny": 45.67,
    "by_agent": {
      "orchestrator": { "calls": 257, "tokens": 234567, "cost": 12.34 },
      "reasoner": { "calls": 320, "tokens": 345678, "cost": 15.67 }
    }
  }
}
```

### 14.3 性能优化建议

1. **缓存优化**：保持 Prompt 前缀稳定，避免动态内容污染前缀，提升缓存命中率。
2. **并行化**：对独立的 Agent 调用采用并行执行（如阶段三的 Critic 与 Mentor）。
3. **流式响应**：长耗时 Agent（Writer）采用 SSE 流式推送，提升用户体验。
4. **模型选择**：对简单任务（如 Searcher）使用低成本模型，对复杂任务（如 Writer）使用高质量模型。
5. **上下文压缩**：定期执行 DST 压缩，避免上下文膨胀导致 token 用量增长。

---

## 15. 扩展性与未来演进

### 15.1 新增 Agent

新增 Agent 的步骤：

1. 在 `backend/agents/` 下新建 Agent 文件，实现 `invoke()` 接口。
2. 在 `config/agents/` 下新建 YAML 配置文件，指定模型、温度、能力等。
3. 在 `docs/constraints/prompt_templates/` 下新建系统提示词模板。
4. 在 Orchestrator 的调度逻辑中注册新 Agent。
5. 在 `docs/api/openapi.yaml` 中补充 Agent 元数据端点。

### 15.2 模型升级

模型升级的步骤：

1. 在 `backend/config.py` 的 `DEFAULT_MODELS` 中新增模型配置。
2. 在 `config/agents/*.yaml` 中更新 `model` 字段。
3. 在 `docs/architecture/agent_architecture.md` 中更新模型绑定表。
4. 运行测试验证新模型的能力与稳定性。

### 15.3 未来演进方向

1. **Agent 自适应**：根据任务复杂度自动选择模型（简单任务用低成本模型，复杂任务用高质量模型）。
2. **Agent 学习**：基于历史调用数据微调 Agent 的系统提示词，提升输出质量。
3. **Agent 协作**：支持 Agent 间的双向通信（如 Writer 向 Reasoner 反馈生成困难，Reasoner 重新生成候选）。
4. **Agent 编排可视化**：提供可视化的 Agent 编排界面，允许用户自定义流程。
5. **Agent 市场**：支持第三方 Agent 接入，扩展系统能力。

---

## 附录 A：Agent 配置文件示例

```yaml
# config/agents/orchestrator.yaml
agent_id: orchestrator
name: Orchestrator
description: 主管理 Agent，调度五阶段流程
model: claude-sonnet-4.5
temperature: 0.3
max_tokens: 8192
capabilities:
  - streaming
  - thinking
  - web_search
system_prompt: |
  你是 ThesisMiner 的主管理 Agent...
stages:
  - info_confirm
  - creativity
  - validation
  - generation
  - deep_assist
gate_rules:
  info_confirm:
    require_user_confirmation: true
  creativity:
    min_candidates: 3
    min_score: 6.0
  validation:
    min_score: 60
    retry_stage: creativity
  generation:
    require_style_normalizer: true
  deep_assist:
    require_menu_render: true
retry:
  max_attempts: 3
  base_delay: 2.0
  max_delay: 30.0
fallback:
  strategy: fallback_proposal
  confidence_score: 0.4
```

## 附录 B：Agent 接口规范

```python
from typing import Any
from pydantic import BaseModel

class AgentInput(BaseModel):
    input_data: dict[str, Any]
    context: dict[str, Any]

class AgentOutput(BaseModel):
    status: str  # success | retry | error
    data: dict[str, Any] | None
    error: dict[str, Any] | None
    tokens_used: dict[str, int]
    duration_ms: int

class Agent:
    agent_id: str
    config: dict

    async def invoke(self, input: AgentInput) -> AgentOutput:
        """Agent 调用入口，所有 Agent 必须实现此接口。"""
        raise NotImplementedError

    def validate_input(self, input: AgentInput) -> bool:
        """校验输入是否符合 Agent 的输入契约。"""
        raise NotImplementedError

    def get_capabilities(self) -> list[str]:
        """返回 Agent 支持的能力列表。"""
        raise NotImplementedError
```

## 附录 C：Agent 注册表

| Agent ID | 配置文件 | 系统提示词 | 模型 | 状态 |
|----------|----------|-----------|------|------|
| orchestrator | config/agents/orchestrator.yaml | docs/constraints/prompt_templates/orchestrator_system.md | claude-sonnet-4.5 | active |
| searcher | config/agents/searcher.yaml | docs/constraints/prompt_templates/searcher_system.md | deepseek-v3.2 | active |
| reasoner | config/agents/reasoner.yaml | docs/constraints/prompt_templates/reasoner_system.md | deepseek-r2 | active |
| critic | config/agents/critic.yaml | docs/constraints/prompt_templates/critic_system.md | deepseek-r2 | active |
| mentor | config/agents/mentor.yaml | docs/constraints/prompt_templates/mentor_system.md | gpt-4.1 | active |
| writer | config/agents/writer.yaml | docs/constraints/prompt_templates/writer_system.md | claude-opus-4.5 | active |

---

## 附录 D：常见问题

### D.1 为什么 Orchestrator 选择 Claude Sonnet 而非 Opus？

Orchestrator 的核心任务是调度与门禁判定，对推理能力要求高但对长文生成要求低。Sonnet 4.5 在调度任务上的性价比高于 Opus 4.5（输入价格仅为 Opus 的 1/5），且具备思维链与联网能力，足以胜任调度职责。

### D.2 为什么 Reasoner 与 Critic 使用同一模型？

Reasoner 与 Critic 都需要精确的逻辑判断与结构化 JSON 输出，使用同一模型（deepseek-r2）可减少模型切换开销，并便于缓存复用（相同的 Prompt 前缀可命中缓存）。

### D.3 为什么 Writer 选择 Claude Opus？

Writer 负责生成开题报告，对长文生成与中文学术写作质量要求高。Claude Opus 4.5 在长文生成上表现卓越，且 AI 痕迹较少，配合 style_normalizer 可输出高质量报告。

### D.4 如何处理 Agent 间的数据格式不匹配？

Orchestrator 在调度时会执行格式转换，将上一 Agent 的输出转换为下一 Agent 的输入格式。例如，Reasoner 输出的候选提案列表会被转换为 Critic 所需的单个候选提案（取 Top 1）。

### D.5 如何监控 Agent 的执行状态？

通过 `/api/agents` 端点获取 Agent 元数据，通过 `/api/cache-stats` 获取缓存命中率，通过 `/api/budgets/summary` 获取 token 用量与费用。所有 Agent 调用通过透明账本记录，可按 Agent 维度查询。

---

## 附录 E：术语表

| 术语 | 定义 |
|------|------|
| Agent | 智能体，承担单一职责的 AI 模块 |
| Orchestrator | 主管理 Agent，负责调度其他 Agent |
| DST | Dialogue State Tracker，对话状态追踪器 |
| SSE | Server-Sent Events，服务器推送事件 |
| KV Cache | 键值缓存，大模型的上下文缓存机制 |
| 前缀哈希 | Prompt 前缀的 SHA-256 哈希，用于缓存命中判断 |
| 门禁 | 阶段切换的判定规则，不通过则回退或重试 |
| 兜底降级 | Agent 失败时的备用方案，确保系统可用 |
| 透明账本 | 记录每次 AI 调用的 token 用量与费用的账本 |
| 五阶段闭环 | 信息确权 → 谱系解析 → 重复度评估 → 多粒度生成 → 深度辅助 |

---

## 附录 F：变更历史

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| v8.0 | 2026-06-19 | 初始版本，定义六 Agent 架构 |
| v8.1 | （规划中） | 新增 Agent 自适应模型选择 |
| v8.2 | （规划中） | 新增 Agent 协作双向通信 |

---

> 文档版本 v8.0 · 最后更新 2026-06-19 · 维护者：ThesisMiner 团队
