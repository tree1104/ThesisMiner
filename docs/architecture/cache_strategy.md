# ThesisMiner v8.0 DeepSeek 缓存优化策略

> **版本**：v8.0
> **日期**：2026-06-19
> **适用范围**：`backend/ai/prompts.py`、`backend/sessions/`、`backend/routes/cache_stats.py`
> **关联模块**：三段式 Prompt + DST 压缩 + 前缀哈希 + 命中率监控

---

## 目录

1. [缓存优化目标](#1-缓存优化目标)
2. [DeepSeek KV Cache 机制](#2-deepseek-kv-cache-机制)
3. [三段式 Prompt 架构](#3-三段式-prompt-架构)
4. [字节级前缀一致性](#4-字节级前缀一致性)
5. [前缀构建规则](#5-前缀构建规则)
6. [动态内容处理](#6-动态内容处理)
7. [缓存命中率监控](#7-缓存命中率监控)
8. [≥95% 命中率达成方法](#8-95-命中率达成方法)
9. [兜底策略](#9-兜底策略)
10. [缓存与多 Agent 协同](#10-缓存与多-agent-协同)
11. [性能基准与压测](#11-性能基准与压测)
12. [常见问题与排查](#12-常见问题与排查)
13. [附录](#13-附录)

---

## 1. 缓存优化目标

### 1.1 业务背景

ThesisMiner v8.0 采用多智能体协作架构，单次五阶段流程涉及 6 个 Agent 的多次 LLM 调用，单会话 token 用量可达 50K-100K。若不优化缓存命中率，API 成本将显著上升。

DeepSeek API 提供 KV Cache 机制：当请求的 Prompt 前缀与之前请求一致时，可命中缓存，**缓存命中的 token 按 0.1 元/百万 token 计费**（正常输入 1-4 元/百万 token），成本降低 10-40 倍。

### 1.2 优化目标

| 指标 | 目标值 | 当前值（v7） | 优化手段 |
|------|--------|-------------|----------|
| 缓存命中率 | ≥ 95% | ~70% | 三段式 Prompt + 前缀哈希 |
| 单会话成本 | < 5 元 | ~12 元 | 缓存优化 + 模型路由 |
| 端到端延迟 | < 60 秒 | ~90 秒 | 缓存命中减少推理时间 |
| Token 用量 | < 50K | ~80K | DST 压缩 + 上下文裁剪 |

### 1.3 优化原则

1. **前缀稳定**：Prompt 前缀（系统提示词 + 静态上下文）保持不变，确保缓存命中。
2. **动态后置**：动态内容（用户输入、DST 状态）放在 Prompt 末尾，避免污染前缀。
3. **哈希校验**：每次请求前计算前缀 SHA-256 哈希，与上次请求比对，确保字节级一致。
4. **命中率监控**：实时监控缓存命中率，低于阈值时告警并触发优化。
5. **兜底降级**：缓存失效时自动降级为非缓存请求，确保功能可用。

---

## 2. DeepSeek KV Cache 机制

### 2.1 工作原理

DeepSeek API 的 KV Cache 机制基于以下原理：

1. **前缀匹配**：当请求的 Prompt 前缀（从开头到某个位置）与缓存中的某个 Prompt 完全一致时，命中缓存。
2. **KV 复用**：命中缓存时，前缀部分的 Key-Value 向量直接从缓存读取，无需重新计算。
3. **成本降低**：缓存命中的 token 按 0.1 元/百万 token 计费，未命中的按正常价格计费。
4. **时效性**：缓存有 TTL（默认 1 小时），超时后自动失效。

### 2.2 命中条件

```text
命中条件（全部满足）：
  1. 请求的 Prompt 前缀与缓存中的 Prompt 字节级完全一致
  2. 缓存未过期（TTL 内）
  3. 请求的模型与缓存时的模型一致
  4. 请求的 temperature 等参数不影响缓存（仅影响生成）
```

### 2.3 响应字段

DeepSeek API 响应中的 `usage` 字段包含缓存信息：

```json
{
  "usage": {
    "prompt_tokens": 1500,
    "completion_tokens": 800,
    "total_tokens": 2300,
    "prompt_cache_hit_tokens": 1200,
    "prompt_cache_miss_tokens": 300
  }
}
```

- `prompt_cache_hit_tokens`：缓存命中的 token 数
- `prompt_cache_miss_tokens`：缓存未命中的 token 数
- 命中率 = `prompt_cache_hit_tokens` / `prompt_tokens`

---

## 3. 三段式 Prompt 架构

### 3.1 架构设计

ThesisMiner v8.0 采用**三段式 Prompt 架构**，将 Prompt 分为前缀、中段、尾段三部分：

```text
┌─────────────────────────────────────────────────────────┐
│  前缀段（Prefix）—— 静态，缓存命中目标                    │
│  ─────────────────────────────────────────────────────  │
│  - Agent 系统提示词（固定不变）                           │
│  - 学位、学科、导师信息（会话级稳定）                      │
│  - 硬约束规则库（固定不变）                               │
│  - 报告模板（固定不变）                                   │
│  长度：约 2000-5000 token                                │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  中段（Middle）—— 半静态，DST 压缩后稳定                  │
│  ─────────────────────────────────────────────────────  │
│  - DST 状态摘要（压缩后变化频率低）                       │
│  - 候选论题列表（阶段性稳定）                             │
│  长度：约 500-2000 token                                 │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  尾段（Tail）—— 动态，每轮变化                            │
│  ─────────────────────────────────────────────────────  │
│  - 最近 2 轮对话原文                                     │
│  - 用户当前输入                                          │
│  长度：约 500-3000 token                                 │
└─────────────────────────────────────────────────────────┘
```

### 3.2 段落职责

| 段落 | 稳定性 | 缓存命中 | 内容 | 长度 |
|------|--------|----------|------|------|
| 前缀段 | 完全静态 | 是 | 系统提示词、学位信息、规则库、模板 | 2000-5000 token |
| 中段 | 半静态 | 部分 | DST 摘要、候选列表 | 500-2000 token |
| 尾段 | 完全动态 | 否 | 最近对话、用户输入 | 500-3000 token |

### 3.3 前缀段构建

```python
def build_prefix(agent_id: str, session_context: dict) -> str:
    """构建 Prompt 前缀段（静态，缓存命中目标）。"""
    # 1. Agent 系统提示词（从 config/agents/*.yaml 加载）
    agent_config = get_agent_config(agent_id)
    system_prompt = agent_config["system_prompt"]

    # 2. 学位、学科、导师信息（会话级稳定）
    degree = session_context.get("degree", "")
    discipline = session_context.get("discipline", "")
    mentor_info = session_context.get("mentor_info", "")

    # 3. 硬约束规则库（固定不变，从 config/constraints/hard_rules.yaml 加载）
    hard_rules = load_hard_rules()

    # 4. 报告模板（固定不变，从 docs/constraints/report_template.md 加载）
    report_template = load_report_template()

    prefix = f"""{system_prompt}

## 学位信息
学位：{degree}
学科：{discipline}
导师信息：
{mentor_info}

## 硬约束规则库
{hard_rules}

## 报告模板
{report_template}
"""
    return prefix
```

### 3.4 中段构建

```python
def build_middle(dst_state: dict, candidates: list) -> str:
    """构建 Prompt 中段（半静态，DST 压缩后稳定）。"""
    middle = f"""## DST 状态
{json.dumps(dst_state, ensure_ascii=False, indent=2)}

## 候选论题列表
{json.dumps(candidates, ensure_ascii=False, indent=2)}
"""
    return middle
```

### 3.5 尾段构建

```python
def build_dynamic_tail(recent_history: list, user_input: str) -> str:
    """构建 Prompt 尾段（动态，每轮变化）。"""
    tail = f"""## 最近对话
"""
    for msg in recent_history:
        tail += f"{msg['role']}: {msg['content']}\n"

    tail += f"""
## 用户当前输入
{user_input}
"""
    return tail
```

### 3.6 完整 Prompt 组装

```python
def build_prompt(agent_id: str, session_context: dict, dst_state: dict,
                 candidates: list, recent_history: list, user_input: str) -> str:
    """组装完整的三段式 Prompt。"""
    prefix = build_prefix(agent_id, session_context)
    middle = build_middle(dst_state, candidates)
    tail = build_dynamic_tail(recent_history, user_input)

    return prefix + "\n" + middle + "\n" + tail
```

---

## 4. 字节级前缀一致性

### 4.1 一致性要求

DeepSeek KV Cache 要求前缀**字节级完全一致**，任何差异都会导致缓存失效：

- 多一个空格 → 失效
- 多一个换行符 → 失效
- 字段顺序不同 → 失效
- 编码不同（UTF-8 vs GBK）→ 失效

### 4.2 前缀哈希校验

每次构建前缀后，计算 SHA-256 哈希，与上次请求的哈希比对：

```python
import hashlib

def compute_prefix_hash(prefix: str) -> str:
    """计算前缀的 SHA-256 哈希。"""
    return hashlib.sha256(prefix.encode("utf-8")).hexdigest()

def check_prefix_consistency(current_hash: str, previous_hash: str) -> bool:
    """检查前缀一致性。"""
    return current_hash == previous_hash
```

### 4.3 哈希存储

前缀哈希存储在 `sessions.cache_prefix_hash` 字段，每次请求更新：

```python
def update_cache_hash(session_id: str, prefix_hash: str):
    """更新会话的缓存前缀哈希。"""
    execute_query(
        "UPDATE sessions SET cache_prefix_hash = ?, updated_at = ? WHERE id = ?",
        (prefix_hash, datetime.now().isoformat(), session_id)
    )
```

### 4.4 一致性保障措施

1. **字段顺序固定**：构建前缀时严格按固定顺序拼接字段，避免字典遍历顺序差异。
2. **空白字符规范化**：构建前缀后执行 `.strip()` + 统一换行符为 `\n`。
3. **编码统一**：所有字符串使用 UTF-8 编码，计算哈希前显式 `.encode("utf-8")`。
4. **模板版本化**：系统提示词与规则库带版本号，版本变更时主动失效缓存。

```python
def normalize_prefix(prefix: str) -> str:
    """规范化前缀，确保字节级一致。"""
    # 统一换行符
    prefix = prefix.replace("\r\n", "\n").replace("\r", "\n")
    # 去除首尾空白
    prefix = prefix.strip()
    return prefix
```

---

## 5. 前缀构建规则

### 5.1 前缀内容顺序

前缀段严格按以下顺序构建（顺序变更会导致缓存失效）：

```text
1. Agent 系统提示词（system_prompt）
2. 学位信息（degree）
3. 学科信息（discipline）
4. 导师信息（mentor_info）
5. 硬约束规则库（hard_rules）
6. 报告模板（report_template）
7. 评分权重（scoring_weights）
8. 风格规范规则（style_rules）
```

### 5.2 前缀稳定性保障

| 内容 | 稳定性 | 保障措施 |
|------|--------|----------|
| Agent 系统提示词 | 完全静态 | 从 YAML 文件加载，运行时不变 |
| 学位信息 | 会话级稳定 | 创建会话时确定，不随对话变化 |
| 学科信息 | 会话级稳定 | 同上 |
| 导师信息 | 会话级稳定 | 同上 |
| 硬约束规则库 | 完全静态 | 从 YAML 文件加载，版本化 |
| 报告模板 | 完全静态 | 从 Markdown 文件加载，版本化 |
| 评分权重 | 完全静态 | 从 YAML 文件加载，版本化 |
| 风格规范规则 | 完全静态 | 从 YAML 文件加载，版本化 |

### 5.3 前缀长度控制

前缀段长度控制在 2000-5000 token，避免过长导致缓存成本上升：

- 系统提示词：500-1500 token
- 学位/学科/导师信息：200-500 token
- 硬约束规则库：500-1500 token
- 报告模板：500-1000 token
- 评分权重：200-500 token
- 风格规范规则：300-800 token

---

## 6. 动态内容处理

### 6.1 动态内容分类

| 内容 | 变化频率 | 处理方式 |
|------|----------|----------|
| 用户当前输入 | 每轮变化 | 放在尾段 |
| 最近 2 轮对话 | 每轮变化 | 放在尾段 |
| DST 状态 | 每 5 轮压缩 | 放在中段，压缩后稳定 |
| 候选论题列表 | 阶段性变化 | 放在中段，阶段内稳定 |
| 检索结果 | 每次检索变化 | 放在尾段 |

### 6.2 DST 压缩与缓存协同

DST 压缩是缓存优化的关键：

```text
未压缩时（每轮变化）：
  前缀 + 完整历史（10 轮） + 用户输入
  → 历史部分每轮变化，缓存失效

压缩后（5 轮触发压缩）：
  前缀 + DST 摘要（稳定） + 最近 2 轮 + 用户输入
  → DST 摘要在 5 轮内稳定，前缀 + DST 摘要可命中缓存
```

### 6.3 候选列表稳定性

候选论题列表在阶段二生成后，阶段三、四、五内保持稳定：

```text
阶段二：生成候选列表 → 列表变化
阶段三：硬约束校验 → 列表稳定（仅修复标题）
阶段四：报告生成 → 列表稳定（仅选定 Top 1）
阶段五：深度辅助 → 列表稳定
```

因此，候选列表放在中段，阶段三、四、五可命中缓存。

### 6.4 检索结果处理

检索结果每次调用都不同，放在尾段：

```python
def build_tail_with_search(recent_history: list, user_input: str, search_results: list) -> str:
    """构建包含检索结果的尾段。"""
    tail = build_dynamic_tail(recent_history, user_input)
    if search_results:
        tail += f"""
## 检索结果
{json.dumps(search_results, ensure_ascii=False, indent=2)}
"""
    return tail
```

---

## 7. 缓存命中率监控

### 7.1 监控指标

| 指标 | 计算方式 | 告警阈值 |
|------|----------|----------|
| 全局命中率 | Σ hit_tokens / Σ prompt_tokens | < 90% 告警 |
| 会话级命中率 | 单会话 hit_tokens / prompt_tokens | < 80% 告警 |
| Agent 级命中率 | 单 Agent hit_tokens / prompt_tokens | < 85% 告警 |
| 缓存失效次数 | prefix_hash 不一致的次数 | > 10 次/小时告警 |

### 7.2 监控端点

通过 `/api/cache-stats` 端点查询缓存统计：

```json
{
  "total_requests": 1234,
  "cache_hits": 1187,
  "cache_hit_rate": 0.962,
  "total_cached_tokens": 1234567,
  "total_uncached_tokens": 56789,
  "cost_saved_cny": 45.67,
  "by_session": {
    "sess_xxx": {
      "requests": 25,
      "hits": 23,
      "hit_rate": 0.92,
      "cached_tokens": 23456,
      "uncached_tokens": 1234
    }
  },
  "by_agent": {
    "orchestrator": {
      "requests": 257,
      "hits": 245,
      "hit_rate": 0.953,
      "cached_tokens": 234567,
      "uncached_tokens": 12345
    },
    "reasoner": {
      "requests": 320,
      "hits": 312,
      "hit_rate": 0.975,
      "cached_tokens": 345678,
      "uncached_tokens": 8765
    }
  }
}
```

### 7.3 监控实现

```python
def record_cache_stats(session_id: str, agent_id: str, usage: dict):
    """记录缓存统计到透明账本。"""
    cached_tokens = usage.get("prompt_cache_hit_tokens", 0)
    uncached_tokens = usage.get("prompt_cache_miss_tokens", 0)
    prompt_tokens = usage.get("prompt_tokens", 0)

    # 记录到 budget_ledger 表
    execute_insert(
        "INSERT INTO budget_ledger (id, session_id, agent_id, model, "
        "prompt_tokens, completion_tokens, total_tokens, cached_prompt_tokens, "
        "uncached_prompt_tokens, cost, purpose, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), session_id, agent_id, model,
         prompt_tokens, usage.get("completion_tokens", 0),
         usage.get("total_tokens", 0), cached_tokens, uncached_tokens,
         cost, purpose, datetime.now().isoformat())
    )
```

### 7.4 告警机制

当命中率低于阈值时，触发告警：

```python
def check_cache_health():
    """检查缓存健康度，触发告警。"""
    stats = get_cache_stats()
    if stats["cache_hit_rate"] < 0.90:
        send_alert(
            level="warning",
            message=f"全局缓存命中率低于 90%：{stats['cache_hit_rate']:.2%}",
            details=stats
        )

    for agent_id, agent_stats in stats["by_agent"].items():
        if agent_stats["hit_rate"] < 0.85:
            send_alert(
                level="warning",
                message=f"Agent {agent_id} 缓存命中率低于 85%：{agent_stats['hit_rate']:.2%}",
                details=agent_stats
            )
```

---

## 8. ≥95% 命中率达成方法

### 8.1 达成路径

```text
当前命中率：~70%
目标命中率：≥ 95%

优化路径：
  1. 三段式 Prompt 架构 → 提升至 ~85%
  2. 前缀哈希校验 → 提升至 ~90%
  3. DST 压缩协同 → 提升至 ~93%
  4. 候选列表稳定化 → 提升至 ~95%
  5. 字节级一致性保障 → 稳定在 ≥ 95%
```

### 8.2 关键优化措施

#### 8.2.1 前缀最大化

将尽可能多的静态内容放入前缀段：

- 系统提示词（必须）
- 学位/学科/导师信息（必须）
- 硬约束规则库（必须）
- 报告模板（必须）
- 评分权重（推荐）
- 风格规范规则（推荐）

#### 8.2.2 动态内容最小化

将动态内容压缩到最小：

- 用户输入：原文保留（不可避免）
- 最近对话：仅保留 2 轮（4 条消息）
- DST 状态：压缩为摘要
- 检索结果：仅保留 Top 5

#### 8.2.3 前缀版本化

系统提示词与规则库带版本号，版本变更时主动失效缓存：

```python
PREFIX_VERSION = "v8.0.1"

def build_prefix_with_version(agent_id: str, session_context: dict) -> str:
    prefix = build_prefix(agent_id, session_context)
    return f"<!-- prefix_version: {PREFIX_VERSION} -->\n{prefix}"
```

#### 8.2.4 会话级缓存预热

新会话首次请求时，主动发送一个「预热」请求，将前缀写入缓存：

```python
def warmup_cache(session_id: str, agent_id: str):
    """会话级缓存预热。"""
    session = get_session(session_id)
    prefix = build_prefix(agent_id, session["context"])
    # 发送一个最小请求，仅包含前缀，将前缀写入缓存
    call_llm(
        model=get_agent_config(agent_id)["model"],
        prompt=prefix + "\n\n请回复 OK。",
        max_tokens=10
    )
```

### 8.3 命中率优化检查清单

- [ ] 前缀段是否包含所有静态内容？
- [ ] 前缀段是否字节级一致（哈希校验通过）？
- [ ] 动态内容是否放在尾段？
- [ ] DST 压缩是否在 5 轮时触发？
- [ ] 候选列表是否在阶段内稳定？
- [ ] 前缀哈希是否存储在 sessions 表？
- [ ] 缓存命中率是否实时监控？
- [ ] 命中率低于阈值时是否告警？

---

## 9. 兜底策略

### 9.1 缓存失效场景

| 场景 | 原因 | 兜底策略 |
|------|------|----------|
| 前缀变更 | 系统提示词更新 | 主动失效缓存，重新预热 |
| TTL 过期 | 缓存超时（>1 小时） | 自动重新写入缓存 |
| 模型切换 | Agent 绑定模型变更 | 重新预热新模型的缓存 |
| 参数变更 | temperature 等参数变化 | 不影响缓存（仅影响生成） |
| 服务异常 | DeepSeek API 不可用 | 切换备选模型 |

### 9.2 兜底降级链

```text
正常流程：
  构建前缀 → 哈希校验 → 发送请求 → 命中缓存 → 返回结果

缓存失效流程：
  构建前缀 → 哈希校验 → 发送请求 → 未命中缓存 → 全量计算 → 返回结果
  （功能正常，仅成本上升）

服务异常流程：
  发送请求 → API 错误 → 切换备选模型 → 重新预热缓存 → 返回结果

全部失败流程：
  所有模型不可用 → 返回 HTTP 500 → 记录错误日志 → 提示用户重试
```

### 9.3 缓存预热失败处理

```python
async def warmup_cache_with_retry(session_id: str, agent_id: str, max_retries: int = 3):
    """带重试的缓存预热。"""
    for attempt in range(max_retries):
        try:
            await warmup_cache(session_id, agent_id)
            return True
        except Exception as e:
            logger.warning(f"缓存预热失败（尝试 {attempt + 1}/{max_retries}）：{e}")
            await asyncio.sleep(2 ** attempt)

    logger.error(f"缓存预热彻底失败，将使用非缓存模式")
    return False
```

---

## 10. 缓存与多 Agent 协同

### 10.1 Agent 间缓存复用

不同 Agent 若使用相同模型且前缀部分重叠，可复用缓存：

```text
Orchestrator 前缀（claude-sonnet-4.5）：
  系统提示词 + 学位信息 + 规则库

Reasoner 前缀（deepseek-r2）：
  系统提示词 + 学位信息 + 规则库 + 评分权重

→ 学位信息 + 规则库部分可复用（若模型相同）
→ 但 Reasoner 用 deepseek-r2，Orchestrator 用 claude-sonnet-4.5，模型不同无法复用
```

### 10.2 同模型 Agent 缓存复用

Reasoner 与 Critic 都使用 deepseek-r2，前缀部分可复用：

```text
Reasoner 前缀：
  Reasoner 系统提示词 + 学位信息 + 规则库 + 评分权重

Critic 前缀：
  Critic 系统提示词 + 学位信息 + 规则库

→ 学位信息 + 规则库部分可复用（前缀重叠）
→ 但系统提示词不同，整体前缀不同，无法直接命中
→ 优化：将系统提示词放在前缀末尾，最大化前缀重叠
```

### 10.3 缓存复用优化

```python
def build_shared_prefix(session_context: dict, hard_rules: str) -> str:
    """构建共享前缀（多个 Agent 可复用）。"""
    return f"""## 学位信息
学位：{session_context['degree']}
学科：{session_context['discipline']}
导师信息：
{session_context['mentor_info']}

## 硬约束规则库
{hard_rules}
"""

def build_agent_prefix(agent_id: str, shared_prefix: str) -> str:
    """构建 Agent 专属前缀（共享前缀 + Agent 系统提示词）。"""
    agent_config = get_agent_config(agent_id)
    # 共享前缀在前，Agent 系统提示词在后，最大化缓存复用
    return f"{shared_prefix}\n## Agent 系统提示词\n{agent_config['system_prompt']}"
```

---

## 11. 性能基准与压测

### 11.1 性能基准

| 场景 | 无缓存 | 有缓存（95% 命中） | 优化幅度 |
|------|--------|-------------------|----------|
| 单次 Agent 调用延迟 | 3.5s | 1.2s | 65% |
| 单次 Agent 调用成本 | 0.05 元 | 0.012 元 | 76% |
| 五阶段流程总延迟 | 90s | 35s | 61% |
| 五阶段流程总成本 | 12 元 | 3.2 元 | 73% |
| 单会话 token 用量 | 80K | 50K | 37% |

### 11.2 压测方案

```text
压测场景：
  1. 单会话五阶段流程（顺序执行）
  2. 10 会话并发五阶段流程
  3. 100 会话并发五阶段流程

压测指标：
  - 端到端延迟（P50/P95/P99）
  - 缓存命中率
  - API 错误率
  - 资源占用（CPU/内存）

压测工具：
  - locust（Python 压测框架）
  - 自定义脚本（基于 asyncio）
```

### 11.3 压测脚本示例

```python
import asyncio
import time
from locust import HttpUser, task, between

class ThesisMinerUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def five_stage_flow(self):
        # 1. 创建会话
        session = self.client.post("/api/sessions", json={
            "title": "压测会话",
            "degree": "master",
            "discipline": "计算机科学",
            "mentor_info": "导师项目：医疗大模型"
        }).json()

        # 2. 执行五阶段流程
        for stage in ["info_confirm", "creativity", "validation", "generation", "deep_assist"]:
            self.client.post(f"/api/sessions/{session['id']}/stage", json={
                "stage": stage,
                "input": "压测输入"
            })

        # 3. 查询缓存统计
        self.client.get("/api/cache-stats")
```

---

## 12. 常见问题与排查

### 12.1 缓存命中率低

**现象**：全局命中率 < 90%

**排查步骤**：

1. 检查前缀哈希是否一致（`/api/cache-stats` → by_session → prefix_hash 一致性）
2. 检查前缀内容是否包含动态内容（如时间戳、随机数）
3. 检查 DST 压缩是否正常触发（dialog_rounds > 5 时）
4. 检查候选列表是否在阶段内稳定
5. 检查模型是否频繁切换

**解决方案**：

- 修复前缀构建逻辑，移除动态内容
- 启用 DST 压缩
- 稳定候选列表
- 减少模型切换

### 12.2 缓存预热失败

**现象**：新会话首次请求未命中缓存

**排查步骤**：

1. 检查 DeepSeek API 是否可用
2. 检查 API Key 是否正确
3. 检查模型是否支持缓存
4. 检查网络连接

**解决方案**：

- 重试缓存预热
- 切换备选模型
- 降级为非缓存模式

### 12.3 缓存成本未下降

**现象**：缓存命中率 ≥ 95% 但成本未下降

**排查步骤**：

1. 检查 `prompt_cache_hit_tokens` 是否正确记录
2. 检查定价计算是否使用缓存价格（0.1 元/百万 token）
3. 检查是否有大量非缓存请求（如 Searcher 联网检索）

**解决方案**：

- 修复定价计算逻辑
- 对 Searcher 等动态 Agent 单独统计成本

---

## 13. 附录

### 13.1 缓存相关配置

```yaml
# config/cache.yaml
cache:
  enabled: true
  target_hit_rate: 0.95
  alert_threshold: 0.90
  warmup_on_session_create: true
  prefix_version: "v8.0.1"
  ttl_seconds: 3600
  retry:
    max_attempts: 3
    base_delay: 2.0
```

### 13.2 缓存监控 SQL

```sql
-- 查询全局缓存命中率
SELECT
    COUNT(*) as total_requests,
    SUM(cached_prompt_tokens) as total_cached,
    SUM(uncached_prompt_tokens) as total_uncached,
    ROUND(SUM(cached_prompt_tokens) * 1.0 / SUM(prompt_tokens), 4) as hit_rate
FROM budget_ledger
WHERE created_at > datetime('now', '-1 day');

-- 查询会话级缓存命中率
SELECT
    session_id,
    COUNT(*) as requests,
    SUM(cached_prompt_tokens) as cached,
    SUM(uncached_prompt_tokens) as uncached,
    ROUND(SUM(cached_prompt_tokens) * 1.0 / SUM(prompt_tokens), 4) as hit_rate
FROM budget_ledger
GROUP BY session_id
ORDER BY hit_rate ASC;

-- 查询 Agent 级缓存命中率
SELECT
    agent_id,
    COUNT(*) as requests,
    SUM(cached_prompt_tokens) as cached,
    SUM(uncached_prompt_tokens) as uncached,
    ROUND(SUM(cached_prompt_tokens) * 1.0 / SUM(prompt_tokens), 4) as hit_rate
FROM budget_ledger
GROUP BY agent_id
ORDER BY hit_rate ASC;
```

### 13.3 术语表

| 术语 | 定义 |
|------|------|
| KV Cache | 键值缓存，大模型的上下文缓存机制 |
| 前缀段 | Prompt 的静态部分，缓存命中目标 |
| 中段 | Prompt 的半静态部分，DST 压缩后稳定 |
| 尾段 | Prompt 的动态部分，每轮变化 |
| 前缀哈希 | 前缀段的 SHA-256 哈希，用于一致性校验 |
| 命中率 | 缓存命中 token 数 / 总 prompt token 数 |
| 缓存预热 | 新会话首次请求前主动写入缓存 |
| DST 压缩 | 对话状态追踪器压缩历史，提升缓存稳定性 |

### 13.4 变更历史

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| v8.0 | 2026-06-19 | 初始版本，定义三段式 Prompt 架构 |
| v8.1 | （规划中） | 新增跨 Agent 缓存复用 |
| v8.2 | （规划中） | 新增自适应前缀构建 |

---

> 文档版本 v8.0 · 最后更新 2026-06-19 · 维护者：ThesisMiner 团队
