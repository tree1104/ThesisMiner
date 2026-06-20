# ThesisMiner v8.0 项目贡献指南

> 本文档详细描述如何为 ThesisMiner v8.0 项目贡献代码，包括开发流程、代码规范、提交规范与发布流程。

## 目录

- [1. 贡献概览](#1-贡献概览)
- [2. 开发环境搭建](#2-开发环境搭建)
- [3. 开发工作流](#3-开发工作流)
- [4. 代码规范](#4-代码规范)
- [5. 提交规范](#5-提交规范)
- [6. 代码审查](#6-代码审查)
- [7. 测试要求](#7-测试要求)
- [8. 文档要求](#8-文档要求)
- [9. 发布流程](#9-发布流程)
- [10. 社区准则](#10-社区准则)
- [11. 附录](#11-附录)

---

## 1. 贡献概览

### 1.1 贡献方式

1. **代码贡献**：修复 Bug、新增功能、性能优化
2. **文档贡献**：完善文档、翻译、教程
3. **测试贡献**：编写测试、报告 Bug
4. **设计贡献**：UI/UX 设计、架构设计
5. **社区贡献**：回答问题、帮助新用户

### 1.2 贡献流程

```
Fork → Clone → Branch → Code → Test → Commit → Push → PR → Review → Merge
```

---

## 2. 开发环境搭建

### 2.1 基础环境

```bash
# Python 3.11+
python --version

# Node.js 18+（前端工具）
node --version

# Git
git --version
```

### 2.2 项目克隆

```bash
# Fork 项目后
git clone https://github.com/your-username/ThesisMiner.git
cd ThesisMiner

# 添加上游
git remote add upstream https://github.com/tree1104/ThesisMiner.git
```

### 2.3 环境配置

```bash
# 虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API 密钥

# 初始化数据库
python -c "from backend.database import init_database; init_database()"

# 运行测试验证
pytest
```

---

## 3. 开发工作流

### 3.1 分支策略

采用 Git Flow 分支模型：

```
main          ← 稳定发布分支
  └── develop ← 开发主分支
       ├── feature/xxx  ← 功能分支
       ├── bugfix/xxx   ← 修复分支
       └── hotfix/xxx   ← 紧急修复
```

### 3.2 分支命名

| 类型 | 前缀 | 示例 |
|------|------|------|
| 功能 | feature/ | feature/multi-agent |
| 修复 | bugfix/ | bugfix/cache-hit-rate |
| 紧急 | hotfix/ | hotfix/security-patch |
| 文档 | docs/ | docs/api-tutorial |
| 重构 | refactor/ | refactor/session-manager |

### 3.3 开发流程

```bash
# 1. 同步上游
git checkout develop
git pull upstream develop

# 2. 创建分支
git checkout -b feature/my-feature

# 3. 开发并提交
git add .
git commit -m "feat: 新增功能描述"

# 4. 推送
git push origin feature/my-feature

# 5. 创建 Pull Request
# 在 GitHub 上创建 PR: feature/my-feature → develop
```

---

## 4. 代码规范

### 4.1 Python 代码规范

遵循 PEP 8，额外要求：

```python
# 类型注解（必须）
def create_conversation(session_id: str, title: str) -> Conversation:
    """创建对话
    
    Args:
        session_id: 会话 ID
        title: 对话标题
        
    Returns:
        Conversation 对象
        
    Raises:
        ValidationError: 标题为空时
    """
    if not title:
        raise ValidationError("标题不能为空")
    # ...
```

### 4.2 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 类 | PascalCase | ConversationManager |
| 函数 | snake_case | create_conversation |
| 变量 | snake_case | session_id |
| 常量 | UPPER_SNAKE | MAX_TOKENS |
| 私有 | _前缀 | _internal_method |

### 4.3 导入规范

```python
# 标准库
import os
import sys
from typing import Optional

# 第三方
import httpx
from fastapi import FastAPI

# 本项目
from backend.config import get_settings
from backend.database import get_db_connection
```

### 4.4 JavaScript 代码规范

```javascript
// ES2022+ 语法
// 2 空格缩进
// 单引号
// 分号结尾
// 驼峰命名

class ConversationManager {
    constructor(apiClient) {
        this.api = apiClient;
        this.conversations = new Map();
    }
    
    async create(title) {
        const response = await this.api.post('/api/conversations', { title });
        return response.data;
    }
}
```

---

## 5. 提交规范

### 5.1 Conventional Commits

```
<type>(<scope>): <subject>

<body>

<footer>
```

### 5.2 提交类型

| 类型 | 说明 | 示例 |
|------|------|------|
| feat | 新功能 | feat(agents): 新增 Orchestrator |
| fix | 修复 | fix(cache): 修复缓存命中率计算 |
| docs | 文档 | docs(api): 更新 API 文档 |
| style | 格式 | style: 代码格式化 |
| refactor | 重构 | refactor(sessions): 重构会话管理 |
| test | 测试 | test(agents): 新增 Agent 测试 |
| chore | 杂务 | chore: 更新依赖 |
| perf | 性能 | perf(db): 优化数据库查询 |

### 5.3 提交示例

```bash
# 好的提交
git commit -m "feat(agents): 新增 CriticAgent 用于论题评审

- 实现 4 维新颖性评分（学科交叉/方法迁移/痛点/趋势）
- 支持评分 < 60 时触发回退
- 新增 30 个单元测试

Closes #123"

# 差的提交（避免）
git commit -m "更新"
git commit -m "fix bug"
```

---

## 6. 代码审查

### 6.1 审查清单

- [ ] 代码符合规范
- [ ] 有充分的测试
- [ ] 测试通过
- [ ] 文档已更新
- [ ] 无明显安全问题
- [ ] 性能可接受
- [ ] 向后兼容
- [ ] 提交信息规范

### 6.2 审查流程

1. **自动检查**：CI 自动运行 lint、test
2. **人工审查**：至少 1 位审查者批准
3. **讨论修改**：根据反馈修改
4. **合并**：squash merge 或 rebase merge

---

## 7. 测试要求

### 7.1 测试覆盖

- 新功能必须有单元测试
- Bug 修复必须有回归测试
- 测试覆盖率不低于 85%

### 7.2 测试规范

```python
class TestNewFeature:
    """新功能测试"""
    
    def test_normal_case(self):
        """测试正常场景"""
        # Arrange
        # Act
        # Assert
        pass
    
    def test_edge_case(self):
        """测试边界条件"""
        pass
    
    def test_error_case(self):
        """测试异常场景"""
        pass
```

---

## 8. 文档要求

### 8.1 代码文档

- 所有公共函数有 docstring
- 复杂逻辑有注释
- 模块有模块级 docstring

### 8.2 项目文档

- 新功能需更新文档
- API 变更需更新 OpenAPI
- 重大变更需更新 CHANGELOG

---

## 9. 发布流程

### 9.1 版本号

遵循语义化版本：`MAJOR.MINOR.PATCH`

### 9.2 发布步骤

1. 更新版本号
2. 更新 CHANGELOG
3. 创建 release 分支
4. 运行完整测试
5. 合并到 main
6. 打 Tag
7. 构建发布包
8. 发布

---

## 10. 社区准则

### 10.1 行为准则

- 尊重所有贡献者
- 接受建设性批评
- 关注项目目标
- 帮助新贡献者

### 10.2 沟通渠道

- GitHub Issues：Bug 报告、功能请求
- GitHub Discussions：问题讨论、想法交流
- Pull Requests：代码贡献

---

## 11. 附录

### 11.1 常用命令

```bash
# 运行测试
pytest

# 代码格式化
black backend/
isort backend/

# 类型检查
mypy backend/

# Lint
flake8 backend/
pylint backend/

# 覆盖率
pytest --cov=backend --cov-report=html
```

### 11.2 资源链接

- [PEP 8](https://pep8.org/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Semantic Versioning](https://semver.org/)
- [Keep a Changelog](https://keepachangelog.com/)

---

## 结语

感谢您对 ThesisMiner 项目的关注与贡献！每一位贡献者都让这个项目变得更好。请遵循本指南，共同维护项目的质量与活力。
