# ThesisMiner v8.0 故障排查参考文档

> **文档版本**: v8.0.0
> **最后更新**: 2026-06-20
> **适用范围**: ThesisMiner v8.0 及以上版本
> **目标读者**: 开发者、运维工程师、系统管理员

---

## 目录

1. [文档概述](#1-文档概述)
2. [故障排查方法论](#2-故障排查方法论)
3. [安装与部署问题](#3-安装与部署问题)
4. [启动与初始化问题](#4-启动与初始化问题)
5. [数据库问题](#5-数据库问题)
6. [缓存问题](#6-缓存问题)
7. [Agent 运行问题](#7-agent-运行问题)
8. [模型调用问题](#8-模型调用问题)
9. [API 与网络问题](#9-api-与网络问题)
10. [SSE 与 WebSocket 问题](#10-sse-与-websocket-问题)
11. [约束规则问题](#11-约束规则问题)
12. [性能问题](#12-性能问题)
13. [内存与资源问题](#13-内存与资源问题)
14. [安全与认证问题](#14-安全与认证问题)
15. [日志与监控](#15-日志与监控)
16. [常见错误码速查](#16-常见错误码速查)
17. [调试技巧与工具](#17-调试技巧与工具)
18. [附录](#18-附录)

---

## 1. 文档概述

### 1.1 文档目的

本文档是 ThesisMiner v8.0 的官方故障排查参考，旨在帮助开发者、运维工程师和系统管理员快速定位、诊断和解决系统运行过程中遇到的各类问题。文档涵盖从安装部署到生产环境运维的全生命周期故障排查场景。

### 1.2 适用范围

| 组件 | 版本 | 说明 |
|------|------|------|
| ThesisMiner Core | v8.0.0 | 核心引擎 |
| ThesisMiner API | v8.0.0 | RESTful API 服务 |
| ThesisMiner CLI | v8.0.0 | 命令行工具 |
| ThesisMiner SDK | v8.0.0 | Python/JavaScript SDK |
| Python Runtime | ≥3.11 | 推荐 3.12 |
| 数据库 | SQLite 3.40+ / PostgreSQL 14+ | |
| Redis | ≥6.2 | 可选，用于分布式缓存 |

### 1.3 故障分级

```
┌─────────────────────────────────────────────────────────────┐
│                    故障严重等级定义                            │
├──────────┬──────────────────────────────────────────────────┤
│   P0     │ 系统完全不可用，所有用户受影响                       │
│ (Critical)│ 例：服务崩溃、数据库损坏、数据丢失                  │
├──────────┼──────────────────────────────────────────────────┤
│   P1     │ 核心功能不可用，影响多数用户                         │
│ (High)   │ 例：Agent 编排失败、API 大量 500 错误              │
├──────────┼──────────────────────────────────────────────────┤
│   P2     │ 部分功能异常，影响少数用户                          │
│ (Medium) │ 例：某个模型调用失败、SSE 偶尔断连                  │
├──────────┼──────────────────────────────────────────────────┤
│   P3     │ 轻微问题，不影响核心功能                            │
│ (Low)    │ 例：日志格式异常、UI 显示问题                       │
└──────────┴──────────────────────────────────────────────────┘
```

### 1.4 排查流程总览

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  问题报告     │ ──▶ │  现象收集     │ ──▶ │  日志分析     │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                 │
                                                 ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  验证修复     │ ◀── │  方案实施     │ ◀── │  根因定位     │
└──────────────┘     └──────────────┘     └──────────────┘
```

### 1.5 相关文档

- [Agent 参考文档](agent_reference.md)
- [约束规则参考](constraint_reference.md)
- [API 参考文档](api_reference.md)
- [配置参考文档](configuration_reference.md)

---

## 2. 故障排查方法论

### 2.1 系统化排查方法

#### 2.1.1 5W2H 分析法

| 维度 | 问题 | 示例 |
|------|------|------|
| What | 发生了什么？ | API 返回 500 错误 |
| Why | 为什么发生？ | 数据库连接池耗尽 |
| When | 何时发生？ | 高峰期 14:00-16:00 |
| Where | 在哪里发生？ | Production 环境，API Server 3 |
| Who | 谁受影响？ | 所有创建 Session 的用户 |
| How | 如何发生？ | 并发请求导致连接池耗尽 |
| How much | 影响多大？ | 30% 请求失败 |

#### 2.1.2 二分法排查

```python
def binary_search_issue(start_state, end_state):
    """二分法定位问题引入点"""
    while not is_consecutive(start_state, end_state):
        mid_state = get_middle_state(start_state, end_state)
        if has_issue(mid_state):
            end_state = mid_state
        else:
            start_state = mid_state
    return start_state  # 问题引入点
```

#### 2.1.3 日志时间线分析

```
2026-06-20 14:00:00 INFO  Session created: sess_abc123
2026-06-20 14:00:01 INFO  Orchestrator started for session sess_abc123
2026-06-20 14:00:02 INFO  Searcher agent called
2026-06-20 14:00:05 WARN  Searcher timeout after 3s, retrying...
2026-06-20 14:00:08 ERROR Searcher failed after 3 retries: ConnectionError
2026-06-20 14:00:08 ERROR Orchestrator stage 'creativity' failed
2026-06-20 14:00:08 ERROR Session sess_abc123 marked as failed
```

### 2.2 日志分析技巧

#### 2.2.1 日志级别说明

| 级别 | 数值 | 用途 | 示例 |
|------|------|------|------|
| DEBUG | 10 | 详细调试信息 | 变量值、函数调用 |
| INFO | 20 | 正常运行信息 | Session 创建、Agent 调用 |
| WARNING | 30 | 警告，不影响功能 | 重试、降级 |
| ERROR | 40 | 错误，影响部分功能 | API 调用失败 |
| CRITICAL | 50 | 严重错误，系统不可用 | 数据库连接断开 |

#### 2.2.2 日志过滤命令

```bash
# 查看所有 ERROR 及以上日志
grep -E "ERROR|CRITICAL" logs/thesis_miner.log

# 查看特定 Session 的日志
grep "sess_abc123" logs/thesis_miner.log

# 查看特定时间段的日志
awk '/2026-06-20 14:00/,/2026-06-20 14:30/' logs/thesis_miner.log

# 统计错误类型
grep "ERROR" logs/thesis_miner.log | awk '{print $NF}' | sort | uniq -c | sort -rn

# 实时跟踪日志
tail -f logs/thesis_miner.log | grep --color=auto "ERROR\|WARN"
```

#### 2.2.3 结构化日志分析

```python
import json
from collections import Counter

def analyze_error_logs(log_file: str):
    """分析错误日志，统计错误类型"""
    error_types = Counter()
    error_sessions = set()
    
    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                log_entry = json.loads(line)
                if log_entry.get('level') in ('ERROR', 'CRITICAL'):
                    error_types[log_entry.get('error_type', 'unknown')] += 1
                    if 'session_id' in log_entry:
                        error_sessions.add(log_entry['session_id'])
            except json.JSONDecodeError:
                continue
    
    print("Error Type Statistics:")
    for error_type, count in error_types.most_common():
        print(f"  {error_type}: {count}")
    
    print(f"\nAffected Sessions: {len(error_sessions)}")
    return error_types, error_sessions
```

### 2.3 性能分析工具

#### 2.3.1 Python 性能分析

```python
import cProfile
import pstats
from io import StringIO

def profile_function(func, *args, **kwargs):
    """性能分析函数"""
    profiler = cProfile.Profile()
    profiler.enable()
    
    result = func(*args, **kwargs)
    
    profiler.disable()
    
    # 输出统计信息
    s = StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
    ps.print_stats(20)
    print(s.getvalue())
    
    return result

# 使用示例
profile_function(orchestrator.run, session_id="sess_abc123")
```

#### 2.3.2 内存分析

```python
import tracemalloc
import linecache

def memory_snapshot():
    """内存快照分析"""
    tracemalloc.start()
    
    # 执行需要分析的代码
    do_something()
    
    snapshot = tracemalloc.take_snapshot()
    top_stats = snapshot.statistics('lineno')
    
    print("[ Top 10 memory usage ]")
    for stat in top_stats[:10]:
        print(stat)

def memory_diff(snapshot1, snapshot2):
    """内存差异分析"""
    diff = snapshot2.compare_to(snapshot1, 'lineno')
    print("[ Memory diff ]")
    for stat in diff[:10]:
        print(stat)
```

### 2.4 系统资源检查

#### 2.4.1 系统状态检查脚本

```bash
#!/bin/bash
# system_health_check.sh - 系统健康检查脚本

echo "========== System Health Check =========="
echo "Timestamp: $(date)"
echo ""

# CPU 使用率
echo "--- CPU Usage ---"
top -bn1 | grep "Cpu(s)" | awk '{print "CPU Usage: " $2 + $4 "%"}'

# 内存使用
echo ""
echo "--- Memory Usage ---"
free -h | grep -E "Mem|Swap"

# 磁盘使用
echo ""
echo "--- Disk Usage ---"
df -h | grep -E "Filesystem|/dev/"

# 网络连接
echo ""
echo "--- Network Connections ---"
ss -s

# 进程状态
echo ""
echo "--- ThesisMiner Processes ---"
ps aux | grep -E "thesis_miner|uvicorn" | grep -v grep

# 端口监听
echo ""
echo "--- Listening Ports ---"
ss -tlnp | grep -E "8000|5432|6379"
```

---

## 3. 安装与部署问题

### 3.1 Python 环境问题

#### 3.1.1 Python 版本不兼容

**现象**:
```
ERROR: ThesisMiner requires Python 3.11 or higher, got 3.10.8
```

**原因**: ThesisMiner v8.0 使用了 Python 3.11+ 的特性，如 `tomllib`、改进的异常处理等。

**解决方案**:

```bash
# 方案 1: 使用 pyenv 安装指定版本
pyenv install 3.12.0
pyenv local 3.12.0

# 方案 2: 使用 conda
conda create -n thesis-miner python=3.12
conda activate thesis-miner

# 方案 3: 使用 uv (推荐)
uv python install 3.12
uv venv --python 3.12
```

**验证**:
```bash
python --version
# Python 3.12.0
```

#### 3.1.2 依赖安装失败

**现象**:
```
ERROR: Failed building wheel for cryptography
ERROR: Could not build wheels for cryptography which use PEP 517
```

**原因**: `cryptography` 等包需要编译，缺少编译工具。

**解决方案**:

```bash
# Windows - 安装 Visual Studio Build Tools
choco install visualstudio2022buildtools --package-parameters "--add Microsoft.VisualStudio.Workload.VCTools"

# Linux (Ubuntu/Debian)
sudo apt-get install build-essential libssl-dev libffi-dev python3-dev

# macOS
xcode-select --install
brew install openssl@3

# 或者使用预编译版本
pip install --only-binary :all: cryptography
```

#### 3.1.3 虚拟环境冲突

**现象**:
```
ImportError: cannot import name '_openssl' from 'cryptography.hazmat.bindings._rust'
```

**原因**: 系统环境与虚拟环境的包冲突。

**解决方案**:

```bash
# 1. 删除现有虚拟环境
rm -rf .venv

# 2. 创建新的虚拟环境
python -m venv .venv

# 3. 激活虚拟环境
# Linux/macOS
source .venv/bin/activate
# Windows
.venv\Scripts\activate

# 4. 升级 pip
pip install --upgrade pip setuptools wheel

# 5. 重新安装依赖
pip install -r requirements.txt
```

### 3.2 数据库安装问题

#### 3.2.1 SQLite 版本过低

**现象**:
```
sqlite3.OperationalError: cannot enable WAL mode
```

**原因**: SQLite 版本低于 3.7.0，不支持 WAL 模式。

**解决方案**:

```bash
# 检查 SQLite 版本
sqlite3 --version

# Linux - 升级 SQLite
sudo apt-get update
sudo apt-get install sqlite3 libsqlite3-dev

# macOS - 使用 Homebrew
brew install sqlite3

# Python 中检查
python -c "import sqlite3; print(sqlite3.sqlite_version)"
```

#### 3.2.2 PostgreSQL 连接失败

**现象**:
```
sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) 
could not connect to server: Connection refused
```

**排查步骤**:

```bash
# 1. 检查 PostgreSQL 服务状态
sudo systemctl status postgresql

# 2. 检查端口监听
ss -tlnp | grep 5432

# 3. 检查 pg_hba.conf 配置
cat /etc/postgresql/14/main/pg_hba.conf | grep -v "^#" | grep -v "^$"

# 4. 测试连接
psql -h localhost -U thesis_user -d thesis_miner -c "SELECT 1;"
```

**常见解决方案**:

```bash
# 方案 1: 启动 PostgreSQL 服务
sudo systemctl start postgresql
sudo systemctl enable postgresql

# 方案 2: 修改 pg_hba.conf 允许连接
# 编辑 /etc/postgresql/14/main/pg_hba.conf
# host    all    all    0.0.0.0/0    md5

# 方案 3: 修改 postgresql.conf 监听地址
# listen_addresses = '*'

# 重启 PostgreSQL
sudo systemctl restart postgresql
```

### 3.3 Redis 安装问题

#### 3.3.1 Redis 连接失败

**现象**:
```
redis.exceptions.ConnectionError: Error 111 connecting to localhost:6379. Connection refused.
```

**排查步骤**:

```bash
# 1. 检查 Redis 服务状态
sudo systemctl status redis

# 2. 检查端口
ss -tlnp | grep 6379

# 3. 测试连接
redis-cli ping
# 期望输出: PONG

# 4. 检查 Redis 日志
tail -f /var/log/redis/redis-server.log
```

**解决方案**:

```bash
# 启动 Redis
sudo systemctl start redis
sudo systemctl enable redis

# 或者使用 Docker
docker run -d --name thesis-redis -p 6379:6379 redis:7-alpine
```

### 3.4 Docker 部署问题

#### 3.4.1 Docker 构建失败

**现象**:
```
ERROR: failed to solve: process "/bin/sh -c pip install -r requirements.txt" did not complete successfully
```

**排查**:

```bash
# 查看详细构建日志
docker build --no-cache --progress=plain -t thesis-miner .

# 检查 Dockerfile
cat Dockerfile
```

**常见解决方案**:

```dockerfile
# 使用多阶段构建减少镜像大小
FROM python:3.12-slim as builder

WORKDIR /app

# 安装编译依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# 运行阶段
FROM python:3.12-slim

WORKDIR /app

# 复制安装好的包
COPY --from=builder /root/.local /root/.local
COPY . .

# 确保 PATH 包含用户安装的包
ENV PATH=/root/.local/bin:$PATH

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 3.4.2 Docker Compose 启动失败

**现象**:
```
ERROR: for thesis-miner Cannot start service thesis-miner: 
network not found
```

**解决方案**:

```bash
# 1. 清理旧的网络和容器
docker-compose down --remove-orphans
docker network prune

# 2. 重新构建并启动
docker-compose up -d --build

# 3. 查看日志
docker-compose logs -f thesis-miner
```

### 3.5 权限问题

#### 3.5.1 文件权限错误

**现象**:
```
PermissionError: [Errno 13] Permission denied: '/data/thesis_miner.db'
```

**解决方案**:

```bash
# 1. 检查目录权限
ls -la data/

# 2. 修改所有者
sudo chown -R $USER:$USER data/ logs/

# 3. 修改权限
chmod -R 755 data/ logs/

# 4. 对于 Docker 部署
docker exec -u root thesis-miner chown -R app:app /app/data /app/logs
```

---

## 4. 启动与初始化问题

### 4.1 应用启动失败

#### 4.1.1 端口被占用

**现象**:
```
uvicorn.error: [Errno 98] Address already in use
```

**排查**:

```bash
# 查看占用端口的进程
lsof -i :8000
# 或
ss -tlnp | grep 8000

# 终止占用进程
kill -9 <PID>

# 或者修改端口启动
uvicorn app.main:app --port 8001
```

#### 4.1.2 配置文件缺失

**现象**:
```
FileNotFoundError: [Errno 2] No such file or directory: 'data/config.json'
```

**解决方案**:

```bash
# 1. 创建必要的目录
mkdir -p data/config/agents
mkdir -p data/config/constraints
mkdir -p logs

# 2. 复制示例配置
cp config.example.json data/config.json
cp -r config.example/* data/config/

# 3. 或者使用初始化命令
python -m thesis_miner init
```

#### 4.1.3 数据库初始化失败

**现象**:
```
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) 
no such table: sessions
```

**原因**: 数据库表未创建。

**解决方案**:

```bash
# 1. 运行数据库迁移
python -m thesis_miner db upgrade

# 2. 或者使用初始化命令
python -m thesis_miner init --with-sample-data

# 3. 验证表是否创建
sqlite3 data/thesis_miner.db ".tables"
```

### 4.2 配置加载问题

#### 4.2.1 环境变量未生效

**现象**:
```
pydantic.env_settings.SettingsError: error validating environment variable "DATABASE_URL"
```

**排查**:

```bash
# 1. 检查 .env 文件是否存在
ls -la .env

# 2. 检查 .env 文件内容
cat .env

# 3. 检查环境变量是否加载
python -c "from thesis_miner.config import get_settings; s = get_settings(); print(s.DATABASE_URL)"

# 4. 检查环境变量优先级
python -c "import os; print(os.environ.get('DATABASE_URL'))"
```

**解决方案**:

```bash
# 确保 .env 文件在项目根目录
# 格式正确，无多余空格
DATABASE_URL=sqlite:///data/thesis_miner.db
CACHE_ENABLED=true
# 不要写成
# DATABASE_URL = sqlite:///data/thesis_miner.db  (有空格)
```

#### 4.2.2 YAML 配置解析错误

**现象**:
```
yaml.scanner.ScannerError: mapping values are not allowed here
```

**原因**: YAML 文件格式错误，通常是缩进或冒号问题。

**解决方案**:

```bash
# 1. 使用 YAML 校验工具
python -c "import yaml; yaml.safe_load(open('data/config/system.yaml'))"

# 2. 检查常见问题
# - 冒号后必须有空格
# - 使用空格缩进，不要用 Tab
# - 字符串包含特殊字符时用引号

# 正确示例
app:
  name: ThesisMiner
  version: "8.0.0"  # 字符串用引号

# 错误示例
app:
  name:ThesisMiner  # 冒号后无空格
  version: 8.0.0
```

### 4.3 模型配置问题

#### 4.3.1 模型 API Key 缺失

**现象**:
```
ValueError: API key not found for model 'gpt-4.1'. 
Please set OPENAI_API_KEY environment variable.
```

**解决方案**:

```bash
# 1. 设置环境变量
export OPENAI_API_KEY="sk-your-api-key"
export ANTHROPIC_API_KEY="sk-ant-your-api-key"
export DEEPSEEK_API_KEY="your-deepseek-key"

# 2. 或者在 .env 文件中配置
echo 'OPENAI_API_KEY=sk-your-api-key' >> .env

# 3. 或者在 config.json 中配置
# data/config.json
{
  "models": [
    {
      "id": "gpt-4.1",
      "api_key_env": "OPENAI_API_KEY",
      "api_key": "sk-your-api-key"  # 不推荐，会暴露在配置文件中
    }
  ]
}
```

#### 4.3.2 模型 ID 不存在

**现象**:
```
KeyError: "Model 'gpt-5' not found in registry"
```

**排查**:

```bash
# 1. 查看可用模型列表
python -c "from thesis_miner.models import MODEL_REGISTRY; print(list(MODEL_REGISTRY.keys()))"

# 2. 检查 config.json 中的模型配置
python -c "import json; print(json.dumps(json.load(open('data/config.json'))['models'], indent=2))"

# 3. 使用 API 查询
curl http://localhost:8000/api/v1/config/models
```

**解决方案**:

```json
// data/config.json - 添加缺失的模型
{
  "models": [
    {
      "id": "gpt-4.1",
      "name": "GPT-4.1",
      "provider": "openai",
      "max_tokens": 1047576,
      "temperature": 0.7
    }
  ]
}
```

---

## 5. 数据库问题

### 5.1 连接池耗尽

#### 5.1.1 现象与诊断

**现象**:
```
sqlalchemy.exc.TimeoutError: QueuePool limit of size 10 overflow 20 reached, 
connection timed out, timeout 30.00
```

**诊断**:

```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    "sqlite:///data/thesis_miner.db",
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30
)

# 查看连接池状态
print(f"Pool size: {engine.pool.size()}")
print(f"Checked out: {engine.pool.checkedout()}")
print(f"Overflow: {engine.pool.overflow()}")
print(f"Checked in: {engine.pool.checkedin()}")
```

#### 5.1.2 解决方案

```python
# 方案 1: 增大连接池
engine = create_engine(
    DATABASE_URL,
    pool_size=20,        # 默认 10
    max_overflow=40,     # 默认 20
    pool_timeout=60,     # 默认 30
    pool_recycle=3600    # 1 小时回收
)

# 方案 2: 确保连接正确关闭
from contextlib import contextmanager

@contextmanager
def get_db_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()  # 确保关闭

# 方案 3: 使用连接池事件监控
from sqlalchemy import event

@event.listens_for(engine, "checkout")
def on_checkout(dbapi_conn, connection_record, connection_proxy):
    logger.debug(f"Connection checked out: {id(dbapi_conn)}")

@event.listens_for(engine, "checkin")
def on_checkin(dbapi_conn, connection_record):
    logger.debug(f"Connection checked in: {id(dbapi_conn)}")
```

### 5.2 数据库锁死

#### 5.2.1 SQLite 锁死

**现象**:
```
sqlite3.OperationalError: database is locked
```

**原因**: SQLite 的写锁是全库级别的，并发写入会导致锁死。

**解决方案**:

```python
# 1. 启用 WAL 模式（支持并发读写）
import sqlite3

conn = sqlite3.connect("data/thesis_miner.db")
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=NORMAL")
conn.execute("PRAGMA busy_timeout=5000")  # 5 秒超时
conn.close()

# 2. 配置 SQLAlchemy
engine = create_engine(
    "sqlite:///data/thesis_miner.db",
    connect_args={
        "timeout": 30,  # 30 秒超时
        "check_same_thread": False
    }
)

# 3. 对于高并发场景，迁移到 PostgreSQL
```

#### 5.2.2 PostgreSQL 锁死

**诊断**:

```sql
-- 查看锁等待情况
SELECT 
    l.locktype,
    l.relation::regclass AS table,
    l.transactionid AS tid,
    l.mode,
    l.granted,
    a.usename,
    a.query,
    a.query_start,
    now() - a.query_start AS duration
FROM pg_locks l
JOIN pg_stat_activity a ON l.pid = a.pid
WHERE NOT l.granted
ORDER BY a.query_start;

-- 终止阻塞的会话
SELECT pg_terminate_backend(<pid>);
```

### 5.3 数据库迁移问题

#### 5.3.1 迁移失败

**现象**:
```
alembic.util.exc.CommandError: Can't locate revision identified by 'abc123'
```

**解决方案**:

```bash
# 1. 查看当前迁移状态
alembic current

# 2. 查看迁移历史
alembic history

# 3. 回滚到指定版本
alembic downgrade <revision>

# 4. 重置到初始状态
alembic downgrade base

# 5. 重新迁移
alembic upgrade head
```

#### 5.3.2 数据丢失恢复

```bash
# 1. 立即停止服务，防止数据覆盖
sudo systemctl stop thesis-miner

# 2. 备份当前数据库
cp data/thesis_miner.db data/thesis_miner.db.bak.$(date +%Y%m%d%H%M%S)

# 3. 从备份恢复
cp backups/thesis_miner_20260620.db data/thesis_miner.db

# 4. 验证数据完整性
sqlite3 data/thesis_miner.db "PRAGMA integrity_check;"

# 5. 重启服务
sudo systemctl start thesis-miner
```

### 5.4 数据库性能问题

#### 5.4.1 慢查询诊断

```sql
-- SQLite - 启用慢查询日志
PRAGMA temp_store = MEMORY;
PRAGMA cache_size = -64000;  -- 64MB

-- PostgreSQL - 启用慢查询日志
-- postgresql.conf
-- log_min_duration_statement = 1000  -- 记录超过 1 秒的查询

-- 查看慢查询
SELECT 
    query,
    calls,
    total_time,
    mean_time,
    rows
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;
```

#### 5.4.2 索引优化

```sql
-- 查看缺失索引建议
SELECT 
    schemaname,
    tablename,
    attname,
    n_distinct,
    correlation
FROM pg_stats
WHERE schemaname = 'public'
ORDER BY n_distinct DESC;

-- 创建索引
CREATE INDEX CONCURRENTLY idx_sessions_user_id ON sessions(user_id);
CREATE INDEX CONCURRENTLY idx_sessions_status ON sessions(status);
CREATE INDEX CONCURRENTLY idx_sessions_created_at ON sessions(created_at);

-- 复合索引
CREATE INDEX CONCURRENTLY idx_sessions_user_status 
ON sessions(user_id, status, created_at DESC);
```

---

## 6. 缓存问题

### 6.1 缓存命中率低

#### 6.1.1 诊断

```python
from thesis_miner.cache import CacheManager

cache = CacheManager()

# 查看缓存统计
stats = cache.get_stats()
print(f"Hit rate: {stats['hit_rate']:.2%}")
print(f"Total requests: {stats['total_requests']}")
print(f"Hits: {stats['hits']}")
print(f"Misses: {stats['misses']}")
print(f"Evictions: {stats['evictions']}")
print(f"Current size: {stats['size']}")
print(f"Max size: {stats['max_size']}")
```

#### 6.1.2 解决方案

```python
# 1. 调整 TTL
cache_config = {
    "session_cache_ttl": 1800,      # 30 分钟
    "model_response_ttl": 3600,     # 1 小时
    "search_result_ttl": 7200,      # 2 小时
    "validation_result_ttl": 86400  # 24 小时
}

# 2. 调整缓存大小
cache_config["max_size"] = 10000  # 默认 1000

# 3. 使用更高效的缓存键
def make_cache_key(*args, **kwargs):
    """生成更精确的缓存键"""
    import hashlib
    import json
    key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
    return hashlib.md5(key_data.encode()).hexdigest()

# 4. 预热缓存
async def warmup_cache():
    """预热常用数据到缓存"""
    popular_sessions = await get_popular_sessions()
    for session in popular_sessions:
        await cache.set(f"session:{session.id}", session, ttl=1800)
```

### 6.2 Redis 连接问题

#### 6.2.1 连接超时

**现象**:
```
redis.exceptions.TimeoutError: Timeout connecting to server
```

**解决方案**:

```python
import redis

# 1. 配置连接超时
redis_client = redis.Redis(
    host="redis-host",
    port=6379,
    db=0,
    socket_timeout=5,        # 操作超时 5 秒
    socket_connect_timeout=3, # 连接超时 3 秒
    retry_on_timeout=True,
    retry_on_error=[redis.ConnectionError],
    max_retries=3
)

# 2. 使用连接池
pool = redis.ConnectionPool(
    host="redis-host",
    port=6379,
    max_connections=50,
    socket_timeout=5
)
redis_client = redis.Redis(connection_pool=pool)

# 3. 健康检查
def check_redis_health():
    try:
        return redis_client.ping()
    except redis.ConnectionError:
        return False
```

#### 6.2.2 内存溢出

**现象**:
```
redis.exceptions.ResponseError: OOM command not allowed when used memory > 'maxmemory'
```

**解决方案**:

```bash
# 1. 查看 Redis 内存使用
redis-cli INFO memory | grep used_memory_human

# 2. 配置最大内存和淘汰策略
redis-cli CONFIG SET maxmemory 2gb
redis-cli CONFIG SET maxmemory-policy allkeys-lru

# 3. 查看键分布
redis-cli --bigkeys

# 4. 清理过期键
redis-cli SCAN 0 COUNT 1000 | xargs -L 1 redis-cli TTL
```

---

## 7. Agent 运行问题

### 7.1 Agent 调用超时

#### 7.1.1 现象

```
TimeoutError: Orchestrator stage 'creativity' timed out after 300s
```

#### 7.1.2 诊断

```python
import asyncio
import time

async def diagnose_agent_timeout(agent, input_data):
    """诊断 Agent 超时"""
    start_time = time.time()
    
    try:
        # 设置较短的超时进行测试
        result = await asyncio.wait_for(
            agent.run(input_data),
            timeout=60  # 1 分钟测试
        )
        elapsed = time.time() - start_time
        print(f"Agent completed in {elapsed:.2f}s")
        return result
    except asyncio.TimeoutError:
        elapsed = time.time() - start_time
        print(f"Agent timed out after {elapsed:.2f}s")
        
        # 检查 Agent 状态
        print(f"Agent state: {agent.state}")
        print(f"Messages count: {len(agent.messages)}")
        
        # 检查模型调用
        if hasattr(agent, 'last_model_call'):
            print(f"Last model call: {agent.last_model_call}")
        
        raise
```

#### 7.1.3 解决方案

```python
# 1. 调整超时配置
ORCHESTRATION_TIMEOUT = 600  # 10 分钟
AGENT_TIMEOUT = {
    "orchestrator": 600,
    "searcher": 120,
    "reasoner": 300,
    "critic": 180,
    "mentor": 300,
    "writer": 600
}

# 2. 实现超时降级
async def run_agent_with_fallback(agent, input_data, timeout=300):
    """带降级的 Agent 调用"""
    try:
        return await asyncio.wait_for(
            agent.run(input_data),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        logger.warning(f"Agent {agent.agent_id} timed out, using fallback")
        return await agent.fallback(input_data)

# 3. 流式输出避免长时间等待
async def run_agent_streaming(agent, input_data):
    """流式输出 Agent 结果"""
    async for chunk in agent.run_stream(input_data):
        yield chunk
```

### 7.2 Agent 状态不一致

#### 7.2.1 现象

```
RuntimeError: Agent 'searcher' is in state 'RUNNING' but expected 'IDLE'
```

#### 7.2.2 诊断与修复

```python
from thesis_miner.agents import BaseAgent, AgentState

async def diagnose_agent_state(agent_id: str):
    """诊断 Agent 状态"""
    agent = await get_agent(agent_id)
    
    print(f"Agent ID: {agent.agent_id}")
    print(f"Current state: {agent.state}")
    print(f"Last activity: {agent.last_activity}")
    print(f"Messages count: {len(agent.messages)}")
    
    # 检查是否卡在 RUNNING 状态
    if agent.state == AgentState.RUNNING:
        idle_time = time.time() - agent.last_activity
        print(f"Idle time: {idle_time:.2f}s")
        
        if idle_time > 300:  # 5 分钟无活动
            print("WARNING: Agent stuck in RUNNING state")
            await reset_agent_state(agent_id)

async def reset_agent_state(agent_id: str):
    """重置 Agent 状态"""
    agent = await get_agent(agent_id)
    agent.state = AgentState.IDLE
    agent.messages.clear()
    agent.last_activity = time.time()
    await agent.save()
    logger.info(f"Agent {agent_id} state reset to IDLE")
```

### 7.3 Agent 间通信失败

#### 7.3.1 现象

```
ConnectionError: Failed to send message from Orchestrator to Searcher
```

#### 7.3.2 排查

```python
# 1. 检查 Agent 注册
from thesis_miner.agents import AgentRegistry

registry = AgentRegistry()
registered_agents = registry.list_agents()
print("Registered agents:", registered_agents)

# 2. 检查消息队列
from thesis_miner.messaging import MessageQueue

queue = MessageQueue()
print(f"Queue size: {queue.size()}")
print(f"Pending messages: {queue.pending()}")

# 3. 测试 Agent 通信
async def test_agent_communication():
    """测试 Agent 间通信"""
    orchestrator = get_agent("orchestrator")
    searcher = get_agent("searcher")
    
    # 发送测试消息
    await orchestrator.send_message(
        target="searcher",
        message_type="test",
        data={"test": True}
    )
    
    # 等待响应
    response = await asyncio.wait_for(
        searcher.receive_message(),
        timeout=5
    )
    
    print(f"Communication test: {'PASS' if response else 'FAIL'}")
```

---

## 8. 模型调用问题

### 8.1 API 调用失败

#### 8.1.1 速率限制

**现象**:
```
openai.RateLimitError: Rate limit reached for gpt-4.1. 
Please retry after 20 seconds.
```

**解决方案**:

```python
import asyncio
from typing import Optional

class RateLimitHandler:
    """速率限制处理器"""
    
    def __init__(self):
        self._last_request: Dict[str, float] = {}
        self._min_interval = {
            "openai": 0.5,      # 每秒 2 次
            "anthropic": 0.5,
            "deepseek": 1.0,    # 每秒 1 次
            "google": 0.5
        }
    
    async def wait_if_needed(self, provider: str):
        """必要时等待"""
        min_interval = self._min_interval.get(provider, 1.0)
        last = self._last_request.get(provider, 0)
        now = time.time()
        
        wait_time = min_interval - (now - last)
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        
        self._last_request[provider] = time.time()
    
    async def call_with_retry(self, model_call, provider: str, max_retries: int = 3):
        """带重试的模型调用"""
        for attempt in range(max_retries):
            try:
                await self.wait_if_needed(provider)
                return await model_call()
            except RateLimitError as e:
                wait_time = self._extract_retry_after(e) or (2 ** attempt)
                logger.warning(f"Rate limited, retrying in {wait_time}s (attempt {attempt + 1})")
                await asyncio.sleep(wait_time)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                wait_time = 2 ** attempt
                logger.warning(f"Error: {e}, retrying in {wait_time}s")
                await asyncio.sleep(wait_time)
    
    @staticmethod
    def _extract_retry_after(error) -> Optional[float]:
        """从错误中提取重试时间"""
        if hasattr(error, 'response') and error.response:
            retry_after = error.response.headers.get('Retry-After')
            if retry_after:
                return float(retry_after)
        return None
```

#### 8.1.2 API Key 无效

**现象**:
```
openai.AuthenticationError: Incorrect API key provided
```

**排查**:

```bash
# 1. 检查 API Key 是否设置
echo $OPENAI_API_KEY

# 2. 验证 API Key 有效性
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# 3. 检查 API Key 格式
python -c "
import os
key = os.environ.get('OPENAI_API_KEY', '')
print(f'Key length: {len(key)}')
print(f'Key prefix: {key[:8]}...')
print(f'Valid format: {key.startswith(\"sk-\")}')
"
```

### 8.2 模型响应异常

#### 8.2.1 响应格式错误

**现象**:
```
json.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

**原因**: 模型返回的内容不是有效的 JSON。

**解决方案**:

```python
import json
import re
from typing import Optional, Any

def parse_model_response(response: str) -> Optional[Any]:
    """健壮的模型响应解析"""
    # 1. 尝试直接解析
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass
    
    # 2. 提取 JSON 代码块
    json_pattern = r'```(?:json)?\s*(.*?)\s*```'
    matches = re.findall(json_pattern, response, re.DOTALL)
    for match in matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue
    
    # 3. 查找最外层的花括号
    start = response.find('{')
    end = response.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(response[start:end+1])
        except json.JSONDecodeError:
            pass
    
    # 4. 查找最外层的方括号
    start = response.find('[')
    end = response.rfind(']')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(response[start:end+1])
        except json.JSONDecodeError:
            pass
    
    logger.error(f"Failed to parse model response: {response[:200]}...")
    return None

# 使用示例
response = """
Here is the result:
```json
{"status": "success", "data": [...]}
```
"""
result = parse_model_response(response)
```

#### 8.2.2 响应内容截断

**现象**:
```
Incomplete model response, likely due to max_tokens limit
```

**解决方案**:

```python
async def call_model_with_continuation(
    model_client,
    prompt: str,
    max_tokens: int = 4096,
    max_continuations: int = 3
) -> str:
    """支持续写的模型调用"""
    full_response = ""
    messages = [{"role": "user", "content": prompt}]
    
    for i in range(max_continuations + 1):
        response = await model_client.chat.completions.create(
            model="gpt-4.1",
            messages=messages,
            max_tokens=max_tokens
        )
        
        content = response.choices[0].message.content
        full_response += content
        
        # 检查是否完成
        finish_reason = response.choices[0].finish_reason
        if finish_reason == "stop":
            break
        elif finish_reason == "length":
            # 续写
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": "请继续"})
            logger.info(f"Continuing model response (attempt {i + 1})")
        else:
            break
    
    return full_response
```

### 8.3 模型路由问题

#### 8.3.1 路由到错误的模型

**现象**: 期望使用 GPT-4.1，实际使用了 GPT-4.1-mini。

**诊断**:

```python
from thesis_miner.models import ModelRouter

router = ModelRouter()

# 查看路由决策
decision = router.resolve_model(
    agent_id="reasoner",
    purpose="creativity",
    explicit_model=None
)

print(f"Selected model: {decision.model_id}")
print(f"Source: {decision.source}")  # explicit | step_models | agent_models | default
print(f"Reason: {decision.reason}")
```

#### 8.3.2 解决方案

```python
# 1. 检查路由优先级
# explicit model > step_models[purpose] > agent_models[agent_id] > models[0].id > ai_model

# 2. 配置 step_models
config = {
    "step_models": {
        "info_confirm": "gpt-4.1-mini",    # 信息确认用快速模型
        "creativity": "gpt-4.1",           # 创意生成用强模型
        "validation": "gpt-4.1-mini",      # 验证用快速模型
        "generation": "gpt-4.1",           # 内容生成用强模型
        "deep_assist": "claude-sonnet-4.5" # 深度辅助用 Claude
    }
}

# 3. 配置 agent_models
config = {
    "agent_models": {
        "orchestrator": "gpt-4.1",
        "searcher": "gpt-4.1-mini",
        "reasoner": "gpt-4.1",
        "critic": "gpt-4.1-mini",
        "mentor": "claude-sonnet-4.5",
        "writer": "gpt-4.1"
    }
}

# 4. 显式指定模型
result = await agent.run(
    input_data,
    model="gpt-4.1"  # 显式指定，最高优先级
)
```

---

## 9. API 与网络问题

### 9.1 API 响应慢

#### 9.1.1 诊断

```python
import time
from fastapi import Request

@app.middleware("http")
async def slow_request_logger(request: Request, call_next):
    """记录慢请求"""
    start_time = time.time()
    
    response = await call_next(request)
    
    duration = time.time() - start_time
    if duration > 1.0:  # 超过 1 秒
        logger.warning(
            f"Slow request: {request.method} {request.url.path} "
            f"took {duration:.2f}s"
        )
    
    response.headers["X-Response-Time"] = f"{duration:.3f}"
    return response
```

#### 9.1.2 常见原因与解决

| 原因 | 现象 | 解决方案 |
|------|------|----------|
| 数据库慢查询 | API 响应时间波动大 | 添加索引、优化查询 |
| 模型调用慢 | 特定端点慢 | 使用缓存、异步调用 |
| N+1 查询 | 列表接口慢 | 使用 eager loading |
| 大数据量返回 | 响应体大 | 分页、字段过滤 |
| 网络延迟 | 所有接口慢 | 检查网络、CDN |

```python
# 解决 N+1 查询
from sqlalchemy.orm import selectinload

# 错误 - N+1 查询
sessions = db.query(Session).all()
for session in sessions:
    print(session.user.name)  # 每次都会查询

# 正确 - eager loading
sessions = db.query(Session).options(
    selectinload(Session.user)
).all()
for session in sessions:
    print(session.user.name)  # 不会额外查询

# 分页
@app.get("/api/v1/sessions")
async def list_sessions(
    page: int = 1,
    size: int = 20,
    db: Session = Depends(get_db)
):
    offset = (page - 1) * size
    sessions = db.query(Session).offset(offset).limit(size).all()
    total = db.query(Session).count()
    
    return {
        "items": sessions,
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size
    }
```

### 9.2 CORS 错误

#### 9.2.1 现象

```
Access to fetch at 'http://api.example.com' from origin 'http://app.example.com' 
has been blocked by CORS policy
```

#### 9.2.2 解决方案

```python
from fastapi.middleware.cors import CORSMiddleware

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",           # 开发环境
        "https://app.thesis.example.com",  # 生产环境
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "X-Response-Time"]
)

# 或者在 .env 中配置
# CORS_ORIGINS=["http://localhost:3000","https://app.thesis.example.com"]
```

### 9.3 请求体过大

**现象**:
```
413 Request Entity Too Large
```

**解决方案**:

```python
# 1. 调整 FastAPI 限制
from fastapi import FastAPI, Request

app = FastAPI()

@app.post("/api/v1/upload")
async def upload_file(request: Request):
    # 限制请求体大小
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(413, "File too large")
    
    # 处理上传
    ...

# 2. Nginx 配置
# nginx.conf
# client_max_body_size 10M;

# 3. 使用分块上传
@app.post("/api/v1/upload/chunk")
async def upload_chunk(
    chunk: UploadFile,
    chunk_index: int,
    total_chunks: int,
    file_id: str
):
    # 处理分块
    chunk_path = f"uploads/{file_id}_{chunk_index}"
    with open(chunk_path, "wb") as f:
        f.write(await chunk.read())
    
    # 所有分块上传完成，合并
    if chunk_index == total_chunks - 1:
        await merge_chunks(file_id, total_chunks)
    
    return {"status": "ok", "chunk_index": chunk_index}
```

---

## 10. SSE 与 WebSocket 问题

### 10.1 SSE 连接断开

#### 10.1.1 现象

```
EventSource connection closed unexpectedly
```

#### 10.1.2 常见原因

| 原因 | 检查方法 | 解决方案 |
|------|----------|----------|
| 超时 | 检查 Nginx/Apache 超时配置 | 增加超时时间 |
| 代理缓冲 | 检查代理配置 | 关闭缓冲 |
| 心跳缺失 | 检查心跳配置 | 启用心跳 |
| 网络中断 | 检查网络稳定性 | 实现重连 |

#### 10.1.3 解决方案

```python
from fastapi.responses import StreamingResponse
import asyncio

@app.get("/api/v1/sessions/{session_id}/stream")
async def stream_session(session_id: str):
    async def event_generator():
        last_heartbeat = time.time()
        
        while True:
            # 发送事件
            event = await get_next_event(session_id)
            if event:
                yield f"event: {event.type}\ndata: {json.dumps(event.data)}\n\n"
                last_heartbeat = time.time()
            
            # 心跳
            if time.time() - last_heartbeat > 15:
                yield f"event: heartbeat\ndata: {int(time.time())}\n\n"
                last_heartbeat = time.time()
            
            # 检查是否完成
            if await is_session_complete(session_id):
                yield f"event: done\ndata: {{}}\n\n"
                break
            
            await asyncio.sleep(0.1)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Nginx 不缓冲
        }
    )
```

**Nginx 配置**:

```nginx
location /api/v1/sessions/*/stream {
    proxy_pass http://backend;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_buffering off;           # 关闭缓冲
    proxy_cache off;               # 关闭缓存
    proxy_read_timeout 300s;       # 5 分钟超时
    chunked_transfer_encoding on;
}
```

**前端重连**:

```javascript
class SSEClient {
    constructor(url) {
        this.url = url;
        this.eventSource = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
    }
    
    connect() {
        this.eventSource = new EventSource(this.url);
        
        this.eventSource.onopen = () => {
            console.log('SSE connected');
            this.reconnectAttempts = 0;
            this.reconnectDelay = 1000;
        };
        
        this.eventSource.onerror = (e) => {
            console.error('SSE error:', e);
            this.eventSource.close();
            
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                this.reconnectAttempts++;
                console.log(`Reconnecting in ${this.reconnectDelay}ms (attempt ${this.reconnectAttempts})`);
                
                setTimeout(() => this.connect(), this.reconnectDelay);
                this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30000); // 指数退避
            }
        };
        
        this.eventSource.addEventListener('stage_start', (e) => {
            const data = JSON.parse(e.data);
            console.log('Stage started:', data);
        });
        
        this.eventSource.addEventListener('done', (e) => {
            console.log('Stream completed');
            this.eventSource.close();
        });
    }
    
    disconnect() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }
}
```

### 10.2 WebSocket 连接问题

#### 10.2.1 连接失败

**现象**:
```
WebSocket connection failed: Error during WebSocket handshake: 
Unexpected response code: 400
```

**排查**:

```bash
# 1. 检查 WebSocket 端点
curl -i -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" \
  -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
  http://localhost:8000/ws

# 2. 检查 Nginx 配置
# nginx.conf
location /ws {
    proxy_pass http://backend;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 86400;
}
```

#### 10.2.2 心跳超时

**现象**:
```
WebSocket disconnected: heartbeat timeout
```

**解决方案**:

```python
from fastapi import WebSocket, WebSocketDisconnect
import asyncio

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    
    heartbeat_interval = 30  # 30 秒
    heartbeat_timeout = 90   # 90 秒
    last_heartbeat = time.time()
    
    try:
        while True:
            # 接收消息（带超时）
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=heartbeat_interval
                )
                
                # 处理心跳
                if data == "ping":
                    await websocket.send_text("pong")
                    last_heartbeat = time.time()
                    continue
                
                # 处理业务消息
                result = await process_message(session_id, data)
                await websocket.send_text(json.dumps(result))
                last_heartbeat = time.time()
                
            except asyncio.TimeoutError:
                # 检查心跳超时
                if time.time() - last_heartbeat > heartbeat_timeout:
                    logger.warning(f"WebSocket heartbeat timeout for session {session_id}")
                    break
                
                # 主动发送心跳
                await websocket.send_text("ping")
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await cleanup_session(session_id)
```

---

## 11. 约束规则问题

### 11.1 规则匹配错误

#### 11.1.1 误报（False Positive）

**现象**: 合规的标题被标记为违规。

**诊断**:

```python
from thesis_miner.constraints import RuleEngine, RuleContext

engine = RuleEngine()

# 测试特定规则
title = "基于深度学习的图像识别研究"
context = RuleContext(
    stage="generation",
    granularity="title",
    degree_type="master",
    content=title
)

results = engine.evaluate(context)

for result in results:
    print(f"Rule: {result.rule_id}")
    print(f"Severity: {result.severity}")
    print(f"Message: {result.message}")
    print(f"Passed: {result.passed}")
    print("---")
```

**解决**:

```python
# 1. 调整规则配置
# data/config/constraints/hard_rules.yaml
rules:
  title_length:
    master_max: 25  # 硕士标题最大长度
    doctor_max: 30  # 博士标题最大长度
    enabled: true

# 2. 添加白名单
rules:
  forbidden_verbs:
    blacklist: ["研究", "分析", "探讨"]
    whitelist: ["基于研究", "深入分析"]  # 允许的组合

# 3. 禁用特定规则
rules:
  custom_rule_001:
    enabled: false  # 临时禁用
```

#### 11.1.2 漏报（False Negative）

**现象**: 违规内容未被检测到。

**诊断**:

```python
# 检查规则是否加载
from thesis_miner.constraints import PREDEFINED_RULES

print(f"Loaded rules: {len(PREDEFINED_RULES)}")
for rule in PREDEFINED_RULES:
    print(f"  {rule.id}: {rule.name} ({rule.type})")

# 检查规则链
engine = RuleEngine()
print(f"Rule chain length: {len(engine.rule_chain.rules)}")
```

### 11.2 规则冲突

**现象**:
```
ConflictWarning: Rules 'title_length' and 'title_descriptive' have conflicting requirements
```

**解决**:

```python
from thesis_miner.constraints import ConflictResolver

resolver = ConflictResolver()

# 配置优先级
resolver.set_priority(
    rule_id="title_length",
    priority=100  # 更高优先级
)

resolver.set_priority(
    rule_id="title_descriptive",
    priority=50
)

# 或者配置冲突策略
resolver.set_strategy(
    strategy="strict"  # strict | lenient | custom
)
```

### 11.3 新颖性评分异常

**现象**: 新颖性评分过低或过高。

**诊断**:

```python
from thesis_miner.constraints import NoveltyScorer

scorer = NoveltyScorer()

# 查看评分细节
title = "基于深度学习的图像识别研究"
score = scorer.score(title)

print(f"Total score: {score.total}")
print(f"Cross-discipline: {score.cross_discipline}")
print(f"Method transfer: {score.method_transfer}")
print(f"Pain point: {score.pain_point}")
print(f"Trend forecast: {score.trend_forecast}")
print(f"Details: {score.details}")
```

**调整权重**:

```yaml
# data/config/constraints/novelty_weights.yaml
weights:
  cross_discipline: 0.30      # 跨学科融合
  method_transfer: 0.25       # 方法迁移
  pain_point_breakthrough: 0.25  # 痛点突破
  trend_forecast: 0.20        # 趋势预测

thresholds:
  excellent: 80    # 优秀
  good: 60         # 良好
  pass: 40         # 及格
  fail: 0          # 不及格
```

---

## 12. 性能问题

### 12.1 整体性能优化

#### 12.1.1 性能基准测试

```python
import asyncio
import time
from statistics import mean, median

async def benchmark_api(endpoint: str, concurrent: int = 10, total: int = 100):
    """API 性能基准测试"""
    import aiohttp
    
    response_times = []
    errors = 0
    
    async def make_request(session):
        nonlocal errors
        start = time.time()
        try:
            async with session.get(endpoint) as response:
                await response.read()
                response_times.append(time.time() - start)
        except Exception as e:
            errors += 1
            logger.error(f"Request failed: {e}")
    
    async with aiohttp.ClientSession() as session:
        # 并发请求
        tasks = []
        for _ in range(total):
            tasks.append(make_request(session))
            if len(tasks) >= concurrent:
                await asyncio.gather(*tasks)
                tasks = []
        if tasks:
            await asyncio.gather(*tasks)
    
    print(f"Total requests: {total}")
    print(f"Errors: {errors}")
    print(f"Success rate: {(total - errors) / total * 100:.2f}%")
    print(f"Mean response time: {mean(response_times):.3f}s")
    print(f"Median response time: {median(response_times):.3f}s")
    print(f"Min response time: {min(response_times):.3f}s")
    print(f"Max response time: {max(response_times):.3f}s")
    
    # 百分位
    sorted_times = sorted(response_times)
    p95 = sorted_times[int(len(sorted_times) * 0.95)]
    p99 = sorted_times[int(len(sorted_times) * 0.99)]
    print(f"P95: {p95:.3f}s")
    print(f"P99: {p99:.3f}s")

# 运行基准测试
asyncio.run(benchmark_api("http://localhost:8000/api/v1/sessions", concurrent=20, total=200))
```

#### 12.1.2 性能优化清单

```
┌─────────────────────────────────────────────────────────────┐
│                    性能优化检查清单                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  □ 数据库层                                                  │
│    □ 添加必要的索引                                          │
│    □ 优化慢查询                                              │
│    □ 使用连接池                                              │
│    □ 启用查询缓存                                            │
│    □ 考虑读写分离                                            │
│                                                             │
│  □ 应用层                                                    │
│    □ 启用 Gzip 压缩                                          │
│    □ 使用异步 I/O                                            │
│    □ 实现缓存策略                                            │
│    □ 优化序列化                                              │
│    □ 减少不必要的计算                                        │
│                                                             │
│  □ 模型调用层                                                │
│    □ 使用 Prompt 缓存                                        │
│    □ 批量处理请求                                            │
│    □ 选择合适的模型                                          │
│    □ 实现降级策略                                            │
│    □ 使用流式输出                                            │
│                                                             │
│  □ 网络层                                                    │
│    □ 使用 CDN                                                │
│    □ 启用 HTTP/2                                            │
│    □ 优化 Nginx 配置                                         │
│    □ 使用 Keep-Alive                                        │
│                                                             │
│  □ 基础设施                                                  │
│    □ 增加服务器资源                                          │
│    □ 水平扩展                                                │
│    □ 使用负载均衡                                            │
│    □ 监控资源使用                                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 12.2 内存优化

#### 12.2.1 内存泄漏检测

```python
import tracemalloc
import gc
import objgraph

def detect_memory_leak():
    """检测内存泄漏"""
    tracemalloc.start()
    
    # 记录初始快照
    snapshot1 = tracemalloc.take_snapshot()
    
    # 执行操作
    for _ in range(1000):
        process_session()
    
    # 强制垃圾回收
    gc.collect()
    
    # 记录结束快照
    snapshot2 = tracemalloc.take_snapshot()
    
    # 比较快照
    diff = snapshot2.compare_to(snapshot1, 'lineno')
    
    print("[ Top 10 memory allocations ]")
    for stat in diff[:10]:
        print(stat)
    
    # 查看对象增长
    print("\n[ Object growth ]")
    objgraph.show_growth(limit=10)

# 定期监控
class MemoryMonitor:
    def __init__(self, interval=60):
        self.interval = interval
        self._running = False
    
    async def start(self):
        self._running = True
        tracemalloc.start()
        
        while self._running:
            current, peak = tracemalloc.get_traced_memory()
            logger.info(f"Memory: current={current / 1024 / 1024:.2f}MB, peak={peak / 1024 / 1024:.2f}MB")
            await asyncio.sleep(self.interval)
    
    def stop(self):
        self._running = False
        tracemalloc.stop()
```

#### 12.2.2 内存优化技巧

```python
# 1. 使用生成器避免大列表
def get_sessions_generator(db):
    """使用生成器而非列表"""
    offset = 0
    batch_size = 100
    while True:
        sessions = db.query(Session).offset(offset).limit(batch_size).all()
        if not sessions:
            break
        for session in sessions:
            yield session
        offset += batch_size

# 2. 使用 __slots__ 减少内存
class SessionData:
    __slots__ = ['id', 'title', 'status', 'created_at']
    
    def __init__(self, id, title, status, created_at):
        self.id = id
        self.title = title
        self.status = status
        self.created_at = created_at

# 3. 及时释放大对象
def process_large_data():
    data = load_large_dataset()  # 大对象
    
    try:
        result = process(data)
    finally:
        del data  # 显式释放
        gc.collect()
    
    return result

# 4. 使用弱引用缓存
import weakref

class WeakCache:
    def __init__(self):
        self._cache = weakref.WeakValueDictionary()
    
    def get(self, key):
        return self._cache.get(key)
    
    def set(self, key, value):
        self._cache[key] = value
```

### 12.3 CPU 优化

#### 12.3.1 CPU 密集型任务优化

```python
import multiprocessing
from concurrent.futures import ProcessPoolExecutor

def cpu_intensive_task(data):
    """CPU 密集型任务"""
    result = complex_calculation(data)
    return result

async def process_batch_parallel(data_list: list):
    """并行处理 CPU 密集型任务"""
    cpu_count = multiprocessing.cpu_count()
    
    with ProcessPoolExecutor(max_workers=cpu_count) as executor:
        loop = asyncio.get_event_loop()
        
        tasks = [
            loop.run_in_executor(executor, cpu_intensive_task, data)
            for data in data_list
        ]
        
        results = await asyncio.gather(*tasks)
    
    return results
```

#### 12.3.2 异步 I/O 优化

```python
import asyncio
import aiohttp

async def fetch_multiple_urls(urls: list, max_concurrent: int = 10):
    """并发获取多个 URL"""
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def fetch_one(session, url):
        async with semaphore:
            async with session.get(url) as response:
                return await response.text()
    
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_one(session, url) for url in urls]
        return await asyncio.gather(*tasks)
```

---

## 13. 内存与资源问题

### 13.1 文件描述符耗尽

**现象**:
```
OSError: [Errno 24] Too many open files
```

**诊断**:

```bash
# 1. 查看当前限制
ulimit -n

# 2. 查看进程打开的文件数
lsof -p <PID> | wc -l

# 3. 查看系统限制
cat /proc/sys/fs/file-max
```

**解决方案**:

```bash
# 1. 临时提高限制
ulimit -n 65536

# 2. 永久修改 /etc/security/limits.conf
# * soft nofile 65536
# * hard nofile 65536

# 3. 修改 systemd 服务配置
# /etc/systemd/system/thesis-miner.service
# [Service]
# LimitNOFILE=65536

# 4. 代码层面确保关闭资源
```

```python
# 使用 context manager 确保资源关闭
from contextlib import contextmanager

@contextmanager
def open_file_safely(path, mode='r'):
    f = open(path, mode)
    try:
        yield f
    finally:
        f.close()

# 使用 asynccontextmanager
from contextlib import asynccontextmanager

@asynccontextmanager
async def open_db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        await session.close()
```

### 13.2 磁盘空间不足

**现象**:
```
OSError: [Errno 28] No space left on device
```

**诊断与清理**:

```bash
# 1. 查看磁盘使用
df -h

# 2. 查看大文件
find /var/log -type f -size +100M -exec ls -lh {} \;

# 3. 清理日志
# 保留最近 7 天的日志
find logs/ -name "*.log" -mtime +7 -delete

# 4. 清理临时文件
find /tmp -name "thesis_miner_*" -mtime +1 -delete

# 5. 清理数据库 WAL 文件
sqlite3 data/thesis_miner.db "PRAGMA wal_checkpoint(TRUNCATE);"

# 6. 清理 Redis
redis-cli FLUSHDB  # 谨慎使用
```

**自动清理脚本**:

```python
import os
import time
from pathlib import Path

class DiskCleaner:
    """磁盘清理工具"""
    
    def __init__(self, paths: dict):
        self.paths = paths  # {path: max_age_days}
    
    def clean(self):
        """执行清理"""
        total_freed = 0
        
        for path, max_age in self.paths.items():
            freed = self._clean_path(path, max_age)
            total_freed += freed
            logger.info(f"Cleaned {path}: freed {freed / 1024 / 1024:.2f}MB")
        
        logger.info(f"Total freed: {total_freed / 1024 / 1024:.2f}MB")
        return total_freed
    
    def _clean_path(self, path: str, max_age_days: int) -> int:
        """清理指定路径"""
        freed = 0
        cutoff = time.time() - max_age_days * 86400
        
        for root, dirs, files in os.walk(path):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    if os.path.getmtime(file_path) < cutoff:
                        size = os.path.getsize(file_path)
                        os.remove(file_path)
                        freed += size
                except OSError as e:
                    logger.warning(f"Failed to remove {file_path}: {e}")
        
        return freed

# 配置
cleaner = DiskCleaner({
    "logs/": 7,           # 日志保留 7 天
    "data/cache/": 1,     # 缓存保留 1 天
    "data/temp/": 1,      # 临时文件保留 1 天
})

# 每天执行一次
import schedule
schedule.every().day.at("03:00").do(cleaner.clean)
```

---

## 14. 安全与认证问题

### 14.1 JWT 认证失败

#### 14.1.1 现象

```
401 Unauthorized: Invalid or expired token
```

#### 14.1.2 诊断

```python
import jwt
from datetime import datetime

def diagnose_jwt(token: str, secret_key: str):
    """诊断 JWT 问题"""
    try:
        # 1. 解码（不验证签名）
        header = jwt.get_unverified_header(token)
        print(f"Algorithm: {header['alg']}")
        print(f"Type: {header.get('typ')}")
        
        # 2. 解码 payload（不验证）
        payload = jwt.decode(token, options={"verify_signature": False})
        print(f"Issued at: {datetime.fromtimestamp(payload['iat'])}")
        print(f"Expires at: {datetime.fromtimestamp(payload['exp'])}")
        print(f"User ID: {payload.get('sub')}")
        
        # 3. 检查是否过期
        now = datetime.now().timestamp()
        if payload['exp'] < now:
            print(f"STATUS: EXPIRED (expired {now - payload['exp']:.0f}s ago)")
        else:
            print(f"STATUS: VALID (expires in {payload['exp'] - now:.0f}s)")
        
        # 4. 验证签名
        try:
            jwt.decode(token, secret_key, algorithms=["HS256"])
            print("SIGNATURE: VALID")
        except jwt.InvalidSignatureError:
            print("SIGNATURE: INVALID")
        
    except jwt.DecodeError as e:
        print(f"DECODE ERROR: {e}")
```

#### 14.1.3 解决方案

```python
# 1. 刷新 token
@app.post("/api/v1/auth/refresh")
async def refresh_token(refresh_token: str):
    try:
        payload = jwt.decode(
            refresh_token,
            SECRET_KEY,
            algorithms=["HS256"]
        )
        
        # 检查是否是 refresh token
        if payload.get("type") != "refresh":
            raise HTTPException(400, "Invalid token type")
        
        # 生成新的 access token
        new_token = create_access_token({"sub": payload["sub"]})
        
        return {"access_token": new_token, "token_type": "bearer"}
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")

# 2. 处理过期 token
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/v1/auth"):
        return await call_next(request)
    
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    
    if not token:
        return await call_next(request)
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        request.state.user_id = payload["sub"]
    except jwt.ExpiredSignatureError:
        return JSONResponse(
            status_code=401,
            content={"detail": "Token expired", "code": "TOKEN_EXPIRED"}
        )
    except jwt.InvalidTokenError:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid token", "code": "TOKEN_INVALID"}
        )
    
    return await call_next(request)
```

### 14.2 SQL 注入防护

**现象**: 安全扫描发现 SQL 注入风险。

**排查**:

```python
# 危险 - 直接拼接 SQL
def dangerous_query(user_input: str):
    query = f"SELECT * FROM sessions WHERE title = '{user_input}'"
    return db.execute(query)

# 安全 - 使用参数化查询
def safe_query(user_input: str):
    query = "SELECT * FROM sessions WHERE title = :title"
    return db.execute(query, {"title": user_input})

# 安全 - 使用 ORM
def safe_orm_query(user_input: str):
    return db.query(Session).filter(Session.title == user_input).all()
```

### 14.3 XSS 防护

```python
import bleach
from markdown import markdown

def sanitize_html(content: str) -> str:
    """清理 HTML 内容"""
    allowed_tags = ['p', 'br', 'strong', 'em', 'ul', 'ol', 'li', 'code', 'pre']
    allowed_attrs = {'code': ['class'], 'pre': ['class']}
    
    return bleach.clean(
        content,
        tags=allowed_tags,
        attributes=allowed_attrs,
        strip=True
    )

def safe_markdown_to_html(md_content: str) -> str:
    """安全的 Markdown 转 HTML"""
    html = markdown(md_content, extensions=['codehilite', 'fenced_code'])
    return sanitize_html(html)
```

---

## 15. 日志与监控

### 15.1 日志配置

#### 15.1.1 日志配置示例

```python
import logging
import logging.handlers
from pathlib import Path

def setup_logging(settings):
    """配置日志系统"""
    log_dir = Path(settings.LOG_FILE).parent
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # 根 logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL))
    
    # 控制台 handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_format)
    
    # 文件 handler（按大小轮转）
    file_handler = logging.handlers.RotatingFileHandler(
        settings.LOG_FILE,
        maxBytes=settings.LOG_MAX_SIZE,
        backupCount=settings.LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )
    file_handler.setFormatter(file_format)
    
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # 第三方库日志级别
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
```

#### 15.1.2 结构化日志

```python
import json
import logging

class JSONFormatter(logging.Formatter):
    """JSON 格式日志"""
    
    def format(self, record):
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
            "function": record.funcName
        }
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # 添加额外字段
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno',
                          'pathname', 'filename', 'module', 'exc_info',
                          'exc_text', 'stack_info', 'lineno', 'funcName',
                          'created', 'msecs', 'relativeCreated', 'thread',
                          'threadName', 'processName', 'process', 'getMessage']:
                log_data[key] = value
        
        return json.dumps(log_data, ensure_ascii=False, default=str)

# 使用
logger = logging.getLogger("thesis_miner")
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)

logger.info("Session created", extra={
    "session_id": "sess_abc123",
    "user_id": "user_001",
    "stage": "info_confirm"
})
```

### 15.2 健康检查

#### 15.2.1 健康检查端点

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import redis
import time

router = APIRouter()

@router.get("/health")
async def health_check():
    """基础健康检查"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "8.0.0"
    }

@router.get("/health/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    """详细健康检查"""
    checks = {}
    overall_healthy = True
    
    # 1. 数据库检查
    try:
        db.execute("SELECT 1")
        checks["database"] = {"status": "healthy", "latency_ms": 0}
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False
    
    # 2. Redis 检查
    try:
        redis_client = redis.from_url(REDIS_URL)
        start = time.time()
        redis_client.ping()
        latency = (time.time() - start) * 1000
        checks["redis"] = {"status": "healthy", "latency_ms": round(latency, 2)}
    except Exception as e:
        checks["redis"] = {"status": "unhealthy", "error": str(e)}
        # Redis 不健康不影响整体
    
    # 3. 磁盘空间检查
    disk_usage = get_disk_usage()
    checks["disk"] = {
        "status": "healthy" if disk_usage["percent"] < 90 else "warning",
        "used_percent": disk_usage["percent"],
        "free_gb": disk_usage["free_gb"]
    }
    
    # 4. 内存检查
    mem_usage = get_memory_usage()
    checks["memory"] = {
        "status": "healthy" if mem_usage["percent"] < 90 else "warning",
        "used_percent": mem_usage["percent"]
    }
    
    # 5. Agent 状态检查
    agent_status = await check_agents_health()
    checks["agents"] = agent_status
    
    return {
        "status": "healthy" if overall_healthy else "degraded",
        "timestamp": time.time(),
        "checks": checks
    }
```

### 15.3 Prometheus 监控

```python
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from fastapi import APIRouter, Response

# 指标定义
REQUEST_COUNT = Counter(
    'thesis_miner_requests_total',
    'Total request count',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'thesis_miner_request_duration_seconds',
    'Request duration in seconds',
    ['method', 'endpoint']
)

ACTIVE_SESSIONS = Gauge(
    'thesis_miner_active_sessions',
    'Number of active sessions'
)

MODEL_CALLS = Counter(
    'thesis_miner_model_calls_total',
    'Total model API calls',
    ['model', 'status']
)

MODEL_LATENCY = Histogram(
    'thesis_miner_model_call_duration_seconds',
    'Model API call duration',
    ['model']
)

router = APIRouter()

@router.get("/metrics")
async def metrics():
    """Prometheus 指标端点"""
    return Response(generate_latest(), media_type="text/plain")

# 中间件收集指标
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    
    response = await call_next(request)
    
    duration = time.time() - start_time
    endpoint = request.url.path
    method = request.method
    status = response.status_code
    
    REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
    REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)
    
    return response
```

---

## 16. 常见错误码速查

### 16.1 HTTP 状态码

| 状态码 | 名称 | 含义 | 常见原因 |
|--------|------|------|----------|
| 200 | OK | 请求成功 | - |
| 201 | Created | 资源创建成功 | POST 创建资源 |
| 204 | No Content | 成功但无内容 | DELETE 成功 |
| 400 | Bad Request | 请求参数错误 | 参数缺失、格式错误 |
| 401 | Unauthorized | 未认证 | Token 缺失或无效 |
| 403 | Forbidden | 无权限 | 权限不足 |
| 404 | Not Found | 资源不存在 | ID 错误 |
| 409 | Conflict | 资源冲突 | 重复创建 |
| 413 | Payload Too Large | 请求体过大 | 上传文件超限 |
| 422 | Unprocessable Entity | 实体验证失败 | 字段验证不通过 |
| 429 | Too Many Requests | 请求过多 | 触发限流 |
| 500 | Internal Server Error | 服务器内部错误 | 代码异常 |
| 502 | Bad Gateway | 网关错误 | 上游服务异常 |
| 503 | Service Unavailable | 服务不可用 | 维护中、过载 |
| 504 | Gateway Timeout | 网关超时 | 上游服务超时 |

### 16.2 业务错误码

| 错误码 | 名称 | HTTP 状态 | 说明 |
|--------|------|-----------|------|
| TM-001 | SESSION_NOT_FOUND | 404 | Session 不存在 |
| TM-002 | SESSION_EXPIRED | 401 | Session 已过期 |
| TM-003 | SESSION_LIMIT_EXCEEDED | 429 | 超过并发 Session 限制 |
| TM-004 | STAGE_INVALID | 400 | 无效的阶段 |
| TM-005 | STAGE_TRANSITION_FAILED | 409 | 阶段转换失败 |
| TM-006 | VALIDATION_FAILED | 422 | 验证不通过 |
| TM-007 | AGENT_NOT_FOUND | 404 | Agent 不存在 |
| TM-008 | AGENT_TIMEOUT | 504 | Agent 调用超时 |
| TM-009 | MODEL_NOT_FOUND | 404 | 模型不存在 |
| TM-010 | MODEL_API_ERROR | 502 | 模型 API 调用失败 |
| TM-011 | MODEL_RATE_LIMITED | 429 | 模型 API 限流 |
| TM-012 | RULE_VIOLATION | 422 | 规则违反 |
| TM-013 | CACHE_ERROR | 500 | 缓存错误 |
| TM-014 | DATABASE_ERROR | 500 | 数据库错误 |
| TM-015 | CONFIG_ERROR | 500 | 配置错误 |
| TM-016 | AUTHENTICATION_FAILED | 401 | 认证失败 |
| TM-017 | PERMISSION_DENIED | 403 | 权限不足 |
| TM-018 | RATE_LIMIT_EXCEEDED | 429 | API 限流 |
| TM-019 | INTERNAL_ERROR | 500 | 内部错误 |
| TM-020 | SERVICE_UNAVAILABLE | 503 | 服务不可用 |

### 16.3 错误响应格式

```json
{
  "error": {
    "code": "TM-006",
    "message": "Validation failed",
    "details": [
      {
        "field": "title",
        "rule": "title_length",
        "message": "Title exceeds maximum length of 25 characters"
      }
    ],
    "request_id": "req_abc123",
    "timestamp": "2026-06-20T14:00:00Z"
  }
}
```

### 16.4 错误处理最佳实践

```python
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
import time
import uuid

class ThesisMinerError(Exception):
    """ThesisMiner 基础异常"""
    def __init__(self, code: str, message: str, status_code: int = 500, details=None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or []
        super().__init__(message)

@app.exception_handler(ThesisMinerError)
async def thesis_miner_error_handler(request: Request, exc: ThesisMinerError):
    """统一错误处理"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "request_id": str(uuid.uuid4()),
                "timestamp": time.time()
            }
        }
    )

@app.exception_handler(Exception)
async def general_error_handler(request: Request, exc: Exception):
    """通用错误处理"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "TM-019",
                "message": "Internal server error",
                "request_id": str(uuid.uuid4()),
                "timestamp": time.time()
            }
        }
    )
```

---

## 17. 调试技巧与工具

### 17.1 Python 调试器

#### 17.1.1 使用 pdb

```python
import pdb

def problematic_function(data):
    result = process(data)
    pdb.set_trace()  # 设置断点
    # 在这里可以交互式调试
    # n - 执行下一行
    # s - 步入函数
    # c - 继续执行
    # p variable - 打印变量
    # l - 查看代码
    # q - 退出
    return result
```

#### 17.1.2 使用 ipdb (增强版)

```bash
pip install ipdb
```

```python
import ipdb

def debug_function():
    ipdb.set_trace()
    # ipdb 提供语法高亮和自动补全
```

#### 17.1.3 条件断点

```python
def process_sessions(sessions):
    for i, session in enumerate(sessions):
        # 只在特定条件断下
        if session.id == "sess_problem":
            breakpoint()  # Python 3.7+
        
        process(session)
```

### 17.2 VS Code 调试配置

`.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "ThesisMiner API",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["app.main:app", "--reload", "--port", "8000"],
      "env": {
        "ENVIRONMENT": "development",
        "DEBUG": "true"
      },
      "justMyCode": false
    },
    {
      "name": "Run Tests",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": ["-v", "--pdb"],
      "justMyCode": false
    },
    {
      "name": "Debug Current File",
      "type": "python",
      "request": "launch",
      "program": "${file}",
      "console": "integratedTerminal",
      "justMyCode": false
    }
  ]
}
```

### 17.3 性能分析工具

#### 17.3.1 py-spy (采样分析器)

```bash
# 安装
pip install py-spy

# 实时查看
py-spy top --pid <PID>

# 生成火焰图
py-spy record --pid <PID> --output flame.svg

# dump 调用栈
py-spy dump --pid <PID>
```

#### 17.3.2 memory-profiler

```bash
pip install memory-profiler
```

```python
from memory_profiler import profile

@profile
def memory_intensive_function():
    a = [1] * (10 ** 6)
    b = [2] * (2 * 10 ** 7)
    del b
    return a

memory_intensive_function()
```

```bash
# 运行
python -m memory_profiler script.py
```

### 17.4 网络调试

#### 17.4.1 使用 mitmproxy

```bash
# 安装
pip install mitmproxy

# 启动代理
mitmproxy --listen-port 8080

# 配置应用使用代理
export HTTP_PROXY=http://localhost:8080
export HTTPS_PROXY=http://localhost:8080
```

#### 17.4.2 使用 tcpdump

```bash
# 捕获 HTTP 流量
sudo tcpdump -i any -A -s 0 'tcp port 8000 and (((ip[2:2] - ((ip[0]&0xf)<<2)) - ((tcp[12]&0xf0)>>2)) != 0)'

# 捕获并保存
sudo tcpdump -i any -w capture.pcap port 8000

# 读取 pcap 文件
tcpdump -r capture.pcap -A
```

### 17.5 数据库调试

#### 17.5.1 SQL 日志

```python
import logging

# 启用 SQL 日志
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# 或者配置
engine = create_engine(
    DATABASE_URL,
    echo=True,  # 打印所有 SQL
    echo_pool=True  # 打印连接池事件
)
```

#### 17.5.2 查询分析

```sql
-- PostgreSQL - 查询执行计划
EXPLAIN ANALYZE
SELECT * FROM sessions WHERE user_id = 'user_001';

-- SQLite - 查询计划
EXPLAIN QUERY PLAN
SELECT * FROM sessions WHERE user_id = 'user_001';
```

---

## 18. 附录

### 18.1 常用命令速查

```bash
# 服务管理
python -m thesis_miner start              # 启动服务
python -m thesis_miner stop               # 停止服务
python -m thesis_miner restart            # 重启服务
python -m thesis_miner status             # 查看状态

# 数据库
python -m thesis_miner db init            # 初始化数据库
python -m thesis_miner db migrate         # 运行迁移
python -m thesis_miner db backup          # 备份数据库
python -m thesis_miner db restore <file>  # 恢复数据库

# 配置
python -m thesis_miner config show        # 显示配置
python -m thesis_miner config validate    # 校验配置
python -m thesis_miner config export      # 导出配置

# 诊断
python -m thesis_miner diagnose           # 运行诊断
python -m thesis_miner health             # 健康检查
python -m thesis_miner benchmark          # 性能测试

# 日志
python -m thesis_miner logs tail          # 实时日志
python -m thesis_miner logs search <text> # 搜索日志
python -m thesis_miner logs clean         # 清理旧日志
```

### 18.2 环境检查脚本

```python
#!/usr/bin/env python3
"""环境检查脚本"""

import sys
import platform
import importlib
from pathlib import Path

def check_environment():
    """检查运行环境"""
    print("=" * 60)
    print("ThesisMiner Environment Check")
    print("=" * 60)
    
    # Python 版本
    print(f"\n[Python]")
    print(f"  Version: {sys.version}")
    print(f"  Executable: {sys.executable}")
    print(f"  Platform: {platform.platform()}")
    
    # 必需包检查
    print(f"\n[Required Packages]")
    required_packages = [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("sqlalchemy", "sqlalchemy"),
        ("pydantic", "pydantic"),
        ("redis", "redis"),
        ("httpx", "httpx"),
        ("openai", "openai"),
        ("anthropic", "anthropic"),
    ]
    
    for package_name, import_name in required_packages:
        try:
            module = importlib.import_module(import_name)
            version = getattr(module, "__version__", "unknown")
            print(f"  ✓ {package_name}: {version}")
        except ImportError:
            print(f"  ✗ {package_name}: NOT INSTALLED")
    
    # 配置文件检查
    print(f"\n[Configuration Files]")
    config_files = [
        ".env",
        "data/config.json",
        "data/config/system.yaml",
        "data/config/models.yaml",
    ]
    
    for file_path in config_files:
        path = Path(file_path)
        if path.exists():
            print(f"  ✓ {file_path}")
        else:
            print(f"  ✗ {file_path}: NOT FOUND")
    
    # 数据库检查
    print(f"\n[Database]")
    db_path = Path("data/thesis_miner.db")
    if db_path.exists():
        size_mb = db_path.stat().st_size / 1024 / 1024
        print(f"  ✓ SQLite database: {size_mb:.2f}MB")
    else:
        print(f"  ✗ SQLite database: NOT FOUND")
    
    # 目录检查
    print(f"\n[Directories]")
    directories = ["data", "logs", "data/config", "data/cache"]
    for dir_path in directories:
        path = Path(dir_path)
        if path.exists() and path.is_dir():
            print(f"  ✓ {dir_path}/")
        else:
            print(f"  ✗ {dir_path}/: NOT FOUND")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    check_environment()
```

### 18.3 FAQ

#### Q1: 如何重置管理员密码？

```bash
python -m thesis_miner reset-password --user admin
```

#### Q2: 如何查看当前活跃的 Session？

```bash
# 通过 API
curl http://localhost:8000/api/v1/sessions?status=active

# 通过数据库
sqlite3 data/thesis_miner.db "SELECT id, user_id, status, created_at FROM sessions WHERE status = 'active';"
```

#### Q3: 如何清理过期的 Session？

```bash
python -m thesis_miner cleanup sessions --expired
```

#### Q4: 如何导出所有配置？

```bash
python -m thesis_miner config export --format json --output config_backup.json
```

#### Q5: 如何切换模型提供商？

```bash
# 1. 修改 config.json
{
  "models": [
    {
      "id": "claude-sonnet-4.5",
      "provider": "anthropic",
      "api_key_env": "ANTHROPIC_API_KEY"
    }
  ]
}

# 2. 设置 API Key
export ANTHROPIC_API_KEY="sk-ant-your-key"

# 3. 重启服务
python -m thesis_miner restart
```

#### Q6: 如何监控模型调用成本？

```python
from thesis_miner.monitoring import CostMonitor

monitor = CostMonitor()
stats = monitor.get_stats(period="24h")

print(f"Total cost: ${stats['total_cost']:.2f}")
print(f"Total tokens: {stats['total_tokens']}")
for model, cost in stats['by_model'].items():
    print(f"  {model}: ${cost:.2f}")
```

#### Q7: 如何处理数据库锁死？

```bash
# SQLite
sqlite3 data/thesis_miner.db "PRAGMA wal_checkpoint(TRUNCATE);"
sqlite3 data/thesis_miner.db "PRAGMA journal_mode=DELETE;"
sqlite3 data/thesis_miner.db "PRAGMA journal_mode=WAL;"

# PostgreSQL
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction';
```

#### Q8: 如何调试 Agent 决策过程？

```python
# 启用 Agent 调试日志
import logging
logging.getLogger("thesis_miner.agents").setLevel(logging.DEBUG)

# 或者使用 trace 模式
python -m thesis_miner run --trace --session-id sess_abc123
```

### 18.4 紧急恢复流程

```
┌─────────────────────────────────────────────────────────────┐
│                    紧急恢复流程                                │
└─────────────────────────────────────────────────────────────┘

  ┌─────────────────┐
  │  1. 确认故障     │
  │  (监控告警)      │
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │  2. 评估影响     │
  │  (用户数/功能)   │
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐     ┌─────────────────┐
  │  3. 紧急止血     │ ──▶ │  • 重启服务      │
  │  (恢复服务)      │     │  • 回滚版本      │
  └────────┬────────┘     │  • 切换备用      │
           │              └─────────────────┘
           ▼
  ┌─────────────────┐
  │  4. 根因分析     │
  │  (日志/监控)     │
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │  5. 修复验证     │
  │  (测试/灰度)     │
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │  6. 复盘总结     │
  │  (文档/改进)     │
  └─────────────────┘
```

### 18.5 联系支持

| 渠道 | 用途 | 响应时间 |
|------|------|----------|
| GitHub Issues | Bug 报告、功能请求 | 24-48 小时 |
| 官方文档 | 使用指南、API 参考 | - |
| 社区论坛 | 使用问题讨论 | 社区驱动 |
| 紧急支持 | 生产环境故障 | 2-4 小时 |

### 18.6 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v8.0.0 | 2026-06-20 | 初始版本 |
| v7.5.0 | 2026-05-15 | 添加 Docker 部署章节 |
| v7.0.0 | 2026-04-01 | 重构故障排查流程 |
| v6.0.0 | 2026-02-10 | 添加监控告警章节 |

---

> **文档结束**
> 
> 如有疑问，请参考相关文档或提交 Issue。