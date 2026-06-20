# ThesisMiner v8.0 变更日志

> 记录 ThesisMiner v8.0 项目的所有重要变更。

## [8.0.0] - 2026-06-19

### 新增

#### 多 Agent 架构
- 新增 Orchestrator 主管理 Agent
- 新增 Searcher 检索 Agent
- 新增 Reasoner 创意 Agent
- 新增 Critic 评审 Agent
- 新增 Mentor 导师 Agent
- 新增 Writer 写作 Agent
- 新增 BaseAgent 抽象基类与 Agent 注册表

#### 五阶段闭环导航流
- 新增信息确权阶段（强制联网检索）
- 新增创意阶段（四维创意引擎）
- 新增校验阶段（新颖性评分）
- 新增生成阶段（多粒度输出）
- 新增深度辅助阶段（文献精读/实验预研/答辩模拟）
- 新增阶段门禁系统

#### DeepSeek 缓存优化
- 新增三段式 Prompt 架构（prefix/dynamic）
- 新增缓存命中率监控
- 缓存命中率 ≥95%
- 新增 `GET /api/cache-stats` 端点

#### 多对话管理
- 新增 conversations 表
- 新增 conversation_messages 表
- 新增 search_citations 表
- 支持多对话并存与上下文隔离
- 新增 DST 压缩算法

#### D3.js 谱系图谱
- 替换原 SVG 手绘为 D3.js v7 力导向图
- 支持节点拖拽、画布缩放、悬停高亮
- 支持类型过滤、布局重置、全屏
- 节点点击弹出详情卡片

#### 联网搜索结果展示
- 新增 CitationParser 引用解析器
- 支持 URL/Markdown/编号引用解析
- 新增引用卡片组件
- 新增 `GET /api/messages/{mid}/citations` 端点

#### 2026 模型更新
- 移除老旧模型（gpt-4o-mini 等）
- 新增 gpt-4.1-mini, gpt-4.1
- 新增 deepseek-v3.2, deepseek-r2
- 新增 claude-sonnet-4.5, claude-opus-4.5
- 新增 qwen3-max, gemini-2.5-pro, glm-4.6, doubao-1.5-pro
- 每个模型新增 agent_default 与 release_year 字段

#### 代码约束工程
- 新增 stage_gate 阶段门禁
- 新增 hard_rules 硬约束
- 新增 novelty_checker 新颖性评估
- 新增 style_normalizer 去 AI 痕迹
- 新增 multi_granularity 多粒度生成
- 新增 deep_assist 深度辅助

#### 新增模块
- backend/analytics/（指标收集、性能监控、用量追踪）
- backend/ml/（文本处理、嵌入引擎、相似度评分）
- backend/export/（文档导出、报告生成、引用格式化）
- backend/knowledge/（知识库、学科分类、方法库）
- backend/validation/（论题验证、抄袭检测、质量评估）
- backend/routing/（模型路由）
- backend/integrity/（学术诚信、引用验证、数据认证）
- backend/optimization/（缓存优化、查询优化、资源管理）
- backend/nlp/（中文处理、学术解析、术语提取）
- backend/monitoring/（健康检查、告警管理、审计日志）
- backend/planning/（研究规划、时间线、里程碑）
- backend/reasoning/（逻辑推理、论证分析、假设检验）

#### 测试套件
- 新增 800+ 单元测试
- 新增集成测试（五阶段流程、多 Agent 协作）
- 新增 E2E 测试（谱系图谱、会话 UI、生成 UI）
- 新增负载测试（并发会话、消息量）
- 测试覆盖率 ≥85%

#### 文档
- 新增架构文档（agent_architecture、session_model、cache_strategy 等）
- 新增约束文档（hard_rules、novelty_scoring、style_normalizer_rules）
- 新增 API 文档（openapi.yaml、agent_api、conversation_api）
- 新增开发文档（contributing、testing_guide、deployment）
- 新增教程文档（getting_started、advanced_features、developer_guide）
- 新增参考文档（agent_reference、constraint_reference、api_reference）

### 变更

- 默认模型从 gpt-4o-mini 改为 deepseek-v3.2
- FastAPI 使用 lifespan 替代废弃的 on_event
- 数据库启用 WAL 模式与外键约束
- 前端引入 D3.js v7

### 移除

- 移除老旧模型（gpt-4o-mini, gpt-4o, deepseek-chat 等）
- 移除 v6/v7 兼容代码

## [7.0.0] - 2026-03

### 新增
- 创意引擎
- 透明预算账本
- 谱系图谱（SVG）
- 基础会话管理

## [6.0.0] - 2025-12

### 新增
- 基础论题生成
- 单 Agent 架构
- SQLite 数据库
- FastAPI 后端
