# ThesisMiner v8.0 管理员指南

> 本指南面向 ThesisMiner 系统管理员，涵盖部署运维、模型配置、预算监控、数据备份、性能调优、安全加固等管理操作。完成本指南后，你将能够独立部署、配置、监控和维护 ThesisMiner 生产环境。

---

## 目录

- [1. 部署运维](#1-部署运维)
  - [1.1 Docker 部署](#11-docker-部署)
  - [1.2 裸机部署](#12-裸机部署)
  - [1.3 Nginx 反向代理](#13-nginx-反向代理)
  - [1.4 systemd 服务管理](#14-systemd-服务管理)
- [2. 模型配置](#2-模型配置)
  - [2.1 多模型注册](#21-多模型注册)
  - [2.2 步骤路由配置](#22-步骤路由配置)
  - [2.3 API Key 管理](#23-api-key-管理)
  - [2.4 模型健康检查](#24-模型健康检查)
- [3. 预算监控](#3-预算监控)
  - [3.1 成本告警](#31-成本告警)
  - [3.2 用量分析](#32-用量分析)
  - [3.3 配额管理](#33-配额管理)
  - [3.4 账本审计](#34-账本审计)
- [4. 数据备份](#4-数据备份)
  - [4.1 SQLite 备份策略](#41-sqlite-备份策略)
  - [4.2 恢复流程](#42-恢复流程)
  - [4.3 数据导出](#43-数据导出)
  - [4.4 数据归档](#44-数据归档)
- [5. 性能调优](#5-性能调优)
  - [5.1 并发配置](#51-并发配置)
  - [5.2 缓存优化](#52-缓存优化)
  - [5.3 数据库索引](#53-数据库索引)
  - [5.4 前端 CDN](#54-前端-cdn)
- [6. 安全加固](#6-安全加固)
  - [6.1 API Key 加密](#61-api-key-加密)
  - [6.2 HTTPS 配置](#62-https-配置)
  - [6.3 CORS 策略](#63-cors-策略)
  - [6.4 速率限制](#64-速率限制)
  - [6.5 审计日志](#65-审计日志)
- [7. 监控告警](#7-监控告警)
- [8. 故障恢复](#8-故障恢复)

---

## 1. 部署运维

### 1.1 Docker 部署

#### 1.1.1 Dockerfile

```dockerfile
# Dockerfile
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制源码
COPY . .

# 创建数据目录
RUN mkdir -p /app/data /app/logs

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# 启动命令
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

#### 1.1.2 docker-compose.yml

```yaml
# docker-compose.yml
version: '3.8'

services:
  thesisminer:
    build: .
    container_name: thesisminer
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./.env:/app/.env:ro
    environment:
      - DATABASE_URL=sqlite:///./data/thesisminer.db
      - LOG_FILE=/app/logs/thesisminer.log
    networks:
      - thesisminer-net
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s

  # 可选：Nginx 反向代理
  nginx:
    image: nginx:alpine
    container_name: thesisminer-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - ./nginx/logs:/var/log/nginx
    depends_on:
      - thesisminer
    networks:
      - thesisminer-net

  # 可选：Prometheus 监控
  prometheus:
    image: prom/prometheus:latest
    container_name: thesisminer-prometheus
    restart: unless-stopped
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    networks:
      - thesisminer-net

  # 可选：Grafana 仪表板
  grafana:
    image: grafana/grafana:latest
    container_name: thesisminer-grafana
    restart: unless-stopped
    ports:
      - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=your-admin-password
    depends_on:
      - prometheus
    networks:
      - thesisminer-net

volumes:
  prometheus-data:
  grafana-data:

networks:
  thesisminer-net:
    driver: bridge
```

#### 1.1.3 构建与启动

```bash
# 构建镜像
$ docker-compose build

# 启动服务
$ docker-compose up -d

# 查看日志
$ docker-compose logs -f thesisminer

# 查看服务状态
$ docker-compose ps

# 停止服务
$ docker-compose down

# 重新构建并启动
$ docker-compose up -d --build
```

#### 1.1.4 Docker 环境变量配置

创建 `.env` 文件：

```env
# Docker 环境变量
DEEPSEEK_API_KEY=sk-your-key
OPENAI_API_KEY=sk-your-key
ANTHROPIC_API_KEY=sk-ant-your-key
SECRET_KEY=your-secret-key-at-least-32-chars
LOG_LEVEL=INFO
WORKERS=4
```

### 1.2 裸机部署

#### 1.2.1 系统准备

**Ubuntu / Debian：**

```bash
# 更新系统
$ sudo apt update && sudo apt upgrade -y

# 安装 Python 3.11
$ sudo apt install -y python3.11 python3.11-venv python3.11-dev

# 安装其他依赖
$ sudo apt install -y nginx supervisor curl
```

**CentOS / RHEL：**

```bash
# 更新系统
$ sudo yum update -y

# 安装 Python 3.11
$ sudo yum install -y python3.11 python3.11-devel

# 安装其他依赖
$ sudo yum install -y nginx supervisor curl
```

#### 1.2.2 部署步骤

```bash
# 1. 创建应用用户
$ sudo useradd -m -s /bin/bash thesisminer

# 2. 切换用户
$ sudo su - thesisminer

# 3. 克隆代码
$ git clone https://github.com/your-org/thesisminer.git
$ cd thesisminer

# 4. 创建虚拟环境
$ python3.11 -m venv .venv
$ source .venv/bin/activate

# 5. 安装依赖
$ pip install -r requirements.txt

# 6. 配置环境变量
$ cp .env.example .env
$ vim .env  # 编辑配置

# 7. 初始化数据库
$ python -m backend.database init

# 8. 测试启动
$ python -m backend.main
```

#### 1.2.3 生产环境配置

```bash
# 安装 gunicorn（生产级 WSGI 服务器）
$ pip install gunicorn

# 使用 gunicorn 启动
$ gunicorn backend.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --timeout 120 \
    --keep-alive 5 \
    --max-requests 1000 \
    --max-requests-jitter 100
```

### 1.3 Nginx 反向代理

#### 1.3.1 Nginx 配置文件

```nginx
# /etc/nginx/conf.d/thesisminer.conf

upstream thesisminer_backend {
    server 127.0.0.1:8000;
    # 如有多实例，可添加：
    # server 127.0.0.1:8001;
    # server 127.0.0.1:8002;
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

    # SSL 配置
    ssl_certificate /etc/nginx/ssl/thesisminer.crt;
    ssl_certificate_key /etc/nginx/ssl/thesisminer.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # 日志
    access_log /var/log/nginx/thesisminer_access.log;
    error_log /var/log/nginx/thesisminer_error.log;

    # 请求体大小限制（文件上传）
    client_max_body_size 50M;

    # 代理配置
    location / {
        proxy_pass http://thesisminer_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE 支持（流式输出）
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;

        # WebSocket 支持（如需要）
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # 静态文件缓存
    location /static/ {
        alias /opt/thesisminer/frontend/dist/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # 健康检查（不记日志）
    location /api/health {
        proxy_pass http://thesisminer_backend;
        access_log off;
    }

    # 限流
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

    location /api/ {
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://thesisminer_backend;
    }
}
```

#### 1.3.2 启用配置

```bash
# 测试配置
$ sudo nginx -t

# 重新加载
$ sudo nginx -s reload

# 重启
$ sudo systemctl restart nginx
```

### 1.4 systemd 服务管理

#### 1.4.1 创建 systemd 服务文件

```ini
# /etc/systemd/system/thesisminer.service

[Unit]
Description=ThesisMiner v8.0 Service
After=network.target

[Service]
Type=simple
User=thesisminer
Group=thesisminer
WorkingDirectory=/home/thesisminer/thesisminer
Environment="PATH=/home/thesisminer/thesisminer/.venv/bin"
EnvironmentFile=/home/thesisminer/thesisminer/.env
ExecStart=/home/thesisminer/thesisminer/.venv/bin/gunicorn backend.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --timeout 120
ExecReload=/bin/kill -s HUP $MAINPID
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

#### 1.4.2 服务管理命令

```bash
# 重新加载 systemd
$ sudo systemctl daemon-reload

# 启动服务
$ sudo systemctl start thesisminer

# 停止服务
$ sudo systemctl stop thesisminer

# 重启服务
$ sudo systemctl restart thesisminer

# 查看状态
$ sudo systemctl status thesisminer

# 设置开机自启
$ sudo systemctl enable thesisminer

# 查看日志
$ sudo journalctl -u thesisminer -f

# 查看最近 100 行日志
$ sudo journalctl -u thesisminer -n 100
```

---

## 2. 模型配置

### 2.1 多模型注册

#### 2.1.1 模型配置文件

```python
# backend/config/models.py

from dataclasses import dataclass
from typing import Dict, List

@dataclass
class ModelConfig:
    """模型配置"""
    name: str                    # 模型名称
    provider: str                # 提供商
    api_key_env: str             # API Key 环境变量名
    base_url: str                # API 端点
    max_tokens: int              # 最大 Token 数
    cost_per_1k_input: float     # 输入成本（美元/1K tokens）
    cost_per_1k_output: float    # 输出成本（美元/1K tokens）
    supports_cache: bool = False # 是否支持缓存
    supports_stream: bool = True # 是否支持流式
    timeout: int = 60            # 超时时间（秒）
    rate_limit_rpm: int = 60     # 每分钟请求限制

# 模型注册表
MODEL_REGISTRY: Dict[str, ModelConfig] = {
    "deepseek-r2": ModelConfig(
        name="deepseek-r2",
        provider="deepseek",
        api_key_env="DEEPSEEK_API_KEY",
        base_url="https://api.deepseek.com/v1",
        max_tokens=8192,
        cost_per_1k_input=0.001,
        cost_per_1k_output=0.002,
        supports_cache=True,  # DeepSeek 支持上下文缓存
        supports_stream=True,
        timeout=60,
        rate_limit_rpm=60
    ),
    "claude-opus-4.5": ModelConfig(
        name="claude-opus-4.5",
        provider="anthropic",
        api_key_env="ANTHROPIC_API_KEY",
        base_url="https://api.anthropic.com/v1",
        max_tokens=8192,
        cost_per_1k_input=0.015,
        cost_per_1k_output=0.075,
        supports_cache=False,
        supports_stream=True,
        timeout=120,
        rate_limit_rpm=50
    ),
    "gpt-4.1": ModelConfig(
        name="gpt-4.1",
        provider="openai",
        api_key_env="OPENAI_API_KEY",
        base_url="https://api.openai.com/v1",
        max_tokens=8192,
        cost_per_1k_input=0.010,
        cost_per_1k_output=0.030,
        supports_cache=False,
        supports_stream=True,
        timeout=90,
        rate_limit_rpm=60
    ),
    "glm-4-plus": ModelConfig(
        name="glm-4-plus",
        provider="zhipu",
        api_key_env="ZHIPU_API_KEY",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        max_tokens=8192,
        cost_per_1k_input=0.005,
        cost_per_1k_output=0.005,
        supports_cache=False,
        supports_stream=True,
        timeout=60,
        rate_limit_rpm=100
    ),
    "moonshot-v1-128k": ModelConfig(
        name="moonshot-v1-128k",
        provider="moonshot",
        api_key_env="MOONSHOT_API_KEY",
        base_url="https://api.moonshot.cn/v1",
        max_tokens=8192,
        cost_per_1k_input=0.008,
        cost_per_1k_output=0.024,
        supports_cache=False,
        supports_stream=True,
        timeout=90,
        rate_limit_rpm=60
    )
}
```

#### 2.1.2 动态添加模型

```python
# 通过 API 动态添加模型
import httpx

async def add_model():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/admin/models",
            json={
                "name": "qwen-max",
                "provider": "alibaba",
                "api_key_env": "DASHSCOPE_API_KEY",
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "max_tokens": 8192,
                "cost_per_1k_input": 0.004,
                "cost_per_1k_output": 0.012,
                "supports_stream": True,
                "timeout": 60
            },
            headers={"Authorization": "Bearer admin-token"}
        )
        return response.json()
```

### 2.2 步骤路由配置

#### 2.2.1 路由配置界面

```
+------------------------------------------------------------------+
|  步骤路由配置                                                     |
+------------------------------------------------------------------+
|                                                                  |
|  阶段              | 主模型            | 备用模型        | 条件   |
|-------------------|-------------------|-----------------|--------|
|  信息确权          | deepseek-r2    ▼  | gpt-4.1     ▼   | -      |
|  创意生成          | claude-opus-4.5▼  | gpt-4.1     ▼   | 博士   |
|  校验              | deepseek-r2    ▼  | gpt-4.1     ▼   | -      |
|  多粒度生成        | gpt-4.1        ▼  | claude-opus▼    | -      |
|  深度辅助          | claude-opus-4.5▼  | gpt-4.1     ▼   | -      |
|                                                                  |
|  [保存配置]  [恢复默认]  [测试路由]                               |
+------------------------------------------------------------------+
```

#### 2.2.2 通过 API 配置路由

```bash
# 设置路由
$ curl -X PUT http://localhost:8000/api/admin/routing \
  -H "Authorization: Bearer admin-token" \
  -H "Content-Type: application/json" \
  -d '{
    "routes": [
      {
        "stage": "information_confirmation",
        "model": "deepseek-r2",
        "fallback_model": "gpt-4.1"
      },
      {
        "stage": "ideation",
        "model": "claude-opus-4.5",
        "fallback_model": "gpt-4.1",
        "condition": "degree == \"doctor\""
      },
      {
        "stage": "validation",
        "model": "deepseek-r2",
        "fallback_model": "gpt-4.1"
      },
      {
        "stage": "generation",
        "model": "gpt-4.1",
        "fallback_model": "claude-opus-4.5"
      },
      {
        "stage": "deep_assistance",
        "model": "claude-opus-4.5",
        "fallback_model": "gpt-4.1"
      }
    ]
  }'

# 查看当前路由
$ curl http://localhost:8000/api/admin/routing \
  -H "Authorization: Bearer admin-token"
```

### 2.3 API Key 管理

#### 2.3.1 API Key 加密存储

```python
# backend/security/api_key_manager.py

import os
from cryptography.fernet import Fernet
from typing import Dict

class APIKeyManager:
    """API Key 加密管理器"""

    def __init__(self, encryption_key: str = None):
        # 从环境变量获取加密密钥
        key = encryption_key or os.getenv("ENCRYPTION_KEY")
        if not key:
            # 生成新密钥（首次部署时）
            key = Fernet.generate_key().decode()
            print(f"[WARNING] 请将此密钥保存到环境变量 ENCRYPTION_KEY：{key}")

        self.cipher = Fernet(key.encode() if isinstance(key, str) else key)
        self._cache: Dict[str, str] = {}

    def encrypt(self, api_key: str) -> str:
        """加密 API Key"""
        return self.cipher.encrypt(api_key.encode()).decode()

    def decrypt(self, encrypted_key: str) -> str:
        """解密 API Key"""
        if encrypted_key in self._cache:
            return self._cache[encrypted_key]

        decrypted = self.cipher.decrypt(encrypted_key.encode()).decode()
        self._cache[encrypted_key] = decrypted
        return decrypted

    def store_key(self, model_name: str, api_key: str, db_conn):
        """存储 API Key 到数据库（加密）"""
        encrypted = self.encrypt(api_key)
        db_conn.execute(
            "INSERT OR REPLACE INTO model_configs (model_name, api_key_encrypted) VALUES (?, ?)",
            (model_name, encrypted)
        )
        db_conn.commit()

    def get_key(self, model_name: str, db_conn) -> str:
        """从数据库获取 API Key（解密）"""
        cursor = db_conn.execute(
            "SELECT api_key_encrypted FROM model_configs WHERE model_name = ?",
            (model_name,)
        )
        row = cursor.fetchone()
        if not row:
            raise KeyError(f"未找到模型 {model_name} 的 API Key")
        return self.decrypt(row[0])

    def rotate_key(self, model_name: str, new_api_key: str, db_conn):
        """轮换 API Key"""
        self.store_key(model_name, new_api_key, db_conn)
        # 清除缓存
        self._cache.clear()
```

#### 2.3.2 API Key 轮换流程

```bash
# 1. 生成新的加密密钥
$ python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
abc123...xyz

# 2. 更新环境变量
$ export ENCRYPTION_KEY="abc123...xyz"

# 3. 重加密所有 API Key
$ python -m backend.cli keys rotate --all

# 4. 更新单个模型的 API Key
$ python -m backend.cli keys update --model deepseek-r2 --key sk-new-key

# 5. 验证
$ python -m backend.cli keys test --model deepseek-r2
```

### 2.4 模型健康检查

#### 2.4.1 健康检查脚本

```python
# backend/monitoring/model_health.py

import asyncio
import httpx
from datetime import datetime
from typing import Dict, List

class ModelHealthChecker:
    """模型健康检查器"""

    def __init__(self, models: Dict):
        self.models = models
        self.health_history: List[Dict] = []

    async def check_all(self) -> Dict:
        """检查所有模型健康状态"""
        results = {}
        for model_name, config in self.models.items():
            result = await self._check_one(model_name, config)
            results[model_name] = result

            # 记录历史
            self.health_history.append({
                "timestamp": datetime.now(),
                "model": model_name,
                **result
            })

        return results

    async def _check_one(self, model_name: str, config: dict) -> Dict:
        """检查单个模型"""
        try:
            start = datetime.now()
            async with httpx.AsyncClient(timeout=10) as client:
                # 发送简单请求测试连通性
                response = await client.post(
                    f"{config['base_url']}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {config['api_key']}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model_name,
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 5
                    }
                )
                latency = (datetime.now() - start).total_seconds() * 1000

                if response.status_code == 200:
                    return {
                        "status": "healthy",
                        "latency_ms": round(latency, 2),
                        "status_code": 200
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "latency_ms": round(latency, 2),
                        "status_code": response.status_code,
                        "error": response.text[:200]
                    }

        except httpx.TimeoutException:
            return {"status": "timeout", "error": "请求超时"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def get_history(self, model_name: str = None, hours: int = 24) -> List:
        """获取健康检查历史"""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(hours=hours)
        history = [h for h in self.health_history if h["timestamp"] > cutoff]
        if model_name:
            history = [h for h in history if h["model"] == model_name]
        return history
```

#### 2.4.2 定时健康检查

```python
# backend/scheduler/health_scheduler.py

import asyncio
from datetime import datetime

class HealthScheduler:
    """定时健康检查调度器"""

    def __init__(self, checker, interval_minutes: int = 5):
        self.checker = checker
        self.interval = interval_minutes * 60
        self.running = False

    async def start(self):
        """启动定时检查"""
        self.running = True
        while self.running:
            try:
                results = await self.checker.check_all()
                unhealthy = [
                    name for name, result in results.items()
                    if result["status"] != "healthy"
                ]
                if unhealthy:
                    await self._send_alert(unhealthy)
            except Exception as e:
                print(f"[HealthScheduler] 检查失败：{e}")

            await asyncio.sleep(self.interval)

    def stop(self):
        """停止定时检查"""
        self.running = False

    async def _send_alert(self, unhealthy_models: list):
        """发送告警"""
        message = f"[告警] 以下模型不健康：{', '.join(unhealthy_models)}"
        # 发送邮件/Slack/钉钉通知
        print(message)
```

---

## 3. 预算监控

### 3.1 成本告警

#### 3.1.1 告警规则配置

```python
# backend/monitoring/budget_alert.py

from typing import List, Dict
from datetime import datetime, timedelta

class BudgetAlertManager:
    """预算告警管理器"""

    def __init__(self, ledger):
        self.ledger = ledger
        self.alert_rules: List[Dict] = []

    def add_rule(
        self,
        name: str,
        metric: str,        # total_cost / daily_cost / session_cost
        threshold: float,
        action: str,        # email / webhook / log
        recipient: str = None
    ):
        """添加告警规则"""
        self.alert_rules.append({
            "name": name,
            "metric": metric,
            "threshold": threshold,
            "action": action,
            "recipient": recipient
        })

    async def check_alerts(self) -> List[Dict]:
        """检查所有告警规则"""
        triggered = []
        for rule in self.alert_rules:
            value = await self._get_metric(rule["metric"])
            if value >= rule["threshold"]:
                alert = {
                    "rule_name": rule["name"],
                    "metric": rule["metric"],
                    "value": value,
                    "threshold": rule["threshold"],
                    "timestamp": datetime.now()
                }
                triggered.append(alert)
                await self._send_alert(alert, rule)

        return triggered

    async def _get_metric(self, metric: str) -> float:
        """获取指标值"""
        if metric == "total_cost":
            return self.ledger.get_total_cost()
        elif metric == "daily_cost":
            return self.ledger.get_cost_since(
                datetime.now() - timedelta(days=1)
            )
        elif metric.startswith("session_cost:"):
            session_id = metric.split(":")[1]
            return self.ledger.get_session_cost(session_id)
        return 0

    async def _send_alert(self, alert: dict, rule: dict):
        """发送告警"""
        message = (
            f"预算告警：{alert['rule_name']}\n"
            f"指标：{alert['metric']}\n"
            f"当前值：${alert['value']:.2f}\n"
            f"阈值：${alert['threshold']:.2f}\n"
            f"时间：{alert['timestamp']}"
        )

        if rule["action"] == "email":
            await self._send_email(rule["recipient"], message)
        elif rule["action"] == "webhook":
            await self._send_webhook(rule["recipient"], alert)
        elif rule["action"] == "log":
            print(f"[ALERT] {message}")

# 配置默认告警规则
def setup_default_alerts(alert_manager: BudgetAlertManager):
    alert_manager.add_rule(
        name="日成本告警",
        metric="daily_cost",
        threshold=50.0,
        action="email",
        recipient="admin@example.com"
    )
    alert_manager.add_rule(
        name="总成本告警",
        metric="total_cost",
        threshold=1000.0,
        action="webhook",
        recipient="https://hooks.slack.com/..."
    )
```

### 3.2 用量分析

#### 3.2.1 用量报表

```python
# backend/reports/usage_report.py

from datetime import datetime, timedelta
from typing import Dict

class UsageReporter:
    """用量报表生成器"""

    def __init__(self, ledger):
        self.ledger = ledger

    def daily_report(self, date: datetime = None) -> Dict:
        """生成日报"""
        date = date or datetime.now()
        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

        records = self.ledger.get_records_between(start, end)

        return {
            "date": start.strftime("%Y-%m-%d"),
            "total_requests": len(records),
            "total_tokens": sum(r["total_tokens"] for r in records),
            "total_cost": sum(r["cost_usd"] for r in records),
            "by_model": self._group_by(records, "model"),
            "by_stage": self._group_by(records, "stage"),
            "by_session": self._group_by(records, "session_id"),
            "cache_hit_rate": self._calc_cache_hit_rate(records)
        }

    def weekly_report(self, end_date: datetime = None) -> Dict:
        """生成周报"""
        end_date = end_date or datetime.now()
        start_date = end_date - timedelta(days=7)

        daily_reports = []
        for i in range(7):
            date = start_date + timedelta(days=i)
            daily_reports.append(self.daily_report(date))

        return {
            "period": f"{start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}",
            "daily_reports": daily_reports,
            "total_cost": sum(r["total_cost"] for r in daily_reports),
            "total_tokens": sum(r["total_tokens"] for r in daily_reports),
            "avg_daily_cost": sum(r["total_cost"] for r in daily_reports) / 7,
            "trend": self._calc_trend(daily_reports)
        }

    def monthly_report(self, year: int, month: int) -> Dict:
        """生成月报"""
        # 实现略
        pass

    def _group_by(self, records, key):
        """按字段分组统计"""
        groups = {}
        for r in records:
            k = r.get(key, "unknown")
            if k not in groups:
                groups[k] = {"count": 0, "tokens": 0, "cost": 0}
            groups[k]["count"] += 1
            groups[k]["tokens"] += r["total_tokens"]
            groups[k]["cost"] += r["cost_usd"]
        return groups

    def _calc_cache_hit_rate(self, records):
        """计算缓存命中率"""
        if not records:
            return 0
        hits = sum(1 for r in records if r.get("cache_hit"))
        return hits / len(records)

    def _calc_trend(self, daily_reports):
        """计算趋势"""
        costs = [r["total_cost"] for r in daily_reports]
        if len(costs) < 2:
            return "stable"
        diff = costs[-1] - costs[0]
        if diff > costs[0] * 0.1:
            return "increasing"
        elif diff < -costs[0] * 0.1:
            return "decreasing"
        return "stable"
```

### 3.3 配额管理

```python
# backend/quota/quota_manager.py

from typing import Dict
from datetime import datetime, timedelta
from dataclasses import dataclass

@dataclass
class Quota:
    """配额定义"""
    name: str
    limit: float
    period: str  # daily / weekly / monthly
    used: float = 0
    reset_at: datetime = None

class QuotaManager:
    """配额管理器"""

    def __init__(self):
        self.quotas: Dict[str, Quota] = {}
        self.user_quotas: Dict[str, Dict[str, Quota]] = {}

    def set_global_quota(self, name: str, limit: float, period: str):
        """设置全局配额"""
        self.quotas[name] = Quota(
            name=name,
            limit=limit,
            period=period,
            reset_at=self._calc_reset_time(period)
        )

    def set_user_quota(self, user_id: str, name: str, limit: float, period: str):
        """设置用户配额"""
        if user_id not in self.user_quotas:
            self.user_quotas[user_id] = {}
        self.user_quotas[user_id][name] = Quota(
            name=name,
            limit=limit,
            period=period,
            reset_at=self._calc_reset_time(period)
        )

    def check_quota(self, user_id: str, amount: float) -> Dict:
        """检查配额"""
        result = {"allowed": True, "violations": []}

        # 检查全局配额
        for name, quota in self.quotas.items():
            if quota.used + amount > quota.limit:
                result["allowed"] = False
                result["violations"].append({
                    "type": "global",
                    "name": name,
                    "used": quota.used,
                    "limit": quota.limit,
                    "requested": amount
                })

        # 检查用户配额
        if user_id in self.user_quotas:
            for name, quota in self.user_quotas[user_id].items():
                if quota.used + amount > quota.limit:
                    result["allowed"] = False
                    result["violations"].append({
                        "type": "user",
                        "name": name,
                        "used": quota.used,
                        "limit": quota.limit,
                        "requested": amount
                    })

        return result

    def record_usage(self, user_id: str, name: str, amount: float):
        """记录用量"""
        if name in self.quotas:
            self.quotas[name].used += amount
        if user_id in self.user_quotas and name in self.user_quotas[user_id]:
            self.user_quotas[user_id][name].used += amount

    def _calc_reset_time(self, period: str) -> datetime:
        """计算重置时间"""
        now = datetime.now()
        if period == "daily":
            return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0)
        elif period == "weekly":
            return now + timedelta(days=7 - now.weekday())
        elif period == "monthly":
            from calendar import monthrange
            _, last_day = monthrange(now.year, now.month)
            return now.replace(day=last_day, hour=23, minute=59, second=59)
        return now

# 配置默认配额
def setup_default_quotas(quota_manager: QuotaManager):
    # 全局配额
    quota_manager.set_global_quota("daily_cost", 100.0, "daily")
    quota_manager.set_global_quota("monthly_cost", 2000.0, "monthly")
    quota_manager.set_global_quota("daily_tokens", 5000000, "daily")

    # 用户配额（示例）
    quota_manager.set_user_quota("user_001", "daily_cost", 20.0, "daily")
    quota_manager.set_user_quota("user_001", "daily_tokens", 500000, "daily")
```

### 3.4 账本审计

```python
# backend/audit/budget_audit.py

from datetime import datetime
from typing import List, Dict

class BudgetAuditor:
    """预算审计器"""

    def __init__(self, ledger):
        self.ledger = ledger

    def audit_anomalies(self, start_date: datetime, end_date: datetime) -> Dict:
        """审计异常"""
        records = self.ledger.get_records_between(start_date, end_date)

        anomalies = {
            "high_cost_requests": [],
            "unusual_patterns": [],
            "missing_records": [],
            "summary": {}
        }

        # 1. 高成本请求（超过平均值 3 倍）
        avg_cost = sum(r["cost_usd"] for r in records) / len(records) if records else 0
        for r in records:
            if r["cost_usd"] > avg_cost * 3:
                anomalies["high_cost_requests"].append({
                    "record_id": r["id"],
                    "cost": r["cost_usd"],
                    "avg_cost": avg_cost,
                    "model": r["model"],
                    "timestamp": r["timestamp"]
                })

        # 2. 异常模式（短时间内大量请求）
        from collections import defaultdict
        from datetime import timedelta

        time_buckets = defaultdict(int)
        for r in records:
            bucket = r["timestamp"].replace(minute=0, second=0, microsecond=0)
            time_buckets[bucket] += 1

        avg_per_hour = sum(time_buckets.values()) / len(time_buckets) if time_buckets else 0
        for bucket, count in time_buckets.items():
            if count > avg_per_hour * 5:
                anomalies["unusual_patterns"].append({
                    "time": bucket,
                    "count": count,
                    "avg": avg_per_hour
                })

        # 3. 摘要
        anomalies["summary"] = {
            "total_records": len(records),
            "total_cost": sum(r["cost_usd"] for r in records),
            "avg_cost": avg_cost,
            "anomaly_count": len(anomalies["high_cost_requests"]) + len(anomalies["unusual_patterns"])
        }

        return anomalies

    def generate_audit_report(self, start_date: datetime, end_date: datetime) -> str:
        """生成审计报告"""
        anomalies = self.audit_anomalies(start_date, end_date)

        report = f"""
预算审计报告
==================================================
审计期间：{start_date} ~ {end_date}

摘要：
- 总记录数：{anomalies['summary']['total_records']}
- 总成本：${anomalies['summary']['total_cost']:.2f}
- 平均成本：${anomalies['summary']['avg_cost']:.4f}
- 异常数：{anomalies['summary']['anomaly_count']}

高成本请求（{len(anomalies['high_cost_requests'])} 个）：
"""
        for req in anomalies["high_cost_requests"][:10]:
            report += f"  - {req['timestamp']}: ${req['cost']:.4f}（模型：{req['model']}）\n"

        report += f"\n异常模式（{len(anomalies['unusual_patterns'])} 个）：\n"
        for pattern in anomalies["unusual_patterns"][:10]:
            report += f"  - {pattern['time']}: {pattern['count']} 次请求（平均：{pattern['avg']:.1f}）\n"

        return report
```

---

## 4. 数据备份

### 4.1 SQLite 备份策略

#### 4.1.1 自动备份脚本

```python
# backend/backup/sqlite_backup.py

import sqlite3
import shutil
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

class SQLiteBackup:
    """SQLite 备份管理器"""

    def __init__(
        self,
        db_path: str,
        backup_dir: str = "./backups",
        max_backups: int = 30
    ):
        self.db_path = db_path
        self.backup_dir = Path(backup_dir)
        self.max_backups = max_backups
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def backup(self, label: str = None) -> str:
        """执行备份

        Args:
            label: 备份标签（可选）

        Returns:
            备份文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        label_part = f"_{label}" if label else ""
        backup_filename = f"thesisminer_{timestamp}{label_part}.db"
        backup_path = self.backup_dir / backup_filename

        # 使用 SQLite Online Backup API（不停机备份）
        source = sqlite3.connect(self.db_path)
        dest = sqlite3.connect(str(backup_path))
        source.backup(dest)
        dest.close()
        source.close()

        # 压缩备份
        import gzip
        compressed_path = str(backup_path) + ".gz"
        with open(backup_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        os.remove(backup_path)

        # 清理旧备份
        self._cleanup_old_backups()

        print(f"[Backup] 已创建备份：{compressed_path}")
        return compressed_path

    def restore(self, backup_path: str) -> bool:
        """从备份恢复

        Args:
            backup_path: 备份文件路径

        Returns:
            是否成功
        """
        try:
            # 解压（如果是压缩文件）
            if backup_path.endswith('.gz'):
                import gzip
                decompressed_path = backup_path[:-3]
                with gzip.open(backup_path, 'rb') as f_in:
                    with open(decompressed_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                backup_path = decompressed_path

            # 备份当前数据库
            current_backup = self.db_path + ".pre_restore"
            if os.path.exists(self.db_path):
                shutil.copy2(self.db_path, current_backup)

            # 恢复
            shutil.copy2(backup_path, self.db_path)

            print(f"[Restore] 已从 {backup_path} 恢复")
            print(f"[Restore] 原数据库已备份到 {current_backup}")
            return True

        except Exception as e:
            print(f"[Restore] 恢复失败：{e}")
            return False

    def _cleanup_old_backups(self):
        """清理旧备份"""
        backups = sorted(
            self.backup_dir.glob("thesisminer_*.db.gz"),
            key=os.path.getmtime,
            reverse=True
        )

        for old_backup in backups[self.max_backups:]:
            old_backup.unlink()
            print(f"[Backup] 已删除旧备份：{old_backup}")

    def list_backups(self) -> list:
        """列出所有备份"""
        backups = []
        for f in sorted(self.backup_dir.glob("thesisminer_*.db.gz"), key=os.path.getmtime, reverse=True):
            stat = os.stat(f)
            backups.append({
                "filename": f.name,
                "path": str(f),
                "size_mb": round(stat.st_size / 1024 / 1024, 2),
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
        return backups
```

#### 4.1.2 定时备份

```bash
# /etc/cron.d/thesisminer-backup

# 每天凌晨 2 点备份
0 2 * * * thesisminer cd /home/thesisminer/thesisminer && .venv/bin/python -m backend.backup sqlite --label daily

# 每周日凌晨 3 点备份（周备份）
0 3 * * 0 thesisminer cd /home/thesisminer/thesisminer && .venv/bin/python -m backend.backup sqlite --label weekly

# 每月 1 号凌晨 4 点备份（月备份）
0 4 1 * * thesisminer cd /home/thesisminer/thesisminer && .venv/bin/python -m backend.backup sqlite --label monthly
```

### 4.2 恢复流程

#### 4.2.1 恢复步骤

```bash
# 1. 停止服务
$ sudo systemctl stop thesisminer

# 2. 列出可用备份
$ python -m backend.backup list
Filename                              | Size    | Created At
thesisminer_20260619_020000_daily.db.gz | 12.5 MB | 2026-06-19T02:00:00
thesisminer_20260618_020000_daily.db.gz | 12.3 MB | 2026-06-18T02:00:00
...

# 3. 恢复指定备份
$ python -m backend.backup restore --file thesisminer_20260619_020000_daily.db.gz

# 4. 验证数据
$ python -m backend.database tables
$ python -m backend.database seed --list

# 5. 重启服务
$ sudo systemctl start thesisminer

# 6. 验证服务
$ curl http://localhost:8000/api/health
```

### 4.3 数据导出

```python
# backend/backup/data_export.py

import json
import csv
from datetime import datetime
from typing import List, Dict

class DataExporter:
    """数据导出器"""

    def __init__(self, db_conn):
        self.conn = db_conn

    def export_sessions(self, format: str = "json") -> str:
        """导出会话数据"""
        cursor = self.conn.execute("SELECT * FROM sessions ORDER BY created_at")
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()

        data = [dict(zip(columns, row)) for row in rows]

        if format == "json":
            return json.dumps(data, ensure_ascii=False, indent=2, default=str)
        elif format == "csv":
            return self._to_csv(data, columns)
        else:
            raise ValueError(f"不支持的格式：{format}")

    def export_budget_ledger(self, start_date: datetime = None, format: str = "csv") -> str:
        """导出预算账本"""
        query = "SELECT * FROM budget_ledger"
        params = []
        if start_date:
            query += " WHERE created_at >= ?"
            params.append(start_date)
        query += " ORDER BY created_at"

        cursor = self.conn.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()

        data = [dict(zip(columns, row)) for row in rows]

        if format == "json":
            return json.dumps(data, ensure_ascii=False, indent=2, default=str)
        else:
            return self._to_csv(data, columns)

    def export_lineage(self, session_id: str, format: str = "json") -> str:
        """导出谱系图谱"""
        # 导出节点
        cursor = self.conn.execute(
            "SELECT * FROM lineage_nodes WHERE session_id = ?",
            (session_id,)
        )
        nodes = [dict(zip([d[0] for d in cursor.description], r)) for r in cursor.fetchall()]

        # 导出边
        cursor = self.conn.execute(
            "SELECT * FROM lineage_edges WHERE session_id = ?",
            (session_id,)
        )
        edges = [dict(zip([d[0] for d in cursor.description], r)) for r in cursor.fetchall()]

        data = {"nodes": nodes, "edges": edges}

        return json.dumps(data, ensure_ascii=False, indent=2, default=str)

    def _to_csv(self, data: List[Dict], columns: List[str]) -> str:
        """转换为 CSV"""
        import io
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        for row in data:
            writer.writerow(row)
        return output.getvalue()
```

### 4.4 数据归档

```python
# backend/backup/archiver.py

import os
import shutil
from datetime import datetime, timedelta
from typing import List

class DataArchiver:
    """数据归档器"""

    def __init__(self, db_conn, archive_dir: str = "./archives"):
        self.conn = db_conn
        self.archive_dir = archive_dir
        os.makedirs(archive_dir, exist_ok=True)

    def archive_old_sessions(self, days: int = 90) -> int:
        """归档旧会话

        Args:
            days: 归档多少天前的数据

        Returns:
            归档的会话数
        """
        cutoff = datetime.now() - timedelta(days=days)

        # 查询旧会话
        cursor = self.conn.execute(
            "SELECT * FROM sessions WHERE created_at < ? AND status = 'completed'",
            (cutoff,)
        )
        old_sessions = cursor.fetchall()

        if not old_sessions:
            return 0

        # 创建归档文件
        archive_filename = f"archive_{datetime.now().strftime('%Y%m%d')}.json"
        archive_path = os.path.join(self.archive_dir, archive_filename)

        import json
        archive_data = {
            "archived_at": datetime.now().isoformat(),
            "cutoff_date": cutoff.isoformat(),
            "sessions": []
        }

        for session in old_sessions:
            session_id = session[0]
            session_data = {
                "session": dict(zip([d[0] for d in cursor.description], session)),
                "messages": self._get_messages(session_id),
                "proposals": self._get_proposals(session_id),
                "budget_records": self._get_budget_records(session_id)
            }
            archive_data["sessions"].append(session_data)

        # 写入归档文件
        with open(archive_path, 'w', encoding='utf-8') as f:
            json.dump(archive_data, f, ensure_ascii=False, indent=2, default=str)

        # 从数据库删除已归档数据
        for session in old_sessions:
            session_id = session[0]
            self.conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            self.conn.execute("DELETE FROM proposals WHERE session_id = ?", (session_id,))
            self.conn.execute("DELETE FROM budget_ledger WHERE session_id = ?", (session_id,))
            self.conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

        self.conn.commit()

        print(f"[Archive] 已归档 {len(old_sessions)} 个会话到 {archive_path}")
        return len(old_sessions)

    def _get_messages(self, session_id):
        cursor = self.conn.execute("SELECT * FROM messages WHERE session_id = ?", (session_id,))
        return [dict(zip([d[0] for d in cursor.description], r)) for r in cursor.fetchall()]

    def _get_proposals(self, session_id):
        cursor = self.conn.execute("SELECT * FROM proposals WHERE session_id = ?", (session_id,))
        return [dict(zip([d[0] for d in cursor.description], r)) for r in cursor.fetchall()]

    def _get_budget_records(self, session_id):
        cursor = self.conn.execute("SELECT * FROM budget_ledger WHERE session_id = ?", (session_id,))
        return [dict(zip([d[0] for d in cursor.description], r)) for r in cursor.fetchall()]
```

---

## 5. 性能调优

### 5.1 并发配置

#### 5.1.1 Uvicorn/Gunicorn Worker 配置

```bash
# 推荐配置公式：workers = (2 * CPU 核心数) + 1

# 4 核服务器
$ gunicorn backend.main:app \
    --workers 9 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000

# 8 核服务器
$ gunicorn backend.main:app \
    --workers 17 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000
```

#### 5.1.2 异步并发控制

```python
# backend/config/concurrency.py

import os

class ConcurrencyConfig:
    """并发配置"""

    # Worker 进程数
    WORKERS = int(os.getenv("WORKERS", 4))

    # Agent 并发数
    MAX_CONCURRENT_AGENTS = int(os.getenv("MAX_CONCURRENT_AGENTS", 5))

    # API 调用并发数
    MAX_CONCURRENT_API_CALLS = int(os.getenv("MAX_CONCURRENT_API_CALLS", 10))

    # 数据库连接池
    DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", 20))

    # HTTP 客户端连接池
    HTTP_POOL_SIZE = int(os.getenv("HTTP_POOL_SIZE", 100))

    # 速率限制
    RATE_LIMIT_RPM = int(os.getenv("RATE_LIMIT_RPM", 60))

    # 超时设置
    API_TIMEOUT = int(os.getenv("API_TIMEOUT", 60))
    DB_TIMEOUT = int(os.getenv("DB_TIMEOUT", 30))
```

### 5.2 缓存优化

#### 5.2.1 缓存配置

```python
# backend/config/cache.py

class CacheConfig:
    """缓存配置"""

    # 是否启用缓存
    ENABLED = True

    # 缓存类型：memory / redis
    TYPE = "memory"

    # 最大缓存条目
    MAX_SIZE = 5000

    # TTL（秒）
    TTL_SECONDS = 7200  # 2 小时

    # 前缀稳定性阈值（低于此值告警）
    PREFIX_STABILITY_THRESHOLD = 0.8

    # Redis 配置（如使用 Redis）
    REDIS_URL = "redis://localhost:6379/0"
    REDIS_PASSWORD = None
```

#### 5.2.2 缓存预热

```python
# backend/cache/cache_warmer.py

import asyncio
from typing import List

class CacheWarmer:
    """缓存预热器"""

    def __init__(self, cache_manager, agents):
        self.cache = cache_manager
        self.agents = agents

    async def warmup(self):
        """预热缓存"""
        # 为每个 Agent 预生成 Prompt 前缀
        tasks = []
        for agent_name, agent_class in self.agents.items():
            task = self._warmup_agent(agent_name, agent_class)
            tasks.append(task)

        await asyncio.gather(*tasks)
        print(f"[CacheWarmer] 预热完成，已缓存 {len(tasks)} 个 Agent 前缀")

    async def _warmup_agent(self, agent_name: str, agent_class):
        """预热单个 Agent 的缓存"""
        # 创建临时 Agent 实例
        from backend.agents.base_agent import AgentContext
        context = AgentContext(
            session_id="warmup",
            conversation_id="warmup",
            stage="warmup"
        )
        agent = agent_class(context=context)

        # 获取稳定前缀
        prompt = agent.debug_prompt("warmup input")
        cache_key = agent.get_cache_key()

        # 写入缓存
        self.cache.set(cache_key, prompt, "warmup", "warmup")
```

### 5.3 数据库索引

```python
# backend/database/indexes.py

class DatabaseIndexer:
    """数据库索引管理器"""

    INDEXES = [
        # 会话表索引
        "CREATE INDEX IF NOT EXISTS idx_sessions_user_created ON sessions(user_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status)",

        # 消息表索引
        "CREATE INDEX IF NOT EXISTS idx_messages_session_created ON messages(session_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id)",

        # 论题表索引
        "CREATE INDEX IF NOT EXISTS idx_proposals_session ON proposals(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_proposals_score ON proposals(score DESC)",

        # 预算账本索引
        "CREATE INDEX IF NOT EXISTS idx_budget_session_created ON budget_ledger(session_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_budget_model ON budget_ledger(model)",
        "CREATE INDEX IF NOT EXISTS idx_budget_stage ON budget_ledger(stage)",

        # 缓存表索引
        "CREATE INDEX IF NOT EXISTS idx_cache_key ON cache_entries(cache_key)",
        "CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache_entries(expires_at)",

        # 谱系表索引
        "CREATE INDEX IF NOT EXISTS idx_lineage_nodes_session ON lineage_nodes(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_lineage_nodes_type ON lineage_nodes(node_type)",
        "CREATE INDEX IF NOT EXISTS idx_lineage_edges_session ON lineage_edges(session_id)",

        # 审计日志索引
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs(user_id, created_at)"
    ]

    @classmethod
    def create_all(cls, db_conn):
        """创建所有索引"""
        for index_sql in cls.INDEXES:
            db_conn.execute(index_sql)
        db_conn.commit()
        print(f"[Database] 已创建 {len(cls.INDEXES)} 个索引")

    @classmethod
    def analyze(cls, db_conn):
        """分析索引使用情况"""
        cursor = db_conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        )
        indexes = cursor.fetchall()
        print(f"[Database] 当前索引数：{len(indexes)}")
        for name, sql in indexes:
            print(f"  - {name}")
```

### 5.4 前端 CDN

#### 5.4.1 Nginx CDN 配置

```nginx
# 静态文件 CDN 配置
location /static/ {
    alias /opt/thesisminer/frontend/dist/;
    expires 30d;
    add_header Cache-Control "public, immutable";
    add_header X-Content-Type-Options "nosniff";
    add_header X-Frame-Options "SAMEORIGIN";

    # Gzip 压缩
    gzip on;
    gzip_types text/css application/javascript application/json;
    gzip_min_length 1000;
}

# 字体文件
location /static/fonts/ {
    alias /opt/thesisminer/frontend/dist/fonts/;
    expires 1y;
    add_header Cache-Control "public, immutable";
    add_header Access-Control-Allow-Origin "*";
}
```

#### 5.4.2 前端资源哈希

```javascript
// webpack.config.js（或 vite.config.js）

// 文件名添加内容哈希，确保缓存正确
module.exports = {
  output: {
    filename: '[name].[contenthash].js',
    chunkFilename: '[name].[contenthash].js'
  },
  // 分包优化
  optimization: {
    splitChunks: {
      chunks: 'all',
      cacheGroups: {
        vendor: {
          test: /[\\/]node_modules[\\/]/,
          name: 'vendors',
          chunks: 'all'
        },
        d3: {
          test: /[\\/]node_modules[\\/]d3[\\/]/,
          name: 'd3',
          chunks: 'all'
        }
      }
    }
  }
};
```

---

## 6. 安全加固

### 6.1 API Key 加密

```python
# backend/security/encryption.py

import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

class EncryptionManager:
    """加密管理器"""

    def __init__(self, password: str = None, salt: bytes = None):
        password = password or os.getenv("ENCRYPTION_PASSWORD", "default-password")
        salt = salt or os.getenv("ENCRYPTION_SALT", "default-salt").encode()

        # 使用 PBKDF2 派生密钥
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        self.cipher = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        """加密"""
        return self.cipher.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """解密"""
        return self.cipher.decrypt(ciphertext.encode()).decode()
```

### 6.2 HTTPS 配置

#### 6.2.1 使用 Let's Encrypt 获取免费证书

```bash
# 安装 Certbot
$ sudo apt install certbot python3-certbot-nginx

# 获取证书
$ sudo certbot --nginx -d thesisminer.example.com

# 自动续期
$ sudo crontab -e
# 添加：0 12 * * * /usr/bin/certbot renew --quiet
```

#### 6.2.2 Nginx SSL 配置

```nginx
server {
    listen 443 ssl http2;
    server_name thesisminer.example.com;

    # SSL 证书
    ssl_certificate /etc/letsencrypt/live/thesisminer.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/thesisminer.example.com/privkey.pem;

    # SSL 优化
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # HSTS
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # 其他安全头
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
}
```

### 6.3 CORS 策略

```python
# backend/config/cors.py

from fastapi.middleware.cors import CORSMiddleware

class CORSConfig:
    """CORS 配置"""

    # 允许的源
    ALLOWED_ORIGINS = [
        "http://localhost:3000",      # 开发环境
        "http://localhost:8000",      # 本地生产
        "https://thesisminer.example.com",  # 生产环境
    ]

    # 允许的方法
    ALLOWED_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]

    # 允许的头部
    ALLOWED_HEADERS = [
        "Authorization",
        "Content-Type",
        "X-Requested-With",
        "X-CSRF-Token"
    ]

    # 是否允许凭证
    ALLOW_CREDENTIALS = True

    # 预检请求缓存时间（秒）
    MAX_AGE = 3600

def setup_cors(app):
    """配置 CORS"""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORSConfig.ALLOWED_ORIGINS,
        allow_methods=CORSConfig.ALLOWED_METHODS,
        allow_headers=CORSConfig.ALLOWED_HEADERS,
        allow_credentials=CORSConfig.ALLOW_CREDENTIALS,
        max_age=CORSConfig.MAX_AGE
    )
```

### 6.4 速率限制

```python
# backend/middleware/rate_limit.py

import time
from collections import defaultdict
from fastapi import Request, Response, HTTPException
from typing import Dict, Tuple

class RateLimiter:
    """速率限制器（滑动窗口算法）"""

    def __init__(
        self,
        requests_per_minute: int = 60,
        burst: int = 10
    ):
        self.rpm = requests_per_minute
        self.burst = burst
        self.requests: Dict[str, list] = defaultdict(list)

    def check(self, client_id: str) -> Tuple[bool, dict]:
        """检查速率"""
        now = time.time()
        window_start = now - 60  # 1 分钟窗口

        # 清理过期记录
        self.requests[client_id] = [
            t for t in self.requests[client_id] if t > window_start
        ]

        # 检查限制
        current = len(self.requests[client_id])
        if current >= self.rpm:
            return False, {
                "error": "rate_limit_exceeded",
                "retry_after": int(60 - (now - self.requests[client_id][0]))
            }

        # 记录请求
        self.requests[client_id].append(now)

        return True, {
            "remaining": self.rpm - current - 1,
            "reset_at": int(now + 60)
        }

# 使用中间件
async def rate_limit_middleware(request: Request, call_next):
    limiter = request.app.state.rate_limiter
    client_id = request.client.host  # 或使用 API Key

    allowed, info = limiter.check(client_id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="请求过于频繁，请稍后重试",
            headers={"Retry-After": str(info["retry_after"])}
        )

    response = await call_next(request)
    response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
    response.headers["X-RateLimit-Reset"] = str(info["reset_at"])
    return response
```

### 6.5 审计日志

```python
# backend/audit/logger.py

import json
from datetime import datetime
from typing import Optional

class AuditLogger:
    """审计日志记录器"""

    def __init__(self, db_conn):
        self.conn = db_conn

    def log(
        self,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        details: dict = None,
        ip_address: str = None,
        user_agent: str = None
    ):
        """记录审计日志"""
        self.conn.execute(
            """INSERT INTO audit_logs
               (user_id, action, resource_type, resource_id, details,
                ip_address, user_agent, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                action,
                resource_type,
                resource_id,
                json.dumps(details, ensure_ascii=False) if details else None,
                ip_address,
                user_agent,
                datetime.now()
            )
        )
        self.conn.commit()

    def query(
        self,
        user_id: str = None,
        action: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
        limit: int = 100
    ):
        """查询审计日志"""
        query = "SELECT * FROM audit_logs WHERE 1=1"
        params = []

        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        if action:
            query += " AND action = ?"
            params.append(action)
        if start_date:
            query += " AND created_at >= ?"
            params.append(start_date)
        if end_date:
            query += " AND created_at <= ?"
            params.append(end_date)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor = self.conn.execute(query, params)
        return [dict(zip([d[0] for d in cursor.description], r)) for r in cursor.fetchall()]
```

---

## 7. 监控告警

### 7.1 Prometheus 指标

```python
# backend/monitoring/metrics.py

from prometheus_client import Counter, Histogram, Gauge, generate_latest

# 定义指标
REQUEST_COUNT = Counter(
    'thesisminer_requests_total',
    'Total request count',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'thesisminer_request_latency_seconds',
    'Request latency in seconds',
    ['endpoint']
)

ACTIVE_SESSIONS = Gauge(
    'thesisminer_active_sessions',
    'Number of active sessions'
)

TOKEN_USAGE = Counter(
    'thesisminer_tokens_total',
    'Total tokens used',
    ['model', 'stage', 'type']  # type: input/output
)

COST = Counter(
    'thesisminer_cost_usd_total',
    'Total cost in USD',
    ['model', 'stage']
)

CACHE_HITS = Counter(
    'thesisminer_cache_hits_total',
    'Cache hit count',
    ['model']
)

CACHE_MISSES = Counter(
    'thesisminer_cache_misses_total',
    'Cache miss count',
    ['model']
)

def record_request(method: str, endpoint: str, status: int, latency: float):
    """记录请求"""
    REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
    REQUEST_LATENCY.labels(endpoint=endpoint).observe(latency)

def record_token_usage(model: str, stage: str, input_tokens: int, output_tokens: int):
    """记录 Token 使用"""
    TOKEN_USAGE.labels(model=model, stage=stage, type="input").inc(input_tokens)
    TOKEN_USAGE.labels(model=model, stage=stage, type="output").inc(output_tokens)

def record_cost(model: str, stage: str, cost: float):
    """记录成本"""
    COST.labels(model=model, stage=stage).inc(cost)

def record_cache_hit(model: str, hit: bool):
    """记录缓存命中"""
    if hit:
        CACHE_HITS.labels(model=model).inc()
    else:
        CACHE_MISSES.labels(model=model).inc()
```

### 7.2 Grafana 仪表板

```json
{
  "dashboard": {
    "title": "ThesisMiner 监控",
    "panels": [
      {
        "title": "请求速率",
        "type": "graph",
        "query": "rate(thesisminer_requests_total[5m])"
      },
      {
        "title": "请求延迟",
        "type": "graph",
        "query": "histogram_quantile(0.95, rate(thesisminer_request_latency_seconds_bucket[5m]))"
      },
      {
        "title": "Token 使用量",
        "type": "graph",
        "query": "rate(thesisminer_tokens_total[1h])"
      },
      {
        "title": "成本",
        "type": "stat",
        "query": "sum(thesisminer_cost_usd_total)"
      },
      {
        "title": "缓存命中率",
        "type": "gauge",
        "query": "rate(thesisminer_cache_hits_total[5m]) / (rate(thesisminer_cache_hits_total[5m]) + rate(thesisminer_cache_misses_total[5m]))"
      },
      {
        "title": "活跃会话数",
        "type": "stat",
        "query": "thesisminer_active_sessions"
      }
    ]
  }
}
```

### 7.3 告警规则

```yaml
# prometheus/alerts.yml

groups:
  - name: thesisminer
    rules:
      - alert: HighErrorRate
        expr: |
          rate(thesisminer_requests_total{status=~"5.."}[5m])
          / rate(thesisminer_requests_total[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "错误率过高"
          description: "5xx 错误率超过 5%"

      - alert: HighLatency
        expr: |
          histogram_quantile(0.95, rate(thesisminer_request_latency_seconds_bucket[5m])) > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "P95 延迟过高"
          description: "95 分位延迟超过 5 秒"

      - alert: HighCost
        expr: |
          increase(thesisminer_cost_usd_total[1h]) > 50
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "小时成本过高"
          description: "过去 1 小时成本超过 $50"

      - alert: LowCacheHitRate
        expr: |
          rate(thesisminer_cache_hits_total[1h])
          / (rate(thesisminer_cache_hits_total[1h]) + rate(thesisminer_cache_misses_total[1h])) < 0.5
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "缓存命中率低"
          description: "缓存命中率低于 50%"
```

---

## 8. 故障恢复

### 8.1 常见故障处理

| 故障 | 症状 | 处理步骤 |
|------|------|----------|
| 服务无响应 | 请求超时 | 1. 检查进程 `ps aux \| grep thesisminer`<br>2. 查看日志 `journalctl -u thesisminer`<br>3. 重启服务 `systemctl restart thesisminer` |
| 数据库锁定 | `database is locked` | 1. 检查并发数<br>2. 启用 WAL 模式<br>3. 重启服务 |
| 磁盘空间不足 | 写入失败 | 1. 清理日志 `journalctl --vacuum-time=7d`<br>2. 清理旧备份<br>3. 扩展磁盘 |
| API Key 失效 | 401 错误 | 1. 检查 API Key<br>2. 更新 Key<br>3. 重启服务 |
| 内存溢出 | OOM Killed | 1. 减少 Worker 数<br>2. 增加内存<br>3. 检查内存泄漏 |

### 8.2 灾难恢复

```bash
# 1. 停止服务
$ sudo systemctl stop thesisminer

# 2. 恢复数据库
$ python -m backend.backup restore --file thesisminer_20260619_020000_daily.db.gz

# 3. 验证数据完整性
$ python -m backend.database verify

# 4. 重启服务
$ sudo systemctl start thesisminer

# 5. 验证服务
$ curl http://localhost:8000/api/health
```

---

## 附录 A：运维命令速查

```bash
# 服务管理
sudo systemctl start thesisminer       # 启动
sudo systemctl stop thesisminer        # 停止
sudo systemctl restart thesisminer     # 重启
sudo systemctl status thesisminer      # 状态
sudo journalctl -u thesisminer -f      # 查看日志

# Docker 管理
docker-compose up -d                   # 启动
docker-compose down                    # 停止
docker-compose logs -f thesisminer     # 日志
docker-compose restart thesisminer     # 重启

# 数据库管理
python -m backend.database init        # 初始化
python -m backend.database backup      # 备份
python -m backend.database restore     # 恢复
python -m backend.database verify      # 验证

# 模型管理
python -m backend.cli models list      # 列出模型
python -m backend.cli models test      # 测试连通性
python -m backend.cli models routing   # 查看路由

# 预算管理
python -m backend.cli budget summary   # 预算摘要
python -m backend.cli budget export    # 导出报表

# 监控
curl http://localhost:8000/api/health  # 健康检查
curl http://localhost:8000/metrics     # Prometheus 指标
```

---

## 附录 B：配置文件清单

| 文件 | 用途 |
|------|------|
| `.env` | 环境变量配置 |
| `docker-compose.yml` | Docker 编排 |
| `Dockerfile` | Docker 镜像构建 |
| `nginx/conf.d/thesisminer.conf` | Nginx 配置 |
| `/etc/systemd/system/thesisminer.service` | systemd 服务 |
| `prometheus/prometheus.yml` | Prometheus 配置 |
| `prometheus/alerts.yml` | 告警规则 |
| `backend/config/models.py` | 模型配置 |
| `backend/config/concurrency.py` | 并发配置 |
| `backend/config/cache.py` | 缓存配置 |
| `backend/config/cors.py` | CORS 配置 |

---

> 本指南最后更新：2026-06-19
> 适用于 ThesisMiner v8.0 及以上版本
> 如有问题，请查阅故障排查指南或联系系统管理员
