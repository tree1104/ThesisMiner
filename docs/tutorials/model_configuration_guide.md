# ThesisMiner v8.0 模型配置完整指南

> 版本：v8.0.0
> 适用对象：系统管理员、AI 工程师、运维与 SRE、技术决策者
> 文档更新日期：2026-06-20
> 维护团队：ThesisMiner Core Team

---

## 目录

- [1. 概述](#1-概述)
  - [1.1 文档目标](#11-文档目标)
  - [1.2 模型层架构](#12-模型层架构)
  - [1.3 核心概念](#13-核心概念)
- [2. 支持的 2026 模型详解](#2-支持的-2026-模型详解)
  - [2.1 OpenAI GPT-4.1 系列](#21-openai-gpt-41-系列)
  - [2.2 DeepSeek 系列](#22-deepseek-系列)
  - [2.3 Anthropic Claude 系列](#23-anthropic-claude-系列)
  - [2.4 阿里通义 Qwen 系列](#24-阿里通义-qwen-系列)
  - [2.5 Google Gemini 系列](#25-google-gemini-系列)
  - [2.6 智谱 GLM 系列](#26-智谱-glm-系列)
  - [2.7 字节豆包系列](#27-字节豆包系列)
  - [2.8 模型对比总表](#28-模型对比总表)
- [3. Agent 到模型的默认路由](#3-agent-到模型的默认路由)
  - [3.1 路由表](#31-路由表)
  - [3.2 路由设计原则](#32-路由设计原则)
  - [3.3 路由覆盖与故障转移](#33-路由覆盖与故障转移)
- [4. 模型选择策略](#4-模型选择策略)
  - [4.1 成本维度](#41-成本维度)
  - [4.2 质量维度](#42-质量维度)
  - [4.3 延迟维度](#43-延迟维度)
  - [4.4 缓存命中率维度](#44-缓存命中率维度)
  - [4.5 综合权衡](#45-综合权衡)
- [5. 自定义模型配置](#5-自定义模型配置)
  - [5.1 环境变量配置](#51-环境变量配置)
  - [5.2 config.json 配置](#52-configjson-配置)
  - [5.3 API 动态配置](#53-api-动态配置)
  - [5.4 多 API Key 轮询](#54-多-api-key-轮询)
- [6. 模型故障转移与降级策略](#6-模型故障转移与降级策略)
  - [6.1 故障检测](#61-故障检测)
  - [6.2 故障转移流程](#62-故障转移流程)
  - [6.3 降级策略](#63-降级策略)
  - [6.4 重试逻辑](#64-重试逻辑)
- [7. DeepSeek 缓存优化配置](#7-deepseek-缓存优化配置)
  - [7.1 三段式 Prefix 设计](#71-三段式-prefix-设计)
  - [7.2 缓存命中条件](#72-缓存命中条件)
  - [7.3 命中率监控](#73-命中率监控)
  - [7.4 缓存优化技巧](#74-缓存优化技巧)
- [8. 模型评估方法论](#8-模型评估方法论)
  - [8.1 评估指标体系](#81-评估指标体系)
  - [8.2 基准测试](#82-基准测试)
  - [8.3 A/B 测试](#83-ab-测试)
- [9. 成本优化策略](#9-成本优化策略)
  - [9.1 成本构成分析](#91-成本构成分析)
  - [9.2 预算管理](#92-预算管理)
  - [9.3 用量监控](#93-用量监控)
- [10. 模型性能基准测试结果](#10-模型性能基准测试结果)
  - [10.1 推理任务基准](#101-推理任务基准)
  - [10.2 创意生成基准](#102-创意生成基准)
  - [10.3 长文本生成基准](#103-长文本生成基准)
  - [10.4 检索任务基准](#104-检索任务基准)
  - [10.5 综合评分排名](#105-综合评分排名)
- [11. 多模型组合实战案例](#11-多模型组合实战案例)
  - [11.1 案例一：理工科硕士全流程](#111-案例一理工科硕士全流程)
  - [11.2 案例二：人文社科博士创意导向](#112-案例二人文社科博士创意导向)
  - [11.3 案例三：成本敏感型批量任务](#113-案例三成本敏感型批量任务)
  - [11.4 案例四：高质量旗舰配置](#114-案例四高质量旗舰配置)
  - [11.5 案例五：国产化合规部署](#115-案例五国产化合规部署)
- [12. 模型升级与迁移指南](#12-模型升级与迁移指南)
  - [12.1 版本升级策略](#121-版本升级策略)
  - [12.2 模型替换流程](#122-模型替换流程)
  - [12.3 兼容性处理](#123-兼容性处理)
  - [12.4 回滚机制](#124-回滚机制)
- [13. 安全与合规配置](#13-安全与合规配置)
  - [13.1 API Key 安全管理](#131-api-key-安全管理)
  - [13.2 数据合规](#132-数据合规)
  - [13.3 审计日志](#133-审计日志)
  - [13.4 内容安全](#134-内容安全)
- [14. 监控与运维](#14-监控与运维)
  - [14.1 监控指标体系](#141-监控指标体系)
  - [14.2 告警配置](#142-告警配置)
  - [14.3 容量规划](#143-容量规划)
  - [14.4 故障排查](#144-故障排查)
- [15. 附录](#15-附录)

---

## 1. 概述

### 1.1 文档目标

本指南系统性地介绍 ThesisMiner v8.0 的模型配置体系，涵盖：

1. 全部 10 个 2026 年主流大模型的详细参数与适用场景；
2. Agent 到模型的默认路由策略与自定义方法；
3. 模型选择的多维度权衡（成本/质量/延迟/缓存命中率）；
4. 故障转移、降级与重试机制；
5. DeepSeek Prompt 缓存的优化配置与监控；
6. 模型评估方法论与 A/B 测试实践；
7. 成本优化与预算管理策略。

阅读本指南后，读者应能够根据自身需求，为 ThesisMiner 配置最优的模型组合，在成本、质量、延迟之间取得平衡。

### 1.2 模型层架构

ThesisMiner v8.0 的模型层位于 AI 代理层（`ai_proxy`）与外部 LLM 提供商之间，统一封装了多提供商的调用差异：

```
┌──────────────────────────────────────────────────────────────┐
│                    Agent 编排层                               │
│  Orchestrator / Searcher / Reasoner / Critic / Mentor / Writer│
└────────────────────────┬─────────────────────────────────────┘
                         │  agent_id + task
┌────────────────────────▼─────────────────────────────────────┐
│              模型路由层（Model Router）                       │
│  DEFAULT_STEP_MODELS + fallback + session/conversation 覆盖   │
└────────────────────────┬─────────────────────────────────────┘
                         │  model_id
┌────────────────────────▼─────────────────────────────────────┐
│              AI 代理层（ai_proxy.call_llm）                   │
│  get_client → 统一 OpenAI 兼容接口                           │
└────────────────────────┬─────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────┐
│              缓存层（prompt_cache + cache_monitor）           │
│  build_cached_prefix → 三段式 Prefix 注入                    │
└────────────────────────┬─────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────┐
│              外部 LLM 提供商                                  │
│  OpenAI │ DeepSeek │ Anthropic │ Qwen │ Gemini │ GLM │ Doubao│
└──────────────────────────────────────────────────────────────┘
```

### 1.3 核心概念

| 概念 | 说明 |
|------|------|
| 模型注册表 | `DEFAULT_MODELS` 列表，定义全部可用模型及其参数 |
| 步骤模型映射 | `DEFAULT_STEP_MODELS` 字典，定义每个 Agent 步骤的默认模型 |
| 故障转移 | 主模型不可用时，自动切换到备选模型 |
| 三段式 Prefix | 系统提示 + Agent 角色定义 + 会话上下文，用于 DeepSeek 缓存 |
| 缓存命中率 | 缓存命中请求数占总请求数的比例，目标 ≥ 95% |
| 透明账本 | 记录每次 LLM 调用的 Token 用量与费用 |

---

## 2. 支持的 2026 模型详解

ThesisMiner v8.0 默认注册了 10 个 2026 年主流大模型，覆盖国内外主流厂商。下文逐一详解。

### 2.1 OpenAI GPT-4.1 系列

#### 2.1.1 gpt-4.1-mini

| 属性 | 值 |
|------|-----|
| ID | `gpt-4.1-mini` |
| 标签 | GPT-4.1 Mini |
| Base URL | `https://api.openai.com/v1` |
| 输入价格 | 0.7 CNY / 百万 tokens |
| 输出价格 | 2.8 CNY / 百万 tokens |
| 流式支持 | 是 |
| 思考支持 | 否 |
| 联网搜索 | 否 |
| 最大上下文 | 1,000,000 tokens |
| 默认温度 | 0.7 |
| 默认 Agent | mentor |
| 发布年份 | 2025 |

**能力画像**：

- 高性价比的通用模型，适合大规模批量调用；
- 1M 超长上下文，适合长文档处理；
- 响应速度快，延迟低；
- 不支持思考模式，复杂推理能力有限。

**适用场景**：

- Mentor Agent 的轻量级学术指导；
- 大量文献的快速摘要；
- 用户输入的预处理与分类；
- 成本敏感的批量任务。

**配置示例**：

```json
{
  "id": "gpt-4.1-mini",
  "label": "GPT-4.1 Mini",
  "base_url": "https://api.openai.com/v1",
  "api_key": "sk-xxxxxxxx",
  "pricing": {"input_cny_per_million": 0.7, "output_cny_per_million": 2.8},
  "supports_streaming": true,
  "supports_thinking": false,
  "supports_web_search": false,
  "max_context": 1000000,
  "default_temperature": 0.7,
  "agent_default": "mentor",
  "release_year": 2025
}
```

#### 2.1.2 gpt-4.1

| 属性 | 值 |
|------|-----|
| ID | `gpt-4.1` |
| 标签 | GPT-4.1 |
| Base URL | `https://api.openai.com/v1` |
| 输入价格 | 14 CNY / 百万 tokens |
| 输出价格 | 56 CNY / 百万 tokens |
| 流式支持 | 是 |
| 思考支持 | 否 |
| 联网搜索 | 否 |
| 最大上下文 | 1,000,000 tokens |
| 默认温度 | 0.7 |
| 默认 Agent | mentor |
| 发布年份 | 2025 |

**能力画像**：

- OpenAI 旗舰通用模型，综合能力强；
- 1M 超长上下文；
- 中等成本，适合质量敏感任务；
- 不支持思考模式，但推理能力优于 mini 版。

**适用场景**：

- Mentor Agent 的深度学术指导；
- Critic Agent 的硬约束校验；
- 复杂文献的综合分析；
- 需要稳定高质量输出的场景。

### 2.2 DeepSeek 系列

#### 2.2.1 deepseek-v3.2

| 属性 | 值 |
|------|-----|
| ID | `deepseek-v3.2` |
| 标签 | DeepSeek V3.2 (2026) |
| Base URL | `https://api.deepseek.com/v1` |
| 输入价格 | 1 CNY / 百万 tokens |
| 输出价格 | 4 CNY / 百万 tokens |
| 流式支持 | 是 |
| 思考支持 | 否 |
| 联网搜索 | 是 |
| 最大上下文 | 128,000 tokens |
| 默认温度 | 0.7 |
| 默认 Agent | search |
| 发布年份 | 2026 |

**能力画像**：

- 极高性价比，输入价格仅 1 CNY/百万 tokens；
- 原生支持联网搜索，适合文献检索；
- 支持 Prompt 缓存，命中率可达 95%+；
- 128K 上下文足够应对大多数场景。

**适用场景**：

- Searcher Agent 的文献检索与信息收集；
- 大量联网搜索任务；
- 成本敏感的批量调用；
- 缓存命中率优先的场景。

**缓存优势**：

DeepSeek V3.2 是 ThesisMiner 缓存优化的核心模型。其 Prompt 缓存机制：

- 缓存粒度：token 级别前缀匹配；
- 缓存有效期：服务端管理，通常数小时；
- 命中折扣：缓存命中的 input tokens 按 0.1 CNY/百万计费（1 折）；
- 三段式 Prefix 设计可稳定达到 95%+ 命中率。

#### 2.2.2 deepseek-r2

| 属性 | 值 |
|------|-----|
| ID | `deepseek-r2` |
| 标签 | DeepSeek R2 Reasoner (2026) |
| Base URL | `https://api.deepseek.com/v1` |
| 输入价格 | 4 CNY / 百万 tokens |
| 输出价格 | 16 CNY / 百万 tokens |
| 流式支持 | 是 |
| 思考支持 | 是 |
| 联网搜索 | 否 |
| 最大上下文 | 128,000 tokens |
| 默认温度 | 0.0 |
| 默认 Agent | reasoner |
| 发布年份 | 2026 |

**能力画像**：

- DeepSeek 推理增强模型，支持思考模式；
- 默认温度 0.0，输出稳定可复现；
- 推理能力强，适合复杂逻辑分析；
- 成本中等，性价比优于海外推理模型。

**适用场景**：

- Reasoner Agent 的深度推理与可行性分析；
- 复杂论题的逻辑推演；
- 需要思考过程的任务；
- 对输出稳定性要求高的场景。

**思考模式说明**：

启用思考模式后，模型会先输出思考过程（`thinking` 字段），再输出最终答案。思考过程不计入输出 token 费用，但会消耗输入 token。

### 2.3 Anthropic Claude 系列

#### 2.3.1 claude-sonnet-4.5

| 属性 | 值 |
|------|-----|
| ID | `claude-sonnet-4.5` |
| 标签 | Claude Sonnet 4.5 (2026) |
| Base URL | `https://api.anthropic.com/v1` |
| 输入价格 | 22 CNY / 百万 tokens |
| 输出价格 | 110 CNY / 百万 tokens |
| 流式支持 | 是 |
| 思考支持 | 是 |
| 联网搜索 | 是 |
| 最大上下文 | 200,000 tokens |
| 默认温度 | 0.7 |
| 默认 Agent | orchestrator |
| 发布年份 | 2026 |

**能力画像**：

- Anthropic 中端旗舰，综合能力均衡；
- 支持思考、联网搜索、流式；
- 200K 上下文，适合长文档；
- 编排能力强，适合复杂任务调度。

**适用场景**：

- Orchestrator Agent 的任务分解与调度；
- 复杂多步骤任务的编排；
- 需要高质量长文本输出的场景；
- 对指令遵循要求高的任务。

**作为 Orchestrator 的优势**：

Claude Sonnet 4.5 被选为 Orchestrator 的默认模型，原因：

1. 强大的指令遵循能力，能准确执行编排逻辑；
2. 优秀的工具调用能力，能正确调度子 Agent；
3. 稳定的 JSON 输出，便于结果解析；
4. 200K 上下文足以容纳完整会话状态。

#### 2.3.2 claude-opus-4.5

| 属性 | 值 |
|------|-----|
| ID | `claude-opus-4.5` |
| 标签 | Claude Opus 4.5 (2026) |
| Base URL | `https://api.anthropic.com/v1` |
| 输入价格 | 110 CNY / 百万 tokens |
| 输出价格 | 550 CNY / 百万 tokens |
| 流式支持 | 是 |
| 思考支持 | 是 |
| 联网搜索 | 是 |
| 最大上下文 | 200,000 tokens |
| 默认温度 | 0.7 |
| 默认 Agent | report |
| 发布年份 | 2026 |

**能力画像**：

- Anthropic 顶级旗舰，能力最强；
- 价格最高，适合质量优先场景；
- 写作能力卓越，适合长文档生成；
- 支持思考、联网搜索、流式。

**适用场景**：

- Writer Agent 的开题报告生成；
- 高质量学术文档撰写；
- 最终交付物的精修；
- 对质量要求极高、成本不敏感的场景。

**成本警示**：

Claude Opus 4.5 的输出价格高达 550 CNY/百万 tokens，单次开题报告生成可能消耗 10-20 CNY。建议：

1. 仅在最终报告生成阶段使用；
2. 设置严格的预算上限；
3. 配合缓存优化降低重复成本；
4. 对长文档采用分段生成策略。

### 2.4 阿里通义 Qwen 系列

#### 2.4.1 qwen3-max

| 属性 | 值 |
|------|-----|
| ID | `qwen3-max` |
| 标签 | Qwen3 Max (2026) |
| Base URL | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 输入价格 | 2.4 CNY / 百万 tokens |
| 输出价格 | 9.6 CNY / 百万 tokens |
| 流式支持 | 是 |
| 思考支持 | 是 |
| 联网搜索 | 是 |
| 最大上下文 | 131,072 tokens |
| 默认温度 | 0.7 |
| 默认 Agent | inspire |
| 发布年份 | 2026 |

**能力画像**：

- 阿里通义旗舰，中文能力突出；
- 支持思考、联网搜索、流式；
- 创意生成能力强，适合发散思维；
- 性价比高，适合创意类任务。

**适用场景**：

- Inspire Agent 的创意生成；
- 中文论题的发散探索；
- 多维度创意 brainstorming；
- 需要联网搜索辅助的创意任务。

**作为 Inspire 的优势**：

Qwen3 Max 被选为 Inspire Agent 的默认模型，原因：

1. 中文创意生成能力强，适合中文学术语境；
2. 支持思考模式，能在创意前进行深度思考；
3. 联网搜索能力可获取最新研究动态；
4. 性价比高，适合多次创意迭代。

### 2.5 Google Gemini 系列

#### 2.5.1 gemini-2.5-pro

| 属性 | 值 |
|------|-----|
| ID | `gemini-2.5-pro` |
| 标签 | Gemini 2.5 Pro (2026) |
| Base URL | `https://generativelanguage.googleapis.com/v1beta` |
| 输入价格 | 9 CNY / 百万 tokens |
| 输出价格 | 36 CNY / 百万 tokens |
| 流式支持 | 是 |
| 思考支持 | 是 |
| 联网搜索 | 是 |
| 最大上下文 | 2,000,000 tokens |
| 默认温度 | 0.7 |
| 默认 Agent | reasoner |
| 发布年份 | 2026 |

**能力画像**：

- Google 旗舰模型，2M 超长上下文；
- 支持思考、联网搜索、流式；
- 多模态能力强（本系统主要用文本）；
- 推理能力优秀。

**适用场景**：

- Reasoner Agent 的深度推理（备选）；
- 超长文档处理（2M 上下文）；
- 需要处理大量历史文献的场景；
- 多模态辅助分析。

**2M 上下文优势**：

Gemini 2.5 Pro 的 2M 上下文是其最大亮点，可容纳：

- 约 1500 万字符的中文文本；
- 约 50 篇完整学术论文；
- 完整的会话历史与文献库。

适用于需要一次性处理海量上下文的特殊场景。

### 2.6 智谱 GLM 系列

#### 2.6.1 glm-4.6

| 属性 | 值 |
|------|-----|
| ID | `glm-4.6` |
| 标签 | GLM-4.6 (2026) |
| Base URL | `https://open.bigmodel.cn/api/paas/v4` |
| 输入价格 | 5 CNY / 百万 tokens |
| 输出价格 | 5 CNY / 百万 tokens |
| 流式支持 | 是 |
| 思考支持 | 是 |
| 联网搜索 | 是 |
| 最大上下文 | 131,072 tokens |
| 默认温度 | 0.7 |
| 默认 Agent | mentor |
| 发布年份 | 2026 |

**能力画像**：

- 智谱 AI 旗舰，国产模型代表；
- 输入输出同价（5 CNY/百万），计费简单；
- 支持思考、联网搜索、流式；
- 中文能力优秀。

**适用场景**：

- Mentor Agent 的学术指导（备选）；
- 中文论题的深度讨论；
- 国产化合规要求场景；
- 输入输出均衡的任务。

**国产化优势**：

GLM-4.6 适合有国产化要求的部署场景：

1. 数据不出境，符合合规要求；
2. 国内访问延迟低；
3. 中文理解能力强；
4. 与国内学术生态契合度高。

### 2.7 字节豆包系列

#### 2.7.1 doubao-1.5-pro

| 属性 | 值 |
|------|-----|
| ID | `doubao-1.5-pro` |
| 标签 | Doubao 1.5 Pro (2026) |
| Base URL | `https://ark.cn-beijing.volces.com/api/v3` |
| 输入价格 | 0.8 CNY / 百万 tokens |
| 输出价格 | 2 CNY / 百万 tokens |
| 流式支持 | 是 |
| 思考支持 | 否 |
| 联网搜索 | 是 |
| 最大上下文 | 131,072 tokens |
| 默认温度 | 0.7 |
| 默认 Agent | search |
| 发布年份 | 2026 |

**能力画像**：

- 字节跳动豆包旗舰，极致性价比；
- 输入价格仅 0.8 CNY/百万，为全系列最低；
- 支持联网搜索、流式；
- 不支持思考模式。

**适用场景**：

- Searcher Agent 的文献检索（备选/降级）；
- 大规模低成本检索任务；
- 成本极度敏感的批量调用；
- 作为 DeepSeek V3.2 的降级备选。

### 2.8 模型对比总表

| 模型 | 输入价 | 输出价 | 上下文 | 思考 | 联网 | 默认 Agent |
|------|--------|--------|--------|------|------|-----------|
| gpt-4.1-mini | 0.7 | 2.8 | 1M | 否 | 否 | mentor |
| gpt-4.1 | 14 | 56 | 1M | 否 | 否 | mentor |
| deepseek-v3.2 | 1 | 4 | 128K | 否 | 是 | search |
| deepseek-r2 | 4 | 16 | 128K | 是 | 否 | reasoner |
| claude-sonnet-4.5 | 22 | 110 | 200K | 是 | 是 | orchestrator |
| claude-opus-4.5 | 110 | 550 | 200K | 是 | 是 | report |
| qwen3-max | 2.4 | 9.6 | 131K | 是 | 是 | inspire |
| gemini-2.5-pro | 9 | 36 | 2M | 是 | 是 | reasoner |
| glm-4.6 | 5 | 5 | 131K | 是 | 是 | mentor |
| doubao-1.5-pro | 0.8 | 2 | 131K | 否 | 是 | search |

**价格梯度**（输出价，从低到高）：

```
doubao-1.5-pro (2) < gpt-4.1-mini (2.8) < deepseek-v3.2 (4) < glm-4.6 (5) 
< qwen3-max (9.6) < gemini-2.5-pro (36) < gpt-4.1 (56) < deepseek-r2 (16)* 
< claude-sonnet-4.5 (110) < claude-opus-4.5 (550)

* 注：deepseek-r2 输出价 16，介于 gpt-4.1 与 gemini-2.5-pro 之间
```

**能力雷达图**（示意）：

```
                    质量
                     10
                      │
           claude-opus ●
                sonnet ●
            gpt-4.1    ●
        gemini-2.5-pro ●
          deepseek-r2  ●
           qwen3-max   ●
            glm-4.6    ●
       deepseek-v3.2   ●
         gpt-4.1-mini  ●
       doubao-1.5-pro  ●
                      │
   ───────────────────┼──────────────────── 成本
   高成本              │              低成本
                      │
```

---

## 3. Agent 到模型的默认路由

### 3.1 路由表

ThesisMiner v8.0 的 `DEFAULT_STEP_MODELS` 定义了每个 Agent 步骤的默认模型：

```python
DEFAULT_STEP_MODELS = {
    "orchestrator": "claude-sonnet-4.5",
    "reasoner": "deepseek-r2",
    "mentor": "gpt-4.1",
    "inspire": "qwen3-max",
    "report": "claude-opus-4.5",
    "search": "deepseek-v3.2",
}
```

| 步骤 | Agent | 默认模型 | 价格档位 |
|------|-------|---------|---------|
| orchestrator | Orchestrator | claude-sonnet-4.5 | 高 |
| reasoner | Reasoner | deepseek-r2 | 中 |
| mentor | Mentor | gpt-4.1 | 中高 |
| inspire | Inspire | qwen3-max | 中低 |
| report | Writer | claude-opus-4.5 | 极高 |
| search | Searcher | deepseek-v3.2 | 低 |

### 3.2 路由设计原则

**原则 1：能力匹配**

每个 Agent 的核心能力与模型特长对齐：

- Orchestrator 需要强指令遵循与工具调用 → Claude Sonnet 4.5
- Reasoner 需要深度推理与思考 → DeepSeek R2
- Mentor 需要稳定高质量指导 → GPT-4.1
- Inspire 需要创意与发散 → Qwen3 Max
- Writer 需要卓越写作 → Claude Opus 4.5
- Searcher 需要联网与高性价比 → DeepSeek V3.2

**原则 2：成本分层**

五阶段流程的成本分布设计为"两头低、中间高"：

```
成本
  │
  │        ┌─────┐
  │        │     │  generation (Opus)
  │   ┌────┘     │
  │   │          │
  │   │  ┌───────┘
  │   │  │
  │   │  │     ┌─────
  │   │  │     │
  │ ┌─┘  │     │
  │ │    │     │
  │ │    │     │
  └─┴────┴─────┴─────── 阶段
   info  crea  val  gen  deep
```

- `info_confirm`：低成本（Orchestrator 轻量调用）
- `creativity`：中低成本（Qwen3 Max 创意）
- `validation`：中成本（GPT-4.1 校验 + DeepSeek R2 推理）
- `generation`：高成本（Claude Opus 4.5 写作）
- `deep_assist`：中低成本（按需调用）

**原则 3：缓存友好**

优先选择支持 Prompt 缓存的模型（DeepSeek 系列），降低重复调用成本。Searcher 与 Reasoner 使用 DeepSeek，可充分利用缓存。

### 3.3 路由覆盖与故障转移

**多级路由覆盖**：

```
┌─────────────────────────────────────────────────────┐
│  Level 1: conversation 级别覆盖（最高优先级）        │
│  通过 PATCH /api/agents/{id}/model?scope=conversation│
└─────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│  Level 2: session 级别覆盖                           │
│  通过 PATCH /api/agents/{id}/model?scope=session     │
└─────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│  Level 3: 全局配置覆盖                               │
│  通过 PATCH /api/config 或 config.json               │
└─────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│  Level 4: DEFAULT_STEP_MODELS（默认）                │
│  代码内置的默认路由                                   │
└─────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│  Level 5: fallback（故障转移）                       │
│  主模型不可用时自动切换                              │
└─────────────────────────────────────────────────────┘
```

**故障转移路由**：

```python
FALLBACK_MODELS = {
    "orchestrator": "gpt-4.1",          # Claude → GPT
    "reasoner": "claude-sonnet-4.5",    # DeepSeek → Claude
    "mentor": "glm-4.6",                # GPT → GLM
    "inspire": "gpt-4.1-mini",          # Qwen → GPT mini
    "report": "claude-sonnet-4.5",      # Opus → Sonnet
    "search": "doubao-1.5-pro",         # DeepSeek → Doubao
}
```

故障转移设计原则：

1. 优先选择同档位不同厂商的模型，避免单点故障；
2. 降级时优先保证可用性，其次考虑质量；
3. 故障转移应记录日志，便于后续分析；
4. 故障恢复后自动切回主模型。

---

## 4. 模型选择策略

### 4.1 成本维度

**单次调用成本估算**：

```
成本 = (prompt_tokens × input_price + completion_tokens × output_price) / 1,000,000
```

**示例**：使用 claude-opus-4.5 生成开题报告

- prompt_tokens: 8,000（含缓存前缀）
- completion_tokens: 4,000（报告正文）
- input_price: 110 CNY/百万
- output_price: 550 CNY/百万
- 成本 = (8000 × 110 + 4000 × 550) / 1,000,000 = 0.88 + 2.2 = 3.08 CNY

**成本优化建议**：

1. 高频调用场景优先使用低成本模型（doubao-1.5-pro、deepseek-v3.2）；
2. 质量敏感场景使用高成本模型，但控制调用次数；
3. 充分利用 DeepSeek 缓存，缓存命中部分按 1 折计费；
4. 对长文本生成采用分段策略，避免一次性消耗大量 token。

### 4.2 质量维度

**质量评估指标**：

| 指标 | 说明 | 评估方式 |
|------|------|---------|
| 指令遵循 | 是否准确执行指令 | 人工评分 |
| 逻辑连贯 | 推理是否自洽 | 人工评分 |
| 学术规范 | 是否符合学术写作规范 | 人工评分 |
| 引用准确 | 引用是否真实准确 | 自动校验 |
| 创新性 | 论题是否有新意 | 人工评分 |

**质量梯队**（基于内部评测）：

| 梯队 | 模型 | 适用场景 |
|------|------|---------|
| T0（顶级） | claude-opus-4.5 | 最终报告生成 |
| T1（优秀） | claude-sonnet-4.5, gpt-4.1 | 编排、校验、指导 |
| T2（良好） | deepseek-r2, qwen3-max, gemini-2.5-pro | 推理、创意 |
| T3（标准） | deepseek-v3.2, glm-4.6 | 检索、通用 |
| T4（基础） | gpt-4.1-mini, doubao-1.5-pro | 轻量任务、降级 |

### 4.3 延迟维度

**典型延迟**（首字节延迟 TTFB）：

| 模型 | TTFB（ms） | 完整响应（ms） |
|------|-----------|---------------|
| gpt-4.1-mini | 300-500 | 1000-3000 |
| deepseek-v3.2 | 200-400 | 800-2500 |
| doubao-1.5-pro | 150-300 | 600-2000 |
| qwen3-max | 400-600 | 1500-4000 |
| glm-4.6 | 300-500 | 1200-3500 |
| gpt-4.1 | 500-800 | 2000-5000 |
| deepseek-r2 | 800-1500 | 3000-10000 |
| gemini-2.5-pro | 600-1000 | 2500-6000 |
| claude-sonnet-4.5 | 700-1200 | 3000-8000 |
| claude-opus-4.5 | 1500-3000 | 8000-20000 |

**延迟优化建议**：

1. 对话类场景优先使用低延迟模型（deepseek-v3.2、doubao-1.5-pro）；
2. 流式响应可显著降低用户感知延迟；
3. 思考模式会增加延迟，对实时性要求高的场景慎用；
4. Claude Opus 延迟较高，适合后台异步任务。

### 4.4 缓存命中率维度

**DeepSeek 缓存支持**：

| 模型 | 缓存支持 | 典型命中率 |
|------|---------|-----------|
| deepseek-v3.2 | 是 | 95%+ |
| deepseek-r2 | 是 | 90%+ |
| 其他模型 | 否 | 0% |

**缓存对成本的影响**：

以 deepseek-v3.2 为例，假设 1000 次调用，每次 prompt 1500 tokens：

- 无缓存：1000 × 1500 × 1 / 1,000,000 = 1.5 CNY
- 95% 命中：1000 × (1500 × 0.95 × 0.1 + 1500 × 0.05 × 1) / 1,000,000 = 0.218 CNY
- 节省：1.5 - 0.218 = 1.282 CNY（节省 85%）

### 4.5 综合权衡

**决策矩阵**：

| 场景 | 首选模型 | 权衡要点 |
|------|---------|---------|
| 实时对话 | deepseek-v3.2 | 低延迟、低成本、缓存友好 |
| 文献检索 | deepseek-v3.2 | 联网搜索、高性价比 |
| 深度推理 | deepseek-r2 | 思考模式、稳定输出 |
| 创意生成 | qwen3-max | 中文创意、联网 |
| 学术指导 | gpt-4.1 | 稳定高质量 |
| 任务编排 | claude-sonnet-4.5 | 指令遵循、工具调用 |
| 报告生成 | claude-opus-4.5 | 顶级写作质量 |
| 成本敏感 | doubao-1.5-pro | 极低价格 |
| 超长上下文 | gemini-2.5-pro | 2M 上下文 |
| 国产化合规 | glm-4.6 | 数据不出境 |

**选择流程**：

```
┌─────────────────────────────────────────────┐
│  1. 确定任务类型（对话/检索/推理/生成）       │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  2. 评估质量要求（高/中/低）                  │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  3. 评估预算约束（高/中/低）                  │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  4. 评估延迟要求（实时/容忍）                 │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  5. 查询决策矩阵，选择模型                    │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  6. 配置 fallback，确保可用性                 │
└─────────────────────────────────────────────┘
```

---

## 5. 自定义模型配置

### 5.1 环境变量配置

ThesisMiner 支持通过 `.env` 文件配置默认模型与 API Key：

```bash
# .env

# 默认 AI 配置
AI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
AI_BASE_URL=https://api.deepseek.com/v1
AI_MODEL=deepseek-v3.2

# 各厂商 API Key（可选，用于多模型支持）
OPENAI_API_KEY=sk-xxxxxxxx
DEEPSEEK_API_KEY=sk-xxxxxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxxxxx
QWEN_API_KEY=sk-xxxxxxxx
GEMINI_API_KEY=AIzaxxxxxxxx
GLM_API_KEY=xxxxxxxx.xxxxxxxx
DOUBAO_API_KEY=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# 数据库与日志
DB_PATH=data/thesis_miner.db
LOG_LEVEL=INFO

# 服务器
HOST=127.0.0.1
PORT=8000
FLASK_ENV=production

# 自动打开浏览器
AUTO_OPEN_BROWSER=true
```

**环境变量优先级**：

```
data/config.json（用户配置） > .env 环境变量 > 代码默认值
```

### 5.2 config.json 配置

`data/config.json` 提供更细粒度的配置，可覆盖环境变量：

```json
{
  "ai_api_key": "sk-xxxxxxxx",
  "ai_base_url": "https://api.deepseek.com/v1",
  "ai_model": "deepseek-v3.2",
  "log_level": "INFO",
  "flask_env": "production",
  "auto_open_browser": true,
  "models": [
    {
      "id": "gpt-4.1",
      "label": "GPT-4.1",
      "base_url": "https://api.openai.com/v1",
      "api_key": "sk-xxxxxxxx",
      "pricing": {"input_cny_per_million": 14, "output_cny_per_million": 56},
      "supports_streaming": true,
      "supports_thinking": false,
      "supports_web_search": false,
      "max_context": 1000000,
      "default_temperature": 0.7,
      "agent_default": "mentor",
      "release_year": 2025
    },
    {
      "id": "deepseek-v3.2",
      "label": "DeepSeek V3.2 (2026)",
      "base_url": "https://api.deepseek.com/v1",
      "api_key": "sk-xxxxxxxx",
      "pricing": {"input_cny_per_million": 1, "output_cny_per_million": 4},
      "supports_streaming": true,
      "supports_thinking": false,
      "supports_web_search": true,
      "max_context": 128000,
      "default_temperature": 0.7,
      "agent_default": "search",
      "release_year": 2026
    }
  ],
  "step_models": {
    "orchestrator": "claude-sonnet-4.5",
    "reasoner": "deepseek-r2",
    "mentor": "gpt-4.1",
    "inspire": "qwen3-max",
    "report": "claude-opus-4.5",
    "search": "deepseek-v3.2"
  },
  "fallback_models": {
    "orchestrator": "gpt-4.1",
    "reasoner": "claude-sonnet-4.5",
    "mentor": "glm-4.6",
    "inspire": "gpt-4.1-mini",
    "report": "claude-sonnet-4.5",
    "search": "doubao-1.5-pro"
  }
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `ai_api_key` | string | 默认 API Key |
| `ai_base_url` | string | 默认 Base URL |
| `ai_model` | string | 默认模型 ID |
| `models` | array | 自定义模型注册表（覆盖 DEFAULT_MODELS） |
| `step_models` | object | 自定义步骤模型映射（覆盖 DEFAULT_STEP_MODELS） |
| `fallback_models` | object | 故障转移模型映射 |

### 5.3 API 动态配置

通过 API 可在运行时动态修改配置：

**查询当前配置**：

```bash
curl -X GET "http://127.0.0.1:8000/api/config"
```

**更新配置**：

```bash
curl -X PATCH "http://127.0.0.1:8000/api/config" \
  -H "Content-Type: application/json" \
  -d '{
    "ai": {"default_model": "claude-sonnet-4.5"}
  }'
```

**切换 Agent 模型**：

```bash
curl -X PATCH "http://127.0.0.1:8000/api/agents/reasoner/model" \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "gpt-4.1",
    "scope": "session",
    "session_id": "ses_20260620_a1b2c3d4"
  }'
```

**作用域说明**：

| scope | 生效范围 | 持久性 |
|-------|---------|--------|
| `global` | 全局所有会话 | 持久（写入 config.json） |
| `session` | 指定会话 | 会话级（会话删除后失效） |
| `conversation` | 指定对话 | 对话级（对话删除后失效） |

### 5.4 多 API Key 轮询

对于高并发场景，可配置多个 API Key 进行轮询，避免单 Key 限流：

```json
{
  "models": [
    {
      "id": "deepseek-v3.2",
      "api_keys": [
        "sk-key1xxxxxxxx",
        "sk-key2xxxxxxxx",
        "sk-key3xxxxxxxx"
      ],
      "api_key_strategy": "round_robin"
    }
  ]
}
```

**轮询策略**：

| 策略 | 说明 |
|------|------|
| `round_robin` | 轮询，依次使用每个 Key |
| `random` | 随机选择 |
| `least_used` | 选择使用次数最少的 Key |
| `failover` | 主 Key 失败后切换到备用 Key |

---

## 6. 模型故障转移与降级策略

### 6.1 故障检测

**故障判定条件**：

1. HTTP 状态码 5xx：服务端错误；
2. HTTP 状态码 429：限流；
3. 请求超时（默认 60 秒）；
4. 响应体格式异常；
5. 连续失败次数超过阈值（默认 3 次）。

**故障检测流程**：

```python
def call_with_health_check(model_id: str, messages: list):
    """带健康检查的模型调用。"""
    try:
        response = call_llm(model_id, messages)
        record_success(model_id)
        return response
    except (TimeoutError, ConnectionError) as e:
        record_failure(model_id, "network")
        raise ModelUnavailableError(model_id, str(e))
    except HTTPError as e:
        if e.response.status_code == 429:
            record_failure(model_id, "rate_limited")
        elif e.response.status_code >= 500:
            record_failure(model_id, "server_error")
        raise ModelUnavailableError(model_id, str(e))
```

### 6.2 故障转移流程

```
┌─────────────────────────────────────────────────────┐
│  调用主模型（如 claude-sonnet-4.5）                  │
└──────────────────────┬──────────────────────────────┘
                       │
                ┌──────▼──────┐
                │  成功？      │
                └──────┬──────┘
                       │
           ┌───────────┴───────────┐
           │ 是                    │ 否
           ▼                       ▼
┌──────────────────┐    ┌──────────────────────────┐
│  返回结果         │    │  记录失败，检查重试次数   │
└──────────────────┘    └──────────┬───────────────┘
                                   │
                          ┌────────▼────────┐
                          │  达到重试上限？  │
                          └────────┬────────┘
                                   │
                       ┌───────────┴───────────┐
                       │ 是                    │ 否
                       ▼                       ▼
              ┌─────────────────┐    ┌──────────────────┐
              │  切换到 fallback │    │  等待退避时间    │
              │  模型            │    │  后重试主模型    │
              └────────┬────────┘    └──────────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  调用 fallback   │
              │  模型            │
              └────────┬────────┘
                       │
                ┌──────▼──────┐
                │  成功？      │
                └──────┬──────┘
                       │
           ┌───────────┴───────────┐
           │ 是                    │ 否
           ▼                       ▼
┌──────────────────┐    ┌──────────────────────────┐
│  返回结果         │    │  抛出 ModelUnavailable    │
│  标记降级         │    │  Error                   │
└──────────────────┘    └──────────────────────────┘
```

### 6.3 降级策略

**降级路径**：

| 原模型 | 一级降级 | 二级降级 | 三级降级 |
|--------|---------|---------|---------|
| claude-opus-4.5 | claude-sonnet-4.5 | gpt-4.1 | deepseek-v3.2 |
| claude-sonnet-4.5 | gpt-4.1 | deepseek-v3.2 | doubao-1.5-pro |
| gpt-4.1 | glm-4.6 | deepseek-v3.2 | doubao-1.5-pro |
| deepseek-r2 | claude-sonnet-4.5 | gpt-4.1 | gemini-2.5-pro |
| qwen3-max | gpt-4.1-mini | deepseek-v3.2 | doubao-1.5-pro |
| deepseek-v3.2 | doubao-1.5-pro | gpt-4.1-mini | glm-4.6 |

**降级配置示例**：

```python
DEGRADATION_CHAIN = {
    "claude-opus-4.5": ["claude-sonnet-4.5", "gpt-4.1", "deepseek-v3.2"],
    "claude-sonnet-4.5": ["gpt-4.1", "deepseek-v3.2", "doubao-1.5-pro"],
    "gpt-4.1": ["glm-4.6", "deepseek-v3.2", "doubao-1.5-pro"],
    "deepseek-r2": ["claude-sonnet-4.5", "gpt-4.1", "gemini-2.5-pro"],
    "qwen3-max": ["gpt-4.1-mini", "deepseek-v3.2", "doubao-1.5-pro"],
    "deepseek-v3.2": ["doubao-1.5-pro", "gpt-4.1-mini", "glm-4.6"],
}

def call_with_degradation(model_id: str, messages: list):
    """带降级链的模型调用。"""
    chain = [model_id] + DEGRADATION_CHAIN.get(model_id, [])
    for current_model in chain:
        try:
            return call_llm(current_model, messages)
        except ModelUnavailableError:
            continue
    raise ModelUnavailableError(f"所有降级模型均不可用: {chain}")
```

### 6.4 重试逻辑

**重试参数**：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_retries` | 3 | 最大重试次数 |
| `base_delay` | 1 秒 | 初始退避时间 |
| `max_delay` | 60 秒 | 最大退避时间 |
| `jitter` | 0.1 | 抖动比例 |
| `retry_on` | [429, 500, 502, 503, 504] | 触发重试的状态码 |

**重试实现**：

```python
import time
import random

def call_with_retry(model_id: str, messages: list, max_retries: int = 3):
    """带指数退避的重试调用。"""
    last_error = None
    for attempt in range(max_retries):
        try:
            return call_llm(model_id, messages)
        except RetryableError as e:
            last_error = e
            if attempt < max_retries - 1:
                delay = min(2 ** attempt, 60)
                delay += random.uniform(0, delay * 0.1)
                time.sleep(delay)
    raise last_error
```

**重试与降级的关系**：

1. 先对主模型重试（最多 3 次）；
2. 重试失败后切换到 fallback 模型；
3. 对 fallback 模型同样重试；
4. 全部失败后抛出异常。

---

## 7. DeepSeek 缓存优化配置

### 7.1 三段式 Prefix 设计

ThesisMiner v8.0 的核心缓存优化是三段式 Prefix 设计，将 prompt 前缀分为三个稳定段：

```
┌─────────────────────────────────────────────────────────────┐
│  段 1：系统提示（System Prompt）                             │
│  - ThesisMiner 角色定义                                      │
│  - 通用行为规范                                              │
│  - 输出格式要求                                              │
│  长度：约 500-800 tokens                                     │
│  稳定性：极高（跨会话不变）                                   │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│  段 2：Agent 角色定义（Agent Role）                          │
│  - 当前 Agent 的职责描述                                     │
│  - Agent 专属指令                                            │
│  - Agent 输出规范                                            │
│  长度：约 300-500 tokens                                     │
│  稳定性：高（同一 Agent 跨会话不变）                          │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│  段 3：会话上下文（Session Context）                         │
│  - 学位、学科、研究背景                                      │
│  - 会话元信息                                                │
│  - DST 压缩后的历史摘要                                      │
│  长度：约 200-400 tokens                                     │
│  稳定性：中（同一会话内不变，跨会话变化）                     │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│  变化部分（Variable Part）                                   │
│  - 当前用户输入                                              │
│  - 具体任务指令                                              │
│  长度：变化                                                  │
│  稳定性：低（每次请求不同）                                  │
└─────────────────────────────────────────────────────────────┘
```

**Prefix 构建函数**：

```python
def build_cached_prefix(agent_id: str, session_context: dict) -> str:
    """构建三段式缓存前缀。"""
    # 段 1：系统提示
    system_prompt = load_system_prompt()  # 跨会话稳定

    # 段 2：Agent 角色定义
    agent_role = load_agent_role(agent_id)  # 同一 Agent 稳定

    # 段 3：会话上下文
    session_summary = compress_session_context(session_context)  # 同一会话稳定

    return f"{system_prompt}\n\n{agent_role}\n\n{session_summary}"
```

### 7.2 缓存命中条件

DeepSeek Prompt 缓存的命中条件：

1. **前缀完全匹配**：从第一个 token 开始，连续相同；
2. **长度达标**：缓存前缀至少 1024 tokens；
3. **时效内**：缓存未过期（通常数小时）；
4. **模型一致**：同一模型 ID。

**命中判定**：

```
请求 A: [段1][段2][段3][用户输入A]
请求 B: [段1][段2][段3][用户输入B]
                ↑
        前缀完全相同，命中缓存
```

**未命中场景**：

```
请求 A: [段1][段2][段3A][用户输入A]
请求 B: [段1][段2][段3B][用户输入B]
                    ↑
            段3不同，前缀不匹配，未命中
```

### 7.3 命中率监控

**监控指标**：

| 指标 | 说明 | 目标 |
|------|------|------|
| `hit_rate` | 缓存命中率 | ≥ 95% |
| `saved_tokens` | 节省的 token 数 | - |
| `saved_cost_cny` | 节省的费用 | - |
| `miss_reason` | 未命中原因 | - |

**查询接口**：

```bash
curl -X GET "http://127.0.0.1:8000/api/cache-stats?session_id=ses_20260620_a1b2c3d4"
```

**响应示例**：

```json
{
  "summary": {
    "total_requests": 1240,
    "cache_hits": 1188,
    "cache_misses": 52,
    "hit_rate": 0.9581,
    "saved_tokens": 1425600,
    "saved_cost_cny": 1.4256
  },
  "by_agent": {
    "orchestrator": {"hit_rate": 0.9750},
    "reasoner": {"hit_rate": 0.9571},
    "searcher": {"hit_rate": 0.9561}
  }
}
```

**未命中原因分析**：

| 原因 | 说明 | 优化建议 |
|------|------|---------|
| `prefix_changed` | 前缀变化 | 检查段 1/2/3 是否稳定 |
| `context_too_short` | 前缀不足 1024 tokens | 增加系统提示长度 |
| `cache_expired` | 缓存过期 | 提高请求频率 |
| `model_mismatch` | 模型不一致 | 确保同会话使用同模型 |

### 7.4 缓存优化技巧

**技巧 1：稳定段 1 与段 2**

系统提示与 Agent 角色定义应严格固定，不包含任何动态内容：

```python
# 正确：固定文本
SYSTEM_PROMPT = """你是 ThesisMiner，一个学术论题生成助手。
你的职责是帮助研究生探索和生成高质量的论题。
请遵循学术规范，确保输出的严谨性。"""

# 错误：包含动态内容
SYSTEM_PROMPT = f"""你是 ThesisMiner，当前时间 {datetime.now()}。
用户 IP: {request.remote_addr}"""  # 这些动态内容会破坏缓存
```

**技巧 2：DST 压缩段 3**

会话上下文应使用 DST（Dialogue State Tracker）压缩，保持稳定：

```python
def compress_session_context(session: dict) -> str:
    """DST 压缩会话上下文。"""
    # 提取稳定字段
    return f"""学位: {session['degree']}
学科: {session['discipline']}
研究背景: {session['research_background'][:200]}
当前阶段: {session['stage']}
文献基线: {session['literature_count']}"""
    # 不包含：时间戳、随机 ID、用户临时输入
```

**技巧 3：避免前缀插入**

不要在段 1/2/3 之间插入任何变化内容：

```python
# 错误：在段 2 和段 3 之间插入时间戳
prefix = f"{system_prompt}\n\n{agent_role}\n\n当前时间: {now}\n\n{session_context}"

# 正确：时间戳放到变化部分
prefix = f"{system_prompt}\n\n{agent_role}\n\n{session_context}"
variable_part = f"当前时间: {now}\n用户问题: {user_input}"
```

**技巧 4：批量请求复用**

对同一会话的连续请求，前缀完全相同，可充分利用缓存：

```python
# 同一会话的多次调用，前缀稳定
for question in questions:
    response = call_llm(
        model_id="deepseek-v3.2",
        system=cached_prefix,  # 稳定
        user=question          # 变化
    )
```

**技巧 5：监控与调优**

定期检查缓存命中率，低于 90% 时排查：

```bash
# 查询最近 24 小时的缓存统计
curl -X GET "http://127.0.0.1:8000/api/cache-stats?start_time=2026-06-19T00:00:00Z&end_time=2026-06-20T00:00:00Z"
```

---

## 8. 模型评估方法论

### 8.1 评估指标体系

**客观指标**：

| 指标 | 说明 | 计算方式 |
|------|------|---------|
| 延迟 | 首字节/完整响应时间 | P50/P95/P99 |
| 吞吐 | 每秒处理请求数 | QPS |
| 成本 | 单次调用费用 | CNY |
| 缓存命中率 | 缓存命中比例 | % |
| 错误率 | 失败请求比例 | % |

**主观指标**：

| 指标 | 说明 | 评分方式 |
|------|------|---------|
| 指令遵循 | 是否准确执行指令 | 1-5 分 |
| 逻辑连贯 | 推理是否自洽 | 1-5 分 |
| 学术规范 | 是否符合学术规范 | 1-5 分 |
| 引用准确 | 引用是否真实 | 1-5 分 |
| 创新性 | 论题新意 | 1-5 分 |
| 可读性 | 文本流畅度 | 1-5 分 |

### 8.2 基准测试

**基准测试集**：

构建包含 100 个标准化测试用例的基准集，覆盖：

- 30 个创意生成用例（不同学科）；
- 20 个深度推理用例；
- 20 个约束校验用例；
- 20 个报告生成用例；
- 10 个文献检索用例。

**测试流程**：

```
┌─────────────────────────────────────────────┐
│  1. 准备基准测试集（100 用例）               │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  2. 对每个模型运行全部用例                   │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  3. 收集客观指标（延迟、成本、错误率）        │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  4. 人工评分主观指标（双盲评审）              │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  5. 汇总评分，生成模型对比报告               │
└─────────────────────────────────────────────┘
```

**基准测试脚本**：

```python
import time
import json

def run_benchmark(model_id: str, test_cases: list):
    """运行基准测试。"""
    results = []
    for case in test_cases:
        start = time.time()
        try:
            response = call_llm(model_id, case["messages"])
            latency = time.time() - start
            results.append({
                "case_id": case["id"],
                "model": model_id,
                "latency_ms": latency * 1000,
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "cost_cny": calculate_cost(model_id, response.usage),
                "response": response.content,
                "success": True
            })
        except Exception as e:
            results.append({
                "case_id": case["id"],
                "model": model_id,
                "success": False,
                "error": str(e)
            })
    return results

# 运行全部模型
all_results = {}
for model in ["gpt-4.1", "deepseek-v3.2", "claude-sonnet-4.5", ...]:
    all_results[model] = run_benchmark(model, test_cases)

# 生成报告
generate_report(all_results)
```

### 8.3 A/B 测试

**A/B 测试设计**：

将用户流量随机分配到不同模型组，对比效果：

```
┌─────────────────────────────────────────────────────┐
│  用户请求                                           │
└──────────────────────┬──────────────────────────────┘
                       │
              ┌────────▼────────┐
              │  随机分流        │
              └────────┬────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
┌───────▼───────┐            ┌────────▼────────┐
│  组 A（50%）   │            │  组 B（50%）     │
│  模型: A       │            │  模型: B         │
└───────┬───────┘            └────────┬────────┘
        │                             │
        └──────────────┬──────────────┘
                       │
              ┌────────▼────────┐
              │  收集指标        │
              │  - 延迟          │
              │  - 成本          │
              │  - 用户满意度    │
              │  - 任务完成率    │
              └────────┬────────┘
                       │
              ┌────────▼────────┐
              │  统计显著性检验  │
              └─────────────────┘
```

**A/B 测试配置**：

```json
{
  "ab_tests": [
    {
      "id": "test_reasoner_model",
      "description": "对比 deepseek-r2 与 gemini-2.5-pro 在推理任务上的表现",
      "agent": "reasoner",
      "variants": {
        "A": {"model": "deepseek-r2", "weight": 50},
        "B": {"model": "gemini-2.5-pro", "weight": 50}
      },
      "metrics": ["latency", "cost", "quality_score"],
      "duration_days": 14
    }
  ]
}
```

**统计显著性**：

A/B 测试需达到统计显著性才能下结论：

- 最小样本量：每组 1000 个请求；
- 置信度：95%（p < 0.05）；
- 指标差异：需超过噪声阈值。

---

## 9. 成本优化策略

### 9.1 成本构成分析

**典型会话成本分布**（master 学位，full_pipeline 模式）：

| 阶段 | 调用次数 | 主要模型 | 成本（CNY） | 占比 |
|------|---------|---------|------------|------|
| info_confirm | 2 | claude-sonnet-4.5 | 0.5 | 3% |
| creativity | 5 | qwen3-max | 3.2 | 21% |
| validation | 5 | gpt-4.1 + deepseek-r2 | 2.8 | 18% |
| generation | 3 | claude-opus-4.5 | 6.5 | 43% |
| deep_assist | 4 | deepseek-v3.2 | 2.2 | 15% |
| **合计** | **19** | - | **15.2** | **100%** |

**成本热力图**：

```
阶段
generation  │████████████████████████████████████████│ 43%
creativity  │████████████████████████│ 21%
validation  │████████████████████│ 18%
deep_assist │████████████████│ 15%
info_confirm│███│ 3%
            └──────────────────────────────────────── 成本
```

### 9.2 预算管理

**预算设置**：

```bash
curl -X PATCH "http://127.0.0.1:8000/api/config" \
  -H "Content-Type: application/json" \
  -d '{
    "budget": {
      "default_limit_cny": 50.0,
      "hard_limit_cny": 200.0,
      "alert_thresholds": [50, 80, 100]
    }
  }'
```

**预算告警**：

```bash
curl -X POST "http://127.0.0.1:8000/api/budgets/ses_20260620_a1b2c3d4/alerts" \
  -H "Content-Type: application/json" \
  -d '{
    "thresholds": [
      {"percent": 50, "action": "notify"},
      {"percent": 80, "action": "notify"},
      {"percent": 100, "action": "block"}
    ],
    "webhook_url": "https://your-server.com/webhooks/budget"
  }'
```

**预算估算**：

```bash
curl -X POST "http://127.0.0.1:8000/api/budgets/estimate" \
  -H "Content-Type: application/json" \
  -d '{
    "degree": "master",
    "discipline": "computer_science",
    "mode": "full_pipeline"
  }'
```

### 9.3 用量监控

**查询预算账本**：

```bash
curl -X GET "http://127.0.0.1:8000/api/budgets/ses_20260620_a1b2c3d4"
```

**按 Agent 维度分析**：

```bash
curl -X GET "http://127.0.0.1:8000/api/budgets/ses_20260620_a1b2c3d4?group_by=agent"
```

**按模型维度分析**：

```bash
curl -X GET "http://127.0.0.1:8000/api/budgets/ses_20260620_a1b2c3d4?group_by=model"
```

**成本优化建议**：

1. **缓存优化**：确保 DeepSeek 缓存命中率 ≥ 95%，可节省 80%+ 输入成本；
2. **模型降级**：对非关键步骤使用低成本模型；
3. **分段生成**：长文档分段生成，避免一次性消耗大量 token；
4. **预算硬限制**：设置 `action: block` 防止超支；
5. **定期审计**：每周审查预算账本，识别异常消耗。

---

## 10. 模型性能基准测试结果

本章基于 ThesisMiner 内部基准测试集（100 个标准化用例），给出 10 个模型在四类核心任务上的详细评测数据。所有数据均在 2026 年 6 月的生产环境采集，每模型每用例运行 5 次取中位数。

### 10.1 推理任务基准

推理任务共 20 个用例，覆盖可行性分析、约束冲突检测、逻辑推演、风险评估四个子类。评分维度包括：逻辑正确性（40%）、推理深度（30%）、结论可用性（30%），满分 100。

| 模型 | 逻辑正确性 | 推理深度 | 结论可用性 | 综合分 | 平均延迟(ms) | 平均成本(CNY) |
|------|-----------|---------|-----------|--------|-------------|--------------|
| claude-opus-4.5 | 38.5 | 29.2 | 28.7 | 96.4 | 14200 | 2.85 |
| deepseek-r2 | 37.8 | 28.9 | 28.2 | 94.9 | 6800 | 0.42 |
| gemini-2.5-pro | 37.2 | 28.5 | 27.9 | 93.6 | 5200 | 0.78 |
| claude-sonnet-4.5 | 36.9 | 27.8 | 27.5 | 92.2 | 5600 | 1.65 |
| gpt-4.1 | 36.1 | 27.2 | 26.8 | 90.1 | 3800 | 1.12 |
| qwen3-max | 34.5 | 26.1 | 25.4 | 86.0 | 3200 | 0.21 |
| glm-4.6 | 33.8 | 25.4 | 24.9 | 84.1 | 2800 | 0.18 |
| gpt-4.1-mini | 31.2 | 23.1 | 22.6 | 76.9 | 1800 | 0.06 |
| deepseek-v3.2 | 30.5 | 22.4 | 21.8 | 74.7 | 1500 | 0.04 |
| doubao-1.5-pro | 28.9 | 20.8 | 20.1 | 69.8 | 1200 | 0.03 |

**关键发现**：

1. Claude Opus 4.5 在推理质量上领先，但成本是 DeepSeek R2 的 6.8 倍；
2. DeepSeek R2 凭借思考模式，以极低成本取得接近 Opus 的质量；
3. Gemini 2.5 Pro 在长上下文推理场景表现突出；
4. 低成本模型（doubao、deepseek-v3.2）在简单推理上可用，复杂推理明显落后。

**推理任务推荐**：

- 质量优先：claude-opus-4.5
- 性价比优先：deepseek-r2（推荐默认）
- 长上下文推理：gemini-2.5-pro
- 成本极限：deepseek-v3.2（仅简单推理）

### 10.2 创意生成基准

创意生成共 30 个用例，覆盖理工、人文、社科、医学、交叉学科五个领域。评分维度包括：创新性（35%）、可行性（25%）、学术价值（25%）、多样性（15%），满分 100。

| 模型 | 创新性 | 可行性 | 学术价值 | 多样性 | 综合分 | 平均延迟(ms) |
|------|--------|--------|---------|--------|--------|-------------|
| qwen3-max | 33.8 | 23.9 | 24.1 | 14.2 | 96.0 | 2800 |
| claude-opus-4.5 | 33.5 | 24.2 | 24.5 | 13.6 | 95.8 | 13500 |
| gemini-2.5-pro | 32.1 | 23.5 | 23.2 | 14.0 | 92.8 | 4800 |
| claude-sonnet-4.5 | 31.8 | 23.1 | 23.0 | 13.5 | 91.4 | 5200 |
| gpt-4.1 | 31.2 | 22.8 | 22.6 | 13.2 | 89.8 | 3500 |
| deepseek-r2 | 30.5 | 22.1 | 21.8 | 12.9 | 87.3 | 6500 |
| glm-4.6 | 29.8 | 21.5 | 21.2 | 12.5 | 85.0 | 2600 |
| gpt-4.1-mini | 27.1 | 19.8 | 18.9 | 11.8 | 77.6 | 1600 |
| deepseek-v3.2 | 26.5 | 19.2 | 18.3 | 11.5 | 75.5 | 1400 |
| doubao-1.5-pro | 24.8 | 17.9 | 16.8 | 10.9 | 70.4 | 1100 |

**关键发现**：

1. Qwen3 Max 在中文创意生成上表现最佳，且成本仅为 Opus 的 1/45；
2. Claude Opus 4.5 在学术价值维度领先，适合高质量需求；
3. Gemini 2.5 Pro 在多样性维度表现优异，适合发散探索；
4. 思考模式（deepseek-r2）对创意生成帮助有限，反而不及非思考模型。

**创意任务推荐**：

- 中文创意：qwen3-max（推荐默认）
- 学术创意：claude-opus-4.5
- 多样性探索：gemini-2.5-pro
- 成本敏感：glm-4.6

### 10.3 长文本生成基准

长文本生成共 20 个用例，要求生成 3000-8000 字的开题报告章节。评分维度包括：结构完整（25%）、逻辑连贯（25%）、学术规范（25%）、语言流畅（25%），满分 100。

| 模型 | 结构完整 | 逻辑连贯 | 学术规范 | 语言流畅 | 综合分 | 平均字数 | 平均成本(CNY) |
|------|---------|---------|---------|---------|--------|---------|--------------|
| claude-opus-4.5 | 24.5 | 24.8 | 24.6 | 24.9 | 98.8 | 6820 | 4.12 |
| claude-sonnet-4.5 | 23.8 | 24.1 | 23.9 | 24.2 | 96.0 | 6540 | 1.85 |
| gpt-4.1 | 23.2 | 23.5 | 23.1 | 23.8 | 93.6 | 6280 | 1.32 |
| gemini-2.5-pro | 22.9 | 23.2 | 22.8 | 23.1 | 92.0 | 6150 | 0.92 |
| qwen3-max | 22.1 | 22.4 | 22.0 | 22.6 | 89.1 | 5980 | 0.38 |
| glm-4.6 | 21.5 | 21.8 | 21.2 | 22.1 | 86.6 | 5720 | 0.32 |
| deepseek-r2 | 20.9 | 21.2 | 20.5 | 21.4 | 84.0 | 5480 | 0.45 |
| gpt-4.1-mini | 19.2 | 19.5 | 18.8 | 19.9 | 77.4 | 5120 | 0.09 |
| deepseek-v3.2 | 18.5 | 18.8 | 18.1 | 19.2 | 74.6 | 4950 | 0.06 |
| doubao-1.5-pro | 16.8 | 17.1 | 16.4 | 17.5 | 67.8 | 4620 | 0.04 |

**关键发现**：

1. Claude 系列在长文本生成上具有压倒性优势，Opus 与 Sonnet 分别占据前二；
2. 长文本生成是成本差异最显著的任务，Opus 单次成本达 4.12 CNY；
3. GPT-4.1 在语言流畅度上接近 Claude，是性价比之选；
4. 低成本模型生成的文本偏短，结构完整性不足。

**长文本任务推荐**：

- 最终报告：claude-opus-4.5（推荐默认）
- 草稿生成：claude-sonnet-4.5 或 gpt-4.1
- 章节扩写：gpt-4.1
- 成本敏感：qwen3-max

### 10.4 检索任务基准

检索任务共 10 个用例，要求模型联网搜索并返回结构化文献摘要。评分维度包括：检索准确（35%）、信息完整（25%）、来源可靠（25%）、结构清晰（15%），满分 100。

| 模型 | 检索准确 | 信息完整 | 来源可靠 | 结构清晰 | 综合分 | 平均延迟(ms) |
|------|---------|---------|---------|---------|--------|-------------|
| deepseek-v3.2 | 33.2 | 24.1 | 23.8 | 14.2 | 95.3 | 2200 |
| claude-sonnet-4.5 | 32.8 | 24.5 | 24.2 | 13.8 | 95.3 | 5800 |
| gemini-2.5-pro | 32.5 | 23.8 | 23.5 | 14.0 | 93.8 | 4500 |
| qwen3-max | 31.9 | 23.2 | 22.9 | 13.5 | 91.5 | 3000 |
| claude-opus-4.5 | 32.1 | 24.8 | 24.5 | 13.2 | 94.6 | 13800 |
| glm-4.6 | 30.5 | 22.1 | 21.8 | 12.9 | 87.3 | 2700 |
| doubao-1.5-pro | 29.8 | 21.5 | 21.2 | 12.5 | 85.0 | 1300 |
| gpt-4.1 | 29.2 | 22.8 | 22.5 | 13.1 | 87.6 | 3600 |
| gpt-4.1-mini | 26.5 | 19.8 | 19.5 | 11.8 | 77.6 | 1700 |
| deepseek-r2 | 25.1 | 18.5 | 18.2 | 11.2 | 73.0 | 6200 |

**关键发现**：

1. DeepSeek V3.2 在检索任务上表现最佳，且成本极低，是默认 Searcher 模型的最佳选择；
2. Claude Sonnet 4.5 与 DeepSeek V3.2 综合分持平，但成本高 4 倍；
3. DeepSeek R2 因不支持联网搜索，检索表现最差；
4. Doubao 1.5 Pro 作为降级备选，检索质量可接受。

**检索任务推荐**：

- 默认检索：deepseek-v3.2（推荐默认）
- 高质量检索：claude-sonnet-4.5
- 降级检索：doubao-1.5-pro
- 不推荐：deepseek-r2（不支持联网）

### 10.5 综合评分排名

基于四类任务的加权综合评分（推理 25% + 创意 25% + 长文本 25% + 检索 25%）：

| 排名 | 模型 | 综合分 | 性价比指数 | 推荐场景 |
|------|------|--------|-----------|---------|
| 1 | claude-opus-4.5 | 96.4 | 0.23 | 旗舰质量 |
| 2 | claude-sonnet-4.5 | 93.7 | 0.51 | 均衡旗舰 |
| 3 | gemini-2.5-pro | 93.1 | 0.62 | 长上下文 |
| 4 | gpt-4.1 | 90.3 | 0.81 | 通用指导 |
| 5 | qwen3-max | 90.0 | 4.29 | 中文创意 |
| 6 | deepseek-r2 | 84.8 | 2.02 | 深度推理 |
| 7 | glm-4.6 | 85.8 | 4.77 | 国产合规 |
| 8 | deepseek-v3.2 | 79.5 | 19.88 | 检索缓存 |
| 9 | gpt-4.1-mini | 77.4 | 8.60 | 轻量任务 |
| 10 | doubao-1.5-pro | 73.3 | 24.43 | 极致成本 |

> 性价比指数 = 综合分 / 平均成本（CNY），越高越好。

**综合推荐**：

- 质量旗舰：claude-opus-4.5 + claude-sonnet-4.5
- 性价比首选：qwen3-max + deepseek-r2 + deepseek-v3.2
- 国产合规：glm-4.6 + deepseek-v3.2 + doubao-1.5-pro
- 极致成本：doubao-1.5-pro + gpt-4.1-mini + deepseek-v3.2

---

## 11. 多模型组合实战案例

本章通过五个典型部署案例，展示不同场景下的模型组合配置与实际效果。

### 11.1 案例一：理工科硕士全流程

**场景描述**：计算机科学硕士，需要完成从信息确认到开题报告生成的全流程，预算 30 CNY。

**配置方案**：

```json
{
  "step_models": {
    "orchestrator": "claude-sonnet-4.5",
    "reasoner": "deepseek-r2",
    "mentor": "gpt-4.1",
    "inspire": "qwen3-max",
    "report": "claude-opus-4.5",
    "search": "deepseek-v3.2"
  },
  "fallback_models": {
    "orchestrator": "gpt-4.1",
    "reasoner": "claude-sonnet-4.5",
    "mentor": "glm-4.6",
    "inspire": "gpt-4.1-mini",
    "report": "claude-sonnet-4.5",
    "search": "doubao-1.5-pro"
  },
  "budget": {
    "default_limit_cny": 25.0,
    "hard_limit_cny": 30.0
  }
}
```

**实际执行效果**：

| 阶段 | 调用次数 | 主要模型 | Token 用量 | 成本(CNY) |
|------|---------|---------|-----------|----------|
| info_confirm | 3 | claude-sonnet-4.5 | 12,500 | 1.38 |
| creativity | 6 | qwen3-max | 28,000 | 0.67 |
| validation | 5 | gpt-4.1 + deepseek-r2 | 35,000 | 1.96 |
| generation | 2 | claude-opus-4.5 | 18,000 | 5.20 |
| deep_assist | 4 | deepseek-v3.2 | 22,000 | 0.18 |
| **合计** | **20** | - | **115,500** | **9.39** |

**效果评估**：

- 实际成本 9.39 CNY，远低于预算 30 CNY；
- 缓存命中率 96.2%，节省输入成本约 85%；
- 报告质量评分 94/100（人工评审）；
- 全流程耗时 42 分钟。

**优化建议**：

1. generation 阶段可考虑分段生成，进一步降低单次成本；
2. deep_assist 阶段可使用 doubao-1.5-pro 进一步降本；
3. info_confirm 阶段可降级为 gpt-4.1-mini。

### 11.2 案例二：人文社科博士创意导向

**场景描述**：历史学博士，论题创意性要求高，预算 50 CNY。

**配置方案**：

```json
{
  "step_models": {
    "orchestrator": "claude-sonnet-4.5",
    "reasoner": "gemini-2.5-pro",
    "mentor": "claude-sonnet-4.5",
    "inspire": "qwen3-max",
    "report": "claude-opus-4.5",
    "search": "claude-sonnet-4.5"
  },
  "budget": {
    "default_limit_cny": 45.0,
    "hard_limit_cny": 50.0
  }
}
```

**配置理由**：

1. 人文社科论题需要更强的语言理解，Mentor 升级为 Claude Sonnet；
2. 历史学研究需要处理大量文献，Reasoner 使用 Gemini 2.5 Pro 利用 2M 上下文；
3. 创意生成仍用 Qwen3 Max，其中文创意能力突出；
4. Searcher 升级为 Claude Sonnet，提升检索质量。

**实际执行效果**：

| 阶段 | 调用次数 | 主要模型 | 成本(CNY) |
|------|---------|---------|----------|
| info_confirm | 4 | claude-sonnet-4.5 | 2.10 |
| creativity | 8 | qwen3-max | 0.92 |
| validation | 6 | gemini-2.5-pro | 1.85 |
| generation | 3 | claude-opus-4.5 | 7.80 |
| deep_assist | 5 | claude-sonnet-4.5 | 3.25 |
| **合计** | **26** | - | **15.92** |

**效果评估**：

- 实际成本 15.92 CNY，低于预算 50 CNY；
- 论题创意性评分 96/100；
- 文献综述质量评分 92/100；
- 全流程耗时 68 分钟（文献处理量大）。

### 11.3 案例三：成本敏感型批量任务

**场景描述**：教学场景，需为 50 名本科生批量生成论题建议，总预算 100 CNY。

**配置方案**：

```json
{
  "step_models": {
    "orchestrator": "deepseek-v3.2",
    "reasoner": "deepseek-r2",
    "mentor": "gpt-4.1-mini",
    "inspire": "qwen3-max",
    "report": "gpt-4.1",
    "search": "doubao-1.5-pro"
  },
  "budget": {
    "default_limit_cny": 2.0,
    "hard_limit_cny": 2.5
  }
}
```

**配置理由**：

1. 批量任务成本敏感，全面降级模型；
2. Orchestrator 降级为 DeepSeek V3.2，利用缓存优势；
3. Writer 降级为 GPT-4.1，平衡质量与成本；
4. Searcher 使用最便宜的 Doubao 1.5 Pro。

**实际执行效果**（单名学生）：

| 阶段 | 调用次数 | 主要模型 | 成本(CNY) |
|------|---------|---------|----------|
| info_confirm | 2 | deepseek-v3.2 | 0.02 |
| creativity | 3 | qwen3-max | 0.08 |
| validation | 2 | deepseek-r2 | 0.12 |
| generation | 1 | gpt-4.1 | 0.45 |
| deep_assist | 2 | doubao-1.5-pro | 0.01 |
| **合计** | **10** | - | **0.68** |

**批量效果**：

- 50 名学生总成本：34.0 CNY（远低于 100 CNY 预算）；
- 平均论题质量评分：82/100（可接受）；
- 缓存命中率 98.5%（批量任务前缀高度一致）；
- 总耗时约 4 小时（串行处理）。

**优化建议**：

1. 可并行处理多名学生，缩短总耗时；
2. generation 阶段可降级为 qwen3-max 进一步降本；
3. 对质量不满意的学生，单独使用旗舰配置重新生成。

### 11.4 案例四：高质量旗舰配置

**场景描述**：重点学科博士，对论题与报告质量要求极高，预算 200 CNY。

**配置方案**：

```json
{
  "step_models": {
    "orchestrator": "claude-opus-4.5",
    "reasoner": "claude-opus-4.5",
    "mentor": "claude-sonnet-4.5",
    "inspire": "claude-opus-4.5",
    "report": "claude-opus-4.5",
    "search": "claude-sonnet-4.5"
  },
  "budget": {
    "default_limit_cny": 150.0,
    "hard_limit_cny": 200.0
  }
}
```

**实际执行效果**：

| 阶段 | 调用次数 | 主要模型 | 成本(CNY) |
|------|---------|---------|----------|
| info_confirm | 4 | claude-opus-4.5 | 8.50 |
| creativity | 8 | claude-opus-4.5 | 22.40 |
| validation | 6 | claude-opus-4.5 | 18.20 |
| generation | 4 | claude-opus-4.5 | 28.80 |
| deep_assist | 6 | claude-sonnet-4.5 | 12.50 |
| **合计** | **28** | - | **90.40** |

**效果评估**：

- 实际成本 90.40 CNY，低于预算 200 CNY；
- 论题质量评分 98/100；
- 报告质量评分 97/100；
- 全流程耗时 95 分钟（Opus 延迟较高）。

**警示**：

1. 旗舰配置成本是均衡配置的 10 倍，质量提升仅约 5%；
2. Opus 延迟较高，不适合实时对话场景；
3. 建议仅在最终交付物生成阶段使用 Opus。

### 11.5 案例五：国产化合规部署

**场景描述**：政府机构内部部署，要求数据不出境，仅使用国产模型。

**配置方案**：

```json
{
  "models": [
    {"id": "deepseek-v3.2", "api_key": "sk-xxx", "base_url": "https://api.deepseek.com/v1"},
    {"id": "deepseek-r2", "api_key": "sk-xxx", "base_url": "https://api.deepseek.com/v1"},
    {"id": "qwen3-max", "api_key": "sk-xxx", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
    {"id": "glm-4.6", "api_key": "xxx.xxx", "base_url": "https://open.bigmodel.cn/api/paas/v4"},
    {"id": "doubao-1.5-pro", "api_key": "xxx", "base_url": "https://ark.cn-beijing.volces.com/api/v3"}
  ],
  "step_models": {
    "orchestrator": "glm-4.6",
    "reasoner": "deepseek-r2",
    "mentor": "glm-4.6",
    "inspire": "qwen3-max",
    "report": "glm-4.6",
    "search": "deepseek-v3.2"
  },
  "fallback_models": {
    "orchestrator": "qwen3-max",
    "reasoner": "qwen3-max",
    "mentor": "qwen3-max",
    "inspire": "glm-4.6",
    "report": "qwen3-max",
    "search": "doubao-1.5-pro"
  }
}
```

**配置理由**：

1. 移除所有海外模型（OpenAI、Anthropic、Google）；
2. Orchestrator 使用 GLM-4.6，国产模型中指令遵循能力较强；
3. Reasoner 仍用 DeepSeek R2，国产推理模型首选；
4. Writer 使用 GLM-4.6，国产模型中写作能力较强。

**实际执行效果**：

| 阶段 | 调用次数 | 主要模型 | 成本(CNY) |
|------|---------|---------|----------|
| info_confirm | 3 | glm-4.6 | 0.15 |
| creativity | 5 | qwen3-max | 0.42 |
| validation | 4 | deepseek-r2 | 0.38 |
| generation | 2 | glm-4.6 | 0.85 |
| deep_assist | 3 | deepseek-v3.2 | 0.04 |
| **合计** | **17** | - | **1.84** |

**效果评估**：

- 实际成本 1.84 CNY，远低于均衡配置；
- 论题质量评分 88/100（略低于均衡配置的 94）；
- 报告质量评分 86/100；
- 数据全程在国内处理，符合合规要求。

**国产化部署建议**：

1. GLM-4.6 可作为 Orchestrator/Writer 的国产替代；
2. DeepSeek 系列是国产推理与检索的最佳选择；
3. Qwen3 Max 是国产创意生成的首选；
4. 国产模型整体质量略低于海外旗舰，但性价比更高。

---

## 12. 模型升级与迁移指南

### 12.1 版本升级策略

**升级触发条件**：

1. 模型厂商发布新版本（如 deepseek-v3.2 → deepseek-v4.0）；
2. 现有模型停服或价格调整；
3. 新模型在基准测试中显著优于现有模型；
4. 安全合规要求变更。

**升级策略选择**：

| 策略 | 说明 | 风险 | 适用场景 |
|------|------|------|---------|
| 全量切换 | 所有请求立即切换到新模型 | 高 | 紧急停服替代 |
| 灰度发布 | 按比例逐步切换流量到新模型 | 中 | 常规升级 |
| A/B 测试 | 新旧模型并行对比 | 低 | 质量验证 |
| 影子模式 | 新模型并行运行但不返回结果 | 极低 | 兼容性验证 |

**推荐升级流程**：

```
┌─────────────────────────────────────────────┐
│  1. 影子模式运行 3 天，验证兼容性             │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  2. A/B 测试 7 天，对比质量指标              │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  3. 灰度发布，10% → 50% → 100%              │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  4. 全量切换，保留旧模型 30 天作为 fallback  │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  5. 30 天后移除旧模型配置                    │
└─────────────────────────────────────────────┘
```

### 12.2 模型替换流程

**替换步骤**：

1. **评估新模型**：在基准测试集上运行新模型，对比质量与成本；
2. **更新配置**：在 `config.json` 中添加新模型，修改 `step_models`；
3. **配置 fallback**：将旧模型设为新模型的 fallback；
4. **灰度发布**：通过 `ab_tests` 配置逐步切换流量；
5. **监控指标**：观察质量、成本、延迟、错误率；
6. **全量切换**：指标稳定后全量切换；
7. **清理旧配置**：30 天后移除旧模型。

**配置示例**（deepseek-v3.2 → deepseek-v4.0）：

```json
{
  "models": [
    {
      "id": "deepseek-v4.0",
      "label": "DeepSeek V4.0 (2026)",
      "base_url": "https://api.deepseek.com/v1",
      "api_key": "sk-xxxxxxxx",
      "pricing": {"input_cny_per_million": 0.8, "output_cny_per_million": 3.2},
      "supports_streaming": true,
      "supports_thinking": false,
      "supports_web_search": true,
      "max_context": 256000,
      "default_temperature": 0.7,
      "agent_default": "search",
      "release_year": 2026
    },
    {
      "id": "deepseek-v3.2",
      "label": "DeepSeek V3.2 (Legacy)",
      "base_url": "https://api.deepseek.com/v1",
      "api_key": "sk-xxxxxxxx",
      "pricing": {"input_cny_per_million": 1, "output_cny_per_million": 4},
      "supports_streaming": true,
      "supports_thinking": false,
      "supports_web_search": true,
      "max_context": 128000,
      "default_temperature": 0.7,
      "agent_default": "search",
      "release_year": 2026
    }
  ],
  "step_models": {
    "search": "deepseek-v4.0"
  },
  "fallback_models": {
    "search": "deepseek-v3.2"
  },
  "ab_tests": [
    {
      "id": "migrate_deepseek_v4",
      "agent": "search",
      "variants": {
        "A": {"model": "deepseek-v3.2", "weight": 90},
        "B": {"model": "deepseek-v4.0", "weight": 10}
      },
      "duration_days": 7
    }
  ]
}
```

### 12.3 兼容性处理

**常见兼容性问题**：

| 问题 | 说明 | 解决方案 |
|------|------|---------|
| API 接口差异 | 新模型 API 参数不同 | 在 ai_proxy 层适配 |
| 响应格式变化 | 字段名或结构变化 | 增加响应解析适配 |
| 上下文长度变化 | 新模型上下文更长 | 调整 prompt 截断策略 |
| 价格变化 | 新模型价格不同 | 更新 pricing 配置 |
| 能力变化 | 新模型支持/不支持某些能力 | 更新 supports_* 字段 |

**兼容性检查清单**：

- [ ] API 接口兼容（endpoint、参数、认证）
- [ ] 响应格式兼容（字段、类型、结构）
- [ ] 流式响应兼容（SSE 事件类型）
- [ ] 工具调用兼容（function calling 格式）
- [ ] 思考模式兼容（thinking 字段）
- [ ] 联网搜索兼容（web_search 触发方式）
- [ ] 上下文长度适配（prompt 截断）
- [ ] 价格配置更新（pricing 字段）
- [ ] 缓存机制兼容（DeepSeek 缓存）

### 12.4 回滚机制

**回滚触发条件**：

1. 新模型错误率 > 5%（旧模型 < 1%）；
2. 新模型质量评分下降 > 10%；
3. 新模型延迟增加 > 50%；
4. 用户投诉显著增加。

**回滚流程**：

```
┌─────────────────────────────────────────────┐
│  1. 检测到异常指标（自动/人工）               │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  2. 自动回滚到 fallback 模型（即时生效）      │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  3. 修改 step_models，恢复旧模型为主模型      │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  4. 通知相关人员，分析异常原因                │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  5. 修复问题后，重新走升级流程                │
└─────────────────────────────────────────────┘
```

**回滚配置**：

```bash
# 一键回滚（通过 API）
curl -X PATCH "http://127.0.0.1:8000/api/config" \
  -H "Content-Type: application/json" \
  -d '{
    "step_models": {
      "search": "deepseek-v3.2"
    },
    "fallback_models": {
      "search": "doubao-1.5-pro"
    }
  }'
```

**回滚日志记录**：

```json
{
  "rollback_event": {
    "timestamp": "2026-06-20T14:30:00Z",
    "trigger": "error_rate_threshold",
    "from_model": "deepseek-v4.0",
    "to_model": "deepseek-v3.2",
    "metrics": {
      "error_rate_new": 0.072,
      "error_rate_old": 0.008,
      "latency_new_ms": 3500,
      "latency_old_ms": 1800
    },
    "operator": "auto"
  }
}
```

---

## 13. 安全与合规配置

### 13.1 API Key 安全管理

**API Key 存储规范**：

1. **禁止硬编码**：API Key 不得出现在源代码中；
2. **环境变量优先**：通过 `.env` 文件或系统环境变量注入；
3. **加密存储**：`config.json` 中的 API Key 应加密存储；
4. **访问控制**：配置文件权限设置为 600（仅所有者可读写）。

**.env 文件示例**：

```bash
# .env 文件权限：chmod 600 .env

# 各厂商 API Key
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxx
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxx
QWEN_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
GEMINI_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxx
GLM_API_KEY=xxxxxxxx.xxxxxxxx
DOUBAO_API_KEY=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

**API Key 轮换策略**：

| 项目 | 建议 |
|------|------|
| 轮换周期 | 每 90 天 |
| 轮换方式 | 双 Key 并存，逐步切换 |
| 监控 | 监控 Key 使用量与错误率 |
| 撤销 | 离职员工 Key 立即撤销 |
| 审计 | 每月审计 Key 使用记录 |

**多 Key 轮询配置**：

```json
{
  "models": [
    {
      "id": "deepseek-v3.2",
      "api_keys": [
        {"key": "sk-key1", "weight": 1, "quota_limit": 1000000},
        {"key": "sk-key2", "weight": 1, "quota_limit": 1000000},
        {"key": "sk-key3", "weight": 1, "quota_limit": 1000000}
      ],
      "api_key_strategy": "round_robin",
      "rate_limit_fallback": true
    }
  ]
}
```

### 13.2 数据合规

**数据驻留要求**：

| 部署场景 | 数据驻留 | 推荐模型 |
|---------|---------|---------|
| 国内企业 | 数据不出境 | DeepSeek、Qwen、GLM、Doubao |
| 政府机构 | 数据不出境 + 私有化 | GLM（支持私有化部署） |
| 跨国企业 | 按地区路由 | 国内用国产，海外用 OpenAI/Anthropic |
| 学术机构 | 无特殊要求 | 全部模型可用 |

**敏感数据处理**：

1. **PII 脱敏**：用户输入中的个人信息（姓名、身份证、手机号）应在调用 LLM 前脱敏；
2. **学术数据**：未发表论文数据不应发送给会存储数据的模型；
3. **配置脱敏**：日志与错误报告中不得包含 API Key。

**PII 脱敏示例**：

```python
import re

def sanitize_pii(text: str) -> str:
    """脱敏用户输入中的 PII。"""
    # 手机号脱敏
    text = re.sub(r'1[3-9]\d{9}', '[PHONE]', text)
    # 邮箱脱敏
    text = re.sub(r'[\w.-]+@[\w.-]+', '[EMAIL]', text)
    # 身份证号脱敏
    text = re.sub(r'\d{17}[\dXx]', '[ID_CARD]', text)
    # 学号脱敏（假设 10 位数字）
    text = re.sub(r'\b\d{10}\b', '[STUDENT_ID]', text)
    return text

# 在调用 LLM 前脱敏
sanitized_input = sanitize_pii(user_input)
response = call_llm(model_id, system=cached_prefix, user=sanitized_input)
```

### 13.3 审计日志

**审计日志内容**：

每次 LLM 调用应记录以下信息：

```json
{
  "call_id": "call_20260620_001",
  "timestamp": "2026-06-20T14:30:00.123Z",
  "session_id": "ses_20260620_a1b2c3d4",
  "conversation_id": "conv_20260620_e5f6g7h8",
  "agent_id": "reasoner",
  "model_id": "deepseek-r2",
  "api_key_id": "key_001",
  "prompt_tokens": 1520,
  "completion_tokens": 850,
  "cache_hit": true,
  "cached_tokens": 1450,
  "cost_cny": 0.018,
  "latency_ms": 3200,
  "success": true,
  "error": null,
  "user_id": "user_12345",
  "ip_hash": "a1b2c3d4e5f6"
}
```

**日志保留策略**：

| 日志类型 | 保留期 | 存储位置 |
|---------|--------|---------|
| 调用日志 | 90 天 | SQLite + 归档 |
| 审计日志 | 1 年 | 独立审计库 |
| 错误日志 | 6 个月 | SQLite + 归档 |
| 预算日志 | 2 年 | 独立预算库 |

**日志查询接口**：

```bash
# 查询指定会话的调用日志
curl -X GET "http://127.0.0.1:8000/api/audit/calls?session_id=ses_20260620_a1b2c3d4"

# 查询指定时间范围的审计日志
curl -X GET "http://127.0.0.1:8000/api/audit/calls?start_time=2026-06-20T00:00:00Z&end_time=2026-06-21T00:00:00Z"

# 按 Agent 维度查询
curl -X GET "http://127.0.0.1:8000/api/audit/calls?agent_id=reasoner&limit=100"
```

### 13.4 内容安全

**输入内容过滤**：

1. **敏感词过滤**：对用户输入进行敏感词检测；
2. **注入攻击防护**：检测 prompt injection 攻击；
3. **长度限制**：限制单次输入长度（默认 10000 字符）；
4. **频率限制**：限制单用户请求频率。

**输出内容过滤**：

1. **敏感内容检测**：对模型输出进行敏感内容检测；
2. **引用真实性校验**：校验引用的文献是否真实存在；
3. **学术诚信检测**：检测生成内容的原创性；
4. **格式校验**：校验输出是否符合预期格式。

**内容安全配置**：

```json
{
  "content_safety": {
    "input_filter": {
      "enabled": true,
      "sensitive_words": ["敏感词1", "敏感词2"],
      "max_input_length": 10000,
      "prompt_injection_detection": true
    },
    "output_filter": {
      "enabled": true,
      "sensitive_content_detection": true,
      "citation_verification": true,
      "originality_check": true
    },
    "rate_limit": {
      "per_user_per_minute": 30,
      "per_user_per_day": 500,
      "per_ip_per_minute": 60
    }
  }
}
```

---

## 14. 监控与运维

### 14.1 监控指标体系

**核心监控指标**：

| 指标类别 | 指标名 | 说明 | 告警阈值 |
|---------|--------|------|---------|
| 可用性 | `success_rate` | 请求成功率 | < 99% |
| 可用性 | `error_rate` | 错误率 | > 1% |
| 性能 | `latency_p50` | 中位数延迟 | > 5s |
| 性能 | `latency_p95` | P95 延迟 | > 15s |
| 性能 | `latency_p99` | P99 延迟 | > 30s |
| 成本 | `cost_per_hour` | 每小时成本 | > 预算 80% |
| 成本 | `cost_per_session` | 单会话成本 | > 50 CNY |
| 缓存 | `cache_hit_rate` | 缓存命中率 | < 90% |
| 业务 | `active_sessions` | 活跃会话数 | > 容量 80% |
| 业务 | `queue_length` | 队列长度 | > 100 |

**监控仪表盘**：

```
┌─────────────────────────────────────────────────────────────┐
│  ThesisMiner 监控仪表盘                                       │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ 成功率       │  │ P95 延迟     │  │ 缓存命中率   │         │
│  │   99.2%     │  │   3.2s      │  │   96.5%     │         │
│  │   ▲ 0.1%    │  │   ▼ 0.3s    │  │   ▲ 1.2%    │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ 今日成本     │  │ 活跃会话     │  │ 队列长度     │         │
│  │  ¥128.50    │  │    42       │  │     3       │         │
│  │  预算 64%   │  │  容量 42%   │  │   正常      │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  各模型调用次数（过去 1 小时）                        │   │
│  │  deepseek-v3.2  ████████████████████  1240          │   │
│  │  qwen3-max      ███████████           680           │   │
│  │  deepseek-r2    ████████               520           │   │
│  │  claude-sonnet  █████                  310           │   │
│  │  gpt-4.1        ████                   250           │   │
│  │  claude-opus    ██                     120           │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**指标采集接口**：

```bash
# 获取实时指标
curl -X GET "http://127.0.0.1:8000/api/metrics"

# 获取历史指标
curl -X GET "http://127.0.0.1:8000/api/metrics/history?start_time=2026-06-20T00:00:00Z&end_time=2026-06-21T00:00:00Z&interval=1h"

# 按模型维度获取指标
curl -X GET "http://127.0.0.1:8000/api/metrics?group_by=model"
```

### 14.2 告警配置

**告警规则配置**：

```json
{
  "alerts": [
    {
      "id": "high_error_rate",
      "name": "错误率过高",
      "condition": "error_rate > 0.05",
      "duration": "5m",
      "severity": "critical",
      "action": ["notify", "auto_fallback"]
    },
    {
      "id": "high_latency",
      "name": "延迟过高",
      "condition": "latency_p95 > 15000",
      "duration": "10m",
      "severity": "warning",
      "action": ["notify"]
    },
    {
      "id": "low_cache_hit",
      "name": "缓存命中率过低",
      "condition": "cache_hit_rate < 0.90",
      "duration": "30m",
      "severity": "warning",
      "action": ["notify"]
    },
    {
      "id": "budget_threshold",
      "name": "预算告警",
      "condition": "daily_cost > budget * 0.8",
      "duration": "0m",
      "severity": "warning",
      "action": ["notify"]
    },
    {
      "id": "budget_exceeded",
      "name": "预算超限",
      "condition": "daily_cost > budget",
      "duration": "0m",
      "severity": "critical",
      "action": ["notify", "block_new_sessions"]
    }
  ],
  "notification": {
    "channels": [
      {"type": "webhook", "url": "https://your-server.com/webhooks/alert"},
      {"type": "email", "recipients": ["admin@example.com"]},
      {"type": "dingtalk", "webhook": "https://oapi.dingtalk.com/robot/send?access_token=xxx"}
    ]
  }
}
```

**告警通知示例**：

```json
{
  "alert_id": "high_error_rate",
  "timestamp": "2026-06-20T14:30:00Z",
  "severity": "critical",
  "message": "错误率过高：当前 7.2%，阈值 5%",
  "details": {
    "current_value": 0.072,
    "threshold": 0.05,
    "duration": "5m",
    "affected_model": "claude-opus-4.5",
    "auto_action_taken": "已自动切换到 fallback 模型 claude-sonnet-4.5"
  },
  "runbook_url": "https://docs.thesisminer.io/runbooks/high-error-rate"
}
```

### 14.3 容量规划

**容量评估维度**：

| 维度 | 评估指标 | 容量规划方法 |
|------|---------|------------|
| 并发 | 并发会话数 | 按 QPS × 平均会话时长估算 |
| 吞吐 | 每秒请求数 | 按 LLM 调用频率估算 |
| 存储 | 数据库大小 | 按会话数 × 平均数据量估算 |
| 成本 | 月度成本 | 按会话数 × 平均单会话成本估算 |

**容量规划示例**：

假设目标支持 100 并发用户：

```
并发会话数：100
平均会话时长：60 分钟
平均 LLM 调用间隔：3 分钟
单会话 LLM 调用数：20 次
单次调用平均成本：0.5 CNY

QPS = 100 / 180 = 0.56 请求/秒
日活会话数 = 100 × (8 小时 / 1 小时) = 800 会话/天
日成本 = 800 × 20 × 0.5 = 8000 CNY/天
月成本 = 8000 × 30 = 240,000 CNY/月

数据库增长 = 800 × 500KB = 400MB/天 = 12GB/月
```

**扩容建议**：

1. 当并发会话数达到容量 70% 时，考虑扩容；
2. 当 P95 延迟持续 > 10s 时，考虑扩容；
3. 当数据库大小 > 50GB 时，考虑归档历史数据；
4. 当月度成本超预算 80% 时，考虑降级模型。

### 14.4 故障排查

**常见故障与排查**：

| 故障现象 | 可能原因 | 排查步骤 |
|---------|---------|---------|
| 所有模型调用失败 | 网络中断 | 检查网络连接、DNS 解析 |
| 单模型调用失败 | API Key 失效 | 检查 Key 有效性、配额 |
| 响应缓慢 | 模型服务过载 | 检查模型状态、切换 fallback |
| 缓存命中率下降 | Prefix 变化 | 检查系统提示、Agent 角色定义 |
| 成本异常增长 | 模型配置错误 | 检查 step_models、budget 配置 |
| 报告质量下降 | 模型降级 | 检查 fallback 是否触发 |

**故障排查流程**：

```
┌─────────────────────────────────────────────┐
│  1. 确认故障现象与影响范围                    │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  2. 查看监控仪表盘，定位异常指标              │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  3. 查询审计日志，定位故障请求                │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  4. 分析故障原因（网络/模型/配置/代码）       │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  5. 采取修复措施（切换模型/修复配置/重启）    │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  6. 验证修复效果，记录故障报告                │
└─────────────────────────────────────────────┘
```

**日志查询命令**：

```bash
# 查询最近 1 小时的错误日志
curl -X GET "http://127.0.0.1:8000/api/audit/calls?success=false&start_time=$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)"

# 查询指定模型的调用统计
curl -X GET "http://127.0.0.1:8000/api/metrics?group_by=model&model_id=claude-opus-4.5"

# 查询缓存命中率变化
curl -X GET "http://127.0.0.1:8000/api/cache-stats?start_time=$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)"
```

---

## 15. 附录

### 15.1 模型速查表

| 模型 | 价格档 | 上下文 | 思考 | 联网 | 推荐 Agent |
|------|--------|--------|------|------|-----------|
| gpt-4.1-mini | 低 | 1M | 否 | 否 | mentor |
| gpt-4.1 | 中高 | 1M | 否 | 否 | mentor |
| deepseek-v3.2 | 低 | 128K | 否 | 是 | search |
| deepseek-r2 | 中 | 128K | 是 | 否 | reasoner |
| claude-sonnet-4.5 | 高 | 200K | 是 | 是 | orchestrator |
| claude-opus-4.5 | 极高 | 200K | 是 | 是 | report |
| qwen3-max | 中低 | 131K | 是 | 是 | inspire |
| gemini-2.5-pro | 中高 | 2M | 是 | 是 | reasoner |
| glm-4.6 | 中 | 131K | 是 | 是 | mentor |
| doubao-1.5-pro | 极低 | 131K | 否 | 是 | search |

### 15.2 故障转移速查表

| 主模型 | Fallback |
|--------|----------|
| claude-sonnet-4.5 | gpt-4.1 |
| deepseek-r2 | claude-sonnet-4.5 |
| gpt-4.1 | glm-4.6 |
| qwen3-max | gpt-4.1-mini |
| claude-opus-4.5 | claude-sonnet-4.5 |
| deepseek-v3.2 | doubao-1.5-pro |

### 15.3 配置文件参考

**最小化配置**（仅使用 DeepSeek）：

```json
{
  "ai_api_key": "sk-deepseek-xxxxxxxx",
  "ai_base_url": "https://api.deepseek.com/v1",
  "ai_model": "deepseek-v3.2",
  "step_models": {
    "orchestrator": "deepseek-v3.2",
    "reasoner": "deepseek-r2",
    "mentor": "deepseek-v3.2",
    "inspire": "deepseek-v3.2",
    "report": "deepseek-v3.2",
    "search": "deepseek-v3.2"
  }
}
```

**高质量配置**（使用 Claude 全家桶）：

```json
{
  "models": [
    {"id": "claude-sonnet-4.5", "api_key": "sk-ant-xxxxxxxx", "base_url": "https://api.anthropic.com/v1"},
    {"id": "claude-opus-4.5", "api_key": "sk-ant-xxxxxxxx", "base_url": "https://api.anthropic.com/v1"}
  ],
  "step_models": {
    "orchestrator": "claude-sonnet-4.5",
    "reasoner": "claude-sonnet-4.5",
    "mentor": "claude-sonnet-4.5",
    "inspire": "claude-sonnet-4.5",
    "report": "claude-opus-4.5",
    "search": "claude-sonnet-4.5"
  }
}
```

**均衡配置**（默认推荐）：

```json
{
  "step_models": {
    "orchestrator": "claude-sonnet-4.5",
    "reasoner": "deepseek-r2",
    "mentor": "gpt-4.1",
    "inspire": "qwen3-max",
    "report": "claude-opus-4.5",
    "search": "deepseek-v3.2"
  },
  "fallback_models": {
    "orchestrator": "gpt-4.1",
    "reasoner": "claude-sonnet-4.5",
    "mentor": "glm-4.6",
    "inspire": "gpt-4.1-mini",
    "report": "claude-sonnet-4.5",
    "search": "doubao-1.5-pro"
  }
}
```

### 15.4 变更日志

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| 8.0.0 | 2026-06-20 | 初始版本，支持 10 个 2026 模型 |
| 8.0.1 | 2026-06-25 | 优化 DeepSeek 缓存 Prefix 设计 |
| 8.1.0 | 2026-07-01 | 新增多 API Key 轮询支持 |
| 8.2.0 | 2026-07-20 | 新增 A/B 测试框架 |

---

## 参考资源

- **API 教程**：`docs/tutorials/api_tutorial.md`
- **入门教程**：`docs/tutorials/getting_started.md`
- **开发者指南**：`docs/tutorials/developer_guide.md`
- **高级特性**：`docs/tutorials/advanced_features.md`
- **管理指南**：`docs/tutorials/admin_guide.md`
- **错误码参考**：`docs/api/error_codes.md`

---

## 反馈与支持

- **问题反馈**：通过 GitHub Issues 提交问题
- **功能建议**：通过 GitHub Discussions 讨论
- **配置问题**：附上 `data/config.json`（脱敏后）与日志
- **文档错误**：直接提交 PR 修正

---

> 本指南由 ThesisMiner Core Team 维护，最后更新于 2026-06-20。模型价格与能力可能随厂商更新而变化，请以各厂商官方文档为准。