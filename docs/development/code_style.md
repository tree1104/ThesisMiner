# ThesisMiner v8.0 代码风格规范完整指南

> **文档版本**：v8.0.0  
> **最后更新**：2026-06-19  
> **文档定位**：ThesisMiner 项目的代码风格权威指南，覆盖 Python、JavaScript、CSS 三大语言的风格规范、命名约定、Lint 配置、Git 工作流  
> **适用对象**：所有贡献者、开发者、代码审查者  

---

## 目录

- [1. 规范总览](#1-规范总览)
- [2. Python 代码风格](#2-python-代码风格)
- [3. JavaScript 代码风格](#3-javascript-代码风格)
- [4. CSS 代码风格](#4-css-代码风格)
- [5. HTML 代码风格](#5-html-代码风格)
- [6. 通用规范](#6-通用规范)
- [7. 文件组织](#7-文件组织)
- [8. Git 工作流](#8-git-工作流)
- [9. 代码审查](#9-代码审查)
- [10. 工具链配置](#10-工具链配置)
- [11. 附录](#11-附录)

---

## 1. 规范总览

### 1.1 设计哲学

ThesisMiner 代码风格规范遵循以下核心原则：

```
┌─────────────────────────────────────────────────────────────────┐
│                  代码风格设计哲学                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  原则一：一致性优先                                                │
│  ─────────────────                                               │
│  代码风格的一致性比个人偏好更重要。                                  │
│  所有代码必须遵循统一的风格规范，                                    │
│  使用自动化工具（Black/Prettier）强制格式化。                       │
│                                                                 │
│  原则二：可读性优先                                                │
│  ─────────────────                                               │
│  代码被阅读的次数远多于被编写的次数。                                │
│  优化可读性而非简洁性，                                             │
│  必要时牺牲简洁性来换取可读性。                                     │
│                                                                 │
│  原则三：显式优于隐式                                              │
│  ─────────────────                                               │
│  明确的代码优于隐式的魔法。                                         │
│  使用显式的类型标注、命名和注释，                                    │
│  避免过度使用元编程和魔法。                                         │
│                                                                 │
│  原则四：约定优于配置                                              │
│  ─────────────────                                               │
│  遵循语言社区的主流约定（PEP 8、ESLint 推荐），                     │
│  减少配置开销，降低新成员学习成本。                                  │
│                                                                 │
│  原则五：自动化优先                                                │
│  ─────────────────                                               │
│  能自动化的就不要手动。                                             │
│  使用 pre-commit hooks、CI/CD 流水线                               │
│  自动检查和修复代码风格问题。                                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 工具链概览

| 语言 | 格式化工具 | Lint 工具 | 类型检查 | 文档工具 |
|------|-----------|----------|---------|---------|
| Python | Black | Ruff | mypy | Sphinx |
| JavaScript | Prettier | ESLint | JSDoc | JSDoc |
| CSS | Prettier | Stylelint | - | - |
| HTML | Prettier | - | - | - |

### 1.3 强制级别定义

| 级别 | 含义 | 执行方式 |
|------|------|---------|
| **MUST** | 必须遵守 | pre-commit hook 拦截 |
| **SHOULD** | 强烈建议 | CI 检查警告 |
| **MAY** | 可选 | 代码审查建议 |

---

## 2. Python 代码风格

### 2.1 基础规范

ThesisMiner Python 代码遵循 PEP 8 规范，并使用 Black 进行自动格式化。

**缩进**：

```python
# ✅ 正确：4 个空格缩进
def example_function():
    if True:
        print("Hello")

# ❌ 错误：Tab 缩进
def example_function():
	if True:
		print("Hello")

# ❌ 错误：2 个空格缩进
def example_function():
  if True:
    print("Hello")
```

**行长度**：

```python
# 规则：每行不超过 100 个字符（Black 默认 88，ThesisMiner 扩展到 100）

# ✅ 正确：短行
result = process_data(input_data, config)

# ✅ 正确：长行换行（使用括号）
result = process_data(
    input_data,
    config,
    options={
        "timeout": 30,
        "retries": 3,
    }
)

# ✅ 正确：长字符串换行
message = (
    "这是一个很长的字符串，"
    "需要分成多行来书写，"
    "使用括号进行隐式连接。"
)

# ❌ 错误：反斜杠换行
result = input_data \
    + processed_data \
    + final_data
```

**空行规范**：

```python
# 顶层函数/类之间：2 个空行
def top_level_function_one():
    pass


def top_level_function_two():
    pass


class TopLevelClass:
    pass


# 类中方法之间：1 个空行
class MyClass:
    def method_one(self):
        pass

    def method_two(self):
        pass


# 函数内逻辑分组：可用 1 个空行（谨慎使用）
def complex_function():
    # 初始化阶段
    data = load_data()
    config = load_config()

    # 处理阶段
    result = process(data, config)

    # 返回阶段
    return result
```

### 2.2 命名约定

ThesisMiner 遵循 PEP 8 命名约定，并根据项目特点进行了扩展。

**命名规则总览**：

| 类型 | 命名风格 | 示例 |
|------|---------|------|
| 模块/文件 | snake_case | `session_manager.py` |
| 包/目录 | snake_case | `backend/agents/` |
| 类 | PascalCase | `SessionManager` |
| 异常 | PascalCase + Error | `SessionNotFoundError` |
| 函数 | snake_case | `create_session()` |
| 方法 | snake_case | `get_session()` |
| 变量 | snake_case | `session_id` |
| 常量 | UPPER_SNAKE_CASE | `MAX_SESSIONS` |
| 私有 | _前缀 | `_internal_method()` |
| 特殊 | __双下划线 | `__init__`, `__str__` |
| 类型变量 | PascalCase + T | `T`, `ResponseType` |
| 枚举 | UPPER_SNAKE_CASE | `SessionState.ACTIVE` |

**函数命名**：

```python
# ✅ 正确：动词开头，描述行为
def create_session(name: str) -> Session:
    pass

def get_session(session_id: str) -> Session:
    pass

def update_session(session_id: str, data: dict) -> Session:
    pass

def delete_session(session_id: str) -> bool:
    pass

def calculate_novelty_score(proposal: Proposal) -> float:
    pass

def validate_title_format(title: str) -> bool:
    pass

# ❌ 错误：名词开头，不描述行为
def session(name: str) -> Session:
    pass

# ❌ 错误：缩写不清晰
def get_sess(sid: str) -> Session:
    pass

# ❌ 错误：过于简短
def g(s: str) -> Session:
    pass
```

**类命名**：

```python
# ✅ 正确：名词，PascalCase
class SessionManager:
    pass

class ProposalGenerator:
    pass

class TransparentLedger:
    pass

class OrchestrationStateMachine:
    pass

# ✅ 正确：异常类以 Error 结尾
class SessionNotFoundError(Exception):
    pass

class ConstraintViolationError(Exception):
    pass

class BudgetExceededError(Exception):
    pass

# ❌ 错误：动词开头
class ManageSession:
    pass

# ❌ 错误：snake_case
class session_manager:
    pass
```

**常量命名**：

```python
# ✅ 正确：全大写，下划线分隔
MAX_SESSIONS = 10
DEFAULT_TIMEOUT = 120
SUPPORTED_MODELS = ["gpt-4.1", "deepseek-chat-v3"]
SESSION_STATES = ["active", "completed", "failed"]

# 配置常量
DATABASE_PATH = "data/thesisminer.db"
CACHE_PREFIX_LENGTH = 1024
RATE_LIMIT_WINDOW = 60

# ❌ 错误：camelCase
maxSessions = 10
defaultTimeout = 120

# ❌ 错误：snake_case
max_sessions = 10
default_timeout = 120
```

**布尔变量命名**：

```python
# ✅ 正确：is/has/can/should 前缀
is_active = True
has_permission = False
can_retry = True
should_cache = False
is_valid = validate(data)

# ❌ 错误：无前缀
active = True
permission = False
retry = True
cache = False
```

### 2.3 类型标注

ThesisMiner 强制使用类型标注（Type Hints），所有函数参数和返回值必须标注类型。

**基础类型标注**：

```python
# ✅ 正确：完整的类型标注
def create_session(
    name: str,
    degree: str,
    discipline: str,
    advisor: str | None = None,
) -> Session:
    pass

# ✅ 正确：Optional 类型
def get_session(session_id: str) -> Session | None:
    pass

# ✅ 正确：容器类型
def list_sessions(
    page: int = 1,
    size: int = 20,
) -> list[Session]:
    pass

# ✅ 正确：字典类型
def update_config(config: dict[str, Any]) -> bool:
    pass

# ✅ 正确：元组类型
def get_session_stats() -> tuple[int, float, float]:
    """返回 (消息数, Token 数, 成本)"""
    pass

# ❌ 错误：无类型标注
def create_session(name, degree, discipline, advisor=None):
    pass
```

**复杂类型标注**：

```python
from typing import Any, Callable, TypeVar, Generic, Protocol
from collections.abc import Awaitable

# TypeVar
T = TypeVar("T")
ResponseType = TypeVar("ResponseType")

# 泛型类
class Repository(Generic[T]):
    def get(self, id: str) -> T | None:
        pass

    def save(self, entity: T) -> bool:
        pass

# Callable 类型
HookFunction = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]

def register_hook(name: str, func: HookFunction) -> None:
    pass

# Protocol（结构化类型）
class AgentProtocol(Protocol):
    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        ...

# TypedDict
from typing import TypedDict

class SessionConfig(TypedDict):
    name: str
    degree: str
    discipline: str
    advisor: str | None

# Literal 类型
from typing import Literal

def set_log_level(level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]) -> None:
    pass
```

### 2.4 Docstring 规范

ThesisMiner 使用 Google 风格的 docstring。

**函数 docstring**：

```python
def calculate_novelty_score(
    proposal: Proposal,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """计算论题的新颖性评分。

    该函数通过四个维度（学科交叉、方法迁移、痛点突破、趋势前瞻）
    计算论题的综合新颖性评分。每个维度独立评分（0-100），最终
    通过加权平均得到综合评分。

    Args:
        proposal: 论题对象，包含标题、摘要、研究方法等信息。
        weights: 各维度权重，默认为均等权重（各 0.25）。
            如果提供，必须包含以下键：
            - cross_discipline: 学科交叉权重
            - method_transfer: 方法迁移权重
            - pain_point: 痛点突破权重
            - trend_foresight: 趋势前瞻权重

    Returns:
        包含以下键的字典：
        - total_score: 综合评分（0-100）
        - sub_scores: 各子维度评分
        - level: 评分等级（卓越/优秀/良好/一般/较弱）
        - penalty: 惩罚分数
        - issues: 潜在问题列表

    Raises:
        ValueError: 如果 weights 的值之和不为 1.0。
        TypeError: 如果 proposal 不是 Proposal 类型。

    Example:
        >>> proposal = Proposal(title="基于量子计算的联邦学习")
        >>> result = calculate_novelty_score(proposal)
        >>> result["total_score"]
        88.75
    """
    pass
```

**类 docstring**：

```python
class SessionManager:
    """会话管理器，负责会话的创建、查询、更新和删除。

    SessionManager 是 ThesisMiner 会话管理的核心组件，提供会话的
    全生命周期管理。支持多会话并行、上下文压缩（DST）、状态追踪
    等功能。

    Attributes:
        db: 数据库连接实例。
        cache: 会话缓存，用于加速频繁访问的会话。
        max_sessions: 最大会话数限制。

    Example:
        >>> manager = SessionManager(db)
        >>> session = manager.create("我的论题", "master", "计算机科学")
        >>> session.id
        'sess-abc123'
    """

    def __init__(self, db: Database, max_sessions: int = 10):
        """初始化会话管理器。

        Args:
            db: 数据库连接实例。
            max_sessions: 最大并发会话数，默认为 10。
        """
        self.db = db
        self.max_sessions = max_sessions
        self._cache: dict[str, Session] = {}
```

### 2.5 导入规范

```python
# ✅ 正确：导入顺序
# 1. 标准库
import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# 2. 第三方库
import fastapi
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import openai

# 3. 本项目模块
from backend.config import Config
from backend.models import Session, Proposal
from backend.agents.reasoner_proposal import ReasonerAgent

# ✅ 正确：使用 from 导入特定名称
from backend.models import Session, Proposal

# ❌ 错误：通配符导入
from backend.models import *

# ❌ 错误：导入顺序混乱
import openai
import os
from backend.models import Session
from datetime import datetime

# ✅ 正确：避免循环导入
# 在函数内部导入
def get_agent_registry():
    from backend.agents.registry import AGENT_REGISTRY
    return AGENT_REGISTRY
```

### 2.6 异常处理

```python
# ✅ 正确：具体异常类型
try:
    session = manager.get(session_id)
except SessionNotFoundError:
    raise HTTPException(status_code=404, detail="会话不存在")
except DatabaseError as e:
    logger.error(f"数据库错误: {e}")
    raise HTTPException(status_code=500, detail="服务器内部错误")

# ✅ 正确：自定义异常
class ThesisMinerError(Exception):
    """ThesisMiner 基础异常类。"""
    pass

class SessionError(ThesisMinerError):
    """会话相关异常。"""
    pass

class SessionNotFoundError(SessionError):
    """会话不存在异常。"""
    def __init__(self, session_id: str):
        self.session_id = session_id
        super().__init__(f"会话不存在: {session_id}")

# ❌ 错误：捕获所有异常
try:
    session = manager.get(session_id)
except Exception:
    pass  # 吞掉异常

# ❌ 错误：裸 except
try:
    session = manager.get(session_id)
except:
    pass
```

### 2.7 异步编程

```python
import asyncio
from collections.abc import AsyncGenerator

# ✅ 正确：async/await
async def generate_proposal(session_id: str) -> Proposal:
    """异步生成论题。"""
    session = await get_session(session_id)
    reasoner_result = await call_reasoner(session)
    mentor_result = await call_mentor(reasoner_result)
    return mentor_result

# ✅ 正确：并发执行
async def generate_multiple_proposals(session_ids: list[str]) -> list[Proposal]:
    """并发生成多个论题。"""
    tasks = [generate_proposal(sid) for sid in session_ids]
    return await asyncio.gather(*tasks)

# ✅ 正确：流式输出
async def stream_proposal(session_id: str) -> AsyncGenerator[str, None]:
    """流式输出论题生成过程。"""
    async for chunk in call_reasoner_stream(session_id):
        yield chunk

# ✅ 正确：超时处理
async def call_with_timeout(agent: Agent, timeout: float = 120):
    """带超时的 Agent 调用。"""
    try:
        return await asyncio.wait_for(agent.run(), timeout=timeout)
    except asyncio.TimeoutError:
        raise AgentTimeoutError(f"Agent 超时: {timeout}s")

# ❌ 错误：在异步函数中使用同步阻塞调用
async def bad_example():
    time.sleep(5)  # 阻塞事件循环
    requests.get("http://example.com")  # 阻塞事件循环
```

### 2.8 Black 配置

```toml
# pyproject.toml

[tool.black]
line-length = 100
target-version = ['py310', 'py311', 'py312']
include = '\.pyi?$'
extend-exclude = '''
/(
    \.eggs
  | \.git
  | \.venv
  | build
  | dist
  | migrations
)/
'''
```

### 2.9 Ruff 配置

```toml
# pyproject.toml

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
    "N",   # pep8-naming
    "SIM", # flake8-simplify
    "TCH", # flake8-type-checking
    "RUF", # ruff-specific rules
]
ignore = [
    "E501",  # line too long (handled by Black)
    "B008",  # do not perform function call in argument defaults
]

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]  # unused imports in __init__.py
"tests/*" = ["B011"]      # assert False in tests

[tool.ruff.lint.isort]
known-first-party = ["backend"]
force-single-line = false
```

### 2.10 mypy 配置

```toml
# pyproject.toml

[tool.mypy]
python_version = "3.10"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
warn_unreachable = true

[[tool.mypy.overrides]]
module = "openai.*"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "d3.*"
ignore_missing_imports = true
```

---

## 3. JavaScript 代码风格

### 3.1 基础规范

**缩进与分号**：

```javascript
// ✅ 正确：2 个空格缩进，无分号（Prettier 默认）
function example() {
  if (true) {
    console.log('Hello')
  }
}

// ❌ 错误：4 个空格缩进
function example() {
    if (true) {
        console.log('Hello')
    }
}

// ❌ 错误：使用分号
function example() {
  console.log('Hello');
}
```

**引号**：

```javascript
// ✅ 正确：单引号
const name = 'ThesisMiner'
const message = 'Hello, World!'

// ✅ 正确：模板字符串
const greeting = `Hello, ${name}!`

// ❌ 错误：双引号
const name = "ThesisMiner"
```

**变量声明**：

```javascript
// ✅ 正确：const 优先
const MAX_SESSIONS = 10
const config = { timeout: 30 }

// ✅ 正确：let 用于可变变量
let count = 0
count += 1

// ❌ 错误：var
var count = 0
```

### 3.2 命名约定

| 类型 | 命名风格 | 示例 |
|------|---------|------|
| 变量 | camelCase | `sessionId` |
| 常量 | UPPER_SNAKE_CASE | `MAX_SESSIONS` |
| 函数 | camelCase | `createSession()` |
| 类 | PascalCase | `SessionManager` |
| 组件 | PascalCase | `SessionList` |
| 文件（组件） | PascalCase | `SessionList.js` |
| 文件（工具） | camelCase | `sessionUtils.js` |
| CSS 类 | kebab-case | `session-card` |
| 事件 | on+Event | `onSessionCreate` |
| 布尔 | is/has/can | `isActive`, `hasPermission` |

### 3.3 ES6+ 规范

**箭头函数**：

```javascript
// ✅ 正确：箭头函数
const createSession = (name, degree) => {
  return fetch('/api/sessions', {
    method: 'POST',
    body: JSON.stringify({ name, degree }),
  })
}

// ✅ 正确：简短箭头函数
const getSessionId = (session) => session.id
const isActive = (session) => session.state === 'active'

// ❌ 错误：不必要的箭头函数
const getSessionId = (session) => {
  return session.id
}
```

**解构赋值**：

```javascript
// ✅ 正确：对象解构
const { id, name, state } = session
const { title, abstract } = proposal

// ✅ 正确：函数参数解构
function renderSession({ id, name, state }) {
  return `<div>${name}</div>`
}

// ✅ 正确：重命名
const { id: sessionId, name: sessionName } = session

// ✅ 正确：默认值
const { timeout = 30, retries = 3 } = config

// ❌ 错误：不使用解构
const id = session.id
const name = session.name
const state = session.state
```

**展开运算符**：

```javascript
// ✅ 正确：对象展开
const updatedSession = { ...session, state: 'completed' }

// ✅ 正确：数组展开
const allSessions = [...activeSessions, ...completedSessions]

// ✅ 正确：合并配置
const mergedConfig = { ...defaultConfig, ...userConfig }
```

**模板字符串**：

```javascript
// ✅ 正确：模板字符串
const message = `会话 ${session.name} 已创建，ID: ${session.id}`
const url = `/api/sessions/${sessionId}/proposals`

// ❌ 错误：字符串拼接
const message = '会话 ' + session.name + ' 已创建，ID: ' + session.id
```

**async/await**：

```javascript
// ✅ 正确：async/await
async function generateProposal(sessionId) {
  try {
    const response = await fetch(`/api/sessions/${sessionId}/proposals`, {
      method: 'POST',
    })
    const data = await response.json()
    return data
  } catch (error) {
    console.error('生成论题失败:', error)
    throw error
  }
}

// ✅ 正确：并发请求
async function loadDashboard() {
  const [sessions, proposals, budgets] = await Promise.all([
    fetch('/api/sessions').then((r) => r.json()),
    fetch('/api/proposals').then((r) => r.json()),
    fetch('/api/budgets/summary').then((r) => r.json()),
  ])
  return { sessions, proposals, budgets }
}
```

### 3.4 JSDoc 规范

```javascript
/**
 * 创建新会话
 *
 * @param {string} name - 会话名称
 * @param {string} degree - 学位级别 ('master' | 'doctor')
 * @param {string} discipline - 学科领域
 * @param {string} [advisor] - 导师姓名（可选）
 * @returns {Promise<Session>} 创建的会话对象
 * @throws {Error} 当会话名称已存在时抛出错误
 *
 * @example
 * const session = await createSession('我的论题', 'master', '计算机科学')
 * console.log(session.id) // 'sess-abc123'
 */
async function createSession(name, degree, discipline, advisor) {
  // ...
}

/**
 * @typedef {Object} Session
 * @property {string} id - 会话 ID
 * @property {string} name - 会话名称
 * @property {string} degree - 学位级别
 * @property {string} discipline - 学科领域
 * @property {string} state - 会话状态
 * @property {Date} createdAt - 创建时间
 */
```

### 3.5 ESLint 配置

```javascript
// .eslintrc.js
module.exports = {
  env: {
    browser: true,
    es2021: true,
    node: true,
  },
  extends: [
    'eslint:recommended',
    'prettier',
  ],
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
  },
  rules: {
    'no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
    'no-console': ['warn', { allow: ['warn', 'error'] }],
    'prefer-const': 'error',
    'no-var': 'error',
    'eqeqeq': ['error', 'always'],
    'curly': ['error', 'all'],
    'no-throw-literal': 'error',
    'prefer-arrow-callback': 'error',
    'prefer-template': 'error',
    'object-shorthand': 'error',
  },
}
```

### 3.6 Prettier 配置

```javascript
// .prettierrc
{
  "semi": false,
  "singleQuote": true,
  "tabWidth": 2,
  "trailingComma": "es5",
  "printWidth": 100,
  "arrowParens": "always",
  "endOfLine": "lf",
  "bracketSpacing": true,
  "jsxSingleQuote": false,
  "jsxBracketSameLine": false
}
```

---

## 4. CSS 代码风格

### 4.1 命名规范

ThesisMiner 使用 BEM（Block Element Modifier）命名规范。

```css
/* ✅ 正确：BEM 命名 */

/* Block */
.session-card {
  /* ... */
}

/* Element */
.session-card__title {
  /* ... */
}

.session-card__body {
  /* ... */
}

/* Modifier */
.session-card--active {
  /* ... */
}

.session-card--disabled {
  /* ... */
}

/* ❌ 错误：非 BEM 命名 */
.sessionCardTitle {
  /* ... */
}

.session-card-title {
  /* ... */
}
```

### 4.2 属性顺序

```css
/* ✅ 正确：属性按类型分组 */

.session-card {
  /* 1. 布局属性 */
  display: flex;
  flex-direction: column;
  position: relative;

  /* 2. 盒模型属性 */
  width: 300px;
  height: auto;
  margin: 16px;
  padding: 20px;

  /* 3. 边框属性 */
  border: 1px solid #e0e0e0;
  border-radius: 8px;

  /* 4. 背景属性 */
  background-color: #ffffff;

  /* 5. 文本属性 */
  color: #333333;
  font-size: 14px;
  line-height: 1.5;
  text-align: left;

  /* 6. 视觉属性 */
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  opacity: 1;

  /* 7. 动画属性 */
  transition: all 0.3s ease;
}
```

### 4.3 Tailwind CSS 规范

```html
<!-- ✅ 正确：Tailwind 类名按顺序排列 -->
<div class="flex items-center justify-between p-4 bg-white rounded-lg shadow-md">
  <h2 class="text-lg font-semibold text-gray-800">会话标题</h2>
  <button class="px-4 py-2 text-white bg-blue-500 rounded hover:bg-blue-600">
    操作
  </button>
</div>

<!-- ❌ 错误：类名顺序混乱 -->
<div class="shadow-md rounded-lg bg-white p-4 justify-between flex items-center">
  <h2 class="text-gray-800 font-semibold text-lg">会话标题</h2>
</div>
```

**Tailwind 类名顺序**：

1. 布局：`flex`, `grid`, `block`, `inline`
2. 定位：`relative`, `absolute`, `fixed`
3. 间距：`p-*`, `m-*`, `gap-*`
4. 尺寸：`w-*`, `h-*`
5. 边框：`border`, `rounded`
6. 背景：`bg-*`
7. 文本：`text-*`, `font-*`
8. 视觉：`shadow-*`, `opacity-*`
9. 交互：`hover:*`, `focus:*`

### 4.4 响应式断点

```css
/* ThesisMiner 响应式断点 */
/*
  sm:  640px   (手机横屏)
  md:  768px   (平板竖屏)
  lg:  1024px  (平板横屏/小笔记本)
  xl:  1280px  (桌面显示器)
  2xl: 1536px  (大屏显示器)
*/

/* ✅ 正确：移动优先 */
.container {
  width: 100%;        /* 默认（移动端） */
  padding: 16px;
}

@media (min-width: 768px) {
  .container {
    max-width: 720px;
    padding: 24px;
  }
}

@media (min-width: 1024px) {
  .container {
    max-width: 960px;
    padding: 32px;
  }
}
```

### 4.5 Stylelint 配置

```javascript
// .stylelintrc.js
module.exports = {
  extends: ['stylelint-config-standard', 'stylelint-config-prettier'],
  rules: {
    'selector-class-pattern': '^[a-z]([a-z0-9-]+)?(__[a-z0-9-]+)?(--[a-z0-9-]+)?$', // BEM
    'no-descending-specificity': true,
    'no-duplicate-selectors': true,
    'declaration-block-no-duplicate-properties': true,
    'color-hex-length': 'short',
    'color-no-hex': null,
    'font-family-name-quotes': 'always-where-recommended',
    'property-no-vendor-prefix': true,
    'value-no-vendor-prefix': true,
    'at-rule-no-unknown': [
      true,
      {
        ignoreAtRules: ['tailwind', 'apply', 'variants', 'responsive', 'screen'],
      },
    ],
  },
}
```

---

## 5. HTML 代码风格

```html
<!-- ✅ 正确：语义化标签 -->
<article class="session-card">
  <header class="session-card__header">
    <h2 class="session-card__title">论题会话</h2>
    <span class="session-card__badge session-card__badge--active">进行中</span>
  </header>
  <main class="session-card__body">
    <p class="session-card__description">基于深度学习的图像识别研究</p>
  </main>
  <footer class="session-card__footer">
    <button class="btn btn--primary" type="button">查看详情</button>
  </footer>
</article>

<!-- ❌ 错误：div 滥用 -->
<div class="session-card">
  <div class="header">
    <div class="title">论题会话</div>
  </div>
  <div class="body">
    <div class="description">基于深度学习的图像识别研究</div>
  </div>
</div>
```

---

## 6. 通用规范

### 6.1 注释规范

**Python 注释**：

```python
# ✅ 正确：行内注释，解释"为什么"
# 使用 SHA-256 的前 1024 字符作为缓存前缀，平衡命中率和唯一性
cache_prefix = sha256_hash(prompt)[:1024]

# ✅ 正确：块注释，解释复杂逻辑
# 三段式 Prompt 结构：
# 1. 稳定前缀（系统提示 + 角色定义）—— 用于缓存命中
# 2. 动态中段（用户输入 + 上下文）—— 每次变化
# 3. DST 尾部（对话状态）—— 压缩后追加
prompt = build_three_segment_prompt(system, user_input, dst_state)

# ❌ 错误：解释"是什么"（代码本身已说明）
# 设置超时为 120 秒
timeout = 120

# ❌ 错误：过时的注释
# 使用 OpenAI GPT-3 模型（实际已改为 GPT-4.1）
model = "gpt-4.1"
```

**TODO 注释**：

```python
# TODO(zhang_san): 添加流式输出支持 - 2026-07-01
# FIXME: DST 压缩在超长对话时可能丢失关键信息
# HACK: 临时绕过 OpenAI API 的 429 限制，需要优化重试策略
# XXX: 这段代码需要重构，复杂度过高
```

### 6.2 文件编码

- 所有源代码文件使用 UTF-8 编码
- Python 文件头部添加编码声明（Python 3 默认 UTF-8，无需声明）
- 换行符使用 LF（Unix 风格），不使用 CRLF（Windows 风格）

### 6.3 文件末尾

- 所有文件以一个空行结尾
- 不使用多个空行结尾

---

## 7. 文件组织

### 7.1 目录结构

```
ThesisMiner/
├── backend/                 # 后端代码
│   ├── agents/              # 智能体
│   │   ├── __init__.py
│   │   ├── base_agent.py    # Agent 基类
│   │   ├── reasoner_proposal.py
│   │   ├── mentor_agent.py
│   │   └── searcher_wrapper.py
│   ├── ai/                  # AI 调用层
│   │   ├── __init__.py
│   │   ├── ai_proxy.py
│   │   └── prompts.py
│   ├── config.py            # 配置管理
│   ├── database.py          # 数据库管理
│   ├── models.py            # 数据模型
│   └── routes/              # API 路由
│       ├── __init__.py
│       ├── sessions.py
│       └── proposals.py
├── frontend/                # 前端代码
│   ├── index.html
│   ├── js/
│   │   ├── app.js
│   │   └── components/
│   └── css/
│       └── styles.css
├── tests/                   # 测试代码
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── docs/                    # 文档
├── samples/                 # 示例代码
└── main.py                  # 应用入口
```

### 7.2 模块划分原则

1. **单一职责**：每个模块只负责一个功能领域
2. **高内聚低耦合**：模块内部高度相关，模块之间依赖最小
3. **依赖方向**：上层模块依赖下层模块，不可反向
4. **接口稳定**：公开接口保持稳定，内部实现可变

```
依赖层次（从上到下）：

  routes/ (API 路由层)
      ↓
  agents/ (智能体层)
      ↓
  orchestration/ (编排层)
      ↓
  ai/ (AI 调用层)    constraints/ (约束层)    sessions/ (会话层)
      ↓                   ↓                      ↓
  config.py (配置)    database.py (数据库)    models.py (模型)
```

### 7.3 导入排序

使用 `isort`（通过 Ruff 集成）自动排序导入：

```python
# 1. 标准库
import os
import sys
from datetime import datetime
from pathlib import Path

# 2. 第三方库
import openai
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# 3. 本项目模块
from backend.agents.reasoner_proposal import ReasonerAgent
from backend.config import Config
from backend.models import Session, Proposal
```

### 7.4 循环依赖处理

```python
# ❌ 错误：循环依赖
# module_a.py
from module_b import func_b

def func_a():
    func_b()

# module_b.py
from module_a import func_a  # 循环依赖！

def func_b():
    func_a()


# ✅ 正确：延迟导入
# module_a.py
def func_a():
    from module_b import func_b  # 延迟导入
    func_b()

# ✅ 正确：依赖注入
# module_a.py
class ClassA:
    def __init__(self, b_factory):
        self._b_factory = b_factory

    def method_a(self):
        b = self._b_factory()
        b.method_b()

# ✅ 正确：提取公共模块
# common.py
def shared_function():
    pass

# module_a.py 和 module_b.py 都从 common.py 导入
```

---

## 8. Git 工作流

### 8.1 分支策略

```
main          ← 稳定发布分支
  ↑
develop       ← 开发集成分支
  ↑
feature/*     ← 功能开发分支
hotfix/*      ← 紧急修复分支
release/*     ← 发布准备分支
```

**分支命名规范**：

| 分支类型 | 命名格式 | 示例 |
|---------|---------|------|
| 功能分支 | `feature/{描述}` | `feature/multi-agent-orchestration` |
| 修复分支 | `fix/{描述}` | `fix/dst-compression-error` |
| 热修复 | `hotfix/{描述}` | `hotfix/cache-prefix-bug` |
| 发布分支 | `release/{版本}` | `release/v8.0.0` |
| 文档分支 | `docs/{描述}` | `docs/api-reference` |

### 8.2 提交规范

ThesisMiner 使用 Conventional Commits 规范：

```
<type>(<scope>): <subject>

<body>

<footer>
```

**提交类型**：

| 类型 | 说明 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat(agents): 添加自定义 Agent 注册功能` |
| `fix` | 修复 Bug | `fix(cache): 修复前缀哈希不一致问题` |
| `docs` | 文档更新 | `docs(api): 更新错误码参考文档` |
| `style` | 代码风格 | `style(python): 应用 Black 格式化` |
| `refactor` | 重构 | `refactor(sessions): 重构会话管理器` |
| `test` | 测试 | `test(agents): 添加 Reasoner Agent 测试` |
| `chore` | 构建/工具 | `chore(deps): 升级 FastAPI 到 0.100` |
| `perf` | 性能优化 | `perf(cache): 优化 SHA-256 哈希性能` |

**提交示例**：

```
feat(agents): 添加多 Agent 编排状态机

实现 OrchestrationStateMachine，支持以下状态转换：
- init → inspiring：初始化到创意激发
- inspiring → reasoning：创意到推理
- reasoning → validating：推理到校验
- validating → completed/failed：校验到完成/失败

包含 pre_search、post_reasoner、feasibility、hard_rule 四个 Hook。

Closes #123
```

### 8.3 PR 模板

```markdown
## 变更描述

<!-- 简要描述本次变更的内容和目的 -->

## 变更类型

- [ ] 新功能 (feat)
- [ ] Bug 修复 (fix)
- [ ] 文档更新 (docs)
- [ ] 代码风格 (style)
- [ ] 重构 (refactor)
- [ ] 测试 (test)
- [ ] 构建/工具 (chore)
- [ ] 性能优化 (perf)

## 检查清单

- [ ] 代码已通过 Black 格式化
- [ ] 代码已通过 Ruff 检查
- [ ] 代码已通过 mypy 类型检查
- [ ] 已添加必要的测试
- [ ] 所有测试通过
- [ ] 已更新相关文档
- [ ] 提交消息遵循 Conventional Commits

## 测试说明

<!-- 描述如何测试本次变更 -->

## 关联 Issue

<!-- 关联的 Issue 编号，如 Closes #123 -->
```

---

## 9. 代码审查

### 9.1 审查清单

**功能正确性**：

- [ ] 代码实现了预期功能
- [ ] 边界条件已处理
- [ ] 错误处理完善
- [ ] 日志记录适当

**代码质量**：

- [ ] 命名清晰且有意义
- [ ] 函数/类职责单一
- [ ] 无重复代码
- [ ] 无魔法数字
- [ ] 注释解释了"为什么"而非"是什么"

**类型安全**：

- [ ] 所有函数有类型标注
- [ ] 无 `Any` 类型滥用
- [ ] Optional 类型正确使用

**性能**：

- [ ] 无不必要的数据库查询
- [ ] 无 N+1 查询问题
- [ ] 大数据集使用分页
- [ ] 异步操作正确使用

**安全**：

- [ ] 无 SQL 注入风险
- [ ] 无 XSS 风险
- [ ] API Key 未硬编码
- [ ] 用户输入已验证

**测试**：

- [ ] 单元测试覆盖核心逻辑
- [ ] 测试用例包含正常/异常/边界情况
- [ ] 测试命名清晰
- [ ] 测试独立可重复

### 9.2 审查流程

```
1. 提交 PR
   ↓
2. 自动化检查（CI）
   - Black 格式检查
   - Ruff Lint 检查
   - mypy 类型检查
   - 单元测试
   ↓
3. 代码审查（至少 1 人）
   - 功能正确性
   - 代码质量
   - 测试覆盖
   ↓
4. 修改（如有）
   ↓
5. 批准合并
   ↓
6. 合并到 develop
```

---

## 10. 工具链配置

### 10.1 pre-commit 配置

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.3.0
    hooks:
      - id: black
        language_version: python3

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.3.0
    hooks:
      - id: ruff
        args: [--fix]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.9.0
    hooks:
      - id: mypy
        additional_dependencies: [types-requests, pydantic]

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-merge-conflict
      - id: debug-statements
```

### 10.2 VS Code 配置

```json
// .vscode/settings.json
{
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "ms-python.black-formatter",
  "python.formatting.provider": "black",
  "python.formatting.blackArgs": ["--line-length", "100"],
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "python.linting.mypyEnabled": true,
  "python.analysis.typeCheckingMode": "strict",
  "editor.rulers": [100],
  "files.eol": "\n",
  "files.insertFinalNewline": true,
  "files.trimTrailingWhitespace": true
}
```

### 10.3 Makefile

```makefile
# Makefile

.PHONY: format lint type-check test check install

install:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
	pre-commit install

format:
	black backend/ tests/
	ruff check --fix backend/ tests/

lint:
	ruff check backend/ tests/
	stylelint "frontend/css/**/*.css"
	eslint "frontend/js/**/*.js"

type-check:
	mypy backend/

test:
	pytest tests/ -v --cov=backend

check: format lint type-check test
	@echo "所有检查通过！"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache .ruff_cache
```

---

## 11. 附录

### 11.1 常见问题

**Q1：Black 和 Ruff 冲突怎么办？**  
A：Black 负责格式化，Ruff 负责 Lint。确保 Ruff 配置中 `ignore` 了 `E501`（行长度，由 Black 处理）。

**Q2：如何处理 mypy 类型错误？**  
A：优先修复类型错误。如果是第三方库的类型缺失，使用 `# type: ignore` 并添加注释说明原因。

**Q3：什么时候使用 `Any` 类型？**  
A：尽量避免使用 `Any`。如果确实需要（如动态 JSON），使用 `dict[str, Any]` 并在文档中说明结构。

**Q4：如何命名布尔变量？**  
A：使用 `is_`/`has_`/`can_`/`should_` 前缀，如 `is_active`、`has_permission`。

**Q5：函数参数过多怎么办？**  
A：超过 5 个参数时，考虑使用参数对象（dataclass 或 TypedDict）。

### 11.2 参考文档

- [PEP 8](https://peps.python.org/pep-0008/) - Python 代码风格指南
- [Black](https://black.readthedocs.io/) - Python 代码格式化工具
- [Ruff](https://docs.astral.sh/ruff/) - Python Lint 工具
- [mypy](https://mypy.readthedocs.io/) - Python 静态类型检查
- [ESLint](https://eslint.org/) - JavaScript Lint 工具
- [Prettier](https://prettier.io/) - 代码格式化工具
- [Conventional Commits](https://www.conventionalcommits.org/) - 提交消息规范
- [BEM](https://getbem.com/) - CSS 命名规范

### 11.3 风格检查命令速查

```bash
# Python
black --check backend/           # 检查格式
black backend/                   # 自动格式化
ruff check backend/              # Lint 检查
ruff check --fix backend/        # Lint 自动修复
mypy backend/                    # 类型检查

# JavaScript
npx eslint frontend/js/          # Lint 检查
npx eslint --fix frontend/js/    # Lint 自动修复
npx prettier --check frontend/   # 检查格式
npx prettier --write frontend/   # 自动格式化

# CSS
npx stylelint "frontend/css/**/*.css"           # Lint 检查
npx stylelint "frontend/css/**/*.css" --fix     # Lint 自动修复

# 全部检查
make check                       # 运行所有检查
```

---

> **文档结束**  
> 本文档是 ThesisMiner v8.0 代码风格的完整指南。所有贡献者必须遵循本规范。如有疑问，请在 PR 中讨论或联系维护团队。