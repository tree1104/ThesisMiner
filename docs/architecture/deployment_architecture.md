# ThesisMiner v8.0 部署架构文档

> **文档版本**: v8.0.0
> **最后更新**: 2026-06-20
> **文档状态**: 正式发布
> **维护者**: ThesisMiner 架构组
> **适用范围**: ThesisMiner v8.0 全量部署场景

---

## 目录

1. [文档概述](#1-文档概述)
2. [部署架构总览](#2-部署架构总览)
3. [开发环境部署](#3-开发环境部署)
4. [测试环境部署](#4-测试环境部署)
5. [生产环境部署](#5-生产环境部署)
6. [Docker 容器化](#6-docker-容器化)
7. [Kubernetes 编排](#7-kubernetes-编排)
8. [服务网格 (Service Mesh)](#8-服务网格-service-mesh)
9. [负载均衡](#9-负载均衡)
10. [自动扩缩容](#10-自动扩缩容)
11. [滚动更新与发布策略](#11-滚动更新与发布策略)
12. [监控告警体系](#12-监控告警体系)
13. [日志聚合](#13-日志聚合)
14. [链路追踪](#14-链路追踪)
15. [数据库部署](#15-数据库部署)
16. [缓存部署](#16-缓存部署)
17. [消息队列部署](#17-消息队列部署)
18. [安全部署](#18-安全部署)
19. [网络隔离](#19-网络隔离)
20. [访问控制](#20-访问控制)
21. [灾备方案](#21-灾备方案)
22. [故障恢复](#22-故障恢复)
23. [业务连续性](#23-业务连续性)
24. [部署检查清单](#24-部署检查清单)
25. [附录](#25-附录)

---

## 1. 文档概述

### 1.1 文档目的

本文档详细描述 ThesisMiner v8.0 系统在不同环境（开发、测试、生产）下的部署架构、容器化方案、编排策略、服务网格、负载均衡、自动扩缩容、滚动更新、监控告警、日志聚合、链路追踪、数据库与缓存部署、安全与网络隔离、灾备与业务连续性等关键内容。

文档面向以下读者：

- **DevOps 工程师**：负责系统部署、运维、监控
- **SRE 工程师**：负责系统可靠性、灾备、故障恢复
- **后端工程师**：负责服务实现与部署配置
- **架构师**：负责整体架构评审与演进
- **安全工程师**：负责安全合规与访问控制

### 1.2 文档范围

本文档涵盖：

- 三套环境（dev / test / prod）的部署差异与统一治理
- Docker 多阶段构建与镜像优化
- Kubernetes 资源编排（Deployment / StatefulSet / DaemonSet / HPA / PDB）
- Istio 服务网格治理（流量管理 / mTLS / 熔断 / 重试）
- 四层与七层负载均衡策略
- 基于 CPU / 内存 / 自定义指标的自动扩缩容
- 滚动更新、蓝绿部署、金丝雀发布
- Prometheus + Grafana + Alertmanager 监控告警
- Loki + Promtail 日志聚合
- OpenTelemetry + Jaeger 链路追踪
- SQLite WAL 模式部署与备份
- Redis 多级缓存与哨兵高可用
- 消息队列选型与部署
- 安全加固（镜像签名 / SecurityContext / NetworkPolicy / RBAC）
- 网络隔离与访问控制
- 灾备方案与业务连续性计划（BCP）

### 1.3 术语表

| 术语 | 英文全称 | 含义 |
|------|----------|------|
| K8s | Kubernetes | 容器编排平台 |
| HPA | Horizontal Pod Autoscaler | 水平 Pod 自动扩缩容 |
| VPA | Vertical Pod Autoscaler | 垂直 Pod 自动扩缩容 |
| PDB | Pod Disruption Budget | Pod 中断预算 |
| LLM | Large Language Model | 大语言模型 |
| WAL | Write-Ahead Logging | 预写式日志 |
| mTLS | mutual TLS | 双向 TLS 加密 |
| SLO | Service Level Objective | 服务等级目标 |
| SLA | Service Level Agreement | 服务等级协议 |
| RTO | Recovery Time Objective | 恢复时间目标 |
| RPO | Recovery Point Objective | 恢复点目标 |
| BCP | Business Continuity Plan | 业务连续性计划 |
| DR | Disaster Recovery | 灾难恢复 |

### 1.4 设计原则

1. **环境一致性**：dev / test / prod 三套环境镜像一致，仅配置差异
2. **不可变基础设施**：所有部署基于镜像，禁止在线修改
3. **声明式配置**：使用 YAML 描述期望状态，由控制器收敛
4. **零信任安全**：所有服务间通信启用 mTLS，最小权限原则
5. **可观测优先**：监控、日志、追踪三件套全覆盖
6. **渐进式发布**：金丝雀 → 蓝绿 → 全量，可回滚
7. **故障域隔离**：通过命名空间、节点池、可用区隔离故障
8. **成本可控**：开发测试环境按需启停，生产环境按容量规划

---

## 2. 部署架构总览

### 2.1 整体部署拓扑

```
                              ┌─────────────────────────────────┐
                              │        全球 DNS (Cloudflare)     │
                              │   thesisminer.example.com        │
                              └───────────────┬─────────────────┘
                                              │
                                              ▼
                              ┌─────────────────────────────────┐
                              │     WAF + DDoS 防护 (Cloudflare) │
                              │   - SQL 注入拦截                  │
                              │   - XSS 过滤                     │
                              │   - CC 攻击防护                  │
                              └───────────────┬─────────────────┘
                                              │
                                              ▼
                              ┌─────────────────────────────────┐
                              │   全球负载均衡 (Geo LB)           │
                              │   - 主站点: 北京 (cn-north-1)    │
                              │   - 备站点: 上海 (cn-east-1)     │
                              └───────────────┬─────────────────┘
                                              │
                       ┌──────────────────────┴──────────────────────┐
                       │                                               │
                       ▼                                               ▼
        ┌──────────────────────────────┐              ┌──────────────────────────────┐
        │   北京主集群 (cn-north-1)     │              │   上海备集群 (cn-east-1)     │
        │   K8s v1.28 + Istio 1.20     │              │   K8s v1.28 + Istio 1.20     │
        │                              │              │                              │
        │  ┌────────────────────────┐  │              │  ┌────────────────────────┐  │
        │  │  Ingress (Nginx)        │  │              │  │  Ingress (Nginx)        │  │
        │  │  TLS 终止 + 路由        │  │              │  │  TLS 终止 + 路由        │  │
        │  └──────────┬─────────────┘  │              │  └──────────┬─────────────┘  │
        │             │                 │              │             │                 │
        │  ┌──────────▼─────────────┐  │              │  ┌──────────▼─────────────┐  │
        │  │  FastAPI 服务 Pod       │  │              │  │  FastAPI 服务 Pod       │  │
        │  │  (Orchestrator + 5     │  │              │  │  (Orchestrator + 5     │  │
        │  │   sub-agents)          │  │              │  │   sub-agents)          │  │
        │  └──────────┬─────────────┘  │              │  └──────────┬─────────────┘  │
        │             │                 │              │             │                 │
        │  ┌──────────▼─────────────┐  │              │  ┌──────────▼─────────────┐  │
        │  │  数据层                │  │              │  │  数据层                │  │
        │  │  - SQLite (StatefulSet)│  │              │  │  - SQLite (StatefulSet)│  │
        │  │  - Redis (Sentinel)    │  │              │  │  - Redis (Sentinel)    │  │
        │  └────────────────────────┘  │              │  └────────────────────────┘  │
        └──────────────────────────────┘              └──────────────────────────────┘
```

### 2.2 组件清单

| 组件 | 角色 | 部署形态 | 副本数 (prod) | 资源配额 (CPU/Mem) |
|------|------|----------|---------------|--------------------|
| Orchestrator | 主调度 Agent | Deployment | 3 | 1C / 2Gi |
| Reasoner Agent | 推理子 Agent | Deployment | 2 | 2C / 4Gi |
| Writer Agent | 写作子 Agent | Deployment | 2 | 1C / 2Gi |
| Critic Agent | 评审子 Agent | Deployment | 2 | 1C / 2Gi |
| Searcher Agent | 检索子 Agent | Deployment | 2 | 1C / 2Gi |
| Mentor Agent | 指导子 Agent | Deployment | 2 | 1C / 2Gi |
| FastAPI Gateway | API 网关 | Deployment | 3 | 1C / 2Gi |
| SQLite | 主数据库 | StatefulSet | 1 (主) | 2C / 4Gi |
| Redis | 缓存 | StatefulSet | 3 (哨兵) | 1C / 2Gi |
| Prometheus | 监控 | StatefulSet | 1 | 1C / 4Gi |
| Grafana | 可视化 | Deployment | 1 | 0.5C / 1Gi |
| Loki | 日志 | StatefulSet | 1 | 1C / 4Gi |
| Jaeger | 追踪 | StatefulSet | 1 | 1C / 2Gi |
| Nginx Ingress | 入口 | DaemonSet | 3 | 0.5C / 1Gi |

### 2.3 网络分区

```
┌─────────────────────────────────────────────────────────────────────┐
│                        公网 (0.0.0.0/0)                              │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  DMZ 区 (10.10.0.0/16)                                       │    │
│  │  - WAF / DDoS 防护                                           │    │
│  │  - 全球 LB                                                    │    │
│  │  - Ingress Controller (仅 80/443)                            │    │
│  └──────────────────────────┬──────────────────────────────────┘    │
└─────────────────────────────┼───────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────────┐
│  应用区 (10.20.0.0/16) - K8s 集群                                   │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  前端命名空间 (frontend) - Nginx (静态资源)                   │    │
│  └──────────────────────────┬──────────────────────────────────┘    │
│  ┌──────────────────────────▼──────────────────────────────────┐    │
│  │  后端命名空间 (backend) - FastAPI / Orchestrator / 5 agents │    │
│  └──────────────────────────┬──────────────────────────────────┘    │
│  ┌──────────────────────────▼──────────────────────────────────┐    │
│  │  数据命名空间 (data) - SQLite / Redis                        │    │
│  └──────────────────────────┬──────────────────────────────────┘    │
│  ┌──────────────────────────▼──────────────────────────────────┐    │
│  │  可观测命名空间 (observability) - Prometheus/Grafana/Loki    │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────────┐
│  外联区 (10.30.0.0/16) - 出口网关                                   │
│  - DeepSeek LLM API (HTTPS 出站)                                   │
│  - 学术数据库 API (CNKI / 万方 / Semantic Scholar)                  │
│  - 对象存储 (S3 兼容)                                              │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.4 部署形态对比

| 部署形态 | 适用场景 | 优点 | 缺点 | 推荐度 |
|----------|----------|------|------|--------|
| 原生进程 | 本地开发 | 启动快、调试方便 | 无法水平扩展 | ★★ |
| Docker Compose | 单机测试 | 一键启动、环境隔离 | 单点故障 | ★★★ |
| K8s 单集群 | 中小规模生产 | 自愈、弹性、声明式 | 运维复杂度高 | ★★★★★ |
| K8s 多集群 | 大规模 / 容灾 | 异地容灾、地理路由 | 成本高、同步复杂 | ★★★★ |
| Serverless | 流量波动大 | 按量付费、零运维 | 冷启动、有状态难 | ★★ |

---

## 3. 开发环境部署

### 3.1 系统要求

| 项目 | 最低要求 | 推荐配置 |
|------|----------|----------|
| 操作系统 | Windows 10 / macOS 12 / Ubuntu 20.04 | Windows 11 / macOS 14 / Ubuntu 22.04 |
| CPU | 4 核 | 8 核 |
| 内存 | 8 GB | 16 GB |
| 磁盘 | 20 GB 可用空间 | 50 GB SSD |
| Python | 3.10 | 3.11 |
| Node.js | 18 LTS | 20 LTS |
| Docker | 24.0 | 25.0 |
| Git | 2.40 | 2.43 |

### 3.2 原生部署（推荐用于日常开发）

```bash
# 1. 克隆代码仓库
git clone https://github.com/thesisminer/thesisminer.git
cd thesisminer

# 2. 创建 Python 虚拟环境
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 3. 安装后端依赖
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 4. 安装前端依赖
cd frontend
npm install
cd ..

# 5. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY 等配置

# 6. 初始化数据库
python -m backend.database init

# 7. 启动后端服务（热重载模式）
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 8. 启动前端开发服务器（另开终端）
cd frontend
npm run dev
```

### 3.3 .env 配置示例

```ini
# ========== 基础配置 ==========
APP_ENV=development
APP_DEBUG=true
APP_HOST=0.0.0.0
APP_PORT=8000
APP_LOG_LEVEL=DEBUG

# ========== 数据库配置 ==========
DATABASE_URL=sqlite:///./data/thesisminer.db
DATABASE_WAL_MODE=true
DATABASE_JOURNAL_SIZE_LIMIT=67108864

# ========== LLM 配置 ==========
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_TIMEOUT=60
DEEPSEEK_MAX_RETRIES=3
DEEPSEEK_CACHE_ENABLED=true

# ========== 缓存配置 ==========
REDIS_URL=redis://localhost:6379/0
CACHE_TTL_DEFAULT=3600
CACHE_L1_ENABLED=true
CACHE_L2_ENABLED=true

# ========== 监控配置 ==========
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=9090
JAEGER_ENABLED=false

# ========== 安全配置 ==========
SECRET_KEY=dev-secret-key-change-in-production
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
RATE_LIMIT_ENABLED=false
```

### 3.4 Docker Compose 部署

```yaml
# docker-compose.dev.yml
version: "3.9"

services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile.dev
    container_name: thesisminer-backend
    ports:
      - "8000:8000"
    volumes:
      - ./:/app
      - ./data:/app/data
    environment:
      - APP_ENV=development
      - APP_DEBUG=true
      - DATABASE_URL=sqlite:///./data/thesisminer.db
      - REDIS_URL=redis://redis:6379/0
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
    depends_on:
      - redis
    command: uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
    networks:
      - thesisminer-net

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.dev
    container_name: thesisminer-frontend
    ports:
      - "5173:5173"
    volumes:
      - ./frontend:/app
      - /app/node_modules
    environment:
      - VITE_API_BASE_URL=http://localhost:8000
    command: npm run dev -- --host 0.0.0.0
    networks:
      - thesisminer-net

  redis:
    image: redis:7.2-alpine
    container_name: thesisminer-redis
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    networks:
      - thesisminer-net

  prometheus:
    image: prom/prometheus:v2.48.0
    container_name: thesisminer-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./config/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    networks:
      - thesisminer-net

  grafana:
    image: grafana/grafana:10.2.0
    container_name: thesisminer-grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-data:/var/lib/grafana
    depends_on:
      - prometheus
    networks:
      - thesisminer-net

volumes:
  redis-data:
  prometheus-data:
  grafana-data:

networks:
  thesisminer-net:
    driver: bridge
```

启动命令：

```bash
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml logs -f backend
```

### 3.5 VS Code 开发配置

```json
// .vscode/launch.json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Backend: FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["backend.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
      "envFile": "${workspaceFolder}/.env",
      "console": "integratedTerminal",
      "justMyCode": true
    },
    {
      "name": "Backend: pytest",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": ["tests/", "-v", "--cov=backend", "--cov-report=html"],
      "envFile": "${workspaceFolder}/.env",
      "console": "integratedTerminal"
    },
    {
      "name": "Frontend: Vite",
      "type": "node",
      "request": "launch",
      "runtimeExecutable": "npm",
      "runtimeArgs": ["run", "dev"],
      "cwd": "${workspaceFolder}/frontend",
      "console": "integratedTerminal"
    }
  ]
}
```

### 3.6 Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
        args: ['--maxkb=1024']
      - id: check-merge-conflict
      - id: detect-private-key

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.7
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.1
    hooks:
      - id: mypy
        additional_dependencies: [types-requests, pydantic]
        args: [--config-file=pyproject.toml]

  - repo: https://github.com/pycqa/bandit
    rev: 1.7.5
    hooks:
      - id: bandit
        args: ['-c', 'pyproject.toml', '-r', 'backend/']
        additional_dependencies: ['bandit[toml]']
```

### 3.7 开发环境数据初始化

```python
# scripts/dev_init.py
"""开发环境数据初始化脚本"""
import asyncio
import json
from pathlib import Path

from backend.database import init_db, get_session
from backend.sessions.session_manager import SessionManager
from backend.knowledge.knowledge_base import KnowledgeBase


async def main():
    # 1. 初始化数据库表结构
    await init_db()
    print("[OK] 数据库表结构初始化完成")

    # 2. 导入示例会话
    sample_dir = Path("scripts/samples")
    async with get_session() as session:
        manager = SessionManager(session)
        for sample_file in sample_dir.glob("*.json"):
            with open(sample_file, encoding="utf-8") as f:
                data = json.load(f)
            await manager.create_session(**data)
            print(f"[OK] 导入会话: {sample_file.name}")

    # 3. 构建知识库索引
    kb = KnowledgeBase()
    await kb.build_index("data/thesis_samples/")
    print(f"[OK] 知识库索引构建完成，共 {kb.doc_count} 篇文档")

    # 4. 预热 Prompt 缓存
    from backend.ai.prompt_cache import PromptCache
    cache = PromptCache()
    await cache.warmup()
    print(f"[OK] Prompt 缓存预热完成，{cache.size} 条目")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 4. 测试环境部署

### 4.1 测试环境架构

测试环境用于自动化测试、回归测试、性能测试、集成测试。与生产环境保持架构一致，但资源配额缩减。

```
┌─────────────────────────────────────────────────────────────────┐
│  测试环境 K8s 集群 (test-cluster)                                │
│  节点池: 2 个 worker (4C8G)                                      │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  namespace: test-thesisminer                              │   │
│  │  - backend (1 replica)                                    │   │
│  │  - frontend (1 replica)                                   │   │
│  │  - sqlite (1 replica, ephemeral storage)                 │   │
│  │  - redis (1 replica)                                      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  namespace: test-perf                                     │   │
│  │  - locust-master / locust-worker                          │   │
│  │  - k6 runner                                              │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  namespace: test-ci                                       │   │
│  │  - Jenkins agent / GitHub Actions runner                 │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 命名空间隔离

```yaml
# k8s/test/namespaces.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: test-thesisminer
  labels:
    environment: test
    app: thesisminer
    istio-injection: enabled
---
apiVersion: v1
kind: Namespace
metadata:
  name: test-perf
  labels:
    environment: test
    purpose: performance
---
apiVersion: v1
kind: Namespace
metadata:
  name: test-ci
  labels:
    environment: test
    purpose: ci
```

### 4.3 测试环境资源配额

```yaml
# k8s/test/resourcequota.yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: test-thesisminer-quota
  namespace: test-thesisminer
spec:
  hard:
    requests.cpu: "4"
    requests.memory: 8Gi
    limits.cpu: "8"
    limits.memory: 16Gi
    persistentvolumeclaims: "5"
    services.loadbalancers: "1"
    services.nodeports: "0"
---
apiVersion: v1
kind: LimitRange
metadata:
  name: test-thesisminer-limits
  namespace: test-thesisminer
spec:
  limits:
    - type: Container
      default:
        cpu: 500m
        memory: 1Gi
      defaultRequest:
        cpu: 100m
        memory: 256Mi
      max:
        cpu: 2
        memory: 4Gi
      min:
        cpu: 50m
        memory: 128Mi
```

### 4.4 CI/CD 流水线

```yaml
# .github/workflows/test-deploy.yml
name: Test Environment Deploy

on:
  push:
    branches: [develop, release/*]
  pull_request:
    branches: [main, develop]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: thesisminer/thesisminer

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      - name: Lint with ruff
        run: ruff check backend/ tests/
      - name: Format check
        run: ruff format --check backend/ tests/
      - name: Type check with mypy
        run: mypy backend/
      - name: Run unit tests
        run: pytest tests/unit/ -v --cov=backend --cov-report=xml
      - name: Run integration tests
        run: pytest tests/integration/ -v
      - name: Security scan with bandit
        run: bandit -r backend/ -f json -o bandit-report.json
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml

  build-and-push:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/develop' || startsWith(github.ref, 'refs/heads/release/')
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      - name: Login to registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=sha,prefix=test-
            type=raw,value=test-latest
      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./Dockerfile
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy-test:
    needs: build-and-push
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/develop'
    environment: test
    steps:
      - uses: actions/checkout@v4
      - name: Configure kubectl
        run: |
          echo "${{ secrets.TEST_KUBECONFIG }}" | base64 -d > kubeconfig
          export KUBECONFIG=$(pwd)/kubeconfig
      - name: Deploy to test cluster
        run: |
          kubectl set image deployment/thesisminer-backend \
            backend=$REGISTRY/$IMAGE_NAME:test-${{ github.sha }} \
            -n test-thesisminer
          kubectl rollout status deployment/thesisminer-backend \
            -n test-thesisminer --timeout=300s
      - name: Run smoke tests
        run: |
          kubectl -n test-thesisminer port-forward svc/thesisminer 8000:8000 &
          sleep 10
          curl -f http://localhost:8000/health || exit 1
          curl -f http://localhost:8000/api/v1/sessions || exit 1
```

### 4.5 测试数据管理

```python
# scripts/test_data_manager.py
"""测试环境数据管理：定期清理、生成测试数据"""
import os
import random
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from backend.database import get_session
from backend.sessions.session_manager import SessionManager


async def cleanup_stale_data(days: int = 7):
    """清理 N 天前的测试数据"""
    cutoff = datetime.utcnow() - timedelta(days=days)
    async with get_session() as session:
        manager = SessionManager(session)
        deleted = await manager.delete_before(cutoff)
        print(f"[OK] 清理 {deleted} 条过期测试数据")


async def seed_test_data(count: int = 100):
    """生成测试数据"""
    async with get_session() as session:
        manager = SessionManager(session)
        for i in range(count):
            await manager.create_session(
                title=f"测试会话 #{i}",
                topic=random.choice(["人工智能", "机器学习", "深度学习", "自然语言处理"]),
                user_id=f"test-user-{random.randint(1, 10)}",
            )
        print(f"[OK] 生成 {count} 条测试数据")


if __name__ == "__main__":
    action = os.getenv("ACTION", "cleanup")
    if action == "cleanup":
        asyncio.run(cleanup_stale_data())
    elif action == "seed":
        asyncio.run(seed_test_data())
```

### 4.6 测试环境清理 CronJob

```yaml
# k8s/test/cleanup-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: test-data-cleanup
  namespace: test-thesisminer
spec:
  schedule: "0 2 * * *"  # 每天凌晨 2 点
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: cleanup
              image: ghcr.io/thesisminer/thesisminer:test-latest
              command: ["python", "-m", "scripts.test_data_manager"]
              env:
                - name: ACTION
                  value: "cleanup"
                - name: DATABASE_URL
                  valueFrom:
                    secretKeyRef:
                      name: thesisminer-secrets
                      key: database-url
          restartPolicy: OnFailure
```

---

## 5. 生产环境部署

### 5.1 生产环境要求

| 项目 | 要求 |
|------|------|
| K8s 版本 | v1.28+ |
| 节点数 | ≥ 6 (3 master + 3 worker) |
| 可用区 | ≥ 2 (跨 AZ 部署) |
| 节点规格 | worker: 8C16G × 3, data: 16C32G × 3 |
| 存储 | SSD, IOPS ≥ 3000 |
| 网络 | VPC + 私有子网 + NAT 网关 |
| 负载均衡 | L4 LB (TCP) + L7 LB (HTTPS) |
| 证书 | Let's Encrypt 或商业证书 |
| 监控 | Prometheus + Grafana + Alertmanager |
| 日志 | Loki + Promtail |
| 追踪 | Jaeger |

### 5.2 节点池规划

```
┌─────────────────────────────────────────────────────────────────┐
│  生产集群 (prod-cluster)                                          │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Master 节点池 (master-pool)                              │   │
│  │  - 3 × 4C8G (跨 3 个 AZ)                                  │   │
│  │  - etcd / kube-apiserver / kube-controller-manager        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  应用节点池 (app-pool)                                     │   │
│  │  - 3 × 8C16G (跨 3 个 AZ)                                 │   │
│  │  - FastAPI / Orchestrator / 5 sub-agents / Ingress        │   │
│  │  - 污点: dedicated=app:NoSchedule                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  数据节点池 (data-pool)                                    │   │
│  │  - 3 × 16C32G + 500GB SSD (跨 3 个 AZ)                    │   │
│  │  - SQLite / Redis / Prometheus / Loki                     │   │
│  │  - 污点: dedicated=data:NoSchedule                         │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  监控节点池 (monitor-pool)                                 │   │
│  │  - 2 × 4C8G                                                │   │
│  │  - Grafana / Alertmanager / Jaeger                        │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 5.3 生产环境 ConfigMap

```yaml
# k8s/prod/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: thesisminer-config
  namespace: production
data:
  APP_ENV: "production"
  APP_DEBUG: "false"
  APP_HOST: "0.0.0.0"
  APP_PORT: "8000"
  APP_LOG_LEVEL: "INFO"
  DATABASE_WAL_MODE: "true"
  DATABASE_JOURNAL_SIZE_LIMIT: "134217728"
  DATABASE_BUSY_TIMEOUT: "5000"
  DEEPSEEK_BASE_URL: "https://api.deepseek.com/v1"
  DEEPSEEK_MODEL: "deepseek-chat"
  DEEPSEEK_TIMEOUT: "60"
  DEEPSEEK_MAX_RETRIES: "3"
  DEEPSEEK_CACHE_ENABLED: "true"
  CACHE_TTL_DEFAULT: "3600"
  CACHE_L1_ENABLED: "true"
  CACHE_L2_ENABLED: "true"
  PROMETHEUS_ENABLED: "true"
  JAEGER_ENABLED: "true"
  JAEGER_AGENT_HOST: "jaeger-agent.observability.svc.cluster.local"
  RATE_LIMIT_ENABLED: "true"
  RATE_LIMIT_RPM: "60"
  CORS_ORIGINS: "https://thesisminer.example.com"
---
apiVersion: v1
kind: Secret
metadata:
  name: thesisminer-secrets
  namespace: production
type: Opaque
stringData:
  DEEPSEEK_API_KEY: "sk-prod-xxxxxxxxxxxxxxxxxxxxxxxx"
  SECRET_KEY: "prod-secret-key-256-bit-random"
  DATABASE_URL: "sqlite:///./data/thesisminer.db"
  REDIS_URL: "redis://redis-sentinel.data.svc.cluster.local:26379/0"
  GRAFANA_ADMIN_PASSWORD: "strong-password-here"
```

### 5.4 生产环境 Ingress

```yaml
# k8s/prod/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: thesisminer-ingress
  namespace: production
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/ssl-ciphers: "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384"
    nginx.ingress.kubernetes.io/ssl-protocols: "TLSv1.2 TLSv1.3"
    nginx.ingress.kubernetes.io/proxy-body-size: "50m"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "120"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "120"
    nginx.ingress.kubernetes.io/proxy-connect-timeout: "10"
    nginx.ingress.kubernetes.io/configuration-snippet: |
      more_set_headers "X-Content-Type-Options: nosniff";
      more_set_headers "X-Frame-Options: SAMEORIGIN";
      more_set_headers "X-XSS-Protection: 1; mode=block";
      more_set_headers "Referrer-Policy: strict-origin-when-cross-origin";
      more_set_headers "Strict-Transport-Security: max-age=31536000; includeSubDomains; preload";
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - thesisminer.example.com
      secretName: thesisminer-tls
  rules:
    - host: thesisminer.example.com
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: thesisminer-backend
                port:
                  number: 8000
          - path: /
            pathType: Prefix
            backend:
              service:
                name: thesisminer-frontend
                port:
                  number: 80
```

### 5.5 生产环境 Service

```yaml
# k8s/prod/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: thesisminer-backend
  namespace: production
  labels:
    app: thesisminer
    component: backend
spec:
  type: ClusterIP
  selector:
    app: thesisminer
    component: backend
  ports:
    - name: http
      port: 8000
      targetPort: 8000
      protocol: TCP
---
apiVersion: v1
kind: Service
metadata:
  name: thesisminer-frontend
  namespace: production
  labels:
    app: thesisminer
    component: frontend
spec:
  type: ClusterIP
  selector:
    app: thesisminer
    component: frontend
  ports:
    - name: http
      port: 80
      targetPort: 80
      protocol: TCP
```

### 5.6 生产环境 PDB

```yaml
# k8s/prod/pdb.yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: thesisminer-backend-pdb
  namespace: production
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: thesisminer
      component: backend
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: thesisminer-frontend-pdb
  namespace: production
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: thesisminer
      component: frontend
```

### 5.7 生产环境 HPA

```yaml
# k8s/prod/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: thesisminer-backend-hpa
  namespace: production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: thesisminer-backend
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
    - type: Pods
      pods:
        metric:
          name: http_requests_per_second
        target:
          type: AverageValue
          averageValue: "100"
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
        - type: Percent
          value: 100
          periodSeconds: 60
        - type: Pods
          value: 4
          periodSeconds: 60
      selectPolicy: Max
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 25
          periodSeconds: 60
      selectPolicy: Min
```

### 5.8 生产环境 NetworkPolicy

```yaml
# k8s/prod/networkpolicy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: thesisminer-backend-policy
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: thesisminer
      component: backend
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: production
          podSelector:
            matchLabels:
              app: thesisminer
              component: frontend
        - namespaceSelector:
            matchLabels:
              name: production
          podSelector:
            matchLabels:
              app: thesisminer
              component: ingress
      ports:
        - protocol: TCP
          port: 8000
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: thesisminer
              component: sqlite
      ports:
        - protocol: TCP
          port: 5432
    - to:
        - podSelector:
            matchLabels:
              app: redis
      ports:
        - protocol: TCP
          port: 6379
    - to:
        - namespaceSelector: {}
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
            except:
              - 10.0.0.0/8
              - 172.16.0.0/12
              - 192.168.0.0/16
      ports:
        - protocol: TCP
          port: 443
```

---

## 6. Docker 容器化

### 6.1 多阶段 Dockerfile

```dockerfile
# Dockerfile
# ========== Stage 1: Builder ==========
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt requirements-prod.txt ./

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --upgrade pip && \
    pip install -r requirements.txt -r requirements-prod.txt

# ========== Stage 2: Frontend Builder ==========
FROM node:20-alpine AS frontend-builder
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ========== Stage 3: Runtime ==========
FROM python:3.11-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    libsqlite3-0 \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r thesisminer && useradd -r -g thesisminer thesisminer

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY --from=frontend-builder /app/dist /app/frontend/dist

WORKDIR /app
COPY --chown=thesisminer:thesisminer backend/ ./backend/
COPY --chown=thesisminer:thesisminer config/ ./config/
COPY --chown=thesisminer:thesisminer scripts/ ./scripts/

RUN mkdir -p /app/data && chown -R thesisminer:thesisminer /app/data
USER thesisminer
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### 6.2 .dockerignore

```
.git
.gitignore
.github
.vscode
.idea
.venv
__pycache__
*.pyc
*.pyo
*.pyd
.pytest_cache
.mypy_cache
.ruff_cache
htmlcov
.coverage
coverage.xml
*.egg-info
node_modules
frontend/node_modules
frontend/dist
data/
logs/
*.log
*.db
*.sqlite
*.sqlite3
.env
.env.local
.env.*.local
docs/
tests/
.trae/
*.tar.gz
*.zip
```

### 6.3 镜像构建脚本

```bash
#!/bin/bash
# scripts/build_image.sh
set -euo pipefail

IMAGE_NAME="ghcr.io/thesisminer/thesisminer"
VERSION="${1:-$(git describe --tags --always --dirty)}"
PLATFORMS="linux/amd64,linux/arm64"

echo "[1/4] 登录镜像仓库..."
echo "${GITHUB_TOKEN}" | docker login ghcr.io -u "${GITHUB_USER}" --password-stdin

echo "[2/4] 创建 Buildx builder..."
docker buildx create --name thesisminer-builder --use --driver docker-container || true

echo "[3/4] 构建多架构镜像..."
docker buildx build \
    --platform "${PLATFORMS}" \
    --tag "${IMAGE_NAME}:${VERSION}" \
    --tag "${IMAGE_NAME}:latest" \
    --build-arg BUILD_DATE="$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
    --build-arg VCS_REF="$(git rev-parse --short HEAD)" \
    --build-arg VERSION="${VERSION}" \
    --label "org.opencontainers.image.title=ThesisMiner" \
    --label "org.opencontainers.image.version=${VERSION}" \
    --label "org.opencontainers.image.source=https://github.com/thesisminer/thesisminer" \
    --push \
    .

echo "[4/4] 镜像签名 (cosign)..."
cosign sign --yes "${IMAGE_NAME}:${VERSION}"
cosign sign --yes "${IMAGE_NAME}:latest"

echo "[OK] 镜像构建并签名完成: ${IMAGE_NAME}:${VERSION}"
```

### 6.4 镜像安全扫描

```yaml
# .github/workflows/security-scan.yml
name: Container Security Scan

on:
  push:
    branches: [main, develop]
  schedule:
    - cron: "0 6 * * 1"

jobs:
  trivy-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build image
        run: docker build -t thesisminer:scan .
      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: "thesisminer:scan"
          format: "sarif"
          output: "trivy-results.sarif"
          severity: "CRITICAL,HIGH"
          exit-code: "1"
      - name: Upload Trivy results
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: "trivy-results.sarif"

  grype-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build image
        run: docker build -t thesisminer:scan .
      - name: Run Grype
        uses: anchore/scan-action@v3
        with:
          image: "thesisminer:scan"
          fail-build: true
          severity-cutoff: high
```

### 6.5 镜像大小优化对比

| 优化措施 | 镜像大小 | 减幅 |
|----------|----------|------|
| 基础镜像 python:3.11 (无优化) | 1.2 GB | - |
| 切换 python:3.11-slim | 450 MB | -62% |
| 多阶段构建（剥离构建依赖） | 280 MB | -77% |
| 删除 .pyc / __pycache__ | 265 MB | -78% |
| 使用 python:3.11-alpine | 180 MB | -85% |
| 启用 strip + UPX 压缩 | 145 MB | -88% |

---

## 7. Kubernetes 编排

### 7.1 K8s 架构

```
┌─────────────────────────────────────────────────────────────────┐
│  Kubernetes 集群架构                                             │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Control Plane (Master)                                   │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │   │
│  │  │ kube-        │  │ kube-        │  │ kube-        │    │   │
│  │  │ apiserver    │  │ controller-  │  │ scheduler    │    │   │
│  │  │              │  │ manager      │  │              │    │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘    │   │
│  │  ┌──────────────────────────────────────────────────┐    │   │
│  │  │  etcd (3 节点 Raft 集群)                          │    │   │
│  │  └──────────────────────────────────────────────────┘    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌───────────────────────────┼──────────────────────────────┐   │
│  │  Worker Nodes              ▼                              │   │
│  │  ┌──────────────────────────────────────────────────┐    │   │
│  │  │  kubelet + kube-proxy + containerd               │    │   │
│  │  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  │    │   │
│  │  │  │ Pod:       │  │ Pod:       │  │ Pod:       │  │    │   │
│  │  │  │ backend    │  │ orchestrator│  │ reasoner  │  │    │   │
│  │  │  └────────────┘  └────────────┘  └────────────┘  │    │   │
│  │  └──────────────────────────────────────────────────┘    │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 Backend Deployment

```yaml
# k8s/prod/backend-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: thesisminer-backend
  namespace: production
  labels:
    app: thesisminer
    component: backend
    version: v8.0.0
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: thesisminer
      component: backend
  template:
    metadata:
      labels:
        app: thesisminer
        component: backend
        version: v8.0.0
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        prometheus.io/path: "/metrics"
        sidecar.istio.io/inject: "true"
    spec:
      serviceAccountName: thesisminer-backend
      terminationGracePeriodSeconds: 60
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                labelSelector:
                  matchLabels:
                    app: thesisminer
                    component: backend
                topologyKey: kubernetes.io/hostname
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
              - matchExpressions:
                  - key: node-pool
                    operator: In
                    values: ["app"]
      tolerations:
        - key: "dedicated"
          operator: "Equal"
          value: "app"
          effect: "NoSchedule"
      containers:
        - name: backend
          image: ghcr.io/thesisminer/thesisminer:v8.0.0
          imagePullPolicy: IfNotPresent
          ports:
            - name: http
              containerPort: 8000
              protocol: TCP
          envFrom:
            - configMapRef:
                name: thesisminer-config
            - secretRef:
                name: thesisminer-secrets
          env:
            - name: POD_NAME
              valueFrom:
                fieldRef:
                  fieldPath: metadata.name
            - name: POD_NAMESPACE
              valueFrom:
                fieldRef:
                  fieldPath: metadata.namespace
            - name: POD_IP
              valueFrom:
                fieldRef:
                  fieldPath: status.podIP
          resources:
            requests:
              cpu: "500m"
              memory: "1Gi"
            limits:
              cpu: "2000m"
              memory: "4Gi"
          livenessProbe:
            httpGet:
              path: /health/live
              port: http
            initialDelaySeconds: 30
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /health/ready
              port: http
            initialDelaySeconds: 10
            periodSeconds: 5
            timeoutSeconds: 3
            failureThreshold: 3
          startupProbe:
            httpGet:
              path: /health/startup
              port: http
            failureThreshold: 30
            periodSeconds: 10
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sh", "-c", "sleep 15"]
          volumeMounts:
            - name: data
              mountPath: /app/data
            - name: config
              mountPath: /app/config
              readOnly: true
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: thesisminer-data
        - name: config
          configMap:
            name: thesisminer-config-files
        - name: tmp
          emptyDir: {}
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
```

### 7.3 SQLite StatefulSet

```yaml
# k8s/prod/sqlite-statefulset.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: thesisminer-sqlite
  namespace: production
  labels:
    app: thesisminer
    component: sqlite
spec:
  serviceName: thesisminer-sqlite
  replicas: 1
  selector:
    matchLabels:
      app: thesisminer
      component: sqlite
  template:
    metadata:
      labels:
        app: thesisminer
        component: sqlite
    spec:
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
              - matchExpressions:
                  - key: node-pool
                    operator: In
                    values: ["data"]
      tolerations:
        - key: "dedicated"
          operator: "Equal"
          value: "data"
          effect: "NoSchedule"
      containers:
        - name: sqlite
          image: ghcr.io/thesisminer/thesisminer:v8.0.0
          command: ["python", "-m", "backend.database.server"]
          ports:
            - name: sql
              containerPort: 5432
          env:
            - name: DATABASE_URL
              value: "sqlite:///./data/thesisminer.db"
            - name: DATABASE_WAL_MODE
              value: "true"
          resources:
            requests:
              cpu: "1000m"
              memory: "2Gi"
            limits:
              cpu: "4000m"
              memory: "8Gi"
          volumeMounts:
            - name: data
              mountPath: /app/data
          livenessProbe:
            exec:
              command: ["python", "-c", "import sqlite3; sqlite3.connect('/app/data/thesisminer.db').execute('SELECT 1').close()"]
            initialDelaySeconds: 30
            periodSeconds: 30
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: ssd-storage
        resources:
          requests:
            storage: 100Gi
```

### 7.4 Redis Deployment

```yaml
# k8s/prod/redis-statefulset.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: redis
  namespace: production
  labels:
    app: redis
spec:
  serviceName: redis
  replicas: 3
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      affinity:
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            - labelSelector:
                matchLabels:
                  app: redis
              topologyKey: kubernetes.io/hostname
      containers:
        - name: redis
          image: redis:7.2-alpine
          command: ["redis-server"]
          args:
            - "/etc/redis/redis.conf"
            - "--replicaof"
            - "$(REDIS_MASTER)"
            - "--replica-announce-ip"
            - "$(POD_IP)"
            - "--replica-announce-port"
            - "6379"
          env:
            - name: POD_IP
              valueFrom:
                fieldRef:
                  fieldPath: status.podIP
            - name: REDIS_MASTER
              value: "redis-0.redis.production.svc.cluster.local 6379"
          ports:
            - name: redis
              containerPort: 6379
          resources:
            requests:
              cpu: "500m"
              memory: "1Gi"
            limits:
              cpu: "1000m"
              memory: "2Gi"
          volumeMounts:
            - name: data
              mountPath: /data
            - name: config
              mountPath: /etc/redis
          livenessProbe:
            exec:
              command: ["redis-cli", "ping"]
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            exec:
              command: ["redis-cli", "ping"]
            initialDelaySeconds: 5
            periodSeconds: 5
      volumes:
        - name: config
          configMap:
            name: redis-config
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: ssd-storage
        resources:
          requests:
            storage: 20Gi
```

### 7.5 ConfigMap 文件挂载

```yaml
# k8s/prod/config-files.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: thesisminer-config-files
  namespace: production
data:
  logging.yaml: |
    version: 1
    disable_existing_loggers: false
    formatters:
      json:
        class: pythonjsonlogger.jsonlogger.JsonFormatter
        format: "%(asctime)s %(name)s %(levelname)s %(message)s"
    handlers:
      console:
        class: logging.StreamHandler
        formatter: json
        stream: ext://sys.stdout
    root:
      level: INFO
      handlers: [console]
    loggers:
      backend:
        level: INFO
        handlers: [console]
        propagate: false
      uvicorn:
        level: INFO
        handlers: [console]
        propagate: false

  prometheus.yml: |
    global:
      scrape_interval: 15s
      evaluation_interval: 15s
    scrape_configs:
      - job_name: thesisminer
        kubernetes_sd_configs:
          - role: pod
        relabel_configs:
          - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
            action: keep
            regex: true
          - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
            action: replace
            target_label: __metrics_path__
```

### 7.6 优雅停机

```python
# backend/main.py
"""FastAPI 应用入口，包含优雅停机逻辑"""
import asyncio
import signal
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from backend.database import close_db, init_db
from backend.sessions.session_manager import SessionManager
from backend.monitoring.health_checker import HealthChecker
from backend.ai.prompt_cache import PromptCache


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动与优雅停机"""
    # ===== 启动阶段 =====
    print("[启动] 初始化数据库连接...")
    await init_db()

    print("[启动] 预热 Prompt 缓存...")
    cache = PromptCache()
    await cache.warmup()

    print("[启动] 启动健康监控...")
    health_checker = HealthChecker()
    await health_checker.start_monitoring()

    # 注册信号处理
    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    def _signal_handler():
        print("[停机] 收到终止信号，开始优雅停机...")
        shutdown_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            # Windows 不支持 add_signal_handler
            pass

    # 启动后台任务
    background_task = asyncio.create_task(_background_worker(app))

    yield

    # ===== 停机阶段 =====
    print("[停机] 等待进行中的请求完成...")
    shutdown_event.set()
    background_task.cancel()
    try:
        await asyncio.wait_for(background_task, timeout=30)
    except asyncio.TimeoutError:
        print("[停机] 后台任务超时，强制终止")

    print("[停机] 关闭健康监控...")
    await health_checker.stop_monitoring()

    print("[停机] 关闭数据库连接...")
    await close_db()

    print("[停机] 清理 Prompt 缓存...")
    await cache.cleanup()

    print("[停机] 优雅停机完成")


async def _background_worker(app: FastAPI):
    """后台任务：定期清理过期会话"""
    while True:
        try:
            await asyncio.sleep(3600)
            manager = SessionManager()
            cleaned = await manager.cleanup_expired()
            print(f"[后台] 清理 {cleaned} 个过期会话")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[后台] 清理任务异常: {e}")


app = FastAPI(
    title="ThesisMiner",
    version="8.0.0",
    lifespan=lifespan,
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")
```

### 7.7 ResourceQuota 与 LimitRange

```yaml
# k8s/prod/resourcequota.yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: production-quota
  namespace: production
spec:
  hard:
    requests.cpu: "32"
    requests.memory: 64Gi
    limits.cpu: "64"
    limits.memory: 128Gi
    persistentvolumeclaims: "20"
    services.loadbalancers: "2"
    configmaps: "50"
    secrets: "50"
---
apiVersion: v1
kind: LimitRange
metadata:
  name: production-limits
  namespace: production
spec:
  limits:
    - type: Container
      default:
        cpu: 1000m
        memory: 2Gi
      defaultRequest:
        cpu: 250m
        memory: 512Mi
      max:
        cpu: 4
        memory: 8Gi
      min:
        cpu: 100m
        memory: 128Mi
    - type: PersistentVolumeClaim
      max:
        storage: 500Gi
      min:
        storage: 1Gi
```

### 7.8 RBAC 配置

```yaml
# k8s/prod/rbac.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: thesisminer-backend
  namespace: production
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: thesisminer-backend-role
  namespace: production
rules:
  - apiGroups: [""]
    resources: ["pods", "pods/log"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["configmaps", "secrets"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["metrics.k8s.io"]
    resources: ["pods"]
    verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: thesisminer-backend-binding
  namespace: production
subjects:
  - kind: ServiceAccount
    name: thesisminer-backend
    namespace: production
roleRef:
  kind: Role
  name: thesisminer-backend-role
  apiGroup: rbac.authorization.k8s.io
```

---

## 8. 服务网格 (Service Mesh)

### 8.1 Istio 架构

```
┌─────────────────────────────────────────────────────────────────┐
│  Istio 服务网格架构                                              │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Control Plane (istiod)                                  │   │
│  │  - Pilot: 服务发现 / 路由规则下发                          │   │
│  │  - Citadel: 证书签发 / mTLS                                │   │
│  │  - Galley: 配置验证                                        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌───────────────────────────┼──────────────────────────────┐   │
│  │  Data Plane (Envoy Sidecar) ▼                             │   │
│  │  ┌──────────┐    ┌──────────┐    ┌──────────┐            │   │
│  │  │ Pod A    │    │ Pod B    │    │ Pod C    │            │   │
│  │  │ ┌──────┐ │    │ ┌──────┐ │    │ ┌──────┐ │            │   │
│  │  │ │App   │ │    │ │App   │ │    │ │App   │ │            │   │
│  │  │ ├──────┤ │    │ ├──────┤ │    │ ├──────┤ │            │   │
│  │  │ │Envoy │◄├────┤►│Envoy │◄├────┤►│Envoy │ │            │   │
│  │  │ └──────┘ │    │ └──────┘ │    │ └──────┘ │            │   │
│  │  └──────────┘    └──────────┘    └──────────┘            │   │
│  │       │ mTLS         │ mTLS         │ mTLS                │   │
│  │       └──────────────┴──────────────┘                    │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 Sidecar 注入

```yaml
# k8s/prod/istio-injection.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    istio-injection: enabled
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: thesisminer-backend
  namespace: production
spec:
  template:
    metadata:
      annotations:
        sidecar.istio.io/inject: "true"
        sidecar.istio.io/proxyCPU: "250m"
        sidecar.istio.io/proxyMemory: "256Mi"
        sidecar.istio.io/proxyCPULimit: "500m"
        sidecar.istio.io/proxyMemoryLimit: "512Mi"
        sidecar.istio.io/interceptionMode: REDIRECT
        traffic.sidecar.istio.io/includeInboundPorts: "8000"
        traffic.sidecar.istio.io/excludeOutboundPorts: "443"
```

### 8.3 DestinationRule（熔断 / 负载均衡）

```yaml
# k8s/prod/destination-rule.yaml
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: thesisminer-backend-dr
  namespace: production
spec:
  host: thesisminer-backend
  trafficPolicy:
    loadBalancer:
      simple: LEAST_REQUEST
    connectionPool:
      tcp:
        maxConnections: 100
        connectTimeout: 5s
        tcpKeepalive:
          time: 60s
          interval: 15s
          probes: 3
      http:
        http1MaxPendingRequests: 50
        http2MaxRequests: 100
        maxRequestsPerConnection: 10
        maxRetries: 3
        idleTimeout: 60s
    outlierDetection:
      consecutive5xxErrors: 5
      interval: 30s
      baseEjectionTime: 60s
      maxEjectionPercent: 50
      minHealthPercent: 50
    tls:
      mode: ISTIO_MUTUAL
  subsets:
    - name: v8
      labels:
        version: v8.0.0
    - name: v7
      labels:
        version: v7.0.0
```

### 8.4 VirtualService（流量路由 / 重试 / 超时）

```yaml
# k8s/prod/virtual-service.yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: thesisminer-backend-vs
  namespace: production
spec:
  hosts:
    - thesisminer-backend
  http:
    - name: v8-canary
      match:
        - headers:
            x-canary:
              exact: "true"
      route:
        - destination:
            host: thesisminer-backend
            subset: v8
            port:
              number: 8000
      retries:
        attempts: 3
        perTryTimeout: 10s
        retryOn: "5xx,reset,connect-failure,refused-stream"
      timeout: 30s
    - name: default
      route:
        - destination:
            host: thesisminer-backend
            subset: v7
            port:
              number: 8000
          weight: 90
        - destination:
            host: thesisminer-backend
            subset: v8
            port:
              number: 8000
          weight: 10
      retries:
        attempts: 3
        perTryTimeout: 10s
        retryOn: "5xx,reset,connect-failure"
      timeout: 30s
```

### 8.5 PeerAuthentication（mTLS 策略）

```yaml
# k8s/prod/peer-authentication.yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: production
spec:
  mtls:
    mode: STRICT
---
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: thesisminer-backend-policy
  namespace: production
spec:
  selector:
    matchLabels:
      app: thesisminer
      component: backend
  action: ALLOW
  rules:
    - from:
        - source:
            principals: ["cluster.local/ns/production/sa/thesisminer-frontend"]
        - source:
            principals: ["cluster.local/ns/production/sa/thesisminer-ingress"]
      to:
        - operation:
            methods: ["GET", "POST", "PUT", "DELETE"]
            paths: ["/api/*"]
```

---

## 9. 负载均衡

### 9.1 四层负载均衡架构

```
┌─────────────────────────────────────────────────────────────────┐
│  四层负载均衡架构                                                │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  L4 LB (Cloud LB) - TCP 负载均衡                          │   │
│  │  - 算法: 最小连接数 (Least Connections)                   │   │
│  │  - 健康检查: TCP 80/443                                    │   │
│  │  - 会话保持: 基于 Client IP                                │   │
│  └──────────────────────────┬──────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────▼──────────────────────────────┐   │
│  │  L7 LB (Nginx Ingress) - HTTP/HTTPS 负载均衡              │   │
│  │  - 算法: 加权轮询 (Weighted Round Robin)                  │   │
│  │  - TLS 终止                                                │   │
│  │  - 路径路由: /api → backend, / → frontend                 │   │
│  │  - 限流: 100 req/s per IP                                 │   │
│  └──────────────────────────┬──────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────▼──────────────────────────────┐   │
│  │  Service Mesh (Istio) - 服务间负载均衡                    │   │
│  │  - 算法: LEAST_REQUEST                                    │   │
│  │  - 熔断: 5xx 连续 5 次剔除 60s                            │   │
│  │  - 重试: 3 次, 超时 10s                                    │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 9.2 负载均衡算法对比

| 算法 | 英文 | 适用场景 | 优点 | 缺点 |
|------|------|----------|------|------|
| 轮询 | Round Robin | 服务器性能相近 | 简单、公平 | 不考虑负载 |
| 加权轮询 | Weighted RR | 服务器性能差异 | 考虑性能差异 | 静态权重 |
| 最小连接 | Least Conn | 长连接场景 | 动态均衡 | 计算开销 |
| IP Hash | IP Hash | 会话保持 | 简单粘性 | 节点变化影响大 |
| 一致性 Hash | Consistent Hash | 缓存场景 | 节点变化影响小 | 实现复杂 |
| 最少响应时间 | Least Time | 对延迟敏感 | 性能最优 | 需要监控 |

### 9.3 Nginx Ingress 配置

```yaml
# k8s/prod/nginx-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: nginx-configuration
  namespace: ingress-nginx
data:
  worker-processes: "auto"
  worker-connections: "65535"
  worker-shutdown-timeout: "240s"
  keep-alive: "75"
  keep-alive-requests: "100"
  upstream-keepalive-connections: "100"
  upstream-keepalive-timeout: "60"
  upstream-keepalive-requests: "100"
  proxy-connect-timeout: "10"
  proxy-send-timeout: "120"
  proxy-read-timeout: "120"
  proxy-next-upstream-timeout: "60"
  proxy-buffer-size: "16k"
  proxy-buffers: "4 16k"
  proxy-busy-buffers-size: "32k"
  proxy-request-buffering: "on"
  proxy-body-size: "50m"
  gzip: "on"
  gzip-level: "6"
  gzip-min-length: "1024"
  gzip-types: "text/plain text/css application/json application/javascript text/xml application/xml"
  limit-conn-zone-variable: "$binary_remote_addr"
  limit-conn-status: 429
  ssl-protocols: "TLSv1.2 TLSv1.3"
  ssl-ciphers: "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384"
  ssl-prefer-server-ciphers: "on"
  ssl-session-cache: "shared:SSL:10m"
  ssl-session-timeout: "10m"
```

### 9.4 会话保持配置

```yaml
# k8s/prod/session-affinity.yaml
apiVersion: v1
kind: Service
metadata:
  name: thesisminer-backend-sticky
  namespace: production
  annotations:
    nginx.ingress.kubernetes.io/affinity: "cookie"
    nginx.ingress.kubernetes.io/affinity-mode: "persistent"
    nginx.ingress.kubernetes.io/session-cookie-name: "thesisminer-route"
    nginx.ingress.kubernetes.io/session-cookie-hash: "sha1"
    nginx.ingress.kubernetes.io/session-cookie-expires: "3600"
    nginx.ingress.kubernetes.io/session-cookie-max-age: "3600"
    nginx.ingress.kubernetes.io/session-cookie-change-on-failure: "true"
spec:
  type: ClusterIP
  selector:
    app: thesisminer
    component: backend
  ports:
    - port: 8000
      targetPort: 8000
```

### 9.5 健康检查配置

```yaml
# k8s/prod/health-checks.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: thesisminer-health-check
  namespace: production
  annotations:
    nginx.ingress.kubernetes.io/backend-protocol: "HTTP"
    nginx.ingress.kubernetes.io/healthcheck-path: "/health/live"
    nginx.ingress.kubernetes.io/healthcheck-interval: "10s"
    nginx.ingress.kubernetes.io/healthcheck-timeout: "5s"
    nginx.ingress.kubernetes.io/healthcheck-fails: "3"
    nginx.ingress.kubernetes.io/healthcheck-passes: "2"
    nginx.ingress.kubernetes.io/healthcheck-port: "8000"
spec:
  ingressClassName: nginx
  rules:
    - host: thesisminer.example.com
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: thesisminer-backend
                port:
                  number: 8000
```

### 9.6 限流配置

```python
# backend/middleware/rate_limiter.py
"""基于 Redis 的分布式限流器"""
import time
from typing import Optional

import redis.asyncio as aioredis
from fastapi import Request, HTTPException


class RateLimiter:
    """滑动窗口限流器"""

    def __init__(self, redis: aioredis.Redis, key_prefix: str = "rl"):
        self.redis = redis
        self.key_prefix = key_prefix

    async def check(
        self,
        identifier: str,
        limit: int,
        window: int = 60,
    ) -> bool:
        """检查是否超过限流

        Args:
            identifier: 限流标识（如 IP / user_id）
            limit: 窗口内最大请求数
            window: 窗口大小（秒）

        Returns:
            True 表示允许，False 表示拒绝
        """
        key = f"{self.key_prefix}:{identifier}:{int(time.time() // window)}"
        try:
            current = await self.redis.incr(key)
            if current == 1:
                await self.redis.expire(key, window)
            return current <= limit
        except Exception:
            # Redis 故障时放行，避免影响业务
            return True


async def rate_limit_middleware(
    request: Request,
    call_next,
    limiter: RateLimiter,
    limit: int = 100,
    window: int = 60,
):
    """限流中间件"""
    client_ip = request.client.host if request.client else "unknown"
    user_id = request.headers.get("X-User-ID", client_ip)

    allowed = await limiter.check(user_id, limit, window)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="请求过于频繁，请稍后再试",
            headers={"Retry-After": str(window)},
        )

    response = await call_next(request)
    remaining = limit - int(
        await limiter.redis.get(f"rl:{user_id}:{int(time.time() // window)}") or 0
    )
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
    return response
```

---

## 10. 自动扩缩容

### 10.1 扩缩容策略对比

| 策略 | 触发条件 | 优点 | 缺点 | 适用场景 |
|------|----------|------|------|----------|
| HPA (CPU) | CPU > 70% | 简单 | 不反映真实负载 | CPU 密集型 |
| HPA (Memory) | Mem > 80% | 反映内存压力 | 内存泄漏误判 | 内存敏感型 |
| HPA (自定义) | QPS / 队列长度 | 精准 | 需自定义指标 | 业务驱动型 |
| VPA | 资源使用率 | 自动调整配额 | 重启 Pod | 资源优化 |
| Cluster Autoscaler | 节点不足 | 自动加节点 | 启动慢 (1-3min) | 节点扩容 |
| CronHPA | 定时 | 可预测 | 不灵活 | 定时任务 |
| KEDA | 事件驱动 | 灵活 | 复杂 | 消息队列消费 |

### 10.2 HPA 配置（CPU + Memory）

```yaml
# k8s/prod/hpa-cpu-memory.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: thesisminer-backend-hpa
  namespace: production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: thesisminer-backend
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
        - type: Percent
          value: 100
          periodSeconds: 60
        - type: Pods
          value: 4
          periodSeconds: 60
      selectPolicy: Max
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 25
          periodSeconds: 60
      selectPolicy: Min
```

### 10.3 HPA 配置（自定义指标）

```yaml
# k8s/prod/hpa-custom.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: thesisminer-backend-custom-hpa
  namespace: production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: thesisminer-backend
  minReplicas: 3
  maxReplicas: 30
  metrics:
    - type: Pods
      pods:
        metric:
          name: http_requests_per_second
        target:
          type: AverageValue
          averageValue: "100"
    - type: Pods
      pods:
        metric:
          name: llm_queue_length
        target:
          type: AverageValue
          averageValue: "10"
    - type: External
      external:
        metric:
          name: redis_queue_length
          selector:
            matchLabels:
              queue: thesisminer-tasks
        target:
          type: AverageValue
          averageValue: "50"
```

### 10.4 自定义指标暴露

```python
# backend/monitoring/metrics.py
"""Prometheus 自定义指标暴露"""
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from fastapi import APIRouter, Response

router = APIRouter()

# HTTP 请求指标
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

# 业务指标
llm_calls_total = Counter(
    "llm_calls_total",
    "Total LLM API calls",
    ["model", "status", "cache_hit"],
)

llm_call_duration_seconds = Histogram(
    "llm_call_duration_seconds",
    "LLM API call duration in seconds",
    ["model"],
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60, 120),
)

llm_tokens_total = Counter(
    "llm_tokens_total",
    "Total LLM tokens consumed",
    ["model", "type"],
)

# 队列指标
llm_queue_length = Gauge(
    "llm_queue_length",
    "Current LLM task queue length",
)

# 会话指标
active_sessions = Gauge(
    "active_sessions_total",
    "Number of active sessions",
)

# 缓存指标
cache_hits_total = Counter(
    "cache_hits_total",
    "Total cache hits",
    ["layer"],
)

cache_misses_total = Counter(
    "cache_misses_total",
    "Total cache misses",
    ["layer"],
)


@router.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")
```

### 10.5 Cluster Autoscaler

```yaml
# k8s/prod/cluster-autoscaler.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cluster-autoscaler
  namespace: kube-system
  labels:
    app: cluster-autoscaler
spec:
  replicas: 1
  selector:
    matchLabels:
      app: cluster-autoscaler
  template:
    metadata:
      labels:
        app: cluster-autoscaler
    spec:
      priorityClassName: system-cluster-critical
      securityContext:
        runAsNonRoot: true
        runAsUser: 65534
      containers:
        - image: registry.k8s.io/autoscaling/cluster-autoscaler:v1.28.0
          name: cluster-autoscaler
          resources:
            limits:
              cpu: 100m
              memory: 300Mi
            requests:
              cpu: 100m
              memory: 300Mi
          command:
            - ./cluster-autoscaler
            - --v=4
            - --stderrthreshold=info
            - --cloud-provider=aws
            - --skip-nodes-with-local-storage=false
            - --expander=least-waste
            - --balance-similar-node-groups
            - --max-graceful-termination-sec=600
            - --max-node-provision-time=15m
          env:
            - name: AWS_REGION
              value: cn-north-1
          imagePullPolicy: Always
```

### 10.6 CronHPA 定时扩缩容

```yaml
# k8s/prod/cron-hpa.yaml
apiVersion: autoscaling.alibaba.com/v1beta1
kind: CronHorizontalPodAutoscaler
metadata:
  name: thesisminer-backend-cronhpa
  namespace: production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: thesisminer-backend
  jobs:
    - name: workday-morning-scale-up
      schedule: "0 8 * * 1-5"
      targetReplicas: 10
    - name: workday-evening-scale-down
      schedule: "0 22 * * 1-5"
      targetReplicas: 3
    - name: weekend-scale-down
      schedule: "0 0 * * 6,0"
      targetReplicas: 2
```

### 10.7 扩缩容决策流程

```
                ┌─────────────────────────┐
                │  Prometheus 采集指标     │
                │  (15s 间隔)              │
                └────────────┬─────────────┘
                             │
                             ▼
                ┌─────────────────────────┐
                │  HPA Controller 评估     │
                │  - 当前副本数             │
                │  - 当前指标值             │
                │  - 期望指标值             │
                └────────────┬─────────────┘
                             │
                ┌────────────▼─────────────┐
                │  期望副本数 = max(        │
                │    ceil(当前 * 当前指标/期望),│
                │    minReplicas)          │
                └────────────┬─────────────┘
                             │
              ┌──────────────┴──────────────┐
              │                              │
              ▼                              ▼
    ┌──────────────────┐          ┌──────────────────┐
    │  期望 > 当前?     │          │  期望 < 当前?     │
    │  扩容             │          │  缩容             │
    └────────┬─────────┘          └────────┬─────────┘
             │                              │
             ▼                              ▼
    ┌──────────────────┐          ┌──────────────────┐
    │  scaleUp 策略     │          │  scaleDown 策略   │
    │  - 稳定窗口 60s   │          │  - 稳定窗口 300s  │
    │  - 最大 100%/min │          │  - 最大 25%/min  │
    └────────┬─────────┘          └────────┬─────────┘
             │                              │
             ▼                              ▼
    ┌──────────────────┐          ┌──────────────────┐
    │  Deployment      │          │  Deployment      │
    │  增加 replicas   │          │  减少 replicas   │
    └────────┬─────────┘          └────────┬─────────┘
             │                              │
             ▼                              ▼
    ┌──────────────────┐          ┌──────────────────┐
    │  Pod 调度         │          │  Pod 优雅终止    │
    │  - 节点资源足够?  │          │  - preStop hook  │
    │  - 是: 创建 Pod   │          │  - terminationGrace│
    │  - 否: 触发 CA    │          │  - 等待连接排空   │
    └──────────────────┘          └──────────────────┘
             │
             ▼
    ┌──────────────────────────────┐
    │  Cluster Autoscaler          │
    │  - 检测 Pending Pod          │
    │  - 扩容节点池                 │
    │  - 等待节点 Ready (1-3min)   │
    └──────────────────────────────┘
```

---

## 11. 滚动更新与发布策略

### 11.1 发布策略对比

| 策略 | 停机时间 | 回滚速度 | 资源开销 | 复杂度 | 适用场景 |
|------|----------|----------|----------|--------|----------|
| 滚动更新 | 0 | 中 (1-5min) | 1.x | 低 | 常规发布 |
| 蓝绿部署 | 0 | 快 (<1min) | 2x | 中 | 关键发布 |
| 金丝雀 | 0 | 快 (<1min) | 1.x | 高 | 风险发布 |
| A/B 测试 | 0 | 快 | 1.x | 高 | 灰度验证 |
| 影子部署 | 0 | N/A | 2x | 高 | 性能验证 |

### 11.2 滚动更新配置

```yaml
# k8s/prod/rolling-update.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: thesisminer-backend
  namespace: production
spec:
  replicas: 6
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 2
      maxUnavailable: 0
  minReadySeconds: 30
  progressDeadlineSeconds: 600
```

### 11.3 滚动更新流程

```
时间轴 ─────────────────────────────────────────────────────────►

初始状态:
  v7: [Pod1] [Pod2] [Pod3] [Pod4] [Pod5] [Pod6]

T0: 触发更新 (镜像 v7 → v8)
  v7: [Pod1] [Pod2] [Pod3] [Pod4] [Pod5] [Pod6]
  v8: [Pod7(创建中)] [Pod8(创建中)]           ← maxSurge=2

T1: Pod7/Pod8 就绪 (readiness 通过)
  v7: [Pod1] [Pod2] [Pod3] [Pod4] [Pod5] [Pod6]
  v8: [Pod7 OK] [Pod8 OK]

T2: 终止 Pod1/Pod2 (preStop + grace period)
  v7: [Pod3] [Pod4] [Pod5] [Pod6]              ← maxUnavailable=0
  v8: [Pod7 OK] [Pod8 OK] [Pod9(创建中)] [Pod10(创建中)]

T3: Pod1/Pod2 终止完成, Pod9/Pod10 就绪
  v7: [Pod3] [Pod4] [Pod5] [Pod6]
  v8: [Pod7 OK] [Pod8 OK] [Pod9 OK] [Pod10 OK]

T4: 终止 Pod3/Pod4
  v7: [Pod5] [Pod6]
  v8: [Pod7 OK] [Pod8 OK] [Pod9 OK] [Pod10 OK] [Pod11(创建中)] [Pod12(创建中)]

... 重复直至全部更新 ...

T_final:
  v8: [Pod7 OK] [Pod8 OK] [Pod9 OK] [Pod10 OK] [Pod11 OK] [Pod12 OK]

回滚条件:
  - progressDeadlineSeconds 超时
  - readinessProbe 失败率 > 阈值
  - 手动 kubectl rollout undo
```

### 11.4 蓝绿部署

```yaml
# k8s/prod/blue-green.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: thesisminer-backend-blue
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: thesisminer
      component: backend
      slot: blue
  template:
    metadata:
      labels:
        app: thesisminer
        component: backend
        slot: blue
        version: v7.0.0
    spec:
      containers:
        - name: backend
          image: ghcr.io/thesisminer/thesisminer:v7.0.0
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: thesisminer-backend-green
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: thesisminer
      component: backend
      slot: green
  template:
    metadata:
      labels:
        app: thesisminer
        component: backend
        slot: green
        version: v8.0.0
    spec:
      containers:
        - name: backend
          image: ghcr.io/thesisminer/thesisminer:v8.0.0
---
apiVersion: v1
kind: Service
metadata:
  name: thesisminer-backend
  namespace: production
spec:
  selector:
    app: thesisminer
    component: backend
    slot: blue   # 切换时改为 green
  ports:
    - port: 8000
      targetPort: 8000
```

切换脚本：

```bash
#!/bin/bash
# scripts/blue_green_switch.sh
set -euo pipefail

NAMESPACE="production"
SERVICE="thesisminer-backend"
NEW_SLOT="${1:-green}"

echo "[1/4] 验证新环境健康..."
kubectl -n "$NAMESPACE" exec deployment/thesisminer-backend-$NEW_SLOT -- \
    curl -f http://localhost:8000/health/ready

echo "[2/4] 切换 Service 到 $NEW_SLOT..."
kubectl -n "$NAMESPACE" patch svc "$SERVICE" -p \
    "{\"spec\":{\"selector\":{\"slot\":\"$NEW_SLOT\"}}}"

echo "[3/4] 等待流量切换完成..."
sleep 30

echo "[4/4] 验证生产流量正常..."
curl -f https://thesisminer.example.com/health

echo "[OK] 蓝绿切换完成: $NEW_SLOT"
```

### 11.5 金丝雀发布

```yaml
# k8s/prod/canary.yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: thesisminer-canary
  namespace: production
spec:
  hosts:
    - thesisminer-backend
  http:
    - route:
        - destination:
            host: thesisminer-backend
            subset: v7
            port:
              number: 8000
          weight: 95
        - destination:
            host: thesisminer-backend
            subset: v8
            port:
              number: 8000
          weight: 5
      retries:
        attempts: 3
        perTryTimeout: 10s
---
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: thesisminer-canary-dr
  namespace: production
spec:
  host: thesisminer-backend
  subsets:
    - name: v7
      labels:
        version: v7.0.0
    - name: v8
      labels:
        version: v8.0.0
```

### 11.6 金丝雀发布流程

```
┌─────────────────────────────────────────────────────────────────┐
│  金丝雀发布流程                                                  │
│                                                                  │
│  Step 1: 部署 v8 (1 副本)                                        │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  v7: 95% 流量 (6 副本)                                  │     │
│  │  v8: 5% 流量  (1 副本) ← 金丝雀                         │     │
│  └────────────────────────────────────────────────────────┘     │
│  观察 30 分钟: 错误率 / 延迟 / 业务指标                          │
│                                                                  │
│  Step 2: 扩大金丝雀 (10% 流量)                                   │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  v7: 90% 流量 (6 副本)                                  │     │
│  │  v8: 10% 流量 (2 副本)                                  │     │
│  └────────────────────────────────────────────────────────┘     │
│  观察 1 小时                                                     │
│                                                                  │
│  Step 3: 继续扩大 (50% 流量)                                     │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  v7: 50% 流量 (3 副本)                                  │     │
│  │  v8: 50% 流量 (4 副本)                                  │     │
│  └────────────────────────────────────────────────────────┘     │
│  观察 2 小时                                                     │
│                                                                  │
│  Step 4: 全量切换 (100% 流量)                                    │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  v8: 100% 流量 (6 副本)                                 │     │
│  │  v7: 0% 流量 (保留 1 副本用于回滚)                      │     │
│  └────────────────────────────────────────────────────────┘     │
│  观察 24 小时, 无异常则下线 v7                                    │
│                                                                  │
│  自动回滚触发条件:                                                │
│  - v8 错误率 > 1%                                                │
│  - v8 P99 延迟 > v7 × 1.5                                        │
│  - v8 业务指标下降 > 5%                                          │
└─────────────────────────────────────────────────────────────────┘
```

### 11.7 自动回滚

```yaml
# k8s/prod/auto-rollback.yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: thesisminer-backend
  namespace: production
spec:
  replicas: 6
  strategy:
    canary:
      canaryService: thesisminer-canary
      stableService: thesisminer-stable
      trafficRouting:
        istio:
          virtualService:
            name: thesisminer-vsvc
            routes:
              - primary
      steps:
        - setWeight: 5
        - pause: { duration: 30m }
        - setWeight: 10
        - pause: { duration: 1h }
        - setWeight: 50
        - pause: { duration: 2h }
        - setWeight: 100
      analysis:
        templates:
          - templateName: success-rate
        startingStep: 1
  selector:
    matchLabels:
      app: thesisminer
      component: backend
  template:
    metadata:
      labels:
        app: thesisminer
        component: backend
    spec:
      containers:
        - name: backend
          image: ghcr.io/thesisminer/thesisminer:v8.0.0
---
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: success-rate
  namespace: production
spec:
  args:
    - name: service-name
  metrics:
    - name: success-rate
      interval: 1m
      successCondition: result[0] >= 0.99
      failureLimit: 3
      provider:
        prometheus:
          address: http://prometheus.observability:9090
          query: |
            sum(rate(http_requests_total{service="{{args.service-name}}",status!~"5.."}[2m]))
            /
            sum(rate(http_requests_total{service="{{args.service-name}}"}[2m]))
```

---

## 12. 监控告警体系

### 12.1 监控架构

```
┌─────────────────────────────────────────────────────────────────┐
│  监控告警架构                                                    │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  数据采集层                                               │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐          │   │
│  │  │ Prometheus │  │  Node      │  │  App       │          │   │
│  │  │  Exporter  │  │  Exporter  │  │  /metrics  │          │   │
│  │  └────────────┘  └────────────┘  └────────────┘          │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐          │   │
│  │  │  Blackbox  │  │  Redis     │  │  SQLite    │          │   │
│  │  │  Exporter  │  │  Exporter  │  │  Exporter  │          │   │
│  │  └────────────┘  └────────────┘  └────────────┘          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────▼──────────────────────────────┐   │
│  │  数据存储层                                               │   │
│  │  ┌────────────────────────────────────────────────┐      │   │
│  │  │  Prometheus TSDB (15 天保留)                    │      │   │
│  │  └────────────────────────────────────────────────┘      │   │
│  │  ┌────────────────────────────────────────────────┐      │   │
│  │  │  Thanos / VictoriaMetrics (1 年长期存储)        │      │   │
│  │  └────────────────────────────────────────────────┘      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────▼──────────────────────────────┐   │
│  │  可视化与告警层                                            │   │
│  │  ┌────────────────┐  ┌────────────────┐                  │   │
│  │  │  Grafana       │  │  Alertmanager  │                  │   │
│  │  │  - 实时仪表盘   │  │  - 告警路由     │                  │   │
│  │  │  - 历史趋势     │  │  - 告警抑制     │                  │   │
│  │  └────────────────┘  └────────────────┘                  │   │
│  │                              │                            │   │
│  │  ┌───────────────────────────▼──────────────────────┐    │   │
│  │  │  通知渠道                                           │    │   │
│  │  │  - 钉钉 / 企业微信 / 飞书                            │    │   │
│  │  │  - 邮件 / 短信                                      │    │   │
│  │  │  - PagerDuty / 值班电话                             │    │   │
│  │  └────────────────────────────────────────────────────┘    │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 12.2 Prometheus 配置

```yaml
# config/prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  scrape_timeout: 10s
  external_labels:
    cluster: prod-cluster
    environment: production

rule_files:
  - /etc/prometheus/rules/*.yml

alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager.observability:9093

scrape_configs:
  - job_name: thesisminer
    kubernetes_sd_configs:
      - role: pod
        namespaces:
          names: [production]
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
        action: replace
        target_label: __metrics_path__
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_port, __meta_kubernetes_pod_ip]
        action: replace
        regex: (.+);(.+)
        replacement: $2:$1
        target_label: __address__
      - source_labels: [__meta_kubernetes_namespace]
        action: replace
        target_label: namespace
      - source_labels: [__meta_kubernetes_pod_name]
        action: replace
        target_label: pod
      - source_labels: [__meta_kubernetes_pod_label_app]
        action: replace
        target_label: app

  - job_name: kubernetes-nodes
    kubernetes_sd_configs:
      - role: node
    relabel_configs:
      - source_labels: [__address__]
        regex: '(.*):.*'
        replacement: '${1}:9100'
        target_label: __address__

  - job_name: blackbox
    metrics_path: /probe
    params:
      module: [http_2xx]
    static_configs:
      - targets:
          - https://thesisminer.example.com/health
          - https://thesisminer.example.com/api/v1/sessions
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: blackbox-exporter.observability:9115
```

### 12.3 告警规则

```yaml
# config/prometheus/rules/thesisminer-alerts.yml
groups:
  - name: thesisminer-app
    rules:
      - alert: ThesisMinerDown
        expr: up{job="thesisminer"} == 0
        for: 1m
        labels:
          severity: critical
          team: thesisminer
        annotations:
          summary: "ThesisMiner 服务不可用"
          description: "{{ $labels.pod }} 已离线超过 1 分钟"

      - alert: ThesisMinerHighErrorRate
        expr: |
          sum(rate(http_requests_total{job="thesisminer",status=~"5.."}[5m]))
          /
          sum(rate(http_requests_total{job="thesisminer"}[5m]))
          > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "ThesisMiner 5xx 错误率过高"
          description: "5xx 错误率 {{ $value | humanizePercentage }} 超过 5%"

      - alert: ThesisMinerHighLatency
        expr: |
          histogram_quantile(0.99,
            sum(rate(http_request_duration_seconds_bucket{job="thesisminer"}[5m])) by (le)
          ) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "ThesisMiner P99 延迟过高"
          description: "P99 延迟 {{ $value }}s 超过 2s"

      - alert: LLMApiFailures
        expr: |
          sum(rate(llm_calls_total{status="error"}[5m]))
          /
          sum(rate(llm_calls_total[5m]))
          > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "LLM API 调用失败率过高"
          description: "DeepSeek API 失败率 {{ $value | humanizePercentage }} 超过 10%"

      - alert: DatabaseConnectionFailed
        expr: thesisminer_db_connections_active == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "数据库连接异常"
          description: "无活跃数据库连接"

      - alert: LowCacheHitRate
        expr: |
          sum(rate(cache_hits_total[10m]))
          /
          (sum(rate(cache_hits_total[10m])) + sum(rate(cache_misses_total[10m])))
          < 0.5
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "缓存命中率过低"
          description: "缓存命中率 {{ $value | humanizePercentage }} 低于 50%"

  - name: kubernetes
    rules:
      - alert: NodeHighCPU
        expr: |
          100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "节点 CPU 使用率过高"
          description: "{{ $labels.instance }} CPU 使用率 {{ $value }}%"

      - alert: NodeHighMemory
        expr: |
          (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 85
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "节点内存使用率过高"

      - alert: NodeHighDisk
        expr: |
          (1 - (node_filesystem_avail_bytes{fstype!~"tmpfs|overlay"} / node_filesystem_size_bytes{fstype!~"tmpfs|overlay"})) * 100 > 85
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "节点磁盘使用率过高"

      - alert: PodRestart
        expr: increase(kube_pod_container_status_restarts_total[1h]) > 3
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Pod 频繁重启"
          description: "{{ $labels.pod }} 1 小时内重启 {{ $value }} 次"

      - alert: PodPending
        expr: kube_pod_status_phase{phase="Pending"} == 1
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Pod 长时间 Pending"
```

### 12.4 Alertmanager 配置

```yaml
# config/alertmanager/alertmanager.yml
global:
  resolve_timeout: 5m
  smtp_smarthost: "smtp.example.com:587"
  smtp_from: "alert@thesisminer.example.com"
  smtp_auth_username: "alert@thesisminer.example.com"
  smtp_auth_password: "${SMTP_PASSWORD}"

templates:
  - /etc/alertmanager/templates/*.tmpl

route:
  group_by: ["alertname", "cluster", "namespace"]
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: default
  routes:
    - match:
        severity: critical
      receiver: critical
      group_wait: 10s
      repeat_interval: 1h
    - match:
        severity: warning
      receiver: warning
      group_wait: 1m
      repeat_interval: 4h

receivers:
  - name: default
    webhook_configs:
      - url: "https://oapi.dingtalk.com/robot/send?access_token=${DINGTALK_TOKEN}"
        send_resolved: true

  - name: critical
    webhook_configs:
      - url: "https://oapi.dingtalk.com/robot/send?access_token=${DINGTALK_CRITICAL_TOKEN}"
        send_resolved: true
    email_configs:
      - to: "oncall@thesisminer.example.com"
        headers:
          Subject: '[CRITICAL] {{ .CommonLabels.alertname }}'

  - name: warning
    webhook_configs:
      - url: "https://oapi.dingtalk.com/robot/send?access_token=${DINGTALK_TOKEN}"
        send_resolved: true

inhibit_rules:
  - source_match:
      severity: critical
    target_match:
      severity: warning
    equal: ["cluster", "namespace", "app"]
```

### 12.5 Grafana 仪表盘

| 仪表盘 | 用途 | 关键面板 |
|--------|------|----------|
| 概览 | 系统整体状态 | QPS / 错误率 / 延迟 / 副本数 |
| API | HTTP 接口监控 | 各 endpoint QPS / 延迟 / 状态码分布 |
| LLM | LLM 调用监控 | 调用量 / 延迟 / Token 消耗 / 缓存命中 |
| 数据库 | SQLite 监控 | 连接数 / 查询延迟 / WAL 大小 |
| 缓存 | Redis 监控 | 命中率 / 内存 / QPS / 慢查询 |
| K8s | 集群监控 | 节点资源 / Pod 状态 / HPA |
| Agent | Multi-Agent 监控 | 各 Agent 任务量 / 耗时 / 失败率 |

### 12.6 指标暴露示例

```python
# backend/monitoring/metrics_middleware.py
"""FastAPI 指标采集中间件"""
import time
from fastapi import Request

from backend.monitoring.metrics import (
    http_requests_total,
    http_request_duration_seconds,
    active_sessions,
)


async def metrics_middleware(request: Request, call_next):
    """采集 HTTP 请求指标"""
    start_time = time.time()
    method = request.method
    endpoint = request.url.path

    try:
        response = await call_next(request)
        status = response.status_code
    except Exception as e:
        status = 500
        raise e
    finally:
        duration = time.time() - start_time
        http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status=status,
        ).inc()
        http_request_duration_seconds.labels(
            method=method,
            endpoint=endpoint,
        ).observe(duration)

    return response
```

---

## 13. 日志聚合

### 13.1 日志架构

```
┌─────────────────────────────────────────────────────────────────┐
│  日志聚合架构                                                    │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  应用层 (Pod)                                              │   │
│  │  ┌────────────────────────────────────────────────┐      │   │
│  │  │  FastAPI / Agents → stdout (JSON 格式)          │      │   │
│  │  └────────────────────────────────────────────────┘      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────▼──────────────────────────────┐   │
│  │  采集层 (DaemonSet)                                        │   │
│  │  ┌────────────────────────────────────────────────┐      │   │
│  │  │  Promtail (每个节点一个)                         │      │   │
│  │  │  - 读取 /var/log/containers/*.log               │      │   │
│  │  │  - 解析 JSON                                    │      │   │
│  │  │  - 添加 K8s 元数据 (namespace/pod/container)     │      │   │
│  │  │  - 推送到 Loki                                  │      │   │
│  │  └────────────────────────────────────────────────┘      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────▼──────────────────────────────┐   │
│  │  存储层                                                    │   │
│  │  ┌────────────────────────────────────────────────┐      │   │
│  │  │  Loki (压缩存储, 索引仅元数据)                   │      │   │
│  │  │  - 短期: 本地 SSD (7 天)                         │      │   │
│  │  │  - 长期: S3 (90 天)                              │      │   │
│  │  └────────────────────────────────────────────────┘      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────▼──────────────────────────────┐   │
│  │  查询层                                                    │   │
│  │  ┌────────────────────────────────────────────────┐      │   │
│  │  │  Grafana → LogQL 查询                           │      │   │
│  │  │  - 实时日志流                                    │      │   │
│  │  │  - 历史日志搜索                                  │      │   │
│  │  │  - 日志告警                                      │      │   │
│  │  └────────────────────────────────────────────────┘      │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 13.2 JSON 日志格式

```python
# backend/monitoring/logging_config.py
"""结构化日志配置"""
import logging
import sys
from datetime import datetime
from pythonjsonlogger import jsonlogger


class ThesisMinerJsonFormatter(jsonlogger.JsonFormatter):
    """自定义 JSON 日志格式器"""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record["timestamp"] = datetime.utcnow().isoformat() + "Z"
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["thread"] = record.threadName
        log_record["module"] = record.module
        log_record["line"] = record.lineno
        import os
        log_record["pod"] = os.getenv("POD_NAME", "local")
        log_record["namespace"] = os.getenv("POD_NAMESPACE", "default")
        log_record["container"] = os.getenv("CONTAINER_NAME", "thesisminer")
        from backend.monitoring.tracing import get_current_trace
        trace = get_current_trace()
        if trace:
            log_record["trace_id"] = trace.trace_id
            log_record["span_id"] = trace.span_id


def setup_logging(level: str = "INFO"):
    """初始化日志系统"""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(ThesisMinerJsonFormatter(
        "%(timestamp)s %(level)s %(logger)s %(message)s"
    ))
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)

    logging.getLogger("uvicorn.access").setLevel("WARNING")
    logging.getLogger("httpx").setLevel("WARNING")
    logging.getLogger("openai").setLevel("WARNING")
```

日志示例：

```json
{
  "timestamp": "2026-06-20T10:30:45.123Z",
  "level": "INFO",
  "logger": "backend.agents.orchestrator",
  "message": "Orchestrator 启动五阶段闭环",
  "module": "orchestrator",
  "line": 234,
  "thread": "MainThread",
  "pod": "thesisminer-backend-7d8f9-abc12",
  "namespace": "production",
  "container": "thesisminer",
  "trace_id": "abc123def456",
  "span_id": "span789",
  "session_id": "sess_001",
  "user_id": "user_123",
  "stage": "信息确权",
  "duration_ms": 1234
}
```

### 13.3 Promtail 配置

```yaml
# config/promtail/promtail.yml
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /var/log/positions.yaml

clients:
  - url: http://loki.observability:3100/loki/api/v1/push
    tenant_id: production

scrape_configs:
  - job_name: kubernetes-pods
    kubernetes_sd_configs:
      - role: pod
    pipeline_stages:
      - json:
          expressions:
            level: level
            logger: logger
            message: message
            timestamp: timestamp
            trace_id: trace_id
            session_id: session_id
      - timestamp:
          source: timestamp
          format: RFC3339Nano
      - labels:
          level:
          logger:
      - output:
          source: message
    relabel_configs:
      - source_labels: [__meta_kubernetes_namespace]
        target_label: namespace
      - source_labels: [__meta_kubernetes_pod_name]
        target_label: pod
      - source_labels: [__meta_kubernetes_pod_label_app]
        target_label: app
      - source_labels: [__meta_kubernetes_pod_label_component]
        target_label: component
      - source_labels: [__meta_kubernetes_container_name]
        target_label: container
      - source_labels: [__meta_kubernetes_pod_label_app]
        regex: thesisminer
        action: keep
```

### 13.4 LogQL 查询示例

```logql
# 1. 查看最近 5 分钟所有 ERROR 日志
{namespace="production", level="ERROR"} |= "" | json | line_format "{{.timestamp}} [{{.logger}}] {{.message}}"

# 2. 查找特定 trace_id 的所有日志
{namespace="production"} |= "trace_id=\"abc123def456\""

# 3. 统计最近 1 小时各 logger 的 ERROR 数量
sum by (logger) (count_over_time({namespace="production", level="ERROR"}[1h]))

# 4. 查找包含 "数据库" 的日志
{namespace="production"} |= "数据库"

# 5. 查找 LLM 调用超时的日志
{namespace="production", logger="backend.ai.deepseek"} |= "timeout"

# 6. 统计每分钟日志量趋势
sum by (app) (count_over_time({namespace="production"}[1m]))

# 7. 查找特定会话的所有日志
{namespace="production"} |= "session_id=\"sess_001\""

# 8. 错误率告警
sum(rate({namespace="production", level="ERROR"}[5m])) by (app) > 1
```

### 13.5 日志保留策略

| 日志类型 | 短期保留 | 长期归档 | 存储位置 |
|----------|----------|----------|----------|
| 应用日志 (INFO+) | 7 天 | 30 天 | Loki (本地) → S3 |
| 错误日志 (ERROR+) | 30 天 | 90 天 | Loki (本地) → S3 |
| 访问日志 | 3 天 | 7 天 | Loki (本地) |
| 审计日志 | 90 天 | 1 年 | Loki (S3) |
| K8s 系统日志 | 7 天 | 30 天 | Loki (本地) → S3 |

---

## 14. 链路追踪

### 14.1 追踪架构

```
┌─────────────────────────────────────────────────────────────────┐
│  分布式追踪架构                                                  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  应用层 (Instrumentation)                                  │   │
│  │  ┌────────────────────────────────────────────────┐      │   │
│  │  │  OpenTelemetry SDK                              │      │   │
│  │  │  - 自动注入: FastAPI / httpx / sqlite3          │      │   │
│  │  │  - 手动 Span: 业务关键路径                       │      │   │
│  │  │  - Context 传播: W3C TraceContext               │      │   │
│  │  └────────────────────────────────────────────────┘      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────▼──────────────────────────────┐   │
│  │  采集层                                                    │   │
│  │  ┌────────────────────────────────────────────────┐      │   │
│  │  │  OTel Collector (DaemonSet)                     │      │   │
│  │  │  - 接收 OTLP                                    │      │   │
│  │  │  - 批处理 / 重试                                 │      │   │
│  │  │  - 推送到 Jaeger                                 │      │   │
│  │  └────────────────────────────────────────────────┘      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────▼──────────────────────────────┐   │
│  │  存储与查询层                                              │   │
│  │  ┌────────────────────────────────────────────────┐      │   │
│  │  │  Jaeger                                         │      │   │
│  │  │  - 存储: Elasticsearch (7 天)                   │      │   │
│  │  │  - 查询: Jaeger UI / API                        │      │   │
│  │  └────────────────────────────────────────────────┘      │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 14.2 OpenTelemetry 集成

```python
# backend/monitoring/tracing.py
"""OpenTelemetry 链路追踪配置"""
import os
from typing import Optional

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlite3 import SQLite3Instrumentor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import SpanKind


class TraceContext:
    """当前追踪上下文"""
    def __init__(self, trace_id: str, span_id: str):
        self.trace_id = trace_id
        self.span_id = span_id


def get_current_trace() -> Optional[TraceContext]:
    """获取当前 Span 的 trace 信息"""
    span = trace.get_current_span()
    if not span or not span.is_recording():
        return None
    ctx = span.get_span_context()
    return TraceContext(
        trace_id=f"{ctx.trace_id:032x}",
        span_id=f"{ctx.span_id:016x}",
    )


def setup_tracing(app, service_name: str = "thesisminer"):
    """初始化链路追踪"""
    resource = Resource.create({
        SERVICE_NAME: service_name,
        "service.version": "8.0.0",
        "deployment.environment": os.getenv("APP_ENV", "development"),
        "pod.name": os.getenv("POD_NAME", "local"),
        "namespace": os.getenv("POD_NAMESPACE", "default"),
    })

    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(
        endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"),
        insecure=True,
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()
    SQLite3Instrumentor().instrument()


def create_span(name: str, kind: SpanKind = SpanKind.INTERNAL):
    """创建自定义 Span 的装饰器"""
    tracer = trace.get_tracer(__name__)

    def decorator(func):
        async def wrapper(*args, **kwargs):
            with tracer.start_as_current_span(name, kind=kind) as span:
                for key, value in kwargs.items():
                    if isinstance(value, (str, int, float, bool)):
                        span.set_attribute(f"arg.{key}", value)
                try:
                    result = await func(*args, **kwargs)
                    span.set_attribute("success", True)
                    return result
                except Exception as e:
                    span.set_attribute("success", False)
                    span.set_attribute("error", str(e))
                    span.record_exception(e)
                    raise

        return wrapper
    return decorator
```

### 14.3 业务 Span 示例

```python
# backend/agents/orchestrator.py
"""Orchestrator 业务追踪示例"""
import time
from opentelemetry import trace
from opentelemetry.trace import SpanKind

from backend.monitoring.tracing import create_span


class Orchestrator:
    """主调度 Agent"""

    def __init__(self):
        self.tracer = trace.get_tracer("backend.agents.orchestrator")

    async def run_five_stage_loop(self, session_id: str, topic: str):
        """运行五阶段闭环: 信息确权 → 创意 → 校验 → 生成 → 深度辅助"""
        with self.tracer.start_as_current_span(
            "orchestrator.five_stage_loop",
            kind=SpanKind.INTERNAL,
        ) as span:
            span.set_attribute("session.id", session_id)
            span.set_attribute("session.topic", topic)

            # Stage 1: 信息确权
            with self.tracer.start_as_current_span("stage.信息确权") as s1:
                s1.set_attribute("stage.index", 1)
                result1 = await self._run_stage("信息确权", session_id, topic)
                s1.set_attribute("stage.duration_ms", result1.duration_ms)

            # Stage 2: 创意
            with self.tracer.start_as_current_span("stage.创意") as s2:
                s2.set_attribute("stage.index", 2)
                result2 = await self._run_stage("创意", session_id, topic)
                s2.set_attribute("stage.duration_ms", result2.duration_ms)

            # Stage 3: 校验
            with self.tracer.start_as_current_span("stage.校验") as s3:
                s3.set_attribute("stage.index", 3)
                result3 = await self._run_stage("校验", session_id, topic)
                s3.set_attribute("stage.duration_ms", result3.duration_ms)

            # Stage 4: 生成
            with self.tracer.start_as_current_span("stage.生成") as s4:
                s4.set_attribute("stage.index", 4)
                result4 = await self._run_stage("生成", session_id, topic)
                s4.set_attribute("stage.duration_ms", result4.duration_ms)

            # Stage 5: 深度辅助
            with self.tracer.start_as_current_span("stage.深度辅助") as s5:
                s5.set_attribute("stage.index", 5)
                result5 = await self._run_stage("深度辅助", session_id, topic)
                s5.set_attribute("stage.duration_ms", result5.duration_ms)

            span.set_attribute("loop.success", True)
            return result5

    async def _run_stage(self, stage_name: str, session_id: str, topic: str):
        """执行单个阶段"""
        start = time.time()
        # 实际业务逻辑...
        await asyncio.sleep(0.1)
        return StageResult(
            stage=stage_name,
            duration_ms=int((time.time() - start) * 1000),
        )
```

### 14.4 LLM 调用追踪

```python
# backend/ai/deepseek_client.py
"""DeepSeek LLM 调用追踪"""
import time
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode


class DeepSeekClient:
    """DeepSeek API 客户端（带追踪）"""

    def __init__(self):
        self.tracer = trace.get_tracer("backend.ai.deepseek")

    async def chat(self, messages: list, model: str = "deepseek-chat"):
        """调用 DeepSeek Chat API"""
        with self.tracer.start_as_current_span(
            "deepseek.chat",
            kind=SpanKind.CLIENT,
        ) as span:
            span.set_attribute("llm.provider", "deepseek")
            span.set_attribute("llm.model", model)
            span.set_attribute("llm.message_count", len(messages))
            span.set_attribute("llm.prompt_length", sum(len(m["content"]) for m in messages))

            # 检查缓存
            cache_key = self._compute_cache_key(messages, model)
            cached = await self._cache_get(cache_key)
            if cached:
                span.set_attribute("llm.cache_hit", True)
                span.set_attribute("llm.cached_tokens", cached.usage.total_tokens)
                return cached

            span.set_attribute("llm.cache_hit", False)

            try:
                start = time.time()
                response = await self._call_api(messages, model)
                duration = time.time() - start

                span.set_attribute("llm.duration_ms", int(duration * 1000))
                span.set_attribute("llm.prompt_tokens", response.usage.prompt_tokens)
                span.set_attribute("llm.completion_tokens", response.usage.completion_tokens)
                span.set_attribute("llm.total_tokens", response.usage.total_tokens)

                # 写入缓存
                await self._cache_set(cache_key, response)

                return response
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise
```

### 14.5 Jaeger 部署

Jaeger 作为分布式链路追踪的后端存储与 UI，负责接收、存储与查询 OpenTelemetry 上报的 trace 数据。

```
┌─────────────────────────────────────────────────────────────────┐
│  Jaeger 部署架构                                                 │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Collector (Deployment, 3 副本)                            │   │
│  │  - 接收 OTLP gRPC/HTTP 数据                                │   │
│  │  - 校验、采样、批处理                                       │   │
│  │  - 写入存储后端                                             │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────▼──────────────────────────────┐   │
│  │  存储后端                                                  │   │
│  │  - 短期: Badger (本地 SSD, 7 天)                           │   │
│  │  - 长期: Elasticsearch (90 天)                             │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────▼──────────────────────────────┐   │
│  │  Query + UI (Deployment, 2 副本)                           │   │
│  │  - 查询接口                                                │   │
│  │  - Web UI (依赖关系图、火焰图)                              │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────▼──────────────────────────────┐   │
│  │  Ingress                                                   │   │
│  │  - jaeger.thesisminer.local → Query UI                    │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

```yaml
# deploy/k8s/observability/jaeger.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: jaeger
  namespace: observability
  labels:
    app: jaeger
spec:
  replicas: 2
  selector:
    matchLabels:
      app: jaeger
  template:
    metadata:
      labels:
        app: jaeger
    spec:
      containers:
        - name: jaeger
          image: jaegertracing/all-in-one:1.52
          args:
            - "--memory.max-traces=50000"
            - "--query.base-path=/jaeger"
          env:
            - name: COLLECTOR_OTLP_ENABLED
              value: "true"
            - name: SPAN_STORAGE_TYPE
              value: memory
          ports:
            - name: otlp-grpc
              containerPort: 4317
            - name: otlp-http
              containerPort: 4318
            - name: ui
              containerPort: 16686
          resources:
            requests:
              cpu: 200m
              memory: 512Mi
            limits:
              cpu: 1000m
              memory: 2Gi
          readinessProbe:
            httpGet:
              path: /
              port: 16686
            initialDelaySeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: jaeger-collector
  namespace: observability
spec:
  selector:
    app: jaeger
  ports:
    - name: otlp-grpc
      port: 4317
      targetPort: 4317
    - name: otlp-http
      port: 4318
      targetPort: 4318
---
apiVersion: v1
kind: Service
metadata:
  name: jaeger-query
  namespace: observability
spec:
  selector:
    app: jaeger
  ports:
    - name: ui
      port: 16686
      targetPort: 16686
```

### 14.6 采样策略

为控制 trace 数据量，采用头部采样（Head Sampling）与尾部采样（Tail Sampling）相结合的策略：

| 采样策略 | 采样率 | 适用场景 | 优点 | 缺点 |
|---------|--------|---------|------|------|
| 头部采样 | 10% | 日常监控 | 实现简单、开销低 | 可能漏掉慢请求 |
| 尾部采样 | 100% (慢请求) | 故障排查 | 保留所有慢请求 trace | 需要缓冲、延迟高 |
| 强制采样 | 100% | Debug 模式 | 完整数据 | 数据量大 |
| 按服务采样 | 5%-20% | 多服务场景 | 灵活控制 | 配置复杂 |

```python
# backend/monitoring/tracing.py
"""采样策略配置"""
from opentelemetry.sdk.trace.sampling import (
    Sampler,
    ParentBased,
    TraceIdRatioBased,
    ALWAYS_ON,
)


def build_sampler(debug: bool = False) -> Sampler:
    """构建采样器"""
    if debug:
        return ALWAYS_ON

    # 头部采样: 10% 基础采样率
    base_sampler = TraceIdRatioBased(rate=0.1)
    # 遵循父 span 的采样决策
    return ParentBased(root=base_sampler)
```

### 14.7 追踪数据保留策略

| 数据类型 | 存储后端 | 保留周期 | 滚动策略 |
|---------|---------|---------|---------|
| 短期 trace | Badger (内存/SSD) | 7 天 | 自动删除 |
| 长期 trace | Elasticsearch | 90 天 | ILM 滚动 |
| 异常 trace | Elasticsearch | 180 天 | 标记保留 |
| 采样统计 | Prometheus | 30 天 | 自动降采样 |

---

## 15. 数据库部署

### 15.1 SQLite 部署策略

ThesisMiner v8.0 采用 SQLite（启用 WAL 模式）作为主数据库。SQLite 的部署策略与传统的客户端/服务器型数据库（如 PostgreSQL、MySQL）有显著差异，需要特别关注并发写入、数据持久化与备份策略。

```
┌─────────────────────────────────────────────────────────────────┐
│  SQLite 部署架构                                                 │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Pod (StatefulSet)                                         │   │
│  │  ┌────────────────────────────────────────────────────┐  │   │
│  │  │  FastAPI Backend                                    │  │   │
│  │  │  ┌──────────────────────────────────────────────┐  │  │   │
│  │  │  │  SQLAlchemy ORM                                │  │  │   │
│  │  │  │  - 连接池 (size=10)                            │  │  │   │
│  │  │  │  - WAL 模式                                    │  │  │   │
│  │  │  └──────────────────────────────────────────────┘  │  │   │
│  │  └────────────────────────────────────────────────────┘  │   │
│  │  ┌────────────────────────────────────────────────────┐  │   │
│  │  │  PVC (持久卷)                                       │  │   │
│  │  │  /data/thesisminer.db                               │  │   │
│  │  │  /data/thesisminer.db-wal                           │  │   │
│  │  │  /data/thesisminer.db-shm                           │  │   │
│  │  └────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────▼──────────────────────────────┐   │
│  │  定时备份 CronJob                                          │   │
│  │  - 每小时: 增量备份 (WAL checkpoint + copy)                │   │
│  │  - 每天: 全量备份 (sqlite3 .backup)                       │   │
│  │  - 备份上传到 S3/MinIO                                     │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 15.2 SQLite 优化配置

```python
# backend/db/sqlite_config.py
"""SQLite 优化配置"""
import sqlite3
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool


def create_optimized_engine(db_path: str):
    """创建优化后的 SQLite 引擎"""
    engine = create_engine(
        f"sqlite:///{db_path}",
        # SQLite 不支持真正的连接池，使用 StaticPool 复用单连接
        poolclass=StaticPool,
        pool_size=10,
        max_overflow=0,
        # 关闭 SQL 日志（生产环境）
        echo=False,
        # 连接参数
        connect_args={
            "check_same_thread": False,
            "timeout": 30,  # 锁等待超时 30s
        },
    )

    # 设置 PRAGMA 优化
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        # 启用 WAL 模式（允许并发读写）
        cursor.execute("PRAGMA journal_mode=WAL")
        # WAL 自动 checkpoint 策略
        cursor.execute("PRAGMA wal_autocheckpoint=1000")
        # 同步模式: NORMAL（WAL 模式下安全且更快）
        cursor.execute("PRAGMA synchronous=NORMAL")
        # 临时存储: 内存
        cursor.execute("PRAGMA temp_store=MEMORY")
        # 缓存大小: 64MB
        cursor.execute("PRAGMA cache_size=-65536")
        # 页大小: 4096（默认值，适合大多数场景）
        cursor.execute("PRAGMA page_size=4096")
        # mmap 大小: 256MB
        cursor.execute("PRAGMA mmap_size=268435456")
        # 忙等待超时: 30s
        cursor.execute("PRAGMA busy_timeout=30000")
        # 外键约束
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine
```

### 15.3 WAL Checkpoint 管理

```python
# backend/db/wal_manager.py
"""WAL Checkpoint 管理器"""
import sqlite3
import threading
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class WALManager:
    """WAL 文件检查点管理器

    定期执行 checkpoint，防止 WAL 文件过大影响性能。
    """

    def __init__(self, db_path: str, checkpoint_interval: int = 300):
        self.db_path = db_path
        self.checkpoint_interval = checkpoint_interval  # 默认 5 分钟
        self._timer = None
        self._running = False

    def start(self):
        """启动定时 checkpoint"""
        self._running = True
        self._schedule_next()

    def stop(self):
        """停止定时 checkpoint"""
        self._running = False
        if self._timer:
            self._timer.cancel()

    def _schedule_next(self):
        if not self._running:
            return
        self._timer = threading.Timer(
            self.checkpoint_interval, self._checkpoint
        )
        self._timer.daemon = True
        self._timer.start()

    def _checkpoint(self):
        try:
            conn = sqlite3.connect(self.db_path)
            # PASSIVE 模式: 不阻塞读写
            result = conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
            busy, log_frames, checkpointed_frames = result.fetchone()
            logger.info(
                "WAL checkpoint 完成",
                extra={
                    "busy": busy,
                    "log_frames": log_frames,
                    "checkpointed_frames": checkpointed_frames,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
            conn.close()
        except Exception as e:
            logger.error(f"WAL checkpoint 失败: {e}", exc_info=True)
        finally:
            self._schedule_next()

    def force_checkpoint(self):
        """强制 checkpoint（RESTART 模式）"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA wal_checkpoint(RESTART)")
        conn.close()
```

### 15.4 数据库备份策略

```python
# backend/db/backup.py
"""数据库备份策略"""
import sqlite3
import shutil
import os
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class DatabaseBackup:
    """SQLite 数据库备份管理"""

    def __init__(self, db_path: str, backup_dir: str, max_backups: int = 24):
        self.db_path = db_path
        self.backup_dir = Path(backup_dir)
        self.max_backups = max_backups
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def backup(self) -> str:
        """执行在线备份（使用 SQLite Online Backup API）"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"thesisminer_{timestamp}.db"

        source = sqlite3.connect(self.db_path)
        target = sqlite3.connect(str(backup_path))

        try:
            source.backup(target)
            logger.info(f"数据库备份完成: {backup_path}")
            self._rotate()
            return str(backup_path)
        except Exception as e:
            logger.error(f"数据库备份失败: {e}", exc_info=True)
            raise
        finally:
            source.close()
            target.close()

    def _rotate(self):
        """滚动删除旧备份"""
        backups = sorted(
            self.backup_dir.glob("thesisminer_*.db"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old_backup in backups[self.max_backups:]:
            old_backup.unlink()
            logger.info(f"删除旧备份: {old_backup}")

    def restore(self, backup_path: str):
        """从备份恢复数据库"""
        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"备份文件不存在: {backup_path}")

        # 先备份当前数据库
        if os.path.exists(self.db_path):
            corrupt_backup = self.db_path + ".corrupt"
            shutil.move(self.db_path, corrupt_backup)

        # 恢复
        shutil.copy2(backup_path, self.db_path)
        logger.info(f"数据库从 {backup_path} 恢复成功")
```

### 15.5 数据库备份 CronJob

```yaml
# deploy/k8s/database/backup-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: db-backup
  namespace: thesisminer
spec:
  schedule: "0 * * * *"  # 每小时执行
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 5
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          volumes:
            - name: data
              persistentVolumeClaim:
                claimName: sqlite-data
            - name: backup
              emptyDir: {}
          containers:
            - name: backup
              image: thesisminer/backend:8.0
              command:
                - /bin/sh
                - -c
                - |
                  python -m backend.db.backup --upload-s3
              volumeMounts:
                - name: data
                  mountPath: /data
                - name: backup
                  mountPath: /backup
              env:
                - name: DB_PATH
                  value: /data/thesisminer.db
                - name: BACKUP_DIR
                  value: /backup
                - name: S3_BUCKET
                  valueFrom:
                    secretKeyRef:
                      name: backup-secret
                      key: s3-bucket
```

### 15.6 数据库监控指标

| 指标名称 | 类型 | 说明 | 告警阈值 |
|---------|------|------|---------|
| sqlite_db_size_bytes | Gauge | 数据库文件大小 | > 10GB |
| sqlite_wal_size_bytes | Gauge | WAL 文件大小 | > 1GB |
| sqlite_connection_count | Gauge | 活跃连接数 | > 50 |
| sqlite_query_duration_seconds | Histogram | 查询耗时 P99 | > 1s |
| sqlite_lock_wait_seconds | Histogram | 锁等待时间 P99 | > 5s |
| sqlite_checkpoint_duration_seconds | Histogram | Checkpoint 耗时 | > 30s |
| sqlite_backup_success_total | Counter | 备份成功次数 | - |
| sqlite_backup_failure_total | Counter | 备份失败次数 | > 0 |

---

## 16. 缓存部署

### 16.1 多级缓存架构

ThesisMiner v8.0 采用三级缓存架构，平衡访问速度与数据一致性：

```
┌─────────────────────────────────────────────────────────────────┐
│  三级缓存架构                                                    │
│                                                                  │
│  请求 ──→ L1 (进程内缓存)                                        │
│           ├─ 命中 → 返回 (延迟 < 0.1ms)                          │
│           └─ 未命中 ↓                                            │
│                                                                  │
│           L2 (Redis 分布式缓存)                                   │
│           ├─ 命中 → 回填 L1 → 返回 (延迟 < 1ms)                   │
│           └─ 未命中 ↓                                            │
│                                                                  │
│           L3 (SQLite 持久化缓存)                                  │
│           ├─ 命中 → 回填 L1/L2 → 返回 (延迟 < 10ms)               │
│           └─ 未命中 ↓                                            │
│                                                                  │
│           数据源 (LLM API / 计算)                                 │
│           └─ 写入 L1/L2/L3 → 返回 (延迟 > 1s)                     │
└─────────────────────────────────────────────────────────────────┘
```

### 16.2 Redis 主从 + Sentinel 部署

```
┌─────────────────────────────────────────────────────────────────┐
│  Redis 高可用架构                                                │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Sentinel 集群 (3 节点)                                    │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐                   │   │
│  │  │Sentinel1│  │Sentinel2│  │Sentinel3│                   │   │
│  │  └────┬────┘  └────┬────┘  └────┬────┘                   │   │
│  └───────┼────────────┼────────────┼────────────────────────┘   │
│          │            │            │                             │
│  ┌───────▼────────────▼────────────▼────────────────────────┐   │
│  │  Redis 集群                                                │   │
│  │  ┌─────────┐     ┌─────────┐     ┌─────────┐              │   │
│  │  │ Master  │ ←→  │ Replica │     │ Replica │              │   │
│  │  │ (读/写) │     │ (只读)  │     │ (只读)  │              │   │
│  │  └─────────┘     └─────────┘     └─────────┘              │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌───────────────────────────▼──────────────────────────────┐   │
│  │  Backend Pod (通过 Sentinel 发现 Master)                   │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

```yaml
# deploy/k8s/cache/redis-statefulset.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: redis
  namespace: thesisminer
spec:
  serviceName: redis-headless
  replicas: 3  # 1 master + 2 replicas
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      terminationGracePeriodSeconds: 30
      containers:
        - name: redis
          image: redis:7.2-alpine
          command:
            - redis-server
            - /etc/redis/redis.conf
            - --replica-announce-ip
            - "$(POD_IP)"
            - --replica-announce-port
            - "6379"
          ports:
            - name: redis
              containerPort: 6379
          env:
            - name: POD_IP
              valueFrom:
                fieldRef:
                  fieldPath: status.podIP
          volumeMounts:
            - name: config
              mountPath: /etc/redis
            - name: data
              mountPath: /data
          resources:
            requests:
              cpu: 100m
              memory: 256Mi
            limits:
              cpu: 500m
              memory: 1Gi
          livenessProbe:
            exec:
              command: ["redis-cli", "ping"]
            initialDelaySeconds: 10
          readinessProbe:
            exec:
              command: ["redis-cli", "ping"]
            initialDelaySeconds: 5
      volumes:
        - name: config
          configMap:
            name: redis-config
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 5Gi
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: redis-config
  namespace: thesisminer
data:
  redis.conf: |
    bind 0.0.0.0
    protected-mode yes
    port 6379
    maxmemory 512mb
    maxmemory-policy allkeys-lru
    appendonly yes
    appendfsync everysec
    save 900 1
    save 300 10
    save 60 10000
```

### 16.3 Sentinel 部署

```yaml
# deploy/k8s/cache/redis-sentinel.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis-sentinel
  namespace: thesisminer
spec:
  replicas: 3
  selector:
    matchLabels:
      app: redis-sentinel
  template:
    metadata:
      labels:
        app: redis-sentinel
    spec:
      containers:
        - name: sentinel
          image: redis:7.2-alpine
          command:
            - redis-sentinel
            - /etc/redis/sentinel.conf
          ports:
            - name: sentinel
              containerPort: 26379
          volumeMounts:
            - name: config
              mountPath: /etc/redis
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 200m
              memory: 256Mi
      volumes:
        - name: config
          configMap:
            name: sentinel-config
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: sentinel-config
  namespace: thesisminer
data:
  sentinel.conf: |
    port 26379
    sentinel monitor mymaster redis-0.redis-headless 6379 2
    sentinel down-after-milliseconds mymaster 5000
    sentinel failover-timeout mymaster 30000
    sentinel parallel-syncs mymaster 1
```

### 16.4 缓存策略

| 缓存策略 | 适用场景 | TTL | 失效方式 | 示例 |
|---------|---------|-----|---------|------|
| Cache-Aside | LLM 响应 | 1 小时 | 主动 + TTL | 论文分析结果 |
| Write-Through | 用户配置 | 永久 | 主动失效 | 用户偏好设置 |
| Write-Behind | 统计数据 | 5 分钟 | 定时刷盘 | 访问计数 |
| Refresh-Ahead | 热点数据 | 1 小时 | 提前刷新 | 热门论文列表 |

```python
# backend/cache/multi_level.py
"""多级缓存实现"""
import json
import time
import threading
from typing import Any, Optional
from collections import OrderedDict


class L1Cache:
    """L1 进程内缓存（LRU）"""

    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self._cache = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._cache:
                return None
            value, expire_at = self._cache[key]
            if time.time() > expire_at:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        with self._lock:
            ttl = ttl or self._default_ttl
            expire_at = time.time() + ttl
            self._cache[key] = (value, expire_at)
            self._cache.move_to_end(key)
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    def delete(self, key: str):
        with self._lock:
            self._cache.pop(key, None)

    def clear(self):
        with self._lock:
            self._cache.clear()


class MultiLevelCache:
    """三级缓存协调器"""

    def __init__(self, l1: L1Cache, l2, l3=None):
        self.l1 = l1
        self.l2 = l2  # Redis client
        self.l3 = l3  # SQLite cache (optional)

    async def get(self, key: str) -> Optional[Any]:
        # L1
        value = self.l1.get(key)
        if value is not None:
            return value
        # L2
        value = await self.l2.get(key)
        if value is not None:
            self.l1.set(key, value)
            return value
        # L3
        if self.l3:
            value = await self.l3.get(key)
            if value is not None:
                self.l1.set(key, value)
                await self.l2.set(key, value)
                return value
        return None

    async def set(self, key: str, value: Any, ttl: int = 3600):
        self.l1.set(key, value, ttl)
        await self.l2.set(key, value, ttl)
        if self.l3:
            await self.l3.set(key, value, ttl)

    async def delete(self, key: str):
        self.l1.delete(key)
        await self.l2.delete(key)
        if self.l3:
            await self.l3.delete(key)
```

### 16.5 缓存监控指标

| 指标名称 | 类型 | 说明 | 告警阈值 |
|---------|------|------|---------|
| cache_l1_hit_total | Counter | L1 命中次数 | - |
| cache_l1_miss_total | Counter | L1 未命中次数 | - |
| cache_l2_hit_total | Counter | L2 命中次数 | - |
| cache_l2_miss_total | Counter | L2 未命中次数 | - |
| cache_hit_rate | Gauge | 缓存命中率 | < 80% |
| cache_eviction_total | Counter | 缓存驱逐次数 | - |
| redis_memory_used_bytes | Gauge | Redis 内存使用 | > 80% maxmemory |
| redis_connected_clients | Gauge | Redis 连接数 | > 100 |
| redis_replication_lag_seconds | Gauge | 主从复制延迟 | > 5s |

---

## 17. 消息队列部署

### 17.1 队列方案选型

ThesisMiner v8.0 根据部署规模提供两种消息队列方案：

| 方案 | 适用场景 | 优点 | 缺点 | 最大吞吐 |
|------|---------|------|------|---------|
| SQLite 队列表 | 单机 / 小规模 | 零依赖、简单 | 吞吐有限、无持久化保证 | ~100 msg/s |
| Redis Stream | 中大规模 | 高吞吐、消费者组 | 依赖 Redis | ~10000 msg/s |

### 17.2 SQLite 队列表设计

```python
# backend/queue/sqlite_queue.py
"""基于 SQLite 的消息队列"""
import sqlite3
import json
import time
import uuid
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class SQLiteQueue:
    """SQLite 消息队列

    利用 SQLite 的事务特性实现可靠的消息投递。
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS message_queue (
                id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                available_at REAL DEFAULT 0,
                created_at REAL NOT NULL,
                processed_at REAL,
                consumer_id TEXT
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_queue_topic_status "
            "ON message_queue(topic, status, available_at)"
        )
        conn.commit()
        conn.close()

    def enqueue(self, topic: str, payload: Dict[str, Any], delay: float = 0) -> str:
        msg_id = str(uuid.uuid4())
        conn = sqlite3.connect(self.db_path, timeout=30)
        try:
            conn.execute(
                "INSERT INTO message_queue (id, topic, payload, available_at, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (msg_id, topic, json.dumps(payload), time.time() + delay, time.time()),
            )
            conn.commit()
            logger.info(f"消息入队: topic={topic}, id={msg_id}")
            return msg_id
        finally:
            conn.close()

    def dequeue(self, topic: str, consumer_id: str, timeout: float = 5) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path, timeout=30)
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT id, payload, retry_count FROM message_queue "
                "WHERE topic=? AND status='pending' AND available_at<=? "
                "ORDER BY created_at LIMIT 1",
                (topic, time.time()),
            ).fetchone()

            if row is None:
                conn.rollback()
                return None

            msg_id, payload, retry_count = row
            conn.execute(
                "UPDATE message_queue SET status='processing', consumer_id=?, "
                "processed_at=? WHERE id=?",
                (consumer_id, time.time(), msg_id),
            )
            conn.commit()
            return {
                "id": msg_id,
                "payload": json.loads(payload),
                "retry_count": retry_count,
            }
        finally:
            conn.close()

    def ack(self, msg_id: str):
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute(
            "UPDATE message_queue SET status='completed' WHERE id=?", (msg_id,)
        )
        conn.commit()
        conn.close()

    def nack(self, msg_id: str, retry_delay: float = 60):
        conn = sqlite3.connect(self.db_path, timeout=30)
        row = conn.execute(
            "SELECT retry_count, max_retries FROM message_queue WHERE id=?", (msg_id,)
        ).fetchone()
        if row is None:
            conn.close()
            return
        retry_count, max_retries = row
        if retry_count >= max_retries:
            conn.execute(
                "UPDATE message_queue SET status='dead_letter' WHERE id=?", (msg_id,)
            )
        else:
            conn.execute(
                "UPDATE message_queue SET status='pending', retry_count=retry_count+1, "
                "available_at=? WHERE id=?",
                (time.time() + retry_delay, msg_id),
            )
        conn.commit()
        conn.close()
```

### 17.3 Worker 部署

```yaml
# deploy/k8s/queue/worker-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: worker
  namespace: thesisminer
  labels:
    app: worker
spec:
  replicas: 3
  selector:
    matchLabels:
      app: worker
  template:
    metadata:
      labels:
        app: worker
    spec:
      containers:
        - name: worker
          image: thesisminer/backend:8.0
          command: ["python", "-m", "backend.queue.worker"]
          env:
            - name: WORKER_CONCURRENCY
              value: "4"
            - name: QUEUE_TYPE
              value: "redis_stream"
            - name: REDIS_URL
              valueFrom:
                secretKeyRef:
                  name: redis-secret
                  key: url
          resources:
            requests:
              cpu: 200m
              memory: 512Mi
            limits:
              cpu: 1000m
              memory: 2Gi
          livenessProbe:
            exec:
              command: ["python", "-c", "import backend.queue.health; backend.queue.health.check()"]
            initialDelaySeconds: 30
            periodSeconds: 60
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: worker-hpa
  namespace: thesisminer
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: worker
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: External
      external:
        metric:
          name: redis_stream_pending_messages
          target:
            type: AverageValue
            averageValue: "10"
```

### 17.4 Redis Stream 方案

```python
# backend/queue/redis_stream.py
"""基于 Redis Stream 的消息队列"""
import json
import asyncio
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class RedisStreamQueue:
    """Redis Stream 消息队列"""

    def __init__(self, redis_client, consumer_group: str = "thesisminer"):
        self.redis = redis_client
        self.consumer_group = consumer_group
        self._consumer_name = None

    async def ensure_group(self, stream: str):
        """确保消费者组存在"""
        try:
            await self.redis.xgroup_create(stream, self.consumer_group, id="0")
        except Exception as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def enqueue(self, stream: str, payload: Dict[str, Any]) -> str:
        msg_id = await self.redis.xadd(stream, {"data": json.dumps(payload)})
        logger.info(f"消息入队: stream={stream}, id={msg_id}")
        return msg_id

    async def dequeue(
        self, stream: str, consumer: str, block: int = 5000
    ) -> Optional[Dict]:
        await self.ensure_group(stream)
        result = await self.redis.xreadgroup(
            self.consumer_group,
            consumer,
            {stream: ">"},
            count=1,
            block=block,
        )
        if not result:
            return None
        messages = result[0][1]
        if not messages:
            return None
        msg_id, fields = messages[0]
        return {
            "id": msg_id,
            "payload": json.loads(fields[b"data"]),
        }

    async def ack(self, stream: str, msg_id: str):
        await self.redis.xack(stream, self.consumer_group, msg_id)

    async def get_pending_count(self, stream: str) -> int:
        info = await self.redis.xpending(stream, self.consumer_group)
        return info["pending"]
```

### 17.5 死信队列处理

```python
# backend/queue/dead_letter.py
"""死信队列处理"""
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)


class DeadLetterHandler:
    """死信队列处理器"""

    def __init__(self, alert_callback=None):
        self.alert_callback = alert_callback

    async def handle(self, msg_id: str, payload: dict, error: str, topic: str):
        """处理死信消息"""
        logger.error(
            "消息进入死信队列",
            extra={
                "msg_id": msg_id,
                "topic": topic,
                "error": error,
                "payload": payload,
            },
        )

        # 记录到数据库
        await self._persist_dead_letter(msg_id, payload, error, topic)

        # 触发告警
        if self.alert_callback:
            await self.alert_callback(
                title="死信队列告警",
                message=f"Topic {topic} 消息 {msg_id} 处理失败: {error}",
                severity="warning",
            )

    async def _persist_dead_letter(self, msg_id, payload, error, topic):
        # 持久化到 dead_letter 表
        pass

    async def replay(self, msg_id: str):
        """重放死信消息"""
        # 从死信表读取并重新入队
        pass
```

### 17.6 队列监控指标

| 指标名称 | 类型 | 说明 | 告警阈值 |
|---------|------|------|---------|
| queue_depth | Gauge | 队列深度 | > 1000 |
| queue_enqueue_total | Counter | 入队总数 | - |
| queue_dequeue_total | Counter | 出队总数 | - |
| queue_process_duration_seconds | Histogram | 处理耗时 P99 | > 30s |
| queue_retry_total | Counter | 重试次数 | - |
| queue_dead_letter_total | Counter | 死信数量 | > 0 |
| queue_consumer_lag_seconds | Gauge | 消费延迟 | > 60s |

---

## 18. 安全部署

### 18.1 安全防御纵深架构

```
┌─────────────────────────────────────────────────────────────────┐
│  安全防御纵深架构                                                │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  第 1 层: 网络边界                                          │   │
│  │  - WAF (Web Application Firewall)                          │   │
│  │  - DDoS 防护                                               │   │
│  │  - IP 白名单 / 黑名单                                       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────▼──────────────────────────────┐   │
│  │  第 2 层: 入口控制                                          │   │
│  │  - TLS 终止 (Ingress)                                      │   │
│  │  - 速率限制                                                │   │
│  │  - 请求大小限制                                             │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────▼──────────────────────────────┐   │
│  │  第 3 层: 身份认证                                          │   │
│  │  - API Key 验证                                            │   │
│  │  - JWT Token                                               │   │
│  │  - OAuth 2.0 (可选)                                        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────▼──────────────────────────────┐   │
│  │  第 4 层: 授权                                              │   │
│  │  - RBAC 角色控制                                            │   │
│  │  - 资源级权限                                               │   │
│  │  - 多租户隔离                                               │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────▼──────────────────────────────┐   │
│  │  第 5 层: 应用安全                                          │   │
│  │  - 输入校验 (Pydantic)                                      │   │
│  │  - SQL 注入防护                                             │   │
│  │  - XSS / CSRF 防护                                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────▼──────────────────────────────┐   │
│  │  第 6 层: 数据安全                                          │   │
│  │  - 静态数据加密                                             │   │
│  │  - 传输加密 (mTLS)                                          │   │
│  │  - 密钥管理 (Vault)                                         │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 18.2 Pod SecurityContext

```yaml
# deploy/k8s/security/pod-security-context.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
  namespace: thesisminer
spec:
  template:
    spec:
      securityContext:
        # 以非 root 用户运行
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
        # 只读根文件系统
        fsGroupChangePolicy: "OnRootMismatch"
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: backend
          securityContext:
            # 禁止特权模式
            privileged: false
            # 禁止能力提升
            allowPrivilegeEscalation: false
            # 只读根文件系统
            readOnlyRootFilesystem: true
            # 丢弃所有 Linux capabilities
            capabilities:
              drop:
                - ALL
            # 只允许必要的 capabilities
            capabilities:
              add: ["NET_BIND_SERVICE"]
              drop: ["ALL"]
          # 可写目录通过 emptyDir 挂载
          volumeMounts:
            - name: tmp
              mountPath: /tmp
            - name: cache
              mountPath: /app/cache
      volumes:
        - name: tmp
          emptyDir: {}
        - name: cache
          emptyDir: {}
```

### 18.3 TLS 证书管理

```yaml
# deploy/k8s/security/cert-manager.yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: thesisminer-tls
  namespace: thesisminer
spec:
  secretName: thesisminer-tls
  duration: 2160h  # 90 天
  renewBefore: 360h  # 提前 15 天续期
  dnsNames:
    - thesisminer.local
    - "*.thesisminer.local"
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
---
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@thesisminer.local
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
      - http01:
          ingress:
            class: nginx
```

### 18.4 Vault 密钥管理

```python
# backend/security/vault_client.py
"""HashiCorp Vault 密钥管理客户端"""
import os
import logging
import hvac
from typing import Optional

logger = logging.getLogger(__name__)


class VaultClient:
    """Vault 密钥管理客户端"""

    def __init__(self):
        self.client = hvac.Client(
            url=os.getenv("VAULT_ADDR", "https://vault:8200"),
            token=os.getenv("VAULT_TOKEN"),
        )
        self._mount_point = "secret"
        self._cache = {}

    def get_secret(self, path: str, key: str) -> Optional[str]:
        """获取密钥"""
        cache_key = f"{path}/{key}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=path, mount_point=self._mount_point
            )
            value = response["data"]["data"].get(key)
            if value:
                self._cache[cache_key] = value
            return value
        except Exception as e:
            logger.error(f"获取密钥失败: path={path}, key={key}, error={e}")
            return None

    def get_llm_api_key(self) -> str:
        """获取 LLM API Key"""
        return self.get_secret("thesisminer/llm", "api_key")

    def get_database_url(self) -> str:
        """获取数据库连接字符串"""
        return self.get_secret("thesisminer/db", "url")
```

### 18.5 镜像签名与验证

```yaml
# deploy/k8s/security/cosign-verification.yaml
apiVersion: policy.sigstore.dev/v1beta1
kind: ClusterImagePolicy
metadata:
  name: thesisminer-image-policy
spec:
  images:
    - glob: "registry.thesisminer.local/thesisminer/**"
  authorities:
    - name: cosign
      key:
        data: |
          -----BEGIN PUBLIC KEY-----
          <cosign 公钥内容>
          -----END PUBLIC KEY-----
      attestations:
        - name: vuln-attestation
          predicateType: vuln
          policy:
            type: cue
            data: |
              predicateType: "https://example.com/vuln/v1"
              predicate: {
                scanner: "trivy"
                findings: [...]
              }
```

```bash
# 镜像签名脚本
#!/bin/bash
# scripts/sign-image.sh
set -euo pipefail

IMAGE="${1:?Usage: sign-image.sh <image>}"
COSIGN_PRIVATE_KEY="${COSIGN_PRIVATE_KEY:?COSIGN_PRIVATE_KEY not set}"

# 签名镜像
cosign sign --key env://COSIGN_PRIVATE_KEY "$IMAGE"

# 生成 SBOM
syft "$IMAGE" -o spdx-json > sbom.json

# 附加 SBOM attestation
cosign attest --key env://COSIGN_PRIVATE_KEY \
  --predicate sbom.json \
  --type spdxjson \
  "$IMAGE"

# 生成漏洞扫描报告
trivy image --format json "$IMAGE" > vuln-report.json

# 附加漏洞扫描 attestation
cosign attest --key env://COSIGN_PRIVATE_KEY \
  --predicate vuln-report.json \
  --type vuln \
  "$IMAGE"

echo "镜像签名完成: $IMAGE"
```

### 18.6 网络策略安全

```yaml
# deploy/k8s/security/default-deny.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: thesisminer
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
---
# 仅允许 Backend 访问数据库
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: backend-to-db
  namespace: thesisminer
spec:
  podSelector:
    matchLabels:
      app: sqlite
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: backend
      ports:
        - protocol: TCP
          port: 8080
```

---

## 19. 网络隔离

### 19.1 网络隔离拓扑

```
┌─────────────────────────────────────────────────────────────────┐
│  网络隔离拓扑                                                    │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  公网 (Internet)                                            │   │
│  │  0.0.0.0/0                                                  │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             │                                    │
│                  ┌──────────▼──────────┐                        │
│                  │  WAF + LoadBalancer  │                        │
│                  │  (公网入口)           │                        │
│                  └──────────┬──────────┘                        │
│                             │                                    │
│  ┌──────────────────────────▼───────────────────────────────┐   │
│  │  DMZ 区 (dmz namespace)                                     │   │
│  │  - Ingress Controller                                        │   │
│  │  - Cert Manager                                              │   │
│  │  - External DNS                                              │   │
│  │  网段: 10.0.1.0/24                                            │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             │                                    │
│  ┌──────────────────────────▼───────────────────────────────┐   │
│  │  应用区 (thesisminer namespace)                              │   │
│  │  - Backend Pods                                              │   │
│  │  - Worker Pods                                               │   │
│  │  网段: 10.0.2.0/24                                            │   │
│  └──────────┬───────────────────────────┬────────────────────┘   │
│             │                           │                        │
│  ┌──────────▼────────────┐  ┌──────────▼────────────────────┐   │
│  │  数据区 (data ns)       │  │  可观测区 (observability ns)  │   │
│  │  - SQLite StatefulSet   │  │  - Prometheus                 │   │
│  │  - Redis StatefulSet    │  │  - Grafana                    │   │
│  │  网段: 10.0.3.0/24       │  │  - Loki                       │   │
│  └─────────────────────────┘  │  - Jaeger                     │   │
│                                │  网段: 10.0.4.0/24              │   │
│                                └───────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 19.2 Namespace 隔离

```yaml
# deploy/k8s/network/namespaces.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: dmz
  labels:
    environment: dmz
    network-zone: dmz
---
apiVersion: v1
kind: Namespace
metadata:
  name: thesisminer
  labels:
    environment: production
    network-zone: app
---
apiVersion: v1
kind: Namespace
metadata:
  name: data
  labels:
    environment: production
    network-zone: data
---
apiVersion: v1
kind: Namespace
metadata:
  name: observability
  labels:
    environment: production
    network-zone: observability
```

### 19.3 跨命名空间网络策略

```yaml
# deploy/k8s/network/cross-namespace-policy.yaml
# 允许 DMZ 区访问应用区
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dmz-to-app
  namespace: thesisminer
spec:
  podSelector:
    matchLabels:
      app: backend
  policyTypes:
    - Ingress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              network-zone: dmz
      ports:
        - protocol: TCP
          port: 8000
---
# 允许应用区访问数据区
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-app-to-data
  namespace: data
spec:
  podSelector: {}
  policyTypes:
    - Ingress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              network-zone: app
---
# 允许应用区访问可观测区
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-app-to-observability
  namespace: observability
spec:
  podSelector: {}
  policyTypes:
    - Ingress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              network-zone: app
      ports:
        - protocol: TCP
          port: 9090  # Prometheus
        - protocol: TCP
          port: 4317  # OTLP gRPC
        - protocol: TCP
          port: 4318  # OTLP HTTP
---
# 限制应用区出站到外网（仅允许 LLM API）
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: restrict-egress
  namespace: thesisminer
spec:
  podSelector: {}
  policyTypes:
    - Egress
  egress:
    # DNS
    - to:
        - namespaceSelector: {}
      ports:
        - protocol: UDP
          port: 53
    # 数据区
    - to:
        - namespaceSelector:
            matchLabels:
              network-zone: data
    # 可观测区
    - to:
        - namespaceSelector:
            matchLabels:
              network-zone: observability
    # 同命名空间内部通信
    - to:
        - podSelector: {}
    # LLM API 出站（通过 NAT Gateway）
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
            except:
              - 10.0.0.0/8
              - 172.16.0.0/12
              - 192.168.0.0/16
      ports:
        - protocol: TCP
          port: 443
```

### 19.4 Service Mesh mTLS

```yaml
# deploy/k8s/network/istio-peer-auth.yaml
# 全局 STRICT mTLS
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: istio-system
spec:
  mtls:
    mode: STRICT
---
# 数据区命名空间 STRICT mTLS
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: data
spec:
  mtls:
    mode: STRICT
  selector:
    matchLabels:
      network-zone: data
```

---

## 20. 访问控制

### 20.1 RBAC 角色模型

```
┌─────────────────────────────────────────────────────────────────┐
│  RBAC 角色模型                                                   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  用户层                                                     │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐     │   │
│  │  │ Admin   │  │Developer│  │ Viewer  │  │ Service │     │   │
│  │  │         │  │         │  │         │  │ Account │     │   │
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘     │   │
│  └───────┼────────────┼────────────┼────────────┼───────────┘   │
│          │            │            │            │                │
│  ┌───────▼────────────▼────────────▼────────────▼───────────┐   │
│  │  角色绑定 (RoleBinding / ClusterRoleBinding)               │   │
│  └───────┬────────────┬────────────┬────────────┬───────────┘   │
│          │            │            │            │                │
│  ┌───────▼────────────▼────────────▼────────────▼───────────┐   │
│  │  权限 (Role / ClusterRole)                                 │   │
│  │  - get / list / watch / create / update / delete           │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 20.2 K8s RBAC 配置

```yaml
# deploy/k8s/rbac/backend-role.yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: backend-role
  namespace: thesisminer
rules:
  # 读取自身配置
  - apiGroups: [""]
    resources: ["configmaps", "secrets"]
    verbs: ["get", "list", "watch"]
    resourceNames: ["backend-config", "backend-secret"]
  # 读取 Pod 信息（用于服务发现）
  - apiGroups: [""]
    resources: ["pods", "endpoints", "services"]
    verbs: ["get", "list", "watch"]
  # 自身 Pod 日志
  - apiGroups: [""]
    resources: ["pods/log"]
    verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: backend-rolebinding
  namespace: thesisminer
subjects:
  - kind: ServiceAccount
    name: backend-sa
    namespace: thesisminer
roleRef:
  kind: Role
  name: backend-role
  apiGroup: rbac.authorization.k8s.io
---
# 管理员角色
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: thesisminer-admin
rules:
  - apiGroups: ["*"]
    resources: ["*"]
    verbs: ["*"]
    resourceNames:
      - "thesisminer/*"
      - "data/*"
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: thesisminer-admin-binding
subjects:
  - kind: Group
    name: thesisminer-admins
    apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: ClusterRole
  name: thesisminer-admin
  apiGroup: rbac.authorization.k8s.io
```

### 20.3 应用层访问控制

```python
# backend/security/access_control.py
"""应用层访问控制"""
import logging
from enum import Enum
from functools import wraps
from typing import List, Optional

logger = logging.getLogger(__name__)


class Role(str, Enum):
    ADMIN = "admin"
    RESEARCHER = "researcher"
    VIEWER = "viewer"
    SERVICE = "service"


class Permission(str, Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    EXPORT = "export"


# 角色-权限映射
ROLE_PERMISSIONS = {
    Role.ADMIN: {
        Permission.READ, Permission.WRITE, Permission.DELETE,
        Permission.ADMIN, Permission.EXPORT,
    },
    Role.RESEARCHER: {Permission.READ, Permission.WRITE, Permission.EXPORT},
    Role.VIEWER: {Permission.READ},
    Role.SERVICE: {Permission.READ, Permission.WRITE},
}


def require_permission(permission: Permission):
    """权限校验装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user=None, **kwargs):
            if current_user is None:
                raise PermissionError("未认证用户")
            user_permissions = ROLE_PERMISSIONS.get(
                Role(current_user.role), set()
            )
            if permission not in user_permissions:
                logger.warning(
                    "权限拒绝",
                    extra={
                        "user": current_user.username,
                        "role": current_user.role,
                        "required_permission": permission,
                    },
                )
                raise PermissionError(
                    f"权限不足: 需要 {permission.value} 权限"
                )
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator


class RateLimiter:
    """基于用户的速率限制"""

    def __init__(self, redis_client):
        self.redis = redis_client

    async def check(self, user_id: str, limit: int = 100, window: int = 60):
        """检查速率限制

        Args:
            user_id: 用户 ID
            limit: 窗口内最大请求数
            window: 时间窗口（秒）
        """
        key = f"rate_limit:{user_id}:{window}"
        current = await self.redis.incr(key)
        if current == 1:
            await self.redis.expire(key, window)
        if current > limit:
            ttl = await self.redis.ttl(key)
            raise RateLimitExceeded(
                f"速率超限: {limit} 请求 / {window} 秒, 请 {ttl} 秒后重试"
            )


class RateLimitExceeded(Exception):
    pass
```

### 20.4 API Key 管理

```python
# backend/security/api_key.py
"""API Key 管理"""
import hashlib
import secrets
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class APIKeyManager:
    """API Key 管理器

    API Key 格式: tm_<random32bytes>
    存储: 仅存储 SHA-256 哈希值
    """

    PREFIX = "tm_"

    @staticmethod
    def generate() -> str:
        """生成新的 API Key"""
        random_part = secrets.token_urlsafe(32)
        return f"{APIKeyManager.PREFIX}{random_part}"

    @staticmethod
    def hash(key: str) -> str:
        """计算 API Key 的哈希值"""
        return hashlib.sha256(key.encode()).hexdigest()

    @staticmethod
    def validate_format(key: str) -> bool:
        """校验 API Key 格式"""
        if not key or not key.startswith(APIKeyManager.PREFIX):
            return False
        return len(key) > len(APIKeyManager.PREFIX) + 16

    async def create(self, user_id: str, name: str, expires_at: Optional[datetime] = None) -> str:
        """创建 API Key（仅返回一次明文）"""
        raw_key = self.generate()
        key_hash = self.hash(raw_key)
        # 存储 key_hash 到数据库
        await self._store_key(user_id, name, key_hash, expires_at)
        logger.info(f"API Key 创建: user={user_id}, name={name}")
        return raw_key

    async def verify(self, raw_key: str) -> Optional[dict]:
        """验证 API Key"""
        if not self.validate_format(raw_key):
            return None
        key_hash = self.hash(raw_key)
        key_info = await self._lookup_key(key_hash)
        if key_info is None:
            return None
        if key_info.get("expires_at") and key_info["expires_at"] < datetime.utcnow():
            return None
        return key_info

    async def _store_key(self, user_id, name, key_hash, expires_at):
        pass

    async def _lookup_key(self, key_hash):
        pass

    async def revoke(self, key_id: str):
        """吊销 API Key"""
        await self._delete_key(key_id)
        logger.info(f"API Key 吊销: id={key_id}")
```

### 20.5 审计日志

```python
# backend/security/audit.py
"""审计日志"""
import logging
import json
from datetime import datetime
from typing import Optional

logger = logging.getLogger("audit")


class AuditLogger:
    """安全审计日志记录器"""

    def __init__(self, db_session=None):
        self.db = db_session

    async def log(
        self,
        action: str,
        user: Optional[str] = None,
        resource: Optional[str] = None,
        resource_id: Optional[str] = None,
        result: str = "success",
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        """记录审计事件"""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "user": user,
            "resource": resource,
            "resource_id": resource_id,
            "result": result,
            "details": details or {},
            "ip_address": ip_address,
            "user_agent": user_agent,
        }
        # 结构化日志
        logger.info(json.dumps(event, ensure_ascii=False))
        # 持久化到数据库
        if self.db:
            await self._persist(event)

    async def _persist(self, event: dict):
        pass
```

---

## 21. 灾备方案

### 21.1 灾备架构

```
┌─────────────────────────────────────────────────────────────────┐
│  灾备架构（同城双活）                                              │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  主数据中心 (AZ-A)                                          │   │
│  │  ┌────────────────────────────────────────────────────┐  │   │
│  │  │  K8s Cluster A                                       │  │   │
│  │  │  - Backend (3 副本)                                   │  │   │
│  │  │  - Worker (3 副本)                                    │  │   │
│  │  │  - SQLite (主)                                        │  │   │
│  │  │  - Redis (主)                                         │  │   │
│  │  └────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             │                                    │
│                    ┌────────▼────────┐                           │
│                    │  数据同步         │                           │
│                    │  - SQLite 复制   │                           │
│                    │  - Redis 复制    │                           │
│                    │  - 对象存储同步   │                           │
│                    └────────┬────────┘                           │
│                             │                                    │
│  ┌──────────────────────────▼───────────────────────────────┐   │
│  │  备数据中心 (AZ-B)                                          │   │
│  │  ┌────────────────────────────────────────────────────┐  │   │
│  │  │  K8s Cluster B                                       │  │   │
│  │  │  - Backend (3 副本, 待命)                              │  │   │
│  │  │  - Worker (3 副本, 待命)                               │  │   │
│  │  │  - SQLite (备)                                        │  │   │
│  │  │  - Redis (备)                                         │  │   │
│  │  └────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  全局负载均衡 (GSLB)                                         │   │
│  │  - 健康检查                                                │   │
│  │  - 自动故障切换                                             │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 21.2 RTO 与 RPO 目标

| 指标 | 目标 | 说明 |
|------|------|------|
| RTO (恢复时间目标) | < 15 分钟 | 从故障到服务恢复 |
| RPO (恢复点目标) | < 1 小时 | 最大数据丢失量 |
| MTTR (平均恢复时间) | < 30 分钟 | 平均故障恢复时间 |
| 可用性 SLA | 99.9% | 年度可用性目标 |
| 数据备份频率 | 1 小时 | 增量备份间隔 |
| 全量备份频率 | 1 天 | 全量备份间隔 |

### 21.3 备份与恢复策略

```python
# backend/backup/disaster_recovery.py
"""灾备管理器"""
import logging
import asyncio
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class DisasterRecovery:
    """灾备管理器"""

    def __init__(self, db_backup, cache_backup, storage_backup):
        self.db_backup = db_backup
        self.cache_backup = cache_backup
        self.storage_backup = storage_backup

    async def backup_all(self) -> dict:
        """全量备份"""
        timestamp = datetime.utcnow().isoformat()
        results = {"timestamp": timestamp, "components": {}}

        # 数据库备份
        try:
            db_path = await self.db_backup.backup()
            results["components"]["database"] = {
                "status": "success", "path": db_path
            }
        except Exception as e:
            results["components"]["database"] = {
                "status": "failed", "error": str(e)
            }
            logger.error(f"数据库备份失败: {e}", exc_info=True)

        # 缓存持久化备份
        try:
            cache_path = await self.cache_backup.backup()
            results["components"]["cache"] = {
                "status": "success", "path": cache_path
            }
        except Exception as e:
            results["components"]["cache"] = {
                "status": "failed", "error": str(e)
            }

        # 对象存储同步
        try:
            await self.storage_backup.sync()
            results["components"]["storage"] = {"status": "success"}
        except Exception as e:
            results["components"]["storage"] = {
                "status": "failed", "error": str(e)
            }

        # 上传备份清单
        await self._upload_manifest(results)
        return results

    async def restore_all(self, backup_timestamp: str) -> dict:
        """全量恢复"""
        results = {"timestamp": backup_timestamp, "components": {}}

        # 恢复数据库
        try:
            await self.db_backup.restore(backup_timestamp)
            results["components"]["database"] = {"status": "success"}
        except Exception as e:
            results["components"]["database"] = {
                "status": "failed", "error": str(e)
            }

        # 恢复缓存
        try:
            await self.cache_backup.restore(backup_timestamp)
            results["components"]["cache"] = {"status": "success"}
        except Exception as e:
            results["components"]["cache"] = {
                "status": "failed", "error": str(e)
            }

        return results

    async def _upload_manifest(self, manifest: dict):
        """上传备份清单"""
        pass

    async def verify_backup(self, backup_timestamp: str) -> bool:
        """验证备份完整性"""
        checks = await asyncio.gather(
            self.db_backup.verify(backup_timestamp),
            self.cache_backup.verify(backup_timestamp),
            return_exceptions=True,
        )
        return all(check is True for check in checks)
```

### 21.4 故障切换流程

```
┌─────────────────────────────────────────────────────────────────┐
│  故障切换流程                                                    │
│                                                                  │
│  1. 检测故障                                                     │
│     └─ 健康检查连续失败 3 次 (间隔 30s)                           │
│                                                                  │
│  2. 故障确认                                                     │
│     └─ 值班工程师确认 / 自动确认 (生产环境)                        │
│                                                                  │
│  3. 启动故障切换                                                  │
│     ├─ GSLB 将流量切到备数据中心                                   │
│     ├─ 备数据中心提升为主                                          │
│     └─ 通知相关人员                                               │
│                                                                  │
│  4. 数据同步状态确认                                              │
│     └─ 确认备数据中心数据完整性                                     │
│                                                                  │
│  5. 服务恢复确认                                                  │
│     └─ 健康检查通过、关键功能验证                                   │
│                                                                  │
│  6. 故障复盘                                                      │
│     └─ 事后分析、改进措施                                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 22. 故障恢复

### 22.1 故障分级

| 级别 | 描述 | 影响范围 | 响应时间 | 恢复目标 |
|------|------|---------|---------|---------|
| P0 | 服务完全不可用 | 全部用户 | 5 分钟 | 30 分钟 |
| P1 | 核心功能不可用 | 大部分用户 | 10 分钟 | 1 小时 |
| P2 | 部分功能不可用 | 部分用户 | 30 分钟 | 4 小时 |
| P3 | 性能下降 | 所有用户 | 2 小时 | 8 小时 |
| P4 | 个别问题 | 个别用户 | 1 工作日 | 3 工作日 |

### 22.2 常见故障与恢复

```python
# backend/recovery/fault_recovery.py
"""故障恢复处理器"""
import logging
import asyncio
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class FaultType(str, Enum):
    DATABASE_LOCK = "database_lock"
    DATABASE_CORRUPT = "database_corrupt"
    REDIS_UNAVAILABLE = "redis_unavailable"
    LLM_API_TIMEOUT = "llm_api_timeout"
    LLM_API_ERROR = "llm_api_error"
    POD_CRASH = "pod_crash"
    DISK_FULL = "disk_full"
    MEMORY_LEAK = "memory_leak"


class FaultRecoveryHandler:
    """故障恢复处理器"""

    async def handle(self, fault_type: FaultType, context: dict) -> dict:
        """处理故障"""
        handler = getattr(self, f"_handle_{fault_type.value}", None)
        if handler is None:
            logger.error(f"未知故障类型: {fault_type}")
            return {"status": "unknown_fault"}

        logger.warning(f"处理故障: {fault_type}", extra=context)
        try:
            result = await handler(context)
            logger.info(f"故障恢复完成: {fault_type}", extra=result)
            return result
        except Exception as e:
            logger.error(f"故障恢复失败: {fault_type}: {e}", exc_info=True)
            return {"status": "failed", "error": str(e)}

    async def _handle_database_lock(self, context: dict) -> dict:
        """处理数据库锁"""
        # 1. 检查锁状态
        # 2. 等待锁释放
        # 3. 必要时重启连接
        await asyncio.sleep(5)
        return {"status": "recovered", "action": "wait_lock"}

    async def _handle_database_corrupt(self, context: dict) -> dict:
        """处理数据库损坏"""
        # 1. 标记数据库为只读
        # 2. 从最近备份恢复
        # 3. 验证数据完整性
        return {"status": "recovered", "action": "restore_from_backup"}

    async def _handle_redis_unavailable(self, context: dict) -> dict:
        """处理 Redis 不可用"""
        # 1. 降级到 L1 缓存
        # 2. 尝试重连
        # 3. 触发告警
        return {"status": "degraded", "action": "fallback_to_l1"}

    async def _handle_llm_api_timeout(self, context: dict) -> dict:
        """处理 LLM API 超时"""
        # 1. 重试（指数退避）
        # 2. 切换备用模型
        # 3. 返回缓存结果
        return {"status": "recovered", "action": "retry_or_fallback"}

    async def _handle_disk_full(self, context: dict) -> dict:
        """处理磁盘满"""
        # 1. 清理临时文件
        # 2. 清理旧日志
        # 3. 触发告警
        return {"status": "recovered", "action": "cleanup"}
```

### 22.3 自动恢复脚本

```bash
#!/bin/bash
# scripts/auto-recovery.sh
set -euo pipefail

NAMESPACE="thesisminer"

# 检查 Backend Pod 状态
check_backend_pods() {
    local not_ready
    not_ready=$(kubectl get pods -n "$NAMESPACE" -l app=backend \
        --no-headers | grep -v "Running" | wc -l)
    if [ "$not_ready" -gt 0 ]; then
        echo "WARN: $not_ready backend pods not ready"
        return 1
    fi
    return 0
}

# 重启不健康的 Pod
restart_unhealthy_pods() {
    local app=$1
    kubectl get pods -n "$NAMESPACE" -l app="$app" --no-headers | \
    while read pod status; do
        if [ "$status" != "Running" ]; then
            echo "重启 Pod: $pod"
            kubectl delete pod "$pod" -n "$NAMESPACE"
        fi
    done
}

# 清理磁盘空间
cleanup_disk() {
    # 清理已完成的 Job
    kubectl delete jobs -n "$NAMESPACE" --field-selector=status.successful=1
    # 清理悬空镜像
    kubectl get nodes -o name | while read node; do
        kubectl debug "node/$node" --image=busybox -- chage -s /root
    done
}

# 主恢复流程
main() {
    if ! check_backend_pods; then
        restart_unhealthy_pods backend
    fi
    cleanup_disk
}

main
```

---

## 23. 业务连续性

### 23.1 业务连续性计划 (BCP)

```
┌─────────────────────────────────────────────────────────────────┐
│  业务连续性计划 (BCP)                                             │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  预防阶段                                                   │   │
│  │  - 容量规划                                                 │   │
│  │  - 冗余部署                                                 │   │
│  │  - 定期备份                                                 │   │
│  │  - 监控告警                                                 │   │
│  │  - 演练测试                                                 │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  响应阶段                                                   │   │
│  │  - 故障检测                                                 │   │
│  │  - 影响评估                                                 │   │
│  │  - 应急处置                                                 │   │
│  │  - 通信协调                                                 │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  恢复阶段                                                   │   │
│  │  - 服务恢复                                                 │   │
│  │  - 数据恢复                                                 │   │
│  │  - 功能验证                                                 │   │
│  │  - 流量恢复                                                 │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  复盘阶段                                                   │   │
│  │  - 根因分析                                                 │   │
│  │  - 改进措施                                                 │   │
│  │  - 文档更新                                                 │   │
│  │  - 培训分享                                                 │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 23.2 降级策略

| 故障场景 | 降级策略 | 用户体验 | 恢复条件 |
|---------|---------|---------|---------|
| LLM API 不可用 | 返回缓存结果 + 提示 | 部分功能受限 | API 恢复 |
| Redis 不可用 | 降级到 L1 缓存 | 性能下降 | Redis 恢复 |
| 数据库锁 | 请求排队等待 | 响应变慢 | 锁释放 |
| 数据库损坏 | 只读模式 + 告警 | 无法写入 | 恢复完成 |
| 磁盘满 | 禁止上传 + 清理 | 部分功能受限 | 空间释放 |
| 内存不足 | 拒绝新请求 | 服务部分可用 | 扩容完成 |

```python
# backend/recovery/degradation.py
"""降级策略管理器"""
import logging
from enum import Enum
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class DegradationLevel(str, Enum):
    NORMAL = "normal"          # 正常
    DEGRADED = "degraded"      # 降级
    LIMITED = "limited"        # 功能受限
    READONLY = "readonly"      # 只读
    EMERGENCY = "emergency"    # 紧急模式


class DegradationManager:
    """降级策略管理器"""

    def __init__(self):
        self._level = DegradationLevel.NORMAL
        self._reason: Optional[str] = None
        self._since: Optional[datetime] = None

    @property
    def level(self) -> DegradationLevel:
        return self._level

    def set_level(self, level: DegradationLevel, reason: str):
        """设置降级级别"""
        if level != self._level:
            logger.warning(
                "降级级别变更",
                extra={
                    "from": self._level.value,
                    "to": level.value,
                    "reason": reason,
                },
            )
            self._level = level
            self._reason = reason
            self._since = datetime.utcnow()

    def reset(self):
        """恢复正常"""
        if self._level != DegradationLevel.NORMAL:
            logger.info("降级恢复", extra={"previous_level": self._level.value})
            self._level = DegradationLevel.NORMAL
            self._reason = None
            self._since = None

    def can_write(self) -> bool:
        """是否允许写入"""
        return self._level in (DegradationLevel.NORMAL, DegradationLevel.DEGRADED)

    def can_call_llm(self) -> bool:
        """是否允许调用 LLM"""
        return self._level in (
            DegradationLevel.NORMAL, DegradationLevel.DEGRADED, DegradationLevel.LIMITED
        )

    def get_status(self) -> dict:
        """获取降级状态"""
        return {
            "level": self._level.value,
            "reason": self._reason,
            "since": self._since.isoformat() if self._since else None,
        }
```

### 23.3 演练计划

| 演练类型 | 频率 | 范围 | 验证目标 |
|---------|------|------|---------|
| 备份恢复演练 | 每月 | 数据库 | 备份可用性、恢复时间 |
| 故障切换演练 | 每季度 | 全系统 | RTO、RPO 达标 |
| 混沌工程 | 每月 | 随机 Pod | 系统韧性 |
| 全链路压测 | 每季度 | 全系统 | 容量上限 |
| 安全演练 | 每半年 | 安全体系 | 安全响应能力 |

---

## 24. 部署检查清单

### 24.1 部署前检查

```markdown
## 部署前检查清单

### 基础设施
- [ ] K8s 集群版本 >= 1.27
- [ ] 节点资源充足（CPU/Memory/Disk）
- [ ] 网络策略配置完成
- [ ] StorageClass 已创建
- [ ] Ingress Controller 已部署
- [ ] cert-manager 已部署
- [ ] 镜像仓库可访问

### 配置
- [ ] ConfigMap 配置正确
- [ ] Secret 已创建（API Key、数据库密码等）
- [ ] 环境变量已设置
- [ ] 资源 Limit/Request 已配置
- [ ] HPA 已配置
- [ ] PDB 已配置

### 安全
- [ ] Pod SecurityContext 已配置
- [ ] NetworkPolicy 已配置
- [ ] RBAC 已配置
- [ ] ServiceAccount 已创建
- [ ] 镜像已签名验证
- [ ] TLS 证书已配置

### 可观测性
- [ ] Prometheus 已部署
- [ ] Grafana 已部署
- [ ] Alertmanager 已配置
- [ ] Loki 已部署
- [ ] Promtail 已部署
- [ ] Jaeger 已部署
- [ ] 仪表盘已导入
- [ ] 告警规则已配置
- [ ] 告警通知渠道已配置
```

### 24.2 部署后验证

```markdown
## 部署后验证清单

### 服务健康
- [ ] 所有 Pod 处于 Running 状态
- [ ] 所有 Deployment 副本数满足
- [ ] Liveness/Readiness Probe 通过
- [ ] 无 CrashLoopBackOff
- [ ] 无 OOMKilled

### 功能验证
- [ ] 健康检查接口返回 200
- [ ] API 文档可访问 (/docs)
- [ ] 核心功能可正常使用
- [ ] 数据库连接正常
- [ ] Redis 连接正常
- [ ] LLM API 可调用

### 性能验证
- [ ] P99 延迟 < 2s
- [ ] 错误率 < 0.1%
- [ ] CPU 使用率 < 70%
- [ ] 内存使用率 < 80%
- [ ] 磁盘使用率 < 70%

### 监控验证
- [ ] Prometheus 指标可采集
- [ ] Grafana 仪表盘有数据
- [ ] 日志可查询
- [ ] Trace 可查询
- [ ] 告警规则已生效
```

### 24.3 部署自动化脚本

```python
# scripts/deploy_verify.py
"""部署验证脚本"""
import subprocess
import sys
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DeployVerifier:
    """部署验证器"""

    def __init__(self, namespace: str = "thesisminer"):
        self.namespace = namespace

    def run(self) -> bool:
        """执行所有验证"""
        checks = [
            self.check_pods_running,
            self.check_deployments_ready,
            self.check_hpa_configured,
            self.check_ingress_ready,
            self.check_health_endpoint,
            self.check_metrics_endpoint,
        ]
        all_passed = True
        for check in checks:
            try:
                result = check()
                status = "PASS" if result else "FAIL"
                logger.info(f"[{status}] {check.__name__}")
                if not result:
                    all_passed = False
            except Exception as e:
                logger.error(f"[ERROR] {check.__name__}: {e}")
                all_passed = False
        return all_passed

    def check_pods_running(self) -> bool:
        result = subprocess.run(
            ["kubectl", "get", "pods", "-n", self.namespace, "--no-headers"],
            capture_output=True, text=True,
        )
        for line in result.stdout.strip().split("\n"):
            if "Running" not in line:
                return False
        return True

    def check_deployments_ready(self) -> bool:
        result = subprocess.run(
            ["kubectl", "get", "deploy", "-n", self.namespace, "--no-headers"],
            capture_output=True, text=True,
        )
        for line in result.stdout.strip().split("\n"):
            parts = line.split()
            if len(parts) >= 2 and parts[1] != parts[2]:
                return False
        return True

    def check_hpa_configured(self) -> bool:
        result = subprocess.run(
            ["kubectl", "get", "hpa", "-n", self.namespace", "--no-headers"],
            capture_output=True, text=True,
        )
        return len(result.stdout.strip()) > 0

    def check_ingress_ready(self) -> bool:
        result = subprocess.run(
            ["kubectl", "get", "ingress", "-n", self.namespace, "--no-headers"],
            capture_output=True, text=True,
        )
        return len(result.stdout.strip()) > 0

    def check_health_endpoint(self) -> bool:
        result = subprocess.run(
            ["kubectl", "exec", "-n", self.namespace,
             "deploy/backend", "--", "curl", "-s", "-o", "/dev/null",
             "-w", "%{http_code}", "http://localhost:8000/health"],
            capture_output=True, text=True,
        )
        return result.stdout.strip() == "200"

    def check_metrics_endpoint(self) -> bool:
        result = subprocess.run(
            ["kubectl", "exec", "-n", self.namespace,
             "deploy/backend", "--", "curl", "-s", "-o", "/dev/null",
             "-w", "%{http_code}", "http://localhost:8000/metrics"],
            capture_output=True, text=True,
        )
        return result.stdout.strip() == "200"


if __name__ == "__main__":
    verifier = DeployVerifier()
    if verifier.run():
        logger.info("所有验证通过")
        sys.exit(0)
    else:
        logger.error("验证失败")
        sys.exit(1)
```

---

## 25. 附录

### 25.1 常用 kubectl 命令

```bash
# 查看 ThesisMiner 资源
kubectl get all -n thesisminer

# 查看 Pod 日志
kubectl logs -n thesisminer -l app=backend --tail=100 -f

# 进入 Pod
kubectl exec -n thesisminer -it deploy/backend -- /bin/sh

# 端口转发
kubectl port-forward -n thesisminer svc/backend 8000:8000

# 查看 Pod 资源使用
kubectl top pods -n thesisminer

# 查看 Node 资源使用
kubectl top nodes

# 查看 Pod 详情
kubectl describe pod <pod-name> -n thesisminer

# 查看 Events
kubectl get events -n thesisminer --sort-by='.lastTimestamp'

# 滚动重启
kubectl rollout restart deploy/backend -n thesisminer

# 查看滚动状态
kubectl rollout status deploy/backend -n thesisminer

# 回滚
kubectl rollout undo deploy/backend -n thesisminer

# 扩缩容
kubectl scale deploy/backend -n thesisminer --replicas=5

# 查看 HPA
kubectl get hpa -n thesisminer

# 查看 NetworkPolicy
kubectl get networkpolicy -n thesisminer

# 查看 PVC
kubectl get pvc -n thesisminer

# 查看 ConfigMap
kubectl get configmap -n thesisminer

# 查看 Secret
kubectl get secret -n thesisminer
```

### 25.2 常用 Docker 命令

```bash
# 构建镜像
docker build -t thesisminer/backend:8.0 .

# 给镜像打标签
docker tag thesisminer/backend:8.0 registry.thesisminer.local/thesisminer/backend:8.0

# 推送镜像
docker push registry.thesisminer.local/thesisminer/backend:8.0

# 查看镜像
docker images | grep thesisminer

# 清理悬空镜像
docker image prune -f

# 查看容器日志
docker logs -f thesisminer-backend

# 进入容器
docker exec -it thesisminer-backend /bin/sh

# 查看容器资源使用
docker stats thesisminer-backend

# 查看容器详情
docker inspect thesisminer-backend
```

### 25.3 故障排查指南

| 现象 | 可能原因 | 排查步骤 |
|------|---------|---------|
| Pod CrashLoopBackOff | 配置错误/OOM/启动失败 | 1. 查看 logs 2. 查看 describe 3. 检查资源 |
| Pod Pending | 资源不足/调度失败 | 1. 查看 describe 2. 检查节点资源 3. 检查 PVC |
| 服务 502 | 后端不可用/健康检查失败 | 1. 查看 Pod 状态 2. 查看 Readiness 3. 查看日志 |
| 服务 504 | 响应超时 | 1. 查看延迟指标 2. 查看数据库 3. 查看 LLM |
| 响应变慢 | 资源不足/锁竞争 | 1. 查看 CPU/Memory 2. 查看数据库锁 3. 查看慢查询 |
| 数据库锁 | 长事务/并发写 | 1. 查看锁状态 2. 查看事务 3. 重启连接 |
| Redis 连接失败 | 网络问题/认证失败 | 1. 查看网络策略 2. 查看密码 3. 查看 Sentinel |
| LLM 调用失败 | API Key/限流/网络 | 1. 查看 Key 2. 查看限流 3. 查看网络 |

### 25.4 参考文档

| 文档 | 说明 |
|------|------|
| [Kubernetes 官方文档](https://kubernetes.io/docs/) | K8s 权威参考 |
| [Istio 官方文档](https://istio.io/docs/) | Service Mesh 参考 |
| [Prometheus 官方文档](https://prometheus.io/docs/) | 监控系统参考 |
| [Grafana 官方文档](https://grafana.com/docs/) | 可视化参考 |
| [Loki 官方文档](https://grafana.com/docs/loki/) | 日志聚合参考 |
| [Jaeger 官方文档](https://www.jaegertracing.io/docs/) | 链路追踪参考 |
| [OpenTelemetry 官方文档](https://opentelemetry.io/docs/) | 可观测性标准 |
| [SQLite 官方文档](https://www.sqlite.org/docs.html) | 数据库参考 |
| [Redis 官方文档](https://redis.io/docs/) | 缓存参考 |
| [Docker 官方文档](https://docs.docker.com/) | 容器化参考 |
| [FastAPI 官方文档](https://fastapi.tiangolo.com/) | Web 框架参考 |

### 25.5 变更记录

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|---------|------|
| v8.0.0 | 2026-06-20 | 初始版本，包含完整部署架构 | ThesisMiner Team |

---

**文档结束**