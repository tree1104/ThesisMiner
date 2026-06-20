# ThesisMiner v8.0 变更日志

> 本文档记录 ThesisMiner v8.0 的所有变更，包括新增功能、改进项、修复项、破坏性变更与迁移指南。

---

## 目录

- [版本信息](#版本信息)
- [新增功能](#新增功能)
- [改进项](#改进项)
- [修复项](#修复项)
- [破坏性变更](#破坏性变更)
- [迁移指南](#迁移指南)
- [已知问题](#已知问题)
- [致谢](#致谢)

---

## 版本信息

| 项目 | 内容 |
|------|------|
| 版本号 | v8.0.0 |
| 发布日期 | 2026-06-15 |
| 代码名称 | Multi-Agent Horizon |
| 前一版本 | v7.5.3 |
| 下一版本 | v8.1.0（计划中） |

### 版本摘要

ThesisMiner v8.0 是一次重大版本更新，引入了全新的多 Agent 架构、五阶段闭环导航流程、多对话管理、D3.js 谱系图谱、DeepSeek 缓存优化等核心特性。本次更新重构了约 60% 的后端代码，新增了 12 个核心模块，是自 v6.0 全栈实现以来最大的一次架构升级。

---

## 新增功能

### 1. 多 Agent 架构

#### 1.1 概述

v8.0 引入了全新的多 Agent 架构，将原有的单一推理引擎拆分为四个专业化 Agent：

- **ReasonerAgent**：负责信息确权与逻辑推理
- **MentorAgent**：负责创意生成与导师指导
- **SearcherAgent**：负责文献检索与谱系构建
- **CriticAgent**：负责约束校验与质量评分

#### 1.2 技术细节

**Agent 基类设计：**

```python
class BaseAgent(ABC):
    @abstractmethod
    async def run(self, input: str) -> AgentResult:
        pass

    async def stream(self, input: str) -> AsyncGenerator[str, None]:
        pass
```

**Agent 注册机制：**

- 全局 `AGENT_REGISTRY` 注册表
- 支持运行时动态注册
- 支持自定义 Agent 扩展

**Agent 上下文隔离：**

- 每个 Agent 拥有独立的 `AgentContext`
- 上下文包含 session_id、conversation_id、stage、history
- Agent 间通过编排器传递结果

#### 1.3 编排状态机

新增 `OrchestrationStateMachine`，管理五阶段流程的状态转换：

```
IDLE → INFORMATION_CONFIRMATION → IDEATION → VALIDATION
                                                      ↓
                                              GENERATION → DEEP_ASSISTANCE → COMPLETED
                                                      ↑
                                              (validation_failed 回退到 IDEATION)
```

**支持的 Hook 类型：**

- `ENTER_STATE`：进入新状态时触发
- `EXIT_STATE`：离开状态时触发
- `PRE_SEARCH`：检索前触发
- `POST_REASONER`：Reasoner 执行后触发
- `FEASIBILITY`：可行性评估时触发
- `HARD_RULE`：硬约束检查时触发

#### 1.4 相关文件

- `backend/agents/base_agent.py`（新增）
- `backend/agents/reasoner_agent.py`（新增）
- `backend/agents/mentor_agent.py`（新增）
- `backend/agents/searcher_agent.py`（新增）
- `backend/agents/critic_agent.py`（新增）
- `backend/agents/registry.py`（新增）
- `backend/orchestrator/state_machine.py`（新增）

---

### 2. 五阶段闭环导航流程

#### 2.1 概述

v8.0 将论题生成流程重构为五个闭环阶段：

1. **信息确权**（Information Confirmation）：收集用户基本信息
2. **创意生成**（Ideation）：基于四维引擎生成候选论题
3. **校验与回退**（Validation & Rollback）：多维度评估，失败回退
4. **多粒度生成**（Multi-granularity Generation）：标题/摘要/大纲/全文
5. **深度辅助三件套**（Deep Assistance）：文献精读/实验预研/答辩模拟

#### 2.2 四维创意引擎

创意生成阶段使用四维并行引擎：

| 维度 | 说明 | 数据来源 |
|------|------|----------|
| 导师项目延伸 | 基于导师近期项目延伸 | 导师信息表 |
| 前辈工作继承 | 基于同门师兄师姐工作 | 谱系图谱 |
| 问题意识驱动 | 基于领域痛点 | 文献检索 |
| 跨学科迁移 | 跨领域方法迁移 | 知识图谱 |

#### 2.3 校验与回退机制

- **硬约束**（fail-fast）：标题长度、学科匹配、导师方向、时间可行性、重复度、AI 痕迹
- **软约束**（评分制）：新颖性（4 维度）、可行性（4 方面）、风格质量（4 指标）
- **回退机制**：校验失败时携带改进建议回退到创意生成阶段

#### 2.4 相关文件

- `backend/orchestrator/five_stage_flow.py`（新增）
- `backend/orchestrator/rollback_handler.py`（新增）
- `backend/constraints/hard_rules.py`（新增）
- `backend/constraints/novelty_scorer.py`（新增）

---

### 3. 多对话管理

#### 3.1 概述

v8.0 支持在同一会话下创建多个并行对话，每个对话拥有独立的上下文。

#### 3.2 特性

- **对话创建**：创建新对话或基于现有对话分支
- **上下文隔离**：对话间上下文完全隔离，互不干扰
- **DST 压缩**：对话历史自动压缩，控制 Token 使用
- **缓存隔离**：每个对话有独立的缓存前缀（SHA-256 哈希）

#### 3.3 数据模型

```
Session (1) ──→ (N) Conversation (1) ──→ (N) Message
```

#### 3.4 相关文件

- `backend/models/conversation.py`（新增）
- `backend/agents/dst_compressor.py`（新增）
- `backend/api/conversation_api.py`（新增）

---

### 4. D3.js 谱系图谱

#### 4.1 概述

v8.0 使用 D3.js v7 构建交互式学术谱系图谱，可视化展示导师、前辈、论题、文献、项目之间的关系。

#### 4.2 特性

- **多种节点类型**：导师、前辈、论题、文献、项目、当前论题
- **多种边类型**：师生关系、论题继承、文献引用、项目关联
- **交互操作**：拖拽、缩放、过滤、详情查看、批量操作
- **多种布局**：力导向、树形、径向、聚类
- **导出格式**：SVG、PNG、PDF、JSON

#### 4.3 相关文件

- `frontend/src/components/lineage/LineageGraph.jsx`（新增）
- `frontend/src/components/lineage/CustomNodeRenderer.js`（新增）
- `frontend/src/components/lineage/CustomEdgeRenderer.js`（新增）
- `frontend/src/components/lineage/LayoutManager.js`（新增）

---

### 5. DeepSeek 缓存优化

#### 5.1 概述

v8.0 集成了 DeepSeek API 的上下文缓存功能，通过 SHA-256 前缀哈希实现缓存命中，显著降低 API 成本。

#### 5.2 三段式 Prompt 架构

```
+-------------------+-------------------+-------------------+
|   稳定前缀        |   动态中间        |   DST 尾部        |
|   (可缓存)        |   (不缓存)        |   (可能变化)      |
+-------------------+-------------------+-------------------+
```

- **稳定前缀**：系统提示、角色定义、规则说明 → 缓存的 key
- **动态中间**：用户输入、当前任务 → 不参与缓存
- **DST 尾部**：历史对话压缩 → 影响缓存命中

#### 5.3 缓存效果

| 场景 | v7.5 缓存命中率 | v8.0 缓存命中率 | 成本节省 |
|------|-----------------|-----------------|----------|
| 信息确权 | 0% | 85% | 85% |
| 创意生成 | 0% | 35% | 35% |
| 校验 | 0% | 78% | 78% |
| 多粒度生成 | 0% | 62% | 62% |
| 深度辅助 | 0% | 55% | 55% |
| **整体** | **0%** | **68.5%** | **68.5%** |

#### 5.4 相关文件

- `backend/cache/prefix_cache.py`（新增）
- `backend/cache/session_cache_manager.py`（新增）
- `backend/prompts/builder.py`（新增）

---

### 6. 透明账本

#### 6.1 概述

v8.0 引入透明账本机制，记录每一次 API 调用的 Token 使用与成本。

#### 6.2 记录内容

每条账本记录包含：

- 时间戳
- 会话 ID / 对话 ID
- 模型名称
- 阶段
- 输入 Token 数 / 输出 Token 数 / 总 Token 数
- 成本（USD）
- 是否缓存命中
- Agent 名称

#### 6.3 查询与导出

- 按会话/对话/模型/阶段查询
- 按时间范围过滤
- 导出为 CSV / JSON / Excel

#### 6.4 相关文件

- `backend/models/budget_ledger.py`（新增）
- `backend/api/budget_api.py`（新增）

---

### 7. 联网搜索展示

#### 7.1 概述

v8.0 在创意生成阶段增加联网搜索功能，实时检索最新文献与资讯，并在前端展示搜索过程。

#### 7.2 特性

- 实时搜索：调用外部检索 API
- 过程展示：前端流式显示搜索进度
- 结果整合：搜索结果整合到创意生成
- 来源标注：每个创意标注来源（导师项目/前辈继承/问题意识/跨学科）

#### 7.3 支持的检索源

- Semantic Scholar API
- arXiv API
- PubMed API（医学领域）
- Google Scholar（通过代理）

#### 7.4 相关文件

- `backend/agents/searcher_agent.py`（增强）
- `backend/search/search_engine.py`（新增）
- `frontend/src/components/SearchProgress.jsx`（新增）

---

### 8. 步骤路由

#### 8.1 概述

v8.0 支持按阶段路由到不同模型，优化成本与质量。

#### 8.2 默认路由

| 阶段 | 默认模型 | 选择理由 |
|------|----------|----------|
| 信息确权 | deepseek-r2 | 性价比高，支持缓存 |
| 创意生成 | claude-opus-4.5 | 创造力强 |
| 校验 | deepseek-r2 | 严格遵循规则 |
| 多粒度生成 | gpt-4.1 | 长文本质量高 |
| 深度辅助 | claude-opus-4.5 | 综合能力强 |

#### 8.3 相关文件

- `backend/config/model_routing.py`（新增）
- `backend/orchestrator/model_router.py`（新增）

---

### 9. 其他新增功能

#### 9.1 AI 痕迹检测

- 200+ 模板词列表
- 基于规则与统计的检测算法
- 置信度评分
- 误报处理机制

#### 9.2 SimHash/MinHash 重复度检测

- SimHash：快速近似相似度
- MinHash：大规模去重
- 余弦相似度：精确相似度
- 多算法组合，平衡速度与精度

#### 9.3 实验预研模板

- 标准模板（计算机科学）
- 医学影像模板
- 自定义模板支持

#### 9.4 答辩模拟

- 三种评委风格（友善/严谨/挑战）
- 可配置问题数量
- 实时评分与反馈

#### 9.5 Webhook 集成

- 论题生成完成通知
- 校验结果通知
- 预算阈值告警
- 支持 Slack / 钉钉 / 企业微信

#### 9.6 Prometheus 监控

- 请求计数
- 延迟直方图
- Token 使用量
- 成本统计
- 缓存命中率
- Grafana 仪表板模板

---

## 改进项

### 1. 模型列表更新

#### 1.1 新增模型

| 模型 | 提供商 | 用途 |
|------|--------|------|
| deepseek-r2 | DeepSeek | 默认模型（支持缓存） |
| claude-opus-4.5 | Anthropic | 创意生成/深度辅助 |
| gpt-4.1 | OpenAI | 多粒度生成 |
| glm-4-plus | 智谱 AI | 备选模型 |
| moonshot-v1-128k | 月之暗面 | 长上下文场景 |

#### 1.2 移除模型

| 模型 | 原因 |
|------|------|
| gpt-3.5-turbo | 性能不足，已由 gpt-4.1 替代 |
| text-davinci-003 | 已弃用 |
| claude-2 | 已由 claude-opus-4.5 替代 |

### 2. 会话管理重构

#### 2.1 数据模型优化

- 新增 `Conversation` 表，支持多对话
- `Message` 表增加 `conversation_id` 字段
- 新增 `LineageNode` / `LineageEdge` 表
- 新增 `BudgetLedger` 表
- 新增 `CacheEntry` 表

#### 2.2 API 优化

- 会话列表支持分页
- 支持按学位/学科过滤
- 支持批量操作
- 响应时间优化（索引优化）

### 3. 约束工程重写

#### 3.1 架构改进

- 硬约束与软约束分离
- 支持约束组合（AND/OR/PRIORITY）
- 支持条件约束
- 约束注册机制

#### 3.2 新增约束

- 关键词必须包含约束
- 时间可行性约束（基于复杂度评估）
- 社会价值评估维度（可选）

### 4. 前端 UI 优化

#### 4.1 视觉设计

- 全新配色方案（更专业的学术风格）
- 响应式布局（支持移动端）
- 暗色模式支持
- 字体优化（中英文混排）

#### 4.2 交互改进

- 流式输出动画
- 加载骨架屏
- 操作确认弹窗
- 快捷键支持（30+ 快捷键）
- 拖拽排序

#### 4.3 性能优化

- 虚拟滚动（大数据列表）
- 懒加载
- 代码分割
- 资源哈希（缓存优化）

### 5. API 文档改进

- 升级到 OpenAPI 3.1
- 新增交互式 API 测试
- 错误码完整文档
- 限流配额文档
- SDK 示例代码

### 6. 日志系统改进

- 结构化日志（JSON 格式）
- 日志分级（DEBUG/INFO/WARNING/ERROR）
- 日志轮转
- 敏感信息脱敏

### 7. 安全性改进

- API Key 加密存储
- CORS 配置化
- 速率限制中间件
- 审计日志
- CSRF 保护

### 8. 测试覆盖

- 单元测试覆盖率从 45% 提升到 78%
- 新增集成测试
- 新增端到端测试
- 新增性能基准测试

---

## 修复项

### v7.x 已知问题修复

#### 1. 严重问题

| 编号 | 问题 | 修复版本 |
|------|------|----------|
| #234 | 多用户并发时数据库锁定 | v8.0.0 |
| #235 | 长对话导致上下文溢出 | v8.0.0（DST 压缩） |
| #236 | 模型 API 超时无重试 | v8.0.0（降级策略） |
| #237 | 缓存 key 冲突 | v8.0.0（SHA-256 前缀） |

#### 2. 一般问题

| 编号 | 问题 | 修复版本 |
|------|------|----------|
| #201 | 前端图谱节点拖拽卡顿 | v8.0.0（D3.js 优化） |
| #202 | SSE 连接断开后不重连 | v8.0.0（自动重连） |
| #203 | 论题导出格式错误 | v8.0.0 |
| #204 | 预算统计不准确 | v8.0.0（透明账本） |
| #205 | 模型切换后上下文丢失 | v8.0.0（上下文持久化） |
| #206 | 搜索结果排序错误 | v8.0.0 |
| #207 | 暗色模式下文字不可读 | v8.0.0 |
| #208 | 移动端布局错乱 | v8.0.0（响应式重写） |

#### 3. 轻微问题

| 编号 | 问题 | 修复版本 |
|------|------|----------|
| #180 | 加载动画不流畅 | v8.0.0 |
| #181 | 输入框 placeholder 截断 | v8.0.0 |
| #182 | 日期格式不统一 | v8.0.0（ISO 8601） |
| #183 | 错误消息不友好 | v8.0.0（错误码体系） |
| #184 | 帮助文档链接失效 | v8.0.0 |
| #185 | 快捷键冲突 | v8.0.0 |

#### 4. 安全修复

| 编号 | 问题 | 修复版本 |
|------|------|----------|
| #301 | API Key 明文存储 | v8.0.0（Fernet 加密） |
| #302 | CORS 配置过于宽松 | v8.0.0（白名单） |
| #303 | 无速率限制 | v8.0.0（滑动窗口） |
| #304 | SQL 注入风险 | v8.0.0（参数化查询） |
| #305 | XSS 漏洞 | v8.0.0（输出转义） |

---

## 破坏性变更

### 1. API 变更

#### 1.1 移除的 API

| API | 替代方案 |
|-----|----------|
| `POST /api/generate` | `POST /api/sessions/{id}/ideate` |
| `GET /api/result` | `GET /api/sessions/{id}/proposals` |
| `POST /api/validate` | `POST /api/sessions/{id}/validate` |

#### 1.2 变更的 API

**会话创建：**

```http
# v7.x
POST /api/sessions
{
  "title": "...",
  "type": "..."
}

# v8.0
POST /api/sessions
{
  "name": "...",        # title → name
  "degree": "master",   # type → degree，值变更
  "discipline": "..."   # 新增字段
}
```

**论题生成：**

```http
# v7.x
POST /api/generate
{
  "session_id": "...",
  "prompt": "..."
}

# v8.0
POST /api/sessions/{session_id}/ideate
{
  "count": 10  # 生成数量
}
```

#### 1.3 新增的 API

| API | 用途 |
|-----|------|
| `POST /api/sessions/{id}/confirm` | 信息确权 |
| `POST /api/sessions/{id}/ideate` | 创意生成 |
| `POST /api/sessions/{id}/validate` | 校验 |
| `POST /api/sessions/{id}/generate` | 多粒度生成 |
| `GET /api/sessions/{id}/budget/summary` | 预算摘要 |
| `GET /api/sessions/{id}/lineage` | 谱系图谱 |
| `POST /api/sessions/{id}/conversations` | 创建对话 |
| `GET /api/models/health` | 模型健康检查 |
| `GET /api/webhooks` | Webhook 管理 |

### 2. 数据库 Schema 变更

#### 2.1 新增表

```sql
-- 对话表
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- 谱系节点表
CREATE TABLE lineage_nodes (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    node_type TEXT NOT NULL,
    label TEXT NOT NULL,
    properties JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 谱系边表
CREATE TABLE lineage_edges (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    edge_type TEXT NOT NULL,
    properties JSON,
    FOREIGN KEY (source_id) REFERENCES lineage_nodes(id),
    FOREIGN KEY (target_id) REFERENCES lineage_nodes(id)
);

-- 预算账本表
CREATE TABLE budget_ledger (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    conversation_id TEXT,
    model TEXT NOT NULL,
    stage TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,
    cost_usd REAL NOT NULL,
    cache_hit BOOLEAN DEFAULT FALSE,
    agent_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 缓存条目表
CREATE TABLE cache_entries (
    id TEXT PRIMARY KEY,
    cache_key TEXT NOT NULL UNIQUE,
    value TEXT NOT NULL,
    session_id TEXT,
    conversation_id TEXT,
    hit_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);
```

#### 2.2 修改的表

```sql
-- sessions 表新增字段
ALTER TABLE sessions ADD COLUMN degree TEXT;
ALTER TABLE sessions ADD COLUMN discipline TEXT;
ALTER TABLE sessions ADD COLUMN status TEXT DEFAULT 'active';

-- messages 表新增字段
ALTER TABLE messages ADD COLUMN conversation_id TEXT;
ALTER TABLE messages ADD COLUMN stage TEXT;
ALTER TABLE messages ADD COLUMN agent_name TEXT;
```

#### 2.3 移除的表

| 表 | 原因 |
|----|------|
| `old_generations` | 已由 `proposals` 替代 |
| `legacy_cache` | 已由 `cache_entries` 替代 |

### 3. 配置项变更

#### 3.1 移除的配置项

| 配置项 | 替代 |
|--------|------|
| `MODEL_NAME` | `MODEL_ROUTING`（多模型路由） |
| `CACHE_PREFIX` | 自动计算（SHA-256） |
| `MAX_HISTORY` | `DST_MAX_RECENT_TURNS` |

#### 3.2 变更的配置项

```env
# v7.x
MODEL_NAME=deepseek-r2
API_KEY=sk-xxx
CACHE_PREFIX=thesisminer

# v8.0
DEEPSEEK_API_KEY=sk-xxx
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx
# 缓存前缀自动计算，无需配置
```

#### 3.3 新增的配置项

```env
# 模型路由
MODEL_ROUTING={"information_confirmation":"deepseek-r2",...}

# 缓存
CACHE_ENABLED=true
CACHE_TTL_SECONDS=3600
CACHE_MAX_SIZE=1000

# DST 压缩
DST_MAX_RECENT_TURNS=3
DST_MAX_SUMMARY_TOKENS=500
DST_COMPRESSION_THRESHOLD=10

# 限流
RATE_LIMIT_ENABLED=true
RATE_LIMIT_RPM=60
RATE_LIMIT_BURST=10

# 安全
ENCRYPTION_KEY=your-encryption-key
CORS_ORIGINS=http://localhost:3000
```

### 4. 前端组件变更

#### 4.1 移除的组件

| 组件 | 替代 |
|------|------|
| `GenerationForm` | `InformationConfirmation` + `IdeationPanel` |
| `ResultDisplay` | `ProposalList` + `ProposalDetail` |
| `SimpleGraph` | `LineageGraph`（D3.js） |

#### 4.2 重命名的组件

| 旧名称 | 新名称 |
|--------|--------|
| `SessionList` | `SessionSidebar` |
| `ChatWindow` | `ConversationPanel` |
| `SettingsPage` | `AdminPanel` |

---

## 迁移指南

### 1. v7 → v8 数据迁移

#### 1.1 自动迁移

```bash
# 1. 备份 v7 数据
$ cp thesisminer.db thesisminer_v7_backup.db

# 2. 启动 v8（自动执行迁移）
$ python -m backend.main
INFO:backend.database:检测到 v7 数据库，开始迁移...
INFO:backend.database:已创建新表：conversations, lineage_nodes, ...
INFO:backend.database:已迁移 156 个会话
INFO:backend.database:已迁移 2,341 条消息
INFO:backend.database:迁移完成

# 3. 验证迁移
$ python -m backend.database verify
✓ 会话数：156（原 156）
✓ 消息数：2,341（原 2,341）
✓ 数据完整性验证通过
```

#### 1.2 手动迁移

如自动迁移失败，可手动执行：

```bash
# 1. 导出 v7 数据
$ python -m backend.migration.export_v7 --output v7_data.json

# 2. 初始化 v8 数据库
$ python -m backend.database init

# 3. 导入数据
$ python -m backend.migration.import_v8 --input v7_data.json

# 4. 验证
$ python -m backend.database verify
```

#### 1.3 数据映射

| v7 表 | v8 表 | 映射说明 |
|-------|-------|----------|
| `sessions.title` | `sessions.name` | 字段重命名 |
| `sessions.type` | `sessions.degree` | 字段重命名，值映射（"1"→"master"） |
| `messages` | `messages` | 新增 conversation_id（默认创建主对话） |
| `old_generations` | `proposals` | 结构转换 |

### 2. 配置迁移

#### 2.1 环境变量迁移

```bash
# 使用迁移工具
$ python -m backend.migration.config --input .env.v7 --output .env

# 或手动更新
$ cp .env.example .env
$ vim .env  # 填入新的配置项
```

#### 2.2 配置映射

| v7 配置 | v8 配置 | 说明 |
|---------|---------|------|
| `MODEL_NAME=deepseek-r2` | `DEEPSEEK_API_KEY=sk-xxx` | 拆分为多模型 |
| `API_KEY=sk-xxx` | `DEEPSEEK_API_KEY=sk-xxx` | 重命名 |
| `CACHE_PREFIX=tm` | （移除） | 自动计算 |
| `MAX_HISTORY=20` | `DST_MAX_RECENT_TURNS=3` | 语义变更 |

### 3. API 迁移

#### 3.1 客户端代码迁移

```python
# v7.x 代码
import requests

response = requests.post("http://localhost:8000/api/generate", json={
    "session_id": "sess_123",
    "prompt": "生成计算机视觉论题"
})
result = response.json()

# v8.0 代码
import httpx

async with httpx.AsyncClient() as client:
    # 1. 信息确权
    await client.post(f"http://localhost:8000/api/sessions/sess_123/confirm", json={
        "research_direction": "computer_vision",
        "interests": ["image_classification"],
        "advisor": {"name": "张教授"},
        "constraints": {"duration_months": 12}
    })

    # 2. 创意生成
    response = await client.post(
        f"http://localhost:8000/api/sessions/sess_123/ideate",
        json={"count": 10}
    )
    ideas = response.json()
```

#### 3.2 Webhook 迁移

```python
# v7.x Webhook 事件
{
    "event": "generation_complete",
    "data": {"result": "..."}
}

# v8.0 Webhook 事件
{
    "event": "proposal.generated",
    "data": {
        "session_id": "...",
        "proposal_id": "...",
        "title": "...",
        "score": 85
    }
}
```

### 4. 前端迁移

#### 4.1 组件迁移

```javascript
// v7.x
import GenerationForm from './components/GenerationForm';
import ResultDisplay from './components/ResultDisplay';

// v8.0
import InformationConfirmation from './components/InformationConfirmation';
import IdeationPanel from './components/IdeationPanel';
import ProposalList from './components/ProposalList';
import ProposalDetail from './components/ProposalDetail';
```

#### 4.2 API 调用迁移

```javascript
// v7.x
const result = await api.post('/api/generate', { prompt: '...' });

// v8.0
await api.post(`/api/sessions/${sessionId}/confirm`, { ... });
const ideas = await api.post(`/api/sessions/${sessionId}/ideate`, { count: 10 });
```

---

## 已知问题

### v8.0 已知问题

| 编号 | 问题 | 严重程度 | 状态 | 临时解决方案 |
|------|------|----------|------|--------------|
| #401 | 大规模谱系图谱（>500 节点）渲染慢 | 中 | 修复中 | 减少节点数量 |
| #402 | DST 压缩偶尔丢失关键信息 | 低 | 调查中 | 增大 max_recent_turns |
| #403 | Safari 浏览器 SSE 偶尔断开 | 低 | 修复中 | 使用 Chrome |
| #404 | 多对话切换时缓存命中率短暂下降 | 低 | 预期行为 | 无需处理 |

### 计划在 v8.1 修复

- 谱系图谱虚拟化渲染
- DST 压缩算法优化
- Safari 兼容性改进
- 更多检索源支持

---

## 性能对比

### v7.5 vs v8.0

| 指标 | v7.5 | v8.0 | 改进 |
|------|------|------|------|
| 平均响应时间 | 3.2s | 2.1s | -34% |
| 缓存命中率 | 0% | 68.5% | +68.5% |
| API 成本（日均） | $15.20 | $4.80 | -68% |
| 并发支持 | 50 | 200 | +300% |
| 内存使用 | 512MB | 380MB | -26% |
| 数据库查询延迟 | 45ms | 12ms | -73% |
| 前端首屏加载 | 2.8s | 1.2s | -57% |

---

## 统计信息

### 代码统计

| 项目 | v7.5 | v8.0 | 变化 |
|------|------|------|------|
| Python 代码行数 | 12,340 | 18,560 | +50% |
| JavaScript 代码行数 | 8,200 | 12,800 | +56% |
| 测试代码行数 | 3,100 | 6,200 | +100% |
| 文档行数 | 2,500 | 8,900 | +256% |
| 总文件数 | 89 | 142 | +60% |

### 测试统计

| 项目 | v7.5 | v8.0 |
|------|------|------|
| 单元测试数 | 234 | 456 |
| 集成测试数 | 45 | 89 |
| 端到端测试数 | 12 | 28 |
| 测试覆盖率 | 45% | 78% |

---

## 升级建议

### 推荐升级路径

1. **v7.0-v7.4 → v7.5**：先升级到 v7.5
2. **v7.5 → v8.0**：直接升级

### 升级前检查

- [ ] 备份当前数据库
- [ ] 备份当前配置文件
- [ ] 检查 API Key 是否有效
- [ ] 确认服务器满足 v8.0 系统要求
- [ ] 通知用户计划停机时间

### 升级步骤

```bash
# 1. 停止服务
$ sudo systemctl stop thesisminer

# 2. 备份
$ cp thesisminer.db thesisminer_v7_backup.db
$ cp .env .env.v7_backup

# 3. 拉取 v8.0 代码
$ git fetch origin
$ git checkout v8.0.0

# 4. 更新依赖
$ source .venv/bin/activate
$ pip install -r requirements.txt --upgrade

# 5. 迁移配置
$ python -m backend.migration.config --input .env.v7_backup --output .env

# 6. 启动服务（自动迁移数据库）
$ python -m backend.main

# 7. 验证
$ curl http://localhost:8000/api/health

# 8. 设置开机自启
$ sudo systemctl enable thesisminer
$ sudo systemctl start thesisminer
```

---

## 致谢

感谢以下贡献者参与 v8.0 的开发：

- 核心开发团队
- 测试团队
- 文档团队
- 社区贡献者（通过 Issue 和 PR 提供反馈）

特别感谢 DeepSeek 团队提供的缓存优化建议。

---

## 附录：版本时间线

| 日期 | 事件 |
|------|------|
| 2026-01-15 | v8.0 开发启动 |
| 2026-02-28 | 多 Agent 架构设计完成 |
| 2026-03-15 | Alpha 版本（内部测试） |
| 2026-04-20 | Beta 版本（社区测试） |
| 2026-05-10 | RC 版本（发布候选） |
| 2026-05-25 | RC2 版本（修复反馈） |
| 2026-06-01 | 代码冻结 |
| 2026-06-10 | 最终测试 |
| 2026-06-15 | v8.0.0 正式发布 |

---

## 附录 A：详细功能对比

### A.1 Agent 架构对比

| 特性 | v7.5 | v8.0 |
|------|------|------|
| Agent 数量 | 1（单一引擎） | 4（Reasoner/Mentor/Searcher/Critic） |
| Agent 通信 | 无 | 通过编排器 |
| 上下文隔离 | 无 | 每个 Agent 独立上下文 |
| 自定义 Agent | 不支持 | 支持（继承 BaseAgent） |
| Agent 注册 | 硬编码 | 动态注册（AGENT_REGISTRY） |
| 流式输出 | 部分支持 | 全部支持 |
| 错误处理 | 基础 | 重试 + 降级 + 优雅退出 |

### A.2 缓存机制对比

| 特性 | v7.5 | v8.0 |
|------|------|------|
| 缓存类型 | 简单内存缓存 | SHA-256 前缀哈希缓存 |
| 缓存命中率 | 0% | 68.5% |
| 缓存粒度 | 整个响应 | Prompt 前缀 |
| 缓存失效 | TTL | TTL + 主动失效 |
| 会话隔离 | 无 | 按 session/conversation 隔离 |
| 监控 | 无 | 命中率监控 + 诊断 |

### A.3 谱系图谱对比

| 特性 | v7.5 | v8.0 |
|------|------|------|
| 图谱库 | 无 | D3.js v7 |
| 节点类型 | 无 | 6 种（导师/前辈/论题/文献/项目/当前） |
| 边类型 | 无 | 4 种（师生/继承/引用/关联） |
| 布局算法 | 无 | 4 种（力导向/树形/径向/聚类） |
| 交互 | 无 | 拖拽/缩放/过滤/详情/批量 |
| 导出 | 无 | SVG/PNG/PDF/JSON |

### A.4 预算监控对比

| 特性 | v7.5 | v8.0 |
|------|------|------|
| 成本记录 | 粗略 | 透明账本（每条 API 调用） |
| 统计维度 | 总成本 | 按模型/阶段/会话/对话 |
| 缓存统计 | 无 | 命中率/节省 Token/节省成本 |
| 告警 | 无 | 多维度告警规则 |
| 导出 | 无 | CSV/JSON/Excel |
| 配额管理 | 无 | 全局/用户/模型配额 |

---

## 附录 B：依赖更新

### B.1 Python 依赖

| 包 | v7.5 版本 | v8.0 版本 | 变更说明 |
|----|-----------|-----------|----------|
| fastapi | 0.95.0 | 0.104.1 | 升级 |
| uvicorn | 0.22.0 | 0.24.0 | 升级 |
| pydantic | 1.10.0 | 2.5.0 | **重大升级**（v1→v2） |
| httpx | 0.24.0 | 0.25.2 | 升级 |
| sse-starlette | 1.6.0 | 1.8.2 | 升级 |
| simhash | - | 2.1.2 | **新增** |
| datasketch | - | 1.6.4 | **新增** |
| tiktoken | - | 0.5.2 | **新增** |
| cryptography | - | 41.0.7 | **新增**（API Key 加密） |
| prometheus-client | - | 0.19.0 | **新增**（监控） |

### B.2 JavaScript 依赖

| 包 | v7.5 版本 | v8.0 版本 | 变更说明 |
|----|-----------|-----------|----------|
| react | 17.0.2 | 18.2.0 | 升级 |
| react-dom | 17.0.2 | 18.2.0 | 升级 |
| d3 | - | 7.8.5 | **新增**（谱系图谱） |
| vite | 4.3.0 | 5.0.0 | 升级 |
| tailwindcss | 3.3.0 | 3.4.0 | 升级 |

### B.3 开发依赖

| 包 | v7.5 版本 | v8.0 版本 | 变更说明 |
|----|-----------|-----------|----------|
| pytest | 7.3.0 | 7.4.3 | 升级 |
| pytest-asyncio | 0.21.0 | 0.21.1 | 升级 |
| black | 23.3.0 | 23.11.0 | 升级 |
| ruff | 0.0.270 | 0.1.6 | 升级 |
| mypy | 1.3.0 | 1.7.0 | 升级 |

---

## 附录 C：数据库迁移脚本

### C.1 迁移脚本 v7_to_v8.py

```python
# backend/migration/v7_to_v8.py

"""v7 到 v8 的数据库迁移脚本"""

import sqlite3
from datetime import datetime

def migrate(db_path: str):
    """执行迁移"""
    conn = sqlite3.connect(db_path)

    print("[Migration] 开始 v7 → v8 迁移...")

    # 1. 创建新表
    _create_new_tables(conn)
    print("[Migration] ✓ 已创建新表")

    # 2. 迁移 sessions 数据
    _migrate_sessions(conn)
    print("[Migration] ✓ 已迁移 sessions")

    # 3. 迁移 messages 数据
    _migrate_messages(conn)
    print("[Migration] ✓ 已迁移 messages")

    # 4. 创建默认对话
    _create_default_conversations(conn)
    print("[Migration] ✓ 已创建默认对话")

    # 5. 迁移生成记录
    _migrate_generations(conn)
    print("[Migration] ✓ 已迁移生成记录")

    # 6. 创建索引
    _create_indexes(conn)
    print("[Migration] ✓ 已创建索引")

    conn.commit()
    conn.close()

    print("[Migration] 迁移完成！")

def _create_new_tables(conn):
    """创建 v8 新表"""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_deleted BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );

        CREATE TABLE IF NOT EXISTS lineage_nodes (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            node_type TEXT NOT NULL,
            label TEXT NOT NULL,
            properties JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS lineage_edges (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            edge_type TEXT NOT NULL,
            properties JSON
        );

        CREATE TABLE IF NOT EXISTS budget_ledger (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            conversation_id TEXT,
            model TEXT NOT NULL,
            stage TEXT NOT NULL,
            input_tokens INTEGER NOT NULL,
            output_tokens INTEGER NOT NULL,
            total_tokens INTEGER NOT NULL,
            cost_usd REAL NOT NULL,
            cache_hit BOOLEAN DEFAULT FALSE,
            agent_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS cache_entries (
            id TEXT PRIMARY KEY,
            cache_key TEXT NOT NULL UNIQUE,
            value TEXT NOT NULL,
            session_id TEXT,
            conversation_id TEXT,
            hit_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP
        );
    """)

def _migrate_sessions(conn):
    """迁移 sessions 表"""
    # 添加新字段
    try:
        conn.execute("ALTER TABLE sessions ADD COLUMN degree TEXT")
    except:
        pass
    try:
        conn.execute("ALTER TABLE sessions ADD COLUMN discipline TEXT")
    except:
        pass
    try:
        conn.execute("ALTER TABLE sessions ADD COLUMN status TEXT DEFAULT 'active'")
    except:
        pass

    # 数据映射：type → degree
    type_mapping = {"1": "bachelor", "2": "master", "3": "doctor"}
    for old_type, new_degree in type_mapping.items():
        conn.execute(
            "UPDATE sessions SET degree = ? WHERE type = ?",
            (new_degree, old_type)
        )

def _migrate_messages(conn):
    """迁移 messages 表"""
    try:
        conn.execute("ALTER TABLE messages ADD COLUMN conversation_id TEXT")
    except:
        pass
    try:
        conn.execute("ALTER TABLE messages ADD COLUMN stage TEXT")
    except:
        pass
    try:
        conn.execute("ALTER TABLE messages ADD COLUMN agent_name TEXT")
    except:
        pass

def _create_default_conversations(conn):
    """为每个 session 创建默认对话"""
    cursor = conn.execute("SELECT id, name FROM sessions")
    sessions = cursor.fetchall()

    for session_id, session_name in sessions:
        conv_id = f"conv_default_{session_id}"
        conn.execute(
            "INSERT OR IGNORE INTO conversations (id, session_id, name) VALUES (?, ?, ?)",
            (conv_id, session_id, f"{session_name} - 主对话")
        )
        # 关联 messages 到默认对话
        conn.execute(
            "UPDATE messages SET conversation_id = ? WHERE session_id = ? AND conversation_id IS NULL",
            (conv_id, session_id)
        )

def _migrate_generations(conn):
    """迁移生成记录到 proposals 表"""
    # 创建 proposals 表（如不存在）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS proposals (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            conversation_id TEXT,
            title TEXT NOT NULL,
            abstract TEXT,
            outline TEXT,
            full_text TEXT,
            score INTEGER,
            source TEXT,
            status TEXT DEFAULT 'generated',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 迁移数据
    try:
        cursor = conn.execute("SELECT * FROM old_generations")
        for row in cursor.fetchall():
            conn.execute(
                """INSERT OR IGNORE INTO proposals
                   (id, session_id, title, abstract, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (row[0], row[1], row[2], row[3], row[4])
            )
    except:
        pass  # old_generations 表可能不存在

def _create_indexes(conn):
    """创建索引"""
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_sessions_user_created ON sessions(user_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_messages_session_created ON messages(session_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
        CREATE INDEX IF NOT EXISTS idx_budget_session_created ON budget_ledger(session_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_cache_key ON cache_entries(cache_key);
        CREATE INDEX IF NOT EXISTS idx_lineage_nodes_session ON lineage_nodes(session_id);
    """)

if __name__ == "__main__":
    import sys
    db_path = sys.argv[1] if len(sys.argv) > 1 else "thesisminer.db"
    migrate(db_path)
```

---

## 附录 D：回滚方案

如需从 v8.0 回滚到 v7.5：

```bash
# 1. 停止 v8.0 服务
$ sudo systemctl stop thesisminer

# 2. 恢复 v7.5 数据库
$ cp thesisminer_v7_backup.db thesisminer.db

# 3. 恢复 v7.5 配置
$ cp .env.v7_backup .env

# 4. 切换到 v7.5 代码
$ git checkout v7.5.3

# 5. 恢复 v7.5 依赖
$ pip install -r requirements.txt

# 6. 启动 v7.5 服务
$ sudo systemctl start thesisminer
```

> ⚠️ 回滚会丢失 v8.0 期间产生的所有数据（对话、谱系、预算记录等）。

---

> 本变更日志最后更新：2026-06-15
> 下次更新预计：v8.1.0（2026-08-15）
