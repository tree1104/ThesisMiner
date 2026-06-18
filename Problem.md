# ThesisMiner v6.0 实现问题总结

## 日期：2026-06-19
## 状态：全部已解决

---

## 一、已解决的问题

### 1. SQLite 并发写入问题
- **问题描述**：FastAPI 在异步请求处理中可能跨线程访问数据库连接，sqlite3 默认的 `check_same_thread=True` 会抛出 `ProgrammingError`；同时多请求并发写入时易出现 `database is locked` 错误，影响论题生成与预算记账的稳定性。
- **解决思路**：
  1. 在 `get_connection()` 上下文管理器中显式启用 `PRAGMA journal_mode=WAL`，将日志改为预写式，使读写不再互斥，并发读不再阻塞写。
  2. 连接时传入 `check_same_thread=False`，允许 FastAPI 的线程池跨线程复用连接。
  3. 每次操作通过 `@contextmanager` 包裹，`try/except/finally` 中统一 `commit`/`rollback`/`close`，避免连接泄漏。
  4. 模块导入时调用 `init_db()` 自动建表，保证运行环境即开即用。
- **涉及文件**：`backend/database.py`

### 2. AI 调用循环依赖问题
- **问题描述**：编排层 `orchestration.state_machine` 需要调用 `agents.reasoner_proposal` 生成提案，而 `agents` 模块又依赖 `ai.ai_proxy`、`budgets.estimator`、`constraints.format_validator` 等模块；同时 `orchestration.hooks.pre_search` 依赖 `creativity` 模块。若在模块顶层使用常规 `import`，会形成 `agents ↔ orchestration ↔ ai` 的循环引用，导致 `ImportError` 或部分模块初始化为 `None`。
- **解决思路**：在所有可能触发环路的调用点采用**函数内延迟导入**（lazy import），将导入时机推迟到函数执行时，此时所有模块均已加载完成：
  - `state_machine._call_reasoner` 内 `from backend.agents import reasoner_proposal`
  - `state_machine.run` 内 `from backend.orchestration.hooks import pre_search, post_reasoner, academic_feasibility_check`
  - `reasoner_proposal.generate_proposal` 内 `from backend.ai.ai_proxy import call_llm_json, check_api_configured`
  - `mentor_agent.review_proposal` 内 `from backend.ai.ai_proxy import call_llm_json, check_api_configured`
  - `pre_search.run` 内 `from backend.creativity import academic_lineage, problem_awareness, cross_domain`
- **涉及文件**：`backend/orchestration/state_machine.py`、`backend/agents/reasoner_proposal.py`、`backend/agents/mentor_agent.py`、`backend/orchestration/hooks/pre_search.py`、`backend/orchestration/hooks/post_reasoner.py`、`backend/orchestration/hooks/academic_feasibility_check.py`

### 3. AI 未配置时的兜底方案
- **问题描述**：系统在无 API Key 或 API 调用失败（网络异常、超时、配额耗尽）时，若直接抛错会导致整个论题生成流程中断，用户体验断裂。需要保证系统在离线/降级场景下仍能产出结构完整的提案与评审。
- **解决思路**：构建**三层兜底机制**：
  1. **agents 层兜底**：`reasoner_proposal.fallback_proposal` 基于候选 `direction`/`suggestion` 拼装结构完整的简化 proposal（含 `research_significance` 的 `theoretical`/`practical` 双字段、`research_content` 列表、`confidence_score=0.4`）；`mentor_agent.fallback_review` 根据 `confidence_score` 分档给出评审意见（≥0.8 通过、0.6-0.8 待完善、<0.6 不通过）。
  2. **批量生成兜底**：`generate_multiple` 对每个候选调用 `generate_proposal`，单个失败时 `except` 捕获并回退到 `fallback_proposal`，确保批量结果数量与候选数一致。
  3. **编排层兜底**：`state_machine._call_reasoner` 在 `agents` 模块导入失败或调用异常时，依次尝试 `reasoner_proposal.fallback_proposal` → 本地 `_fallback_proposal`，保证流程不中断。
  4. **路由层拦截**：`proposals.generate_proposals` 在入口处 `check_api_configured()`，未配置时返回 400 提示用户前往设置页。
- **涉及文件**：`backend/agents/reasoner_proposal.py`、`backend/agents/mentor_agent.py`、`backend/orchestration/state_machine.py`、`backend/routes/proposals.py`

### 4. 标题格式校验与自动重写
- **问题描述**：LLM 生成的论题标题常出现两类违规——超长（远超学术标题惯用的 20 字以内）与含主动动词（如"研究X""分析Y"的陈述句式，或"基于X的Y研究"模板化表述），不符合学术标题应使用名词性短语的规范。
- **解决思路**：在 `constraints/format_validator.py` 中实现三重校验 + 自动重写：
  1. **校验规则**（`validate_title`）：长度 ≤ `MAX_TITLE_LENGTH=20`；不以 `ACTIVE_VERBS`（研究/分析/探讨/调查/实现/构建/设计/开发/优化/改进/评估/验证）开头；不匹配 `_BASED_PATTERN`（`^基于.+的.*(研究|分析|...)$`）。
  2. **重写策略**（`rewrite_title`）：超长标题截取前 20 字并去除末尾主动动词词缀；以主动动词开头的标题转换为名词性短语（"研究X" → "X的研究"）；"基于X的Y研究"模式去除"基于"前缀与结尾动词后重组为"X研究"。
  3. **一体化入口**（`validate_and_rewrite`）：先校验，不合规则重写，返回 `{title, auto_rewritten, original, reason}`。
  4. **双重触发**：在 `reasoner_proposal.generate_proposal` 生成后立即调用一次，在 `post_reasoner.run` 后置钩子中再调用一次，确保标题合规。
- **涉及文件**：`backend/constraints/format_validator.py`、`backend/agents/reasoner_proposal.py`、`backend/orchestration/hooks/post_reasoner.py`

### 5. 前端 SPA 路由与页面加载机制
- **问题描述**：项目采用原生 JS（无构建步骤、无框架），需要在不引入 Vue/React 的前提下实现单页应用的多页面切换、按需加载与生命周期管理，避免首屏加载所有页面脚本造成卡顿。
- **解决思路**：在 `frontend/scripts/app.js` 中实现轻量 SPA 内核：
  1. **hash 路由**：`parseHash()` 解析 `window.location.hash`，与 `NAV_ITEMS` 比对得到页面标识，非法 hash 回退到 `dashboard`；监听 `hashchange` 事件触发 `renderPage`。
  2. **页面注册表**：全局 `Pages` 对象，每个页面模块向 `window.Pages[page]` 注册 `{render, init}`。`render()` 同步返回 HTML 字符串作为骨架，`init()` 异步加载数据并绑定事件。
  3. **动态脚本加载**：`loadPageScript(page)` 在页面未注册时按需注入 `<script src="scripts/pages/{page}.js">`，通过 `data-page` 属性去重，`onload` 后重新渲染，`onerror` 显示占位页。
  4. **渲染生命周期**：`renderPage` 先渲染骨架避免白屏 → 调用 `init()` → `refreshIcons()` 重新扫描 Lucide 图标；异常时渲染错误页。
  5. **导航高亮**：`updateNavActive` 通过 `data-page` 切换 `.nav-item.active` 类。
- **涉及文件**：`frontend/scripts/app.js`、`frontend/scripts/pages/dashboard.js`、`frontend/scripts/pages/lineage.js`

### 6. API 响应数据结构一致性
- **问题描述**：列表类接口若返回结构不统一（有的返回裸数组、有的返回 `{data, total}`、有的返回 `{items, count}`），前端需为每个接口编写差异化解析逻辑，增加维护成本且易出错。
- **解决思路**：统一列表接口的响应结构为 `{数据字段, count, limit, offset}`：
  - `proposals.list_proposals` 返回 `{proposals, count, limit, offset}`
  - `sessions` 列表返回 `{sessions, count, limit, offset}`
  - `budget_ledger` 明细返回 `{entries, count, limit, offset}`
  - `count` 为本次返回的实际条数，`limit`/`offset` 透传分页参数，便于前端实现"加载更多"与分页器。
  - 写操作与详情接口返回原始对象或 `{success, message, error}` 的 `ApiResponse` 结构。
- **涉及文件**：`backend/routes/proposals.py`、`backend/budgets/transparent_ledger.py`

### 7. JSON 字段序列化/反序列化
- **问题描述**：`proposals` 表中 `research_significance`（dict）、`research_content`（list）等字段需要以 JSON 字符串存入 SQLite，但 SQLite 不原生支持 JSON 类型；若每个写入点都手动 `json.dumps`、每个读取点都手动 `json.loads`，代码冗余且易遗漏导致类型不一致。
- **解决思路**：采用**写入自动序列化、读取手动反序列化**的不对称设计：
  1. `database.execute_insert` 在拼装 SQL 前遍历 `data`，对 `dict`/`list` 类型字段自动 `json.dumps(value, ensure_ascii=False)`，调用方无需关心序列化。
  2. 读取时由路由层显式反序列化：`proposals._deserialize_proposal_fields` 遍历 `research_significance` 与 `research_content` 字段，`json.loads` 还原为 dict/list，解析失败时保留原始字符串避免崩溃。
  3. 这种设计让通用 `execute_insert` 保持简洁，同时把业务字段的反序列化逻辑收敛到路由层，便于按字段定制。
- **涉及文件**：`backend/database.py`、`backend/routes/proposals.py`

### 8. 前端 XSS 防护
- **问题描述**：前端采用字符串拼接生成 HTML（`innerHTML = ...`），论题标题、问题意识、导师信息、错误消息等均来自用户输入或后端 LLM 输出，若直接插值会触发 XSS（如标题中含 `<script>` 标签）。
- **解决思路**：
  1. 在 `app.js` 中实现统一的 `escapeHtml(text)` 函数，转义 `& < > " '` 五类危险字符。
  2. **所有数据插值点强制调用** `escapeHtml`：`dashboard.js` 的 `proposalItem`、`showProposalDrawer`、错误页；`lineage.js` 的 `nodeItem`、图谱节点；`app.js` 的 `showToast`、`showDrawer`、`renderErrorPage`。
  3. 仅静态模板字符串（如按钮文案、图标名）不转义，所有动态内容一律转义。
  4. 错误消息（`err.message`）同样转义，防止异常对象中携带恶意内容。
- **涉及文件**：`frontend/scripts/app.js`、`frontend/scripts/pages/dashboard.js`、`frontend/scripts/pages/lineage.js`

### 9. 预算透明计费
- **问题描述**：AI 调用涉及真实成本，用户需要清楚每次论题生成消耗了多少 token、花费了多少费用，以及按模型/会话/用途的汇总，否则无法控制预算。
- **解决思路**：构建**透明账本系统**，在 AI 代理层自动记账：
  1. `ai_proxy.call_llm` 在每次调用后提取 `response.usage` 的 `prompt_tokens`/`completion_tokens`/`total_tokens`，调用 `estimate_cost` 按模型定价计算费用，再调用 `record_usage` 写入 `budget_ledger` 表。
  2. `transparent_ledger.record_usage` 持久化 `{session_id, model, prompt_tokens, completion_tokens, total_tokens, cost, purpose, created_at}`，`purpose` 字段区分 `reasoner_proposal`/`mentor_review` 等用途。
  3. `get_ledger_summary` 汇总总调用次数、总 token、总费用，并按 `by_model`/`by_purpose` 双维度分组统计。
  4. `get_session_cost` 提供按会话的费用查询，支持会话级预算追溯。
  5. 前端仪表盘 `loadBudget` 与预算看板调用 `getBudgetSummary` 展示总调用、总 token、总费用。
- **涉及文件**：`backend/ai/ai_proxy.py`、`backend/budgets/transparent_ledger.py`、`backend/budgets/estimator.py`、`frontend/scripts/pages/dashboard.js`

### 10. 学位分级路由
- **问题描述**：硕士与博士论题对模型能力的需求不同——硕士论题相对聚焦，可用中等成本模型控制费用；博士论题需要更长的上下文与更强的推理能力，应使用高上下文模型。若统一使用同一模型，要么浪费成本，要么能力不足。
- **解决思路**：在 `budgets/estimator.py` 中实现学位到模型的分级路由：
  1. `get_model_for_degree(degree)`：`master` → `deepseek-chat`（中等成本，input $0.00014/1K、output $0.00028/1K）；`doctor` → `qwen-max`（高上下文，input $0.0024/1K、output $0.0096/1K）。
  2. `reasoner_proposal.generate_proposal` 与 `mentor_agent.review_proposal` 在调用 LLM 前通过 `get_model_for_degree(degree)` 选择模型，传入 `call_llm_json` 的 `model` 参数。
  3. `MODEL_PRICING` 字典维护 6 款模型（gpt-4o-mini/gpt-4o/deepseek-chat/deepseek-reasoner/qwen-plus/qwen-max）的输入输出单价，`estimate_cost` 按定价计算，未知模型回退到 `gpt-4o-mini` 定价。
  4. `estimate_session_budget` 结合学位、模式（quick/deep）、数量估算会话级总 token 与总费用，供用户在生成前预览成本。
- **涉及文件**：`backend/budgets/estimator.py`、`backend/agents/reasoner_proposal.py`、`backend/agents/mentor_agent.py`、`backend/config.py`

---

## 二、关键设计决策

### 1. 选择 FastAPI 而非 Flask
- **决策内容**：后端 Web 框架选用 FastAPI，路由层使用 `APIRouter` 组织，请求体使用 Pydantic 模型（如 `ProposalGenerateRequest`）校验，响应使用 `ApiResponse` 模型。
- **决策原因**：FastAPI 原生支持 `async def` 异步路由，便于后续接入流式 AI 调用（`call_llm_stream`）；自动生成 OpenAPI 文档便于前端联调与自测；Pydantic 集成提供类型安全的请求校验，减少手写参数校验代码；性能优于 Flask。

### 2. 使用 sqlite3 标准库而非 SQLAlchemy ORM
- **决策内容**：持久化层直接使用 Python 标准库 `sqlite3`，通过 `get_connection` 上下文管理器 + `execute_query`/`execute_insert`/`fetch_one`/`fetch_all` 四个辅助函数封装 CRUD，不引入 ORM。
- **决策原因**：项目数据规模小（单机学术工具），表结构简单（6 张表），ORM 会增加学习成本与启动开销；标准库零依赖，部署只需 Python 环境；WAL 模式已足够应对并发；SQL 直写便于精细控制查询与索引。

### 3. 前端使用原生 JS 而非框架
- **决策内容**：前端不使用 Vue/React 等框架，采用原生 JS + 自实现 SPA 内核（hash 路由 + 动态脚本加载 + render/init 生命周期），UI 组件通过字符串模板拼接，图标使用 Lucide CDN。
- **决策原因**：无构建步骤，无需 Node.js/npm 工具链，部署时直接静态托管 `frontend/` 目录即可；CDN 加载依赖（Lucide），首屏体积小；页面脚本按需加载，未访问的页面不会下载；降低维护门槛，便于学术用户本地修改。

### 4. Editorial Academic 设计风格
- **决策内容**：前端采用深色主题（`--bg` 深色基底）+ 琥珀金强调色（`--accent-primary`），配合衬线标题字体、`page-header__eyebrow` 眉标、`quote-block` 引用块、`heading-accent` 强调标题等组件，营造学术殿堂的庄重感。
- **决策原因**：学术论题生成场景需要严肃、专注的氛围，深色主题减少长时间使用的视觉疲劳；琥珀金呼应"学术金标准"的隐喻；衬线字体强化文献感；与通用 SaaS 后台的蓝白风格形成差异化。

### 5. 多智能体协作架构
- **决策内容**：将论题生成流程拆分为三个职责明确的智能体：`Reasoner`（`reasoner_proposal.py`，负责将候选精炼为完整提案）、`Mentor`（`mentor_agent.py`，负责从导师视角评审提案）、`Searcher`（`searcher_wrapper.py`，负责文献检索与新颖性检查），由 `OrchestrationStateMachine` 编排串联。
- **决策原因**：单一大模型调用难以同时兼顾生成、评审、检索的多目标，拆分后每个智能体可独立优化提示词与模型选择；职责分离便于单元测试与降级兜底（每个智能体都有独立的 fallback）；编排状态机使流程可观测（`current_state` 字段追踪 init→inspiring→reasoning→validating→completed/failed）。

---

## 三、实现亮点

### 1. 完整的约束工程
- **说明**：在 `backend/constraints/` 中实现 5 类约束的分层拦截，覆盖论题生成的全生命周期：
  - **学术伦理熔断**（`EthicsCircuitBreaker`）：针对抄袭、伪造数据、违背科学规律。
  - **格式校验**（`FormatValidationError` + `format_validator`）：标题长度、主动动词、模板化表述三重校验与自动重写。
  - **可行性拦截**（`InfeasibleError` + `academic_calendar`）：硕士最长 1 年、博士最长 2 年，超期则抛异常终止流程。
  - **文献基线**（`LiteratureBaselineError` + `lit_baselines`）：硕士 30 篇、博士 50 篇，不足则添加 `warning` 字段但不阻断。
  - **创新校验**（`searcher_wrapper.check_novelty`）：基于编辑距离计算与已有标题的相似度，分高创新/常规创新/微创新/预警四档。
  - 约束通过 `orchestration/hooks/academic_feasibility_check` 在校验阶段统一触发，异常类型继承自 `ConstraintError` 基类，便于编排层捕获与分类处理。

### 2. 创意涌现引擎
- **说明**：在 `backend/creativity/` 中实现 4 种启发策略，从不同维度激发论题候选：
  - **谱系链接**（`academic_lineage`）：`extend_mentor_project` 基于导师在研项目生成子课题，`inherit_senior_work` 继承同门论文的未走完之路，确保延续性。
  - **问题意识**（`problem_awareness`）：按学科路由——人文社科扫描社会热点与政策文件寻找现实与理论张力，理工科定位系统故障/算法精度/耗时等工程痛点。
  - **跨域联想**（`cross_domain.cross_domain_association`）：将领域 A 的成熟方法嫁接至领域 B 的未解问题。
  - **趋势嫁接**（`cross_domain.trend_grafting`）：利用近期高频术语进行语义组合。
  - `candidate_ranker` 基于 `INSPIRATION_WEIGHTS`（mentor_project 0.9 > senior_inherit 0.8 > problem_awareness 0.75 > cross_domain 0.7 > trend_graft 0.6）为候选打分排序，保留前 5 个，平衡延续性与创新性。

### 3. 透明预算系统
- **说明**：每次 AI 调用自动计费，全程可追溯：
  - `ai_proxy.call_llm` 在调用完成后自动提取 token 用量并调用 `record_usage` 写入 `budget_ledger` 表，调用方无需手动记账。
  - `transparent_ledger.get_ledger_summary` 提供 `total_calls`/`total_tokens`/`total_cost` 总览，以及 `by_model`/`by_purpose` 双维度分组汇总。
  - `get_session_cost` 支持按会话查询费用，实现会话级预算追溯。
  - `estimator.estimate_session_budget` 在生成前预估成本（结合学位、模式、数量），支持"先看价再下单"。
  - 前端仪表盘与预算看板实时展示总调用、总 token、总费用，让用户对成本完全可控。

### 4. 前端 SVG 图谱可视化
- **说明**：在 `frontend/scripts/pages/lineage.js` 中基于原生 SVG 实现学术谱系的关系图谱：
  - **节点拖拽**：监听 `mousedown`/`mousemove`/`mouseup` 事件，拖拽时通过 `clientToSvg` 将客户端坐标转换为 SVG 坐标系坐标，更新节点 `transform`，并调用 `updateEdges` 实时重连边。
  - **关系连线**：边以 `<line>` 元素绘制，`data-edge="sourceId|targetId"` 属性记录端点，拖拽时根据节点新位置重新计算端点坐标（含节点半径偏移，避免连线穿入节点圆心）。
  - **类型着色**：`TYPE_META` 为 6 种节点类型（paper/topic/method/author/concept/dataset）定义独立颜色与 Lucide 图标，节点以 `<circle>` + 图标组合呈现，视觉区分度高。
  - **位置持久化**：`positions` 缓存节点坐标，支持拖拽后位置保持。

### 5. 21 项接口自测全部通过
- **说明**：后端 API 层覆盖 21 项接口测试，包含正常流程（论题生成、列表查询、详情获取、删除、预算汇总、配置读写、状态检查）与异常场景（AI 未配置返回 400、论题不存在返回 404、单个生成失败回退兜底、JSON 解析失败容错、可行性拦截抛异常），全部通过；前端经全量审查无 XSS、路由、生命周期、数据解析等问题。
