# ThesisMiner v8.0 贡献指南

> 版本：v8.0 | 更新日期：2026-06-19 | 适用范围：所有内部与外部贡献者

感谢您关注 ThesisMiner 项目！本文档规范了参与本项目开发的所有流程，包括环境搭建、分支策略、提交规范、代码审查与发布流程。请在提交任何代码前完整阅读本指南。

---

## 目录

1. [项目概览](#1-项目概览)
2. [开发环境搭建](#2-开发环境搭建)
3. [分支策略与工作流](#3-分支策略与工作流)
4. [提交规范](#4-提交规范)
5. [代码风格与质量要求](#5-代码风格与质量要求)
6. [Pull Request 流程](#6-pull-request-流程)
7. [代码审查标准](#7-代码审查标准)
8. [Issue 与 Bug 报告](#8-issue-与-bug-报告)
9. [文档贡献](#9-文档贡献)
10. [发布流程](#10-发布流程)
11. [社区行为准则](#11-社区行为准则)

---

## 1. 项目概览

ThesisMiner 是一个基于多 Agent 架构的研究生开题全生命周期导航系统，v8.0 版本采用 Claude Code 式主管理 Agent + 子 Agent 协作架构，覆盖信息确权、谱系解析、重复度评估、多粒度生成、深度辅助五阶段闭环导航流。

### 技术栈

- **后端**：Python 3.11+、FastAPI、SQLite（生产可切换 PostgreSQL）
- **前端**：原生 JavaScript + D3.js v7（谱系图谱）、Tailwind CSS
- **AI 集成**：多模型代理（claude-sonnet-4.5、deepseek-r2、gpt-4.1 等 10 个模型）
- **测试**：pytest（后端）、Playwright（前端 E2E）
- **部署**：Docker + docker-compose

### 项目结构

```
ThesisMiner/
├── backend/           # 后端服务
│   ├── agents/        # 多 Agent 实现（orchestrator + 5 子 Agent）
│   ├── ai/            # AI 代理层（多模型路由、缓存优化、引用解析）
│   ├── constraints/   # 代码约束工程（五阶段门禁、硬约束、新颖性、风格）
│   ├── orchestration/ # 编排状态机
│   ├── sessions/      # 会话/对话管理
│   ├── routes/        # API 路由
│   └── config.py      # 全局配置与模型注册表
├── frontend/          # 前端资源
│   └── scripts/pages/ # 页面脚本（sessions、generate、lineage）
├── config/            # 配置文件
│   ├── agents/        # 各 Agent 的 YAML 配置
│   └── constraints/   # 约束规则 YAML 配置
├── docs/              # 项目文档
│   ├── architecture/  # 架构设计文档
│   ├── constraints/   # 约束工程文档与 Prompt 模板
│   ├── api/           # API 文档
│   └── development/   # 开发文档（本文档所在目录）
└── tests/             # 测试套件
    ├── unit/          # 单元测试
    ├── integration/   # 集成测试
    ├── e2e/           # 端到端测试
    ├── fixtures/      # 测试数据
    └── load/          # 压力测试
```

---

## 2. 开发环境搭建

### 前置依赖

- Python 3.11 或更高版本
- Node.js 18+（仅前端构建与 Playwright 需要）
- Git 2.30+
- Docker 24+（可选，用于容器化部署）

### 本地启动步骤

1. **克隆仓库**

   ```bash
   git clone https://github.com/your-org/ThesisMiner.git
   cd ThesisMiner
   ```

2. **创建 Python 虚拟环境**

   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # Linux/macOS
   source .venv/bin/activate
   ```

3. **安装后端依赖**

   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # 测试与开发工具
   ```

4. **配置环境变量**

   在项目根目录创建 `.env` 文件，填入各 AI 模型的 API Key：

   ```env
   DEEPSEEK_API_KEY=sk-xxx
   OPENAI_API_KEY=sk-xxx
   ANTHROPIC_API_KEY=sk-ant-xxx
   # 其他模型 Key 按需配置
   ```

5. **初始化数据库**

   ```bash
   python -c "from backend.database import init_db; init_db()"
   ```

6. **启动开发服务器**

   ```bash
   python main.py
   ```

   服务默认运行在 `http://localhost:8000`。

7. **验证启动**

   访问 `http://localhost:8000/api/health`，返回 `{"status": "ok", "version": "8.0.0"}` 即表示启动成功。

### 前端开发

前端为纯静态资源，无需单独构建。开发时直接由后端 FastAPI 托管 `frontend/` 目录。如需修改前端，编辑 `frontend/scripts/pages/` 下的 JS 文件后刷新浏览器即可。

---

## 3. 分支策略与工作流

本项目采用简化的 Git Flow 模型。

### 分支命名

| 分支 | 用途 | 命名规范 |
|------|------|----------|
| `main` | 生产稳定分支，受保护 | 固定 |
| `develop` | 开发集成分支 | 固定 |
| `feature/*` | 新功能开发 | `feature/<简短描述>`，如 `feature/multi-conversation` |
| `fix/*` | Bug 修复 | `fix/<issue-id>-<简述>`，如 `fix/123-cache-miss` |
| `docs/*` | 文档更新 | `docs/<简述>`，如 `docs/api-reference` |
| `release/*` | 发布准备 | `release/v<版本号>`，如 `release/v8.1.0` |

### 工作流

1. 从 `develop` 分支拉取最新代码
2. 创建功能分支：`git checkout -b feature/your-feature develop`
3. 开发并提交（遵循提交规范）
4. 推送分支并创建 Pull Request 到 `develop`
5. 通过代码审查后合并
6. 定期将 `develop` 合并到 `main` 进行发布

### 同步上游

开发期间定期同步 `develop` 以避免冲突：

```bash
git fetch origin
git rebase origin/develop
```

---

## 4. 提交规范

本项目遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范。

### 提交消息格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

### 类型（type）

| 类型 | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `docs` | 文档变更 |
| `style` | 代码格式（不影响功能） |
| `refactor` | 重构（非新功能、非修复） |
| `perf` | 性能优化 |
| `test` | 测试相关 |
| `chore` | 构建/工具/依赖变更 |
| `ci` | CI 配置变更 |

### 作用域（scope）

常用作用域：`agents`、`ai`、`constraints`、`sessions`、`orchestration`、`routes`、`frontend`、`config`、`docs`。

### 示例

```
feat(agents): 新增 CriticAgent 新颖性评估能力

实现四维创意评分（学科交叉/方法迁移/痛点突破/趋势前瞻），
与 novelty_checker 联动，评分 < 60 触发回退到创意阶段。

Closes #142
```

### 注意事项

- Subject 行不超过 50 个字符，使用祈使句（如"新增"而非"新增了"）
- Body 解释"为什么"而非"做了什么"（代码本身说明做了什么）
- 一个提交只做一件事，避免混合多个不相关变更
- 不要在提交中包含调试代码、注释掉的代码或 `console.log`

---

## 5. 代码风格与质量要求

### Python 代码

- 遵循 PEP 8，使用 `ruff` 进行 lint
- 行宽上限 100 字符
- 使用类型注解（Type Hints）
- 函数与类必须有 docstring（中文）
- 模块顶部注释说明用途与适用范围

```python
async def orchestrate(
    user_input: str,
    conversation_id: str
) -> AsyncGenerator[str, None]:
    """按五阶段顺序编排子 Agent，流式返回各阶段产出。

    Args:
        user_input: 用户输入文本
        conversation_id: 对话 ID，用于上下文隔离

    Yields:
        各阶段的流式输出片段
    """
    ...
```

### JavaScript 代码

- 使用 ES2020+ 语法
- 4 空格缩进
- 函数名使用 camelCase，常量使用 UPPER_SNAKE_CASE
- 避免全局变量污染，使用模块化封装

### YAML 配置

- 缩进 2 空格
- 每个配置文件顶部包含版本、日期、适用范围注释
- 字段名使用 snake_case
- 复杂字段添加行内注释说明

### 质量门禁

提交前必须通过以下检查：

```bash
# Python lint
ruff check backend/ tests/

# Python 类型检查
mypy backend/

# 运行测试
pytest tests/ -v --cov=backend --cov-report=term-missing
```

测试覆盖率要求：新增代码覆盖率不低于 80%，关键模块（agents、constraints、orchestration）不低于 90%。

---

## 6. Pull Request 流程

### 创建 PR

1. 确保本地测试全部通过
2. PR 标题遵循提交规范（如 `feat(agents): 新增 CriticAgent`）
3. PR 描述包含：
   - 变更摘要（做了什么、为什么）
   - 关联 Issue（如 `Closes #123`）
   - 测试方式（如何验证本次变更）
   - 截图/录屏（前端变更必须提供）
4. 至少指定一名审查人

### PR 模板

```markdown
## 变更摘要
<!-- 简述本次变更内容与目的 -->

## 关联 Issue
Closes #

## 变更类型
- [ ] 新功能
- [ ] Bug 修复
- [ ] 重构
- [ ] 文档
- [ ] 性能优化

## 测试方式
<!-- 描述如何验证本次变更 -->

## 检查清单
- [ ] 本地测试通过
- [ ] 新增代码有对应测试
- [ ] 文档已更新（如涉及）
- [ ] 无硬编码的密钥或敏感信息
```

### 合并规则

- 至少一名审查人 Approve
- CI 流水线全部通过
- 无未解决的讨论
- 使用 Squash Merge 保持提交历史整洁

---

## 7. 代码审查标准

审查人应关注以下维度：

### 功能正确性
- 是否正确实现了需求
- 边界条件是否处理
- 异常路径是否覆盖

### 架构一致性
- 是否遵循多 Agent 架构分层（Orchestrator 不直接操作数据库，子 Agent 不互相调用）
- 是否遵循上下文隔离原则（子 Agent 上下文不混入其他 Agent 历史）
- 是否遵循三段式 Prompt 固化（DeepSeek 缓存前缀不可变）

### 安全性
- 无 SQL 注入风险（使用参数化查询）
- 无 XSS 风险（前端输出转义）
- API Key 等敏感信息不硬编码、不记日志
- 用户输入有长度与内容校验

### 性能
- 数据库查询避免 N+1 问题
- AI 调用有超时与重试机制
- 大列表有分页
- 前端重计算有防抖/节流

### 可维护性
- 命名清晰、无歧义缩写
- 单一职责，函数不过长（<80 行）
- 复杂逻辑有注释说明"为什么"

---

## 8. Issue 与 Bug 报告

### 提交 Issue

使用 GitHub Issue 模板，包含：

- **环境信息**：操作系统、Python 版本、ThesisMiner 版本
- **复现步骤**：逐步操作描述
- **预期行为**：应当发生什么
- **实际行为**：实际发生了什么
- **日志/截图**：错误日志与界面截图

### Issue 标签

| 标签 | 说明 |
|------|------|
| `bug` | 功能缺陷 |
| `feature` | 新功能请求 |
| `enhancement` | 现有功能增强 |
| `documentation` | 文档问题 |
| `performance` | 性能问题 |
| `security` | 安全漏洞（请勿公开提交，邮件联系维护者） |
| `good first issue` | 适合新贡献者的入门任务 |

### Bug 优先级

- **P0 严重**：服务崩溃、数据丢失、安全漏洞 → 24 小时内响应
- **P1 高**：核心功能不可用 → 3 天内响应
- **P2 中**：非核心功能异常 → 1 周内响应
- **P3 低**：体验问题、小缺陷 → 按版本规划处理

---

## 9. 文档贡献

文档与代码同等重要。文档变更遵循与代码相同的 PR 流程。

### 文档类型

- `docs/architecture/`：架构设计文档，重大架构决策需更新
- `docs/constraints/`：约束工程文档与 Prompt 模板
- `docs/api/`：API 文档，接口变更必须同步更新
- `docs/development/`：开发文档（本文档、测试指南、部署指南）
- `README.md`：项目入门说明

### 文档规范

- 全部使用中文撰写（代码示例与 YAML 语法除外）
- Markdown 格式，标题层级清晰
- 包含目录与交叉链接
- 代码示例必须可运行
- 截图存放在 `docs/assets/` 目录

---

## 10. 发布流程

### 版本号

遵循语义化版本（SemVer）：`MAJOR.MINOR.PATCH`

- MAJOR：不兼容的 API 变更
- MINOR：向后兼容的新功能
- PATCH：向后兼容的 Bug 修复

### 发布步骤

1. 从 `develop` 创建 `release/v<版本号>` 分支
2. 更新版本号（`main.py`、`backend/config.py`、`README.md`）
3. 更新 `CHANGELOG.md`
4. 运行完整测试套件，确保 100% 通过
5. 合并 `release/*` 到 `main` 并打 Tag
6. 合并 `main` 回 `develop`
7. 触发 CI 构建镜像并发布

### CHANGELOG 格式

```markdown
## [8.1.0] - 2026-07-15

### 新增
- 新增 CriticAgent 新颖性评估能力
- 新增 GET /api/cache-stats 缓存命中率端点

### 修复
- 修复多对话切换时上下文未完全隔离的问题

### 变更
- DeepSeek 缓存前缀策略调整，命中率提升至 97%
```

---

## 11. 社区行为准则

我们致力于营造一个开放、友好、包容的开发社区。所有贡献者应遵守以下准则：

- **保持尊重**：尊重不同背景、不同水平的贡献者
- **建设性沟通**：批评针对代码而非个人，提供改进建议
- **耐心指导**：对新贡献者给予帮助与引导
- **聚焦问题**：讨论围绕技术问题本身，避免偏离主题
- **承认错误**：犯错时坦诚承认并及时修正

不当行为（骚扰、人身攻击、歧视性言论）将被零容忍处理，维护团队有权移除违规者的贡献资格。

---

如有任何疑问，请通过 GitHub Issue 或邮件联系维护团队。再次感谢您对 ThesisMiner 的贡献！
