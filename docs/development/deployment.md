# ThesisMiner v8.0 部署指南

> 版本：v8.0 | 更新日期：2026-06-19 | 适用范围：运维人员与系统管理员

本文档详细说明 ThesisMiner v8.0 的部署方式，涵盖本地开发部署、Docker 容器化部署、生产环境部署三种模式，以及配置管理、数据备份、监控告警与故障排查等运维事项。

---

## 目录

1. [部署架构总览](#1-部署架构总览)
2. [环境要求](#2-环境要求)
3. [本地开发部署](#3-本地开发部署)
4. [Docker 容器化部署](#4-docker-容器化部署)
5. [生产环境部署](#5-生产环境部署)
6. [配置管理](#6-配置管理)
7. [数据库管理](#7-数据库管理)
8. [AI 模型 API Key 配置](#8-ai-模型-api-key-配置)
9. [反向代理与 HTTPS](#9-反向代理与-https)
10. [监控与告警](#10-监控与告警)
11. [数据备份与恢复](#11-数据备份与恢复)
12. [性能调优](#12-性能调优)
13. [故障排查](#13-故障排查)
14. [升级与回滚](#14-升级与回滚)

---

## 1. 部署架构总览

ThesisMiner v8.0 采用单体应用架构，后端 FastAPI 服务同时托管前端静态资源与 API 接口。

```
                    ┌─────────────────────────┐
                    │      用户浏览器          │
                    └────────────┬────────────┘
                                 │ HTTPS
                    ┌────────────▼────────────┐
                    │   Nginx 反向代理         │
                    │   （TLS 终止 + 静态缓存）│
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   ThesisMiner 后端       │
                    │   （FastAPI + Uvicorn）  │
                    │   ├─ 多 Agent 编排       │
                    │   ├─ 五阶段约束引擎      │
                    │   └─ 会话/对话管理       │
                    └──┬─────────────┬────────┘
                       │             │
              ┌────────▼──┐   ┌──────▼──────────┐
              │  SQLite   │   │  外部 AI 模型 API │
              │  /PostgreSQL│  │  （DeepSeek 等） │
              └───────────┘   └─────────────────┘
```

### 组件说明

| 组件 | 说明 | 默认端口 |
|------|------|----------|
| ThesisMiner 后端 | FastAPI 应用，含 API 与前端托管 | 8000 |
| 数据库 | SQLite（默认）或 PostgreSQL（生产） | - |
| Nginx | 反向代理，TLS 终止，静态资源缓存 | 80/443 |

---

## 2. 环境要求

### 硬件要求

| 部署规模 | CPU | 内存 | 磁盘 | 适用场景 |
|----------|-----|------|------|----------|
| 最小 | 2 核 | 2 GB | 10 GB | 个人/测试 |
| 推荐 | 4 核 | 4 GB | 50 GB | 小团队 |
| 生产 | 8 核 | 8 GB | 100 GB+ | 机构级 |

### 软件要求

- **操作系统**：Linux（Ubuntu 22.04 LTS 推荐）、Windows Server 2019+
- **Python**：3.11 或更高版本
- **Docker**：24+（容器化部署）
- **Nginx**：1.22+（生产反向代理）
- **PostgreSQL**：15+（生产数据库，可选）

---

## 3. 本地开发部署

适用于开发与测试环境。

### 步骤

1. **克隆代码**

   ```bash
   git clone https://github.com/your-org/ThesisMiner.git
   cd ThesisMiner
   ```

2. **创建虚拟环境并安装依赖**

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Linux
   # .venv\Scripts\activate    # Windows
   pip install -r requirements.txt
   ```

3. **配置环境变量**

   复制 `.env.example` 为 `.env` 并填写配置（见 [配置管理](#6-配置管理) 章节）。

4. **初始化数据库**

   ```bash
   python -c "from backend.database import init_db; init_db()"
   ```

5. **启动服务**

   ```bash
   python main.py
   ```

   服务启动后访问 `http://localhost:8000`。

---

## 4. Docker 容器化部署

### Dockerfile

项目根目录的 `Dockerfile`：

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 构建镜像

```bash
docker build -t thesisminer:8.0 .
```

### 运行容器

```bash
docker run -d \
  --name thesisminer \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/.env:/app/.env:ro \
  --restart unless-stopped \
  thesisminer:8.0
```

### docker-compose 部署

`docker-compose.yml`：

```yaml
version: "3.8"
services:
  thesisminer:
    image: thesisminer:8.0
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./.env:/app/.env:ro
    environment:
      - PYTHONUNBUFFERED=1
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

启动：

```bash
docker-compose up -d
```

查看日志：

```bash
docker-compose logs -f thesisminer
```

---

## 5. 生产环境部署

### 使用 systemd 部署（Linux）

1. **安装依赖**

   ```bash
   sudo apt update
   sudo apt install python3.11 python3.11-venv nginx
   ```

2. **创建系统用户**

   ```bash
   sudo useradd -r -s /bin/false thesisminer
   sudo mkdir -p /opt/thesisminer
   sudo chown thesisminer:thesisminer /opt/thesisminer
   ```

3. **部署代码**

   ```bash
   sudo -u thesisminer git clone https://github.com/your-org/ThesisMiner.git /opt/thesisminer/app
   cd /opt/thesisminer/app
   sudo -u thesisminer python3.11 -m venv .venv
   sudo -u thesisminer .venv/bin/pip install -r requirements.txt
   ```

4. **配置 systemd 服务**

   `/etc/systemd/system/thesisminer.service`：

   ```ini
   [Unit]
   Description=ThesisMiner v8.0 Service
   After=network.target

   [Service]
   Type=simple
   User=thesisminer
   WorkingDirectory=/opt/thesisminer/app
   EnvironmentFile=/opt/thesisminer/app/.env
   ExecStart=/opt/thesisminer/app/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 4
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```

5. **启动服务**

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable thesisminer
   sudo systemctl start thesisminer
   sudo systemctl status thesisminer
   ```

### 使用 Gunicorn + Uvicorn Worker（生产推荐）

```bash
gunicorn main:app \
  -w 4 \
  -k uvicorn.workers.UvicornWorker \
  --bind 127.0.0.1:8000 \
  --timeout 120 \
  --keep-alive 5
```

`-w 4` 表示 4 个工作进程，建议设置为 CPU 核心数的 2-4 倍。

---

## 6. 配置管理

所有配置通过环境变量管理，`.env` 文件示例：

```env
# 应用配置
APP_VERSION=8.0.0
DEBUG=false
SECRET_KEY=请替换为随机长字符串

# 数据库配置
DATABASE_URL=sqlite:///./data/thesisminer.db
# 生产环境推荐 PostgreSQL：
# DATABASE_URL=postgresql://user:pass@localhost:5432/thesisminer

# 服务配置
HOST=0.0.0.0
PORT=8000
WORKERS=4

# AI 模型 API Key（按需配置）
DEEPSEEK_API_KEY=sk-xxx
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx
GOOGLE_API_KEY=xxx
DASHSCOPE_API_KEY=xxx
VOLCENGINE_API_KEY=xxx
ZHIPU_API_KEY=xxx

# DeepSeek 缓存配置
CACHE_PREFIX_ENABLED=true
CACHE_HIT_RATE_TARGET=0.95

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=./data/logs/thesisminer.log
```

### 敏感信息保护

- `.env` 文件权限设置为 `600`（仅所有者可读写）
- 不要将 `.env` 提交到 Git 仓库（已在 `.gitignore` 中排除）
- 生产环境推荐使用密钥管理服务（如 Vault、AWS Secrets Manager）

---

## 7. 数据库管理

### SQLite（默认）

数据文件位于 `data/thesisminer.db`，无需额外配置。

### PostgreSQL（生产推荐）

1. **创建数据库与用户**

   ```bash
   sudo -u postgres psql
   CREATE DATABASE thesisminer;
   CREATE USER thesisminer_user WITH PASSWORD '强密码';
   GRANT ALL PRIVILEGES ON DATABASE thesisminer TO thesisminer_user;
   \q
   ```

2. **配置连接字符串**

   ```env
   DATABASE_URL=postgresql://thesisminer_user:强密码@localhost:5432/thesisminer
   ```

3. **初始化表结构**

   ```bash
   python -c "from backend.database import init_db; init_db()"
   ```

### 数据库迁移

版本升级时运行迁移脚本兼容旧库：

```bash
python -c "from backend.database import migrate_db; migrate_db()"
```

---

## 8. AI 模型 API Key 配置

ThesisMiner v8.0 支持 10 个模型，按需配置对应 API Key：

| 模型 | 提供商 | 环境变量 | 用途 |
|------|--------|----------|------|
| claude-sonnet-4.5 | Anthropic | `ANTHROPIC_API_KEY` | Orchestrator 主管理 |
| claude-opus-4.5 | Anthropic | `ANTHROPIC_API_KEY` | Writer 报告生成 |
| deepseek-v3.2 | DeepSeek | `DEEPSEEK_API_KEY` | Searcher 检索 |
| deepseek-r2 | DeepSeek | `DEEPSEEK_API_KEY` | Reasoner/Critic 推理评审 |
| gpt-4.1 | OpenAI | `OPENAI_API_KEY` | Mentor 导师模拟 |
| qwen3-max | 阿里通义 | `DASHSCOPE_API_KEY` | 创意启发 |
| gemini-2.5-pro | Google | `GOOGLE_API_KEY` | 备选推理 |
| glm-4.6 | 智谱 | `ZHIPU_API_KEY` | 备选推理 |
| doubao-1.5-pro | 火山引擎 | `VOLCENGINE_API_KEY` | 备选推理 |

至少配置 DeepSeek 与一个推理模型（claude-sonnet-4.5 或 gpt-4.1）的 Key 即可基本运行。

---

## 9. 反向代理与 HTTPS

### Nginx 配置

`/etc/nginx/sites-available/thesisminer`：

```nginx
server {
    listen 80;
    server_name thesisminer.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name thesisminer.example.com;

    ssl_certificate /etc/letsencrypt/live/thesisminer.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/thesisminer.example.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    # 前端静态资源缓存
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # SSE 流式接口专用配置
    location /api/stream {
        proxy_pass http://127.0.0.1:8000;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        chunked_transfer_encoding on;
    }

    # 上传大小限制
    client_max_body_size 20m;
}
```

启用配置：

```bash
sudo ln -s /etc/nginx/sites-available/thesisminer /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### HTTPS 证书

使用 Let's Encrypt 免费证书：

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d thesisminer.example.com
```

---

## 10. 监控与告警

### 健康检查端点

- `GET /api/health`：返回服务状态与版本
- `GET /api/cache-stats`：返回 DeepSeek 缓存命中率

### 日志监控

日志输出到 `data/logs/thesisminer.log`，按天滚动。建议使用 `logrotate` 管理：

```
/opt/thesisminer/app/data/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
}
```

### 关键指标监控

| 指标 | 告警阈值 | 检查方式 |
|------|----------|----------|
| 服务可用性 | 连续 3 次健康检查失败 | 外部探针 |
| 响应时间 | P95 > 5 秒 | APM 工具 |
| DeepSeek 缓存命中率 | < 90% | `/api/cache-stats` |
| 磁盘使用率 | > 85% | 系统监控 |
| 数据库连接数 | > 80% 上限 | 数据库监控 |

---

## 11. 数据备份与恢复

### 自动备份脚本

`scripts/backup.sh`：

```bash
#!/bin/bash
BACKUP_DIR="/opt/thesisminer/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# SQLite 备份
cp /opt/thesisminer/app/data/thesisminer.db $BACKUP_DIR/thesisminer_$DATE.db

# PostgreSQL 备份
# pg_dump thesisminer > $BACKUP_DIR/thesisminer_$DATE.sql

# 保留最近 30 天备份
find $BACKUP_DIR -name "thesisminer_*.db" -mtime +30 -delete
```

加入 crontab 每日凌晨备份：

```bash
0 2 * * * /opt/thesisminer/app/scripts/backup.sh
```

### 恢复流程

```bash
# 停止服务
sudo systemctl stop thesisminer

# 恢复数据库
cp /opt/thesisminer/backups/thesisminer_20260619_020000.db /opt/thesisminer/app/data/thesisminer.db

# 启动服务
sudo systemctl start thesisminer
```

---

## 12. 性能调优

### Uvicorn Worker 数量

```bash
# 根据 CPU 核心数自动设置
WORKERS=$(( $(nproc) * 2 + 1 ))
gunicorn main:app -w $WORKERS -k uvicorn.workers.UvicornWorker
```

### DeepSeek 缓存优化

确保三段式 Prompt 前缀固化策略生效：

- 系统角色 + 硬约束 + 学位学科导师信息作为不可变前缀
- 多轮对话通过 DST 压缩后拼接，保持前缀字节级一致
- 监控 `/api/cache-stats`，命中率应 ≥ 95%

### 数据库索引

确保以下字段有索引（迁移脚本自动创建）：

- `conversations.session_id`
- `conversation_messages.conversation_id`
- `search_citations.message_id`
- `sessions.user_id`

---

## 13. 故障排查

### 服务无法启动

1. 检查日志：`journalctl -u thesisminer -n 100`
2. 验证 `.env` 配置完整性
3. 确认数据库文件权限：`ls -la data/thesisminer.db`
4. 检查端口占用：`lsof -i :8000`

### AI 调用失败

1. 验证 API Key 有效性
2. 检查网络连通性：`curl https://api.deepseek.com/v1/models`
3. 查看请求超时配置
4. 确认 API 余额/配额

### 前端加载异常

1. 检查 Nginx 配置与静态资源路径
2. 清除浏览器缓存后重试
3. 查看浏览器控制台错误
4. 确认 CDN 资源（D3.js）可访问

### 缓存命中率低

1. 确认 `CACHE_PREFIX_ENABLED=true`
2. 检查 Prompt 前缀是否被意外修改
3. 验证 DST 压缩是否破坏前缀一致性
4. 查看缓存监控日志定位异常调用

---

## 14. 升级与回滚

### 升级流程

1. **备份当前数据**

   ```bash
   sudo systemctl stop thesisminer
   bash scripts/backup.sh
   ```

2. **拉取新版本代码**

   ```bash
   cd /opt/thesisminer/app
   sudo -u thesisminer git fetch --tags
   sudo -u thesisminer git checkout v8.1.0
   sudo -u thesisminer .venv/bin/pip install -r requirements.txt
   ```

3. **执行数据库迁移**

   ```bash
   sudo -u thesisminer .venv/bin/python -c "from backend.database import migrate_db; migrate_db()"
   ```

4. **启动并验证**

   ```bash
   sudo systemctl start thesisminer
   curl http://localhost:8000/api/health
   ```

### 回滚流程

1. 停止服务
2. 切回上一版本代码：`git checkout v8.0.0`
3. 恢复备份数据库
4. 启动服务并验证

> **注意**：跨大版本回滚可能因数据库结构变更导致不兼容，务必先在测试环境验证。

---

如部署过程中遇到本指南未覆盖的问题，请提交 Issue 并附上完整日志与环境信息，维护团队将协助排查。
