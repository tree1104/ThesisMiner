# ThesisMiner v8.0 配置参考文档

> **版本**：v8.0.0
> **最后更新**：2026-06-20
> **适用范围**：`backend/config.py`、`config/`、`.env`
> **文档状态**：正式发布（Stable）

---

## 目录

- [1. 文档概述](#1-文档概述)
- [2. 配置层次](#2-配置层次)
- [3. 环境变量](#3-环境变量)
- [4. config.json](#4-configjson)
- [5. YAML 配置文件](#5-yaml-配置文件)
- [6. 模型注册表](#6-模型注册表)
- [7. 数据库配置](#7-数据库配置)
- [8. 缓存配置](#8-缓存配置)
- [9. 日志配置](#9-日志配置)
- [10. 安全配置](#10-安全配置)
- [11. 限流配置](#11-限流配置)
- [12. 会话配置](#12-会话配置)
- [13. 编排配置](#13-编排配置)
- [14. 流式配置](#14-流式配置)
- [15. 附录](#15-附录)

---

## 1. 文档概述

### 1.1 文档目的

本文档是 ThesisMiner v8.0 配置系统的完整参考手册，涵盖：

- 配置层次与优先级
- 环境变量
- config.json 配置
- YAML 配置文件
- 模型注册表
- 各模块配置详解

### 1.2 面向读者

- **运维工程师**：负责部署和配置系统
- **后端开发者**：需要修改配置项
- **架构师**：需要理解配置体系
- **二次开发者**：基于 ThesisMiner 进行二次开发

### 1.3 配置体系概览

```
┌─────────────────────────────────────────────────────────────────┐
│                    配置层次（优先级从高到低）                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. 环境变量 (.env)                  ← 最高优先级               │
│     ↓                                                           │
│  2. data/config.json                 ← 运行时配置               │
│     ↓                                                           │
│  3. config/*.yaml                    ← YAML 配置文件            │
│     ↓                                                           │
│  4. backend/config.py 代码默认值      ← 最低优先级               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.4 术语表

| 术语 | 英文 | 含义 |
|------|------|------|
| 配置层次 | Config Hierarchy | 配置的优先级顺序 |
| 环境变量 | Environment Variable | 操作系统级配置 |
| 运行时配置 | Runtime Config | 可动态修改的配置 |
| 静态配置 | Static Config | 启动时加载的配置 |
| 模型注册表 | Model Registry | 模型配置列表 |

---

## 2. 配置层次

### 2.1 优先级规则

ThesisMiner v8.0 的配置优先级（从高到低）：

```
1. 环境变量 (最高)
   ↓ 覆盖
2. data/config.json (运行时配置)
   ↓ 覆盖
3. config/*.yaml (YAML 配置)
   ↓ 覆盖
4. 代码默认值 (最低)
```

### 2.2 配置加载流程

```python
# backend/config.py
from typing import Optional
from pydantic import BaseModel
import os
import json
import yaml

class Settings(BaseModel):
    """系统配置"""
    
    # 基础配置
    app_name: str = "ThesisMiner"
    version: str = "8.0.0"
    debug: bool = False
    
    # AI 配置
    ai_model: str = "gpt-4.1-mini"
    ai_api_key: str = ""
    ai_base_url: str = "https://api.openai.com/v1"
    
    # 模型列表
    models: list = []
    step_models: dict = {}
    
    # 数据库配置
    database_url: str = "sqlite:///data/thesis_miner.db"
    
    # ... 更多配置

def get_settings() -> Settings:
    """获取配置（按优先级合并）"""
    # 1. 代码默认值
    settings = Settings()
    
    # 2. 加载 YAML 配置
    settings = _load_yaml_config(settings)
    
    # 3. 加载 config.json
    settings = _load_json_config(settings)
    
    # 4. 加载环境变量（覆盖）
    settings = _load_env_config(settings)
    
    return settings

def _load_yaml_config(settings: Settings) -> Settings:
    """加载 YAML 配置"""
    yaml_files = [
        "config/system.yaml",
        "config/models.yaml",
        "config/agents/orchestrator.yaml",
        "config/constraints/hard_rules.yaml"
    ]
    
    for file_path in yaml_files:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                # 合并配置
                settings = _merge_config(settings, config)
    
    return settings

def _load_json_config(settings: Settings) -> Settings:
    """加载 config.json"""
    config_path = "data/config.json"
    
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            settings = _merge_config(settings, config)
    
    return settings

def _load_env_config(settings: Settings) -> Settings:
    """加载环境变量"""
    # 环境变量映射
    env_mapping = {
        "DEBUG": "debug",
        "AI_MODEL": "ai_model",
        "AI_API_KEY": "ai_api_key",
        "AI_BASE_URL": "ai_base_url",
        "DATABASE_URL": "database_url"
    }
    
    for env_key, config_key in env_mapping.items():
        env_value = os.getenv(env_key)
        if env_value is not None:
            # 类型转换
            current_value = getattr(settings, config_key)
            if isinstance(current_value, bool):
                env_value = env_value.lower() in ("true", "1", "yes")
            elif isinstance(current_value, int):
                env_value = int(env_value)
            elif isinstance(current_value, float):
                env_value = float(env_value)
            
            setattr(settings, config_key, env_value)
    
    return settings
```

### 2.3 配置文件结构

```
ThesisMiner/
├── .env                          # 环境变量
├── data/
│   └── config.json               # 运行时配置
├── config/
│   ├── system.yaml               # 系统配置
│   ├── models.yaml               # 模型配置
│   ├── agents/
│   │   ├── orchestrator.yaml     # Orchestrator 配置
│   │   ├── searcher.yaml         # Searcher 配置
│   │   ├── reasoner.yaml         # Reasoner 配置
│   │   ├── critic.yaml           # Critic 配置
│   │   ├── mentor.yaml           # Mentor 配置
│   │   └── writer.yaml           # Writer 配置
│   └── constraints/
│       ├── hard_rules.yaml       # 硬约束配置
│       ├── novelty_weights.yaml  # 新颖性权重
│       └── style_normalizer_rules.yaml  # 样式规范
└── backend/
    └── config.py                 # 配置代码
```

---

## 3. 环境变量

### 3.1 基础环境变量

```bash
# .env 文件

# === 基础配置 ===
APP_NAME=ThesisMiner
VERSION=8.0.0
DEBUG=false
ENVIRONMENT=production  # development / staging / production

# === AI 配置 ===
AI_MODEL=gpt-4.1-mini
AI_API_KEY=sk-xxxxxxxxxxxxxxxx
AI_BASE_URL=https://api.openai.com/v1

# === 数据库配置 ===
DATABASE_URL=sqlite:///data/thesis_miner.db
# DATABASE_URL=postgresql://user:pass@localhost:5432/thesis_miner

# === 日志配置 ===
LOG_LEVEL=INFO
LOG_FILE=logs/thesis_miner.log
LOG_MAX_SIZE=10485760  # 10MB
LOG_BACKUP_COUNT=5

# === 缓存配置 ===
CACHE_ENABLED=true
CACHE_TTL=3600

# === 安全配置 ===
SECRET_KEY=your-secret-key
AUTH_ENABLED=false
```

### 3.2 模型 API Key

```bash
# === OpenAI ===
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx
OPENAI_BASE_URL=https://api.openai.com/v1

# === DeepSeek ===
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# === Anthropic ===
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
ANTHROPIC_BASE_URL=https://api.anthropic.com

# === 通义千问 ===
QWEN_API_KEY=sk-xxxxxxxxxxxxxxxx
QWEN_BASE_URL=https://dashscope.aliyuncs.com/api/v1

# === Google Gemini ===
GEMINI_API_KEY=AIzaSyxxxxxxxxxxxxxxxx
GEMINI_BASE_URL=https://generativelanguage.googleapis.com

# === 智谱 GLM ===
GLM_API_KEY=xxxxxxxxxxxxxxxx
GLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4

# === 字节豆包 ===
DOUBAO_API_KEY=xxxxxxxxxxxxxxxx
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
```

### 3.3 搜索 API

```bash
# === arXiv ===
ARXIV_API_URL=http://export.arxiv.org/api/query
ARXIV_MAX_RESULTS=20

# === Semantic Scholar ===
S2_API_URL=https://api.semanticscholar.org/graph/v1/paper/search
S2_API_KEY=  # 可选
S2_MAX_RESULTS=20
```

### 3.4 环境变量完整列表

| 变量名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| APP_NAME | string | ThesisMiner | 应用名称 |
| VERSION | string | 8.0.0 | 版本号 |
| DEBUG | bool | false | 调试模式 |
| ENVIRONMENT | string | production | 环境类型 |
| AI_MODEL | string | gpt-4.1-mini | 默认模型 |
| AI_API_KEY | string | - | AI API Key |
| AI_BASE_URL | string | - | AI API 地址 |
| DATABASE_URL | string | sqlite:///data/thesis_miner.db | 数据库 URL |
| LOG_LEVEL | string | INFO | 日志级别 |
| LOG_FILE | string | logs/thesis_miner.log | 日志文件 |
| CACHE_ENABLED | bool | true | 缓存启用 |
| CACHE_TTL | int | 3600 | 缓存 TTL |
| SECRET_KEY | string | - | 密钥 |
| AUTH_ENABLED | bool | false | 认证启用 |

---

## 4. config.json

### 4.1 文件位置

```
data/config.json
```

### 4.2 完整配置示例

```json
{
  "app": {
    "name": "ThesisMiner",
    "version": "8.0.0",
    "debug": false
  },
  "ai": {
    "model": "gpt-4.1-mini",
    "api_key": "sk-xxxxxxxxxxxxxxxx",
    "base_url": "https://api.openai.com/v1"
  },
  "models": [
    {
      "id": "gpt-4.1-mini",
      "name": "GPT-4.1 Mini",
      "provider": "openai",
      "enabled": true,
      "api_key": "sk-xxxxxxxxxxxxxxxx",
      "base_url": "https://api.openai.com/v1",
      "max_tokens": 128000,
      "temperature": 0.3,
      "capabilities": ["streaming", "function_calling"],
      "pricing": {
        "input": 0.15,
        "output": 0.6
      }
    },
    {
      "id": "deepseek-v3.2",
      "name": "DeepSeek V3.2",
      "provider": "deepseek",
      "enabled": true,
      "api_key": "sk-xxxxxxxxxxxxxxxx",
      "base_url": "https://api.deepseek.com/v1",
      "max_tokens": 64000,
      "temperature": 0.3,
      "capabilities": ["streaming", "prompt_caching"],
      "pricing": {
        "input": 0.14,
        "output": 0.28
      }
    }
  ],
  "step_models": {
    "orchestrator": {
      "confirm": "claude-sonnet-4.5",
      "compress": "gpt-4.1-mini"
    },
    "searcher": {
      "search": "deepseek-v3.2",
      "novelty_check": "deepseek-v3.2"
    },
    "reasoner": {
      "creativity": "deepseek-r2"
    },
    "critic": {
      "evaluate": "deepseek-r2",
      "arbitrate": "claude-opus-4.5"
    },
    "mentor": {
      "review": "gpt-4.1"
    },
    "writer": {
      "generate_title": "claude-opus-4.5",
      "generate_full": "claude-opus-4.5"
    }
  },
  "database": {
    "url": "sqlite:///data/thesis_miner.db",
    "pool_size": 10,
    "max_overflow": 20
  },
  "cache": {
    "enabled": true,
    "ttl": 3600
  }
}
```

### 4.3 配置操作 API

```python
# backend/config.py
def save_config(config: dict) -> None:
    """保存配置到 config.json"""
    config_path = "data/config.json"
    
    # 确保目录存在
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def get_model_config(model_id: str) -> dict:
    """获取指定模型的配置"""
    settings = get_settings()
    
    for model in settings.models:
        if model.id == model_id:
            return model.dict()
    
    return {}

def get_step_model(agent_id: str, purpose: str) -> str:
    """获取指定 Agent 指定用途的模型"""
    settings = get_settings()
    
    # 优先级 1: step_models 配置
    step_models = settings.step_models or {}
    agent_step = step_models.get(agent_id, {})
    if purpose in agent_step:
        return agent_step[purpose]
    
    # 优先级 2: models[0].id
    if settings.models:
        return settings.models[0].id
    
    # 优先级 3: ai_model
    return settings.ai_model or "gpt-4.1-mini"
```

---

## 5. YAML 配置文件

### 5.1 system.yaml

```yaml
# config/system.yaml
app:
  name: ThesisMiner
  version: 8.0.0
  debug: false
  environment: production

database:
  type: sqlite
  url: sqlite:///data/thesis_miner.db
  pool_size: 10
  max_overflow: 20
  echo: false  # SQL 日志
  
  # SQLite 特殊配置
  sqlite:
    journal_mode: WAL          # WAL 模式
    synchronous: NORMAL        # 同步模式
    cache_size: -64000         # 缓存大小（KB，负数表示字节）
    foreign_keys: true         # 外键约束
    busy_timeout: 5000         # 忙等待超时（毫秒）

cache:
  enabled: true
  type: memory                 # memory / redis
  ttl: 3600                    # 默认 TTL（秒）
  max_size: 1000               # 最大缓存条目
  
  # Prompt 缓存
  prompt_cache:
    enabled: true
    target_hit_rate: 0.95      # 目标命中率
    prefix_version: v8.0.1     # 前缀版本
    warmup_on_session_create: true

logging:
  level: INFO                  # DEBUG / INFO / WARNING / ERROR
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: logs/thesis_miner.log
  max_size: 10485760           # 10MB
  backup_count: 5
  
  # 按模块配置
  loggers:
    backend.agents: INFO
    backend.ai: INFO
    backend.routes: INFO
    backend.constraints: INFO

security:
  auth_enabled: false
  token_header: Authorization
  token_prefix: Bearer
  token_expiry: 3600
  
  # CORS
  cors:
    enabled: true
    allow_origins:
      - "http://localhost:3000"
    allow_methods: ["GET", "POST", "PUT", "PATCH", "DELETE"]
    allow_headers: ["*"]
    allow_credentials: true

rate_limiting:
  enabled: true
  strategy: token_bucket
  default_limit: 60            # 60 请求/分钟
  burst_limit: 10              # 突发 10 请求
  
  endpoints:
    /api/sessions:
      limit: 30
      burst: 5
    /api/proposals/generate:
      limit: 10
      burst: 2

session:
  timeout: 3600                # 会话超时（秒）
  max_sessions_per_user: 10    # 每用户最大会话数
  cleanup_interval: 300        # 清理间隔（秒）

orchestration:
  max_concurrent_sessions: 100  # 最大并发会话
  stage_timeout: 120            # 阶段超时（秒）
  retry:
    max_attempts: 3
    base_delay: 2.0
    max_delay: 30.0
    backoff: exponential

streaming:
  sse:
    enabled: true
    heartbeat_interval: 30     # 心跳间隔（秒）
    retry_interval: 3          # 重连间隔（秒）
  
  websocket:
    enabled: true
    heartbeat_interval: 30
    timeout: 90                # 超时（秒）
```

### 5.2 models.yaml

```yaml
# config/models.yaml
models:
  - id: gpt-4.1-mini
    name: GPT-4.1 Mini
    provider: openai
    enabled: true
    api_key: ${OPENAI_API_KEY}
    base_url: https://api.openai.com/v1
    max_tokens: 128000
    temperature: 0.3
    capabilities:
      - streaming
      - function_calling
      - json_mode
    pricing:
      input: 0.15              # 美元/1K token
      output: 0.6
    rate_limit:
      requests_per_minute: 500
      tokens_per_minute: 150000
    fallback:
      - gpt-4.1
      - deepseek-v3.2
  
  - id: gpt-4.1
    name: GPT-4.1
    provider: openai
    enabled: true
    api_key: ${OPENAI_API_KEY}
    base_url: https://api.openai.com/v1
    max_tokens: 128000
    temperature: 0.3
    capabilities:
      - streaming
      - function_calling
      - json_mode
      - vision
    pricing:
      input: 2.5
      output: 10
    rate_limit:
      requests_per_minute: 500
      tokens_per_minute: 150000
  
  - id: deepseek-v3.2
    name: DeepSeek V3.2
    provider: deepseek
    enabled: true
    api_key: ${DEEPSEEK_API_KEY}
    base_url: https://api.deepseek.com/v1
    max_tokens: 64000
    temperature: 0.3
    capabilities:
      - streaming
      - prompt_caching
      - json_mode
    pricing:
      input: 0.14
      output: 0.28
    rate_limit:
      requests_per_minute: 60
      tokens_per_minute: 60000
    cache:
      enabled: true
      min_tokens: 1024
      max_tokens: 16384
  
  - id: deepseek-r2
    name: DeepSeek R2 (Reasoner)
    provider: deepseek
    enabled: true
    api_key: ${DEEPSEEK_API_KEY}
    base_url: https://api.deepseek.com/v1
    max_tokens: 64000
    temperature: 0.8
    capabilities:
      - streaming
      - thinking
      - prompt_caching
    pricing:
      input: 0.55
      output: 2.19
    rate_limit:
      requests_per_minute: 60
      tokens_per_minute: 60000
  
  - id: claude-sonnet-4.5
    name: Claude Sonnet 4.5
    provider: anthropic
    enabled: true
    api_key: ${ANTHROPIC_API_KEY}
    base_url: https://api.anthropic.com
    max_tokens: 200000
    temperature: 0.3
    capabilities:
      - streaming
      - thinking
      - vision
    pricing:
      input: 3
      output: 15
    rate_limit:
      requests_per_minute: 50
      tokens_per_minute: 80000
  
  - id: claude-opus-4.5
    name: Claude Opus 4.5
    provider: anthropic
    enabled: true
    api_key: ${ANTHROPIC_API_KEY}
    base_url: https://api.anthropic.com
    max_tokens: 200000
    temperature: 0.6
    capabilities:
      - streaming
      - thinking
      - vision
    pricing:
      input: 15
      output: 75
    rate_limit:
      requests_per_minute: 50
      tokens_per_minute: 80000
  
  - id: qwen3-max
    name: Qwen3 Max
    provider: qwen
    enabled: true
    api_key: ${QWEN_API_KEY}
    base_url: https://dashscope.aliyuncs.com/api/v1
    max_tokens: 32000
    temperature: 0.3
    capabilities:
      - streaming
      - function_calling
    pricing:
      input: 1.2
      output: 3.6
    rate_limit:
      requests_per_minute: 60
      tokens_per_minute: 60000
  
  - id: gemini-2.5-pro
    name: Gemini 2.5 Pro
    provider: google
    enabled: true
    api_key: ${GEMINI_API_KEY}
    base_url: https://generativelanguage.googleapis.com
    max_tokens: 1000000
    temperature: 0.3
    capabilities:
      - streaming
      - vision
      - function_calling
    pricing:
      input: 1.25
      output: 5
  
  - id: glm-4.6
    name: GLM-4.6
    provider: zhipu
    enabled: true
    api_key: ${GLM_API_KEY}
    base_url: https://open.bigmodel.cn/api/paas/v4
    max_tokens: 128000
    temperature: 0.3
    capabilities:
      - streaming
      - function_calling
    pricing:
      input: 0.5
      output: 0.5
  
  - id: doubao-1.5-pro
    name: Doubao 1.5 Pro
    provider: bytedance
    enabled: true
    api_key: ${DOUBAO_API_KEY}
    base_url: https://ark.cn-beijing.volces.com/api/v3
    max_tokens: 256000
    temperature: 0.3
    capabilities:
      - streaming
      - function_calling
    pricing:
      input: 0.8
      output: 2

# 模型路由配置
routing:
  default_model: gpt-4.1-mini
  
  agent_models:
    orchestrator: claude-sonnet-4.5
    searcher: deepseek-v3.2
    reasoner: deepseek-r2
    critic: deepseek-r2
    mentor: gpt-4.1
    writer: claude-opus-4.5
  
  step_models:
    orchestrator:
      confirm: claude-sonnet-4.5
      compress: gpt-4.1-mini
    searcher:
      search: deepseek-v3.2
      novelty_check: deepseek-v3.2
    reasoner:
      creativity: deepseek-r2
    critic:
      evaluate: deepseek-r2
      arbitrate: claude-opus-4.5
    mentor:
      review: gpt-4.1
    writer:
      generate_title: claude-opus-4.5
      generate_full: claude-opus-4.5
  
  fallback_models:
    - gpt-4.1-mini
    - deepseek-v3.2
    - qwen3-max
```

### 5.3 Agent 配置文件

#### 5.3.1 orchestrator.yaml

```yaml
# config/agents/orchestrator.yaml
agent_id: orchestrator
name: Orchestrator
model: claude-sonnet-4.5
temperature: 0.3
max_tokens: 4096

stages:
  info_confirm:
    require_user_confirm: true
    min_info_fields:
      - discipline
      - degree
      - direction
  
  creativity:
    min_candidates: 3
    max_candidates: 5
    require_all_dimensions: true
  
  validation:
    min_score: 60
    max_retries: 2
    fallback: mark_warning
  
  generation:
    report_generated: true
    style_normalizer_applied: true
    fallback: template_mode
  
  deep_assist:
    require_menu_render: true
    require_user_end: true
    loop: true

retry:
  max_attempts: 3
  base_delay: 2.0
  max_delay: 30.0
  backoff: exponential
  retryable_errors:
    - AGENT_TIMEOUT
    - AGENT_RATE_LIMIT
    - AGENT_JSON_PARSE
    - MODEL_UNAVAILABLE

fallback:
  strategy: fallback_proposal
  confidence_score: 0.4
  cascade:
    - searcher: mock_searcher
    - reasoner: fallback_proposal
    - critic: mark_warning
    - mentor: skip_mentor
    - writer: template_mode

context:
  max_history_rounds: 10
  recent_history_rounds: 3
  compression_threshold: 5
  compression_strategy: summary

cache:
  enabled: true
  cache_system_prompt: true
  cache_user_info: true
```

#### 5.3.2 searcher.yaml

```yaml
# config/agents/searcher.yaml
agent_id: searcher
name: Searcher
model: deepseek-v3.2
temperature: 0.3
max_tokens: 2048

search:
  mode: auto  # mock / real / auto
  top_k: 10
  timeout: 30
  sources:
    - arxiv
    - semantic_scholar

arxiv:
  api_url: http://export.arxiv.org/api/query
  max_results: 20
  sort_by: relevance
  sort_order: descending

semantic_scholar:
  api_url: https://api.semanticscholar.org/graph/v1/paper/search
  max_results: 20
  fields:
    - title
    - authors
    - year
    - abstract
    - url
    - citationCount

novelty:
  algorithm: levenshtein
  high_risk_threshold: 0.4
  medium_risk_threshold: 0.7
  min_novelty_for_pass: 0.5
```

#### 5.3.3 reasoner.yaml

```yaml
# config/agents/reasoner.yaml
agent_id: reasoner
name: Reasoner
model: deepseek-r2
temperature: 0.8
max_tokens: 4096

dimensions:
  - cross_discipline
  - method_transfer
  - pain_point_breakthrough
  - trend_forecast

generation:
  min_candidates: 3
  max_candidates: 5
  require_all_dimensions: true

parsing:
  modes:
    - json
    - markdown
    - heuristic
  fallback_on_failure: true

weights:
  cross_discipline: 0.30
  method_transfer: 0.25
  pain_point_breakthrough: 0.25
  trend_forecast: 0.20
```

### 5.4 约束配置文件

#### 5.4.1 hard_rules.yaml

```yaml
# config/constraints/hard_rules.yaml
title:
  length:
    master: 25
    doctor: 30
    default: 25
  forbidden_prefixes:
    - "基于"
    - "关于"
    - "浅谈"
    - "试论"
  forbidden_suffixes_short:
    - "研究"
    - "应用"
    - "探讨"
    - "浅析"
    - "初探"

timeline:
  duration_months:
    master: [6, 36]
    doctor: [12, 60]

literature:
  count_baseline:
    master: 30
    doctor: 80
  recent_ratio:
    min: 0.5
    target: 0.7

duplication:
  thresholds:
    overall_max: 0.30
    single_source_max: 0.10
    self_duplication: 0.20
  algorithm: levenshtein

discipline:
  keyword_match_threshold: 0.2

advisor:
  direction_alignment: true
```

#### 5.4.2 novelty_weights.yaml

```yaml
# config/constraints/novelty_weights.yaml
novelty:
  weights:
    cross_discipline: 0.30
    method_transfer: 0.25
    pain_point_breakthrough: 0.25
    trend_forecast: 0.20
  
  thresholds:
    excellent: 85
    good: 70
    pass: 60
    fail: 0
  
  risk_levels:
    low:
      max_score: 100
      min_score: 85
      label: "低风险"
    medium:
      max_score: 84
      min_score: 60
      label: "中风险"
    high:
      max_score: 59
      min_score: 0
      label: "高风险"
```

---

## 6. 模型注册表

### 6.1 2026 模型注册表

ThesisMiner v8.0 支持的 10 个模型：

| 模型 ID | 名称 | 提供商 | 最大 Token | 输入价格 | 输出价格 |
|---------|------|--------|-----------|----------|----------|
| gpt-4.1-mini | GPT-4.1 Mini | OpenAI | 128K | $0.15/1K | $0.6/1K |
| gpt-4.1 | GPT-4.1 | OpenAI | 128K | $2.5/1K | $10/1K |
| deepseek-v3.2 | DeepSeek V3.2 | DeepSeek | 64K | $0.14/1K | $0.28/1K |
| deepseek-r2 | DeepSeek R2 | DeepSeek | 64K | $0.55/1K | $2.19/1K |
| claude-sonnet-4.5 | Claude Sonnet 4.5 | Anthropic | 200K | $3/1K | $15/1K |
| claude-opus-4.5 | Claude Opus 4.5 | Anthropic | 200K | $15/1K | $75/1K |
| qwen3-max | Qwen3 Max | 阿里 | 32K | $1.2/1K | $3.6/1K |
| gemini-2.5-pro | Gemini 2.5 Pro | Google | 1M | $1.25/1K | $5/1K |
| glm-4.6 | GLM-4.6 | 智谱 | 128K | $0.5/1K | $0.5/1K |
| doubao-1.5-pro | Doubao 1.5 Pro | 字节 | 256K | $0.8/1K | $2/1K |

### 6.2 模型能力对比

| 模型 | Streaming | Thinking | Vision | Function Call | Prompt Cache |
|------|-----------|----------|--------|---------------|--------------|
| gpt-4.1-mini | ✓ | - | - | ✓ | - |
| gpt-4.1 | ✓ | - | ✓ | ✓ | - |
| deepseek-v3.2 | ✓ | - | - | - | ✓ |
| deepseek-r2 | ✓ | ✓ | - | - | ✓ |
| claude-sonnet-4.5 | ✓ | ✓ | ✓ | - | - |
| claude-opus-4.5 | ✓ | ✓ | ✓ | - | - |
| qwen3-max | ✓ | - | - | ✓ | - |
| gemini-2.5-pro | ✓ | - | ✓ | ✓ | - |
| glm-4.6 | ✓ | - | - | ✓ | - |
| doubao-1.5-pro | ✓ | - | - | ✓ | - |

### 6.3 模型选择建议

| 用途 | 推荐模型 | 原因 |
|------|----------|------|
| 主管理（Orchestrator） | claude-sonnet-4.5 | 综合能力强 |
| 文献检索（Searcher） | deepseek-v3.2 | 性价比高，支持缓存 |
| 创意生成（Reasoner） | deepseek-r2 | 推理能力强 |
| 候选评估（Critic） | deepseek-r2 | 推理能力强 |
| 导师评审（Mentor） | gpt-4.1 | 综合能力强 |
| 报告生成（Writer） | claude-opus-4.5 | 写作能力最强 |

---

## 7. 数据库配置

### 7.1 SQLite 配置（默认）

```yaml
# config/system.yaml
database:
  type: sqlite
  url: sqlite:///data/thesis_miner.db
  
  sqlite:
    journal_mode: WAL          # WAL 模式（推荐）
    synchronous: NORMAL        # 同步模式
    cache_size: -64000         # 64MB 缓存
    foreign_keys: true         # 外键约束
    busy_timeout: 5000         # 忙等待 5 秒
```

### 7.2 PostgreSQL 配置（可选）

```yaml
database:
  type: postgresql
  url: postgresql://user:password@localhost:5432/thesis_miner
  pool_size: 10
  max_overflow: 20
  echo: false
```

### 7.3 数据库初始化

```python
# backend/database/init.py
import sqlite3
from pathlib import Path

def init_database(db_path: str = "data/thesis_miner.db"):
    """初始化数据库"""
    # 确保目录存在
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    
    # 设置 WAL 模式
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    
    # 创建表
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        status TEXT DEFAULT 'active',
        current_stage TEXT DEFAULT 'info_confirm',
        stage_results TEXT,  -- JSON
        metadata TEXT,       -- JSON
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE TABLE IF NOT EXISTS proposals (
        proposal_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        stages TEXT,         -- JSON
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id)
    );
    
    CREATE TABLE IF NOT EXISTS conversations (
        message_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        agent_id TEXT,
        stage TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id)
    );
    
    CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
    CREATE INDEX IF NOT EXISTS idx_proposals_session_id ON proposals(session_id);
    CREATE INDEX IF NOT EXISTS idx_conversations_session_id ON conversations(session_id);
    """)
    
    conn.commit()
    conn.close()
```

---

## 8. 缓存配置

### 8.1 内存缓存（默认）

```yaml
cache:
  enabled: true
  type: memory
  ttl: 3600
  max_size: 1000
```

### 8.2 Redis 缓存（可选）

```yaml
cache:
  enabled: true
  type: redis
  url: redis://localhost:6379/0
  ttl: 3600
  max_size: 10000
```

### 8.3 Prompt 缓存

```yaml
cache:
  prompt_cache:
    enabled: true
    target_hit_rate: 0.95
    prefix_version: v8.0.1
    warmup_on_session_create: true
    
    # DeepSeek 特殊配置
    deepseek:
      enabled: true
      cache_tokens_threshold: 1024
      max_cache_tokens: 16384
      ttl: 3600
```

```python
# backend/ai/prompt_cache.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class CachedPrefix:
    """缓存的前缀"""
    system_prompt: str
    user_info: dict
    version: str
    token_count: int

def build_cached_prefix(
    system_prompt: str,
    user_info: dict,
    version: str = "v8.0.1"
) -> CachedPrefix:
    """构建缓存前缀"""
    # 估算 token 数
    token_count = len(system_prompt) // 3  # 粗略估算
    
    return CachedPrefix(
        system_prompt=system_prompt,
        user_info=user_info,
        version=version,
        token_count=token_count
    )

def is_deepseek_model(model_id: str) -> bool:
    """判断是否为 DeepSeek 模型"""
    return model_id.startswith("deepseek-")
```

---

## 9. 日志配置

### 9.1 日志级别

| 级别 | 值 | 说明 |
|------|----|------|
| DEBUG | 10 | 调试信息 |
| INFO | 20 | 一般信息 |
| WARNING | 30 | 警告 |
| ERROR | 40 | 错误 |
| CRITICAL | 50 | 严重错误 |

### 9.2 日志配置

```yaml
logging:
  level: INFO
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: logs/thesis_miner.log
  max_size: 10485760  # 10MB
  backup_count: 5
  
  # 控制台输出
  console:
    enabled: true
    level: INFO
  
  # 文件输出
  file:
    enabled: true
    level: DEBUG
    rotation: size  # size / time
    when: midnight  # time 模式
    interval: 1
  
  # 按模块配置
  loggers:
    backend.agents: INFO
    backend.ai: INFO
    backend.routes: INFO
    backend.constraints: INFO
    backend.database: WARNING
```

### 9.3 日志格式

```python
# backend/logging_config.py
import logging
import logging.handlers
from pathlib import Path

def setup_logging(config: dict):
    """配置日志"""
    log_config = config.get("logging", {})
    
    # 根 logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_config.get("level", "INFO"))
    
    # 格式
    formatter = logging.Formatter(
        log_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    
    # 控制台 handler
    console_config = log_config.get("console", {})
    if console_config.get("enabled", True):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(console_config.get("level", "INFO"))
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # 文件 handler
    file_config = log_config.get("file", {})
    if file_config.get("enabled", True):
        log_file = log_config.get("file", "logs/thesis_miner.log")
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=log_config.get("max_size", 10485760),
            backupCount=log_config.get("backup_count", 5),
            encoding="utf-8"
        )
        file_handler.setLevel(file_config.get("level", "DEBUG"))
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # 按模块配置
    for logger_name, level in log_config.get("loggers", {}).items():
        logging.getLogger(logger_name).setLevel(level)
```

---

## 10. 安全配置

### 10.1 认证配置

```yaml
security:
  auth_enabled: false
  token_header: Authorization
  token_prefix: Bearer
  token_expiry: 3600
  
  # JWT 配置
  jwt:
    algorithm: HS256
    secret_key: ${SECRET_KEY}
  
  # API Key 认证
  api_key_enabled: false
  api_key_header: X-API-Key
  api_keys:
    - key: "api-key-1"
      name: "Client 1"
      rate_limit: 100
```

### 10.2 CORS 配置

```yaml
security:
  cors:
    enabled: true
    allow_origins:
      - "http://localhost:3000"
      - "https://thesisminer.example.com"
    allow_methods: ["GET", "POST", "PUT", "PATCH", "DELETE"]
    allow_headers: ["*"]
    allow_credentials: true
    max_age: 3600
```

### 10.3 输入验证

```yaml
security:
  input_validation:
    enabled: true
    max_request_size: 1048576  # 1MB
    max_input_length: 10000    # 输入最大长度
    sanitize_html: true
    prevent_sql_injection: true
```

---

## 11. 限流配置

### 11.1 全局限流

```yaml
rate_limiting:
  enabled: true
  strategy: token_bucket
  default_limit: 60
  burst_limit: 10
```

### 11.2 按端点限流

```yaml
rate_limiting:
  endpoints:
    /api/sessions:
      limit: 30
      burst: 5
    /api/proposals/generate:
      limit: 10
      burst: 2
    /api/stream/proposals:
      limit: 5
      burst: 1
    /api/conversations:
      limit: 60
      burst: 10
    /api/config:
      limit: 100
      burst: 20
    /api/agents:
      limit: 60
      burst: 10
```

---

## 12. 会话配置

```yaml
session:
  timeout: 3600                # 会话超时（秒）
  max_sessions_per_user: 10    # 每用户最大会话数
  cleanup_interval: 300        # 清理间隔（秒）
  
  # 会话状态
  status:
    active: "active"           # 活跃
    inactive: "inactive"       # 不活跃
    closed: "closed"           # 已关闭
  
  # 阶段配置
  stages:
    - info_confirm
    - creativity
    - validation
    - generation
    - deep_assist
  
  # 阶段超时
  stage_timeout: 120           # 单阶段超时（秒）
```

---

## 13. 编排配置

```yaml
orchestration:
  max_concurrent_sessions: 100
  stage_timeout: 120
  
  retry:
    max_attempts: 3
    base_delay: 2.0
    max_delay: 30.0
    backoff: exponential
    retryable_errors:
      - AGENT_TIMEOUT
      - AGENT_RATE_LIMIT
      - AGENT_JSON_PARSE
      - MODEL_UNAVAILABLE
  
  fallback:
    strategy: fallback_proposal
    confidence_score: 0.4
    cascade:
      - searcher: mock_searcher
      - reasoner: fallback_proposal
      - critic: mark_warning
      - mentor: skip_mentor
      - writer: template_mode
  
  context:
    max_history_rounds: 5
    recent_history_rounds: 2
    compression_threshold: 5
    context_overflow_threshold: 0.8
```

---

## 14. 流式配置

```yaml
streaming:
  sse:
    enabled: true
    heartbeat_interval: 30
    retry_interval: 3
    max_connections: 100
  
  websocket:
    enabled: true
    heartbeat_interval: 30
    timeout: 90
    max_connections: 100
    
    # 消息大小限制
    max_message_size: 65536  # 64KB
```

---

## 15. 附录

### 15.1 配置速查表

```
┌─────────────────────────────────────────────────────────────────┐
│                    配置速查表                                     │
├──────────────────┬──────────────────────┬──────────────────────┤
│ 配置类型         │ 文件位置             │ 优先级               │
├──────────────────┼──────────────────────┼──────────────────────┤
│ 环境变量         │ .env                 │ 最高                 │
│ 运行时配置       │ data/config.json     │ 高                   │
│ YAML 配置        │ config/*.yaml        │ 中                   │
│ 代码默认值       │ backend/config.py    │ 最低                 │
└──────────────────┴──────────────────────┴──────────────────────┘
```

### 15.2 常用配置项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| AI_MODEL | gpt-4.1-mini | 默认模型 |
| DATABASE_URL | sqlite:///data/thesis_miner.db | 数据库 |
| LOG_LEVEL | INFO | 日志级别 |
| CACHE_ENABLED | true | 缓存启用 |
| AUTH_ENABLED | false | 认证启用 |
| DEBUG | false | 调试模式 |

### 15.3 配置示例

#### 15.3.1 开发环境配置

```bash
# .env.dev
DEBUG=true
ENVIRONMENT=development
LOG_LEVEL=DEBUG
AI_MODEL=gpt-4.1-mini
AI_API_KEY=sk-xxx
DATABASE_URL=sqlite:///data/thesis_miner_dev.db
```

#### 15.3.2 生产环境配置

```bash
# .env.prod
DEBUG=false
ENVIRONMENT=production
LOG_LEVEL=INFO
AI_MODEL=claude-sonnet-4.5
AI_API_KEY=sk-xxx
DATABASE_URL=postgresql://user:pass@db:5432/thesis_miner
CACHE_ENABLED=true
AUTH_ENABLED=true
SECRET_KEY=strong-secret-key
```

### 15.4 相关文档

- [Agent 参考](agent_reference.md)
- [约束规则参考](constraint_reference.md)
- [API 参考](api_reference.md)
- [故障排查参考](troubleshooting_reference.md)
- [模型配置指南](../tutorials/model_configuration_guide.md)

### 15.5 术语表

| 术语 | 英文 | 含义 |
|------|------|------|
| 配置层次 | Config Hierarchy | 配置的优先级顺序 |
| 环境变量 | Environment Variable | 操作系统级配置 |
| 运行时配置 | Runtime Config | 可动态修改的配置 |
| 模型注册表 | Model Registry | 模型配置列表 |
| WAL | Write-Ahead Logging | 预写式日志 |
| TTL | Time To Live | 缓存生存时间 |
| CORS | Cross-Origin Resource Sharing | 跨域资源共享 |

### 15.6 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v8.0.0 | 2026-06-20 | 初始版本 |
| v7.5.0 | 2026-05-15 | 添加 Prompt 缓存配置 |
| v7.0.0 | 2026-04-01 | 重构配置体系 |
| v6.0.0 | 2026-02-10 | 添加 YAML 配置 |

---

## 16. 配置管理工具

### 16.1 配置加载流程详解

ThesisMiner v8.0 的配置加载遵循分层覆盖原则，下图展示了完整的加载流程：

```
┌─────────────────────────────────────────────────────────────┐
│                    应用启动 (App Startup)                     │
└──────────────────────────────────┬──────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 加载代码默认值 (Code Defaults)                       │
│  - Settings 类字段默认值                                       │
│  - PREDEFINED_RULES 常量                                       │
│  - DEFAULT_AGENT_CONFIG 字典                                   │
└──────────────────────────────────┬──────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 加载 YAML 配置文件                                    │
│  - data/config/system.yaml                                    │
│  - data/config/models.yaml                                    │
│  - data/config/agents/*.yaml                                  │
│  - data/config/constraints/*.yaml                             │
└──────────────────────────────────┬──────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 加载 config.json                                      │
│  - data/config.json                                           │
│  - 覆盖 models、step_models、agent_models                     │
└──────────────────────────────────┬──────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 加载环境变量 (.env)                                   │
│  - DATABASE_URL、CACHE_ENABLED 等                              │
│  - 最高优先级                                                  │
└──────────────────────────────────┬──────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 5: 配置校验 (Validation)                                 │
│  - 字段类型检查                                                │
│  - 必填字段检查                                                │
│  - 业务规则校验                                                │
└──────────────────────────────────┬──────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 6: 缓存 Settings 单例 (lru_cache)                       │
└─────────────────────────────────────────────────────────────┘
```

### 16.2 Settings 类完整定义

```python
from pydantic import BaseSettings, Field, validator
from typing import Optional, List, Dict, Any
from functools import lru_cache
import os
from pathlib import Path

class Settings(BaseSettings):
    """ThesisMiner 全局配置类"""
    
    # 应用基础配置
    APP_NAME: str = "ThesisMiner"
    APP_VERSION: str = "8.0.0"
    ENVIRONMENT: str = "development"  # development | staging | production
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4
    
    # 数据库配置
    DATABASE_URL: str = "sqlite:///data/thesis_miner.db"
    DATABASE_ECHO: bool = False
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 3600
    
    # 缓存配置
    CACHE_ENABLED: bool = True
    CACHE_TYPE: str = "memory"  # memory | redis
    CACHE_TTL: int = 3600
    CACHE_MAX_SIZE: int = 1000
    REDIS_URL: Optional[str] = None
    
    # 认证配置
    AUTH_ENABLED: bool = False
    SECRET_KEY: str = "thesis-miner-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 小时
    API_KEY_HEADER: str = "X-API-Key"
    
    # CORS 配置
    CORS_ENABLED: bool = True
    CORS_ORIGINS: List[str] = ["*"]
    CORS_METHODS: List[str] = ["*"]
    CORS_HEADERS: List[str] = ["*"]
    
    # 限流配置
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT: int = 100  # 每分钟请求数
    RATE_LIMIT_BURST: int = 20
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: Optional[str] = "logs/thesis_miner.log"
    LOG_MAX_SIZE: int = 10485760  # 10MB
    LOG_BACKUP_COUNT: int = 5
    
    # Session 配置
    SESSION_TIMEOUT_MINUTES: int = 30
    SESSION_MAX_CONCURRENT: int = 100
    SESSION_CLEANUP_INTERVAL: int = 300  # 5 分钟
    
    # 编排配置
    ORCHESTRATION_MAX_RETRIES: int = 3
    ORCHESTRATION_TIMEOUT: int = 300
    ORCHESTRATION_PARALLEL_AGENTS: bool = True
    VALIDATION_THRESHOLD: int = 60
    
    # 流式配置
    SSE_HEARTBEAT_INTERVAL: int = 15
    SSE_CONNECTION_TIMEOUT: int = 300
    WEBSOCKET_HEARTBEAT_INTERVAL: int = 30
    WEBSOCKET_CONNECTION_TIMEOUT: int = 90
    
    # 路径配置
    DATA_DIR: Path = Path("data")
    CONFIG_DIR: Path = Path("data/config")
    LOGS_DIR: Path = Path("logs")
    CACHE_DIR: Path = Path("data/cache")
    
    @validator("ENVIRONMENT")
    def validate_environment(cls, v):
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of {allowed}")
        return v
    
    @validator("LOG_LEVEL")
    def validate_log_level(cls, v):
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {allowed}")
        return v.upper()
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """获取全局 Settings 单例"""
    return Settings()
```

### 16.3 配置校验工具

```python
class ConfigValidator:
    """配置校验工具类"""
    
    REQUIRED_ENV_VARS = {
        "production": ["DATABASE_URL", "SECRET_KEY"],
        "staging": ["DATABASE_URL", "SECRET_KEY"],
        "development": []
    }
    
    @classmethod
    def validate(cls, settings: Settings) -> List[str]:
        """校验配置，返回错误列表"""
        errors = []
        
        # 检查必填环境变量
        required = cls.REQUIRED_ENV_VARS.get(settings.ENVIRONMENT, [])
        for var in required:
            value = getattr(settings, var, None)
            if not value or value == "":
                errors.append(f"Missing required env var: {var}")
        
        # 检查生产环境安全配置
        if settings.ENVIRONMENT == "production":
            if settings.SECRET_KEY == "thesis-miner-secret-key-change-in-production":
                errors.append("SECRET_KEY must be changed in production")
            if settings.DEBUG:
                errors.append("DEBUG must be False in production")
            if "*" in settings.CORS_ORIGINS:
                errors.append("CORS_ORIGINS must not be '*' in production")
        
        # 检查数据库 URL 格式
        if not settings.DATABASE_URL.startswith(("sqlite://", "postgresql://", "mysql://")):
            errors.append("DATABASE_URL must start with sqlite://, postgresql://, or mysql://")
        
        # 检查端口范围
        if not (1 <= settings.PORT <= 65535):
            errors.append(f"PORT must be between 1 and 65535, got {settings.PORT}")
        
        # 检查 Worker 数量
        if settings.WORKERS < 1:
            errors.append("WORKERS must be at least 1")
        
        return errors
    
    @classmethod
    def validate_model_config(cls, config: Dict) -> List[str]:
        """校验模型配置"""
        errors = []
        
        required_fields = ["id", "name", "provider", "max_tokens"]
        for field in required_fields:
            if field not in config:
                errors.append(f"Model config missing required field: {field}")
        
        if "id" in config:
            valid_providers = {"openai", "anthropic", "deepseek", "google", "zhipu", "bytedance", "alibaba"}
            if config.get("provider") not in valid_providers:
                errors.append(f"Invalid provider: {config.get('provider')}")
        
        if "max_tokens" in config:
            if not isinstance(config["max_tokens"], int) or config["max_tokens"] < 1:
                errors.append("max_tokens must be a positive integer")
        
        return errors
```

### 16.4 配置热重载

```python
import watchdog.events
import watchdog.observers
import threading
import time

class ConfigWatcher:
    """配置文件热重载监听器"""
    
    def __init__(self, config_dir: str, callback):
        self.config_dir = config_dir
        self.callback = callback
        self.observer = watchdog.observers.Observer()
        self._debounce_timer = None
        self._debounce_delay = 1.0  # 1 秒防抖
    
    def start(self):
        """启动监听"""
        handler = watchdog.events.FileSystemEventHandler()
        handler.on_modified = self._on_file_changed
        handler.on_created = self._on_file_changed
        self.observer.schedule(handler, self.config_dir, recursive=True)
        self.observer.start()
    
    def stop(self):
        """停止监听"""
        self.observer.stop()
        self.observer.join()
    
    def _on_file_changed(self, event):
        """文件变更回调（带防抖）"""
        if not event.src_path.endswith(('.yaml', '.yml', '.json', '.env')):
            return
        
        if self._debounce_timer:
            self._debounce_timer.cancel()
        
        self._debounce_timer = threading.Timer(
            self._debounce_delay,
            self._reload_config
        )
        self._debounce_timer.start()
    
    def _reload_config(self):
        """重新加载配置"""
        try:
            # 清除 Settings 缓存
            get_settings.cache_clear()
            new_settings = get_settings()
            
            # 触发回调
            self.callback(new_settings)
            
            logger.info("Configuration reloaded successfully")
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")
```

### 16.5 配置导出工具

```python
import json
import yaml
from pathlib import Path

class ConfigExporter:
    """配置导出工具"""
    
    @staticmethod
    def export_to_json(settings: Settings, output_path: str):
        """导出配置为 JSON 文件"""
        config_dict = settings.dict()
        
        # 转换 Path 为字符串
        for key, value in config_dict.items():
            if isinstance(value, Path):
                config_dict[key] = str(value)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)
    
    @staticmethod
    def export_to_yaml(settings: Settings, output_path: str):
        """导出配置为 YAML 文件"""
        config_dict = settings.dict()
        
        # 转换 Path 为字符串
        for key, value in config_dict.items():
            if isinstance(value, Path):
                config_dict[key] = str(value)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)
    
    @staticmethod
    def export_to_env(settings: Settings, output_path: str):
        """导出配置为 .env 文件"""
        config_dict = settings.dict()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for key, value in config_dict.items():
                if isinstance(value, Path):
                    value = str(value)
                elif isinstance(value, list):
                    value = ",".join(str(v) for v in value)
                elif isinstance(value, bool):
                    value = "true" if value else "false"
                
                f.write(f"{key}={value}\n")
    
    @staticmethod
    def export_masked(settings: Settings, output_path: str):
        """导出脱敏配置（用于分享/调试）"""
        config_dict = settings.dict()
        
        # 脱敏敏感字段
        sensitive_keys = {"SECRET_KEY", "DATABASE_URL", "REDIS_URL"}
        for key in sensitive_keys:
            if key in config_dict and config_dict[key]:
                config_dict[key] = "***MASKED***"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)
```

---

## 17. 多环境配置管理

### 17.1 环境分层策略

```
┌─────────────────────────────────────────────────────────────┐
│                    多环境配置架构                              │
└─────────────────────────────────────────────────────────────┘

  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
  │   Development   │  │     Staging     │  │   Production    │
  ├─────────────────┤  ├─────────────────┤  ├─────────────────┤
  │ • DEBUG=true    │  │ • DEBUG=false   │  │ • DEBUG=false   │
  │ • SQLite        │  │ • PostgreSQL    │  │ • PostgreSQL HA │
  │ • Memory Cache  │  │ • Redis         │  │ • Redis Cluster │
  │ • No Auth       │  │ • Auth Enabled  │  │ • Auth + HTTPS  │
  │ • CORS=*        │  │ • CORS=specific │  │ • CORS=domain   │
  │ • 1 Worker      │  │ • 2 Workers     │  │ • 4+ Workers    │
  │ • Verbose Logs  │  │ • INFO Logs     │  │ • WARN Logs     │
  └─────────────────┘  └─────────────────┘  └─────────────────┘
          │                    │                    │
          └────────────────────┼────────────────────┘
                               │
                               ▼
                   ┌───────────────────────┐
                   │  共享基础配置          │
                   │  (base.yaml)          │
                   └───────────────────────┘
```

### 17.2 开发环境配置 (.env.development)

```bash
# .env.development
APP_NAME=ThesisMiner-Dev
APP_VERSION=8.0.0
ENVIRONMENT=development
DEBUG=true
HOST=127.0.0.1
PORT=8000
WORKERS=1

# 数据库 - 开发环境使用 SQLite
DATABASE_URL=sqlite:///data/thesis_miner_dev.db
DATABASE_ECHO=true

# 缓存 - 开发环境使用内存缓存
CACHE_ENABLED=true
CACHE_TYPE=memory
CACHE_TTL=300

# 认证 - 开发环境关闭
AUTH_ENABLED=false

# CORS - 开发环境允许所有
CORS_ENABLED=true
CORS_ORIGINS=["*"]

# 限流 - 开发环境放宽
RATE_LIMIT_ENABLED=false

# 日志 - 开发环境详细日志
LOG_LEVEL=DEBUG
LOG_FILE=logs/thesis_miner_dev.log

# Session - 开发环境超时较长
SESSION_TIMEOUT_MINUTES=120
SESSION_MAX_CONCURRENT=10
```

### 17.3 生产环境配置 (.env.production)

```bash
# .env.production
APP_NAME=ThesisMiner
APP_VERSION=8.0.0
ENVIRONMENT=production
DEBUG=false
HOST=0.0.0.0
PORT=8000
WORKERS=4

# 数据库 - 生产环境使用 PostgreSQL
DATABASE_URL=postgresql://thesis_user:strong_password@db-host:5432/thesis_miner
DATABASE_ECHO=false
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40

# 缓存 - 生产环境使用 Redis
CACHE_ENABLED=true
CACHE_TYPE=redis
CACHE_TTL=3600
REDIS_URL=redis://redis-host:6379/0

# 认证 - 生产环境必须开启
AUTH_ENABLED=true
SECRET_KEY=<generate-with-openssl-rand-hex-32>
JWT_EXPIRE_MINUTES=720

# CORS - 生产环境限制域名
CORS_ENABLED=true
CORS_ORIGINS=["https://thesis.example.com","https://app.thesis.example.com"]

# 限流 - 生产环境严格
RATE_LIMIT_ENABLED=true
RATE_LIMIT_DEFAULT=100
RATE_LIMIT_BURST=20

# 日志 - 生产环境只记录 WARNING 及以上
LOG_LEVEL=WARNING
LOG_FILE=logs/thesis_miner.log

# Session - 生产环境超时较短
SESSION_TIMEOUT_MINUTES=30
SESSION_MAX_CONCURRENT=1000
```

### 17.4 环境切换脚本

```python
import os
import shutil
from pathlib import Path

class EnvironmentManager:
    """环境切换管理器"""
    
    ENV_FILES = {
        "development": ".env.development",
        "staging": ".env.staging",
        "production": ".env.production"
    }
    
    @classmethod
    def switch(cls, env: str):
        """切换环境"""
        if env not in cls.ENV_FILES:
            raise ValueError(f"Unknown environment: {env}")
        
        source = cls.ENV_FILES[env]
        target = ".env"
        
        if not Path(source).exists():
            raise FileNotFoundError(f"Environment file not found: {source}")
        
        shutil.copy(source, target)
        print(f"Switched to {env} environment")
        print(f"  Source: {source}")
        print(f"  Target: {target}")
        
        # 清除配置缓存
        get_settings.cache_clear()
    
    @classmethod
    def current_env(cls) -> str:
        """获取当前环境"""
        return get_settings().ENVIRONMENT
    
    @classmethod
    def list_envs(cls) -> List[str]:
        """列出所有可用环境"""
        return [name for name, path in cls.ENV_FILES.items() if Path(path).exists()]
```

---

## 18. 高级配置场景

### 18.1 多租户配置

```python
from typing import Dict, Optional
from dataclasses import dataclass

@dataclass
class TenantConfig:
    """租户配置"""
    tenant_id: str
    display_name: str
    database_url: str
    redis_url: Optional[str] = None
    rate_limit: int = 100
    max_sessions: int = 10
    allowed_models: List[str] = None
    custom_rules: Dict = None

class TenantConfigManager:
    """多租户配置管理器"""
    
    def __init__(self):
        self._tenants: Dict[str, TenantConfig] = {}
        self._load_tenants()
    
    def _load_tenants(self):
        """从 data/config/tenants.yaml 加载租户配置"""
        tenants_file = Path("data/config/tenants.yaml")
        if not tenants_file.exists():
            return
        
        with open(tenants_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        for tenant_data in data.get('tenants', []):
            tenant = TenantConfig(**tenant_data)
            self._tenants[tenant.tenant_id] = tenant
    
    def get_tenant(self, tenant_id: str) -> Optional[TenantConfig]:
        """获取租户配置"""
        return self._tenants.get(tenant_id)
    
    def is_model_allowed(self, tenant_id: str, model_id: str) -> bool:
        """检查模型是否允许租户使用"""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return False
        if not tenant.allowed_models:
            return True  # 未限制
        return model_id in tenant.allowed_models
```

### 18.2 动态配置更新

```python
from typing import Callable, Dict, List

class DynamicConfigManager:
    """动态配置管理器（运行时可修改）"""
    
    def __init__(self):
        self._config: Dict = {}
        self._listeners: Dict[str, List[Callable]] = {}
    
    def get(self, key: str, default=None):
        """获取配置值"""
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any, notify: bool = True):
        """设置配置值"""
        old_value = self._config.get(key)
        self._config[key] = value
        
        if notify and old_value != value:
            self._notify_listeners(key, old_value, value)
    
    def register_listener(self, key: str, callback: Callable):
        """注册配置变更监听器"""
        if key not in self._listeners:
            self._listeners[key] = []
        self._listeners[key].append(callback)
    
    def _notify_listeners(self, key: str, old_value: Any, new_value: Any):
        """通知监听器"""
        for callback in self._listeners.get(key, []):
            try:
                callback(key, old_value, new_value)
            except Exception as e:
                logger.error(f"Config listener error: {e}")
    
    def snapshot(self) -> Dict:
        """获取配置快照"""
        return self._config.copy()
    
    def restore(self, snapshot: Dict):
        """从快照恢复配置"""
        self._config = snapshot.copy()
```

### 18.3 配置加密存储

```python
from cryptography.fernet import Fernet
import base64

class SecureConfigStorage:
    """加密配置存储"""
    
    def __init__(self, master_key: str):
        # 从主密钥派生 Fernet 密钥
        key = base64.urlsafe_b64encode(master_key.encode().ljust(32)[:32])
        self._cipher = Fernet(key)
    
    def encrypt_value(self, value: str) -> str:
        """加密配置值"""
        return self._cipher.encrypt(value.encode()).decode()
    
    def decrypt_value(self, encrypted: str) -> str:
        """解密配置值"""
        return self._cipher.decrypt(encrypted.encode()).decode()
    
    def encrypt_config(self, config: Dict) -> Dict:
        """加密整个配置字典中的敏感字段"""
        sensitive_keys = {"password", "secret", "api_key", "token", "private_key"}
        encrypted_config = {}
        
        for key, value in config.items():
            if any(s in key.lower() for s in sensitive_keys) and isinstance(value, str):
                encrypted_config[key] = f"ENC:{self.encrypt_value(value)}"
            else:
                encrypted_config[key] = value
        
        return encrypted_config
    
    def decrypt_config(self, config: Dict) -> Dict:
        """解密配置字典"""
        decrypted_config = {}
        
        for key, value in config.items():
            if isinstance(value, str) and value.startswith("ENC:"):
                decrypted_config[key] = self.decrypt_value(value[4:])
            else:
                decrypted_config[key] = value
        
        return decrypted_config
```

---

> **文档结束**
> 
> 如有疑问，请参考相关文档或提交 Issue。
