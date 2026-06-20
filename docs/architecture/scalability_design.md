# ThesisMiner v8.0 可扩展性设计文档

> **版本**: v8.0.0  
> **最后更新**: 2026-06-20  
> **文档状态**: 正式发布  
> **维护者**: ThesisMiner Architecture Team

---

## 目录

1. [文档概述](#1-文档概述)
2. [可扩展性架构总览](#2-可扩展性架构总览)
3. [水平扩展 (Horizontal Scaling)](#3-水平扩展-horizontal-scaling)
4. [垂直扩展 (Vertical Scaling)](#4-垂直扩展-vertical-scaling)
5. [混合扩展策略](#5-混合扩展策略)
6. [无状态服务设计](#6-无状态服务设计)
7. [数据库分片与扩展](#7-数据库分片与扩展)
8. [缓存扩展策略](#8-缓存扩展策略)
9. [微服务架构演进](#9-微服务架构演进)
10. [性能瓶颈识别](#10-性能瓶颈识别)
11. [容量规划](#11-容量规划)
12. [弹性伸缩机制](#12-弹性伸缩机制)
13. [异步处理扩展](#13-异步处理扩展)
14. [数据分区策略](#14-数据分区策略)
15. [CDN 与边缘缓存](#15-cdn-与边缘缓存)
16. [连接池管理](#16-连接池管理)
17. [请求队列与背压](#17-请求队列与背压)
18. [扩展性测试与基准](#18-扩展性测试与基准)
19. [扩展性反模式](#19-扩展性反模式)
20. [附录](#20-附录)

---

## 1. 文档概述

### 1.1 文档目的

本文档阐述 ThesisMiner v8.0 系统的可扩展性（Scalability）设计原则、策略与实现方案。可扩展性是系统能够处理不断增长的负载、数据量和用户规模的核心能力。本文档为开发、运维和架构团队提供统一的扩展性设计参考，确保系统在不同负载水平下均能保持良好的性能与可用性。

### 1.2 文档范围

本文档覆盖以下内容：

- 水平扩展与垂直扩展策略
- 无状态服务设计原则
- 数据库分片与读写分离
- 多级缓存扩展
- 微服务架构演进路径
- 性能瓶颈识别方法论
- 容量规划与弹性伸缩
- 异步处理与消息队列扩展
- 扩展性测试与基准

### 1.3 术语表

| 术语 | 英文 | 说明 |
|------|------|------|
| 水平扩展 | Horizontal Scaling / Scale Out | 增加节点数量提升处理能力 |
| 垂直扩展 | Vertical Scaling / Scale Up | 增加单节点资源提升处理能力 |
| 无状态 | Stateless | 请求不依赖服务器本地状态 |
| 分片 | Sharding | 将数据水平拆分到多个节点 |
| 读写分离 | Read-Write Splitting | 读操作与写操作路由到不同节点 |
| 背压 | Backpressure | 下游过载时向上游施加的反向压力 |
| 弹性伸缩 | Elastic Scaling | 根据负载自动增减资源 |
| 容量规划 | Capacity Planning | 预估未来资源需求 |
| 热点 | Hotspot | 负载分布不均导致的局部过载 |
| 扇出 | Fan-out | 一个请求触发多个下游请求 |

### 1.4 设计原则

ThesisMiner v8.0 的可扩展性设计遵循以下核心原则：

1. **无状态优先 (Stateless First)**：应用层尽量无状态，状态下沉到专门的存储层
2. **水平扩展优先 (Scale-Out First)**：优先通过增加节点而非提升单节点配置来扩展
3. **分区容忍 (Partition Tolerance)**：系统在网络分区时仍能提供服务
4. **渐进扩展 (Gradual Scaling)**：支持从小规模到大规模的平滑过渡
5. **弹性优先 (Elasticity First)**：能够根据负载快速伸缩
6. **故障隔离 (Failure Isolation)**：单节点故障不影响整体服务
7. **可观测性 (Observability)**：扩展性指标可度量、可告警

### 1.5 扩展性目标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 并发用户数 | 1000+ | 同时在线用户 |
| QPS (每秒查询) | 500+ | API 请求峰值 |
| LLM 并发调用 | 50+ | 同时进行的 LLM 调用 |
| 数据存储容量 | 100GB+ | 论文与缓存数据 |
| 响应延迟 P99 | < 2s | 95% 请求 < 500ms |
| 扩展响应时间 | < 60s | 从触发扩容到新节点就绪 |
| 缩容延迟 | < 300s | 负载下降后回收资源 |

---

## 2. 可扩展性架构总览

### 2.1 整体扩展性架构

```
┌─────────────────────────────────────────────────────────────────┐
│  ThesisMiner v8.0 可扩展性架构                                    │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  接入层 (可水平扩展)                                        │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐                   │   │
│  │  │ Ingress │  │ Ingress │  │ Ingress │  ← 无状态, 可扩展  │   │
│  │  │   #1    │  │   #2    │  │   #3    │                   │   │
│  │  └────┬────┘  └────┬────┘  └────┬────┘                   │   │
│  └───────┼────────────┼────────────┼────────────────────────┘   │
│          │            │            │                             │
│  ┌───────▼────────────▼────────────▼────────────────────────┐   │
│  │  应用层 (无状态, 可水平扩展)                                 │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐      │   │
│  │  │Backend  │  │Backend  │  │Backend  │  │Backend  │      │   │
│  │  │  Pod#1  │  │  Pod#2  │  │  Pod#3  │  │  Pod#N  │      │   │
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘      │   │
│  └───────┼────────────┼────────────┼────────────┼────────────┘   │
│          │            │            │            │                │
│  ┌───────▼────────────▼────────────▼────────────▼────────────┐   │
│  │  异步处理层 (Worker, 可水平扩展)                              │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐                   │   │
│  │  │ Worker  │  │ Worker  │  │ Worker  │  ← 消费消息队列     │   │
│  │  │  #1     │  │  #2     │  │  #N     │                   │   │
│  │  └─────────┘  └─────────┘  └─────────┘                   │   │
│  └──────────────────────────────────────────────────────────┘   │
│          │            │            │                             │
│  ┌───────▼────────────▼────────────▼────────────────────────┐   │
│  │  数据层 (有状态, 分片/复制)                                  │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │   │
│  │  │ SQLite (主)   │  │ Redis (主)    │  │ 对象存储      │    │   │
│  │  │  + 只读副本   │  │  + 副本       │  │ (S3/MinIO)   │    │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  外部依赖 (LLM API, 学术数据库)                              │   │
│  │  - 限流与重试                                              │   │
│  │  - 熔断与降级                                              │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 扩展维度

ThesisMiner v8.0 从以下维度进行扩展：

| 扩展维度 | 扩展对象 | 扩展方式 | 触发条件 |
|---------|---------|---------|---------|
| 计算扩展 | Backend Pod | 水平扩展 (HPA) | CPU > 70%, QPS 上升 |
| 计算扩展 | Worker Pod | 水平扩展 (HPA) | 队列深度 > 阈值 |
| 内存扩展 | Backend Pod | 垂直扩展 | 内存 > 80% |
| 存储扩展 | SQLite | 分片 / 读写分离 | 数据量 > 10GB |
| 缓存扩展 | Redis | 主从 + Cluster | 缓存命中率 < 80% |
| 网络扩展 | Ingress | 水平扩展 | 连接数 > 阈值 |
| 并发扩展 | LLM 调用 | 连接池 + 限流 | 并发数 > 限制 |

### 2.3 扩展性成熟度模型

```
┌─────────────────────────────────────────────────────────────────┐
│  扩展性成熟度模型                                                 │
│                                                                  │
│  Level 4: 自动弹性 ────────────────── (目标)                      │
│  - 全自动扩缩容                                                 │
│  - 预测性扩展                                                   │
│  - 多维度指标驱动                                                │
│                                                                  │
│  Level 3: 半自动扩展 ──────────────── (当前)                      │
│  - HPA 自动扩缩容                                               │
│  - 手动触发垂直扩展                                              │
│  - 监控告警驱动                                                 │
│                                                                  │
│  Level 2: 手动扩展 ──────────────────                             │
│  - 人工调整副本数                                                │
│  - 人工调整资源配额                                              │
│  - 定时扩缩容                                                   │
│                                                                  │
│  Level 1: 单节点 ──────────────────────                           │
│  - 单实例运行                                                    │
│  - 垂直扩展为主                                                  │
│  - 无自动伸缩                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 水平扩展 (Horizontal Scaling)

### 3.1 水平扩展原理

水平扩展通过增加节点数量来提升系统整体处理能力。其核心优势在于理论上无上限，且天然具备高可用性。

```
┌─────────────────────────────────────────────────────────────────┐
│  水平扩展原理                                                    │
│                                                                  │
│  扩展前:                                                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Backend Pod (4C/8G)                                      │   │
│  │  处理能力: 100 QPS                                         │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  扩展后 (水平扩展 3 倍):                                          │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                │
│  │ Backend #1 │  │ Backend #2 │  │ Backend #3 │                │
│  │ (4C/8G)    │  │ (4C/8G)    │  │ (4C/8G)    │                │
│  │ 100 QPS    │  │ 100 QPS    │  │ 100 QPS    │                │
│  └────────────┘  └────────────┘  └────────────┘                │
│  总处理能力: 300 QPS (线性扩展)                                   │
│                                                                  │
│  负载均衡器将请求分发到各节点:                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Load Balancer (Round-Robin / Least-Connections)          │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 水平扩展前提条件

水平扩展要求应用具备以下条件：

| 条件 | 说明 | ThesisMiner 实现 |
|------|------|-----------------|
| 无状态 | 请求不依赖本地状态 | 会话状态存储在 Redis/SQLite |
| 可共享 | 所有节点等价 | 镜像一致，配置一致 |
| 数据分离 | 状态数据集中存储 | SQLite + Redis 集中存储 |
| 负载均衡 | 请求可均匀分发 | K8s Service + Istio |
| 健康检查 | 可检测节点可用性 | Liveness/Readiness Probe |

### 3.3 Backend 水平扩展

```yaml
# deploy/k8s/scalability/backend-hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: backend-hpa
  namespace: thesisminer
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: backend
  minReplicas: 3
  maxReplicas: 20
  scaleDownBehavior:
    stabilizationWindowSeconds: 300  # 缩容稳定窗口 5 分钟
    policies:
      - type: Percent
        value: 25  # 每次最多缩容 25%
        periodSeconds: 60
  scaleUpBehavior:
    stabilizationWindowSeconds: 0  # 扩容立即执行
    policies:
      - type: Percent
        value: 100  # 每次最多扩容 100%
        periodSeconds: 30
      - type: Pods
        value: 4  # 或增加 4 个 Pod
        periodSeconds: 30
    selectPolicy: Max
  metrics:
    # CPU 利用率
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    # 内存利用率
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
    # 自定义指标: QPS
    - type: Pods
      pods:
        metric:
          name: http_requests_per_second
        target:
          type: AverageValue
          averageValue: "100"
```

### 3.4 水平扩展的挑战与应对

| 挑战 | 影响 | 应对策略 |
|------|------|---------|
| 会话状态共享 | 用户请求可能路由到不同节点 | 使用 Redis 存储会话 |
| 数据一致性 | 多节点并发写 | SQLite 单写者 + 乐观锁 |
| 连接数膨胀 | 每个节点连接数据库 | 连接池 + 连接复用 |
| 部署一致性 | 版本不一致导致行为差异 | 滚动更新 + 就绪检查 |
| 日志分散 | 排查困难 | 集中日志 (Loki) |
| 监控聚合 | 指标分散 | Prometheus 聚合 |

### 3.5 水平扩展决策矩阵

```
┌─────────────────────────────────────────────────────────────────┐
│  水平扩展决策流程                                                 │
│                                                                  │
│  负载上升                                                        │
│      │                                                           │
│      ▼                                                           │
│  ┌──────────────┐                                                │
│  │ CPU > 70%?   │──否──→ 检查其他指标                             │
│  └──────┬───────┘                                                │
│         是                                                       │
│         │                                                        │
│      ▼                                                           │
│  ┌──────────────┐                                                │
│  │ 应用无状态?  │──否──→ 重构为无状态 → 再扩展                     │
│  └──────┬───────┘                                                │
│         是                                                       │
│         │                                                        │
│      ▼                                                           │
│  ┌──────────────┐                                                │
│  │ 数据可共享?  │──否──→ 数据迁移到共享存储                        │
│  └──────┬───────┘                                                │
│         是                                                       │
│         │                                                        │
│      ▼                                                           │
│  ┌──────────────┐                                                │
│  │ 负载均衡就绪?│──否──→ 配置负载均衡                              │
│  └──────┬───────┘                                                │
│         是                                                       │
│         │                                                        │
│      ▼                                                           │
│  ┌──────────────┐                                                │
│  │ 执行水平扩展 │ → 增加 Pod 副本数                                │
│  └──────────────┘                                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. 垂直扩展 (Vertical Scaling)

### 4.1 垂直扩展原理

垂直扩展通过增加单个节点的资源（CPU、内存、存储）来提升处理能力。其优势在于实现简单，但受限于单机上限。

```
┌─────────────────────────────────────────────────────────────────┐
│  垂直扩展原理                                                    │
│                                                                  │
│  扩展前:                                                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Backend Pod (2C/4G)                                      │   │
│  │  处理能力: 50 QPS                                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  扩展后 (垂直扩展 2 倍):                                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Backend Pod (4C/8G)                                      │   │
│  │  处理能力: 100 QPS                                         │   │
│  └──────────────────────────────────────────────────────────┘   │
│  总处理能力: 100 QPS (受限于单机上限)                              │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 垂直扩展适用场景

| 场景 | 说明 | 示例 |
|------|------|------|
| 内存密集型 | 需要大内存缓存 | 大规模论文索引加载 |
| CPU 密集型 | 需要强计算能力 | NLP 处理、相似度计算 |
| I/O 密集型 | 需要高磁盘吞吐 | 大文件解析 |
| 单点瓶颈 | 无法水平扩展 | SQLite 写入节点 |
| 临时扩容 | 快速应对突发负载 | 紧急增加资源 |

### 4.3 K8s Vertical Pod Autoscaler

```yaml
# deploy/k8s/scalability/backend-vpa.yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: backend-vpa
  namespace: thesisminer
spec:
  targetRef:
    apiVersion: "apps/v1"
    kind: Deployment
    name: backend
  updatePolicy:
    updateMode: "Auto"  # Auto / Off / Initial
    minReplicas: 3
  resourcePolicy:
    containerPolicies:
      - containerName: backend
        minAllowed:
          cpu: 250m
          memory: 512Mi
        maxAllowed:
          cpu: 4000m
          memory: 8Gi
        controlledResources: ["cpu", "memory"]
        controlledValues: RequestsAndLimits
```

### 4.4 垂直扩展的局限

| 局限 | 说明 | 影响 |
|------|------|------|
| 上限限制 | 单机资源有物理上限 | 无法无限扩展 |
| 停机时间 | 修改资源需重启 Pod | 短暂服务中断 |
| 成本递增 | 高配机器性价比下降 | 单位成本上升 |
| 单点风险 | 单节点故障影响大 | 可用性降低 |
| 不灵活 | 资源调整粒度大 | 容易浪费或不足 |

### 4.5 水平 vs 垂直扩展对比

| 维度 | 水平扩展 | 垂直扩展 |
|------|---------|---------|
| 扩展上限 | 理论无上限 | 单机上限 |
| 实现复杂度 | 高（需无状态化） | 低（改配置即可） |
| 停机时间 | 无（滚动扩展） | 有（需重启） |
| 成本效率 | 线性递增 | 递减（高配贵） |
| 容错性 | 高（多副本） | 低（单点） |
| 灵活性 | 高（细粒度） | 低（粗粒度） |
| 适用阶段 | 成熟期 | 初期/瓶颈期 |
| 状态要求 | 无状态 | 可有状态 |

---

## 5. 混合扩展策略

### 5.1 混合扩展模型

ThesisMiner v8.0 采用水平扩展与垂直扩展相结合的混合策略，在不同层级和不同场景下选择最优扩展方式。

```
┌─────────────────────────────────────────────────────────────────┐
│  混合扩展策略                                                    │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  第 1 层: 水平扩展 (应用层)                                  │   │
│  │  - Backend Pod: 3-20 副本 (HPA)                            │   │
│  │  - Worker Pod: 2-10 副本 (HPA)                             │   │
│  │  - 每副本: 500m-2000m CPU, 512Mi-4Gi Memory               │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌───────────────────────────▼──────────────────────────────┐   │
│  │  第 2 层: 垂直扩展 (数据层)                                  │   │
│  │  - SQLite: 增加内存用于缓存                                 │   │
│  │  - Redis: 垂直扩展内存                                      │   │
│  │  - 节点: 升级到更高配机器                                    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌───────────────────────────▼──────────────────────────────┐   │
│  │  第 3 层: 分片扩展 (存储层)                                  │   │
│  │  - SQLite 分片 (按租户/时间)                                │   │
│  │  - Redis Cluster (按 Key 分片)                              │   │
│  │  - 对象存储 (天然可扩展)                                     │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 扩展策略选择矩阵

| 负载特征 | 推荐策略 | 理由 |
|---------|---------|------|
| 高并发、低计算 | 水平扩展 | 多节点分担连接 |
| 低并发、高计算 | 垂直扩展 | 单节点强计算 |
| 高并发、高计算 | 混合扩展 | 先水平后垂直 |
| 突发流量 | 水平扩展 | 快速扩容 |
| 持续增长 | 混合扩展 | 渐进扩展 |
| 数据量增长 | 分片扩展 | 数据分散 |

### 5.3 混合扩展实施

```python
# backend/scalability/scaling_policy.py
"""扩展策略管理器"""
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class ScalingDirection(str, Enum):
    UP = "up"
    DOWN = "down"
    NONE = "none"


class ScalingType(str, Enum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"
    HYBRID = "hybrid"


@dataclass
class ScalingMetrics:
    """扩展性指标"""
    cpu_utilization: float       # CPU 利用率 (0-1)
    memory_utilization: float    # 内存利用率 (0-1)
    qps: float                   # 每秒请求数
    avg_response_time: float     # 平均响应时间 (秒)
    queue_depth: int             # 队列深度
    active_connections: int      # 活跃连接数
    error_rate: float            # 错误率 (0-1)


class ScalingPolicy:
    """扩展策略决策器"""

    # 阈值配置
    CPU_SCALE_UP_THRESHOLD = 0.70
    CPU_SCALE_DOWN_THRESHOLD = 0.30
    MEMORY_SCALE_UP_THRESHOLD = 0.80
    MEMORY_SCALE_DOWN_THRESHOLD = 0.40
    RESPONSE_TIME_THRESHOLD = 2.0  # 秒
    ERROR_RATE_THRESHOLD = 0.01

    def decide(self, metrics: ScalingMetrics, current_replicas: int) -> dict:
        """根据指标决定扩展策略"""
        direction = self._evaluate_direction(metrics)
        scaling_type = self._select_type(metrics, direction)

        action = {
            "direction": direction.value,
            "type": scaling_type.value,
            "current_replicas": current_replicas,
            "metrics": {
                "cpu": metrics.cpu_utilization,
                "memory": metrics.memory_utilization,
                "qps": metrics.qps,
                "response_time": metrics.avg_response_time,
            },
        }

        if direction == ScalingDirection.UP:
            if scaling_type == ScalingType.HORIZONTAL:
                action["target_replicas"] = min(
                    current_replicas * 2, 20  # 最大 20 副本
                )
            elif scaling_type == ScalingType.VERTICAL:
                action["resource_adjustment"] = "increase"
            else:  # HYBRID
                action["target_replicas"] = min(
                    current_replicas + 2, 20
                )
                action["resource_adjustment"] = "increase"
        elif direction == ScalingDirection.DOWN:
            if scaling_type == ScalingType.HORIZONTAL:
                action["target_replicas"] = max(
                    current_replicas - 1, 3  # 最小 3 副本
                )
            else:
                action["resource_adjustment"] = "decrease"

        logger.info(f"扩展决策: {action}")
        return action

    def _evaluate_direction(self, m: ScalingMetrics) -> ScalingDirection:
        """评估扩展方向"""
        scale_up_signals = 0
        scale_down_signals = 0

        if m.cpu_utilization > self.CPU_SCALE_UP_THRESHOLD:
            scale_up_signals += 2
        elif m.cpu_utilization < self.CPU_SCALE_DOWN_THRESHOLD:
            scale_down_signals += 1

        if m.memory_utilization > self.MEMORY_SCALE_UP_THRESHOLD:
            scale_up_signals += 2
        elif m.memory_utilization < self.MEMORY_SCALE_DOWN_THRESHOLD:
            scale_down_signals += 1

        if m.avg_response_time > self.RESPONSE_TIME_THRESHOLD:
            scale_up_signals += 3

        if m.error_rate > self.ERROR_RATE_THRESHOLD:
            scale_up_signals += 2

        if scale_up_signals > scale_down_signals:
            return ScalingDirection.UP
        elif scale_down_signals > scale_up_signals:
            return ScalingDirection.DOWN
        return ScalingDirection.NONE

    def _select_type(
        self, m: ScalingMetrics, direction: ScalingDirection
    ) -> ScalingType:
        """选择扩展类型"""
        if direction == ScalingDirection.NONE:
            return ScalingType.HORIZONTAL

        # CPU 密集型 → 水平扩展
        if m.cpu_utilization > 0.7 and m.memory_utilization < 0.6:
            return ScalingType.HORIZONTAL

        # 内存密集型 → 垂直扩展
        if m.memory_utilization > 0.8 and m.cpu_utilization < 0.6:
            return ScalingType.VERTICAL

        # 两者都高 → 混合扩展
        if m.cpu_utilization > 0.7 and m.memory_utilization > 0.8:
            return ScalingType.HYBRID

        return ScalingType.HORIZONTAL
```

---

## 6. 无状态服务设计

### 6.1 无状态服务原则

无状态服务是水平扩展的前提。ThesisMiner v8.0 严格遵循无状态设计原则，确保任何请求可以被任何节点处理。

```
┌─────────────────────────────────────────────────────────────────┐
│  无状态服务设计                                                   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  有状态设计 (避免)                                          │   │
│  │  ┌─────────┐     ┌─────────┐                               │   │
│  │  │ 请求 1  │────→│ Pod #1  │ ← 会话状态存储在本地内存        │   │
│  │  └─────────┘     └─────────┘                               │   │
│  │  ┌─────────┐     ┌─────────┐                               │   │
│  │  │ 请求 2  │────→│ Pod #2  │ ← 无会话信息，请求失败          │   │
│  │  └─────────┘     └─────────┘                               │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  无状态设计 (推荐)                                          │   │
│  │  ┌─────────┐     ┌─────────┐     ┌──────────────┐        │   │
│  │  │ 请求 1  │────→│ Pod #1  │────→│              │        │   │
│  │  └─────────┘     └─────────┘     │  Redis       │        │   │
│  │  ┌─────────┐     ┌─────────┐     │  (会话存储)  │        │   │
│  │  │ 请求 2  │────→│ Pod #2  │────→│              │        │   │
│  │  └─────────┘     └─────────┘     └──────────────┘        │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 状态外置策略

| 状态类型 | 存储位置 | 访问方式 | 生命周期 |
|---------|---------|---------|---------|
| 用户会话 | Redis | Session ID | 30 分钟 |
| 请求上下文 | 请求体/Header | 每次携带 | 单次请求 |
| 临时文件 | 对象存储 (S3) | URL 引用 | 按需清理 |
| 计算中间结果 | Redis / SQLite | Key 引用 | TTL 过期 |
| 文件上传 | 对象存储 | Multipart | 永久/按需 |
| 长任务状态 | SQLite | 任务 ID | 任务完成 |

### 6.3 无状态服务实现

```python
# backend/scalability/stateless_service.py
"""无状态服务实现示例"""
import hashlib
import json
from typing import Optional, Any
from fastapi import Request, Response


class StatelessSessionManager:
    """无状态会话管理器

    将会话状态存储在 Redis 中，而非本地内存。
    请求通过 Session ID 关联会话。
    """

    def __init__(self, redis_client):
        self.redis = redis_client
        self.session_ttl = 1800  # 30 分钟

    async def create_session(self, user_id: str, data: dict) -> str:
        """创建会话"""
        session_id = self._generate_session_id(user_id)
        await self.redis.setex(
            f"session:{session_id}",
            self.session_ttl,
            json.dumps({"user_id": user_id, **data}),
        )
        return session_id

    async def get_session(self, session_id: str) -> Optional[dict]:
        """获取会话"""
        data = await self.redis.get(f"session:{session_id}")
        if data is None:
            return None
        # 续期
        await self.redis.expire(f"session:{session_id}", self.session_ttl)
        return json.loads(data)

    async def destroy_session(self, session_id: str):
        """销毁会话"""
        await self.redis.delete(f"session:{session_id}")

    def _generate_session_id(self, user_id: str) -> str:
        """生成会话 ID"""
        import secrets
        import time
        raw = f"{user_id}:{time.time()}:{secrets.token_hex(16)}"
        return hashlib.sha256(raw.encode()).hexdigest()


class StatelessFileHandler:
    """无状态文件处理器

    文件不存储在本地磁盘，而是上传到对象存储。
    """

    def __init__(self, storage_client):
        self.storage = storage_client

    async def upload(self, file_data: bytes, filename: str, user_id: str) -> str:
        """上传文件，返回存储 URL"""
        key = f"uploads/{user_id}/{filename}"
        url = await self.storage.upload(key, file_data)
        return url

    async def download(self, url: str) -> bytes:
        """下载文件"""
        return await self.storage.download(url)

    async def delete(self, url: str):
        """删除文件"""
        await self.storage.delete(url)
```

### 6.4 请求上下文传递

```python
# backend/scalability/request_context.py
"""请求上下文传递

所有请求所需的状态通过请求体或 Header 传递，
不依赖服务器本地存储。
"""
from dataclasses import dataclass
from typing import Optional
from fastapi import Request, Header


@dataclass
class RequestContext:
    """请求上下文"""
    user_id: str
    session_id: str
    conversation_id: Optional[str]
    request_id: str
    trace_id: str


async def build_context(
    request: Request,
    x_user_id: str = Header(...),
    x_session_id: str = Header(...),
    x_conversation_id: Optional[str] = Header(None),
    x_request_id: str = Header(...),
    x_trace_id: str = Header(...),
) -> RequestContext:
    """从请求 Header 构建上下文"""
    return RequestContext(
        user_id=x_user_id,
        session_id=x_session_id,
        conversation_id=x_conversation_id,
        request_id=x_request_id,
        trace_id=x_trace_id,
    )
```

### 6.5 本地缓存与无状态的平衡

完全无状态会导致每次请求都访问外部存储，增加延迟。ThesisMiner v8.0 采用"本地缓存 + 外部状态"的折中方案：

```python
# backend/scalability/local_cache.py
"""本地缓存（非状态依赖）

本地缓存仅作为性能优化，缓存丢失不影响正确性。
"""
import time
import threading
from typing import Optional, Any
from collections import OrderedDict


class LocalCache:
    """本地缓存

    特点:
    - 仅缓存可重建的数据
    - 缓存丢失不影响正确性
    - 设置 TTL 防止数据过期
    - 限制大小防止内存泄漏
    """

    def __init__(self, max_size: int = 500, default_ttl: int = 300):
        self._cache: OrderedDict = OrderedDict()
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
            self._cache[key] = (value, time.time() + ttl)
            self._cache.move_to_end(key)
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    def invalidate(self, key: str):
        with self._lock:
            self._cache.pop(key, None)


# 全局本地缓存实例（每个 Pod 独立）
_user_profile_cache = LocalCache(max_size=500, default_ttl=300)
_config_cache = LocalCache(max_size=100, default_ttl=600)


async def get_user_profile(user_id: str, db, cache: LocalCache = _user_profile_cache):
    """获取用户配置（带本地缓存）

    缓存未命中时从数据库加载，结果可安全缓存。
    """
    cached = cache.get(f"user:{user_id}")
    if cached is not None:
        return cached

    # 从数据库加载
    profile = await db.fetch_user_profile(user_id)
    if profile:
        cache.set(f"user:{user_id}", profile, ttl=300)

    return profile
```

---

## 7. 数据库分片与扩展

### 7.1 SQLite 扩展挑战

SQLite 作为嵌入式数据库，其扩展性面临独特挑战：

| 挑战 | 说明 | 影响 |
|------|------|------|
| 单写者 | SQLite 仅支持单写者 | 写入吞吐受限 |
| 无网络接口 | 嵌入式数据库，无客户端/服务器模式 | 无法多节点共享 |
| 文件大小 | 单文件大小限制 | 数据量上限 |
| 并发限制 | WAL 模式下读并发，写串行 | 高并发写入瓶颈 |

### 7.2 SQLite 扩展策略

```
┌─────────────────────────────────────────────────────────────────┐
│  SQLite 扩展策略演进                                              │
│                                                                  │
│  阶段 1: 单库 (初期)                                              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  thesisminer.db (< 1GB)                                   │   │
│  │  - 所有数据在一个文件                                       │   │
│  │  - WAL 模式                                                │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  阶段 2: 读写分离 (中期)                                          │
│  ┌──────────────┐        ┌──────────────┐                       │
│  │  主库 (读写)  │──复制──→│  只读副本     │                       │
│  │ thesisminer  │        │ thesisminer  │                       │
│  │   .db        │        │  _ro.db      │                       │
│  └──────────────┘        └──────────────┘                       │
│                                                                  │
│  阶段 3: 分库 (后期)                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ 分片 1   │  │ 分片 2   │  │ 分片 3   │  │ 分片 N   │        │
│  │ (用户A-D)│  │ (用户E-H)│  │ (用户I-L)│  │ (用户M-Z)│        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

### 7.3 分片策略

```python
# backend/scalability/sharding.py
"""数据库分片策略"""
import hashlib
import logging
from typing import Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ShardingStrategy:
    """分片策略基类"""

    def get_shard(self, key: str) -> int:
        raise NotImplementedError


class HashSharding(ShardingStrategy):
    """哈希分片

    对 Key 取哈希后取模，均匀分布到各分片。
    """

    def __init__(self, shard_count: int):
        self.shard_count = shard_count

    def get_shard(self, key: str) -> int:
        hash_value = int(hashlib.md5(key.encode()).hexdigest(), 16)
        return hash_value % self.shard_count


class RangeSharding(ShardingStrategy):
    """范围分片

    按 Key 的范围分配到不同分片。
    """

    def __init__(self, ranges: list):
        """ranges: [(start, end, shard_id), ...]"""
        self.ranges = ranges

    def get_shard(self, key: str) -> int:
        for start, end, shard_id in self.ranges:
            if start <= key < end:
                return shard_id
        return self.ranges[-1][2]  # 默认最后一个分片


class TimeSharding(ShardingStrategy):
    """时间分片

    按时间维度分片，适合时序数据。
    """

    def __init__(self, interval_days: int = 30):
        self.interval_days = interval_days

    def get_shard(self, timestamp: float) -> int:
        return int(timestamp // (self.interval_days * 86400))


@dataclass
class ShardInfo:
    """分片信息"""
    shard_id: int
    db_path: str
    host: str
    port: int


class ShardManager:
    """分片管理器"""

    def __init__(self, strategy: ShardingStrategy, shards: list):
        self.strategy = strategy
        self.shards = {s.shard_id: s for s in shards}

    def get_shard_info(self, key: str) -> ShardInfo:
        """获取 Key 对应的分片信息"""
        shard_id = self.strategy.get_shard(key)
        return self.shards[shard_id]

    def get_all_shards(self) -> list:
        """获取所有分片"""
        return list(self.shards.values())


# 分片路由示例
hash_sharding = HashSharding(shard_count=4)
shards = [
    ShardInfo(0, "/data/shard_0.db", "db-0", 5432),
    ShardInfo(1, "/data/shard_1.db", "db-1", 5432),
    ShardInfo(2, "/data/shard_2.db", "db-2", 5432),
    ShardInfo(3, "/data/shard_3.db", "db-3", 5432),
]
shard_manager = ShardManager(hash_sharding, shards)
```

### 7.4 读写分离

```python
# backend/scalability/read_write_split.py
"""读写分离实现"""
import logging
from contextlib import asynccontextmanager
from typing import Optional

logger = logging.getLogger(__name__)


class ReadWriteSplitRouter:
    """读写分离路由器

    写操作路由到主库，读操作路由到只读副本。
    """

    def __init__(self, master_engine, replica_engines: list):
        self.master = master_engine
        self.replicas = replica_engines
        self._replica_index = 0
        self._replica_count = len(replica_engines)

    def get_write_engine(self):
        """获取写引擎（主库）"""
        return self.master

    def get_read_engine(self):
        """获取读引擎（轮询只读副本）"""
        if not self.replicas:
            return self.master
        engine = self.replicas[self._replica_index]
        self._replica_index = (self._replica_index + 1) % self._replica_count
        return engine

    @asynccontextmanager
    async def write_session(self):
        """写会话"""
        session = self.master.begin()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise

    @asynccontextmanager
    async def read_session(self):
        """读会话"""
        engine = self.get_read_engine()
        session = engine.begin()
        try:
            yield session
        finally:
            session.close()
```

### 7.5 数据库连接池扩展

```python
# backend/scalability/connection_pool.py
"""数据库连接池管理"""
import logging
import asyncio
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class PoolConfig:
    """连接池配置"""
    min_size: int = 5
    max_size: int = 20
    max_idle_time: int = 300  # 秒
    max_lifetime: int = 1800  # 秒
    connection_timeout: float = 30.0
    idle_check_interval: int = 60


class ScalableConnectionPool:
    """可扩展的连接池

    特性:
    - 动态调整连接数
    - 连接健康检查
    - 空闲连接回收
    - 连接生命周期管理
    """

    def __init__(self, create_connection, config: PoolConfig):
        self._create_connection = create_connection
        self._config = config
        self._pool: asyncio.Queue = asyncio.Queue(maxsize=config.max_size)
        self._size = 0
        self._lock = asyncio.Lock()
        self._stats = {
            "created": 0,
            "reused": 0,
            "closed": 0,
            "timed_out": 0,
        }

    async def acquire(self):
        """获取连接"""
        try:
            # 尝试从池中获取空闲连接
            conn = await asyncio.wait_for(
                self._pool.get(), timeout=0.1
            )
            if self._is_valid(conn):
                self._stats["reused"] += 1
                return conn
            else:
                await self._close_connection(conn)
        except asyncio.TimeoutError:
            pass

        # 创建新连接
        async with self._lock:
            if self._size < self._config.max_size:
                self._size += 1
                conn = await self._create_connection()
                self._stats["created"] += 1
                return conn

        # 等待连接释放
        conn = await asyncio.wait_for(
            self._pool.get(), timeout=self._config.connection_timeout
        )
        self._stats["reused"] += 1
        return conn

    async def release(self, conn):
        """释放连接"""
        if self._is_valid(conn):
            await self._pool.put(conn)
        else:
            await self._close_connection(conn)
            async with self._lock:
                self._size -= 1

    def _is_valid(self, conn) -> bool:
        """检查连接是否有效"""
        # 实现连接健康检查
        return True

    async def _close_connection(self, conn):
        """关闭连接"""
        try:
            await conn.close()
            self._stats["closed"] += 1
        except Exception as e:
            logger.error(f"关闭连接失败: {e}")

    def get_stats(self) -> dict:
        """获取连接池统计"""
        return {
            **self._stats,
            "pool_size": self._size,
            "idle": self._pool.qsize(),
            "active": self._size - self._pool.qsize(),
        }
```

---

## 8. 缓存扩展策略

### 8.1 缓存扩展架构

```
┌─────────────────────────────────────────────────────────────────┐
│  缓存扩展架构                                                    │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  L1: 进程内缓存 (每 Pod 独立)                                │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐                   │   │
│  │  │ Pod #1  │  │ Pod #2  │  │ Pod #3  │                   │   │
│  │  │ L1Cache │  │ L1Cache │  │ L1Cache │                   │   │
│  │  └─────────┘  └─────────┘  └─────────┘                   │   │
│  └──────────────────────────────────────────────────────────┘   │
│         │            │            │                              │
│  ┌──────▼────────────▼────────────▼──────────────────────────┐  │
│  │  L2: Redis Cluster (分布式共享缓存)                          │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐                    │  │
│  │  │ Shard 0 │  │ Shard 1 │  │ Shard 2 │  ← 按 Key 分片      │  │
│  │  │ Master  │  │ Master  │  │ Master  │                    │  │
│  │  │ +Repl   │  │ +Repl   │  │ +Repl   │                    │  │
│  │  └─────────┘  └─────────┘  └─────────┘                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│         │            │            │                              │
│  ┌──────▼────────────▼────────────▼──────────────────────────┐  │
│  │  L3: SQLite 持久化缓存 (冷数据)                              │  │
│  │  ┌────────────────────────────────────────────────────┐   │  │
│  │  │  cache_table (key, value, expires_at)               │   │  │
│  │  └────────────────────────────────────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 Redis Cluster 扩展

```python
# backend/scalability/redis_cluster.py
"""Redis Cluster 扩展配置"""
import logging
from redis.cluster import RedisCluster, ClusterNode

logger = logging.getLogger(__name__)


def create_redis_cluster(nodes: list) -> RedisCluster:
    """创建 Redis Cluster 客户端

    Args:
        nodes: [(host, port), ...] 至少 6 个节点 (3 主 3 从)
    """
    startup_nodes = [
        ClusterNode(host=host, port=port)
        for host, port in nodes
    ]
    client = RedisCluster(
        startup_nodes=startup_nodes,
        decode_responses=True,
        # 连接池配置
        max_connections=100,
        # 重试配置
        retry_on_timeout=True,
        retry_on_error=[],
        # 超时配置
        socket_timeout=5.0,
        socket_connect_timeout=5.0,
        health_check_interval=30,
    )
    logger.info(f"Redis Cluster 创建成功: {len(nodes)} 节点")
    return client


# Redis Cluster 部署配置
REDIS_CLUSTER_NODES = [
    ("redis-cluster-0", 6379),
    ("redis-cluster-1", 6379),
    ("redis-cluster-2", 6379),
    ("redis-cluster-3", 6379),
    ("redis-cluster-4", 6379),
    ("redis-cluster-5", 6379),
]
```

### 8.3 缓存分片策略

| 分片策略 | 说明 | 优点 | 缺点 |
|---------|------|------|------|
| 哈希分片 | CRC16(key) % 16384 | 分布均匀 | 扩容需 rehash |
| 一致性哈希 | 虚拟节点环 | 扩容影响小 | 实现复杂 |
| 范围分片 | 按 Key 范围 | 范围查询高效 | 可能热点 |
| 业务分片 | 按业务维度 | 隔离性好 | 可能不均衡 |

### 8.4 缓存预热与淘汰

```python
# backend/scalability/cache_warmup.py
"""缓存预热与淘汰策略"""
import logging
import asyncio
from typing import List

logger = logging.getLogger(__name__)


class CacheWarmupManager:
    """缓存预热管理器"""

    def __init__(self, cache, db):
        self.cache = cache
        self.db = db

    async def warmup_user_profiles(self, user_ids: List[str]):
        """预热用户配置缓存"""
        logger.info(f"预热 {len(user_ids)} 个用户配置")
        tasks = [self._warmup_one(uid) for uid in user_ids]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _warmup_one(self, user_id: str):
        try:
            profile = await self.db.fetch_user_profile(user_id)
            if profile:
                await self.cache.set(
                    f"user:{user_id}", profile, ttl=3600
                )
        except Exception as e:
            logger.error(f"预热用户 {user_id} 失败: {e}")

    async def warmup_hot_theses(self, limit: int = 100):
        """预热热门论文缓存"""
        theses = await self.db.fetch_hot_theses(limit)
        for thesis in theses:
            await self.cache.set(
                f"thesis:{thesis['id']}", thesis, ttl=7200
            )
        logger.info(f"预热 {len(theses)} 篇热门论文")


class CacheEvictionPolicy:
    """缓存淘汰策略"""

    # 淘汰策略优先级
    EVICTION_PRIORITY = {
        "expired": 0,      # 最高优先级: 已过期
        "lru": 1,          # 最近最少使用
        "lfu": 2,          # 最少使用频率
        "fifo": 3,         # 先进先出
        "size_based": 4,   # 基于大小
        "ttl_based": 5,    # 基于 TTL
    }

    async def evict(self, cache, target_size: int):
        """执行淘汰"""
        current_size = await cache.dbsize()
        if current_size <= target_size:
            return 0

        evicted = 0
        # 1. 清理过期 Key
        evicted += await self._evict_expired(cache)

        # 2. 如果仍超限，按 LRU 淘汰
        if await cache.dbsize() > target_size:
            evicted += await self._evict_lru(cache, target_size)

        return evicted

    async def _evict_expired(self, cache) -> int:
        """清理过期 Key"""
        # Redis 自动清理过期 Key，这里主动触发
        return 0

    async def _evict_lru(self, cache, target_size: int) -> int:
        """LRU 淘汰"""
        # 配置 maxmemory-policy allkeys-lru
        # Redis 会自动淘汰
        return 0
```

### 8.5 缓存击穿/穿透/雪崩防护

```python
# backend/scalability/cache_protection.py
"""缓存防护: 击穿、穿透、雪崩"""
import asyncio
import logging
import time
import hashlib
from typing import Optional, Any

logger = logging.getLogger(__name__)


class CacheProtection:
    """缓存防护器"""

    def __init__(self, cache, db):
        self.cache = cache
        self.db = db
        self._locks: dict = {}  # Key 级别互斥锁
        self._bloom_filter = set()  # 简化版布隆过滤器

    async def get_with_protection(
        self,
        key: str,
        loader,
        ttl: int = 3600,
        null_ttl: int = 60,
    ) -> Optional[Any]:
        """带防护的缓存获取

        防护:
        - 击穿: 互斥锁防止并发回源
        - 穿透: 空值缓存 + 布隆过滤器
        - 雪崩: TTL 随机化
        """
        # 1. 检查布隆过滤器（防止穿透）
        if key not in self._bloom_filter:
            # 可能不存在，先查缓存
            cached = await self.cache.get(key)
            if cached is not None:
                return cached if cached != "__NULL__" else None
            # 不在布隆过滤器中，直接返回 None
            return None

        # 2. 查缓存
        cached = await self.cache.get(key)
        if cached is not None:
            return cached if cached != "__NULL__" else None

        # 3. 互斥锁防止击穿
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            # Double-check
            cached = await self.cache.get(key)
            if cached is not None:
                return cached if cached != "__NULL__" else None

            # 4. 回源加载
            value = await loader()
            if value is not None:
                # TTL 随机化防止雪崩
                actual_ttl = ttl + int(time.time()) % 60
                await self.cache.set(key, value, ttl=actual_ttl)
                self._bloom_filter.add(key)
                return value
            else:
                # 空值缓存（防止穿透）
                await self.cache.set(key, "__NULL__", ttl=null_ttl)
                return None
```

---

## 9. 微服务架构演进

### 9.1 单体到微服务演进路径

```
┌─────────────────────────────────────────────────────────────────┐
│  架构演进路径                                                    │
│                                                                  │
│  阶段 1: 单体应用 (当前)                                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  ThesisMiner Backend (单体)                                │   │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐           │   │
│  │  │ API  │ │ NLP  │ │ LLM  │ │Agent │ │ DB   │           │   │
│  │  │路由  │ │处理  │ │调用  │ │编排  │ │访问  │           │   │
│  │  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  阶段 2: 模块化单体 (近期)                                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  ThesisMiner Backend (模块化)                              │   │
│  │  ┌──────────────────────────────────────────────────┐    │   │
│  │  │  清晰的模块边界 + 内部 API                         │    │   │
│  │  └──────────────────────────────────────────────────┘    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  阶段 3: 微服务 (远期, 按需)                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ API 网关 │  │ NLP 服务 │  │ LLM 服务 │  │ Agent    │       │
│  │ Service  │  │ Service  │  │ Service  │  │ Service  │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
│         │            │            │            │                │
│  ┌──────▼────────────▼────────────▼────────────▼───────────┐   │
│  │  消息总线 / 服务网格                                      │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 9.2 服务拆分原则

| 原则 | 说明 | 示例 |
|------|------|------|
| 单一职责 | 每个服务负责一个业务领域 | NLP 服务只做文本处理 |
| 独立部署 | 服务可独立部署和升级 | NLP 服务升级不影响 API |
| 数据自治 | 每个服务管理自己的数据 | NLP 服务有自己的数据库 |
| 接口稳定 | 服务间接口向后兼容 | API 版本化 |
| 故障隔离 | 单服务故障不蔓延 | 熔断器隔离故障 |

### 9.3 服务间通信

```python
# backend/scalability/service_communication.py
"""服务间通信模式"""
import asyncio
import logging
from typing import Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ServiceEndpoint:
    """服务端点"""
    name: str
    host: str
    port: int
    health_check_path: str = "/health"


class ServiceClient:
    """服务客户端

    支持同步/异步通信，内置重试、熔断、超时。
    """

    def __init__(self, endpoint: ServiceEndpoint, http_client):
        self.endpoint = endpoint
        self.http = http_client
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=30,
        )

    async def call(self, method: str, path: str, **kwargs) -> Any:
        """调用服务"""
        if not self._circuit_breaker.can_call():
            raise ServiceUnavailableError(
                f"服务 {self.endpoint.name} 熔断中"
            )

        url = f"http://{self.endpoint.host}:{self.endpoint.port}{path}"
        try:
            response = await self._call_with_retry(
                method, url, **kwargs
            )
            self._circuit_breaker.record_success()
            return response
        except Exception as e:
            self._circuit_breaker.record_failure()
            raise

    async def _call_with_retry(self, method, url, retries=3, **kwargs):
        """带重试的调用"""
        last_error = None
        for attempt in range(retries):
            try:
                response = await self.http.request(
                    method, url, timeout=10.0, **kwargs
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                last_error = e
                wait = 2 ** attempt  # 指数退避
                logger.warning(
                    f"调用失败 (attempt {attempt+1}/{retries}): {e}, "
                    f"等待 {wait}s 重试"
                )
                await asyncio.sleep(wait)
        raise last_error


class CircuitBreaker:
    """熔断器"""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 30):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._failure_count = 0
        self._last_failure_time = 0
        self._state = "closed"  # closed / open / half-open

    def can_call(self) -> bool:
        if self._state == "open":
            import time
            if time.time() - self._last_failure_time > self.recovery_timeout:
                self._state = "half-open"
                return True
            return False
        return True

    def record_success(self):
        self._failure_count = 0
        self._state = "closed"

    def record_failure(self):
        import time
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self.failure_threshold:
            self._state = "open"
            logger.warning(f"熔断器开启: 失败 {self._failure_count} 次")


class ServiceUnavailableError(Exception):
    pass
```

### 9.4 服务发现

```python
# backend/scalability/service_discovery.py
"""服务发现"""
import logging
import asyncio
from typing import List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ServiceInstance:
    """服务实例"""
    id: str
    host: str
    port: int
    healthy: bool = True
    metadata: dict = None


class ServiceRegistry:
    """服务注册中心

    基于 K8s Service + DNS 实现服务发现。
    """

    def __init__(self):
        self._services: dict = {}  # name -> [ServiceInstance]
        self._watchers: list = []

    async def register(self, service_name: str, instance: ServiceInstance):
        """注册服务实例"""
        if service_name not in self._services:
            self._services[service_name] = []
        self._services[service_name].append(instance)
        logger.info(f"注册服务: {service_name} -> {instance.host}:{instance.port}")
        await self._notify_watchers(service_name)

    async def deregister(self, service_name: str, instance_id: str):
        """注销服务实例"""
        if service_name in self._services:
            self._services[service_name] = [
                i for i in self._services[service_name]
                if i.id != instance_id
            ]
            logger.info(f"注销服务: {service_name}/{instance_id}")

    async def discover(self, service_name: str) -> List[ServiceInstance]:
        """发现服务实例"""
        instances = self._services.get(service_name, [])
        return [i for i in instances if i.healthy]

    async def discover_one(self, service_name: str) -> Optional[ServiceInstance]:
        """发现一个健康实例（负载均衡）"""
        instances = await self.discover(service_name)
        if not instances:
            return None
        # 简单轮询
        import random
        return random.choice(instances)

    async def _notify_watchers(self, service_name: str):
        """通知监听者"""
        for watcher in self._watchers:
            await watcher(service_name)
```

---

## 10. 性能瓶颈识别

### 10.1 瓶颈识别方法论

```
┌─────────────────────────────────────────────────────────────────┐
│  性能瓶颈识别流程                                                 │
│                                                                  │
│  1. 监控指标收集                                                  │
│     ├─ 系统指标 (CPU/Memory/Disk/Network)                        │
│     ├─ 应用指标 (QPS/延迟/错误率)                                 │
│     ├─ 依赖指标 (DB/Cache/LLM 延迟)                              │
│     └─ 业务指标 (并发用户/任务队列)                               │
│                                                                  │
│  2. 异常检测                                                      │
│     ├─ 阈值告警 (CPU > 80%)                                      │
│     ├─ 趋势分析 (延迟持续上升)                                    │
│     ├─ 异常检测 (突发尖峰)                                       │
│     └─ 对比分析 (环比/同比)                                      │
│                                                                  │
│  3. 根因分析                                                      │
│     ├─ 链路追踪 (Jaeger)                                         │
│     ├─ 性能剖析 (cProfile/py-spy)                                │
│     ├─ 日志分析 (Loki)                                           │
│     └─ 依赖排查 (DB 慢查询/Cache 命中率)                          │
│                                                                  │
│  4. 优化实施                                                      │
│     ├─ 代码优化                                                  │
│     ├─ 架构优化                                                  │
│     ├─ 资源调整                                                  │
│     └─ 扩展调整                                                  │
│                                                                  │
│  5. 效果验证                                                      │
│     └─ 指标对比 (优化前后)                                       │
└─────────────────────────────────────────────────────────────────┘
```

### 10.2 常见瓶颈与特征

| 瓶颈类型 | 特征指标 | 典型原因 | 解决方向 |
|---------|---------|---------|---------|
| CPU 瓶颈 | CPU > 80%, 负载高 | 计算密集、低效算法 | 水平扩展、算法优化 |
| 内存瓶颈 | 内存 > 90%, OOM | 内存泄漏、大对象 | 垂直扩展、修复泄漏 |
| 磁盘 I/O | I/O wait 高, 磁盘满 | 频繁读写、日志过多 | SSD、异步写入 |
| 网络 I/O | 网络延迟高 | 带宽不足、跨可用区 | CDN、就近部署 |
| 数据库 | 查询慢、锁等待 | 慢查询、锁竞争 | 索引优化、读写分离 |
| 缓存 | 命中率低 | 缓存策略不当 | 调整 TTL、预热 |
| LLM API | 调用慢、超时 | 限流、网络 | 批处理、缓存 |
| 连接池 | 连接耗尽 | 连接泄漏、池太小 | 修复泄漏、扩池 |

### 10.3 性能剖析工具

```python
# backend/scalability/profiling.py
"""性能剖析工具集成"""
import cProfile
import pstats
import io
import time
import logging
from functools import wraps
from contextlib import contextmanager

logger = logging.getLogger(__name__)


def profile(func):
    """函数性能剖析装饰器"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        profiler = cProfile.Profile()
        profiler.enable()
        try:
            result = await func(*args, **kwargs)
        finally:
            profiler.disable()
            stats = pstats.Stats(profiler)
            stats.sort_stats("cumulative")
            buffer = io.StringIO()
            stats.stream = buffer
            stats.print_stats(20)  # Top 20
            logger.info(
                f"性能剖析: {func.__name__}\n{buffer.getvalue()}"
            )
        return result
    return wrapper


@contextmanager
def timing(name: str):
    """计时上下文管理器"""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        logger.info(f"{name} 耗时: {elapsed:.3f}s")


class PerformanceMonitor:
    """性能监控器"""

    def __init__(self):
        self._timings: dict = {}

    @contextmanager
    def measure(self, name: str):
        """测量代码块耗时"""
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            if name not in self._timings:
                self._timings[name] = {
                    "count": 0, "total": 0, "max": 0, "min": float("inf")
                }
            stats = self._timings[name]
            stats["count"] += 1
            stats["total"] += elapsed
            stats["max"] = max(stats["max"], elapsed)
            stats["min"] = min(stats["min"], elapsed)

    def get_report(self) -> dict:
        """获取性能报告"""
        report = {}
        for name, stats in self._timings.items():
            report[name] = {
                "count": stats["count"],
                "avg": stats["total"] / stats["count"] if stats["count"] else 0,
                "max": stats["max"],
                "min": stats["min"],
                "total": stats["total"],
            }
        return report
```

### 10.4 USE 方法 (Utilization/Saturation/Errors)

```python
# backend/scalability/use_method.py
"""USE 方法: 利用率/饱和度/错误"""
import psutil
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ResourceMetrics:
    """资源指标"""
    # CPU
    cpu_utilization: float       # 利用率 (0-1)
    cpu_load_avg_1m: float       # 1 分钟负载
    cpu_load_avg_5m: float       # 5 分钟负载
    cpu_load_avg_15m: float      # 15 分钟负载

    # 内存
    memory_utilization: float    # 利用率 (0-1)
    memory_available: float      # 可用内存 (bytes)
    memory_total: float          # 总内存 (bytes)
    swap_utilization: float      # Swap 利用率

    # 磁盘
    disk_utilization: dict       # 各分区利用率
    disk_io_read_bytes: float    # 读字节
    disk_io_write_bytes: float   # 写字节
    disk_io_time: float          # I/O 时间

    # 网络
    network_bytes_sent: float    # 发送字节
    network_bytes_recv: float    # 接收字节
    network_errors: int          # 网络错误
    network_drops: int           # 丢包


class USEAnalyzer:
    """USE 方法分析器"""

    def collect(self) -> ResourceMetrics:
        """收集资源指标"""
        cpu_percent = psutil.cpu_percent(interval=1) / 100
        load_avg = psutil.getloadavg()
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        disk_usage = {}
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disk_usage[partition.mountpoint] = usage.percent / 100
            except PermissionError:
                continue

        disk_io = psutil.disk_io_counters()
        net_io = psutil.net_io_counters()

        return ResourceMetrics(
            cpu_utilization=cpu_percent,
            cpu_load_avg_1m=load_avg[0],
            cpu_load_avg_5m=load_avg[1],
            cpu_load_avg_15m=load_avg[2],
            memory_utilization=mem.percent / 100,
            memory_available=mem.available,
            memory_total=mem.total,
            swap_utilization=swap.percent / 100,
            disk_utilization=disk_usage,
            disk_io_read_bytes=disk_io.read_bytes if disk_io else 0,
            disk_io_write_bytes=disk_io.write_bytes if disk_io else 0,
            disk_io_time=0,
            network_bytes_sent=net_io.bytes_sent,
            network_bytes_recv=net_io.bytes_recv,
            network_errors=net_io.errin + net_io.errout,
            network_drops=net_io.dropin + net_io.dropout,
        )

    def analyze(self, metrics: ResourceMetrics) -> list:
        """分析瓶颈"""
        bottlenecks = []

        # CPU 分析
        if metrics.cpu_utilization > 0.8:
            bottlenecks.append({
                "resource": "CPU",
                "type": "Utilization",
                "value": metrics.cpu_utilization,
                "severity": "high",
                "message": f"CPU 利用率过高: {metrics.cpu_utilization:.1%}",
            })
        if metrics.cpu_load_avg_1m > psutil.cpu_count() * 1.5:
            bottlenecks.append({
                "resource": "CPU",
                "type": "Saturation",
                "value": metrics.cpu_load_avg_1m,
                "severity": "high",
                "message": f"CPU 负载饱和: {metrics.cpu_load_avg_1m:.1f}",
            })

        # 内存分析
        if metrics.memory_utilization > 0.85:
            bottlenecks.append({
                "resource": "Memory",
                "type": "Utilization",
                "value": metrics.memory_utilization,
                "severity": "high",
                "message": f"内存利用率过高: {metrics.memory_utilization:.1%}",
            })
        if metrics.swap_utilization > 0.1:
            bottlenecks.append({
                "resource": "Memory",
                "type": "Saturation",
                "value": metrics.swap_utilization,
                "severity": "medium",
                "message": f"使用 Swap: {metrics.swap_utilization:.1%}",
            })

        # 磁盘分析
        for mount, usage in metrics.disk_utilization.items():
            if usage > 0.85:
                bottlenecks.append({
                    "resource": f"Disk:{mount}",
                    "type": "Utilization",
                    "value": usage,
                    "severity": "high",
                    "message": f"磁盘 {mount} 使用率过高: {usage:.1%}",
                })

        # 网络分析
        if metrics.network_errors > 0:
            bottlenecks.append({
                "resource": "Network",
                "type": "Errors",
                "value": metrics.network_errors,
                "severity": "medium",
                "message": f"网络错误: {metrics.network_errors}",
            })

        return bottlenecks
```

---

## 11. 容量规划

### 11.1 容量规划方法论

```
┌─────────────────────────────────────────────────────────────────┐
│  容量规划流程                                                    │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  1. 基线测量                                                │   │
│  │  - 当前资源使用                                              │   │
│  │  - 当前性能指标                                              │   │
│  │  - 当前用户规模                                              │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              ↓                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  2. 增长预测                                                │   │
│  │  - 用户增长曲线                                              │   │
│  │  - 数据增长速率                                              │   │
│  │  - 流量模式分析                                              │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              ↓                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  3. 需求计算                                                │   │
│  │  - 峰值 QPS 估算                                             │   │
│  │  - 存储容量估算                                              │   │
│  │  - 带宽需求估算                                              │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              ↓                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  4. 资源规划                                                │   │
│  │  - 计算资源 (CPU/Memory)                                    │   │
│  │  - 存储资源 (Disk/Object)                                   │   │
│  │  - 网络资源 (Bandwidth)                                     │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              ↓                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  5. 预留缓冲                                                │   │
│  │  - 峰值缓冲 (2x 峰值)                                       │   │
│  │  - 故障缓冲 (单节点故障可承受)                                │   │
│  │  - 增长缓冲 (6 个月增长)                                     │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 11.2 容量计算模型

```python
# backend/scalability/capacity_planning.py
"""容量规划模型"""
import logging
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class CurrentMetrics:
    """当前指标"""
    daily_active_users: int       # 日活用户
    peak_qps: float               # 峰值 QPS
    avg_qps: float                # 平均 QPS
    avg_response_time: float      # 平均响应时间 (秒)
    data_size_gb: float           # 数据量 (GB)
    daily_growth_mb: float        # 日增长量 (MB)
    cpu_per_pod: float            # 每 Pod CPU (核)
    memory_per_pod: float         # 每 Pod 内存 (GB)
    current_pods: int             # 当前 Pod 数


@dataclass
class GrowthForecast:
    """增长预测"""
    monthly_user_growth: float    # 月用户增长率
    monthly_data_growth: float    # 月数据增长率
    forecast_months: int          # 预测月数


@dataclass
class CapacityPlan:
    """容量规划"""
    required_pods: int
    required_cpu_total: float
    required_memory_total: float
    required_storage_gb: float
    required_bandwidth_mbps: float
    peak_qps_forecast: float
    recommendations: List[str]


class CapacityPlanner:
    """容量规划器"""

    # 单 Pod 处理能力 (QPS)
    QPS_PER_POD = 100
    # 峰值/均值比
    PEAK_RATIO = 3.0
    # 缓冲系数
    BUFFER_FACTOR = 1.5
    # 故障冗余 (至少能承受 1 个节点故障)
    FAILOVER_REDUNDANCY = 1

    def plan(
        self,
        current: CurrentMetrics,
        forecast: GrowthForecast,
    ) -> CapacityPlan:
        """生成容量规划"""
        # 1. 预测用户增长
        future_users = current.daily_active_users * (
            (1 + forecast.monthly_user_growth) ** forecast.forecast_months
        )

        # 2. 预测 QPS
        user_growth_factor = future_users / max(current.daily_active_users, 1)
        future_peak_qps = current.peak_qps * user_growth_factor
        future_avg_qps = current.avg_qps * user_growth_factor

        # 3. 计算所需 Pod 数
        required_qps = future_peak_qps * self.BUFFER_FACTOR
        required_pods = int(required_qps / self.QPS_PER_POD) + 1
        required_pods += self.FAILOVER_REDUNDANCY  # 故障冗余
        required_pods = max(required_pods, 3)  # 最少 3 个

        # 4. 计算所需资源
        required_cpu = required_pods * current.cpu_per_pod
        required_memory = required_pods * current.memory_per_pod

        # 5. 预测存储需求
        future_data_growth = (
            current.daily_growth_mb * 30 * forecast.forecast_months
        )
        future_data_size = (
            current.data_size_gb * (1 + forecast.monthly_data_growth) ** forecast.forecast_months
            + future_data_growth / 1024
        )
        required_storage = future_data_size * self.BUFFER_FACTOR

        # 6. 带宽估算
        avg_response_size = 50  # KB (估算)
        required_bandwidth = (
            future_peak_qps * avg_response_size * 8 / 1000  # Mbps
        ) * self.BUFFER_FACTOR

        # 7. 生成建议
        recommendations = self._generate_recommendations(
            current, required_pods, required_storage, future_peak_qps
        )

        plan = CapacityPlan(
            required_pods=required_pods,
            required_cpu_total=required_cpu,
            required_memory_total=required_memory,
            required_storage_gb=required_storage,
            required_bandwidth_mbps=required_bandwidth,
            peak_qps_forecast=future_peak_qps,
            recommendations=recommendations,
        )

        logger.info(f"容量规划完成: {plan}")
        return plan

    def _generate_recommendations(
        self, current, required_pods, required_storage, future_qps
    ) -> List[str]:
        """生成建议"""
        recs = []
        if required_pods > current.current_pods * 2:
            recs.append(
                f"Pod 数需从 {current.current_pods} 扩展到 {required_pods}，"
                f"建议提前配置 HPA 最大副本数"
            )
        if required_storage > current.data_size_gb * 3:
            recs.append(
                f"存储需从 {current.data_size_gb:.1f}GB 扩展到 "
                f"{required_storage:.1f}GB，建议启用数据分片"
            )
        if future_qps > 500:
            recs.append(
                f"预测峰值 QPS {future_qps:.0f}，建议增加缓存层"
            )
        if required_pods > 10:
            recs.append(
                f"Pod 数 {required_pods}，建议考虑微服务拆分"
            )
        return recs


# 容量规划示例
current = CurrentMetrics(
    daily_active_users=500,
    peak_qps=150,
    avg_qps=30,
    avg_response_time=0.5,
    data_size_gb=5,
    daily_growth_mb=50,
    cpu_per_pod=0.5,
    memory_per_pod=1,
    current_pods=3,
)

forecast = GrowthForecast(
    monthly_user_growth=0.15,  # 月增长 15%
    monthly_data_growth=0.10,  # 月增长 10%
    forecast_months=6,         # 预测 6 个月
)

planner = CapacityPlanner()
plan = planner.plan(current, forecast)
```

### 11.3 容量规划表

| 资源 | 当前 (100 用户) | 3 个月 (500 用户) | 6 个月 (1000 用户) | 12 个月 (3000 用户) |
|------|---------------|------------------|-------------------|-------------------|
| Backend Pod | 3 | 5 | 8 | 15 |
| Worker Pod | 2 | 4 | 6 | 10 |
| CPU 总量 | 1.5 核 | 3 核 | 5 核 | 10 核 |
| 内存总量 | 3 GB | 6 GB | 10 GB | 20 GB |
| SQLite 存储 | 1 GB | 5 GB | 10 GB | 30 GB |
| Redis 内存 | 512 MB | 1 GB | 2 GB | 4 GB |
| 对象存储 | 5 GB | 25 GB | 50 GB | 150 GB |
| 网络带宽 | 10 Mbps | 50 Mbps | 100 Mbps | 300 Mbps |

---

## 12. 弹性伸缩机制

### 12.1 弹性伸缩架构

```
┌─────────────────────────────────────────────────────────────────┐
│  弹性伸缩架构                                                    │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  指标采集层                                                 │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐               │   │
│  │  │ CPU/Mem  │  │ QPS/延迟 │  │ 队列深度  │               │   │
│  │  └──────────┘  └──────────┘  └──────────┘               │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              ↓                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  决策层                                                     │   │
│  │  ┌──────────────────────────────────────────────────┐    │   │
│  │  │  伸缩策略引擎                                      │    │   │
│  │  │  - 阈值规则                                        │    │   │
│  │  │  - 预测模型                                        │    │   │
│  │  │  - 冷却期                                          │    │   │
│  │  └──────────────────────────────────────────────────┘    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              ↓                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  执行层                                                     │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐               │   │
│  │  │ HPA      │  │ VPA      │  │ CA       │               │   │
│  │  │ (Pod级)  │  │ (资源级) │  │ (节点级) │               │   │
│  │  └──────────┘  └──────────┘  └──────────┘               │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 12.2 预测性扩展

```python
# backend/scalability/predictive_scaling.py
"""预测性扩展"""
import logging
from datetime import datetime, timedelta
from typing import List, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class HistoricalDataPoint:
    """历史数据点"""
    timestamp: datetime
    qps: float
    cpu_utilization: float
    pod_count: int


class PredictiveScaler:
    """预测性扩展器

    基于历史负载数据预测未来负载，提前扩展。
    """

    def __init__(self, lookback_hours: int = 168):  # 默认回看 7 天
        self.lookback_hours = lookback_hours
        self._history: List[HistoricalDataPoint] = []

    def add_data_point(self, point: HistoricalDataPoint):
        """添加数据点"""
        self._history.append(point)
        # 保留最近 lookback_hours 的数据
        cutoff = datetime.utcnow() - timedelta(hours=self.lookback_hours)
        self._history = [p for p in self._history if p.timestamp > cutoff]

    def predict(self, hours_ahead: int = 1) -> dict:
        """预测未来负载"""
        if len(self._history) < 24:
            logger.warning("历史数据不足，无法预测")
            return {"qps": 0, "cpu": 0, "confidence": 0}

        # 简单的时间序列预测: 取同时段历史均值
        target_time = datetime.utcnow() + timedelta(hours=hours_ahead)
        target_hour = target_time.hour

        same_hour_data = [
            p for p in self._history if p.timestamp.hour == target_hour
        ]

        if not same_hour_data:
            return {"qps": 0, "cpu": 0, "confidence": 0}

        avg_qps = sum(p.qps for p in same_hour_data) / len(same_hour_data)
        avg_cpu = sum(p.cpu_utilization for p in same_hour_data) / len(same_hour_data)

        # 置信度基于数据量
        confidence = min(len(same_hour_data) / 7.0, 1.0)

        return {
            "qps": avg_qps,
            "cpu": avg_cpu,
            "confidence": confidence,
            "target_time": target_time.isoformat(),
        }

    def should_pre_scale(self, hours_ahead: int = 1) -> bool:
        """是否应该提前扩展"""
        prediction = self.predict(hours_ahead)
        if prediction["confidence"] < 0.5:
            return False
        # 预测 CPU > 70% 则提前扩展
        return prediction["cpu"] > 0.70
```

### 12.3 伸缩冷却期

```python
# backend/scalability/cooldown.py
"""伸缩冷却期管理"""
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class CooldownManager:
    """冷却期管理器

    防止频繁伸缩导致的抖动。
    """

    def __init__(
        self,
        scale_up_cooldown: int = 60,    # 扩容冷却 60s
        scale_down_cooldown: int = 300,  # 缩容冷却 300s
    ):
        self.scale_up_cooldown = scale_up_cooldown
        self.scale_down_cooldown = scale_down_cooldown
        self._last_scale_up: float = 0
        self._last_scale_down: float = 0

    def can_scale_up(self) -> bool:
        """是否可以扩容"""
        elapsed = time.time() - self._last_scale_up
        if elapsed < self.scale_up_cooldown:
            logger.debug(
                f"扩容冷却中: 还需 {self.scale_up_cooldown - elapsed:.0f}s"
            )
            return False
        return True

    def can_scale_down(self) -> bool:
        """是否可以缩容"""
        elapsed = time.time() - self._last_scale_down
        if elapsed < self.scale_down_cooldown:
            logger.debug(
                f"缩容冷却中: 还需 {self.scale_down_cooldown - elapsed:.0f}s"
            )
            return False
        return True

    def record_scale_up(self):
        """记录扩容"""
        self._last_scale_up = time.time()

    def record_scale_down(self):
        """记录缩容"""
        self._last_scale_down = time.time()
```

---

## 13. 异步处理扩展

### 13.1 异步处理架构

```
┌─────────────────────────────────────────────────────────────────┐
│  异步处理架构                                                    │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  API 请求                                                  │   │
│  │  ├─ 同步请求 (快速响应) → 立即返回                          │   │
│  │  └─ 异步任务 (耗时操作) → 入队 → 返回任务 ID                │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              ↓                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  消息队列                                                  │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐                   │   │
│  │  │ Topic 1 │  │ Topic 2 │  │ Topic 3 │                   │   │
│  │  │LLM分析  │  │论文解析 │  │导出任务 │                   │   │
│  │  └─────────┘  └─────────┘  └─────────┘                   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              ↓                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Worker 集群 (可水平扩展)                                   │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐                   │   │
│  │  │ Worker  │  │ Worker  │  │ Worker  │                   │   │
│  │  │  #1     │  │  #2     │  │  #N     │                   │   │
│  │  └─────────┘  └─────────┘  └─────────┘                   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              ↓                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  结果存储                                                  │   │
│  │  - 任务状态 (SQLite)                                       │   │
│  │  - 任务结果 (Redis/对象存储)                                │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 13.2 异步任务设计

```python
# backend/scalability/async_task.py
"""异步任务设计"""
import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(int, Enum):
    LOW = 1
    NORMAL = 5
    HIGH = 10
    URGENT = 20


@dataclass
class AsyncTask:
    """异步任务"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    payload: dict = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Any = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout: int = 300  # 秒
    progress: float = 0.0  # 0-1


class AsyncTaskManager:
    """异步任务管理器"""

    def __init__(self, queue, task_store):
        self.queue = queue
        self.store = task_store
        self._handlers: dict = {}

    def register_handler(self, task_type: str, handler: Callable):
        """注册任务处理器"""
        self._handlers[task_type] = handler

    async def submit(
        self,
        task_type: str,
        payload: dict,
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> str:
        """提交异步任务"""
        task = AsyncTask(
            name=task_type,
            payload=payload,
            priority=priority,
        )
        await self.store.save(task)
        await self.queue.enqueue(
            topic=task_type,
            payload={"task_id": task.id, **payload},
        )
        logger.info(f"任务提交: {task_type}/{task.id}")
        return task.id

    async def process(self, task_type: str, worker_id: str):
        """处理任务 (Worker 调用)"""
        message = await self.queue.dequeue(task_type, worker_id)
        if message is None:
            return

        task_id = message["payload"]["task_id"]
        task = await self.store.get(task_id)
        if task is None:
            await self.queue.ack(task_type, message["id"])
            return

        handler = self._handlers.get(task_type)
        if handler is None:
            logger.error(f"无处理器: {task_type}")
            await self.queue.ack(task_type, message["id"])
            return

        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        await self.store.save(task)

        try:
            result = await asyncio.wait_for(
                handler(task.payload),
                timeout=task.timeout,
            )
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            await self.queue.ack(task_type, message["id"])
        except asyncio.TimeoutError:
            task.error = "任务超时"
            task.status = TaskStatus.FAILED
            logger.error(f"任务超时: {task_id}")
        except Exception as e:
            task.error = str(e)
            task.retry_count += 1
            if task.retry_count < task.max_retries:
                task.status = TaskStatus.PENDING
                await self.queue.nack(task_type, message["id"])
            else:
                task.status = TaskStatus.FAILED
                await self.queue.ack(task_type, message["id"])
            logger.error(f"任务失败: {task_id}: {e}")

        await self.store.save(task)

    async def get_status(self, task_id: str) -> Optional[dict]:
        """获取任务状态"""
        task = await self.store.get(task_id)
        if task is None:
            return None
        return {
            "id": task.id,
            "status": task.status.value,
            "progress": task.progress,
            "result": task.result,
            "error": task.error,
            "created_at": task.created_at.isoformat(),
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        }
```

### 13.3 Worker 扩展

```python
# backend/scalability/worker_pool.py
"""Worker 池管理"""
import asyncio
import logging
from typing import List

logger = logging.getLogger(__name__)


class WorkerPool:
    """Worker 池

    每个 Worker 独立消费消息队列，可动态增减。
    """

    def __init__(self, task_manager, topics: List[str], concurrency: int = 4):
        self.task_manager = task_manager
        self.topics = topics
        self.concurrency = concurrency
        self._workers: List[asyncio.Task] = []
        self._running = False

    async def start(self):
        """启动 Worker 池"""
        self._running = True
        for i in range(self.concurrency):
            for topic in self.topics:
                worker = asyncio.create_task(self._worker_loop(topic, f"worker-{i}"))
                self._workers.append(worker)
        logger.info(f"Worker 池启动: {len(self._workers)} 个 worker")

    async def stop(self):
        """停止 Worker 池"""
        self._running = False
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("Worker 池停止")

    async def _worker_loop(self, topic: str, worker_id: str):
        """Worker 循环"""
        while self._running:
            try:
                await self.task_manager.process(topic, worker_id)
                await asyncio.sleep(0.1)  # 避免 CPU 空转
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} 异常: {e}")
                await asyncio.sleep(1)  # 错误后等待

    async def scale(self, target_concurrency: int):
        """调整 Worker 并发数"""
        if target_concurrency > self.concurrency:
            # 扩容
            for i in range(self.concurrency, target_concurrency):
                for topic in self.topics:
                    worker = asyncio.create_task(
                        self._worker_loop(topic, f"worker-{i}")
                    )
                    self._workers.append(worker)
            logger.info(f"Worker 扩容: {self.concurrency} → {target_concurrency}")
        elif target_concurrency < self.concurrency:
            # 缩容
            to_remove = self.concurrency - target_concurrency
            for _ in range(to_remove):
                if self._workers:
                    worker = self._workers.pop()
                    worker.cancel()
            logger.info(f"Worker 缩容: {self.concurrency} → {target_concurrency}")
        self.concurrency = target_concurrency
```

---

## 14. 数据分区策略

### 14.1 数据分区维度

| 分区维度 | 适用数据 | 分区方式 | 示例 |
|---------|---------|---------|------|
| 按用户 | 用户相关数据 | 用户 ID 哈希 | 用户配置、历史记录 |
| 按时间 | 时序数据 | 时间范围 | 日志、访问记录 |
| 按业务 | 业务数据 | 业务类型 | 论文、引用、分析 |
| 按地域 | 地理数据 | 地理位置范围 | 区域统计 |
| 按大小 | 大数据集 | 数据量阈值 | 分批处理 |

### 14.2 数据分区实现

```python
# backend/scalability/data_partitioning.py
"""数据分区策略"""
import logging
from typing import Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class DataPartitioner:
    """数据分区器"""

    def partition_by_user(self, data: list, shard_count: int) -> List[list]:
        """按用户分区"""
        partitions = [[] for _ in range(shard_count)]
        for item in data:
            user_id = item.get("user_id", "")
            shard = hash(user_id) % shard_count
            partitions[shard].append(item)
        return partitions

    def partition_by_time(
        self, data: list, time_field: str, interval_days: int = 30
    ) -> dict:
        """按时间分区"""
        partitions = {}
        for item in data:
            timestamp = item.get(time_field)
            if timestamp is None:
                continue
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            partition_key = timestamp.strftime("%Y%m%d")
            partition_key = str(int(partition_key) // interval_days * interval_days)
            if partition_key not in partitions:
                partitions[partition_key] = []
            partitions[partition_key].append(item)
        return partitions

    def partition_by_size(self, data: list, batch_size: int = 1000) -> List[list]:
        """按大小分区"""
        return [data[i:i + batch_size] for i in range(0, len(data), batch_size)]
```

---

## 15. CDN 与边缘缓存

### 15.1 CDN 缓存策略

| 资源类型 | CDN 缓存 | TTL | 回源条件 |
|---------|---------|-----|---------|
| 静态资源 | 是 | 7 天 | 文件更新 |
| API 响应 | 部分 | 5 分钟 | 缓存过期 |
| 用户数据 | 否 | - | 实时回源 |
| LLM 结果 | 是 | 1 小时 | 缓存过期 |
| 文档 | 是 | 1 天 | 内容更新 |

### 15.2 边缘缓存配置

```yaml
# deploy/cdn/edge-cache.yaml
# Cloudflare / CloudFront 配置示例
rules:
  - name: static-assets
    match: "/static/*"
    cache:
      ttl: 604800  # 7 天
      browser_ttl: 86400  # 1 天

  - name: api-cache
    match: "/api/v1/theses/*"
    methods: ["GET"]
    cache:
      ttl: 300  # 5 分钟
      vary: ["Accept-Language"]

  - name: no-cache
    match: "/api/v1/auth/*"
    cache:
      enabled: false
```

---

## 16. 连接池管理

### 16.1 连接池配置

| 连接类型 | 最小连接 | 最大连接 | 超时 | 空闲回收 |
|---------|---------|---------|------|---------|
| 数据库 | 5 | 20 | 30s | 5 分钟 |
| Redis | 5 | 50 | 5s | 5 分钟 |
| HTTP (LLM) | 2 | 10 | 60s | 10 分钟 |
| HTTP (内部) | 5 | 20 | 10s | 5 分钟 |

### 16.2 连接池监控

```python
# backend/scalability/pool_monitor.py
"""连接池监控"""
import logging
import asyncio
from typing import dict

logger = logging.getLogger(__name__)


class PoolMonitor:
    """连接池监控器"""

    def __init__(self):
        self._pools: dict = {}

    def register(self, name: str, pool):
        """注册连接池"""
        self._pools[name] = pool

    def get_stats(self) -> dict:
        """获取所有连接池统计"""
        stats = {}
        for name, pool in self._pools.items():
            stats[name] = pool.get_stats()
        return stats

    def check_health(self) -> dict:
        """检查连接池健康状态"""
        health = {}
        for name, pool in self._pools.items():
            stats = pool.get_stats()
            utilization = stats.get("active", 0) / max(stats.get("pool_size", 1), 1)
            health[name] = {
                "healthy": utilization < 0.9,
                "utilization": utilization,
                "active": stats.get("active", 0),
                "idle": stats.get("idle", 0),
                "pool_size": stats.get("pool_size", 0),
            }
        return health
```

---

## 17. 请求队列与背压

### 17.1 背压机制

```python
# backend/scalability/backpressure.py
"""背压机制"""
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class BackpressureController:
    """背压控制器

    当系统负载过高时，通过拒绝或延迟请求来保护系统。
    """

    def __init__(
        self,
        max_concurrent: int = 100,
        max_queue_size: int = 200,
        queue_timeout: float = 30.0,
    ):
        self.max_concurrent = max_concurrent
        self.max_queue_size = max_queue_size
        self.queue_timeout = queue_timeout
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._queue_size = 0
        self._queue_lock = asyncio.Lock()

    async def acquire(self) -> bool:
        """获取处理许可

        Returns:
            True: 可以处理
            False: 系统过载，应拒绝请求
        """
        async with self._queue_lock:
            if self._queue_size >= self.max_queue_size:
                logger.warning("系统过载，拒绝请求")
                return False
            self._queue_size += 1

        try:
            await asyncio.wait_for(
                self._semaphore.acquire(),
                timeout=self.queue_timeout,
            )
            return True
        except asyncio.TimeoutError:
            logger.warning("请求排队超时")
            return False
        finally:
            async with self._queue_lock:
                self._queue_size -= 1

    def release(self):
        """释放处理许可"""
        self._semaphore.release()

    def get_stats(self) -> dict:
        """获取统计"""
        return {
            "max_concurrent": self.max_concurrent,
            "current_concurrent": self.max_concurrent - self._semaphore._value,
            "queue_size": self._queue_size,
            "max_queue_size": self.max_queue_size,
        }
```

### 17.2 限流策略

| 限流策略 | 适用场景 | 配置 | 效果 |
|---------|---------|------|------|
| 固定窗口 | 简单限流 | 100 req/min | 窗口边界突发 |
| 滑动窗口 | 平滑限流 | 100 req/min | 平滑过渡 |
| 令牌桶 | 允许突发 | 100 token/min, burst=20 | 突发后恢复 |
| 漏桶 | 严格速率 | 100 req/min | 严格匀速 |

---

## 18. 扩展性测试与基准

### 18.1 扩展性测试类型

| 测试类型 | 目的 | 方法 | 指标 |
|---------|------|------|------|
| 负载测试 | 验证预期负载 | 逐步加压到预期 | QPS/延迟 |
| 压力测试 | 找到系统极限 | 持续加压到崩溃 | 最大 QPS |
| 浸泡测试 | 验证稳定性 | 长时间运行 | 内存泄漏 |
| 扩展测试 | 验证扩展效果 | 增加节点对比 | 扩展效率 |
| 突发测试 | 验证弹性 | 瞬时高负载 | 恢复时间 |

### 18.2 基准测试脚本

```python
# tests/load/benchmark.py
"""扩展性基准测试"""
import asyncio
import time
import logging
import aiohttp
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """基准测试结果"""
    total_requests: int
    successful: int
    failed: int
    duration: float
    qps: float
    avg_latency: float
    p50_latency: float
    p95_latency: float
    p99_latency: float


async def benchmark(
    url: str,
    concurrent: int = 10,
    total_requests: int = 1000,
) -> BenchmarkResult:
    """执行基准测试"""
    semaphore = asyncio.Semaphore(concurrent)
    latencies: List[float] = []
    successful = 0
    failed = 0

    async def single_request(session):
        nonlocal successful, failed
        async with semaphore:
            start = time.perf_counter()
            try:
                async with session.get(url, timeout=30) as response:
                    if response.status == 200:
                        successful += 1
                    else:
                        failed += 1
            except Exception:
                failed += 1
            latencies.append(time.perf_counter() - start)

    start_time = time.perf_counter()
    async with aiohttp.ClientSession() as session:
        tasks = [single_request(session) for _ in range(total_requests)]
        await asyncio.gather(*tasks)
    duration = time.perf_counter() - start_time

    latencies.sort()
    return BenchmarkResult(
        total_requests=total_requests,
        successful=successful,
        failed=failed,
        duration=duration,
        qps=successful / duration if duration > 0 else 0,
        avg_latency=sum(latencies) / len(latencies) if latencies else 0,
        p50_latency=latencies[len(latencies) // 2] if latencies else 0,
        p95_latency=latencies[int(len(latencies) * 0.95)] if latencies else 0,
        p99_latency=latencies[int(len(latencies) * 0.99)] if latencies else 0,
    )


# 扩展性测试: 不同并发下的性能
async def scalability_test(url: str):
    """扩展性测试"""
    results = {}
    for concurrent in [1, 5, 10, 20, 50, 100]:
        result = await benchmark(url, concurrent=concurrent, total_requests=500)
        results[concurrent] = result
        logger.info(
            f"并发 {concurrent}: QPS={result.qps:.1f}, "
            f"P99={result.p99_latency:.3f}s"
        )
    return results
```

### 18.3 扩展效率计算

```
扩展效率 = (扩展后 QPS / 扩展前 QPS) / (扩展后节点数 / 扩展前节点数)

理想值: 1.0 (线性扩展)
可接受: > 0.7
需优化: < 0.5

示例:
- 3 节点: 300 QPS
- 6 节点: 550 QPS
- 扩展效率 = (550/300) / (6/3) = 1.83 / 2 = 0.92 (良好)
```

---

## 19. 扩展性反模式

### 19.1 常见反模式

| 反模式 | 描述 | 后果 | 解决方案 |
|--------|------|------|---------|
| 有状态服务 | 会话存储在本地 | 无法水平扩展 | 状态外置 |
| 共享可变状态 | 多节点共享可变数据 | 数据竞争 | 不可变数据 + CAS |
| 同步扇出 | 同步调用多个下游 | 延迟叠加 | 异步并行 |
| N+1 查询 | 循环中查询数据库 | 数据库压力 | 批量查询 |
| 缓存击穿 | 热点 Key 过期 | 瞬间高负载 | 互斥锁 |
| 连接泄漏 | 连接未释放 | 连接耗尽 | 连接池 + finally |
| 大对象传输 | 传输大量数据 | 带宽/内存压力 | 分页/流式 |
| 阻塞调用 | 异步中阻塞 | 线程耗尽 | 异步 I/O |
| 过度分片 | 分片过细 | 管理开销 | 合理分片数 |
| 忽略背压 | 不限流 | 级联故障 | 限流 + 熔断 |

### 19.2 反模式检测

```python
# backend/scalability/antipattern_detector.py
"""反模式检测器"""
import logging
import time
from typing import List

logger = logging.getLogger(__name__)


class AntiPatternDetector:
    """反模式检测器"""

    def __init__(self):
        self._query_patterns: dict = {}
        self._call_patterns: dict = {}

    def record_query(self, request_id: str, table: str, timestamp: float):
        """记录数据库查询"""
        if request_id not in self._query_patterns:
            self._query_patterns[request_id] = []
        self._query_patterns[request_id].append((table, timestamp))

    def detect_n_plus_1(self) -> List[dict]:
        """检测 N+1 查询"""
        issues = []
        for request_id, queries in self._query_patterns.items():
            table_counts = {}
            for table, _ in queries:
                table_counts[table] = table_counts.get(table, 0) + 1
            for table, count in table_counts.items():
                if count > 5:  # 同一表查询超过 5 次
                    issues.append({
                        "type": "N+1_QUERY",
                        "request_id": request_id,
                        "table": table,
                        "count": count,
                        "severity": "high" if count > 20 else "medium",
                    })
        return issues

    def detect_blocking_call(self, sync_duration: float) -> bool:
        """检测阻塞调用"""
        # 异步上下文中同步操作超过 100ms
        return sync_duration > 0.1
```

---

## 20. 附录

### 20.1 扩展性检查清单

```markdown
## 扩展性检查清单

### 无状态化
- [ ] 会话状态外置到 Redis
- [ ] 文件存储使用对象存储
- [ ] 本地缓存可安全丢失
- [ ] 请求上下文通过 Header 传递

### 水平扩展
- [ ] 应用支持多副本运行
- [ ] 配置 HPA 自动扩缩容
- [ ] 负载均衡配置正确
- [ ] 健康检查配置正确
- [ ] 优雅停机实现

### 数据层
- [ ] 数据库读写分离
- [ ] 分片策略已规划
- [ ] 连接池配置合理
- [ ] 慢查询监控
- [ ] 数据备份策略

### 缓存层
- [ ] 多级缓存配置
- [ ] 缓存预热机制
- [ ] 缓存击穿防护
- [ ] 缓存穿透防护
- [ ] 缓存雪崩防护

### 异步处理
- [ ] 耗时操作异步化
- [ ] 消息队列配置
- [ ] Worker 可水平扩展
- [ ] 任务重试机制
- [ ] 死信队列处理

### 弹性
- [ ] 限流配置
- [ ] 熔断配置
- [ ] 背压机制
- [ ] 降级策略
- [ ] 自动恢复

### 监控
- [ ] 性能指标采集
- [ ] 容量监控
- [ ] 扩展事件告警
- [ ] 瓶颈分析工具
- [ ] 容量规划报告
```

### 20.2 扩展性指标参考

| 指标 | 良好 | 警告 | 危险 |
|------|------|------|------|
| CPU 利用率 | < 60% | 60-80% | > 80% |
| 内存利用率 | < 70% | 70-85% | > 85% |
| 磁盘利用率 | < 60% | 60-80% | > 80% |
| 响应延迟 P99 | < 1s | 1-3s | > 3s |
| 错误率 | < 0.1% | 0.1-1% | > 1% |
| 缓存命中率 | > 90% | 80-90% | < 80% |
| 扩展效率 | > 0.8 | 0.5-0.8 | < 0.5 |
| 连接池利用率 | < 60% | 60-80% | > 80% |

### 20.3 参考文档

| 文档 | 说明 |
|------|------|
| [Kubernetes HPA](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/) | 水平 Pod 自动扩缩容 |
| [Kubernetes VPA](https://github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler) | 垂直 Pod 自动扩缩容 |
| [Redis Cluster](https://redis.io/docs/management/scaling/) | Redis 集群扩展 |
| [SQLite WAL](https://www.sqlite.org/wal.html) | SQLite WAL 模式 |
| [The USE Method](https://brendangregg.com/usemethod.html) | USE 方法论 |
| [Backpressure](https://www.reactivemanifesto.org/glossary#Back-Pressure) | 背压机制 |

### 20.4 变更记录

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|---------|------|
| v8.0.0 | 2026-06-20 | 初始版本 | ThesisMiner Team |

---

**文档结束**
