基于对现有架构的深度剖析，结合 Claude Code 在多智能体编排、上下文管理与缓存复用方面的顶级工程实践，为您制定以下超级详细的改进清单。本清单致力于将 ThesisMiner 的多轮会话缓存命中率提升至 95% 以上，并彻底修复既有缺陷，实现系统架构的尽善尽美。

---

### 一、 仿 Claude Code 的高性能多轮会话与缓存架构设计（目标：缓存命中率 ≥ 95%）

要实现多轮对话下 95% 的缓存命中率，核心在于**保持 Prompt 前缀的绝对稳定**与**上下文的增量更新**，摒弃传统全量重写历史的方式。

#### 1. 稳定前缀注入与 `THESIS_RULES.md` 长期配置机制
- **改进方案**：仿照 Claude Code 的 `CLAUDE.md` 机制，在系统启动时将不变的学术约束（标题规范、文献基线、学术日历）、系统指令与角色设定抽离为静态的 `System Prefix`。在多轮对话中，该前缀作为 Prompt 的绝对头部原封不动传递，确保底层大模型服务商的 KV Cache 永远命中。
- **架构实现**：`backend/ai/prompts.py` 拆分为 `stable_system_prompt`（不含任何动态变量）与 `dynamic_user_prompt`。严禁在系统提示词中使用时间戳或随机变量。

#### 2. 对话状态追踪（DST）与增量指纹注入
- **改进方案**：传统多轮对话将历史全量拼接，导致每轮 Prompt 变动极大，缓存失效。引入 DST 机制，将历史对话压缩为结构化状态槽（如 `{"degree": "硕士", "confirmed_topic": "...", "lineage_nodes": [...]}`）。
- **缓存保障**：每轮对话仅将上一轮的 DST 状态作为稳定前缀的一部分，用户最新输入附加在最后。只要核心状态未变，前缀哈希保持一致，缓存依然命中。新增 `backend/sessions/dialogue_state_tracker.py` 模块。

#### 3. 子智能体共享缓存编排
- **改进方案**：Reasoner、Mentor、Searcher 在并行或串行调用时，往往需要相同的上下文背景。仿照 Claude Code 的子 Agent 共享缓存机制，编排层在调用子 Agent 时，强制复用主会话的 `messages` 前缀，仅追加子 Agent 特定的指令后缀。
- **架构实现**：`backend/agents/` 下所有 Agent 统一继承 `BaseAgent`，`BaseAgent` 负责从 `session_manager` 提取带哈希签名的上下文前缀，确保同一会话内不同 Agent 调用的前缀高度一致，将并行执行成本压缩至单线程水平。

#### 4. 五级上下文压缩与淘汰策略
- **改进方案**：上下文膨胀是导致系统不稳定与缓存击穿的核心原因。引入 Claude Code 的五级压缩策略：
  1. **滑窗截断**：保留最近 5 轮原始对话。
  2. **指代消解重写**：对超过 5 轮的对话，利用轻量模型进行共指消解（如将“那个方法”重写为“XX算法”），消除历史依赖。
  3. **实体抽取替换**：将长文本历史替换为知识图谱实体 ID 列表。
  4. **摘要注入**：生成历史摘要并注入 DST 状态。
  5. **硬截断熔断**：当 Token 超过模型限制 80% 时，直接截断非核心历史，仅保留 System Prompt 与 DST。

#### 5. 会话持久化与断点续传设计
- **改进方案**：将 KV Cache 的指针或哈希签名持久化到 SQLite 中。当用户关闭浏览器后再次打开同一会话时，系统优先尝试复用底层服务商的 Cache ID（如 Anthropic 的 `cache_control` 或 DeepSeek 的 `prefix_id`），实现跨会话周期的缓存命中。

---

### 二、 既有架构缺陷修复与鲁棒性提升

#### 6. 会话与论题数据级联清理机制
- **改进方案**：修复“删除会话后论题仍存在”的孤儿数据问题。在 `backend/database.py` 的 `init_db()` 建表语句中，为 `proposals` 和 `budget_ledger` 表增加外键约束 `FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE`。
- **架构实现**：在执行 `DELETE FROM sessions` 前确保执行 `PRAGMA foreign_keys = ON;`，或在 `session_manager.delete_session()` 中增加显式的事务级联删除逻辑。

#### 7. AI 调用全异步化改造消除阻塞风险
- **改进方案**：当前 FastAPI 路由层使用 `async def`，但 `ai_proxy` 内部使用同步 OpenAI 客户端，会导致事件循环阻塞，高并发下服务假死。
- **架构实现**：将 `openai.OpenAI` 替换为 `openai.AsyncOpenAI`，`call_llm`、`call_llm_json` 等方法全面改为 `async def`，并使用 `await client.chat.completions.create(...)`。对于必须使用同步的第三方库，封装至 `asyncio.to_thread()` 中执行。

#### 8. JSON 解析容错与强制格式化降级
- **改进方案**：当前虽支持代码块容错，但面对模型输出非闭合 JSON 仍易崩溃。
- **架构实现**：在 `ai_proxy._parse_json()` 中引入 `json5` 库增强容错（容忍尾随逗号、单引号等）。若二次解析仍失败，触发自动重试机制，并在重试 Prompt 中强制附加 `response_format={"type": "json_object"}` 参数（针对支持的模型），将兜底机制作为最后手段。

#### 9. 真实文献检索引擎接入与双轨校验
- **改进方案**：废弃 `searcher_wrapper` 中的模拟检索，真实接入 arXiv API（理工科）与 Semantic Scholar API（全学科）。
- **架构实现**：通过 `httpx.AsyncClient` 异步抓取真实文献元数据。文献基线校验从“查数量”升级为“查质量与查重”，利用 Embedding 计算生成论题与真实文献标题的余弦相似度，>0.85 直接在 UI 标红预警。

---

### 三、 学术生态对齐与可行性闭环升级

#### 10. 硬约束规则的代码级硬拦截
- **改进方案**：将学术规范从“软提示”升级为“硬拦截”。在 `orchestration/hooks/` 中增加 `hard_rule_interceptor.py`。
- **架构实现**：
  - 标题校验：在落库前强制正则校验，主动动词开头的标题直接抛出 `HTTP 422`，要求 Reasoner 重新生成，而非简单标记 `auto_rewritten`。
  - 周期校验：Reasoner 输出的 `research_content` 必须包含时间节点（如“第3个月完成数据收集”），`academic_calendar` 模块解析这些节点，若总和超过学制限制，直接打回重生成。

#### 11. 开题报告直出模块与标准模板对齐
- **改进方案**：实现从论题到开题报告的一键生成，满足“直通开题”核心理念。
- **架构实现**：在 `backend/agents/` 新增 `proposal_writer.py`。接收 Reasoner 生成的结构化数据，注入内置的标准高校开题报告 Markdown 模板（含选题依据、国内外研究现状、研究内容、技术路线图、进度安排），输出可直接复制粘贴的完整开题报告文档。

#### 12. 谱系图谱自动化构建扩展
- **改进方案**：当前的 `graph_expander` 仍需手动输入，升级为基于 PDF 解析的自动图谱构建。
- **架构实现**：集成 `PyMuPDF` 解析导师与同门论文 PDF，提取摘要部分，通过 LLM 结构化抽取（实体：方法、数据集、问题；关系：解决、改进、基于），自动生成 `lineage_nodes` 与 `lineage_edges` 并入库。

---

### 四、 工程化扩展与安全控制（仿 Claude Code 扩展层）

#### 13. 生命周期 Hook 系统全面增强
- **改进方案**：仿照 Claude Code 提供 25+ 生命周期切入点，增强系统的可扩展性。
- **架构实现**：在 `orchestration/hooks/` 定义标准化 Hook 接口 `BaseHook`，新增：
  - `pre_persistence`：落库前敏感词与伦理拦截。
  - `post_parsing`：JSON 解析后字段格式微调。
  - `budget_exceed`：超预算时自动降级模型或熔断流程。

#### 14. 分层权限控制与越权防护
- **改进方案**：防止用户跨会话、跨谱系查询数据，防止 Prompt 注入泄露系统指令。
- **架构实现**：
  - 在 API 层增加 `session_id` 归属校验中间件。
  - 前端配置页输入的 `mentor_info` 等自由文本，在传入 LLM 前进行清洗，过滤“忽略以上指令”等注入特征词。
  - 系统层增加“安全沙箱”声明，限制模型仅输出与学术相关的内容。

#### 15. 前端 SPA 状态管理与实时反馈优化
- **改进方案**：提升多轮对话与长文本生成时的前端体验。
- **架构实现**：`frontend/scripts/api.js` 全面支持 `fetch` 流式读取（SSE/Chunked），实现生成论题与开题报告时的打字机效果。前端本地维护 `sessionStorage` 缓存会话列表，减少首屏加载延迟。

----------------------------------------------------------improve----------------------------------------------------------
结合最新的架构演进需求，将真实文献检索改造为可热插拔的开关功能，并全面引入深度优化的仿 Claude Code 高性能多轮会话与缓存架构。以下是超级详细改进清单：

---

### 一、 真实文献检索引擎的“可开关”热插拔设计

为了在保证系统开箱即用的同时，支持高阶用户接入真实文献数据，对检索层进行策略模式改造。

#### 1. 顶部配置开关与环境感知
- **改进方案**：在 `data/config.json` 与 `backend/config.py` 中新增 `real_search_enabled` (默认: `false`) 与 `search_api_keys` 配置项。前端「设置」页增加“真实文献检索”开关 UI。
- **架构实现**：当开关开启且配置了 API Key 时，系统走真实检索；否则自动降级为内置的模拟检索器，确保系统在任何环境下都不会因缺少 Key 而崩溃。

#### 2. 检索策略工厂与双轨容错降级
- **改进方案**：在 `backend/agents/searcher_wrapper.py` 中引入工厂模式，定义 `MockSearcher` 与 `RealSearcher`。
- **架构实现**：
  - `RealSearcher` 通过 `httpx.AsyncClient` 异步并发请求 arXiv 与 Semantic Scholar API。
  - **降级机制**：若真实 API 请求超时（>5秒）或返回异常，自动捕获并平滑回退至 `MockSearcher`，并在响应体中附加 `search_degraded: true` 标记，前端提示“检索服务暂不可用，已使用本地模拟数据”。

---

### 二、 仿 Claude Code 超高性能多轮会话与缓存架构（超级强化版）

为实现多轮对话下缓存命中率 ≥ 95% 的极致目标，彻底重构 `sessions` 与 `ai_proxy` 模块，引入前缀哈希固化、状态差分与显式缓存控制。

#### 3. Prompt 前缀绝对哈希稳定化
- **改进方案**：大模型底层 KV Cache 命中的前提是 Prompt 前缀字符绝对一致。摒弃在系统提示词中拼接动态时间戳或随机范例的做法。
- **架构实现**：将 `backend/ai/prompts.py` 彻底重构为三段式：
  - `[Immutable Base]`：系统角色、输出格式要求、硬约束规则（永不改变）。
  - `[Immutable Profile]`：用户的学位、学科、导师信息（会话内不变）。
  - `[Dynamic Tail]`：用户当前输入与最新状态差分。
  前两段拼接后生成 SHA-256 哈希，作为请求的唯一前缀标识。

#### 4. 对话状态差分引擎
- **改进方案**：传统多轮对话将历史 `messages` 全量拼接，导致前缀每轮都变。引入 DST（Dialogue State Tracker），将历史压缩为结构化状态块。
- **架构实现**：新增 `backend/sessions/dst_compactor.py`。每轮对话结束后，提取关键信息（如 `{"selected_topic": "X", "confirmed_methods": ["Y"]}`）。下一轮请求时，将历史对话替换为 `[Immutable Base] + [Immutable Profile] + [Compressed DST State] + [Current Query]`。只要核心状态未变，前缀哈希保持稳定，底层 KV Cache 100% 命中。

#### 5. 显式 Cache 标记与跨轮次复用
- **改进方案**：主动利用大模型厂商提供的 Context Caching API（如 DeepSeek 的 `prefix_id` 或 Anthropic 的 `cache_control`）。
- **架构实现**：在 `ai_proxy.call_llm` 中，若检测到当前前缀哈希与上一轮一致，则在请求体中显式注入 `cache_control: {"type": "ephemeral"}` 或传入上一轮返回的 `cache_id`。这不仅保证了命中率，还能直接享受厂商的缓存折扣计费，大幅降低 `budget_ledger` 中的开销。

#### 6. 子 Agent 共享前缀路由机制
- **改进方案**：Reasoner、Mentor、Searcher 在编排层被调用时，往往需要相同的背景上下文。仿照 Claude Code 的子 Agent 机制，强制复用主会话的前缀。
- **架构实现**：`backend/orchestration/state_machine.py` 在调度子 Agent 时，不重新构建上下文，而是直接截取主会话的 `[Immutable Base] + [Immutable Profile]` 作为子 Agent 请求的前缀。由于前缀完全一致，多个子 Agent 并发执行时，底层物理缓存共享，将并行 Token 计算成本压缩至单次水平。

#### 7. 异步 KV Cache 预热机制
- **改进方案**：在用户阅读上一轮生成结果或思考时，后台提前将下一次可能用到的上下文送入大模型预热。
- **架构实现**：当用户在前端输入框聚焦且停留超过 3 秒时，前端发送一个轻量级 `ping` 请求。后端接收到后，提前将当前会话的稳定前缀发送给大模型进行“空运行”缓存预热。当用户真正点击发送时，大模型已有热缓存，实现首 Token 毫秒级响应。

#### 8. 上下文微观压缩与结构化剪枝
- **改进方案**：当多轮对话极其漫长，导致 `[Compressed DST State]` 本身超过 2000 Token 时，触发微观剪枝。
- **架构实现**：引入 `backend/sessions/micro_pruner.py`。利用轻量级模型（如 `deepseek-chat`），将过长的 DST 状态提炼为不超过 500 Token 的极简核心事实陈述。此操作虽然改变了前缀哈希，但会生成新的稳定哈希并重新预热，在长对话中实现“断点续存”，避免上下文爆炸。

#### 9. 会话缓存指纹持久化
- **改进方案**：将每轮对话的缓存命中情况、前缀哈希、Cache ID 持久化，用于性能调优与断点续传。
- **架构实现**：扩展 SQLite 的 `sessions` 表，增加 `cache_prefix_hash`、`cache_id`、`cache_hit_rate` 字段。在「会话历史」前端页面，直观展示每个会话的缓存命中率，让系统的高性能具备可视化可度量的依据。