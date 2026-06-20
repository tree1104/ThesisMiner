# ThesisMiner v8.0 发布流程文档

> **文档版本**：v8.0.0
> **最后更新**：2026-06-20
> **文档负责**：ThesisMiner Release Engineering Team
> **审阅状态**：Approved
> **适用范围**：ThesisMiner v8.0 全部版本发布、回滚、热修复

---

## 目录

- [1. 概述](#1-概述)
  - [1.1 文档目的](#11-文档目的)
  - [1.2 发布理念](#12-发布理念)
  - [1.3 设计原则](#13-设计原则)
  - [1.4 术语表](#14-术语表)
- [2. 版本管理](#2-版本管理)
  - [2.1 语义化版本](#21-语义化版本)
  - [2.2 版本分支策略](#22-版本分支策略)
  - [2.3 版本号管理](#23-版本号管理)
  - [2.4 预发布版本](#24-预发布版本)
- [3. 发布策略](#3-发布策略)
  - [3.1 发布类型](#31-发布类型)
  - [3.2 蓝绿部署](#32-蓝绿部署)
  - [3.3 金丝雀发布](#33-金丝雀发布)
  - [3.4 滚动更新](#34-滚动更新)
  - [3.5 A/B 测试](#35-ab-测试)
  - [3.6 特性开关](#36-特性开关)
- [4. CI/CD 流水线](#4-cicd-流水线)
  - [4.1 流水线架构](#41-流水线架构)
  - [4.2 持续集成（CI）](#42-持续集成ci)
  - [4.3 持续交付（CD）](#43-持续交付cd)
  - [4.4 自动化测试](#44-自动化测试)
  - [4.5 自动化部署](#45-自动化部署)
  - [4.6 流水线配置](#46-流水线配置)
- [5. 变更日志与发布说明](#5-变更日志与发布说明)
  - [5.1 变更日志](#51-变更日志)
  - [5.2 发布说明](#52-发布说明)
  - [5.3 变更分类](#53-变更分类)
- [6. 发布流程](#6-发布流程)
  - [6.1 发布计划](#61-发布计划)
  - [6.2 发布前准备](#62-发布前准备)
  - [6.3 发布执行](#63-发布执行)
  - [6.4 发布后验证](#64-发布后验证)
  - [6.5 发布检查清单](#65-发布检查清单)
  - [6.6 发布审批](#66-发布审批)
  - [6.7 发布通知](#67-发布通知)
- [7. 回滚策略](#7-回滚策略)
  - [7.1 回滚分类](#71-回滚分类)
  - [7.2 自动回滚](#72-自动回滚)
  - [7.3 手动回滚](#73-手动回滚)
  - [7.4 紧急回滚](#74-紧急回滚)
  - [7.5 数据库回滚](#75-数据库回滚)
- [8. 发布后监控](#8-发布后监控)
  - [8.1 监控指标](#81-监控指标)
  - [8.2 异常响应](#82-异常响应)
  - [8.3 发布复盘](#83-发布复盘)
- [9. 发布案例研究](#9-发布案例研究)
  - [9.1 案例一：v8.0.0 大版本发布](#91-案例一v800-大版本发布)
  - [9.2 案例二：紧急热修复](#92-案例二紧急热修复)
  - [9.3 案例三：金丝雀发布失败](#93-案例三金丝雀发布失败)
  - [9.4 案例四：数据库迁移发布](#94-案例四数据库迁移发布)
  - [9.5 经验教训](#95-经验教训)
- [10. 最佳实践](#10-最佳实践)
  - [10.1 发布最佳实践](#101-发布最佳实践)
  - [10.2 回滚最佳实践](#102-回滚最佳实践)
  - [10.3 CI/CD 最佳实践](#103-cicd-最佳实践)
- [11. 附录](#11-附录)
  - [11.1 配置示例](#111-配置示例)
  - [11.2 模板](#112-模板)
  - [11.3 检查清单](#113-检查清单)
  - [11.4 变更记录](#114-变更记录)

---

## 1. 概述

### 1.1 文档目的

本文档定义 ThesisMiner v8.0 系统的发布流程规范，覆盖版本管理、发布策略、CI/CD 流水线、变更日志、发布流程、回滚策略、发布后监控、案例研究等主题。文档面向以下读者：

- **发布工程师**：负责 CI/CD 流水线建设与维护
- **后端开发工程师**：负责在 ThesisMiner 各模块（`backend/agents`、`backend/sessions`、`backend/orchestration`、`backend/ai`、`backend/analytics`、`backend/ml`、`backend/export`、`backend/knowledge`、`backend/validation`、`backend/routing`、`backend/integrity`、`backend/optimization`、`backend/nlp`、`backend/monitoring`、`backend/planning`、`backend/reasoning` 等）中实现可发布、可回滚的代码
- **SRE 与运维工程师**：负责执行发布、监控、回滚
- **QA 与测试工程师**：负责发布前测试验证
- **产品经理**：负责发布计划、发布说明、用户通知

文档目标是让任何一名工程师在阅读后能够：

1. 理解 ThesisMiner v8.0 发布流程
2. 知道如何提交符合规范的代码变更
3. 能够执行发布与回滚操作
4. 能够处理发布异常
5. 能够从历史案例中汲取经验

### 1.2 发布理念

ThesisMiner v8.0 发布理念：

- **小步快跑**：频繁发布小版本，降低单次发布风险
- **自动化优先**：构建、测试、部署全自动化，减少人为错误
- **可回滚**：任何发布必须可在 5 分钟内回滚
- **可观测**：发布过程全程监控，异常立即告警
- **渐进式**：金丝雀发布，逐步扩大流量
- **零停机**：滚动更新或蓝绿部署，发布不影响用户

### 1.3 设计原则

| 编号 | 原则 | 说明 |
|------|------|------|
| P1 | **可重复** | 同一代码版本可重复构建出相同产物 |
| P2 | **可追溯** | 每次发布可追溯到具体的代码 commit |
| P3 | **可回滚** | 任何发布可在 5 分钟内回滚 |
| P4 | **可观测** | 发布过程全程监控 |
| P5 | **自动化** | 构建、测试、部署全自动化 |
| P6 | **渐进式** | 金丝雀发布，逐步扩大 |
| P7 | **零停机** | 发布不影响用户 |

### 1.4 术语表

| 术语 | 英文 | 说明 |
|------|------|------|
| CI | Continuous Integration | 持续集成 |
| CD | Continuous Delivery/Deployment | 持续交付/部署 |
| SemVer | Semantic Versioning | 语义化版本 |
| Canary | Canary Release | 金丝雀发布 |
| Blue-Green | Blue-Green Deployment | 蓝绿部署 |
| Rolling | Rolling Update | 滚动更新 |
| Rollback | Rollback | 回滚 |
| Hotfix | Hotfix | 热修复 |
| Release | Release | 发布 |
| Changelog | Changelog | 变更日志 |
| Release Notes | Release Notes | 发布说明 |
| Feature Flag | Feature Flag | 特性开关 |
| Artifact | Artifact | 构建产物 |
| Pipeline | Pipeline | 流水线 |

---

## 2. 版本管理

### 2.1 语义化版本

ThesisMiner v8.0 采用语义化版本（Semantic Versioning 2.0.0）：

```
MAJOR.MINOR.PATCH
   |     |     |
   |     |     +-- 向后兼容的 bug 修复
   |     +-------- 向后兼容的新功能
   +-------------- 不兼容的 API 变更
```

**版本号规则**：

| 版本类型 | 触发条件 | 示例 |
|----------|----------|------|
| MAJOR | 不兼容的 API 变更 | 8.0.0 → 9.0.0 |
| MINOR | 向后兼容的新功能 | 8.0.0 → 8.1.0 |
| PATCH | 向后兼容的 bug 修复 | 8.0.0 → 8.0.1 |

**ThesisMiner v8.0 版本示例**：

- `8.0.0`：v8.0 首次发布
- `8.0.1`：v8.0 第一个 bug 修复
- `8.1.0`：新增功能（如新 Agent）
- `8.1.1`：v8.1 的 bug 修复
- `9.0.0`：不兼容变更（如 API 重构）

### 2.2 版本分支策略

ThesisMiner v8.0 采用 Git Flow 简化版：

```
master (主干，生产代码)
  |
  +-- develop (开发主干)
  |     |
  |     +-- feature/xxx (功能分支)
  |     +-- feature/yyy
  |
  +-- release/8.0.0 (发布分支)
  |     |
  |     +-- hotfix/8.0.1 (热修复分支)
  |
  +-- hotfix/8.0.2
```

**分支规范**：

| 分支类型 | 命名规范 | 来源 | 合并到 | 生命周期 |
|----------|----------|------|--------|----------|
| master | master | - | - | 永久 |
| develop | develop | master | master（发布时） | 永久 |
| feature | feature/xxx | develop | develop | 临时 |
| release | release/x.y.z | develop | master + develop | 临时 |
| hotfix | hotfix/x.y.z | master | master + develop | 临时 |

### 2.3 版本号管理

#### 2.3.1 版本号存储

版本号存储在 `pyproject.toml`：

```toml
[project]
name = "thesisminer"
version = "8.0.0"
description = "ThesisMiner - 智能论文导航系统"
```

#### 2.3.2 版本号自动化

使用 `bump2version` 自动管理版本号：

```ini
# .bumpversion.cfg
[bumpversion]
current_version = 8.0.0
commit = True
tag = True
tag_name = {new_version}
message = Bump version: {current_version} → {new_version}

[bumpversion:file:pyproject.toml]
search = version = "{current_version}"
replace = version = "{new_version}"

[bumpversion:file:backend/__init__.py]
search = __version__ = "{current_version}"
replace = __version__ = "{new_version}"

[bumpversion:file:docs/changelog/v8_changelog.md]
search = ## [Unreleased]
replace = ## [{new_version}] - {now:%Y-%m-%d}
```

**使用示例**：

```bash
# 升级 PATCH 版本
bump2version patch

# 升级 MINOR 版本
bump2version minor

# 升级 MAJOR 版本
bump2version major
```

### 2.4 预发布版本

预发布版本用于发布前测试：

| 后缀 | 说明 | 示例 |
|------|------|------|
| `-alpha.N` | 内部测试 | 8.1.0-alpha.1 |
| `-beta.N` | 外部测试 | 8.1.0-beta.1 |
| `-rc.N` | 发布候选 | 8.1.0-rc.1 |

**预发布流程**：

```
8.1.0-alpha.1 → 8.1.0-alpha.2 → ... → 8.1.0-beta.1 → ... → 8.1.0-rc.1 → 8.1.0
```

---

## 3. 发布策略

### 3.1 发布类型

| 类型 | 频率 | 风险 | 策略 |
|------|------|------|------|
| 常规发布 | 每周 | 低 | 滚动更新 |
| 功能发布 | 每月 | 中 | 金丝雀发布 |
| 大版本发布 | 每季度 | 高 | 蓝绿部署 |
| 紧急修复 | 随时 | 中 | 滚动更新 |
| 热修复 | 随时 | 高 | 蓝绿部署 |

### 3.2 蓝绿部署

蓝绿部署维护两套完全相同的环境，通过切换流量实现零停机发布。

```
+-------------------+        +-------------------+
| 蓝环境 (当前)     |        | 绿环境 (待发布)   |
| - v8.0.0          |        | - v8.1.0          |
| - 接收 100% 流量   |        | - 接收 0% 流量     |
+-------------------+        +-------------------+
         |                            |
         +--------- 负载均衡 ----------+
                     |
                     v
              [切换流量]
                     |
                     v
+-------------------+        +-------------------+
| 蓝环境 (备用)     |        | 绿环境 (当前)     |
| - v8.0.0          |        | - v8.1.0          |
| - 接收 0% 流量     |        | - 接收 100% 流量   |
+-------------------+        +-------------------+
```

**蓝绿部署流程**：

1. 在绿环境部署新版本
2. 对绿环境进行健康检查与测试
3. 切换流量到绿环境
4. 监控绿环境运行情况
5. 若异常，切回蓝环境
6. 若正常，蓝环境升级为新版本（作为备用）

**Kubernetes 蓝绿部署实现**：

```yaml
# deploy/k8s/thesisminer-blue.yml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: thesisminer-blue
  namespace: thesisminer
spec:
  replicas: 6
  selector:
    matchLabels:
      app: thesisminer
      color: blue
  template:
    metadata:
      labels:
        app: thesisminer
        color: blue
    spec:
      containers:
      - name: thesisminer
        image: thesisminer:8.0.0
        ports:
        - containerPort: 8000
---
apiVersion: v1
kind: Service
metadata:
  name: thesisminer
  namespace: thesisminer
spec:
  selector:
    app: thesisminer
    color: blue  # 当前指向蓝
  ports:
  - port: 80
    targetPort: 8000
```

**切换脚本**：

```bash
#!/bin/bash
# scripts/deploy/blue_green_switch.sh

set -euo pipefail

TARGET_COLOR="${1}"  # blue or green

echo "Switching traffic to ${TARGET_COLOR}"

# 1. 等待目标环境就绪
kubectl wait --for=condition=ready pod \
  -l app=thesisminer,color=${TARGET_COLOR} \
  -n thesisminer --timeout=300s

# 2. 切换 Service
kubectl patch service thesisminer -n thesisminer --type=json \
  -p="[{\"op\":\"replace\",\"path\":\"spec/selector/color\",\"value\":\"${TARGET_COLOR}\"}]"

# 3. 验证
sleep 10
curl -f http://thesisminer.example.com/health

echo "Switched to ${TARGET_COLOR}"
```

### 3.3 金丝雀发布

金丝雀发布逐步将流量从旧版本切换到新版本，便于发现问题及时回滚。

```
阶段 1：5% 流量到新版本
+-------------------+        +-------------------+
| 旧版本 v8.0.0     |        | 新版本 v8.1.0     |
| 95% 流量           |        | 5% 流量            |
+-------------------+        +-------------------+

阶段 2：25% 流量到新版本
+-------------------+        +-------------------+
| 旧版本 v8.0.0     |        | 新版本 v8.1.0     |
| 75% 流量           |        | 25% 流量           |
+-------------------+        +-------------------+

阶段 3：50% 流量到新版本
+-------------------+        +-------------------+
| 旧版本 v8.0.0     |        | 新版本 v8.1.0     |
| 50% 流量           |        | 50% 流量           |
+-------------------+        +-------------------+

阶段 4：100% 流量到新版本
+-------------------+        +-------------------+
| 旧版本 v8.0.0     |        | 新版本 v8.1.0     |
| 0% 流量            |        | 100% 流量          |
+-------------------+        +-------------------+
```

**Kubernetes 金丝雀发布实现**（使用 Istio）：

```yaml
# deploy/istio/virtualservice-canary.yml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: thesisminer
  namespace: thesisminer
spec:
  hosts:
  - thesisminer.example.com
  http:
  - route:
    - destination:
        host: thesisminer-stable
        port:
          number: 8000
      weight: 95  # 旧版本 95%
    - destination:
        host: thesisminer-canary
        port:
          number: 8000
      weight: 5  # 新版本 5%
    retries:
      attempts: 3
      perTryTimeout: 10s
```

**渐进式流量切换脚本**：

```bash
#!/bin/bash
# scripts/deploy/canary_progressive.sh

set -euo pipefail

STAGES=(5 25 50 100)
WAIT_MINUTES=15

for weight in "${STAGES[@]}"; do
    echo "Setting canary weight to ${weight}%"

    # 更新 VirtualService
    kubectl patch virtualservice thesisminer -n thesisminer --type=json \
      -p="[{\"op\":\"replace\",\"path\":\"spec/http/0/route/1/weight\",\"value\":${weight}},
           {\"op\":\"replace\",\"path\":\"spec/http/0/route/0/weight\",\"value\":$((100-weight))}]"

    echo "Waiting ${WAIT_MINUTES} minutes to monitor..."
    sleep $((WAIT_MINUTES * 60))

    # 检查指标
    ERROR_RATE=$(curl -s "http://prometheus:9090/api/v1/query" \
      --data-urlencode "query=thesisminer:http_error_rate:ratio5m{version=\"canary\"}" \
      | jq -r '.data.result[0].value[1]')

    echo "Canary error rate: ${ERROR_RATE}"

    # 阈值检查
    if (( $(echo "${ERROR_RATE} > 0.05" | bc -l) )); then
        echo "Error rate too high, rolling back!"
        kubectl patch virtualservice thesisminer -n thesisminer --type=json \
          -p="[{\"op\":\"replace\",\"path\":\"spec/http/0/route/0/weight\",\"value\":100},
               {\"op\":\"replace\",\"path\":\"spec/http/0/route/1/weight\",\"value\":0}]"
        exit 1
    fi
done

echo "Canary release completed successfully"
```

### 3.4 滚动更新

滚动更新逐步替换 Pod，是最常用的发布策略。

```yaml
# deploy/k8s/thesisminer.yml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: thesisminer
  namespace: thesisminer
spec:
  replicas: 6
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1  # 最多 1 个不可用
      maxSurge: 2  # 最多多 2 个
  template:
    spec:
      containers:
      - name: thesisminer
        image: thesisminer:8.1.0
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
        lifecycle:
          preStop:
            exec:
              command: ["sleep", "15"]  # 优雅关闭
```

### 3.5 A/B 测试

A/B 测试基于用户特征分流，对比不同版本效果。

```yaml
# deploy/istio/virtualservice-ab.yml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: thesisminer-ab
  namespace: thesisminer
spec:
  hosts:
  - thesisminer.example.com
  http:
  - match:
    - headers:
        x-user-type:
          exact: "premium"
    route:
    - destination:
        host: thesisminer-v8
  - route:
    - destination:
        host: thesisminer-v7
```

### 3.6 特性开关

特性开关（Feature Flag）允许在不重新部署的情况下启用/禁用功能。

```python
# backend/monitoring/feature_flag.py
from typing import Optional
import os
import redis


class FeatureFlag:
    """特性开关管理器。"""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def is_enabled(self, feature: str, user_id: Optional[str] = None) -> bool:
        """检查特性是否启用。"""
        # 全局开关
        global_flag = self.redis.get(f"feature:{feature}:global")
        if global_flag == b"false":
            return False

        # 用户白名单
        if user_id:
            user_flag = self.redis.sismember(
                f"feature:{feature}:users", user_id
            )
            if user_flag:
                return True

        # 百分比灰度
        percentage = self.redis.get(f"feature:{feature}:percentage")
        if percentage:
            percentage = int(percentage)
            if user_id:
                hash_value = hash(user_id) % 100
                return hash_value < percentage

        return global_flag == b"true"

    def enable(self, feature: str):
        """启用特性。"""
        self.redis.set(f"feature:{feature}:global", "true")

    def disable(self, feature: str):
        """禁用特性。"""
        self.redis.set(f"feature:{feature}:global", "false")

    def enable_for_user(self, feature: str, user_id: str):
        """为特定用户启用。"""
        self.redis.sadd(f"feature:{feature}:users", user_id)

    def set_percentage(self, feature: str, percentage: int):
        """设置灰度百分比。"""
        self.redis.set(f"feature:{feature}:percentage", percentage)


# 使用示例
feature_flag = FeatureFlag(redis_client)

if feature_flag.is_enabled("new_orchestrator", user_id="user-001"):
    # 使用新 Orchestrator
    pass
else:
    # 使用旧 Orchestrator
    pass
```

---

## 4. CI/CD 流水线

### 4.1 流水线架构

```
+----------+     +----------+     +----------+     +----------+
| 开发提交 | --> | CI 构建  | --> | CI 测试  | --> | 镜像构建 |
| (Push)   |     | (Build)  |     | (Test)   |     | (Image)  |
+----------+     +----------+     +----------+     +----------+
                                                        |
                                                        v
+----------+     +----------+     +----------+     +----------+
| 生产部署 | <-- | 金丝雀   | <-- | 预发部署 | <-- | 镜像推送 |
| (Prod)   |     | (Canary) |     | (Staging)|    | (Push)   |
+----------+     +----------+     +----------+     +----------+
```

### 4.2 持续集成（CI）

#### 4.2.1 CI 流程

1. **代码提交**：开发者 push 到 feature 分支
2. **触发 CI**：GitHub Actions / GitLab CI 触发
3. **代码检查**：lint、format、type check
4. **单元测试**：运行单元测试
5. **集成测试**：运行集成测试
6. **构建镜像**：构建 Docker 镜像
7. **安全扫描**：镜像漏洞扫描
8. **推送镜像**：推送到镜像仓库

#### 4.2.2 GitHub Actions 配置

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [develop, master, 'release/*']
  pull_request:
    branches: [develop]

env:
  PYTHON_VERSION: '3.11'
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:

  lint:
    name: Lint & Type Check
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4

    - name: Setup Python
      uses: actions/setup-python@v5
      with:
        python-version: ${{ env.PYTHON_VERSION }}

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements-dev.txt

    - name: Ruff lint
      run: ruff check backend/

    - name: Black format check
      run: black --check backend/

    - name: Mypy type check
      run: mypy backend/

  test:
    name: Unit & Integration Tests
    runs-on: ubuntu-latest
    needs: lint
    strategy:
      matrix:
        python-version: ['3.10', '3.11', '3.12']
    steps:
    - uses: actions/checkout@v4

    - name: Setup Python ${{ matrix.python-version }}
      uses: actions/setup-python@v5
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
        pip install -e .

    - name: Run unit tests
      run: |
        pytest tests/unit/ --cov=backend --cov-report=xml --cov-report=term

    - name: Run integration tests
      run: |
        pytest tests/integration/ -v

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml

  build:
    name: Build Docker Image
    runs-on: ubuntu-latest
    needs: test
    if: github.event_name == 'push'
    steps:
    - uses: actions/checkout@v4

    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3

    - name: Login to Registry
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
          type=ref,event=pr
          type=semver,pattern={{version}}
          type=sha,prefix=sha-

    - name: Build and push
      uses: docker/build-push-action@v5
      with:
        context: .
        push: true
        tags: ${{ steps.meta.outputs.tags }}
        labels: ${{ steps.meta.outputs.labels }}
        cache-from: type=gha
        cache-to: type=gha,mode=max

  security-scan:
    name: Security Scan
    runs-on: ubuntu-latest
    needs: build
    steps:
    - uses: actions/checkout@v4

    - name: Trivy vulnerability scan
      uses: aquasecurity/trivy-action@master
      with:
        image-ref: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:sha-${{ github.sha }}
        format: 'sarif'
        output: 'trivy-results.sarif'
        severity: 'CRITICAL,HIGH'

    - name: Upload Trivy results
      uses: github/codeql-action/upload-sarif@v3
      with:
        sarif_file: 'trivy-results.sarif'
```

### 4.3 持续交付（CD）

#### 4.3.1 CD 流程

1. **镜像就绪**：CI 构建的镜像通过测试
2. **部署预发**：自动部署到预发环境
3. **预发验证**：自动化测试 + 人工验证
4. **审批**：发布经理审批
5. **金丝雀发布**：5% → 25% → 50% → 100%
6. **生产验证**：监控指标验证
7. **完成**：发布完成，旧版本作为备用

#### 4.3.2 ArgoCD 配置

```yaml
# deploy/argocd/thesisminer.yml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: thesisminer
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/thesisminer/thesisminer-k8s
    targetRevision: HEAD
    path: deploy/k8s/overlays/production
  destination:
    server: https://kubernetes.default.svc
    namespace: thesisminer
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
    - PruneLast=true
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
```

### 4.4 自动化测试

#### 4.4.1 测试金字塔

```
                    /\
                   /UI\          少量，慢，昂贵
                  /----\
                 / E2E  \         少量，慢
                /--------\
               /Integration\      中等，中速
              /--------------\
             /  Unit Tests    \   大量，快，便宜
            /------------------\
```

#### 4.4.2 单元测试

```python
# tests/unit/agents/test_orchestrator.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.agents.orchestrator import Orchestrator


class TestOrchestrator:
    @pytest.fixture
    def orchestrator(self):
        return Orchestrator()

    @pytest.mark.asyncio
    async def test_dispatch_to_searcher(self, orchestrator):
        """测试分发到 Searcher agent。"""
        query = "机器学习在医学影像中的应用"
        session_id = "test-session"
        stage = "literature_mapping"

        result = await orchestrator.dispatch(query, session_id, stage)

        assert result is not None
        assert result.agent == "searcher"

    @pytest.mark.asyncio
    async def test_dispatch_with_invalid_stage(self, orchestrator):
        """测试无效阶段。"""
        with pytest.raises(ValueError):
            await orchestrator.dispatch("query", "session", "invalid_stage")
```

#### 4.4.3 集成测试

```python
# tests/integration/test_api.py
import pytest
from fastapi.testclient import TestClient
from backend.main import app


class TestThesisAPI:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_generate_thesis(self, client):
        """测试论文生成 API。"""
        response = client.post(
            "/api/v1/thesis/generate",
            json={
                "topic": "深度学习在自然语言处理中的应用",
                "session_id": "test-session"
            }
        )
        assert response.status_code in (200, 202)
        data = response.json()
        assert "thesis_id" in data

    def test_get_thesis(self, client):
        """测试获取论文。"""
        response = client.get("/api/v1/thesis/test-thesis-id")
        assert response.status_code == 200
```

#### 4.4.4 端到端测试

```python
# tests/e2e/test_full_flow.py
import pytest
import requests


class TestE2E:
    @pytest.mark.e2e
    def test_full_thesis_generation_flow(self):
        """测试完整论文生成流程。"""
        base_url = "http://thesisminer-staging:8000"

        # 1. 创建会话
        response = requests.post(
            f"{base_url}/api/v1/sessions",
            json={"user_id": "e2e-test-user"}
        )
        assert response.status_code == 200
        session_id = response.json()["session_id"]

        # 2. 生成论文
        response = requests.post(
            f"{base_url}/api/v1/thesis/generate",
            json={
                "topic": "机器学习在医学影像诊断中的应用",
                "session_id": session_id
            }
        )
        assert response.status_code == 202
        thesis_id = response.json()["thesis_id"]

        # 3. 等待生成完成
        for _ in range(60):
            response = requests.get(f"{base_url}/api/v1/thesis/{thesis_id}")
            status = response.json()["status"]
            if status == "completed":
                break
            elif status == "failed":
                pytest.fail("Thesis generation failed")
            import time
            time.sleep(10)

        # 4. 导出论文
        response = requests.post(
            f"{base_url}/api/v1/thesis/export",
            json={"thesis_id": thesis_id, "format": "pdf"}
        )
        assert response.status_code == 200
```

### 4.5 自动化部署

#### 4.5.1 部署脚本

```python
# scripts/deploy/deploy.py
import subprocess
import logging
import time
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Deployer:
    """自动化部署器。"""

    def __init__(self, image_tag: str, environment: str = "production"):
        self.image_tag = image_tag
        self.environment = environment

    def deploy(self) -> bool:
        """执行部署。"""
        logger.info(f"Deploying {self.image_tag} to {self.environment}")

        # 1. 更新镜像
        if not self._update_image():
            return False

        # 2. 等待滚动更新完成
        if not self._wait_for_rollout():
            return False

        # 3. 健康检查
        if not self._health_check():
            logger.error("Health check failed, rolling back")
            self._rollback()
            return False

        logger.info("Deployment completed successfully")
        return True

    def _update_image(self) -> bool:
        """更新镜像。"""
        result = subprocess.run([
            "kubectl", "set", "image",
            f"deployment/thesisminer",
            f"thesisminer=ghcr.io/thesisminer/thesisminer:{self.image_tag}",
            "-n", "thesisminer"
        ], capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Image update failed: {result.stderr}")
            return False

        return True

    def _wait_for_rollout(self, timeout: int = 300) -> bool:
        """等待滚动更新完成。"""
        result = subprocess.run([
            "kubectl", "rollout", "status",
            "deployment/thesisminer",
            "-n", "thesisminer",
            f"--timeout={timeout}s"
        ], capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Rollout failed: {result.stderr}")
            return False

        return True

    def _health_check(self, retries: int = 10) -> bool:
        """健康检查。"""
        for i in range(retries):
            try:
                result = subprocess.run([
                    "kubectl", "exec", "-n", "thesisminer",
                    "deployment/thesisminer", "--",
                    "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                    "http://localhost:8000/health"
                ], capture_output=True, text=True)

                if result.stdout == "200":
                    return True
            except Exception as e:
                logger.warning(f"Health check attempt {i+1} failed: {e}")

            time.sleep(5)

        return False

    def _rollback(self):
        """回滚。"""
        logger.warning("Rolling back deployment")
        subprocess.run([
            "kubectl", "rollout", "undo",
            "deployment/thesisminer", "-n", "thesisminer"
        ], check=False)


if __name__ == "__main__":
    import sys
    deployer = Deployer(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "production")
    exit(0 if deployer.deploy() else 1)
```

### 4.6 流水线配置

#### 4.6.1 多环境配置

```yaml
# deploy/k8s/overlays/production/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: thesisminer
resources:
- ../../base
patchesStrategicMerge:
- deployment-patch.yml
- configmap-patch.yml
configMapGenerator:
- name: thesisminer-config
  behavior: merge
  literals:
  - ENVIRONMENT=production
  - LOG_LEVEL=INFO
  - DEEPSEEK_MODEL=deepseek-coder
  - CACHE_TTL=3600
images:
- name: ghcr.io/thesisminer/thesisminer
  newTag: 8.0.0
```

---

## 5. 变更日志与发布说明

### 5.1 变更日志

ThesisMiner v8.0 遵循 Keep a Changelog 格式：

```markdown
# Changelog

All notable changes to ThesisMiner will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- 新增 D3.js v7 力导向谱系图
- 新增 Multi-Agent 架构（Orchestrator + 5 sub-agents）

### Changed
- 升级 FastAPI 到 0.110
- 重构会话管理模块

### Deprecated
- 废弃旧的论文生成 API v1

### Removed
- 移除 Python 3.8 支持

### Fixed
- 修复 DeepSeek API 超时问题
- 修复多会话上下文泄露问题

### Security
- 修复 SQL 注入漏洞 CVE-2026-1234

## [8.0.0] - 2026-06-20

### Added
- v8.0 首次发布
- Multi-Agent 架构
- 五阶段闭环导航
- 三段式 Prompt 缓存
- 多会话上下文隔离
```

### 5.2 发布说明

发布说明面向用户，用通俗语言描述变更：

```markdown
# ThesisMiner v8.0.0 发布说明

发布日期：2026-06-20

## 亮点

### 全新 Multi-Agent 架构
ThesisMiner v8.0 引入 Multi-Agent 架构，由 Orchestrator 协调 5 个专业 Agent：
- **Searcher**：文献检索
- **Reasoner**：方法推理
- **Critic**：质量评审
- **Mentor**：导师建议
- **Writer**：论文撰写

### 五阶段闭环导航
全新的五阶段闭环导航流程：
1. Topic Clarification（选题澄清）
2. Literature Mapping（文献映射）
3. Method Design（方法设计）
4. Writing（撰写）
5. Refinement（精修）

### 三段式 Prompt 缓存
通过 System Prompt、Session Context、User Query 三段缓存，DeepSeek API 成本降低 60%。

### 多会话上下文隔离
支持多用户并发，会话间数据严格隔离。

### D3.js v7 谱系图
全新力导向谱系图，可视化导师项目谱系。

## 新功能
- 新增 `/api/v2/thesis/generate` API
- 新增会话管理 API
- 新增谱系图可视化

## 改进
- 论文生成速度提升 40%
- API 响应延迟降低 30%
- 内存使用降低 25%

## Bug 修复
- 修复长文本生成截断问题
- 修复导出 PDF 格式错误
- 修复会话切换数据丢失

## 破坏性变更
- 移除 `/api/v1/thesis/generate` API（请迁移到 v2）
- 配置文件格式变更（参考迁移指南）

## 升级指南
1. 备份数据：`./scripts/backup.sh`
2. 拉取新版本：`docker pull thesisminer:8.0.0`
3. 执行迁移：`./scripts/migrate.sh`
4. 重启服务：`./scripts/restart.sh`

## 已知问题
- 谱系图在 Safari 上可能渲染缓慢
- 大量会话同时切换时可能有短暂延迟

## 反馈
如有问题，请联系 support@thesisminer.io
```

### 5.3 变更分类

| 分类 | 说明 | 示例 |
|------|------|------|
| Added | 新功能 | 新增 Agent |
| Changed | 变更 | 升级依赖 |
| Deprecated | 废弃 | 废弃旧 API |
| Removed | 移除 | 移除旧功能 |
| Fixed | 修复 | 修复 bug |
| Security | 安全 | 修复漏洞 |

---

## 6. 发布流程

### 6.1 发布计划

#### 6.1.1 发布日历

| 类型 | 频率 | 时间 | 负责人 |
|------|------|------|--------|
| 常规发布 | 每周二 | 02:00-04:00 UTC | 发布工程师 |
| 功能发布 | 每月 15 日 | 02:00-06:00 UTC | 发布经理 |
| 大版本发布 | 每季度 | 周末 | 发布经理 + CTO |
| 紧急修复 | 随时 | 随时 | OnCall |

#### 6.1.2 发布窗口

- **允许发布窗口**：周二至周四 02:00-06:00 UTC
- **禁止发布窗口**：周五 12:00 至周一 09:00（避免周末故障）
- **例外**：紧急修复、安全修复

### 6.2 发布前准备

#### 6.2.1 发布前检查清单

- [ ] 所有 PR 已合并
- [ ] CI 全部通过
- [ ] 单元测试覆盖率 ≥ 80%
- [ ] 集成测试全部通过
- [ ] E2E 测试全部通过
- [ ] 安全扫描无严重漏洞
- [ ] 性能测试达标
- [ ] 变更日志已更新
- [ ] 发布说明已撰写
- [ ] 数据库迁移脚本已准备
- [ ] 回滚方案已准备
- [ ] 监控告警已配置
- [ ] 通知已发送

#### 6.2.2 发布前测试

```bash
#!/bin/bash
# scripts/release/pre_release_test.sh

set -euo pipefail

VERSION="${1}"
ENVIRONMENT="staging"

echo "Running pre-release tests for v${VERSION}"

# 1. 部署到预发
./scripts/deploy/deploy.sh "${VERSION}" "${ENVIRONMENT}"

# 2. 等待部署完成
kubectl rollout status deployment/thesisminer -n thesisminer-staging

# 3. 运行冒烟测试
pytest tests/smoke/ -v --tb=short

# 4. 运行 E2E 测试
pytest tests/e2e/ -v --tb=short

# 5. 性能测试
./scripts/test/performance_test.sh

# 6. 安全测试
./scripts/test/security_scan.sh

echo "Pre-release tests passed"
```

### 6.3 发布执行

#### 6.3.1 发布步骤

```
[发布开始] --> [备份] --> [部署] --> [验证] --> [监控] --> [发布完成]
    |            |          |          |          |          |
    v            v          v          v          v          v
  通知团队    备份数据   金丝雀     业务验证   观察 30m   通知用户
```

#### 6.3.2 发布脚本

```bash
#!/bin/bash
# scripts/release/release.sh

set -euo pipefail

VERSION="${1}"
ENVIRONMENT="${2:-production}"

echo "=========================================="
echo "ThesisMiner v${VERSION} Release"
echo "Environment: ${ENVIRONMENT}"
echo "Time: $(date)"
echo "Operator: $(whoami)"
echo "=========================================="

# 1. 发布前检查
echo "[1/8] Pre-release checks..."
./scripts/release/pre_release_check.sh "${VERSION}"

# 2. 备份
echo "[2/8] Backup..."
./scripts/backup/sqlite_full_backup.sh

# 3. 通知团队
echo "[3/8] Notify team..."
./scripts/notify/slack_notify.sh "release_started" "${VERSION}"

# 4. 部署
echo "[4/8] Deploy..."
if [ "${ENVIRONMENT}" = "production" ]; then
    ./scripts/deploy/canary_deploy.sh "${VERSION}"
else
    ./scripts/deploy/deploy.sh "${VERSION}" "${ENVIRONMENT}"
fi

# 5. 验证
echo "[5/8] Verify..."
./scripts/verify/post_deploy_verify.sh

# 6. 监控
echo "[6/8] Monitor (30 minutes)..."
./scripts/monitor/release_monitor.sh 30

# 7. 通知用户
echo "[7/8] Notify users..."
./scripts/notify/user_notify.sh "${VERSION}"

# 8. 发布完成
echo "[8/8] Release completed"
./scripts/notify/slack_notify.sh "release_completed" "${VERSION}"

echo "=========================================="
echo "Release v${VERSION} completed successfully"
echo "=========================================="
```

### 6.4 发布后验证

```python
# scripts/verify/post_deploy_verify.py
import requests
import time
import logging
from typing import List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PostDeployVerifier:
    """发布后验证器。"""

    def __init__(self, base_url: str):
        self.base_url = base_url

    def verify_all(self) -> bool:
        """执行全部验证。"""
        checks = [
            ("健康检查", self._check_health),
            ("API 可用性", self._check_api),
            ("核心业务流程", self._check_business_flow),
            ("监控指标", self._check_metrics),
            ("日志正常", self._check_logs),
        ]

        all_passed = True
        for name, check in checks:
            try:
                if check():
                    logger.info(f"✓ {name} 通过")
                else:
                    logger.error(f"✗ {name} 失败")
                    all_passed = False
            except Exception as e:
                logger.error(f"✗ {name} 异常: {e}")
                all_passed = False

        return all_passed

    def _check_health(self) -> bool:
        response = requests.get(f"{self.base_url}/health", timeout=10)
        return response.status_code == 200

    def _check_api(self) -> bool:
        endpoints = [
            "/api/v1/health",
            "/api/v1/sessions",
            "/api/v1/thesis",
        ]
        for endpoint in endpoints:
            response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
            if response.status_code not in (200, 401, 404):
                return False
        return True

    def _check_business_flow(self) -> bool:
        # 创建会话
        response = requests.post(
            f"{self.base_url}/api/v1/sessions",
            json={"user_id": "post-deploy-test"},
            timeout=30
        )
        if response.status_code != 200:
            return False

        # 生成论文（异步）
        session_id = response.json()["session_id"]
        response = requests.post(
            f"{self.base_url}/api/v1/thesis/generate",
            json={
                "topic": "测试论文",
                "session_id": session_id
            },
            timeout=30
        )
        return response.status_code in (200, 202)

    def _check_metrics(self) -> bool:
        # 检查 Prometheus 指标
        response = requests.get(
            "http://prometheus:9090/api/v1/query",
            params={"query": "up{job='thesisminer-app'}"},
            timeout=10
        )
        data = response.json()
        if not data["data"]["result"]:
            return False
        return all(r["value"][1] == "1" for r in data["data"]["result"])

    def _check_logs(self) -> bool:
        # 检查最近 5 分钟无 ERROR 日志
        response = requests.get(
            "http://elasticsearch:9200/thesisminer-logs-*/_count",
            json={
                "query": {
                    "bool": {
                        "must": [
                            {"match": {"level": "ERROR"}},
                            {"range": {"@timestamp": {"gte": "now-5m"}}}
                        ]
                    }
                }
            },
            timeout=10
        )
        count = response.json()["count"]
        return count < 10  # 允许少量错误


if __name__ == "__main__":
    import sys
    verifier = PostDeployVerifier(sys.argv[1])
    exit(0 if verifier.verify_all() else 1)
```

### 6.5 发布检查清单

#### 6.5.1 发布前检查清单

- [ ] 版本号已更新
- [ ] 变更日志已更新
- [ ] 发布说明已撰写
- [ ] CI 全部通过
- [ ] 测试全部通过
- [ ] 安全扫描通过
- [ ] 性能测试达标
- [ ] 数据库迁移已测试
- [ ] 回滚方案已准备
- [ ] 监控告警已配置
- [ ] 团队已通知
- [ ] 用户已通知（如需要）

#### 6.5.2 发布中检查清单

- [ ] 备份已完成
- [ ] 部署已执行
- [ ] 健康检查通过
- [ ] 业务验证通过
- [ ] 监控指标正常
- [ ] 日志无异常

#### 6.5.3 发布后检查清单

- [ ] 监控 30 分钟无异常
- [ ] 用户反馈正常
- [ ] 旧版本已下线
- [ ] 发布报告已撰写
- [ ] Postmortem（如有问题）

### 6.6 发布审批

#### 6.6.1 审批级别

| 发布类型 | 审批人 | 审批方式 |
|----------|--------|----------|
| 常规发布 | 发布工程师 | 自动 |
| 功能发布 | 发布经理 | 邮件 |
| 大版本发布 | CTO | 会议 |
| 紧急修复 | OnCall + 发布经理 | 电话 |
| 热修复 | CTO | 电话 |

#### 6.6.2 审批流程

```
[发布申请] --> [审批人审核] --> [批准/拒绝] --> [执行/中止]
    |              |                |              |
    v              v                v              v
  提交申请      检查清单          决策          执行发布
```

### 6.7 发布通知

#### 6.7.1 内部通知

```bash
# Slack 通知
./scripts/notify/slack_notify.sh "release_started" "8.0.0"

# 邮件通知
./scripts/notify/email_notify.sh "release_started" "8.0.0"
```

#### 6.7.2 用户通知

- **站内公告**：发布前 24 小时
- **邮件通知**：大版本发布前 7 天
- **状态页**：发布期间更新状态

---

## 7. 回滚策略

### 7.1 回滚分类

| 类型 | 触发条件 | 速度 | 方式 |
|------|----------|------|------|
| 自动回滚 | 监控指标异常 | 秒级 | 自动 |
| 手动回滚 | 人工判断异常 | 分钟级 | 脚本 |
| 紧急回滚 | 严重故障 | 分钟级 | 脚本 |
| 数据库回滚 | 数据问题 | 小时级 | 备份恢复 |

### 7.2 自动回滚

#### 7.2.1 自动回滚条件

- 错误率 > 5%（5 分钟）
- P99 延迟 > 10s（5 分钟）
- 健康检查失败 > 3 次
- CPU 使用率 > 95%（5 分钟）
- 内存使用率 > 95%（5 分钟）

#### 7.2.2 自动回滚实现

```yaml
# deploy/prometheus/rules/auto-rollback.yml
groups:
- name: auto-rollback
  rules:

  - alert: AutoRollbackTriggered
    expr: |
      thesisminer:http_error_rate:ratio5m > 0.05
      and
      thesisminer:deployment_new:bool == 1
    for: 2m
    labels:
      severity: critical
      action: auto_rollback
    annotations:
      summary: "Auto rollback triggered due to high error rate"

  - alert: AutoRollbackHighLatency
    expr: |
      thesisminer:p99_latency:5m > 10
      and
      thesisminer:deployment_new:bool == 1
    for: 5m
    labels:
      severity: critical
      action: auto_rollback
    annotations:
      summary: "Auto rollback triggered due to high latency"
```

```python
# scripts/rollback/auto_rollback.py
import subprocess
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AutoRollback:
    """自动回滚器。"""

    def __init__(self, deployment: str, namespace: str):
        self.deployment = deployment
        self.namespace = namespace

    def should_rollback(self) -> bool:
        """检查是否需要回滚。"""
        # 检查错误率
        error_rate = self._query_prometheus(
            'thesisminer:http_error_rate:ratio5m'
        )
        if error_rate > 0.05:
            logger.warning(f"Error rate too high: {error_rate}")
            return True

        # 检查延迟
        latency = self._query_prometheus(
            'thesisminer:p99_latency:5m'
        )
        if latency > 10:
            logger.warning(f"Latency too high: {latency}s")
            return True

        return False

    def rollback(self) -> bool:
        """执行回滚。"""
        logger.warning("Initiating auto rollback...")

        result = subprocess.run([
            "kubectl", "rollout", "undo",
            f"deployment/{self.deployment}",
            "-n", self.namespace
        ], capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Rollback failed: {result.stderr}")
            return False

        # 等待回滚完成
        subprocess.run([
            "kubectl", "rollout", "status",
            f"deployment/{self.deployment}",
            "-n", self.namespace,
            "--timeout=300s"
        ], check=True)

        logger.info("Rollback completed")
        self._notify("Auto rollback completed")
        return True

    def _query_prometheus(self, query: str) -> float:
        """查询 Prometheus。"""
        import requests
        response = requests.get(
            "http://prometheus:9090/api/v1/query",
            params={"query": query},
            timeout=10
        )
        data = response.json()
        if data["data"]["result"]:
            return float(data["data"]["result"][0]["value"][1])
        return 0.0

    def _notify(self, message: str):
        """发送通知。"""
        # 发送 Slack 通知
        pass


if __name__ == "__main__":
    rollback = AutoRollback("thesisminer", "thesisminer")
    if rollback.should_rollback():
        rollback.rollback()
```

### 7.3 手动回滚

```bash
#!/bin/bash
# scripts/rollback/manual_rollback.sh

set -euo pipefail

DEPLOYMENT="thesisminer"
NAMESPACE="thesisminer"

echo "Manual rollback initiated by $(whoami) at $(date)"

# 1. 查看发布历史
echo "Revision history:"
kubectl rollout history deployment/${DEPLOYMENT} -n ${NAMESPACE}

# 2. 回滚到上一版本
echo "Rolling back to previous revision..."
kubectl rollout undo deployment/${DEPLOYMENT} -n ${NAMESPACE}

# 3. 等待回滚完成
echo "Waiting for rollback to complete..."
kubectl rollout status deployment/${DEPLOYMENT} -n ${NAMESPACE} --timeout=300s

# 4. 验证
echo "Verifying..."
sleep 10
curl -f http://thesisminer.example.com/health

echo "Rollback completed successfully"
```

### 7.4 紧急回滚

```bash
#!/bin/bash
# scripts/rollback/emergency_rollback.sh

set -euo pipefail

VERSION="${1:-previous}"

echo "=========================================="
echo "EMERGENCY ROLLBACK"
echo "Time: $(date)"
echo "Operator: $(whoami)"
echo "Target: ${VERSION}"
echo "=========================================="

# 1. 立即回滚（不等待）
if [ "${VERSION}" = "previous" ]; then
    kubectl rollout undo deployment/thesisminer -n thesisminer
else
    kubectl set image deployment/thesisminer \
        thesisminer=ghcr.io/thesisminer/thesisminer:${VERSION} \
        -n thesisminer
fi

# 2. 强制重启
kubectl rollout restart deployment/thesisminer -n thesisminer

# 3. 等待（最多 5 分钟）
kubectl rollout status deployment/thesisminer -n thesisminer --timeout=300s || true

# 4. 通知
./scripts/notify/pagerduty_alert.sh "Emergency rollback executed"

# 5. 验证
sleep 30
curl -f http://thesisminer.example.com/health || echo "WARNING: Health check failed"

echo "Emergency rollback completed"
```

### 7.5 数据库回滚

数据库回滚需要特别小心，避免数据丢失。

#### 7.5.1 数据库迁移回滚

```python
# scripts/migrate/db_rollback.py
import sqlite3
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseRollback:
    """数据库回滚器。"""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)

    def rollback_migration(self, migration_id: str) -> bool:
        """回滚指定迁移。"""
        conn = sqlite3.connect(str(self.db_path))

        try:
            # 1. 检查迁移记录
            cursor = conn.execute(
                "SELECT * FROM schema_migrations WHERE id = ?",
                (migration_id,)
            )
            migration = cursor.fetchone()
            if not migration:
                logger.error(f"Migration {migration_id} not found")
                return False

            # 2. 备份当前数据库
            self._backup()

            # 3. 执行回滚脚本
            rollback_sql = self._get_rollback_sql(migration_id)
            conn.executescript(rollback_sql)

            # 4. 删除迁移记录
            conn.execute(
                "DELETE FROM schema_migrations WHERE id = ?",
                (migration_id,)
            )

            conn.commit()
            logger.info(f"Migration {migration_id} rolled back successfully")
            return True

        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def _backup(self):
        """备份数据库。"""
        import shutil
        backup_path = self.db_path.with_suffix(
            f".db.bak.{int(time.time())}"
        )
        shutil.copy2(self.db_path, backup_path)
        logger.info(f"Database backed up to {backup_path}")

    def _get_rollback_sql(self, migration_id: str) -> str:
        """获取回滚 SQL。"""
        rollback_file = Path(f"migrations/{migration_id}_rollback.sql")
        if not rollback_file.exists():
            raise FileNotFoundError(f"Rollback file not found: {rollback_file}")
        return rollback_file.read_text()
```

---

## 8. 发布后监控

### 8.1 监控指标

发布后需重点监控：

| 指标 | 正常范围 | 告警阈值 |
|------|----------|----------|
| 错误率 | < 0.1% | > 1% |
| P99 延迟 | < 2s | > 5s |
| QPS | 与平时一致 | 下降 > 30% |
| CPU 使用率 | < 70% | > 90% |
| 内存使用率 | < 80% | > 95% |
| 数据库连接数 | < 50 | > 100 |
| 缓存命中率 | > 80% | < 50% |

### 8.2 异常响应

#### 8.2.1 异常分级

| 级别 | 现象 | 响应 |
|------|------|------|
| P0 | 服务不可用 | 立即回滚 |
| P1 | 错误率 > 5% | 评估后回滚 |
| P2 | 延迟突增 | 观察 5 分钟 |
| P3 | 部分功能异常 | 评估影响 |

#### 8.2.2 响应流程

```
[异常检测] --> [分级] --> [决策] --> [执行] --> [验证] --> [复盘]
    |            |          |          |          |          |
    v            v          v          v          v          v
  监控告警     评估影响   回滚/观察   执行决策   验证恢复   Postmortem
```

### 8.3 发布复盘

#### 8.3.1 复盘模板

```markdown
# 发布复盘：v8.0.0

## 发布信息
- **版本**：v8.0.0
- **发布时间**：2026-06-20 02:00-04:00 UTC
- **发布人员**：[列表]
- **发布结果**：成功/失败/部分成功

## 发布过程
| 阶段 | 计划时间 | 实际时间 | 偏差 | 原因 |
|------|----------|----------|------|------|
| 备份 | 02:00-02:10 | 02:00-02:08 | -2m | - |
| 部署 | 02:10-02:30 | 02:10-02:35 | +5m | 镜像拉取慢 |
| 验证 | 02:30-02:40 | 02:35-02:45 | +5m | - |
| 监控 | 02:40-03:10 | 02:45-03:15 | +5m | - |

## 问题记录
| 问题 | 影响 | 原因 | 改进 |
|------|------|------|------|
| 镜像拉取慢 | 部署延迟 5 分钟 | 镜像仓库带宽不足 | 预拉取镜像 |

## 关键指标
| 指标 | 发布前 | 发布后 | 变化 |
|------|--------|--------|------|
| 错误率 | 0.05% | 0.08% | +60% |
| P99 延迟 | 1.2s | 1.1s | -8% |
| QPS | 120 | 125 | +4% |

## 结论
发布成功，指标正常。需优化镜像拉取速度。

## 行动项
| 行动项 | 负责人 | 截止日期 |
|--------|--------|----------|
| 预拉取镜像 | 张三 | 2026-06-27 |
```

---

## 9. 发布案例研究

### 9.1 案例一：v8.0.0 大版本发布

#### 9.1.1 背景

- **版本**：v8.0.0
- **变更**：Multi-Agent 架构、五阶段闭环、三段式缓存
- **风险**：高（架构级变更）

#### 9.1.2 发布过程

1. **发布前 1 周**：完成所有测试，性能达标
2. **发布前 1 天**：用户通知，团队确认
3. **发布日 02:00**：开始发布
4. **发布日 02:10**：备份完成
5. **发布日 02:30**：蓝绿部署，绿环境就绪
6. **发布日 02:35**：切换流量到绿环境
7. **发布日 02:40**：业务验证通过
8. **发布日 03:10**：监控 30 分钟无异常
9. **发布日 03:15**：发布完成

#### 9.1.3 结果

发布成功，关键指标：
- 错误率：0.05% → 0.08%（轻微上升，可接受）
- P99 延迟：1.5s → 1.1s（改善）
- QPS：120 → 125（正常波动）
- 缓存命中率：60% → 85%（大幅提升）

#### 9.1.4 经验

1. 充分的发布前测试是关键
2. 蓝绿部署确保零停机
3. 30 分钟监控窗口足够发现问题

### 9.2 案例二：紧急热修复

#### 9.2.1 背景

- **问题**：DeepSeek API 限流导致论文生成失败
- **修复**：增加多 API Key 轮换
- **紧急程度**：高（影响核心功能）

#### 9.2.2 发布过程

1. **10:00**：发现问题，错误率突增到 15%
2. **10:05**：定位原因：DeepSeek 限流
3. **10:10**：开发修复方案
4. **10:30**：代码完成，CI 通过
5. **10:35**：紧急发布审批（CTO 电话审批）
6. **10:40**：开始发布
7. **10:50**：发布完成
8. **11:00**：错误率恢复正常

#### 9.2.3 结果

热修复成功，从发现问题到修复完成耗时 1 小时。

#### 9.2.4 经验

1. 紧急修复流程需简化审批
2. 多 API Key 是必要的容灾措施
3. 监控告警及时发现问题

### 9.3 案例三：金丝雀发布失败

#### 9.3.1 背景

- **版本**：v8.1.0
- **变更**：新增 Reasoner Agent 优化
- **策略**：金丝雀发布

#### 9.3.2 发布过程

1. **02:00**：开始金丝雀发布，5% 流量
2. **02:15**：监控 15 分钟，指标正常
3. **02:20**：扩大到 25% 流量
4. **02:25**：错误率突增到 8%
5. **02:26**：自动回滚触发
6. **02:30**：回滚完成，错误率恢复

#### 9.3.3 根因

新 Reasoner Agent 在高并发下有内存泄漏，25% 流量时触发 OOM。

#### 9.3.4 经验

1. 金丝雀发布有效防止了全量故障
2. 自动回滚机制有效
3. 需要加强高并发压测

### 9.4 案例四：数据库迁移发布

#### 9.4.1 背景

- **变更**：数据库 schema 变更（新增表、修改字段）
- **风险**：高（涉及数据迁移）

#### 9.4.2 发布过程

1. **发布前 1 周**：在预发环境测试迁移
2. **发布前 1 天**：备份生产数据库
3. **发布日 02:00**：开始迁移
4. **发布日 02:30**：迁移完成
5. **发布日 02:35**：数据校验
6. **发布日 02:45**：应用部署
7. **发布日 03:00**：验证完成

#### 9.4.3 结果

迁移成功，无数据丢失。

#### 9.4.4 经验

1. 数据库迁移必须充分测试
2. 迁移前必须备份
3. 迁移后必须数据校验
4. 准备回滚脚本

### 9.5 经验教训

| 编号 | 教训 | 改进 |
|------|------|------|
| L1 | 充分测试是关键 | 发布前完整测试 |
| L2 | 金丝雀发布有效 | 所有功能发布用金丝雀 |
| L3 | 自动回滚必要 | 配置自动回滚 |
| L4 | 数据库迁移需谨慎 | 充分测试 + 备份 |
| L5 | 紧急流程需简化 | 简化紧急审批 |
| L6 | 监控是保障 | 发布后密切监控 |
| L7 | 复盘是改进 | 每次发布后复盘 |

---

## 10. 最佳实践

### 10.1 发布最佳实践

1. **小步快跑**：频繁发布小版本
2. **自动化**：构建、测试、部署全自动化
3. **可回滚**：任何发布可回滚
4. **金丝雀**：渐进式发布
5. **监控**：发布后密切监控
6. **文档**：变更日志、发布说明
7. **沟通**：及时通知团队与用户
8. **复盘**：每次发布后复盘

### 10.2 回滚最佳实践

1. **快速回滚**：5 分钟内可回滚
2. **自动回滚**：监控触发自动回滚
3. **数据备份**：回滚前备份
4. **回滚验证**：回滚后验证
5. **回滚演练**：定期演练

### 10.3 CI/CD 最佳实践

1. **流水线即代码**：CI/CD 配置版本化
2. **快速反馈**：CI 在 10 分钟内完成
3. **并行化**：测试并行执行
4. **缓存**：依赖、镜像缓存
5. **安全扫描**：每次构建扫描
6. **不可变产物**：镜像不可变

---

## 11. 附录

### 11.1 配置示例

#### 11.1.1 Dockerfile

```dockerfile
# Dockerfile
FROM python:3.11-slim as builder

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# 多阶段构建
FROM python:3.11-slim

WORKDIR /app

# 复制依赖
COPY --from=builder /root/.local /root/.local

# 复制代码
COPY . .

# 安装应用
RUN pip install --no-cache-dir -e .

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 运行
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 11.1.2 GitHub Actions 完整配置

```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    tags:
    - 'v*'

jobs:

  release:
    name: Release
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4

    - name: Setup Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-dev.txt

    - name: Run tests
      run: pytest tests/ -v

    - name: Build Docker image
      run: docker build -t thesisminer:${{ github.ref_name }} .

    - name: Push to registry
      run: |
        echo ${{ secrets.REGISTRY_PASSWORD }} | docker login -u ${{ secrets.REGISTRY_USER }} --password-stdin
        docker tag thesisminer:${{ github.ref_name }} ghcr.io/thesisminer/thesisminer:${{ github.ref_name }}
        docker push ghcr.io/thesisminer/thesisminer:${{ github.ref_name }}

    - name: Deploy to staging
      run: |
        ./scripts/deploy/deploy.sh ${{ github.ref_name }} staging

    - name: Run E2E tests
      run: pytest tests/e2e/ -v

    - name: Notify team
      uses: slackapi/slack-github-action@v1
      with:
        slack-message: "Release ${{ github.ref_name }} ready for production"
```

### 11.2 模板

#### 11.2.1 发布申请模板

```markdown
# 发布申请

## 基本信息
- **版本号**：v8.1.0
- **发布类型**：功能发布
- **计划时间**：2026-07-15 02:00 UTC
- **申请人**：张三
- **审批人**：李四（发布经理）

## 变更内容
- 新增 Reasoner Agent 优化
- 修复 DeepSeek API 超时问题
- 升级 FastAPI 到 0.111

## 风险评估
- **风险等级**：中
- **影响范围**：论文生成功能
- **回滚方案**：蓝绿部署，可秒级回滚

## 测试情况
- [x] 单元测试通过
- [x] 集成测试通过
- [x] E2E 测试通过
- [x] 性能测试达标
- [x] 安全扫描通过

## 审批
- [ ] 发布经理审批
- [ ] CTO 审批（大版本）
```

#### 11.2.2 发布报告模板

```markdown
# 发布报告

## 发布信息
- **版本**：v8.1.0
- **发布时间**：2026-07-15 02:00-03:00 UTC
- **发布人员**：张三、李四
- **发布结果**：成功

## 发布过程
| 阶段 | 时间 | 状态 |
|------|------|------|
| 备份 | 02:00-02:05 | 成功 |
| 部署 | 02:05-02:30 | 成功 |
| 验证 | 02:30-02:40 | 成功 |
| 监控 | 02:40-03:00 | 正常 |

## 关键指标
| 指标 | 发布前 | 发布后 |
|------|--------|--------|
| 错误率 | 0.05% | 0.06% |
| P99 延迟 | 1.2s | 1.0s |

## 问题
无

## 结论
发布成功
```

### 11.3 检查清单

#### 11.3.1 发布前检查清单

- [ ] 版本号已更新
- [ ] 变更日志已更新
- [ ] 发布说明已撰写
- [ ] CI 全部通过
- [ ] 单元测试通过
- [ ] 集成测试通过
- [ ] E2E 测试通过
- [ ] 性能测试达标
- [ ] 安全扫描通过
- [ ] 数据库迁移已测试
- [ ] 回滚方案已准备
- [ ] 监控告警已配置
- [ ] 团队已通知
- [ ] 用户已通知

#### 11.3.2 发布后检查清单

- [ ] 健康检查通过
- [ ] 业务验证通过
- [ ] 监控指标正常
- [ ] 日志无异常
- [ ] 30 分钟监控完成
- [ ] 发布报告已撰写

### 11.4 变更记录

| 版本 | 日期 | 变更 | 作者 |
|------|------|------|------|
| v1.0 | 2026-01-15 | 初始版本 | Release Team |
| v2.0 | 2026-03-20 | 增加金丝雀发布 | Release Team |
| v3.0 | 2026-05-10 | 增加自动回滚 | SRE Team |
| v8.0 | 2026-06-20 | 适配 v8.0 架构 | Release Team |

---

## 12. FAQ

### Q1: 发布频率应该多高？

**A**: 建议每周常规发布，每月功能发布，每季度大版本。频繁小步发布比偶尔大版本发布风险更低。

### Q2: 金丝雀发布的流量比例怎么定？

**A**: 建议 5% → 25% → 50% → 100%，每阶段观察 15-30 分钟。关键业务可更保守：1% → 5% → 25% → 50% → 100%。

### Q3: 什么时候应该回滚？

**A**: 1) 错误率 > 5%；2) P99 延迟 > 10s；3) 核心功能不可用；4) 数据丢失风险。宁可回滚也不要"等等看"。

### Q4: 数据库迁移怎么发布？

**A**: 1) 预发环境充分测试；2) 生产备份；3) 低峰期执行；4) 数据校验；5) 准备回滚脚本。复杂迁移分多次执行。

### Q5: 紧急修复怎么快速发布？

**A**: 1) 简化审批（电话审批）；2) 跳过部分测试（仅核心测试）；3) 直接部署；4) 发布后补测试。但必须记录并复盘。

### Q6: 蓝绿部署和金丝雀发布怎么选？

**A**: 蓝绿部署适合大版本发布（零停机切换），金丝雀适合常规发布（渐进式验证）。ThesisMiner v8.0 大版本用蓝绿，常规用金丝雀。

### Q7: 特性开关怎么用？

**A**: 用于：1) 未完成功能提前合并；2) 灰度发布；3) 紧急禁用功能。但不要滥用，已验证的功能应及时移除开关。

### Q8: 发布后监控多久？

**A**: 至少 30 分钟。大版本发布监控 2-4 小时。关键指标：错误率、延迟、QPS、资源使用。

### Q9: 如何避免"周五发布"陷阱？

**A**: 1) 禁止周五 12:00 后发布；2) 紧急修复除外；3) 自动化检查发布窗口；4) 文化建设。

### Q10: 发布失败怎么办？

**A**: 1) 立即回滚；2) 通知团队；3) 定位根因；4) 修复后重新发布；5) 复盘并改进流程。

---

## 13. 结语

发布是软件交付的最后一公里，也是风险最高的一环。ThesisMiner v8.0 通过完善的版本管理、CI/CD 流水线、渐进式发布策略、自动回滚机制，构建了可靠的发布体系。随着团队成熟度提升，发布流程应持续优化，目标是让发布变得"无聊"——可重复、可预测、无惊喜。

**核心要点回顾**：

1. **小步快跑**：频繁发布小版本
2. **自动化**：构建、测试、部署全自动化
3. **可回滚**：任何发布可回滚
4. **金丝雀**：渐进式发布
5. **监控**：发布后密切监控
6. **复盘**：每次发布后复盘

---

**文档结束**

> 本文档由 ThesisMiner Release Engineering Team 维护，最后更新于 2026-06-20。
> 如有疑问或建议，请联系 `release@thesisminer.io` 或在内部 Wiki 提交 Issue。
