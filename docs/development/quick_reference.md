# ThesisMiner v8.0 开发者快速参考

> 开发者日常使用的快速参考卡片。

## 常用命令

### 开发

```bash
# 启动开发服务器
python main.py

# 热重载
uvicorn main:app --reload --port 8000

# 多 worker
uvicorn main:app --workers 4
```

### 测试

```bash
# 全部测试
pytest

# 单元测试
pytest tests/unit/

# 集成测试
pytest tests/integration/

# E2E 测试
pytest tests/e2e/

# 覆盖率
pytest --cov=backend --cov-report=html

# 特定测试
pytest tests/unit/test_orchestrator.py -v

# 并行
pytest -n auto
```

### 代码质量

```bash
# 格式化
black backend/
isort backend/

# Lint
flake8 backend/
pylint backend/

# 类型检查
mypy backend/

# 安全扫描
bandit -r backend/
pip-audit
```

### 数据库

```bash
# 初始化
python -c "from backend.database import init_database; init_database()"

# 迁移
python -c "from backend.database import migrate_db; migrate_db()"

# 备份
sqlite3 data/thesisminer.db ".backup data/backup.db"

# 优化
sqlite3 data/thesisminer.db "VACUUM; ANALYZE; PRAGMA optimize;"

# 完整性检查
sqlite3 data/thesisminer.db "PRAGMA integrity_check;"
```

### Git

```bash
# 状态
git status

# 差异
git diff

# 提交
git add .
git commit -m "feat: 描述"

# 推送
git push origin main

# 拉取
git pull origin main
```

## API 端点速查

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/health | 健康检查 |
| GET | /api/agents | Agent 列表 |
| GET | /api/models | 模型列表 |
| GET | /api/cache-stats | 缓存统计 |
| GET/POST | /api/sessions | 会话管理 |
| GET/POST | /api/sessions/{sid}/conversations | 对话管理 |
| GET/POST | /api/conversations/{cid}/messages | 消息管理 |
| GET | /api/messages/{mid}/citations | 引用查询 |
| GET | /api/lineage | 谱系数据 |

## 模型路由

| Agent | 默认模型 |
|-------|---------|
| orchestrator | claude-sonnet-4.5 |
| reasoner | deepseek-r2 |
| mentor | gpt-4.1 |
| inspire | qwen3-max |
| report | claude-opus-4.5 |
| search | deepseek-v3.2 |

## 五阶段流程

```
信息确权 → 创意 → 校验 → 生成 → 深度辅助
  ↓         ↓       ↓       ↓        ↓
联网检索  四维创意  评分≥60  多粒度   三件套
等待确认  候选论题  通过门禁  去AI痕   精读/预研/答辩
```

## 目录结构

```
backend/
├── agents/         # 6 个 Agent
├── sessions/       # 会话管理
├── constraints/    # 约束工程
├── orchestration/  # 编排系统
├── ai/             # AI 代理层
├── analytics/      # 分析监控
├── ml/             # 机器学习
├── export/         # 导出
├── knowledge/      # 知识库
├── validation/     # 验证
├── routing/        # 路由
├── integrity/      # 学术诚信
├── optimization/   # 优化
├── nlp/            # NLP
├── monitoring/     # 监控
├── planning/       # 规划
├── reasoning/      # 推理
└── utils/          # 工具
```

## 关键配置

```python
# backend/config.py
APP_VERSION = "8.0.0"
DEFAULT_MODEL = "deepseek-v3.2"
DB_PATH = "data/thesisminer.db"
CACHE_TTL = 3600
RATE_LIMIT_DEFAULT = 60
```

## 性能指标

| 指标 | 目标 |
|------|------|
| API P95 | < 200ms |
| LLM 首 Token | < 2s |
| 缓存命中率 | ≥ 95% |
| 谱系渲染 | < 3s |
| 并发会话 | ≥ 100 |
| 内存 | < 2GB |

## 错误码

| 码 | 含义 |
|----|------|
| TM_1001 | 验证错误 |
| TM_2001 | 认证错误 |
| TM_3001 | 未找到 |
| TM_4001 | 限流 |
| TM_5001 | LLM 错误 |
| TM_6001 | 数据库错误 |
| TM_7001 | Agent 错误 |
| TM_8001 | 约束错误 |

## 联系方式

- GitHub: https://github.com/tree1104/ThesisMiner
- Issues: https://github.com/tree1104/ThesisMiner/issues
