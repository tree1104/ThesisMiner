# ThesisMiner v8.0 项目说明

> ThesisMiner v8.0 - 基于 AI 多 Agent 架构的学术论题挖掘系统

## 项目简介

ThesisMiner v8.0 是一个基于多 Agent 架构的学术论题挖掘系统，通过模拟真实的学术指导流程，帮助研究者发现、论证与完善研究论题。

## 核心特性

- **多 Agent 架构**：Orchestrator + 5 个子 Agent（Searcher/Reasoner/Critic/Mentor/Writer）
- **五阶段闭环**：信息确权→创意→校验→生成→深度辅助
- **DeepSeek 缓存优化**：三段式 Prompt，缓存命中率 ≥95%
- **多对话管理**：多对话并存，上下文完全隔离
- **D3.js 谱系图谱**：力导向交互式可视化
- **2026 最新模型**：支持 10 个最新 AI 模型
- **联网搜索支持**：智能解析引用并展示

## 技术栈

- **后端**：Python 3.11+, FastAPI, SQLite (WAL)
- **前端**：原生 JavaScript, D3.js v7
- **测试**：pytest, 800+ 测试用例
- **代码量**：≥10MB

## 快速开始

```bash
# 克隆项目
git clone https://github.com/tree1104/ThesisMiner.git
cd ThesisMiner

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API 密钥

# 启动
python main.py
```

## 项目结构

```
ThesisMiner/
├── backend/          # 后端代码
├── frontend/         # 前端代码
├── tests/            # 测试
├── docs/             # 文档
├── config/           # 配置
├── data/             # 数据
└── main.py           # 入口
```

## 文档

- [架构文档](docs/architecture/)
- [约束文档](docs/constraints/)
- [API 文档](docs/api/)
- [开发文档](docs/development/)
- [教程文档](docs/tutorials/)
- [参考文档](docs/reference/)

## 许可证

MIT License - 详见 [LICENSE](LICENSE)

## 贡献

欢迎贡献！请阅读 [贡献指南](docs/development/contributing.md)。

## 联系

- GitHub: https://github.com/tree1104/ThesisMiner
- Issues: https://github.com/tree1104/ThesisMiner/issues

---

Copyright (c) 2026 tree1104
