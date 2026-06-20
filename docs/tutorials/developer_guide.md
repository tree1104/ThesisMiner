# ThesisMiner v8.0 开发者指南

> 本指南面向 ThesisMiner v8.0 的核心开发者、贡献者与二次开发团队。文档系统性地覆盖了从开发环境搭建、项目结构理解、核心模块剖析、开发工作流、调试技巧、扩展开发、测试编写到部署运维的完整开发链路。无论你是首次接触本项目的工程师，还是希望深度定制系统的资深开发者，都能在本指南中找到所需的实践指引。
>
> **版本**：v8.0.0  
> **最后更新**：2026-06-20  
> **适用对象**：后端工程师、前端工程师、DevOps 工程师、AI 算法工程师

---

## 目录

- [第 1 章 项目总览](#第-1-章-项目总览)
- [第 2 章 开发环境搭建](#第-2-章-开发环境搭建)
- [第 3 章 项目结构详解](#第-3-章-项目结构详解)
- [第 4 章 核心模块详解](#第-4-章-核心模块详解)
- [第 5 章 开发工作流](#第-5-章-开发工作流)
- [第 6 章 调试技巧](#第-6-章-调试技巧)
- [第 7 章 扩展开发指南](#第-7-章-扩展开发指南)
- [第 8 章 测试编写指南](#第-8-章-测试编写指南)
- [第 9 章 部署指南](#第-9-章-部署指南)
- [第 10 章 常见问题排查](#第-10-章-常见问题排查)
- [第 11 章 最佳实践](#第-11-章-最佳实践)
- [第 12 章 完整代码示例集](#第-12-章-完整代码示例集)
- [附录](#附录)

---

# 第 1 章 项目总览

## 1.1 项目定位与愿景

ThesisMiner 是一个面向研究生（硕士/博士）开题全生命周期的智能辅助系统。项目以「让每一位研究生都能拥有一个 7×24 小时在线的 AI 导师团队」为愿景，通过多 Agent 协作架构，覆盖从信息确权、创意激发、可行性校验、多粒度生成到深度辅助的完整开题流程。

### 1.1.1 解决的核心痛点

研究生在开题阶段普遍面临以下痛点，ThesisMiner 针对性地提供了系统化解决方案：

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         研究生开题痛点 vs ThesisMiner 解决方案            │
├──────────────────────┬──────────────────────────────────────────────────┤
│ 痛点                  │ ThesisMiner 解决方案                              │
├──────────────────────┼──────────────────────────────────────────────────┤
│ 选题方向不明确        │ 五阶段闭环导航：信息确权→创意→校验→生成→辅助      │
│ 文献调研不充分        │ SearcherAgent 联网检索 + 引用解析 + 谱系图谱      │
│ 创新性难以判断        │ NoveltyChecker + PlagiarismChecker 双重校验       │
│ 可行性评估缺失        │ AcademicCalendar 时间约束 + 资源校验              │
│ 格式规范不统一        │ FormatValidator + StyleNormalizer 自动规范化     │
│ 多次返工成本高        │ 状态机回退机制 + 阶段门禁控制                     │
│ 导师沟通效率低        │ MentorAgent 模拟导师对话 + 多粒度生成             │
│ 成本不可控            │ TransparentLedger 透明账本 + 预算管理             │
└──────────────────────┴──────────────────────────────────────────────────┘
```

### 1.1.2 设计哲学

ThesisMiner v8.0 遵循以下设计哲学：

1. **Multi-Agent 协作优先**：摒弃单体 LLM 调用，采用 Orchestrator + 5 子 Agent 的分工架构，每个 Agent 专注单一职责，独立上下文，独立模型路由。
2. **闭环导航**：五阶段流程不是线性流水线，而是带门禁与回退机制的闭环，确保每阶段输出质量达标后才进入下一阶段。
3. **约束驱动**：硬约束（Hard Rules）作为不可逾越的红线，软约束（Soft Rules）作为质量提升的引导，二者协同保证输出规范性。
4. **成本透明**：每一次 LLM 调用都记录到透明账本，用户可随时查看用量与成本，支持预算上限与自动降级。
5. **缓存优先**：DeepSeek 三段式 Prompt 缓存设计，目标命中率 ≥95%，大幅降低重复调用的成本与延迟。
6. **可扩展性**：Agent、约束规则、导出格式、管道模板均支持热插拔，新增能力无需修改核心代码。

## 1.2 核心能力速览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ThesisMiner v8.0 核心能力矩阵                       │
├─────────────────┬───────────────────────────────────────────────────────────┤
│ 能力域           │ 具体能力                                                  │
├─────────────────┼───────────────────────────────────────────────────────────┤
│ 多 Agent 协作    │ Orchestrator + Searcher/Reasoner/Critic/Mentor/Writer    │
│ 五阶段闭环       │ info_confirm → creativity → validation → generation      │
│                 │ → deep_assist（带门禁与回退）                              │
│ 多对话管理       │ 单会话多对话，上下文隔离，DST 压缩                        │
│ 约束引擎         │ 硬规则 + 软规则 + 学术日历 + 文献基线 + 格式校验           │
│ 创意引擎         │ 学术谱系 + 跨域联想 + 趋势嫁接 + 候选排序                 │
│ 知识图谱         │ D3.js v7 力导向图 + 节点/边管理 + 知识卡片                │
│ AI 代理          │ 10 个 2026 模型 + 故障转移 + 降级链 + 重试退避            │
│ Prompt 缓存      │ 三段式 Prefix 设计 + 命中率监控 + ≥95% 目标              │
│ 引用解析         │ Web 搜索结果引用提取 + 域名识别 + Favicon 抓取            │
│ 预算管理         │ 透明账本 + 估算器 + 汇总统计 + 预算告警                   │
│ 多粒度生成       │ 标题/摘要/大纲/全文 四级粒度                              │
│ 导出能力         │ Markdown / HTML / DOCX / JSON / BibTeX                   │
│ 分析监控         │ 指标采集 + 性能监控 + 用量追踪                            │
│ 机器学习组件     │ Embedding 引擎 + 相似度打分 + 文本处理                    │
└─────────────────┴───────────────────────────────────────────────────────────┘
```

## 1.3 技术栈全景

ThesisMiner v8.0 的技术栈经过精心选型，兼顾开发效率、运行性能与可维护性：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            技术栈分层架构                                    │
├──────────────┬──────────────────────────────────────────────────────────────┤
│ 层级          │ 技术选型                                                     │
├──────────────┼──────────────────────────────────────────────────────────────┤
│ 前端          │ 原生 HTML5 + CSS3 + JavaScript (ES2022) + D3.js v7          │
│ 后端框架      │ FastAPI 0.110+ (基于 Starlette + Pydantic 2.x)              │
│ ASGI 服务器   │ Uvicorn (with uvloop + httptools)                           │
│ 数据库        │ SQLite 3.40+ (WAL 模式) + SQLAlchemy 2.0 ORM                │
│ AI SDK        │ OpenAI Python SDK 1.12+ (兼容多家 API)                      │
│ HTTP 客户端   │ httpx 0.27+ (异步 HTTP 客户端)                              │
│ 配置管理      │ python-dotenv + YAML + JSON                                 │
│ 日志系统      │ Python logging + 自定义 Formatter                           │
│ 测试框架      │ pytest + pytest-asyncio + httpx (ASGI 测试)                 │
│ 包管理        │ pip + requirements.txt                                      │
│ 版本控制      │ Git + GitHub                                                │
│ CI/CD         │ GitHub Actions                                              │
│ 容器化        │ Docker + Docker Compose                                     │
│ 反向代理      │ Nginx (生产环境)                                            │
│ 进程管理      │ systemd / supervisord                                       │
└──────────────┴──────────────────────────────────────────────────────────────┘
```

### 1.3.1 为什么选择这些技术

**FastAPI 而非 Flask/Django**：
- 原生异步支持，适合高并发 AI 调用场景
- 自动生成 OpenAPI 文档，降低 API 维护成本
- Pydantic 2.x 提供类型安全的请求/响应校验
- 性能接近 Node.js / Go，远超 Flask

**SQLite 而非 PostgreSQL/MySQL**：
- 单文件部署，降低运维复杂度
- WAL 模式下支持并发读 + 单写，满足中小规模场景
- 零配置，开箱即用，适合学术工具定位
- 通过 SQLAlchemy 可平滑迁移至其他数据库

**D3.js v7 而非 Vue/React**：
- 谱系图谱是数据可视化场景，D3.js 是最佳选择
- 力导向图布局算法成熟，性能优秀
- 无需构建工具链，降低前端复杂度
- 与原生 JS 无缝集成

**OpenAI SDK 兼容多家 API**：
- DeepSeek、通义、智谱等均提供 OpenAI 兼容接口
- 单一 SDK 降低依赖管理复杂度
- 切换模型只需修改 base_url 与 model_name

## 1.4 版本演进历程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ThesisMiner 版本演进时间线                          │
├──────────┬──────────────┬───────────────────────────────────────────────────┤
│ 版本      │ 发布时间      │ 核心变更                                          │
├──────────┼──────────────┼───────────────────────────────────────────────────┤
│ v1.0     │ 2024-06      │ 单体 LLM 调用，基础论题生成                       │
│ v2.0     │ 2024-09      │ 引入五阶段流程，SQLite 持久化                     │
│ v3.0     │ 2024-12      │ 多模型支持，成本统计                              │
│ v4.0     │ 2025-03      │ 约束引擎，硬规则校验                              │
│ v5.0     │ 2025-06      │ 谱系图谱，D3.js 可视化                            │
│ v6.0     │ 2025-09      │ 真实文献检索，引用解析                            │
│ v7.0     │ 2025-12      │ 多对话管理，DST 压缩，上下文隔离                  │
│ v8.0     │ 2026-03      │ Multi-Agent 架构，三段式缓存，2026 模型注册表     │
└──────────┴──────────────┴───────────────────────────────────────────────────┘
```

### 1.4.1 v8.0 核心变更详解

v8.0 是一次架构级升级，主要变更包括：

1. **Multi-Agent 架构重构**：从单体 LLM 调用升级为 Orchestrator + 5 子 Agent 的协作架构，每个 Agent 拥有独立上下文窗口与模型路由。

2. **三段式 Prompt 缓存**：针对 DeepSeek API 的缓存机制，设计了 System / Few-shot / User 三段式 Prefix，目标命中率 ≥95%。

3. **2026 模型注册表**：全面更新至 2026 年最新模型，包括 GPT-4.1、Claude Sonnet/Opus 4.5、DeepSeek V3.2/R2、Qwen3 Max、Gemini 2.5 Pro、GLM-4.6、Doubao 1.5 Pro 等 10 个模型。

4. **多对话上下文隔离**：单会话下支持多对话，每个对话独立维护消息列表与上下文窗口，通过 DST（Dialogue State Tracker）压缩长上下文。

5. **管道模板路由**：预定义 20+ 管道模板（论题生成、文献综述、可行性检查等），每个模板的每个阶段可指定不同模型。

6. **预算透明化**：TransparentLedger 记录每一次 LLM 调用的 Token 用量与成本，支持按会话/模型/时间维度查询。

## 1.5 仓库结构鸟瞰

```
ThesisMiner/
├── backend/                    # 后端 Python 包
│   ├── agents/                 # 多 Agent 架构
│   ├── ai/                     # AI 代理与缓存
│   ├── analytics/              # 分析与监控
│   ├── budgets/                # 预算与账本
│   ├── constraints/            # 约束引擎
│   ├── creativity/             # 创意引擎
│   ├── export/                 # 导出与报告
│   ├── knowledge/              # 知识图谱
│   ├── ml/                     # 机器学习组件
│   ├── orchestration/          # 编排与状态机
│   ├── routes/                 # FastAPI 路由
│   ├── sessions/               # 会话与对话管理
│   ├── utils/                  # 工具函数
│   ├── config.py               # 配置管理
│   ├── database.py             # 数据库连接
│   └── models.py               # Pydantic 数据模型
├── config/                     # 配置文件目录
│   ├── agents/                 # Agent 配置 YAML
│   ├── constraints/            # 约束规则 YAML
│   ├── models.yaml             # 模型注册表
│   ├── routing.yaml            # 路由配置
│   ├── monitoring.yaml         # 监控配置
│   └── system.yaml             # 系统配置
├── docs/                       # 文档目录
│   ├── api/                    # API 文档
│   ├── architecture/           # 架构文档
│   ├── changelog/              # 变更日志
│   ├── constraints/            # 约束文档
│   ├── development/            # 开发文档
│   └── tutorials/              # 教程文档
├── frontend/                   # 前端资源
│   ├── scripts/                # JavaScript
│   ├── styles/                 # CSS
│   └── index.html              # 入口 HTML
├── samples/                    # 示例代码
├── tests/                      # 测试代码
│   ├── e2e/                    # 端到端测试
│   ├── fixtures/               # 测试夹具
│   ├── integration/            # 集成测试
│   ├── load/                   # 压力测试
│   └── unit/                   # 单元测试
├── main.py                     # 应用入口
├── requirements.txt            # Python 依赖
└── README.md                   # 项目说明
```

---

# 第 2 章 开发环境搭建

## 2.1 系统要求

### 2.1.1 操作系统支持

ThesisMiner v8.0 在以下操作系统上经过完整测试：

| 操作系统 | 版本要求 | 支持等级 | 备注 |
|---------|---------|---------|------|
| Windows | 10/11 (64-bit) | 一级支持 | 开发团队主力环境 |
| macOS | 12 Monterey+ | 一级支持 | Apple Silicon 与 Intel 均支持 |
| Ubuntu Linux | 22.04 LTS+ | 一级支持 | 生产环境推荐 |
| CentOS/RHEL | 8+ | 二级支持 | 企业部署场景 |
| Debian | 11+ | 二级支持 | Docker 基础镜像 |

### 2.1.2 硬件要求

| 资源 | 最低要求 | 推荐配置 | 说明 |
|------|---------|---------|------|
| CPU | 2 核 | 4 核+ | AI 调用为 IO 密集型，CPU 压力较小 |
| 内存 | 2 GB | 4 GB+ | SQLite + Uvicorn 常驻内存约 200MB |
| 磁盘 | 1 GB | 5 GB+ | 数据库与日志增长较快 |
| 网络 | 可访问公网 | 稳定低延迟 | 需调用多家 LLM API |

### 2.1.3 软件依赖版本

| 软件 | 最低版本 | 推荐版本 | 用途 |
|------|---------|---------|------|
| Python | 3.11 | 3.12+ | 后端运行时 |
| Node.js | 18 LTS | 20 LTS+ | 前端构建工具（可选） |
| Git | 2.30+ | 2.40+ | 版本控制 |
| pip | 23.0+ | 24.0+ | Python 包管理 |
| SQLite | 3.40+ | 3.45+ | 数据库（Python 自带） |

## 2.2 Python 3.11+ 环境安装

### 2.2.1 Windows 安装

**方式一：官方安装包（推荐新手）**

1. 访问 Python 官网下载 Python 3.12+ 安装包
2. 运行安装程序，务必勾选「Add Python to PATH」
3. 选择「Customize installation」，确保勾选 pip 与 tcl/tk
4. 安装完成后打开 PowerShell 验证：

```powershell
# 验证 Python 安装
python --version
# 预期输出：Python 3.12.x

# 验证 pip 安装
pip --version
# 预期输出：pip 24.x.x from ...

# 验证 sqlite3 模块
python -c "import sqlite3; print(sqlite3.sqlite_version)"
# 预期输出：3.45.x
```

**方式二：通过 winget 安装**

```powershell
# 使用 Windows 包管理器安装
winget install Python.Python.3.12

# 验证安装
python --version
```

**方式三：通过 conda 安装（推荐数据科学场景）**

```powershell
# 安装 Miniconda
winget install Anaconda.Miniconda3

# 创建专用环境
conda create -n thesisminer python=3.12
conda activate thesisminer
```

### 2.2.2 macOS 安装

```bash
# 使用 Homebrew 安装
brew install python@3.12

# 验证安装
python3.12 --version
python3.12 -c "import sqlite3; print(sqlite3.sqlite_version)"
```

### 2.2.3 Linux 安装

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.12 python3.12-venv python3.12-dev

# 验证安装
python3.12 --version
python3.12 -c "import sqlite3; print(sqlite3.sqlite_version)"
```

### 2.2.4 验证 Python 环境完整性

创建 `verify_python.py` 脚本验证环境：

```python
"""验证 Python 环境是否满足 ThesisMiner 要求"""
import sys
import sqlite3
import importlib

def verify_python():
    """验证 Python 版本"""
    version = sys.version_info
    print(f"Python 版本：{version.major}.{version.minor}.{version.micro}")
    if version < (3, 11):
        print("Python 版本过低，需要 3.11+")
        return False
    print("Python 版本满足要求")
    return True

def verify_sqlite():
    """验证 SQLite 版本"""
    version = sqlite3.sqlite_version
    print(f"SQLite 版本：{version}")
    major, minor, _ = (int(x) for x in version.split("."))
    if (major, minor) < (3, 40):
        print("SQLite 版本过低，需要 3.40+")
        return False
    print("SQLite 版本满足要求")
    return True

def verify_modules():
    """验证必需模块"""
    required = ["asyncio", "json", "pathlib", "dataclasses", "typing"]
    for mod in required:
        try:
            importlib.import_module(mod)
            print(f"{mod} 模块可用")
        except ImportError:
            print(f"{mod} 模块缺失")
            return False
    return True

if __name__ == "__main__":
    print("=" * 50)
    print("ThesisMiner Python 环境验证")
    print("=" * 50)
    ok = all([verify_python(), verify_sqlite(), verify_modules()])
    print("=" * 50)
    if ok:
        print("环境验证通过，可以开始安装 ThesisMiner")
    else:
        print("环境验证失败，请按提示修复")
    sys.exit(0 if ok else 1)
```

运行验证脚本：

```bash
python verify_python.py
```

## 2.3 Node.js 18+ 环境安装

Node.js 在 ThesisMiner 中主要用于前端构建工具链（可选）。如果你只修改后端，可以跳过本节。

### 2.3.1 Windows 安装

```powershell
# 使用 winget 安装
winget install OpenJS.NodeJS.LTS

# 验证安装
node --version
# 预期输出：v20.x.x

npm --version
# 预期输出：10.x.x
```

### 2.3.2 macOS 安装

```bash
# 使用 Homebrew 安装
brew install node@20

# 验证安装
node --version
npm --version
```

### 2.3.3 Linux 安装

```bash
# Ubuntu/Debian - 使用 NodeSource 仓库
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# 验证安装
node --version
npm --version
```

### 2.3.4 配置 npm 镜像（中国大陆用户推荐）

```bash
# 设置淘宝镜像
npm config set registry https://registry.npmmirror.com

# 验证配置
npm config get registry
```

## 2.4 Git 与版本控制

### 2.4.1 Git 安装

**Windows**：
```powershell
winget install Git.Git
```

**macOS**：
```bash
brew install git
```

**Linux**：
```bash
sudo apt install git
```

### 2.4.2 Git 全局配置

安装 Git 后，进行全局配置：

```bash
# 配置用户名与邮箱（使用你的真实信息）
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# 配置默认分支名为 main
git config --global init.defaultBranch main

# 配置默认编辑器
git config --global core.editor "code --wait"  # VS Code
# 或
git config --global core.editor "vim"

# 配置换行符处理（Windows）
git config --global core.autocrlf true
# macOS/Linux
git config --global core.autocrlf input

# 配置中文文件名显示
git config --global core.quotepath false

# 配置长路径支持（Windows）
git config --global core.longpaths true
```

### 2.4.3 SSH 密钥配置

```bash
# 生成 SSH 密钥（使用你的邮箱）
ssh-keygen -t ed25519 -C "your.email@example.com"

# 查看公钥
cat ~/.ssh/id_ed25519.pub

# 将公钥添加到 GitHub 账户
# 访问 https://github.com/settings/keys
# 点击 "New SSH key" 粘贴公钥

# 测试 SSH 连接
ssh -T git@github.com
# 预期输出：Hi your-username! You've successfully authenticated...
```

### 2.4.4 克隆仓库

```bash
# 通过 SSH 克隆（推荐）
git clone git@github.com:your-org/ThesisMiner.git

# 或通过 HTTPS 克隆
git clone https://github.com/your-org/ThesisMiner.git

# 进入项目目录
cd ThesisMiner

# 查看当前分支
git branch -a

# 查看最近提交
git log --oneline -10
```

## 2.5 虚拟环境与依赖管理

### 2.5.1 创建虚拟环境

**方式一：venv（Python 内置，推荐）**

```bash
# 在项目根目录创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows PowerShell
.venv\Scripts\Activate.ps1
# Windows CMD
.venv\Scripts\activate.bat
# macOS/Linux
source .venv/bin/activate

# 验证激活（命令行前缀应显示 .venv）
which python
# 预期输出：.../ThesisMiner/.venv/bin/python
```

**Windows PowerShell 执行策略问题处理**：

如果激活时遇到「无法加载文件，因为在此系统上禁止运行脚本」错误：

```powershell
# 以管理员身份运行 PowerShell，执行
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 然后重新激活
.venv\Scripts\Activate.ps1
```

**方式二：conda（推荐数据科学场景）**

```bash
# 创建 conda 环境
conda create -n thesisminer python=3.12

# 激活环境
conda activate thesisminer
```

### 2.5.2 安装依赖

```bash
# 升级 pip
python -m pip install --upgrade pip

# 安装项目依赖
pip install -r requirements.txt

# 验证关键依赖
python -c "import fastapi; print(f'FastAPI {fastapi.__version__}')"
python -c "import uvicorn; print(f'Uvicorn {uvicorn.__version__}')"
python -c "import pydantic; print(f'Pydantic {pydantic.__version__}')"
python -c "import sqlalchemy; print(f'SQLAlchemy {sqlalchemy.__version__}')"
python -c "import openai; print(f'OpenAI {openai.__version__}')"
python -c "import httpx; print(f'httpx {httpx.__version__}')"
```

### 2.5.3 开发依赖安装

安装开发所需的额外工具：

```bash
# 安装开发工具
pip install pytest pytest-asyncio pytest-cov httpx black ruff mypy

# 验证安装
pytest --version
black --version
ruff --version
mypy --version
```

### 2.5.4 依赖冲突排查

如果遇到依赖冲突，使用以下命令排查：

```bash
# 查看已安装包列表
pip list

# 查看某个包的依赖关系
pip show fastapi

# 检查依赖冲突
pip check

# 生成依赖树
pip install pipdeptree
pipdeptree
```

## 2.6 API Key 配置

ThesisMiner 支持多家 LLM 提供商，你需要至少配置一个 API Key 才能使用 AI 功能。

### 2.6.1 创建环境变量文件

在项目根目录创建 `.env` 文件：

```bash
# 复制示例文件
cp .env.example .env

# 编辑 .env 文件
# Windows: notepad .env
# macOS/Linux: nano .env
```

### 2.6.2 .env 文件内容

```ini
# =============================================================================
# ThesisMiner 环境变量配置
# =============================================================================

# ----- OpenAI API Key -----
# 获取地址：https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxx

# ----- DeepSeek API Key -----
# 获取地址：https://platform.deepseek.com/api_keys
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx

# ----- Anthropic API Key -----
# 获取地址：https://console.anthropic.com/
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxx

# ----- 阿里云 DashScope API Key -----
# 获取地址：https://dashscope.console.aliyun.com/apiKey
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx

# ----- Google AI API Key -----
# 获取地址：https://aistudio.google.com/app/apikey
GOOGLE_API_KEY=AIzaxxxxxxxxxxxxxxxxxxx

# ----- 智谱 AI API Key -----
# 获取地址：https://open.bigmodel.cn/usercenter/apikeys
ZHIPU_API_KEY=xxxxxxxxxxxxxxxx.xxxxxxxxxxxxxxxx

# ----- 火山引擎 API Key -----
# 获取地址：https://console.volcengine.com/ark/
VOLCENGINE_API_KEY=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# ----- 系统配置 -----
# 日志级别：DEBUG / INFO / WARNING / ERROR
LOG_LEVEL=INFO

# 数据库路径（默认 data/thesisminer.db）
DB_PATH=data/thesisminer.db

# 是否自动打开浏览器
AUTO_OPEN_BROWSER=true

# Flask 环境（保持 development）
FLASK_ENV=development
```

### 2.6.3 API Key 安全须知

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          API Key 安全最佳实践                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. 永远不要将 .env 文件提交到 Git 仓库                                    │
│     → .gitignore 已包含 .env，请勿手动移除                                  │
│                                                                             │
│  2. 不要在代码中硬编码 API Key                                              │
│     → 始终通过 os.getenv() 读取                                             │
│                                                                             │
│  3. 不要在日志中打印 API Key                                                │
│     → 日志系统已配置脱敏过滤器                                              │
│                                                                             │
│  4. 定期轮换 API Key                                                        │
│     → 建议每 90 天更换一次                                                  │
│                                                                             │
│  5. 为不同环境使用不同 Key                                                  │
│     → 开发/测试/生产环境使用独立 Key                                        │
│                                                                             │
│  6. 设置 API Key 用量上限                                                   │
│     → 在各提供商后台设置预算上限                                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.6.4 验证 API Key 配置

```python
"""验证 API Key 配置"""
import os
from dotenv import load_dotenv

load_dotenv()

keys = {
    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
    "DEEPSEEK_API_KEY": os.getenv("DEEPSEEK_API_KEY"),
    "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
    "DASHSCOPE_API_KEY": os.getenv("DASHSCOPE_API_KEY"),
    "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY"),
    "ZHIPU_API_KEY": os.getenv("ZHIPU_API_KEY"),
    "VOLCENGINE_API_KEY": os.getenv("VOLCENGINE_API_KEY"),
}

print("=" * 50)
print("API Key 配置状态")
print("=" * 50)
for name, value in keys.items():
    if value:
        # 仅显示前 8 位与后 4 位
        masked = f"{value[:8]}...{value[-4:]}" if len(value) > 12 else "***"
        print(f"OK {name}: {masked}")
    else:
        print(f"MISSING {name}: 未配置")
print("=" * 50)
configured = sum(1 for v in keys.values() if v)
print(f"已配置 {configured}/{len(keys)} 个 API Key")
if configured == 0:
    print("WARNING: 至少需要配置一个 API Key 才能使用 AI 功能")
```

## 2.7 IDE 与编辑器配置

### 2.7.1 VS Code 配置（推荐）

**安装推荐扩展**：

```json
// .vscode/extensions.json
{
    "recommendations": [
        "ms-python.python",
        "ms-python.vscode-pylance",
        "ms-python.black-formatter",
        "charliermarsh.ruff",
        "ms-python.mypy-type-checker",
        "redhat.vscode-yaml",
        "yzhang.markdown-all-in-one",
        "shd101wyy.markdown-preview-enhanced",
        "eamodio.gitlens",
        "ms-vscode.vscode-json"
    ]
}
```

**工作区设置**：

```json
// .vscode/settings.json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
    "python.analysis.typeCheckingMode": "basic",
    "python.analysis.autoImportCompletions": true,
    "python.formatting.provider": "none",
    "[python]": {
        "editor.defaultFormatter": "ms-python.black-formatter",
        "editor.formatOnSave": true,
        "editor.codeActionsOnSave": {
            "source.fixAll.ruff": "explicit",
            "source.organizeImports.ruff": "explicit"
        }
    },
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": ["tests"],
    "python.testing.autoTestDiscoverOnSaveEnabled": true,
    "files.exclude": {
        "**/__pycache__": true,
        "**/.pytest_cache": true,
        "**/.mypy_cache": true,
        "**/.ruff_cache": true
    },
    "search.exclude": {
        "**/data": true,
        "**/.venv": true
    },
    "editor.rulers": [88],
    "editor.tabSize": 4,
    "editor.insertSpaces": true
}
```

**调试配置**：

```json
// .vscode/launch.json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "ThesisMiner Server",
            "type": "debugpy",
            "request": "launch",
            "module": "uvicorn",
            "args": ["main:app", "--reload", "--host", "127.0.0.1", "--port", "8000"],
            "jinja": true,
            "justMyCode": true,
            "env": {
                "LOG_LEVEL": "DEBUG"
            }
        },
        {
            "name": "Pytest Current File",
            "type": "debugpy",
            "request": "launch",
            "module": "pytest",
            "args": ["${file}", "-v", "-s"],
            "console": "integratedTerminal"
        },
        {
            "name": "Pytest All",
            "type": "debugpy",
            "request": "launch",
            "module": "pytest",
            "args": ["tests/", "-v", "--cov=backend"],
            "console": "integratedTerminal"
        }
    ]
}
```

### 2.7.2 PyCharm 配置

1. 打开 PyCharm → File → Open → 选择 ThesisMiner 目录
2. File → Settings → Project → Python Interpreter → 选择 `.venv` 中的 Python
3. Run → Edit Configurations → 添加 Python 配置：
   - Module name: `uvicorn`
   - Parameters: `main:app --reload --host 127.0.0.1 --port 8000`
   - Working directory: 项目根目录
4. 配置测试框架：Settings → Tools → Python Integrated Tools → Testing → pytest

### 2.7.3 Vim/Neovim 配置

对于 Vim 用户，推荐使用以下插件配置：

```vim
" .vimrc 或 init.vim
Plug 'dense-analysis/ale'           " 代码检查
Plug 'psf/black', { 'tag': '24.1.0' }  " 代码格式化
Plug 'vim-test/vim-test'            " 测试运行
Plug 'nvim-treesitter/nvim-treesitter'  " 语法高亮

" Python 专用设置
let g:ale_linters = {'python': ['ruff', 'mypy']}
let g:ale_fixers = {'python': ['black', 'ruff']}
let g:ale_fix_on_save = 1
set colorcolumn=88
set tabstop=4
set shiftwidth=4
set expandtab
```

## 2.8 数据库初始化

### 2.8.1 自动初始化

ThesisMiner 在首次启动时会自动创建数据库与所有表：

```bash
# 启动应用（会自动初始化数据库）
python main.py

# 或通过 uvicorn 启动
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### 2.8.2 手动初始化

如果需要手动初始化数据库（例如在测试环境中）：

```python
"""手动初始化数据库"""
import sys
import os

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend import database

# 初始化数据库
database.init_db()
print("数据库初始化完成")

# 验证表创建
conn = database.get_db_connection()
tables = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
).fetchall()
conn.close()

print(f"已创建 {len(tables)} 张表：")
for table in tables:
    print(f"  - {table['name']}")
```

### 2.8.3 数据库结构概览

ThesisMiner v8.0 的数据库包含以下核心表：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          数据库表结构总览                                    │
├──────────────────────┬──────────────────────────────────────────────────────┤
│ 表名                  │ 用途                                                 │
├──────────────────────┼──────────────────────────────────────────────────────┤
│ sessions             │ 会话主表（学位/学科/导师/研究方向）                  │
│ conversations        │ 对话表（会话下的多对话）                             │
│ conversation_messages│ 消息表（对话内的消息列表）                           │
│ search_citations     │ 引用表（消息的引用来源）                             │
│ proposals            │ 论题表（生成的论题提案）                             │
│ lineage_nodes        │ 谱系节点表                                           │
│ lineage_edges        │ 谱系边表                                             │
│ knowledge_cards      │ 知识卡片表                                           │
│ budget_ledger        │ 预算账本表（每次 LLM 调用记录）                      │
│ cache_stats          │ 缓存统计表                                           │
│ agent_executions     │ Agent 执行记录表                                     │
│ constraint_violations│ 约束违规记录表                                       │
└──────────────────────┴──────────────────────────────────────────────────────┘
```

### 2.8.4 数据库管理工具

**命令行查看数据库**：

```bash
# 使用 sqlite3 命令行工具
sqlite3 data/thesisminer.db

# 常用命令
.tables                          # 查看所有表
.schema sessions                 # 查看 sessions 表结构
SELECT * FROM sessions LIMIT 5;  # 查询数据
.quit                            # 退出
```

**使用 DB Browser for SQLite（GUI 工具）**：

1. 下载 DB Browser for SQLite
2. 打开 `data/thesisminer.db` 文件
3. 可视化浏览表结构与数据

## 2.9 首次启动验证

### 2.9.1 启动开发服务器

```bash
# 确保虚拟环境已激活
# Windows: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate

# 启动开发服务器
python main.py

# 预期输出：
# INFO:     Will watch for changes in these directories: ['d:/CodeProject/ThesisMiner']
# INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
# INFO:     Started reloader process [xxxxx] using WatchFiles
# INFO:     Started server process [xxxxx]
# INFO:     Waiting for application startup.
# INFO:     Application startup complete.
```

### 2.9.2 验证服务可用性

```bash
# 在另一个终端窗口执行

# 1. 验证首页可访问
curl http://127.0.0.1:8000/

# 2. 验证 API 文档可访问
curl http://127.0.0.1:8000/docs

# 3. 验证配置接口
curl http://127.0.0.1:8000/api/config

# 4. 验证会话列表
curl http://127.0.0.1:8000/api/sessions

# 5. 验证 Agent 列表
curl http://127.0.0.1:8000/api/agents

# 6. 验证模型定价
curl http://127.0.0.1:8000/api/budgets/pricing
```

### 2.9.3 浏览器访问

打开浏览器访问 `http://127.0.0.1:8000`，你应该看到 ThesisMiner 的主界面。

**首次访问检查清单**：

- [ ] 页面正常加载，无控制台错误
- [ ] 左侧导航栏显示所有功能入口
- [ ] 仪表盘页面显示空状态（无会话数据）
- [ ] 设置页面显示 API Key 配置状态
- [ ] 谱系页面显示空图谱
- [ ] 预算页面显示零成本

### 2.9.4 常见启动问题

**问题 1：端口被占用**

```bash
# 查看端口占用
# Windows
netstat -ano | findstr :8000
# macOS/Linux
lsof -i :8000

# 解决方案 1：结束占用进程
# Windows
taskkill /PID <PID> /F
# macOS/Linux
kill -9 <PID>

# 解决方案 2：更换端口
uvicorn main:app --reload --port 8001
```

**问题 2：模块导入失败**

```bash
# 确保在项目根目录执行
cd d:/CodeProject/ThesisMiner

# 确保虚拟环境已激活
which python  # 应指向 .venv

# 重新安装依赖
pip install -r requirements.txt
```

**问题 3：数据库权限错误**

```bash
# 确保数据目录存在且有写权限
mkdir -p data
chmod 755 data  # macOS/Linux

# Windows: 右键 data 目录 → 属性 → 安全 → 编辑权限
```

---

# 第 3 章 项目结构详解

## 3.1 顶层目录结构

ThesisMiner v8.0 的顶层目录遵循「关注点分离」原则，每个顶层目录承担明确的职责：

```
ThesisMiner/
│
├── backend/          # 后端 Python 包（核心业务逻辑）
├── frontend/         # 前端静态资源（HTML/CSS/JS）
├── config/           # 配置文件（YAML 格式）
├── docs/             # 项目文档
├── samples/          # 示例代码
├── tests/            # 测试代码
├── data/             # 运行时数据（数据库/日志，gitignore）
├── main.py           # 应用入口
├── requirements.txt  # Python 依赖清单
├── README.md         # 项目说明
├── .gitignore        # Git 忽略规则
└── .env              # 环境变量（gitignore）
```

### 3.1.1 目录职责矩阵

| 目录 | 职责 | 可修改 | 提交到 Git | 说明 |
|------|------|--------|-----------|------|
| backend/ | 后端业务逻辑 | 是 | 是 | 核心代码 |
| frontend/ | 前端资源 | 是 | 是 | 静态文件 |
| config/ | 配置文件 | 是 | 是 | YAML 配置 |
| docs/ | 项目文档 | 是 | 是 | 文档源码 |
| samples/ | 示例代码 | 是 | 是 | 学习参考 |
| tests/ | 测试代码 | 是 | 是 | 质量保证 |
| data/ | 运行时数据 | 否 | 否 | 自动生成 |
| .venv/ | 虚拟环境 | 否 | 否 | 本地环境 |
| __pycache__/ | Python 缓存 | 否 | 否 | 自动生成 |

## 3.2 backend 后端模块

backend 是 ThesisMiner 的核心 Python 包，采用分层架构：

```
backend/
├── __init__.py              # 包初始化
├── config.py                # 配置管理（加载 .env 与 config.json）
├── database.py              # 数据库连接与初始化
├── models.py                # Pydantic 数据模型
│
├── agents/                  # 多 Agent 架构
│   ├── __init__.py
│   ├── base_agent.py        # Agent 抽象基类
│   ├── orchestrator.py      # 主管理 Agent
│   ├── searcher_wrapper.py  # 检索 Agent
│   ├── reasoner.py          # 推理 Agent
│   ├── reasoner_proposal.py # 论题推理 Agent
│   ├── critic.py            # 批评 Agent
│   ├── mentor_agent.py      # 导师 Agent
│   ├── proposal_writer.py   # 写作 Agent
│   ├── agent_registry.py    # Agent 注册表
│   ├── agent_context.py     # Agent 上下文管理
│   └── agent_communicator.py# Agent 间通信
│
├── ai/                      # AI 代理层
│   ├── __init__.py
│   ├── ai_proxy.py          # LLM 调用代理
│   ├── prompt_cache.py      # Prompt 缓存
│   ├── cache_monitor.py     # 缓存监控
│   ├── citation_parser.py   # 引用解析器
│   ├── streaming.py         # 流式响应处理
│   ├── response_parser.py   # 响应解析器
│   └── prompts.py           # Prompt 模板
│
├── analytics/               # 分析与监控
│   ├── __init__.py
│   ├── metrics_collector.py # 指标采集
│   ├── performance_monitor.py # 性能监控
│   └── usage_tracker.py     # 用量追踪
│
├── budgets/                 # 预算管理
│   ├── __init__.py
│   ├── estimator.py         # 预算估算器
│   └── transparent_ledger.py # 透明账本
│
├── constraints/             # 约束引擎
│   ├── __init__.py
│   ├── hard_rules.py        # 硬规则
│   ├── rule_engine.py       # 规则引擎
│   ├── format_validator.py  # 格式校验
│   ├── academic_calendar.py # 学术日历
│   ├── academic_standards.py # 学术标准
│   ├── lit_baselines.py     # 文献基线
│   ├── novelty_checker.py   # 新颖性检查
│   ├── plagiarism_checker.py # 抄袭检查
│   ├── style_normalizer.py  # 风格规范化
│   ├── multi_granularity.py # 多粒度生成
│   ├── stage_gate.py        # 阶段门禁
│   ├── deep_assist.py       # 深度辅助
│   └── exceptions.py        # 约束异常
│
├── creativity/              # 创意引擎
│   ├── __init__.py
│   ├── academic_lineage.py  # 学术谱系
│   ├── cross_domain.py      # 跨域联想
│   ├── candidate_ranker.py  # 候选排序
│   └── problem_awareness.py # 问题意识
│
├── export/                  # 导出模块
│   ├── __init__.py
│   ├── document_exporter.py # 文档导出
│   ├── citation_formatter.py # 引用格式化
│   └── report_generator.py  # 报告生成
│
├── knowledge/               # 知识图谱
│   ├── __init__.py
│   ├── lineage_graph_store.py # 谱系存储
│   ├── graph_expander.py    # 图谱扩展
│   └── card_manager.py      # 知识卡片
│
├── ml/                      # 机器学习组件
│   ├── __init__.py
│   ├── embedding_engine.py  # Embedding 引擎
│   ├── similarity_scorer.py # 相似度打分
│   └── text_processor.py    # 文本处理
│
├── orchestration/           # 编排层
│   ├── __init__.py
│   ├── pipeline.py          # 管道执行
│   ├── scheduler.py         # 调度器
│   ├── state_machine.py     # 状态机
│   └── hooks/               # 钩子
│       ├── __init__.py
│       ├── pre_search.py    # 检索前钩子
│       ├── post_reasoner.py # 推理后钩子
│       ├── hard_rule_interceptor.py # 硬规则拦截器
│       └── academic_feasibility_check.py # 可行性检查
│
├── routes/                  # FastAPI 路由
│   ├── __init__.py
│   ├── config.py            # 配置路由
│   ├── sessions.py          # 会话路由
│   ├── conversations.py     # 对话路由
│   ├── proposals.py         # 论题路由
│   ├── constraints.py       # 约束路由
│   ├── creativity.py        # 创意路由
│   ├── lineage.py           # 谱系路由
│   ├── budgets.py           # 预算路由
│   └── citations.py         # 引用路由
│
├── sessions/                # 会话管理
│   ├── __init__.py
│   ├── session_manager.py   # 会话管理器
│   ├── conversation_manager.py # 对话管理器
│   ├── context_manager.py   # 上下文管理器
│   ├── dialogue_state_tracker.py # DST 对话状态追踪
│   └── dst_compactor.py     # DST 压缩器
│
└── utils/                   # 工具函数
    ├── __init__.py
    ├── cache.py             # 缓存工具
    ├── helpers.py           # 辅助函数
    ├── logger.py            # 日志工具
    ├── security.py          # 安全工具
    └── validators.py        # 校验工具
```

### 3.2.1 模块依赖关系

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          模块依赖关系图                                      │
│                                                                             │
│                          ┌──────────────┐                                   │
│                          │   main.py    │                                   │
│                          │  (应用入口)   │                                   │
│                          └──────┬───────┘                                   │
│                                 │                                           │
│                          ┌──────▼───────┐                                   │
│                          │   routes/    │                                   │
│                          │  (API 路由)   │                                   │
│                          └──────┬───────┘                                   │
│            ┌───────────────────┼───────────────────┐                        │
│            │                   │                   │                        │
│     ┌──────▼──────┐    ┌──────▼──────┐    ┌──────▼──────┐                 │
│     │  sessions/  │    │orchestration│    │constraints/ │                 │
│     │ (会话管理)   │    │  (编排层)    │    │ (约束引擎)   │                 │
│     └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                 │
│            │                  │                   │                        │
│            │           ┌──────▼──────┐            │                        │
│            │           │   agents/   │            │                        │
│            │           │ (多 Agent)  │            │                        │
│            │           └──────┬──────┘            │                        │
│            │                  │                   │                        │
│            └──────────────────┼───────────────────┘                        │
│                               │                                            │
│                        ┌──────▼──────┐                                     │
│                        │     ai/     │                                     │
│                        │ (AI 代理层)  │                                     │
│                        └──────┬──────┘                                     │
│                               │                                            │
│            ┌──────────────────┼───────────────────┐                        │
│            │                   │                   │                        │
│     ┌──────▼──────┐    ┌──────▼──────┐    ┌──────▼──────┐                 │
│     │  budgets/   │    │ analytics/  │    │knowledge/   │                 │
│     │ (预算管理)   │    │  (分析监控)  │    │ (知识图谱)   │                 │
│     └─────────────┘    └─────────────┘    └─────────────┘                 │
│                                                                             │
│                        ┌──────────────┐                                     │
│                        │  database.py │                                     │
│                        │  (数据访问层)  │                                     │
│                        └──────────────┘                                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2.2 模块职责详解

**config.py - 配置管理**

配置管理模块负责加载与管理系统配置，包括：
- 从 `.env` 文件加载环境变量
- 从 `data/config.json` 加载用户配置
- 提供全局单例 `Settings` 对象
- 按学位分级的模型路由常量
- 模型注册表（10 个 2026 模型）

**database.py - 数据库访问**

数据库访问模块提供 SQLite 数据库的连接与操作能力：
- 初始化数据库与所有表
- 提供 `get_db_connection()` 获取连接
- 提供 `execute_insert()` / `fetch_one()` / `fetch_all()` 等便捷方法
- 启用 WAL 模式以支持并发读

**models.py - 数据模型**

数据模型模块使用 Pydantic 2.x 定义所有 API 的请求/响应模型：
- `SessionCreate` - 会话创建请求
- `ProposalGenerateRequest` - 论题生成请求
- `ApiResponse` - 统一响应格式
- `DegreeType` - 学位类型枚举
- `DisciplineType` - 学科类型枚举

## 3.3 frontend 前端模块

前端采用原生 HTML/CSS/JS + D3.js v7，无需构建工具链：

```
frontend/
├── index.html              # 入口 HTML
├── styles/
│   └── main.css            # 全局样式
└── scripts/
    ├── app.js              # 应用主逻辑
    ├── api.js              # API 调用封装
    └── pages/
        ├── dashboard.js    # 仪表盘页面
        ├── sessions.js     # 会话管理页面
        ├── generate.js     # 论题生成页面
        ├── lineage.js      # 谱系图谱页面
        ├── budgets.js      # 预算管理页面
        └── settings.js     # 设置页面
```

### 3.3.1 前端架构说明

前端采用「页面模块化」架构，每个页面独立 JS 文件，通过 `app.js` 统一路由：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          前端架构图                                          │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        index.html                                   │   │
│  │  ┌─────────────┐  ┌─────────────────────────────────────────────┐  │   │
│  │  │  侧边导航栏  │  │              主内容区域                       │  │   │
│  │  │             │  │                                             │  │   │
│  │  │  - 仪表盘   │  │  ┌─────────────────────────────────────┐    │  │   │
│  │  │  - 会话     │  │  │     动态加载的页面内容                │    │  │   │
│  │  │  - 生成     │  │  │  (dashboard/sessions/generate/...)   │    │  │   │
│  │  │  - 谱系     │  │  └─────────────────────────────────────┘    │  │   │
│  │  │  - 预算     │  │                                             │  │   │
│  │  │  - 设置     │  │                                             │  │   │
│  │  └─────────────┘  └─────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                          app.js                                     │   │
│  │  - 页面路由（hash 路由）                                             │   │
│  │  - 全局状态管理                                                      │   │
│  │  - 事件总线                                                          │   │
│  └──────────────────────────────┬──────────────────────────────────────┘   │
│                                 │                                           │
│  ┌──────────────────────────────▼──────────────────────────────────────┐   │
│  │                          api.js                                      │   │
│  │  - fetch 封装                                                        │   │
│  │  - 请求/响应拦截                                                     │   │
│  │  - 错误处理                                                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       pages/*.js                                     │   │
│  │  - 各页面独立逻辑                                                    │   │
│  │  - D3.js 谱系图渲染                                                  │   │
│  │  - 表单处理                                                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 3.4 tests 测试模块

测试模块按测试类型分层组织：

```
tests/
├── unit/                    # 单元测试
│   ├── conftest.py          # pytest 夹具
│   ├── test_orchestrator.py # Orchestrator 测试
│   ├── test_critic.py       # Critic Agent 测试
│   ├── test_reasoner.py     # Reasoner Agent 测试
│   ├── test_searcher.py     # Searcher Agent 测试
│   ├── test_mentor.py       # Mentor Agent 测试
│   ├── test_writer.py       # Writer Agent 测试
│   ├── test_ai_proxy.py     # AI 代理测试
│   ├── test_prompt_cache.py # Prompt 缓存测试
│   ├── test_citation_parser.py # 引用解析测试
│   ├── test_hard_rules.py   # 硬规则测试
│   ├── test_format_validator.py # 格式校验测试
│   ├── test_state_machine.py # 状态机测试
│   ├── test_pipeline.py     # 管道测试
│   ├── test_database.py     # 数据库测试
│   └── ...                  # 更多单元测试
│
├── integration/             # 集成测试
│   ├── test_api_endpoints.py # API 端点集成测试
│   ├── test_five_stage_flow.py # 五阶段流程集成测试
│   ├── test_multi_agent_collaboration.py # 多 Agent 协作测试
│   ├── test_multi_conversation.py # 多对话集成测试
│   ├── test_cache_optimization.py # 缓存优化测试
│   └── test_citation_pipeline.py # 引用管道测试
│
├── e2e/                     # 端到端测试
│   ├── test_full_user_journey.py # 完整用户旅程测试
│   ├── test_frontend_pages.py # 前端页面测试
│   ├── test_generate_ui.py  # 生成界面测试
│   ├── test_sessions_ui.py  # 会话界面测试
│   └── test_lineage_graph.py # 谱系图谱测试
│
├── load/                    # 压力测试
│   ├── test_concurrent_sessions.py # 并发会话测试
│   ├── test_message_volume.py # 消息量测试
│   ├── test_cache_performance.py # 缓存性能测试
│   └── test_lineage_graph_performance.py # 谱系图谱性能测试
│
└── fixtures/                # 测试夹具
    ├── sample_papers.py     # 示例论文数据
    ├── sample_conversations.py # 示例对话数据
    ├── sample_theses.py     # 示例论题数据
    ├── sample_responses.py  # 示例 LLM 响应
    ├── sample_lineage.py    # 示例谱系数据
    └── sample_budgets.py    # 示例预算数据
```

### 3.4.1 测试命名规范

```
测试文件命名：test_<被测模块>.py
测试函数命名：test_<被测函数>_<场景>
测试类命名：Test<被测类>

示例：
test_orchestrator.py
  - test_orchestrator_init()
  - test_orchestrator_stage_transition()
  - test_orchestrator_fallback()
```

## 3.5 docs 文档模块

```
docs/
├── api/                     # API 文档
│   ├── openapi.yaml         # OpenAPI 规范
│   ├── conversation_api.md  # 对话 API
│   ├── agent_api.md         # Agent API
│   ├── error_codes.md       # 错误码
│   └── rate_limiting.md     # 速率限制
│
├── architecture/            # 架构文档
│   ├── system_overview.md   # 系统总览
│   ├── agent_architecture.md # Agent 架构
│   ├── five_stage_flow.md   # 五阶段流程
│   ├── data_flow.md         # 数据流
│   ├── database_design.md   # 数据库设计
│   ├── session_model.md     # 会话模型
│   ├── cache_strategy.md    # 缓存策略
│   ├── performance_design.md # 性能设计
│   └── security_design.md   # 安全设计
│
├── changelog/               # 变更日志
│   ├── v8_changelog.md      # v8.0 变更
│   └── version_history.md   # 版本历史
│
├── constraints/             # 约束文档
│   ├── hard_rules.md        # 硬规则
│   ├── rule_catalog.md      # 规则目录
│   ├── novelty_scoring.md   # 新颖性评分
│   ├── style_normalizer_rules.md # 风格规范化规则
│   ├── evaluation_rubric.md # 评估标准
│   ├── prompt_engineering.md # Prompt 工程
│   └── prompt_templates/    # Prompt 模板
│       ├── orchestrator_system.md
│       ├── searcher_system.md
│       ├── reasoner_system.md
│       ├── critic_system.md
│       ├── mentor_system.md
│       └── writer_system.md
│
├── development/             # 开发文档
│   ├── code_style.md        # 代码规范
│   ├── contributing.md      # 贡献指南
│   ├── deployment.md        # 部署指南
│   ├── testing_guide.md     # 测试指南
│   ├── troubleshooting.md   # 故障排查
│   └── faq.md               # 常见问题
│
└── tutorials/               # 教程文档
    ├── getting_started.md   # 入门教程
    ├── advanced_features.md # 高级功能
    ├── admin_guide.md       # 管理员指南
    ├── developer_guide.md   # 开发者指南（本文档）
    ├── api_tutorial.md      # API 教程
    └── model_configuration_guide.md # 模型配置指南
```

## 3.6 config 配置模块

```
config/
├── agents/                  # Agent 配置
│   ├── orchestrator.yaml    # Orchestrator 配置
│   ├── searcher.yaml        # Searcher 配置
│   ├── reasoner.yaml        # Reasoner 配置
│   ├── critic.yaml          # Critic 配置
│   ├── mentor.yaml          # Mentor 配置
│   └── writer.yaml          # Writer 配置
│
├── constraints/             # 约束配置
│   ├── hard_rules.yaml      # 硬规则配置
│   ├── novelty_weights.yaml # 新颖性权重
│   └── style_rules.yaml     # 风格规则
│
├── models.yaml              # 模型注册表
├── routing.yaml             # 路由配置
├── monitoring.yaml          # 监控配置
└── system.yaml              # 系统配置
```

### 3.6.1 配置文件加载顺序

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          配置加载优先级                                      │
│                                                                             │
│  低优先级 ──────────────────────────────────────────────────► 高优先级      │
│                                                                             │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐      │
│  │ 代码内默认  │ -> │ config/*.  │ -> │ data/      │ -> │ .env       │      │
│  │ 值         │    │ yaml       │    │ config.json│    │ 环境变量   │      │
│  └────────────┘    └────────────┘    └────────────┘    └────────────┘      │
│                                                                             │
│  说明：右侧配置覆盖左侧同名配置项                                           │
│  - 代码内默认值：DEFAULT_MODELS 等                                          │
│  - config/*.yaml：项目级配置，提交到 Git                                    │
│  - data/config.json：用户级配置，运行时可修改                               │
│  - .env：环境变量，敏感信息（API Key）                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 3.7 samples 示例模块

```
samples/
├── example_agents.py        # Agent 扩展示例
├── example_constraints.py   # 约束规则扩展示例
└── example_integrations.py  # 第三方集成示例
```

示例代码是学习如何扩展 ThesisMiner 的最佳起点，每个示例都是可运行的完整代码。

---

# 第 4 章 核心模块详解

## 4.1 agents 模块：多 Agent 架构

agents 模块是 ThesisMiner v8.0 的核心，实现了 Claude Code 式的主管理 + 子 Agent 架构。

### 4.1.1 架构总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Multi-Agent 架构总览                                │
│                                                                             │
│                              ┌─────────────────┐                            │
│                              │  Orchestrator   │                            │
│                              │  (主管理 Agent)  │                            │
│                              │  模型: claude-   │                            │
│                              │  sonnet-4.5     │                            │
│                              └────────┬────────┘                            │
│                                       │                                     │
│                    ┌──────────────────┼──────────────────┐                  │
│                    │                  │                  │                  │
│              ┌─────▼─────┐     ┌─────▼─────┐     ┌─────▼─────┐            │
│              │ Searcher  │     │ Reasoner  │     │  Critic   │            │
│              │ (检索)    │     │ (推理)    │     │ (批评)    │            │
│              │ deepseek- │     │ deepseek- │     │ deepseek- │            │
│              │ v3.2      │     │ r2        │     │ r2        │            │
│              └───────────┘     └───────────┘     └───────────┘            │
│                                                                             │
│              ┌─────────────┐           ┌─────────────┐                     │
│              │   Mentor    │           │   Writer    │                     │
│              │  (导师)     │           │  (写作)     │                     │
│              │  gpt-4.1    │           │ claude-     │                     │
│              │            │           │ opus-4.5    │                     │
│              └─────────────┘           └─────────────┘                     │
│                                                                             │
│  每个 Agent 拥有：                                                           │
│  - 独立的 system_prompt（系统提示）                                          │
│  - 独立的 messages 上下文列表                                                │
│  - 独立的 model_id（模型路由）                                               │
│  - 独立的 temperature / max_tokens 参数                                      │
│  - 独立的 capabilities（能力标记）                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.1.2 BaseAgent 抽象基类

所有 Agent 都继承自 `BaseAgent`，该基类定义了 Agent 的核心接口：

```python
# backend/agents/base_agent.py

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class AgentResult:
    """Agent 执行结果

    所有子 Agent 的 run() 方法都应返回此结构，
    便于 Orchestrator 统一汇总与门禁判断。
    """
    agent_id: str
    success: bool
    content: str = ""
    reasoning: str = ""
    data: dict = field(default_factory=dict)
    citations: list = field(default_factory=list)
    token_usage: dict = field(default_factory=dict)
    error: str = ""


class BaseAgent(ABC):
    """Agent 抽象基类

    每个 Agent 维护独立的 messages 上下文列表，
    通过 ai_proxy.call_llm 调用 LLM，使用自己的 model_id 与 system_prompt。
    """

    def __init__(
        self,
        agent_id: str,
        name: str,
        description: str,
        system_prompt: str,
        model_id: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        capabilities: list[str] = None,
    ):
        self.agent_id = agent_id
        self.name = name
        self.description = description
        self.system_prompt = system_prompt
        self.model_id = model_id
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.capabilities = capabilities or []
        # 独立上下文窗口：仅初始化时包含系统提示
        self.messages: list[dict] = [{"role": "system", "content": system_prompt}]

    def reset_context(self):
        """重置上下文，仅保留系统提示"""
        self.messages = [{"role": "system", "content": self.system_prompt}]

    def add_message(self, role: str, content: str):
        """添加消息到上下文"""
        self.messages.append({"role": role, "content": content})

    def get_context(self) -> list[dict]:
        """获取当前上下文（返回副本）"""
        return self.messages.copy()

    @abstractmethod
    async def run(self, input_data: dict) -> AgentResult:
        """执行 Agent 任务（子类必须实现）

        Args:
            input_data: 输入数据，包含任务所需信息

        Returns:
            AgentResult: 执行结果
        """
        pass
```

### 4.1.3 OrchestratorAgent 主管理 Agent

OrchestratorAgent 是系统的「大脑」，负责五阶段流程调度：

```python
# backend/agents/orchestrator.py（核心逻辑）

class OrchestratorAgent(BaseAgent):
    """主管理 Agent

    负责任务分解、阶段调度、门禁控制。
    """

    # 五阶段顺序
    STAGES = ["info_confirm", "creativity", "validation", "generation", "deep_assist"]

    def __init__(self):
        super().__init__(
            agent_id="orchestrator",
            name="Orchestrator",
            description="主管理Agent，调度五阶段流程",
            system_prompt=self._default_system_prompt(),
            model_id=get_step_model("orchestrator"),  # claude-sonnet-4.5
            temperature=0.3,
            max_tokens=4096,
            capabilities=["streaming", "thinking", "web_search"],
        )
        self.current_stage = "info_confirm"
        self.stage_results: dict[str, AgentResult] = {}

    async def run(self, input_data: dict) -> AgentResult:
        """执行五阶段流程"""
        try:
            # 阶段一：信息确权
            if self.current_stage == "info_confirm":
                result = await self._run_info_confirm(input_data)
                self.stage_results["info_confirm"] = result
                if result.success:
                    self.current_stage = "creativity"
                return result

            # 阶段二：创意激发
            elif self.current_stage == "creativity":
                result = await self._run_creativity(input_data)
                self.stage_results["creativity"] = result
                if result.success:
                    self.current_stage = "validation"
                return result

            # 阶段三：校验
            elif self.current_stage == "validation":
                result = await self._run_validation(input_data)
                self.stage_results["validation"] = result
                if result.success:
                    self.current_stage = "generation"
                else:
                    # 校验失败，回退到创意阶段
                    if result.data.get("score", 0) < 60:
                        self.current_stage = "creativity"
                return result

            # 阶段四：生成
            elif self.current_stage == "generation":
                result = await self._run_generation(input_data)
                self.stage_results["generation"] = result
                if result.success:
                    self.current_stage = "deep_assist"
                return result

            # 阶段五：深度辅助
            elif self.current_stage == "deep_assist":
                result = await self._run_deep_assist(input_data)
                self.stage_results["deep_assist"] = result
                return result

        except Exception as e:
            return AgentResult(
                agent_id=self.agent_id,
                success=False,
                error=str(e),
            )
```

### 4.1.4 Agent 注册表

Agent 注册表管理所有已注册的 Agent 实例：

```python
# backend/agents/agent_registry.py

from backend.agents.orchestrator import OrchestratorAgent
from backend.agents.searcher_wrapper import SearcherAgent
from backend.agents.reasoner import ReasonerAgent
from backend.agents.critic import CriticAgent
from backend.agents.mentor_agent import MentorAgent
from backend.agents.proposal_writer import WriterAgent

# Agent 注册表（单例）
_registry: dict[str, BaseAgent] = {}


def register_agent(agent: BaseAgent):
    """注册 Agent 到注册表"""
    _registry[agent.agent_id] = agent


def get_agent(agent_id: str) -> BaseAgent:
    """获取指定 Agent"""
    if agent_id not in _registry:
        raise KeyError(f"Agent '{agent_id}' 未注册")
    return _registry[agent_id]


def list_agents() -> list[dict]:
    """列出所有已注册 Agent 的元数据"""
    return [
        {
            "agent_id": agent.agent_id,
            "name": agent.name,
            "description": agent.description,
            "model_id": agent.model_id,
            "capabilities": agent.capabilities,
        }
        for agent in _registry.values()
    ]


def init_agents():
    """初始化所有 Agent（应用启动时调用）"""
    register_agent(OrchestratorAgent())
    register_agent(SearcherAgent())
    register_agent(ReasonerAgent())
    register_agent(CriticAgent())
    register_agent(MentorAgent())
    register_agent(WriterAgent())
```

### 4.1.5 Agent 间通信

Agent 间通过 `AgentCommunicator` 进行通信，避免直接耦合：

```python
# backend/agents/agent_communicator.py

class AgentCommunicator:
    """Agent 间通信器

    提供 Agent 间的消息传递与结果共享能力，
    避免子 Agent 之间直接耦合。
    """

    def __init__(self):
        self._messages: dict[str, list[dict]] = {}  # agent_id -> messages

    async def send(
        self,
        from_agent: str,
        to_agent: str,
        message: dict,
    ) -> dict:
        """发送消息到目标 Agent

        Args:
            from_agent: 发送方 Agent ID
            to_agent: 接收方 Agent ID
            message: 消息内容

        Returns:
            接收方 Agent 的响应
        """
        # 记录消息
        if to_agent not in self._messages:
            self._messages[to_agent] = []
        self._messages[to_agent].append({
            "from": from_agent,
            "content": message,
        })

        # 调用目标 Agent
        target_agent = get_agent(to_agent)
        result = await target_agent.run(message)
        return result

    def get_messages(self, agent_id: str) -> list[dict]:
        """获取指定 Agent 收到的所有消息"""
        return self._messages.get(agent_id, [])
```

### 4.1.6 Agent 上下文管理

每个 Agent 维护独立的上下文窗口，`AgentContext` 提供上下文管理能力：

```python
# backend/agents/agent_context.py

class AgentContext:
    """Agent 上下文管理器

    管理单个 Agent 的上下文窗口，包括：
    - 消息列表维护
    - 上下文长度控制
    - Token 计数
    - 上下文压缩
    """

    def __init__(self, system_prompt: str, max_tokens: int = 8000):
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self.messages: list[dict] = [
            {"role": "system", "content": system_prompt}
        ]
        self._total_tokens = 0

    def add_user_message(self, content: str):
        """添加用户消息"""
        self.messages.append({"role": "user", "content": content})
        self._update_token_count()

    def add_assistant_message(self, content: str, reasoning: str = ""):
        """添加助手消息"""
        msg = {"role": "assistant", "content": content}
        if reasoning:
            msg["reasoning"] = reasoning
        self.messages.append(msg)
        self._update_token_count()

    def _update_token_count(self):
        """更新 Token 计数（粗略估算：1 字符约 0.3 token）"""
        total_chars = sum(len(m["content"]) for m in self.messages)
        self._total_tokens = int(total_chars * 0.3)

    def needs_compression(self) -> bool:
        """判断是否需要压缩上下文"""
        return self._total_tokens > self.max_tokens * 0.8

    def compress(self, keep_recent: int = 5):
        """压缩上下文，保留最近 N 轮对话"""
        if len(self.messages) <= keep_recent + 1:
            return
        # 保留系统提示 + 最近 N 条消息
        system = self.messages[0]
        recent = self.messages[-(keep_recent * 2):]  # 保留最近 N 轮（user+assistant）
        self.messages = [system] + recent
        self._update_token_count()

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "system_prompt": self.system_prompt,
            "max_tokens": self.max_tokens,
            "messages": self.messages,
            "total_tokens": self._total_tokens,
        }
```

### 4.1.7 各子 Agent 职责详解

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          子 Agent 职责矩阵                                   │
├──────────┬──────────────┬──────────────────┬───────────────────────────────┤
│ Agent    │ 默认模型      │ 职责              │ 输入/输出                     │
├──────────┼──────────────┼──────────────────┼───────────────────────────────┤
│Searcher  │deepseek-v3.2 │ 联网检索文献      │ 输入：关键词/学科             │
│          │              │ 估算文献数量      │ 输出：文献列表+引用+计数      │
├──────────┼──────────────┼──────────────────┼───────────────────────────────┤
│Reasoner  │deepseek-r2   │ 生成候选论题      │ 输入：学位/学科/导师/方向     │
│          │              │ 深度推理分析      │ 输出：论题列表+推理过程       │
├──────────┼──────────────┼──────────────────┼───────────────────────────────┤
│Critic    │deepseek-r2   │ 评估新颖性/可行性 │ 输入：候选论题                │
│          │              │ 打分与改进建议    │ 输出：评分+评语+改进建议      │
├──────────┼──────────────┼──────────────────┼───────────────────────────────┤
│Mentor    │gpt-4.1       │ 模拟导师对话      │ 输入：用户问题+上下文         │
│          │              │ 提供指导建议      │ 输出：导师回复+建议           │
├──────────┼──────────────┼──────────────────┼───────────────────────────────┤
│Writer    │claude-       │ 多粒度内容生成    │ 输入：论题+粒度（标题/摘要/   │
│          │opus-4.5      │ 开题报告撰写      │ 大纲/全文）                   │
│          │              │                  │ 输出：生成内容                │
└──────────┴──────────────┴──────────────────┴───────────────────────────────┘
```

### 4.1.8 SearcherAgent 检索 Agent

```python
# backend/agents/searcher_wrapper.py

class SearcherAgent(BaseAgent):
    """检索 Agent

    负责联网检索学术文献，估算文献数量。
    默认使用 DeepSeek V3.2（支持联网搜索）。
    """

    def __init__(self):
        super().__init__(
            agent_id="searcher",
            name="Searcher",
            description="联网检索学术文献，估算文献数量",
            system_prompt=self._default_system_prompt(),
            model_id=get_step_model("searcher"),  # deepseek-v3.2
            temperature=0.3,
            max_tokens=4096,
            capabilities=["streaming", "web_search"],
        )

    async def run(self, input_data: dict) -> AgentResult:
        """执行检索任务

        Args:
            input_data: 包含 keywords/discipline 等字段

        Returns:
            AgentResult: 包含文献列表与引用
        """
        keywords = input_data.get("keywords", [])
        discipline = input_data.get("discipline", "")

        # 构建检索提示
        prompt = self._build_search_prompt(keywords, discipline)
        self.add_message("user", prompt)

        # 调用 LLM
        from backend.ai.ai_proxy import AIProxy
        proxy = AIProxy()
        response = await proxy.call_llm(
            model_id=self.model_id,
            messages=self.get_context(),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        # 解析引用
        from backend.ai.citation_parser import CitationParser
        parser = CitationParser()
        citations = parser.parse(response["content"])

        # 记录助手响应
        self.add_message("assistant", response["content"])

        return AgentResult(
            agent_id=self.agent_id,
            success=True,
            content=response["content"],
            data={
                "keywords": keywords,
                "result_count": len(citations),
            },
            citations=citations,
            token_usage=response.get("usage", {}),
        )

    async def estimate_literature_count(self, keyword: str) -> dict:
        """估算文献数量

        Args:
            keyword: 检索关键词

        Returns:
            包含 count 与 search_degraded 的字典
        """
        prompt = f"请估算关于「{keyword}」的学术文献数量，返回 JSON 格式：{{\"count\": 数字}}"

        self.add_message("user", prompt)
        from backend.ai.ai_proxy import AIProxy
        proxy = AIProxy()
        response = await proxy.call_llm(
            model_id=self.model_id,
            messages=self.get_context(),
            temperature=0.0,
            max_tokens=256,
        )
        self.add_message("assistant", response["content"])

        # 解析 JSON 响应
        import json
        try:
            data = json.loads(response["content"])
            return {
                "count": data.get("count", 0),
                "search_degraded": False,
            }
        except json.JSONDecodeError:
            return {
                "count": 0,
                "search_degraded": True,
            }

    def _build_search_prompt(self, keywords: list, discipline: str) -> str:
        """构建检索提示"""
        kw_str = "、".join(keywords)
        return (
            f"请检索以下领域的最新学术文献：\n"
            f"学科：{discipline}\n"
            f"关键词：{kw_str}\n"
            f"要求：\n"
            f"1. 检索近 2 年的高质量文献\n"
            f"2. 每条文献包含标题、作者、年份、摘要\n"
            f"3. 在文献末尾标注引用来源 URL\n"
            f"4. 返回至少 5 条相关文献"
        )

    @staticmethod
    def _default_system_prompt() -> str:
        return """你是 ThesisMiner 的检索 Agent（Searcher）。

你的职责：
1. 根据用户的研究方向，联网检索最新学术文献
2. 估算特定关键词的文献数量
3. 提供文献的引用来源（URL）

输出格式要求：
- 每条文献包含：标题、作者、年份、摘要、URL
- 在文献列表末尾，使用 [1] [2] 等编号标注引用
- 估算文献数量时，返回 JSON 格式

注意：
- 优先检索近 2 年的文献
- 优先检索高质量期刊与会议
- 如果无法联网，明确告知用户"""
```

### 4.1.9 ReasonerAgent 推理 Agent

```python
# backend/agents/reasoner.py

class ReasonerAgent(BaseAgent):
    """推理 Agent

    负责生成候选论题与深度推理分析。
    默认使用 DeepSeek R2（支持深度思考链）。
    """

    def __init__(self):
        super().__init__(
            agent_id="reasoner",
            name="Reasoner",
            description="生成候选论题，深度推理分析",
            system_prompt=self._default_system_prompt(),
            model_id=get_step_model("reasoner"),  # deepseek-r2
            temperature=0.0,
            max_tokens=8192,
            capabilities=["streaming", "thinking"],
        )

    async def run(self, input_data: dict) -> AgentResult:
        """执行推理任务

        Args:
            input_data: 包含 degree/discipline/mentor_info/direction 等字段

        Returns:
            AgentResult: 包含候选论题列表
        """
        degree = input_data.get("degree", "master")
        discipline = input_data.get("discipline", "")
        mentor_info = input_data.get("mentor_info", "")
        direction = input_data.get("research_direction", "")
        count = input_data.get("count", 5)

        # 构建推理提示
        prompt = self._build_reasoning_prompt(
            degree, discipline, mentor_info, direction, count
        )
        self.add_message("user", prompt)

        # 调用 LLM（启用思考链）
        from backend.ai.ai_proxy import AIProxy
        proxy = AIProxy()
        response = await proxy.call_llm(
            model_id=self.model_id,
            messages=self.get_context(),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        # 解析候选论题
        proposals = self._parse_proposals(response["content"])

        self.add_message("assistant", response["content"])

        return AgentResult(
            agent_id=self.agent_id,
            success=True,
            content=response["content"],
            reasoning=response.get("reasoning", ""),
            data={
                "proposals": proposals,
                "count": len(proposals),
            },
            token_usage=response.get("usage", {}),
        )

    def _build_reasoning_prompt(
        self,
        degree: str,
        discipline: str,
        mentor_info: str,
        direction: str,
        count: int,
    ) -> str:
        """构建推理提示"""
        return (
            f"请基于以下信息生成 {count} 个候选论题：\n"
            f"学位：{degree}\n"
            f"学科：{discipline}\n"
            f"导师信息：{mentor_info}\n"
            f"研究方向：{direction}\n\n"
            f"要求：\n"
            f"1. 每个论题包含：标题、研究意义、研究内容、预期成果\n"
            f"2. 标题必须包含「研究」关键词\n"
            f"3. 研究周期不超过学位年限（硕士1年/博士2年）\n"
            f"4. 论题之间具有差异性，避免雷同\n"
            f"5. 返回 JSON 数组格式"
        )

    def _parse_proposals(self, content: str) -> list[dict]:
        """解析候选论题"""
        import json
        try:
            # 尝试直接解析 JSON
            data = json.loads(content)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "proposals" in data:
                return data["proposals"]
        except json.JSONDecodeError:
            pass

        # 如果不是 JSON，返回空列表
        # 实际实现中会使用更复杂的解析逻辑
        return []

    @staticmethod
    def _default_system_prompt() -> str:
        return """你是 ThesisMiner 的推理 Agent（Reasoner）。

你的职责：
1. 基于用户信息生成多个候选论题
2. 对每个论题进行深度推理分析
3. 确保论题的可行性与创新性

输出格式要求：
- 返回 JSON 数组，每个元素包含：
  - title: 论题标题（必须包含"研究"）
  - research_significance: 研究意义
  - research_content: 研究内容（数组）
  - expected_outcome: 预期成果
  - timeframe_months: 预计研究周期（月）

注意：
- 标题必须包含"研究"关键词
- 研究周期不超过学位年限
- 论题之间具有差异性
- 优先考虑创新性与可行性"""
```

### 4.1.10 CriticAgent 批评 Agent

```python
# backend/agents/critic.py

class CriticAgent(BaseAgent):
    """批评 Agent

    负责评估候选论题的新颖性与可行性，提供打分与改进建议。
    默认使用 DeepSeek R2（支持深度思考链）。
    """

    def __init__(self):
        super().__init__(
            agent_id="critic",
            name="Critic",
            description="评估新颖性/可行性，打分与改进建议",
            system_prompt=self._default_system_prompt(),
            model_id=get_step_model("critic"),  # deepseek-r2
            temperature=0.0,
            max_tokens=8192,
            capabilities=["streaming", "thinking"],
        )

    async def run(self, input_data: dict) -> AgentResult:
        """执行批评任务

        Args:
            input_data: 包含 proposals 列表

        Returns:
            AgentResult: 包含评分与改进建议
        """
        proposals = input_data.get("proposals", [])

        # 构建批评提示
        prompt = self._build_critic_prompt(proposals)
        self.add_message("user", prompt)

        # 调用 LLM
        from backend.ai.ai_proxy import AIProxy
        proxy = AIProxy()
        response = await proxy.call_llm(
            model_id=self.model_id,
            messages=self.get_context(),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        # 解析评分结果
        evaluations = self._parse_evaluations(response["content"])

        # 计算总体评分
        total_score = sum(e.get("score", 0) for e in evaluations) / max(len(evaluations), 1)

        self.add_message("assistant", response["content"])

        return AgentResult(
            agent_id=self.agent_id,
            success=total_score >= 60,
            content=response["content"],
            reasoning=response.get("reasoning", ""),
            data={
                "evaluations": evaluations,
                "score": total_score,
                "should_rollback": total_score < 60,
            },
            token_usage=response.get("usage", {}),
        )

    def _build_critic_prompt(self, proposals: list[dict]) -> str:
        """构建批评提示"""
        import json
        proposals_str = json.dumps(proposals, ensure_ascii=False, indent=2)
        return (
            f"请评估以下候选论题的新颖性与可行性：\n\n"
            f"{proposals_str}\n\n"
            f"评估维度：\n"
            f"1. 新颖性（0-100分）：论题是否具有创新性\n"
            f"2. 可行性（0-100分）：论题是否可在学位年限内完成\n"
            f"3. 规范性（0-100分）：标题格式是否符合学术规范\n"
            f"4. 综合评分（0-100分）：加权平均分\n\n"
            f"请返回 JSON 数组，每个元素包含：\n"
            f"- title: 论题标题\n"
            f"- novelty_score: 新颖性评分\n"
            f"- feasibility_score: 可行性评分\n"
            f"- format_score: 规范性评分\n"
            f"- score: 综合评分\n"
            f"- comments: 评语\n"
            f"- suggestions: 改进建议（数组）"
        )

    def _parse_evaluations(self, content: str) -> list[dict]:
        """解析评估结果"""
        import json
        try:
            data = json.loads(content)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
        return []

    @staticmethod
    def _default_system_prompt() -> str:
        return """你是 ThesisMiner 的批评 Agent（Critic）。

你的职责：
1. 评估候选论题的新颖性、可行性、规范性
2. 对每个论题打分（0-100分）
3. 提供具体的改进建议

评分标准：
- 90-100：优秀，强烈推荐
- 80-89：良好，推荐
- 70-79：一般，可改进
- 60-69：及格，需修改
- 0-59：不及格，需重新生成

注意：
- 评分要客观公正
- 改进建议要具体可操作
- 如果论题存在硬规则违反，直接给低分"""
```

### 4.1.11 MentorAgent 导师 Agent

```python
# backend/agents/mentor_agent.py

class MentorAgent(BaseAgent):
    """导师 Agent

    负责模拟导师对话，提供指导建议。
    默认使用 GPT-4.1（高质量通用模型）。
    """

    def __init__(self):
        super().__init__(
            agent_id="mentor",
            name="Mentor",
            description="模拟导师对话，提供指导建议",
            system_prompt=self._default_system_prompt(),
            model_id=get_step_model("mentor"),  # gpt-4.1
            temperature=0.7,
            max_tokens=4096,
            capabilities=["streaming"],
        )

    async def run(self, input_data: dict) -> AgentResult:
        """执行导师对话

        Args:
            input_data: 包含 user_message 与 context

        Returns:
            AgentResult: 包含导师回复
        """
        user_message = input_data.get("user_message", "")
        context = input_data.get("context", {})

        # 构建上下文感知的提示
        prompt = self._build_mentor_prompt(user_message, context)
        self.add_message("user", prompt)

        # 调用 LLM
        from backend.ai.ai_proxy import AIProxy
        proxy = AIProxy()
        response = await proxy.call_llm(
            model_id=self.model_id,
            messages=self.get_context(),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        self.add_message("assistant", response["content"])

        return AgentResult(
            agent_id=self.agent_id,
            success=True,
            content=response["content"],
            data={
                "context": context,
            },
            token_usage=response.get("usage", {}),
        )

    def _build_mentor_prompt(self, user_message: str, context: dict) -> str:
        """构建导师对话提示"""
        context_str = ""
        if context:
            context_str = (
                f"\n[当前上下文]\n"
                f"学位：{context.get('degree', '未知')}\n"
                f"学科：{context.get('discipline', '未知')}\n"
                f"导师：{context.get('mentor', '未知')}\n"
                f"方向：{context.get('direction', '未知')}\n"
                f"阶段：{context.get('stage', '未知')}\n"
            )
        return f"{context_str}\n[学生问题]\n{user_message}"

    @staticmethod
    def _default_system_prompt() -> str:
        return """你是 ThesisMiner 的导师 Agent（Mentor）。

你的角色是一位经验丰富的研究生导师，擅长：
1. 指导学生选择研究方向
2. 帮助学生完善研究方案
3. 提供学术写作建议
4. 解答研究方法问题

对话风格：
- 鼓励式引导，而非命令式
- 提出启发性问题，引导学生思考
- 结合学生背景给出针对性建议
- 必要时指出问题，但态度温和

注意：
- 始终以导师身份回答
- 回答要专业但易懂
- 如果学生问题不明确，主动追问
- 结合当前对话上下文给出建议"""
```

### 4.1.12 WriterAgent 写作 Agent

```python
# backend/agents/proposal_writer.py

class WriterAgent(BaseAgent):
    """写作 Agent

    负责多粒度内容生成与开题报告撰写。
    默认使用 Claude Opus 4.5（顶级质量模型）。
    """

    def __init__(self):
        super().__init__(
            agent_id="writer",
            name="Writer",
            description="多粒度内容生成，开题报告撰写",
            system_prompt=self._default_system_prompt(),
            model_id=get_step_model("report"),  # claude-opus-4.5
            temperature=0.7,
            max_tokens=16384,
            capabilities=["streaming", "thinking"],
        )

    async def run(self, input_data: dict) -> AgentResult:
        """执行写作任务

        Args:
            input_data: 包含 proposal 与 granularity

        Returns:
            AgentResult: 包含生成内容
        """
        proposal = input_data.get("proposal", {})
        granularity = input_data.get("granularity", "full_text")  # title/abstract/outline/full_text

        # 构建写作提示
        prompt = self._build_writing_prompt(proposal, granularity)
        self.add_message("user", prompt)

        # 调用 LLM
        from backend.ai.ai_proxy import AIProxy
        proxy = AIProxy()
        response = await proxy.call_llm(
            model_id=self.model_id,
            messages=self.get_context(),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        self.add_message("assistant", response["content"])

        return AgentResult(
            agent_id=self.agent_id,
            success=True,
            content=response["content"],
            data={
                "granularity": granularity,
                "proposal_title": proposal.get("title", ""),
            },
            token_usage=response.get("usage", {}),
        )

    def _build_writing_prompt(self, proposal: dict, granularity: str) -> str:
        """构建写作提示"""
        import json
        proposal_str = json.dumps(proposal, ensure_ascii=False, indent=2)

        granularity_map = {
            "title": "仅生成论题标题（10-30字）",
            "abstract": "生成摘要（300-500字）",
            "outline": "生成详细大纲（含一级/二级标题）",
            "full_text": "生成完整开题报告（含所有章节）",
        }

        requirement = granularity_map.get(granularity, "生成完整开题报告")

        return (
            f"请基于以下论题信息生成内容：\n\n"
            f"{proposal_str}\n\n"
            f"生成要求：{requirement}\n\n"
            f"格式规范：\n"
            f"- 使用学术写作风格\n"
            f"- 避免使用模板化词汇（深入/全面/系统/高效等）\n"
            f"- 引用文献时使用 [1] [2] 编号格式\n"
            f"- 段落之间逻辑清晰，过渡自然"
        )

    @staticmethod
    def _default_system_prompt() -> str:
        return """你是 ThesisMiner 的写作 Agent（Writer）。

你的职责：
1. 基于论题信息生成多粒度内容（标题/摘要/大纲/全文）
2. 撰写高质量的开题报告
3. 确保内容符合学术规范

写作规范：
- 使用学术写作风格，避免口语化
- 禁止使用模板化词汇：深入、全面、系统、高效、精准、智能
- 段落之间逻辑清晰，使用过渡句
- 引用文献使用 [1] [2] 编号格式
- 标题简洁明了，包含"研究"关键词

开题报告结构（全文模式）：
1. 选题依据（研究背景与意义）
2. 文献综述（国内外研究现状）
3. 研究内容与目标
4. 研究方法与技术路线
5. 预期成果与创新点
6. 研究进度安排
7. 参考文献

注意：
- 内容要具体，避免空泛
- 方法要可操作，避免泛泛而谈
- 进度安排要合理，符合学位年限"""
```

## 4.2 sessions 模块：会话与对话管理

sessions 模块负责管理用户会话与对话，支持单会话多对话的上下文隔离。

### 4.2.1 会话与对话的关系

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          会话与对话层级关系                                  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Session（会话）                               │   │
│  │  ID: sess_xxx                                                       │   │
│  │  学位：硕士 / 博士                                                   │   │
│  │  学科：计算机科学                                                    │   │
│  │  导师：张教授                                                        │   │
│  │  研究方向：大语言模型                                                │   │
│  │                                                                     │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │ Conversation │  │ Conversation │  │ Conversation │              │   │
│  │  │  (对话 1)    │  │  (对话 2)    │  │  (对话 3)    │              │   │
│  │  │  标题：论题  │  │  标题：文献  │  │  标题：答辩  │              │   │
│  │  │  Agent:      │  │  Agent:      │  │  Agent:      │              │   │
│  │  │  orchestrator│  │  searcher    │  │  mentor      │              │   │
│  │  │              │  │              │  │              │              │   │
│  │  │ ┌──────────┐│  │ ┌──────────┐│  │ ┌──────────┐│              │   │
│  │  │ │ Message 1││  │ │ Message 1││  │ │ Message 1││              │   │
│  │  │ │ Message 2││  │ │ Message 2││  │ │ Message 2││              │   │
│  │  │ │ Message 3││  │ │ Message 3││  │ │ ...      ││              │   │
│  │  │ │ ...      ││  │ │ ...      ││  │ └──────────┘│              │   │
│  │  │ └──────────┘│  │ └──────────┘│  │              │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  │                                                                     │   │
│  │  激活对话：Conversation 1                                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  特点：                                                                      │
│  - 一个会话可有多个对话                                                     │
│  - 每个对话独立维护消息列表                                                 │
│  - 对话间上下文隔离                                                         │
│  - 同一时刻只有一个激活对话                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2.2 SessionManager 会话管理器

```python
# backend/sessions/session_manager.py

class SessionManager:
    """会话管理器

    负责会话的 CRUD 操作，所有持久化通过 database 模块完成。
    """

    def create_session(self, req: SessionCreate) -> dict:
        """创建新会话

        Args:
            req: 会话创建请求，包含学位/学科/导师/研究方向

        Returns:
            新建的会话字典
        """
        session_id = f"sess_{uuid.uuid4().hex[:16]}"
        now = datetime.datetime.now().isoformat()

        session = {
            "id": session_id,
            "degree": req.degree,
            "discipline": req.discipline,
            "mentor_info": req.mentor_info,
            "research_direction": req.research_direction,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }

        execute_insert("sessions", session)
        return session

    def get_session(self, session_id: str) -> dict | None:
        """获取会话详情"""
        return fetch_one(
            "SELECT * FROM sessions WHERE id = ?",
            (session_id,),
        )

    def list_sessions(self, limit: int = 20, offset: int = 0) -> list[dict]:
        """分页查询会话列表"""
        return fetch_all(
            "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )

    def delete_session(self, session_id: str):
        """删除会话（级联删除对话与消息）"""
        # 先删除消息
        execute_query(
            "DELETE FROM conversation_messages WHERE conversation_id IN "
            "(SELECT id FROM conversations WHERE session_id = ?)",
            (session_id,),
        )
        # 再删除对话
        execute_query(
            "DELETE FROM conversations WHERE session_id = ?",
            (session_id,),
        )
        # 最后删除会话
        execute_query(
            "DELETE FROM sessions WHERE id = ?",
            (session_id,),
        )

    def update_session_status(self, session_id: str, status: str):
        """更新会话状态"""
        execute_query(
            "UPDATE sessions SET status = ?, updated_at = ? WHERE id = ?",
            (status, datetime.datetime.now().isoformat(), session_id),
        )
```

### 4.2.3 ConversationManager 对话管理器

```python
# backend/sessions/conversation_manager.py

class ConversationManager:
    """对话管理器

    管理会话下的多个对话，每个对话独立维护消息列表。
    """

    def create_conversation(
        self,
        session_id: str,
        title: str = "新对话",
        agent_id: str = "orchestrator",
    ) -> dict:
        """在指定会话下创建新对话"""
        conv_id = f"conv_{uuid.uuid4().hex[:16]}"
        now = datetime.datetime.now().isoformat()

        conv = {
            "id": conv_id,
            "session_id": session_id,
            "title": title,
            "agent_id": agent_id,
            "created_at": now,
            "updated_at": now,
        }

        execute_insert("conversations", conv)
        return conv

    def list_conversations(self, session_id: str) -> list[dict]:
        """列出指定会话下的所有对话"""
        return fetch_all(
            "SELECT * FROM conversations WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        )

    def get_messages(self, conversation_id: str, limit: int = 100) -> list[dict]:
        """获取对话的消息列表"""
        return fetch_all(
            "SELECT * FROM conversation_messages "
            "WHERE conversation_id = ? ORDER BY id LIMIT ?",
            (conversation_id, limit),
        )

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        agent_id: str = "",
        reasoning: str = "",
        search_results: list = None,
        token_usage: dict = None,
        citations: list = None,
    ) -> dict:
        """添加消息到对话"""
        msg_id = f"msg_{uuid.uuid4().hex[:16]}"
        now = datetime.datetime.now().isoformat()

        msg = {
            "id": msg_id,
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "agent_id": agent_id,
            "reasoning": reasoning,
            "search_results": json.dumps(search_results or [], ensure_ascii=False),
            "token_usage": json.dumps(token_usage or {}, ensure_ascii=False),
            "created_at": now,
        }

        execute_insert("conversation_messages", msg)

        # 保存引用
        if citations:
            for cite in citations:
                cite["message_id"] = msg_id
                execute_insert("search_citations", cite)

        return msg

    def get_context_window(
        self,
        conversation_id: str,
        max_tokens: int = 8000,
    ) -> list[dict]:
        """获取对话的上下文窗口（含 DST 压缩）"""
        messages = self.get_messages(conversation_id, limit=500)

        # 如果消息过多，使用 DST 压缩
        total_chars = sum(len(m["content"]) for m in messages)
        estimated_tokens = int(total_chars * 0.3)

        if estimated_tokens > max_tokens:
            # 使用 DST 压缩器压缩上下文
            compactor = DSTCompactor()
            messages = compactor.compact(messages, max_tokens)

        return messages
```

### 4.2.4 DialogueStateTracker 对话状态追踪

DST（Dialogue State Tracker）负责追踪对话状态并在上下文过长时进行压缩：

```python
# backend/sessions/dialogue_state_tracker.py

class DialogueStateTracker:
    """对话状态追踪器

    追踪对话中的关键状态信息，包括：
    - 用户基本信息（学位/学科/导师/方向）
    - 当前阶段
    - 已生成的论题
    - 校验结果
    - 用户偏好

    在上下文压缩时，保留状态摘要而非完整历史。
    """

    def __init__(self):
        self.state: dict = {
            "user_info": {},
            "current_stage": "info_confirm",
            "proposals": [],
            "validation_results": [],
            "preferences": {},
        }

    def update(self, key: str, value):
        """更新状态"""
        self.state[key] = value

    def get(self, key: str, default=None):
        """获取状态"""
        return self.state.get(key, default)

    def to_summary(self) -> str:
        """生成状态摘要（用于上下文压缩）"""
        lines = ["[对话状态摘要]"]

        if self.state["user_info"]:
            info = self.state["user_info"]
            lines.append(f"学位：{info.get('degree', '未知')}")
            lines.append(f"学科：{info.get('discipline', '未知')}")
            lines.append(f"导师：{info.get('mentor', '未知')}")
            lines.append(f"方向：{info.get('direction', '未知')}")

        lines.append(f"当前阶段：{self.state['current_stage']}")

        if self.state["proposals"]:
            lines.append(f"已生成论题数：{len(self.state['proposals'])}")
            for i, p in enumerate(self.state["proposals"][-3:], 1):  # 仅保留最近 3 个
                lines.append(f"  论题{i}：{p.get('title', '无标题')}")

        if self.state["validation_results"]:
            latest = self.state["validation_results"][-1]
            lines.append(f"最新校验评分：{latest.get('score', '未评分')}")

        return "\n".join(lines)
```

### 4.2.5 DSTCompactor 上下文压缩器

```python
# backend/sessions/dst_compactor.py

class DSTCompactor:
    """DST 上下文压缩器

    当对话历史超过上下文窗口时，使用 DST 摘要替代早期消息，
    保留最近 N 轮对话的完整内容。
    """

    def compact(
        self,
        messages: list[dict],
        max_tokens: int = 8000,
        keep_recent: int = 6,
    ) -> list[dict]:
        """压缩对话历史

        Args:
            messages: 原始消息列表
            max_tokens: 最大 Token 数
            keep_recent: 保留最近 N 条消息（不压缩）

        Returns:
            压缩后的消息列表
        """
        if len(messages) <= keep_recent + 1:
            return messages

        # 分离系统消息
        system_msgs = [m for m in messages if m["role"] == "system"]
        non_system = [m for m in messages if m["role"] != "system"]

        # 保留最近 N 条消息
        recent = non_system[-keep_recent:]
        old = non_system[:-keep_recent]

        # 将旧消息压缩为摘要
        summary = self._summarize(old)

        # 构建压缩后的消息列表
        compacted = system_msgs + [
            {"role": "system", "content": f"[历史摘要]\n{summary}"},
            *recent,
        ]

        return compacted

    def _summarize(self, messages: list[dict]) -> str:
        """将消息列表压缩为摘要"""
        lines = [f"共 {len(messages)} 条历史消息，摘要如下："]

        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            # 截取每条消息的前 100 字符
            preview = content[:100] + ("..." if len(content) > 100 else "")
            lines.append(f"[{role}] {preview}")

        return "\n".join(lines)
```

## 4.3 constraints 模块：约束引擎

constraints 模块是 ThesisMiner 的「质量守门员」，通过硬规则与软规则确保输出规范性。

### 4.3.1 约束引擎架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          约束引擎架构                                        │
│                                                                             │
│                          ┌──────────────────┐                               │
│                          │   RuleEngine     │                               │
│                          │   (规则引擎)      │                               │
│                          └────────┬─────────┘                               │
│                                   │                                         │
│              ┌────────────────────┼────────────────────┐                    │
│              │                    │                    │                    │
│       ┌──────▼──────┐     ┌──────▼──────┐     ┌──────▼──────┐             │
│       │  HardRules  │     │  SoftRules  │     │ StageGate   │             │
│       │  (硬规则)    │     │  (软规则)    │     │ (阶段门禁)  │             │
│       └──────┬──────┘     └──────┬──────┘     └──────┬──────┘             │
│              │                    │                    │                    │
│    ┌─────────┴─────────┐         │                    │                    │
│    │                   │         │                    │                    │
│ ┌──▼──────────┐  ┌─────▼─────┐  │                    │                    │
│ │Format       │  │Academic   │  │                    │                    │
│ │Validator    │  │Calendar   │  │                    │                    │
│ │(格式校验)    │  │(学术日历) │  │                    │                    │
│ └─────────────┘  └───────────┘  │                    │                    │
│                                                                             │
│ ┌─────────────┐  ┌───────────┐  ┌─────────────┐  ┌─────────────┐         │
│ │LitBaselines │  │Novelty    │  │Plagiarism   │  │Style        │         │
│ │(文献基线)    │  │Checker    │  │Checker      │  │Normalizer   │         │
│ │             │  │(新颖性)   │  │(抄袭检查)    │  │(风格规范化) │         │
│ └─────────────┘  └───────────┘  └─────────────┘  └─────────────┘         │
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────┐   │
│ │                        MultiGranularity                             │   │
│ │                        (多粒度生成)                                  │   │
│ └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.3.2 硬规则 vs 软规则

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          硬规则 vs 软规则                                    │
├──────────────────┬──────────────────────────┬──────────────────────────────┤
│ 维度              │ 硬规则（Hard Rules）      │ 软规则（Soft Rules）          │
├──────────────────┼──────────────────────────┼──────────────────────────────┤
│ 严重程度          │ 阻断性（必须满足）        │ 提示性（建议满足）            │
├──────────────────┼──────────────────────────┼──────────────────────────────┤
│ 违反后果          │ 抛出异常，阻断流程        │ 记录警告，流程继续            │
├──────────────────┼──────────────────────────┼──────────────────────────────┤
│ 典型规则          │ - 标题必须包含"研究"      │ - 建议引用近 3 年文献          │
│                  │ - 时间节点不可超期        │ - 建议文献数 >= 30 篇         │
│                  │ - 学位必须为硕士/博士     │ - 建议避免使用"显著"等词      │
├──────────────────┼──────────────────────────┼──────────────────────────────┤
│ 配置位置          │ config/constraints/      │ config/constraints/          │
│                  │ hard_rules.yaml          │ style_rules.yaml             │
├──────────────────┼──────────────────────────┼──────────────────────────────┤
│ 实现类            │ HardRules                │ SoftRules / StyleNormalizer  │
├──────────────────┼──────────────────────────┼──────────────────────────────┤
│ 触发时机          │ 生成后立即校验            │ 生成后异步校验                │
└──────────────────┴──────────────────────────┴──────────────────────────────┘
```

### 4.3.3 RuleEngine 规则引擎

```python
# backend/constraints/rule_engine.py

from backend.constraints.hard_rules import HardRules
from backend.constraints.format_validator import FormatValidator
from backend.constraints.academic_calendar import AcademicCalendar
from backend.constraints.lit_baselines import LiteratureBaselines
from backend.constraints.novelty_checker import NoveltyChecker
from backend.constraints.plagiarism_checker import PlagiarismChecker
from backend.constraints.style_normalizer import StyleNormalizer


class RuleEngine:
    """规则引擎

    统一管理所有约束规则，提供批量校验能力。
    """

    def __init__(self):
        self.hard_rules = HardRules()
        self.format_validator = FormatValidator()
        self.academic_calendar = AcademicCalendar()
        self.lit_baselines = LiteratureBaselines()
        self.novelty_checker = NoveltyChecker()
        self.plagiarism_checker = PlagiarismChecker()
        self.style_normalizer = StyleNormalizer()

    def validate_proposal(self, proposal: dict, degree: str) -> dict:
        """校验论题（硬规则 + 软规则）

        Args:
            proposal: 论题字典
            degree: 学位（master/doctor）

        Returns:
            校验结果字典
        """
        results = {
            "passed": True,
            "hard_rule_violations": [],
            "soft_rule_warnings": [],
            "score": 100,
        }

        # 1. 硬规则校验（阻断性）
        try:
            self.hard_rules.validate_title_format(proposal.get("title", ""))
        except HardRuleViolation as e:
            results["hard_rule_violations"].append(str(e))
            results["passed"] = False
            results["score"] -= 30

        try:
            self.hard_rules.validate_degree(degree)
        except HardRuleViolation as e:
            results["hard_rule_violations"].append(str(e))
            results["passed"] = False
            results["score"] -= 20

        # 2. 格式校验
        format_result = self.format_validator.validate_and_rewrite(
            proposal.get("title", "")
        )
        if not format_result["valid"]:
            results["soft_rule_warnings"].append(format_result["message"])
            results["score"] -= 10

        # 3. 学术日历校验
        if proposal.get("timeframe_months"):
            cal_result = self.academic_calendar.validate_timeframe(
                degree, proposal["timeframe_months"]
            )
            if not cal_result["feasible"]:
                results["hard_rule_violations"].append(cal_result["message"])
                results["passed"] = False
                results["score"] -= 25

        # 4. 新颖性检查
        novelty_score = self.novelty_checker.check(proposal)
        results["novelty_score"] = novelty_score
        if novelty_score < 60:
            results["soft_rule_warnings"].append(
                f"新颖性评分较低：{novelty_score}/100"
            )
            results["score"] -= 15

        # 5. 抄袭检查
        plagiarism_score = self.plagiarism_checker.check(proposal)
        results["plagiarism_score"] = plagiarism_score
        if plagiarism_score > 30:
            results["hard_rule_violations"].append(
                f"抄袭风险过高：{plagiarism_score}%"
            )
            results["passed"] = False
            results["score"] -= 40

        results["score"] = max(0, results["score"])
        return results
```

### 4.3.4 FormatValidator 格式校验器

```python
# backend/constraints/format_validator.py

import re


class FormatValidator:
    """标题格式校验器

    校验论题标题是否符合学术规范，并提供自动重写建议。
    """

    # 标题必须包含的关键词
    REQUIRED_KEYWORDS = ["研究", "分析", "设计", "实现", "评估", "探索"]

    # 禁止使用的模板化词汇
    TEMPLATE_WORDS = [
        "深入", "全面", "系统", "高效", "精准", "智能",
        "新型", "创新", "先进", "前沿",
    ]

    # 标题长度范围
    MIN_LENGTH = 8
    MAX_LENGTH = 50

    def validate_and_rewrite(self, title: str) -> dict:
        """校验标题格式并自动重写

        Args:
            title: 原始标题

        Returns:
            校验结果，包含 valid/message/rewritten_title
        """
        result = {
            "valid": True,
            "message": "",
            "original_title": title,
            "rewritten_title": title,
        }

        # 1. 长度校验
        if len(title) < self.MIN_LENGTH:
            result["valid"] = False
            result["message"] = f"标题过短，建议 {self.MIN_LENGTH}-{self.MAX_LENGTH} 字"
            return result

        if len(title) > self.MAX_LENGTH:
            result["valid"] = False
            result["message"] = f"标题过长，建议 {self.MIN_LENGTH}-{self.MAX_LENGTH} 字"
            return result

        # 2. 关键词校验
        has_keyword = any(kw in title for kw in self.REQUIRED_KEYWORDS)
        if not has_keyword:
            result["valid"] = False
            result["message"] = (
                f"标题应包含研究性关键词：{', '.join(self.REQUIRED_KEYWORDS)}"
            )
            # 自动重写：在末尾添加"研究"
            result["rewritten_title"] = f"{title}研究"
            return result

        # 3. 模板化词汇检测
        used_templates = [w for w in self.TEMPLATE_WORDS if w in title]
        if used_templates:
            result["valid"] = False
            result["message"] = (
                f"标题包含模板化词汇：{', '.join(used_templates)}，建议替换为具体描述"
            )
            # 自动重写：移除模板化词汇
            rewritten = title
            for word in used_templates:
                rewritten = rewritten.replace(word, "")
            result["rewritten_title"] = rewritten
            return result

        return result
```

### 4.3.5 AcademicCalendar 学术日历

```python
# backend/constraints/academic_calendar.py

class AcademicCalendar:
    """学术日历

    根据学位类型校验研究时间周期的可行性。
    """

    # 学位对应的最大年限
    CALENDAR = {
        "master": {"max_years": 1, "description": "硕士1年内出结果"},
        "doctor": {"max_years": 2, "description": "博士2年内出结果"},
    }

    def validate_timeframe(self, degree: str, months: int) -> dict:
        """校验研究周期可行性

        Args:
            degree: 学位（master/doctor）
            months: 预计研究周期（月）

        Returns:
            校验结果，包含 feasible/message/max_months
        """
        if degree not in self.CALENDAR:
            return {
                "feasible": False,
                "message": f"未知学位类型：{degree}",
                "max_months": 0,
            }

        max_years = self.CALENDAR[degree]["max_years"]
        max_months = max_years * 12

        if months > max_months:
            return {
                "feasible": False,
                "message": (
                    f"研究周期 {months} 个月超过 {degree} 学位上限 "
                    f"{max_months} 个月（{max_years} 年）"
                ),
                "max_months": max_months,
                "actual_months": months,
            }

        return {
            "feasible": True,
            "message": f"研究周期 {months} 个月在 {degree} 学位允许范围内",
            "max_months": max_months,
            "actual_months": months,
        }
```

### 4.3.6 StageGate 阶段门禁

```python
# backend/constraints/stage_gate.py

class StageGate:
    """阶段门禁

    控制五阶段流程的阶段间转换，确保每阶段输出质量达标后才进入下一阶段。
    """

    # 各阶段的通过阈值
    THRESHOLDS = {
        "info_confirm": {"min_completeness": 0.8},
        "creativity": {"min_candidate_count": 3, "min_novelty_score": 50},
        "validation": {"min_score": 60, "max_plagiarism": 30},
        "generation": {"min_completeness": 0.9},
        "deep_assist": {},
    }

    def check_gate(
        self,
        stage: str,
        result: dict,
    ) -> dict:
        """检查阶段门禁

        Args:
            stage: 阶段名称
            result: 阶段执行结果

        Returns:
            门禁检查结果，包含 passed/message
        """
        threshold = self.THRESHOLDS.get(stage, {})

        if stage == "info_confirm":
            completeness = result.get("completeness", 0)
            if completeness < threshold["min_completeness"]:
                return {
                    "passed": False,
                    "message": (
                        f"信息完整度 {completeness:.0%} 低于阈值 "
                        f"{threshold['min_completeness']:.0%}"
                    ),
                }

        elif stage == "creativity":
            candidates = result.get("candidates", [])
            if len(candidates) < threshold["min_candidate_count"]:
                return {
                    "passed": False,
                    "message": (
                        f"候选论题数 {len(candidates)} 少于阈值 "
                        f"{threshold['min_candidate_count']}"
                    ),
                }

        elif stage == "validation":
            score = result.get("score", 0)
            plagiarism = result.get("plagiarism_score", 0)
            if score < threshold["min_score"]:
                return {
                    "passed": False,
                    "message": f"校验评分 {score} 低于阈值 {threshold['min_score']}",
                    "should_rollback": True,
                    "rollback_to": "creativity",
                }
            if plagiarism > threshold["max_plagiarism"]:
                return {
                    "passed": False,
                    "message": (
                        f"抄袭风险 {plagiarism}% 超过阈值 "
                        f"{threshold['max_plagiarism']}%"
                    ),
                    "should_rollback": True,
                    "rollback_to": "creativity",
                }

        return {"passed": True, "message": "门禁通过"}
```

## 4.4 orchestration 模块：编排与状态机

orchestration 模块负责五阶段流程的编排调度与状态管理。

### 4.4.1 状态机

```python
# backend/orchestration/state_machine.py

from enum import Enum


class Stage(str, Enum):
    """五阶段枚举"""
    INFO_CONFIRM = "info_confirm"
    CREATIVITY = "creativity"
    VALIDATION = "validation"
    GENERATION = "generation"
    DEEP_ASSIST = "deep_assist"


class StateMachine:
    """五阶段状态机

    管理阶段间的转换，支持前进与回退。

    状态转换图：
        info_confirm -> creativity -> validation
            ^              |            |
            |              v            v
            +--------------+       generation -> deep_assist
    """

    # 允许的状态转换
    TRANSITIONS = {
        Stage.INFO_CONFIRM: [Stage.CREATIVITY],
        Stage.CREATIVITY: [Stage.VALIDATION, Stage.INFO_CONFIRM],
        Stage.VALIDATION: [Stage.GENERATION, Stage.CREATIVITY],
        Stage.GENERATION: [Stage.DEEP_ASSIST, Stage.VALIDATION],
        Stage.DEEP_ASSIST: [],
    }

    def __init__(self):
        self.current_stage = Stage.INFO_CONFIRM
        self.history: list[Stage] = [Stage.INFO_CONFIRM]

    def can_transition(self, target: Stage) -> bool:
        """检查是否可以转换到目标阶段"""
        return target in self.TRANSITIONS.get(self.current_stage, [])

    def transition(self, target: Stage) -> bool:
        """转换到目标阶段"""
        if not self.can_transition(target):
            return False
        self.current_stage = target
        self.history.append(target)
        return True

    def rollback(self, target: Stage = None) -> bool:
        """回退到指定阶段（默认回退到上一阶段）"""
        if target:
            # 回退到指定阶段
            if target not in self.TRANSITIONS.get(self.current_stage, []):
                return False
            self.current_stage = target
            self.history.append(target)
            return True
        else:
            # 回退到上一阶段
            if len(self.history) < 2:
                return False
            self.history.pop()  # 移除当前阶段
            self.current_stage = self.history[-1]
            return True

    def is_final_stage(self) -> bool:
        """是否处于最终阶段"""
        return self.current_stage == Stage.DEEP_ASSIST

    def get_history(self) -> list[str]:
        """获取状态转换历史"""
        return [s.value for s in self.history]
```

### 4.4.2 Pipeline 管道

```python
# backend/orchestration/pipeline.py

class Pipeline:
    """管道执行器

    按预定义的管道模板执行多阶段任务。
    """

    def __init__(self, template: str = "proposal_generation"):
        self.template = template
        self.stages: list[dict] = self._load_template(template)

    def _load_template(self, template: str) -> list[dict]:
        """加载管道模板"""
        templates = {
            "proposal_generation": [
                {"name": "info_confirm", "agent": "orchestrator"},
                {"name": "creativity", "agent": "reasoner"},
                {"name": "validation", "agent": "critic"},
                {"name": "generation", "agent": "writer"},
                {"name": "deep_assist", "agent": "mentor"},
            ],
            "literature_review": [
                {"name": "search", "agent": "searcher"},
                {"name": "filter", "agent": "searcher"},
                {"name": "classify", "agent": "reasoner"},
                {"name": "summarize", "agent": "reasoner"},
                {"name": "review_write", "agent": "writer"},
            ],
        }
        return templates.get(template, templates["proposal_generation"])

    async def execute(self, input_data: dict) -> dict:
        """执行管道

        Args:
            input_data: 输入数据

        Returns:
            执行结果，包含各阶段输出
        """
        results = {}
        current_data = input_data

        for stage in self.stages:
            stage_name = stage["name"]
            agent_id = stage["agent"]

            try:
                agent = get_agent(agent_id)
                result = await agent.run(current_data)

                results[stage_name] = {
                    "success": result.success,
                    "content": result.content,
                    "data": result.data,
                }

                if not result.success:
                    results["failed_at"] = stage_name
                    results["error"] = result.error
                    break

                # 将本阶段输出作为下阶段输入
                current_data.update(result.data)

            except Exception as e:
                results[stage_name] = {
                    "success": False,
                    "error": str(e),
                }
                results["failed_at"] = stage_name
                break

        results["completed"] = "failed_at" not in results
        return results
```

### 4.4.3 Hooks 钩子机制

```python
# backend/orchestration/hooks/__init__.py

class Hook:
    """钩子基类"""

    async def before(self, context: dict) -> dict:
        """阶段执行前钩子"""
        return context

    async def after(self, context: dict, result: dict) -> dict:
        """阶段执行后钩子"""
        return result


# backend/orchestration/hooks/pre_search.py

class PreSearchHook(Hook):
    """检索前钩子

    在检索前进行关键词扩展与上下文丰富。
    """

    async def before(self, context: dict) -> dict:
        """检索前：扩展关键词"""
        keywords = context.get("keywords", [])

        # 使用创意引擎扩展关键词
        from backend.creativity import cross_domain
        expanded = cross_domain.expand_keywords(keywords)

        context["expanded_keywords"] = expanded
        return context


# backend/orchestration/hooks/hard_rule_interceptor.py

class HardRuleInterceptor(Hook):
    """硬规则拦截器

    在论题生成后立即校验硬规则，失败则拦截。
    """

    async def after(self, context: dict, result: dict) -> dict:
        """生成后：硬规则校验"""
        proposals = result.get("proposals", [])
        degree = context.get("degree", "master")

        for i, proposal in enumerate(proposals):
            try:
                validate_proposal_hard(proposal, degree)
            except HTTPException as e:
                # 拦截：标记失败
                result["intercepted"] = True
                result["intercept_reason"] = (
                    f"论题{i + 1}校验失败：{e.detail}"
                )
                break

        return result
```

### 4.4.4 Scheduler 调度器

```python
# backend/orchestration/scheduler.py

import asyncio


class Scheduler:
    """调度器

    管理并发 Agent 执行，控制并发度与资源分配。
    """

    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._running: dict[str, asyncio.Task] = {}

    async def submit(
        self,
        agent_id: str,
        input_data: dict,
        priority: int = 0,
    ) -> str:
        """提交任务

        Args:
            agent_id: Agent ID
            input_data: 输入数据
            priority: 优先级（数值越大优先级越高）

        Returns:
            任务 ID
        """
        task_id = f"task_{uuid.uuid4().hex[:12]}"

        async def _execute():
            async with self._semaphore:
                agent = get_agent(agent_id)
                return await agent.run(input_data)

        task = asyncio.create_task(_execute())
        self._running[task_id] = task
        return task_id

    async def wait(self, task_id: str) -> AgentResult:
        """等待任务完成"""
        task = self._running.get(task_id)
        if not task:
            raise KeyError(f"任务 {task_id} 不存在")
        result = await task
        del self._running[task_id]
        return result

    async def wait_all(self) -> dict[str, AgentResult]:
        """等待所有任务完成"""
        results = {}
        for task_id, task in list(self._running.items()):
            results[task_id] = await task
        self._running.clear()
        return results

    def get_running_count(self) -> int:
        """获取正在运行的任务数"""
        return len(self._running)
```

## 4.5 ai 模块：AI 代理与缓存

ai 模块是 ThesisMiner 与 LLM 交互的核心层，负责调用 LLM、管理缓存、解析响应。

### 4.5.1 AIProxy LLM 调用代理

```python
# backend/ai/ai_proxy.py

import httpx
from openai import AsyncOpenAI

from backend.config import get_settings
from backend.ai.prompt_cache import PromptCache
from backend.ai.cache_monitor import CacheMonitor


class AIProxy:
    """LLM 调用代理

    统一封装多家 LLM 的调用逻辑，支持：
    - 同步/异步调用
    - 流式响应
    - 自动重试与降级
    - Prompt 缓存
    - Token 用量统计
    """

    def __init__(self):
        self.settings = get_settings()
        self.prompt_cache = PromptCache()
        self.cache_monitor = CacheMonitor()
        self._clients: dict[str, AsyncOpenAI] = {}

    def _get_client(self, model_id: str) -> AsyncOpenAI:
        """获取指定模型的客户端"""
        if model_id not in self._clients:
            model_config = self._get_model_config(model_id)
            api_key = os.getenv(model_config["api_key_env"], "")
            self._clients[model_id] = AsyncOpenAI(
                api_key=api_key,
                base_url=model_config["base_url"],
            )
        return self._clients[model_id]

    async def call_llm(
        self,
        model_id: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
        enable_cache: bool = True,
    ) -> dict:
        """调用 LLM

        Args:
            model_id: 模型 ID
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大输出 Token
            stream: 是否流式响应
            enable_cache: 是否启用缓存

        Returns:
            响应字典，包含 content/usage/cache_hit
        """
        # 1. 检查缓存
        cache_key = None
        if enable_cache:
            cache_key = self.prompt_cache.build_key(model_id, messages)
            cached = self.prompt_cache.get(cache_key)
            if cached:
                self.cache_monitor.record_hit(model_id)
                return {**cached, "cache_hit": True}

        # 2. 调用 LLM
        client = self._get_client(model_id)
        model_config = self._get_model_config(model_id)

        try:
            response = await client.chat.completions.create(
                model=model_config["model_name"],
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
            )

            if stream:
                # 流式响应单独处理
                return await self._handle_stream(response, model_id)

            # 3. 解析响应
            result = {
                "content": response.choices[0].message.content,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                "cache_hit": False,
            }

            # 4. 写入缓存
            if enable_cache and cache_key:
                self.prompt_cache.set(cache_key, result)
                self.cache_monitor.record_miss(model_id)

            # 5. 记录账本
            self._record_ledger(model_id, result["usage"])

            return result

        except Exception as e:
            # 6. 降级处理
            return await self._handle_fallback(model_id, messages, str(e))
```

### 4.5.2 PromptCache Prompt 缓存

```python
# backend/ai/prompt_cache.py

import hashlib
import time


class PromptCache:
    """Prompt 缓存

    实现 DeepSeek 三段式 Prefix 缓存设计：
    - System 段：系统提示（固定不变，缓存命中率最高）
    - Few-shot 段：示例对话（较少变化，缓存命中率高）
    - User 段：用户输入（频繁变化，缓存命中率低）

    通过将固定内容放在 Prefix，最大化缓存命中率。
    """

    def __init__(self, ttl: int = 1800):
        self.ttl = ttl  # 缓存 TTL（秒）
        self._cache: dict[str, dict] = {}  # key -> {value, expire_at}

    def build_key(self, model_id: str, messages: list[dict]) -> str:
        """构建缓存键

        仅基于 System + Few-shot 段构建键，
        User 段不参与键计算（因为 User 段频繁变化）。
        """
        # 提取 System 与 Few-shot 段
        prefix_parts = []
        for msg in messages:
            if msg["role"] == "system":
                prefix_parts.append(msg["content"])
            elif msg.get("role") == "user" and msg.get("is_fewshot"):
                prefix_parts.append(msg["content"])

        prefix = "|".join(prefix_parts)
        key_str = f"{model_id}:{prefix}"
        return hashlib.sha256(key_str.encode()).hexdigest()

    def get(self, key: str) -> dict | None:
        """获取缓存"""
        entry = self._cache.get(key)
        if not entry:
            return None
        if time.time() > entry["expire_at"]:
            del self._cache[key]
            return None
        return entry["value"]

    def set(self, key: str, value: dict):
        """写入缓存"""
        self._cache[key] = {
            "value": value,
            "expire_at": time.time() + self.ttl,
        }

    def clear(self):
        """清空缓存"""
        self._cache.clear()

    def get_stats(self) -> dict:
        """获取缓存统计"""
        now = time.time()
        valid_count = sum(
            1 for entry in self._cache.values()
            if now <= entry["expire_at"]
        )
        expired_count = len(self._cache) - valid_count
        return {
            "total_entries": len(self._cache),
            "valid_entries": valid_count,
            "expired_entries": expired_count,
        }
```

### 4.5.3 CacheMonitor 缓存监控

```python
# backend/ai/cache_monitor.py

import time


class CacheMonitor:
    """缓存监控器

    监控各模型的缓存命中率，目标 >=95%。
    """

    def __init__(self):
        self._stats: dict[str, dict] = {}  # model_id -> stats

    def record_hit(self, model_id: str):
        """记录缓存命中"""
        if model_id not in self._stats:
            self._stats[model_id] = {"hits": 0, "misses": 0}
        self._stats[model_id]["hits"] += 1

    def record_miss(self, model_id: str):
        """记录缓存未命中"""
        if model_id not in self._stats:
            self._stats[model_id] = {"hits": 0, "misses": 0}
        self._stats[model_id]["misses"] += 1

    def get_hit_rate(self, model_id: str) -> float:
        """获取指定模型的缓存命中率"""
        stats = self._stats.get(model_id, {"hits": 0, "misses": 0})
        total = stats["hits"] + stats["misses"]
        if total == 0:
            return 0.0
        return stats["hits"] / total

    def get_all_stats(self) -> dict:
        """获取所有模型的缓存统计"""
        result = {}
        for model_id, stats in self._stats.items():
            total = stats["hits"] + stats["misses"]
            result[model_id] = {
                "hits": stats["hits"],
                "misses": stats["misses"],
                "total": total,
                "hit_rate": stats["hits"] / total if total > 0 else 0,
            }
        return result

    def reset(self):
        """重置统计"""
        self._stats.clear()
```

### 4.5.4 CitationParser 引用解析器

```python
# backend/ai/citation_parser.py

import re
from urllib.parse import urlparse


class CitationParser:
    """引用解析器

    从 LLM 响应中提取引用信息，支持多种引用格式：
    - [1] URL 格式
    - Markdown 链接格式
    - 行内 URL 格式
    """

    # 引用模式
    PATTERNS = {
        "numbered": r"\[(\d+)\]\s*(https?://[^\s\]]+)",
        "markdown": r"\[([^\]]+)\]\((https?://[^\s)]+)\)",
        "inline": r"(https?://[^\s\)\]]+)",
    }

    def parse(self, content: str) -> list[dict]:
        """解析引用

        Args:
            content: LLM 响应内容

        Returns:
            引用列表，每个引用包含 url/title/source_domain
        """
        citations = []
        seen_urls = set()

        # 1. 解析编号引用 [1] URL
        for match in re.finditer(self.PATTERNS["numbered"], content):
            num, url = match.groups()
            if url not in seen_urls:
                citations.append({
                    "index": int(num),
                    "url": url,
                    "title": "",
                    "source_domain": self._extract_domain(url),
                })
                seen_urls.add(url)

        # 2. 解析 Markdown 链接 [title](url)
        for match in re.finditer(self.PATTERNS["markdown"], content):
            title, url = match.groups()
            if url not in seen_urls:
                citations.append({
                    "index": len(citations) + 1,
                    "url": url,
                    "title": title,
                    "source_domain": self._extract_domain(url),
                })
                seen_urls.add(url)

        # 3. 解析行内 URL
        for match in re.finditer(self.PATTERNS["inline"], content):
            url = match.group(1)
            if url not in seen_urls:
                citations.append({
                    "index": len(citations) + 1,
                    "url": url,
                    "title": "",
                    "source_domain": self._extract_domain(url),
                })
                seen_urls.add(url)

        return citations

    def _extract_domain(self, url: str) -> str:
        """提取域名"""
        parsed = urlparse(url)
        return parsed.netloc or ""
```

### 4.5.5 Streaming 流式响应处理

```python
# backend/ai/streaming.py

from typing import AsyncGenerator


class StreamHandler:
    """流式响应处理器

    处理 LLM 的流式响应，支持 SSE（Server-Sent Events）格式输出。
    """

    async def process_stream(
        self,
        response: AsyncGenerator,
    ) -> AsyncGenerator[str, None]:
        """处理流式响应

        Args:
            response: LLM 流式响应

        Yields:
            SSE 格式的数据块
        """
        full_content = ""
        try:
            async for chunk in response:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_content += content
                    # 转换为 SSE 格式
                    yield f"data: {content}\n\n"

            # 发送结束标记
            yield f"data: [DONE]\n\n"

        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"
```

## 4.6 analytics 模块：分析监控

analytics 模块负责系统运行时的指标采集、性能监控与用量追踪。

### 4.6.1 MetricsCollector 指标采集器

```python
# backend/analytics/metrics_collector.py

import time
from collections import defaultdict


class MetricsCollector:
    """指标采集器

    采集系统运行时的关键指标，包括：
    - API 请求量
    - Agent 执行次数
    - LLM 调用次数与延迟
    - 缓存命中率
    - 错误率
    """

    def __init__(self):
        self._metrics: dict[str, list] = defaultdict(list)

    def record(self, metric_name: str, value: float, tags: dict = None):
        """记录指标

        Args:
            metric_name: 指标名称
            value: 指标值
            tags: 标签（用于分组）
        """
        self._metrics[metric_name].append({
            "value": value,
            "timestamp": time.time(),
            "tags": tags or {},
        })

    def get_metric(
        self,
        metric_name: str,
        time_range: int = 3600,
    ) -> list[dict]:
        """获取指定时间范围内的指标"""
        now = time.time()
        return [
            m for m in self._metrics[metric_name]
            if now - m["timestamp"] <= time_range
        ]

    def get_aggregate(
        self,
        metric_name: str,
        aggregation: str = "avg",
        time_range: int = 3600,
    ) -> float:
        """获取聚合指标"""
        metrics = self.get_metric(metric_name, time_range)
        if not metrics:
            return 0

        values = [m["value"] for m in metrics]
        if aggregation == "avg":
            return sum(values) / len(values)
        elif aggregation == "sum":
            return sum(values)
        elif aggregation == "max":
            return max(values)
        elif aggregation == "min":
            return min(values)
        elif aggregation == "count":
            return len(values)
        return 0
```

### 4.6.2 PerformanceMonitor 性能监控

```python
# backend/analytics/performance_monitor.py

import time
from contextlib import asynccontextmanager


class PerformanceMonitor:
    """性能监控器

    监控关键操作的执行时间，识别性能瓶颈。
    """

    def __init__(self):
        self._timings: dict[str, list[float]] = defaultdict(list)

    @asynccontextmanager
    async def measure(self, operation: str):
        """测量操作耗时（异步上下文管理器）

        Args:
            operation: 操作名称

        Yields:
            None

        用法：
            async with perf_monitor.measure("llm_call"):
                response = await proxy.call_llm(...)
        """
        start = time.time()
        try:
            yield
        finally:
            elapsed = time.time() - start
            self._timings[operation].append(elapsed)

    def get_avg_time(self, operation: str) -> float:
        """获取操作平均耗时"""
        timings = self._timings.get(operation, [])
        if not timings:
            return 0
        return sum(timings) / len(timings)

    def get_p95_time(self, operation: str) -> float:
        """获取操作 P95 耗时"""
        timings = sorted(self._timings.get(operation, []))
        if not timings:
            return 0
        idx = int(len(timings) * 0.95)
        return timings[min(idx, len(timings) - 1)]

    def get_stats(self) -> dict:
        """获取所有性能统计"""
        return {
            op: {
                "count": len(timings),
                "avg_time": sum(timings) / len(timings) if timings else 0,
                "max_time": max(timings) if timings else 0,
                "min_time": min(timings) if timings else 0,
            }
            for op, timings in self._timings.items()
        }
```

### 4.6.3 UsageTracker 用量追踪

```python
# backend/analytics/usage_tracker.py

import time
from collections import defaultdict


class UsageTracker:
    """用量追踪器

    追踪 LLM 调用的 Token 用量与成本。
    """

    def __init__(self):
        self._usage: dict[str, list[dict]] = defaultdict(list)

    def track(
        self,
        model_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost: float,
        session_id: str = "",
    ):
        """追踪一次 LLM 调用

        Args:
            model_id: 模型 ID
            prompt_tokens: 输入 Token 数
            completion_tokens: 输出 Token 数
            cost: 成本（元）
            session_id: 会话 ID
        """
        self._usage[model_id].append({
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cost": cost,
            "session_id": session_id,
            "timestamp": time.time(),
        })

    def get_total_cost(self, time_range: int = 86400) -> float:
        """获取指定时间范围内的总成本"""
        now = time.time()
        total = 0
        for usage_list in self._usage.values():
            for u in usage_list:
                if now - u["timestamp"] <= time_range:
                    total += u["cost"]
        return total

    def get_total_tokens(self, time_range: int = 86400) -> dict:
        """获取指定时间范围内的总 Token 用量"""
        now = time.time()
        total = {"prompt": 0, "completion": 0, "total": 0}
        for usage_list in self._usage.values():
            for u in usage_list:
                if now - u["timestamp"] <= time_range:
                    total["prompt"] += u["prompt_tokens"]
                    total["completion"] += u["completion_tokens"]
                    total["total"] += u["total_tokens"]
        return total

    def get_by_model(self) -> dict[str, dict]:
        """按模型分组统计"""
        result = {}
        for model_id, usage_list in self._usage.items():
            result[model_id] = {
                "calls": len(usage_list),
                "total_tokens": sum(u["total_tokens"] for u in usage_list),
                "total_cost": sum(u["cost"] for u in usage_list),
            }
        return result
```

## 4.7 ml 模块：机器学习组件

ml 模块提供文本嵌入、相似度计算等机器学习能力。

### 4.7.1 EmbeddingEngine 嵌入引擎

```python
# backend/ml/embedding_engine.py

class EmbeddingEngine:
    """文本嵌入引擎

    将文本转换为向量表示，用于相似度计算。
    支持本地嵌入与 API 嵌入两种模式。
    """

    def __init__(self, mode: str = "local"):
        """初始化嵌入引擎

        Args:
            mode: 嵌入模式（local/api）
        """
        self.mode = mode
        self._model = None
        if mode == "local":
            self._init_local_model()

    def _init_local_model(self):
        """初始化本地嵌入模型"""
        # 使用 sentence-transformers 本地模型
        # 实际实现中会延迟加载
        pass

    async def embed(self, text: str) -> list[float]:
        """生成文本嵌入

        Args:
            text: 输入文本

        Returns:
            嵌入向量（浮点数列表）
        """
        if self.mode == "local":
            return self._embed_local(text)
        else:
            return await self._embed_api(text)

    def _embed_local(self, text: str) -> list[float]:
        """本地嵌入"""
        if self._model is None:
            # 延迟加载模型
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
        embedding = self._model.encode(text)
        return embedding.tolist()

    async def _embed_api(self, text: str) -> list[float]:
        """API 嵌入"""
        from openai import AsyncOpenAI
        client = AsyncOpenAI()
        response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return response.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量生成嵌入

        Args:
            texts: 输入文本列表

        Returns:
            嵌入向量列表
        """
        if self.mode == "local":
            if self._model is None:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer("all-MiniLM-L6-v2")
            embeddings = self._model.encode(texts)
            return embeddings.tolist()
        else:
            # API 模式逐个调用
            results = []
            for text in texts:
                embedding = await self._embed_api(text)
                results.append(embedding)
            return results
```

### 4.7.2 SimilarityScorer 相似度打分

```python
# backend/ml/similarity_scorer.py

import math


class SimilarityScorer:
    """相似度打分器

    计算文本/向量之间的相似度，支持多种算法。
    """

    @staticmethod
    def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        """计算余弦相似度

        Args:
            vec_a: 向量 A
            vec_b: 向量 B

        Returns:
            相似度（0-1）
        """
        if len(vec_a) != len(vec_b):
            raise ValueError("向量维度不一致")

        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    @staticmethod
    def jaccard_similarity(set_a: set, set_b: set) -> float:
        """计算 Jaccard 相似度

        Args:
            set_a: 集合 A
            set_b: 集合 B

        Returns:
            相似度（0-1）
        """
        if not set_a and not set_b:
            return 1.0
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union) if union else 0.0

    @staticmethod
    def text_similarity(text_a: str, text_b: str) -> float:
        """计算文本相似度（基于词集的 Jaccard）

        Args:
            text_a: 文本 A
            text_b: 文本 B

        Returns:
            相似度（0-1）
        """
        # 简单分词
        words_a = set(text_a.lower().split())
        words_b = set(text_b.lower().split())
        return SimilarityScorer.jaccard_similarity(words_a, words_b)

    @staticmethod
    def find_most_similar(
        query: str,
        candidates: list[str],
        threshold: float = 0.5,
    ) -> list[tuple[str, float]]:
        """查找最相似的文本

        Args:
            query: 查询文本
            candidates: 候选文本列表
            threshold: 相似度阈值

        Returns:
            相似文本列表，每项为 (text, score)
        """
        results = []
        for candidate in candidates:
            score = SimilarityScorer.text_similarity(query, candidate)
            if score >= threshold:
                results.append((candidate, score))

        # 按相似度降序排序
        results.sort(key=lambda x: x[1], reverse=True)
        return results
```

### 4.7.3 TextProcessor 文本处理

```python
# backend/ml/text_processor.py

import re
from collections import Counter


class TextProcessor:
    """文本处理器

    提供文本清洗、分词、关键词提取等功能。
    """

    @staticmethod
    def clean_text(text: str) -> str:
        """清洗文本

        - 移除多余空白
        - 移除特殊字符
        - 标准化标点
        """
        # 移除多余空白
        text = re.sub(r"\s+", " ", text)
        # 移除控制字符
        text = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)
        # 标准化引号
        text = text.replace("\u201c", "\"").replace("\u201d", "\"")
        text = text.replace("\u2018", "'").replace("\u2019", "'")
        return text.strip()

    @staticmethod
    def extract_keywords(text: str, top_n: int = 10) -> list[str]:
        """提取关键词（基于词频）

        Args:
            text: 输入文本
            top_n: 返回前 N 个关键词

        Returns:
            关键词列表
        """
        # 简单分词
        words = re.findall(r"[\u4e00-\u9fa5]+|[a-zA-Z]+", text.lower())

        # 过滤停用词
        stop_words = {"的", "了", "在", "是", "我", "有", "和", "就",
                      "不", "人", "都", "一", "一个", "上", "也", "很",
                      "到", "说", "要", "去", "你", "会", "着", "没有",
                      "看", "好", "自己", "这"}
        words = [w for w in words if w not in stop_words and len(w) > 1]

        # 统计词频
        counter = Counter(words)
        return [word for word, _ in counter.most_common(top_n)]

    @staticmethod
    def count_words(text: str) -> dict:
        """统计文本信息

        Returns:
            包含字符数/词数/段落数的字典
        """
        chars = len(text)
        words = len(re.findall(r"[\u4e00-\u9fa5]+|[a-zA-Z]+", text))
        paragraphs = len([p for p in text.split("\n\n") if p.strip()])
        sentences = len(re.findall(r"[。！？.!?]", text))

        return {
            "chars": chars,
            "words": words,
            "paragraphs": paragraphs,
            "sentences": sentences,
        }

    @staticmethod
    def split_into_chunks(text: str, max_chars: int = 2000) -> list[str]:
        """将长文本分割为块

        Args:
            text: 输入文本
            max_chars: 每块最大字符数

        Returns:
            文本块列表
        """
        if len(text) <= max_chars:
            return [text]

        chunks = []
        current_chunk = ""

        for paragraph in text.split("\n\n"):
            if len(current_chunk) + len(paragraph) > max_chars:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = paragraph
            else:
                current_chunk += "\n\n" + paragraph if current_chunk else paragraph

        if current_chunk:
            chunks.append(current_chunk)

        return chunks
```

## 4.8 export 模块：导出与报告

export 模块负责将生成的内容导出为多种格式。

### 4.8.1 DocumentExporter 文档导出器

```python
# backend/export/document_exporter.py

import json
from datetime import datetime


class DocumentExporter:
    """文档导出器

    支持将内容导出为多种格式：
    - Markdown
    - HTML
    - JSON
    - 纯文本
    """

    def export_markdown(self, content: dict, metadata: dict = None) -> str:
        """导出为 Markdown

        Args:
            content: 内容字典
            metadata: 元数据

        Returns:
            Markdown 字符串
        """
        lines = []

        # 标题
        if metadata and metadata.get("title"):
            lines.append(f"# {metadata['title']}\n")

        # 元信息
        if metadata:
            lines.append("---")
            if metadata.get("author"):
                lines.append(f"**作者**：{metadata['author']}")
            if metadata.get("date"):
                lines.append(f"**日期**：{metadata['date']}")
            if metadata.get("degree"):
                lines.append(f"**学位**：{metadata['degree']}")
            if metadata.get("discipline"):
                lines.append(f"**学科**：{metadata['discipline']}")
            lines.append("---\n")

        # 正文
        if isinstance(content, dict):
            for section, text in content.items():
                lines.append(f"## {section}\n")
                lines.append(text)
                lines.append("")
        elif isinstance(content, str):
            lines.append(content)

        return "\n".join(lines)

    def export_html(self, content: dict, metadata: dict = None) -> str:
        """导出为 HTML"""
        lines = ["<!DOCTYPE html>", "<html lang='zh-CN'>", "<head>",
                 "<meta charset='UTF-8'>",
                 "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"]

        if metadata and metadata.get("title"):
            lines.append(f"<title>{metadata['title']}</title>")

        lines.append("<style>")
        lines.append("body { font-family: 'Microsoft YaHei', sans-serif; "
                     "max-width: 800px; margin: 0 auto; padding: 20px; "
                     "line-height: 1.8; color: #333; }")
        lines.append("h1 { color: #2c3e50; border-bottom: 2px solid #3498db; "
                     "padding-bottom: 10px; }")
        lines.append("h2 { color: #34495e; margin-top: 30px; }")
        lines.append("meta { color: #7f8c8d; font-size: 14px; }")
        lines.append("</style>")
        lines.append("</head>", "<body>")

        if metadata and metadata.get("title"):
            lines.append(f"<h1>{metadata['title']}</h1>")

        if metadata:
            lines.append("<div class='meta'>")
            if metadata.get("author"):
                lines.append(f"<p>作者：{metadata['author']}</p>")
            if metadata.get("date"):
                lines.append(f"<p>日期：{metadata['date']}</p>")
            if metadata.get("degree"):
                lines.append(f"<p>学位：{metadata['degree']}</p>")
            lines.append("</div>")

        if isinstance(content, dict):
            for section, text in content.items():
                lines.append(f"<h2>{section}</h2>")
                # 简单的段落转换
                paragraphs = text.split("\n\n")
                for p in paragraphs:
                    lines.append(f"<p>{p}</p>")
        elif isinstance(content, str):
            lines.append(f"<p>{content}</p>")

        lines.append("</body>", "</html>")
        return "\n".join(lines)

    def export_json(self, content: dict, metadata: dict = None) -> str:
        """导出为 JSON"""
        export_data = {
            "metadata": metadata or {},
            "content": content,
            "exported_at": datetime.now().isoformat(),
        }
        return json.dumps(export_data, ensure_ascii=False, indent=2)

    def export_text(self, content: dict, metadata: dict = None) -> str:
        """导出为纯文本"""
        lines = []

        if metadata and metadata.get("title"):
            lines.append(metadata["title"])
            lines.append("=" * len(metadata["title"]))
            lines.append("")

        if metadata:
            if metadata.get("author"):
                lines.append(f"作者：{metadata['author']}")
            if metadata.get("date"):
                lines.append(f"日期：{metadata['date']}")
            if metadata.get("degree"):
                lines.append(f"学位：{metadata['degree']}")
            lines.append("")

        if isinstance(content, dict):
            for section, text in content.items():
                lines.append(section)
                lines.append("-" * len(section))
                lines.append(text)
                lines.append("")
        elif isinstance(content, str):
            lines.append(content)

        return "\n".join(lines)
```

### 4.8.2 CitationFormatter 引用格式化

```python
# backend/export/citation_formatter.py


class CitationFormatter:
    """引用格式化器

    将引用信息格式化为多种学术引用格式：
    - GB/T 7714（中国国家标准）
    - APA
    - MLA
    - BibTeX
    """

    def format_gbt7714(self, citation: dict) -> str:
        """格式化为 GB/T 7714"""
        parts = []
        if citation.get("author"):
            parts.append(citation["author"])
        if citation.get("title"):
            parts.append(f"{citation['title']}[J]")
        if citation.get("journal"):
            parts.append(f"{citation['journal']}")
        if citation.get("year"):
            parts.append(f",{citation['year']}")
        if citation.get("volume"):
            parts.append(f",{citation['volume']}")
        if citation.get("pages"):
            parts.append(f":{citation['pages']}")
        return "".join(parts) + "."

    def format_apa(self, citation: dict) -> str:
        """格式化为 APA"""
        parts = []
        if citation.get("author"):
            parts.append(f"{citation['author']}")
        if citation.get("year"):
            parts.append(f"({citation['year']})")
        if citation.get("title"):
            parts.append(f"{citation['title']}")
        if citation.get("journal"):
            parts.append(f"*{citation['journal']}*")
        if citation.get("volume"):
            vol = citation["volume"]
            if citation.get("issue"):
                vol += f"({citation['issue']})"
            parts.append(vol)
        if citation.get("pages"):
            parts.append(f"{citation['pages']}")
        return ". ".join(parts) + "."

    def format_bibtex(self, citation: dict) -> str:
        """格式化为 BibTeX"""
        key = citation.get("author", "unknown").split(",")[0].lower()
        year = citation.get("year", "xxxx")
        cite_key = f"{key}{year}"

        lines = [f"@article{{{cite_key},"]
        if citation.get("author"):
            lines.append(f"  author = {{{citation['author']}}},")
        if citation.get("title"):
            lines.append(f"  title = {{{citation['title']}}},")
        if citation.get("journal"):
            lines.append(f"  journal = {{{citation['journal']}}},")
        if citation.get("year"):
            lines.append(f"  year = {{{citation['year']}}},")
        if citation.get("volume"):
            lines.append(f"  volume = {{{citation['volume']}}},")
        if citation.get("pages"):
            lines.append(f"  pages = {{{citation['pages']}}},")
        lines.append("}")
        return "\n".join(lines)
```

### 4.8.3 ReportGenerator 报告生成

```python
# backend/export/report_generator.py

from datetime import datetime


class ReportGenerator:
    """报告生成器

    生成完整的开题报告，包含所有必要章节。
    """

    def generate_proposal_report(
        self,
        proposal: dict,
        validation: dict = None,
        metadata: dict = None,
    ) -> dict:
        """生成开题报告

        Args:
            proposal: 论题信息
            validation: 校验结果
            metadata: 元数据

        Returns:
            报告内容字典（章节名 -> 内容）
        """
        report = {}

        # 1. 选题依据
        report["一、选题依据"] = self._generate_background(proposal)

        # 2. 研究意义
        report["二、研究意义与目标"] = self._generate_significance(proposal)

        # 3. 文献综述
        report["三、国内外研究现状"] = self._generate_literature_review(proposal)

        # 4. 研究内容
        report["四、研究内容"] = self._generate_research_content(proposal)

        # 5. 研究方法
        report["五、研究方法与技术路线"] = self._generate_methodology(proposal)

        # 6. 预期成果
        report["六、预期成果与创新点"] = self._generate_expected_outcomes(proposal)

        # 7. 研究进度
        report["七、研究进度安排"] = self._generate_timeline(proposal, metadata)

        # 8. 参考文献
        report["八、参考文献"] = self._generate_references(proposal)

        return report

    def _generate_background(self, proposal: dict) -> str:
        """生成选题背景"""
        title = proposal.get("title", "")
        direction = proposal.get("research_direction", "")
        return (
            f"本研究选题为「{title}」，"
            f"属于{direction}领域的研究范畴。\n\n"
            f"随着相关技术的快速发展，该领域面临着诸多挑战与机遇。"
            f"本研究旨在针对现有研究的不足，提出新的解决方案。"
        )

    def _generate_significance(self, proposal: dict) -> str:
        """生成研究意义"""
        significance = proposal.get("research_significance", "")
        if isinstance(significance, list):
            significance = "\n".join(f"- {s}" for s in significance)
        return (
            f"本研究具有重要的理论意义与实践价值：\n\n"
            f"{significance}\n\n"
            f"研究目标：通过本研究，预期在理论与方法上取得创新性成果。"
        )

    def _generate_literature_review(self, proposal: dict) -> str:
        """生成文献综述"""
        return (
            "（此处由 WriterAgent 生成详细文献综述）\n\n"
            "国内外学者在该领域已开展了大量研究工作，"
            "但仍有若干问题亟待解决。"
        )

    def _generate_research_content(self, proposal: dict) -> str:
        """生成研究内容"""
        content = proposal.get("research_content", [])
        if isinstance(content, list):
            lines = []
            for i, item in enumerate(content, 1):
                lines.append(f"{i}. {item}")
            return "\n".join(lines)
        return str(content)

    def _generate_methodology(self, proposal: dict) -> str:
        """生成研究方法"""
        return (
            "本研究将采用以下研究方法：\n\n"
            "1. 文献研究法：系统梳理国内外相关文献\n"
            "2. 实验研究法：设计实验验证所提方法\n"
            "3. 对比分析法：与现有方法进行对比\n"
            "4. 统计分析法：对实验数据进行统计分析"
        )

    def _generate_expected_outcomes(self, proposal: dict) -> str:
        """生成预期成果"""
        outcome = proposal.get("expected_outcome", "")
        return (
            f"预期成果：\n\n"
            f"{outcome}\n\n"
            f"创新点：\n"
            f"- 方法创新：提出新的研究方法\n"
            f"- 应用创新：拓展方法的应用场景"
        )

    def _generate_timeline(self, proposal: dict, metadata: dict) -> str:
        """生成研究进度"""
        degree = metadata.get("degree", "master") if metadata else "master"
        months = 12 if degree == "master" else 24

        lines = [f"本研究预计周期为 {months} 个月，具体安排如下：\n"]
        phases = [
            (1, 2, "文献调研与需求分析"),
            (3, 4, "研究方案设计与技术选型"),
            (5, 8, "核心方法实现与实验"),
            (9, 10, "实验验证与结果分析"),
            (11, months, "论文撰写与答辩准备"),
        ]

        for start, end, task in phases:
            lines.append(f"第 {start}-{end} 月：{task}")

        return "\n".join(lines)

    def _generate_references(self, proposal: dict) -> str:
        """生成参考文献"""
        citations = proposal.get("citations", [])
        if not citations:
            return "（参考文献由 WriterAgent 生成）"

        lines = []
        for i, cite in enumerate(citations, 1):
            title = cite.get("title", "")
            url = cite.get("url", "")
            lines.append(f"[{i}] {title}. {url}")

        return "\n".join(lines)
```

## 4.9 creativity 模块：创意引擎

creativity 模块负责激发创意，包括学术谱系分析、跨域联想与候选排序。

### 4.9.1 AcademicLineage 学术谱系

```python
# backend/creativity/academic_lineage.py


class AcademicLineage:
    """学术谱系分析

    分析研究方向的学术传承关系，识别研究脉络。
    """

    def analyze_lineage(self, direction: str) -> dict:
        """分析学术谱系

        Args:
            direction: 研究方向

        Returns:
            谱系分析结果，包含起源/发展/分支/当前热点
        """
        return {
            "direction": direction,
            "origin": self._find_origin(direction),
            "milestones": self._find_milestones(direction),
            "branches": self._find_branches(direction),
            "current_hotspots": self._find_hotspots(direction),
        }

    def _find_origin(self, direction: str) -> dict:
        """查找研究方向起源"""
        # 实际实现中会查询知识图谱
        return {
            "era": "2010s",
            "key_papers": [],
            "founding_researchers": [],
        }

    def _find_milestones(self, direction: str) -> list[dict]:
        """查找里程碑事件"""
        return [
            {"year": 2015, "event": "基础理论建立"},
            {"year": 2018, "event": "方法突破"},
            {"year": 2022, "event": "大规模应用"},
        ]

    def _find_branches(self, direction: str) -> list[str]:
        """查找研究分支"""
        return [
            f"{direction}-理论方向",
            f"{direction}-应用方向",
            f"{direction}-优化方向",
        ]

    def _find_hotspots(self, direction: str) -> list[str]:
        """查找当前研究热点"""
        return [
            f"{direction}的最新进展",
            f"{direction}的开放问题",
            f"{direction}的跨学科应用",
        ]
```

### 4.9.2 CrossDomain 跨域联想

```python
# backend/creativity/cross_domain.py


class CrossDomain:
    """跨域联想

    将领域 A 的成熟方法嫁接至领域 B 的未解问题。
    """

    def cross_domain_association(
        self,
        domain_a: str,
        domain_b: str,
    ) -> dict:
        """跨域联想

        Args:
            domain_a: 源领域（方法来源）
            domain_b: 目标领域（问题所在）

        Returns:
            联想结果，包含可嫁接的方法与潜在创新点
        """
        return {
            "domain_a": domain_a,
            "domain_b": domain_b,
            "transferable_methods": self._find_transferable_methods(domain_a, domain_b),
            "potential_innovations": self._find_innovations(domain_a, domain_b),
            "challenges": self._find_challenges(domain_a, domain_b),
        }

    def trend_grafting(self, keywords: list[str]) -> dict:
        """趋势嫁接

        基于近期高频术语进行语义组合。

        Args:
            keywords: 高频关键词列表

        Returns:
            嫁接结果，包含组合创意
        """
        combinations = []
        for i, kw1 in enumerate(keywords):
            for kw2 in keywords[i + 1:]:
                combinations.append({
                    "combination": f"{kw1} + {kw2}",
                    "potential": self._evaluate_combination(kw1, kw2),
                })

        # 按潜力排序
        combinations.sort(key=lambda x: x["potential"], reverse=True)
        return {
            "keywords": keywords,
            "combinations": combinations[:10],  # 返回前 10 个
        }

    def expand_keywords(self, keywords: list[str]) -> list[str]:
        """扩展关键词

        Args:
            keywords: 原始关键词列表

        Returns:
            扩展后的关键词列表
        """
        expanded = list(keywords)
        for kw in keywords:
            # 添加同义词
            expanded.extend(self._get_synonyms(kw))
            # 添加下位词
            expanded.extend(self._get_hyponyms(kw))
        # 去重
        return list(set(expanded))

    def _find_transferable_methods(self, domain_a: str, domain_b: str) -> list[str]:
        """查找可嫁接的方法"""
        return [
            f"{domain_a}的核心算法",
            f"{domain_a}的评估方法",
            f"{domain_a}的优化策略",
        ]

    def _find_innovations(self, domain_a: str, domain_b: str) -> list[str]:
        """查找潜在创新点"""
        return [
            f"将{domain_a}的方法应用于{domain_b}的问题",
            f"融合{domain_a}与{domain_b}的理论框架",
        ]

    def _find_challenges(self, domain_a: str, domain_b: str) -> list[str]:
        """查找挑战"""
        return [
            "领域差异导致的适配问题",
            "方法迁移的有效性验证",
            "跨领域评价标准的建立",
        ]

    def _evaluate_combination(self, kw1: str, kw2: str) -> float:
        """评估组合潜力（0-1）"""
        # 简单实现：基于关键词长度与差异度
        return 0.7  # 实际实现会更复杂

    def _get_synonyms(self, keyword: str) -> list[str]:
        """获取同义词"""
        return [f"{keyword}的同义词"]

    def _get_hyponyms(self, keyword: str) -> list[str]:
        """获取下位词"""
        return [f"{keyword}的子方向"]
```

### 4.9.3 CandidateRanker 候选排序

```python
# backend/creativity/candidate_ranker.py


class CandidateRanker:
    """候选排序器

    基于灵感来源权重对候选论题打分并排序。
    """

    # 灵感来源权重
    WEIGHTS = {
        "academic_lineage": 0.3,   # 学术谱系
        "cross_domain": 0.25,      # 跨域联想
        "trend_graft": 0.2,        # 趋势嫁接
        "problem_awareness": 0.15, # 问题意识
        "novelty": 0.1,            # 新颖性
    }

    def rank_candidates(
        self,
        candidates: list[dict],
        degree: str = "master",
    ) -> list[dict]:
        """对候选论题排序

        Args:
            candidates: 候选论题列表
            degree: 学位类型

        Returns:
            按分数降序排序的候选列表
        """
        # 为每个候选打分
        for candidate in candidates:
            candidate["score"] = self._calculate_score(candidate, degree)

        # 按分数降序排序
        ranked = sorted(candidates, key=lambda x: x.get("score", 0), reverse=True)

        # 添加排名
        for i, candidate in enumerate(ranked, 1):
            candidate["rank"] = i

        return ranked

    def _calculate_score(self, candidate: dict, degree: str) -> float:
        """计算候选论题的综合分数"""
        total_score = 0.0

        for source, weight in self.WEIGHTS.items():
            source_score = candidate.get(f"{source}_score", 0)
            total_score += source_score * weight

        # 学位加权
        if degree == "doctor":
            # 博士更看重新颖性
            total_score *= 1.1 if candidate.get("novelty_score", 0) > 70 else 0.9

        return round(total_score, 2)
```

## 4.10 knowledge 模块：知识图谱

knowledge 模块管理学术谱系图谱与知识卡片。

### 4.10.1 LineageGraphStore 谱系存储

```python
# backend/knowledge/lineage_graph_store.py


class LineageGraphStore:
    """谱系图谱存储

    管理学术谱系图的节点与边，支持增删改查。
    """

    def add_node(
        self,
        node_type: str,
        title: str,
        abstract: str = "",
        metadata: dict = None,
    ) -> dict:
        """添加节点

        Args:
            node_type: 节点类型（paper/author/concept/method）
            title: 标题
            abstract: 摘要
            metadata: 元数据

        Returns:
            新建的节点
        """
        node_id = f"node_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()

        node = {
            "id": node_id,
            "node_type": node_type,
            "title": title,
            "abstract": abstract,
            "metadata": json.dumps(metadata or {}, ensure_ascii=False),
            "created_at": now,
        }

        execute_insert("lineage_nodes", node)
        return node

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        weight: float = 1.0,
    ) -> dict:
        """添加边

        Args:
            source_id: 源节点 ID
            target_id: 目标节点 ID
            relation_type: 关系类型（cites/extends/refines/contradicts）
            weight: 权重

        Returns:
            新建的边
        """
        edge_id = f"edge_{uuid.uuid4().hex[:12]}"

        edge = {
            "id": edge_id,
            "source_id": source_id,
            "target_id": target_id,
            "relation_type": relation_type,
            "weight": weight,
        }

        execute_insert("lineage_edges", edge)
        return edge

    def get_all_nodes(self) -> list[dict]:
        """获取所有节点"""
        return fetch_all("SELECT * FROM lineage_nodes ORDER BY created_at DESC")

    def get_all_edges(self) -> list[dict]:
        """获取所有边"""
        return fetch_all("SELECT * FROM lineage_edges")

    def get_node(self, node_id: str) -> dict | None:
        """获取节点详情"""
        return fetch_one(
            "SELECT * FROM lineage_nodes WHERE id = ?",
            (node_id,),
        )

    def get_node_edges(self, node_id: str) -> list[dict]:
        """获取节点的所有边"""
        return fetch_all(
            "SELECT * FROM lineage_edges WHERE source_id = ? OR target_id = ?",
            (node_id, node_id),
        )

    def search_nodes(self, query: str) -> list[dict]:
        """搜索节点"""
        return fetch_all(
            "SELECT * FROM lineage_nodes WHERE title LIKE ? OR abstract LIKE ?",
            (f"%{query}%", f"%{query}%"),
        )

    def delete_node(self, node_id: str):
        """删除节点（级联删除相关边）"""
        execute_query("DELETE FROM lineage_edges WHERE source_id = ? OR target_id = ?", (node_id, node_id))
        execute_query("DELETE FROM lineage_nodes WHERE id = ?", (node_id,))

    def get_graph_data(self) -> dict:
        """获取完整图谱数据（用于 D3.js 渲染）"""
        nodes = self.get_all_nodes()
        edges = self.get_all_edges()

        # 转换为 D3.js 格式
        d3_nodes = [
            {
                "id": n["id"],
                "type": n["node_type"],
                "title": n["title"],
                "abstract": n["abstract"],
            }
            for n in nodes
        ]
        d3_links = [
            {
                "source": e["source_id"],
                "target": e["target_id"],
                "relation": e["relation_type"],
                "weight": e["weight"],
            }
            for e in edges
        ]

        return {"nodes": d3_nodes, "links": d3_links}
```

### 4.10.2 CardManager 知识卡片

```python
# backend/knowledge/card_manager.py


class CardManager:
    """知识卡片管理器

    管理知识卡片的增删改查。
    """

    def create_card(
        self,
        title: str,
        content: str,
        tags: list[str] = None,
        source: str = "",
    ) -> dict:
        """创建知识卡片

        Args:
            title: 卡片标题
            content: 卡片内容
            tags: 标签列表
            source: 来源

        Returns:
            新建的卡片
        """
        card_id = f"card_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()

        card = {
            "id": card_id,
            "title": title,
            "content": content,
            "tags": json.dumps(tags or [], ensure_ascii=False),
            "source": source,
            "created_at": now,
            "updated_at": now,
        }

        execute_insert("knowledge_cards", card)
        return card

    def get_card(self, card_id: str) -> dict | None:
        """获取卡片详情"""
        card = fetch_one(
            "SELECT * FROM knowledge_cards WHERE id = ?",
            (card_id,),
        )
        if card and card.get("tags"):
            card["tags"] = json.loads(card["tags"])
        return card

    def list_cards(self, tag: str = None, limit: int = 20) -> list[dict]:
        """列出卡片

        Args:
            tag: 按标签过滤
            limit: 返回数量

        Returns:
            卡片列表
        """
        if tag:
            cards = fetch_all(
                "SELECT * FROM knowledge_cards WHERE tags LIKE ? ORDER BY created_at DESC LIMIT ?",
                (f"%{tag}%", limit),
            )
        else:
            cards = fetch_all(
                "SELECT * FROM knowledge_cards ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )

        for card in cards:
            if card.get("tags"):
                card["tags"] = json.loads(card["tags"])

        return cards

    def update_card(self, card_id: str, updates: dict) -> dict | None:
        """更新卡片"""
        updates["updated_at"] = datetime.now().isoformat()
        if "tags" in updates:
            updates["tags"] = json.dumps(updates["tags"], ensure_ascii=False)

        # 构建更新语句
        set_parts = [f"{k} = ?" for k in updates.keys()]
        values = list(updates.values()) + [card_id]

        execute_query(
            f"UPDATE knowledge_cards SET {', '.join(set_parts)} WHERE id = ?",
            values,
        )
        return self.get_card(card_id)

    def delete_card(self, card_id: str) -> bool:
        """删除卡片"""
        execute_query("DELETE FROM knowledge_cards WHERE id = ?", (card_id,))
        return True
```

## 4.11 budgets 模块：预算与账本

budgets 模块负责 LLM 调用成本的追踪、估算与控制。

### 4.11.1 TransparentLedger 透明账本

```python
# backend/budgets/transparent_ledger.py

from datetime import datetime


class TransparentLedger:
    """透明账本

    记录每一次 LLM 调用的 Token 用量与成本，
    支持按会话/模型/时间维度查询。
    """

    def record(
        self,
        session_id: str,
        model_id: str,
        agent_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost: float,
        cache_hit: bool = False,
    ) -> dict:
        """记录一次 LLM 调用

        Args:
            session_id: 会话 ID
            model_id: 模型 ID
            agent_id: Agent ID
            prompt_tokens: 输入 Token 数
            completion_tokens: 输出 Token 数
            cost: 成本（元）
            cache_hit: 是否缓存命中

        Returns:
            账本条目
        """
        entry_id = f"ledger_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()

        entry = {
            "id": entry_id,
            "session_id": session_id,
            "model_id": model_id,
            "agent_id": agent_id,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cost": cost,
            "cache_hit": cache_hit,
            "created_at": now,
        }

        execute_insert("budget_ledger", entry)
        return entry

    def get_ledger_entries(
        self,
        session_id: str = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """获取账本条目

        Args:
            session_id: 按会话过滤
            limit: 返回数量
            offset: 偏移量

        Returns:
            账本条目列表
        """
        if session_id:
            return fetch_all(
                "SELECT * FROM budget_ledger WHERE session_id = ? "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (session_id, limit, offset),
            )
        else:
            return fetch_all(
                "SELECT * FROM budget_ledger ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )

    def get_ledger_summary(self) -> dict:
        """获取账本汇总统计"""
        row = fetch_one(
            "SELECT "
            "COUNT(*) as total_calls, "
            "SUM(prompt_tokens) as total_prompt_tokens, "
            "SUM(completion_tokens) as total_completion_tokens, "
            "SUM(total_tokens) as total_tokens, "
            "SUM(cost) as total_cost, "
            "SUM(CASE WHEN cache_hit = 1 THEN 1 ELSE 0 END) as cache_hits "
            "FROM budget_ledger"
        )

        if not row:
            return {
                "total_calls": 0,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
                "cache_hits": 0,
                "cache_hit_rate": 0.0,
            }

        total_calls = row["total_calls"] or 0
        cache_hits = row["cache_hits"] or 0

        return {
            "total_calls": total_calls,
            "total_prompt_tokens": row["total_prompt_tokens"] or 0,
            "total_completion_tokens": row["total_completion_tokens"] or 0,
            "total_tokens": row["total_tokens"] or 0,
            "total_cost": row["total_cost"] or 0.0,
            "cache_hits": cache_hits,
            "cache_hit_rate": cache_hits / total_calls if total_calls > 0 else 0.0,
        }

    def get_session_cost(self, session_id: str) -> dict:
        """获取指定会话的费用统计"""
        row = fetch_one(
            "SELECT "
            "COUNT(*) as calls, "
            "SUM(total_tokens) as tokens, "
            "SUM(cost) as cost "
            "FROM budget_ledger WHERE session_id = ?",
            (session_id,),
        )

        if not row:
            return {"session_id": session_id, "calls": 0, "tokens": 0, "cost": 0.0}

        return {
            "session_id": session_id,
            "calls": row["calls"] or 0,
            "tokens": row["tokens"] or 0,
            "cost": row["cost"] or 0.0,
        }
```

### 4.11.2 BudgetEstimator 预算估算器

```python
# backend/budgets/estimator.py


class BudgetEstimator:
    """预算估算器

    根据学位类型与生成模式估算会话级预算。
    """

    # 学位对应的估算参数
    ESTIMATES = {
        "master": {
            "stages": 5,
            "avg_calls_per_stage": 3,
            "avg_tokens_per_call": 2000,
        },
        "doctor": {
            "stages": 5,
            "avg_calls_per_stage": 5,
            "avg_tokens_per_call": 3000,
        },
    }

    # 模式对应的成本系数
    MODE_FACTORS = {
        "standard": 1.0,
        "deep": 1.5,
        "fast": 0.7,
    }

    def estimate_session_budget(
        self,
        degree: str,
        mode: str = "standard",
        count: int = 5,
    ) -> dict:
        """估算会话级预算

        Args:
            degree: 学位类型
            mode: 生成模式（standard/deep/fast）
            count: 候选论题数量

        Returns:
            预算估算结果
        """
        params = self.ESTIMATES.get(degree, self.ESTIMATES["master"])
        mode_factor = self.MODE_FACTORS.get(mode, 1.0)

        # 计算总调用次数
        total_calls = params["stages"] * params["avg_calls_per_stage"] * count
        total_calls = int(total_calls * mode_factor)

        # 计算总 Token 数
        total_tokens = total_calls * params["avg_tokens_per_call"]

        # 估算成本（使用平均价格）
        avg_input_price = 5.0  # 元/百万 Token
        avg_output_price = 20.0
        prompt_tokens = int(total_tokens * 0.7)
        completion_tokens = int(total_tokens * 0.3)

        estimated_cost = (
            prompt_tokens * avg_input_price / 1_000_000
            + completion_tokens * avg_output_price / 1_000_000
        )

        return {
            "degree": degree,
            "mode": mode,
            "count": count,
            "estimated_calls": total_calls,
            "estimated_tokens": {
                "prompt": prompt_tokens,
                "completion": completion_tokens,
                "total": total_tokens,
            },
            "estimated_cost_cny": round(estimated_cost, 2),
            "breakdown": {
                "stages": params["stages"],
                "calls_per_stage": params["avg_calls_per_stage"],
                "tokens_per_call": params["avg_tokens_per_call"],
                "mode_factor": mode_factor,
            },
        }
```

---

<!-- PART2_END_MARKER -->
