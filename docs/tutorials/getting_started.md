# ThesisMiner v8.0 入门教程

> 本教程面向首次使用 ThesisMiner 的用户与开发者，将带领你从零开始完成环境准备、首次运行、五阶段流程实操、多对话管理、谱系图谱使用、预算监控等核心操作。完成本教程后，你将能够独立使用 ThesisMiner 生成高质量的学术论题，并理解系统的整体工作原理。

---

## 目录

- [1. 教程概述](#1-教程概述)
- [2. 环境准备](#2-环境准备)
  - [2.1 系统要求](#21-系统要求)
  - [2.2 Python 环境安装](#22-python-环境安装)
  - [2.3 虚拟环境创建](#23-虚拟环境创建)
  - [2.4 依赖安装](#24-依赖安装)
  - [2.5 API Key 配置](#25-api-key-配置)
  - [2.6 数据库初始化](#26-数据库初始化)
- [3. 首次运行](#3-首次运行)
  - [3.1 启动服务器](#31-启动服务器)
  - [3.2 打开浏览器](#32-打开浏览器)
  - [3.3 首次配置向导](#33-首次配置向导)
  - [3.4 模型连通性测试](#34-模型连通性测试)
- [4. 五阶段流程实操](#4-五阶段流程实操)
  - [4.1 阶段一：信息确权](#41-阶段一信息确权)
  - [4.2 阶段二：创意生成](#42-阶段二创意生成)
  - [4.3 阶段三：校验与回退](#43-阶段三校验与回退)
  - [4.4 阶段四：多粒度生成](#44-阶段四多粒度生成)
  - [4.5 阶段五：深度辅助三件套](#45-阶段五深度辅助三件套)
- [5. 多对话管理](#5-多对话管理)
  - [5.1 创建新对话](#51-创建新对话)
  - [5.2 切换对话](#52-切换对话)
  - [5.3 重命名对话](#53-重命名对话)
  - [5.4 删除对话](#54-删除对话)
  - [5.5 上下文隔离验证](#55-上下文隔离验证)
- [6. 谱系图谱使用](#6-谱系图谱使用)
  - [6.1 图谱浏览](#61-图谱浏览)
  - [6.2 拖拽与缩放](#62-拖拽与缩放)
  - [6.3 节点类型过滤](#63-节点类型过滤)
  - [6.4 节点详情查看](#64-节点详情查看)
  - [6.5 批量操作](#65-批量操作)
- [7. 预算监控](#7-预算监控)
  - [7.1 账本查看](#71-账本查看)
  - [7.2 成本分析](#72-成本分析)
  - [7.3 缓存命中率](#73-缓存命中率)
  - [7.4 导出报表](#74-导出报表)
- [8. 常见操作速查](#8-常见操作速查)
  - [8.1 快捷键速查表](#81-快捷键速查表)
  - [8.2 命令行速查](#82-命令行速查)
  - [8.3 配置项速查](#83-配置项速查)
- [9. 下一步学习](#9-下一步学习)

---

## 1. 教程概述

### 1.1 本教程适合谁

本教程适合以下人群：

- **研究生新生**：刚刚开始准备学位论文选题，希望借助 AI 工具生成高质量论题
- **科研工作者**：需要快速探索研究方向、评估论题可行性
- **开发者**：希望了解 ThesisMiner 的架构与扩展能力，进行二次开发
- **系统管理员**：需要部署与运维 ThesisMiner 实例

### 1.2 学习目标

完成本教程后，你将能够：

1. 在本地成功安装并运行 ThesisMiner v8.0
2. 配置多个 AI 模型并理解步骤路由策略
3. 完整走通五阶段闭环导航流程（信息确权 → 创意生成 → 校验回退 → 多粒度生成 → 深度辅助）
4. 管理多个并行对话，理解上下文隔离机制
5. 使用 D3.js 谱系图谱浏览学术谱系
6. 监控 Token 预算与缓存命中率
7. 掌握常用快捷键与命令行操作

### 1.3 预计学习时长

| 阶段 | 内容 | 预计时长 |
|------|------|----------|
| 环境准备 | 安装 Python、依赖、配置 API Key | 30-45 分钟 |
| 首次运行 | 启动服务、配置向导、模型测试 | 15-20 分钟 |
| 五阶段实操 | 完整走通一次论题生成流程 | 60-90 分钟 |
| 多对话管理 | 创建、切换、删除对话 | 15-20 分钟 |
| 谱系图谱 | 浏览、过滤、导出 | 20-30 分钟 |
| 预算监控 | 查看账本、分析成本 | 15-20 分钟 |
| **总计** | **完整入门** | **约 2.5-3.5 小时** |

### 1.4 教程约定

本教程使用以下约定：

- **Linux/macOS 命令**：以 `$` 开头
- **Windows PowerShell 命令**：以 `PS>` 开头
- **浏览器操作**：以「」标注按钮或菜单名称
- **重要提示**：以 > 标注
- **警告信息**：以 ⚠️ 标注
- **代码示例**：使用代码块标注语言类型

---

## 2. 环境准备

### 2.1 系统要求

#### 2.1.1 硬件要求

| 资源 | 最低要求 | 推荐配置 |
|------|----------|----------|
| CPU | 双核 2.0 GHz | 四核 2.5 GHz 及以上 |
| 内存 | 2 GB | 4 GB 及以上 |
| 磁盘 | 500 MB 可用空间 | 2 GB 及以上（含日志与缓存） |
| 网络 | 可访问 AI API 端点 | 稳定的宽带连接 |

#### 2.1.2 操作系统支持

ThesisMiner v8.0 支持以下操作系统：

- **Windows**：Windows 10 64 位及以上、Windows Server 2016 及以上
- **macOS**：macOS 10.15 (Catalina) 及以上
- **Linux**：Ubuntu 18.04 / CentOS 7 / Debian 10 及以上（需 glibc 2.17+）

#### 2.1.3 软件依赖

| 软件 | 最低版本 | 推荐版本 | 用途 |
|------|----------|----------|------|
| Python | 3.10 | 3.11 或 3.12 | 运行时环境 |
| pip | 22.0 | 最新版 | 包管理 |
| Git | 2.20 | 最新版 | 源码获取 |
| Node.js | 18.0 | 20 LTS | 前端构建（可选） |
| SQLite | 3.35 | 3.40+ | 数据库（Python 自带） |

> ThesisMiner 使用 Python 自带的 `sqlite3` 模块，无需单独安装 SQLite。但建议系统 SQLite 版本 ≥ 3.35 以支持 RETURNING 子句等新特性。

### 2.2 Python 环境安装

#### 2.2.1 Windows 安装 Python

**步骤 1：下载 Python**

访问 Python 官方网站 https://www.python.org/downloads/ ，下载 Python 3.11 或 3.12 的 Windows 安装包（64 位）。

**步骤 2：运行安装程序**

双击下载的安装包，在安装界面：

1. 勾选「Add Python 3.x to PATH」选项（重要！）
2. 选择「Customize installation」
3. 在「Optional Features」中勾选所有选项
4. 在「Advanced Options」中勾选「Install for all users」
5. 设置安装路径为 `C:\Python311`（避免路径含空格）
6. 点击「Install」开始安装

**步骤 3：验证安装**

打开 PowerShell，执行：

```powershell
PS> python --version
Python 3.11.7

PS> pip --version
pip 23.3.1 from C:\Python311\Lib\site-packages\pip (python 3.11)
```

#### 2.2.2 macOS 安装 Python

**方式一：使用 Homebrew（推荐）**

```bash
# 安装 Homebrew（如未安装）
$ /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安装 Python 3.11
$ brew install python@3.11

# 验证安装
$ python3.11 --version
Python 3.11.7
```

**方式二：使用官方安装包**

访问 https://www.python.org/downloads/macos/ 下载 macOS 安装包，双击安装。

#### 2.2.3 Linux 安装 Python

**Ubuntu / Debian：**

```bash
$ sudo apt update
$ sudo apt install -y python3.11 python3.11-venv python3.11-dev
$ python3.11 --version
```

**CentOS / RHEL：**

```bash
$ sudo yum install -y python3.11 python3.11-devel
$ python3.11 --version
```

> 如果系统仓库中没有 Python 3.11，可以使用 pyenv 或编译源码安装。详见高级特性教程。

### 2.3 虚拟环境创建

为避免与系统 Python 环境冲突，强烈建议使用虚拟环境。

#### 2.3.1 使用 venv 创建虚拟环境

**Windows PowerShell：**

```powershell
# 进入项目目录
PS> cd D:\CodeProject\ThesisMiner

# 创建虚拟环境
PS> python -m venv .venv

# 激活虚拟环境
PS> .\.venv\Scripts\Activate.ps1

# 验证激活（提示符前会出现 (.venv) 标识）
(.venv) PS> python --version
```

> 如果 PowerShell 执行策略限制脚本运行，执行：
> `PS> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`

**macOS / Linux：**

```bash
# 进入项目目录
$ cd ~/CodeProject/ThesisMiner

# 创建虚拟环境
$ python3.11 -m venv .venv

# 激活虚拟环境
$ source .venv/bin/activate

# 验证激活
(.venv) $ python --version
```

#### 2.3.2 使用 conda 创建虚拟环境（可选）

如果你使用 Anaconda 或 Miniconda：

```bash
# 创建虚拟环境
$ conda create -n thesisminer python=3.11

# 激活虚拟环境
$ conda activate thesisminer

# 验证
(thesisminer) $ python --version
```

#### 2.3.3 虚拟环境管理常用命令

| 操作 | Windows | macOS / Linux |
|------|---------|---------------|
| 激活 | `.\.venv\Scripts\Activate.ps1` | `source .venv/bin/activate` |
| 退出 | `deactivate` | `deactivate` |
| 删除 | 删除 `.venv` 目录 | `rm -rf .venv` |
| 查看已安装包 | `pip list` | `pip list` |
| 导出依赖 | `pip freeze > requirements.txt` | `pip freeze > requirements.txt` |

### 2.4 依赖安装

#### 2.4.1 获取源码

```bash
# 使用 Git 克隆仓库
$ git clone https://github.com/your-org/thesisminer.git
$ cd thesisminer

# 或解压已下载的源码包
$ tar -xzf thesisminer-v8.0.tar.gz
$ cd thesisminer-v8.0
```

#### 2.4.2 安装 Python 依赖

确保虚拟环境已激活，然后执行：

```bash
# 升级 pip
(.venv) $ python -m pip install --upgrade pip

# 安装核心依赖
(.venv) $ pip install -r requirements.txt
```

`requirements.txt` 主要包含以下依赖：

```
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
httpx==0.25.2
python-dotenv==1.0.0
sse-starlette==1.8.2
simhash==2.1.2
datasketch==1.6.4
tiktoken==0.5.2
```

#### 2.4.3 验证依赖安装

```bash
(.venv) $ python -c "import fastapi; import uvicorn; import httpx; print('依赖安装成功')"
依赖安装成功
```

#### 2.4.4 安装开发依赖（可选）

如果你需要参与开发或运行测试：

```bash
(.venv) $ pip install -r requirements-dev.txt
```

开发依赖包含：

```
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
black==23.11.0
ruff==0.1.6
mypy==1.7.0
httpx==0.25.2
```

#### 2.4.5 常见安装问题

**问题 1：安装 httpx 报错 `error: Microsoft Visual C++ 14.0 is required`**

解决方案：安装 Microsoft C++ Build Tools。

1. 访问 https://visualstudio.microsoft.com/visual-cpp-build-tools/
2. 下载并安装 Build Tools
3. 在安装选项中勾选「C++ build tools」
4. 重新执行 `pip install -r requirements.txt`

**问题 2：安装 tiktoken 报错 `error: command 'gcc' failed`**

解决方案（Linux）：

```bash
$ sudo apt install -y build-essential python3.11-dev
```

解决方案（macOS）：

```bash
$ xcode-select --install
```

**问题 3：pip 安装速度慢**

使用国内镜像源：

```bash
# 临时使用
(.venv) $ pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 永久配置
(.venv) $ pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2.5 API Key 配置

ThesisMiner 需要配置至少一个 AI 模型的 API Key 才能正常工作。v8.0 支持多模型注册与步骤路由。

#### 2.5.1 获取 API Key

ThesisMiner 支持以下模型提供商：

| 提供商 | 模型示例 | 获取地址 |
|--------|----------|----------|
| DeepSeek | deepseek-r2, deepseek-coder | https://platform.deepseek.com/ |
| Anthropic | claude-opus-4.5, claude-sonnet-4 | https://console.anthropic.com/ |
| OpenAI | gpt-4.1, gpt-4-turbo | https://platform.openai.com/ |
| 智谱 AI | glm-4-plus, glm-4-air | https://open.bigmodel.cn/ |
| 月之暗面 | moonshot-v1-128k | https://platform.moonshot.cn/ |

> 推荐至少配置 DeepSeek 与 OpenAI 两个提供商，以体验步骤路由功能。

#### 2.5.2 创建配置文件

在项目根目录创建 `.env` 文件：

```bash
# 复制示例配置
(.venv) $ cp .env.example .env
```

编辑 `.env` 文件，填入你的 API Key：

```env
# ============ DeepSeek 配置 ============
DEEPSEEK_API_KEY=sk-your-deepseek-api-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# ============ OpenAI 配置 ============
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_BASE_URL=https://api.openai.com/v1

# ============ Anthropic 配置 ============
ANTHROPIC_API_KEY=sk-ant-your-anthropic-api-key-here
ANTHROPIC_BASE_URL=https://api.anthropic.com/v1

# ============ 智谱 AI 配置（可选）============
ZHIPU_API_KEY=your-zhipu-api-key-here
ZHIPU_BASE_URL=https://open.bigmodel.cn/api/paas/v4

# ============ 月之暗面配置（可选）============
MOONSHOT_API_KEY=your-moonshot-api-key-here
MOONSHOT_BASE_URL=https://api.moonshot.cn/v1

# ============ 系统配置 ============
SECRET_KEY=please-change-this-to-a-random-string-of-at-least-32-characters
DATABASE_URL=sqlite:///./thesisminer.db
LOG_LEVEL=INFO

# ============ 服务配置 ============
HOST=0.0.0.0
PORT=8000
WORKERS=1

# ============ 缓存配置 ============
CACHE_ENABLED=true
CACHE_TTL_SECONDS=3600
```

> ⚠️ **安全提示**：`.env` 文件包含敏感信息，请确保它已被 `.gitignore` 排除，不要提交到版本控制系统。

#### 2.5.3 验证配置加载

```bash
(.venv) $ python -c "from backend.config import get_settings; s = get_settings(); print(f'已加载配置：DeepSeek={bool(s.deepseek_api_key)}, OpenAI={bool(s.openai_api_key)}')"
已加载配置：DeepSeek=True, OpenAI=True
```

#### 2.5.4 配置步骤路由（可选）

ThesisMiner v8.0 支持按步骤路由到不同模型。编辑 `backend/config.py` 中的 `MODEL_ROUTING` 配置：

```python
MODEL_ROUTING = {
    "information_confirmation": "deepseek-r2",      # 信息确权：使用 DeepSeek
    "ideation": "claude-opus-4.5",                  # 创意生成：使用 Claude
    "validation": "deepseek-r2",                    # 校验：使用 DeepSeek
    "generation": "gpt-4.1",                        # 生成：使用 GPT-4
    "deep_assistance": "claude-opus-4.5",           # 深度辅助：使用 Claude
}
```

默认路由策略：

| 阶段 | 默认模型 | 选择理由 |
|------|----------|----------|
| 信息确权 | deepseek-r2 | 性价比高，支持缓存 |
| 创意生成 | claude-opus-4.5 | 创造力强，逻辑严谨 |
| 校验 | deepseek-r2 | 严格遵循规则，支持缓存 |
| 生成 | gpt-4.1 | 长文本生成质量高 |
| 深度辅助 | claude-opus-4.5 | 综合能力强 |

### 2.6 数据库初始化

ThesisMiner 使用 SQLite 作为默认数据库，无需单独安装数据库服务。

#### 2.6.1 自动初始化

首次启动服务时，系统会自动创建数据库并执行迁移：

```bash
(.venv) $ python -m backend.main
INFO:backend.database:正在初始化数据库...
INFO:backend.database:数据库迁移完成
INFO:backend.main:ThesisMiner v8.0 启动中...
```

#### 2.6.2 手动初始化

如需手动初始化数据库（例如排查问题）：

```bash
(.venv) $ python -m backend.database init
INFO:backend.database:数据库文件已创建：./thesisminer.db
INFO:backend.database:已执行 12 个迁移脚本
INFO:backend.database:初始数据已写入
```

#### 2.6.3 验证数据库

```bash
# 查看数据库表
(.venv) $ python -m backend.database tables
+-------------------------+
| 表名                    |
+-------------------------+
| sessions                |
| conversations           |
| messages                |
| proposals               |
| lineage_nodes           |
| lineage_edges           |
| budget_ledger           |
| cache_entries           |
| model_configs           |
| agent_runs              |
| audit_logs              |
| constraints             |
+-------------------------+

# 查看初始数据
(.venv) $ python -m backend.database seed --list
已加载 6 个默认模型配置
已加载 4 个默认 Agent 配置
已加载 8 个默认约束规则
```

#### 2.6.4 数据库文件位置

默认数据库文件位于项目根目录的 `thesisminer.db`。如需修改位置，编辑 `.env`：

```env
DATABASE_URL=sqlite:///./data/thesisminer.db
```

> 建议将数据库文件放在 `data/` 目录下，便于备份与管理。

#### 2.6.5 重置数据库

如需重置数据库（⚠️ 会删除所有数据）：

```bash
(.venv) $ python -m backend.database reset --confirm
WARNING: 此操作将删除所有数据！
确认重置？(yes/no): yes
INFO:backend.database:数据库已重置
INFO:backend.database:已重新执行迁移与种子数据
```

---

## 3. 首次运行

### 3.1 启动服务器

#### 3.1.1 开发模式启动

```bash
(.venv) $ python -m backend.main
INFO:backend.main:ThesisMiner v8.0 启动中...
INFO:backend.config:已加载配置文件：.env
INFO:backend.database:数据库连接成功
INFO:backend.agents:已注册 4 个 Agent：Reasoner, Mentor, Searcher, Critic
INFO:uvicorn.error:Started server process [12345]
INFO:uvicorn.error:Waiting for application startup.
INFO:uvicorn.error:Application startup complete.
INFO:uvicorn.error:Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

#### 3.1.2 使用 uvicorn 启动（支持热重载）

```bash
(.venv) $ uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

参数说明：

| 参数 | 说明 |
|------|------|
| `--reload` | 代码变更后自动重启（开发模式） |
| `--host 0.0.0.0` | 监听所有网络接口 |
| `--port 8000` | 监听端口 |
| `--workers 4` | 工作进程数（生产模式） |

#### 3.1.3 后台启动（Linux/macOS）

```bash
# 使用 nohup
$ nohup python -m backend.main > thesisminer.log 2>&1 &

# 查看进程
$ ps aux | grep thesisminer

# 停止服务
$ kill <PID>
```

#### 3.1.4 Windows 服务启动

```powershell
# 使用 NSSM 安装为 Windows 服务
PS> nssm install ThesisMiner "D:\CodeProject\ThesisMiner\.venv\Scripts\python.exe" "-m backend.main"
PS> nssm start ThesisMiner
```

### 3.2 打开浏览器

#### 3.2.1 访问 Web 界面

服务器启动后，打开浏览器访问：

```
http://localhost:8000
```

你将看到 ThesisMiner v8.0 的欢迎界面：

```
+----------------------------------------------------------+
|                    ThesisMiner v8.0                       |
|              学术论题智能生成与导航系统                     |
+----------------------------------------------------------+
|                                                          |
|  欢迎使用 ThesisMiner！首次使用请完成配置向导。            |
|                                                          |
|  [开始配置向导]    [跳过，直接使用]                       |
|                                                          |
+----------------------------------------------------------+
| 版本：v8.0.0  |  状态：运行中  |  模型：3 个已配置         |
+----------------------------------------------------------+
```

#### 3.2.2 访问 API 文档

ThesisMiner 提供交互式 API 文档：

- **Swagger UI**：http://localhost:8000/docs
- **ReDoc**：http://localhost:8000/redoc
- **OpenAPI Schema**：http://localhost:8000/openapi.json

#### 3.2.3 健康检查

```bash
$ curl http://localhost:8000/api/health
{
  "status": "healthy",
  "version": "8.0.0",
  "uptime_seconds": 120,
  "database": "connected",
  "models": {
    "deepseek-r2": "available",
    "claude-opus-4.5": "available",
    "gpt-4.1": "available"
  },
  "agents": ["Reasoner", "Mentor", "Searcher", "Critic"]
}
```

### 3.3 首次配置向导

首次访问 Web 界面时，系统会引导你完成配置向导。

#### 3.3.1 步骤一：基本信息配置

```
+----------------------------------------------------------+
|  配置向导 - 步骤 1/4：基本信息                             |
+----------------------------------------------------------+
|                                                          |
|  系统名称：[ThesisMiner v8.0          ]                  |
|  管理员邮箱：[admin@example.com       ]                  |
|  时区：[Asia/Shanghai          ▼]                        |
|  语言：[简体中文              ▼]                         |
|                                                          |
|                              [上一步]  [下一步]           |
+----------------------------------------------------------+
```

#### 3.3.2 步骤二：模型配置

```
+----------------------------------------------------------+
|  配置向导 - 步骤 2/4：模型配置                             |
+----------------------------------------------------------+
|                                                          |
|  已检测到的 API Key：                                      |
|  ✓ DeepSeek (deepseek-r2)                                |
|  ✓ OpenAI (gpt-4.1)                                      |
|  ✓ Anthropic (claude-opus-4.5)                           |
|  ✗ 智谱 AI (未配置)                                       |
|  ✗ 月之暗面 (未配置)                                      |
|                                                          |
|  步骤路由配置：                                            |
|  信息确权：[deepseek-r2          ▼]                      |
|  创意生成：[claude-opus-4.5     ▼]                      |
|  校验：    [deepseek-r2          ▼]                      |
|  生成：    [gpt-4.1             ▼]                      |
|  深度辅助：[claude-opus-4.5     ▼]                      |
|                                                          |
|                              [上一步]  [下一步]           |
+----------------------------------------------------------+
```

#### 3.3.3 步骤三：约束配置

```
+----------------------------------------------------------+
|  配置向导 - 步骤 3/4：约束配置                             |
+----------------------------------------------------------+
|                                                          |
|  硬约束规则（启用/禁用）：                                  |
|  [✓] 标题长度 15-40 字符                                  |
|  [✓] 学科匹配验证                                         |
|  [✓] 导师方向一致性                                       |
|  [✓] 时间可行性检查                                       |
|  [✓] 重复度 ≤ 30%                                        |
|  [✓] AI 痕迹检测                                          |
|                                                          |
|  评估阈值：                                               |
|  新颖性最低分：[60        ]                               |
|  可行性最低分：[60        ]                               |
|  风格质量最低分：[70      ]                               |
|                                                          |
|                              [上一步]  [下一步]           |
+----------------------------------------------------------+
```

#### 3.3.4 步骤四：完成

```
+----------------------------------------------------------+
|  配置向导 - 步骤 4/4：完成                                |
+----------------------------------------------------------+
|                                                          |
|  ✓ 基本信息已保存                                         |
|  ✓ 模型配置已保存                                         |
|  ✓ 约束配置已保存                                         |
|                                                          |
|  配置摘要：                                               |
|  - 已配置 3 个模型                                        |
|  - 已启用 6 条硬约束                                      |
|  - 已设置评估阈值                                         |
|                                                          |
|  [完成配置，开始使用]                                     |
+----------------------------------------------------------+
```

### 3.4 模型连通性测试

配置完成后，建议测试每个模型的连通性。

#### 3.4.1 通过 Web 界面测试

1. 进入「设置」→「模型管理」
2. 点击每个模型旁的「测试连接」按钮
3. 等待测试结果（通常 2-5 秒）

```
+----------------------------------------------------------+
|  模型管理                                                 |
+----------------------------------------------------------+
|  模型名称          | 状态      | 延迟    | [测试连接]    |
|-------------------|-----------|---------|---------------|
|  deepseek-r2      | ✓ 可用    | 320 ms  | [测试连接]    |
|  claude-opus-4.5  | ✓ 可用    | 890 ms  | [测试连接]    |
|  gpt-4.1          | ✓ 可用    | 450 ms  | [测试连接]    |
+----------------------------------------------------------+
```

#### 3.4.2 通过 API 测试

```bash
# 测试 DeepSeek
$ curl -X POST http://localhost:8000/api/models/test \
  -H "Content-Type: application/json" \
  -d '{"model": "deepseek-r2"}'
{
  "model": "deepseek-r2",
  "status": "available",
  "latency_ms": 320,
  "timestamp": "2026-06-19T10:30:00Z"
}

# 测试所有模型
$ curl http://localhost:8000/api/models/health
{
  "models": [
    {"name": "deepseek-r2", "status": "available", "latency_ms": 320},
    {"name": "claude-opus-4.5", "status": "available", "latency_ms": 890},
    {"name": "gpt-4.1", "status": "available", "latency_ms": 450}
  ]
}
```

#### 3.4.3 通过命令行测试

```bash
(.venv) $ python -m backend.cli models test
测试模型连通性...

[1/3] deepseek-r2          ✓ 可用 (320 ms)
[2/3] claude-opus-4.5      ✓ 可用 (890 ms)
[3/3] gpt-4.1              ✓ 可用 (450 ms)

所有模型均可正常访问。
```

#### 3.4.4 常见连接问题

**问题：API Key 无效**

```
错误：401 Unauthorized
原因：API Key 错误或已过期
解决：检查 .env 文件中的 API Key 是否正确
```

**问题：连接超时**

```
错误：TimeoutError
原因：网络问题或 API 端点不可达
解决：
1. 检查网络连接
2. 确认 BASE_URL 是否正确
3. 尝试使用代理（如在国内访问 OpenAI）
```

**问题：余额不足**

```
错误：402 Payment Required
原因：API 账户余额不足
解决：登录对应平台充值
```

---

## 4. 五阶段流程实操

ThesisMiner v8.0 的核心是五阶段闭环导航流程。本节将通过一个完整示例，带你走通整个流程。

### 4.1 阶段一：信息确权

信息确权阶段用于收集用户的基本信息，包括学位类型、学科方向、导师信息、研究兴趣等。

#### 4.1.1 创建新会话

1. 在 Web 界面点击「新建会话」按钮
2. 输入会话名称（例如：「计算机视觉方向硕士论题」）
3. 选择学位类型：硕士
4. 点击「创建」

```
+----------------------------------------------------------+
|  新建会话                                                 |
+----------------------------------------------------------+
|  会话名称：[计算机视觉方向硕士论题    ]                    |
|  学位类型：[硕士          ▼]                              |
|  学科门类：[工学          ▼]                              |
|  一级学科：[计算机科学与技术 ▼]                            |
|                                                          |
|                              [取消]  [创建]               |
+----------------------------------------------------------+
```

#### 4.1.2 填写信息确权表单

系统会引导你填写以下信息：

**基本信息：**

| 字段 | 示例值 | 说明 |
|------|--------|------|
| 学位类型 | 硕士 | 学士/硕士/博士 |
| 学科门类 | 工学 | 用于学科匹配约束 |
| 一级学科 | 计算机科学与技术 | 用于检索相关文献 |
| 研究方向 | 计算机视觉 | 细分研究方向 |
| 入学年份 | 2024 | 用于时间可行性评估 |

**导师信息：**

| 字段 | 示例值 | 说明 |
|------|--------|------|
| 导师姓名 | 张教授 | 用于谱系图谱构建 |
| 导师研究方向 | 图像识别、深度学习 | 用于方向一致性约束 |
| 导师近期项目 | 医学影像分析（国家自然科学基金） | 用于导师项目延伸创意 |
| 导师代表性论文 | 5 篇（系统自动检索） | 用于谱系继承 |

**研究兴趣：**

```
+----------------------------------------------------------+
|  研究兴趣（可多选，至少 3 项）                              |
+----------------------------------------------------------+
|  [✓] 图像分类                                             |
|  [✓] 目标检测                                             |
|  [✓] 图像分割                                             |
|  [ ] 图像生成                                             |
|  [ ] 视频理解                                             |
|  [✓] 医学影像分析                                         |
|  [ ] 遥感图像处理                                         |
|  [ ] 三维视觉                                             |
|                                                          |
|  其他兴趣（可选）：                                        |
|  [小样本学习、迁移学习                              ]      |
+----------------------------------------------------------+
```

**约束条件：**

| 字段 | 示例值 | 说明 |
|------|--------|------|
| 论题类型 | 应用研究 | 理论/应用/综述 |
| 预期工作量 | 中等 | 轻/中/重 |
| 实验条件 | 有 GPU 服务器 | 影响可行性评估 |
| 时间限制 | 12 个月 | 影响时间可行性 |

#### 4.1.3 提交信息确权

填写完成后，点击「提交信息」按钮。系统会调用 ReasonerAgent 进行信息整理：

```
[系统] 正在分析你的信息...
[ReasonerAgent] 已提取关键信息：
  - 学位：硕士
  - 学科：计算机科学与技术 / 计算机视觉
  - 导师：张教授（图像识别、深度学习）
  - 兴趣：图像分类、目标检测、医学影像分析
  - 约束：应用研究、12 个月、有 GPU

[ReasonerAgent] 已构建初始上下文，准备进入创意生成阶段。
```

#### 4.1.4 通过 API 完成信息确权

```bash
# 创建会话
$ curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "name": "计算机视觉方向硕士论题",
    "degree": "master",
    "discipline": "computer_science"
  }'
{
  "session_id": "sess_abc123",
  "name": "计算机视觉方向硕士论题",
  "degree": "master",
  "created_at": "2026-06-19T10:35:00Z"
}

# 提交信息确权
$ curl -X POST http://localhost:8000/api/sessions/sess_abc123/confirm \
  -H "Content-Type: application/json" \
  -d '{
    "research_direction": "computer_vision",
    "interests": ["image_classification", "object_detection", "medical_imaging"],
    "advisor": {
      "name": "张教授",
      "research_areas": ["image_recognition", "deep_learning"],
      "recent_projects": ["医学影像分析（国家自然科学基金）"]
    },
    "constraints": {
      "thesis_type": "applied",
      "duration_months": 12,
      "has_gpu": true
    }
  }'
{
  "status": "confirmed",
  "stage": "ideation",
  "context_summary": "硕士/计算机视觉/张教授/图像分类+目标检测+医学影像",
  "next_action": "开始创意生成"
}
```

### 4.2 阶段二：创意生成

创意生成阶段会基于信息确权的结果，生成多个候选论题方向。

#### 4.2.1 启动创意生成

在 Web 界面点击「开始创意生成」按钮，或系统会自动进入此阶段。

#### 4.2.2 四维创意引擎

ThesisMiner v8.0 使用四维创意引擎生成论题：

1. **导师项目延伸**：基于导师近期项目延伸出新的研究点
2. **前辈工作继承**：基于同门师兄师姐的工作继续深入
3. **问题意识驱动**：基于领域痛点提出解决方案
4. **跨学科迁移**：将其他领域的方法迁移到本领域

```
[系统] 正在生成创意（四维引擎并行运行）...

[MentorAgent - 导师项目延伸]
  基于导师的「医学影像分析」项目，延伸出：
  1. 基于深度学习的 CT 影像肺结节检测
  2. 视网膜图像中的糖尿病视网膜病变分级
  3. 超声图像中的甲状腺结节分割

[SearcherAgent - 前辈工作继承]
  检索到 3 位前辈的相关工作：
  1. 李师兄（2023）：基于 YOLOv8 的医学图像目标检测
  2. 王师姐（2022）：基于 U-Net 的医学图像分割
  3. 赵师兄（2021）：基于迁移学习的医学图像分类
  可继承方向：
  1. 改进 YOLOv8 在小目标检测上的性能
  2. 将 U-Net 扩展到三维医学图像分割
  3. 研究少样本场景下的迁移学习

[MentorAgent - 问题意识驱动]
  识别到领域痛点：
  1. 医学影像标注数据稀缺
  2. 小病灶检测准确率低
  3. 跨设备影像风格不一致
  提出方向：
  1. 基于半监督学习的医学影像分析
  2. 注意力机制增强的小病灶检测
  3. 域自适应的跨设备影像分析

[MentorAgent - 跨学科迁移]
  检索到可迁移方法：
  1. NLP 中的 Transformer → 医学图像分析
  2. 推荐系统中的协同过滤 → 辅助诊断
  3. 强化学习 → 医学图像分割优化
  提出方向：
  1. Vision Transformer 在医学图像分类中的应用
  2. 基于强化学习的交互式医学图像分割
```

#### 4.2.3 查看生成的创意

系统会生成 8-12 个候选论题方向，按综合评分排序：

```
+------------------------------------------------------------------+
|  候选论题（共 10 个，按综合评分排序）                              |
+------------------------------------------------------------------+
|  # | 论题方向                            | 来源       | 评分     |
|----|-------------------------------------|------------|----------|
|  1 | 基于半监督学习的医学影像小病灶检测   | 问题意识   | 87       |
|  2 | Vision Transformer 在视网膜图像分级 | 跨学科迁移 | 84       |
|  3 | 改进 YOLOv8 的肺结节检测            | 前辈继承   | 82       |
|  4 | 注意力机制增强的甲状腺结节分割       | 问题意识   | 80       |
|  5 | 域自适应的跨设备超声影像分析         | 问题意识   | 78       |
|  6 | 三维 U-Net 的 CT 肺部分割           | 前辈继承   | 76       |
|  7 | 少样本迁移学习的医学图像分类         | 前辈继承   | 74       |
|  8 | 基于强化学习的交互式图像分割         | 跨学科迁移 | 72       |
|  9 | 协同过滤辅助的医学诊断              | 跨学科迁移 | 68       |
| 10 | 多模态医学影像融合分析              | 导师延伸   | 65       |
+------------------------------------------------------------------+
|  [选择论题]  [重新生成]  [导出列表]                               |
+------------------------------------------------------------------+
```

#### 4.2.4 选择论题

点击你感兴趣的论题，查看详情：

```
+------------------------------------------------------------------+
|  论题详情：基于半监督学习的医学影像小病灶检测                      |
+------------------------------------------------------------------+
|                                                                  |
|  综合评分：87/100                                                |
|  创意来源：问题意识驱动                                          |
|                                                                  |
|  研究背景：                                                       |
|  医学影像中的小病灶（如早期肿瘤、微小结节）检测准确率低，主要     |
|  原因是标注数据稀缺且病灶占比小。半监督学习可以利用未标注数据     |
|  提升检测性能。                                                   |
|                                                                  |
|  拟解决问题：                                                     |
|  1. 小病灶特征提取不充分                                          |
|  2. 未标注数据的有效利用                                          |
|  3. 伪标签噪声抑制                                                |
|                                                                  |
|  拟采用方法：                                                     |
|  1. 基于一致性正则化的半监督框架                                  |
|  2. 注意力机制增强的小目标特征提取                                |
|  3. 基于不确定性的伪标签筛选                                      |
|                                                                  |
|  预期贡献：                                                       |
|  1. 提出适用于小病灶检测的半监督学习框架                          |
|  2. 在公开数据集上达到 SOTA 性能                                  |
|  3. 在合作医院数据上验证泛化能力                                  |
|                                                                  |
|  关联文献（5 篇）：                                               |
|  [1] Semi-supervised Medical Image Segmentation...               |
|  [2] Small Object Detection in Medical Images...                 |
|  [3] Attention Mechanisms for Medical Imaging...                 |
|  ...                                                             |
|                                                                  |
|  [选择此论题]  [返回列表]                                         |
+------------------------------------------------------------------+
```

#### 4.2.5 通过 API 生成创意

```bash
# 启动创意生成
$ curl -X POST http://localhost:8000/api/sessions/sess_abc123/ideate \
  -H "Content-Type: application/json" \
  -d '{"count": 10}'
{
  "task_id": "task_xyz789",
  "status": "running",
  "stream_url": "/api/tasks/task_xyz789/stream"
}

# 获取流式输出
$ curl -N http://localhost:8000/api/tasks/task_xyz789/stream
data: {"type": "progress", "agent": "MentorAgent", "stage": "mentor_project", "progress": 25}
data: {"type": "progress", "agent": "SearcherAgent", "stage": "senior_inherit", "progress": 50}
data: {"type": "idea", "id": "idea_001", "title": "基于半监督学习的医学影像小病灶检测", "score": 87}
data: {"type": "idea", "id": "idea_002", "title": "Vision Transformer 在视网膜图像分级", "score": 84}
...
data: {"type": "complete", "total_ideas": 10}
```

### 4.3 阶段三：校验与回退

校验阶段会对选定的论题进行多维度评估，不通过的论题会触发回退机制。

#### 4.3.1 启动校验

选择论题后，点击「校验论题」按钮：

```
[系统] 正在校验论题：基于半监督学习的医学影像小病灶检测

[CriticAgent] 正在执行硬约束检查...
  [✓] 标题长度：22 字符（要求 15-40）
  [✓] 学科匹配：计算机视觉 → 计算机科学与技术
  [✓] 导师方向一致性：医学影像分析 ∈ 导师研究方向
  [✓] 时间可行性：12 个月可完成
  [✓] 重复度检测：18%（阈值 30%）
  [✓] AI 痕迹检测：未检测到明显 AI 痕迹

[CriticAgent] 正在执行软约束评估...
  新颖性评分：
    - 学科交叉：75/100
    - 方法迁移：85/100
    - 痛点突破：92/100
    - 趋势前瞻：88/100
    综合：85/100 ✓（阈值 60）

  可行性评估：
    - 技术可行性：88/100
    - 资源可行性：90/100（有 GPU）
    - 时间可行性：82/100
    - 学术可行性：85/100
    综合：86/100 ✓（阈值 60）

  风格质量：
    - 句式多样性：85/100
    - 词汇丰富度：80/100
    - 逻辑连贯性：88/100
    - 学术规范性：90/100
    综合：86/100 ✓（阈值 70）

[CriticAgent] 校验结果：通过 ✓
  综合评分：86/100
  建议进入多粒度生成阶段
```

#### 4.3.2 校验失败与回退

如果论题未通过校验，系统会触发回退机制：

```
[CriticAgent] 校验结果：未通过 ✗
  失败原因：
  1. 重复度 35% > 阈值 30%
  2. 新颖性评分 55 < 阈值 60

[系统] 触发回退机制...
[ReasonerAgent] 分析失败原因：
  - 重复度高：与已有工作「Semi-supervised Medical Image Segmentation」过于相似
  - 新颖性低：方法组合较为常见

[ReasonerAgent] 生成改进建议：
  1. 增加创新点：引入对比学习增强特征表示
  2. 调整角度：聚焦于特定器官（如肝脏）的小病灶
  3. 结合最新方法：引入 2024 年提出的 SAM (Segment Anything Model)

[系统] 是否根据建议重新生成？
  [是，重新生成]  [否，选择其他论题]  [手动修改]
```

#### 4.3.3 回退流程图

```
+-------------------+
|   选定论题        |
+-------------------+
         |
         v
+-------------------+
|   硬约束检查      |
+-------------------+
         |
    +----+----+
    |         |
    v         v
  通过      失败
    |         |
    v         v
+-------+ +-------------------+
| 软约束 | | 记录失败原因      |
| 评估  | | 生成改进建议      |
+-------+ +-------------------+
    |              |
    +------+-------+
           |
      +----+----+
      |         |
      v         v
    通过      失败
      |         |
      v         v
+----------+ +-------------------+
| 进入生成 | | 回退到创意生成    |
| 阶段     | | (携带改进建议)    |
+----------+ +-------------------+
```

#### 4.3.4 通过 API 校验

```bash
# 校验论题
$ curl -X POST http://localhost:8000/api/sessions/sess_abc123/validate \
  -H "Content-Type: application/json" \
  -d '{"idea_id": "idea_001"}'
{
  "validation_id": "val_def456",
  "status": "passed",
  "hard_constraints": {
    "title_length": {"passed": true, "value": 22, "threshold": "15-40"},
    "discipline_match": {"passed": true},
    "advisor_alignment": {"passed": true},
    "time_feasibility": {"passed": true},
    "duplication": {"passed": true, "value": 0.18, "threshold": 0.30},
    "ai_trace": {"passed": true}
  },
  "soft_constraints": {
    "novelty": {"score": 85, "threshold": 60, "passed": true},
    "feasibility": {"score": 86, "threshold": 60, "passed": true},
    "style": {"score": 86, "threshold": 70, "passed": true}
  },
  "overall_score": 86,
  "next_stage": "generation"
}
```

### 4.4 阶段四：多粒度生成

多粒度生成阶段会生成不同详细程度的论题描述，从标题到全文。

#### 4.4.1 生成粒度选择

```
+----------------------------------------------------------+
|  多粒度生成 - 选择生成粒度                                 |
+----------------------------------------------------------+
|                                                          |
|  [✓] 标题级（15-40 字符）                                 |
|  [✓] 摘要级（200-300 字）                                 |
|  [✓] 大纲级（章节标题 + 简述）                             |
|  [ ] 全文级（完整论题报告，约 3000-5000 字）               |
|                                                          |
|  生成选项：                                               |
|  [✓] 包含参考文献                                         |
|  [✓] 包含研究方法                                         |
|  [✓] 包含预期贡献                                         |
|  [ ] 包含实验设计                                         |
|                                                          |
|                              [取消]  [开始生成]           |
+----------------------------------------------------------+
```

#### 4.4.2 生成结果

**标题级：**

```
基于半监督学习与注意力机制的小病灶检测方法研究
```

**摘要级：**

```
医学影像中的小病灶检测是计算机辅助诊断的关键挑战之一。由于小病灶占比小、
特征不明显，传统方法难以取得理想效果。同时，医学影像标注成本高昂，标注
数据稀缺进一步限制了监督学习方法的性能。本文提出一种基于半监督学习与注
意力机制的小病灶检测框架，主要贡献包括：（1）设计了一种多尺度注意力模
块，增强小病灶的特征表示；（2）提出基于一致性正则化的半监督学习策略，
有效利用未标注数据；（3）引入不确定性估计机制，筛选高质量伪标签。在
公开数据集上的实验表明，所提方法在小病灶检测任务上达到 SOTA 性能，
mAP 提升 5.3%。
```

**大纲级：**

```
第一章 绪论
  1.1 研究背景与意义
  1.2 国内外研究现状
    1.2.1 医学影像小病灶检测研究现状
    1.2.2 半监督学习在医学影像中的应用
    1.2.3 注意力机制研究进展
  1.3 研究内容与贡献
  1.4 论文组织结构

第二章 相关工作
  2.1 医学影像分析基础
  2.2 目标检测方法
    2.2.1 两阶段检测器
    2.2.2 单阶段检测器
  2.3 半监督学习方法
    2.3.1 一致性正则化
    2.3.2 伪标签方法
    2.3.3 自训练方法
  2.4 注意力机制
    2.4.1 空间注意力
    2.4.2 通道注意力
    2.4.3 自注意力

第三章 方法
  3.1 整体框架
  3.2 多尺度注意力模块
    3.2.1 模块设计
    3.2.2 特征融合策略
  3.3 半监督学习策略
    3.3.1 一致性正则化
    3.3.2 伪标签生成
  3.4 不确定性估计
    3.4.1 Monte Carlo Dropout
    3.4.2 伪标签筛选
  3.5 损失函数设计

第四章 实验
  4.1 数据集
  4.2 评价指标
  4.3 实现细节
  4.4 与 SOTA 方法对比
  4.5 消融实验
  4.6 可视化分析

第五章 总结与展望
  5.1 工作总结
  5.2 未来工作
```

#### 4.4.3 通过 API 生成

```bash
# 多粒度生成
$ curl -X POST http://localhost:8000/api/sessions/sess_abc123/generate \
  -H "Content-Type: application/json" \
  -d '{
    "idea_id": "idea_001",
    "granularities": ["title", "abstract", "outline"],
    "options": {
      "include_references": true,
      "include_methods": true,
      "include_contributions": true
    }
  }'
{
  "generation_id": "gen_ghi012",
  "results": {
    "title": "基于半监督学习与注意力机制的小病灶检测方法研究",
    "abstract": "医学影像中的小病灶检测...",
    "outline": "第一章 绪论\n  1.1 研究背景与意义..."
  },
  "metadata": {
    "model": "gpt-4.1",
    "tokens_used": 3500,
    "cache_hit": true,
    "cost_usd": 0.035
  }
}
```

### 4.5 阶段五：深度辅助三件套

深度辅助阶段提供三个工具：文献精读、实验预研、答辩模拟。

#### 4.5.1 文献精读

```
+----------------------------------------------------------+
|  深度辅助 - 文献精读                                       |
+----------------------------------------------------------+
|                                                          |
|  输入文献：                                                |
|  [粘贴文献摘要或上传 PDF                          ]        |
|                                                          |
|  精读维度：                                                |
|  [✓] 研究问题与动机                                       |
|  [✓] 方法核心创新                                         |
|  [✓] 实验设计与结果                                       |
|  [✓] 与本论题的关联                                       |
|  [✓] 可借鉴之处                                          |
|  [✓] 局限性与改进空间                                     |
|                                                          |
|                              [取消]  [开始精读]           |
+----------------------------------------------------------+
```

精读结果示例：

```
[SearcherAgent] 文献精读报告
==================================================

文献：Semi-supervised Medical Image Segmentation with
      Consistency Regularization (MICCAI 2023)

1. 研究问题与动机
   - 问题：医学影像标注数据稀缺，全监督方法性能受限
   - 动机：利用未标注数据提升分割性能

2. 方法核心创新
   - 创新 1：提出双流网络结构，分别处理标注与未标注数据
   - 创新 2：基于强增强与弱增强的一致性正则化
   - 创新 3：动态调整一致性损失权重

3. 实验设计与结果
   - 数据集：ACDC、BraTS、LiTS
   - 指标：Dice 系数、Hausdorff 距离
   - 结果：在 10% 标注数据下，Dice 提升 8.2%

4. 与本论题的关联
   - 关联度：高
   - 可借鉴：一致性正则化框架、动态权重调整
   - 差异点：本文聚焦检测任务（非分割），且针对小病灶

5. 可借鉴之处
   - 借鉴双流网络结构处理标注/未标注数据
   - 借鉴动态权重调整策略
   - 借鉴强增强策略（CutMix、Cutout）

6. 局限性与改进空间
   - 局限：仅验证了分割任务，未验证检测任务
   - 局限：未考虑小目标场景
   - 改进：可扩展到检测任务，增加小目标注意力机制
```

#### 4.5.2 实验预研

```
+----------------------------------------------------------+
|  深度辅助 - 实验预研                                       |
+----------------------------------------------------------+
|                                                          |
|  实验预研模板：                                            |
|                                                          |
|  1. 实验目标：                                            |
|     [验证所提方法在小病灶检测上的有效性            ]       |
|                                                          |
|  2. 数据集选择：                                          |
|     [✓] 公开数据集：ChestX-ray14                         |
|     [✓] 公开数据集：DeepLesion                           |
|     [ ] 自采数据集（需说明来源）                          |
|                                                          |
|  3. 评价指标：                                            |
|     [✓] mAP (mean Average Precision)                     |
|     [✓] Recall@K                                        |
|     [✓] F1-Score                                        |
|                                                          |
|  4. 对比方法：                                            |
|     [✓] YOLOv8                                          |
|     [✓] Faster R-CNN                                    |
|     [✓] RetinaNet                                       |
|     [✓] 半监督基线：Mean Teacher                         |
|                                                          |
|  5. 消融实验设计：                                        |
|     [✓] 移除注意力模块                                   |
|     [✓] 移除半监督策略                                   |
|     [✓] 移除不确定性估计                                 |
|                                                          |
|                              [生成预研报告]               |
+----------------------------------------------------------+
```

#### 4.5.3 答辩模拟

```
+----------------------------------------------------------+
|  深度辅助 - 答辩模拟                                       |
+----------------------------------------------------------+
|                                                          |
|  模拟模式：                                                |
|  ( ) 快速模拟（5 个问题）                                 |
|  (•) 完整模拟（15 个问题，含追问）                        |
|  ( ) 自定义问题                                           |
|                                                          |
|  评委风格：                                                |
|  ( ) 友善型（多鼓励，少追问）                             |
|  (•) 严谨型（追问细节，质疑方法）                         |
|  ( ) 挑战型（强烈质疑，压力测试）                         |
|                                                          |
|                              [取消]  [开始模拟]           |
+----------------------------------------------------------+
```

答辩模拟示例：

```
[MentorAgent - 评委角色]
问题 1：请简要介绍你的研究工作。

[用户输入]
本研究针对医学影像小病灶检测问题，提出了一种基于半监督学习与注意力机制
的方法...

[MentorAgent - 评委追问]
追问：你提到使用半监督学习，请问与 Mean Teacher 方法相比，你的方法
有什么本质区别？为什么选择一致性正则化而不是伪标签方法？

[用户输入]
...

[MentorAgent - 评价]
评价：
  - 表达清晰度：85/100
  - 方法理解深度：78/100（建议加强对 Mean Teacher 的理解）
  - 应对追问能力：82/100
  - 整体表现：82/100

建议改进：
  1. 准备好与基线方法的详细对比
  2. 深入理解半监督学习的理论基础
  3. 准备实验结果的多种可视化方式
```

---

## 5. 多对话管理

ThesisMiner v8.0 支持多对话管理，每个对话拥有独立的上下文，互不干扰。

### 5.1 创建新对话

#### 5.1.1 通过 Web 界面创建

1. 点击左侧边栏的「+ 新建对话」按钮
2. 输入对话名称
3. 选择是否基于现有对话创建（可选）
4. 点击「创建」

```
+-------------------+--------------------------------------+
| 对话列表          |  对话内容                            |
+-------------------+--------------------------------------+
| + 新建对话        |                                      |
|-------------------|                                      |
| 📌 计算机视觉     |  （当前对话内容显示区域）             |
|    硕士论题       |                                      |
|                   |                                      |
| 📂 NLP 博士论题   |                                      |
|                   |                                      |
| 📂 数据挖掘       |                                      |
|    硕士论题       |                                      |
|                   |                                      |
+-------------------+--------------------------------------+
```

#### 5.1.2 通过 API 创建

```bash
$ curl -X POST http://localhost:8000/api/sessions/sess_abc123/conversations \
  -H "Content-Type: application/json" \
  -d '{
    "name": "备选方案：三维分割",
    "based_on": null
  }'
{
  "conversation_id": "conv_xyz123",
  "session_id": "sess_abc123",
  "name": "备选方案：三维分割",
  "created_at": "2026-06-19T11:00:00Z"
}
```

#### 5.1.3 基于现有对话创建

```bash
$ curl -X POST http://localhost:8000/api/sessions/sess_abc123/conversations \
  -H "Content-Type: application/json" \
  -d '{
    "name": "方案二：基于现有对话分支",
    "based_on": "conv_xyz123"
  }'
{
  "conversation_id": "conv_branch456",
  "session_id": "sess_abc123",
  "name": "方案二：基于现有对话分支",
  "based_on": "conv_xyz123",
  "inherited_messages": 15
}
```

### 5.2 切换对话

#### 5.2.1 通过 Web 界面切换

点击左侧边栏中的任意对话名称即可切换。切换时：

1. 当前对话的上下文自动保存
2. 目标对话的上下文加载到内存
3. DST（Dialog State Tracking）状态切换
4. 缓存前缀更新

#### 5.2.2 切换时的上下文隔离

```
对话 A：计算机视觉硕士论题
  上下文：
    - 学位：硕士
    - 学科：计算机视觉
    - 导师：张教授
    - 已生成论题：基于半监督学习的小病灶检测

对话 B：NLP 博士论题
  上下文：
    - 学位：博士
    - 学科：自然语言处理
    - 导师：李教授
    - 已生成论题：基于大语言模型的文本理解

切换 A → B 时：
  ✓ 保存 A 的上下文
  ✓ 加载 B 的上下文
  ✓ 更新缓存前缀（SHA-256 重新计算）
  ✓ Agent 上下文重置
  ✗ A 的上下文不会泄漏到 B
```

#### 5.2.3 通过 API 切换

```bash
# 切换对话（前端行为，API 层面通过在请求中指定 conversation_id 实现）
$ curl -X POST http://localhost:8000/api/sessions/sess_abc123/conversations/conv_branch456/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "继续讨论三维分割方案"}'
```

### 5.3 重命名对话

#### 5.3.1 通过 Web 界面重命名

1. 右键点击对话名称
2. 选择「重命名」
3. 输入新名称
4. 按 Enter 确认

#### 5.3.2 通过 API 重命名

```bash
$ curl -X PATCH http://localhost:8000/api/sessions/sess_abc123/conversations/conv_xyz123 \
  -H "Content-Type: application/json" \
  -d '{"name": "主方案：半监督小病灶检测"}'
{
  "conversation_id": "conv_xyz123",
  "name": "主方案：半监督小病灶检测",
  "updated_at": "2026-06-19T11:05:00Z"
}
```

### 5.4 删除对话

#### 5.4.1 通过 Web 界面删除

1. 右键点击对话名称
2. 选择「删除」
3. 在确认对话框中点击「确认删除」

> ⚠️ 删除对话会同时删除该对话的所有消息、生成的论题、预算记录等。此操作不可撤销。

#### 5.4.2 通过 API 删除

```bash
$ curl -X DELETE http://localhost:8000/api/sessions/sess_abc123/conversations/conv_branch456
{
  "conversation_id": "conv_branch456",
  "deleted": true,
  "deleted_messages": 8,
  "deleted_proposals": 2
}
```

#### 5.4.3 软删除与硬删除

ThesisMiner 默认使用软删除（标记 `is_deleted = true`），可在 30 天内恢复：

```bash
# 恢复已删除的对话
$ curl -X POST http://localhost:8000/api/sessions/sess_abc123/conversations/conv_branch456/restore
{
  "conversation_id": "conv_branch456",
  "restored": true
}

# 永久删除（硬删除）
$ curl -X DELETE http://localhost:8000/api/sessions/sess_abc123/conversations/conv_branch456?permanent=true
```

### 5.5 上下文隔离验证

#### 5.5.1 验证方法

创建两个对话，分别讨论不同主题，验证上下文不会交叉：

```bash
# 对话 A：讨论计算机视觉
$ curl -X POST http://localhost:8000/api/sessions/sess_abc123/conversations/conv_a/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "我的研究方向是计算机视觉"}'

# 对话 B：讨论 NLP
$ curl -X POST http://localhost:8000/api/sessions/sess_abc123/conversations/conv_b/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "我的研究方向是自然语言处理"}'

# 在对话 A 中询问"我的研究方向是什么"
$ curl -X POST http://localhost:8000/api/sessions/sess_abc123/conversations/conv_a/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "我的研究方向是什么？"}'

# 预期回答：计算机视觉（不应出现 NLP）
```

#### 5.5.2 上下文隔离机制

```
+-------------------+     +-------------------+
|    对话 A         |     |    对话 B         |
+-------------------+     +-------------------+
| messages_a        |     | messages_b        |
| dst_state_a       |     | dst_state_b       |
| cache_prefix_a    |     | cache_prefix_b    |
+-------------------+     +-------------------+
         |                         |
         v                         v
+-------------------+     +-------------------+
| Agent 上下文 A    |     | Agent 上下文 B    |
| (独立内存空间)    |     | (独立内存空间)    |
+-------------------+     +-------------------+
         |                         |
         +------------+------------+
                      |
                      v
          +-----------------------+
          |   共享的会话级配置     |
          |   (学位、学科等)       |
          +-----------------------+
```

#### 5.5.3 缓存前缀验证

每个对话有独立的缓存前缀（基于对话 ID 的 SHA-256 哈希）：

```bash
# 查看对话 A 的缓存前缀
$ curl http://localhost:8000/api/sessions/sess_abc123/conversations/conv_a/cache-info
{
  "conversation_id": "conv_a",
  "cache_prefix_hash": "a1b2c3d4e5f6...",
  "cache_hits": 12,
  "cache_misses": 3
}

# 查看对话 B 的缓存前缀
$ curl http://localhost:8000/api/sessions/sess_abc123/conversations/conv_b/cache-info
{
  "conversation_id": "conv_b",
  "cache_prefix_hash": "f6e5d4c3b2a1...",
  "cache_hits": 8,
  "cache_misses": 5
}
```

---

## 6. 谱系图谱使用

ThesisMiner v8.0 使用 D3.js 构建学术谱系图谱，可视化展示导师、前辈、论题之间的关系。

### 6.1 图谱浏览

#### 6.1.1 打开图谱视图

在 Web 界面点击「谱系图谱」标签：

```
+------------------------------------------------------------------+
|  谱系图谱                                                         |
+------------------------------------------------------------------+
|  [会话选择：sess_abc123 ▼]   [布局：力导向 ▼]   [导出 SVG]       |
+------------------------------------------------------------------+
|                                                                  |
|                    [导师]                                        |
|                   张教授                                          |
|                  /  |  \                                         |
|                 /   |   \                                        |
|            [前辈]  [前辈]  [前辈]                                 |
|            李师兄  王师姐  赵师兄                                  |
|              |      |      |                                     |
|            [论题]  [论题]  [论题]                                 |
|              \      |      /                                     |
|               \     |     /                                      |
|                [当前论题]                                         |
|                小病灶检测                                         |
|                                                                  |
+------------------------------------------------------------------+
|  节点：12  |  边：15  |  过滤：全部  |  缩放：100%                |
+------------------------------------------------------------------+
```

#### 6.1.2 节点类型

谱系图谱包含以下节点类型：

| 节点类型 | 图标 | 颜色 | 说明 |
|----------|------|------|------|
| 导师 | 👨‍🏫 | 蓝色 | 当前用户的导师 |
| 前辈 | 🎓 | 绿色 | 同门师兄师姐 |
| 论题 | 📝 | 橙色 | 已生成的论题 |
| 文献 | 📄 | 紫色 | 相关文献 |
| 项目 | 🔬 | 红色 | 导师研究项目 |
| 当前论题 | ⭐ | 金色 | 当前选定的论题 |

#### 6.1.3 边类型

| 边类型 | 线型 | 说明 |
|--------|------|------|
| 师生关系 | 实线 | 导师 → 学生 |
| 论题继承 | 虚线 | 前辈论题 → 当前论题 |
| 文献引用 | 点线 | 论题 → 文献 |
| 项目关联 | 粗实线 | 项目 → 论题 |

### 6.2 拖拽与缩放

#### 6.2.1 拖拽节点

- **鼠标左键按住节点拖拽**：移动节点位置
- **鼠标左键按住空白处拖拽**：平移整个图谱

#### 6.2.2 缩放

- **鼠标滚轮**：以鼠标位置为中心缩放
- **「+」按钮**：放大
- **「-」按钮**：缩小
- **「重置」按钮**：重置缩放与位置

#### 6.2.3 触摸操作（移动端）

- **单指拖拽**：平移图谱
- **双指捏合**：缩放
- **双指点击**：重置视图

### 6.3 节点类型过滤

#### 6.3.1 通过 Web 界面过滤

点击图谱上方的过滤按钮：

```
+------------------------------------------------------------------+
|  节点过滤                                                         |
+------------------------------------------------------------------+
|  [✓] 👨‍🏫 导师    [✓] 🎓 前辈    [✓] 📝 论题                     |
|  [✓] 📄 文献    [ ] 🔬 项目    [✓] ⭐ 当前论题                   |
+------------------------------------------------------------------+
|  [全选]  [全不选]  [仅显示当前论题相关]                           |
+------------------------------------------------------------------+
```

#### 6.3.2 通过 API 过滤

```bash
$ curl http://localhost:8000/api/sessions/sess_abc123/lineage?node_types=advisor,proposal
{
  "nodes": [
    {"id": "node_001", "type": "advisor", "label": "张教授", ...},
    {"id": "node_002", "type": "proposal", "label": "小病灶检测", ...}
  ],
  "edges": [...]
}
```

### 6.4 节点详情查看

#### 6.4.1 点击节点查看详情

点击任意节点，右侧弹出详情面板：

```
+------------------------------------------------------------------+
|  节点详情：张教授                                          [×]    |
+------------------------------------------------------------------+
|                                                                  |
|  类型：导师                                                       |
|  姓名：张教授                                                     |
|  职称：教授                                                       |
|  单位：XX 大学计算机学院                                           |
|                                                                  |
|  研究方向：                                                       |
|  - 图像识别                                                       |
|  - 深度学习                                                       |
|  - 医学影像分析                                                   |
|                                                                  |
|  近期项目：                                                       |
|  1. 医学影像分析（国家自然科学基金，2023-2026）                   |
|  2. 基于 AI 的辅助诊断系统（省部级，2022-2024）                   |
|                                                                  |
|  代表性论文（5 篇）：                                              |
|  [1] Deep Learning for Medical Image Analysis...                 |
|  [2] ...                                                         |
|                                                                  |
|  指导学生：                                                       |
|  - 李师兄（2023 届，现就职于 XX 公司）                            |
|  - 王师姐（2022 届，现于 XX 大学读博）                            |
|  - 赵师兄（2021 届，现于 XX 研究所）                              |
|                                                                  |
|  [在图谱中高亮]  [导出详情]  [查看关联论题]                       |
+------------------------------------------------------------------+
```

### 6.5 批量操作

#### 6.5.1 多选节点

- **Shift + 点击**：连续多选
- **Ctrl/Cmd + 点击**：非连续多选
- **框选**：鼠标左键按住空白处拖拽

#### 6.5.2 批量操作菜单

选中多个节点后，右键弹出批量操作菜单：

```
+-------------------+
| 批量操作          |
+-------------------+
| 📤 导出选中节点   |
| 🏷️ 添加标签       |
| 🔗 创建关联       |
| 🗑️ 删除选中       |
| 📋 复制到其他会话 |
+-------------------+
```

#### 6.5.3 导出图谱

```
+------------------------------------------------------------------+
|  导出图谱                                                         |
+------------------------------------------------------------------+
|  格式：                                                           |
|  (•) SVG（矢量图，可编辑）                                        |
|  ( ) PNG（位图，300 DPI）                                         |
|  ( ) PDF（适合打印）                                              |
|  ( ) JSON（数据格式，可导入）                                     |
|                                                                  |
|  范围：                                                           |
|  (•) 当前视图                                                     |
|  ( ) 全部节点                                                     |
|  ( ) 选中节点                                                     |
|                                                                  |
|  选项：                                                           |
|  [✓] 包含节点详情                                                 |
|  [✓] 包含边标签                                                   |
|  [ ] 包含元数据                                                   |
|                                                                  |
|                              [取消]  [导出]                       |
+------------------------------------------------------------------+
```

#### 6.5.4 通过 API 导出

```bash
# 导出为 SVG
$ curl http://localhost:8000/api/sessions/sess_abc123/lineage/export?format=svg \
  -o lineage.svg

# 导出为 JSON
$ curl http://localhost:8000/api/sessions/sess_abc123/lineage/export?format=json \
  -o lineage.json
```

---

## 7. 预算监控

ThesisMiner v8.0 提供透明的 Token 预算监控，帮助你控制成本。

### 7.1 账本查看

#### 7.1.1 通过 Web 界面查看

点击「预算监控」标签，查看透明账本：

```
+------------------------------------------------------------------+
|  预算监控 - 透明账本                                              |
+------------------------------------------------------------------+
|  会话：sess_abc123    时间范围：[最近 7 天 ▼]                    |
+------------------------------------------------------------------+
|                                                                  |
|  总览：                                                           |
|  +----------------+----------------+----------------+            |
|  | 总 Token 数    | 总成本 (USD)   | 缓存命中率     |            |
|  +----------------+----------------+----------------+            |
|  | 1,234,567      | $12.34         | 68.5%          |            |
|  +----------------+----------------+----------------+            |
|                                                                  |
|  按模型分布：                                                     |
|  deepseek-r2          850,000 tokens    $2.55    (69%)           |
|  claude-opus-4.5      234,567 tokens    $7.04    (19%)           |
|  gpt-4.1              150,000 tokens    $2.75    (12%)           |
|                                                                  |
|  按阶段分布：                                                     |
|  信息确权             120,000 tokens    $0.36                    |
|  创意生成             450,000 tokens    $4.50                    |
|  校验                 180,000 tokens    $0.54                    |
|  多粒度生成           380,000 tokens    $5.70                    |
|  深度辅助             104,567 tokens    $1.24                    |
|                                                                  |
+------------------------------------------------------------------+
|  [查看明细]  [导出报表]  [设置预算告警]                           |
+------------------------------------------------------------------+
```

#### 7.1.2 账本明细

点击「查看明细」查看每条记录：

```
+------------------------------------------------------------------+
|  账本明细                                                         |
+------------------------------------------------------------------+
|  时间              | 模型        | 阶段     | Token | 成本       |
|-------------------|-------------|----------|-------|------------|
| 2026-06-19 10:35  | deepseek-r2 | 确权     | 1,200 | $0.0036    |
| 2026-06-19 10:38  | claude-opus | 创意     | 3,500 | $0.105     |
| 2026-06-19 10:42  | deepseek-r2 | 创意     | 2,800 | $0.0084    |
| 2026-06-19 10:45  | deepseek-r2 | 校验     | 1,500 | $0.0045    |
| 2026-06-19 10:50  | gpt-4.1     | 生成     | 3,500 | $0.035     |
| ...                                                             |
+------------------------------------------------------------------+
|  共 156 条记录                              [导出 CSV]           |
+------------------------------------------------------------------+
```

#### 7.1.3 通过 API 查看账本

```bash
# 查看账本总览
$ curl http://localhost:8000/api/sessions/sess_abc123/budget/summary
{
  "session_id": "sess_abc123",
  "total_tokens": 1234567,
  "total_cost_usd": 12.34,
  "cache_hit_rate": 0.685,
  "by_model": {
    "deepseek-r2": {"tokens": 850000, "cost": 2.55},
    "claude-opus-4.5": {"tokens": 234567, "cost": 7.04},
    "gpt-4.1": {"tokens": 150000, "cost": 2.75}
  },
  "by_stage": {
    "information_confirmation": {"tokens": 120000, "cost": 0.36},
    "ideation": {"tokens": 450000, "cost": 4.50},
    "validation": {"tokens": 180000, "cost": 0.54},
    "generation": {"tokens": 380000, "cost": 5.70},
    "deep_assistance": {"tokens": 104567, "cost": 1.24}
  }
}

# 查看账本明细
$ curl "http://localhost:8000/api/sessions/sess_abc123/budget/ledger?limit=10"
{
  "records": [
    {
      "id": "led_001",
      "timestamp": "2026-06-19T10:35:00Z",
      "model": "deepseek-r2",
      "stage": "information_confirmation",
      "input_tokens": 800,
      "output_tokens": 400,
      "total_tokens": 1200,
      "cost_usd": 0.0036,
      "cache_hit": false
    },
    ...
  ],
  "total": 156
}
```

### 7.2 成本分析

#### 7.2.1 成本趋势图

```
+------------------------------------------------------------------+
|  成本趋势（最近 7 天）                                            |
+------------------------------------------------------------------+
|  $3 |                              *                              |
|  $2 |                    *       * *                              |
|  $1 |          *       * *     * * * *                            |
|  $0 |  * * * * * * * * * * * * * * * * * *                        |
|     +--------------------------------------------------+          |
|      06/13  06/14  06/15  06/16  06/17  06/18  06/19             |
+------------------------------------------------------------------+
|  日均成本：$1.76  |  预估月成本：$52.80                          |
+------------------------------------------------------------------+
```

#### 7.2.2 成本优化建议

系统会根据使用情况提供成本优化建议：

```
+------------------------------------------------------------------+
|  成本优化建议                                                     |
+------------------------------------------------------------------+
|                                                                  |
|  1. 提高 DeepSeek 缓存命中率                                      |
|     当前命中率：68.5%                                             |
|     建议命中率：80%+                                              |
|     预计节省：$0.50/天                                            |
|     方法：固化 Prompt 前缀，减少动态内容                          |
|                                                                  |
|  2. 将校验阶段从 claude-opus-4.5 切换到 deepseek-r2               |
|     当前成本：$0.54/天                                            |
|     切换后：$0.16/天                                              |
|     预计节省：$0.38/天                                            |
|     方法：校验阶段对创造力要求低，DeepSeek 足够                   |
|                                                                  |
|  3. 减少深度辅助阶段的调用频率                                     |
|     当前频率：每次生成后都调用                                    |
|     建议频率：仅在校验通过后调用                                  |
|     预计节省：$0.20/天                                            |
|                                                                  |
+------------------------------------------------------------------+
```

### 7.3 缓存命中率

#### 7.3.1 缓存命中率详情

```
+------------------------------------------------------------------+
|  缓存命中率详情                                                   |
+------------------------------------------------------------------+
|                                                                  |
|  总体命中率：68.5%                                                |
|                                                                  |
|  按模型：                                                         |
|  deepseek-r2          72.3%  (615,000 / 850,000)                 |
|  claude-opus-4.5      45.2%  (106,000 / 234,567)                 |
|  gpt-4.1              58.0%  (87,000 / 150,000)                  |
|                                                                  |
|  按阶段：                                                         |
|  信息确权             85.0%  (前缀稳定，命中率高)                |
|  创意生成             35.0%  (动态内容多，命中率低)              |
|  校验                 78.0%  (规则固定，命中率高)                |
|  多粒度生成           62.0%  (部分模板可复用)                    |
|  深度辅助             55.0%  (中等)                              |
|                                                                  |
|  缓存节省：                                                       |
|  - 节省 Token 数：808,000                                         |
|  - 节省成本：$8.08                                                |
|                                                                  |
+------------------------------------------------------------------+
```

#### 7.3.2 提高缓存命中率的方法

1. **固化 Prompt 前缀**：将系统提示、角色定义等稳定内容放在 Prompt 开头
2. **减少动态参数**：将易变的参数放在 Prompt 末尾
3. **会话切换时复用上下文**：相似会话共享部分上下文
4. **使用 DST 压缩**：压缩历史对话，减少动态内容

### 7.4 导出报表

#### 7.4.1 导出 CSV

```bash
$ curl http://localhost:8000/api/sessions/sess_abc123/budget/export?format=csv \
  -o budget_report.csv
```

CSV 格式示例：

```csv
timestamp,model,stage,input_tokens,output_tokens,total_tokens,cost_usd,cache_hit
2026-06-19T10:35:00Z,deepseek-r2,information_confirmation,800,400,1200,0.0036,false
2026-06-19T10:38:00Z,claude-opus-4.5,ideation,2500,1000,3500,0.105,false
2026-06-19T10:42:00Z,deepseek-r2,ideation,2000,800,2800,0.0084,true
...
```

#### 7.4.2 导出 JSON

```bash
$ curl http://localhost:8000/api/sessions/sess_abc123/budget/export?format=json \
  -o budget_report.json
```

#### 7.4.3 导出 Excel（通过 Web 界面）

1. 点击「导出报表」按钮
2. 选择格式：Excel
3. 选择时间范围
4. 点击「导出」

---

## 8. 常见操作速查

### 8.1 快捷键速查表

#### 8.1.1 全局快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl/Cmd + K` | 打开命令面板 |
| `Ctrl/Cmd + N` | 新建会话 |
| `Ctrl/Cmd + Shift + N` | 新建对话 |
| `Ctrl/Cmd + S` | 保存当前状态 |
| `Ctrl/Cmd + E` | 导出当前内容 |
| `Ctrl/Cmd + ,` | 打开设置 |
| `Ctrl/Cmd + /` | 显示快捷键帮助 |
| `Esc` | 关闭弹窗/取消操作 |

#### 8.1.2 对话快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl/Cmd + Enter` | 发送消息 |
| `Shift + Enter` | 换行 |
| `Ctrl/Cmd + ↑` | 查看上一条消息 |
| `Ctrl/Cmd + ↓` | 查看下一条消息 |
| `Ctrl/Cmd + Shift + C` | 清空当前对话（需确认） |
| `Ctrl/Cmd + Shift + D` | 删除当前对话（需确认） |

#### 8.1.3 图谱快捷键

| 快捷键 | 功能 |
|--------|------|
| `+` / `=` | 放大 |
| `-` | 缩小 |
| `0` | 重置缩放 |
| `F` | 适应屏幕 |
| `Shift + 点击` | 多选节点 |
| `Ctrl/Cmd + A` | 全选节点 |
| `Delete` | 删除选中节点 |
| `Ctrl/Cmd + E` | 导出图谱 |

#### 8.1.4 阶段导航快捷键

| 快捷键 | 功能 |
|--------|------|
| `Alt + 1` | 跳转到信息确权 |
| `Alt + 2` | 跳转到创意生成 |
| `Alt + 3` | 跳转到校验 |
| `Alt + 4` | 跳转到多粒度生成 |
| `Alt + 5` | 跳转到深度辅助 |
| `Alt + L` | 打开谱系图谱 |
| `Alt + B` | 打开预算监控 |

### 8.2 命令行速查

#### 8.2.1 启动与停止

```bash
# 启动开发服务器
python -m backend.main

# 启动生产服务器（多进程）
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4

# 启动并开启热重载
uvicorn backend.main:app --reload

# 停止服务（前台运行时）
Ctrl + C
```

#### 8.2.2 数据库管理

```bash
# 初始化数据库
python -m backend.database init

# 查看数据库表
python -m backend.database tables

# 查看种子数据
python -m backend.database seed --list

# 重置数据库
python -m backend.database reset --confirm

# 备份数据库
python -m backend.database backup --output backup.db

# 恢复数据库
python -m backend.database restore --input backup.db
```

#### 8.2.3 模型管理

```bash
# 列出已配置模型
python -m backend.cli models list

# 测试模型连通性
python -m backend.cli models test

# 测试单个模型
python -m backend.cli models test --model deepseek-r2

# 查看模型路由配置
python -m backend.cli models routing
```

#### 8.2.4 会话管理

```bash
# 列出所有会话
python -m backend.cli sessions list

# 创建会话
python -m backend.cli sessions create --name "测试会话" --degree master

# 删除会话
python -m backend.cli sessions delete --id sess_abc123

# 导出会话数据
python -m backend.cli sessions export --id sess_abc123 --format json
```

#### 8.2.5 预算查询

```bash
# 查看会话预算总览
python -m backend.cli budget summary --session sess_abc123

# 查看全局预算
python -m backend.cli budget summary --global

# 导出预算报表
python -m backend.cli budget export --session sess_abc123 --format csv
```

### 8.3 配置项速查

#### 8.3.1 核心配置项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `HOST` | `0.0.0.0` | 监听地址 |
| `PORT` | `8000` | 监听端口 |
| `WORKERS` | `1` | 工作进程数 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `DATABASE_URL` | `sqlite:///./thesisminer.db` | 数据库连接 |
| `SECRET_KEY` | （需设置） | 会话加密密钥 |

#### 8.3.2 模型配置项

| 配置项 | 说明 |
|--------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key |
| `DEEPSEEK_BASE_URL` | DeepSeek API 端点 |
| `OPENAI_API_KEY` | OpenAI API Key |
| `OPENAI_BASE_URL` | OpenAI API 端点 |
| `ANTHROPIC_API_KEY` | Anthropic API Key |
| `ANTHROPIC_BASE_URL` | Anthropic API 端点 |
| `MODEL_ROUTING` | 步骤路由配置（JSON） |

#### 8.3.3 缓存配置项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `CACHE_ENABLED` | `true` | 是否启用缓存 |
| `CACHE_TTL_SECONDS` | `3600` | 缓存过期时间（秒） |
| `CACHE_MAX_SIZE` | `1000` | 最大缓存条目数 |
| `CACHE_PREFIX_HASH` | （自动） | 缓存前缀哈希 |

#### 8.3.4 约束配置项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `TITLE_MIN_LENGTH` | `15` | 标题最小长度 |
| `TITLE_MAX_LENGTH` | `40` | 标题最大长度 |
| `DUPLICATION_THRESHOLD` | `0.30` | 重复度阈值 |
| `NOVELTY_MIN_SCORE` | `60` | 新颖性最低分 |
| `FEASIBILITY_MIN_SCORE` | `60` | 可行性最低分 |
| `STYLE_MIN_SCORE` | `70` | 风格质量最低分 |

#### 8.3.5 限流配置项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `RATE_LIMIT_ENABLED` | `true` | 是否启用限流 |
| `RATE_LIMIT_RPM` | `60` | 每分钟请求数 |
| `RATE_LIMIT_BURST` | `10` | 突发请求数 |
| `TOKEN_QUOTA_DAILY` | `1000000` | 每日 Token 配额 |

---

## 9. 下一步学习

完成本入门教程后，你可以继续学习以下内容：

### 9.1 进阶教程

- **高级特性教程**（`docs/tutorials/advanced_features.md`）：学习自定义 Agent、约束扩展、缓存优化等高级功能
- **管理员指南**（`docs/tutorials/admin_guide.md`）：学习部署运维、模型配置、安全加固等管理操作

### 9.2 架构理解

- **系统总览**（`docs/architecture/system_overview.md`）：了解 ThesisMiner 的整体架构
- **数据流设计**（`docs/architecture/data_flow.md`）：理解五阶段流程的数据流转
- **Agent 架构**（`docs/architecture/agent_architecture.md`）：深入理解多 Agent 协作机制

### 9.3 开发贡献

- **代码风格规范**（`docs/development/code_style.md`）：了解代码贡献规范
- **故障排查指南**（`docs/development/troubleshooting.md`）：解决常见问题
- **FAQ**（`docs/development/faq.md`）：查看常见问题解答

### 9.4 API 集成

- **API 文档**（`docs/api/openapi.yaml`）：完整的 API 参考
- **错误码参考**（`docs/api/error_codes.md`）：错误码查询
- **限流配额**（`docs/api/rate_limiting.md`）：限流策略说明

### 9.5 示例代码

- **Agent 示例**（`samples/example_agents.py`）：自定义 Agent 实现示例
- **约束示例**（`samples/example_constraints.py`）：自定义约束实现示例
- **集成示例**（`samples/example_integrations.py`）：第三方集成示例

### 9.6 社区与支持

- **GitHub Issues**：提交问题与建议
- **讨论区**：与其他用户交流
- **贡献指南**（`docs/development/contributing.md`）：参与项目贡献

---

## 附录 A：环境变量完整列表

```env
# ============ 基础配置 ============
HOST=0.0.0.0
PORT=8000
WORKERS=1
LOG_LEVEL=INFO
SECRET_KEY=your-secret-key-at-least-32-chars

# ============ 数据库配置 ============
DATABASE_URL=sqlite:///./thesisminer.db

# ============ DeepSeek 配置 ============
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# ============ OpenAI 配置 ============
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1

# ============ Anthropic 配置 ============
ANTHROPIC_API_KEY=sk-ant-xxx
ANTHROPIC_BASE_URL=https://api.anthropic.com/v1

# ============ 智谱 AI 配置 ============
ZHIPU_API_KEY=xxx
ZHIPU_BASE_URL=https://open.bigmodel.cn/api/paas/v4

# ============ 月之暗面配置 ============
MOONSHOT_API_KEY=xxx
MOONSHOT_BASE_URL=https://api.moonshot.cn/v1

# ============ 缓存配置 ============
CACHE_ENABLED=true
CACHE_TTL_SECONDS=3600
CACHE_MAX_SIZE=1000

# ============ 约束配置 ============
TITLE_MIN_LENGTH=15
TITLE_MAX_LENGTH=40
DUPLICATION_THRESHOLD=0.30
NOVELTY_MIN_SCORE=60
FEASIBILITY_MIN_SCORE=60
STYLE_MIN_SCORE=70

# ============ 限流配置 ============
RATE_LIMIT_ENABLED=true
RATE_LIMIT_RPM=60
RATE_LIMIT_BURST=10
TOKEN_QUOTA_DAILY=1000000

# ============ CORS 配置 ============
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
CORS_ALLOW_CREDENTIALS=true

# ============ 日志配置 ============
LOG_FILE=logs/thesisminer.log
LOG_MAX_SIZE_MB=10
LOG_BACKUP_COUNT=5
```

## 附录 B：常见问题快速排查

| 症状 | 可能原因 | 解决方案 |
|------|----------|----------|
| 启动报错 `ModuleNotFoundError` | 依赖未安装 | `pip install -r requirements.txt` |
| 启动报错 `KeyError: 'DEEPSEEK_API_KEY'` | .env 未配置 | 创建 .env 文件并填入 API Key |
| 模型测试失败 `401 Unauthorized` | API Key 错误 | 检查 .env 中的 API Key |
| 模型测试失败 `TimeoutError` | 网络问题 | 检查网络、配置代理 |
| 缓存命中率低 | Prompt 前缀不稳定 | 固化前缀，减少动态内容 |
| 图谱不显示 | D3.js 加载失败 | 检查浏览器控制台、清除缓存 |
| 数据库锁定 | 并发写入 | 减少并发数、使用 WAL 模式 |
| 响应慢 | 模型延迟高 | 切换更快的模型、启用缓存 |

---

## 附录 C：版本信息

| 组件 | 版本 |
|------|------|
| ThesisMiner | v8.0.0 |
| Python | 3.11+ |
| FastAPI | 0.104+ |
| Uvicorn | 0.24+ |
| SQLite | 3.35+ |
| D3.js | v7 |

---

> 本教程最后更新：2026-06-19
> 适用于 ThesisMiner v8.0 及以上版本
> 如有问题，请查阅 FAQ 或提交 GitHub Issue
