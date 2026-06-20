# ThesisMiner v8.0 常见问题解答（FAQ）

> **文档版本**：v8.0.0  
> **最后更新**：2026-06-19  
> **文档定位**：ThesisMiner 常见问题的完整问答集，覆盖安装配置、模型选择、会话管理、五阶段流程、谱系图谱、预算统计、开发贡献、部署运维等 80+ 问题  
> **适用对象**：所有用户  

---

## 目录

- [1. 安装配置类](#1-安装配置类)
- [2. 模型选择类](#2-模型选择类)
- [3. 会话管理类](#3-会话管理类)
- [4. 五阶段流程类](#4-五阶段流程类)
- [5. 谱系图谱类](#5-谱系图谱类)
- [6. 预算统计类](#6-预算统计类)
- [7. 开发贡献类](#7-开发贡献类)
- [8. 部署运维类](#8-部署运维类)

---

## 1. 安装配置类

### Q1.1：ThesisMiner 的系统要求是什么？

**答**：ThesisMiner v8.0 的系统要求如下：

| 要求项 | 最低配置 | 推荐配置 |
|--------|---------|---------|
| 操作系统 | Windows 10 / macOS 11 / Ubuntu 20.04 | Windows 11 / macOS 14 / Ubuntu 22.04 |
| Python | 3.10+ | 3.11+ |
| 内存 | 2GB | 4GB+ |
| 磁盘 | 500MB | 1GB+ |
| 网络 | 需要访问 AI API | 稳定的网络连接 |
| 浏览器 | Chrome 90+ / Firefox 88+ / Safari 14+ | 最新版本 |

### Q1.2：如何安装 ThesisMiner？

**答**：

```bash
# 1. 克隆仓库
git clone https://github.com/your-org/ThesisMiner.git
cd ThesisMiner

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate     # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入 API Key

# 5. 初始化数据库
python -m backend.database init

# 6. 启动服务
python main.py
```

### Q1.3：如何配置 API Key？

**答**：ThesisMiner 支持三种方式配置 API Key：

**方式一：环境变量（推荐）**

```bash
# .env 文件
OPENAI_API_KEY=sk-xxxxxxxxxxxx
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxx
QWEN_API_KEY=sk-xxxxxxxxxxxx
```

**方式二：config.json**

```json
{
  "api_keys": {
    "openai": "sk-xxxxxxxxxxxx",
    "deepseek": "sk-xxxxxxxxxxxx",
    "qwen": "sk-xxxxxxxxxxxx"
  }
}
```

**方式三：系统环境变量**

```bash
export OPENAI_API_KEY=sk-xxxxxxxxxxxx
export DEEPSEEK_API_KEY=sk-xxxxxxxxxxxx
```

配置优先级：环境变量 > .env 文件 > config.json > 默认值。

### Q1.4：如何初始化数据库？

**答**：

```bash
# 方式一：命令行初始化
python -m backend.database init

# 方式二：自动初始化（首次启动时自动执行）
python main.py
# 服务启动时会自动检查并创建数据库

# 方式三：手动创建
python -c "
import sqlite3
conn = sqlite3.connect('data/thesisminer.db')
conn.executescript(open('backend/schema.sql').read())
conn.close()
"
```

### Q1.5：如何更新到新版本？

**答**：

```bash
# 1. 备份数据
cp data/thesisminer.db data/thesisminer.db.bak

# 2. 拉取最新代码
git pull origin main

# 3. 更新依赖
pip install -r requirements.txt --upgrade

# 4. 运行数据库迁移
python -m backend.database migrate

# 5. 重启服务
python main.py
```

### Q1.6：如何配置自定义 base_url？

**答**：如果使用 API 代理或镜像，可以配置自定义 base_url：

```bash
# .env 文件
OPENAI_BASE_URL=https://your-proxy.com/v1
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
```

或在 config.json 中：

```json
{
  "models": {
    "gpt-4.1": {
      "base_url": "https://your-proxy.com/v1",
      "api_key": "sk-xxx"
    }
  }
}
```

### Q1.7：如何配置代理？

**答**：

```bash
# .env 文件
HTTP_PROXY=http://proxy:8080
HTTPS_PROXY=http://proxy:8080
NO_PROXY=localhost,127.0.0.1
```

### Q1.8：如何禁用自动打开浏览器？

**答**：

```bash
# .env 文件
AUTO_OPEN_BROWSER=false
```

或在 config.json 中：

```json
{
  "auto_open_browser": false
}
```

### Q1.9：如何修改默认端口？

**答**：

```bash
# .env 文件
SERVER_PORT=8001
```

或启动时指定：

```bash
python main.py --port 8001
```

### Q1.10：如何查看当前版本？

**答**：

```bash
# 命令行
python -c "from backend.config import Config; print(Config.version)"

# API
curl http://localhost:8000/api/version

# Web 界面
# 页面右下角显示版本号
```

### Q1.11：如何重置所有配置？

**答**：

```bash
# 1. 备份当前配置
cp config.json config.json.bak
cp .env .env.bak

# 2. 恢复默认配置
cp config.example.json config.json
rm .env

# 3. 重新配置
cp .env.example .env
# 编辑 .env

# 4. 重启服务
python main.py
```

### Q1.12：如何配置日志级别？

**答**：

```bash
# .env 文件
LOG_LEVEL=DEBUG  # DEBUG / INFO / WARNING / ERROR / CRITICAL
```

### Q1.13：如何配置 CORS？

**答**：

```python
# 在 main.py 中
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Q1.14：如何配置 SQLite WAL 模式？

**答**：ThesisMiner 默认启用 WAL 模式。如需手动配置：

```python
# backend/database.py
conn = sqlite3.connect("data/thesisminer.db")
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=5000")
```

### Q1.15：如何解决依赖冲突？

**答**：

```bash
# 方案 1：使用 pip-tools 精确管理依赖
pip install pip-tools
pip-compile requirements.in
pip-sync requirements.txt

# 方案 2：使用 poetry
pip install poetry
poetry install

# 方案 3：创建全新的虚拟环境
python -m venv venv_new
source venv_new/bin/activate
pip install -r requirements.txt
```

---

## 2. 模型选择类

### Q2.1：ThesisMiner 支持哪些 AI 模型？

**答**：ThesisMiner v8.0 内置支持以下模型：

| 模型 | 提供商 | 适用步骤 | 特点 |
|------|--------|---------|------|
| gpt-4.1 | OpenAI | reasoner/mentor | 高质量，成本较高 |
| gpt-4.1-mini | OpenAI | inspire/search | 快速，成本低 |
| deepseek-chat-v3 | DeepSeek | reasoner/mentor | 高性价比，中文优秀 |
| deepseek-reasoner | DeepSeek | reasoner | 推理能力强 |
| qwen-plus | 阿里通义 | inspire/search | 中文优秀 |
| qwen-max | 阿里通义 | reasoner/mentor | 质量高 |
| claude-opus-4.5 | Anthropic | mentor | 评审能力强 |

### Q2.2：如何选择合适的模型？

**答**：模型选择建议：

| 场景 | 推荐模型 | 原因 |
|------|---------|------|
| 硕士论题生成 | deepseek-chat-v3 | 性价比高，中文优秀 |
| 博士论题生成 | gpt-4.1 / deepseek-reasoner | 质量高，推理强 |
| 创意激发 | gpt-4.1-mini / qwen-plus | 快速，成本低 |
| 导师评审 | gpt-4.1 / claude-opus-4.5 | 评审质量高 |
| 文献检索 | gpt-4.1-mini | 快速响应 |
| 开题报告 | deepseek-chat-v3 | 长文本生成好 |

### Q2.3：如何配置步骤路由？

**答**：步骤路由将不同的处理步骤映射到不同的模型：

```json
// config.json
{
  "model_routing": {
    "reasoner": "deepseek-reasoner",
    "mentor": "gpt-4.1",
    "inspire": "gpt-4.1-mini",
    "search": "gpt-4.1-mini",
    "report": "deepseek-chat-v3"
  }
}
```

或通过 API 配置：

```bash
curl -X PUT http://localhost:8000/api/config/routing \
  -H "Content-Type: application/json" \
  -d '{
    "reasoner": "deepseek-reasoner",
    "mentor": "gpt-4.1"
  }'
```

### Q2.4：如何添加自定义模型？

**答**：

```python
# 1. 在 config.json 中添加模型配置
{
  "models": {
    "my-custom-model": {
      "provider": "openai",
      "base_url": "https://api.my-provider.com/v1",
      "api_key": "sk-xxx",
      "model_name": "my-model-v1",
      "pricing": {
        "input": 0.001,
        "output": 0.002,
        "currency": "USD"
      },
      "max_tokens": 4096,
      "context_window": 128000
    }
  }
}

# 2. 通过 API 添加
curl -X POST http://localhost:8000/api/config/models \
  -H "Content-Type: application/json" \
  -d '{
    "id": "my-custom-model",
    "provider": "openai",
    "base_url": "https://api.my-provider.com/v1",
    "api_key": "sk-xxx",
    "model_name": "my-model-v1"
  }'
```

### Q2.5：如何进行模型 A/B 测试？

**答**：

```python
# 在 config.json 中配置 A/B 测试
{
  "ab_testing": {
    "enabled": true,
    "experiments": [
      {
        "name": "reasoner-comparison",
        "step": "reasoner",
        "variants": {
          "A": "deepseek-reasoner",
          "B": "gpt-4.1"
        },
        "ratio": 0.5
      }
    ]
  }
}
```

### Q2.6：如何配置模型降级策略？

**答**：

```json
// config.json
{
  "model_fallback": {
    "reasoner": ["deepseek-reasoner", "gpt-4.1", "deepseek-chat-v3"],
    "mentor": ["gpt-4.1", "deepseek-chat-v3", "qwen-max"],
    "inspire": ["gpt-4.1-mini", "qwen-plus", "deepseek-chat-v3"]
  }
}
```

当主模型不可用时，自动切换到备用模型。

### Q2.7：如何查看模型定价？

**答**：

```bash
# API 查询
curl http://localhost:8000/api/config/models | jq '.[].pricing'

# 或在 Web 界面
# 设置 → 模型管理 → 查看定价
```

### Q2.8：如何切换货币单位？

**答**：

```bash
# .env 文件
CURRENCY=CNY  # CNY 或 USD
```

### Q2.9：如何测试模型可用性？

**答**：

```bash
# API 测试
curl -X POST http://localhost:8000/api/config/models/test \
  -H "Content-Type: application/json" \
  -d '{"model_id": "gpt-4.1"}'
```

### Q2.10：如何配置模型超时时间？

**答**：

```json
// config.json
{
  "model_timeouts": {
    "reasoner": 120,
    "mentor": 90,
    "searcher": 5,
    "writer": 300
  }
}
```

### Q2.11：deepseek-reasoner 和 gpt-4.1 有什么区别？

**答**：

| 对比项 | deepseek-reasoner | gpt-4.1 |
|--------|------------------|---------|
| 推理能力 | 优秀（思维链） | 优秀 |
| 中文能力 | 优秀 | 良好 |
| 响应速度 | 较慢（推理过程） | 中等 |
| 成本 | 较低 | 较高 |
| 上下文窗口 | 128K | 128K |
| 适用场景 | 复杂推理 | 通用任务 |

### Q2.12：如何优化模型成本？

**答**：

1. **使用步骤路由**：将简单任务分配给低成本模型
2. **启用缓存**：利用 DeepSeek 的 Prompt 缓存
3. **控制输入长度**：使用 DST 压缩减少 Token
4. **选择合适模型**：根据任务复杂度选择模型
5. **监控用量**：通过透明账本监控成本

### Q2.13：如何查看模型调用统计？

**答**：

```bash
# API 查询
curl http://localhost:8000/api/budgets/summary?group_by=model

# Web 界面
# 预算统计 → 按模型分组
```

### Q2.14：如何配置模型并发限制？

**答**：

```json
// config.json
{
  "model_concurrency": {
    "gpt-4.1": 5,
    "deepseek-chat-v3": 10,
    "deepseek-reasoner": 3
  }
}
```

### Q2.15：如何使用本地模型？

**答**：

```json
// config.json
{
  "models": {
    "local-llama": {
      "provider": "ollama",
      "base_url": "http://localhost:11434/v1",
      "api_key": "ollama",
      "model_name": "llama3:70b",
      "pricing": {
        "input": 0,
        "output": 0,
        "currency": "USD"
      }
    }
  }
}
```

---

## 3. 会话管理类

### Q3.1：如何创建新会话？

**答**：

```bash
# API 创建
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "name": "我的论题会话",
    "degree": "master",
    "discipline": "计算机科学",
    "advisor": "张教授"
  }'

# Web 界面
# 点击左侧"新建会话"按钮
```

### Q3.2：如何切换会话？

**答**：

```
# Web 界面
# 点击左侧会话列表中的目标会话

# API 切换（通过在请求中指定 session_id）
curl http://localhost:8000/api/sessions/sess-abc123
```

### Q3.3：如何重命名会话？

**答**：

```bash
# API
curl -X PUT http://localhost:8000/api/sessions/sess-abc123 \
  -H "Content-Type: application/json" \
  -d '{"name": "新名称"}'

# Web 界面
# 双击会话名称进行编辑
```

### Q3.4：如何删除会话？

**答**：

```bash
# API
curl -X DELETE http://localhost:8000/api/sessions/sess-abc123

# Web 界面
# 右键会话 → 删除
```

### Q3.5：多会话之间会相互影响吗？

**答**：不会。每个会话有独立的上下文和 DST 状态，会话之间完全隔离。切换会话时，DST 状态会自动保存和恢复。

### Q3.6：如何导出会话历史？

**答**：

```bash
# API 导出
curl http://localhost:8000/api/sessions/sess-abc123/export?format=json \
  -o session_history.json

# 支持的格式：json, markdown, txt
```

### Q3.7：会话的上下文压缩是如何工作的？

**答**：ThesisMiner 使用 DST（Dialog State Tracking）进行上下文压缩：

1. 当历史消息超过阈值（默认 15 条）时触发压缩
2. 压缩保留最近 5 条完整消息
3. 旧消息被压缩为摘要
4. 摘要包含关键信息（论题、约束、决策等）
5. 压缩后的上下文用于后续 AI 调用

### Q3.8：如何调整上下文压缩参数？

**答**：

```json
// config.json
{
  "dst_config": {
    "max_history": 10,
    "summary_ratio": 0.3,
    "compact_threshold": 15,
    "preserve_recent": 5
  }
}
```

### Q3.9：会话数据存储在哪里？

**答**：会话数据存储在 SQLite 数据库中：

- 会话元数据：`sessions` 表
- 对话消息：`messages` 表
- DST 状态：`dst_states` 表
- 论题数据：`proposals` 表

### Q3.10：如何查看会话状态？

**答**：

```bash
# API
curl http://localhost:8000/api/sessions/sess-abc123

# 返回的 state 字段：
# - active: 活跃中
# - generating: 正在生成论题
# - completed: 已完成
# - failed: 失败
```

---

## 4. 五阶段流程类

### Q4.1：什么是五阶段闭环导航流？

**答**：五阶段闭环导航流是 ThesisMiner v8.0 的核心流程，包括：

1. **信息确权**：确认学位、学科、导师等基本信息
2. **创意生成**：基于谱系和跨域联想生成论题创意
3. **校验回退**：对创意进行约束校验，不通过则回退
4. **多粒度生成**：生成标题级、摘要级、大纲级论题
5. **深度辅助**：文献精读、实验预研、答辩模拟

### Q4.2：如何进行信息确权？

**答**：

```
# Web 界面
# 1. 创建新会话
# 2. 在对话中输入基本信息
#    "我是计算机科学专业的硕士生，导师是张教授，研究方向是人工智能"
# 3. 系统会自动提取并确认信息
# 4. 确认信息无误后进入下一阶段
```

### Q4.3：创意生成阶段是如何工作的？

**答**：创意生成阶段使用四维创意引擎：

1. **导师项目延伸**：基于导师的研究项目延伸论题
2. **同门继承**：基于同门师兄师姐的工作继续研究
3. **问题意识激发**：基于学科痛点激发论题
4. **跨域联想**：跨学科方法迁移产生创意

### Q4.4：校验回退机制是什么？

**答**：校验回退是确保论题质量的关键机制：

1. 生成创意后，自动进行约束校验
2. 校验包括：标题格式、时间可行性、文献基线、新颖性
3. 如果校验不通过，自动回退到创意生成阶段
4. 最多重试 3 次，仍不通过则返回失败

### Q4.5：多粒度生成是什么？

**答**：多粒度生成提供不同详细程度的论题：

| 粒度 | 内容 | 适用场景 |
|------|------|---------|
| 标题级 | 仅论题标题 | 快速浏览 |
| 摘要级 | 标题 + 摘要 | 初步评估 |
| 大纲级 | 标题 + 摘要 + 研究大纲 | 详细规划 |
| 全文级 | 完整开题报告 | 直接使用 |

### Q4.6：深度辅助三件套是什么？

**答**：深度辅助三件套包括：

1. **文献精读**：对关键文献进行深度解读
2. **实验预研**：提供实验设计建议和预研方案
3. **答辩模拟**：模拟开题答辩，提供问答练习

### Q4.7：如何使用文献精读？

**答**：

```
# Web 界面
# 1. 在论题详情页点击"深度辅助"
# 2. 选择"文献精读"
# 3. 输入或上传文献
# 4. 系统生成精读笔记
```

### Q4.8：如何使用实验预研？

**答**：

```
# Web 界面
# 1. 在论题详情页点击"深度辅助"
# 2. 选择"实验预研"
# 3. 系统基于论题生成实验设计建议
# 4. 包括：实验方案、数据集建议、评估指标
```

### Q4.9：如何使用答辩模拟？

**答**：

```
# Web 界面
# 1. 在论题详情页点击"深度辅助"
# 2. 选择"答辩模拟"
# 3. 系统扮演评审委员提问
# 4. 用户回答，系统给出反馈
```

### Q4.10：五阶段流程可以跳过某些阶段吗？

**答**：不可以。五阶段流程是闭环设计，每个阶段都为下一阶段提供输入。但可以在阶段内进行迭代（如校验回退）。

### Q4.11：如何查看当前处于哪个阶段？

**答**：

```bash
# API
curl http://localhost:8000/api/sessions/sess-abc123

# 返回的 orchestration_state 字段：
# - init: 初始化
# - inspiring: 创意生成
# - reasoning: 推理生成
# - validating: 校验中
# - completed: 已完成
# - failed: 失败
```

### Q4.12：如何重新生成论题？

**答**：

```bash
# API
curl -X POST http://localhost:8000/api/sessions/sess-abc123/proposals/regenerate

# Web 界面
# 论题详情页 → "重新生成"按钮
```

### Q4.13：如何修改已生成的论题？

**答**：

```bash
# API
curl -X PUT http://localhost:8000/api/proposals/prop-abc123 \
  -H "Content-Type: application/json" \
  -d '{
    "title": "修改后的标题",
    "abstract": "修改后的摘要"
  }'
```

### Q4.14：如何导出开题报告？

**答**：

```bash
# API
curl http://localhost:8000/api/proposals/prop-abc123/report?format=markdown \
  -o report.md

# 支持的格式：markdown, docx, pdf
```

### Q4.15：如何查看论题评估结果？

**答**：

```bash
# API
curl http://localhost:8000/api/proposals/prop-abc123/evaluation

# 返回评估结果，包括：
# - 新颖性评分
# - 可行性评分
# - 重复度
# - 风格质量
# - AI 痕迹
# - 综合评分
```

---

## 5. 谱系图谱类

### Q5.1：什么是学术谱系图谱？

**答**：学术谱系图谱是 ThesisMiner 的核心功能之一，以可视化方式展示学术关系网络，包括：

- 导师-学生关系
- 研究项目继承关系
- 论文引用关系
- 研究方向关联

### Q5.2：如何查看谱系图谱？

**答**：

```
# Web 界面
# 1. 点击顶部导航栏的"谱系图谱"
# 2. 图谱以 D3.js 力导向图展示
# 3. 可拖拽、缩放、过滤
```

### Q5.3：谱系图谱中有哪些节点类型？

**答**：

| 节点类型 | 颜色 | 图标 | 说明 |
|---------|------|------|------|
| 导师 | 蓝色 | 👨‍🏫 | 研究生导师 |
| 学生 | 绿色 | 🎓 | 研究生 |
| 项目 | 橙色 | 📋 | 研究项目 |
| 论文 | 紫色 | 📄 | 学术论文 |
| 方向 | 红色 | 🧭 | 研究方向 |
| 机构 | 灰色 | 🏛️ | 研究机构 |

### Q5.4：如何添加谱系节点？

**答**：

```bash
# API
curl -X POST http://localhost:8000/api/lineage/nodes \
  -H "Content-Type: application/json" \
  -d '{
    "type": "advisor",
    "name": "张教授",
    "properties": {
      "institution": "清华大学",
      "research_area": "人工智能"
    }
  }'

# Web 界面
# 图谱页面 → 右键 → "添加节点"
```

### Q5.5：如何添加谱系边？

**答**：

```bash
# API
curl -X POST http://localhost:8000/api/lineage/edges \
  -H "Content-Type: application/json" \
  -d '{
    "source": "node-advisor-001",
    "target": "node-student-001",
    "type": "advise",
    "properties": {
      "start_date": "2023-09-01"
    }
  }'
```

### Q5.6：如何搜索谱系节点？

**答**：

```bash
# API
curl "http://localhost:8000/api/lineage/search?keyword=张教授&type=advisor"

# Web 界面
# 图谱页面 → 搜索框 → 输入关键词
```

### Q5.7：如何批量删除节点？

**答**：

```bash
# API
curl -X POST http://localhost:8000/api/lineage/batch-delete \
  -H "Content-Type: application/json" \
  -d '{"node_ids": ["node-001", "node-002", "node-003"]}'

# Web 界面
# 图谱页面 → 框选节点 → 右键 → "批量删除"
```

### Q5.8：如何导出图谱？

**答**：

```bash
# API 导出
curl http://localhost:8000/api/lineage/export?format=json \
  -o lineage.json

# Web 界面导出
# 图谱页面 → "导出"按钮 → 选择格式（SVG/PNG/JSON）
```

### Q5.9：如何从论文摘要扩展图谱？

**答**：

```bash
# API
curl -X POST http://localhost:8000/api/lineage/expand \
  -H "Content-Type: application/json" \
  -d '{
    "node_id": "node-paper-001",
    "text": "论文摘要文本..."
  }'

# 系统会从摘要中抽取实体和关系，自动扩展图谱
```

### Q5.10：如何过滤图谱显示？

**答**：

```
# Web 界面
# 图谱页面 → 左侧过滤面板
# - 按节点类型过滤
# - 按关系类型过滤
# - 按时间范围过滤
```

---

## 6. 预算统计类

### Q6.1：如何查看预算使用情况？

**答**：

```bash
# API
curl http://localhost:8000/api/budgets/summary

# 返回：
# - 日成本
# - 月成本
# - 总成本
# - 按模型分组
# - 按步骤分组
```

### Q6.2：成本是如何计算的？

**答**：成本计算公式：

```
成本 = (输入 Token 数 × 输入单价) + (输出 Token 数 × 输出单价)

示例：
- 输入：1000 Token，单价 $0.001/1K Token
- 输出：500 Token，单价 $0.002/1K Token
- 成本 = (1000 × 0.001/1000) + (500 × 0.002/1000) = $0.001 + $0.001 = $0.002
```

### Q6.3：如何查看缓存命中情况？

**答**：

```bash
# API
curl http://localhost:8000/api/cache/stats

# 返回：
# - 总请求数
# - 缓存命中数
# - 缓存命中率
# - 节省成本
```

### Q6.4：如何导出预算账本？

**答**：

```bash
# API
curl http://localhost:8000/api/budgets/export?format=csv \
  -o budget.csv

# 支持的格式：csv, json, excel
```

### Q6.5：如何设置预算告警？

**答**：

```json
// config.json
{
  "budget_alerts": {
    "daily_limit": 10.0,
    "session_limit": 2.0,
    "alert_threshold": 0.8,
    "alert_email": "admin@example.com"
  }
}
```

当使用量达到阈值的 80% 时发送告警。

### Q6.6：如何查看单次调用的成本明细？

**答**：

```bash
# API
curl http://localhost:8000/api/budgets/ledger?session_id=sess-abc123

# 返回每次 AI 调用的详细记录：
# - 调用时间
# - 模型名称
# - 输入/输出 Token 数
# - 是否缓存命中
# - 成本
```

### Q6.7：缓存命中如何影响成本？

**答**：缓存命中时，输入 Token 的成本大幅降低：

```
正常成本：输入 Token × 输入单价
缓存命中：输入 Token × 输入单价 × 0.1（降价 90%）

示例（DeepSeek 缓存）：
- 正常：1000 Token × $0.001/1K = $0.001
- 缓存：1000 Token × $0.0001/1K = $0.0001
- 节省：90%
```

### Q6.8：如何查看按模型分组的成本？

**答**：

```bash
# API
curl http://localhost:8000/api/budgets/summary?group_by=model

# Web 界面
# 预算统计 → 按模型分组
```

### Q6.9：如何查看按步骤分组的成本？

**答**：

```bash
# API
curl http://localhost:8000/api/budgets/summary?group_by=step

# 步骤包括：reasoner, mentor, inspire, search, report
```

### Q6.10：如何重置预算统计？

**答**：

```bash
# API（需要管理员权限）
curl -X POST http://localhost:8000/api/budgets/reset \
  -H "Authorization: Bearer admin-token"
```

---

## 7. 开发贡献类

### Q7.1：如何参与 ThesisMiner 开发？

**答**：

1. Fork 仓库到个人 GitHub
2. 克隆 Fork 仓库到本地
3. 创建功能分支：`git checkout -b feature/your-feature`
4. 编写代码并测试
5. 提交 PR 到主仓库

### Q7.2：如何设置开发环境？

**答**：

```bash
# 1. 克隆仓库
git clone https://github.com/your-fork/ThesisMiner.git
cd ThesisMiner

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate

# 3. 安装开发依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 4. 安装 pre-commit hooks
pre-commit install

# 5. 运行测试
pytest
```

### Q7.3：如何运行测试？

**答**：

```bash
# 运行所有测试
pytest

# 运行单元测试
pytest tests/unit/

# 运行集成测试
pytest tests/integration/

# 运行特定测试
pytest tests/unit/test_session_manager.py

# 生成覆盖率报告
pytest --cov=backend --cov-report=html
```

### Q7.4：如何提交代码？

**答**：

```bash
# 1. 检查代码风格
black --check backend/
ruff check backend/
mypy backend/

# 2. 运行测试
pytest

# 3. 提交代码（遵循 Conventional Commits）
git add .
git commit -m "feat(agents): 添加自定义 Agent 功能"

# 4. 推送分支
git push origin feature/your-feature

# 5. 创建 PR
```

### Q7.5：如何编写自定义 Agent？

**答**：

```python
from backend.agents.base_agent import BaseAgent, AgentResult

class MyCustomAgent(BaseAgent):
    """自定义 Agent 示例"""

    def __init__(self):
        super().__init__(
            agent_id="my-custom-agent",
            agent_name="自定义 Agent",
        )

    async def run(self, context: dict) -> AgentResult:
        # 实现 Agent 逻辑
        result = await self.call_model(context["prompt"])
        return AgentResult(
            success=True,
            data=result,
            metadata={"agent": self.agent_id},
        )

# 注册 Agent
from backend.agents.registry import AGENT_REGISTRY
AGENT_REGISTRY["my-custom-agent"] = MyCustomAgent()
```

### Q7.6：如何添加自定义约束？

**答**：

```python
from backend.constraints.base import BaseConstraint, ConstraintResult

class TitleLengthConstraint(BaseConstraint):
    """标题长度约束"""

    def check(self, proposal: dict) -> ConstraintResult:
        title = proposal.get("title", "")
        if len(title) > 20:
            return ConstraintResult(
                passed=False,
                message=f"标题过长：{len(title)} 字（最大 20 字）",
                suggestion="请缩减标题长度",
            )
        return ConstraintResult(passed=True)

# 注册约束
from backend.constraints.registry import CONSTRAINT_REGISTRY
CONSTRAINT_REGISTRY["title_length"] = TitleLengthConstraint()
```

### Q7.7：如何更新文档？

**答**：

1. 文档位于 `docs/` 目录
2. 使用 Markdown 格式
3. 中文编写（代码和术语除外）
4. 提交 PR 时在描述中说明文档变更

### Q7.8：如何报告 Bug？

**答**：

1. 在 GitHub Issues 中搜索是否已有相同问题
2. 如果没有，创建新 Issue
3. 包含：Bug 描述、复现步骤、期望行为、实际行为、环境信息、日志

### Q7.9：如何请求新功能？

**答**：

1. 在 GitHub Issues 中创建 Feature Request
2. 描述功能需求和使用场景
3. 等待社区讨论和维护者审核

### Q7.10：如何参与代码审查？

**答**：

1. 查看待审查的 PR
2. 检查代码质量、测试覆盖、文档完整性
3. 提出建设性意见
4. 批准或请求修改

---

## 8. 部署运维类

### Q8.1：如何使用 Docker 部署？

**答**：

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "main.py"]
```

```bash
# 构建镜像
docker build -t thesisminer:latest .

# 运行容器
docker run -d \
  --name thesisminer \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/.env:/app/.env \
  thesisminer:latest
```

### Q8.2：如何使用 Docker Compose 部署？

**答**：

```yaml
# docker-compose.yml
version: '3.8'

services:
  thesisminer:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./.env:/app/.env
    restart: unless-stopped
    environment:
      - PYTHONUNBUFFERED=1
```

```bash
docker-compose up -d
```

### Q8.3：如何配置 Nginx 反向代理？

**答**：

```nginx
# /etc/nginx/conf.d/thesisminer.conf
server {
    listen 80;
    server_name thesisminer.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # SSE 支持
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }
}
```

### Q8.4：如何配置 HTTPS？

**答**：

```bash
# 使用 Let's Encrypt 获取免费 SSL 证书
sudo certbot --nginx -d thesisminer.example.com
```

```nginx
server {
    listen 443 ssl;
    server_name thesisminer.example.com;

    ssl_certificate /etc/letsencrypt/live/thesisminer.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/thesisminer.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
    }
}
```

### Q8.5：如何配置 systemd 服务？

**答**：

```ini
# /etc/systemd/system/thesisminer.service
[Unit]
Description=ThesisMiner Service
After=network.target

[Service]
Type=simple
User=thesisminer
WorkingDirectory=/opt/thesisminer
EnvironmentFile=/opt/thesisminer/.env
ExecStart=/opt/thesisminer/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable thesisminer
sudo systemctl start thesisminer
sudo systemctl status thesisminer
```

### Q8.6：如何备份数据？

**答**：

```bash
# 方案 1：手动备份
cp data/thesisminer.db data/thesisminer.db.bak.$(date +%Y%m%d)

# 方案 2：定时备份脚本
#!/bin/bash
BACKUP_DIR="/backups/thesisminer"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR
cp /opt/thesisminer/data/thesisminer.db $BACKUP_DIR/thesisminer_$DATE.db
# 保留最近 30 天的备份
find $BACKUP_DIR -name "*.db" -mtime +30 -delete

# 方案 3：使用 SQLite 在线备份
sqlite3 data/thesisminer.db ".backup data/thesisminer_backup.db"
```

### Q8.7：如何恢复数据？

**答**：

```bash
# 1. 停止服务
sudo systemctl stop thesisminer

# 2. 恢复备份
cp /backups/thesisminer/thesisminer_20260619.db data/thesisminer.db

# 3. 重启服务
sudo systemctl start thesisminer
```

### Q8.8：如何监控服务状态？

**答**：

```bash
# 方案 1：systemd 状态
sudo systemctl status thesisminer

# 方案 2：健康检查 API
curl http://localhost:8000/api/health

# 方案 3：Prometheus 监控
# 访问 /metrics 端点获取指标
curl http://localhost:8000/metrics
```

### Q8.9：如何查看日志？

**答**：

```bash
# 方案 1：应用日志
tail -f logs/thesisminer.log

# 方案 2：systemd 日志
journalctl -u thesisminer -f

# 方案 3：Docker 日志
docker logs -f thesisminer
```

### Q8.10：如何升级部署？

**答**：

```bash
# 1. 备份数据
cp data/thesisminer.db data/thesisminer.db.bak

# 2. 拉取最新代码
git pull origin main

# 3. 更新依赖
pip install -r requirements.txt --upgrade

# 4. 运行迁移
python -m backend.database migrate

# 5. 重启服务
sudo systemctl restart thesisminer
```

---

## 附录

### A. 快速参考

| 操作 | 命令/API |
|------|---------|
| 启动服务 | `python main.py` |
| 健康检查 | `GET /api/health` |
| 创建会话 | `POST /api/sessions` |
| 生成论题 | `POST /api/sessions/{id}/proposals` |
| 查看谱系 | `GET /api/lineage/nodes` |
| 预算统计 | `GET /api/budgets/summary` |
| 缓存统计 | `GET /api/cache/stats` |
| 模型列表 | `GET /api/config/models` |

### B. 相关文档

- [错误码参考](./api/error_codes.md)
- [限流配额](./api/rate_limiting.md)
- [故障排查指南](./development/troubleshooting.md)
- [代码风格规范](./development/code_style.md)
- [入门教程](./tutorials/getting_started.md)
- [高级特性教程](./tutorials/advanced_features.md)
- [管理员指南](./tutorials/admin_guide.md)

### C. 获取帮助

- **GitHub Issues**：提交问题或 Bug 报告
- **文档**：查阅官方文档
- **社区**：加入用户社区讨论

---

> **文档结束**  
> 本文档包含 ThesisMiner v8.0 的 80+ 常见问题解答。如需了解更多信息，请参阅相关文档或提交 Issue。