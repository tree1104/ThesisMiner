# ThesisMiner v8.0 灾备设计文档

> **文档版本**：v8.0.0
> **最后更新**：2026-06-20
> **文档负责**：ThesisMiner SRE & Architecture Team
> **审阅状态**：Approved
> **适用范围**：ThesisMiner v8.0 全部生产环境、预发环境与灾备环境
> **机密级别**：内部机密（Confidential）

---

## 目录

- [1. 概述](#1-概述)
  - [1.1 文档目的](#11-文档目的)
  - [1.2 业务背景](#12-业务背景)
  - [1.3 灾备定义](#13-灾备定义)
  - [1.4 设计原则](#14-设计原则)
  - [1.5 术语表](#15-术语表)
- [2. RPO/RTO 目标](#2-rporto-目标)
  - [2.1 指标定义](#21-指标定义)
  - [2.2 ThesisMiner v8.0 目标](#22-thesisminer-v80-目标)
  - [2.3 业务影响分析](#23-业务影响分析)
  - [2.4 成本权衡](#24-成本权衡)
- [3. 灾备策略](#3-灾备策略)
  - [3.1 灾备架构模式](#31-灾备架构模式)
  - [3.2 ThesisMiner v8.0 灾备架构](#32-thesisminer-v80-灾备架构)
  - [3.3 多活架构设计](#33-多活架构设计)
  - [3.4 灾备站点选择](#34-灾备站点选择)
- [4. 数据备份设计](#4-数据备份设计)
  - [4.1 备份策略](#41-备份策略)
  - [4.2 全量备份](#42-全量备份)
  - [4.3 增量备份](#43-增量备份)
  - [4.4 差异备份](#44-差异备份)
  - [4.5 备份验证](#45-备份验证)
  - [4.6 备份加密](#46-备份加密)
  - [4.7 备份存储与归档](#47-备份存储与归档)
  - [4.8 备份监控与告警](#48-备份监控与告警)
- [5. 故障切换设计](#5-故障切换设计)
  - [5.1 故障检测](#51-故障检测)
  - [5.2 故障切换流程](#52-故障切换流程)
  - [5.3 故障回切](#53-故障回切)
  - [5.4 数据一致性保障](#54-数据一致性保障)
  - [5.5 流量切换](#55-流量切换)
- [6. 数据恢复设计](#6-数据恢复设计)
  - [6.1 恢复场景](#61-恢复场景)
  - [6.2 时间点恢复](#62-时间点恢复)
  - [6.3 跨区域恢复](#63-跨区域恢复)
  - [6.4 恢复验证](#64-恢复验证)
  - [6.5 恢复演练](#65-恢复演练)
- [7. 灾备演练](#7-灾备演练)
  - [7.1 演练分类](#71-演练分类)
  - [7.2 桌面演练](#72-桌面演练)
  - [7.3 半实战演练](#73-半实战演练)
  - [7.4 全实战演练](#74-全实战演练)
  - [7.5 混沌工程](#75-混沌工程)
  - [7.6 演练报告](#76-演练报告)
- [8. 灾备预案](#8-灾备预案)
  - [8.1 预案体系](#81-预案体系)
  - [8.2 数据库故障预案](#82-数据库故障预案)
  - [8.3 应用故障预案](#83-应用故障预案)
  - [8.4 网络故障预案](#84-网络故障预案)
  - [8.5 区域级故障预案](#85-区域级故障预案)
  - [8.6 第三方服务故障预案](#86-第三方服务故障预案)
- [9. 业务连续性计划（BCP）](#9-业务连续性计划bcp)
  - [9.1 BCP 概述](#91-bcp-概述)
  - [9.2 业务影响分析（BIA）](#92-业务影响分析bia)
  - [9.3 连续性策略](#93-连续性策略)
  - [9.4 应急响应组织](#94-应急响应组织)
  - [9.5 沟通计划](#95-沟通计划)
- [10. 灾难恢复计划（DRP）](#10-灾难恢复计划drp)
  - [10.1 DRP 概述](#101-drp-概述)
  - [10.2 恢复优先级](#102-恢复优先级)
  - [10.3 恢复步骤](#103-恢复步骤)
  - [10.4 DRP 文档维护](#104-drp-文档维护)
- [11. 灾备案例研究](#11-灾备案例研究)
  - [11.1 案例一：数据库故障切换](#111-案例一数据库故障切换)
  - [11.2 案例二：区域级故障](#112-案例二区域级故障)
  - [11.3 案例三：勒索软件攻击](#113-案例三勒索软件攻击)
  - [11.4 案例四：人为误操作](#114-案例四人为误操作)
  - [11.5 经验教训汇总](#115-经验教训汇总)
- [12. 实施与运维](#12-实施与运维)
  - [12.1 实施路线图](#121-实施路线图)
  - [12.2 运维流程](#122-运维流程)
  - [12.3 成本管理](#123-成本管理)
  - [12.4 合规与审计](#124-合规与审计)
- [13. 附录](#13-附录)
  - [13.1 配置示例](#131-配置示例)
  - [13.2 检查清单](#132-检查清单)
  - [13.3 故障排查](#133-故障排查)
  - [13.4 变更记录](#134-变更记录)

---

## 1. 概述

### 1.1 文档目的

本文档定义 ThesisMiner v8.0 系统的灾难恢复（Disaster Recovery, DR）与业务连续性（Business Continuity, BC）设计规范，覆盖 RPO/RTO 目标、灾备策略、数据备份、故障切换、数据恢复、灾备演练、灾备预案、BCP/DRP、案例研究等主题。文档面向以下读者：

- **SRE 与运维工程师**：负责灾备基础设施部署、演练、故障切换
- **后端开发工程师**：负责在 ThesisMiner 各模块（`backend/agents`、`backend/sessions`、`backend/orchestration`、`backend/ai`、`backend/analytics`、`backend/ml`、`backend/export`、`backend/knowledge`、`backend/validation`、`backend/routing`、`backend/integrity`、`backend/optimization`、`backend/nlp`、`backend/monitoring`、`backend/planning`、`backend/reasoning` 等）中实现数据持久化与恢复逻辑
- **DBA**：负责 SQLite 数据库备份、恢复、一致性校验
- **架构师**：评审灾备架构的合理性、RPO/RTO 是否满足业务要求
- **安全工程师**：负责备份加密、访问控制、合规审计
- **管理层**：了解业务连续性保障能力，做出投资决策

文档目标是让任何一名工程师在阅读后能够：

1. 理解 ThesisMiner v8.0 灾备整体架构
2. 知道在不同故障场景下如何执行恢复
3. 能够参与灾备演练并撰写演练报告
4. 能够基于 BCP/DRP 框架制定部门级预案
5. 能够从历史案例中汲取经验，避免重蹈覆辙

### 1.2 业务背景

ThesisMiner v8.0 是面向研究生开题全生命周期的智能导航系统，核心能力包括：

- **Multi-Agent 架构**：Orchestrator + 5 sub-agents（Searcher、Reasoner、Critic、Mentor、Writer）
- **五阶段闭环导航**：Topic Clarification → Literature Mapping → Method Design → Writing → Refinement
- **三段式 Prompt 缓存**：System Prompt、Session Context、User Query 三段缓存，降低 DeepSeek API 成本
- **多会话上下文隔离**：支持多用户并发，会话间数据严格隔离
- **D3.js v7 力导向谱系图**：可视化导师项目谱系
- **SQLite + WAL 模式**：轻量级持久化，支持高并发读
- **FastAPI 后端**：高性能异步 API

业务关键性：

- 用户依赖 ThesisMiner 完成开题报告，数据丢失将导致用户数周工作付诸东流
- 系统不可用将直接影响研究生开题进度，影响学术周期
- 用户论文内容属于敏感学术数据，泄露将造成严重声誉损失

因此，ThesisMiner v8.0 必须具备：

- **数据零丢失**：用户论文、会话、生成结果必须可靠持久化
- **快速恢复**：故障后能在分钟级恢复服务
- **跨区域容灾**：单区域故障不影响全局服务
- **备份可验证**：备份数据必须可恢复、可验证

### 1.3 灾备定义

灾难恢复（Disaster Recovery, DR）指在系统遭受灾难性故障（如自然灾害、硬件故障、网络中断、人为误操作、恶意攻击）后，恢复业务服务的能力。

灾难恢复与高可用（High Availability, HA）的区别：

```
+-------------------+        +-------------------+
| 高可用 HA         |        | 灾备 DR           |
| - 单点故障消除     |        | - 区域级故障恢复   |
| - 自动故障转移     |        | - 数据备份与恢复   |
| - 秒级切换         |        | - 分钟到小时级恢复 |
| - 同机房冗余       |        | - 跨机房/跨区域    |
+-------------------+        +-------------------+
        |                              |
        v                              v
   "一台机器挂了"              "整个机房挂了"
   "自动切到备机"              "切到异地灾备中心"
```

ThesisMiner v8.0 同时需要 HA 与 DR：

- **HA**：Pod 多副本、SQLite 主从、负载均衡
- **DR**：跨区域备份、异地灾备、数据恢复

### 1.4 设计原则

ThesisMiner v8.0 灾备设计遵循以下八项原则：

| 编号 | 原则 | 说明 |
|------|------|------|
| P1 | **数据优先** | 数据备份是灾备核心，宁可服务不可用也不能丢数据 |
| P2 | **RPO/RTO 驱动** | 所有设计围绕 RPO/RTO 目标，避免过度设计或不足 |
| P3 | **自动化优先** | 备份、切换、恢复尽量自动化，减少人为错误 |
| P4 | **演练常态化** | 灾备方案必须定期演练，未演练的预案等于没有 |
| P5 | **降级可用** | 灾备切换后可降级服务，优先恢复核心功能 |
| P6 | **安全合规** | 备份数据加密、访问审计、合规留存 |
| P7 | **成本可控** | 灾备资源按需使用，避免闲置浪费 |
| P8 | **持续演进** | 灾备方案随业务演进，定期评审与更新 |

### 1.5 术语表

| 术语 | 英文 | 说明 |
|------|------|------|
| RPO | Recovery Point Objective | 恢复点目标，可容忍的数据丢失量 |
| RTO | Recovery Time Objective | 恢复时间目标，可容忍的服务中断时长 |
| DR | Disaster Recovery | 灾难恢复 |
| BCP | Business Continuity Plan | 业务连续性计划 |
| DRP | Disaster Recovery Plan | 灾难恢复计划 |
| BIA | Business Impact Analysis | 业务影响分析 |
| HA | High Availability | 高可用 |
| FT | Fault Tolerance | 容错 |
| Hot Standby | Hot Standby | 热备 |
| Warm Standby | Warm Standby | 温备 |
| Cold Standby | Cold Standby | 冷备 |
| Active-Active | Active-Active | 双活 |
| Active-Passive | Active-Passive | 主备 |
| PITR | Point-in-Time Recovery | 时间点恢复 |
| WAL | Write-Ahead Logging | 预写日志 |
| WORM | Write Once Read Many | 一次写入多次读取 |

---

## 2. RPO/RTO 目标

### 2.1 指标定义

#### 2.1.1 RPO（Recovery Point Objective）

RPO 指灾难发生后可容忍的数据丢失量，以时间衡量。

```
时间轴：
  T0          T1          T2          T3
  |           |           |           |
  v           v           v           v
  最后备份    故障发生    恢复开始    恢复完成
              |                       |
              |<----- RPO ----------->|
              |<----- RTO --------------------------->|
```

- RPO = 0：零数据丢失（同步复制）
- RPO = 5 分钟：最多丢失 5 分钟数据（异步复制，5 分钟延迟）
- RPO = 1 小时：最多丢失 1 小时数据（每小时备份）

#### 2.1.2 RTO（Recovery Time Objective）

RTO 指灾难发生后可容忍的服务中断时长，从故障发生到服务恢复。

- RTO = 0：零中断（双活，自动切换）
- RTO = 15 分钟：15 分钟内恢复（热备，自动切换）
- RTO = 4 小时：4 小时内恢复（温备，手动切换）
- RTO = 24 小时：24 小时内恢复（冷备，重建）

### 2.2 ThesisMiner v8.0 目标

ThesisMiner v8.0 按业务关键性分级制定 RPO/RTO 目标：

| 业务等级 | 业务功能 | RPO | RTO | 策略 |
|----------|----------|-----|-----|------|
| L1 核心 | 论文生成、会话管理 | 0 | 15 分钟 | 同城双活 |
| L1 核心 | 用户数据、论文存储 | 0 | 15 分钟 | 同步复制 + 异地备份 |
| L2 重要 | 导出功能（PDF/DOCX） | 5 分钟 | 1 小时 | 异步复制 |
| L2 重要 | 谱系图可视化 | 5 分钟 | 1 小时 | 异步复制 |
| L3 一般 | 分析报表、监控 | 1 小时 | 4 小时 | 定时备份 |
| L3 一般 | 日志、审计 | 1 小时 | 4 小时 | 定时备份 |

#### 2.2.1 L1 核心业务目标

- **论文生成**：用户提交的论文生成请求与生成结果必须零丢失
- **会话管理**：用户会话状态（五阶段进度、上下文）必须零丢失
- **RPO = 0**：通过同步复制实现
- **RTO = 15 分钟**：通过同城双活 + 自动切换实现

#### 2.2.2 L2 重要业务目标

- **导出功能**：论文导出任务可容忍少量丢失（用户可重新触发）
- **谱系图**：可视化数据可容忍短时间不一致
- **RPO = 5 分钟**：通过异步复制实现
- **RTO = 1 小时**：通过热备 + 手动切换实现

#### 2.2.3 L3 一般业务目标

- **分析报表**：可容忍较长中断，不影响核心业务
- **日志审计**：可容忍较长中断，但需保证最终一致
- **RPO = 1 小时**：通过定时备份实现
- **RTO = 4 小时**：通过冷备 + 重建实现

### 2.3 业务影响分析

#### 2.3.1 停机成本

| 停机时长 | 业务影响 | 估算损失 |
|----------|----------|----------|
| 15 分钟 | 约 25 篇论文生成延迟 | $500 |
| 1 小时 | 约 100 篇论文生成延迟，用户投诉 | $2,000 |
| 4 小时 | 约 400 篇论文生成延迟，用户流失 | $10,000 |
| 24 小时 | 大规模用户流失，声誉受损 | $50,000+ |

#### 2.3.2 数据丢失影响

| 数据丢失量 | 业务影响 | 估算损失 |
|------------|----------|----------|
| 0 | 无影响 | $0 |
| 5 分钟 | 少量用户需重新提交 | $200 |
| 1 小时 | 部分用户工作丢失，投诉 | $2,000 |
| 1 天 | 大量用户工作丢失，信任危机 | $20,000+ |

### 2.4 成本权衡

灾备建设成本与业务收益权衡：

| 方案 | RPO | RTO | 年成本 | 适用场景 |
|------|-----|-----|--------|----------|
| 冷备 | 24 小时 | 24 小时 | $5,000 | L3 业务 |
| 温备 | 1 小时 | 4 小时 | $15,000 | L3 业务 |
| 热备 | 5 分钟 | 1 小时 | $40,000 | L2 业务 |
| 同城双活 | 0 | 15 分钟 | $100,000 | L1 业务 |
| 两地三中心 | 0 | 5 分钟 | $200,000 | L1 关键业务 |

ThesisMiner v8.0 选择：**L1 同城双活 + L2 热备 + L3 温备**，年成本约 $120,000。

---

## 3. 灾备策略

### 3.1 灾备架构模式

#### 3.1.1 主备模式（Active-Passive）

```
+-------------------+        +-------------------+
| 主中心 (Active)   |  复制  | 备中心 (Passive)  |
| - 处理全部流量     | -----> | - 待命，不处理流量 |
| - 读写             |        | - 只读或待机       |
+-------------------+        +-------------------+
```

- 优点：简单、成本低
- 缺点：备中心资源闲置，切换有延迟

#### 3.1.2 双活模式（Active-Active）

```
+-------------------+        +-------------------+
| 中心 A (Active)   | 双向   | 中心 B (Active)   |
| - 处理 50% 流量    | 复制   | - 处理 50% 流量    |
| - 读写             | <----> | - 读写             |
+-------------------+        +-------------------+
```

- 优点：资源充分利用、切换快
- 缺点：复杂、数据一致性挑战

#### 3.1.3 多活模式（Multi-Active）

```
+-------------------+
| 中心 A (Active)   | ---+
+-------------------+    |
                         v
+-------------------+    +-------------------+
| 中心 B (Active)   | <->| 全局协调          |
+-------------------+    +-------------------+
                         ^
+-------------------+    |
| 中心 C (Active)   | ---+
+-------------------+
```

- 优点：极高可用、就近访问
- 缺点：极复杂、冲突解决难

#### 3.1.4 两地三中心

```
+-------------------+        +-------------------+
| 同城中心 A        | 同步   | 同城中心 B        |
| (Active)          | 复制   | (Active)          |
+-------------------+        +-------------------+
         |                            |
         |       异步复制              |
         +----------------------------+
                                      |
                                      v
                          +-------------------+
                          | 异地中心 C        |
                          | (Standby)         |
                          +-------------------+
```

- 优点：兼顾同城高可用与异地灾备
- 缺点：成本高

### 3.2 ThesisMiner v8.0 灾备架构

ThesisMiner v8.0 采用 **同城双活 + 异地温备** 架构：

```
+======================================================================+
|                    同城（北京，可用区 A + B）                          |
|                                                                      |
|  +-------------------+              +-------------------+            |
|  | 可用区 A          |   同步复制    | 可用区 B          |            |
|  | - ThesisMiner App | <=========>  | - ThesisMiner App |            |
|  | - SQLite Primary  |              | - SQLite Replica  |            |
|  | - Redis Primary   |              | - Redis Replica   |            |
|  | - 对象存储 A      |              | - 对象存储 B      |            |
|  +-------------------+              +-------------------+            |
|          |                                  |                        |
|          +----------- 全局负载均衡 -----------+                        |
|                          |                                           |
+======================================================================+
                           |
                      异步复制（5 分钟延迟）
                           |
+======================================================================+
|                    异地（上海，可用区 C）                              |
|                                                                      |
|  +-------------------+                                              |
|  | 可用区 C          |                                              |
|  | - ThesisMiner App |  (待命，平时不接流量)                          |
|  | - SQLite Replica  |                                              |
|  | - Redis Replica   |                                              |
|  | - 对象存储 C      |                                              |
|  +-------------------+                                              |
|                                                                      |
+======================================================================+
```

#### 3.2.1 同城双活设计

- **应用层**：可用区 A、B 各部署 N 个 Pod，通过全局负载均衡分流
- **数据库层**：SQLite 主从复制，主在 A，从在 B，同步复制
- **缓存层**：Redis 主从复制，主在 A，从在 B，异步复制
- **对象存储**：可用区 A、B 各一份，跨可用区同步
- **故障切换**：可用区 A 故障时，B 自动接管，RTO < 5 分钟

#### 3.2.2 异地温备设计

- **应用层**：可用区 C 部署最小规模 Pod（平时不接流量）
- **数据库层**：SQLite 异步复制，5 分钟延迟
- **缓存层**：Redis 异步复制
- **对象存储**：跨区域复制
- **故障切换**：同城两可用区都故障时，C 接管，RTO < 30 分钟

### 3.3 多活架构设计

#### 3.3.1 数据一致性

多活架构核心挑战是数据一致性。ThesisMiner v8.0 采用 **最终一致性 + 冲突解决** 策略：

- **强一致数据**（用户、论文、会话）：同步复制，主写从读
- **最终一致数据**（缓存、索引）：异步复制，容忍短时间不一致
- **冲突解决**：基于时间戳 + 业务规则

#### 3.3.2 流量路由

```
用户请求 --> 全局 DNS / Anycast
                |
                +--> 健康检查
                |
                +--> 就近路由
                |
                v
            可用区 A / B / C
```

路由策略：

1. **就近优先**：用户请求路由到最近的可用区
2. **健康检查**：可用区故障时自动剔除
3. **容量感知**：根据可用区容量动态分流
4. **会话保持**：同一会话路由到同一可用区（避免跨区数据同步）

#### 3.3.3 会话保持

ThesisMiner v8.0 多会话场景下，会话保持至关重要：

- 同一 `session_id` 的请求必须路由到同一可用区
- 通过 Sticky Session 或会话路由表实现
- 跨可用区切换时，会话数据必须已同步

### 3.4 灾备站点选择

#### 3.4.1 选址原则

- **地理距离**：同城站点距离 > 30km，异地站点距离 > 1000km
- **自然灾害**：避开地震带、洪水区、台风区
- **网络质量**：站点间网络延迟 < 5ms（同城），< 30ms（异地）
- **电力供应**：双路市电 + UPS + 柴油发电机
- **合规要求**：数据不出境（如中国数据存中国）

#### 3.4.2 ThesisMiner v8.0 选址

- **主中心**：北京（可用区 A）
- **同城备中心**：北京（可用区 B），距 A 约 50km
- **异地备中心**：上海（可用区 C），距北京约 1200km

---

## 4. 数据备份设计

### 4.1 备份策略

ThesisMiner v8.0 采用 **3-2-1 备份策略**：

- **3** 份数据副本
- **2** 种不同存储介质（SSD + 对象存储）
- **1** 份离线/异地备份

#### 4.1.1 备份类型组合

| 数据类型 | 全量备份 | 增量备份 | 差异备份 | WAL 归档 |
|----------|----------|----------|----------|----------|
| SQLite 数据库 | 每周 | 每小时 | 每天 | 实时 |
| 用户论文 | 每天 | 每 15 分钟 | - | - |
| 会话数据 | 每天 | 每 5 分钟 | - | - |
| 配置文件 | 每次变更 | - | - | - |
| 日志 | 每天 | - | - | - |
| 代码 | 每次发布 | - | - | Git |

#### 4.1.2 备份保留策略

| 备份类型 | 保留期 | 存储介质 | 加密 |
|----------|--------|----------|------|
| 实时 WAL | 7 天 | SSD | 是 |
| 每小时增量 | 30 天 | SSD + 对象存储 | 是 |
| 每天差异 | 90 天 | 对象存储 | 是 |
| 每周全量 | 365 天 | 对象存储 + 磁带 | 是 |
| 每月归档 | 2555 天（7 年） | 磁带 + 异地 | 是 |

### 4.2 全量备份

#### 4.2.1 SQLite 全量备份

SQLite 全量备份使用 `VACUUM INTO` 或 `.backup` 命令：

```bash
#!/bin/bash
# scripts/backup/sqlite_full_backup.sh

set -euo pipefail

BACKUP_DIR="/data/backups/sqlite/full"
DB_PATH="/data/thesisminer/thesisminer.db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/thesisminer_full_${TIMESTAMP}.db"

mkdir -p "${BACKUP_DIR}"

# 使用 sqlite3 .backup 命令（在线备份，不阻塞写入）
sqlite3 "${DB_PATH}" ".backup '${BACKUP_FILE}'"

# 验证备份完整性
sqlite3 "${BACKUP_FILE}" "PRAGMA integrity_check;"

# 压缩
gzip "${BACKUP_FILE}"

# 计算哈希
sha256sum "${BACKUP_FILE}.gz" > "${BACKUP_FILE}.gz.sha256"

# 加密
gpg --batch --yes --passphrase-file /etc/thesisminer/backup_key \
    --symmetric --cipher-algo AES256 \
    "${BACKUP_FILE}.gz"

# 删除未加密文件
rm "${BACKUP_FILE}.gz" "${BACKUP_FILE}.gz.sha256"

echo "Full backup completed: ${BACKUP_FILE}.gz.gpg"
```

#### 4.2.2 应用数据全量备份

```python
# backend/monitoring/backup.py
import os
import shutil
import tarfile
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional


class FullBackup:
    """全量备份器。"""

    def __init__(self, source_dir: str, backup_dir: str,
                 encryption_key: Optional[str] = None):
        self.source_dir = Path(source_dir)
        self.backup_dir = Path(backup_dir)
        self.encryption_key = encryption_key

    def backup(self) -> Path:
        """执行全量备份。"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"full_{timestamp}.tar.gz"

        # 创建压缩包
        with tarfile.open(backup_file, "w:gz") as tar:
            tar.add(self.source_dir, arcname=".")

        # 计算哈希
        sha256 = self._calculate_sha256(backup_file)
        hash_file = backup_file.with_suffix(".sha256")
        hash_file.write_text(f"{sha256}  {backup_file.name}\n")

        # 加密
        if self.encryption_key:
            encrypted_file = self._encrypt(backup_file, self.encryption_key)
            backup_file.unlink()
            backup_file = encrypted_file

        return backup_file

    def _calculate_sha256(self, file_path: Path) -> str:
        """计算文件 SHA256。"""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _encrypt(self, file_path: Path, key: str) -> Path:
        """AES256 加密文件。"""
        encrypted_path = file_path.with_suffix(file_path.suffix + ".enc")
        # 实际实现使用 cryptography 库
        os.system(
            f"gpg --batch --yes --passphrase '{key}' "
            f"--symmetric --cipher-algo AES256 "
            f"--output {encrypted_path} {file_path}"
        )
        return encrypted_path
```

### 4.3 增量备份

#### 4.3.1 SQLite 增量备份（WAL 归档）

SQLite WAL 模式下，WAL 文件记录所有变更。归档 WAL 实现增量备份：

```bash
#!/bin/bash
# scripts/backup/sqlite_wal_archive.sh

set -euo pipefail

DB_PATH="/data/thesisminer/thesisminer.db"
WAL_PATH="${DB_PATH}-wal"
ARCHIVE_DIR="/data/backups/sqlite/wal"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "${ARCHIVE_DIR}"

# 检查 WAL 文件是否存在
if [ ! -f "${WAL_PATH}" ]; then
    echo "No WAL file, skipping archive"
    exit 0
fi

# 复制 WAL 文件（不阻塞写入）
cp "${WAL_PATH}" "${ARCHIVE_DIR}/wal_${TIMESTAMP}.wal"

# 触发 checkpoint，将 WAL 写入主库
sqlite3 "${DB_PATH}" "PRAGMA wal_checkpoint(TRUNCATE);"

# 计算哈希
sha256sum "${ARCHIVE_DIR}/wal_${TIMESTAMP}.wal" > "${ARCHIVE_DIR}/wal_${TIMESTAMP}.sha256"

# 加密
gpg --batch --yes --passphrase-file /etc/thesisminer/backup_key \
    --symmetric --cipher-algo AES256 \
    "${ARCHIVE_DIR}/wal_${TIMESTAMP}.wal"

rm "${ARCHIVE_DIR}/wal_${TIMESTAMP}.wal" "${ARCHIVE_DIR}/wal_${TIMESTAMP}.sha256"

echo "WAL archive completed: wal_${TIMESTAMP}.wal.gpg"
```

#### 4.3.2 文件级增量备份

基于 `rsync --link-dest` 实现硬链接增量备份：

```bash
#!/bin/bash
# scripts/backup/file_incremental.sh

set -euo pipefail

SOURCE="/data/thesisminer/uploads"
BACKUP_DIR="/data/backups/files"
DATE=$(date +%Y%m%d)
YESTERDAY=$(date -d "yesterday" +%Y%m%d)
TIMESTAMP=$(date +%H%M%S)

CURRENT_BACKUP="${BACKUP_DIR}/${DATE}_${TIMESTAMP}"
LATEST_LINK="${BACKUP_DIR}/latest"

mkdir -p "${BACKUP_DIR}"

# 使用硬链接增量备份
rsync -a --link-dest="${LATEST_LINK}" "${SOURCE}/" "${CURRENT_BACKUP}/"

# 更新 latest 链接
rm -f "${LATEST_LINK}"
ln -s "${CURRENT_BACKUP}" "${LATEST_LINK}"

echo "Incremental backup completed: ${CURRENT_BACKUP}"
```

### 4.4 差异备份

差异备份备份自上次全量备份以来的所有变更：

```bash
#!/bin/bash
# scripts/backup/sqlite_diff_backup.sh

set -euo pipefail

DB_PATH="/data/thesisminer/thesisminer.db"
BACKUP_DIR="/data/backups/sqlite/diff"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# 找到最近的全量备份
LATEST_FULL=$(ls -t "${BACKUP_DIR}/../full/"*.db.gpg 2>/dev/null | head -1)
if [ -z "${LATEST_FULL}" ]; then
    echo "No full backup found, run full backup first"
    exit 1
fi

# 解密全量备份
gpg --batch --yes --passphrase-file /etc/thesisminer/backup_key \
    --decrypt "${LATEST_FULL}" > /tmp/full_backup.db

# 使用 rsync 计算差异
# SQLite 差异备份通过 dump + diff 实现
sqlite3 /tmp/full_backup.db ".dump" > /tmp/full_dump.sql
sqlite3 "${DB_PATH}" ".dump" > /tmp/current_dump.sql

diff /tmp/full_dump.sql /tmp/current_dump.sql > "${BACKUP_DIR}/diff_${TIMESTAMP}.sql"

# 压缩加密
gzip "${BACKUP_DIR}/diff_${TIMESTAMP}.sql"
gpg --batch --yes --passphrase-file /etc/thesisminer/backup_key \
    --symmetric --cipher-algo AES256 \
    "${BACKUP_DIR}/diff_${TIMESTAMP}.sql.gz"

rm /tmp/full_backup.db /tmp/full_dump.sql /tmp/current_dump.sql \
   "${BACKUP_DIR}/diff_${TIMESTAMP}.sql.gz"

echo "Diff backup completed: diff_${TIMESTAMP}.sql.gz.gpg"
```

### 4.5 备份验证

#### 4.5.1 验证策略

备份不验证等于没有备份。ThesisMiner v8.0 强制备份验证：

| 验证类型 | 频率 | 验证内容 |
|----------|------|----------|
| 完整性验证 | 每次备份 | 文件哈希、数据库 integrity_check |
| 可恢复验证 | 每天 | 恢复到测试环境，验证可读 |
| 数据一致性验证 | 每周 | 恢复后跑业务校验脚本 |
| 跨区域验证 | 每月 | 异地恢复，验证网络与数据 |

#### 4.5.2 验证脚本

```python
# scripts/backup/verify_backup.py
import subprocess
import sqlite3
import hashlib
import tempfile
import os
from pathlib import Path
from typing import Optional


class BackupVerifier:
    """备份验证器。"""

    def __init__(self, backup_file: str, encryption_key: Optional[str] = None):
        self.backup_file = Path(backup_file)
        self.encryption_key = encryption_key

    def verify(self) -> bool:
        """执行完整验证。"""
        try:
            # 1. 验证文件存在
            if not self.backup_file.exists():
                raise FileNotFoundError(f"Backup file not found: {self.backup_file}")

            # 2. 验证哈希
            if not self._verify_hash():
                raise ValueError("Hash verification failed")

            # 3. 解密
            decrypted_file = self._decrypt()

            # 4. 解压
            extracted_file = self._extract(decrypted_file)

            # 5. 验证数据库完整性
            if extracted_file.suffix == ".db":
                if not self._verify_sqlite(extracted_file):
                    raise ValueError("SQLite integrity check failed")

            # 6. 验证可读性
            if not self._verify_readable(extracted_file):
                raise ValueError("Backup is not readable")

            print(f"Backup verification PASSED: {self.backup_file}")
            return True

        except Exception as e:
            print(f"Backup verification FAILED: {self.backup_file}, error: {e}")
            return False

    def _verify_hash(self) -> bool:
        """验证文件哈希。"""
        hash_file = self.backup_file.with_suffix(self.backup_file.suffix + ".sha256")
        if not hash_file.exists():
            print("No hash file, skipping hash verification")
            return True

        expected_hash = hash_file.read_text().split()[0]
        actual_hash = hashlib.sha256(self.backup_file.read_bytes()).hexdigest()
        return expected_hash == actual_hash

    def _decrypt(self) -> Path:
        """解密备份文件。"""
        if not self.encryption_key:
            return self.backup_file

        decrypted = self.backup_file.with_suffix("")
        subprocess.run([
            "gpg", "--batch", "--yes",
            "--passphrase", self.encryption_key,
            "--decrypt", "--output", str(decrypted),
            str(self.backup_file)
        ], check=True)
        return decrypted

    def _extract(self, file_path: Path) -> Path:
        """解压备份文件。"""
        if file_path.suffix == ".gz":
            extracted = file_path.with_suffix("")
            subprocess.run(["gunzip", str(file_path)], check=True)
            return extracted
        return file_path

    def _verify_sqlite(self, db_file: Path) -> bool:
        """验证 SQLite 数据库完整性。"""
        conn = sqlite3.connect(str(db_file))
        try:
            cursor = conn.execute("PRAGMA integrity_check;")
            result = cursor.fetchone()
            return result[0] == "ok"
        finally:
            conn.close()

    def _verify_readable(self, file_path: Path) -> bool:
        """验证文件可读。"""
        return os.access(file_path, os.R_OK)


if __name__ == "__main__":
    verifier = BackupVerifier(
        "/data/backups/sqlite/full/thesisminer_full_20260620_000000.db.gz.gpg",
        encryption_key=os.environ.get("BACKUP_KEY")
    )
    exit(0 if verifier.verify() else 1)
```

### 4.6 备份加密

#### 4.6.1 加密策略

- **算法**：AES-256
- **密钥管理**：HashiCorp Vault 或 AWS KMS
- **密钥轮换**：每 90 天轮换一次
- **密钥分离**：加密密钥与备份数据分离存储

#### 4.6.2 加密实现

```python
# backend/monitoring/backup_crypto.py
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import base64
import hashlib


class BackupEncryptor:
    """备份加密器。"""

    def __init__(self, key_derivation_password: str, salt: bytes = None):
        self.salt = salt or os.urandom(16)
        self._key = self._derive_key(key_derivation_password, self.salt)

    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """PBKDF2 派生密钥。"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        return kdf.derive(password.encode())

    def encrypt_file(self, input_path: str, output_path: str) -> str:
        """AES-256-GCM 加密文件。"""
        # 生成 IV
        iv = os.urandom(12)

        # 读取文件
        with open(input_path, "rb") as f:
            plaintext = f.read()

        # 加密
        cipher = Cipher(
            algorithms.AES(self._key),
            modes.GCM(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(plaintext) + encryptor.finalize()

        # 写入文件：salt(16) + iv(12) + tag(16) + ciphertext
        with open(output_path, "wb") as f:
            f.write(self.salt)
            f.write(iv)
            f.write(encryptor.tag)
            f.write(ciphertext)

        return output_path

    def decrypt_file(self, input_path: str, output_path: str,
                     password: str) -> str:
        """AES-256-GCM 解密文件。"""
        with open(input_path, "rb") as f:
            data = f.read()

        # 解析：salt(16) + iv(12) + tag(16) + ciphertext
        salt = data[:16]
        iv = data[16:28]
        tag = data[28:44]
        ciphertext = data[44:]

        # 派生密钥
        key = self._derive_key(password, salt)

        # 解密
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(iv, tag),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()

        with open(output_path, "wb") as f:
            f.write(plaintext)

        return output_path
```

### 4.7 备份存储与归档

#### 4.7.1 存储分层

```
+-------------------+     +-------------------+     +-------------------+
| 热存储 (Hot)      | --> | 温存储 (Warm)     | --> | 冷存储 (Cold)     |
| - SSD             |     | - 对象存储        |     | - 磁带 / 归档     |
| - 0-7 天          |     | - 7-90 天         |     | - 90-2555 天      |
| - 快速恢复        |     | - 分钟级恢复      |     | - 小时级恢复      |
| - 高成本          |     | - 中成本          |     | - 低成本          |
+-------------------+     +-------------------+     +-------------------+
```

#### 4.7.2 对象存储配置

```yaml
# deploy/backup/object-storage.yml
apiVersion: v1
kind: ConfigMap
metadata:
  name: backup-storage-config
  namespace: thesisminer
data:
  storage_config.yaml: |
    hot:
      type: local
      path: /data/backups/hot
      retention: 7d

    warm:
      type: s3
      bucket: thesisminer-backups-warm
      region: cn-north-1
      endpoint: https://s3.cn-north-1.amazonaws.com.cn
      retention: 90d
      lifecycle:
        transition_to_glacier: 30d
        expiration: 90d

    cold:
      type: s3
      bucket: thesisminer-backups-cold
      region: cn-north-1
      storage_class: GLACIER
      retention: 2555d  # 7 years
      lifecycle:
        transition_to_deep_archive: 365d
        expiration: 2555d

    offsite:
      type: s3
      bucket: thesisminer-backups-offsite
      region: cn-east-1  # Shanghai
      replication: true
      retention: 365d
```

#### 4.7.3 WORM 存储

审计日志等合规数据使用 WORM（Write Once Read Many）存储，防止篡改：

```yaml
# S3 Object Lock 配置
apiVersion: v1
kind: ConfigMap
metadata:
  name: worm-storage-config
  namespace: thesisminer
data:
  config.yaml: |
    bucket: thesisminer-audit-worm
    object_lock:
      mode: COMPLIANCE  # 合规模式，不可删除
      retention_days: 2555  # 7 years
    legal_hold: true  # 法律保留
```

### 4.8 备份监控与告警

#### 4.8.1 监控指标

| 指标 | 说明 | 告警阈值 |
|------|------|----------|
| `backup_success_total` | 备份成功次数 | - |
| `backup_failure_total` | 备份失败次数 | > 0 |
| `backup_duration_seconds` | 备份耗时 | > 3600 |
| `backup_size_bytes` | 备份大小 | 异常波动 |
| `backup_age_seconds` | 最近备份距今 | > 86400（1 天） |
| `backup_verification_success_total` | 验证成功次数 | - |
| `backup_verification_failure_total` | 验证失败次数 | > 0 |

#### 4.8.2 告警规则

```yaml
# deploy/prometheus/rules/backup-alerts.yml
groups:
- name: thesisminer-backup
  rules:

  # 备份失败
  - alert: BackupFailed
    expr: increase(backup_failure_total[1h]) > 0
    for: 5m
    labels:
      severity: critical
      team: sre
    annotations:
      summary: "Backup failed"
      description: "Backup job failed, check logs"

  # 备份超时
  - alert: BackupTimeout
    expr: backup_duration_seconds > 3600
    for: 5m
    labels:
      severity: warning
      team: sre
    annotations:
      summary: "Backup taking too long"

  # 备份过期
  - alert: BackupStale
    expr: time() - backup_last_success_timestamp_seconds > 86400
    for: 1h
    labels:
      severity: critical
      team: sre
    annotations:
      summary: "No successful backup in 24 hours"

  # 验证失败
  - alert: BackupVerificationFailed
    expr: increase(backup_verification_failure_total[1h]) > 0
    for: 5m
    labels:
      severity: critical
      team: sre
    annotations:
      summary: "Backup verification failed"
      description: "Backup is corrupted or unreadable"
```

---

## 5. 故障切换设计

### 5.1 故障检测

#### 5.1.1 健康检查

ThesisMiner v8.0 多层健康检查：

```
+-------------------+
| L7 健康检查       |  HTTP GET /health，检查应用状态
+-------------------+
         |
         v
+-------------------+
| L4 健康检查       |  TCP 连接检查
+-------------------+
         |
         v
+-------------------+
| L3 健康检查       |  ICMP ping
+-------------------+
```

#### 5.1.2 健康检查端点

```python
# backend/api/health.py
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
import sqlite3
import redis
import time

router = APIRouter()


@router.get("/health")
async def health_check():
    """L7 健康检查。"""
    checks = {
        "database": await _check_database(),
        "redis": await _check_redis(),
        "deepseek": await _check_deepseek(),
    }

    all_healthy = all(c["status"] == "healthy" for c in checks.values())

    return JSONResponse(
        status_code=status.HTTP_200_OK if all_healthy
                    else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "healthy" if all_healthy else "unhealthy",
            "timestamp": time.time(),
            "checks": checks
        }
    )


@router.get("/health/live")
async def liveness():
    """存活检查，不检查依赖。"""
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness():
    """就绪检查，检查依赖。"""
    checks = {
        "database": await _check_database(),
        "redis": await _check_redis(),
    }
    ready = all(c["status"] == "healthy" for c in checks.values())
    return JSONResponse(
        status_code=status.HTTP_200_OK if ready
                    else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "ready" if ready else "not ready", "checks": checks}
    )


async def _check_database() -> dict:
    try:
        conn = sqlite3.connect("/data/thesisminer/thesisminer.db", timeout=1)
        conn.execute("SELECT 1")
        conn.close()
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


async def _check_redis() -> dict:
    try:
        r = redis.Redis(host="redis", port=6379, socket_timeout=1)
        r.ping()
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


async def _check_deepseek() -> dict:
    # 轻量级检查，不实际调用 API
    return {"status": "healthy"}
```

#### 5.1.3 故障判定

| 检查类型 | 连续失败次数 | 判定 |
|----------|--------------|------|
| L7 健康检查 | 3 次（15 秒） | 应用故障 |
| L4 TCP 检查 | 3 次（9 秒） | 网络故障 |
| 数据库连接 | 5 次（25 秒） | 数据库故障 |
| Redis 连接 | 3 次（15 秒） | 缓存故障 |

### 5.2 故障切换流程

#### 5.2.1 自动故障切换

```
[检测故障] --> [确认故障] --> [提升备库] --> [切换流量] --> [验证恢复]
   |              |              |              |              |
   v              v              v              v              v
 健康检查      多数派投票     SQLite 提升    DNS/负载均衡    健康检查
 3 次失败      Raft 协议      主库角色       切换           通过
```

#### 5.2.2 故障切换脚本

```python
# scripts/failover/auto_failover.py
import subprocess
import time
import logging
import requests
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AutoFailover:
    """自动故障切换器。"""

    def __init__(self, primary_host: str, secondary_host: str,
                 health_check_url: str, dns_record: str,
                 max_retries: int = 3, retry_interval: int = 5):
        self.primary_host = primary_host
        self.secondary_host = secondary_host
        self.health_check_url = health_check_url
        self.dns_record = dns_record
        self.max_retries = max_retries
        self.retry_interval = retry_interval

    def check_health(self, host: str) -> bool:
        """检查主机健康状态。"""
        url = f"http://{host}{self.health_check_url}"
        for i in range(self.max_retries):
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    return True
            except Exception as e:
                logger.warning(f"Health check failed (attempt {i+1}): {e}")
            time.sleep(self.retry_interval)
        return False

    def promote_secondary(self) -> bool:
        """提升备库为主库。"""
        logger.info("Promoting secondary to primary...")

        # 1. 停止备库的复制
        subprocess.run([
            "sqlite3", f"{self.secondary_host}:/data/thesisminer/thesisminer.db",
            "PRAGMA replication_stop;"
        ], check=True)

        # 2. 提升备库为主库
        subprocess.run([
            "sqlite3", f"{self.secondary_host}:/data/thesisminer/thesisminer.db",
            "PRAGMA replication_promote;"
        ], check=True)

        # 3. 验证新主库可写
        try:
            subprocess.run([
                "sqlite3", f"{self.secondary_host}:/data/thesisminer/thesisminer.db",
                "CREATE TABLE IF NOT EXISTS failover_test (id INTEGER);"
            ], check=True)
            logger.info("Secondary promoted successfully")
            return True
        except Exception as e:
            logger.error(f"Promotion failed: {e}")
            return False

    def switch_dns(self) -> bool:
        """切换 DNS 指向。"""
        logger.info(f"Switching DNS {self.dns_record} to {self.secondary_host}")
        # 使用 Route 53 / CloudDNS API
        result = subprocess.run([
            "aws", "route53", "change-resource-record-sets",
            "--hosted-zone-id", "Z123ABC",
            "--change-batch", f"""{{
                "Changes": [{{
                    "Action": "UPSERT",
                    "ResourceRecordSet": {{
                        "Name": "{self.dns_record}",
                        "Type": "CNAME",
                        "TTL": 60,
                        "ResourceRecords": [{{"Value": "{self.secondary_host}"}}]
                    }}
                }}]
            }}"""
        ], capture_output=True, text=True)

        if result.returncode == 0:
            logger.info("DNS switched successfully")
            return True
        else:
            logger.error(f"DNS switch failed: {result.stderr}")
            return False

    def failover(self) -> bool:
        """执行故障切换。"""
        logger.info("Starting failover process...")

        # 1. 检查主库健康
        if self.check_health(self.primary_host):
            logger.info("Primary is healthy, no failover needed")
            return False

        logger.warning("Primary is unhealthy, initiating failover")

        # 2. 检查备库健康
        if not self.check_health(self.secondary_host):
            logger.error("Secondary is also unhealthy, cannot failover")
            return False

        # 3. 提升备库
        if not self.promote_secondary():
            logger.error("Failed to promote secondary")
            return False

        # 4. 切换流量
        if not self.switch_dns():
            logger.error("Failed to switch DNS")
            return False

        # 5. 等待 DNS 生效
        logger.info("Waiting for DNS propagation...")
        time.sleep(60)

        # 6. 验证恢复
        if self.check_health(self.secondary_host):
            logger.info("Failover completed successfully")
            self._send_notification("Failover completed", "success")
            return True
        else:
            logger.error("Failover verification failed")
            self._send_notification("Failover verification failed", "critical")
            return False

    def _send_notification(self, message: str, severity: str):
        """发送通知。"""
        # 发送到 PagerDuty / Slack
        pass


if __name__ == "__main__":
    failover = AutoFailover(
        primary_host="thesisminer-primary.internal",
        secondary_host="thesisminer-secondary.internal",
        health_check_url="/health",
        dns_record="thesisminer.example.com"
    )
    failover.failover()
```

### 5.3 故障回切

故障恢复后，需要将流量切回主中心，称为回切（Failback）。

#### 5.3.1 回切流程

```
[原主库恢复] --> [数据同步] --> [一致性校验] --> [切换流量] --> [恢复复制]
      |              |              |              |              |
      v              v              v              v              v
   健康检查      增量同步       数据对比       DNS 切换       重建立复制
```

#### 5.3.2 回切脚本

```python
# scripts/failover/failback.py
import subprocess
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Failback:
    """故障回切器。"""

    def __init__(self, original_primary: str, current_primary: str):
        self.original_primary = original_primary
        self.current_primary = current_primary

    def failback(self) -> bool:
        """执行回切。"""
        logger.info("Starting failback process...")

        # 1. 检查原主库健康
        if not self._check_health(self.original_primary):
            logger.error("Original primary is not healthy")
            return False

        # 2. 建立反向复制（current -> original）
        logger.info("Setting up reverse replication...")
        subprocess.run([
            "sqlite3", f"{self.original_primary}:/data/thesisminer/thesisminer.db",
            f"PRAGMA replication_setup_primary='{self.current_primary}';"
        ], check=True)

        # 3. 等待数据同步
        logger.info("Waiting for data sync...")
        if not self._wait_for_sync():
            logger.error("Data sync failed")
            return False

        # 4. 一致性校验
        logger.info("Verifying data consistency...")
        if not self._verify_consistency():
            logger.error("Data consistency check failed")
            return False

        # 5. 切换流量
        logger.info("Switching traffic back to original primary...")
        if not self._switch_dns(self.original_primary):
            logger.error("DNS switch failed")
            return False

        # 6. 等待 DNS 生效
        time.sleep(60)

        # 7. 恢复正常复制（original -> current）
        logger.info("Restoring normal replication...")
        subprocess.run([
            "sqlite3", f"{self.current_primary}:/data/thesisminer/thesisminer.db",
            f"PRAGMA replication_setup_primary='{self.original_primary}';"
        ], check=True)

        logger.info("Failback completed successfully")
        return True

    def _check_health(self, host: str) -> bool:
        # 实现健康检查
        pass

    def _wait_for_sync(self, timeout: int = 3600) -> bool:
        """等待数据同步完成。"""
        start = time.time()
        while time.time() - start < timeout:
            # 检查复制延迟
            result = subprocess.run([
                "sqlite3", f"{self.original_primary}:/data/thesisminer/thesisminer.db",
                "PRAGMA replication_lag;"
            ], capture_output=True, text=True)

            lag = int(result.stdout.strip())
            if lag == 0:
                return True

            logger.info(f"Replication lag: {lag}s")
            time.sleep(10)

        return False

    def _verify_consistency(self) -> bool:
        """验证数据一致性。"""
        # 对比两库数据
        pass

    def _switch_dns(self, target: str) -> bool:
        """切换 DNS。"""
        pass
```

### 5.4 数据一致性保障

#### 5.4.1 一致性级别

| 级别 | 说明 | 适用场景 |
|------|------|----------|
| 强一致 | 写入立即可读 | 用户数据、论文 |
| 最终一致 | 写入后延迟可读 | 缓存、索引 |
| 会话一致 | 同一会话内一致 | 会话状态 |

#### 5.4.2 一致性校验

```python
# scripts/verify/consistency_check.py
import sqlite3
import hashlib
from typing import List, Tuple


class ConsistencyChecker:
    """数据一致性校验器。"""

    def __init__(self, primary_db: str, secondary_db: str):
        self.primary = sqlite3.connect(primary_db)
        self.secondary = sqlite3.connect(secondary_db)

    def check_all(self) -> bool:
        """执行全部一致性检查。"""
        checks = [
            self._check_table_count,
            self._check_row_counts,
            self._check_checksums,
            self._check_latest_records,
        ]
        return all(check() for check in checks)

    def _check_table_count(self) -> bool:
        """检查表数量一致。"""
        primary_tables = self._get_tables(self.primary)
        secondary_tables = self._get_tables(self.secondary)
        if primary_tables != secondary_tables:
            print(f"Table mismatch: {primary_tables} vs {secondary_tables}")
            return False
        return True

    def _check_row_counts(self) -> bool:
        """检查每表行数一致。"""
        tables = self._get_tables(self.primary)
        for table in tables:
            primary_count = self.primary.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
            secondary_count = self.secondary.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
            if primary_count != secondary_count:
                print(f"Row count mismatch for {table}: "
                      f"{primary_count} vs {secondary_count}")
                return False
        return True

    def _check_checksums(self) -> bool:
        """检查数据校验和一致。"""
        tables = self._get_tables(self.primary)
        for table in tables:
            primary_hash = self._table_checksum(self.primary, table)
            secondary_hash = self._table_checksum(self.secondary, table)
            if primary_hash != secondary_hash:
                print(f"Checksum mismatch for {table}")
                return False
        return True

    def _check_latest_records(self) -> bool:
        """检查最新记录一致。"""
        tables = self._get_tables(self.primary)
        for table in tables:
            # 检查最新 100 条记录
            primary_records = self.primary.execute(
                f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT 100"
            ).fetchall()
            secondary_records = self.secondary.execute(
                f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT 100"
            ).fetchall()
            if primary_records != secondary_records:
                print(f"Latest records mismatch for {table}")
                return False
        return True

    def _get_tables(self, conn: sqlite3.Connection) -> List[str]:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        return [row[0] for row in cursor.fetchall()]

    def _table_checksum(self, conn: sqlite3.Connection,
                        table: str) -> str:
        cursor = conn.execute(f"SELECT * FROM {table}")
        data = str(cursor.fetchall()).encode()
        return hashlib.md5(data).hexdigest()
```

### 5.5 流量切换

#### 5.5.1 DNS 切换

```yaml
# deploy/dns/failover.yml
apiVersion: v1
kind: ConfigMap
metadata:
  name: dns-failover-config
  namespace: thesisminer
data:
  primary: thesisminer-primary.internal
  secondary: thesisminer-secondary.internal
  dns_record: thesisminer.example.com
  ttl: 60  # 1 分钟 TTL，快速切换
  health_check_interval: 10
```

#### 5.5.2 负载均衡切换

```yaml
# deploy/loadbalancer/failover.yml
apiVersion: v1
kind: ConfigMap
metadata:
  name: lb-failover-config
  namespace: thesisminer
data:
  strategy: weighted  # weighted | failover
  primary_weight: 100
  secondary_weight: 0
  health_check_path: /health
  health_check_interval: 10
  unhealthy_threshold: 3
```

#### 5.5.3 蓝绿切换

```bash
#!/bin/bash
# scripts/failover/blue_green_switch.sh

set -euo pipefail

CURRENT=$(kubectl get service thesisminer -o jsonpath='{.spec.selector.color}')
if [ "${CURRENT}" = "blue" ]; then
    TARGET="green"
else
    TARGET="blue"
fi

echo "Switching from ${CURRENT} to ${TARGET}"

# 1. 部署目标版本
kubectl apply -f deploy/k8s/thesisminer-${TARGET}.yml

# 2. 等待目标版本就绪
kubectl wait --for=condition=ready pod -l color=${TARGET} -n thesisminer --timeout=300s

# 3. 切换 Service
kubectl patch service thesisminer -p "{\"spec\":{\"selector\":{\"color\":\"${TARGET}\"}}}"

# 4. 验证
sleep 10
curl -f http://thesisminer.example.com/health

echo "Switched to ${TARGET}"
```

---

## 6. 数据恢复设计

### 6.1 恢复场景

ThesisMiner v8.0 数据恢复场景：

| 场景 | 触发原因 | 恢复方式 | RTO |
|------|----------|----------|-----|
| 误删表 | 人为误操作 | 时间点恢复 | 30 分钟 |
| 误删记录 | 人为误操作 | 时间点恢复 | 30 分钟 |
| 数据库损坏 | 硬件故障 | 全量 + WAL 恢复 | 1 小时 |
| 数据库锁定 | 软件故障 | 重启 + 恢复 | 15 分钟 |
| 区域故障 | 自然灾害 | 跨区域恢复 | 4 小时 |
| 勒索软件 | 恶意攻击 | 离线备份恢复 | 8 小时 |
| 误删文件 | 人为误操作 | 备份恢复 | 1 小时 |

### 6.2 时间点恢复

#### 6.2.1 PITR 原理

时间点恢复（Point-in-Time Recovery, PITR）通过全量备份 + WAL 归档实现：

```
时间轴：
  T0          T1          T2          T3          T4
  |           |           |           |           |
  v           v           v           v           v
  全量备份    WAL归档1    WAL归档2    WAL归档3    故障点
              |
              +-- 恢复到 T1：全量 + WAL归档1
              |
              +-- 恢复到 T2：全量 + WAL归档1 + WAL归档2
```

#### 6.2.2 PITR 实现

```bash
#!/bin/bash
# scripts/recovery/pitr.sh

set -euo pipefail

DB_PATH="/data/thesisminer/thesisminer.db"
BACKUP_DIR="/data/backups/sqlite"
RECOVERY_TIME="${1}"  # 格式：2026-06-20 10:30:00
RECOVERY_DIR="/tmp/recovery_$(date +%s)"

mkdir -p "${RECOVERY_DIR}"

echo "Recovering to: ${RECOVERY_TIME}"

# 1. 找到恢复时间点之前的最近全量备份
FULL_BACKUP=$(find "${BACKUP_DIR}/full" -name "*.db.gpg" | \
    while read f; do
        timestamp=$(echo "$f" | grep -oP '\d{8}_\d{6}')
        date -d "${timestamp:0:8} ${timestamp:8:2}:${timestamp:10:2}:${timestamp:12:2}" +%s
        echo "$f"
    done | sort -k1 -n | awk -v target=$(date -d "${RECOVERY_TIME}" +%s) \
        '$1 <= target {file=$2} END {print file}')

if [ -z "${FULL_BACKUP}" ]; then
    echo "No suitable full backup found"
    exit 1
fi

echo "Using full backup: ${FULL_BACKUP}"

# 2. 解密并解压全量备份
gpg --batch --yes --passphrase-file /etc/thesisminer/backup_key \
    --decrypt "${FULL_BACKUP}" > "${RECOVERY_DIR}/full.db.gz"
gunzip "${RECOVERY_DIR}/full.db.gz"

# 3. 应用 WAL 归档（直到恢复时间点）
WAL_FILES=$(find "${BACKUP_DIR}/wal" -name "*.wal.gpg" | \
    while read f; do
        timestamp=$(echo "$f" | grep -oP '\d{8}_\d{6}')
        date -d "${timestamp:0:8} ${timestamp:8:2}:${timestamp:10:2}:${timestamp:12:2}" +%s
        echo "$f"
    done | sort -k1 -n | awk -v target=$(date -d "${RECOVERY_TIME}" +%s) \
        '$1 <= target {print $2}')

for wal_file in ${WAL_FILES}; do
    echo "Applying WAL: ${wal_file}"
    gpg --batch --yes --passphrase-file /etc/thesisminer/backup_key \
        --decrypt "${wal_file}" > "${RECOVERY_DIR}/current.wal"
    cp "${RECOVERY_DIR}/current.wal" "${RECOVERY_DIR}/full.db-wal"
    sqlite3 "${RECOVERY_DIR}/full.db" "PRAGMA wal_checkpoint(TRUNCATE);"
done

# 4. 验证恢复结果
sqlite3 "${RECOVERY_DIR}/full.db" "PRAGMA integrity_check;"

# 5. 替换生产数据库
echo "Backup current database"
cp "${DB_PATH}" "${DB_PATH}.bak.$(date +%s)"

echo "Replace with recovered database"
cp "${RECOVERY_DIR}/full.db" "${DB_PATH}"

echo "PITR completed successfully"
```

### 6.3 跨区域恢复

#### 6.3.1 跨区域恢复流程

```
[异地备份可用] --> [拉取备份] --> [本地恢复] --> [数据校验] --> [服务恢复]
      |               |              |              |              |
      v               v              v              v              v
   验证备份存在    跨区域传输    解密解压       一致性检查     流量切换
```

#### 6.3.2 跨区域恢复脚本

```python
# scripts/recovery/cross_region_recovery.py
import subprocess
import logging
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CrossRegionRecovery:
    """跨区域恢复器。"""

    def __init__(self, source_region: str, source_bucket: str,
                 target_dir: str, db_path: str):
        self.source_region = source_region
        self.source_bucket = source_bucket
        self.target_dir = Path(target_dir)
        self.db_path = Path(db_path)

    def recover(self, backup_date: str) -> bool:
        """执行跨区域恢复。"""
        logger.info(f"Starting cross-region recovery for {backup_date}")

        # 1. 拉取异地备份
        if not self._pull_backup(backup_date):
            return False

        # 2. 解密解压
        decrypted_file = self._decrypt_backup(backup_date)
        if not decrypted_file:
            return False

        # 3. 验证备份
        if not self._verify_backup(decrypted_file):
            return False

        # 4. 备份当前数据库
        self._backup_current()

        # 5. 替换数据库
        if not self._replace_database(decrypted_file):
            return False

        # 6. 数据校验
        if not self._verify_data():
            return False

        # 7. 重启服务
        if not self._restart_service():
            return False

        logger.info("Cross-region recovery completed successfully")
        return True

    def _pull_backup(self, date: str) -> bool:
        """从异地拉取备份。"""
        logger.info(f"Pulling backup from {self.source_region}")
        self.target_dir.mkdir(parents=True, exist_ok=True)

        result = subprocess.run([
            "aws", "s3", "sync",
            f"s3://{self.source_bucket}/{date}/",
            str(self.target_dir / date),
            "--source-region", self.source_region,
            "--region", "cn-north-1"
        ], capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Failed to pull backup: {result.stderr}")
            return False

        logger.info("Backup pulled successfully")
        return True

    def _decrypt_backup(self, date: str) -> Path:
        """解密备份。"""
        backup_file = self.target_dir / date / "thesisminer.db.gz.gpg"
        decrypted_file = self.target_dir / date / "thesisminer.db.gz"

        result = subprocess.run([
            "gpg", "--batch", "--yes",
            "--passphrase-file", "/etc/thesisminer/backup_key",
            "--decrypt", "--output", str(decrypted_file),
            str(backup_file)
        ], capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Decryption failed: {result.stderr}")
            return None

        # 解压
        subprocess.run(["gunzip", str(decrypted_file)], check=True)
        return decrypted_file.with_suffix("")  # .db

    def _verify_backup(self, db_file: Path) -> bool:
        """验证备份完整性。"""
        result = subprocess.run([
            "sqlite3", str(db_file), "PRAGMA integrity_check;"
        ], capture_output=True, text=True)

        if result.returncode != 0 or result.stdout.strip() != "ok":
            logger.error(f"Backup verification failed: {result.stdout}")
            return False

        logger.info("Backup verification passed")
        return True

    def _backup_current(self):
        """备份当前数据库。"""
        backup_path = self.db_path.with_suffix(
            f".db.bak.{int(time.time())}"
        )
        subprocess.run([
            "cp", str(self.db_path), str(backup_path)
        ], check=True)
        logger.info(f"Current database backed up to {backup_path}")

    def _replace_database(self, new_db: Path) -> bool:
        """替换数据库。"""
        try:
            subprocess.run([
                "cp", str(new_db), str(self.db_path)
            ], check=True)
            logger.info("Database replaced successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to replace database: {e}")
            return False

    def _verify_data(self) -> bool:
        """验证恢复数据。"""
        # 执行业务校验脚本
        result = subprocess.run([
            "python", "/opt/thesisminer/scripts/verify/data_check.py"
        ], capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Data verification failed: {result.stderr}")
            return False

        logger.info("Data verification passed")
        return True

    def _restart_service(self) -> bool:
        """重启服务。"""
        result = subprocess.run([
            "kubectl", "rollout", "restart",
            "deployment/thesisminer", "-n", "thesisminer"
        ], capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Service restart failed: {result.stderr}")
            return False

        # 等待滚动更新完成
        subprocess.run([
            "kubectl", "rollout", "status",
            "deployment/thesisminer", "-n", "thesisminer",
            "--timeout=300s"
        ], check=True)

        logger.info("Service restarted successfully")
        return True


if __name__ == "__main__":
    recovery = CrossRegionRecovery(
        source_region="cn-east-1",
        source_bucket="thesisminer-backups-offsite",
        target_dir="/tmp/cross_region_recovery",
        db_path="/data/thesisminer/thesisminer.db"
    )
    success = recovery.recover("2026-06-20")
    exit(0 if success else 1)
```

### 6.4 恢复验证

#### 6.4.1 验证清单

| 验证项 | 验证方法 | 通过标准 |
|--------|----------|----------|
| 数据库完整性 | `PRAGMA integrity_check` | 返回 "ok" |
| 表数量 | 对比备份前后 | 一致 |
| 行数 | 对比关键表行数 | 一致 |
| 最新记录 | 查询最新 100 条 | 存在且正确 |
| 业务功能 | 执行核心业务流程 | 全部通过 |
| 性能 | 压测 | P99 < 5s |
| 监控 | 检查指标正常 | 全部正常 |

#### 6.4.2 业务功能验证脚本

```python
# scripts/verify/business_check.py
import requests
import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BusinessVerifier:
    """业务功能验证器。"""

    def __init__(self, api_base: str, db_path: str):
        self.api_base = api_base
        self.db_path = db_path

    def verify_all(self) -> bool:
        """执行全部业务验证。"""
        checks = [
            ("API 可用性", self._check_api_health),
            ("用户登录", self._check_user_login),
            ("论文生成", self._check_thesis_generation),
            ("论文导出", self._check_thesis_export),
            ("会话管理", self._check_session_management),
            ("数据库查询", self._check_database_query),
        ]

        all_passed = True
        for name, check in checks:
            try:
                if check():
                    logger.info(f"✓ {name} 验证通过")
                else:
                    logger.error(f"✗ {name} 验证失败")
                    all_passed = False
            except Exception as e:
                logger.error(f"✗ {name} 验证异常: {e}")
                all_passed = False

        return all_passed

    def _check_api_health(self) -> bool:
        response = requests.get(f"{self.api_base}/health", timeout=5)
        return response.status_code == 200

    def _check_user_login(self) -> bool:
        response = requests.post(
            f"{self.api_base}/api/v1/auth/login",
            json={"username": "test", "password": "test"},
            timeout=10
        )
        return response.status_code == 200

    def _check_thesis_generation(self) -> bool:
        response = requests.post(
            f"{self.api_base}/api/v1/thesis/generate",
            json={"topic": "测试论文", "session_id": "verify-test"},
            timeout=30
        )
        return response.status_code in (200, 202)

    def _check_thesis_export(self) -> bool:
        response = requests.post(
            f"{self.api_base}/api/v1/thesis/export",
            json={"thesis_id": "test", "format": "pdf"},
            timeout=30
        )
        return response.status_code in (200, 202)

    def _check_session_management(self) -> bool:
        # 创建会话
        response = requests.post(
            f"{self.api_base}/api/v1/sessions",
            json={"user_id": "verify-test"},
            timeout=10
        )
        return response.status_code == 200

    def _check_database_query(self) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            # 检查关键表
            tables = ["users", "theses", "sessions", "conversations"]
            for table in tables:
                cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                logger.info(f"Table {table}: {count} rows")
            return True
        except Exception as e:
            logger.error(f"Database query failed: {e}")
            return False
        finally:
            conn.close()


if __name__ == "__main__":
    verifier = BusinessVerifier(
        api_base="http://thesisminer.example.com",
        db_path="/data/thesisminer/thesisminer.db"
    )
    exit(0 if verifier.verify_all() else 1)
```

### 6.5 恢复演练

#### 6.5.1 演练计划

| 演练类型 | 频率 | 范围 | 参与者 |
|----------|------|------|--------|
| 桌面演练 | 每月 | 流程讨论 | SRE + 开发 |
| 半实战演练 | 每季度 | 预发环境 | SRE + 开发 + DBA |
| 全实战演练 | 每年 | 生产环境 | 全员 |
| 混沌工程 | 每月 | 生产环境（小范围） | SRE |

#### 6.5.2 演练记录

每次演练必须记录：

- 演练时间、参与人员
- 演练场景、预期结果
- 实际结果、耗时
- 发现的问题
- 改进措施

---

## 7. 灾备演练

### 7.1 演练分类

#### 7.1.1 按实战程度分类

```
+-------------------+     +-------------------+     +-------------------+
| 桌面演练          | --> | 半实战演练        | --> | 全实战演练        |
| (Tabletop)        |     | (Partial)         |     | (Full)            |
| - 讨论流程        |     | - 预发环境执行    |     | - 生产环境执行    |
| - 不实际操作      |     | - 模拟故障        |     | - 真实故障注入    |
| - 低风险          |     | - 中风险          |     | - 高风险          |
+-------------------+     +-------------------+     +-------------------+
```

#### 7.1.2 按演练目标分类

| 类型 | 目标 | 示例 |
|------|------|------|
| 流程演练 | 验证流程可行性 | 故障切换流程 |
| 技术演练 | 验证技术方案 | 数据库恢复 |
| 人员演练 | 验证人员能力 | OnCall 响应 |
| 综合演练 | 验证整体能力 | 区域级故障 |

### 7.2 桌面演练

#### 7.2.1 桌面演练流程

1. **场景设定**：主持人描述故障场景
2. **流程讨论**：参与者讨论应对步骤
3. **问题识别**：识别流程中的问题
4. **改进建议**：提出改进措施
5. **报告撰写**：形成演练报告

#### 7.2.2 桌面演练示例

**场景**：北京可用区 A 完全故障，包括电力、网络。

**讨论记录**：

| 时间 | 步骤 | 负责人 | 耗时 | 问题 |
|------|------|--------|------|------|
| T+0 | 检测到可用区 A 故障 | 监控系统 | 1 分钟 | - |
| T+1 | 确认故障范围 | SRE OnCall | 5 分钟 | 需要明确判断标准 |
| T+6 | 启动故障切换 | SRE OnCall | 2 分钟 | - |
| T+8 | 提升可用区 B 为主 | 自动化脚本 | 3 分钟 | 脚本是否可靠？ |
| T+11 | 切换 DNS | 自动化脚本 | 1 分钟 | DNS TTL 60s |
| T+12 | 等待 DNS 生效 | - | 60 秒 | - |
| T+13 | 验证服务恢复 | SRE OnCall | 5 分钟 | - |
| T+18 | 通知用户 | 运营 | 10 分钟 | 通知模板？ |

**发现问题**：

1. 故障判断标准不明确
2. 自动化脚本可靠性存疑
3. 用户通知模板缺失

**改进措施**：

1. 制定明确的故障判断标准
2. 定期测试自动化脚本
3. 准备用户通知模板

### 7.3 半实战演练

#### 7.3.1 半实战演练流程

1. **演练准备**：在预发环境准备
2. **故障注入**：模拟故障
3. **实际响应**：按流程响应
4. **结果验证**：验证恢复结果
5. **报告撰写**：形成演练报告

#### 7.3.2 半实战演练示例

**场景**：预发环境数据库故障。

**执行步骤**：

```bash
# 1. 备份预发环境数据库
./scripts/backup/sqlite_full_backup.sh

# 2. 注入故障：删除数据库
rm /data/thesisminer-preprod/thesisminer.db

# 3. 验证故障：应用报错
curl http://thesisminer-preprod.example.com/health
# 预期：503 Service Unavailable

# 4. 启动恢复
./scripts/recovery/pitr.sh "2026-06-20 10:00:00"

# 5. 验证恢复
curl http://thesisminer-preprod.example.com/health
# 预期：200 OK

# 6. 业务验证
./scripts/verify/business_check.py
```

### 7.4 全实战演练

#### 7.4.1 全实战演练原则

- **最小影响**：选择低峰时段，最小化业务影响
- **充分准备**：提前通知用户，准备回滚方案
- **实时监控**：全程监控，异常立即中止
- **完整记录**：记录每一步操作与耗时

#### 7.4.2 全实战演练流程

```
[演练准备] --> [用户通知] --> [故障注入] --> [故障响应] --> [恢复验证] --> [演练总结]
    |              |              |              |              |              |
    v              v              v              v              v              v
  方案评审      提前 7 天      生产环境      按预案响应      业务验证      Postmortem
  回滚准备      通知          真实故障                      全通过
```

#### 7.4.3 全实战演练示例

**场景**：生产环境可用区 A 故障切换到可用区 B。

**演练计划**：

| 阶段 | 时间 | 操作 | 负责人 |
|------|------|------|--------|
| 准备 | T-7d | 方案评审、用户通知 | 演练负责人 |
| 准备 | T-1d | 最终确认、回滚准备 | SRE |
| 演练 | T+0 | 开始演练，记录基线 | 全员 |
| 演练 | T+5m | 注入故障：关闭可用区 A | SRE |
| 演练 | T+10m | 验证故障检测 | SRE |
| 演练 | T+15m | 启动故障切换 | SRE |
| 演练 | T+20m | 验证可用区 B 接管 | SRE |
| 演练 | T+25m | 业务验证 | QA |
| 演练 | T+30m | 演练结束，开始回切 | SRE |
| 演练 | T+60m | 回切完成，验证 | SRE |
| 总结 | T+1d | 撰写演练报告 | 演练负责人 |

### 7.5 混沌工程

#### 7.5.1 混沌工程原则

- **假设稳定性**：假设系统在故障下仍能稳定运行
- **注入真实故障**：模拟真实故障场景
- **自动化运行**：持续、自动地注入故障
- **最小化爆炸半径**：从小范围开始，逐步扩大

#### 7.5.2 Chaos Mesh 集成

ThesisMiner v8.0 使用 Chaos Mesh 进行混沌实验：

```yaml
# deploy/chaos/pod-kill.yml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: thesisminer-pod-kill
  namespace: thesisminer
spec:
  action: pod-kill
  mode: one
  selector:
    namespaces:
      - thesisminer
    labelSelectors:
      app: thesisminer
  scheduler:
    cron: "@every 1h"
```

```yaml
# deploy/chaos/network-delay.yml
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: thesisminer-network-delay
  namespace: thesisminer
spec:
  action: delay
  mode: all
  selector:
    namespaces:
      - thesisminer
    labelSelectors:
      app: thesisminer
  delay:
    latency: "100ms"
    correlation: "100"
    jitter: "10ms"
  duration: "30s"
  scheduler:
    cron: "@every 6h"
```

```yaml
# deploy/chaos/disk-pressure.yml
apiVersion: chaos-mesh.org/v1alpha1
kind: DiskChaos
metadata:
  name: thesisminer-disk-pressure
  namespace: thesisminer
spec:
  action: fill
  mode: one
  selector:
    namespaces:
      - thesisminer
    labelSelectors:
      app: thesisminer
  disk:
    size: "80%"
  duration: "60s"
  scheduler:
    cron: "@every 12h"
```

### 7.6 演练报告

#### 7.6.1 报告模板

```markdown
# 灾备演练报告

## 基本信息
- **演练名称**：2026 Q2 全实战故障切换演练
- **演练日期**：2026-06-20
- **演练类型**：全实战
- **演练场景**：可用区 A 故障切换
- **参与人员**：[列表]

## 演练目标
1. 验证可用区 A 故障时，系统能在 15 分钟内切换到可用区 B
2. 验证数据零丢失（RPO = 0）
3. 验证业务功能正常

## 演练过程

### 时间线
| 时间 | 事件 | 耗时 | 负责人 | 结果 |
|------|------|------|--------|------|
| 02:00 | 演练开始 | - | 张三 | - |
| 02:05 | 注入故障：关闭可用区 A | 5 分钟 | 李四 | 成功 |
| 02:06 | 监控告警触发 | 1 分钟 | 自动 | 成功 |
| 02:08 | OnCall 确认故障 | 2 分钟 | 王五 | 成功 |
| 02:10 | 启动故障切换 | 2 分钟 | 王五 | 成功 |
| 02:13 | 可用区 B 提升为主 | 3 分钟 | 自动 | 成功 |
| 02:14 | DNS 切换 | 1 分钟 | 自动 | 成功 |
| 02:15 | 等待 DNS 生效 | 60 秒 | - | 成功 |
| 02:16 | 服务恢复验证 | 1 分钟 | QA | 成功 |
| 02:17 | 业务功能验证 | 5 分钟 | QA | 成功 |
| 02:22 | 演练完成 | 22 分钟 | - | - |

### 关键指标
| 指标 | 目标 | 实际 | 结果 |
|------|------|------|------|
| RTO | < 15 分钟 | 17 分钟 | ⚠ 未达标 |
| RPO | = 0 | 0 | ✓ 达标 |
| 数据完整性 | 100% | 100% | ✓ 达标 |
| 业务功能 | 全通过 | 全通过 | ✓ 达标 |

## 发现的问题

### 问题 1：RTO 超出目标
- **描述**：实际 RTO 17 分钟，超出 15 分钟目标
- **原因**：DNS 生效时间比预期长
- **改进**：降低 DNS TTL 到 30 秒，或使用 Anycast

### 问题 2：OnCall 响应延迟
- **描述**：从告警到确认耗时 2 分钟
- **原因**：OnCall 人员未及时查看告警
- **改进**：升级告警渠道，增加电话通知

## 改进措施
| 行动项 | 负责人 | 截止日期 | 优先级 |
|--------|--------|----------|--------|
| 降低 DNS TTL | 张三 | 2026-06-27 | 高 |
| 升级告警渠道 | 李四 | 2026-06-24 | 高 |
| 更新 Runbook | 王五 | 2026-06-23 | 中 |

## 结论
演练基本成功，系统具备故障切换能力。RTO 略超目标，需优化。建议下次演练在优化后重新验证。
```

---

## 8. 灾备预案

### 8.1 预案体系

ThesisMiner v8.0 灾备预案体系：

```
                    +-------------------+
                    | 总体预案          |
                    | (BCP/DRP)         |
                    +-------------------+
                            |
            +---------------+---------------+
            |               |               |
            v               v               v
    +-----------+   +-----------+   +-----------+
    | 数据库    |   | 应用      |   | 网络      |
    | 故障预案  |   | 故障预案  |   | 故障预案  |
    +-----------+   +-----------+   +-----------+
            |
    +-------+-------+-------+
    |               |       |
    v               v       v
+-------+   +-------+   +-------+
| 区域  |   | 第三方|   | 安全  |
| 故障  |   | 服务  |   | 事件  |
| 预案  |   | 预案  |   | 预案  |
+-------+   +-------+   +-------+
```

### 8.2 数据库故障预案

#### 8.2.1 SQLite 数据库锁定

**症状**：`database is locked` 错误

**处理步骤**：

1. 检查锁定原因
   ```bash
   sqlite3 /data/thesisminer/thesisminer.db "PRAGMA lock_status;"
   ```

2. 查找锁定进程
   ```bash
   fuser /data/thesisminer/thesisminer.db
   ```

3. 若为僵尸进程，终止
   ```bash
   kill -9 <PID>
   ```

4. 若无法终止，重启服务
   ```bash
   kubectl rollout restart deployment/thesisminer -n thesisminer
   ```

5. 验证恢复
   ```bash
   sqlite3 /data/thesisminer/thesisminer.db "PRAGMA integrity_check;"
   curl http://thesisminer.example.com/health
   ```

#### 8.2.2 SQLite 数据库损坏

**症状**：`database disk image is malformed` 错误

**处理步骤**：

1. 确认损坏
   ```bash
   sqlite3 /data/thesisminer/thesisminer.db "PRAGMA integrity_check;"
   # 若返回非 "ok"，则确认损坏
   ```

2. 尝试恢复
   ```bash
   # 方法 1：dump 恢复
   sqlite3 /data/thesisminer/thesisminer.db ".dump" > /tmp/dump.sql
   sqlite3 /data/thesisminer/thesisminer_recovered.db < /tmp/dump.sql

   # 方法 2：从备份恢复
   ./scripts/recovery/pitr.sh "最近可用时间点"
   ```

3. 替换数据库
   ```bash
   cp /data/thesisminer/thesisminer.db /data/thesisminer/thesisminer.db.corrupt.$(date +%s)
   cp /data/thesisminer/thesisminer_recovered.db /data/thesisminer/thesisminer.db
   ```

4. 重启服务并验证

#### 8.2.3 WAL 文件过大

**症状**：WAL 文件 > 1GB

**处理步骤**：

1. 手动触发 checkpoint
   ```bash
   sqlite3 /data/thesisminer/thesisminer.db "PRAGMA wal_checkpoint(TRUNCATE);"
   ```

2. 检查 checkpoint 参数
   ```bash
   sqlite3 /data/thesisminer/thesisminer.db "PRAGMA journal_mode;"
   sqlite3 /data/thesisminer/thesisminer.db "PRAGMA wal_autocheckpoint;"
   ```

3. 调整配置
   ```python
   # 在应用中设置
   conn.execute("PRAGMA wal_autocheckpoint=1000")  # 每 1000 页 checkpoint
   ```

### 8.3 应用故障预案

#### 8.3.1 应用无响应

**症状**：健康检查失败，请求超时

**处理步骤**：

1. 检查 Pod 状态
   ```bash
   kubectl get pods -n thesisminer -l app=thesisminer
   kubectl describe pod <pod-name> -n thesisminer
   ```

2. 查看日志
   ```bash
   kubectl logs <pod-name> -n thesisminer --tail=100
   ```

3. 检查资源使用
   ```bash
   kubectl top pod -n thesisminer
   ```

4. 若资源不足，扩容
   ```bash
   kubectl scale deployment/thesisminer -n thesisminer --replicas=10
   ```

5. 若代码问题，回滚
   ```bash
   kubectl rollout undo deployment/thesisminer -n thesisminer
   ```

6. 验证恢复
   ```bash
   kubectl rollout status deployment/thesisminer -n thesisminer
   curl http://thesisminer.example.com/health
   ```

#### 8.3.2 应用 OOM

**症状**：Pod 被 OOMKilled

**处理步骤**：

1. 确认 OOM
   ```bash
   kubectl get pod <pod-name> -n thesisminer -o jsonpath='{.status.containerStatuses[0].lastState}'
   ```

2. 检查内存限制
   ```bash
   kubectl get deployment thesisminer -n thesisminer -o yaml | grep -A5 resources
   ```

3. 分析内存使用
   ```bash
   kubectl top pod <pod-name> -n thesisminer --containers
   ```

4. 增加内存限制或修复内存泄漏
   ```bash
   kubectl patch deployment thesisminer -n thesisminer --type=json \
     -p='[{"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"2Gi"}]'
   ```

5. 重启并监控

### 8.4 网络故障预案

#### 8.4.1 网络分区

**症状**：跨可用区通信失败

**处理步骤**：

1. 确认网络分区
   ```bash
   kubectl get nodes -o wide
   kubectl describe node <node-name>
   ```

2. 检查网络策略
   ```bash
   kubectl get networkpolicy -n thesisminer
   ```

3. 若分区持续，切换到健康可用区
   ```bash
   # 通过负载均衡切换
   kubectl patch service thesisminer -n thesisminer --type=json \
     -p='[{"op":"replace","path":"/spec.selector.zone","value":"B"}]'
   ```

4. 验证服务

#### 8.4.2 DNS 故障

**症状**：域名解析失败

**处理步骤**：

1. 检查 CoreDNS
   ```bash
   kubectl get pods -n kube-system -l k8s-app=kube-dns
   kubectl logs <coredns-pod> -n kube-system
   ```

2. 重启 CoreDNS
   ```bash
   kubectl rollout restart deployment/coredns -n kube-system
   ```

3. 若外部 DNS 故障，切换到备用 DNS
   ```bash
   # 修改 Pod DNS 配置
   kubectl patch deployment thesisminer -n thesisminer --type=json \
     -p='[{"op":"replace","path":"/spec/template/spec/dnsPolicy","value":"None"},{"op":"add","path":"/spec/template/spec/dnsConfig","value":{"nameservers":["8.8.8.8","114.114.114.114"]}}]'
   ```

### 8.5 区域级故障预案

#### 8.5.1 区域级故障场景

- 自然灾害（地震、洪水）
- 电力中断
- 网络中断
- 云服务商区域故障

#### 8.5.2 处理流程

```
[区域故障] --> [确认范围] --> [启动跨区域切换] --> [异地恢复] --> [服务恢复]
    |              |              |                  |              |
    v              v              v                  v              v
  监控告警      评估影响       切换 DNS 到异地    拉取异地备份    验证
```

#### 8.5.3 详细步骤

1. **确认故障范围**（5 分钟）
   ```bash
   # 检查所有可用区
   kubectl get nodes -o wide

   # 检查服务状态
   kubectl get pods --all-namespaces -o wide
   ```

2. **决策切换**（5 分钟）
   - 评估故障持续时间
   - 评估业务影响
   - 决定是否切换到异地

3. **启动异地恢复**（30 分钟）
   ```bash
   # 在异地集群启动应用
   kubectl --context=shanghai apply -f deploy/k8s/thesisminer.yml

   # 拉取异地备份恢复数据库
   ./scripts/recovery/cross_region_recovery.py 2026-06-20

   # 等待应用就绪
   kubectl --context=shanghai wait --for=condition=ready pod -l app=thesisminer --timeout=300s
   ```

4. **切换 DNS**（5 分钟）
   ```bash
   # 切换 DNS 到异地
   aws route53 change-resource-record-sets ...
   ```

5. **验证恢复**（10 分钟）
   ```bash
   curl http://thesisminer.example.com/health
   ./scripts/verify/business_check.py
   ```

6. **通知用户**（5 分钟）
   - 通过公告、邮件、短信通知用户

### 8.6 第三方服务故障预案

#### 8.6.1 DeepSeek API 故障

**症状**：DeepSeek API 调用失败率 > 10%

**处理步骤**：

1. 确认 DeepSeek 故障
   ```bash
   curl -I https://api.deepseek.com/health
   ```

2. 启用备用 API Key
   ```bash
   kubectl patch configmap thesisminer-config -n thesisminer \
     --from-literal=DEEPSEEK_API_KEY=$BACKUP_API_KEY
   kubectl rollout restart deployment/thesisminer -n thesisminer
   ```

3. 若 DeepSeek 完全不可用，启用降级模式
   ```python
   # 降级模式：使用本地缓存结果
   if deepseek_unavailable:
       result = cache.get(query) or default_response
   ```

4. 通知用户：AI 能力降级

#### 8.6.2 对象存储故障

**症状**：S3 上传/下载失败

**处理步骤**：

1. 切换到备用存储
   ```bash
   kubectl patch configmap thesisminer-config -n thesisminer \
     --from-literal=STORAGE_ENDPOINT=$BACKUP_ENDPOINT
   ```

2. 启用本地存储兜底
   ```python
   try:
       s3.upload(file)
   except S3Error:
       local_storage.save(file)
       queue_for_sync(file)
   ```

---

## 9. 业务连续性计划（BCP）

### 9.1 BCP 概述

业务连续性计划（Business Continuity Plan, BCP）是确保业务在灾难发生后能够持续运营的整体计划，覆盖人员、流程、设施、技术等全方位。

BCP 与 DRP 的区别：

| 维度 | BCP | DRP |
|------|-----|-----|
| 范围 | 业务整体 | 技术系统 |
| 目标 | 业务持续 | 系统恢复 |
| 关注 | 人员、流程、设施 | 数据、应用、基础设施 |
| 时间 | 长期（数天到数周） | 短期（数分钟到数小时） |

### 9.2 业务影响分析（BIA）

#### 9.2.1 业务功能识别

ThesisMiner v8.0 业务功能：

| 功能 | 描述 | 关键性 |
|------|------|--------|
| 论文生成 | AI 生成开题报告 | L1 |
| 会话管理 | 用户会话与上下文 | L1 |
| 论文存储 | 用户论文持久化 | L1 |
| 论文导出 | PDF/DOCX 导出 | L2 |
| 谱系图 | 导师项目谱系可视化 | L2 |
| 分析报表 | 使用统计与分析 | L3 |
| 用户管理 | 注册、登录、权限 | L1 |
| 通知服务 | 邮件、短信通知 | L3 |

#### 9.2.2 影响分析

| 功能 | 停机影响（1 小时） | 停机影响（1 天） | 停机影响（1 周） |
|------|---------------------|-------------------|-------------------|
| 论文生成 | 100 篇延迟 | 2400 篇延迟 | 用户流失 |
| 会话管理 | 全部功能不可用 | 全部功能不可用 | 严重声誉损失 |
| 论文存储 | 数据丢失风险 | 数据丢失风险 | 法律责任 |
| 论文导出 | 50 次导出延迟 | 1200 次导出延迟 | 用户不满 |
| 谱系图 | 可视化不可用 | 可视化不可用 | 用户不满 |
| 分析报表 | 报表延迟 | 报表延迟 | 决策受影响 |
| 用户管理 | 新用户无法注册 | 新用户无法注册 | 用户流失 |
| 通知服务 | 通知延迟 | 通知延迟 | 用户体验差 |

### 9.3 连续性策略

#### 9.3.1 连续性目标

| 功能 | 连续性目标 | 策略 |
|------|------------|------|
| 论文生成 | 7x24 可用 | 同城双活 |
| 会话管理 | 7x24 可用 | 同城双活 |
| 论文存储 | 零丢失 | 同步复制 + 异地备份 |
| 论文导出 | 工作日可用 | 热备 |
| 谱系图 | 工作日可用 | 热备 |
| 分析报表 | 可延迟 | 温备 |
| 用户管理 | 7x24 可用 | 同城双活 |
| 通知服务 | 可延迟 | 温备 |

#### 9.3.2 降级策略

当全面恢复不可行时，按优先级降级：

| 降级级别 | 措施 |
|----------|------|
| L0 正常 | 全部功能正常 |
| L1 轻度降级 | 关闭分析报表、通知服务 |
| L2 中度降级 | 关闭谱系图、论文导出 |
| L3 重度降级 | 仅保留论文生成、会话管理 |
| L4 只读模式 | 仅允许查看已有论文，不允许新生成 |
| L5 紧急模式 | 显示维护页面，仅保留登录 |

### 9.4 应急响应组织

#### 9.4.1 组织架构

```
                    +-------------------+
                    | 应急指挥官        |
                    | (CTO 或 VP)       |
                    +-------------------+
                            |
            +---------------+---------------+
            |               |               |
            v               v               v
    +-----------+   +-----------+   +-----------+
    | 技术组    |   | 业务组    |   | 沟通组    |
    | (SRE 负责)|   | (PM 负责)|   | (PR 负责)|
    +-----------+   +-----------+   +-----------+
```

#### 9.4.2 职责分工

| 角色 | 职责 |
|------|------|
| 应急指挥官 | 总体决策、资源协调、对外沟通 |
| 技术组 | 故障定位、系统恢复、技术决策 |
| 业务组 | 业务影响评估、用户沟通、降级决策 |
| 沟通组 | 内部通知、外部公告、媒体应对 |

#### 9.4.3 联系方式

| 角色 | 姓名 | 手机 | 邮箱 |
|------|------|------|------|
| 应急指挥官 | 张总 | 138xxxx0001 | ceo@thesisminer.io |
| 技术组负责人 | 李工 | 138xxxx0002 | sre-lead@thesisminer.io |
| 业务组负责人 | 王经理 | 138xxxx0003 | pm-lead@thesisminer.io |
| 沟通组负责人 | 赵主管 | 138xxxx0004 | pr@thesisminer.io |

### 9.5 沟通计划

#### 9.5.1 内部沟通

| 时间点 | 沟通内容 | 渠道 |
|--------|----------|------|
| T+0 | 故障确认 | PagerDuty + 电话 |
| T+5m | 初步评估 | Slack #incident |
| T+15m | 详细更新 | Slack #incident + 邮件 |
| T+30m | 恢复进展 | Slack #incident |
| T+恢复 | 恢复通知 | Slack #incident + 邮件 |
| T+1d | 复盘通知 | 邮件 |

#### 9.5.2 外部沟通

| 影响程度 | 沟通内容 | 渠道 |
|----------|----------|------|
| 轻微（< 5 分钟） | 不通知 | - |
| 中等（5-30 分钟） | 公告栏通知 | 站内公告 |
| 严重（> 30 分钟） | 邮件 + 短信通知 | 邮件 + 短信 |
| 重大（> 4 小时） | 媒体公告 | 官网 + 社交媒体 |

#### 9.5.3 沟通模板

**用户通知模板**：

```
尊敬的 ThesisMiner 用户：

您好！ThesisMiner 服务于 [时间] 出现 [故障描述]，可能导致 [影响描述]。

我们的工程师正在紧急处理，预计 [预计恢复时间] 恢复。

给您带来的不便，我们深表歉意。如有疑问，请联系 support@thesisminer.io。

ThesisMiner 团队
[时间]
```

**恢复通知模板**：

```
尊敬的 ThesisMiner 用户：

您好！ThesisMiner 服务已于 [时间] 恢复正常。

故障原因：[原因描述]
故障时长：[时长]
影响范围：[范围]

我们将进行深入复盘，避免类似问题再次发生。

感谢您的耐心与支持。

ThesisMiner 团队
[时间]
```

---

## 10. 灾难恢复计划（DRP）

### 10.1 DRP 概述

灾难恢复计划（Disaster Recovery Plan, DRP）是 BCP 的技术子集，专注于 IT 系统的恢复。

### 10.2 恢复优先级

ThesisMiner v8.0 恢复优先级：

| 优先级 | 系统 | RTO | 恢复顺序 |
|--------|------|-----|----------|
| P0 | 网络 | 5 分钟 | 1 |
| P0 | DNS | 5 分钟 | 2 |
| P1 | 数据库 | 15 分钟 | 3 |
| P1 | 对象存储 | 15 分钟 | 4 |
| P1 | 核心应用 | 15 分钟 | 5 |
| P2 | 缓存 | 30 分钟 | 6 |
| P2 | 辅助应用 | 1 小时 | 7 |
| P3 | 监控 | 2 小时 | 8 |
| P3 | 日志 | 4 小时 | 9 |

### 10.3 恢复步骤

#### 10.3.1 第一阶段：基础设施恢复（0-15 分钟）

1. 恢复网络
2. 恢复 DNS
3. 恢复负载均衡

#### 10.3.2 第二阶段：数据恢复（15-30 分钟）

1. 恢复 SQLite 数据库
2. 恢复对象存储
3. 验证数据完整性

#### 10.3.3 第三阶段：应用恢复（30-45 分钟）

1. 启动核心应用
2. 启动辅助应用
3. 验证服务健康

#### 10.3.4 第四阶段：验证与切换（45-60 分钟）

1. 业务功能验证
2. 流量切换
3. 监控验证

### 10.4 DRP 文档维护

#### 10.4.1 维护要求

- 每季度审查一次
- 每次重大架构变更后更新
- 每次演练后更新
- 版本化管理

#### 10.4.2 文档分发

- 在线版本：内部 Wiki
- 离线版本：打印件存放在应急指挥中心
- 移动版本：OnCall 人员手机存储

---

## 11. 灾备案例研究

### 11.1 案例一：数据库故障切换

#### 11.1.1 事件背景

- **时间**：2026-03-15 02:30 UTC
- **事件**：主数据库所在节点硬件故障
- **影响**：论文生成功能不可用

#### 11.1.2 事件经过

| 时间 | 事件 |
|------|------|
| 02:30 | 主数据库节点硬件故障，服务中断 |
| 02:31 | 监控告警触发：DatabaseDown |
| 02:33 | OnCall 确认故障 |
| 02:35 | 启动自动故障切换 |
| 02:38 | 备库提升为主库 |
| 02:39 | DNS 切换完成 |
| 02:40 | 服务恢复 |
| 02:45 | 业务验证通过 |

#### 11.1.3 根因分析

硬件故障为不可抗力，但故障切换耗时 10 分钟，主要消耗在：

1. 故障检测：2 分钟（告警延迟）
2. 人工确认：2 分钟（OnCall 响应）
3. 自动切换：6 分钟（脚本执行 + DNS 生效）

#### 11.1.4 改进措施

1. 降低告警延迟：从 2 分钟降到 30 秒
2. 自动化故障切换：减少人工确认环节
3. 降低 DNS TTL：从 60 秒降到 30 秒

### 11.2 案例二：区域级故障

#### 11.2.1 事件背景

- **时间**：2026-05-10 14:00 UTC
- **事件**：北京区域云服务商故障
- **影响**：全部服务不可用

#### 11.2.2 事件经过

| 时间 | 事件 |
|------|------|
| 14:00 | 北京区域开始出现故障 |
| 14:05 | 全部服务不可用 |
| 14:10 | 确认为区域级故障 |
| 14:15 | 决定切换到上海异地灾备 |
| 14:20 | 启动异地恢复 |
| 14:50 | 异地应用启动完成 |
| 15:00 | 数据恢复完成 |
| 15:10 | DNS 切换到上海 |
| 15:15 | 服务恢复 |
| 15:30 | 业务验证通过 |

#### 11.2.3 根因分析

云服务商区域故障为不可抗力，但异地恢复耗时 75 分钟，主要消耗在：

1. 决策时间：15 分钟（需要人工决策）
2. 数据恢复：40 分钟（跨区域数据传输）
3. 应用启动：20 分钟（镜像拉取、配置）

#### 11.2.4 改进措施

1. 预置异地应用：平时保持最小规模运行
2. 预置异地数据：异步复制，减少恢复时数据传输
3. 自动化决策：基于健康检查自动切换

### 11.3 案例三：勒索软件攻击

#### 11.3.1 事件背景

- **时间**：2026-04-20 03:00 UTC
- **事件**：勒索软件加密生产数据
- **影响**：部分用户论文被加密

#### 11.3.2 事件经过

| 时间 | 事件 |
|------|------|
| 03:00 | 攻击开始，数据被加密 |
| 03:15 | 监控告警：异常文件变更 |
| 03:20 | OnCall 确认攻击 |
| 03:25 | 隔离受影响系统 |
| 03:30 | 启动离线备份恢复 |
| 04:00 | 全量备份恢复完成 |
| 04:30 | WAL 应用完成 |
| 05:00 | 数据完整性验证 |
| 05:30 | 服务恢复 |

#### 11.3.3 根因分析

攻击者通过弱密码 SSH 入侵，植入勒索软件。防御不足：

1. SSH 弱密码
2. 缺乏文件完整性监控
3. 备份与生产同网络

#### 11.3.4 改进措施

1. 强制 SSH 密钥认证
2. 部署文件完整性监控（FIM）
3. 备份离线存储
4. 网络分段隔离
5. 定期安全审计

### 11.4 案例四：人为误操作

#### 11.4.1 事件背景

- **时间**：2026-06-05 10:00 UTC
- **事件**：工程师误删生产数据库表
- **影响**：用户会话数据丢失

#### 11.4.2 事件经过

| 时间 | 事件 |
|------|------|
| 10:00 | 工程师执行 `DROP TABLE sessions` |
| 10:01 | 用户报障：会话丢失 |
| 10:02 | 确认误删 |
| 10:05 | 启动 PITR 恢复 |
| 10:15 | 恢复到 09:59（误删前） |
| 10:20 | 数据验证 |
| 10:25 | 服务恢复 |

#### 11.4.3 根因分析

1. 工程师直接操作生产数据库
2. 缺乏操作审批流程
3. 缺乏 SQL 执行前确认

#### 11.4.4 改进措施

1. 禁止直接操作生产数据库
2. 建立 DBA 操作审批流程
3. SQL 执行前自动备份
4. 危险 SQL 自动拦截
5. 数据库操作审计

### 11.5 经验教训汇总

| 编号 | 教训 | 改进 |
|------|------|------|
| L1 | 自动化优于人工 | 故障切换全自动化 |
| L2 | 备份必须验证 | 每日备份验证 |
| L3 | 演练必须常态 | 每季度全实战演练 |
| L4 | 监控必须及时 | 降低告警延迟 |
| L5 | 安全必须重视 | 强制密钥认证、网络隔离 |
| L6 | 操作必须审批 | DBA 操作审批流程 |
| L7 | 预案必须更新 | 每季度审查更新 |
| L8 | 沟通必须及时 | 建立沟通模板与渠道 |

---

## 12. 实施与运维

### 12.1 实施路线图

#### 12.1.1 第一阶段（1-2 月）：基础建设

- 部署备份系统
- 实现全量 + 增量备份
- 部署监控告警
- 制定基础预案

#### 12.1.2 第二阶段（3-4 月）：高可用建设

- 实现同城双活
- 实现自动故障切换
- 部署健康检查
- 实现数据同步复制

#### 12.1.3 第三阶段（5-6 月）：异地灾备

- 建设异地灾备中心
- 实现异步复制
- 实现跨区域恢复
- 部署混沌工程

#### 12.1.4 第四阶段（7-12 月）：持续优化

- 定期演练
- 优化 RPO/RTO
- 完善 BCP/DRP
- 安全加固

### 12.2 运维流程

#### 12.2.1 日常运维

| 任务 | 频率 | 负责人 |
|------|------|--------|
| 检查备份状态 | 每日 | SRE |
| 检查复制延迟 | 每日 | SRE |
| 检查健康检查 | 每日 | SRE |
| 审查告警 | 每日 | SRE |
| 备份验证 | 每日 | DBA |
| 演练 | 每月 | SRE |
| 预案审查 | 每季度 | SRE + 架构师 |
| 全实战演练 | 每年 | 全员 |

#### 12.2.2 应急运维

| 事件 | 响应时间 | 负责人 |
|------|----------|--------|
| P0 告警 | 5 分钟 | OnCall |
| P1 告警 | 15 分钟 | OnCall |
| P2 告警 | 1 小时 | OnCall |
| 用户报障 | 15 分钟 | 客服 + OnCall |

### 12.3 成本管理

#### 12.3.1 成本构成

| 项目 | 年成本 | 占比 |
|------|--------|------|
| 异地灾备中心 | $40,000 | 33% |
| 备份存储 | $25,000 | 21% |
| 同城双活 | $30,000 | 25% |
| 监控告警 | $10,000 | 8% |
| 演练 | $5,000 | 4% |
| 其他 | $10,000 | 8% |
| **合计** | **$120,000** | **100%** |

#### 12.3.2 成本优化

1. **冷热分层**：冷数据使用低成本存储
2. **压缩去重**：备份数据压缩 + 去重
3. **按需扩容**：灾备资源按需使用
4. **共享资源**：多业务共享灾备中心

### 12.4 合规与审计

#### 12.4.1 合规要求

- **数据保护**：用户数据加密存储与传输
- **数据留存**：审计日志留存 7 年
- **数据本地化**：中国数据存中国
- **访问审计**：所有数据访问可审计

#### 12.4.2 审计要求

| 审计项 | 频率 | 审计方 |
|--------|------|--------|
| 备份完整性 | 每月 | 内部审计 |
| 恢复能力 | 每季度 | 内部审计 |
| 访问控制 | 每季度 | 安全团队 |
| 数据加密 | 每年 | 第三方 |
| 合规性 | 每年 | 第三方 |

---

## 13. 附录

### 13.1 配置示例

#### 13.1.1 灾备配置文件

```yaml
# config/disaster_recovery.yml
recovery:
  rpo:
    l1: 0
    l2: 300  # 5 minutes
    l3: 3600  # 1 hour

  rto:
    l1: 900  # 15 minutes
    l2: 3600  # 1 hour
    l3: 14400  # 4 hours

backup:
  schedule:
    full: "0 2 * * 0"  # 每周日 02:00
    incremental: "0 * * * *"  # 每小时
    differential: "0 3 * * *"  # 每天 03:00
    wal_archive: "*/5 * * * *"  # 每 5 分钟

  retention:
    wal: 7d
    incremental: 30d
    differential: 90d
    full: 365d
    archive: 2555d  # 7 years

  encryption:
    algorithm: AES-256-GCM
    key_rotation: 90d

failover:
  detection:
    health_check_interval: 5
    failure_threshold: 3

  automation:
    enabled: true
    script: /opt/thesisminer/scripts/failover/auto_failover.py

  dns:
    ttl: 30
    provider: route53

replication:
  primary:
    region: cn-north-1
    zone: A

  secondary:
    region: cn-north-1
    zone: B
    mode: sync

  offsite:
    region: cn-east-1
    zone: C
    mode: async
    lag: 300  # 5 minutes
```

#### 13.1.2 Kubernetes 灾备配置

```yaml
# deploy/k8s/thesisminer-ha.yml
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
      maxUnavailable: 1
      maxSurge: 2
  template:
    spec:
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchLabels:
                  app: thesisminer
              topologyKey: kubernetes.io/hostname
          - weight: 50
            podAffinityTerm:
              labelSelector:
                matchLabels:
                  app: thesisminer
              topologyKey: topology.kubernetes.io/zone
      containers:
      - name: thesisminer
        image: thesisminer:8.0.0
        resources:
          requests:
            cpu: 1
            memory: 2Gi
          limits:
            cpu: 2
            memory: 4Gi
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
          failureThreshold: 3
        volumeMounts:
        - name: data
          mountPath: /data/thesisminer
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: thesisminer-data
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: thesisminer-data
  namespace: thesisminer
spec:
  accessModes:
  - ReadWriteOnce
  storageClassName: ebs-ssd
  resources:
    requests:
      storage: 100Gi
```

### 13.2 检查清单

#### 13.2.1 灾备就绪检查清单

- [ ] RPO/RTO 目标已定义并文档化
- [ ] 备份策略已实施
- [ ] 备份验证已自动化
- [ ] 故障切换已自动化
- [ ] 健康检查已部署
- [ ] 监控告警已配置
- [ ] 灾备预案已编写
- [ ] 灾备演练已执行
- [ ] BCP/DRP 已制定
- [ ] 应急响应组织已建立
- [ ] 沟通计划已制定
- [ ] 联系方式已更新
- [ ] 合规要求已满足
- [ ] 审计已通过

#### 13.2.2 演练前检查清单

- [ ] 演练方案已评审
- [ ] 回滚方案已准备
- [ ] 用户已通知
- [ ] 监控已加强
- [ ] 参与人员已确认
- [ ] 联系方式已确认
- [ ] 演练记录表已准备
- [ ] 应急联系人已待命

#### 13.2.3 故障切换检查清单

- [ ] 故障已确认
- [ ] 影响范围已评估
- [ ] 切换决策已批准
- [ ] 备库健康已验证
- [ ] 数据同步已完成
- [ ] DNS 切换已执行
- [ ] 服务恢复已验证
- [ ] 业务功能已验证
- [ ] 用户已通知
- [ ] 监控已正常

### 13.3 故障排查

#### 13.3.1 备份失败

```bash
# 检查备份日志
tail -f /var/log/thesisminer/backup.log

# 检查磁盘空间
df -h /data/backups

# 检查权限
ls -la /data/backups

# 手动执行备份
./scripts/backup/sqlite_full_backup.sh

# 检查加密密钥
ls -la /etc/thesisminer/backup_key
```

#### 13.3.2 故障切换失败

```bash
# 检查备库状态
sqlite3 /data/thesisminer/thesisminer.db "PRAGMA replication_status;"

# 检查网络
ping thesisminer-secondary.internal

# 检查 DNS
nslookup thesisminer.example.com

# 手动切换
./scripts/failover/auto_failover.py --force
```

#### 13.3.3 恢复失败

```bash
# 检查备份完整性
sqlite3 /tmp/recovery/full.db "PRAGMA integrity_check;"

# 检查 WAL 文件
ls -la /data/backups/sqlite/wal/

# 检查磁盘空间
df -h /data/thesisminer

# 查看恢复日志
tail -f /var/log/thesisminer/recovery.log
```

### 13.4 变更记录

| 版本 | 日期 | 变更 | 作者 |
|------|------|------|------|
| v1.0 | 2026-01-20 | 初始版本，定义基础灾备策略 | SRE Team |
| v2.0 | 2026-03-10 | 增加同城双活设计 | Architecture Team |
| v3.0 | 2026-05-15 | 增加异地灾备 | SRE Team |
| v4.0 | 2026-06-10 | 增加 BCP/DRP 框架 | SRE + 业务团队 |
| v8.0 | 2026-06-20 | 适配 ThesisMiner v8.0，增加案例研究 | SRE Team |

---

## 14. 参考资源

### 14.1 标准与框架

- ISO 22301:2019 业务连续性管理体系
- ISO 27031:2011 信息技术业务连续性指南
- NIST SP 800-34 容灾计划指南
- NIST SP 800-53 安全控制
- GB/T 20988-2007 信息安全技术 信息系统灾难恢复规范

### 14.2 推荐阅读

- 《Site Reliability Engineering》- Google
- 《The Site Reliability Workbook》- Google
- 《Disaster Recovery Planning》- Jon William Toigo
- 《Business Continuity Planning》- Kenneth L. Fulmer
- 《Chaos Engineering》- Casey Rosenthal

### 14.3 内部资源

- ThesisMiner v8.0 架构文档：`docs/architecture/system_overview.md`
- ThesisMiner v8.0 部署文档：`docs/architecture/deployment_architecture.md`
- ThesisMiner v8.0 可观测性设计：`docs/architecture/observability_design.md`
- ThesisMiner v8.0 安全设计：`docs/architecture/security_design.md`
- ThesisMiner v8.0 数据库设计：`docs/architecture/database_design.md`

---

## 15. FAQ

### Q1: RPO 和 RTO 应该设多少？

**A**: 根据业务关键性分级设定。ThesisMiner v8.0 L1 业务 RPO=0、RTO=15 分钟；L2 业务 RPO=5 分钟、RTO=1 小时；L3 业务 RPO=1 小时、RTO=4 小时。不要盲目追求零 RPO/RTO，需权衡成本。

### Q2: 同城双活和异地灾备必须同时建设吗？

**A**: 不必须，但建议。同城双活解决单可用区故障，异地灾备解决区域级故障。预算有限时优先建设同城双活。

### Q3: 备份频率应该多高？

**A**: 取决于 RPO。RPO=0 需要同步复制；RPO=5 分钟需要每 5 分钟备份；RPO=1 小时需要每小时备份。ThesisMiner v8.0 采用 WAL 实时归档 + 每小时增量 + 每周全量。

### Q4: 演练必须定期做吗？

**A**: 必须定期做。未演练的预案等于没有。建议桌面演练每月、半实战每季度、全实战每年。演练后必须复盘并改进。

### Q5: 混沌工程会破坏生产吗？

**A**: 有风险，需控制爆炸半径。从小范围开始，逐步扩大。使用 Chaos Mesh 等工具控制影响范围。演练前充分准备回滚方案。

### Q6: 灾备数据必须加密吗？

**A**: 必须加密。备份数据包含用户敏感信息，加密是基本要求。ThesisMiner v8.0 使用 AES-256-GCM 加密，密钥 90 天轮换。

### Q7: BCP 和 DRP 有什么区别？

**A**: BCP 关注业务整体连续性，覆盖人员、流程、设施；DRP 关注 IT 系统恢复。DRP 是 BCP 的子集。两者都需要制定并定期演练。

### Q8: 如何评估灾备建设效果？

**A**: 关键指标：1) RPO/RTO 达成率；2) 备份成功率；3) 演练通过率；4) 故障恢复时间；5) 数据丢失量。定期评估并改进。

### Q9: SQLite 灾备怎么做？

**A**: SQLite 是单文件数据库，灾备相对简单：1) WAL 模式实时归档；2) `.backup` 命令在线全量备份；3) 主从复制（需第三方工具如 LiteSync）；4) 跨区域同步备份文件。

### Q10: 多活架构数据冲突如何解决？

**A**: 1) 避免冲突：按业务分片，不同区域写不同数据；2) 时间戳优先：后写覆盖；3) 业务规则：基于业务逻辑解决；4) 人工介入：关键数据人工合并。ThesisMiner v8.0 采用主写从读 + 会话保持避免冲突。

---

## 16. 结语

灾备建设是一项系统工程，涉及技术、流程、人员全方位。ThesisMiner v8.0 通过同城双活 + 异地温备架构、完善的备份策略、自动化的故障切换、常态化的灾备演练，构建了完整的灾备体系。随着业务演进，灾备方案应持续迭代，确保在任何灾难场景下都能保障业务连续性。

**核心要点回顾**：

1. **数据优先**：数据备份是灾备核心，宁可服务不可用也不能丢数据
2. **RPO/RTO 驱动**：所有设计围绕 RPO/RTO 目标
3. **自动化优先**：备份、切换、恢复尽量自动化
4. **演练常态化**：未演练的预案等于没有
5. **降级可用**：灾备切换后可降级服务，优先恢复核心功能
6. **安全合规**：备份数据加密、访问审计、合规留存
7. **持续演进**：灾备方案随业务演进，定期评审与更新

---

**文档结束**

> 本文档由 ThesisMiner SRE & Architecture Team 维护，最后更新于 2026-06-20。
> 如有疑问或建议，请联系 `sre@thesisminer.io` 或在内部 Wiki 提交 Issue。
> 本文档为内部机密，未经授权不得外传。
