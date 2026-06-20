# ThesisMiner 项目架构文档

## 版本 V8.0（多 Agent 架构版）
## 日期 2026-06-20

---

## 1. 项目概述

### 1.1 项目定位

- **一句话定义**：学术语境驱动的实战论题生成与开题架构系统。
- **目标用户**：研究生（硕士 / 博士）、导师、学术研究者。
- **解决的核心问题**：
  - 论题创意生成难——缺乏学术谱系延续性与跨域发散能力；
  - 开题报告撰写难——论题无法直通开题报告核心模块；
  - 学术可行性评估难——缺乏硬性的学术日历、文献基线与资源边界约束。

ThesisMiner 将 AI 的跨域发散能力与真实学术生存法则（导师项目、同门基础、时间与经费限制、开题规范）深度融合，生成既能通过答辩盲审、又具备可行性的研究论题，并直接映射为开题报告核心素材。

### 1.2 核心功能

| 功能模块 | 能力说明 | 对应后端目录 |
|----------|----------|--------------|
| **多 Agent 架构** | Orchestrator 主管理 + 5 个子 Agent（Searcher/Reasoner/Critic/Mentor/Writer），独立上下文，协同工作 | `backend/agents/`、`backend/agents/orchestrator.py` |
| **五阶段闭环** | 信息确权→创意→校验→生成→深度辅助，门禁控制，评分<60 回退 | `backend/orchestration/`、`backend/constraints/stage_gate.py` |
| **DeepSeek 缓存优化** | 三段式 Prompt（prefix/dynamic），缓存命中率 ≥95% | `backend/ai/prompt_cache.py`、`backend/ai/cache_monitor.py` |
| **多对话管理** | 多对话并存，上下文完全隔离，DST 压缩，历史对话支持 | `backend/sessions/conversation_manager.py`、`backend/routes/conversations.py` |
| **D3.js 谱系图谱** | 力导向交互式图谱，节点拖拽、画布缩放、悬停高亮、类型过滤 | `frontend/scripts/pages/lineage.js` |
| **联网搜索引用** | 智能解析 URL/Markdown/编号引用，异步富化，卡片展示 | `backend/ai/citation_parser.py`、`backend/routes/citations.py` |
| **2026 最新模型** | 10 个 2026 模型（gpt-4.1/claude-sonnet-4.5/deepseek-v3.2 等），agent_default 路由 | `backend/config.py` |
| 论题生成 | 多粒度生成（标题/摘要/大纲/全文），去 AI 痕迹 | `backend/agents/proposal_writer.py`、`backend/constraints/multi_granularity.py` |
| 约束校验 | 硬约束（标题/学科/导师/时间/重复度）+ 新颖性 4 维评分 | `backend/constraints/`、`backend/routes/constraints.py` |
| 谱系管理 | 学术谱系图节点/边管理，知识卡片，图谱扩展 | `backend/knowledge/`、`backend/routes/lineage.py` |
| 预算控制 | 透明账本，缓存命中细分，会话级费用估算 | `backend/budgets/`、`backend/routes/budgets.py` |
| 真实文献检索 | 模拟/真实检索热插拔（arXiv + Semantic Scholar） | `backend/agents/searcher_wrapper.py` |
| 开题报告直出 | 基于论题数据一键生成标准 Markdown 开题报告 | `backend/agents/proposal_writer.py` |
| 深度辅助三件套 | 文献精读 / 实验预研 / 答辩模拟 | `backend/constraints/deep_assist.py` |
| 自动开浏览器 | lifespan 启动钩子，自动打开浏览器 | `main.py` |

### 1.3 技术底座

- **后端框架**：Python 3.10+ / FastAPI（ASGI，由 Uvicorn 驱动）。
- **前端技术**：HTML + Tailwind CSS（CDN）+ 原生 JS（单页应用 SPA，按需动态加载页面脚本）。
- **数据库**：SQLite（启用 WAL 模式以支持并发读取，`check_same_thread=False` 允许跨线程）。
- **AI 能力**：OpenAI SDK（兼容 DeepSeek / 通义千问等 OpenAI 协议服务商，可配置 `base_url` 与 `api_key`）。

---

## 2. 文件结构与职责

### 2.1 目录树

```bash
ThesisMiner/
├── main.py                          # 应用入口：FastAPI 实例、CORS、路由注册、前端静态挂载
├── requirements.txt                 # Python 依赖清单
├── ThesisMiner项目架构文档.md        # 原始架构设计文档（v6.0 设计稿）
├── README.md                        # 本架构文档（V5.0 增强版）
├── .gitignore
├── backend/                         # 后端业务包
│   ├── __init__.py
│   ├── config.py                    # 配置管理：.env / config.json / 默认值三级优先级
│   ├── database.py                  # SQLite 连接管理、建表、CRUD 辅助函数
│   ├── models.py                    # Pydantic 数据模型与枚举
│   ├── ai/                          # AI 调用代理层
│   │   ├── ai_proxy.py              # OpenAI 客户端封装、同步 / JSON / 流式调用、账本记录
│   │   └── prompts.py               # Reasoner / Mentor / Inspire 提示词模板
│   ├── constraints/                 # 约束工程
│   │   ├── academic_calendar.py     # 学术时间约束（硕士 1 年 / 博士 2 年）
│   │   ├── format_validator.py      # 标题格式校验与自动重写
│   │   ├── lit_baselines.py         # 文献数量基线校验
│   │   └── exceptions.py            # 约束违规自定义异常
│   ├── creativity/                  # 创意涌现引擎
│   │   ├── academic_lineage.py      # 学术谱系链接器（导师项目 / 同门继承）
│   │   ├── cross_domain.py          # 跨域联想与趋势嫁接
│   │   ├── problem_awareness.py     # 问题意识激发器（按学科路由）
│   │   └── candidate_ranker.py      # 多候选打分排序
│   ├── knowledge/                   # 知识图谱
│   │   ├── lineage_graph_store.py   # 谱系节点 / 边 CRUD
│   │   ├── card_manager.py          # 知识卡片管理
│   │   └── graph_expander.py        # 从论文文本抽取实体关系扩展图谱
│   ├── orchestration/               # 编排层
│   │   ├── state_machine.py         # 编排流程状态机
│   │   └── hooks/                   # 流程钩子
│   │       ├── pre_search.py        # 前置检索：整合谱系 / 问题意识 / 跨域联想
│   │       ├── post_reasoner.py     # 后置精炼：标题校验重写
│   │       ├── academic_feasibility_check.py  # 可行性拦截：时间与文献校验
│   │       └── hard_rule_interceptor.py       # 硬约束拦截：标题/周期强制校验（HTTP 422）
│   ├── agents/                      # 智能体
│   │   ├── reasoner_proposal.py     # Reasoner：直通开题的论题生成
│   │   ├── mentor_agent.py          # Mentor：导师视角评审
│   │   ├── searcher_wrapper.py      # Searcher：模拟文献检索与新颖性检查
│   │   └── proposal_writer.py       # 开题报告生成（AI增强+模板兜底）
│   ├── sessions/                    # 会话管理
│   │   ├── session_manager.py       # 会话 CRUD 与上下文压缩
│   │   ├── dialogue_state_tracker.py # DST 对话状态追踪器
│   │   └── dst_compactor.py         # DST 历史压缩器
│   ├── budgets/                     # 预算控制
│   │   ├── estimator.py             # 预算估算与模型分级路由
│   │   └── transparent_ledger.py    # 透明账本：用量记录与汇总统计
│   └── routes/                      # API 路由层（统一 /api 前缀）
│       ├── config.py                # 配置与状态
│       ├── lineage.py               # 谱系管理
│       ├── creativity.py            # 创意引擎
│       ├── proposals.py             # 论题生成
│       ├── constraints.py           # 约束校验
│       ├── sessions.py              # 会话管理
│       └── budgets.py               # 预算控制
├── frontend/                        # 前端单页应用
│   ├── index.html                   # SPA 外壳：侧边导航 + 主内容区
│   ├── styles/
│   │   └── main.css                 # 自定义设计系统（Editorial Academic 主题）
│   └── scripts/
│       ├── api.js                   # API 客户端（基础依赖）
│       ├── app.js                   # 应用主逻辑（路由 / 状态 / 工具）
│       └── pages/                   # 各页面脚本（按需动态加载）
│           ├── dashboard.js         # 仪表盘
│           ├── generate.js          # 论题生成
│           ├── lineage.js           # 谱系管理
│           ├── sessions.js          # 会话历史
│           ├── budgets.js           # 预算看板
│           └── settings.js          # 设置
├── tests/                           # 测试
│   ├── test_api.py                  # 接口自测（FastAPI TestClient）
│   └── test_frontend.py             # 前端资源可访问性检查
└── data/                            # 运行时数据（已 gitignore，保留 .gitkeep）
    ├── .gitkeep
    ├── config.json                  # 用户配置文件
    └── thesis_miner.db              # SQLite 数据库文件
```

### 2.2 核心文件职责说明

| 文件 | 职责唯一性 |
|------|------------|
| `main.py` | 应用唯一入口。创建 FastAPI 实例（title=`ThesisMiner v8.0`，version=`8.0.0`），配置 CORS（开发环境允许所有源），通过 `asynccontextmanager` 实现的 `lifespan` 异步上下文管理器在启动时初始化数据库并按配置自动打开浏览器（替代已弃用的 `@app.on_event`），注册全部 9 个路由模块（含 v8.0 新增 conversations / citations 路由与 cache_stats 路由），并将 `frontend/` 目录以静态文件形式挂载到根路径 `/`（仅当目录存在时挂载）。 |
| `backend/routes/*.py` | API 路由层唯一载体。每个文件对应一个业务域，内部定义 `APIRouter(prefix=...)`，将 HTTP 请求映射到对应业务模块。路由内部不承载复杂业务逻辑，仅做参数转换与异常包装。 |
| `backend/ai/ai_proxy.py` | AI 调用唯一代理。封装 OpenAI 客户端创建、配置检查、同步调用（`call_llm`）、JSON 解析调用（`call_llm_json`）、流式调用（`call_llm_stream`），并在每次调用后通过透明账本记录 token 用量与费用；内置 JSON 容错解析（支持代码块包裹与裸 JSON 提取）。 |
| `backend/orchestration/state_machine.py` | 编排流程唯一状态机。定义 `init → inspiring → reasoning → validating → completed/failed` 状态流转，串联前置检索、精炼、后置校验钩子，编排从创意发散到校验完成的完整流程；提供 `create_orchestration` 便捷工厂函数与兜底提案能力。 |
| `frontend/index.html` | 前端唯一 HTML 入口。定义 SPA 外壳（侧边导航 + 主内容区 + 通知容器 + 抽屉容器），引入 Tailwind CDN、Lucide 图标、Google Fonts，并通过 `tailwind.config` 注入 Editorial Academic 设计令牌；按依赖顺序加载 `api.js` 与 `app.js`，页面脚本由 `app.js` 动态加载。 |

---

## 3. 技术栈详情

### 3.1 后端运行环境

| 组件 | 选型 | 说明 |
|------|------|------|
| 编程语言 | Python 3.10+ | 使用 `str \| None`、`dict[str, Any]` 等 PEP 604 联合类型语法 |
| Web 框架 | FastAPI ≥ 0.110.0 | ASGI 框架，原生支持异步路由与 Pydantic 校验 |
| ASGI 服务器 | Uvicorn[standard] ≥ 0.27.0 | 开发环境 `reload=True`，监听 `127.0.0.1:8000` |
| 异步支持 | async/await | 路由层大量使用 `async def`，AI 调用全异步（openai.AsyncOpenAI） |
| 进程管理 | 直接 `python main.py` 或 `uvicorn main:app` | 未引入 Gunicorn，单进程开发模式 |

### 3.2 数据库与持久化

| 组件 | 选型 | 说明 |
|------|------|------|
| 主数据库 | SQLite（`data/thesis_miner.db`） | 标准库 `sqlite3`，启用 WAL 模式，`check_same_thread=False` |
| 配置存储 | `data/config.json` | JSON 格式用户配置，覆盖 `.env` 与默认值 |
| 缓存 | 无独立缓存层 | 依赖 SQLite WAL 的并发读能力；配置单例缓存在内存（`get_settings()`） |
| 数据表 | sessions / proposals / lineage_nodes / lineage_edges / budget_ledger / knowledge_cards | 模块导入时自动 `init_db()` 建表 |

### 3.3 AI 与多智能体组件

| 组件 | 选型 / 实现 | 说明 |
|------|------|------|
| 大语言模型 | OpenAI SDK ≥ 1.12.0 | 兼容 DeepSeek / 通义千问，通过 `base_url` 切换服务商 |
| 约束引擎 | `backend/constraints/` | 标题正则校验、学术日历时间约束、文献基线数量约束、伦理熔断异常 |
| 创意引擎 | `backend/creativity/` | 学术谱系链接器、问题意识激发器（按学科路由）、跨域联想、候选打分排序 |
| 编排状态机 | `backend/orchestration/state_machine.py` | v8.0 五阶段状态机（INFO_CONFIRM → CREATIVITY → VALIDATION → GENERATION → DEEP_ASSIST）+ 阶段门禁 + 评分<60 回退逻辑 |
| 智能体 | `backend/agents/` | v8.0 多 Agent 架构：Orchestrator（主管理）+ Searcher（联网检索）/ Reasoner（四维创意）/ Critic（新颖性评估）/ Mentor（导师评审）/ Writer（多粒度生成），每个 Agent 继承 BaseAgent 抽象基类，独立上下文，通过 AgentRegistry 全局注册 |
| 检索策略 | `backend/agents/searcher_wrapper.py` | MockSearcher / RealSearcher 工厂模式（`get_searcher()`），RealSearcher 使用 httpx.AsyncClient 异步请求 arXiv + Semantic Scholar，5 秒超时自动降级 MockSearcher |
| 缓存策略 | `backend/ai/prompt_cache.py`、`backend/ai/cache_monitor.py` | v8.0 三段式 Prompt（不可变前缀 + 动态尾部），DeepSeek 缓存命中率 ≥95%，cache_hit_rate 写入 budget_ledger |

### 3.4 前端技术

| 组件 | 选型 | 说明 |
|------|------|------|
| 框架 | 原生 JS（无构建步骤） | SPA 架构，`app.js` 实现路由与状态管理，页面脚本按需动态加载 |
| 样式 | Tailwind CSS（CDN） + `styles/main.css` | CDN 引入并通过 `tailwind.config` 扩展自定义设计令牌 |
| 图标 | Lucide Icons（CDN） | `https://unpkg.com/lucide@latest` |
| 字体 | Google Fonts | Fraunces（display）、DM Sans（body）、Noto Serif SC / Noto Sans SC（中文）、JetBrains Mono（mono） |
| 主题 | Editorial Academic（暗色） | `darkMode: 'class'`，ink / paper / amber 三色体系 |

---

## 4. 核心机制与架构设计

### 4.1 系统架构分层图

```text
┌─────────────────────────────────────────────────────────────────┐
│                        前端层（SPA）                              │
│   index.html + scripts/{api.js, app.js, pages/*.js} + main.css  │
│   仪表盘 / 论题生成 / 谱系管理 / 会话历史 / 预算看板 / 设置        │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP / JSON（统一 /api 前缀）
┌───────────────────────────┴─────────────────────────────────────┐
│                     API 路由层（FastAPI）                         │
│   config / lineage / creativity / proposals / constraints /      │
│   sessions / budgets   （7 个路由模块，44 个端点）                │
└───────────────────────────┬─────────────────────────────────────┘
                            │ 函数调用
┌───────────────────────────┴─────────────────────────────────────┐
│                    业务服务层（多智能体协作）                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────────┐  │
│  │constraints│ │creativity│ │knowledge │ │  orchestration     │  │
│  │ 约束工程  │ │ 创意涌现 │ │ 知识图谱 │ │  状态机 + 钩子     │  │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────────┘  │
│  ┌──────────────────────────────────┐ ┌────────┐ ┌───────────┐  │
│  │  agents（Reasoner/Mentor/Searcher）│ │sessions│ │  budgets  │  │
│  └──────────────────────────────────┘ └────────┘ └───────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────┴─────────────────────────────────────┐
│                      基础设施层                                   │
│   ai/ai_proxy（OpenAI 代理 + 账本记录） │ config（三级配置）       │
│   database（SQLite / WAL）            │ data/{config.json, *.db}  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 核心业务流程

#### 4.2.1 论题生成流程

入口：`POST /api/proposals/generate`，请求体包含 `degree`、`discipline`、`mentor_info`、`mode`、`count`、`session_id`。

1. **配置检查**：路由层调用 `check_api_configured()`，若未配置 `AI_API_KEY` 则返回 HTTP 400，提示用户在设置页配置。
2. **候选构建**：调用 `reasoner_proposal.generate_multiple()`。若未传入候选列表，则基于 `mentor_info` 生成默认候选方向（理论拓展 / 实证分析 / 跨学科应用 / 方法论创新 / 案例研究）。
3. **单提案生成**（对每个候选）：
   - 富化上下文：将候选的 `direction` / `suggestion` 拼入上下文；
   - 构建用户提示：`build_reasoner_prompt()` 拼装学位、学科、导师信息与上下文；
   - 模型路由：`get_model_for_degree()` 按学位选择模型（硕士 `deepseek-chat`，博士 `qwen-max`）；
   - 调用 LLM：`call_llm_json()` 获取结构化 JSON 响应并记录账本；
   - 标题校验重写：`validate_and_rewrite()` 校验标题格式，不合规则自动重写并置 `auto_rewritten=True`；
   - 字段补全：`_ensure_proposal_fields()` 补全缺失字段，确保输出符合 `AcademicThesisProposal` 结构。
4. **兜底机制**：单个候选生成失败时回退到 `fallback_proposal()`，基于候选信息拼装结构完整的简化提案（`confidence_score=0.4`），确保系统可用。
5. **持久化**：为每个提案生成 `uuid` 与时间戳，写入 `proposals` 表（`research_significance` 与 `research_content` 自动 JSON 序列化）。
6. **返回**：响应包含 `proposals` 列表、`count` 与 `session_id`。

> 完整编排流程（创意发散 → 精炼 → 校验）由 `orchestration/state_machine.py` 的 `OrchestrationStateMachine.run()` 提供，依次执行 `pre_search` → `_call_reasoner` → `post_reasoner` + `academic_feasibility_check`，可通过 `create_orchestration()` 工厂创建。

#### 4.2.2 约束校验流程

约束工程分为三类硬性校验，对应 `backend/constraints/` 三个模块：

- **标题校验**（`format_validator.validate_and_rewrite`）：
  - 长度校验：标题不超过 20 字（`MAX_TITLE_LENGTH=20`）；
  - 主动动词校验：不以「研究 / 分析 / 探讨 / 调查 / 实现 / 构建 / 设计 / 开发 / 优化 / 改进 / 评估 / 验证」等主动动词开头；
  - 模式校验：不匹配「基于 X 的 Y 研究」正则模式；
  - 自动重写：超长标题截取前 20 字并去除末尾动词词缀；动词前置结构转换为名词性短语（如「研究 X」→「X 的研究」）；「基于 X 的 Y 研究」模式重组为核心名词性短语。
- **可行性校验**（`academic_calendar.validate_timeframe`）：
  - 硕士研究周期 ≤ 12 个月（1 年），博士 ≤ 24 个月（2 年）；
  - 超期返回 `feasible=False` 并给出原因；编排层可行性拦截钩子在超期时抛出 `InfeasibleError`。
- **文献基线校验**（`lit_baselines.check_literature_count`）：
  - 硕士文献基线 ≥ 30 篇，博士 ≥ 50 篇；
  - 不足返回 `sufficient=False` 并给出原因；编排层在文献不足时为提案添加 `warning` 字段而非熔断。

#### 4.2.3 创意涌现流程

入口：`POST /api/creativity/inspire`，由前置检索钩子 `pre_search.run()` 编排：

1. **谱系链接**：`_parse_mentor_info()` 解析导师信息（按换行分隔，识别「项目: / 导师项目:」「论文: / 同门:」显式前缀，无前缀时按「《」开头或含「论文」启发式归类），分离导师项目与同门论文；`academic_lineage.generate_lineage_candidates()` 遍历生成候选——导师项目调用 `extend_mentor_project()`（生成可在年限内完成的子课题），同门论文调用 `inherit_senior_work()`（继承未走完之路，迁移至相邻场景或引入新变量）。
2. **问题意识激发**：`problem_awareness.inspire()` 按学科路由——人文社科扫描社会热点与政策文件匹配学科理论寻找现实与理论张力；理工科从工程应用背景定位系统故障 / 算法精度 / 耗时等具体痛点。
3. **跨域联想**：当导师信息含 ≥2 个主题时，`cross_domain.cross_domain_association()` 将领域 A 的成熟方法嫁接至领域 B 的未解问题，追加为候选。
4. **候选排序**：`candidate_ranker.rank_candidates()` 按灵感来源权重打分（`mentor_project` 0.9 > `senior_inherit` 0.8 > `problem_awareness` 0.75 > `cross_domain` 0.7 > `trend_graft` 0.6），降序排序并保留前 5 个（`MAX_RETAINED_CANDIDATES=5`）。
5. **上下文富化**：将解析出的主题拼入上下文，供后续精炼阶段使用。

#### 4.2.4 开题报告生成流程

入口：`POST /api/proposals/{proposal_id}/report?use_ai=true|false`，由 `proposal_writer.generate_report()` 编排：

1. **论题加载**：根据 `proposal_id` 从 `proposals` 表读取论题详情（含标题、研究意义、研究内容、置信度等），不存在则返回 HTTP 404。
2. **生成模式选择**：
   - `use_ai=true`（AI 增强模式）：调用 `call_llm` 基于论题数据生成更丰富的报告内容，失败时自动回退到模板模式；
   - `use_ai=false`（模板兜底模式）：直接基于论题字段填充标准模板。
3. **章节拼装**：按 6 章节标准结构生成 Markdown——基本信息、选题依据、国内外研究现状、研究内容、技术路线与可行性分析、进度安排。
4. **返回**：响应包含 `report`（Markdown 全文）、`proposal_id`、`mode`（ai/template）字段，前端在论题详情抽屉中提供「生成开题报告」按钮与报告抽屉（支持复制 / 下载）。

#### 4.2.5 硬约束拦截流程

入口：`/api/proposals/generate` 端点在持久化前调用 `hard_rule_interceptor` 进行 fail-fast 校验：

1. **标题硬校验**（`validate_title_hard`）：标题为空、超过 20 字、以主动动词开头、匹配「基于 X 的 Y 研究」模式时，立即抛出 HTTP 422。
2. **周期硬校验**（`validate_timeline_hard`）：`_extract_total_months` 从 `research_content` 解析「X 个月 / X 年 / 半年 / X 周」等表述，超出学位上限（硕士 12 个月 / 博士 24 个月）时抛出 HTTP 422。
3. **提案硬校验**（`validate_proposal_hard`）：对单个提案依次执行标题与周期校验，任一失败立即返回。
4. **批量 fail-fast**：在 `/api/proposals/generate` 端点中，任一论题校验失败立即返回 422，不保存任何论题，避免不合规数据落库。

#### 4.2.6 DST 对话状态压缩流程

由 `sessions/session_manager.update_session_context_with_dst()` 在会话上下文更新时触发：

1. **状态提取**：`dialogue_state_tracker.extract_state(history)` 从对话历史中提取结构化状态槽——`selected_topic`（已选论题）、`confirmed_methods`（已确认方法）、`confirmed_discipline`（已确认学科）、`open_questions`（待解决问题）、`iteration_count`（迭代轮数）。
2. **历史压缩**：`dst_compactor.compact_history(history, dst_state)` 当历史超过 5 轮时，将早期历史压缩为 DST 摘要 + 最近 2 轮原文，控制 token 用量线性增长。
3. **上下文集成**：压缩后的上下文写回 `sessions.context`，供下一轮 Reasoner / Mentor 调用使用，同时与三段式 Prompt 协同——DST 状态作为 `build_dynamic_tail` 的输入，保证 Prompt 前缀稳定以提高 KV Cache 命中率。

### 4.3 数据存储规范

| 路径 | 用途 | 格式 |
|------|------|------|
| `data/thesis_miner.db` | 主数据库，存储会话、论题、谱系图、预算账本、知识卡片 | SQLite（WAL 模式） |
| `data/config.json` | 用户配置（AI 密钥、模型、base_url 等） | JSON |
| `data/.gitkeep` | 占位文件，确保 `data/` 目录纳入版本控制 | 纯文本 |
| `.env` | 环境变量配置（可选，优先级低于 config.json） | KEY=VALUE |

数据库表结构（`init_db()` 自动创建）：

| 表名 | 主要字段 | 用途 |
|------|----------|------|
| `sessions` | id, title, degree, discipline, mentor_info, status, context | 会话元数据与上下文 |
| `proposals` | id, session_id, title, inspiration_source, research_significance, research_content, confidence_score, auto_rewritten | 论题提案 |
| `lineage_nodes` | id, node_type, title, abstract, metadata | 谱系节点 |
| `lineage_edges` | id, source_id, target_id, relation_type, weight | 谱系边 |
| `budget_ledger` | id, session_id, model, prompt_tokens, completion_tokens, total_tokens, cached_prompt_tokens, cost, purpose | 预算账本明细（含缓存命中 token 细分） |
| `knowledge_cards` | id, title, content, tags, source | 知识卡片 |

> `metadata`、`tags`、`context`、`research_significance`、`research_content` 等 dict/list 字段在写入时自动 JSON 序列化，读取时由各业务模块反序列化还原。

---

## 5. API 接口清单（核心）

遵循 RESTful 风格，统一前缀 `/api`，返回 JSON。v8.0 系统共提供 **60+** 个 API 端点，分布于 9 个路由模块（含 v8.0 新增 conversations / citations / cache-stats 路由）。

### 5.1 配置与状态

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/config` | 返回当前配置（隐藏 api_key，仅显示是否已配置；含学位模型映射、文献基线、学术日历） |
| POST | `/api/config` | 更新配置并持久化到 `data/config.json`（仅保存非空字段，合并写回） |
| GET | `/api/status` | 返回服务健康状态（status、version=8.0.0、rag_enabled、ai_configured） |
| GET | `/api/models` | 获取多模型注册表（v8.0 含 10 个 2025-2026 模型，含 agent_default / release_year 字段） |
| POST | `/api/models` | 新增模型到注册表（接收模型配置 JSON） |
| PUT | `/api/models/{model_id}` | 更新指定模型配置 |
| DELETE | `/api/models/{model_id}` | 删除模型（若被步骤路由使用则拒绝） |
| GET | `/api/step-models` | 获取步骤路由配置（v8.0 返回 orchestrator/reasoner/mentor/inspire/report/search 映射） |
| PUT | `/api/step-models` | 更新步骤路由配置（校验模型存在性） |
| PUT | `/api/currency` | 切换计价货币（仅支持 CNY/USD） |
| GET | `/api/agents` | v8.0 新增：返回 Agent 注册表元数据（id/name/description/default_model/capabilities） |
| GET | `/api/cache-stats` | v8.0 新增：返回最近 100 次 DeepSeek 调用的平均缓存命中率 |

### 5.2 谱系管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/lineage` | 列出谱系节点（metadata 已反序列化），支持 `limit/offset` 分页，返回 `total` 总数（v7.0 增强） |
| POST | `/api/lineage/import` | 批量导入谱系节点与边 |
| GET | `/api/lineage/graph` | 获取完整图谱（nodes + edges） |
| GET | `/api/lineage/search?keyword=` | 按关键词模糊搜索节点（标题 LIKE 匹配） |
| DELETE | `/api/lineage/batch` | 批量删除节点及关联边（v7.0 新增，接收 `{node_ids: list[str]}`） |
| DELETE | `/api/lineage/{node_id}` | 删除指定节点及其关联边 |
| POST | `/api/lineage/cards` | 新增知识卡片（title、content、tags、source） |
| GET | `/api/lineage/cards?tag=` | 列出知识卡片，可选按标签过滤 |

### 5.3 创意引擎

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/creativity/inspire` | 激发创意候选，整合学术谱系、问题意识与跨域联想 |
| POST | `/api/creativity/cross-domain` | 跨域联想：将领域 A 的成熟方法嫁接至领域 B |
| POST | `/api/creativity/trend-graft` | 趋势嫁接：基于近期高频术语进行语义组合 |
| POST | `/api/creativity/rank` | 候选排序：按灵感来源权重打分降序，保留前 5 |
| GET | `/api/creativity/candidates?degree=&discipline=&mentor_info=` | 获取示例候选：解析导师信息生成谱系候选 |

### 5.4 论题生成

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/proposals/generate` | 生成论题提案（未配置 API Key 时返回 400；硬约束不合规返回 422） |
| GET | `/api/proposals?limit=&offset=&session_id=` | 分页查询论题列表，可选按会话过滤 |
| GET | `/api/proposals/{proposal_id}` | 获取单个论题详情（不存在返回 404） |
| DELETE | `/api/proposals/{proposal_id}` | 删除指定论题 |
| POST | `/api/proposals/{proposal_id}/report?use_ai=true\|false` | 基于论题生成标准 Markdown 开题报告（AI 增强 + 模板兜底） |

### 5.5 约束校验

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/constraints/validate-title` | 校验标题格式并自动重写（返回 title、auto_rewritten、reason） |
| POST | `/api/constraints/check-feasibility` | 校验研究周期可行性（degree、timeframe_months） |
| POST | `/api/constraints/check-literature` | 校验文献数量是否达到基线（degree、count） |
| GET | `/api/constraints/calendar/{degree}` | 获取指定学位的学术日历（max_years、description） |
| GET | `/api/constraints/baseline/{degree}` | 获取指定学位的文献基线值 |
| POST | `/api/constraints/search-literature` | 真实文献检索（arXiv + Semantic Scholar），5 秒超时自动降级模拟检索 |
| GET | `/api/constraints/search-status` | 查询文献检索配置状态（real_search_enabled、degraded 标记） |

### 5.6 会话管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/sessions` | 创建新会话（初始状态 active，初始 context 含空 history 与 candidates） |
| GET | `/api/sessions?limit=&offset=` | 分页查询会话列表（按创建时间降序），返回 `dialog_rounds` 对话轮数 |
| GET | `/api/sessions/{session_id}` | 获取会话详情（不存在返回 404），含 `dialog_rounds` 对话轮数与 `active_conversation_id` |
| DELETE | `/api/sessions/{session_id}` | 删除指定会话（级联删除 proposals / budget_ledger / conversations / conversation_messages / search_citations） |
| PATCH | `/api/sessions/{session_id}/status` | 更新会话状态（如 active / closed / completed） |

### 5.7 对话管理（v8.0 新增）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/sessions/{sid}/conversations` | 在指定会话下新建对话（接收 agent_id 选择目标 Agent） |
| GET | `/api/sessions/{sid}/conversations` | 列出会话下所有对话（按 updated_at 降序） |
| GET | `/api/conversations/{cid}` | 获取对话详情（含 agent_id / status / title） |
| PUT | `/api/conversations/{cid}` | 更新对话（重命名 / 切换状态） |
| DELETE | `/api/conversations/{cid}` | 删除对话（级联删除消息与引用） |
| GET | `/api/conversations/{cid}/messages?limit=` | 获取对话消息列表（按 conversation_id 隔离，含 agent_id / role / content / reasoning / citations） |

### 5.8 引用查询（v8.0 新增）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/messages/{mid}/citations` | 返回指定消息的所有联网搜索引用（url / title / snippet / source_domain / favicon） |

### 5.9 预算控制

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/budgets/ledger?session_id=&limit=&offset=` | 获取账本明细，可选按会话过滤（含 cache_hit_rate 字段） |
| POST | `/api/budgets/estimate` | 估算会话级预算（degree、mode、count） |
| GET | `/api/budgets/summary` | 获取账本汇总统计（总调用、总 token、总费用、input_cached/input_uncached/output 三类细分、按模型 / 用途分组、平均 cache_hit_rate） |
| GET | `/api/budgets/session/{session_id}` | 获取指定会话的费用统计（含三类 token 细分与 cache_hit_rate） |
| GET | `/api/budgets/pricing` | 获取模型定价表（从模型注册表读取，元/百万 token，支持 CNY/USD 货币切换） |

---

## 6. 配置与环境变量

### 6.1 环境变量列表

配置优先级：`data/config.json` 用户配置 > `.env` 环境变量 > 默认值。

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `AI_API_KEY` | （空） | AI 服务商 API 密钥，未配置时生成接口返回 400 |
| `AI_BASE_URL` | `https://api.openai.com/v1` | AI 服务商基础 URL，可切换至 DeepSeek / 通义 |
| `AI_MODEL` | `deepseek-v3.2` | 默认模型名称（v8.0 默认切换至 2026 最新 DeepSeek） |
| `DB_PATH` | `data/thesis_miner.db` | SQLite 数据库文件路径 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `FLASK_ENV` | `production` | 运行环境标识（历史命名，沿用） |
| `REAL_SEARCH_ENABLED` | `false` | 是否启用真实文献检索（默认模拟检索），设为 `true` 时调用 arXiv + Semantic Scholar |
| `SEARCH_API_KEYS_ARXIV` | （空） | arXiv API 密钥（可选，未配置时使用匿名调用） |
| `SEARCH_API_KEYS_SEMANTIC_SCHOLAR` | （空） | Semantic Scholar API 密钥（可选，未配置时使用匿名调用） |
| `AUTO_OPEN_BROWSER` | `true` | 启动时是否自动打开浏览器（v7.0 新增） |
| `CURRENCY` | `CNY` | 计价货币（CNY/USD，v7.0 新增） |

**学位分级路由常量**（`backend/config.py`）：

| 常量 | 说明 |
|------|------|
| `DEGREE_MODELS` | 硕士 → 中等成本模型，博士 → 高上下文模型 |
| `LITERATURE_BASELINE` | 硕士 30 篇，博士 50 篇 |
| `ACADEMIC_CALENDAR` | 硕士 1 年，博士 2 年 |
| `APP_VERSION` | v8.0.0（应用版本号常量） |
| `APP_TITLE` | ThesisMiner v8.0（应用标题常量） |
| `DEFAULT_MODELS` | v8.0 多模型注册表默认值（10 个 2025-2026 模型，含定价/能力开关/上下文长度/agent_default/release_year） |
| `DEFAULT_STEP_MODELS` | v8.0 步骤路由默认值（orchestrator/reasoner/mentor/inspire/report/search → 各 Agent 角色最优模型） |

> v8.0 模型路由优先级：显式 `model` 参数 > `get_step_model(purpose)`（按步骤路由，含 orchestrator）> `settings.ai_model`（默认模型）。定价单位为"元/百万 token"，从 `models` 注册表读取，回退到 `MODEL_PRICING_LEGACY_USD`。v8.0 内置 10 个模型：gpt-4.1-mini / gpt-4.1 / deepseek-chat-v3 / deepseek-reasoner / qwen-plus / qwen-max / claude-sonnet-4.5 / claude-opus-4.5 / deepseek-v3.2 / deepseek-r2 / qwen3-max / gemini-2.5-pro / glm-4.6 / doubao-1.5-pro。

### 6.2 用户配置文件结构

`data/config.json` 示例：

```json
{
  "ai_api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxx",
  "ai_base_url": "https://api.deepseek.com/v1",
  "ai_model": "deepseek-v3.2",
  "db_path": "data/thesis_miner.db",
  "log_level": "INFO",
  "flask_env": "production"
}
```

> 通过 `POST /api/config` 更新时，仅写入请求中提供的非空字段，与已有配置合并后写回；写入后重置配置单例，下次读取生效。

---

## 7. 部署与运行

### 7.1 开发环境启动

```bash
# 1. 克隆项目并进入目录
cd ThesisMiner

# 2. 创建虚拟环境（可选但推荐）
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置 AI 密钥（二选一）
#    方式 A：创建 .env 文件
#    AI_API_KEY=sk-xxxxxxxx
#    AI_BASE_URL=https://api.deepseek.com/v1
#    方式 B：启动后在前端「设置」页填写并保存（写入 data/config.json）

# 5. 启动开发服务器（自动重载）
python main.py
# 或
uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# 6. 访问应用
#    前端：http://127.0.0.1:8000/
#    API 状态：http://127.0.0.1:8000/api/status
#    交互式文档：http://127.0.0.1:8000/docs
```

### 7.2 生产环境构建说明

```bash
# 1. 安装依赖（不含开发工具）
pip install -r requirements.txt

# 2. 使用 Uvicorn 多 worker 启动（关闭 reload）
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

# 3. 建议通过反向代理（Nginx）转发，并配置：
#    - HTTPS 终止
#    - 静态资源缓存（frontend/ 目录）
#    - 限制 /api 请求体大小与速率

# 4. 数据持久化：
#    - data/ 目录需可写，挂载到持久卷
#    - 定期备份 data/thesis_miner.db（WAL 模式下可热备）
```

> 注意：`main.py` 中 CORS 配置为 `allow_origins=["*"]`（开发友好），生产环境应收紧为具体域名。前端为纯静态资源，无需构建步骤，由 FastAPI `StaticFiles` 直接挂载到根路径。

---

## 8. 扩展性设计

### 8.1 添加新功能模块的规范

1. **业务模块**：在 `backend/` 下新建子目录（如 `backend/evaluation/`），包含 `__init__.py` 与业务函数，所有持久化操作委托 `backend/database` 的 CRUD 函数（`execute_insert` / `fetch_one` / `fetch_all` / `execute_query`）。
2. **数据模型**：在 `backend/models.py` 中新增 Pydantic 请求 / 响应模型，复用 `ApiResponse` 通用响应结构。
3. **路由模块**：在 `backend/routes/` 下新建路由文件，定义 `APIRouter(prefix="/api/<module>", tags=["<module>"])`，路由内部仅做参数转换与异常包装，业务逻辑下沉到业务模块。
4. **注册路由**：在 `main.py` 中 `from backend.routes import <module> as <module>_router` 并 `app.include_router(<module>_router.router)`。
5. **数据库表**：若需新表，在 `backend/database.py` 的 `init_db()` 中追加 `CREATE TABLE IF NOT EXISTS` 语句。
6. **前端页面**：在 `frontend/scripts/pages/` 下新增页面脚本，并在 `app.js` 路由表中注册导航项。

### 8.2 替换或升级 AI 模型

- **切换服务商**：修改 `data/config.json` 或 `.env` 中的 `ai_base_url` 与 `ai_api_key`（如 DeepSeek：`https://api.deepseek.com/v1`；通义：`https://dashscope.aliyuncs.com/compatible-mode/v1`；Anthropic Claude：`https://api.anthropic.com/v1`）。
- **切换默认模型**：修改 `ai_model` 字段。
- **调整学位分级路由**：修改 `backend/budgets/estimator.py` 的 `get_model_for_degree()` 返回值。
- **新增模型定价**：v8.0 起通过多模型注册表管理，调用 `POST /api/models` 新增模型并配置 `pricing`（元/百万 token）与 `agent_default` / `release_year` 字段；或直接编辑 `data/config.json` 的 `models` 列表。未登记的模型回退到 `MODEL_PRICING_LEGACY_USD` 定价。
- **调整生成模式 token 估算**：修改 `_MODE_TOKEN_ESTIMATE`（`quick`：prompt 2000 / completion 1000；`deep`：prompt 5000 / completion 3000）。
- **按步骤路由模型**：v8.0 `step_models` 配置支持 orchestrator/reasoner/mentor/inspire/report/search 六个 Agent 角色，调用 `PUT /api/step-models` 为各 Agent 指定不同模型。
- **切换计价货币**：调用 `PUT /api/currency` 在 CNY/USD 间切换。
- **DeepSeek 缓存优化**：v8.0 三段式 Prompt 自动固化前缀，DeepSeek 调用缓存命中率 ≥95%，无需手动干预；通过 `GET /api/cache-stats` 查看实时命中率。

> v8.0 内置模型注册表支持 10 个 2025-2026 模型：`gpt-4.1-mini`、`gpt-4.1`、`deepseek-chat-v3`、`deepseek-reasoner`、`qwen-plus`、`qwen-max`、`claude-sonnet-4.5`、`claude-opus-4.5`、`deepseek-v3.2`、`deepseek-r2`、`qwen3-max`、`gemini-2.5-pro`、`glm-4.6`、`doubao-1.5-pro`，定价单位为"元/百万 token"，每个模型含 `agent_default`（适合的 Agent 角色）与 `release_year`（发布年份）字段。

---

## 9. 测试策略

### 9.1 接口自测

`tests/test_api.py` 使用 FastAPI `TestClient` 对所有核心接口进行自测，覆盖正常流程与异常场景：

```bash
# 方式一：pytest
python -m pytest tests/test_api.py -v

# 方式二：直接运行（自动安装 httpx 依赖）
python tests/test_api.py
```

测试覆盖范围（v8.0 共 394+ 用例全部通过）：
- 配置与状态：`GET /api/status`（version=8.0.0）、`GET /api/config`、`POST /api/config`
- 谱系管理：导入与查询、图谱、搜索、知识卡片增查、分页查询、批量删除端点
- 创意引擎：创意激发、跨域联想、候选排序（验证 `mentor_project` 权重最高排首位）
- 约束校验：标题校验（合法 / 超长）、可行性校验（可行 / 超期）、文献基线校验（充足 / 不足）、学术日历查询、文献基线查询
- 会话管理：完整 CRUD（创建 / 列表 / 详情 / 状态更新 / 删除）、对话轮数统计、级联删除验证
- 论题生成：列表查询、未配置 API Key 时正确返回 400
- 预算控制：估算、汇总、账本、定价表、三类 token 统计、估算器人民币定价
- 异常处理：404 处理
- 会话级联删除：删除会话后 proposals / budget_ledger / conversations / conversation_messages / search_citations 同步清理验证
- 文献检索状态：`GET /api/constraints/search-status` 返回 real_search_enabled 字段
- 模拟文献检索：`POST /api/constraints/search-literature` 默认返回模拟文献
- 硬约束拦截：标题超长 / 主动动词 / 周期超期返回 HTTP 422
- 开题报告模板：`POST /api/proposals/{id}/report?use_ai=false` 返回 6 章节标准模板
- 论题 404 场景：获取不存在的论题返回 404
- 缓存字段：sessions 表含 cache_prefix_hash / cache_id / cache_hit_rate 字段
- lifespan 启动：无 on_event 弃用告警
- auto_open_browser 配置项存在
- 多模型注册表：models 列表（10 个 2025-2026 模型）、step_models（含 orchestrator）、currency、辅助函数
- 模型管理 API CRUD：增删改查模型
- 步骤路由 API：GET/PUT 步骤路由
- 货币切换 API：CNY/USD 切换与非法值拒绝
- **v8.0 多 Agent 架构**：`tests/test_models_v8.py`（旧模型已移除、新模型已加入、agent_default 字段存在）、`tests/test_orchestrator.py`（五阶段顺序调用、门禁回退、子 Agent 上下文隔离）
- **v8.0 多对话管理**：`tests/test_conversations.py`（多对话并存、上下文隔离、消息按 conversation_id 过滤）
- **v8.0 DeepSeek 缓存**：`tests/test_cache_hit.py`（连续 10 次 DeepSeek 调用 prefix 字节级一致、cache_hit_rate ≥ 0.95）
- **v8.0 五阶段约束**：`tests/test_constraints_v8.py`（五阶段门禁、新颖性评分、style_normalizer 输出无模板词）、`tests/test_state_machine_v8.py`（状态转移、回退逻辑）
- **v8.0 引用解析**：`tests/test_citation_parser.py`（URL/Markdown/编号引用解析）
- **v8.0 扩展单元测试**：`tests/unit/` 与 `tests/integration/` 共 20+ 测试文件，覆盖 analytics / ml / export / knowledge / validation / routing / integrity / optimization / nlp / monitoring / planning / reasoning 等模块

### 9.2 前端审查

`tests/test_frontend.py` 通过 `urllib` 检查前端资源可访问性（需先启动服务）：

```bash
# 先启动服务
python main.py &
# 再运行检查
python tests/test_frontend.py
```

检查清单覆盖：根页面 `/`、`/api/status`、`scripts/api.js`、`scripts/app.js`、6 个页面脚本（dashboard / generate / lineage / sessions / budgets / settings）、`styles/main.css`，要求全部返回 HTTP 200。

---

## 10. 依赖管理

### 10.1 主依赖

`requirements.txt` 内容：

| 依赖 | 版本要求 | 用途 |
|------|----------|------|
| fastapi | ≥ 0.110.0 | Web 框架 |
| uvicorn[standard] | ≥ 0.27.0 | ASGI 服务器 |
| pydantic | ≥ 2.6.0 | 数据模型校验 |
| python-dotenv | ≥ 1.0.0 | `.env` 环境变量加载 |
| sqlalchemy | ≥ 2.0.0 | ORM（已声明，当前实现直接使用 sqlite3） |
| openai | ≥ 1.12.0 | AI 服务调用 |
| httpx | ≥ 0.27.0 | HTTP 客户端（TestClient 依赖） |
| python-multipart | ≥ 0.0.9 | 表单解析支持 |

> 测试额外依赖：`pytest`（可选）、`httpx`（TestClient 必需，已在主依赖中）。

---

## 11. 常见问题与故障排除（FAQ）

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 生成论题返回 HTTP 400「AI API Key 未配置」 | 未配置 `AI_API_KEY` | 在前端「设置」页填写并保存，或写入 `.env` / `data/config.json` |
| 启动报错 `Address already in use`（端口 8000 被占用） | 端口冲突 | 更换端口：`uvicorn main:app --port 8001`，或终止占用进程 |
| `database is locked` | SQLite 并发写冲突 | 已启用 WAL 模式缓解；避免多进程同时写，或排队写入 |
| 前端页面空白 / JS 报错 | 静态资源未正确挂载 | 确认 `frontend/` 目录存在于项目根目录；检查浏览器控制台网络请求 |
| AI 调用返回 JSON 解析失败 | 模型未严格按 JSON 格式输出 | `ai_proxy._parse_json()` 已支持代码块与裸 JSON 容错；可降低 `temperature` 或在提示词中强化 JSON 要求 |
| 账本费用为 0 | 模型未返回 `usage` 字段 | 部分服务商不返回 token 用量，`call_llm` 已做 `usage` 为空的兜底（记为 0） |
| 标题被自动重写 | 触发约束校验（超 20 字 / 含主动动词 / 「基于 X 的 Y 研究」模式） | 属预期行为，响应中 `auto_rewritten=True` 并附 `reason` |
| 博士生生成论题成本偏高 | 博士路由至 `qwen-max`（高上下文模型） | 属设计预期；可在 `estimator.get_model_for_degree()` 中调整 |
| 真实文献检索返回模拟数据 | `REAL_SEARCH_ENABLED=false` 或真实检索 5 秒超时自动降级 | 在设置页开启真实检索开关，或配置 `SEARCH_API_KEYS_ARXIV` / `SEARCH_API_KEYS_SEMANTIC_SCHOLAR`；响应中 `search_degraded=true` 表示已降级 |
| 论题生成返回 HTTP 422 | 触发硬约束拦截（标题为空 / 超 20 字 / 主动动词开头 / 「基于 X 的 Y 研究」模式 / 周期超学位上限） | 属 fail-fast 设计，不合规论题不落库；按 422 响应中 `detail` 修改后重试 |
| 开题报告生成失败 | AI 增强模式调用 LLM 失败 | 自动回退到模板兜底模式（`mode=template`），仍可生成 6 章节标准报告；如需 AI 增强请检查 API Key 与网络 |
| 多轮对话后 token 用量增长过快 | 历史全量拼接导致上下文膨胀 | DST 压缩器在历史超过 5 轮时自动压缩为状态摘要 + 最近 2 轮，无需手动干预；如需查看压缩后上下文可查询会话详情 |

---

## 12. 项目演进路线图

1. **谱系图谱构建**：开发导入工具，支持解析导师论文库（PDF / 知网导出格式）与历年优秀同门毕业论文，借助 `graph_expander` 自动构建本课题组学术知识图谱。
2. **开题模板对齐**：依据研究生院标准开题报告模板（选题依据、研究内容、研究方案、工作计划），微调 Reasoner 的 Prompt，确保输出结构直接可用。
3. **硬约束规则编码** ✓ 已完成：将「题目 20 字限制」「硕博文献基线要求」「1 / 2 年研究周期限制」进一步沉淀为代码层硬性拦截规则与可配置策略。新增 `hard_rule_interceptor.py`，对标题 / 周期不合规论题返回 HTTP 422，fail-fast 阻止落库。
4. **可行性评估闭环**：在生成研究方案后，强制要求模型自证「如何在学习年限内利用现有资源完成」，无法自证则打回重生成。
5. **全流程联调**：打通从「大方向输入」到「谱系检索」「创意发散」「可行性过滤」「开题报告段落生成」的完整链路，将 `OrchestrationStateMachine` 接入主生成路由。
6. **真实检索接入** ✓ 已完成：将 `searcher_wrapper` 的模拟检索替换为真实文献 API（arXiv / Semantic Scholar），实现文献基线检测与新颖性验证的实数据支撑。新增 `MockSearcher` / `RealSearcher` 工厂模式与 5 秒超时自动降级机制。

---

## 13. 参考文献与致谢

### 参考文献

- **FastAPI** 官方文档：<https://fastapi.tiangolo.com/>
- **Uvicorn** ASGI 服务器：<https://www.uvicorn.org/>
- **Pydantic** 数据校验：<https://docs.pydantic.dev/>
- **OpenAI Python SDK**：<https://github.com/openai/openai-python>
- **SQLite WAL 模式**：<https://www.sqlite.org/wal.html>
- **Tailwind CSS**：<https://tailwindcss.com/>
- **Lucide Icons**：<https://lucide.dev/>
- **Google Fonts**（Fraunces / DM Sans / Noto Serif SC / Noto Sans SC / JetBrains Mono）：<https://fonts.google.com/>

### 致谢

本项目架构源于 `ThesisMiner项目架构文档.md`（v6.0 设计稿），核心理念为「生态对齐 · 创意落地 · 直通开题」，将 AI 的跨域发散能力与真实学术生存法则融合。感谢所有为学术论题生成与开题架构实践提供灵感的研究生、导师与开源社区贡献者。

---

> 文档版本 V8.0（多 Agent 架构版）· 最后更新 2026-06-20 · 对应应用版本 ThesisMiner v8.0.0
