# ThesisMiner v8.0 部署运维手册

> 本文档详细描述 ThesisMiner v8.0 项目的部署流程、运维操作、环境配置与生产环境最佳实践。

## 目录

- [1. 部署概览](#1-部署概览)
- [2. 环境要求](#2-环境要求)
- [3. 开发环境部署](#3-开发环境部署)
- [4. 生产环境部署](#4-生产环境部署)
- [5. Docker 部署](#5-docker-部署)
- [6. 配置管理](#6-配置管理)
- [7. 启动与停止](#7-启动与停止)
- [8. 日志管理](#8-日志管理)
- [9. 监控告警](#9-监控告警)
- [10. 备份恢复](#10-备份恢复)
- [11. 升级流程](#11-升级流程)
- [12. 故障排查](#12-故障排查)
- [13. 安全加固](#13-安全加固)
- [14. 性能调优](#14-性能调优)
- [15. 附录](#15-附录)

---

## 1. 部署概览

### 1.1 部署架构

```
┌─────────────────────────────────────────┐
│              负载均衡器                   │
│            (Nginx/HAProxy)              │
├─────────────────────────────────────────┤
│                                         │
│  ┌──────────┐  ┌──────────┐  ┌────────┐│
│  │ App实例1 │  │ App实例2 │  │  ...   ││
│  │ (Uvicorn)│  │ (Uvicorn)│  │        ││
│  └──────────┘  └──────────┘  └────────┘│
│                                         │
├─────────────────────────────────────────┤
│              共享存储                    │
│  ┌──────────┐  ┌──────────┐            │
│  │ SQLite DB│  │ 日志文件 │            │
│  │  (WAL)   │  │          │            │
│  └──────────┘  └──────────┘            │
└─────────────────────────────────────────┘
```

### 1.2 部署方式对比

| 方式 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| 直接部署 | 简单直接 | 环境依赖多 | 开发、测试 |
| Docker | 环境隔离 | 学习成本 | 生产 |
| Docker Compose | 多容器编排 | 单机限制 | 小规模生产 |
| Kubernetes | 自动扩缩容 | 复杂度高 | 大规模生产 |

---

## 2. 环境要求

### 2.1 硬件要求

| 配置 | 最低 | 推荐 | 生产 |
|------|------|------|------|
| CPU | 2核 | 4核 | 8核+ |
| 内存 | 2GB | 4GB | 8GB+ |
| 磁盘 | 10GB | 20GB | 50GB+ |
| 网络 | 1Mbps | 10Mbps | 100Mbps+ |

### 2.2 软件要求

| 软件 | 版本 | 用途 |
|------|------|------|
| Python | 3.11+ | 运行时 |
| pip | 23+ | 包管理 |
| Git | 2.30+ | 版本控制 |
| SQLite | 3.40+ | 数据库 |
| Nginx | 1.20+ | 反向代理（生产） |

---

## 3. 开发环境部署

### 3.1 克隆代码

```bash
git clone https://github.com/tree1104/ThesisMiner.git
cd ThesisMiner
```

### 3.2 创建虚拟环境

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3.3 安装依赖

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 3.4 配置环境变量

```bash
# .env 文件
OPENAI_API_KEY=sk-xxx
DEEPSEEK_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-xxx
QWEN_API_KEY=sk-xxx
GEMINI_API_KEY=xxx
GLM_API_KEY=xxx
DOUBAO_API_KEY=xxx
```

### 3.5 初始化数据库

```bash
python -c "from backend.database import init_database; init_database()"
```

### 3.6 启动开发服务器

```bash
python main.py
# 或
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

## 4. 生产环境部署

### 4.1 系统准备

```bash
# 创建用户
sudo useradd -m -s /bin/bash thesisminer

# 创建目录
sudo mkdir -p /opt/thesisminer
sudo chown thesisminer:thesisminer /opt/thesisminer

# 切换用户
sudo su - thesisminer
```

### 4.2 部署代码

```bash
cd /opt/thesisminer
git clone https://github.com/tree1104/ThesisMiner.git .
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4.3 配置 systemd 服务

```ini
# /etc/systemd/system/thesisminer.service
[Unit]
Description=ThesisMiner v8.0
After=network.target

[Service]
Type=simple
User=thesisminer
WorkingDirectory=/opt/thesisminer
Environment=PATH=/opt/thesisminer/venv/bin
EnvironmentFile=/opt/thesisminer/.env
ExecStart=/opt/thesisminer/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 4.4 启动服务

```bash
sudo systemctl daemon-reload
sudo systemctl enable thesisminer
sudo systemctl start thesisminer
sudo systemctl status thesisminer
```

### 4.5 Nginx 反向代理

```nginx
# /etc/nginx/conf.d/thesisminer.conf
upstream thesisminer {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name thesisminer.example.com;
    
    # 重定向到 HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name thesisminer.example.com;
    
    ssl_certificate /etc/ssl/certs/thesisminer.crt;
    ssl_certificate_key /etc/ssl/private/thesisminer.key;
    
    # 前端静态文件
    location /frontend/ {
        alias /opt/thesisminer/frontend/;
        expires 1d;
    }
    
    # API 代理
    location /api/ {
        proxy_pass http://thesisminer;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # SSE 支持
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }
    
    # WebSocket
    location /ws/ {
        proxy_pass http://thesisminer;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

---

## 5. Docker 部署

### 5.1 Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# 创建数据目录
RUN mkdir -p /app/data

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# 启动
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### 5.2 docker-compose.yml

```yaml
version: '3.8'

services:
  thesisminer:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    env_file:
      - .env
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
      - ./ssl:/etc/ssl
    depends_on:
      - thesisminer
    restart: unless-stopped
```

### 5.3 构建与运行

```bash
# 构建镜像
docker-compose build

# 启动
docker-compose up -d

# 查看日志
docker-compose logs -f thesisminer

# 停止
docker-compose down
```

---

## 6. 配置管理

### 6.1 配置文件层次

```
优先级（从高到低）：
1. 环境变量
2. data/config.json（用户配置）
3. backend/config.py（默认值）
```

### 6.2 关键配置项

```python
# backend/config.py
class Settings:
    # 应用
    APP_NAME = "ThesisMiner"
    APP_VERSION = "8.0.0"
    DEBUG = False
    
    # 数据库
    DB_PATH = "data/thesisminer.db"
    
    # LLM
    DEFAULT_MODEL = "deepseek-v3.2"
    LLM_TIMEOUT = 30
    
    # 缓存
    CACHE_ENABLED = True
    CACHE_TTL = 3600
    
    # 限流
    RATE_LIMIT_ENABLED = True
    RATE_LIMIT_DEFAULT = 60  # 每分钟
    
    # 日志
    LOG_LEVEL = "INFO"
    LOG_FILE = "logs/thesisminer.log"
```

---

## 7. 启动与停止

### 7.1 启动

```bash
# 开发模式
python main.py

# 生产模式
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

# Docker
docker-compose up -d

# systemd
sudo systemctl start thesisminer
```

### 7.2 停止

```bash
# 开发模式
Ctrl+C

# Docker
docker-compose down

# systemd
sudo systemctl stop thesisminer
```

### 7.3 重启

```bash
# Docker
docker-compose restart

# systemd
sudo systemctl restart thesisminer
```

---

## 8. 日志管理

### 8.1 日志配置

```python
import logging
from logging.handlers import RotatingFileHandler

def setup_logging():
    handler = RotatingFileHandler(
        "logs/thesisminer.log",
        maxBytes=100 * 1024 * 1024,  # 100MB
        backupCount=10
    )
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    
    logger = logging.getLogger("thesisminer")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
```

### 8.2 日志轮转

```bash
# logrotate 配置
/opt/thesisminer/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 thesisminer thesisminer
}
```

---

## 9. 监控告警

### 9.1 健康检查

```bash
# 手动检查
curl http://localhost:8000/api/health

# 自动检查脚本
#!/bin/bash
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health)
if [ "$HEALTH" != "200" ]; then
    echo "ALERT: ThesisMiner 健康检查失败"
    # 发送告警
fi
```

### 9.2 Prometheus 监控

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'thesisminer'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/api/metrics'
```

---

## 10. 备份恢复

### 10.1 自动备份

```bash
#!/bin/bash
# backup.sh - 每日备份

BACKUP_DIR="/opt/thesisminer/backups"
DATE=$(date +%Y%m%d)

# 备份数据库
sqlite3 /opt/thesisminer/data/thesisminer.db ".backup $BACKUP_DIR/db_$DATE.db"

# 备份配置
cp /opt/thesisminer/data/config.json $BACKUP_DIR/config_$DATE.json

# 压缩
gzip $BACKUP_DIR/db_$DATE.db

# 清理旧备份（保留30天）
find $BACKUP_DIR -name "*.gz" -mtime +30 -delete
```

### 10.2 恢复

```bash
# 停止服务
sudo systemctl stop thesisminer

# 恢复数据库
gunzip -c /opt/thesisminer/backups/db_20260619.db.gz > /opt/thesisminer/data/thesisminer.db

# 启动服务
sudo systemctl start thesisminer
```

---

## 11. 升级流程

### 11.1 升级步骤

```bash
# 1. 备份
./backup.sh

# 2. 停止服务
sudo systemctl stop thesisminer

# 3. 拉取新代码
cd /opt/thesisminer
git pull origin main

# 4. 更新依赖
source venv/bin/activate
pip install -r requirements.txt

# 5. 数据库迁移
python -c "from backend.database import migrate_db; migrate_db()"

# 6. 启动服务
sudo systemctl start thesisminer

# 7. 验证
curl http://localhost:8000/api/health
```

### 11.2 回滚

```bash
# 1. 停止服务
sudo systemctl stop thesisminer

# 2. 回滚代码
git checkout v8.0.0

# 3. 恢复备份
gunzip -c /opt/thesisminer/backups/db_20260618.db.gz > /opt/thesisminer/data/thesisminer.db

# 4. 启动服务
sudo systemctl start thesisminer
```

---

## 12. 故障排查

### 12.1 常见问题

#### 服务无法启动

```bash
# 检查日志
sudo journalctl -u thesisminer -n 100

# 检查端口
sudo netstat -tlnp | grep 8000

# 检查配置
python -c "from backend.config import get_settings; print(get_settings())"
```

#### 数据库锁定

```bash
# 检查锁定
sqlite3 /opt/thesisminer/data/thesisminer.db "PRAGMA lock_status"

# 重置 WAL
sqlite3 /opt/thesisminer/data/thesisminer.db "PRAGMA wal_checkpoint(TRUNCATE)"
```

#### 内存过高

```bash
# 查看进程
ps aux | grep uvicorn

# 查看内存
top -p $(pgrep -f uvicorn)
```

---

## 13. 安全加固

### 13.1 系统加固

```bash
# 防火墙
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# SSH 加固
# /etc/ssh/sshd_config
PermitRootLogin no
PasswordAuthentication no
```

### 13.2 应用加固

```bash
# 文件权限
chmod 600 /opt/thesisminer/.env
chmod 644 /opt/thesisminer/data/config.json
chmod 700 /opt/thesisminer/data
```

---

## 14. 性能调优

### 14.1 Uvicorn 调优

```bash
# 多 worker
uvicorn main:app --workers 4

# 异步循环
uvicorn main:app --loop uvloop

# HTTP 协议
uvicorn main:app --http httptools
```

### 14.2 数据库调优

```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=-64000;  -- 64MB
PRAGMA temp_store=MEMORY;
PRAGMA mmap_size=268435456;  -- 256MB
```

---

## 15. 附录

### 15.1 常用命令速查

```bash
# 服务管理
sudo systemctl start/stop/restart/status thesisminer

# 日志查看
sudo journalctl -u thesisminer -f

# Docker
docker-compose up/down/restart/logs

# 数据库
sqlite3 data/thesisminer.db

# 测试
pytest

# 部署
git pull && pip install -r requirements.txt && sudo systemctl restart thesisminer
```

---

## 结语

良好的部署运维是系统稳定运行的基础。ThesisMiner v8.0 通过完善的部署流程、监控告警、备份恢复机制，确保系统在生产环境中的可靠性、可用性与可维护性。
